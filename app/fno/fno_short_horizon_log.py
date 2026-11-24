"""Log 5m/10m short-horizon predictions and settle them for quality research.

Each finished 5m bucket stores one prediction (side, p_side, expected pts,
feature snapshot). When later bars arrive, we fill actual moves so hit-rate
and calibration can be scored offline.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

_lock = threading.Lock()
_last_log: Dict[str, float] = {}
_MIN_GAP_SEC = 20.0


def default_db_path() -> str:
    import knowledge_db

    return knowledge_db.ensure_db_dir()


def ensure_tables(db_path: Optional[str] = None) -> str:
    path = db_path or default_db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS fno_short_horizon_pred (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock TEXT NOT NULL,
            session_date TEXT NOT NULL,
            pred_bucket TEXT NOT NULL,
            mode TEXT,
            side TEXT,
            p_side REAL,
            p_up REAL,
            expected_pts_5m REAL,
            expected_pts_10m REAL,
            remain_pts REAL,
            atr_5m REAL,
            price REAL,
            candle_open REAL,
            candle_ltp REAL,
            candle_change REAL,
            candle_progress REAL,
            live_p_up REAL,
            micro_score REAL,
            checklist_bull INTEGER,
            checklist_bear INTEGER,
            mom_p_up REAL,
            blend_json TEXT,
            features_json TEXT,
            settled INTEGER NOT NULL DEFAULT 0,
            actual_side_5m TEXT,
            actual_move_5m REAL,
            hit_side_5m INTEGER,
            abs_err_5m REAL,
            actual_side_10m TEXT,
            actual_move_10m REAL,
            hit_side_10m INTEGER,
            abs_err_10m REAL,
            settled_at TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(stock, pred_bucket)
        );
        CREATE INDEX IF NOT EXISTS idx_shp_day
            ON fno_short_horizon_pred(session_date, stock);
        CREATE INDEX IF NOT EXISTS idx_shp_unset
            ON fno_short_horizon_pred(stock, settled, pred_bucket);
        """
    )
    conn.commit()
    conn.close()
    return path


