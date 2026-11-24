"""Point-in-time NIFTY tape validation. Kite candle timestamps are bar starts."""
from __future__ import annotations

import hashlib
from datetime import time, timedelta

import numpy as np
import pandas as pd

IST = "Asia/Kolkata"
MIN_DEEP_HISTORY_SESSIONS = 1000
MIN_DEEP_HISTORY_YEARS = 4.5

# Exchange-announced short sessions inside the current five-year training
# window.  Keep exact schedules here so an arbitrary partial day never passes
# merely because it occurred on a weekend or started outside normal hours.
SPECIAL_SESSION_TIMES = {
    "2024-03-02": ("09:15", "09:30", "09:45", "11:30", "11:45", "12:00", "12:15"),
    "2024-05-18": ("09:15", "09:30", "09:45", "11:30", "11:45", "12:00", "12:15"),
    "2025-10-21": ("13:45", "14:00", "14:15", "14:30"),
}


def timestamp(value=None):
    ts = pd.Timestamp.now(tz=IST) if value is None else pd.Timestamp(value)
    return ts.tz_localize(IST) if ts.tzinfo is None else ts.tz_convert(IST)


def normalize(frame):
    """Canonical OHLCV, sorted and deduplicated; never invent missing prices."""
    if frame is None or not len(frame):
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    out = pd.DataFrame(index=pd.DatetimeIndex(frame.index))
    out.index = out.index.tz_localize(IST) if out.index.tz is None else out.index.tz_convert(IST)
    for name in ("Open", "High", "Low", "Close", "Volume"):
        cols = [c for c in frame.columns if str(c).lower() == name.lower()]
        values = pd.to_numeric(frame[cols[0]], errors="coerce") if cols else pd.Series(np.nan, index=frame.index)
        for col in cols[1:]:
            values = values.fillna(pd.to_numeric(frame[col], errors="coerce"))
        out[name] = values.to_numpy()
    out["Volume"] = out["Volume"].fillna(0).clip(lower=0)
    valid = np.isfinite(out[["Open", "High", "Low", "Close"]]).all(axis=1)
    valid &= out["Low"].gt(0) & out["High"].ge(out[["Open", "Close", "Low"]].max(axis=1))
    valid &= out["Low"].le(out[["Open", "Close"]].min(axis=1))
    out = out.loc[valid]
    return out.loc[~out.index.duplicated(keep="last")].sort_index()


def completed(frame, asof=None, minutes=15):
    out = normalize(frame)
    return out.loc[out.index + timedelta(minutes=int(minutes)) <= timestamp(asof)]


def quote_fresh(quote, asof=None, max_age_seconds=30):
    if not isinstance(quote, dict):
        return False
    if str(quote.get("feed_type") or "").lower() == "delayed_quote" or str(quote.get("source") or "").lower() == "yahoo":
        return False
    try:
        if quote.get("staleness_ms") is not None and float(quote["staleness_ms"]) > max_age_seconds * 1000:
            return False
    except (TypeError, ValueError):
        return False
    # REST quotes must carry an exchange stamp. Fetch-time received_at alone
    # always looks "fresh" and hid after-hours / hung last_price values.
    stamp = quote.get("exchange_timestamp") or quote.get("exchange_timestamp_utc")
    feed = str(quote.get("feed_type") or "").lower()
    source = str(quote.get("source") or "").lower()
    if source == "replay" or feed == "replay":
        try:
            price = float(quote.get("last_price") or 0)
        except (TypeError, ValueError):
            return False
        return np.isfinite(price) and price > 0
    if stamp is None and (feed.startswith("websocket") or source in ("kite_ws", "websocket")):
        stamp = quote.get("received_at_ist") or quote.get("updated_at_ist")
    try:
        age = (timestamp(asof) - timestamp(stamp)).total_seconds() if stamp else float("inf")
        price = float(quote.get("last_price") or 0)
        return np.isfinite(price) and price > 0 and -2 <= age <= max_age_seconds
    except (ValueError, TypeError):
        return False


