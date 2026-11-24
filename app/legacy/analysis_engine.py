"""
Pre-market / intraday enrichment: candlesticks, news tone, global lead, day range, reasons.
"""

from __future__ import annotations

import math
import threading
import time as time_mod
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

import numpy as np
import pandas as pd

import india_market_context

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore

IST = ZoneInfo("Asia/Kolkata") if ZoneInfo else None
# First completed 15m bar (09:15–09:30). 3×5m is the same window when 15m is missing.
OPENING_RANGE_BARS = 1
OPENING_RANGE_BARS_5M = 3

BULLISH_NEWS = (
    "dividend", "bonus", "buyback", "upgrade", "profit", "growth", "order win",
    "partnership", "approval", "record", "expansion", "acquisition",
    "ceasefire", "rate cut", "dovish",
)
BEARISH_NEWS = (
    "downgrade", "loss", "fraud", "default", "resign", "penalty", "investigation",
    "litigation", "delay", "cut", "weak", "slump", "recall",
    "crude", "oil price", "hormuz", "iran", "geopolit", "bond yield",
    "sell-off", "selloff", "sanction",
)

GLOBAL_TICKERS = {
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ",
    "^DJI": "Dow Jones",
}

# Overnight panel for pre-market cron (Yahoo symbols; no live feed)
OVERNIGHT_PANEL: Dict[str, Tuple[str, float, bool]] = {
    "^GSPC": ("S&P 500", 1.0, False),
    "^IXIC": ("NASDAQ", 1.0, False),
    "^DJI": ("Dow Jones", 0.85, False),
    "^VIX": ("VIX", 0.9, True),
    "^N225": ("Nikkei 225", 0.75, False),
    "^HSI": ("Hang Seng", 0.65, False),
    "CL=F": ("Crude WTI", 0.85, False),
    "INR=X": ("USD/INR", 0.7, True),
    "^INDIAVIX": ("India VIX", 0.85, True),
}


def _ist_now() -> datetime:
    if IST:
        return datetime.now(tz=IST)
    return datetime.now()


def resolve_analysis_mode(requested: Optional[str] = None) -> str:
    """auto | premarket | intraday."""
    if requested and requested.lower() in ("premarket", "pre_market", "pre"):
        return "premarket"
    if requested and requested.lower() in ("intraday", "live", "market"):
        return "intraday"
    now = _ist_now()
    t = now.time()
    if time(9, 15) <= t <= time(15, 30) and now.weekday() < 5:
        return "intraday"
    return "premarket"


def _body(o: float, h: float, l: float, c: float) -> float:
    return abs(c - o)


def _range(h: float, l: float) -> float:
    return max(h - l, 1e-9)


def _empty_candle() -> Dict[str, Any]:
    return {"patterns": [], "score_delta": 0, "bias": "NEUTRAL"}


def _ohlc_row(row: Any) -> Tuple[float, float, float, float]:
    return float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])


def detect_candlestick_patterns(df: pd.DataFrame) -> Dict[str, Any]:
    """Rule-based patterns on the last 5 candles (daily or 5m/15m)."""
    if df is None or len(df) < 3:
        return _empty_candle()
    return detect_candlestick_window(df.tail(5))


def detect_candlestick_three_bars(tail: pd.DataFrame) -> Dict[str, Any]:
    """Detect patterns on three+ OHLC rows (historical scan or live)."""
    return detect_candlestick_window(tail)


