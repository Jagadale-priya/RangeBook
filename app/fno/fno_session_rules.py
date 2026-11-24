"""Same-session F&O quality rules: clock, tickets, OR break, room to T1."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

ENTRY_START = time(9, 15)
# First hour: opening-range calls are allowed even when the daily stack disagrees.
OPENING_CALL_END = time(10, 15)
ENTRY_CUTOFF = time(11, 30)
# New calls, including the first break of the day, print through the cash close.
SESSION_END = time(15, 30)
REENTRY_CUTOFF = SESSION_END
MIN_T1_REMAINING_FRAC = 0.25
MIN_OR_FRAC = 0.0025
MAX_OR_FRAC = 0.008
MIN_REWARD_RISK = 1.0
# A second clip the same way must clear the full model bar. The trend discount
# (down to 0.54) is only for the first break. 23 Sep Nifty bought again at 0.545 after
# the first target and that add-on hit the stop.
SAME_SIDE_REENTRY_P = 0.58
# Suggestions (independent of listed model calls): engulf or EMA9 pullback,
# then VWAP + strong body + clean wick, sized at 0.75×ATR. Prefer 5m bars.
# Close must sit this far past the OR edge (as a fraction of OR width) or the break is a poke.
# Prod entry policy (measured): listed calls stay at model floor 52% with this
# shallow OR poke hard-block. Do not lower 52% or remove shallow without a new
# multi-month replay that beats year shallow (~+3015 / ~70%+).
MIN_BREAK_EXT = 0.08
# Year walk (2025-10-27→2026-10-23, 246 sessions): max 2 listed calls/day after the
# first resolves (T1 / SL / early_drop / cancel) = 126 calls @ 69.0% vs 98 @ 69.4%
# one-and-done; +664 pts with early-drop. Cap is hard — no 3rd listed ticket.
MAX_LISTED_TICKETS_PER_DAY = 2
# NIFTY FINAL books (CHAMP Cap6 + morning) — do not clip accurate fires at 2.
MAX_LISTED_TICKETS_NIFTY = 6
# After a dead ticket, wait this long before the opposite call (kills 1-bar flip-flops).
RECLAIM_COOLDOWN_MIN = 30
# Bounce back into the range after a paid T1 (today's 11:00 BUY).
T1_RECLAIM_FRAC = 0.08
IST = ZoneInfo("Asia/Kolkata") if ZoneInfo else None


def as_ist(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        dt = ts
    else:
        try:
            dt = pd_timestamp(ts)
        except Exception:
            return None
    if dt.tzinfo is None and IST:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST) if IST else dt


def pd_timestamp(ts: Any) -> datetime:
    import pandas as pd

    return pd.Timestamp(ts).to_pydatetime()


def session_date(ts: Any) -> Optional[date]:
    dt = as_ist(ts)
    return dt.date() if dt else None


CLOSED_STATUSES = (
    "t1_before_sl",
    "sl_before_t1",
    "same_bar_both",
    "expired",
    "expired_unobserved",
    "cancelled",
    "early_drop",
    "superseded_by_model",
)


def _history_row_is_live_clip(row: Optional[Dict[str, Any]]) -> bool:
    """True for live-confluence history rows (and model-superseded live)."""
    if not isinstance(row, dict):
        return False
    if str(row.get("status") or "") == "superseded_by_model":
        return True
    readings = row.get("readings") if isinstance(row.get("readings"), dict) else {}
    if row.get("live_confluence") or readings.get("live_confluence"):
        return True
    if readings.get("history_eligible") is False:
        return True
    track = str(
        readings.get("track")
        or row.get("track")
        or readings.get("source")
        or row.get("source")
        or row.get("regime")
        or ""
    )
    return track == "live_confluence"


def closed_ticket_count(session_ticket: Optional[Dict[str, Any]]) -> int:
    """Closed tickets that consume the model daily listed-call cap.

    Live-confluence clips (and live closed as superseded_by_model) do not burn
    a model slot — otherwise replacing 12:23 live with 12:28 model would
    unfairly count against MAX_LISTED.
    """
    if not session_ticket:
        return 0
    hist = session_ticket.get("history") or []
    closed = sum(
        1
        for h in hist
        if str(h.get("status") or "") in CLOSED_STATUSES
        and not _history_row_is_live_clip(h)
    )
    if closed:
        return closed
    if str(session_ticket.get("status") or "") in CLOSED_STATUSES:
        if _history_row_is_live_clip(session_ticket) or is_live_confluence_ticket(session_ticket):
            return 0
        return max(1, int(session_ticket.get("tickets") or 1))
    return 0


def first_frame(*candidates: Any) -> Any:
    """Return the first non-None candle frame.

    Never use ``a or b`` with pandas objects — DataFrame/Series truthiness raises
    ``ValueError: The truth value of a DataFrame is ambiguous``.
    """
    for cand in candidates:
        if cand is not None:
            return cand
    return None


def bars_after_fill(bars: Any, taken_at: Any) -> Any:
    """Bars strictly after the fill time with High/Low columns, or None."""
    if bars is None or taken_at in (None, ""):
        return None
    try:
        import pandas as pd

        work = bars
        if not isinstance(work, pd.DataFrame) or len(work) == 0:
            return None
        taken = pd.Timestamp(taken_at)
        idx = pd.DatetimeIndex(work.index)
        if taken.tzinfo is not None and idx.tz is None:
            taken = taken.tz_localize(None)
        elif taken.tzinfo is None and idx.tz is not None:
            taken = taken.tz_localize(idx.tz)
        after = work.loc[(idx >= taken) & (idx.date == taken.date())]
        if len(after) == 0:
            return None
        colmap = {str(c).lower(): c for c in after.columns}
        hcol = colmap.get("high")
        lcol = colmap.get("low")
        if hcol is None or lcol is None:
            return None
        out = pd.DataFrame(
            {"High": after[hcol].astype(float), "Low": after[lcol].astype(float)},
            index=after.index,
        )
        return out
    except Exception:
        return None


def path_extremes(
    bars: Any,
    taken_at: Any,
    last: float,
) -> Tuple[float, float]:
    """High/low after the fill bar — the entry candle's wick is not yet in the trade."""
    px = float(last)
    after = bars_after_fill(bars, taken_at)
    if after is None:
        return px, px
    try:
        hi = max(float(after["High"].max()), px)
        lo = min(float(after["Low"].min()), px)
    except Exception:
        return px, px
    return hi, lo


def path_status(
    bars: Any,
    taken_at: Any,
    last: float,
    *,
    bearish: bool,
    stop_loss: float,
    target_1: float,
) -> Optional[str]:
    """Walk the bars after the fill in order, then the live print. Returns
    't1_before_sl' / 'sl_before_t1' / 'same_bar_both', or None if neither printed.
    Order matters: a target that printed before a later stop is a win, not a
    'same bar' loss that extremes-only marking would report."""
    import triple_barrier

    after = bars_after_fill(bars, taken_at)
    if after is not None:
        outcome = triple_barrier.path_outcome(
            after, bearish=bearish, stop=float(stop_loss), target=float(target_1)
        )
        if outcome in ("t1_before_sl", "sl_before_t1", "same_bar_both"):
            return outcome
    px = float(last)
    if bearish:
        hit_sl = px >= float(stop_loss)
        hit_t1 = px <= float(target_1)
    else:
        hit_sl = px <= float(stop_loss)
        hit_t1 = px >= float(target_1)
    if hit_sl and hit_t1:
        return "same_bar_both"
    if hit_t1:
        return "t1_before_sl"
    if hit_sl:
        return "sl_before_t1"
    return None


def cancel_open_ticket(session_ticket: Optional[Dict[str, Any]], closed_at: Any = None) -> Optional[Dict[str, Any]]:
    """Close the open call by hand so the next passed bar can open a new one.

    The cancelled call stays in today's history. It is not a stop and not a target.
    """
    return _close_open_ticket(session_ticket, status="cancelled", closed_at=closed_at)


def is_live_confluence_ticket(session_ticket: Optional[Dict[str, Any]]) -> bool:
    """True when the open (or just-listed) ticket came from live confluence, not model."""
    if not isinstance(session_ticket, dict):
        return False
    readings = session_ticket.get("readings") if isinstance(session_ticket.get("readings"), dict) else {}
    if readings.get("live_confluence") or readings.get("history_eligible") is False:
        return True
    track = str(
        readings.get("track")
        or session_ticket.get("track")
        or readings.get("source")
        or session_ticket.get("source")
        or session_ticket.get("regime")
        or ""
    )
    if track == "live_confluence":
        return True
    label = str(readings.get("accuracy_label") or session_ticket.get("accuracy_label") or "").lower()
    return "live confluence" in label


