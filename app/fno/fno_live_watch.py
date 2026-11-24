"""Server-side F&O desk watch: NIFTY + SENSEX every ~30s.

Runs inside the API process. Does not need the dashboard open or three tabs.
Uses scheduled_refresh (same path as silent F&O refresh) so dual-track, overlay,
and desktop/desk notifications all fire without a browser.

Every ~15 minutes (configurable) also runs a full Analyze pass so ML / tech /
news / VIX snapshots stay fresh — separate from the fast 30s tape loop.

BANKNIFTY is not on the live desk (processing cut); NIFTY logic unchanged.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, time as dt_time
from typing import Any, Callable, Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

IST = ZoneInfo("Asia/Kolkata") if ZoneInfo else None

try:
    import fno_live_config

    CORE_SYMBOLS = tuple(fno_live_config.fno_live_indexes())
except Exception:
    CORE_SYMBOLS = ("NIFTY", "SENSEX")
DEFAULT_FULL_SEC = 15 * 60

_lock = threading.Lock()
_state: Dict[str, Any] = {
    "running": False,
    "enabled": True,
    "poll_sec": 30,
    "full_sec": DEFAULT_FULL_SEC,
    "symbols": list(CORE_SYMBOLS),
    "last_beat": None,
    "last_cycle_sec": None,
    "last_error": None,
    "last_results": {},
    "cycles": 0,
    "last_full_at": None,
    "last_full_sec": None,
    "last_full_results": {},
    "last_full_error": None,
    "full_cycles": 0,
}
_thread: Optional[threading.Thread] = None
_full_thread: Optional[threading.Thread] = None
_stop = threading.Event()
_indian_stocks: Dict[str, str] = {}
_full_predict_fn: Optional[Callable[..., Any]] = None
_last_full_mono: float = 0.0


def set_full_analyze_fn(fn: Optional[Callable[..., Any]]) -> None:
    """Register predict_stock(stock, product='fno') for the 15m full pass."""
    global _full_predict_fn
    _full_predict_fn = fn


def _now_ist() -> datetime:
    if IST:
        return datetime.now(IST)
    return datetime.now()


def in_session(now: Optional[datetime] = None) -> bool:
    now = now or _now_ist()
    if now.weekday() >= 5:
        return False
    t = now.time()
    # Slight pad so open/close tickets and late overlays still settle.
    return dt_time(9, 10) <= t <= dt_time(15, 35)


def watch_state() -> Dict[str, Any]:
    with _lock:
        return dict(_state)


def _set(**kwargs: Any) -> None:
    with _lock:
        _state.update(kwargs)


def _refresh_one(symbol: str) -> Dict[str, Any]:
    import fno_ws_rescore

    t0 = time.time()
    result, err = fno_ws_rescore.scheduled_refresh(symbol, _indian_stocks or {})
    elapsed = round(time.time() - t0, 2)
    if err or result is None:
        return {"symbol": symbol, "ok": False, "error": err or "refresh failed", "elapsed_sec": elapsed}
    decision = str(result.get("decision") or "HOLD")
    active = result.get("active_call") or {}
    return {
        "symbol": symbol,
        "ok": True,
        "decision": decision,
        "active": bool(active and active.get("decision") not in (None, "HOLD")),
        "elapsed_sec": elapsed,
        "overlay": str(
            (result.get("overlay_indication") or {}).get("decision")
            or (result.get("overlay_indication") or {}).get("side")
            or ""
        ).upper()
        in ("BUY", "SELL"),
    }


def run_cycle(symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """One sequential fast pass over the index desk. Safe to call from tests."""
    syms = [str(s).upper() for s in (symbols or _state.get("symbols") or CORE_SYMBOLS)]
    started = time.time()
    results: Dict[str, Any] = {}
    for sym in syms:
        if _stop.is_set():
            break
        try:
            results[sym] = _refresh_one(sym)
        except Exception as exc:
            results[sym] = {"symbol": sym, "ok": False, "error": str(exc)}
    cycle_sec = round(time.time() - started, 2)
    errs = [
        f"{r.get('symbol')}: {r.get('error')}"
        for r in results.values()
        if isinstance(r, dict) and not r.get("ok") and r.get("error")
    ]
    _set(
        last_beat=_now_ist().isoformat(timespec="seconds"),
        last_cycle_sec=cycle_sec,
        last_results=results,
        last_error="; ".join(errs) if errs else None,
        cycles=int(_state.get("cycles") or 0) + 1,
    )
    return {"cycle_sec": cycle_sec, "results": results}


def _full_one(symbol: str) -> Dict[str, Any]:
    fn = _full_predict_fn
    if fn is None:
        return {"symbol": symbol, "ok": False, "error": "full analyze fn not registered"}
    t0 = time.time()
    try:
        result = fn(symbol, force_retrain=False, mode="auto", product="fno")
    except TypeError:
        # Older predict signatures without product kw.
        result = fn(symbol, force_retrain=False, mode="auto")
    elapsed = round(time.time() - t0, 2)
    if not isinstance(result, dict):
        return {"symbol": symbol, "ok": False, "error": "empty full result", "elapsed_sec": elapsed}
    if result.get("error"):
        return {
            "symbol": symbol,
            "ok": False,
            "error": str(result.get("error")),
            "elapsed_sec": elapsed,
        }
    decision = str(result.get("decision") or "HOLD")
    active = result.get("active_call") or {}
    return {
        "symbol": symbol,
        "ok": True,
        "decision": decision,
        "active": bool(active and active.get("decision") not in (None, "HOLD")),
        "elapsed_sec": elapsed,
        "kind": "full",
    }


def run_full_cycle(symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """Full Analyze for each index — refreshes ML/tech/news/VIX snapshots."""
    global _last_full_mono
    if _full_predict_fn is None:
        return {"ok": False, "error": "full analyze fn not registered"}
    syms = [str(s).upper() for s in (symbols or _state.get("symbols") or CORE_SYMBOLS)]
    started = time.time()
    results: Dict[str, Any] = {}
    for sym in syms:
        if _stop.is_set():
            break
        try:
            results[sym] = _full_one(sym)
        except Exception as exc:
            results[sym] = {"symbol": sym, "ok": False, "error": str(exc), "kind": "full"}
    cycle_sec = round(time.time() - started, 2)
    errs = [
        f"{r.get('symbol')}: {r.get('error')}"
        for r in results.values()
        if isinstance(r, dict) and not r.get("ok") and r.get("error")
    ]
    _last_full_mono = time.monotonic()
    _set(
        last_full_at=_now_ist().isoformat(timespec="seconds"),
        last_full_sec=cycle_sec,
        last_full_results=results,
        last_full_error="; ".join(errs) if errs else None,
        full_cycles=int(_state.get("full_cycles") or 0) + 1,
    )
    return {"cycle_sec": cycle_sec, "results": results}


def _maybe_kick_full() -> None:
    """Start a background full-Analyze pass when the 15m cadence is due."""
    global _full_thread
    full_sec = float(_state.get("full_sec") or 0)
    if full_sec <= 0 or _full_predict_fn is None:
        return
    if not in_session():
        return
    if _full_thread is not None and _full_thread.is_alive():
        return
    due = (_last_full_mono <= 0) or ((time.monotonic() - _last_full_mono) >= full_sec)
    if not due:
        return

    def _runner() -> None:
        try:
            run_full_cycle()
        except Exception as exc:
            _set(last_full_error=str(exc))

    _full_thread = threading.Thread(
        target=_runner, name="fno_full_analyze", daemon=True
    )
    _full_thread.start()


def _loop(poll_sec: float) -> None:
    _set(running=True, poll_sec=poll_sec)
    while not _stop.is_set():
        started = time.time()
        try:
            if not _state.get("enabled", True):
                _stop.wait(poll_sec)
                continue
            if in_session():
                run_cycle()
                _maybe_kick_full()
            else:
                _set(last_beat=_now_ist().isoformat(timespec="seconds"), last_error=None)
        except Exception as exc:
            _set(last_error=str(exc))
        # Keep ~poll_sec cadence from cycle start (don't add full wait after a long cycle).
        elapsed = time.time() - started
        remain = max(1.0, float(poll_sec) - elapsed)
        _stop.wait(remain)
    _set(running=False)


def start(
    indian_stocks: Optional[Dict[str, str]] = None,
    *,
    poll_sec: float = 30.0,
    full_sec: float = DEFAULT_FULL_SEC,
    symbols: Optional[List[str]] = None,
) -> bool:
    """Start daemon watch thread. No-op if DISABLE_FNO_LIVE_WATCH=1."""
    global _thread, _indian_stocks, _last_full_mono
    if os.environ.get("DISABLE_FNO_LIVE_WATCH", "").strip().lower() in ("1", "true", "yes"):
        _set(enabled=False, running=False)
        return False
    if _thread and _thread.is_alive():
        # Allow updating full cadence + predict fn on an already-running watch.
        try:
            fs = float(full_sec)
        except (TypeError, ValueError):
            fs = DEFAULT_FULL_SEC
        _set(full_sec=max(0.0, fs), poll_sec=float(poll_sec))
        return False
    if indian_stocks:
        _indian_stocks = dict(indian_stocks)
    else:
        try:
            import market_symbols

            _indian_stocks = dict(getattr(market_symbols, "INDIAN_STOCKS", {}) or {})
        except Exception:
            _indian_stocks = {}
    syms = [str(s).upper() for s in (symbols or CORE_SYMBOLS)]
    try:
        fs = float(full_sec)
    except (TypeError, ValueError):
        fs = DEFAULT_FULL_SEC
    # Env override: FNO_FULL_ANALYZE_SEC=900 (0 disables)
    env_full = os.environ.get("FNO_FULL_ANALYZE_SEC", "").strip()
    if env_full:
        try:
            fs = float(env_full)
        except ValueError:
            pass
    _stop.clear()
    _last_full_mono = 0.0
    _set(
        enabled=True,
        symbols=syms,
        poll_sec=float(poll_sec),
        full_sec=max(0.0, fs),
    )
    _thread = threading.Thread(
        target=_loop,
        args=(float(poll_sec),),
        name="fno_live_watch",
        daemon=True,
    )
    _thread.start()
    return True


def stop() -> None:
    _stop.set()


def load_estimate(poll_sec: float = 30.0, full_sec: float = DEFAULT_FULL_SEC) -> Dict[str, Any]:
    """Human-facing load note for Settings / docs."""
    return {
        "symbols": list(CORE_SYMBOLS),
        "poll_sec": poll_sec,
        "full_sec": full_sec,
        "per_symbol": {
            "kite_history": "5m + 15m candles",
            "quote": "1 live LTP (WS preferred)",
            "model": "F&O head + dual-track + overlay manage",
            "typical_wall_sec": "4–8s sequential",
        },
        "per_cycle": {
            "kite_requests_approx": "12–20 (history + quote + chain)",
            "wall_sec_typical": "12–24s for all three",
            "cpu": "low (tree models; IO-bound)",
            "memory": "small — three 15m/5m frames in process snapshots",
        },
        "full_analyze": {
            "every_sec": full_sec,
            "every_min": round(full_sec / 60.0, 1) if full_sec else 0,
            "what": "Full Analyze (ML + tech + news/VIX + live desks) for all three indices",
            "wall_sec_typical": "30–90s for all three (background thread; does not block 30s tape)",
            "enabled": bool(full_sec and full_sec > 0),
        },
        "fits_interval": True,
        "browser_required": False,
        "api_required": True,
        "note": (
            "Keep the API running on this PC. You do not need F&O open or three tabs. "
            "Fast tape every ~30s; full Analyze every ~15m refreshes ML/news into the snapshot. "
            "Desktop toasts need this Windows session; the hamburger list needs the dashboard open."
        ),
    }
