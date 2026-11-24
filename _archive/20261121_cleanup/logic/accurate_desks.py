"""Lane B HOLDING — all researched accurate desks in one place.

Separate from LIVE (`stack` + `AGREE_15M_ANY5`).

Each desk is tagged with an **accuracy_range** derived from research
hit% across 3y → 10y (lo = min window hit, hi = max window hit).

  python -u prod_live/tests/confirm_accurate_desks_3y_match.py
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from .acc100_streams import (
    TAG_DESK,
    TAG_DESK_V2,
    TAG_DESK_V3,
    TAG_DESK_V4,
    TAG_DESK_V5,
    TAG_WIDE_P75,
    TAG_WIDE_P75_CAP2,
    TAG_WIDE_P80,
    TAG_WIDE_P80_CAP2,
    TAG_WIDE_P85,
    TAG_WIDE_P85B,
    TAG_WIDE_P90,
    TAG_WIDE_P92,
    merge_acc100_multi,
    merge_acc100_multi_v2,
    merge_acc100_multi_v3,
    merge_acc100_multi_v4,
    merge_acc100_multi_v5,
    merge_acc_wide_p75,
    merge_acc_wide_p75_cap2,
    merge_acc_wide_p80,
    merge_acc_wide_p80_cap2,
    merge_acc_wide_p85,
    merge_acc_wide_p85b,
    merge_acc_wide_p90,
    merge_acc_wide_p92,
)
from .confirm_dual_tf import (
    TAG_CONFIRM,
    build_confirm_rows,
    merge_proven15_plus_confirm,
)

LANE = "HOLDING"
STATUS = "HOLDING"

# Research window end used when locking ACC_ALL_DESKS_10Y.md
RESEARCH_END = "2026-11-13"

# accuracy_range = f"ACC_RANGE_{lo}_{hi}" from min/max hit across 3y/5y/10y research
# RESEARCH_EXPECTED 3y is the lock target for confirm_accurate_desks_3y_match.py
DESK_REGISTRY: Dict[str, Dict[str, Any]] = {
    "PROVEN15_PLUS_CONFIRM_T30": {
        "accuracy_range": "ACC_RANGE_100_100",
        "accuracy_lo": 100.0,
        "accuracy_hi": 100.0,
        "band": "A_PERFECT_3Y5Y",
        "kind": "holding_accurate_desk",
        "research_3y": {"n": 49, "hit_pct": 100.0},
        "research_5y": None,
        "research_10y": None,
        "note": "proven ∪ confirm T30 only",
    },
    TAG_DESK: {
        "accuracy_range": "ACC_RANGE_96_100",
        "accuracy_lo": 96.62,
        "accuracy_hi": 100.0,
        "band": "A_PERFECT_3Y5Y",
        "kind": "holding_accurate_desk",
        "research_3y": {"n": 70, "hit_pct": 100.0},
        "research_5y": {"n": 104, "hit_pct": 100.0},
        "research_10y": {"n": 148, "hit_pct": 96.62},
    },
    TAG_DESK_V2: {
        "accuracy_range": "ACC_RANGE_97_100",
        "accuracy_lo": 97.8,
        "accuracy_hi": 100.0,
        "band": "A_PERFECT_3Y5Y",
        "kind": "holding_accurate_desk",
        "research_3y": {"n": 118, "hit_pct": 100.0},
        "research_5y": {"n": 171, "hit_pct": 100.0},
        "research_10y": {"n": 227, "hit_pct": 97.8},
    },
    TAG_DESK_V3: {
        "accuracy_range": "ACC_RANGE_97_100",
        "accuracy_lo": 97.9,
        "accuracy_hi": 100.0,
        "band": "A_PERFECT_3Y5Y",
        "kind": "holding_accurate_desk",
        "research_3y": {"n": 122, "hit_pct": 100.0},
        "research_5y": {"n": 181, "hit_pct": 100.0},
        "research_10y": {"n": 238, "hit_pct": 97.9},
    },
    TAG_DESK_V4: {
        "accuracy_range": "ACC_RANGE_97_100",
        "accuracy_lo": 97.92,
        "accuracy_hi": 100.0,
        "band": "A_PERFECT_3Y5Y",
        "kind": "holding_accurate_desk",
        "research_3y": {"n": 123, "hit_pct": 100.0},
        "research_5y": {"n": 182, "hit_pct": 100.0},
        "research_10y": {"n": 240, "hit_pct": 97.92},
    },
    TAG_DESK_V5: {
        "accuracy_range": "ACC_RANGE_98_100",
        "accuracy_lo": 98.17,
        "accuracy_hi": 100.0,
        "band": "A_PERFECT_3Y5Y",
        "kind": "holding_accurate_desk",
        "research_3y": {"n": 141, "hit_pct": 100.0},
        "research_5y": {"n": 202, "hit_pct": 100.0},
        "research_10y": {"n": 273, "hit_pct": 98.17},
    },
    TAG_WIDE_P92: {
        "accuracy_range": "ACC_RANGE_91_100",
        "accuracy_lo": 91.1,
        "accuracy_hi": 99.24,
        "band": "B_HIGH_90",
        "kind": "holding_wide_desk",
        "research_3y": {"n": 131, "hit_pct": 99.24},
        "research_5y": {"n": 199, "hit_pct": 97.49},
        "research_10y": {"n": 292, "hit_pct": 91.1},
    },
    TAG_WIDE_P90: {
        "accuracy_range": "ACC_RANGE_89_96",
        "accuracy_lo": 89.88,
        "accuracy_hi": 95.4,
        "band": "B_HIGH_90",
        "kind": "holding_wide_desk",
        "research_3y": {"n": 174, "hit_pct": 95.4},
        "research_5y": {"n": 259, "hit_pct": 94.98},
        "research_10y": {"n": 405, "hit_pct": 89.88},
    },
    TAG_WIDE_P85: {
        "accuracy_range": "ACC_RANGE_84_90",
        "accuracy_lo": 84.0,
        "accuracy_hi": 89.88,
        "band": "C_MID_85",
        "kind": "holding_wide_desk",
        "research_3y": {"n": 223, "hit_pct": 89.69},
        "research_5y": {"n": 326, "hit_pct": 89.88},
        "research_10y": {"n": 525, "hit_pct": 84.0},
    },
    TAG_WIDE_P85B: {
        "accuracy_range": "ACC_RANGE_81_89",
        "accuracy_lo": 81.1,
        "accuracy_hi": 88.4,
        "band": "C_MID_85",
        "kind": "holding_wide_desk",
        "research_3y": {"n": 250, "hit_pct": 88.4},
        "research_5y": {"n": 364, "hit_pct": 88.19},
        "research_10y": {"n": 598, "hit_pct": 81.1},
    },
    TAG_WIDE_P80: {
        "accuracy_range": "ACC_RANGE_76_85",
        "accuracy_lo": 76.63,
        "accuracy_hi": 84.72,
        "band": "D_VOL_80",
        "kind": "holding_wide_desk",
        "research_3y": {"n": 301, "hit_pct": 84.72},
        "research_5y": {"n": 442, "hit_pct": 83.48},
        "research_10y": {"n": 723, "hit_pct": 76.63},
    },
    TAG_WIDE_P80_CAP2: {
        "accuracy_range": "ACC_RANGE_77_87",
        "accuracy_lo": 77.7,
        "accuracy_hi": 86.29,
        "band": "D_VOL_80",
        "kind": "holding_wide_desk",
        "research_3y": {"n": 525, "hit_pct": 86.29},
        "research_5y": {"n": 770, "hit_pct": 84.94},
        "research_10y": {"n": 1278, "hit_pct": 77.7},
    },
    TAG_WIDE_P75: {
        "accuracy_range": "ACC_RANGE_75_83",
        "accuracy_lo": 75.15,
        "accuracy_hi": 82.71,
        "band": "E_VOL_75",
        "kind": "holding_wide_desk",
        "research_3y": {"n": 347, "hit_pct": 82.71},
        "research_5y": {"n": 514, "hit_pct": 81.71},
        "research_10y": {"n": 833, "hit_pct": 75.15},
    },
    TAG_WIDE_P75_CAP2: {
        "accuracy_range": "ACC_RANGE_75_84",
        "accuracy_lo": 75.5,
        "accuracy_hi": 83.39,
        "band": "E_VOL_75",
        "kind": "holding_wide_desk",
        "research_3y": {"n": 626, "hit_pct": 83.39},
        "research_5y": {"n": 933, "hit_pct": 82.21},
        "research_10y": {"n": 1510, "hit_pct": 75.5},
    },
}


def _stamp(rows: List[dict], desk_tag: str) -> List[dict]:
    meta = DESK_REGISTRY[desk_tag]
    ar = meta["accuracy_range"]
    band = meta["band"]
    band_tag = f"ACC_BAND_{band}" if band else None
    out: List[dict] = []
    for r in rows:
        rr = dict(r)
        accurate = rr.get("holding_tag") or rr.get("accurate_tag") or desk_tag
        rr["desk_tag"] = desk_tag
        rr["accurate_tag"] = accurate
        rr["accuracy_tag"] = ar
        rr["accuracy_range_tag"] = ar
        rr["accuracy_lo"] = meta.get("accuracy_lo")
        rr["accuracy_hi"] = meta.get("accuracy_hi")
        rr["accuracy_band"] = band
        tags = [accurate, ar]
        if band_tag:
            tags.append(band_tag)
        tags.append("LOGIC_P1")
        # de-dupe
        seen = set()
        rr["tags"] = [t for t in tags if t and not (t in seen or seen.add(t))]
        rr["lane"] = LANE
        rr["status"] = STATUS
        out.append(rr)
    return out


def build_proven15_plus_confirm(
    *,
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    tol_min: int = 30,
) -> List[dict]:
    confirm = build_confirm_rows(dual15, dual5, tol_min=tol_min)
    rows = merge_proven15_plus_confirm(proven15, confirm)
    return _stamp(rows, "PROVEN15_PLUS_CONFIRM_T30")


def _v1(
    *,
    proven15,
    dual15,
    dual5,
    crown_by_risk,
    good_by_risk,
    gap_pct_by_day,
    **_kwargs,
) -> List[dict]:
    rows = merge_acc100_multi(
        proven15,
        dual15,
        dual5,
        crown_by_risk.get("20.0") or crown_by_risk.get("20") or [],
        good_by_risk.get("30.0") or good_by_risk.get("30") or [],
        gap_pct_by_day,
    )
    return _stamp(rows, TAG_DESK)


def build_all_accurate_desks(
    *,
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]] = None,
) -> Dict[str, List[dict]]:
    """Build every researched accurate/wide desk, stamped with range tags."""
    kw = dict(
        proven15=proven15,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
    )
    builders: List[Tuple[str, Callable[..., List[dict]]]] = [
        ("PROVEN15_PLUS_CONFIRM_T30", lambda **k: build_proven15_plus_confirm(
            proven15=k["proven15"], dual15=k["dual15"], dual5=k["dual5"]
        )),
        (TAG_DESK, _v1),
        (TAG_DESK_V2, lambda **k: _stamp(merge_acc100_multi_v2(**k), TAG_DESK_V2)),
        (TAG_DESK_V3, lambda **k: _stamp(merge_acc100_multi_v3(**k), TAG_DESK_V3)),
        (TAG_DESK_V4, lambda **k: _stamp(merge_acc100_multi_v4(**k), TAG_DESK_V4)),
        (TAG_DESK_V5, lambda **k: _stamp(merge_acc100_multi_v5(**k), TAG_DESK_V5)),
        (TAG_WIDE_P92, lambda **k: _stamp(merge_acc_wide_p92(**k), TAG_WIDE_P92)),
        (TAG_WIDE_P90, lambda **k: _stamp(merge_acc_wide_p90(**k), TAG_WIDE_P90)),
        (TAG_WIDE_P85, lambda **k: _stamp(merge_acc_wide_p85(**k), TAG_WIDE_P85)),
        (TAG_WIDE_P85B, lambda **k: _stamp(merge_acc_wide_p85b(**k), TAG_WIDE_P85B)),
        (TAG_WIDE_P80, lambda **k: _stamp(merge_acc_wide_p80(**k), TAG_WIDE_P80)),
        (TAG_WIDE_P75, lambda **k: _stamp(merge_acc_wide_p75(**k), TAG_WIDE_P75)),
        (TAG_WIDE_P80_CAP2, lambda **k: _stamp(merge_acc_wide_p80_cap2(**k), TAG_WIDE_P80_CAP2)),
        (TAG_WIDE_P75_CAP2, lambda **k: _stamp(merge_acc_wide_p75_cap2(**k), TAG_WIDE_P75_CAP2)),
    ]
    out: Dict[str, List[dict]] = {}
    for name, fn in builders:
        out[name] = fn(**kw)
    return out


def desks_by_accuracy_range() -> Dict[str, List[str]]:
    """Group desk tags by accuracy_range tag."""
    by: Dict[str, List[str]] = {}
    for desk, meta in DESK_REGISTRY.items():
        by.setdefault(str(meta["accuracy_range"]), []).append(desk)
    return by


def desks_by_band() -> Dict[str, List[str]]:
    by: Dict[str, List[str]] = {}
    for desk, meta in DESK_REGISTRY.items():
        by.setdefault(str(meta["band"]), []).append(desk)
    return by
