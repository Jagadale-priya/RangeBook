"""5-minute (and other) intraday technical stack for strict intraday product checks."""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None  # type: ignore
    np = None  # type: ignore


def _normalize_ohlcv(df: Any) -> Optional[Any]:
    if df is None or pd is None or len(df) < 20:
        return None
    out = df.copy()
    colmap = {str(c).lower(): c for c in out.columns}
    for src, dst in [("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close")]:
        if dst not in out.columns and src in colmap:
            out[dst] = out[colmap[src]]
    if "Close" not in out.columns:
        return None
    return out.sort_index()


def _rsi(close: Any, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    r = 100.0 - (100.0 / (1.0 + rs))
    val = r.iloc[-1]
    if pd.isna(val):
        return 50.0
    return float(val)


def _ema(series: Any, span: int) -> Any:
    return series.ewm(span=span, adjust=False).mean()


def compute_intraday_technical(df: Any, interval: str = "5minute") -> Dict[str, Any]:
    """Score 0–100 from recent 5m (or other) bars."""
    ohlcv = _normalize_ohlcv(df)
    if ohlcv is None or len(ohlcv) < 30:
        return {"available": False, "error": "Not enough intraday bars"}

    close = ohlcv["Close"].astype(float)
    high = ohlcv["High"].astype(float)
    low = ohlcv["Low"].astype(float)

    score = 50.0
    rsi_val = _rsi(close, 14)
    if rsi_val < 35:
        score += 12
    elif rsi_val < 45:
        score += 6
    elif rsi_val > 65:
        score -= 12
    elif rsi_val > 55:
        score -= 6

    ema9 = _ema(close, 9)
    ema21 = _ema(close, 21)
    if float(ema9.iloc[-1]) > float(ema21.iloc[-1]):
        score += 10
        if float(ema9.iloc[-2]) <= float(ema21.iloc[-2]):
            score += 5
    else:
        score -= 10

    last6 = close.tail(6)
    if len(last6) >= 4 and float(last6.iloc[-1]) > float(last6.iloc[0]):
        score += 6
    elif len(last6) >= 4 and float(last6.iloc[-1]) < float(last6.iloc[0]):
        score -= 6

    hl = (high - low).replace(0, np.nan)
    vol_proxy = hl.tail(12).mean()
    if vol_proxy and not pd.isna(vol_proxy):
        last_range = float(high.iloc[-1] - low.iloc[-1])
        if last_range > float(vol_proxy) * 1.2 and close.iloc[-1] > close.iloc[-2]:
            score += 4
        elif last_range > float(vol_proxy) * 1.2 and close.iloc[-1] < close.iloc[-2]:
            score -= 4

    score = max(0.0, min(100.0, score))
    bias = "BULLISH" if score >= 56 else ("BEARISH" if score <= 44 else "NEUTRAL")

    return {
        "available": True,
        "interval": interval,
        "bars_used": len(ohlcv),
        "intraday_score": round(score, 1),
        "intraday_bias": bias,
        "rsi_14": round(rsi_val, 1),
        "ema9_above_21": bool(float(ema9.iloc[-1]) > float(ema21.iloc[-1])),
        "last_close": round(float(close.iloc[-1]), 2),
    }


def intraday_score_confirms(decision: str, intraday_tech: Dict[str, Any]) -> bool:
    if not intraday_tech.get("available"):
        return True
    sc = float(intraday_tech.get("intraday_score") or 50)
    if "BUY" in decision:
        return sc >= 54
    if "SELL" in decision:
        return sc <= 46
    return True


def intraday_probability_up(intraday_tech: Dict[str, Any]) -> float:
    """Map intraday TA score to pseudo-ML probability for blending."""
    if not intraday_tech.get("available"):
        return 0.5
    sc = float(intraday_tech.get("intraday_score") or 50)
    return max(0.05, min(0.95, sc / 100.0))
