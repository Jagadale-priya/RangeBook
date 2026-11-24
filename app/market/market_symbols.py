"""Shared NSE/BSE symbol helpers and OHLCV patch (no broker-specific APIs)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore

INDEX_SYMBOLS = frozenset({"NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50", "BANKEX"})

NSE_SYMBOL_OVERRIDES = {
    "BANKNIFTY": "NIFTY BANK",
    "NIFTY": "NIFTY",
}


def ist_now() -> datetime:
    if ZoneInfo:
        return datetime.now(ZoneInfo("Asia/Kolkata"))
    return datetime.now()


def stock_key_from_input(stock_input: str) -> str:
    return stock_input.strip().upper()


def is_indian_symbol(stock_key: str, indian_stocks: Dict[str, str]) -> bool:
    key = stock_key_from_input(stock_key)
    if key in indian_stocks or key in INDEX_SYMBOLS:
        return True
    if key.endswith(".NS"):
        base = key[:-3]
        return base in indian_stocks or base in INDEX_SYMBOLS or _on_user_book(base)
    return _on_user_book(key)


def _on_user_book(key: str) -> bool:
    try:
        import fno_universe

        if fno_universe.contains(key):
            return True
    except Exception:
        pass
    try:
        import user_watchlists

        return user_watchlists.contains(user_watchlists.default_base(), key)
    except Exception:
        return False


def nse_trading_symbol(stock_key: str) -> str:
    key = stock_key_from_input(stock_key)
    if key.endswith(".NS"):
        key = key[:-3]
    if key in NSE_SYMBOL_OVERRIDES:
        return NSE_SYMBOL_OVERRIDES[key]
    return key


# Back-compat aliases used across the codebase
groww_trading_symbol = nse_trading_symbol


def is_groww_eligible(stock_key: str, indian_stocks: Dict[str, str]) -> bool:
    return is_indian_symbol(stock_key, indian_stocks)


def apply_live_quote_to_daily_df(df, quote: Dict[str, Any]):
    if pd is None or df is None or len(df) == 0 or not quote:
        return df

    df = df.copy()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)

    try:
        import kite_calendar

        if not kite_calendar.should_apply_live_daily_bar()[0]:
            return df
    except ImportError:
        pass

    today = ist_now().date()
    last_idx = df.index[-1]
    last_date = last_idx.date() if hasattr(last_idx, "date") else pd.Timestamp(last_idx).date()

    o = quote.get("open") or quote["last_price"]
    h = max(quote.get("high") or o, quote["last_price"])
    l = min(quote.get("low") or o, quote["last_price"])
    c = quote["last_price"]
    v = quote.get("volume") or 0

    row = {"Open": o, "High": h, "Low": l, "Close": c, "Volume": v}
    ts = pd.Timestamp(today)

    if last_date == today:
        for col, val in row.items():
            df.at[last_idx, col] = val
        df.at[last_idx, "High"] = max(float(df.at[last_idx, "High"]), h)
        df.at[last_idx, "Low"] = min(float(df.at[last_idx, "Low"]), l)
    elif last_date < today:
        df.loc[ts] = row
        df.sort_index(inplace=True)
    return df
