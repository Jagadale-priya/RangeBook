"""Append fresh Kite 15m bars into fno_validate CSV tapes."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore

FNO_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_signal_data", "fno_validate")


def _norm(df: Any) -> Optional[Any]:
    if df is None or pd is None or len(df) == 0:
        return None
    out = df.copy()
    colmap = {str(c).lower(): c for c in out.columns}
    for src, dst in (("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close"), ("volume", "Volume")):
        if dst not in out.columns and src in colmap:
            out[dst] = out[colmap[src]]
    if "Close" not in out.columns:
        return None
    if "Volume" not in out.columns:
        out["Volume"] = 0.0
    return out.sort_index()


def merge_into_csv(symbol: str, fresh: Any, *, prefer_5y: bool = True) -> Tuple[Optional[str], int]:
    """Merge fresh bars into local 15m CSV; return path and new bar count."""
    if pd is None:
        return None, 0
    sym = symbol.strip().upper()
    fresh_n = _norm(fresh)
    if fresh_n is None:
        return None, 0
    os.makedirs(FNO_CACHE, exist_ok=True)
    path = os.path.join(FNO_CACHE, f"{sym}_15m_5y.csv" if prefer_5y else f"{sym}_15m_6m.csv")
    if not os.path.isfile(path):
        alt = os.path.join(FNO_CACHE, f"{sym}_15m.csv")
        path = alt if os.path.isfile(alt) else path
    before = 0
    if os.path.isfile(path):
        old = _norm(pd.read_csv(path, index_col=0, parse_dates=True))
        if old is not None:
            before = len(old)
            merged = pd.concat([old, fresh_n])
        else:
            merged = fresh_n
    else:
        merged = fresh_n
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    merged.to_csv(path)
    return path, max(0, len(merged) - before)


def fetch_and_merge(symbol: str, days: int = 12) -> Dict[str, Any]:
    try:
        import kite_data

        if not kite_data.kite_enabled():
            return {"ok": False, "symbol": symbol, "error": "kite disabled"}
        df, err = kite_data.fetch_historical_candles(symbol, "15minute", days=days)
        if df is None:
            return {"ok": False, "symbol": symbol, "error": err or "fetch failed"}
        path, added = merge_into_csv(symbol, df)
        return {"ok": True, "symbol": symbol, "path": path, "bars_added": added}
    except Exception as exc:
        return {"ok": False, "symbol": symbol, "error": str(exc)}


def ingest_symbols(symbols: List[str], days: int = 12) -> Dict[str, Any]:
    rows = [fetch_and_merge(s, days=days) for s in symbols]
    return {"ok": True, "results": rows}
