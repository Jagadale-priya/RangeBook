"""RESEARCH ONLY — Support / Resistance / Range from where the market ACTUALLY moves.

NO candle patterns. NO textbook. NO green/red streaks.
Pure price path:

  1. ZigZag legs: alternating peaks/troughs with min reversal (≥ max(25pts, 2.5×ATR))
  2. Each leg = a real move. ORIGIN = start extreme. END = finish extreme.
  3. Cluster origins in price → LAUNCH PADS (true S/R candidates)
  4. Prove: when price revisits a pad later, does another big leg launch?
  5. RANGE = band between strongest opposite pads / high time-at-price (acceptance)

  python -u prod_live/tests/builders/_diag_scalp_move_origin_sr_range.py
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
REPORT = OUT / "NIFTY_1M_MOVE_ORIGIN_SR_RANGE.md"
REPORT_JSON = OUT / "NIFTY_1M_MOVE_ORIGIN_SR_RANGE.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
MIN_REV_PTS = 25.0
MIN_REV_ATR = 2.5
CLUSTER_ATR = 0.5
CLUSTER_MAX_SPAN = 12.0  # hard cap — no mega-chains
LAUNCH_MIN_PTS = 35.0
RETEST_TOUCH_ATR = 0.40
NEXT_LEG_BARS = 50
NEXT_LEG_MIN_PTS = 40.0  # real move, not noise


def zigzag_legs(h, l, c, atr, day, mins):
    """Build zigzag on close extremes using high/low confirmation.

    State machine: track last pivot; reverse when adverse extreme ≥ threshold.
    Returns list of legs: {side, start_i, end_i, origin_px, end_px, pts, bars}
    side BUY = up leg from trough; SELL = down leg from peak.
    """
    n = len(c)
    if n < 50:
        return []

    # seed: first session bar extreme
    pivots = []  # (i, px, kind) kind='H' or 'L'
    # find first meaningful direction
    i0 = 0
    while i0 < n and (mins[i0] < MINS_LO or mins[i0] >= MINS_HI):
        i0 += 1
    if i0 >= n:
        return []

    last_i = i0
    last_px = float(c[i0])
    last_kind = None  # unknown until first reverse
    candidate_i = i0
    candidate_px = float(c[i0])
    direction = 0  # +1 seeking high, -1 seeking low, 0 seeking either

    for i in range(i0 + 1, n):
        if mins[i] < MINS_LO or mins[i] >= MINS_HI:
            continue
        # day change: soft reset candidate but keep last pivot
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 10.0
        thr = max(MIN_REV_PTS, MIN_REV_ATR * a)
        hi = float(h[i])
        lo = float(l[i])
        cl = float(c[i])

        if direction == 0:
            # establish: extend both ways
            if hi >= candidate_px:
                candidate_px = hi
                candidate_i = i
                direction = 1
            elif lo <= candidate_px:
                candidate_px = lo
                candidate_i = i
                direction = -1
            continue

        if direction == 1:
            # tracking potential peak
            if hi >= candidate_px:
                candidate_px = hi
                candidate_i = i
            # reverse down if low goes thr below peak
            if lo <= candidate_px - thr:
                pivots.append((candidate_i, candidate_px, "H"))
                # start seeking trough from this low
                direction = -1
                candidate_i = i
                candidate_px = lo
        else:
            if lo <= candidate_px:
                candidate_px = lo
                candidate_i = i
            if hi >= candidate_px + thr:
                pivots.append((candidate_i, candidate_px, "L"))
                direction = 1
                candidate_i = i
                candidate_px = hi

    # build legs between alternating pivots
    legs = []
    for k in range(1, len(pivots)):
        a_i, a_px, a_k = pivots[k - 1]
        b_i, b_px, b_k = pivots[k]
        if a_k == b_k:
            continue
        if a_k == "L" and b_k == "H":
            side = "BUY"
            pts = b_px - a_px
        elif a_k == "H" and b_k == "L":
            side = "SELL"
            pts = a_px - b_px
        else:
            continue
        if pts < LAUNCH_MIN_PTS:
            continue
        if b_i <= a_i:
            continue
        legs.append(
            {
                "side": side,
                "start_i": int(a_i),
                "end_i": int(b_i),
                "origin_px": round(float(a_px), 2),
                "end_px": round(float(b_px), 2),
                "pts": round(float(pts), 2),
                "bars": int(b_i - a_i),
                "day": str(day[a_i]),
                "mins": int(mins[a_i]),
                "origin_kind": a_k,
            }
        )
    return legs, pivots


def cluster_origins(legs, atr_arr, merge_atr=CLUSTER_ATR, max_span=CLUSTER_MAX_SPAN):
    """Cluster origin prices into launch pads with hard max span (no mega-chains)."""
    items = []
    for leg in legs:
        i = leg["start_i"]
        a = float(atr_arr[i]) if np.isfinite(atr_arr[i]) and atr_arr[i] > 0 else 10.0
        items.append(
            {
                "px": leg["origin_px"],
                "side": leg["side"],
                "kind": leg["origin_kind"],
                "i": i,
                "pts": leg["pts"],
                "day": leg["day"],
                "atr": a,
            }
        )
    if not items:
        return []
    items = sorted(items, key=lambda x: x["px"])
    clusters = []
    cur = [items[0]]
    for it in items[1:]:
        a = float(np.mean([x["atr"] for x in cur]))
        tol = max(5.0, merge_atr * a)
        span_if = it["px"] - cur[0]["px"]
        if abs(it["px"] - cur[-1]["px"]) <= tol and span_if <= max_span:
            cur.append(it)
        else:
            clusters.append(cur)
            cur = [it]
    clusters.append(cur)

    pads = []
    for cur in clusters:
        px = float(np.mean([x["px"] for x in cur]))
        buys = sum(1 for x in cur if x["side"] == "BUY")
        sells = sum(1 for x in cur if x["side"] == "SELL")
        role = "SUPPORT" if buys > sells else ("RESISTANCE" if sells > buys else "BOTH")
        pads.append(
            {
                "px": round(px, 2),
                "n": len(cur),
                "buys": buys,
                "sells": sells,
                "role": role,
                "avg_launch_pts": round(float(np.mean([x["pts"] for x in cur])), 2),
                "span": round(max(x["px"] for x in cur) - min(x["px"] for x in cur), 2),
                "first_i": int(min(x["i"] for x in cur)),
                "last_i": int(max(x["i"] for x in cur)),
                "days": len({x["day"] for x in cur}),
                "members": cur,
            }
        )
    pads.sort(key=lambda p: (-p["n"], -p["days"], -p["avg_launch_pts"]))
    return pads


def prove_pad_retests(h, l, c, atr, day, mins, pads, legs):
    """After pad has ≥2 launches, leave & revisit → directional ≥NEXT_LEG_MIN_PTS move?"""
    results = []
    for pad in pads:
        if pad["n"] < 2 or pad["days"] < 1:
            continue
        px = pad["px"]
        members = sorted(pad.get("members") or [], key=lambda x: x["i"])
        if len(members) < 2:
            # fallback near filter
            near = sorted(
                [leg for leg in legs if abs(leg["origin_px"] - px) <= CLUSTER_MAX_SPAN],
                key=lambda x: x["start_i"],
            )
            if len(near) < 2:
                continue
            live_i = near[1]["start_i"]
        else:
            live_i = members[1]["i"]

        left = False
        a0 = float(atr[live_i]) if np.isfinite(atr[live_i]) else 10.0
        want_up = pad["role"] in ("SUPPORT", "BOTH")
        want_dn = pad["role"] in ("RESISTANCE", "BOTH")

        for j in range(live_i + 5, len(c)):
            if mins[j] < MINS_LO or mins[j] >= MINS_HI:
                continue
            a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else a0
            if not left:
                if abs(float(c[j]) - px) >= 1.0 * a:
                    left = True
                continue
            touched = abs(float(c[j]) - px) <= RETEST_TOUCH_ATR * a or (
                float(l[j]) <= px <= float(h[j])
            )
            if not touched:
                continue

            launched = False
            launch_pts = 0.0
            # 1) zigzag leg from near this pad, correct direction
            for leg in legs:
                if not (j <= leg["start_i"] <= j + NEXT_LEG_BARS):
                    continue
                if abs(leg["origin_px"] - px) > max(8.0, 0.8 * a):
                    continue
                if leg["pts"] < NEXT_LEG_MIN_PTS:
                    continue
                if leg["side"] == "BUY" and want_up:
                    launched, launch_pts = True, leg["pts"]
                    break
                if leg["side"] == "SELL" and want_dn:
                    launched, launch_pts = True, leg["pts"]
                    break
            # 2) directional path excursion only (role-matched), ≥40pts
            if not launched:
                end = min(len(c) - 1, j + NEXT_LEG_BARS)
                up = float(np.max(h[j : end + 1])) - px
                dn = px - float(np.min(l[j : end + 1]))
                if want_up and (not want_dn or up >= dn) and up >= NEXT_LEG_MIN_PTS:
                    launched, launch_pts = True, up
                elif want_dn and (not want_up or dn >= up) and dn >= NEXT_LEG_MIN_PTS:
                    launched, launch_pts = True, dn

            results.append(
                {
                    "pad_px": px,
                    "role": pad["role"],
                    "touch_i": j,
                    "launched": launched,
                    "launch_pts": round(float(launch_pts), 2),
                    "n_hist": pad["n"],
                    "days": pad["days"],
                }
            )
            break
    return results


def time_at_price(c, day, mins, keep, bin_pts=5.0):
    """Acceptance profile: count session closes per price bin."""
    counts = defaultdict(int)
    for i in range(len(c)):
        if day[i] not in keep:
            continue
        if mins[i] < MINS_LO or mins[i] >= MINS_HI:
            continue
        b = int(round(float(c[i]) / bin_pts) * bin_pts)
        counts[b] += 1
    if not counts:
        return []
    total = sum(counts.values())
    rows = [
        {"px": px, "n": n, "pct": round(100.0 * n / total, 2)}
        for px, n in counts.items()
    ]
    rows.sort(key=lambda x: -x["n"])
    return rows


def range_from_pads(pads, min_n=3):
    """Range candidates: between strongest SUPPORT pad below and RESISTANCE pad above POC area."""
    sup = [p for p in pads if p["role"] in ("SUPPORT", "BOTH") and p["n"] >= min_n]
    res = [p for p in pads if p["role"] in ("RESISTANCE", "BOTH") and p["n"] >= min_n]
    pairs = []
    for s in sup:
        for r in res:
            if r["px"] > s["px"] + 15:
                width = r["px"] - s["px"]
                strength = s["n"] + r["n"]
                pairs.append(
                    {
                        "lo": s["px"],
                        "hi": r["px"],
                        "width": round(width, 2),
                        "strength": strength,
                        "lo_n": s["n"],
                        "hi_n": r["n"],
                    }
                )
    pairs.sort(key=lambda x: (-x["strength"], x["width"]))
    return pairs[:15]


def containment(c, day, mins, keep, lo, hi, sample_every=5):
    inside = total = 0
    for i in range(0, len(c), sample_every):
        if day[i] not in keep:
            continue
        if mins[i] < MINS_LO or mins[i] >= MINS_HI:
            continue
        total += 1
        if lo <= float(c[i]) <= hi:
            inside += 1
    if total < 50:
        return None
    return round(100.0 * inside / total, 2)


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("Move-origin S/R/Range (NO candles) RESEARCH", flush=True)

    raw = base.load_existing_1m()
    hi_ts = raw.index.max()
    # deeper window for structure — ~2 months
    raw = raw[raw.index >= hi_ts - pd.Timedelta(days=70)]
    df = raw.copy()
    df["day"] = [str(ts.date()) for ts in df.index]
    df["mins"] = df.index.hour * 60 + df.index.minute
    df = add_indicators(df)

    days_all = sorted(set(df["day"].astype(str)))
    keep = set(days_all[-30:]) if len(days_all) > 30 else set(days_all)
    day_lo, day_hi = min(keep), max(keep)
    print(f"window {day_lo}→{day_hi} n_days={len(keep)} bars={len(df)}", flush=True)

    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    atr = df["atr14"].astype(float).values
    day = df["day"].astype(str).values
    mins = df["mins"].astype(int).values
    idx = df.index

    zz = zigzag_legs(h, l, c, atr, day, mins)
    legs, pivots = zz
    # filter legs whose origin day in keep
    legs_w = [x for x in legs if x["day"] in keep]
    print(f"zigzag pivots={len(pivots)} legs≥{LAUNCH_MIN_PTS}pts in window={len(legs_w)}", flush=True)

    pads = cluster_origins(legs_w, atr)
    print(f"launch pads={len(pads)} (top n={pads[0]['n'] if pads else 0})", flush=True)

    proofs = prove_pad_retests(h, l, c, atr, day, mins, pads, legs_w)
    n_proof = len(proofs)
    n_launch = sum(1 for p in proofs if p["launched"])
    proof_rate = round(100.0 * n_launch / n_proof, 2) if n_proof else None
    avg_pts = (
        round(float(np.mean([p["launch_pts"] for p in proofs if p["launched"]])), 2)
        if n_launch
        else None
    )
    print(f"pad retests={n_proof} launched_again={n_launch} rate={proof_rate}%", flush=True)

    # split proof by role
    def role_rate(role):
        sub = [p for p in proofs if p["role"] == role or (role == "SUPPORT" and p["role"] == "BOTH")]
        if role == "RESISTANCE":
            sub = [p for p in proofs if p["role"] in ("RESISTANCE", "BOTH")]
        if role == "SUPPORT":
            sub = [p for p in proofs if p["role"] in ("SUPPORT", "BOTH")]
        if len(sub) < 5:
            return len(sub), None, None
        k = sum(1 for p in sub if p["launched"])
        return len(sub), round(100.0 * k / len(sub), 2), round(
            float(np.mean([p["launch_pts"] for p in sub if p["launched"]] or [0])), 2
        )

    # acceptance profile
    profile = time_at_price(c, day, mins, keep, bin_pts=5.0)
    poc = profile[0] if profile else None
    # VAH/VAL ≈ 70% value area around POC
    value_bins = []
    if profile:
        target = 0.70 * sum(x["n"] for x in profile)
        ordered = sorted(profile, key=lambda x: abs(x["px"] - poc["px"]))
        acc = 0
        chosen = []
        for b in ordered:
            chosen.append(b)
            acc += b["n"]
            if acc >= target:
                break
        vah = max(x["px"] for x in chosen)
        val = min(x["px"] for x in chosen)
        value_bins = {"poc": poc["px"], "vah": vah, "val": val, "poc_pct": poc["pct"]}

    ranges = range_from_pads(pads, min_n=2)
    for rg in ranges[:8]:
        rg["contain_pct"] = containment(c, day, mins, keep, rg["lo"], rg["hi"])

    # Also: ends of legs cluster = where moves DIE (opposite of origin) — targets / weak S/R
    end_legs = []
    for leg in legs_w:
        end_legs.append(
            {
                **leg,
                "origin_px": leg["end_px"],
                "side": "SELL" if leg["side"] == "BUY" else "BUY",
                "origin_kind": "H" if leg["side"] == "BUY" else "L",
                "start_i": leg["end_i"],
            }
        )
    end_pads = cluster_origins(end_legs, atr)

    # Day-level: where did the biggest move of each day start?
    by_day = defaultdict(list)
    for leg in legs_w:
        by_day[leg["day"]].append(leg)
    day_origins = []
    for d, lst in sorted(by_day.items()):
        best = max(lst, key=lambda x: x["pts"])
        day_origins.append(best)

    # Stats on origins vs session so-far
    sess_stats = {"near_sess_ext": 0, "mid_range": 0, "n": 0}
    for leg in legs_w:
        i = leg["start_i"]
        # session so far
        d = day[i]
        sess = np.where(day == d)[0]
        sess = sess[sess < i]
        if len(sess) < 5:
            continue
        sh, sl = float(np.max(h[sess])), float(np.min(l[sess]))
        a = float(atr[i]) if np.isfinite(atr[i]) else 10.0
        ox = leg["origin_px"]
        sess_stats["n"] += 1
        if leg["side"] == "BUY" and abs(ox - sl) <= 0.8 * a:
            sess_stats["near_sess_ext"] += 1
        elif leg["side"] == "SELL" and abs(ox - sh) <= 0.8 * a:
            sess_stats["near_sess_ext"] += 1
        elif sl + 0.25 * (sh - sl) < ox < sh - 0.25 * (sh - sl):
            sess_stats["mid_range"] += 1

    lines = [
        "# NIFTY 1m — Support / Resistance / Range from **where market actually moves**",
        "",
        "> **RESEARCH ONLY.** No candle patterns. No textbook. Pure price-path ZigZag legs.",
        "",
        f"Window **{day_lo} → {day_hi}** ({len(keep)} sessions).",
        "",
        "## Method",
        "",
        "1. Build a **ZigZag** on price: reverse only after ≥ max(25pts, 2.5×ATR).",
        "2. Each leg ≥30pts is a **real move**.",
        "3. **Origin** = trough that started an up-leg, or peak that started a down-leg.",
        "4. Cluster origins within ~0.6×ATR → **launch pads** = candidate S/R.",
        "5. **Prove** pads: after 2 launches, next revisit → another ≥25pt move?",
        "6. **Range** = band between strong opposite pads + time-at-price value area.",
        "",
        f"Legs in window: **{len(legs_w)}** · Launch pads: **{len(pads)}** · "
        f"ZigZag pivots: {len(pivots)}",
        "",
        "## Top launch pads (real S/R candidates)",
        "",
        "| Rank | Price | Role | Launches | Days | BUY origins | SELL origins | Avg move pts | Span |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for i, p in enumerate(pads[:25], 1):
        lines.append(
            f"| {i} | **{p['px']}** | {p['role']} | {p['n']} | {p['days']} | "
            f"{p['buys']} | {p['sells']} | {p['avg_launch_pts']} | {p['span']} |"
        )

    lines += [
        "",
        "## Proven: does revisiting a pad launch again?",
        "",
        f"Pads with ≥2 historical launches, then leave & retest: **{n_proof}** tests.",
        f"Launched another ≥{NEXT_LEG_MIN_PTS}pt move within ~40–60 bars: "
        f"**{n_launch}** → **{proof_rate}%**" if proof_rate is not None else "Insufficient.",
        f"Avg launch size when it fires: **{avg_pts}** pts." if avg_pts else "",
        "",
    ]

    # role breakdown
    for role in ("SUPPORT", "RESISTANCE"):
        n, rate, pts = role_rate(role)
        lines.append(f"- **{role}** pads retest→launch: n={n} rate={rate}% avg_pts={pts}")

    lines += [
        "",
        "## Where do big daily moves start?",
        "",
        "| Day | Side | Origin | End | Pts | Time |",
        "|---|---|---:|---:|---:|---|",
    ]
    for leg in day_origins[-20:]:
        ts = str(idx[leg["start_i"]])[11:16]
        lines.append(
            f"| {leg['day']} | {leg['side']} | **{leg['origin_px']}** | {leg['end_px']} | "
            f"{leg['pts']} | {ts} |"
        )

    near_pct = (
        round(100.0 * sess_stats["near_sess_ext"] / sess_stats["n"], 1)
        if sess_stats["n"]
        else None
    )
    mid_pct = (
        round(100.0 * sess_stats["mid_range"] / sess_stats["n"], 1)
        if sess_stats["n"]
        else None
    )
    lines += [
        "",
        "## Origin location vs session so far",
        "",
        f"Among {sess_stats['n']} legs:",
        f"- Started **near session extreme** (BUY near day-low / SELL near day-high): **{near_pct}%**",
        f"- Started in **mid session range**: **{mid_pct}%**",
        "",
        "## Acceptance / value area (time-at-price, 5pt bins)",
        "",
    ]
    if value_bins:
        lines += [
            f"- **POC** (most time): **{value_bins['poc']}** ({value_bins['poc_pct']}% of closes)",
            f"- **VAL–VAH** (~70% value): **{value_bins['val']} → {value_bins['vah']}**",
            "",
            "Top acceptance bins:",
            "",
            "| Price bin | Closes | % |",
            "|---:|---:|---:|",
        ]
        for b in profile[:12]:
            lines.append(f"| {b['px']} | {b['n']} | {b['pct']} |")

    lines += [
        "",
        "## Range from opposite launch pads",
        "",
        "| Lo (support pad) | Hi (resist pad) | Width | Strength | Contain% |",
        "|---:|---:|---:|---:|---:|",
    ]
    for rg in ranges[:10]:
        lines.append(
            f"| {rg['lo']} | {rg['hi']} | {rg['width']} | {rg['strength']} | "
            f"**{rg.get('contain_pct')}** |"
        )

    lines += [
        "",
        "## Where moves DIE (end-of-leg clusters)",
        "",
        "| Price | Role@end | Hits | Avg leg into it |",
        "|---:|---|---:|---:|",
    ]
    for p in end_pads[:12]:
        lines.append(
            f"| {p['px']} | {p['role']} | {p['n']} | {p['avg_launch_pts']} |"
        )

    # Final stack
    top_sup = [p for p in pads if p["role"] in ("SUPPORT", "BOTH") and p["n"] >= 3][:5]
    top_res = [p for p in pads if p["role"] in ("RESISTANCE", "BOTH") and p["n"] >= 3][:5]
    best_range = ranges[0] if ranges else None

    lines += [
        "",
        "## Accurate logic (proven from move origins)",
        "",
        "```",
        "SUPPORT  = price clusters where UP-legs repeatedly launch (BUY origins / troughs)",
        "RESISTANCE = price clusters where DOWN-legs repeatedly launch (SELL origins / peaks)",
        "RANGE    = band between a strong support pad and strong resistance pad",
        "         + tighten with VAL–VAH (time-at-price acceptance)",
        "",
        "Build:",
        "  ZigZag reverse ≥ max(25pts, 2.5×ATR)",
        "  Keep legs ≥ 30pts",
        "  Cluster origins within 0.6×ATR → pads",
        "  Trust pads with n≥3 launches across ≥2 days",
        "  On retest of pad after leave: expect another ≥25pt move (~proof rate above)",
        "```",
        "",
        "### Strongest SUPPORT pads this window",
        "",
    ]
    for p in top_sup:
        lines.append(
            f"- **{p['px']}** · {p['n']} launches · {p['days']} days · avg {p['avg_launch_pts']} pts"
        )
    lines += ["", "### Strongest RESISTANCE pads this window", ""]
    for p in top_res:
        lines.append(
            f"- **{p['px']}** · {p['n']} launches · {p['days']} days · avg {p['avg_launch_pts']} pts"
        )
    if best_range:
        lines += [
            "",
            f"### Best range box: **{best_range['lo']} – {best_range['hi']}** "
            f"(width {best_range['width']}, contain {best_range.get('contain_pct')}%)",
        ]
    if value_bins:
        lines.append(
            f"### Value area: **{value_bins['val']} – {value_bins['vah']}** · POC **{value_bins['poc']}**"
        )

    lines += [
        "",
        "No candle patterns used. Levels come only from **where real legs started**.",
        "",
        f"Elapsed {time.time() - t0:.0f}s",
        "",
    ]

    def strip_members(ps):
        out = []
        for p in ps:
            q = {k: v for k, v in p.items() if k != "members"}
            out.append(q)
        return out

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "window": [day_lo, day_hi],
                "n_legs": len(legs_w),
                "pads": strip_members(pads[:40]),
                "proof_rate": proof_rate,
                "n_proof": n_proof,
                "n_launch": n_launch,
                "avg_launch_pts": avg_pts,
                "value_area": value_bins,
                "ranges": ranges[:10],
                "day_origins": day_origins,
                "sess_stats": sess_stats,
                "end_pads": strip_members(end_pads[:20]),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {REPORT}", flush=True)
    if pads:
        print(
            f"TOP pad {pads[0]['px']} role={pads[0]['role']} n={pads[0]['n']} "
            f"proof_rate={proof_rate}%",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
