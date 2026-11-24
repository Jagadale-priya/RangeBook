"""Shared market stack used by cash Analyze and F&O.

Not every overlay in existence — the layers both products actually need:
higher-timeframe trend, session VWAP, volume-profile POC, India flows/VIX,
earnings date, and (when NFO cache exists) futures basis + ATM OI/PCR.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

import fno_instruments
import india_market_context
import kite_data


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        v = float(value)
        return v if math.isfinite(v) else float(default)
    except (TypeError, ValueError):
        return float(default)


def _rsi(close: pd.Series, period: int = 14) -> Optional[float]:
    if close is None or len(close) < period + 2:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    val = 100.0 - (100.0 / (1.0 + rs))
    last = val.iloc[-1]
    return None if pd.isna(last) else float(last)


def higher_timeframes(df: pd.DataFrame) -> Dict[str, Any]:
    """Weekly + monthly bias from the same daily OHLCV (no extra download)."""
    if df is None or len(df) < 40 or "Close" not in df.columns:
        return {"available": False}
    work = df.copy()
    work.index = pd.to_datetime(work.index)
    if getattr(work.index, "tz", None) is not None:
        work.index = work.index.tz_localize(None)

    def _pack(rule: str, min_bars: int) -> Dict[str, Any]:
        try:
            try:
                bars = work.resample(rule).agg(
                    {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
                ).dropna(subset=["Close"])
            except ValueError:
                alt = "M" if rule == "ME" else rule
                bars = work.resample(alt).agg(
                    {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
                ).dropna(subset=["Close"])
        except Exception:
            return {"available": False}
        if len(bars) < min_bars:
            return {"available": False, "bars": int(len(bars))}
        close = bars["Close"].astype(float)
        sma = float(close.tail(min(20, len(close))).mean())
        last = float(close.iloc[-1])
        prev = float(close.iloc[-2])
        chg = (last / prev - 1.0) * 100 if prev else 0.0
        rsi = _rsi(close)
        vs_sma = (last / sma - 1.0) * 100 if sma else 0.0
        if vs_sma > 0.4 and (rsi is None or rsi >= 50):
            bias = "BULLISH"
            score = min(12.0, 4 + vs_sma)
        elif vs_sma < -0.4 and (rsi is None or rsi <= 50):
            bias = "BEARISH"
            score = max(-12.0, -4 + vs_sma)
        else:
            bias = "NEUTRAL"
            score = vs_sma
        return {
            "available": True,
            "bars": int(len(bars)),
            "last": round(last, 2),
            "change_pct": round(chg, 2),
            "rsi_14": None if rsi is None else round(rsi, 1),
            "vs_sma20_pct": round(vs_sma, 2),
            "bias": bias,
            "score": round(score, 2),
        }

    weekly = _pack("W-FRI", 12)
    monthly = _pack("ME", 8)
    score = float(weekly.get("score") or 0) * 0.6 + float(monthly.get("score") or 0) * 0.4
    bias = "BULLISH" if score >= 3 else ("BEARISH" if score <= -3 else "NEUTRAL")
    return {
        "available": bool(weekly.get("available") or monthly.get("available")),
        "weekly": weekly,
        "monthly": monthly,
        "bias": bias,
        "score": round(score, 2),
        "note": "Resampled from daily bars — not a separate weekly/monthly model.",
    }


def session_vwap(live_quote: Optional[Dict[str, Any]], current_price: float) -> Dict[str, Any]:
    """Kite session average_price is VWAP when the full quote is present."""
    if not live_quote:
        return {"available": False, "note": "No live quote"}
    avg = live_quote.get("average_price")
    try:
        vwap = float(avg) if avg not in (None, "", 0) else None
    except (TypeError, ValueError):
        vwap = None
    if vwap is None or vwap <= 0:
        return {
            "available": False,
            "note": "VWAP needs Kite full quote (average_price). WS LTP-only ticks omit it.",
        }
    dist = (float(current_price) - vwap) / vwap * 100
    bias = "ABOVE_VWAP" if dist > 0.08 else ("BELOW_VWAP" if dist < -0.08 else "AT_VWAP")
    return {
        "available": True,
        "vwap": round(vwap, 2),
        "distance_pct": round(dist, 3),
        "bias": bias,
        "score": round(max(-8.0, min(8.0, dist * 4)), 2),
    }


def volume_profile_lite(df: pd.DataFrame, bins: int = 16) -> Dict[str, Any]:
    """POC / value area from the last ~60 daily typical prices × volume."""
    if df is None or len(df) < 20 or "Close" not in df.columns:
        return {"available": False}
    tail = df.tail(60)
    typical = (tail["High"].astype(float) + tail["Low"].astype(float) + tail["Close"].astype(float)) / 3.0
    vol = tail["Volume"].astype(float).clip(lower=1.0)
    lo, hi = float(typical.min()), float(typical.max())
    if hi <= lo:
        return {"available": False}
    edges = np.linspace(lo, hi, bins + 1)
    idx = np.clip(np.digitize(typical.to_numpy(), edges) - 1, 0, bins - 1)
    weights = np.zeros(bins)
    for i, w in zip(idx, vol.to_numpy()):
        weights[i] += w
    poc_i = int(np.argmax(weights))
    poc = (edges[poc_i] + edges[poc_i + 1]) / 2.0
    last = float(tail["Close"].iloc[-1])
    dist = (last - poc) / poc * 100 if poc else 0.0
    return {
        "available": True,
        "poc": round(poc, 2),
        "value_low": round(float(edges[max(0, poc_i - 2)]), 2),
        "value_high": round(float(edges[min(bins, poc_i + 3)]), 2),
        "distance_to_poc_pct": round(dist, 2),
        "bias": "ABOVE_POC" if dist > 0.3 else ("BELOW_POC" if dist < -0.3 else "AT_POC"),
        "score": round(max(-6.0, min(6.0, dist)), 2),
        "note": "Lite profile from daily typical price, not tick volume profile.",
    }


def _quote_nfo(contract: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    tradingsymbol = (contract or {}).get("tradingsymbol")
    if not tradingsymbol:
        return {"available": False}
    raw, err = kite_data.fetch_exchange_quote((contract or {}).get("exchange") or "NFO", tradingsymbol)
    if err or not raw:
        return {"available": False, "error": err, "tradingsymbol": tradingsymbol}
    last = float(raw.get("last_price") or 0)
    oi = raw.get("oi")
    try:
        oi_n = float(oi) if oi is not None else None
    except (TypeError, ValueError):
        oi_n = None
    iv = raw.get("implied_volatility") or (raw.get("depth") or {}).get("implied_volatility")
    try:
        iv_n = float(iv) if iv is not None else None
    except (TypeError, ValueError):
        iv_n = None
    return {
        "available": True,
        "tradingsymbol": tradingsymbol,
        "last_price": round(last, 2),
        "oi": oi_n,
        "volume": int(raw.get("volume") or 0),
        "implied_volatility": None if iv_n is None else round(iv_n, 4),
        "average_price": raw.get("average_price"),
    }


def derivatives_snapshot(stock_key: str, spot: float, vix_level: float = 0.0) -> Dict[str, Any]:
    """ATM CE/PE OI + PCR + futures basis. Needs NFO instrument cache + Kite."""
    try:
        contracts = fno_instruments.resolve_contracts(stock_key, spot)
    except Exception as exc:
        return {"available": False, "error": str(exc)}
    if not contracts.get("available"):
        return {"available": False, "error": contracts.get("error"), "contracts": contracts}

    fut = _quote_nfo(contracts.get("future"))
    ce = _quote_nfo(contracts.get("atm_ce"))
    pe = _quote_nfo(contracts.get("atm_pe"))

    pcr = None
    if ce.get("oi") and pe.get("oi") and float(ce["oi"]) > 0:
        pcr = float(pe["oi"]) / float(ce["oi"])
    basis = None
    if fut.get("available") and fut.get("last_price") and spot:
        basis = float(fut["last_price"]) - float(spot)

    score = 0.0
    notes: List[str] = []
    if pcr is not None:
        if pcr >= 1.2:
            score += 4
            notes.append(f"PCR {pcr:.2f} (put-heavy — often a bounce tilt)")
        elif pcr <= 0.8:
            score -= 4
            notes.append(f"PCR {pcr:.2f} (call-heavy — often a fade/up-stretch)")
        else:
            notes.append(f"PCR {pcr:.2f} balanced")
    if basis is not None:
        notes.append(f"Futures basis {basis:+.1f} vs spot")
        if basis > abs(spot) * 0.0015:
            score += 1
        elif basis < -abs(spot) * 0.0015:
            score -= 1

    gex = {"available": False}
    try:
        import option_gex

        gex = option_gex.snapshot(stock_key, float(spot or 0), vix_level=vix_level)
        if gex.get("available"):
            notes.append(gex.get("note") or f"GEX {gex.get('bias')}")
            if gex.get("bias") == "PIN":
                score += 2
            elif gex.get("bias") == "SQUEEZE":
                score -= 2
    except Exception:
        gex = {"available": False}

    return {
        "available": True,
        "expiry": contracts.get("expiry"),
        "future": fut,
        "atm_ce": ce,
        "atm_pe": pe,
        "pcr": None if pcr is None else round(pcr, 3),
        "futures_basis": None if basis is None else round(basis, 2),
        "gex": gex,
        "bias": "BULLISH" if score >= 3 else ("BEARISH" if score <= -3 else "NEUTRAL"),
        "score": round(score, 2),
        "notes": notes,
        "contracts": {
            "future": (contracts.get("future") or {}).get("tradingsymbol"),
            "atm_ce": (contracts.get("atm_ce") or {}).get("tradingsymbol"),
            "atm_pe": (contracts.get("atm_pe") or {}).get("tradingsymbol"),
        },
    }


def book_imbalance(live_quote: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not live_quote:
        return {"available": False}
    buy = live_quote.get("buy_quantity")
    sell = live_quote.get("sell_quantity")
    try:
        b, s = float(buy or 0), float(sell or 0)
    except (TypeError, ValueError):
        return {"available": False}
    if b + s <= 0:
        return {"available": False, "note": "Depth not on this feed (WS LTP has no book)."}
    ratio = b / s if s else 2.0
    return {
        "available": True,
        "buy_quantity": b,
        "sell_quantity": s,
        "buy_sell_ratio": round(ratio, 2),
        "bias": "BID" if ratio >= 1.15 else ("ASK" if ratio <= 0.87 else "BALANCED"),
        "score": round(max(-5.0, min(5.0, (ratio - 1.0) * 8)), 2),
    }


def build_full_stack(
    *,
    stock_key: str,
    df: pd.DataFrame,
    current_price: float,
    live_quote: Optional[Dict[str, Any]],
    is_indian: bool,
    want_derivatives: bool = True,
) -> Dict[str, Any]:
    htf = higher_timeframes(df)
    vwap = session_vwap(live_quote, current_price)
    vp = volume_profile_lite(df)
    book = book_imbalance(live_quote)
    india = {"available": False, "combined_adjust": 0.0}
    if is_indian:
        try:
            india = india_market_context.fetch_india_market_context()
        except Exception as exc:
            india = {"available": False, "error": str(exc), "combined_adjust": 0.0}

    deriv = {"available": False}
    if want_derivatives and is_indian and kite_data.kite_enabled():
        deriv = derivatives_snapshot(
            stock_key,
            current_price,
            vix_level=_finite_float(((india.get("india_vix") or {}).get("level")), 0.0),
        )

    score = (
        float(htf.get("score") or 0) * 0.25
        + float(vwap.get("score") or 0) * 0.2
        + float(vp.get("score") or 0) * 0.15
        + float(book.get("score") or 0) * 0.1
        + float((india.get("score_delta") or 0)) * 0.8
        + float(deriv.get("score") or 0) * 0.35
    )
    score = max(-12.0, min(12.0, score))
    bias = "BULLISH" if score >= 2.5 else ("BEARISH" if score <= -2.5 else "MIXED")
    return {
        "available": True,
        "bias": bias,
        "score": round(score, 2),
        "combined_adjust": round(score / 100.0 * 0.04, 4),
        "higher_timeframe": htf,
        "vwap": vwap,
        "volume_profile": vp,
        "book": book,
        "india": india,
        "derivatives": deriv,
        "fetched_at": datetime.now().isoformat(),
        "used_for": ["cash", "intraday", "fno"],
        "not_included": [
            "Max pain / vendor Greeks",
            "Tick volume profile / market profile",
            "Elliott / harmonic / Gann",
        ],
    }


def extra_horizon_tilt(pack: Dict[str, Any]) -> Dict[str, float]:
    """Small signed tilts for the F&O short/mid/long books."""
    htf = pack.get("higher_timeframe") or {}
    vwap = pack.get("vwap") or {}
    deriv = pack.get("derivatives") or {}
    return {
        "short": float(vwap.get("score") or 0) * 0.4,
        "mid": float(deriv.get("score") or 0) * 0.5,
        "long": float(htf.get("score") or 0) * 0.45,
    }
