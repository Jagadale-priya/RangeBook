"""Market regime features (Nifty trend, India VIX) aligned to daily feature index."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore

NIFTY = "^NSEI"
VIX = "^INDIAVIX"
CACHE_DAYS = 400


def _cache_path(ticker: str) -> str:
    root = os.environ.get("STOCK_SIGNAL_DATA_DIR", "").strip()
    if not root:
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_signal_data")
    os.makedirs(os.path.join(root, "cache"), exist_ok=True)
    safe = ticker.replace("^", "IDX_").replace(".", "_")
    return os.path.join(root, "cache", f"regime_{safe}.csv")


def _load_series(ticker: str, force_refresh: bool = False) -> Optional[pd.Series]:
    path = _cache_path(ticker)
    if not force_refresh and os.path.isfile(path):
        age_h = (datetime.now().timestamp() - os.path.getmtime(path)) / 3600
        if age_h < 12:
            try:
                df = pd.read_csv(path, index_col=0, parse_dates=True)
                if "Close" in df.columns and len(df) > 50:
                    return df["Close"].sort_index()
            except (OSError, ValueError, KeyError):
                pass
    if yf is None:
        return None
    try:
        end = datetime.now()
        start = end - timedelta(days=CACHE_DAYS)
        hist = yf.Ticker(ticker).history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=False,
        )
        if hist is None or len(hist) < 30:
            return None
        hist.index = pd.to_datetime(hist.index).tz_localize(None)
        hist[["Close"]].to_csv(path)
        return hist["Close"].sort_index()
    except Exception:
        return None


def attach_regime_features(feat: pd.DataFrame, *, force_refresh: bool = False) -> pd.DataFrame:
    """Add regime_nifty_ret_1d, regime_nifty_ret_5d, regime_vix_level, regime_vix_chg_1d."""
    if feat is None or len(feat) == 0:
        return feat
    out = feat.copy()
    idx = pd.to_datetime(feat.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    dates = idx.normalize()

    nifty = _load_series(NIFTY, force_refresh=force_refresh)
    vix = _load_series(VIX, force_refresh=force_refresh)

    n1 = n5 = vlev = vchg = pd.Series(index=feat.index, dtype=float)
    if nifty is not None and len(nifty) > 10:
        nr1 = nifty.pct_change(1) * 100
        nr5 = nifty.pct_change(5) * 100
        n1 = dates.map(lambda d: nr1.get(d, float("nan")))
        n5 = dates.map(lambda d: nr5.get(d, float("nan")))
    if vix is not None and len(vix) > 10:
        vc = vix.pct_change(1) * 100
        vlev = dates.map(lambda d: vix.get(d, float("nan")))
        vchg = dates.map(lambda d: vc.get(d, float("nan")))

    out["regime_nifty_ret_1d"] = pd.Series(n1.values, index=feat.index)
    out["regime_nifty_ret_5d"] = pd.Series(n5.values, index=feat.index)
    out["regime_vix_level"] = pd.Series(vlev.values, index=feat.index)
    out["regime_vix_chg_1d"] = pd.Series(vchg.values, index=feat.index)
    # Missing macro dates (backtest / long history): neutral regime, not row-dropping NaN.
    out["regime_nifty_ret_1d"] = out["regime_nifty_ret_1d"].fillna(0.0)
    out["regime_nifty_ret_5d"] = out["regime_nifty_ret_5d"].fillna(0.0)
    out["regime_vix_chg_1d"] = out["regime_vix_chg_1d"].fillna(0.0)
    vix_default = 15.0
    if vix is not None and len(vix) > 10:
        med = float(vix.median())
        if med == med:  # not NaN
            vix_default = med
    out["regime_vix_level"] = out["regime_vix_level"].fillna(vix_default)
    return out


def regime_status() -> Dict[str, Any]:
    n = _load_series(NIFTY)
    v = _load_series(VIX)
    return {
        "nifty_bars": int(len(n)) if n is not None else 0,
        "vix_bars": int(len(v)) if v is not None else 0,
        "cache_nifty": _cache_path(NIFTY),
        "cache_vix": _cache_path(VIX),
    }
