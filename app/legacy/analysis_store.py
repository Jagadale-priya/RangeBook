"""Persist full analysis payloads + historical audit outcomes (knowledge.db)."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

_ANALYSIS_JSON_KEYS = (
    "stock_input",
    "symbol",
    "decision",
    "confidence",
    "signal_quality",
    "signals_agree",
    "analysis_mode",
    "summary",
    "ml_prediction",
    "technical_analysis",
    "fundamental_analysis",
    "structural_analysis",
    "knowledge_memory",
    "validation",
    "data_provenance",
    "panel_hints",
    "recent_news",
    "metadata",
    "session_ticket",
    "session_tickets",
    "fno_analysis",
    "intraday_analysis",
)


def ensure_analysis_tables(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS analysis_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock TEXT NOT NULL,
            symbol TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            analysis_mode TEXT NOT NULL DEFAULT 'auto',
            product TEXT,
            source TEXT NOT NULL DEFAULT 'live',
            decision TEXT NOT NULL,
            confidence REAL,
            signal_quality TEXT,
            ml_probability REAL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(stock, as_of_date, analysis_mode, product, source)
        );
        CREATE INDEX IF NOT EXISTS idx_analysis_stock_date ON analysis_snapshots(stock, as_of_date DESC);

        CREATE TABLE IF NOT EXISTS audit_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            holdout_start TEXT NOT NULL,
            symbols_json TEXT,
            total_days INTEGER,
            total_correct INTEGER,
            total_evaluated INTEGER,
            accuracy REAL,
            params_json TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS daily_audit_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_run_id INTEGER NOT NULL,
            stock TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            predicted_decision TEXT NOT NULL,
            predicted_side TEXT NOT NULL,
            ml_probability REAL,
            technical_score REAL,
            combined_score REAL,
            knowledge_adjust REAL,
            news_count INTEGER,
            signals_agree INTEGER,
            signal_quality TEXT,
            actual_return_1d REAL,
            actual_side TEXT NOT NULL,
            label_correct INTEGER NOT NULL,
            failure_reason TEXT,
            base_rate REAL,
            confidence_lift REAL,
            UNIQUE(audit_run_id, stock, as_of_date),
            FOREIGN KEY (audit_run_id) REFERENCES audit_runs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_audit_stock ON daily_audit_outcomes(stock, as_of_date);
        """
    )
    existing = {r[1] for r in conn.execute("PRAGMA table_info(daily_audit_outcomes)")}
    for col in ("base_rate", "confidence_lift"):
        if col not in existing:
            conn.execute(f"ALTER TABLE daily_audit_outcomes ADD COLUMN {col} REAL")
    conn.commit()
    conn.close()
    try:
        import session_calls

        session_calls.ensure_tables(db_path)
    except Exception:
        pass
    try:
        import training_store

        training_store.ensure_tables(db_path)
    except Exception:
        pass


def _trim_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in _ANALYSIS_JSON_KEYS:
        if k in result:
            out[k] = result[k]
    out["combined_score"] = result.get("combined_score")
    out["current_price"] = result.get("current_price")
    return out