def detect_candlestick_window(tail: pd.DataFrame) -> Dict[str, Any]:
    """Classic reversal / continuation catalog for same-session F&O and daily TA."""
    if tail is None or len(tail) < 3:
        return _empty_candle()

    patterns: List[str] = []
    score = 0.0

    c0 = tail.iloc[-1]
    c1 = tail.iloc[-2]
    o, h, l, c = _ohlc_row(c0)
    po, ph, pl, pc = _ohlc_row(c1)

    body = _body(o, h, l, c)
    rng = _range(h, l)
    lower_wick = min(o, c) - l
    upper_wick = h - max(o, c)
    prev_up = pc > po
    prev_down = pc < po

    if body / rng < 0.12:
        if lower_wick > 2.2 * max(body, rng * 0.04) and upper_wick < rng * 0.12:
            patterns.append("Dragonfly doji (bullish)")
            score += 5
        elif upper_wick > 2.2 * max(body, rng * 0.04) and lower_wick < rng * 0.12:
            patterns.append("Gravestone doji (bearish)")
            score -= 5
        else:
            patterns.append("Doji (indecision)")

    if 0.12 <= body / rng <= 0.28 and upper_wick > body * 0.8 and lower_wick > body * 0.8:
        patterns.append("Spinning top (indecision)")

    if lower_wick > 2 * body and upper_wick < body:
        if c > o:
            patterns.append("Hammer (bullish reversal)")
            score += 6
        elif prev_up:
            patterns.append("Hanging man (bearish reversal)")
            score -= 5
    if upper_wick > 2 * body and lower_wick < body:
        if c < o:
            patterns.append("Shooting star (bearish reversal)")
            score -= 6
        elif prev_down:
            patterns.append("Inverted hammer (bullish reversal)")
            score += 5

    if c > o and pc < po and c >= po and o <= pc:
        patterns.append("Bullish engulfing")
        score += 8
    elif c < o and pc > po and c <= po and o >= pc:
        patterns.append("Bearish engulfing")
        score -= 8

    if h > ph and l < pl:
        patterns.append("Outside bar")
        score += 3 if c > o else -3
    elif h < ph and l > pl:
        patterns.append("Inside bar (compression)")

    if body / rng > 0.78 and lower_wick < rng * 0.08 and upper_wick < rng * 0.08:
        if c > o and prev_down:
            patterns.append("Bullish belt hold")
            score += 4
        elif c < o and prev_up:
            patterns.append("Bearish belt hold")
            score -= 4

    if prev_down and c > o and o > ph and c > ph:
        patterns.append("Bullish kicker")
        score += 7
    if prev_up and c < o and o < pl and c < pl:
        patterns.append("Bearish kicker")
        score -= 7

    if abs(pc - po) > 0:
        if pc > po and c < o and c <= po and o >= pc:
            patterns.append("Bearish harami")
            score -= 4
        if pc < po and c > o and c >= po and o <= pc:
            patterns.append("Bullish harami")
            score += 4

    if body / rng > 0.85:
        patterns.append("Marubozu (strong momentum)")
        score += 4 if c > o else -4

    if pc < po and o < pc and c > (po + pc) / 2 and c < po:
        patterns.append("Piercing line (bullish)")
        score += 5
    if pc > po and o > pc and c < (po + pc) / 2 and c > po:
        patterns.append("Dark cloud cover (bearish)")
        score -= 5

    if prev_down and c > o and abs(c - pc) / max(abs(pc), 1e-9) < 0.0015:
        patterns.append("Bullish meeting lines")
        score += 3
    if prev_up and c < o and abs(c - pc) / max(abs(pc), 1e-9) < 0.0015:
        patterns.append("Bearish meeting lines")
        score -= 3

    if abs(h - max(o, c)) / rng < 0.05 and abs(l - min(o, c)) / rng < 0.08:
        patterns.append("Tweezer top/bottom (reversal watch)")
        score += 2 if c > o else -2
    if abs(h - ph) / max(ph, 1e-9) < 0.0012 and h > max(o, c) and ph > max(po, pc):
        patterns.append("Tweezer top")
        score -= 3
    if abs(l - pl) / max(pl, 1e-9) < 0.0012 and l < min(o, c) and pl < min(po, pc):
        patterns.append("Tweezer bottom")
        score += 3

    if len(tail) >= 3:
        a, b, d = tail.iloc[-3], tail.iloc[-2], tail.iloc[-1]
        ao, ah, al, ac = _ohlc_row(a)
        bo, bh, bl, bc = _ohlc_row(b)
        do, dh, dl, dc = _ohlc_row(d)
        a_up, b_up, d_up = ac > ao, bc > bo, dc > do
        a_dn, b_dn, d_dn = ac < ao, bc < bo, dc < do

        if a_up and b_up and d_up and dc > bc > ac:
            patterns.append("Three white soldiers")
            score += 5
        if a_dn and b_dn and d_dn and dc < bc < ac:
            patterns.append("Three black crows")
            score -= 5

        if b_dn and a_up and d_up and dc > bo and bc < (ao + ac) / 2:
            patterns.append("Morning star (bullish)")
            score += 7
        if b_up and a_dn and d_dn and dc < bo and bc > (ao + ac) / 2:
            patterns.append("Evening star (bearish)")
            score -= 7

        b_body = _body(bo, bh, bl, bc)
        b_rng = _range(bh, bl)
        if b_body / b_rng < 0.15:
            if a_dn and d_up and dc > (ao + ac) / 2:
                patterns.append("Morning doji star (bullish)")
                score += 6
            if a_up and d_dn and dc < (ao + ac) / 2:
                patterns.append("Evening doji star (bearish)")
                score -= 6

        if a_dn and bh < ah and bl > al and d_up and dc > ao:
            patterns.append("Three inside up")
            score += 5
        if a_up and bh < ah and bl > al and d_dn and dc < ao:
            patterns.append("Three inside down")
            score -= 5
        if a_dn and b_up and bc >= ao and bo <= ac and d_up and dc > bc:
            patterns.append("Three outside up")
            score += 5
        if a_up and b_dn and bc <= ao and bo >= ac and d_dn and dc < bc:
            patterns.append("Three outside down")
            score -= 5

    if len(tail) >= 5:
        x0, x1, x2, x3, x4 = (tail.iloc[i] for i in range(-5, 0))
        o0, _, _, c0c = _ohlc_row(x0)
        o1, h1, l1, c1c = _ohlc_row(x1)
        o2, h2, l2, c2c = _ohlc_row(x2)
        o3, h3, l3, c3c = _ohlc_row(x3)
        o4, _, _, c4c = _ohlc_row(x4)
        if c0c > o0 and c4c > o4 and c4c > c0c:
            if all(c < o for c, o in ((c1c, o1), (c2c, o2), (c3c, o3))):
                if max(h1, h2, h3) < max(o0, c0c) and min(l1, l2, l3) > min(o0, c0c):
                    patterns.append("Rising three methods")
                    score += 4
        if c0c < o0 and c4c < o4 and c4c < c0c:
            if all(c > o for c, o in ((c1c, o1), (c2c, o2), (c3c, o3))):
                if min(l1, l2, l3) > min(o0, c0c) and max(h1, h2, h3) < max(o0, c0c):
                    patterns.append("Falling three methods")
                    score -= 4

    if len(tail) >= 3:
        gap_up = l > ph
        gap_dn = h < pl
        if gap_up and c > o and pc > po:
            patterns.append("Rising window (bullish gap)")
            score += 3
        if gap_dn and c < o and pc < po:
            patterns.append("Falling window (bearish gap)")
            score -= 3
        mid_body = _body(po, ph, pl, pc)
        if gap_up and c < o and c > pc and body < mid_body:
            patterns.append("Upside tasuki gap")
            score += 3
        if gap_dn and c > o and c < pc and body < mid_body:
            patterns.append("Downside tasuki gap")
            score -= 3
        if body / rng < 0.12 and abs(pc - po) > 0 and min(o, c) > min(po, pc) and max(o, c) < max(po, pc):
            if pc < po:
                patterns.append("Harami cross (bullish)")
                score += 3
            else:
                patterns.append("Harami cross (bearish)")
                score -= 3

    if len(tail) >= 3:
        a, b, d = tail.iloc[-3], tail.iloc[-2], tail.iloc[-1]
        ao, ah, al, ac = _ohlc_row(a)
        bo, bh, bl, bc = _ohlc_row(b)
        do, dh, dl, dc = _ohlc_row(d)
        if ac < ao and bc < bo and dc > do and dc > ao and do < bc:
            patterns.append("Bullish three line strike")
            score += 4
        if ac > ao and bc > bo and dc < do and dc < ao and do > bc:
            patterns.append("Bearish three line strike")
            score -= 4
        b_small = _body(bo, bh, bl, bc) / max(_range(bh, bl), 1e-9) < 0.12
        if ac < ao and b_small and bl > ah and dc > do and dl > bh:
            patterns.append("Abandoned baby (bullish)")
            score += 6
        if ac > ao and b_small and bh < al and dc < do and dh < bl:
            patterns.append("Abandoned baby (bearish)")
            score -= 6
        if ac > ao and bc > bo and dc > do and dc < bc and bc < ac:
            patterns.append("Advance block (rally tiring)")
            score -= 3
        if (ac > ao) == (bc > bo) and abs(bo - ac) / max(abs(ac), 1e-9) < 0.002:
            if bc > bo:
                patterns.append("Bullish separating lines")
                score += 3
            else:
                patterns.append("Bearish separating lines")
                score -= 3

    if len(tail) >= 4:
        w0, w1, w2, w3 = (tail.iloc[i] for i in range(-4, 0))
        _, _, _, c_a = _ohlc_row(w0)
        o_b, _, _, c_b = _ohlc_row(w1)
        o_c, _, _, c_c = _ohlc_row(w2)
        o_d, _, _, c_d = _ohlc_row(w3)
        if c_a > _ohlc_row(w0)[0] and c_b < o_b and c_c < o_c and c_d > o_d and abs(c_d - c_a) / max(abs(c_a), 1e-9) < 0.003:
            patterns.append("Stick sandwich (bullish)")
            score += 3

    if prev_down and c > o and o < pc and abs(c - pl) / max(rng, 1e-9) < 0.08:
        patterns.append("On-neck line (bearish)")
        score -= 3
    if prev_down and c > o and o < pc and c > pl and c < pc and (c - pl) / max(abs(pc - po), 1e-9) < 0.25:
        patterns.append("In-neck line (bearish)")
        score -= 3
    if prev_down and c > o and c > pc and c < (po + pc) / 2:
        patterns.append("Thrusting pattern (bearish)")
        score -= 3
    if prev_down and c < o and abs(l - pl) / max(abs(pl), 1e-9) < 0.0015:
        patterns.append("Matching low (bullish)")
        score += 3
    if prev_down and c < o and o > pc and c < po and min(o, c) > min(po, pc) and max(o, c) < max(po, pc):
        patterns.append("Homing pigeon (bearish)")
        score -= 3

    if len(tail) >= 3:
        a, b, d = tail.iloc[-3], tail.iloc[-2], tail.iloc[-1]
        ao, ah, al, ac = _ohlc_row(a)
        bo, bh, bl, bc = _ohlc_row(b)
        do, dh, dl, dc = _ohlc_row(d)
        a_doji = _body(ao, ah, al, ac) / max(_range(ah, al), 1e-9) < 0.12
        b_doji = _body(bo, bh, bl, bc) / max(_range(bh, bl), 1e-9) < 0.12
        d_doji = _body(do, dh, dl, dc) / max(_range(dh, dl), 1e-9) < 0.12
        if a_doji and b_doji and d_doji and (bl > ah or bh < al):
            patterns.append("Tri-star (reversal watch)")
            score += 2 if dc >= do else -2
        if ac > ao and bl > ah and bc < bo and dc < do and max(do, dc) > bc and min(do, dc) < bo and dl > ac:
            patterns.append("Upside gap two crows (bearish)")
            score -= 5
        if ac > ao and bc < bo and dc < do and bo > ac and do > bc and dc < ac:
            patterns.append("Two crows (bearish)")
            score -= 4
        if ac < ao and bc < bo and bl < al and _body(bo, bh, bl, bc) < _body(ao, ah, al, ac) and dc > do and dc < bc:
            patterns.append("Unique three river (bullish)")
            score += 4
        if ac < ao and bc < bo and dc < do and max(bh, dh) < al and bc > ac and dc > bc:
            patterns.append("Three stars in the south (bullish)")
            score += 4

    # unique preserve order
    seen = set()
    uniq: List[str] = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    score = max(-18.0, min(18.0, score))
    bias = "BULLISH" if score >= 4 else ("BEARISH" if score <= -4 else "NEUTRAL")
    return {"patterns": uniq, "score_delta": score, "bias": bias}


