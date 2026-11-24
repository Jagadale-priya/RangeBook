"""Combine SENSEX FINAL desks (PROVEN100 + CHAMP_PLUS). NIFTY untouched."""
from __future__ import annotations

from typing import Any, Dict, List

from prod_live.logic import sensex_final_live as sx


def call_key(row: dict) -> str:
    day = str(row.get("day") or "")[:10]
    hm = str(row.get("hm") or row.get("time") or "")[:5]
    side = str(row.get("decision") or row.get("side") or "").upper()
    return f"{day}|{hm}|{side}"


def combine_live_rows(
    proven: List[dict] | None = None,
    champ: List[dict] | None = None,
) -> Dict[str, Any]:
    """Union desks by call_key; CHAMP wins on collision. Never blocks."""
    proven = list(proven if proven is not None else sx.load_proven_calls())
    champ = list(champ if champ is not None else sx.load_held_calls())
    by_key: Dict[str, dict] = {}
    order: List[str] = []
    for src, rows in (("proven", proven), ("champ", champ)):
        for r in rows:
            k = call_key(r)
            if k not in by_key:
                order.append(k)
            by_key[k] = dict(r)
            by_key[k]["combine_source"] = src
    rows = [by_key[k] for k in order]
    return {
        "symbol": sx.SYMBOL,
        "rows": rows,
        "n": len(rows),
        "n_proven": len(proven),
        "n_champ": len(champ),
        "blocked": 0,
        "desks": [sx.DESK_PROVEN, sx.DESK_CHAMP],
        "primary": sx.DESK_CHAMP,
        "accuracy_tag": sx.ACCURACY_TAG,
        "brackets": dict(sx.BRACKETS),
        "registry": sx.book_registry(),
    }


def final_book_registry() -> Dict[str, Any]:
    return sx.book_registry()
