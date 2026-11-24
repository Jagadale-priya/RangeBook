"""
Historical pattern + news impact memory: scan OHLCV & news DB, train ML, store rules.

Horizons use daily bars (1 / 5 / 20 sessions ≈ 1d / 1w / 1mo). Intraday (e.g. 20min) needs
minute history (Kite) — same pipeline can be extended later.

Database: stock_signal_data/knowledge.db
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import analysis_engine
import news_data

try:
    import joblib
except ImportError:
    joblib = None  # type: ignore

try:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import accuracy_score, roc_auc_score
except ImportError:
    HistGradientBoostingClassifier = None  # type: ignore

KNOWLEDGE_MIN_SAMPLES = 5
KNOWLEDGE_MIN_ABS_AVG_5D = 0.35
# A rule only earns a vote if its forward return beats the unconditional drift of the
# same sample by a statistically significant margin. A raw magnitude gate cannot tell
# "this pattern predicts +0.3%" apart from "everything drifts +0.3% over five days".
KNOWLEDGE_MIN_TSTAT = 2.0
KNOWLEDGE_MIN_RULE_SAMPLES = 30
KNOWLEDGE_ML_MIN_AUC = 0.55
FLAT_THRESHOLD_PCT = 0.15

FORWARD_HORIZONS = [1, 5, 20]
INTRADAY_INTERVALS = ("5minute", "15minute")
INTRADAY_FORWARD_BARS = {
    "5minute": [1, 3, 12],
    "15minute": [1, 2, 4],
}

NEWS_TOPIC_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("dividend_bonus", ("dividend", "bonus", "buyback", "split")),
    ("results_earnings", ("result", "quarter", "q1", "q2", "q3", "q4", "earnings", "revenue", "profit", "ebitda")),
    ("regulatory_legal", ("sebi", "penalty", "investigation", "litigation", "fraud", "court")),
    ("corporate_action", ("merger", "acquisition", "demerger", "delist", "agm", "egm")),
    ("management", ("resign", "appoint", "ceo", "md", "director")),
    ("order_contract", ("order", "contract", "win", "partnership", "deal")),
    ("credit_rating", ("upgrade", "downgrade", "rating", "moody", "crisil")),
    ("general", ()),
]


def default_knowledge_db_path(base_dir: str) -> str:
    return os.path.join(base_dir, "knowledge.db")


def setup_knowledge_database(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS candle_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock TEXT NOT NULL,
            symbol TEXT NOT NULL,
            event_date TEXT NOT NULL,
            pattern_name TEXT NOT NULL,
            rsi_14 REAL,
            vol_ratio REAL,
            forward_return_1d REAL,
            forward_return_5d REAL,
            forward_return_20d REAL,
            direction_1d TEXT,
            direction_5d TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(stock, event_date, pattern_name)
        );
        CREATE INDEX IF NOT EXISTS idx_candle_pat ON candle_events(pattern_name);
        CREATE INDEX IF NOT EXISTS idx_candle_stock ON candle_events(stock, event_date);

        CREATE TABLE IF NOT EXISTS news_impact_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock TEXT NOT NULL,
            news_id INTEGER,
            published_at TEXT NOT NULL,
            event_trade_date TEXT NOT NULL,
            topic TEXT NOT NULL,
            title TEXT NOT NULL,
            tone TEXT,
            forward_return_1d REAL,
            forward_return_5d REAL,
            forward_return_20d REAL,
            direction_5d TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_news_topic ON news_impact_events(topic);
        CREATE INDEX IF NOT EXISTS idx_news_stock ON news_impact_events(stock);

        CREATE TABLE IF NOT EXISTS learned_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_type TEXT NOT NULL,
            rule_key TEXT NOT NULL,
            summary TEXT NOT NULL,
            sample_count INTEGER NOT NULL,
            avg_forward_1d REAL,
            avg_forward_5d REAL,
            avg_forward_20d REAL,
            win_rate_1d REAL,
            win_rate_5d REAL,
            ml_probability_up REAL,
            baseline_forward_5d REAL,
            edge_forward_5d REAL,
            t_stat_5d REAL,
            source TEXT NOT NULL DEFAULT 'pattern_memory_train',
            updated_at TEXT NOT NULL,
            UNIQUE(rule_type, rule_key)
        );

        CREATE TABLE IF NOT EXISTS ml_training_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_type TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            symbols_json TEXT,
            metrics_json TEXT,
            model_path TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS intraday_candle_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock TEXT NOT NULL,
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            event_ts TEXT NOT NULL,
            pattern_name TEXT NOT NULL,
            forward_return_1b REAL,
            forward_return_3b REAL,
            forward_return_12b REAL,
            direction_3b TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(stock, event_ts, interval, pattern_name)
        );
        CREATE INDEX IF NOT EXISTS idx_intraday_pat ON intraday_candle_events(pattern_name, interval);
        """
    )
    conn.commit()
    conn.close()
    import analysis_store

    analysis_store.ensure_analysis_tables(db_path)


def _direction(pct: Optional[float]) -> str:
    if pct is None or np.isnan(pct):
        return "UNKNOWN"
    if pct > FLAT_THRESHOLD_PCT:
        return "UP"
    if pct < -FLAT_THRESHOLD_PCT:
        return "DOWN"
    return "FLAT"


def _forward_returns(close: pd.Series, i: int) -> Dict[int, Optional[float]]:
    out: Dict[int, Optional[float]] = {}
    c0 = float(close.iloc[i])
    if c0 <= 0:
        return {h: None for h in FORWARD_HORIZONS}
    for h in FORWARD_HORIZONS:
        j = i + h
        if j < len(close):
            out[h] = (float(close.iloc[j]) / c0 - 1.0) * 100.0
        else:
            out[h] = None
    return out


def _norm_index_dates(df: pd.DataFrame) -> pd.Series:
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return pd.Series(idx.normalize().values, index=df.index)


