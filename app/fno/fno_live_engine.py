"""
Live / short-horizon signals for F&O decisions.

F&O is volatile: daily ML is anchor only; session LTP, open-to-now move,
day-range position, and 5m/15m structure drive the product decision in market hours.
"""

from __future__ import annotations

from datetime import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore

import analysis_engine
import intraday_engine


def _ist_in_market_hours() -> bool:
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime

        now = datetime.now(ZoneInfo("Asia/Kolkata"))
    except Exception:
        from datetime import datetime

        now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return time(9, 15) <= t <= time(15, 30)


def _normalize_bars(df: Any) -> Optional[Any]:
    if df is None or pd is None or len(df) < 5:
        return None
    out = df.copy()
    colmap = {str(c).lower(): c for c in out.columns}
    for src, dst in [("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close")]:
        if dst not in out.columns and src in colmap:
            out[dst] = out[colmap[src]]
    if "Close" not in out.columns:
        return None
    return out.sort_index()


def session_from_live_quote(live_quote: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not live_quote or live_quote.get("last_price") is None:
        return {"available": False}
    lp = float(live_quote["last_price"])
    o = float(live_quote.get("open") or lp)
    h = float(live_quote.get("high") or lp)
    l = float(live_quote.get("low") or lp)
    o = o if o > 0 else lp
    rng = max(h - l, lp * 0.0005)
    chg_pct = ((lp - o) / o) * 100.0 if o else 0.0
    range_pos = max(0.0, min(1.0, (lp - l) / rng))

    bias = "NEUTRAL"
    score = 50.0
    if chg_pct >= 0.35:
        score += min(18, chg_pct * 4)
        bias = "BULLISH"
    elif chg_pct <= -0.35:
        score -= min(18, abs(chg_pct) * 4)
        bias = "BEARISH"

    if range_pos >= 0.72:
        score += 8
        if bias == "NEUTRAL":
            bias = "BULLISH"
    elif range_pos <= 0.28:
        score -= 8
        if bias == "NEUTRAL":
            bias = "BEARISH"

    if chg_pct > 0.15 and range_pos < 0.35:
        score -= 6
        bias = "NEUTRAL"
    if chg_pct < -0.15 and range_pos > 0.65:
        score += 6

    score = max(0.0, min(100.0, score))
    return {
        "available": True,
        "last_price": round(lp, 2),
        "open": round(o, 2),
        "high": round(h, 2),
        "low": round(l, 2),
        "change_from_open_pct": round(chg_pct, 3),
        "day_range_position": round(range_pos, 3),
        "session_bias": bias,
        "session_score": round(score, 1),
        "source": live_quote.get("source"),
        "feed_type": live_quote.get("feed_type"),
        "received_at_ist": live_quote.get("received_at_ist"),
    }


def microstructure_from_bars(
    df_5m: Any,
    df_15m: Optional[Any] = None,
) -> Dict[str, Any]:
    """F&O tape: 15m is the decision clock. 5m is confirm / conflict only."""
    norm15 = _normalize_bars(df_15m)
    norm5 = _normalize_bars(df_5m)
    have15 = norm15 is not None and len(norm15) >= 5
    have5 = norm5 is not None and len(norm5) >= 8
    if not have15 and not have5:
        return {"available": False}

    out: Dict[str, Any] = {
        "available": True,
        "decision_interval": "15minute" if have15 else "5minute",
        "interval_15m_bars": len(norm15) if have15 else 0,
        "interval_5m_bars": len(norm5) if have5 else 0,
        "five_min_conflict": False,
    }

    score = 50.0
    bias = "NEUTRAL"
    if have15:
        intra15 = intraday_engine.compute_intraday_technical(norm15, "15minute")
        out["intraday_15m"] = intra15
        if intra15.get("available"):
            score = float(intra15.get("intraday_score") or 50)
            bias = intra15.get("intraday_bias") or "NEUTRAL"
        cs15 = analysis_engine.detect_candlestick_window(norm15.tail(5))
        out["micro_candlestick_15m"] = cs15
        c15 = norm15["Close"].astype(float)
        look = min(8, len(c15))
        m15 = (float(c15.iloc[-1]) - float(c15.iloc[-look])) / float(c15.iloc[-look]) * 100
        out["momentum_15m_8bar_pct"] = round(m15, 3)
        if m15 >= 0.15:
            score = min(100, score + 8)
        elif m15 <= -0.15:
            score = max(0, score - 8)
        if cs15.get("bias") == "BULLISH" and float(cs15.get("score_delta") or 0) >= 4:
            score = min(100, score + 8)
            bias = "BULLISH"
        elif cs15.get("bias") == "BEARISH" and float(cs15.get("score_delta") or 0) <= -4:
            score = max(0, score - 8)
            bias = "BEARISH"
        orb = analysis_engine.detect_opening_range(norm15, analysis_engine.OPENING_RANGE_BARS)
        out["opening_range"] = orb
        if orb.get("available") and orb.get("broken"):
            if orb.get("bias") == "BULLISH":
                score = min(100, score + 5)
                if bias == "NEUTRAL":
                    bias = "BULLISH"
            elif orb.get("bias") == "BEARISH":
                score = max(0, score - 5)
                if bias == "NEUTRAL":
                    bias = "BEARISH"

    if have5:
        close5 = norm5["Close"].astype(float)
        last12 = close5.tail(min(12, len(close5)))
        mom = float(last12.iloc[-1] - last12.iloc[0])
        mom_pct = (mom / float(last12.iloc[0])) * 100 if last12.iloc[0] else 0.0
        cs5 = analysis_engine.detect_candlestick_window(norm5.tail(5))
        intra5 = intraday_engine.compute_intraday_technical(norm5, "5minute")
        out["momentum_12bar_pct"] = round(mom_pct, 3)
        out["micro_candlestick"] = cs5
        out["intraday_5m"] = intra5
        five_bias = cs5.get("bias") or "NEUTRAL"
        if have15 and bias in ("BULLISH", "BEARISH") and five_bias in ("BULLISH", "BEARISH"):
            if five_bias != bias and abs(float(cs5.get("score_delta") or 0)) >= 5:
                out["five_min_conflict"] = True
                score = 50.0 + (score - 50.0) * 0.35
                out["five_min_note"] = "5m fights the 15m book — conviction cut"
        elif not have15:
            score = float(intra5.get("intraday_score") or 50) if intra5.get("available") else 50.0
            bias = intra5.get("intraday_bias") or five_bias
            out["opening_range"] = analysis_engine.detect_opening_range(
                norm5, analysis_engine.OPENING_RANGE_BARS_5M
            )
            out["decision_interval"] = "5minute"

    out["micro_score"] = round(max(0.0, min(100.0, score)), 1)
    out["micro_bias"] = bias
    return out


def live_probability_up(session: Dict[str, Any], micro: Dict[str, Any]) -> float:
    weights: List[Tuple[float, float]] = []
    if session.get("available"):
        weights.append((float(session.get("session_score") or 50) / 100.0, 0.25))
    if micro.get("available"):
        weights.append((float(micro.get("micro_score") or 50) / 100.0, 0.55))
        intra15 = micro.get("intraday_15m") or {}
        intra5 = micro.get("intraday_5m") or {}
        if intra15.get("available"):
            weights.append((intraday_engine.intraday_probability_up(intra15), 0.20))
        elif intra5.get("available"):
            weights.append((intraday_engine.intraday_probability_up(intra5), 0.15))
    if not weights:
        return 0.5
    tot_w = sum(w for _, w in weights)
    return max(0.05, min(0.95, sum(p * w for p, w in weights) / tot_w))


def build_fno_live_context(
    live_quote: Optional[Dict[str, Any]],
    df_5m: Any,
    df_15m: Optional[Any],
    ml_proba: float,
    adj_tech: float,
    daily_combined: float,
    core_decision: str,
    cached_micro: Optional[Dict[str, Any]] = None,
    force_in_session: bool = False,
) -> Dict[str, Any]:
    in_session = bool(force_in_session) or _ist_in_market_hours()
    session = session_from_live_quote(live_quote)
    bars_ready = df_5m is not None or df_15m is not None
    if in_session and bars_ready:
        micro = microstructure_from_bars(df_5m, df_15m)
        if not micro.get("available") and cached_micro and cached_micro.get("available"):
            micro = cached_micro
    elif in_session and cached_micro and cached_micro.get("available"):
        micro = cached_micro
    else:
        micro = {"available": False}

    live_p = live_probability_up(session, micro)
    daily_p = max(0.05, min(0.95, 0.55 * ml_proba + 0.45 * (adj_tech / 100.0)))

    if in_session and (session.get("available") or micro.get("available")):
        fno_combined = round(0.15 * daily_p + 0.85 * live_p, 4)
        driver = "live_weighted"
    else:
        fno_combined = float(daily_combined)
        live_p = daily_p
        driver = "daily_anchor"

    notes: List[str] = []
    if session.get("available"):
        notes.append(
            f"Session {session.get('change_from_open_pct'):+.2f}% from open · "
            f"range position {session.get('day_range_position'):.0%} · {session.get('session_bias')}"
        )
    if micro.get("available"):
        notes.append(
            f"{micro.get('decision_interval') or '15m'} score {micro.get('micro_score')}/100 "
            f"· 15m mom {micro.get('momentum_15m_8bar_pct')}%"
        )
        pats15 = (micro.get("micro_candlestick_15m") or {}).get("patterns") or []
        if pats15:
            notes.append("15m pattern: " + pats15[0])
        if micro.get("five_min_conflict"):
            notes.append(str(micro.get("five_min_note") or "5m conflicts with 15m"))

    core_bull = "BUY" in (core_decision or "")
    core_bear = "SELL" in (core_decision or "")
    conflict = False
    if in_session and (session.get("available") or micro.get("available")):
        if core_bull and live_p < 0.44:
            conflict = True
            notes.append("Live tape contradicts core BUY — F&O bias pulled down.")
        elif core_bear and live_p > 0.56:
            conflict = True
            notes.append("Live tape contradicts core SELL — F&O bias pulled up.")
        elif not core_bull and not core_bear and abs(live_p - 0.5) >= 0.08:
            notes.append("Core HOLD but live edge detected — F&O may still show direction.")

    session_model: Dict[str, Any] = {"available": False}
    try:
        import fno_session_model

        session_model = fno_session_model.infer(df_15m if df_15m is not None else df_5m, interval="15minute")
    except Exception:
        session_model = {"available": False}

    return {
        "in_market_session": in_session,
        "driver": driver,
        "live_probability_up": round(live_p, 4),
        "fno_combined_live": round(fno_combined, 4),
        "session": session,
        "microstructure": micro,
        "session_model": session_model,
        "notes": notes,
        "live_core_conflict": conflict,
        "weights": {
            "daily_ml_ta": 0.15 if in_session else 1.0,
            "live_session_micro": 0.85 if in_session else 0.0,
        },
    }


def live_adjusted_risk(
    bearish: bool,
    current_price: float,
    atr_val: float,
    live_quote: Optional[Dict[str, Any]],
    primary_rm: Dict[str, Any],
) -> Dict[str, Any]:
    """Tighter F&O stops using session high/low when live."""
    atr = max(atr_val, current_price * 0.005)
    session = session_from_live_quote(live_quote)
    if session.get("available"):
        h = float(session["high"])
        l = float(session["low"])
        buf = max(atr * 0.35, current_price * 0.0015)
        if bearish:
            sl = round(max(current_price + 1.1 * atr, h + buf), 2)
            t1 = round(min(current_price - 1.4 * atr, l), 2)
        else:
            sl = round(min(current_price - 1.1 * atr, l - buf), 2)
            t1 = round(max(current_price + 1.4 * atr, h), 2)
        method = "session_ohlc_atr"
    else:
        if bearish:
            sl = round(current_price + 1.25 * atr, 2)
            t1 = round(current_price - 1.5 * atr, 2)
        else:
            sl = round(current_price - 1.25 * atr, 2)
            t1 = round(current_price + 1.5 * atr, 2)
        method = "atr_only"

    return {
        "stop_loss": sl,
        "target_1": t1,
        "target_2": primary_rm.get("target_2"),
        "method": method,
        "reference_price": round(current_price, 2),
    }
