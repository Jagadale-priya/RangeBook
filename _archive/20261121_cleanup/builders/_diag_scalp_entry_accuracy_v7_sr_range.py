"""RESEARCH ONLY — Accurate entry via Range Support / Resistance.

Sources of range S/R (causal, live after form):
  OR15 / OR30 opening range
  Prior-day high/low
  Intraday fractal swing clusters (L=3, ≥2 touches)
  Session high/low so far (rolling extreme as resistance/support after leave)

Entries:
  BOUNCE  : leave ≥0.5×ATR → retest zone → control close away from level
  BREAK   : body close through → extend ≥0.5×ATR → retest zone → continue

Score: m25_first / clean15 / raw m25. Hunt filters ctrl/held/ad/htf/compress.

  python -u prod_live/tests/builders/_diag_scalp_entry_accuracy_v7_sr_range.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
REPORT = OUT / "NIFTY_1M_ENTRY_ACCURACY_V7_SR_RANGE.md"
REPORT_JSON = OUT / "NIFTY_1M_ENTRY_ACCURACY_V7_SR_RANGE.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 120
LOOKBACK_CAL = 240
FWD = 60
M25 = 25.0
LEAVE_ATR = 0.50
TOUCH_ATR = 0.40
EXT_ATR = 0.50
ZONE_HALF_ATR = 0.50


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


def verdict(st, min_n=15, min_half=6):
    if not st or st["n"] < min_n:
        return "THIN"
    if (
        st["prec"] == 100.0
        and st["train_prec"] == 100.0
        and st["oos_prec"] == 100.0
        and (st["train_n"] or 0) >= min_half
        and (st["oos_n"] or 0) >= min_half
    ):
        return "PROVEN_100"
    if (
        (st["prec"] or 0) >= 95
        and (st["train_prec"] or 0) >= 95
        and (st["oos_prec"] or 0) >= 95
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


def make_zone(px, a, kind):
    half = ZONE_HALF_ATR * a
    return {"px": float(px), "lo": float(px) - half, "hi": float(px) + half, "kind": kind}


def in_zone(lo, hi, z):
    return lo <= z["hi"] and hi >= z["lo"]


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("ENTRY ACCURACY v7 — Range S/R entries", flush=True)

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
    day = np.array([str(ts.date()) for ts in df1.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df1.index])
    idx = df1.index
    n = len(c)
    by_day: Dict[str, np.ndarray] = {d: np.where(day == d)[0] for d in keep}

    # Prior-day H/L
    prior_hl = {}
    for i, d in enumerate(days_sorted):
        if i == 0:
            continue
        prev = days_sorted[i - 1]
        ii = by_day[prev]
        prior_hl[d] = {"hi": float(np.max(h[ii])), "lo": float(np.min(l[ii]))}

    # Fractal swings L=3
    L = 3
    swing_hi, swing_lo = [], []
    for i in range(L, n - L):
        if h[i] >= np.max(h[i - L : i + L + 1]) - 1e-9:
            swing_hi.append((i, float(h[i])))
        if l[i] <= np.min(l[i - L : i + L + 1]) + 1e-9:
            swing_lo.append((i, float(l[i])))

    # Cluster same-day swings into zones (≥2)
    def cluster_day(pivots, merge_atr=0.5):
        by = defaultdict(list)
        for i, px in pivots:
            by[day[i]].append((i, px))
        zones = []
        for d, items in by.items():
            items = sorted(items, key=lambda x: x[1])
            if not items:
                continue
            cur = [items[0]]
            for p in items[1:]:
                a = float(atr[cur[-1][0]]) if np.isfinite(atr[cur[-1][0]]) else 8.0
                tol = max(4.0, merge_atr * a)
                if abs(p[1] - cur[-1][1]) <= tol:
                    cur.append(p)
                else:
                    if len(cur) >= 2:
                        live = max(x[0] for x in cur)
                        zones.append(
                            {
                                "day": d,
                                "live_i": live,
                                "px": float(np.mean([x[1] for x in cur])),
                                "n": len(cur),
                            }
                        )
                    cur = [p]
            if len(cur) >= 2:
                live = max(x[0] for x in cur)
                zones.append(
                    {
                        "day": d,
                        "live_i": live,
                        "px": float(np.mean([x[1] for x in cur])),
                        "n": len(cur),
                    }
                )
        return zones

    res_zones = cluster_day(swing_hi)  # resistance
    sup_zones = cluster_day(swing_lo)  # support

    def entry_feats(i, side, entry):
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        d = day[i]
        rng = max(float(h[i]) - float(l[i]), 0.05)
        loc = (float(c[i]) - float(l[i])) / rng
        green = c[i] > o[i]
        red = c[i] < o[i]
        body = abs(float(c[i]) - float(o[i]))
        ctrl = (side == "BUY" and loc >= 0.65 and green) or (side == "SELL" and loc <= 0.35 and red)
        di_ok = (side == "BUY" and pdi[i] > mdi[i]) or (side == "SELL" and mdi[i] > pdi[i])
        above = float(c[i]) >= float(ema34[i]) if np.isfinite(ema34[i]) else True
        gate34 = (side == "BUY" and above) or (side == "SELL" and not above)
        vw = float(vwap[i]) if np.isfinite(vwap[i]) else entry
        vwap_with = (side == "BUY" and entry >= vw) or (side == "SELL" and entry <= vw)
        held = bool(di_ok and gate34 and vwap_with)
        ad = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))
        htf_raw = htf_bias_lookup(bias15, idx[i])
        htf_with = (side == "BUY" and htf_raw == "up") or (side == "SELL" and htf_raw == "down")
        so_far = by_day[d][by_day[d] < i]
        if len(so_far):
            sess_hi, sess_lo = float(np.max(h[so_far])), float(np.min(l[so_far]))
        else:
            sess_hi = sess_lo = entry
        into_ext = (side == "BUY" and (sess_hi - entry) <= max(8.0, a)) or (
            side == "SELL" and (entry - sess_lo) <= max(8.0, a)
        )
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
        return {
            "ctrl": bool(ctrl),
            "ad": bool(ad),
            "held": bool(held),
            "htf_with": bool(htf_with),
            "not_extreme": not into_ext,
            "disp10": body >= 1.0 * a,
            "disp08": body >= 0.8 * a,
            "big_body": body >= max(8.0, 0.6 * a),
            "compress": bool(compress),
            "engulf": bool(engulf),
            "close_strong": bool(close_strong),
            "am": mins[i] < 11 * 60,
            "atr_hi": a >= 10.0,
            "atr_ok": a >= 6.0,
        }

    cands: List[dict] = []

    def emit(src, mode, side, i, level_px, z=None):
        if not (MINS_LO <= mins[i] <= MINS_HI):
            return
        entry = float(c[i])
        fp = entry_feats(i, side, entry)
        lab = label(h, l, c, day, i, entry, side)
        cands.append(
            {
                "src": src,
                "mode": mode,
                "day": day[i],
                "hm": idx[i].strftime("%H:%M"),
                "mins": int(mins[i]),
                "side": side,
                "entry": round(entry, 2),
                "level": round(float(level_px), 2),
                **fp,
                **lab,
            }
        )

    # ---------- OR15 / OR30 ----------
    for width, tag in ((15, "OR15"), (30, "OR30")):
        for d, idxs in by_day.items():
            # OR bars from 09:15
            or_bars = [j for j in idxs if 9 * 60 + 15 <= mins[j] < 9 * 60 + 15 + width]
            if len(or_bars) < max(5, width // 2):
                continue
            or_hi = float(np.max(h[or_bars]))
            or_lo = float(np.min(l[or_bars]))
            live = or_bars[-1]
            a0 = float(atr[live]) if np.isfinite(atr[live]) and atr[live] > 0 else 10.0
            if or_hi - or_lo < 5.0:
                continue
            up = make_zone(or_hi, a0, "UP")
            dn = make_zone(or_lo, a0, "DOWN")
            after = [j for j in idxs if j > live and MINS_LO <= mins[j] <= MINS_HI]

            # BOUNCE fade: leave then retest from inside-ish
            left_up = left_dn = False
            bounce_up_done = bounce_dn_done = False
            broke_up = broke_dn = False
            ext_up = ext_dn = False
            break_up_done = break_dn_done = False

            for j in after:
                a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else a0
                # --- bounce resistance (SELL): leave below then retest UP zone ---
                if not bounce_up_done:
                    if not left_up:
                        if float(c[j]) <= up["px"] - LEAVE_ATR * a:
                            left_up = True
                    elif in_zone(float(l[j]), float(h[j]), up) and float(c[j]) < up["px"]:
                        emit(tag, "bounce", "SELL", j, or_hi, up)
                        bounce_up_done = True
                if not bounce_dn_done:
                    if not left_dn:
                        if float(c[j]) >= dn["px"] + LEAVE_ATR * a:
                            left_dn = True
                    elif in_zone(float(l[j]), float(h[j]), dn) and float(c[j]) > dn["px"]:
                        emit(tag, "bounce", "BUY", j, or_lo, dn)
                        bounce_dn_done = True

                # --- break + retest ---
                if not broke_up and float(c[j]) > or_hi:
                    broke_up = True
                    continue
                if not broke_dn and float(c[j]) < or_lo:
                    broke_dn = True
                    continue
                if broke_up and not ext_up:
                    if float(c[j]) >= or_hi + EXT_ATR * a:
                        ext_up = True
                    continue
                if broke_dn and not ext_dn:
                    if float(c[j]) <= or_lo - EXT_ATR * a:
                        ext_dn = True
                    continue
                if broke_up and ext_up and not break_up_done:
                    if in_zone(float(l[j]), float(h[j]), up) and float(c[j]) > or_hi:
                        emit(tag, "break_retest", "BUY", j, or_hi, up)
                        break_up_done = True
                if broke_dn and ext_dn and not break_dn_done:
                    if in_zone(float(l[j]), float(h[j]), dn) and float(c[j]) < or_lo:
                        emit(tag, "break_retest", "SELL", j, or_lo, dn)
                        break_dn_done = True

    print(f"after OR: cands={len(cands)}", flush=True)

    # ---------- Prior-day H/L ----------
    for d, phl in prior_hl.items():
        idxs = by_day.get(d)
        if idxs is None or len(idxs) < 10:
            continue
        a0 = float(atr[idxs[0]]) if np.isfinite(atr[idxs[0]]) else 10.0
        up = make_zone(phl["hi"], a0, "UP")
        dn = make_zone(phl["lo"], a0, "DOWN")
        left_up = left_dn = False
        bounce_up_done = bounce_dn_done = False
        broke_up = broke_dn = False
        ext_up = ext_dn = False
        break_up_done = break_dn_done = False
        for j in idxs:
            if mins[j] < MINS_LO or mins[j] > MINS_HI:
                continue
            a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else a0
            if not bounce_up_done:
                if not left_up and float(c[j]) <= up["px"] - LEAVE_ATR * a:
                    left_up = True
                elif left_up and in_zone(float(l[j]), float(h[j]), up) and float(c[j]) < up["px"]:
                    emit("PDHL", "bounce", "SELL", j, phl["hi"])
                    bounce_up_done = True
            if not bounce_dn_done:
                if not left_dn and float(c[j]) >= dn["px"] + LEAVE_ATR * a:
                    left_dn = True
                elif left_dn and in_zone(float(l[j]), float(h[j]), dn) and float(c[j]) > dn["px"]:
                    emit("PDHL", "bounce", "BUY", j, phl["lo"])
                    bounce_dn_done = True
            if not broke_up and float(c[j]) > phl["hi"]:
                broke_up = True
                continue
            if not broke_dn and float(c[j]) < phl["lo"]:
                broke_dn = True
                continue
            if broke_up and not ext_up:
                if float(c[j]) >= phl["hi"] + EXT_ATR * a:
                    ext_up = True
                continue
            if broke_dn and not ext_dn:
                if float(c[j]) <= phl["lo"] - EXT_ATR * a:
                    ext_dn = True
                continue
            if broke_up and ext_up and not break_up_done:
                if in_zone(float(l[j]), float(h[j]), up) and float(c[j]) > phl["hi"]:
                    emit("PDHL", "break_retest", "BUY", j, phl["hi"])
                    break_up_done = True
            if broke_dn and ext_dn and not break_dn_done:
                if in_zone(float(l[j]), float(h[j]), dn) and float(c[j]) < phl["lo"]:
                    emit("PDHL", "break_retest", "SELL", j, phl["lo"])
                    break_dn_done = True

    print(f"after PDHL: cands={len(cands)}", flush=True)

    # ---------- Swing cluster S/R ----------
    for z in res_zones:
        live = z["live_i"]
        d = z["day"]
        px = z["px"]
        a0 = float(atr[live]) if np.isfinite(atr[live]) else 8.0
        zone = make_zone(px, a0, "UP")
        left = False
        bounce_done = break_done = False
        broke = False
        ext = False
        for j in range(live + 1, n):
            if day[j] != d:
                break
            if mins[j] < MINS_LO or mins[j] > MINS_HI:
                continue
            a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else a0
            if not bounce_done:
                if not left and float(c[j]) <= px - LEAVE_ATR * a:
                    left = True
                elif left and in_zone(float(l[j]), float(h[j]), zone) and float(c[j]) < px:
                    emit("SWING_R", "bounce", "SELL", j, px)
                    bounce_done = True
            if not broke and float(c[j]) > px:
                broke = True
                continue
            if broke and not ext:
                if float(c[j]) >= px + EXT_ATR * a:
                    ext = True
                continue
            if broke and ext and not break_done:
                if in_zone(float(l[j]), float(h[j]), zone) and float(c[j]) > px:
                    emit("SWING_R", "break_retest", "BUY", j, px)
                    break_done = True
            if bounce_done and break_done:
                break

    for z in sup_zones:
        live = z["live_i"]
        d = z["day"]
        px = z["px"]
        a0 = float(atr[live]) if np.isfinite(atr[live]) else 8.0
        zone = make_zone(px, a0, "DOWN")
        left = False
        bounce_done = break_done = False
        broke = False
        ext = False
        for j in range(live + 1, n):
            if day[j] != d:
                break
            if mins[j] < MINS_LO or mins[j] > MINS_HI:
                continue
            a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else a0
            if not bounce_done:
                if not left and float(c[j]) >= px + LEAVE_ATR * a:
                    left = True
                elif left and in_zone(float(l[j]), float(h[j]), zone) and float(c[j]) > px:
                    emit("SWING_S", "bounce", "BUY", j, px)
                    bounce_done = True
            if not broke and float(c[j]) < px:
                broke = True
                continue
            if broke and not ext:
                if float(c[j]) <= px - EXT_ATR * a:
                    ext = True
                continue
            if broke and ext and not break_done:
                if in_zone(float(l[j]), float(h[j]), zone) and float(c[j]) < px:
                    emit("SWING_S", "break_retest", "SELL", j, px)
                    break_done = True
            if bounce_done and break_done:
                break

    print(f"total cands={len(cands)}", flush=True)
    by_src = defaultdict(int)
    for r in cands:
        by_src[f"{r['src']}|{r['mode']}"] += 1
    for k, v in sorted(by_src.items()):
        print(f"  {k}: {v}", flush=True)

    # ---------- Score curated gates ----------
    results = []

    def score(name, rows, pred, book="1d"):
        hit = [r for r in rows if pred(r)]
        use = one_per_day(hit) if book == "1d" else hit
        st = pack(use, "m25_first", mid)
        st_m = pack(use, "m25", mid)
        st_c = pack(use, "clean15", mid)
        v = verdict(st, min_n=12 if book == "1d" else 15, min_half=5 if book == "1d" else 6)
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

    print("\n--- base by source ---", flush=True)
    families = [
        ("OR15 break", [r for r in cands if r["src"] == "OR15" and r["mode"] == "break_retest"]),
        ("OR30 break", [r for r in cands if r["src"] == "OR30" and r["mode"] == "break_retest"]),
        ("OR15 bounce", [r for r in cands if r["src"] == "OR15" and r["mode"] == "bounce"]),
        ("OR30 bounce", [r for r in cands if r["src"] == "OR30" and r["mode"] == "bounce"]),
        ("PDHL break", [r for r in cands if r["src"] == "PDHL" and r["mode"] == "break_retest"]),
        ("PDHL bounce", [r for r in cands if r["src"] == "PDHL" and r["mode"] == "bounce"]),
        ("SWING_R bounce", [r for r in cands if r["src"] == "SWING_R" and r["mode"] == "bounce"]),
        ("SWING_S bounce", [r for r in cands if r["src"] == "SWING_S" and r["mode"] == "bounce"]),
        ("SWING_R break", [r for r in cands if r["src"] == "SWING_R" and r["mode"] == "break_retest"]),
        ("SWING_S break", [r for r in cands if r["src"] == "SWING_S" and r["mode"] == "break_retest"]),
        ("ALL break", [r for r in cands if r["mode"] == "break_retest"]),
        ("ALL bounce", [r for r in cands if r["mode"] == "bounce"]),
    ]

    filters = [
        ("raw", lambda r: True),
        ("ctrl", lambda r: r["ctrl"]),
        ("ctrl+htf", lambda r: r["ctrl"] and r["htf_with"]),
        ("ctrl+held", lambda r: r["ctrl"] and r["held"]),
        ("ctrl+held+htf", lambda r: r["ctrl"] and r["held"] and r["htf_with"]),
        ("ctrl+ad+htf", lambda r: r["ctrl"] and r["ad"] and r["htf_with"]),
        ("ctrl+!ext+htf", lambda r: r["ctrl"] and r["not_extreme"] and r["htf_with"]),
        ("ctrl+held+!ext", lambda r: r["ctrl"] and r["held"] and r["not_extreme"]),
        ("ctrl+close_strong+htf", lambda r: r["ctrl"] and r["close_strong"] and r["htf_with"]),
        ("ctrl+engulf+htf", lambda r: r["ctrl"] and r["engulf"] and r["htf_with"]),
        ("ctrl+compress+htf", lambda r: r["ctrl"] and r["compress"] and r["htf_with"]),
        ("ctrl+atr_hi+htf", lambda r: r["ctrl"] and r["atr_hi"] and r["htf_with"]),
        ("ctrl+held+ad+htf", lambda r: r["ctrl"] and r["held"] and r["ad"] and r["htf_with"]),
        ("ctrl+held+close_strong+htf", lambda r: r["ctrl"] and r["held"] and r["close_strong"] and r["htf_with"]),
    ]

    print("\n--- curated ---", flush=True)
    priority = [
        "OR30 break",
        "OR15 break",
        "PDHL break",
        "SWING_R break",
        "SWING_S break",
        "OR30 bounce",
        "OR15 bounce",
        "PDHL bounce",
        "SWING_R bounce",
        "SWING_S bounce",
        "ALL break",
        "ALL bounce",
    ]
    fam_map = {n: rows for n, rows in families}
    for fname in priority:
        rows = fam_map.get(fname, [])
        if not rows:
            continue
        for fname_filt, pred in filters:
            # skip very heavy combos on ALL without filter
            if fname.startswith("ALL") and fname_filt == "raw":
                score(f"{fname} {fname_filt}", rows, pred, "1d")
                continue
            score(f"{fname} {fname_filt}", rows, pred, "1d")
            if fname_filt in ("ctrl+held+htf", "ctrl+held+ad+htf", "ctrl+atr_hi+htf", "ctrl+engulf+htf"):
                score(f"{fname} {fname_filt}", rows, pred, "all")

    # Exhaustive on best families
    print("\n--- hunt OR/PDHL/SWING break ---", flush=True)
    feat_keys = ["ctrl", "ad", "held", "htf_with", "not_extreme", "close_strong", "engulf", "compress", "atr_hi", "disp08", "big_body", "am"]
    hunt = []
    for fname in ("OR30 break", "OR15 break", "PDHL break", "SWING_R break", "SWING_S break", "OR30 bounce", "PDHL bounce", "ALL break"):
        universe = fam_map.get(fname, [])
        if len(universe) < 20:
            continue
        for k in (2, 3, 4):
            for combo in combinations(feat_keys, k):
                if "ctrl" not in combo:
                    continue
                hit = [r for r in universe if all(r.get(f) for f in combo)]
                for book, use, min_n in (("1d", one_per_day(hit), 12), ("all", hit, 15)):
                    st = pack(use, "m25_first", mid)
                    if st["n"] < min_n or st["prec"] is None or st["prec"] < 75:
                        continue
                    hunt.append(
                        {
                            "name": f"{fname}|{book}|" + "+".join(combo),
                            **st,
                            "verdict": verdict(st, min_n=min_n, min_half=5 if book == "1d" else 6),
                            "m25": pack(use, "m25", mid)["prec"],
                            "clean15": pack(use, "clean15", mid)["prec"],
                            "samples": use[:10],
                        }
                    )
    hunt.sort(
        key=lambda x: (
            0 if x["verdict"] == "PROVEN_100" else 1 if x["verdict"] == "PROMISING_95" else 2 if x["verdict"] == "HIGH_85" else 3 if x["verdict"] == "HIGH_75" else 4,
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
    print(f"hunt ≥75%: {len(hunt_u)}", flush=True)
    for hrow in hunt_u[:15]:
        print(
            f"  {hrow['verdict']} {hrow['name']}: n={hrow['n']} m25f={hrow['prec']}% "
            f"tr={hrow['train_prec']}% oos={hrow['oos_prec']}% c15={hrow['clean15']}%",
            flush=True,
        )

    pool = [r for r in results if r["verdict"] != "THIN"] + [h for h in hunt_u if h["verdict"] != "THIN"]
    pool.sort(
        key=lambda x: (
            0 if x["verdict"] == "PROVEN_100" else 1 if x["verdict"] == "PROMISING_95" else 2 if x["verdict"] == "HIGH_85" else 3 if x["verdict"] == "HIGH_75" else 4,
            -(x["prec"] or 0),
            -(x["oos_prec"] or 0),
            -x["n"],
        )
    )
    best = pool[0] if pool else (results[0] if results else None)

    # Report
    lines = [
        "# NIFTY 1m — Entry accuracy **v7** (Range Support / Resistance)",
        "",
        "> Add **range S/R** then find entry: OR15/OR30, prior-day H/L, swing clusters.",
        "> Modes: **bounce** (fade retest) · **break_retest** (continue).",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS **{mid}**. Candidates **{len(cands)}**.",
        "",
        "## 0) Candidate counts",
        "",
        "| Source|Mode | n |",
        "|---|---:|",
    ]
    for k, v in sorted(by_src.items()):
        lines.append(f"| `{k}` | {v} |")

    lines += [
        "",
        "## 1) Curated gates (m25_first)",
        "",
        "| Gate | Verdict | n | m25_first% | Train | OOS | m25% | clean15% | MFE | MAE |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    ranked = sorted(
        results,
        key=lambda x: (
            0 if "HIGH" in x["verdict"] or "PROVEN" in x["verdict"] or "PROMISING" in x["verdict"] else 1 if x["verdict"] == "WEAK" else 2,
            -(x["prec"] or 0),
        ),
    )
    for r in ranked[:60]:
        lines.append(
            f"| `{r['name']}` | **{r['verdict']}** | {r['n']} | **{r['prec']}** | {r['train_prec']} | "
            f"{r['oos_prec']} | {r['m25']} | {r['clean15']} | {r['avg_mfe']} | {r['avg_mae']} |"
        )

    lines += ["", "## 2) Hunt ≥75% m25_first", ""]
    if not hunt_u:
        lines.append("_None._")
    else:
        lines += [
            "| Rule | Verdict | n | m25_first% | Train | OOS | m25% | clean15% |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for hrow in hunt_u[:25]:
            lines.append(
                f"| `{hrow['name']}` | **{hrow['verdict']}** | {hrow['n']} | **{hrow['prec']}** | "
                f"{hrow['train_prec']} | {hrow['oos_prec']} | {hrow['m25']} | {hrow['clean15']} |"
            )

    lines += ["", "## 3) Most accurate range S/R entry", ""]
    if best:
        lines += [
            f"**Best effort:** `{best['name']}` · **{best['verdict']}**",
            f"- m25_first **{best['prec']}%** · TRAIN **{best.get('train_prec')}%** · OOS **{best.get('oos_prec')}%** · n={best['n']}",
            f"- raw m25 **{best.get('m25')}%** · clean15 **{best.get('clean15')}%**",
            f"- avg MFE {best.get('avg_mfe')} · avg MAE {best.get('avg_mae')}",
            "",
            "### Entry rule (side + price)",
            "",
            "```",
            "1) Build range level (OR15/OR30 edge, prior-day H/L, or swing cluster)",
            "2) Zone = level ± 0.5×ATR14",
            "3) BREAK path: close through → extend ≥0.5×ATR → retest zone → enter continuation close",
            "   BOUNCE path: leave ≥0.5×ATR → retest zone → enter fade close",
            "4) Apply best filters from this report (ctrl / held / htf / …)",
            "SIDE  : BUY/SELL from path",
            "ENTRY : close of signal 1m bar",
            "```",
            "",
            "### Samples",
            "",
            "| Day | HM | Side | Entry | Level | MFE | MAE | m25_first | clean15 |",
            "|---|---|---|---:|---:|---:|---:|---|---|",
        ]
        for x in (best.get("samples") or [])[:12]:
            lines.append(
                f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | {x.get('level','')} | "
                f"{x['mfe']} | {x['mae']} | {x['m25_first']} | {x['clean15']} |"
            )
    else:
        lines.append("_No viable gate._")

    high = [x for x in pool if x["verdict"] in ("PROVEN_100", "PROMISING_95", "HIGH_85")]
    lines += [
        "",
        "## 4) vs prior research",
        "",
        "- OR break+retest was **PROVEN** for 3R expectancy (~40–45% hit) — different metric than m25_first.",
        f"- Gates ≥85% m25_first this pass: **{len(high)}**",
        "- Near-100% favour-first still requires PROVEN_100 / PROMISING_95 — report if absent.",
        "",
        f"_Generated in {time.time() - t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "counts": dict(by_src),
                "curated": results,
                "hunt": hunt_u,
                "best": best,
                "high85": high,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT}", flush=True)
    if best:
        print(f"BEST={best['name']} {best['verdict']} prec={best['prec']}%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
