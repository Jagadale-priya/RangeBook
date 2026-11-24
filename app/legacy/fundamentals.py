"""
Fundamental snapshot from Yahoo Finance `info` (free, no extra API key).
Indices and some symbols may return sparse data.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, Optional

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore

INDEX_KEYS = frozenset({"NIFTY", "BANKNIFTY", "SENSEX"})
_FUND_TTL_SEC = 6 * 3600
_FUND_CACHE: Dict[str, Any] = {}


def _index_fundamentals(symbol: str, stock_key: str) -> Dict[str, Any]:
    return {
        "available": False,
        "reason": "Index — fundamentals N/A",
        "fundamental_score": 50.0,
        "bias": "NEUTRAL",
        "combined_adjust": 0.0,
        "symbol": symbol,
        "stock": stock_key,
    }


def _finfo(info: Dict[str, Any], *keys: str) -> Optional[float]:
    for k in keys:
        v = info.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def compute_fundamental_score(info: Dict[str, Any], stock_key: str) -> Dict[str, Any]:
    key = (stock_key or "").strip().upper()
    if key in INDEX_KEYS or key.startswith("^"):
        return {
            "available": False,
            "reason": "Index — fundamentals N/A",
            "fundamental_score": 50.0,
            "bias": "NEUTRAL",
            "combined_adjust": 0.0,
        }

    pe = _finfo(info, "trailingPE", "forwardPE")
    pb = _finfo(info, "priceToBook")
    roe = _finfo(info, "returnOnEquity")
    if roe is not None and abs(roe) < 2:
        roe = roe * 100.0
    debt_eq = _finfo(info, "debtToEquity")
    rev_g = _finfo(info, "revenueGrowth")
    earn_g = _finfo(info, "earningsGrowth")
    div_y = _finfo(info, "dividendYield")
    if div_y is not None and div_y < 0.5:
        div_y = div_y * 100.0
    mcap = _finfo(info, "marketCap")

    score = 50.0
    notes: list[str] = []

    if pe is not None and pe > 0:
        if pe < 18:
            score += 6
            notes.append(f"P/E {pe:.1f} below market-typical band")
        elif pe > 35:
            score -= 6
            notes.append(f"P/E {pe:.1f} elevated")
        elif pe > 28:
            score -= 3

    if pb is not None and pb > 0:
        if pb < 2.5:
            score += 3
        elif pb > 6:
            score -= 4

    if roe is not None:
        if roe > 18:
            score += 5
            notes.append(f"ROE {roe:.1f}% strong")
        elif roe < 8:
            score -= 4

    if debt_eq is not None:
        if debt_eq > 150:
            score -= 5
            notes.append(f"Debt/equity {debt_eq:.0f} high")
        elif debt_eq < 50:
            score += 2

    if rev_g is not None:
        if rev_g > 0.12:
            score += 4
        elif rev_g < -0.05:
            score -= 4

    if earn_g is not None:
        if earn_g > 0.15:
            score += 3
        elif earn_g < -0.1:
            score -= 5

    if div_y is not None and div_y > 1.5:
        score += 2

    score = max(0.0, min(100.0, score))
    bias = "BULLISH" if score >= 58 else ("BEARISH" if score <= 42 else "NEUTRAL")
    adjust = (score - 50.0) / 1000.0

    return {
        "available": bool(pe or pb or roe or rev_g is not None),
        "fundamental_score": round(score, 1),
        "bias": bias,
        "combined_adjust": round(adjust, 4),
        "pe_trailing": round(pe, 2) if pe else None,
        "price_to_book": round(pb, 2) if pb else None,
        "roe_pct": round(roe, 2) if roe is not None else None,
        "debt_to_equity": round(debt_eq, 2) if debt_eq is not None else None,
        "revenue_growth_pct": round(rev_g * 100, 2) if rev_g is not None else None,
        "earnings_growth_pct": round(earn_g * 100, 2) if earn_g is not None else None,
        "dividend_yield_pct": round(div_y, 2) if div_y is not None else None,
        "market_cap_cr": round(mcap / 1e7, 2) if mcap and mcap > 0 else None,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "notes": notes[:4],
    }


def analyze_fundamentals(symbol: str, stock_key: str) -> Dict[str, Any]:
    key = (stock_key or "").strip().upper()
    if key in INDEX_KEYS or key.startswith("^") or str(symbol).startswith("^"):
        return _index_fundamentals(symbol, key)
    now = time.time()
    hit = _FUND_CACHE.get(symbol)
    if hit and now - float(hit[0]) < _FUND_TTL_SEC:
        return dict(hit[1])
    if yf is None:
        return {"available": False, "reason": "yfinance not installed", "fundamental_score": 50.0, "bias": "NEUTRAL", "combined_adjust": 0.0}
    try:
        info = yf.Ticker(symbol).info or {}
    except Exception as exc:
        return {"available": False, "reason": str(exc), "fundamental_score": 50.0, "bias": "NEUTRAL", "combined_adjust": 0.0}
    out = compute_fundamental_score(info, stock_key)
    out["symbol"] = symbol
    out["next_earnings"] = _next_earnings(info)
    if out.get("available"):
        _FUND_CACHE[symbol] = (now, out)
    return out


def _next_earnings(info: Dict[str, Any]) -> Optional[str]:
    for key in ("earningsTimestamp", "earningsTimestampStart", "earningsDate"):
        raw = info.get(key)
        if raw is None:
            continue
        if isinstance(raw, (list, tuple)) and raw:
            raw = raw[0]
        try:
            ts = float(raw)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        except (TypeError, ValueError, OSError):
            text = str(raw)[:10]
            if len(text) == 10 and text[4] == "-":
                return text
    return None
