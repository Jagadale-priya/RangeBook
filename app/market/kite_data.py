"""
Zerodha Kite Connect — quotes, LTP, OHLC, historical candles.

Requires Connect plan (₹500/mo) + .env credentials (see kite_auth.py).
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import fno_universe
import kite_auth
import kite_calendar
import market_symbols
from market_symbols import is_indian_symbol, nse_trading_symbol, stock_key_from_input

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore

try:
    from kiteconnect import KiteConnect
except ImportError:
    KiteConnect = None  # type: ignore

_kite: Any = None
_kite_token: Optional[str] = None
_last_error: Optional[str] = None

INDEX_KITE = dict(fno_universe.INDEX_SPOT)

# What Kite Connect offers vs what this app uses (see GET /data/kite-capabilities)
KITE_API_CATALOG: Dict[str, Any] = {
    "used_by_this_app": [
        {"api": "GET /quote", "use": "Live full quote fallback", "module": "fetch_live_quote"},
        {"api": "GET /quote/ltp", "use": "Batch last price fallback", "module": "fetch_live_ltp"},
        {"api": "GET /quote/ohlc", "use": "Lightweight OHLC snapshot", "module": "fetch_ohlc_snapshot"},
        {"api": "KiteTicker WebSocket", "use": "Streaming quotes for watchlist", "module": "kite_ticker"},
        {"api": "GET /instruments", "use": "Cached symbol master", "module": "kite_instruments"},
        {"api": "historical_data day", "use": "Daily OHLCV history", "module": "fetch_daily_ohlcv"},
        {"api": "historical_data intraday", "use": "5m/15m for pattern_memory", "module": "fetch_historical_candles"},
        {"api": "Exchange calendar", "use": "Skip live bar on holidays", "module": "kite_calendar"},
        {"api": "orders / portfolio / gtt / margins", "use": "Trading (dry-run default)", "module": "kite_trading"},
    ],
    "available_not_wired": [],
    "not_in_kite_use_elsewhere": [
        {"need": "Fundamentals (P/E, ROE)", "source": "Yahoo Finance info (fundamentals.py)"},
        {"need": "NSE corporate announcements / news", "source": "NSE public API (news_data.py)"},
        {"need": "US/global macro panel", "source": "Yahoo (analysis_engine overnight panel)"},
    ],
    "rate_limits": {
        "quote": "1 request/second",
        "historical": "3 requests/second",
        "ltp_per_request": "up to 1000 instruments",
        "websocket": "3000 instruments per connection, 3 connections per API key",
    },
}


def _read_env(name: str) -> Optional[str]:
    val = os.environ.get(name, "").strip()
    return val or None


def is_kite_eligible(stock_key: str, indian_stocks: Dict[str, str]) -> bool:
    return is_indian_symbol(stock_key, indian_stocks)


def kite_instrument_id(stock_key: str) -> str:
    raw = str(stock_key or "").strip()
    # Already EXCHANGE:SYMBOL (NFO/BFO options, BSE spot, etc.)
    if ":" in raw:
        ex, sym = raw.split(":", 1)
        ex = ex.strip().upper()
        sym = sym.strip()
        if ex in ("NSE", "BSE", "NFO", "BFO", "MCX") and sym:
            return f"{ex}:{sym}"
    key = stock_key_from_input(stock_key)
    if key in INDEX_KITE:
        ex, sym = INDEX_KITE[key]
        return f"{ex}:{sym}"
    return f"NSE:{nse_trading_symbol(stock_key)}"


import kite_instruments  # after INDEX_KITE / kite_instrument_id (kite_instruments imports these)


def is_configured() -> bool:
    if not kite_auth.api_credentials_ready():
        return False
    if _read_env("KITE_ACCESS_TOKEN"):
        return True
    return kite_auth.auto_login_configured()


def kite_enabled() -> bool:
    if os.environ.get("KITE_ENABLE", "1").strip().lower() in ("0", "false", "no"):
        return False
    return is_configured()


def _token_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if "socket" in msg or "failed to establish a new connection" in msg:
        return False
    return any(x in msg for x in ("token", "401", "403", "session", "unauthorized", "forbidden"))


def reset_client() -> None:
    global _kite, _kite_token
    _kite = None
    _kite_token = None


def _get_kite(force_refresh: bool = False) -> Tuple[Any, Optional[str]]:
    global _kite, _kite_token, _last_error
    if KiteConnect is None:
        _last_error = "Install kiteconnect: pip install kiteconnect"
        return None, _last_error
    access_token, err = kite_auth.get_access_token(force_refresh=force_refresh)
    if err or not access_token:
        _last_error = err
        reset_client()
        return None, err
    api_key = _read_env("KITE_API_KEY")
    if not api_key:
        _last_error = "KITE_API_KEY not set"
        return None, _last_error
    if _kite is None or _kite_token != access_token or force_refresh:
        k = KiteConnect(api_key=api_key)
        k.set_access_token(access_token)
        _kite = k
        _kite_token = access_token
    return _kite, None


def _parse_kite_exchange_ts(raw: Dict[str, Any], received: datetime) -> Tuple[Optional[datetime], Optional[int]]:
    """Kite may omit last_trade_time after hours; fall back to packet `timestamp`."""
    for key in ("last_trade_time", "timestamp"):
        value = raw.get(key)
        if not value:
            continue
        try:
            exchange_ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if exchange_ts.tzinfo is None:
                # Kite's naive exchange timestamps are in the exchange's local
                # timezone, not UTC.
                exchange_ts = exchange_ts.replace(tzinfo=market_symbols.ist_now().tzinfo)
            staleness_ms = max(
                0,
                int((received.astimezone(timezone.utc) - exchange_ts.astimezone(timezone.utc)).total_seconds() * 1000),
            )
            return exchange_ts, staleness_ms
        except (TypeError, ValueError, OSError):
            continue
    return None, None


def _normalize_kite_quote(raw: Dict[str, Any], stock_key: str, received: datetime) -> Dict[str, Any]:
    ohlc = raw.get("ohlc") or {}
    last_price = float(raw.get("last_price") or 0)
    exchange_ts, staleness_ms = _parse_kite_exchange_ts(raw, received)
    prev_close = float(ohlc.get("close") or 0) or None
    ex = "BSE" if str(raw.get("exchange") or "").upper() == "BSE" else "NSE"
    auto = kite_auth.auto_login_configured()
    depth = raw.get("depth") or {}
    return {
        "stock": stock_key_from_input(stock_key),
        "trading_symbol": nse_trading_symbol(stock_key),
        "exchange": ex,
        "segment": "CASH",
        "last_price": round(last_price, 2),
        "open": round(float(ohlc.get("open") or last_price), 2),
        "high": round(float(ohlc.get("high") or last_price), 2),
        "low": round(float(ohlc.get("low") or last_price), 2),
        # Kite OHLC.close is the previous close; the working close is last price.
        "close": round(last_price, 2),
        "prev_close": round(prev_close, 2) if prev_close else None,
        "volume": int(raw.get("volume") or raw.get("volume_traded") or 0),
        "average_price": raw.get("average_price"),
        "oi": raw.get("oi"),
        "buy_quantity": depth.get("buy") and sum(x.get("quantity", 0) for x in depth["buy"][:5]),
        "sell_quantity": depth.get("sell") and sum(x.get("quantity", 0) for x in depth["sell"][:5]),
        "day_change": raw.get("net_change"),
        "day_change_perc": raw.get("change"),
        "received_at_ist": received.isoformat(),
        "exchange_timestamp": exchange_ts.isoformat() if exchange_ts else None,
        "exchange_timestamp_utc": exchange_ts.astimezone(timezone.utc).isoformat() if exchange_ts else None,
        "staleness_ms": staleness_ms,
        "source": "kite",
        "feed_type": "live_quote",
        "subscription_required": True,
        "disclaimer": (
            "Zerodha Kite Connect (Connect plan). "
            + ("Auto TOTP refresh enabled." if auto else "Run py kite_login.py or set TOTP in .env.")
        ),
    }


def fetch_live_quote(stock_key: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    global _last_error
    key = stock_key_from_input(stock_key)

    try:
        import kite_ticker

        tick = kite_ticker.get_tick(key)
        if tick and tick.get("last_price"):
            received_raw = tick.get("updated_at_ist") or market_symbols.ist_now().isoformat()
            received = datetime.fromisoformat(str(received_raw))
            lp = float(tick["last_price"])
            o = float(tick.get("open") or lp)
            h = float(tick.get("high") or lp)
            l = float(tick.get("low") or lp)
            quote = {
                "stock": key,
                "trading_symbol": nse_trading_symbol(stock_key),
                "exchange": "NSE",
                "segment": "CASH",
                "last_price": round(lp, 2),
                "open": round(o, 2),
                "high": round(max(h, lp), 2),
                "low": round(min(l, lp), 2),
                "close": round(lp, 2),
                "volume": int(tick.get("volume") or 0),
                "source": "kite_ws",
                "feed_type": "websocket_quote",
                "received_at_ist": received.isoformat(),
                "disclaimer": "KiteTicker WebSocket (MODE_QUOTE).",
            }
            if key != "NIFTY":
                return quote, None
            from nifty_fno_data import quote_fresh

            if quote_fresh(quote):
                return quote, None
    except ImportError:
        pass

    for attempt in range(2):
        kite, err = _get_kite(force_refresh=attempt > 0)
        if err or not kite:
            return None, err
        ins = kite_instrument_id(stock_key)
        received = market_symbols.ist_now()
        try:
            data = kite.quote([ins])
            if not data:
                return None, f"Kite returned no quote for {ins}"
            raw = next(iter(data.values()))
            return _normalize_kite_quote(raw, stock_key, received), None
        except Exception as exc:
            msg = str(exc)
            _last_error = msg
            if attempt == 0 and _token_error(exc):
                reset_client()
                continue
            return None, msg
    return None, _last_error


def fetch_exchange_quote(exchange: str, tradingsymbol: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Full Kite quote for any exchange:symbol (used for NFO OI / IV)."""
    rows, err = quote_many([f"{exchange}:{tradingsymbol}"])
    if err and not rows:
        return None, err
    key = f"{exchange}:{tradingsymbol}"
    raw = rows.get(key)
    if not raw:
        raw = next(iter(rows.values()), None) if rows else None
    if not raw:
        return None, err or f"No quote for {key}"
    return raw, None


