"""
Morning pre-market job: session CONTEXT only (no trade calls).

MORNING_CALIBRATED_V1 — before 9:15 IST:
  news + global overnight + prior-day TA → expected high/low, gap lean,
  bias (HIGH when US+Asia agree & |SPX|>=1.5%), trend, vol, chain guidance.

Stores JSON under stock_signal_data/morning_reports/.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import analysis_engine
import india_market_context
import morning_session_context as msc
import news_data
import pandas as pd


def default_report_dir(base_dir: str) -> str:
    return os.path.join(base_dir, "morning_reports")


def _json_ready(value: Any) -> Any:
    """Strip NaN/Inf (invalid JSON) so Flask/browser parse never see bare NaN."""
    if value is None:
        return None
    # numpy / pandas scalars
    try:
        import numpy as np

        if isinstance(value, (np.floating, np.integer)):
            value = value.item()
    except Exception:
        pass
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    # pandas Timestamp etc.
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def _save_report(report_dir: str, payload: Dict[str, Any]) -> str:
    os.makedirs(report_dir, exist_ok=True)
    clean = _json_ready(payload)
    ts = str(clean.get("generated_at") or datetime.now().isoformat()).replace(":", "-")
    path = os.path.join(report_dir, f"report_{ts[:19]}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, default=str, allow_nan=False)
    latest = os.path.join(report_dir, "latest.json")
    with open(latest, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, default=str, allow_nan=False)
    return latest


def load_latest_report(report_dir: str) -> Optional[Dict[str, Any]]:
    latest = os.path.join(report_dir, "latest.json")
    if not os.path.exists(latest):
        return None
    with open(latest, encoding="utf-8") as f:
        return _json_ready(json.load(f))


def validate_context_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    checks: List[Dict[str, str]] = []
    ctx = payload.get("session_context") or []
    if len(ctx) < 10:
        checks.append({
            "level": "error",
            "code": "FEW_SYMBOLS",
            "message": f"Need ≥10 session_context rows, got {len(ctx)}",
        })
    else:
        checks.append({"level": "ok", "code": "SYMBOLS", "message": f"{len(ctx)} symbols in context"})

    for bad in ("fno_picks", "intraday_picks"):
        if payload.get(bad):
            checks.append({"level": "error", "code": "HAS_CALLS", "message": f"Forbidden key {bad} present"})

    callish = 0
    for row in ctx:
        if row.get("is_call") is True or row.get("decision") in ("BUY", "SELL"):
            callish += 1
        # Calibrated bias_edge (HIGH US+Asia+SPX) is context, not a trade call.
        if row.get("BUY") or row.get("SELL") or row.get("fno_picks") or row.get("intraday_picks"):
            callish += 1
    if callish:
        checks.append({"level": "error", "code": "CALL_ROWS", "message": f"{callish} rows look like calls"})
    else:
        checks.append({"level": "ok", "code": "NO_CALLS", "message": "No call fields in session_context"})

    # Calibrated V1 shape checks
    sample = next((r for r in ctx if r.get("available")), None)
    if sample:
        if sample.get("logic_tag") != msc.LOGIC_TAG:
            checks.append({
                "level": "warn",
                "code": "LOGIC_TAG",
                "message": f"Expected {msc.LOGIC_TAG}, got {sample.get('logic_tag')}",
            })
        else:
            checks.append({"level": "ok", "code": "LOGIC_TAG", "message": msc.LOGIC_TAG})
        if "bias_confidence" not in sample or "gap_confidence" not in sample:
            checks.append({
                "level": "warn",
                "code": "CALIBRATED_FIELDS",
                "message": "Missing bias_confidence/gap_confidence on context rows",
            })
        else:
            checks.append({"level": "ok", "code": "CALIBRATED_FIELDS", "message": "gap/bias confidence present"})

    avail = [r for r in ctx if r.get("available")]
    if len(avail) < 8:
        checks.append({
            "level": "warn",
            "code": "LOW_AVAILABLE",
            "message": f"Only {len(avail)} available context rows",
        })
    else:
        checks.append({"level": "ok", "code": "AVAILABLE", "message": f"{len(avail)} available"})

    news = payload.get("news_by_symbol") or {}
    if len(news) < 10:
        checks.append({
            "level": "warn",
            "code": "NEWS_SPARSE",
            "message": f"News map has {len(news)} symbols (want ≥10)",
        })
    else:
        checks.append({"level": "ok", "code": "NEWS", "message": f"News for {len(news)} symbols"})

    passed = not any(c["level"] == "error" for c in checks)
    return {"passed": passed, "checks": checks}


def default_load_daily(symbol: str, cache_dir: str, nifty_daily_path: Optional[str] = None) -> pd.DataFrame:
    """Load daily OHLCV for context builders."""
    sym = symbol.strip().upper()
    if sym == "NIFTY" and nifty_daily_path and os.path.isfile(nifty_daily_path):
        df = pd.read_csv(nifty_daily_path)
        df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
        return df
    # Yahoo-style cache names
    candidates = [
        os.path.join(cache_dir, f"{sym}_NS.csv"),
        os.path.join(cache_dir, f"IDX_NSEI.csv") if sym == "NIFTY" else "",
        os.path.join(cache_dir, f"IDX_NSEBANK.csv") if sym == "BANKNIFTY" else "",
        os.path.join(cache_dir, f"IDX_BSESN.csv") if sym == "SENSEX" else "",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            df = pd.read_csv(path)
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], utc=False)
                try:
                    df["Date"] = df["Date"].dt.tz_localize(None)
                except TypeError:
                    pass
            return df
    raise FileNotFoundError(f"No daily cache for {sym}")


def run_morning_brief(
    predict_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    watchlist: Optional[List[Dict[str, str]]] = None,
    news_db_path: str = "",
    report_dir: str = "",
    refresh_news: bool = True,
    symbols: Optional[List[str]] = None,
    force_retrain: bool = False,
    train_knowledge_if_empty: bool = False,
    train_knowledge_fn: Optional[Callable[[], Dict[str, Any]]] = None,
    knowledge_db_path: Optional[str] = None,
    progress_fn: Optional[Callable[[int, int, str], None]] = None,
    load_daily_fn: Optional[Callable[[str], pd.DataFrame]] = None,
    cache_dir: Optional[str] = None,
    nifty_daily_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run pre-market CONTEXT pipeline (no calls).

    `predict_fn` / retrain / knowledge args are accepted for API compatibility
    but are not used for decisions.
    """
    del predict_fn, force_retrain, train_knowledge_if_empty, train_knowledge_fn, knowledge_db_path
    started = datetime.now()
    watchlist = list(watchlist or [])

    news_refresh = None
    if refresh_news and news_db_path:
        news_refresh = news_data.prefetch_watchlist_news(
            news_db_path,
            watchlist,
            years=5,
            include_market_headlines=True,
            max_months_per_symbol=1,
        )

    global_panel = analysis_engine.fetch_global_overnight_panel()
    try:
        india_panel = india_market_context.fetch_india_market_context()
    except Exception as exc:
        india_panel = {"available": False, "error": str(exc)}

    news_stats = news_data.get_news_stats(news_db_path) if news_db_path else {}

    keys = [s.strip().upper() for s in (symbols or []) if s.strip()]
    if not keys:
        keys = [w["symbol"] for w in watchlist if w.get("symbol")]
    # Ensure indices first, then stocks — at least 10 names
    preferred = ["NIFTY", "BANKNIFTY"]
    ordered: List[str] = []
    for s in preferred + keys:
        if s and s not in ordered:
            ordered.append(s)
    keys = ordered

    vix_level = None
    try:
        vix_level = float(((india_panel.get("india_vix") or {}).get("level")))
    except (TypeError, ValueError):
        vix_level = None
    overnight_bias = None
    if isinstance(global_panel, dict):
        overnight_bias = global_panel.get("bias")

    if load_daily_fn is None:
        cdir = cache_dir or ""
        ndp = nifty_daily_path

        def load_daily_fn(sym: str) -> pd.DataFrame:
            return default_load_daily(sym, cdir, ndp)

    news_by_symbol: Dict[str, Any] = {}
    news_tone_by_symbol: Dict[str, str] = {}
    for sym in keys:
        items = []
        if news_db_path:
            try:
                items = news_data.get_news(news_db_path, symbol=sym, limit=8, include_market=True)
            except Exception:
                items = []
        tone = "NEUTRAL"
        if items:
            scored = analysis_engine.score_news_sentiment(items)
            tone = str(scored.get("tone") or "NEUTRAL")
            news_by_symbol[sym] = {
                "tone": tone,
                "score_delta": scored.get("score_delta"),
                "highlights": scored.get("highlights") or [],
                "items": [
                    {"title": x.get("title"), "published_at": x.get("published_at"), "source": x.get("source")}
                    for x in items[:5]
                ],
            }
        else:
            news_by_symbol[sym] = {"tone": "NEUTRAL", "items": []}
        news_tone_by_symbol[sym] = tone

    total = len(keys)
    if progress_fn:
        progress_fn(0, total, "Starting context")

    session_context: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for i, sym in enumerate(keys, start=1):
        try:
            df = load_daily_fn(sym)
            news_pack = news_by_symbol.get(sym) or {}
            row = msc.build_session_context(
                sym,
                df,
                open_px=None,  # before 9:15 — cash open unknown
                vix_level=vix_level,
                news_tone=news_tone_by_symbol.get(sym),
                news_score=news_pack.get("score_delta"),
                overnight_bias=overnight_bias,
                overnight_panel=global_panel if isinstance(global_panel, dict) else None,
            )
            msc.assert_no_calls(row)
            session_context.append(row)
        except Exception as exc:
            errors.append({"symbol": sym, "error": str(exc)})
            session_context.append({
                "symbol": sym,
                "available": False,
                "error": str(exc),
                "is_call": False,
                "logic_tag": msc.LOGIC_TAG,
            })
        if progress_fn:
            progress_fn(i, total, sym)

    finished = datetime.now()
    payload: Dict[str, Any] = {
        "job": "morning_pre915_context",
        "logic_tag": msc.LOGIC_TAG,
        "mode": "pre915",
        "no_calls": True,
        "note": (
            "Runs before 9:15 IST. Uses realtime news + overnight US/Asia/VIX + prior-day TA. "
            "GUARANTEED: day range ~96%+. Bias spoken ≥70% only on strong US+Asia+SPX days. "
            "Gap is calibrated lean (not guaranteed). No BUY/SELL calls."
        ),
        "generated_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round((finished - started).total_seconds(), 1),
        "refresh_news": refresh_news,
        "news_refresh_summary": news_refresh,
        "news_stats": news_stats,
        "news_by_symbol": news_by_symbol,
        "global_overnight_panel": global_panel,
        "india_market_context": india_panel,
        "symbols_requested": keys,
        "session_context": session_context,
        "errors": errors,
        "stocks_analyzed": sum(1 for r in session_context if r.get("available")),
        "stocks_failed": len(errors),
        "provenance": {
            "locked_1y": msc.LOCKED_1Y,
            "locked_pre915": msc.LOCKED_PRE915,
            "locked_calibrated": msc.LOCKED_CALIBRATED,
        },
        # Explicitly empty — morning product must not carry call desks
        "fno_picks": [],
        "intraday_picks": [],
        "stocks": [],  # legacy key cleared — UI reads session_context
    }
    payload["validation"] = validate_context_report(payload)
    payload["report_path"] = _save_report(report_dir, payload)
    try:
        import knowledge_db
        import training_store

        db = knowledge_db.ensure_db_dir()
        training_store.ensure_tables(db)
        payload["db_rows"] = training_store.save_morning_report(payload, db)
    except Exception as exc:
        payload["db_error"] = str(exc)
    # Always return JSON-safe payload (NaN/Inf → null). Sync /morning/run uses this directly.
    return _json_ready(payload)


# Back-compat stub — callers that still import build_fno_picks get an empty list.
def build_fno_picks(*_args: Any, **_kwargs: Any) -> List[Dict[str, Any]]:
    return []


def validate_stock_analysis(result: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy per-symbol analyze validation (not morning context)."""
    checks: List[Dict[str, str]] = []
    if not result.get("decision"):
        checks.append({"level": "warn", "code": "NO_DECISION", "message": "No decision field"})
    else:
        checks.append({"level": "ok", "code": "DECISION", "message": str(result.get("decision"))})
    passed = not any(c["level"] == "error" for c in checks)
    return {"passed": passed, "checks": checks}
