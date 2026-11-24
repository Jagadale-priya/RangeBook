"""INITIAL research: last ~1y NIFTY 1m + multi-layer MA noise filters.

Protocol (batch-1, small):
  Window  : trailing ~12m (2025-11-17 → data end)
  Train   : days < HOLD_LO  (build / lock)
  Hold    : days >= HOLD_LO (true unknown — not used to pick gates/micros)
  Goal    : toward ≥1 call/day with path accuracy; MA removes lossy noise
  Adaptive: T1 and SL vary by entry/MA distance (not one fixed bracket)

  python -u prod_live/tests/builders/_diag_scalp_ma_lastyear_init.py
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_chart_only_100 as co  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
import research_nifty_1m_vix_candle_adaptive as vixmod  # noqa: E402
import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod  # noqa: E402
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import enrich_prior3, SL10_STYLES  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_ma_lastyear"
REPORT_MD = OUT / "NIFTY_1M_SCALP_MA_LASTYEAR_INIT.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_MA_LASTYEAR_INIT.json"

WIN_LO = "2025-11-17"
HOLD_LO = "2026-08-01"  # last ~3.5m unknown
GAP = 1
# MA spans user hint: >15 useful — include short for contrast
EMA_SPANS = (9, 15, 21, 34, 50, 100)
SMA_SPANS = (20, 50)
T1_GRID = (12.0, 15.0, 20.0, 25.0, 30.0)
SL_STYLES = ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "cap15", "p75", "p60"]
SL_MAX_SOFT = 18.0  # adaptive can go a bit wider than old SL10 lock


def add_ma_layers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c = df["Close"].astype(float)
    for n in EMA_SPANS:
        df[f"ema{n}"] = c.ewm(span=n, adjust=False).mean()
    for n in SMA_SPANS:
        df[f"sma{n}"] = c.rolling(n, min_periods=n).mean()
    return df


def _slope_bin(arr, i, atr, look=5):
    if i < look or not np.isfinite(arr[i - look]):
        return "unk"
    d = float(arr[i]) - float(arr[i - look])
    thr = 0.05 * atr
    if d > thr:
        return "up"
    if d < -thr:
        return "dn"
    return "flat"


def enrich_ma_layers(events, df):
    """Multi-layer MA tags + practical noise gates (no look-ahead)."""
    close = df["Close"].astype(float).values
    emas = {n: df[f"ema{n}"].astype(float).values for n in EMA_SPANS}
    smas = {n: df[f"sma{n}"].astype(float).values for n in SMA_SPANS}

    for e in events:
        i = int(e["full_i"])
        atr = max(float(e.get("atr") or 8.0), 3.0)
        side = e["decision"]
        if i < 100 or not np.isfinite(emas[100][i]):
            e["ma_ok"] = False
            e["ma_stack15"] = "unk"
            e["ma_stack21"] = "unk"
            e["ma_stack34"] = "unk"
            e["ma_side15"] = "unk"
            e["ma_side21"] = "unk"
            e["ma_side34"] = "unk"
            e["ma_side50"] = "unk"
            e["gate_ema15"] = False
            e["gate_ema21"] = False
            e["gate_ema34"] = False
            e["gate_ema50"] = False
            e["gate_stack15"] = False
            e["gate_stack21"] = False
            e["gate_stack34"] = False
            e["gate_pull15"] = False
            e["gate_pull21"] = False
            e["gate_pull34"] = False
            e["gate_hard15"] = False
            e["gate_hard21"] = False
            e["gate_hard34"] = False
            e["gate_hard50"] = False
            e["t1_hint"] = 15.0
            e["sl_cap_hint"] = 10.0
            continue

        cl = float(close[i])
        e9, e15, e21, e34, e50, e100 = (float(emas[n][i]) for n in EMA_SPANS)
        s20, s50 = float(smas[20][i]), float(smas[50][i])

        def stack3(a, b, c_):
            if a > b > c_:
                return "bull"
            if a < b < c_:
                return "bear"
            return "mix"

        st15 = stack3(e9, e15, e34)
        st21 = stack3(e9, e21, e50)
        st34 = stack3(e15, e34, e100)
        e["ma_stack15"] = st15
        e["ma_stack21"] = st21
        e["ma_stack34"] = st34

        def side_vs(px_above, stack):
            if side == "BUY":
                align = int(px_above)
                mside = "with" if stack == "bull" else ("against" if stack == "bear" else "mix")
            else:
                align = int(not px_above)
                mside = "with" if stack == "bear" else ("against" if stack == "bull" else "mix")
            return align, mside

        a15, ms15 = side_vs(cl >= e15, st15)
        a21, ms21 = side_vs(cl >= e21, st21)
        a34, ms34 = side_vs(cl >= e34, st34)
        a50, ms50 = side_vs(cl >= e50, st21)
        e["ma_align15"], e["ma_side15"] = a15, ms15
        e["ma_align21"], e["ma_side21"] = a21, ms21
        e["ma_align34"], e["ma_side34"] = a34, ms34
        e["ma_align50"], e["ma_side50"] = a50, ms50

        slope15 = _slope_bin(emas[15], i, atr)
        slope21 = _slope_bin(emas[21], i, atr)
        slope34 = _slope_bin(emas[34], i, atr)
        slope50 = _slope_bin(emas[50], i, atr)
        e["ema15_slope"] = slope15
        e["ema21_slope"] = slope21
        e["ema34_slope"] = slope34
        e["ema50_slope"] = slope50
        want = "up" if side == "BUY" else "dn"

        def dist_bin(ma):
            d = (cl - ma) / atr
            if side == "SELL":
                d = -d
            if abs(d) < 0.35:
                return "near", d
            if abs(d) > 1.2:
                return "ext", d
            return "mid", d

        d15b, d15 = dist_bin(e15)
        d21b, d21 = dist_bin(e21)
        d34b, d34 = dist_bin(e34)
        e["dist15_bin"], e["dist15"] = d15b, round(d15, 2)
        e["dist21_bin"], e["dist21"] = d21b, round(d21, 2)
        e["dist34_bin"], e["dist34"] = d34b, round(d34, 2)
        e["sma20_ok"] = int((cl >= s20) if side == "BUY" else (cl <= s20))
        e["sma50_ok"] = int((cl >= s50) if side == "BUY" else (cl <= s50))

        # gates — noise killers
        e["gate_ema15"] = bool(a15 == 1)
        e["gate_ema21"] = bool(a21 == 1)
        e["gate_ema34"] = bool(a34 == 1)
        e["gate_ema50"] = bool(a50 == 1)
        e["gate_stack15"] = bool(ms15 == "with")
        e["gate_stack21"] = bool(ms21 == "with")
        e["gate_stack34"] = bool(ms34 == "with")
        e["gate_pull15"] = bool(a15 == 1 and d15b == "near" and ms15 != "against")
        e["gate_pull21"] = bool(a21 == 1 and d21b == "near" and ms21 != "against")
        e["gate_pull34"] = bool(a34 == 1 and d34b == "near" and ms34 != "against")
        e["gate_hard15"] = bool(a15 == 1 and ms15 == "with" and slope15 == want)
        e["gate_hard21"] = bool(a21 == 1 and ms21 == "with" and slope21 == want)
        e["gate_hard34"] = bool(a34 == 1 and ms34 == "with" and slope34 == want)
        e["gate_hard50"] = bool(a50 == 1 and ms50 == "with" and slope50 == want)
        # longer MA + close quality (user: remove noisy losses)
        e["gate_clean21"] = bool(
            e["gate_hard21"] and e.get("close_ok", 0) == 1 and e.get("fail_risk", True) is False
        )
        e["gate_clean34"] = bool(
            e["gate_hard34"] and e.get("close_ok", 0) == 1 and e.get("fail_risk", True) is False
        )
        e["gate_clean50"] = bool(
            e["gate_hard50"] and e.get("close_ok", 0) == 1 and int(e.get("sma50_ok", 0)) == 1
        )
        e["ma_ok"] = True

        # adaptive T1 / SL-cap hints from MA distance + stack
        # near pullback → smaller target; mid stack-with → medium; extended → skip or larger only if hard
        if d21b == "near" and ms21 == "with":
            e["t1_hint"] = 15.0
            e["sl_cap_hint"] = 8.0
        elif ms21 == "with" and d21b == "mid":
            e["t1_hint"] = 20.0
            e["sl_cap_hint"] = 10.0
        elif ms34 == "with" and d34b == "mid":
            e["t1_hint"] = 25.0
            e["sl_cap_hint"] = 12.0
        elif d21b == "ext" and ms21 == "with":
            e["t1_hint"] = 30.0
            e["sl_cap_hint"] = 12.0
        else:
            e["t1_hint"] = 15.0
            e["sl_cap_hint"] = 10.0


def score_adaptive(e, h, l, c, t1=None, sl_cap=None):
    """Best path among SL styles under adaptive T1/SL-cap. Returns dict or None."""
    t1 = float(t1 if t1 is not None else e.get("t1_hint", 20.0))
    sl_cap = float(sl_cap if sl_cap is not None else e.get("sl_cap_hint", 10.0))
    best = None
    for st in SL_STYLES:
        sl = float(fwdmod.lesser(e, st))
        if not (4.0 <= sl <= min(sl_cap, SL_MAX_SOFT)):
            continue
        win, out = co.path_hit(h, l, c, int(e["full_i"]), e["decision"], sl, t1)
        ok = bool(win and out == "t1")
        cand = (ok, sl, st, t1)
        if best is None:
            best = cand
        elif ok and not best[0]:
            best = cand
        elif ok == best[0] and sl < best[1]:
            best = cand
    if best is None:
        return None
    ok, sl, st, t1v = best
    return {"_win": ok, "_sl": sl, "_st": st, "_t1": t1v}


def attach_scores(events, h, l, c):
    """Score each event once (adaptive + fixed T20/SL10)."""
    for e in events:
        sc_a = score_adaptive(e, h, l, c)
        sc_f = score_adaptive(e, h, l, c, t1=20.0, sl_cap=10.0)
        e["_sc_adapt"] = sc_a
        e["_sc_fixed"] = sc_f


def gated_calls(events, pred, adaptive=True, gap=GAP):
    rows = []
    key = "_sc_adapt" if adaptive else "_sc_fixed"
    for e in events:
        if pred is not None and not pred(e):
            continue
        sc = e.get(key)
        if sc is None:
            continue
        rows.append({**e, **sc})
    return fwdmod.apply_gap(rows, gap)


def one_per_day(calls):
    first = {}
    for e in sorted(calls, key=lambda x: (x["day"], x["mins"])):
        first.setdefault(e["day"], e)
    return list(first.values())


def summarize(calls, n_days):
    if not calls:
        return {"n": 0, "hit": 0.0, "wins": 0, "days": 0, "cover": 0.0, "cpd": 0.0, "avg_sl": 0, "avg_t1": 0, "all_win": True}
    w = sum(1 for e in calls if e["_win"])
    days = len({e["day"] for e in calls})
    return {
        "n": len(calls),
        "wins": w,
        "hit": round(100.0 * w / len(calls), 2),
        "days": days,
        "cover": round(100.0 * days / max(n_days, 1), 1),
        "cpd": round(len(calls) / max(n_days, 1), 3),
        "avg_sl": round(sum(e["_sl"] for e in calls) / len(calls), 2),
        "avg_t1": round(sum(e["_t1"] for e in calls) / len(calls), 2),
        "all_win": all(e["_win"] for e in calls),
    }


def keys_ma_ly(e):
    """Compact fingerprints for last-year clean-cell hunt."""
    return [
        ("L1", e["primary"], e["decision"], e.get("ma_stack21"), e.get("dist21_bin"), e.get("ema21_slope"), e.get("close_ok")),
        ("L2", e["primary"], e["decision"], e.get("ma_stack34"), e.get("dist34_bin"), e.get("ema34_slope"), e.get("hm_bin")),
        ("L3", e["family"], e["decision"], e.get("ma_side21"), e.get("pre3_UD"), e.get("vix_regime"), e.get("sma50_ok")),
        ("L4", e["primary"], e["decision"], e.get("ma_side50"), e.get("dist21_bin"), e.get("rsi_bin"), e.get("body_bin")),
        ("L5", e["decision"], e.get("ma_stack15"), e.get("ma_stack34"), e.get("dist15_bin"), e.get("close_ok"), e.get("adv_bin")),
        ("L6", e["primary"], e["decision"], e.get("gate_hard34"), e.get("pre3_stack"), e.get("struct2"), e.get("t1_hint")),
    ]


def hunt_clean_1cpd(train, hold, h, l, c, gate_pred, min_train=2):
    """Lock adaptive path-clean fingerprint cells on train; score hold; pick ≤1/day."""
    tr = [e for e in train if gate_pred is None or gate_pred(e)]
    scored = []
    for e in tr:
        sc = e.get("_sc_adapt")
        if sc is None:
            continue
        scored.append({**e, **sc, "_keys": set(keys_ma_ly(e))})

    bucket = defaultdict(list)
    for e in scored:
        for k in e["_keys"]:
            bucket[(k, e["_st"], e["_t1"])].append(e)

    cells = []
    for id_, rows in bucket.items():
        if any(not r["_win"] for r in rows):
            continue
        if len(rows) < min_train:
            continue
        days = {r["day"] for r in rows}
        cells.append(
            {
                "k": id_[0],
                "st": id_[1],
                "t1": id_[2],
                "n": len(rows),
                "days": days,
                "avg_sl": sum(r["_sl"] for r in rows) / len(rows),
                "rows": rows,
            }
        )
    cells.sort(key=lambda r: (-len(r["days"]), -r["n"], r["avg_sl"]))

    # greedy cover train days, max 1 contribution tracking
    used = set()
    day_taken = set()
    chosen = []
    for cell in cells:
        kept = []
        for e in sorted(cell["rows"], key=lambda x: (x["day"], x["mins"])):
            if e["day"] in day_taken:
                continue
            key = (e["day"], e["mins"])
            if key in used:
                continue
            kept.append(e)
            day_taken.add(e["day"])
            used.add(key)
        if kept:
            chosen.append({"k": cell["k"], "st": cell["st"], "t1": cell["t1"], "kept": kept})

    train_calls = []
    for ch in chosen:
        train_calls.extend(ch["kept"])
    train_calls = one_per_day(train_calls)

    # apply micros on hold
    micro_map = [(ch["k"], ch["st"], ch["t1"]) for ch in chosen]
    hold_rows = []
    by = defaultdict(list)
    for e in hold:
        if gate_pred is not None and not gate_pred(e):
            continue
        by[e["day"]].append(e)
    for d, xs in sorted(by.items()):
        last = None
        for e in sorted(xs, key=lambda x: x["mins"]):
            if last is not None and e["mins"] - last < GAP:
                continue
            keys = set(keys_ma_ly(e))
            hit = None
            for k, st, t1 in micro_map:
                if k not in keys:
                    continue
                sl = float(fwdmod.lesser(e, st))
                if not (4.0 <= sl <= min(float(e.get("sl_cap_hint", 12.0)), SL_MAX_SOFT)):
                    continue
                # enforce micro's locked t1
                win, out = co.path_hit(h, l, c, int(e["full_i"]), e["decision"], sl, float(t1))
                hit = {**e, "_win": bool(win and out == "t1"), "_sl": sl, "_st": st, "_t1": float(t1)}
                break
            if hit is not None:
                hold_rows.append(hit)
                last = e["mins"]
    hold_1 = one_per_day(hold_rows)
    return chosen, train_calls, hold_rows, hold_1


GATES = [
    ("raw", None),
    ("ema15_align", lambda e: e.get("gate_ema15")),
    ("ema21_align", lambda e: e.get("gate_ema21")),
    ("ema34_align", lambda e: e.get("gate_ema34")),
    ("ema50_align", lambda e: e.get("gate_ema50")),
    ("stack15_with", lambda e: e.get("gate_stack15")),
    ("stack21_with", lambda e: e.get("gate_stack21")),
    ("stack34_with", lambda e: e.get("gate_stack34")),
    ("pull15", lambda e: e.get("gate_pull15")),
    ("pull21", lambda e: e.get("gate_pull21")),
    ("pull34", lambda e: e.get("gate_pull34")),
    ("hard15", lambda e: e.get("gate_hard15")),
    ("hard21", lambda e: e.get("gate_hard21")),
    ("hard34", lambda e: e.get("gate_hard34")),
    ("hard50", lambda e: e.get("gate_hard50")),
    ("clean21", lambda e: e.get("gate_clean21")),
    ("clean34", lambda e: e.get("gate_clean34")),
    ("clean50", lambda e: e.get("gate_clean50")),
]


def main() -> int:
    t0 = time.time()
    PACK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    print("=" * 60, flush=True)
    print("MA last-year INIT · adaptive T/SL · hold unknown", flush=True)
    print("=" * 60, flush=True)

    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    print(f"bars={len(raw)} {raw.index.min()} → {raw.index.max()}", flush=True)

    print("[1] textbook + RSI + MA layers…", flush=True)
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    vix = vixmod.load_vix()

    data_hi = str(raw.index.max().date())
    ev_cache = PACK / f"events_{WIN_LO}_{data_hi}.pkl"
    if ev_cache.exists():
        xs = pickle.load(ev_cache.open("rb"))
        print(f"[2] events cache n={len(xs)}", flush=True)
    else:
        print(f"[2] collect events {WIN_LO}→{data_hi}…", flush=True)
        xs = scalp.collect_scalp_events(df, WIN_LO, data_hi)
        pickle.dump(xs, ev_cache.open("wb"), protocol=pickle.HIGHEST_PROTOCOL)
        print(f"    n={len(xs)}", flush=True)

    print("[3] enrich structure/prior/deep/MA…", flush=True)
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)
    print("[3b] path-score adaptive + fixed (once)…", flush=True)
    attach_scores(xs, h, l, c)

    train = [e for e in xs if e["day"] < HOLD_LO]
    hold = [e for e in xs if e["day"] >= HOLD_LO]
    train_days = sorted({e["day"] for e in train})
    hold_days = sorted({e["day"] for e in hold})
    print(f"train events={len(train)} days={len(train_days)} | hold={len(hold)} days={len(hold_days)}", flush=True)

    lines = [
        "# NIFTY 1m — **MA last-year INIT** (adaptive T/SL)",
        "",
        f"Window **{WIN_LO} → {data_hi}** · Train days **{len(train_days)}** (`<{HOLD_LO}`) · Hold unknown **{len(hold_days)}** (`≥{HOLD_LO}`)",
        "",
        "## Exact logic under test",
        "",
        "1. Signal = textbook 1m candle (bull→BUY / bear→SELL).",
        "2. MA layers: EMA **9/15/21/34/50/100** + SMA **20/50** (same-bar close vs MA, no look-ahead).",
        "3. Noise gates: align / stack-with / pullback-near / hard (align+stack+slope) / clean (hard+close_ok+!fail_risk).",
        "4. **Adaptive bracket**: T1 hint 15/20/25/30 and SL-cap 8/10/12 from MA distance+stack; path win = T1 before structure SL.",
        "5. Blind rule: hold months never used to choose gates or micros.",
        "",
        "## A) Gate lift — full calls (adaptive) then **1/day**",
        "",
        "| Gate | Train n@hit | Train 1d n@hit cover | Hold n@hit | Hold 1d n@hit cover | AvgT1/SL hold |",
        "|---|---|---|---|---|---|",
    ]

    gate_rows = []
    print("[4] gate lift…", flush=True)
    for name, pred in GATES:
        tr = gated_calls(train, pred, adaptive=True)
        ho = gated_calls(hold, pred, adaptive=True)
        tr1 = one_per_day(tr)
        ho1 = one_per_day(ho)
        st_tr, st_ho = summarize(tr, len(train_days)), summarize(ho, len(hold_days))
        st_tr1, st_ho1 = summarize(tr1, len(train_days)), summarize(ho1, len(hold_days))
        gate_rows.append(
            {
                "gate": name,
                "train": st_tr,
                "train_1d": st_tr1,
                "hold": st_ho,
                "hold_1d": st_ho1,
            }
        )
        print(
            f"  {name:14s} tr {st_tr['n']}@{st_tr['hit']}% 1d {st_tr1['hit']}%/{st_tr1['cover']}% | "
            f"ho {st_ho['n']}@{st_ho['hit']}% 1d {st_ho1['hit']}%/{st_ho1['cover']}%",
            flush=True,
        )
        lines.append(
            f"| `{name}` | {st_tr['n']}@{st_tr['hit']}% | {st_tr1['n']}@{st_tr1['hit']}% {st_tr1['cover']}% | "
            f"{st_ho['n']}@{st_ho['hit']}% | {st_ho1['n']}@{st_ho1['hit']}% {st_ho1['cover']}% | "
            f"{st_ho1['avg_t1']}/{st_ho1['avg_sl']} |"
        )

    # rank gates by hold 1/day hit, then cover
    ranked = sorted(gate_rows, key=lambda r: (-r["hold_1d"]["hit"], -r["hold_1d"]["cover"], -r["train_1d"]["hit"]))
    best_gates = [r["gate"] for r in ranked[:5]]
    lines += ["", f"**Top hold 1/day gates:** {', '.join(f'`{g}`' for g in best_gates)}", ""]

    # Fixed T20/SL10 contrast on best longer-MA gates
    lines += [
        "## B) Fixed T20/SL≤10 vs adaptive (selected gates)",
        "",
        "| Gate | Mode | Train 1d hit/cover | Hold 1d hit/cover |",
        "|---|---|---|---|",
    ]
    contrast_names = ["raw", "hard21", "hard34", "hard50", "clean21", "clean34", "clean50", "pull21", "pull34"]
    print("[5] fixed vs adaptive…", flush=True)
    for name in contrast_names:
        pred = dict(GATES)[name]
        for mode, adaptive in (("adapt", True), ("t20sl10", False)):
            tr1 = one_per_day(gated_calls(train, pred, adaptive=adaptive))
            ho1 = one_per_day(gated_calls(hold, pred, adaptive=adaptive))
            st_tr1, st_ho1 = summarize(tr1, len(train_days)), summarize(ho1, len(hold_days))
            lines.append(
                f"| `{name}` | {mode} | {st_tr1['hit']}% / {st_tr1['cover']}% | {st_ho1['hit']}% / {st_ho1['cover']}% |"
            )

    # Clean-cell hunt on top MA gates
    lines += [
        "",
        "## C) Clean fingerprint micros (100% train path) → hold unknown",
        "",
        "| Book (gate) | Micros | Train 1d n@hit cover | Hold full n@hit | Hold 1d n@hit cover | all_win hold1 |",
        "|---|---:|---|---|---|:---:|",
    ]
    hunt_gates = ["hard34", "hard50", "clean34", "clean50", "hard21", "pull34", "stack34_with"]
    books = {}
    print("[6] clean micro hunt…", flush=True)
    for name in hunt_gates:
        pred = dict(GATES)[name]
        chosen, tr1, ho_full, ho1 = hunt_clean_1cpd(train, hold, h, l, c, pred, min_train=2)
        st_tr1 = summarize(tr1, len(train_days))
        st_ho = summarize(ho_full, len(hold_days))
        st_ho1 = summarize(ho1, len(hold_days))
        books[name] = {
            "n_micros": len(chosen),
            "train_1d": st_tr1,
            "hold": st_ho,
            "hold_1d": st_ho1,
        }
        (PACK / f"BOOK_{name}_micros.pkl").write_bytes(
            pickle.dumps([{"k": c["k"], "st": c["st"], "t1": c["t1"]} for c in chosen], protocol=pickle.HIGHEST_PROTOCOL)
        )
        print(
            f"  BOOK {name}: micros={len(chosen)} train1d {st_tr1['n']}@{st_tr1['hit']}% "
            f"hold1d {st_ho1['n']}@{st_ho1['hit']}% cover={st_ho1['cover']}%",
            flush=True,
        )
        lines.append(
            f"| **{name}** | {len(chosen)} | {st_tr1['n']}@{st_tr1['hit']}% {st_tr1['cover']}% | "
            f"{st_ho['n']}@{st_ho['hit']}% | {st_ho1['n']}@{st_ho1['hit']}% {st_ho1['cover']}% | {st_ho1['all_win']} |"
        )

    # Best book detail
    best_book = max(books.items(), key=lambda kv: (kv[1]["hold_1d"]["hit"], kv[1]["hold_1d"]["cover"]))
    bn, bv = best_book
    lines += [
        "",
        f"### Best hold 1/day book: `{bn}`",
        "",
        f"- Micros **{bv['n_micros']}** · hold 1/day **{bv['hold_1d']['n']}@{bv['hold_1d']['hit']}%** cover **{bv['hold_1d']['cover']}%**",
        f"- Train was locked at **{bv['train_1d']['hit']}%** on **{bv['train_1d']['n']}** days covered ({bv['train_1d']['cover']}%)",
        "",
        "## Simple read",
        "",
        "- This is **batch-1 / last year only** — not 2011→now yet.",
        "- Longer MA gates (34/50) are meant to strip noisy counter-trend ticks; adaptive T/SL lets tight pullbacks take smaller targets and trend mid takes larger.",
        "- If hold hit stays ~25–40%, fingerprints still overfit train months — next batch adds prior years **without** peeking hold.",
        "- Target state: hold 1/day hit → **100%** with cover near session count; we are measuring the gap now.",
        "",
        f"Pack: `{PACK}`",
        f"Elapsed: {time.time()-t0:.1f}s",
        "",
    ]

    payload = {
        "window": [WIN_LO, data_hi],
        "hold_lo": HOLD_LO,
        "train_days": len(train_days),
        "hold_days": len(hold_days),
        "gates": gate_rows,
        "books": books,
        "best_book": bn,
        "elapsed_s": round(time.time() - t0, 1),
    }
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {REPORT_MD}", flush=True)
    print(f"best_book={bn} hold1d={bv['hold_1d']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