def classify_news_topic(title: str, summary: Optional[str] = None) -> str:
    text = f"{title} {summary or ''}".lower()
    best = "general"
    best_hits = 0
    for topic, keywords in NEWS_TOPIC_RULES:
        if topic == "general":
            continue
        hits = sum(1 for k in keywords if k in text)
        if hits > best_hits:
            best_hits = hits
            best = topic
    return best


def classify_news_tone(title: str, summary: Optional[str] = None) -> str:
    text = f"{title} {summary or ''}".lower()
    bull = sum(1 for w in analysis_engine.BULLISH_NEWS if w in text)
    bear = sum(1 for w in analysis_engine.BEARISH_NEWS if w in text)
    if bull > bear:
        return "BULLISH"
    if bear > bull:
        return "BEARISH"
    return "NEUTRAL"


def scan_candles_on_df(
    df: pd.DataFrame,
    stock_key: str,
    symbol: str,
    features_df: Optional[pd.DataFrame] = None,
) -> List[Dict[str, Any]]:
    """Walk history; record each pattern and forward outcomes."""
    if df is None or len(df) < 25:
        return []
    events: List[Dict[str, Any]] = []
    close = df["Close"]
    max_i = len(df) - max(FORWARD_HORIZONS) - 1
    for i in range(2, max_i):
        window = df.iloc[i - 2 : i + 1]
        det = analysis_engine.detect_candlestick_three_bars(window)
        if not det.get("patterns"):
            continue
        fwd = _forward_returns(close, i)
        dt = _norm_index_dates(df).iloc[i]
        rsi_v = vol_v = None
        if features_df is not None and i < len(features_df):
            row = features_df.iloc[i]
            rsi_v = float(row["rsi_14"]) if "rsi_14" in row and pd.notna(row.get("rsi_14")) else None
            vol_v = float(row["vol_ratio"]) if "vol_ratio" in row and pd.notna(row.get("vol_ratio")) else None
        for pat in det["patterns"]:
            events.append(
                {
                    "stock": stock_key.upper(),
                    "symbol": symbol,
                    "event_date": dt.strftime("%Y-%m-%d"),
                    "pattern_name": pat,
                    "rsi_14": rsi_v,
                    "vol_ratio": vol_v,
                    "forward_return_1d": fwd.get(1),
                    "forward_return_5d": fwd.get(5),
                    "forward_return_20d": fwd.get(20),
                    "direction_1d": _direction(fwd.get(1)),
                    "direction_5d": _direction(fwd.get(5)),
                }
            )
    return events


def _forward_returns_bars(close: pd.Series, i: int, bar_horizons: List[int]) -> Dict[int, Optional[float]]:
    out: Dict[int, Optional[float]] = {}
    c0 = float(close.iloc[i])
    if c0 <= 0:
        return {h: None for h in bar_horizons}
    for h in bar_horizons:
        j = i + h
        if j < len(close):
            out[h] = (float(close.iloc[j]) / c0 - 1.0) * 100.0
        else:
            out[h] = None
    return out


def _intraday_df_to_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    colmap = {c.lower(): c for c in out.columns}
    for src, dst in [("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close")]:
        if dst not in out.columns and src in colmap:
            out[dst] = out[colmap[src]]
    if "Close" not in out.columns:
        return out
    return out


def scan_intraday_candles_on_df(
    df: pd.DataFrame,
    stock_key: str,
    symbol: str,
    interval: str,
) -> List[Dict[str, Any]]:
    bar_horizons = INTRADAY_FORWARD_BARS.get(interval, [1, 3, 12])
    df = _intraday_df_to_ohlcv(df)
    if df is None or len(df) < max(bar_horizons) + 10:
        return []
    events: List[Dict[str, Any]] = []
    close = df["Close"]
    max_i = len(df) - max(bar_horizons) - 1
    for i in range(2, max_i):
        window = df.iloc[i - 2 : i + 1]
        det = analysis_engine.detect_candlestick_three_bars(window)
        if not det.get("patterns"):
            continue
        fwd = _forward_returns_bars(close, i, bar_horizons)
        ts = df.index[i]
        event_ts = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        h1, hmid, hlong = bar_horizons[0], bar_horizons[min(1, len(bar_horizons) - 1)], bar_horizons[-1]
        for pat in det["patterns"]:
            events.append(
                {
                    "stock": stock_key.upper(),
                    "symbol": symbol,
                    "interval": interval,
                    "event_ts": event_ts,
                    "pattern_name": pat,
                    "forward_return_1b": fwd.get(h1),
                    "forward_return_3b": fwd.get(hmid),
                    "forward_return_12b": fwd.get(hlong),
                    "direction_3b": _direction(fwd.get(hmid)),
                }
            )
    return events


def _clear_intraday_events(conn: sqlite3.Connection, stock: str) -> None:
    conn.execute("DELETE FROM intraday_candle_events WHERE stock = ?", (stock.upper(),))


