"""Live option guide for an index call: contract, entry, stop, and target.

For T30/SL30 index tickets we size premium SL/T from estimated Δ and keep
per-trade rupee loss ≤ max_loss_inr (default ₹2000, UI-configurable).

Each call surfaces three accurate suggestions (same side):
  1. lower_premium — cheapest eligible fill
  2. higher_profit — max premium target rupees under the loss cap
  3. lower_loss — smallest planned SL rupees under the loss cap
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

# Index risk/reward clips — NIFTY locked to ±30 with FINAL live books.
INDEX_CLIP = {
    "NIFTY": (30.0, 30.0),
    # Locked FINAL research 2026-11-16 (BN_FINAL / SENSEX_FINAL reports)
    "BANKNIFTY": (75.0, 75.0),
    "SENSEX": (100.0, 100.0),
    "FINNIFTY": (30.0, 30.0),
}
DEFAULT_MAX_LOSS_INR = 2000.0
IST = ZoneInfo("Asia/Kolkata")
SUGGEST_ROLES = ("lower_premium", "higher_profit", "lower_loss")


def resolve_max_loss_inr(
    explicit: Optional[float] = None,
    *,
    snapshot: Optional[Dict[str, Any]] = None,
) -> float:
    """Prefer explicit → Flask request → snapshot option/contracts cap → ₹2000.

    Background watch has no request context; use the last desk cap from snapshot.
    """
    if explicit is not None:
        try:
            v = float(explicit)
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass
    try:
        from flask import has_request_context, request

        if has_request_context():
            ml = request.args.get("max_loss", type=float)
            if ml is None:
                body = request.get_json(silent=True) or {}
                raw = body.get("max_loss")
                ml = float(raw) if raw is not None else None
            if ml is not None and float(ml) > 0:
                return float(ml)
    except Exception:
        pass
    snap = snapshot or {}
    for bag in (snap.get("option_order"), snap.get("fno_contracts")):
        if isinstance(bag, dict) and bag.get("max_loss_inr") is not None:
            try:
                v = float(bag.get("max_loss_inr"))
                if v > 0:
                    return v
            except (TypeError, ValueError):
                pass
    return float(DEFAULT_MAX_LOSS_INR)


def _f(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def select_expiry(expiries: List[date], today: date) -> Optional[date]:
    """Nearest expiry that is still ahead. Skip a contract that expires today."""
    ahead = sorted({exp for exp in expiries if exp >= today})
    if not ahead:
        return None
    if ahead[0] == today and len(ahead) > 1:
        return ahead[1]
    return ahead[0]


def _step(strikes: List[float]) -> float:
    ordered = sorted(set(strikes))
    gaps = [b - a for a, b in zip(ordered, ordered[1:]) if b > a]
    if not gaps:
        return 50.0
    gaps.sort()
    return gaps[len(gaps) // 2]


def nearby_strikes(strikes: List[float], spot: float, right: str, *, near_only: bool = False) -> List[float]:
    """Front-expiry strikes around the live price, four steps each side.

    On an expiry day the band is the at-the-money strike and one step in the money.
    """
    ordered = sorted(set(strikes))
    if not ordered or spot <= 0:
        return []
    atm = min(ordered, key=lambda k: abs(k - spot))
    i = ordered.index(atm)
    if near_only:
        if right == "CE":
            itm_i = i - 1 if i > 0 else i
        else:
            itm_i = i + 1 if i + 1 < len(ordered) else i
        picked: List[float] = []
        for idx in (itm_i, i):
            if ordered[idx] not in picked:
                picked.append(ordered[idx])
        return picked
    return ordered[max(0, i - 4) : min(len(ordered), i + 5)]


def _moneyness(spot: float, strike: float, right: str, step: float) -> float:
    width = step if step > 0 else 1.0
    if right == "CE":
        return (spot - strike) / width
    return (strike - spot) / width


def _score(spot: float, strike: float, right: str, step: float, quote: Dict[str, Any]) -> Optional[float]:
    last = _f(quote.get("last_price"))
    if last is None or last <= 0:
        return None
    itm = _moneyness(spot, strike, right, step)
    near = -0.05 <= itm <= 1.05
    fit = 0.0 if near else abs(itm) * 3.0
    itm_bonus = 0.6 if 0 < itm <= 1.05 else 0.0
    oi = _f(quote.get("oi")) or 0.0
    vol = _f(quote.get("volume")) or 0.0
    liq = math.log1p(max(oi, 0.0)) + 0.25 * math.log1p(max(vol, 0.0))
    return liq + itm_bonus - fit


def _delta(spot: float, strike: float, right: str, step: float) -> float:
    return max(0.35, min(0.70, 0.50 + 0.08 * _moneyness(spot, strike, right, step)))


def _target_delta(asof: Any = None) -> float:
    """Varsity: aim ~0.60Δ ITM; late session bump for theta (see fno_pdf_accuracy)."""
    try:
        import fno_pdf_accuracy

        hour = None
        if asof is not None:
            hour = float(asof.hour) + float(asof.minute) / 60.0
        return float(fno_pdf_accuracy.option_target_delta(hour=hour))
    except Exception:
        return 0.60


def _index_points(
    symbol: str,
    decision: str,
    spot: float,
    index_stop: Optional[float],
    index_target: Optional[float],
) -> Tuple[float, float]:
    clip = INDEX_CLIP.get(symbol, (25.0, 30.0))
    risk = reward = None
    if decision == "BUY" and index_stop is not None and index_target is not None:
        risk = spot - float(index_stop)
        reward = float(index_target) - spot
    elif decision == "SELL" and index_stop is not None and index_target is not None:
        risk = float(index_stop) - spot
        reward = spot - float(index_target)
    if risk is None or reward is None or risk <= 0 or reward <= 0:
        return clip
    return risk, reward


def _premium_levels(entry: float, risk: float, reward: float, delta: float) -> Tuple[float, float, str]:
    note = ""
    raw_stop = entry - delta * risk
    if raw_stop < 0.05:
        stop = round(max(0.05, entry * 0.5), 2)
        note = " Premium is small, so exit when the index hits its stop."
    else:
        stop = round(raw_stop, 2)
    target = round(entry + delta * reward, 2)
    if target <= entry:
        target = round(entry + 0.5, 2)
    if stop >= entry:
        stop = round(max(0.05, entry - 0.5), 2)
    return stop, target, note


def _lots_for_max_loss(sl_rupees_1lot: float, max_loss_inr: float) -> int:
    """Largest whole-lot size whose planned SL rupees stay ≤ max_loss."""
    if sl_rupees_1lot <= 0:
        return 1
    if sl_rupees_1lot > max_loss_inr:
        return 0
    return max(1, int(max_loss_inr // sl_rupees_1lot))


def _pack_leg(
    *,
    symbol_text: str,
    right: str,
    index_side: str,
    underlying: str,
    expiry: str,
    strike: float,
    entry: float,
    stop: float,
    target: float,
    delta: float,
    target_d: float,
    lot_size: int,
    risk: float,
    reward: float,
    max_loss_inr: float,
    score: float,
    place: str,
    small_note: str,
    role: Optional[str] = None,
) -> Dict[str, Any]:
    lot = max(1, int(lot_size or 1))
    sl_pts = max(0.0, round(entry - stop, 2))
    t_pts = max(0.0, round(target - entry, 2))
    sl_1 = round(sl_pts * lot, 2)
    t_1 = round(t_pts * lot, 2)
    wipe_1 = round(entry * lot, 2)
    lots = _lots_for_max_loss(sl_1, max_loss_inr)
    fits = lots >= 1
    sl_rupees = round(sl_1 * max(lots, 1), 2) if fits else sl_1
    t_rupees = round(t_1 * max(lots, 1), 2) if fits else t_1
    right_name = "call" if right == "CE" else "put"
    order_line = (
        f"BUY {lots} lot{'s' if lots != 1 else ''} {symbol_text} at ₹{entry:.2f}. "
        f"Stop ₹{stop:.2f}. Target ₹{target:.2f}."
        if fits
        else f"SKIP {symbol_text} — 1-lot SL ₹{sl_1:.0f} exceeds max loss ₹{max_loss_inr:.0f}."
    )
    why = (
        f"{expiry} {int(strike) if float(strike).is_integer() else strike} {right_name}, {place}. "
        f"Index {underlying} {index_side} · ±{risk:.0f}/{reward:.0f} pts → premium SL/T via Δ≈{delta:.0%}. "
        f"Planned SL ₹{sl_rupees:.0f} · Target ₹{t_rupees:.0f} · lot {lot} × {max(lots, 1)} "
        f"(cap ₹{max_loss_inr:.0f}).{small_note}"
    )
    out: Dict[str, Any] = {
        "available": True,
        "action": "BUY",
        "right": right,
        "index_decision": index_side,
        "underlying": underlying,
        "tradingsymbol": symbol_text,
        "expiry": expiry,
        "strike": strike,
        "entry": entry,
        "stop_loss": stop,
        "target": target,
        "delta": round(delta, 2),
        "target_delta": round(target_d, 2),
        "lot_size": lot,
        "lots": lots if fits else 0,
        "index_risk_pts": round(risk, 2),
        "index_reward_pts": round(reward, 2),
        "sl_premium_pts": sl_pts,
        "target_premium_pts": t_pts,
        "sl_rupees": sl_rupees,
        "target_rupees": t_rupees,
        "wipeout_rupees_1lot": wipe_1,
        "max_loss_inr": float(max_loss_inr),
        "fits_max_loss": fits,
        "score": round(score, 3),
        "order_line": order_line,
        "why": why,
        "quote_source": "kite",
    }
    if role:
        out["role"] = role
        out["role_label"] = {
            "lower_premium": "Lower premium",
            "higher_profit": "Higher profit",
            "lower_loss": "Lower loss",
        }.get(role, role)
    return out


def _role_pick(eligible: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Pick three roles from eligible legs (fits_max_loss=True)."""
    if not eligible:
        return {}
    by_prem = sorted(eligible, key=lambda r: (float(r["entry"]), -float(r.get("score") or 0)))
    by_profit = sorted(
        eligible,
        key=lambda r: (float(r.get("target_rupees") or 0), float(r.get("score") or 0)),
        reverse=True,
    )
    by_loss = sorted(
        eligible,
        key=lambda r: (float(r.get("sl_rupees") or 0), -float(r.get("score") or 0)),
    )
    picked: Dict[str, Dict[str, Any]] = {}
    used = set()

    def take(role: str, ordered: List[Dict[str, Any]]) -> None:
        for row in ordered:
            key = row.get("tradingsymbol")
            if key in used and len(eligible) > 1:
                continue
            item = dict(row)
            item["role"] = role
            item["role_label"] = {
                "lower_premium": "Lower premium",
                "higher_profit": "Higher profit",
                "lower_loss": "Lower loss",
            }[role]
            picked[role] = item
            used.add(key)
            return
        # fallback: allow reuse if chain is thin
        if ordered:
            item = dict(ordered[0])
            item["role"] = role
            item["role_label"] = {
                "lower_premium": "Lower premium",
                "higher_profit": "Higher profit",
                "lower_loss": "Lower loss",
            }[role]
            picked[role] = item

    take("lower_premium", by_prem)
    take("higher_profit", by_profit)
    take("lower_loss", by_loss)
    return picked


