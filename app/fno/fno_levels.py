"""Level room, volatility/time fit and 60-minute trend for index F&O clips.

Everything here is computed from the 15-minute bars already in hand; nothing
fetches. The clip (stop / target in points) is fixed per index, so the useful
questions are practical ones:

* Is a known level (prior day high/low/close, floor pivots, session extremes,
  the opening range, round numbers) sitting in the path to the target?
* Is the stop inside one bar of normal 15m noise?
* Is there enough session left for the target to print?
* Does the 60-minute trend agree with the 15-minute break?
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

ROUND_STEP = {"NIFTY": 100.0, "FINNIFTY": 100.0, "BANKNIFTY": 500.0}
# A level this close to the entry is already being traded through — ignore it.
LEVEL_MIN_FRAC = 0.2
# A level inside this fraction of the entry->T1 path blocks the clip.
LEVEL_BLOCK_FRAC = 0.5
# Stop must be at least this many 15m true ranges away to sit outside noise.
NOISE_MAX_RATIO = 1.6
# Expected move to the close must cover this much of the target.
TIME_MIN_COVER = 0.9
SESSION_END_MINS = 15 * 60 + 30
HTF_FAST = 5
HTF_SLOW = 13


def _ist(ts: Any) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("Asia/Kolkata")
    return t


def _norm(df: Any) -> Optional[pd.DataFrame]:
    if df is None or len(df) == 0:
        return None
    out = df.copy()
    colmap = {str(c).lower(): c for c in out.columns}
    for src, dst in (("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close")):
        if dst not in out.columns and src in colmap:
            out[dst] = out[colmap[src]]
    if not {"Open", "High", "Low", "Close"} <= set(out.columns):
        return None
    return out.sort_index()


def _session_split(work: pd.DataFrame):
    days = [_ist(i).date() for i in work.index]
    today = days[-1]
    mask_today = np.array([d == today for d in days])
    mask_prev = np.array([d < today for d in days])
    sess = work.iloc[np.where(mask_today)[0]]
    prev = work.iloc[np.where(mask_prev)[0]]
    prev_sess = None
    if len(prev):
        pday = _ist(prev.index[-1]).date()
        pm = np.array([_ist(i).date() == pday for i in prev.index])
        prev_sess = prev.iloc[np.where(pm)[0]]
    return sess, prev_sess


def key_levels(bars_15m: Any, symbol: str = "NIFTY") -> Dict[str, Any]:
    """Named levels known at the last bar close."""
    work = _norm(bars_15m)
    if work is None or len(work) < 2:
        return {"available": False, "levels": {}}
    sess, prev_sess = _session_split(work)
    px = float(work["Close"].astype(float).iloc[-1])
    levels: Dict[str, float] = {}
    if prev_sess is not None and len(prev_sess):
        pdh = float(prev_sess["High"].astype(float).max())
        pdl = float(prev_sess["Low"].astype(float).min())
        pdc = float(prev_sess["Close"].astype(float).iloc[-1])
        pivot = (pdh + pdl + pdc) / 3.0
        levels.update(
            {
                "PDH": pdh,
                "PDL": pdl,
                "PDC": pdc,
                "Pivot": pivot,
                "R1": 2 * pivot - pdl,
                "S1": 2 * pivot - pdh,
                "R2": pivot + (pdh - pdl),
                "S2": pivot - (pdh - pdl),
            }
        )
    if len(sess):
        levels["OR_high"] = float(sess["High"].astype(float).iloc[0])
        levels["OR_low"] = float(sess["Low"].astype(float).iloc[0])
        levels["Day_open"] = float(sess["Open"].astype(float).iloc[0])
        # Session extremes set *before* the current bar. The bar that is
        # printing the break is not a level in its own way.
        earlier = sess.iloc[:-1]
        if len(earlier):
            levels["Day_high"] = float(earlier["High"].astype(float).max())
            levels["Day_low"] = float(earlier["Low"].astype(float).min())
    step = ROUND_STEP.get(str(symbol).upper(), 100.0)
    below = math.floor(px / step) * step
    levels["Round_below"] = below
    levels["Round_above"] = below + step
    return {"available": True, "price": round(px, 2), "levels": {k: round(v, 2) for k, v in levels.items()}}


def level_room(
    decision: str,
    price: Optional[float],
    stop_loss: Optional[float],
    target_1: Optional[float],
    levels: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Levels in the path to T1 (bad) and between entry and stop (protective)."""
    out: Dict[str, Any] = {"available": False, "blocking": [], "protecting": [], "warning": None, "bias": "NEUTRAL"}
    if decision in (None, "HOLD") or price is None or target_1 is None or stop_loss is None:
        return out
    lv = (levels or {}).get("levels") if isinstance(levels, dict) else None
    if not lv:
        return out
    try:
        px, t1, sl = float(price), float(target_1), float(stop_loss)
    except (TypeError, ValueError):
        return out
    bearish = "SELL" in str(decision)
    t1_dist = abs(t1 - px)
    sl_dist = abs(sl - px)
    if t1_dist <= 0:
        return out
    out["available"] = True
    nearest_block: Optional[Dict[str, Any]] = None
    for name, val in lv.items():
        if name in ("Day_high", "Day_low") and (
            (not bearish and val <= px) or (bearish and val >= px)
        ):
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        ahead = (v - px) if not bearish else (px - v)
        if ahead > 0:
            frac = ahead / t1_dist
            if LEVEL_MIN_FRAC <= frac <= LEVEL_BLOCK_FRAC:
                row = {"level": name, "value": round(v, 2), "path_frac": round(frac, 3)}
                out["blocking"].append(row)
                if nearest_block is None or frac < nearest_block["path_frac"]:
                    nearest_block = row
        else:
            behind = -ahead
            if sl_dist > 0 and 0 < behind < sl_dist:
                out["protecting"].append({"level": name, "value": round(v, 2), "stop_frac": round(behind / sl_dist, 3)})
    if nearest_block is not None:
        side = "SELL" if bearish else "BUY"
        # A level in the path leans against the call (a cutoff vote), it does not
        # veto it: as a veto it blocked 9 winners for 4 losers (Sep 21 - Oct 12).
        out["bias"] = "BULLISH" if bearish else "BEARISH"
        out["warning"] = (
            f"{nearest_block['level']} {nearest_block['value']} sits "
            f"{nearest_block['path_frac']:.0%} of the way to T1 — the {side} has to clear it first."
        )
    return out


