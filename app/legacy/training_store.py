"""Morning briefs, session outcomes, bar ingest, and model train log (knowledge.db)."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import knowledge_db

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore

_DB_TIMEOUT = 60.0


def _connect(path: str) -> sqlite3.Connection:
    return sqlite3.connect(path, timeout=_DB_TIMEOUT)


def ensure_tables(db_path: Optional[str] = None) -> str:
    path = db_path or knowledge_db.ensure_db_dir()
    conn = _connect(path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS morning_briefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            stock TEXT NOT NULL,
            report_key TEXT NOT NULL,
            generated_at TEXT,
            ref_close REAL,
            expected_low REAL,
            expected_high REAL,
            trade_low REAL,
            trade_high REAL,
            forecast_method TEXT,
            locked INTEGER DEFAULT 0,
            decision TEXT,
            confidence REAL,
            signal_quality TEXT,
            vix_level REAL,
            payload_json TEXT,
            actual_open REAL,
            actual_high REAL,
            actual_low REAL,
            actual_close REAL,
            inside_forecast INTEGER,
            inside_trade_box INTEGER,
            high_miss_pts REAL,
            low_miss_pts REAL,
            scored_at TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(session_date, stock, report_key)
        );
        CREATE INDEX IF NOT EXISTS idx_morning_briefs_day ON morning_briefs(session_date, stock);

        CREATE TABLE IF NOT EXISTS market_bar_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            stock TEXT NOT NULL,
            interval TEXT NOT NULL DEFAULT '15minute',
            bar_count INTEGER,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            or_high REAL,
            or_low REAL,
            source TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(session_date, stock, interval)
        );

        CREATE TABLE IF NOT EXISTS dark_pool_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            stock TEXT NOT NULL,
            dix REAL NOT NULL,
            source TEXT,
            note TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(session_date, stock)
        );

        CREATE TABLE IF NOT EXISTS model_train_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            symbols_json TEXT,
            metrics_json TEXT,
            ok INTEGER DEFAULT 0,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS agent_heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            beat_at TEXT NOT NULL,
            phase TEXT,
            detail_json TEXT
        );

        CREATE TABLE IF NOT EXISTS chain_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock TEXT NOT NULL,
            bar_ts TEXT NOT NULL,
            session_date TEXT NOT NULL,
            pcr REAL,
            ce_oi REAL,
            pe_oi REAL,
            iv_atm REAL,
            iv_skew REAL,
            gex_flip REAL,
            gex_bias TEXT,
            fut_basis REAL,
            vix_level REAL,
            book_buy REAL,
            book_sell REAL,
            spot REAL,
            updated_at TEXT NOT NULL,
            UNIQUE(stock, bar_ts)
        );
        CREATE INDEX IF NOT EXISTS idx_chain_snap_stock ON chain_snapshots(stock, bar_ts);

        CREATE TABLE IF NOT EXISTS ml_session_days (
            stock TEXT NOT NULL,
            session_date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            pcr REAL,
            ce_oi REAL,
            pe_oi REAL,
            iv_atm REAL,
            fut_basis REAL,
            vix_level REAL,
            saved_at TEXT NOT NULL,
            UNIQUE(stock, session_date)
        );
        CREATE INDEX IF NOT EXISTS idx_ml_session_days ON ml_session_days(stock, session_date);

        CREATE TABLE IF NOT EXISTS notify_dedupe (
            dedupe_key TEXT PRIMARY KEY,
            notified_at TEXT NOT NULL,
            stock TEXT,
            decision TEXT,
            payload_json TEXT
        );
        """
    )
    conn.commit()
    conn.close()
    return path


def _dr(row: Dict[str, Any]) -> Dict[str, Any]:
    dr = row.get("day_range_forecast") or {}
    if not dr and row.get("full"):
        dr = (row.get("full") or {}).get("day_range_forecast") or {}
    return dr


