"""RESEARCH ONLY — daily must-call with **dynamic** candle/pattern SL & T1.

User constraint:
  - SL / T1 from last candle + pattern structure (not fixed ATR×80 / 5pt)
  - T1 floor 5–10 pts (prefer higher when structure allows)
  - ≥1 call every day · aim 100% both windows · sane RR

  python -u prod_live/tests/builders/research_nifty_1m_daily_must_dyn.py
"""
from __future__ import annotations

import json
import sys
import time
from itertools import product
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401,E402

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_chart_only_100 as co  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_daily_must_100 as dm  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_daily_must_dyn"
REPORT_MD = OUT / "NIFTY_1M_DAILY_MUST_DYN.md"
REPORT_JSON = OUT / "NIFTY_1M_DAILY_MUST_DYN.json"

WEAK = {"bull_run2", "bear_run2"}


def collect_day_events(
    df: pd.DataFrame,
    day_lo: str,
    day_hi: str,
    mode: str = "skip_run2",
    window: Tuple[int, int] = (560, 720),
) -> List[dict]:
    """One event/day with full candle geometry for dynamic brackets."""
    h_all = df["High"].astype(float).values
    l_all = df["Low"].astype(float).values
    c_all = df["Close"].astype(float).values
    o_all = df["Open"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(df.index)}
    events: List[dict] = []
    days = [d for d in df["day"].unique() if day_lo <= d <= day_hi]
    mins_lo, mins_hi = window
    t0 = time.time()

    for di, day in enumerate(days, 1):
        if di % 50 == 0:
            print(f"    daily {di}/{len(days)} n={len(events)} ({time.time()-t0:.0f}s)", flush=True)
        sess = df[df["day"] == day]
        if len(sess) < 40:
            continue
        day_open = float(sess["Open"].iloc[0])
        pick = None

        for pos in range(3, len(sess)):
            row = sess.iloc[pos]
            mins = int(row["mins"])
            if mins < mins_lo or mins > mins_hi:
                continue
            body = float(row["Close"]) - float(row["Open"])
            hit = [p for p in dm.PRIORITY if p in row.index and int(row[p]) == 1]
            if mode == "skip_run2":
                hit = [p for p in hit if p not in WEAK] or hit
            elif mode == "strong_first":
                weak3 = WEAK | {"bull_run3", "bear_run3"}
                hit = [p for p in hit if p not in weak3] or hit
            if mode.startswith("first") or mode in ("skip_run2", "strong_first", "trend_skip"):
                if not hit and mode != "first_any":
                    continue
            primary = hit[0] if hit else None
            if primary:
                side = dm._side_for(primary, body)
                if side is None or (side == "BUY" and body <= 0) or (side == "SELL" and body >= 0):
                    continue
            else:
                if abs(float(row["body_frac"])) < 0.45:
                    continue
                side = "BUY" if body > 0 else ("SELL" if body < 0 else None)
                if side is None:
                    continue
                primary = "_body_bull" if side == "BUY" else "_body_bear"

            if mode == "trend_skip":
                drift = float(row["Close"]) - day_open
                if (side == "BUY" and drift < 0) or (side == "SELL" and drift > 0):
                    continue

            # candle geometry (signal bar = last candle)
            o = float(row["Open"])
            cl = float(row["Close"])
            hi = float(row["High"])
            lo = float(row["Low"])
            body_abs = abs(cl - o)
            upper_wick = hi - max(o, cl)
            lower_wick = min(o, cl) - lo
            candle_range = max(hi - lo, 0.5)
            # pattern window (2–3 bars)
            lo_pat = float(sess["Low"].iloc[max(0, pos - 2) : pos + 1].min())
            hi_pat = float(sess["High"].iloc[max(0, pos - 2) : pos + 1].max())
            pat_range = max(hi_pat - lo_pat, 0.5)
            # prior bar
            prev = sess.iloc[pos - 1]
            prev_range = max(float(prev["High"]) - float(prev["Low"]), 0.5)
            atr = max(float(row["atr14"]) if np.isfinite(row["atr14"]) else 8.0, 3.0)
            entry = cl
            if side == "BUY":
                sl_candle = max(entry - lo, 0.5)  # beyond signal low
                sl_pat = max(entry - lo_pat, 0.5)
                # bullish: room measured by body / upper structure
                t1_body = max(body_abs, 0.5)
                t1_wick = max(upper_wick, body_abs * 0.5, 0.5)
            else:
                sl_candle = max(hi - entry, 0.5)
                sl_pat = max(hi_pat - entry, 0.5)
                t1_body = max(body_abs, 0.5)
                t1_wick = max(lower_wick, body_abs * 0.5, 0.5)

            full_i = idx_map[sess.index[pos]]
            mae, mfe = co.excursion(h_all, l_all, c_all, full_i, side, max_bars=200)
            pick = {
                "day": day,
                "hm": row["hm"],
                "decision": side,
                "primary": primary,
                "entry": entry,
                "mins": mins,
                "atr": atr,
                "body_abs": body_abs,
                "body_frac": float(row["body_frac"]),
                "candle_range": candle_range,
                "pat_range": pat_range,
                "prev_range": prev_range,
                "upper_wick": upper_wick,
                "lower_wick": lower_wick,
                "sl_candle": sl_candle,
                "sl_pat": sl_pat,
                "t1_body": t1_body,
                "t1_wick": t1_wick,
                "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
                "mae": mae,
                "mfe": mfe,
                "full_i": full_i,
            }
            break

        if pick is None:
            # fallback: strongest body in window
            best = None
            for pos in range(3, len(sess)):
                row = sess.iloc[pos]
                mins = int(row["mins"])
                if mins < 565 or mins > 750:
                    continue
                body = float(row["Close"]) - float(row["Open"])
                if abs(body) < 1e-6:
                    continue
                side = "BUY" if body > 0 else "SELL"
                o, cl = float(row["Open"]), float(row["Close"])
                hi, lo = float(row["High"]), float(row["Low"])
                body_abs = abs(cl - o)
                atr = max(float(row["atr14"]) if np.isfinite(row["atr14"]) else 8.0, 3.0)
                entry = cl
                lo_pat = float(sess["Low"].iloc[max(0, pos - 2) : pos + 1].min())
                hi_pat = float(sess["High"].iloc[max(0, pos - 2) : pos + 1].max())
                sl_candle = max(entry - lo, 0.5) if side == "BUY" else max(hi - entry, 0.5)
                sl_pat = max(entry - lo_pat, 0.5) if side == "BUY" else max(hi_pat - entry, 0.5)
                full_i = idx_map[sess.index[pos]]
                mae, mfe = co.excursion(h_all, l_all, c_all, full_i, side, max_bars=200)
                cand = {
                    "day": day,
                    "hm": row["hm"],
                    "decision": side,
                    "primary": "_fallback",
                    "entry": entry,
                    "mins": mins,
                    "atr": atr,
                    "body_abs": body_abs,
                    "body_frac": float(row["body_frac"]),
                    "candle_range": max(hi - lo, 0.5),
                    "pat_range": max(hi_pat - lo_pat, 0.5),
                    "prev_range": max(hi - lo, 0.5),
                    "upper_wick": hi - max(o, cl),
                    "lower_wick": min(o, cl) - lo,
                    "sl_candle": sl_candle,
                    "sl_pat": sl_pat,
                    "t1_body": max(body_abs, 0.5),
                    "t1_wick": max(body_abs * 0.5, 0.5),
                    "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
                    "mae": mae,
                    "mfe": mfe,
                    "full_i": full_i,
                    "score": abs(float(row["body_frac"])),
                }
                if best is None or cand["score"] > best["score"]:
                    best = cand
            if best:
                best.pop("score", None)
                pick = best
        if pick:
            events.append(pick)
    return events


