"""RESEARCH ONLY — Precision of range/S/R markers for clean ≥40 one-direction moves.

Coverage (prior report): of true clean40, how many markers catch.
Precision (this report): when a marker FIRES, how often a clean ≥40 same-color
move actually follows (only green to +40 / only red to −40).

  python -u prod_live/tests/builders/_diag_scalp_clean40_precision.py
"""
from __future__ import annotations

import json
import sys
time  # noqa — placeholder fix below
import time
from collections import defaultdict
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
from _diag_scalp_pa_bos_choch_fvg import _norm_1m  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_CLEAN40_PRECISION.md"
REPORT_JSON = OUT / "NIFTY_1M_CLEAN40_PRECISION.json"

MINS_LO, MINS_HI = 9 * 60 + 15, 14 * 60 + 30
N_SESSIONS = 120
LOOKBACK_CAL = 240
MIN_PTS = 40.0
PIVOT_L = 3
ZONE_ATR = 0.5
RANGE_LOOK = 20
RANGE_WIDTH_ATR = 3.5


def pack(rows, key, mid):
    if not rows:
        return {"n": 0, "prec": None, "train_n": 0, "train_prec": None, "oos_n": 0, "oos_prec": None}
    tr = [r for r in rows if r["day"] < mid]
    oo = [r for r in rows if r["day"] >= mid]

    def _p(rs):
        if not rs:
            return None, 0
        return round(100.0 * sum(1 for x in rs if x.get(key)) / len(rs), 2), len(rs)

    p, n = _p(rows)
    pt, nt = _p(tr)
    po, no = _p(oo)
    return {"n": n, "prec": p, "train_n": nt, "train_prec": pt, "oos_n": no, "oos_prec": po}


