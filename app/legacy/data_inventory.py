"""Audit OHLCV + news coverage, remove corrupt/unused cache, backfill gaps."""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import pandas as pd

import news_data

INDEX_SYMBOLS = frozenset({"NIFTY", "BANKNIFTY", "SENSEX"})

# ~252 sessions/year; 5y ≈ 1260 rows
MIN_OHLCV_ROWS = 750
MIN_SPAN_YEARS = 4.2
MIN_NEWS_SPAN_YEARS = 4.0
MIN_NEWS_ITEMS = 20

CACHE_KEEP_PREFIXES = (
    "regime_",
    "kite_",
    "exchange_",
    "nfo_",
)


def _expected_cache_names(watchlist: List[Dict[str, Any]], resolve_fn: Callable) -> Set[str]:
    names: Set[str] = set()
    for item in watchlist:
        key = (item.get("symbol") or "").strip().upper()
        yahoo = resolve_fn(key)
        safe = yahoo.replace("^", "IDX_").replace(".", "_")
        names.add(f"{safe}.csv")
    return names


def audit_ohlcv_cache(
    cache_dir: str,
    watchlist: List[Dict[str, Any]],
    resolve_fn: Callable,
    cache_row_stats_fn: Callable,
    configured_years: float = 5,
) -> Dict[str, Any]:
    """Per-symbol OHLCV cache health."""
    target_start = date.today() - timedelta(days=int(configured_years * 365.25))
    symbols: List[Dict[str, Any]] = []
    ok = 0
    for item in watchlist:
        key = (item.get("symbol") or "").strip().upper()
        yahoo = resolve_fn(key)
        row = cache_row_stats_fn(yahoo, stock_key=key)
        status = "ok"
        issues: List[str] = []
        if row.get("error"):
            status = "corrupt"
            issues.append(row["error"])
        elif not row.get("cached"):
            status = "missing"
            issues.append("no cache file")
        else:
            rows_n = int(row.get("rows") or 0)
            span = row.get("span_years")
            if rows_n < MIN_OHLCV_ROWS:
                status = "short"
                issues.append(f"rows={rows_n} (<{MIN_OHLCV_ROWS})")
            if span is not None and span < MIN_SPAN_YEARS:
                status = "short" if status == "ok" else status
                issues.append(f"span={span}y (<{MIN_SPAN_YEARS}y)")
            start_s = row.get("start_date") or ""
            if start_s:
                try:
                    start_d = datetime.fromisoformat(start_s[:10]).date()
                    if start_d > target_start + timedelta(days=120):
                        status = "short" if status == "ok" else status
                        issues.append(f"starts {start_s} (need ~{target_start.isoformat()})")
                except ValueError:
                    pass
        if status == "ok":
            ok += 1
        symbols.append({**row, "status": status, "issues": issues})
    return {
        "configured_years": configured_years,
        "target_start_approx": target_start.isoformat(),
        "ok_count": ok,
        "watchlist_count": len(watchlist),
        "symbols": symbols,
    }


def audit_news_db(db_path: str, watchlist: List[Dict[str, Any]], years: float = 5) -> Dict[str, Any]:
    """Per-symbol news coverage in news.db."""
    if not os.path.isfile(db_path):
        return {"ready": False, "db_path": db_path, "symbols": []}
    target_start = date.today() - timedelta(days=int(years * 365.25))
    conn = sqlite3.connect(db_path)
    symbols: List[Dict[str, Any]] = []
    ok = 0
    for item in watchlist:
        key = (item.get("symbol") or "").strip().upper()
        if key in INDEX_SYMBOLS:
            symbols.append(
                {
                    "symbol": key,
                    "status": "n/a",
                    "reason": "index — NSE filings not per index symbol",
                    "count": 0,
                }
            )
            continue
        row = conn.execute(
            """
            SELECT COUNT(*), MIN(published_at), MAX(published_at)
            FROM news_items WHERE symbol = ?
            """,
            (key,),
        ).fetchone()
        count, earliest, latest = int(row[0] or 0), row[1], row[2]
        status = "ok"
        issues: List[str] = []
        if count < MIN_NEWS_ITEMS:
            status = "sparse"
            issues.append(f"count={count}")
        if earliest:
            try:
                est = datetime.fromisoformat(str(earliest)[:19]).date()
                span_y = (date.today() - est).days / 365.25
                if span_y < MIN_NEWS_SPAN_YEARS:
                    status = "short" if status == "ok" else status
                    issues.append(f"earliest={earliest[:10]} ({span_y:.1f}y)")
                if est > target_start + timedelta(days=180):
                    status = "short" if status == "ok" else status
                    issues.append(f"need data from ~{target_start.isoformat()}")
            except ValueError:
                pass
        else:
            status = "missing"
            issues.append("no rows")
        if status == "ok":
            ok += 1
        symbols.append(
            {
                "symbol": key,
                "count": count,
                "earliest": earliest,
                "latest": latest,
                "status": status,
                "issues": issues,
            }
        )
    total = conn.execute("SELECT COUNT(*) FROM news_items").fetchone()[0]
    conn.close()
    return {
        "db_path": db_path,
        "years_target": years,
        "target_start_approx": target_start.isoformat(),
        "total_items": total,
        "ok_count": ok,
        "symbols": symbols,
    }