def quote_many(instrument_ids: List[str]) -> Tuple[Dict[str, Dict[str, Any]], Optional[str]]:
    """One Kite /quote call (up to 500 ids). Keys like NFO:NIFTY25SEP22600CE."""
    ids = [str(i) for i in instrument_ids if i][:500]
    if not ids:
        return {}, None
    kite, err = _get_kite()
    if err or not kite:
        return {}, err
    try:
        data = kite.quote(ids)
        if not isinstance(data, dict):
            return {}, "Kite quote returned no map"
        return {str(k): v for k, v in data.items() if isinstance(v, dict)}, None
    except Exception as exc:
        return {}, str(exc)


def fetch_live_ltp(stock_keys: List[str]) -> Tuple[Dict[str, float], Optional[str]]:
    keys = [stock_key_from_input(k) for k in stock_keys][:50]
    if not keys:
        return {}, None
    try:
        import kite_ticker

        ws = kite_ticker.get_ltps(keys)
        if ws and len(ws) >= len(keys) * 0.5:
            return ws, None
    except ImportError:
        pass
    for attempt in range(2):
        kite, err = _get_kite(force_refresh=attempt > 0)
        if err or not kite:
            return {}, err
        instruments = [kite_instrument_id(k) for k in keys]
        try:
            data = kite.ltp(instruments)
            out: Dict[str, float] = {}
            for k, ins in zip(keys, instruments):
                row = data.get(ins) if isinstance(data, dict) else None
                if isinstance(row, dict) and row.get("last_price") is not None:
                    out[k] = float(row["last_price"])
                elif isinstance(row, (int, float)):
                    out[k] = float(row)
            if out:
                return out, None
            return {}, "Kite LTP returned no prices"
        except Exception as exc:
            if attempt == 0 and _token_error(exc):
                reset_client()
                continue
            return {}, str(exc)
    return {}, _last_error