def one_per_day(rows):
    byd = {}
    for r in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        if r["day"] not in byd:
            byd[r["day"]] = r
    return list(byd.values())


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("CLEAN40 PRECISION — marker fires → clean ≥40 follows?", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df = _norm_1m(raw)
    df = add_ma_layers(df)
    df = add_indicators(df)
    df = add_ad_obv_proxy(df)

    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    mid = days_sorted[n_days // 2]
    df = df[[str(ts.date()) in keep for ts in df.index]]
    print(f"window {day_lo}→{day_hi} n={n_days} OOS≥{mid}", flush=True)

    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    atr = df["atr14"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    vwap = df["vwap"].astype(float).values if "vwap" in df.columns else c.copy()
    pdi = df["plus_di"].astype(float).values if "plus_di" in df.columns else np.zeros(len(c))
    mdi = df["minus_di"].astype(float).values if "minus_di" in df.columns else np.zeros(len(c))
    ad_r = df["ad_rising"].astype(bool).values if "ad_rising" in df.columns else np.zeros(len(c), dtype=bool)
    ad_f = df["ad_falling"].astype(bool).values if "ad_falling" in df.columns else np.zeros(len(c), dtype=bool)
    day = np.array([str(ts.date()) for ts in df.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df.index])
    idx = df.index
    n = len(c)
    by_day = {d: np.where(day == d)[0] for d in keep}

    # OR / prior day
    or_lv = {}
    for d, ii in by_day.items():
        or15 = [j for j in ii if 9 * 60 + 15 <= mins[j] <= 9 * 60 + 29]
        or30 = [j for j in ii if 9 * 60 + 15 <= mins[j] <= 9 * 60 + 44]
        if not or15:
            continue
        or_lv[d] = {
            "or15_hi": float(np.max(h[or15])),
            "or15_lo": float(np.min(l[or15])),
            "or30_hi": float(np.max(h[or30])) if or30 else float(np.max(h[or15])),
            "or30_lo": float(np.min(l[or30])) if or30 else float(np.min(l[or15])),
        }
    prior = {}
    for i, d in enumerate(days_sorted):
        if i == 0:
            continue
        prev = days_sorted[i - 1]
        ii = by_day[prev]
        prior[d] = {"hi": float(np.max(h[ii])), "lo": float(np.min(l[ii]))}

    swing_hi, swing_lo = [], []
    for i in range(PIVOT_L, n - PIVOT_L):
        if h[i] >= np.max(h[i - PIVOT_L : i + PIVOT_L + 1]) - 1e-9:
            swing_hi.append((i + PIVOT_L, float(h[i])))
        if l[i] <= np.min(l[i - PIVOT_L : i + PIVOT_L + 1]) + 1e-9:
            swing_lo.append((i + PIVOT_L, float(l[i])))

    def live_swings(i):
        return (
            [(li, lp) for li, lp in swing_hi if li < i][-40:],
            [(li, lp) for li, lp in swing_lo if li < i][-40:],
        )

    def nearest(levels, px, above, a):
        cand = []
        for li, lp in levels:
            if above and lp > px + 0.05:
                cand.append((lp - px, lp))
            if (not above) and lp < px - 0.05:
                cand.append((px - lp, lp))
        if not cand:
            return None, None
        dist, lp = min(cand, key=lambda x: x[0])
        if dist > 3.0 * a:
            return None, None
        return lp, dist

    def streak_start(i, side):
        """Walk back to first bar of current same-color streak."""
        s = i
        while s - 1 >= 0 and day[s - 1] == day[i]:
            if side == "BUY" and c[s - 1] > o[s - 1]:
                s -= 1
            elif side == "SELL" and c[s - 1] < o[s - 1]:
                s -= 1
            else:
                break
        return s

    def clean40_from(start_i, side):
        """From open of start_i, only same-color until ±40. Returns (ok, hit_i, ext, bars)."""
        if start_i < 0 or start_i >= n:
            return False, None, 0.0, 0
        if side == "BUY" and not (c[start_i] > o[start_i]):
            return False, None, 0.0, 0
        if side == "SELL" and not (c[start_i] < o[start_i]):
            return False, None, 0.0, 0
        start_px = float(o[start_i])
        d = day[start_i]
        ext = 0.0
        hit = None
        j = start_i
        while j < n and day[j] == d and mins[j] <= MINS_HI:
            if side == "BUY" and not (c[j] > o[j]):
                break
            if side == "SELL" and not (c[j] < o[j]):
                break
            if side == "BUY":
                ext = max(ext, float(h[j]) - start_px)
            else:
                ext = max(ext, start_px - float(l[j]))
            if hit is None and ext >= MIN_PTS:
                hit = j
                break
            j += 1
        if hit is None:
            return False, None, round(ext, 2), j - start_i
        # extend full streak for reporting
        full = ext
        k = hit
        while k + 1 < n and day[k + 1] == d and mins[k + 1] <= MINS_HI:
            if side == "BUY" and c[k + 1] > o[k + 1]:
                k += 1
                full = max(full, float(h[k]) - start_px)
            elif side == "SELL" and c[k + 1] < o[k + 1]:
                k += 1
                full = max(full, start_px - float(l[k]))
            else:
                break
        return True, hit, round(full, 2), hit - start_i + 1

    # True clean40 set (for coverage) — ignition at color flip
    true_starts = set()  # (day, start_i, side)
    true_moves = []
    i = 0
    while i < n - 1:
        if day[i] not in keep or not (MINS_LO <= mins[i] <= MINS_HI):
            i += 1
            continue
        green, red = c[i] > o[i], c[i] < o[i]
        if not green and not red:
            i += 1
            continue
        if i > 0 and day[i - 1] == day[i]:
            if green and c[i - 1] > o[i - 1]:
                i += 1
                continue
            if red and c[i - 1] < o[i - 1]:
                i += 1
                continue
        side = "BUY" if green else "SELL"
        ok, hit, ext, bars = clean40_from(i, side)
        if ok:
            true_starts.add((day[i], i, side))
            true_moves.append({"day": day[i], "start_i": i, "side": side, "ext": ext, "bars": bars})
            # skip to end of streak
            j = hit
            while j + 1 < n and day[j + 1] == day[i]:
                if side == "BUY" and c[j + 1] > o[j + 1]:
                    j += 1
                elif side == "SELL" and c[j + 1] < o[j + 1]:
                    j += 1
                else:
                    break
            i = j + 1
        else:
            i += 1
    print(f"true clean40 moves: {len(true_moves)}", flush=True)

    # Emit signals
    signals: List[dict] = []

    def emit(name, i, side, extra=None):
        if not (MINS_LO <= mins[i] <= MINS_HI) or day[i] not in keep:
            return
        # require signal bar matches side color
        if side == "BUY" and not (c[i] > o[i]):
            return
        if side == "SELL" and not (c[i] < o[i]):
            return
        s0 = streak_start(i, side)
        ok, hit, ext, bars = clean40_from(s0, side)
        # success only if 40 is reached at or after signal bar (we didn't miss it)
        success = bool(ok and hit is not None and hit >= i)
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        rng = max(float(h[i]) - float(l[i]), 0.05)
        loc = (float(c[i]) - float(l[i])) / rng
        ctrl = (side == "BUY" and loc >= 0.65) or (side == "SELL" and loc <= 0.35)
        body = abs(float(c[i]) - float(o[i]))
        di_ok = (side == "BUY" and pdi[i] > mdi[i]) or (side == "SELL" and mdi[i] > pdi[i])
        above = float(c[i]) >= float(ema34[i]) if np.isfinite(ema34[i]) else True
        gate34 = (side == "BUY" and above) or (side == "SELL" and not above)
        vw = float(vwap[i]) if np.isfinite(vwap[i]) else float(c[i])
        vwap_with = (side == "BUY" and float(c[i]) >= vw) or (side == "SELL" and float(c[i]) <= vw)
        held = bool(di_ok and gate34 and vwap_with)
        ad = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))
        row = {
            "name": name,
            "day": day[i],
            "hm": idx[i].strftime("%H:%M"),
            "mins": int(mins[i]),
            "side": side,
            "entry": round(float(c[i]), 2),
            "start_i": s0,
            "signal_i": i,
            "clean40": success,
            "ext": ext if success else (ext or 0.0),
            "bars_to_40": bars if success else None,
            "ctrl": ctrl,
            "held": held,
            "ad": ad,
            "disp08": body >= 0.8 * a,
            "big_body": body >= max(8.0, 0.6 * a),
            "atr_hi": a >= 10.0,
            "caught_true": (day[i], s0, side) in true_starts,
        }
        if extra:
            row.update(extra)
        signals.append(row)

    # Walk all bars — fire markers
    # Track OR/PDHL break state per day
    or_broke = {d: {"15u": False, "15d": False, "30u": False, "30d": False} for d in keep}
    pd_broke = {d: {"u": False, "d": False} for d in keep}
    box_fired = set()  # (day, side, box_hi/lo key) once

    for i in range(1, n):
        d = day[i]
        if d not in keep or not (MINS_LO <= mins[i] <= MINS_HI):
            continue
        if day[i - 1] != d:
            continue
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        green, red = c[i] > o[i], c[i] < o[i]
        prev_g, prev_r = c[i - 1] > o[i - 1], c[i - 1] < o[i - 1]

        # 1) color flip ignition
        if green and prev_r:
            emit("flip0", i, "BUY")
        if red and prev_g:
            emit("flip0", i, "SELL")

        # 2) confirm1 = 2nd bar of streak
        if green and prev_g:
            s0 = streak_start(i, "BUY")
            if i == s0 + 1:
                emit("confirm1", i, "BUY")
        if red and prev_r:
            s0 = streak_start(i, "SELL")
            if i == s0 + 1:
                emit("confirm1", i, "SELL")

        # 3) flip0+ctrl / confirm1+ctrl handled as filters later

        # Prior box (20 bars before i)
        so = by_day[d][by_day[d] < i]
        range_hi = range_lo = None
        in_coil = False
        if len(so) >= 8:
            look = so[-RANGE_LOOK:] if len(so) >= RANGE_LOOK else so[-8:]
            range_hi = float(np.max(h[look]))
            range_lo = float(np.min(l[look]))
            in_coil = (range_hi - range_lo) <= RANGE_WIDTH_ATR * a

        # box break on this bar
        if range_hi is not None and green and float(c[i]) > range_hi:
            key = (d, "BUY", round(range_hi, 1))
            if key not in box_fired:
                box_fired.add(key)
                emit("box_break", i, "BUY", {"coil": in_coil})
                if in_coil:
                    emit("tight_range_break", i, "BUY")
        if range_lo is not None and red and float(c[i]) < range_lo:
            key = (d, "SELL", round(range_lo, 1))
            if key not in box_fired:
                box_fired.add(key)
                emit("box_break", i, "SELL", {"coil": in_coil})
                if in_coil:
                    emit("tight_range_break", i, "SELL")

        # OR breaks (first close beyond)
        od = or_lv.get(d)
        if od:
            st = or_broke[d]
            if not st["15u"] and float(c[i]) > od["or15_hi"] and green:
                st["15u"] = True
                emit("or15_break", i, "BUY")
            if not st["15d"] and float(c[i]) < od["or15_lo"] and red:
                st["15d"] = True
                emit("or15_break", i, "SELL")
            if not st["30u"] and float(c[i]) > od["or30_hi"] and green:
                st["30u"] = True
                emit("or30_break", i, "BUY")
            if not st["30d"] and float(c[i]) < od["or30_lo"] and red:
                st["30d"] = True
                emit("or30_break", i, "SELL")

        # PDHL breaks
        pdhl = prior.get(d)
        if pdhl:
            st = pd_broke[d]
            if not st["u"] and float(c[i]) > pdhl["hi"] and green:
                st["u"] = True
                emit("pdhl_break", i, "BUY")
            if not st["d"] and float(c[i]) < pdhl["lo"] and red:
                st["d"] = True
                emit("pdhl_break", i, "SELL")

        # session extreme
        if len(so):
            shi, slo = float(np.max(h[so])), float(np.min(l[so]))
            if green and float(h[i]) > shi and (i == 0 or not (day[i - 1] == d and float(h[i - 1]) > shi)):
                # first bar making new high
                if float(c[i]) > shi:
                    emit("sess_ext", i, "BUY")
            if red and float(l[i]) < slo and float(c[i]) < slo:
                emit("sess_ext", i, "SELL")

        # S/R bounce: leave then touch — simplified: near S and green flip / near R and red flip
        sh, sl = live_swings(i)
        res, rd = nearest(sh, float(c[i]), True, a)
        sup, sd = nearest(sl, float(c[i]), False, a)
        if green and prev_r and sd is not None and sd <= ZONE_ATR * a:
            emit("support_bounce", i, "BUY")
        if red and prev_g and rd is not None and rd <= ZONE_ATR * a:
            emit("resist_bounce", i, "SELL")

    print(f"raw signals emitted: {len(signals)}", flush=True)

    # Build evaluated books
    books = []

    def add_book(label, rows, filt=None):
        hit = [r for r in rows if (filt(r) if filt else True)]
        st_all = pack(hit, "clean40", mid)
        one = one_per_day(hit)
        st_1d = pack(one, "clean40", mid)
        # coverage: unique true starts caught
        caught = {(r["day"], r["start_i"], r["side"]) for r in hit if r.get("caught_true")}
        cov = round(100.0 * len(caught) / max(len(true_moves), 1), 1)
        avg_ext = round(float(np.mean([r["ext"] for r in hit if r["clean40"]])), 1) if any(r["clean40"] for r in hit) else None
        books.append(
            {
                "name": label,
                "all": st_all,
                "one": st_1d,
                "coverage": cov,
                "caught_n": len(caught),
                "avg_ext": avg_ext,
                "samples": [r for r in one if r["clean40"]][:6] + [r for r in one if not r["clean40"]][:4],
            }
        )
        print(
            f"  {label}: all n={st_all['n']} prec={st_all['prec']}% oos={st_all['oos_prec']}% | "
            f"1d n={st_1d['n']} prec={st_1d['prec']}% | cov={cov}% ({len(caught)}/{len(true_moves)})",
            flush=True,
        )

    by_name = defaultdict(list)
    for r in signals:
        by_name[r["name"]].append(r)

    base_names = [
        "flip0",
        "confirm1",
        "box_break",
        "tight_range_break",
        "or15_break",
        "or30_break",
        "pdhl_break",
        "sess_ext",
        "support_bounce",
        "resist_bounce",
    ]
    for nm in base_names:
        rows = by_name.get(nm, [])
        if not rows:
            continue
        add_book(nm, rows)
        add_book(f"{nm}+ctrl", rows, lambda r: r["ctrl"])
        add_book(f"{nm}+ctrl+ad", rows, lambda r: r["ctrl"] and r["ad"])
        add_book(f"{nm}+ctrl+held", rows, lambda r: r["ctrl"] and r["held"])
        add_book(f"{nm}+ctrl+disp08", rows, lambda r: r["ctrl"] and r["disp08"])
        add_book(f"{nm}+ctrl+big_body", rows, lambda r: r["ctrl"] and r["big_body"])
        add_book(f"{nm}+ctrl+atr_hi", rows, lambda r: r["ctrl"] and r["atr_hi"])

    # Combined structure
    struct = []
    for nm in ("box_break", "or15_break", "or30_break", "pdhl_break", "sess_ext", "tight_range_break"):
        struct.extend(by_name.get(nm, []))
    # dedupe same bar+side keep first name
    seen = set()
    struct_u = []
    for r in sorted(struct, key=lambda x: (x["day"], x["mins"], x["side"])):
        k = (r["day"], r["mins"], r["side"])
        if k in seen:
            continue
        seen.add(k)
        struct_u.append(r)
    add_book("ANY_structure_break", struct_u)
    add_book("ANY_structure+ctrl", struct_u, lambda r: r["ctrl"])
    add_book("ANY_structure+ctrl+ad", struct_u, lambda r: r["ctrl"] and r["ad"])

    sr = by_name.get("support_bounce", []) + by_name.get("resist_bounce", [])
    add_book("ANY_SR_bounce", sr)
    add_book("ANY_SR_bounce+ctrl", sr, lambda r: r["ctrl"])

    struct_sr = struct_u + sr
    seen2 = set()
    ss_u = []
    for r in sorted(struct_sr, key=lambda x: (x["day"], x["mins"], x["side"])):
        k = (r["day"], r["mins"], r["side"])
        if k in seen2:
            continue
        seen2.add(k)
        ss_u.append(r)
    add_book("structure_or_SR", ss_u)
    add_book("structure_or_SR+ctrl", ss_u, lambda r: r["ctrl"])
    add_book("structure_or_SR+ctrl+ad", ss_u, lambda r: r["ctrl"] and r["ad"])
    add_book("structure_or_SR+ctrl+held", ss_u, lambda r: r["ctrl"] and r["held"])

    # confirm1 with structure context: confirm1 bar where streak start had box/or/sr — approximate as confirm1+ctrl+ad
    add_book("confirm1+ctrl+ad+disp08", by_name.get("confirm1", []), lambda r: r["ctrl"] and r["ad"] and r["disp08"])
    add_book("confirm1+ctrl+held+ad", by_name.get("confirm1", []), lambda r: r["ctrl"] and r["held"] and r["ad"])

    # Rank by 1d precision then coverage
    def rank_key(b):
        p = b["one"]["prec"] or 0
        o = b["one"]["oos_prec"] or 0
        n = b["one"]["n"]
        return (0 if n >= 15 and p >= 40 else 1, -p, -o, -b["coverage"], -n)

    ranked = sorted(books, key=rank_key)
    # Best balanced: precision * coverage with n>=20
    balanced = [
        b
        for b in books
        if b["one"]["n"] >= 20 and b["one"]["prec"] is not None
    ]
    for b in balanced:
        b["score"] = round((b["one"]["prec"] / 100.0) * (b["coverage"] / 100.0) * 100, 2)
    balanced.sort(key=lambda b: (-b["score"], -(b["one"]["prec"] or 0), -b["coverage"]))

    lines = [
        "# NIFTY 1m — Clean ≥40 **precision** (marker → move follows)",
        "",
        "> When we **mark** a level/break/flip, how often does a clean one-direction ≥40 follow?",
        "> Clean = only green candles to +40 / only red to −40.",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS **{mid}**. True clean40 moves: **{len(true_moves)}**.",
        "",
        "## Definitions",
        "",
        "| Term | Meaning |",
        "|---|---|",
        "| **Precision** | Of marker signals, % that become clean ≥40 |",
        "| **Coverage** | Of true clean40 moves, % caught by that marker |",
        "| **1/day** | First signal per day (stable book) |",
        "",
        "## 1) All marker books (1/day + all)",
        "",
        "| Marker | Verdict-ish | 1d n | 1d prec% | OOS% | all n | all prec% | Coverage% | caught | avg ext |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for b in ranked:
        p = b["one"]["prec"]
        n1 = b["one"]["n"]
        tag = (
            "HIGH"
            if n1 >= 15 and (p or 0) >= 50 and (b["one"]["oos_prec"] or 0) >= 45
            else "OK"
            if n1 >= 15 and (p or 0) >= 35
            else "WEAK"
            if n1 >= 10
            else "THIN"
        )
        lines.append(
            f"| `{b['name']}` | {tag} | {n1} | **{p}** | {b['one']['oos_prec']} | "
            f"{b['all']['n']} | {b['all']['prec']} | **{b['coverage']}** | {b['caught_n']} | {b['avg_ext']} |"
        )

    lines += [
        "",
        "## 2) Best balance (precision × coverage, 1d n≥20)",
        "",
        "| Marker | score | 1d prec% | Coverage% | 1d n | OOS% |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for b in balanced[:15]:
        lines.append(
            f"| `{b['name']}` | **{b['score']}** | {b['one']['prec']} | {b['coverage']} | "
            f"{b['one']['n']} | {b['one']['oos_prec']} |"
        )

    best = balanced[0] if balanced else (ranked[0] if ranked else None)
    best_prec = max(
        [b for b in books if b["one"]["n"] >= 15 and b["one"]["prec"] is not None],
        key=lambda b: (b["one"]["prec"], b["one"]["oos_prec"] or 0, b["coverage"]),
        default=None,
    )

    lines += ["", "## 3) Practical takeaway", ""]
    if best_prec:
        lines += [
            f"**Highest precision (n≥15 1d):** `{best_prec['name']}`",
            f"- 1/day precision **{best_prec['one']['prec']}%** OOS **{best_prec['one']['oos_prec']}%** n={best_prec['one']['n']}",
            f"- Coverage **{best_prec['coverage']}%** ({best_prec['caught_n']}/{len(true_moves)} true moves)",
            "",
        ]
    if best:
        lines += [
            f"**Best balance:** `{best['name']}` · score {best.get('score')}",
            f"- 1/day precision **{best['one']['prec']}%** · coverage **{best['coverage']}%** · n={best['one']['n']}",
            "",
        ]
    lines += [
        "### How to use",
        "",
        "```",
        "1. Mark range box (prior 20-bar H/L), OR15/OR30, PDHL, swing S/R",
        "2. When 1m CLOSES beyond box / OR / PDHL (or bounces S/R with color flip) → signal",
        "3. Side = break/bounce direction",
        "4. Track only while candles stay SAME COLOR",
        "5. Success = reach ±40 with no opposite-color candle",
        "6. If opposite color prints before 40 → abandon (not a clean one-way move)",
        "```",
        "",
    ]
    if best:
        lines += [
            "### Samples (best balance, 1/day)",
            "",
            "| Day | HM | Side | Entry | clean40 | ext |",
            "|---|---|---|---:|---|---:|",
        ]
        for x in (best.get("samples") or [])[:12]:
            lines.append(
                f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | "
                f"{x['clean40']} | {x['ext']} |"
            )

    lines += ["", f"_Generated in {time.time() - t0:.1f}s._", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "true_n": len(true_moves),
                "books": [
                    {
                        "name": b["name"],
                        "one": b["one"],
                        "all": b["all"],
                        "coverage": b["coverage"],
                        "caught_n": b["caught_n"],
                        "score": b.get("score"),
                    }
                    for b in ranked
                ],
                "best_balance": best["name"] if best else None,
                "best_precision": best_prec["name"] if best_prec else None,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT}", flush=True)
    if best:
        print(f"BEST_BALANCE={best['name']} prec={best['one']['prec']}% cov={best['coverage']}%", flush=True)
    if best_prec:
        print(f"BEST_PREC={best_prec['name']} prec={best_prec['one']['prec']}% cov={best_prec['coverage']}%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
