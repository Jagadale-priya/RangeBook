"""Support/Resistance filter on HELD entries — skip trades into a wall.

Idea: entry can be valid on candle+gates, but nearby opposing S/R blocks T1.
  BUY  blocked if resistance within room (cannot go up in favor)
  SELL blocked if support within room (cannot go down in favor)
Also test bounce: BUY near support / SELL near resistance.

S/R sources (no lookahead — only bars < entry):
  - swing pivots (L-bar fractal highs/lows)
  - session: day open, prior day H/L/C
  - VWAP (soft)

Exit baseline: EMA34 trail · T1=12 (+ optional ratchet_arm12_gb8)

  python -u prod_live/tests/builders/_diag_scalp_ma_hold100_sr_filter.py
"""
from __future__ import annotations

import json
import pickle
import sys
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
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
import research_nifty_1m_vix_candle_adaptive as vixmod  # noqa: E402
import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import enrich_prior3  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402
from _diag_scalp_ma_lastyear_init import WIN_LO, PACK, add_ma_layers, enrich_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_HELD_SR_FILTER.md"
REPORT_JSON = OUT / "NIFTY_1M_HELD_SR_FILTER.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
T1 = 12.0
MAX_BARS = 120
PIVOT_L = 3  # fractal half-width
LOOK_BARS = 120  # ~2h of pivots behind entry


def in_session(e) -> bool:
    return MINS_LO <= int(e["mins"]) < MINS_HI


def path_fixed_t1(h, l, c, ma, i, side, t1_pts, max_bars=MAX_BARS):
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    if side == "BUY":
        t1 = entry + t1_pts
        for j in range(i + 1, end + 1):
            hi, cl, m = float(h[j]), float(c[j]), float(ma[j])
            if hi >= t1:
                return True, "t1", float(t1_pts)
            if cl < m:
                return False, "ma_sl", cl - entry
        return False, "exp", float(c[end]) - entry
    t1 = entry - t1_pts
    for j in range(i + 1, end + 1):
        lo, cl, m = float(l[j]), float(c[j]), float(ma[j])
        if lo <= t1:
            return True, "t1", float(t1_pts)
        if cl > m:
            return False, "ma_sl", entry - cl
    return False, "exp", entry - float(c[end])


def path_ratchet(h, l, c, ma, i, side, floor=12.0, giveback=8.0, max_bars=MAX_BARS):
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    armed, peak = False, 0.0
    if side == "BUY":
        for j in range(i + 1, end + 1):
            hi, cl, m = float(h[j]), float(c[j]), float(ma[j])
            peak = max(peak, hi - entry)
            if not armed and peak >= floor:
                armed = True
            if armed:
                cur = cl - entry
                if peak - cur >= giveback:
                    lock = max(peak - giveback, 0.0)
                    return lock > 0, "ratchet", lock
                if cl < m:
                    pts = cl - entry
                    return pts > 0, "runner_ma", pts
            elif cl < m:
                return False, "ma_sl", cl - entry
        pts = float(c[end]) - entry
        return pts > 0, "exp", pts
    for j in range(i + 1, end + 1):
        lo, cl, m = float(l[j]), float(c[j]), float(ma[j])
        peak = max(peak, entry - lo)
        if not armed and peak >= floor:
            armed = True
        if armed:
            cur = entry - cl
            if peak - cur >= giveback:
                lock = max(peak - giveback, 0.0)
                return lock > 0, "ratchet", lock
            if cl > m:
                pts = entry - cl
                return pts > 0, "runner_ma", pts
        elif cl > m:
            return False, "ma_sl", entry - cl
    pts = entry - float(c[end])
    return pts > 0, "exp", pts


def build_pivots(h, l, L=PIVOT_L):
    """Return lists of (index, price) for swing highs / lows confirmed at i+L."""
    n = len(h)
    sh, sl = [], []
    for i in range(L, n - L):
        window_h = h[i - L : i + L + 1]
        window_l = l[i - L : i + L + 1]
        if h[i] >= np.max(window_h) and h[i] > h[i - 1] and h[i] >= h[i + 1]:
            sh.append((i, float(h[i])))
        if l[i] <= np.min(window_l) and l[i] < l[i - 1] and l[i] <= l[i + 1]:
            sl.append((i, float(l[i])))
    return sh, sl


