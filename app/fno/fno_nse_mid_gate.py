"""Frozen Nov NSE mid-tercile gate for stacked PROD calls.

Prior-day AbsChangePct (and optional cols) must sit in the Nov frozen
mid band [p33, p67). Research: lifts PROD hit on 6m/1y/2y/5y with ~30% keep.

Flag: ENABLE_NSE_MID_GATE=1
Cols:  NSE_MID_GATE_COLS=AbsChangePct  (comma-separated AND)
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

import path_setup
ROOT = path_setup.ROOT
DAILY_FULL = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_daily_nse.csv"
DAILY_5Y = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_daily_5y_nse.csv"

# Frozen Nov 2026 mid terciles (from nifty_nse_mid_gate_6m.json)
FROZEN_CUTS: Dict[str, Tuple[float, float]] = {
    "ChangePct": (0.6276, 1.6866),
    "PointsChange": (149.082, 389.821),
    "AbsChangePct": (0.6276, 1.6866),
    "Vol_vs_20": (1.1308379416199754, 1.2087377304759954),
}

DEFAULT_COLS = ("AbsChangePct",)

_DAILY_CACHE: Optional[pd.DataFrame] = None
_DAILY_MTIME: Optional[float] = None
_DAILY_PATH: Optional[Path] = None


def _truthy(name: str, default: str = "0") -> bool:
    v = str(os.environ.get(name, default)).strip().lower()
    return v not in ("0", "false", "no", "off", "")


def enabled() -> bool:
    try:
        import fno_live_config

        return bool(fno_live_config.enable_nse_mid_gate())
    except Exception:
        return _truthy("ENABLE_NSE_MID_GATE", "0")


def gate_cols() -> List[str]:
    raw = str(os.environ.get("NSE_MID_GATE_COLS", "") or "").strip()
    if not raw:
        return list(DEFAULT_COLS)
    cols = [c.strip() for c in raw.split(",") if c.strip()]
    return [c for c in cols if c in FROZEN_CUTS] or list(DEFAULT_COLS)


def _as_day(asof: Any) -> str:
    if asof is None:
        return datetime.now().strftime("%Y-%m-%d")
    if hasattr(asof, "strftime"):
        return asof.strftime("%Y-%m-%d")
    return str(asof)[:10]


def _load_daily() -> Optional[pd.DataFrame]:
    global _DAILY_CACHE, _DAILY_MTIME, _DAILY_PATH
    path = DAILY_FULL if DAILY_FULL.exists() else DAILY_5Y
    if not path.exists():
        return None
    try:
        mtime = path.stat().st_mtime
        if (
            _DAILY_CACHE is not None
            and _DAILY_MTIME == mtime
            and _DAILY_PATH == path
        ):
            return _DAILY_CACHE
        df = pd.read_csv(path)
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
        df = df.sort_values("Date").reset_index(drop=True)
        df["AbsChangePct"] = df["ChangePct"].astype(float).abs()
        df["Vol_vs_20"] = (
            df["Volume"].astype(float)
            / df["Volume"].astype(float).rolling(20, min_periods=5).median()
        )
        for c in FROZEN_CUTS:
            df[f"prior_{c}"] = df[c].shift(1)
        _DAILY_CACHE = df
        _DAILY_MTIME = mtime
        _DAILY_PATH = path
        return df
    except Exception:
        return None


def prior_features(asof: Any = None) -> Dict[str, Any]:
    """Prior-session NSE features for the session day."""
    day = _as_day(asof)
    daily = _load_daily()
    if daily is None or daily.empty:
        return {"day": day, "ok": False, "reason": "daily_missing"}
    row = daily[daily["Date"] == day]
    if row.empty:
        # use last completed prior relative to day
        prior = daily[daily["Date"] < day]
        if prior.empty:
            return {"day": day, "ok": False, "reason": "no_prior"}
        r = prior.iloc[-1]
        src_day = str(r["Date"])
    else:
        r = row.iloc[0]
        src_day = day
    feats = {c: r.get(f"prior_{c}") for c in FROZEN_CUTS}
    return {
        "day": day,
        "feature_day": src_day,
        "ok": True,
        "features": feats,
        "source": str(_DAILY_PATH) if _DAILY_PATH else None,
    }


def passes(asof: Any = None, *, cols: Optional[List[str]] = None) -> Dict[str, Any]:
    """Return allow/reason for frozen Nov mid gate (AND across cols).

    Fail-open if daily tape missing so desk is not silently killed.
    """
    use_cols = cols or gate_cols()
    info = prior_features(asof)
    out: Dict[str, Any] = {
        "allow": True,
        "reason": "off",
        "cols": use_cols,
        "cuts": {c: list(FROZEN_CUTS[c]) for c in use_cols},
        "values": {},
    }
    if not enabled():
        return out
    if not info.get("ok"):
        out["reason"] = f"fail_open_{info.get('reason')}"
        out["allow"] = True
        return out
    feats = info.get("features") or {}
    values = {}
    for c in use_cols:
        p33, p67 = FROZEN_CUTS[c]
        v = feats.get(c)
        values[c] = None if v is None or (isinstance(v, float) and pd.isna(v)) else float(v)
        if values[c] is None or not (p33 <= values[c] < p67):
            out["allow"] = False
            out["reason"] = f"nse_mid_fail_{c}"
            out["values"] = values
            out["feature_day"] = info.get("feature_day")
            return out
    out["allow"] = True
    out["reason"] = "nse_mid_ok"
    out["values"] = values
    out["feature_day"] = info.get("feature_day")
    return out
