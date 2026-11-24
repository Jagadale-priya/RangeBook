"""RESEARCH ONLY — HH/HL/LH/LL accurate entry (lean v2).

Faster causal structure hunt:
  L=3 swings → label HH/HL/LH/LL → bias
  Entries:
    1) HL/LH confirm (at confirmation bar)
    2) HL/LH retest (leave→touch→control)
    3) HH/LL break→retest
    4) HH/LL confirm (momentum)

Score T15 only on candidates; quality filters after.

  python -u prod_live/tests/builders/_diag_scalp_hhll_accurate_entry_v2.py
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
REPORT = OUT / "NIFTY_1M_HHLL_ACCURATE_ENTRY.md"
REPORT_JSON = OUT / "NIFTY_1M_HHLL_ACCURATE_ENTRY.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 120
LOOKBACK_CAL = 240
T15 = 15.0
L = 3
ZONE = 0.40
LEAVE = 0.35
RETEST_MAX = 40


def pack(rows, key, mid):
    if not rows:
        return {"n": 0, "prec": None, "train_n": 0, "train_prec": None,
                "oos_n": 0, "oos_prec": None, "avg_pts": None, "avg_mfe": None}
    tr = [r for r in rows if r["day"] < mid]
    oo = [r for r in rows if r["day"] >= mid]

    def _p(rs):
        if not rs:
            return None, 0
        return round(100.0 * sum(1 for x in rs if x.get(key)) / len(rs), 2), len(rs)

    p, n = _p(rows)
    pt, nt = _p(tr)
    po, no = _p(oo)
    pts = [r["pts"] for r in rows if r.get("pts") is not None]
    mfes = [r["mfe"] for r in rows if r.get("mfe") is not None]
    return {
        "n": n, "prec": p, "train_n": nt, "train_prec": pt,
        "oos_n": no, "oos_prec": po,
        "avg_pts": round(float(np.mean(pts)), 2) if pts else None,
        "avg_mfe": round(float(np.mean(mfes)), 2) if mfes else None,
    }


def one_per_day(rows):
    byd = {}
    for r in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        if r["day"] not in byd:
            byd[r["day"]] = r
    return list(byd.values())


def verdict(st, min_n=18):
    if not st or st["n"] < min_n:
        return "THIN"
    if (st["prec"] or 0) >= 85 and (st["oos_prec"] or 0) >= 80 and (st["train_prec"] or 0) >= 80:
        return "HIGH_85"
    if (st["prec"] or 0) >= 75 and (st["oos_prec"] or 0) >= 70 and (st["train_prec"] or 0) >= 70:
        return "HIGH_75"
    if (st["prec"] or 0) >= 70 and (st["oos_prec"] or 0) >= 65 and (st["train_prec"] or 0) >= 65:
        return "OK_70"
    if (st["prec"] or 0) >= 65 and (st["oos_prec"] or 0) >= 60:
        return "OK_65"
    return "WEAK"


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("HHLL v2 lean accurate entry", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df = raw.copy()
    # light prep — skip textbook detect (slow / unused here)
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
    print(f"window {day_lo}→{day_hi} n={n_days} OOS≥{mid_day} bars={len(df)}", flush=True)

    print("HTF15…", flush=True)
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

    # fractal pivots (need L bars right) — confirm at i+L
    print("swings…", flush=True)
    is_sh = np.zeros(n, dtype=bool)
    is_sl = np.zeros(n, dtype=bool)
    for i in range(L, n - L):
        if h[i] >= np.max(h[i - L : i + L + 1]) - 1e-9:
            is_sh[i] = True
        if l[i] <= np.min(l[i - L : i + L + 1]) + 1e-9:
            is_sl[i] = True

    # raw entries before scoring
    raw_entries: List[dict] = []

    last_sh_px = None
    last_sl_px = None
    last_hh = last_hl = last_lh = last_ll = None  # (conf_i, pivot_i, px)
    bias = None
    tag_n = defaultdict(int)
    bias_at = [None] * n

    # pending retests: list of dicts armed after confirm/break
    pending: List[dict] = []
    used_break = set()

    def arm_retest(kind, side, level, arm_i, logic, tag):
        pending.append({
            "kind": kind, "side": side, "level": float(level),
            "arm_i": arm_i, "logic": logic, "tag": tag,
            "away": False, "day": day[arm_i],
        })

    def upd_bias():
        nonlocal bias
        if last_hh and last_hl and (not last_lh or last_hh[0] > last_lh[0]) and (not last_ll or last_hl[0] > last_ll[0]):
            bias = "up"
        elif last_lh and last_ll and (not last_hh or last_lh[0] > last_hh[0]) and (not last_hl or last_ll[0] > last_hl[0]):
            bias = "down"

    print("walk structure…", flush=True)
    for i in range(n):
        d = day[i]
        new_high_tag = None
        new_low_tag = None
        new_high_px = None
        new_low_px = None

        # confirm pivots
        if i >= L and is_sh[i - L]:
            j = i - L
            px = float(h[j])
            tag = None
            if last_sh_px is not None:
                tag = "HH" if px > last_sh_px else "LH"
            last_sh_px = px
            if tag:
                tag_n[tag] += 1
                new_high_tag, new_high_px = tag, px
                if tag == "HH":
                    last_hh = (i, j, px)
                else:
                    last_lh = (i, j, px)
                    arm_retest("LH", "SELL", px, i, "LH_retest", tag)

        if i >= L and is_sl[i - L]:
            j = i - L
            px = float(l[j])
            tag = None
            if last_sl_px is not None:
                tag = "HL" if px > last_sl_px else "LL"
            last_sl_px = px
            if tag:
                tag_n[tag] += 1
                new_low_tag, new_low_px = tag, px
                if tag == "HL":
                    last_hl = (i, j, px)
                    arm_retest("HL", "BUY", px, i, "HL_retest", tag)
                else:
                    last_ll = (i, j, px)

        upd_bias()
        bias_at[i] = bias

        # confirm entries only with matching structure bias
        if new_high_tag and MINS_LO <= mins[i] <= MINS_HI and d in keep:
            if new_high_tag == "HH" and bias == "up":
                raw_entries.append({"i": i, "side": "BUY", "logic": "HH_confirm", "tag": new_high_tag, "level": new_high_px, "bias": bias})
            elif new_high_tag == "LH" and bias == "down":
                raw_entries.append({"i": i, "side": "SELL", "logic": "LH_confirm", "tag": new_high_tag, "level": new_high_px, "bias": bias})
        if new_low_tag and MINS_LO <= mins[i] <= MINS_HI and d in keep:
            if new_low_tag == "HL" and bias == "up":
                raw_entries.append({"i": i, "side": "BUY", "logic": "HL_confirm", "tag": new_low_tag, "level": new_low_px, "bias": bias})
            elif new_low_tag == "LL" and bias == "down":
                raw_entries.append({"i": i, "side": "SELL", "logic": "LL_confirm", "tag": new_low_tag, "level": new_low_px, "bias": bias})

        # HH/LL break detection (first cross)
        if last_hh and d in keep and MINS_LO <= mins[i] <= MINS_HI and i > 0 and day[i - 1] == d:
            lvl = last_hh[2]
            key = (d, "BUY", round(lvl, 2))
            if key not in used_break and c[i - 1] <= lvl < c[i]:
                used_break.add(key)
                arm_retest("HH_brk", "BUY", lvl, i, "HH_break_retest", "HH")
        if last_ll and d in keep and MINS_LO <= mins[i] <= MINS_HI and i > 0 and day[i - 1] == d:
            lvl = last_ll[2]
            key = (d, "SELL", round(lvl, 2))
            if key not in used_break and c[i - 1] >= lvl > c[i]:
                used_break.add(key)
                arm_retest("LL_brk", "SELL", lvl, i, "LL_break_retest", "LL")

        # process pending retests at this bar
        if not pending:
            continue
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        band = ZONE * a
        leave = LEAVE * a
        still = []
        for p in pending:
            if day[i] != p["day"] or i - p["arm_i"] > RETEST_MAX:
                continue  # expire
            if not (MINS_LO <= mins[i] <= MINS_HI):
                still.append(p)
                continue
            lvl = p["level"]
            side = p["side"]
            if side == "BUY":
                if l[i] > lvl + leave:
                    p["away"] = True
                if p["away"] and l[i] <= lvl + band and c[i] >= lvl:
                    rng = max(h[i] - l[i], 0.05)
                    loc = (c[i] - l[i]) / rng
                    if c[i] > o[i] and loc >= 0.55:
                        raw_entries.append({
                            "i": i, "side": "BUY", "logic": p["logic"],
                            "tag": p["tag"], "level": lvl, "bias": bias_at[i],
                        })
                        continue  # filled — drop
            else:
                if h[i] < lvl - leave:
                    p["away"] = True
                if p["away"] and h[i] >= lvl - band and c[i] <= lvl:
                    rng = max(h[i] - l[i], 0.05)
                    loc = (c[i] - l[i]) / rng
                    if c[i] < o[i] and loc <= 0.45:
                        raw_entries.append({
                            "i": i, "side": "SELL", "logic": p["logic"],
                            "tag": p["tag"], "level": lvl, "bias": bias_at[i],
                        })
                        continue
            still.append(p)
        pending = still

    print(f"tags {dict(tag_n)} raw_entries={len(raw_entries)}", flush=True)

    # score
    print("scoring…", flush=True)
    cands = []
    for k, e in enumerate(raw_entries):
        if k and k % 2000 == 0:
            print(f"  scored {k}/{len(raw_entries)}", flush=True)
        i = int(e["i"])
        side = e["side"]
        entry = float(c[i])
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        vw = float(vwap[i]) if np.isfinite(vwap[i]) else entry
        e9, e20, e50 = float(ema9[i]), float(ema20[i]), float(ema50[i])
        e34 = float(ema34[i]) if np.isfinite(ema34[i]) else entry
        vwap_with = (side == "BUY" and entry >= vw) or (side == "SELL" and entry <= vw)
        ema_with = (side == "BUY" and e9 >= e20) or (side == "SELL" and e9 <= e20)
        ema50_with = (side == "BUY" and entry >= e50) or (side == "SELL" and entry <= e50)
        di_ok = (side == "BUY" and pdi[i] > mdi[i]) or (side == "SELL" and mdi[i] > pdi[i])
        gate34 = (side == "BUY" and entry >= e34) or (side == "SELL" and entry <= e34)
        held = bool(di_ok and gate34 and vwap_with)
        htf = htf_bias_lookup(bias15, idx[i])
        htf_with = (side == "BUY" and htf == "up") or (side == "SELL" and htf == "down")
        rng = max(h[i] - l[i], 0.05)
        loc = (c[i] - l[i]) / rng
        ctrl = (side == "BUY" and loc >= 0.65 and c[i] > o[i]) or (side == "SELL" and loc <= 0.35 and c[i] < o[i])
        # streak
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
        so = [k for k in range(max(0, i - 400), i) if day[k] == day[i]]
        if so:
            shi, slo = float(np.max(h[so])), float(np.min(l[so]))
        else:
            shi = slo = entry
        not_extreme = not (
            (side == "BUY" and (shi - entry) <= max(8.0, a))
            or (side == "SELL" and (entry - slo) <= max(8.0, a))
        )
        ok, reason, exit_px, j, pts = scalper.path_ma_trail(h, l, c, ema34, i, side, T15)
        mfe = 0.0
        for j2 in range(i + 1, min(n, i + 31)):
            if day[j2] != day[i]:
                break
            if side == "BUY":
                mfe = max(mfe, float(h[j2]) - entry)
            else:
                mfe = max(mfe, entry - float(l[j2]))
        cands.append({
            "day": day[i], "hm": idx[i].strftime("%H:%M"), "mins": int(mins[i]),
            "side": side, "entry": round(entry, 2),
            "logic": e["logic"], "tag": e["tag"], "level": round(float(e["level"]), 2),
            "t15_win": bool(ok),
            "pts": round(float(pts), 2) if pts is not None else None,
            "mfe": round(mfe, 2),
            "atr": round(a, 2),
            "atr_hi": a >= 10.0,
            "atr_12": a >= 12.0,
            "held": held,
            "htf_with": bool(htf_with),
            "vwap_with": bool(vwap_with),
            "ema_with": bool(ema_with),
            "desk_ge3": sum([vwap_with, ema_with, ema50_with, gate34]) >= 3,
            "ctrl": bool(ctrl),
            "not_extreme": bool(not_extreme),
            "streak4": st >= 4,
            "streak6": st >= 6,
            "bias_up": e.get("bias") == "up",
            "bias_dn": e.get("bias") == "down",
            "bias_with": (e.get("bias") == "up" and side == "BUY") or (e.get("bias") == "down" and side == "SELL"),
        })

    print(f"scored {len(cands)}", flush=True)
    by_logic = defaultdict(int)
    for r in cands:
        by_logic[r["logic"]] += 1
    print("by logic:", dict(by_logic), flush=True)

    books = []

    def add(name, pred, pool=None):
        src = pool if pool is not None else cands
        hit = [r for r in src if pred(r)]
        one = one_per_day(hit)
        st1 = pack(one, "t15_win", mid_day)
        v = verdict(st1)
        books.append({"name": name, "verdict": v, "one": st1, "samples": one[:10]})
        print(f"  {name}: n={st1['n']} T15={st1['prec']}% tr={st1['train_prec']}% oos={st1['oos_prec']}% → {v}", flush=True)

    print("\n--- baselines ---", flush=True)
    for logic in sorted(by_logic):
        add(logic, lambda r, logic=logic: r["logic"] == logic)

    print("\n--- quality ---", flush=True)
    for logic in sorted(by_logic):
        pool = [r for r in cands if r["logic"] == logic]
        add(f"{logic}+bias", lambda r: r["bias_with"], pool)
        add(f"{logic}+htf", lambda r: r["htf_with"], pool)
        add(f"{logic}+held+htf", lambda r: r["held"] and r["htf_with"], pool)
        add(f"{logic}+held+htf+atr10", lambda r: r["held"] and r["htf_with"] and r["atr_hi"], pool)
        add(f"{logic}+held+htf+atr12", lambda r: r["held"] and r["htf_with"] and r["atr_12"], pool)
        add(f"{logic}+bias+htf+atr10", lambda r: r["bias_with"] and r["htf_with"] and r["atr_hi"], pool)
        add(f"{logic}+held+htf+atr10+ctrl", lambda r: r["held"] and r["htf_with"] and r["atr_hi"] and r["ctrl"], pool)
        add(f"{logic}+held+htf+atr10+!ext", lambda r: r["held"] and r["htf_with"] and r["atr_hi"] and r["not_extreme"], pool)

    print("\n--- families ---", flush=True)
    add("HL/LH_confirm+held+htf+atr10", lambda r: r["logic"] in ("HL_confirm", "LH_confirm") and r["held"] and r["htf_with"] and r["atr_hi"])
    add("HH/LL_confirm+held+htf+atr10", lambda r: r["logic"] in ("HH_confirm", "LL_confirm") and r["held"] and r["htf_with"] and r["atr_hi"])
    add("HL/LH_retest+held+htf+atr10", lambda r: r["logic"] in ("HL_retest", "LH_retest") and r["held"] and r["htf_with"] and r["atr_hi"])
    add("HH/LL_break_retest+held+htf+atr10", lambda r: r["logic"] in ("HH_break_retest", "LL_break_retest") and r["held"] and r["htf_with"] and r["atr_hi"])
    add("ALL_retest+held+htf+atr10", lambda r: r["logic"].endswith("retest") and r["held"] and r["htf_with"] and r["atr_hi"])
    add("ALL_confirm+held+htf+atr10", lambda r: r["logic"].endswith("confirm") and r["held"] and r["htf_with"] and r["atr_hi"])

    print("\n--- hunt ---", flush=True)
    feat = ["held", "htf_with", "atr_hi", "atr_12", "bias_with", "ctrl", "not_extreme", "desk_ge3", "streak4", "ema_with"]
    pools = {
        "HL_LH_retest": [r for r in cands if r["logic"] in ("HL_retest", "LH_retest")],
        "HH_LL_break": [r for r in cands if r["logic"] in ("HH_break_retest", "LL_break_retest")],
        "HL_LH_confirm": [r for r in cands if r["logic"] in ("HL_confirm", "LH_confirm")],
        "HH_LL_confirm": [r for r in cands if r["logic"] in ("HH_confirm", "LL_confirm")],
    }
    hunt = []
    for pname, pool in pools.items():
        for k in (2, 3, 4):
            for combo in combinations(feat, k):
                if not any(x in combo for x in ("held", "htf_with", "bias_with", "atr_hi")):
                    continue
                hit = [r for r in pool if all(r.get(f) for f in combo)]
                one = one_per_day(hit)
                if len(one) < 15:
                    continue
                st1 = pack(one, "t15_win", mid_day)
                if (st1["prec"] or 0) < 65:
                    continue
                v = verdict(st1)
                hunt.append({"pool": pname, "combo": "+".join(combo), "verdict": v, "one": st1})
                if (st1["prec"] or 0) >= 70:
                    add(f"HUNT:{pname}|{'+'.join(combo)}", lambda r, combo=combo: all(r.get(f) for f in combo), pool)

    hunt.sort(key=lambda x: (-(x["one"]["prec"] or 0), -x["one"]["n"]))
    for hrow in hunt[:20]:
        o1 = hrow["one"]
        print(f"  [{hrow['verdict']}] {hrow['pool']}|{hrow['combo']}: n={o1['n']} T15={o1['prec']}% oos={o1['oos_prec']}%", flush=True)

    ranked = sorted([b for b in books if b["one"]["n"] >= 15], key=lambda b: (-(b["one"]["prec"] or 0), -b["one"]["n"]))
    best75 = next((b for b in ranked if b["verdict"] in ("HIGH_75", "HIGH_85")), None)
    best70 = next((b for b in ranked if (b["one"]["prec"] or 0) >= 70 and (b["one"]["oos_prec"] or 0) >= 65 and (b["one"]["train_prec"] or 0) >= 65), None)
    pick = best75 or best70 or (ranked[0] if ranked else None)

    # lift on retest family
    pool = [r for r in cands if "retest" in r["logic"]]
    win = [r for r in pool if r["t15_win"]]
    lose = [r for r in pool if not r["t15_win"]]
    lift = []
    for k in feat:
        if not win or not lose:
            continue
        pw = 100.0 * sum(1 for r in win if r.get(k)) / len(win)
        pl = 100.0 * sum(1 for r in lose if r.get(k)) / len(lose)
        lift.append({"mark": k, "win_pct": round(pw, 1), "lose_pct": round(pl, 1), "lift_pp": round(pw - pl, 1)})
    lift.sort(key=lambda x: -x["lift_pp"])

    lines = [
        "# NIFTY 1m — **HH / HL / LH / LL** accurate entry",
        "",
        "> Structure from highs & lows only. Find accurate entry logic.",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS **{mid_day}**. Candidates **{len(cands)}**.",
        "",
        "## Structure",
        "",
        "```",
        "Swing L=3 → label vs prior:",
        "  high > prior high = HH   high < prior high = LH",
        "  low  > prior low  = HL   low  < prior low  = LL",
        "Bias: HH+HL = UP · LH+LL = DOWN",
        "```",
        "",
        "| Tag | n |",
        "|---|---:|",
    ]
    for k, v in sorted(tag_n.items()):
        lines.append(f"| `{k}` | {v} |")
    lines += ["", "| Logic | n |", "|---|---:|"]
    for k, v in sorted(by_logic.items()):
        lines.append(f"| `{k}` | {v} |")

    lines += [
        "",
        "## Lift on retest family",
        "",
        "| Mark | % Win | % Lose | Lift |",
        "|---|---:|---:|---:|",
    ]
    for lr in lift:
        lines.append(f"| `{lr['mark']}` | {lr['win_pct']} | {lr['lose_pct']} | {lr['lift_pp']} |")

    lines += [
        "",
        "## Gates (1/day T15)",
        "",
        "| Gate | Verdict | n | T15% | Train | OOS | avg MFE | avg pts |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for b in ranked[:60]:
        o1 = b["one"]
        lines.append(
            f"| `{b['name']}` | **{b['verdict']}** | {o1['n']} | **{o1['prec']}** | "
            f"{o1['train_prec']} | {o1['oos_prec']} | {o1['avg_mfe']} | {o1['avg_pts']} |"
        )

    lines += ["", "## Hunt ≥70% stable", ""]
    good = [h for h in hunt if (h["one"]["prec"] or 0) >= 70 and (h["one"]["oos_prec"] or 0) >= 65 and (h["one"]["train_prec"] or 0) >= 65]
    if not good:
        lines.append("_None._")
        near = [h for h in hunt if (h["one"]["prec"] or 0) >= 68][:12]
        if near:
            lines += ["", "Near:", "", "| Pool | Combo | n | T15 | Train | OOS |", "|---|---|---:|---:|---:|---:|"]
            for hrow in near:
                o1 = hrow["one"]
                lines.append(f"| `{hrow['pool']}` | `{hrow['combo']}` | {o1['n']} | **{o1['prec']}** | {o1['train_prec']} | {o1['oos_prec']} |")
    else:
        lines += ["| Pool | Combo | Verdict | n | T15 | Train | OOS |", "|---|---|---|---:|---:|---:|---:|"]
        for hrow in good[:20]:
            o1 = hrow["one"]
            lines.append(
                f"| `{hrow['pool']}` | `{hrow['combo']}` | **{hrow['verdict']}** | "
                f"{o1['n']} | **{o1['prec']}** | {o1['train_prec']} | {o1['oos_prec']} |"
            )

    lines += ["", "## Best logic", ""]
    if pick:
        o1 = pick["one"]
        lines += [
            f"**`{pick['name']}`** · **{pick['verdict']}**",
            f"- T15 **{o1['prec']}%** · TRAIN **{o1['train_prec']}%** · OOS **{o1['oos_prec']}%** · n={o1['n']}",
            "",
            "```",
            "1) Mark swing H/L (L=3)",
            "2) Label HH/HL/LH/LL vs prior swing",
            "3) Bias = HH+HL (buy) or LH+LL (sell)",
            "4) Enter on best gate (confirm or retest — see name)",
            "5) Filter: held + HTF15 + ATR≥10",
            "6) Exit: EMA34 trail · T15",
            "```",
            "",
            "| Day | HM | Side | Entry | logic | tag | ATR | T15 | MFE |",
            "|---|---|---|---:|---|---|---:|---|---:|",
        ]
        for x in pick["samples"]:
            lines.append(
                f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | "
                f"{x['logic']} | {x['tag']} | {x['atr']} | {x['t15_win']} | {x['mfe']} |"
            )

    lines += ["", f"_Generated in {time.time()-t0:.1f}s._", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({
        "tags": dict(tag_n), "logics": dict(by_logic), "lift": lift,
        "books": [{"name": b["name"], "verdict": b["verdict"], "one": b["one"]} for b in ranked[:60]],
        "hunt": hunt[:30],
        "best": {"name": pick["name"], "verdict": pick["verdict"], "one": pick["one"]} if pick else None,
    }, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    if pick:
        print(f"BEST: {pick['name']} → {pick['verdict']} T15={pick['one']['prec']}%", flush=True)
    print(f"done in {time.time()-t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
