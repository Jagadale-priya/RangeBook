"""RESEARCH ONLY — Hybrid coil → impulse break for clean ≥40 one-direction.

Recipe (trained dual-clean ideas + online breakout docs):
  COIL   = BB-width squeeze AND ATR compression, lasting ≥ min_bars
  BREAK  = first close outside coil Donchian high/low
  IMPULSE= break candle body ≥ 0.8×ATR + control close
  TRACK  = only same-color 1m until ±40; abort on opposite color

Also score baselines: confirm1, box_break, or30 for comparison.

  python -u prod_live/tests/builders/_diag_scalp_clean40_hybrid_coil.py
"""
from __future__ import annotations

import json
import sys
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
REPORT = OUT / "NIFTY_1M_CLEAN40_HYBRID_COIL.md"
REPORT_JSON = OUT / "NIFTY_1M_CLEAN40_HYBRID_COIL.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30  # after OR-ish; also allow from 9:30
N_SESSIONS = 120
LOOKBACK_CAL = 240
MIN_PTS = 40.0
BB_LEN = 20
BB_SQUEEZE_THR = 0.60  # bbWidth < SMA(bbWidth)*thr
ATR_COMPRESS = 0.75  # atr < SMA(atr)*ratio
MIN_COIL_BARS = 5
IMPULSE_BODY_ATR = 0.80


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
    print("CLEAN40 HYBRID — dual squeeze coil + impulse break", flush=True)

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

    # --- BB width + ATR compression ---
    close_s = pd.Series(c)
    mid_bb = close_s.rolling(BB_LEN, min_periods=BB_LEN).mean()
    std_bb = close_s.rolling(BB_LEN, min_periods=BB_LEN).std()
    bb_width = ((2 * std_bb) / mid_bb.replace(0, np.nan)).values
    bb_width_sma = pd.Series(bb_width).rolling(BB_LEN, min_periods=BB_LEN).mean().values
    atr_s = pd.Series(atr)
    atr_sma = atr_s.rolling(BB_LEN, min_periods=BB_LEN).mean().values

    bb_squeeze = (bb_width < bb_width_sma * BB_SQUEEZE_THR) & np.isfinite(bb_width) & np.isfinite(bb_width_sma)
    atr_comp = (atr < atr_sma * ATR_COMPRESS) & np.isfinite(atr) & np.isfinite(atr_sma)
    dual_sq = bb_squeeze & atr_comp

    # coil streak length ending at i (inclusive)
    coil_len = np.zeros(n, dtype=int)
    for i in range(n):
        if dual_sq[i]:
            coil_len[i] = (coil_len[i - 1] + 1) if i > 0 else 1
        else:
            coil_len[i] = 0

    # OR30 for baseline
    or_lv = {}
    for d, ii in by_day.items():
        or30 = [j for j in ii if 9 * 60 + 15 <= mins[j] <= 9 * 60 + 44]
        if or30:
            or_lv[d] = {"hi": float(np.max(h[or30])), "lo": float(np.min(l[or30]))}

    def streak_start(i, side):
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
            return False, None, round(ext, 2), max(0, j - start_i)
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

    # True clean40 set
    true_moves = []
    true_starts = set()
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
            true_moves.append({"day": day[i], "start_i": i, "side": side, "ext": ext})
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
    print(f"true clean40: {len(true_moves)}", flush=True)

    def feats(i, side):
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        body = abs(float(c[i]) - float(o[i]))
        rng = max(float(h[i]) - float(l[i]), 0.05)
        loc = (float(c[i]) - float(l[i])) / rng
        ctrl = (side == "BUY" and loc >= 0.65 and c[i] > o[i]) or (
            side == "SELL" and loc <= 0.35 and c[i] < o[i]
        )
        impulse = body >= IMPULSE_BODY_ATR * a
        di_ok = (side == "BUY" and pdi[i] > mdi[i]) or (side == "SELL" and mdi[i] > pdi[i])
        above = float(c[i]) >= float(ema34[i]) if np.isfinite(ema34[i]) else True
        gate34 = (side == "BUY" and above) or (side == "SELL" and not above)
        vw = float(vwap[i]) if np.isfinite(vwap[i]) else float(c[i])
        vwap_with = (side == "BUY" and float(c[i]) >= vw) or (side == "SELL" and float(c[i]) <= vw)
        held = bool(di_ok and gate34 and vwap_with)
        ad = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))
        return {
            "ctrl": ctrl,
            "impulse": impulse,
            "held": held,
            "ad": ad,
            "atr_hi": a >= 10.0,
            "big_body": body >= max(8.0, 0.6 * a),
            "atr": round(a, 2),
            "body": round(body, 2),
        }

    def emit_row(name, i, side, extra=None):
        if not (MINS_LO <= mins[i] <= MINS_HI) or day[i] not in keep:
            return None
        if side == "BUY" and not (c[i] > o[i]):
            return None
        if side == "SELL" and not (c[i] < o[i]):
            return None
        s0 = streak_start(i, side)
        ok, hit, ext, bars = clean40_from(s0, side)
        success = bool(ok and hit is not None and hit >= i)
        fp = feats(i, side)
        row = {
            "name": name,
            "day": day[i],
            "hm": idx[i].strftime("%H:%M"),
            "mins": int(mins[i]),
            "side": side,
            "entry": round(float(c[i]), 2),
            "start_i": s0,
            "clean40": success,
            "ext": ext if success else (ext or 0.0),
            "caught_true": (day[i], s0, side) in true_starts,
            **fp,
        }
        if extra:
            row.update(extra)
        return row

    signals: List[dict] = []

    # State machines per day for coil boxes
    # When coil_len hits MIN_COIL_BARS, start tracking Donchian of the coil window.
    # While still in dual_sq, expand box. On first bar NOT in squeeze OR break of box → evaluate break.
    # Spec from docs: range built DURING squeeze; break = close outside while impulse.

    coil_active = False
    coil_start = -1
    coil_hi = coil_lo = None
    coil_day = None
    broke_up = broke_dn = False

    for i in range(n):
        d = day[i]
        if d not in keep:
            coil_active = False
            continue

        # day change reset
        if coil_day is not None and d != coil_day:
            coil_active = False
            broke_up = broke_dn = False
        coil_day = d

        # Start coil when dual-squeeze has lasted ≥ MIN_COIL_BARS (box from those bars only)
        if not coil_active and coil_len[i] >= MIN_COIL_BARS:
            coil_active = True
            coil_start = i - MIN_COIL_BARS + 1
            coil_hi = float(np.max(h[coil_start : i + 1]))
            coil_lo = float(np.min(l[coil_start : i + 1]))
            broke_up = broke_dn = False
            continue  # box forms this bar; break can only happen on later bars

        if coil_active and coil_hi is not None:
            # Break vs frozen box from prior coil bars (do NOT expand with this bar first)
            if (
                not broke_up
                and float(c[i]) > coil_hi
                and c[i] > o[i]
                and MINS_LO <= mins[i] <= MINS_HI
            ):
                row = emit_row(
                    "coil_break",
                    i,
                    "BUY",
                    {"coil_bars": int(i - coil_start), "coil_w": round(coil_hi - coil_lo, 2)},
                )
                if row:
                    signals.append(row)
                broke_up = True
                coil_active = False  # consume coil on first directional break
            elif (
                not broke_dn
                and float(c[i]) < coil_lo
                and c[i] < o[i]
                and MINS_LO <= mins[i] <= MINS_HI
            ):
                row = emit_row(
                    "coil_break",
                    i,
                    "SELL",
                    {"coil_bars": int(i - coil_start), "coil_w": round(coil_hi - coil_lo, 2)},
                )
                if row:
                    signals.append(row)
                broke_dn = True
                coil_active = False
            elif dual_sq[i]:
                # still coiling inside — expand box
                coil_hi = max(coil_hi, float(h[i]))
                coil_lo = min(coil_lo, float(l[i]))
            else:
                # squeeze ended without a clean close-break
                coil_active = False

        # Baselines on same walk
        if i >= 1 and day[i - 1] == d and MINS_LO <= mins[i] <= MINS_HI:
            green, red = c[i] > o[i], c[i] < o[i]
            prev_g, prev_r = c[i - 1] > o[i - 1], c[i - 1] < o[i - 1]
            if green and prev_g and streak_start(i, "BUY") == i - 1:
                row = emit_row("confirm1", i, "BUY")
                if row:
                    signals.append(row)
            if red and prev_r and streak_start(i, "SELL") == i - 1:
                row = emit_row("confirm1", i, "SELL")
                if row:
                    signals.append(row)

            # simple 20-bar box break baseline
            so = by_day[d][by_day[d] < i]
            if len(so) >= 8:
                look = so[-20:] if len(so) >= 20 else so[-8:]
                rh, rl = float(np.max(h[look])), float(np.min(l[look]))
                if green and float(c[i]) > rh:
                    row = emit_row("box20_break", i, "BUY")
                    if row:
                        signals.append(row)
                if red and float(c[i]) < rl:
                    row = emit_row("box20_break", i, "SELL")
                    if row:
                        signals.append(row)

    # OR30 first break baseline
    or_done = {d: {"u": False, "d": False} for d in keep}
    for i in range(n):
        d = day[i]
        if d not in keep or not (MINS_LO <= mins[i] <= MINS_HI):
            continue
        od = or_lv.get(d)
        if not od:
            continue
        if not or_done[d]["u"] and float(c[i]) > od["hi"] and c[i] > o[i]:
            or_done[d]["u"] = True
            row = emit_row("or30_break", i, "BUY")
            if row:
                signals.append(row)
        if not or_done[d]["d"] and float(c[i]) < od["lo"] and c[i] < o[i]:
            or_done[d]["d"] = True
            row = emit_row("or30_break", i, "SELL")
            if row:
                signals.append(row)

    # Dedupe coil_break same bar floods from box20 — keep all names separate
    print(f"signals={len(signals)}", flush=True)
    by_name = defaultdict(list)
    for r in signals:
        by_name[r["name"]].append(r)

    # Also: only first coil_break per day per side
    coil_rows = by_name.get("coil_break", [])
    coil_1 = []
    seen_cs = set()
    for r in sorted(coil_rows, key=lambda x: (x["day"], x["mins"])):
        k = (r["day"], r["side"])
        if k in seen_cs:
            continue
        seen_cs.add(k)
        coil_1.append(r)
    by_name["coil_break_1perside"] = coil_1

    books = []

    def add_book(label, rows, filt=None):
        hit = [r for r in rows if (filt(r) if filt else True)]
        # dedupe identical day/mins/side
        seen = set()
        uniq = []
        for r in sorted(hit, key=lambda x: (x["day"], x["mins"], x["side"])):
            k = (r["day"], r["mins"], r["side"])
            if k in seen:
                continue
            seen.add(k)
            uniq.append(r)
        st_all = pack(uniq, "clean40", mid)
        one = one_per_day(uniq)
        st_1d = pack(one, "clean40", mid)
        caught = {(r["day"], r["start_i"], r["side"]) for r in uniq if r.get("caught_true")}
        cov = round(100.0 * len(caught) / max(len(true_moves), 1), 1)
        avg_ext = (
            round(float(np.mean([r["ext"] for r in uniq if r["clean40"]])), 1)
            if any(r["clean40"] for r in uniq)
            else None
        )
        score = round((st_1d["prec"] or 0) / 100.0 * cov / 100.0 * 100, 2) if st_1d["n"] else 0
        books.append(
            {
                "name": label,
                "all": st_all,
                "one": st_1d,
                "coverage": cov,
                "caught_n": len(caught),
                "avg_ext": avg_ext,
                "score": score,
                "samples": one[:10],
            }
        )
        print(
            f"  {label}: 1d n={st_1d['n']} prec={st_1d['prec']}% oos={st_1d['oos_prec']}% "
            f"| all n={st_all['n']} prec={st_all['prec']}% | cov={cov}% score={score}",
            flush=True,
        )

    # Hybrid family
    for nm in ("coil_break", "coil_break_1perside"):
        rows = by_name.get(nm, [])
        add_book(nm, rows)
        add_book(f"{nm}+ctrl", rows, lambda r: r["ctrl"])
        add_book(f"{nm}+impulse", rows, lambda r: r["impulse"])
        add_book(f"{nm}+ctrl+impulse", rows, lambda r: r["ctrl"] and r["impulse"])
        add_book(f"{nm}+ctrl+impulse+ad", rows, lambda r: r["ctrl"] and r["impulse"] and r["ad"])
        add_book(f"{nm}+ctrl+impulse+held", rows, lambda r: r["ctrl"] and r["impulse"] and r["held"])
        add_book(f"{nm}+ctrl+impulse+atr_hi", rows, lambda r: r["ctrl"] and r["impulse"] and r["atr_hi"])
        add_book(
            f"{nm}+FULL",
            rows,
            lambda r: r["ctrl"] and r["impulse"] and r["ad"] and r["atr_hi"],
        )
        add_book(
            f"{nm}+FULL+held",
            rows,
            lambda r: r["ctrl"] and r["impulse"] and r["ad"] and r["held"] and r["atr_hi"],
        )

    # Baselines
    for nm in ("confirm1", "box20_break", "or30_break"):
        rows = by_name.get(nm, [])
        add_book(nm, rows)
        add_book(f"{nm}+ctrl+impulse", rows, lambda r: r["ctrl"] and r["impulse"])
        add_book(f"{nm}+ctrl+impulse+atr_hi", rows, lambda r: r["ctrl"] and r["impulse"] and r["atr_hi"])

    # Rank
    ranked = sorted(
        books,
        key=lambda b: (
            -(b["one"]["prec"] or 0) if (b["one"]["n"] or 0) >= 12 else -1,
            -b["coverage"],
            -(b["one"]["n"] or 0),
        ),
    )
    balanced = [b for b in books if (b["one"]["n"] or 0) >= 15]
    balanced.sort(key=lambda b: (-b["score"], -(b["one"]["prec"] or 0)))

    best_prec = next((b for b in ranked if (b["one"]["n"] or 0) >= 12), None)
    best_bal = balanced[0] if balanced else best_prec

    # Compare to prior headline numbers
    lines = [
        "# NIFTY 1m — Clean ≥40 **hybrid coil** (dual squeeze → impulse break)",
        "",
        "> Test: BB-width squeeze **AND** ATR compression ≥5 bars → Donchian break → impulse candle.",
        "> Success = clean one-direction ≥40 (only green to +40 / only red to −40).",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS **{mid}**. True clean40: **{len(true_moves)}**.",
        "",
        "## Recipe",
        "",
        "```",
        f"BB squeeze : bbWidth < SMA(bbWidth,{BB_LEN}) × {BB_SQUEEZE_THR}",
        f"ATR compress: ATR14 < SMA(ATR,{BB_LEN}) × {ATR_COMPRESS}",
        f"COIL       : both true for ≥ {MIN_COIL_BARS} bars; box = high/low during coil",
        f"BREAK      : close outside coil box (same-color body)",
        f"IMPULSE    : body ≥ {IMPULSE_BODY_ATR}×ATR + control close",
        "SUCCESS    : from streak open, only same-color until ±40",
        "```",
        "",
        "## Results",
        "",
        "| Gate | 1d n | 1d prec% | OOS% | all n | all prec% | Coverage% | score | avg ext |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for b in ranked:
        lines.append(
            f"| `{b['name']}` | {b['one']['n']} | **{b['one']['prec']}** | {b['one']['oos_prec']} | "
            f"{b['all']['n']} | {b['all']['prec']} | {b['coverage']} | {b['score']} | {b['avg_ext']} |"
        )

    lines += [
        "",
        "## vs prior markers (same metric)",
        "",
        "| Approach | Typical 1d prec | Coverage |",
        "|---|---:|---:|",
        "| confirm1 (prior) | ~29% | ~93% |",
        "| OR30+ctrl+atr_hi (prior) | ~43% | ~4% |",
        "| box break (prior) | ~25–28% | ~50% |",
    ]
    if best_prec:
        lines.append(
            f"| **This hybrid best prec** `{best_prec['name']}` | "
            f"**{best_prec['one']['prec']}%** | {best_prec['coverage']}% |"
        )
    if best_bal and best_bal != best_prec:
        lines.append(
            f"| **This hybrid best balance** `{best_bal['name']}` | "
            f"**{best_bal['one']['prec']}%** | {best_bal['coverage']}% |"
        )

    lines += ["", "## Verdict", ""]
    if best_prec and (best_prec["one"]["prec"] or 0) >= 50 and (best_prec["one"]["oos_prec"] or 0) >= 45:
        lines.append(
            f"**Improved.** `{best_prec['name']}` reaches **{best_prec['one']['prec']}%** 1d precision "
            f"(OOS {best_prec['one']['oos_prec']}%) — better than prior ~29–43% band for useful n."
        )
    elif best_prec and (best_prec["one"]["prec"] or 0) > 43:
        lines.append(
            f"**Modest gain.** Best `{best_prec['name']}` @ **{best_prec['one']['prec']}%** "
            f"(n={best_prec['one']['n']}, cov {best_prec['coverage']}%). Still not high-accuracy entry."
        )
    else:
        lines.append(
            "**No breakthrough.** Dual-squeeze hybrid did **not** clearly beat prior best ~43% "
            "OR30 precision (or stays in the same ballpark). Clean≥40 entry remains hard."
        )

    if best_bal:
        lines += [
            "",
            "### Samples (best balance 1/day)",
            "",
            "| Day | HM | Side | Entry | clean40 | ext | impulse | ctrl |",
            "|---|---|---|---:|---|---:|---|---|",
        ]
        for x in best_bal.get("samples") or []:
            lines.append(
                f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | "
                f"{x['clean40']} | {x['ext']} | {x['impulse']} | {x['ctrl']} |"
            )

    lines += ["", f"_Generated in {time.time() - t0:.1f}s._", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "true_n": len(true_moves),
                "books": books,
                "best_prec": best_prec["name"] if best_prec else None,
                "best_balance": best_bal["name"] if best_bal else None,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT}", flush=True)
    if best_prec:
        print(f"BEST_PREC={best_prec['name']} prec={best_prec['one']['prec']}% cov={best_prec['coverage']}%", flush=True)
    if best_bal:
        print(f"BEST_BAL={best_bal['name']} prec={best_bal['one']['prec']}% cov={best_bal['coverage']}% score={best_bal['score']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
