"""
Product-specific decision layers on top of the core ML + TA pipeline.

- F&O: Index-first (NIFTY, BANKNIFTY); stock F&O only when setup passes filters.
  Full analyze sets anchored direction; live ticks refresh levels/alerts only.
  Candlesticks guide and can trigger adverse alerts — they do not flip decision per bar.
- Intraday: Stricter — requires agreement, quality, no conflicting candles, gate open.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

import fno_alerts
import fno_path_health
import fno_short_horizon
import fno_structure_scan
import fno_tape_alignment
import fno_session_rules
import fno_setup_engine
import fno_universe

# NSE stock F&O underlyings we support for eligibility checks (extend as needed).
FNO_STOCK_UNIVERSE: Set[str] = {
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "SBIN", "BAJFINANCE",
    "BHARTIARTL", "AXISBANK", "ITC", "LT", "TATASTEEL", "SUNPHARMA", "HINDALCO",
    "MARUTI", "WIPRO", "HCLTECH", "TATAMOTORS", "ADANIENT", "KOTAKBANK", "M&M",
    "TATAPOWER", "NTPC", "DRREDDY", "BEL", "ADANIPORTS", "ONGC", "FINNIFTY",
}

# Live tape may not open a ticket by itself (that over-traded ~60% of 15m bars).
FNO_LIVE_EDGE = 0.12
# The 15m micro score only vetoes a model call when it leans the *other* way.
# Demanding a "clean" 60/40 read on top of the model blocked 12 winners for 5
# losers over Sep 21 - Oct 12 (fno_live_diagnose): the score repeats features the
# model already prices.
FNO_MICRO_BUY = 45.0
FNO_MICRO_SELL = 55.0

STRONG_CANDLE_KEYWORDS = (
    "engulfing", "morning star", "evening star", "marubozu", "three white soldiers",
    "hammer", "shooting star", "piercing", "dark cloud",
)


def is_fno_primary(stock_key: str) -> bool:
    return fno_universe.contains(stock_key)


def is_fno_stock_eligible_symbol(stock_key: str) -> bool:
    k = stock_key.strip().upper()
    return k in FNO_STOCK_UNIVERSE and not is_fno_primary(k)


def _candle_strength(candlestick: Dict[str, Any]) -> Tuple[float, str]:
    patterns = candlestick.get("patterns") or []
    score = float(candlestick.get("score_delta") or 0)
    bias = candlestick.get("bias") or "NEUTRAL"
    strong = any(any(k in p.lower() for k in STRONG_CANDLE_KEYWORDS) for p in patterns)
    if strong and abs(score) >= 5:
        return abs(score), "strong_candle"
    if abs(score) >= 6:
        return abs(score), "candle_bias"
    return abs(score), "neutral"


def _session_quality_hold(
    decision: str,
    live_context: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Veto a same-session ticket that is only tape noise."""
    if decision in (None, "HOLD"):
        return None
    live = live_context or {}
    micro = live.get("microstructure") or {}
    if micro.get("five_min_conflict"):
        return "Alert — 5m fights the 15m book. The call is still shown."
    if micro.get("available"):
        ms = float(micro.get("micro_score") or 50)
        if "BUY" in decision and ms < FNO_MICRO_BUY:
            return f"Alert — 15m score {ms:.0f} leans against a BUY (need ≥{FNO_MICRO_BUY:.0f}). The call is still shown."
        if "SELL" in decision and ms > FNO_MICRO_SELL:
            return f"Alert — 15m score {ms:.0f} leans against a SELL (need ≤{FNO_MICRO_SELL:.0f}). The call is still shown."
        # A contrary 15m candle read only vetoes when the micro score leans the
        # same contrary way. On its own it blocked 8 winners for 4 losers.
        cs15 = micro.get("micro_candlestick_15m") or {}
        bias = (cs15.get("bias") or "NEUTRAL").upper()
        if cs15 and (cs15.get("patterns") or bias != "NEUTRAL"):
            if "BUY" in decision and bias == "BEARISH" and ms < 50:
                return f"Alert — 15m candle bias is BEARISH and the 15m score ({ms:.0f}) agrees. The call is still shown."
            if "SELL" in decision and bias == "BULLISH" and ms > 50:
                return f"Alert — 15m candle bias is BULLISH and the 15m score ({ms:.0f}) agrees. The call is still shown."
    return None


CONTEXT_AGAINST_MIN = 2


def _context_against_hold(decision: str, fno_model: Optional[Dict[str, Any]]) -> Optional[str]:
    """Hold a 15m break when the daily stack (daily ML, technicals, news, daily
    candle, session read, 60m trend, VIX, level in path) leans the other way on
    at least two inputs and at least as many oppose as agree. The cutoff nudge alone cannot stop these because
    the first-break discount bypasses it; such calls went 1W/3L on NIFTY in the
    Sep 21 - Oct 12 replay versus 63% otherwise."""
    if decision in (None, "HOLD"):
        return None
    ctx = (fno_model or {}).get("context") or {}
    if not ctx.get("available"):
        return None
    try:
        oppose = int(ctx.get("oppose") or 0)
        agree = int(ctx.get("agree") or 0)
    except (TypeError, ValueError):
        return None
    # A tie (2 for / 2 against) is not agreement either: both tied calls in the
    # replay were stopped.
    if oppose >= CONTEXT_AGAINST_MIN and oppose >= agree:
        side = "BUY" if "BUY" in str(decision) else "SELL"
        return (
            f"Daily stack leans against this {side} "
            f"({oppose} against, {agree} for). The call is still shown."
        )
    return None


