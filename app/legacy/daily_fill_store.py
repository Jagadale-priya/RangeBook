"""Independent SQLite store for daily_fill channel (up to K calls/day).

Parallel to dual-track / 5m crown / 15m classic — never touches those tables.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional


def default_db_path() -> str:
    import knowledge_db

    return knowledge_db.ensure_db_dir()


def _migrate_calls_to_k2(conn: sqlite3.Connection) -> None:
    """Relax UNIQUE(stock, session_date) → UNIQUE(stock, session_date, bar_time)."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='daily_fill_calls'"
    ).fetchone()
    if not row or not row[0]:
        return
    sql = str(row[0])
    if "UNIQUE(stock, session_date, bar_time)" in sql.replace(" ", ""):
        return
    if "UNIQUE(stock, session_date)" not in sql.replace(" ", "") and "UNIQUE (stock, session_date)" not in sql:
        # already no day-unique, or custom — still ensure bar_time unique index
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_daily_fill_bar "
            "ON daily_fill_calls(stock, session_date, bar_time)"
        )
        return
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS daily_fill_calls_k2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock TEXT NOT NULL,
            session_date TEXT NOT NULL,
            bar_time TEXT NOT NULL,
            decision TEXT NOT NULL,
            status TEXT NOT NULL,
            entry REAL,
            stop_loss REAL,
            target_1 REAL,
            p_t1 REAL,
            track TEXT,
            fill_used INTEGER NOT NULL DEFAULT 0,
            accuracy_label TEXT,
            tags_json TEXT,
            payload_json TEXT,
            taken_at TEXT,
            closed_at TEXT,
            notify_sent INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(stock, session_date, bar_time)
        );
        INSERT OR IGNORE INTO daily_fill_calls_k2 (
            id, stock, session_date, bar_time, decision, status,
            entry, stop_loss, target_1, p_t1, track, fill_used,
            accuracy_label, tags_json, payload_json, taken_at, closed_at,
            notify_sent, created_at, updated_at
        )
        SELECT
            id, stock, session_date, bar_time, decision, status,
            entry, stop_loss, target_1, p_t1, track, fill_used,
            accuracy_label, tags_json, payload_json, taken_at, closed_at,
            notify_sent, created_at, updated_at
        FROM daily_fill_calls;
        DROP TABLE daily_fill_calls;
        ALTER TABLE daily_fill_calls_k2 RENAME TO daily_fill_calls;
        CREATE INDEX IF NOT EXISTS idx_daily_fill_day
            ON daily_fill_calls(session_date, stock);
        CREATE INDEX IF NOT EXISTS idx_daily_fill_open
            ON daily_fill_calls(stock, status);
        """
    )


def ensure_tables(db_path: Optional[str] = None) -> str:
    path = db_path or default_db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS daily_fill_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock TEXT NOT NULL,
                session_date TEXT NOT NULL,
                bar_time TEXT NOT NULL,
                decision TEXT NOT NULL,
                status TEXT NOT NULL,
                entry REAL,
                stop_loss REAL,
                target_1 REAL,
                p_t1 REAL,
                track TEXT,
                fill_used INTEGER NOT NULL DEFAULT 0,
                accuracy_label TEXT,
                tags_json TEXT,
                payload_json TEXT,
                taken_at TEXT,
                closed_at TEXT,
                notify_sent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(stock, session_date, bar_time)
            );
            CREATE INDEX IF NOT EXISTS idx_daily_fill_day
                ON daily_fill_calls(session_date, stock);
            CREATE INDEX IF NOT EXISTS idx_daily_fill_open
                ON daily_fill_calls(stock, status);
            CREATE TABLE IF NOT EXISTS daily_fill_pending (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock TEXT NOT NULL,
                session_date TEXT NOT NULL,
                track TEXT NOT NULL,
                decision TEXT NOT NULL,
                mins INTEGER,
                p_t1 REAL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(stock, session_date, track, decision, mins)
            );
            CREATE INDEX IF NOT EXISTS idx_daily_fill_pending_day
                ON daily_fill_pending(stock, session_date);
            """
        )
        _migrate_calls_to_k2(conn)
        conn.commit()
    finally:
        conn.close()
    return path


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def count_today(stock: str, session_date: str, *, db_path: Optional[str] = None) -> int:
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM daily_fill_calls WHERE stock=? AND session_date=?",
            (str(stock).upper(), str(session_date)[:10]),
        )
        return int(cur.fetchone()[0] or 0)
    finally:
        conn.close()


