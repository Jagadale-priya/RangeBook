"""F&O market checklist for each symbol on the F&O list (NIFTY, BANKNIFTY, SENSEX, ...).

Each item reads one input a desk trader checks before an index option trade:
futures OI buildup, full option chain (call/put OI walls, PCR), India VIX,
FII/DII cash, FII index-futures long share, 9/20/50 EMA and VWAP, RSI,
50/200 DMA, CPR, heavyweight breadth, US close, crude, USD/INR, DXY and the
opening gap.

Items lean BULLISH / BEARISH / NEUTRAL on their own. They are alerts and
context on the desk; they do not move the model cutoff, because replay has no
history for most of them yet. Snapshots are saved per 15-minute bucket so a
later replay can test them.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"

HEAVYWEIGHTS = {
    "NIFTY": ("RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS"),
    "BANKNIFTY": ("HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK"),
    "SENSEX": ("RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL"),
    "FINNIFTY": ("HDFCBANK", "ICICIBANK", "BAJFINANCE", "SBIN", "AXISBANK"),
    "BANKEX": ("HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK"),
}
BANK_HEAVY = {"BANKNIFTY", "FINNIFTY", "BANKEX"}
# ±10 strikes around spot: NIFTY 50-pt and BANKNIFTY 100-pt steps.
CHAIN_STRIKES = 21
CHAIN_BAND_FRAC = 0.03
PCR_HIGH = 1.3
PCR_LOW = 0.7
PCR_BULL = 1.1
PCR_BEAR = 0.9
VIX_HIGH = 20.0
VIX_EXTREME = 22.0
VIX_MOVE_PCT = 3.0
# Futures OI or price moves smaller than this over 30 minutes are treated as flat.
OI_FLAT_PCT = 0.10
PX_FLAT_PCT = 0.03
# CPR width as % of pivot. Width is |2C - H - L| / 3. On NIFTY 8-22 Oct 2026
# the ten sessions ran 0.09 to 0.64. A 0.20 cutoff marked eight of them wide,
# so the banner never turned off. Narrow is the quiet pair (<=0.12). Wide is
# only the days above 0.40.
CPR_NARROW_PCT = 0.12
CPR_WIDE_PCT = 0.40
FII_LONG_OVERSOLD = 25.0
FII_LONG_OVERBOUGHT = 75.0
GAP_PCT = 0.30
GLOBAL_MOVE_PCT = 0.35
LIVE_TTL_SEC = 60.0
DAILY_TTL_SEC = 3600.0
FAIL_TTL_SEC = 1800.0
FETCH_TIMEOUT_SEC = 10.0

PARTICIPANT_OI_URL = "https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_{d}.csv"
DXY_TICKER = "DX-Y.NYB"

_cache: Dict[str, Tuple[float, Any]] = {}
_cache_lock = threading.Lock()
_build_locks: Dict[str, threading.Lock] = {}


def _cached(key: str, ttl: float, fn: Callable[[], Any], fail_ttl: Optional[float] = None) -> Any:
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
    if hit and now < hit[0]:
        return hit[1]
    try:
        val = fn()
    except Exception as exc:
        val = {"available": False, "error": str(exc)}
    ok = not (isinstance(val, dict) and val.get("available") is False)
    with _cache_lock:
        _cache[key] = (now + (ttl if ok else (fail_ttl or ttl)), val)
    return val


def _f(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return (a / b - 1.0) * 100.0


def _item(key: str, group: str, label: str, value: str, lean: Optional[str], note: str = "", **extra: Any) -> Dict[str, Any]:
    return {"key": key, "group": group, "label": label, "value": value, "lean": lean, "note": note, "available": True, **extra}


def _missing(key: str, group: str, label: str, why: str) -> Dict[str, Any]:
    return {"key": key, "group": group, "label": label, "value": "—", "lean": None, "note": why, "available": False}


# --- pure reads -------------------------------------------------------------


def classify_buildup(px_chg_pct: Optional[float], oi_chg_pct: Optional[float]) -> Tuple[str, Optional[str]]:
    """Price vs futures OI over the window."""
    if px_chg_pct is None or oi_chg_pct is None:
        return "UNKNOWN", None
    if abs(oi_chg_pct) < OI_FLAT_PCT or abs(px_chg_pct) < PX_FLAT_PCT:
        return "FLAT", NEUTRAL
    if px_chg_pct > 0 and oi_chg_pct > 0:
        return "LONG_BUILDUP", BULLISH
    if px_chg_pct < 0 and oi_chg_pct > 0:
        return "SHORT_BUILDUP", BEARISH
    if px_chg_pct < 0 and oi_chg_pct < 0:
        return "LONG_UNWINDING", BEARISH
    return "SHORT_COVERING", BULLISH


BUILDUP_PLAIN = {
    "LONG_BUILDUP": "Long buildup (price up, OI up)",
    "SHORT_BUILDUP": "Short buildup (price down, OI up)",
    "LONG_UNWINDING": "Long unwinding (price down, OI down)",
    "SHORT_COVERING": "Short covering (price up, OI down)",
    "FLAT": "No clear buildup",
    "UNKNOWN": "Not enough futures bars",
}


def chain_read(rows: List[Dict[str, Any]], spot: float) -> Dict[str, Any]:
    """rows: {strike, type CE/PE, oi}. Highest call OI = ceiling, highest put OI = floor."""
    ce = [(float(r["strike"]), float(r.get("oi") or 0)) for r in rows if r.get("type") == "CE"]
    pe = [(float(r["strike"]), float(r.get("oi") or 0)) for r in rows if r.get("type") == "PE"]
    ce_tot = sum(o for _, o in ce)
    pe_tot = sum(o for _, o in pe)
    if ce_tot <= 0 or pe_tot <= 0:
        return {"available": False, "error": "no option OI in chain"}
    call_wall = max(ce, key=lambda x: x[1])[0]
    put_wall = max(pe, key=lambda x: x[1])[0]
    pcr = pe_tot / ce_tot
    return {
        "available": True,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "pcr_total": round(pcr, 3),
        "ce_oi_total": ce_tot,
        "pe_oi_total": pe_tot,
        "strikes": len({s for s, _ in ce} | {s for s, _ in pe}),
        "spot": spot,
    }


def pcr_lean(pcr: Optional[float]) -> Tuple[Optional[str], str]:
    if pcr is None:
        return None, ""
    if pcr >= PCR_HIGH:
        return BULLISH, f"PCR {pcr:.2f} is above {PCR_HIGH} — bullish but stretched; profit-booking risk."
    if pcr <= PCR_LOW:
        return BEARISH, f"PCR {pcr:.2f} is below {PCR_LOW} — bearish but stretched; short-covering bounce risk."
    if pcr >= PCR_BULL:
        return BULLISH, ""
    if pcr <= PCR_BEAR:
        return BEARISH, ""
    return NEUTRAL, ""


def ema_read(close: pd.Series) -> Dict[str, Any]:
    if close is None or len(close) < 20:
        return {"available": False}
    e9 = close.ewm(span=9, adjust=False).mean()
    e20 = close.ewm(span=20, adjust=False).mean()
    e50 = close.ewm(span=50, adjust=False).mean() if len(close) >= 50 else None
    px = float(close.iloc[-1])
    a, b = float(e9.iloc[-1]), float(e20.iloc[-1])
    if px > a > b:
        lean = BULLISH
    elif px < a < b:
        lean = BEARISH
    else:
        lean = NEUTRAL
    cross = None
    if len(e9) >= 3:
        prev_diff = float(e9.iloc[-3] - e20.iloc[-3])
        now_diff = a - b
        if prev_diff <= 0 < now_diff:
            cross = "9 EMA crossed above 20 EMA"
        elif prev_diff >= 0 > now_diff:
            cross = "9 EMA crossed below 20 EMA"
    return {
        "available": True,
        "ema9": round(a, 2),
        "ema20": round(b, 2),
        "ema50": None if e50 is None else round(float(e50.iloc[-1]), 2),
        "lean": lean,
        "cross": cross,
    }


def rsi(close: pd.Series, period: int = 14) -> Optional[float]:
    if close is None or len(close) < period + 1:
        return None
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    val = float((100 - 100 / (1 + rs)).iloc[-1])
    return round(val, 1) if math.isfinite(val) else None


def rsi_lean(val: Optional[float]) -> Optional[str]:
    if val is None:
        return None
    if val >= 60:
        return BULLISH
    if val <= 40:
        return BEARISH
    return NEUTRAL


def cpr(prev_high: float, prev_low: float, prev_close: float) -> Dict[str, Any]:
    p = (prev_high + prev_low + prev_close) / 3.0
    bc = (prev_high + prev_low) / 2.0
    tc = 2 * p - bc
    top, bot = max(tc, bc), min(tc, bc)
    width_pct = (top - bot) / p * 100.0 if p else 0.0
    kind = "NARROW" if width_pct <= CPR_NARROW_PCT else ("WIDE" if width_pct >= CPR_WIDE_PCT else "NORMAL")
    return {
        "pivot": round(p, 2),
        "tc": round(top, 2),
        "bc": round(bot, 2),
        "width_pct": round(width_pct, 3),
        "kind": kind,
        "r1": round(2 * p - prev_low, 2),
        "s1": round(2 * p - prev_high, 2),
        "r2": round(p + (prev_high - prev_low), 2),
        "s2": round(p - (prev_high - prev_low), 2),
    }


def session_vwap(bars: pd.DataFrame) -> Optional[float]:
    if bars is None or not len(bars) or "Volume" not in bars.columns:
        return None
    vol = bars["Volume"].astype(float)
    if float(vol.sum()) <= 0:
        return None
    tp = (bars["High"].astype(float) + bars["Low"].astype(float) + bars["Close"].astype(float)) / 3.0
    return float((tp * vol).sum() / vol.sum())


def parse_participant_oi(text: str) -> Optional[Dict[str, float]]:
    """NSE fao_participant_oi CSV -> FII index futures long / short contracts."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    start = next((i for i, ln in enumerate(lines) if ln.lower().startswith("client type")), None)
    if start is None:
        return None
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    for row in reader:
        clean = {str(k).strip().lower(): v for k, v in row.items() if k}
        if str(clean.get("client type") or "").strip().upper() != "FII":
            continue
        long_v = _f(str(clean.get("future index long") or "").replace(",", ""))
        short_v = _f(str(clean.get("future index short") or "").replace(",", ""))
        if long_v is None or short_v is None or long_v + short_v <= 0:
            return None
        return {"long": long_v, "short": short_v, "long_pct": round(long_v / (long_v + short_v) * 100.0, 1)}
    return None


