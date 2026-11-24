"""RESEARCH ONLY — Accuracy v2: truth-aligned bar ignition (not textbook-only).

Finding from v1: real ≥25pt impulses have
  prev_opposite ~99% · not_extreme ~86% · ctrl ~84%
  but room_ok only ~11% · disp10 only ~24%
So old IGN100 (room+disp10+bounce) was MISALIGNED with how big moves start.

This pass scores EVERY session 1m bar as a causal ignition candidate:
  SIDE  = BUY if green bar after red (prev_opposite), else SELL if red after green
  ENTRY = close of that bar (or confirm+1)
  FILTERS mined from truth rates

Prove on m25_first (reach +25 before −25) and clean15.

  python -u prod_live/tests/builders/_diag_scalp_entry_accuracy_v2.py
"""
from __future__ import annotations

import json
import sys
import time
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators  # noqa: E402
from _diag_scalp_ad_sr_entry_1m import add_ad_obv_proxy  # noqa: E402
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ENTRY_ACCURACY_V2.md"
REPORT_JSON = OUT / "NIFTY_1M_ENTRY_ACCURACY_V2.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 120
LOOKBACK_CAL = 240
FWD = 60
M25 = 25.0
PIVOT_L = 3


def swings(h, l, i, L=PIVOT_L, look=120):
    lo = max(L, i - look)
    hi_i, lo_i = [], []
    for j in range(lo, i - L):
        if h[j] >= np.max(h[j - L : j + L + 1]) - 1e-9:
            hi_i.append(j)
        if l[j] <= np.min(l[j - L : j + L + 1]) + 1e-9:
            lo_i.append(j)
    return [float(h[j]) for j in hi_i], [float(l[j]) for j in lo_i]


def nearest_above(levels, px):
    above = [x for x in levels if x > px + 0.05]
    return min(above) if above else None


def nearest_below(levels, px):
    below = [x for x in levels if x < px - 0.05]
    return max(below) if below else None


def label(h, l, c, day, i, entry, side):
    d = day[i]
    mfe = mae = 0.0
    hit25 = None
    end = min(len(c) - 1, i + FWD)
    for j in range(i + 1, end + 1):
        if day[j] != d:
            break
        if side == "BUY":
            mfe = max(mfe, float(h[j]) - entry)
            mae = max(mae, entry - float(l[j]))
        else:
            mfe = max(mfe, entry - float(l[j]))
            mae = max(mae, float(h[j]) - entry)
        if hit25 is None and mfe >= M25:
            hit25 = j
    m25_first = False
    if hit25 is not None:
        adv = 0.0
        m25_first = True
        for j in range(i + 1, hit25 + 1):
            if side == "BUY":
                adv = max(adv, entry - float(l[j]))
            else:
                adv = max(adv, float(h[j]) - entry)
            if adv >= M25:
                m25_first = False
                break
    return {
        "mfe": round(mfe, 2),
        "mae": round(mae, 2),
        "m25": mfe >= M25,
        "m25_first": m25_first,
        "clean15": mfe >= M25 and mae <= 15.0,
        "clean10": mfe >= M25 and mae <= 10.0,
    }


def pack(rows, key, mid):
    if not rows:
        return {"n": 0, "prec": None, "train_n": 0, "train_prec": None, "oos_n": 0, "oos_prec": None,
                "avg_mfe": None, "avg_mae": None, "t25": None}
    tr = [r for r in rows if r["day"] < mid]
    oo = [r for r in rows if r["day"] >= mid]

    def _p(rs):
        if not rs:
            return None, 0
        return round(100.0 * sum(1 for x in rs if x.get(key)) / len(rs), 2), len(rs)

    p, n = _p(rows)
    pt, nt = _p(tr)
    po, no = _p(oo)
    return {
        "n": n,
        "prec": p,
        "train_n": nt,
        "train_prec": pt,
        "oos_n": no,
        "oos_prec": po,
        "avg_mfe": round(float(np.mean([r["mfe"] for r in rows])), 2),
        "avg_mae": round(float(np.mean([r["mae"] for r in rows])), 2),
        "t25": round(100.0 * sum(1 for r in rows if r.get("t25")) / n, 2),
        "m25": round(100.0 * sum(1 for r in rows if r.get("m25")) / n, 2),
        "clean15": round(100.0 * sum(1 for r in rows if r.get("clean15")) / n, 2),
    }


