"""Index option gamma exposure from Kite NFO chain (nearest expiry).

Dealers are treated as short retail: calls add GEX, puts subtract.
Positive net GEX → pin / range. Negative → trend / squeeze.
"""

from __future__ import annotations

import math
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

CACHE_TTL_SEC = 60.0
BAND_FRAC = 0.045
MAX_STRIKES = 36
RATE = 0.065

_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_gamma(spot: float, strike: float, t_years: float, iv: float, r: float = RATE) -> float:
    if spot <= 0 or strike <= 0 or iv <= 0 or t_years <= 1.0 / 365.0 / 4.0:
        return 0.0
    sqrt_t = math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * t_years) / (iv * sqrt_t)
    return _norm_pdf(d1) / (spot * iv * sqrt_t)


def years_to_expiry(expiry: str, *, today: Optional[date] = None) -> float:
    day = today or date.today()
    try:
        exp = datetime.strptime(str(expiry)[:10], "%Y-%m-%d").date()
    except ValueError:
        return 7.0 / 365.0
    days = max((exp - day).days, 0) + 0.4
    return max(days / 365.0, 0.5 / 365.0)


def _iv_skew(legs: List[Dict[str, Any]], spot: float) -> float:
    """OTM put IV minus OTM call IV. Positive = downside protection is richer. 0 if quotes lack IV."""
    if spot <= 0:
        return 0.0
    put_ivs: List[float] = []
    call_ivs: List[float] = []
    for leg in legs:
        k = float(leg.get("strike") or 0)
        if k <= 0:
            continue
        pe = float(leg.get("pe_iv") or 0)
        ce = float(leg.get("ce_iv") or 0)
        if pe > 2:
            pe = pe / 100.0
        if ce > 2:
            ce = ce / 100.0
        if k <= spot * 0.99 and pe > 0.02:
            put_ivs.append(pe)
        if k >= spot * 1.01 and ce > 0.02:
            call_ivs.append(ce)
    if not put_ivs or not call_ivs:
        return 0.0
    return (sum(put_ivs) / len(put_ivs)) - (sum(call_ivs) / len(call_ivs))


def gex_from_legs(
    legs: List[Dict[str, Any]],
    *,
    spot: float,
    vix_pct: float = 12.0,
) -> Dict[str, Any]:
    """legs: strike, ce_oi, pe_oi, lot, iv (optional 0-2), expiry."""
    if not legs or spot <= 0:
        return {"available": False, "reason": "no_legs"}
    iv_flat = max(float(vix_pct or 12.0) / 100.0, 0.08)
    call_gex = 0.0
    put_gex = 0.0
    n = 0
    lot = 1.0
    expiry = ""
    for leg in legs:
        k = float(leg.get("strike") or 0)
        if k <= 0:
            continue
        lot = float(leg.get("lot") or lot or 1) or 1.0
        expiry = str(leg.get("expiry") or expiry)
        t = years_to_expiry(expiry)
        iv = float(leg.get("iv") or 0)
        if iv > 2:
            iv = iv / 100.0
        if iv <= 0:
            iv = iv_flat
        g = bs_gamma(spot, k, t, iv)
        ce_oi = float(leg.get("ce_oi") or 0)
        pe_oi = float(leg.get("pe_oi") or 0)
        # Point GEX: OI × gamma × spot × lot. Call +, put − (dealer short retail).
        call_gex += ce_oi * g * spot * lot
        put_gex -= pe_oi * g * spot * lot
        n += 1
    net = call_gex + put_gex
    mag = abs(call_gex) + abs(put_gex)
    flip = (net / mag) if mag > 0 else 0.0
    if flip >= 0.22:
        bias, note = "PIN", "Options GEX is positive — dealers likely to pin; treat as a range day."
    elif flip <= -0.22:
        bias, note = "SQUEEZE", "Options GEX is negative — dealers short gamma; a trend day is more likely."
    else:
        bias, note = "MIXED", "Options GEX is balanced — no pin or squeeze signal."
    return {
        "available": True,
        "iv_skew": round(_iv_skew(legs, spot), 4),
        "net": round(net, 0),
        "call_gex": round(call_gex, 0),
        "put_gex": round(put_gex, 0),
        "flip": round(flip, 3),
        "bias": bias,
        "note": note,
        "n_strikes": n,
        "expiry": expiry,
        "spot": round(spot, 2),
        "lot": lot,
    }


def snapshot(
    stock_key: str,
    spot: float,
    *,
    vix_level: float = 0.0,
    force: bool = False,
) -> Dict[str, Any]:
    key = (stock_key or "").strip().upper()
    now = time.time()
    hit = _cache.get(key)
    if not force and hit and now - hit[0] < CACHE_TTL_SEC:
        return dict(hit[1])
    try:
        import fno_instruments
        import kite_data

        if not kite_data.kite_enabled():
            out = {"available": False, "reason": "kite_off"}
            _cache[key] = (now, out)
            return out
        chain = fno_instruments.list_option_chain(key, float(spot or 0))
        if not chain.get("available"):
            out = {"available": False, "reason": chain.get("error") or "no_chain"}
            _cache[key] = (now, out)
            return out
        keys = list(chain.get("quote_keys") or [])
        quotes, err = kite_data.quote_many(keys)
        if err and not quotes:
            out = {"available": False, "reason": err}
            _cache[key] = (now, out)
            return out
        legs = []
        by_strike: Dict[float, Dict[str, Any]] = {}
        lot = float(chain.get("lot_size") or 1)
        expiry = str(chain.get("expiry") or "")
        for row in chain.get("rows") or []:
            ts = str(row.get("tradingsymbol") or "")
            qkey = fno_instruments.quote_key(row)
            raw = quotes.get(qkey) or quotes.get(ts) or {}
            oi = raw.get("oi")
            try:
                oi_n = float(oi or 0)
            except (TypeError, ValueError):
                oi_n = 0.0
            iv = raw.get("implied_volatility")
            try:
                iv_n = float(iv) if iv not in (None, 0, "0") else 0.0
            except (TypeError, ValueError):
                iv_n = 0.0
            k = float(row.get("strike") or 0)
            slot = by_strike.setdefault(
                k,
                {
                    "strike": k, "lot": lot, "expiry": expiry,
                    "ce_oi": 0.0, "pe_oi": 0.0, "iv": 0.0, "ce_iv": 0.0, "pe_iv": 0.0,
                },
            )
            if row.get("instrument_type") == "CE":
                slot["ce_oi"] = oi_n
                if iv_n > 0:
                    slot["ce_iv"] = iv_n
            else:
                slot["pe_oi"] = oi_n
                if iv_n > 0:
                    slot["pe_iv"] = iv_n
            if iv_n > slot["iv"]:
                slot["iv"] = iv_n
        legs = [by_strike[k] for k in sorted(by_strike)]
        out = gex_from_legs(legs, spot=float(spot), vix_pct=float(vix_level or 12.0))
        if quotes:
            out["quoted"] = len(quotes)
        _cache[key] = (now, out)
        return dict(out)
    except Exception as exc:
        out = {"available": False, "reason": str(exc)}
        _cache[key] = (now, out)
        return out
