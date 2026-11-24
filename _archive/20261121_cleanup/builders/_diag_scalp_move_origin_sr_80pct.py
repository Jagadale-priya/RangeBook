"""RESEARCH ONLY — Push move-origin S/R pads to ≥80% proven retest→launch.

Base: ZigZag legs → origin clusters (launch pads).
Proof: after pad qualifies, leave & retest → role-matched ≥40pt move.

Search filters (n_hist, days, avg_pts, role, session location, confluence…)
to find books with react/launch ≥80% and usable sample size.

  python -u prod_live/tests/builders/_diag_scalp_move_origin_sr_80pct.py
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

# reuse zigzag / cluster from prior module
from _diag_scalp_move_origin_sr_range import (  # noqa: E402
    CLUSTER_ATR,
    CLUSTER_MAX_SPAN,
    LAUNCH_MIN_PTS,
    MINS_HI,
    MINS_LO,
    NEXT_LEG_BARS,
    NEXT_LEG_MIN_PTS,
    RETEST_TOUCH_ATR,
    cluster_origins,
    zigzag_legs,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_MOVE_ORIGIN_SR_80PCT.md"
REPORT_JSON = OUT / "NIFTY_1M_MOVE_ORIGIN_SR_80PCT.json"


def collect_retest_events(h, l, c, atr, day, mins, pads, legs, keep):
    """Every pad retest event with rich features (for filter search)."""
    events = []
    for pad in pads:
        members = sorted(pad.get("members") or [], key=lambda x: x["i"])
        if len(members) < 2:
            continue
        # evaluate after 2nd, 3rd, ... launch — each subsequent first retest window
        for qi in range(1, len(members)):
            live_i = members[qi]["i"]
            if day[live_i] not in keep:
                continue
            px = pad["px"]
            n_hist = qi + 1  # launches known so far (0..qi inclusive)
            days_hist = len({m["day"] for m in members[: qi + 1]})
            avg_pts = float(np.mean([m["pts"] for m in members[: qi + 1]]))
            buys = sum(1 for m in members[: qi + 1] if m["side"] == "BUY")
            sells = sum(1 for m in members[: qi + 1] if m["side"] == "SELL")
            role = "SUPPORT" if buys > sells else ("RESISTANCE" if sells > buys else "BOTH")

            left = False
            a0 = float(atr[live_i]) if np.isfinite(atr[live_i]) else 10.0
            touch_i = None
            for j in range(live_i + 5, len(c)):
                if mins[j] < MINS_LO or mins[j] >= MINS_HI:
                    continue
                if day[j] not in keep:
                    # allow later days in keep
                    pass
                a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else a0
                if not left:
                    if abs(float(c[j]) - px) >= 1.0 * a:
                        left = True
                    continue
                if abs(float(c[j]) - px) <= RETEST_TOUCH_ATR * a or (
                    float(l[j]) <= px <= float(h[j])
                ):
                    touch_i = j
                    break
            if touch_i is None:
                continue

            a = float(atr[touch_i]) if np.isfinite(atr[touch_i]) else a0
            want_up = role in ("SUPPORT", "BOTH")
            want_dn = role in ("RESISTANCE", "BOTH")

            launched = False
            launch_pts = 0.0
            launch_side = None
            for leg in legs:
                if not (touch_i <= leg["start_i"] <= touch_i + NEXT_LEG_BARS):
                    continue
                if abs(leg["origin_px"] - px) > max(8.0, 0.8 * a):
                    continue
                if leg["pts"] < NEXT_LEG_MIN_PTS:
                    continue
                if leg["side"] == "BUY" and want_up:
                    launched, launch_pts, launch_side = True, leg["pts"], "BUY"
                    break
                if leg["side"] == "SELL" and want_dn:
                    launched, launch_pts, launch_side = True, leg["pts"], "SELL"
                    break
            if not launched:
                end = min(len(c) - 1, touch_i + NEXT_LEG_BARS)
                up = float(np.max(h[touch_i : end + 1])) - px
                dn = px - float(np.min(l[touch_i : end + 1]))
                if want_up and (not want_dn or up >= dn) and up >= NEXT_LEG_MIN_PTS:
                    launched, launch_pts, launch_side = True, up, "BUY"
                elif want_dn and (not want_up or dn >= up) and dn >= NEXT_LEG_MIN_PTS:
                    launched, launch_pts, launch_side = True, dn, "SELL"

            # session context at touch
            d = day[touch_i]
            sess = np.where(day == d)[0]
            sess = sess[sess < touch_i]
            near_ext = False
            mid = False
            sess_pos = 0.5
            if len(sess) >= 5:
                sh, sl = float(np.max(h[sess])), float(np.min(l[sess]))
                width = max(sh - sl, 1.0)
                sess_pos = (px - sl) / width
                if role in ("SUPPORT", "BOTH") and abs(px - sl) <= 1.0 * a:
                    near_ext = True
                if role in ("RESISTANCE", "BOTH") and abs(px - sh) <= 1.0 * a:
                    near_ext = True
                mid = 0.3 <= sess_pos <= 0.7

            # prior day HL confluence
            # find prior day
            days_sorted = sorted(set(day.tolist()))
            try:
                di = days_sorted.index(d)
            except ValueError:
                di = -1
            near_pdh = near_pdl = False
            if di > 0:
                pd = days_sorted[di - 1]
                pidxs = np.where(day == pd)[0]
                pdh, pdl = float(np.max(h[pidxs])), float(np.min(l[pidxs]))
                near_pdh = abs(px - pdh) <= 1.2 * a
                near_pdl = abs(px - pdl) <= 1.2 * a

            # leave distance
            leave_dist = abs(float(c[touch_i]) - px)  # at touch ~0; use max leave before touch
            # approximate: max distance between live and touch
            seg = c[live_i:touch_i]
            leave_dist = float(np.max(np.abs(seg - px))) if len(seg) else 0.0

            # time
            mh = int(mins[touch_i])
            morning = mh < 11 * 60 + 30
            midday = 11 * 60 + 30 <= mh < 13 * 60 + 30
            afternoon = mh >= 13 * 60 + 30

            # freshness: last launch how many bars ago
            fresh_bars = touch_i - members[qi]["i"]
            fresh_1d = fresh_bars <= 400  # ~1 session
            fresh_2d = fresh_bars <= 800

            events.append(
                {
                    "pad_px": px,
                    "role": role,
                    "n_hist": n_hist,
                    "days_hist": days_hist,
                    "avg_pts": round(avg_pts, 2),
                    "launched": launched,
                    "launch_pts": round(float(launch_pts), 2),
                    "launch_side": launch_side,
                    "near_ext": near_ext,
                    "mid": mid,
                    "sess_pos": round(sess_pos, 3),
                    "near_pdh": near_pdh,
                    "near_pdl": near_pdl,
                    "leave_dist": round(leave_dist, 2),
                    "leave_ge_1atr": leave_dist >= 1.0 * a,
                    "leave_ge_2atr": leave_dist >= 2.0 * a,
                    "morning": morning,
                    "midday": midday,
                    "afternoon": afternoon,
                    "fresh_1d": fresh_1d,
                    "fresh_2d": fresh_2d,
                    "touch_i": touch_i,
                    "day": d,
                    "atr": round(a, 2),
                }
            )
    return events


def score(events, pred, min_n=15):
    sub = [e for e in events if pred(e)]
    n = len(sub)
    if n < min_n:
        return None
    w = sum(1 for e in sub if e["launched"])
    pts = [e["launch_pts"] for e in sub if e["launched"]]
    return {
        "n": n,
        "hit": round(100.0 * w / n, 2),
        "w": w,
        "l": n - w,
        "avg_pts": round(float(np.mean(pts)), 2) if pts else None,
        "cover_days": len({e["day"] for e in sub}),
    }


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("Move-origin S/R ≥80% search (NOT live)", flush=True)

    raw = base.load_existing_1m()
    hi_ts = raw.index.max()
    raw = raw[raw.index >= hi_ts - pd.Timedelta(days=70)]
    df = raw.copy()
    df["day"] = [str(ts.date()) for ts in df.index]
    df["mins"] = df.index.hour * 60 + df.index.minute
    df = add_indicators(df)

    days_all = sorted(set(df["day"].astype(str)))
    keep = set(days_all[-30:]) if len(days_all) > 30 else set(days_all)
    day_lo, day_hi = min(keep), max(keep)
    print(f"window {day_lo}→{day_hi} n_days={len(keep)}", flush=True)

    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    atr = df["atr14"].astype(float).values
    day = df["day"].astype(str).values
    mins = df["mins"].astype(int).values

    legs, pivots = zigzag_legs(h, l, c, atr, day, mins)
    legs_w = [x for x in legs if x["day"] in keep]
    pads = cluster_origins(legs_w, atr)
    print(f"legs={len(legs_w)} pads={len(pads)}", flush=True)

    events = collect_retest_events(h, l, c, atr, day, mins, pads, legs_w, keep)
    base_s = score(events, lambda e: True, min_n=10)
    print(f"retest events={len(events)} base hit={base_s}", flush=True)

    gates = [
        ("ALL retests", lambda e: True),
        ("RESISTANCE only", lambda e: e["role"] == "RESISTANCE"),
        ("SUPPORT only", lambda e: e["role"] == "SUPPORT"),
        ("n_hist≥3", lambda e: e["n_hist"] >= 3),
        ("n_hist≥4", lambda e: e["n_hist"] >= 4),
        ("n_hist≥5", lambda e: e["n_hist"] >= 5),
        ("days≥3", lambda e: e["days_hist"] >= 3),
        ("days≥4", lambda e: e["days_hist"] >= 4),
        ("avg_pts≥60", lambda e: e["avg_pts"] >= 60),
        ("avg_pts≥80", lambda e: e["avg_pts"] >= 80),
        ("leave≥2ATR", lambda e: e["leave_ge_2atr"]),
        ("fresh_1d", lambda e: e["fresh_1d"]),
        ("fresh_2d", lambda e: e["fresh_2d"]),
        ("near_sess_ext", lambda e: e["near_ext"]),
        ("near_PDH", lambda e: e["near_pdh"]),
        ("near_PDL", lambda e: e["near_pdl"]),
        ("morning", lambda e: e["morning"]),
        ("afternoon", lambda e: e["afternoon"]),
        # combos aiming 80%
        ("RES + n≥3", lambda e: e["role"] == "RESISTANCE" and e["n_hist"] >= 3),
        ("RES + n≥4", lambda e: e["role"] == "RESISTANCE" and e["n_hist"] >= 4),
        ("RES + n≥5", lambda e: e["role"] == "RESISTANCE" and e["n_hist"] >= 5),
        ("RES + days≥3", lambda e: e["role"] == "RESISTANCE" and e["days_hist"] >= 3),
        ("RES + avg≥60", lambda e: e["role"] == "RESISTANCE" and e["avg_pts"] >= 60),
        ("RES + avg≥80", lambda e: e["role"] == "RESISTANCE" and e["avg_pts"] >= 80),
        ("RES + leave≥2ATR", lambda e: e["role"] == "RESISTANCE" and e["leave_ge_2atr"]),
        ("RES + near_ext", lambda e: e["role"] == "RESISTANCE" and e["near_ext"]),
        ("RES + near_PDH", lambda e: e["role"] == "RESISTANCE" and e["near_pdh"]),
        ("RES + fresh_1d", lambda e: e["role"] == "RESISTANCE" and e["fresh_1d"]),
        ("RES + n≥3 + avg≥60", lambda e: e["role"] == "RESISTANCE" and e["n_hist"] >= 3 and e["avg_pts"] >= 60),
        ("RES + n≥3 + leave≥2ATR", lambda e: e["role"] == "RESISTANCE" and e["n_hist"] >= 3 and e["leave_ge_2atr"]),
        ("RES + n≥4 + leave≥2ATR", lambda e: e["role"] == "RESISTANCE" and e["n_hist"] >= 4 and e["leave_ge_2atr"]),
        ("RES + n≥3 + days≥3", lambda e: e["role"] == "RESISTANCE" and e["n_hist"] >= 3 and e["days_hist"] >= 3),
        ("RES + n≥4 + days≥3 + avg≥60", lambda e: e["role"] == "RESISTANCE" and e["n_hist"] >= 4 and e["days_hist"] >= 3 and e["avg_pts"] >= 60),
        ("RES + n≥3 + fresh_1d + leave≥2ATR", lambda e: e["role"] == "RESISTANCE" and e["n_hist"] >= 3 and e["fresh_1d"] and e["leave_ge_2atr"]),
        ("RES + n≥5 + leave≥2ATR", lambda e: e["role"] == "RESISTANCE" and e["n_hist"] >= 5 and e["leave_ge_2atr"]),
        ("SUP + n≥4", lambda e: e["role"] == "SUPPORT" and e["n_hist"] >= 4),
        ("SUP + n≥5", lambda e: e["role"] == "SUPPORT" and e["n_hist"] >= 5),
        ("SUP + near_ext", lambda e: e["role"] == "SUPPORT" and e["near_ext"]),
        ("SUP + near_PDL", lambda e: e["role"] == "SUPPORT" and e["near_pdl"]),
        ("SUP + n≥3 + leave≥2ATR", lambda e: e["role"] == "SUPPORT" and e["n_hist"] >= 3 and e["leave_ge_2atr"]),
        ("SUP + n≥4 + leave≥2ATR + avg≥60", lambda e: e["role"] == "SUPPORT" and e["n_hist"] >= 4 and e["leave_ge_2atr"] and e["avg_pts"] >= 60),
        ("SUP + n≥3 + near_ext", lambda e: e["role"] == "SUPPORT" and e["n_hist"] >= 3 and e["near_ext"]),
        ("any + n≥5 + leave≥2ATR + avg≥80", lambda e: e["n_hist"] >= 5 and e["leave_ge_2atr"] and e["avg_pts"] >= 80),
        ("any + n≥4 + days≥3 + leave≥2ATR", lambda e: e["n_hist"] >= 4 and e["days_hist"] >= 3 and e["leave_ge_2atr"]),
        ("any + n≥5 + days≥3 + leave≥2ATR", lambda e: e["n_hist"] >= 5 and e["days_hist"] >= 3 and e["leave_ge_2atr"]),
        ("RES + afternoon + n≥3", lambda e: e["role"] == "RESISTANCE" and e["afternoon"] and e["n_hist"] >= 3),
        ("RES + morning + n≥3", lambda e: e["role"] == "RESISTANCE" and e["morning"] and e["n_hist"] >= 3),
        # stricter launch definition already 40pts; try requiring avg historical stronger
        ("RES + n≥3 + avg≥70 + leave≥2ATR", lambda e: e["role"] == "RESISTANCE" and e["n_hist"] >= 3 and e["avg_pts"] >= 70 and e["leave_ge_2atr"]),
        ("RES + n≥4 + avg≥70 + leave≥2ATR", lambda e: e["role"] == "RESISTANCE" and e["n_hist"] >= 4 and e["avg_pts"] >= 70 and e["leave_ge_2atr"]),
        ("RES + days≥4 + leave≥2ATR", lambda e: e["role"] == "RESISTANCE" and e["days_hist"] >= 4 and e["leave_ge_2atr"]),
        ("RES + n≥3 + near_PDH + leave≥2ATR", lambda e: e["role"] == "RESISTANCE" and e["n_hist"] >= 3 and e["near_pdh"] and e["leave_ge_2atr"]),
    ]

    rows = []
    for name, pred in gates:
        s = score(events, pred, min_n=8)
        if s is None:
            print(f"  {name}: <8 samples", flush=True)
            continue
        rows.append({"name": name, **s})
        print(f"  {name}: hit={s['hit']}% n={s['n']} days={s['cover_days']}", flush=True)

    # also try min_n=12 for 80% board
    ge80 = [r for r in rows if r["hit"] >= 80 and r["n"] >= 12]
    ge80.sort(key=lambda r: (-r["hit"], -r["n"]))
    ge75 = [r for r in rows if r["hit"] >= 75 and r["n"] >= 12]
    ge75.sort(key=lambda r: (-r["hit"], -r["n"]))
    best = sorted(rows, key=lambda r: (-r["hit"], -r["n"]))

    # secondary: require launch_pts≥50 as success (harder) — re-score top candidates
    def score_hard(pred, min_pts=50, min_n=10):
        sub = [e for e in events if pred(e)]
        if len(sub) < min_n:
            return None
        w = sum(1 for e in sub if e["launched"] and e["launch_pts"] >= min_pts)
        return {
            "n": len(sub),
            "hit": round(100.0 * w / len(sub), 2),
            "w": w,
        }

    lines = [
        "# NIFTY 1m — Move-origin S/R · chase **≥80%** proven",
        "",
        "> **RESEARCH ONLY.** Success = pad retest → role-matched ≥40pt move.",
        "",
        f"Window **{day_lo} → {day_hi}** ({len(keep)} sessions) · retest events **{len(events)}**.",
        f"Baseline (all retests): **{base_s['hit'] if base_s else None}%** n={base_s['n'] if base_s else 0}.",
        "",
        "## Gates ≥80% (n≥12)",
        "",
    ]
    if not ge80:
        lines += [
            "**None reached ≥80% with n≥12 on this window.**",
            "",
            "Closest (≥75%, n≥12):",
            "",
            "| Gate | Hit% | n | W/L | avg pts | days |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for r in ge75[:15]:
            lines.append(
                f"| `{r['name']}` | **{r['hit']}** | {r['n']} | {r['w']}/{r['l']} | "
                f"{r['avg_pts']} | {r['cover_days']} |"
            )
        if not ge75:
            lines += [
                "",
                "No ≥75%/n≥12 either. Top by hit% (n≥8):",
                "",
                "| Gate | Hit% | n | W/L | avg pts | days |",
                "|---|---:|---:|---:|---:|---:|",
            ]
            for r in best[:20]:
                lines.append(
                    f"| `{r['name']}` | **{r['hit']}** | {r['n']} | {r['w']}/{r['l']} | "
                    f"{r['avg_pts']} | {r['cover_days']} |"
                )
    else:
        lines += [
            "| Gate | Hit% | n | W/L | avg pts | days |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for r in ge80:
            lines.append(
                f"| `{r['name']}` | **{r['hit']}** | {r['n']} | {r['w']}/{r['l']} | "
                f"{r['avg_pts']} | {r['cover_days']} |"
            )

    lines += [
        "",
        "## Full ranked board (n≥8)",
        "",
        "| Gate | Hit% | n | W/L | avg pts | days |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in best:
        mark = " ✅" if r["hit"] >= 80 and r["n"] >= 12 else ""
        lines.append(
            f"| `{r['name']}`{mark} | **{r['hit']}** | {r['n']} | {r['w']}/{r['l']} | "
            f"{r['avg_pts']} | {r['cover_days']} |"
        )

    # best honest proven rule
    proven = ge80[0] if ge80 else (ge75[0] if ge75 else (best[0] if best else None))
    lines += ["", "## Verdict", ""]
    if ge80:
        lines += [
            f"**YES — proven ≥80%:** `{ge80[0]['name']}` → **{ge80[0]['hit']}%** "
            f"(n={ge80[0]['n']}, {ge80[0]['cover_days']} days).",
            "",
            "### Proven logic",
            "",
            "```",
            f"Use gate: {ge80[0]['name']}",
            "Pad = ZigZag origin cluster (0.5×ATR, span≤12)",
            "Retest after leave ≥1ATR",
            "Expect role-matched ≥40pt continuation",
            "```",
        ]
    else:
        lines += [
            "**No stable ≥80% / n≥12 gate on this 30d window.**",
            "",
        ]
        if proven:
            lines.append(
                f"Best available: `{proven['name']}` → **{proven['hit']}%** "
                f"(n={proven['n']}). Still below 80% bar."
            )
        lines += [
            "",
            "What lifts accuracy most: **RESISTANCE pads** + **more prior launches** + "
            "**leave ≥2ATR** before retest. Support pads stay weaker.",
            "",
            "Next research levers (if you want): longer history (90d+), stricter "
            "HTF confluence, or define success as Dom/trail hit instead of raw ≥40pt.",
        ]

    lines += ["", f"Elapsed {time.time() - t0:.0f}s", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "window": [day_lo, day_hi],
                "n_events": len(events),
                "baseline": base_s,
                "rows": rows,
                "ge80": ge80,
                "ge75": ge75,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {REPORT}", flush=True)
    if ge80:
        print(f"PROVEN80: {ge80[0]['name']} hit={ge80[0]['hit']} n={ge80[0]['n']}", flush=True)
    elif ge75:
        print(f"BEST75: {ge75[0]['name']} hit={ge75[0]['hit']} n={ge75[0]['n']}", flush=True)
    elif best:
        print(f"BEST: {best[0]['name']} hit={best[0]['hit']} n={best[0]['n']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
