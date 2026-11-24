"""Event notes for the book.

An RBI policy day raises risk and the call is still allowed. The Union Budget
is 1 February, or the next weekday when that date falls on a weekend, and
that day stays a hold.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

# Decision day (last day) of each RBI MPC meeting, FY 2026-27.
RBI_DECISION_DAYS = {
    date(2026, 4, 8),
    date(2026, 6, 5),
    date(2026, 8, 5),
    date(2026, 10, 7),
    date(2026, 12, 4),
    date(2027, 2, 5),
}


def budget_day(year: int) -> date:
    day = date(year, 2, 1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def event_risk(day: date) -> Optional[str]:
    """Shown on the call. It does not block."""
    if day in RBI_DECISION_DAYS:
        return "RBI policy day — event risk is higher. The call is still allowed."
    return None


def event_hold(day: date) -> Optional[str]:
    if day == budget_day(day.year):
        return "Union Budget day — no new call."
    return None
