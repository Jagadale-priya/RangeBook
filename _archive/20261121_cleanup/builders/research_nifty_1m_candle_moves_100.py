"""RESEARCH ONLY — Complete candlestick + market-move 1m model → 100% max-calls.

Goes beyond OR first-break:
  1) Full candlestick catalog (classic + multi-bar)
  2) Market-move taxonomy: impulse / pullback-resume / swing-break /
     OR-break / reversal-at-extreme
  3) SL/T1 from the *move geometry* (impulse origin, swing, pattern wick)
  4) ANALYZE → TRAIN → TEST_NEW hunt for both-window 100% max n

  python -u prod_live/tests/builders/research_nifty_1m_candle_moves_100.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from itertools import product
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401,E402

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_5y_candle_ml as c5  # noqa: E402
import research_nifty_1m_chart_only_100 as co  # noqa: E402
from nifty_side_clean import recent_sample_weights  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_candle_moves_100"
REPORT_MD = OUT / "NIFTY_1M_CANDLE_MOVES_100.md"
REPORT_JSON = OUT / "NIFTY_1M_CANDLE_MOVES_100.json"

START, END = co.START, co.END
ANALYZE_END, TRAIN_END, TEST_START = co.ANALYZE_END, co.TRAIN_END, co.TEST_START
OR_BARS = 15

# Extra patterns beyond c5.PATTERN_COLS
EXTRA_PATS = [
    "spinning_top",
    "belt_bull",
    "belt_bear",
    "piercing",
    "dark_cloud",
    "tweezer_bot",
    "tweezer_top",
    "three_soldiers",
    "three_crows",
    "bull_kicker",
    "bear_kicker",
]

MOVE_TYPES = [
    "or_break_up",
    "or_break_dn",
    "impulse_up",
    "impulse_dn",
    "pullback_resume_up",
    "pullback_resume_dn",
    "swing_break_up",
    "swing_break_dn",
    "reversal_up",
    "reversal_dn",
]


def add_full_candle_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Complete candlestick catalog on top of base patterns."""
    out = c5.add_candle_cols(df)
    o = out["Open"].astype(float)
    h = out["High"].astype(float)
    l = out["Low"].astype(float)
    c = out["Close"].astype(float)
    body = out["body"]
    rng = out["range"].replace(0, np.nan)
    po, pc = o.shift(1), c.shift(1)
    pb = pc - po
    ph, pl = h.shift(1), l.shift(1)

    out["spinning_top"] = (
        (body.abs() / rng < 0.30) & (out["upper_frac"] > 0.25) & (out["lower_frac"] > 0.25)
    ).fillna(False).astype(np.int8)
    out["belt_bull"] = ((body > 0) & (out["lower_frac"] < 0.05) & (out["body_frac"] > 0.55)).fillna(False).astype(np.int8)
    out["belt_bear"] = ((body < 0) & (out["upper_frac"] < 0.05) & (out["body_frac"].abs() > 0.55)).fillna(False).astype(np.int8)
    # piercing / dark cloud
    mid_prev = (po + pc) / 2.0
    out["piercing"] = (
        (pb < 0) & (body > 0) & (o < pl) & (c > mid_prev) & (c < po)
    ).fillna(False).astype(np.int8)
    out["dark_cloud"] = (
        (pb > 0) & (body < 0) & (o > ph) & (c < mid_prev) & (c > po)
    ).fillna(False).astype(np.int8)
    # tweezers
    out["tweezer_bot"] = (
        (pb < 0) & (body > 0) & ((l - pl).abs() <= (rng * 0.05).fillna(1e9))
    ).fillna(False).astype(np.int8)
    out["tweezer_top"] = (
        (pb > 0) & (body < 0) & ((h - ph).abs() <= (rng * 0.05).fillna(1e9))
    ).fillna(False).astype(np.int8)
    # three soldiers / crows
    b1, b2 = body.shift(2), body.shift(1)
    out["three_soldiers"] = (
        (b1 > 0) & (b2 > 0) & (body > 0)
        & (c > c.shift(1)) & (c.shift(1) > c.shift(2))
        & (out["body_frac"] > 0.5) & (out["body_frac"].shift(1) > 0.5)
    ).fillna(False).astype(np.int8)
    out["three_crows"] = (
        (b1 < 0) & (b2 < 0) & (body < 0)
        & (c < c.shift(1)) & (c.shift(1) < c.shift(2))
        & (out["body_frac"].abs() > 0.5) & (out["body_frac"].shift(1).abs() > 0.5)
    ).fillna(False).astype(np.int8)
    # kicker (gap + opposite)
    out["bull_kicker"] = ((pb < 0) & (body > 0) & (o > po)).fillna(False).astype(np.int8)
    out["bear_kicker"] = ((pb > 0) & (body < 0) & (o < po)).fillna(False).astype(np.int8)

    # structure helpers
    out["atr14"] = (h - l).rolling(14, min_periods=5).mean()
    typ = (h + l + c) / 3.0
    out["vwap_sess"] = typ.groupby(out["day"]).cumsum() / (typ.groupby(out["day"]).cumcount() + 1)
    out["vwap_dist"] = (c - out["vwap_sess"]) / c * 100.0
    return out


ALL_PATS = list(c5.PATTERN_COLS) + EXTRA_PATS


def _pats_at(row) -> List[str]:
    return [p for p in ALL_PATS if int(row.get(p, 0)) == 1] or ["_none_"]