def verdict(st, soft=95.0, hard=100.0, min_n=15, min_half=6):
    if not st or st["n"] < min_n:
        return "THIN"
    if (
        st["prec"] == hard
        and st["train_prec"] == hard
        and st["oos_prec"] == hard
        and (st["train_n"] or 0) >= min_half
        and (st["oos_n"] or 0) >= min_half
    ):
        return "PROVEN_100"
    if (
        st["prec"] is not None
        and st["train_prec"] is not None
        and st["oos_prec"] is not None
        and st["prec"] >= soft
        and st["train_prec"] >= soft
        and st["oos_prec"] >= soft
        and (st["train_n"] or 0) >= min_half
        and (st["oos_n"] or 0) >= min_half
    ):
        return "PROMISING_95"
    if st["prec"] is not None and st["prec"] >= 85 and (st["oos_prec"] or 0) >= 80:
        return "HIGH_85"
    return "WEAK"


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("ENTRY ACCURACY v2 — truth-aligned bar ignition", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    df = add_ad_obv_proxy(df)

    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    mid = days_sorted[n_days // 2]
    print(f"window {day_lo}→{day_hi} n={n_days} OOS≥{mid}", flush=True)

    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    atr = df["atr14"].astype(float).values
    vwap = df["vwap"].astype(float).values if "vwap" in df.columns else c.copy()
    pdi = df["plus_di"].astype(float).values if "plus_di" in df.columns else np.zeros(len(c))
    mdi = df["minus_di"].astype(float).values if "minus_di" in df.columns else np.zeros(len(c))
    ad_r = df["ad_rising"].astype(bool).values if "ad_rising" in df.columns else np.zeros(len(c), dtype=bool)
    ad_f = df["ad_falling"].astype(bool).values if "ad_falling" in df.columns else np.zeros(len(c), dtype=bool)
    day = np.array([str(ts.date()) for ts in df.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df.index])
    idx = df.index

    # Precompute session extremes per day
    sess_hl = {}
    for d in keep:
        m = day == d
        ii = np.where(m)[0]
        sess_hl[d] = ii

    cands: List[dict] = []
    for i in range(1, len(c) - 1):
        d = day[i]
        if d not in keep:
            continue
        if not (MINS_LO <= mins[i] <= MINS_HI):
            continue
        if day[i - 1] != d:
            continue
        green = c[i] > o[i]
        red = c[i] < o[i]
        prev_green = c[i - 1] > o[i - 1]
        prev_red = c[i - 1] < o[i - 1]
        # ignition: color flip into this bar
        if green and prev_red:
            side = "BUY"
        elif red and prev_green:
            side = "SELL"
        else:
            continue

        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        entry = float(c[i])
        rng = max(float(h[i]) - float(l[i]), 0.05)
        loc = (float(c[i]) - float(l[i])) / rng
        buyer = loc >= 0.65 and green
        seller = loc <= 0.35 and red
        ctrl = (side == "BUY" and buyer) or (side == "SELL" and seller)
        body = abs(float(c[i]) - float(o[i]))
        # S/R room
        sh, sl = swings(h, l, i)
        levels = sh + sl + [float(vwap[i])]
        # session so far
        si = sess_hl[d]
        so_far = si[si < i]
        if len(so_far):
            levels += [float(np.max(h[so_far])), float(np.min(l[so_far])), float(o[so_far[0]])]
            sess_hi, sess_lo = float(np.max(h[so_far])), float(np.min(l[so_far]))
        else:
            sess_hi = sess_lo = entry
        uniq = sorted({round(x, 1) for x in levels if np.isfinite(x)})
        resist = nearest_above(uniq, entry)
        support = nearest_below(uniq, entry)
        room_up = 999.0 if resist is None else resist - entry
        room_dn = 999.0 if support is None else entry - support
        room_fav = room_up if side == "BUY" else room_dn
        room_ag = room_dn if side == "BUY" else room_up
        near_sup = support is not None and (entry - float(support)) <= 0.6 * a
        near_res = resist is not None and (float(resist) - entry) <= 0.6 * a
        bounce = (side == "BUY" and near_sup) or (side == "SELL" and near_res)
        into_ext = (side == "BUY" and (sess_hi - entry) <= max(8.0, a)) or (
            side == "SELL" and (entry - sess_lo) <= max(8.0, a)
        )
        di_ok = (side == "BUY" and pdi[i] > mdi[i]) or (side == "SELL" and mdi[i] > pdi[i])
        above = float(c[i]) >= float(ema34[i]) if np.isfinite(ema34[i]) else True
        gate34 = (side == "BUY" and above) or (side == "SELL" and not above)
        vw = float(vwap[i]) if np.isfinite(vwap[i]) else entry
        vwap_with = (side == "BUY" and entry >= vw) or (side == "SELL" and entry <= vw)
        held = bool(di_ok and gate34 and vwap_with)
        ad = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))

        # confirm+1: next bar continues same color
        conf = False
        conf_i = None
        if i + 1 < len(c) and day[i + 1] == d:
            if side == "BUY" and c[i + 1] > o[i + 1]:
                conf = True
                conf_i = i + 1
            if side == "SELL" and c[i + 1] < o[i + 1]:
                conf = True
                conf_i = i + 1

        lab0 = label(h, l, c, day, i, entry, side)
        ok25, _, _, _ = path_ma_trail_strict(h, l, c, ema34, i, side, 25.0)
        row = {
            "day": d,
            "hm": idx[i].strftime("%H:%M"),
            "mins": int(mins[i]),
            "side": side,
            "entry": round(entry, 2),
            "entry_i": i,
            "mode": "ignition0",
            "ctrl": ctrl,
            "ad": ad,
            "held": held,
            "bounce": bounce,
            "not_extreme": not into_ext,
            "room_ok": room_fav >= 1.5 * a and not into_ext,
            "runway2": room_fav >= 2.0 * a,
            "disp10": body >= 1.0 * a,
            "disp08": body >= 0.8 * a,
            "big_body": body >= max(8.0, 0.6 * a),
            "di_ok": bool(di_ok),
            "vwap_with": bool(vwap_with),
            "gate34": bool(gate34),
            "conf1": conf,
            "t25": bool(ok25),
            **lab0,
        }
        cands.append(row)

        if conf and conf_i is not None:
            entry1 = float(c[conf_i])
            lab1 = label(h, l, c, day, conf_i, entry1, side)
            ok25b, _, _, _ = path_ma_trail_strict(h, l, c, ema34, conf_i, side, 25.0)
            # recompute a few flags at confirm bar lightly
            a1 = float(atr[conf_i]) if np.isfinite(atr[conf_i]) and atr[conf_i] > 0 else a
            body1 = abs(float(c[conf_i]) - float(o[conf_i]))
            rng1 = max(float(h[conf_i]) - float(l[conf_i]), 0.05)
            loc1 = (float(c[conf_i]) - float(l[conf_i])) / rng1
            ctrl1 = (side == "BUY" and loc1 >= 0.65 and c[conf_i] > o[conf_i]) or (
                side == "SELL" and loc1 <= 0.35 and c[conf_i] < o[conf_i]
            )
            cands.append(
                {
                    "day": d,
                    "hm": idx[conf_i].strftime("%H:%M"),
                    "mins": int(mins[conf_i]),
                    "side": side,
                    "entry": round(entry1, 2),
                    "entry_i": conf_i,
                    "mode": "confirm1",
                    "ctrl": ctrl1,
                    "ad": (side == "BUY" and bool(ad_r[conf_i])) or (side == "SELL" and bool(ad_f[conf_i])),
                    "held": held,  # keep ignition held context
                    "bounce": bounce,
                    "not_extreme": not into_ext,
                    "room_ok": room_fav >= 1.5 * a and not into_ext,
                    "runway2": room_fav >= 2.0 * a,
                    "disp10": body1 >= 1.0 * a1,
                    "disp08": body1 >= 0.8 * a1,
                    "big_body": body1 >= max(8.0, 0.6 * a1),
                    "di_ok": bool(di_ok),
                    "vwap_with": bool(vwap_with),
                    "gate34": bool(gate34),
                    "conf1": True,
                    "t25": bool(ok25b),
                    **lab1,
                }
            )

    print(f"candidates={len(cands)}", flush=True)
    ign0 = [r for r in cands if r["mode"] == "ignition0"]
    conf1 = [r for r in cands if r["mode"] == "confirm1"]

    def run_gate(name, rows, pred, key="m25_first"):
        hit = [r for r in rows if pred(r)]
        # 1 per day first signal
        byd = {}
        for r in sorted(hit, key=lambda x: (x["day"], x["mins"])):
            if r["day"] not in byd:
                byd[r["day"]] = r
        # also keep all-signals book
        st_all = pack(hit, key, mid)
        st_1d = pack(list(byd.values()), key, mid)
        return {
            "name": name,
            "key": key,
            "all": st_all,
            "one_per_day": st_1d,
            "verdict_all": verdict(st_all, min_n=20, min_half=8),
            "verdict_1d": verdict(st_1d, min_n=15, min_half=6),
            "samples": list(byd.values())[:15],
        }

    gates = []
    # Truth-aligned cores
    cores = [
        ("ign0 prev_opp+ctrl+!ext", ign0, lambda r: r["ctrl"] and r["not_extreme"]),
        ("ign0 prev_opp+ctrl+!ext+ad", ign0, lambda r: r["ctrl"] and r["not_extreme"] and r["ad"]),
        ("ign0 prev_opp+ctrl+!ext+bounce", ign0, lambda r: r["ctrl"] and r["not_extreme"] and r["bounce"]),
        ("ign0 prev_opp+ctrl+!ext+ad+bounce", ign0, lambda r: r["ctrl"] and r["not_extreme"] and r["ad"] and r["bounce"]),
        ("ign0 prev_opp+ctrl+!ext+held", ign0, lambda r: r["ctrl"] and r["not_extreme"] and r["held"]),
        ("ign0 prev_opp+ctrl+!ext+held+ad", ign0, lambda r: r["ctrl"] and r["not_extreme"] and r["held"] and r["ad"]),
        ("ign0 prev_opp+ctrl+!ext+held+bounce", ign0, lambda r: r["ctrl"] and r["not_extreme"] and r["held"] and r["bounce"]),
        ("ign0 prev_opp+ctrl+!ext+big_body", ign0, lambda r: r["ctrl"] and r["not_extreme"] and r["big_body"]),
        ("ign0 prev_opp+ctrl+!ext+ad+big_body", ign0, lambda r: r["ctrl"] and r["not_extreme"] and r["ad"] and r["big_body"]),
        ("ign0 prev_opp+ctrl+!ext+held+big_body", ign0, lambda r: r["ctrl"] and r["not_extreme"] and r["held"] and r["big_body"]),
        ("ign0 prev_opp+ctrl+!ext+ad+held+big_body", ign0, lambda r: r["ctrl"] and r["not_extreme"] and r["ad"] and r["held"] and r["big_body"]),
        ("ign0 prev_opp+ctrl+!ext+ad+held+bounce+big_body", ign0, lambda r: r["ctrl"] and r["not_extreme"] and r["ad"] and r["held"] and r["bounce"] and r["big_body"]),
        # confirm1 (wait 1 more same-color bar)
        ("conf1 ctrl+!ext", conf1, lambda r: r["ctrl"] and r["not_extreme"]),
        ("conf1 ctrl+!ext+ad", conf1, lambda r: r["ctrl"] and r["not_extreme"] and r["ad"]),
        ("conf1 ctrl+!ext+ad+held", conf1, lambda r: r["ctrl"] and r["not_extreme"] and r["ad"] and r["held"]),
        ("conf1 ctrl+!ext+ad+held+bounce", conf1, lambda r: r["ctrl"] and r["not_extreme"] and r["ad"] and r["held"] and r["bounce"]),
        ("conf1 ctrl+!ext+ad+held+big_body", conf1, lambda r: r["ctrl"] and r["not_extreme"] and r["ad"] and r["held"] and r["big_body"]),
        ("conf1 ctrl+!ext+ad+bounce+big_body", conf1, lambda r: r["ctrl"] and r["not_extreme"] and r["ad"] and r["bounce"] and r["big_body"]),
        ("conf1 ctrl+!ext+held+bounce+big_body", conf1, lambda r: r["ctrl"] and r["not_extreme"] and r["held"] and r["bounce"] and r["big_body"]),
        ("conf1 ctrl+!ext+ad+held+bounce+big_body", conf1, lambda r: r["ctrl"] and r["not_extreme"] and r["ad"] and r["held"] and r["bounce"] and r["big_body"]),
        ("conf1 ctrl+!ext+ad+held+bounce+disp08", conf1, lambda r: r["ctrl"] and r["not_extreme"] and r["ad"] and r["held"] and r["bounce"] and r["disp08"]),
    ]

    for name, rows, pred in cores:
        g = run_gate(name, rows, pred, "m25_first")
        g2 = run_gate(name + " [clean15]", rows, pred, "clean15")
        gates.append(g)
        print(
            f"  {name}: all n={g['all']['n']} m25f={g['all']['prec']}% OOS={g['all']['oos_prec']}% "
            f"| 1/day n={g['one_per_day']['n']} m25f={g['one_per_day']['prec']}% → {g['verdict_1d']} "
            f"| clean15={g2['one_per_day']['prec']}%",
            flush=True,
        )

    # Exhaustive on confirm1 with 1/day for high precision
    feat_keys = ["ctrl", "ad", "held", "bounce", "not_extreme", "big_body", "disp08", "disp10", "room_ok"]
    hunt = []
    for k in (3, 4, 5):
        for combo in combinations(feat_keys, k):
            if "ctrl" not in combo or "not_extreme" not in combo:
                continue
            hit = [r for r in conf1 if all(r.get(f) for f in combo)]
            byd = {}
            for r in sorted(hit, key=lambda x: (x["day"], x["mins"])):
                if r["day"] not in byd:
                    byd[r["day"]] = r
            rows = list(byd.values())
            st = pack(rows, "m25_first", mid)
            if st["n"] < 12 or st["prec"] is None or st["prec"] < 85:
                continue
            hunt.append(
                {
                    "name": "conf1|1d|" + "+".join(combo),
                    **st,
                    "verdict": verdict(st),
                    "clean15": pack(rows, "clean15", mid)["prec"],
                }
            )
    hunt.sort(key=lambda x: (0 if x["verdict"] == "PROVEN_100" else 1 if x["verdict"] == "PROMISING_95" else 2, -(x["prec"] or 0), -(x["oos_prec"] or 0), -x["n"]))
    # dedupe
    seen = set()
    hunt_u = []
    for h_ in hunt:
        if h_["name"] in seen:
            continue
        seen.add(h_["name"])
        hunt_u.append(h_)
    hunt = hunt_u[:25]
    print(f"confirm1 1/day hunt ≥85% m25_first n≥12: {len(hunt)}", flush=True)
    for h_ in hunt[:8]:
        print(f"  {h_['name']}: n={h_['n']} prec={h_['prec']}% OOS={h_['oos_prec']}% {h_['verdict']}", flush=True)

    # Same hunt on ign0
    hunt0 = []
    for k in (3, 4, 5):
        for combo in combinations(feat_keys, k):
            if "ctrl" not in combo or "not_extreme" not in combo:
                continue
            hit = [r for r in ign0 if all(r.get(f) for f in combo)]
            byd = {}
            for r in sorted(hit, key=lambda x: (x["day"], x["mins"])):
                if r["day"] not in byd:
                    byd[r["day"]] = r
            rows = list(byd.values())
            st = pack(rows, "m25_first", mid)
            if st["n"] < 12 or st["prec"] is None or st["prec"] < 85:
                continue
            hunt0.append(
                {
                    "name": "ign0|1d|" + "+".join(combo),
                    **st,
                    "verdict": verdict(st),
                    "clean15": pack(rows, "clean15", mid)["prec"],
                }
            )
    hunt0.sort(key=lambda x: (0 if x["verdict"] == "PROVEN_100" else 1 if x["verdict"] == "PROMISING_95" else 2, -(x["prec"] or 0), -(x["oos_prec"] or 0), -x["n"]))
    seen = set()
    hunt0_u = []
    for h_ in hunt0:
        if h_["name"] in seen:
            continue
        seen.add(h_["name"])
        hunt0_u.append(h_)
    hunt0 = hunt0_u[:25]
    print(f"ign0 1/day hunt ≥85%: {len(hunt0)}", flush=True)

    best_gates = sorted(
        gates,
        key=lambda g: (
            0 if g["verdict_1d"] == "PROVEN_100" else 1 if g["verdict_1d"] == "PROMISING_95" else 2 if g["verdict_1d"] == "HIGH_85" else 3,
            -(g["one_per_day"]["prec"] or 0),
            -(g["one_per_day"]["oos_prec"] or 0),
            -g["one_per_day"]["n"],
        ),
    )
    best = best_gates[0]
    proven = [h for h in hunt + hunt0 if h["verdict"] == "PROVEN_100"]
    promising = [h for h in hunt + hunt0 if h["verdict"] == "PROMISING_95"]

    payload = {
        "ok": True,
        "research_only": True,
        "window": {"day_lo": day_lo, "day_hi": day_hi, "n_days": n_days, "oos_from": mid},
        "insight": "Truth impulses: prev_opp~99% ctrl~84% !extreme~86%; room_ok~11% disp10~24% — avoid room/disp as required",
        "gates": [
            {
                "name": g["name"],
                "verdict_1d": g["verdict_1d"],
                "one_per_day": g["one_per_day"],
                "all": g["all"],
                "samples": [
                    {"day": s["day"], "hm": s["hm"], "side": s["side"], "entry": s["entry"],
                     "mfe": s["mfe"], "mae": s["mae"], "m25_first": s["m25_first"], "clean15": s["clean15"]}
                    for s in g["samples"][:12]
                ],
            }
            for g in best_gates
        ],
        "hunt_conf1": hunt,
        "hunt_ign0": hunt0,
        "proven": proven[:10],
        "promising": promising[:10],
        "best_gate": best["name"],
        "took_sec": round(time.time() - t0, 1),
    }

    lines = [
        "# NIFTY 1m — Entry accuracy **v2** (truth-aligned ignition)",
        "",
        "> Fix: real ≥25pt moves rarely have `room_ok` / `disp10`. Align filters with truth rates.",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS **{mid}**.",
        "",
        "## Insight",
        "",
        "| Feature at true impulse | Rate | Use in gate? |",
        "|---|---:|---|",
        "| prev_opposite | ~99% | **required** (defines ignition) |",
        "| control_with | ~84% | **required** |",
        "| not_extreme | ~86% | **required** |",
        "| bounce | ~59% | optional tighten |",
        "| AD with | ~56% | optional tighten |",
        "| room_ok | ~11% | **do not require** |",
        "| disp10 | ~24% | **do not require** |",
        "",
        "Entry modes: `ignition0` = close of flip bar · `confirm1` = wait 1 more same-color bar then enter.",
        "Books reported as **1 trade/day** (first signal) for stability.",
        "",
        "## 1) Truth-aligned gates (1/day · m25_first)",
        "",
        "| Gate | Verdict | n | m25_first% | OOS | clean15% | avg MFE | avg MAE |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for g in best_gates:
        s = g["one_per_day"]
        lines.append(
            f"| `{g['name']}` | **{g['verdict_1d']}** | {s['n']} | **{s['prec']}** | {s['oos_prec']} | "
            f"{s['clean15']} | {s['avg_mfe']} | {s['avg_mae']} |"
        )

    lines += [
        "",
        "## 2) Exhaustive hunt ≥85% m25_first (1/day)",
        "",
        "### confirm1",
        "",
    ]
    if not hunt:
        lines.append("_None._")
    else:
        lines.append("| Rule | n | prec | Train | OOS | clean15 | Verdict |")
        lines.append("|---|---:|---:|---|---|---:|---|")
        for h_ in hunt[:15]:
            lines.append(
                f"| `{h_['name']}` | {h_['n']} | **{h_['prec']}** | {h_['train_n']}/{h_['train_prec']}% | "
                f"{h_['oos_n']}/{h_['oos_prec']}% | {h_['clean15']} | **{h_['verdict']}** |"
            )

    lines += ["", "### ignition0", ""]
    if not hunt0:
        lines.append("_None._")
    else:
        lines.append("| Rule | n | prec | Train | OOS | clean15 | Verdict |")
        lines.append("|---|---:|---:|---|---|---:|---|")
        for h_ in hunt0[:15]:
            lines.append(
                f"| `{h_['name']}` | {h_['n']} | **{h_['prec']}** | {h_['train_n']}/{h_['train_prec']}% | "
                f"{h_['oos_n']}/{h_['oos_prec']}% | {h_['clean15']} | **{h_['verdict']}** |"
            )

    lines += ["", "## 3) Most accurate logic", ""]
    if proven:
        w = proven[0]
        lines += [
            f"**PROVEN_100:** `{w['name']}`",
            f"- n={w['n']} · m25_first **{w['prec']}%** · TRAIN {w['train_prec']}% · OOS {w['oos_prec']}% · clean15 {w['clean15']}%",
            "",
            "```",
            "1. Wait for color flip 1m bar (prev opposite) = ignition",
            "2. Optional: wait 1 more same-color bar (confirm1)",
            f"3. Require: {w['name'].split('|',2)[-1].replace('+',' + ')}",
            "4. SIDE = BUY if green run / SELL if red run",
            "5. ENTRY = close of entry bar",
            "```",
        ]
    elif promising:
        w = promising[0]
        lines += [
            f"**PROMISING_95:** `{w['name']}`",
            f"- n={w['n']} · m25_first **{w['prec']}%** · OOS {w['oos_prec']}% · clean15 {w['clean15']}%",
            "",
            "Ship only after another OOS window confirms.",
        ]
    else:
        lines += [
            f"**Best effort:** `{best['name']}` · {best['verdict_1d']}",
            f"- 1/day m25_first **{best['one_per_day']['prec']}%** OOS **{best['one_per_day']['oos_prec']}%** n={best['one_per_day']['n']}",
            f"- clean15 **{best['one_per_day']['clean15']}%** · avg MFE {best['one_per_day']['avg_mfe']} · avg MAE {best['one_per_day']['avg_mae']}",
            "",
            "### Samples",
            "",
            "| Day | HM | Side | Entry | MFE | MAE | m25_first | clean15 |",
            "|---|---|---|---:|---:|---:|---|---|",
        ]
        for s in best["samples"][:12]:
            lines.append(
                f"| {s['day']} | {s['hm']} | **{s['side']}** | **{s['entry']}** | "
                f"{s['mfe']} | {s['mae']} | {s['m25_first']} | {s['clean15']} |"
            )

    lines += [
        "",
        "## 4) Action for live IGN100",
        "",
        "- Old `run_ignition_100` (room+disp10+bounce) is **not** the most accurate one-direction rule.",
        "- Prefer a **truth-aligned** gate from this report once PROVEN_100 / PROMISING_95 appears.",
        "- Until then: keep IGN100 as research mode, do not claim clean one-way accuracy.",
        "",
        f"_Generated in {payload['took_sec']}s._",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    print(
        f"BEST={best['name']} 1d={best['one_per_day']['prec']}% proven={len(proven)} promising={len(promising)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
