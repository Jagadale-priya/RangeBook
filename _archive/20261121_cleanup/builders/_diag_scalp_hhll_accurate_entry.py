"""RESEARCH ONLY — Accurate entry from High / Low / HH / HL / LH / LL structure.

Pure OHLC swing structure on 1m:
  - Confirm fractal swings (L=3)
  - Label each new swing vs prior same-type: HH / LH (highs), HL / LL (lows)
  - Bias = HH+HL (up) or LH+LL (down)

Entry logics hunted:
  A) HL retest in uptrend (buy the higher-low)
  B) LH retest in downtrend (sell the lower-high)
  C) Break last HH then retest (bull BOS retest)
  D) Break last LL then retest (bear BOS retest)
  E) Fresh HH print after HL (momentum confirm buy)
  F) Fresh LL print after LH (momentum confirm sell)
  G) CHoCH: break opposite swing then retest new side

Metric: EMA34 trail T15 + path 0.35×ATR + mfe30.
Quality: HTF15, ATR≥10/12, held (DI+EMA34+VWAP), streak 4–6.

  python -u prod_live/tests/builders/_diag_scalp_hhll_accurate_entry.py
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
    swing_points,
    SWING_L,
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
ZONE_ATR = 0.40
LEAVE_ATR = 0.35
PATH_ATR = 0.35
PATH_BARS = 8
FWD = 40
RETEST_MAX = 50


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


def color_side(o, c, i):
    if c[i] > o[i]:
        return "BUY"
    if c[i] < o[i]:
        return "SELL"
    return None


def streak_len(o, c, day, i, side):
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
    print("HH/HL/LH/LL accurate entry hunt — deep structure analysis", flush=True)

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

    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    mid_day = days_sorted[n_days // 2]
    df = df[[str(ts.date()) in keep for ts in df.index]].copy()
    print(f"window {day_lo}→{day_hi} n={n_days} OOS≥{mid_day}", flush=True)

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
    ad_r = df["ad_rising"].astype(bool).values
    ad_f = df["ad_falling"].astype(bool).values
    day = np.array([str(ts.date()) for ts in df.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df.index])
    idx = df.index
    n = len(c)

    # ---- Causal swing confirmation + HH/HL/LH/LL labels ----
    sh_idx, sl_idx = swing_points(h, l, L=SWING_L)
    sh_set, sl_set = set(sh_idx), set(sl_idx)

    # At bar i, newly confirmed swing is at i-SWING_L
    # Track labeled swings
    highs: List[dict] = []  # {i, px, tag: HH/LH, conf_i}
    lows: List[dict] = []

    # Per-bar state snapshots (for entry-time context)
    state_at: List[Optional[dict]] = [None] * n
    bias = None
    last_hh = last_hl = last_lh = last_ll = None
    last_sh = last_sl = None  # (i, px, tag)

    # Events to drive entry searches
    events: List[dict] = []  # structure events with labels

    for i in range(n):
        # confirm swings
        if i - SWING_L in sh_set:
            j = i - SWING_L
            px = float(h[j])
            tag = None
            if last_sh is not None:
                tag = "HH" if px > last_sh[1] else "LH"
            highs.append({"i": j, "px": px, "tag": tag, "conf_i": i})
            last_sh = (j, px, tag)
            if tag == "HH":
                last_hh = (j, px)
                events.append({"kind": "HH", "side": "BUY", "i": i, "pivot_i": j, "level": px})
            elif tag == "LH":
                last_lh = (j, px)
                events.append({"kind": "LH", "side": "SELL", "i": i, "pivot_i": j, "level": px})

        if i - SWING_L in sl_set:
            j = i - SWING_L
            px = float(l[j])
            tag = None
            if last_sl is not None:
                tag = "HL" if px > last_sl[1] else "LL"
            lows.append({"i": j, "px": px, "tag": tag, "conf_i": i})
            last_sl = (j, px, tag)
            if tag == "HL":
                last_hl = (j, px)
                events.append({"kind": "HL", "side": "BUY", "i": i, "pivot_i": j, "level": px})
            elif tag == "LL":
                last_ll = (j, px)
                events.append({"kind": "LL", "side": "SELL", "i": i, "pivot_i": j, "level": px})

        # update bias from last two labeled highs+lows
        recent_h = [x for x in highs if x["tag"]][-2:]
        recent_l = [x for x in lows if x["tag"]][-2:]
        if len(recent_h) >= 1 and len(recent_l) >= 1:
            ht, lt = recent_h[-1]["tag"], recent_l[-1]["tag"]
            if ht == "HH" and lt == "HL":
                bias = "up"
            elif ht == "LH" and lt == "LL":
                bias = "down"
            elif ht == "HH" and lt == "LL":
                bias = "mixed_exp"  # expanding
            elif ht == "LH" and lt == "HL":
                bias = "mixed_contract"

        state_at[i] = {
            "bias": bias,
            "last_hh": last_hh,
            "last_hl": last_hl,
            "last_lh": last_lh,
            "last_ll": last_ll,
            "last_sh": last_sh,
            "last_sl": last_sl,
        }

    print(f"labeled events: {len(events)}  highs={len(highs)} lows={len(lows)}", flush=True)
    tag_counts = defaultdict(int)
    for e in events:
        tag_counts[e["kind"]] += 1
    print("tags:", dict(tag_counts), flush=True)

    def quality(i, side, entry):
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
        ad = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))
        htf = htf_bias_lookup(bias15, idx[i])
        htf_with = (side == "BUY" and htf == "up") or (side == "SELL" and htf == "down")
        st = streak_len(o, c, day, i, side)
        rng = max(float(h[i]) - float(l[i]), 0.05)
        loc = (float(c[i]) - float(l[i])) / rng
        ctrl = (side == "BUY" and loc >= 0.65 and c[i] > o[i]) or (side == "SELL" and loc <= 0.35 and c[i] < o[i])
        # room: not into session extreme
        so_far = [k for k in range(i) if day[k] == day[i]]
        if so_far:
            sess_hi, sess_lo = float(np.max(h[so_far])), float(np.min(l[so_far]))
        else:
            sess_hi = sess_lo = entry
        not_extreme = not (
            (side == "BUY" and (sess_hi - entry) <= max(8.0, a))
            or (side == "SELL" and (entry - sess_lo) <= max(8.0, a))
        )
        return {
            "atr": round(a, 2),
            "atr_hi": a >= 10.0,
            "atr_12": a >= 12.0,
            "held": held,
            "htf_with": bool(htf_with),
            "ad": bool(ad),
            "vwap_with": bool(vwap_with),
            "ema_with": bool(ema_with),
            "ema50_with": bool(ema50_with),
            "desk_ge3": sum([vwap_with, ema_with, ema50_with, gate34]) >= 3,
            "streak": int(st),
            "streak4": st >= 4,
            "streak6": st >= 6,
            "ctrl": bool(ctrl),
            "not_extreme": bool(not_extreme),
            "bias_1m": (state_at[i] or {}).get("bias"),
            "bias_with": (
                ((state_at[i] or {}).get("bias") == "up" and side == "BUY")
                or ((state_at[i] or {}).get("bias") == "down" and side == "SELL")
            ),
        }

    def score(i, side, entry, meta):
        if not (MINS_LO <= mins[i] <= MINS_HI):
            return None
        if day[i] not in keep:
            return None
        ok, reason, exit_px, j, pts = scalper.path_ma_trail(h, l, c, ema34, i, side, T15)
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        mfe = mae = 0.0
        path_ok = None
        need = PATH_ATR * a
        d = day[i]
        for j2 in range(i + 1, min(n - 1, i + FWD) + 1):
            if day[j2] != d:
                break
            if side == "BUY":
                mfe = max(mfe, float(h[j2]) - entry)
                mae = max(mae, entry - float(l[j2]))
            else:
                mfe = max(mfe, entry - float(l[j2]))
                mae = max(mae, float(h[j2]) - entry)
        for j2 in range(i + 1, min(n - 1, i + PATH_BARS) + 1):
            if day[j2] != d:
                break
            if side == "BUY" and float(h[j2]) - entry >= need:
                path_ok = True
                break
            if side == "SELL" and entry - float(l[j2]) >= need:
                path_ok = True
                break
            if side == "BUY" and entry - float(l[j2]) >= need:
                path_ok = False
                break
            if side == "SELL" and float(h[j2]) - entry >= need:
                path_ok = False
                break
        q = quality(i, side, entry)
        return {
            "day": d,
            "hm": idx[i].strftime("%H:%M"),
            "mins": int(mins[i]),
            "side": side,
            "entry": round(float(entry), 2),
            "t15_win": bool(ok),
            "pts": round(float(pts), 2) if pts is not None else None,
            "mfe": round(mfe, 2),
            "mae": round(mae, 2),
            "path_ok": path_ok is True,
            **q,
            **meta,
        }

    def wait_retest(i0, side, level, d, max_bars=RETEST_MAX):
        """Leave then retest level; enter on control close away from level."""
        a0 = float(atr[i0]) if np.isfinite(atr[i0]) and atr[i0] > 0 else 8.0
        leave = LEAVE_ATR * a0
        away = False
        for j in range(i0 + 1, min(n, i0 + max_bars + 1)):
            if day[j] != d:
                break
            if not (MINS_LO <= mins[j] <= MINS_HI):
                continue
            a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else a0
            band = ZONE_ATR * a
            if side == "BUY":
                if float(l[j]) > level + leave:
                    away = True
                if away and float(l[j]) <= level + band and float(c[j]) >= level:
                    # control: close in upper half / green
                    rng = max(float(h[j]) - float(l[j]), 0.05)
                    loc = (float(c[j]) - float(l[j])) / rng
                    if float(c[j]) > float(o[j]) and loc >= 0.55:
                        return j, float(c[j])
            else:
                if float(h[j]) < level - leave:
                    away = True
                if away and float(h[j]) >= level - band and float(c[j]) <= level:
                    rng = max(float(h[j]) - float(l[j]), 0.05)
                    loc = (float(c[j]) - float(l[j])) / rng
                    if float(c[j]) < float(o[j]) and loc <= 0.45:
                        return j, float(c[j])
        return None, None

    def wait_break_retest(i0, side, level, d, max_bars=RETEST_MAX):
        """Body close beyond level, leave, retest, continue."""
        broke = False
        break_i = None
        a0 = float(atr[i0]) if np.isfinite(atr[i0]) and atr[i0] > 0 else 8.0
        leave = LEAVE_ATR * a0
        for j in range(i0, min(n, i0 + max_bars + 1)):
            if day[j] != d:
                break
            if not broke:
                if side == "BUY" and float(c[j]) > level:
                    broke = True
                    break_i = j
                elif side == "SELL" and float(c[j]) < level:
                    broke = True
                    break_i = j
                continue
            # after break: leave then retest
            a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else a0
            band = ZONE_ATR * a
            if side == "BUY":
                if float(l[j]) > level + leave:
                    # armed leave — look ahead in same loop via state
                    pass
            # Use nested scan from break
            break
        if not broke or break_i is None:
            return None, None
        away = False
        for j in range(break_i + 1, min(n, break_i + max_bars + 1)):
            if day[j] != d:
                break
            if not (MINS_LO <= mins[j] <= MINS_HI):
                continue
            a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else a0
            band = ZONE_ATR * a
            if side == "BUY":
                if float(l[j]) > level + leave:
                    away = True
                if away and float(l[j]) <= level + band and float(c[j]) >= level:
                    rng = max(float(h[j]) - float(l[j]), 0.05)
                    loc = (float(c[j]) - float(l[j])) / rng
                    if float(c[j]) > float(o[j]) and loc >= 0.55:
                        return j, float(c[j])
            else:
                if float(h[j]) < level - leave:
                    away = True
                if away and float(h[j]) >= level - band and float(c[j]) <= level:
                    rng = max(float(h[j]) - float(l[j]), 0.05)
                    loc = (float(c[j]) - float(l[j])) / rng
                    if float(c[j]) < float(o[j]) and loc <= 0.45:
                        return j, float(c[j])
        return None, None

    cands: List[dict] = []

    # ---- A/B: HL retest (up) / LH retest (down) ----
    for e in events:
        if e["kind"] not in ("HL", "LH"):
            continue
        i_conf = int(e["i"])
        d = day[i_conf]
        if d not in keep:
            continue
        level = float(e["level"])
        side = e["side"]
        st = state_at[i_conf] or {}
        # require matching bias
        if e["kind"] == "HL" and st.get("bias") not in ("up", "mixed_exp"):
            # still allow HL retest if last high was HH
            if not (st.get("last_hh") and st["last_hh"][1] > level):
                continue
        if e["kind"] == "LH" and st.get("bias") not in ("down", "mixed_contract"):
            if not (st.get("last_ll") and st["last_ll"][1] < level):
                continue
        ei, ep = wait_retest(i_conf, side, level, d)
        if ei is None:
            continue
        row = score(ei, side, ep, {
            "logic": "HL_retest" if e["kind"] == "HL" else "LH_retest",
            "struct_tag": e["kind"],
            "level": round(level, 2),
        })
        if row:
            cands.append(row)

    # ---- C/D: Break HH then retest / Break LL then retest ----
    for e in events:
        if e["kind"] not in ("HH", "LL"):
            continue
        # After HH confirmed, look for break of that HH (continuation) — actually
        # BOS uses prior HH as level to break. When HH prints, the *previous* HH
        # was already broken to make this HH. Better: use last_sh before this as break level.
        # Simpler causal: at each bar where close breaks last confirmed opposite-of-bias swing
        pass

    # Walk-forward BOS retest using live last_hh / last_ll (first break only)
    used_bos = set()
    for i in range(1, n):
        if day[i] not in keep or day[i - 1] != day[i]:
            continue
        if not (MINS_LO <= mins[i] <= MINS_HI):
            continue
        st = state_at[i]
        if not st:
            continue
        d = day[i]
        # Bull BOS: first close that crosses above last HH
        if st.get("last_hh"):
            level = st["last_hh"][1]
            key = (d, "BUY", round(level, 2))
            if key not in used_bos and float(c[i - 1]) <= level < float(c[i]):
                used_bos.add(key)
                ei, ep = wait_break_retest(i, "BUY", level, d)
                if ei is not None:
                    row = score(ei, "BUY", ep, {
                        "logic": "HH_break_retest",
                        "struct_tag": "HH",
                        "level": round(level, 2),
                    })
                    if row:
                        cands.append(row)
        # Bear BOS: first close that crosses below last LL
        if st.get("last_ll"):
            level = st["last_ll"][1]
            key = (d, "SELL", round(level, 2))
            if key not in used_bos and float(c[i - 1]) >= level > float(c[i]):
                used_bos.add(key)
                ei, ep = wait_break_retest(i, "SELL", level, d)
                if ei is not None:
                    row = score(ei, "SELL", ep, {
                        "logic": "LL_break_retest",
                        "struct_tag": "LL",
                        "level": round(level, 2),
                    })
                    if row:
                        cands.append(row)

    # ---- E/F: Fresh HH after HL / Fresh LL after LH — enter at confirmation bar ----
    for e in events:
        i_conf = int(e["i"])
        d = day[i_conf]
        if d not in keep or not (MINS_LO <= mins[i_conf] <= MINS_HI):
            continue
        st = state_at[i_conf] or {}
        if e["kind"] == "HH":
            # need a prior HL (up structure)
            if st.get("last_hl") is None:
                continue
            if st.get("last_lh") and st["last_hl"][0] < st["last_lh"][0]:
                # more recent LH than HL → not clean up
                continue
            row = score(i_conf, "BUY", float(c[i_conf]), {
                "logic": "HH_confirm",
                "struct_tag": "HH",
                "level": round(float(e["level"]), 2),
            })
            if row:
                cands.append(row)
        if e["kind"] == "LL":
            if st.get("last_lh") is None:
                continue
            if st.get("last_hl") and st["last_lh"][0] < st["last_hl"][0]:
                continue
            row = score(i_conf, "SELL", float(c[i_conf]), {
                "logic": "LL_confirm",
                "struct_tag": "LL",
                "level": round(float(e["level"]), 2),
            })
            if row:
                cands.append(row)

    # ---- G: CHoCH-style — HH then LL (or LL then HH) flip, retest broken level ----
    for k in range(1, len(events)):
        e0, e1 = events[k - 1], events[k]
        # up→down: was making HH/HL, then LL prints below last HL
        if e1["kind"] == "LL" and e0["kind"] in ("HH", "HL", "LH"):
            # find last HL before this LL
            st = state_at[e1["i"]] or {}
            # CHoCH sell: break of last HL (already implied by LL if LL < last HL)
            if st.get("last_hl") and e1["level"] < st["last_hl"][1]:
                level = st["last_hl"][1]
                d = day[e1["i"]]
                ei, ep = wait_retest(e1["i"], "SELL", level, d)
                if ei is not None:
                    row = score(ei, "SELL", ep, {
                        "logic": "CHOCH_LL_retest_HL",
                        "struct_tag": "LL",
                        "level": round(level, 2),
                    })
                    if row:
                        cands.append(row)
        if e1["kind"] == "HH" and e0["kind"] in ("LL", "LH", "HL"):
            st = state_at[e1["i"]] or {}
            if st.get("last_lh") and e1["level"] > st["last_lh"][1]:
                level = st["last_lh"][1]
                d = day[e1["i"]]
                ei, ep = wait_retest(e1["i"], "BUY", level, d)
                if ei is not None:
                    row = score(ei, "BUY", ep, {
                        "logic": "CHOCH_HH_retest_LH",
                        "struct_tag": "HH",
                        "level": round(level, 2),
                    })
                    if row:
                        cands.append(row)

    # ---- H: HL print confirm entry (buy when HL confirms, not wait retest) ----
    for e in events:
        if e["kind"] not in ("HL", "LH"):
            continue
        i_conf = int(e["i"])
        if day[i_conf] not in keep or not (MINS_LO <= mins[i_conf] <= MINS_HI):
            continue
        st = state_at[i_conf] or {}
        if e["kind"] == "HL":
            if st.get("bias") not in ("up", "mixed_exp") and not (
                st.get("last_hh") and st["last_hh"][1] > e["level"]
            ):
                continue
            row = score(i_conf, "BUY", float(c[i_conf]), {
                "logic": "HL_confirm",
                "struct_tag": "HL",
                "level": round(float(e["level"]), 2),
            })
            if row:
                cands.append(row)
        else:
            if st.get("bias") not in ("down", "mixed_contract") and not (
                st.get("last_ll") and st["last_ll"][1] < e["level"]
            ):
                continue
            row = score(i_conf, "SELL", float(c[i_conf]), {
                "logic": "LH_confirm",
                "struct_tag": "LH",
                "level": round(float(e["level"]), 2),
            })
            if row:
                cands.append(row)

    print(f"candidates: {len(cands)}", flush=True)
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
        sta = pack(hit, "t15_win", mid_day)
        path_rows = one
        path_p = round(100.0 * sum(1 for r in path_rows if r.get("path_ok")) / len(path_rows), 2) if path_rows else None
        v = verdict(st1)
        books.append({
            "name": name, "verdict": v, "one": st1, "all": sta,
            "path_prec": path_p, "samples": one[:10],
        })
        print(
            f"  {name}: 1d n={st1['n']} T15={st1['prec']}% tr={st1['train_prec']}% "
            f"oos={st1['oos_prec']}% path={path_p}% → {v}",
            flush=True,
        )

    print("\n--- logic baselines ---", flush=True)
    for logic in sorted(by_logic.keys()):
        add(logic, lambda r, logic=logic: r["logic"] == logic)

    print("\n--- quality on each logic ---", flush=True)
    for logic in sorted(by_logic.keys()):
        pool = [r for r in cands if r["logic"] == logic]
        add(f"{logic}+bias", lambda r: r["bias_with"], pool)
        add(f"{logic}+htf", lambda r: r["htf_with"], pool)
        add(f"{logic}+held", lambda r: r["held"], pool)
        add(f"{logic}+held+htf", lambda r: r["held"] and r["htf_with"], pool)
        add(f"{logic}+held+htf+atr10", lambda r: r["held"] and r["htf_with"] and r["atr_hi"], pool)
        add(f"{logic}+held+htf+atr12", lambda r: r["held"] and r["htf_with"] and r["atr_12"], pool)
        add(f"{logic}+bias+htf+atr10", lambda r: r["bias_with"] and r["htf_with"] and r["atr_hi"], pool)
        add(f"{logic}+held+htf+atr10+ctrl", lambda r: r["held"] and r["htf_with"] and r["atr_hi"] and r["ctrl"], pool)
        add(f"{logic}+held+htf+atr10+!ext", lambda r: r["held"] and r["htf_with"] and r["atr_hi"] and r["not_extreme"], pool)
        add(f"{logic}+held+htf+atr10+streak4", lambda r: r["held"] and r["htf_with"] and r["atr_hi"] and r["streak4"], pool)

    # Combined families
    print("\n--- families ---", flush=True)
    add("ALL_retest (HL/LH/HH/LL break)", lambda r: r["logic"] in (
        "HL_retest", "LH_retest", "HH_break_retest", "LL_break_retest",
        "CHOCH_LL_retest_HL", "CHOCH_HH_retest_LH",
    ))
    add("ALL_confirm (HH/LL/HL/LH)", lambda r: r["logic"] in (
        "HH_confirm", "LL_confirm", "HL_confirm", "LH_confirm",
    ))
    add("retest+held+htf+atr10", lambda r: r["logic"] in (
        "HL_retest", "LH_retest", "HH_break_retest", "LL_break_retest",
    ) and r["held"] and r["htf_with"] and r["atr_hi"])
    add("confirm+held+htf+atr10", lambda r: r["logic"] in (
        "HH_confirm", "LL_confirm", "HL_confirm", "LH_confirm",
    ) and r["held"] and r["htf_with"] and r["atr_hi"])
    add("HL/LH_retest+held+htf+atr10", lambda r: r["logic"] in ("HL_retest", "LH_retest") and r["held"] and r["htf_with"] and r["atr_hi"])
    add("HH/LL_break_retest+held+htf+atr10", lambda r: r["logic"] in ("HH_break_retest", "LL_break_retest") and r["held"] and r["htf_with"] and r["atr_hi"])
    add("HH/LL_confirm+held+htf+atr10", lambda r: r["logic"] in ("HH_confirm", "LL_confirm") and r["held"] and r["htf_with"] and r["atr_hi"])
    add("HL/LH_confirm+held+htf+atr10", lambda r: r["logic"] in ("HL_confirm", "LH_confirm") and r["held"] and r["htf_with"] and r["atr_hi"])

    # Hunt combinations on best pools
    print("\n--- hunt ---", flush=True)
    feat = ["held", "htf_with", "atr_hi", "atr_12", "bias_with", "ctrl", "not_extreme", "ad", "desk_ge3", "streak4", "ema_with", "vwap_with"]
    hunt_pools = {
        "HL_LH_retest": [r for r in cands if r["logic"] in ("HL_retest", "LH_retest")],
        "HH_LL_break_retest": [r for r in cands if r["logic"] in ("HH_break_retest", "LL_break_retest")],
        "HH_LL_confirm": [r for r in cands if r["logic"] in ("HH_confirm", "LL_confirm")],
        "HL_LH_confirm": [r for r in cands if r["logic"] in ("HL_confirm", "LH_confirm")],
        "CHOCH_retest": [r for r in cands if r["logic"].startswith("CHOCH")],
        "ALL": cands,
    }
    hunt = []
    for pname, pool in hunt_pools.items():
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
                hunt.append({
                    "pool": pname, "combo": "+".join(combo), "verdict": v, "one": st1,
                    "path": round(100.0 * sum(1 for r in one if r.get("path_ok")) / len(one), 2),
                })
                if (st1["prec"] or 0) >= 70:
                    add(f"HUNT:{pname}|{'+'.join(combo)}", lambda r, combo=combo: all(r.get(f) for f in combo), pool)

    hunt.sort(key=lambda x: (-(x["one"]["prec"] or 0), -x["one"]["n"]))
    print(f"hunt ≥65%: {len(hunt)}", flush=True)
    for hrow in hunt[:20]:
        o1 = hrow["one"]
        print(f"  [{hrow['verdict']}] {hrow['pool']}|{hrow['combo']}: n={o1['n']} T15={o1['prec']}% oos={o1['oos_prec']}%", flush=True)

    ranked = sorted([b for b in books if b["one"]["n"] >= 15], key=lambda b: (-(b["one"]["prec"] or 0), -b["one"]["n"]))
    best = ranked[0] if ranked else None
    best70 = next((b for b in ranked if (b["one"]["prec"] or 0) >= 70 and (b["one"]["oos_prec"] or 0) >= 65 and (b["one"]["train_prec"] or 0) >= 65), None)
    best75 = next((b for b in ranked if b["verdict"] in ("HIGH_75", "HIGH_85")), None)
    pick = best75 or best70 or best

    # Lift on best family pool
    best_pool_name = "HL_LH_retest"
    for cand_name in ("HH_LL_break_retest", "HL_LH_retest", "HH_LL_confirm", "HL_LH_confirm"):
        # pick pool with most hunt survivors
        pass
    lift_pool = [r for r in cands if r["logic"] in ("HH_break_retest", "LL_break_retest", "HL_retest", "LH_retest")]
    win = [r for r in lift_pool if r["t15_win"]]
    lose = [r for r in lift_pool if not r["t15_win"]]
    lift = []
    for k in feat + ["streak6", "bias_1m"]:
        if not win or not lose:
            continue
        if k == "bias_1m":
            continue
        pw = 100.0 * sum(1 for r in win if r.get(k)) / len(win)
        pl = 100.0 * sum(1 for r in lose if r.get(k)) / len(lose)
        lift.append({"mark": k, "win_pct": round(pw, 1), "lose_pct": round(pl, 1), "lift_pp": round(pw - pl, 1)})
    lift.sort(key=lambda x: -x["lift_pp"])

    lines = [
        "# NIFTY 1m — **HH / HL / LH / LL** accurate entry hunt",
        "",
        "> Pure structure: highs & lows → HH/HL (up) or LH/LL (down).",
        "> Entries: retest HL/LH · break+retest HH/LL · confirm prints · CHoCH retest.",
        "> Metric = EMA34 trail **T15**. Quality = held · HTF15 · ATR.",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS **{mid_day}**. Candidates **{len(cands)}**.",
        "",
        "## Structure counts",
        "",
        "| Tag | n |",
        "|---|---:|",
    ]
    for k, v in sorted(tag_counts.items()):
        lines.append(f"| `{k}` | {v} |")
    lines += [
        "",
        "| Logic | n |",
        "|---|---:|",
    ]
    for k, v in sorted(by_logic.items()):
        lines.append(f"| `{k}` | {v} |")

    lines += [
        "",
        "## 1) Lift on retest/break family (winners vs losers)",
        "",
        "| Mark | % Winners | % Losers | Lift pp |",
        "|---|---:|---:|---:|",
    ]
    for lr in lift[:15]:
        lines.append(f"| `{lr['mark']}` | {lr['win_pct']} | {lr['lose_pct']} | {lr['lift_pp']} |")

    lines += [
        "",
        "## 2) Gates (1/day · T15%)",
        "",
        "| Gate | Verdict | n | T15% | Train | OOS | path% | avg MFE | avg pts |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for b in ranked[:70]:
        o1 = b["one"]
        lines.append(
            f"| `{b['name']}` | **{b['verdict']}** | {o1['n']} | **{o1['prec']}** | "
            f"{o1['train_prec']} | {o1['oos_prec']} | {b['path_prec']} | {o1['avg_mfe']} | {o1['avg_pts']} |"
        )

    lines += ["", "## 3) Hunt ≥70% (n≥15, OOS≥65, TRAIN≥65)", ""]
    good = [h for h in hunt if (h["one"]["prec"] or 0) >= 70 and (h["one"]["oos_prec"] or 0) >= 65 and (h["one"]["train_prec"] or 0) >= 65]
    if not good:
        lines.append("_None fully stable at ≥70% with both folds._")
        # show near misses
        near = [h for h in hunt if (h["one"]["prec"] or 0) >= 68][:15]
        if near:
            lines += ["", "Near misses:", "", "| Pool | Combo | Verdict | n | T15% | Train | OOS |", "|---|---|---|---:|---:|---:|---:|"]
            for hrow in near:
                o1 = hrow["one"]
                lines.append(
                    f"| `{hrow['pool']}` | `{hrow['combo']}` | **{hrow['verdict']}** | "
                    f"{o1['n']} | **{o1['prec']}** | {o1['train_prec']} | {o1['oos_prec']} |"
                )
    else:
        lines += ["| Pool | Combo | Verdict | n | T15% | Train | OOS | path% |", "|---|---|---|---:|---:|---:|---:|---:|"]
        for hrow in good[:25]:
            o1 = hrow["one"]
            lines.append(
                f"| `{hrow['pool']}` | `{hrow['combo']}` | **{hrow['verdict']}** | "
                f"{o1['n']} | **{o1['prec']}** | {o1['train_prec']} | {o1['oos_prec']} | {hrow['path']} |"
            )

    lines += ["", "## 4) Best accurate entry logic", ""]
    if pick:
        o1 = pick["one"]
        lines += [
            f"**`{pick['name']}`** · **{pick['verdict']}**",
            f"- 1/day T15 **{o1['prec']}%** · TRAIN **{o1['train_prec']}%** · OOS **{o1['oos_prec']}%** · n={o1['n']}",
            f"- path **{pick['path_prec']}%** · MFE **{o1['avg_mfe']}** · pts **{o1['avg_pts']}**",
            "",
            "### Structure recipe",
            "",
            "```",
            "1) Mark fractal swing highs & lows (L=3)",
            "2) Label: high vs prior high → HH or LH",
            "          low  vs prior low  → HL or LL",
            "3) Bias: HH+HL = UP · LH+LL = DOWN",
            "4) Entry (best gate name above):",
            "   - UP: buy HL retest OR HH break→retest OR HH/HL confirm",
            "   - DOWN: sell LH retest OR LL break→retest OR LL/LH confirm",
            "5) Quality: held (DI+EMA34+VWAP) · HTF15 with · ATR≥10",
            "6) Exit: EMA34 trail · T15",
            "```",
            "",
            "### Samples",
            "",
            "| Day | HM | Side | Entry | logic | tag | ATR | T15 | MFE |",
            "|---|---|---|---:|---|---|---:|---|---:|",
        ]
        for x in pick["samples"]:
            lines.append(
                f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | "
                f"{x['logic']} | {x['struct_tag']} | {x['atr']} | {x['t15_win']} | {x['mfe']} |"
            )
    else:
        lines.append("_No qualifying book._")

    lines += [
        "",
        "## 5) Takeaway",
        "",
        "- HH/HL/LH/LL gives **clear direction** (structure bias).",
        "- Raw confirm/retest alone is usually mid-accuracy; **ATR + held + HTF** is the accuracy lock.",
        "- Compare to streak·hit6 gate (~82%): structure should win on *logic clarity*; streak/ATR may still win on raw T15%.",
        "",
        f"_Generated in {time.time()-t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({
        "window": [day_lo, day_hi], "oos": mid_day, "n": len(cands),
        "tags": dict(tag_counts), "logics": dict(by_logic),
        "lift": lift[:20],
        "books": [{"name": b["name"], "verdict": b["verdict"], "one": b["one"], "path": b["path_prec"]} for b in ranked[:80]],
        "hunt_top": hunt[:40],
        "best": {"name": pick["name"], "verdict": pick["verdict"], "one": pick["one"]} if pick else None,
    }, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {REPORT}", flush=True)
    if pick:
        print(f"BEST: {pick['name']} → {pick['verdict']} T15={pick['one']['prec']}%", flush=True)
    print(f"done in {time.time()-t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