def _insert_intraday_events(conn: sqlite3.Connection, events: List[Dict[str, Any]]) -> int:
    now = datetime.now().isoformat()
    n = 0
    for e in events:
        cur = conn.execute(
            """
            INSERT OR REPLACE INTO intraday_candle_events
            (stock, symbol, interval, event_ts, pattern_name,
             forward_return_1b, forward_return_3b, forward_return_12b, direction_3b, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                e["stock"],
                e["symbol"],
                e["interval"],
                e["event_ts"],
                e["pattern_name"],
                e.get("forward_return_1b"),
                e.get("forward_return_3b"),
                e.get("forward_return_12b"),
                e.get("direction_3b"),
                now,
            ),
        )
        if cur.rowcount:
            n += 1
    return n


def _trade_date_for_news(pub_iso: str, trading_dates: pd.Series) -> Optional[pd.Timestamp]:
    try:
        pub = pd.to_datetime(pub_iso)
        if getattr(pub, "tz", None) is not None:
            pub = pub.tz_localize(None)
        pub = pub.normalize()
    except Exception:
        return None
    aligned = trading_dates[trading_dates >= pub]
    if len(aligned):
        return pd.Timestamp(aligned.iloc[0])
    if len(trading_dates):
        return pd.Timestamp(trading_dates.iloc[-1])
    return None


def scan_news_impacts(
    df: pd.DataFrame,
    stock_key: str,
    news_db_path: str,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    if not os.path.exists(news_db_path) or df is None or len(df) < 25:
        return []
    items = news_data.get_news(news_db_path, symbol=stock_key, limit=limit, include_market=False)
    trading_dates = _norm_index_dates(df)
    close = df["Close"]
    date_to_i = {trading_dates.iloc[i]: i for i in range(len(df))}
    now = datetime.now().isoformat()
    rows: List[Dict[str, Any]] = []
    for item in items:
        td = _trade_date_for_news(item.get("published_at", ""), trading_dates)
        if td is None or td not in date_to_i:
            continue
        i = date_to_i[td]
        if i >= len(df) - max(FORWARD_HORIZONS):
            continue
        fwd = _forward_returns(close, i)
        topic = classify_news_topic(item.get("title", ""), item.get("summary"))
        tone = classify_news_tone(item.get("title", ""), item.get("summary"))
        rows.append(
            {
                "stock": stock_key.upper(),
                "news_id": item.get("id"),
                "published_at": item.get("published_at"),
                "event_trade_date": td.strftime("%Y-%m-%d"),
                "topic": topic,
                "title": (item.get("title") or "")[:500],
                "tone": tone,
                "forward_return_1d": fwd.get(1),
                "forward_return_5d": fwd.get(5),
                "forward_return_20d": fwd.get(20),
                "direction_5d": _direction(fwd.get(5)),
                "created_at": now,
            }
        )
    return rows


def _clear_symbol_events(conn: sqlite3.Connection, stock: str) -> None:
    conn.execute("DELETE FROM candle_events WHERE stock = ?", (stock.upper(),))
    conn.execute("DELETE FROM news_impact_events WHERE stock = ?", (stock.upper(),))


def _insert_candle_events(conn: sqlite3.Connection, events: List[Dict[str, Any]]) -> int:
    now = datetime.now().isoformat()
    n = 0
    for e in events:
        cur = conn.execute(
            """
            INSERT OR REPLACE INTO candle_events
            (stock, symbol, event_date, pattern_name, rsi_14, vol_ratio,
             forward_return_1d, forward_return_5d, forward_return_20d,
             direction_1d, direction_5d, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                e["stock"],
                e["symbol"],
                e["event_date"],
                e["pattern_name"],
                e.get("rsi_14"),
                e.get("vol_ratio"),
                e.get("forward_return_1d"),
                e.get("forward_return_5d"),
                e.get("forward_return_20d"),
                e.get("direction_1d"),
                e.get("direction_5d"),
                now,
            ),
        )
        if cur.rowcount:
            n += 1
    return n


