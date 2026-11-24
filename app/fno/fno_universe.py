"""F&O underlyings the desk tracks. NIFTY + SENSEX by default (BANKNIFTY off)."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_SYMBOLS = ("NIFTY", "SENSEX")
# Kite spot instrument for each index underlying. Stock underlyings quote on NSE under their own name.
INDEX_SPOT = {
    "NIFTY": ("NSE", "NIFTY 50"),
    "BANKNIFTY": ("NSE", "NIFTY BANK"),
    "FINNIFTY": ("NSE", "NIFTY FIN SERVICE"),
    "MIDCPNIFTY": ("NSE", "NIFTY MID SELECT"),
    "NIFTYNXT50": ("NSE", "NIFTY NEXT 50"),
    "SENSEX": ("BSE", "SENSEX"),
    "BANKEX": ("BSE", "BANKEX"),
}
TRAIN_YEARS = 5.0

_lock = threading.Lock()
_memo: Optional[List[str]] = None
_training: Dict[str, Dict[str, Any]] = {}


def _path() -> str:
    custom = os.environ.get("STOCK_SIGNAL_DATA_DIR", "").strip()
    root = custom or os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_signal_data")
    return os.path.join(root, "fno_universe.json")


def _norm(symbol: Any) -> str:
    return str(symbol or "").strip().upper()


def symbols() -> List[str]:
    global _memo
    with _lock:
        if _memo is not None:
            return list(_memo)
        out: List[str] = []
        try:
            with open(_path(), encoding="utf-8") as fh:
                out = [_norm(s) for s in (json.load(fh).get("symbols") or []) if _norm(s)]
        except (OSError, json.JSONDecodeError, AttributeError):
            out = []
        _memo = out or list(DEFAULT_SYMBOLS)
        return list(_memo)


def _save(syms: List[str]) -> None:
    global _memo
    path = _path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"symbols": syms, "saved_at": datetime.now().isoformat()}, fh, indent=2)
    with _lock:
        _memo = list(syms)


def contains(symbol: Any) -> bool:
    return _norm(symbol) in symbols()


def is_index(symbol: Any) -> bool:
    return _norm(symbol) in INDEX_SPOT


def derivatives_exchange(symbol: Any) -> str:
    """BSE indices trade on BFO; everything else on NFO."""
    spot = INDEX_SPOT.get(_norm(symbol))
    return "BFO" if spot and spot[0] == "BSE" else "NFO"


def _has_contracts(symbol: str) -> bool:
    import fno_instruments

    return any(r.get("name") == symbol for r in fno_instruments._load_nfo_rows())


def add(symbol: Any) -> Tuple[bool, Optional[str]]:
    sym = _norm(symbol)
    if not sym or not sym.replace("&", "").replace("-", "").isalnum():
        return False, "Type a symbol such as SENSEX or FINNIFTY."
    current = symbols()
    if sym in current:
        return True, None
    _save(current + [sym])
    if not _has_contracts(sym):
        import kite_instruments

        ok, err = kite_instruments.refresh_instruments(force=True)
        if not _has_contracts(sym):
            _save(current)
            if not ok:
                return False, f"Could not refresh Kite instruments: {err}"
            return False, f"Kite lists no F&O contracts for {sym}."
    train_async(sym)
    return True, None


def remove(symbol: Any) -> Tuple[bool, Optional[str]]:
    sym = _norm(symbol)
    current = symbols()
    if sym not in current:
        return True, None
    if len(current) == 1:
        return False, "Keep at least one F&O symbol."
    _save([s for s in current if s != sym])
    return True, None


def train_async(symbol: str) -> bool:
    sym = _norm(symbol)
    with _lock:
        if (_training.get(sym) or {}).get("state") == "training":
            return False
        _training[sym] = {"state": "training", "started_at": datetime.now().isoformat(), "note": "Fetching 15m history"}
    threading.Thread(target=_train, args=(sym,), name=f"fno_train_{sym}", daemon=True).start()
    return True


def _train(sym: str) -> None:
    import train_fno_models

    def _set(**kw: Any) -> None:
        with _lock:
            _training[sym] = {**_training.get(sym, {}), **kw}

    try:
        df, err, _ = train_fno_models.fetch_15m(sym, TRAIN_YEARS)
        if df is not None:
            train_fno_models.save_15m(sym, df)
        else:
            df, _ = train_fno_models._best_local_15m(sym)
        if df is None:
            _set(state="failed", note=err or "No 15m history from Kite")
            return
        _set(note=f"Training on {len(df)} bars")
        row = train_fno_models.train_one(sym, df)
        if row.get("usable"):
            _set(state="ready", note=f"Holdout {row.get('holdout_accuracy')}", finished_at=datetime.now().isoformat())
        else:
            _set(state="failed", note=str(row.get("reason") or "Model did not pass the holdout bar"))
    except Exception as exc:
        _set(state="failed", note=str(exc))


def status() -> List[Dict[str, Any]]:
    import fno_model

    out = []
    for sym in symbols():
        with _lock:
            job = dict(_training.get(sym) or {})
        if job.get("state") == "training":
            model = "training"
        elif fno_model.pack_usable(fno_model.load(symbol=sym)):
            model = "ready"
        else:
            model = "missing"
        out.append({
            "symbol": sym,
            "kind": "index" if is_index(sym) else "stock",
            "exchange": derivatives_exchange(sym),
            "model": model,
            "note": job.get("note"),
            "default": sym in DEFAULT_SYMBOLS,
        })
    return out
