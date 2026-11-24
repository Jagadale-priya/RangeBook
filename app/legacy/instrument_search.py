"""Search NSE cash and index symbols from the cached Kite instrument master.

Watchlists hold tradable underlyings only — no option legs (CE/PE).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

import kite_instruments
from kite_data import INDEX_KITE

import product_analysis

_CATALOG_NAME = "search_catalog.json"
_CACHE: Dict[str, Any] = {"mtime": None, "rows": []}
_TOKEN = re.compile(r"^[A-Z][A-Z0-9&-]{0,19}$")


def _catalog_path() -> str:
    return os.path.join(kite_instruments.cache_dir(), _CATALOG_NAME)


def _index_key(ex: str, tradingsymbol: str) -> Optional[str]:
    for key, (e, sym) in INDEX_KITE.items():
        if ex == e and tradingsymbol == sym:
            return key
    return None


def _tags(symbol: str) -> List[str]:
    key = symbol.strip().upper()
    tags: List[str] = ["Intraday"]
    if product_analysis.is_fno_primary(key):
        tags.append("Index F&O")
    elif product_analysis.is_fno_stock_eligible_symbol(key):
        tags.append("Stock F&O")
    return tags


def rebuild_from_kite_rows(rows: List[Any]) -> int:
    """Rebuild search_catalog.json from a fresh kite.instruments() dump."""
    out: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        ex = str(row.get("exchange") or "").upper()
        sym = str(row.get("tradingsymbol") or "").strip()
        it = str(row.get("instrument_type") or "").upper()
        seg = str(row.get("segment") or "").upper()
        name = str(row.get("name") or sym).strip()
        if not sym or ex != "NSE":
            continue
        if it in ("CE", "PE", "FUT") or ex == "NFO":
            continue
        key: Optional[str] = None
        if it in ("EQ", "BE") and seg not in ("INDICES",):
            key = sym.upper()
        else:
            key = _index_key(ex, sym)
        if not key or not _TOKEN.match(key) or key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "symbol": key,
                "tradingsymbol": sym,
                "name": name,
                "exchange": ex,
                "instrument_type": it or "EQ",
                "tags": _tags(key),
            }
        )
    out.sort(key=lambda r: r["symbol"])
    path = _catalog_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"count": len(out), "symbols": out}, handle, indent=0)
    _CACHE["mtime"] = None
    return len(out)


def _load_rows() -> List[Dict[str, Any]]:
    path = _catalog_path()
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return []
    if _CACHE.get("mtime") == mtime:
        return list(_CACHE.get("rows") or [])
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    rows = list(data.get("symbols") or [])
    _CACHE["mtime"] = mtime
    _CACHE["rows"] = rows
    return rows


def catalog_ready() -> bool:
    return bool(_load_rows())


def ensure_catalog() -> bool:
    """Build search_catalog.json when the token cache exists but search was never warmed."""
    if catalog_ready():
        return True
    import kite_data

    if not kite_data.kite_enabled():
        return False
    ok, _err = kite_instruments.refresh_instruments(force=True)
    return catalog_ready() if ok else False


def resolve_addable_symbol(raw: str) -> Optional[str]:
    """Return the desk symbol if it exists in the Kite catalog."""
    key = str(raw or "").strip().upper()
    if not _TOKEN.match(key):
        return None
    for row in _load_rows():
        if row.get("symbol") == key:
            return key
    # Index aliases users type
    if key in INDEX_KITE:
        return key
    if key in INDEX_KITE:
        ex, sym = INDEX_KITE[key]
        ins = f"{ex}:{sym}"
    else:
        ins = f"NSE:{key}"
    idx = kite_instruments._load_index()
    if ins in idx:
        return key
    return None


def _score(row: Dict[str, Any], q: str) -> int:
    sym = str(row.get("symbol") or "").upper()
    name = str(row.get("name") or "").upper()
    ts = str(row.get("tradingsymbol") or "").upper()
    if sym == q:
        return 1000
    if sym.startswith(q):
        return 900 - len(sym)
    if ts.startswith(q):
        return 850 - len(ts)
    if q in sym:
        return 700
    if name.startswith(q):
        return 650 - len(name) // 10
    if q in name:
        return 500
    return 0


def search(query: str, *, limit: int = 12) -> Dict[str, Any]:
    q = " ".join(str(query or "").strip().upper().split())
    rows = _load_rows()
    if q and not rows:
        ensure_catalog()
        rows = _load_rows()
    if not q:
        return {"available": bool(rows), "query": "", "results": [], "hint": _hint(rows)}
    if not rows:
        return {"available": False, "query": q, "results": [], "hint": _hint(rows)}
    ranked = []
    for row in rows:
        sc = _score(row, q)
        if sc > 0:
            ranked.append((sc, row))
    ranked.sort(key=lambda item: (-item[0], item[1].get("symbol")))
    results = []
    for _sc, row in ranked[: max(1, min(int(limit), 30))]:
        results.append(
            {
                "symbol": row["symbol"],
                "name": row.get("name") or row["symbol"],
                "tradingsymbol": row.get("tradingsymbol"),
                "tags": row.get("tags") or _tags(row["symbol"]),
            }
        )
    return {"available": True, "query": q, "results": results, "hint": None}


def _hint(rows: List[Dict[str, Any]]) -> str:
    if rows:
        return None
    return "Connect Kite and refresh instruments once (Settings or GET /kite/instruments/refresh). Then search works from the live NSE list."
