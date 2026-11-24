"""RESEARCH ONLY — Stabilize HHLL HL/LH confirm on 500d (find SHIP gate).

Reuses same structure walk; hunts quality combos with:
  n≥30, T15≥70, train≥65, oos≥65, fold_min≥65 (5-fold)

  python -u prod_live/tests/builders/_diag_scalp_hhll_large_stabilize.py
"""
from __future__ import annotations

import json
import sys
import time
from itertools import combinations
from pathlib import Path

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
REPORT = OUT / "NIFTY_1M_HHLL_LARGE_STABILIZE.md"
REPORT_JSON = OUT / "NIFTY_1M_HHLL_LARGE_STABILIZE.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
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


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("HHLL stabilize hunt on 500d", flush=True)

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
    mid = days_sorted[n_days // 2]
    df = df[[str(ts.date()) in keep for ts in df.index]].copy()
    print(f"{day_lo}→{day_hi} n={n_days}", flush=True)

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

    for i in range(n):
        d = day[i]
        new_high_tag = new_low_tag = None
        new_high_px = new_low_px = None
        if i >= L and is_sh[i - L]:
            j = i - L
            px = float(h[j])
            tag = "HH" if last_sh_px is not None and px > last_sh_px else ("LH" if last_sh_px is not None else None)
            if last_sh_px is not None and px == last_sh_px:
                tag = "LH"  # equal → treat as not HH
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
        side = tag = level = None
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
        rng = max(h[i] - l[i], 0.05)
        loc = (c[i] - l[i]) / rng
        ctrl = (side == "BUY" and loc >= 0.65 and c[i] > o[i]) or (side == "SELL" and loc <= 0.35 and c[i] < o[i])
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
        # session time buckets
        m = int(mins[i])
        skip_open = m >= 9 * 60 + 45
        am = m < 12 * 60
        prime = (9 * 60 + 45) <= m <= (12 * 60 + 30) or (13 * 60 + 15) <= m <= (14 * 60 + 15)

        ok, reason, exit_px, j, pts = scalper.path_ma_trail(h, l, c, ema34, i, side, T15)
        cands.append({
            "day": d, "hm": idx[i].strftime("%H:%M"), "mins": m, "side": side,
            "entry": round(entry, 2), "tag": tag, "t15_win": bool(ok),
            "pts": round(float(pts), 2) if pts is not None else None,
            "held": held, "htf_with": bool(htf_with), "desk_ge3": desk_ge3,
            "atr_hi": a >= 10.0, "atr_12": a >= 12.0, "atr_14": a >= 14.0,
            "streak4": st >= 4, "streak5": st >= 5, "streak6": st >= 6,
            "ctrl": bool(ctrl), "ema_with": bool(ema_with), "vwap_with": bool(vwap_with),
            "skip_open": skip_open, "am": am, "prime": prime,
            "buy": side == "BUY", "sell": side == "SELL",
        })

    print(f"cands={len(cands)}", flush=True)

    feat = [
        "held", "htf_with", "desk_ge3", "atr_hi", "atr_12", "atr_14",
        "streak4", "streak5", "streak6", "ctrl", "ema_with", "vwap_with",
        "skip_open", "prime", "am",
    ]

    def eval_one(name, hit):
        one = one_per_day(hit)
        p, nn = prec(one)
        tr = [r for r in one if r["day"] < mid]
        oo = [r for r in one if r["day"] >= mid]
        pt, nt = prec(tr)
        po, no = prec(oo)
        # 5 folds
        size = max(1, n_days // 5)
        fprecs = []
        folds = []
        for fi in range(5):
            lo = days_sorted[fi * size]
            hi_d = days_sorted[min(n_days - 1, (fi + 1) * size - 1 if fi < 4 else n_days - 1)]
            fr = [r for r in one if lo <= r["day"] <= hi_d]
            fp, fn = prec(fr)
            folds.append({"fold": fi + 1, "n": fn, "prec": fp, "lo": lo, "hi": hi_d})
            if fn >= 5 and fp is not None:
                fprecs.append(fp)
        fmin = min(fprecs) if fprecs else None
        ship = (
            nn >= 30 and (p or 0) >= 70 and (pt or 0) >= 65 and (po or 0) >= 65
            and (fmin or 0) >= 65
        )
        soft = (
            nn >= 25 and (p or 0) >= 72 and (pt or 0) >= 65 and (po or 0) >= 68
            and (fmin or 0) >= 60
        )
        return {
            "name": name, "n": nn, "prec": p, "train": pt, "oos": po,
            "fold_min": fmin, "fold_avg": round(float(np.mean(fprecs)), 2) if fprecs else None,
            "folds": folds, "ship": "SHIP" if ship else ("SOFT" if soft else "HOLD"),
            "samples": one[:8],
        }

    hunt = []
    # curated
    curated = [
        ("htf+atr12+desk+streak4", lambda r: r["htf_with"] and r["atr_12"] and r["desk_ge3"] and r["streak4"]),
        ("held+htf+atr12+streak4", lambda r: r["held"] and r["htf_with"] and r["atr_12"] and r["streak4"]),
        ("htf+atr12+desk+streak4+ctrl", lambda r: r["htf_with"] and r["atr_12"] and r["desk_ge3"] and r["streak4"] and r["ctrl"]),
        ("htf+atr12+desk+streak4+skip", lambda r: r["htf_with"] and r["atr_12"] and r["desk_ge3"] and r["streak4"] and r["skip_open"]),
        ("htf+atr12+desk+streak4+prime", lambda r: r["htf_with"] and r["atr_12"] and r["desk_ge3"] and r["streak4"] and r["prime"]),
        ("htf+atr14+desk+streak4", lambda r: r["htf_with"] and r["atr_14"] and r["desk_ge3"] and r["streak4"]),
        ("held+htf+atr14+streak4", lambda r: r["held"] and r["htf_with"] and r["atr_14"] and r["streak4"]),
        ("htf+atr12+desk+streak5", lambda r: r["htf_with"] and r["atr_12"] and r["desk_ge3"] and r["streak5"]),
        ("htf+atr12+desk+streak6", lambda r: r["htf_with"] and r["atr_12"] and r["desk_ge3"] and r["streak6"]),
        ("held+htf+atr12+streak4+ctrl", lambda r: r["held"] and r["htf_with"] and r["atr_12"] and r["streak4"] and r["ctrl"]),
        ("held+htf+atr12+streak4+prime", lambda r: r["held"] and r["htf_with"] and r["atr_12"] and r["streak4"] and r["prime"]),
        ("htf+atr12+streak4+ctrl+prime", lambda r: r["htf_with"] and r["atr_12"] and r["streak4"] and r["ctrl"] and r["prime"]),
        ("SELL htf+atr12+desk+streak4", lambda r: r["sell"] and r["htf_with"] and r["atr_12"] and r["desk_ge3"] and r["streak4"]),
        ("BUY htf+atr12+desk+streak4", lambda r: r["buy"] and r["htf_with"] and r["atr_12"] and r["desk_ge3"] and r["streak4"]),
        ("htf+atr12+desk+streak4+ema", lambda r: r["htf_with"] and r["atr_12"] and r["desk_ge3"] and r["streak4"] and r["ema_with"]),
    ]
    for name, pred in curated:
        st = eval_one(name, [r for r in cands if pred(r)])
        hunt.append(st)
        print(f"  {st['ship']} {name}: n={st['n']} T15={st['prec']}% tr={st['train']}% oos={st['oos']}% fmin={st['fold_min']}", flush=True)

    # combo hunt requiring atr_12 or atr_14 + htf
    print("combo hunt…", flush=True)
    for k in (3, 4, 5):
        for combo in combinations(feat, k):
            if "htf_with" not in combo:
                continue
            if not any(x in combo for x in ("atr_12", "atr_14", "atr_hi")):
                continue
            if not any(x in combo for x in ("streak4", "streak5", "streak6")):
                continue
            hit = [r for r in cands if all(r.get(f) for f in combo)]
            one = one_per_day(hit)
            if len(one) < 25:
                continue
            p, _ = prec(one)
            if (p or 0) < 70:
                continue
            st = eval_one("+".join(combo), hit)
            if st["ship"] in ("SHIP", "SOFT") or (st["fold_min"] or 0) >= 60 and (st["prec"] or 0) >= 72:
                hunt.append(st)

    # dedupe by name
    seen = set()
    uniq = []
    for hrow in sorted(hunt, key=lambda x: (-(x["fold_min"] or 0), -(x["prec"] or 0), -x["n"])):
        if hrow["name"] in seen:
            continue
        seen.add(hrow["name"])
        uniq.append(hrow)
    hunt = uniq

    ships = [h for h in hunt if h["ship"] == "SHIP"]
    softs = [h for h in hunt if h["ship"] == "SOFT"]
    print(f"SHIP={len(ships)} SOFT={len(softs)}", flush=True)
    for hrow in (ships or softs or hunt)[:15]:
        print(f"  [{hrow['ship']}] {hrow['name']}: n={hrow['n']} T15={hrow['prec']}% fmin={hrow['fold_min']}", flush=True)

    pick = ships[0] if ships else (softs[0] if softs else hunt[0])

    lines = [
        "# NIFTY 1m — HHLL **stabilize** on 500d",
        "",
        f"Window **{day_lo}→{day_hi}** ({n_days}d). Goal: SHIP = n≥30 · T15≥70 · train/oos≥65 · fold_min≥65.",
        "",
        f"SHIP count: **{len(ships)}** · SOFT: **{len(softs)}**",
        "",
        "| Gate | Ship | n | T15% | Train | OOS | fold_min | fold_avg |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for hrow in hunt[:40]:
        lines.append(
            f"| `{hrow['name']}` | **{hrow['ship']}** | {hrow['n']} | **{hrow['prec']}** | "
            f"{hrow['train']} | {hrow['oos']} | {hrow['fold_min']} | {hrow['fold_avg']} |"
        )

    lines += ["", "## Decision", ""]
    if pick and pick["ship"] == "SHIP":
        lines += [
            f"**WIRE Scalper:** `{pick['name']}`",
            f"- T15 **{pick['prec']}%** · fold_min **{pick['fold_min']}%** · n={pick['n']}",
        ]
    elif pick and pick["ship"] == "SOFT":
        lines += [
            f"**WIRE as chart+notify with caution (SOFT):** `{pick['name']}`",
            f"- T15 **{pick['prec']}%** · fold_min **{pick['fold_min']}%** · n={pick['n']}",
            "- fold_min below hard 65 — show indication; notify OK if user accepts ~60% worst fold",
        ]
    else:
        lines += [
            "**Do not wire live calls yet** — no fold-stable ≥70% gate on 500d.",
            "- Can still add **chart indication only** (markers, no notify) for visual study.",
        ]

    if pick:
        lines += ["", "### Folds", "", "| Fold | From | To | n | T15 |", "|---|---|---|---:|---:|"]
        for f in pick["folds"]:
            lines.append(f"| {f['fold']} | {f['lo']} | {f['hi']} | {f['n']} | {f['prec']} |")

    lines += ["", f"_Generated in {time.time()-t0:.1f}s._", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({
        "ships": ships[:10], "softs": softs[:10], "pick": pick,
        "window": [day_lo, day_hi],
    }, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    print(f"PICK: {pick['ship']} {pick['name']} T15={pick['prec']}% fmin={pick['fold_min']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