def _move_lean(chg: Optional[float], invert: bool = False) -> Optional[str]:
    if chg is None:
        return None
    signed = -chg if invert else chg
    if signed >= GLOBAL_MOVE_PCT:
        return BULLISH
    if signed <= -GLOBAL_MOVE_PCT:
        return BEARISH
    return NEUTRAL


# --- fetches ----------------------------------------------------------------


def _norm_bars(df: Any) -> Optional[pd.DataFrame]:
    if df is None or not len(df):
        return None
    out = df.copy()
    cols = {str(c).lower(): c for c in out.columns}
    for src, dst in (("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close"), ("volume", "Volume"), ("oi", "OI")):
        if dst not in out.columns and src in cols:
            out[dst] = out[cols[src]]
    return out.sort_index()


def _today_rows(df: pd.DataFrame) -> pd.DataFrame:
    last_day = pd.Timestamp(df.index[-1]).date()
    return df[[pd.Timestamp(i).date() == last_day for i in df.index]]


def fetch_future_bars(symbol: str, spot: float) -> Dict[str, Any]:
    import fno_instruments
    import kite_data

    contracts = fno_instruments.resolve_contracts(symbol, spot)
    fut = (contracts or {}).get("future") or {}
    sym = fut.get("tradingsymbol")
    if not sym:
        return {"available": False, "error": (contracts or {}).get("error") or "no future contract"}
    quote, err = kite_data.fetch_exchange_quote(fut.get("exchange") or "NFO", sym)
    token = (quote or {}).get("instrument_token")
    if not token:
        return {"available": False, "error": err or "no future token"}
    kite, kerr = kite_data._get_kite()
    if kerr or not kite:
        return {"available": False, "error": kerr or "Kite not connected"}
    to_d = datetime.now()
    candles = kite.historical_data(int(token), to_d - timedelta(days=5), to_d, interval="15minute", oi=True)
    if not candles:
        return {"available": False, "error": "no futures candles"}
    df = pd.DataFrame(candles)
    df["date"] = pd.to_datetime(df["date"])
    df = _norm_bars(df.set_index("date"))
    return {"available": True, "tradingsymbol": sym, "bars": df, "quote_oi": _f((quote or {}).get("oi"))}