def _direction_from_combined(combined: float, ml_proba: float, bullish: bool) -> str:
    if bullish:
        if combined > 0.62 and ml_proba >= 0.58:
            return "STRONG BUY"
        if combined > 0.54:
            return "BUY"
        return "HOLD"
    if combined < 0.38 and ml_proba <= 0.42:
        return "STRONG SELL"
    if combined < 0.46:
        return "SELL"
    return "HOLD"


def _fno_tighter_risk(
    bearish: bool,
    current_price: float,
    atr_val: float,
    primary_rm: Dict[str, Any],
) -> Dict[str, Any]:
    """F&O uses primary SL/T1/T2 as reference; optional tighter stop for options."""
    atr = max(atr_val, current_price * 0.006)
    if bearish:
        tight_sl = round(current_price + 1.25 * atr, 2)
        tight_t1 = round(current_price - 1.5 * atr, 2)
    else:
        tight_sl = round(current_price - 1.25 * atr, 2)
        tight_t1 = round(current_price + 1.5 * atr, 2)
    return {
        "primary_reference": {
            "stop_loss": primary_rm.get("stop_loss"),
            "target_1": primary_rm.get("target_1"),
            "target_2": primary_rm.get("target_2"),
            "atr_14": primary_rm.get("atr_14"),
            "note": "Use for index/stock futures; align option strikes to these levels.",
        },
        "options_tight": {
            "stop_loss": tight_sl,
            "target_1": tight_t1,
            "note": "Shorter-horizon option trades — tighter ATR band (1.25× / 1.5×).",
        },
    }