def _book_prices(quote: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """Best bid and ask. A buy fills at the ask."""
    bid = _f(quote.get("bid"))
    ask = _f(quote.get("ask"))
    depth = quote.get("depth") or {}
    if bid is None:
        buys = depth.get("buy") or []
        if buys and isinstance(buys[0], dict):
            bid = _f(buys[0].get("price"))
    if ask is None:
        sells = depth.get("sell") or []
        if sells and isinstance(sells[0], dict):
            ask = _f(sells[0].get("price"))
    return bid, ask


def tradable_price(quote: Dict[str, Any]) -> Optional[float]:
    """Ask when the book is tight. A wide book is not a price we can use.

    When live_book_required is False (Contracts desk), fall back to last traded
    premium if depth is empty — common in the first minutes after open.
    """
    require_book = bool(quote.get("live_book_required"))
    try:
        age = float(quote["staleness_ms"]) if quote.get("staleness_ms") is not None else None
    except (TypeError, ValueError):
        age = None
    if age is not None:
        # Strict guide: 30s. Desk LTP fallback: allow up to 5 minutes.
        if require_book and age > 30_000:
            return None
        if not require_book and age > 300_000:
            return None
    last = _f(quote.get("last_price"))
    bid, ask = _book_prices(quote)
    if bid is None or ask is None or bid <= 0 or ask < bid:
        if require_book:
            return None
        return last if last and last > 0 else None
    mid = (bid + ask) / 2.0
    if mid <= 0 or (ask - bid) / mid > 0.08:
        if require_book:
            return None
        return last if last and last > 0 else None
    return ask


def _kite_quotes(
    symbols: List[str],
    exchange: str = "NFO",
    *,
    require_live_book: bool = True,
) -> Tuple[Dict[str, Dict[str, Any]], Optional[str]]:
    import kite_data

    keys = [f"{exchange}:{sym}" for sym in symbols]
    rows, err = kite_data.quote_many(keys)
    out: Dict[str, Dict[str, Any]] = {}
    for key, raw in (rows or {}).items():
        sym = str(key).split(":", 1)[-1]
        stamp = raw.get("timestamp") or raw.get("exchange_timestamp")
        age_ms = None
        if stamp is not None:
            try:
                dt = stamp if isinstance(stamp, datetime) else datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=IST)
                age_ms = max(0, int((datetime.now(IST) - dt.astimezone(IST)).total_seconds() * 1000))
            except (TypeError, ValueError, OSError):
                age_ms = None
        out[sym] = {
            "last_price": raw.get("last_price"),
            "oi": raw.get("oi"),
            "volume": raw.get("volume"),
            "depth": raw.get("depth") or {},
            "staleness_ms": raw.get("staleness_ms") if raw.get("staleness_ms") is not None else age_ms,
            "exchange_timestamp": stamp,
            # Contracts desk allows LTP fallback near open when depth is empty;
            # open-call guide keeps require_live_book=True for a tight ask.
            "live_book_required": bool(require_live_book),
        }
    return out, err


