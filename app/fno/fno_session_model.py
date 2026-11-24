"""Light same-day F&O head on 5-minute bars (not the daily cash ensemble).

Train once on prior 5m history. Predict is milliseconds. Live path never retrains.
"""

from __future__ import annotations

import os
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

import analysis_engine

FEATURE_NAMES = (
    "ret_3",
    "ret_6",
    "ret_12",
    "rsi_14",
    "vwap_dist",
    "range_pos",
    "candle_score",
    "vol_ratio",
    "bar_range_pct",
    "or_break",
)

MODEL_VERSION = "fno_session_1.0"
HORIZON_BARS_15M = 4  # 60 minutes on 15m
HORIZON_BARS_5M = 6  # 30 minutes on 5m
MIN_MOVE = 0.0005  # 0.05% — typical Nifty 30–60 min clip


def _norm(df: Any) -> Optional[pd.DataFrame]:
    if df is None or len(df) < 16:
        return None
    out = df.copy()
    colmap = {str(c).lower(): c for c in out.columns}
    for src, dst in (("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close"), ("volume", "Volume")):
        if dst not in out.columns and src in colmap:
            out[dst] = out[colmap[src]]
    if "Close" not in out.columns:
        return None
    if "Volume" not in out.columns:
        out["Volume"] = 1.0
    return out.sort_index()


def _rsi(close: pd.Series, period: int = 14, *, legacy: bool = False) -> float:
    delta = close.diff()
    up = delta.clip(lower=0).rolling(period).mean()
    down = (-delta.clip(upper=0)).rolling(period).mean()
    if not legacy and len(down) and float(down.iloc[-1]) == 0:
        return 100.0 if float(up.iloc[-1]) > 0 else 50.0
    rs = up / down.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = float(rsi.iloc[-1])
    return val if np.isfinite(val) else 50.0


def features_from_bars(df: Any, *, legacy: bool = False) -> Optional[Dict[str, float]]:
    work = _norm(df)
    if work is None:
        return None
    close = work["Close"].astype(float)
    high = work["High"].astype(float)
    low = work["Low"].astype(float)
    vol = work["Volume"].astype(float)
    last = float(close.iloc[-1])
    if last <= 0:
        return None

    def _ret(n: int) -> float:
        if len(close) <= n:
            return 0.0
        prev = float(close.iloc[-n - 1])
        return (last - prev) / prev * 100.0 if prev else 0.0

    typical = (high + low + close) / 3.0
    vwap = float((typical * vol).tail(24).sum() / max(float(vol.tail(24).sum()), 1e-9))
    if not legacy and float(vol.tail(24).sum()) <= 0:
        vwap = float(typical.tail(24).mean())
    day_h = float(high.tail(24).max())
    day_l = float(low.tail(24).min())
    span = max(day_h - day_l, last * 0.0005)
    candle = analysis_engine.detect_candlestick_window(work.tail(5))
    orb = analysis_engine.detect_opening_range(work, analysis_engine.OPENING_RANGE_BARS)
    or_break = 0.0
    if orb.get("available") and orb.get("broken"):
        or_break = 1.0 if orb.get("bias") == "BULLISH" else -1.0
    vol_ma = float(vol.tail(20).mean()) or 1.0
    return {
        "ret_3": _ret(3),
        "ret_6": _ret(6),
        "ret_12": _ret(12),
        "rsi_14": _rsi(close, legacy=legacy),
        "vwap_dist": (last - vwap) / last * 100.0,
        "range_pos": (last - day_l) / span,
        "candle_score": float(candle.get("score_delta") or 0),
        "vol_ratio": float(vol.iloc[-1]) / vol_ma,
        "bar_range_pct": (float(high.iloc[-1]) - float(low.iloc[-1])) / last * 100.0,
        "or_break": or_break,
    }


def rule_p_up(feat: Dict[str, float]) -> float:
    raw = 50.0
    raw += max(-12, min(12, feat.get("ret_6", 0) * 8))
    raw += max(-8, min(8, (feat.get("rsi_14", 50) - 50) * 0.25))
    raw += max(-8, min(8, feat.get("vwap_dist", 0) * 4))
    raw += max(-8, min(8, (feat.get("range_pos", 0.5) - 0.5) * 16))
    raw += max(-8, min(8, feat.get("candle_score", 0) * 0.45))
    raw += feat.get("or_break", 0) * 6
    return max(0.05, min(0.95, raw / 100.0))