def day_levels_map(df):
    """Prior-day H/L/C and day-open per day string."""
    days = df["day"].values
    high = df["High"].astype(float).values
    low = df["Low"].astype(float).values
    close = df["Close"].astype(float).values
    open_ = df["Open"].astype(float).values
    by = defaultdict(lambda: {"h": -1e18, "l": 1e18, "c": None, "o": None, "first": True})
    order = []
    for i, d in enumerate(days):
        if d not in by or by[d]["first"]:
            if d not in by or by[d]["o"] is None:
                order.append(d)
            by[d]["o"] = float(open_[i])
            by[d]["first"] = False
        by[d]["h"] = max(by[d]["h"], float(high[i]))
        by[d]["l"] = min(by[d]["l"], float(low[i]))
        by[d]["c"] = float(close[i])
    prev = {}
    last = None
    for d in order:
        if last is not None:
            prev[d] = {
                "pdh": by[last]["h"],
                "pdl": by[last]["l"],
                "pdc": by[last]["c"],
            }
        else:
            prev[d] = {"pdh": None, "pdl": None, "pdc": None}
        last = d
    opens = {d: by[d]["o"] for d in order}
    return prev, opens


def nearest_above(levels, px):
    above = [lv for lv in levels if lv > px]
    return min(above) if above else None


def nearest_below(levels, px):
    below = [lv for lv in levels if lv < px]
    return max(below) if below else None


def collect_levels_at(i, entry, day, piv_hi, piv_lo, prev_map, opens, vwap_arr, look=LOOK_BARS):
    """All S/R prices known before bar i (pivots confirmed by i-L)."""
    levels = []
    # pivots whose confirmation index < i  (pivot at p confirmed at p+L)
    lo_i = max(0, i - look)
    for p, price in piv_hi:
        if p + PIVOT_L < i and p >= lo_i - PIVOT_L:
            levels.append(price)
    for p, price in piv_lo:
        if p + PIVOT_L < i and p >= lo_i - PIVOT_L:
            levels.append(price)
    # session / prior day
    o = opens.get(day)
    if o is not None:
        levels.append(float(o))
    pdlev = prev_map.get(day) or {}
    for k in ("pdh", "pdl", "pdc"):
        v = pdlev.get(k)
        if v is not None:
            levels.append(float(v))
    # VWAP soft
    if vwap_arr is not None and np.isfinite(vwap_arr[i]):
        levels.append(float(vwap_arr[i]))
    # unique rounded
    uniq = sorted({round(x, 2) for x in levels})
    resist = nearest_above(uniq, entry)
    support = nearest_below(uniq, entry)
    return uniq, support, resist


def enrich_sr(events, h, l, c, df, piv_hi, piv_lo, prev_map, opens):
    vwap = df["vwap"].astype(float).values if "vwap" in df.columns else None
    atr = df["atr14"].astype(float).values
    for e in events:
        i = int(e["full_i"])
        entry = float(e["entry"])
        side = e["decision"]
        if i < 30:
            e["sr_ok"] = False
            continue
        levels, support, resist = collect_levels_at(
            i, entry, e["day"], piv_hi, piv_lo, prev_map, opens, vwap
        )
        a = float(atr[i]) if np.isfinite(atr[i]) else 15.0
        e["sr_support"] = None if support is None else round(support, 2)
        e["sr_resist"] = None if resist is None else round(resist, 2)
        e["sr_n_levels"] = len(levels)

        room_up = (resist - entry) if resist is not None else 999.0
        room_dn = (entry - support) if support is not None else 999.0
        e["sr_room_up"] = round(room_up, 2)
        e["sr_room_dn"] = round(room_dn, 2)
        e["sr_room_fav"] = round(room_up if side == "BUY" else room_dn, 2)
        e["sr_room_against"] = round(room_dn if side == "BUY" else room_up, 2)

        # near favorable S/R (bounce zone): within 0.5 ATR
        near_sup = support is not None and (entry - support) <= 0.5 * a
        near_res = resist is not None and (resist - entry) <= 0.5 * a
        e["sr_near_support"] = bool(near_sup)
        e["sr_near_resist"] = bool(near_res)
        e["sr_bounce"] = bool((side == "BUY" and near_sup) or (side == "SELL" and near_res))

        # wall in path to T1 / 1ATR / 1.5ATR
        e["sr_wall_t1"] = bool(e["sr_room_fav"] < T1)  # opposing S/R closer than target
        e["sr_wall_atr"] = bool(e["sr_room_fav"] < a)
        e["sr_wall_1p5atr"] = bool(e["sr_room_fav"] < 1.5 * a)
        e["sr_wall_20"] = bool(e["sr_room_fav"] < 20.0)
        e["sr_wall_30"] = bool(e["sr_room_fav"] < 30.0)

        # clear path filters (NOT into wall)
        e["sr_clear_t1"] = not e["sr_wall_t1"]
        e["sr_clear_atr"] = not e["sr_wall_atr"]
        e["sr_clear_20"] = not e["sr_wall_20"]
        e["sr_clear_30"] = not e["sr_wall_30"]

        # into wall (bad): BUY under tight resistance / SELL above tight support
        e["sr_into_wall"] = bool(e["sr_wall_t1"])

        # space behind for SL (optional): want some room against so not instantly invalid
        e["sr_backed"] = bool(e["sr_room_against"] <= 1.0 * a)  # sitting near favorable side


