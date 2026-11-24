"""RESEARCH ONLY — HHLL confirm ONLY at swing / OR resistance walls.

Gap filled: HL/LH structure entry required to sit on a real wall
  OR15 / OR30 · swing cluster · PDH/PDL · 15m L3 S/R

Then apply SHIP-style quality gates and score EMA34 trail T15.
Also print last-5-session calls for the best gate.

  python -u prod_live/tests/builders/_diag_scalp_hhll_at_swing_wall.py
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
    to_15m, structure_events, build_htf_bias, htf_bias_lookup, swing_points,
)

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_1m as scalper  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_HHLL_AT_SWING_WALL.md"
REPORT_JSON = OUT / "NIFTY_1M_HHLL_AT_SWING_WALL.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 500
LOOKBACK_CAL = 900
T15 = 15.0
L = 3
ZONE_ATR = 0.45
OR15, OR30 = 15, 30
SWING_LOOK = 80


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


def near(a, b, atr_v, k=ZONE_ATR):
    return abs(float(a) - float(b)) <= k * float(atr_v)


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("HHLL at swing/OR wall · 500d · T15", flush=True)

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
    last5 = set(days_sorted[-5:])
    df = df[[str(ts.date()) in keep for ts in df.index]].copy()
    print(f"{day_lo}→{day_hi} n={n_days} last5={sorted(last5)}", flush=True)

    df15 = to_15m(df)
    bias15 = build_htf_bias(df15, structure_events(df15))
    h15 = df15["High"].astype(float).values
    l15 = df15["Low"].astype(float).values
    idx15 = df15.index
    sh15, sl15 = swing_points(h15, l15, L=3)
    # causal 15m levels available after confirm (+L bars)
    levels15_hi: List[Tuple[pd.Timestamp, float]] = []
    levels15_lo: List[Tuple[pd.Timestamp, float]] = []
    for j in sh15:
        conf = j + 3
        if conf < len(idx15):
            levels15_hi.append((idx15[conf], float(h15[j])))
    for j in sl15:
        conf = j + 3
        if conf < len(idx15):
            levels15_lo.append((idx15[conf], float(l15[j])))

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

    # prior day H/L
    by_day: Dict[str, List[int]] = defaultdict(list)
    for i in range(n):
        by_day[day[i]].append(i)
    pdh: Dict[str, float] = {}
    pdl: Dict[str, float] = {}
    prev_d = None
    for d in days_sorted:
        if prev_d is not None and prev_d in by_day:
            ixs = by_day[prev_d]
            pdh[d] = float(np.max(h[ixs]))
            pdl[d] = float(np.min(l[ixs]))
        prev_d = d

    # OR15 / OR30
    or15_hi = np.full(n, np.nan)
    or15_lo = np.full(n, np.nan)
    or30_hi = np.full(n, np.nan)
    or30_lo = np.full(n, np.nan)
    sess_i = np.zeros(n, dtype=int)
    for d, ixs in by_day.items():
        for k, i in enumerate(ixs):
            sess_i[i] = k
        if len(ixs) >= OR15:
            hi15 = float(np.max(h[ixs[:OR15]]))
            lo15 = float(np.min(l[ixs[:OR15]]))
            for i in ixs[OR15:]:
                or15_hi[i], or15_lo[i] = hi15, lo15
        if len(ixs) >= OR30:
            hi30 = float(np.max(h[ixs[:OR30]]))
            lo30 = float(np.min(l[ixs[:OR30]]))
            for i in ixs[OR30:]:
                or30_hi[i], or30_lo[i] = hi30, lo30

    # 1m swing pivots + clusters
    is_sh = np.zeros(n, dtype=bool)
    is_sl = np.zeros(n, dtype=bool)
    for i in range(L, n - L):
        if h[i] >= np.max(h[i - L : i + L + 1]) - 1e-9:
            is_sh[i] = True
        if l[i] <= np.min(l[i - L : i + L + 1]) + 1e-9:
            is_sl[i] = True

    # confirmed swing availability at bar i (pivot at i-L)
    sh_run: List[Tuple[int, float]] = []
    sl_run: List[Tuple[int, float]] = []
    cluster_levels: List[List[float]] = [[] for _ in range(n)]

    last_sh_px = last_sl_px = None
    last_hh = last_hl = last_lh = last_ll = None
    bias = None
    cands = []

    def upd_bias():
        nonlocal bias
        if last_hh and last_hl and (not last_lh or last_hh[0] > last_lh[0]) and (not last_ll or last_hl[0] > last_ll[0]):
            bias = "up"
        elif last_lh and last_ll and (not last_hh or last_lh[0] > last_hh[0]) and (not last_hl or last_ll[0] > last_ll[0]):
            bias = "down"

    # pointer into 15m levels
    p15h = p15l = 0
    avail15_hi: List[float] = []
    avail15_lo: List[float] = []

    for i in range(n):
        # advance 15m levels causally
        ts = idx[i]
        while p15h < len(levels15_hi) and levels15_hi[p15h][0] <= ts:
            avail15_hi.append(levels15_hi[p15h][1])
            avail15_hi = avail15_hi[-8:]
            p15h += 1
        while p15l < len(levels15_lo) and levels15_lo[p15l][0] <= ts:
            avail15_lo.append(levels15_lo[p15l][1])
            avail15_lo = avail15_lo[-8:]
            p15l += 1

        if i >= L and is_sh[i - L]:
            j = i - L
            sh_run.append((j, float(h[j])))
            sh_run = [(ii, pp) for ii, pp in sh_run if i - ii <= SWING_LOOK][-12:]
        if i >= L and is_sl[i - L]:
            j = i - L
            sl_run.append((j, float(l[j])))
            sl_run = [(ii, pp) for ii, pp in sl_run if i - ii <= SWING_LOOK][-12:]

        recent = sorted(sh_run + sl_run, key=lambda x: x[1])
        out = []
        if recent:
            cur = [recent[0]]
            for p in recent[1:]:
                span = max(abs(p[1]) * 0.0025, 4.0)
                if abs(p[1] - cur[-1][1]) <= span:
                    cur.append(p)
                else:
                    if len(cur) >= 2:
                        out.append(float(np.mean([x[1] for x in cur])))
                    cur = [p]
            if len(cur) >= 2:
                out.append(float(np.mean([x[1] for x in cur])))
        cluster_levels[i] = out[-6:]

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
        side = tag = level = None
        if new_low_tag == "HL" and bias == "up":
            side, tag, level = "BUY", "HL", new_low_px
        elif new_high_tag == "LH" and bias == "down":
            side, tag, level = "SELL", "LH", new_high_px
        if side is None or level is None:
            continue

        entry = float(c[i])
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        walls = []
        # OR15
        if np.isfinite(or15_hi[i]) and near(level, or15_hi[i], a):
            walls.append("OR15_HI")
        if np.isfinite(or15_lo[i]) and near(level, or15_lo[i], a):
            walls.append("OR15_LO")
        # OR30
        if np.isfinite(or30_hi[i]) and near(level, or30_hi[i], a):
            walls.append("OR30_HI")
        if np.isfinite(or30_lo[i]) and near(level, or30_lo[i], a):
            walls.append("OR30_LO")
        # PDH/PDL
        if d in pdh and near(level, pdh[d], a):
            walls.append("PDH")
        if d in pdl and near(level, pdl[d], a):
            walls.append("PDL")
        # 1m swing cluster
        for p in cluster_levels[i]:
            if near(level, p, a):
                walls.append("SWING_CLUSTER")
                break
        # 15m L3
        for p in avail15_hi[-6:]:
            if near(level, p, a):
                walls.append("L15_HI")
                break
        for p in avail15_lo[-6:]:
            if near(level, p, a):
                walls.append("L15_LO")
                break

        # also: entry itself near wall (HL/LH pivot may sit just off; allow entry near)
        entry_walls = []
        for name, px in [
            ("OR15_HI", or15_hi[i]), ("OR15_LO", or15_lo[i]),
            ("OR30_HI", or30_hi[i]), ("OR30_LO", or30_lo[i]),
            ("PDH", pdh.get(d)), ("PDL", pdl.get(d)),
        ]:
            if px is not None and np.isfinite(px) and near(entry, px, a):
                entry_walls.append(name)
        for p in cluster_levels[i]:
            if near(entry, p, a):
                entry_walls.append("SWING_CLUSTER")
                break
        for p in avail15_hi[-6:]:
            if near(entry, p, a):
                entry_walls.append("L15_HI")
                break
        for p in avail15_lo[-6:]:
            if near(entry, p, a):
                entry_walls.append("L15_LO")
                break

        wall_any = sorted(set(walls + entry_walls))
        at_wall = len(wall_any) > 0
        at_or = any(w.startswith("OR") for w in wall_any)
        at_swing = "SWING_CLUSTER" in wall_any or any(w.startswith("L15") for w in wall_any)
        at_pd = "PDH" in wall_any or "PDL" in wall_any
        # resist/support role
        if side == "SELL":
            role_ok = any(w.endswith("_HI") or w == "PDH" or w == "SWING_CLUSTER" for w in wall_any)
        else:
            role_ok = any(w.endswith("_LO") or w == "PDL" or w == "SWING_CLUSTER" for w in wall_any)

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
        m = int(mins[i])
        am = m < 12 * 60
        skip_open = m >= 9 * 60 + 45
        prime = (9 * 60 + 45) <= m <= (12 * 60 + 30) or (13 * 60 + 15) <= m <= (14 * 60 + 15)

        ok, reason, exit_px, j, pts = scalper.path_ma_trail(h, l, c, ema34, i, side, T15)
        cands.append({
            "day": d, "hm": idx[i].strftime("%H:%M"), "mins": m, "side": side,
            "entry": round(entry, 2), "tag": tag, "level": round(float(level), 2),
            "walls": ",".join(wall_any) if wall_any else "",
            "t15_win": bool(ok),
            "pts": round(float(pts), 2) if pts is not None else None,
            "at_wall": at_wall, "at_or": at_or, "at_swing": at_swing, "at_pd": at_pd,
            "role_ok": bool(role_ok and at_wall),
            "held": held, "htf_with": bool(htf_with), "desk_ge3": desk_ge3,
            "atr_hi": a >= 10.0, "atr_12": a >= 12.0, "atr_14": a >= 14.0,
            "streak4": st >= 4, "streak5": st >= 5, "ctrl": bool(ctrl),
            "ema_with": bool(ema_with), "vwap_with": bool(vwap_with),
            "am": am, "skip_open": skip_open, "prime": prime,
            "atr": round(a, 2),
        })

    print(f"cands={len(cands)} at_wall={sum(1 for r in cands if r['at_wall'])}", flush=True)

    def eval_one(name, hit):
        one = one_per_day(hit)
        p, nn = prec(one)
        tr = [r for r in one if r["day"] < mid]
        oo = [r for r in one if r["day"] >= mid]
        pt, nt = prec(tr)
        po, no = prec(oo)
        size = max(1, n_days // 5)
        fprecs, folds = [], []
        for fi in range(5):
            lo = days_sorted[fi * size]
            hi_d = days_sorted[min(n_days - 1, (fi + 1) * size - 1 if fi < 4 else n_days - 1)]
            fr = [r for r in one if lo <= r["day"] <= hi_d]
            fp, fn = prec(fr)
            folds.append({"fold": fi + 1, "n": fn, "prec": fp, "lo": lo, "hi": hi_d})
            if fn >= 4 and fp is not None:
                fprecs.append(fp)
        fmin = min(fprecs) if fprecs else None
        ship = (
            nn >= 25 and (p or 0) >= 70 and (pt or 0) >= 65 and (po or 0) >= 65
            and (fmin or 0) >= 65
        )
        soft = (
            nn >= 20 and (p or 0) >= 72 and (pt or 0) >= 65 and (po or 0) >= 68
            and (fmin or 0) >= 60
        )
        return {
            "name": name, "n": nn, "prec": p, "train": pt, "oos": po,
            "fold_min": fmin, "fold_avg": round(float(np.mean(fprecs)), 2) if fprecs else None,
            "folds": folds, "ship": "SHIP" if ship else ("SOFT" if soft else "HOLD"),
            "samples": [
                {k: r[k] for k in ("day", "hm", "side", "entry", "tag", "walls", "t15_win", "atr")}
                for r in one[:10]
            ],
            "last5": [
                {k: r[k] for k in ("day", "hm", "side", "entry", "tag", "walls", "t15_win", "atr", "pts")}
                for r in one if r["day"] in last5
            ],
        }

    gates = [
        ("HHLL raw (no wall)", lambda r: True),
        ("at ANY wall", lambda r: r["at_wall"]),
        ("at OR wall", lambda r: r["at_or"]),
        ("at swing/L15 wall", lambda r: r["at_swing"]),
        ("at PDH/PDL", lambda r: r["at_pd"]),
        ("role-matched wall", lambda r: r["role_ok"]),
        ("wall + htf", lambda r: r["at_wall"] and r["htf_with"]),
        ("wall + htf + atr12 + streak4", lambda r: r["at_wall"] and r["htf_with"] and r["atr_12"] and r["streak4"]),
        ("wall + htf + atr14 + streak4", lambda r: r["at_wall"] and r["htf_with"] and r["atr_14"] and r["streak4"]),
        ("wall + SHIP stack", lambda r: r["at_wall"] and r["htf_with"] and r["atr_14"] and r["streak4"] and r["ema_with"] and r["am"]),
        ("role wall + SHIP stack", lambda r: r["role_ok"] and r["htf_with"] and r["atr_14"] and r["streak4"] and r["ema_with"] and r["am"]),
        ("OR wall + SHIP stack", lambda r: r["at_or"] and r["htf_with"] and r["atr_14"] and r["streak4"] and r["ema_with"] and r["am"]),
        ("swing wall + SHIP stack", lambda r: r["at_swing"] and r["htf_with"] and r["atr_14"] and r["streak4"] and r["ema_with"] and r["am"]),
        ("wall + held + htf + atr12 + streak4", lambda r: r["at_wall"] and r["held"] and r["htf_with"] and r["atr_12"] and r["streak4"]),
        ("wall + htf + atr14 + streak4 + am", lambda r: r["at_wall"] and r["htf_with"] and r["atr_14"] and r["streak4"] and r["am"]),
        ("role wall + htf + atr14 + streak4 + am", lambda r: r["role_ok"] and r["htf_with"] and r["atr_14"] and r["streak4"] and r["am"]),
        ("OR+swing + htf + atr12 + streak4", lambda r: r["at_or"] and r["at_swing"] and r["htf_with"] and r["atr_12"] and r["streak4"]),
        ("OR+swing + SHIP stack", lambda r: r["at_or"] and r["at_swing"] and r["htf_with"] and r["atr_14"] and r["streak4"] and r["ema_with"] and r["am"]),
        ("wall + desk3 + htf + atr14 + streak4", lambda r: r["at_wall"] and r["desk_ge3"] and r["htf_with"] and r["atr_14"] and r["streak4"]),
        ("role wall + held + htf + atr12 + streak4", lambda r: r["role_ok"] and r["held"] and r["htf_with"] and r["atr_12"] and r["streak4"]),
        ("wall + htf + atr12 + streak4 + ctrl", lambda r: r["at_wall"] and r["htf_with"] and r["atr_12"] and r["streak4"] and r["ctrl"]),
        ("wall + htf + atr12 + streak4 + am", lambda r: r["at_wall"] and r["htf_with"] and r["atr_12"] and r["streak4"] and r["am"]),
    ]

    hunt = []
    for name, pred in gates:
        st = eval_one(name, [r for r in cands if pred(r)])
        hunt.append(st)
        print(
            f"  {st['ship']} {name}: n={st['n']} T15={st['prec']}% "
            f"tr={st['train']}% oos={st['oos']}% fmin={st['fold_min']}",
            flush=True,
        )

    hunt = sorted(hunt, key=lambda x: (
        0 if x["ship"] == "SHIP" else (1 if x["ship"] == "SOFT" else 2),
        -(x["fold_min"] or 0), -(x["prec"] or 0), -x["n"],
    ))
    ships = [h for h in hunt if h["ship"] == "SHIP"]
    softs = [h for h in hunt if h["ship"] == "SOFT"]
    pick = ships[0] if ships else (softs[0] if softs else hunt[0])

    # last 5 days: show ALL wall HHLL + best-gate hits
    wall_last5 = one_per_day([r for r in cands if r["at_wall"] and r["day"] in last5])
    best_pred = dict(gates).get(pick["name"], lambda r: r["at_wall"])
    # recover pred by name
    pred_map = {n: p for n, p in gates}
    best_pred = pred_map[pick["name"]]
    pick_last5 = one_per_day([r for r in cands if best_pred(r) and r["day"] in last5])

    lines = [
        "# NIFTY 1m — HHLL confirm **at swing / OR wall**",
        "",
        "> Entry = HL (BUY) / LH (SELL) only when the pivot or price sits on",
        "> **OR15/OR30 · swing cluster · PDH/PDL · 15m L3**. Score = EMA34 trail T15.",
        "",
        f"Window **{day_lo}→{day_hi}** ({n_days}d). SHIP = n≥25 · T15≥70 · train/oos≥65 · fold_min≥65.",
        f"SHIP **{len(ships)}** · SOFT **{len(softs)}**",
        "",
        "| Gate | Ship | n | T15% | Train | OOS | fold_min | fold_avg |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for hrow in hunt:
        lines.append(
            f"| `{hrow['name']}` | **{hrow['ship']}** | {hrow['n']} | **{hrow['prec']}** | "
            f"{hrow['train']} | {hrow['oos']} | {hrow['fold_min']} | {hrow['fold_avg']} |"
        )

    lines += ["", "## Best", ""]
    lines += [
        f"**`{pick['name']}`** · **{pick['ship']}**",
        f"- T15 **{pick['prec']}%** · fold_min **{pick['fold_min']}** · n={pick['n']}",
        f"- train {pick['train']}% · oos {pick['oos']}%",
        "",
        "### Folds",
        "",
        "| Fold | From | To | n | T15 |",
        "|---|---|---|---:|---:|",
    ]
    for f in pick["folds"]:
        lines.append(f"| {f['fold']} | {f['lo']} | {f['hi']} | {f['n']} | {f['prec']} |")

    lines += [
        "",
        "## Last 5 sessions — wall HHLL (1/day)",
        "",
        "| Day | HM | Side | Tag | Entry | Walls | ATR | T15 | pts |",
        "|---|---|---|---|---:|---|---:|---|---:|",
    ]
    for r in sorted(wall_last5, key=lambda x: x["day"]):
        lines.append(
            f"| {r['day']} | {r['hm']} | **{r['side']}** | {r['tag']} | {r['entry']} | "
            f"`{r['walls']}` | {r['atr']} | {'✓' if r['t15_win'] else '✗'} | {r['pts']} |"
        )
    if not wall_last5:
        lines.append("| — | — | — | — | — | no wall HHLL | — | — | — |")

    lines += [
        "",
        f"## Last 5 sessions — best gate `{pick['name']}`",
        "",
        "| Day | HM | Side | Tag | Entry | Walls | ATR | T15 | pts |",
        "|---|---|---|---|---:|---|---:|---|---:|",
    ]
    for r in sorted(pick_last5, key=lambda x: x["day"]):
        lines.append(
            f"| {r['day']} | {r['hm']} | **{r['side']}** | {r['tag']} | {r['entry']} | "
            f"`{r['walls']}` | {r['atr']} | {'✓' if r['t15_win'] else '✗'} | {r['pts']} |"
        )
    if not pick_last5:
        lines.append("| — | — | — | — | — | none fired | — | — | — |")

    lines += [
        "",
        "## How to use",
        "",
        "```",
        "WALL  : OR15/30 · swing cluster · PDH/PDL · 15m L3 (within 0.45×ATR)",
        "STRUCT: HL in up bias → BUY · LH in down bias → SELL",
        "QUAL  : HTF with + ATR≥14 + streak≥4 + EMA with + AM  (or best gate above)",
        "EXIT  : EMA34 trail · T15",
        "```",
        "",
        f"_Generated in {time.time()-t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({
        "pick": pick, "ships": ships[:8], "softs": softs[:8],
        "hunt": [{k: h[k] for k in ("name", "ship", "n", "prec", "train", "oos", "fold_min")} for h in hunt],
        "wall_last5": wall_last5, "pick_last5": pick_last5,
        "window": [day_lo, day_hi],
    }, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    print(f"PICK: {pick['ship']} {pick['name']} T15={pick['prec']}% fmin={pick['fold_min']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
