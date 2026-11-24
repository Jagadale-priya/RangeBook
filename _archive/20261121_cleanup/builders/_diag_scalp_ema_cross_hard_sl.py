"""RESEARCH ONLY — Desk EMA9×EMA20 cross entry · hard SL accuracy (no T15 target).

User chart: light-blue EMA crosses dark-blue EMA → brief hold → strong move.
Desk overlays = EMA9 (fast/light) · EMA20 (slow/dark) · EMA50 · VWAP · BB.

Accurate trade (user def):
  after entry, MAE never hits hard SL (15 or 20 pts) against,
  AND price does move in our direction (MFE > 0).

Also count consecutive same-color candles in our direction after entry.

Entries hunted:
  A) cross bar close
  B) cross → hold N bars under/over EMA20 → break / strong candle
  C) cross → first impulse (body≥0.6×ATR or streak≥3)

  python -u prod_live/tests/builders/_diag_scalp_ema_cross_hard_sl.py
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
from _diag_scalp_pa_bos_choch_fvg import (  # noqa: E402
    to_15m, structure_events, build_htf_bias, htf_bias_lookup,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_EMA_CROSS_HARD_SL.md"
REPORT_JSON = OUT / "NIFTY_1M_EMA_CROSS_HARD_SL.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 120
LOOKBACK_CAL = 240
FWD = 45
HARD_SL = (15.0, 20.0)
HOLD_MIN, HOLD_MAX = 3, 10


def one_per_day(rows):
    byd = {}
    for r in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        if r["day"] not in byd:
            byd[r["day"]] = r
    return list(byd.values())


def score_path(h, l, o, c, day, i, side, hard_sl: float):
    """User accuracy: never MAE≥hard_sl against; did move with us."""
    d = day[i]
    entry = float(c[i])
    mfe = mae = 0.0
    hit_sl = False
    sl_bar = None
    pos_run = 0
    pos_total = 0
    first_pos = True
    end = min(len(c) - 1, i + FWD)
    for j in range(i + 1, end + 1):
        if day[j] != d:
            break
        if side == "BUY":
            mfe = max(mfe, float(h[j]) - entry)
            mae = max(mae, entry - float(l[j]))
            bull = c[j] > o[j]
            if not hit_sl:
                if bull:
                    pos_total += 1
                    if first_pos:
                        pos_run += 1
                else:
                    first_pos = False
        else:
            mfe = max(mfe, entry - float(l[j]))
            mae = max(mae, float(h[j]) - entry)
            bear = c[j] < o[j]
            if not hit_sl:
                if bear:
                    pos_total += 1
                    if first_pos:
                        pos_run += 1
                else:
                    first_pos = False
        if not hit_sl and mae >= hard_sl:
            hit_sl = True
            sl_bar = j - i
    went_with = mfe > 0.0
    accurate = (not hit_sl) and went_with
    # stronger: never hit SL and got at least hard_sl in favor (clean)
    clean = (not hit_sl) and mfe >= hard_sl
    return {
        "mfe": round(mfe, 2),
        "mae": round(mae, 2),
        "hit_sl": hit_sl,
        "sl_bar": sl_bar,
        "went_with": went_with,
        "accurate": accurate,
        "clean": clean,
        "pos_run": pos_run,
        "pos_total": pos_total,
    }


def pack(rows, key="accurate"):
    if not rows:
        return {"n": 0, "pct": None, "avg_mfe": None, "avg_mae": None,
                "avg_pos_run": None, "avg_pos_tot": None}
    pct = round(100.0 * sum(1 for r in rows if r.get(key)) / len(rows), 2)
    return {
        "n": len(rows),
        "pct": pct,
        "avg_mfe": round(float(np.mean([r["mfe"] for r in rows])), 2),
        "avg_mae": round(float(np.mean([r["mae"] for r in rows])), 2),
        "avg_pos_run": round(float(np.mean([r["pos_run"] for r in rows])), 2),
        "avg_pos_tot": round(float(np.mean([r["pos_total"] for r in rows])), 2),
    }


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("EMA9×EMA20 cross · hard SL 15/20 · no T15 target", flush=True)

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
    ema9 = df["ema9"].astype(float).values
    ema20 = df["ema20"].astype(float).values
    ema50 = df["ema50"].astype(float).values
    pdi = df["plus_di"].astype(float).values
    mdi = df["minus_di"].astype(float).values
    day = np.array([str(ts.date()) for ts in df.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df.index])
    idx = df.index
    n = len(c)

    # Detect crosses
    crosses = []  # (i, side) side=SELL when 9× below 20
    for i in range(1, n):
        if day[i] != day[i - 1]:
            continue
        if not (MINS_LO <= mins[i] <= MINS_HI):
            continue
        e9, e20 = float(ema9[i]), float(ema20[i])
        e9p, e20p = float(ema9[i - 1]), float(ema20[i - 1])
        if not all(np.isfinite(x) for x in (e9, e20, e9p, e20p)):
            continue
        cross_dn = e9p >= e20p and e9 < e20   # light below dark → SELL setup
        cross_up = e9p <= e20p and e9 > e20   # light above dark → BUY setup
        if cross_dn:
            crosses.append((i, "SELL"))
        elif cross_up:
            crosses.append((i, "BUY"))

    print(f"crosses={len(crosses)}", flush=True)

    def emit(mode, i, side, cross_i):
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        entry = float(c[i])
        vw = float(vwap[i]) if np.isfinite(vwap[i]) else entry
        e9, e20, e50 = float(ema9[i]), float(ema20[i]), float(ema50[i])
        vwap_with = (side == "BUY" and entry >= vw) or (side == "SELL" and entry <= vw)
        ema50_with = (side == "BUY" and entry >= e50) or (side == "SELL" and entry <= e50)
        stack = (side == "BUY" and e9 > e20) or (side == "SELL" and e9 < e20)
        price_vs20 = (side == "BUY" and entry >= e20) or (side == "SELL" and entry <= e20)
        di_ok = (side == "BUY" and pdi[i] > mdi[i]) or (side == "SELL" and mdi[i] > pdi[i])
        htf = htf_bias_lookup(bias15, idx[i])
        htf_with = (side == "BUY" and htf == "up") or (side == "SELL" and htf == "down")
        body = abs(c[i] - o[i])
        strong = body >= 0.6 * a and (
            (side == "BUY" and c[i] > o[i]) or (side == "SELL" and c[i] < o[i])
        )
        # streak of same color ending at i
        st = 0
        if (side == "BUY" and c[i] > o[i]) or (side == "SELL" and c[i] < o[i]):
            s = i
            while s - 1 >= 0 and day[s - 1] == day[i]:
                if side == "BUY" and c[s - 1] > o[s - 1]:
                    s -= 1
                elif side == "SELL" and c[s - 1] < o[s - 1]:
                    s -= 1
                else:
                    break
            st = i - s + 1
        delay = i - cross_i
        row = {
            "day": day[i], "hm": idx[i].strftime("%H:%M"), "mins": int(mins[i]),
            "side": side, "mode": mode, "entry": round(entry, 2), "atr": round(a, 2),
            "cross_hm": idx[cross_i].strftime("%H:%M"), "delay": delay,
            "vwap_with": bool(vwap_with), "ema50_with": bool(ema50_with),
            "stack": bool(stack), "price_vs20": bool(price_vs20),
            "di_ok": bool(di_ok), "htf_with": bool(htf_with),
            "strong": bool(strong), "streak3": st >= 3, "streak4": st >= 4,
            "atr10": a >= 10.0, "atr12": a >= 12.0, "am": int(mins[i]) < 12 * 60,
        }
        for sl in HARD_SL:
            sc = score_path(h, l, o, c, day, i, side, sl)
            tag = f"sl{int(sl)}"
            row[f"acc_{tag}"] = sc["accurate"]
            row[f"clean_{tag}"] = sc["clean"]
            row[f"hit_{tag}"] = sc["hit_sl"]
            if sl == 15.0:
                row.update({
                    "mfe": sc["mfe"], "mae": sc["mae"],
                    "pos_run": sc["pos_run"], "pos_total": sc["pos_total"],
                    "went_with": sc["went_with"],
                })
        return row

    cands: List[dict] = []
    used_entry = set()  # (day, mode, side, i) de-dupe

    for cross_i, side in crosses:
        d = day[cross_i]
        # A) immediate cross close
        row = emit("cross_bar", cross_i, side, cross_i)
        key = (d, "cross_bar", side, cross_i)
        if key not in used_entry:
            used_entry.add(key)
            cands.append(row)

        # B) hold then break / strong
        # hold = price stays on correct side of EMA20 for HOLD_MIN..HOLD_MAX bars
        hold_ok = True
        hold_hi = float(h[cross_i])
        hold_lo = float(l[cross_i])
        for k in range(1, HOLD_MAX + 1):
            j = cross_i + k
            if j >= n or day[j] != d or mins[j] > MINS_HI:
                break
            e20j = float(ema20[j])
            # still stacked after cross
            stacked = (side == "SELL" and ema9[j] < ema20[j]) or (side == "BUY" and ema9[j] > ema20[j])
            if not stacked:
                hold_ok = False
                break
            # during hold window, track range
            hold_hi = max(hold_hi, float(h[j]))
            hold_lo = min(hold_lo, float(l[j]))
            if k < HOLD_MIN:
                continue
            # entry triggers on break of hold range or strong candle
            a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else 8.0
            broke = (
                (side == "SELL" and float(c[j]) < hold_lo - 0.05)
                or (side == "BUY" and float(c[j]) > hold_hi + 0.05)
            )
            body = abs(c[j] - o[j])
            strong = body >= 0.6 * a and (
                (side == "BUY" and c[j] > o[j]) or (side == "SELL" and c[j] < o[j])
            )
            # also: price clearly away from EMA20
            away = (
                (side == "SELL" and float(c[j]) < e20j - 0.35 * a)
                or (side == "BUY" and float(c[j]) > e20j + 0.35 * a)
            )
            if broke or (strong and away) or (strong and broke):
                key = (d, "hold_break", side, j)
                if key not in used_entry:
                    used_entry.add(key)
                    cands.append(emit("hold_break", j, side, cross_i))
                break  # first hold_break per cross

        # C) first impulse after cross (streak≥3 or strong body), within 12 bars
        for k in range(1, 13):
            j = cross_i + k
            if j >= n or day[j] != d or mins[j] > MINS_HI:
                break
            stacked = (side == "SELL" and ema9[j] < ema20[j]) or (side == "BUY" and ema9[j] > ema20[j])
            if not stacked:
                break
            a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else 8.0
            body = abs(c[j] - o[j])
            strong = body >= 0.6 * a and (
                (side == "BUY" and c[j] > o[j]) or (side == "SELL" and c[j] < o[j])
            )
            st = 0
            if (side == "BUY" and c[j] > o[j]) or (side == "SELL" and c[j] < o[j]):
                s = j
                while s - 1 >= 0 and day[s - 1] == d:
                    if side == "BUY" and c[s - 1] > o[s - 1]:
                        s -= 1
                    elif side == "SELL" and c[s - 1] < o[s - 1]:
                        s -= 1
                    else:
                        break
                st = j - s + 1
            if strong or st >= 3:
                key = (d, "impulse", side, j)
                if key not in used_entry:
                    used_entry.add(key)
                    cands.append(emit("impulse", j, side, cross_i))
                break

    print(f"cands={len(cands)}", flush=True)

    def eval_gate(name, pred, key="acc_sl15"):
        hit = [r for r in cands if pred(r)]
        one = one_per_day(hit)
        tr = [r for r in one if r["day"] < mid]
        oo = [r for r in one if r["day"] >= mid]
        p15 = pack(one, "acc_sl15")
        p20 = pack(one, "acc_sl20")
        c15 = pack(one, "clean_sl15")
        c20 = pack(one, "clean_sl20")
        pt = pack(tr, "acc_sl15")
        po = pack(oo, "acc_sl15")
        # verdict on hard-SL accuracy (not T15)
        n = p15["n"]
        pct = p15["pct"] or 0
        oos = po["pct"] or 0
        trn = pt["pct"] or 0
        if n >= 25 and pct >= 75 and oos >= 70 and trn >= 70:
            verd = "HIGH_75"
        elif n >= 20 and pct >= 70 and oos >= 65 and trn >= 65:
            verd = "OK_70"
        elif n >= 15 and pct >= 65:
            verd = "OK_65"
        elif n < 15:
            verd = "THIN"
        else:
            verd = "WEAK"
        return {
            "name": name, "verd": verd,
            "n": n, "acc15": p15["pct"], "acc20": p20["pct"],
            "clean15": c15["pct"], "clean20": c20["pct"],
            "train15": pt["pct"], "oos15": po["pct"],
            "avg_mfe": p15["avg_mfe"], "avg_mae": p15["avg_mae"],
            "avg_pos_run": p15["avg_pos_run"], "avg_pos_tot": p15["avg_pos_tot"],
            "samples": one[:8],
            "last5": [r for r in one if r["day"] in last5],
        }

    gates = [
        ("A cross_bar", lambda r: r["mode"] == "cross_bar"),
        ("B hold_break (delay)", lambda r: r["mode"] == "hold_break"),
        ("C impulse after cross", lambda r: r["mode"] == "impulse"),
        ("B + price vs EMA20", lambda r: r["mode"] == "hold_break" and r["price_vs20"]),
        ("B + VWAP with", lambda r: r["mode"] == "hold_break" and r["vwap_with"]),
        ("B + HTF with", lambda r: r["mode"] == "hold_break" and r["htf_with"]),
        ("B + VWAP + HTF", lambda r: r["mode"] == "hold_break" and r["vwap_with"] and r["htf_with"]),
        ("B + strong candle", lambda r: r["mode"] == "hold_break" and r["strong"]),
        ("B + streak≥3", lambda r: r["mode"] == "hold_break" and r["streak3"]),
        ("B + ATR≥10 + HTF", lambda r: r["mode"] == "hold_break" and r["atr10"] and r["htf_with"]),
        ("B + ATR≥12 + HTF + VWAP", lambda r: r["mode"] == "hold_break" and r["atr12"] and r["htf_with"] and r["vwap_with"]),
        ("B + DI + VWAP + HTF", lambda r: r["mode"] == "hold_break" and r["di_ok"] and r["vwap_with"] and r["htf_with"]),
        ("B + EMA50 with + HTF", lambda r: r["mode"] == "hold_break" and r["ema50_with"] and r["htf_with"]),
        ("C + HTF + VWAP", lambda r: r["mode"] == "impulse" and r["htf_with"] and r["vwap_with"]),
        ("C + strong + HTF", lambda r: r["mode"] == "impulse" and r["strong"] and r["htf_with"]),
        ("C + ATR≥10 + HTF + VWAP", lambda r: r["mode"] == "impulse" and r["atr10"] and r["htf_with"] and r["vwap_with"]),
        ("C + streak≥3 + HTF + VWAP", lambda r: r["mode"] == "impulse" and r["streak3"] and r["htf_with"] and r["vwap_with"]),
        ("A + HTF + VWAP", lambda r: r["mode"] == "cross_bar" and r["htf_with"] and r["vwap_with"]),
        ("A + price vs20 + HTF", lambda r: r["mode"] == "cross_bar" and r["price_vs20"] and r["htf_with"]),
        ("B SELL only + HTF + VWAP", lambda r: r["mode"] == "hold_break" and r["side"] == "SELL" and r["htf_with"] and r["vwap_with"]),
        ("B BUY only + HTF + VWAP", lambda r: r["mode"] == "hold_break" and r["side"] == "BUY" and r["htf_with"] and r["vwap_with"]),
        ("B + AM + HTF + VWAP", lambda r: r["mode"] == "hold_break" and r["am"] and r["htf_with"] and r["vwap_with"]),
        ("B + delay≤6 + HTF + VWAP", lambda r: r["mode"] == "hold_break" and r["delay"] <= 6 and r["htf_with"] and r["vwap_with"]),
        ("B + delay 3-8 + strong + HTF", lambda r: r["mode"] == "hold_break" and 3 <= r["delay"] <= 8 and r["strong"] and r["htf_with"]),
    ]

    hunt = [eval_gate(n, p) for n, p in gates]
    for st in hunt:
        print(
            f"  {st['verd']} {st['name']}: n={st['n']} acc15={st['acc15']}% "
            f"acc20={st['acc20']}% clean15={st['clean15']}% pos_run={st['avg_pos_run']} "
            f"oos={st['oos15']}%",
            flush=True,
        )

    hunt = sorted(hunt, key=lambda x: (
        {"HIGH_75": 0, "OK_70": 1, "OK_65": 2, "THIN": 4, "WEAK": 3}.get(x["verd"], 5),
        -(x["acc15"] or 0), -(x["n"] or 0),
    ))
    pick = hunt[0]

    # last 5: show hold_break and impulse raw + pick
    hb_last5 = one_per_day([r for r in cands if r["mode"] == "hold_break" and r["day"] in last5])
    pred_map = {n: p for n, p in gates}
    pick_last5 = one_per_day([r for r in cands if pred_map[pick["name"]](r) and r["day"] in last5])

    lines = [
        "# NIFTY 1m — **EMA9×EMA20 cross** · hard SL accuracy (no T15)",
        "",
        "> Desk indications: **light blue = EMA9**, **dark blue = EMA20**.",
        "> Cross below → SELL setup · cross above → BUY setup.",
        "> Optional: short **hold**, then break / strong candle (your chart pattern).",
        "",
        "**Accurate** = after entry, never goes **≥15 (or 20) pts against**, AND moves in our direction.",
        "**Clean** = never hits hard SL AND MFE ≥ hard SL the other way.",
        "**pos_run** = consecutive same-color candles in our direction right after entry.",
        "",
        f"Window **{day_lo}→{day_hi}** ({n_days}d). OOS ≥ **{mid}**.",
        "",
        "| Gate | Verd | n | Acc@15 | Acc@20 | Clean@15 | Train | OOS | avg MFE | avg MAE | pos_run | pos_tot |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for st in hunt:
        lines.append(
            f"| `{st['name']}` | **{st['verd']}** | {st['n']} | **{st['acc15']}** | {st['acc20']} | "
            f"{st['clean15']} | {st['train15']} | {st['oos15']} | {st['avg_mfe']} | {st['avg_mae']} | "
            f"{st['avg_pos_run']} | {st['avg_pos_tot']} |"
        )

    lines += [
        "",
        "## Best",
        "",
        f"**`{pick['name']}`** · **{pick['verd']}**",
        f"- Acc@15 **{pick['acc15']}%** · Acc@20 **{pick['acc20']}%** · Clean@15 **{pick['clean15']}%**",
        f"- n={pick['n']} · train {pick['train15']}% · oos {pick['oos15']}%",
        f"- avg MFE {pick['avg_mfe']} · avg MAE {pick['avg_mae']} · avg pos_run **{pick['avg_pos_run']}** candles",
        "",
        "```",
        "SIGNAL : EMA9 crosses EMA20 (light × dark)",
        "SELL   : 9 crosses below 20 → hold under 20 → break / strong red",
        "BUY    : 9 crosses above 20 → hold over 20 → break / strong green",
        "ACCURATE: MAE < 15–20 pts against, and price moves with us",
        "```",
        "",
        "## Last 5 sessions — hold_break (1/day)",
        "",
        "| Day | Cross | Entry | Side | Delay | Acc@15 | Acc@20 | MAE | MFE | pos_run | pos_tot |",
        "|---|---|---|---|---:|---|---|---:|---:|---:|---:|",
    ]
    for r in sorted(hb_last5, key=lambda x: x["day"]):
        lines.append(
            f"| {r['day']} | {r['cross_hm']} | {r['hm']} **{r['side']}** @ {r['entry']} | "
            f"{r['side']} | {r['delay']} | "
            f"{'✓' if r['acc_sl15'] else '✗'} | {'✓' if r['acc_sl20'] else '✗'} | "
            f"{r['mae']} | {r['mfe']} | {r['pos_run']} | {r['pos_total']} |"
        )
    if not hb_last5:
        lines.append("| — | — | — | — | — | — | — | — | — | — | — |")

    lines += [
        "",
        f"## Last 5 — best gate `{pick['name']}`",
        "",
        "| Day | Cross | Entry | Side | Delay | Acc@15 | MAE | MFE | pos_run |",
        "|---|---|---|---|---:|---|---:|---:|---:|",
    ]
    for r in sorted(pick_last5, key=lambda x: x["day"]):
        lines.append(
            f"| {r['day']} | {r['cross_hm']} | {r['hm']} **{r['side']}** @ {r['entry']} | "
            f"{r['side']} | {r['delay']} | "
            f"{'✓' if r['acc_sl15'] else '✗'} | {r['mae']} | {r['mfe']} | {r['pos_run']} |"
        )
    if not pick_last5:
        lines.append("| — | — | — | — | — | none | — | — | — |")

    lines += ["", f"_Generated in {time.time()-t0:.1f}s._", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({
        "pick": pick, "hunt": [
            {k: st[k] for k in (
                "name", "verd", "n", "acc15", "acc20", "clean15", "clean20",
                "train15", "oos15", "avg_mfe", "avg_mae", "avg_pos_run", "avg_pos_tot",
            )} for st in hunt
        ],
        "last5_hold_break": hb_last5, "last5_pick": pick_last5,
        "window": [day_lo, day_hi],
    }, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    print(
        f"PICK: {pick['verd']} {pick['name']} acc15={pick['acc15']}% "
        f"pos_run={pick['avg_pos_run']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