def list_today_signals(
    stock: str, session_date: str, *, db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Return today's locked daily_fill rows (oldest first)."""
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT * FROM daily_fill_calls WHERE stock=? AND session_date=? "
            "ORDER BY bar_time, id",
            (str(stock).upper(), str(session_date)[:10]),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def upsert_signal(
    sig: Dict[str, Any],
    *,
    db_path: Optional[str] = None,
    max_per_day: int = 2,
) -> Dict[str, Any]:
    """Insert a daily_fill call (up to max_per_day per stock/session_date)."""
    try:
        path = ensure_tables(db_path)
        stock = str(sig.get("symbol") or "").upper()
        bar_time = str(sig.get("bar_time") or "")
        decision = str(sig.get("decision") or "").upper()
        if not stock or not bar_time or decision not in ("BUY", "SELL"):
            return {"ok": False, "reason": "bad_payload"}
        session_date = str(sig.get("session_date") or bar_time[:10])[:10]
        now = _now()
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                "SELECT id, status, notify_sent FROM daily_fill_calls "
                "WHERE stock=? AND session_date=? AND bar_time=?",
                (stock, session_date, bar_time),
            )
            row = cur.fetchone()
            if row:
                return {
                    "ok": True,
                    "created": False,
                    "id": int(row["id"]),
                    "status": row["status"],
                    "notify_sent": int(row["notify_sent"] or 0),
                }
            n = int(
                conn.execute(
                    "SELECT COUNT(*) FROM daily_fill_calls WHERE stock=? AND session_date=?",
                    (stock, session_date),
                ).fetchone()[0]
                or 0
            )
            if n >= int(max_per_day):
                return {"ok": True, "created": False, "reason": "day_cap", "count": n}
            cur = conn.execute(
                """
                INSERT INTO daily_fill_calls (
                    stock, session_date, bar_time, decision, status,
                    entry, stop_loss, target_1, p_t1, track, fill_used,
                    accuracy_label, tags_json, payload_json, taken_at, closed_at,
                    notify_sent, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)
                """,
                (
                    stock,
                    session_date,
                    bar_time,
                    decision,
                    "open",
                    sig.get("entry"),
                    sig.get("stop_loss"),
                    sig.get("target_1"),
                    sig.get("p_t1"),
                    sig.get("track") or "daily_fill",
                    1 if sig.get("fill_used") or sig.get("daily_fill") else 0,
                    sig.get("accuracy_label") or "daily fill",
                    json.dumps(sig.get("accuracy_tags") or [], default=str),
                    json.dumps(sig, default=str),
                    sig.get("taken_at") or now,
                    None,
                    now,
                    now,
                ),
            )
            conn.commit()
            return {
                "ok": True,
                "created": True,
                "id": int(cur.lastrowid),
                "status": "open",
                "notify_sent": 0,
                "call_n": n + 1,
            }
        finally:
            conn.close()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def claim_notify(row_id: int, *, db_path: Optional[str] = None) -> bool:
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "UPDATE daily_fill_calls SET notify_sent=1, updated_at=? "
            "WHERE id=? AND notify_sent=0",
            (_now(), int(row_id)),
        )
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def list_open(
    stock: Optional[str] = None,
    *,
    db_path: Optional[str] = None,
    shadow_only: bool = False,
) -> List[Dict[str, Any]]:
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        if stock:
            cur = conn.execute(
                "SELECT * FROM daily_fill_calls WHERE status='open' AND stock=? "
                "ORDER BY session_date, id",
                (str(stock).upper(),),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM daily_fill_calls WHERE status='open' "
                "ORDER BY stock, session_date, id"
            )
        rows = [dict(r) for r in cur.fetchall()]
        if not shadow_only:
            return rows
        out = []
        for r in rows:
            try:
                payload = json.loads(r.get("payload_json") or "{}")
            except Exception:
                payload = {}
            if payload.get("shadow") or "SHADOW" in str(r.get("accuracy_label") or ""):
                out.append(r)
        return out
    finally:
        conn.close()


