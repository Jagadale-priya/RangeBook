"""Binance public market data — free, no API key.

Uses market-data-only host for accurate BTC/alt 1m klines + LTP.
  REST: https://data-api.binance.vision
  WS:   wss://data-stream.binance.vision/ws/<symbol>@kline_1m
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

BASE = "https://data-api.binance.vision"
_KLINE_CACHE: Dict[str, Tuple[float, Optional[pd.DataFrame], Optional[str]]] = {}
_KLINE_TTL = 20.0

# Top liquid USDT pairs people commonly scalp/trade
TOP10_CRYPTO: List[Dict[str, str]] = [
    {"key": "BTCUSDT", "symbol": "BTCUSDT", "display": "Bitcoin", "base": "BTC"},
    {"key": "ETHUSDT", "symbol": "ETHUSDT", "display": "Ethereum", "base": "ETH"},
    {"key": "BNBUSDT", "symbol": "BNBUSDT", "display": "BNB", "base": "BNB"},
    {"key": "SOLUSDT", "symbol": "SOLUSDT", "display": "Solana", "base": "SOL"},
    {"key": "XRPUSDT", "symbol": "XRPUSDT", "display": "XRP", "base": "XRP"},
    {"key": "DOGEUSDT", "symbol": "DOGEUSDT", "display": "Dogecoin", "base": "DOGE"},
    {"key": "ADAUSDT", "symbol": "ADAUSDT", "display": "Cardano", "base": "ADA"},
    {"key": "AVAXUSDT", "symbol": "AVAXUSDT", "display": "Avalanche", "base": "AVAX"},
    {"key": "LINKUSDT", "symbol": "LINKUSDT", "display": "Chainlink", "base": "LINK"},
    {"key": "DOTUSDT", "symbol": "DOTUSDT", "display": "Polkadot", "base": "DOT"},
]

_TOP_KEYS = {r["key"] for r in TOP10_CRYPTO}
_TOP_BASE = {r["base"]: r for r in TOP10_CRYPTO}


def is_crypto_symbol(raw: str) -> bool:
    s = str(raw or "").strip().upper().replace("-", "").replace("/", "").replace(" ", "")
    if not s:
        return False
    if s in _TOP_KEYS or s in _TOP_BASE:
        return True
    if s.endswith("USDT") and len(s) >= 6:
        return True
    if s in ("BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT", "BITCOIN", "ETHEREUM"):
        return True
    return False


def resolve_crypto(raw: str) -> Dict[str, Any]:
    s = str(raw or "").strip().upper().replace("-", "").replace("/", "").replace(" ", "")
    aliases = {
        "BITCOIN": "BTC",
        "ETHEREUM": "ETH",
        "BTCUSD": "BTCUSDT",
        "ETHUSD": "ETHUSDT",
    }
    s = aliases.get(s, s)
    if s in _TOP_BASE:
        row = _TOP_BASE[s]
    elif s in _TOP_KEYS:
        row = next(r for r in TOP10_CRYPTO if r["key"] == s)
    elif s.endswith("USDT"):
        base = s[:-4]
        row = {"key": s, "symbol": s, "display": base, "base": base}
    else:
        sym = f"{s}USDT"
        row = {"key": sym, "symbol": sym, "display": s, "base": s}
    return {
        "ok": True,
        "key": row["key"],
        "kind": "crypto",
        "market": "crypto",
        "exchange": "BINANCE",
        "tradingsymbol": row["symbol"],
        "display": f"{row['display']} ({row['symbol']})",
        "underlying": row["base"],
        "instrument_type": "CRYPTO",
        "symbol": row["symbol"],
    }


def list_top10() -> List[Dict[str, Any]]:
    return [
        {
            "key": r["key"],
            "display": f"{r['display']} · {r['symbol']}",
            "base": r["base"],
            "symbol": r["symbol"],
            "kind": "crypto",
            "market": "crypto",
            "instrument_type": "CRYPTO",
        }
        for r in TOP10_CRYPTO
    ]


def search_crypto(query: str, *, limit: int = 12) -> Dict[str, Any]:
    q = str(query or "").strip().upper()
    rows = list_top10()
    if q:
        rows = [
            r
            for r in rows
            if q in r["key"] or q in r["base"] or q in str(r["display"]).upper()
        ]
    return {"ok": True, "market": "crypto", "results": rows[: max(1, int(limit))]}


def _klines_to_df(rows: List[list]) -> pd.DataFrame:
    # [openTime, o, h, l, c, volume, closeTime, ...]
    recs = []
    for r in rows:
        ts = pd.Timestamp(int(r[0]), unit="ms", tz="UTC").tz_convert("Asia/Kolkata")
        recs.append(
            {
                "Open": float(r[1]),
                "High": float(r[2]),
                "Low": float(r[3]),
                "Close": float(r[4]),
                "Volume": float(r[5]),
                "date": ts,
            }
        )
    if not recs:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df = pd.DataFrame(recs).set_index("date").sort_index()
    return df[~df.index.duplicated(keep="last")]


def fetch_klines_1m(
    symbol: str,
    *,
    days: int = 5,
    hours: Optional[int] = None,
    force_refresh: bool = False,
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Fetch 1m OHLCV for symbol (e.g. BTCUSDT). Returns IST-indexed frame.

    Prefer ``hours`` for live charts (e.g. 36 ≈ 24h chart + SR lookback) —
    only ~2 Binance pages vs many for multi-day history.
    """
    if requests is None:
        return None, "requests_not_installed"
    sym = str(symbol or "BTCUSDT").upper().replace("-", "").replace("/", "")
    if not sym.endswith("USDT"):
        sym = f"{sym}USDT"
    days = int(max(1, min(int(days), 30)))
    hrs = int(hours) if hours is not None else None
    if hrs is not None:
        hrs = int(max(6, min(hrs, 24 * 14)))
    cache_k = f"{sym}:h{hrs}" if hrs is not None else f"{sym}:d{days}"
    now = time.time()
    if not force_refresh:
        hit = _KLINE_CACHE.get(cache_k)
        if hit and (now - hit[0]) < _KLINE_TTL:
            return hit[1], hit[2]

    # Binance max 1000 bars/request. Page with endTime only (newest first).
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if hrs is not None:
        start_ms = int((datetime.now(timezone.utc) - timedelta(hours=hrs)).timestamp() * 1000)
        max_pages = max(2, (hrs // 16) + 2)  # ~1000 bars ≈ 16.6h
    else:
        start_ms = int((datetime.now(timezone.utc) - timedelta(days=days + 1)).timestamp() * 1000)
        max_pages = 40
    all_rows: List[list] = []
    cursor_end = end_ms
    try:
        for _ in range(max_pages):
            params = {
                "symbol": sym,
                "interval": "1m",
                "endTime": cursor_end,
                "limit": 1000,
            }
            url = f"{BASE}/api/v3/klines"
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                msg = f"binance_http_{resp.status_code}: {resp.text[:160]}"
                _KLINE_CACHE[cache_k] = (now, None, msg)
                return None, msg
            batch = resp.json()
            if not batch:
                break
            kept = [r for r in batch if int(r[0]) >= start_ms]
            all_rows = kept + all_rows
            first_open = int(batch[0][0])
            if first_open <= start_ms or not kept:
                break
            cursor_end = first_open - 1
            if len(batch) < 1000:
                break
            time.sleep(0.03)
    except Exception as exc:
        msg = f"binance_fetch: {exc}"
        _KLINE_CACHE[cache_k] = (now, None, msg)
        return None, msg

    if not all_rows:
        _KLINE_CACHE[cache_k] = (now, None, "empty_klines")
        return None, "empty_klines"

    # de-dupe by open time
    seen = set()
    uniq = []
    for r in all_rows:
        t0 = int(r[0])
        if t0 in seen:
            continue
        seen.add(t0)
        uniq.append(r)
    uniq.sort(key=lambda x: int(x[0]))
    df = _klines_to_df(uniq)
    _KLINE_CACHE[cache_k] = (now, df, None)
    return df, None


def fetch_ltp(symbol: str) -> Tuple[Optional[float], Optional[str]]:
    if requests is None:
        return None, "requests_not_installed"
    sym = str(symbol or "BTCUSDT").upper()
    if not sym.endswith("USDT"):
        sym = f"{sym}USDT"
    try:
        resp = requests.get(
            f"{BASE}/api/v3/ticker/price",
            params={"symbol": sym},
            timeout=10,
        )
        if resp.status_code != 200:
            return None, f"binance_ltp_{resp.status_code}"
        data = resp.json()
        return float(data["price"]), None
    except Exception as exc:
        return None, str(exc)


def latest_bar_from_df(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    if df is None or df.empty:
        return None
    ts = df.index[-1]
    row = df.iloc[-1]
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("Asia/Kolkata")
    else:
        t = t.tz_convert("Asia/Kolkata")
    return {
        "time": int(t.timestamp()),
        "open": round(float(row["Open"]), 6),
        "high": round(float(row["High"]), 6),
        "low": round(float(row["Low"]), 6),
        "close": round(float(row["Close"]), 6),
    }
