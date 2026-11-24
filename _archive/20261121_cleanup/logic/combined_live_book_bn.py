"""Combine BANKNIFTY FINAL desks (PROVEN100 + CHAMP_PLUS). NIFTY untouched."""
from __future__ import annotations

from typing import Any, Dict, List

from prod_live.logic import bn_final_live as bn


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
    proven = list(proven if proven is not None else bn.load_proven_calls())
    champ = list(champ if champ is not None else bn.load_held_calls())
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
        "symbol": bn.SYMBOL,
        "rows": rows,
        "n": len(rows),
        "n_proven": len(proven),
        "n_champ": len(champ),
        "blocked": 0,
        "desks": [bn.DESK_PROVEN, bn.DESK_CHAMP],
        "primary": bn.DESK_CHAMP,
        "accuracy_tag": bn.ACCURACY_TAG,
        "brackets": dict(bn.BRACKETS),
        "registry": bn.book_registry(),
    }


def final_book_registry() -> Dict[str, Any]:
    return bn.book_registry()