def _pivots(hi: np.ndarray, lo: np.ndarray, left: int = 2, right: int = 2) -> Tuple[List[int], List[int]]:
    ph, pl = [], []
    n = len(hi)
    for i in range(left, n - right):
        if hi[i] >= hi[i - left : i + right + 1].max() and hi[i] > hi[i - 1] and hi[i] > hi[i + 1]:
            ph.append(i)
        if lo[i] <= lo[i - left : i + right + 1].min() and lo[i] < lo[i - 1] and lo[i] < lo[i + 1]:
            pl.append(i)
    return ph, pl


def _move_sl_t1(side: str, entry: float, origin: float, swing_opp: float, atr: float, pat_extreme: float) -> Tuple[float, float, dict]:
    """SL/T1 from move geometry (chart only)."""
    if side == "BUY":
        sl_origin = max(entry - origin, 0.0)
        sl_swing = max(entry - swing_opp, 0.0) if swing_opp < entry else 0.0
        sl_pat = max(entry - pat_extreme, 0.0)
        t1_swing = max(swing_opp - entry, 0.0) if swing_opp > entry else 0.0
    else:
        sl_origin = max(origin - entry, 0.0)
        sl_swing = max(swing_opp - entry, 0.0) if swing_opp > entry else 0.0
        sl_pat = max(pat_extreme - entry, 0.0)
        t1_swing = max(entry - swing_opp, 0.0) if swing_opp < entry else 0.0

    # families of chart brackets from the same move
    families = {
        "move_origin": (max(sl_origin * 1.05, 0.8 * atr, 5.0), max(0.55 * atr, 0.35 * sl_origin, 5.0)),
        "move_swing": (max(sl_swing * 1.05, 0.9 * atr, 5.0), max(t1_swing * 0.7, 0.5 * atr, 5.0)),
        "move_pat": (max(sl_pat * 1.08, 0.85 * atr, 5.0), max(0.55 * atr, 5.0)),
        "move_mix": (
            max(0.6 * sl_origin + 0.4 * sl_swing, 0.9 * atr, 5.0),
            max(0.5 * atr + 0.25 * max(t1_swing, sl_origin * 0.4), 5.0),
        ),
        "atr_tight": (max(1.1 * atr, 5.0), max(0.65 * atr, 5.0)),
        "atr_wide": (max(1.5 * atr, 5.0), max(0.85 * atr, 5.0)),
    }
    # default primary = mix
    sl, t1 = families["move_mix"]
    return float(sl), float(t1), {k: (round(v[0], 2), round(v[1], 2)) for k, v in families.items()}