def fetch_ohlc_snapshot(stock_keys: List[str]) -> Tuple[Dict[str, Any], Optional[str]]:
    """Kite /quote/ohlc — lighter than full quote."""
    keys = [stock_key_from_input(k) for k in stock_keys][:100]
    if not keys:
        return {}, None
    kite, err = _get_kite()
    if err or not kite:
        return {}, err
    instruments = [kite_instrument_id(k) for k in keys]
    try:
        return kite.ohlc(instruments), None
    except Exception as exc:
        return {}, str(exc)


def _instrument_token(kite: Any, stock_key: str) -> Tuple[Optional[int], Optional[str]]:
    tok, err = kite_instruments.resolve_instrument_token(stock_key)
    if tok:
        return tok, None
    ins = kite_instrument_id(stock_key)
    try:
        data = kite.quote([ins])
        if not data:
            return None, err or f"No quote for {ins}"
        raw = next(iter(data.values()))
        token = raw.get("instrument_token")
        if token is not None:
            return int(token), None
    except Exception as exc:
        return None, err or str(exc)
    return None, err or f"No instrument_token for {ins}"


def fetch_daily_ohlcv(stock_key: str, years: float = 5) -> Tuple[Optional[Any], Optional[str]]:
    if pd is None:
        return None, "pandas required"
    if not kite_enabled():
        return None, "Kite not enabled"
    kite_instruments.ensure_cache()
    for attempt in range(2):
        kite, err = _get_kite(force_refresh=attempt > 0)
        if err or not kite:
            return None, err
        token, tok_err = _instrument_token(kite, stock_key)
        if not token:
            return None, tok_err or "instrument token missing"
        to_d = date.today()
        from_d = to_d - timedelta(days=int(years * 365.25))
        try:
            # Kite rejects a multi-year daily request that exceeds its interval
            # cap.  Keep a day of headroom because both request endpoints are
            # inclusive, then merge de-duplicated windows.  This lets callers
            # ask for 10+ years without silently falling back to a shorter set.
            max_span = max(1, INTERVAL_MAX_DAYS.get("day", 2000) - 2)
            frames = []
            window_start = from_d
            while window_start <= to_d:
                window_end = min(window_start + timedelta(days=max_span), to_d)
                candles = kite.historical_data(token, window_start, window_end, interval="day")
                if not candles:
                    return None, f"Kite returned no daily candles for {window_start} to {window_end}"
                frames.append(pd.DataFrame(candles))
                window_start = window_end + timedelta(days=1)

            df = pd.concat(frames, ignore_index=True)
            df["date"] = pd.to_datetime(df["date"])
            df = df.drop_duplicates(subset="date").set_index("date").sort_index()
            df = df.rename(
                columns={
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume",
                }
            )
            keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
            df = df[keep]
            if len(df) < 50:
                return None, f"Only {len(df)} daily bars from Kite"
            return df, None
        except Exception as exc:
            if attempt == 0 and _token_error(exc):
                reset_client()
                continue
            return None, str(exc)
    return None, _last_error


