"""Background ingest, EOD scoring, daily F&O train, and desktop alerts for new calls."""

from __future__ import annotations

import os
import threading
import time
from datetime import date, datetime, time as dt_time
from typing import Any, Callable, Dict, List, Optional

import knowledge_db
import training_store

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

IST = ZoneInfo("Asia/Kolkata") if ZoneInfo else None

_lock = threading.Lock()
_state: Dict[str, Any] = {
    "running": False,
    "last_beat": None,
    "last_error": None,
    "last_train": None,
    "last_notify": None,
}
_last_decisions: Dict[str, str] = {}
_thread: Optional[threading.Thread] = None
_stop = threading.Event()


def _now_ist() -> datetime:
    if IST:
        return datetime.now(IST)
    return datetime.now()


def _in_session() -> bool:
    now = _now_ist()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return dt_time(9, 10) <= t <= dt_time(15, 35)


def _after_close_train_window() -> bool:
    now = _now_ist()
    if now.weekday() >= 5:
        return False
    return now.time() >= dt_time(15, 45)


def agent_state() -> Dict[str, Any]:
    with _lock:
        return dict(_state)


def _tick_ingest(symbols: List[str], db_path: str) -> None:
    import bar_ingest

    out = bar_ingest.ingest_symbols(symbols, days=12)
    training_store.heartbeat(db_path, "ingest", out)
    for sym in symbols:
        day = _now_ist().date().isoformat()
        act = training_store.resolve_session_ohlc(sym, day)
        if act:
            training_store.upsert_bar_session(db_path, stock=sym, session_date=day, interval="15minute", ohlc=act, source="live")


def _tick_chain(symbols: List[str], db_path: str) -> None:
    """Save the option chain even when the full F&O analysis fails or is still running."""
    import chain_flow

    for sym in symbols:
        try:
            chain_flow.capture_live(sym, db_path=db_path)
        except Exception as exc:
            training_store.heartbeat(db_path, "chain_error", {"symbol": sym, "error": str(exc)})


def _tick_fno_poll(
    predict_fn: Callable[..., Dict[str, Any]],
    symbols: List[str],
    db_path: str,
) -> None:
    import desktop_notify

    for sym in symbols:
        try:
            result = predict_fn(sym, product="fno", mode="live")
        except Exception as exc:
            training_store.heartbeat(db_path, "predict_error", {"symbol": sym, "error": str(exc)})
            continue
        decision = str(result.get("decision") or "HOLD").upper()
        prev = _last_decisions.get(sym)
        _last_decisions[sym] = decision
        rm = result.get("risk_management") or {}
        trade = rm.get("fno_trade") or rm
        sl = trade.get("stop_loss")
        t1 = trade.get("target_1")
        if decision in ("BUY", "SELL", "STRONG BUY", "STRONG SELL") and decision != prev:
            ticket = result.get("session_ticket") or {}
            n = ticket.get("tickets") or 1
            day = str(ticket.get("session_date") or _now_ist().date().isoformat())
            key = f"{sym}:{day}:{n}:{decision}"
            if training_store.should_notify(db_path, key):
                option_line = ((result.get("option_order") or {}).get("order_line"))
                if desktop_notify.notify_call(sym, decision, stop=sl, target=t1, option_line=option_line):
                    training_store.mark_notified(db_path, key, stock=sym, decision=decision, payload={"sl": sl, "t1": t1})
                    with _lock:
                        _state["last_notify"] = {"symbol": sym, "decision": decision, "at": datetime.now().isoformat()}
        import session_calls

        session_calls.sync_session(
            db_path,
            stock=sym,
            product="fno",
            session_ticket=result.get("session_ticket"),
            extra={"source": "background_agent"},
        )


def _tick_eod(db_path: str, train_symbols: List[str]) -> None:
    today = _now_ist().date()
    days = [(today - __import__("datetime").timedelta(days=i)).isoformat() for i in (1, 0)]
    training_store.score_morning_briefs(db_path, session_dates=days)
    import daily_fno_train

    rep = daily_fno_train.run_daily_train(train_symbols, refresh_kite_days=20, db_path=db_path)
    with _lock:
        _state["last_train"] = rep
    training_store.heartbeat(db_path, "daily_train", rep)


def _loop(
    predict_fn: Callable[..., Dict[str, Any]],
    fno_symbols: List[str],
    ingest_symbols: List[str],
    db_path: str,
    poll_sec: float,
) -> None:
    global _state
    last_train_day: Optional[str] = None
    with _lock:
        _state["running"] = True
    while not _stop.is_set():
        try:
            db_path = training_store.ensure_tables(db_path)
            if _in_session():
                _tick_ingest(ingest_symbols, db_path)
                _tick_chain(fno_symbols, db_path)
                _tick_fno_poll(predict_fn, fno_symbols, db_path)
            day = _now_ist().date().isoformat()
            if _after_close_train_window() and last_train_day != day:
                _tick_eod(db_path, fno_symbols)
                last_train_day = day
            training_store.heartbeat(db_path, "idle" if not _in_session() else "session", {"poll_sec": poll_sec})
            with _lock:
                _state["last_beat"] = datetime.now().isoformat()
                _state["last_error"] = None
        except Exception as exc:
            with _lock:
                _state["last_error"] = str(exc)
            training_store.heartbeat(db_path, "error", {"error": str(exc)})
        _stop.wait(poll_sec)
    with _lock:
        _state["running"] = False


def start_background_agent(
    predict_fn: Callable[..., Dict[str, Any]],
    *,
    fno_symbols: Optional[List[str]] = None,
    ingest_symbols: Optional[List[str]] = None,
    poll_sec: float = 90.0,
    db_path: Optional[str] = None,
) -> bool:
    """Start daemon thread (no-op if DISABLE_BACKGROUND_AGENT=1)."""
    global _thread
    if os.environ.get("DISABLE_BACKGROUND_AGENT", "").strip() in ("1", "true", "yes"):
        return False
    if _thread and _thread.is_alive():
        return False
    path = knowledge_db.ensure_db_dir() if db_path is None else db_path
    training_store.ensure_tables(path)
    import fno_universe

    fno = fno_symbols or fno_universe.symbols()
    ingest = ingest_symbols or list(fno)
    _stop.clear()
    _thread = threading.Thread(
        target=_loop,
        args=(predict_fn, fno, ingest, path, poll_sec),
        name="background_agent",
        daemon=True,
    )
    _thread.start()
    return True


def stop_background_agent() -> None:
    _stop.set()