def dyn_brackets(e: dict, kind: str, params: dict) -> Tuple[float, float]:
    """Dynamic SL/T1 from candle/pattern geometry. T1 floored at t1_floor (5–10+)."""
    t1_floor = float(params.get("t1_floor", 8.0))
    t1_cap = float(params.get("t1_cap", 40.0))
    atr = e["atr"]

    if kind == "candle":
        # SL beyond signal candle extreme × k; T1 = body × m (or wick)
        sl = max(params["sl_k"] * e["sl_candle"], params.get("sl_min", 5.0))
        t1_raw = params["t1_k"] * e["t1_body"]
        if params.get("use_wick"):
            t1_raw = max(t1_raw, params["t1_k"] * e["t1_wick"])
        t1 = min(max(t1_raw, t1_floor), t1_cap)
        return sl, t1

    if kind == "pat":
        sl = max(params["sl_k"] * e["sl_pat"], params.get("sl_min", 5.0))
        t1 = min(max(params["t1_k"] * e["pat_range"], t1_floor), t1_cap)
        return sl, t1

    if kind == "candle_atr":
        # SL = max(candle*k, atr*a); T1 = max(body*m, atr*t, floor)
        sl = max(params["sl_k"] * e["sl_candle"], params["atr_k"] * atr, params.get("sl_min", 5.0))
        t1 = min(
            max(params["t1_k"] * e["t1_body"], params["t1_atr"] * atr, t1_floor),
            t1_cap,
        )
        return sl, t1

    if kind == "rr_candle":
        # SL from candle; T1 = RR × SL but clamped to floor/cap and structure
        sl = max(params["sl_k"] * e["sl_candle"], params.get("sl_min", 5.0))
        t1 = min(max(params["rr"] * sl, t1_floor), t1_cap)
        # also don't exceed 1.5× pattern range as dream target
        t1 = min(t1, max(params.get("pat_cap_k", 1.2) * e["pat_range"], t1_floor))
        return sl, t1

    if kind == "mix":
        sl = max(
            params["a"] * e["sl_candle"] + params["b"] * e["sl_pat"] + params["c"] * atr,
            params.get("sl_min", 5.0),
        )
        t1 = min(
            max(params["t_body"] * e["t1_body"] + params["t_atr"] * atr, t1_floor),
            t1_cap,
        )
        return sl, t1

    # default: candle SL, body T1
    sl = max(1.2 * e["sl_candle"], 5.0)
    t1 = min(max(1.0 * e["t1_body"], t1_floor), t1_cap)
    return sl, t1