def entry_issue(bars, quote, asof=None, *, allow_dual_lag: bool = False):
    """Reject new NIFTY entries on bad/stale tape.

    Dual-track listings already scored on this session tape. For those, allow a
    modest quote/tape lag so background refresh can list NIFTY the same way
    BANKNIFTY/SENSEX do (they have no equivalent freshness gate). Structural
    checks (session hours, opening candle, gaps) still apply.
    """
    now = timestamp(asof)
    if now.weekday() >= 5 or not time(9, 30) <= now.time() < time(15, 15):
        return "New NIFTY calls are available from 09:30 until 15:15 IST."
    # Core path: a failed 15m refresh must not open a new call. Dual-track may
    # still list from a complete cached tape (BN/Sensex have no such gate).
    if (
        isinstance(quote, dict)
        and quote.get("history_refresh_failed")
        and not allow_dual_lag
    ):
        return "Waiting for current completed NIFTY candles."
    # Dual-track already scored on this tape (same independence as BN/Sensex).
    # Do not require a live quote — missing LTP was silently blocking NIFTY lists
    # while BANKNIFTY/SENSEX still listed from the same refresh cycle.
    if not allow_dual_lag and not quote_fresh(quote, now):
        return "Waiting for a fresh NIFTY quote."
    if bars is None or getattr(bars, "empty", len(bars) == 0 if hasattr(bars, "__len__") else True):
        # Dual persist skips this gate entirely; if called with no tape, don't
        # invent a quote failure — ask for candles only on the core path.
        if allow_dual_lag:
            return None
        return "Waiting for today's completed opening candle."
    tape = completed(bars, now)
    today = tape.loc[tape.index.date == now.date()]
    if today.empty or today.index[0].time() != time(9, 15):
        return "Waiting for today's completed opening candle."
    if not allow_dual_lag:
        age = (now - (today.index[-1] + timedelta(minutes=15))).total_seconds()
        # Core path only: ≤16m. Dual path skips tape-age (BN/Sensex have no age gate).
        if age > 16 * 60:
            return "Waiting for current completed NIFTY candles."
    if len(today) > 1 and (today.index.to_series().diff().dropna() != timedelta(minutes=15)).any():
        return "NIFTY intraday candles have a gap; refresh the tape."
    return None


def audit(frame):
    tape = normalize(frame)
    days = sorted(set(tape.index.date))
    gaps = [{"after": str(a), "before": str(b), "calendar_days": (b - a).days}
            for a, b in zip(days, days[1:]) if (b - a).days > 7]
    bad_sessions = []
    special_sessions = []
    for day, session in tape.groupby(tape.index.date):
        actual_times = tuple(stamp.strftime("%H:%M") for stamp in session.index)
        special_times = SPECIAL_SESSION_TIMES.get(str(day))
        if special_times and actual_times == special_times:
            special_sessions.append(str(day))
            continue
        # NSE Muhurat sessions are intentionally short evening sessions. They
        # are retained for provenance but are not missing daytime data.
        if len(session) and session.index[0].time() >= time(17, 0):
            continue
        expected = pd.date_range(f"{day} 09:15", periods=25, freq="15min", tz=IST)
        if not session.index.equals(expected):
            bad_sessions.append(str(day))
    digest = hashlib.sha256(pd.util.hash_pandas_object(tape, index=True).values.tobytes()).hexdigest()
    span_years = (
        float((tape.index[-1] - tape.index[0]).total_seconds() / (365.25 * 86400))
        if len(tape) > 1 else 0.0
    )
    integrity_ok = bool(len(days) >= 120 and not gaps and not bad_sessions)
    deep_history_ok = bool(
        integrity_ok
        and len(days) >= MIN_DEEP_HISTORY_SESSIONS
        and span_years >= MIN_DEEP_HISTORY_YEARS
    )
    return {"rows_input": len(frame) if frame is not None else 0, "rows_valid": len(tape),
            "sessions": len(days), "first": str(tape.index[0]) if len(tape) else None,
            "last": str(tape.index[-1]) if len(tape) else None, "long_gaps": gaps,
            "incomplete_sessions": bad_sessions, "special_sessions": special_sessions,
            "sha256": digest,
            "span_years": round(span_years, 4),
            "zero_volume_fraction": float(tape.Volume.eq(0).mean()) if len(tape) else None,
            "promotion_data_ok": integrity_ok,
            "deep_history_ok": deep_history_ok,
            "deep_history_min_sessions": MIN_DEEP_HISTORY_SESSIONS,
            "deep_history_min_years": MIN_DEEP_HISTORY_YEARS}