def volatility_fit(
    bars_15m: Any,
    *,
    sl_pts: Optional[float],
    t1_pts: Optional[float],
    asof: Any = None,
) -> Dict[str, Any]:
    """Is the stop outside 15m noise, and is there time left for the target?"""
    out: Dict[str, Any] = {"available": False, "hold": None}
    work = _norm(bars_15m)
    if work is None or len(work) < 6 or not sl_pts or not t1_pts:
        return out
    h = work["High"].astype(float)
    l = work["Low"].astype(float)
    c = work["Close"].astype(float)
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1).dropna()
    atr = float(tr.tail(14).mean()) if len(tr) else 0.0
    if not np.isfinite(atr) or atr <= 0:
        return out
    ts = _ist(asof if asof is not None else work.index[-1])
    mins = ts.hour * 60 + ts.minute
    bars_left = max(0, int((SESSION_END_MINS - mins) // 15))
    expected_move = atr * math.sqrt(bars_left) if bars_left else 0.0
    noise_ratio = atr / float(sl_pts)
    cover = expected_move / float(t1_pts) if t1_pts else 0.0
    out.update(
        {
            "available": True,
            "atr_15m": round(atr, 2),
            "bars_left": bars_left,
            "expected_move_to_close": round(expected_move, 2),
            "noise_vs_stop": round(noise_ratio, 3),
            "target_cover": round(cover, 3),
        }
    )
    # Noise vs stop is a warning, not a hold: as a hold it blocked 13 winners for
    # 6 losers (Sep 21 - Oct 12). Time left is physical and stays a hold.
    out["warning"] = None
    if noise_ratio > NOISE_MAX_RATIO:
        out["warning"] = (
            f"15m range {atr:.0f} pts vs a {float(sl_pts):.0f}-pt stop ({noise_ratio:.1f}x) — "
            f"expect the stop to be tested."
        )
    if bars_left and cover < TIME_MIN_COVER:
        out["hold"] = (
            f"Only {bars_left} bars left; expected move {expected_move:.0f} pts does not cover "
            f"the {float(t1_pts):.0f}-pt target."
        )
    return out


def htf_bias(bars_15m: Any) -> Dict[str, Any]:
    """60-minute trend: EMA(5) vs EMA(13) on hourly closes plus the last hourly close
    versus the hourly EMA(5). BULLISH / BEARISH / NEUTRAL."""
    work = _norm(bars_15m)
    if work is None or len(work) < 4 * (HTF_SLOW + 2):
        return {"available": False, "bias": "NEUTRAL"}
    try:
        hourly = work["Close"].astype(float).resample("60min", label="right", closed="right").last().dropna()
    except Exception:
        return {"available": False, "bias": "NEUTRAL"}
    if len(hourly) < HTF_SLOW + 2:
        return {"available": False, "bias": "NEUTRAL"}
    fast = hourly.ewm(span=HTF_FAST, adjust=False).mean()
    slow = hourly.ewm(span=HTF_SLOW, adjust=False).mean()
    f, s, last = float(fast.iloc[-1]), float(slow.iloc[-1]), float(hourly.iloc[-1])
    slope = float(fast.iloc[-1] - fast.iloc[-3]) if len(fast) >= 3 else 0.0
    if f > s and last >= f and slope > 0:
        bias = "BULLISH"
    elif f < s and last <= f and slope < 0:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"
    return {
        "available": True,
        "bias": bias,
        "ema_fast": round(f, 2),
        "ema_slow": round(s, 2),
        "last_60m_close": round(last, 2),
        "fast_slope": round(slope, 2),
    }


def vix_bias(vix: Optional[Dict[str, Any]]) -> str:
    """Rising fear leans SELL, falling fear leans BUY. Uses the day change if present."""
    if not isinstance(vix, dict):
        return "NEUTRAL"
    try:
        chg = float(vix.get("change_pct")) if vix.get("change_pct") is not None else None
    except (TypeError, ValueError):
        chg = None
    if chg is None:
        return "NEUTRAL"
    if chg >= 5.0:
        return "BEARISH"
    if chg <= -5.0:
        return "BULLISH"
    return "NEUTRAL"


def summary_lines(levels: Dict[str, Any], room: Dict[str, Any], vol: Dict[str, Any], htf: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    if htf.get("available"):
        lines.append(f"60m trend {htf['bias']} (EMA5 {htf['ema_fast']} vs EMA13 {htf['ema_slow']}).")
    if vol.get("available"):
        lines.append(
            f"15m ATR {vol['atr_15m']} pts · {vol['bars_left']} bars left · "
            f"expected move {vol['expected_move_to_close']} pts."
        )
    if vol.get("available") and vol.get("warning"):
        lines.append(str(vol["warning"]))
    if room.get("available") and room.get("warning"):
        lines.append(str(room["warning"]))
    if room.get("available") and room.get("protecting"):
        p = room["protecting"][0]
        lines.append(f"{p['level']} {p['value']} sits between entry and stop.")
    return lines


INFO_PREFIXES = ("60m trend ", "15m ATR ", "15m range ")


def is_info_line(text: str) -> bool:
    """Informational lines this module appends to the reasons list."""
    t = str(text)
    return t.startswith(INFO_PREFIXES) or "sits between entry and stop" in t or "of the way to T1" in t
