"""HL/LH swing bounce + midday + VWAP + EMA stack (15m desk signal).

Research (last 3y, T1-before-SL decided, h=4–6):
  NIFTY / SENSEX ~60–62%  → chart + suggest-only
  BANKNIFTY ~59%          → chart markers only (below 60% gate)

Never lists Calls (listable=False).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

DESK_LEVELS = {
    "NIFTY": {"t1": 30.0, "sl": 25.0},
    "BANKNIFTY": {"t1": 75.0, "sl": 60.0},
    "SENSEX": {"t1": 100.0, "sl": 80.0},
}
# Suggestions only where research cleared ~60%+
SUGGEST_SYMBOLS = frozenset({"NIFTY", "SENSEX"})
HIT_NOTE = {
    "NIFTY": "~60–62% T1-before-SL (research, midday HL/LH stack)",
    "SENSEX": "~60–62% T1-before-SL (research, midday HL/LH stack)",
    "BANKNIFTY": "~59% research — chart only, below 60% gate",
}


def _norm(bars: Any) -> Optional[pd.DataFrame]:
    if bars is None:
        return None
    try:
        if hasattr(bars, "empty") and bars.empty:
            return None
        work = bars.copy()
        rename = {}
        for c in work.columns:
            cl = str(c).strip().lower()
            if cl in ("open", "o"):
                rename[c] = "Open"
            elif cl in ("high", "h"):
                rename[c] = "High"
            elif cl in ("low", "l"):
                rename[c] = "Low"
            elif cl in ("close", "c"):
                rename[c] = "Close"
            elif cl in ("volume", "vol", "v"):
                rename[c] = "Volume"
        if rename:
            work = work.rename(columns=rename)
        need = {"Open", "High", "Low", "Close"}
        if not need.issubset(set(work.columns)):
            return None
        for col in need:
            work[col] = pd.to_numeric(work[col], errors="coerce")
        work = work.dropna(subset=list(need))
        if not isinstance(work.index, pd.DatetimeIndex):
            work.index = pd.to_datetime(work.index)
        if work.index.tz is None:
            work.index = work.index.tz_localize("Asia/Kolkata")
        else:
            work.index = work.index.tz_convert("Asia/Kolkata")
        return work if len(work) >= 40 else None
    except Exception:
        return None


def _ema(series: pd.Series, span: int) -> np.ndarray:
    return series.astype(float).ewm(span=span, adjust=False).mean().to_numpy()


def _atr(df: pd.DataFrame, n: int = 14) -> np.ndarray:
    h, l, c = df["High"].astype(float), df["Low"].astype(float), df["Close"].astype(float)
    prev = c.shift(1)
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean().to_numpy()


def _session_vwap(df: pd.DataFrame) -> np.ndarray:
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)
    vol = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(0.0, index=df.index)
    day = pd.Series(df.index.tz_convert("Asia/Kolkata").date, index=df.index)
    tp = (high + low + close) / 3.0
    out = np.full(len(df), np.nan)
    for _, locs in day.groupby(day).groups.items():
        tps = tp.loc[locs].to_numpy()
        vs = vol.loc[locs].to_numpy()
        if float(np.nansum(vs)) > 0:
            pv = np.cumsum(tps * vs)
            cv = np.cumsum(np.where(vs > 0, vs, 0.0))
            vals = np.divide(pv, cv, out=np.full_like(pv, np.nan), where=cv > 0)
            expand = np.cumsum(tps) / (np.arange(len(tps)) + 1.0)
            vals = np.where(np.isfinite(vals), vals, expand)
        else:
            vals = np.cumsum(tps) / (np.arange(len(tps)) + 1.0)
        out[df.index.get_indexer(locs)] = vals
    return out


def _swings(high: np.ndarray, low: np.ndarray, depth: int = 3):
    highs, lows = [], []
    n = len(high)
    for i in range(depth, n - depth):
        if high[i] >= float(np.max(high[i - depth : i + depth + 1])):
            highs.append((i, float(high[i])))
        if low[i] <= float(np.min(low[i - depth : i + depth + 1])):
            lows.append((i, float(low[i])))
    return highs, lows


def _swing_levels(high: np.ndarray, low: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    sh, slp = _swings(high, low, 3)
    n = len(high)
    last_hi = np.full(n, np.nan)
    last_lo = np.full(n, np.nan)
    prev_hi = np.full(n, np.nan)
    prev_lo = np.full(n, np.nan)
    hi_i = lo_i = 0
    for i in range(n):
        while hi_i < len(sh) and sh[hi_i][0] <= i:
            prev_hi[i] = last_hi[i - 1] if i else np.nan
            last_hi[i] = sh[hi_i][1]
            hi_i += 1
        if i and not np.isfinite(last_hi[i]):
            last_hi[i] = last_hi[i - 1]
            prev_hi[i] = prev_hi[i - 1]
        while lo_i < len(slp) and slp[lo_i][0] <= i:
            prev_lo[i] = last_lo[i - 1] if i else np.nan
            last_lo[i] = slp[lo_i][1]
            lo_i += 1
        if i and not np.isfinite(last_lo[i]):
            last_lo[i] = last_lo[i - 1]
            prev_lo[i] = prev_lo[i - 1]
    return last_hi, last_lo, prev_hi, prev_lo


def detect_signals(bars: Any) -> List[Dict[str, Any]]:
    """Return causal HL/LH midday-stack hits (one dict per bar index that fires)."""
    df = _norm(bars)
    if df is None:
        return []
    o = df["Open"].astype(float).to_numpy()
    h = df["High"].astype(float).to_numpy()
    l = df["Low"].astype(float).to_numpy()
    c = df["Close"].astype(float).to_numpy()
    vwap = _session_vwap(df)
    e9 = _ema(df["Close"], 9)
    e20 = _ema(df["Close"], 20)
    atr = _atr(df)
    last_hi, last_lo, prev_hi, prev_lo = _swing_levels(h, l)
    tol = np.maximum(atr * 0.15, 1.0)
    minutes = np.array([ts.hour * 60 + ts.minute for ts in df.index.tz_convert("Asia/Kolkata")])
    midday = (minutes >= (10 * 60 + 15)) & (minutes <= (14 * 60 + 30))
    days = pd.Series(df.index.tz_convert("Asia/Kolkata").date, index=df.index)
    first = (days != days.shift(1)).to_numpy()

    bull = c > o
    bear = c < o
    swing_up = np.isfinite(last_lo) & (l <= last_lo + tol) & (c > last_lo) & bull
    swing_dn = np.isfinite(last_hi) & (h >= last_hi - tol) & (c < last_hi) & bear
    hl_up = swing_up & np.isfinite(prev_lo) & (last_lo > prev_lo)
    lh_dn = swing_dn & np.isfinite(prev_hi) & (last_hi < prev_hi)
    buy = hl_up & (c > vwap) & (e9 > e20) & midday & (~first) & np.isfinite(vwap) & np.isfinite(e20)
    sell = lh_dn & (c < vwap) & (e9 < e20) & midday & (~first) & np.isfinite(vwap) & np.isfinite(e20)

    out: List[Dict[str, Any]] = []
    for i in np.flatnonzero(buy | sell):
        side = "BUY" if buy[i] else "SELL"
        code = "HL" if side == "BUY" else "LH"
        ts = df.index[i]
        out.append(
            {
                "i": int(i),
                "time": int(pd.Timestamp(ts).timestamp()),
                "iso": str(ts),
                "decision": side,
                "code": code,
                "price": round(float(c[i]), 2),
                "vwap": round(float(vwap[i]), 2) if np.isfinite(vwap[i]) else None,
                "ema9": round(float(e9[i]), 2) if np.isfinite(e9[i]) else None,
                "ema20": round(float(e20[i]), 2) if np.isfinite(e20[i]) else None,
                "swing": round(float(last_lo[i] if side == "BUY" else last_hi[i]), 2),
                "name": "HL bounce stack" if side == "BUY" else "LH bounce stack",
                "hint": (
                    "Higher-low bounce + midday + above VWAP + EMA9>EMA20"
                    if side == "BUY"
                    else "Lower-high bounce + midday + below VWAP + EMA9<EMA20"
                ),
                "color": "#0d9e6c" if side == "BUY" else "#dc2c42",
                "marker_time": int(pd.Timestamp(ts).timestamp()),
                "family": "hl_lh_stack",
            }
        )
    return out


def chart_patterns(bars: Any, *, max_keep: int = 12) -> List[Dict[str, Any]]:
    """Shape hits for 15m chart markers (same schema family as W/M patterns)."""
    hits = detect_signals(bars)
    if not hits:
        return []
    # keep most recent
    tail = hits[-max_keep:]
    return [
        {
            "code": h["code"],
            "name": h["name"],
            "role": "bullish" if h["decision"] == "BUY" else "bearish",
            "hint": h["hint"],
            "marker_time": h["marker_time"],
            "color": h["color"],
            "family": "hl_lh_stack",
            "decision": h["decision"],
            "price": h["price"],
            "points": [{"time": h["time"], "price": h["price"], "label": h["code"]}],
        }
        for h in tail
    ]


def latest_signal(bars: Any, *, asof: Any = None) -> Optional[Dict[str, Any]]:
    df = _norm(bars)
    if df is None:
        return None
    work = df
    if asof is not None:
        try:
            ts = pd.Timestamp(asof)
            if ts.tzinfo is None:
                ts = ts.tz_localize("Asia/Kolkata")
            else:
                ts = ts.tz_convert("Asia/Kolkata")
            work = df.loc[df.index <= ts]
        except Exception:
            work = df
    hits = detect_signals(work)
    return hits[-1] if hits else None


def maybe_suggestion(
    symbol: str,
    bars: Any,
    *,
    price: Any = None,
    asof: Any = None,
) -> Optional[Dict[str, Any]]:
    """Suggest-only ticket for NIFTY/SENSEX when latest bar fires. Never listable."""
    key = str(symbol or "").upper()
    if key not in SUGGEST_SYMBOLS:
        return None
    hit = latest_signal(bars, asof=asof)
    if not hit:
        return None
    # Only fire if signal is on the last 1–2 bars of the provided tape (fresh)
    try:
        idx = getattr(bars, "index", None)
        if idx is None or len(idx) < 1:
            return None
        last_ts = int(pd.Timestamp(idx[-1]).timestamp())
        prev_ts = int(pd.Timestamp(idx[-2]).timestamp()) if len(idx) >= 2 else last_ts
        if int(hit.get("time") or 0) not in (last_ts, prev_ts):
            return None
    except Exception:
        return None

    lv = DESK_LEVELS.get(key) or {"t1": 30.0, "sl": 25.0}
    entry = float(price) if price is not None and float(price) > 0 else float(hit["price"])
    side = hit["decision"]
    if side == "BUY":
        sl = round(entry - lv["sl"], 2)
        t1 = round(entry + lv["t1"], 2)
    else:
        sl = round(entry + lv["sl"], 2)
        t1 = round(entry - lv["t1"], 2)
    return {
        "kind": "suggestion",
        "decision": side,
        "entry": round(entry, 2),
        "stop_loss": sl,
        "target_1": t1,
        "target_2": None,
        "listable": False,
        "suggestion_only": True,
        "hl_lh_stack": True,
        "dual_track": False,
        "live_confluence": False,
        "track": "hl_lh_stack",
        "source": "hl_lh_mid_stack",
        "suggestion_tag": "HL/LH stack · suggest only",
        "tag_tone": "neutral",
        "basis": (
            f"{hit['hint']}. {HIT_NOTE.get(key, '')}. "
            "Suggest only — not auto Calls; your risk."
        ),
        "accuracy_label": HIT_NOTE.get(key, "Research stack"),
        "message": f"HL/LH midday stack suggests {side}",
        "bars_asof": hit.get("iso"),
        "need": hit.get("code"),
        "meta": {
            "code": hit.get("code"),
            "vwap": hit.get("vwap"),
            "ema9": hit.get("ema9"),
            "ema20": hit.get("ema20"),
            "swing": hit.get("swing"),
        },
    }


def apply_if_idle(
    result: Dict[str, Any],
    *,
    symbol: str,
    bars: Any,
    price: Any = None,
    asof: Any = None,
) -> Optional[Dict[str, Any]]:
    """Attach HL/LH suggestion when no model / live-confluence suggestion already won."""
    prior = result.get("suggestion") if isinstance(result, dict) else None
    if isinstance(prior, dict) and prior.get("decision") in ("BUY", "SELL"):
        if prior.get("dual_track") or prior.get("live_confluence"):
            return None
        if prior.get("hl_lh_stack") and prior.get("listable") is False:
            return prior

    sug = maybe_suggestion(symbol, bars, price=price, asof=asof)
    if not sug:
        return None
    result["suggestion"] = sug
    fa = dict(result.get("fno_analysis") or {})
    fa["suggestion"] = sug
    fa["hl_lh_stack"] = sug
    notes = list(fa.get("desk_alerts") or [])
    msg = f"HL/LH stack suggests {sug['decision']} (suggest only — not listed on Calls)."
    if msg not in notes:
        notes.insert(0, msg)
    fa["desk_alerts"] = notes
    result["fno_analysis"] = fa
    return sug
