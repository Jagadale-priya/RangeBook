"""Groww option chart deep-links from NSE/BSE F&O trading symbols.

Examples:
  https://groww.in/charts/options/nifty/NIFTY26N0924450CE?exchange=NSE
  https://groww.in/charts/options/sp-bse-sensex/SENSEX26N1279700CE?exchange=BSE
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import quote

_UNDERLYING_PATH = {
    "NIFTY": "nifty",
    "BANKNIFTY": "banknifty",
    "FINNIFTY": "finnifty",
    "MIDCPNIFTY": "midcpnifty",
    # Groww BSE index path uses sp-bse-* (plain "sensex" 404s).
    "SENSEX": "sp-bse-sensex",
    "BANKEX": "sp-bse-bankex",
}

_EXCHANGE = {
    "NIFTY": "NSE",
    "BANKNIFTY": "NSE",
    "FINNIFTY": "NSE",
    "MIDCPNIFTY": "NSE",
    "SENSEX": "BSE",
    "BANKEX": "BSE",
}


def underlying_slug(stock: Any) -> Optional[str]:
    key = str(stock or "").strip().upper()
    return _UNDERLYING_PATH.get(key)


def exchange_for(stock: Any) -> str:
    key = str(stock or "").strip().upper()
    return _EXCHANGE.get(key, "NSE")


def option_chart_url(
    stock: Any,
    tradingsymbol: Any,
    *,
    exchange: Optional[str] = None,
) -> Optional[str]:
    """Build Groww charts URL for a CE/PE contract, or None if incomplete."""
    sym = str(tradingsymbol or "").strip().upper()
    slug = underlying_slug(stock)
    if not sym or not slug:
        # Infer underlying from symbol prefix when stock missing
        for name, path in _UNDERLYING_PATH.items():
            if sym.startswith(name):
                slug = path
                stock = name
                break
    if not sym or not slug:
        return None
    ex = (exchange or exchange_for(stock) or "NSE").upper()
    return f"https://groww.in/charts/options/{slug}/{quote(sym, safe='')}?exchange={ex}"


def enrich_option_guide(order: Optional[Dict[str, Any]], stock: Any = None) -> Optional[Dict[str, Any]]:
    """Attach groww_url onto an option_order / readings.option dict."""
    if not isinstance(order, dict):
        return order
    out = dict(order)
    und = stock or out.get("underlying") or out.get("stock")
    url = option_chart_url(und, out.get("tradingsymbol"))
    if url:
        out["groww_url"] = url
        out["groww_chart"] = url
    return out
