"""RESEARCH ONLY — Large-dataset multi-fold validate of best HHLL gate.

Gate under test (from v2 HIGH_75):
  HL_confirm (BUY) / LH_confirm (SELL)
  + htf_with + atr≥10 + desk≥3 + streak≥4
  Exit: EMA34 trail · T15

Also checks sibling: held+htf+atr10+streak4

  python -u prod_live/tests/builders/_diag_scalp_hhll_large_validate.py
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
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators  # noqa: E402
from _diag_scalp_ad_sr_entry_1m import add_ad_obv_proxy  # noqa: E402
from _diag_scalp_pa_bos_choch_fvg import (  # noqa: E402
    to_15m, structure_events, build_htf_bias, htf_bias_lookup,
)

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_1m as scalper  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_HHLL_LARGE_VALIDATE.md"
REPORT_JSON = OUT / "NIFTY_1M_HHLL_LARGE_VALIDATE.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
# Use all available recent history up to ~500 sessions
N_SESSIONS = 500
LOOKBACK_CAL = 900
T15 = 15.0
L = 3


def one_per_day(rows):
    byd = {}
    for r in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        if r["day"] not in byd:
            byd[r["day"]] = r
    return list(byd.values())


def prec(rows):
    if not rows:
        return None, 0
    return round(100.0 * sum(1 for r in rows if r["t15_win"]) / len(rows), 2), len(rows)


def fold_stats(rows, days_sorted, n_folds=5):
    if not days_sorted or not rows:
        return []
    n = len(days_sorted)
    size = max(1, n // n_folds)
    out = []
    for fi in range(n_folds):
        lo_i = fi * size
        hi_i = n - 1 if fi == n_folds - 1 else min(n - 1, (fi + 1) * size - 1)
        lo, hi = days_sorted[lo_i], days_sorted[hi_i]
        fr = [r for r in rows if lo <= r["day"] <= hi]
        p, nn = prec(fr)
        out.append({"fold": fi + 1, "lo": lo, "hi": hi, "n": nn, "prec": p})
    return out


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("HHLL LARGE validate — multi-fold", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df = raw.copy()
    if "Open" not in df.columns and "open" in df.columns:
        df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    df = add_ad_obv_proxy(df)
    close = df["Close"].astype(float)
    df["ema9"] = close.ewm(span=9, adjust=False).mean()
    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()

    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    mid_day = days_sorted[n_days // 2]
    df = df[[str(ts.date()) in keep for ts in df.index]].copy()
    print(f"window {day_lo}→{day_hi} n={n_days} bars={len(df)} mid={mid_day}", flush=True)

    df15 = to_15m(df)
    bias15 = build_htf_bias(df15, structure_events(df15))

    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    atr = df["atr14"].astype(float).values
    vwap = df["vwap"].astype(float).values
    ema9 = df["ema9"].astype(float).values
    ema20 = df["ema20"].astype(float).values
    ema50 = df["ema50"].astype(float).values
    pdi = df["plus_di"].astype(float).values
    mdi = df["minus_di"].astype(float).values
    day = np.array([str(ts.date()) for ts in df.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df.index])
    idx = df.index
    n = len(c)

    is_sh = np.zeros(n, dtype=bool)
    is_sl = np.zeros(n, dtype=bool)
    for i in range(L, n - L):
        if h[i] >= np.max(h[i - L : i + L + 1]) - 1e-9:
            is_sh[i] = True
        if l[i] <= np.min(l[i - L : i + L + 1]) + 1e-9:
            is_sl[i] = True

    last_sh_px = last_sl_px = None
    last_hh = last_hl = last_lh = last_ll = None
    bias = None
    cands = []

    def upd_bias():
        nonlocal bias
        if last_hh and last_hl and (not last_lh or last_hh[0] > last_lh[0]) and (not last_ll or last_hl[0] > last_ll[0]):
            bias = "up"
        elif last_lh and last_ll and (not last_hh or last_lh[0] > last_hh[0]) and (not last_hl or last_ll[0] > last_hl[0]):
            bias = "down"

    print("walk…", flush=True)
    for i in range(n):
        d = day[i]
        new_high_tag = new_low_tag = None
        new_high_px = new_low_px = None

        if i >= L and is_sh[i - L]:
            j = i - L
            px = float(h[j])
            tag = None
            if last_sh_px is not None:
                tag = "HH" if px > last_sh_px else "LH"
            last_sh_px = px
            if tag:
                new_high_tag, new_high_px = tag, px
                if tag == "HH":
                    last_hh = (i, j, px)
                else:
                    last_lh = (i, j, px)

        if i >= L and is_sl[i - L]:
            j = i - L
            px = float(l[j])
            tag = None
            if last_sl_px is not None:
                tag = "HL" if px > last_sl_px else "LL"
            last_sl_px = px
            if tag:
                new_low_tag, new_low_px = tag, px
                if tag == "HL":
                    last_hl = (i, j, px)
                else:
                    last_ll = (i, j, px)

        upd_bias()
        if not (MINS_LO <= mins[i] <= MINS_HI) or d not in keep:
            continue

        # only HL/LH confirm with matching bias
        side = None
        tag = None
        level = None
        if new_low_tag == "HL" and bias == "up":
            side, tag, level = "BUY", "HL", new_low_px
        elif new_high_tag == "LH" and bias == "down":
            side, tag, level = "SELL", "LH", new_high_px
        if side is None:
            continue

        entry = float(c[i])
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        vw = float(vwap[i]) if np.isfinite(vwap[i]) else entry
        e9, e20, e50 = float(ema9[i]), float(ema20[i]), float(ema50[i])
        e34 = float(ema34[i]) if np.isfinite(ema34[i]) else entry
        vwap_with = (side == "BUY" and entry >= vw) or (side == "SELL" and entry <= vw)
        ema_with = (side == "BUY" and e9 >= e20) or (side == "SELL" and e9 <= e20)
        ema50_with = (side == "BUY" and entry >= e50) or (side == "SELL" and entry <= e50)
        gate34 = (side == "BUY" and entry >= e34) or (side == "SELL" and entry <= e34)
        di_ok = (side == "BUY" and pdi[i] > mdi[i]) or (side == "SELL" and mdi[i] > pdi[i])
        held = bool(di_ok and gate34 and vwap_with)
        desk_ge3 = sum([vwap_with, ema_with, ema50_with, gate34]) >= 3
        htf = htf_bias_lookup(bias15, idx[i])
        htf_with = (side == "BUY" and htf == "up") or (side == "SELL" and htf == "down")
        st = 0
        if (side == "BUY" and c[i] > o[i]) or (side == "SELL" and c[i] < o[i]):
            s = i
            while s - 1 >= 0 and day[s - 1] == d:
                if side == "BUY" and c[s - 1] > o[s - 1]:
                    s -= 1
                elif side == "SELL" and c[s - 1] < o[s - 1]:
                    s -= 1
                else:
                    break
            st = i - s + 1

        ok, reason, exit_px, j, pts = scalper.path_ma_trail(h, l, c, ema34, i, side, T15)
        cands.append({
            "day": d, "hm": idx[i].strftime("%H:%M"), "mins": int(mins[i]),
            "side": side, "entry": round(entry, 2), "tag": tag, "level": round(float(level), 2),
            "t15_win": bool(ok),
            "pts": round(float(pts), 2) if pts is not None else None,
            "atr": round(a, 2),
            "atr_hi": a >= 10.0,
            "atr_12": a >= 12.0,
            "held": held,
            "htf_with": bool(htf_with),
            "desk_ge3": desk_ge3,
            "streak4": st >= 4,
            "streak6": st >= 6,
            "gate_best": bool(htf_with and a >= 10.0 and desk_ge3 and st >= 4),
            "gate_held": bool(held and htf_with and a >= 10.0 and st >= 4),
            "gate_best12": bool(htf_with and a >= 12.0 and desk_ge3 and st >= 4),
        })

    print(f"HL/LH confirm cands: {len(cands)}", flush=True)

    gates = {
        "raw HL/LH confirm": lambda r: True,
        "BEST: htf+atr10+desk≥3+streak4": lambda r: r["gate_best"],
        "ALT: held+htf+atr10+streak4": lambda r: r["gate_held"],
        "TIGHT: htf+atr12+desk≥3+streak4": lambda r: r["gate_best12"],
        "BEST BUY only": lambda r: r["gate_best"] and r["side"] == "BUY",
        "BEST SELL only": lambda r: r["gate_best"] and r["side"] == "SELL",
    }

    results = []
    for name, pred in gates.items():
        hit = [r for r in cands if pred(r)]
        one = one_per_day(hit)
        p, nn = prec(one)
        pa, na = prec(hit)
        # mid split
        tr = [r for r in one if r["day"] < mid_day]
        oo = [r for r in one if r["day"] >= mid_day]
        pt, nt = prec(tr)
        po, no = prec(oo)
        folds = fold_stats(one, days_sorted, n_folds=5)
        fold_precs = [f["prec"] for f in folds if f["prec"] is not None and f["n"] >= 5]
        row = {
            "name": name,
            "n_1d": nn, "prec_1d": p,
            "n_all": na, "prec_all": pa,
            "train_n": nt, "train_prec": pt,
            "oos_n": no, "oos_prec": po,
            "coverage_pct": round(100.0 * nn / n_days, 1) if n_days else 0,
            "folds": folds,
            "fold_min": min(fold_precs) if fold_precs else None,
            "fold_avg": round(float(np.mean(fold_precs)), 2) if fold_precs else None,
            "avg_pts": round(float(np.mean([r["pts"] for r in one if r.get("pts") is not None])), 2) if one else None,
            "samples": one[:12],
        }
        # ship bar: n≥40, prec≥70, fold_min≥65, oos≥65, train≥65
        ship = (
            nn >= 40
            and (p or 0) >= 70
            and (row["fold_min"] or 0) >= 65
            and (po or 0) >= 65
            and (pt or 0) >= 65
        )
        # softer ship for rarer accurate gates
        ship_soft = (
            nn >= 25
            and (p or 0) >= 75
            and (row["fold_min"] or 0) >= 65
            and (po or 0) >= 70
            and (pt or 0) >= 65
        )
        row["ship"] = "SHIP" if ship else ("SHIP_SOFT" if ship_soft else "HOLD")
        results.append(row)
        print(
            f"  {name}: n={nn} T15={p}% tr={pt}% oos={po}% fold_min={row['fold_min']} "
            f"cov={row['coverage_pct']}% → {row['ship']}",
            flush=True,
        )

    best = next((r for r in results if r["name"].startswith("BEST:") and r["ship"] in ("SHIP", "SHIP_SOFT")), None)
    if not best:
        best = next((r for r in results if r["ship"] in ("SHIP", "SHIP_SOFT")), None)
    if not best:
        # pick highest fold_min among n>=25
        cands_r = [r for r in results if (r["n_1d"] or 0) >= 25]
        best = max(cands_r, key=lambda x: ((x["fold_min"] or 0), (x["prec_1d"] or 0))) if cands_r else results[1]

    lines = [
        "# NIFTY 1m — HHLL gate **LARGE** multi-fold validate",
        "",
        "> Gate: **HL confirm (BUY) / LH confirm (SELL)** + HTF15 + ATR≥10 + Desk≥3 + streak≥4",
        f"> Window **{day_lo} → {day_hi}** ({n_days}d). Mid-split **{mid_day}**. 5-fold WF.",
        "",
        "## Results",
        "",
        "| Gate | Ship | n | T15% | Train | OOS | fold_min | fold_avg | cov% | avg pts |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| `{r['name']}` | **{r['ship']}** | {r['n_1d']} | **{r['prec_1d']}** | "
            f"{r['train_prec']} | {r['oos_prec']} | {r['fold_min']} | {r['fold_avg']} | "
            f"{r['coverage_pct']} | {r['avg_pts']} |"
        )

    lines += ["", "## 5-fold detail (BEST gate)", ""]
    best_row = next(r for r in results if r["name"].startswith("BEST:"))
    lines += ["| Fold | From | To | n | T15% |", "|---|---|---|---:|---:|"]
    for f in best_row["folds"]:
        lines.append(f"| {f['fold']} | {f['lo']} | {f['hi']} | {f['n']} | {f['prec']} |")

    lines += ["", "## Verdict", ""]
    if best and best["ship"] in ("SHIP", "SHIP_SOFT"):
        lines += [
            f"**PASS → wire Scalper:** `{best['name']}` · **{best['ship']}**",
            f"- 1/day T15 **{best['prec_1d']}%** · fold_min **{best['fold_min']}%** · cov **{best['coverage_pct']}%**",
            "",
            "```",
            "Mode: hhll_t15",
            "UP:   HH+HL bias → HL confirm + HTF up + ATR≥10 + Desk≥3 + ≥4 green",
            "DOWN: LH+LL bias → LH confirm + HTF down + ATR≥10 + Desk≥3 + ≥4 red",
            "EXIT: EMA34 trail · T15 · live notify on new confirm",
            "```",
        ]
    else:
        lines += [
            f"**HOLD — do not wire yet.** Best=`{best['name'] if best else None}` "
            f"T15={best['prec_1d'] if best else None}% fold_min={best['fold_min'] if best else None}",
            "- Need n≥25–40 with fold_min≥65 and train/oos both ≥65–70.",
        ]

    lines += ["", "### Samples (BEST)", "", "| Day | HM | Side | Entry | tag | ATR | T15 | pts |", "|---|---|---|---:|---|---:|---|---:|"]
    for x in best_row["samples"]:
        lines.append(
            f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | "
            f"{x['tag']} | {x['atr']} | {x['t15_win']} | {x['pts']} |"
        )
    lines += ["", f"_Generated in {time.time()-t0:.1f}s._", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({
        "window": [day_lo, day_hi], "n_days": n_days, "mid": mid_day,
        "results": [{k: v for k, v in r.items() if k != "samples"} for r in results],
        "ship": best["ship"] if best else None,
        "best_name": best["name"] if best else None,
    }, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    print(f"SHIP_DECISION: {best['ship'] if best else None} · {best['name'] if best else None}", flush=True)
    print(f"done in {time.time()-t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