def futures_oi_item(fut: Dict[str, Any]) -> Dict[str, Any]:
    if not fut.get("available"):
        return _missing("futures_oi", "derivatives", "Futures OI buildup", fut.get("error") or "unavailable")
    bars = fut["bars"]
    if "OI" not in bars.columns or len(bars) < 3:
        return _missing("futures_oi", "derivatives", "Futures OI buildup", "no OI on futures bars")
    close = bars["Close"].astype(float)
    oi = bars["OI"].astype(float)
    px_chg = _pct(float(close.iloc[-1]), float(close.iloc[-3]))
    oi_chg = _pct(float(oi.iloc[-1]), float(oi.iloc[-3]))
    state, lean = classify_buildup(px_chg, oi_chg)
    today = _today_rows(bars)
    day_state = None
    if len(today) >= 2:
        day_state, _ = classify_buildup(
            _pct(float(today["Close"].iloc[-1]), float(today["Open"].iloc[0])),
            _pct(float(today["OI"].iloc[-1]), float(today["OI"].iloc[0])),
        )
    value = BUILDUP_PLAIN[state]
    note = f"Last 30 min: price {px_chg:+.2f}%, OI {oi_chg:+.2f}%." if px_chg is not None and oi_chg is not None else ""
    if day_state and day_state not in ("FLAT", "UNKNOWN"):
        note += f" Since open: {BUILDUP_PLAIN[day_state].split(' (')[0].lower()}."
    return _item("futures_oi", "derivatives", "Futures OI buildup", value, lean, note.strip(), state=state, day_state=day_state,
                 contract=fut.get("tradingsymbol"))


def vwap_item(fut: Dict[str, Any]) -> Dict[str, Any]:
    """Index spot has no volume on Kite, so VWAP is read from the near-month future."""
    if not fut.get("available"):
        return _missing("vwap", "technical", "VWAP (futures)", fut.get("error") or "unavailable")
    today = _today_rows(fut["bars"])
    vw = session_vwap(today)
    if vw is None:
        return _missing("vwap", "technical", "VWAP (futures)", "no futures volume today")
    last = float(today["Close"].iloc[-1])
    diff = (last / vw - 1) * 100.0
    lean = BULLISH if diff > 0.05 else (BEARISH if diff < -0.05 else NEUTRAL)
    side = "above" if diff >= 0 else "below"
    return _item("vwap", "technical", "VWAP (futures)", f"Future {side} VWAP by {abs(diff):.2f}%", lean,
                 f"Future {last:.1f} vs VWAP {vw:.1f}.", vwap=round(vw, 2))


