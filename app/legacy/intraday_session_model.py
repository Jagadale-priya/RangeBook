"""Dedicated Intraday 15m model. Separate from the daily cash ensemble.

Label is the next four 15m bars (~60 minutes), same session only.
Each saved pack keeps at most one side (BUY or SELL) that cleared holdout.
Live tickets use the F&O small clip (NIFTY 25/30, BANKNIFTY 60/75, stocks ~0.25/0.30%).
Research model — not live trading advice.
"""

from __future__ import annotations

import os
from datetime import time as dtime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import joblib
except ImportError:
    joblib = None  # type: ignore

try:
    from sklearn.ensemble import HistGradientBoostingClassifier
except ImportError:
    HistGradientBoostingClassifier = None  # type: ignore

import fno_session_model

MODEL_VERSION = "intraday_session_1.1"
HORIZON_BARS = 4
MIN_MOVE = 0.0005
BUY_P = 0.64
SELL_P = 0.36
HOLDOUT_FRAC = 0.20
MIN_TRAIN_SAMPLES = 200
MIN_TRAIN_DAYS = 20
MIN_SIDE_TRADES = 25
MIN_SIDE_PRECISION = 0.58
FEATURE_WINDOW = 80
ENTRY_AFTER = dtime(9, 45)
ENTRY_CUTOFF = dtime(14, 0)

FEATURE_NAMES = fno_session_model.FEATURE_NAMES + (
    "session_chg",
    "gap_pct",
    "minutes_from_open",
)

import path_setup
ROOT = str(path_setup.ROOT)
MODEL_DIR = os.path.join(ROOT, "stock_signal_data", "models")
TAPE_DIR = os.path.join(ROOT, "stock_signal_data", "fno_validate")


def model_path(symbol: str) -> str:
    return os.path.join(MODEL_DIR, f"intraday_{symbol.strip().upper()}.pkl")


def _clock(ts: Any) -> dtime:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("Asia/Kolkata")
    return t.to_pydatetime().replace(tzinfo=None).time()


def _to_date(ts: Any):
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("Asia/Kolkata")
    return t.date()


def features_from_bars(df: Any) -> Optional[Dict[str, float]]:
    base = fno_session_model.features_from_bars(df)
    if not base:
        return None
    work = fno_session_model._norm(df)
    session_chg = 0.0
    gap_pct = 0.0
    minutes_from_open = 0.0
    if work is not None and len(work):
        last_ts = work.index[-1]
        day = _to_date(last_ts)
        session = work[[_to_date(i) == day for i in work.index]]
        try:
            o = float(session["Open"].astype(float).iloc[0])
            c = float(session["Close"].astype(float).iloc[-1])
            if o:
                session_chg = (c - o) / o * 100.0
            prev = work[[_to_date(i) < day for i in work.index]]
            if len(prev) and o:
                prev_c = float(prev["Close"].astype(float).iloc[-1])
                if prev_c:
                    gap_pct = (o - prev_c) / prev_c * 100.0
            first = pd.Timestamp(session.index[0])
            last = pd.Timestamp(last_ts)
            minutes_from_open = max(0.0, (last - first).total_seconds() / 60.0)
        except Exception:
            pass
    out = dict(base)
    out["session_chg"] = session_chg
    out["gap_pct"] = gap_pct
    out["minutes_from_open"] = minutes_from_open
    return out


def _xy(df: pd.DataFrame) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    work = fno_session_model._norm(df)
    if work is None or len(work) < 60:
        return None, None, None
    days = np.array([_to_date(i) for i in work.index])
    close = work["Close"].astype(float)
    rows: List[List[float]] = []
    labels: List[int] = []
    day_labels: List[str] = []
    last_i = len(work) - HORIZON_BARS
    for i in range(20, last_i):
        clock = _clock(work.index[i])
        if clock < ENTRY_AFTER or clock > ENTRY_CUTOFF:
            continue
        later_i = i + HORIZON_BARS
        if days[later_i] != days[i]:
            continue
        now = float(close.iloc[i])
        later = float(close.iloc[later_i])
        if now <= 0:
            continue
        ret = (later - now) / now
        if ret >= MIN_MOVE:
            y = 1
        elif ret <= -MIN_MOVE:
            y = 0
        else:
            continue
        start = max(0, i + 1 - FEATURE_WINDOW)
        feat = features_from_bars(work.iloc[start : i + 1])
        if not feat:
            continue
        rows.append([float(feat[k]) for k in FEATURE_NAMES])
        labels.append(y)
        day_labels.append(str(days[i]))
    if len(rows) < 80:
        return None, None, None
    return (
        np.asarray(rows, dtype=float),
        np.asarray(labels, dtype=int),
        np.asarray(day_labels),
    )