def weekly_expires_today(symbol: str, today: Optional[date] = None) -> bool:
    """True when this index has a listed option expiring today."""
    day = today or date.today()
    try:
        chain = _chain_rows(symbol)
    except Exception:
        return False
    import fno_instruments

    for row in chain:
        if row.get("instrument_type") not in ("CE", "PE"):
            continue
        if fno_instruments._parse_expiry(str(row.get("expiry") or "")) == day:
            return True
    return False


def _chain_rows(symbol: str) -> List[Dict[str, Any]]:
    import fno_instruments

    name = fno_instruments.underlying_name(symbol)
    return [r for r in fno_instruments._load_nfo_rows() if r.get("name") == name]


def _build_legs_for_side(
    symbol: str,
    index_side: str,
    *,
    spot: float,
    index_stop: Optional[float] = None,
    index_target: Optional[float] = None,
    max_loss_inr: float = DEFAULT_MAX_LOSS_INR,
    preferred_expiry: Optional[date] = None,
    rows: Optional[List[Dict[str, Any]]] = None,
    quote_fn: Optional[Callable[[List[str]], Tuple[Dict[str, Dict[str, Any]], Optional[str]]]] = None,
    today: Optional[date] = None,
    require_live_book: bool = True,
) -> Dict[str, Any]:
    """Rank CE (BUY) or PE (SELL) legs with premium SL/T and ₹ max-loss filter."""
    right = "CE" if index_side == "BUY" else "PE"
    name = symbol.strip().upper()
    px = _f(spot) or 0.0
    cap = float(max_loss_inr or DEFAULT_MAX_LOSS_INR)
    if px <= 0:
        return {"available": False, "right": right, "reason": "No live index price, so no option is chosen."}

    import fno_instruments

    chain = rows if rows is not None else _chain_rows(name)
    day = today or date.today()
    expiries = []
    for row in chain:
        if row.get("instrument_type") not in ("CE", "PE"):
            continue
        exp = fno_instruments._parse_expiry(str(row.get("expiry") or ""))
        if exp:
            expiries.append(exp)
    # Lock to Contracts ATM expiry when provided (same CE/PE week)
    if preferred_expiry is not None and any(
        abs((e - preferred_expiry).days) == 0 for e in expiries
    ):
        expiry = preferred_expiry
    else:
        expiry = select_expiry(expiries, day)
    if expiry is None:
        return {"available": False, "right": right, "reason": "No listed expiry in the option chain."}

    leg_rows = [
        r
        for r in chain
        if r.get("instrument_type") == right
        and fno_instruments._parse_expiry(str(r.get("expiry") or "")) == expiry
    ]
    strikes = sorted({float(r["strike"]) for r in leg_rows if _f(r.get("strike"))})
    if not strikes:
        return {
            "available": False,
            "right": right,
            "reason": f"No {right} strikes for {expiry.isoformat()}.",
        }

    step = _step(strikes)
    expiry_day = any(
        fno_instruments._parse_expiry(str(r.get("expiry") or "")) == day
        for r in chain
        if r.get("instrument_type") in ("CE", "PE")
    )
    chosen_strikes = nearby_strikes(strikes, px, right, near_only=expiry_day)
    by_strike: Dict[float, Dict[str, Any]] = {}
    for row in leg_rows:
        k = _f(row.get("strike"))
        if k is None or not row.get("tradingsymbol"):
            continue
        if any(abs(k - s) < 0.1 for s in chosen_strikes):
            by_strike[min(chosen_strikes, key=lambda s: abs(s - k))] = row

    symbols = [by_strike[s]["tradingsymbol"] for s in chosen_strikes if s in by_strike]
    if not symbols:
        return {
            "available": False,
            "right": right,
            "reason": "Chain has no tradable symbol at these strikes.",
        }

    quotes, _err = (
        quote_fn(symbols)
        if quote_fn
        else _kite_quotes(
            symbols,
            fno_instruments.row_exchange(leg_rows[0]),
            require_live_book=require_live_book,
        )
    )
    target_d = _target_delta(None)
    risk, reward = _index_points(name, index_side, px, index_stop, index_target)
    all_legs: List[Dict[str, Any]] = []
    for strike in chosen_strikes:
        row = by_strike.get(strike)
        if not row:
            continue
        quote = (quotes or {}).get(row["tradingsymbol"]) or {}
        fill = tradable_price(quote)
        if fill is None:
            continue
        quote = dict(quote)
        quote["last_price"] = fill
        score = _score(px, strike, right, step, quote)
        if score is None:
            continue
        itm = _moneyness(px, strike, right, step)
        if itm < -0.2:
            score -= 2.0
        elif 0 < itm <= 1.05:
            score += 0.4
        d_here = _delta(px, strike, right, step)
        score += max(0.0, 1.2 - abs(d_here - target_d) * 3.0)
        entry = round(float(fill), 2)
        stop, target, small_note = _premium_levels(entry, risk, reward, d_here)
        place = (
            "in the money"
            if itm > 0.15
            else ("at the money" if itm > -0.15 else "just out of the money")
        )
        # Prefer contracts whose planned SL fits the ₹ cap
        if _lots_for_max_loss(max(0.0, entry - stop) * max(1, int(row.get("lot_size") or 1)), cap) >= 1:
            score += 1.5
        # Prefer wipeout risk also under cap when possible
        if entry * max(1, int(row.get("lot_size") or 1)) <= cap:
            score += 0.8
        leg = _pack_leg(
            symbol_text=row["tradingsymbol"],
            right=right,
            index_side=index_side,
            underlying=name,
            expiry=expiry.isoformat(),
            strike=strike,
            entry=entry,
            stop=stop,
            target=target,
            delta=d_here,
            target_d=target_d,
            lot_size=int(row.get("lot_size") or 1),
            risk=risk,
            reward=reward,
            max_loss_inr=cap,
            score=score,
            place=place,
            small_note=small_note,
        )
        leg["strikes_checked"] = len(chosen_strikes)
        all_legs.append(leg)

    if not all_legs:
        return {
            "available": False,
            "right": right,
            "expiry": expiry.isoformat(),
            "index_decision": index_side,
            "max_loss_inr": cap,
            "reason": "Kite did not return a live price, so entry, stop, and target are withheld.",
        }

    eligible = [r for r in all_legs if r.get("fits_max_loss")]
    roles = _role_pick(eligible if eligible else all_legs)
    # Primary: lower_loss (safest under ₹2k), else higher_profit, else best score
    primary = (
        roles.get("lower_loss")
        or roles.get("higher_profit")
        or roles.get("lower_premium")
        or max(all_legs, key=lambda r: float(r.get("score") or 0))
    )
    primary = dict(primary)
    primary["suggestions"] = [roles[k] for k in SUGGEST_ROLES if k in roles]
    primary["suggestion_roles"] = list(SUGGEST_ROLES)
    primary["max_loss_inr"] = cap
    primary["index_stop"] = index_stop
    primary["index_target"] = index_target
    primary["eligible_count"] = len(eligible)
    primary["candidates_scanned"] = len(all_legs)
    if not eligible:
        primary["available"] = True
        primary["fits_max_loss"] = False
        primary["reason"] = (
            f"No contract keeps planned SL ≤ ₹{cap:.0f} at 1 lot — shown best effort; "
            "raise max loss in Settings or skip."
        )
    try:
        import groww_option_links

        primary = groww_option_links.enrich_option_guide(primary, name) or primary
        enriched = []
        for s in primary.get("suggestions") or []:
            enriched.append(groww_option_links.enrich_option_guide(dict(s), name) or s)
        primary["suggestions"] = enriched
    except Exception:
        pass
    return primary


