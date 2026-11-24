"""
Live and historical market data routing.

Indian symbols (watchlist): **Kite Connect only** when configured.
Fallback: Yahoo Finance (US/crypto/indian when Kite off).
Groww / NSE public quote APIs removed from default path (legacy: GROWW_ENABLE=1).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import kite_data
import market_symbols
from market_symbols import apply_live_quote_to_daily_df, is_indian_symbol, nse_trading_symbol

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore


def _groww_legacy_enabled() -> bool:
    return os.environ.get("GROWW_ENABLE", "").strip().lower() in ("1", "true", "yes")


def is_live_eligible(stock_key: str, indian_stocks: Dict[str, str]) -> bool:
    return is_indian_symbol(stock_key, indian_stocks)


def _yahoo_symbol(stock_key: str, indian_stocks: Dict[str, str]) -> str:
    key = stock_key.strip().upper()
    if key in indian_stocks:
        return indian_stocks[key]
    if key.endswith(".NS") or key.startswith("^") or "-" in key:
        return key
    return f"{key}.NS"


def _fetch_yahoo(stock_key: str, indian_stocks: Dict[str, str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if yf is None:
        return None, "yfinance not installed"
    ysym = _yahoo_symbol(stock_key, indian_stocks)
    try:
        t = yf.Ticker(ysym)
        fi = t.fast_info
        last_p = getattr(fi, "last_price", None) or getattr(fi, "lastPrice", None)
        if last_p is None:
            hist = t.history(period="1d")
            if len(hist):
                last_p = float(hist["Close"].iloc[-1])
        if last_p is None:
            return None, f"Yahoo no price for {ysym}"
        open_p = getattr(fi, "open", None) or last_p
        high = getattr(fi, "day_high", None) or getattr(fi, "dayHigh", None) or last_p
        low = getattr(fi, "day_low", None) or getattr(fi, "dayLow", None) or last_p
        received = market_symbols.ist_now()
        return {
            "stock": stock_key.strip().upper(),
            "trading_symbol": nse_trading_symbol(stock_key),
            "exchange": "NSE" if ysym.endswith(".NS") else "OTHER",
            "segment": "CASH",
            "last_price": round(float(last_p), 2),
            "open": round(float(open_p), 2),
            "high": round(float(high), 2),
            "low": round(float(low), 2),
            "close": round(float(last_p), 2),
            "volume": 0,
            "source": "yahoo",
            "feed_type": "delayed_quote",
            "received_at_ist": received.isoformat(),
            "disclaimer": "Yahoo Finance fallback (enable Kite Connect for exchange quotes).",
        }, None
    except Exception as exc:
        return None, str(exc)


def fetch_live_quote(
    stock_key: str,
    indian_stocks: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    indian_stocks = indian_stocks or {}
    key = stock_key.strip().upper()
    indian = is_indian_symbol(key, indian_stocks)

    if indian and kite_data.kite_enabled():
        q, err = kite_data.fetch_live_quote(key)
        if q:
            return q, None
        return None, err or "Kite quote failed — check token and Connect plan"

    if indian and _groww_legacy_enabled():
        try:
            import groww_data
            q, err = groww_data.fetch_live_quote(key)
            if q:
                q["source"] = "groww"
                q["disclaimer"] = "Legacy Groww feed (GROWW_ENABLE=1). Prefer Kite."
                return q, None
        except Exception as exc:
            pass

    if indian and not kite_data.kite_enabled():
        q, err = _fetch_yahoo(key, indian_stocks)
        if q:
            return q, None
        return None, (
            err
            or "Configure Kite Connect in .env (KITE_API_KEY, KITE_ACCESS_TOKEN) for Indian live quotes."
        )

    q, err = _fetch_yahoo(key, indian_stocks)
    return (q, err) if q else (None, err or "No quote source")


def fetch_live_ltp(
    stock_keys: List[str],
    indian_stocks: Optional[Dict[str, str]] = None,
) -> Tuple[Dict[str, float], Optional[str]]:
    indian_stocks = indian_stocks or {}
    keys = [k.strip().upper() for k in stock_keys[:50]]
    if kite_data.kite_enabled():
        try:
            import kite_ticker

            ws = kite_ticker.get_ltps(keys)
            if len(ws) == len(keys):
                return ws, None
        except ImportError:
            pass
        ltps, err = kite_data.fetch_live_ltp(keys)
        if ltps:
            return ltps, err
        if err:
            return {}, err
    out: Dict[str, float] = {}
    last_err = None
    for k in keys:
        q, e = fetch_live_quote(k, indian_stocks)
        if q:
            out[k] = float(q["last_price"])
        else:
            last_err = e
    return out, last_err if not out else None


def get_provider_status() -> Dict[str, Any]:
    kite = kite_data.get_provider_status()
    ready = kite.get("ready")
    ws_status = {}
    try:
        import kite_ticker

        ws_status = kite_ticker.get_status()
    except ImportError:
        pass
    return {
        "mode": "kite_connect" if ready else "yahoo_fallback",
        "primary": "kite_connect" if ready else "yahoo_finance",
        "fallback": None if ready else "yahoo_finance",
        "kite": kite,
        "websocket": ws_status,
        "groww_legacy": _groww_legacy_enabled(),
        "nse_scrape_live": False,
        "cost": "Kite Connect ₹500/mo when ready" if ready else "Yahoo free (delayed); add Kite for NSE live",
        "note": "Indian live + daily history use Kite when ready. News still from NSE filings API.",
        "capabilities_url": "/data/kite-capabilities",
    }
