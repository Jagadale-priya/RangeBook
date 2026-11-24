"""Phase-2G RESEARCH — P2F day logic with dual = 10m train model.

Not live. Same hard floors / day merge as P2F; dual universe = D10.
"""
from __future__ import annotations

from typing import Dict, List

LANE = "RESEARCH"
STATUS = "RESEARCH"
LOGIC_LEVEL = "P2G"
MODE = "day"
NOT_LIVE = True

# Same floors as P2F day
HARD_GATES: Dict[str, float] = {
    "ACC100_MULTI_V12_P2G_10M": 100.0,
    "ACC_WIDE_P92_P2G_10M": 99.24,
    "ACC_WIDE_P90_P2G_10M": 95.4,
    "ACC_WIDE_P85_P2G_10M": 89.69,
    "ACC_WIDE_P85B_P2G_10M": 88.4,
    "ACC_WIDE_P80_P2G_10M": 84.72,
    "ACC_WIDE_P75_P2G_10M": 82.71,
}

DAY_DESKS: List[str] = list(HARD_GATES.keys())

BASE_KEY_BY_DESK: Dict[str, str] = {
    "ACC100_MULTI_V12_P2G_10M": "ACC100_MULTI_V5",
    "ACC_WIDE_P92_P2G_10M": "ACC_WIDE_P92",
    "ACC_WIDE_P90_P2G_10M": "ACC_WIDE_P90",
    "ACC_WIDE_P85_P2G_10M": "ACC_WIDE_P85",
    "ACC_WIDE_P85B_P2G_10M": "ACC_WIDE_P85B",
    "ACC_WIDE_P80_P2G_10M": "ACC_WIDE_P80",
    "ACC_WIDE_P75_P2G_10M": "ACC_WIDE_P75",
}

ACCURACY_TAG_BY_DESK: Dict[str, str] = {
    "ACC100_MULTI_V12_P2G_10M": "ACC_RANGE_94_100",
    "ACC_WIDE_P92_P2G_10M": "ACC_RANGE_83_100",
    "ACC_WIDE_P90_P2G_10M": "ACC_RANGE_92_100",
    "ACC_WIDE_P85_P2G_10M": "ACC_RANGE_86_97",
    "ACC_WIDE_P85B_P2G_10M": "ACC_RANGE_88_95",
    "ACC_WIDE_P80_P2G_10M": "ACC_RANGE_81_85",
    "ACC_WIDE_P75_P2G_10M": "ACC_RANGE_81_84",
}

# Measured lo/hi from 1y·3y·5y·extra_2y (ACC_PHASE2G_10M_5Y.json)
ACCURACY_META_BY_DESK: Dict[str, Dict[str, object]] = {
    "ACC100_MULTI_V12_P2G_10M": {"accuracy_tag": "ACC_RANGE_94_100", "accuracy_lo": 94.51, "accuracy_hi": 100.0, "accuracy_band": "B_HIGH_90", "floor_tag": "ACC_FLOOR_100"},
    "ACC_WIDE_P92_P2G_10M": {"accuracy_tag": "ACC_RANGE_83_100", "accuracy_lo": 83.08, "accuracy_hi": 100.0, "accuracy_band": "D_VOL_80", "floor_tag": "ACC_FLOOR_99p24"},
    "ACC_WIDE_P90_P2G_10M": {"accuracy_tag": "ACC_RANGE_92_100", "accuracy_lo": 92.92, "accuracy_hi": 100.0, "accuracy_band": "B_HIGH_90", "floor_tag": "ACC_FLOOR_95p4"},
    "ACC_WIDE_P85_P2G_10M": {"accuracy_tag": "ACC_RANGE_86_97", "accuracy_lo": 86.17, "accuracy_hi": 96.72, "accuracy_band": "C_MID_85", "floor_tag": "ACC_FLOOR_89p69"},
    "ACC_WIDE_P85B_P2G_10M": {"accuracy_tag": "ACC_RANGE_88_95", "accuracy_lo": 88.41, "accuracy_hi": 94.23, "accuracy_band": "C_MID_85", "floor_tag": "ACC_FLOOR_88p4"},
    "ACC_WIDE_P80_P2G_10M": {"accuracy_tag": "ACC_RANGE_81_85", "accuracy_lo": 81.37, "accuracy_hi": 84.81, "accuracy_band": "D_VOL_80", "floor_tag": "ACC_FLOOR_84p72"},
    "ACC_WIDE_P75_P2G_10M": {"accuracy_tag": "ACC_RANGE_81_84", "accuracy_lo": 81.46, "accuracy_hi": 83.49, "accuracy_band": "D_VOL_80", "floor_tag": "ACC_FLOOR_82p71"},
}

# Compare windows (same style as P2F live confirm)
WINDOW_1Y = {"start": "2025-11-15", "end": "2026-11-15"}
WINDOW_3Y = {"start": "2023-11-16", "end": "2026-11-15"}
WINDOW_5Y = {"start": "2021-11-16", "end": "2026-11-15"}
# Extra slice beyond held 3y confirm (older 2y inside 5y)
WINDOW_EXTRA_2Y = {"start": "2021-11-16", "end": "2023-11-15"}
# P2F day 1y reference (locked)
P2F_1Y_REF: Dict[str, Dict[str, float]] = {
    "ACC100_MULTI_V11": {"n": 86, "hit_pct": 100.0},
    "ACC_WIDE_P92_P2F": {"n": 86, "hit_pct": 100.0},
    "ACC_WIDE_P90_P2F": {"n": 98, "hit_pct": 100.0},
    "ACC_WIDE_P85_P2F": {"n": 114, "hit_pct": 92.98},
    "ACC_WIDE_P85B_P2F": {"n": 116, "hit_pct": 93.1},
    "ACC_WIDE_P80_P2F": {"n": 123, "hit_pct": 90.24},
    "ACC_WIDE_P75_P2F": {"n": 127, "hit_pct": 88.98},
}


def stamp_research(rows, desk_tag: str):
    """Stamp RESEARCH P2G 10m multi-tags with measured ACC_RANGE."""
    meta = ACCURACY_META_BY_DESK.get(desk_tag) or {}
    ar = str(meta.get("accuracy_tag") or ACCURACY_TAG_BY_DESK.get(desk_tag) or "")
    band = str(meta.get("accuracy_band") or "")
    ft = str(meta.get("floor_tag") or "")
    lo = meta.get("accuracy_lo")
    hi = meta.get("accuracy_hi")
    tags = [desk_tag]
    if ar:
        tags.append(ar)
    if band:
        tags.append(f"ACC_BAND_{band}")
    if ft:
        tags.append(ft)
    tags.extend([f"LOGIC_{LOGIC_LEVEL}", "LANE_RESEARCH"])
    out = []
    for r in rows:
        rr = dict(r)
        rr["lane"] = LANE
        rr["status"] = STATUS
        rr["not_live"] = True
        rr["logic_level"] = LOGIC_LEVEL
        rr["desk_tag"] = desk_tag
        rr["accurate_tag"] = desk_tag
        rr["accuracy_tag"] = ar
        rr["accuracy_range_tag"] = ar
        rr["accuracy_lo"] = lo
        rr["accuracy_hi"] = hi
        rr["accuracy_band"] = band
        rr["mode"] = MODE
        rr["hard_gate"] = HARD_GATES.get(desk_tag)
        existing = list(rr.get("tags") or [])
        seen = set(existing)
        for t in tags:
            if t and t not in seen:
                existing.append(t)
                seen.add(t)
        rr["tags"] = existing
        out.append(rr)
    return out

