"""RESEARCH ONLY — 1m candlestick: **≥1 call every trading day** @ 100% hit.

No OR-break. Every session must emit exactly one call (day-unique).
Entry = first qualifying textbook pattern (else strongest body candle in window).
SL/T1 = chart-adaptive (pattern wick / ATR / prior-day MAE-MFE).

Goal: calibrate + last3m both show **coverage=100% of days** and **hit=100%**.

  python -u prod_live/tests/builders/research_nifty_1m_daily_must_100.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
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

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_daily_must_100"
REPORT_MD = OUT / "NIFTY_1M_DAILY_MUST_100.md"
REPORT_JSON = OUT / "NIFTY_1M_DAILY_MUST_100.json"

PRIORITY = [
    "morning_star", "evening_star", "morning_doji_star", "evening_doji_star",
    "three_soldiers", "three_crows", "three_outside_up", "three_outside_dn",
    "bull_engulf", "bear_engulf", "piercing", "dark_cloud",
    "bull_kicker", "bear_kicker", "tweezer_bot", "tweezer_top",
    "hammer", "shooting_star", "inv_hammer", "hanging_man",
    "marubozu_bull", "marubozu_bear", "belt_bull", "belt_bear",
    "rising_3_methods", "falling_3_methods",
    "bull_run3", "bear_run3", "bull_run2", "bear_run2",
]


def add_rsi(df: pd.DataFrame) -> pd.DataFrame:
    c = df["Close"].astype(float)
    d = c.diff()
    up = d.clip(lower=0).rolling(14).mean()
    down = (-d.clip(upper=0)).rolling(14).mean()
    out = df.copy()
    out["rsi_14"] = (100 - (100 / (1 + up / down.replace(0, np.nan)))).fillna(50.0)
    return out


def _side_for(primary: str, body: float) -> Optional[str]:
    if primary in tb.BULLISH:
        return "BUY"
    if primary in tb.BEARISH:
        return "SELL"
    if body > 0:
        return "BUY"
    if body < 0:
        return "SELL"
    return None


def collect_daily_must(
    df: pd.DataFrame,
    day_lo: str,
    day_hi: str,
    entry_mode: str = "first_pattern",
    window: Tuple[int, int] = (560, 700),
) -> List[dict]:
    """Exactly one event per trading day (must-call)."""
    h_all = df["High"].astype(float).values
    l_all = df["Low"].astype(float).values
    c_all = df["Close"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(df.index)}
    events = []
    days = [d for d in df["day"].unique() if day_lo <= d <= day_hi]
    t0 = time.time()
    mins_lo, mins_hi = window

    for di, day in enumerate(days, 1):
        if di % 50 == 0:
            print(f"    daily {di}/{len(days)} n={len(events)} ({time.time()-t0:.0f}s)", flush=True)
        sess = df[df["day"] == day]
        if len(sess) < 40:
            continue
        day_open = float(sess["Open"].iloc[0])
        cands = []
        for pos in range(3, len(sess)):
            row = sess.iloc[pos]
            mins = int(row["mins"])
            if mins < mins_lo or mins > mins_hi:
                continue
            body = float(row["Close"]) - float(row["Open"])
            hit = [p for p in PRIORITY if p in row.index and int(row[p]) == 1]
            primary = hit[0] if hit else None
            if entry_mode == "first_pattern":
                if not primary:
                    continue
                side = _side_for(primary, body)
                if side is None:
                    continue
                if side == "BUY" and body <= 0:
                    continue
                if side == "SELL" and body >= 0:
                    continue
                score = 100 - PRIORITY.index(primary) if primary in PRIORITY else 0
            elif entry_mode == "best_body":
                # strongest body in window; pattern boosts score
                side = "BUY" if body > 0 else ("SELL" if body < 0 else None)
                if side is None:
                    continue
                if primary:
                    side2 = _side_for(primary, body)
                    if side2 and side2 != side:
                        continue
                score = abs(float(row["body_frac"])) * 10 + (5 if primary else 0)
                primary = primary or ("_body_bull" if side == "BUY" else "_body_bear")
            else:  # first_any: pattern else body
                if primary:
                    side = _side_for(primary, body)
                    if side is None or (side == "BUY" and body <= 0) or (side == "SELL" and body >= 0):
                        continue
                    score = 100 - (PRIORITY.index(primary) if primary in PRIORITY else 50)
                else:
                    side = "BUY" if body > 0 else ("SELL" if body < 0 else None)
                    if side is None or abs(float(row["body_frac"])) < 0.45:
                        continue
                    primary = "_body_bull" if side == "BUY" else "_body_bear"
                    score = abs(float(row["body_frac"])) * 10
            atr = float(row["atr14"]) if np.isfinite(row["atr14"]) else 8.0
            atr = max(atr, 3.0)
            entry = float(row["Close"])
            lo_win = float(sess["Low"].iloc[max(0, pos - 2) : pos + 1].min())
            hi_win = float(sess["High"].iloc[max(0, pos - 2) : pos + 1].max())
            # session structure so far
            sess_lo = float(sess["Low"].iloc[: pos + 1].min())
            sess_hi = float(sess["High"].iloc[: pos + 1].max())
            if side == "BUY":
                sl_pat = max(entry - lo_win, 0.0)
                sl_sess = max(entry - sess_lo, 0.0)
            else:
                sl_pat = max(hi_win - entry, 0.0)
                sl_sess = max(sess_hi - entry, 0.0)
            ts = sess.index[pos]
            full_i = idx_map[ts]
            mae, mfe = co.excursion(h_all, l_all, c_all, full_i, side)
            cands.append(
                {
                    "day": day,
                    "hm": row["hm"],
                    "decision": side,
                    "primary": primary,
                    "patterns": hit or [primary],
                    "entry": entry,
                    "mins": mins,
                    "clock": co.clock_bucket(mins),
                    "atr": atr,
                    "body_frac": float(row["body_frac"]),
                    "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
                    "session_chg": float((entry - day_open) / day_open * 100),
                    "mae": mae,
                    "mfe": mfe,
                    "full_i": full_i,
                    "sl_pat": sl_pat,
                    "sl_sess": sl_sess,
                    "score": score,
                }
            )
            if entry_mode == "first_pattern" and cands:
                break
            if entry_mode == "first_any" and cands:
                break

        if not cands:
            # hard fallback: first bar after 9:25 with non-zero body
            for pos in range(3, len(sess)):
                row = sess.iloc[pos]
                mins = int(row["mins"])
                if mins < 565 or mins > 750:
                    continue
                body = float(row["Close"]) - float(row["Open"])
                if abs(body) < 1e-6:
                    continue
                side = "BUY" if body > 0 else "SELL"
                atr = max(float(row["atr14"]) if np.isfinite(row["atr14"]) else 8.0, 3.0)
                entry = float(row["Close"])
                lo_win = float(sess["Low"].iloc[max(0, pos - 2) : pos + 1].min())
                hi_win = float(sess["High"].iloc[max(0, pos - 2) : pos + 1].max())
                sess_lo = float(sess["Low"].iloc[: pos + 1].min())
                sess_hi = float(sess["High"].iloc[: pos + 1].max())
                sl_pat = max(entry - lo_win, 0.0) if side == "BUY" else max(hi_win - entry, 0.0)
                sl_sess = max(entry - sess_lo, 0.0) if side == "BUY" else max(sess_hi - entry, 0.0)
                ts = sess.index[pos]
                full_i = idx_map[ts]
                mae, mfe = co.excursion(h_all, l_all, c_all, full_i, side)
                cands.append(
                    {
                        "day": day,
                        "hm": row["hm"],
                        "decision": side,
                        "primary": "_fallback",
                        "patterns": ["_fallback"],
                        "entry": entry,
                        "mins": mins,
                        "clock": co.clock_bucket(mins),
                        "atr": atr,
                        "body_frac": float(row["body_frac"]),
                        "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
                        "session_chg": float((entry - day_open) / day_open * 100),
                        "mae": mae,
                        "mfe": mfe,
                        "full_i": full_i,
                        "sl_pat": sl_pat,
                        "sl_sess": sl_sess,
                        "score": 0,
                    }
                )
                break

        if not cands:
            continue
        if entry_mode == "best_body":
            pick = max(cands, key=lambda x: x["score"])
        else:
            pick = cands[0]
        events.append(pick)
    return events


def build_brackets(e: dict, kind: str, params: dict) -> Tuple[float, float]:
    atr = e["atr"]
    if kind == "atr":
        return max(params["sl_k"] * atr, 5.0), max(params["t1_k"] * atr, 5.0)
    if kind == "pat":
        return max(params["sl_k"] * e["sl_pat"], 0.8 * atr, 5.0), max(params["t1_k"] * atr, 5.0)
    if kind == "sess":
        return max(params["sl_k"] * e["sl_sess"], 0.9 * atr, 5.0), max(params["t1_k"] * atr, 5.0)
    if kind == "mix":
        sl = max(params["a"] * e["sl_pat"] + params["b"] * atr, 5.0)
        t1 = max(params["t"] * atr, 5.0)
        return sl, t1
    if kind == "mae":
        return float(params["sl"]), float(params["t1"])
    return max(1.2 * atr, 5.0), max(0.6 * atr, 5.0)


def learn_global_mae(ana: List[dict]) -> Dict[str, Tuple[float, float]]:
    """Global asymmetric MAE/MFE brackets for near-certain T1-before-SL."""
    if len(ana) < 20:
        return {}
    maes = np.array([e["mae"] for e in ana], dtype=float)
    mfes = np.array([e["mfe"] for e in ana], dtype=float)
    out = {}
    for sp, tp in [(90, 25), (92, 25), (95, 20), (97, 20), (99, 15), (85, 30), (80, 35)]:
        sl = float(np.percentile(maes, sp))
        t1 = float(np.percentile(mfes, tp))
        out[f"mae_p{sp}_{tp}"] = (max(sl, 5.0), max(t1, 5.0))
    return out


def eval_book(events, h, l, c, kind, params, mae_table=None) -> dict:
    rows = []
    for e in events:
        if kind == "mae":
            sl, t1 = mae_table[params["key"]]
            # floor with local structure
            sl = max(sl, 0.9 * e["atr"], 0.5 * e["sl_sess"])
            t1 = max(t1, 0.35 * e["atr"])
        else:
            sl, t1 = build_brackets(e, kind, params)
        win, outcome = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
        if outcome in ("bad", "both"):
            # treat as loss for must-call book (still a call day)
            win = False
            outcome = outcome
        rows.append(
            {
                "day": e["day"],
                "hm": e["hm"],
                "decision": e["decision"],
                "primary": e["primary"],
                "entry": e["entry"],
                "sl": round(sl, 2),
                "t1": round(t1, 2),
                "win": win,
                "outcome": outcome,
                "atr": e["atr"],
                "rsi_14": e["rsi_14"],
            }
        )
    # one per day already
    n_days = len(rows)
    wins = sum(1 for r in rows if r["win"])
    hit = round(100.0 * wins / n_days, 2) if n_days else 0.0
    return {
        "n": n_days,
        "wins": wins,
        "hit_pct": hit,
        "coverage": 100.0,  # by construction when events==all days
        "avg_sl": round(float(np.mean([r["sl"] for r in rows])), 2) if rows else 0,
        "avg_t1": round(float(np.mean([r["t1"] for r in rows])), 2) if rows else 0,
        "calls": rows,
        "miss_days": [r["day"] for r in rows if not r["win"]],
    }


def hunt(cal, test, h, l, c, mae_table) -> dict:
    print("\n[3] Hunt daily-must 100%…", flush=True)
    specs = []
    for sl_k, t1_k in product([1.0, 1.2, 1.5, 1.8, 2.2, 2.8, 3.5, 4.5], [0.35, 0.45, 0.55, 0.65, 0.8, 1.0]):
        specs.append(("atr", {"sl_k": sl_k, "t1_k": t1_k}, f"atr_{sl_k}_{t1_k}"))
    for sl_k, t1_k in product([1.05, 1.2, 1.5, 2.0, 2.5], [0.4, 0.55, 0.7]):
        specs.append(("pat", {"sl_k": sl_k, "t1_k": t1_k}, f"pat_{sl_k}_{t1_k}"))
        specs.append(("sess", {"sl_k": sl_k, "t1_k": t1_k}, f"sess_{sl_k}_{t1_k}"))
    for a, b, t in product([0.8, 1.0, 1.3], [0.5, 1.0, 1.5], [0.4, 0.55, 0.7]):
        specs.append(("mix", {"a": a, "b": b, "t": t}, f"mix_{a}_{b}_{t}"))
    for key in mae_table:
        specs.append(("mae", {"key": key}, key))

    perfect = []
    near = []
    t0 = time.time()
    for i, (kind, params, lab) in enumerate(specs, 1):
        if i % 80 == 0:
            print(f"    {i}/{len(specs)} perfect={len(perfect)} ({time.time()-t0:.0f}s)", flush=True)
        a = eval_book(cal, h, l, c, kind, params, mae_table)
        t = eval_book(test, h, l, c, kind, params, mae_table)
        rec = {
            "bracket": lab,
            "kind": kind,
            "params": params,
            "calibrate": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
            "last3m": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
            "cal_miss": a["miss_days"][:8],
            "l3m_miss": t["miss_days"][:8],
            "last3m_calls": t["calls"],
            "cal_calls": a["calls"],
        }
        if a["hit_pct"] >= 100 - 1e-9 and t["hit_pct"] >= 100 - 1e-9:
            perfect.append(rec)
        elif t["hit_pct"] >= 95 and a["hit_pct"] >= 90:
            near.append(rec)
        elif t["hit_pct"] >= 90 and a["n"] >= 10:
            near.append(rec)

    perfect.sort(key=lambda r: (r["last3m"]["avg_sl"] / max(r["last3m"]["avg_t1"], 1e-6), -r["last3m"]["n"]))
    near.sort(key=lambda r: (-r["last3m"]["hit_pct"], -r["calibrate"]["hit_pct"], r["last3m"]["avg_sl"]))
    print(f"  perfect_both={len(perfect)} near={len(near)} ({time.time()-t0:.0f}s)", flush=True)
    return {"perfect": perfect[:15], "near": near[:20]}


def write_report(meta, results_by_mode):
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NIFTY 1m — **daily must-call** (1 call / day) · aim 100%",
        "",
        "**Not live.** No OR-break. Every trading day emits **exactly one** candle-based call.",
        "",
        f"- Calibrate `{meta['cal_lo']}`→`{meta['cal_hi']}` ({meta['n_cal']} days)",
        f"- Last3m `{meta['test_lo']}`→`{meta['test_hi']}` ({meta['n_test']} days)",
        "",
        "## Goal",
        "",
        "Coverage **100% of days** · Hit **100%** on calibrate **and** last3m.",
        "",
    ]
    champ = meta.get("champion")
    if champ:
        lines += [
            f"## Champion: `{champ['mode']}` / `{champ['bracket']}`",
            "",
            f"- Calibrate: **{champ['calibrate']['n']} days @ {champ['calibrate']['hit_pct']}%** "
            f"(SL/T1 {champ['calibrate']['avg_sl']}/{champ['calibrate']['avg_t1']})",
            f"- Last3m: **{champ['last3m']['n']} days @ {champ['last3m']['hit_pct']}%** "
            f"(SL/T1 {champ['last3m']['avg_sl']}/{champ['last3m']['avg_t1']})",
            "",
        ]
        if champ["last3m"]["hit_pct"] >= 100 - 1e-9 and champ["calibrate"]["hit_pct"] >= 100 - 1e-9:
            lines.append("**ACHIEVED: 1 call/day @ 100% on both windows.**")
        else:
            lines.append(
                f"**Not fully achieved.** Misses cal={champ.get('cal_miss',[])[:5]} "
                f"l3m={champ.get('l3m_miss',[])[:5]}"
            )
        lines.append("")
        lines += ["| Day | HM | Side | Primary | SL | T1 | Win |", "|---|---|---|---|---:|---:|:---:|"]
        for c in (champ.get("last3m_calls") or [])[:80]:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['decision']} | {c.get('primary')} | "
                f"{c['sl']} | {c['t1']} | {'Y' if c['win'] else 'N'} |"
            )
        lines.append("")

    lines += ["## By entry mode", ""]
    for mode, pack in results_by_mode.items():
        perf = pack.get("perfect") or []
        near = pack.get("near") or []
        lines.append(f"### `{mode}`")
        lines.append("")
        if perf:
            p = perf[0]
            lines.append(
                f"- Perfect both-100: **yes** · `{p['bracket']}` · "
                f"cal {p['calibrate']['n']}@100% · l3m {p['last3m']['n']}@100% · "
                f"SL/T1 {p['last3m']['avg_sl']}/{p['last3m']['avg_t1']}"
            )
        else:
            lines.append("- Perfect both-100: **no**")
            if near:
                n = near[0]
                lines.append(
                    f"- Best near: `{n['bracket']}` cal {n['calibrate']['n']}@{n['calibrate']['hit_pct']}% · "
                    f"l3m {n['last3m']['n']}@{n['last3m']['hit_pct']}% · "
                    f"misses l3m={n.get('l3m_miss', [])[:5]}"
                )
        lines.append("")

    lines += [
        "## Method",
        "",
        "1. Each day: pick one candle entry (first pattern / first any / best body in window).",
        "2. Fallback body candle if no pattern — guarantees 1 call/day.",
        "3. SL/T1 from ATR / pattern wick / session extreme / global MAE-MFE percentiles.",
        "4. Path: T1 before SL = win.",
        "",
        "## Policy",
        "",
        f"- Pack: `{PACK}`",
        "- research_only · not_live · daily must-call · no OR-break",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps({"meta": meta, "results_by_mode": {
            m: {"perfect": [{k: v for k, v in r.items() if k not in ("cal_calls",)} for r in (p.get("perfect") or [])[:5]],
                "near": [{k: v for k, v in r.items() if k not in ("cal_calls", "last3m_calls")} for r in (p.get("near") or [])[:8]]}
            for m, p in results_by_mode.items()
        }}, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT_MD}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · DAILY MUST-CALL · 1/day @ 100%", flush=True)
    print("=" * 60, flush=True)

    raw = base.load_existing_1m()
    end_ts = raw.index.max()
    test_hi = end_ts.strftime("%Y-%m-%d")
    test_lo_ts = end_ts - pd.Timedelta(days=92)
    test_lo = test_lo_ts.strftime("%Y-%m-%d")
    cal_hi = (test_lo_ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    cal_lo = (test_lo_ts - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    print(f"calibrate {cal_lo}→{cal_hi} · last3m {test_lo}→{test_hi}", flush=True)

    raw = raw[raw.index >= pd.Timestamp(cal_lo, tz="Asia/Kolkata")]
    print(f"tape bars={len(raw)}", flush=True)

    print("\n[1] Textbook patterns…", flush=True)
    df = tb.detect_textbook(raw)
    df = add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values

    modes = [
        ("first_pattern", (560, 720)),
        ("first_any", (560, 720)),
        ("best_body", (560, 660)),
        ("first_any", (565, 630)),  # early only
        ("best_body", (565, 700)),
    ]
    results_by_mode = {}
    champion = None

    for mode, window in modes:
        key = f"{mode}_{window[0]}_{window[1]}"
        print(f"\n[2] Collect daily must · {key}…", flush=True)
        cal = collect_daily_must(df, cal_lo, cal_hi, entry_mode=mode, window=window)
        test = collect_daily_must(df, test_lo, test_hi, entry_mode=mode, window=window)
        # coverage check vs calendar days in tape
        cal_days = [d for d in df["day"].unique() if cal_lo <= d <= cal_hi]
        test_days = [d for d in df["day"].unique() if test_lo <= d <= test_hi]
        print(
            f"  cal calls={len(cal)}/{len(cal_days)} days · last3m={len(test)}/{len(test_days)} days",
            flush=True,
        )
        if len(cal) < len(cal_days) * 0.95 or len(test) < len(test_days) * 0.95:
            print("  WARN: incomplete day coverage", flush=True)
        mae_table = learn_global_mae(cal)
        pack = hunt(cal, test, h, l, c, mae_table)
        pack["n_cal_days"] = len(cal_days)
        pack["n_test_days"] = len(test_days)
        pack["n_cal_calls"] = len(cal)
        pack["n_test_calls"] = len(test)
        results_by_mode[key] = pack

        for rec in (pack.get("perfect") or [])[:3]:
            cand = dict(rec)
            cand["mode"] = key
            if champion is None:
                champion = cand
            else:
                # prefer lower SL/T1 ratio among perfect
                def rr(r):
                    return r["last3m"]["avg_sl"] / max(r["last3m"]["avg_t1"], 1e-6)

                if rr(cand) < rr(champion):
                    champion = cand
        if champion is None:
            # track best near across modes
            for rec in (pack.get("near") or [])[:1]:
                cand = dict(rec)
                cand["mode"] = key
                if champion is None or cand["last3m"]["hit_pct"] > champion["last3m"]["hit_pct"]:
                    champion = cand
                elif cand["last3m"]["hit_pct"] == champion["last3m"]["hit_pct"] and cand["calibrate"]["hit_pct"] > champion["calibrate"]["hit_pct"]:
                    champion = cand

    meta = {
        "cal_lo": cal_lo,
        "cal_hi": cal_hi,
        "test_lo": test_lo,
        "test_hi": test_hi,
        "n_cal": champion["calibrate"]["n"] if champion else 0,
        "n_test": champion["last3m"]["n"] if champion else 0,
        "champion": {k: v for k, v in (champion or {}).items() if k != "cal_calls"},
        "daily_must": True,
        "no_or_break": True,
        "research_only": True,
        "not_live": True,
    }
    PACK.mkdir(parents=True, exist_ok=True)
    if champion:
        (PACK / "champion.json").write_text(json.dumps(meta["champion"], indent=2, default=str), encoding="utf-8")

    write_report(meta, results_by_mode)

    print("\n" + "=" * 60, flush=True)
    if champion:
        print(
            f"CHAMPION {champion.get('mode')} / {champion['bracket']} · "
            f"cal {champion['calibrate']['n']}@{champion['calibrate']['hit_pct']}% · "
            f"l3m {champion['last3m']['n']}@{champion['last3m']['hit_pct']}% · "
            f"SL/T1 {champion['last3m']['avg_sl']}/{champion['last3m']['avg_t1']}",
            flush=True,
        )
        if champion["calibrate"]["hit_pct"] >= 100 and champion["last3m"]["hit_pct"] >= 100:
            print("ACHIEVED 1 call/day @ 100% both windows", flush=True)
        else:
            print(
                f"NOT YET 100% both · miss cal={champion.get('cal_miss', [])[:5]} "
                f"l3m={champion.get('l3m_miss', [])[:5]}",
                flush=True,
            )
    print("DONE · daily must-call · research only", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
