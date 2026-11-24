"""Point-in-time 15-minute F&O replay (5m is tracked, not the ticket).

No daily 4-model ensemble, no news, no FII fetch.
"""

from __future__ import annotations

import json
import os
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

import analysis_engine
import fno_live_engine
import fno_risk_engine
import fno_session_model
import fno_setup_engine
import product_analysis


def _norm(df: Any) -> Optional[pd.DataFrame]:
    if df is None or len(df) < 8:
        return None
    out = df.copy()
    colmap = {str(c).lower(): c for c in out.columns}
    for src, dst in (("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close"), ("volume", "Volume")):
        if dst not in out.columns and src in colmap:
            out[dst] = out[colmap[src]]
    if "Close" not in out.columns:
        return None
    if "Volume" not in out.columns:
        out["Volume"] = 1.0
    return out.sort_index()


def session_day_range(df: pd.DataFrame, lookback: int = 12) -> Dict[str, Any]:
    """Morning box from the first bars (stand-in for the brief when replaying)."""
    work = _norm(df)
    if work is None:
        return {"expected_low": None, "expected_high": None}
    head = work.iloc[: max(3, min(lookback, len(work)))]
    hi = float(head["High"].astype(float).max())
    lo = float(head["Low"].astype(float).min())
    pad = max((hi - lo) * 0.15, float(head["Close"].astype(float).iloc[-1]) * 0.0015)
    return {
        "expected_high": round(hi + pad, 2),
        "expected_low": round(lo - pad, 2),
        "method": "replay_opening_box",
        "session_bias": "NEUTRAL",
    }


def _forward_outcome(
    future: pd.DataFrame,
    *,
    bearish: bool,
    sl: float,
    t1: float,
) -> str:
    return _forward_result(future, bearish=bearish, sl=sl, t1=t1)["outcome"]


def _forward_result(
    future: pd.DataFrame,
    *,
    bearish: bool,
    sl: float,
    t1: float,
) -> Dict[str, Any]:
    """First barrier plus elapsed bars; same-bar ambiguity is conservative."""
    for bar_n, (_, row) in enumerate(future.iterrows(), 1):
        h = float(row["High"])
        l = float(row["Low"])
        if bearish:
            hit_sl = h >= sl
            hit_t1 = l <= t1
        else:
            hit_sl = l <= sl
            hit_t1 = h >= t1
        if hit_t1 and hit_sl:
            return {"outcome": "same_bar_both", "bars_held": bar_n}
        if hit_t1:
            return {"outcome": "t1_before_sl", "bars_held": bar_n}
        if hit_sl:
            return {"outcome": "sl_before_t1", "bars_held": bar_n}
    return {"outcome": "expired", "bars_held": len(future)}


