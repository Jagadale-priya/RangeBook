"""Point journal for finished 15-minute bars.

A close outside the opening range is written as a suggestion: entry, the clip,
and whether +20, +50, or +100 points print before -20. Thirty minutes after
that bar ends, the later tape fills in what happened. Nothing here is a call,
and nothing here retrains the live model.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import timedelta
from typing import Any, Dict, List, Optional

HORIZON_MINUTES = 30
BAR_MINUTES = 15
FAVOR_POINTS = (20, 50, 100)
ADVERSE_POINTS = 20


def ensure_tables(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fno_point_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock TEXT NOT NULL,
                session_date TEXT NOT NULL,
                bar_ts TEXT NOT NULL,
                decision TEXT NOT NULL,
                entry REAL NOT NULL,
                stop_loss REAL,
                target_1 REAL,
                p_t1 REAL,
                horizon_min INTEGER NOT NULL,
                status TEXT NOT NULL,
                favor_points REAL,
                adverse_points REAL,
                outcome_json TEXT,
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                UNIQUE(stock, session_date, bar_ts)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def update_journal(
    db_path: str,
    stock: str,
    bars_15m: Any,
    bars_5m: Any = None,
    *,
    asof: Any = None,
    p_t1: Any = None,
) -> Dict[str, Any]:
    """Record the latest finished outside bar and resolve rows whose 30 minutes are over."""
    ensure_tables(db_path)
    now = _as_ist(asof) if asof is not None else _now()
    key = str(stock or "").strip().upper()
    recorded = _record_latest(db_path, key, bars_15m, now, p_t1)
    resolved = _resolve_due(db_path, key, bars_5m if bars_5m is not None else bars_15m, now)
    latest = latest_today(db_path, key, now)
    return {"recorded": recorded, "resolved": resolved, "latest": latest}


def attach(result: Dict[str, Any], stock: str, bars_15m: Any, bars_5m: Any = None, fno_head: Any = None) -> None:
    """Store the forecast and put the latest row on the response. Failures stay off the call."""
    try:
        import session_calls

        score = fno_head.get("p_t1") if isinstance(fno_head, dict) else None
        journal = update_journal(
            session_calls.default_db_path(),
            stock,
            bars_15m,
            bars_5m,
            p_t1=score,
        )
    except Exception:
        return
    latest = journal.get("latest")
    result["point_journal"] = latest
    fa = result.get("fno_analysis")
    if isinstance(fa, dict):
        fa["point_journal"] = latest


def latest_today(db_path: str, stock: str, asof: Any = None) -> Optional[Dict[str, Any]]:
    if not db_path or not os.path.isfile(db_path):
        return None
    now = _as_ist(asof) if asof is not None else _now()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT * FROM fno_point_journal
            WHERE stock = ? AND session_date = ?
            ORDER BY bar_ts DESC LIMIT 1
            """,
            (str(stock or "").strip().upper(), str(now.date())),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
    return _public_row(row) if row else None


def walk_points(
    bars: Any,
    *,
    entry: float,
    decision: str,
    signal_end: Any,
    horizon_end: Any,
) -> Dict[str, Any]:
    """How far price went, and which point printed first, inside the window."""
    work = _finished_frame(bars)
    favor = 0.0
    adverse = 0.0
    hit = {pts: None for pts in FAVOR_POINTS}
    if work is None or not len(work):
        return _walk_result(favor, adverse, hit)
    high_col, low_col = _hl(work)
    start = _as_ist(signal_end)
    end = _as_ist(horizon_end)
    bull = "BUY" in str(decision)
    for ts, row in work.iterrows():
        bar_start = _as_ist(ts)
        if bar_start < start or bar_start >= end:
            continue
        high = float(row[high_col])
        low = float(row[low_col])
        up = high - entry
        down = entry - low
        bar_favor = up if bull else down
        bar_adverse = down if bull else up
        favor = max(favor, bar_favor)
        adverse = max(adverse, bar_adverse)
        adverse_hit = bar_adverse + 1e-9 >= ADVERSE_POINTS
        for pts in FAVOR_POINTS:
            if hit[pts] is not None:
                continue
            favor_hit = bar_favor + 1e-9 >= pts
            if favor_hit and adverse_hit:
                hit[pts] = "same_bar"
            elif favor_hit:
                hit[pts] = "favor"
            elif adverse_hit:
                hit[pts] = "adverse"
    return _walk_result(favor, adverse, hit)