# Kite caps the span of a single historical_data call per interval; asking for more
# fails outright with "interval exceeds max limit: N days".
# https://kite.trade/forum/discussion/3105
INTERVAL_MAX_DAYS = {
    "minute": 60,
    "3minute": 100,
    "4minute": 100,
    "5minute": 100,
    "10minute": 100,
    "15minute": 200,
    "30minute": 200,
    "60minute": 400,
    "hour": 400,
    "day": 2000,
    "week": 2000,
}
INTERVAL_MINUTES = {
    "minute": 1,
    "3minute": 3,
    "4minute": 4,
    "5minute": 5,
    "10minute": 10,
    "15minute": 15,
    "30minute": 30,
    "60minute": 60,
    "hour": 60,
}


def drop_unfinished_candle(df: Any, interval: str, *, asof: Any = None) -> Any:
    """Kite timestamps are bar starts; the last row can still be filling."""
    minutes = INTERVAL_MINUTES.get(interval)
    if pd is None or minutes is None or df is None or getattr(df, "empty", True):
        return df
    last = pd.Timestamp(df.index[-1])
    now = pd.Timestamp(asof) if asof is not None else pd.Timestamp.now(tz=last.tzinfo) if last.tzinfo else pd.Timestamp.now()
    if last.tzinfo is None and now.tzinfo is not None:
        now = now.tz_localize(None)
    elif last.tzinfo is not None and now.tzinfo is None:
        now = now.tz_localize(last.tzinfo)
    if last + timedelta(minutes=int(minutes)) > now:
        return df.iloc[:-1]
    return df


