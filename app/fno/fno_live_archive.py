"""Archive live F&O snapshots for future accuracy / loss analysis.

Stores one row per (stock, finished 5m bucket) while analyzing — richer when a
call is open. Fields chosen so later research can ask: which indications
preceded winners vs losers (path, Fib/W, micro, checklist, short-horizon).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

_lock = threading.Lock()
_last_write: Dict[str, float] = {}
_MIN_GAP_SEC = 25.0  # don't spam on 1s LTP polls; 5m bar + open-call polls OK


def default_db_path() -> str:
    import knowledge_db

    return knowledge_db.ensure_db_dir()


def ensure_tables(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS fno_live_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock TEXT NOT NULL,
            session_date TEXT NOT NULL,
            bar_bucket TEXT NOT NULL,
            ticket_n INTEGER,
            decision TEXT,
            call_status TEXT,
            price REAL,
            entry REAL,
            stop_loss REAL,
            target_1 REAL,
            favor_pts REAL,
            against_pts REAL,
            p_t1_entry REAL,
            p_t1_live REAL,
            live_p_up REAL,
            micro_score REAL,
            combined_score REAL,
            path_state TEXT,
            short_side TEXT,
            short_p_side REAL,
            expected_pts_5m REAL,
            pattern_top TEXT,
            pattern_count INTEGER,
            checklist_bull INTEGER,
            checklist_bear INTEGER,
            high_alert INTEGER,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(stock, session_date, bar_bucket, ticket_n, call_status)
        );
        CREATE INDEX IF NOT EXISTS idx_fno_live_arch_day
            ON fno_live_archive(session_date, stock);
        CREATE INDEX IF NOT EXISTS idx_fno_live_arch_ticket
            ON fno_live_archive(stock, ticket_n, session_date);
        """
    )
    conn.commit()
    conn.close()


def _bucket(ts: Optional[str] = None) -> str:
    """Floor to 5-minute wall-clock bucket (local/IST process time)."""
    now = datetime.now()
    if ts:
        try:
            text = str(ts).replace("Z", "+00:00")
            now = datetime.fromisoformat(text)
            if now.tzinfo is not None:
                now = now.replace(tzinfo=None)
        except ValueError:
            pass
    floored = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)
    return floored.strftime("%Y-%m-%dT%H:%M")