def _insert_news_events(conn: sqlite3.Connection, events: List[Dict[str, Any]]) -> int:
    conn.execute("DELETE FROM news_impact_events WHERE stock = ?", (events[0]["stock"],)) if events else None
    n = 0
    for e in events:
        conn.execute(
            """
            INSERT INTO news_impact_events
            (stock, news_id, published_at, event_trade_date, topic, title, tone,
             forward_return_1d, forward_return_5d, forward_return_20d, direction_5d, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                e["stock"],
                e.get("news_id"),
                e.get("published_at"),
                e["event_trade_date"],
                e["topic"],
                e["title"],
                e["tone"],
                e.get("forward_return_1d"),
                e.get("forward_return_5d"),
                e.get("forward_return_20d"),
                e.get("direction_5d"),
                e["created_at"],
            ),
        )
        n += 1
    return n


def _ensure_rule_stat_columns(conn: sqlite3.Connection) -> None:
    existing = {r[1] for r in conn.execute("PRAGMA table_info(learned_rules)")}
    for col in ("baseline_forward_5d", "edge_forward_5d", "t_stat_5d"):
        if col not in existing:
            conn.execute(f"ALTER TABLE learned_rules ADD COLUMN {col} REAL")


def significance(mean: Optional[float], sq_mean: Optional[float], n: int, baseline: float):
    """Edge over baseline and its t-statistic, from E[x] and E[x^2]."""
    if mean is None or sq_mean is None or n < 2:
        return None, None
    edge = float(mean) - float(baseline)
    var = float(sq_mean) - float(mean) ** 2
    if var <= 0:
        return edge, None
    var *= n / (n - 1.0)
    se = math.sqrt(var / n)
    if se <= 0:
        return edge, None
    return edge, edge / se


def _table_baseline(conn: sqlite3.Connection, table: str, column: str) -> float:
    row = conn.execute(
        f"SELECT AVG({column}) FROM {table} WHERE {column} IS NOT NULL"
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def aggregate_learned_rules(db_path: str) -> int:
    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    _ensure_rule_stat_columns(conn)
    now = datetime.now().isoformat()
    count = 0

    candle_baseline = _table_baseline(conn, "candle_events", "forward_return_5d")
    pat_rows = conn.execute(
        """
        SELECT pattern_name,
               COUNT(*) AS n,
               AVG(forward_return_1d) AS a1,
               AVG(forward_return_5d) AS a5,
               AVG(forward_return_20d) AS a20,
               AVG(CASE WHEN direction_1d = 'UP' THEN 1.0 ELSE 0 END) AS w1,
               AVG(CASE WHEN direction_5d = 'UP' THEN 1.0 ELSE 0 END) AS w5,
               AVG(forward_return_5d * forward_return_5d) AS sq5
        FROM candle_events
        WHERE forward_return_5d IS NOT NULL
        GROUP BY pattern_name
        HAVING COUNT(*) >= 3
        """
    ).fetchall()

    for row in pat_rows:
        name, n, a1, a5, a20, w1, w5, sq5 = row
        edge, tstat = significance(a5, sq5, n, candle_baseline)
        verdict = (
            f"edge {edge:+.3f}% vs baseline {candle_baseline:+.3f}% (t={tstat:+.2f})"
            if edge is not None and tstat is not None
            else "edge not measurable"
        )
        summary = (
            f"After '{name}' on daily chart (n={n}): avg +5d {a5:+.2f}%, "
            f"win rate 5d {100 * (w5 or 0):.0f}%; {verdict} — historical scan, not guaranteed."
        )
        conn.execute(
            """
            INSERT INTO learned_rules
            (rule_type, rule_key, summary, sample_count,
             avg_forward_1d, avg_forward_5d, avg_forward_20d,
             win_rate_1d, win_rate_5d, baseline_forward_5d, edge_forward_5d, t_stat_5d,
             source, updated_at)
            VALUES ('candle', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'historical_scan', ?)
            ON CONFLICT(rule_type, rule_key) DO UPDATE SET
              summary=excluded.summary, sample_count=excluded.sample_count,
              avg_forward_1d=excluded.avg_forward_1d, avg_forward_5d=excluded.avg_forward_5d,
              avg_forward_20d=excluded.avg_forward_20d, win_rate_1d=excluded.win_rate_1d,
              win_rate_5d=excluded.win_rate_5d, baseline_forward_5d=excluded.baseline_forward_5d,
              edge_forward_5d=excluded.edge_forward_5d, t_stat_5d=excluded.t_stat_5d,
              updated_at=excluded.updated_at
            """,
            (name, summary, n, a1, a5, a20, w1, w5, candle_baseline, edge, tstat, now),
        )
        count += 1

    news_baseline = _table_baseline(conn, "news_impact_events", "forward_return_5d")
    news_rows = conn.execute(
        """
        SELECT topic, tone,
               COUNT(*) AS n,
               AVG(forward_return_1d) AS a1,
               AVG(forward_return_5d) AS a5,
               AVG(forward_return_20d) AS a20,
               AVG(CASE WHEN direction_5d = 'UP' THEN 1.0 ELSE 0 END) AS w5,
               AVG(forward_return_5d * forward_return_5d) AS sq5
        FROM news_impact_events
        WHERE forward_return_5d IS NOT NULL
        GROUP BY topic, tone
        HAVING COUNT(*) >= 2
        """
    ).fetchall()

    for row in news_rows:
        topic, tone, n, a1, a5, a20, w5, sq5 = row
        key = f"{topic}|{tone}"
        edge, tstat = significance(a5, sq5, n, news_baseline)
        verdict = (
            f"edge {edge:+.3f}% vs baseline {news_baseline:+.3f}% (t={tstat:+.2f})"
            if edge is not None and tstat is not None
            else "edge not measurable"
        )
        summary = (
            f"News topic '{topic}' ({tone}) (n={n}): avg +5d {a5:+.2f}%, "
            f"up-rate 5d {100 * (w5 or 0):.0f}% after event day; {verdict}."
        )
        conn.execute(
            """
            INSERT INTO learned_rules
            (rule_type, rule_key, summary, sample_count,
             avg_forward_1d, avg_forward_5d, avg_forward_20d,
             win_rate_5d, baseline_forward_5d, edge_forward_5d, t_stat_5d,
             source, updated_at)
            VALUES ('news', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'news_align', ?)
            ON CONFLICT(rule_type, rule_key) DO UPDATE SET
              summary=excluded.summary, sample_count=excluded.sample_count,
              avg_forward_1d=excluded.avg_forward_1d, avg_forward_5d=excluded.avg_forward_5d,
              avg_forward_20d=excluded.avg_forward_20d, win_rate_5d=excluded.win_rate_5d,
              baseline_forward_5d=excluded.baseline_forward_5d,
              edge_forward_5d=excluded.edge_forward_5d, t_stat_5d=excluded.t_stat_5d,
              updated_at=excluded.updated_at
            """,
            (key, summary, n, a1, a5, a20, w5, news_baseline, edge, tstat, now),
        )
        count += 1

    intra_rows = conn.execute(
        """
        SELECT interval, pattern_name,
               COUNT(*) AS n,
               AVG(forward_return_1b) AS a1,
               AVG(forward_return_3b) AS a3,
               AVG(forward_return_12b) AS a12,
               AVG(CASE WHEN direction_3b = 'UP' THEN 1.0 ELSE 0 END) AS w3,
               AVG(forward_return_3b * forward_return_3b) AS sq3
        FROM intraday_candle_events
        WHERE forward_return_3b IS NOT NULL
        GROUP BY interval, pattern_name
        HAVING COUNT(*) >= 5
        """
    ).fetchall()

    intra_baseline = _table_baseline(conn, "intraday_candle_events", "forward_return_3b")
    for row in intra_rows:
        interval, name, n, a1, a3, a12, w3, sq3 = row
        key = f"{interval}|{name}"
        edge, tstat = significance(a3, sq3, n, intra_baseline)
        verdict = (
            f"edge {edge:+.3f}% vs baseline {intra_baseline:+.3f}% (t={tstat:+.2f})"
            if edge is not None and tstat is not None
            else "edge not measurable"
        )
        summary = (
            f"Intraday '{name}' on {interval} (n={n}): avg mid-horizon {a3:+.2f}%, "
            f"up-rate {100 * (w3 or 0):.0f}%; {verdict} — Kite minute history."
        )
        conn.execute(
            """
            INSERT INTO learned_rules
            (rule_type, rule_key, summary, sample_count,
             avg_forward_1d, avg_forward_5d, avg_forward_20d,
             win_rate_5d, baseline_forward_5d, edge_forward_5d, t_stat_5d,
             source, updated_at)
            VALUES ('candle_intraday', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'kite_intraday', ?)
            ON CONFLICT(rule_type, rule_key) DO UPDATE SET
              summary=excluded.summary, sample_count=excluded.sample_count,
              avg_forward_1d=excluded.avg_forward_1d, avg_forward_5d=excluded.avg_forward_5d,
              avg_forward_20d=excluded.avg_forward_20d, win_rate_5d=excluded.win_rate_5d,
              baseline_forward_5d=excluded.baseline_forward_5d,
              edge_forward_5d=excluded.edge_forward_5d, t_stat_5d=excluded.t_stat_5d,
              updated_at=excluded.updated_at
            """,
            (key, summary, n, a1, a3, a12, w3, intra_baseline, edge, tstat, now),
        )
        count += 1

    conn.commit()
    conn.close()
    return count


def _train_classifier(
    df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str = "target_up_5d",
) -> Tuple[Any, Dict[str, Any]]:
    if HistGradientBoostingClassifier is None or len(df) < 80:
        return None, {"skipped": True, "reason": "insufficient samples or sklearn missing"}
    X = df[feature_cols].fillna(0)
    y = df[target_col].astype(int)
    split = int(len(X) * 0.8)
    X_tr, X_te = X.iloc[:split], X.iloc[split:]
    y_tr, y_te = y.iloc[:split], y.iloc[split:]
    if y_tr.nunique() < 2:
        return None, {"skipped": True, "reason": "single class in training target"}
    model = HistGradientBoostingClassifier(max_depth=6, learning_rate=0.06, max_iter=200, random_state=42)
    model.fit(X_tr, y_tr)
    proba = model.predict_proba(X_te)[:, 1]
    pred = (proba >= 0.5).astype(int)
    metrics = {
        "test_accuracy": float(accuracy_score(y_te, pred)),
        "samples": int(len(df)),
        "features": feature_cols,
    }
    try:
        metrics["test_auc"] = float(roc_auc_score(y_te, proba))
    except Exception:
        pass
    return model, metrics


def train_memory_models(db_path: str, model_dir: str) -> Dict[str, Any]:
    os.makedirs(model_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    candle_df = pd.read_sql_query(
        "SELECT pattern_name, rsi_14, vol_ratio, forward_return_5d FROM candle_events WHERE forward_return_5d IS NOT NULL",
        conn,
    )
    news_df = pd.read_sql_query(
        "SELECT topic, tone, forward_return_5d FROM news_impact_events WHERE forward_return_5d IS NOT NULL",
        conn,
    )
    conn.close()

    out: Dict[str, Any] = {"candle_model": None, "news_model": None}

    if len(candle_df) >= 80:
        dummies = pd.get_dummies(candle_df["pattern_name"], prefix="pat")
        X = pd.concat([dummies, candle_df[["rsi_14", "vol_ratio"]].fillna(0)], axis=1)
        candle_df = candle_df.copy()
        candle_df["target_up_5d"] = (candle_df["forward_return_5d"] > FLAT_THRESHOLD_PCT).astype(int)
        full = pd.concat([X, candle_df["target_up_5d"]], axis=1)
        model, metrics = _train_classifier(full, list(X.columns))
        if model is not None and joblib:
            path = os.path.join(model_dir, "pattern_memory_candle.joblib")
            joblib.dump({"model": model, "feature_cols": list(X.columns), "metrics": metrics}, path)
            out["candle_model"] = {"path": path, "metrics": metrics}
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                INSERT INTO ml_training_runs (run_type, started_at, finished_at, metrics_json, model_path, notes)
                VALUES ('candle_ml', ?, ?, ?, ?, 'Predict P(up) within 5 sessions after pattern')
                """,
                (datetime.now().isoformat(), datetime.now().isoformat(), json.dumps(metrics), path),
            )
            conn.commit()
            conn.close()

    if len(news_df) >= 40:
        dummies = pd.get_dummies(news_df["topic"], prefix="topic")
        tone_d = pd.get_dummies(news_df["tone"], prefix="tone")
        Xn = pd.concat([dummies, tone_d], axis=1)
        news_df = news_df.copy()
        news_df["target_up_5d"] = (news_df["forward_return_5d"] > FLAT_THRESHOLD_PCT).astype(int)
        full = pd.concat([Xn, news_df["target_up_5d"]], axis=1)
        model, metrics = _train_classifier(full, list(Xn.columns))
        if model is not None and joblib:
            path = os.path.join(model_dir, "pattern_memory_news.joblib")
            joblib.dump({"model": model, "feature_cols": list(Xn.columns), "metrics": metrics}, path)
            out["news_model"] = {"path": path, "metrics": metrics}
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                INSERT INTO ml_training_runs (run_type, started_at, finished_at, metrics_json, model_path, notes)
                VALUES ('news_ml', ?, ?, ?, ?, 'Predict P(up) within 5 sessions after news topic/tone')
                """,
                (datetime.now().isoformat(), datetime.now().isoformat(), json.dumps(metrics), path),
            )
            conn.commit()
            conn.close()

    return out


def run_knowledge_training(
    db_path: str,
    model_dir: str,
    news_db_path: str,
    watchlist: List[Dict[str, Any]],
    download_fn: Callable,
    resolve_fn: Callable,
    compute_features_fn: Callable,
    indian_stocks: Dict[str, str],
    clear_per_symbol: bool = True,
    include_intraday: bool = True,
) -> Dict[str, Any]:
    setup_knowledge_database(db_path)
    started = datetime.now().isoformat()
    symbols_done: List[str] = []
    candle_total = 0
    news_total = 0
    intraday_total = 0
    errors: List[Dict[str, str]] = []

    conn = sqlite3.connect(db_path)
    for item in watchlist:
        stock = (item.get("symbol") or item.get("stock") or "").strip().upper()
        if not stock:
            continue
        try:
            yahoo = resolve_fn(stock)
            df = download_fn(yahoo, stock_key=stock)
            if df is None or len(df) < 50:
                errors.append({"stock": stock, "error": "insufficient OHLCV"})
                continue
            features_df, _ = compute_features_fn(df)
            if clear_per_symbol:
                _clear_symbol_events(conn, stock)
                _clear_intraday_events(conn, stock)
            c_events = scan_candles_on_df(df, stock, yahoo, features_df)
            candle_total += _insert_candle_events(conn, c_events)
            n_events = scan_news_impacts(df, stock, news_db_path)
            if n_events:
                news_total += _insert_news_events(conn, n_events)
            if include_intraday:
                try:
                    import kite_data

                    if kite_data.kite_enabled() and kite_data.is_kite_eligible(stock, indian_stocks):
                        for interval in INTRADAY_INTERVALS:
                            idf, ierr = kite_data.fetch_historical_candles(
                                stock, interval=interval, days=int(os.environ.get("KITE_INTRADAY_HISTORY_DAYS", "120"))
                            )
                            if idf is not None and len(idf) > 30:
                                ie = scan_intraday_candles_on_df(idf, stock, yahoo, interval)
                                intraday_total += _insert_intraday_events(conn, ie)
                                print(f"    Intraday {interval}: {len(ie)} events")
                            elif ierr:
                                print(f"    Intraday {interval} skip: {ierr[:50]}")
                except ImportError:
                    pass
            symbols_done.append(stock)
            conn.commit()
            print(f"  Knowledge scan {stock}: {len(c_events)} candle events, {len(n_events)} news events")
        except Exception as exc:
            errors.append({"stock": stock, "error": str(exc)})
    conn.close()

    rules = aggregate_learned_rules(db_path)
    ml_out = train_memory_models(db_path, model_dir)

    finished = datetime.now().isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO ml_training_runs (run_type, started_at, finished_at, symbols_json, metrics_json, notes)
        VALUES ('full_knowledge_pipeline', ?, ?, ?, ?, ?)
        """,
        (
            started,
            finished,
            json.dumps(symbols_done),
            json.dumps({"rules": rules, "ml": ml_out, "candle_events": candle_total, "news_events": news_total, "intraday_events": intraday_total}),
            "Scan candles + news, aggregate rules, train memory ML",
        ),
    )
    conn.commit()
    conn.close()

    return {
        "started": started,
        "finished": finished,
        "symbols": symbols_done,
        "candle_events_written": candle_total,
        "news_events_written": news_total,
        "intraday_events_written": intraday_total,
        "learned_rules": rules,
        "ml": ml_out,
        "errors": errors,
        "db_path": db_path,
    }


