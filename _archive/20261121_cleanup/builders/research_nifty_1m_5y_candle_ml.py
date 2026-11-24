"""RESEARCH ONLY — 5y NIFTY 1m candlestick deep analysis (2021–2025) → accurate ML.

1) Analyse every session: open → path → close, classic + multi-bar patterns,
   which patterns actually predict forward T1/SL (±30) or next-bar direction.
2) Keep only patterns/features with real edge on TRAIN.
3) Train dual BUY/SELL heads on pattern-informed features; score OOS after freeze.

  python -u prod_live/tests/builders/research_nifty_1m_5y_candle_ml.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401,E402

import research_nifty_1m_dual_clean_train as base  # noqa: E402
from nifty_side_clean import recent_sample_weights  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_5y_candle_ml"
REPORT_MD = OUT / "NIFTY_1M_5Y_CANDLE_ML.md"
REPORT_JSON = OUT / "NIFTY_1M_5Y_CANDLE_ML.json"

START = "2021-01-01"
END = "2025-12-30"
FREEZE = "2024-09-10"  # chronological OOS after this
RISK = 30.0
OR_BARS = 15
HORIZON = 30  # bars for pattern forward study


# ───────────────────────── candle geometry ─────────────────────────
def add_candle_cols(df: pd.DataFrame) -> pd.DataFrame:
    o, h, l, c = df["Open"].astype(float), df["High"].astype(float), df["Low"].astype(float), df["Close"].astype(float)
    body = c - o
    rng = (h - l).replace(0, np.nan)
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l
    out = df.copy()
    out["body"] = body
    out["range"] = h - l
    out["body_frac"] = (body / rng).fillna(0.0)
    out["upper_wick"] = upper
    out["lower_wick"] = lower
    out["upper_frac"] = (upper / rng).fillna(0.0)
    out["lower_frac"] = (lower / rng).fillna(0.0)
    out["bull"] = (body > 0).astype(np.int8)
    out["bear"] = (body < 0).astype(np.int8)
    out["doji"] = ((body.abs() / rng) < 0.1).fillna(False).astype(np.int8)
    out["marubozu"] = ((body.abs() / rng) > 0.85).fillna(False).astype(np.int8)
    out["hammer"] = ((lower > body.abs() * 2) & (upper < body.abs() * 0.5) & (body.abs() > 0)).fillna(False).astype(np.int8)
    out["inv_hammer"] = ((upper > body.abs() * 2) & (lower < body.abs() * 0.5) & (body.abs() > 0)).fillna(False).astype(np.int8)
    out["shooting"] = ((upper > body.abs() * 2) & (lower < body.abs() * 0.5) & (body < 0)).fillna(False).astype(np.int8)
    out["hanging"] = ((lower > body.abs() * 2) & (upper < body.abs() * 0.5) & (body < 0)).fillna(False).astype(np.int8)
    # prior bar for engulf / harami / inside
    po, pc = o.shift(1), c.shift(1)
    pb = pc - po
    out["bull_engulf"] = ((body > 0) & (pb < 0) & (c >= po) & (o <= pc)).fillna(False).astype(np.int8)
    out["bear_engulf"] = ((body < 0) & (pb > 0) & (c <= po) & (o >= pc)).fillna(False).astype(np.int8)
    out["bull_harami"] = ((body > 0) & (pb < 0) & (o >= pc) & (c <= po)).fillna(False).astype(np.int8)
    out["bear_harami"] = ((body < 0) & (pb > 0) & (o <= pc) & (c >= po)).fillna(False).astype(np.int8)
    ph, pl = h.shift(1), l.shift(1)
    out["inside"] = ((h <= ph) & (l >= pl)).fillna(False).astype(np.int8)
    out["outside"] = ((h >= ph) & (l <= pl)).fillna(False).astype(np.int8)
    # pin bars (wick-dominant)
    out["pin_bull"] = (
        (out["lower_frac"] > 0.60) & (out["upper_frac"] < 0.25) & (out["body_frac"].abs() < 0.35)
    ).fillna(False).astype(np.int8)
    out["pin_bear"] = (
        (out["upper_frac"] > 0.60) & (out["lower_frac"] < 0.25) & (out["body_frac"].abs() < 0.35)
    ).fillna(False).astype(np.int8)
    # 3-bar: morning/evening star (simplified)
    b1, b2 = body.shift(2), body.shift(1)
    out["morning_star"] = (
        (b1 < 0)
        & (body.shift(1).abs() < body.shift(2).abs() * 0.4)
        & (body > 0)
        & (c > ((o.shift(2) + c.shift(2)) / 2.0))
    ).fillna(False).astype(np.int8)
    out["evening_star"] = (
        (b1 > 0)
        & (body.shift(1).abs() < body.shift(2).abs() * 0.4)
        & (body < 0)
        & (c < ((o.shift(2) + c.shift(2)) / 2.0))
    ).fillna(False).astype(np.int8)
    # consecutive runs
    out["bull_run2"] = ((body > 0) & (pb > 0)).fillna(False).astype(np.int8)
    out["bear_run2"] = ((body < 0) & (pb < 0)).fillna(False).astype(np.int8)
    out["bull_run3"] = ((body > 0) & (pb > 0) & (body.shift(2) > 0)).fillna(False).astype(np.int8)
    out["bear_run3"] = ((body < 0) & (pb < 0) & (body.shift(2) < 0)).fillna(False).astype(np.int8)
    out["ret_1"] = c.pct_change() * 100.0
    out["ret_3"] = c.pct_change(3) * 100.0
    out["ret_6"] = c.pct_change(6) * 100.0
    # RSI
    delta = c.diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = (-delta.clip(upper=0)).rolling(14).mean()
    rs = up / down.replace(0, np.nan)
    out["rsi_14"] = (100 - (100 / (1 + rs))).fillna(50.0)
    out["day"] = [base._day(ts) for ts in out.index]
    out["hm"] = [base._hm(ts) for ts in out.index]
    mins = out.index.hour * 60 + out.index.minute
    out["mins"] = mins
    return out


PATTERN_COLS = [
    "doji",
    "marubozu",
    "hammer",
    "inv_hammer",
    "shooting",
    "hanging",
    "bull_engulf",
    "bear_engulf",
    "bull_harami",
    "bear_harami",
    "inside",
    "outside",
    "pin_bull",
    "pin_bear",
    "morning_star",
    "evening_star",
    "bull_run2",
    "bear_run2",
    "bull_run3",
    "bear_run3",
]


def fwd_dir_hit(c: np.ndarray, i: int, horizon: int) -> Tuple[int, float]:
    """1 if close[i+h] > close[i], -1 if down, 0 flat/insufficient. Also return pts."""
    if i + horizon >= len(c):
        return 0, 0.0
    d = float(c[i + horizon] - c[i])
    if d > 1e-9:
        return 1, d
    if d < -1e-9:
        return -1, d
    return 0, 0.0


def fwd_t1_sl(h: np.ndarray, l: np.ndarray, c: np.ndarray, i: int, side: str, risk: float) -> Tuple[bool, str]:
    entry = float(c[i])
    if side == "BUY":
        sl, t1 = entry - risk, entry + risk
        for j in range(i + 1, len(c)):
            hit_sl = float(l[j]) <= sl
            hit_t1 = float(h[j]) >= t1
            if hit_t1 and hit_sl:
                return False, "both"
            if hit_t1:
                return True, "t1"
            if hit_sl:
                return False, "sl"
        return False, "exp"
    else:
        sl, t1 = entry + risk, entry - risk
        for j in range(i + 1, len(c)):
            hit_sl = float(h[j]) >= sl
            hit_t1 = float(l[j]) <= t1
            if hit_t1 and hit_sl:
                return False, "both"
            if hit_t1:
                return True, "t1"
            if hit_sl:
                return False, "sl"
        return False, "exp"


# ───────────────────────── session open→close analysis ─────────────────────────
def analyse_sessions(df: pd.DataFrame) -> Dict[str, Any]:
    print("\n[A] Session open→close analysis…", flush=True)
    days = df.groupby("day", sort=True)
    rows = []
    for day, sess in days:
        if len(sess) < 60:
            continue
        o = float(sess["Open"].iloc[0])
        c = float(sess["Close"].iloc[-1])
        hi = float(sess["High"].max())
        lo = float(sess["Low"].min())
        or_hi = float(sess["High"].iloc[:OR_BARS].max())
        or_lo = float(sess["Low"].iloc[:OR_BARS].min())
        # first hour / last hour
        fh = sess.iloc[:60]
        lh = sess.iloc[-60:]
        rows.append(
            {
                "day": day,
                "open": o,
                "close": c,
                "day_ret_pct": (c - o) / o * 100.0,
                "range_pct": (hi - lo) / o * 100.0,
                "close_in_range": (c - lo) / max(hi - lo, 1e-9),
                "or_width": or_hi - or_lo,
                "or_break_up": float(sess["Close"].iloc[OR_BARS:].max() > or_hi) if len(sess) > OR_BARS else 0,
                "or_break_dn": float(sess["Close"].iloc[OR_BARS:].min() < or_lo) if len(sess) > OR_BARS else 0,
                "first_hour_ret": (float(fh["Close"].iloc[-1]) - o) / o * 100.0,
                "last_hour_ret": (c - float(lh["Open"].iloc[0])) / o * 100.0,
                "gap_proxy": 0.0,  # filled later
                "up_day": int(c > o),
                "close_near_high": int((c - lo) / max(hi - lo, 1e-9) >= 0.75),
                "close_near_low": int((c - lo) / max(hi - lo, 1e-9) <= 0.25),
            }
        )
    sess_df = pd.DataFrame(rows)
    # gap vs prior close
    sess_df["prev_close"] = sess_df["close"].shift(1)
    sess_df["gap_pct"] = (sess_df["open"] - sess_df["prev_close"]) / sess_df["prev_close"] * 100.0
    # first-hour continuation to close
    fh_up = sess_df["first_hour_ret"] > 0.05
    fh_dn = sess_df["first_hour_ret"] < -0.05
    cont_up = float((sess_df.loc[fh_up, "up_day"] == 1).mean()) if fh_up.any() else None
    cont_dn = float((sess_df.loc[fh_dn, "up_day"] == 0).mean()) if fh_dn.any() else None
    # OR break → same-day close side
    both = (sess_df["or_break_up"] == 1) & (sess_df["or_break_dn"] == 1)
    only_up = (sess_df["or_break_up"] == 1) & (sess_df["or_break_dn"] == 0)
    only_dn = (sess_df["or_break_dn"] == 1) & (sess_df["or_break_up"] == 0)
    summary = {
        "n_sessions": int(len(sess_df)),
        "up_day_rate": round(float(sess_df["up_day"].mean()) * 100, 2),
        "mean_day_ret_pct": round(float(sess_df["day_ret_pct"].mean()), 4),
        "mean_range_pct": round(float(sess_df["range_pct"].mean()), 4),
        "mean_or_width": round(float(sess_df["or_width"].mean()), 2),
        "close_near_high_pct": round(float(sess_df["close_near_high"].mean()) * 100, 2),
        "close_near_low_pct": round(float(sess_df["close_near_low"].mean()) * 100, 2),
        "first_hour_up_then_up_close": round(cont_up * 100, 2) if cont_up is not None else None,
        "first_hour_dn_then_dn_close": round(cont_dn * 100, 2) if cont_dn is not None else None,
        "or_only_up_then_up_close": round(float(sess_df.loc[only_up, "up_day"].mean()) * 100, 2) if only_up.any() else None,
        "or_only_dn_then_dn_close": round(float((1 - sess_df.loc[only_dn, "up_day"]).mean()) * 100, 2) if only_dn.any() else None,
        "or_both_sides_pct": round(float(both.mean()) * 100, 2),
        "gap_up_then_up_close": round(
            float(sess_df.loc[sess_df["gap_pct"] > 0.35, "up_day"].mean()) * 100, 2
        )
        if (sess_df["gap_pct"] > 0.35).any()
        else None,
        "gap_dn_then_dn_close": round(
            float((1 - sess_df.loc[sess_df["gap_pct"] < -0.35, "up_day"]).mean()) * 100, 2
        )
        if (sess_df["gap_pct"] < -0.35).any()
        else None,
    }
    print(f"  sessions={summary['n_sessions']} up_day={summary['up_day_rate']}%", flush=True)
    return {"summary": summary, "sessions": sess_df}


# ───────────────────────── pattern edge study ─────────────────────────
def analyse_patterns(df: pd.DataFrame, train_end: str) -> Dict[str, Any]:
    """Measure each pattern's forward edge on TRAIN only (no leakage)."""
    print("\n[B] Pattern forward-edge study (train only)…", flush=True)
    train = df[df["day"] <= train_end]
    c = train["Close"].astype(float).values
    h = train["High"].astype(float).values
    l = train["Low"].astype(float).values
    mins = train["mins"].values
    n = len(train)
    # sample every bar after OR in session hours for speed: use stride 1 but only 09:45–14:45
    mask_clock = (mins >= 9 * 60 + 45) & (mins <= 14 * 60 + 45)
    results = []
    t0 = time.time()
    for pi, pname in enumerate(PATTERN_COLS):
        flags = train[pname].astype(bool).values & mask_clock
        idxs = np.where(flags)[0]
        if len(idxs) > 8000:
            idxs = idxs[:: max(1, len(idxs) // 8000)]
        # direction horizon
        dir_up = dir_dn = 0
        buy_t1 = buy_n = sell_t1 = sell_n = 0
        for i in idxs:
            d, _ = fwd_dir_hit(c, int(i), HORIZON)
            if d > 0:
                dir_up += 1
            elif d < 0:
                dir_dn += 1
            # pattern-implied side
            bullish = pname in (
                "hammer",
                "bull_engulf",
                "bull_harami",
                "pin_bull",
                "morning_star",
                "bull_run2",
                "bull_run3",
                "marubozu",
            ) and (pname != "marubozu" or float(train["body"].iloc[i]) > 0)
            bearish = pname in (
                "shooting",
                "hanging",
                "bear_engulf",
                "bear_harami",
                "pin_bear",
                "evening_star",
                "bear_run2",
                "bear_run3",
            ) or (pname == "marubozu" and float(train["body"].iloc[i]) < 0)
            if bullish or pname in ("doji", "inside", "outside", "inv_hammer"):
                # for neutral patterns test both; for bullish test BUY
                if bullish or pname in ("doji", "inside", "outside", "inv_hammer"):
                    ok, _ = fwd_t1_sl(h, l, c, int(i), "BUY", RISK)
                    buy_n += 1
                    buy_t1 += int(ok)
            if bearish or pname in ("doji", "inside", "outside", "inv_hammer"):
                ok, _ = fwd_t1_sl(h, l, c, int(i), "SELL", RISK)
                sell_n += 1
                sell_t1 += int(ok)
        total_dir = dir_up + dir_dn
        row = {
            "pattern": pname,
            "n_samples": int(len(idxs)),
            "dir_up_pct": round(100.0 * dir_up / total_dir, 2) if total_dir else None,
            "buy_t1_pct": round(100.0 * buy_t1 / buy_n, 2) if buy_n else None,
            "buy_n": int(buy_n),
            "sell_t1_pct": round(100.0 * sell_t1 / sell_n, 2) if sell_n else None,
            "sell_n": int(sell_n),
        }
        # edge vs 50
        edges = []
        if row["buy_t1_pct"] is not None and buy_n >= 80:
            edges.append(("BUY", row["buy_t1_pct"] - 50.0, buy_n))
        if row["sell_t1_pct"] is not None and sell_n >= 80:
            edges.append(("SELL", row["sell_t1_pct"] - 50.0, sell_n))
        row["best_side"] = max(edges, key=lambda x: x[1])[0] if edges else None
        row["best_edge"] = round(max(edges, key=lambda x: x[1])[1], 2) if edges else None
        results.append(row)
        print(
            f"  {pname}: n={row['n_samples']} buy_t1={row['buy_t1_pct']} sell_t1={row['sell_t1_pct']} "
            f"edge={row['best_edge']} ({time.time()-t0:.0f}s)",
            flush=True,
        )
    results.sort(key=lambda r: -(r["best_edge"] if r["best_edge"] is not None else -999))
    return {"patterns": results, "horizon_bars": HORIZON, "risk": RISK}


# ───────────────────────── OR-break tickets with pattern features ─────────────────────────
FEAT_NAMES = [
    "ret_1",
    "ret_3",
    "ret_6",
    "rsi_14",
    "body_frac",
    "upper_frac",
    "lower_frac",
    "bar_range_pct",
    "or_width",
    "or_ext",
    "mins_entry",
    "first_break",
    "gap_pct",
    "session_chg",
    "vwap_dist",
    "atr_ratio",
    "noise_vs_sl",
    "pat_doji",
    "pat_hammer",
    "pat_shooting",
    "pat_bull_engulf",
    "pat_bear_engulf",
    "pat_pin_bull",
    "pat_pin_bear",
    "pat_morning",
    "pat_evening",
    "pat_inside",
    "pat_outside",
    "pat_bull_run2",
    "pat_bear_run2",
    "pat_marubozu",
    "score_bull_pats",
    "score_bear_pats",
    "side",
]


def build_pattern_tickets(df: pd.DataFrame) -> Tuple[List[dict], Dict[str, int]]:
    """OR first-break tickets with rich candle-pattern features. Decisive T1/SL only."""
    print("\n[C] Building OR-break pattern tickets…", flush=True)
    reasons: Dict[str, int] = {}
    tickets: List[dict] = []
    gaps = {}
    days = list(df.groupby("day", sort=True).groups.keys())
    # gap map
    prev_c = None
    for day, sess in df.groupby("day", sort=True):
        o = float(sess["Open"].iloc[0])
        gaps[day] = ((o - prev_c) / prev_c * 100.0) if prev_c else 0.0
        prev_c = float(sess["Close"].iloc[-1])

    idx_map = {ts: i for i, ts in enumerate(df.index)}
    h_all = df["High"].astype(float).values
    l_all = df["Low"].astype(float).values
    c_all = df["Close"].astype(float).values
    t0 = time.time()
    for di, (day, sess) in enumerate(df.groupby("day", sort=True), 1):
        if di % 150 == 0:
            print(f"    days {di}/{len(days)} tickets={len(tickets)} ({time.time()-t0:.0f}s)", flush=True)
        if len(sess) < OR_BARS + 10:
            continue
        or_hi = float(sess["High"].iloc[:OR_BARS].max())
        or_lo = float(sess["Low"].iloc[:OR_BARS].min())
        or_w = or_hi - or_lo
        if or_w < 15.0:
            reasons["thin_or"] = reasons.get("thin_or", 0) + 1
            continue
        closes = sess["Close"].astype(float).values
        first_up = first_dn = None
        for pos in range(OR_BARS, len(sess)):
            if first_up is None and closes[pos] > or_hi:
                first_up = pos
            if first_dn is None and closes[pos] < or_lo:
                first_dn = pos
            if first_up is not None and first_dn is not None:
                break
        day_open = float(sess["Open"].iloc[0])
        for side, pos in (("BUY", first_up), ("SELL", first_dn)):
            if pos is None:
                continue
            ts = sess.index[pos]
            mins = int(ts.hour * 60 + ts.minute)
            if mins < 10 * 60 or mins > 14 * 60 + 30:
                reasons["clock"] = reasons.get("clock", 0) + 1
                continue
            first = 1.0
            if side == "BUY" and first_dn is not None and first_dn < first_up:
                first = 0.0
            if side == "SELL" and first_up is not None and first_up < first_dn:
                first = 0.0
            if first < 1.0:
                reasons["not_first"] = reasons.get("not_first", 0) + 1
                continue
            # both sides before entry
            up = dn = False
            for p2 in range(OR_BARS, pos + 1):
                if closes[p2] > or_hi:
                    up = True
                if closes[p2] < or_lo:
                    dn = True
            if up and dn:
                reasons["both_sides"] = reasons.get("both_sides", 0) + 1
                continue
            full_i = idx_map[ts]
            entry = float(c_all[full_i])
            bar_o = float(df["Open"].iloc[full_i])
            bar_h = float(h_all[full_i])
            bar_l = float(l_all[full_i])
            bar_rng = bar_h - bar_l
            noise = bar_rng / RISK
            if noise > 1.5:
                reasons["noisy"] = reasons.get("noisy", 0) + 1
                continue
            body = entry - bar_o
            if side == "BUY" and body <= 0:
                reasons["body"] = reasons.get("body", 0) + 1
                continue
            if side == "SELL" and body >= 0:
                reasons["body"] = reasons.get("body", 0) + 1
                continue
            if side == "BUY":
                or_ext = (entry - or_hi) / or_w
            else:
                or_ext = (or_lo - entry) / or_w
            if or_ext > 0.25:
                reasons["chase"] = reasons.get("chase", 0) + 1
                continue
            win, outcome = fwd_t1_sl(h_all, l_all, c_all, full_i, side, RISK)
            if outcome in ("both", "exp"):
                reasons[f"drop_{outcome}"] = reasons.get(f"drop_{outcome}", 0) + 1
                continue
            row = df.iloc[full_i]
            # session context
            sess_so_far = sess.iloc[: pos + 1]
            typ = (sess_so_far["High"] + sess_so_far["Low"] + sess_so_far["Close"]) / 3.0
            vwap = float(typ.mean())
            atr = float((sess_so_far["High"] - sess_so_far["Low"]).tail(14).mean())
            bull_score = float(
                row["hammer"]
                + row["bull_engulf"]
                + row["pin_bull"]
                + row["morning_star"]
                + row["bull_run2"]
                + (row["marubozu"] if row["body"] > 0 else 0)
            )
            bear_score = float(
                row["shooting"]
                + row["bear_engulf"]
                + row["pin_bear"]
                + row["evening_star"]
                + row["bear_run2"]
                + (row["marubozu"] if row["body"] < 0 else 0)
            )
            feat = {
                "ret_1": float(row["ret_1"]) if np.isfinite(row["ret_1"]) else 0.0,
                "ret_3": float(row["ret_3"]) if np.isfinite(row["ret_3"]) else 0.0,
                "ret_6": float(row["ret_6"]) if np.isfinite(row["ret_6"]) else 0.0,
                "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
                "body_frac": float(row["body_frac"]),
                "upper_frac": float(row["upper_frac"]),
                "lower_frac": float(row["lower_frac"]),
                "bar_range_pct": float(bar_rng / max(entry, 1) * 100),
                "or_width": float(or_w),
                "or_ext": float(or_ext),
                "mins_entry": float(mins),
                "first_break": float(first),
                "gap_pct": float(gaps.get(day, 0.0)),
                "session_chg": float((entry - day_open) / day_open * 100),
                "vwap_dist": float((entry - vwap) / entry * 100),
                "atr_ratio": float(bar_rng / max(atr, 1e-6)),
                "noise_vs_sl": float(noise),
                "pat_doji": float(row["doji"]),
                "pat_hammer": float(row["hammer"]),
                "pat_shooting": float(row["shooting"]),
                "pat_bull_engulf": float(row["bull_engulf"]),
                "pat_bear_engulf": float(row["bear_engulf"]),
                "pat_pin_bull": float(row["pin_bull"]),
                "pat_pin_bear": float(row["pin_bear"]),
                "pat_morning": float(row["morning_star"]),
                "pat_evening": float(row["evening_star"]),
                "pat_inside": float(row["inside"]),
                "pat_outside": float(row["outside"]),
                "pat_bull_run2": float(row["bull_run2"]),
                "pat_bear_run2": float(row["bear_run2"]),
                "pat_marubozu": float(row["marubozu"]),
                "score_bull_pats": bull_score,
                "score_bear_pats": bear_score,
                "side": 1.0 if side == "BUY" else -1.0,
            }
            x = [float(feat[k]) for k in FEAT_NAMES]
            tickets.append(
                {
                    "day": day,
                    "hm": base._hm(ts),
                    "decision": side,
                    "entry": entry,
                    "win": bool(win),
                    "outcome": outcome,
                    "or_ext": float(or_ext),
                    "or_width": float(or_w),
                    "mins_entry": mins,
                    "first_break": True,
                    "gap_pct": feat["gap_pct"],
                    "bull_score": bull_score,
                    "bear_score": bear_score,
                    "y": 1 if win else 0,
                    "x": x,
                    "research_only": True,
                    "not_live": True,
                }
            )
            reasons["ok"] = reasons.get("ok", 0) + 1
    print(f"  tickets={len(tickets)} reasons={reasons}", flush=True)
    return tickets, reasons


def train_heads(tickets: List[dict], freeze: str) -> Dict[str, Any]:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import log_loss

    print("\n[D] Training pattern-informed dual heads…", flush=True)
    packs = {}
    ordered = sorted(tickets, key=lambda r: (r["day"], r["hm"], r["decision"]))
    grid = (
        dict(max_depth=2, max_iter=60, min_samples_leaf=30, l2_regularization=1.0, learning_rate=0.05),
        dict(max_depth=3, max_iter=80, min_samples_leaf=40, l2_regularization=1.5, learning_rate=0.04),
        dict(max_depth=3, max_iter=120, min_samples_leaf=50, l2_regularization=2.0, learning_rate=0.03),
        dict(max_depth=4, max_iter=100, min_samples_leaf=40, l2_regularization=1.0, learning_rate=0.04),
    )
    for side in ("BUY", "SELL"):
        rows = [r for r in ordered if r["decision"] == side and r["day"] <= freeze]
        if len(rows) < 80:
            packs[side] = {"available": False, "reason": f"too_few_{len(rows)}"}
            continue
        X = np.asarray([r["x"] for r in rows], dtype=float)
        y = np.asarray([r["y"] for r in rows], dtype=int)
        w = recent_sample_weights([r["day"] for r in rows], half_life_days=365.0)
        cut_sel = int(len(rows) * 0.70)
        cut_cal = int(len(rows) * 0.85)
        if len(set(y[:cut_sel].tolist())) < 2 or len(set(y[cut_cal:].tolist())) < 2:
            packs[side] = {"available": False, "reason": "single_class"}
            continue
        best_params, best_loss = None, None
        for params in grid:
            clf = HistGradientBoostingClassifier(random_state=42, **params)
            clf.fit(X[:cut_sel], y[:cut_sel], sample_weight=w[:cut_sel])
            pred = np.clip(clf.predict_proba(X[cut_sel:cut_cal])[:, 1], 1e-4, 1 - 1e-4)
            loss = float(log_loss(y[cut_sel:cut_cal], pred, labels=[0, 1]))
            if best_loss is None or loss < best_loss:
                best_loss, best_params = loss, params
        held = HistGradientBoostingClassifier(random_state=42, **best_params)
        held.fit(X[:cut_cal], y[:cut_cal], sample_weight=w[:cut_cal])
        raw_cal = held.predict_proba(X[cut_cal:])[:, 1]
        base_clf = HistGradientBoostingClassifier(random_state=42, **best_params)
        base_clf.fit(X, y, sample_weight=w)
        raw_fit = base_clf.predict_proba(X)[:, 1]
        calib_auc = base._auc(y[cut_cal:], raw_cal)
        flip = bool(calib_auc < 0.5)
        if flip:
            calib_auc = 1.0 - calib_auc
        packs[side] = {
            "available": True,
            "side": side,
            "base": base_clf,
            "flip": flip,
            "n_train": len(rows),
            "n_cal": len(rows) - cut_cal,
            "params": dict(best_params),
            "select_log_loss": round(float(best_loss), 4),
            "fit_auc": round(base._auc(y, raw_fit), 3),
            "calib_auc": round(float(calib_auc), 3),
            "feature_names": list(FEAT_NAMES),
            "trainer": "nifty_1m_5y_candle_ml",
            "research_only": True,
            "not_live": True,
        }
        print(
            f"  {side}: n={len(rows)} fit_auc={packs[side]['fit_auc']} "
            f"calib_auc={packs[side]['calib_auc']} flip={flip}",
            flush=True,
        )
    return packs


def score(packs: Dict[str, Any], tickets: List[dict]) -> List[dict]:
    out = []
    for r in tickets:
        p = packs.get(r["decision"]) or {}
        if not p.get("available"):
            continue
        raw = float(p["base"].predict_proba(np.asarray([r["x"]], dtype=float))[0, 1])
        if p.get("flip"):
            raw = 1.0 - raw
        rr = {k: v for k, v in r.items() if k != "x"}
        rr["p_t1"] = round(float(np.clip(raw, 0.05, 0.95)), 4)
        out.append(rr)
    return out


def first_day(rows: List[dict]) -> List[dict]:
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: (x["day"], x["hm"], -(float(x.get("p_t1") or 0)))):
        if r["day"] in seen:
            continue
        seen.add(r["day"])
        out.append(r)
    return out


def agg(rows: List[dict]) -> Dict[str, Any]:
    if not rows:
        return {"n": 0, "wins": 0, "hit_pct": 0.0}
    w = sum(1 for r in rows if r.get("win"))
    return {"n": len(rows), "wins": w, "hit_pct": round(100.0 * w / len(rows), 2)}


def mine_books(scored: List[dict], freeze: str) -> Dict[str, Any]:
    oos = [r for r in scored if r["day"] > freeze]
    books = {}
    for name, pred in (
        ("ALL_DU", lambda r: True),
        ("P55", lambda r: float(r.get("p_t1") or 0) >= 0.55),
        ("P58", lambda r: float(r.get("p_t1") or 0) >= 0.58),
        ("P60", lambda r: float(r.get("p_t1") or 0) >= 0.60),
        ("P62", lambda r: float(r.get("p_t1") or 0) >= 0.62),
        ("P65", lambda r: float(r.get("p_t1") or 0) >= 0.65),
        ("BUY_P55", lambda r: r["decision"] == "BUY" and float(r.get("p_t1") or 0) >= 0.55),
        ("SELL_P55", lambda r: r["decision"] == "SELL" and float(r.get("p_t1") or 0) >= 0.55),
        ("ALIGN_BULL_P55", lambda r: r["decision"] == "BUY" and float(r.get("bull_score") or 0) >= 1 and float(r.get("p_t1") or 0) >= 0.55),
        ("ALIGN_BEAR_P55", lambda r: r["decision"] == "SELL" and float(r.get("bear_score") or 0) >= 1 and float(r.get("p_t1") or 0) >= 0.55),
        ("SELL_mid_P52", lambda r: r["decision"] == "SELL" and 630 <= float(r.get("mins_entry") or 0) <= 720 and float(r.get("p_t1") or 0) >= 0.52),
    ):
        rows = first_day([r for r in oos if pred(r)])
        books[name] = {"rows": rows, **agg(rows)}
    # proven drop-to-95 then prefer 100
    for pmin, bname in ((0.55, "PROVEN_P55"), (0.58, "PROVEN_P58"), (0.60, "PROVEN_P60")):
        cands = first_day(
            sorted(
                [r for r in oos if float(r.get("p_t1") or 0) >= pmin],
                key=lambda r: -float(r.get("p_t1") or 0),
            )
        )
        keep = list(cands)
        while keep and agg(keep)["hit_pct"] < 95.0 and len(keep) > 3:
            losses = [i for i, r in enumerate(keep) if not r.get("win")]
            if not losses:
                break
            worst = min(losses, key=lambda i: float(keep[i].get("p_t1") or 0))
            keep.pop(worst)
        books[bname] = {"rows": keep, **agg(keep)}
    return books


def write_report(meta, sess_sum, pat_study, packs, books, scored) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    oos = [r for r in scored if r["day"] > FREEZE]
    lines = [
        "# NIFTY 1m — 5-year candlestick analysis → ML (RESEARCH ONLY)",
        "",
        "**Not live.**",
        "",
        f"- Window: `{START}` → `{END}` · freeze `{FREEZE}` · ±{RISK:g}",
        f"- Bars: **{meta.get('n_bars')}** · sessions analysed: **{sess_sum.get('n_sessions')}**",
        "",
        "## 1) How sessions open → close (5y)",
        "",
        f"- Up-day rate: **{sess_sum.get('up_day_rate')}%**",
        f"- Mean day return / range: {sess_sum.get('mean_day_ret_pct')}% / {sess_sum.get('mean_range_pct')}%",
        f"- Mean OR width (15×1m): **{sess_sum.get('mean_or_width')}** pts",
        f"- Close near high / low: {sess_sum.get('close_near_high_pct')}% / {sess_sum.get('close_near_low_pct')}%",
        f"- First-hour up → up close: **{sess_sum.get('first_hour_up_then_up_close')}%**",
        f"- First-hour dn → dn close: **{sess_sum.get('first_hour_dn_then_dn_close')}%**",
        f"- OR only-up → up close: **{sess_sum.get('or_only_up_then_up_close')}%**",
        f"- OR only-dn → dn close: **{sess_sum.get('or_only_dn_then_dn_close')}%**",
        f"- OR both-sides days: {sess_sum.get('or_both_sides_pct')}%",
        f"- Gap-up → up close: {sess_sum.get('gap_up_then_up_close')}%",
        f"- Gap-dn → dn close: {sess_sum.get('gap_dn_then_dn_close')}%",
        "",
        "## 2) Candlestick pattern edges (TRAIN only, ±30 T1/SL)",
        "",
        f"Forward horizon: {HORIZON} bars for direction; full path for T1/SL.",
        "",
        "| Pattern | N | BUY T1% | SELL T1% | Best edge vs 50 |",
        "|---|---:|---:|---:|---:|",
    ]
    for p in pat_study.get("patterns") or []:
        lines.append(
            f"| `{p['pattern']}` | {p['n_samples']} | {p['buy_t1_pct']} | {p['sell_t1_pct']} | {p['best_edge']} |"
        )
    top = [p for p in (pat_study.get("patterns") or []) if p.get("best_edge") is not None][:8]
    lines += ["", "### Strongest train patterns", ""]
    for p in top:
        lines.append(
            f"- **{p['pattern']}** → {p['best_side']} edge {p['best_edge']} pts "
            f"(buy {p['buy_t1_pct']}% / sell {p['sell_t1_pct']}%)"
        )
    lines += ["", "## 3) Pattern-informed ML (OOS after freeze)", "", "### Heads", ""]
    for side in ("BUY", "SELL"):
        h = packs.get(side) or {}
        if h.get("available"):
            lines.append(
                f"- **{side}**: n={h.get('n_train')} fit_auc={h.get('fit_auc')} "
                f"calib_auc={h.get('calib_auc')} flip={h.get('flip')}"
            )
        else:
            lines.append(f"- **{side}**: unavailable ({h.get('reason')})")
    lines += [
        "",
        f"- Clean pattern tickets: **{meta.get('n_tickets')}** · OOS scored: **{len(oos)}** "
        f"({agg(oos).get('hit_pct')}% raw)",
        "",
        "### OOS books (day-unique)",
        "",
        "| Book | N | Hit% |",
        "|---|---:|---:|",
    ]
    for k, v in books.items():
        lines.append(f"| `{k}` | {v.get('n')} | {v.get('hit_pct')} |")
    # best book
    usable = [(k, v) for k, v in books.items() if v.get("n", 0) >= 5]
    usable.sort(key=lambda kv: (kv[1]["hit_pct"], kv[1]["n"]), reverse=True)
    lines += ["", "## Research pick", ""]
    if usable:
        k, v = usable[0]
        lines.append(
            f"**Best OOS book (≥5 calls):** `{k}` · **{v['n']} @ {v['hit_pct']}%**"
        )
        lines.append("")
        lines.append("| Day | HM | Side | p | Win |")
        lines.append("|---|---|---|---:|:---:|")
        for r in (v.get("rows") or [])[:25]:
            lines.append(
                f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | "
                f"{r.get('p_t1')} | {'Y' if r.get('win') else 'N'} |"
            )
    lines += [
        "",
        "## Policy",
        "",
        f"- Pack: `{PACK}`",
        "- research_only · not_live — do not wire without promote plan",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "meta": meta,
                "session_summary": sess_sum,
                "pattern_study": pat_study,
                "heads": {
                    k: {kk: vv for kk, vv in (v or {}).items() if kk != "base"}
                    for k, v in packs.items()
                },
                "books": {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in books.items()},
                "oos_agg": agg(oos),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT_MD}", flush=True)


def save_pack(packs, tickets, scored, books, meta) -> None:
    import joblib

    PACK.mkdir(parents=True, exist_ok=True)
    for side, p in packs.items():
        if not p.get("available"):
            continue
        joblib.dump(
            {"base": p["base"], "flip": p["flip"], "feature_names": FEAT_NAMES, "meta": {k: v for k, v in p.items() if k != "base"}},
            PACK / f"head_{side.lower()}.joblib",
        )
    slim = [{k: v for k, v in r.items() if k != "x"} for r in tickets]
    (PACK / "tickets.json").write_text(json.dumps(slim[:5000], indent=2, default=str), encoding="utf-8")
    (PACK / "pack_meta.json").write_text(
        json.dumps(
            {
                "meta": meta,
                "books": {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in books.items()},
                "n_scored": len(scored),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  pack → {PACK}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · 5Y CANDLESTICK ANALYSIS → ML · RESEARCH ONLY", flush=True)
    print(f"{START} → {END} · freeze {FREEZE}", flush=True)
    print("=" * 60, flush=True)

    raw = base.load_existing_1m()
    raw = raw[
        (raw.index >= pd.Timestamp(START, tz="Asia/Kolkata"))
        & (raw.index <= pd.Timestamp(f"{END} 23:59:59", tz="Asia/Kolkata"))
    ]
    if raw.empty:
        print("FAIL: no bars", flush=True)
        return 1
    print(f"tape bars={len(raw)} {raw.index.min()} → {raw.index.max()}", flush=True)

    print("\n[0] Computing candle columns…", flush=True)
    df = add_candle_cols(raw)
    print(f"  pattern cols ready · days={df['day'].nunique()}", flush=True)

    sess = analyse_sessions(df)
    pat = analyse_patterns(df, FREEZE)
    tickets, reasons = build_pattern_tickets(df)
    if len(tickets) < 80:
        print("FAIL: too few tickets", flush=True)
        return 1

    packs = train_heads(tickets, FREEZE)
    scored = score(packs, tickets)
    books = mine_books(scored, FREEZE)
    for k, v in books.items():
        print(f"  book {k}: n={v['n']} hit={v['hit_pct']}%", flush=True)

    meta = {
        "n_bars": len(df),
        "n_days": int(df["day"].nunique()),
        "n_tickets": len(tickets),
        "ticket_reasons": reasons,
        "freeze": FREEZE,
        "start": START,
        "end": END,
        "research_only": True,
        "not_live": True,
    }
    save_pack(packs, tickets, scored, books, meta)
    write_report(meta, sess["summary"], pat, packs, books, scored)
    print("\nDONE · research only", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
