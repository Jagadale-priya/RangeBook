"""HTF_ACTIVE_DAY — crown listing gate (prior Volume P40 OR range% median)."""
from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd


def htf_active_day(
    daily: pd.DataFrame,
    asof: str,
    *,
    lookback_sessions: int = 252,
) -> Dict[str, Any]:
    """Return whether crown may list on this session day.

    Fail-open (active=True) if history too short — matches live desk behavior.
    """
    day = str(asof)[:10]
    if daily is None or daily.empty:
        return {"active": True, "reason": "no_daily", "day": day}

    d = daily.copy()
    d["Date"] = pd.to_datetime(d["Date"]).dt.strftime("%Y-%m-%d")
    d = d.sort_values("Date")
    prior = d[d["Date"] < day]
    if prior.empty:
        return {"active": True, "reason": "no_prior", "day": day}

    hist = prior.tail(lookback_sessions + 1)
    if len(hist) < 40:
        return {"active": True, "reason": "short_history", "day": day}

    row = hist.iloc[-1]
    window = hist.iloc[:-1]
    vol = float(row.get("Volume") or 0)
    hi = float(row.get("High") or 0)
    lo = float(row.get("Low") or 0)
    cl = float(row.get("Close") or 1) or 1.0
    range_pct = (hi - lo) / cl * 100.0

    vols = pd.to_numeric(window["Volume"], errors="coerce").dropna()
    ranges = (
        (pd.to_numeric(window["High"], errors="coerce") - pd.to_numeric(window["Low"], errors="coerce"))
        / pd.to_numeric(window["Close"], errors="coerce").replace(0, pd.NA)
        * 100.0
    ).dropna()
    p40 = float(vols.quantile(0.40)) if len(vols) else 0.0
    med = float(ranges.median()) if len(ranges) else 0.0
    active = bool(vol >= p40 or range_pct >= med)
    return {
        "active": active,
        "day": day,
        "prior_date": str(row["Date"]),
        "vol": vol,
        "vol_p40": p40,
        "range_pct": round(range_pct, 4),
        "range_median": round(med, 4),
        "reason": "vol_or_range" if active else "inactive",
    }
