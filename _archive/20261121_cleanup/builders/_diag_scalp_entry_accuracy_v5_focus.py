"""RESEARCH ONLY — Accuracy v5: fix HTF + stress-test best v4 lead.

v4 lead: pullback after run2/3 + atr_hi + compress + engulf + ctrl
  → 80% m25_first OOS 80% n=15 (HIGH_75)

Fixes: HTF bias uses 'up'/'down' (not bull/bear).
This pass expands that family, adds held/AD/time, all-signals vs 1/day,
and hunts ≥85/95/100 with min_n floors.

  python -u prod_live/tests/builders/_diag_scalp_entry_accuracy_v5_focus.py
"""
from __future__ import annotations

import json
import sys
import time
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators  # noqa: E402
from _diag_scalp_ad_sr_entry_1m import add_ad_obv_proxy  # noqa: E402
from _diag_scalp_pa_bos_choch_fvg import (  # noqa: E402
    _norm_1m,
    to_15m,
    structure_events,
    build_htf_bias,
    htf_bias_lookup,
)
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ENTRY_ACCURACY_V5_FOCUS.md"
REPORT_JSON = OUT / "NIFTY_1M_ENTRY_ACCURACY_V5_FOCUS.json"

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
        return {
            "n": 0,
            "prec": None,
            "train_n": 0,
            "train_prec": None,
            "oos_n": 0,
            "oos_prec": None,
            "avg_mfe": None,
            "avg_mae": None,
            "clean15": None,
            "m25": None,
        }
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
        "clean15": round(100.0 * sum(1 for r in rows if r.get("clean15")) / n, 2),
        "m25": round(100.0 * sum(1 for r in rows if r.get("m25")) / n, 2),
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
        (st["prec"] or 0) >= soft
        and (st["train_prec"] or 0) >= soft
        and (st["oos_prec"] or 0) >= soft
        and (st["train_n"] or 0) >= min_half
        and (st["oos_n"] or 0) >= min_half
    ):
        return "PROMISING_95"
    if (st["prec"] or 0) >= 85 and (st["oos_prec"] or 0) >= 80 and (st["train_prec"] or 0) >= 80:
        return "HIGH_85"
    if (st["prec"] or 0) >= 75 and (st["oos_prec"] or 0) >= 70 and (st["train_prec"] or 0) >= 70:
        return "HIGH_75"
    return "WEAK"