def archive_tape_days(db_path: str, stock: str, tape: Any) -> int:
    """Store each finished session, with the chain print from that day, for the next train."""
    if pd is None or tape is None or len(tape) == 0:
        return 0
    path = ensure_tables(db_path)
    frame = tape.copy()
    idx = pd.to_datetime(frame.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("Asia/Kolkata")
    frame = frame.copy()
    frame["_day"] = idx.date
    name = stock.strip().upper()
    now = datetime.now().isoformat(timespec="seconds")
    conn = _connect(path)
    saved = 0
    for day, sess in frame.groupby("_day"):
        if sess is None or len(sess) == 0:
            continue
        close_col = "Close" if "Close" in sess.columns else "close"
        open_col = "Open" if "Open" in sess.columns else "open"
        high_col = "High" if "High" in sess.columns else "high"
        low_col = "Low" if "Low" in sess.columns else "low"
        vol_col = "Volume" if "Volume" in sess.columns else ("volume" if "volume" in sess.columns else None)
        if close_col not in sess.columns:
            continue
        chain = conn.execute(
            """
            SELECT pcr, ce_oi, pe_oi, iv_atm, fut_basis, vix_level
            FROM chain_snapshots
            WHERE stock = ? AND session_date = ?
            ORDER BY bar_ts DESC LIMIT 1
            """,
            (name, str(day)),
        ).fetchone()
        pcr = ce = pe = iv = basis = vix = None
        if chain:
            pcr, ce, pe, iv, basis, vix = chain
        volume = float(sess[vol_col].fillna(0).sum()) if vol_col else None
        conn.execute(
            """
            INSERT INTO ml_session_days (
                stock, session_date, open, high, low, close, volume,
                pcr, ce_oi, pe_oi, iv_atm, fut_basis, vix_level, saved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stock, session_date) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume,
                pcr=COALESCE(excluded.pcr, ml_session_days.pcr),
                ce_oi=COALESCE(excluded.ce_oi, ml_session_days.ce_oi),
                pe_oi=COALESCE(excluded.pe_oi, ml_session_days.pe_oi),
                iv_atm=COALESCE(excluded.iv_atm, ml_session_days.iv_atm),
                fut_basis=COALESCE(excluded.fut_basis, ml_session_days.fut_basis),
                vix_level=COALESCE(excluded.vix_level, ml_session_days.vix_level),
                saved_at=excluded.saved_at
            """,
            (
                name, str(day),
                float(sess[open_col].iloc[0]),
                float(sess[high_col].max()),
                float(sess[low_col].min()),
                float(sess[close_col].iloc[-1]),
                volume, pcr, ce, pe, iv, basis, vix, now,
            ),
        )
        saved += 1
    conn.commit()
    conn.close()
    return saved


def save_morning_report(payload: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """Persist each symbol row from a morning_premarket_brief JSON report."""
    path = ensure_tables(db_path)
    gen = str(payload.get("generated_at") or datetime.now().isoformat())
    report_key = gen[:19].replace(":", "-")
    session_day = gen[:10]
    now = datetime.now().isoformat()
    n = 0
    conn = _connect(path)
    for row in payload.get("stocks") or []:
        sym = str(row.get("symbol") or "").strip().upper()
        if not sym:
            continue
        dr = _dr(row)
        hi = dr.get("session_expected_high", dr.get("expected_high"))
        lo = dr.get("session_expected_low", dr.get("expected_low"))
        vix = None
        try:
            vix = float(((row.get("full") or {}).get("india_market_context") or {}).get("india_vix", {}).get("level"))
        except (TypeError, ValueError):
            vix = None
        slim = {k: v for k, v in row.items() if k != "full"}
        conn.execute(
            """
            INSERT INTO morning_briefs (
                session_date, stock, report_key, generated_at, ref_close,
                expected_low, expected_high, trade_low, trade_high, forecast_method,
                locked, decision, confidence, signal_quality, vix_level,
                payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_date, stock, report_key) DO UPDATE SET
                generated_at=excluded.generated_at,
                ref_close=excluded.ref_close,
                expected_low=excluded.expected_low,
                expected_high=excluded.expected_high,
                trade_low=excluded.trade_low,
                trade_high=excluded.trade_high,
                forecast_method=excluded.forecast_method,
                locked=excluded.locked,
                decision=excluded.decision,
                confidence=excluded.confidence,
                signal_quality=excluded.signal_quality,
                vix_level=excluded.vix_level,
                payload_json=excluded.payload_json
            """,
            (
                session_day,
                sym,
                report_key,
                gen,
                row.get("current_price"),
                lo,
                hi,
                dr.get("expected_low"),
                dr.get("expected_high"),
                dr.get("method"),
                1 if dr.get("locked") else 0,
                row.get("decision"),
                row.get("confidence"),
                row.get("signal_quality"),
                vix,
                json.dumps(slim, default=str),
                now,
            ),
        )
        n += 1
    conn.commit()
    conn.close()
    return n


def import_morning_reports_dir(report_dir: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    path = ensure_tables(db_path)
    if not os.path.isdir(report_dir):
        return {"ok": False, "error": "no report dir"}
    files = sorted(
        f for f in os.listdir(report_dir) if f.startswith("report_") and f.endswith(".json")
    )
    total = 0
    for name in files:
        try:
            with open(os.path.join(report_dir, name), encoding="utf-8") as fh:
                payload = json.load(fh)
            total += save_morning_report(payload, path)
        except Exception:
            continue
    latest = os.path.join(report_dir, "latest.json")
    if os.path.isfile(latest):
        try:
            with open(latest, encoding="utf-8") as fh:
                total += save_morning_report(json.load(fh), path)
        except Exception:
            pass
    return {"ok": True, "rows_upserted": total, "files": len(files)}


def _session_from_15m_csv(symbol: str, session_date: str) -> Optional[Dict[str, float]]:
    if pd is None:
        return None
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_signal_data", "fno_validate")
    for name in (f"{symbol}_15m_5y.csv", f"{symbol}_15m_6m.csv", f"{symbol}_15m.csv"):
        p = os.path.join(root, name)
        if not os.path.isfile(p):
            continue
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        colmap = {str(c).lower(): c for c in df.columns}
        for src, dst in (("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close")):
            if dst not in df.columns and src in colmap:
                df[dst] = df[colmap[src]]
        day = pd.Timestamp(session_date).date()
        mask = [pd.Timestamp(i).date() == day for i in df.index]
        sess = df.loc[mask]
        if len(sess) < 2:
            continue
        o = float(sess["Open"].astype(float).iloc[0])
        h = float(sess["High"].astype(float).max())
        l = float(sess["Low"].astype(float).min())
        c = float(sess["Close"].astype(float).iloc[-1])
        or_hi = float(sess["High"].astype(float).iloc[0])
        or_lo = float(sess["Low"].astype(float).iloc[0])
        return {
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "or_high": or_hi,
            "or_low": or_lo,
            "bar_count": float(len(sess)),
        }
    return None


def _session_from_daily_cache(symbol: str, session_date: str) -> Optional[Dict[str, float]]:
    if pd is None:
        return None
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_signal_data", "cache")
    sym = symbol.upper()
    p = os.path.join(cache, f"{sym}_NS.csv")
    if not os.path.isfile(p):
        p = os.path.join(cache, f"{sym}.csv")
    if not os.path.isfile(p):
        return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    colmap = {str(c).lower(): c for c in df.columns}
    for src, dst in (("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close")):
        if dst not in df.columns and src in colmap:
            df[dst] = df[colmap[src]]
    day = pd.Timestamp(session_date).date()
    for i in df.index:
        if pd.Timestamp(i).date() == day:
            row = df.loc[i]
            return {
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "or_high": float(row["High"]),
                "or_low": float(row["Low"]),
                "bar_count": 1.0,
            }
    return None


def resolve_session_ohlc(symbol: str, session_date: str) -> Optional[Dict[str, float]]:
    sym = symbol.strip().upper()
    if sym in ("NIFTY", "BANKNIFTY", "FINNIFTY"):
        return _session_from_15m_csv(sym, session_date)
    return _session_from_daily_cache(sym, session_date) or _session_from_15m_csv(sym, session_date)


def upsert_bar_session(
    db_path: str,
    *,
    stock: str,
    session_date: str,
    interval: str,
    ohlc: Dict[str, float],
    source: str = "tape",
) -> None:
    ensure_tables(db_path)
    now = datetime.now().isoformat()
    conn = _connect(db_path)
    conn.execute(
        """
        INSERT INTO market_bar_sessions (
            session_date, stock, interval, bar_count, open, high, low, close, volume,
            or_high, or_low, source, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_date, stock, interval) DO UPDATE SET
            bar_count=excluded.bar_count,
            open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close,
            or_high=excluded.or_high, or_low=excluded.or_low,
            source=excluded.source, updated_at=excluded.updated_at
        """,
        (
            session_date[:10],
            stock.strip().upper(),
            interval,
            int(ohlc.get("bar_count") or 0),
            ohlc.get("open"),
            ohlc.get("high"),
            ohlc.get("low"),
            ohlc.get("close"),
            ohlc.get("volume"),
            ohlc.get("or_high"),
            ohlc.get("or_low"),
            source,
            now,
        ),
    )
    conn.commit()
    conn.close()


def score_morning_briefs(
    db_path: Optional[str] = None,
    *,
    session_dates: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Fill actual H/L and inside-box flags for morning rows."""
    path = ensure_tables(db_path)
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    if session_dates:
        placeholders = ",".join("?" * len(session_dates))
        rows = conn.execute(
            f"""
            SELECT * FROM morning_briefs
            WHERE session_date IN ({placeholders}) AND scored_at IS NULL
            """,
            session_dates,
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM morning_briefs WHERE scored_at IS NULL ORDER BY session_date DESC LIMIT 200"
        ).fetchall()
    scored = 0
    now = datetime.now().isoformat()
    for r in rows:
        day = str(r["session_date"])
        sym = str(r["stock"])
        act = resolve_session_ohlc(sym, day)
        if not act:
            continue
        conn.execute(
            """
            INSERT INTO market_bar_sessions (
                session_date, stock, interval, bar_count, open, high, low, close, volume,
                or_high, or_low, source, updated_at
            ) VALUES (?, ?, '15minute', ?, ?, ?, ?, ?, ?, ?, ?, 'score', ?)
            ON CONFLICT(session_date, stock, interval) DO UPDATE SET
                bar_count=excluded.bar_count,
                open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close,
                or_high=excluded.or_high, or_low=excluded.or_low,
                source=excluded.source, updated_at=excluded.updated_at
            """,
            (
                day[:10],
                sym,
                int(act.get("bar_count") or 0),
                act.get("open"),
                act.get("high"),
                act.get("low"),
                act.get("close"),
                act.get("volume"),
                act.get("or_high"),
                act.get("or_low"),
                now,
            ),
        )
        t_lo = r["trade_low"] if r["trade_low"] is not None else r["expected_low"]
        t_hi = r["trade_high"] if r["trade_high"] is not None else r["expected_high"]
        f_lo = r["expected_low"]
        f_hi = r["expected_high"]
        ah, al = float(act["high"]), float(act["low"])
        inside_trade = None
        inside_forecast = None
        if t_lo is not None and t_hi is not None:
            inside_trade = int(ah <= float(t_hi) + 0.05 and al >= float(t_lo) - 0.05)
        if f_lo is not None and f_hi is not None:
            inside_forecast = int(ah <= float(f_hi) + 0.05 and al >= float(f_lo) - 0.05)
        hi_miss = None
        lo_miss = None
        if t_hi is not None:
            hi_miss = round(max(0.0, ah - float(t_hi)), 2)
        if t_lo is not None:
            lo_miss = round(max(0.0, float(t_lo) - al), 2)
        conn.execute(
            """
            UPDATE morning_briefs SET
                actual_open=?, actual_high=?, actual_low=?, actual_close=?,
                inside_trade_box=?, inside_forecast=?,
                high_miss_pts=?, low_miss_pts=?, scored_at=?
            WHERE id=?
            """,
            (
                act.get("open"),
                ah,
                al,
                act.get("close"),
                inside_trade,
                inside_forecast,
                hi_miss,
                lo_miss,
                now,
                r["id"],
            ),
        )
        scored += 1
    conn.commit()
    conn.close()
    return {"ok": True, "scored": scored}


def range_accuracy_summary(
    db_path: Optional[str] = None,
    *,
    last_days: int = 7,
) -> Dict[str, Any]:
    path = ensure_tables(db_path)
    cutoff = (date.today() - timedelta(days=last_days)).isoformat()
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT * FROM morning_briefs
        WHERE session_date >= ? AND scored_at IS NOT NULL
        ORDER BY session_date DESC, stock
        """,
        (cutoff,),
    ).fetchall()
    conn.close()
    by_stock: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_stock.setdefault(r["stock"], []).append(dict(r))
    summary: Dict[str, Any] = {"from_date": cutoff, "stocks": {}}
    for sym, items in sorted(by_stock.items()):
        n = len(items)
        trade_ok = sum(1 for x in items if x.get("inside_trade_box") == 1)
        fc_ok = sum(1 for x in items if x.get("inside_forecast") == 1)
        summary["stocks"][sym] = {
            "days_scored": n,
            "trade_box_inside_pct": round(trade_ok / n, 4) if n else None,
            "forecast_inside_pct": round(fc_ok / n, 4) if n else None,
            "rows": [
                {
                    "session_date": x["session_date"],
                    "expected_low": x["expected_low"],
                    "expected_high": x["expected_high"],
                    "actual_low": x["actual_low"],
                    "actual_high": x["actual_high"],
                    "inside_trade_box": x.get("inside_trade_box"),
                }
                for x in items
            ],
        }
    return summary


def log_train_run(
    db_path: str,
    job: str,
    *,
    started_at: str,
    finished_at: str,
    symbols: List[str],
    metrics: Dict[str, Any],
    ok: bool,
    notes: str = "",
) -> None:
    ensure_tables(db_path)
    conn = _connect(db_path)
    conn.execute(
        """
        INSERT INTO model_train_runs (job, started_at, finished_at, symbols_json, metrics_json, ok, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job,
            started_at,
            finished_at,
            json.dumps(symbols),
            json.dumps(metrics, default=str),
            1 if ok else 0,
            notes,
        ),
    )
    conn.commit()
    conn.close()


def heartbeat(db_path: str, phase: str, detail: Optional[Dict[str, Any]] = None) -> None:
    ensure_tables(db_path)
    conn = _connect(db_path)
    conn.execute(
        "INSERT INTO agent_heartbeats (beat_at, phase, detail_json) VALUES (?, ?, ?)",
        (datetime.now().isoformat(), phase, json.dumps(detail or {}, default=str)),
    )
    conn.commit()
    conn.close()


def should_notify(db_path: str, dedupe_key: str) -> bool:
    ensure_tables(db_path)
    conn = _connect(db_path)
    row = conn.execute("SELECT 1 FROM notify_dedupe WHERE dedupe_key=?", (dedupe_key,)).fetchone()
    conn.close()
    return row is None


def mark_notified(
    db_path: str,
    dedupe_key: str,
    *,
    stock: str,
    decision: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    ensure_tables(db_path)
    conn = _connect(db_path)
    conn.execute(
        """
        INSERT INTO notify_dedupe (dedupe_key, notified_at, stock, decision, payload_json)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(dedupe_key) DO NOTHING
        """,
        (
            dedupe_key,
            datetime.now().isoformat(),
            stock,
            decision,
            json.dumps(payload or {}, default=str),
        ),
    )
    conn.commit()
    conn.close()
