"""Fast F&O refresh.

The 15-second poll only moves the live price against bars already in memory.
The 90-second pass downloads the session tape once, rescores the same model,
and prices the option. Neither path reruns the daily stock model.
"""

from __future__ import annotations

import copy
import math
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import fno_live_engine
import fno_risk_engine
import kite_data
import live_market
import market_symbols
import product_analysis
from market_symbols import stock_key_from_input

import fno_alerts
import fno_volatility_pulse

_snapshots: Dict[str, Dict[str, Any]] = {}
_snap_lock = threading.RLock()


def _finite_float(value: Any, default: float = 0.0) -> float:
    """NaN is truthy — never use `float(x or 0)` for VIX/levels."""
    try:
        if value is None:
            return float(default)
        v = float(value)
        return v if math.isfinite(v) else float(default)
    except (TypeError, ValueError):
        return float(default)


def update_volatility_pulse(
    snap: Dict[str, Any],
    symbol: str,
    price: float,
    *,
    ts: Any = None,
    live_context: Optional[Dict[str, Any]] = None,
    india_ctx: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Sample LTP, store in snapshot, return pulse dict."""
    india = india_ctx or snap.get("india_ctx") or {}
    vix = india.get("india_vix") or {}
    vix_level = _finite_float(vix.get("level"), 0.0)
    vix_chg = vix.get("change_pct")
    micro = None
    if isinstance(live_context, dict):
        micro = live_context.get("microstructure")
    if not micro and isinstance(snap.get("microstructure"), dict):
        micro = snap.get("microstructure")
    hist, pulse = fno_volatility_pulse.record_and_assess(
        snap.get("price_samples"),
        symbol,
        price,
        ts=ts,
        vix_level=vix_level,
        vix_change_pct=vix_chg,
        micro=micro if isinstance(micro, dict) else None,
    )
    snap["price_samples"] = hist
    snap["volatility_pulse"] = pulse
    return pulse


def merge_volatility_into_block(
    snap: Dict[str, Any],
    symbol: str,
    price: float,
    fno_block: Dict[str, Any],
    *,
    live_context: Optional[Dict[str, Any]] = None,
    live_quote: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Sample LTP, attach pulse to the F&O block, refresh alert summary."""
    pulse = update_volatility_pulse(
        snap,
        symbol,
        price,
        ts=(live_quote or {}).get("received_at_ist"),
        live_context=live_context,
        india_ctx=snap.get("india_ctx"),
    )
    fno_block = dict(fno_block)
    fno_block["volatility_pulse"] = pulse
    alerts = fno_volatility_pulse.attach_pulse_alert(list(fno_block.get("alerts") or []), pulse)
    fno_block["alerts"] = alerts
    fno_block["alerts_summary"] = fno_alerts.alerts_summary(alerts)
    return fno_block


def option_fingerprint(call: Optional[Dict[str, Any]], max_loss_inr: Optional[float] = None) -> str:
    """Same open call should not re-price the option on every 15-second tick.

    Includes max_loss_inr so Settings cap changes force a reprice.
    """
    if not call:
        return ""
    try:
        import option_ticket

        cap = option_ticket.resolve_max_loss_inr(max_loss_inr)
    except Exception:
        cap = float(max_loss_inr) if max_loss_inr else 2000.0
    parts = [
        call.get("decision"),
        call.get("n"),
        call.get("entry"),
        call.get("stop_loss"),
        call.get("target_1"),
        call.get("status"),
        f"ml={round(float(cap), 2)}",
    ]
    return "|".join("" if part is None else str(part) for part in parts)


def save_snapshot(stock_key: str, payload: Dict[str, Any]) -> None:
    key = stock_key_from_input(stock_key)
    packed = copy.deepcopy({
        **payload,
        "saved_at": time.time(),
        "snapshot_date": str(market_symbols.ist_now().date()),
    })
    with _snap_lock:
        _snapshots[key] = packed


def _last_indications(stock_key: str) -> Optional[Dict[str, Any]]:
    try:
        import fno_indications

        return fno_indications.last(stock_key)
    except Exception:
        return None


def get_snapshot(stock_key: str) -> Optional[Dict[str, Any]]:
    key = stock_key_from_input(stock_key)
    with _snap_lock:
        snap = _snapshots.get(key)
        if not snap:
            return None
        # Drop prior-day snapshots for every index (was NIFTY-only — BN/Sensex
        # could keep yesterday's open ticket and block today's list).
        if snap.get("snapshot_date") and snap.get("snapshot_date") != str(
            market_symbols.ist_now().date()
        ):
            return None
        return copy.deepcopy(snap)


def tick_to_live_quote(stock_key: str, tick: Dict[str, Any]) -> Dict[str, Any]:
    key = stock_key_from_input(stock_key)
    lp = float(tick.get("last_price") or 0)
    ohlc = tick.get("ohlc") or {}
    o = float(ohlc.get("open") or tick.get("open") or lp)
    h = float(ohlc.get("high") or tick.get("high") or lp)
    l = float(ohlc.get("low") or tick.get("low") or lp)
    h = max(h, lp)
    l = min(l, lp)
    received = tick.get("updated_at_ist") or market_symbols.ist_now().isoformat()
    return {
        "stock": key,
        "trading_symbol": market_symbols.nse_trading_symbol(key),
        "exchange": "NSE",
        "segment": "CASH",
        "last_price": round(lp, 2),
        "open": round(o, 2),
        "high": round(h, 2),
        "low": round(l, 2),
        "close": round(lp, 2),
        "volume": int(tick.get("volume") or 0),
        "source": tick.get("source") or "kite_ws",
        "feed_type": "websocket_ltp",
        "received_at_ist": received,
        "exchange_timestamp": tick.get("exchange_timestamp"),
    }


def _fetch_live_quote_ws_first(stock_key: str, indian_stocks: Dict[str, str]) -> Tuple[Optional[Dict[str, Any]], str]:
    key = stock_key_from_input(stock_key)
    feed = "http_quote"
    try:
        import kite_ticker

        kite_ticker.ensure_stream([key])
        tick = kite_ticker.get_tick(key)
        if tick and tick.get("last_price") is not None:
            quote = tick_to_live_quote(key, tick)
            if key != "NIFTY":
                return quote, "websocket"
            from nifty_fno_data import quote_fresh

            if quote_fresh(quote):
                return quote, "websocket"
    except Exception:
        pass

    if live_market.is_live_eligible(key, indian_stocks):
        q, err = live_market.fetch_live_quote(key, indian_stocks)
        if q:
            return q, "http_quote"
        return None, err or "quote failed"
    return None, "not eligible"


def rescore_from_websocket(
    stock_key: str,
    indian_stocks: Dict[str, str],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Rebuild F&O decision from cached swing + fresh WS/HTTP LTP.
    Requires prior full POST /predict/fno (seeds snapshot).
    """
    key = stock_key_from_input(stock_key)
    snap = get_snapshot(key)
    if not snap:
        return None, "No F&O snapshot — run Analyze on F&O tab first (POST /predict/fno)"

    live_quote, feed = _fetch_live_quote_ws_first(key, indian_stocks)
    if not live_quote:
        return None, f"No live price ({feed})"

    # Bars and the 5-minute read stay on the 90-second refresh. This poll is the live price.
    micro = snap.get("microstructure") or {"available": False}
    current_price = float(live_quote["last_price"])
    import fno_session_rules as fsrules

    idf15 = snap.get("bars_15m")
    idf5 = snap.get("bars_5m")
    ticket_before = snap.get("session_ticket")
    live0 = fsrules.open_ticket(snap.get("session_ticket"))
    hi, lo = current_price, current_price
    if live0:
        hi, lo = fsrules.path_extremes(idf15, live0.get("taken_at"), current_price)
    import fno_alerts

    session_ticket, skip_mark = fno_alerts.settle_open_call(
        snap.get("session_ticket"),
        current_price,
        snap.get("bars_5m"),
        live_quote.get("received_at_ist"),
        bars_15m=idf15,
    )
    if skip_mark:
        ticket = session_ticket
    else:
        ticket = fsrules.mark_ticket_from_tape(
            session_ticket,
            last=current_price,
            session_high=hi,
            session_low=lo,
            bars=idf15,
            symbol=key,
            asof=live_quote.get("received_at_ist"),
        )
    snap["session_ticket"] = ticket
    live = fsrules.open_ticket(ticket)
    if not live:
        snap["opening_ticket"] = None
    deriv = dict(snap.get("derivatives") or {})
    if snap.get("last_pcr") is not None:
        deriv["pcr_prev"] = snap["last_pcr"]
    try:
        import chain_flow

        chain_flow.capture(
            key,
            deriv,
            live_quote=live_quote,
            vix_level=_finite_float(((snap.get("india_ctx") or {}).get("india_vix") or {}).get("level"), 0.0),
            spot=current_price,
        )
        snap["derivatives"] = deriv
    except Exception:
        pass
    force_decision = None
    force_setup = None
    fno_head = snap.get("fno_model")
    if live:
        force_decision = live.get("decision")
        force_setup = snap.get("anchored_setup_type")
    else:
        try:
            import fno_model

            pack = fno_model.load(symbol=key)
            if pack.get("available") and idf15 is not None and len(idf15):
                micro = snap.get("microstructure") or {}
                orb = micro.get("opening_range") or {}
                fno_head = fno_model.infer(
                    idf15,
                    pack,
                    derivatives=deriv,
                    news_delta=float(snap.get("news_delta") or 0),
                    five_min_conflict=bool(micro.get("five_min_conflict")),
                    daily_decision=str(snap.get("core_decision") or "HOLD"),
                    vix_level=_finite_float(((snap.get("india_ctx") or {}).get("india_vix") or {}).get("level"), 0.0),
                    gex=snap.get("gex") or deriv.get("gex"),
                    asof=live_quote.get("received_at_ist"),
                    force_side=fsrules.infer_side_override(
                        ticket, orb, current_price, asof=live_quote.get("received_at_ist")
                    ),
                    first_clip=fsrules.is_first_clip(ticket),
                    symbol=key,
                    context={
                        "ml_proba": snap.get("ml_proba"),
                        "adj_tech": snap.get("adj_tech"),
                        "news_delta": snap.get("news_delta"),
                        "candle_bias": (snap.get("candlestick") or {}).get("bias"),
                        "session_bias": fno_live_engine.session_from_live_quote(live_quote).get(
                            "session_bias"
                        ),
                        "vix": (snap.get("india_ctx") or {}).get("india_vix"),
                    },
                )
                snap["fno_model"] = fno_head
        except Exception:
            pass
    save_snapshot(key, snap)

    ml_proba = float(snap.get("ml_proba") or 0.5)
    adj_tech = float(snap.get("adj_tech") or 50)
    combined = float(snap.get("combined_score") or 0.5)
    core_decision = str(snap.get("core_decision") or "HOLD")
    decision_info = snap.get("decision_info") or {}
    candlestick = snap.get("candlestick") or {}
    india_ctx = snap.get("india_ctx")
    atr_val = float(snap.get("atr_val") or live_quote["last_price"] * 0.02)
    micro = snap.get("microstructure") or {}

    import fno_short_horizon

    bars5_live = fno_short_horizon.patch_forming_5m(
        snap.get("bars_5m"), current_price, asof=live_quote.get("received_at_ist")
    )
    live_ctx = fno_live_engine.build_fno_live_context(
        live_quote,
        None,
        None,
        ml_proba,
        adj_tech,
        combined,
        core_decision,
        cached_micro=micro if micro.get("available") else None,
    )
    live_ctx["feed"] = feed
    live_ctx["rescore"] = "ws_ltp"
    live_ctx["fno_model"] = fno_head
    live_ctx["bars_5m"] = bars5_live
    live_ctx["bars_15m"] = idf15

    contracts = snap.get("fno_contracts")
    if contracts and contracts.get("available"):
        contracts = dict(contracts)
        contracts["spot_reference"] = round(current_price, 2)

    fno_block = product_analysis.build_fno_analysis(
        key,
        decision_info,
        ml_proba,
        adj_tech,
        float(snap.get("combined_adjust") or 0),
        candlestick,
        india_ctx,
        current_price,
        atr_val,
        fno_contracts=contracts,
        live_context=live_ctx,
        live_quote=live_quote,
        structural=snap.get("structural"),
        indicators=snap.get("indicators"),
        market_tilt=snap.get("market_tilt"),
        force_decision=force_decision,
        force_setup_type=force_setup,
        day_range=snap.get("day_range"),
        same_session_only=True,
        asof=live_quote.get("received_at_ist"),
        session_ticket=ticket,
        fno_model=fno_head,
        indications=_last_indications(key),
    )
    fno_block = merge_volatility_into_block(
        snap, key, current_price, fno_block, live_context=live_ctx, live_quote=live_quote
    )
    if key == "NIFTY":
        import nifty_fno_runtime

        fno_block = nifty_fno_runtime.prepare_block(
            fno_block, ticket, bars=idf15, quote=live_quote,
            asof=live_quote.get("received_at_ist"),
        )

    risk = fno_risk_engine.fno_risk_for_api(fno_block.get("risk") or {})
    trade = (risk.get("fno_trade") or {})
    now = market_symbols.ist_now()
    import session_calls

    india = snap.get("india_ctx") or {}
    dual_ev = None
    dual_call = None
    list_decision = str(fno_block.get("decision") or "HOLD")
    list_sl = trade.get("stop_loss")
    list_t1 = trade.get("target_1")
    list_entry = current_price
    import fno_live_config

    use_dual = fno_live_config.use_dual_track()
    stacked = fno_live_config.enable_stacked_calls()
    snap["use_dual_track"] = use_dual
    snap["stacked_calls"] = stacked
    good_decision = list_decision
    run_dual = bool(fno_live_config.is_fno_live_index(key) and (use_dual or stacked))
    if run_dual:
        try:
            import fno_live_dual_track

            holder0 = {"fno_analysis": fno_block, "fno_model": fno_head or {}}
            dual_ev = fno_live_dual_track.apply_to_analyze_result(
                key,
                holder0,
                bars=idf15,
                asof=live_quote.get("received_at_ist") or now,
                session_ticket=ticket,
                price=current_price,
                day_range=snap.get("day_range"),
            )
            fno_block = holder0.get("fno_analysis") or fno_block
            if isinstance(holder0.get("fno_model"), dict):
                fno_head = holder0["fno_model"]
                live_ctx["fno_model"] = fno_head
            dual_call = (dual_ev or {}).get("call_payload")
        except Exception as exc:
            dual_ev = None
            snap["dual_track_error"] = str(exc)
            print(f"[fno_ws_rescore] dual_track failed for {key}: {exc}")
    # NIFTY Calls = research thrusts only (no dual-block skip).
    suppress_dual_pre = bool(fno_live_config.suppress_dual_list_for(key))
    if key == "NIFTY":
        nifty_payloads_fast: list = []
        if fno_live_config.enable_nifty_morning_strong_thrust():
            try:
                import nifty_morning_strong_thrust as nmst

                mthrust = nmst.evaluate(
                    idf15,
                    bars5_live if bars5_live is not None else idf5,
                    asof=live_quote.get("received_at_ist") or now,
                    price=current_price,
                )
                if isinstance(mthrust, dict) and mthrust.get("decision") == "BUY":
                    nifty_payloads_fast.append(mthrust)
                    dual_call = mthrust
                    snap["nifty_morning_strong_thrust"] = True
                    snap["nifty_morning_strong_thrust_payload"] = mthrust
            except Exception as exc:
                snap["nifty_morning_strong_thrust_error"] = str(exc)
        if fno_live_config.enable_nifty_afternoon_thrust():
            try:
                import nifty_afternoon_thrust as nat

                thrust = nat.evaluate(
                    idf15,
                    asof=live_quote.get("received_at_ist") or now,
                    price=current_price,
                )
                if isinstance(thrust, dict) and thrust.get("decision") == "BUY":
                    nifty_payloads_fast.append(thrust)
                    dual_call = thrust
                    snap["nifty_afternoon_thrust"] = True
                    snap["nifty_afternoon_thrust_payload"] = thrust
            except Exception as exc:
                snap["nifty_afternoon_thrust_error"] = str(exc)
        if nifty_payloads_fast:
            snap["nifty_list_payloads"] = nifty_payloads_fast
            if len(nifty_payloads_fast) > 1:
                try:
                    import nifty_calls_live

                    dual_call = nifty_calls_live.merge_payloads(nifty_payloads_fast)
                    snap["nifty_call_merged"] = True
                except Exception:
                    dual_call = nifty_payloads_fast[-1]
    if stacked and fno_live_config.is_fno_live_index(key):
        try:
            import fno_stacked_calls

            thrust_keep = isinstance(dual_call, dict) and (
                dual_call.get("afternoon_thrust") or dual_call.get("morning_strong_thrust")
            )
            stack_pick = fno_stacked_calls.choose_list_source(
                dual_call=dual_call if isinstance(dual_call, dict) else None,
                good_decision=good_decision,
                session_ticket=ticket,
                symbol=key,
                asof=live_quote.get("received_at_ist") or now,
            )
            snap["stacked_pick"] = {
                "track": stack_pick.get("track"),
                "decision": stack_pick.get("decision"),
                "reason": stack_pick.get("reason"),
                "htf": stack_pick.get("htf"),
            }
            if stack_pick.get("use_dual_payload") and isinstance(
                stack_pick.get("call_payload"), dict
            ):
                dual_call = stack_pick["call_payload"]
            elif thrust_keep:
                # Stacked pick ignores confident thrust — keep research afternoon lane.
                pass
            else:
                dual_call = None
                if stack_pick.get("use_good") and stack_pick.get("decision") in (
                    "BUY",
                    "SELL",
                ):
                    list_decision = str(stack_pick["decision"])
        except Exception as exc:
            snap["stacked_calls_error"] = str(exc)
            print(f"[fno_ws_rescore] stacked_calls failed for {key}: {exc}")
    suppress_dual = bool(fno_live_config.suppress_dual_list_for(key))
    # Confident thrust lanes are not dual proven/champion — always listable.
    if isinstance(dual_call, dict) and (
        dual_call.get("afternoon_thrust") or dual_call.get("morning_strong_thrust")
    ):
        suppress_dual = False
    snap["suppress_dual_list"] = suppress_dual
    if isinstance(dual_call, dict) and dual_call.get("decision") in ("BUY", "SELL"):
        fno_block = dict(fno_block)
        fno_block["dual_track_call"] = dual_call
        if dual_call.get("afternoon_thrust"):
            fno_block["nifty_afternoon_thrust"] = True
        if dual_call.get("morning_strong_thrust"):
            fno_block["nifty_morning_strong_thrust"] = True
        if stacked:
            fno_block["stacked_calls"] = True
        if suppress_dual:
            # Dual annotate only. NIFTY board fills from research thrusts.
            fno_block["dual_list_suppressed"] = True
            notes = list(fno_block.get("desk_alerts") or [])
            msg = (
                "NIFTY Calls: morning strong + afternoon thrust only (dual annotate)."
                if key == "NIFTY"
                else (
                    "Dual proven/champion list suppressed — "
                    "CHAMP_PLUS / crown fill when board empty."
                )
            )
            if msg not in notes:
                notes.insert(0, msg)
            fno_block["desk_alerts"] = notes
            # Dual fired but is not listing — also block ExtraTrees fall-through.
            held = fno_live_config.suppress_core_list_if_needed(
                list_decision, dual_call=None
            )
            if held != list_decision:
                list_decision = held
                fno_block["decision"] = "HOLD"
                fno_block["extra_trees_single_disabled"] = True
        else:
            # research thrust (or BN/SX dual) list with accuracy tags
            list_decision = str(dual_call["decision"])
            list_sl = dual_call.get("stop_loss", list_sl)
            list_t1 = dual_call.get("target_1", list_t1)
            list_entry = dual_call.get("entry", list_entry)
            fno_block["decision"] = list_decision
            if dual_call.get("accuracy_label"):
                fno_block["headline"] = dual_call.get("accuracy_label")
            risk = dict(risk or {})
            ft = dict(risk.get("fno_trade") or trade or {})
            ft["stop_loss"] = list_sl
            ft["target_1"] = list_t1
            ft["entry"] = list_entry
            risk["fno_trade"] = ft
            trade = ft
        if key == "NIFTY" and snap.get("nifty_list_payloads"):
            fno_block["nifty_list_payloads"] = snap.get("nifty_list_payloads")
            if snap.get("nifty_morning_strong_thrust_payload"):
                fno_block["nifty_morning_strong_thrust_payload"] = snap[
                    "nifty_morning_strong_thrust_payload"
                ]
            if snap.get("nifty_afternoon_thrust_payload"):
                fno_block["nifty_afternoon_thrust_payload"] = snap[
                    "nifty_afternoon_thrust_payload"
                ]
    elif (
        fno_live_config.is_fno_live_index(key)
        and fno_live_config.enable_pre_dual_single()
        and (not use_dual or stacked)
    ):
        fno_block = dict(fno_block)
        fno_block["pre_dual_single"] = True
        fno_block["good"] = True
        if stacked:
            fno_block["stacked_calls"] = True
        if list_decision in ("BUY", "SELL"):
            fno_block["headline"] = (
                f"Stacked · good core (~{fno_live_config.STACK_HIT_PCT_6M:.0f}% 6m research)"
                if stacked
                else "Good · pre-dual single (~71%)"
            )
    elif fno_live_config.is_fno_live_index(key):
        # Dual exclusive: never list ExtraTrees single fall-through.
        # When dual list is suppressed, treat as no dual list so core stays HOLD.
        dual_for_core = (
            None
            if suppress_dual
            else (dual_call if isinstance(dual_call, dict) else None)
        )
        held = fno_live_config.suppress_core_list_if_needed(
            list_decision, dual_call=dual_for_core
        )
        if held != list_decision:
            list_decision = held
            fno_block = dict(fno_block)
            fno_block["decision"] = "HOLD"
            fno_block["extra_trees_single_disabled"] = True
            notes = list(fno_block.get("desk_alerts") or [])
            msg = (
                "ExtraTrees single 15m listing disabled — "
                + (
                    "CHAMP_PLUS / crown fill path (dual list suppressed)."
                    if suppress_dual
                    else "dual proven/champion only."
                )
            )
            if msg not in notes:
                notes.insert(0, msg)
            fno_block["desk_alerts"] = notes
    # Live confluence → Suggestions only (never lists / never flips decision).
    if fno_live_config.is_fno_live_index(key) and list_decision in ("HOLD", ""):
        try:
            import fno_live_confluence_call

            holder_live = {
                "decision": list_decision,
                "fno_analysis": fno_block,
                "candlestick": snap.get("candlestick"),
                "live_context": live_ctx,
                "symbol": key,
            }
            sug = fno_live_confluence_call.apply_if_hold(
                holder_live,
                price=current_price,
                open_call=None,
                session_ticket=ticket,
                asof=now,
                symbol=key,
            )
            fno_block = holder_live.get("fno_analysis") or fno_block
            if isinstance(sug, dict) and sug.get("decision") in ("BUY", "SELL"):
                snap["suggestion"] = sug
        except Exception:
            pass
    if fsrules.open_ticket(ticket) and fsrules.is_live_confluence_ticket(ticket):
        ticket = fsrules.cancel_open_ticket(ticket, closed_at=now.isoformat())
        notes = list(fno_block.get("desk_alerts") or [])
        msg = "Prior live-indication call cancelled — live path is suggest-only now."
        if msg not in notes:
            notes.insert(0, msg)
        fno_block = dict(fno_block)
        fno_block["desk_alerts"] = notes
    readings = session_calls.live_readings(
        fno_head=fno_head,
        live_context=live_ctx,
        candlestick=snap.get("candlestick"),
        derivatives=snap.get("derivatives"),
        vix_level=_finite_float(((india.get("india_vix") or {}).get("level")), 0.0),
        setup_type=fno_block.get("setup_type"),
        core_decision=core_decision,
    )
    listed_from_dual = (
        isinstance(dual_call, dict)
        and dual_call.get("decision") in ("BUY", "SELL")
        and not suppress_dual
    )
    if listed_from_dual and isinstance(readings, dict):
        if dual_call.get("morning_strong_thrust"):
            import nifty_morning_strong_thrust as nmst

            nmst.stamp_readings(readings, dual_call)
            snap["suggestion"] = nmst.as_suggestion(dual_call)
            fno_block = dict(fno_block)
            fno_block["headline"] = dual_call.get("accuracy_label") or nmst.ACCURACY_LABEL
        elif dual_call.get("afternoon_thrust"):
            import nifty_afternoon_thrust as nat

            nat.stamp_readings(readings, dual_call)
            snap["suggestion"] = nat.as_suggestion(dual_call)
            fno_block = dict(fno_block)
            fno_block["headline"] = dual_call.get("accuracy_label") or nat.ACCURACY_LABEL
        else:
            readings["accuracy_tags"] = dual_call.get("accuracy_tags")
            readings["model_view"] = dual_call.get("model_view")
            readings["p_sl"] = (dual_call.get("model_view") or {}).get("p_sl")
            if stacked:
                fno_live_config.stamp_stack_dual_readings(readings, dual_call=dual_call)
            else:
                readings["dual_track"] = True
                track = str(dual_call.get("track") or "champion")
                readings["track"] = track
                readings["source"] = track
                readings["accuracy_label"] = dual_call.get("accuracy_label")
                readings["proven_100"] = track == "proven_100"
                readings["history_eligible"] = True
                readings["priority"] = (
                    100 if track == "proven_100" else (80 if track == "champion" else 60)
                )
                readings["live_confluence"] = False
            # Enrich Clean morning + Clean multi tags (candle / overlay / NSE mid)
            try:
                import fno_clean_call_tags as clean_tags

                candle_bias = (snap.get("candlestick") or {}).get("bias")
                nse_mid = None
                if stacked:
                    try:
                        import fno_nse_mid_gate as nse_gate

                        if nse_gate.enabled() and key in ("NIFTY", "NIFTY 50", "NIFTY50"):
                            nse_mid = nse_gate.passes(now)
                    except Exception:
                        nse_mid = None
                clean_tags.enrich_readings_clean(
                    readings,
                    dual_call=dual_call,
                    asof=now,
                    candle_bias=candle_bias,
                    nse_mid=nse_mid,
                    overlay_today=snap.get("overlay_indication_today"),
                    overlay_sig=snap.get("overlay_indication"),
                    snap=snap,
                )
                if dual_call.get("clean"):
                    if dual_call.get("accuracy_label"):
                        fno_block = dict(fno_block)
                        fno_block["headline"] = dual_call.get("accuracy_label")
                        fno_block["clean"] = True
                        fno_block["clean_multi"] = bool(dual_call.get("clean_multi"))
                        fno_block["clean_morning"] = bool(dual_call.get("clean_morning"))
                        fno_block["clean_recipe"] = dual_call.get("clean_recipe")
            except Exception:
                pass
    elif (
        isinstance(readings, dict)
        and fno_live_config.enable_pre_dual_single()
        and (not use_dual or stacked)
        and fno_live_config.is_fno_live_index(key)
    ):
        fno_live_config.stamp_good_readings(readings, decision=list_decision)
    if key == "NIFTY" and (
        stacked
        or use_dual
        or (
            isinstance(dual_call, dict)
            and (dual_call.get("afternoon_thrust") or dual_call.get("morning_strong_thrust"))
        )
    ):
        try:
            import fno_p2f_live

            holder_p2f = {"fno_analysis": fno_block}
            fno_p2f_live.annotate(
                holder_p2f,
                symbol=key,
                dual_call=dual_call if isinstance(dual_call, dict) else None,
                readings=readings if isinstance(readings, dict) else None,
            )
            fno_block = holder_p2f.get("fno_analysis") or fno_block
            if holder_p2f.get("p2f_live"):
                snap["p2f_live"] = holder_p2f["p2f_live"]
            if holder_p2f.get("champ_plus_live"):
                snap["champ_plus_live"] = holder_p2f["champ_plus_live"]
        except Exception as exc:
            snap["p2f_live_error"] = str(exc)
    elif key == "SENSEX" and (stacked or use_dual):
        try:
            import fno_sensex_final_live

            holder_sx = {"fno_analysis": fno_block}
            fno_sensex_final_live.annotate(
                holder_sx,
                symbol=key,
                dual_call=dual_call if isinstance(dual_call, dict) else None,
                readings=readings if isinstance(readings, dict) else None,
            )
            fno_block = holder_sx.get("fno_analysis") or fno_block
            if holder_sx.get("final_sensex_fno"):
                snap["final_sensex_fno"] = holder_sx["final_sensex_fno"]
            if isinstance(dual_call, dict) and dual_call.get("decision") in ("BUY", "SELL"):
                list_sl = dual_call.get("stop_loss", list_sl)
                list_t1 = dual_call.get("target_1", list_t1)
                list_entry = dual_call.get("entry", list_entry)
        except Exception as exc:
            snap["final_sensex_fno_error"] = str(exc)
    ticket = fsrules.persist_new_ticket(
        ticket,
        decision=list_decision,
        stop_loss=list_sl,
        target_1=list_t1,
        taken_at=now.isoformat(),
        session_date_value=now.date(),
        entry=list_entry,
        target_2=trade.get("target_2"),
        p_t1=(
            (dual_call.get("p_t1") if isinstance(dual_call, dict) else None)
            or (fno_head or {}).get("p_t1")
        ),
        p_meta=(
            (dual_call.get("p_t1") if isinstance(dual_call, dict) else None)
            or ((fno_head or {}).get("p_meta") or (fno_head or {}).get("p_t1"))
        ),
        regime=((fno_head or {}).get("regime") or {}).get("name")
        or (dual_call or {}).get("regime"),
        readings=readings,
        symbol=key,
        bars=idf15,
        live_quote=live_quote,
    )
    snap["session_ticket"] = ticket
    snap["anchored_decision"] = list_decision
    holder = {"fno_analysis": fno_block}
    if use_dual and isinstance(dual_ev, dict) and dual_ev.get("suggestion_payload"):
        holder["suggestion"] = dual_ev["suggestion_payload"]
    fsrules.stamp_call_suggestion(
        holder,
        fno_head,
        price=current_price,
        session_ticket=ticket,
        symbol=key,
        bars=idf15,
        live_quote=live_quote,
        live_context=live_ctx,
        day_range=snap.get("day_range"),
    )
    snap["suggestion"] = holder.get("suggestion")
    import fno_point_journal

    fno_point_journal.attach(holder, key, idf15, idf5, fno_head)
    snap["point_journal"] = holder.get("point_journal")
    save_snapshot(key, snap)

    calls = []
    try:
        import session_calls

        calls = session_calls.sync_session(
            session_calls.default_db_path(),
            stock=key,
            product="fno",
            session_ticket=ticket,
            extra={"source": "ws_rescore"},
        )
    except Exception:
        import session_calls

        calls = session_calls.ticket_rows(ticket)

    split = session_calls.split_live(calls)
    try:
        import fno_live_archive

        fno_live_archive.maybe_record(
            stock=key,
            fno_analysis=fno_block,
            price=current_price,
            active_call=split.get("active"),
        )
    except Exception:
        pass
    try:
        import fno_short_horizon_log

        fno_short_horizon_log.maybe_record_and_settle(
            stock=key,
            short_horizon=(fno_block or {}).get("short_horizon"),
            price=current_price,
            live_context=live_ctx,
            indications=(fno_block or {}).get("indications"),
            bars_5m=idf5,
        )
    except Exception:
        pass
    payload = {
        "stock_input": key,
        "product": "fno",
        "source": "ws_ltp_rescore",
        "live_feed": feed,
        "core_decision": core_decision,
        # Must match ticket listing (dual-track list_decision), not core-only block.
        "decision": list_decision,
        "confidence": fno_block.get("confidence"),
        "summary": fno_block.get("headline"),
        "current_price": round(current_price, 2),
        "live_market": live_quote,
        "fno_analysis": fno_block,
        "fno_model": fno_head or fno_block.get("fno_model"),
        "risk_management": risk,
        "rescore_at": now.isoformat(),
        "decision_anchored": bool(live),
        "session_ticket": ticket,
        "session_tickets": split["all"],
        "active_call": split["active"],
        "call_history": split["history"],
        "suggestion": snap.get("suggestion") or fno_block.get("suggestion"),
        "predictions": fno_block.get("predictions"),
        "point_journal": fno_block.get("point_journal") or snap.get("point_journal"),
        "alerts": fno_block.get("alerts"),
        "alerts_summary": fno_block.get("alerts_summary"),
        "tape_read": None,
    }
    if snap.get("dual_track_error"):
        payload["dual_track_error"] = snap.get("dual_track_error")
    import option_ticket

    active = split.get("active")
    max_loss = option_ticket.resolve_max_loss_inr(snapshot=snap)
    fp = option_fingerprint(active, max_loss)
    cached_order = snap.get("option_order")
    cached_ok = (
        fp
        and fp == snap.get("option_fp")
        and isinstance(cached_order, dict)
        and abs(float(cached_order.get("max_loss_inr") or 0) - float(max_loss)) < 0.5
    )
    if cached_ok:
        payload["option_order"] = cached_order
        fa = dict(payload.get("fno_analysis") or {})
        fa["option_order"] = cached_order
        payload["fno_analysis"] = fa
    else:
        option_ticket.attach_for_open_call(
            payload,
            key,
            active,
            float(current_price or 0),
            max_loss_inr=max_loss,
        )
        snap["option_order"] = payload.get("option_order")
        snap["option_fp"] = fp
        save_snapshot(key, snap)
    try:
        session_calls.note_option(
            session_calls.default_db_path(),
            stock=key,
            product="fno",
            session_ticket=ticket,
            order=payload.get("option_order"),
        )
    except Exception:
        pass
    # Notify after option guide so NEW/BOOK/DROP alerts carry Groww contract + premiums.
    try:
        import desktop_notify

        if isinstance(ticket, dict) and isinstance(payload.get("option_order"), dict):
            readings = dict(ticket.get("readings") or {})
            if not readings.get("option") and payload["option_order"].get("tradingsymbol"):
                readings["option"] = payload["option_order"]
                ticket["readings"] = readings
        desktop_notify.notify_ticket_change(key, ticket_before, ticket)
    except Exception:
        pass
    attach_overlay_indication(payload, key, idf15, float(current_price))
    # Re-stamp Clean multi after overlay is known (candle∨overlay confirm)
    if key in ("NIFTY", "NIFTY 50", "NIFTY50"):
        try:
            import fno_clean_call_tags as clean_tags

            candle_bias = (
                (payload.get("candlestick") or {}).get("bias")
                or (snap.get("candlestick") or {}).get("bias")
            )
            ticket = snap.get("session_ticket")
            readings = (
                dict(ticket.get("readings") or {})
                if isinstance(ticket, dict)
                else {}
            )
            dual = (
                (payload.get("fno_analysis") or {}).get("dual_track_call")
                or readings
            )
            if isinstance(dual, dict) and clean_tags.is_quality_track(
                dual.get("track") or readings.get("track")
            ):
                clean_tags.stamp_clean(
                    dual,
                    asof=now,
                    candle_bias=candle_bias,
                    overlay_today=payload.get("overlay_indication_today"),
                    overlay_sig=payload.get("overlay_indication"),
                    snap=payload,
                    track=dual.get("track") or readings.get("track"),
                    decision=dual.get("decision") or readings.get("decision") or list_decision,
                    p_t1=dual.get("p_t1") or readings.get("p_t1"),
                )
                if dual.get("clean") and isinstance(ticket, dict):
                    readings.update(
                        {
                            "accuracy_tags": dual.get("accuracy_tags"),
                            "accuracy_label": dual.get("accuracy_label"),
                            "clean": True,
                            "clean_multi": dual.get("clean_multi"),
                            "clean_morning": dual.get("clean_morning"),
                            "clean_recipe": dual.get("clean_recipe"),
                        }
                    )
                    ticket["readings"] = readings
                    snap["session_ticket"] = ticket
                    if dual.get("accuracy_label"):
                        payload["summary"] = dual.get("accuracy_label")
        except Exception:
            pass
    if fno_live_config.is_fno_live_index(key):
        # Live desk: dual proven/champion + 5m crown + 15m classic (pre-dual prod2).
        # daily_fill: shadow (DAILY_FILL_SHADOW=1) or live (ENABLE_DAILY_FILL=1).
        try:
            import fno_5m_crown

            fno_5m_crown.attach_to_result(
                payload,
                key,
                idf5,
                bars_1m=None,
                price=float(current_price),
                asof=now,
                day_range=snap.get("day_range"),
            )
        except Exception as exc:
            payload["crown_5m_error"] = str(exc)
        try:
            import fno_15m_classic

            fno_15m_classic.attach_to_result(
                payload,
                key,
                idf15,
                price=float(current_price),
                asof=now,
                fno_head=payload.get("fno_model"),
                day_range=snap.get("day_range"),
            )
        except Exception as exc:
            payload["classic_15m_error"] = str(exc)
        try:
            import fno_daily_fill

            if fno_daily_fill.enabled():
                fno_daily_fill.attach_to_result(
                    payload,
                    key,
                    idf15,
                    bars_5m=idf5,
                    price=float(current_price),
                    asof=now,
                    day_range=snap.get("day_range"),
                )
        except Exception as exc:
            payload["daily_fill_error"] = str(exc)
        try:
            import fno_move_capture

            if fno_move_capture.enabled():
                fno_move_capture.attach_to_result(
                    payload,
                    key,
                    idf15,
                    price=float(current_price),
                    asof=now,
                    session_ticket=ticket,
                )
        except Exception as exc:
            payload["move_capture_error"] = str(exc)
        # 10m CHAMP / 5m crown → Calls board when 15m dual did not list.
        try:
            import fno_dual_modal_list
            import session_calls as _sc_fill

            ticket2 = fno_dual_modal_list.fill_from_channels(
                payload,
                symbol=key,
                session_ticket=ticket,
                bars=idf15,
                live_quote=live_quote,
                db_path=_sc_fill.default_db_path(),
                asof=now,
            )
            if ticket2 is not None:
                ticket = ticket2
                snap["session_ticket"] = ticket
                payload["session_ticket"] = ticket
                calls = _sc_fill.ticket_rows(ticket)
                split = _sc_fill.split_live(calls)
                payload["session_tickets"] = split["all"]
                payload["active_call"] = split["active"]
                payload["call_history"] = split["history"]
        except Exception as exc:
            payload["dual_modal_list_error"] = str(exc)
    return payload, None


def _hold_decision() -> Dict[str, Any]:
    return {
        "decision": "HOLD",
        "confidence": 50,
        "combined_score": 0.5,
        "signal_quality": "HIGH",
        "agreement_score": 70,
        "signals_agree": True,
    }


def attach_overlay_indication(
    result: Dict[str, Any],
    key: str,
    fno_bars: Any,
    current_price: float,
) -> None:
    """Overlay indication channel retired — dual accurate calls only.

    Kept as a no-op stub so callers do not break; never evaluates or notifies.
    """
    result["overlay_indication"] = None
    result["overlay_indication_today"] = []
    result["overlay_indication_open"] = []
    result["overlay_indication_disabled"] = True
    result["overlay_indication_note"] = (
        "Overlay indication removed — use dual proven/champion for NIFTY/BN/SENSEX."
    )
    return
    # --- retired body below (unreachable) ---
    if not fno_live_config.is_fno_live_index(key):
        return
    if fno_bars is None or len(fno_bars) < 80:
        return
    try:
        import fno_overlay_indication as foi
        import overlay_indication_store as ois
    except Exception as exc:
        result["overlay_indication_error"] = str(exc)
        return

    try:
        fno_bars = foi._ensure_ohlc(fno_bars)
    except Exception:
        pass

    # Path + book/drop management on open rows (rules, favour floor, early kill)
    try:
        _cols = {str(c).lower(): c for c in fno_bars.columns}
        _hi = _cols.get("high") or "High"
        _lo = _cols.get("low") or "Low"
        bar_hi = float(fno_bars[_hi].iloc[-1])
        bar_lo = float(fno_bars[_lo].iloc[-1])
    except Exception:
        bar_hi = float(current_price)
        bar_lo = float(current_price)
    path_hi = max(bar_hi, float(current_price))
    path_lo = min(bar_lo, float(current_price))
    try:
        for open_row in ois.list_open(key):
            try:
                closed = ois.manage_open_trade(
                    int(open_row["id"]),
                    fno_bars,
                    high=path_hi,
                    low=path_lo,
                    last=float(current_price),
                )
                if closed and closed.get("status") != "open":
                    _toast_overlay_exit(key, closed)
            except Exception:
                pass
    except Exception as exc:
        result["overlay_indication_error"] = str(exc)

    try:
        sig = foi.evaluate_latest(fno_bars, key)
        result["overlay_indication"] = sig
        if isinstance(sig, dict) and sig.get("decision") in ("BUY", "SELL"):
            saved = ois.upsert_signal(sig)
            result["overlay_indication_saved"] = saved
            # New bar → toast immediately. Also catch rows saved earlier with notify_sent=0
            # (backfill / OHLC crash) so open indications still alert once.
            if saved.get("created") and saved.get("notify"):
                _toast_overlay_row(key, sig, int(saved["id"]))
    except Exception as exc:
        result["overlay_indication_error"] = str(exc)

    try:
        _catchup_unsent_overlay_notifies(key)
    except Exception:
        pass

    try:
        today = ois.list_today(key)
        opens = ois.list_open(key)
        result["overlay_indication_today"] = ois.enrich_ui_alerts(
            today, last_price=float(current_price)
        )
        result["overlay_indication_open"] = ois.enrich_ui_alerts(
            opens, last_price=float(current_price)
        )
        # Live BOOK NOW / DROP NOW while still open → desk + WhatsApp channel
        _toast_overlay_live_alerts(key, result["overlay_indication_open"])
    except Exception as exc:
        result.setdefault("overlay_indication_today", [])
        result.setdefault("overlay_indication_open", [])
        result["overlay_indication_error"] = str(exc)


def _toast_overlay_row(key: str, sig: Dict[str, Any], row_id: int) -> bool:
    """Fire desktop toast for one overlay indication; claim notify slot first (no dupes)."""
    try:
        import fno_overlay_indication as foi

        if not foi.overlay_notify_enabled():
            return False
    except Exception:
        return False
    try:
        import desktop_notify
        import overlay_indication_store as ois

        rid = int(row_id)
        if not ois.claim_notify_sent(rid):
            return False
        ok = desktop_notify.notify_overlay_indication(
            key,
            str(sig.get("decision") or ""),
            entry=sig.get("entry"),
            stop=sig.get("stop_loss"),
            target=sig.get("target_1"),
            accuracy_label=sig.get("accuracy_label"),
            rules=sig.get("rule_labels"),
            favour_bars=sig.get("favour_bars"),
            favour_minutes=sig.get("favour_minutes"),
            med_favour_pts=sig.get("med_favour_pts"),
            favour_label=sig.get("favour_label"),
            book_label=sig.get("book_profit_label") or sig.get("book_profit_label"),
            stop_label=sig.get("stop_label"),
            row_id=rid,
        )
        if not ok:
            ois.release_notify_sent(rid)
        return bool(ok)
    except Exception:
        try:
            import overlay_indication_store as ois

            ois.release_notify_sent(int(row_id))
        except Exception:
            pass
        return False


def _toast_overlay_exit(key: str, closed: Dict[str, Any]) -> None:
    """BOOK PROFIT / DROP TRADE toast when an open overlay indication closes."""
    try:
        import fno_overlay_indication as foi

        if not foi.overlay_notify_enabled():
            return
    except Exception:
        return
    try:
        import desktop_notify

        kind = str(closed.get("alert_kind") or closed.get("status") or "")
        side = str(closed.get("decision") or "")
        entry = closed.get("entry")
        fav = closed.get("favour_pts")
        plain = str(closed.get("status_plain") or kind)
        rid = closed.get("id")
        dedupe = (
            f"overlay:exit:{key}:{int(rid)}:{kind or closed.get('status')}"
            if rid is not None
            else None
        )
        if kind in ("booked_rule", "booked_favour") or closed.get("status") == "booked":
            desktop_notify.notify_overlay_book(
                key, side, reason=plain, entry=entry, favour_pts=fav, dedupe_key=dedupe
            )
        elif kind in ("stopped_rule", "stopped_early") or closed.get("status") == "stopped":
            desktop_notify.notify_overlay_drop(
                key, side, reason=plain, entry=entry, favour_pts=fav, dedupe_key=dedupe
            )
        elif closed.get("status") == "expired":
            desktop_notify.notify(
                "CALL CLOSED",
                f"{key} {side} · Overlay indication\nFavour window ended — review / exit if still open. {plain}",
                stock=key,
                kind="overlay_close",
                decision=side,
                entry=entry,
                dedupe_key=dedupe,
                payload={"action": "CLOSE", "channel": "Overlay indication"},
            )
    except Exception:
        pass


def _toast_overlay_live_alerts(key: str, open_rows: Any) -> None:
    """Push BOOK/DROP desk notifications while overlay trades are still open."""
    try:
        import fno_overlay_indication as foi

        if not foi.overlay_notify_enabled():
            return
        import desktop_notify
    except Exception:
        return
    for row in open_rows or []:
        if not isinstance(row, dict):
            continue
        alert = row.get("ui_alert") or {}
        level = str(alert.get("level") or "")
        if level not in ("book", "drop"):
            continue
        try:
            desktop_notify.notify_overlay_live_alert(
                key,
                str(row.get("decision") or alert.get("decision") or ""),
                level=level,
                detail=str(alert.get("detail") or ""),
                entry=row.get("entry"),
                favour_pts=alert.get("favour_pts") or row.get("favour_pts"),
                row_id=row.get("id"),
            )
        except Exception:
            pass


def _catchup_unsent_overlay_notifies(key: str) -> None:
    """Toast once for open overlay rows that were saved without a notification."""
    try:
        import fno_overlay_indication as foi

        if not foi.overlay_notify_enabled():
            return
    except Exception:
        return
    import overlay_indication_store as ois

    for row in ois.list_open(key):
        if int(row.get("notify_sent") or 0) == 1:
            continue
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        sig = {
            "decision": row.get("decision"),
            "entry": row.get("entry"),
            "stop_loss": row.get("stop_loss"),
            "target_1": row.get("target_1"),
            "accuracy_label": row.get("accuracy_label") or payload.get("accuracy_label"),
            "rule_labels": payload.get("rule_labels"),
            "favour_bars": row.get("favour_bars") or payload.get("favour_bars"),
            "favour_minutes": row.get("favour_minutes") or payload.get("favour_minutes"),
            "med_favour_pts": row.get("med_favour_pts") or payload.get("med_favour_pts"),
            "favour_label": row.get("favour_label") or payload.get("favour_label"),
            "book_profit_label": row.get("book_profit_label") or payload.get("book_profit_label"),
            "stop_label": row.get("stop_label") or payload.get("stop_label"),
        }
        _toast_overlay_row(key, sig, int(row["id"]))


def scheduled_refresh(
    stock_key: str,
    indian_stocks: Dict[str, str],
    *,
    max_loss_inr: Optional[float] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """90-second F&O pass. Same call rules as Analyze, without the daily stock stack.

    Reuses the last manual read for the daily decision, news, and VIX. Refreshes
    the 5-minute and 15-minute tape, the option chain, and the option to buy.
    Optional max_loss_inr (from UI Settings) overrides snapshot/default for option sizing.
    """
    started = time.time()
    key = stock_key_from_input(stock_key)
    if not product_analysis.is_fno_primary(key):
        return None, "The 90-second refresh is for NIFTY and SENSEX. Press Analyze for a stock."

    snap = dict(get_snapshot(key) or {})
    live_quote, feed = _fetch_live_quote_ws_first(key, indian_stocks)
    if not live_quote or not live_quote.get("last_price"):
        return None, f"No live price ({feed})"
    current_price = float(live_quote["last_price"])

    idf5 = snap.get("bars_5m")
    idf15 = snap.get("bars_15m")
    bar_err = None
    if kite_data.kite_enabled():
        try:
            fresh5, _ = kite_data.fetch_historical_candles(
                key, "5minute", days=2, keep_partial=True
            )
            # keep_partial=False so decisions use completed 15m bars only.
            fresh15, bar_err = kite_data.fetch_historical_candles(key, "15minute", days=10)
            if fresh5 is not None:
                idf5 = fresh5
            if fresh15 is not None:
                idf15 = fresh15
            elif key == "NIFTY":
                bar_err = bar_err or "NIFTY 15m history refresh returned no candles"
        except Exception as exc:
            bar_err = str(exc)
    if key == "NIFTY" and bar_err:
        # Flag for core entry_issue. Dual-track persist ignores this flag when
        # the cached tape is still structurally valid (allow_dual_lag).
        live_quote = dict(live_quote)
        live_quote["history_refresh_failed"] = True

    decision_info = dict(snap.get("decision_info") or _hold_decision())
    ml_proba = float(snap.get("ml_proba") or 0.5)
    adj_tech = float(snap.get("adj_tech") or 50)
    combined_adjust = float(snap.get("combined_adjust") or 0)
    news_delta = float(snap.get("news_delta") or 0)
    india_ctx = snap.get("india_ctx")
    vix_level = _finite_float(((india_ctx or {}).get("india_vix") or {}).get("level"), 0.0)
    candlestick = snap.get("candlestick") or {}

    deriv = dict(snap.get("derivatives") or {})
    try:
        import full_market_analysis

        fresh = full_market_analysis.derivatives_snapshot(key, current_price, vix_level=vix_level)
        if fresh.get("available"):
            deriv = fresh
    except Exception:
        pass
    if vix_level > 0:
        deriv["vix_level"] = vix_level
    elif "vix_level" in deriv:
        cleaned = _finite_float(deriv.get("vix_level"), 0.0)
        if cleaned > 0:
            deriv["vix_level"] = cleaned
        else:
            deriv.pop("vix_level", None)
    if snap.get("last_pcr") is not None:
        deriv["pcr_prev"] = snap["last_pcr"]
    gex = deriv.get("gex") if isinstance(deriv.get("gex"), dict) else snap.get("gex")
    if isinstance(gex, dict):
        deriv["gex"] = gex
    try:
        import dark_pool

        deriv["dix"] = dark_pool.latest(key)
    except Exception:
        deriv["dix"] = {"available": False}
    try:
        import chain_flow

        saved = chain_flow.capture(
            key,
            deriv,
            live_quote=live_quote,
            vix_level=vix_level,
            spot=current_price,
        )
        if not saved.get("stored"):
            prior = chain_flow.readings_asof(key)
            if prior:
                deriv = prior
    except Exception:
        pass

    import fno_model
    import fno_session_rules as fsrules
    import fno_short_horizon

    idf5 = fno_short_horizon.patch_forming_5m(
        idf5, current_price, asof=live_quote.get("received_at_ist")
    )
    live_ctx = fno_live_engine.build_fno_live_context(
        live_quote,
        idf5,
        idf15,
        ml_proba,
        adj_tech,
        float(decision_info.get("combined_score") or 0.5),
        decision_info.get("decision") or "HOLD",
    )
    live_ctx["bars_5m"] = idf5
    if bar_err:
        live_ctx.setdefault("notes", []).append(f"F&O 15m history: {bar_err}")
    live_ctx["feed"] = feed
    live_ctx["rescore"] = "scheduled"

    fno_bars = idf15 if idf15 is not None and len(idf15) else None
    fno_pack = fno_model.load(symbol=key)
    if not fno_model.pack_usable(fno_pack):
        fno_pack = {"available": False, "model_version": fno_model.MODEL_VERSION}
    prev_ticket = snap.get("session_ticket")
    today_s = str(market_symbols.ist_now().date())
    if prev_ticket and str(prev_ticket.get("session_date") or "")[:10] != today_s:
        # Do not manage/block today with yesterday's open BN/Sensex/NIFTY ticket.
        prev_ticket = None
        snap["session_ticket"] = None
    if not prev_ticket:
        try:
            import session_calls as _sc

            prev_ticket = _sc.session_ticket_from_db(
                _sc.default_db_path(), key, session_date=market_symbols.ist_now().date()
            )
        except Exception:
            prev_ticket = None
    ticket_before = dict(prev_ticket) if isinstance(prev_ticket, dict) else prev_ticket
    live0 = fsrules.open_ticket(prev_ticket)
    if live0:
        hi, lo = fsrules.path_extremes(fno_bars, live0.get("taken_at"), current_price)
    else:
        hi, lo = current_price, current_price
    import fno_alerts

    prev_ticket, skip_mark = fno_alerts.settle_open_call(
        prev_ticket,
        current_price,
        idf5,
        market_symbols.ist_now(),
        bars_15m=fno_bars,
    )
    if not skip_mark:
        prev_ticket = fsrules.mark_ticket_from_tape(
            prev_ticket,
            last=current_price,
            session_high=hi,
            session_low=lo,
            bars=fno_bars,
            symbol=key,
            asof=market_symbols.ist_now(),
        )
    orb = (live_ctx.get("microstructure") or {}).get("opening_range") or {}
    fno_head = fno_model.infer(
        fno_bars,
        fno_pack,
        derivatives=deriv,
        news_delta=news_delta,
        vix_level=vix_level,
        five_min_conflict=bool((live_ctx.get("microstructure") or {}).get("five_min_conflict")),
        daily_decision=decision_info.get("decision"),
        gex=gex,
        asof=market_symbols.ist_now(),
        force_side=fsrules.infer_side_override(
            prev_ticket, orb, current_price, asof=market_symbols.ist_now()
        ),
        first_clip=fsrules.is_first_clip(prev_ticket),
        symbol=key,
        context={
            "ml_proba": ml_proba,
            "adj_tech": adj_tech,
            "news_delta": news_delta,
            "candle_bias": (candlestick or {}).get("bias"),
            "session_bias": (live_ctx.get("session") or {}).get("session_bias"),
            "vix": (india_ctx or {}).get("india_vix"),
        },
    )
    if not fno_head.get("available"):
        fno_head = {
            "available": True,
            "decision": "HOLD",
            "p_up": 0.5,
            "confidence": 45,
            "source": "fno_model_missing",
        }
    live_ctx["fno_model"] = fno_head
    live_ctx["session_model"] = fno_head

    contracts = snap.get("fno_contracts")
    try:
        import fno_instruments

        resolved = fno_instruments.resolve_contracts(key, current_price)
        if resolved and resolved.get("available"):
            # Preserve prior 3-pack suggestions (ATM refresh alone has none)
            # Drop them if open-call index SL/T moved away from the stamped levels.
            prev = contracts if isinstance(contracts, dict) else {}
            contracts = dict(resolved)
            sug = prev.get("option_suggestions")
            keep_sug = isinstance(sug, dict) and sug.get("available")
            if keep_sug:
                try:
                    act = fsrules.open_ticket(prev_ticket) or {}
                    sl = act.get("stop_loss")
                    t1 = act.get("target_1")
                    has_live = sl is not None or t1 is not None
                    stamped = (
                        sug.get("index_stop") is not None
                        or sug.get("index_target") is not None
                    )
                    has_pts = (
                        sug.get("index_risk_pts") is not None
                        or sug.get("index_reward_pts") is not None
                    )
                    if has_live and not stamped and not has_pts:
                        # Synced before the call opened — INDEX_CLIP sizing, not live SL/T.
                        keep_sug = False
                    elif has_live and stamped:
                        if sl is not None and sug.get("index_stop") is not None:
                            if abs(float(sl) - float(sug.get("index_stop"))) > 0.05:
                                keep_sug = False
                        if keep_sug and t1 is not None and sug.get("index_target") is not None:
                            if abs(float(t1) - float(sug.get("index_target"))) > 0.05:
                                keep_sug = False
                    elif has_live and has_pts and act.get("entry") is not None:
                        entry = float(act.get("entry"))
                        if sl is not None and sug.get("index_risk_pts") is not None:
                            if abs(abs(entry - float(sl)) - float(sug.get("index_risk_pts"))) > 0.05:
                                keep_sug = False
                        if keep_sug and t1 is not None and sug.get("index_reward_pts") is not None:
                            if abs(abs(float(t1) - entry) - float(sug.get("index_reward_pts"))) > 0.05:
                                keep_sug = False
                except (TypeError, ValueError):
                    keep_sug = False
            # Desk cap from UI (fast refresh) or prior snapshot
            desk_cap = None
            try:
                if max_loss_inr is not None and float(max_loss_inr) > 0:
                    desk_cap = float(max_loss_inr)
            except (TypeError, ValueError):
                desk_cap = None
            if desk_cap is None and prev.get("max_loss_inr") is not None:
                try:
                    desk_cap = float(prev.get("max_loss_inr"))
                except (TypeError, ValueError):
                    desk_cap = None
            if keep_sug and desk_cap is not None and sug.get("max_loss_inr") is not None:
                try:
                    if abs(float(sug.get("max_loss_inr")) - desk_cap) > 0.5:
                        keep_sug = False
                except (TypeError, ValueError):
                    pass
            if keep_sug and contracts.get("option_suggestions") is None:
                contracts["option_suggestions"] = sug
            elif (
                not keep_sug
                and isinstance(sug, dict)
                and sug.get("available")
            ):
                # Explicit clear so UI merge does not restore the stale base pack.
                contracts["option_suggestions"] = {
                    "available": False,
                    "reason": "Index SL/T or max-loss changed — Sync Contracts again.",
                    "stale": True,
                }
            if desk_cap is not None:
                contracts["max_loss_inr"] = desk_cap
            elif prev.get("max_loss_inr") is not None and contracts.get("max_loss_inr") is None:
                contracts["max_loss_inr"] = prev.get("max_loss_inr")
    except Exception:
        pass

    atr_val = float(snap.get("atr_val") or current_price * 0.02)
    try:
        import fno_indications

        indications = fno_indications.build(key, bars=fno_bars, price=current_price, india_ctx=india_ctx)
    except Exception:
        indications = None
    fno_block = product_analysis.build_fno_analysis(
        key,
        decision_info,
        ml_proba,
        adj_tech,
        combined_adjust,
        candlestick,
        india_ctx if isinstance(india_ctx, dict) and india_ctx.get("available") else None,
        current_price,
        atr_val,
        fno_contracts=contracts,
        live_context=live_ctx,
        live_quote=live_quote,
        structural=snap.get("structural"),
        indicators=snap.get("indicators"),
        market_tilt=snap.get("market_tilt"),
        day_range=snap.get("day_range"),
        same_session_only=True,
        asof=market_symbols.ist_now(),
        session_ticket=prev_ticket,
        fno_model=fno_head,
        indications=indications,
    )
    fno_block = merge_volatility_into_block(
        snap, key, current_price, fno_block, live_context=live_ctx, live_quote=live_quote
    )

    tape = snap.get("tape_read")
    if not isinstance(tape, dict) and fno_bars is not None:
        try:
            import opening_tape

            tape = opening_tape.read_opening(key, fno_bars, news={})
        except Exception:
            tape = None

    result: Dict[str, Any] = {
        "stock_input": key,
        "product": "fno",
        "source": "fno_refresh",
        "live_feed": feed,
        "core_decision": decision_info.get("decision") or "HOLD",
        "decision": fno_block.get("decision"),
        "confidence": fno_block.get("confidence"),
        "summary": fno_block.get("headline"),
        "current_price": round(current_price, 2),
        "live_market": live_quote,
        "fno_analysis": fno_block,
        "fno_model": fno_head,
        "tape_read": tape,
        "market_analysis": {
            "derivatives": deriv,
            "india": india_ctx if isinstance(india_ctx, dict) else {},
        },
    }
    if fno_block.get("risk"):
        result["risk_management"] = fno_risk_engine.fno_risk_for_api(fno_block["risk"])

    import opening_tape

    desk_decision = str((fno_block.get("decision") or "HOLD")).upper()
    already = bool(fsrules.closed_ticket_count(prev_ticket) or fsrules.open_ticket(prev_ticket))
    tape_overrode = False
    if not already:
        opening_tape.apply_fno_call(
            result, tape, allow_override=desk_decision in ("HOLD", "") and key != "NIFTY"
        )
        tape_overrode = bool((result.get("opening_ticket") or {}).get("available")) and str(
            result.get("decision")
        ) != str(fno_block.get("decision"))
    elif result.get("tape_read"):
        kept = dict(result["tape_read"])
        kept["historical"] = True
        result["tape_read"] = kept
    if not tape_overrode:
        result["confidence"] = fno_block.get("confidence")
        result["summary"] = fno_block.get("headline")

    now_ist = market_symbols.ist_now()
    if key == "NIFTY":
        import nifty_fno_runtime

        result["session_ticket"] = prev_ticket
        nifty_fno_runtime.finalize_result(
            result, bars=fno_bars, quote=live_quote, asof=now_ist
        )
    # Dual-track must run on the 30s/90s fast refresh too — Analyze already
    # lists proven/champion; without this, silent refresh left NIFTY on core
    # HOLD. Stacked mode also evaluates dual as add-on channels.
    dual_ev = None
    import fno_live_config

    use_dual = fno_live_config.use_dual_track()
    stacked = fno_live_config.enable_stacked_calls()
    result["use_dual_track"] = use_dual
    result["stacked_calls"] = stacked
    snap["use_dual_track"] = use_dual
    snap["stacked_calls"] = stacked
    run_dual = bool(fno_live_config.is_fno_live_index(key) and (use_dual or stacked))
    if run_dual:
        try:
            import fno_live_dual_track

            dual_ev = fno_live_dual_track.apply_to_analyze_result(
                key,
                result,
                bars=fno_bars,
                asof=now_ist,
                session_ticket=prev_ticket,
                price=current_price,
                day_range=snap.get("day_range") or result.get("day_range_forecast"),
            )
            if isinstance(result.get("fno_model"), dict):
                fno_head = result["fno_model"]
                live_ctx["fno_model"] = fno_head
                live_ctx["session_model"] = fno_head
        except Exception as exc:
            dual_ev = None
            result["dual_track_error"] = str(exc)
            print(f"[fno_ws_rescore] dual_track failed for {key}: {exc}")
    trade = ((result.get("risk_management") or {}).get("fno_trade") or {})
    tape_lv = ((result.get("tape_read") or {}).get("ticket") or {})
    live_decision = str(result.get("decision") or "HOLD")
    live_sl = trade.get("stop_loss") if trade.get("stop_loss") is not None else tape_lv.get("stop_loss")
    live_t1 = trade.get("target_1") if trade.get("target_1") is not None else tape_lv.get("target_1")
    dual_call = (dual_ev or {}).get("call_payload") if isinstance(dual_ev, dict) else None
    dual_entry = None
    good_decision = live_decision
    # Sticky pending: dual BUY windows are often one closed bar (~15m). If the
    # refresh missed that bar (restart / quote blip), retry the last scored call
    # until this symbol lists or the side invalidates — never blocked by BN/SX.
    # After 13:15 on NIFTY, do not sticky-replay suppressed dual — afternoon
    # confident thrust must be able to list (research thrust2_up30).
    suppress_dual_pre = bool(fno_live_config.suppress_dual_list_for(key))
    skip_pending_for_thrust = False
    if key == "NIFTY" and suppress_dual_pre:
        try:
            if fno_live_config.enable_nifty_morning_strong_thrust():
                import nifty_morning_strong_thrust as nmst

                skip_pending_for_thrust = bool(nmst.in_fill_window(now_ist))
            if not skip_pending_for_thrust and fno_live_config.enable_nifty_afternoon_thrust():
                import nifty_afternoon_thrust as nat

                skip_pending_for_thrust = bool(nat.in_thrust_window(now_ist))
        except Exception:
            skip_pending_for_thrust = False
    if (
        (use_dual or stacked)
        and not skip_pending_for_thrust
        and not (
            isinstance(dual_call, dict) and dual_call.get("decision") in ("BUY", "SELL")
        )
    ):
        pending = snap.get("dual_pending_call")
        pending_at = snap.get("dual_pending_at")
        if (
            isinstance(pending, dict)
            and pending.get("decision") in ("BUY", "SELL")
            and not pending.get("afternoon_thrust")
            and not pending.get("morning_strong_thrust")
            and not fsrules.open_ticket(prev_ticket)
        ):
            try:
                age_m = (
                    now_ist
                    - datetime.fromisoformat(str(pending_at).replace("Z", "+00:00")).replace(
                        tzinfo=None
                    )
                ).total_seconds() / 60.0
            except Exception:
                age_m = 999.0
            if age_m <= 20:
                dual_call = pending
                result["dual_pending_replay"] = True
    # NIFTY Calls = research thrusts only. Always evaluate both; never let dual
    # annotate block them. Same-refresh multi-fire → nifty_list_payloads merge.
    if key == "NIFTY":
        nifty_payloads: list = []
        if fno_live_config.enable_nifty_morning_strong_thrust():
            try:
                import nifty_morning_strong_thrust as nmst

                mthrust = nmst.evaluate(
                    fno_bars, idf5, asof=now_ist, price=current_price
                )
                if isinstance(mthrust, dict) and mthrust.get("decision") == "BUY":
                    nifty_payloads.append(mthrust)
                    dual_call = mthrust
                    result["nifty_morning_strong_thrust"] = True
                    result["nifty_morning_strong_thrust_payload"] = mthrust
                    snap["nifty_morning_strong_thrust"] = True
            except Exception as exc:
                result["nifty_morning_strong_thrust_error"] = str(exc)
        if fno_live_config.enable_nifty_afternoon_thrust():
            try:
                import nifty_afternoon_thrust as nat

                thrust = nat.evaluate(fno_bars, asof=now_ist, price=current_price)
                if isinstance(thrust, dict) and thrust.get("decision") == "BUY":
                    nifty_payloads.append(thrust)
                    dual_call = thrust
                    result["nifty_afternoon_thrust"] = True
                    result["nifty_afternoon_thrust_payload"] = thrust
                    snap["nifty_afternoon_thrust"] = True
            except Exception as exc:
                result["nifty_afternoon_thrust_error"] = str(exc)
        if nifty_payloads:
            result["nifty_list_payloads"] = nifty_payloads
            fa_np = dict(result.get("fno_analysis") or {})
            fa_np["nifty_list_payloads"] = nifty_payloads
            if len(nifty_payloads) > 1:
                try:
                    import nifty_calls_live

                    dual_call = nifty_calls_live.merge_payloads(nifty_payloads)
                    result["nifty_call_merged"] = True
                except Exception:
                    dual_call = nifty_payloads[-1]
            result["fno_analysis"] = fa_np

    if stacked and fno_live_config.is_fno_live_index(key):
        try:
            import fno_stacked_calls

            thrust_keep = isinstance(dual_call, dict) and (
                dual_call.get("afternoon_thrust") or dual_call.get("morning_strong_thrust")
            )
            stack_pick = fno_stacked_calls.choose_list_source(
                dual_call=dual_call if isinstance(dual_call, dict) else None,
                good_decision=good_decision,
                session_ticket=prev_ticket,
                symbol=key,
                asof=now_ist,
            )
            result["stacked_pick"] = {
                "track": stack_pick.get("track"),
                "decision": stack_pick.get("decision"),
                "reason": stack_pick.get("reason"),
                "candidates": stack_pick.get("candidates"),
                "htf": stack_pick.get("htf"),
            }
            snap["stacked_pick"] = result["stacked_pick"]
            if stack_pick.get("use_dual_payload") and isinstance(
                stack_pick.get("call_payload"), dict
            ):
                dual_call = stack_pick["call_payload"]
            elif thrust_keep:
                pass
            else:
                dual_call = None
                if stack_pick.get("use_good") and stack_pick.get("decision") in (
                    "BUY",
                    "SELL",
                ):
                    live_decision = str(stack_pick["decision"])
        except Exception as exc:
            result["stacked_calls_error"] = str(exc)
            print(f"[fno_ws_rescore] stacked_calls failed for {key}: {exc}")
    suppress_dual = bool(fno_live_config.suppress_dual_list_for(key))
    if isinstance(dual_call, dict) and (
        dual_call.get("afternoon_thrust") or dual_call.get("morning_strong_thrust")
    ):
        suppress_dual = False
    result["suppress_dual_list"] = suppress_dual
    snap["suppress_dual_list"] = suppress_dual
    if (
        use_dual
        or stacked
        or (
            isinstance(dual_call, dict)
            and (dual_call.get("afternoon_thrust") or dual_call.get("morning_strong_thrust"))
        )
    ) and isinstance(dual_call, dict) and dual_call.get("decision") in ("BUY", "SELL"):
        fa = dict(result.get("fno_analysis") or {})
        fa["dual_track_call"] = dual_call
        if dual_call.get("afternoon_thrust"):
            fa["nifty_afternoon_thrust"] = True
        if dual_call.get("morning_strong_thrust"):
            fa["nifty_morning_strong_thrust"] = True
        if stacked:
            fa["stacked_calls"] = True
        if suppress_dual:
            fa["dual_list_suppressed"] = True
            notes = list(fa.get("desk_alerts") or [])
            msg = (
                "NIFTY Calls: morning strong + afternoon thrust only (dual annotate)."
                if key == "NIFTY"
                else (
                    "Dual proven/champion list suppressed — "
                    "CHAMP_PLUS / crown fill when board empty."
                )
            )
            if msg not in notes:
                notes.insert(0, msg)
            fa["desk_alerts"] = notes
            held = fno_live_config.suppress_core_list_if_needed(
                live_decision, dual_call=None
            )
            if held != live_decision:
                live_decision = held
                result["decision"] = "HOLD"
                fa["decision"] = "HOLD"
                fa["extra_trees_single_disabled"] = True
                result["summary"] = msg
            result["fno_analysis"] = fa
            # Keep dual payload for annotate; do not promote to live_decision.
            if not result.get("dual_pending_replay"):
                snap["dual_pending_call"] = dict(dual_call)
                snap["dual_pending_at"] = now_ist.isoformat()
        else:
            live_decision = str(dual_call["decision"])
            live_sl = dual_call.get("stop_loss", live_sl)
            live_t1 = dual_call.get("target_1", live_t1)
            dual_entry = dual_call.get("entry")
            result["decision"] = live_decision
            fa["decision"] = live_decision
            result["fno_analysis"] = fa
            result["summary"] = dual_call.get("accuracy_label") or result.get("summary")
            rm = dict(result.get("risk_management") or {})
            ft = dict(rm.get("fno_trade") or {})
            ft["stop_loss"] = live_sl
            ft["target_1"] = live_t1
            ft["entry"] = dual_entry if dual_entry is not None else current_price
            rm["fno_trade"] = ft
            result["risk_management"] = rm
            if not result.get("dual_pending_replay"):
                snap["dual_pending_call"] = dict(dual_call)
                snap["dual_pending_at"] = now_ist.isoformat()
    elif (
        fno_live_config.is_fno_live_index(key)
        and fno_live_config.enable_pre_dual_single()
        and (not use_dual or stacked)
    ):
        fa = dict(result.get("fno_analysis") or {})
        fa["pre_dual_single"] = True
        fa["good"] = True
        if stacked:
            fa["stacked_calls"] = True
        result["fno_analysis"] = fa
        if live_decision in ("BUY", "SELL"):
            result["summary"] = (
                f"Stacked · good core (~{fno_live_config.STACK_HIT_PCT_6M:.0f}% 6m research)"
                if stacked
                else "Good · pre-dual single (~71%)"
            )
    elif fno_live_config.is_fno_live_index(key):
        dual_for_core = (
            None
            if suppress_dual
            else (dual_call if isinstance(dual_call, dict) else None)
        )
        held = fno_live_config.suppress_core_list_if_needed(
            live_decision, dual_call=dual_for_core
        )
        if held != live_decision:
            live_decision = held
            result["decision"] = "HOLD"
            fa = dict(result.get("fno_analysis") or {})
            fa["decision"] = "HOLD"
            fa["extra_trees_single_disabled"] = True
            notes = list(fa.get("desk_alerts") or [])
            msg = (
                "ExtraTrees single 15m listing disabled — "
                + (
                    "CHAMP_PLUS / crown fill path (dual list suppressed)."
                    if suppress_dual
                    else "dual proven/champion only."
                )
            )
            if msg not in notes:
                notes.insert(0, msg)
            fa["desk_alerts"] = notes
            result["fno_analysis"] = fa
            result["summary"] = msg
    if fno_live_config.is_fno_live_index(key) and live_decision in ("HOLD", ""):
        try:
            import fno_live_confluence_call

            fno_live_confluence_call.apply_if_hold(
                result,
                price=current_price,
                open_call=None,
                session_ticket=prev_ticket,
                asof=now_ist,
                symbol=key,
            )
        except Exception:
            pass
    if fsrules.open_ticket(prev_ticket) and fsrules.is_live_confluence_ticket(prev_ticket):
        prev_ticket = fsrules.cancel_open_ticket(prev_ticket, closed_at=now_ist.isoformat())
        fa = dict(result.get("fno_analysis") or {})
        notes = list(fa.get("desk_alerts") or [])
        msg = "Prior live-indication call cancelled — live path is suggest-only now."
        if msg not in notes:
            notes.insert(0, msg)
        fa["desk_alerts"] = notes
        result["fno_analysis"] = fa
    if not isinstance(orb, dict):
        orb = ((live_ctx or {}).get("microstructure") or {}).get("opening_range")
    # Dual-track already cleared OR + score gates — do not wipe the listed
    # decision on a microstructure shallow re-check (that blocked NIFTY lists).
    dual_listed = isinstance(dual_call, dict) and dual_call.get("decision") in ("BUY", "SELL")
    shallow_note = None
    if not dual_listed:
        shallow_note = fsrules.shallow_break_hold(
            live_decision, current_price, orb, prev_ticket, asof=now_ist
        )
    if shallow_note:
        live_decision = "HOLD"
        result["decision"] = "HOLD"
        fa = dict(result.get("fno_analysis") or {})
        fa["decision"] = "HOLD"
        notes = list(fa.get("desk_alerts") or [])
        alerts = list(fa.get("alerts") or [])
        if shallow_note not in notes:
            notes.append(shallow_note)
            alerts.append({"code": "shallow_break", "severity": "warning", "message": shallow_note})
        fa["desk_alerts"] = notes
        fa["alerts"] = alerts
        result["fno_analysis"] = fa
        result["summary"] = shallow_note
    if live_decision not in ("HOLD",):
        extra = [
            n
            for n in (
                fsrules.clock_alert(now_ist),
                fsrules.live_room_hold(live_decision, current_price, live_sl, live_t1),
            )
            if n
        ]
        safety_notes = fsrules.safety_entry_alerts(
            live_decision,
            session_ticket=prev_ticket,
            opening_range=orb,
            price=current_price,
            t1=live_t1,
            p_t1=(
                (dual_call.get("p_t1") if isinstance(dual_call, dict) else None)
                or (fno_head or {}).get("p_t1")
            ),
            fresh_break=float(((fno_head or {}).get("features") or {}).get("first_break") or 0) >= 1.0,
            asof=now_ist,
        )
        fa = dict(result.get("fno_analysis") or {})
        notes = list(fa.get("desk_alerts") or [])
        alerts = list(fa.get("alerts") or [])
        for n in extra + safety_notes:
            if n not in notes:
                notes.append(n)
                alerts.append({"code": "desk_notice", "severity": "warning", "message": n})
        fa["desk_alerts"] = notes
        fa["alerts"] = alerts
        result["fno_analysis"] = fa

    import session_calls

    conf_readings = session_calls.live_readings(
        fno_head=fno_head,
        live_context=live_ctx,
        candlestick=candlestick,
        derivatives=deriv,
        news_delta=news_delta,
        vix_level=vix_level,
        setup_type=(result.get("fno_analysis") or {}).get("setup_type"),
        core_decision=decision_info.get("decision"),
    )
    listed_from_dual = (
        isinstance(dual_call, dict)
        and dual_call.get("decision") in ("BUY", "SELL")
        and not suppress_dual
    )
    if isinstance(conf_readings, dict) and listed_from_dual:
        if dual_call.get("morning_strong_thrust"):
            import nifty_morning_strong_thrust as nmst

            nmst.stamp_readings(conf_readings, dual_call)
            result["suggestion"] = nmst.as_suggestion(dual_call)
            fa = dict(result.get("fno_analysis") or {})
            fa["headline"] = dual_call.get("accuracy_label") or nmst.ACCURACY_LABEL
            fa["suggestion"] = result["suggestion"]
            result["fno_analysis"] = fa
        elif dual_call.get("afternoon_thrust"):
            import nifty_afternoon_thrust as nat

            nat.stamp_readings(conf_readings, dual_call)
            result["suggestion"] = nat.as_suggestion(dual_call)
            fa = dict(result.get("fno_analysis") or {})
            fa["headline"] = dual_call.get("accuracy_label") or nat.ACCURACY_LABEL
            fa["suggestion"] = result["suggestion"]
            result["fno_analysis"] = fa
        else:
            conf_readings["accuracy_tags"] = dual_call.get("accuracy_tags")
            conf_readings["model_view"] = dual_call.get("model_view")
            conf_readings["p_sl"] = (dual_call.get("model_view") or {}).get("p_sl")
            if stacked:
                fno_live_config.stamp_stack_dual_readings(
                    conf_readings, dual_call=dual_call
                )
            else:
                conf_readings["dual_track"] = True
                track = str(dual_call.get("track") or "champion")
                conf_readings["track"] = track
                conf_readings["source"] = track
                conf_readings["accuracy_label"] = dual_call.get("accuracy_label")
                conf_readings["proven_100"] = track == "proven_100"
                conf_readings["history_eligible"] = True
                conf_readings["priority"] = (
                    100 if track == "proven_100" else (80 if track == "champion" else 60)
                )
                conf_readings["live_confluence"] = False
        if not dual_call.get("afternoon_thrust") and not dual_call.get("morning_strong_thrust"):
            try:
                import fno_clean_call_tags as clean_tags

                candle_bias = (candlestick or {}).get("bias")
                nse_mid = None
                if stacked:
                    try:
                        import fno_nse_mid_gate as nse_gate

                        if nse_gate.enabled() and key in ("NIFTY", "NIFTY 50", "NIFTY50"):
                            nse_mid = nse_gate.passes(now_ist)
                    except Exception:
                        nse_mid = None
                snap_ctx = {
                    "candlestick": candlestick,
                    "overlay_indication_today": result.get("overlay_indication_today")
                    or (
                        snap.get("overlay_indication_today")
                        if isinstance(snap, dict)
                        else None
                    ),
                    "overlay_indication": result.get("overlay_indication")
                    or (
                        snap.get("overlay_indication") if isinstance(snap, dict) else None
                    ),
                }
                clean_tags.enrich_readings_clean(
                    conf_readings,
                    dual_call=dual_call,
                    asof=now_ist,
                    candle_bias=candle_bias,
                    nse_mid=nse_mid,
                    overlay_today=snap_ctx.get("overlay_indication_today"),
                    overlay_sig=snap_ctx.get("overlay_indication"),
                    snap=snap_ctx,
                )
                if dual_call.get("clean") and dual_call.get("accuracy_label"):
                    result["summary"] = dual_call.get("accuracy_label")
                    fa = dict(result.get("fno_analysis") or {})
                    fa["headline"] = dual_call.get("accuracy_label")
                    fa["clean"] = True
                    fa["clean_multi"] = bool(dual_call.get("clean_multi"))
                    fa["clean_morning"] = bool(dual_call.get("clean_morning"))
                    fa["clean_recipe"] = dual_call.get("clean_recipe")
                    result["fno_analysis"] = fa
            except Exception:
                pass
    elif (
        isinstance(conf_readings, dict)
        and fno_live_config.enable_pre_dual_single()
        and (not use_dual or stacked)
        and fno_live_config.is_fno_live_index(key)
    ):
        fno_live_config.stamp_good_readings(conf_readings, decision=live_decision)
    # FINAL accurate books — NIFTY P2F/P2G/CHAMP · BN · SENSEX
    # Confident thrust lanes must also hit CHAMP live fill / Calls board.
    if key == "NIFTY" and (
        use_dual
        or stacked
        or (
            isinstance(dual_call, dict)
            and (dual_call.get("afternoon_thrust") or dual_call.get("morning_strong_thrust"))
        )
    ):
        try:
            import fno_p2f_live

            fno_p2f_live.annotate(
                result,
                symbol=key,
                dual_call=dual_call if isinstance(dual_call, dict) else None,
                readings=conf_readings if isinstance(conf_readings, dict) else None,
            )
        except Exception as exc:
            result["p2f_live_error"] = str(exc)
    elif key == "SENSEX" and (use_dual or stacked):
        try:
            import fno_sensex_final_live

            holder_sx = {"fno_analysis": dict(result.get("fno_analysis") or {})}
            fno_sensex_final_live.annotate(
                holder_sx,
                symbol=key,
                dual_call=dual_call if isinstance(dual_call, dict) else None,
                readings=conf_readings if isinstance(conf_readings, dict) else None,
            )
            result["fno_analysis"] = holder_sx.get("fno_analysis") or result.get("fno_analysis")
            if holder_sx.get("final_sensex_fno"):
                result["final_sensex_fno"] = holder_sx["final_sensex_fno"]
            if isinstance(dual_call, dict) and dual_call.get("stop_loss") is not None:
                live_sl = dual_call.get("stop_loss")
            if isinstance(dual_call, dict) and dual_call.get("target_1") is not None:
                live_t1 = dual_call.get("target_1")
        except Exception as exc:
            result["final_sensex_fno_error"] = str(exc)
    session_ticket = fsrules.persist_new_ticket(
        prev_ticket,
        decision=live_decision,
        stop_loss=live_sl,
        target_1=live_t1,
        taken_at=now_ist.isoformat(),
        session_date_value=now_ist.date(),
        entry=dual_entry if dual_entry is not None else current_price,
        target_2=trade.get("target_2"),
        p_t1=(
            (dual_call.get("p_t1") if isinstance(dual_call, dict) else None)
            or (fno_head or {}).get("p_t1")
        ),
        p_meta=(
            (dual_call.get("p_t1") if isinstance(dual_call, dict) else None)
            or ((fno_head or {}).get("p_meta") or (fno_head or {}).get("p_t1"))
        ),
        regime=((fno_head or {}).get("regime") or {}).get("name")
        or (dual_call or {}).get("regime"),
        readings=conf_readings,
        symbol=key,
        bars=fno_bars,
        live_quote=live_quote,
    )
    # Clear sticky dual once this symbol has an open listed call.
    if fsrules.open_ticket(session_ticket):
        snap.pop("dual_pending_call", None)
        snap.pop("dual_pending_at", None)
    try:
        calls = session_calls.sync_session(
            session_calls.default_db_path(),
            stock=key,
            product="fno",
            session_ticket=session_ticket,
            extra={"source": "fno_refresh"},
        )
    except Exception:
        calls = session_calls.ticket_rows(session_ticket)
    split = session_calls.split_live(calls)
    result["session_ticket"] = session_ticket
    result["session_tickets"] = split["all"]
    result["active_call"] = split["active"]
    result["call_history"] = split["history"]
    try:
        import fno_live_archive

        fno_live_archive.maybe_record(
            stock=key,
            fno_analysis=result.get("fno_analysis") or fno_block,
            price=current_price,
            active_call=split.get("active"),
        )
    except Exception:
        pass
    try:
        import fno_short_horizon_log

        fa_log = result.get("fno_analysis") or fno_block or {}
        fno_short_horizon_log.maybe_record_and_settle(
            stock=key,
            short_horizon=fa_log.get("short_horizon"),
            price=current_price,
            live_context=live_ctx,
            indications=fa_log.get("indications"),
            bars_5m=idf5,
        )
        result["short_horizon_quality"] = fno_short_horizon_log.recent_accuracy(stock=key, limit=120)
    except Exception:
        pass
    fsrules.stamp_call_suggestion(
        result,
        fno_head,
        price=current_price,
        session_ticket=session_ticket,
        symbol=key,
        bars=fno_bars,
        live_quote=live_quote,
        live_context=live_ctx,
        day_range=snap.get("day_range"),
        asof=now_ist,
    )
    import fno_predictions

    fno_predictions.attach(result, key, fno_bars, result.get("suggestion"), asof=now_ist)
    import fno_point_journal

    fno_point_journal.attach(result, key, fno_bars, idf5, fno_head)
    attach_overlay_indication(result, key, fno_bars, float(current_price))
    if fno_live_config.is_fno_live_index(key):
        # Live desk: dual proven/champion + 5m crown + 15m classic; daily_fill via flags.
        try:
            import fno_5m_crown

            fno_5m_crown.attach_to_result(
                result,
                key,
                idf5,
                bars_1m=None,
                price=float(current_price),
                asof=now_ist,
                day_range=snap.get("day_range") or result.get("day_range_forecast"),
            )
        except Exception as exc:
            result["crown_5m_error"] = str(exc)
        try:
            import fno_15m_classic

            fno_15m_classic.attach_to_result(
                result,
                key,
                fno_bars,
                price=float(current_price),
                asof=now_ist,
                fno_head=fno_head,
                day_range=snap.get("day_range") or result.get("day_range_forecast"),
            )
        except Exception as exc:
            result["classic_15m_error"] = str(exc)
        try:
            import fno_daily_fill

            if fno_daily_fill.enabled():
                fno_daily_fill.attach_to_result(
                    result,
                    key,
                    fno_bars,
                    bars_5m=idf5,
                    price=float(current_price),
                    asof=now_ist,
                    day_range=snap.get("day_range") or result.get("day_range_forecast"),
                )
        except Exception as exc:
            result["daily_fill_error"] = str(exc)
        try:
            import fno_move_capture

            if fno_move_capture.enabled():
                fno_move_capture.attach_to_result(
                    result,
                    key,
                    fno_bars,
                    price=float(current_price),
                    asof=now_ist,
                    session_ticket=session_ticket,
                )
        except Exception as exc:
            result["move_capture_error"] = str(exc)
        # 10m CHAMP / 5m crown → Calls board when 15m dual did not list.
        try:
            import fno_dual_modal_list

            session_ticket = fno_dual_modal_list.fill_from_channels(
                result,
                symbol=key,
                session_ticket=session_ticket,
                bars=fno_bars,
                live_quote=live_quote,
                db_path=session_calls.default_db_path(),
                asof=now_ist,
            )
            result["session_ticket"] = session_ticket
            calls = session_calls.ticket_rows(session_ticket)
            split = session_calls.split_live(calls)
            result["session_tickets"] = split["all"]
            result["active_call"] = split["active"]
            result["call_history"] = split["history"]
        except Exception as exc:
            result["dual_modal_list_error"] = str(exc)
    result["alerts"] = fno_block.get("alerts")
    result["alerts_summary"] = fno_block.get("alerts_summary")

    import option_ticket

    option_ticket.attach_for_open_call(
        result,
        key,
        split.get("active"),
        current_price,
        max_loss_inr=option_ticket.resolve_max_loss_inr(
            max_loss_inr, snapshot=snap
        ),
    )
    try:
        session_calls.note_option(
            session_calls.default_db_path(),
            stock=key,
            product="fno",
            session_ticket=session_ticket,
            order=result.get("option_order"),
        )
    except Exception:
        pass
    # Notify after option guide so NEW/BOOK/DROP alerts carry Groww contract links.
    try:
        import desktop_notify

        if isinstance(session_ticket, dict) and isinstance(result.get("option_order"), dict):
            readings = dict(session_ticket.get("readings") or {})
            if not readings.get("option") and result["option_order"].get("tradingsymbol"):
                readings["option"] = result["option_order"]
                session_ticket["readings"] = readings
        desktop_notify.notify_ticket_change(key, ticket_before, session_ticket)
    except Exception:
        pass

    elapsed = round(time.time() - started, 2)
    result["elapsed_sec"] = elapsed
    save_snapshot(
        key,
        {
            **snap,
            "ml_proba": ml_proba,
            "adj_tech": adj_tech,
            "combined_score": float(decision_info.get("combined_score") or 0.5),
            "combined_adjust": combined_adjust,
            "core_decision": decision_info.get("decision"),
            "anchored_decision": result.get("decision"),
            "opening_ticket": result.get("opening_ticket"),
            "anchored_setup_type": fno_block.get("setup_type"),
            "decision_info": decision_info,
            "candlestick": candlestick,
            "india_ctx": india_ctx,
            "atr_val": atr_val,
            "news_delta": news_delta,
            "microstructure": live_ctx.get("microstructure"),
            "micro_ts": time.time(),
            "fno_contracts": contracts,
            "day_range": snap.get("day_range"),
            "structural": snap.get("structural"),
            "indicators": snap.get("indicators"),
            "market_tilt": snap.get("market_tilt"),
            "fno_model": fno_head,
            "session_ticket": session_ticket,
            "last_pcr": deriv.get("pcr"),
            "gex": gex if isinstance(gex, dict) else None,
            "derivatives": deriv,
            "bars_15m": idf15,
            "bars_5m": idf5,
            "bars_ts": time.time(),
            "tape_read": result.get("tape_read"),
            "option_order": result.get("option_order"),
            "suggestion": result.get("suggestion"),
            "pattern_watch": result.get("pattern_watch"),
            "predictions": result.get("predictions"),
            "option_fp": option_fingerprint(
                split.get("active"),
                (result.get("option_order") or {}).get("max_loss_inr"),
            ),
        },
    )
    return result, None
