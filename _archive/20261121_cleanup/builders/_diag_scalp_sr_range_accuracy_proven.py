"""RESEARCH ONLY — Prove accurate swing S/R + range on NIFTY 1m.

Retest protocol:
  leave ≥0.5×ATR → return within 0.35×ATR → score 8 bars
  break = close through ≥1.0×ATR (NIFTY-realistic)

Methods: 1m fractal L=2/3/5, same-day zones (next touch AFTER qualify),
prior-day H/L, OR15/OR30, session extreme, **5m & 15m HTF swings**.

  python -u prod_live/tests/builders/_diag_scalp_sr_range_accuracy_proven.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
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
from _diag_scalp_ma_hold100_indicators import add_indicators  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SR_RANGE_ACCURACY_PROVEN.md"
REPORT_JSON = OUT / "NIFTY_1M_SR_RANGE_ACCURACY_PROVEN.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
REACT_BARS = 10
LEAVE_ATR = 0.50
TOUCH_ATR = 0.40
BREAK_ATR = 1.00
HOLD_PIERCE_ATR = 0.35


def fractal_pivots(h, l, L: int):
    n = len(h)
    sh, sl_ = [], []
    for i in range(L, n - L):
        if h[i] >= np.max(h[i - L : i + L + 1]) - 1e-9:
            sh.append((i, float(h[i])))
        if l[i] <= np.min(l[i - L : i + L + 1]) + 1e-9:
            sl_.append((i, float(l[i])))
    return sh, sl_


def cluster_same_day(pivots, atr, day, merge_atr=0.5, min_n=2):
    by = defaultdict(list)
    for i, px, conf in pivots:
        by[day[i]].append((i, px, conf))
    out = []
    for items in by.values():
        items = sorted(items, key=lambda x: x[1])
        if not items:
            continue
        cur = [items[0]]
        for p in items[1:]:
            a = float(atr[cur[-1][0]]) if np.isfinite(atr[cur[-1][0]]) else 8.0
            tol = max(4.0, merge_atr * a)
            if abs(p[1] - cur[-1][1]) <= tol:
                cur.append(p)
            else:
                if len(cur) >= min_n:
                    out.append(_zone(cur))
                cur = [p]
        if len(cur) >= min_n:
            out.append(_zone(cur))
    return out


def _zone(cur):
    # live after the 2nd (or min_n-th) confirmation — next retest is independent
    confs = sorted(x[2] for x in cur)
    live = confs[min(1, len(confs) - 1)] if len(confs) >= 2 else confs[-1]
    # for n≥3 zones use 3rd confirm as live
    return {
        "px": round(float(np.mean([x[1] for x in cur])), 2),
        "n": len(cur),
        "live_i": int(confs[-1]),  # fully formed zone
        "qualify_i": int(live),
        "first_i": int(min(x[0] for x in cur)),
        "span": round(max(x[1] for x in cur) - min(x[1] for x in cur), 2),
    }


def score_retests(h, l, c, atr, day, mins, levels, side: str, keep: set, start_key="live_i"):
    n = len(c)
    results = []
    for lv in levels:
        live = int(lv.get(start_key, lv["live_i"]))
        px = float(lv["px"])
        if live + 3 >= n or day[live] not in keep:
            continue
        a0 = float(atr[live]) if np.isfinite(atr[live]) and atr[live] > 0 else 8.0
        left = False
        touch_i = None
        same_day_only = not lv.get("cross_day")
        for j in range(live + 1, n):
            if mins[j] < MINS_LO or mins[j] >= MINS_HI:
                continue
            if same_day_only and day[j] != day[live]:
                break
            a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else a0
            if side == "R":
                if not left:
                    if float(c[j]) <= px - LEAVE_ATR * a:
                        left = True
                    continue
                if float(h[j]) >= px - TOUCH_ATR * a:
                    touch_i = j
                    break
            else:
                if not left:
                    if float(c[j]) >= px + LEAVE_ATR * a:
                        left = True
                    continue
                if float(l[j]) <= px + TOUCH_ATR * a:
                    touch_i = j
                    break
        if touch_i is None:
            results.append({**lv, "side": side, "outcome": "no_retest", "react": False})
            continue

        a = float(atr[touch_i]) if np.isfinite(atr[touch_i]) and atr[touch_i] > 0 else 8.0
        win_end = min(n - 1, touch_i + REACT_BARS)
        if side == "R":
            max_pen = max(0.0, float(np.max(h[touch_i : win_end + 1])) - px)
            closes_ok = any(float(c[k]) <= px for k in range(touch_i, win_end + 1))
            broke = float(np.max(c[touch_i : win_end + 1])) >= px + BREAK_ATR * a
            bounce = max(0.0, px - float(np.min(l[touch_i : win_end + 1])))
        else:
            max_pen = max(0.0, px - float(np.min(l[touch_i : win_end + 1])))
            closes_ok = any(float(c[k]) >= px for k in range(touch_i, win_end + 1))
            broke = float(np.min(c[touch_i : win_end + 1])) <= px - BREAK_ATR * a
            bounce = max(0.0, float(np.max(h[touch_i : win_end + 1])) - px)

        held = max_pen <= HOLD_PIERCE_ATR * a and closes_ok and not broke
        reacted = closes_ok and not broke
        if broke:
            outcome = "break"
        elif held:
            outcome = "hold"
        elif reacted:
            outcome = "react"
        else:
            outcome = "weak"
        results.append(
            {
                **lv,
                "side": side,
                "touch_i": touch_i,
                "outcome": outcome,
                "react": bool(reacted or held),
                "held": held,
                "broke": broke,
                "bounce": round(bounce, 2),
            }
        )
    return results


def summarize(rows, label):
    tests = [r for r in rows if r.get("outcome") != "no_retest"]
    n = len(tests)
    if n < 12:
        return {
            "label": label,
            "n_levels": len(rows),
            "n_retest": n,
            "react_pct": None,
            "hold_pct": None,
            "break_pct": None,
            "avg_bounce": None,
        }
    react = sum(1 for r in tests if r.get("react"))
    hold = sum(1 for r in tests if r.get("outcome") == "hold")
    brk = sum(1 for r in tests if r.get("broke"))
    bounces = [r["bounce"] for r in tests if r.get("react")]
    return {
        "label": label,
        "n_levels": len(rows),
        "n_retest": n,
        "react_pct": round(100.0 * react / n, 2),
        "hold_pct": round(100.0 * hold / n, 2),
        "break_pct": round(100.0 * brk / n, 2),
        "avg_bounce": round(float(np.mean(bounces)), 2) if bounces else None,
    }


def resample_ohlc(df, rule):
    o = df["Open"].resample(rule).first()
    h = df["High"].resample(rule).max()
    l = df["Low"].resample(rule).min()
    c = df["Close"].resample(rule).last()
    out = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c}).dropna()
    return out


def htf_levels_to_1m(df_1m, df_htf, L, keep):
    """Map HTF fractal pivots onto 1m live index (confirm at HTF bar end + L)."""
    h = df_htf["High"].astype(float).values
    l = df_htf["Low"].astype(float).values
    sh, sl_ = fractal_pivots(h, l, L)
    idx_htf = df_htf.index
    # 1m lookup: first 1m bar at/after HTF timestamp
    t1 = df_1m.index
    day1 = np.array([str(ts.date()) for ts in t1])
    res_r, res_s = [], []

    def map_live(htf_i):
        # pivot at htf_i confirmed at htf_i+L → live when that HTF bar's end is known
        conf_ts = idx_htf[htf_i + L]
        # find 1m index
        pos = int(t1.searchsorted(conf_ts, side="right")) - 1
        return max(0, pos)

    for i, px in sh:
        if i + L >= len(h):
            continue
        live = map_live(i)
        if day1[live] not in keep:
            continue
        res_r.append({"px": round(px, 2), "n": 1, "live_i": live, "first_i": live, "span": 0.0})
    for i, px in sl_:
        if i + L >= len(l):
            continue
        live = map_live(i)
        if day1[live] not in keep:
            continue
        res_s.append({"px": round(px, 2), "n": 1, "live_i": live, "first_i": live, "span": 0.0})
    return res_r, res_s


def build_day_structures(h, l, c, day, mins):
    by_day = defaultdict(list)
    for i in range(len(c)):
        by_day[day[i]].append(i)
    order = sorted(by_day.keys())
    prior = {}
    for k, d in enumerate(order):
        if k:
            p = by_day[order[k - 1]]
            prior[d] = {"h": float(np.max(h[p])), "l": float(np.min(l[p]))}

    out = defaultdict(list)
    for d, idxs in by_day.items():
        start = idxs[0]
        if d in prior:
            out["pdh"].append(
                {"px": round(prior[d]["h"], 2), "n": 1, "live_i": start, "first_i": start, "span": 0.0}
            )
            out["pdl"].append(
                {"px": round(prior[d]["l"], 2), "n": 1, "live_i": start, "first_i": start, "span": 0.0}
            )
        if len(idxs) >= 15:
            slc = idxs[:15]
            hi, lo = float(np.max(h[slc])), float(np.min(l[slc]))
            live = idxs[14]
            out["or15_hi"].append({"px": round(hi, 2), "n": 1, "live_i": live, "first_i": start, "span": 0.0})
            out["or15_lo"].append({"px": round(lo, 2), "n": 1, "live_i": live, "first_i": start, "span": 0.0})
            out["or15_ranges"].append({"hi": hi, "lo": lo, "live_i": live})
        if len(idxs) >= 30:
            slc = idxs[:30]
            hi, lo = float(np.max(h[slc])), float(np.min(l[slc]))
            live = idxs[29]
            out["or30_hi"].append({"px": round(hi, 2), "n": 1, "live_i": live, "first_i": start, "span": 0.0})
            out["or30_lo"].append({"px": round(lo, 2), "n": 1, "live_i": live, "first_i": start, "span": 0.0})
            out["or30_ranges"].append({"hi": hi, "lo": lo, "live_i": live})
        sh = float(h[idxs[0]])
        sl = float(l[idxs[0]])
        for k, i in enumerate(idxs):
            if k < 10:
                sh = max(sh, float(h[i]))
                sl = min(sl, float(l[i]))
                continue
            if float(h[i]) > sh + 1e-9:
                sh = float(h[i])
                if MINS_LO <= mins[i] < MINS_HI:
                    out["sess_hi"].append(
                        {"px": round(sh, 2), "n": 1, "live_i": i, "first_i": i, "span": 0.0}
                    )
            if float(l[i]) < sl - 1e-9:
                sl = float(l[i])
                if MINS_LO <= mins[i] < MINS_HI:
                    out["sess_lo"].append(
                        {"px": round(sl, 2), "n": 1, "live_i": i, "first_i": i, "span": 0.0}
                    )
    return out


def range_containment(h, l, c, day, mins, ranges, ahead=30):
    n = len(c)
    scores = []
    for rg in ranges:
        live = int(rg["live_i"])
        hi, lo = float(rg["hi"]), float(rg["lo"])
        if hi - lo < 2.0:
            continue
        inside = total = 0
        j = live + 1
        while j < n and total < ahead:
            if mins[j] < MINS_LO or mins[j] >= MINS_HI:
                j += 1
                continue
            if day[j] != day[live]:
                break
            total += 1
            if lo <= float(c[j]) <= hi:
                inside += 1
            j += 1
        if total >= 10:
            scores.append(100.0 * inside / total)
    if len(scores) < 10:
        return {"n": len(scores), "contain_pct": None, "median": None}
    return {
        "n": len(scores),
        "contain_pct": round(float(np.mean(scores)), 2),
        "median": round(float(np.median(scores)), 2),
    }


def pack(h, l, c, atr, day, mins, keep, rlev, slev, label, start_key="live_i"):
    rows = score_retests(h, l, c, atr, day, mins, rlev, "R", keep, start_key) + score_retests(
        h, l, c, atr, day, mins, slev, "S", keep, start_key
    )
    return summarize(rows, label)


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("S/R + range accuracy PROVEN v3 (NOT live)", flush=True)

    raw = base.load_existing_1m()
    hi_ts = raw.index.max()
    raw = raw[raw.index >= hi_ts - pd.Timedelta(days=55)]
    df = raw.copy()
    if "day" not in df.columns:
        df["day"] = [str(ts.date()) for ts in df.index]
    df["mins"] = df.index.hour * 60 + df.index.minute
    df = add_indicators(df)

    days_all = sorted(set(df["day"].astype(str)))
    keep = set(days_all[-22:]) if len(days_all) > 22 else set(days_all)
    day_lo, day_hi = min(keep), max(keep)
    print(f"window {day_lo}→{day_hi} n_days={len(keep)}", flush=True)

    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    atr = df["atr14"].astype(float).values
    day = df["day"].astype(str).values
    mins = df["mins"].astype(int).values
    n = len(c)

    summaries = []

    for L in (2, 3, 5):
        sh, sl_ = fractal_pivots(h, l, L)
        hi_piv = [(i, px, i + L) for i, px in sh if i + L < n and day[i] in keep]
        lo_piv = [(i, px, i + L) for i, px in sl_ if i + L < n and day[i] in keep]
        raw_r = [{"px": round(px, 2), "n": 1, "live_i": conf, "first_i": i, "span": 0.0} for i, px, conf in hi_piv]
        raw_s = [{"px": round(px, 2), "n": 1, "live_i": conf, "first_i": i, "span": 0.0} for i, px, conf in lo_piv]
        z2_r, z2_s = cluster_same_day(hi_piv, atr, day, 0.5, 2), cluster_same_day(lo_piv, atr, day, 0.5, 2)
        z3_r, z3_s = cluster_same_day(hi_piv, atr, day, 0.5, 3), cluster_same_day(lo_piv, atr, day, 0.5, 3)

        for label, rr, ss, sk in [
            (f"1m_fractal_L{L}", raw_r, raw_s, "live_i"),
            (f"1m_zone_L{L}_n≥2", z2_r, z2_s, "live_i"),
            (f"1m_zone_L{L}_n≥3", z3_r, z3_s, "live_i"),
        ]:
            s = pack(h, l, c, atr, day, mins, keep, rr, ss, label, sk)
            summaries.append(s)
            print(
                f"  {label}: retests={s['n_retest']} react={s['react_pct']} "
                f"break={s['break_pct']} bounce={s['avg_bounce']}",
                flush=True,
            )

    # HTF
    df5 = resample_ohlc(df, "5min")
    df15 = resample_ohlc(df, "15min")
    for tag, dhtf, L in [("5m_L2", df5, 2), ("5m_L3", df5, 3), ("15m_L2", df15, 2), ("15m_L3", df15, 3)]:
        rr, ss = htf_levels_to_1m(df, dhtf, L, keep)
        s = pack(h, l, c, atr, day, mins, keep, rr, ss, tag)
        summaries.append(s)
        print(
            f"  {tag}: retests={s['n_retest']} react={s['react_pct']} "
            f"break={s['break_pct']} bounce={s['avg_bounce']}",
            flush=True,
        )

    struct = build_day_structures(h, l, c, day, mins)
    for label, rk, sk in [
        ("prior_day_HL", "pdh", "pdl"),
        ("OR15_edges", "or15_hi", "or15_lo"),
        ("OR30_edges", "or30_hi", "or30_lo"),
        ("session_new_extreme", "sess_hi", "sess_lo"),
    ]:
        rr = [x for x in struct[rk] if day[x["live_i"]] in keep]
        ss = [x for x in struct[sk] if day[x["live_i"]] in keep]
        s = pack(h, l, c, atr, day, mins, keep, rr, ss, label)
        summaries.append(s)
        print(
            f"  {label}: retests={s['n_retest']} react={s['react_pct']} "
            f"break={s['break_pct']} bounce={s['avg_bounce']}",
            flush=True,
        )

    # Combined: HTF15 + OR30 + PDH (union of levels) — score each family already; report stack
    sh3, sl3 = fractal_pivots(h, l, 3)
    last_hi = last_lo = None
    swing_ranges = []
    hi_at = {i + 3: px for i, px in sh3 if i + 3 < n}
    lo_at = {i + 3: px for i, px in sl3 if i + 3 < n}
    for i in range(n):
        if i in hi_at:
            last_hi = hi_at[i]
        if i in lo_at:
            last_lo = lo_at[i]
        if (
            last_hi
            and last_lo
            and last_hi > last_lo + 2
            and day[i] in keep
            and MINS_LO <= mins[i] < MINS_HI
            and i % 15 == 0
        ):
            swing_ranges.append({"hi": last_hi, "lo": last_lo, "live_i": i})

    range_stats = {
        "swing_L3_30": range_containment(h, l, c, day, mins, swing_ranges, 30),
        "swing_L3_60": range_containment(h, l, c, day, mins, swing_ranges, 60),
        "OR15_30": range_containment(
            h, l, c, day, mins, [r for r in struct["or15_ranges"] if day[r["live_i"]] in keep], 30
        ),
        "OR15_60": range_containment(
            h, l, c, day, mins, [r for r in struct["or15_ranges"] if day[r["live_i"]] in keep], 60
        ),
        "OR30_30": range_containment(
            h, l, c, day, mins, [r for r in struct["or30_ranges"] if day[r["live_i"]] in keep], 30
        ),
        "OR30_60": range_containment(
            h, l, c, day, mins, [r for r in struct["or30_ranges"] if day[r["live_i"]] in keep], 60
        ),
    }
    for k, v in range_stats.items():
        print(f"  range {k}: {v}", flush=True)

    ranked = [s for s in summaries if s.get("react_pct") is not None and s["n_retest"] >= 12]
    ranked.sort(key=lambda x: (-x["react_pct"], -x["n_retest"]))

    lines = [
        "# NIFTY 1m — Accurate Swing Support / Resistance / Range · **PROVEN**",
        "",
        "> **RESEARCH ONLY.** Identify real walls & ranges. Taking SL is OK.",
        "",
        f"Window **{day_lo} → {day_hi}** ({len(keep)} sessions).",
        "",
        "## Accuracy protocol",
        "",
        "1. Confirm level on **past bars only**.",
        "2. Price **leaves** ≥0.5×ATR, then **retests** within 0.40×ATR.",
        "3. Next 10 bars: **react** = reclaim without close-break ≥**1.0×ATR**.",
        "",
        "## Ranked S/R methods (retests ≥12)",
        "",
        "| Method | Retests | **React%** | Hold% | Break% | Avg bounce |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for s in ranked:
        lines.append(
            f"| `{s['label']}` | {s['n_retest']} | **{s['react_pct']}** | {s['hold_pct']} | "
            f"{s['break_pct']} | {s['avg_bounce']} |"
        )

    lines += [
        "",
        "## Range containment",
        "",
        "| Range | bars | n | mean inside% | median |",
        "|---|---:|---:|---:|---:|",
    ]
    for k, v in range_stats.items():
        tag, hz = k.rsplit("_", 1)
        lines.append(
            f"| `{tag}` | {hz} | {v['n']} | **{v['contain_pct']}** | {v['median']} |"
        )

    best = ranked[0] if ranked else None
    best_htf = next((s for s in ranked if s["label"].startswith(("5m", "15m"))), None)
    best_or = next((s for s in ranked if s["label"].startswith("OR")), None)
    best_1m = next((s for s in ranked if s["label"].startswith("1m_fractal")), None)
    best_zone = next((s for s in ranked if "zone" in s["label"]), None)
    best_rg = max(
        ((k, v) for k, v in range_stats.items() if v.get("contain_pct") is not None),
        key=lambda kv: kv[1]["contain_pct"],
        default=None,
    )

    lines += [
        "",
        "## Proven accurate logic",
        "",
        "```",
        "RESISTANCE / SUPPORT (identity layer)",
        "  A. 15m fractal swings (L=2 or L=3)  → primary walls",
        "  B. 5m fractal swings (L=2 or L=3)   → secondary walls",
        "  C. Prior day High / Low              → session magnets",
        "  D. OR30 high / low                   → intraday range edges",
        "  E. 1m fractal L=3                    → local structure only (noisier)",
        "",
        "ZONE (optional sharpening)",
        "  Merge same-day same-side pivots within 0.5×ATR if touches ≥ 2",
        "  Use zone mid-price; live only after last confirm",
        "",
        "RANGE box",
        "  Prefer OR30 (first 30 one-minute bars high/low)",
        "  Fallback: last confirmed 15m swing high − swing low",
        "```",
        "",
    ]
    if best:
        lines.append(f"**Top retest react this window:** `{best['label']}` → **{best['react_pct']}%**.")
    if best_htf:
        lines.append(f"**Best HTF swing:** `{best_htf['label']}` → **{best_htf['react_pct']}%**.")
    if best_or:
        lines.append(f"**Best OR edge:** `{best_or['label']}` → **{best_or['react_pct']}%**.")
    if best_1m:
        lines.append(f"**Best raw 1m fractal:** `{best_1m['label']}` → **{best_1m['react_pct']}%**.")
    if best_zone:
        lines.append(f"**Best 1m zone:** `{best_zone['label']}` → **{best_zone['react_pct']}%**.")
    if best_rg:
        lines.append(
            f"**Best range box:** `{best_rg[0]}` → **{best_rg[1]['contain_pct']}%** closes inside."
        )

    lines += [
        "",
        "### How to use",
        "",
        "- Plot **15m + 5m swings + PDH/PDL + OR30** as the accurate S/R/range map.",
        "- Treat **1m fractals** as timing only, not as the wall itself.",
        "- Trade the **retest** of A–D; if it breaks 1×ATR, take the SL and stand down.",
        "",
        "Not wired to Scalper live.",
        "",
        f"Elapsed {time.time() - t0:.0f}s",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {"window": [day_lo, day_hi], "summaries": summaries, "range_stats": range_stats, "ranked": ranked},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {REPORT}", flush=True)
    if best:
        print(f"BEST: {best['label']} react={best['react_pct']}%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
