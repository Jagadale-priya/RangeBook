"""Regime + meta cutoff on top of the F&O T1 model.

Primary call = opening-range side. Meta = P(T1 before SL).
We only print a ticket when P(T1) clears a regime-aware cutoff.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def _wilder_adx(work: pd.DataFrame, period: int = 14) -> float:
    if work is None or len(work) < period + 2:
        return 0.0
    h = work["High"].astype(float)
    l = work["Low"].astype(float)
    c = work["Close"].astype(float)
    up = h.diff()
    dn = -l.diff()
    plus_dm = up.where((up > dn) & (up > 0), 0.0)
    minus_dm = dn.where((dn > up) & (dn > 0), 0.0)
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr.replace(0, np.nan)
    dx = (100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0)
    val = float(dx.ewm(alpha=1.0 / period, adjust=False).mean().iloc[-1])
    return val if np.isfinite(val) else 0.0


def _atr_expand(work: pd.DataFrame, period: int = 14) -> float:
    if work is None or len(work) < period + 2:
        return 1.0
    h = work["High"].astype(float)
    l = work["Low"].astype(float)
    c = work["Close"].astype(float)
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    last = float(atr.iloc[-1] or 0)
    mid = float(atr.iloc[-min(len(atr), 20) :].median() or 0)
    if mid <= 0:
        return 1.0
    return last / mid


def classify_regime(
    df: Any = None,
    *,
    vix_level: float = 0.0,
    gex: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    work = df
    if work is not None and not isinstance(work, pd.DataFrame):
        work = None
    adx = _wilder_adx(work) if work is not None else 0.0
    expand = _atr_expand(work) if work is not None else 1.0
    vix = float(vix_level or 0)
    if vix >= 18 or expand >= 1.35:
        name = "VOLATILE"
        note = "Wide swings — need a higher chance of hitting the target first."
    elif adx >= 25:
        name = "TREND"
        note = "Market is trending — momentum calls are allowed a bit earlier."
    elif 0 < adx < 20:
        name = "RANGE"
        note = "Choppy tape — only take a call if conviction is clearly high."
    else:
        name = "MIXED"
        note = "No clear trend or range."
    gex = gex or {}
    gex_bias = str(gex.get("bias") or "")
    if gex.get("available") and gex_bias == "PIN" and name == "TREND":
        name = "RANGE"
        note = gex.get("note") or "Positive GEX — treat as a range day."
    elif gex.get("available") and gex_bias == "SQUEEZE" and name in ("RANGE", "MIXED"):
        name = "TREND"
        note = gex.get("note") or "Negative GEX — a trend day is more likely."
    elif gex.get("available") and gex_bias == "PIN" and name == "MIXED":
        name = "RANGE"
        note = gex.get("note") or "Positive GEX — treat as a range day."
    return {
        "name": name,
        "adx": round(adx, 1),
        "vix": round(vix, 1) if vix else None,
        "atr_expand": round(expand, 2),
        "gex_bias": gex_bias or None,
        "note": note,
    }


def timeframe_align(
    side: int,
    *,
    five_min_conflict: bool = False,
    daily_decision: Optional[str] = None,
) -> Dict[str, Any]:
    daily = str(daily_decision or "HOLD").upper()
    daily_ok = True
    if side > 0 and "SELL" in daily:
        daily_ok = False
    if side < 0 and "BUY" in daily:
        daily_ok = False
    five_ok = not bool(five_min_conflict)
    n_ok = int(daily_ok) + int(five_ok) + 1  # 15m side always present if side != 0
    if side == 0:
        return {"aligned": False, "score": 0, "note": "No opening-range break yet."}
    if five_ok and daily_ok:
        note = "15m break, 5m, and daily bias agree."
    elif not five_ok:
        note = "5-minute tape is fighting the 15-minute call."
    else:
        note = "Daily bias does not match this 15-minute break."
    return {
        "aligned": bool(five_ok and daily_ok),
        "score": n_ok,
        "note": note,
        "five_min_ok": five_ok,
        "daily_ok": daily_ok,
    }


CONTEXT_AGREE_EASE = 0.01
CONTEXT_OPPOSE_RAISE = 0.015
CONTEXT_MAX_SHIFT = 0.03


def context_align(
    side: int,
    *,
    ml_proba: Optional[float] = None,
    adj_tech: Optional[float] = None,
    news_delta: Optional[float] = None,
    candle_bias: Optional[str] = None,
    session_bias: Optional[str] = None,
    htf_bias: Optional[str] = None,
    vix_bias: Optional[str] = None,
    level_bias: Optional[str] = None,
) -> Dict[str, Any]:
    """Daily ML, technical score, news tone, daily candle bias, session read,
    60-minute trend and VIX direction versus the 15-minute side. Each agreeing
    input eases the cutoff slightly; each opposing input raises it more.
    Direction itself never comes from here."""
    if side == 0:
        return {"available": False, "agree": 0, "oppose": 0, "shift": 0.0, "note": "", "inputs": {}}
    inputs: Dict[str, str] = {}

    def _vote(name: str, value: Optional[float], hi: float, lo: float) -> None:
        if value is None:
            return
        try:
            v = float(value)
        except (TypeError, ValueError):
            return
        if v >= hi:
            inputs[name] = "BULLISH"
        elif v <= lo:
            inputs[name] = "BEARISH"
        else:
            inputs[name] = "NEUTRAL"

    _vote("daily_ml", ml_proba, 0.55, 0.45)
    _vote("tech", adj_tech, 56.0, 44.0)
    # Same bar as analysis_engine.score_news_sentiment's tone (±3): one mild
    # headline must not cast a vote.
    _vote("news", news_delta, 3.0, -3.0)
    for name, bias in (
        ("daily_candle", candle_bias),
        ("session", session_bias),
        ("htf_60m", htf_bias),
        ("vix", vix_bias),
        ("level_in_path", level_bias),
    ):
        b = str(bias or "").upper()
        if b in ("BULLISH", "BEARISH"):
            inputs[name] = b
    want = "BULLISH" if side > 0 else "BEARISH"
    against = "BEARISH" if side > 0 else "BULLISH"
    agree = sum(1 for v in inputs.values() if v == want)
    oppose = sum(1 for v in inputs.values() if v == against)
    shift = oppose * CONTEXT_OPPOSE_RAISE - agree * CONTEXT_AGREE_EASE
    shift = max(-CONTEXT_MAX_SHIFT, min(CONTEXT_MAX_SHIFT, shift))
    if oppose and not agree:
        note = f"Daily stack and news lean against this {want.lower()} break ({oppose} against)."
    elif agree and not oppose:
        note = f"Daily stack and news agree with this break ({agree} for)."
    elif agree or oppose:
        note = f"Mixed context: {agree} for, {oppose} against."
    else:
        note = "No daily or news context on this read."
    return {
        "available": True,
        "agree": agree,
        "oppose": oppose,
        "shift": round(shift, 4),
        "note": note,
        "inputs": inputs,
    }


def meta_cutoff(
    base_buy_p: float,
    regime: Optional[Dict[str, Any]] = None,
    align: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> float:
    """Raise the bar in chop or against context; ease slightly in a clean,
    aligned trend. Bounded so no single input can turn the cutoff into a coin flip."""
    p = float(base_buy_p)
    name = str((regime or {}).get("name") or "MIXED")
    if name == "RANGE":
        p += 0.04
    elif name == "VOLATILE":
        p += 0.03
    elif name == "TREND":
        p -= 0.02
    if align and not align.get("five_min_ok", True):
        p += 0.03
    if align and align.get("aligned"):
        p -= 0.02
    if context and context.get("available"):
        try:
            p += float(context.get("shift") or 0.0)
        except (TypeError, ValueError):
            pass
    return round(min(0.72, max(0.54, p)), 4)