def close_call(
    row_id: int,
    *,
    status: str,
    db_path: Optional[str] = None,
) -> bool:
    """Mark a call closed: status in t1_before_sl / sl_before_t1 / same_bar_both / expired."""
    path = ensure_tables(db_path)
    now = _now()
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "UPDATE daily_fill_calls SET status=?, closed_at=?, updated_at=? "
            "WHERE id=? AND status='open'",
            (str(status), now, now, int(row_id)),
        )
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def list_closed_since(
    *,
    since_day: str,
    db_path: Optional[str] = None,
    shadow_only: bool = True,
) -> List[Dict[str, Any]]:
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT * FROM daily_fill_calls WHERE session_date>=? AND status!='open' "
            "ORDER BY session_date, id",
            (str(since_day)[:10],),
        )
        rows = [dict(r) for r in cur.fetchall()]
        if not shadow_only:
            return rows
        out = []
        for r in rows:
            try:
                payload = json.loads(r.get("payload_json") or "{}")
            except Exception:
                payload = {}
            if payload.get("shadow") or "SHADOW" in str(r.get("accuracy_label") or ""):
                out.append(r)
        return out
    finally:
        conn.close()


def list_today(stock: str, session_date: str, *, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_today_signals(stock, session_date, db_path=db_path)


def upsert_pending(cands: List[Dict[str, Any]], *, db_path: Optional[str] = None) -> int:
    """Accumulate session candidates for best-of-day pick at 14:15 (no day lock)."""
    if not cands:
        return 0
    path = ensure_tables(db_path)
    now = _now()
    n = 0
    conn = sqlite3.connect(path)
    try:
        for c in cands:
            stock = str(c.get("symbol") or "").upper()
            day = str(c.get("session_date") or "")[:10]
            track = str(c.get("track") or "")
            decision = str(c.get("decision") or "").upper()
            mins = int(c.get("mins") or 0)
            if not stock or not day or decision not in ("BUY", "SELL") or not track:
                continue
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO daily_fill_pending (
                        stock, session_date, track, decision, mins, p_t1,
                        payload_json, created_at
                    ) VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        stock,
                        day,
                        track,
                        decision,
                        mins,
                        float(c.get("p_t1") or 0),
                        json.dumps(c, default=str),
                        now,
                    ),
                )
                n += 1
            except Exception:
                continue
        conn.commit()
    finally:
        conn.close()
    return n


def list_pending(stock: str, session_date: str, *, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT payload_json FROM daily_fill_pending "
            "WHERE stock=? AND session_date=? ORDER BY mins, track",
            (str(stock).upper(), str(session_date)[:10]),
        )
        out: List[Dict[str, Any]] = []
        for r in cur.fetchall():
            try:
                payload = json.loads(r["payload_json"] or "{}")
                if isinstance(payload, dict) and payload.get("decision") in ("BUY", "SELL"):
                    out.append(payload)
            except Exception:
                continue
        return out
    finally:
        conn.close()


def clear_pending(stock: str, session_date: str, *, db_path: Optional[str] = None) -> None:
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "DELETE FROM daily_fill_pending WHERE stock=? AND session_date=?",
            (str(stock).upper(), str(session_date)[:10]),
        )
        conn.commit()
    finally:
        conn.close()