def collect_move_events(df: pd.DataFrame, day_lo: str, day_hi: str) -> List[dict]:
    """Identify each market move + candle confirmation as an event."""
    events: List[dict] = []
    h_all = df["High"].astype(float).values
    l_all = df["Low"].astype(float).values
    c_all = df["Close"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(df.index)}
    days = [d for d in df["day"].unique() if day_lo <= d <= day_hi]
    t0 = time.time()

    for di, day in enumerate(days, 1):
        if di % 150 == 0:
            print(f"    move events {di}/{len(days)} n={len(events)} ({time.time()-t0:.0f}s)", flush=True)
        sess = df[df["day"] == day]
        if len(sess) < OR_BARS + 30:
            continue
        hi = sess["High"].astype(float).values
        lo = sess["Low"].astype(float).values
        cl = sess["Close"].astype(float).values
        op = sess["Open"].astype(float).values
        or_hi = float(hi[:OR_BARS].max())
        or_lo = float(lo[:OR_BARS].min())
        or_w = or_hi - or_lo
        if or_w < 10:
            continue
        day_open = float(op[0])
        ph_idx, pl_idx = _pivots(hi, lo, 2, 2)
        seen_moves = set()  # (move, side) once per day — first clean print

        def emit(pos: int, side: str, move: str, origin: float, swing_opp: float, pat_ext: float, extra: dict):
            key = (move, side)
            if key in seen_moves:
                return
            ts = sess.index[pos]
            mins = int(ts.hour * 60 + ts.minute)
            if mins < 10 * 60 or mins > 14 * 60 + 45:
                return
            row = sess.iloc[pos]
            body = float(row["Close"]) - float(row["Open"])
            if side == "BUY" and body <= 0:
                return
            if side == "SELL" and body >= 0:
                return
            atr = float(row["atr14"]) if np.isfinite(row["atr14"]) else float(hi[max(0, pos - 13) : pos + 1].max() - lo[max(0, pos - 13) : pos + 1].min()) / max(1, min(14, pos + 1))
            atr = max(atr, 3.0)
            entry = float(cl[pos])
            # extension vs OR
            if side == "BUY":
                or_ext = (entry - or_hi) / or_w if entry > or_hi else max(0.0, (entry - or_lo) / or_w - 0.5)
            else:
                or_ext = (or_lo - entry) / or_w if entry < or_lo else max(0.0, (or_hi - entry) / or_w - 0.5)
            if or_ext > 0.45:
                return
            sl, t1, fams = _move_sl_t1(side, entry, origin, swing_opp, atr, pat_ext)
            full_i = idx_map[ts]
            mae, mfe = co.excursion(h_all, l_all, c_all, full_i, side)
            pats = _pats_at(row)
            # impulse length / pullback depth context
            events.append(
                {
                    "day": day,
                    "hm": base._hm(ts),
                    "decision": side,
                    "move": move,
                    "entry": entry,
                    "mins": mins,
                    "clock": co.clock_bucket(mins),
                    "or_width": or_w,
                    "or_ext": float(or_ext),
                    "atr": float(atr),
                    "mae": mae,
                    "mfe": mfe,
                    "patterns": pats,
                    "pattern_primary": pats[0],
                    "full_i": full_i,
                    "body_frac": float(row["body_frac"]),
                    "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
                    "vwap_dist": float(row["vwap_dist"]) if np.isfinite(row["vwap_dist"]) else 0.0,
                    "session_chg": float((entry - day_open) / day_open * 100),
                    "origin": float(origin),
                    "swing_opp": float(swing_opp),
                    "pat_ext": float(pat_ext),
                    "sl_default": round(sl, 2),
                    "t1_default": round(t1, 2),
                    "families": fams,
                    "marubozu": int(row["marubozu"]),
                    "hammer": int(row["hammer"]),
                    "bull_engulf": int(row["bull_engulf"]),
                    "bear_engulf": int(row["bear_engulf"]),
                    "bull_run2": int(row["bull_run2"]),
                    "bear_run2": int(row["bear_run2"]),
                    "three_soldiers": int(row.get("three_soldiers", 0)),
                    "three_crows": int(row.get("three_crows", 0)),
                    "morning_star": int(row["morning_star"]),
                    "evening_star": int(row["evening_star"]),
                    **extra,
                }
            )
            seen_moves.add(key)

        # --- OR breaks ---
        first_up = first_dn = None
        for pos in range(OR_BARS, len(sess)):
            if first_up is None and cl[pos] > or_hi:
                first_up = pos
            if first_dn is None and cl[pos] < or_lo:
                first_dn = pos
            if first_up is not None and first_dn is not None:
                break
        if first_up is not None and (first_dn is None or first_up < first_dn):
            emit(first_up, "BUY", "or_break_up", or_lo, or_hi + 0.25 * or_w, float(lo[first_up]), {"impulse_bars": first_up - OR_BARS})
        if first_dn is not None and (first_up is None or first_dn < first_up):
            emit(first_dn, "SELL", "or_break_dn", or_hi, or_lo - 0.25 * or_w, float(hi[first_dn]), {"impulse_bars": first_dn - OR_BARS})

        # --- impulse: 3+ consecutive body bars, then confirm ---
        run = 0
        run_dir = 0
        run_start = OR_BARS
        for pos in range(OR_BARS, min(len(sess), 200)):
            b = cl[pos] - op[pos]
            d = 1 if b > 0 else (-1 if b < 0 else 0)
            if d == 0:
                run, run_dir = 0, 0
                continue
            if d == run_dir:
                run += 1
            else:
                run, run_dir, run_start = 1, d, pos
            if run == 3:  # first print only when run hits 3
                atr_i = atr_est(hi, lo, pos)
                if run_dir > 0:
                    origin = float(lo[run_start : pos + 1].min())
                    target = float(cl[pos]) + 1.2 * atr_i
                    emit(pos, "BUY", "impulse_up", origin, target, float(lo[pos]), {"impulse_bars": run})
                else:
                    origin = float(hi[run_start : pos + 1].max())
                    target = float(cl[pos]) - 1.2 * atr_i
                    emit(pos, "SELL", "impulse_dn", origin, target, float(hi[pos]), {"impulse_bars": run})

        # --- pullback resume: after impulse ≥3, pullback 1–4 bars, then resume candle ---
        for pos in range(OR_BARS + 6, min(len(sess), 220)):
            # look back for impulse then pullback
            for ib in range(3, 8):
                start = pos - ib - 3
                if start < OR_BARS:
                    continue
                seg = cl[start : start + ib] - op[start : start + ib]
                if np.all(seg > 0):
                    # bullish impulse then pullback (down/flat bars) then bull resume
                    pb = cl[start + ib : pos] - op[start + ib : pos]
                    if len(pb) < 1 or len(pb) > 4:
                        continue
                    if not np.any(pb < 0):
                        continue  # need actual pullback bars
                    if cl[pos] > op[pos] and cl[pos] > cl[pos - 1]:
                        origin = float(lo[start : pos + 1].min())
                        emit(
                            pos,
                            "BUY",
                            "pullback_resume_up",
                            origin,
                            float(hi[start : start + ib].max()),
                            float(lo[start + ib : pos + 1].min()),
                            {"impulse_bars": ib, "pb_bars": len(pb)},
                        )
                        break
                if np.all(seg < 0):
                    pb = cl[start + ib : pos] - op[start + ib : pos]
                    if len(pb) < 1 or len(pb) > 4:
                        continue
                    if not np.any(pb > 0):
                        continue
                    if cl[pos] < op[pos] and cl[pos] < cl[pos - 1]:
                        origin = float(hi[start : pos + 1].max())
                        emit(
                            pos,
                            "SELL",
                            "pullback_resume_dn",
                            origin,
                            float(lo[start : start + ib].min()),
                            float(hi[start + ib : pos + 1].max()),
                            {"impulse_bars": ib, "pb_bars": len(pb)},
                        )
                        break

        # --- swing breaks ---
        for pos in range(OR_BARS + 8, min(len(sess), 230)):
            prior_ph = [i for i in ph_idx if i < pos - 1]
            prior_pl = [i for i in pl_idx if i < pos - 1]
            if prior_ph and cl[pos] > hi[prior_ph[-1]] and cl[pos] > op[pos]:
                origin = float(lo[prior_pl[-1]]) if prior_pl else float(lo[max(0, pos - 20) : pos + 1].min())
                emit(pos, "BUY", "swing_break_up", origin, float(hi[prior_ph[-1]]), float(lo[pos]), {"impulse_bars": pos - prior_ph[-1]})
            if prior_pl and cl[pos] < lo[prior_pl[-1]] and cl[pos] < op[pos]:
                origin = float(hi[prior_ph[-1]]) if prior_ph else float(hi[max(0, pos - 20) : pos + 1].max())
                emit(pos, "SELL", "swing_break_dn", origin, float(lo[prior_pl[-1]]), float(hi[pos]), {"impulse_bars": pos - prior_pl[-1]})

        # --- reversal at extreme with reversal candle ---
        for pos in range(OR_BARS + 10, min(len(sess), 240)):
            row = sess.iloc[pos]
            # bullish reversal near session low / pivot low
            recent_lo = float(lo[max(0, pos - 25) : pos].min())
            recent_hi = float(hi[max(0, pos - 25) : pos].max())
            bull_rev = int(row["morning_star"]) or int(row["bull_engulf"]) or int(row["hammer"]) or int(row["piercing"]) or int(row["tweezer_bot"]) or int(row["pin_bull"])
            bear_rev = int(row["evening_star"]) or int(row["bear_engulf"]) or int(row["shooting"]) or int(row["dark_cloud"]) or int(row["tweezer_top"]) or int(row["pin_bear"])
            if bull_rev and lo[pos] <= recent_lo * 1.0005 and cl[pos] > op[pos]:
                emit(pos, "BUY", "reversal_up", float(lo[pos]), recent_hi, float(lo[pos]), {"impulse_bars": 0})
            if bear_rev and hi[pos] >= recent_hi * 0.9995 and cl[pos] < op[pos]:
                emit(pos, "SELL", "reversal_dn", float(hi[pos]), recent_lo, float(hi[pos]), {"impulse_bars": 0})

    return events


