"""EMPTY_FILL_FADE1030_GAP055_T35 — holding empty-day structure fill.

HOLDING (not finalized / not auto-wired to live).
Fires only when the volume stack has 0 calls that day.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set


TAG = "EMPTY_FILL_FADE1030_GAP055_T35"
TRACK = "empty_fade_gap055_t35"
PRIORITY = 5  # after crown in stack merge order
GAP_MIN_PCT = 0.55
ENTRY_HM = "10:30"
RISK = 35.0  # T35 / S35


def gap_pct(open_px: float, prior_close: float) -> float:
    return (open_px - prior_close) / prior_close * 100.0


def qualifies_gap(open_px: float, prior_close: float, *, gap_min: float = GAP_MIN_PCT) -> bool:
    if prior_close <= 0:
        return False
    return abs(gap_pct(open_px, prior_close)) >= gap_min


def fade_side(open_px: float, entry_px: float) -> str:
    """Fade the open at entry: at/above open → SELL, below → BUY."""
    return "SELL" if entry_px >= open_px else "BUY"


def build_empty_fill_row(
    *,
    day: str,
    open_px: float,
    prior_close: float,
    entry_px: float,
    hm: str = ENTRY_HM,
    risk: float = RISK,
    gap_min: float = GAP_MIN_PCT,
    win: Optional[bool] = None,
    points: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[dict]:
    """Build one holding empty-fill ticket, or None if gap gate fails."""
    if not qualifies_gap(open_px, prior_close, gap_min=gap_min):
        return None
    side = fade_side(open_px, entry_px)
    gap = round(gap_pct(open_px, prior_close), 4)
    row: Dict[str, Any] = {
        "day": day,
        "hm": hm,
        "decision": side,
        "entry": float(entry_px),
        "open": float(open_px),
        "prior_close": float(prior_close),
        "gap_pct": gap,
        "risk": float(risk),
        "t1": float(entry_px + risk) if side == "BUY" else float(entry_px - risk),
        "sl": float(entry_px - risk) if side == "BUY" else float(entry_px + risk),
        "track": TRACK,
        "priority": PRIORITY,
        "holding_tag": TAG,
        "accurate": False,
        "accurate_tag": None,  # structure fill — never AGREE stamp
        "p_t1": 0.5,
    }
    if win is not None:
        row["win"] = bool(win)
    if points is not None:
        row["points"] = float(points)
    if extra:
        row.update(extra)
    return row


def stack_call_days(stack_rows: Iterable[dict]) -> Set[str]:
    return {str(r.get("day") or "") for r in stack_rows if r.get("day")}


def merge_stack_plus_empty_fill(
    stack_rows: List[dict],
    fill_rows: List[dict],
    *,
    day_cap: int = 2,
) -> List[dict]:
    """Add empty fills only on days the stack is silent; then same-side cap2."""
    silent = stack_call_days(stack_rows)
    # only fills on days NOT in stack
    extras = [dict(r) for r in fill_rows if str(r.get("day") or "") not in silent]
    for r in extras:
        r.setdefault("track", TRACK)
        r.setdefault("priority", PRIORITY)
        r.setdefault("holding_tag", TAG)
        r["accurate"] = False
        r["accurate_tag"] = None

    by_day: Dict[str, List[dict]] = defaultdict(list)
    for r in list(stack_rows) + extras:
        by_day[str(r.get("day") or "")].append(dict(r))

    out: List[dict] = []
    for day in sorted(by_day):
        cands = sorted(
            by_day[day],
            key=lambda r: (
                int(r.get("priority", 9)),
                -float(r.get("p_t1") or 0),
                str(r.get("hm") or ""),
            ),
        )
        picked: List[dict] = []
        side_lock: Optional[str] = None
        for r in cands:
            if len(picked) >= day_cap:
                break
            side = str(r.get("decision") or "").upper()
            if side_lock is None:
                side_lock = side
            elif side != side_lock:
                continue
            picked.append(r)
        out.extend(picked)
    return out
