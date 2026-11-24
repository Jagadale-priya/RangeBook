"""NSE trading calendar (Kite has no holidays API — NSE seed + optional refresh)."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import market_symbols

import kite_auth

try:
    import nse_session
except ImportError:
    nse_session = None  # type: ignore

NSE_HOLIDAY_URL = "https://www.nseindia.com/api/holiday-master"
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

_holidays: Optional[Set[date]] = None
_last_load_error: Optional[str] = None


def _seed_path() -> str:
    root = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(root, "stock_signal_data", "exchange_holidays_seed.json")


def _cache_path() -> str:
    root = os.environ.get("STOCK_SIGNAL_DATA_DIR", "").strip()
    if not root:
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_signal_data")
    os.makedirs(os.path.join(root, "cache"), exist_ok=True)
    return os.path.join(root, "cache", "exchange_calendar.json")


def _parse_date_str(s: str) -> Optional[date]:
    s = (s or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _load_json_dates(path: str) -> Set[date]:
    out: Set[date] = set()
    if not os.path.isfile(path):
        return out
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        if isinstance(payload, dict):
            items = payload.get("dates") or payload.get("holidays") or []
        elif isinstance(payload, list):
            items = payload
        else:
            items = []
        for raw in items:
            if isinstance(raw, dict):
                raw = raw.get("date") or raw.get("tradingDate") or raw.get("holiday")
            d = _parse_date_str(str(raw))
            if d:
                out.add(d)
    except (json.JSONDecodeError, OSError):
        pass
    return out


def _try_kite_holidays_api() -> Tuple[Set[date], Optional[str]]:
    """Best-effort GET /market/holidays (not in official Python SDK routes)."""
    try:
        import kite_data

        if not kite_data.kite_enabled():
            return set(), "Kite disabled"
        kite, err = kite_data._get_kite()
        if err or not kite:
            return set(), err
        access_token, _ = kite_auth.get_access_token()
        if not access_token:
            return set(), "No access token"
        api_key = os.environ.get("KITE_API_KEY", "").strip()
        headers = {
            "Authorization": f"token {api_key}:{access_token}",
            "X-Kite-Version": kite.kite_header_version,
        }
        resp = kite.reqsession.get(
            f"{kite.root}/market/holidays",
            headers=headers,
            timeout=kite.timeout,
        )
        if resp.status_code == 404:
            return set(), "Kite /market/holidays not available (404)"
        if resp.status_code != 200:
            return set(), f"Kite holidays HTTP {resp.status_code}"
        data = resp.json()
        body = data.get("data") if isinstance(data, dict) else data
        out: Set[date] = set()
        if isinstance(body, list):
            for row in body:
                if isinstance(row, dict):
                    d = _parse_date_str(str(row.get("date") or row.get("trading_date") or ""))
                    if d:
                        out.add(d)
        return out, None if out else "Empty Kite holidays payload"
    except Exception as exc:
        return set(), str(exc)


def _fetch_nse_holidays() -> Tuple[Set[date], Optional[str]]:
    if nse_session is None:
        return set(), "nse_session unavailable"
    session = nse_session.nse_session()
    if session is None:
        return set(), "NSE session failed"
    out: Set[date] = set()
    try:
        for typ in ("trading", "clearing"):
            r = session.get(NSE_HOLIDAY_URL, params={"type": typ}, timeout=35)
            if r.status_code == 403:
                nse_session.reset_session()
                return set(), "NSE 403"
            if r.status_code != 200:
                continue
            payload = r.json()
            if isinstance(payload, list):
                for block in payload:
                    for row in block.get("tradingDate") or block.get("CM") or []:
                        if isinstance(row, dict):
                            d = _parse_date_str(str(row.get("tradingDate") or row.get("date") or ""))
                            if d:
                                out.add(d)
            elif isinstance(payload, dict):
                for rows in payload.values():
                    if isinstance(rows, list):
                        for row in rows:
                            if isinstance(row, dict):
                                d = _parse_date_str(str(row.get("tradingDate") or ""))
                                if d:
                                    out.add(d)
        return out, None if out else "NSE returned no dates"
    except Exception as exc:
        return set(), str(exc)


def refresh_calendar(force_nse: bool = True) -> Dict[str, Any]:
    global _holidays, _last_load_error
    merged: Set[date] = set()
    merged |= _load_json_dates(_seed_path())
    merged |= _load_json_dates(_cache_path())

    sources: Dict[str, Any] = {"seed": len(_load_json_dates(_seed_path()))}
    kite_set, kite_err = _try_kite_holidays_api()
    if kite_set:
        merged |= kite_set
        sources["kite_api"] = len(kite_set)
    else:
        sources["kite_api_error"] = kite_err

    if force_nse:
        nse_set, nse_err = _fetch_nse_holidays()
        if nse_set:
            merged |= nse_set
            sources["nse_api"] = len(nse_set)
        else:
            sources["nse_api_error"] = nse_err

    if merged:
        payload = {
            "updated_at": datetime.now().isoformat(),
            "dates": sorted(d.isoformat() for d in merged),
            "sources": sources,
        }
        try:
            with open(_cache_path(), "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
        except OSError as exc:
            _last_load_error = str(exc)
        _holidays = merged
        _last_load_error = None
    else:
        _last_load_error = "No holiday dates loaded"

    return get_status()


def ensure_loaded() -> Set[date]:
    global _holidays
    if _holidays is not None:
        return _holidays
    merged = set()
    merged |= _load_json_dates(_seed_path())
    merged |= _load_json_dates(_cache_path())
    _holidays = merged
    return _holidays


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def is_exchange_holiday(d: Optional[date] = None) -> bool:
    d = d or market_symbols.ist_now().date()
    if is_weekend(d):
        return True
    return d in ensure_loaded()


def is_trading_day(d: Optional[date] = None) -> bool:
    return not is_exchange_holiday(d)


def is_market_hours(now: Optional[datetime] = None) -> bool:
    now = now or market_symbols.ist_now()
    if is_exchange_holiday(now.date()):
        return False
    t = now.time()
    return MARKET_OPEN <= t <= MARKET_CLOSE


def should_apply_live_daily_bar(now: Optional[datetime] = None) -> Tuple[bool, str]:
    """Whether to patch today's OHLCV bar with live quote."""
    now = now or market_symbols.ist_now()
    d = now.date()
    if is_exchange_holiday(d):
        return False, "exchange_holiday_or_weekend"
    if now.time() < MARKET_OPEN:
        return False, "premarket"
    return True, "ok"


def next_trading_day(d: Optional[date] = None) -> date:
    d = d or market_symbols.ist_now().date()
    cur = d
    for _ in range(14):
        if is_trading_day(cur):
            return cur
        cur += timedelta(days=1)
    return d


def get_status() -> Dict[str, Any]:
    hol = ensure_loaded()
    today = market_symbols.ist_now().date()
    apply_ok, reason = should_apply_live_daily_bar()
    return {
        "holiday_count": len(hol),
        "today": today.isoformat(),
        "is_trading_day": is_trading_day(today),
        "is_market_hours": is_market_hours(),
        "apply_live_daily_bar": apply_ok,
        "apply_live_reason": reason,
        "cache_file": _cache_path(),
        "last_error": _last_load_error,
        "note": "Kite Connect has no official holidays API; calendar uses seed + NSE refresh.",
    }
