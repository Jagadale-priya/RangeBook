"""Adapter helper — stamp / recognize promoted P2F day LIVE accurate tags.

Volume selection stays in app/fno (STACK_PLUS_CROWN_HTF_CAP2).
Use this after stack pick to attach LIVE accurate multi-tags when a
listed call belongs to a P2F day desk membership set.

  from prod_live.adapters.stamp_p2f_day import apply_p2f_day_stamp, LIVE_DAY_DESKS
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Set, Tuple

from prod_live.logic.p2f_day_live import (
    LIVE_DAY_DESKS,
    stamp_fields_for,
)


def call_key(row: dict) -> Tuple[str, str, str]:
    return (
        str(row.get("day") or ""),
        str(row.get("decision") or "").upper(),
        str(row.get("hm") or ""),
    )


def membership_keys(desk_rows: Iterable[dict]) -> Set[Tuple[str, str, str]]:
    return {call_key(r) for r in desk_rows}


def apply_p2f_day_stamp(
    payload: Dict[str, Any],
    *,
    desk_tag: str,
    desk_keys: Optional[Set[Tuple[str, str, str]]] = None,
) -> Dict[str, Any]:
    """If payload matches desk membership (or desk_keys is None), merge LIVE stamps."""
    if desk_tag not in LIVE_DAY_DESKS:
        return payload
    if desk_keys is not None and call_key(payload) not in desk_keys:
        return payload
    fields = stamp_fields_for(desk_tag)
    out = dict(payload)
    for k, v in fields.items():
        if k == "tags":
            existing = list(out.get("accuracy_tags") or out.get("tags") or [])
            seen = set(str(x) for x in existing)
            for t in v or []:
                if t and t not in seen:
                    existing.append(t)
                    seen.add(t)
            out["accuracy_tags"] = existing
            out["tags"] = existing
        else:
            out[k] = v
    return out
