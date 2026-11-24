"""Data source tags and UI empty-state hints for predict API + dashboard."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional

import market_symbols

INDEX_KEYS = frozenset({"NIFTY", "BANKNIFTY", "SENSEX"})


def _cache_age_hours(path: str) -> Optional[float]:
    if not os.path.isfile(path):
        return None
    return (datetime.now().timestamp() - os.path.getmtime(path)) / 3600.0


def build_data_provenance(
    symbol: str,
    stock_key: str,
    hist_source: str,
    live_quote: Optional[Dict[str, Any]],
    live_err: Optional[str],
    cache_dir: str,
) -> Dict[str, Any]:
    safe = symbol.replace("^", "IDX_").replace(".", "_")
    cache_file = os.path.join(cache_dir, f"{safe}.csv")
    age_h = _cache_age_hours(cache_file)

    live_source = None
    feed_type = None
    if live_quote:
        live_source = live_quote.get("source") or "kite"
        feed_type = live_quote.get("feed_type")
    elif live_err:
        live_source = "unavailable"

    apply_ok, apply_reason = True, "ok"
    try:
        import kite_calendar

        apply_ok, apply_reason = kite_calendar.should_apply_live_daily_bar()
    except ImportError:
        pass

    tag = live_source or hist_source or "yahoo_finance"
    if tag in ("kite", "kite_ws"):
        display = "Live · Kite WS" if tag == "kite_ws" else "Live · Kite"
    elif tag == "yahoo":
        display = "Yahoo (delayed)"
    else:
        display = str(tag)

    return {
        "historical_source": hist_source,
        "cache_file": os.path.basename(cache_file) if os.path.isfile(cache_file) else None,
        "cache_age_hours": round(age_h, 1) if age_h is not None else None,
        "live_source": live_source,
        "live_feed_type": feed_type,
        "live_error": live_err,
        "price_tag": display,
        "apply_live_daily_bar": apply_ok,
        "apply_live_reason": apply_reason,
    }


def build_panel_hints(
    stock_key: str,
    fund: Dict[str, Any],
    struct: Dict[str, Any],
    live_quote: Optional[Dict[str, Any]],
    live_err: Optional[str],
    knowledge: Dict[str, Any],
    indian_stocks: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    key = stock_key.strip().upper()
    hints: Dict[str, str] = {}

    if key in INDEX_KEYS:
        hints["fundamentals"] = "Index symbol — fundamentals not applicable (use structure + ML)."
    elif not fund.get("available"):
        hints["fundamentals"] = fund.get("reason") or "Yahoo fundamentals sparse — retry later or check symbol."

    sr = struct.get("support_resistance") or {}
    if not struct.get("bias") and not sr.get("nearest_support"):
        hints["structure"] = "Insufficient swing history or flat structure — levels may be unavailable."

    if live_err and "token" in str(live_err).lower():
        hints["live"] = "Kite token expired — run py kite_login.py or set TOTP in .env."
    elif live_err:
        hints["live"] = live_err
    elif not live_quote and indian_stocks and market_symbols.is_indian_symbol(key, indian_stocks):
        hints["live"] = "Enable Kite in .env for exchange live quotes."

    try:
        import kite_calendar

        ok, reason = kite_calendar.should_apply_live_daily_bar()
        if not ok:
            hints["live_bar"] = f"Today's bar not patched: {reason.replace('_', ' ')}."
    except ImportError:
        pass

    if int(knowledge.get("matched_rule_count") or 0) == 0:
        hints["memory"] = "No matching rules — run --train-knowledge or try after more history."

    return hints