def fetch_chain(symbol: str, spot: float) -> Dict[str, Any]:
    import fno_instruments
    import kite_data

    chain = fno_instruments.list_option_chain(symbol, spot, band_frac=CHAIN_BAND_FRAC, max_strikes=CHAIN_STRIKES)
    if not chain.get("available"):
        return {"available": False, "error": chain.get("error")}
    quotes, err = kite_data.quote_many(chain["quote_keys"])
    if not quotes:
        return {"available": False, "error": err or "no chain quotes"}
    rows = []
    for r in chain["rows"]:
        q = quotes.get(fno_instruments.quote_key(r)) or {}
        rows.append({"strike": r.get("strike"), "type": r.get("instrument_type"), "oi": q.get("oi") or 0})
    read = chain_read(rows, spot)
    read["expiry"] = chain.get("expiry")
    return read


def chain_items(read: Dict[str, Any], spot: float) -> List[Dict[str, Any]]:
    if not read.get("available"):
        why = read.get("error") or "unavailable"
        return [
            _missing("pcr", "derivatives", "PCR (±10 strikes)", why),
            _missing("oi_walls", "derivatives", "Call / put OI walls", why),
        ]
    pcr = read["pcr_total"]
    lean, stretch = pcr_lean(pcr)
    ceiling, floor = read["call_wall"], read["put_wall"]
    to_ceiling = (ceiling - spot) / spot * 100.0
    to_floor = (spot - floor) / spot * 100.0
    if to_ceiling < 0:
        wall_lean, wall_note = BULLISH, f"Price is above the call-OI ceiling {ceiling:.0f} — call writers under pressure."
    elif to_floor < 0:
        wall_lean, wall_note = BEARISH, f"Price is below the put-OI floor {floor:.0f} — put writers under pressure."
    elif to_ceiling < to_floor * 0.5:
        wall_lean, wall_note = BEARISH, f"Closer to the ceiling ({to_ceiling:.2f}% away) than the floor ({to_floor:.2f}%)."
    elif to_floor < to_ceiling * 0.5:
        wall_lean, wall_note = BULLISH, f"Closer to the floor ({to_floor:.2f}% away) than the ceiling ({to_ceiling:.2f}%)."
    else:
        wall_lean, wall_note = NEUTRAL, f"Ceiling {to_ceiling:.2f}% up, floor {to_floor:.2f}% down."
    return [
        _item("pcr", "derivatives", "PCR (±10 strikes)", f"{pcr:.2f}", lean,
              stretch or f"Put OI / call OI across {read['strikes']} strikes, expiry {read.get('expiry')}.",
              pcr=pcr, stretched=bool(stretch)),
        _item("oi_walls", "derivatives", "Call / put OI walls", f"Ceiling {ceiling:.0f} · Floor {floor:.0f}", wall_lean, wall_note,
              call_wall=ceiling, put_wall=floor),
    ]


def fetch_quotes(symbol: str) -> Dict[str, Any]:
    import kite_data

    ids = [kite_data.kite_instrument_id(symbol), "NSE:INDIA VIX"] + [f"NSE:{s}" for s in HEAVYWEIGHTS.get(symbol, ())]
    quotes, err = kite_data.quote_many(ids)
    if not quotes:
        return {"available": False, "error": err or "no quotes"}
    return {"available": True, "quotes": quotes, "index_id": ids[0]}


def _chg(q: Dict[str, Any], base: str) -> Optional[float]:
    last = _f(q.get("last_price"))
    ref = _f((q.get("ohlc") or {}).get(base))
    return _pct(last, ref)