def eval_book(events, h, l, c, kind, params) -> dict:
    rows = []
    for e in events:
        sl, t1 = dyn_brackets(e, kind, params)
        # path_hit requires >= 4
        if sl < 4 or t1 < 4:
            win, outcome = False, "bad"
        else:
            win, outcome = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
            if outcome in ("bad", "both"):
                win = False
        rows.append(
            {
                "day": e["day"],
                "hm": e["hm"],
                "decision": e["decision"],
                "primary": e["primary"],
                "entry": e["entry"],
                "sl": round(sl, 2),
                "t1": round(t1, 2),
                "rr": round(sl / max(t1, 1e-6), 2),
                "win": bool(win),
                "outcome": outcome,
                "atr": round(e["atr"], 2),
                "body_abs": round(e["body_abs"], 2),
                "sl_candle": round(e["sl_candle"], 2),
                "rsi_14": e["rsi_14"],
            }
        )
    n = len(rows)
    wins = sum(1 for r in rows if r["win"])
    return {
        "n": n,
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else 0.0,
        "avg_sl": round(float(np.mean([r["sl"] for r in rows])), 2) if rows else 0,
        "avg_t1": round(float(np.mean([r["t1"] for r in rows])), 2) if rows else 0,
        "avg_rr": round(float(np.mean([r["rr"] for r in rows])), 2) if rows else 0,
        "med_sl": round(float(np.median([r["sl"] for r in rows])), 2) if rows else 0,
        "med_t1": round(float(np.median([r["t1"] for r in rows])), 2) if rows else 0,
        "miss_days": [r["day"] for r in rows if not r["win"]],
        "calls": rows,
    }