def _num(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _slim_payload(fa: Dict[str, Any], active: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Keep research-useful fields; drop huge bar frames."""
    sh = fa.get("short_horizon") or {}
    scan = fa.get("structure_scan") or {}
    ind = fa.get("indications") or {}
    live = fa.get("live_context") or {}
    micro = live.get("microstructure") or {}
    cl = fa.get("call_live") or {}
    ph = fa.get("path_health") or {}
    fm = fa.get("fno_model") or {}
    return {
        "decision": fa.get("decision"),
        "confidence": fa.get("confidence"),
        "combined_score_fno": fa.get("combined_score_fno"),
        "short_horizon": {
            k: sh.get(k)
            for k in (
                "side", "p_side", "p_up", "p_down", "expected_points_5m",
                "expected_points_10m", "headline", "votes", "react_up", "react_down",
                "vs_call", "atr_5m",
            )
            if k in sh or sh.get(k) is not None
        },
        "structure_scan": {
            "count": scan.get("count"),
            "bullish": scan.get("bullish"),
            "bearish": scan.get("bearish"),
            "frame": scan.get("frame"),
            "top": scan.get("top"),
            "patterns": [
                {k: p.get(k) for k in ("key", "name", "lean", "status", "trigger", "note", "score")}
                for p in (scan.get("patterns") or [])[:8]
            ],
            "guide": scan.get("guide"),
        },
        "indications_summary": (ind.get("summary") if isinstance(ind, dict) else None),
        "call_live": cl if cl else None,
        "path_health": {
            "state": ph.get("state"),
            "tone": ph.get("tone"),
            "message": ph.get("message"),
            "metrics": ph.get("metrics"),
        } if ph else None,
        "model": {
            "p_t1": fm.get("p_t1"),
            "buy_p": fm.get("buy_p"),
            "decision": fm.get("decision"),
            "regime": (fm.get("regime") or {}).get("name") if isinstance(fm.get("regime"), dict) else fm.get("regime"),
        },
        "micro": {
            "micro_bias": micro.get("micro_bias"),
            "micro_score": micro.get("micro_score"),
            "five_min_conflict": micro.get("five_min_conflict"),
        },
        "live_probability_up": live.get("live_probability_up") or live.get("live_p"),
        "active": {
            "n": (active or {}).get("n") or (active or {}).get("ticket_n"),
            "decision": (active or {}).get("decision"),
            "entry": (active or {}).get("entry"),
            "stop_loss": (active or {}).get("stop_loss"),
            "target_1": (active or {}).get("target_1"),
            "p_t1": (active or {}).get("p_t1"),
            "path_peak_favor": (active or {}).get("path_peak_favor"),
            "path_against": (active or {}).get("path_against"),
            "taken_at": (active or {}).get("taken_at"),
        } if active else None,
    }


def maybe_record(
    *,
    stock: str,
    fno_analysis: Optional[Dict[str, Any]],
    price: Optional[float] = None,
    active_call: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
    force: bool = False,
) -> bool:
    """Insert/replace snapshot for this 5m bucket. Returns True if written."""
    fa = fno_analysis or {}
    key = (stock or "").strip().upper()
    if not key or not fa:
        return False
    path = db_path or default_db_path()
    now = time.time()
    with _lock:
        last = _last_write.get(key, 0.0)
        # Always allow a write when a call is open or force; else throttle.
        open_call = bool(active_call and active_call.get("decision") not in (None, "HOLD"))
        if not force and not open_call and (now - last) < _MIN_GAP_SEC:
            return False
        if not force and open_call and (now - last) < 12.0:
            return False
        _last_write[key] = now

    ensure_tables(path)
    bucket = _bucket()
    day = bucket[:10]
    sh = fa.get("short_horizon") or {}
    scan = fa.get("structure_scan") or {}
    ind = (fa.get("indications") or {}).get("summary") or {}
    cl = fa.get("call_live") or {}
    ph = fa.get("path_health") or {}
    live = fa.get("live_context") or {}
    micro = live.get("microstructure") or {}
    readings = (active_call or {}).get("readings") if isinstance((active_call or {}).get("readings"), dict) else {}

    ticket_n = 0
    if active_call:
        try:
            ticket_n = int(active_call.get("n") or active_call.get("ticket_n") or 0)
        except (TypeError, ValueError):
            ticket_n = 0

    call_status = "open" if open_call else "idle"
    if open_call and active_call and active_call.get("status"):
        call_status = str(active_call.get("status"))

    top = scan.get("top") or {}
    payload = _slim_payload(fa, active_call)
    created = datetime.now().isoformat(timespec="seconds")

    row = (
        key,
        day,
        bucket,
        ticket_n,
        str((active_call or {}).get("decision") or fa.get("decision") or "HOLD"),
        call_status,
        _num(price),
        _num((active_call or {}).get("entry")),
        _num((active_call or {}).get("stop_loss")),
        _num((active_call or {}).get("target_1")),
        _num((active_call or {}).get("path_peak_favor")),
        _num((active_call or {}).get("path_against")),
        _num(readings.get("p_t1") or (active_call or {}).get("p_t1")),
        _num(cl.get("live_p_t1") or (fa.get("fno_model") or {}).get("p_t1")),
        _num(live.get("live_probability_up") or live.get("live_p")),
        _num(micro.get("micro_score") or cl.get("live_micro_score")),
        _num(fa.get("combined_score_fno")),
        ph.get("state"),
        sh.get("side"),
        _num(sh.get("p_side")),
        _num(sh.get("expected_points_5m")),
        (top.get("name") if isinstance(top, dict) else None),
        int(scan.get("count") or 0),
        int(ind.get("bullish") or 0) if ind else None,
        int(ind.get("bearish") or 0) if ind else None,
        1 if cl.get("high_alert") else 0,
        json.dumps(payload, default=str),
        created,
    )

    try:
        conn = sqlite3.connect(path)
        conn.execute(
            """
            INSERT OR REPLACE INTO fno_live_archive (
                stock, session_date, bar_bucket, ticket_n, decision, call_status,
                price, entry, stop_loss, target_1, favor_pts, against_pts,
                p_t1_entry, p_t1_live, live_p_up, micro_score, combined_score,
                path_state, short_side, short_p_side, expected_pts_5m,
                pattern_top, pattern_count, checklist_bull, checklist_bear,
                high_alert, payload_json, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            row,
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False