def _holdout_split(day_labels: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    uniq = sorted(set(day_labels.tolist()))
    cut = max(1, int(len(uniq) * (1.0 - HOLDOUT_FRAC)))
    train_days = set(uniq[:cut])
    train_ix = np.array([d in train_days for d in day_labels])
    test_ix = ~train_ix
    if int(test_ix.sum()) < 20:
        n = len(day_labels)
        split = max(40, int(n * (1.0 - HOLDOUT_FRAC)))
        train_ix = np.zeros(n, dtype=bool)
        train_ix[:split] = True
        test_ix = ~train_ix
    return train_ix, test_ix


def _threshold_stats(proba: np.ndarray, y: np.ndarray, buy_p: float, sell_p: float) -> Dict[str, Any]:
    buy = proba >= buy_p
    sell = proba <= sell_p
    pred = np.full(len(y), -1)
    pred[buy] = 1
    pred[sell] = 0
    taken = pred >= 0
    n = int(taken.sum())
    if n == 0:
        return {"n_trades": 0, "accuracy": None, "precision_buy": None, "precision_sell": None}
    acc = float((pred[taken] == y[taken]).mean())
    pb = float((y[buy] == 1).mean()) if int(buy.sum()) else None
    ps = float((y[sell] == 0).mean()) if int(sell.sum()) else None
    return {
        "n_trades": n,
        "accuracy": round(acc, 4),
        "precision_buy": None if pb is None else round(pb, 4),
        "precision_sell": None if ps is None else round(ps, 4),
        "n_buy": int(buy.sum()),
        "n_sell": int(sell.sum()),
    }


def _proven_side(high: Dict[str, Any]) -> Optional[str]:
    """Keep the single holdout side that is both frequent and accurate enough."""
    buy_n = int(high.get("n_buy") or 0)
    sell_n = int(high.get("n_sell") or 0)
    buy_p = high.get("precision_buy")
    sell_p = high.get("precision_sell")
    buy_ok = buy_p is not None and float(buy_p) >= MIN_SIDE_PRECISION and buy_n >= MIN_SIDE_TRADES
    sell_ok = sell_p is not None and float(sell_p) >= MIN_SIDE_PRECISION and sell_n >= MIN_SIDE_TRADES
    if buy_ok and sell_ok:
        return "BUY" if float(buy_p) >= float(sell_p) else "SELL"
    if buy_ok:
        return "BUY"
    if sell_ok:
        return "SELL"
    return None


def clip_levels(symbol: str, price: float, decision: str) -> Optional[Dict[str, Any]]:
    """Small stop and first target. Same clips as the F&O book."""
    if decision not in ("BUY", "SELL") or price <= 0:
        return None
    import fno_risk_engine

    sl_pts, t1_pts, _t2, _key = fno_risk_engine.clip_points(symbol, price)
    sl, t1, _ = fno_risk_engine._apply_clip("SELL" in decision, float(price), sl_pts, t1_pts, None)
    return {
        "stop_loss": sl,
        "target_1": t1,
        "stop_points": sl_pts,
        "target_points": t1_pts,
        "note": "60-minute clip. Stop and target are small; no 2x ATR swing levels.",
    }


def train(df: Any) -> Dict[str, Any]:
    """Fit the 60-minute head. One proven side, or none if holdout is weak."""
    work = df if isinstance(df, pd.DataFrame) else fno_session_model._norm(df)
    X, y, days = _xy(work)
    if X is None or HistGradientBoostingClassifier is None:
        return {"available": False, "reason": "not_enough_rows_or_sklearn", "model_version": MODEL_VERSION}
    if len(set(y.tolist())) < 2:
        return {"available": False, "reason": "single_class_labels", "model_version": MODEL_VERSION}
    train_ix, test_ix = _holdout_split(days)
    if int(train_ix.sum()) < MIN_TRAIN_SAMPLES or int(test_ix.sum()) < 20:
        return {"available": False, "reason": "holdout_too_small", "model_version": MODEL_VERSION}
    model = HistGradientBoostingClassifier(
        max_depth=3, max_iter=80, learning_rate=0.07, random_state=17
    )
    model.fit(X[train_ix], y[train_ix])
    classes = list(model.classes_)
    proba = model.predict_proba(X[test_ix])
    p_up = proba[:, classes.index(1)] if 1 in classes else np.full(int(test_ix.sum()), 0.5)
    y_te = y[test_ix]
    mid = _threshold_stats(p_up, y_te, 0.55, 0.45)
    high = _threshold_stats(p_up, y_te, BUY_P, SELL_P)
    stricter = _threshold_stats(p_up, y_te, 0.70, 0.30)
    pred = (p_up >= 0.5).astype(int)
    acc_all = float((pred == y_te).mean())
    side = _proven_side(high)
    return {
        "available": True,
        "model": model,
        "feature_names": list(FEATURE_NAMES),
        "holdout_accuracy": round(acc_all, 4),
        "holdout_all_bars": mid,
        "holdout_high_conf": high,
        "holdout_strict": stricter,
        "allowed_side": side,
        "n_train": int(train_ix.sum()),
        "n_holdout": int(test_ix.sum()),
        "n_days_train": int(len(set(days[train_ix].tolist()))),
        "n_days_holdout": int(len(set(days[test_ix].tolist()))),
        "model_version": MODEL_VERSION,
        "interval": "15minute",
        "horizon_bars": HORIZON_BARS,
        "label": "next_60m",
        "min_move": MIN_MOVE,
        "buy_p": BUY_P,
        "sell_p": SELL_P,
    }


def save(pack: Dict[str, Any], path: Optional[str] = None, symbol: str = "NIFTY") -> str:
    dest = path or model_path(symbol)
    if joblib is None or not pack.get("available"):
        return dest
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    joblib.dump(dict(pack), dest)
    return dest


def pack_usable(pack: Optional[Dict[str, Any]]) -> bool:
    if not pack or not pack.get("available") or pack.get("model") is None:
        return False
    if pack.get("model_version") != MODEL_VERSION:
        return False
    if int(pack.get("n_train") or 0) < MIN_TRAIN_SAMPLES:
        return False
    if int(pack.get("n_days_train") or 0) < MIN_TRAIN_DAYS:
        return False
    return True


def load(symbol: str = "NIFTY") -> Dict[str, Any]:
    dest = model_path(symbol)
    if joblib is None or not os.path.isfile(dest):
        return {"available": False, "model_version": MODEL_VERSION}
    try:
        pack = joblib.load(dest)
        if not pack_usable({**pack, "available": True}):
            return {
                "available": False,
                "reason": pack.get("reason") or "unusable_pack",
                "model_version": MODEL_VERSION,
            }
        pack["available"] = True
        return pack
    except Exception:
        return {"available": False, "model_version": MODEL_VERSION}


def infer(df: Any, model_pack: Optional[Dict[str, Any]] = None, *, symbol: str = "") -> Dict[str, Any]:
    feat = features_from_bars(df)
    if not feat:
        return {"available": False, "p_up": 0.5, "decision": "HOLD", "source": "none"}
    p_rule = fno_session_model.rule_p_up(feat)
    p_model = None
    pack = model_pack or {}
    if pack.get("available") and pack.get("model") is not None:
        try:
            x = np.asarray([[float(feat[k]) for k in FEATURE_NAMES]], dtype=float)
            proba = pack["model"].predict_proba(x)[0]
            classes = list(pack["model"].classes_)
            p_model = float(proba[classes.index(1)]) if 1 in classes else p_rule
        except Exception:
            p_model = None
    p_up = p_model if p_model is not None else p_rule
    p_up = max(0.05, min(0.95, float(p_up)))
    buy_p = float(pack.get("buy_p") or BUY_P)
    sell_p = float(pack.get("sell_p") or SELL_P)
    allowed = pack.get("allowed_side")
    raw = "HOLD"
    if p_up >= buy_p:
        raw = "BUY"
    elif p_up <= sell_p:
        raw = "SELL"
    if allowed not in ("BUY", "SELL"):
        decision = "HOLD"
        source = "no_proven_side"
    elif raw == allowed:
        decision = raw
        source = "hgb_intraday" if p_model is not None else "rule_intraday"
    else:
        decision = "HOLD"
        source = "other_side_blocked"
    price = 0.0
    work = fno_session_model._norm(df)
    if work is not None and len(work):
        price = float(work["Close"].astype(float).iloc[-1])
    return {
        "available": True,
        "p_up": round(p_up, 4),
        "p_rule": round(float(p_rule), 4),
        "decision": decision,
        "raw_decision": raw,
        "allowed_side": allowed,
        "confidence": round(50 + abs(p_up - 0.5) * 100, 1),
        "source": source,
        "clip": clip_levels(symbol, price, decision),
        "holdout_high_conf": pack.get("holdout_high_conf"),
        "horizon": "60m",
        "model_version": MODEL_VERSION,
    }


def cached_15m(symbol: str) -> Optional[pd.DataFrame]:
    sym = symbol.strip().upper()
    for name in (f"{sym}_15m_5y.csv", f"{sym}_15m_6m.csv", f"{sym}_15m.csv"):
        path = os.path.join(TAPE_DIR, name)
        if not os.path.isfile(path):
            continue
        try:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            work = fno_session_model._norm(df)
            if work is not None and len(work) >= 80:
                return work
        except Exception:
            continue
    return None