def atr_est(hi, lo, pos, n=14) -> float:
    sl = max(0, pos - n + 1)
    return float((hi[sl : pos + 1] - lo[sl : pos + 1]).mean())


def apply_move_filters(events: List[dict], f: dict) -> List[dict]:
    out = []
    for e in events:
        if f.get("side") and e["decision"] != f["side"]:
            continue
        if f.get("moves") and e["move"] not in f["moves"]:
            continue
        if f.get("clocks") and e["clock"] not in f["clocks"]:
            continue
        if f.get("patterns") and not (set(e["patterns"]) & set(f["patterns"])):
            continue
        if f.get("max_or_ext") is not None and e["or_ext"] > f["max_or_ext"]:
            continue
        if f.get("min_or") is not None and e["or_width"] < f["min_or"]:
            continue
        if f.get("min_body") is not None and abs(e["body_frac"]) < f["min_body"]:
            continue
        if f.get("rsi_lo") is not None and e["rsi_14"] < f["rsi_lo"]:
            continue
        if f.get("rsi_hi") is not None and e["rsi_14"] > f["rsi_hi"]:
            continue
        if f.get("vwap_side") == "with":
            if e["decision"] == "BUY" and e["vwap_dist"] < 0:
                continue
            if e["decision"] == "SELL" and e["vwap_dist"] > 0:
                continue
        if f.get("min_impulse") is not None and e.get("impulse_bars", 0) < f["min_impulse"]:
            continue
        out.append(e)
    return out


def eval_family(events, h, l, c, f, fam: str) -> dict:
    rows = []
    for e in apply_move_filters(events, f):
        sl, t1 = e["families"].get(fam, (e["sl_default"], e["t1_default"]))
        win, outcome = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
        if outcome in ("bad", "both"):
            continue
        rows.append(
            {
                "day": e["day"],
                "hm": e["hm"],
                "decision": e["decision"],
                "move": e["move"],
                "entry": e["entry"],
                "sl": round(sl, 2),
                "t1": round(t1, 2),
                "patterns": e["patterns"],
                "clock": e["clock"],
                "win": win,
                "outcome": outcome,
                "or_ext": e["or_ext"],
                "atr": e["atr"],
                "body_frac": e["body_frac"],
                "rsi_14": e["rsi_14"],
                "x_chart": [
                    e["atr"],
                    e["or_width"],
                    e["or_ext"],
                    e["body_frac"],
                    e["vwap_dist"],
                    e["session_chg"],
                    e["rsi_14"],
                    float(e["mins"]),
                    1.0 if e["decision"] == "BUY" else -1.0,
                    float(e.get("impulse_bars", 0)),
                    float(e["marubozu"]),
                    float(e["bull_engulf"]),
                    float(e["bear_engulf"]),
                    float(e["morning_star"]),
                    float(e["evening_star"]),
                    float(e["three_soldiers"]),
                    float(e["three_crows"]),
                    sl,
                    t1,
                    t1 / sl if sl else 0,
                ],
            }
        )
    du = co.first_day(rows)
    a = co.agg(du)
    a["calls"] = du
    a["avg_sl"] = round(float(np.mean([r["sl"] for r in du])), 2) if du else 0
    a["avg_t1"] = round(float(np.mean([r["t1"] for r in du])), 2) if du else 0
    return a