def first_pass(xs, pred):
    for e in sorted(xs, key=lambda x: x["mins"]):
        if pred(e):
            return e
    return None


def summarize(calls, ndays, pts_key="_pts"):
    n = len(calls)
    if n == 0:
        return {"n": 0, "hit": 0.0, "cover": 0.0, "avg_pts": 0.0, "total_pts": 0.0, "pf": 0.0}
    wins = [e for e in calls if e.get("_win")]
    pts = [float(e.get(pts_key, 0)) for e in calls]
    gp = sum(p for p in pts if p > 0)
    gl = abs(sum(p for p in pts if p <= 0))
    return {
        "n": n,
        "hit": round(100 * len(wins) / n, 2),
        "cover": round(100 * n / ndays, 2) if ndays else 0.0,
        "avg_pts": round(float(np.mean(pts)), 2),
        "total_pts": round(float(np.sum(pts)), 2),
        "med_pts": round(float(np.median(pts)), 2),
        "pf": round(gp / gl, 2) if gl > 0 else (99.0 if gp > 0 else 0.0),
        "avg_room_fav": round(float(np.mean([e.get("sr_room_fav", 0) for e in calls])), 2),
    }


def eval_book(events, days, gate, h, l, c, ema34, exit_mode="t12"):
    by = defaultdict(list)
    for e in events:
        by[e["day"]].append(e)
    calls = []
    for d in days:
        e = first_pass(by.get(d, []), gate)
        if not e:
            continue
        i = int(e["full_i"])
        if exit_mode == "t12":
            ok, reason, pts = path_fixed_t1(h, l, c, ema34, i, e["decision"], T1)
        else:
            ok, reason, pts = path_ratchet(h, l, c, ema34, i, e["decision"])
        e = dict(e)
        e["_win"] = bool(ok)
        e["_reason"] = reason
        e["_pts"] = float(pts)
        calls.append(e)
    return calls