def index_items(qs: Dict[str, Any], symbol: str) -> List[Dict[str, Any]]:
    if not qs.get("available"):
        why = qs.get("error") or "unavailable"
        return [
            _missing("india_vix", "derivatives", "India VIX", why),
            _missing("heavyweights", "inter_market", "Heavyweights", why),
            _missing("gap", "global", "Opening gap", why),
        ]
    quotes = qs["quotes"]
    idx = quotes.get(qs["index_id"]) or {}
    idx_chg = _chg(idx, "close")
    out: List[Dict[str, Any]] = []

    vix = quotes.get("NSE:INDIA VIX") or {}
    vix_lvl = _f(vix.get("last_price"))
    vix_chg = _chg(vix, "close")
    if vix_lvl is None:
        out.append(_missing("india_vix", "derivatives", "India VIX", "no VIX quote"))
    else:
        lean, note = NEUTRAL, ""
        if vix_chg is not None and idx_chg is not None:
            if vix_chg >= VIX_MOVE_PCT and idx_chg < 0:
                lean, note = BEARISH, "VIX rising while the index falls — confirms selling pressure."
            elif vix_chg <= -VIX_MOVE_PCT and idx_chg > 0:
                lean, note = BULLISH, "VIX falling while the index rises — steady bullish tape."
        if vix_lvl >= VIX_HIGH:
            note = (note + " " if note else "") + f"VIX {vix_lvl:.1f} — option premiums are inflated and can crash fast."
        out.append(_item("india_vix", "derivatives", "India VIX",
                         f"{vix_lvl:.2f} ({vix_chg:+.1f}%)" if vix_chg is not None else f"{vix_lvl:.2f}",
                         lean, note, level=vix_lvl, change_pct=vix_chg))

    names = HEAVYWEIGHTS.get(symbol, ())
    ups, downs, parts = 0, 0, []
    for name in names:
        q = quotes.get(f"NSE:{name}") or {}
        c = _chg(q, "open")
        if c is None:
            continue
        parts.append(f"{name} {c:+.2f}%")
        if c > 0.05:
            ups += 1
        elif c < -0.05:
            downs += 1
    seen = len(parts)
    if not seen:
        out.append(_missing("heavyweights", "inter_market", "Heavyweights", "no stock quotes"))
    else:
        lean = BULLISH if ups >= 4 else (BEARISH if downs >= 4 else NEUTRAL)
        out.append(_item("heavyweights", "inter_market", "Heavyweights vs open", f"{ups} up · {downs} down of {seen}", lean,
                         ", ".join(parts), ups=ups, downs=downs))

    gap = _pct(_f((idx.get("ohlc") or {}).get("open")), _f((idx.get("ohlc") or {}).get("close")))
    if gap is None:
        out.append(_missing("gap", "global", "Opening gap", "no index open"))
    else:
        lean = BULLISH if gap >= GAP_PCT else (BEARISH if gap <= -GAP_PCT else NEUTRAL)
        out.append(_item("gap", "global", "Opening gap", f"{gap:+.2f}% vs prior close", lean,
                         "Kite has no GIFT Nifty feed; this is the actual cash open vs prior close.", gap_pct=round(gap, 2)))
    return out


def fetch_daily(symbol: str) -> Dict[str, Any]:
    import kite_data

    df, err = kite_data.fetch_daily_ohlcv(symbol, years=1.3)
    if df is None:
        return {"available": False, "error": err}
    return {"available": True, "bars": _norm_bars(df)}


def daily_items(daily: Dict[str, Any], price: float) -> List[Dict[str, Any]]:
    if not daily.get("available"):
        why = daily.get("error") or "unavailable"
        return [
            _missing("dma", "technical", "50 / 200 DMA", why),
            _missing("rsi_daily", "technical", "RSI daily", why),
            _missing("cpr", "technical", "CPR", why),
        ]
    df = daily["bars"]
    today = date.today()
    prior = df[[pd.Timestamp(i).date() < today for i in df.index]]
    close = prior["Close"].astype(float)
    out: List[Dict[str, Any]] = []
    if len(close) >= 200:
        d50 = float(close.rolling(50).mean().iloc[-1])
        d200 = float(close.rolling(200).mean().iloc[-1])
        if price > d50 and price > d200:
            lean = BULLISH
        elif price < d50 and price < d200:
            lean = BEARISH
        else:
            lean = NEUTRAL
        out.append(_item("dma", "technical", "50 / 200 DMA", f"50 DMA {d50:.0f} · 200 DMA {d200:.0f}", lean,
                         f"Price {'above' if price > d200 else 'below'} the 200 DMA.", dma50=round(d50, 2), dma200=round(d200, 2)))
    else:
        out.append(_missing("dma", "technical", "50 / 200 DMA", "fewer than 200 daily bars"))
    r = rsi(pd.concat([close, pd.Series([price])], ignore_index=True))
    note = "Overbought above 70." if r is not None and r >= 70 else ("Oversold below 30." if r is not None and r <= 30 else "")
    out.append(_item("rsi_daily", "technical", "RSI daily", "—" if r is None else f"{r:.1f}", rsi_lean(r), note, rsi=r)
               if r is not None else _missing("rsi_daily", "technical", "RSI daily", "not enough bars"))
    if len(prior):
        last = prior.iloc[-1]
        c = cpr(float(last["High"]), float(last["Low"]), float(last["Close"]))
        lean = BULLISH if price > c["tc"] else (BEARISH if price < c["bc"] else NEUTRAL)
        kind_note = {
            "NARROW": "Narrow CPR — trending or volatile day likely.",
            "WIDE": "Wide CPR — sideways, range-bound day likely.",
            "NORMAL": "",
        }[c["kind"]]
        out.append(_item("cpr", "technical", "CPR", f"{c['kind'].title()} ({c['width_pct']:.2f}%) · BC {c['bc']:.0f} – TC {c['tc']:.0f}",
                         lean, (kind_note + f" R1 {c['r1']:.0f} · S1 {c['s1']:.0f}.").strip(), **c))
    else:
        out.append(_missing("cpr", "technical", "CPR", "no prior session"))
    return out