def find_orphan_cache_files(cache_dir: str, watchlist: List[Dict[str, Any]], resolve_fn: Callable) -> List[str]:
    expected = _expected_cache_names(watchlist, resolve_fn)
    orphans: List[str] = []
    if not os.path.isdir(cache_dir):
        return orphans
    for name in os.listdir(cache_dir):
        if not name.endswith(".csv"):
            continue
        if any(name.startswith(p) for p in CACHE_KEEP_PREFIXES):
            continue
        if name not in expected:
            orphans.append(name)
    return sorted(orphans)


def cleanup_cache(
    cache_dir: str,
    watchlist: List[Dict[str, Any]],
    resolve_fn: Callable,
    cache_row_stats_fn: Callable,
    *,
    remove_orphans: bool = True,
    remove_corrupt: bool = True,
    remove_short: bool = False,
) -> Dict[str, Any]:
    """Remove corrupt OHLCV caches and optional orphan symbol files."""
    removed: List[Dict[str, str]] = []
    audit = audit_ohlcv_cache(cache_dir, watchlist, resolve_fn, cache_row_stats_fn)
    for sym in audit["symbols"]:
        path = os.path.join(cache_dir, sym.get("cache_file") or "")
        if not sym.get("cache_file"):
            continue
        full = os.path.join(cache_dir, sym["cache_file"])
        if remove_corrupt and sym["status"] == "corrupt" and os.path.isfile(full):
            os.remove(full)
            removed.append({"file": sym["cache_file"], "reason": "corrupt"})
        elif remove_short and sym["status"] == "short" and os.path.isfile(full):
            os.remove(full)
            removed.append({"file": sym["cache_file"], "reason": "short"})
    if remove_orphans:
        for name in find_orphan_cache_files(cache_dir, watchlist, resolve_fn):
            full = os.path.join(cache_dir, name)
            try:
                os.remove(full)
                removed.append({"file": name, "reason": "orphan"})
            except OSError:
                pass
    return {"removed": removed, "removed_count": len(removed)}


def repair_data_gaps(
    watchlist: List[Dict[str, Any]],
    cache_dir: str,
    news_db_path: str,
    resolve_fn: Callable,
    download_fn: Callable,
    cache_row_stats_fn: Callable,
    news_prefetch_fn: Callable,
    *,
    years: float = 5,
    force_ohlcv: bool = False,
) -> Dict[str, Any]:
    """Clean bad caches, re-download OHLCV/news where audit failed."""
    cleanup = cleanup_cache(
        cache_dir,
        watchlist,
        resolve_fn,
        cache_row_stats_fn,
        remove_orphans=True,
        remove_corrupt=True,
        remove_short=force_ohlcv,
    )
    ohlcv_before = audit_ohlcv_cache(cache_dir, watchlist, resolve_fn, cache_row_stats_fn, years)
    refetched: List[Dict[str, Any]] = []
    for sym in ohlcv_before["symbols"]:
        if sym["status"] in ("ok",) and not force_ohlcv:
            continue
        key = sym["stock"]
        yahoo = sym.get("yahoo_symbol") or resolve_fn(key)
        try:
            df = download_fn(yahoo, years=int(years), force=True, stock_key=key)
            refetched.append(
                {
                    "stock": key,
                    "status": "ok",
                    "rows": len(df),
                    "source": df.attrs.get("historical_source"),
                }
            )
        except Exception as exc:
            refetched.append({"stock": key, "status": "error", "error": str(exc)})

    news_before = audit_news_db(news_db_path, watchlist, years)
    news_targets = [
        s["symbol"]
        for s in news_before["symbols"]
        if s.get("status") in ("missing", "short", "sparse")
    ]
    news_results: List[Dict[str, Any]] = []
    if news_targets:
        news_data.setup_news_database(news_db_path)
        for sym in news_targets:
            print(f"  News backfill {sym}...")
            news_results.append(
                news_data.prefetch_symbol_nse(news_db_path, sym, years=years, max_months=None)
            )

    return {
        "cleanup": cleanup,
        "ohlcv_refetched": refetched,
        "ohlcv_after": audit_ohlcv_cache(cache_dir, watchlist, resolve_fn, cache_row_stats_fn, years),
        "news_before_ok": news_before["ok_count"],
        "news_after": audit_news_db(news_db_path, watchlist, years),
        "news_backfill": news_results,
    }


def full_inventory_report(
    cache_dir: str,
    news_db_path: str,
    watchlist: List[Dict[str, Any]],
    resolve_fn: Callable,
    cache_row_stats_fn: Callable,
    years: float = 5,
) -> Dict[str, Any]:
    orphans = find_orphan_cache_files(cache_dir, watchlist, resolve_fn)
    return {
        "ohlcv": audit_ohlcv_cache(cache_dir, watchlist, resolve_fn, cache_row_stats_fn, years),
        "news": audit_news_db(news_db_path, watchlist, years),
        "orphan_cache_files": orphans,
        "generated_at": datetime.now().isoformat(),
    }