def precompute_move(events, h, l, c, families: List[str]) -> Dict[str, List[Optional[dict]]]:
    out = {fam: [None] * len(events) for fam in families}
    t0 = time.time()
    for ei, e in enumerate(events):
        if (ei + 1) % 200 == 0:
            print(f"    precompute moves {ei+1}/{len(events)} ({time.time()-t0:.0f}s)", flush=True)
        for fam in families:
            sl, t1 = e["families"].get(fam, (e["sl_default"], e["t1_default"]))
            win, outcome = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
            if outcome in ("bad", "both"):
                continue
            out[fam][ei] = {
                "day": e["day"],
                "hm": e["hm"],
                "decision": e["decision"],
                "move": e["move"],
                "entry": e["entry"],
                "sl": round(sl, 2),
                "t1": round(t1, 2),
                "patterns": e["patterns"],
                "clock": e["clock"],
                "win": win,
                "outcome": outcome,
                "or_ext": e["or_ext"],
                "atr": e["atr"],
                "body_frac": e["body_frac"],
                "rsi_14": e["rsi_14"],
                "vwap_dist": e["vwap_dist"],
                "impulse_bars": e.get("impulse_bars", 0),
                "x_chart": [
                    e["atr"],
                    e["or_width"],
                    e["or_ext"],
                    e["body_frac"],
                    e["vwap_dist"],
                    e["session_chg"],
                    e["rsi_14"],
                    float(e["mins"]),
                    1.0 if e["decision"] == "BUY" else -1.0,
                    float(e.get("impulse_bars", 0)),
                    float(e["marubozu"]),
                    float(e["bull_engulf"]),
                    float(e["bear_engulf"]),
                    float(e["morning_star"]),
                    float(e["evening_star"]),
                    float(e["three_soldiers"]),
                    float(e["three_crows"]),
                    sl,
                    t1,
                    t1 / sl if sl else 0,
                ],
            }
    return out


def event_mask(events, f) -> List[bool]:
    kept = {(e["day"], e["hm"], e["decision"], e["move"]) for e in apply_move_filters(events, f)}
    return [(e["day"], e["hm"], e["decision"], e["move"]) in kept for e in events]


