"""LIVE book — CHAMP_PLUS_T30SL30_CAP6 (champion seed + ticket-fill · ±30).

Held 5y research book + **live ticket-fill engine** for new session days.
Brackets: Target +30 / SL −30. Cap6 same-side. Never blocked by other desks.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from prod_live.logic import champ_plus_engine as eng

LANE = "LIVE"
STATUS = "PROMOTED"
LOGIC_LEVEL = "CHAMP_PLUS"
MODE = "cap6"
NOT_LIVE = False

DESK = "CHAMP_PLUS_T30SL30_CAP6"
ACCURACY_TAG = "ACC_RANGE_93_100"
ACCURACY_LO = 93.19
ACCURACY_HI = 99.61
ACCURACY_BAND = "B_HIGH_90"
FLOOR_TAG = "ACC_FLOOR_99p42"
BRACKETS = {"target": 30.0, "sl": 30.0, "risk": 30.0}

_HOLD = Path(__file__).resolve().parents[1] / "holding_accurate" / "champion_plus"
_CALLS_5Y = _HOLD / "t30_sl30_5y_calls.json"
_REPORT_5Y = (
    Path(__file__).resolve().parents[1] / "reports" / "5y" / "CHAMPION_PLUS_T30_SL30_5Y.json"
)

# Locked windows / expected (refreshed by _lock_nifty_champ_cap6.py)
WINDOW_1Y = {"start": "2025-11-20", "end": "2026-11-20"}
WINDOW_3Y = {"start": "2023-11-20", "end": "2026-11-20"}
WINDOW_5Y = {"start": "2021-11-16", "end": "2026-11-20"}
# Causal Cap6 = live fill_day (no win hindsight) — locked 2026-11-20
EXPECTED = {
    "1y": {"n": 467, "hit_pct": 75.16},
    "3y": {"n": 0, "hit_pct": None},
    "5y": {"n": 1250, "hit_pct": None},
}


def stamp_fields_for() -> Dict[str, Any]:
    return {
        "lane": LANE,
        "status": STATUS,
        "not_live": False,
        "logic_level": LOGIC_LEVEL,
        "desk_tag": DESK,
        "accurate_tag": DESK,
        "accuracy_tag": ACCURACY_TAG,
        "accuracy_range_tag": ACCURACY_TAG,
        "accuracy_lo": ACCURACY_LO,
        "accuracy_hi": ACCURACY_HI,
        "accuracy_band": ACCURACY_BAND,
        "mode": MODE,
        "brackets": dict(BRACKETS),
        "tags": [
            DESK,
            ACCURACY_TAG,
            f"ACC_BAND_{ACCURACY_BAND}",
            FLOOR_TAG,
            f"LOGIC_{LOGIC_LEVEL}",
            "LANE_LIVE",
        ],
    }


def stamp_live(rows: Iterable[dict]) -> List[dict]:
    meta = stamp_fields_for()
    tags = list(meta["tags"])
    out = []
    for r in rows:
        rr = dict(r)
        side = str(rr.get("decision") or rr.get("side") or "").upper()
        if side and not rr.get("decision"):
            rr["decision"] = side
        rr.update(
            {
                "lane": LANE,
                "status": STATUS,
                "not_live": False,
                "logic_level": LOGIC_LEVEL,
                "desk_tag": DESK,
                "accurate_tag": DESK,
                "accuracy_tag": ACCURACY_TAG,
                "accuracy_range_tag": ACCURACY_TAG,
                "accuracy_lo": ACCURACY_LO,
                "accuracy_hi": ACCURACY_HI,
                "accuracy_band": ACCURACY_BAND,
                "mode": MODE,
                "book": "champ_plus",
                "source_desk": DESK,
                "brackets": dict(BRACKETS),
                "t1_pts": BRACKETS["target"],
                "sl_pts": BRACKETS["sl"],
            }
        )
        existing = list(rr.get("tags") or [])
        seen = set(existing)
        for t in tags:
            if t and t not in seen:
                existing.append(t)
                seen.add(t)
        rr["tags"] = existing
        out.append(rr)
    return out


def load_held_calls(*, path: Optional[Path] = None) -> List[dict]:
    """Load frozen CHAMP_PLUS 5y call book and stamp LIVE."""
    p = path or _CALLS_5Y
    raw = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("calls") or []
    return stamp_live(raw)


def load_live_book() -> List[dict]:
    """Held 5y ∪ live-session ledger (stamped)."""
    return stamp_live(eng.load_full_book_raw())


def ensure_session_calls(
    day: Optional[str] = None,
    *,
    dual_call: Optional[dict] = None,
    session_candidates: Optional[Sequence[dict]] = None,
    hm: Optional[str] = None,
    entry: Optional[float] = None,
) -> Dict[str, Any]:
    """Run live ticket-fill for `day` and return stamped day calls + meta.

    Other desks never block. Cap6 same-side is the only day limit.
    """
    day = (day or date.today().isoformat())[:10]
    meta = eng.ensure_session_day(
        day,
        session_candidates=session_candidates,
        dual_call=dual_call,
        hm=hm,
        entry=entry,
    )
    day_calls = stamp_live(meta.get("day_calls") or [])
    added = stamp_live(meta.get("added") or [])
    return {
        **meta,
        "day_calls": day_calls,
        "added": added,
        "desk": DESK,
        "accuracy_tag": ACCURACY_TAG,
        "live_engine": True,
    }


def expected_snapshot() -> Dict[str, Any]:
    # Prefer refreshed 5y report numbers when present
    expected = dict(EXPECTED)
    try:
        if _REPORT_5Y.exists():
            blob = json.loads(_REPORT_5Y.read_text(encoding="utf-8"))
            if isinstance(blob.get("expected"), dict):
                expected.update(blob["expected"])
    except Exception:
        pass
    return {
        "desk": DESK,
        "accuracy_tag": ACCURACY_TAG,
        "windows": {"1y": WINDOW_1Y, "3y": WINDOW_3Y, "5y": WINDOW_5Y},
        "expected": expected,
        "report": str(_REPORT_5Y).replace("\\", "/"),
        "calls": str(_CALLS_5Y).replace("\\", "/"),
        "live_ledger": str(_HOLD / "live_session_calls.json").replace("\\", "/"),
        "live_engine": True,
        "cap": eng.CAP,
        "brackets": dict(BRACKETS),
    }