def save_live_analysis(db_path: str, result: Dict[str, Any], *, product: Optional[str] = None) -> None:
    ensure_analysis_tables(db_path)
    stock = (result.get("stock_input") or "").strip().upper()
    if not stock:
        return
    meta = result.get("metadata") or {}
    as_of = (meta.get("as_of_date") or meta.get("timestamp") or datetime.now().isoformat())[:10]
    mode = result.get("analysis_mode") or meta.get("analysis_mode") or "auto"
    prod = product or result.get("product")
    ml = result.get("ml_prediction") or {}
    payload = json.dumps(_trim_payload(result), default=str)
    now = datetime.now().isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO analysis_snapshots
        (stock, symbol, as_of_date, analysis_mode, product, source, decision, confidence,
         signal_quality, ml_probability, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, 'live', ?, ?, ?, ?, ?, ?)
        ON CONFLICT(stock, as_of_date, analysis_mode, product, source) DO UPDATE SET
          decision=excluded.decision,
          confidence=excluded.confidence,
          signal_quality=excluded.signal_quality,
          ml_probability=excluded.ml_probability,
          payload_json=excluded.payload_json,
          created_at=excluded.created_at
        """,
        (
            stock,
            result.get("symbol"),
            as_of,
            mode,
            prod,
            result.get("decision"),
            result.get("confidence"),
            result.get("signal_quality"),
            ml.get("probability_up"),
            payload,
            now,
        ),
    )
    conn.commit()
    conn.close()


def save_audit_snapshot(db_path: str, result: Dict[str, Any], as_of_date: str) -> None:
    ensure_analysis_tables(db_path)
    stock = (result.get("stock_input") or "").strip().upper()
    meta = result.get("metadata") or {}
    mode = result.get("analysis_mode") or "auto"
    ml = result.get("ml_prediction") or {}
    payload = json.dumps(_trim_payload(result), default=str)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO analysis_snapshots
        (stock, symbol, as_of_date, analysis_mode, product, source, decision, confidence,
         signal_quality, ml_probability, payload_json, created_at)
        VALUES (?, ?, ?, ?, NULL, 'audit', ?, ?, ?, ?, ?, ?)
        ON CONFLICT(stock, as_of_date, analysis_mode, product, source) DO UPDATE SET
          payload_json=excluded.payload_json,
          decision=excluded.decision,
          created_at=excluded.created_at
        """,
        (
            stock,
            result.get("symbol"),
            as_of_date,
            mode,
            result.get("decision"),
            result.get("confidence"),
            result.get("signal_quality"),
            ml.get("probability_up"),
            payload,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_live_snapshot(
    db_path: str,
    stock: str,
    as_of_date: Optional[str] = None,
    analysis_mode: str = "auto",
    product: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not os.path.isfile(db_path):
        return None
    day = (as_of_date or datetime.now().strftime("%Y-%m-%d"))[:10]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT payload_json FROM analysis_snapshots
        WHERE stock = ? AND as_of_date = ? AND analysis_mode = ? AND source = 'live'
          AND (product IS ? OR product = ?)
        ORDER BY id DESC LIMIT 1
        """,
        (stock.strip().upper(), day, analysis_mode, product, product),
    ).fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row["payload_json"])
    except json.JSONDecodeError:
        return None


def get_audit_summary(db_path: str, stock: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    if not os.path.isfile(db_path):
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    runs = conn.execute(
        "SELECT * FROM audit_runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    out = []
    for run in runs:
        item = dict(run)
        if stock:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n,
                       SUM(label_correct) AS ok,
                       AVG(label_correct) AS acc
                FROM daily_audit_outcomes
                WHERE audit_run_id = ? AND stock = ?
                """,
                (run["id"], stock.strip().upper()),
            ).fetchone()
            item["stock_stats"] = dict(row) if row else {}
        out.append(item)
    conn.close()
    return out


def analysis_stats(db_path: str) -> Dict[str, Any]:
    if not os.path.isfile(db_path):
        return {"ready": False}
    ensure_analysis_tables(db_path)
    conn = sqlite3.connect(db_path)
    live_n = conn.execute(
        "SELECT COUNT(*) FROM analysis_snapshots WHERE source = 'live'"
    ).fetchone()[0]
    audit_n = conn.execute("SELECT COUNT(*) FROM analysis_snapshots WHERE source = 'audit'").fetchone()[0]
    outcomes = conn.execute("SELECT COUNT(*) FROM daily_audit_outcomes").fetchone()[0]
    runs = conn.execute("SELECT COUNT(*) FROM audit_runs").fetchone()[0]
    conn.close()
    return {
        "ready": live_n > 0 or outcomes > 0,
        "live_snapshots": live_n,
        "audit_snapshots": audit_n,
        "daily_outcomes": outcomes,
        "audit_runs": runs,
    }
