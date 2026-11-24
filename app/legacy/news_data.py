"""
Market news storage and ingest (free sources).

  1. Downstox public overview — Indian market headlines (no API key)
  2. NSE corporate announcements — exchange filings per symbol (session cookie)
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    requests = None  # type: ignore

import nse_session

DOWNSTOX_OVERVIEW_URL = "https://downstox.com/api/india-markets/overview"
NSE_ANNOUNCEMENTS_URL = "https://www.nseindia.com/api/corporate-announcements"
USER_AGENT = nse_session.USER_AGENT

INDEX_SYMBOLS = frozenset({"NIFTY", "BANKNIFTY", "SENSEX"})
NSE_REQUEST_DELAY_SEC = 0.4


def default_news_db_path(base_dir: str) -> str:
    return os.path.join(base_dir, "news.db")


def setup_news_database(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS news_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            published_at TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            source TEXT NOT NULL,
            url TEXT,
            item_type TEXT NOT NULL,
            external_id TEXT NOT NULL,
            ingested_at TEXT NOT NULL,
            UNIQUE(source, external_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_symbol_published ON news_items(symbol, published_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at DESC)"
    )
    conn.commit()
    conn.close()


def _parse_nse_an_dt(raw: str) -> Optional[str]:
    if not raw:
        return None
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).isoformat()
        except ValueError:
            continue
    return None


def _parse_iso_dt(raw: str) -> Optional[str]:
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def _insert_items(db_path: str, rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    now = datetime.now().isoformat()
    conn = sqlite3.connect(db_path)
    inserted = 0
    for row in rows:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO news_items
            (symbol, published_at, title, summary, source, url, item_type, external_id, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["symbol"],
                row["published_at"],
                row["title"],
                row.get("summary"),
                row["source"],
                row.get("url"),
                row["item_type"],
                row["external_id"],
                now,
            ),
        )
        if cur.rowcount:
            inserted += 1
    conn.commit()
    conn.close()
    return inserted


def fetch_downstox_overview_market_news() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    if requests is None:
        return [], "requests package not installed"
    try:
        r = requests.get(
            DOWNSTOX_OVERVIEW_URL,
            timeout=25,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        payload = r.json()
        if not payload.get("success", True) and not payload.get("news"):
            return [], "overview response not successful"
        items = []
        for entry in payload.get("news") or []:
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            pub = _parse_iso_dt(entry.get("pubDate") or "") or datetime.now().isoformat()
            link = entry.get("link") or ""
            ext = hashlib.sha256(link.encode("utf-8")).hexdigest()[:32] if link else hashlib.sha256(title.encode("utf-8")).hexdigest()[:32]
            items.append(
                {
                    "symbol": "MARKET",
                    "published_at": pub,
                    "title": title,
                    "summary": (entry.get("description") or "")[:4000] or None,
                    "source": entry.get("source") or "downstox_overview",
                    "url": link or None,
                    "item_type": "headline",
                    "external_id": f"downstox:{ext}",
                }
            )
        return items, None
    except Exception as exc:
        return [], str(exc)


def ingest_downstox_overview(db_path: str) -> Dict[str, Any]:
    items, err = fetch_downstox_overview_market_news()
    added = _insert_items(db_path, items)
    return {
        "source": "downstox_overview",
        "fetched": len(items),
        "inserted": added,
        "error": err,
    }


def _nse_date_str(d: date) -> str:
    return d.strftime("%d-%m-%Y")


def _month_chunks(start: date, end: date) -> List[Tuple[date, date]]:
    chunks: List[Tuple[date, date]] = []
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        last_day = monthrange(y, m)[1]
        chunk_start = date(y, m, 1)
        if chunk_start < start:
            chunk_start = start
        chunk_end = date(y, m, last_day)
        if chunk_end > end:
            chunk_end = end
        if chunk_start <= chunk_end:
            chunks.append((chunk_start, chunk_end))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return chunks


def fetch_nse_announcements(
    symbol: str,
    from_date: date,
    to_date: date,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    if requests is None:
        return [], "requests package not installed"
    sym = symbol.strip().upper()
    if sym in INDEX_SYMBOLS:
        return [], None
    session = nse_session.nse_session()
    if session is None:
        return [], "NSE session unavailable (403 or network)"
    params = {
        "index": "equities",
        "from_date": _nse_date_str(from_date),
        "to_date": _nse_date_str(to_date),
        "symbol": sym,
        "reqXbrl": "false",
    }
    try:
        r = session.get(NSE_ANNOUNCEMENTS_URL, params=params, timeout=6)
        if r.status_code == 403:
            nse_session.reset_session()
            return [], "NSE 403 — retry later"
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        data = r.json()
        if not isinstance(data, list):
            return [], "unexpected NSE payload"
        rows = []
        for item in data:
            title_part = (item.get("desc") or "Announcement").strip()
            body = (item.get("attchmntText") or "").strip()
            title = f"{title_part}: {body[:120]}..." if len(body) > 120 else (f"{title_part}: {body}" if body else title_part)
            pub = _parse_nse_an_dt(item.get("an_dt") or item.get("sort_date") or "")
            if not pub:
                continue
            seq = item.get("seq_id")
            ext = f"nse:{seq}" if seq is not None else hashlib.sha256(f"{sym}:{pub}:{title}".encode()).hexdigest()[:24]
            rows.append(
                {
                    "symbol": sym,
                    "published_at": pub,
                    "title": title[:500],
                    "summary": body[:4000] or None,
                    "source": "nse_announcements",
                    "url": item.get("attchmntFile") or None,
                    "item_type": "filing",
                    "external_id": str(ext),
                }
            )
        return rows, None
    except Exception as exc:
        return [], str(exc)


def prefetch_symbol_nse(
    db_path: str,
    symbol: str,
    years: float = 5,
    max_months: Optional[int] = None,
) -> Dict[str, Any]:
    sym = symbol.strip().upper()
    if sym in INDEX_SYMBOLS:
        return {"symbol": sym, "skipped": True, "reason": "index symbol"}

    end = date.today()
    start = end - timedelta(days=int(years * 365.25))
    chunks = _month_chunks(start, end)
    if max_months is not None:
        chunks = chunks[-max_months:]

    fetched = 0
    inserted = 0
    errors: List[str] = []
    for chunk_start, chunk_end in chunks:
        items, err = fetch_nse_announcements(sym, chunk_start, chunk_end)
        fetched += len(items)
        inserted += _insert_items(db_path, items)
        if err:
            errors.append(f"{chunk_start:%Y-%m}:{err}")
        time.sleep(NSE_REQUEST_DELAY_SEC)

    return {
        "symbol": sym,
        "months_scanned": len(chunks),
        "fetched": fetched,
        "inserted": inserted,
        "errors": errors[:5],
        "error_count": len(errors),
    }


def prefetch_watchlist_news(
    db_path: str,
    watchlist: List[Dict[str, str]],
    years: float = 5,
    include_market_headlines: bool = True,
    max_months_per_symbol: Optional[int] = None,
) -> Dict[str, Any]:
    setup_news_database(db_path)
    summary: Dict[str, Any] = {
        "db_path": db_path,
        "years": years,
        "symbols": [],
    }
    if include_market_headlines:
        summary["market_headlines"] = ingest_downstox_overview(db_path)

    results = []
    session_fails = 0
    for item in watchlist:
        sym = item.get("symbol") or item.get("stock") or ""
        if not sym:
            continue
        print(f"  News prefetch {sym}...")
        row = prefetch_symbol_nse(
            db_path,
            sym,
            years=years,
            max_months=max_months_per_symbol,
        )
        results.append(row)
        err = " ".join(str(e) for e in (row.get("errors") or []))
        if "403" in err or "session unavailable" in err.lower():
            session_fails += 1
        else:
            session_fails = 0
        if session_fails >= 2:
            summary["aborted"] = "NSE news session failed; skipped the rest of the watchlist"
            break
    summary["symbols"] = results
    summary["stats"] = get_news_stats(db_path)
    return summary


def get_news(
    db_path: str,
    symbol: Optional[str] = None,
    limit: int = 50,
    item_type: Optional[str] = None,
    include_market: bool = True,
) -> List[Dict[str, Any]]:
    if not os.path.exists(db_path):
        return []
    limit = max(1, min(int(limit), 200))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    clauses: List[str] = []
    params: List[Any] = []

    if symbol:
        sym = symbol.strip().upper()
        if include_market:
            clauses.append("(symbol = ? OR symbol = 'MARKET')")
            params.append(sym)
        else:
            clauses.append("symbol = ?")
            params.append(sym)

    if item_type:
        clauses.append("item_type = ?")
        params.append(item_type)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM news_items{where} ORDER BY published_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_news_as_of(
    db_path: str,
    symbol: str,
    as_of: Any,
    limit: int = 8,
    cutoff_hour: int = 15,
    cutoff_minute: int = 30,
) -> List[Dict[str, Any]]:
    """News known at the as_of decision time (point-in-time for audit).

    Cuts off at the market close (15:30 IST) rather than midnight: NSE files most
    corporate announcements after the close, so including the whole day would let
    news the trader could not have seen drive that day's decision.
    """
    if not os.path.isfile(db_path):
        return []
    if isinstance(as_of, str):
        day = datetime.fromisoformat(as_of[:10])
    else:
        day = datetime(as_of.year, as_of.month, as_of.day)
    end_iso = day.replace(hour=cutoff_hour, minute=cutoff_minute).isoformat()
    sym = symbol.strip().upper()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT title, summary, published_at, source, url, item_type
        FROM news_items
        WHERE symbol = ? AND published_at < ?
        ORDER BY published_at DESC
        LIMIT ?
        """,
        (sym, end_iso, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_for_symbol(db_path: str, symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
    items = get_news(db_path, symbol=symbol, limit=limit, include_market=False)
    if len(items) < limit:
        market = get_news(db_path, symbol="MARKET", limit=limit, include_market=False)
        seen = {i["id"] for i in items}
        for m in market:
            if m["id"] not in seen:
                items.append(m)
            if len(items) >= limit:
                break
    return items[:limit]


def get_news_stats(db_path: str) -> Dict[str, Any]:
    if not os.path.exists(db_path):
        return {
            "total_items": 0,
            "by_type": {},
            "by_symbol": {},
            "earliest": None,
            "latest": None,
            "db_path": db_path,
        }
    conn = sqlite3.connect(db_path)
    total = conn.execute("SELECT COUNT(*) FROM news_items").fetchone()[0]
    by_type = dict(conn.execute(
        "SELECT item_type, COUNT(*) FROM news_items GROUP BY item_type"
    ).fetchall())
    by_symbol = dict(
        conn.execute(
            "SELECT symbol, COUNT(*) FROM news_items GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 25"
        ).fetchall()
    )
    earliest, latest = conn.execute(
        "SELECT MIN(published_at), MAX(published_at) FROM news_items"
    ).fetchone()
    conn.close()
    return {
        "total_items": total,
        "by_type": by_type,
        "by_symbol": by_symbol,
        "earliest": earliest,
        "latest": latest,
        "db_path": db_path,
    }
