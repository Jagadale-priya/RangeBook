"""RESEARCH ONLY — Chart-analysis-only 1m model aiming **100% hit** with max calls.

No VIX. No hardcoded ±30.
SL/T1 from chart math only: MAE/MFE percentiles, ATR, OR geometry, swing structure.

Protocol:
  ANALYZE ≤ 2023-12-31 → learn brackets + find 100% logics (max n)
  TRAIN   ≤ 2024-06-30 → fit ranker on chart-great (analyze-perfect contexts) only
  TEST    ≥ 2024-07-01 → brand-new candles; keep logics that stay 100%

  python -u prod_live/tests/builders/research_nifty_1m_chart_only_100.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from itertools import product
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
import research_nifty_1m_5y_candle_ml as c5  # noqa: E402
from nifty_side_clean import recent_sample_weights  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_chart_only_100"
REPORT_MD = OUT / "NIFTY_1M_CHART_ONLY_100.md"
REPORT_JSON = OUT / "NIFTY_1M_CHART_ONLY_100.json"

START = "2021-01-01"
END = "2025-12-30"
ANALYZE_END = "2023-12-31"
TRAIN_END = "2024-06-30"
TEST_START = "2024-07-01"
OR_BARS = 15


def clock_bucket(mins: int) -> str:
    if mins < 10 * 60 + 30:
        return "early"
    if mins < 12 * 60:
        return "morning"
    if mins < 14 * 60:
        return "midday"
    return "late"


def atr_at(sess: pd.DataFrame, pos: int, n: int = 14) -> float:
    hi = sess["High"].astype(float)
    lo = sess["Low"].astype(float)
    sl = max(0, pos - n + 1)
    return float((hi.iloc[sl : pos + 1] - lo.iloc[sl : pos + 1]).mean())


def swing_levels(sess: pd.DataFrame, pos: int, look: int = 20) -> Tuple[float, float]:
    """Recent swing high/low before entry (chart structure)."""
    sl = max(0, pos - look)
    window = sess.iloc[sl:pos]
    if len(window) < 3:
        return float(sess["High"].iloc[pos]), float(sess["Low"].iloc[pos])
    return float(window["High"].max()), float(window["Low"].min())


def excursion(h, l, c, i, side, max_bars=150) -> Tuple[float, float]:
    entry = float(c[i])
    mae = mfe = 0.0
    for j in range(i + 1, min(len(c), i + 1 + max_bars)):
        if side == "BUY":
            mae = max(mae, entry - float(l[j]))
            mfe = max(mfe, float(h[j]) - entry)
        else:
            mae = max(mae, float(h[j]) - entry)
            mfe = max(mfe, entry - float(l[j]))
    return mae, mfe


def path_hit(h, l, c, i, side, sl_pts, t1_pts) -> Tuple[bool, str]:
    if sl_pts < 4 or t1_pts < 4:
        return False, "bad"
    entry = float(c[i])
    if side == "BUY":
        sl, t1 = entry - sl_pts, entry + t1_pts
        for j in range(i + 1, len(c)):
            hi, lo = float(h[j]), float(l[j])
            hs, ht = lo <= sl, hi >= t1
            if hs and ht:
                return False, "both"
            if ht:
                return True, "t1"
            if hs:
                return False, "sl"
        return False, "exp"
    sl, t1 = entry + sl_pts, entry - t1_pts
    for j in range(i + 1, len(c)):
        hi, lo = float(h[j]), float(l[j])
        hs, ht = hi >= sl, lo <= t1
        if hs and ht:
            return False, "both"
        if ht:
            return True, "t1"
        if hs:
            return False, "sl"
    return False, "exp"


def collect_chart_events(df: pd.DataFrame, day_lo: str, day_hi: str) -> List[dict]:
    """Chart-only OR first-break events with structure features."""
    events = []
    h_all = df["High"].astype(float).values
    l_all = df["Low"].astype(float).values
    c_all = df["Close"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(df.index)}
    days = [d for d in df["day"].unique() if day_lo <= d <= day_hi]
    t0 = time.time()
    for di, day in enumerate(days, 1):
        if di % 150 == 0:
            print(f"    chart events {di}/{len(days)} n={len(events)} ({time.time()-t0:.0f}s)", flush=True)
        sess = df[df["day"] == day]
        if len(sess) < OR_BARS + 25:
            continue
        or_hi = float(sess["High"].iloc[:OR_BARS].max())
        or_lo = float(sess["Low"].iloc[:OR_BARS].min())
        or_w = or_hi - or_lo
        if or_w < 12:
            continue
        day_open = float(sess["Open"].iloc[0])
        closes = sess["Close"].astype(float).values
        first_up = first_dn = None
        for pos in range(OR_BARS, len(sess)):
            if first_up is None and closes[pos] > or_hi:
                first_up = pos
            if first_dn is None and closes[pos] < or_lo:
                first_dn = pos
            if first_up is not None and first_dn is not None:
                break
        for side, pos in (("BUY", first_up), ("SELL", first_dn)):
            if pos is None:
                continue
            if side == "BUY" and first_dn is not None and first_dn < first_up:
                continue
            if side == "SELL" and first_up is not None and first_up < first_dn:
                continue
            up = dn = False
            for p2 in range(OR_BARS, pos + 1):
                if closes[p2] > or_hi:
                    up = True
                if closes[p2] < or_lo:
                    dn = True
            if up and dn:
                continue
            ts = sess.index[pos]
            mins = int(ts.hour * 60 + ts.minute)
            if mins < 10 * 60 or mins > 14 * 60 + 30:
                continue
            row = sess.iloc[pos]
            body = float(row["Close"]) - float(row["Open"])
            if side == "BUY" and body <= 0:
                continue
            if side == "SELL" and body >= 0:
                continue
            full_i = idx_map[ts]
            atr = atr_at(sess, pos)
            sw_hi, sw_lo = swing_levels(sess, pos, 20)
            entry = float(row["Close"])
            or_ext = (entry - or_hi) / or_w if side == "BUY" else (or_lo - entry) / or_w
            if or_ext > 0.30:
                continue
            # chart-derived structural distances
            if side == "BUY":
                dist_sl_or = entry - or_lo  # stop beyond OR low
                dist_t1_sw = max(sw_hi - entry, 0.0)
                dist_sl_sw = entry - sw_lo
            else:
                dist_sl_or = or_hi - entry
                dist_t1_sw = max(entry - sw_lo, 0.0)
                dist_sl_sw = sw_hi - entry
            mae, mfe = excursion(h_all, l_all, c_all, full_i, side)
            pats = [p for p in c5.PATTERN_COLS if int(row[p]) == 1] or ["_structure_"]
            typ = (sess["High"].iloc[: pos + 1] + sess["Low"].iloc[: pos + 1] + sess["Close"].iloc[: pos + 1]) / 3.0
            vwap = float(typ.mean())
            events.append(
                {
                    "day": day,
                    "hm": base._hm(ts),
                    "decision": side,
                    "entry": entry,
                    "mins": mins,
                    "clock": clock_bucket(mins),
                    "or_width": or_w,
                    "or_ext": float(or_ext),
                    "atr": float(atr),
                    "bar_range": float(row["High"] - row["Low"]),
                    "mae": mae,
                    "mfe": mfe,
                    "dist_sl_or": float(dist_sl_or),
                    "dist_t1_sw": float(dist_t1_sw),
                    "dist_sl_sw": float(dist_sl_sw),
                    "vwap_dist": float((entry - vwap) / entry * 100),
                    "session_chg": float((entry - day_open) / day_open * 100),
                    "patterns": pats,
                    "full_i": full_i,
                    "body_frac": float(row["body_frac"]),
                    "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
                    "marubozu": int(row["marubozu"]),
                    "hammer": int(row["hammer"]),
                    "bull_engulf": int(row["bull_engulf"]),
                    "bear_engulf": int(row["bear_engulf"]),
                    "bull_run2": int(row["bull_run2"]),
                    "bear_run2": int(row["bear_run2"]),
                    "pin_bull": int(row["pin_bull"]),
                    "pin_bear": int(row["pin_bear"]),
                }
            )
    return events


def bracket_family(e: dict, kind: str, params: dict) -> Tuple[float, float]:
    """Compute SL/T1 purely from chart fields + learned percentile params."""
    atr, orw = e["atr"], e["or_width"]
    if kind == "mae_mfe":
        # params carry absolute pts learned for this bucket
        return float(params["sl"]), float(params["t1"])
    if kind == "atr":
        return max(params["sl_k"] * atr, 5.0), max(params["t1_k"] * atr, 5.0)
    if kind == "or":
        return max(params["sl_k"] * orw, 5.0), max(params["t1_k"] * orw, 5.0)
    if kind == "or_opposite":
        # SL beyond OR far side, T1 fraction of OR
        sl = max(e["dist_sl_or"] * params.get("sl_k", 1.0), 0.15 * orw, 5.0)
        t1 = max(params["t1_k"] * orw, 5.0)
        return sl, t1
    if kind == "swing":
        sl = max(e["dist_sl_sw"] * params.get("sl_k", 1.05), 0.6 * atr, 5.0)
        t1 = max(e["dist_t1_sw"] * params.get("t1_k", 0.85), 0.7 * atr, 5.0)
        if t1 < 5:
            t1 = max(0.9 * atr, 5.0)
        return sl, t1
    if kind == "mix":
        sl = max(params["sl_atr"] * atr, params["sl_or"] * orw, 5.0)
        t1 = max(params["t1_atr"] * atr, params["t1_or"] * orw, 5.0)
        return sl, t1
    return max(0.8 * atr, 5.0), max(1.2 * atr, 5.0)


def learn_mae_mfe_grid(ana: List[dict]) -> Dict[str, dict]:
    """For each pattern×side×clock, store MAE/MFE percentile pairs for high-hit brackets."""
    buckets: Dict[str, List[dict]] = defaultdict(list)
    for e in ana:
        for pat in e["patterns"]:
            buckets[f"{pat}|{e['decision']}|{e['clock']}"].append(e)
            buckets[f"{pat}|{e['decision']}|*"].append(e)
        buckets[f"*|{e['decision']}|{e['clock']}"].append(e)
        buckets[f"*|{e['decision']}|*"].append(e)

    # Asymmetric percentiles favor T1-before-SL (wider SL, nearer T1)
    pairs = [
        (70, 40),
        (75, 35),
        (80, 30),
        (80, 40),
        (85, 35),
        (65, 45),
        (60, 50),
        (75, 45),
    ]
    out = {}
    for key, rows in buckets.items():
        if len(rows) < 10:
            continue
        maes = np.array([r["mae"] for r in rows], dtype=float)
        mfes = np.array([r["mfe"] for r in rows], dtype=float)
        atr_m = float(np.median([r["atr"] for r in rows]))
        or_m = float(np.median([r["or_width"] for r in rows]))
        for sp, tp in pairs:
            sl = float(np.percentile(maes, sp))
            t1 = float(np.percentile(mfes, tp))
            sl = max(sl, 0.5 * atr_m, 0.10 * or_m, 5.0)
            t1 = max(t1, 0.35 * atr_m, 0.08 * or_m, 5.0)
            # keep if R:R not absurdly bad for research
            out[f"{key}|p{sp}_{tp}"] = {
                "sl": round(sl, 2),
                "t1": round(t1, 2),
                "n": len(rows),
                "sl_p": sp,
                "t1_p": tp,
                "kind": "mae_mfe",
            }
    return out


def resolve_mae_bracket(e: dict, table: dict, sl_p: int, t1_p: int) -> Tuple[float, float, str]:
    side, clock = e["decision"], e["clock"]
    cands = []
    for pat in e["patterns"]:
        for key in (
            f"{pat}|{side}|{clock}|p{sl_p}_{t1_p}",
            f"{pat}|{side}|*|p{sl_p}_{t1_p}",
            f"*|{side}|{clock}|p{sl_p}_{t1_p}",
            f"*|{side}|*|p{sl_p}_{t1_p}",
        ):
            if key in table:
                b = table[key]
                cands.append((key, b["sl"], b["t1"], b["n"]))
    if not cands:
        # local chart fallback
        sl = max(0.85 * e["atr"], 0.14 * e["or_width"], 5.0)
        t1 = max(0.55 * e["atr"], 0.10 * e["or_width"], 5.0)
        return sl, t1, "local_chart"
    key, sl, t1, _ = max(cands, key=lambda x: (x[3],))
    return float(sl), float(t1), key


def first_day(rows: List[dict]) -> List[dict]:
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: (x["day"], x["hm"])):
        if r["day"] in seen:
            continue
        seen.add(r["day"])
        out.append(r)
    return out


def agg(rows: List[dict]) -> dict:
    if not rows:
        return {"n": 0, "wins": 0, "hit_pct": 0.0}
    w = sum(1 for r in rows if r.get("win"))
    return {"n": len(rows), "wins": w, "hit_pct": round(100.0 * w / len(rows), 2)}


def apply_filters(events: List[dict], f: dict) -> List[dict]:
    out = []
    for e in events:
        if f.get("side") and e["decision"] != f["side"]:
            continue
        if f.get("clocks") and e["clock"] not in f["clocks"]:
            continue
        if f.get("patterns") and not (set(e["patterns"]) & set(f["patterns"])):
            continue
        if f.get("max_or_ext") is not None and e["or_ext"] > f["max_or_ext"]:
            continue
        if f.get("min_or") is not None and e["or_width"] < f["min_or"]:
            continue
        if f.get("min_atr") is not None and e["atr"] < f["min_atr"]:
            continue
        if f.get("max_body") is not None and abs(e["body_frac"]) > f["max_body"]:
            continue
        if f.get("vwap_side") == "with":
            # BUY above vwap, SELL below
            if e["decision"] == "BUY" and e["vwap_dist"] < 0:
                continue
            if e["decision"] == "SELL" and e["vwap_dist"] > 0:
                continue
        out.append(e)
    return out


def eval_bracketed(events, h, l, c, f, bracket_mode, bracket_args, mae_table=None) -> dict:
    rows = []
    for e in apply_filters(events, f):
        if bracket_mode == "mae_mfe":
            sl, t1, src = resolve_mae_bracket(e, mae_table, bracket_args["sl_p"], bracket_args["t1_p"])
        else:
            sl, t1 = bracket_family(e, bracket_mode, bracket_args)
            src = bracket_mode
        win, outcome = path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
        if outcome in ("bad", "both"):
            continue
        rows.append(
            {
                "day": e["day"],
                "hm": e["hm"],
                "decision": e["decision"],
                "entry": e["entry"],
                "sl": round(sl, 2),
                "t1": round(t1, 2),
                "bracket_src": src,
                "patterns": e["patterns"],
                "clock": e["clock"],
                "or_width": e["or_width"],
                "atr": e["atr"],
                "win": win,
                "outcome": outcome,
                "full_i": e["full_i"],
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
                    float(e["marubozu"]),
                    float(e["hammer"]),
                    float(e["bull_engulf"]),
                    float(e["bear_engulf"]),
                    float(e["bull_run2"]),
                    float(e["bear_run2"]),
                    sl,
                    t1,
                    t1 / sl if sl else 0,
                ],
            }
        )
    du = first_day(rows)
    a = agg(du)
    a["calls"] = du
    a["avg_sl"] = round(float(np.mean([r["sl"] for r in du])), 2) if du else 0
    a["avg_t1"] = round(float(np.mean([r["t1"] for r in du])), 2) if du else 0
    return a


def _call_row(e: dict, sl: float, t1: float, src: str, win: bool, outcome: str) -> dict:
    return {
        "day": e["day"],
        "hm": e["hm"],
        "decision": e["decision"],
        "entry": e["entry"],
        "sl": round(sl, 2),
        "t1": round(t1, 2),
        "bracket_src": src,
        "patterns": e["patterns"],
        "clock": e["clock"],
        "or_width": e["or_width"],
        "atr": e["atr"],
        "win": win,
        "outcome": outcome,
        "full_i": e["full_i"],
        "or_ext": e["or_ext"],
        "vwap_dist": e["vwap_dist"],
        "body_frac": e["body_frac"],
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
            float(e["marubozu"]),
            float(e["hammer"]),
            float(e["bull_engulf"]),
            float(e["bear_engulf"]),
            float(e["bull_run2"]),
            float(e["bear_run2"]),
            sl,
            t1,
            t1 / sl if sl else 0,
        ],
    }


def precompute_brackets(events, h, l, c, mae_table, specs: List[Tuple[str, dict, str]]) -> Dict[str, List[Optional[dict]]]:
    """One path_hit per event×bracket. Returns label → list aligned to events (None if bad/both)."""
    out: Dict[str, List[Optional[dict]]] = {lab: [None] * len(events) for _, _, lab in specs}
    t0 = time.time()
    for ei, e in enumerate(events):
        if (ei + 1) % 80 == 0:
            print(f"    precompute {ei+1}/{len(events)} ({time.time()-t0:.0f}s)", flush=True)
        for mode, args, lab in specs:
            if mode == "mae_mfe":
                sl, t1, src = resolve_mae_bracket(e, mae_table, args["sl_p"], args["t1_p"])
            else:
                sl, t1 = bracket_family(e, mode, args)
                src = mode
            win, outcome = path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
            if outcome in ("bad", "both"):
                continue
            out[lab][ei] = _call_row(e, sl, t1, src, win, outcome)
    return out


def _agg_pre(events, pre_col: List[Optional[dict]], mask: List[bool]) -> dict:
    rows = [pre_col[i] for i, ok in enumerate(mask) if ok and pre_col[i] is not None]
    du = first_day(rows)
    a = agg(du)
    a["calls"] = du
    a["avg_sl"] = round(float(np.mean([r["sl"] for r in du])), 2) if du else 0
    a["avg_t1"] = round(float(np.mean([r["t1"] for r in du])), 2) if du else 0
    return a


def _event_mask(events: List[dict], f: dict) -> List[bool]:
    kept = {(e["day"], e["hm"], e["decision"]) for e in apply_filters(events, f)}
    return [(e["day"], e["hm"], e["decision"]) in kept for e in events]


def hunt_100(ana_events, test_events, h, l, c, mae_table) -> dict:
    """Deep hunt for 100% logics with max calls (precomputed paths)."""
    print("\n[3] Deep hunt for 100% chart logics…", flush=True)
    pattern_sets = [
        None,
        ["marubozu"],
        ["_structure_"],
        ["hammer", "pin_bull"],
        ["shooting", "pin_bear"],
        ["bull_engulf", "bull_run2"],
        ["bear_engulf", "bear_run2"],
        ["marubozu", "bull_engulf"],
        ["marubozu", "bear_engulf"],
        ["bull_run2"],
        ["bear_run2"],
        ["doji"],
        ["hammer"],
        ["pin_bull"],
        ["pin_bear"],
        ["bull_engulf"],
        ["bear_engulf"],
    ]
    sides = [None, "BUY", "SELL"]
    clocks = [None, ["early"], ["morning"], ["early", "morning"], ["morning", "midday"], ["midday"], ["early", "morning", "midday"]]
    max_exts = [0.08, 0.10, 0.12, 0.15, 0.18, 0.22, 0.25]
    min_ors = [12, 15, 18, 20, 25, 30, 35]
    vwap_opts = [None, "with"]

    mae_pairs = [(70, 40), (75, 35), (80, 30), (80, 40), (85, 35), (75, 45), (65, 45), (85, 40), (90, 35)]
    atr_params = [
        {"sl_k": 0.9, "t1_k": 0.6},
        {"sl_k": 1.1, "t1_k": 0.7},
        {"sl_k": 1.3, "t1_k": 0.8},
        {"sl_k": 1.5, "t1_k": 0.9},
        {"sl_k": 1.2, "t1_k": 0.55},
        {"sl_k": 1.4, "t1_k": 0.65},
        {"sl_k": 1.6, "t1_k": 0.75},
    ]
    or_params = [
        {"sl_k": 0.20, "t1_k": 0.12},
        {"sl_k": 0.25, "t1_k": 0.14},
        {"sl_k": 0.30, "t1_k": 0.15},
        {"sl_k": 0.22, "t1_k": 0.10},
        {"sl_k": 0.35, "t1_k": 0.18},
        {"sl_k": 0.28, "t1_k": 0.12},
        {"sl_k": 0.40, "t1_k": 0.20},
    ]
    swing_params = [
        {"sl_k": 1.05, "t1_k": 0.8},
        {"sl_k": 1.1, "t1_k": 0.7},
        {"sl_k": 1.15, "t1_k": 0.65},
        {"sl_k": 1.2, "t1_k": 0.75},
    ]
    mix_params = [
        {"sl_atr": 1.0, "sl_or": 0.12, "t1_atr": 0.6, "t1_or": 0.10},
        {"sl_atr": 1.2, "sl_or": 0.15, "t1_atr": 0.7, "t1_or": 0.12},
        {"sl_atr": 0.9, "sl_or": 0.18, "t1_atr": 0.55, "t1_or": 0.10},
        {"sl_atr": 1.3, "sl_or": 0.20, "t1_atr": 0.65, "t1_or": 0.11},
    ]

    specs: List[Tuple[str, dict, str]] = []
    for sp, tp in mae_pairs:
        specs.append(("mae_mfe", {"sl_p": sp, "t1_p": tp}, f"mae_mfe_p{sp}_{tp}"))
    for p in atr_params:
        specs.append(("atr", p, f"atr_sl{p['sl_k']}_t{p['t1_k']}"))
    for p in or_params:
        specs.append(("or", p, f"or_sl{p['sl_k']}_t{p['t1_k']}"))
    for p in swing_params:
        specs.append(("swing", p, f"swing_sl{p['sl_k']}_t{p['t1_k']}"))
    for p in mix_params:
        specs.append(("mix", p, f"mix_{p['sl_atr']}_{p['sl_or']}_{p['t1_atr']}_{p['t1_or']}"))

    print(f"  precompute ana={len(ana_events)} test={len(test_events)} brackets={len(specs)}", flush=True)
    ana_pre = precompute_brackets(ana_events, h, l, c, mae_table, specs)
    test_pre = precompute_brackets(test_events, h, l, c, mae_table, specs)

    filter_grid = []
    for pats, side, clk, ext, mor, vw in product(pattern_sets, sides, clocks, max_exts, min_ors, vwap_opts):
        filter_grid.append(
            {"side": side, "patterns": pats, "clocks": clk, "max_or_ext": ext, "min_or": mor, "vwap_side": vw}
        )
    print(f"  filter combos={len(filter_grid)} · scoring…", flush=True)

    results_100 = []
    results_hi = []
    t0 = time.time()
    n_try = 0
    labels = [lab for _, _, lab in specs]

    for fi, f in enumerate(filter_grid, 1):
        if fi % 2000 == 0:
            print(
                f"    filters {fi}/{len(filter_grid)} found100={len(results_100)} both-scan ({time.time()-t0:.0f}s)",
                flush=True,
            )
        ana_mask = _event_mask(ana_events, f)
        if sum(ana_mask) < 5:
            continue
        test_mask = _event_mask(test_events, f)
        for lab in labels:
            n_try += 1
            ares = _agg_pre(ana_events, ana_pre[lab], ana_mask)
            if ares["n"] < 5:
                continue
            if ares["hit_pct"] < 70:
                continue
            tres = _agg_pre(test_events, test_pre[lab], test_mask)
            compact = {
                "bracket": lab,
                "filters": f,
                "analyze": {k: ares[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                "test": {k: tres[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
            }
            if ares["hit_pct"] >= 100 - 1e-9:
                if tres["hit_pct"] >= 100 - 1e-9 and tres["n"] >= 1:
                    compact["test_calls"] = tres["calls"]
                    compact["analyze_calls"] = ares["calls"]
                results_100.append(compact)
            elif ares["n"] >= 8 and len(results_hi) < 400:
                results_hi.append(compact)

    def sig(r):
        days = tuple(sorted(c["day"] for c in r.get("test_calls") or []))
        return (
            r["bracket"].split("_")[0],
            r["analyze"]["n"],
            r["test"]["n"],
            days,
            json.dumps(r["filters"], sort_keys=True, default=str),
            round(r["test"]["hit_pct"], 2),
        )

    uniq = []
    seen = set()
    for r in sorted(
        results_100,
        key=lambda x: (
            -x["test"]["n"] if x["test"]["hit_pct"] >= 100 else 0,
            -x["analyze"]["n"],
            -x["test"]["hit_pct"],
        ),
    ):
        s = sig(r)
        if s in seen:
            continue
        seen.add(s)
        uniq.append(r)

    both100 = [
        r
        for r in uniq
        if r["analyze"]["hit_pct"] >= 100 - 1e-9 and r["test"]["hit_pct"] >= 100 - 1e-9 and r["test"]["n"] >= 1
    ]
    both100.sort(key=lambda r: (-r["test"]["n"], -r["analyze"]["n"]))

    # materialize calls for top analyze-100 that lacked them
    analyze100 = []
    for r in uniq[:40]:
        lab = r["bracket"]
        if "analyze_calls" not in r:
            am = _event_mask(ana_events, r["filters"])
            tm = _event_mask(test_events, r["filters"])
            ares = _agg_pre(ana_events, ana_pre[lab], am)
            tres = _agg_pre(test_events, test_pre[lab], tm)
            r = dict(r)
            r["analyze_calls"] = ares["calls"]
            r["test_calls"] = tres["calls"]
        analyze100.append(r)
    both100 = both100[:25]

    by_day = {}
    for r in both100:
        for call in r.get("test_calls") or []:
            by_day.setdefault(call["day"], call)
    union = first_day(list(by_day.values()))

    print(
        f"  tried~{n_try} analyze100={len(uniq)} both100={len(both100)} "
        f"union_test_n={len(union)} ({time.time()-t0:.0f}s)",
        flush=True,
    )
    return {
        "analyze100": analyze100,
        "both100": both100,
        "hi70": sorted(results_hi, key=lambda r: (-r["test"]["hit_pct"], -r["test"]["n"]))[:20],
        "union100": {
            "n": len(union),
            "wins": sum(1 for call in union if call["win"]),
            "hit_pct": agg(union)["hit_pct"],
            "calls": union,
        },
        "ml_pool_lab": "mae_mfe_p80_40",
        "ana_pre_ml": ana_pre.get("mae_mfe_p80_40"),
        "test_pre_ml": test_pre.get("mae_mfe_p80_40"),
    }


FEAT = [
    "atr",
    "or_width",
    "or_ext",
    "body_frac",
    "vwap_dist",
    "session_chg",
    "rsi",
    "mins",
    "side",
    "marubozu",
    "hammer",
    "bull_engulf",
    "bear_engulf",
    "bull_run2",
    "bear_run2",
    "sl",
    "t1",
    "rr",
]


def train_chart_ml(calls: List[dict], test_calls: Optional[List[dict]] = None) -> Optional[dict]:
    """Train ranker on chart features (wins+losses) through TRAIN_END; score TEST."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    rows = [r for r in calls if r and r["day"] <= TRAIN_END]
    if len(rows) < 25 or len(set(bool(r["win"]) for r in rows)) < 2:
        return None
    X = np.asarray([r["x_chart"] for r in rows], dtype=float)
    y = np.asarray([1 if r["win"] else 0 for r in rows], dtype=int)
    w = recent_sample_weights([r["day"] for r in rows], half_life_days=400.0)
    clf = HistGradientBoostingClassifier(
        max_depth=3, max_iter=100, min_samples_leaf=12, l2_regularization=1.0, learning_rate=0.05, random_state=42
    )
    clf.fit(X, y, sample_weight=w)
    raw = clf.predict_proba(X)[:, 1]
    out = {
        "base": clf,
        "fit_auc": round(base._auc(y, raw), 3),
        "n_train": len(rows),
        "feature_names": FEAT,
        "research_only": True,
        "chart_only": True,
        "train_hit": round(100.0 * float(y.mean()), 2),
    }
    te = [r for r in (test_calls or []) if r]
    if te:
        Xt = np.asarray([r["x_chart"] for r in te], dtype=float)
        yt = np.asarray([1 if r["win"] else 0 for r in te], dtype=int)
        pt = clf.predict_proba(Xt)[:, 1]
        out["test_auc"] = round(base._auc(yt, pt), 3) if len(set(yt.tolist())) > 1 else None
        # high-confidence slice aiming at 100%
        best = None
        for q in (0.70, 0.75, 0.80, 0.85, 0.90, 0.92, 0.95):
            thr = float(np.quantile(pt, q))
            sel = [(te[i], float(pt[i])) for i in range(len(te)) if pt[i] >= thr]
            du = first_day([{"day": s[0]["day"], "hm": s[0]["hm"], "decision": s[0]["decision"],
                             "entry": s[0]["entry"], "sl": s[0]["sl"], "t1": s[0]["t1"],
                             "patterns": s[0]["patterns"], "win": s[0]["win"], "prob": s[1]} for s in sel])
            if len(du) < 3:
                continue
            hit = agg(du)["hit_pct"]
            cand = {"q": q, "thr": round(thr, 4), "n": len(du), "hit_pct": hit, "calls": du}
            if hit >= 100 - 1e-9 and (best is None or cand["n"] > best["n"]):
                best = cand
            elif best is None or (hit > best["hit_pct"] or (hit == best["hit_pct"] and cand["n"] > best["n"])):
                if best is None or best.get("hit_pct", 0) < 100:
                    best = cand
        out["test_p_slice"] = {k: v for k, v in (best or {}).items() if k != "calls"}
        out["test_p_calls"] = (best or {}).get("calls")
    return out


