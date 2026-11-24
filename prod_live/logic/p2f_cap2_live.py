"""Lane A LIVE — Phase-2F Cap2 desks (≤2 same-side/day) promoted accurate book.

Volume stack stays `STACK_PLUS_CROWN_HTF_CAP2` (golden unchanged).
Hard P2F floors kept. Merge = `union_day_cap2`.

  python -u prod_live/tests/confirm_p2f_cap2_live_1y.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

LANE = "LIVE"
STATUS = "PROMOTED"
LOGIC_LEVEL = "P2F"
MODE = "cap2"
NOT_LIVE = False

_HOLD = Path(__file__).resolve().parents[1] / "holding_accurate"
_RECIPES = _HOLD / "phase2f" / "recipes_research.json"

HARD_GATES: Dict[str, float] = {
    "ACC100_MULTI_V5_CAP2_P2F": 100.0,
    "ACC_WIDE_P92_CAP2_P2F": 99.24,
    "ACC_WIDE_P90_CAP2_P2F": 95.4,
    "ACC_WIDE_P85_CAP2_P2F": 89.69,
}

LIVE_CAP2_DESKS: List[str] = [
    "ACC100_MULTI_V5_CAP2_P2F",
    "ACC_WIDE_P92_CAP2_P2F",
    "ACC_WIDE_P90_CAP2_P2F",
    "ACC_WIDE_P85_CAP2_P2F",
]

WINDOW_1Y = {"start": "2025-11-15", "end": "2026-11-15"}
EXPECTED_1Y: Dict[str, Dict[str, float]] = {
    "ACC100_MULTI_V5_CAP2_P2F": {"n": 124, "hit_pct": 100.0},
    "ACC_WIDE_P92_CAP2_P2F": {"n": 123, "hit_pct": 100.0},
    "ACC_WIDE_P90_CAP2_P2F": {"n": 139, "hit_pct": 99.28},
    "ACC_WIDE_P85_CAP2_P2F": {"n": 169, "hit_pct": 91.12},
}

LIVE_HIT_FLOOR_1Y = 87.0

# Cap2 recipes seed from Phase-1 day base (not Cap2 P1), then merge mode=cap2
BASE_KEY_BY_DESK: Dict[str, str] = {
    "ACC100_MULTI_V5_CAP2_P2F": "ACC100_MULTI_V5",
    "ACC_WIDE_P92_CAP2_P2F": "ACC_WIDE_P92",
    "ACC_WIDE_P90_CAP2_P2F": "ACC_WIDE_P90",
    "ACC_WIDE_P85_CAP2_P2F": "ACC_WIDE_P85",
}

ACCURACY_TAG_BY_DESK: Dict[str, str] = {
    "ACC100_MULTI_V5_CAP2_P2F": "ACC_RANGE_98_100",
    "ACC_WIDE_P92_CAP2_P2F": "ACC_RANGE_91_100",
    "ACC_WIDE_P90_CAP2_P2F": "ACC_RANGE_89_96",
    "ACC_WIDE_P85_CAP2_P2F": "ACC_RANGE_84_90",
}


def load_phase2f_cap2_recipes() -> Dict[str, Dict[str, Any]]:
    data = json.loads(_RECIPES.read_text(encoding="utf-8"))
    out: Dict[str, Dict[str, Any]] = {}
    for base, meta in (data.get("candidates") or {}).items():
        if (meta.get("mode") or "") != "cap2":
            continue
        tag = meta.get("candidate_tag") or base
        if tag in HARD_GATES:
            out[tag] = dict(meta)
            out[tag]["base_key"] = base
    return out


def stamp_live(
    rows: Iterable[dict],
    desk_tag: str,
    *,
    accuracy_tag: Optional[str] = None,
) -> List[dict]:
    ar = accuracy_tag or ACCURACY_TAG_BY_DESK.get(desk_tag) or ""
    floor = HARD_GATES.get(desk_tag)
    floor_t = None
    if floor is not None:
        floor_t = (
            f"ACC_FLOOR_{str(floor).replace('.', 'p')}"
            if floor % 1
            else f"ACC_FLOOR_{int(floor)}"
        )
    tags = [desk_tag]
    if ar:
        tags.append(ar)
    tags.append(f"LOGIC_{LOGIC_LEVEL}")
    if floor_t:
        tags.append(floor_t)
    tags.append("LANE_LIVE")
    tags.append("MODE_CAP2")
    out = []
    for r in rows:
        rr = dict(r)
        rr["lane"] = LANE
        rr["status"] = STATUS
        rr["not_live"] = False
        rr["logic_level"] = LOGIC_LEVEL
        rr["desk_tag"] = desk_tag
        rr["accurate_tag"] = desk_tag
        rr["accuracy_tag"] = ar or rr.get("accuracy_tag")
        rr["accuracy_range_tag"] = ar or rr.get("accuracy_range_tag")
        rr["mode"] = MODE
        rr["hard_gate"] = floor
        existing = list(rr.get("tags") or [])
        seen = set(existing)
        for t in tags:
            if t and t not in seen:
                existing.append(t)
                seen.add(t)
        rr["tags"] = existing
        out.append(rr)
    return out


def stamp_fields_for(desk_tag: str) -> Dict[str, Any]:
    ar = ACCURACY_TAG_BY_DESK.get(desk_tag) or ""
    return {
        "lane": LANE,
        "status": STATUS,
        "not_live": False,
        "logic_level": LOGIC_LEVEL,
        "desk_tag": desk_tag,
        "accurate_tag": desk_tag,
        "accuracy_tag": ar,
        "accuracy_range_tag": ar,
        "mode": MODE,
        "hard_gate": HARD_GATES.get(desk_tag),
        "tags": [desk_tag, ar, f"LOGIC_{LOGIC_LEVEL}", "LANE_LIVE", "MODE_CAP2"],
    }


def build_p2f_cap2_desks(
    phase1: Dict[str, List[dict]],
    by_tag: Dict[str, List[dict]],
) -> Dict[str, List[dict]]:
    from prod_live.holding_accurate.replay import replay_tags

    recipes = load_phase2f_cap2_recipes()
    out: Dict[str, List[dict]] = {}
    for desk_tag in LIVE_CAP2_DESKS:
        meta = recipes.get(desk_tag) or {}
        base_key = BASE_KEY_BY_DESK.get(desk_tag) or meta.get("base_desk") or ""
        base_rows = list(phase1.get(base_key) or [])
        tags = list(meta.get("stream_tags_research") or [])
        rows = replay_tags(base_rows, tags, by_tag, mode="cap2") if tags else list(base_rows)
        out[desk_tag] = stamp_live(rows, desk_tag)
    return out


def is_live_cap2_desk(tag: str) -> bool:
    return tag in HARD_GATES