def live_session_close(
    bars: pd.DataFrame,
    signal_ts,
    side: str,
    entry: float,
    sl: float,
    t1: float,
    bar_minutes: int = 15,
) -> Dict[str, Any]:
    """Close one listed call the way the live desk does.

    Later bars of the same session only, through 15:30. The signal bar itself
    is not a fill. Target first is a win at the target. Stop first, or both
    on the same candle, is a loss (a gap through the stop fills at the open).
    Neither by 15:30 is not a win; points are the 15:30 close versus entry.
    The next session cannot finish today's trade.
    """
    sig = pd.Timestamp(signal_ts)
    if sig.tzinfo is None:
        sig = sig.tz_localize("Asia/Kolkata")
    else:
        sig = sig.tz_convert("Asia/Kolkata")
    end = pd.Timestamp(
        year=sig.year, month=sig.month, day=sig.day, hour=15, minute=30, tz="Asia/Kolkata"
    )
    delta = pd.Timedelta(minutes=int(bar_minutes))
    sign = 1.0 if str(side).upper() == "BUY" else -1.0
    side_u = "BUY" if sign > 0 else "SELL"
    probe = pd.Timestamp(signal_ts)
    if getattr(bars.index, "tz", None) is not None and probe.tzinfo is None:
        probe = probe.tz_localize(bars.index.tz)
    elif getattr(bars.index, "tz", None) is not None and probe.tzinfo is not None:
        probe = probe.tz_convert(bars.index.tz)
    start_i = int(bars.index.searchsorted(probe, side="right"))
    fut_idx = []
    for ts in bars.index[start_i:]:
        t = pd.Timestamp(ts)
        if t.tzinfo is None:
            t = t.tz_localize("Asia/Kolkata")
        else:
            t = t.tz_convert("Asia/Kolkata")
        if t.date() != sig.date():
            break
        if t + delta <= end:
            fut_idx.append(ts)
    outcome = "expired"
    exit_px = None
    for ts in fut_idx:
        row = bars.loc[ts]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[-1]
        h = float(row["High"])
        l = float(row["Low"])
        o = float(row["Open"])
        if side_u == "BUY":
            stop_hit = l <= float(sl)
            target_hit = h >= float(t1)
            stop_px = min(float(sl), o)
        else:
            stop_hit = h >= float(sl)
            target_hit = l <= float(t1)
            stop_px = max(float(sl), o)
        if stop_hit and target_hit:
            outcome, exit_px = "same_bar_both", stop_px
            break
        if stop_hit:
            outcome, exit_px = "sl_before_t1", stop_px
            break
        if target_hit:
            outcome, exit_px = "t1_before_sl", float(t1)
            break
    if outcome == "expired":
        close = None
        for ts in reversed(fut_idx):
            t = pd.Timestamp(ts)
            if t.tzinfo is None:
                t = t.tz_localize("Asia/Kolkata")
            else:
                t = t.tz_convert("Asia/Kolkata")
            if t + delta == end:
                row = bars.loc[ts]
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[-1]
                close = float(row["Close"])
                break
        if close is None and fut_idx:
            row = bars.loc[fut_idx[-1]]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[-1]
            close = float(row["Close"])
        exit_px = close
    if exit_px is None:
        points = 0.0
    elif outcome == "t1_before_sl":
        points = abs(float(t1) - float(entry))
    else:
        points = sign * (float(exit_px) - float(entry))
    plain = {
        "t1_before_sl": "Target hit",
        "sl_before_t1": "Stop hit",
        "same_bar_both": "Same candle — counted as stop",
        "expired": "Closed at 3:30",
    }[outcome]
    return {
        "win": outcome == "t1_before_sl",
        "outcome": outcome,
        "result": plain,
        "points": round(float(points), 1),
        "scoring": "live_session_close",
    }


def _session_slice(work: pd.DataFrame) -> pd.DataFrame:
    """Bars of the as-of session only (not the full history prefix)."""
    try:
        day = pd.Timestamp(work.index[-1]).date()
        session = work[[pd.Timestamp(i).date() == day for i in work.index]]
    except Exception:
        session = work
    return session if session is not None and len(session) else work


def session_live_quote(work: pd.DataFrame, price: Optional[float] = None) -> Dict[str, Any]:
    """Replay stand-in for a Kite session quote: today's open/high/low."""
    session = _session_slice(work)
    last = float(price if price is not None else session["Close"].astype(float).iloc[-1])
    return {
        "last_price": last,
        "open": float(session["Open"].astype(float).iloc[0]),
        "high": float(session["High"].astype(float).max()),
        "low": float(session["Low"].astype(float).min()),
        "source": "replay",
        "feed_type": "replay",
    }


def _close_issued_ticket(
    issued: Dict[str, Any],
    future: pd.DataFrame,
    *,
    symbol: str,
    bar_minutes: int = 15,
) -> str:
    return _close_issued_result(issued, future, symbol=symbol, bar_minutes=bar_minutes)["outcome"]


def _close_issued_result(
    issued: Dict[str, Any],
    future: pd.DataFrame,
    *,
    symbol: str,
    bar_minutes: int = 15,
) -> Dict[str, Any]:
    """Resolve one newly issued ticket with the live NIFTY marker when available."""
    if future is None or len(future) == 0:
        return {"outcome": "expired", "bars_held": 0}
    if str(symbol).upper() != "NIFTY":
        return _forward_result(
            future,
            bearish="SELL" in str(issued.get("decision") or ""),
            sl=float(issued["stop_loss"]),
            t1=float(issued["target_1"]),
        )
    import nifty_fno_runtime

    last_ts = pd.Timestamp(future.index[-1])
    closed = nifty_fno_runtime.mark(
        {
            "session_date": str(pd.Timestamp(issued.get("taken_at") or last_ts).date()),
            "decision": issued["decision"],
            "status": "open",
            "tickets": 1,
            "taken_at": issued.get("taken_at"),
            "entry": issued.get("entry"),
            "stop_loss": issued["stop_loss"],
            "target_1": issued["target_1"],
            "history": [],
        },
        last=float(future["Close"].astype(float).iloc[-1]),
        bars=future,
        asof=last_ts + timedelta(minutes=int(bar_minutes)),
        use_ticks=False,
        bar_minutes=bar_minutes,
    )
    outcome = str(closed.get("status") or "expired")
    bars_held = len(future)
    try:
        taken = pd.Timestamp(issued.get("taken_at"))
        done = pd.Timestamp(closed.get("closed_at") or last_ts)
        bars_held = max(1, int(round((done - taken).total_seconds() / (bar_minutes * 60.0))))
    except Exception:
        bars_held = max(1, len(future))
    return {"outcome": outcome, "bars_held": bars_held}


