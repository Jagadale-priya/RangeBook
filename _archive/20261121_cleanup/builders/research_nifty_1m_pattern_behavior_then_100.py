"""RESEARCH ONLY — Pattern behavior first, then clean multi-call 100% (SL≤20).

Phase A — For every textbook pattern completion on NIFTY 1m:
  1) BEFORE: how price/RSI/body approached the pattern
  2) AT: candle geometry (body, wicks, range)
  3) AFTER: MAE/MFE path, direction persistence, time-to-+5/+10

Phase B — From clean behavior slices, hunt multi-call books @ 100%
  both windows with SL ≤ 20 and T1 ≥ 8–10.

  python -u prod_live/tests/builders/research_nifty_1m_pattern_behavior_then_100.py
"""
from __future__ import annotations

import json
import pickle
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
import research_nifty_1m_chart_only_100 as co  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_daily_must_100 as dm  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_pattern_behavior_100"
REPORT_MD = OUT / "NIFTY_1M_PATTERN_BEHAVIOR_THEN_100.md"
REPORT_JSON = OUT / "NIFTY_1M_PATTERN_BEHAVIOR_THEN_100.json"
SL_MAX = 20.0

PATTERNS = list(dm.PRIORITY)


def add_rsi(df: pd.DataFrame) -> pd.DataFrame:
    c = df["Close"].astype(float)
    d = c.diff()
    up = d.clip(lower=0).rolling(14).mean()
    down = (-d.clip(upper=0)).rolling(14).mean()
    out = df.copy()
    out["rsi_14"] = (100 - (100 / (1 + up / down.replace(0, np.nan)))).fillna(50.0)
    return out


def side_for(primary: str, body: float) -> Optional[str]:
    if primary in tb.BULLISH:
        return "BUY"
    if primary in tb.BEARISH:
        return "SELL"
    if body > 0:
        return "BUY"
    if body < 0:
        return "SELL"
    return None


def path_stats(h, l, c, i: int, side: str, max_bars: int = 120) -> dict:
    """After-entry path behavior."""
    entry = float(c[i])
    mae = mfe = 0.0
    t_mae5 = t_mfe5 = t_mfe8 = t_mfe10 = None
    first_dir = None  # which threshold hit first: fav5 or adv5
    end = min(len(c), i + 1 + max_bars)
    for j in range(i + 1, end):
        hi, lo = float(h[j]), float(l[j])
        if side == "BUY":
            adv = entry - lo
            fav = hi - entry
        else:
            adv = hi - entry
            fav = entry - lo
        mae = max(mae, adv)
        mfe = max(mfe, fav)
        bar = j - i
        if t_mae5 is None and adv >= 5:
            t_mae5 = bar
        if t_mfe5 is None and fav >= 5:
            t_mfe5 = bar
        if t_mfe8 is None and fav >= 8:
            t_mfe8 = bar
        if t_mfe10 is None and fav >= 10:
            t_mfe10 = bar
        if first_dir is None:
            if fav >= 5 and adv >= 5:
                first_dir = "both5"
            elif fav >= 5:
                first_dir = "fav5"
            elif adv >= 5:
                first_dir = "adv5"
    # SL20 / T1 path outcomes
    outcomes = {}
    for t1 in (5.0, 8.0, 10.0):
        win, out = co.path_hit(h, l, c, i, side, SL_MAX, t1)
        outcomes[f"sl20_t{int(t1)}"] = "win" if (win and out == "t1") else out
    return {
        "mae": mae,
        "mfe": mfe,
        "t_mae5": t_mae5,
        "t_mfe5": t_mfe5,
        "t_mfe8": t_mfe8,
        "t_mfe10": t_mfe10,
        "first5": first_dir or "neither",
        **outcomes,
    }