def detect_opening_range(df: pd.DataFrame, n_bars: int = OPENING_RANGE_BARS) -> Dict[str, Any]:
    """First n bars of the latest session — break used for same-day F&O."""
    if df is None or len(df) < n_bars + 2:
        return {"available": False}
    work = df.copy()
    colmap = {str(c).lower(): c for c in work.columns}
    for src, dst in (("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close")):
        if dst not in work.columns and src in colmap:
            work[dst] = work[colmap[src]]
    if "Close" not in work.columns:
        return {"available": False}
    idx = work.index
    try:
        last_day = pd.Timestamp(idx[-1]).date()
        day = work[[pd.Timestamp(i).date() == last_day for i in idx]]
    except Exception:
        day = work
    if len(day) < n_bars + 1:
        return {"available": False}
    or_bars = day.iloc[:n_bars]
    or_high = float(or_bars["High"].astype(float).max())
    or_low = float(or_bars["Low"].astype(float).min())
    last = float(day["Close"].astype(float).iloc[-1])
    bias = "NEUTRAL"
    if last > or_high:
        bias = "BULLISH"
    elif last < or_low:
        bias = "BEARISH"
    return {
        "available": True,
        "or_high": round(or_high, 2),
        "or_low": round(or_low, 2),
        "last_close": round(last, 2),
        "bias": bias,
        "n_bars": n_bars,
        "broken": bias != "NEUTRAL",
    }