def score_snapshot(
    bars_asof: pd.DataFrame,
    *,
    symbol: str,
    day_range: Dict[str, Any],
    model_pack: Optional[Dict[str, Any]] = None,
    atr_val: Optional[float] = None,
    primary: bool = True,
    intraday_ready: bool = False,
    asof: Any = None,
    session_ticket: Optional[Dict[str, Any]] = None,
    chain_db: Optional[str] = None,
    news_delta: float = 0.0,
    context: Optional[Dict[str, Any]] = None,
    daily_decision: str = "HOLD",
    indications: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """`news_delta`, `context` and `daily_decision` let a replay feed the same
    daily-stack read the live desk passes to `fno_model.infer`."""
    work = _norm(bars_asof)
    if work is None:
        return {"decision": "HOLD", "skip": True}
    price = float(work["Close"].astype(float).iloc[-1])
    bar_start = pd.Timestamp(work.index[-1])
    decision_asof = pd.Timestamp(asof if asof is not None else bar_start)
    # Historical candle timestamps are starts; a decision using its Close is
    # available only at the end of that candle.
    if decision_asof <= bar_start:
        decision_asof = bar_start + timedelta(minutes=15)
    high = work["High"].astype(float)
    low = work["Low"].astype(float)
    atr = float(atr_val or max((high.tail(14) - low.tail(14)).mean(), price * 0.004))
    live_quote = session_live_quote(work, price)
    live_quote["received_at_ist"] = str(decision_asof)
    live_quote["exchange_timestamp"] = str(decision_asof)
    live_ctx = fno_live_engine.build_fno_live_context(
        live_quote,
        None,
        work,
        0.5,
        50.0,
        0.5,
        "HOLD",
        force_in_session=True,
    )
    import fno_session_rules as fsrules

    live0 = fsrules.open_ticket(session_ticket)
    hi, lo = price, price
    if live0:
        hi, lo = fsrules.path_extremes(work, live0.get("taken_at"), price)
    ticket = fsrules.mark_ticket_from_tape(
        session_ticket,
        last=price,
        session_high=hi,
        session_low=lo,
        bars=work,
        symbol=symbol,
        asof=decision_asof,
        use_ticks=False,
    )
    orb = ((live_ctx.get("microstructure") or {}).get("opening_range") or {})
    try:
        import fno_model as fno_md

        is_fno_pack = (model_pack or {}).get("model_version") == fno_md.MODEL_VERSION
        session_pack = None if is_fno_pack else model_pack
        fno_pack = model_pack if is_fno_pack else None
        live_ctx["session_model"] = fno_session_model.infer(
            work, session_pack, interval="15minute"
        )
        derivatives = None
        if chain_db:
            try:
                import chain_flow

                derivatives = chain_flow.readings_asof(
                    symbol,
                    decision_asof,
                    db_path=chain_db,
                ) or None
            except Exception:
                derivatives = None
        ctx = dict(context or {})
        ctx.setdefault("session_bias", (live_ctx.get("session") or {}).get("session_bias"))
        fno_head = fno_md.infer(
            work,
            fno_pack,
            derivatives=derivatives,
            news_delta=float(news_delta or 0.0),
            five_min_conflict=bool((live_ctx.get("microstructure") or {}).get("five_min_conflict")),
            daily_decision=daily_decision,
            force_side=fsrules.infer_side_override(
                ticket, orb, price, asof=decision_asof
            ),
            first_clip=fsrules.is_first_clip(ticket),
            symbol=symbol,
            context=ctx,
            asof=decision_asof,
        )
    except Exception:
        live_ctx["session_model"] = fno_session_model.infer(work, None, interval="15minute")
        fno_head = {"available": False, "decision": "HOLD", "p_up": 0.5}
    live_ctx["fno_model"] = fno_head
    candle = analysis_engine.detect_candlestick_window(work.tail(5))
    base = {
        "decision": "HOLD",
        "confidence": 50,
        "combined_score": 0.5,
        "signal_quality": "HIGH" if primary else "MEDIUM",
        "agreement_score": 70,
        "signals_agree": True,
        "risk_management": {},
    }
    block = product_analysis.build_fno_analysis(
        symbol,
        base,
        0.5,
        50.0,
        0.0,
        candle,
        None,
        price,
        atr,
        live_context=live_ctx,
        live_quote=live_quote,
        day_range=day_range,
        same_session_only=True,
        intraday_ready=intraday_ready if not product_analysis.is_fno_primary(symbol) else None,
        intraday_decision="BUY" if intraday_ready else "HOLD",
        asof=decision_asof,
        session_ticket=ticket,
        fno_model=fno_head,
        indications=indications,
    )
    trade = (block.get("risk") or {}).get("fno_trade") or {}
    count_before = int((ticket or {}).get("tickets") or 0)
    open_before = fsrules.open_ticket(ticket)
    ticket = fsrules.persist_new_ticket(
        ticket,
        decision=str(block.get("decision") or "HOLD"),
        stop_loss=trade.get("stop_loss"),
        target_1=trade.get("target_1"),
        taken_at=decision_asof,
        session_date_value=fsrules.session_date(decision_asof),
        entry=price,
        target_2=trade.get("target_2"),
        p_t1=(fno_head or {}).get("p_t1"),
        p_meta=(fno_head or {}).get("p_meta") or (fno_head or {}).get("p_t1"),
        regime=((fno_head or {}).get("regime") or {}).get("name"),
        symbol=symbol,
        bars=work,
        live_quote=live_quote,
    )
    active = fsrules.open_ticket(ticket)
    issued = active if (open_before is None and active is not None and int((ticket or {}).get("tickets") or 0) > count_before) else None
    return {
        "decision": block.get("decision"),
        "confidence": block.get("confidence"),
        "setup_type": block.get("setup_type"),
        "active_horizon": block.get("active_horizon"),
        "price": round(price, 2),
        "stop_loss": trade.get("stop_loss"),
        "target_1": trade.get("target_1"),
        "target_2": trade.get("target_2"),
        "levels_fit": trade.get("levels_fit"),
        "day_range": day_range,
        "fno_eligible": block.get("fno_eligible"),
        "fno_p_up": (fno_head or {}).get("p_up"),
        "fno_model_decision": (fno_head or {}).get("decision"),
        "fno_head": fno_head,
        "reasons": list(block.get("reasons") or []),
        "session_ticket": ticket,
        "new_ticket": issued is not None,
        "issued_ticket": dict(issued) if issued else None,
        "decision_asof": str(decision_asof),
        "skip": False,
    }


def replay_index_session(
    df_bars: Any,
    *,
    symbol: str = "NIFTY",
    step_minutes: int = 15,
    bar_minutes: int = 15,
    day_range: Optional[Dict[str, Any]] = None,
    model_pack: Optional[Dict[str, Any]] = None,
    train_on_prefix: bool = True,
    max_seconds: float = 55.0,
    forward_bars: int = 4,
    same_day_only: bool = True,
    chain_db: Optional[str] = None,
) -> Dict[str, Any]:
    """Walk a session on 15m bars (default) and score T1-before-SL."""
    started = time.perf_counter()
    work = _norm(df_bars)
    if work is None:
        return {"ok": False, "error": "need 15m bars", "elapsed_sec": 0.0}

    pack = model_pack
    if pack is None and train_on_prefix and len(work) >= 80:
        cut = max(40, int(len(work) * 0.45))
        pack = fno_session_model.train_session_head(work.iloc[:cut], interval="15minute")

    box = day_range or session_day_range(work, lookback=2 if bar_minutes >= 15 else 12)
    step = max(1, int(round(step_minutes / max(bar_minutes, 1))))
    snapshots: List[Dict[str, Any]] = []
    actionable = 0
    t1_wins = 0
    sl_hits = 0

    warmup = 18 if bar_minutes <= 5 else 4
    session_ticket = None
    for i in range(warmup, len(work) - 1, step):
        if time.perf_counter() - started > max_seconds:
            break
        asof = work.iloc[: i + 1]
        snap = score_snapshot(
            asof,
            symbol=symbol,
            day_range=box,
            model_pack=pack,
            primary=product_analysis.is_fno_primary(symbol),
            asof=asof.index[-1],
            session_ticket=session_ticket,
            chain_db=chain_db,
        )
        if snap.get("session_ticket"):
            session_ticket = snap["session_ticket"]
        if snap.get("skip"):
            continue
        rest = work.iloc[i + 1 :]
        if same_day_only:
            try:
                day = pd.Timestamp(asof.index[-1]).date()
                rest = rest[[pd.Timestamp(ix).date() == day for ix in rest.index]]
            except Exception:
                pass
        future = rest if str(symbol).upper() == "NIFTY" else rest.iloc[:forward_bars]
        outcome = "hold"
        issued = snap.get("issued_ticket") or {}
        if issued:
            actionable += 1
            outcome = _close_issued_ticket(issued, future, symbol=symbol, bar_minutes=bar_minutes)
            if outcome == "t1_before_sl":
                t1_wins += 1
            elif outcome == "sl_before_t1":
                sl_hits += 1
        sl, t1 = snap.get("stop_loss"), snap.get("target_1")
        lo, hi = box.get("expected_low"), box.get("expected_high")
        if snap.get("decision") not in (None, "HOLD") and sl is not None and t1 is not None and lo is not None and hi is not None:
            for lvl in (sl, t1):
                if not (float(lo) - 0.02 <= float(lvl) <= float(hi) + 0.02):
                    snap["range_violation"] = True
        snap["asof"] = str(asof.index[-1])
        snap["outcome"] = outcome
        snapshots.append(snap)

    elapsed = time.perf_counter() - started
    return {
        "ok": True,
        "symbol": symbol.upper(),
        "bar_minutes": bar_minutes,
        "decision_interval": "15minute" if bar_minutes >= 15 else "5minute",
        "step_minutes": step_minutes,
        "elapsed_sec": round(elapsed, 3),
        "under_one_minute": elapsed < 60.0,
        "n_snapshots": len(snapshots),
        "n_actionable": actionable,
        "t1_before_sl": t1_wins,
        "sl_before_t1": sl_hits,
        "t1_hit_rate": round(t1_wins / actionable, 4) if actionable else None,
        "day_range": box,
        "model_used": bool(pack and pack.get("available")),
        "snapshots": snapshots,
    }


def replay_multi_day(
    df_15m: Any,
    *,
    symbol: str = "NIFTY",
    model_pack: Optional[Dict[str, Any]] = None,
    train_on_prefix: bool = True,
    max_seconds: float = 170.0,
    forward_bars: Optional[int] = None,
    chain_db: Optional[str] = None,
) -> Dict[str, Any]:
    """Replay every cash session on a 15m series. Score T1/SL until 15:15."""
    started = time.perf_counter()
    work = _norm(df_15m)
    if work is None or len(work) < 20:
        return {"ok": False, "error": "need 15m history", "elapsed_sec": 0.0}

    pack = model_pack
    if pack is None and train_on_prefix and len(work) >= 80:
        cut = max(60, int(len(work) * 0.40))
        pack = fno_session_model.train_session_head(work.iloc[:cut], interval="15minute")

    days = pd.Series([pd.Timestamp(i).date() for i in work.index], index=work.index)
    unique_days = sorted(set(days.tolist()))
    snapshots: List[Dict[str, Any]] = []
    actionable = t1_wins = sl_hits = both = expired = 0
    n_days = 0

    for day in unique_days:
        if time.perf_counter() - started > max_seconds:
            break
        day_mask = days == day
        day_idx = [i for i, flag in enumerate(day_mask.tolist()) if flag]
        if len(day_idx) < 6:
            continue
        n_days += 1
        day_frame = work.iloc[day_idx]
        box = session_day_range(day_frame, lookback=2)
        day_ticket: Optional[Dict[str, Any]] = None
        for pos, i in enumerate(day_idx):
            if pos < 2 or pos >= len(day_idx) - 1:
                continue
            if time.perf_counter() - started > max_seconds:
                break
            asof = work.iloc[: i + 1]
            snap = score_snapshot(
                asof,
                symbol=symbol,
                day_range=box,
                model_pack=pack,
                primary=product_analysis.is_fno_primary(symbol),
                asof=asof.index[-1],
                session_ticket=day_ticket,
                chain_db=chain_db,
            )
            if snap.get("skip"):
                continue
            if snap.get("session_ticket"):
                day_ticket = snap["session_ticket"]
            rest = work.iloc[day_idx[pos + 1] : day_idx[-1] + 1]
            future = rest if (forward_bars is None or str(symbol).upper() == "NIFTY") else rest.head(forward_bars)
            outcome = "hold"
            issued = snap.get("issued_ticket") or {}
            if issued:
                actionable += 1
                outcome = _close_issued_ticket(issued, future, symbol=symbol)
                if outcome == "t1_before_sl":
                    t1_wins += 1
                elif outcome == "sl_before_t1":
                    sl_hits += 1
                elif outcome == "same_bar_both":
                    both += 1
                elif outcome == "expired":
                    expired += 1
            snap["asof"] = str(asof.index[-1])
            snap["session_day"] = str(day)
            snap["outcome"] = outcome
            snapshots.append(snap)

    elapsed = time.perf_counter() - started
    return {
        "ok": True,
        "symbol": symbol.upper(),
        "decision_interval": "15minute",
        "elapsed_sec": round(elapsed, 3),
        "n_days": n_days,
        "n_snapshots": len(snapshots),
        "n_actionable": actionable,
        "t1_before_sl": t1_wins,
        "sl_before_t1": sl_hits,
        "same_bar_both": both,
        "expired": expired,
        "t1_hit_rate": round(t1_wins / actionable, 4) if actionable else None,
        "resolved": t1_wins + sl_hits,
        "resolved_t1_rate": round(t1_wins / (t1_wins + sl_hits), 4) if (t1_wins + sl_hits) else None,
        "tickets_per_day": round(actionable / n_days, 2) if n_days else None,
        "option_miss": expired,
        "scored_to": "session_close",
        "model_used": bool(pack and pack.get("available")),
        "model_in_sample": (pack or {}).get("accuracy_in_sample"),
        "snapshots": snapshots,
    }


def cache_dir(base: Optional[str] = None) -> str:
    root = base or os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_signal_data", "fno_validate")
    os.makedirs(root, exist_ok=True)
    return root


def load_cached_15m(symbol: str, dest: Optional[str] = None) -> Optional[pd.DataFrame]:
    path = os.path.join(dest or cache_dir(), f"{symbol.upper()}_15m.csv")
    if not os.path.isfile(path):
        return None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return _norm(df)


def fetch_index_15m(symbol: str, days: int = 90) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    import kite_data

    df, err = kite_data.fetch_historical_candles(symbol, "15minute", days=days)
    return df, err


def save_bars(df: pd.DataFrame, symbol: str, dest: str) -> str:
    path = os.path.join(dest, f"{symbol.upper()}_15m.csv")
    out = _norm(df)
    if out is None:
        raise ValueError("empty bars")
    out.to_csv(path)
    return path


def validate_kite_indices(
    days: int = 90,
    symbols: Optional[List[str]] = None,
    max_seconds_each: float = 85.0,
) -> Dict[str, Any]:
    """Pull Kite 15m for NIFTY/BANKNIFTY and replay F&O same-day logic."""
    dest = cache_dir()
    symbols = symbols or ["NIFTY", "BANKNIFTY"]
    started = time.perf_counter()
    reports: List[Dict[str, Any]] = []
    fetch_errors: Dict[str, str] = {}
    for sym in symbols:
        df = load_cached_15m(sym, dest)
        err = None
        if df is None:
            df, err = fetch_index_15m(sym, days=days)
        if df is None or err:
            fetch_errors[sym] = err or "no data"
            continue
        csv_path = save_bars(df, sym, dest)
        rep = replay_multi_day(df, symbol=sym, max_seconds=max_seconds_each)
        slim = {k: v for k, v in rep.items() if k != "snapshots"}
        slim["csv_path"] = csv_path
        slim["n_bars"] = int(len(df))
        slim["from"] = str(df.index.min())
        slim["to"] = str(df.index.max())
        reports.append(slim)

    payload = {
        "job": "fno_15m_kite_validate",
        "days_requested": days,
        "elapsed_sec": round(time.perf_counter() - started, 3),
        "fetch_errors": fetch_errors,
        "reports": reports,
        "note": (
            "T1-before-SL is the quality bar, not badge confidence. "
            "This is a research replay, not live trading advice."
        ),
    }
    out_json = os.path.join(dest, "latest_validate.json")
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    payload["report_path"] = out_json
    return payload


if __name__ == "__main__":
    print(json.dumps(validate_kite_indices(), indent=2, default=str))
