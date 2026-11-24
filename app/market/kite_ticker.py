"""KiteTicker WebSocket — streaming LTP/quotes for watchlist (avoids /quote 1 req/s polling)."""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import kite_auth
import kite_data
import kite_instruments
import market_symbols
from market_symbols import stock_key_from_input

try:
    from kiteconnect import KiteTicker
except ImportError:
    KiteTicker = None  # type: ignore

_lock = threading.Lock()
_ticker: Any = None
_running = False
_last_error: Optional[str] = None
_subscribed_keys: List[str] = []
_token_to_key: Dict[int, str] = {}
_ticks: Dict[str, Dict[str, Any]] = {}
_mode = "quote"


def _ws_enabled() -> bool:
    if os.environ.get("KITE_WEBSOCKET", "1").strip().lower() in ("0", "false", "no"):
        return False
    return kite_data.kite_enabled()


def get_tick(stock_key: str) -> Optional[Dict[str, Any]]:
    key = stock_key_from_input(stock_key)
    with _lock:
        row = _ticks.get(key)
        return dict(row) if row else None


def get_ltps(stock_keys: List[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    with _lock:
        for k in stock_keys:
            key = stock_key_from_input(k)
            row = _ticks.get(key)
            if row and row.get("last_price") is not None:
                out[key] = float(row["last_price"])
    return out


def get_status() -> Dict[str, Any]:
    with _lock:
        return {
            "enabled": _ws_enabled(),
            "running": _running,
            "subscribed_count": len(_subscribed_keys),
            "symbols_with_ticks": len(_ticks),
            "mode": _mode,
            "last_error": _last_error,
            "subscribed": list(_subscribed_keys)[:20],
        }


def _on_ticks(_ws, ticks: List[Dict[str, Any]]) -> None:
    now = market_symbols.ist_now().isoformat()
    with _lock:
        for t in ticks or []:
            tok = t.get("instrument_token")
            if tok is None:
                continue
            key = _token_to_key.get(int(tok))
            if not key:
                continue
            ohlc = t.get("ohlc") or {}
            _ticks[key] = {
                "last_price": t.get("last_price"),
                "open": ohlc.get("open"),
                "high": ohlc.get("high"),
                "low": ohlc.get("low"),
                "close": ohlc.get("close"),
                "volume": t.get("volume_traded") or t.get("volume"),
                "change": t.get("change"),
                "exchange_timestamp": t.get("last_trade_time") or t.get("exchange_timestamp") or t.get("timestamp"),
                "updated_at_ist": now,
                "source": "kite_ws",
            }
            if key == "NIFTY":
                import nifty_fno_runtime

                nifty_fno_runtime.record_tick(t.get("last_price"), now)


def _on_connect(_ws, _response) -> None:
    global _last_error
    with _lock:
        tokens = list(_token_to_key.keys())
    if tokens and _ticker is not None:
        try:
            _ticker.subscribe(tokens)
            mode_const = getattr(KiteTicker, "MODE_QUOTE", "quote")
            _ticker.set_mode(mode_const, tokens)
        except Exception as exc:
            _last_error = str(exc)


def _on_close(_ws, code, reason) -> None:
    global _running
    with _lock:
        _running = False


def _on_error(_ws, code, reason) -> None:
    global _last_error
    _last_error = f"ws {code}: {reason}"


def stop_stream() -> None:
    global _ticker, _running, _last_error
    with _lock:
        t = _ticker
        _ticker = None
        _running = False
    if t is not None:
        try:
            t.close()
        except Exception:
            pass
    time.sleep(0.3)


def start_stream(stock_keys: List[str], *, force: bool = False) -> Tuple[bool, Optional[str]]:
    global _ticker, _running, _last_error, _subscribed_keys, _token_to_key, _ticks

    if not _ws_enabled():
        return False, "WebSocket disabled (KITE_WEBSOCKET=0 or Kite off)"

    if KiteTicker is None:
        return False, "Install kiteconnect for KiteTicker"

    keys = [stock_key_from_input(k) for k in stock_keys if k.strip()]
    if not keys:
        return False, "No symbols"

    with _lock:
        if _running and not force and set(keys) <= set(_subscribed_keys):
            return True, None

    stop_stream()
    ok, err = kite_instruments.ensure_cache()
    if not ok:
        return False, err or "Instrument cache missing"

    token_map, missing = kite_instruments.resolve_tokens_for_keys(keys)
    if missing:
        return False, f"Missing instrument tokens: {', '.join(missing[:5])}"

    access_token, terr = kite_auth.get_access_token()
    if not access_token:
        return False, terr or "No Kite token"
    # Vault-first — do not require plaintext env (login often only updates vault/process)
    api_key = (kite_auth._read_env("KITE_API_KEY") or os.environ.get("KITE_API_KEY", "")).strip()
    if not api_key:
        return False, "KITE_API_KEY not set"
    os.environ.setdefault("KITE_API_KEY", api_key)

    inv_token: Dict[int, str] = {v: k for k, v in token_map.items()}

    kws = KiteTicker(api_key, access_token)
    kws.on_ticks = _on_ticks
    kws.on_connect = _on_connect
    kws.on_close = _on_close
    kws.on_error = _on_error

    with _lock:
        _ticker = kws
        _token_to_key = inv_token
        _subscribed_keys = list(token_map.keys())
        _ticks = {}
        _running = True
        _last_error = None

    try:
        kws.connect(threaded=True)
        return True, None
    except Exception as exc:
        _last_error = str(exc)
        _running = False
        return False, str(exc)


def ensure_stream(stock_keys: List[str]) -> Tuple[bool, Optional[str]]:
    if not _ws_enabled():
        return False, "disabled"
    st = get_status()
    if st.get("running"):
        return True, None
    return start_stream(stock_keys)
