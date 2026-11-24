"""F&O trade book: short / mid / long from candles + classic formulas.

The cash ML is built to sit in HOLD unless both heads agree. Futures and options
cannot wait for that. This layer votes independently:

  SHORT  same session / next open   — session tape, 5m micro, last candles
  MID    2–7 sessions / weekly      — RSI, MACD, stoch, EMA, S/R
  LONG   positional / next expiry   — SMA50/200, ADX, trend strength

The live ticket is the SHORT book (same session). Mid/long stay as context
and must not set SL/T1/T2.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Same-session ticket must clear this. Mild leans are disabled — they over-traded.
SHORT_TICKET_PRIMARY = 14.0
SHORT_TICKET_OTHER = 16.0

HORIZON_META = {
    "short": {
        "label": "Short",
        "hold": "same session / next open",
        "setup_type": "horizon_short",
    },
    "mid": {
        "label": "Mid",
        "hold": "2–7 sessions / this week",
        "setup_type": "horizon_mid",
    },
    "long": {
        "label": "Long",
        "hold": "positional / next expiry",
        "setup_type": "horizon_long",
    },
}


def _f(ind: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        v = ind.get(key, default)
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _side(score: float, thresh: float) -> str:
    if score >= thresh:
        return "BUY"
    if score <= -thresh:
        return "SELL"
    return "HOLD"


def candle_score(candlestick: Optional[Dict[str, Any]]) -> Tuple[float, List[str]]:
    """Signed score from detected patterns. Positive = bullish."""
    cs = candlestick or {}
    score = float(cs.get("score_delta") or 0)
    reasons: List[str] = []
    bias = (cs.get("bias") or "NEUTRAL").upper()
    patterns = [str(p) for p in (cs.get("patterns") or [])]
    if bias == "BULLISH":
        score = max(score, 4.0)
        reasons.append("Candle bias BULLISH")
    elif bias == "BEARISH":
        score = min(score, -4.0)
        reasons.append("Candle bias BEARISH")
    for p in patterns[:4]:
        reasons.append(f"Pattern: {p}")
        low = p.lower()
        if any(k in low for k in (
            "engulfing", "morning star", "three white", "hammer", "piercing", "marubozu",
            "dragonfly", "inverted hammer", "kicker", "belt hold", "three inside up",
            "three outside up", "rising three", "tweezer bottom", "opening range",
            "rising window", "upside tasuki", "three line strike", "abandoned baby (bullish)",
            "separating lines", "stick sandwich", "harami cross (bullish)", "matching low",
            "unique three river", "three stars in the south",
        )):
            if "bear" not in low and "dark" not in low and "shooting" not in low and "hanging" not in low:
                score += 3
        if any(k in low for k in (
            "evening star", "dark cloud", "shooting star", "three black", "gravestone",
            "hanging man", "three inside down", "three outside down", "falling three",
            "tweezer top", "falling window", "downside tasuki", "advance block",
            "abandoned baby (bearish)", "bearish three line strike", "bearish separating",
            "harami cross (bearish)", "on-neck", "in-neck", "thrusting", "homing pigeon",
            "two crows",
        )):
            score -= 3
        if "bearish engulfing" in low:
            score -= 4
        if "bullish engulfing" in low:
            score += 4
    return max(-25.0, min(25.0, score)), reasons


def formula_mid_score(ind: Dict[str, Any], structural: Optional[Dict[str, Any]] = None) -> Tuple[float, List[str]]:
    """Daily oscillator / swing formulas (2–7 day F&O)."""
    score = 0.0
    reasons: List[str] = []
    rsi = _f(ind, "rsi_14", 50)
    if rsi <= 35:
        score += 8
        reasons.append(f"RSI {rsi:.0f} oversold")
    elif rsi <= 42:
        score += 4
        reasons.append(f"RSI {rsi:.0f} weak — bounce zone")
    elif rsi >= 65:
        score -= 8
        reasons.append(f"RSI {rsi:.0f} overbought")
    elif rsi >= 58:
        score -= 4
        reasons.append(f"RSI {rsi:.0f} stretched up")

    macd = _f(ind, "macd_hist", 0)
    if macd > 0:
        score += 5
        reasons.append("MACD histogram positive")
    elif macd < 0:
        score -= 5
        reasons.append("MACD histogram negative")
    if int(_f(ind, "macd_cross", 0)) == 1:
        score += 3
        reasons.append("MACD bullish cross")
    elif int(_f(ind, "macd_cross", 0)) == -1:
        score -= 3
        reasons.append("MACD bearish cross")

    if int(_f(ind, "ema_cross", 0)) == 1:
        score += 4
        reasons.append("EMA stack bullish")
    elif int(_f(ind, "ema_cross", 0)) == -1:
        score -= 4
        reasons.append("EMA stack bearish")

    stoch = _f(ind, "stoch_k", 50)
    if stoch <= 25:
        score += 4
        reasons.append(f"Stoch %K {stoch:.0f} oversold")
    elif stoch >= 75:
        score -= 4
        reasons.append(f"Stoch %K {stoch:.0f} overbought")

    vs20 = _f(ind, "price_vs_sma20", 0)
    if vs20 > 1.0:
        score += 3
        reasons.append("Price above SMA20")
    elif vs20 < -1.0:
        score -= 3
        reasons.append("Price below SMA20")

    adx = _f(ind, "adx", 0)
    if adx >= 22:
        score *= 1.15
        reasons.append(f"ADX {adx:.0f} — trend is real")
    elif 0 < adx < 16:
        score *= 0.75
        reasons.append(f"ADX {adx:.0f} — choppy, fade conviction")

    sr = (structural or {}).get("support_resistance") or {}
    near_s = sr.get("nearest_support")
    near_r = sr.get("nearest_resistance")
    px = _f(ind, "close", 0) or None
    if px and near_s:
        dist_s = (px - float(near_s)) / px * 100
        if 0 <= dist_s <= 0.8:
            score += 4
            reasons.append("Holding near support")
    if px and near_r:
        dist_r = (float(near_r) - px) / px * 100
        if 0 <= dist_r <= 0.8:
            score -= 4
            reasons.append("Pressed into resistance")

    return max(-30.0, min(30.0, score)), reasons


def formula_long_score(ind: Dict[str, Any]) -> Tuple[float, List[str]]:
    """Positional / next-expiry trend formulas."""
    score = 0.0
    reasons: List[str] = []
    vs50 = _f(ind, "price_vs_sma50", 0)
    vs200 = _f(ind, "price_vs_sma200", 0)
    if vs50 > 0:
        score += 6
        reasons.append("Price above SMA50")
    elif vs50 < 0:
        score -= 6
        reasons.append("Price below SMA50")
    if vs200 > 0:
        score += 7
        reasons.append("Price above SMA200 — primary uptrend")
    elif vs200 < 0:
        score -= 7
        reasons.append("Price below SMA200 — primary downtrend")

    sma50 = _f(ind, "sma_50", 0)
    sma200 = _f(ind, "sma_200", 0)
    if sma50 and sma200:
        if sma50 > sma200:
            score += 5
            reasons.append("SMA50 > SMA200 (golden alignment)")
        else:
            score -= 5
            reasons.append("SMA50 < SMA200 (death alignment)")

    trend = _f(ind, "trend_strength", 0)
    if trend > 0.4:
        score += 4
        reasons.append("Trend strength elevated")
    elif trend < -0.4:
        score -= 4
        reasons.append("Trend strength negative")

    adx = _f(ind, "adx", 0)
    if adx >= 25:
        score *= 1.1
        reasons.append(f"ADX {adx:.0f} supports a positional hold")

    return max(-30.0, min(30.0, score)), reasons


def short_score(
    candlestick: Optional[Dict[str, Any]],
    live_context: Optional[Dict[str, Any]],
    adj_tech: float,
) -> Tuple[float, List[str]]:
    """Same-session book: 15m candles decide; 5m only confirms or vetoes."""
    live = live_context or {}
    session = live.get("session") or {}
    micro = live.get("microstructure") or {}
    cs15 = (micro.get("micro_candlestick_15m") or {}) if micro else {}
    if cs15.get("patterns") or cs15.get("bias"):
        score, reasons = candle_score(cs15)
        reasons = ["15m " + r for r in reasons]
    else:
        score, reasons = candle_score(candlestick)
        reasons = ["daily/fallback " + r for r in reasons]

    if session.get("available"):
        chg = float(session.get("change_from_open_pct") or 0)
        pos = float(session.get("day_range_position") or 0.5)
        sess_bias = session.get("session_bias") or "NEUTRAL"
        score += max(-10, min(10, chg * 5))
        if pos >= 0.72:
            score += 3
        elif pos <= 0.28:
            score -= 3
        reasons.append(f"Session {chg:+.2f}% · range {pos:.0%} · {sess_bias}")

    if micro.get("available"):
        ms = float(micro.get("micro_score") or 50)
        score += (ms - 50) * 0.28
        reasons.append(
            f"{micro.get('decision_interval') or '15m'} score {ms:.0f}/100 · {micro.get('micro_bias')}"
        )
        orb = micro.get("opening_range") or {}
        if orb.get("available") and orb.get("broken"):
            if orb.get("bias") == "BULLISH":
                score += 4
                reasons.append(f"15m opening-range break up ({orb.get('or_high')})")
            elif orb.get("bias") == "BEARISH":
                score -= 4
                reasons.append(f"15m opening-range break down ({orb.get('or_low')})")
        extra5, extra5_r = candle_score(micro.get("micro_candlestick") or {})
        if micro.get("five_min_conflict"):
            score *= 0.45
            reasons.append(micro.get("five_min_note") or "5m conflicts with 15m — fade conviction")
        else:
            score += extra5 * 0.15
            reasons.extend(["5m track " + r for r in extra5_r[:2]])

    sm = live.get("session_model") or {}
    if sm.get("available"):
        p_up = float(sm.get("p_up") or 0.5)
        score += (p_up - 0.5) * 22.0
        reasons.append(f"Same-day 15m model P(up) {p_up:.0%} ({sm.get('source')})")

    # Daily TA as a light tilt when the tape is quiet (weekend / closed).
    if not session.get("available") and not micro.get("available"):
        tilt = (float(adj_tech) - 50.0) * 0.15
        score += tilt
        if abs(tilt) >= 1:
            reasons.append(f"Closed-market tilt from daily TA {adj_tech:.0f}/100")

    return max(-30.0, min(30.0, score)), reasons


def _pack(name: str, score: float, thresh: float, reasons: List[str]) -> Dict[str, Any]:
    side = _side(score, thresh)
    meta = HORIZON_META[name]
    return {
        "horizon": name,
        "label": meta["label"],
        "hold_period": meta["hold"],
        "decision": side,
        "score": round(float(score), 2),
        "threshold": thresh,
        "reasons": reasons[:8],
        "setup_type": meta["setup_type"],
    }


def _hold_pack(reasons: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "horizon": "none",
        "label": "None",
        "hold_period": "wait",
        "decision": "HOLD",
        "score": 0.0,
        "threshold": 0,
        "reasons": reasons or ["No short/mid/long book cleared its formula+candle bar."],
        "setup_type": "horizon_flat",
    }


def choose_active(
    book: Dict[str, Dict[str, Any]],
    *,
    primary: bool,
    in_session: bool,
    same_session_only: bool = False,
) -> Dict[str, Any]:
    """Pick the F&O trade.

    same_session_only (index / stock F&O ticket): the live trade is the short
    book only. Mid/long stay on the card as context — they must not set SL/T1.
    """
    if same_session_only:
        short = book["short"]
        if short["decision"] != "HOLD":
            return short
        return _hold_pack(["Same-session book is flat — no F&O ticket (mid/long are context only)."])

    order = ("short", "mid", "long") if in_session else ("mid", "long", "short")
    directional = [book[h] for h in order if book[h]["decision"] != "HOLD"]
    if directional:
        # If the first preferred book is live, take it unless a later book is
        # clearly stronger the other way (1.6× score).
        lead = directional[0]
        for other in directional[1:]:
            if other["decision"] != lead["decision"] and abs(other["score"]) > abs(lead["score"]) * 1.6:
                lead = other
                break
        return lead

    return _hold_pack()


def build_horizon_book(
    *,
    indicators: Optional[Dict[str, Any]] = None,
    candlestick: Optional[Dict[str, Any]] = None,
    structural: Optional[Dict[str, Any]] = None,
    live_context: Optional[Dict[str, Any]] = None,
    adj_tech: float = 50.0,
    primary: bool = False,
    market_tilt: Optional[Dict[str, float]] = None,
    same_session_only: Optional[bool] = None,
) -> Dict[str, Any]:
    ind = indicators or {}
    live = live_context or {}
    in_session = bool(live.get("in_market_session"))
    if same_session_only is None:
        same_session_only = bool(primary)

    short_t = SHORT_TICKET_PRIMARY if (primary or in_session) else SHORT_TICKET_OTHER
    mid_t = 8.0 if primary else 10.0
    long_t = 10.0 if primary else 12.0

    s_score, s_why = short_score(candlestick, live, adj_tech)
    m_score, m_why = formula_mid_score(ind, structural)
    l_score, l_why = formula_long_score(ind)
    tilt = market_tilt or {}
    if tilt.get("short"):
        s_score += float(tilt["short"])
        s_why.append(f"VWAP/tape tilt {float(tilt['short']):+.1f}")
    if tilt.get("mid"):
        m_score += float(tilt["mid"])
        m_why.append(f"OI/PCR tilt {float(tilt['mid']):+.1f}")
    if tilt.get("long"):
        l_score += float(tilt["long"])
        l_why.append(f"Weekly/monthly tilt {float(tilt['long']):+.1f}")

    book = {
        "short": _pack("short", s_score, short_t, s_why),
        "mid": _pack("mid", m_score, mid_t, m_why),
        "long": _pack("long", l_score, long_t, l_why),
    }
    active = choose_active(
        book, primary=primary, in_session=in_session, same_session_only=same_session_only
    )
    return {
        "short": book["short"],
        "mid": book["mid"],
        "long": book["long"],
        "active": active,
        "in_market_session": in_session,
        "same_session_only": same_session_only,
        "note": (
            "The F&O ticket is the same-session (short) book. "
            "Mid/long are context only and do not set SL/T1/T2. "
            "Cash ML HOLD is not a veto."
        ),
    }