def one_per_day(rows):
    byd = {}
    for r in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        if r["day"] not in byd:
            byd[r["day"]] = r
    return list(byd.values())


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("ENTRY ACCURACY v5 — focus pullback compress+engulf + HTF fix", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df1 = _norm_1m(raw)
    df1 = add_ma_layers(df1)
    df1 = add_indicators(df1)
    df1 = add_ad_obv_proxy(df1)

    days_all = sorted({str(ts.date()) for ts in df1.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    mid = days_sorted[n_days // 2]
    df1 = df1[[str(ts.date()) in keep for ts in df1.index]]
    df15 = to_15m(df1)
    bias15 = build_htf_bias(df15, structure_events(df15))
    print(f"window {day_lo}→{day_hi} n={n_days} OOS≥{mid} htf_keys={len(bias15)}", flush=True)

    o = df1["Open"].astype(float).values
    h = df1["High"].astype(float).values
    l = df1["Low"].astype(float).values
    c = df1["Close"].astype(float).values
    ema34 = df1["ema34"].astype(float).values
    atr = df1["atr14"].astype(float).values
    vwap = df1["vwap"].astype(float).values if "vwap" in df1.columns else c.copy()
    pdi = df1["plus_di"].astype(float).values if "plus_di" in df1.columns else np.zeros(len(c))
    mdi = df1["minus_di"].astype(float).values if "minus_di" in df1.columns else np.zeros(len(c))
    ad_r = df1["ad_rising"].astype(bool).values if "ad_rising" in df1.columns else np.zeros(len(c), dtype=bool)
    ad_f = df1["ad_falling"].astype(bool).values if "ad_falling" in df1.columns else np.zeros(len(c), dtype=bool)
    day = np.array([str(ts.date()) for ts in df1.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df1.index])
    idx = df1.index
    n = len(c)

    sess = {d: np.where(day == d)[0] for d in keep}

    def feats(i, side, entry, ign_i):
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        d = day[i]
        rng = max(float(h[i]) - float(l[i]), 0.05)
        loc = (float(c[i]) - float(l[i])) / rng
        green = c[i] > o[i]
        red = c[i] < o[i]
        body = abs(float(c[i]) - float(o[i]))
        ctrl = (side == "BUY" and loc >= 0.65 and green) or (side == "SELL" and loc <= 0.35 and red)
        sh, sl = swings(h, l, i)
        levels = sh + sl + [float(vwap[i])]
        so_far = sess[d][sess[d] < i]
        if len(so_far):
            sess_hi, sess_lo = float(np.max(h[so_far])), float(np.min(l[so_far]))
            levels += [sess_hi, sess_lo, float(o[so_far[0]])]
        else:
            sess_hi = sess_lo = entry
        uniq = sorted({round(x, 1) for x in levels if np.isfinite(x)})
        resist = nearest_above(uniq, entry)
        support = nearest_below(uniq, entry)
        room_fav = (999.0 if resist is None else resist - entry) if side == "BUY" else (
            999.0 if support is None else entry - support
        )
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
        htf_raw = htf_bias_lookup(bias15, idx[i])
        htf_with = (side == "BUY" and htf_raw == "up") or (side == "SELL" and htf_raw == "down")
        already = 0.0
        if ign_i is not None and ign_i <= i:
            already = (float(c[i]) - float(l[ign_i])) if side == "BUY" else (float(h[ign_i]) - float(c[i]))
        compress = False
        if i >= 1 and day[i - 1] == d:
            pr = max(float(h[i - 1]) - float(l[i - 1]), 0.05)
            compress = pr <= 0.7 * a and body >= 0.8 * a
        # softer compress variants
        compress_soft = False
        if i >= 1 and day[i - 1] == d:
            pr = max(float(h[i - 1]) - float(l[i - 1]), 0.05)
            compress_soft = pr <= 0.9 * a and body >= 0.6 * a
        engulf = False
        if i >= 1 and day[i - 1] == d:
            if side == "BUY":
                engulf = float(c[i]) > float(o[i - 1]) and float(o[i]) <= float(c[i - 1])
            else:
                engulf = float(c[i]) < float(o[i - 1]) and float(o[i]) >= float(c[i - 1])
        # engulf body only (close beyond prior close)
        engulf_close = False
        if i >= 1 and day[i - 1] == d:
            if side == "BUY":
                engulf_close = float(c[i]) > float(c[i - 1]) and float(c[i - 1]) < float(o[i - 1])
            else:
                engulf_close = float(c[i]) < float(c[i - 1]) and float(c[i - 1]) > float(o[i - 1])
        close_strong = (side == "BUY" and loc >= 0.8) or (side == "SELL" and loc <= 0.2)
        hl3 = True
        if i >= 2 and day[i - 2] == d:
            if side == "BUY":
                hl3 = l[i] >= l[i - 1] - 0.05 and l[i - 1] >= l[i - 2] - 0.05
            else:
                hl3 = h[i] <= h[i - 1] + 0.05 and h[i - 1] <= h[i - 2] + 0.05
        wick_ag = (float(c[i]) - float(l[i])) if side == "BUY" else (float(h[i]) - float(c[i]))
        tight_wick = wick_ag <= 0.35 * a
        body_dom = body >= 0.55 * rng
        return {
            "ctrl": bool(ctrl),
            "ad": bool(ad),
            "held": bool(held),
            "bounce": bool(bounce),
            "not_extreme": not into_ext,
            "room_ok": room_fav >= 1.5 * a and not into_ext,
            "disp10": body >= 1.0 * a,
            "disp08": body >= 0.8 * a,
            "big_body": body >= max(8.0, 0.6 * a),
            "htf_with": bool(htf_with),
            "atr_hi": a >= 10.0,
            "atr_ok": a >= 6.0,
            "compress": bool(compress),
            "compress_soft": bool(compress_soft),
            "engulf": bool(engulf),
            "engulf_close": bool(engulf_close),
            "close_strong": bool(close_strong),
            "hl3": bool(hl3),
            "tight_wick": bool(tight_wick),
            "body_dom": bool(body_dom),
            "am": mins[i] < 11 * 60,
            "midday": 11 * 60 <= mins[i] < 13 * 60,
            "already8": already >= 8.0,
            "already12": already >= 12.0,
            "already_lt25": already < 25.0,
            "already": round(already, 2),
            "atr": round(a, 2),
        }

    # Pullback universe (same as v4)
    pb: List[dict] = []
    i = 1
    while i < n - 2:
        d = day[i]
        if d not in keep or not (MINS_LO <= mins[i] <= MINS_HI):
            i += 1
            continue
        if c[i] == o[i]:
            i += 1
            continue
        bull = c[i] > o[i]
        s = i
        while s - 1 >= 0 and day[s - 1] == d:
            if bull and c[s - 1] > o[s - 1]:
                s -= 1
            elif (not bull) and c[s - 1] < o[s - 1]:
                s -= 1
            else:
                break
        nb = i - s + 1
        if nb not in (2, 3):
            i += 1
            continue
        side = "BUY" if bull else "SELL"
        ign_i = s
        ign_hi, ign_lo = float(h[ign_i]), float(l[ign_i])
        for k in range(i + 1, min(i + 9, n - 1)):
            if day[k] != d:
                break
            opp = (bull and c[k] < o[k]) or ((not bull) and c[k] > o[k])
            if not opp:
                continue
            if not (float(l[k]) <= ign_hi and float(h[k]) >= ign_lo):
                continue
            j = k + 1
            if j >= n or day[j] != d:
                break
            cont = (bull and c[j] > o[j]) or ((not bull) and c[j] < o[j])
            if not cont or not (MINS_LO <= mins[j] <= MINS_HI):
                continue
            entry = float(c[j])
            if side == "BUY" and entry - ign_lo >= 25:
                break
            if side == "SELL" and ign_hi - entry >= 25:
                break
            fp = feats(j, side, entry, ign_i)
            lab = label(h, l, c, day, j, entry, side)
            ok25, _, _, _ = path_ma_trail_strict(h, l, c, ema34, j, side, 25.0)
            pb.append(
                {
                    "day": d,
                    "hm": idx[j].strftime("%H:%M"),
                    "mins": int(mins[j]),
                    "side": side,
                    "entry": round(entry, 2),
                    "entry_i": j,
                    "run_n": nb,
                    "t25": bool(ok25),
                    **fp,
                    **lab,
                }
            )
            break
        i += 1
    print(f"pullback cands={len(pb)} htf_with rate={100*sum(1 for r in pb if r['htf_with'])/max(len(pb),1):.1f}%", flush=True)

    # Also ignition for HTF-fixed baselines
    ign: List[dict] = []
    for i in range(1, n - 1):
        d = day[i]
        if d not in keep or not (MINS_LO <= mins[i] <= MINS_HI) or day[i - 1] != d:
            continue
        green, red = c[i] > o[i], c[i] < o[i]
        prev_g, prev_r = c[i - 1] > o[i - 1], c[i - 1] < o[i - 1]
        if green and prev_r:
            side = "BUY"
        elif red and prev_g:
            side = "SELL"
        else:
            continue
        entry = float(c[i])
        fp = feats(i, side, entry, i)
        lab = label(h, l, c, day, i, entry, side)
        ign.append({"day": d, "hm": idx[i].strftime("%H:%M"), "mins": int(mins[i]), "side": side, "entry": round(entry, 2), **fp, **lab})
    print(f"ignition cands={len(ign)} htf_with={100*sum(1 for r in ign if r['htf_with'])/max(len(ign),1):.1f}%", flush=True)

    results = []

    def score(name, rows, pred, book="1d"):
        hit = [r for r in rows if pred(r)]
        use = one_per_day(hit) if book == "1d" else hit
        st = pack(use, "m25_first", mid)
        st_m = pack(use, "m25", mid)
        st_c = pack(use, "clean15", mid)
        v = verdict(st, min_n=12 if book == "1d" else 20, min_half=5 if book == "1d" else 8)
        row = {
            "name": f"{name}|{book}",
            "verdict": v,
            **st,
            "m25": st_m["prec"],
            "clean15": st_c["prec"],
            "samples": use[:12],
        }
        results.append(row)
        print(
            f"  {row['name']}: n={st['n']} m25f={st['prec']}% tr={st['train_prec']}% oos={st['oos_prec']}% "
            f"m25={st_m['prec']}% c15={st_c['prec']}% → {v}",
            flush=True,
        )
        return row

    print("\n--- focus gates ---", flush=True)
    focus = [
        ("pb atr_hi+compress+engulf+ctrl", pb, lambda r: r["atr_hi"] and r["compress"] and r["engulf"] and r["ctrl"]),
        ("pb atr_hi+compress+engulf+ctrl+!ext", pb, lambda r: r["atr_hi"] and r["compress"] and r["engulf"] and r["ctrl"] and r["not_extreme"]),
        ("pb atr_hi+compress+engulf+ctrl+held", pb, lambda r: r["atr_hi"] and r["compress"] and r["engulf"] and r["ctrl"] and r["held"]),
        ("pb atr_hi+compress+engulf+ctrl+htf", pb, lambda r: r["atr_hi"] and r["compress"] and r["engulf"] and r["ctrl"] and r["htf_with"]),
        ("pb atr_hi+compress+engulf+ctrl+ad", pb, lambda r: r["atr_hi"] and r["compress"] and r["engulf"] and r["ctrl"] and r["ad"]),
        ("pb atr_hi+compress+engulf+ctrl+am", pb, lambda r: r["atr_hi"] and r["compress"] and r["engulf"] and r["ctrl"] and r["am"]),
        ("pb atr_hi+compress+engulf+ctrl+close_strong", pb, lambda r: r["atr_hi"] and r["compress"] and r["engulf"] and r["ctrl"] and r["close_strong"]),
        ("pb atr_hi+compress+engulf+ctrl+already8", pb, lambda r: r["atr_hi"] and r["compress"] and r["engulf"] and r["ctrl"] and r["already8"] and r["already_lt25"]),
        ("pb atr_hi+compress_soft+engulf+ctrl", pb, lambda r: r["atr_hi"] and r["compress_soft"] and r["engulf"] and r["ctrl"]),
        ("pb atr_hi+compress+engulf_close+ctrl", pb, lambda r: r["atr_hi"] and r["compress"] and r["engulf_close"] and r["ctrl"]),
        ("pb atr_hi+compress+engulf+ctrl+held+htf", pb, lambda r: r["atr_hi"] and r["compress"] and r["engulf"] and r["ctrl"] and r["held"] and r["htf_with"]),
        ("pb atr_ok+compress+engulf+ctrl", pb, lambda r: r["atr_ok"] and r["compress"] and r["engulf"] and r["ctrl"]),
        ("pb compress+engulf+ctrl+htf", pb, lambda r: r["compress"] and r["engulf"] and r["ctrl"] and r["htf_with"]),
        ("pb atr_hi+engulf+ctrl+htf+!ext", pb, lambda r: r["atr_hi"] and r["engulf"] and r["ctrl"] and r["htf_with"] and r["not_extreme"]),
        ("pb atr_hi+compress+ctrl+htf+close_strong", pb, lambda r: r["atr_hi"] and r["compress"] and r["ctrl"] and r["htf_with"] and r["close_strong"]),
        ("ign atr_hi+compress+engulf+ctrl", ign, lambda r: r["atr_hi"] and r["compress"] and r["engulf"] and r["ctrl"]),
        ("ign atr_hi+compress+engulf+ctrl+htf", ign, lambda r: r["atr_hi"] and r["compress"] and r["engulf"] and r["ctrl"] and r["htf_with"]),
        ("ign ctrl+!ext+held+htf+close_strong", ign, lambda r: r["ctrl"] and r["not_extreme"] and r["held"] and r["htf_with"] and r["close_strong"]),
        ("ign ctrl+!ext+held+htf+ad+big_body", ign, lambda r: r["ctrl"] and r["not_extreme"] and r["held"] and r["htf_with"] and r["ad"] and r["big_body"]),
        ("ign IGN100 room+disp10+bounce+ctrl", ign, lambda r: r["ctrl"] and r["room_ok"] and r["disp10"] and r["bounce"]),
        ("ign IGN100+htf", ign, lambda r: r["ctrl"] and r["room_ok"] and r["disp10"] and r["bounce"] and r["htf_with"]),
    ]
    for name, rows, pred in focus:
        score(name, rows, pred, "1d")
        score(name, rows, pred, "all")

    # Exhaustive around lead family
    print("\n--- exhaustive around lead ---", flush=True)
    lead_feats = [
        "atr_hi",
        "compress",
        "compress_soft",
        "engulf",
        "engulf_close",
        "ctrl",
        "not_extreme",
        "held",
        "ad",
        "htf_with",
        "close_strong",
        "am",
        "already8",
        "big_body",
        "disp08",
        "body_dom",
        "hl3",
        "tight_wick",
    ]
    hunt = []
    for k in (3, 4, 5, 6):
        for combo in combinations(lead_feats, k):
            if "ctrl" not in combo:
                continue
            # require at least one of compress*/engulf*
            if not any(x in combo for x in ("compress", "compress_soft", "engulf", "engulf_close", "atr_hi")):
                continue
            hit = [r for r in pb if all(r.get(f) for f in combo)]
            for book, use, min_n in (("1d", one_per_day(hit), 12), ("all", hit, 20)):
                st = pack(use, "m25_first", mid)
                if st["n"] < min_n or st["prec"] is None or st["prec"] < 75:
                    continue
                # require both halves non-empty for HIGH claims
                hunt.append(
                    {
                        "name": "pb|" + book + "|" + "+".join(combo),
                        **st,
                        "verdict": verdict(st, min_n=min_n, min_half=5 if book == "1d" else 8),
                        "m25": pack(use, "m25", mid)["prec"],
                        "clean15": pack(use, "clean15", mid)["prec"],
                        "samples": use[:10],
                    }
                )
    hunt.sort(
        key=lambda x: (
            0
            if x["verdict"] == "PROVEN_100"
            else 1
            if x["verdict"] == "PROMISING_95"
            else 2
            if x["verdict"] == "HIGH_85"
            else 3
            if x["verdict"] == "HIGH_75"
            else 4,
            -(x["prec"] or 0),
            -(x["oos_prec"] or 0),
            -(x["train_prec"] or 0),
            -x["n"],
        )
    )
    seen = set()
    hunt_u = []
    for hrow in hunt:
        if hrow["name"] in seen:
            continue
        seen.add(hrow["name"])
        hunt_u.append(hrow)
    hunt_u = hunt_u[:50]
    print(f"hunt kept={len(hunt_u)}", flush=True)
    for hrow in hunt_u[:20]:
        print(
            f"  {hrow['verdict']} {hrow['name']}: n={hrow['n']} m25f={hrow['prec']}% "
            f"tr={hrow['train_prec']}% oos={hrow['oos_prec']}% c15={hrow['clean15']}%",
            flush=True,
        )

    # Rank best non-THIN
    pool = [r for r in results if r["verdict"] != "THIN"] + [h for h in hunt_u if h["verdict"] != "THIN"]
    pool.sort(
        key=lambda x: (
            0
            if x["verdict"] == "PROVEN_100"
            else 1
            if x["verdict"] == "PROMISING_95"
            else 2
            if x["verdict"] == "HIGH_85"
            else 3
            if x["verdict"] == "HIGH_75"
            else 4,
            -(x["prec"] or 0),
            -(x["oos_prec"] or 0),
            -x["n"],
        )
    )
    best = pool[0] if pool else (hunt_u[0] if hunt_u else (results[0] if results else None))

    lines = [
        "# NIFTY 1m — Entry accuracy **v5** (focus · HTF fixed)",
        "",
        "> Follow-up to v4 lead: `pb atr_hi+compress+engulf+ctrl` @ ~80% m25_first. HTF bias key fixed (`up`/`down`).",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS **{mid}**.",
        "",
        f"Pullback cands **{len(pb)}** · Ignition **{len(ign)}** · HTF-with on pb "
        f"**{100*sum(1 for r in pb if r['htf_with'])/max(len(pb),1):.1f}%**",
        "",
        "## 1) Focus gates",
        "",
        "| Gate | Verdict | n | m25_first% | Train | OOS | raw m25% | clean15% | MFE | MAE |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in sorted(results, key=lambda x: (0 if "HIGH" in x["verdict"] or "PROVEN" in x["verdict"] or "PROMISING" in x["verdict"] else 1, -(x["prec"] or 0))):
        lines.append(
            f"| `{r['name']}` | **{r['verdict']}** | {r['n']} | **{r['prec']}** | {r['train_prec']} | "
            f"{r['oos_prec']} | {r['m25']} | {r['clean15']} | {r['avg_mfe']} | {r['avg_mae']} |"
        )

    lines += ["", "## 2) Exhaustive around lead (≥75%)", ""]
    if not hunt_u:
        lines.append("_None._")
    else:
        lines += [
            "| Rule | Verdict | n | m25_first% | Train | OOS | m25% | clean15% |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for hrow in hunt_u[:30]:
            lines.append(
                f"| `{hrow['name']}` | **{hrow['verdict']}** | {hrow['n']} | **{hrow['prec']}** | "
                f"{hrow['train_prec']} | {hrow['oos_prec']} | {hrow['m25']} | {hrow['clean15']} |"
            )

    lines += ["", "## 3) Most accurate logic", ""]
    if best:
        lines += [
            f"**Best effort:** `{best['name']}` · **{best['verdict']}**",
            f"- m25_first **{best['prec']}%** · TRAIN **{best['train_prec']}%** · OOS **{best['oos_prec']}%** · n={best['n']}",
            f"- raw m25 **{best.get('m25')}%** · clean15 **{best.get('clean15')}%**",
            f"- avg MFE {best.get('avg_mfe')} · avg MAE {best.get('avg_mae')}",
            "",
            "### Entry rule (side + price)",
            "",
            "```",
            "1) Wait for bull_run2/3 or bear_run2/3 on 1m",
            "2) Within 8 bars: opposite-color pullback that touches ignition bar range",
            "3) Next same-color continuation bar = ENTRY BAR",
            "4) Filters (best): atr≥10 + prior bar compress + engulf + control close",
            "SIDE  : BUY/SELL from run direction",
            "ENTRY : close of continuation bar",
            "```",
            "",
            "### Samples",
            "",
            "| Day | HM | Side | Entry | MFE | MAE | m25_first | clean15 |",
            "|---|---|---|---:|---:|---:|---|---|",
        ]
        for x in (best.get("samples") or [])[:12]:
            lines.append(
                f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | "
                f"{x['mfe']} | {x['mae']} | {x['m25_first']} | {x['clean15']} |"
            )
    else:
        lines.append("_No viable gate._")

    high85 = [x for x in pool if x["verdict"] in ("PROVEN_100", "PROMISING_95", "HIGH_85")]
    lines += [
        "",
        "## 4) Ship decision",
        "",
        f"- Gates ≥85% walk-forward: **{len(high85)}**",
        "- Do **not** replace live IGN100 claiming 100% one-way unless PROVEN_100 / PROMISING_95 appears.",
        f"- Current best accuracy class: **{best['verdict'] if best else 'n/a'}** @ **{best['prec'] if best else 'n/a'}%** m25_first.",
        "",
        f"_Generated in {time.time() - t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps({"best": best, "focus": results, "hunt": hunt_u[:40], "high85": high85}, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT}", flush=True)
    if best:
        print(f"BEST={best['name']} {best['verdict']} prec={best['prec']}%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
