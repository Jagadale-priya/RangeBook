"""Deep profit-booking: fixed vs dynamic T1 vs runner trail on HELD calls.

HELD entry locked: DI + hard34 + VWAP · session 09:30–14:30 · 1/day first
Exit variants compared on last 1y (+ last 1m / 3m slices):

  A) Fixed T1 grid under EMA34-strict
  B) Dynamic T1 = clip(k*ATR, lo, hi)
  C) Dynamic T1 = clip(|entry-EMA34|*k, lo, hi)
  D) Dynamic T1 = t1_hint (MA distance recipe)
  E) Arm@floor then RUNNER: after +floor MFE, no fixed T1 — exit on EMA34 flip (book open PnL)
  F) Ratchet: after +floor, trail from MFE with giveback g (pts)
  G) Pure MA trail (no T1): exit on flip, pts = exit-entry (can be green or red)

Goal: raise avg pts / total pts without collapsing hit too far.

  python -u prod_live/tests/builders/_diag_scalp_ma_hold100_dynamic_t1.py
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
REPORT = OUT / "NIFTY_1M_HELD_DYNAMIC_T1_PROFIT.md"
REPORT_JSON = OUT / "NIFTY_1M_HELD_DYNAMIC_T1_PROFIT.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
MAX_BARS = 120


def in_session(e) -> bool:
    return MINS_LO <= int(e["mins"]) < MINS_HI


def held_session(e) -> bool:
    return in_session(e) and held_gate(e)


def signed_pts(side, entry, exit_px):
    if side == "BUY":
        return float(exit_px) - float(entry)
    return float(entry) - float(exit_px)


def mfe_before_ma_flip(h, l, c, ma, i, side, max_bars=MAX_BARS):
    """Max favorable excursion until first EMA34 close flip (or cap)."""
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    mfe = 0.0
    for j in range(i + 1, end + 1):
        hi, lo, cl, m = float(h[j]), float(l[j]), float(c[j]), float(ma[j])
        if not np.isfinite(m):
            break
        if side == "BUY":
            mfe = max(mfe, hi - entry)
            if cl < m:
                break
        else:
            mfe = max(mfe, entry - lo)
            if cl > m:
                break
    return mfe


def path_fixed_t1(h, l, c, ma, i, side, t1_pts, max_bars=MAX_BARS):
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    if side == "BUY":
        t1 = entry + t1_pts
        for j in range(i + 1, end + 1):
            hi, cl, m = float(h[j]), float(c[j]), float(ma[j])
            if hi >= t1:
                return True, "t1", t1, j, float(t1_pts)
            if cl < m:
                return False, "ma_sl", cl, j, signed_pts(side, entry, cl)
        px = float(c[end])
        return False, "exp", px, end, signed_pts(side, entry, px)
    t1 = entry - t1_pts
    for j in range(i + 1, end + 1):
        lo, cl, m = float(l[j]), float(c[j]), float(ma[j])
        if lo <= t1:
            return True, "t1", t1, j, float(t1_pts)
        if cl > m:
            return False, "ma_sl", cl, j, signed_pts(side, entry, cl)
    px = float(c[end])
    return False, "exp", px, end, signed_pts(side, entry, px)


def path_runner_after_floor(h, l, c, ma, i, side, floor, max_bars=MAX_BARS):
    """After MFE>=floor, ignore fixed T1 — hold until EMA34 close flip; book open PnL.
    If MA flips before floor → loss at flip.
    """
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    armed = False
    peak = 0.0
    if side == "BUY":
        for j in range(i + 1, end + 1):
            hi, cl, m = float(h[j]), float(c[j]), float(ma[j])
            fav = hi - entry
            peak = max(peak, fav)
            if not armed and peak >= floor:
                armed = True
            if armed:
                if cl < m:
                    pts = signed_pts(side, entry, cl)
                    return pts > 0, "runner_ma", cl, j, pts
            else:
                if cl < m:
                    return False, "ma_sl", cl, j, signed_pts(side, entry, cl)
        px = float(c[end])
        pts = signed_pts(side, entry, px)
        return pts > 0, "exp", px, end, pts
    for j in range(i + 1, end + 1):
        lo, cl, m = float(l[j]), float(c[j]), float(ma[j])
        fav = entry - lo
        peak = max(peak, fav)
        if not armed and peak >= floor:
            armed = True
        if armed:
            if cl > m:
                pts = signed_pts(side, entry, cl)
                return pts > 0, "runner_ma", cl, j, pts
        else:
            if cl > m:
                return False, "ma_sl", cl, j, signed_pts(side, entry, cl)
    px = float(c[end])
    pts = signed_pts(side, entry, px)
    return pts > 0, "exp", px, end, pts


def path_ratchet(h, l, c, ma, i, side, floor, giveback, max_bars=MAX_BARS):
    """After MFE>=floor, lock peak−giveback; exit when close gives that much back, or MA flip."""
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    armed = False
    peak = 0.0
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
                    px = entry + lock
                    return lock > 0, "ratchet", px, j, lock
                if cl < m:
                    pts = signed_pts(side, entry, cl)
                    return pts > 0, "runner_ma", cl, j, pts
            elif cl < m:
                return False, "ma_sl", cl, j, signed_pts(side, entry, cl)
        px = float(c[end])
        pts = signed_pts(side, entry, px)
        return pts > 0, "exp", px, end, pts
    for j in range(i + 1, end + 1):
        lo, cl, m = float(l[j]), float(c[j]), float(ma[j])
        peak = max(peak, entry - lo)
        if not armed and peak >= floor:
            armed = True
        if armed:
            cur = entry - cl
            if peak - cur >= giveback:
                lock = max(peak - giveback, 0.0)
                px = entry - lock
                return lock > 0, "ratchet", px, j, lock
            if cl > m:
                pts = signed_pts(side, entry, cl)
                return pts > 0, "runner_ma", cl, j, pts
        elif cl > m:
            return False, "ma_sl", cl, j, signed_pts(side, entry, cl)
    px = float(c[end])
    pts = signed_pts(side, entry, px)
    return pts > 0, "exp", px, end, pts


def path_pure_trail(h, l, c, ma, i, side, max_bars=MAX_BARS):
    """No T1 — exit only on EMA34 close flip."""
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    if side == "BUY":
        for j in range(i + 1, end + 1):
            cl, m = float(c[j]), float(ma[j])
            if cl < m:
                pts = signed_pts(side, entry, cl)
                return pts > 0, "ma_exit", cl, j, pts
        px = float(c[end])
        pts = signed_pts(side, entry, px)
        return pts > 0, "exp", px, end, pts
    for j in range(i + 1, end + 1):
        cl, m = float(c[j]), float(ma[j])
        if cl > m:
            pts = signed_pts(side, entry, cl)
            return pts > 0, "ma_exit", cl, j, pts
    px = float(c[end])
    pts = signed_pts(side, entry, px)
    return pts > 0, "exp", px, end, pts


def first_pass(xs, pred):
    for e in sorted(xs, key=lambda x: x["mins"]):
        if pred(e):
            return e
    return None


def pick_held(events, days):
    by = defaultdict(list)
    for e in events:
        by[e["day"]].append(e)
    calls = []
    for d in days:
        e = first_pass(by.get(d, []), held_session)
        if e:
            calls.append(e)
    return calls


def summarize_pts(results, ndays):
    n = len(results)
    if n == 0:
        return {
            "n": 0, "hit": 0.0, "cover": 0.0, "avg_pts": 0.0, "total_pts": 0.0,
            "med_pts": 0.0, "avg_win": 0.0, "avg_loss": 0.0, "pf": 0.0, "exp": 0.0,
        }
    wins = [r for r in results if r["pts"] > 0]
    losses = [r for r in results if r["pts"] <= 0]
    # hit = classic path win flag if present else pts>0
    hit_n = sum(1 for r in results if r.get("win"))
    gp = sum(r["pts"] for r in wins)
    gl = abs(sum(r["pts"] for r in losses))
    pts = [r["pts"] for r in results]
    return {
        "n": n,
        "hit": round(100 * hit_n / n, 2),
        "cover": round(100 * n / ndays, 2) if ndays else 0.0,
        "avg_pts": round(float(np.mean(pts)), 2),
        "med_pts": round(float(np.median(pts)), 2),
        "total_pts": round(float(np.sum(pts)), 2),
        "avg_win": round(float(np.mean([r["pts"] for r in wins])), 2) if wins else 0.0,
        "avg_loss": round(float(np.mean([r["pts"] for r in losses])), 2) if losses else 0.0,
        "pf": round(gp / gl, 2) if gl > 0 else (99.0 if gp > 0 else 0.0),
        "exp": round(float(np.mean(pts)), 2),
        "win_n": len(wins),
        "loss_n": len(losses),
    }


def run_scheme(calls, h, l, c, ema34, atr, name, fn):
    rows = []
    for e in calls:
        i = int(e["full_i"])
        side = e["decision"]
        win, reason, px, j, pts = fn(e, h, l, c, ema34, atr, i, side)
        rows.append(
            {
                "day": e["day"],
                "hm": e["hm"],
                "side": side,
                "primary": e["primary"],
                "entry": e["entry"],
                "win": bool(win),
                "reason": reason,
                "pts": float(pts),
                "exit_px": float(px),
                "bars": int(j - i),
                "scheme": name,
                "mfe_ma": e.get("_mfe_ma"),
            }
        )
    return rows


def main() -> int:
    print("HELD dynamic T1 / runner profit deep dive", flush=True)
    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    data_hi = str(raw.index.max().date())
    y1_lo = str((pd.Timestamp(data_hi) - pd.DateOffset(years=1) + pd.Timedelta(days=1)).date())
    y1_lo = max(y1_lo, WIN_LO)
    print(f"data {WIN_LO}→{data_hi} · analyze {y1_lo}→{data_hi}", flush=True)

    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    atr = df["atr14"].astype(float).values
    vix = vixmod.load_vix()

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

    days = sorted({e["day"] for e in hold})
    # session days = days with ≥1 session-window event
    sess_days = sorted({e["day"] for e in hold if in_session(e)})
    calls = pick_held(hold, sess_days)
    nd = len(sess_days)
    print(f"session days={nd} HELD calls={len(calls)}", flush=True)

    # MFE before MA flip on HELD entries
    mfes = []
    for e in calls:
        i = int(e["full_i"])
        mfe = mfe_before_ma_flip(h, l, c, ema34, i, e["decision"])
        e["_mfe_ma"] = round(mfe, 2)
        mfes.append(mfe)
    mfes = np.array(mfes, dtype=float)
    mfe_stats = {
        "n": len(mfes),
        "mean": round(float(np.mean(mfes)), 2) if len(mfes) else 0,
        "med": round(float(np.median(mfes)), 2) if len(mfes) else 0,
        "p25": round(float(np.percentile(mfes, 25)), 2) if len(mfes) else 0,
        "p75": round(float(np.percentile(mfes, 75)), 2) if len(mfes) else 0,
        "p90": round(float(np.percentile(mfes, 90)), 2) if len(mfes) else 0,
        "frac_ge_12": round(100 * float(np.mean(mfes >= 12)), 1) if len(mfes) else 0,
        "frac_ge_20": round(100 * float(np.mean(mfes >= 20)), 1) if len(mfes) else 0,
        "frac_ge_30": round(100 * float(np.mean(mfes >= 30)), 1) if len(mfes) else 0,
        "frac_ge_40": round(100 * float(np.mean(mfes >= 40)), 1) if len(mfes) else 0,
        "frac_ge_50": round(100 * float(np.mean(mfes >= 50)), 1) if len(mfes) else 0,
    }
    print(f"MFE-before-MAFlip {mfe_stats}", flush=True)

    schemes = []

    # A) fixed T1
    for t1 in (12.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0):
        name = f"fixed_T{t1:.0f}"

        def make_fn(t1=t1):
            def fn(e, h, l, c, ema34, atr, i, side):
                return path_fixed_t1(h, l, c, ema34, i, side, t1)

            return fn

        schemes.append((name, make_fn()))

    # B) ATR dynamic
    for k, lo, hi in ((0.8, 12, 30), (1.0, 12, 35), (1.2, 15, 40), (1.5, 15, 50), (2.0, 20, 60)):
        name = f"dyn_ATR_k{k}_[{lo},{hi}]"

        def make_fn(k=k, lo=lo, hi=hi):
            def fn(e, h, l, c, ema34, atr, i, side):
                a = float(atr[i]) if np.isfinite(atr[i]) else 15.0
                t1 = float(np.clip(k * a, lo, hi))
                return path_fixed_t1(h, l, c, ema34, i, side, t1)

            return fn

        schemes.append((name, make_fn()))

    # C) |entry-EMA34| dynamic
    for k, lo, hi in ((0.5, 12, 30), (0.75, 12, 40), (1.0, 15, 50), (1.25, 15, 60)):
        name = f"dyn_EMA34_k{k}_[{lo},{hi}]"

        def make_fn(k=k, lo=lo, hi=hi):
            def fn(e, h, l, c, ema34, atr, i, side):
                dist = abs(float(c[i]) - float(ema34[i])) if np.isfinite(ema34[i]) else 15.0
                t1 = float(np.clip(k * dist, lo, hi))
                return path_fixed_t1(h, l, c, ema34, i, side, t1)

            return fn

        schemes.append((name, make_fn()))

    # D) t1_hint
    def fn_hint(e, h, l, c, ema34, atr, i, side):
        t1 = float(e.get("t1_hint") or 15.0)
        t1 = float(np.clip(t1, 12.0, 40.0))
        return path_fixed_t1(h, l, c, ema34, i, side, t1)

    schemes.append(("dyn_t1_hint_[12,40]", fn_hint))

    # E) runner after floor
    for floor in (8.0, 12.0, 15.0, 20.0):
        name = f"runner_arm{floor:.0f}"

        def make_fn(floor=floor):
            def fn(e, h, l, c, ema34, atr, i, side):
                return path_runner_after_floor(h, l, c, ema34, i, side, floor)

            return fn

        schemes.append((name, make_fn()))

    # F) ratchet
    for floor, gb in ((12.0, 5.0), (12.0, 8.0), (15.0, 6.0), (20.0, 8.0), (12.0, 10.0)):
        name = f"ratchet_arm{floor:.0f}_gb{gb:.0f}"

        def make_fn(floor=floor, gb=gb):
            def fn(e, h, l, c, ema34, atr, i, side):
                return path_ratchet(h, l, c, ema34, i, side, floor, gb)

            return fn

        schemes.append((name, make_fn()))

    # G) pure trail
    def fn_pure(e, h, l, c, ema34, atr, i, side):
        return path_pure_trail(h, l, c, ema34, i, side)

    schemes.append(("pure_MA_trail", fn_pure))

    # windows
    m1_lo = str((pd.Timestamp(data_hi) - pd.DateOffset(months=1) + pd.Timedelta(days=1)).date())
    m3_lo = str((pd.Timestamp(data_hi) - pd.DateOffset(months=3) + pd.Timedelta(days=1)).date())
    windows = [
        ("last_1y", y1_lo, data_hi),
        ("last_3m", max(m3_lo, y1_lo), data_hi),
        ("last_1m", max(m1_lo, y1_lo), data_hi),
    ]

    all_out = {"mfe": mfe_stats, "windows": {}}
    lines = [
        "# NIFTY HELD — dynamic T1 / runner profit booking",
        "",
        f"Entry locked: **DI+hard34+VWAP** · session **09:30–14:30** · 1/day first",
        f"Window base **`{y1_lo}` → `{data_hi}`** · HELD n={len(calls)} / {nd} session days",
        "",
        "## MFE before EMA34 flip (room beyond T1=12)",
        "",
        f"| stat | value |",
        f"|---|---:|",
        f"| mean / med | {mfe_stats['mean']} / {mfe_stats['med']} |",
        f"| p25 / p75 / p90 | {mfe_stats['p25']} / {mfe_stats['p75']} / {mfe_stats['p90']} |",
        f"| % days MFE≥12/20/30/40/50 | {mfe_stats['frac_ge_12']}% / {mfe_stats['frac_ge_20']}% / {mfe_stats['frac_ge_30']}% / {mfe_stats['frac_ge_40']}% / {mfe_stats['frac_ge_50']}% |",
        "",
        "If med MFE ≫ 12, fixed T1=12 leaves money on table → runners / higher dyn T1 can lift avg pts.",
        "",
    ]

    best_by_window = {}

    for wname, wlo, whi in windows:
        w_calls = [e for e in calls if wlo <= e["day"] <= whi]
        w_days = [d for d in sess_days if wlo <= d <= whi]
        wnd = len(w_days)
        print(f"\n=== {wname} {wlo}→{whi} calls={len(w_calls)} days={wnd} ===", flush=True)
        lines += [
            f"## {wname} (`{wlo}` → `{whi}`)",
            "",
            "| Scheme | n | Hit% | Cover | Avg pts | Med pts | Total pts | AvgW | AvgL | PF |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        ranked = []
        for name, fn in schemes:
            rows = run_scheme(w_calls, h, l, c, ema34, atr, name, fn)
            st = summarize_pts(rows, wnd)
            ranked.append((name, st, rows))
            print(
                f"  {name:28} n={st['n']:3} hit={st['hit']:6}% avg={st['avg_pts']:7} "
                f"tot={st['total_pts']:8} pf={st['pf']}",
                flush=True,
            )
            lines.append(
                f"| `{name}` | {st['n']} | {st['hit']}% | {st['cover']}% | "
                f"**{st['avg_pts']}** | {st['med_pts']} | {st['total_pts']} | "
                f"{st['avg_win']} | {st['avg_loss']} | {st['pf']} |"
            )

        # rank by total_pts then avg_pts then hit
        ranked.sort(key=lambda x: (x[1]["total_pts"], x[1]["avg_pts"], x[1]["hit"]), reverse=True)
        top = ranked[:8]
        lines += ["", "### Top by total pts", ""]
        for i, (name, st, _) in enumerate(top, 1):
            lines.append(
                f"{i}. `{name}` → total **{st['total_pts']}** · avg **{st['avg_pts']}** · "
                f"hit {st['hit']}% · PF {st['pf']}"
            )
        lines.append("")

        # also best with hit>=70%
        solid = [r for r in ranked if r[1]["hit"] >= 70]
        solid.sort(key=lambda x: (x[1]["total_pts"], x[1]["avg_pts"]), reverse=True)
        if solid:
            name, st, rows = solid[0]
            lines += [
                f"### Best with hit≥70%: `{name}`",
                f"avg **{st['avg_pts']}** · total **{st['total_pts']}** · hit {st['hit']}% · PF {st['pf']}",
                "",
            ]
            best_by_window[wname] = {"name": name, "stats": st}
        else:
            name, st, rows = ranked[0]
            best_by_window[wname] = {"name": name, "stats": st}

        all_out["windows"][wname] = {
            "lo": wlo,
            "hi": whi,
            "n_calls": len(w_calls),
            "n_days": wnd,
            "schemes": {name: st for name, st, _ in ranked},
            "top": [{"name": n, "stats": s} for n, s, _ in top],
        }

        # last_1m trade ledger for baseline vs best runner
        if wname == "last_1m":
            t12_rows = next(r for n, _, r in ranked if n == "fixed_T12")
            best_rows = ranked[0][2]
            runner_rows = next((r for n, _, r in ranked if n == "runner_arm12"), None)
            lines += ["### last_1m trade compare: fixed_T12 vs runner_arm12 vs best", ""]
            by_t12 = {r["day"]: r for r in t12_rows}
            by_run = {r["day"]: r for r in (runner_rows or [])}
            by_best = {r["day"]: r for r in best_rows}
            lines += [
                "| Day | Side | Pattern | T12 pts | Runner12 pts | Best pts |",
                "|---|---|---|---:|---:|---:|",
            ]
            for e in w_calls:
                d = e["day"]
                a = by_t12.get(d, {})
                b = by_run.get(d, {})
                c_ = by_best.get(d, {})
                lines.append(
                    f"| {d} | {e['decision']} | {e['primary']} | "
                    f"{a.get('pts', 0):+.1f} | {b.get('pts', 0):+.1f} | {c_.get('pts', 0):+.1f} |"
                )
            lines.append("")

    # recommendation
    lines += [
        "## Recommendation",
        "",
        "1. **Keep entry gates fixed** (DI+hard34+VWAP, session cut).",
        "2. Prefer schemes that beat `fixed_T12` on **total pts** without hit collapsing below ~70% when possible.",
        "3. **Runner after arm** (floor=12): once +12 prints, stop using fixed T1 — ride until EMA34 close flip; books open PnL (often >12).",
        "4. **Dynamic ATR T1** as simpler alternative if you want a hard target still.",
        "",
    ]
    for w, b in best_by_window.items():
        st = b["stats"]
        lines.append(
            f"- **{w}:** `{b['name']}` · avg {st['avg_pts']} · total {st['total_pts']} · hit {st['hit']}%"
        )
    lines.append("")

    # vs fixed_T12 lift on 1y
    y1 = all_out["windows"]["last_1y"]["schemes"]
    t12_base = y1.get("fixed_T12", {})
    lines += [
        "## Lift vs fixed_T12 (last 1y)",
        "",
        "| Scheme | Δ avg pts | Δ total | Hit |",
        "|---|---:|---:|---:|",
    ]
    for name, st in sorted(y1.items(), key=lambda kv: kv[1]["total_pts"], reverse=True)[:15]:
        lines.append(
            f"| `{name}` | {st['avg_pts'] - t12_base.get('avg_pts', 0):+.2f} | "
            f"{st['total_pts'] - t12_base.get('total_pts', 0):+.1f} | {st['hit']}% |"
        )

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(all_out, indent=2), encoding="utf-8")
    print(f"\nWrote {REPORT}", flush=True)
    print(f"Wrote {REPORT_JSON}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