def pre_context(sess: pd.DataFrame, pos: int, side: str, day_open: float) -> dict:
    """How market behaved BEFORE pattern completed."""
    row = sess.iloc[pos]
    entry = float(row["Close"])
    look = sess.iloc[max(0, pos - 15) : pos]  # bars before signal (not including)
    if len(look) < 3:
        return {
            "pre_chg_5": 0.0,
            "pre_chg_15": 0.0,
            "pre_dir": "flat",
            "pre_body_sum": 0.0,
            "pre_range_sum": 0.0,
            "pre_rsi_delta": 0.0,
            "session_chg": 0.0,
            "align_session": 0,
        }
    c5 = look.iloc[-5:] if len(look) >= 5 else look
    pre_chg_5 = float(c5["Close"].iloc[-1] - c5["Open"].iloc[0])
    pre_chg_15 = float(look["Close"].iloc[-1] - look["Open"].iloc[0])
    bodies = (look["Close"].astype(float) - look["Open"].astype(float)).values
    ranges = (look["High"].astype(float) - look["Low"].astype(float)).values
    rsi_now = float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0
    rsi_ago = float(look["rsi_14"].iloc[0]) if np.isfinite(look["rsi_14"].iloc[0]) else 50.0
    if abs(pre_chg_5) < 3:
        pre_dir = "flat"
    elif pre_chg_5 > 0:
        pre_dir = "up"
    else:
        pre_dir = "down"
    # continuation vs reversal vs signal side
    if side == "BUY":
        regime = "continuation" if pre_chg_5 > 3 else ("reversal" if pre_chg_5 < -3 else "balanced")
    else:
        regime = "continuation" if pre_chg_5 < -3 else ("reversal" if pre_chg_5 > 3 else "balanced")
    session_chg = entry - day_open
    align = 1 if (side == "BUY" and session_chg > 0) or (side == "SELL" and session_chg < 0) else 0
    return {
        "pre_chg_5": pre_chg_5,
        "pre_chg_15": pre_chg_15,
        "pre_dir": pre_dir,
        "pre_regime": regime,
        "pre_body_sum": float(np.sum(bodies)),
        "pre_range_sum": float(np.sum(ranges)),
        "pre_rsi_delta": rsi_now - rsi_ago,
        "session_chg": session_chg,
        "align_session": align,
        "rsi_14": rsi_now,
    }


def collect_events(df: pd.DataFrame, day_lo: str, day_hi: str) -> List[dict]:
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(df.index)}
    events = []
    days = [d for d in df["day"].unique() if day_lo <= d <= day_hi]
    t0 = time.time()
    for di, day in enumerate(days, 1):
        if di % 50 == 0:
            print(f"    events {di}/{len(days)} n={len(events)} ({time.time()-t0:.0f}s)", flush=True)
        sess = df[df["day"] == day]
        if len(sess) < 40:
            continue
        day_open = float(sess["Open"].iloc[0])
        for pos in range(5, len(sess)):
            row = sess.iloc[pos]
            mins = int(row["mins"])
            if mins < 560 or mins > 900:
                continue
            body = float(row["Close"]) - float(row["Open"])
            hits = [p for p in PATTERNS if p in row.index and int(row[p]) == 1]
            if not hits:
                continue
            # one event per pattern tag on bar (primary = highest priority)
            primary = hits[0]
            side = side_for(primary, body)
            if side is None:
                continue
            if side == "BUY" and body <= 0:
                continue
            if side == "SELL" and body >= 0:
                continue
            o, cl = float(row["Open"]), float(row["Close"])
            hi, lo = float(row["High"]), float(row["Low"])
            body_abs = abs(cl - o)
            cr = max(hi - lo, 0.5)
            atr = max(float(row["atr14"]) if np.isfinite(row["atr14"]) else 8.0, 3.0)
            if side == "BUY":
                sl_candle = max(cl - lo, 0.5)
            else:
                sl_candle = max(hi - cl, 0.5)
            full_i = idx_map[sess.index[pos]]
            pre = pre_context(sess, pos, side, day_open)
            post = path_stats(h, l, c, full_i, side)
            events.append(
                {
                    "day": day,
                    "hm": row["hm"],
                    "mins": mins,
                    "clock": co.clock_bucket(mins),
                    "decision": side,
                    "primary": primary,
                    "patterns": hits[:4],
                    "entry": cl,
                    "atr": atr,
                    "body_abs": body_abs,
                    "body_frac": float(row["body_frac"]),
                    "candle_range": cr,
                    "upper_wick": hi - max(o, cl),
                    "lower_wick": min(o, cl) - lo,
                    "sl_candle": sl_candle,
                    "full_i": full_i,
                    **pre,
                    **post,
                }
            )
    return events