def classify_vix_regime(india_ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """India VIX bands for F&O instrument choice."""
    if not india_ctx or not india_ctx.get("available"):
        return {
            "available": False,
            "level": None,
            "regime": "UNKNOWN",
            "prefer": "INDEX_FUT",
            "note": "VIX unavailable — default to futures or defined-risk options.",
        }
    vix = india_ctx.get("india_vix") or {}
    if not vix.get("available"):
        return {"available": False, "level": None, "regime": "UNKNOWN", "prefer": "INDEX_FUT", "note": "VIX fetch failed"}
    import math as _math
    try:
        level = float(vix.get("level")) if vix.get("level") is not None else 0.0
        if not _math.isfinite(level):
            level = 0.0
    except (TypeError, ValueError):
        level = 0.0
    chg_out = None
    try:
        raw_chg = vix.get("change_pct")
        if raw_chg is not None:
            chg_f = float(raw_chg)
            if _math.isfinite(chg_f):
                chg_out = chg_f
    except (TypeError, ValueError):
        chg_out = None
    if level < 14:
        regime, prefer, note = "LOW", "INDEX_FUT", "Low VIX — futures/slightly OTM options; avoid overpaying premium."
    elif level < 18:
        regime, prefer, note = "NORMAL", "INDEX_FUT_OR_ATM", "Normal VIX — futures or ATM options."
    elif level < 22:
        regime, prefer, note = "ELEVATED", "INDEX_OPTION", "Elevated VIX — prefer options; size down; wider SL."
    else:
        regime, prefer, note = "HIGH", "DEFINED_RISK", "High VIX — spreads or small directional; avoid naked short vol."
    return {
        "available": True,
        "level": round(level, 2),
        "change_pct": chg_out,
        "bias": vix.get("bias"),
        "regime": regime,
        "prefer": prefer,
        "note": note,
    }


def _suggest_instrument(
    stock_key: str,
    decision: str,
    india_ctx: Optional[Dict[str, Any]],
    vix_regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    k = stock_key.strip().upper()
    bearish = "SELL" in decision
    if decision == "HOLD":
        return {
            "use_fno": False,
            "instrument_type": "NONE",
            "suggestion": "No F&O trade — wait for clearer setup.",
        }

    vix_regime = vix_regime or classify_vix_regime(india_ctx)
    prefer = vix_regime.get("prefer") or "INDEX_FUT"

    if is_fno_primary(k):
        leg = "PE" if bearish else "CE"
        if prefer == "INDEX_FUT":
            inst = "INDEX_FUT"
            sug = f"Primary F&O: {k} current-month future (VIX {vix_regime.get('regime', '—')})."
        elif prefer == "DEFINED_RISK":
            inst = "INDEX_OPTION_SPREAD"
            sug = f"{k} {leg} spread or small size — high VIX ({vix_regime.get('level')})."
        else:
            inst = "INDEX_OPTION"
            sug = f"Primary F&O: {k} {leg} ATM/near-ATM (VIX {vix_regime.get('regime', '—')})."
        return {
            "use_fno": True,
            "instrument_type": inst,
            "option_side": leg,
            "underlying": k,
            "vix_regime": vix_regime,
            "suggestion": sug,
        }

    if is_fno_stock_eligible_symbol(k):
        leg = "PE" if bearish else "CE"
        inst = "STOCK_FUT" if prefer in ("INDEX_FUT", "NORMAL", "LOW") else "STOCK_OPTION"
        return {
            "use_fno": True,
            "instrument_type": inst,
            "option_side": leg,
            "underlying": k,
            "vix_regime": vix_regime,
            "suggestion": f"Stock F&O on {k}: {inst.replace('_', ' ').lower()} or {leg}; smaller size than index.",
        }

    return {
        "use_fno": False,
        "instrument_type": "NONE",
        "suggestion": f"{k} is not in the supported stock F&O list — use NIFTY/BANKNIFTY for F&O.",
    }


CROSS_INDEX_STALE_MIN = 60.0


def _other_index_side(
    symbol: str,
    session_date: Optional[str] = None,
    asof: Any = None,
) -> Optional[str]:
    """Direction of the other index that is still live: an open call, or one
    closed within the last hour. A call stopped at 10:00 must not veto a 14:00 call."""
    other = "BANKNIFTY" if symbol == "NIFTY" else ("NIFTY" if symbol == "BANKNIFTY" else "")
    if not other:
        return None
    try:
        import session_calls

        rows = session_calls.list_calls(
            session_calls.default_db_path(), other, session_date=session_date, product="fno"
        )
    except Exception:
        return None
    now = fno_session_rules.as_ist(asof) if asof is not None else None
    if now is None:
        try:
            import market_symbols

            now = fno_session_rules.as_ist(market_symbols.ist_now())
        except Exception:
            now = None
    for row in reversed(rows or []):
        side = str(row.get("decision") or "").upper()
        if "BUY" not in side and "SELL" not in side:
            continue
        status = str(row.get("status") or "open")
        if status == "open":
            return side
        closed_at = fno_session_rules.as_ist(row.get("closed_at")) if row.get("closed_at") else None
        if now is None or closed_at is None:
            return side
        try:
            a, b = now, closed_at
            if (a.tzinfo is None) != (b.tzinfo is None):
                a, b = a.replace(tzinfo=None), b.replace(tzinfo=None)
            age_min = (a - b).total_seconds() / 60.0
        except Exception:
            return side
        if age_min <= CROSS_INDEX_STALE_MIN:
            return side
        return None
    return None


def build_fno_analysis(
    stock_key: str,
    base_decision: Dict[str, Any],
    ml_proba: float,
    adj_tech: float,
    combined_adjust: float,
    candlestick: Dict[str, Any],
    india_ctx: Optional[Dict[str, Any]],
    current_price: float,
    atr_val: float,
    fno_contracts: Optional[Dict[str, Any]] = None,
    live_context: Optional[Dict[str, Any]] = None,
    live_quote: Optional[Dict[str, Any]] = None,
    structural: Optional[Dict[str, Any]] = None,
    indicators: Optional[Dict[str, Any]] = None,
    market_tilt: Optional[Dict[str, float]] = None,
    force_decision: Optional[str] = None,
    force_setup_type: Optional[str] = None,
    day_range: Optional[Dict[str, Any]] = None,
    intraday_ready: Optional[bool] = None,
    intraday_decision: Optional[str] = None,
    same_session_only: Optional[bool] = None,
    asof: Any = None,
    session_ticket: Optional[Dict[str, Any]] = None,
    fno_model: Optional[Dict[str, Any]] = None,
    indications: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """F&O decision: same-session ticket; mid/long stay as context."""
    k = stock_key.strip().upper()
    primary = is_fno_primary(k)
    stock_fno_symbol = is_fno_stock_eligible_symbol(k)
    if same_session_only is None:
        same_session_only = True

    combined = float(base_decision.get("combined_score") or 0.5)
    signals_agree = bool(base_decision.get("signals_agree"))
    signal_quality = base_decision.get("signal_quality") or "LOW"
    base_dir = base_decision.get("decision") or "HOLD"

    candle_score, candle_driver = _candle_strength(candlestick)
    candle_bias = candlestick.get("bias") or "NEUTRAL"
    feat_ind = dict(indicators or {})
    if current_price and "close" not in feat_ind:
        feat_ind["close"] = current_price
    horizons = fno_setup_engine.build_horizon_book(
        indicators=feat_ind,
        candlestick=candlestick,
        structural=structural,
        live_context=live_context,
        adj_tech=adj_tech,
        primary=primary,
        market_tilt=market_tilt,
        same_session_only=same_session_only,
    )
    active_hz = horizons.get("active") or {}

    fno_combined = combined
    live_p = ml_proba
    live_led = False
    if live_context and live_context.get("driver") == "live_weighted":
        fno_combined = float(live_context.get("fno_combined_live") or fno_combined)
        live_p = float(live_context.get("live_probability_up") or live_p)
        live_led = True

    ml_bull = live_p >= 0.52 if live_led else ml_proba >= 0.52
    ml_bear = live_p <= 0.48 if live_led else ml_proba <= 0.48
    tech_bull = adj_tech >= 52
    tech_bear = adj_tech <= 48

    reasons: List[str] = []
    if live_context:
        for note in live_context.get("notes") or []:
            reasons.append(note)
        if live_context.get("driver") == "live_weighted":
            reasons.append("Uses today's 15-minute tape plus 5-minute confirmation.")

    if primary:
        eligible = True
        reasons.append(f"{k} is an index — same-day F&O only (stop and first target inside today's range).")
    elif stock_fno_symbol:
        if not intraday_ready:
            eligible = False
            reasons.append(
                "Stock F&O blocked: run Intraday first and wait for a strong same-session signal."
            )
        else:
            eligible = True
            reasons.append("Intraday ready — stock F&O allowed as a same-session ticket only.")
    else:
        eligible = False
        reasons.append(f"{k} is outside the configured stock F&O universe — prefer NIFTY/BANKNIFTY.")

    conflict = bool(live_context and live_context.get("live_core_conflict"))

    if force_decision:
        decision = force_decision
        setup_type = force_setup_type or "anchored"
        confidence = float(base_decision.get("confidence") or 50)
        reasons.append("F&O direction is locked while this call is open — live ticks only update price and alerts.")
    elif not eligible:
        decision = "HOLD"
        setup_type = "not_eligible"
        confidence = round(45 + abs(fno_combined - 0.5) * 30, 1)
    elif conflict and not primary:
        decision = "HOLD"
        setup_type = "live_conflict"
        confidence = round(42 + abs(live_p - 0.5) * 40, 1)
        reasons.append("Stock F&O: HOLD — live tape fights swing model.")
    elif eligible:
        # Dedicated F&O model is the index ticket. Cash / Intraday ensemble is not used.
        hz_dir = active_hz.get("decision") or "HOLD"
        head = fno_model or {}
        if head.get("available") and head.get("decision") is not None:
            decision = str(head.get("decision") or "HOLD")
            setup_type = "fno_model" if decision != "HOLD" else "fno_model_flat"
            confidence = float(head.get("confidence") or 50)
            reasons.append(
                (
                    f"The model's first-target-before-stop score is "
                    f"{float(head.get('p_t1') or head.get('p_up') or 0.5):.0%}. "
                    f"A call is taken only at {float(head.get('buy_p') or 0.55):.0%} or higher."
                )
                if str(head.get("decision") or "HOLD") == "HOLD"
                else (
                    f"{decision} — first-target-before-stop score "
                    f"{float(head.get('p_t1') or 0.5):.0%} (need {float(head.get('buy_p') or 0.55):.0%})."
                )
            )
            if head.get("bar_note"):
                reasons.append(str(head["bar_note"]))
            if head.get("structure_note"):
                reasons.append(str(head["structure_note"]))
            if head.get("holdout_accuracy") is not None:
                reasons.append(
                    f"The saved base-model filter hit T1 first on "
                    f"{float(head['holdout_accuracy']):.0%} of its chronological test selections."
                )
            if head.get("p_runner") is not None:
                reasons.append(
                    f"Second-target strategy score: {float(head['p_runner']):.0%}"
                    + (" — T2 is informational; the recorded ticket closes at T1." if head.get("continue_ok") else " — book the first target only.")
                )
            regime = head.get("regime") or {}
            if regime.get("name"):
                reasons.append(f"Tape regime: {regime.get('name')} — {regime.get('note')}")
            align = head.get("alignment") or {}
            if align.get("note"):
                reasons.append(align["note"])
            if stock_fno_symbol and not intraday_ready:
                decision = "HOLD"
                setup_type = "not_eligible"
                reasons.append("Stock F&O still needs a strong Intraday signal first.")
        else:
            intra_dir = (intraday_decision or "").upper()
            if hz_dir != "HOLD":
                decision = hz_dir
                setup_type = active_hz.get("setup_type") or "horizon_short"
                reasons.append(
                    f"Same-session book: {hz_dir} · score {active_hz.get('score')} "
                    f"({active_hz.get('hold_period')})"
                )
                for line in (active_hz.get("reasons") or [])[:4]:
                    reasons.append(line)
            elif stock_fno_symbol and intra_dir in ("BUY", "STRONG BUY", "SELL", "STRONG SELL"):
                decision = "BUY" if "BUY" in intra_dir else "SELL"
                setup_type = "horizon_short"
                reasons.append(f"Stock F&O follows strong Intraday {intra_dir}.")
            elif primary:
                decision = "HOLD"
                setup_type = "horizon_flat"
                reasons.append("Same-session book is flat — no index F&O ticket (weekly book is context only).")
            elif ml_bull or (tech_bull and fno_combined > 0.52):
                decision = _direction_from_combined(fno_combined, live_p, bullish=True)
                setup_type = "horizon_short"
            elif ml_bear or (tech_bear and fno_combined < 0.48):
                decision = _direction_from_combined(fno_combined, live_p, bullish=False)
                setup_type = "horizon_short"
            else:
                decision = "HOLD"
                setup_type = "horizon_flat"

        if live_led and decision != "HOLD" and str(setup_type).startswith("horizon_short"):
            setup_type = "live_tape_confirmed"

        if not str(setup_type).startswith("fno_model"):
            confidence = float(base_decision.get("confidence") or 50)
            if active_hz.get("decision") not in (None, "HOLD"):
                confidence = round(min(88, 52 + abs(float(active_hz.get("score") or 0)) * 1.6), 1)
            if setup_type in ("live_tape", "live_tape_confirmed", "live_overrides_core"):
                confidence = round(52 + abs(live_p - 0.5) * 85, 1)
    else:
        decision = "HOLD"
        setup_type = "not_eligible"
        confidence = 50.0

    desk_alerts: list = []
    if (fno_model or {}).get("bar_note"):
        desk_alerts.append(str(fno_model["bar_note"]))
    if not (fno_model or {}).get("reclaim") and not (fno_model or {}).get("first_clip"):
        quality = _session_quality_hold(decision, live_context)
        if quality:
            desk_alerts.append(quality)
            reasons.append(quality)
    ctx_note = _context_against_hold(decision, fno_model)
    if ctx_note:
        desk_alerts.append(ctx_note)
        reasons.append(ctx_note)

    clock = asof or (live_quote or {}).get("received_at_ist")
    fresh_break = float(((fno_model or {}).get("features") or {}).get("first_break") or 0) >= 1.0
    expiry_day = False
    expiry_banner = None
    side_day = None
    if is_fno_primary(k):
        side_day = None
        if clock is not None:
            side_dt = fno_session_rules.as_ist(clock)
            side_day = side_dt.date().isoformat() if side_dt is not None and hasattr(side_dt, "date") else None
        try:
            import option_ticket

            exp_day = None
            if side_day:
                from datetime import date as _date

                exp_day = _date.fromisoformat(side_day)
            expiry_day = option_ticket.weekly_expires_today(k, exp_day)
        except Exception:
            expiry_day = False
        if expiry_day:
            detail = fno_session_rules.expiry_open_hold(True, fresh_break) or "Weekly settlement today."
            expiry_banner = f"{k} weekly expiry today. {detail}"

    if not force_decision:
        orb = ((live_context or {}).get("microstructure") or {}).get("opening_range")
        open_px = (live_quote or {}).get("open") or (day_range or {}).get("reference_open")
        other_side = None
        if k in ("NIFTY", "BANKNIFTY"):
            other_side = _other_index_side(k, side_day, asof=clock)
        for note in fno_session_rules.desk_alerts(
            decision,
            asof=clock,
            session_ticket=session_ticket,
            opening_range=orb,
            price=current_price,
            fresh_break=fresh_break,
            day_range=day_range,
            open_price=open_px,
            p_t1=(fno_model or {}).get("p_t1"),
            expiry_day=expiry_day,
            other_index_decision=other_side,
        ):
            if note not in desk_alerts:
                desk_alerts.append(note)
                reasons.append(note)
        try:
            import event_calendar

            risk_day = None
            if clock is not None:
                risk_dt = fno_session_rules.as_ist(clock)
                risk_day = risk_dt.date() if risk_dt is not None and hasattr(risk_dt, "date") else None
            risk_note = event_calendar.event_risk(risk_day) if risk_day is not None else None
            if risk_note:
                reasons.append(risk_note)
        except Exception:
            pass

    vix_regime = classify_vix_regime(india_ctx)
    if vix_regime.get("available"):
        reasons.append(
            f"India VIX {vix_regime.get('regime')} ({vix_regime.get('level')}) — {vix_regime.get('note')}"
        )
        if vix_regime.get("regime") == "HIGH" and decision not in ("HOLD",) and setup_type == "live_tape":
            confidence = min(float(confidence), 68)
            reasons.append("High VIX — cap confidence; prefer defined risk.")

    bearish = "SELL" in decision
    rm = base_decision.get("risk_management") or {}
    instrument = _suggest_instrument(k, decision, india_ctx, vix_regime)
    try:
        import fno_risk_engine

        ctx = dict(live_context or {})
        if fno_model:
            ctx.setdefault("fno_model", fno_model)
        if indications and indications.get("available"):
            ctx["indications"] = indications
        fno_risk = fno_risk_engine.compute_fno_trade_risk(
            bearish,
            current_price,
            atr_val,
            setup_type=setup_type if str(setup_type).startswith("horizon_") else "horizon_short",
            instrument=instrument,
            live_quote=live_quote,
            live_context=ctx,
            structural=structural,
            swing_risk=rm,
            decision=decision,
            day_range=day_range,
            underlying=k,
        )
    except Exception:
        decision = "HOLD"
        setup_type = "risk_error"
        confidence = min(float(confidence), 48)
        reasons.append("HOLD — F&O risk engine failed; no swing fallback.")
        fno_risk = {
            "fno_trade": {
                "stop_loss": None,
                "target_1": None,
                "target_2": None,
                "horizon": "none",
                "levels_fit": False,
                "note": "HOLD — F&O levels unavailable.",
            },
            "swing_reference_only": {},
        }
    trade_lv = (fno_risk.get("fno_trade") or {})

    def _reset_hold_levels() -> None:
        nonlocal fno_risk, trade_lv
        try:
            import fno_risk_engine as _fre

            fno_risk = _fre.compute_fno_trade_risk(
                False, current_price, atr_val, decision="HOLD", day_range=day_range, swing_risk=rm
            )
        except Exception:
            fno_risk = {
                "fno_trade": {
                    "stop_loss": None,
                    "target_1": None,
                    "target_2": None,
                    "horizon": "none",
                    "levels_fit": False,
                    "note": "HOLD — F&O levels unavailable.",
                },
                "swing_reference_only": {},
            }
        trade_lv = (fno_risk.get("fno_trade") or {})

    if decision != "HOLD" and not force_decision:
        for note in fno_session_rules.safety_entry_alerts(
            decision,
            session_ticket=session_ticket,
            opening_range=((live_context or {}).get("microstructure") or {}).get("opening_range"),
            price=current_price,
            t1=trade_lv.get("target_1"),
            p_t1=(fno_model or {}).get("p_t1"),
            fresh_break=fresh_break,
            asof=clock,
        ):
            if note not in desk_alerts:
                desk_alerts.append(note)
                reasons.append(note)

    if decision != "HOLD" and trade_lv.get("levels_fit") is False:
        fit_note = trade_lv.get("note") or "SL/T1/T2 cannot fit inside the morning day range."
        desk_alerts.append(fit_note)
        reasons.append(fit_note)
    # Clip T1 is intentionally smaller than 25% of leftover day range.
    room = None
    if trade_lv.get("setup_type") != "safe_clip":
        room = fno_session_rules.t1_room_hold(
            decision, current_price, trade_lv.get("target_1"), day_range
        )
    if room:
        desk_alerts.append(room)
        reasons.append(room)
    rr = fno_session_rules.reward_risk_hold(
        decision, current_price, trade_lv.get("stop_loss"), trade_lv.get("target_1")
    )
    if rr:
        desk_alerts.append(rr)
        reasons.append(rr)
    if indications and indications.get("available"):
        import fno_indications

        for note in list(indications.get("alerts") or []) + fno_indications.call_alerts(
            indications, decision, price=current_price, target_1=trade_lv.get("target_1")
        ):
            if note not in desk_alerts:
                desk_alerts.append(note)
                reasons.append(note)
    # Practical fit of the fixed clip: a known level in the path to T1, a stop
    # inside 15m noise, or too little session left for the target.
    import fno_levels

    level_read = fno_levels.level_room(
        decision,
        current_price,
        trade_lv.get("stop_loss"),
        trade_lv.get("target_1"),
        (fno_model or {}).get("levels"),
    )
    vol_read = (fno_model or {}).get("vol_fit") or {}
    if decision != "HOLD" and vol_read.get("hold"):
        time_note = f"Time left: {vol_read['hold']}"
        desk_alerts.append(time_note)
        reasons.append(time_note)
    for line in fno_levels.summary_lines(
        (fno_model or {}).get("levels") or {}, level_read, vol_read, (fno_model or {}).get("htf") or {}
    ):
        reasons.append(line)
    micro = (live_context or {}).get("microstructure") or {}
    live_candle = micro.get("micro_candlestick_15m") if micro.get("available") else None
    shown_candle = live_candle if isinstance(live_candle, dict) else candlestick
    candle_guidance = fno_alerts.build_candle_guidance(shown_candle or {})
    if isinstance(live_candle, dict):
        names = live_candle.get("patterns") or []
        candle_guidance["summary"] = (
            "Last finished 15-minute candle: " + "; ".join(names[:3])
            if names
            else "Last finished 15-minute candle has no strong pattern."
        )
        candle_guidance["source"] = "15minute"
    open_for_review = fno_session_rules.open_ticket(session_ticket)
    path_health = None
    if open_for_review and current_price:
        try:
            review = fno_alerts.open_call_review(
                open_for_review,
                current_price,
                fno_model,
                bars_5m=(live_context or {}).get("bars_5m"),
                asof=clock,
            )
            if review and review not in desk_alerts:
                desk_alerts.append(review)
                reasons.append(review)
            # 12y-proven path health (CONFIDENT green / WARN red) — open call only
            ctx = live_context or {}
            # Never ``df or other`` — pandas truthiness is ambiguous.
            bars_15 = fno_session_rules.first_frame(
                ctx.get("bars_15m"),
                ctx.get("bars"),
                ctx.get("idf15"),
                ((ctx.get("microstructure") or {}).get("bars_15m")),
            )
            try:
                hi, lo = fno_session_rules.path_extremes(
                    bars_15, open_for_review.get("taken_at"), float(current_price)
                )
            except Exception:
                hi = lo = float(current_price)
            # Persist running peak on ticket so LTP-only polls still keep MFE
            try:
                side_buy = "BUY" in str(open_for_review.get("decision") or "")
                entry_px = float(open_for_review["entry"])
                cur_favor = (hi - entry_px) if side_buy else (entry_px - lo)
                prev_peak = float(open_for_review.get("path_peak_favor") or 0)
                open_for_review["path_peak_favor"] = round(max(prev_peak, cur_favor, 0.0), 2)
                open_for_review["path_against"] = round(
                    max(0.0, (entry_px - lo) if side_buy else (hi - entry_px)), 2
                )
            except Exception:
                pass
            path_health = fno_path_health.assess_open_ticket(
                open_for_review,
                last=float(current_price),
                path_high=hi,
                path_low=lo,
                bars=bars_15,
            )
            # If bars missing, still apply peak stored on ticket for WARN/CONFIDENT
            if path_health and open_for_review.get("path_peak_favor") is not None:
                try:
                    metrics = dict(path_health.get("metrics") or {})
                    peak = max(
                        float(metrics.get("peak") or 0),
                        float(open_for_review["path_peak_favor"]),
                    )
                    metrics["peak"] = peak
                    metrics["favor"] = peak
                    reward = float(metrics.get("reward") or 0)
                    metrics["peak_frac_reward"] = (peak / reward) if reward else 0.0
                    metrics["hit50"] = 1.0 if reward and peak >= 0.5 * reward else 0.0
                    path_health = fno_path_health.assess(metrics)
                    path_health["decision"] = open_for_review.get("decision")
                    path_health["entry"] = open_for_review.get("entry")
                except Exception:
                    pass
            if path_health and path_health.get("message"):
                msg = path_health["message"]
                if msg not in desk_alerts:
                    desk_alerts.insert(0, msg)
                if msg not in reasons:
                    reasons.insert(0, msg)
        except Exception:
            # Never fail Analyze because of path-health / frame selection.
            path_health = None
    alerts = fno_alerts.build_adverse_alerts(
        decision,
        live_p=live_p,
        live_context=live_context,
        candlestick=candlestick,
        current_price=current_price,
        fno_trade_risk=fno_risk,
    )
    for text in desk_alerts:
        # Path-health messages already carried as structured alerts below
        if path_health and text == path_health.get("message"):
            continue
        alerts.append({"code": "desk_notice", "severity": "warning", "message": text})
    alerts = fno_path_health.attach_path_health_alerts(alerts, path_health)
    alert_meta = fno_alerts.alerts_summary(alerts)
    open_tk = fno_session_rules.open_ticket(session_ticket)
    tape_indication = fno_tape_alignment.build_tape_indication(
        decision=decision,
        live_context=live_context,
        alerts=alerts,
        fno_model=fno_model,
        active_call=open_tk,
        core_decision=base_dir,
        confidence=confidence,
    )
    short_horizon = fno_short_horizon.build(
        live_context=live_context,
        indications=indications if (indications or {}).get("available") else None,
        price=current_price,
        active_call=open_tk,
    )
    try:
        import fno_short_horizon_log

        fno_short_horizon_log.maybe_record_and_settle(
            stock=k,
            short_horizon=short_horizon,
            price=current_price,
            live_context=live_context,
            indications=indications if (indications or {}).get("available") else None,
            bars_5m=(live_context or {}).get("bars_5m") if isinstance(live_context, dict) else None,
        )
    except Exception:
        pass
    call_live = fno_short_horizon.call_live_track(
        active_call=open_tk,
        fno_model=fno_model,
        live_context=live_context,
        path_health=path_health,
        short_horizon=short_horizon,
        combined_score=fno_combined,
        confidence=confidence,
    )
    structure_scan = fno_structure_scan.build(
        live_context=live_context,
        price=current_price,
        candlestick=shown_candle if isinstance(shown_candle, dict) else candlestick,
        short_horizon=short_horizon,
        decision=decision,
        active_call=open_tk,
    )
    if candle_guidance.get("patterns"):
        reasons.append("Candle guide: " + candle_guidance["summary"][:120])
    top_pat = (structure_scan or {}).get("top") or {}
    if top_pat.get("note") and decision == "HOLD" and not open_tk:
        note = str(top_pat["note"])
        if note not in reasons:
            reasons.append("Structure: " + note[:140])

    if not eligible:
        instrument = {
            **instrument,
            "use_fno": False,
            "suggestion": instrument.get("suggestion", "")
            + (" For F&O today, analyze NIFTY or BANKNIFTY." if not primary else ""),
        }

    live_tk = fno_session_rules.open_ticket(session_ticket)
    n_closed = fno_session_rules.closed_ticket_count(session_ticket)
    if live_tk:
        call_n = max(int((session_ticket or {}).get("tickets") or 1), n_closed)
    elif decision != "HOLD":
        call_n = n_closed + 1
    else:
        call_n = n_closed
    sl_txt = trade_lv.get("stop_loss")
    t1_txt = trade_lv.get("target_1")
    if eligible and decision != "HOLD" and sl_txt is not None and t1_txt is not None:
        headline = (
            f"{decision} call #{max(call_n, 1)} — stop {sl_txt}, first target {t1_txt}."
        )
    elif not primary and not eligible:
        headline = f"{k} is not on the F&O list today. Use NIFTY or BANKNIFTY."
    elif decision == "HOLD":
        hold_lines = [
            r for r in reasons
            if r and (
                str(r).startswith("HOLD")
                or str(r).startswith("Wait")
                or str(r).startswith("No new")
                or str(r).startswith("Need ")
                or str(r).startswith("Expiry")
                or str(r).startswith("Nifty and Bank")
                or str(r).startswith("Cash market")
                or str(r).startswith("Price already")
                or str(r).startswith("Break ")
                or str(r).startswith("The open gap")
                or str(r).startswith("Opening range")
            )
        ]
        why = hold_lines[-1] if hold_lines else next(
            (r for r in reversed(reasons) if r and not r.lower().startswith("india vix") and "candle" not in r.lower()),
            "No clean call right now.",
        )
        headline = f"No new call. {why}"
    else:
        headline = f"{decision} on {k}."

    return {
        "product": "fno",
        "fno_primary": primary,
        "fno_eligible": eligible,
        "decision": decision,
        "confidence": round(confidence, 1),
        "setup_type": setup_type,
        "headline": headline,
        "combined_score_fno": round(fno_combined, 4),
        "candle_driver": candle_driver,
        "candle_patterns": (shown_candle or {}).get("patterns") or [],
        "instrument": instrument,
        "fno_contracts": fno_contracts,
        "vix_regime": vix_regime,
        "live_context": live_context,
        "risk": fno_risk,
        "candle_guidance": candle_guidance,
        "alerts": alerts,
        "alerts_summary": alert_meta,
        "desk_alerts": desk_alerts,
        "path_health": path_health,
        "expiry_day": bool(expiry_day),
        "expiry_banner": expiry_banner,
        "indications": indications if (indications or {}).get("available") else None,
        "tape_indication": tape_indication,
        "short_horizon": short_horizon,
        "call_live": call_live,
        "structure_scan": structure_scan,
        "levels": (fno_model or {}).get("levels"),
        "level_room": level_read,
        "clip_fit": vol_read,
        "htf_trend": (fno_model or {}).get("htf"),
        "anchored_decision": decision,
        "horizons": horizons,
        "active_horizon": active_hz.get("horizon"),
        "day_range_forecast": day_range,
        "intraday_ready": bool(intraday_ready) if stock_fno_symbol else None,
        "fno_model": fno_model,
        "decision_policy": (
            "A call is a small same-day clip with volatility-aware stop and target levels. "
            "NIFTY new entries require a fresh quote, a continuous completed 15-minute tape, "
            "and a decision between 09:30 and 15:15 IST. A new call can print after the prior "
            "ticket closes; the engine never forces a fixed number of calls. Expiry, chase, "
            "re-entry, volatility, and market context remain visible as risk alerts."
        ),
        "reasons": reasons,
        "disclaimer": "F&O is leveraged; review alerts if tape turns against you. Not investment advice.",
    }


def build_intraday_analysis(
    stock_key: str,
    base_decision: Dict[str, Any],
    ml_proba: float,
    adj_tech: float,
    candlestick: Dict[str, Any],
    trading_gate: Optional[Dict[str, Any]],
    india_ctx: Optional[Dict[str, Any]],
    intraday_bars_ok: Optional[bool] = None,
    intraday_tech: Optional[Dict[str, Any]] = None,
    blended_intraday_score: Optional[float] = None,
    session_model: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Intraday: all key checks must pass — no candlestick-led override.

    When a dedicated 15m session model is available, that is the ticket.
    The daily cash ensemble stays as context only.
    """
    k = stock_key.strip().upper()
    cash_decision = base_decision.get("decision") or "HOLD"
    head = session_model or {}
    use_session = bool(head.get("available"))
    decision = head.get("decision") if use_session else cash_decision
    if not decision:
        decision = "HOLD"
    signals_agree = bool(base_decision.get("signals_agree"))
    signal_quality = base_decision.get("signal_quality") or "LOW"
    combined = float(base_decision.get("combined_score") or 0.5)
    agreement = float(base_decision.get("agreement_score") or 0)
    p_up = float(head.get("p_up") or 0.5) if use_session else combined

    candle_bias = candlestick.get("bias") or "NEUTRAL"
    patterns = candlestick.get("patterns") or []

    blockers: List[str] = []
    checks: List[Dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "pass": ok, "detail": detail})
        if not ok:
            blockers.append(f"{name}: {detail}")

    if use_session:
        check(
            "Session 15m model",
            decision not in ("HOLD",),
            f"{head.get('source') or 'session'} p(up) {p_up:.2f} · "
            f"60m · side {head.get('allowed_side') or 'none'}.",
        )
        check(
            "Cash ensemble (context)",
            True,
            f"Daily core is {cash_decision} — not the ticket when 15m model is loaded.",
        )
    else:
        check("ML + TA agree", signals_agree, "Required for intraday entry.")
        check(
            "Signal quality",
            signal_quality in ("HIGH", "MEDIUM"),
            f"Got {signal_quality}; intraday needs MEDIUM or HIGH.",
        )
        check(
            "Conviction",
            abs(combined - 0.5) >= 0.07,
            f"Combined score {combined:.2f} too close to neutral.",
        )
        check(
            "Agreement score",
            agreement >= 65,
            f"ML vs TA agreement {agreement:.0f}% (need ≥65).",
        )

    bullish = "BUY" in decision
    bearish = "SELL" in decision
    if bullish and candle_bias == "BEARISH" and patterns:
        check("Candle alignment", False, "Bearish candle bias conflicts with BUY.")
    elif bearish and candle_bias == "BULLISH" and patterns:
        check("Candle alignment", False, "Bullish candle bias conflicts with SELL.")
    else:
        check("Candle alignment", True, "No conflict with candle bias.")

    gate_open = True
    if use_session:
        check("Session gate", True, "15m session model is the gate — cash WAIT is ignored.")
    elif trading_gate:
        allow = trading_gate.get("allow_trade")
        if allow is None:
            allow = trading_gate.get("allowed_to_act_on_signal", True)
        status = str(
            trading_gate.get("status") or trading_gate.get("recommended_action") or ""
        ).upper()
        gate_open = bool(allow) and status != "WAIT"
        reasons = trading_gate.get("reasons") or []
        check(
            "Session gate",
            gate_open,
            trading_gate.get("message")
            or (reasons[0] if reasons else None)
            or status
            or "Gate closed",
        )
    else:
        check("Session gate", True, "No gate data — assumed open.")

    if intraday_bars_ok is False:
        check("Intraday trend (5m)", False, "Last 5m bars do not confirm direction.")
    elif intraday_bars_ok is True:
        check("Intraday trend (5m)", True, "5m structure aligns with decision.")
    elif intraday_bars_ok is None:
        check("Intraday trend (5m)", True, "5m check skipped (no Kite intraday data).")

    it = intraday_tech or {}
    if it.get("available"):
        sc = float(it.get("intraday_score") or 50)
        ok_ta = True
        if bullish:
            ok_ta = sc >= 54
        elif bearish:
            ok_ta = sc <= 46
        check(
            "Intraday TA (5m score)",
            ok_ta,
            f"5m score {sc:.0f}/100 (need ≥54 BUY / ≤46 SELL); bias {it.get('intraday_bias')}.",
        )
    else:
        check("Intraday TA (5m score)", True, "5m TA skipped — no Kite minute history.")

    if blended_intraday_score is not None and not use_session:
        check(
            "Blended conviction",
            abs(blended_intraday_score - 0.5) >= 0.08,
            f"Daily+5m blend {blended_intraday_score:.2f} (need clear edge).",
        )

    passed = len(blockers) == 0 and decision not in ("HOLD",)

    if not passed:
        intraday_decision = "HOLD"
        if decision == "HOLD":
            blockers.append(
                "Session 15m model is HOLD — no same-session edge."
                if use_session
                else "Core model is HOLD — no same-session edge."
            )
    else:
        intraday_decision = decision

    rm = base_decision.get("risk_management") or {}
    clip = head.get("clip") if use_session and passed else None
    if clip:
        rm = {
            "stop_loss": clip.get("stop_loss"),
            "target_1": clip.get("target_1"),
            "target_2": None,
            "note": clip.get("note"),
        }
    if passed and use_session:
        confidence = float(head.get("confidence") or 60)
    elif passed:
        confidence = float(base_decision.get("confidence") or 50)
    else:
        confidence = round(40 + agreement * 0.3, 1)

    return {
        "product": "intraday",
        "decision": intraday_decision,
        "core_decision": cash_decision,
        "driver": "session_15m" if use_session else "cash_ensemble",
        "session_model": head if use_session else None,
        "confidence": round(confidence, 1),
        "intraday_ready": passed,
        "checks": checks,
        "blockers": blockers,
        "headline": (
            f"Intraday {intraday_decision} — checklist passed."
            if passed
            else "Intraday HOLD — at least one check failed, so no same-day trade."
        ),
        "risk_reference": {
            "stop_loss": rm.get("stop_loss"),
            "target_1": rm.get("target_1"),
            "target_2": rm.get("target_2"),
            "note": "Use these levels on the cash/spot chart; tighten manually for scalps.",
        },
        "intraday_technical": it if it.get("available") else None,
        "blended_intraday_score": blended_intraday_score,
        "disclaimer": "Intraday requires discipline; one failed check → no trade.",
    }


def intraday_5m_confirms(
    df_intraday: Any,
    bullish: bool,
) -> bool:
    """Simple 5m confirmation: last 3 closes trend."""
    if df_intraday is None or len(df_intraday) < 5:
        return True
    try:
        col = "close" if "close" in df_intraday.columns else "Close"
        closes = df_intraday[col].astype(float).tail(5)
        if len(closes) < 3:
            return True
        up = closes.iloc[-1] > closes.iloc[-3]
        down = closes.iloc[-1] < closes.iloc[-3]
        if bullish:
            return up
        if not bullish:
            return down
    except Exception:
        return True
    return True
