"""Holding-accurate registry — ALL levels P1→P2F with accurate tags.

Phase-1 numbers stay locked in logic/accurate_desks.DESK_REGISTRY.
Complete desk map: desks_held.json · human doc: DESKS.md

P2F **day** desks (1 call/day) are **PROMOTED to LIVE** — see
`prod_live.logic.p2f_day_live`. Cap2 P2F remains HOLDING.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from prod_live.logic.p2f_day_live import LIVE_DAY_DESKS, stamp_fields_for as _live_day_stamp
from prod_live.logic.p2f_cap2_live import LIVE_CAP2_DESKS, stamp_fields_for as _live_cap2_stamp

_DIR = Path(__file__).resolve().parent
_RECIPES_P2C = json.loads((_DIR / "recipes.json").read_text(encoding="utf-8"))
_HELD = json.loads((_DIR / "desks_held.json").read_text(encoding="utf-8"))

PHASE1_LOGIC = "prod_live/logic/accurate_desks.py"
PHASE1_STREAMS = "prod_live/logic/acc100_streams.py"
PHASE1_STATUS = "LOCKED"
PHASE2C_STATUS = "HELD"
PHASE2D_STATUS = "HELD"
PHASE2E_STATUS = "HELD"
PHASE2F_STATUS = "HELD"
PHASE2F_DAY_LIVE = "PROMOTED"
PHASE2F_CAP2_LIVE = "PROMOTED"
LATEST_LEVEL = "P2F"
LANE = "HOLDING"
NOT_LIVE = True
STATUS = "HELD_COMPLETE"
LIVE_DAY_PROMOTED = set(LIVE_DAY_DESKS)
LIVE_CAP2_PROMOTED = set(LIVE_CAP2_DESKS)

# Full desk map (accurate_tag → meta)
DESKS_HELD: Dict[str, Dict[str, Any]] = dict(_HELD.get("desks") or {})

# Phase-2c held desk snapshot (compat)
PHASE2C_HELD: Dict[str, Dict[str, Any]] = {}
for _base, _meta in (_RECIPES_P2C.get("candidates") or {}).items():
    cand = _meta.get("candidate_tag") or f"{_base}_P2C"
    held = _meta.get("held_3y") or {}
    PHASE2C_HELD[cand] = {
        "base_desk": _meta.get("base_desk") or _base.replace("_CAP2", ""),
        "mode": _meta.get("mode") or "day",
        "floor": _meta.get("floor"),
        "research_3y": {
            "n": held.get("n"),
            "hit_pct": held.get("hit_pct"),
        },
        "delta_vs_phase1_3y": _meta.get("delta_vs_phase1_3y"),
        "stream_count": len(_meta.get("stream_tags_held") or []),
        "status": PHASE2C_STATUS,
        "lane": LANE,
        "not_live": True,
        "kind": "holding_phase2c_candidate",
        "accurate_tag": cand,
        "accuracy_range_tag": (DESKS_HELD.get(cand) or {}).get("accuracy_range_tag"),
    }


def recipes() -> Dict[str, Any]:
    return _RECIPES_P2C


def held_complete() -> Dict[str, Any]:
    return _HELD


def desk_meta(accurate_tag: str) -> Optional[Dict[str, Any]]:
    return DESKS_HELD.get(accurate_tag)


def accurate_tags(*, level: Optional[str] = None, latest_only: bool = False) -> List[str]:
    out = []
    for tag, m in DESKS_HELD.items():
        if latest_only and m.get("logic_level") != LATEST_LEVEL:
            continue
        if level and m.get("logic_level") != level:
            continue
        out.append(tag)
    return sorted(out)


def stamp_fields_for(accurate_tag: str) -> Dict[str, Any]:
    """Multi-tag stamp: desk + accuracy-range + band + floor + logic level.

    Promoted P2F day/Cap2 desks stamp lane=LIVE / not_live=False.
    """
    if accurate_tag in LIVE_DAY_PROMOTED or accurate_tag in LIVE_CAP2_PROMOTED:
        base = (
            _live_day_stamp(accurate_tag)
            if accurate_tag in LIVE_DAY_PROMOTED
            else _live_cap2_stamp(accurate_tag)
        )
        m = DESKS_HELD.get(accurate_tag) or {}
        base["accuracy_lo"] = m.get("accuracy_lo")
        base["accuracy_hi"] = m.get("accuracy_hi")
        base["accuracy_band"] = m.get("accuracy_band")
        tags = list(m.get("tags") or base.get("tags") or [])
        if "LANE_LIVE" not in tags:
            tags.append("LANE_LIVE")
        base["tags"] = tags
        return base
    m = DESKS_HELD.get(accurate_tag) or {}
    ar = m.get("accuracy_tag") or m.get("accuracy_range_tag")
    return {
        "lane": LANE,
        "logic_level": m.get("logic_level"),
        "desk_tag": accurate_tag,
        "accurate_tag": accurate_tag,
        "accuracy_tag": ar,
        "accuracy_range_tag": ar,
        "accuracy_lo": m.get("accuracy_lo"),
        "accuracy_hi": m.get("accuracy_hi"),
        "accuracy_band": m.get("accuracy_band"),
        "tags": list(m.get("tags") or []),
        "status": m.get("status"),
        "not_live": True,
    }


def candidate_stream_tags(candidate_or_base: str) -> list[str]:
    """Resolve stream tags from any held recipe file (P2C→P2F)."""
    # P2C held
    cands = _RECIPES_P2C.get("candidates") or {}
    if candidate_or_base in cands:
        return list(cands[candidate_or_base].get("stream_tags_held") or [])
    for meta in cands.values():
        if meta.get("candidate_tag") == candidate_or_base:
            return list(meta.get("stream_tags_held") or [])
    # Later phases
    for rel in (
        "phase2d/recipes_research.json",
        "phase2e/recipes_research.json",
        "phase2f/recipes_research.json",
    ):
        path = _DIR / rel
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for base, meta in (data.get("candidates") or {}).items():
            if candidate_or_base in (base, meta.get("candidate_tag")):
                return list(
                    meta.get("stream_tags_research")
                    or meta.get("stream_tags_held")
                    or []
                )
    return []