def intraday_items(bars: Any, price: float) -> List[Dict[str, Any]]:
    work = _norm_bars(bars)
    if work is None or len(work) < 20:
        return [
            _missing("ema", "technical", "9 / 20 / 50 EMA (15m)", "not enough 15m bars"),
            _missing("rsi_15m", "technical", "RSI 15m", "not enough 15m bars"),
        ]
    close = work["Close"].astype(float)
    e = ema_read(close)
    value = f"9 EMA {e['ema9']:.0f} · 20 EMA {e['ema20']:.0f}" + (f" · 50 EMA {e['ema50']:.0f}" if e.get("ema50") else "")
    out = [_item("ema", "technical", "9 / 20 / 50 EMA (15m)", value, e["lean"], e.get("cross") or "", **{k: e[k] for k in ("ema9", "ema20", "ema50")})]
    r = rsi(close)
    note = "Overbought above 70." if r is not None and r >= 70 else ("Oversold below 30." if r is not None and r <= 30 else "")
    out.append(_item("rsi_15m", "technical", "RSI 15m", "—" if r is None else f"{r:.1f}", rsi_lean(r), note, rsi=r))
    return out


def fetch_fii_long_share() -> Dict[str, Any]:
    import requests
    import nse_session

    sess = nse_session.nse_session()
    getter = sess.get if sess is not None else requests.get
    headers = None if sess is not None else {"User-Agent": nse_session.USER_AGENT}
    found: List[Tuple[date, Dict[str, float]]] = []
    day = date.today()
    for _ in range(10):
        if day.weekday() < 5:
            url = PARTICIPANT_OI_URL.format(d=day.strftime("%d%m%Y"))
            try:
                r = getter(url, timeout=6, headers=headers) if headers else getter(url, timeout=6)
                if r.status_code == 200 and "client type" in r.text.lower():
                    parsed = parse_participant_oi(r.text)
                    if parsed:
                        found.append((day, parsed))
                        if len(found) == 2:
                            break
            except Exception:
                pass
        day -= timedelta(days=1)
    if not found:
        return {"available": False, "error": "NSE participant OI file not reachable"}
    latest_day, latest = found[0]
    prev = found[1][1] if len(found) > 1 else None
    return {
        "available": True,
        "date": latest_day.isoformat(),
        "long_pct": latest["long_pct"],
        "prev_long_pct": prev["long_pct"] if prev else None,
        "long": latest["long"],
        "short": latest["short"],
    }


