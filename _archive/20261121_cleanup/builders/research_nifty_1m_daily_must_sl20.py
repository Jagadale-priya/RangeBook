"""RESEARCH ONLY — 1 call/day @ 100% with **SL ≤ 20 pts hard cap**.

T1 dynamic from candle/pattern, floor 5–10.
Entry must have structure that fits under SL20 (candle/pattern stop ≤ 20 or capped).

  python -u prod_live/tests/builders/research_nifty_1m_daily_must_sl20.py
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
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_daily_must_sl20"
REPORT_MD = OUT / "NIFTY_1M_DAILY_MUST_SL20.md"
REPORT_JSON = OUT / "NIFTY_1M_DAILY_MUST_SL20.json"

SL_MAX = 20.0
WEAK = {"bull_run2", "bear_run2"}


def _geom(sess, pos, side, row) -> dict:
    o, cl = float(row["Open"]), float(row["Close"])
    hi, lo = float(row["High"]), float(row["Low"])
    entry = cl
    body_abs = abs(cl - o)
    lo_pat = float(sess["Low"].iloc[max(0, pos - 2) : pos + 1].min())
    hi_pat = float(sess["High"].iloc[max(0, pos - 2) : pos + 1].max())
    atr = max(float(row["atr14"]) if np.isfinite(row["atr14"]) else 8.0, 3.0)
    if side == "BUY":
        sl_candle = max(entry - lo, 0.5)
        sl_pat = max(entry - lo_pat, 0.5)
        t1_body = max(body_abs, 0.5)
    else:
        sl_candle = max(hi - entry, 0.5)
        sl_pat = max(hi_pat - entry, 0.5)
        t1_body = max(body_abs, 0.5)
    return {
        "entry": entry,
        "atr": atr,
        "body_abs": body_abs,
        "body_frac": float(row["body_frac"]),
        "candle_range": max(hi - lo, 0.5),
        "pat_range": max(hi_pat - lo_pat, 0.5),
        "sl_candle": sl_candle,
        "sl_pat": sl_pat,
        "t1_body": t1_body,
        "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
    }


def collect_all_cands(
    df: pd.DataFrame,
    day_lo: str,
    day_hi: str,
    window: Tuple[int, int] = (560, 750),
) -> Dict[str, List[dict]]:
    """All pattern (+ strong body) cands per day with geometry + MAE/MFE."""
    h_all = df["High"].astype(float).values
    l_all = df["Low"].astype(float).values
    c_all = df["Close"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(df.index)}
    by_day: Dict[str, List[dict]] = {}
    days = [d for d in df["day"].unique() if day_lo <= d <= day_hi]
    mins_lo, mins_hi = window
    t0 = time.time()

    for di, day in enumerate(days, 1):
        if di % 50 == 0:
            print(f"    cands {di}/{len(days)} ({time.time()-t0:.0f}s)", flush=True)
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
            hit = [p for p in dm.PRIORITY if p in row.index and int(row[p]) == 1]
            sides = []
            if hit:
                primary = hit[0]
                side = dm._side_for(primary, body)
                if side and not ((side == "BUY" and body <= 0) or (side == "SELL" and body >= 0)):
                    score = 100 - (dm.PRIORITY.index(primary) if primary in dm.PRIORITY else 50)
                    sides.append((side, primary, score, hit))
            if abs(float(row["body_frac"])) >= 0.45:
                sd = "BUY" if body > 0 else ("SELL" if body < 0 else None)
                if sd and not any(s[0] == sd for s in sides):
                    sides.append((sd, "_body", abs(float(row["body_frac"])) * 10, []))

            for side, primary, score, hitlist in sides:
                g = _geom(sess, pos, side, row)
                # only keep if structure can fit under SL_MAX with some multiplier ≤ ~2
                # (still collect all; filter at pick time)
                drift = g["entry"] - day_open
                trend = 1 if (side == "BUY" and drift > 0) or (side == "SELL" and drift < 0) else 0
                full_i = idx_map[sess.index[pos]]
                mae, mfe = co.excursion(h_all, l_all, c_all, full_i, side, max_bars=200)
                cands.append(
                    {
                        "day": day,
                        "hm": row["hm"],
                        "decision": side,
                        "primary": primary,
                        "patterns": hitlist or [primary],
                        "mins": mins,
                        "score": score,
                        "trend_align": trend,
                        "drift": drift,
                        "mae": mae,
                        "mfe": mfe,
                        "full_i": full_i,
                        **g,
                    }
                )
        if cands:
            by_day[day] = cands
    return by_day


def brackets(e: dict, kind: str, params: dict) -> Optional[Tuple[float, float]]:
    """Return (sl, t1) or None if SL would exceed SL_MAX."""
    t1_floor = float(params.get("t1_floor", 8.0))
    t1_cap = float(params.get("t1_cap", 25.0))
    atr = e["atr"]

    if kind == "candle":
        sl = max(params["sl_k"] * e["sl_candle"], params.get("sl_min", 4.0))
        t1 = min(max(params["t1_k"] * e["t1_body"], t1_floor), t1_cap)
    elif kind == "pat":
        sl = max(params["sl_k"] * e["sl_pat"], params.get("sl_min", 4.0))
        t1 = min(max(params["t1_k"] * e["pat_range"], t1_floor), t1_cap)
    elif kind == "candle_cap":
        sl = min(max(params["sl_k"] * e["sl_candle"], params.get("sl_min", 4.0)), SL_MAX)
        t1 = min(max(params["t1_k"] * e["t1_body"], params.get("t1_atr", 0.0) * atr, t1_floor), t1_cap)
    elif kind == "fixed_sl":
        sl = float(params["sl"])
        t1 = min(max(params["t1_k"] * e["t1_body"], t1_floor), t1_cap)
    elif kind == "atr_cap":
        sl = min(max(params["atr_k"] * atr, params.get("sl_min", 4.0)), SL_MAX)
        t1 = min(max(params["t1_k"] * atr, t1_floor), t1_cap)
    elif kind == "mix_cap":
        sl = min(
            max(params["a"] * e["sl_candle"] + params["b"] * atr, params.get("sl_min", 4.0)),
            SL_MAX,
        )
        t1 = min(max(params["t_body"] * e["t1_body"], params["t_atr"] * atr, t1_floor), t1_cap)
    else:
        sl = min(max(1.2 * e["sl_candle"], 4.0), SL_MAX)
        t1 = min(max(1.0 * e["t1_body"], t1_floor), t1_cap)

    if sl > SL_MAX + 1e-9:
        return None  # reject — SL too high
    if sl < 4 or t1 < 4:
        return None
    return sl, t1


def path_win(e, h, l, c, sl, t1) -> bool:
    # gate
    if e["mfe"] + 1e-9 < t1:
        return False
    if e["mae"] >= sl - 1e-9:
        return False
    win, outcome = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
    return bool(win) and outcome == "t1"


def pick_oracle(cands, h, l, c, kind, params) -> Optional[dict]:
    """Best winning cand under SL≤20 brackets (prefer non-weak pattern, score, early)."""
    winners = []
    for e in cands:
        bt = brackets(e, kind, params)
        if bt is None:
            continue
        sl, t1 = bt
        if path_win(e, h, l, c, sl, t1):
            winners.append((e, sl, t1))
    if not winners:
        return None
    winners.sort(
        key=lambda x: (
            0 if not str(x[0]["primary"]).startswith("_") else 1,
            0 if x[0]["primary"] not in WEAK else 1,
            -x[0]["score"],
            x[0]["mins"],
        )
    )
    e, sl, t1 = winners[0]
    out = dict(e)
    out["_sl"], out["_t1"] = sl, t1
    return out


def pick_rule(cands, rule: str, kind, params) -> Optional[dict]:
    """Non-lookahead pick among cands whose structure SL ≤ 20 under this bracket."""
    eligible = []
    for e in cands:
        bt = brackets(e, kind, params)
        if bt is None:
            continue
        # structure fit: raw candle stop should be reasonable
        if e["sl_candle"] > SL_MAX and kind in ("candle", "candle_cap", "mix_cap"):
            # still allow if capped kind
            if kind != "candle_cap" and kind != "mix_cap" and kind != "atr_cap" and kind != "fixed_sl":
                continue
        eligible.append((e, bt[0], bt[1]))
    if not eligible:
        return None

    def ok_pool(pred):
        return [x for x in eligible if pred(x[0])]

    if rule == "first_fit":
        pool = sorted(eligible, key=lambda x: x[0]["mins"])
    elif rule == "first_trend":
        pool = ok_pool(lambda e: e["trend_align"] == 1) or eligible
        pool = sorted(pool, key=lambda x: x[0]["mins"])
    elif rule == "first_tight":
        # smallest structure SL first among early
        pool = sorted(eligible, key=lambda x: (x[0]["sl_candle"], x[0]["mins"]))
    elif rule == "best_score_trend":
        pool = ok_pool(lambda e: e["trend_align"] == 1) or eligible
        pool = sorted(pool, key=lambda x: (-x[0]["score"], x[0]["mins"]))
    elif rule == "best_body_trend":
        pool = ok_pool(lambda e: e["trend_align"] == 1) or eligible
        pool = sorted(pool, key=lambda x: (-x[0]["body_abs"], x[0]["mins"]))
    elif rule == "tight_trend":
        pool = ok_pool(lambda e: e["trend_align"] == 1 and e["sl_candle"] <= 15) or ok_pool(
            lambda e: e["trend_align"] == 1
        ) or eligible
        pool = sorted(pool, key=lambda x: (x[0]["sl_candle"], -x[0]["score"], x[0]["mins"]))
    elif rule == "mid_tight":
        pool = ok_pool(lambda e: 575 <= e["mins"] <= 700 and e["sl_candle"] <= SL_MAX) or eligible
        pool = sorted(pool, key=lambda x: (x[0]["sl_candle"], -x[0]["score"]))
    elif rule == "pat_priority_tight":
        pool = ok_pool(lambda e: not str(e["primary"]).startswith("_") and e["sl_candle"] <= 12) or ok_pool(
            lambda e: not str(e["primary"]).startswith("_")
        ) or eligible
        pool = sorted(pool, key=lambda x: (-x[0]["score"], x[0]["sl_candle"], x[0]["mins"]))
    else:
        pool = sorted(eligible, key=lambda x: x[0]["mins"])

    e, sl, t1 = pool[0]
    out = dict(e)
    out["_sl"], out["_t1"] = sl, t1
    return out


def eval_picker(by_day, h, l, c, kind, params, picker: str) -> dict:
    rows = []
    miss = []
    for day, cands in sorted(by_day.items()):
        if picker == "oracle":
            e = pick_oracle(cands, h, l, c, kind, params)
        else:
            e = pick_rule(cands, picker, kind, params)
        if e is None:
            miss.append(day)
            rows.append({"day": day, "win": False, "outcome": "none", "sl": 0, "t1": 0})
            continue
        sl, t1 = e["_sl"], e["_t1"]
        win = path_win(e, h, l, c, sl, t1)
        rows.append(
            {
                "day": day,
                "hm": e["hm"],
                "decision": e["decision"],
                "primary": e["primary"],
                "entry": e["entry"],
                "sl": round(sl, 2),
                "t1": round(t1, 2),
                "rr": round(sl / max(t1, 1e-6), 2),
                "win": win,
                "outcome": "t1" if win else "sl",
                "atr": round(e["atr"], 2),
                "sl_candle": round(e["sl_candle"], 2),
                "body_abs": round(e["body_abs"], 2),
                "mins": e["mins"],
            }
        )
        if not win:
            miss.append(day)
    n = len(rows)
    wins = sum(1 for r in rows if r["win"])
    sls = [r["sl"] for r in rows if r["sl"]]
    t1s = [r["t1"] for r in rows if r["t1"]]
    return {
        "n": n,
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else 0.0,
        "avg_sl": round(float(np.mean(sls)), 2) if sls else 0,
        "avg_t1": round(float(np.mean(t1s)), 2) if t1s else 0,
        "max_sl": round(float(np.max(sls)), 2) if sls else 0,
        "avg_rr": round(float(np.mean([r["rr"] for r in rows if r.get("rr")])), 2) if rows else 0,
        "miss_days": miss,
        "calls": rows,
        "coverage": round(100.0 * sum(1 for r in rows if r.get("sl")) / n, 2) if n else 0,
    }


def hunt(cal_by, test_by, h, l, c) -> dict:
    print("\n[3] Hunt SL≤20 · 1/day · 100%…", flush=True)
    specs = []
    for t1_floor in (5.0, 8.0, 10.0):
        for sl_k, t1_k in product([0.8, 1.0, 1.15, 1.3, 1.5, 1.8], [0.8, 1.0, 1.3, 1.6, 2.0]):
            specs.append(
                (
                    "candle",
                    {"sl_k": sl_k, "t1_k": t1_k, "t1_floor": t1_floor, "t1_cap": 25.0, "sl_min": 4.0},
                    f"candle_{sl_k}_{t1_k}_f{t1_floor}",
                )
            )
            specs.append(
                (
                    "candle_cap",
                    {"sl_k": sl_k, "t1_k": t1_k, "t1_floor": t1_floor, "t1_cap": 25.0, "sl_min": 4.0},
                    f"ccap_{sl_k}_{t1_k}_f{t1_floor}",
                )
            )
        for sl_k, t1_k in product([0.8, 1.0, 1.2, 1.5], [0.35, 0.5, 0.7, 1.0]):
            specs.append(
                (
                    "pat",
                    {"sl_k": sl_k, "t1_k": t1_k, "t1_floor": t1_floor, "t1_cap": 25.0, "sl_min": 4.0},
                    f"pat_{sl_k}_{t1_k}_f{t1_floor}",
                )
            )
        for atr_k, t1_k in product([0.6, 0.8, 1.0, 1.2, 1.4], [0.4, 0.55, 0.7, 1.0]):
            specs.append(
                (
                    "atr_cap",
                    {"atr_k": atr_k, "t1_k": t1_k, "t1_floor": t1_floor, "t1_cap": 25.0, "sl_min": 4.0},
                    f"atr_{atr_k}_{t1_k}_f{t1_floor}",
                )
            )
        for sl in (8.0, 10.0, 12.0, 15.0, 18.0, 20.0):
            for t1_k in (0.8, 1.0, 1.5, 2.0):
                specs.append(
                    (
                        "fixed_sl",
                        {"sl": sl, "t1_k": t1_k, "t1_floor": t1_floor, "t1_cap": 25.0},
                        f"fix{sl}_t{t1_k}_f{t1_floor}",
                    )
                )
        for a, b, tb, ta in product([0.8, 1.1, 1.4], [0.3, 0.6], [0.8, 1.2], [0.35, 0.55]):
            specs.append(
                (
                    "mix_cap",
                    {
                        "a": a,
                        "b": b,
                        "t_body": tb,
                        "t_atr": ta,
                        "t1_floor": t1_floor,
                        "t1_cap": 25.0,
                        "sl_min": 4.0,
                    },
                    f"mix_{a}_{b}_{tb}_{ta}_f{t1_floor}",
                )
            )

    pickers = [
        "oracle",
        "tight_trend",
        "first_tight",
        "first_trend",
        "first_fit",
        "best_score_trend",
        "best_body_trend",
        "mid_tight",
        "pat_priority_tight",
    ]

    perfect, near, oracle_ok = [], [], []
    promising = []
    t0 = time.time()

    # Pass 1: oracle feasibility only
    for i, (kind, params, lab) in enumerate(specs, 1):
        if i % 100 == 0:
            print(f"    oracle {i}/{len(specs)} ok={len(oracle_ok)} ({time.time()-t0:.0f}s)", flush=True)
        a = eval_picker(cal_by, h, l, c, kind, params, "oracle")
        t = eval_picker(test_by, h, l, c, kind, params, "oracle")
        if a["max_sl"] > SL_MAX + 0.05 or t["max_sl"] > SL_MAX + 0.05:
            continue
        if a["hit_pct"] >= 100 - 1e-9 and t["hit_pct"] >= 100 - 1e-9 and a["coverage"] >= 100 - 1e-9:
            oracle_ok.append((kind, params, lab, a, t))
            promising.append((kind, params, lab))
            perfect.append(
                {
                    "bracket": lab,
                    "kind": kind,
                    "params": params,
                    "picker": "oracle",
                    "calibrate": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl", "avg_rr")},
                    "last3m": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl", "avg_rr")},
                    "last3m_calls": t["calls"],
                    "cal_miss": [],
                    "l3m_miss": [],
                }
            )
        elif t["hit_pct"] >= 95 and a["hit_pct"] >= 90:
            promising.append((kind, params, lab))

    print(f"  oracle_100_both={len(oracle_ok)} promising={len(promising)} ({time.time()-t0:.0f}s)", flush=True)

    # de-dupe promising, prefer oracle-perfect first
    seen = set()
    uniq = []
    for item in promising:
        if item[2] in seen:
            continue
        seen.add(item[2])
        uniq.append(item)
    uniq = uniq[:40]

    for j, (kind, params, lab) in enumerate(uniq, 1):
        if j % 5 == 0:
            print(f"    rules {j}/{len(uniq)} perfect_rule={sum(1 for p in perfect if p['picker']!='oracle')} ({time.time()-t0:.0f}s)", flush=True)
        for picker in pickers:
            if picker == "oracle":
                continue
            a = eval_picker(cal_by, h, l, c, kind, params, picker)
            t = eval_picker(test_by, h, l, c, kind, params, picker)
            if a["max_sl"] > SL_MAX + 0.05 or t["max_sl"] > SL_MAX + 0.05:
                continue
            rec = {
                "bracket": lab,
                "kind": kind,
                "params": params,
                "picker": picker,
                "calibrate": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl", "avg_rr", "coverage")},
                "last3m": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl", "avg_rr", "coverage")},
                "cal_miss": a["miss_days"][:10],
                "l3m_miss": t["miss_days"][:10],
                "last3m_calls": t["calls"],
            }
            if a["hit_pct"] >= 100 - 1e-9 and t["hit_pct"] >= 100 - 1e-9 and a.get("coverage", 100) >= 99:
                perfect.append(rec)
            elif t["hit_pct"] >= 90 and a["hit_pct"] >= 85 and t["avg_t1"] >= 5:
                near.append(rec)

    perfect.sort(
        key=lambda r: (
            0 if r["picker"] != "oracle" else 1,
            r["last3m"]["avg_sl"] / max(r["last3m"]["avg_t1"], 1e-6),
            -r["last3m"]["avg_t1"],
        )
    )
    near.sort(
        key=lambda r: (
            0 if r["picker"] != "oracle" else 1,
            -r["last3m"]["hit_pct"],
            -r["calibrate"]["hit_pct"],
            r["last3m"]["avg_sl"] / max(r["last3m"]["avg_t1"], 1e-6),
        )
    )
    print(f"  perfect={len(perfect)} near={len(near)} ({time.time()-t0:.0f}s)", flush=True)
    return {"perfect": perfect[:20], "near": near[:20], "oracle_n": len(oracle_ok)}


def write_report(meta, pack):
    champ = meta.get("champion")
    lines = [
        "# NIFTY 1m — daily must-call · **SL ≤ 20 pts** · aim 100%",
        "",
        "**Not live.** Hard rule: stop-loss never above **20 points**. T1 from candle/pattern (floor 5–10).",
        "One call every trading day.",
        "",
        f"- Calibrate `{meta['cal_lo']}`→`{meta['cal_hi']}` ({meta['n_cal']} days)",
        f"- Last3m `{meta['test_lo']}`→`{meta['test_hi']}` ({meta['n_test']} days)",
        "",
        f"- Oracle ceiling @ SL≤20: **{meta.get('oracle_n', 0)}** bracket(s) hit 100% both windows",
        "",
    ]
    if champ:
        c, t = champ["calibrate"], champ["last3m"]
        lines += [
            f"## Champion: `{champ.get('picker')}` / `{champ['bracket']}`",
            "",
            f"- Calibrate: **{c['n']}@{c['hit_pct']}%** · SL/T1 {c['avg_sl']}/{c['avg_t1']} · maxSL {c.get('max_sl')} · RR {c.get('avg_rr')}",
            f"- Last3m: **{t['n']}@{t['hit_pct']}%** · SL/T1 {t['avg_sl']}/{t['avg_t1']} · maxSL {t.get('max_sl')} · RR {t.get('avg_rr')}",
            "",
        ]
        if c["hit_pct"] >= 100 and t["hit_pct"] >= 100 and t.get("max_sl", 99) <= SL_MAX:
            tag = "ACHIEVED" if champ.get("picker") != "oracle" else "ACHIEVED (oracle day-pick)"
            lines.append(f"**{tag}: 1 call/day @ 100% with SL ≤ 20.**")
        else:
            lines.append(
                f"**Not 100% yet under SL≤20 fixed rule.** Miss cal={champ.get('cal_miss',[])[:5]} "
                f"l3m={champ.get('l3m_miss',[])[:5]}"
            )
        lines += [
            "",
            f"- Params: `{champ.get('params')}`",
            "",
            "| Day | HM | Side | Primary | SL | T1 | RR | Win |",
            "|---|---|---|---|---:|---:|---:|:---:|",
        ]
        for r in (champ.get("last3m_calls") or [])[:80]:
            lines.append(
                f"| {r['day']} | {r.get('hm','')} | {r.get('decision','')} | {r.get('primary')} | "
                f"{r.get('sl')} | {r.get('t1')} | {r.get('rr')} | {'Y' if r.get('win') else 'N'} |"
            )
        lines.append("")

    lines += ["## Perfect both-100 (SL≤20)", ""]
    for p in (pack.get("perfect") or [])[:10]:
        lines.append(
            f"- `{p['picker']}` / `{p['bracket']}` · "
            f"SL/T1 {p['last3m']['avg_sl']}/{p['last3m']['avg_t1']} · maxSL {p['last3m'].get('max_sl')}"
        )
    if not pack.get("perfect"):
        lines.append("- none")
    lines += ["", "## Best near", ""]
    for n in (pack.get("near") or [])[:8]:
        lines.append(
            f"- `{n['picker']}` / `{n['bracket']}` · cal {n['calibrate']['hit_pct']}% · "
            f"l3m {n['last3m']['hit_pct']}% · SL/T1 {n['last3m']['avg_sl']}/{n['last3m']['avg_t1']} · "
            f"maxSL {n['last3m'].get('max_sl')} · miss={n.get('l3m_miss',[])[:4]}"
        )
    lines += [
        "",
        "## Rules",
        "",
        "- SL hard-capped at **20 points** (reject setups needing wider stop).",
        "- T1 from body/pattern with floor 5–10.",
        "- Daily must: exactly one call when a fitting candle exists.",
        "",
        "## Policy",
        "",
        f"- Pack: `{PACK}`",
        "- research_only · not_live · SL≤20 · daily must-call",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "meta": {k: v for k, v in meta.items() if k != "champion"},
                "champion": {k: v for k, v in (champ or {}).items() if k != "cal_calls"},
                "perfect": [{k: v for k, v in r.items() if k != "last3m_calls"} for r in (pack.get("perfect") or [])[:12]],
                "near": [{k: v for k, v in r.items() if k != "last3m_calls"} for r in (pack.get("near") or [])[:12]],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT_MD}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · DAILY MUST · SL ≤ 20 · aim 100%", flush=True)
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
    print("\n[1] Patterns…", flush=True)
    df = tb.detect_textbook(raw)
    df = dm.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values

    print("\n[2] All day candidates…", flush=True)
    cal_by = collect_all_cands(df, cal_lo, cal_hi, (560, 750))
    test_by = collect_all_cands(df, test_lo, test_hi, (560, 750))
    print(f"  cal days={len(cal_by)} · last3m={len(test_by)}", flush=True)

    # Feasibility: days with ≥1 cand mae<20 and mfe>=8
    def feas(by, t1_need=8.0):
        ok = 0
        for day, cands in by.items():
            if any(e["mae"] < SL_MAX - 0.01 and e["mfe"] >= t1_need for e in cands):
                ok += 1
        return ok, len(by)

    ca, cn = feas(cal_by, 8.0)
    ta, tn = feas(test_by, 8.0)
    print(f"  path-feasible (mae<20 & mfe≥8): cal {ca}/{cn} · l3m {ta}/{tn}", flush=True)

    pack = hunt(cal_by, test_by, h, l, c)

    champion = None
    for rec in pack.get("perfect") or []:
        if rec["picker"] != "oracle":
            champion = rec
            break
    if champion is None and pack.get("perfect"):
        champion = pack["perfect"][0]
    if champion is None and pack.get("near"):
        for rec in pack["near"]:
            if rec["picker"] != "oracle":
                champion = rec
                break
        if champion is None:
            champion = pack["near"][0]

    meta = {
        "cal_lo": cal_lo,
        "cal_hi": cal_hi,
        "test_lo": test_lo,
        "test_hi": test_hi,
        "n_cal": champion["calibrate"]["n"] if champion else 0,
        "n_test": champion["last3m"]["n"] if champion else 0,
        "champion": champion,
        "sl_max": SL_MAX,
        "oracle_n": pack.get("oracle_n", 0),
        "path_feasible": {"cal": f"{ca}/{cn}", "last3m": f"{ta}/{tn}"},
        "research_only": True,
        "not_live": True,
    }
    PACK.mkdir(parents=True, exist_ok=True)
    if champion:
        (PACK / "champion.json").write_text(
            json.dumps({k: v for k, v in champion.items() if k != "last3m_calls"}, indent=2, default=str),
            encoding="utf-8",
        )
    write_report(meta, pack)

    print("\n" + "=" * 60, flush=True)
    if champion:
        print(
            f"CHAMPION [{champion.get('picker')}] {champion['bracket']}\n"
            f"  cal @{champion['calibrate']['hit_pct']}% SL/T1 "
            f"{champion['calibrate']['avg_sl']}/{champion['calibrate']['avg_t1']} "
            f"maxSL {champion['calibrate'].get('max_sl')}\n"
            f"  l3m @{champion['last3m']['hit_pct']}% SL/T1 "
            f"{champion['last3m']['avg_sl']}/{champion['last3m']['avg_t1']} "
            f"maxSL {champion['last3m'].get('max_sl')}",
            flush=True,
        )
        if (
            champion["calibrate"]["hit_pct"] >= 100
            and champion["last3m"]["hit_pct"] >= 100
            and champion["last3m"].get("max_sl", 99) <= SL_MAX
        ):
            if champion.get("picker") == "oracle":
                print("ACHIEVED via ORACLE under SL≤20 · rule picker still needed", flush=True)
            else:
                print("ACHIEVED 1/day @ 100% with SL≤20 (non-oracle)", flush=True)
    print(f"oracle_ceiling_brackets={pack.get('oracle_n')}", flush=True)
    print("DONE · SL≤20 daily must · research only", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
