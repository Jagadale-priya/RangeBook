"""Persist desk alerts (model/overlay calls, book, drop) for the hamburger Notifications list."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

_lock = threading.Lock()
_DB_TIMEOUT = 30.0
_schema_ready: set[str] = set()


def _db_path(db_path: Optional[str] = None) -> str:
    if db_path:
        return db_path
    import knowledge_db

    return knowledge_db.ensure_db_dir()


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=_DB_TIMEOUT, check_same_thread=False)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.Error:
        pass
    return conn


def ensure_tables(db_path: Optional[str] = None) -> str:
    path = _db_path(db_path)
    if path in _schema_ready:
        return path
    with _lock:
        if path in _schema_ready:
            return path
        conn = _connect(path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS desk_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    stock TEXT,
                    product TEXT NOT NULL DEFAULT 'fno',
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    decision TEXT,
                    entry REAL,
                    stop_loss REAL,
                    target_1 REAL,
                    dedupe_key TEXT,
                    read_at TEXT,
                    payload_json TEXT
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_desk_notify_dedupe "
                "ON desk_notifications(dedupe_key) WHERE dedupe_key IS NOT NULL"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_desk_notify_created "
                "ON desk_notifications(created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_desk_notify_unread "
                "ON desk_notifications(read_at, created_at DESC)"
            )
            conn.commit()
            _schema_ready.add(path)
        finally:
            conn.close()
    return path


def record(
    *,
    title: str,
    message: str,
    stock: Optional[str] = None,
    product: str = "fno",
    kind: str = "alert",
    decision: Optional[str] = None,
    entry: Any = None,
    stop_loss: Any = None,
    target_1: Any = None,
    dedupe_key: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> Optional[int]:
    """Insert a notification. Returns row id, or None if deduped / empty."""
    head = (title or "").strip()
    body = (message or "").strip()
    if not head or not body:
        return None
    path = ensure_tables(db_path)
    sym = (stock or "").strip().upper() or None
    now = datetime.now().isoformat(timespec="seconds")

    def _num(v: Any) -> Optional[float]:
        try:
            if v is None or v == "":
                return None
            return float(v)
        except (TypeError, ValueError):
            return None

    with _lock:
        conn = _connect(path)
        try:
            if dedupe_key:
                exists = conn.execute(
                    "SELECT id FROM desk_notifications WHERE dedupe_key=?",
                    (dedupe_key,),
                ).fetchone()
                if exists:
                    return None
            cur = conn.execute(
                """
                INSERT INTO desk_notifications (
                    created_at, stock, product, kind, title, message,
                    decision, entry, stop_loss, target_1, dedupe_key, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    sym,
                    (product or "fno").lower(),
                    (kind or "alert").strip() or "alert",
                    head[:160],
                    body[:2000],
                    (str(decision).upper() if decision else None),
                    _num(entry),
                    _num(stop_loss),
                    _num(target_1),
                    dedupe_key,
                    json.dumps(payload or {}, default=str),
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        except sqlite3.IntegrityError:
            return None
        except sqlite3.OperationalError as exc:
            # Don't crash the desk on transient lock contention.
            print(f"[desk_notifications] record locked/failed: {exc}")
            return None
        finally:
            conn.close()


def list_notifications(
    *,
    limit: int = 80,
    unread_only: bool = False,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    path = ensure_tables(db_path)
    lim = max(1, min(int(limit or 80), 200))
    sql = """
        SELECT id, created_at, stock, product, kind, title, message,
               decision, entry, stop_loss, target_1, read_at, payload_json
        FROM desk_notifications
    """
    if unread_only:
        sql += " WHERE read_at IS NULL"
    sql += " ORDER BY id DESC LIMIT ?"
    try:
        with _lock:
            conn = _connect(path)
            conn.row_factory = sqlite3.Row
            try:
                rows = [dict(r) for r in conn.execute(sql, (lim,)).fetchall()]
            finally:
                conn.close()
    except sqlite3.OperationalError as exc:
        print(f"[desk_notifications] list locked/failed: {exc}")
        return []
    for r in rows:
        try:
            r["payload"] = json.loads(r.pop("payload_json") or "{}")
        except Exception:
            r["payload"] = {}
            r.pop("payload_json", None)
        payload = r.get("payload") if isinstance(r.get("payload"), dict) else {}
        r["unread"] = r.get("read_at") is None
        action = str(payload.get("action") or "").upper()
        if not action:
            kind = str(r.get("kind") or "").lower()
            if "book" in kind:
                action = "BOOK"
            elif "drop" in kind:
                action = "DROP"
            elif kind in ("model_call", "overlay_indication"):
                action = "NEW"
            elif "close" in kind:
                action = "CLOSE"
            else:
                action = "ALERT"
        r["action"] = action
        when_label = payload.get("when_label")
        if not when_label:
            try:
                import desk_notify_format as fmt

                when_label = fmt.now_ist_label(r.get("created_at"))
            except Exception:
                when_label = str(r.get("created_at") or "")[:16]
        r["when_label"] = when_label
        # Prefer body after first line for popup message block (keep contract / premium lines).
        msg = str(r.get("message") or "")
        parts = [p.strip() for p in msg.split("\n") if p.strip()]
        r["headline"] = parts[0] if parts else str(r.get("title") or "")
        r["detail_line"] = (
            " · ".join(parts[1:]) if len(parts) > 1 else (parts[0] if parts else "")
        )
        ts = payload.get("tradingsymbol")
        groww = payload.get("groww_url") or payload.get("groww_chart")
        if ts and not groww:
            try:
                import groww_option_links

                groww = groww_option_links.option_chart_url(r.get("stock"), ts)
            except Exception:
                groww = None
        r["tradingsymbol"] = ts
        r["groww_url"] = groww
        r["option_right"] = payload.get("right")
        r["premium_buy"] = payload.get("premium_buy")
        r["premium_sl"] = payload.get("premium_sl")
        r["premium_exit_book"] = payload.get("premium_exit_book") or payload.get("premium_target")
    return rows


def unread_count(db_path: Optional[str] = None) -> int:
    path = ensure_tables(db_path)
    try:
        with _lock:
            conn = _connect(path)
            try:
                n = conn.execute(
                    "SELECT COUNT(*) FROM desk_notifications WHERE read_at IS NULL"
                ).fetchone()[0]
            finally:
                conn.close()
        return int(n or 0)
    except sqlite3.OperationalError as exc:
        print(f"[desk_notifications] unread locked/failed: {exc}")
        return 0


def mark_read(
    ids: Optional[List[int]] = None,
    *,
    all_unread: bool = False,
    db_path: Optional[str] = None,
) -> int:
    path = ensure_tables(db_path)
    now = datetime.now().isoformat(timespec="seconds")
    try:
        with _lock:
            conn = _connect(path)
            try:
                if all_unread:
                    cur = conn.execute(
                        "UPDATE desk_notifications SET read_at=? WHERE read_at IS NULL",
                        (now,),
                    )
                else:
                    id_list = [int(i) for i in (ids or []) if i is not None]
                    if not id_list:
                        return 0
                    q = ",".join("?" * len(id_list))
                    cur = conn.execute(
                        f"UPDATE desk_notifications SET read_at=? WHERE id IN ({q}) AND read_at IS NULL",
                        [now, *id_list],
                    )
                conn.commit()
                n = cur.rowcount
            finally:
                conn.close()
        return int(n or 0)
    except sqlite3.OperationalError as exc:
        print(f"[desk_notifications] mark_read locked/failed: {exc}")
        return 0


def status(db_path: Optional[str] = None) -> Dict[str, Any]:
    path = ensure_tables(db_path)
    return {
        "unread": unread_count(path),
        "items": list_notifications(limit=40, db_path=path),
    }