def _horizon_bars(interval: str) -> int:
    return HORIZON_BARS_5M if "5" in str(interval) and "15" not in str(interval) else HORIZON_BARS_15M


def _xy(df: pd.DataFrame, horizon_bars: int) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    work = _norm(df)
    if work is None or len(work) < 40:
        return None, None
    rows: List[List[float]] = []
    labels: List[int] = []
    close = work["Close"].astype(float)
    for i in range(20, len(work) - horizon_bars):
        feat = features_from_bars(work.iloc[: i + 1])
        if not feat:
            continue
        now = float(close.iloc[i])
        later = float(close.iloc[i + horizon_bars])
        if now <= 0:
            continue
        ret = (later - now) / now
        if ret >= MIN_MOVE:
            y = 1
        elif ret <= -MIN_MOVE:
            y = 0
        else:
            continue
        rows.append([float(feat[k]) for k in FEATURE_NAMES])
        labels.append(y)
    if len(rows) < 24:
        return None, None
    return np.asarray(rows, dtype=float), np.asarray(labels, dtype=int)


def train_session_head(df: Any, interval: str = "15minute") -> Dict[str, Any]:
    """Fit a small HGB on 15m (default) bars. Safe for replay / overnight — not per tick."""
    X, y = _xy(df if isinstance(df, pd.DataFrame) else _norm(df), _horizon_bars(interval))
    if X is None or HistGradientBoostingClassifier is None:
        return {"available": False, "reason": "not_enough_rows_or_sklearn"}
    model = HistGradientBoostingClassifier(
        max_depth=3, max_iter=40, learning_rate=0.08, random_state=7
    )
    model.fit(X, y)
    acc = float((model.predict(X) == y).mean())
    return {
        "available": True,
        "model": model,
        "feature_names": list(FEATURE_NAMES),
        "accuracy_in_sample": round(acc, 4),
        "n_rows": int(len(y)),
        "model_version": MODEL_VERSION,
        "interval": interval,
    }


def save_session_model(pack: Dict[str, Any], path: str) -> None:
    if joblib is None or not pack.get("available"):
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    joblib.dump({k: v for k, v in pack.items() if k != "model"} | {"model": pack["model"]}, path)


def load_session_model(path: str) -> Dict[str, Any]:
    if joblib is None or not os.path.isfile(path):
        return {"available": False}
    try:
        pack = joblib.load(path)
        pack["available"] = pack.get("model") is not None
        return pack
    except Exception:
        return {"available": False}


def infer(
    df: Any,
    model_pack: Optional[Dict[str, Any]] = None,
    interval: str = "15minute",
) -> Dict[str, Any]:
    """Always returns a rule P(up). Uses the 15m model when a pack is passed."""
    feat = features_from_bars(df)
    if not feat:
        return {"available": False, "p_up": 0.5, "source": "none"}
    p_rule = rule_p_up(feat)
    p_model = None
    if model_pack and model_pack.get("available") and model_pack.get("model") is not None:
        try:
            x = np.asarray([[float(feat[k]) for k in FEATURE_NAMES]], dtype=float)
            proba = model_pack["model"].predict_proba(x)[0]
            classes = list(model_pack["model"].classes_)
            p_model = float(proba[classes.index(1)]) if 1 in classes else p_rule
        except Exception:
            p_model = None
    p_up = p_model if p_model is not None else p_rule
    p_up = max(0.05, min(0.95, float(p_up)))
    tag = "15m" if "15" in str(interval) else "5m"
    source = f"hgb_{tag}" if p_model is not None else f"rule_{tag}"
    return {
        "available": True,
        "p_up": round(float(p_up), 4),
        "p_rule": round(p_rule, 4),
        "source": source,
        "interval": interval,
        "features": {k: round(float(feat[k]), 4) for k in FEATURE_NAMES},
        "model_version": MODEL_VERSION,
    }