def score_news_sentiment(news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not news_items:
        return {"score_delta": 0, "tone": "NEUTRAL", "highlights": []}

    try:
        import finbert_news

        fb = finbert_news.score_news_items(news_items)
        if fb:
            return fb
    except Exception:
        pass

    delta = 0.0
    highlights: List[str] = []
    for item in news_items[:12]:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        bull = sum(1 for w in BULLISH_NEWS if w in text)
        bear = sum(1 for w in BEARISH_NEWS if w in text)
        if bull > bear:
            delta += min(3, bull)
            highlights.append(f"Positive tone: {item.get('title', '')[:100]}")
        elif bear > bull:
            delta -= min(3, bear)
            highlights.append(f"Risk tone: {item.get('title', '')[:100]}")

    delta = max(-12.0, min(12.0, delta))
    tone = "BULLISH" if delta >= 3 else ("BEARISH" if delta <= -3 else "NEUTRAL")
    return {
        "score_delta": delta,
        "tone": tone,
        "highlights": highlights[:5],
    }


_PANEL_LOCK = threading.Lock()
_PANEL_CACHE: Dict[str, Any] = {"at": 0.0, "data": None}
_PANEL_TTL_SEC = 900.0


def _one_overnight(ticker: str, name: str, weight: float, invert: bool) -> Optional[Dict[str, Any]]:
    if yf is None:
        return None
    try:
        hist = yf.Ticker(ticker).history(period="10d", auto_adjust=False, timeout=5)
    except TypeError:
        hist = yf.Ticker(ticker).history(period="10d", auto_adjust=False)
    except Exception:
        return None
    if hist is None or len(hist) < 2:
        return None
    close = float(hist["Close"].iloc[-1])
    prev = float(hist["Close"].iloc[-2])
    if not math.isfinite(close) or not math.isfinite(prev) or prev == 0:
        return None
    chg = (close / prev - 1) * 100
    bar_date = str(hist.index[-1].date()) if hasattr(hist.index[-1], "date") else str(hist.index[-1])[:10]
    signed = -chg if invert else chg
    return {
        "symbol": ticker,
        "name": name,
        "close": round(close, 4),
        "prev_close": round(prev, 4),
        "change_pct": round(chg, 2),
        "impact_score": round(signed * weight, 2),
        "bar_date": bar_date,
        "invert_for_india": invert,
        "_signed": signed,
        "_weight": weight,
    }


def fetch_global_overnight_panel() -> Dict[str, Any]:
    """Last available close vs previous close for macro symbols (cron / pre-market UI)."""
    now = time_mod.time()
    with _PANEL_LOCK:
        cached = _PANEL_CACHE.get("data")
        if cached and now - float(_PANEL_CACHE.get("at") or 0) < _PANEL_TTL_SEC:
            return cached
        if yf is None:
            return {"available": False, "markets": [], "bias": "NEUTRAL", "score_delta": 0, "as_of_ist": None}

        from concurrent.futures import ThreadPoolExecutor

        markets: List[Dict[str, Any]] = []
        score = 0.0
        as_of = _ist_now().isoformat()
        items = list(OVERNIGHT_PANEL.items())
        with ThreadPoolExecutor(max_workers=min(6, len(items) or 1)) as pool:
            futs = [
                pool.submit(_one_overnight, ticker, meta[0], meta[1], meta[2])
                for ticker, meta in items
            ]
            for fut in futs:
                try:
                    row = fut.result(timeout=8)
                except Exception:
                    row = None
                if not row:
                    continue
                signed = float(row.pop("_signed"))
                weight = float(row.pop("_weight"))
                markets.append(row)
                if signed > 0.35:
                    score += weight * 2
                elif signed < -0.35:
                    score -= weight * 2

        score = max(-12.0, min(12.0, score))
        bias = "RISK_ON" if score >= 3 else ("RISK_OFF" if score <= -3 else "NEUTRAL")
        payload = {
            "available": bool(markets),
            "markets": markets,
            "bias": bias,
            "score_delta": round(score, 2),
            "as_of_ist": as_of,
        }
        if markets:
            _PANEL_CACHE["at"] = time_mod.time()
            _PANEL_CACHE["data"] = payload
        return payload


def fetch_global_lead() -> Dict[str, Any]:
    panel = fetch_global_overnight_panel()
    if not panel.get("available"):
        return {"available": False, "markets": [], "bias": "NEUTRAL", "score_delta": 0}
    slim = [
        {"symbol": m["symbol"], "name": m["name"], "change_pct": m["change_pct"]}
        for m in panel["markets"]
        if m["symbol"] in GLOBAL_TICKERS or m["symbol"] in ("^GSPC", "^IXIC", "^DJI")
    ]
    if not slim:
        slim = [{"symbol": m["symbol"], "name": m["name"], "change_pct": m["change_pct"]} for m in panel["markets"][:3]]
    return {
        "available": True,
        "markets": slim,
        "bias": panel["bias"],
        "score_delta": panel["score_delta"],
        "overnight_panel": panel,
    }


def planned_session_width(prev_high: float, prev_low: float, atr_val: float, price: float) -> float:
    """Full-day size. Yesterday's range matches the next session; ATR is the floor."""
    day_rng = max(float(prev_high) - float(prev_low), 0.0)
    atr = max(float(atr_val), float(price) * 0.004)
    return max(day_rng, atr, float(price) * 0.004)


def _range_payload(
    center: float,
    width: float,
    *,
    locked: bool,
    anchor: str,
    method: str,
    pivot: float,
    open_px: Optional[float] = None,
    prev_close: Optional[float] = None,
) -> Dict[str, Any]:
    half = width / 2.0
    hi = round(center + half, 2)
    lo = round(center - half, 2)
    return {
        "expected_high": hi,
        "expected_low": lo,
        "session_expected_high": hi,
        "session_expected_low": lo,
        "planned_width": round(width, 2),
        "locked": locked,
        "anchor": anchor,
        "session_bias": "NEUTRAL",
        "method": method,
        "reference_pivot": round(pivot, 2),
        "reference_open": None if open_px is None else round(open_px, 2),
        "reference_prev_close": None if prev_close is None else round(float(prev_close), 2),
    }


def forecast_day_range(
    df: pd.DataFrame,
    current_price: float,
    atr_val: float,
    live_quote: Optional[Dict[str, Any]],
    mode: str,
    combined_score: float,
) -> Dict[str, Any]:
    """Same-session high/low. Width from yesterday; center is the open, not the score.

    Before the open the box is provisional around the prior close.
    `combined_score` is ignored so a bullish/bearish lean cannot slide the box.
    """
    del mode, combined_score
    prev = df.iloc[-1]
    prev_h, prev_l, prev_c = float(prev["High"]), float(prev["Low"]), float(prev["Close"])
    pivot = (prev_h + prev_l + prev_c) / 3.0
    width = planned_session_width(prev_h, prev_l, atr_val, current_price or prev_c)
    open_px = None
    if live_quote and live_quote.get("open"):
        try:
            open_px = float(live_quote["open"])
        except (TypeError, ValueError):
            open_px = None
    if open_px and open_px > 0:
        return _range_payload(
            open_px, width, locked=True, anchor="session_open",
            method="open_locked_width", pivot=pivot, open_px=open_px, prev_close=prev_c,
        )
    return _range_payload(
        prev_c, width, locked=False, anchor="prev_close",
        method="premarket_width_provisional", pivot=pivot, prev_close=prev_c,
    )


def lock_day_range_on_open(day_range: Dict[str, Any], open_price: float) -> Dict[str, Any]:
    """Seat the planned width on the cash open.

    A gap larger than 0.35% of the prior close gets extra room on the gap side.
    A normal open stays symmetric.
    """
    width = float(day_range.get("planned_width") or 0)
    if width <= 0:
        width = float(day_range.get("expected_high") or 0) - float(day_range.get("expected_low") or 0)
    width = max(width, 1.0)
    open_px = float(open_price)
    prev_close = day_range.get("reference_prev_close")
    half = width / 2.0
    hi = open_px + half
    lo = open_px - half
    method = "open_locked_width"
    try:
        prev = float(prev_close) if prev_close is not None else 0.0
    except (TypeError, ValueError):
        prev = 0.0
    if prev > 0:
        gap = open_px - prev
        if abs(gap) / prev >= 0.0035:
            extra = min(abs(gap), width * 0.35)
            if gap > 0:
                hi += extra
            else:
                lo -= extra
            method = "open_locked_gap_asymmetric"
    out = _range_payload(
        open_px,
        width,
        locked=True,
        anchor="session_open",
        method=method,
        pivot=float(day_range.get("reference_pivot") or open_px),
        open_px=open_px,
        prev_close=prev_close,
    )
    out["expected_high"] = round(hi, 2)
    out["expected_low"] = round(lo, 2)
    out["session_expected_high"] = out["expected_high"]
    out["session_expected_low"] = out["expected_low"]
    out["planned_width"] = round(hi - lo, 2)
    out["method"] = method
    return out


def apply_opening_range_box(
    day_range: Dict[str, Any],
    or_high: float,
    or_low: float,
) -> Dict[str, Any]:
    """After 9:45, keep the day width but seat it on the 15m opening range."""
    width = float(day_range.get("planned_width") or 0)
    if width <= 0:
        width = float(day_range.get("session_expected_high") or day_range.get("expected_high") or 0) - float(
            day_range.get("session_expected_low") or day_range.get("expected_low") or 0
        )
    span = max(float(or_high) - float(or_low), 0.0)
    pad = span * 0.15 if span >= width else (width - span) / 2.0
    out = dict(day_range)
    out["session_expected_high"] = day_range.get("session_expected_high", day_range.get("expected_high"))
    out["session_expected_low"] = day_range.get("session_expected_low", day_range.get("expected_low"))
    out["expected_high"] = round(float(or_high) + pad, 2)
    out["expected_low"] = round(float(or_low) - pad, 2)
    out["planned_width"] = round(max(width, 1.0), 2)
    out["locked"] = True
    out["anchor"] = "opening_range"
    out["method"] = "opening_range_plus_pad"
    out["or_high"] = round(float(or_high), 2)
    out["or_low"] = round(float(or_low), 2)
    return out


def refresh_day_range(
    day_range: Dict[str, Any],
    live_quote: Optional[Dict[str, Any]] = None,
    df_15m: Any = None,
) -> Dict[str, Any]:
    """Lock on the open, then seat the box on the 15m opening range when it exists."""
    out = dict(day_range or {})
    if live_quote and live_quote.get("open"):
        try:
            out = lock_day_range_on_open(out, float(live_quote["open"]))
        except (TypeError, ValueError):
            pass
    if df_15m is not None:
        orb = detect_opening_range(df_15m, OPENING_RANGE_BARS)
        if orb.get("available"):
            out = apply_opening_range_box(out, float(orb["or_high"]), float(orb["or_low"]))
    return out


def build_reasons(
    decision: str,
    ml_proba: float,
    tech_score: float,
    signals_agree: bool,
    candle: Dict[str, Any],
    news: Dict[str, Any],
    global_lead: Dict[str, Any],
    mode: str,
    day_range: Dict[str, Any],
    structural: Optional[Dict[str, Any]] = None,
    fundamentals: Optional[Dict[str, Any]] = None,
    india_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    reasons: List[Dict[str, str]] = []

    reasons.append({
        "category": "ML",
        "text": f"Model estimates {ml_proba * 100:.1f}% chance of next meaningful up move (>0.3%).",
    })
    reasons.append({
        "category": "Technical",
        "text": f"Technical score {tech_score:.0f}/100 — trend/momentum/volume composite.",
    })
    if signals_agree:
        reasons.append({"category": "Agreement", "text": "ML and technical signals point the same way."})
    else:
        reasons.append({"category": "Agreement", "text": "ML and technical signals conflict — confidence capped."})

    for p in candle.get("patterns") or []:
        reasons.append({"category": "Candlestick", "text": p})

    if structural:
        for line in structural.get("reason_lines") or []:
            reasons.append({"category": "Structure", "text": line})

    if fundamentals and fundamentals.get("available"):
        fs = fundamentals.get("fundamental_score", 50)
        reasons.append({
            "category": "Fundamental",
            "text": f"Fundamental score {fs}/100 ({fundamentals.get('bias', 'NEUTRAL')}).",
        })
        for note in fundamentals.get("notes") or []:
            reasons.append({"category": "Fundamental", "text": note})

    for h in news.get("highlights") or []:
        reasons.append({"category": "News", "text": h})

    if global_lead.get("available"):
        parts = ", ".join(
            f"{m['name']} {m['change_pct']:+.2f}%"
            for m in global_lead.get("markets", [])[:3]
        )
        reasons.append({
            "category": "Global",
            "text": f"Overnight US lead ({global_lead.get('bias')}): {parts}.",
        })

    if india_context and india_context.get("available"):
        for line in india_market_context.india_reason_lines(india_context):
            reasons.append({"category": "India context", "text": line})

    if mode == "premarket":
        reasons.append({
            "category": "Session",
            "text": (
                f"Pre-market plan: expected range ₹{day_range['expected_low']} – "
                f"₹{day_range['expected_high']} ({day_range['session_bias']} bias)."
            ),
        })
    else:
        reasons.append({
            "category": "Session",
            "text": (
                f"Intraday: watch ₹{day_range['expected_low']} – ₹{day_range['expected_high']} "
                f"while price action develops."
            ),
        })

    if "BUY" in decision:
        reasons.append({"category": "Action", "text": "Bias favors long exposure; use stop below ATR-based level."})
    elif "SELL" in decision:
        reasons.append({"category": "Action", "text": "Bias favors reducing longs or hedging; confirm with live price."})
    else:
        reasons.append({"category": "Action", "text": "No strong edge — wait for ML/technical alignment or range break."})

    return reasons


def enrich_prediction(
    df: pd.DataFrame,
    ml_proba: float,
    tech_score: float,
    combined_score: float,
    current_price: float,
    atr_val: float,
    live_quote: Optional[Dict[str, Any]],
    news_items: List[Dict[str, Any]],
    mode: Optional[str] = None,
) -> Dict[str, Any]:
    analysis_mode = resolve_analysis_mode(mode)
    candle = detect_candlestick_patterns(df)
    news = score_news_sentiment(news_items)
    global_lead = fetch_global_lead() if analysis_mode == "premarket" else {"available": False, "score_delta": 0, "bias": "SKIPPED", "markets": []}

    tech_adj = (candle["score_delta"] / 100.0) * 0.08
    global_adj = (global_lead.get("score_delta", 0) / 100.0) * 0.05 if analysis_mode == "premarket" else 0.0
    # News tone shown in reasons; numeric nudge comes from knowledge.db rules (avoid double-count).
    combined_adjust = tech_adj + global_adj

    adjusted_tech = max(0.0, min(100.0, tech_score + candle["score_delta"] + news["score_delta"] * 0.35))

    day_range = forecast_day_range(
        df, current_price, atr_val, live_quote, analysis_mode, combined_score + combined_adjust
    )

    return {
        "mode": analysis_mode,
        "combined_adjust": round(combined_adjust, 4),
        "adjusted_technical_score": round(adjusted_tech, 1),
        "candlestick": candle,
        "news_sentiment": news,
        "global_lead": global_lead,
        "day_range_forecast": day_range,
    }
