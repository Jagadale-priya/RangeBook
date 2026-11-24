"""Lane A LIVE — Phase-2F day desks (1 call/day) promoted accurate book.

Volume stack stays `STACK_PLUS_CROWN_HTF_CAP2` (golden unchanged).
These desks are the **live accurate** ladder: hard P2F floors kept,
merge = `union_unique_days` (exactly 1 call per calendar day within desk).

Cap2 P2F desks: see `p2f_cap2_live.py` (also PROMOTED).

  python -u prod_live/tests/confirm_p2f_day_live_1y.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

LANE = "LIVE"
STATUS = "PROMOTED"
LOGIC_LEVEL = "P2F"
MODE = "day"  # 1 call / day
NOT_LIVE = False

_HOLD = Path(__file__).resolve().parents[1] / "holding_accurate"
_RECIPES = _HOLD / "phase2f" / "recipes_research.json"

# P2F hard gates (3y hit floors used when desks were built) — do not loosen.
HARD_GATES: Dict[str, float] = {
    "ACC100_MULTI_V11": 100.0,
    "ACC_WIDE_P92_P2F": 99.24,
    "ACC_WIDE_P90_P2F": 95.4,
    "ACC_WIDE_P85_P2F": 89.69,
    "ACC_WIDE_P85B_P2F": 88.4,
    "ACC_WIDE_P80_P2F": 84.72,
    "ACC_WIDE_P75_P2F": 82.71,
}

# Live promote order (priority 1 = highest accuracy)
LIVE_DAY_DESKS: List[str] = [
    "ACC100_MULTI_V11",
    "ACC_WIDE_P92_P2F",
    "ACC_WIDE_P90_P2F",
    "ACC_WIDE_P85_P2F",
    "ACC_WIDE_P85B_P2F",
    "ACC_WIDE_P80_P2F",
    "ACC_WIDE_P75_P2F",
]

# Locked 1y holding window (confirm gate)
WINDOW_1Y = {"start": "2025-11-15", "end": "2026-11-15"}
EXPECTED_1Y: Dict[str, Dict[str, float]] = {
    "ACC100_MULTI_V11": {"n": 86, "hit_pct": 100.0},
    "ACC_WIDE_P92_P2F": {"n": 86, "hit_pct": 100.0},
    "ACC_WIDE_P90_P2F": {"n": 98, "hit_pct": 100.0},
    "ACC_WIDE_P85_P2F": {"n": 114, "hit_pct": 92.98},
    "ACC_WIDE_P85B_P2F": {"n": 116, "hit_pct": 93.1},
    "ACC_WIDE_P80_P2F": {"n": 123, "hit_pct": 90.24},
    "ACC_WIDE_P75_P2F": {"n": 127, "hit_pct": 88.98},
}

# Soft live bar (all promoted day desks clear this on the locked 1y window)
LIVE_HIT_FLOOR_1Y = 87.0

BASE_KEY_BY_DESK: Dict[str, str] = {
    "ACC100_MULTI_V11": "ACC100_MULTI_V5",
    "ACC_WIDE_P92_P2F": "ACC_WIDE_P92",
    "ACC_WIDE_P90_P2F": "ACC_WIDE_P90",
    "ACC_WIDE_P85_P2F": "ACC_WIDE_P85",
    "ACC_WIDE_P85B_P2F": "ACC_WIDE_P85B",
    "ACC_WIDE_P80_P2F": "ACC_WIDE_P80",
    "ACC_WIDE_P75_P2F": "ACC_WIDE_P75",
}

ACCURACY_TAG_BY_DESK: Dict[str, str] = {
    "ACC100_MULTI_V11": "ACC_RANGE_98_100",
    "ACC_WIDE_P92_P2F": "ACC_RANGE_91_100",
    "ACC_WIDE_P90_P2F": "ACC_RANGE_89_96",
    "ACC_WIDE_P85_P2F": "ACC_RANGE_84_90",
    "ACC_WIDE_P85B_P2F": "ACC_RANGE_81_89",
    "ACC_WIDE_P80_P2F": "ACC_RANGE_76_85",
    "ACC_WIDE_P75_P2F": "ACC_RANGE_75_83",
}


def load_phase2f_day_recipes() -> Dict[str, Dict[str, Any]]:
    """Return day-mode P2F candidates keyed by candidate_tag."""
    data = json.loads(_RECIPES.read_text(encoding="utf-8"))
    out: Dict[str, Dict[str, Any]] = {}
    for base, meta in (data.get("candidates") or {}).items():
        if (meta.get("mode") or "day") != "day":
            continue
        tag = meta.get("candidate_tag") or base
        if tag in HARD_GATES:
            out[tag] = dict(meta)
            out[tag]["base_key"] = base
    return out


def stream_tags_for(desk_tag: str) -> List[str]:
    recipes = load_phase2f_day_recipes()
    meta = recipes.get(desk_tag) or {}
    return list(meta.get("stream_tags_research") or meta.get("stream_tags_held") or [])


def stamp_live(
    rows: Iterable[dict],
    desk_tag: str,
    *,
    accuracy_tag: Optional[str] = None,
) -> List[dict]:
    """Stamp a row as LIVE P2F day accurate (multi-tag)."""
    ar = accuracy_tag or ACCURACY_TAG_BY_DESK.get(desk_tag) or ""
    floor = HARD_GATES.get(desk_tag)
    floor_t = None
    if floor is not None:
        floor_t = f"ACC_FLOOR_{str(floor).replace('.', 'p')}" if floor % 1 else f"ACC_FLOOR_{int(floor)}"
    tags = [desk_tag]
    if ar:
        tags.append(ar)
    tags.append(f"LOGIC_{LOGIC_LEVEL}")
    if floor_t:
        tags.append(floor_t)
    tags.append("LANE_LIVE")
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
    """Registry-style stamp fields for a promoted LIVE day desk."""
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
        "tags": [
            desk_tag,
            ar,
            f"LOGIC_{LOGIC_LEVEL}",
            "LANE_LIVE",
        ],
    }


def build_p2f_day_desks(
    phase1: Dict[str, List[dict]],
    by_tag: Dict[str, List[dict]],
) -> Dict[str, List[dict]]:
    """Replay P2F day recipes onto Phase-1 bases; stamp LIVE.

    `phase1` keys are base desks (ACC100_MULTI_V5, ACC_WIDE_P92, …).
    `by_tag` maps stream tag → path-true rows (from rebuild_all_tags).
    """
    # Lazy imports avoid circular load with holding_accurate.registry
    from prod_live.holding_accurate.phase2c.builders import union_unique_days
    from prod_live.holding_accurate.replay import replay_tags

    recipes = load_phase2f_day_recipes()
    out: Dict[str, List[dict]] = {}
    for desk_tag in LIVE_DAY_DESKS:
        meta = recipes.get(desk_tag) or {}
        base_key = BASE_KEY_BY_DESK.get(desk_tag) or meta.get("base_desk") or ""
        base_rows = list(phase1.get(base_key) or [])
        tags = list(meta.get("stream_tags_research") or [])
        if tags:
            rows = replay_tags(base_rows, tags, by_tag, mode="day")
        else:
            rows = union_unique_days([], base_rows) if base_rows else []
            if base_rows and not rows:
                rows = list(base_rows)
        out[desk_tag] = stamp_live(rows, desk_tag)
    return out


def is_live_day_desk(tag: str) -> bool:
    return tag in HARD_GATES