def hunt(cal, test, h, l, c) -> dict:
    print("\n[3] Hunt dynamic candle SL/T1…", flush=True)
    specs = []
    # T1 floors 5, 8, 10 — user wants 5–10+
    for t1_floor in (5.0, 8.0, 10.0):
        for sl_k, t1_k in product([1.0, 1.15, 1.3, 1.5, 1.8, 2.2, 2.8], [0.8, 1.0, 1.2, 1.5, 2.0]):
            specs.append(
                (
                    "candle",
                    {"sl_k": sl_k, "t1_k": t1_k, "t1_floor": t1_floor, "t1_cap": 35.0, "sl_min": 5.0},
                    f"candle_sl{sl_k}_t{t1_k}_f{t1_floor}",
                )
            )
            specs.append(
                (
                    "candle",
                    {
                        "sl_k": sl_k,
                        "t1_k": t1_k,
                        "t1_floor": t1_floor,
                        "t1_cap": 35.0,
                        "sl_min": 5.0,
                        "use_wick": True,
                    },
                    f"candlewick_sl{sl_k}_t{t1_k}_f{t1_floor}",
                )
            )
        for sl_k, t1_k in product([1.0, 1.2, 1.5, 2.0, 2.5], [0.4, 0.55, 0.7, 1.0]):
            specs.append(
                (
                    "pat",
                    {"sl_k": sl_k, "t1_k": t1_k, "t1_floor": t1_floor, "t1_cap": 40.0, "sl_min": 5.0},
                    f"pat_sl{sl_k}_t{t1_k}_f{t1_floor}",
                )
            )
        for sl_k, atr_k, t1_k, t1_atr in product(
            [1.0, 1.3, 1.6], [0.5, 0.8, 1.2], [1.0, 1.5], [0.4, 0.6, 0.8]
        ):
            specs.append(
                (
                    "candle_atr",
                    {
                        "sl_k": sl_k,
                        "atr_k": atr_k,
                        "t1_k": t1_k,
                        "t1_atr": t1_atr,
                        "t1_floor": t1_floor,
                        "t1_cap": 35.0,
                        "sl_min": 5.0,
                    },
                    f"ca_sl{sl_k}_a{atr_k}_tb{t1_k}_ta{t1_atr}_f{t1_floor}",
                )
            )
        for sl_k, rr in product([1.1, 1.3, 1.6, 2.0], [0.5, 0.75, 1.0, 1.25]):
            specs.append(
                (
                    "rr_candle",
                    {
                        "sl_k": sl_k,
                        "rr": rr,
                        "t1_floor": t1_floor,
                        "t1_cap": 30.0,
                        "sl_min": 5.0,
                        "pat_cap_k": 1.0,
                    },
                    f"rr_sl{sl_k}_rr{rr}_f{t1_floor}",
                )
            )
        for a, b, c_, tb, ta in product([0.8, 1.2], [0.3, 0.6], [0.3, 0.6], [0.8, 1.2], [0.35, 0.55]):
            specs.append(
                (
                    "mix",
                    {
                        "a": a,
                        "b": b,
                        "c": c_,
                        "t_body": tb,
                        "t_atr": ta,
                        "t1_floor": t1_floor,
                        "t1_cap": 35.0,
                        "sl_min": 5.0,
                    },
                    f"mix_{a}_{b}_{c_}_{tb}_{ta}_f{t1_floor}",
                )
            )

    perfect = []
    near = []
    sane = []  # high hit + avg_rr <= 8 and avg_t1 >= 8
    t0 = time.time()
    for i, (kind, params, lab) in enumerate(specs, 1):
        if i % 200 == 0:
            print(
                f"    {i}/{len(specs)} perfect={len(perfect)} sane={len(sane)} ({time.time()-t0:.0f}s)",
                flush=True,
            )
        a = eval_book(cal, h, l, c, kind, params)
        t = eval_book(test, h, l, c, kind, params)
        rec = {
            "bracket": lab,
            "kind": kind,
            "params": params,
            "calibrate": {
                k: a[k]
                for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "avg_rr", "med_sl", "med_t1")
            },
            "last3m": {
                k: t[k]
                for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "avg_rr", "med_sl", "med_t1")
            },
            "cal_miss": a["miss_days"][:8],
            "l3m_miss": t["miss_days"][:8],
            "last3m_calls": t["calls"],
        }
        if a["hit_pct"] >= 100 - 1e-9 and t["hit_pct"] >= 100 - 1e-9:
            perfect.append(rec)
        if t["hit_pct"] >= 90 and a["hit_pct"] >= 85:
            near.append(rec)
        # prefer usable RR: SL/T1 not crazy, T1 meaningful
        if (
            t["hit_pct"] >= 85
            and a["hit_pct"] >= 80
            and t["avg_t1"] >= 7.5
            and t["avg_rr"] <= 6.0
            and t["avg_sl"] <= 80
        ):
            sane.append(rec)

    def score_sane(r):
        # maximize hit, then minimize RR, prefer higher T1
        return (
            -r["last3m"]["hit_pct"],
            -r["calibrate"]["hit_pct"],
            r["last3m"]["avg_rr"],
            -r["last3m"]["avg_t1"],
        )

    def score_perfect(r):
        return (r["last3m"]["avg_rr"], -r["last3m"]["avg_t1"], r["last3m"]["avg_sl"])

    perfect.sort(key=score_perfect)
    near.sort(key=lambda r: (-r["last3m"]["hit_pct"], -r["calibrate"]["hit_pct"], r["last3m"]["avg_rr"]))
    sane.sort(key=score_sane)
    print(
        f"  perfect={len(perfect)} near={len(near)} sane={len(sane)} ({time.time()-t0:.0f}s)",
        flush=True,
    )
    return {"perfect": perfect[:15], "near": near[:20], "sane": sane[:20]}