def summarize_behavior(events: List[dict]) -> dict:
    """Per-pattern before/after behavior tables."""
    by_pat: Dict[str, List[dict]] = defaultdict(list)
    for e in events:
        by_pat[e["primary"]].append(e)

    rows = []
    for pat, xs in sorted(by_pat.items(), key=lambda kv: -len(kv[1])):
        n = len(xs)
        if n < 8:
            continue
        fav5 = sum(1 for e in xs if e["first5"] == "fav5") / n * 100
        adv5 = sum(1 for e in xs if e["first5"] == "adv5") / n * 100
        win20_8 = sum(1 for e in xs if e["sl20_t8"] == "win") / n * 100
        win20_10 = sum(1 for e in xs if e["sl20_t10"] == "win") / n * 100
        # clean slice: continuation + session align + tight candle
        clean = [
            e
            for e in xs
            if e["pre_regime"] == "continuation"
            and e["align_session"] == 1
            and e["sl_candle"] <= 15
            and e["body_frac"] >= 0.45
        ]
        clean_n = len(clean)
        clean_w8 = (
            sum(1 for e in clean if e["sl20_t8"] == "win") / clean_n * 100 if clean_n else 0.0
        )
        rows.append(
            {
                "pattern": pat,
                "n": n,
                "avg_mae": round(float(np.mean([e["mae"] for e in xs])), 2),
                "avg_mfe": round(float(np.mean([e["mfe"] for e in xs])), 2),
                "med_mae": round(float(np.median([e["mae"] for e in xs])), 2),
                "med_mfe": round(float(np.median([e["mfe"] for e in xs])), 2),
                "pct_fav5_first": round(fav5, 1),
                "pct_adv5_first": round(adv5, 1),
                "pct_win_sl20_t8": round(win20_8, 1),
                "pct_win_sl20_t10": round(win20_10, 1),
                "pct_continuation": round(
                    100.0 * sum(1 for e in xs if e["pre_regime"] == "continuation") / n, 1
                ),
                "pct_reversal": round(
                    100.0 * sum(1 for e in xs if e["pre_regime"] == "reversal") / n, 1
                ),
                "clean_n": clean_n,
                "clean_win_sl20_t8": round(clean_w8, 1),
                "avg_pre_chg5": round(float(np.mean([e["pre_chg_5"] for e in xs])), 2),
                "avg_rsi": round(float(np.mean([e["rsi_14"] for e in xs])), 1),
            }
        )
    rows.sort(key=lambda r: (-r["clean_win_sl20_t8"], -r["pct_win_sl20_t8"], -r["n"]))
    return {"by_pattern": rows}


def slice_events(events: List[dict], spec: dict) -> List[dict]:
    out = []
    for e in events:
        if spec.get("primaries") and e["primary"] not in spec["primaries"]:
            continue
        if spec.get("side") and e["decision"] != spec["side"]:
            continue
        if spec.get("regime") and e["pre_regime"] != spec["regime"]:
            continue
        if spec.get("align") is not None and e["align_session"] != spec["align"]:
            continue
        if spec.get("clocks") and e["clock"] not in spec["clocks"]:
            continue
        if spec.get("min_body") is not None and e["body_frac"] < spec["min_body"]:
            continue
        if spec.get("max_sl_candle") is not None and e["sl_candle"] > spec["max_sl_candle"]:
            continue
        if spec.get("rsi_lo") is not None and e["rsi_14"] < spec["rsi_lo"]:
            continue
        if spec.get("rsi_hi") is not None and e["rsi_14"] > spec["rsi_hi"]:
            continue
        if spec.get("first5") and e["first5"] != spec["first5"]:
            continue  # only for analysis; NOT for live filters
        out.append(e)
    return out


