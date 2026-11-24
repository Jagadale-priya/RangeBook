"""US dark-pool index (SqueezeMetrics DIX) joined to Indian sessions without lookahead.

NSE has no FINRA-style dark pool. The public series is S&P 500 short-volume DIX.
A NIFTY bar on date D only sees the last US print strictly before D.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

import path_setup
ROOT = str(path_setup.ROOT)
DIR = os.path.join(ROOT, "stock_signal_data", "dark_pool")
DIX_CSV = os.path.join(DIR, "DIX.csv")
DIX_URL = "https://squeezemetrics.com/monitor/static/DIX.csv"

_series: Optional[list] = None


def _load_series() -> list:
    """Sorted (date, dix) from the local SqueezeMetrics file."""
    global _series
    if _series is not None:
        return _series
    rows = []
    if os.path.isfile(DIX_CSV):
        with open(DIX_CSV, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                day = str(row.get("date") or "")[:10]
                val = _parse_dix(row.get("dix"))
                if day and val is not None:
                    rows.append((day, val))
    rows.sort()
    _series = rows
    return rows


def dix_before(session_date) -> Optional[Dict[str, Any]]:
    """Last US DIX strictly before this session date. None if the file has no earlier row."""
    day = str(session_date)[:10]
    if len(day) < 10:
        return None
    series = _load_series()
    if not series:
        return None
    lo, hi = 0, len(series)
    while lo < hi:
        mid = (lo + hi) // 2
        if series[mid][0] < day:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return None
    prev_day, val = series[lo - 1]
    return {
        "dix": val,
        "session_date": prev_day,
        "source": "squeezemetrics_spx",
        "note": "S&P 500 dark-pool short-volume index, lagged so the Indian session cannot see the same-day US close.",
    }


def import_public_series(db_path: Optional[str] = None) -> int:
    """Copy the CSV into dark_pool_daily as stock SPX."""
    import knowledge_db
    import training_store

    series = _load_series()
    if not series:
        return 0
    path = training_store.ensure_tables(db_path or knowledge_db.ensure_db_dir())
    now = datetime.now().isoformat()
    conn = training_store._connect(path)
    conn.executemany(
        """
        INSERT INTO dark_pool_daily (session_date, stock, dix, source, note, updated_at)
        VALUES (?, 'SPX', ?, 'squeezemetrics_spx', 'US DIX', ?)
        ON CONFLICT(session_date, stock) DO UPDATE SET
            dix=excluded.dix, source=excluded.source, updated_at=excluded.updated_at
        """,
        [(day, val, now) for day, val in series],
    )
    conn.commit()
    conn.close()
    return len(series)


def _parse_dix(raw: Any) -> Optional[float]:
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if val > 1.5:
        val = val / 100.0
    if val < 0 or val > 1.5:
        return None
    return round(val, 4)


def upsert(
    stock: str,
    session_date: str,
    dix: float,
    *,
    source: str = "manual",
    note: str = "",
    db_path: Optional[str] = None,
) -> None:
    import knowledge_db
    import training_store

    path = training_store.ensure_tables(db_path or knowledge_db.ensure_db_dir())
    val = _parse_dix(dix)
    if val is None:
        return
    conn = training_store._connect(path)
    conn.execute(
        """
        INSERT INTO dark_pool_daily (session_date, stock, dix, source, note, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_date, stock) DO UPDATE SET
            dix=excluded.dix, source=excluded.source, note=excluded.note, updated_at=excluded.updated_at
        """,
        (
            str(session_date)[:10],
            stock.strip().upper(),
            val,
            source,
            note,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def _from_csv(symbol: str, day: Optional[str]) -> Optional[Dict[str, Any]]:
    path = os.path.join(DIR, f"{symbol}.csv")
    if not os.path.isfile(path):
        return None
    best = None
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            raw_day = str(row.get("date") or row.get("session_date") or "")[:10]
            val = _parse_dix(row.get("dix"))
            if not raw_day or val is None:
                continue
            if day and raw_day > day:
                continue
            if best is None or raw_day >= best["session_date"]:
                best = {"session_date": raw_day, "dix": val, "source": "csv"}
    return best


def _from_db(symbol: str, day: Optional[str], db_path: Optional[str]) -> Optional[Dict[str, Any]]:
    import knowledge_db
    import training_store

    path = db_path or knowledge_db.default_db_path()
    if not os.path.isfile(path):
        return None
    training_store.ensure_tables(path)
    conn = training_store._connect(path)
    conn.row_factory = __import__("sqlite3").Row
    if day:
        row = conn.execute(
            """
            SELECT session_date, dix, source FROM dark_pool_daily
            WHERE stock = ? AND session_date <= ?
            ORDER BY session_date DESC LIMIT 1
            """,
            (symbol, day),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT session_date, dix, source FROM dark_pool_daily
            WHERE stock = ?
            ORDER BY session_date DESC LIMIT 1
            """,
            (symbol,),
        ).fetchone()
    conn.close()
    if not row:
        return None
    return {"session_date": row["session_date"], "dix": float(row["dix"]), "source": row["source"] or "db"}


def _today_ist() -> str:
    now = datetime.now(ZoneInfo("Asia/Kolkata")) if ZoneInfo else datetime.now()
    return now.date().isoformat()


def latest(symbol: str, *, session_date: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Symbol row on or before the Indian session. The US series stays strictly before that date."""
    sym = (symbol or "").strip().upper()
    day = str(session_date)[:10] if session_date else _today_ist()
    hit = _from_db(sym, day, db_path) or _from_csv(sym, day)
    if not hit:
        lagged = dix_before(day)
        if lagged:
            return {
                "available": True,
                "symbol": sym,
                "dix": lagged["dix"],
                "session_date": lagged["session_date"],
                "source": lagged["source"],
                "note": lagged["note"],
            }
        return {
            "available": False,
            "symbol": sym,
            "reason": "no_dark_pool_feed",
            "note": "US DIX file is missing. Expected stock_signal_data/dark_pool/DIX.csv.",
        }
    return {
        "available": True,
        "symbol": sym,
        "dix": hit["dix"],
        "session_date": hit["session_date"],
        "source": hit["source"],
    }