def main() -> int:
    print("HELD + Support/Resistance path filter", flush=True)
    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    data_hi = str(raw.index.max().date())
    y1_lo = max(
        str((pd.Timestamp(data_hi) - pd.DateOffset(years=1) + pd.Timedelta(days=1)).date()),
        WIN_LO,
    )
    print(f"window {y1_lo}→{data_hi}", flush=True)

    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    vix = vixmod.load_vix()

    print("[1] pivots + day levels…", flush=True)
    piv_hi, piv_lo = build_pivots(h, l, PIVOT_L)
    prev_map, opens = day_levels_map(df)
    print(f"  swing highs={len(piv_hi)} lows={len(piv_lo)}", flush=True)

    cache = next(PACK.glob("events_2025-11-17_*.pkl"))
    xs = pickle.load(cache.open("rb"))
    hold = [e for e in xs if y1_lo <= e["day"] <= data_hi]
    print(f"events={len(hold)}", flush=True)

    fwdmod.enrich_evt(hold, h, l, c, o)
    enrich_structure(hold, h, l, c, o, vix)
    enrich_prior3(hold, h, l, c, o)
    enrich_deep(hold, h, l, c, o, df)
    enrich_ma_layers(hold, df)
    enrich_ind(hold, df)
    enrich_sr(hold, h, l, c, df, piv_hi, piv_lo, prev_map, opens)

    sess_days = sorted({e["day"] for e in hold if in_session(e)})
    nd = len(sess_days)
    m1_lo = max(str((pd.Timestamp(data_hi) - pd.DateOffset(months=1) + pd.Timedelta(days=1)).date()), y1_lo)
    m3_lo = max(str((pd.Timestamp(data_hi) - pd.DateOffset(months=3) + pd.Timedelta(days=1)).date()), y1_lo)

    def held_sess(e):
        return in_session(e) and held_gate(e)

    # diagnose: among HELD losses, how often into wall?
    base_calls = eval_book(hold, sess_days, held_sess, h, l, c, ema34, "t12")
    loss = [e for e in base_calls if not e["_win"]]
    win = [e for e in base_calls if e["_win"]]
    def rate(xs, key):
        return round(100 * sum(1 for e in xs if e.get(key)) / len(xs), 1) if xs else 0.0

    print(
        f"HELD baseline n={len(base_calls)} hit={summarize(base_calls, nd)['hit']}% "
        f"wall_t1 on wins={rate(win,'sr_wall_t1')}% losses={rate(loss,'sr_wall_t1')}%",
        flush=True,
    )

    gates = [
        ("HELD only", held_sess),
        ("HELD + clear_T1 (no wall <12)", lambda e: held_sess(e) and e.get("sr_clear_t1")),
        ("HELD + clear_20", lambda e: held_sess(e) and e.get("sr_clear_20")),
        ("HELD + clear_30", lambda e: held_sess(e) and e.get("sr_clear_30")),
        ("HELD + clear_ATR", lambda e: held_sess(e) and e.get("sr_clear_atr")),
        ("HELD + clear_1.5ATR", lambda e: held_sess(e) and not e.get("sr_wall_1p5atr")),
        ("HELD + bounce (near fav S/R)", lambda e: held_sess(e) and e.get("sr_bounce")),
        ("HELD + bounce + clear_T1", lambda e: held_sess(e) and e.get("sr_bounce") and e.get("sr_clear_t1")),
        ("HELD + clear_T1 + not_bounce_only", lambda e: held_sess(e) and e.get("sr_clear_t1")),
        ("HELD + clear_20 + bounce", lambda e: held_sess(e) and e.get("sr_clear_20") and e.get("sr_bounce")),
        # skip if into wall OR require room_fav >= 15
        ("HELD + room_fav≥15", lambda e: held_sess(e) and float(e.get("sr_room_fav") or 0) >= 15),
        ("HELD + room_fav≥20", lambda e: held_sess(e) and float(e.get("sr_room_fav") or 0) >= 20),
        ("HELD + room_fav≥25", lambda e: held_sess(e) and float(e.get("sr_room_fav") or 0) >= 25),
        # avoid sitting right under/over wall even if room slightly > T1
        ("HELD + !into_wall + room_against≤1ATR (backed)", lambda e: held_sess(e) and e.get("sr_clear_t1") and e.get("sr_backed")),
    ]

    windows = [
        ("last_1y", y1_lo, data_hi),
        ("last_3m", m3_lo, data_hi),
        ("last_1m", m1_lo, data_hi),
    ]

    lines = [
        "# NIFTY HELD — Support/Resistance path filter",
        "",
        "Skip entries that must travel **into nearby opposing S/R** (wall) before T1.",
        "",
        "**S/R sources:** swing pivots (L=3), day open, prior day H/L/C, VWAP.",
        f"**Entry base:** DI+hard34+VWAP · 09:30–14:30 · 1/day · Exit T1={T1:.0f} EMA34 trail",
        "",
        "## Loss vs win: wall frequency (HELD baseline, 1y)",
        "",
        f"| | n | wall&lt;T1 | wall&lt;20 | bounce | avg room_fav |",
        f"|---|---:|---:|---:|---:|---:|",
        f"| Wins | {len(win)} | {rate(win,'sr_wall_t1')}% | {rate(win,'sr_wall_20')}% | {rate(win,'sr_bounce')}% | {round(np.mean([e['sr_room_fav'] for e in win]),1) if win else 0} |",
        f"| Losses | {len(loss)} | {rate(loss,'sr_wall_t1')}% | {rate(loss,'sr_wall_20')}% | {rate(loss,'sr_bounce')}% | {round(np.mean([e['sr_room_fav'] for e in loss]),1) if loss else 0} |",
        "",
    ]

    out = {"baseline_wall": {"win_wall_t1": rate(win, "sr_wall_t1"), "loss_wall_t1": rate(loss, "sr_wall_t1")}, "windows": {}}

    for wname, wlo, whi in windows:
        w_events = [e for e in hold if wlo <= e["day"] <= whi]
        w_days = [d for d in sess_days if wlo <= d <= whi]
        wnd = len(w_days)
        print(f"\n=== {wname} days={wnd} ===", flush=True)
        lines += [
            f"## {wname} (`{wlo}` → `{whi}`)",
            "",
            "### Exit = fixed T12",
            "",
            "| Gate | n | Hit% | Cover | Avg pts | Total | PF | avg room |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        ranked = []
        for gname, gate in gates:
            calls = eval_book(w_events, w_days, gate, h, l, c, ema34, "t12")
            st = summarize(calls, wnd)
            ranked.append((gname, st))
            print(f"  T12 {gname:55} {st['n']:3}@{st['hit']:6}% avg={st['avg_pts']:7} tot={st['total_pts']}", flush=True)
            lines.append(
                f"| `{gname}` | {st['n']} | {st['hit']}% | {st['cover']}% | "
                f"**{st['avg_pts']}** | {st['total_pts']} | {st['pf']} | {st.get('avg_room_fav',0)} |"
            )

        # ratchet on top SR filters
        lines += [
            "",
            "### Exit = ratchet arm12 gb8",
            "",
            "| Gate | n | Hit% | Cover | Avg pts | Total | PF |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for gname in (
            "HELD only",
            "HELD + clear_T1 (no wall <12)",
            "HELD + clear_20",
            "HELD + room_fav≥20",
            "HELD + bounce (near fav S/R)",
            "HELD + clear_T1 + not_bounce_only",
            "HELD + !into_wall + room_against≤1ATR (backed)",
        ):
            gate = next(g for n, g in gates if n == gname)
            calls = eval_book(w_events, w_days, gate, h, l, c, ema34, "ratchet")
            st = summarize(calls, wnd)
            print(f"  R12 {gname:55} {st['n']:3}@{st['hit']:6}% avg={st['avg_pts']:7} tot={st['total_pts']}", flush=True)
            lines.append(
                f"| `{gname}` | {st['n']} | {st['hit']}% | {st['cover']}% | "
                f"**{st['avg_pts']}** | {st['total_pts']} | {st['pf']} |"
            )

        ranked.sort(key=lambda x: (x[1]["hit"], x[1]["avg_pts"], x[1]["cover"]), reverse=True)
        lines += ["", "### Best T12 by hit then avg pts", ""]
        for i, (n, st) in enumerate(ranked[:5], 1):
            lines.append(f"{i}. `{n}` → hit **{st['hit']}%** · avg **{st['avg_pts']}** · cover {st['cover']}% · n={st['n']}")
        lines.append("")

        # last_1m ledger: baseline vs clear_T1 vs clear_20
        if wname == "last_1m":
            lines += ["### last_1m call ledger (T12)", ""]
            lines += [
                "| Day | Side | Pattern | room_fav | wall_t1 | bounce | HELD pts | clear20 pts |",
                "|---|---|---|---:|:---:|:---:|---:|---:|",
            ]
            c_held = {e["day"]: e for e in eval_book(w_events, w_days, held_sess, h, l, c, ema34, "t12")}
            g20 = next(g for n, g in gates if n == "HELD + clear_20")
            c_20 = {e["day"]: e for e in eval_book(w_events, w_days, g20, h, l, c, ema34, "t12")}
            for d in w_days:
                a = c_held.get(d)
                b = c_20.get(d)
                if not a:
                    lines.append(f"| {d} | — | — | — | — | — | — | — |")
                    continue
                lines.append(
                    f"| {d} | {a['decision']} | {a['primary']} | {a.get('sr_room_fav')} | "
                    f"{int(bool(a.get('sr_wall_t1')))} | {int(bool(a.get('sr_bounce')))} | "
                    f"{a['_pts']:+.1f} | {(b['_pts'] if b else float('nan')):+.1f} |"
                )
            lines.append("")

        out["windows"][wname] = {"schemes_t12": {n: s for n, s in ranked}}

    lines += [
        "## How to use live",
        "",
        "1. Same HELD entry trigger.",
        "2. Build S/R from recent swing pivots + PDH/PDL/PDC + day open + VWAP.",
        "3. Measure **room_fav** = distance to next opposing level (resistance for BUY, support for SELL).",
        "4. **Skip** if `room_fav < T1` (or `< 20` for stricter) — price has a wall before target.",
        "5. Optional: prefer **bounce** (BUY near support / SELL near resistance) when room_fav is also clear.",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
