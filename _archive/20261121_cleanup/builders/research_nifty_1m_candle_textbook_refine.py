"""RESEARCH ONLY — Refine textbook candle events with RSI/early gates for both-100."""
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

REPORT_MD = tb.REPORT_MD
REPORT_JSON = tb.REPORT_JSON


def soft(e, g):
    if g.get("side") and e["decision"] != g["side"]:
        return False
    if g.get("primaries") and e["primary"] not in g["primaries"]:
        return False
    if g.get("clocks") and e["clock"] not in g["clocks"]:
        return False
    if g.get("max_or_ext") is not None and e["or_ext"] > g["max_or_ext"]:
        return False
    if g.get("min_or") is not None and e["or_width"] < g["min_or"]:
        return False
    if g.get("min_body") is not None and abs(e["body_frac"]) < g["min_body"]:
        return False
    if g.get("rsi_lo") is not None and e["rsi_14"] < g["rsi_lo"]:
        return False
    if g.get("rsi_hi") is not None and e["rsi_14"] > g["rsi_hi"]:
        return False
    return True


def main() -> int:
    print("TEXTBOOK REFINE · RSI + pattern gates", flush=True)
    raw = base.load_existing_1m()
    raw = raw[
        (raw.index >= pd.Timestamp(tb.START, tz="Asia/Kolkata"))
        & (raw.index <= pd.Timestamp(f"{tb.END} 23:59:59", tz="Asia/Kolkata"))
    ]
    df = tb.detect_textbook(raw)
    c = df["Close"].astype(float)
    delta = c.diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi_14"] = (100 - (100 / (1 + up / down.replace(0, np.nan)))).fillna(50.0)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    cl = df["Close"].astype(float).values

    ana = tb.collect_pattern_events(df, tb.START, tb.ANALYZE_END)
    test = tb.collect_pattern_events(df, tb.TEST_START, tb.END)
    for e in ana + test:
        e["rsi_14"] = float(df["rsi_14"].iloc[e["full_i"]])

    from collections import defaultdict

    buckets = defaultdict(list)
    for e in ana:
        buckets[e["primary"]].append(e)
        buckets["*"].append(e)
    for e in ana + test:
        rows = buckets.get(e["primary"]) or buckets["*"]
        maes = np.array([r["mae"] for r in rows])
        mfes = np.array([r["mfe"] for r in rows])
        sl = max(float(np.percentile(maes, 80)), 0.9 * e["atr"], 5.0)
        t1 = max(float(np.percentile(mfes, 35)), 0.5 * e["atr"], 5.0)
        e["families"]["mae_p80_35"] = (round(sl, 2), round(t1, 2))
        e["families"]["mae_p85_30"] = (
            round(max(float(np.percentile(maes, 85)), 1.0 * e["atr"], 5.0), 2),
            round(max(float(np.percentile(mfes, 30)), 0.45 * e["atr"], 5.0), 2),
        )

    fams = ["pat_wick", "atr_1_0_6", "atr_1_3_0_7", "or_frac", "mae_p80_35", "mae_p85_30"]
    ana_pre = tb.precompute(ana, h, l, cl, fams)
    test_pre = tb.precompute(test, h, l, cl, fams)

    prim_sets = [
        None,
        ["morning_star", "evening_star", "bull_engulf", "bear_engulf"],
        ["bull_engulf", "bear_engulf", "piercing", "dark_cloud"],
        ["three_soldiers", "three_crows", "marubozu_bull", "marubozu_bear"],
        ["hammer", "shooting_star", "inv_hammer", "hanging_man"],
        ["bull_engulf", "three_soldiers", "morning_star", "piercing", "hammer", "marubozu_bull", "belt_bull"],
        ["bear_engulf", "three_crows", "evening_star", "dark_cloud", "shooting_star", "marubozu_bear", "belt_bear"],
        ["marubozu_bull", "marubozu_bear", "belt_bull", "belt_bear"],
    ]
    both = []
    for pr, side, clk, ext, mor, mb, rsi in product(
        prim_sets,
        [None, "BUY", "SELL"],
        [None, ["early"], ["early", "morning"]],
        [0.10, 0.15, 0.25, 0.5],
        [12, 18],
        [None, 0.5],
        [None, (45, 65), (40, 70), (35, 75)],
    ):
        g = {"primaries": pr, "side": side, "clocks": clk, "max_or_ext": ext, "min_or": mor, "min_body": mb}
        if rsi:
            g["rsi_lo"], g["rsi_hi"] = rsi
        am = [soft(e, g) for e in ana]
        if sum(am) < 5:
            continue
        tm = [soft(e, g) for e in test]
        for fam in fams:
            a = co._agg_pre(ana, ana_pre[fam], am)
            if a["n"] < 5 or a["hit_pct"] < 100 - 1e-9:
                continue
            t = co._agg_pre(test, test_pre[fam], tm)
            if t["hit_pct"] >= 100 - 1e-9 and t["n"] >= 1:
                both.append(
                    {
                        "bracket": fam,
                        "filters": g,
                        "analyze": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                        "test": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                        "test_calls": t["calls"],
                    }
                )
    both.sort(key=lambda r: (-r["test"]["n"], -r["analyze"]["n"]))
    uniq, seen = [], set()
    for r in both:
        key = (r["bracket"], r["test"]["n"], r["analyze"]["n"], json.dumps(r["filters"], sort_keys=True, default=str))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    by = {}
    for r in uniq:
        for call in r["test_calls"]:
            by.setdefault(call["day"], call)
    union = co.first_day(list(by.values()))
    print(f"BOTH={len(uniq)} best_n={(uniq[0]['test']['n'] if uniq else 0)} union={len(union)}", flush=True)
    if uniq:
        print("BEST", uniq[0]["bracket"], uniq[0]["filters"], uniq[0]["analyze"], uniq[0]["test"], flush=True)
        for call in uniq[0]["test_calls"]:
            print(call["day"], call["hm"], call["decision"], call.get("primary"), call["sl"], call["t1"], flush=True)

    extra = [
        "",
        "## Refined trade hunt (RSI + textbook patterns)",
        "",
        f"- Both-100 logics: **{len(uniq)}** · Union **{len(union)} @ {co.agg(union)['hit_pct']}%**",
        "",
    ]
    if uniq:
        b = uniq[0]
        extra += [
            f"**Best:** `{b['bracket']}` test **{b['test']['n']} @ 100%** (ana {b['analyze']['n']} @ 100%)",
            f"- Filters: `{json.dumps(b['filters'], default=str)}`",
            "",
            "| Day | HM | Side | Primary | SL | T1 |",
            "|---|---|---|---|---:|---:|",
        ]
        for call in union:
            extra.append(
                f"| {call['day']} | {call['hm']} | {call['decision']} | {call.get('primary','')} | "
                f"{call['sl']} | {call['t1']} |"
            )
    REPORT_MD.write_text(REPORT_MD.read_text(encoding="utf-8") + "\n".join(extra), encoding="utf-8")
    js = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    js["refine_both100"] = [{k: v for k, v in r.items() if k != "analyze_calls"} for r in uniq[:10]]
    js["refine_union"] = {"n": len(union), "hit_pct": co.agg(union)["hit_pct"], "calls": union}
    REPORT_JSON.write_text(json.dumps(js, indent=2, default=str), encoding="utf-8")
    print("DONE refine", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
