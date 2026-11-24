"""Track checklist+candle suggestions and resolve them against the tape.

Suggestions stay off the call list. This module only records whether the clip
reached the target before the stop, so the Predictions tab can show accuracy.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

import fno_model
import session_calls

TABLE = """
CREATE TABLE IF NOT EXISTS fno_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock TEXT NOT NULL,
    session_date TEXT NOT NULL,
    bar_ts TEXT NOT NULL,
    decision TEXT NOT NULL,
    entry REAL NOT NULL,
    stop_loss REAL NOT NULL,
    target_1 REAL NOT NULL,
    candle_bias TEXT,
    ema_lean TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    points REAL,
    resolved_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(stock, session_date, bar_ts)
)
"""


def _conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or session_calls.default_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(TABLE)
    return conn


def _as_ist(ts: Any):
    import pandas as pd

    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is None:
        return stamp.tz_localize("Asia/Kolkata")
    return stamp.tz_convert("Asia/Kolkata")


def record_suggestion(
    stock: str,
    suggestion: Dict[str, Any],
    *,
    db_path: Optional[str] = None,
    asof: Any = None,
) -> None:
    if not isinstance(suggestion, dict) or suggestion.get("decision") not in ("BUY", "SELL"):
        return
    try:
        entry = float(suggestion["entry"])
        stop = float(suggestion["stop_loss"])
        target = float(suggestion["target_1"])
    except (KeyError, TypeError, ValueError):
        return
    when = _as_ist(suggestion.get("bars_asof") or asof or datetime.now())
    session_date = str(when.date())
    bar_ts = when.isoformat()
    now = datetime.now().astimezone().isoformat()
    conn = _conn(db_path)
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO fno_predictions
            (stock, session_date, bar_ts, decision, entry, stop_loss, target_1,
             candle_bias, ema_lean, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
            """,
            (
                str(stock).upper(),
                session_date,
                bar_ts,
                suggestion["decision"],
                entry,
                stop,
                target,
                suggestion.get("candle_bias"),
                suggestion.get("ema_lean"),
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def resolve_open(
    stock: str,
    bars: Any,
    *,
    db_path: Optional[str] = None,
    asof: Any = None,
) -> int:
    if bars is None:
        return 0
    try:
        if len(bars) == 0:
            return 0
    except TypeError:
        return 0
    now = _as_ist(asof or datetime.now())
    conn = _conn(db_path)
    resolved = 0
    try:
        rows = conn.execute(
            """
            SELECT id, decision, entry, stop_loss, target_1, bar_ts
            FROM fno_predictions
            WHERE stock=? AND status='open'
            ORDER BY bar_ts
            """,
            (str(stock).upper(),),
        ).fetchall()
        for row in rows:
            start = _as_ist(row["bar_ts"])
            future = bars[bars.index.map(lambda ts: _as_ist(ts) > start)]
            if future is None or not len(future):
                # Keep open until the session has more tape, then expire next day.
                if now.date() > start.date() and now.hour >= 15:
                    conn.execute(
                        "UPDATE fno_predictions SET status='expired', resolved_at=?, points=0 WHERE id=?",
                        (now.isoformat(), row["id"]),
                    )
                    resolved += 1
                continue
            outcome, _ = fno_model._clip_resolution(
                future,
                row["decision"] == "SELL",
                float(row["stop_loss"]),
                float(row["target_1"]),
            )
            if outcome == "t1_before_sl":
                points = abs(float(row["target_1"]) - float(row["entry"]))
                status = "hit_target"
            elif outcome in ("sl_before_t1", "same_bar_both"):
                points = -abs(float(row["entry"]) - float(row["stop_loss"]))
                status = "hit_stop"
            else:
                if now.date() > start.date() and now.hour >= 15:
                    points = 0.0
                    status = "expired"
                else:
                    continue
            conn.execute(
                "UPDATE fno_predictions SET status=?, points=?, resolved_at=? WHERE id=?",
                (status, float(points), now.isoformat(), row["id"]),
            )
            resolved += 1
        conn.commit()
    finally:
        conn.close()
    return resolved


def accuracy(
    stock: str,
    *,
    db_path: Optional[str] = None,
    limit: int = 40,
) -> Dict[str, Any]:
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """
            SELECT session_date, bar_ts, decision, entry, stop_loss, target_1,
                   candle_bias, ema_lean, status, points, resolved_at
            FROM fno_predictions
            WHERE stock=?
            ORDER BY bar_ts DESC
            LIMIT ?
            """,
            (str(stock).upper(), int(limit)),
        ).fetchall()
        recent = [dict(r) for r in rows]
        closed = [r for r in recent if r["status"] in ("hit_target", "hit_stop")]
        wins = sum(1 for r in closed if r["status"] == "hit_target")
        stops = sum(1 for r in closed if r["status"] == "hit_stop")
        points = sum(float(r["points"] or 0) for r in closed)
        hit_rate = round(100.0 * wins / len(closed), 1) if closed else None
        return {
            "available": True,
            "stock": str(stock).upper(),
            "total": len(recent),
            "resolved": len(closed),
            "hit_target": wins,
            "hit_stop": stops,
            "hit_rate": hit_rate,
            "points": round(points, 1),
            "open": sum(1 for r in recent if r["status"] == "open"),
            "recent": recent,
            "rule": (
                "Live finished 15m candlestick patterns (engulfing, harami, "
                "shooting star, gravestone, belt hold, stick sandwich, three "
                "line strike, homing pigeon) with matching 9/20 EMA lean. "
                "No opening-range break required."
            ),
        }
    finally:
        conn.close()


def attach(
    result: Dict[str, Any],
    stock: str,
    bars: Any,
    suggestion: Optional[Dict[str, Any]] = None,
    *,
    asof: Any = None,
) -> Dict[str, Any]:
    try:
        card = suggestion if suggestion is not None else result.get("suggestion")
        if isinstance(card, dict):
            record_suggestion(stock, card, asof=asof)
        resolve_open(stock, bars, asof=asof)
        stats = accuracy(stock)
        result["predictions"] = stats
        fa = result.get("fno_analysis")
        if isinstance(fa, dict):
            fa["predictions"] = stats
        return stats
    except Exception:
        return {"available": False}
