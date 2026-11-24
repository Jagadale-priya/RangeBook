"""Independent 15m classic channel — pre-dual production model (prod2).

Parallel to dual-track (proven/champion) and 5m crown.
Uses stock_signal_data/models/fno_{SYM}.pkl issued tickets — same recipe as
full12y prod2 (~71% NIFTY 1y). Never blocks or replaces dual Calls.
Tag: "15m classic". Kill switch: ENABLE_15M_CLASSIC=0 (default off).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

import path_setup
ROOT = path_setup.ROOT

SYMBOLS = frozenset({"NIFTY", "BANKNIFTY", "SENSEX"})
TAG_CODE = "15m_classic"
TAG_LABEL = "15m classic"
# Match historical prod2 desk: max 2 issued calls / day
DAY_CAP = 2
SIDE_CAP = 2


def enabled() -> bool:
    # Optional parallel research channel (default off). Prefer ENABLE_PRE_DUAL_SINGLE
    # for the true pre-dual live listing path.
    v = str(os.environ.get("ENABLE_15M_CLASSIC", "0")).strip().lower()
    return v not in ("0", "false", "no", "off")


def classic_tag() -> Dict[str, Any]:
    return {
        "code": TAG_CODE,
        "label": TAG_LABEL,
        "detail": (
            "Pre-dual 15m production model (fno_*.pkl · prod2, up to 2/day) "
            "as an independent parallel channel — does not block dual-track or 5m crown."
        ),
        "tone": "baseline",
        "priority": 40,
    }


def _norm_ohlc(bars: Any) -> Optional[pd.DataFrame]:
    if bars is None or len(bars) < 40:
        return None
    df = bars.copy() if hasattr(bars, "copy") else bars
    if not isinstance(df.index, pd.DatetimeIndex):
        return None
    rename = {}
    for c in df.columns:
        cl = str(c).lower()
        if cl in ("open", "high", "low", "close", "volume"):
            rename[c] = cl[:1].upper() + cl[1:]
    if rename:
        df = df.rename(columns=rename)
    if not {"Open", "High", "Low", "Close"}.issubset(set(df.columns)):
        return None
    return df.sort_index()


def _levels(entry: float, decision: str, bars: pd.DataFrame, symbol: str) -> tuple:
    try:
        import fno_dual_score

        clipped = fno_dual_score._clip_levels(symbol, entry, decision, bars)
        if clipped:
            return float(clipped[0]), float(clipped[1])
    except Exception:
        pass
    atr = float((bars["High"] - bars["Low"]).astype(float).tail(14).mean() or entry * 0.002)
    if decision == "BUY":
        return round(entry - 1.2 * atr, 2), round(entry + 1.8 * atr, 2)
    return round(entry + 1.2 * atr, 2), round(entry - 1.8 * atr, 2)


def evaluate_latest(
    symbol: str,
    bars_15m: Any,
    *,
    price: Optional[float] = None,
    asof: Any = None,
    fno_head: Optional[Dict[str, Any]] = None,
    day_range: Optional[dict] = None,
    db_path: Optional[str] = None,
    ignore_enable: bool = False,
) -> Optional[Dict[str, Any]]:
    """Score latest 15m bar with production fno_model — independent of dual.

    ignore_enable=True: allow daily_fill waterfall to probe classic even when
    the standalone classic desk channel is disabled.
    """
    try:
        if not ignore_enable and not enabled():
            return None
        key = str(symbol or "").upper()
        if key not in SYMBOLS:
            return None
        bars = _norm_ohlc(bars_15m)
        if bars is None:
            return None
        if asof is None:
            asof = bars.index[-1]

        import fno_model
        import fno_session_replay as fsr
        import fno_session_rules as fsrules

        pack = fno_model.load(symbol=key)
        if not fno_model.pack_usable(pack):
            return None

        day = str(fsrules.session_date(asof))
        if not ignore_enable:
            try:
                import classic_15m_store as store

                if store.count_today(key, day, db_path=db_path) >= DAY_CAP:
                    return None
            except Exception:
                pass

        # Same listing path as old single-model Calls (score_snapshot → persist),
        # but on this channel only — dual/crown tickets are never touched.
        win = bars.tail(200)
        box = day_range if isinstance(day_range, dict) and day_range else None
        if not box:
            try:
                asof_ts = pd.Timestamp(asof)
                if asof_ts.tzinfo is None and win.index.tz is not None:
                    asof_ts = asof_ts.tz_localize(win.index.tz)
                elif asof_ts.tzinfo is not None and win.index.tz is not None:
                    asof_ts = asof_ts.tz_convert(win.index.tz)
                sess_day = asof_ts.date()
                sess = win.loc[[t.date() == sess_day for t in win.index]]
                if sess is None or len(sess) < 1:
                    sess = win.tail(25)
                box = fsr.session_day_range(sess, lookback=2)
            except Exception:
                try:
                    box = fsr.session_day_range(win.tail(25), lookback=2)
                except Exception:
                    box = {}
        snap = fsr.score_snapshot(
            win,
            symbol=key,
            day_range=box or {},
            model_pack=pack,
            primary=True,
            asof=asof,
            session_ticket=None,
            indications=None,
        )
        issued = snap.get("issued_ticket") or {}
        want = str(issued.get("decision") or "").upper()
        if want not in ("BUY", "SELL"):
            # Fallback: raw head decision (when already scored this cycle)
            head = fno_head if isinstance(fno_head, dict) else (snap.get("fno_head") or {})
            want = str((head or {}).get("decision") or "HOLD").upper()
            if want not in ("BUY", "SELL"):
                return None
            try:
                entry = float(price) if price is not None else float(win["Close"].iloc[-1])
            except (TypeError, ValueError):
                return None
            sl, t1 = _levels(entry, want, win, key)
            p = float((head or {}).get("p_t1") or 0.0)
            model_version = (head or {}).get("model_version") or pack.get("model_version")
        else:
            try:
                entry = float(issued.get("entry") or price or win["Close"].iloc[-1])
            except (TypeError, ValueError):
                return None
            sl = float(issued.get("stop_loss"))
            t1 = float(issued.get("target_1"))
            p = float(issued.get("p_t1") or (snap.get("fno_head") or {}).get("p_t1") or 0.0)
            model_version = (snap.get("fno_head") or {}).get("model_version") or pack.get("model_version")

        try:
            import classic_15m_store as store

            if store.count_today(key, day, side=want, db_path=db_path) >= SIDE_CAP:
                return None
        except Exception:
            pass

        if entry <= 0:
            return None
        bar_ts = bars.index[-1]
        bar_time = bar_ts.isoformat() if hasattr(bar_ts, "isoformat") else str(bar_ts)

        return {
            "symbol": key,
            "decision": want,
            "entry": round(entry, 2),
            "stop_loss": sl,
            "target_1": t1,
            "p_t1": round(p, 4),
            "bar_time": bar_time,
            "session_date": day[:10],
            "taken_at": bar_time,
            "track": TAG_CODE,
            "source": "fno_15m_classic",
            "channel": TAG_LABEL,
            "accuracy_label": TAG_LABEL,
            "accuracy_tags": [classic_tag()],
            "dual_track": False,
            "independent": True,
            "recipe": "prod2_issued_fno_model",
            "model_version": model_version,
            "message": f"{want} 15m classic · p={p*100:.0f}% (prod2 production model)",
        }
    except Exception:
        return None


def attach_to_result(
    result: Dict[str, Any],
    symbol: str,
    bars_15m: Any,
    *,
    price: Optional[float] = None,
    asof: Any = None,
    fno_head: Optional[Dict[str, Any]] = None,
    day_range: Optional[dict] = None,
) -> Dict[str, Any]:
    """Evaluate, persist, notify. Never raises; never touches dual/crown tickets."""
    out: Dict[str, Any] = {"ok": False}
    try:
        if not enabled():
            result["classic_15m"] = {"enabled": False}
            return {"ok": True, "enabled": False}
        key = str(symbol or "").upper()
        if key not in SYMBOLS:
            result["classic_15m"] = {"enabled": True, "signal": None, "reason": "symbol"}
            return {"ok": True, "reason": "symbol"}

        sig = evaluate_latest(
            key,
            bars_15m,
            price=price,
            asof=asof,
            fno_head=fno_head or result.get("fno_model"),
            day_range=day_range,
        )
        result["classic_15m"] = {"enabled": True, "signal": sig}
        if not sig:
            return {"ok": True, "signal": None}

        import classic_15m_store as store

        saved = store.upsert_signal(sig)
        result["classic_15m"]["saved"] = saved
        out = {"ok": True, "signal": sig, "saved": saved}

        if saved.get("ok") and saved.get("created") and saved.get("id") is not None:
            rid = int(saved["id"])
            if store.claim_notify(rid):
                try:
                    import desktop_notify

                    ok = desktop_notify.notify_15m_classic_call(
                        key,
                        sig["decision"],
                        entry=sig.get("entry"),
                        stop=sig.get("stop_loss"),
                        target=sig.get("target_1"),
                        accuracy_label=TAG_LABEL,
                        row_id=rid,
                    )
                    result["classic_15m"]["notified"] = bool(ok)
                    out["notified"] = bool(ok)
                except Exception as exc:
                    result["classic_15m"]["notify_error"] = str(exc)

        try:
            day = sig.get("session_date")
            if day:
                result["classic_15m_today"] = store.list_today(key, day)
        except Exception:
            pass
        return out
    except Exception as exc:
        result["classic_15m_error"] = str(exc)
        return {"ok": False, "error": str(exc)}