def fetch_historical_candles(
    stock_key: str,
    interval: str = "5minute",
    days: int = 5,
    *,
    strict: bool = False,
    keep_partial: bool = False,
) -> Tuple[Optional[Any], Optional[str]]:
    """Intraday/weekly history via Kite (Connect plan), chunked to the per-interval cap."""
    if pd is None:
        return None, "pandas required"
    if interval not in INTERVAL_MAX_DAYS:
        return None, f"Unsupported interval {interval}"
    kite_instruments.ensure_cache()
    kite, err = _get_kite()
    if err or not kite:
        return None, err
    token, tok_err = _instrument_token(kite, stock_key)
    if not token:
        return None, tok_err

    to_d = datetime.now()
    start = (to_d - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    # Stay a day inside the cap; Kite counts calendar days inclusively.
    chunk = max(1, INTERVAL_MAX_DAYS[interval] - 1)
    frames = []
    last_err = None
    window_start = start
    failed_windows = []
    while window_start < to_d:
        window_end = min(window_start + timedelta(days=chunk), to_d)
        try:
            candles = kite.historical_data(token, window_start, window_end, interval=interval)
            if candles:
                frames.append(pd.DataFrame(candles))
            elif strict:
                failed_windows.append(f"{window_start.isoformat()} to {window_end.isoformat()}: empty")
        except Exception as exc:
            last_err = str(exc)
            failed_windows.append(f"{window_start.isoformat()} to {window_end.isoformat()}: {exc}")
        # Endpoints include their time component. Starting at the prior end is
        # continuous; de-duplication below removes the shared boundary candle.
        window_start = window_end

    if strict and failed_windows:
        return None, "Incomplete historical download: " + "; ".join(failed_windows[:3])
    if not frames:
        return None, last_err or "No candles returned"
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(subset="date").set_index("date").sort_index()
    # The chart needs the bar that is still filling. Decisions keep only finished bars.
    if not keep_partial:
        df = drop_unfinished_candle(df, interval)
    return df, None


def get_api_capabilities() -> Dict[str, Any]:
    try:
        import kite_ticker
        import kite_trading

        ws = kite_ticker.get_status()
        trading = kite_trading.trading_status()
    except ImportError:
        ws, trading = {}, {}
    return {
        "kite_enabled": kite_enabled(),
        "provider_status": get_provider_status(),
        "instruments": kite_instruments.get_status(),
        "calendar": kite_calendar.get_status(),
        "websocket": ws,
        "trading": trading,
        "catalog": KITE_API_CATALOG,
        "docs": "https://kite.trade/docs/connect/v3/",
    }


def get_provider_status() -> Dict[str, Any]:
    api_key = _read_env("KITE_API_KEY")
    auth = kite_auth.get_auth_status()
    ready = kite_enabled() and (
        bool(_read_env("KITE_ACCESS_TOKEN")) or auth.get("auto_login_configured")
    )
    return {
        "enabled": kite_enabled(),
        "ready": ready,
        "api_key_set": bool(api_key),
        "api_secret_set": bool(_read_env("KITE_API_SECRET")),
        "access_token_set": auth.get("access_token_set"),
        "auto_login": auth.get("auto_login_configured"),
        "last_refresh_mode": auth.get("last_refresh_mode"),
        "last_error": _last_error or auth.get("last_error"),
        "login_url_hint": (
            f"https://kite.zerodha.com/connect/login?v=3&api_key={quote(api_key)}"
            if api_key
            else None
        ),
        "plan": "Kite Connect Connect (₹500/mo) — quotes, LTP, OHLC, historical",
        "replaces": "Groww live + NSE scrape for Indian quotes when ready",
        "instruments_cache": kite_instruments.get_status(),
        "calendar": kite_calendar.get_status(),
    }