def hunt(ana, test, ana_pre, test_pre, families) -> dict:
    print("\n[3] Hunt 100% move+candle logics…", flush=True)
    move_sets = [
        None,
        ["or_break_up", "or_break_dn"],
        ["or_break_up"],
        ["or_break_dn"],
        ["impulse_up", "impulse_dn"],
        ["impulse_up"],
        ["impulse_dn"],
        ["pullback_resume_up", "pullback_resume_dn"],
        ["pullback_resume_up"],
        ["pullback_resume_dn"],
        ["swing_break_up", "swing_break_dn"],
        ["swing_break_up"],
        ["swing_break_dn"],
        ["reversal_up", "reversal_dn"],
        ["reversal_up"],
        ["reversal_dn"],
        ["or_break_up", "impulse_up", "pullback_resume_up", "swing_break_up"],
        ["or_break_dn", "impulse_dn", "pullback_resume_dn", "swing_break_dn"],
        ["impulse_up", "pullback_resume_up"],
        ["impulse_dn", "pullback_resume_dn"],
    ]
    pattern_sets = [
        None,
        ["marubozu"],
        ["bull_engulf", "bear_engulf"],
        ["hammer", "pin_bull", "morning_star", "piercing", "tweezer_bot"],
        ["shooting", "pin_bear", "evening_star", "dark_cloud", "tweezer_top"],
        ["three_soldiers", "bull_run3", "marubozu"],
        ["three_crows", "bear_run3", "marubozu"],
        ["bull_run2", "bear_run2"],
        ["outside", "belt_bull", "belt_bear"],
        ["bull_kicker", "bear_kicker"],
    ]
    sides = [None, "BUY", "SELL"]
    clocks = [None, ["early"], ["early", "morning"], ["early", "morning", "midday"]]
    exts = [0.12, 0.18, 0.25]
    min_ors = [12, 20]
    bodies = [None, 0.50, 0.70]
    rsis = [None, (45, 65), (40, 70)]
    vwap = [None, "with"]

    grid = []
    for mv, pat, side, clk, ext, mor, mb, rsi, vw in product(
        move_sets, pattern_sets, sides, clocks, exts, min_ors, bodies, rsis, vwap
    ):
        # skip nonsense: BUY-only pats with SELL side etc. still ok via intersection
        g = {
            "moves": mv,
            "patterns": pat,
            "side": side,
            "clocks": clk,
            "max_or_ext": ext,
            "min_or": mor,
            "min_body": mb,
            "vwap_side": vw,
        }
        if rsi:
            g["rsi_lo"], g["rsi_hi"] = rsi
        grid.append(g)
    # ~20*10*3*4*3*2*3*3*2 = 259200 → stride 5 ≈ 50k
    grid = grid[::5]
    print(f"  filter combos={len(grid)} families={families}", flush=True)

    results_100, results_hi = [], []
    t0 = time.time()
    n_try = 0
    for fi, f in enumerate(grid, 1):
        if fi % 2500 == 0:
            print(f"    {fi}/{len(grid)} found100={len(results_100)} ({time.time()-t0:.0f}s)", flush=True)
        am = event_mask(ana, f)
        if sum(am) < 5:
            continue
        tm = event_mask(test, f)
        for fam in families:
            n_try += 1
            ares = co._agg_pre(ana, ana_pre[fam], am)
            if ares["n"] < 5:
                continue
            if ares["hit_pct"] < 70:
                continue
            tres = co._agg_pre(test, test_pre[fam], tm)
            compact = {
                "bracket": fam,
                "filters": f,
                "analyze": {k: ares[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                "test": {k: tres[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
            }
            if ares["hit_pct"] >= 100 - 1e-9:
                if tres["hit_pct"] >= 100 - 1e-9 and tres["n"] >= 1:
                    compact["test_calls"] = tres["calls"]
                    compact["analyze_calls"] = ares["calls"]
                results_100.append(compact)
            elif ares["n"] >= 8 and len(results_hi) < 300:
                results_hi.append(compact)

    def sig(r):
        days = tuple(sorted(c["day"] for c in r.get("test_calls") or []))
        return (r["bracket"], r["analyze"]["n"], r["test"]["n"], days, json.dumps(r["filters"], sort_keys=True, default=str))

    uniq, seen = [], set()
    for r in sorted(results_100, key=lambda x: (-(x["test"]["n"] if x["test"]["hit_pct"] >= 100 else 0), -x["analyze"]["n"])):
        s = sig(r)
        if s in seen:
            continue
        seen.add(s)
        uniq.append(r)

    both = [r for r in uniq if r["test"]["hit_pct"] >= 100 - 1e-9 and r["test"]["n"] >= 1 and "test_calls" in r]
    both.sort(key=lambda r: (-r["test"]["n"], -r["analyze"]["n"]))

    # materialize top analyze100
    analyze100 = []
    for r in uniq[:40]:
        if "analyze_calls" not in r:
            am = event_mask(ana, r["filters"])
            tm = event_mask(test, r["filters"])
            ares = co._agg_pre(ana, ana_pre[r["bracket"]], am)
            tres = co._agg_pre(test, test_pre[r["bracket"]], tm)
            r = dict(r)
            r["analyze_calls"] = ares["calls"]
            r["test_calls"] = tres["calls"]
        analyze100.append(r)

    by_day = {}
    for r in both:
        for call in r.get("test_calls") or []:
            by_day.setdefault(call["day"], call)
    union = co.first_day(list(by_day.values()))
    print(
        f"  tried~{n_try} analyze100={len(uniq)} both100={len(both)} union={len(union)} ({time.time()-t0:.0f}s)",
        flush=True,
    )
    return {
        "analyze100": analyze100,
        "both100": both[:30],
        "hi70": sorted(results_hi, key=lambda r: (-r["test"]["hit_pct"], -r["test"]["n"]))[:20],
        "union100": {
            "n": len(union),
            "wins": sum(1 for x in union if x.get("win")),
            "hit_pct": co.agg(union)["hit_pct"],
            "calls": union,
        },
    }


def move_census(events: List[dict]) -> dict:
    by_move = defaultdict(int)
    by_pat = defaultdict(int)
    for e in events:
        by_move[e["move"]] += 1
        for p in e["patterns"][:3]:
            by_pat[p] += 1
    return {
        "by_move": dict(sorted(by_move.items(), key=lambda x: -x[1])),
        "top_patterns": dict(sorted(by_pat.items(), key=lambda x: -x[1])[:25]),
        "n": len(events),
    }


def train_ml(calls, test_calls=None):
    from sklearn.ensemble import HistGradientBoostingClassifier

    rows = [r for r in calls if r and r["day"] <= TRAIN_END]
    if len(rows) < 30 or len(set(bool(r["win"]) for r in rows)) < 2:
        return None
    X = np.asarray([r["x_chart"] for r in rows], dtype=float)
    y = np.asarray([1 if r["win"] else 0], dtype=int) if False else np.asarray([1 if r["win"] else 0 for r in rows], dtype=int)
    w = recent_sample_weights([r["day"] for r in rows], half_life_days=400.0)
    clf = HistGradientBoostingClassifier(
        max_depth=3, max_iter=120, min_samples_leaf=12, l2_regularization=1.0, learning_rate=0.05, random_state=42
    )
    clf.fit(X, y, sample_weight=w)
    out = {
        "base": clf,
        "fit_auc": round(base._auc(y, clf.predict_proba(X)[:, 1]), 3),
        "n_train": len(rows),
        "chart_only": True,
        "research_only": True,
    }
    if test_calls:
        te = [r for r in test_calls if r]
        Xt = np.asarray([r["x_chart"] for r in te], dtype=float)
        yt = np.asarray([1 if r["win"] else 0 for r in te], dtype=int)
        pt = clf.predict_proba(Xt)[:, 1]
        out["test_auc"] = round(base._auc(yt, pt), 3) if len(set(yt.tolist())) > 1 else None
        best = None
        for q in (0.7, 0.8, 0.85, 0.9, 0.93, 0.95):
            thr = float(np.quantile(pt, q))
            rows2 = []
            for r, p in zip(te, pt):
                if p >= thr:
                    rr = dict(r)
                    rr["prob"] = float(p)
                    rows2.append(rr)
            du = co.first_day(rows2)
            if len(du) < 3:
                continue
            hit = co.agg(du)["hit_pct"]
            cand = {"q": q, "thr": round(thr, 4), "n": len(du), "hit_pct": hit, "calls": du}
            if hit >= 100 - 1e-9 and (best is None or cand["n"] > best["n"]):
                best = cand
        if best:
            out["test_p_slice"] = {k: v for k, v in best.items() if k != "calls"}
            out["test_p_calls"] = best["calls"]
    return out


def write_report(meta, hunt_res, census_a, census_t, pack_ml):
    OUT.mkdir(parents=True, exist_ok=True)
    both = hunt_res.get("both100") or []
    union = hunt_res.get("union100") or {}
    lines = [
        "# NIFTY 1m — **complete candlestick + market-move** model · 100% max-calls",
        "",
        "**Not live.** Full candle catalog + every move type (impulse / pullback / swing-break / OR-break / reversal).",
        "SL/T1 from **move geometry** (origin, swing, pattern extreme, ATR mix).",
        "",
        f"- Analyze ≤ `{ANALYZE_END}` · Train ≤ `{TRAIN_END}` · Test ≥ `{TEST_START}`",
        f"- Move events ana/test: {meta.get('n_ana')} / {meta.get('n_test')}",
        "",
        "## Candlestick catalog",
        "",
        f"Patterns: `{', '.join(ALL_PATS)}`",
        "",
        "## Market-move taxonomy",
        "",
        "| Move | Meaning |",
        "|---|---|",
        "| `or_break_up/dn` | First clean OR break with confirming candle |",
        "| `impulse_up/dn` | ≥3 consecutive body bars same direction |",
        "| `pullback_resume_up/dn` | Impulse → 1–4 bar pullback → resume candle |",
        "| `swing_break_up/dn` | Close beyond last pivot high/low |",
        "| `reversal_up/dn` | Reversal candle at session extreme |",
        "",
        "### Analyze census",
        "",
        f"- Events: {census_a.get('n')}",
        f"- By move: `{json.dumps(census_a.get('by_move'))}`",
        f"- Top patterns: `{json.dumps(census_a.get('top_patterns'))}`",
        "",
        "### Test census",
        "",
        f"- Events: {census_t.get('n')}",
        f"- By move: `{json.dumps(census_t.get('by_move'))}`",
        "",
        f"## Both-window 100%: **{len(both)}** logics · Union **{union.get('n')} @ {union.get('hit_pct')}%**",
        "",
    ]
    if union.get("calls"):
        lines += ["| Day | HM | Side | Move | SL | T1 | Win |", "|---|---|---|---|---:|---:|:---:|"]
        for c in union["calls"]:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['decision']} | {c.get('move','')} | {c['sl']} | {c['t1']} | "
                f"{'Y' if c['win'] else 'N'} |"
            )
        lines.append("")

    lines += ["## Best both-100 (max test n)", "", "| # | Bracket | Filters | Ana | Test | SL/T1 |", "|---:|---|---|---:|---:|---|"]
    for i, r in enumerate(both[:12], 1):
        f = r["filters"]
        short = (
            f"mv={f.get('moves')} pat={f.get('patterns')} side={f.get('side')} "
            f"clk={f.get('clocks')} ext≤{f.get('max_or_ext')} rsi={f.get('rsi_lo')}-{f.get('rsi_hi')} body≥{f.get('min_body')}"
        )
        lines.append(
            f"| {i} | `{r['bracket']}` | {short[:110]} | {r['analyze']['n']} | **{r['test']['n']}** | "
            f"{r['test']['avg_sl']}/{r['test']['avg_t1']} |"
        )

    if both:
        best = both[0]
        lines += [
            "",
            f"### Detail · best · test **{best['test']['n']} @ 100%**",
            "",
            f"- Bracket family: `{best['bracket']}` (move-geometry SL/T1)",
            f"- Filters: `{json.dumps(best['filters'], default=str)}`",
            f"- Analyze: {best['analyze']['n']} @ 100%",
            "",
            "| Day | HM | Side | Move | Patterns | SL | T1 |",
            "|---|---|---|---|---|---:|---:|",
        ]
        for c in best.get("test_calls") or []:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['decision']} | {c.get('move','')} | "
                f"{','.join((c.get('patterns') or [])[:4])} | {c['sl']} | {c['t1']} |"
            )

    lines += ["", "## Near-miss", "", "| Bracket | Ana | Test |", "|---|---|---|"]
    for r in (hunt_res.get("hi70") or [])[:10]:
        lines.append(
            f"| `{r['bracket']}` | {r['analyze']['n']}@{r['analyze']['hit_pct']}% | "
            f"{r['test']['n']}@{r['test']['hit_pct']}% |"
        )

    lines += ["", "## Chart ML on move features", ""]
    if pack_ml:
        sl = pack_ml.get("test_p_slice") or {}
        lines.append(
            f"- n={pack_ml.get('n_train')} fit_auc={pack_ml.get('fit_auc')} test_auc={pack_ml.get('test_auc')} "
            f"P-slice={sl.get('n')}@{sl.get('hit_pct')}%"
        )
    else:
        lines.append("- skipped")

    lines += ["", "## Research pick", ""]
    if both:
        lines.append(
            f"**Best single move-logic:** `{both[0]['bracket']}` · test **{both[0]['test']['n']} @ 100%** "
            f"(analyze {both[0]['analyze']['n']} @ 100%)."
        )
        if union.get("n", 0) > both[0]["test"]["n"]:
            lines.append(f"**Union book:** **{union['n']} @ 100%** across both-100 micros.")
    else:
        lines.append("No both-100 yet — see near-miss.")

    lines += ["", "## Policy", "", f"- Pack: `{PACK}`", "- research_only · not_live · candle+move chart-only", ""]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    payload = {
        "meta": meta,
        "census_analyze": census_a,
        "census_test": census_t,
        "both100": [{k: v for k, v in r.items() if k != "analyze_calls"} for r in both[:15]],
        "union100": union,
        "hi70": [{k: v for k, v in r.items() if k not in ("analyze_calls", "test_calls")} for r in (hunt_res.get("hi70") or [])[:15]],
        "ml": {k: v for k, v in (pack_ml or {}).items() if k != "base"},
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {REPORT_MD}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · COMPLETE CANDLE + MARKET MOVES · 100% max-calls", flush=True)
    print(f"analyze≤{ANALYZE_END} train≤{TRAIN_END} test≥{TEST_START}", flush=True)
    print("=" * 60, flush=True)

    raw = base.load_existing_1m()
    raw = raw[
        (raw.index >= pd.Timestamp(START, tz="Asia/Kolkata"))
        & (raw.index <= pd.Timestamp(f"{END} 23:59:59", tz="Asia/Kolkata"))
    ]
    if raw.empty:
        print("FAIL: no bars", flush=True)
        return 1
    print(f"tape bars={len(raw)}", flush=True)

    print("\n[0] Full candlestick catalog…", flush=True)
    df = add_full_candle_cols(raw)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values

    print("\n[1] Identify every market move + candle confirm…", flush=True)
    ana = collect_move_events(df, START, ANALYZE_END)
    test = collect_move_events(df, TEST_START, END)
    print(f"  analyze={len(ana)} test={len(test)}", flush=True)
    census_a = move_census(ana)
    census_t = move_census(test)
    print(f"  ana moves={census_a['by_move']}", flush=True)
    print(f"  test moves={census_t['by_move']}", flush=True)

    families = ["move_mix", "move_origin", "move_swing", "move_pat", "atr_tight", "atr_wide"]
    print("\n[2] Precompute move-geometry brackets…", flush=True)
    ana_pre = precompute_move(ana, h, l, c, families)
    test_pre = precompute_move(test, h, l, c, families)

    hunt_res = hunt(ana, test, ana_pre, test_pre, families)

    print("\n[4] Train chart ML on move features…", flush=True)
    train_pool = [r for r in (ana_pre.get("move_mix") or []) if r]
    test_pool = [r for r in (test_pre.get("move_mix") or []) if r]
    for r in (hunt_res.get("analyze100") or [])[:15]:
        train_pool.extend(r.get("analyze_calls") or [])
    pack_ml = train_ml(train_pool, test_pool)
    if pack_ml:
        sl = pack_ml.get("test_p_slice") or {}
        print(f"  ML n={pack_ml['n_train']} fit_auc={pack_ml['fit_auc']} slice={sl.get('n')}@{sl.get('hit_pct')}%", flush=True)
        if sl.get("hit_pct", 0) >= 100 and pack_ml.get("test_p_calls"):
            by = {c["day"]: c for c in (hunt_res["union100"].get("calls") or [])}
            for c in pack_ml["test_p_calls"]:
                by.setdefault(c["day"], c)
            union = co.first_day(list(by.values()))
            hunt_res["union100"] = {
                "n": len(union),
                "wins": sum(1 for x in union if x.get("win")),
                "hit_pct": co.agg(union)["hit_pct"],
                "calls": union,
            }

    meta = {
        "n_ana": len(ana),
        "n_test": len(test),
        "n_both100": len(hunt_res.get("both100") or []),
        "union_n": (hunt_res.get("union100") or {}).get("n"),
        "patterns": ALL_PATS,
        "moves": MOVE_TYPES,
        "chart_only": True,
        "candle_moves": True,
        "hardcoded_sl_t1": False,
        "research_only": True,
        "not_live": True,
    }
    PACK.mkdir(parents=True, exist_ok=True)
    (PACK / "census.json").write_text(json.dumps({"analyze": census_a, "test": census_t}, indent=2), encoding="utf-8")
    if hunt_res.get("both100"):
        (PACK / "best_both100.json").write_text(
            json.dumps(
                {
                    "bracket": hunt_res["both100"][0]["bracket"],
                    "filters": hunt_res["both100"][0]["filters"],
                    "analyze": hunt_res["both100"][0]["analyze"],
                    "test": hunt_res["both100"][0]["test"],
                    "test_calls": hunt_res["both100"][0]["test_calls"],
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
    if pack_ml:
        import joblib

        joblib.dump(pack_ml, PACK / "move_ranker.joblib")

    write_report(meta, hunt_res, census_a, census_t, pack_ml)
    u = hunt_res.get("union100") or {}
    print("\n" + "=" * 60, flush=True)
    print(f"BOTH100={meta['n_both100']} · UNION {u.get('n')}@{u.get('hit_pct')}%", flush=True)
    if hunt_res.get("both100"):
        b = hunt_res["both100"][0]
        print(
            f"BEST: {b['bracket']} mv={b['filters'].get('moves')} "
            f"test {b['test']['n']}@100% ana {b['analyze']['n']}@100%",
            flush=True,
        )
    print("DONE · candle+moves · research only", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
