"""RESEARCH ONLY — Clean ≥40pt one-direction 1m moves + range/S/R tracking.

User definition:
  UP  : from start price P to P+40, EVERY 1m candle in between is GREEN only
  DOWN: from start price P to P−40, EVERY 1m candle in between is RED only
  (no opposite-color bar until the 40pt extreme is tagged)

Questions:
  1) How many such clean ≥40 moves exist (up + down)?
  2) Where do they start — range block, support, resistance, OR edge, breakout?
  3) How often can markers IDENTIFY them at / just after ignition (coverage)?

  python -u prod_live/tests/builders/_diag_scalp_clean40_range_track.py
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
REPORT = OUT / "NIFTY_1M_CLEAN40_RANGE_TRACK.md"
REPORT_JSON = OUT / "NIFTY_1M_CLEAN40_RANGE_TRACK.json"

MINS_LO, MINS_HI = 9 * 60 + 15, 14 * 60 + 30
N_SESSIONS = 120
LOOKBACK_CAL = 240
MIN_PTS = 40.0
PIVOT_L = 3
ZONE_ATR = 0.5
RANGE_LOOK = 20  # bars to judge "in a range block" before start
RANGE_WIDTH_ATR = 3.5  # micro-range width ≤ this → block (coil)


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("CLEAN ≥40 one-direction moves + range/S/R track", flush=True)

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
    df = df[[str(ts.date()) in keep for ts in df.index]]
    print(f"window {day_lo}→{day_hi} n={n_days}", flush=True)

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

    # OR15 / OR30 per day
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

    # Prior day H/L
    prior = {}
    for i, d in enumerate(days_sorted):
        if i == 0:
            continue
        prev = days_sorted[i - 1]
        ii = by_day[prev]
        prior[d] = {"hi": float(np.max(h[ii])), "lo": float(np.min(l[ii]))}

    # Fractal swings for S/R marks (confirmed after L bars)
    swing_hi: List[Tuple[int, float]] = []
    swing_lo: List[Tuple[int, float]] = []
    for i in range(PIVOT_L, n - PIVOT_L):
        if h[i] >= np.max(h[i - PIVOT_L : i + PIVOT_L + 1]) - 1e-9:
            swing_hi.append((i + PIVOT_L, float(h[i])))  # live when confirmed
        if l[i] <= np.min(l[i - PIVOT_L : i + PIVOT_L + 1]) + 1e-9:
            swing_lo.append((i + PIVOT_L, float(l[i])))

    def nearest_level(levels, px, side_above: bool, a: float):
        """Nearest resistance (above) or support (below) within 3×ATR."""
        cand = []
        for li, lp in levels:
            if side_above and lp > px + 0.05:
                cand.append((lp - px, lp, li))
            if (not side_above) and lp < px - 0.05:
                cand.append((px - lp, lp, li))
        if not cand:
            return None, None, None
        dist, lp, li = min(cand, key=lambda x: x[0])
        if dist > 3.0 * a:
            return None, None, None
        return lp, dist, li

    def live_swings_before(i):
        sh = [(li, lp) for li, lp in swing_hi if li < i]
        sl = [(li, lp) for li, lp in swing_lo if li < i]
        return sh[-40:], sl[-40:]

    # ---------- Find clean ≥40 same-color-only runs ----------
    # Strict: from start bar open, walk consecutive same-color bars only.
    # BUY hits when max(high) - start_open ≥ 40 while still all green.
    # SELL hits when start_open - min(low) ≥ 40 while still all red.
    # One event per streak (first time 40 is reached). Do not overlap streaks.
    moves: List[dict] = []
    i = 0
    while i < n - 1:
        if day[i] not in keep or not (MINS_LO <= mins[i] <= MINS_HI):
            i += 1
            continue
        green = c[i] > o[i]
        red = c[i] < o[i]
        if not green and not red:
            i += 1
            continue
        # streak must start as color flip OR session open (new impulse)
        if i > 0 and day[i - 1] == day[i]:
            prev_g = c[i - 1] > o[i - 1]
            prev_r = c[i - 1] < o[i - 1]
            if green and prev_g:
                i += 1
                continue  # mid-streak — only start at first green
            if red and prev_r:
                i += 1
                continue

        side = "BUY" if green else "SELL"
        start_i = i
        start_px = float(o[i])  # mark level = open of first candle of clean run
        end_i = i
        hit40_i = None
        run_ext = 0.0
        j = i
        while j < n and day[j] == day[i] and mins[j] <= MINS_HI:
            is_g = c[j] > o[j]
            is_r = c[j] < o[j]
            if side == "BUY" and not is_g:
                break
            if side == "SELL" and not is_r:
                break
            if side == "BUY":
                run_ext = max(run_ext, float(h[j]) - start_px)
            else:
                run_ext = max(run_ext, start_px - float(l[j]))
            end_i = j
            if hit40_i is None and run_ext >= MIN_PTS:
                hit40_i = j
                break  # clean40 tagged — stop at first reach (path so far all same color)
            j += 1

        if hit40_i is None:
            # advance past this failed streak start
            i = end_i + 1
            continue

        # Full streak length until color breaks (for bars count after 40)
        j = hit40_i
        while j + 1 < n and day[j + 1] == day[i] and mins[j + 1] <= MINS_HI:
            if side == "BUY" and c[j + 1] > o[j + 1]:
                j += 1
                run_ext = max(run_ext, float(h[j]) - start_px)
            elif side == "SELL" and c[j + 1] < o[j + 1]:
                j += 1
                run_ext = max(run_ext, start_px - float(l[j]))
            else:
                break
        streak_end = j
        bars_to_40 = hit40_i - start_i + 1
        bars_full = streak_end - start_i + 1

        a = float(atr[start_i]) if np.isfinite(atr[start_i]) and atr[start_i] > 0 else 8.0
        d = day[start_i]
        so_far = by_day[d][by_day[d] < start_i]

        # --- Range block before start (prior bars only — causal) ---
        in_range_block = False
        range_hi = range_lo = None
        range_width = None
        look_n = RANGE_LOOK if len(so_far) >= RANGE_LOOK else (8 if len(so_far) >= 8 else 0)
        if look_n:
            look = so_far[-look_n:]
            range_hi = float(np.max(h[look]))
            range_lo = float(np.min(l[look]))
            range_width = range_hi - range_lo
            in_range_block = range_width <= RANGE_WIDTH_ATR * a

        # --- S/R marks ---
        sh, sl = live_swings_before(start_i)
        res_px, res_dist, _ = nearest_level(sh, start_px, True, a)
        sup_px, sup_dist, _ = nearest_level(sl, start_px, False, a)
        near_res = res_dist is not None and res_dist <= ZONE_ATR * a
        near_sup = sup_dist is not None and sup_dist <= ZONE_ATR * a

        # Range → trend: prior block exists, and within first 2 bars of streak
        # we CLOSE beyond that block high/low (breakout ignition).
        broke_range_up = False
        broke_range_dn = False
        if range_hi is not None and range_lo is not None:
            for k in (start_i, start_i + 1):
                if k > hit40_i or k >= n or day[k] != d:
                    break
                if side == "BUY" and c[k] > o[k] and float(c[k]) > range_hi:
                    broke_range_up = True
                    break
                if side == "SELL" and c[k] < o[k] and float(c[k]) < range_lo:
                    broke_range_dn = True
                    break
        # also count "left a coil" even if width slightly wide but still broke prior 20-bar box
        left_prior_box = broke_range_up or broke_range_dn

        od = or_lv.get(d)
        or15_break = False
        or30_break = False
        if od:
            if side == "BUY":
                or15_break = float(c[start_i]) > od["or15_hi"]
                or30_break = float(c[start_i]) > od["or30_hi"]
            else:
                or15_break = float(c[start_i]) < od["or15_lo"]
                or30_break = float(c[start_i]) < od["or30_lo"]

        pdhl = prior.get(d)
        pd_break = False
        if pdhl:
            if side == "BUY":
                pd_break = float(c[start_i]) > pdhl["hi"]
            else:
                pd_break = float(c[start_i]) < pdhl["lo"]

        # session extreme break (new high/low)
        new_sess_ext = False
        if len(so_far):
            sess_hi, sess_lo = float(np.max(h[so_far])), float(np.min(l[so_far]))
            if side == "BUY":
                new_sess_ext = float(h[start_i]) > sess_hi
            else:
                new_sess_ext = float(l[start_i]) < sess_lo

        # ignition features
        rng = max(float(h[start_i]) - float(l[start_i]), 0.05)
        loc = (float(c[start_i]) - float(l[start_i])) / rng
        ctrl = (side == "BUY" and loc >= 0.65) or (side == "SELL" and loc <= 0.35)
        body = abs(float(c[start_i]) - float(o[start_i]))
        di_ok = (side == "BUY" and pdi[start_i] > mdi[start_i]) or (
            side == "SELL" and mdi[start_i] > pdi[start_i]
        )
        above = float(c[start_i]) >= float(ema34[start_i]) if np.isfinite(ema34[start_i]) else True
        gate34 = (side == "BUY" and above) or (side == "SELL" and not above)
        vw = float(vwap[start_i]) if np.isfinite(vwap[start_i]) else start_px
        vwap_with = (side == "BUY" and float(c[start_i]) >= vw) or (
            side == "SELL" and float(c[start_i]) <= vw
        )
        held = bool(di_ok and gate34 and vwap_with)
        ad = (side == "BUY" and bool(ad_r[start_i])) or (side == "SELL" and bool(ad_f[start_i]))
        prev_opp = True
        if start_i > 0 and day[start_i - 1] == d:
            if side == "BUY":
                prev_opp = c[start_i - 1] < o[start_i - 1]
            else:
                prev_opp = c[start_i - 1] > o[start_i - 1]

        # Origin class (priority)
        if left_prior_box and in_range_block:
            origin = "RANGE_BREAK"  # left a tight coil
        elif left_prior_box:
            origin = "BOX_BREAK"  # left prior 20-bar high/low (wider box)
        elif or30_break:
            origin = "OR30_BREAK"
        elif or15_break:
            origin = "OR15_BREAK"
        elif pd_break:
            origin = "PDHL_BREAK"
        elif new_sess_ext:
            origin = "SESSION_EXT"
        elif side == "BUY" and near_sup:
            origin = "SUPPORT_BOUNCE"
        elif side == "SELL" and near_res:
            origin = "RESIST_BOUNCE"
        elif in_range_block:
            origin = "INSIDE_RANGE"
        else:
            origin = "OPEN_TREND"

        # Trackable markers at ignition (or bar+1 continue)
        markers = {
            "prev_opposite": prev_opp,
            "ctrl": ctrl,
            "held": held,
            "ad": ad,
            "in_range_block": in_range_block,
            "range_break": bool(left_prior_box and in_range_block),
            "box_break": bool(left_prior_box),  # break of prior N-bar high/low
            "near_support": near_sup,
            "near_resist": near_res,
            "or15_break": or15_break,
            "or30_break": or30_break,
            "pd_break": pd_break,
            "new_sess_ext": new_sess_ext,
            "disp08": body >= 0.8 * a,
            "big_body": body >= max(8.0, 0.6 * a),
            "am": mins[start_i] < 11 * 60,
        }

        # Early confirm: bar+1 same color (we "track" after 2nd candle)
        confirm1 = False
        if start_i + 1 <= hit40_i and start_i + 1 < n and day[start_i + 1] == d:
            if side == "BUY":
                confirm1 = c[start_i + 1] > o[start_i + 1]
            else:
                confirm1 = c[start_i + 1] < o[start_i + 1]
        markers["confirm1"] = confirm1

        moves.append(
            {
                "day": d,
                "start_hm": idx[start_i].strftime("%H:%M"),
                "hit40_hm": idx[hit40_i].strftime("%H:%M"),
                "end_hm": idx[streak_end].strftime("%H:%M"),
                "side": side,
                "start_px": round(start_px, 2),
                "hit40_px": round(start_px + MIN_PTS if side == "BUY" else start_px - MIN_PTS, 2),
                "full_ext": round(run_ext, 2),
                "bars_to_40": int(bars_to_40),
                "bars_full": int(bars_full),
                "origin": origin,
                "range_width": round(range_width, 2) if range_width is not None else None,
                "sup": round(sup_px, 2) if sup_px else None,
                "res": round(res_px, 2) if res_px else None,
                **markers,
            }
        )
        i = streak_end + 1

    print(f"clean ≥40 same-color moves: {len(moves)}", flush=True)
    buys = [m for m in moves if m["side"] == "BUY"]
    sells = [m for m in moves if m["side"] == "SELL"]
    print(f"  BUY={len(buys)} SELL={len(sells)}  avg bars_to_40={np.mean([m['bars_to_40'] for m in moves]):.1f}", flush=True)

    # Origin distribution
    origin_counts = defaultdict(int)
    for m in moves:
        origin_counts[m["origin"]] += 1

    # Marker coverage: % of true clean40 moves that had marker at ignition
    marker_keys = [
        "prev_opposite",
        "ctrl",
        "held",
        "ad",
        "confirm1",
        "in_range_block",
        "range_break",
        "box_break",
        "near_support",
        "near_resist",
        "or15_break",
        "or30_break",
        "pd_break",
        "new_sess_ext",
        "disp08",
        "big_body",
        "am",
    ]

    def coverage(rows, key):
        if not rows:
            return None
        return round(100.0 * sum(1 for r in rows if r.get(key)) / len(rows), 1)

    # Combo coverage (how many moves we "identify")
    combos = [
        ("prev_opp", lambda m: m["prev_opposite"]),
        ("prev_opp+confirm1", lambda m: m["prev_opposite"] and m["confirm1"]),
        ("box_break (prior 20-bar H/L)", lambda m: m["box_break"]),
        ("box_break+confirm1", lambda m: m["box_break"] and m["confirm1"]),
        ("tight_range_break", lambda m: m["range_break"]),
        ("tight_range_break+confirm1", lambda m: m["range_break"] and m["confirm1"]),
        ("or30_break", lambda m: m["or30_break"]),
        ("or15_break", lambda m: m["or15_break"]),
        ("new_sess_ext", lambda m: m["new_sess_ext"]),
        ("new_sess_ext+confirm1", lambda m: m["new_sess_ext"] and m["confirm1"]),
        ("S_bounce (BUY near_sup)", lambda m: m["side"] == "BUY" and m["near_support"]),
        ("R_bounce (SELL near_res)", lambda m: m["side"] == "SELL" and m["near_resist"]),
        ("prev_opp+ctrl+confirm1", lambda m: m["prev_opposite"] and m["ctrl"] and m["confirm1"]),
        ("prev_opp+held+confirm1", lambda m: m["prev_opposite"] and m["held"] and m["confirm1"]),
        ("prev_opp+ad+confirm1", lambda m: m["prev_opposite"] and m["ad"] and m["confirm1"]),
        (
            "any_structure_break",
            lambda m: m["box_break"]
            or m["range_break"]
            or m["or15_break"]
            or m["or30_break"]
            or m["pd_break"]
            or m["new_sess_ext"],
        ),
        (
            "structure_break+confirm1",
            lambda m: (
                m["box_break"]
                or m["range_break"]
                or m["or15_break"]
                or m["or30_break"]
                or m["pd_break"]
                or m["new_sess_ext"]
            )
            and m["confirm1"],
        ),
        (
            "structure_or_SR",
            lambda m: m["box_break"]
            or m["range_break"]
            or m["or15_break"]
            or m["or30_break"]
            or m["pd_break"]
            or m["new_sess_ext"]
            or (m["side"] == "BUY" and m["near_support"])
            or (m["side"] == "SELL" and m["near_resist"]),
        ),
        (
            "structure_or_SR+confirm1",
            lambda m: (
                m["box_break"]
                or m["range_break"]
                or m["or15_break"]
                or m["or30_break"]
                or m["pd_break"]
                or m["new_sess_ext"]
                or (m["side"] == "BUY" and m["near_support"])
                or (m["side"] == "SELL" and m["near_resist"])
            )
            and m["confirm1"],
        ),
    ]

    combo_stats = []
    for name, pred in combos:
        hit = [m for m in moves if pred(m)]
        combo_stats.append(
            {
                "name": name,
                "tracked": len(hit),
                "total": len(moves),
                "pct": round(100.0 * len(hit) / max(len(moves), 1), 1),
                "buy": sum(1 for m in hit if m["side"] == "BUY"),
                "sell": sum(1 for m in hit if m["side"] == "SELL"),
                "avg_ext": round(float(np.mean([m["full_ext"] for m in hit])), 1) if hit else None,
            }
        )
        print(f"  track {name}: {len(hit)}/{len(moves)} = {combo_stats[-1]['pct']}%", flush=True)

    # Per-day density
    by_day_n = defaultdict(int)
    for m in moves:
        by_day_n[m["day"]] += 1
    dens = list(by_day_n.values())
    days_with = len(by_day_n)

    # Bars-to-40 distribution
    b40 = [m["bars_to_40"] for m in moves]

    # Report
    lines = [
        "# NIFTY 1m — Clean ≥40 **one-direction** moves + Range / S / R tracking",
        "",
        "## What we mean (your definition)",
        "",
        "```",
        "UP move  : start price P → P+40, and EVERY 1m candle until +40 is GREEN only",
        "DOWN move: start price P → P−40, and EVERY 1m candle until −40 is RED only",
        "No opposite-color candle allowed before 40 pts is tagged.",
        "Mark level = OPEN of the first candle of that clean streak.",
        "```",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days} sessions).",
        "",
        "## 1) How many such moves exist?",
        "",
        f"| Metric | Value |",
        f"|---|---:|",
        f"| **Total clean ≥40 moves** | **{len(moves)}** |",
        f"| BUY (all-green to +40) | {len(buys)} |",
        f"| SELL (all-red to −40) | {len(sells)} |",
        f"| Days with ≥1 move | {days_with} / {n_days} |",
        f"| Avg moves / active day | {round(np.mean(dens), 2) if dens else 0} |",
        f"| Avg bars to reach 40 | {round(float(np.mean(b40)), 2) if b40 else 0} |",
        f"| Median bars to 40 | {int(np.median(b40)) if b40 else 0} |",
        f"| Avg full streak extension | {round(float(np.mean([m['full_ext'] for m in moves])), 1) if moves else 0} pts |",
        "",
        "## 2) Where do they start? (origin / mark context)",
        "",
        "Before each clean move we mark:",
        "",
        "| Mark | Meaning |",
        "|---|---|",
        "| **RANGE BLOCK** | Last ~20 bars width ≤ 2.5×ATR (market coiling) |",
        "| **RANGE BREAK** | First candle closes outside that block → trend start |",
        "| **SUPPORT / RESIST** | Nearest swing low/high within 0.5×ATR |",
        "| **OR15 / OR30** | Opening range edge break |",
        "| **PDHL** | Prior-day high/low break |",
        "| **SESSION EXT** | New session high/low on ignition bar |",
        "",
        "| Origin class | n | % of clean40 |",
        "|---|---:|---:|",
    ]
    for k, v in sorted(origin_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| `{k}` | {v} | {round(100.0 * v / max(len(moves), 1), 1)} |")

    lines += [
        "",
        "## 3) Marker coverage at ignition (of all clean40 moves)",
        "",
        "This answers: *when a clean ≥40 happened, was the mark already visible?*",
        "",
        "| Marker at start bar | % of clean40 moves |",
        "|---|---:|",
    ]
    for k in marker_keys:
        lines.append(f"| `{k}` | {coverage(moves, k)} |")

    lines += [
        "",
        "## 4) How many can we **track / identify**?",
        "",
        "Coverage = share of true clean ≥40 moves that match the identifier at start (or start+1).",
        "",
        "| Identifier | Tracked | Total | **Coverage %** | BUY | SELL | avg ext |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for cstat in sorted(combo_stats, key=lambda x: -x["pct"]):
        lines.append(
            f"| `{cstat['name']}` | {cstat['tracked']} | {cstat['total']} | **{cstat['pct']}** | "
            f"{cstat['buy']} | {cstat['sell']} | {cstat['avg_ext']} |"
        )

    best_struct = max(
        [c for c in combo_stats if "structure" in c["name"] or c["name"] == "range_break"],
        key=lambda x: x["pct"],
        default=None,
    )
    best_early = next((c for c in combo_stats if c["name"] == "prev_opp+confirm1"), None)

    lines += [
        "",
        "## 5) How to think about it (method)",
        "",
        "```",
        "1. While market chops → mark RANGE BLOCK (tight high/low band)",
        "2. Also mark SUPPORT (swing lows) and RESISTANCE (swing highs)",
        "3. Opening RANGE (OR15/OR30) is a special morning block",
        "4. When price CLOSES outside the block / through S or R → TREND ignition",
        "5. Track only if next 1m candles stay SAME COLOR until +40 / −40",
        "6. If an opposite-color candle prints before 40 → NOT a clean one-direction move",
        "```",
        "",
        "### Best practical trackers from this window",
        "",
    ]
    if best_early:
        lines.append(
            f"- **Earliest generic:** `{best_early['name']}` covers **{best_early['pct']}%** "
            f"({best_early['tracked']}/{best_early['total']}) of clean ≥40 moves."
        )
    if best_struct:
        lines.append(
            f"- **Structure/range marks:** `{best_struct['name']}` covers **{best_struct['pct']}%** "
            f"({best_struct['tracked']}/{best_struct['total']})."
        )
    lines += [
        "",
        "Important: high coverage ≠ high precision. Coverage = *of real clean40, how many we flag*.",
        "Precision (flag → clean40) is a separate question; this report focuses on **finding & tracking the moves**.",
        "",
        "## 6) Sample clean ≥40 moves",
        "",
        "| Day | Start | Hit40 | Side | Start px | Ext | bars→40 | Origin | range_brk | OR30 | sess_ext |",
        "|---|---|---|---|---:|---:|---:|---|---|---|---|",
    ]
    for m in moves[-30:]:
        lines.append(
            f"| {m['day']} | {m['start_hm']} | {m['hit40_hm']} | **{m['side']}** | **{m['start_px']}** | "
            f"{m['full_ext']} | {m['bars_to_40']} | {m['origin']} | {m['range_break']} | "
            f"{m['or30_break']} | {m['new_sess_ext']} |"
        )

    lines += [
        "",
        f"_Generated in {time.time() - t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "window": [day_lo, day_hi],
                "n_moves": len(moves),
                "n_buy": len(buys),
                "n_sell": len(sells),
                "origins": dict(origin_counts),
                "marker_coverage": {k: coverage(moves, k) for k in marker_keys},
                "combo_tracking": combo_stats,
                "moves_sample": moves[-50:],
                "all_moves": moves,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT}", flush=True)
    print(f"TOTAL clean40={len(moves)} BUY={len(buys)} SELL={len(sells)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
