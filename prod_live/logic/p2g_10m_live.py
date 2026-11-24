"""LIVE book — Phase-2G 10m day desks (D10 dual train · ±30 risk).

Same held recipes as RESEARCH P2G; measured ACC_RANGE stamps from 5y confirm.
Promoted as one of the three NIFTY F&O live logics (parallel · never blocks).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from prod_live.logic.p2g_10m import (
    ACCURACY_META_BY_DESK,
    ACCURACY_TAG_BY_DESK,
    BASE_KEY_BY_DESK,
    DAY_DESKS,
    HARD_GATES,
    WINDOW_1Y,
    WINDOW_3Y,
    WINDOW_5Y,
    WINDOW_EXTRA_2Y,
)

LANE = "LIVE"
STATUS = "PROMOTED"
LOGIC_LEVEL = "P2G"
MODE = "day"
NOT_LIVE = False

LIVE_P2G_DESKS: List[str] = list(DAY_DESKS)

_HOLD = Path(__file__).resolve().parents[1] / "holding_accurate" / "phase2g"
_RECIPES = _HOLD / "recipes_research.json"
_ACC_TAGS = _HOLD / "accuracy_tags.json"
_REPORT_5Y = (
    Path(__file__).resolve().parents[1] / "reports" / "5y" / "ACC_PHASE2G_10M_5Y.json"
)

# Locked expected from ACC_PHASE2G_10M_5Y.json (full 5y book per desk)
EXPECTED_5Y: Dict[str, Dict[str, float]] = {
    "ACC100_MULTI_V12_P2G_10M": {"n": 256, "hit_pct": 98.05},
    "ACC_WIDE_P92_P2G_10M": {"n": 174, "hit_pct": 92.53},
    "ACC_WIDE_P90_P2G_10M": {"n": 320, "hit_pct": 94.69},
    "ACC_WIDE_P85_P2G_10M": {"n": 283, "hit_pct": 90.11},
    "ACC_WIDE_P85B_P2G_10M": {"n": 418, "hit_pct": 88.76},
    "ACC_WIDE_P80_P2G_10M": {"n": 431, "hit_pct": 83.53},
    "ACC_WIDE_P75_P2G_10M": {"n": 472, "hit_pct": 82.42},
}

EXPECTED_1Y: Dict[str, Dict[str, float]] = {
    "ACC100_MULTI_V12_P2G_10M": {"n": 61, "hit_pct": 100.0},
    "ACC_WIDE_P92_P2G_10M": {"n": 34, "hit_pct": 100.0},
    "ACC_WIDE_P90_P2G_10M": {"n": 75, "hit_pct": 100.0},
    "ACC_WIDE_P85_P2G_10M": {"n": 61, "hit_pct": 96.72},
    "ACC_WIDE_P85B_P2G_10M": {"n": 104, "hit_pct": 94.23},
    "ACC_WIDE_P80_P2G_10M": {"n": 98, "hit_pct": 83.67},
    "ACC_WIDE_P75_P2G_10M": {"n": 109, "hit_pct": 83.49},
}

EXPECTED_3Y: Dict[str, Dict[str, float]] = {
    "ACC100_MULTI_V12_P2G_10M": {"n": 165, "hit_pct": 100.0},
    "ACC_WIDE_P92_P2G_10M": {"n": 109, "hit_pct": 98.17},
    "ACC_WIDE_P90_P2G_10M": {"n": 207, "hit_pct": 95.65},
    "ACC_WIDE_P85_P2G_10M": {"n": 189, "hit_pct": 92.06},
    "ACC_WIDE_P85B_P2G_10M": {"n": 280, "hit_pct": 88.93},
    "ACC_WIDE_P80_P2G_10M": {"n": 270, "hit_pct": 84.81},
    "ACC_WIDE_P75_P2G_10M": {"n": 294, "hit_pct": 82.99},
}


def load_phase2g_recipes() -> Dict[str, Dict[str, Any]]:
    data = json.loads(_RECIPES.read_text(encoding="utf-8"))
    out: Dict[str, Dict[str, Any]] = {}
    for base, meta in (data.get("candidates") or {}).items():
        tag = meta.get("candidate_tag") or base
        if tag in HARD_GATES:
            out[tag] = dict(meta)
            out[tag]["base_key"] = base
    return out


def stamp_fields_for(desk_tag: str) -> Dict[str, Any]:
    meta = dict(ACCURACY_META_BY_DESK.get(desk_tag) or {})
    ar = str(meta.get("accuracy_tag") or ACCURACY_TAG_BY_DESK.get(desk_tag) or "")
    band = str(meta.get("accuracy_band") or "")
    ft = str(meta.get("floor_tag") or "")
    tags = [desk_tag]
    if ar:
        tags.append(ar)
    if band:
        tags.append(f"ACC_BAND_{band}")
    if ft:
        tags.append(ft)
    tags.extend([f"LOGIC_{LOGIC_LEVEL}", "LANE_LIVE"])
    return {
        "lane": LANE,
        "status": STATUS,
        "not_live": False,
        "logic_level": LOGIC_LEVEL,
        "desk_tag": desk_tag,
        "accurate_tag": desk_tag,
        "accuracy_tag": ar,
        "accuracy_range_tag": ar,
        "accuracy_lo": meta.get("accuracy_lo"),
        "accuracy_hi": meta.get("accuracy_hi"),
        "accuracy_band": band,
        "mode": MODE,
        "hard_gate": HARD_GATES.get(desk_tag),
        "dual_model": "10m_train",
        "brackets": {"target": 30.0, "sl": 30.0, "risk": 30.0},
        "tags": tags,
    }


def stamp_live(
    rows: Iterable[dict],
    desk_tag: str,
    *,
    accuracy_tag: Optional[str] = None,
) -> List[dict]:
    fields = stamp_fields_for(desk_tag)
    if accuracy_tag:
        fields["accuracy_tag"] = accuracy_tag
        fields["accuracy_range_tag"] = accuracy_tag
        tags = [desk_tag, accuracy_tag] + [
            t for t in fields["tags"] if t not in (desk_tag, fields.get("accuracy_tag"))
        ]
        fields["tags"] = tags
    out = []
    for r in rows:
        rr = dict(r)
        rr["lane"] = LANE
        rr["status"] = STATUS
        rr["not_live"] = False
        rr["logic_level"] = LOGIC_LEVEL
        rr["desk_tag"] = desk_tag
        rr["accurate_tag"] = desk_tag
        rr["accuracy_tag"] = fields["accuracy_tag"]
        rr["accuracy_range_tag"] = fields["accuracy_range_tag"]
        rr["accuracy_lo"] = fields.get("accuracy_lo")
        rr["accuracy_hi"] = fields.get("accuracy_hi")
        rr["accuracy_band"] = fields.get("accuracy_band")
        rr["mode"] = MODE
        rr["hard_gate"] = HARD_GATES.get(desk_tag)
        rr["book"] = "p2g_10m"
        rr["source_desk"] = desk_tag
        rr["dual_model"] = "10m_train"
        rr["brackets"] = fields.get("brackets")
        existing = list(rr.get("tags") or [])
        seen = set(existing)
        for t in fields["tags"]:
            if t and t not in seen:
                existing.append(t)
                seen.add(t)
        # drop RESEARCH lane if present
        rr["tags"] = [t for t in existing if t != "LANE_RESEARCH"]
        if "LANE_LIVE" not in rr["tags"]:
            rr["tags"].append("LANE_LIVE")
        out.append(rr)
    return out


def expected_snapshot() -> Dict[str, Any]:
    return {
        "desks": list(LIVE_P2G_DESKS),
        "windows": {
            "1y": WINDOW_1Y,
            "3y": WINDOW_3Y,
            "5y": WINDOW_5Y,
            "extra_2y": WINDOW_EXTRA_2Y,
        },
        "expected_1y": EXPECTED_1Y,
        "expected_3y": EXPECTED_3Y,
        "expected_5y": EXPECTED_5Y,
        "accuracy_tags": ACCURACY_TAG_BY_DESK,
        "report": str(_REPORT_5Y).replace("\\", "/"),
        "recipes": str(_RECIPES).replace("\\", "/"),
        "accuracy_tags_file": str(_ACC_TAGS).replace("\\", "/"),
    }
