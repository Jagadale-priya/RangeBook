"""NIFTY afternoon BUY thrust — tagged as confident (champion), never proven_100.

Research (60 sessions → 2026-11-19): thrust2_up30 · 13@92.31% · fires Nov19 14:00.

Isolated lane:
  - Does NOT change proven_100 gates / 13:00 cut
  - Does NOT change morning first-break champion
  - Sensex untouched
  - Only lists when dual proven/champion is silent that refresh

Rule (locked research):
  - Time 13:15–14:45
  - Close above OR high
  - Green bar
  - Close breaks prior 2 bar highs
  - Close ≥ 13:00 open + 30 pts
  - Cap 1 / day · brackets ±30
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

# Confident / high-accuracy family (not proven_100)
TRACK = "confident"
SOURCE = "nifty_afternoon_thrust_confident"
ACCURACY_LABEL = "Priority · High accuracy · afternoon thrust (~92%)"
ACCURACY_TAG_CODE = "most_accurate"
SL_PTS = 30.0
T1_PTS = 30.0
HM_MIN = "13:15"
HM_MAX = "14:45"
MIN_UPLIFT_FROM_13 = 30.0
BREAK_PRIOR_HIGHS = 2


def enabled() -> bool:
    v = str(os.environ.get("ENABLE_NIFTY_AFTERNOON_THRUST", "1")).strip().lower()
    return v not in ("0", "false", "no", "off", "")


def is_thrust_payload(dual_call: Any) -> bool:
    return isinstance(dual_call, dict) and bool(dual_call.get("afternoon_thrust"))


def dual_blocks_thrust(dual_call: Any, *, suppress_dual_list: bool) -> bool:
    """True only when a dual call would actually list on Calls.

    SUPPRESS_DUAL_LIST keeps proven/champion for annotate — that must NOT
    block the confident afternoon lane (research thrust2_up30).
    Morning strong thrust already listing also blocks overwrite.
    """
    if is_thrust_payload(dual_call):
        return False
    if isinstance(dual_call, dict) and dual_call.get("morning_strong_thrust"):
        return True
    if not isinstance(dual_call, dict):
        return False
    if dual_call.get("decision") not in ("BUY", "SELL"):
        return False
    if suppress_dual_list:
        return False
    return True


def in_thrust_window(asof: Any = None) -> bool:
    hm = _ist_hm(asof) if asof is not None else None
    if hm is None:
        try:
            import market_symbols

            hm = _ist_hm(market_symbols.ist_now())
        except Exception:
            return False
    return bool(hm and HM_MIN <= hm <= HM_MAX)


def stamp_readings(readings: Any, dual_call: Optional[Dict[str, Any]] = None) -> Any:
    """Stamp Calls-board readings for the confident afternoon lane."""
    if not isinstance(readings, dict):
        return readings
    payload = dual_call if isinstance(dual_call, dict) else {}
    readings["dual_track"] = False
    readings["afternoon_thrust"] = True
    readings["track"] = TRACK
    readings["source"] = SOURCE
    readings["accuracy_label"] = payload.get("accuracy_label") or ACCURACY_LABEL
    readings["accuracy_tags"] = list(
        payload.get("accuracy_tags")
        or [
            {
                "code": TRACK,
                "label": ACCURACY_LABEL,
                "expected_hit_pct": 92.3,
                "tone": "research",
                "priority": 70,
            }
        ]
    )
    readings["accuracy_tag_code"] = ACCURACY_TAG_CODE
    readings["proven_100"] = False
    readings["history_eligible"] = True
    readings["priority"] = 70
    readings["live_confluence"] = False
    readings["listable"] = True
    if payload.get("p_t1") is not None:
        readings["p_t1"] = payload.get("p_t1")
    if payload.get("uplift_from_13") is not None:
        readings["uplift_from_13"] = payload.get("uplift_from_13")
    return readings


def as_suggestion(dual_call: Dict[str, Any]) -> Dict[str, Any]:
    """UI suggestion card for a live afternoon thrust list."""
    sug = dict(dual_call)
    sug["dual_track"] = False
    sug["afternoon_thrust"] = True
    sug["track"] = TRACK
    sug["source"] = SOURCE
    sug["listable"] = True
    sug["suggestion_tag"] = "Confident · afternoon thrust (~92%)"
    sug["tag_tone"] = "champion"
    sug["basis"] = (
        "NIFTY post-13:00 BUY thrust — close>OR, green bar, "
        "break prior 2 highs, +30 from 13:00 open."
    )
    sug["accuracy_label"] = dual_call.get("accuracy_label") or ACCURACY_LABEL
    return sug


def _ist_hm(ts: Any) -> Optional[str]:
    try:
        import pandas as pd
        import fno_session_rules as fsrules

        dt = fsrules.as_ist(ts)
        if dt is None:
            dt = pd.Timestamp(ts)
            if dt.tzinfo is None:
                dt = dt.tz_localize("Asia/Kolkata")
            else:
                dt = dt.tz_convert("Asia/Kolkata")
        return f"{int(dt.hour):02d}:{int(dt.minute):02d}"
    except Exception:
        return None


def evaluate(
    bars: Any,
    *,
    asof: Any = None,
    price: Any = None,
) -> Optional[Dict[str, Any]]:
    """Return BUY call_payload when afternoon thrust rule fires at asof, else None."""
    if not enabled():
        return None
    try:
        import pandas as pd
        import fno_session_rules as fsrules
    except Exception:
        return None
    if bars is None or len(bars) < 8:
        return None
    work = bars
    if not isinstance(getattr(work, "index", None), pd.DatetimeIndex):
        return None
    ts = pd.Timestamp(asof) if asof is not None else work.index[-1]
    hm = _ist_hm(ts)
    if not hm or hm < HM_MIN or hm > HM_MAX:
        return None
    day = fsrules.session_date(ts)
    if day is None:
        return None
    day_mask = [fsrules.session_date(t) == day for t in work.index]
    sess = work.loc[day_mask]
    if len(sess) < 8:
        return None
    # align asof bar
    if ts.tzinfo is None and sess.index.tz is not None:
        ts = ts.tz_localize(sess.index.tz)
    elif sess.index.tz is not None:
        ts = ts.tz_convert(sess.index.tz)
    loc = sess.index.searchsorted(ts, side="right") - 1
    if loc < BREAK_PRIOR_HIGHS:
        return None
    or_hi = float(sess["High"].astype(float).iloc[0])
    or_lo = float(sess["Low"].astype(float).iloc[0])
    # 13:00 open
    open13 = None
    for t in sess.index:
        if _ist_hm(t) == "13:00":
            open13 = float(sess.loc[t, "Open"])
            break
    if open13 is None:
        return None
    row = sess.iloc[loc]
    close = float(row["Close"])
    high = float(row["High"])
    low = float(row["Low"])
    opn = float(row["Open"])
    if close <= or_hi:
        return None
    if close <= opn:
        return None
    if (close - open13) < MIN_UPLIFT_FROM_13:
        return None
    prior_highs = [float(sess["High"].astype(float).iloc[j]) for j in range(loc - BREAK_PRIOR_HIGHS, loc)]
    if close <= max(prior_highs):
        return None
    try:
        entry = float(price) if price is not None else close
    except (TypeError, ValueError):
        entry = close
    stop = round(entry - SL_PTS, 2)
    target = round(entry + T1_PTS, 2)
    return {
        "decision": "BUY",
        "side": "BUY",
        "entry": round(entry, 2),
        "stop_loss": stop,
        "target_1": target,
        "t1_pts": T1_PTS,
        "sl_pts": SL_PTS,
        "p_t1": 0.70,
        "track": TRACK,
        "source": SOURCE,
        "hm": hm,
        "list_priority": 2,
        "dual_track": False,
        "afternoon_thrust": True,
        "accuracy_label": ACCURACY_LABEL,
        "accuracy_tags": [
            {
                "code": TRACK,
                "label": ACCURACY_LABEL,
                "expected_hit_pct": 92.3,
                "tone": "research",
                "priority": 70,
            }
        ],
        "or_hi": round(or_hi, 2),
        "or_lo": round(or_lo, 2),
        "uplift_from_13": round(close - open13, 1),
        "message": (
            f"BUY afternoon thrust · close>OR · +{close - open13:.0f} from 13:00 · ±{SL_PTS:.0f}"
        ),
    }
