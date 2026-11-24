"""Replay held Phase-2c stream-tag recipes onto Phase-1 desks.

Does not mutate Phase-1. Rebuilds candidate desks when a mined tag→rows map is provided.

  from prod_live.holding_accurate.phase2c.builders import replay_held_candidate
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

_DIR = Path(__file__).resolve().parent
_RECIPES = json.loads((_DIR.parent / "recipes.json").read_text(encoding="utf-8"))


def _hm_mins(hm: str) -> int:
    try:
        h, m = str(hm).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 12 * 60


def _side(r: dict) -> str:
    return str(r.get("decision") or "").upper()


def union_unique_days(base: Iterable[dict], extra: Iterable[dict]) -> List[dict]:
    days = {str(r.get("day") or "") for r in base}
    out = [dict(r) for r in base]
    for r in extra:
        day = str(r.get("day") or "")
        if not day or day in days:
            continue
        days.add(day)
        out.append(dict(r))
    return out


def union_day_cap2(base: Iterable[dict], extra: Iterable[dict], *, cap: int = 2) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in base:
        by[str(r.get("day") or "")].append(dict(r))
    for r in extra:
        day = str(r.get("day") or "")
        cur = by[day]
        sig = (_side(r), str(r.get("hm") or ""))
        if any((_side(x), str(x.get("hm") or "")) == sig for x in cur):
            continue
        cur.append(dict(r))
        cur.sort(
            key=lambda x: (_hm_mins(str(x.get("hm") or "99:99")), -float(x.get("p_t1") or 0))
        )
        by[day] = cur[:cap]
    out: List[dict] = []
    for day in sorted(by):
        out.extend(by[day])
    return out


def held_recipe(base_or_cand: str) -> Optional[Dict[str, Any]]:
    cands = _RECIPES.get("candidates") or {}
    if base_or_cand in cands:
        return cands[base_or_cand]
    for meta in cands.values():
        if meta.get("candidate_tag") == base_or_cand:
            return meta
    return None


def replay_held_candidate(
    phase1_rows: List[dict],
    by_tag: Dict[str, List[dict]],
    base_or_cand: str,
    *,
    stamp_tag: Optional[str] = None,
) -> Tuple[List[dict], List[str]]:
    """Apply held stream tags in order onto a Phase-1 desk. Returns (rows, applied_tags)."""
    meta = held_recipe(base_or_cand)
    if not meta:
        return list(phase1_rows), []
    mode = meta.get("mode") or "day"
    merge = union_day_cap2 if mode == "cap2" else union_unique_days
    cur = list(phase1_rows)
    applied: List[str] = []
    for tag in meta.get("stream_tags_held") or []:
        rows = by_tag.get(tag)
        if not rows:
            continue
        merged = merge(cur, rows)
        if len(merged) > len(cur):
            cur = merged
            applied.append(tag)
    cand = stamp_tag or meta.get("candidate_tag") or base_or_cand
    out = []
    for r in cur:
        rr = dict(r)
        rr["desk_tag"] = cand
        rr["phase2c_held"] = True
        rr["lane"] = "HOLDING"
        rr["status"] = "HOLDING"
        out.append(rr)
    return out, applied


def all_held_bases() -> List[str]:
    return list((_RECIPES.get("candidates") or {}).keys())
