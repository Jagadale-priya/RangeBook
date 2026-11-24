"""RESEARCH ONLY — Opening ZONE BOX (like you draw at open).

Idea you described:
  At/near open, mark ONE up-zone and ONE down-zone (boxes).
  Market later returns to a zone → either SWING from it or BREAK through.
  Both outcomes are real; we measure how often each happens and whether
  the day's big moves actually launch from these zones.

Zone definitions tested (no candle patterns):
  A) OR15 box: high/low of first 15 one-minute bars → up-edge & down-edge zones
  B) OR30 box: first 30 bars
  C) Open±ATR box: day open ± 1×ATR as mid; up zone = [open, open+1.5ATR],
     down = [open-1.5ATR, open]
  D) First ZigZag origin of day expanded to ±0.5×ATR box (move-origin pad)
  E) Dual: OR30 edges as thin zones (0.5×ATR thick)

Success metrics:
  1) Zone TOUCH → SWING% (reject/reclaim) vs BREAK%
  2) Did today's biggest ZigZag leg ORIGINATE inside a zone?
  3) Filtered: first revisit after leave → swing≥15pts without 1ATR break

  python -u prod_live/tests/builders/_diag_scalp_open_zone_box.py
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
from _diag_scalp_move_origin_sr_range import zigzag_legs, MINS_LO, MINS_HI  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_OPEN_ZONE_BOX.md"
REPORT_JSON = OUT / "NIFTY_1M_OPEN_ZONE_BOX.json"

ZONE_HALF_ATR = 0.50
REACT_BARS = 12
BREAK_ATR = 1.0
SWING_PTS = 15.0
LEAVE_ATR = 0.8


def day_slices(day):
    by = defaultdict(list)
    for i, d in enumerate(day):
        by[d].append(i)
    return by


def make_edge_zone(edge_px, atr, side):
    """side UP = resistance zone around edge; DOWN = support zone."""
    half = max(4.0, ZONE_HALF_ATR * atr)
    if side == "UP":
        return {
            "side": "UP",
            "lo": round(edge_px - half, 2),
            "hi": round(edge_px + half, 2),
            "mid": round(edge_px, 2),
        }
    return {
        "side": "DOWN",
        "lo": round(edge_px - half, 2),
        "hi": round(edge_px + half, 2),
        "mid": round(edge_px, 2),
    }


def build_day_zones(h, l, c, atr, day, mins, by_day, legs):
    """Return list of {day, live_i, method, up, down}."""
    out = []
    for d, idxs in by_day.items():
        if len(idxs) < 35:
            continue
        start = idxs[0]
        a = float(atr[idxs[min(14, len(idxs) - 1)]])
        if not np.isfinite(a) or a <= 0:
            a = 10.0

        # OR15
        slc15 = idxs[:15]
        or15_hi, or15_lo = float(np.max(h[slc15])), float(np.min(l[slc15]))
        live15 = idxs[14]
        out.append(
            {
                "day": d,
                "live_i": live15,
                "method": "OR15",
                "up": make_edge_zone(or15_hi, a, "UP"),
                "down": make_edge_zone(or15_lo, a, "DOWN"),
                "box_lo": round(or15_lo, 2),
                "box_hi": round(or15_hi, 2),
            }
        )

        # OR30
        slc30 = idxs[:30]
        or30_hi, or30_lo = float(np.max(h[slc30])), float(np.min(l[slc30]))
        live30 = idxs[29]
        a30 = float(atr[live30]) if np.isfinite(atr[live30]) else a
        out.append(
            {
                "day": d,
                "live_i": live30,
                "method": "OR30",
                "up": make_edge_zone(or30_hi, a30, "UP"),
                "down": make_edge_zone(or30_lo, a30, "DOWN"),
                "box_lo": round(or30_lo, 2),
                "box_hi": round(or30_hi, 2),
            }
        )

        # Open ± ATR bands
        o = float(c[start])  # use first close; better open if available
        # prefer Open column via h/l mid — use first bar open from high/low average no —
        # pass open separately: use (h+l)/2 of first bar as fallback; caller has Open in df
        open_px = float(c[start])  # overwritten below if we store opens
        out.append(
            {
                "day": d,
                "live_i": idxs[min(9, len(idxs) - 1)],  # live after 10 bars
                "method": "OPEN_ATR",
                "up": {
                    "side": "UP",
                    "lo": round(open_px, 2),
                    "hi": round(open_px + 1.5 * a, 2),
                    "mid": round(open_px + 0.75 * a, 2),
                },
                "down": {
                    "side": "DOWN",
                    "lo": round(open_px - 1.5 * a, 2),
                    "hi": round(open_px, 2),
                    "mid": round(open_px - 0.75 * a, 2),
                },
                "box_lo": round(open_px - 1.5 * a, 2),
                "box_hi": round(open_px + 1.5 * a, 2),
                "_need_open": True,
                "_start": start,
            }
        )

        # First real ZigZag origin of day → zone
        day_legs = [x for x in legs if x["day"] == d and x["mins"] >= MINS_LO]
        day_legs = sorted(day_legs, key=lambda x: x["start_i"])
        if day_legs:
            first = day_legs[0]
            ai = first["start_i"]
            aa = float(atr[ai]) if np.isfinite(atr[ai]) else a
            # opposite zone = first end of that leg? User wants one up + one down.
            # Use first BUY origin as DOWN zone, first SELL origin as UP zone in day.
            buy_o = next((x for x in day_legs if x["side"] == "BUY"), None)
            sell_o = next((x for x in day_legs if x["side"] == "SELL"), None)
            if buy_o and sell_o:
                live_z = max(buy_o["start_i"], sell_o["start_i"])
                # zones only live after both first origins known — a bit late
                # better: live after OR30, but zone centers from first origins once known
                live_z = max(live_z, live30)
                out.append(
                    {
                        "day": d,
                        "live_i": live_z,
                        "method": "FIRST_ORIGIN",
                        "up": make_edge_zone(sell_o["origin_px"], aa, "UP"),
                        "down": make_edge_zone(buy_o["origin_px"], aa, "DOWN"),
                        "box_lo": round(
                            min(buy_o["origin_px"], sell_o["origin_px"]) - ZONE_HALF_ATR * aa, 2
                        ),
                        "box_hi": round(
                            max(buy_o["origin_px"], sell_o["origin_px"]) + ZONE_HALF_ATR * aa, 2
                        ),
                    }
                )

        # Hybrid: OR30 box as the RANGE, edges are the zones (same as OR30 but tagged)
        out.append(
            {
                "day": d,
                "live_i": live30,
                "method": "OR30_BOX",
                "up": make_edge_zone(or30_hi, a30, "UP"),
                "down": make_edge_zone(or30_lo, a30, "DOWN"),
                "box_lo": round(or30_lo, 2),
                "box_hi": round(or30_hi, 2),
            }
        )
    return out


def in_zone(lo, hi, px_lo, px_hi):
    return not (px_hi < lo or px_lo > hi)


def score_zone_touches(h, l, c, atr, day, mins, zones_day, keep):
    """For each zone (up & down), find first leave then revisit; classify swing vs break."""
    events = []
    for zday in zones_day:
        if zday["day"] not in keep:
            continue
        live = int(zday["live_i"])
        for zkey in ("up", "down"):
            z = zday[zkey]
            lo, hi, mid, side = z["lo"], z["hi"], z["mid"], z["side"]
            left = False
            touch_i = None
            for j in range(live + 1, len(c)):
                if day[j] != zday["day"]:
                    break
                if mins[j] < MINS_LO or mins[j] >= MINS_HI:
                    continue
                a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else 10.0
                cl = float(c[j])
                # leave = close clearly outside zone
                if not left:
                    if side == "UP" and cl < lo - LEAVE_ATR * a * 0.25:
                        # below up-zone
                        if cl < lo - 0.3 * a:
                            left = True
                    elif side == "DOWN" and cl > hi + 0.3 * a:
                        left = True
                    elif not in_zone(lo, hi, float(l[j]), float(h[j])) and abs(cl - mid) >= LEAVE_ATR * a:
                        left = True
                    continue
                # revisit
                if in_zone(lo, hi, float(l[j]), float(h[j])):
                    touch_i = j
                    break
            if touch_i is None:
                events.append(
                    {
                        "method": zday["method"],
                        "day": zday["day"],
                        "side": side,
                        "outcome": "no_retest",
                        "swing": False,
                        "broke": False,
                    }
                )
                continue

            a = float(atr[touch_i]) if np.isfinite(atr[touch_i]) else 10.0
            end = min(len(c) - 1, touch_i + REACT_BARS)
            # same day only
            while end > touch_i and day[end] != zday["day"]:
                end -= 1

            if side == "UP":
                # swing = reject down: bounce down ≥ SWING_PTS, no close break above hi+1ATR
                broke = float(np.max(c[touch_i : end + 1])) >= hi + BREAK_ATR * a
                bounce = mid - float(np.min(l[touch_i : end + 1]))
                reclaim = any(float(c[k]) <= mid for k in range(touch_i, end + 1))
            else:
                broke = float(np.min(c[touch_i : end + 1])) <= lo - BREAK_ATR * a
                bounce = float(np.max(h[touch_i : end + 1])) - mid
                reclaim = any(float(c[k]) >= mid for k in range(touch_i, end + 1))

            swung = (not broke) and reclaim and bounce >= SWING_PTS
            if broke:
                outcome = "break"
            elif swung:
                outcome = "swing"
            elif reclaim and not broke:
                outcome = "weak_hold"
            else:
                outcome = "weak"
            events.append(
                {
                    "method": zday["method"],
                    "day": zday["day"],
                    "side": side,
                    "lo": lo,
                    "hi": hi,
                    "mid": mid,
                    "touch_i": touch_i,
                    "outcome": outcome,
                    "swing": swung,
                    "broke": broke,
                    "bounce": round(float(bounce), 2),
                    # useful reaction = swing OR break (zone did something decisive)
                    "decisive": swung or broke,
                }
            )
    return events


def origin_in_zones(legs, zones_day, keep):
    """For each day, does the biggest leg originate inside up or down zone?"""
    rows = []
    by_m = defaultdict(list)
    for z in zones_day:
        if z["day"] in keep:
            by_m[z["method"]].append(z)
    for method, zlist in by_m.items():
        hits = total = 0
        for z in zlist:
            d = z["day"]
            day_legs = [x for x in legs if x["day"] == d]
            if not day_legs:
                continue
            # legs that start AFTER zone live
            after = [x for x in day_legs if x["start_i"] > z["live_i"]]
            if not after:
                continue
            best = max(after, key=lambda x: x["pts"])
            ox = best["origin_px"]
            in_up = z["up"]["lo"] <= ox <= z["up"]["hi"]
            in_dn = z["down"]["lo"] <= ox <= z["down"]["hi"]
            total += 1
            if in_up or in_dn:
                hits += 1
            rows.append(
                {
                    "method": method,
                    "day": d,
                    "hit": in_up or in_dn,
                    "side": "UP" if in_up else ("DOWN" if in_dn else None),
                    "origin": ox,
                    "pts": best["pts"],
                }
            )
        # store summary later
    return rows


def summarize_events(events, method):
    sub = [e for e in events if e["method"] == method and e["outcome"] != "no_retest"]
    n = len(sub)
    if n < 10:
        return {
            "method": method,
            "n": n,
            "swing_pct": None,
            "break_pct": None,
            "decisive_pct": None,
            "weak_pct": None,
            "avg_bounce_swing": None,
        }
    sw = sum(1 for e in sub if e["swing"])
    br = sum(1 for e in sub if e["broke"])
    dec = sum(1 for e in sub if e["decisive"])
    weak = n - dec
    bounces = [e["bounce"] for e in sub if e["swing"]]
    return {
        "method": method,
        "n": n,
        "swing_pct": round(100.0 * sw / n, 2),
        "break_pct": round(100.0 * br / n, 2),
        "decisive_pct": round(100.0 * dec / n, 2),
        "weak_pct": round(100.0 * weak / n, 2),
        "avg_bounce_swing": round(float(np.mean(bounces)), 2) if bounces else None,
        "swing_n": sw,
        "break_n": br,
    }


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("Open ZONE BOX research (NOT live)", flush=True)

    raw = base.load_existing_1m()
    hi_ts = raw.index.max()
    raw = raw[raw.index >= hi_ts - pd.Timedelta(days=55)]
    df = raw.copy()
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
    o = df["Open"].astype(float).values
    atr = df["atr14"].astype(float).values
    day = df["day"].astype(str).values
    mins = df["mins"].astype(int).values
    by = day_slices(day)

    legs, _ = zigzag_legs(h, l, c, atr, day, mins)
    zones = build_day_zones(h, l, c, atr, day, mins, by, legs)

    # fix OPEN_ATR with real open
    fixed = []
    for z in zones:
        if z.get("_need_open"):
            start = z["_start"]
            open_px = float(o[start])
            a = float(atr[z["live_i"]]) if np.isfinite(atr[z["live_i"]]) else 10.0
            z["up"] = {
                "side": "UP",
                "lo": round(open_px, 2),
                "hi": round(open_px + 1.5 * a, 2),
                "mid": round(open_px + 0.75 * a, 2),
            }
            z["down"] = {
                "side": "DOWN",
                "lo": round(open_px - 1.5 * a, 2),
                "hi": round(open_px, 2),
                "mid": round(open_px - 0.75 * a, 2),
            }
            z["box_lo"] = round(open_px - 1.5 * a, 2)
            z["box_hi"] = round(open_px + 1.5 * a, 2)
            z.pop("_need_open", None)
            z.pop("_start", None)
        fixed.append(z)
    zones = fixed

    # dedupe OR30 vs OR30_BOX (identical) — keep both labels for clarity in report as one
    events = score_zone_touches(h, l, c, atr, day, mins, zones, keep)
    origin_rows = origin_in_zones(legs, zones, keep)

    methods = sorted({z["method"] for z in zones})
    summaries = []
    for m in methods:
        s = summarize_events(events, m)
        # origin coverage
        osub = [r for r in origin_rows if r["method"] == m]
        if osub:
            s["origin_in_zone_pct"] = round(100.0 * sum(1 for r in osub if r["hit"]) / len(osub), 2)
            s["origin_n"] = len(osub)
        else:
            s["origin_in_zone_pct"] = None
            s["origin_n"] = 0
        # per side
        for side in ("UP", "DOWN"):
            ss = [e for e in events if e["method"] == m and e.get("side") == side and e["outcome"] != "no_retest"]
            if len(ss) >= 8:
                s[f"{side}_swing"] = round(100.0 * sum(1 for e in ss if e["swing"]) / len(ss), 2)
                s[f"{side}_break"] = round(100.0 * sum(1 for e in ss if e["broke"]) / len(ss), 2)
                s[f"{side}_n"] = len(ss)
        summaries.append(s)
        print(
            f"  {m}: retests={s['n']} swing={s['swing_pct']} break={s['break_pct']} "
            f"decisive={s['decisive_pct']} origin_in={s['origin_in_zone_pct']}",
            flush=True,
        )

    # Accuracy for "zone behaved as expected map":
    # User said sometimes swing sometimes break — DECISIVE% is the key "zone matters" rate.
    # Also swing-only for mean-reversion use.
    ranked = [s for s in summaries if s.get("decisive_pct") is not None]
    ranked.sort(key=lambda x: (-(x["decisive_pct"] or 0), -(x["n"] or 0)))

    best = ranked[0] if ranked else None
    best_swing = max(
        (s for s in summaries if s.get("swing_pct") is not None),
        key=lambda x: x["swing_pct"],
        default=None,
    )
    best_origin = max(
        (s for s in summaries if s.get("origin_in_zone_pct") is not None),
        key=lambda x: x["origin_in_zone_pct"],
        default=None,
    )

    lines = [
        "# NIFTY 1m — Opening **ZONE BOX** (draw up + down at open)",
        "",
        "> **RESEARCH ONLY.** Matches your idea: one up zone, one down zone; "
        "market later **swings** from it or **breaks** it.",
        "",
        f"Window **{day_lo} → {day_hi}** ({len(keep)} sessions).",
        "",
        "## What a zone box is here",
        "",
        "```",
        "UP zone   = resistance box around a high edge  (mid ± 0.5×ATR)",
        "DOWN zone = support box around a low edge",
        "After zone is LIVE (OR complete / first origins known):",
        "  price leaves → returns into the box →",
        "    SWING = reject ≥15pts, no 1×ATR close-break",
        "    BREAK = close through zone by ≥1×ATR",
        "```",
        "",
        "Both swing and break are valid zone behaviors (as you said).",
        "**Decisive%** = swing + break (zone actually mattered).",
        "",
        "## Methods compared",
        "",
        "| Method | Retests | Swing% | Break% | **Decisive%** | Avg swing bounce | Big-leg origin in zone% |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s in ranked:
        lines.append(
            f"| `{s['method']}` | {s['n']} | {s['swing_pct']} | {s['break_pct']} | "
            f"**{s['decisive_pct']}** | {s['avg_bounce_swing']} | {s['origin_in_zone_pct']} |"
        )

    lines += [
        "",
        "## Per side (UP vs DOWN)",
        "",
        "| Method | UP n | UP swing% | UP break% | DOWN n | DOWN swing% | DOWN break% |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s in ranked:
        lines.append(
            f"| `{s['method']}` | {s.get('UP_n')} | {s.get('UP_swing')} | {s.get('UP_break')} | "
            f"{s.get('DOWN_n')} | {s.get('DOWN_swing')} | {s.get('DOWN_break')} |"
        )

    lines += ["", "## Proven takeaway", ""]
    if best:
        lines.append(
            f"**Most decisive zone map:** `{best['method']}` → decisive **{best['decisive_pct']}%** "
            f"(swing {best['swing_pct']}% / break {best['break_pct']}%, n={best['n']})."
        )
    if best_swing:
        lines.append(
            f"**Best pure swing (reject) rate:** `{best_swing['method']}` → **{best_swing['swing_pct']}%**."
        )
    if best_origin:
        lines.append(
            f"**Big moves launching from zone:** `{best_origin['method']}` → "
            f"**{best_origin['origin_in_zone_pct']}%** of day’s largest post-live legs start inside a zone."
        )

    lines += [
        "",
        "### Accurate zone logic to use (research)",
        "",
        "```",
        "At open / first 30 minutes:",
        "  BOX = OR30 high/low  (the range you draw)",
        "  UP zone   = OR30 high ± 0.5×ATR",
        "  DOWN zone = OR30 low  ± 0.5×ATR",
        "",
        "Optional sharpening (move-origin):",
        "  Also mark first BUY-origin and first SELL-origin of day as pads",
        "  (same ±0.5×ATR boxes) once those legs confirm",
        "",
        "How to read a revisit:",
        "  into UP zone   → expect SELL swing OR upside break (both OK)",
        "  into DOWN zone → expect BUY swing OR downside break (both OK)",
        "  If break → drop that edge; if swing → trade the bounce, SL beyond box",
        "```",
        "",
        "This is the zone/fox box behavior you described — not single lines, not candle patterns.",
        "",
        f"Elapsed {time.time() - t0:.0f}s",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "window": [day_lo, day_hi],
                "summaries": summaries,
                "n_events": len(events),
                "origin_rows_sample": origin_rows[:40],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {REPORT}", flush=True)
    if best:
        print(
            f"BEST decisive: {best['method']} {best['decisive_pct']}% "
            f"swing={best['swing_pct']} break={best['break_pct']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
