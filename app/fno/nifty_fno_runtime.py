"""NIFTY ticket lifecycle shared by Analyze, refresh and historical replay."""
from __future__ import annotations

from collections import deque
from datetime import timedelta
from threading import Lock

import pandas as pd

from nifty_fno_data import normalize, timestamp

_ticks = deque(maxlen=100000)
_tick_lock = Lock()


def record_tick(price, at):
    if price is None:
        return
    with _tick_lock:
        _ticks.append((timestamp(at), float(price)))


def mark(ticket, *, last, bars=None, asof=None, use_ticks=True, bar_minutes=15):
    import fno_session_rules as rules

    live = rules.open_ticket(ticket)
    if not live:
        return ticket
    now = timestamp(asof)
    taken = timestamp(live["taken_at"])
    end = taken.normalize() + timedelta(hours=15, minutes=30)
    deadline = min(now, end)
    sl, target = float(live["stop_loss"]), float(live["target_1"])
    side = -1 if "SELL" in live["decision"] else 1
    events = []
    tape = normalize(bars)
    # A bar beginning exactly at entry is wholly post-entry. A partly pre-entry
    # candle cannot establish barrier order; streaming prices cover that portion.
    # A runner starts after the first target is locked, so the bar that reached
    # that target is not re-read as a stop.
    bar_delta = timedelta(minutes=int(bar_minutes))
    path_from = taken
    if live.get("runner") and live.get("runner_since"):
        path_from = timestamp(live["runner_since"])
    path = tape.loc[(tape.index >= path_from) & (tape.index + bar_delta <= deadline)]
    for ts, row in path.iterrows():
        stop_hit = row.High >= sl if side < 0 else row.Low <= sl
        target_hit = row.Low <= target if side < 0 else row.High >= target
        when = ts + bar_delta
        if stop_hit or target_hit:
            status = "same_bar_both" if stop_hit and target_hit else "sl_before_t1" if stop_hit else "t1_before_sl"
            # Gap through a stop is filled at the worse bar open. Targets are
            # conservatively credited at the requested level.
            price = (max(sl, row.Open) if side < 0 else min(sl, row.Open)) if stop_hit else target
            events.append((when, status, float(price), "bar"))
    if use_ticks:
        with _tick_lock:
            ticks = list(_ticks)
        for ts, price in ticks:
            if not taken < ts <= deadline:
                continue
            if side * (price - sl) <= 0:
                events.append((ts, "sl_before_t1", price, "tick"))
            elif side * (price - target) >= 0:
                events.append((ts, "t1_before_sl", target, "tick"))
    # A next-session print must never resolve yesterday's trade.
    if taken.date() == now.date() and now <= end:
        if side * (float(last) - sl) <= 0:
            events.append((now, "sl_before_t1", float(last), "quote"))
        elif side * (float(last) - target) >= 0:
            events.append((now, "t1_before_sl", target, "quote"))
    if not rules.levels_on_side(live["decision"], live.get("entry"), sl, target):
        event = (now, "expired", None, "invalid_levels")
    elif events:
        # Coarse bar events describe an interval. Keep the conservative bar result
        # if it may precede a later tick; never claim exact sequencing from OHLC.
        events.sort(key=lambda event: event[0] - (bar_delta if event[3] == "bar" else timedelta(0)))
        event = events[0]
    elif now >= end:
        session = tape.loc[(tape.index.date == taken.date()) & (tape.index >= taken)
                           & (tape.index + bar_delta <= end)]
        close = float(session.Close.iloc[-1]) if len(session) and session.index[-1] + bar_delta == end else None
        event = (end, "expired", close, "session_close" if close is not None else "missing_session_close")
    else:
        return ticket
    at, status, price, source = event
    history = list(ticket.get("history") or [])
    history.append({**{k: v for k, v in live.items() if k not in ("history", "tickets")},
                    "status": status, "closed_at": at.isoformat(), "exit_price": price,
                    "exit_source": source, "points": None if price is None else round(side * (price - float(live["entry"])), 2)})
    return {**ticket, "history": history, "status": status, "closed_at": at.isoformat(),
            "decision": "HOLD", "entry": None, "stop_loss": None, "target_1": None, "target_2": None}


def align_block(block, ticket):
    """An open call retains its issued direction and levels in every API view."""
    import fno_session_rules as rules

    live = rules.open_ticket(ticket)
    if not live:
        return block
    result = dict(block)
    result["candidate_decision"] = block.get("decision")
    result["decision"] = result["anchored_decision"] = live["decision"]
    result["risk"] = dict(block.get("risk") or {})
    trade = dict(result["risk"].get("fno_trade") or {})
    for key in ("entry", "stop_loss", "target_1", "target_2"):
        trade[key] = live.get(key)
    risk = abs(float(live["entry"]) - float(live["stop_loss"]))
    trade.update(sl_points=risk, t1_points=abs(float(live["target_1"]) - float(live["entry"])),
                 t2_points=None if live.get("target_2") is None else abs(float(live["target_2"]) - float(live["entry"])),
                 levels_source="issued_ticket",
                 runner_policy=(
                     "First target is locked. This ticket now targets the runner."
                     if live.get("runner")
                     else "T2 is informational; this ticket closes at T1."
                 ))
    result["risk"]["fno_trade"] = trade
    result["headline"] = f"{live['decision']} call #{live.get('tickets', 1)} — stop {live['stop_loss']}, first target {live['target_1']}."
    return result


def prepare_block(block, ticket, *, bars, quote, asof=None):
    """Anchor an active call and reject a new call when its inputs are stale."""
    from nifty_fno_data import entry_issue
    import fno_session_rules as rules

    result = align_block(block, ticket)
    issue = entry_issue(bars, quote, asof)
    result["data_issue"] = issue
    if issue and not rules.open_ticket(ticket):
        result.update(decision="HOLD", headline=issue, risk={"fno_trade": {}}, anchored_decision="HOLD")
    return result


def finalize_result(result, *, bars, quote, asof=None):
    """Apply the same data guard after every override, before ticket creation."""
    import fno_risk_engine

    ticket = result.get("session_ticket")
    block = prepare_block(result.get("fno_analysis") or {}, ticket, bars=bars, quote=quote, asof=asof)
    result["fno_analysis"] = block
    result["decision"] = block.get("decision", "HOLD")
    result["summary"] = block.get("headline")
    result["risk_management"] = fno_risk_engine.fno_risk_for_api(block.get("risk") or {})
    return result
