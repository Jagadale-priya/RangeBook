"""NIFTY morning strong BUY — 15m thrust → 5m limit fill at OR+5.

Locked research (holds 100% on 1y / 3y / 5y):
  L5_u70_b80_t0_11:30_fg_fb_mb18
  1y 11@100% · 3y 26@100% · 5y 41@100%

Honest path: signal on 15m, fill only when 5m revisits OR+5.

Locked rule:
  - Signal 09:45–11:30: close>OR · green · uplift from open ≥70 ·
    break prior 2 highs · body ≥80% of bar range · forbid down-break-first
  - Fill within 18×5m bars (by 13:00): 5m low ≤ OR+5 · close>OR · green 5m
  - Entry = OR+5 · ±30 · Cap 1/day · confident (not proven_100)
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

TRACK = "confident"
SOURCE = "nifty_morning_strong_thrust_confident"
ACCURACY_LABEL = "Priority · High accuracy · morning strong OR+5 (100% 1y/3y/5y)"
ACCURACY_TAG_CODE = "most_accurate"
EXPECTED_HIT_PCT = 100.0
SL_PTS = 30.0
T1_PTS = 30.0

SIG_HM_MIN = "09:45"
SIG_HM_MAX = "11:30"
FILL_HM_MAX = "13:00"
MIN_UPLIFT = 70.0
BREAK_PRIOR_HIGHS = 2
MIN_BODY_FRAC = 0.80
LIMIT_OFFSET = 5.0
REQUIRE_FILL_GREEN = True
FORBID_DOWN_BREAK_FIRST = True
MAX_FILL_BARS = 18


def enabled() -> bool:
    v = str(os.environ.get("ENABLE_NIFTY_MORNING_STRONG_THRUST", "1")).strip().lower()
    return v not in ("0", "false", "no", "off", "")


def is_morning_strong_payload(dual_call: Any) -> bool:
    return isinstance(dual_call, dict) and bool(dual_call.get("morning_strong_thrust"))


def dual_blocks(dual_call: Any, *, suppress_dual_list: bool) -> bool:
    """True only when a dual call would actually list on Calls."""
    if is_morning_strong_payload(dual_call):
        return False
    if isinstance(dual_call, dict) and dual_call.get("afternoon_thrust"):
        return True  # afternoon already owns the dual_call slot
    if not isinstance(dual_call, dict):
        return False
    if dual_call.get("decision") not in ("BUY", "SELL"):
        return False
    if suppress_dual_list:
        return False
    return True


def in_fill_window(asof: Any = None) -> bool:
    hm = _ist_hm(asof) if asof is not None else None
    if hm is None:
        try:
            import market_symbols

            hm = _ist_hm(market_symbols.ist_now())
        except Exception:
            return False
    return bool(hm and "09:45" <= hm <= FILL_HM_MAX)


def stamp_readings(readings: Any, dual_call: Optional[Dict[str, Any]] = None) -> Any:
    if not isinstance(readings, dict):
        return readings
    payload = dual_call if isinstance(dual_call, dict) else {}
    readings["dual_track"] = False
    readings["morning_strong_thrust"] = True
    readings["afternoon_thrust"] = False
    readings["track"] = TRACK
    readings["source"] = SOURCE
    readings["accuracy_label"] = payload.get("accuracy_label") or ACCURACY_LABEL
    readings["accuracy_tags"] = list(
        payload.get("accuracy_tags")
        or [
            {
                "code": TRACK,
                "label": ACCURACY_LABEL,
                "expected_hit_pct": EXPECTED_HIT_PCT,
                "tone": "research",
                "priority": 72,
            }
        ]
    )
    readings["accuracy_tag_code"] = ACCURACY_TAG_CODE
    readings["proven_100"] = False
    readings["history_eligible"] = True
    readings["priority"] = 72
    readings["live_confluence"] = False
    readings["listable"] = True
    if payload.get("p_t1") is not None:
        readings["p_t1"] = payload.get("p_t1")
    if payload.get("uplift_from_open") is not None:
        readings["uplift_from_open"] = payload.get("uplift_from_open")
    if payload.get("limit_entry") is not None:
        readings["limit_entry"] = payload.get("limit_entry")
    return readings


def as_suggestion(dual_call: Dict[str, Any]) -> Dict[str, Any]:
    sug = dict(dual_call)
    sug["dual_track"] = False
    sug["morning_strong_thrust"] = True
    sug["track"] = TRACK
    sug["source"] = SOURCE
    sug["listable"] = True
    sug["suggestion_tag"] = "Confident · morning strong OR+5 (100% 1y/3y/5y)"
    sug["tag_tone"] = "champion"
    sug["basis"] = (
        "NIFTY morning strong BUY — 15m thrust (OR+ green + prior2 + uplift≥70 + body≥80%), "
        "fill on 5m revisit of OR+5 (locked L5_u70_b80)."
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


def _session_slice(work: Any, ts: Any):
    import fno_session_rules as fsrules

    day = fsrules.session_date(ts)
    if day is None:
        return None
    day_mask = [fsrules.session_date(t) == day for t in work.index]
    return work.loc[day_mask]


def _find_signal(sess: Any) -> Optional[Tuple[Any, Dict[str, float]]]:
    """First 15m thrust signal bar in SIG window, or None."""
    if sess is None or len(sess) < 3:
        return None
    or_hi = float(sess["High"].astype(float).iloc[0])
    or_lo = float(sess["Low"].astype(float).iloc[0])
    day_open = float(sess["Open"].astype(float).iloc[0])
    if FORBID_DOWN_BREAK_FIRST:
        first_up = first_dn = None
        closes = sess["Close"].astype(float)
        for i in range(len(sess)):
            c = float(closes.iloc[i])
            if first_up is None and c > or_hi:
                first_up = i
            if first_dn is None and c < or_lo:
                first_dn = i
        if first_up is not None and first_dn is not None and first_dn < first_up:
            return None
    # Locked research: take the FIRST loose thrust bar in the window, then
    # require locked gates on that same bar (do not hunt a later cleaner bar).
    loose_uplift = 40.0
    loose_body = 0.50
    for i, ts in enumerate(sess.index):
        hm = _ist_hm(ts)
        if not hm or hm < SIG_HM_MIN or hm > SIG_HM_MAX:
            continue
        if i < BREAK_PRIOR_HIGHS:
            continue
        row = sess.iloc[i]
        close = float(row["Close"])
        opn = float(row["Open"])
        high = float(row["High"])
        low = float(row["Low"])
        if close <= or_hi or close <= opn:
            continue
        uplift = close - day_open
        if uplift < loose_uplift:
            continue
        prior_hi = max(
            float(sess["High"].astype(float).iloc[j])
            for j in range(i - BREAK_PRIOR_HIGHS, i)
        )
        if close <= prior_hi:
            continue
        rng = max(high - low, 1e-9)
        body = abs(close - opn) / rng
        if body < loose_body:
            continue
        # First loose thrust found — apply locked L5_u70_b80 on THIS bar only.
        if uplift < MIN_UPLIFT or body < MIN_BODY_FRAC:
            return None
        return ts, {
            "or_hi": or_hi,
            "or_lo": or_lo,
            "day_open": day_open,
            "uplift": uplift,
            "sig_close": close,
        }
    return None


def _fill_after_signal(
    *,
    sig_ts: Any,
    or_hi: float,
    bars_5m: Any,
    asof: Any,
    price: Any,
) -> Optional[Tuple[Any, float, str]]:
    """Return (fill_ts, entry, fill_hm) when limit OR+5 is touched after signal."""
    import pandas as pd

    lim = or_hi + LIMIT_OFFSET
    hm_now = _ist_hm(asof)
    if hm_now and hm_now > FILL_HM_MAX:
        return None

    after = None
    if bars_5m is not None and len(bars_5m) and isinstance(
        getattr(bars_5m, "index", None), pd.DatetimeIndex
    ):
        after = bars_5m[bars_5m.index > sig_ts]
        # stay on signal session
        sess5 = _session_slice(bars_5m, sig_ts)
        if sess5 is not None and len(sess5):
            after = sess5[sess5.index > sig_ts]

    if after is not None and len(after):
        n_bars = 0
        for thr, row in after.iterrows():
            n_bars += 1
            if n_bars > MAX_FILL_BARS:
                break
            hm2 = _ist_hm(thr)
            if not hm2 or hm2 > FILL_HM_MAX:
                break
            if asof is not None:
                try:
                    if pd.Timestamp(thr) > pd.Timestamp(asof):
                        break
                except Exception:
                    pass
            low = float(row["Low"])
            close = float(row["Close"])
            opn = float(row["Open"])
            if low > lim:
                continue
            if close <= or_hi:
                continue
            if REQUIRE_FILL_GREEN and close <= opn:
                continue
            return thr, lim, hm2

    # Live touch: signal armed, price back at/under limit
    try:
        px = float(price) if price is not None else None
    except (TypeError, ValueError):
        px = None
    if px is not None and px <= lim and px > or_hi and hm_now and hm_now <= FILL_HM_MAX:
        return asof, lim, hm_now or "live"
    return None


def evaluate(
    bars_15m: Any,
    bars_5m: Any = None,
    *,
    asof: Any = None,
    price: Any = None,
) -> Optional[Dict[str, Any]]:
    """Return BUY payload when morning strong limit fill is active at asof."""
    if not enabled():
        return None
    try:
        import pandas as pd
        import fno_session_rules as fsrules
    except Exception:
        return None
    if bars_15m is None or len(bars_15m) < 4:
        return None
    work = bars_15m
    if not isinstance(getattr(work, "index", None), pd.DatetimeIndex):
        return None
    ts = pd.Timestamp(asof) if asof is not None else work.index[-1]
    hm = _ist_hm(ts)
    if not hm or hm < SIG_HM_MIN or hm > FILL_HM_MAX:
        return None
    sess = _session_slice(work, ts)
    if sess is None or len(sess) < 4:
        return None
    found = _find_signal(sess)
    if not found:
        return None
    sig_ts, meta = found
    fill = _fill_after_signal(
        sig_ts=sig_ts,
        or_hi=float(meta["or_hi"]),
        bars_5m=bars_5m,
        asof=ts,
        price=price,
    )
    if not fill:
        return None
    fill_ts, entry, fill_hm = fill
    stop = round(entry - SL_PTS, 2)
    target = round(entry + T1_PTS, 2)
    sig_hm = _ist_hm(sig_ts) or ""
    return {
        "decision": "BUY",
        "side": "BUY",
        "entry": round(entry, 2),
        "stop_loss": stop,
        "target_1": target,
        "t1_pts": T1_PTS,
        "sl_pts": SL_PTS,
        "p_t1": 0.72,
        "track": TRACK,
        "source": SOURCE,
        "hm": fill_hm,
        "sig_hm": sig_hm,
        "list_priority": 2,
        "dual_track": False,
        "morning_strong_thrust": True,
        "afternoon_thrust": False,
        "limit_entry": round(entry, 2),
        "limit_offset": LIMIT_OFFSET,
        "accuracy_label": ACCURACY_LABEL,
        "accuracy_tags": [
            {
                "code": TRACK,
                "label": ACCURACY_LABEL,
                "expected_hit_pct": EXPECTED_HIT_PCT,
                "tone": "research",
                "priority": 72,
            }
        ],
        "or_hi": round(float(meta["or_hi"]), 2),
        "or_lo": round(float(meta["or_lo"]), 2),
        "uplift_from_open": round(float(meta["uplift"]), 1),
        "message": (
            f"BUY morning strong · sig {sig_hm} · fill OR+{LIMIT_OFFSET:.0f} @ {fill_hm} · "
            f"+{meta['uplift']:.0f} open · ±{SL_PTS:.0f}"
        ),
    }