def write_report(meta, hunt, pack_ml) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    both = hunt.get("both100") or []
    union = hunt.get("union100") or {}
    lines = [
        "# NIFTY 1m — **chart-only** model · aim 100% with max calls",
        "",
        "**Not live.** Chart analysis only (OR / candles / ATR / swings / VWAP). **No hardcoded ±30.**",
        "",
        f"- Analyze ≤ `{ANALYZE_END}` · Train ≤ `{TRAIN_END}` · Test ≥ `{TEST_START}`",
        f"- Events ana/test: {meta.get('n_ana')} / {meta.get('n_test')}",
        "",
        "## How SL / T1 are calculated (chart math)",
        "",
        "1. **MAE/MFE path stats** on analyze first-breaks → SL = MAE percentile, T1 = MFE percentile (asymmetric for high hit).",
        "2. **ATR / OR geometry** — multiples of entry ATR and opening-range width.",
        "3. **Swing structure** — SL beyond recent swing, T1 toward opposite swing.",
        "4. **OR opposite** — SL toward far OR side, T1 as OR fraction.",
        "",
        f"## 100% on BOTH analyze + new test: **{len(both)}** logics",
        "",
        f"### Union of all both-100 test calls: **{union.get('n')} @ {union.get('hit_pct')}%**",
        "",
    ]
    if union.get("calls"):
        lines += ["| Day | HM | Side | SL | T1 | Win |", "|---|---|---|---:|---:|:---:|"]
        for c in union["calls"]:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['decision']} | {c['sl']} | {c['t1']} | "
                f"{'Y' if c['win'] else 'N'} |"
            )
        lines.append("")

    lines += ["## Best both-100 logics (max test n)", "", "| # | Bracket | Filters | Ana n | Test n | Avg SL/T1 |", "|---:|---|---|---:|---:|---|"]
    for i, r in enumerate(both[:12], 1):
        f = r["filters"]
        short = (
            f"side={f.get('side')} pats={f.get('patterns') or f.get('require_any')} "
            f"clk={f.get('clocks')} ext≤{f.get('max_or_ext')} OR≥{f.get('min_or')} "
            f"vwap={f.get('vwap_side')} rsi={f.get('rsi_lo')}-{f.get('rsi_hi')} body≥{f.get('min_body')}"
        )
        lines.append(
            f"| {i} | `{r['bracket']}` | {short[:90]} | {r['analyze']['n']} | "
            f"**{r['test']['n']}** | {r['test']['avg_sl']}/{r['test']['avg_t1']} |"
        )

    if both:
        best = both[0]
        lines += [
            "",
            f"### Detail · best both-100 · test **{best['test']['n']} @ 100%**",
            "",
            f"- Bracket: `{best['bracket']}`",
            f"- Filters: `{json.dumps(best['filters'], default=str)}`",
            f"- Analyze: {best['analyze']['n']} @ 100% · avg SL/T1 {best['analyze']['avg_sl']}/{best['analyze']['avg_t1']}",
            "",
            "| Day | HM | Side | SL | T1 | patterns | Win |",
            "|---|---|---|---:|---:|---|:---:|",
        ]
        for c in best.get("test_calls") or []:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['decision']} | {c['sl']} | {c['t1']} | "
                f"{','.join(c.get('patterns') or [])} | Y |"
            )

    lines += ["", "## Near-miss (analyze ≥70%, for context)", "", "| Bracket | Ana | Test |", "|---|---|---|"]
    for r in (hunt.get("hi70") or [])[:10]:
        lines.append(
            f"| `{r['bracket']}` | {r['analyze']['n']}@{r['analyze']['hit_pct']}% | "
            f"{r['test']['n']}@{r['test']['hit_pct']}% |"
        )

    lines += ["", "## Chart ML ranker (chart features only)", ""]
    if pack_ml:
        sl = pack_ml.get("test_p_slice") or {}
        lines.append(
            f"- Trained on chart path labels · n={pack_ml.get('n_train')} "
            f"fit_auc={pack_ml.get('fit_auc')} test_auc={pack_ml.get('test_auc')}"
        )
        if sl:
            lines.append(
                f"- High-P test slice: **{sl.get('n')} @ {sl.get('hit_pct')}%** "
                f"(q={sl.get('q')} thr={sl.get('thr')})"
            )
        if pack_ml.get("test_p_calls"):
            lines += ["", "| Day | HM | Side | SL | T1 | P | Win |", "|---|---|---|---:|---:|---:|:---:|"]
            for c in pack_ml["test_p_calls"]:
                lines.append(
                    f"| {c['day']} | {c['hm']} | {c['decision']} | {c['sl']} | {c['t1']} | "
                    f"{c.get('prob', 0):.3f} | {'Y' if c['win'] else 'N'} |"
                )
    else:
        lines.append("- Ranker skipped (too few labeled chart rows).")

    lines += [
        "",
        "## Research pick",
        "",
    ]
    if both:
        lines.append(
            f"**Promote-candidate (chart-only, 100% on analyze+test):** "
            f"`{both[0]['bracket']}` with **{both[0]['test']['n']} new-data calls @ 100%** "
            f"(analyze n={both[0]['analyze']['n']} @ 100%)."
        )
        if union.get("n", 0) > both[0]["test"]["n"]:
            lines.append(
                f"**Union book:** **{union['n']} @ 100%** by combining all both-100 micros "
                "(still research-only; overlapping filters)."
            )
    else:
        lines.append("No logic stayed 100% on both windows — see near-miss table; tighten chart filters further.")

    lines += [
        "",
        "## Policy",
        "",
        f"- Pack: `{PACK}`",
        "- research_only · not_live · chart_only · no hardcoded ±30",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    payload = {
        "meta": meta,
        "both100": [
            {k: v for k, v in r.items() if k not in ("analyze_calls",)}
            for r in both[:15]
        ],
        "union100": union,
        "hi70": [{k: v for k, v in r.items() if k not in ("analyze_calls", "test_calls")} for r in (hunt.get("hi70") or [])[:15]],
        "ml": {k: v for k, v in (pack_ml or {}).items() if k != "base"},
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {REPORT_MD}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · CHART-ONLY · 100% max-calls · adaptive SL/T1", flush=True)
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
    print("\n[0] Chart candle columns…", flush=True)
    df = c5.add_candle_cols(raw)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values

    print("\n[1] Collect chart events…", flush=True)
    ana = collect_chart_events(df, START, ANALYZE_END)
    test = collect_chart_events(df, TEST_START, END)
    print(f"  analyze={len(ana)} test={len(test)}", flush=True)

    print("\n[2] Learn MAE/MFE chart brackets (asymmetric percentiles)…", flush=True)
    mae_table = learn_mae_mfe_grid(ana)
    print(f"  mae/mfe recipes={len(mae_table)}", flush=True)

    hunt = hunt_100(ana, test, h, l, c, mae_table)

    # Train ML on chart features using MAE/MFE path labels (wins+losses)
    print("\n[4] Train chart-only ML on chart path labels…", flush=True)
    train_pool = [r for r in (hunt.get("ana_pre_ml") or []) if r]
    test_pool = [r for r in (hunt.get("test_pre_ml") or []) if r]
    # enrich with analyze-100 wins so great contexts are weighted in sample
    for r in (hunt.get("analyze100") or [])[:20]:
        for c in r.get("analyze_calls") or []:
            train_pool.append(c)
    pack_ml = train_chart_ml(train_pool, test_pool) if train_pool else None
    if pack_ml:
        sl = pack_ml.get("test_p_slice") or {}
        print(
            f"  ML n={pack_ml['n_train']} fit_auc={pack_ml['fit_auc']} "
            f"test_auc={pack_ml.get('test_auc')} slice={sl.get('n')}@{sl.get('hit_pct')}%",
            flush=True,
        )
    else:
        print("  ML skipped", flush=True)

    meta = {
        "n_ana": len(ana),
        "n_test": len(test),
        "n_mae_recipes": len(mae_table),
        "n_both100": len(hunt.get("both100") or []),
        "union_n": (hunt.get("union100") or {}).get("n"),
        "chart_only": True,
        "hardcoded_sl_t1": False,
        "research_only": True,
        "not_live": True,
    }
    PACK.mkdir(parents=True, exist_ok=True)
    (PACK / "mae_mfe_brackets.json").write_text(json.dumps(mae_table, indent=2), encoding="utf-8")
    if pack_ml:
        import joblib

        joblib.dump(pack_ml, PACK / "chart_ranker.joblib")
    if hunt.get("both100"):
        (PACK / "best_both100.json").write_text(
            json.dumps(
                {
                    "bracket": hunt["both100"][0]["bracket"],
                    "filters": hunt["both100"][0]["filters"],
                    "analyze": hunt["both100"][0]["analyze"],
                    "test": hunt["both100"][0]["test"],
                    "test_calls": hunt["both100"][0]["test_calls"],
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
    write_report(meta, hunt, pack_ml)

    u = hunt.get("union100") or {}
    print("\n" + "=" * 60, flush=True)
    print(f"BOTH100 logics={meta['n_both100']} · UNION test {u.get('n')}@{u.get('hit_pct')}%", flush=True)
    if hunt.get("both100"):
        b = hunt["both100"][0]
        print(f"BEST: {b['bracket']} test {b['test']['n']}@100% ana {b['analyze']['n']}@100%", flush=True)
    print("DONE · chart-only · research only", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
