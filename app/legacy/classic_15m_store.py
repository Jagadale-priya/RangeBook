"""Independent SQLite store for 15m classic (old single fno_model) calls.

Parallel to dual-track / 5m crown — never touches those tables.
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


def ensure_tables(db_path: Optional[str] = None) -> str:
    path = db_path or default_db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS classic_15m_calls (
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
                accuracy_label TEXT,
                tags_json TEXT,
                payload_json TEXT,
                taken_at TEXT,
                closed_at TEXT,
                notify_sent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(stock, bar_time, decision)
            );
            CREATE INDEX IF NOT EXISTS idx_classic_15m_day
                ON classic_15m_calls(session_date, stock);
            CREATE INDEX IF NOT EXISTS idx_classic_15m_open
                ON classic_15m_calls(stock, status);
            """
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def count_today(
    stock: str, session_date: str, *, side: Optional[str] = None, db_path: Optional[str] = None
) -> int:
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    try:
        if side in ("BUY", "SELL"):
            cur = conn.execute(
                "SELECT COUNT(*) FROM classic_15m_calls WHERE stock=? AND session_date=? AND decision=?",
                (str(stock).upper(), str(session_date)[:10], side),
            )
        else:
            cur = conn.execute(
                "SELECT COUNT(*) FROM classic_15m_calls WHERE stock=? AND session_date=?",
                (str(stock).upper(), str(session_date)[:10]),
            )
        return int(cur.fetchone()[0] or 0)
    finally:
        conn.close()


def upsert_signal(sig: Dict[str, Any], *, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Insert classic call if this bar/side not already stored."""
    try:
        path = ensure_tables(db_path)
        stock = str(sig.get("symbol") or "").upper()
        bar_time = str(sig.get("bar_time") or "")
        decision = str(sig.get("decision") or "").upper()
        if not stock or not bar_time or decision not in ("BUY", "SELL"):
            return {"ok": False, "reason": "bad_payload"}
        session_date = str(sig.get("session_date") or bar_time[:10])
        now = _now()
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                "SELECT id, status, notify_sent FROM classic_15m_calls "
                "WHERE stock=? AND bar_time=? AND decision=?",
                (stock, bar_time, decision),
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
            cur = conn.execute(
                """
                INSERT INTO classic_15m_calls (
                    stock, session_date, bar_time, decision, status,
                    entry, stop_loss, target_1, p_t1, accuracy_label,
                    tags_json, payload_json, taken_at, closed_at,
                    notify_sent, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)
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
                    sig.get("accuracy_label") or "15m classic",
                    json.dumps(sig.get("accuracy_tags") or [], default=str),
                    json.dumps(sig, default=str),
                    sig.get("taken_at") or now,
                    None,
                    now,
                    now,
                ),
            )
            conn.commit()
            return {"ok": True, "created": True, "id": int(cur.lastrowid), "status": "open", "notify_sent": 0}
        finally:
            conn.close()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def claim_notify(row_id: int, *, db_path: Optional[str] = None) -> bool:
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "UPDATE classic_15m_calls SET notify_sent=1, updated_at=? "
            "WHERE id=? AND notify_sent=0",
            (_now(), int(row_id)),
        )
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def list_today(stock: str, session_date: str, *, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT * FROM classic_15m_calls WHERE stock=? AND session_date=? ORDER BY bar_time",
            (str(stock).upper(), str(session_date)[:10]),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