def get_knowledge_stats(db_path: str) -> Dict[str, Any]:
    if not os.path.exists(db_path):
        return {"ready": False, "db_path": db_path}
    conn = sqlite3.connect(db_path)
    ce = conn.execute("SELECT COUNT(*) FROM candle_events").fetchone()[0]
    try:
        ie = conn.execute("SELECT COUNT(*) FROM intraday_candle_events").fetchone()[0]
    except sqlite3.OperationalError:
        ie = 0
    ne = conn.execute("SELECT COUNT(*) FROM news_impact_events").fetchone()[0]
    lr = conn.execute("SELECT COUNT(*) FROM learned_rules").fetchone()[0]
    runs = conn.execute("SELECT COUNT(*) FROM ml_training_runs").fetchone()[0]
    top_pat = conn.execute(
        "SELECT pattern_name, COUNT(*) FROM candle_events GROUP BY pattern_name ORDER BY 2 DESC LIMIT 8"
    ).fetchall()
    conn.close()
    return {
        "ready": ce > 0 or ne > 0,
        "candle_events": ce,
        "intraday_candle_events": ie,
        "news_impact_events": ne,
        "learned_rules": lr,
        "training_runs": runs,
        "top_patterns": [{"pattern": p, "count": n} for p, n in top_pat],
        "db_path": db_path,
        "horizon_note": "Daily: 1/5/20 sessions. Intraday: 5m & 15m bars from Kite when enabled.",
    }