def eval_book(events: List[dict], h, l, c, sl_mode: str, params: dict) -> dict:
    """Day-unique first call; SL≤20."""
    rows = []
    used_days = set()
    for e in sorted(events, key=lambda x: (x["day"], x["mins"])):
        if e["day"] in used_days:
            continue
        if sl_mode == "fixed":
            sl = float(params["sl"])
            t1 = float(params["t1"])
        elif sl_mode == "candle_cap":
            sl = min(max(params["sl_k"] * e["sl_candle"], 4.0), SL_MAX)
            t1 = max(float(params["t1"]), 5.0)
        elif sl_mode == "atr_cap":
            sl = min(max(params["atr_k"] * e["atr"], 4.0), SL_MAX)
            t1 = max(float(params["t1"]), 5.0)
        else:
            sl, t1 = 15.0, 8.0
        if sl > SL_MAX + 1e-9:
            continue
        win, outcome = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
        if outcome in ("bad", "both"):
            win = False
        rows.append(
            {
                "day": e["day"],
                "hm": e["hm"],
                "decision": e["decision"],
                "primary": e["primary"],
                "entry": e["entry"],
                "sl": round(sl, 2),
                "t1": round(t1, 2),
                "win": bool(win),
                "outcome": outcome,
                "pre_regime": e["pre_regime"],
                "align_session": e["align_session"],
            }
        )
        used_days.add(e["day"])
    n = len(rows)
    wins = sum(1 for r in rows if r["win"])
    return {
        "n": n,
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else 0.0,
        "avg_sl": round(float(np.mean([r["sl"] for r in rows])), 2) if rows else 0,
        "avg_t1": round(float(np.mean([r["t1"] for r in rows])), 2) if rows else 0,
        "max_sl": round(float(np.max([r["sl"] for r in rows])), 2) if rows else 0,
        "miss_days": [r["day"] for r in rows if not r["win"]],
        "calls": rows,
    }


def eval_multi(events: List[dict], h, l, c, sl_mode: str, params: dict, gap_mins: int = 15) -> dict:
    """Multiple calls/day allowed with min gap; still SL≤20."""
    rows = []
    last_mins_by_day: Dict[str, int] = {}
    for e in sorted(events, key=lambda x: (x["day"], x["mins"])):
        prev = last_mins_by_day.get(e["day"])
        if prev is not None and e["mins"] - prev < gap_mins:
            continue
        if sl_mode == "fixed":
            sl = float(params["sl"])
            t1 = float(params["t1"])
        elif sl_mode == "candle_cap":
            sl = min(max(params["sl_k"] * e["sl_candle"], 4.0), SL_MAX)
            t1 = max(float(params["t1"]), 5.0)
        elif sl_mode == "atr_cap":
            sl = min(max(params["atr_k"] * e["atr"], 4.0), SL_MAX)
            t1 = max(float(params["t1"]), 5.0)
        else:
            continue
        if sl > SL_MAX + 1e-9:
            continue
        win, outcome = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
        if outcome in ("bad", "both"):
            win = False
        rows.append(
            {
                "day": e["day"],
                "hm": e["hm"],
                "decision": e["decision"],
                "primary": e["primary"],
                "entry": e["entry"],
                "sl": round(sl, 2),
                "t1": round(t1, 2),
                "win": bool(win),
                "outcome": outcome,
            }
        )
        last_mins_by_day[e["day"]] = e["mins"]
    n = len(rows)
    wins = sum(1 for r in rows if r["win"])
    n_days = len({r["day"] for r in rows})
    return {
        "n": n,
        "n_days": n_days,
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else 0.0,
        "avg_sl": round(float(np.mean([r["sl"] for r in rows])), 2) if rows else 0,
        "avg_t1": round(float(np.mean([r["t1"] for r in rows])), 2) if rows else 0,
        "max_sl": round(float(np.max([r["sl"] for r in rows])), 2) if rows else 0,
        "miss_days": sorted({r["day"] for r in rows if not r["win"]}),
        "calls": rows,
    }


def _precompute_fixed_wins(events: List[dict], h, l, c) -> None:
    """Attach win flags for fixed SL/T1 under SL≤20 (mutates events)."""
    for e in events:
        for sl, t1 in product([20.0, 15.0, 12.0, 10.0], [8.0, 10.0]):
            key = f"w_{int(sl)}_{int(t1)}"
            if key in e:
                continue
            # reuse path_stats outcomes when sl==20
            if sl == 20.0 and t1 == 8.0:
                e[key] = e.get("sl20_t8") == "win"
            elif sl == 20.0 and t1 == 10.0:
                e[key] = e.get("sl20_t10") == "win"
            else:
                win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
                e[key] = bool(win) and out == "t1"


def eval_book_fast(events: List[dict], sl: float, t1: float) -> dict:
    """Day-unique using precomputed fixed wins."""
    key = f"w_{int(sl)}_{int(t1)}"
    rows = []
    used = set()
    for e in sorted(events, key=lambda x: (x["day"], x["mins"])):
        if e["day"] in used:
            continue
        win = bool(e.get(key))
        rows.append(
            {
                "day": e["day"],
                "hm": e["hm"],
                "decision": e["decision"],
                "primary": e["primary"],
                "entry": e["entry"],
                "sl": sl,
                "t1": t1,
                "win": win,
                "pre_regime": e["pre_regime"],
                "align_session": e["align_session"],
            }
        )
        used.add(e["day"])
    n = len(rows)
    wins = sum(1 for r in rows if r["win"])
    return {
        "n": n,
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else 0.0,
        "avg_sl": sl,
        "avg_t1": t1,
        "max_sl": sl,
        "miss_days": [r["day"] for r in rows if not r["win"]],
        "calls": rows,
    }