def _num(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _bucket_from_candle(sh: Dict[str, Any], asof: Any = None) -> str:
    candle = sh.get("candle") if isinstance(sh.get("candle"), dict) else {}
    start = candle.get("start")
    day = None
    if asof:
        try:
            text = str(asof).replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            day = dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    if not day:
        day = datetime.now().strftime("%Y-%m-%d")
    if start and ":" in str(start):
        return f"{day}T{start}"
    now = datetime.now().replace(second=0, microsecond=0)
    floored = now.replace(minute=(now.minute // 5) * 5)
    return floored.strftime("%Y-%m-%dT%H:%M")


def _parse_bucket(bucket: str) -> Optional[datetime]:
    try:
        return datetime.strptime(str(bucket)[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def _side_from_move(move: float, *, dead: float = 1.5) -> str:
    if move > dead:
        return "UP"
    if move < -dead:
        return "DOWN"
    return "SIDEWAYS"


def _bar_close_at(bars: Any, when: datetime) -> Optional[Tuple[float, float]]:
    """Return (open, close) of the 5m bar that starts at `when` (naive local)."""
    if bars is None:
        return None
    try:
        if getattr(bars, "empty", True):
            return None
        # Prefer exact index match; else nearest within 2 minutes.
        for ts in bars.index:
            t = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            if getattr(t, "tzinfo", None) is not None:
                t = t.astimezone().replace(tzinfo=None)
            if abs((t - when).total_seconds()) <= 120:
                row = bars.loc[ts]
                cols = {str(c).lower(): c for c in bars.columns}
                o = float(row[cols["open"]]) if "open" in cols else float(row.iloc[0])
                c = float(row[cols["close"]]) if "close" in cols else float(row.iloc[3])
                return o, c
    except Exception:
        return None
    return None


def log_prediction(
    *,
    stock: str,
    short_horizon: Optional[Dict[str, Any]],
    price: Optional[float] = None,
    live_context: Optional[Dict[str, Any]] = None,
    indications: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
    force: bool = False,
) -> bool:
    """Upsert prediction for the current 5m bucket. Returns True if written."""
    sh = short_horizon if isinstance(short_horizon, dict) else {}
    key = (stock or "").strip().upper()
    if not key or not sh.get("available"):
        return False
    side = str(sh.get("side") or "")
    if not side:
        return False

    path = ensure_tables(db_path)
    now = time.time()
    with _lock:
        last = _last_log.get(key, 0.0)
        if not force and (now - last) < _MIN_GAP_SEC:
            return False
        _last_log[key] = now

    live = live_context or {}
    micro = live.get("microstructure") or {}
    candle = sh.get("candle") if isinstance(sh.get("candle"), dict) else {}
    summary = (indications or {}).get("summary") if isinstance(indications, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    blend = sh.get("blend") if isinstance(sh.get("blend"), dict) else {}
    asof = sh.get("asof") or live.get("asof") or live.get("received_at_ist")
    bucket = _bucket_from_candle(sh, asof)
    day = bucket[:10]
    created = datetime.now().isoformat(timespec="seconds")

    features = {
        "headline": sh.get("headline"),
        "mode": sh.get("mode"),
        "tone": sh.get("tone"),
        "weights": blend.get("weights"),
        "inputs": blend.get("inputs"),
        "votes": sh.get("votes"),
        "react_up": sh.get("react_up"),
        "react_down": sh.get("react_down"),
        "candle": candle,
        "micro_bias": micro.get("micro_bias"),
        "structure_lean": sh.get("structure_lean"),
        "mom_p_up": sh.get("mom_p_up"),
    }

    row = (
        key,
        day,
        bucket,
        sh.get("mode"),
        side,
        _num(sh.get("p_side")),
        _num(sh.get("p_up")),
        _num(sh.get("expected_points_5m")),
        _num(sh.get("expected_points_10m")),
        _num(sh.get("remain_points")),
        _num(sh.get("atr_5m")),
        _num(price),
        _num(candle.get("open")),
        _num(candle.get("ltp")),
        _num(candle.get("change_pts")),
        _num(candle.get("progress_pct")),
        _num(live.get("live_probability_up") or live.get("live_p") or (blend.get("inputs") or {}).get("live_p")),
        _num(micro.get("micro_score")),
        int(summary.get("bullish") or 0) if summary else None,
        int(summary.get("bearish") or 0) if summary else None,
        _num(sh.get("mom_p_up") or (blend.get("inputs") or {}).get("momentum")),
        json.dumps(blend, default=str),
        json.dumps(features, default=str),
        created,
    )

    try:
        conn = sqlite3.connect(path)
        # Keep first prediction for the bucket (don't thrash mid-bar); update
        # price/candle progress fields only if still unsettled.
        existing = conn.execute(
            "SELECT id, settled FROM fno_short_horizon_pred WHERE stock=? AND pred_bucket=?",
            (key, bucket),
        ).fetchone()
        if existing and int(existing[1] or 0) == 1:
            conn.close()
            return False
        if existing:
            conn.execute(
                """
                UPDATE fno_short_horizon_pred SET
                    side=?, p_side=?, p_up=?, expected_pts_5m=?, expected_pts_10m=?,
                    remain_pts=?, atr_5m=?, price=?, candle_open=?, candle_ltp=?,
                    candle_change=?, candle_progress=?, live_p_up=?, micro_score=?,
                    checklist_bull=?, checklist_bear=?, mom_p_up=?, blend_json=?,
                    features_json=?, mode=?
                WHERE id=?
                """,
                (
                    side,
                    _num(sh.get("p_side")),
                    _num(sh.get("p_up")),
                    _num(sh.get("expected_points_5m")),
                    _num(sh.get("expected_points_10m")),
                    _num(sh.get("remain_points")),
                    _num(sh.get("atr_5m")),
                    _num(price),
                    _num(candle.get("open")),
                    _num(candle.get("ltp")),
                    _num(candle.get("change_pts")),
                    _num(candle.get("progress_pct")),
                    _num(live.get("live_probability_up") or live.get("live_p")),
                    _num(micro.get("micro_score")),
                    int(summary.get("bullish") or 0) if summary else None,
                    int(summary.get("bearish") or 0) if summary else None,
                    _num(sh.get("mom_p_up") or (blend.get("inputs") or {}).get("momentum")),
                    json.dumps(blend, default=str),
                    json.dumps(features, default=str),
                    sh.get("mode"),
                    existing[0],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO fno_short_horizon_pred (
                    stock, session_date, pred_bucket, mode, side, p_side, p_up,
                    expected_pts_5m, expected_pts_10m, remain_pts, atr_5m, price,
                    candle_open, candle_ltp, candle_change, candle_progress,
                    live_p_up, micro_score, checklist_bull, checklist_bear,
                    mom_p_up, blend_json, features_json, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                row,
            )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def settle_pending(
    *,
    stock: str,
    bars_5m: Any = None,
    db_path: Optional[str] = None,
    limit: int = 40,
) -> int:
    """Fill actual 5m/10m outcomes for unsettled predictions. Returns settled count."""
    key = (stock or "").strip().upper()
    if not key or bars_5m is None:
        return 0
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, pred_bucket, side, expected_pts_5m, expected_pts_10m, price, candle_open
        FROM fno_short_horizon_pred
        WHERE stock=? AND settled=0
        ORDER BY pred_bucket ASC
        LIMIT ?
        """,
        (key, int(limit)),
    ).fetchall()
    settled_n = 0
    now_iso = datetime.now().isoformat(timespec="seconds")
    for r in rows:
        start = _parse_bucket(r["pred_bucket"])
        if start is None:
            continue
        # Need the predicted bar to be finished (+ a little slack).
        if datetime.now() < start + timedelta(minutes=5, seconds=15):
            continue
        bar5 = _bar_close_at(bars_5m, start)
        if not bar5:
            continue
        o5, c5 = bar5
        # Prefer candle_open from prediction if present.
        open_px = _num(r["candle_open"]) or o5
        move5 = c5 - open_px
        act5 = _side_from_move(move5)
        pred_side = str(r["side"] or "")
        hit5 = None
        if pred_side in ("UP", "DOWN"):
            hit5 = 1 if act5 == pred_side else (0 if act5 != "SIDEWAYS" else None)
        elif pred_side == "SIDEWAYS":
            hit5 = 1 if act5 == "SIDEWAYS" else 0
        exp5 = _num(r["expected_pts_5m"])
        abs_err5 = abs(abs(move5) - exp5) if exp5 is not None else None

        # 10m = open of pred bar → close of next finished bar
        bar10 = _bar_close_at(bars_5m, start + timedelta(minutes=5))
        act10 = move10 = hit10 = abs_err10 = None
        if bar10 and datetime.now() >= start + timedelta(minutes=10, seconds=15):
            _o10, c10 = bar10
            move10 = c10 - open_px
            act10 = _side_from_move(move10)
            if pred_side in ("UP", "DOWN"):
                hit10 = 1 if act10 == pred_side else (0 if act10 != "SIDEWAYS" else None)
            elif pred_side == "SIDEWAYS":
                hit10 = 1 if act10 == "SIDEWAYS" else 0
            exp10 = _num(r["expected_pts_10m"])
            abs_err10 = abs(abs(move10) - exp10) if exp10 is not None else None

        # Settle when 10m window is observable; otherwise store 5m partial only.
        fully = bar10 is not None and datetime.now() >= start + timedelta(minutes=10, seconds=15)
        if fully:
            conn.execute(
                """
                UPDATE fno_short_horizon_pred SET
                    actual_side_5m=?, actual_move_5m=?, hit_side_5m=?, abs_err_5m=?,
                    actual_side_10m=?, actual_move_10m=?, hit_side_10m=?, abs_err_10m=?,
                    settled=1, settled_at=?
                WHERE id=?
                """,
                (
                    act5,
                    round(move5, 2),
                    hit5,
                    round(abs_err5, 2) if abs_err5 is not None else None,
                    act10,
                    round(move10, 2) if move10 is not None else None,
                    hit10,
                    round(abs_err10, 2) if abs_err10 is not None else None,
                    now_iso,
                    r["id"],
                ),
            )
            settled_n += 1
        else:
            conn.execute(
                """
                UPDATE fno_short_horizon_pred SET
                    actual_side_5m=?, actual_move_5m=?, hit_side_5m=?, abs_err_5m=?
                WHERE id=?
                """,
                (
                    act5,
                    round(move5, 2),
                    hit5,
                    round(abs_err5, 2) if abs_err5 is not None else None,
                    r["id"],
                ),
            )
    conn.commit()
    conn.close()
    return settled_n


def maybe_record_and_settle(
    *,
    stock: str,
    short_horizon: Optional[Dict[str, Any]],
    price: Optional[float] = None,
    live_context: Optional[Dict[str, Any]] = None,
    indications: Optional[Dict[str, Any]] = None,
    bars_5m: Any = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience for analyze/rescore paths."""
    logged = log_prediction(
        stock=stock,
        short_horizon=short_horizon,
        price=price,
        live_context=live_context,
        indications=indications,
        db_path=db_path,
    )
    bars = bars_5m
    if bars is None and isinstance(live_context, dict):
        bars = live_context.get("bars_5m")
    n = settle_pending(stock=stock, bars_5m=bars, db_path=db_path)
    return {"logged": logged, "settled": n}


def recent_accuracy(
    *,
    stock: Optional[str] = None,
    db_path: Optional[str] = None,
    limit: int = 200,
) -> Dict[str, Any]:
    """Quick hit-rate summary for settled predictions."""
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    if stock:
        rows = conn.execute(
            """
            SELECT side, hit_side_5m, hit_side_10m, abs_err_5m, abs_err_10m
            FROM fno_short_horizon_pred
            WHERE stock=? AND settled=1
            ORDER BY pred_bucket DESC LIMIT ?
            """,
            (stock.strip().upper(), int(limit)),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT side, hit_side_5m, hit_side_10m, abs_err_5m, abs_err_10m
            FROM fno_short_horizon_pred
            WHERE settled=1
            ORDER BY pred_bucket DESC LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    conn.close()
    if not rows:
        return {"available": False, "n": 0}

    def _rate(field: str) -> Optional[float]:
        vals = [int(r[field]) for r in rows if r[field] is not None]
        if not vals:
            return None
        return round(100.0 * sum(vals) / len(vals), 1)

    def _mae(field: str) -> Optional[float]:
        vals = [_num(r[field]) for r in rows if _num(r[field]) is not None]
        vals = [v for v in vals if v is not None]
        if not vals:
            return None
        return round(sum(vals) / len(vals), 2)

    return {
        "available": True,
        "n": len(rows),
        "hit_pct_5m": _rate("hit_side_5m"),
        "hit_pct_10m": _rate("hit_side_10m"),
        "mae_pts_5m": _mae("abs_err_5m"),
        "mae_pts_10m": _mae("abs_err_10m"),
    }