def build_order(
    symbol: str,
    decision: str,
    *,
    spot: float,
    index_stop: Optional[float] = None,
    index_target: Optional[float] = None,
    max_loss_inr: float = DEFAULT_MAX_LOSS_INR,
    preferred_expiry: Optional[date] = None,
    rows: Optional[List[Dict[str, Any]]] = None,
    quote_fn: Optional[Callable[[List[str]], Tuple[Dict[str, Dict[str, Any]], Optional[str]]]] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """BUY the call for an index BUY, or BUY the put for an index SELL (+ 3 suggestions)."""
    side = str(decision or "HOLD").upper()
    if "SELL" in side:
        index_side = "SELL"
    elif "BUY" in side:
        index_side = "BUY"
    else:
        return {
            "available": False,
            "reason": "No option until the index call is BUY or SELL.",
        }
    return _build_legs_for_side(
        symbol,
        index_side,
        spot=spot,
        index_stop=index_stop,
        index_target=index_target,
        max_loss_inr=max_loss_inr,
        preferred_expiry=preferred_expiry,
        rows=rows,
        quote_fn=quote_fn,
        today=today,
    )


def build_contracts_suggestions(
    symbol: str,
    *,
    spot: float,
    index_stop: Optional[float] = None,
    index_target: Optional[float] = None,
    max_loss_inr: float = DEFAULT_MAX_LOSS_INR,
    preferred_expiry: Optional[date] = None,
    rows: Optional[List[Dict[str, Any]]] = None,
    quote_fn: Optional[Callable[[List[str]], Tuple[Dict[str, Dict[str, Any]], Optional[str]]]] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """BUY-side and SELL-side 3-packs for the Contracts desk (CE + PE).

    Allows last-traded premium when the live book is empty (common near open).
    """
    buy = _build_legs_for_side(
        symbol,
        "BUY",
        spot=spot,
        index_stop=index_stop,
        index_target=index_target,
        max_loss_inr=max_loss_inr,
        preferred_expiry=preferred_expiry,
        rows=rows,
        quote_fn=quote_fn,
        today=today,
        require_live_book=False,
    )
    sell = _build_legs_for_side(
        symbol,
        "SELL",
        spot=spot,
        index_stop=index_stop,
        index_target=index_target,
        max_loss_inr=max_loss_inr,
        preferred_expiry=preferred_expiry,
        rows=rows,
        quote_fn=quote_fn,
        today=today,
        require_live_book=False,
    )
    name = symbol.strip().upper()
    clip = INDEX_CLIP.get(name, (30.0, 30.0))
    avail = bool(buy.get("available") or sell.get("available"))
    reason = None
    if not avail:
        reason = buy.get("reason") or sell.get("reason") or "No live option quotes."
    elif not (buy.get("suggestions") or sell.get("suggestions")):
        reason = buy.get("reason") or sell.get("reason")
    # Stamp clip pts so fast-refresh keep_sug can validate without absolute SL/T.
    px = float(spot or 0)
    stamped_stop = index_stop
    stamped_target = index_target
    if stamped_stop is None and px > 0:
        stamped_stop = round(px - float(clip[0]), 2)
    if stamped_target is None and px > 0:
        stamped_target = round(px + float(clip[1]), 2)
    return {
        "available": avail,
        "underlying": name,
        "spot": round(px, 2),
        "max_loss_inr": float(max_loss_inr or DEFAULT_MAX_LOSS_INR),
        "index_brackets": {"stop_pts": float(clip[0]), "target_pts": float(clip[1])},
        "index_risk_pts": float(clip[0]),
        "index_reward_pts": float(clip[1]),
        "option_expiry": (buy.get("expiry") or sell.get("expiry")),
        "index_stop": stamped_stop,
        "index_target": stamped_target,
        "reason": reason,
        "buy": {
            "index_decision": "BUY",
            "right": "CE",
            "available": bool(buy.get("available")),
            "primary": buy if buy.get("available") else None,
            "suggestions": (buy.get("suggestions") if buy.get("available") else []) or [],
            "reason": buy.get("reason"),
        },
        "sell": {
            "index_decision": "SELL",
            "right": "PE",
            "available": bool(sell.get("available")),
            "primary": sell if sell.get("available") else None,
            "suggestions": (sell.get("suggestions") if sell.get("available") else []) or [],
            "reason": sell.get("reason"),
        },
    }


def attach_for_open_call(
    result: Dict[str, Any],
    symbol: str,
    active_call: Optional[Dict[str, Any]],
    spot: float,
    *,
    max_loss_inr: Optional[float] = None,
) -> Dict[str, Any]:
    """Price options for the open index call (3 suggestions + primary). Guidance only."""
    max_loss_inr = resolve_max_loss_inr(max_loss_inr)
    name = str(symbol or "").strip().upper()
    call = active_call or {}
    open_now = bool(call.get("open") or str(call.get("status") or "") == "open")
    side = str(call.get("decision") or "")
    import fno_universe

    if not fno_universe.contains(name) or not open_now or ("BUY" not in side and "SELL" not in side):
        order = {
            "available": False,
            "guide_only": True,
            "reason": "Option guide is shown only while an F&O call is open.",
        }
        result["option_order"] = order
        fa = dict(result.get("fno_analysis") or {})
        fa["option_order"] = order
        result["fno_analysis"] = fa
        return order
    # Reuse saved guide for any F&O index when max-loss + index SL/T + suggestions still match
    saved = (call.get("readings") or {}).get("option")
    reuse = (
        isinstance(saved, dict)
        and saved.get("tradingsymbol")
        and saved.get("right")
        and isinstance(saved.get("suggestions"), list)
        and len(saved.get("suggestions") or []) >= 1
        and abs(float(saved.get("max_loss_inr") or 0) - float(max_loss_inr or 0)) < 0.5
    )
    if reuse:
        try:
            sl = call.get("stop_loss")
            t1 = call.get("target_1")
            has_live = sl is not None or t1 is not None
            stamped = (
                saved.get("index_stop") is not None
                or saved.get("index_target") is not None
            )
            has_pts = (
                saved.get("index_risk_pts") is not None
                or saved.get("index_reward_pts") is not None
            )
            if has_live and not stamped and not has_pts:
                # Very old guide — cannot verify levels; reprice.
                reuse = False
            elif has_live and stamped:
                if sl is not None and saved.get("index_stop") is not None:
                    if abs(float(sl) - float(saved.get("index_stop"))) > 0.05:
                        reuse = False
                if reuse and t1 is not None and saved.get("index_target") is not None:
                    if abs(float(t1) - float(saved.get("index_target"))) > 0.05:
                        reuse = False
            elif has_live and has_pts and call.get("entry") is not None:
                entry = float(call.get("entry"))
                if sl is not None and saved.get("index_risk_pts") is not None:
                    if abs(abs(entry - float(sl)) - float(saved.get("index_risk_pts"))) > 0.05:
                        reuse = False
                if reuse and t1 is not None and saved.get("index_reward_pts") is not None:
                    if abs(abs(float(t1) - entry) - float(saved.get("index_reward_pts"))) > 0.05:
                        reuse = False
        except (TypeError, ValueError):
            reuse = False
    if reuse:
        order = {**saved, "available": True, "guide_only": True}
        order["price_reference"] = "original_entry_guide"
        try:
            import groww_option_links

            order = groww_option_links.enrich_option_guide(order, name) or order
        except Exception:
            pass
        result["option_order"] = order
        result.setdefault("fno_analysis", {})["option_order"] = order
        return order
    order = attach(
        result,
        name,
        side,
        spot,
        call.get("stop_loss"),
        call.get("target_1"),
        max_loss_inr=max_loss_inr,
    )
    if isinstance(order, dict):
        order["guide_only"] = True
        try:
            import groww_option_links

            order = groww_option_links.enrich_option_guide(order, name) or order
        except Exception:
            pass
        result["option_order"] = order
        fa = dict(result.get("fno_analysis") or {})
        fa["option_order"] = order
        result["fno_analysis"] = fa
        return order
    order = {
        "available": False,
        "guide_only": True,
        "reason": "Could not price an option for this call.",
    }
    result["option_order"] = order
    fa = dict(result.get("fno_analysis") or {})
    fa["option_order"] = order
    result["fno_analysis"] = fa
    return order


def attach(
    result: Dict[str, Any],
    symbol: str,
    decision: str,
    spot: float,
    index_stop: Optional[float] = None,
    index_target: Optional[float] = None,
    *,
    max_loss_inr: float = DEFAULT_MAX_LOSS_INR,
) -> Dict[str, Any]:
    try:
        order = build_order(
            symbol,
            decision,
            spot=spot,
            index_stop=index_stop,
            index_target=index_target,
            max_loss_inr=max_loss_inr,
        )
    except Exception as exc:
        order = {"available": False, "reason": f"Option price could not be built ({exc})."}
    result["option_order"] = order
    fa = dict(result.get("fno_analysis") or {})
    fa["option_order"] = order
    result["fno_analysis"] = fa
    return order
