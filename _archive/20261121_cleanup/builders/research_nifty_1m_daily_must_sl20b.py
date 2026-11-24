"""RESEARCH ONLY — SL≤20, 1/day @100%. Expand to all bars × both sides.

Prior gap: 1 cal + 1 l3m day had no pattern/body cand with mae<20.
Deep scan showed those days ARE feasible on other bars/sides.

  python -u prod_live/tests/builders/research_nifty_1m_daily_must_sl20b.py
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
import research_nifty_1m_daily_must_sl20 as S  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_daily_must_sl20"
REPORT_MD = OUT / "NIFTY_1M_DAILY_MUST_SL20.md"
REPORT_JSON = OUT / "NIFTY_1M_DAILY_MUST_SL20.json"
SL_MAX = 20.0


def collect_dense(
    df: pd.DataFrame,
    day_lo: str,
    day_hi: str,
    window: Tuple[int, int] = (560, 800),
) -> Dict[str, List[dict]]:
    """Pattern/body + dual-side probe on every bar in window."""
    h_all = df["High"].astype(float).values
    l_all = df["Low"].astype(float).values
    c_all = df["Close"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(df.index)}
    by_day: Dict[str, List[dict]] = {}
    days = [d for d in df["day"].unique() if day_lo <= d <= day_hi]
    mins_lo, mins_hi = window
    t0 = time.time()

    for di, day in enumerate(days, 1):
        if di % 40 == 0:
            print(f"    dense {di}/{len(days)} ({time.time()-t0:.0f}s)", flush=True)
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
            wanted = []
            if hit:
                primary = hit[0]
                side = dm._side_for(primary, body)
                if side and not ((side == "BUY" and body <= 0) or (side == "SELL" and body >= 0)):
                    score = 100 - dm.PRIORITY.index(primary) if primary in dm.PRIORITY else 50
                    wanted.append((side, primary, float(score), False))
            if abs(float(row["body_frac"])) >= 0.40:
                sd = "BUY" if body > 0 else ("SELL" if body < 0 else None)
                if sd:
                    wanted.append((sd, "_body", abs(float(row["body_frac"])) * 10, False))
            # dual-side probes (for ceiling + tight-structure rules)
            for sd in ("BUY", "SELL"):
                if not any(w[0] == sd and not w[3] for w in wanted):
                    wanted.append((sd, f"_probe_{sd.lower()}", 1.0, True))

            seen = set()
            for side, primary, score, is_probe in wanted:
                key = (side, is_probe, primary if not is_probe else side)
                if key in seen:
                    continue
                seen.add(key)
                g = S._geom(sess, pos, side, row)
                # skip probes with huge candle stop (noise) — keep if sl_candle <= 25 for search room
                if is_probe and g["sl_candle"] > 25:
                    continue
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
                        "mins": mins,
                        "score": score,
                        "trend_align": trend,
                        "drift": drift,
                        "mae": mae,
                        "mfe": mfe,
                        "full_i": full_i,
                        "is_probe": is_probe,
                        **g,
                    }
                )
        if cands:
            by_day[day] = cands
    return by_day


def eval_fixed_oracle(by, h, l, c, sl: float, t1: float) -> dict:
    rows = []
    miss = []
    for day, cands in sorted(by.items()):
        winners = []
        for e in cands:
            if e["mae"] >= sl - 1e-9 or e["mfe"] < t1 - 1e-9:
                continue
            win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
            if win and out == "t1":
                winners.append(e)
        if not winners:
            miss.append(day)
            rows.append({"day": day, "win": False, "sl": sl, "t1": t1})
            continue
        # prefer real pattern, tight candle, score
        winners.sort(
            key=lambda e: (
                0 if not e.get("is_probe") and not str(e["primary"]).startswith("_") else 1,
                0 if not e.get("is_probe") else 1,
                e["sl_candle"],
                -e["score"],
                e["mins"],
            )
        )
        e = winners[0]
        rows.append(
            {
                "day": day,
                "hm": e["hm"],
                "decision": e["decision"],
                "primary": e["primary"],
                "entry": e["entry"],
                "sl": sl,
                "t1": t1,
                "rr": round(sl / t1, 2),
                "win": True,
                "sl_candle": round(e["sl_candle"], 2),
                "mins": e["mins"],
                "is_probe": e.get("is_probe", False),
            }
        )
    n = len(rows)
    wins = sum(1 for r in rows if r["win"])
    return {
        "n": n,
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else 0,
        "avg_sl": sl,
        "avg_t1": t1,
        "max_sl": sl,
        "avg_rr": round(sl / t1, 2),
        "miss_days": miss,
        "calls": rows,
    }


def pick_rule_fixed(cands, rule: str, sl: float, t1: float, h, l, c) -> Optional[dict]:
    """Non-lookahead: filter structure then pick; win evaluated later."""
    pool = [e for e in cands if not e.get("is_probe")]
    if not pool:
        pool = list(cands)
    # must have structure candle stop <= sl (dynamic fit under cap)
    fit = [e for e in pool if e["sl_candle"] <= sl]
    if not fit:
        fit = [e for e in pool if e["sl_candle"] <= SL_MAX]
    if not fit:
        fit = pool

    if rule == "first_tight":
        fit = sorted(fit, key=lambda e: (e["sl_candle"], e["mins"]))
    elif rule == "trend_tight":
        al = [e for e in fit if e["trend_align"] == 1]
        fit = sorted(al or fit, key=lambda e: (e["sl_candle"], -e["score"], e["mins"]))
    elif rule == "pat_tight":
        pats = [e for e in fit if not str(e["primary"]).startswith("_")]
        fit = sorted(pats or fit, key=lambda e: (-e["score"], e["sl_candle"], e["mins"]))
    elif rule == "trend_pat_tight":
        pats = [e for e in fit if e["trend_align"] == 1 and not str(e["primary"]).startswith("_")]
        if not pats:
            pats = [e for e in fit if e["trend_align"] == 1]
        fit = sorted(pats or fit, key=lambda e: (-e["score"], e["sl_candle"], e["mins"]))
    elif rule == "mid_trend_tight":
        mid = [e for e in fit if 575 <= e["mins"] <= 720 and e["trend_align"] == 1]
        fit = sorted(mid or fit, key=lambda e: (e["sl_candle"], -e["score"]))
    elif rule == "body_trend":
        al = [e for e in fit if e["trend_align"] == 1]
        fit = sorted(al or fit, key=lambda e: (-e["body_abs"], e["sl_candle"]))
    else:
        fit = sorted(fit, key=lambda e: e["mins"])

    e = dict(fit[0])
    e["_sl"], e["_t1"] = sl, t1
    return e


def eval_rule_fixed(by, h, l, c, sl, t1, rule) -> dict:
    rows = []
    miss = []
    for day, cands in sorted(by.items()):
        e = pick_rule_fixed(cands, rule, sl, t1, h, l, c)
        if e is None:
            miss.append(day)
            continue
        win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
        ok = bool(win) and out == "t1"
        rows.append(
            {
                "day": day,
                "hm": e["hm"],
                "decision": e["decision"],
                "primary": e["primary"],
                "entry": e["entry"],
                "sl": sl,
                "t1": t1,
                "rr": round(sl / t1, 2),
                "win": ok,
                "sl_candle": round(e["sl_candle"], 2),
                "mins": e["mins"],
            }
        )
        if not ok:
            miss.append(day)
    n = len(rows)
    wins = sum(1 for r in rows if r["win"])
    return {
        "n": n,
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else 0,
        "avg_sl": sl,
        "avg_t1": t1,
        "max_sl": sl,
        "avg_rr": round(sl / t1, 2),
        "miss_days": miss,
        "calls": rows,
    }


def eval_dyn_oracle(by, h, l, c, kind, params) -> dict:
    rows = []
    miss = []
    for day, cands in sorted(by.items()):
        winners = []
        for e in cands:
            bt = S.brackets(e, kind, params)
            if bt is None:
                continue
            sl, t1 = bt
            if sl > SL_MAX + 1e-9:
                continue
            if e["mae"] >= sl - 1e-9 or e["mfe"] < t1 - 1e-9:
                continue
            win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
            if win and out == "t1":
                winners.append((e, sl, t1))
        if not winners:
            miss.append(day)
            rows.append({"day": day, "win": False, "sl": 0, "t1": 0})
            continue
        winners.sort(
            key=lambda x: (
                0 if not x[0].get("is_probe") else 1,
                x[0]["sl_candle"],
                -x[0]["score"],
                x[0]["mins"],
            )
        )
        e, sl, t1 = winners[0]
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
                "win": True,
                "sl_candle": round(e["sl_candle"], 2),
                "mins": e["mins"],
                "is_probe": e.get("is_probe", False),
            }
        )
    n = len(rows)
    wins = sum(1 for r in rows if r["win"])
    sls = [r["sl"] for r in rows if r.get("sl")]
    t1s = [r["t1"] for r in rows if r.get("t1")]
    return {
        "n": n,
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else 0,
        "avg_sl": round(float(np.mean(sls)), 2) if sls else 0,
        "avg_t1": round(float(np.mean(t1s)), 2) if t1s else 0,
        "max_sl": round(float(np.max(sls)), 2) if sls else 0,
        "avg_rr": round(float(np.mean([r["rr"] for r in rows if r.get("rr")])), 2) if rows else 0,
        "miss_days": miss,
        "calls": rows,
    }


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · SL≤20 dense · 1/day @100%", flush=True)
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
    df = tb.detect_textbook(raw)
    df = dm.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values

    print("\n[1] Dense candidates…", flush=True)
    cal_by = collect_dense(df, cal_lo, cal_hi, (560, 800))
    test_by = collect_dense(df, test_lo, test_hi, (560, 800))
    print(f"  days cal={len(cal_by)} l3m={len(test_by)}", flush=True)

    perfect = []
    near = []

    print("\n[2] Fixed SL≤20 oracle…", flush=True)
    for sl, t1 in product([20.0, 18.0, 15.0, 12.0, 10.0], [5.0, 8.0, 10.0]):
        a = eval_fixed_oracle(cal_by, h, l, c, sl, t1)
        t = eval_fixed_oracle(test_by, h, l, c, sl, t1)
        lab = f"fixed_{sl}_{t1}"
        print(
            f"  {lab}: cal @{a['hit_pct']}% miss={len(a['miss_days'])} | "
            f"l3m @{t['hit_pct']}% miss={len(t['miss_days'])} {t['miss_days'][:3]}",
            flush=True,
        )
        rec = {
            "bracket": lab,
            "kind": "fixed_sl",
            "params": {"sl": sl, "t1": t1},
            "picker": "oracle",
            "calibrate": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl", "avg_rr")},
            "last3m": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl", "avg_rr")},
            "cal_miss": a["miss_days"][:8],
            "l3m_miss": t["miss_days"][:8],
            "last3m_calls": t["calls"],
        }
        if a["hit_pct"] >= 100 and t["hit_pct"] >= 100:
            perfect.append(rec)
        elif t["hit_pct"] >= 95 and a["hit_pct"] >= 90:
            near.append(rec)

    print("\n[3] Dynamic capped oracle…", flush=True)
    dyn_specs = []
    for t1_floor in (5.0, 8.0, 10.0):
        for sl_k, t1_k in product([1.0, 1.2, 1.5, 1.8], [0.8, 1.0, 1.5]):
            dyn_specs.append(
                (
                    "candle_cap",
                    {"sl_k": sl_k, "t1_k": t1_k, "t1_floor": t1_floor, "t1_cap": 25.0, "sl_min": 4.0},
                    f"ccap_{sl_k}_{t1_k}_f{t1_floor}",
                )
            )
        for atr_k, t1_k in product([0.8, 1.0, 1.2, 1.4], [0.5, 0.7, 1.0]):
            dyn_specs.append(
                (
                    "atr_cap",
                    {"atr_k": atr_k, "t1_k": t1_k, "t1_floor": t1_floor, "t1_cap": 25.0, "sl_min": 4.0},
                    f"atr_{atr_k}_{t1_k}_f{t1_floor}",
                )
            )
    for kind, params, lab in dyn_specs:
        a = eval_dyn_oracle(cal_by, h, l, c, kind, params)
        t = eval_dyn_oracle(test_by, h, l, c, kind, params)
        if a.get("max_sl", 99) > SL_MAX + 0.05:
            continue
        rec = {
            "bracket": lab,
            "kind": kind,
            "params": params,
            "picker": "oracle",
            "calibrate": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl", "avg_rr")},
            "last3m": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl", "avg_rr")},
            "cal_miss": a["miss_days"][:8],
            "l3m_miss": t["miss_days"][:8],
            "last3m_calls": t["calls"],
        }
        if a["hit_pct"] >= 100 and t["hit_pct"] >= 100:
            perfect.append(rec)
            print(f"  PERFECT oracle {lab} SL/T1 {t['avg_sl']}/{t['avg_t1']}", flush=True)
        elif t["hit_pct"] >= 95 and a["hit_pct"] >= 90:
            near.append(rec)

    print(f"\n[4] Rule pickers on best fixed…", flush=True)
    # Use best perfect fixed or best near fixed for rules
    fixed_targets = [(20.0, 5.0), (20.0, 8.0), (20.0, 10.0), (18.0, 5.0), (15.0, 5.0)]
    rules = ["trend_pat_tight", "trend_tight", "pat_tight", "first_tight", "mid_trend_tight", "body_trend"]
    for sl, t1 in fixed_targets:
        for rule in rules:
            a = eval_rule_fixed(cal_by, h, l, c, sl, t1, rule)
            t = eval_rule_fixed(test_by, h, l, c, sl, t1, rule)
            lab = f"fixed_{sl}_{t1}"
            rec = {
                "bracket": lab,
                "kind": "fixed_sl",
                "params": {"sl": sl, "t1": t1},
                "picker": rule,
                "calibrate": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl", "avg_rr")},
                "last3m": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl", "avg_rr")},
                "cal_miss": a["miss_days"][:8],
                "l3m_miss": t["miss_days"][:8],
                "last3m_calls": t["calls"],
            }
            if a["hit_pct"] >= 100 and t["hit_pct"] >= 100:
                perfect.append(rec)
                print(f"  PERFECT RULE {rule} {lab}", flush=True)
            elif t["hit_pct"] >= 85 and a["hit_pct"] >= 80:
                near.append(rec)
                if t["hit_pct"] >= 95:
                    print(
                        f"  near {rule} {lab} cal {a['hit_pct']}% l3m {t['hit_pct']}%",
                        flush=True,
                    )

    perfect.sort(
        key=lambda r: (
            0 if r["picker"] != "oracle" else 1,
            -r["last3m"]["avg_t1"],
            r["last3m"]["avg_sl"],
        )
    )
    near.sort(
        key=lambda r: (
            0 if r["picker"] != "oracle" else 1,
            -r["last3m"]["hit_pct"],
            -r["calibrate"]["hit_pct"],
            r["last3m"]["avg_sl"],
        )
    )

    champion = None
    for r in perfect:
        if r["picker"] != "oracle":
            champion = r
            break
    if champion is None and perfect:
        champion = perfect[0]
    if champion is None and near:
        for r in near:
            if r["picker"] != "oracle":
                champion = r
                break
        if champion is None:
            champion = near[0]

    # write report
    lines = [
        "# NIFTY 1m — daily must-call · **SL ≤ 20** · aim 100%",
        "",
        "**Not live.** Hard cap: stop-loss **≤ 20 points**. T1 ≥ 5–10. One call/day.",
        "",
        f"- Calibrate `{cal_lo}`→`{cal_hi}`",
        f"- Last3m `{test_lo}`→`{test_hi}`",
        "",
    ]
    if champion:
        c, t = champion["calibrate"], champion["last3m"]
        lines += [
            f"## Champion: `{champion['picker']}` / `{champion['bracket']}`",
            "",
            f"- Calibrate: **{c['n']}@{c['hit_pct']}%** · SL/T1 {c['avg_sl']}/{c['avg_t1']} · maxSL {c.get('max_sl')}",
            f"- Last3m: **{t['n']}@{t['hit_pct']}%** · SL/T1 {t['avg_sl']}/{t['avg_t1']} · maxSL {t.get('max_sl')}",
            "",
        ]
        if c["hit_pct"] >= 100 and t["hit_pct"] >= 100:
            tag = "ACHIEVED" if champion["picker"] != "oracle" else "ACHIEVED (oracle day-pick under SL≤20)"
            lines.append(f"**{tag}.**")
        else:
            lines.append(
                f"**Best under SL≤20.** Miss cal={champion.get('cal_miss',[])[:5]} "
                f"l3m={champion.get('l3m_miss',[])[:5]}"
            )
        lines += [
            "",
            "| Day | HM | Side | Primary | SL | T1 | Win |",
            "|---|---|---|---|---:|---:|:---:|",
        ]
        for r in (champion.get("last3m_calls") or [])[:80]:
            lines.append(
                f"| {r['day']} | {r.get('hm','')} | {r.get('decision','')} | {r.get('primary')} | "
                f"{r.get('sl')} | {r.get('t1')} | {'Y' if r.get('win') else 'N'} |"
            )
        lines.append("")

    lines += ["## Perfect both-100 @ SL≤20", ""]
    if not perfect:
        lines.append("- none yet")
    for p in perfect[:12]:
        lines.append(
            f"- `{p['picker']}` / `{p['bracket']}` · SL/T1 {p['last3m']['avg_sl']}/{p['last3m']['avg_t1']}"
        )
    lines += ["", "## Best near", ""]
    for n in near[:10]:
        lines.append(
            f"- `{n['picker']}` / `{n['bracket']}` · cal {n['calibrate']['hit_pct']}% · "
            f"l3m {n['last3m']['hit_pct']}% · miss={n.get('l3m_miss',[])[:4]}"
        )
    lines += [
        "",
        "## Policy",
        "",
        f"- Pack: `{PACK}`",
        "- research_only · not_live · SL≤20 · daily must-call",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    PACK.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    payload = {
        "champion": {k: v for k, v in (champion or {}).items()},
        "perfect": [{k: v for k, v in r.items() if k != "last3m_calls"} for r in perfect[:15]],
        "near": [{k: v for k, v in r.items() if k != "last3m_calls"} for r in near[:15]],
        "sl_max": 20,
        "research_only": True,
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    if champion:
        (PACK / "champion.json").write_text(
            json.dumps({k: v for k, v in champion.items() if k != "last3m_calls"}, indent=2, default=str),
            encoding="utf-8",
        )
    print(f"\nwrote {REPORT_MD}", flush=True)
    print("=" * 60, flush=True)
    if champion:
        print(
            f"CHAMPION {champion['picker']} / {champion['bracket']} · "
            f"cal @{champion['calibrate']['hit_pct']}% · l3m @{champion['last3m']['hit_pct']}% · "
            f"SL/T1 {champion['last3m']['avg_sl']}/{champion['last3m']['avg_t1']}",
            flush=True,
        )
        if champion["calibrate"]["hit_pct"] >= 100 and champion["last3m"]["hit_pct"] >= 100:
            print("ACHIEVED under SL≤20", flush=True)
    print(f"perfect_n={len(perfect)} near_n={len(near)}", flush=True)
    print("DONE sl20b", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
