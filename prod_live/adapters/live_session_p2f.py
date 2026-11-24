"""Annotate live analyze results with promoted P2F accurate books.

Does **not** change volume stack decision / SL / T1 / track.
Attaches parallel accurate-book metadata + optional accuracy_tags markers.

Used from app/fno after stack pick.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from prod_live.logic.p2f_day_live import LIVE_DAY_DESKS, EXPECTED_1Y as DAY_1Y
from prod_live.logic.p2f_cap2_live import LIVE_CAP2_DESKS, EXPECTED_1Y as CAP2_1Y

BOOK_DAY = "P2F_LIVE_DAY"
BOOK_CAP2 = "P2F_LIVE_CAP2"


def book_snapshot() -> Dict[str, Any]:
    return {
        "status": "PROMOTED",
        "lane": "LIVE",
        "volume_unchanged": True,
        "volume_desk": "STACK_PLUS_CROWN_HTF_CAP2",
        "day": {
            "mode": "day",
            "merge": "1_call_per_day",
            "desks": list(LIVE_DAY_DESKS),
            "primary": LIVE_DAY_DESKS[0],
            "expected_1y": dict(DAY_1Y),
        },
        "cap2": {
            "mode": "cap2",
            "merge": "leq_2_same_side_per_day",
            "desks": list(LIVE_CAP2_DESKS),
            "primary": LIVE_CAP2_DESKS[0],
            "expected_1y": dict(CAP2_1Y),
        },
        "confirm": {
            "day": "prod_live/tests/confirm_p2f_day_live_1y.py",
            "cap2": "prod_live/tests/confirm_p2f_cap2_live_1y.py",
            "volume": "prod_live/tests/confirm_final_hold_1y_match.py",
        },
    }


def _append_tag(tags: List[Any], value: str) -> List[Any]:
    seen = {str(t) for t in tags}
    if value not in seen:
        tags.append(value)
    return tags


def annotate_analyze_result(
    result: Dict[str, Any],
    *,
    symbol: str,
    dual_call: Optional[Dict[str, Any]] = None,
    readings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Attach P2F LIVE book metadata to NIFTY analyze result (safe / additive)."""
    if str(symbol or "").upper() not in ("NIFTY", "NIFTY 50", "NIFTY50"):
        return result
    snap = book_snapshot()
    fa = dict(result.get("fno_analysis") or {})
    fa["p2f_live"] = snap
    result["fno_analysis"] = fa
    result["p2f_live"] = snap

    # Accuracy-first markers (highest accuracy desk first for UI pills)
    markers = [
        snap["day"]["primary"],  # ACC100_MULTI_V11
        "ACC_RANGE_98_100",
        snap["cap2"]["primary"],
        BOOK_DAY,
        BOOK_CAP2,
        "LANE_LIVE",
    ]

    if isinstance(dual_call, dict):
        tags = list(dual_call.get("accuracy_tags") or [])
        # Prepend high-acc markers so UI shows them first
        merged: List[Any] = []
        for m in markers:
            merged = _append_tag(merged, m)
        for t in tags:
            merged = _append_tag(merged, t)
        dual_call["accuracy_tags"] = merged
        dual_call["p2f_live"] = {
            "day_primary": snap["day"]["primary"],
            "cap2_primary": snap["cap2"]["primary"],
            "volume_unchanged": True,
            "ui_combine": "same day+side+hm → 1 call, tags accuracy-first",
        }

    if isinstance(readings, dict):
        tags = list(readings.get("accuracy_tags") or [])
        merged = []
        for m in markers:
            merged = _append_tag(merged, m)
        for t in tags:
            merged = _append_tag(merged, t)
        readings["accuracy_tags"] = merged
        readings["p2f_live"] = snap

    return result
