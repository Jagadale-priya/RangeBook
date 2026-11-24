"""RESEARCH ONLY — Accuracy v4: discriminator + pullback + OR-retest hunt.

Prior: ignition/join tops ~52–54% m25_first. IGN100 was 100% raw m25 (n=12)
but weak on favour-first. This pass:

1) Mine feature LIFT on ignition universe (winners vs losers)
2) Pullback entries: after run2/3, wait for 1–2 bar reverse into ignition range, enter continuation
3) OR15/OR30 break+retest (body close) — previously PROVEN for R:R; re-score m25_first
4) Exhaustive AND of top-lift features, walk-forward ≥80/85/95/100

  python -u prod_live/tests/builders/_diag_scalp_entry_accuracy_v4_disc.py
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
REPORT = OUT / "NIFTY_1M_ENTRY_ACCURACY_V4_DISC.md"
REPORT_JSON = OUT / "NIFTY_1M_ENTRY_ACCURACY_V4_DISC.json"

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
    if (st["prec"] or 0) >= 85 and (st["oos_prec"] or 0) >= 80:
        return "HIGH_85"
    if (st["prec"] or 0) >= 75 and (st["oos_prec"] or 0) >= 70:
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
    print("ENTRY ACCURACY v4 — discriminator + pullback + OR", flush=True)

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
    print(f"window {day_lo}→{day_hi} n={n_days} OOS≥{mid}", flush=True)

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
    rsi = df1["rsi14"].astype(float).values if "rsi14" in df1.columns else np.full(len(c), 50.0)
    day = np.array([str(ts.date()) for ts in df1.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df1.index])
    idx = df1.index
    n = len(c)

    # Session bar indices
    sess = {}
    for d in keep:
        sess[d] = np.where(day == d)[0]

    # OR15 / OR30 levels per day (first 15 / 30 mins from 09:15)
    or_lv = {}
    for d, ii in sess.items():
        # NSE open 09:15 → OR15 ends 09:29, OR30 ends 09:44
        or15 = [j for j in ii if 9 * 60 + 15 <= mins[j] <= 9 * 60 + 29]
        or30 = [j for j in ii if 9 * 60 + 15 <= mins[j] <= 9 * 60 + 44]
        if not or15:
            continue
        or_lv[d] = {
            "or15_hi": float(np.max(h[or15])),
            "or15_lo": float(np.min(l[or15])),
            "or30_hi": float(np.max(h[or30])) if or30 else float(np.max(h[or15])),
            "or30_lo": float(np.min(l[or30])) if or30 else float(np.min(l[or15])),
            "day_open": float(o[or15[0]]),
        }

    def feat_pack(i, side, entry, ign_i=None):
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
        room_up = 999.0 if resist is None else resist - entry
        room_dn = 999.0 if support is None else entry - support
        room_fav = room_up if side == "BUY" else room_dn
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
        htf = htf_bias_lookup(bias15, idx[i])
        htf_with = (side == "BUY" and htf == "bull") or (side == "SELL" and htf == "bear")
        # distance from day open / OR
        od = or_lv.get(d)
        from_open = 0.0
        or15_broke = False
        or30_broke = False
        or_room = 999.0
        if od:
            from_open = entry - od["day_open"] if side == "BUY" else od["day_open"] - entry
            if side == "BUY":
                or15_broke = entry > od["or15_hi"]
                or30_broke = entry > od["or30_hi"]
                or_room = (od["or15_hi"] - entry) if entry < od["or15_hi"] else 999.0
            else:
                or15_broke = entry < od["or15_lo"]
                or30_broke = entry < od["or30_lo"]
                or_room = (entry - od["or15_lo"]) if entry > od["or15_lo"] else 999.0
        # micro structure last 3 bars
        hl3 = True
        if i >= 2 and day[i - 2] == d:
            if side == "BUY":
                hl3 = l[i] >= l[i - 1] - 0.05 and l[i - 1] >= l[i - 2] - 0.05
            else:
                hl3 = h[i] <= h[i - 1] + 0.05 and h[i - 1] <= h[i - 2] + 0.05
        # consecutive closes in favour
        cc2 = False
        if i >= 1 and day[i - 1] == d:
            if side == "BUY":
                cc2 = c[i] > c[i - 1]
            else:
                cc2 = c[i] < c[i - 1]
        cc3 = False
        if i >= 2 and day[i - 2] == d:
            if side == "BUY":
                cc3 = c[i] > c[i - 1] > c[i - 2]
            else:
                cc3 = c[i] < c[i - 1] < c[i - 2]
        # impulse size from ignition if known
        already = 0.0
        if ign_i is not None and ign_i <= i:
            if side == "BUY":
                already = float(c[i]) - float(l[ign_i])
            else:
                already = float(h[ign_i]) - float(c[i])
        # RSI not extreme against
        rsi_ok = (side == "BUY" and rsi[i] < 70) or (side == "SELL" and rsi[i] > 30)
        rsi_mid = 40 <= rsi[i] <= 60
        # time buckets
        am = mins[i] < 11 * 60
        midday = 11 * 60 <= mins[i] < 13 * 60
        pm = mins[i] >= 13 * 60
        # tight first adverse proxy: wick against small
        wick_ag = (float(c[i]) - float(l[i])) if side == "BUY" else (float(h[i]) - float(c[i]))
        wick_fav = (float(h[i]) - float(c[i])) if side == "BUY" else (float(c[i]) - float(l[i]))
        tight_wick = wick_ag <= 0.35 * a
        # body dominance
        body_dom = body >= 0.55 * rng
        # ATR regime
        atr_ok = a >= 6.0
        atr_hi = a >= 10.0
        # distance already from session extreme (not at extreme)
        not_extreme = not into_ext
        # favour room vs adverse room
        room_ok = room_fav >= 1.5 * a and not_extreme
        runway2 = room_fav >= 2.0 * a
        # compression then expand: prior bar range small, this body big
        compress = False
        if i >= 1 and day[i - 1] == d:
            pr = max(float(h[i - 1]) - float(l[i - 1]), 0.05)
            compress = pr <= 0.7 * a and body >= 0.8 * a
        # engulf prior
        engulf = False
        if i >= 1 and day[i - 1] == d:
            if side == "BUY":
                engulf = float(c[i]) > float(o[i - 1]) and float(o[i]) <= float(c[i - 1])
            else:
                engulf = float(c[i]) < float(o[i - 1]) and float(o[i]) >= float(c[i - 1])
        # close in upper/lower 80%
        close_strong = (side == "BUY" and loc >= 0.8) or (side == "SELL" and loc <= 0.2)
        # from_open already meaningful but not exhausted
        open_push = from_open >= 8.0
        open_fresh = from_open <= 40.0
        return {
            "ctrl": bool(ctrl),
            "ad": bool(ad),
            "held": bool(held),
            "bounce": bool(bounce),
            "not_extreme": bool(not_extreme),
            "room_ok": bool(room_ok),
            "runway2": bool(runway2),
            "disp10": body >= 1.0 * a,
            "disp08": body >= 0.8 * a,
            "big_body": body >= max(8.0, 0.6 * a),
            "di_ok": bool(di_ok),
            "vwap_with": bool(vwap_with),
            "gate34": bool(gate34),
            "htf_with": bool(htf_with),
            "or15_broke": bool(or15_broke),
            "or30_broke": bool(or30_broke),
            "hl3": bool(hl3),
            "cc2": bool(cc2),
            "cc3": bool(cc3),
            "rsi_ok": bool(rsi_ok),
            "rsi_mid": bool(rsi_mid),
            "am": bool(am),
            "midday": bool(midday),
            "pm": bool(pm),
            "tight_wick": bool(tight_wick),
            "body_dom": bool(body_dom),
            "atr_ok": bool(atr_ok),
            "atr_hi": bool(atr_hi),
            "compress": bool(compress),
            "engulf": bool(engulf),
            "close_strong": bool(close_strong),
            "open_push": bool(open_push),
            "open_fresh": bool(open_fresh),
            "already8": already >= 8.0,
            "already12": already >= 12.0,
            "already15": already >= 15.0,
            "already_lt25": already < 25.0,
            "atr": round(a, 2),
            "body": round(body, 2),
            "already": round(already, 2),
            "from_open": round(from_open, 2),
            "room_fav": round(room_fav if room_fav < 900 else 999.0, 2),
        }

    # ---------- A) Ignition universe (color flip) ----------
    ign_rows: List[dict] = []
    for i in range(1, n - 1):
        d = day[i]
        if d not in keep or not (MINS_LO <= mins[i] <= MINS_HI):
            continue
        if day[i - 1] != d:
            continue
        green = c[i] > o[i]
        red = c[i] < o[i]
        prev_g = c[i - 1] > o[i - 1]
        prev_r = c[i - 1] < o[i - 1]
        if green and prev_r:
            side = "BUY"
        elif red and prev_g:
            side = "SELL"
        else:
            continue
        entry = float(c[i])
        fp = feat_pack(i, side, entry, ign_i=i)
        lab = label(h, l, c, day, i, entry, side)
        ok25, _, _, _ = path_ma_trail_strict(h, l, c, ema34, i, side, 25.0)
        ign_rows.append(
            {
                "family": "ignition",
                "day": d,
                "hm": idx[i].strftime("%H:%M"),
                "mins": int(mins[i]),
                "side": side,
                "entry": round(entry, 2),
                "entry_i": i,
                "ign_i": i,
                "t25": bool(ok25),
                **fp,
                **lab,
            }
        )
    print(f"ignition cands={len(ign_rows)}", flush=True)

    # ---------- B) Pullback after run2/3 ----------
    # After streak of 2–3 same-color bars, wait ≤8 bars for opposite color that
    # overlaps ignition bar range, then enter on next same-color continuation close.
    pb_rows: List[dict] = []
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
        # search pullback
        found = False
        for k in range(i + 1, min(i + 9, n - 1)):
            if day[k] != d:
                break
            # opposite color touching ignition range
            opp = (bull and c[k] < o[k]) or ((not bull) and c[k] > o[k])
            if not opp:
                continue
            touch = (float(l[k]) <= ign_hi and float(h[k]) >= ign_lo)
            if not touch:
                continue
            # next continuation bar
            j = k + 1
            if j >= n or day[j] != d:
                break
            cont = (bull and c[j] > o[j]) or ((not bull) and c[j] < o[j])
            if not cont:
                continue
            if not (MINS_LO <= mins[j] <= MINS_HI):
                break
            entry = float(c[j])
            # skip if already moved ≥25 from ign low/high (too late)
            if side == "BUY" and entry - ign_lo >= 25:
                break
            if side == "SELL" and ign_hi - entry >= 25:
                break
            fp = feat_pack(j, side, entry, ign_i=ign_i)
            lab = label(h, l, c, day, j, entry, side)
            ok25, _, _, _ = path_ma_trail_strict(h, l, c, ema34, j, side, 25.0)
            pb_rows.append(
                {
                    "family": "pullback",
                    "day": d,
                    "hm": idx[j].strftime("%H:%M"),
                    "mins": int(mins[j]),
                    "side": side,
                    "entry": round(entry, 2),
                    "entry_i": j,
                    "ign_i": ign_i,
                    "run_n": nb,
                    "t25": bool(ok25),
                    **fp,
                    **lab,
                }
            )
            found = True
            break
        i += 1
    print(f"pullback cands={len(pb_rows)}", flush=True)

    # ---------- C) OR15 / OR30 break + retest ----------
    or_rows: List[dict] = []
    for d, od in or_lv.items():
        ii = sess[d]
        # start after OR window
        for kind, hi_lv, lo_lv, after_m in (
            ("OR15", od["or15_hi"], od["or15_lo"], 9 * 60 + 30),
            ("OR30", od["or30_hi"], od["or30_lo"], 9 * 60 + 45),
        ):
            broke_up = broke_dn = False
            retested_up = retested_dn = False
            for i in ii:
                if mins[i] < after_m or mins[i] > MINS_HI:
                    continue
                # break = body close beyond
                if not broke_up and float(c[i]) > hi_lv:
                    broke_up = True
                    continue
                if not broke_dn and float(c[i]) < lo_lv:
                    broke_dn = True
                    continue
                # retest: touch level then close back in break direction
                if broke_up and not retested_up:
                    if float(l[i]) <= hi_lv + 0.5 * float(atr[i] if atr[i] > 0 else 8) and float(c[i]) > hi_lv:
                        # confirmation: close above OR high after touch
                        side = "BUY"
                        entry = float(c[i])
                        fp = feat_pack(i, side, entry, ign_i=i)
                        lab = label(h, l, c, day, i, entry, side)
                        ok25, _, _, _ = path_ma_trail_strict(h, l, c, ema34, i, side, 25.0)
                        or_rows.append(
                            {
                                "family": f"or_retest_{kind}",
                                "day": d,
                                "hm": idx[i].strftime("%H:%M"),
                                "mins": int(mins[i]),
                                "side": side,
                                "entry": round(entry, 2),
                                "entry_i": i,
                                "ign_i": i,
                                "t25": bool(ok25),
                                **fp,
                                **lab,
                            }
                        )
                        retested_up = True
                if broke_dn and not retested_dn:
                    if float(h[i]) >= lo_lv - 0.5 * float(atr[i] if atr[i] > 0 else 8) and float(c[i]) < lo_lv:
                        side = "SELL"
                        entry = float(c[i])
                        fp = feat_pack(i, side, entry, ign_i=i)
                        lab = label(h, l, c, day, i, entry, side)
                        ok25, _, _, _ = path_ma_trail_strict(h, l, c, ema34, i, side, 25.0)
                        or_rows.append(
                            {
                                "family": f"or_retest_{kind}",
                                "day": d,
                                "hm": idx[i].strftime("%H:%M"),
                                "mins": int(mins[i]),
                                "side": side,
                                "entry": round(entry, 2),
                                "entry_i": i,
                                "ign_i": i,
                                "t25": bool(ok25),
                                **fp,
                                **lab,
                            }
                        )
                        retested_dn = True
    print(f"OR retest cands={len(or_rows)}", flush=True)

    # ---------- Feature lift on ignition (train only) ----------
    BOOL_FEATS = [
        "ctrl",
        "ad",
        "held",
        "bounce",
        "not_extreme",
        "room_ok",
        "runway2",
        "disp10",
        "disp08",
        "big_body",
        "di_ok",
        "vwap_with",
        "gate34",
        "htf_with",
        "or15_broke",
        "or30_broke",
        "hl3",
        "cc2",
        "cc3",
        "rsi_ok",
        "rsi_mid",
        "am",
        "midday",
        "pm",
        "tight_wick",
        "body_dom",
        "atr_ok",
        "atr_hi",
        "compress",
        "engulf",
        "close_strong",
        "open_push",
        "open_fresh",
    ]
    ign_tr = [r for r in ign_rows if r["day"] < mid]
    base_rate = 100.0 * sum(1 for r in ign_tr if r["m25_first"]) / max(len(ign_tr), 1)
    lifts = []
    for f in BOOL_FEATS:
        sub = [r for r in ign_tr if r.get(f)]
        if len(sub) < 30:
            continue
        rate = 100.0 * sum(1 for r in sub if r["m25_first"]) / len(sub)
        lifts.append({"feat": f, "n": len(sub), "prec": round(rate, 2), "lift": round(rate - base_rate, 2)})
    lifts.sort(key=lambda x: (-x["lift"], -x["n"]))
    print(f"ignition train base m25_first={base_rate:.2f}%  top lifts:", flush=True)
    for x in lifts[:12]:
        print(f"  {x['feat']}: +{x['lift']}pp  prec={x['prec']}% n={x['n']}", flush=True)

    # ---------- Score families with curated + mined gates ----------
    results = []

    def score_family(name, rows, pred, key="m25_first"):
        hit = [r for r in rows if pred(r)]
        st_all = pack(hit, key, mid)
        one = one_per_day(hit)
        st_1d = pack(one, key, mid)
        st_c15 = pack(one, "clean15", mid)
        st_m25 = pack(one, "m25", mid)
        row = {
            "name": name,
            "key": key,
            "all": st_all,
            "one_per_day": st_1d,
            "clean15_1d": st_c15.get("prec"),
            "m25_1d": st_m25.get("prec"),
            "verdict_1d": verdict(st_1d),
            "verdict_all": verdict(st_all, min_n=20, min_half=8),
            "samples": one[:12],
        }
        results.append(row)
        print(
            f"  {name}: 1d n={st_1d['n']} m25f={st_1d['prec']}% OOS={st_1d['oos_prec']}% "
            f"m25={st_m25.get('prec')}% c15={st_c15.get('prec')}% → {row['verdict_1d']}",
            flush=True,
        )
        return row

    print("\n--- curated gates ---", flush=True)
    curated = [
        ("ign ctrl+!ext+held+close_strong", ign_rows, lambda r: r["ctrl"] and r["not_extreme"] and r["held"] and r["close_strong"]),
        ("ign ctrl+!ext+held+htf+close_strong", ign_rows, lambda r: r["ctrl"] and r["not_extreme"] and r["held"] and r["htf_with"] and r["close_strong"]),
        ("ign ctrl+!ext+htf+compress", ign_rows, lambda r: r["ctrl"] and r["not_extreme"] and r["htf_with"] and r["compress"]),
        ("ign ctrl+!ext+htf+engulf+close_strong", ign_rows, lambda r: r["ctrl"] and r["not_extreme"] and r["htf_with"] and r["engulf"] and r["close_strong"]),
        ("ign ctrl+!ext+held+hl3+cc2", ign_rows, lambda r: r["ctrl"] and r["not_extreme"] and r["held"] and r["hl3"] and r["cc2"]),
        ("ign ctrl+!ext+ad+held+htf+am", ign_rows, lambda r: r["ctrl"] and r["not_extreme"] and r["ad"] and r["held"] and r["htf_with"] and r["am"]),
        ("ign ctrl+!ext+htf+or15+close_strong", ign_rows, lambda r: r["ctrl"] and r["not_extreme"] and r["htf_with"] and r["or15_broke"] and r["close_strong"]),
        ("ign ctrl+!ext+held+tight_wick+body_dom", ign_rows, lambda r: r["ctrl"] and r["not_extreme"] and r["held"] and r["tight_wick"] and r["body_dom"]),
        ("ign IGN100-like room+disp10+bounce", ign_rows, lambda r: r["ctrl"] and r["room_ok"] and r["disp10"] and r["bounce"]),
        ("ign IGN100+htf", ign_rows, lambda r: r["ctrl"] and r["room_ok"] and r["disp10"] and r["bounce"] and r["htf_with"]),
        ("ign IGN100+held+htf", ign_rows, lambda r: r["ctrl"] and r["room_ok"] and r["disp10"] and r["bounce"] and r["held"] and r["htf_with"]),
        ("pb run2/3 ctrl+!ext+held", pb_rows, lambda r: r["ctrl"] and r["not_extreme"] and r["held"]),
        ("pb ctrl+!ext+held+htf", pb_rows, lambda r: r["ctrl"] and r["not_extreme"] and r["held"] and r["htf_with"]),
        ("pb ctrl+!ext+held+ad+htf", pb_rows, lambda r: r["ctrl"] and r["not_extreme"] and r["held"] and r["ad"] and r["htf_with"]),
        ("pb ctrl+!ext+held+htf+already8+lt25", pb_rows, lambda r: r["ctrl"] and r["not_extreme"] and r["held"] and r["htf_with"] and r["already8"] and r["already_lt25"]),
        ("pb ctrl+!ext+htf+close_strong+already8", pb_rows, lambda r: r["ctrl"] and r["not_extreme"] and r["htf_with"] and r["close_strong"] and r["already8"] and r["already_lt25"]),
        ("pb ctrl+!ext+held+hl3+already12", pb_rows, lambda r: r["ctrl"] and r["not_extreme"] and r["held"] and r["hl3"] and r["already12"] and r["already_lt25"]),
        ("OR15 retest ctrl+htf", [r for r in or_rows if r["family"] == "or_retest_OR15"], lambda r: r["ctrl"] and r["htf_with"]),
        ("OR15 retest ctrl+held+htf", [r for r in or_rows if r["family"] == "or_retest_OR15"], lambda r: r["ctrl"] and r["held"] and r["htf_with"]),
        ("OR15 retest ctrl+held+ad+htf", [r for r in or_rows if r["family"] == "or_retest_OR15"], lambda r: r["ctrl"] and r["held"] and r["ad"] and r["htf_with"]),
        ("OR30 retest ctrl+htf", [r for r in or_rows if r["family"] == "or_retest_OR30"], lambda r: r["ctrl"] and r["htf_with"]),
        ("OR30 retest ctrl+held+htf", [r for r in or_rows if r["family"] == "or_retest_OR30"], lambda r: r["ctrl"] and r["held"] and r["htf_with"]),
        ("OR30 retest ctrl+held+ad+!ext", [r for r in or_rows if r["family"] == "or_retest_OR30"], lambda r: r["ctrl"] and r["held"] and r["ad"] and r["not_extreme"]),
        ("OR30 retest ctrl+held+htf+close_strong", [r for r in or_rows if r["family"] == "or_retest_OR30"], lambda r: r["ctrl"] and r["held"] and r["htf_with"] and r["close_strong"]),
    ]
    for name, rows, pred in curated:
        score_family(name, rows, pred)

    # ---------- Exhaustive hunt on top-lift features ----------
    print("\n--- exhaustive hunt (top-lift feats) ---", flush=True)
    top_feats = [x["feat"] for x in lifts if x["lift"] > 0][:14]
    # always include ctrl + not_extreme if present
    for must in ("ctrl", "not_extreme", "htf_with"):
        if must not in top_feats and must in BOOL_FEATS:
            top_feats.append(must)
    top_feats = list(dict.fromkeys(top_feats))[:16]
    print(f"hunt feats: {top_feats}", flush=True)

    hunt = []
    for family_name, universe in (
        ("ign", ign_rows),
        ("pb", pb_rows),
        ("OR15", [r for r in or_rows if r["family"] == "or_retest_OR15"]),
        ("OR30", [r for r in or_rows if r["family"] == "or_retest_OR30"]),
    ):
        for k in (3, 4, 5, 6):
            for combo in combinations(top_feats, k):
                if "ctrl" not in combo:
                    continue
                hit = [r for r in universe if all(r.get(f) for f in combo)]
                one = one_per_day(hit)
                st = pack(one, "m25_first", mid)
                if st["n"] < 12 or st["prec"] is None or st["prec"] < 75:
                    continue
                hunt.append(
                    {
                        "name": f"{family_name}|1d|" + "+".join(combo),
                        **st,
                        "verdict": verdict(st),
                        "clean15": pack(one, "clean15", mid)["prec"],
                        "m25": pack(one, "m25", mid)["prec"],
                        "samples": one[:8],
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
    hunt_u = hunt_u[:40]
    print(f"hunt ≥75% n≥12: {len(hunt)} kept={len(hunt_u)}", flush=True)
    for hrow in hunt_u[:15]:
        print(
            f"  {hrow['verdict']} {hrow['name']}: n={hrow['n']} m25f={hrow['prec']}% "
            f"OOS={hrow['oos_prec']}% m25={hrow['m25']}% c15={hrow['clean15']}%",
            flush=True,
        )

    # Also hunt raw m25 100% (like old IGN100) but report m25_first honestly
    print("\n--- perfect raw-m25 books (report m25_first too) ---", flush=True)
    perfect_m25 = []
    for family_name, universe in (
        ("ign", ign_rows),
        ("pb", pb_rows),
        ("OR15", [r for r in or_rows if r["family"] == "or_retest_OR15"]),
        ("OR30", [r for r in or_rows if r["family"] == "or_retest_OR30"]),
    ):
        for k in (3, 4, 5):
            for combo in combinations(
                ["ctrl", "not_extreme", "held", "ad", "bounce", "disp10", "room_ok", "htf_with", "close_strong", "compress", "engulf", "am"],
                k,
            ):
                if "ctrl" not in combo:
                    continue
                hit = [r for r in universe if all(r.get(f) for f in combo)]
                one = one_per_day(hit)
                st_m = pack(one, "m25", mid)
                if st_m["n"] < 10 or st_m["prec"] != 100.0:
                    continue
                if (st_m["train_prec"] or 0) != 100.0 or (st_m["oos_prec"] or 0) != 100.0:
                    continue
                if (st_m["train_n"] or 0) < 4 or (st_m["oos_n"] or 0) < 4:
                    continue
                st_f = pack(one, "m25_first", mid)
                perfect_m25.append(
                    {
                        "name": f"{family_name}|m25_100|" + "+".join(combo),
                        "m25": st_m,
                        "m25_first": st_f,
                        "clean15": pack(one, "clean15", mid)["prec"],
                        "samples": one[:10],
                    }
                )
    perfect_m25.sort(key=lambda x: (-(x["m25_first"]["prec"] or 0), -x["m25"]["n"]))
    print(f"perfect raw-m25 train+OOS books: {len(perfect_m25)}", flush=True)
    for p in perfect_m25[:8]:
        print(
            f"  {p['name']}: n={p['m25']['n']} m25=100% m25_first={p['m25_first']['prec']}% "
            f"OOS_m25f={p['m25_first']['oos_prec']}% c15={p['clean15']}%",
            flush=True,
        )

    # Best overall
    ranked = sorted(
        results,
        key=lambda g: (
            0
            if g["verdict_1d"] == "PROVEN_100"
            else 1
            if g["verdict_1d"] == "PROMISING_95"
            else 2
            if g["verdict_1d"] == "HIGH_85"
            else 3
            if g["verdict_1d"] == "HIGH_75"
            else 4,
            -(g["one_per_day"]["prec"] or 0),
            -(g["one_per_day"]["oos_prec"] or 0),
            -g["one_per_day"]["n"],
        ),
    )
    best = ranked[0] if ranked else None
    if hunt_u and (
        best is None
        or (hunt_u[0]["prec"] or 0) > (best["one_per_day"]["prec"] or 0)
        or hunt_u[0]["verdict"] in ("PROVEN_100", "PROMISING_95", "HIGH_85")
        and best["verdict_1d"] == "WEAK"
    ):
        # promote hunt winner as best if stronger
        hw = hunt_u[0]
        best_hunt = {
            "name": hw["name"],
            "one_per_day": hw,
            "verdict_1d": hw["verdict"],
            "clean15_1d": hw.get("clean15"),
            "m25_1d": hw.get("m25"),
            "samples": hw.get("samples", []),
        }
    else:
        best_hunt = None

    # ---------- Report ----------
    lines = [
        "# NIFTY 1m — Entry accuracy **v4** (discriminator + pullback + OR)",
        "",
        "> Deeper pass after v2 (~52%) and v3 join (~54%). Mines feature lift, pullback joins, OR break+retest.",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS **{mid}**.",
        "",
        "## 0) Universe sizes",
        "",
        f"- Ignition (color flip): **{len(ign_rows)}**",
        f"- Pullback after run2/3: **{len(pb_rows)}**",
        f"- OR retest: **{len(or_rows)}**",
        f"- Ignition TRAIN base m25_first: **{base_rate:.2f}%**",
        "",
        "## 1) Feature lift (TRAIN ignition · m25_first)",
        "",
        "| Feat | n | prec% | lift pp |",
        "|---|---:|---:|---:|",
    ]
    for x in lifts[:20]:
        lines.append(f"| `{x['feat']}` | {x['n']} | {x['prec']} | {x['lift']:+.2f} |")

    lines += [
        "",
        "## 2) Curated gates (1/day · m25_first)",
        "",
        "| Gate | Verdict | n | m25_first% | OOS | raw m25% | clean15% | avg MFE | avg MAE |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for g in ranked:
        s = g["one_per_day"]
        lines.append(
            f"| `{g['name']}` | **{g['verdict_1d']}** | {s['n']} | **{s['prec']}** | {s['oos_prec']} | "
            f"{g.get('m25_1d')} | {g.get('clean15_1d')} | {s['avg_mfe']} | {s['avg_mae']} |"
        )

    lines += ["", "## 3) Exhaustive hunt ≥75% m25_first (1/day)", ""]
    if not hunt_u:
        lines.append("_None._")
    else:
        lines += [
            "| Rule | Verdict | n | m25_first% | OOS | raw m25% | clean15% |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
        for hrow in hunt_u[:25]:
            lines.append(
                f"| `{hrow['name']}` | **{hrow['verdict']}** | {hrow['n']} | **{hrow['prec']}** | "
                f"{hrow['oos_prec']} | {hrow['m25']} | {hrow['clean15']} |"
            )

    lines += ["", "## 4) Perfect raw-m25 books (honest m25_first)", ""]
    if not perfect_m25:
        lines.append("_None with train+OOS 100% raw m25, n≥10._")
    else:
        lines += [
            "| Rule | n | m25 | m25_first% | OOS m25_first | clean15% |",
            "|---|---:|---|---:|---:|---:|",
        ]
        for p in perfect_m25[:15]:
            lines.append(
                f"| `{p['name']}` | {p['m25']['n']} | 100% | **{p['m25_first']['prec']}** | "
                f"{p['m25_first']['oos_prec']} | {p['clean15']} |"
            )

    show = best_hunt if best_hunt and (best_hunt["verdict_1d"] in ("PROVEN_100", "PROMISING_95", "HIGH_85", "HIGH_75") or (best_hunt["one_per_day"].get("prec") or 0) >= (best["one_per_day"]["prec"] or 0 if best else 0)) else best
    lines += ["", "## 5) Most accurate logic this pass", ""]
    if show:
        s = show["one_per_day"] if "one_per_day" in show else show
        name = show["name"]
        verd = show.get("verdict_1d") or show.get("verdict")
        lines += [
            f"**Best effort:** `{name}` · {verd}",
            f"- 1/day m25_first **{s.get('prec')}%** OOS **{s.get('oos_prec')}%** n={s.get('n')}",
            f"- raw m25 **{show.get('m25_1d', s.get('m25'))}%** · clean15 **{show.get('clean15_1d', s.get('clean15'))}%**",
            f"- avg MFE {s.get('avg_mfe')} · avg MAE {s.get('avg_mae')}",
            "",
            "### Samples",
            "",
            "| Day | HM | Side | Entry | MFE | MAE | m25_first | clean15 |",
            "|---|---|---|---:|---:|---:|---|---|",
        ]
        for x in (show.get("samples") or [])[:12]:
            lines.append(
                f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | "
                f"{x['mfe']} | {x['mae']} | {x['m25_first']} | {x['clean15']} |"
            )
    else:
        lines.append("_No viable gate._")

    lines += [
        "",
        "## 6) Action vs live IGN100",
        "",
        "- Keep judging on **m25_first** (favour-first), not raw m25 alone.",
        "- Replace IGN100 only if this pass yields PROVEN_100 / PROMISING_95 on m25_first.",
        "- If best remains WEAK/HIGH_75: near-100% one-way entry is **not** established on 120d.",
        "",
        f"_Generated in {time.time() - t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    payload: Dict[str, Any] = {
        "window": [day_lo, day_hi],
        "mid": mid,
        "base_rate_train": base_rate,
        "lifts": lifts[:25],
        "curated": [
            {
                "name": g["name"],
                "verdict": g["verdict_1d"],
                **g["one_per_day"],
                "clean15": g.get("clean15_1d"),
                "m25": g.get("m25_1d"),
            }
            for g in ranked
        ],
        "hunt": hunt_u,
        "perfect_m25": [
            {
                "name": p["name"],
                "n": p["m25"]["n"],
                "m25_first": p["m25_first"]["prec"],
                "oos_m25_first": p["m25_first"]["oos_prec"],
                "clean15": p["clean15"],
            }
            for p in perfect_m25[:20]
        ],
        "best": {
            "name": show["name"] if show else None,
            "verdict": (show.get("verdict_1d") or show.get("verdict")) if show else None,
            "stats": (show.get("one_per_day") if show and "one_per_day" in show else show) if show else None,
        },
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {REPORT}", flush=True)
    if show:
        s = show["one_per_day"] if "one_per_day" in show else show
        print(f"BEST={show['name']} {show.get('verdict_1d') or show.get('verdict')} prec={s.get('prec')}%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
