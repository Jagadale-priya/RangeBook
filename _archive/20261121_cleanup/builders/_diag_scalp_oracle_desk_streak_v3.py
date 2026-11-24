"""RESEARCH ONLY — Improve Oracle T15 × Desk × streak accuracy (v3 deep).

Prior ceiling ~58–63% T15. This pass adds:
  - Entry modes: streak-hit / confirm+1 / pullback-resume
  - Quality: HTF15, AD, DI, ctrl, close_strong, not_extreme, ATR
  - Extension: distance from EMA34 / VWAP (avoid chase)
  - Session buckets (skip open chaos / lunch)
  - Desk core only (VWAP+EMA+EMA50+BBmid; fib dropped — negative lift)

Metric = EMA34 trail · T15 (scalper Oracle exit). 1/day + walk-forward.

  python -u prod_live/tests/builders/_diag_scalp_oracle_desk_streak_v3.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
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
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators  # noqa: E402
from _diag_scalp_ad_sr_entry_1m import add_ad_obv_proxy  # noqa: E402
from _diag_scalp_pa_bos_choch_fvg import (  # noqa: E402
    to_15m,
    structure_events,
    build_htf_bias,
    htf_bias_lookup,
)

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_1m as scalper  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ORACLE_DESK_STREAK_V3.md"
REPORT_JSON = OUT / "NIFTY_1M_ORACLE_DESK_STREAK_V3.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 120
LOOKBACK_CAL = 240
T15 = 15.0
ZONE_ATR = 0.45
EXT_ATR_MAX = 1.8  # too far from EMA34 = chase
PB_MAX = 3  # max opposite bars in pullback


def pack(rows, key, mid):
    if not rows:
        return {
            "n": 0, "prec": None, "train_n": 0, "train_prec": None,
            "oos_n": 0, "oos_prec": None, "avg_pts": None,
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
    pts = [r["pts"] for r in rows if r.get("pts") is not None]
    return {
        "n": n, "prec": p, "train_n": nt, "train_prec": pt,
        "oos_n": no, "oos_prec": po,
        "avg_pts": round(float(np.mean(pts)), 2) if pts else None,
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


def color_side(o, c, i):
    if c[i] > o[i]:
        return "BUY"
    if c[i] < o[i]:
        return "SELL"
    return None


def streak_len_at(o, c, day, i, side):
    if side == "BUY" and not (c[i] > o[i]):
        return 0
    if side == "SELL" and not (c[i] < o[i]):
        return 0
    s = i
    while s - 1 >= 0 and day[s - 1] == day[i]:
        if side == "BUY" and c[s - 1] > o[s - 1]:
            s -= 1
        elif side == "SELL" and c[s - 1] < o[s - 1]:
            s -= 1
        else:
            break
    return i - s + 1


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("v3: Oracle×Desk×streak accuracy IMPROVE (HTF/AD/ext/session/pullback)", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    df = add_ad_obv_proxy(df)

    close = df["Close"].astype(float)
    df["ema9"] = close.ewm(span=9, adjust=False).mean()
    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()
    midb = close.rolling(20, min_periods=20).mean()
    std = close.rolling(20, min_periods=20).std(ddof=0)
    df["bb_mid"] = midb
    df["bb_up"] = midb + 2 * std
    df["bb_lo"] = midb - 2 * std

    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    mid_day = days_sorted[n_days // 2]
    df = df[[str(ts.date()) in keep for ts in df.index]]
    print(f"window {day_lo}→{day_hi} n={n_days} OOS≥{mid_day}", flush=True)

    df15 = to_15m(df)
    bias15 = build_htf_bias(df15, structure_events(df15))

    # textbook event bars (optional confluence)
    events = scalper._collect_events(df, day_lo, day_hi)
    scalper._enrich(events, df)
    evt_i = set()
    for e in events:
        ii = int(e.get("full_i") or e.get("i") or -1)
        if ii >= 0:
            evt_i.add(ii)
    print(f"textbook events: {len(events)} idxs={len(evt_i)}", flush=True)

    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    atr = df["atr14"].astype(float).values
    vwap = df["vwap"].astype(float).values if "vwap" in df.columns else c.copy()
    ema9 = df["ema9"].astype(float).values
    ema20 = df["ema20"].astype(float).values
    ema50 = df["ema50"].astype(float).values
    bb_mid = df["bb_mid"].astype(float).values
    pdi = df["plus_di"].astype(float).values
    mdi = df["minus_di"].astype(float).values
    ad_r = df["ad_rising"].astype(bool).values
    ad_f = df["ad_falling"].astype(bool).values
    rsi = df["rsi_14"].astype(float).values if "rsi_14" in df.columns else np.full(len(c), 50.0)
    day = np.array([str(ts.date()) for ts in df.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df.index])
    idx = df.index
    n = len(c)
    by_day: Dict[str, np.ndarray] = {}
    for d in keep:
        by_day[d] = np.where(day == d)[0]

    def feats(i: int, side: str, entry: float) -> Dict[str, Any]:
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        d = day[i]
        rng = max(float(h[i]) - float(l[i]), 0.05)
        loc = (float(c[i]) - float(l[i])) / rng
        body = abs(float(c[i]) - float(o[i]))
        green = c[i] > o[i]
        red = c[i] < o[i]

        vw = float(vwap[i]) if np.isfinite(vwap[i]) else entry
        e9, e20, e50 = float(ema9[i]), float(ema20[i]), float(ema50[i])
        bm = float(bb_mid[i]) if np.isfinite(bb_mid[i]) else entry
        e34 = float(ema34[i]) if np.isfinite(ema34[i]) else entry

        vwap_with = (side == "BUY" and entry >= vw) or (side == "SELL" and entry <= vw)
        ema_with = (side == "BUY" and np.isfinite(e9) and np.isfinite(e20) and e9 >= e20) or (
            side == "SELL" and np.isfinite(e9) and np.isfinite(e20) and e9 <= e20
        )
        ema50_with = (side == "BUY" and np.isfinite(e50) and entry >= e50) or (
            side == "SELL" and np.isfinite(e50) and entry <= e50
        )
        bb_mid_with = (side == "BUY" and entry >= bm) or (side == "SELL" and entry <= bm)
        desk_hits = sum([vwap_with, ema_with, ema50_with, bb_mid_with])

        di_ok = (side == "BUY" and pdi[i] > mdi[i]) or (side == "SELL" and mdi[i] > pdi[i])
        gate34 = (side == "BUY" and entry >= e34) or (side == "SELL" and entry <= e34)
        held = bool(di_ok and gate34 and vwap_with)
        ad = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))
        htf_raw = htf_bias_lookup(bias15, idx[i])
        htf_with = (side == "BUY" and htf_raw == "up") or (side == "SELL" and htf_raw == "down")

        ctrl = (side == "BUY" and loc >= 0.65 and green) or (side == "SELL" and loc <= 0.35 and red)
        close_strong = (side == "BUY" and loc >= 0.8) or (side == "SELL" and loc <= 0.2)

        so_far = by_day[d][by_day[d] < i]
        if len(so_far):
            sess_hi, sess_lo = float(np.max(h[so_far])), float(np.min(l[so_far]))
        else:
            sess_hi = sess_lo = entry
        into_ext = (side == "BUY" and (sess_hi - entry) <= max(8.0, a)) or (
            side == "SELL" and (entry - sess_lo) <= max(8.0, a)
        )
        # distance from EMA34 in ATR — chasing if too far
        dist34 = abs(entry - e34) / a
        not_chase = dist34 <= EXT_ATR_MAX
        near34 = dist34 <= 1.0

        rs = float(rsi[i]) if np.isfinite(rsi[i]) else 50.0
        rsi_ok = (side == "BUY" and 45 <= rs <= 72) or (side == "SELL" and 28 <= rs <= 55)

        m = int(mins[i])
        skip_open = m >= 9 * 60 + 45
        am = m < 11 * 60 + 30
        prime = (9 * 60 + 45) <= m <= (12 * 60 + 30) or (13 * 60 + 15) <= m <= (14 * 60 + 15)
        atr_hi = a >= 10.0
        atr_ok = a >= 6.0
        big_body = body >= max(6.0, 0.55 * a)
        disp08 = body >= 0.8 * a

        return {
            "vwap_with": bool(vwap_with),
            "ema_with": bool(ema_with),
            "ema50_with": bool(ema50_with),
            "bb_mid_with": bool(bb_mid_with),
            "desk_ge2": desk_hits >= 2,
            "desk_ge3": desk_hits >= 3,
            "desk_ge4": desk_hits >= 4,
            "desk_hits": int(desk_hits),
            "held": held,
            "di_ok": bool(di_ok),
            "gate34": bool(gate34),
            "ad": bool(ad),
            "htf_with": bool(htf_with),
            "ctrl": bool(ctrl),
            "close_strong": bool(close_strong),
            "not_extreme": not into_ext,
            "not_chase": bool(not_chase),
            "near34": bool(near34),
            "rsi_ok": bool(rsi_ok),
            "skip_open": bool(skip_open),
            "am": bool(am),
            "prime": bool(prime),
            "atr_hi": bool(atr_hi),
            "atr_ok": bool(atr_ok),
            "big_body": bool(big_body),
            "disp08": bool(disp08),
            "dist34": round(float(dist34), 2),
            "atr": round(a, 2),
        }

    cands: List[dict] = []

    def emit(mode: str, i: int, side: str, streak: int, meta: Optional[dict] = None):
        if not (MINS_LO <= mins[i] <= MINS_HI):
            return
        if day[i] not in keep:
            return
        entry = float(c[i])
        fp = feats(i, side, entry)
        ok, reason, exit_px, j, pts = scalper.path_ma_trail(h, l, c, ema34, i, side, T15)
        row = {
            "mode": mode,
            "day": day[i],
            "hm": idx[i].strftime("%H:%M"),
            "mins": int(mins[i]),
            "side": side,
            "entry": round(entry, 2),
            "streak": int(streak),
            "has_oracle": i in evt_i,
            "t15_win": bool(ok),
            "reason": reason,
            "pts": round(float(pts), 2) if pts is not None else None,
            **fp,
        }
        if meta:
            row.update(meta)
        cands.append(row)

    # ---- Mode A: streak first hits 4/5/6 ----
    for i in range(n):
        if day[i] not in keep:
            continue
        side = color_side(o, c, i)
        if side is None:
            continue
        st = streak_len_at(o, c, day, i, side)
        if st not in (4, 5, 6):
            continue
        # first hit only
        if i > 0 and day[i - 1] == day[i]:
            prev = color_side(o, c, i - 1)
            if prev == side and streak_len_at(o, c, day, i - 1, side) == st - 1 and st - 1 >= 4:
                # already counted at earlier hit for this streak if prior was also 4/5/6
                # allow emit only when THIS bar is the first time streak reaches st
                pass
        emit(f"hit{st}", i, side, st)

    # ---- Mode B: confirm+1 — streak hit N, next bar same color ----
    for i in range(1, n):
        if day[i] != day[i - 1] or day[i] not in keep:
            continue
        side = color_side(o, c, i)
        if side is None:
            continue
        prev_side = color_side(o, c, i - 1)
        if prev_side != side:
            continue
        pst = streak_len_at(o, c, day, i - 1, side)
        if pst not in (4, 5, 6):
            continue
        # prev was first-hit of that streak?
        # require prev streak == pst and this bar continues → confirm
        cst = streak_len_at(o, c, day, i, side)
        if cst != pst + 1:
            continue
        emit(f"conf{pst}", i, side, cst, {"base_streak": pst})

    # ---- Mode C: pullback resume — after streak≥4, 1–3 opposite, then resume ----
    for i in range(n):
        if day[i] not in keep:
            continue
        side = color_side(o, c, i)
        if side is None:
            continue
        # current bar resumes side; look back for opposite pullback then prior streak
        # find start of current resume bar(s) — emit only on FIRST resume bar after pullback
        if i > 0 and day[i - 1] == day[i] and color_side(o, c, i - 1) == side:
            continue  # not first resume bar
        # walk back opposite bars
        j = i - 1
        opp = 0
        while j >= 0 and day[j] == day[i]:
            cs = color_side(o, c, j)
            if cs is None or cs == side:
                break
            opp += 1
            j -= 1
            if opp > PB_MAX:
                break
        if not (1 <= opp <= PB_MAX):
            continue
        # j should be end of prior same-side streak
        if j < 0 or day[j] != day[i]:
            continue
        if color_side(o, c, j) != side:
            continue
        pst = streak_len_at(o, c, day, j, side)
        if pst < 4:
            continue
        emit("pullback", i, side, pst, {"pb_bars": opp, "impulse_streak": pst})

    print(f"candidates: {len(cands)}", flush=True)
    by_mode = defaultdict(int)
    for r in cands:
        by_mode[r["mode"]] += 1
    print("by mode:", dict(by_mode), flush=True)

    books = []

    def add(name, pred, pool=None):
        src = pool if pool is not None else cands
        hit = [r for r in src if pred(r)]
        one = one_per_day(hit)
        st1 = pack(one, "t15_win", mid_day)
        sta = pack(hit, "t15_win", mid_day)
        v = verdict(st1)
        books.append({
            "name": name,
            "verdict": v,
            "one": st1,
            "all": sta,
            "samples": one[:10],
        })
        print(
            f"  {name}: 1d n={st1['n']} T15={st1['prec']}% tr={st1['train_prec']}% "
            f"oos={st1['oos_prec']}% all={sta['n']}/{sta['prec']}% → {v}",
            flush=True,
        )
        return st1, v

    print("\n--- mode baselines ---", flush=True)
    for m in ("hit4", "hit5", "hit6", "conf4", "conf5", "conf6", "pullback"):
        add(m, lambda r, m=m: r["mode"] == m)

    print("\n--- prior best recreates ---", flush=True)
    add("hit6+desk≥3+held", lambda r: r["mode"] == "hit6" and r["desk_ge3"] and r["held"])
    add("any_hit+desk≥3", lambda r: r["mode"] in ("hit4", "hit5", "hit6") and r["desk_ge3"])
    add("any_hit+desk≥3+held", lambda r: r["mode"] in ("hit4", "hit5", "hit6") and r["desk_ge3"] and r["held"])

    print("\n--- quality lifts on hit6 ---", flush=True)
    hit6 = [r for r in cands if r["mode"] == "hit6"]
    for nm, pred in [
        ("hit6+htf", lambda r: r["htf_with"]),
        ("hit6+ad", lambda r: r["ad"]),
        ("hit6+held", lambda r: r["held"]),
        ("hit6+ctrl", lambda r: r["ctrl"]),
        ("hit6+!ext", lambda r: r["not_extreme"]),
        ("hit6+!chase", lambda r: r["not_chase"]),
        ("hit6+near34", lambda r: r["near34"]),
        ("hit6+skip_open", lambda r: r["skip_open"]),
        ("hit6+prime", lambda r: r["prime"]),
        ("hit6+atr_hi", lambda r: r["atr_hi"]),
        ("hit6+desk≥3+htf", lambda r: r["desk_ge3"] and r["htf_with"]),
        ("hit6+desk≥3+held+htf", lambda r: r["desk_ge3"] and r["held"] and r["htf_with"]),
        ("hit6+desk≥3+held+!chase", lambda r: r["desk_ge3"] and r["held"] and r["not_chase"]),
        ("hit6+desk≥3+held+!ext", lambda r: r["desk_ge3"] and r["held"] and r["not_extreme"]),
        ("hit6+desk≥3+held+htf+!chase", lambda r: r["desk_ge3"] and r["held"] and r["htf_with"] and r["not_chase"]),
        ("hit6+desk≥3+held+htf+!ext", lambda r: r["desk_ge3"] and r["held"] and r["htf_with"] and r["not_extreme"]),
        ("hit6+desk≥3+ad+htf", lambda r: r["desk_ge3"] and r["ad"] and r["htf_with"]),
        ("hit6+held+htf+!chase+skip", lambda r: r["held"] and r["htf_with"] and r["not_chase"] and r["skip_open"]),
        ("hit6+FULL_Q", lambda r: r["desk_ge3"] and r["held"] and r["htf_with"] and r["not_chase"] and r["not_extreme"] and r["skip_open"]),
        ("hit6+desk≥3+held+htf+ad+!chase", lambda r: r["desk_ge3"] and r["held"] and r["htf_with"] and r["ad"] and r["not_chase"]),
        ("hit6+vwap+ema+held+htf+!chase", lambda r: r["vwap_with"] and r["ema_with"] and r["held"] and r["htf_with"] and r["not_chase"]),
        ("hit6+ctrl+held+htf+!ext", lambda r: r["ctrl"] and r["held"] and r["htf_with"] and r["not_extreme"]),
        ("hit6+close_strong+held+htf", lambda r: r["close_strong"] and r["held"] and r["htf_with"]),
        ("hit6+prime+desk≥3+held+htf", lambda r: r["prime"] and r["desk_ge3"] and r["held"] and r["htf_with"]),
        ("hit6+atr_hi+desk≥3+held+htf", lambda r: r["atr_hi"] and r["desk_ge3"] and r["held"] and r["htf_with"]),
        ("hit6+near34+desk≥3+held+htf", lambda r: r["near34"] and r["desk_ge3"] and r["held"] and r["htf_with"]),
        ("hit6+rsi_ok+desk≥3+held+htf", lambda r: r["rsi_ok"] and r["desk_ge3"] and r["held"] and r["htf_with"]),
        ("hit6+oracle+desk≥3+held+htf", lambda r: r["has_oracle"] and r["desk_ge3"] and r["held"] and r["htf_with"]),
    ]:
        add(nm, pred, hit6)

    print("\n--- confirm modes ---", flush=True)
    for base_m in ("conf4", "conf5", "conf6"):
        pool = [r for r in cands if r["mode"] == base_m]
        add(f"{base_m}+desk≥3+held", lambda r: r["desk_ge3"] and r["held"], pool)
        add(f"{base_m}+desk≥3+held+htf", lambda r: r["desk_ge3"] and r["held"] and r["htf_with"], pool)
        add(f"{base_m}+desk≥3+held+htf+!chase", lambda r: r["desk_ge3"] and r["held"] and r["htf_with"] and r["not_chase"], pool)
        add(f"{base_m}+held+htf+!ext+skip", lambda r: r["held"] and r["htf_with"] and r["not_extreme"] and r["skip_open"], pool)
        add(f"{base_m}+FULL_Q", lambda r: r["desk_ge3"] and r["held"] and r["htf_with"] and r["not_chase"] and r["not_extreme"] and r["skip_open"], pool)

    print("\n--- pullback resume ---", flush=True)
    pb = [r for r in cands if r["mode"] == "pullback"]
    for nm, pred in [
        ("pb", lambda r: True),
        ("pb+desk≥3", lambda r: r["desk_ge3"]),
        ("pb+desk≥3+held", lambda r: r["desk_ge3"] and r["held"]),
        ("pb+desk≥3+held+htf", lambda r: r["desk_ge3"] and r["held"] and r["htf_with"]),
        ("pb+desk≥3+held+htf+!chase", lambda r: r["desk_ge3"] and r["held"] and r["htf_with"] and r["not_chase"]),
        ("pb+held+htf+!ext", lambda r: r["held"] and r["htf_with"] and r["not_extreme"]),
        ("pb+held+htf+!chase+skip", lambda r: r["held"] and r["htf_with"] and r["not_chase"] and r["skip_open"]),
        ("pb+ctrl+held+htf", lambda r: r["ctrl"] and r["held"] and r["htf_with"]),
        ("pb+ad+held+htf+desk≥3", lambda r: r["ad"] and r["held"] and r["htf_with"] and r["desk_ge3"]),
        ("pb+FULL_Q", lambda r: r["desk_ge3"] and r["held"] and r["htf_with"] and r["not_chase"] and r["not_extreme"] and r["skip_open"]),
        ("pb+impulse≥6+desk≥3+held+htf", lambda r: (r.get("impulse_streak") or 0) >= 6 and r["desk_ge3"] and r["held"] and r["htf_with"]),
        ("pb+impulse≥5+desk≥3+held+htf+!chase", lambda r: (r.get("impulse_streak") or 0) >= 5 and r["desk_ge3"] and r["held"] and r["htf_with"] and r["not_chase"]),
        ("pb+near34+held+htf+desk≥3", lambda r: r["near34"] and r["held"] and r["htf_with"] and r["desk_ge3"]),
        ("pb+prime+desk≥3+held+htf", lambda r: r["prime"] and r["desk_ge3"] and r["held"] and r["htf_with"]),
        ("pb+atr_hi+desk≥3+held+htf", lambda r: r["atr_hi"] and r["desk_ge3"] and r["held"] and r["htf_with"]),
    ]:
        add(nm, pred, pb)

    # Exhaustive hunt on promising feature sets
    print("\n--- hunt combinations ---", flush=True)
    feat_keys = [
        "desk_ge3", "held", "htf_with", "ad", "not_chase", "not_extreme",
        "skip_open", "ctrl", "close_strong", "near34", "atr_hi", "prime", "rsi_ok",
    ]
    hunt_pools = {
        "hit6": [r for r in cands if r["mode"] == "hit6"],
        "conf6": [r for r in cands if r["mode"] == "conf6"],
        "pullback": pb,
        "any_hit": [r for r in cands if r["mode"] in ("hit4", "hit5", "hit6")],
        "any_conf": [r for r in cands if r["mode"] in ("conf4", "conf5", "conf6")],
    }
    hunt_hits = []
    for pname, pool in hunt_pools.items():
        for k in (2, 3, 4, 5):
            for combo in combinations(feat_keys, k):
                # require at least one structural filter
                if not any(x in combo for x in ("desk_ge3", "held", "htf_with")):
                    continue
                hit = [r for r in pool if all(r.get(f) for f in combo)]
                one = one_per_day(hit)
                if len(one) < 15:
                    continue
                st1 = pack(one, "t15_win", mid_day)
                if (st1["prec"] or 0) < 65:
                    continue
                v = verdict(st1)
                hunt_hits.append({
                    "pool": pname,
                    "combo": "+".join(combo),
                    "verdict": v,
                    "one": st1,
                    "all_n": len(hit),
                    "all_prec": pack(hit, "t15_win", mid_day)["prec"],
                })
                if (st1["prec"] or 0) >= 70:
                    add(f"HUNT:{pname}|{'+'.join(combo)}", lambda r, combo=combo: all(r.get(f) for f in combo), pool)

    hunt_hits.sort(key=lambda x: (-(x["one"]["prec"] or 0), -x["one"]["n"]))
    print(f"hunt survivors ≥65% 1d (n≥15): {len(hunt_hits)}", flush=True)
    for hrow in hunt_hits[:25]:
        o1 = hrow["one"]
        print(
            f"  [{hrow['verdict']}] {hrow['pool']}|{hrow['combo']}: "
            f"n={o1['n']} T15={o1['prec']}% oos={o1['oos_prec']}%",
            flush=True,
        )

    # Winner lift table on hit6 desk≥3
    base_h6 = [r for r in hit6 if r["desk_ge3"]]
    win = [r for r in base_h6 if r["t15_win"]]
    lose = [r for r in base_h6 if not r["t15_win"]]
    lift_rows = []
    for k in feat_keys + ["vwap_with", "ema_with", "ema50_with", "bb_mid_with", "desk_ge4", "big_body", "disp08", "has_oracle", "am"]:
        if not win or not lose:
            continue
        pw = 100.0 * sum(1 for r in win if r.get(k)) / len(win)
        pl = 100.0 * sum(1 for r in lose if r.get(k)) / len(lose)
        lift_rows.append({"mark": k, "win_pct": round(pw, 1), "lose_pct": round(pl, 1), "lift_pp": round(pw - pl, 1)})
    lift_rows.sort(key=lambda x: -x["lift_pp"])

    # Rank books
    ranked = sorted(
        [b for b in books if b["one"]["n"] >= 15],
        key=lambda b: (-(b["one"]["prec"] or 0), -b["one"]["n"]),
    )
    best = ranked[0] if ranked else None
    best70 = next((b for b in ranked if (b["one"]["prec"] or 0) >= 70 and (b["one"]["oos_prec"] or 0) >= 65), None)
    best75 = next((b for b in ranked if b["verdict"] in ("HIGH_75", "HIGH_85")), None)

    lines = [
        "# NIFTY 1m — Oracle×Desk×streak **v3** (accuracy improve)",
        "",
        "> Goal: lift T15 entry accuracy above prior ~58–63% ceiling.",
        "> Modes: **hit4/5/6** · **confirm+1** · **pullback-resume**.",
        "> Filters: Desk core · held · HTF15 · AD · !chase · !extreme · session · ATR.",
        "> Metric = EMA34 trail **T15** (Oracle exit). 1/day + walk-forward.",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS **{mid_day}**. Candidates **{len(cands)}**.",
        "",
        "## 0) Mode counts",
        "",
        "| Mode | n |",
        "|---|---:|",
    ]
    for m, cnt in sorted(by_mode.items()):
        lines.append(f"| `{m}` | {cnt} |")

    lines += [
        "",
        "## 1) Lift on hit6+desk≥3 (winners vs losers)",
        "",
        "| Mark | % Winners | % Losers | Lift pp |",
        "|---|---:|---:|---:|",
    ]
    for lr in lift_rows[:20]:
        lines.append(f"| `{lr['mark']}` | {lr['win_pct']} | {lr['lose_pct']} | {lr['lift_pp']} |")

    lines += [
        "",
        "## 2) Curated + hunt gates (1/day · T15%)",
        "",
        "| Gate | Verdict | n | T15% | Train | OOS | all n/prec | avg pts |",
        "|---|---|---:|---:|---:|---:|---|---:|",
    ]
    for b in ranked[:60]:
        o1, a1 = b["one"], b["all"]
        lines.append(
            f"| `{b['name']}` | **{b['verdict']}** | {o1['n']} | **{o1['prec']}** | "
            f"{o1['train_prec']} | {o1['oos_prec']} | {a1['n']}/{a1['prec']} | {o1['avg_pts']} |"
        )

    lines += ["", "## 3) Hunt ≥70% T15 (1/day, n≥15, OOS≥65)", ""]
    good70 = [h for h in hunt_hits if (h["one"]["prec"] or 0) >= 70 and (h["one"]["oos_prec"] or 0) >= 65]
    if not good70:
        lines.append("_None stable at ≥70% with OOS≥65._")
    else:
        lines += ["| Pool | Combo | Verdict | n | T15% | Train | OOS |", "|---|---|---|---:|---:|---:|---:|"]
        for hrow in good70[:30]:
            o1 = hrow["one"]
            lines.append(
                f"| `{hrow['pool']}` | `{hrow['combo']}` | **{hrow['verdict']}** | "
                f"{o1['n']} | **{o1['prec']}** | {o1['train_prec']} | {o1['oos_prec']} |"
            )

    lines += ["", "## 4) Best accurate entry (this pass)", ""]
    if best75:
        pick = best75
        tag = "HIGH (≥75%)"
    elif best70:
        pick = best70
        tag = "OK (≥70%)"
    else:
        pick = best
        tag = "best effort"
    if pick:
        o1 = pick["one"]
        lines += [
            f"**{tag}:** `{pick['name']}` · **{pick['verdict']}**",
            f"- 1/day T15 **{o1['prec']}%** · TRAIN **{o1['train_prec']}%** · OOS **{o1['oos_prec']}%** · n={o1['n']}",
            f"- avg pts **{o1['avg_pts']}**",
            "",
            "### Recipe",
            "",
            "```",
            "1) Wait 4–6 same-color 1m bars (direction)",
            "2) Entry mode = hit / confirm+1 / pullback-resume (see gate name)",
            "3) Desk core: VWAP + EMA stack + EMA50 / BBmid (≥3)",
            "4) Quality: held (DI+EMA34+VWAP) · HTF15 with · not chase EMA34",
            "5) Optional: skip open <09:45 · not session extreme · AD with",
            "6) Exit: EMA34 trail · T15 (Oracle geometry)",
            "```",
            "",
            "### Samples",
            "",
            "| Day | HM | Side | Entry | mode | streak | desk | T15 |",
            "|---|---|---|---:|---|---:|---:|---|",
        ]
        for x in pick["samples"][:10]:
            lines.append(
                f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | "
                f"{x['mode']} | {x['streak']} | {x['desk_hits']} | {x['t15_win']} |"
            )
    else:
        lines.append("_No qualifying book._")

    lines += [
        "",
        "## 5) vs prior",
        "",
        "- v1 (oracle event + streak present): best ~**63%** T15",
        "- v2 (enter at streak hit): best ~**59%** T15",
        f"- v3 (this): best **{(pick['one']['prec'] if pick else None)}%** · verdict **{(pick['verdict'] if pick else None)}**",
        "",
        "## 6) Live takeaway",
        "",
        "- If ≥75% OOS-stable: wire that gate into Oracle T15 notify.",
        "- If only ~65–70%: still better than raw Oracle; not “mostly accurate”.",
        "- Target research only after entry gate holds walk-forward.",
        "",
        f"_Generated in {time.time()-t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    payload = {
        "window": [day_lo, day_hi],
        "oos": mid_day,
        "n_cands": len(cands),
        "by_mode": dict(by_mode),
        "lift": lift_rows[:30],
        "books": [
            {"name": b["name"], "verdict": b["verdict"], "one": b["one"], "all": b["all"]}
            for b in ranked[:80]
        ],
        "hunt_top": hunt_hits[:40],
        "best": {
            "name": pick["name"] if pick else None,
            "verdict": pick["verdict"] if pick else None,
            "one": pick["one"] if pick else None,
        },
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {REPORT}", flush=True)
    print(f"BEST: {pick['name'] if pick else None} → {pick['verdict'] if pick else None} "
          f"T15={pick['one']['prec'] if pick else None}%", flush=True)
    print(f"done in {time.time()-t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
