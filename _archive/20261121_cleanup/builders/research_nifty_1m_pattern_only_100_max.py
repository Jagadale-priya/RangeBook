"""RESEARCH ONLY — Pattern-only (no OR), ALL completions, max-n @ 100% both windows."""
from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path

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
import research_nifty_1m_pattern_only_100 as po  # noqa: E402

REPORT_MD = po.REPORT_MD
REPORT_JSON = po.REPORT_JSON
PACK = po.PACK


def main() -> int:
    print("PATTERN-ONLY MAX · all completions · no OR", flush=True)
    raw = base.load_existing_1m()
    end_ts = raw.index.max()
    test_hi = end_ts.strftime("%Y-%m-%d")
    test_lo_ts = end_ts - pd.Timedelta(days=92)
    test_lo = test_lo_ts.strftime("%Y-%m-%d")
    cal_hi = (test_lo_ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    cal_lo = (test_lo_ts - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    raw = raw[raw.index >= pd.Timestamp(cal_lo, tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = po.add_rsi(df)

    # ALL pattern completions (many per day)
    cal = po.collect_pattern_entries(df, cal_lo, cal_hi, one_per_day_side=False)
    test = po.collect_pattern_entries(df, test_lo, test_hi, one_per_day_side=False)
    # still cap insane density: max 6 per day (earliest strongest)
    def cap_day(evs, k=6):
        by = {}
        for e in sorted(evs, key=lambda x: (x["day"], x["mins"])):
            by.setdefault(e["day"], [])
            if len(by[e["day"]]) < k:
                by[e["day"]].append(e)
        out = []
        for day in sorted(by):
            out.extend(by[day])
        return out

    cal, test = cap_day(cal, 8), cap_day(test, 8)
    print(f"cal={len(cal)} last3m={len(test)}", flush=True)
    mae = po.attach_mae(cal, test)
    fams = ["pat_wick", "atr_1_1_0_65", "atr_1_4_0_75", "atr_1_6_0_85", "mix_pat_atr"] + mae
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    cal_pre = po.precompute(cal, h, l, c, fams)
    test_pre = po.precompute(test, h, l, c, fams)

    # focused high-value pattern families
    prim_sets = [
        ["hammer", "shooting_star", "inv_hammer", "hanging_man"],
        ["shooting_star", "hanging_man"],
        ["bull_engulf", "bear_engulf"],
        ["morning_star", "evening_star"],
        ["three_soldiers", "three_crows"],
        ["marubozu_bull", "marubozu_bear"],
        ["belt_bull", "belt_bear"],
        ["piercing", "dark_cloud"],
        ["three_outside_up", "three_outside_dn"],
        ["rising_3_methods", "falling_3_methods"],
        ["morning_star", "bull_engulf", "three_soldiers", "hammer", "marubozu_bull", "belt_bull", "piercing"],
        ["evening_star", "bear_engulf", "three_crows", "shooting_star", "hanging_man", "marubozu_bear", "belt_bear", "dark_cloud"],
        None,
    ]
    both = []
    for pr, side, clk, mb, rsi, fam in product(
        prim_sets,
        [None, "BUY", "SELL"],
        [None, ["early"], ["early", "morning"], ["morning"]],
        [None, 0.35, 0.55],
        [None, (20, 50), (45, 65), (40, 70), (30, 55), (50, 80)],
        fams,
    ):
        g = {"primaries": pr, "side": side, "clocks": clk, "min_body": mb}
        if rsi:
            g["rsi_lo"], g["rsi_hi"] = rsi
        cm = [po.soft(e, g) for e in cal]
        if sum(cm) < 5:
            continue
        tm = [po.soft(e, g) for e in test]
        a = po.agg_all(cal_pre[fam], cm)
        if a["n"] < 5 or a["hit_pct"] < 100 - 1e-9:
            continue
        t = po.agg_all(test_pre[fam], tm)
        if t["n"] < 1 or t["hit_pct"] < 100 - 1e-9:
            continue
        # skip absurd R:R
        if t["avg_t1"] > 0 and t["avg_sl"] > 6.0 * t["avg_t1"]:
            continue
        both.append(
            {
                "bracket": fam,
                "filters": g,
                "calibrate": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                "last3m": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                "last3m_calls": t["calls"],
            }
        )

    both.sort(key=lambda r: (-r["last3m"]["n"], -r["calibrate"]["n"], r["last3m"]["avg_sl"]))
    uniq, seen = [], set()
    for r in both:
        key = (
            r["bracket"],
            r["last3m"]["n"],
            r["calibrate"]["n"],
            tuple(sorted((c["day"], c["hm"], c["decision"]) for c in r["last3m_calls"])),
            json.dumps(r["filters"], sort_keys=True, default=str),
        )
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)

    by = {}
    for r in uniq:
        for c in r["last3m_calls"]:
            by.setdefault((c["day"], c["hm"], c["decision"]), c)
    union = sorted(by.values(), key=lambda x: (x["day"], x["hm"]))
    print(f"both100={len(uniq)} best_n={(uniq[0]['last3m']['n'] if uniq else 0)} union={len(union)}", flush=True)
    if uniq:
        b = uniq[0]
        print("BEST", b["bracket"], b["filters"], b["calibrate"], b["last3m"], flush=True)
        for c in b["last3m_calls"]:
            print(c["day"], c["hm"], c["decision"], c["primary"], c["sl"], c["t1"], flush=True)

    # patch main report
    hunt = {
        "both100": uniq[:25],
        "near": [],
        "union100": {"n": len(union), "wins": sum(1 for x in union if x["win"]), "hit_pct": co.agg(union)["hit_pct"], "calls": union},
        "union_rr": {"n": len(union), "wins": sum(1 for x in union if x["win"]), "hit_pct": co.agg(union)["hit_pct"], "calls": union},
    }
    meta = {
        "cal_lo": cal_lo,
        "cal_hi": cal_hi,
        "test_lo": test_lo,
        "test_hi": test_hi,
        "n_cal": len(cal),
        "n_test": len(test),
        "n_both100": len(uniq),
        "union_n": len(union),
        "union_rr_n": len(union),
        "no_or_break": True,
        "all_completions": True,
        "research_only": True,
        "not_live": True,
    }
    PACK.mkdir(parents=True, exist_ok=True)
    if uniq:
        (PACK / "best_both100_max.json").write_text(json.dumps(uniq[0], indent=2, default=str), encoding="utf-8")
    po.write_report(meta, hunt)
    print("DONE max", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