def fii_items(fii_cash: Dict[str, Any], fii_fut: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if fii_cash.get("available") and fii_cash.get("flows"):
        flows = {str(r.get("category") or "").upper(): r for r in fii_cash["flows"]}
        fii = next((v for k, v in flows.items() if "FII" in k or "FPI" in k), None)
        dii = next((v for k, v in flows.items() if "DII" in k and "FII" not in k), None)
        net = _f((fii or {}).get("net_value_cr"))
        lean = BULLISH if net is not None and net > 500 else (BEARISH if net is not None and net < -500 else NEUTRAL)
        value = (f"FII ₹{net:,.0f} Cr" if net is not None else "FII —") + (
            f" · DII ₹{float(dii['net_value_cr']):,.0f} Cr" if dii and dii.get("net_value_cr") is not None else ""
        )
        note = f"Provisional figures for {(fii or {}).get('date') or 'last session'}."
        out.append(_item("fii_cash", "institutional", "FII / DII cash", value, lean, note, fii_net_cr=net))
    else:
        out.append(_missing("fii_cash", "institutional", "FII / DII cash", fii_cash.get("error") or "unavailable"))
    if fii_fut.get("available"):
        pct = float(fii_fut["long_pct"])
        prev = fii_fut.get("prev_long_pct")
        note = ""
        if pct <= FII_LONG_OVERSOLD:
            lean, note = BULLISH, f"FII long share {pct:.0f}% — very short; market oversold and prone to a bounce."
        elif pct >= FII_LONG_OVERBOUGHT:
            lean, note = BEARISH, f"FII long share {pct:.0f}% — very long; market overbought and prone to a correction."
        elif prev is not None and pct - float(prev) >= 2:
            lean = BULLISH
        elif prev is not None and float(prev) - pct >= 2:
            lean = BEARISH
        else:
            lean = NEUTRAL
        change = f" ({pct - float(prev):+.1f} pts)" if prev is not None else ""
        out.append(_item("fii_futures", "institutional", "FII index futures long share", f"{pct:.1f}% long{change}", lean,
                         note or f"NSE participant OI for {fii_fut.get('date')}.", long_pct=pct, stretched=bool(note)))
    else:
        out.append(_missing("fii_futures", "institutional", "FII index futures long share", fii_fut.get("error") or "unavailable"))
    return out


def fetch_global() -> Dict[str, Any]:
    import analysis_engine

    panel = analysis_engine.fetch_global_overnight_panel()
    dxy = _cached("dxy", 900.0, lambda: analysis_engine._one_overnight(DXY_TICKER, "DXY", 0.7, True) or {"available": False})
    return {"available": bool(panel.get("available")), "panel": panel, "dxy": dxy}


def global_items(glob: Dict[str, Any], symbol: str) -> List[Dict[str, Any]]:
    panel = glob.get("panel") or {}
    markets = {m.get("symbol"): m for m in panel.get("markets") or []}
    out: List[Dict[str, Any]] = []
    us = [markets.get(t) for t in ("^GSPC", "^IXIC", "^DJI") if markets.get(t)]
    if us:
        avg = sum(float(m["change_pct"]) for m in us) / len(us)
        out.append(_item("us_markets", "global", "US close (S&P · Nasdaq · Dow)",
                         " · ".join(f"{m['name']} {float(m['change_pct']):+.2f}%" for m in us), _move_lean(avg),
                         f"Last US session ({us[0].get('bar_date')}).", avg_pct=round(avg, 2)))
    else:
        out.append(_missing("us_markets", "global", "US close", "global panel unavailable"))
    macro_rows = [("CL=F", "Crude"), ("INR=X", "USD/INR")]
    parts, score = [], 0.0
    bank = symbol in BANK_HEAVY
    for tick, name in macro_rows:
        m = markets.get(tick)
        if m:
            parts.append(f"{name} {float(m['change_pct']):+.2f}%")
            score -= float(m["change_pct"]) * (1.2 if bank else 1.0)
    dxy = glob.get("dxy") or {}
    if dxy.get("change_pct") is not None:
        parts.append(f"DXY {float(dxy['change_pct']):+.2f}%")
        score -= float(dxy["change_pct"]) * (1.2 if bank else 1.0)
    if parts:
        note = "Rising crude, rupee weakness or a stronger dollar weigh on India" + (", banks most." if bank else ".")
        out.append(_item("macro", "global", "Crude · USD/INR · DXY", " · ".join(parts), _move_lean(score / max(len(parts), 1)), note))
    else:
        out.append(_missing("macro", "global", "Crude · USD/INR · DXY", "macro quotes unavailable"))
    return out


# --- assemble ---------------------------------------------------------------


GROUP_ORDER = ("derivatives", "institutional", "technical", "inter_market", "global")
GROUP_TITLE = {
    "derivatives": "F&O derivatives",
    "institutional": "Institutional",
    "technical": "Technicals",
    "inter_market": "Inter-market",
    "global": "Global & open",
}


def summarize(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    bull = [i["label"] for i in items if i.get("lean") == BULLISH]
    bear = [i["label"] for i in items if i.get("lean") == BEARISH]
    seen = [i for i in items if i.get("available")]
    lean = NEUTRAL
    if len(bull) >= len(bear) + 2:
        lean = BULLISH
    elif len(bear) >= len(bull) + 2:
        lean = BEARISH
    return {"bullish": len(bull), "bearish": len(bear), "neutral": len(seen) - len(bull) - len(bear),
            "available": len(seen), "total": len(items), "lean": lean}


def standing_alerts(items: List[Dict[str, Any]]) -> List[str]:
    """Alerts that hold whatever the call side is."""
    by = {i["key"]: i for i in items if i.get("available")}
    notes: List[str] = []
    vix = by.get("india_vix") or {}
    if (vix.get("level") or 0) >= VIX_EXTREME:
        notes.append(f"India VIX {vix['level']:.1f} — above {VIX_EXTREME:.0f}, premiums are inflated and can collapse fast.")
    elif (vix.get("level") or 0) >= VIX_HIGH:
        notes.append(f"India VIX {vix['level']:.1f} — above {VIX_HIGH:.0f}, option premiums are rich.")
    it = by.get("pcr") or {}
    if it.get("stretched") and it.get("note"):
        notes.append(it["note"])
    for key in ("rsi_15m", "rsi_daily"):
        it = by.get(key) or {}
        r = it.get("rsi")
        if r is not None and (r >= 70 or r <= 30):
            notes.append(f"{it['label']} {r:.0f} — {'overbought' if r >= 70 else 'oversold'}.")
    return notes


def _save(symbol: str, payload: Dict[str, Any]) -> None:
    try:
        import chain_flow
        import knowledge_db

        path = knowledge_db.ensure_db_dir()
        conn = sqlite3.connect(path)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS fno_indications (
                stock TEXT NOT NULL, bar_ts TEXT NOT NULL, session_date TEXT NOT NULL,
                payload_json TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (stock, bar_ts))"""
        )
        bucket = chain_flow.bar_bucket()
        slim = {"items": [{k: v for k, v in i.items() if k != "note"} for i in payload["items"]], "summary": payload["summary"]}
        conn.execute(
            "INSERT OR REPLACE INTO fno_indications VALUES (?, ?, ?, ?, ?)",
            (symbol, bucket, bucket[:10], json.dumps(slim, default=str), datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _fii_cash(india_ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Always go through the 5-minute FII read. A carried copy can be a failed fetch."""
    import india_market_context

    return india_market_context.fetch_fii_dii()


def build(symbol: str, *, bars: Any = None, price: Optional[float] = None, india_ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Full checklist for any symbol on the F&O list. Cached for LIVE_TTL_SEC per symbol."""
    import fno_universe

    sym = str(symbol or "").strip().upper()
    if not fno_universe.contains(sym):
        return {"available": False, "error": f"{sym} is not on the F&O list."}
    px = _f(price)
    if not px:
        return last(sym) or {"available": False, "error": "no price"}
    key = f"build:{sym}"
    with _cache_lock:
        hit = _cache.get(key)
        lock = _build_locks.setdefault(sym, threading.Lock())
    if hit and time.time() < hit[0]:
        return hit[1]
    if not lock.acquire(blocking=False):
        return last(sym) or {"available": False, "error": "checklist is refreshing"}
    try:
        import india_market_context

        today = date.today().isoformat()
        jobs = {
            "fut": lambda: fetch_future_bars(sym, px),
            "chain": lambda: fetch_chain(sym, px),
            "quotes": lambda: fetch_quotes(sym),
            "daily": lambda: _cached(f"daily:{sym}:{today}", DAILY_TTL_SEC, lambda: fetch_daily(sym), FAIL_TTL_SEC / 6),
            "fii_cash": lambda: _fii_cash(india_ctx),
            "fii_fut": lambda: _cached(f"fii_fut:{today}", DAILY_TTL_SEC * 3, fetch_fii_long_share, FAIL_TTL_SEC),
            "global": lambda: _cached("global", 900.0, fetch_global, FAIL_TTL_SEC / 3),
        }
        got: Dict[str, Any] = {}
        pool = ThreadPoolExecutor(max_workers=len(jobs))
        futs = {name: pool.submit(fn) for name, fn in jobs.items()}
        deadline = time.time() + FETCH_TIMEOUT_SEC
        for name, fut in futs.items():
            try:
                got[name] = fut.result(timeout=max(0.1, deadline - time.time())) or {"available": False}
            except Exception as exc:
                got[name] = {"available": False, "error": f"{type(exc).__name__} {exc}".strip()[:160] or "timed out"}
        pool.shutdown(wait=False, cancel_futures=True)
        items: List[Dict[str, Any]] = []
        items.append(futures_oi_item(got["fut"]))
        items.extend(chain_items(got["chain"], px))
        idx_items = index_items(got["quotes"], sym)
        items.append(next(i for i in idx_items if i["key"] == "india_vix"))
        items.extend(fii_items(got["fii_cash"], got["fii_fut"]))
        spot_bars = _norm_bars(bars)
        if (spot_bars is None or len(spot_bars) < 20) and got["fut"].get("available"):
            spot_bars = got["fut"]["bars"]
        items.extend(intraday_items(spot_bars, px))
        items.append(vwap_item(got["fut"]))
        items.extend(daily_items(got["daily"], px))
        items.extend(i for i in idx_items if i["key"] in ("heavyweights", "gap"))
        items.extend(global_items(got["global"], sym))
        chain = got["chain"] if got["chain"].get("available") else {}
        payload = {
            "available": True,
            "symbol": sym,
            "asof": datetime.now().isoformat(timespec="seconds"),
            "price": px,
            "items": items,
            "groups": [{"key": g, "title": GROUP_TITLE[g]} for g in GROUP_ORDER],
            "summary": summarize(items),
            "alerts": standing_alerts(items),
            "call_wall": chain.get("call_wall"),
            "put_wall": chain.get("put_wall"),
            "policy": "Checklist items are alerts and context. They do not hide or flip the model call.",
        }
        with _cache_lock:
            _cache[key] = (time.time() + LIVE_TTL_SEC, payload)
            _cache[f"last:{sym}"] = (float("inf"), payload)
        _save(sym, payload)
        return payload
    finally:
        lock.release()


def last(symbol: str) -> Optional[Dict[str, Any]]:
    with _cache_lock:
        hit = _cache.get(f"last:{str(symbol or '').strip().upper()}")
    return hit[1] if hit else None


def call_alerts(indications: Optional[Dict[str, Any]], decision: str, *, price: Optional[float], target_1: Optional[float]) -> List[str]:
    """Checklist notes against a printed call: items that oppose it and OI walls in the target path."""
    ind = indications or {}
    if not ind.get("available") or decision in (None, "HOLD"):
        return []
    bull = "BUY" in str(decision)
    against = BEARISH if bull else BULLISH
    side = "BUY" if bull else "SELL"
    opp = [i for i in ind.get("items") or [] if i.get("lean") == against]
    notes: List[str] = []
    if opp:
        names = ", ".join(f"{i['label']} ({i['value']})" for i in opp[:6])
        notes.append(f"Checklist against this {side} — {len(opp)} item{'s' if len(opp) > 1 else ''}: {names}.")
    px, t1 = _f(price), _f(target_1)
    wall = _f(ind.get("call_wall") if bull else ind.get("put_wall"))
    if px and t1 and wall:
        if bull and px < wall <= t1:
            notes.append(f"Call-OI ceiling {wall:.0f} sits before the first target {t1:.0f} — sellers defend that strike.")
        elif not bull and t1 <= wall < px:
            notes.append(f"Put-OI floor {wall:.0f} sits before the first target {t1:.0f} — writers defend that strike.")
    return notes