_PIT_RULE_CACHE: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]] = {}


def candle_rules_as_of(db_path: str, as_of: Any, horizon_buffer_days: int = 7) -> Dict[str, Dict[str, Any]]:
    """Candle rules built only from events whose 5-day outcome was already known at as_of.

    The stored `learned_rules` table is aggregated over all history, so reusing it
    inside a historical audit leaks the future. This recomputes the same statistics
    from `candle_events` with an event-date cutoff.
    """
    day = str(as_of)[:10]
    key = (db_path, day)
    cached = _PIT_RULE_CACHE.get(key)
    if cached is not None:
        return cached
    if not os.path.exists(db_path):
        return {}
    cutoff = (datetime.fromisoformat(day) - timedelta(days=horizon_buffer_days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    try:
        base_row = conn.execute(
            "SELECT AVG(forward_return_5d) FROM candle_events "
            "WHERE forward_return_5d IS NOT NULL AND event_date < ?",
            (cutoff,),
        ).fetchone()
        baseline = float(base_row[0]) if base_row and base_row[0] is not None else 0.0
        rows = conn.execute(
            """
            SELECT pattern_name, COUNT(*) AS n,
                   AVG(forward_return_1d) AS a1,
                   AVG(forward_return_5d) AS a5,
                   AVG(CASE WHEN direction_5d = 'UP' THEN 1.0 ELSE 0 END) AS w5,
                   AVG(forward_return_5d * forward_return_5d) AS sq5
            FROM candle_events
            WHERE forward_return_5d IS NOT NULL AND event_date < ?
            GROUP BY pattern_name
            HAVING COUNT(*) >= 3
            """,
            (cutoff,),
        ).fetchall()
    finally:
        conn.close()

    out: Dict[str, Dict[str, Any]] = {}
    for name, n, a1, a5, w5, sq5 in rows:
        edge, tstat = significance(a5, sq5, n, baseline)
        out[name] = {
            "rule_type": "candle",
            "rule_key": name,
            "sample_count": n,
            "avg_forward_1d": a1,
            "avg_forward_5d": a5,
            "win_rate_5d": w5,
            "baseline_forward_5d": baseline,
            "edge_forward_5d": edge,
            "t_stat_5d": tstat,
            "summary": (
                f"'{name}' as of {day} (n={n}): edge {edge:+.3f}% vs baseline "
                f"{baseline:+.3f}% (t={tstat:+.2f})"
                if edge is not None and tstat is not None
                else f"'{name}' as of {day} (n={n}): edge not measurable"
            ),
        }
    if len(_PIT_RULE_CACHE) > 4000:
        _PIT_RULE_CACHE.clear()
    _PIT_RULE_CACHE[key] = out
    return out


_PIT_NEWS_CACHE: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]] = {}
_PIT_INTRA_CACHE: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]] = {}


