"""Causal 15m structure for the F&O clip model.

Every value uses only bars up to the last row. No option-chain series is invented:
OI velocity, PCR variance, and GEX stay in the derivative slots and are 0 when
the chain snapshot is missing.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

FIB_LEVELS = (0.236, 0.382, 0.5, 0.618, 0.786, 1.272, 1.618)
STRUCTURE_NAMES = (
    "body_ratio",
    "pat_doji",
    "pat_hammer",
    "pat_engulf",
    "pat_star",
    "slope_3",
    "fib_pos",
    "fib_near",
    "pivot_pos",
    "pivot_near",
    "bb_pctb",
    "bb_width",
    "atr_ratio",
    "donch_pos",
    "donch_break",
    "vwap_z",
)


def empty_structure() -> Dict[str, float]:
    out = {name: 0.0 for name in STRUCTURE_NAMES}
    out["bb_pctb"] = 0.5
    out["atr_ratio"] = 1.0
    out["donch_pos"] = 0.5
    return out


def _clip(val: float, lo: float, hi: float) -> float:
    if not np.isfinite(val):
        return 0.0
    return float(max(lo, min(hi, val)))


def _ohlc(row) -> tuple:
    return float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])


def structure_features(work: pd.DataFrame) -> Dict[str, float]:
    out = empty_structure()
    if work is None or len(work) < 3:
        return out
    try:
        return _compute(work)
    except Exception:
        return empty_structure()


def _compute(work: pd.DataFrame) -> Dict[str, float]:
    out = empty_structure()
    h = work["High"].astype(float)
    l = work["Low"].astype(float)
    c = work["Close"].astype(float)
    o = work["Open"].astype(float)
    px = float(c.iloc[-1])
    if px <= 0:
        return out
    out.update(_candles(o, h, l, c, px))
    out.update(_fib(h, l, px))
    out.update(_pivots(work, px))
    out.update(_bollinger(c, px))
    out["atr_ratio"] = _atr_ratio(h, l, c)
    out.update(_donchian(h, l, px))
    out["vwap_z"] = _vwap_z(work, px)
    return out


def _candles(o: pd.Series, h: pd.Series, l: pd.Series, c: pd.Series, px: float) -> Dict[str, float]:
    oo, hh, ll, cc = float(o.iloc[-1]), float(h.iloc[-1]), float(l.iloc[-1]), float(c.iloc[-1])
    rng = max(hh - ll, 1e-9)
    body = abs(cc - oo)
    lower = min(oo, cc) - ll
    upper = hh - max(oo, cc)
    out = {
        "body_ratio": _clip(body / rng, 0.0, 1.0),
        "pat_doji": 1.0 if body / rng < 0.12 else 0.0,
        "pat_hammer": 0.0,
        "pat_engulf": 0.0,
        "pat_star": 0.0,
        "slope_3": 0.0,
    }
    if lower > 2.0 * max(body, rng * 0.02) and upper < body:
        out["pat_hammer"] = 1.0 if cc >= oo else 0.0
    elif upper > 2.0 * max(body, rng * 0.02) and lower < body:
        out["pat_hammer"] = -1.0 if cc <= oo else 0.0
    po, _, _, pc = float(o.iloc[-2]), float(h.iloc[-2]), float(l.iloc[-2]), float(c.iloc[-2])
    if cc > oo and pc < po and cc >= po and oo <= pc:
        out["pat_engulf"] = 1.0
    elif cc < oo and pc > po and cc <= po and oo >= pc:
        out["pat_engulf"] = -1.0
    if len(c) >= 3:
        ao, _, _, ac = float(o.iloc[-3]), float(h.iloc[-3]), float(l.iloc[-3]), float(c.iloc[-3])
        bo, bh, bl, bc = float(o.iloc[-2]), float(h.iloc[-2]), float(l.iloc[-2]), float(c.iloc[-2])
        mid_body = abs(bc - bo) / max(bh - bl, 1e-9)
        a_dn, a_up = ac < ao, ac > ao
        d_up, d_dn = cc > oo, cc < oo
        if a_dn and mid_body < 0.35 and d_up and cc > (ao + ac) / 2.0:
            out["pat_star"] = 1.0
        elif a_up and mid_body < 0.35 and d_dn and cc < (ao + ac) / 2.0:
            out["pat_star"] = -1.0
        ys = c.iloc[-3:].to_numpy(dtype=float)
        slope = float(np.polyfit(np.array([0.0, 1.0, 2.0]), ys, 1)[0])
        out["slope_3"] = _clip(slope / px * 100.0, -1.0, 1.0)
    return out


def _fib(h: pd.Series, l: pd.Series, px: float) -> Dict[str, float]:
    tail_h = h.tail(26)
    tail_l = l.tail(26)
    swing_hi = float(tail_h.max())
    swing_lo = float(tail_l.min())
    span = swing_hi - swing_lo
    if span <= 0:
        return {"fib_pos": 0.0, "fib_near": 0.0}
    pos = (px - swing_lo) / span
    near = min(abs(pos - level) for level in FIB_LEVELS)
    return {"fib_pos": _clip(pos, -0.2, 1.8), "fib_near": 1.0 if near <= 0.08 else 0.0}


def _pivots(work: pd.DataFrame, px: float) -> Dict[str, float]:
    last = pd.Timestamp(work.index[-1])
    if last.tzinfo is not None:
        last = last.tz_convert("Asia/Kolkata")
    day = last.date()
    dates = []
    for ts in work.index:
        dt = pd.Timestamp(ts)
        if dt.tzinfo is not None:
            dt = dt.tz_convert("Asia/Kolkata")
        dates.append(dt.date())
    prev_days = sorted({d for d in dates if d < day})
    if not prev_days:
        return {"pivot_pos": 0.0, "pivot_near": 0.0}
    prev = work[[d == prev_days[-1] for d in dates]]
    if len(prev) < 1:
        return {"pivot_pos": 0.0, "pivot_near": 0.0}
    hi = float(prev["High"].astype(float).max())
    lo = float(prev["Low"].astype(float).min())
    close = float(prev["Close"].astype(float).iloc[-1])
    span = max(hi - lo, 1.0)
    pivot = (hi + lo + close) / 3.0
    levels = (
        pivot,
        2.0 * pivot - lo,
        pivot + (hi - lo),
        hi + 2.0 * (pivot - lo),
        2.0 * pivot - hi,
        pivot - (hi - lo),
        lo - 2.0 * (hi - pivot),
    )
    near = min(abs(px - level) / span for level in levels)
    return {
        "pivot_pos": _clip((px - pivot) / span, -3.0, 3.0),
        "pivot_near": 1.0 if near <= 0.12 else 0.0,
    }


def _bollinger(c: pd.Series, px: float) -> Dict[str, float]:
    tail = c.tail(20)
    if len(tail) < 8:
        return {"bb_pctb": 0.5, "bb_width": 0.0}
    mid = float(tail.mean())
    std = float(tail.std(ddof=0) or 0.0)
    if mid <= 0 or std <= 0:
        return {"bb_pctb": 0.5, "bb_width": 0.0}
    upper = mid + 2.0 * std
    lower = mid - 2.0 * std
    width = (upper - lower) / mid
    pctb = (px - lower) / (upper - lower) if upper > lower else 0.5
    return {"bb_pctb": _clip(pctb, -0.5, 1.5), "bb_width": _clip(width, 0.0, 0.2)}


def _atr_ratio(h: pd.Series, l: pd.Series, c: pd.Series) -> float:
    prev = c.shift()
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    atr14 = tr.ewm(alpha=1.0 / 14.0, adjust=False).mean()
    last = float(atr14.iloc[-1] or 0.0)
    if len(tr) >= 100:
        base = float(tr.ewm(alpha=1.0 / 100.0, adjust=False).mean().iloc[-1] or 0.0)
    else:
        base = float(atr14.tail(min(len(atr14), 40)).median() or 0.0)
    if base <= 0 or not np.isfinite(last):
        return 1.0
    return _clip(last / base, 0.2, 4.0)


def _donchian(h: pd.Series, l: pd.Series, px: float) -> Dict[str, float]:
    if len(h) < 21:
        return {"donch_pos": 0.5, "donch_break": 0.0}
    prior_h = float(h.iloc[-21:-1].max())
    prior_l = float(l.iloc[-21:-1].min())
    span = prior_h - prior_l
    if span <= 0:
        return {"donch_pos": 0.5, "donch_break": 0.0}
    if px > prior_h:
        brk = 1.0
    elif px < prior_l:
        brk = -1.0
    else:
        brk = 0.0
    return {"donch_pos": _clip((px - prior_l) / span, -0.25, 1.25), "donch_break": brk}


def _vwap_z(work: pd.DataFrame, px: float) -> float:
    last = pd.Timestamp(work.index[-1])
    if last.tzinfo is not None:
        last = last.tz_convert("Asia/Kolkata")
    day = last.date()
    mask = []
    for ts in work.index:
        dt = pd.Timestamp(ts)
        if dt.tzinfo is not None:
            dt = dt.tz_convert("Asia/Kolkata")
        mask.append(dt.date() == day)
    sess = work[mask]
    if len(sess) < 4:
        sess = work.tail(min(len(work), 20))
    h = sess["High"].astype(float)
    l = sess["Low"].astype(float)
    c = sess["Close"].astype(float)
    typical = (h + l + c) / 3.0
    vol = sess["Volume"].astype(float) if "Volume" in sess.columns else pd.Series(0.0, index=sess.index)
    if float(vol.sum()) > 1.0:
        vwap = float((typical * vol).sum() / float(vol.sum()))
    else:
        vwap = float(typical.mean())
    dev = (typical - vwap).astype(float)
    std = float(dev.std(ddof=0) or 0.0)
    if std <= 0:
        return 0.0
    return _clip((px - vwap) / std, -4.0, 4.0)