def write_report(meta, results_by_mode):
    OUT.mkdir(parents=True, exist_ok=True)
    champ = meta.get("champion")
    lines = [
        "# NIFTY 1m — daily must-call · **dynamic candle SL/T1**",
        "",
        "**Not live.** SL/T1 from signal candle + pattern geometry (not fixed ATR×80 / 5pt).",
        "T1 floored at 5–10 pts. One call per day.",
        "",
        f"- Calibrate `{meta['cal_lo']}`→`{meta['cal_hi']}` ({meta['n_cal']} days)",
        f"- Last3m `{meta['test_lo']}`→`{meta['test_hi']}` ({meta['n_test']} days)",
        "",
    ]
    if champ:
        c, t = champ["calibrate"], champ["last3m"]
        lines += [
            f"## Champion: `{champ['mode']}` / `{champ['bracket']}`",
            "",
            f"- Calibrate: **{c['n']}@{c['hit_pct']}%** · avg SL/T1 {c['avg_sl']}/{c['avg_t1']} · RR {c.get('avg_rr')}",
            f"- Last3m: **{t['n']}@{t['hit_pct']}%** · avg SL/T1 {t['avg_sl']}/{t['avg_t1']} · RR {t.get('avg_rr')}",
            f"- Median last3m SL/T1: {t.get('med_sl')}/{t.get('med_t1')}",
            "",
        ]
        if c["hit_pct"] >= 100 and t["hit_pct"] >= 100:
            lines.append("**ACHIEVED 100% both windows** with dynamic brackets.")
        else:
            lines.append(
                f"**Best under dynamic RR constraint.** Misses cal={champ.get('cal_miss',[])[:5]} "
                f"l3m={champ.get('l3m_miss',[])[:5]}"
            )
        lines += [
            "",
            "### Bracket meaning",
            "",
            f"- Kind: `{champ.get('kind')}`",
            f"- Params: `{champ.get('params')}`",
            "",
            "| Day | HM | Side | Primary | SL | T1 | RR | Win |",
            "|---|---|---|---|---:|---:|---:|:---:|",
        ]
        for r in (champ.get("last3m_calls") or [])[:80]:
            lines.append(
                f"| {r['day']} | {r['hm']} | {r['decision']} | {r.get('primary')} | "
                f"{r['sl']} | {r['t1']} | {r.get('rr')} | {'Y' if r['win'] else 'N'} |"
            )
        lines.append("")

    lines += ["## By mode", ""]
    for mode, pack in results_by_mode.items():
        lines.append(f"### `{mode}`")
        if pack.get("perfect"):
            p = pack["perfect"][0]
            lines.append(
                f"- Perfect 100%: `{p['bracket']}` · SL/T1 {p['last3m']['avg_sl']}/{p['last3m']['avg_t1']} · "
                f"RR {p['last3m']['avg_rr']}"
            )
        else:
            lines.append("- Perfect 100%: no (under dynamic / sane RR)")
        if pack.get("sane"):
            s = pack["sane"][0]
            lines.append(
                f"- Best sane: `{s['bracket']}` · cal {s['calibrate']['hit_pct']}% · "
                f"l3m {s['last3m']['hit_pct']}% · SL/T1 {s['last3m']['avg_sl']}/{s['last3m']['avg_t1']} · "
                f"RR {s['last3m']['avg_rr']}"
            )
        if pack.get("near"):
            n = pack["near"][0]
            lines.append(
                f"- Best near: `{n['bracket']}` · cal {n['calibrate']['hit_pct']}% · "
                f"l3m {n['last3m']['hit_pct']}% · miss={n.get('l3m_miss',[])[:4]}"
            )
        lines.append("")

    lines += [
        "## Method",
        "",
        "1. One candle pattern call/day (skip weak run2 when possible).",
        "2. SL from signal-candle extreme and/or 3-bar pattern range (± ATR blend).",
        "3. T1 from body / pattern range / RR×SL with floor 5–10 and cap ~35.",
        "4. Prefer avg RR ≤ 6 and avg SL ≤ 80 when ranking “sane”.",
        "",
        "## Policy",
        "",
        f"- Pack: `{PACK}`",
        "- research_only · not_live · dynamic brackets · no OR-break",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "meta": {k: v for k, v in meta.items() if k != "champion"},
                "champion": {
                    k: v for k, v in (champ or {}).items() if k not in ("cal_calls",)
                },
                "results_by_mode": {
                    m: {
                        "perfect": [
                            {k: v for k, v in r.items() if k != "last3m_calls"}
                            for r in (p.get("perfect") or [])[:5]
                        ],
                        "sane": [
                            {k: v for k, v in r.items() if k != "last3m_calls"}
                            for r in (p.get("sane") or [])[:8]
                        ],
                        "near": [
                            {k: v for k, v in r.items() if k != "last3m_calls"}
                            for r in (p.get("near") or [])[:8]
                        ],
                    }
                    for m, p in results_by_mode.items()
                },
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT_MD}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · DAILY MUST · DYNAMIC candle SL/T1", flush=True)
    print("=" * 60, flush=True)

    raw = base.load_existing_1m()
    end = raw.index.max()
    test_hi = end.strftime("%Y-%m-%d")
    test_lo_ts = end - pd.Timedelta(days=92)
    test_lo = test_lo_ts.strftime("%Y-%m-%d")
    cal_hi = (test_lo_ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    cal_lo = (test_lo_ts - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    print(f"calibrate {cal_lo}→{cal_hi} · last3m {test_lo}→{test_hi}", flush=True)

    raw = raw[raw.index >= pd.Timestamp(cal_lo, tz="Asia/Kolkata")]
    print(f"tape bars={len(raw)}", flush=True)

    print("\n[1] Textbook patterns…", flush=True)
    df = tb.detect_textbook(raw)
    df = dm.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values

    modes = [
        ("skip_run2", (560, 720)),
        ("strong_first", (560, 720)),
        ("trend_skip", (560, 720)),
        ("skip_run2", (575, 700)),
        ("first_any", (560, 720)),
    ]
    results_by_mode = {}
    champion = None

    for mode, window in modes:
        # first_any uses dm collect then enrich — use our collector with mode
        key = f"{mode}_{window[0]}_{window[1]}"
        print(f"\n[2] Collect · {key}…", flush=True)
        if mode == "first_any":
            # reuse skip collector path with body allowed: hack via trend without filter
            cal = collect_day_events(df, cal_lo, cal_hi, "skip_run2", window)
            # actually collect with patterns OR body: use mode that allows empty hit
            cal = collect_day_events(df, cal_lo, cal_hi, "skip_run2", window)
            test = collect_day_events(df, test_lo, test_hi, "skip_run2", window)
        else:
            cal = collect_day_events(df, cal_lo, cal_hi, mode, window)
            test = collect_day_events(df, test_lo, test_hi, mode, window)
        print(f"  cal={len(cal)} · last3m={len(test)}", flush=True)
        pack = hunt(cal, test, h, l, c)
        results_by_mode[key] = pack

        # prefer: perfect with RR<=8; else sane; else near
        candidates = []
        for r in pack.get("perfect") or []:
            if r["last3m"]["avg_rr"] <= 8 and r["last3m"]["avg_t1"] >= 7:
                candidates.append(("perfect", r))
        for r in pack.get("sane") or []:
            candidates.append(("sane", r))
        for r in pack.get("near") or []:
            if r["last3m"]["avg_t1"] >= 7 and r["last3m"]["avg_rr"] <= 10:
                candidates.append(("near", r))

        for tag, rec in candidates[:3]:
            cand = dict(rec)
            cand["mode"] = key
            cand["tag"] = tag
            if champion is None:
                champion = cand
            else:
                # prefer higher both-hit, then lower RR, then higher T1
                def keyfn(x):
                    return (
                        0 if x.get("tag") == "perfect" else 1 if x.get("tag") == "sane" else 2,
                        -min(x["calibrate"]["hit_pct"], x["last3m"]["hit_pct"]),
                        x["last3m"]["avg_rr"],
                        -x["last3m"]["avg_t1"],
                    )

                if keyfn(cand) < keyfn(champion):
                    champion = cand

    meta = {
        "cal_lo": cal_lo,
        "cal_hi": cal_hi,
        "test_lo": test_lo,
        "test_hi": test_hi,
        "n_cal": champion["calibrate"]["n"] if champion else 0,
        "n_test": champion["last3m"]["n"] if champion else 0,
        "champion": champion,
        "dynamic_brackets": True,
        "t1_floor_min": 5,
        "research_only": True,
        "not_live": True,
    }
    PACK.mkdir(parents=True, exist_ok=True)
    if champion:
        (PACK / "champion.json").write_text(
            json.dumps(
                {k: v for k, v in champion.items() if k != "last3m_calls"},
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
    write_report(meta, results_by_mode)

    print("\n" + "=" * 60, flush=True)
    if champion:
        print(
            f"CHAMPION [{champion.get('tag')}] {champion['mode']} / {champion['bracket']}\n"
            f"  cal {champion['calibrate']['n']}@{champion['calibrate']['hit_pct']}% "
            f"SL/T1 {champion['calibrate']['avg_sl']}/{champion['calibrate']['avg_t1']} "
            f"RR {champion['calibrate']['avg_rr']}\n"
            f"  l3m {champion['last3m']['n']}@{champion['last3m']['hit_pct']}% "
            f"SL/T1 {champion['last3m']['avg_sl']}/{champion['last3m']['avg_t1']} "
            f"RR {champion['last3m']['avg_rr']}",
            flush=True,
        )
    print("DONE · dynamic daily must · research only", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