def news_rules_as_of(db_path: str, as_of: Any, horizon_buffer_days: int = 7) -> Dict[str, Dict[str, Any]]:
    """News rules from events whose 5-day outcome was already known at as_of."""
    day = str(as_of)[:10]
    key = (db_path, day)
    cached = _PIT_NEWS_CACHE.get(key)
    if cached is not None:
        return cached
    if not os.path.exists(db_path):
        return {}
    cutoff = (datetime.fromisoformat(day) - timedelta(days=horizon_buffer_days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    try:
        base_row = conn.execute(
            "SELECT AVG(forward_return_5d) FROM news_impact_events "
            "WHERE forward_return_5d IS NOT NULL AND event_trade_date < ?",
            (cutoff,),
        ).fetchone()
        baseline = float(base_row[0]) if base_row and base_row[0] is not None else 0.0
        rows = conn.execute(
            """
            SELECT topic, tone, COUNT(*) AS n,
                   AVG(forward_return_1d) AS a1,
                   AVG(forward_return_5d) AS a5,
                   AVG(CASE WHEN direction_5d = 'UP' THEN 1.0 ELSE 0 END) AS w5,
                   AVG(forward_return_5d * forward_return_5d) AS sq5
            FROM news_impact_events
            WHERE forward_return_5d IS NOT NULL AND event_trade_date < ?
            GROUP BY topic, tone
            HAVING COUNT(*) >= 3
            """,
            (cutoff,),
        ).fetchall()
    finally:
        conn.close()

    out: Dict[str, Dict[str, Any]] = {}
    for topic, tone, n, a1, a5, w5, sq5 in rows:
        edge, tstat = significance(a5, sq5, n, baseline)
        rkey = f"{topic}|{tone}"
        out[rkey] = {
            "rule_type": "news",
            "rule_key": rkey,
            "sample_count": n,
            "avg_forward_1d": a1,
            "avg_forward_5d": a5,
            "win_rate_5d": w5,
            "baseline_forward_5d": baseline,
            "edge_forward_5d": edge,
            "t_stat_5d": tstat,
            "summary": (
                f"news '{rkey}' as of {day} (n={n}): edge {edge:+.3f}% vs baseline "
                f"{baseline:+.3f}% (t={tstat:+.2f})"
                if edge is not None and tstat is not None
                else f"news '{rkey}' as of {day} (n={n}): edge not measurable"
            ),
        }
    if len(_PIT_NEWS_CACHE) > 4000:
        _PIT_NEWS_CACHE.clear()
    _PIT_NEWS_CACHE[key] = out
    return out


def intraday_rules_as_of(db_path: str, as_of: Any, horizon_buffer_days: int = 2) -> Dict[str, Dict[str, Any]]:
    """Intraday rules from bars whose mid-horizon outcome was known at as_of."""
    day = str(as_of)[:10]
    key = (db_path, day)
    cached = _PIT_INTRA_CACHE.get(key)
    if cached is not None:
        return cached
    if not os.path.exists(db_path):
        return {}
    cutoff = (datetime.fromisoformat(day) - timedelta(days=horizon_buffer_days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    try:
        base_row = conn.execute(
            "SELECT AVG(forward_return_3b) FROM intraday_candle_events "
            "WHERE forward_return_3b IS NOT NULL AND event_ts < ?",
            (cutoff,),
        ).fetchone()
        baseline = float(base_row[0]) if base_row and base_row[0] is not None else 0.0
        rows = conn.execute(
            """
            SELECT interval, pattern_name, COUNT(*) AS n,
                   AVG(forward_return_1b) AS a1,
                   AVG(forward_return_3b) AS a3,
                   AVG(CASE WHEN direction_3b = 'UP' THEN 1.0 ELSE 0 END) AS w3,
                   AVG(forward_return_3b * forward_return_3b) AS sq3
            FROM intraday_candle_events
            WHERE forward_return_3b IS NOT NULL AND substr(event_ts, 1, 10) < ?
            GROUP BY interval, pattern_name
            HAVING COUNT(*) >= 5
            """,
            (cutoff,),
        ).fetchall()
    finally:
        conn.close()

    out: Dict[str, Dict[str, Any]] = {}
    for interval, name, n, a1, a3, w3, sq3 in rows:
        edge, tstat = significance(a3, sq3, n, baseline)
        rkey = f"{interval}|{name}"
        out[rkey] = {
            "rule_type": "candle_intraday",
            "rule_key": rkey,
            "sample_count": n,
            "avg_forward_1d": a1,
            "avg_forward_5d": a3,
            "win_rate_5d": w3,
            "baseline_forward_5d": baseline,
            "edge_forward_5d": edge,
            "t_stat_5d": tstat,
            "summary": (
                f"intraday '{rkey}' as of {day} (n={n}): edge {edge:+.3f}% "
                f"(t={tstat:+.2f})"
                if edge is not None and tstat is not None
                else f"intraday '{rkey}' as of {day} (n={n}): edge not measurable"
            ),
        }
    if len(_PIT_INTRA_CACHE) > 4000:
        _PIT_INTRA_CACHE.clear()
    _PIT_INTRA_CACHE[key] = out
    return out


def lookup_rules_for_patterns(
    db_path: str, patterns: List[str], as_of: Optional[Any] = None
) -> List[Dict[str, Any]]:
    if not patterns or not os.path.exists(db_path):
        return []
    if as_of is not None:
        pit = candle_rules_as_of(db_path, as_of)
        return [pit[p] for p in patterns if p in pit]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    out = []
    for p in patterns:
        row = conn.execute(
            "SELECT * FROM learned_rules WHERE rule_type = 'candle' AND rule_key = ?",
            (p,),
        ).fetchone()
        if row:
            out.append(dict(row))
    conn.close()
    return out


def lookup_rules_for_news(
    db_path: str, topics: List[str], tone: str, as_of: Optional[Any] = None
) -> List[Dict[str, Any]]:
    if not os.path.exists(db_path):
        return []
    if as_of is not None:
        pit = news_rules_as_of(db_path, as_of)
        return [pit[f"{t}|{tone}"] for t in topics if f"{t}|{tone}" in pit]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    out = []
    for topic in topics:
        key = f"{topic}|{tone}"
        row = conn.execute(
            "SELECT * FROM learned_rules WHERE rule_type = 'news' AND rule_key = ?",
            (key,),
        ).fetchone()
        if row:
            out.append(dict(row))
    conn.close()
    return out


def lookup_intraday_rules(
    db_path: str,
    patterns: List[str],
    interval: str = "5minute",
    as_of: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    if not patterns or not os.path.exists(db_path):
        return []
    if as_of is not None:
        pit = intraday_rules_as_of(db_path, as_of)
        return [pit[f"{interval}|{p}"] for p in patterns if f"{interval}|{p}" in pit]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    out = []
    for p in patterns:
        key = f"{interval}|{p}"
        row = conn.execute(
            "SELECT * FROM learned_rules WHERE rule_type = 'candle_intraday' AND rule_key = ?",
            (key,),
        ).fetchone()
        if row:
            out.append(dict(row))
    conn.close()
    return out


def apply_knowledge_to_prediction(
    db_path: str,
    model_dir: str,
    stock_key: str,
    candle_patterns: List[str],
    recent_news: List[Dict[str, Any]],
    raw_indicators: Optional[Dict[str, Any]] = None,
    *,
    intraday_interval: Optional[str] = None,
    as_of: Optional[Any] = None,
) -> Dict[str, Any]:
    """Match current setup to stored rules + optional memory ML models."""
    rules = lookup_rules_for_patterns(db_path, candle_patterns, as_of=as_of)
    topics = [classify_news_topic(n.get("title", ""), n.get("summary")) for n in recent_news[:5]]
    tone = classify_news_tone(
        " ".join(n.get("title", "") for n in recent_news[:3]),
        None,
    )
    rules.extend(lookup_rules_for_news(db_path, list(set(topics)), tone, as_of=as_of))
    if intraday_interval:
        rules.extend(lookup_intraday_rules(
            db_path, candle_patterns, intraday_interval, as_of=as_of
        ))

    adjust = 0.0
    summaries: List[str] = []
    skipped: List[str] = []
    for r in rules:
        n = int(r.get("sample_count") or 0)
        key = r.get("rule_key") or "?"
        edge = r.get("edge_forward_5d")
        tstat = r.get("t_stat_5d")
        if n < KNOWLEDGE_MIN_RULE_SAMPLES:
            skipped.append(f"{key}: only {n} samples (need {KNOWLEDGE_MIN_RULE_SAMPLES})")
            continue
        if edge is None or tstat is None:
            skipped.append(f"{key}: edge vs baseline not measured")
            continue
        if abs(float(tstat)) < KNOWLEDGE_MIN_TSTAT:
            skipped.append(f"{key}: edge {float(edge):+.3f}% not significant (t={float(tstat):+.2f})")
            continue
        summaries.append(r.get("summary", ""))
        # Vote on the excess return over baseline drift, not the raw forward return.
        adjust += float(edge) / 500.0

    ml_scores: Dict[str, Any] = {}
    # Memory ML is trained on the full scan, so it leaks the future inside a
    # historical audit. Live calls (as_of is None) may still use it.
    if as_of is not None:
        ml_scores["skipped"] = "point-in-time audit does not use full-history memory ML"
    elif joblib and os.path.isdir(model_dir):
        candle_path = os.path.join(model_dir, "pattern_memory_candle.joblib")
        if os.path.isfile(candle_path) and candle_patterns:
            try:
                pack = joblib.load(candle_path)
                metrics = pack.get("metrics") or {}
                auc = metrics.get("test_auc")
                if auc is not None and float(auc) < KNOWLEDGE_ML_MIN_AUC:
                    ml_scores["candle_skipped"] = f"AUC {auc:.2f} below {KNOWLEDGE_ML_MIN_AUC}"
                else:
                    model = pack["model"]
                    cols = pack["feature_cols"]
                    row = {c: 0.0 for c in cols}
                    for p in candle_patterns:
                        col = f"pat_{p}"
                        if col in row:
                            row[col] = 1.0
                    if raw_indicators:
                        if "rsi_14" in row:
                            row["rsi_14"] = float(raw_indicators.get("rsi_14") or 0)
                        if "vol_ratio" in row:
                            row["vol_ratio"] = float(raw_indicators.get("vol_ratio") or 1)
                    X = pd.DataFrame([row])[cols]
                    ml_scores["candle_up_5d"] = float(model.predict_proba(X)[0, 1])
                    adjust += (ml_scores["candle_up_5d"] - 0.5) * 0.03
            except Exception as exc:
                ml_scores["candle_error"] = str(exc)

    adjust = max(-0.06, min(0.06, adjust))
    return {
        "source": "knowledge.db",
        "matched_rules": rules,
        "rule_summaries": summaries[:8],
        "skipped_rules": skipped[:8],
        "applied_rule_count": len(summaries),
        "combined_adjust": round(adjust, 4),
        "memory_ml": ml_scores,
        "topics_checked": topics,
    }
