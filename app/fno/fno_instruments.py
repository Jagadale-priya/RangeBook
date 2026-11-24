"""Resolve NFO/BFO futures and ATM options from cached Kite instruments."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import fno_universe
import kite_instruments
import product_analysis

NFO_CACHE_NAME = "nfo_underlyings.json"

# Kite `name` field on NFO rows
UNDERLYING_BY_KEY: Dict[str, str] = {
    "NIFTY": "NIFTY",
    "BANKNIFTY": "BANKNIFTY",
    "FINNIFTY": "FINNIFTY",
    "SENSEX": "SENSEX",
}


def _data_dir() -> str:
    return kite_instruments.cache_dir()


def _nfo_path() -> str:
    return os.path.join(_data_dir(), NFO_CACHE_NAME)


def underlying_name(stock_key: str) -> str:
    k = stock_key.strip().upper()
    return UNDERLYING_BY_KEY.get(k, k)


def allowed_underlying_names() -> set:
    names = set(UNDERLYING_BY_KEY.values())
    names.update(product_analysis.FNO_STOCK_UNIVERSE)
    names.update(fno_universe.symbols())
    return names


def save_nfo_subset(rows: List[Dict[str, Any]]) -> int:
    """Persist compact NFO/BFO rows for supported underlyings (called from instrument refresh)."""
    allowed = allowed_underlying_names()
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        exchange = str(row.get("exchange") or "").upper()
        if exchange not in ("NFO", "BFO"):
            continue
        name = str(row.get("name") or "").strip().upper()
        if name not in allowed or exchange != fno_universe.derivatives_exchange(name):
            continue
        exp = row.get("expiry")
        if hasattr(exp, "isoformat"):
            exp_s = exp.isoformat()[:10]
        else:
            exp_s = str(exp)[:10] if exp else ""
        out.append(
            {
                "name": name,
                "exchange": exchange,
                "tradingsymbol": str(row.get("tradingsymbol") or ""),
                "instrument_type": str(row.get("instrument_type") or ""),
                "expiry": exp_s,
                "strike": float(row.get("strike") or 0),
                "lot_size": int(row.get("lot_size") or 0),
                "tick_size": float(row.get("tick_size") or 0.05),
            }
        )
    os.makedirs(_data_dir(), exist_ok=True)
    with open(_nfo_path(), "w", encoding="utf-8") as fh:
        json.dump({"saved_at": datetime.now().isoformat(), "rows": out}, fh)
    return len(out)


def nfo_row_count() -> int:
    return len(_load_nfo_rows())


def _load_nfo_rows() -> List[Dict[str, Any]]:
    p = _nfo_path()
    if not os.path.isfile(p):
        return []
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return list(data.get("rows") or [])
    except (json.JSONDecodeError, OSError):
        return []


def row_exchange(row: Dict[str, Any]) -> str:
    return str(row.get("exchange") or fno_universe.derivatives_exchange(row.get("name"))).upper()


def quote_key(row: Dict[str, Any]) -> str:
    return f"{row_exchange(row)}:{row['tradingsymbol']}"


def _parse_expiry(exp_s: str) -> Optional[date]:
    if not exp_s:
        return None
    try:
        return datetime.strptime(exp_s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def resolve_contracts(
    stock_key: str,
    spot_price: float,
    *,
    prefer_weekly: bool = True,
) -> Dict[str, Any]:
    """
    Nearest liquid expiry future + ATM CE/PE for underlying.
    Requires Kite instruments cache (POST /kite/instruments/refresh).
    """
    kite_instruments.ensure_cache()
    rows = _load_nfo_rows()
    if not rows:
        import kite_data

        if kite_data.kite_enabled():
            kite_instruments.refresh_instruments(force=True)
            rows = _load_nfo_rows()
    uname = underlying_name(stock_key)
    if not rows:
        return {
            "available": False,
            "error": "F&O contract cache empty — run GET /kite/instruments/refresh with Kite connected",
            "underlying": uname,
        }

    today = date.today()
    subset = [r for r in rows if r.get("name") == uname]
    if not subset:
        return {"available": False, "error": f"No NFO rows for {uname}", "underlying": uname}

    futures = []
    for r in subset:
        if r.get("instrument_type") != "FUT":
            continue
        exp = _parse_expiry(r.get("expiry", ""))
        if exp and exp >= today:
            futures.append((exp, r))
    if not futures:
        return {"available": False, "error": "No active future expiry found", "underlying": uname}

    futures.sort(key=lambda x: x[0])
    fut_exp = futures[0][0]
    fut_row = futures[0][1]

    # ATM CE/PE use the same option-expiry rule as option_ticket (weekly-first),
    # not the futures expiry — keeps Contracts ATM aligned with 3-pack suggestions.
    opt_exps: List[date] = []
    for r in subset:
        if r.get("instrument_type") not in ("CE", "PE"):
            continue
        exp = _parse_expiry(r.get("expiry", ""))
        if exp and exp >= today:
            opt_exps.append(exp)
    try:
        import option_ticket

        opt_exp = option_ticket.select_expiry(opt_exps, today) if prefer_weekly else fut_exp
    except Exception:
        opt_exp = fut_exp
    if opt_exp is None:
        opt_exp = fut_exp

    opts = [
        r
        for r in subset
        if r.get("instrument_type") in ("CE", "PE") and _parse_expiry(r.get("expiry", "")) == opt_exp
    ]
    spot = float(spot_price or 0)
    ce_rows = [r for r in opts if r.get("instrument_type") == "CE" and r.get("strike")]
    pe_rows = [r for r in opts if r.get("instrument_type") == "PE" and r.get("strike")]

    def _atm(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not candidates or spot <= 0:
            return None
        return min(candidates, key=lambda r: abs(float(r["strike"]) - spot))

    atm_ce = _atm(ce_rows)
    atm_pe = _atm(pe_rows)

    def _pack(r: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not r:
            return None
        return {
            "tradingsymbol": r["tradingsymbol"],
            "exchange": row_exchange(r),
            "strike": r.get("strike"),
            "lot_size": r.get("lot_size"),
            "expiry": r.get("expiry"),
        }

    return {
        "available": True,
        "underlying": uname,
        "spot_reference": round(spot, 2),
        "expiry": opt_exp.isoformat(),
        "future_expiry": fut_exp.isoformat(),
        "option_expiry": opt_exp.isoformat(),
        "future": {
            "tradingsymbol": fut_row["tradingsymbol"],
            "exchange": row_exchange(fut_row),
            "lot_size": fut_row.get("lot_size"),
            "expiry": fut_row.get("expiry"),
        },
        "atm_ce": _pack(atm_ce),
        "atm_pe": _pack(atm_pe),
        "prefer_weekly": prefer_weekly,
    }


def list_option_chain(
    stock_key: str,
    spot_price: float,
    *,
    band_frac: float = 0.045,
    max_strikes: int = 36,
) -> Dict[str, Any]:
    """Nearest option expiry, strikes within band_frac of spot (CE+PE)."""
    kite_instruments.ensure_cache()
    rows = _load_nfo_rows()
    uname = underlying_name(stock_key)
    if not rows:
        return {"available": False, "error": "NFO cache empty", "underlying": uname}
    today = date.today()
    subset = [r for r in rows if r.get("name") == uname]
    exps = []
    for r in subset:
        if r.get("instrument_type") not in ("CE", "PE"):
            continue
        exp = _parse_expiry(r.get("expiry", ""))
        if exp and exp >= today:
            exps.append(exp)
    if not exps:
        return {"available": False, "error": f"No option expiry for {uname}", "underlying": uname}
    chosen = min(exps)
    spot = float(spot_price or 0)
    if spot <= 0:
        return {"available": False, "error": "Need spot to pick strikes", "underlying": uname}
    band = spot * float(band_frac)
    opts = [
        r
        for r in subset
        if r.get("instrument_type") in ("CE", "PE")
        and _parse_expiry(r.get("expiry", "")) == chosen
        and abs(float(r.get("strike") or 0) - spot) <= band
        and float(r.get("strike") or 0) > 0
    ]
    strikes = sorted({float(r["strike"]) for r in opts})
    if len(strikes) > max_strikes:
        strikes = sorted(strikes, key=lambda k: abs(k - spot))[:max_strikes]
        want = set(strikes)
        opts = [r for r in opts if float(r["strike"]) in want]
    if not opts:
        return {"available": False, "error": "No strikes in band", "underlying": uname}
    lot = int(opts[0].get("lot_size") or 0) or 1
    quote_keys = [quote_key(r) for r in opts if r.get("tradingsymbol")]
    return {
        "available": True,
        "underlying": uname,
        "expiry": chosen.isoformat(),
        "lot_size": lot,
        "n": len(opts),
        "quote_keys": quote_keys,
        "rows": opts,
    }


def get_status() -> Dict[str, Any]:
    rows = _load_nfo_rows()
    return {
        "nfo_rows_cached": len(rows),
        "cache_path": _nfo_path(),
        "underlyings": sorted({r.get("name") for r in rows if r.get("name")}),
    }