def _record_latest(db_path: str, stock: str, bars_15m: Any, now, p_t1: Any) -> bool:
    work = _drop_unfinished(bars_15m, now, BAR_MINUTES)
    if work is None or not len(work):
        return False
    today = _session(work, now)
    if today is None or len(today) < 1:
        return False
    or_high, or_low = _or_bounds(today)
    if or_high is None or or_high <= or_low:
        return False
    close_col = _col(today, "close")
    last_ts = today.index[-1]
    close = float(today[close_col].iloc[-1])
    if close > or_high:
        decision = "BUY"
    elif close < or_low:
        decision = "SELL"
    else:
        return False
    bar_end = _as_ist(last_ts) + timedelta(minutes=BAR_MINUTES)
    if bar_end > now:
        return False
    try:
        import fno_risk_engine

        sl_pts, t1_pts, _t2, _name = fno_risk_engine.clip_points(stock, close)
        stop = round(close - sl_pts, 2) if decision == "BUY" else round(close + sl_pts, 2)
        target = round(close + t1_pts, 2) if decision == "BUY" else round(close - t1_pts, 2)
    except Exception:
        stop = None
        target = None
    score = None
    try:
        if p_t1 is not None:
            score = round(float(p_t1), 4)
    except (TypeError, ValueError):
        score = None
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO fno_point_journal (
                stock, session_date, bar_ts, decision, entry, stop_loss, target_1,
                p_t1, horizon_min, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
            """,
            (
                stock,
                str(now.date()),
                _as_ist(last_ts).isoformat(),
                decision,
                round(close, 2),
                stop,
                target,
                score,
                HORIZON_MINUTES,
                now.isoformat(),
            ),
        )
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def _resolve_due(db_path: str, stock: str, bars: Any, now) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, bar_ts, decision, entry FROM fno_point_journal
            WHERE stock = ? AND status = 'open' AND session_date = ?
            """,
            (stock, str(now.date())),
        ).fetchall()
    finally:
        conn.close()
    done = 0
    for row in rows:
        start = _as_ist(row["bar_ts"])
        signal_end = start + timedelta(minutes=BAR_MINUTES)
        horizon_end = signal_end + timedelta(minutes=HORIZON_MINUTES)
        if now < horizon_end:
            continue
        outcome = walk_points(
            bars,
            entry=float(row["entry"]),
            decision=row["decision"],
            signal_end=signal_end,
            horizon_end=horizon_end,
        )
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                UPDATE fno_point_journal
                SET status = 'resolved', favor_points = ?, adverse_points = ?,
                    outcome_json = ?, resolved_at = ?
                WHERE id = ?
                """,
                (
                    outcome["favor_points"],
                    outcome["adverse_points"],
                    json.dumps(outcome),
                    now.isoformat(),
                    row["id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
        done += 1
    return done


def _public_row(row: sqlite3.Row) -> Dict[str, Any]:
    outcome = {}
    if row["outcome_json"]:
        try:
            outcome = json.loads(row["outcome_json"])
        except (TypeError, ValueError):
            outcome = {}
    return {
        "stock": row["stock"],
        "session_date": row["session_date"],
        "bar_ts": row["bar_ts"],
        "decision": row["decision"],
        "entry": row["entry"],
        "stop_loss": row["stop_loss"],
        "target_1": row["target_1"],
        "p_t1": row["p_t1"],
        "horizon_min": row["horizon_min"],
        "status": row["status"],
        "favor_points": row["favor_points"],
        "adverse_points": row["adverse_points"],
        "checks": outcome.get("checks") or {},
        "message": _message(row, outcome),
    }


def _message(row: sqlite3.Row, outcome: Dict[str, Any]) -> str:
    clock = str(row["bar_ts"])[11:16]
    base = (
        f"Point check {clock} {row['decision']} at {row['entry']}. "
        f"Watching +20, +50, and +100 before -20 for {row['horizon_min']} minutes. "
        "Not a listed call."
    )
    if row["status"] != "resolved":
        return base
    checks = outcome.get("checks") or {}
    parts = [f"+{pts} {checks.get(str(pts)) or checks.get(pts) or 'open'}" for pts in FAVOR_POINTS]
    return (
        f"Point check {clock} {row['decision']} at {row['entry']} resolved. "
        + ", ".join(parts)
        + f". Best {row['favor_points']} in favor, worst {row['adverse_points']} against. "
        "Not a listed call."
    )


def _walk_result(favor: float, adverse: float, hit: Dict[int, Optional[str]]) -> Dict[str, Any]:
    checks = {}
    for pts, value in hit.items():
        checks[str(pts)] = value or "neither"
    return {
        "favor_points": round(favor, 2),
        "adverse_points": round(adverse, 2),
        "checks": checks,
    }


def _now():
    import market_symbols

    return _as_ist(market_symbols.ist_now())


def _as_ist(ts):
    import pandas as pd

    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is None:
        return stamp.tz_localize("Asia/Kolkata")
    return stamp.tz_convert("Asia/Kolkata")


def _col(frame, name: str) -> str:
    for col in frame.columns:
        if str(col).lower() == name:
            return col
    raise KeyError(name)


def _hl(frame):
    return _col(frame, "high"), _col(frame, "low")


def _finished_frame(bars: Any):
    if bars is None:
        return None
    try:
        if len(bars) == 0:
            return None
    except TypeError:
        return None
    return bars


def _drop_unfinished(bars: Any, now, minutes: int):
    work = _finished_frame(bars)
    if work is None:
        return None
    end = _as_ist(now)
    keep: List[Any] = []
    for ts in work.index:
        if _as_ist(ts) + timedelta(minutes=minutes) <= end:
            keep.append(ts)
    if not keep:
        return work.iloc[0:0]
    return work.loc[keep]


def _session(work, now):
    day = _as_ist(now).date()
    mask = [_as_ist(ts).date() == day for ts in work.index]
    today = work.loc[mask]
    return today if len(today) else None


def _or_bounds(today):
    high_col, low_col = _hl(today)
    return float(today[high_col].iloc[0]), float(today[low_col].iloc[0])