def supersede_open_live_for_model(
    session_ticket: Optional[Dict[str, Any]],
    *,
    closed_at: Any = None,
    reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """If a live-confluence call is open and the model now lists, close live first.

    Model / proven / champion always wins. Open model tickets are left alone
    (no stacking). Returns the ticket pack ready for persist_new_ticket.
    """
    live = open_ticket(session_ticket)
    if not live:
        return session_ticket
    if not is_live_confluence_ticket(session_ticket):
        # Open model call keeps the seat — do not replace with another model clip here.
        return session_ticket
    note = reason or "Model listed call takes priority over live confluence."
    return _close_open_ticket(
        session_ticket,
        status="superseded_by_model",
        closed_at=closed_at,
        reason=note,
    )


def close_early_drop(
    session_ticket: Optional[Dict[str, Any]],
    *,
    exit_price: Optional[float] = None,
    closed_at: Any = None,
    reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Auto-close when the tape never ran in favor and turned against the call.

    Research (year + 30d 5m): cutting never-ran losers early lifts points without
    cutting call count. Status is early_drop — not a full stop, not a cancel.
    """
    live = open_ticket(session_ticket)
    points = None
    if live is not None and exit_price is not None and live.get("entry") is not None:
        try:
            entry = float(live["entry"])
            px = float(exit_price)
            bull = "BUY" in str(live.get("decision") or "")
            points = round((px - entry) if bull else (entry - px), 1)
        except (TypeError, ValueError):
            points = None
    return _close_open_ticket(
        session_ticket,
        status="early_drop",
        closed_at=closed_at,
        exit_price=exit_price,
        points=points,
        reason=reason,
    )


def _close_open_ticket(
    session_ticket: Optional[Dict[str, Any]],
    *,
    status: str,
    closed_at: Any = None,
    exit_price: Optional[float] = None,
    points: Optional[float] = None,
    reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    live = open_ticket(session_ticket)
    if not live or not session_ticket:
        return session_ticket
    if closed_at is None:
        try:
            import market_symbols

            closed_at = market_symbols.ist_now().isoformat()
        except Exception:
            closed_at = None
    hist = list(session_ticket.get("history") or [])
    row = {
        "decision": live.get("decision"),
        "entry": live.get("entry"),
        "stop_loss": live.get("stop_loss"),
        "target_1": live.get("target_1"),
        "target_2": live.get("target_2"),
        "p_t1": live.get("p_t1"),
        "p_meta": live.get("p_meta") or live.get("p_t1"),
        "regime": live.get("regime"),
        "taken_at": live.get("taken_at"),
        "closed_at": closed_at,
        "status": status,
        "readings": live.get("readings"),
    }
    if exit_price is not None:
        row["exit_price"] = exit_price
        row["exit_source"] = "early_drop" if status == "early_drop" else "manual"
    if points is not None:
        row["points"] = points
    if reason:
        row["close_reason"] = reason
    hist.append(row)
    out = dict(session_ticket)
    out["history"] = hist
    out["tickets"] = max(int(out.get("tickets") or 0), len(hist))
    out["status"] = status
    out["decision"] = "HOLD"
    out["closed_at"] = closed_at
    out["entry"] = None
    out["stop_loss"] = None
    out["target_1"] = None
    out["target_2"] = None
    return out


def open_ticket(session_ticket: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not session_ticket:
        return None
    status = str(session_ticket.get("status") or "open")
    if session_ticket.get("decision") in (None, "HOLD"):
        return None
    if status in CLOSED_STATUSES:
        return None
    return session_ticket


def mark_ticket_from_tape(
    session_ticket: Optional[Dict[str, Any]],
    *,
    last: float,
    session_high: Optional[float] = None,
    session_low: Optional[float] = None,
    bars: Any = None,
    symbol: Optional[str] = None,
    asof: Any = None,
    use_ticks: bool = True,
    bar_minutes: int = 15,
) -> Optional[Dict[str, Any]]:
    """If an open ticket's SL or T1 has printed on the session tape, close it.
    With `bars`, the path is walked bar by bar so the first barrier wins; the
    extremes are only a fallback when no bars are available."""
    if str(symbol).upper() == "NIFTY":
        import nifty_fno_runtime

        before = open_ticket(session_ticket)
        out = nifty_fno_runtime.mark(
            session_ticket,
            last=last,
            bars=bars,
            asof=asof,
            use_ticks=use_ticks,
            bar_minutes=bar_minutes,
        )
        # Track dual SL fails (range first-break champion reverses, etc.)
        if before and not open_ticket(out):
            try:
                import fno_dual_fail_track

                hist = list((out or {}).get("history") or [])
                fno_dual_fail_track.maybe_log_closed_ticket(
                    out, symbol="NIFTY", closed_row=hist[-1] if hist else None
                )
            except Exception:
                pass
        return out
    live = open_ticket(session_ticket)
    if not live:
        return session_ticket
    try:
        sl = float(live.get("stop_loss"))
        t1 = float(live.get("target_1"))
    except (TypeError, ValueError):
        return session_ticket
    hi = float(session_high if session_high is not None else last)
    lo = float(session_low if session_low is not None else last)
    bearish = "SELL" in str(live.get("decision") or "")
    # A target already behind the entry is not a win (30 Sep BHARTIARTL closed in 2 seconds).
    if live.get("entry") is not None and not levels_on_side(live.get("decision"), live.get("entry"), sl, t1):
        status = "expired"
        out = dict(session_ticket)
        out["status"] = status
        closed_at = None
        try:
            import market_symbols

            closed_at = market_symbols.ist_now().isoformat()
        except Exception:
            closed_at = None
        out["closed_at"] = closed_at
        hist = list(out.get("history") or [])
        hist.append({
            "decision": live.get("decision"),
            "entry": live.get("entry"),
            "stop_loss": sl,
            "target_1": t1,
            "target_2": live.get("target_2"),
            "p_t1": live.get("p_t1"),
            "p_meta": live.get("p_meta") or live.get("p_t1"),
            "regime": live.get("regime"),
            "taken_at": live.get("taken_at"),
            "closed_at": closed_at,
            "status": status,
            "readings": live.get("readings"),
        })
        out["history"] = hist
        out["tickets"] = max(int(out.get("tickets") or 0), len(hist))
        out["decision"] = "HOLD"
        out["entry"] = None
        out["stop_loss"] = None
        out["target_1"] = None
        out["target_2"] = None
        return out
    status: Optional[str] = None
    if bars is not None:
        status = path_status(
            bars, live.get("taken_at"), last, bearish=bearish, stop_loss=sl, target_1=t1
        )
    if status is None:
        if bearish:
            hit_sl = hi >= sl
            hit_t1 = lo <= t1
        else:
            hit_sl = lo <= sl
            hit_t1 = hi >= t1
        if not hit_sl and not hit_t1:
            return session_ticket
        status = "same_bar_both" if hit_sl and hit_t1 else ("t1_before_sl" if hit_t1 else "sl_before_t1")
    out = dict(session_ticket)
    out["status"] = status
    closed_at = None
    try:
        import market_symbols

        closed_at = market_symbols.ist_now().isoformat()
    except Exception:
        closed_at = None
    out["closed_at"] = closed_at
    hist = list(out.get("history") or [])
    hist.append({
        "decision": live.get("decision"),
        "entry": live.get("entry"),
        "stop_loss": sl,
        "target_1": t1,
        "target_2": live.get("target_2"),
        "p_t1": live.get("p_t1"),
        "p_meta": live.get("p_meta") or live.get("p_t1"),
        "regime": live.get("regime"),
        "taken_at": live.get("taken_at"),
        "closed_at": closed_at,
        "status": status,
        "readings": live.get("readings"),
    })
    out["history"] = hist
    out["tickets"] = max(int(out.get("tickets") or 0), len(hist))
    # Live badge must not keep showing the dead call.
    out["decision"] = "HOLD"
    out["status"] = status
    out["entry"] = None
    out["stop_loss"] = None
    out["target_1"] = None
    out["target_2"] = None
    return out


# Transparent suggestion stack (research: VWAP+body+wick on engulf/EMA pullback).
SUGGEST_STOP_ATR = 0.75
SUGGEST_T1_ATR = 0.75
SUGGEST_BODY_MIN = 0.45
SUGGEST_ATR_BARS = 14


def _suggest_frame(bars: Any) -> Optional[Any]:
    if bars is None:
        return None
    try:
        if len(bars) < 25:
            return None
    except TypeError:
        return None
    try:
        import pandas as pd

        work = bars.copy() if hasattr(bars, "copy") else bars
        rename = {c: str(c).title() for c in work.columns}
        work = work.rename(columns=rename)
        need = ("Open", "High", "Low", "Close")
        if any(c not in work.columns for c in need):
            return None
        if not isinstance(work.index, pd.DatetimeIndex):
            return None
        return work
    except Exception:
        return None


def _suggestion_drop_partial(work: Any, interval: str, asof: Any = None) -> Any:
    """Keep only finished candles for the suggestion interval."""
    try:
        import kite_data

        minutes = "5minute" if interval == "5m" else "15minute"
        trimmed = kite_data.drop_unfinished_candle(work, minutes, asof=asof)
        return trimmed if trimmed is not None and len(trimmed) >= 25 else work
    except Exception:
        return work


def _suggestion_work_bars(
    bars: Any,
    live_context: Optional[Dict[str, Any]] = None,
    *,
    asof: Any = None,
) -> Tuple[Optional[Any], str]:
    """Prefer finished 5m tape; fall back to 15m only when 5m is missing."""
    five = _suggest_frame((live_context or {}).get("bars_5m"))
    if five is not None:
        return _suggestion_drop_partial(five, "5m", asof=asof), "5m"
    fifteen = _suggest_frame(bars)
    if fifteen is not None:
        return _suggestion_drop_partial(fifteen, "15m", asof=asof), "15m"
    return None, ""


def _suggestion_atr(work: Any) -> Optional[float]:
    try:
        import fno_risk_engine

        return fno_risk_engine.bar_atr(work.tail(max(SUGGEST_ATR_BARS + 2, 20)))
    except Exception:
        return None


def _suggestion_session_vwap(work: Any) -> Optional[float]:
    """Causal VWAP for the session of the last bar (volume-weighted; else typical mean)."""
    try:
        import pandas as pd

        last_day = work.index[-1].date()
        day = work[work.index.map(lambda t: t.date()) == last_day]
        if len(day) < 2:
            return None
        typical = (day["High"].astype(float) + day["Low"].astype(float) + day["Close"].astype(float)) / 3.0
        if "Volume" in day.columns and float(day["Volume"].fillna(0).sum()) > 0:
            vol = day["Volume"].astype(float).clip(lower=0.0)
            den = float(vol.sum())
            if den > 0:
                return float((typical * vol).sum() / den)
        return float(typical.mean())
    except Exception:
        return None


def _suggestion_trigger(work: Any) -> Tuple[int, str, Dict[str, Any]]:
    """Engulfing or EMA9 pullback in a 9/20 stack on the last closed bar."""
    o = work["Open"].astype(float)
    h = work["High"].astype(float)
    l = work["Low"].astype(float)
    c = work["Close"].astype(float)
    atr = _suggestion_atr(work)
    if atr is None or atr <= 0:
        return 0, "", {}
    e9 = c.ewm(span=9, adjust=False).mean()
    e20 = c.ewm(span=20, adjust=False).mean()
    px = float(c.iloc[-1])
    op = float(o.iloc[-1])
    hi = float(h.iloc[-1])
    lo = float(l.iloc[-1])
    po, pc = float(o.iloc[-2]), float(c.iloc[-2])
    e9v, e20v = float(e9.iloc[-1]), float(e20.iloc[-1])

    bull_eng = px > op and pc < po and px >= po and op <= pc
    bear_eng = px < op and pc > po and px <= po and op >= pc
    bull_ema = px >= e9v >= e20v and lo <= e9v + 0.15 * atr and px > op
    bear_ema = px <= e9v <= e20v and hi >= e9v - 0.15 * atr and px < op

    meta = {
        "atr": atr,
        "ema9": round(e9v, 2),
        "ema20": round(e20v, 2),
        "body_frac": round(abs(px - op) / max(hi - lo, 1e-9), 3),
        "upper_wick": round(hi - max(px, op), 2),
        "lower_wick": round(min(px, op) - lo, 2),
    }
    # Prefer dual / engulf naming when both fire.
    if bull_eng and bull_ema:
        return 1, "engulf+ema_pullback", meta
    if bear_eng and bear_ema:
        return -1, "engulf+ema_pullback", meta
    if bull_eng:
        return 1, "engulf", meta
    if bear_eng:
        return -1, "engulf", meta
    if bull_ema:
        return 1, "ema_pullback", meta
    if bear_ema:
        return -1, "ema_pullback", meta
    return 0, "", meta


def _suggestion_filters_ok(work: Any, side: int, meta: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """VWAP aligned + strong body + clean wick (research transparent stack)."""
    px = float(work["Close"].astype(float).iloc[-1])
    op = float(work["Open"].astype(float).iloc[-1])
    body = abs(px - op)
    vwap = _suggestion_session_vwap(work)
    body_frac = float(meta.get("body_frac") or 0)
    upper = float(meta.get("upper_wick") or 0)
    lower = float(meta.get("lower_wick") or 0)
    vwap_ok = False
    if vwap is not None:
        vwap_ok = (px >= float(vwap)) if side > 0 else (px <= float(vwap))
    body_ok = body_frac >= SUGGEST_BODY_MIN
    wick_ok = (lower <= body * 1.2) if side > 0 else (upper <= body * 1.2)
    detail = {
        "vwap": None if vwap is None else round(float(vwap), 2),
        "vwap_ok": vwap_ok,
        "body_ok": body_ok,
        "wick_ok": wick_ok,
        "body_frac": body_frac,
    }
    return bool(vwap_ok and body_ok and wick_ok), detail


def _suggestion_levels(side: int, price: float, atr: float) -> Tuple[Optional[float], Optional[float]]:
    if side == 0 or atr <= 0 or price <= 0:
        return None, None
    sl_pts = max(8.0, round(SUGGEST_STOP_ATR * atr, 1))
    t1_pts = max(8.0, round(SUGGEST_T1_ATR * atr, 1))
    if side > 0:
        return round(price - sl_pts, 2), round(price + t1_pts, 2)
    return round(price + sl_pts, 2), round(price - t1_pts, 2)


def _suggestion_candle(bars: Any, live_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Candlestick read for pattern_watch fallback (last 5 bars of suggest tape)."""
    try:
        import analysis_engine

        work, _ = _suggestion_work_bars(bars, live_context, asof=None)
        if work is not None and len(work) >= 5:
            return analysis_engine.detect_candlestick_window(work.tail(5)) or {}
    except Exception:
        pass
    micro = ((live_context or {}).get("microstructure") or {})
    candle = micro.get("micro_candlestick_15m")
    return candle if isinstance(candle, dict) else {}


def _trigger_label(trigger: str) -> str:
    labels = {
        "engulf": "Engulfing",
        "ema_pullback": "EMA pullback",
        "engulf+ema_pullback": "Engulf + EMA",
        "strong_candle": "Strong candle",
    }
    return labels.get(str(trigger or ""), str(trigger or "pattern").replace("_", " "))


def _live_suggestion_basis(
    *,
    interval: str,
    trigger: str,
    kind: str,
    incomplete: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Short desk tag + one-line why for live candle suggestions."""
    iv = "5m" if str(interval).startswith("5") else ("15m" if str(interval).startswith("15") else str(interval or "live"))
    trig = _trigger_label(trigger)
    if kind == "pattern_watch":
        miss = ", ".join(incomplete or []) or "filters incomplete"
        return {
            "suggestion_tag": "Pattern watch",
            "tag_tone": "warning",
            "basis": f"Live {iv} {trig} — stack incomplete ({miss}). Discretionary only.",
        }
    return {
        "suggestion_tag": f"Live {iv} · {trig}",
        "tag_tone": "neutral",
        "basis": f"Live {iv} indicator: {trig} with VWAP, body, and wick aligned.",
    }


def build_call_suggestion(
    fno_head: Optional[Dict[str, Any]],
    *,
    price: Any,
    session_ticket: Optional[Dict[str, Any]] = None,
    symbol: Optional[str] = None,
    bars: Any = None,
    live_quote: Any = None,
    live_context: Optional[Dict[str, Any]] = None,
    day_range: Optional[Dict[str, Any]] = None,
    asof: Any = None,
) -> Optional[Dict[str, Any]]:
    """Independent suggestion: engulf or EMA pullback → VWAP+body+wick → 0.75×ATR.

    Not a listed call. Works with or without an open model ticket. Prefer 5m bars
    from live_context; fall back to 15m decision bars.
    """
    del session_ticket, day_range  # independent of open ticket / day-range clip
    try:
        px = float(price)
    except (TypeError, ValueError):
        return None
    if px <= 0:
        return None
    # Suggestions read finished 5m candles (+ tech filters). Do not reuse the
    # listed-call entry_issue gate (fresh quote / OR wait) — that blanked the card.
    del live_quote
    work, interval = _suggestion_work_bars(bars, live_context, asof=asof)
    if work is None:
        return None
    side, trigger, meta = _suggestion_trigger(work)
    if side == 0 or not trigger:
        return None
    ok, filt = _suggestion_filters_ok(work, side, meta)
    if not ok:
        return None
    atr = float(meta.get("atr") or 0)
    # Size off the suggestion tape close when live LTP is missing/stale.
    try:
        entry_px = float(work["Close"].astype(float).iloc[-1])
    except Exception:
        entry_px = px
    sl, t1 = _suggestion_levels(side, entry_px, atr)
    decision = "BUY" if side > 0 else "SELL"
    if not levels_on_side(decision, entry_px, sl, t1):
        return None
    want = "BULLISH" if side > 0 else "BEARISH"
    bars_asof = None
    try:
        bars_asof = str(work.index[-1])
    except Exception:
        bars_asof = (fno_head or {}).get("bars_asof")
    basis = _live_suggestion_basis(interval=interval, trigger=trigger, kind="suggestion")
    return {
        "kind": "suggestion",
        "source": "vwap_body_wick_stack",
        "decision": decision,
        "entry": round(entry_px, 2),
        "stop_loss": sl,
        "target_1": t1,
        "target_2": None,
        "p_t1": (fno_head or {}).get("p_t1"),
        "need": (fno_head or {}).get("buy_p"),
        "bars_asof": bars_asof,
        "interval": interval,
        "trigger": trigger,
        "candle_bias": want,
        "ema_lean": want,
        "candle_patterns": [trigger.replace("_", " ")],
        "score_delta": 0.0,
        "atr": round(atr, 2),
        "filters": filt,
        "suggestion_tag": basis["suggestion_tag"],
        "tag_tone": basis["tag_tone"],
        "basis": basis["basis"],
        "message": basis["basis"],
    }


def build_pattern_watch(
    fno_head: Optional[Dict[str, Any]],
    *,
    price: Any,
    session_ticket: Optional[Dict[str, Any]] = None,
    symbol: Optional[str] = None,
    bars: Any = None,
    live_quote: Any = None,
    live_context: Optional[Dict[str, Any]] = None,
    day_range: Optional[Dict[str, Any]] = None,
    asof: Any = None,
) -> Optional[Dict[str, Any]]:
    """Discretionary watch when a 5m trigger fires but VWAP/body/wick is incomplete."""
    del session_ticket, day_range, live_quote
    try:
        px = float(price)
    except (TypeError, ValueError):
        return None
    if px <= 0:
        return None
    work, interval = _suggestion_work_bars(bars, live_context, asof=asof)
    if work is None:
        return None
    side, trigger, meta = _suggestion_trigger(work)
    if side == 0:
        # Fall back to strong 5m/15m candle score without full stack.
        candle = _suggestion_candle(bars, live_context)
        bias = str(candle.get("bias") or "NEUTRAL").upper()
        score = float(candle.get("score_delta") or 0)
        atr_v = _suggestion_atr(work) or 0.0
        if bias == "BULLISH" and score >= 8:
            side, trigger = 1, "strong_candle"
            meta = {"atr": atr_v, "body_frac": 0.0, "upper_wick": 0.0, "lower_wick": 0.0}
        elif bias == "BEARISH" and score <= -8:
            side, trigger = -1, "strong_candle"
            meta = {"atr": atr_v, "body_frac": 0.0, "upper_wick": 0.0, "lower_wick": 0.0}
        else:
            return None
    ok, filt = _suggestion_filters_ok(work, side, meta)
    if ok and trigger not in ("strong_candle",):
        # Full suggestion path owns this bar.
        return None
    atr = float(meta.get("atr") or 0)
    if atr <= 0:
        return None
    try:
        entry_px = float(work["Close"].astype(float).iloc[-1])
    except Exception:
        entry_px = px
    decision = "BUY" if side > 0 else "SELL"
    sl, t1 = _suggestion_levels(side, entry_px, atr)
    if not levels_on_side(decision, entry_px, sl, t1):
        return None
    why = []
    if not filt.get("vwap_ok"):
        why.append("VWAP not aligned")
    if not filt.get("body_ok"):
        why.append("body too small")
    if not filt.get("wick_ok"):
        why.append("wick messy")
    if trigger == "strong_candle":
        why.append("strong candle score only")
    basis = _live_suggestion_basis(
        interval=interval, trigger=trigger, kind="pattern_watch", incomplete=why
    )
    return {
        "kind": "pattern_watch",
        "source": "stack_incomplete_watch",
        "decision": decision,
        "entry": round(entry_px, 2),
        "stop_loss": sl,
        "target_1": t1,
        "target_2": None,
        "p_t1": (fno_head or {}).get("p_t1"),
        "need": (fno_head or {}).get("buy_p"),
        "bars_asof": str(work.index[-1]),
        "interval": interval,
        "trigger": trigger,
        "candle_bias": "BULLISH" if side > 0 else "BEARISH",
        "ema_lean": "BULLISH" if side > 0 else "BEARISH",
        "candle_patterns": [trigger.replace("_", " ")],
        "score_delta": 0.0,
        "filters": filt,
        "discretionary": True,
        "suggestion_tag": basis["suggestion_tag"],
        "tag_tone": basis["tag_tone"],
        "basis": basis["basis"],
        "message": basis["basis"],
    }


def stamp_call_suggestion(
    result: Dict[str, Any],
    fno_head: Optional[Dict[str, Any]],
    *,
    price: Any,
    session_ticket: Optional[Dict[str, Any]] = None,
    symbol: Optional[str] = None,
    bars: Any = None,
    live_quote: Any = None,
    live_context: Optional[Dict[str, Any]] = None,
    day_range: Optional[Dict[str, Any]] = None,
    asof: Any = None,
) -> Optional[Dict[str, Any]]:
    # Dual-track model suggestions win when present. Live-confluence / HL-LH stack
    # suggestions (listable=False) stay Suggestions only — never auto Calls.
    prior = result.get("suggestion") if isinstance(result, dict) else None
    if (
        isinstance(prior, dict)
        and prior.get("live_confluence")
        and prior.get("decision") in ("BUY", "SELL")
        and prior.get("listable") is False
        and not (isinstance(prior, dict) and prior.get("dual_track"))
    ):
        fa = dict(result.get("fno_analysis") or {})
        fa["suggestion"] = prior
        result["fno_analysis"] = fa
        result["suggestion"] = prior
        return prior
    if (
        isinstance(prior, dict)
        and prior.get("hl_lh_stack")
        and prior.get("decision") in ("BUY", "SELL")
        and prior.get("listable") is False
        and not prior.get("dual_track")
    ):
        fa = dict(result.get("fno_analysis") or {})
        fa["suggestion"] = prior
        result["fno_analysis"] = fa
        result["suggestion"] = prior
        return prior
    if (
        isinstance(prior, dict)
        and prior.get("decision") in ("BUY", "SELL")
        and (prior.get("dual_track") or prior.get("afternoon_thrust"))
    ):
        # Ensure a short basis line for the clean UI (mutate in place).
        if not prior.get("basis"):
            track = str(prior.get("track") or "baseline")
            if track == "proven_100":
                prior["suggestion_tag"] = "Model · Confident 100%"
                prior["tag_tone"] = "proven"
                prior["basis"] = "From the 15m dual-track model (walk-forward proven gate)."
            elif track == "champion":
                prior["suggestion_tag"] = "Model · most accurate"
                prior["tag_tone"] = "champion"
                prior["basis"] = "From the 15m dual-track model (champion quality gate)."
            elif track == "confident" or prior.get("afternoon_thrust"):
                prior["suggestion_tag"] = "Confident · afternoon thrust (~92%)"
                prior["tag_tone"] = "champion"
                prior["basis"] = (
                    "NIFTY post-13:00 BUY thrust — close>OR, green bar, "
                    "break prior 2 highs, +30 from 13:00 open."
                )
            else:
                prior["suggestion_tag"] = "Model · lower accuracy · your risk"
                prior["tag_tone"] = "neutral"
                prior["basis"] = "Baseline track — lower hit rate; take on your risk."
        fa = dict(result.get("fno_analysis") or {})
        fa["suggestion"] = prior
        fa["pattern_watch"] = None
        if prior.get("afternoon_thrust"):
            fa["nifty_afternoon_thrust"] = True
        result["fno_analysis"] = fa
        result["suggestion"] = prior
        result["pattern_watch"] = None
        return prior
    # Research HL/LH midday stack (NIFTY/SENSEX only) before generic candle suggestion.
    try:
        import fno_hl_lh_stack

        hl = fno_hl_lh_stack.maybe_suggestion(
            symbol or "",
            bars,
            price=price,
            asof=asof,
        )
        if isinstance(hl, dict) and hl.get("decision") in ("BUY", "SELL"):
            result["suggestion"] = hl
            result["pattern_watch"] = None
            fa = dict(result.get("fno_analysis") or {})
            fa["suggestion"] = hl
            fa["hl_lh_stack"] = hl
            fa["pattern_watch"] = None
            notes = list(fa.get("desk_alerts") or [])
            msg = (
                f"HL/LH stack suggests {hl.get('decision')} "
                "(suggest only — not listed on Calls)."
            )
            if msg not in notes:
                notes.insert(0, msg)
            fa["desk_alerts"] = notes
            result["fno_analysis"] = fa
            return hl
    except Exception:
        pass
    suggestion = build_call_suggestion(
        fno_head,
        price=price,
        session_ticket=session_ticket,
        symbol=symbol,
        bars=bars,
        live_quote=live_quote,
        live_context=live_context,
        day_range=day_range,
        asof=asof,
    )
    watch = None
    if suggestion is None:
        watch = build_pattern_watch(
            fno_head,
            price=price,
            session_ticket=session_ticket,
            symbol=symbol,
            bars=bars,
            live_quote=live_quote,
            live_context=live_context,
            day_range=day_range,
            asof=asof,
        )
    result["suggestion"] = suggestion
    result["pattern_watch"] = watch
    fa = result.get("fno_analysis")
    if isinstance(fa, dict):
        fa["suggestion"] = suggestion
        fa["pattern_watch"] = watch
    return suggestion


def _opening_range_from_bars(bars: Any, asof: Any = None) -> Optional[Dict[str, Any]]:
    """First completed session bar high/low — the live opening range."""
    if bars is None:
        return None
    try:
        if len(bars) == 0:
            return None
    except TypeError:
        return None
    when = as_ist(asof)
    try:
        import pandas as pd

        work = bars
        if when is not None:
            day = when.date()
            keep = []
            for ts in work.index:
                stamp = pd.Timestamp(ts)
                if stamp.tzinfo is None:
                    stamp = stamp.tz_localize("Asia/Kolkata")
                else:
                    stamp = stamp.tz_convert("Asia/Kolkata")
                keep.append(stamp.date() == day)
            sess = work.loc[keep]
        else:
            sess = work
        if sess is None or not len(sess):
            return None
        high_col = next(c for c in sess.columns if str(c).lower() == "high")
        low_col = next(c for c in sess.columns if str(c).lower() == "low")
        high = float(sess[high_col].iloc[0])
        low = float(sess[low_col].iloc[0])
    except Exception:
        return None
    if high <= low:
        return None
    return {"available": True, "or_high": high, "or_low": low}


def persist_new_ticket(
    session_ticket: Optional[Dict[str, Any]],
    *,
    decision: str,
    stop_loss: Any,
    target_1: Any,
    taken_at: Any,
    session_date_value: Any,
    entry: Any = None,
    target_2: Any = None,
    p_t1: Any = None,
    p_meta: Any = None,
    regime: Any = None,
    readings: Any = None,
    symbol: Optional[str] = None,
    bars: Any = None,
    live_quote: Any = None,
) -> Optional[Dict[str, Any]]:
    # Never carry an open/closed ticket from a prior session into today's list.
    # (Previously only NIFTY cleared this — BN/Sensex could block a new day.)
    if session_ticket and str(session_ticket.get("session_date") or "")[:10] != str(session_date_value)[:10]:
        session_ticket = None
    dualish = False
    soft_pre_dual = False
    confident_thrust = False
    track = ""
    if isinstance(readings, dict):
        track = str(readings.get("track") or readings.get("source") or "")
        confident_thrust = bool(
            readings.get("afternoon_thrust")
            or readings.get("morning_strong_thrust")
            or track == "confident"
            or "thrust_confident" in track
            or "thrust_confident" in str(readings.get("source") or "")
        )
        dualish = bool(readings.get("dual_track")) or confident_thrust or track in (
            "proven_100",
            "champion",
            "baseline",
            "dual10m",
            "crown_5m",
            "champ_plus",
            "p2g_10m",
            "dual5_research",
            "confident",
        )
        soft_pre_dual = bool(readings.get("soft_gates") or readings.get("good")) or track in (
            "pre_dual_single",
            "good",
        )
        if soft_pre_dual:
            try:
                import fno_live_config

                # Hard kill: when pre-dual channel is off, never list/replace on soft path
                if not fno_live_config.enable_pre_dual_single():
                    return session_ticket
                soft_pre_dual = fno_live_config.pre_dual_soft_gates()
            except Exception:
                soft_pre_dual = True
    # Soft pre-dual "good" path skips hard entry/shallow HOLDs (alerts only upstream).
    skip_hard = dualish or soft_pre_dual
    # Kill raw ExtraTrees / rule_fno single 15m listing when dual desk is exclusive.
    # Dual proven/champion (dualish) and stamped good/pre-dual still list.
    try:
        import fno_live_config as _flc

        _is_live_idx = _flc.is_fno_live_index(symbol)
    except Exception:
        _is_live_idx = str(symbol or "").upper() in ("NIFTY", "SENSEX")
    if not dualish and not soft_pre_dual and _is_live_idx:
        src = ""
        if isinstance(readings, dict):
            src = str(readings.get("source") or "")
        if src in ("extra_trees_fno_t1", "hgb_fno_t1_regime", "rule_fno") or track in (
            "extra_trees_fno_t1",
            "hgb_fno_t1_regime",
            "rule_fno",
        ):
            try:
                import fno_live_config

                if not fno_live_config.allow_extra_trees_single_list():
                    return session_ticket
            except Exception:
                return session_ticket
    # NIFTY core freshness only — dual-track / soft good path list independently.
    if str(symbol).upper() == "NIFTY" and not skip_hard:
        from nifty_fno_data import entry_issue

        if entry_issue(bars, live_quote, taken_at, allow_dual_lag=False):
            return session_ticket
    if decision in (None, "HOLD"):
        return session_ticket
    try:
        sl = float(stop_loss)
        t1 = float(target_1)
    except (TypeError, ValueError):
        return session_ticket
    if entry is not None and not levels_on_side(decision, entry, sl, t1):
        return session_ticket
    # Shallow OR poke is a hard block on core path only.
    # Dual-track and soft pre-dual good path do not re-block.
    orb = _opening_range_from_bars(bars, taken_at)
    if (not skip_hard) and orb and shallow_break_hold(decision, entry, orb, session_ticket, asof=taken_at):
        return session_ticket
    # Optional A+ only mode (prior-30 100% gate). Off by default — desk alerts still warn.
    try:
        import fno_pdf_accuracy

        if fno_pdf_accuracy.ACCURACY_PLUS_ONLY and not fno_pdf_accuracy.calendar_settled(taken_at):
            return session_ticket
    except Exception:
        pass
    live = open_ticket(session_ticket)
    if live:
        # One open model call per symbol.
        # Soft/good pre-dual must NEVER cancel on LTP drift — that caused
        # BANKNIFTY/SENSEX double NEW then cancel within 1–2 minutes.
        live_side = str(live.get("decision") or "").upper()
        new_side = str(decision or "").upper()
        live_readings = live.get("readings") if isinstance(live.get("readings"), dict) else {}
        live_track = str(
            live_readings.get("track") or live_readings.get("source") or ""
        )
        live_is_dual_family = bool(live_readings.get("dual_track")) or live_track in (
            "proven_100",
            "champion",
            "baseline",
            "dual10m",
            "champ_plus",
            "p2g_10m",
            "dual5_research",
            "proven_research",
        )
        if live_readings.get("afternoon_thrust") or live_readings.get("morning_strong_thrust"):
            live_is_dual_family = False
        suppress_dual = False
        try:
            import fno_live_config

            suppress_dual = bool(fno_live_config.suppress_dual_list_for(symbol or ""))
        except Exception:
            suppress_dual = False
        # Under SUPPRESS_DUAL_LIST, confident thrust may replace an open dual-family
        # ticket (same or opposite side) so afternoon/morning lanes actually list.
        thrust_replaces_dual = bool(
            confident_thrust and suppress_dual and live_is_dual_family
        )
        # NIFTY accurate desk (morning L5_u70_b80 + CHAMP_PLUS / P2F·P2G tags):
        # never silent-skip. Same fire merges upstream; distinct fire archives
        # prior open into history and lists. Afternoon must not block.
        new_track = ""
        if isinstance(readings, dict):
            new_track = str(readings.get("track") or readings.get("source") or "")
        is_nifty = str(symbol or "").upper() in ("NIFTY", "NIFTY 50", "NIFTY50")
        nifty_accurate_lists = bool(
            is_nifty
            and (
                confident_thrust
                or new_track in ("dual10m", "champ_plus", "p2g_10m", "confident")
                or (
                    isinstance(readings, dict)
                    and (
                        readings.get("morning_strong_thrust")
                        or readings.get("champ_plus")
                        or "CHAMP_PLUS" in str(readings.get("accuracy_label") or "")
                        or "P2F" in str(readings.get("accuracy_label") or "")
                        or "P2G" in str(readings.get("accuracy_label") or "")
                    )
                )
            )
        )
        if live_side == new_side and not thrust_replaces_dual and not nifty_accurate_lists:
            # Same side already listed — keep the original ticket until T1/SL/manual.
            return session_ticket
        if not skip_hard and not thrust_replaces_dual and not nifty_accurate_lists:
            return session_ticket
        # Opposite side: only dual-track may replace; soft good cannot flip-flop.
        if not dualish and not thrust_replaces_dual and not nifty_accurate_lists:
            return session_ticket
        rank = {
            "proven_100": 3,
            "confident": 3,
            "champion": 2,
            "dual10m": 2,
            "champ_plus": 2,
            "p2g_10m": 2,
            "crown_5m": 1,
            "dual5_research": 1,
            "baseline": 1,
            "pre_dual_single": 0,
            "good": 0,
        }
        if (
            not thrust_replaces_dual
            and not nifty_accurate_lists
            and rank.get(new_track, 0) <= rank.get(live_track, 0)
        ):
            return session_ticket
        session_ticket = _close_open_ticket(
            session_ticket,
            status="cancelled",
            closed_at=str(taken_at),
            reason=(
                "Archived — NIFTY accurate lane lists without blocker"
                if nifty_accurate_lists
                else (
                    "Replaced by nifty confident thrust (suppressed dual open ticket)"
                    if thrust_replaces_dual
                    else "Replaced by stronger dual-track call that cleared model gates"
                )
            ),
        )
    prev = dict(session_ticket or {})
    closed_n = closed_ticket_count(prev)
    n = max(int(prev.get("tickets") or 0), closed_n) + 1
    # Live-confluence clips are uncapped (accuracy-gated elsewhere). Model /
    # dual-track tickets still respect the daily listed-call cap.
    live_clip = False
    if isinstance(readings, dict):
        live_clip = bool(
            readings.get("live_confluence")
            or readings.get("track") == "live_confluence"
            or readings.get("source") == "live_confluence"
            or readings.get("setup_type") == "live_confluence"
            or str(regime or "") == "live_confluence"
        )
    if not live_clip:
        day_cap = MAX_LISTED_TICKETS_PER_DAY
        if str(symbol or "").upper() in ("NIFTY", "NIFTY 50", "NIFTY50"):
            day_cap = MAX_LISTED_TICKETS_NIFTY
        if closed_n >= day_cap:
            return session_ticket
        if n > day_cap:
            return session_ticket
    return {
        "session_date": str(session_date_value),
        "decision": decision,
        "taken_at": str(taken_at),
        "tickets": n,
        "status": "open",
        "entry": entry,
        "stop_loss": sl,
        "target_1": t1,
        "target_2": target_2,
        "p_t1": p_t1,
        "p_meta": p_meta if p_meta is not None else p_t1,
        "regime": regime,
        "readings": readings or None,
        "history": list(prev.get("history") or []),
    }


def _event_hold(ts: Any) -> Optional[str]:
    dt = as_ist(ts)
    if dt is None:
        return None
    import event_calendar

    day = dt.date() if hasattr(dt, "date") else None
    if day is None:
        return None
    return event_calendar.event_hold(day)


def expiry_open_hold(expiry_day: bool, fresh_break: bool) -> Optional[str]:
    """Expiry is an alert. It does not hide the call."""
    if expiry_day and not fresh_break:
        return "Expiry day — higher risk until price closes outside the opening range."
    if expiry_day:
        return "Expiry day — weekly settlement. Size for a faster tape."
    return None


def cross_index_hold(decision: str, other_decision: Optional[str]) -> Optional[str]:
    """No new call when Nifty and Bank Nifty point opposite ways."""
    other = str(other_decision or "").upper()
    side = str(decision or "").upper()
    if "BUY" not in side and "SELL" not in side:
        return None
    if "BUY" not in other and "SELL" not in other:
        return None
    if ("BUY" in side) != ("BUY" in other):
        return "Nifty and Bank Nifty disagree — check both before you take this."
    return None


def _clock(ts: Any) -> Optional[time]:
    dt = as_ist(ts)
    if dt is None:
        return None
    return dt.timetz().replace(tzinfo=None) if hasattr(dt, "timetz") else dt.time()


def in_opening_call_window(ts: Any) -> bool:
    """9:15–10:15 IST. Calls may print inside the opening range; the risk is higher."""
    t = _clock(ts)
    return t is not None and ENTRY_START <= t < OPENING_CALL_END


def clock_alert(ts: Any) -> Optional[str]:
    """Time is context only. A passed model call is still shown."""
    t = _clock(ts)
    if t is None:
        return None
    if t < ENTRY_START:
        return "Before 9:15 IST. The call is shown if the model passed — the cash open has not started."
    if t > SESSION_END:
        return "After 3:30 pm IST. The call is shown if the model passed — closing risk is higher."
    return None


def entry_window_hold(ts: Any, session_ticket: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Clock and expiry never hide a call. Use clock_alert for the note."""
    return None


def last_closed_decision(session_ticket: Optional[Dict[str, Any]]) -> Optional[str]:
    if not session_ticket:
        return None
    hist = list(session_ticket.get("history") or [])
    if hist:
        return str(hist[-1].get("decision") or "")
    if str(session_ticket.get("status") or "") in ("t1_before_sl", "sl_before_t1", "same_bar_both"):
        return str(session_ticket.get("decision") or "")
    return None


def last_closed_status(session_ticket: Optional[Dict[str, Any]]) -> str:
    if not session_ticket:
        return ""
    hist = list(session_ticket.get("history") or [])
    if hist:
        return str(hist[-1].get("status") or "")
    return str(session_ticket.get("status") or "")


def last_ticket_time(session_ticket: Optional[Dict[str, Any]]) -> Optional[datetime]:
    if not session_ticket:
        return None
    hist = list(session_ticket.get("history") or [])
    stamp = None
    if hist:
        stamp = hist[-1].get("taken_at") or hist[-1].get("closed_at")
    if not stamp:
        stamp = session_ticket.get("taken_at") or session_ticket.get("closed_at")
    return as_ist(stamp)


def reclaim_too_soon(session_ticket: Optional[Dict[str, Any]], asof: Any = None) -> bool:
    """Skip the next 15-minute bar after a ticket — that is where the 1-bar flips died."""
    now = as_ist(asof)
    taken = last_ticket_time(session_ticket)
    if now is None or taken is None:
        return False
    a = now.replace(tzinfo=None) if getattr(now, "tzinfo", None) else now
    b = taken.replace(tzinfo=None) if getattr(taken, "tzinfo", None) else taken
    try:
        return (a - b).total_seconds() / 60.0 < RECLAIM_COOLDOWN_MIN
    except Exception:
        return False


def reclaim_decision(
    session_ticket: Optional[Dict[str, Any]],
    opening_range: Optional[Dict[str, Any]],
    price: Optional[float],
    asof: Any = None,
) -> Optional[str]:
    """Second call only: paid T1 can bounce back into the range; a stop needs a true failed-break."""
    if open_ticket(session_ticket) or closed_ticket_count(session_ticket) != 1:
        return None
    if reclaim_too_soon(session_ticket, asof):
        return None
    last = last_closed_decision(session_ticket) or ""
    status = last_closed_status(session_ticket)
    orb = opening_range or {}
    try:
        lo = float(orb.get("or_low"))
        hi = float(orb.get("or_high"))
        px = float(price)
    except (TypeError, ValueError):
        return None
    if hi <= lo or px <= 0:
        return None
    width = hi - lo
    failed = status in ("sl_before_t1", "same_bar_both")
    if failed:
        if "SELL" in last and px > hi:
            return "BUY"
        if "BUY" in last and px < lo:
            return "SELL"
        return None
    dt = as_ist(asof)
    if dt is not None:
        t = dt.timetz().replace(tzinfo=None) if hasattr(dt, "timetz") else dt.time()
        if t > SESSION_END:
            return None
    if "SELL" in last and px >= lo + T1_RECLAIM_FRAC * width:
        return "BUY"
    if "BUY" in last and px <= hi - T1_RECLAIM_FRAC * width:
        return "SELL"
    return None


def infer_side_override(
    session_ticket: Optional[Dict[str, Any]],
    opening_range: Optional[Dict[str, Any]],
    price: Optional[float],
    asof: Any = None,
) -> float:
    rec = reclaim_decision(session_ticket, opening_range, price, asof=asof)
    if rec == "BUY":
        return 1.0
    if rec == "SELL":
        return -1.0
    return 0.0


def is_first_clip(session_ticket: Optional[Dict[str, Any]]) -> bool:
    return not open_ticket(session_ticket) and closed_ticket_count(session_ticket) < 1


def or_gate_hold(
    decision: str,
    opening_range: Optional[Dict[str, Any]],
    session_ticket: Optional[Dict[str, Any]] = None,
    price: Optional[float] = None,
    asof: Any = None,
) -> Optional[str]:
    if decision in (None, "HOLD"):
        return None
    rec = reclaim_decision(session_ticket, opening_range, price, asof=asof)
    if rec and rec in str(decision):
        return None
    orb = opening_range or {}
    if not orb.get("available"):
        return None
    if not orb.get("broken"):
        return "Waiting — price has not closed outside the first 15-minute range."
    bias = (orb.get("bias") or "NEUTRAL").upper()
    if "BUY" in decision and bias != "BULLISH":
        return "Need a close above the first 15-minute high for a BUY."
    if "SELL" in decision and bias != "BEARISH":
        return "Need a close below the first 15-minute low for a SELL."
    return None


def session_cap_hold(session_ticket: Optional[Dict[str, Any]], ts: Any) -> Optional[str]:
    if not session_ticket:
        return None
    today = session_date(ts)
    taken_day = session_ticket.get("session_date")
    if today and taken_day and str(taken_day) != str(today):
        return None
    live = open_ticket(session_ticket)
    if live:
        n = int(live.get("tickets") or 1)
        more = (
            f"Call #{n + 1} can open after this one hits target, stop, or early-drop "
            f"(max {MAX_LISTED_TICKETS_PER_DAY}/day)."
            if n < MAX_LISTED_TICKETS_PER_DAY
            else f"Daily listed-call cap ({MAX_LISTED_TICKETS_PER_DAY}) — no further ticket today after this closes."
        )
        return (
            f"Call #{n} is still open "
            f"({live.get('decision')} from {str(live.get('taken_at') or '')[11:16] or live.get('taken_at')}). "
            f"The model read stays on screen. {more}"
        )
    closed_n = closed_ticket_count(session_ticket)
    if closed_n >= MAX_LISTED_TICKETS_PER_DAY:
        return (
            f"Daily listed-call cap ({MAX_LISTED_TICKETS_PER_DAY}) reached. "
            "No further listed ticket today."
        )
    return None


def t1_room_hold(
    decision: str,
    price: float,
    t1: Optional[float],
    day_range: Optional[Dict[str, Any]],
) -> Optional[str]:
    if decision in (None, "HOLD") or t1 is None:
        return None
    try:
        lo = float((day_range or {}).get("expected_low"))
        hi = float((day_range or {}).get("expected_high"))
    except (TypeError, ValueError):
        return None
    if hi <= lo:
        return None
    if "SELL" in decision:
        remaining = max(price - lo, 0.0)
        dist = price - float(t1)
    else:
        remaining = max(hi - price, 0.0)
        dist = float(t1) - price
    need = remaining * MIN_T1_REMAINING_FRAC
    if remaining <= 0 or dist + 1e-9 < need:
        return (
            f"First target is too close to the remaining day range "
            f"({dist:.0f} pts vs {remaining:.0f} pts left)."
        )
    return None


def or_width_hold(opening_range: Optional[Dict[str, Any]], price: Optional[float]) -> Optional[str]:
    """Skip a tiny range (false breaks) and a huge range (stop is too far)."""
    orb = opening_range or {}
    if not orb.get("available") or not price:
        return None
    try:
        width = float(orb["or_high"]) - float(orb["or_low"])
        px = float(price)
    except (TypeError, ValueError, KeyError):
        return None
    if width <= 0 or px <= 0:
        return None
    if width < px * MIN_OR_FRAC:
        return "Opening range is too small — breaks here are often fake."
    if width > px * MAX_OR_FRAC:
        return "Opening range is too wide — the stop would be too far."
    return None


CHASE_OR_MULT = 1.5


def chase_hold(
    decision: str,
    price: Optional[float],
    opening_range: Optional[Dict[str, Any]],
    t1: Optional[float] = None,
    first_clip: bool = False,
    fresh_break: bool = False,
) -> Optional[str]:
    """Skip once price has already run a full clip past the opening-range edge.
    The first break of the day may run; a later add must not chase a 30-pt clip
    40 points past the range (13 Oct 10:49 / 11:39 NIFTY)."""
    if decision in (None, "HOLD") or price is None:
        return None
    orb = opening_range or {}
    if not orb.get("available"):
        return None
    try:
        hi = float(orb["or_high"])
        lo = float(orb["or_low"])
        px = float(price)
    except (TypeError, ValueError, KeyError):
        return None
    width = hi - lo
    if width <= 0:
        return None
    or_limit = CHASE_OR_MULT * width
    clip = None
    try:
        if t1 is not None:
            clip = abs(float(t1) - px)
    except (TypeError, ValueError):
        clip = None
    if not clip or clip < 10:
        clip = 30.0
    limit = or_limit if (first_clip or fresh_break) else min(or_limit, clip)
    if "BUY" in decision and px > hi + limit:
        return "Price already ran a full clip above the opening range — too late to chase."
    if "SELL" in decision and px < lo - limit:
        return "Price already ran a full clip below the opening range — too late to chase."
    return None


def shallow_break_hold(
    decision: str,
    price: Optional[float],
    opening_range: Optional[Dict[str, Any]],
    session_ticket: Optional[Dict[str, Any]] = None,
    asof: Any = None,
) -> Optional[str]:
    """Block a one-tick poke through the opening range (9 Sep / 10 Sep stops).

    persist_new_ticket refuses the ticket when this returns a note. The desk
    also clears the on-screen call so a shallow poke is not shown as live.
    """
    if decision in (None, "HOLD") or price is None:
        return None
    rec = reclaim_decision(session_ticket, opening_range, price, asof=asof)
    if rec and rec in str(decision):
        return None
    orb = opening_range or {}
    if not orb.get("available"):
        return None
    try:
        hi = float(orb["or_high"])
        lo = float(orb["or_low"])
        px = float(price)
    except (TypeError, ValueError, KeyError):
        return None
    width = hi - lo
    if width <= 0:
        return None
    need = MIN_BREAK_EXT * width
    if "BUY" in decision and 0 < (px - hi) < need:
        return "Break above the opening range is too shallow — wait for a closer close outside."
    if "SELL" in decision and 0 < (lo - px) < need:
        return "Break below the opening range is too shallow — wait for a closer close outside."
    return None


def gap_hold(day_range: Optional[Dict[str, Any]], open_price: Optional[float]) -> Optional[str]:
    dr = day_range or {}
    try:
        prev = float(dr.get("reference_prev_close"))
        width = float(dr.get("planned_width"))
        opened = float(open_price)
    except (TypeError, ValueError):
        return None
    if width <= 0:
        return None
    if abs(opened - prev) > 0.5 * width:
        return "The open gap is too large versus the planned day range — skip."
    return None


# A live price this close to the target (versus the stop) has already used the move.
# Last week BHARTIARTL / INFY / TCS printed a target that was already behind the spot.
LIVE_MIN_REWARD_RISK = 0.65


def levels_on_side(
    decision: str,
    entry: Any,
    stop_loss: Any,
    target_1: Any,
) -> bool:
    """BUY needs stop below entry and target above. SELL is the reverse."""
    if decision in (None, "HOLD"):
        return False
    try:
        px = float(entry)
        sl = float(stop_loss)
        t1 = float(target_1)
    except (TypeError, ValueError):
        return False
    if px <= 0:
        return False
    if "SELL" in str(decision):
        return t1 < px < sl
    if "BUY" in str(decision):
        return sl < px < t1
    return False


def _risk_reward(decision: str, price: float, stop_loss: float, target_1: float) -> Tuple[float, float]:
    if "SELL" in str(decision):
        return float(stop_loss) - price, price - float(target_1)
    return price - float(stop_loss), float(target_1) - price


def reward_risk_hold(
    decision: str,
    price: Optional[float],
    stop_loss: Optional[float],
    target_1: Optional[float],
) -> Optional[str]:
    if decision in (None, "HOLD") or price is None or stop_loss is None or target_1 is None:
        return None
    if not levels_on_side(decision, price, stop_loss, target_1):
        return "Stop or target is on the wrong side of the live price — skip."
    risk, reward = _risk_reward(decision, float(price), float(stop_loss), float(target_1))
    if risk <= 0 or reward + 1e-9 < risk * MIN_REWARD_RISK:
        return f"Target ({reward:.0f} pts) is smaller than the stop ({risk:.0f} pts) — skip."
    return None


def live_room_hold(
    decision: str,
    price: Optional[float],
    stop_loss: Optional[float],
    target_1: Optional[float],
) -> Optional[str]:
    """Reject a ticket the live price has already run through, or nearly so."""
    if decision in (None, "HOLD") or price is None or stop_loss is None or target_1 is None:
        return None
    if not levels_on_side(decision, price, stop_loss, target_1):
        return "Stop or target is on the wrong side of the live price — skip."
    risk, reward = _risk_reward(decision, float(price), float(stop_loss), float(target_1))
    if risk <= 0 or reward + 1e-9 < risk * LIVE_MIN_REWARD_RISK:
        return (
            f"Live price is too close to the target ({reward:.0f} pts left, stop is {risk:.0f} pts) — skip."
        )
    return None


def same_side_fade_hold(
    decision: str,
    session_ticket: Optional[Dict[str, Any]],
    price: Optional[float],
) -> Optional[str]:
    """Do not buy again once the whole move has been given back — price is back
    past the *entry* of the ticket that just paid. A pullback that only retraces
    the booked target is normal trend behaviour: holding on that blocked 9
    winners for 1 loser (Sep 21 - Oct 12 replay)."""
    if decision in (None, "HOLD") or not session_ticket or price is None:
        return None
    if last_closed_status(session_ticket) != "t1_before_sl":
        return None
    last = last_closed_decision(session_ticket) or ""
    same = ("BUY" in str(decision) and "BUY" in last) or ("SELL" in str(decision) and "SELL" in last)
    if not same:
        return None
    hist = list(session_ticket.get("history") or [])
    prev = hist[-1] if hist else {}
    ref = prev.get("entry")
    if ref is None:
        ref = prev.get("target_1")
    try:
        booked = float(ref)
        px = float(price)
    except (TypeError, ValueError):
        return None
    if "BUY" in str(decision) and px < booked:
        return "Price has given back the whole move since the last buy paid. No second buy from here."
    if "SELL" in str(decision) and px > booked:
        return "Price has given back the whole move since the last sell paid. No second sell from here."
    return None


def same_side_reentry_hold(
    decision: str,
    session_ticket: Optional[Dict[str, Any]],
    p_t1: Any = None,
    fresh_break: bool = False,
) -> Optional[str]:
    """After any closed ticket, the same direction needs the full 58% bar, not
    the eased first-break one — unless the tape prints a fresh OR break."""
    if fresh_break:
        return None
    if decision in (None, "HOLD") or not session_ticket:
        return None
    if closed_ticket_count(session_ticket) < 1:
        return None
    last = last_closed_decision(session_ticket) or ""
    same = ("BUY" in str(decision) and "BUY" in last) or ("SELL" in str(decision) and "SELL" in last)
    if not same:
        return None
    try:
        p = float(p_t1)
    except (TypeError, ValueError):
        p = 0.0
    if p + 1e-9 < SAME_SIDE_REENTRY_P:
        return (
            f"Same direction again needs at least a {SAME_SIDE_REENTRY_P:.0%} chance of the target. "
            f"This one is {p:.0%}."
        )
    return None


MAX_SAME_SIDE_STOPS = 2


def same_side_stop_count(session_ticket: Optional[Dict[str, Any]], decision: str) -> int:
    """How many tickets in this direction have already hit the stop today."""
    if not session_ticket:
        return 0
    want = "BUY" if "BUY" in str(decision) else ("SELL" if "SELL" in str(decision) else "")
    if not want:
        return 0
    n = 0
    for tk in list(session_ticket.get("history") or []):
        if want in str(tk.get("decision") or "") and str(tk.get("status") or "") in ("sl_before_t1", "same_bar_both"):
            n += 1
    if str(session_ticket.get("status") or "") in ("sl_before_t1", "same_bar_both") and want in str(
        session_ticket.get("decision") or last_closed_decision(session_ticket) or ""
    ):
        n = max(n, 1)
    return n


def same_side_after_stop_hold(
    decision: str,
    session_ticket: Optional[Dict[str, Any]],
) -> Optional[str]:
    """One retry after a stop is allowed when a later bar actually closes that way.
    The third try on that side is not. 30 Sep NIFTY bought twice and lost twice."""
    if decision in (None, "HOLD") or not session_ticket:
        return None
    if same_side_stop_count(session_ticket, decision) >= MAX_SAME_SIDE_STOPS:
        return (
            f"{MAX_SAME_SIDE_STOPS} stops already in this direction today. "
            "Higher risk on another try — the call is still shown."
        )
    return None


def safety_entry_alerts(
    decision: str,
    *,
    session_ticket: Optional[Dict[str, Any]] = None,
    opening_range: Optional[Dict[str, Any]] = None,
    price: Optional[float] = None,
    t1: Optional[float] = None,
    p_t1: Any = None,
    fresh_break: bool = False,
    asof: Any = None,
) -> list:
    """Risk notes for a model call. None of these hide the live desk call."""
    if decision in (None, "HOLD"):
        return []
    rec = reclaim_decision(session_ticket, opening_range, price, asof=asof)
    if rec and rec in str(decision):
        return []
    notes: list = []
    for fn in (
        lambda: same_side_after_stop_hold(decision, session_ticket),
        lambda: same_side_fade_hold(decision, session_ticket, price),
        lambda: same_side_reentry_hold(decision, session_ticket, p_t1, fresh_break=fresh_break),
        lambda: chase_hold(
            decision,
            price,
            opening_range,
            t1=t1,
            first_clip=is_first_clip(session_ticket),
            fresh_break=fresh_break,
        ),
    ):
        msg = fn()
        if msg and msg not in notes:
            notes.append(msg)
    return notes


def safety_entry_hold(
    decision: str,
    *,
    session_ticket: Optional[Dict[str, Any]] = None,
    opening_range: Optional[Dict[str, Any]] = None,
    price: Optional[float] = None,
    t1: Optional[float] = None,
    p_t1: Any = None,
    fresh_break: bool = False,
    asof: Any = None,
) -> Optional[str]:
    """Replay-only first safety note. Live desk uses safety_entry_alerts()."""
    alerts = safety_entry_alerts(
        decision,
        session_ticket=session_ticket,
        opening_range=opening_range,
        price=price,
        t1=t1,
        p_t1=p_t1,
        fresh_break=fresh_break,
        asof=asof,
    )
    return alerts[0] if alerts else None


def apply_session_holds(
    decision: str,
    *,
    asof: Any = None,
    session_ticket: Optional[Dict[str, Any]] = None,
    opening_range: Optional[Dict[str, Any]] = None,
    price: Optional[float] = None,
    t1: Optional[float] = None,
    stop_loss: Optional[float] = None,
    day_range: Optional[Dict[str, Any]] = None,
    open_price: Optional[float] = None,
    p_t1: Any = None,
    fresh_break: bool = False,
    expiry_day: bool = False,
    other_index_decision: Optional[str] = None,
) -> Optional[str]:
    """Strict replay mode only. The live desk uses desk_alerts(): nothing here
    hides a call on screen. Expiry and the clock are never holds."""
    if decision in (None, "HOLD"):
        return None
    opening = in_opening_call_window(asof)
    for fn in (
        lambda: _event_hold(asof),
        lambda: cross_index_hold(decision, other_index_decision),
        lambda: session_cap_hold(session_ticket, asof),
        lambda: None if opening else gap_hold(day_range, open_price),
        lambda: None if opening else or_width_hold(opening_range, price),
        lambda: None if opening else or_gate_hold(decision, opening_range, session_ticket, price, asof=asof),
        lambda: shallow_break_hold(decision, price, opening_range, session_ticket, asof=asof),
        lambda: chase_hold(decision, price, opening_range),
        lambda: same_side_after_stop_hold(decision, session_ticket),
        lambda: same_side_fade_hold(decision, session_ticket, price),
        lambda: same_side_reentry_hold(decision, session_ticket, p_t1, fresh_break=fresh_break),
        lambda: t1_room_hold(decision, float(price or 0), t1, day_range) if price and t1 is not None else None,
        lambda: reward_risk_hold(decision, price, stop_loss, t1),
    ):
        msg = fn()
        if msg:
            return msg
    return None


def desk_alerts(
    decision: str,
    *,
    asof: Any = None,
    session_ticket: Optional[Dict[str, Any]] = None,
    opening_range: Optional[Dict[str, Any]] = None,
    price: Optional[float] = None,
    t1: Optional[float] = None,
    stop_loss: Optional[float] = None,
    day_range: Optional[Dict[str, Any]] = None,
    open_price: Optional[float] = None,
    p_t1: Any = None,
    fresh_break: bool = False,
    expiry_day: bool = False,
    other_index_decision: Optional[str] = None,
    regime: Any = None,
    or_ext: Any = None,
    delta_proxy: Any = None,
    atr_frac: Any = None,
    direction_ok: bool = True,
    soft_direction: bool = True,
) -> list:
    """Risk notes for a call that already passed the model. None of these hide it."""
    if decision in (None, "HOLD"):
        return []
    notes = []
    chase_msg = chase_hold(
        decision,
        price,
        opening_range,
        t1=t1,
        first_clip=is_first_clip(session_ticket),
        fresh_break=fresh_break,
    )
    for fn in (
        lambda: clock_alert(asof),
        lambda: _event_hold(asof),
        lambda: expiry_open_hold(expiry_day, fresh_break),
        lambda: cross_index_hold(decision, other_index_decision),
        lambda: session_cap_hold(session_ticket, asof),
        lambda: gap_hold(day_range, open_price),
        lambda: or_width_hold(opening_range, price),
        lambda: or_gate_hold(decision, opening_range, session_ticket, price, asof=asof),
        lambda: shallow_break_hold(decision, price, opening_range, session_ticket, asof=asof),
        lambda: chase_msg,
        lambda: same_side_after_stop_hold(decision, session_ticket),
        lambda: same_side_fade_hold(decision, session_ticket, price),
        lambda: same_side_reentry_hold(decision, session_ticket, p_t1, fresh_break=fresh_break),
        lambda: t1_room_hold(decision, float(price or 0), t1, day_range) if price and t1 is not None else None,
        lambda: reward_risk_hold(decision, price, stop_loss, t1),
    ):
        msg = fn()
        if msg and msg not in notes:
            notes.append(msg)
    # PDF accuracy alerts (Varsity/Cboe/IISc) — prior-30 validation language
    try:
        import fno_pdf_accuracy

        try:
            score = float(p_t1) if p_t1 is not None else 0.0
        except (TypeError, ValueError):
            score = 0.0
        reg = regime
        if isinstance(regime, dict):
            reg = regime.get("name") or regime.get("regime")
        for msg in fno_pdf_accuracy.accuracy_alerts(
            score=score,
            decision=str(decision),
            regime=str(reg) if reg is not None else None,
            first_break=bool(fresh_break),
            chase=bool(chase_msg),
            or_ext=float(or_ext) if or_ext is not None else None,
            direction_ok=bool(direction_ok),
            soft_direction=bool(soft_direction),
            delta_proxy=float(delta_proxy) if delta_proxy is not None else None,
            atr_frac=float(atr_frac) if atr_frac is not None else None,
            asof=asof,
        ):
            if msg not in notes:
                notes.append(msg)
    except Exception:
        pass
    return notes
