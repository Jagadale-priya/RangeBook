"""Same-session F&O clips on the underlying — small stop, small first target."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import fno_universe

STRONG_P = 0.66
# (stop, first target, runner after T1). Points on the index / % fallback for stocks.
INDEX_CLIPS = {
    # Locked FINAL research — fixed clips (no ATR widen for these three)
    "NIFTY": (30.0, 30.0, 60.0),
    "FINNIFTY": (25.0, 30.0, 60.0),
    "BANKNIFTY": (75.0, 75.0, 150.0),
    "SENSEX": (100.0, 100.0, 200.0),
    "BANKEX": (75.0, 75.0, 150.0),
    "MIDCPNIFTY": (15.0, 18.0, 36.0),
    "NIFTYNXT50": (70.0, 85.0, 170.0),
}
# FINAL index desks use research-locked SL/T1 — ATR must not widen them.
FIXED_FINAL_CLIPS = frozenset({"NIFTY", "BANKNIFTY", "SENSEX"})
# A 25-point NIFTY stop sat inside one median 15m bar (39 points), so most stops were noise.
# 5y of OR breaks: 1x ATR stop with 1x target beat the fixed clip on both the old years and the last 15 months.
ATR_BARS = 14
ATR_STOP_MULT = 1.0
T1_PER_STOP = 1.0
STOCK_SL_FRAC = 0.0025
STOCK_T1_FRAC = 0.0030
STOCK_T2_FRAC = 0.0060


def day_range_box(day_range: Optional[Dict[str, Any]]) -> Optional[Tuple[float, float]]:
    if not day_range:
        return None
    try:
        lo = float(day_range.get("expected_low"))
        hi = float(day_range.get("expected_high"))
    except (TypeError, ValueError):
        return None
    if hi <= lo:
        return None
    return lo, hi


def clamp_levels_to_day_range(
    bearish: bool,
    price: float,
    sl: float,
    t1: float,
    t2: float,
    expected_low: float,
    expected_high: float,
) -> Tuple[Optional[float], Optional[float], Optional[float], bool, str]:
    """Force SL/T1/T2 inside the morning same-day high/low. No fit → no trade."""
    lo, hi = (expected_low, expected_high) if expected_low <= expected_high else (expected_high, expected_low)
    if price < lo:
        lo = price
    if price > hi:
        hi = price
    min_gap = max(abs(price) * 0.00035, (hi - lo) * 0.05, 1.0)

    sl = min(max(sl, lo), hi)
    t1 = min(max(t1, lo), hi)
    t2 = min(max(t2, lo), hi)

    if bearish:
        sl = max(sl, price + min_gap)
        sl = min(sl, hi)
        t1 = min(t1, price - min_gap)
        t1 = max(t1, lo)
        t2 = min(t2, t1)
        t2 = max(t2, lo)
        ok = (
            sl <= hi + 1e-9
            and sl > price
            and t1 < price
            and t1 >= lo - 1e-9
            and (sl - price) >= min_gap * 0.8
            and (price - t1) >= min_gap * 0.8
        )
        note = "SELL levels clamped to morning day range"
    else:
        sl = min(sl, price - min_gap)
        sl = max(sl, lo)
        t1 = max(t1, price + min_gap)
        t1 = min(t1, hi)
        t2 = max(t2, t1)
        t2 = min(t2, hi)
        ok = (
            sl >= lo - 1e-9
            and sl < price
            and t1 > price
            and t1 <= hi + 1e-9
            and (price - sl) >= min_gap * 0.8
            and (t1 - price) >= min_gap * 0.8
        )
        note = "BUY levels clamped to morning day range"

    if not ok:
        return None, None, None, False, "SL/T1/T2 cannot fit inside the morning day range — no same-day F&O ticket."
    return round(sl, 2), round(t1, 2), round(t2, 2), True, note


def bar_atr(bars: Any) -> Optional[float]:
    """Wilder true-range mean over the last completed 15m bars."""
    try:
        if bars is None or len(bars) < ATR_BARS:
            return None
        high = bars["High"].astype(float)
        low = bars["Low"].astype(float)
        tr = high - low
        if "Close" in bars.columns:
            prev_close = bars["Close"].astype(float).shift(1)
            tr = tr.to_frame("hl").join((high - prev_close).abs().rename("hc")).join(
                (low - prev_close).abs().rename("lc")
            ).max(axis=1)
        val = float(tr.tail(ATR_BARS).mean())
        return val if val > 0 else None
    except Exception:
        return None


def clip_points(
    underlying: Optional[str],
    price: float,
    atr: Optional[float] = None,
    cpr_kind: Optional[str] = None,
) -> Tuple[float, float, float, str]:
    """Stop / T1 / optional runner in underlying points. Index stops widen with the
    15m ATR; the fixed clip is the floor. A narrow CPR steps both up. A wide CPR
    keeps the stop and books a smaller first target."""
    key = str(underlying or "").strip().upper()
    if key in INDEX_CLIPS:
        sl_pts, t1_pts, t2_pts = INDEX_CLIPS[key]
        # NIFTY / BANKNIFTY / SENSEX FINAL books are fixed-point desks.
        # ATR widen was listing BN ±140 / SX ±160 and breaking research parity.
        if key not in FIXED_FINAL_CLIPS:
            if atr is not None and atr > 0:
                sl_pts = max(sl_pts, float(round(ATR_STOP_MULT * atr)))
                t1_pts = max(t1_pts, float(round(T1_PER_STOP * sl_pts)))
                t2_pts = max(t2_pts, 2.0 * t1_pts)
            kind = str(cpr_kind or "").upper()
            if kind == "NARROW" and atr is not None and atr > 0:
                sl_pts = max(sl_pts, float(round(1.25 * atr)))
                t1_pts = max(t1_pts, sl_pts)
                t2_pts = max(t2_pts, 2.0 * t1_pts)
            elif kind == "WIDE":
                t1_pts = max(15.0, float(round(sl_pts * 0.75)))
                t2_pts = max(t2_pts, 2.0 * t1_pts)
        return sl_pts, t1_pts, t2_pts, key
    px = abs(float(price)) or 1.0
    sl_pts = max(round(px * STOCK_SL_FRAC, 2), 0.5)
    t1_pts = max(round(px * STOCK_T1_FRAC, 2), round(sl_pts * 1.2, 2))
    t2_pts = max(round(px * STOCK_T2_FRAC, 2), round(t1_pts * 2.0, 2))
    if atr is not None and atr > 0 and fno_universe.contains(key):
        sl_pts = max(sl_pts, round(ATR_STOP_MULT * atr, 2))
        t1_pts = max(t1_pts, round(T1_PER_STOP * sl_pts, 2))
        t2_pts = max(t2_pts, round(2.0 * t1_pts, 2))
    return sl_pts, t1_pts, t2_pts, key or "STOCK"


def is_strong_signal(decision: str, live_context: Optional[Dict[str, Any]] = None) -> bool:
    """Runner only if the clip model says T1 is likely and the path can continue."""
    if "BUY" not in str(decision) and "SELL" not in str(decision):
        return False
    head = (live_context or {}).get("fno_model") or {}
    if "continue_ok" in head:
        return bool(head["continue_ok"])
    try:
        p_t1 = float(head["p_t1"]) if head.get("p_t1") is not None else None
    except (TypeError, ValueError):
        p_t1 = None
    if p_t1 is not None and p_t1 >= STRONG_P:
        return True
    try:
        p_up = float(head.get("p_up"))
    except (TypeError, ValueError):
        return False
    if "SELL" in str(decision):
        return p_up <= (1.0 - STRONG_P)
    return p_up >= STRONG_P


def _apply_clip(bearish: bool, price: float, sl_pts: float, t1_pts: float, t2_pts: Optional[float]):
    if bearish:
        sl = price + sl_pts
        t1 = price - t1_pts
        t2 = None if t2_pts is None else price - t2_pts
    else:
        sl = price - sl_pts
        t1 = price + t1_pts
        t2 = None if t2_pts is None else price + t2_pts
    return (
        round(sl, 2),
        round(t1, 2),
        None if t2 is None else round(t2, 2),
    )


def compute_fno_trade_risk(
    bearish: bool,
    current_price: float,
    atr_val: float,
    *,
    setup_type: str = "full_stack",
    instrument: Optional[Dict[str, Any]] = None,
    live_quote: Optional[Dict[str, Any]] = None,
    live_context: Optional[Dict[str, Any]] = None,
    structural: Optional[Dict[str, Any]] = None,
    swing_risk: Optional[Dict[str, Any]] = None,
    decision: str = "HOLD",
    day_range: Optional[Dict[str, Any]] = None,
    underlying: Optional[str] = None,
) -> Dict[str, Any]:
    """Small same-session SL/T1. T2 is a runner only on a strong dedicated-model print."""
    del atr_val, live_quote, structural, setup_type
    if decision == "HOLD":
        return {
            "fno_trade": {
                "stop_loss": None,
                "target_1": None,
                "target_2": None,
                "horizon": "none",
                "levels_fit": False,
                "note": "No F&O levels while decision is HOLD.",
            },
            "swing_reference_only": _swing_ref(swing_risk),
        }

    inst_type = (instrument or {}).get("instrument_type") or "INDEX_FUT"
    is_option = "OPTION" in str(inst_type).upper()
    name = underlying or (instrument or {}).get("underlying")
    head = (live_context or {}).get("fno_model") or {}
    cpr_kind = None
    for item in ((live_context or {}).get("indications") or {}).get("items") or []:
        if item.get("key") == "cpr" and item.get("kind"):
            cpr_kind = str(item.get("kind"))
            break
    sl_pts, t1_pts, t2_pts, clip_name = clip_points(
        name, current_price, atr=head.get("clip_atr"), cpr_kind=cpr_kind
    )
    strong = is_strong_signal(decision, live_context)
    runner = t2_pts if strong else None
    sl, t1, t2 = _apply_clip(bearish, current_price, sl_pts, t1_pts, runner)

    kind = str(cpr_kind or "").upper()
    if kind == "NARROW":
        sl_reason = f"{clip_name} stop {sl_pts:g} points — narrow CPR, stop and target stepped up with the 15m range"
        t1_reason = f"Book first at {t1_pts:g} points — same step-up as the stop"
    elif kind == "WIDE":
        sl_reason = f"{clip_name} stop {sl_pts:g} points (wider of the fixed clip and 15m true range)"
        t1_reason = f"Book first at {t1_pts:g} points — wide CPR, smaller target than the stop"
    else:
        sl_reason = f"{clip_name} stop {sl_pts:g} points (wider of the fixed clip and 15m true range)"
        t1_reason = f"Book first at {t1_pts:g} points"
    t2_reason = (
        f"Runner {t2_pts:g} points — only after T1, strong signal"
        if strong
        else "No runner — book T1 (signal is not strong)"
    )

    box = day_range_box(day_range)
    levels_fit = True
    opt_note = ""
    if is_option:
        opt_note = " Options: theta decay — prefer exiting at T1; SL is on underlying."

    return {
        "fno_trade": {
            "stop_loss": sl,
            "target_1": t1,
            "target_2": t2,
            "horizon": "same_session_short",
            "levels_fit": levels_fit,
            "day_range_low": box[0] if box else None,
            "day_range_high": box[1] if box else None,
            "setup_type": "safe_clip",
            "instrument_type": inst_type,
            "clip_name": clip_name,
            "strong_signal": strong,
            "sl_points": sl_pts,
            "t1_points": t1_pts,
            "t2_points": runner,
            "sl_reason": sl_reason,
            "t1_reason": t1_reason,
            "t2_reason": t2_reason,
            "runner_policy": "T2 is informational; the recorded ticket closes at T1.",
            "note": (
                "Same-day F&O clip — small stop and small first target. "
                "T2 is informational on a strong model print; the ticket closes at T1."
                + opt_note
            ),
        },
        "swing_reference_only": _swing_ref(swing_risk),
    }


def _swing_ref(swing_risk: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    rm = swing_risk or {}
    return {
        "stop_loss": rm.get("stop_loss"),
        "target_1": rm.get("target_1"),
        "target_2": rm.get("target_2"),
        "note": "Daily swing levels — reference only; too wide for typical F&O.",
    }


def _bias_from_trade(trade: Dict[str, Any]) -> str:
    """LONG when stop is below the target, SHORT when stop is above it."""
    sl = trade.get("stop_loss")
    t1 = trade.get("target_1")
    if sl is None or t1 is None:
        return "FLAT"
    try:
        stop = float(sl)
        tgt = float(t1)
    except (TypeError, ValueError):
        return "FLAT"
    if stop < tgt:
        return "LONG"
    if stop > tgt:
        return "SHORT"
    return "FLAT"


def fno_risk_for_api(risk_block: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten for API risk_management on F&O responses."""
    trade = risk_block.get("fno_trade") or {}
    return {
        "bias": _bias_from_trade(trade),
        "stop_loss": trade.get("stop_loss"),
        "target_1": trade.get("target_1"),
        "target_2": trade.get("target_2"),
        "fno_trade": trade,
        "swing_reference_only": risk_block.get("swing_reference_only"),
        "position_advice": trade.get("note"),
        "risk_horizon": trade.get("horizon"),
    }