def eval_multi_fast(events: List[dict], sl: float, t1: float, gap_mins: int = 20) -> dict:
    key = f"w_{int(sl)}_{int(t1)}"
    rows = []
    last: Dict[str, int] = {}
    for e in sorted(events, key=lambda x: (x["day"], x["mins"])):
        prev = last.get(e["day"])
        if prev is not None and e["mins"] - prev < gap_mins:
            continue
        win = bool(e.get(key))
        rows.append(
            {
                "day": e["day"],
                "hm": e["hm"],
                "decision": e["decision"],
                "primary": e["primary"],
                "entry": e["entry"],
                "sl": sl,
                "t1": t1,
                "win": win,
            }
        )
        last[e["day"]] = e["mins"]
    n = len(rows)
    wins = sum(1 for r in rows if r["win"])
    return {
        "n": n,
        "n_days": len({r["day"] for r in rows}),
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else 0.0,
        "avg_sl": sl,
        "avg_t1": t1,
        "max_sl": sl,
        "miss_days": sorted({r["day"] for r in rows if not r["win"]}),
        "calls": rows,
    }


def hunt_100(cal_ev, test_ev, h, l, c, behavior_top: List[str]) -> dict:
    print("\n[B] Hunt multi-call 100% from clean behavior slices (fast)…", flush=True)
    print("  precompute fixed SL/T1 wins…", flush=True)
    _precompute_fixed_wins(cal_ev, h, l, c)
    _precompute_fixed_wins(test_ev, h, l, c)

    base_pats = behavior_top[:8]
    groups = [
        base_pats[:3],
        base_pats[:5],
        ["morning_star", "evening_star"],
        ["falling_3_methods", "rising_3_methods"],
        ["three_crows", "three_soldiers"],
        ["hanging_man", "shooting_star"],
        ["hanging_man", "shooting_star", "hammer", "inv_hammer"],
        ["three_outside_dn", "three_outside_up"],
        ["bear_engulf", "bull_engulf"],
        ["belt_bear", "belt_bull", "marubozu_bear", "marubozu_bull"],
    ]
    # focused clean filters from Phase A
    filter_grid = []
    for pats in groups:
        for regime, align, min_body, max_slc, clocks, rsi in product(
            ["continuation", None],
            [1, None],
            [0.45, 0.55, None],
            [12.0, 15.0, 20.0],
            [None, ["early"], ["early", "morning"]],
            [(None, None), (20, 55), (25, 50), (40, 80)],
        ):
            filter_grid.append(
                {
                    "primaries": pats,
                    "regime": regime,
                    "align": align,
                    "min_body": min_body,
                    "max_sl_candle": max_slc,
                    "clocks": clocks,
                    "rsi_lo": rsi[0],
                    "rsi_hi": rsi[1],
                    "side": None,
                }
            )
        if set(pats) <= {"hanging_man", "shooting_star", "hammer", "inv_hammer"} or pats == [
            "hanging_man",
            "shooting_star",
        ]:
            for side in ("SELL", "BUY"):
                filter_grid.append(
                    {
                        "primaries": pats,
                        "regime": "continuation",
                        "align": 1,
                        "min_body": 0.45,
                        "max_sl_candle": 15.0,
                        "clocks": ["early", "morning"],
                        "rsi_lo": 20,
                        "rsi_hi": 55 if side == "SELL" else 80,
                        "side": side,
                    }
                )

    brackets = list(product([20.0, 15.0, 12.0, 10.0], [8.0, 10.0]))
    perfect_day, perfect_multi, near = [], [], []
    t0 = time.time()
    n_specs = 0

    for spec in filter_grid:
        cal_s = slice_events(cal_ev, spec)
        test_s = slice_events(test_ev, spec)
        if len(cal_s) < 5 or len(test_s) < 3:
            continue
        for sl, t1 in brackets:
            n_specs += 1
            if n_specs % 500 == 0:
                print(
                    f"    {n_specs} p_day={len(perfect_day)} p_multi={len(perfect_multi)} ({time.time()-t0:.0f}s)",
                    flush=True,
                )
            lab = f"fix{sl}_{t1}"
            a = eval_book_fast(cal_s, sl, t1)
            t = eval_book_fast(test_s, sl, t1)
            if a["n"] < 3 or t["n"] < 2:
                continue
            filt = {k: v for k, v in spec.items() if v is not None}
            rec = {
                "mode": "day_unique",
                "bracket": lab,
                "sl_mode": "fixed",
                "params": {"sl": sl, "t1": t1},
                "filter": filt,
                "calibrate": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl")},
                "last3m": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl")},
                "cal_miss": a["miss_days"][:6],
                "l3m_miss": t["miss_days"][:6],
                "last3m_calls": t["calls"],
            }
            if a["hit_pct"] >= 100 - 1e-9 and t["hit_pct"] >= 100 - 1e-9:
                perfect_day.append(rec)
            elif t["hit_pct"] >= 90 and a["hit_pct"] >= 85 and t["n"] >= 3:
                near.append(rec)

            am = eval_multi_fast(cal_s, sl, t1, gap_mins=20)
            tm = eval_multi_fast(test_s, sl, t1, gap_mins=20)
            if am["n"] < 5 or tm["n"] < 3:
                continue
            recm = {
                "mode": "multi",
                "bracket": lab,
                "sl_mode": "fixed",
                "params": {"sl": sl, "t1": t1},
                "filter": filt,
                "calibrate": {
                    k: am[k] for k in ("n", "n_days", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl")
                },
                "last3m": {
                    k: tm[k] for k in ("n", "n_days", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl")
                },
                "cal_miss": am["miss_days"][:6],
                "l3m_miss": tm["miss_days"][:6],
                "last3m_calls": tm["calls"],
            }
            if am["hit_pct"] >= 100 - 1e-9 and tm["hit_pct"] >= 100 - 1e-9:
                perfect_multi.append(recm)
            elif tm["hit_pct"] >= 90 and am["hit_pct"] >= 85 and tm["n"] >= 4:
                near.append(recm)

    def rank(r):
        return (
            -r["last3m"]["n"],
            -r["calibrate"]["n"],
            r["last3m"]["avg_sl"] / max(r["last3m"]["avg_t1"], 1e-6),
        )

    perfect_day.sort(key=rank)
    perfect_multi.sort(key=rank)
    near.sort(
        key=lambda r: (-r["last3m"]["hit_pct"], -r["last3m"]["n"], -r["calibrate"]["hit_pct"])
    )
    print(
        f"  specs={n_specs} perfect_day={len(perfect_day)} perfect_multi={len(perfect_multi)} "
        f"near={len(near)} ({time.time()-t0:.0f}s)",
        flush=True,
    )
    return {
        "perfect_day": perfect_day[:25],
        "perfect_multi": perfect_multi[:25],
        "near": near[:25],
    }


def write_report(meta, behavior, hunt):
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NIFTY 1m — pattern **behavior** → clean 100% calls (SL≤20)",
        "",
        "**Not live.** Research order: understand how patterns form and how price moves after, "
        "then extract clean multi-call books at 100%.",
        "",
        f"- Calibrate `{meta['cal_lo']}`→`{meta['cal_hi']}`",
        f"- Last3m `{meta['test_lo']}`→`{meta['test_hi']}`",
        f"- Events: cal **{meta['n_cal_events']}** · last3m **{meta['n_test_events']}**",
        "",
        "## Phase A — How patterns behave",
        "",
        "For each completion we measure:",
        "",
        "1. **Before** — 5/15-bar drift, continuation vs reversal vs signal side, session align, RSI",
        "2. **At** — body/wicks/range, candle stop distance",
        "3. **After** — MAE/MFE, who hits ±5 first, win-rate with **SL≤20 / T1 8–10**",
        "",
        "### Pattern leaderboard (calibrate, sorted by clean SL20/T1=8 win%)",
        "",
        "| Pattern | N | Fav5% | Adv5% | Win SL20/T8 | Clean N | Clean Win% | Med MAE/MFE |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in behavior["by_pattern"][:20]:
        lines.append(
            f"| {r['pattern']} | {r['n']} | {r['pct_fav5_first']} | {r['pct_adv5_first']} | "
            f"{r['pct_win_sl20_t8']} | {r['clean_n']} | {r['clean_win_sl20_t8']} | "
            f"{r['med_mae']}/{r['med_mfe']} |"
        )

    lines += [
        "",
        "### What “clean” means (non-lookahead)",
        "",
        "- Pre-regime = **continuation** (last 5 bars already moved with signal side)",
        "- Session open→entry aligned with side",
        "- Candle stop distance ≤ 15 pts, body_frac ≥ 0.45",
        "",
        "## Phase B — 100% books (SL≤20, T1≥8)",
        "",
    ]

    champ = meta.get("champion")
    if champ:
        c, t = champ["calibrate"], champ["last3m"]
        lines += [
            f"### Champion: `{champ['mode']}` / `{champ['bracket']}`",
            "",
            f"- Filter: `{champ.get('filter')}`",
            f"- Calibrate: **{c['n']} @ {c['hit_pct']}%** · SL/T1 {c['avg_sl']}/{c['avg_t1']} · maxSL {c.get('max_sl')}",
            f"- Last3m: **{t['n']} @ {t['hit_pct']}%** · SL/T1 {t['avg_sl']}/{t['avg_t1']} · maxSL {t.get('max_sl')}",
            "",
        ]
        if c["hit_pct"] >= 100 and t["hit_pct"] >= 100:
            lines.append("**ACHIEVED 100% both windows** under SL≤20.")
        lines += [
            "",
            "| Day | HM | Side | Primary | SL | T1 | Win |",
            "|---|---|---|---|---:|---:|:---:|",
        ]
        for r in (champ.get("last3m_calls") or [])[:60]:
            lines.append(
                f"| {r['day']} | {r['hm']} | {r['decision']} | {r.get('primary')} | "
                f"{r['sl']} | {r['t1']} | {'Y' if r['win'] else 'N'} |"
            )
        lines.append("")

    lines += ["### Perfect day-unique (1st call/day)", ""]
    for p in (hunt.get("perfect_day") or [])[:8]:
        lines.append(
            f"- `{p['bracket']}` · {p.get('filter')} · "
            f"cal {p['calibrate']['n']}@100% · l3m {p['last3m']['n']}@100% · "
            f"SL/T1 {p['last3m']['avg_sl']}/{p['last3m']['avg_t1']}"
        )
    if not hunt.get("perfect_day"):
        lines.append("- none")

    lines += ["", "### Perfect multi-call (gap ≥20m)", ""]
    for p in (hunt.get("perfect_multi") or [])[:8]:
        lines.append(
            f"- `{p['bracket']}` · {p.get('filter')} · "
            f"cal {p['calibrate']['n']} calls/{p['calibrate'].get('n_days')}d @100% · "
            f"l3m {p['last3m']['n']} calls/{p['last3m'].get('n_days')}d @100% · "
            f"SL/T1 {p['last3m']['avg_sl']}/{p['last3m']['avg_t1']}"
        )
    if not hunt.get("perfect_multi"):
        lines.append("- none")

    lines += ["", "### Near", ""]
    for n in (hunt.get("near") or [])[:8]:
        lines.append(
            f"- `{n['mode']}` `{n['bracket']}` · cal {n['calibrate']['n']}@{n['calibrate']['hit_pct']}% · "
            f"l3m {n['last3m']['n']}@{n['last3m']['hit_pct']}% · filter={n.get('filter')}"
        )

    lines += [
        "",
        "## Policy",
        "",
        f"- Pack: `{PACK}`",
        "- research_only · not_live · behavior-first · SL≤20 · no OR-break",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "meta": {k: v for k, v in meta.items() if k != "champion"},
                "champion": {k: v for k, v in (champ or {}).items() if k != "cal_calls"},
                "behavior_top": behavior["by_pattern"][:25],
                "perfect_day": [
                    {k: v for k, v in r.items() if k != "last3m_calls"}
                    for r in (hunt.get("perfect_day") or [])[:12]
                ],
                "perfect_multi": [
                    {k: v for k, v in r.items() if k != "last3m_calls"}
                    for r in (hunt.get("perfect_multi") or [])[:12]
                ],
                "near": [
                    {k: v for k, v in r.items() if k != "last3m_calls"}
                    for r in (hunt.get("near") or [])[:12]
                ],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT_MD}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · PATTERN BEHAVIOR → 100% clean calls", flush=True)
    print("=" * 60, flush=True)

    raw = base.load_existing_1m()
    end = raw.index.max()
    test_hi = end.strftime("%Y-%m-%d")
    test_lo_ts = end - pd.Timedelta(days=92)
    test_lo = test_lo_ts.strftime("%Y-%m-%d")
    cal_hi = (test_lo_ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    cal_lo = (test_lo_ts - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    print(f"calibrate {cal_lo}→{cal_hi} · last3m {test_lo}→{test_hi}", flush=True)

    raw = raw[raw.index >= pd.Timestamp(cal_lo, tz="Asia/Kolkata")]
    print("\n[A1] Detect textbook patterns…", flush=True)
    df = tb.detect_textbook(raw)
    df = add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values

    print("\n[A2] Collect pattern events + before/after path…", flush=True)
    cache = PACK / f"events_cache_{cal_lo}_{test_hi}.pkl"
    PACK.mkdir(parents=True, exist_ok=True)
    if cache.exists():
        print(f"  load cache {cache.name}…", flush=True)
        with cache.open("rb") as f:
            blob = pickle.load(f)
        cal_ev, test_ev = blob["cal"], blob["test"]
    else:
        cal_ev = collect_events(df, cal_lo, cal_hi)
        test_ev = collect_events(df, test_lo, test_hi)
        with cache.open("wb") as f:
            pickle.dump({"cal": cal_ev, "test": test_ev}, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"  wrote cache {cache.name}", flush=True)
    print(f"  cal events={len(cal_ev)} · last3m events={len(test_ev)}", flush=True)

    print("\n[A3] Summarize behavior…", flush=True)
    behavior = summarize_behavior(cal_ev)
    top = [r["pattern"] for r in behavior["by_pattern"][:12]]
    print("  top clean patterns:", top[:8], flush=True)
    for r in behavior["by_pattern"][:8]:
        print(
            f"    {r['pattern']}: n={r['n']} win8={r['pct_win_sl20_t8']}% "
            f"clean={r['clean_n']}@{r['clean_win_sl20_t8']}% fav5={r['pct_fav5_first']}%",
            flush=True,
        )

    hunt = hunt_100(cal_ev, test_ev, h, l, c, top)

    champion = None
    for bucket in ("perfect_multi", "perfect_day"):
        for rec in hunt.get(bucket) or []:
            if champion is None or rec["last3m"]["n"] > champion["last3m"]["n"]:
                champion = rec
            elif rec["last3m"]["n"] == champion["last3m"]["n"] and rec["calibrate"]["n"] > champion["calibrate"]["n"]:
                champion = rec
    if champion is None and hunt.get("near"):
        champion = hunt["near"][0]

    meta = {
        "cal_lo": cal_lo,
        "cal_hi": cal_hi,
        "test_lo": test_lo,
        "test_hi": test_hi,
        "n_cal_events": len(cal_ev),
        "n_test_events": len(test_ev),
        "champion": champion,
        "sl_max": SL_MAX,
        "research_only": True,
        "not_live": True,
        "behavior_first": True,
    }
    PACK.mkdir(parents=True, exist_ok=True)
    if champion:
        (PACK / "champion.json").write_text(
            json.dumps({k: v for k, v in champion.items() if k != "last3m_calls"}, indent=2, default=str),
            encoding="utf-8",
        )
    (PACK / "behavior_top.json").write_text(
        json.dumps(behavior["by_pattern"][:30], indent=2), encoding="utf-8"
    )
    write_report(meta, behavior, hunt)

    print("\n" + "=" * 60, flush=True)
    if champion:
        print(
            f"CHAMPION {champion['mode']} / {champion['bracket']} · "
            f"cal {champion['calibrate']['n']}@{champion['calibrate']['hit_pct']}% · "
            f"l3m {champion['last3m']['n']}@{champion['last3m']['hit_pct']}% · "
            f"SL/T1 {champion['last3m']['avg_sl']}/{champion['last3m']['avg_t1']}",
            flush=True,
        )
        print(f"  filter={champion.get('filter')}", flush=True)
    print(
        f"perfect_day={len(hunt.get('perfect_day') or [])} "
        f"perfect_multi={len(hunt.get('perfect_multi') or [])}",
        flush=True,
    )
    print("DONE · behavior → 100% · research only", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
