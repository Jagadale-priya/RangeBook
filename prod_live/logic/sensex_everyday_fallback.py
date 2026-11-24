"""Sensex OR fallback — break-only with min break fraction (locked bf>=0.20)."""
from __future__ import annotations

from typing import Any, Dict, Optional

MIN_BREAK_FRAC = 0.20


def or_fallback_call(bars: Any, *, asof: Any = None, price: Any = None) -> Optional[Dict[str, Any]]:
    try:
        import pandas as pd
        import fno_session_rules as fsrules
    except Exception:
        return None
    if bars is None or len(bars) < 2:
        return None
    work = bars
    if not isinstance(work.index, pd.DatetimeIndex):
        return None
    ts = pd.Timestamp(asof) if asof is not None else work.index[-1]
    if ts.tzinfo is None and work.index.tz is not None:
        ts = ts.tz_localize(work.index.tz)
    elif work.index.tz is not None:
        ts = ts.tz_convert(work.index.tz)
    day = fsrules.session_date(ts)
    if day is None:
        return None
    day_mask = [fsrules.session_date(t) == day for t in work.index]
    sess = work.loc[day_mask]
    if len(sess) < 2:
        return None
    or_hi = float(sess["High"].astype(float).iloc[0])
    or_lo = float(sess["Low"].astype(float).iloc[0])
    width = or_hi - or_lo
    if width <= 0:
        return None
    entry_pos = min(1, len(sess) - 1)
    for i, t in enumerate(sess.index):
        hm = f"{pd.Timestamp(t).hour:02d}:{pd.Timestamp(t).minute:02d}"
        if hm in ("09:45", "09:30", "10:00"):
            entry_pos = i
            if hm == "09:45":
                break
    entry_ts = sess.index[entry_pos]
    close = float(sess["Close"].astype(float).iloc[entry_pos])
    if close > or_hi:
        side = "BUY"
        bf = (close - or_hi) / width
    elif close < or_lo:
        side = "SELL"
        bf = (or_lo - close) / width
    else:
        return None
    if bf < MIN_BREAK_FRAC:
        return None
    hm = f"{pd.Timestamp(entry_ts).hour:02d}:{pd.Timestamp(entry_ts).minute:02d}"
    return {
        "decision": side,
        "side": side,
        "entry": round(close, 2),
        "p_t1": 0.55,
        "track": "or_fallback",
        "hm": hm,
        "source": "sensex_everyday_fallback",
        "fb_kind": "break",
        "break_frac": round(bf, 4),
        "accuracy_label": f"OR fallback · break frac>={MIN_BREAK_FRAC:.0%}",
        "or_hi": round(or_hi, 2),
        "or_lo": round(or_lo, 2),
    }
