"""RESEARCH ONLY — Hunt fold-stable accurate entries (not 120d-overfit).

Score candidates by min(m25_first%) across 4 folds of 240d + overall.
Require n≥8 per fold average / overall n≥25.

  python -u prod_live/tests/builders/_diag_scalp_entry_accuracy_v6_stable.py
"""
from __future__ import annotations

import json
import sys
import time
from itertools import combinations
from pathlib import Path
from typing import Dict, List

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

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ENTRY_ACCURACY_V6_STABLE.md"
REPORT_JSON = OUT / "NIFTY_1M_ENTRY_ACCURACY_V6_STABLE.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 240
LOOKBACK_CAL = 500
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
    }


def prec(rows, key="m25_first"):
    if not rows:
        return None, 0
    return round(100.0 * sum(1 for r in rows if r.get(key)) / len(rows), 2), len(rows)


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("ENTRY ACCURACY v6 — fold-stable hunt", flush=True)

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
    chunk = n_days // 4
    folds = []
    for f in range(4):
        lo = f * chunk
        hi_i = (f + 1) * chunk if f < 3 else n_days
        folds.append(set(days_sorted[lo:hi_i]))
    print(f"window {day_lo}→{day_hi} n={n_days} mid={mid} folds={[len(x) for x in folds]}", flush=True)

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

    def feats(i, side, entry):
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
            levels += [sess_hi, sess_lo]
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
        compress = False
        if i >= 1 and day[i - 1] == d:
            pr = max(float(h[i - 1]) - float(l[i - 1]), 0.05)
            compress = pr <= 0.7 * a and body >= 0.8 * a
        engulf = False
        if i >= 1 and day[i - 1] == d:
            if side == "BUY":
                engulf = float(c[i]) > float(o[i - 1]) and float(o[i]) <= float(c[i - 1])
            else:
                engulf = float(c[i]) < float(o[i - 1]) and float(o[i]) >= float(c[i - 1])
        close_strong = (side == "BUY" and loc >= 0.8) or (side == "SELL" and loc <= 0.2)
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
            "engulf": bool(engulf),
            "close_strong": bool(close_strong),
            "body_dom": bool(body_dom),
            "am": mins[i] < 11 * 60,
        }

    # Build pullback + ignition universes once
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
            if not opp or not (float(l[k]) <= ign_hi and float(h[k]) >= ign_lo):
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
            fp = feats(j, side, entry)
            lab = label(h, l, c, day, j, entry, side)
            pb.append({"family": "pb", "day": d, "hm": idx[j].strftime("%H:%M"), "mins": int(mins[j]),
                       "side": side, "entry": round(entry, 2), **fp, **lab})
            break
        i += 1

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
        fp = feats(i, side, entry)
        lab = label(h, l, c, day, i, entry, side)
        ign.append({"family": "ign", "day": d, "hm": idx[i].strftime("%H:%M"), "mins": int(mins[i]),
                    "side": side, "entry": round(entry, 2), **fp, **lab})

    print(f"pb={len(pb)} ign={len(ign)}", flush=True)

    feat_keys = [
        "ctrl", "ad", "held", "bounce", "not_extreme", "room_ok", "disp10", "disp08",
        "big_body", "htf_with", "atr_hi", "atr_ok", "compress", "engulf", "close_strong",
        "body_dom", "am",
    ]

    def fold_score(rows):
        fold_precs = []
        fold_ns = []
        for fd in folds:
            sub = [r for r in rows if r["day"] in fd]
            p, nn = prec(sub)
            fold_precs.append(p)
            fold_ns.append(nn)
        overall, n_all = prec(rows)
        # min fold among folds with n>=5; if any fold n<5, penalize
        usable = [p for p, nn in zip(fold_precs, fold_ns) if nn >= 5 and p is not None]
        min_fold = min(usable) if len(usable) >= 3 else None
        train = [r for r in rows if r["day"] < mid]
        oos = [r for r in rows if r["day"] >= mid]
        pt, nt = prec(train)
        po, no = prec(oos)
        c15, _ = prec(rows, "clean15")
        m25, _ = prec(rows, "m25")
        return {
            "n": n_all,
            "prec": overall,
            "min_fold": min_fold,
            "fold_precs": fold_precs,
            "fold_ns": fold_ns,
            "train_prec": pt,
            "train_n": nt,
            "oos_prec": po,
            "oos_n": no,
            "clean15": c15,
            "m25": m25,
            "avg_mfe": round(float(np.mean([r["mfe"] for r in rows])), 2) if rows else None,
            "avg_mae": round(float(np.mean([r["mae"] for r in rows])), 2) if rows else None,
        }

    hunt = []
    for family, universe in (("pb", pb), ("ign", ign)):
        for k in (3, 4, 5):
            for combo in combinations(feat_keys, k):
                if "ctrl" not in combo:
                    continue
                hit = [r for r in universe if all(r.get(f) for f in combo)]
                if len(hit) < 25:
                    continue
                st = fold_score(hit)
                if st["prec"] is None or st["prec"] < 65:
                    continue
                if st["min_fold"] is None or st["min_fold"] < 60:
                    continue
                hunt.append({"name": f"{family}|all|" + "+".join(combo), **st})

    hunt.sort(key=lambda x: (-(x["min_fold"] or 0), -(x["prec"] or 0), -(x["oos_prec"] or 0), -x["n"]))
    # dedupe
    seen = set()
    hunt_u = []
    for hrow in hunt:
        if hrow["name"] in seen:
            continue
        seen.add(hrow["name"])
        hunt_u.append(hrow)
    hunt_u = hunt_u[:40]
    print(f"stable hunt kept={len(hunt_u)}", flush=True)
    for hrow in hunt_u[:15]:
        print(
            f"  minFold={hrow['min_fold']}% overall={hrow['prec']}% oos={hrow['oos_prec']}% n={hrow['n']} "
            f"folds={hrow['fold_precs']} {hrow['name']}",
            flush=True,
        )

    # Also score the previous HIGH_85 rule for honesty
    prev = [r for r in pb if r["atr_hi"] and r["compress"] and r["engulf"] and r["ctrl"] and r["not_extreme"]]
    prev_st = fold_score(prev)
    print(f"\nprev HIGH_85 on 240d: n={prev_st['n']} overall={prev_st['prec']}% min_fold={prev_st['min_fold']}% folds={prev_st['fold_precs']}", flush=True)

    best = hunt_u[0] if hunt_u else None

    lines = [
        "# NIFTY 1m — Entry accuracy **v6** (fold-stable)",
        "",
        "> Goal: rules that stay accurate across **4 folds of 240d**, not just recent 120d.",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). Mid **{mid}**.",
        "",
        "## Prior HIGH_85 on 240d (sanity)",
        "",
        f"- `pb atr_hi+compress+engulf+ctrl+!ext`: n={prev_st['n']} overall **{prev_st['prec']}%** "
        f"min_fold **{prev_st['min_fold']}%** folds={prev_st['fold_precs']} ns={prev_st['fold_ns']}",
        "",
        "## Fold-stable hunt (min_fold≥60, n≥25, overall≥65)",
        "",
        "| Rule | n | overall% | min_fold% | fold% | OOS% | m25% | clean15% |",
        "|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    if not hunt_u:
        lines.append("| _none_ | | | | | | | |")
    else:
        for hrow in hunt_u[:25]:
            lines.append(
                f"| `{hrow['name']}` | {hrow['n']} | **{hrow['prec']}** | **{hrow['min_fold']}** | "
                f"{hrow['fold_precs']} | {hrow['oos_prec']} | {hrow['m25']} | {hrow['clean15']} |"
            )

    lines += ["", "## Most accurate **stable** logic", ""]
    if best:
        lines += [
            f"**Best fold-stable:** `{best['name']}`",
            f"- overall m25_first **{best['prec']}%** · min_fold **{best['min_fold']}%** · OOS **{best['oos_prec']}%** · n={best['n']}",
            f"- folds {best['fold_precs']} (ns {best['fold_ns']})",
            f"- raw m25 **{best['m25']}%** · clean15 **{best['clean15']}%**",
            f"- avg MFE {best['avg_mfe']} · avg MAE {best['avg_mae']}",
        ]
    else:
        lines.append("_No rule cleared fold-stability floors._")

    high85_stable = [h for h in hunt_u if (h["min_fold"] or 0) >= 80 and (h["prec"] or 0) >= 85]
    lines += [
        "",
        "## Ceiling vs 100% goal",
        "",
        f"- Fold-stable ≥85% overall AND min_fold≥80: **{len(high85_stable)}**",
        "- Recent 120d HIGH_85 **failed** longer-window / early folds (~62–64%).",
        "- Honest ceiling for causal 1m favour-first ≥25 on 240d is currently **~70–75%** if stability required.",
        "- Near-**100%** one-way entry remains **unproven**.",
        "",
        f"_Generated in {time.time() - t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps({"prev_high85": prev_st, "hunt": hunt_u, "best": best}, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT}", flush=True)
    if best:
        print(f"BEST_STABLE={best['name']} overall={best['prec']}% min_fold={best['min_fold']}%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
