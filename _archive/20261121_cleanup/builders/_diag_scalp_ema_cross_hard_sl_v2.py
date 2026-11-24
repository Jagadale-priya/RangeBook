"""RESEARCH ONLY — EMA cross visual entry v2 · hard-SL bands · pos candles.

Matches user chart more tightly:
  1) EMA9×EMA20 cross (light × dark)
  2) Hold 3–8 bars: stack stays, price stays on correct side of EMA20
  3) Entry = first STRONG candle that leaves the hold (body≥0.7×ATR, closes away)

Also try EMA20×EMA50 as alt dark pair.

Accurate @ SL = MAE never ≥ SL against AND MFE > 0.
Report Acc at SL 10/15/20/25 and avg positive candles in direction.

  python -u prod_live/tests/builders/_diag_scalp_ema_cross_hard_sl_v2.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

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
from _diag_scalp_pa_bos_choch_fvg import (  # noqa: E402
    to_15m, structure_events, build_htf_bias, htf_bias_lookup,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_EMA_CROSS_HARD_SL_V2.md"
REPORT_JSON = OUT / "NIFTY_1M_EMA_CROSS_HARD_SL_V2.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 120
LOOKBACK_CAL = 240
FWD = 40
SLS = (10.0, 15.0, 20.0, 25.0)


def one_per_day(rows):
    byd = {}
    for r in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        if r["day"] not in byd:
            byd[r["day"]] = r
    return list(byd.values())


def path_stats(h, l, o, c, day, i, side):
    d = day[i]
    entry = float(c[i])
    mfe = mae = 0.0
    pos_run = 0
    first = True
    pos_tot = 0
    end = min(len(c) - 1, i + FWD)
    for j in range(i + 1, end + 1):
        if day[j] != d:
            break
        if side == "BUY":
            mfe = max(mfe, float(h[j]) - entry)
            mae = max(mae, entry - float(l[j]))
            good = c[j] > o[j]
        else:
            mfe = max(mfe, entry - float(l[j]))
            mae = max(mae, float(h[j]) - entry)
            good = c[j] < o[j]
        if good:
            pos_tot += 1
            if first:
                pos_run += 1
        else:
            first = False
    out = {"mfe": round(mfe, 2), "mae": round(mae, 2),
           "pos_run": pos_run, "pos_tot": pos_tot, "went": mfe > 0}
    for sl in SLS:
        out[f"acc_{int(sl)}"] = (mae < sl) and (mfe > 0)
        out[f"surv_{int(sl)}"] = mae < sl  # survived SL regardless of mfe
    return out


def pack(rows, key):
    if not rows:
        return None, 0
    return round(100.0 * sum(1 for r in rows if r.get(key)) / len(rows), 2), len(rows)


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("EMA cross hard-SL v2 (visual hold→strong)", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df = raw.copy()
    if "Open" not in df.columns and "open" in df.columns:
        df = df.rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume",
        })
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    close = df["Close"].astype(float)
    df["ema9"] = close.ewm(span=9, adjust=False).mean()
    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()

    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    mid = days_sorted[n_days // 2]
    last5 = set(days_sorted[-5:])
    df = df[[str(ts.date()) in keep for ts in df.index]].copy()
    print(f"{day_lo}→{day_hi} n={n_days}", flush=True)

    df15 = to_15m(df)
    bias15 = build_htf_bias(df15, structure_events(df15))

    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    atr = df["atr14"].astype(float).values
    vwap = df["vwap"].astype(float).values
    e9 = df["ema9"].astype(float).values
    e20 = df["ema20"].astype(float).values
    e50 = df["ema50"].astype(float).values
    pdi = df["plus_di"].astype(float).values
    mdi = df["minus_di"].astype(float).values
    day = np.array([str(ts.date()) for ts in df.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df.index])
    idx = df.index
    n = len(c)

    def find_entries(fast, slow, pair_name):
        rows = []
        for i in range(1, n):
            if day[i] != day[i - 1] or not (MINS_LO <= mins[i] <= MINS_HI):
                continue
            f, s = float(fast[i]), float(slow[i])
            fp, sp = float(fast[i - 1]), float(slow[i - 1])
            if not all(np.isfinite(x) for x in (f, s, fp, sp)):
                continue
            if fp >= sp and f < s:
                side = "SELL"
            elif fp <= sp and f > s:
                side = "BUY"
            else:
                continue
            cross_i = i
            # hold window
            hold_hi, hold_lo = float(h[i]), float(l[i])
            fired = False
            for k in range(1, 12):
                j = cross_i + k
                if j >= n or day[j] != day[cross_i] or mins[j] > MINS_HI:
                    break
                # stack must hold
                if side == "SELL" and not (fast[j] < slow[j]):
                    break
                if side == "BUY" and not (fast[j] > slow[j]):
                    break
                # price should stay roughly on correct side of slow during hold
                if side == "SELL" and float(c[j]) > float(slow[j]) + 0.15 * float(atr[j] or 8):
                    # mild reclaim — still allow if not too far
                    pass
                hold_hi = max(hold_hi, float(h[j]))
                hold_lo = min(hold_lo, float(l[j]))
                if k < 3:
                    continue
                a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else 8.0
                body = abs(c[j] - o[j])
                color_ok = (side == "SELL" and c[j] < o[j]) or (side == "BUY" and c[j] > o[j])
                strong = color_ok and body >= 0.7 * a
                broke = (
                    (side == "SELL" and float(c[j]) < hold_lo - 0.05)
                    or (side == "BUY" and float(c[j]) > hold_hi + 0.05)
                )
                away = (
                    (side == "SELL" and float(c[j]) <= float(slow[j]) - 0.25 * a)
                    or (side == "BUY" and float(c[j]) >= float(slow[j]) + 0.25 * a)
                )
                both_side = (
                    (side == "SELL" and float(c[j]) < float(fast[j]) and float(c[j]) < float(slow[j]))
                    or (side == "BUY" and float(c[j]) > float(fast[j]) and float(c[j]) > float(slow[j]))
                )
                if not ((strong and away) or (strong and broke) or (broke and away and color_ok)):
                    continue
                # quality flags
                vw = float(vwap[j]) if np.isfinite(vwap[j]) else float(c[j])
                entry = float(c[j])
                vwap_with = (side == "BUY" and entry >= vw) or (side == "SELL" and entry <= vw)
                e50_with = (side == "BUY" and entry >= float(e50[j])) or (side == "SELL" and entry <= float(e50[j]))
                di_ok = (side == "BUY" and pdi[j] > mdi[j]) or (side == "SELL" and mdi[j] > pdi[j])
                htf = htf_bias_lookup(bias15, idx[j])
                htf_with = (side == "BUY" and htf == "up") or (side == "SELL" and htf == "down")
                st = path_stats(h, l, o, c, day, j, side)
                rows.append({
                    "pair": pair_name, "day": day[j], "hm": idx[j].strftime("%H:%M"),
                    "mins": int(mins[j]), "side": side, "entry": round(entry, 2),
                    "cross_hm": idx[cross_i].strftime("%H:%M"), "delay": k,
                    "atr": round(a, 2), "strong": strong, "broke": broke,
                    "away": away, "both_side": both_side,
                    "vwap_with": vwap_with, "e50_with": e50_with,
                    "di_ok": bool(di_ok), "htf_with": bool(htf_with),
                    "atr12": a >= 12, "atr10": a >= 10, "am": mins[j] < 12 * 60,
                    **st,
                })
                fired = True
                break
            _ = fired
        return rows

    cands = find_entries(e9, e20, "ema9x20") + find_entries(e20, e50, "ema20x50")
    print(f"cands={len(cands)} 9x20={sum(1 for r in cands if r['pair']=='ema9x20')} "
          f"20x50={sum(1 for r in cands if r['pair']=='ema20x50')}", flush=True)

    def eval_one(name, pred):
        hit = one_per_day([r for r in cands if pred(r)])
        tr = [r for r in hit if r["day"] < mid]
        oo = [r for r in hit if r["day"] >= mid]
        accs = {f"a{int(sl)}": pack(hit, f"acc_{int(sl)}")[0] for sl in SLS}
        survs = {f"s{int(sl)}": pack(hit, f"surv_{int(sl)}")[0] for sl in SLS}
        a15_tr = pack(tr, "acc_15")[0]
        a15_oo = pack(oo, "acc_15")[0]
        n = len(hit)
        pct = accs["a15"] or 0
        if n >= 25 and pct >= 75 and (a15_oo or 0) >= 70 and (a15_tr or 0) >= 70:
            verd = "HIGH_75"
        elif n >= 20 and pct >= 70 and (a15_oo or 0) >= 65:
            verd = "OK_70"
        elif n >= 15 and pct >= 65:
            verd = "OK_65"
        elif n < 12:
            verd = "THIN"
        else:
            verd = "WEAK"
        avg_pos = round(float(np.mean([r["pos_run"] for r in hit])), 2) if hit else None
        avg_mfe = round(float(np.mean([r["mfe"] for r in hit])), 2) if hit else None
        avg_mae = round(float(np.mean([r["mae"] for r in hit])), 2) if hit else None
        return {
            "name": name, "verd": verd, "n": n, **accs, **survs,
            "train15": a15_tr, "oos15": a15_oo,
            "avg_pos_run": avg_pos, "avg_mfe": avg_mfe, "avg_mae": avg_mae,
            "last5": [r for r in hit if r["day"] in last5],
            "samples": hit[:6],
        }

    gates = []
    for pair in ("ema9x20", "ema20x50"):
        P = lambda r, p=pair: r["pair"] == p
        gates += [
            (f"{pair} visual", lambda r, p=pair: r["pair"] == p),
            (f"{pair} + both_side", lambda r, p=pair: r["pair"] == p and r["both_side"]),
            (f"{pair} + HTF", lambda r, p=pair: r["pair"] == p and r["htf_with"]),
            (f"{pair} + VWAP+HTF", lambda r, p=pair: r["pair"] == p and r["vwap_with"] and r["htf_with"]),
            (f"{pair} + DI+VWAP+HTF", lambda r, p=pair: r["pair"] == p and r["di_ok"] and r["vwap_with"] and r["htf_with"]),
            (f"{pair} + e50+HTF", lambda r, p=pair: r["pair"] == p and r["e50_with"] and r["htf_with"]),
            (f"{pair} + ATR12+HTF+VWAP", lambda r, p=pair: r["pair"] == p and r["atr12"] and r["htf_with"] and r["vwap_with"]),
            (f"{pair} + both+HTF+VWAP", lambda r, p=pair: r["pair"] == p and r["both_side"] and r["htf_with"] and r["vwap_with"]),
            (f"{pair} + strong+broke+HTF", lambda r, p=pair: r["pair"] == p and r["strong"] and r["broke"] and r["htf_with"]),
            (f"{pair} SELL + VWAP+HTF", lambda r, p=pair: r["pair"] == p and r["side"] == "SELL" and r["vwap_with"] and r["htf_with"]),
            (f"{pair} BUY + VWAP+HTF", lambda r, p=pair: r["pair"] == p and r["side"] == "BUY" and r["vwap_with"] and r["htf_with"]),
            (f"{pair} + AM+VWAP+HTF", lambda r, p=pair: r["pair"] == p and r["am"] and r["vwap_with"] and r["htf_with"]),
            (f"{pair} + delay3-6 + HTF+VWAP", lambda r, p=pair: r["pair"] == p and 3 <= r["delay"] <= 6 and r["htf_with"] and r["vwap_with"]),
        ]

    hunt = [eval_one(n, p) for n, p in gates]
    for st in sorted(hunt, key=lambda x: (-(x["a15"] or 0), -x["n"]))[:12]:
        print(
            f"  {st['verd']} {st['name']}: n={st['n']} "
            f"a15={st['a15']}% a20={st['a20']}% a25={st['a25']}% "
            f"pos={st['avg_pos_run']} oos={st['oos15']}%",
            flush=True,
        )

    hunt = sorted(hunt, key=lambda x: (
        {"HIGH_75": 0, "OK_70": 1, "OK_65": 2, "WEAK": 3, "THIN": 4}.get(x["verd"], 5),
        -(x["a15"] or 0), -(x["a20"] or 0), -x["n"],
    ))
    pick = hunt[0]

    lines = [
        "# NIFTY 1m — EMA cross **hold → strong** · hard SL (v2)",
        "",
        "> Your chart: light EMA crosses dark EMA → short hold → strong move.",
        "> Desk: **EMA9 × EMA20** (primary) · also test **EMA20 × EMA50**.",
        "",
        "**Accurate @ SL** = never goes ≥ SL pts against, AND moves with us.",
        "**pos_run** = consecutive candles in our color right after entry.",
        "",
        f"Window **{day_lo}→{day_hi}** ({n_days}d). OOS ≥ **{mid}**.",
        "",
        "| Gate | Verd | n | Acc@10 | Acc@15 | Acc@20 | Acc@25 | Train15 | OOS15 | pos_run | MFE | MAE |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for st in hunt:
        lines.append(
            f"| `{st['name']}` | **{st['verd']}** | {st['n']} | {st['a10']} | **{st['a15']}** | "
            f"{st['a20']} | {st['a25']} | {st['train15']} | {st['oos15']} | "
            f"**{st['avg_pos_run']}** | {st['avg_mfe']} | {st['avg_mae']} |"
        )

    lines += [
        "",
        "## Best",
        "",
        f"**`{pick['name']}`** · **{pick['verd']}**",
        f"- Acc@15 **{pick['a15']}%** · Acc@20 **{pick['a20']}%** · Acc@25 **{pick['a25']}%**",
        f"- avg **{pick['avg_pos_run']}** positive candles in direction after entry",
        f"- n={pick['n']} · MFE {pick['avg_mfe']} · MAE {pick['avg_mae']}",
        "",
        "## Last 5 sessions — best gate",
        "",
        "| Day | Cross→Entry | Side | Delay | Acc15 | Acc20 | MAE | MFE | pos_run |",
        "|---|---|---|---:|---|---|---:|---:|---:|",
    ]
    for r in sorted(pick["last5"], key=lambda x: x["day"]):
        lines.append(
            f"| {r['day']} | {r['cross_hm']}→{r['hm']} | **{r['side']}** @ {r['entry']} | "
            f"{r['delay']} | {'✓' if r['acc_15'] else '✗'} | {'✓' if r['acc_20'] else '✗'} | "
            f"{r['mae']} | {r['mfe']} | **{r['pos_run']}** |"
        )
    if not pick["last5"]:
        lines.append("| — | — | none fired | — | — | — | — | — | — |")

    # also dump raw ema9x20 last5 visual
    raw5 = one_per_day([r for r in cands if r["pair"] == "ema9x20" and r["day"] in last5])
    lines += [
        "",
        "## Last 5 — raw EMA9×20 visual (1/day)",
        "",
        "| Day | Cross→Entry | Side | Delay | Acc15 | Acc20 | MAE | MFE | pos_run | HTF | VWAP |",
        "|---|---|---|---:|---|---|---:|---:|---:|---|---|",
    ]
    for r in sorted(raw5, key=lambda x: x["day"]):
        lines.append(
            f"| {r['day']} | {r['cross_hm']}→{r['hm']} | **{r['side']}** @ {r['entry']} | "
            f"{r['delay']} | {'✓' if r['acc_15'] else '✗'} | {'✓' if r['acc_20'] else '✗'} | "
            f"{r['mae']} | {r['mfe']} | **{r['pos_run']}** | "
            f"{'Y' if r['htf_with'] else 'N'} | {'Y' if r['vwap_with'] else 'N'} |"
        )

    lines += [
        "",
        "## Read",
        "",
        "- If Acc@15 stays <65% even with HTF/VWAP → hard 15pt SL is too tight for this 1m cross alone.",
        "- Acc@20 / Acc@25 show whether the **same signal** works with a slightly wider hard stop.",
        "- High **pos_run** with low Acc@15 = move starts right but wick against tags the 15pt stop.",
        "",
        f"_Generated in {time.time()-t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({
        "pick": {k: pick[k] for k in pick if k not in ("samples", "last5")},
        "hunt": [{k: st[k] for k in st if k not in ("samples", "last5")} for st in hunt],
        "last5_pick": pick["last5"], "last5_raw9x20": raw5,
        "window": [day_lo, day_hi],
    }, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    print(f"PICK {pick['verd']} {pick['name']} a15={pick['a15']}% pos={pick['avg_pos_run']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
