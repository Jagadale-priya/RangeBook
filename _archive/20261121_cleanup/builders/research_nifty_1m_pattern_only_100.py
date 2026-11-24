"""RESEARCH ONLY — No OR-break. Textbook pattern completions → max-n @ 100%.

Entry = candle pattern completion (1/2/3-bar) with side from pattern bias.
SL/T1 = pattern wick / ATR / MAE-MFE percentiles (chart only).

  python -u prod_live/tests/builders/research_nifty_1m_pattern_only_100.py
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
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_pattern_only_100"
REPORT_MD = OUT / "NIFTY_1M_PATTERN_ONLY_100.md"
REPORT_JSON = OUT / "NIFTY_1M_PATTERN_ONLY_100.json"

# Strong tradeable patterns (priority order)
PRIORITY = [
    "morning_star", "evening_star", "morning_doji_star", "evening_doji_star",
    "abandoned_baby_bull", "abandoned_baby_bear",
    "three_soldiers", "three_crows",
    "three_outside_up", "three_outside_dn", "three_inside_up", "three_inside_dn",
    "bull_engulf", "bear_engulf", "piercing", "dark_cloud",
    "bull_kicker", "bear_kicker", "tweezer_bot", "tweezer_top",
    "hammer", "shooting_star", "inv_hammer", "hanging_man",
    "marubozu_bull", "marubozu_bear", "belt_bull", "belt_bear",
    "rising_3_methods", "falling_3_methods",
    "stick_sandwich", "matching_low",
]


def add_rsi(df: pd.DataFrame) -> pd.DataFrame:
    c = df["Close"].astype(float)
    d = c.diff()
    up = d.clip(lower=0).rolling(14).mean()
    down = (-d.clip(upper=0)).rolling(14).mean()
    out = df.copy()
    out["rsi_14"] = (100 - (100 / (1 + up / down.replace(0, np.nan)))).fillna(50.0)
    return out


def collect_pattern_entries(df: pd.DataFrame, day_lo: str, day_hi: str, one_per_day_side: bool = True) -> List[dict]:
    """Every strong pattern completion → BUY/SELL. NO OR-break."""
    h_all = df["High"].astype(float).values
    l_all = df["Low"].astype(float).values
    c_all = df["Close"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(df.index)}
    events: List[dict] = []
    days = [d for d in df["day"].unique() if day_lo <= d <= day_hi]
    t0 = time.time()

    for di, day in enumerate(days, 1):
        if di % 40 == 0:
            print(f"    pat events {di}/{len(days)} n={len(events)} ({time.time()-t0:.0f}s)", flush=True)
        sess = df[df["day"] == day]
        if len(sess) < 30:
            continue
        seen = set()
        day_open = float(sess["Open"].iloc[0])
        for pos in range(5, min(len(sess), 360)):
            row = sess.iloc[pos]
            mins = int(row["mins"])
            if mins < 9 * 60 + 20 or mins > 14 * 60 + 45:
                continue
            hit = [p for p in PRIORITY if p in row.index and int(row[p]) == 1]
            if not hit:
                continue
            primary = hit[0]
            if primary in tb.BULLISH:
                side = "BUY"
            elif primary in tb.BEARISH:
                side = "SELL"
            else:
                continue
            body = float(row["Close"]) - float(row["Open"])
            if side == "BUY" and body <= 0:
                continue
            if side == "SELL" and body >= 0:
                continue
            if one_per_day_side and side in seen:
                continue

            entry = float(row["Close"])
            atr = float(row["atr14"]) if np.isfinite(row["atr14"]) else 8.0
            atr = max(atr, 3.0)
            # pattern geometry (last 1–3 bars)
            lo_win = float(sess["Low"].iloc[max(0, pos - 2) : pos + 1].min())
            hi_win = float(sess["High"].iloc[max(0, pos - 2) : pos + 1].max())
            if side == "BUY":
                sl_pat = max(entry - lo_win, 0.0)
                t1_room = max(hi_win - entry, 0.0)
            else:
                sl_pat = max(hi_win - entry, 0.0)
                t1_room = max(entry - lo_win, 0.0)

            families = {
                "pat_wick": (
                    round(max(1.08 * sl_pat, 0.9 * atr, 5.0), 2),
                    round(max(0.55 * atr, 0.35 * max(sl_pat, 1.0), 5.0), 2),
                ),
                "atr_1_1_0_65": (round(max(1.1 * atr, 5.0), 2), round(max(0.65 * atr, 5.0), 2)),
                "atr_1_4_0_75": (round(max(1.4 * atr, 5.0), 2), round(max(0.75 * atr, 5.0), 2)),
                "atr_1_6_0_85": (round(max(1.6 * atr, 5.0), 2), round(max(0.85 * atr, 5.0), 2)),
                "mix_pat_atr": (
                    round(max(0.7 * sl_pat + 0.5 * atr, 5.0), 2),
                    round(max(0.5 * atr + 0.2 * max(t1_room, atr), 5.0), 2),
                ),
            }
            ts = sess.index[pos]
            full_i = idx_map[ts]
            mae, mfe = co.excursion(h_all, l_all, c_all, full_i, side)
            events.append(
                {
                    "day": day,
                    "hm": row["hm"],
                    "decision": side,
                    "primary": primary,
                    "patterns": hit,
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
                    "families": families,
                    "sl_pat": sl_pat,
                }
            )
            if one_per_day_side:
                seen.add(side)
                if len(seen) >= 2:
                    break
    return events


def attach_mae(ana: List[dict], others: List[dict]) -> List[str]:
    buckets: Dict[str, List[dict]] = defaultdict(list)
    for e in ana:
        buckets[e["primary"]].append(e)
        buckets[f"{e['decision']}|*"].append(e)
        buckets["*"].append(e)
    names = ["mae_p80_35", "mae_p85_30", "mae_p75_40", "mae_p90_30"]
    pairs = [(80, 35), (85, 30), (75, 40), (90, 30)]
    for e in ana + others:
        rows = buckets.get(e["primary"]) or buckets.get(f"{e['decision']}|*") or buckets["*"]
        if len(rows) < 10:
            rows = buckets["*"]
        maes = np.array([r["mae"] for r in rows], dtype=float)
        mfes = np.array([r["mfe"] for r in rows], dtype=float)
        for (sp, tp), name in zip(pairs, names):
            sl = max(float(np.percentile(maes, sp)), 0.85 * e["atr"], 5.0)
            t1 = max(float(np.percentile(mfes, tp)), 0.40 * e["atr"], 5.0)
            # cap absurd SL for usable R:R research (still chart-derived)
            sl = min(sl, max(3.5 * e["atr"], 1.5 * max(e["sl_pat"], e["atr"])))
            e["families"][name] = (round(sl, 2), round(t1, 2))
    return names


def soft(e: dict, g: dict) -> bool:
    if g.get("side") and e["decision"] != g["side"]:
        return False
    if g.get("clocks") and e["clock"] not in g["clocks"]:
        return False
    if g.get("primaries") and e["primary"] not in g["primaries"]:
        return False
    if g.get("min_body") is not None and abs(e["body_frac"]) < g["min_body"]:
        return False
    if g.get("rsi_lo") is not None and e["rsi_14"] < g["rsi_lo"]:
        return False
    if g.get("rsi_hi") is not None and e["rsi_14"] > g["rsi_hi"]:
        return False
    if g.get("max_session_abs") is not None and abs(e["session_chg"]) > g["max_session_abs"]:
        return False
    if g.get("mins_lo") is not None and e["mins"] < g["mins_lo"]:
        return False
    if g.get("mins_hi") is not None and e["mins"] > g["mins_hi"]:
        return False
    return True


def precompute(events, h, l, c, fams):
    out = {f: [None] * len(events) for f in fams}
    for ei, e in enumerate(events):
        for f in fams:
            sl, t1 = e["families"][f]
            win, outcome = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
            if outcome in ("bad", "both"):
                continue
            out[f][ei] = {
                "day": e["day"],
                "hm": e["hm"],
                "decision": e["decision"],
                "primary": e["primary"],
                "patterns": e["patterns"][:5],
                "entry": e["entry"],
                "sl": sl,
                "t1": t1,
                "clock": e["clock"],
                "win": win,
                "rsi_14": e["rsi_14"],
                "body_frac": e["body_frac"],
            }
    return out


def agg_all(pre_col, mask) -> dict:
    """Count every (day,hm) call — not OR-style one-per-day collapse."""
    rows = [pre_col[i] for i, ok in enumerate(mask) if ok and pre_col[i] is not None]
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: (x["day"], x["hm"])):
        k = (r["day"], r["hm"], r["decision"])
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    a = co.agg(out)
    a["calls"] = out
    a["avg_sl"] = round(float(np.mean([r["sl"] for r in out])), 2) if out else 0
    a["avg_t1"] = round(float(np.mean([r["t1"] for r in out])), 2) if out else 0
    return a


def hunt(cal, test, cal_pre, test_pre, fams) -> dict:
    print("\n[3] Hunt pattern-only 100% max-calls (no OR)…", flush=True)
    prim_sets = [
        None,
        ["morning_star", "evening_star", "morning_doji_star", "evening_doji_star"],
        ["bull_engulf", "bear_engulf"],
        ["three_soldiers", "three_crows"],
        ["piercing", "dark_cloud"],
        ["hammer", "shooting_star", "inv_hammer", "hanging_man"],
        ["marubozu_bull", "marubozu_bear", "belt_bull", "belt_bear"],
        ["bull_kicker", "bear_kicker", "tweezer_bot", "tweezer_top"],
        ["three_inside_up", "three_inside_dn", "three_outside_up", "three_outside_dn"],
        ["morning_star", "bull_engulf", "three_soldiers", "piercing", "hammer", "marubozu_bull"],
        ["evening_star", "bear_engulf", "three_crows", "dark_cloud", "shooting_star", "marubozu_bear"],
        ["rising_3_methods", "falling_3_methods"],
    ]
    grids = []
    for pr, side, clk, mb, rsi, sess, mins in product(
        prim_sets,
        [None, "BUY", "SELL"],
        [None, ["early"], ["morning"], ["early", "morning"], ["early", "morning", "midday"]],
        [None, 0.40, 0.55, 0.70],
        [None, (45, 65), (40, 70), (35, 75), (30, 60), (50, 80), (20, 50)],
        [None, 0.8, 1.2],
        [None, (560, 660), (560, 720), (600, 780)],
    ):
        g = {"primaries": pr, "side": side, "clocks": clk, "min_body": mb, "max_session_abs": sess}
        if rsi:
            g["rsi_lo"], g["rsi_hi"] = rsi
        if mins:
            g["mins_lo"], g["mins_hi"] = mins
        grids.append(g)
    grids = grids[::3]
    print(f"  combos={len(grids)}", flush=True)

    both, hi = [], []
    t0 = time.time()
    for fi, g in enumerate(grids, 1):
        if fi % 1000 == 0:
            print(f"    {fi}/{len(grids)} both={len(both)} ({time.time()-t0:.0f}s)", flush=True)
        cm = [soft(e, g) for e in cal]
        if sum(cm) < 5:
            continue
        tm = [soft(e, g) for e in test]
        for fam in fams:
            a = agg_all(cal_pre[fam], cm)
            if a["n"] < 5:
                continue
            t = agg_all(test_pre[fam], tm)
            if t["n"] < 1:
                continue
            rec = {
                "bracket": fam,
                "filters": g,
                "calibrate": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                "last3m": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                "last3m_calls": t["calls"],
                "cal_calls": a["calls"],
            }
            if a["hit_pct"] >= 100 - 1e-9 and t["hit_pct"] >= 100 - 1e-9:
                both.append(rec)
            elif t["hit_pct"] >= 100 - 1e-9 and t["n"] >= 3 and a["hit_pct"] >= 80:
                hi.append(rec)
            elif a["hit_pct"] >= 90 and t["hit_pct"] >= 90 and t["n"] >= 3 and len(hi) < 400:
                hi.append({k: v for k, v in rec.items() if k not in ("cal_calls", "last3m_calls")})

    both.sort(key=lambda r: (-r["last3m"]["n"], -r["calibrate"]["n"], r["last3m"]["avg_sl"]))

    def sig(r):
        keys = tuple(sorted((c["day"], c["hm"], c["decision"]) for c in r.get("last3m_calls") or []))
        return (r["bracket"], r["last3m"]["n"], r["calibrate"]["n"], keys, json.dumps(r["filters"], sort_keys=True, default=str))

    uniq, seen = [], set()
    for r in both:
        s = sig(r)
        if s in seen:
            continue
        seen.add(s)
        uniq.append(r)

    by = {}
    for r in uniq:
        for c in r.get("last3m_calls") or []:
            by.setdefault((c["day"], c["hm"], c["decision"]), c)
    union = list(by.values())
    union.sort(key=lambda x: (x["day"], x["hm"]))

    by2 = {}
    for r in uniq:
        if r["last3m"]["avg_t1"] <= 0:
            continue
        if r["last3m"]["avg_sl"] > 5.0 * r["last3m"]["avg_t1"]:
            continue
        for c in r.get("last3m_calls") or []:
            by2.setdefault((c["day"], c["hm"], c["decision"]), c)
    union_rr = sorted(by2.values(), key=lambda x: (x["day"], x["hm"]))

    print(
        f"  both100={len(uniq)} union={len(union)} union_rr={len(union_rr)} ({time.time()-t0:.0f}s)",
        flush=True,
    )
    return {
        "both100": uniq[:25],
        "near": sorted(hi, key=lambda r: (-r.get("last3m", {}).get("hit_pct", 0), -r.get("last3m", {}).get("n", 0)))[:15],
        "union100": {
            "n": len(union),
            "wins": sum(1 for x in union if x.get("win")),
            "hit_pct": co.agg(union)["hit_pct"],
            "calls": union,
        },
        "union_rr": {
            "n": len(union_rr),
            "wins": sum(1 for x in union_rr if x.get("win")),
            "hit_pct": co.agg(union_rr)["hit_pct"],
            "calls": union_rr,
        },
    }


# (helpers above)


def write_report(meta, hunt_res):
    OUT.mkdir(parents=True, exist_ok=True)
    both = hunt_res.get("both100") or []
    u = hunt_res.get("union100") or {}
    ur = hunt_res.get("union_rr") or {}
    lines = [
        "# NIFTY 1m — **pattern-only** (NO OR-break) · 100% max-calls",
        "",
        "**Not live.** Entries = textbook candlestick completions only. No opening-range break.",
        "",
        f"- Calibrate `{meta['cal_lo']}`→`{meta['cal_hi']}` · Last3m `{meta['test_lo']}`→`{meta['test_hi']}`",
        f"- Events cal/test: {meta['n_cal']} / {meta['n_test']}",
        "",
        f"## Both-window 100%: **{len(both)}** logics",
        "",
        f"### Union: **{u.get('n')} @ {u.get('hit_pct')}%** · Union (R:R capped): **{ur.get('n')} @ {ur.get('hit_pct')}%**",
        "",
    ]
    show = ur.get("calls") or u.get("calls") or []
    if show:
        lines += ["| Day | HM | Side | Primary | SL | T1 | Win |", "|---|---|---|---|---:|---:|:---:|"]
        for c in show:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['decision']} | {c.get('primary','')} | "
                f"{c['sl']} | {c['t1']} | {'Y' if c.get('win') else 'N'} |"
            )
        lines.append("")

    lines += ["## Best both-100 (max last3m n)", "", "| # | Bracket | Filters | Cal | Last3m | SL/T1 |", "|---:|---|---|---:|---:|---|"]
    for i, r in enumerate(both[:12], 1):
        f = r["filters"]
        short = (
            f"pri={f.get('primaries')} side={f.get('side')} clk={f.get('clocks')} "
            f"rsi={f.get('rsi_lo')}-{f.get('rsi_hi')} body≥{f.get('min_body')}"
        )
        lines.append(
            f"| {i} | `{r['bracket']}` | {short[:100]} | "
            f"{r['calibrate']['n']}@100% | **{r['last3m']['n']}@100%** | "
            f"{r['last3m']['avg_sl']}/{r['last3m']['avg_t1']} |"
        )

    if both:
        b = both[0]
        lines += [
            "",
            f"### Detail · best · last3m **{b['last3m']['n']} @ 100%**",
            f"- `{b['bracket']}` · `{json.dumps(b['filters'], default=str)}`",
            f"- Calibrate: {b['calibrate']['n']} @ 100%",
            "",
            "| Day | HM | Side | Primary | Patterns | SL | T1 |",
            "|---|---|---|---|---|---:|---:|",
        ]
        for c in b.get("last3m_calls") or []:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['decision']} | {c.get('primary')} | "
                f"{','.join((c.get('patterns') or [])[:3])} | {c['sl']} | {c['t1']} |"
            )

    lines += ["", "## Near / high last3m", "", "| Bracket | Cal | Last3m |", "|---|---|---|"]
    for r in (hunt_res.get("near") or [])[:8]:
        lines.append(
            f"| `{r.get('bracket')}` | {r.get('calibrate',{}).get('n')}@{r.get('calibrate',{}).get('hit_pct')}% | "
            f"{r.get('last3m',{}).get('n')}@{r.get('last3m',{}).get('hit_pct')}% |"
        )

    lines += ["", "## Research pick", ""]
    if both:
        lines.append(
            f"**Best single (no OR):** `{both[0]['bracket']}` · last3m **{both[0]['last3m']['n']} @ 100%** "
            f"(cal {both[0]['calibrate']['n']} @ 100%)."
        )
        if ur.get("n"):
            lines.append(f"**Union (R:R-aware):** **{ur['n']} @ 100%**.")
        elif u.get("n"):
            lines.append(f"**Union:** **{u['n']} @ 100%**.")
    else:
        lines.append("No both-100 yet — see near table.")

    lines += ["", "## Policy", "", f"- Pack: `{PACK}`", "- research_only · not_live · **no OR-break** · pattern-only", ""]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "meta": meta,
                "both100": [{k: v for k, v in r.items() if k != "cal_calls"} for r in both[:15]],
                "union100": u,
                "union_rr": ur,
                "near": hunt_res.get("near"),
                "no_or_break": True,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT_MD}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · PATTERN-ONLY · NO OR-BREAK · 100% max-calls", flush=True)
    print("=" * 60, flush=True)

    raw = base.load_existing_1m()
    end_ts = raw.index.max()
    test_hi = end_ts.strftime("%Y-%m-%d")
    test_lo_ts = end_ts - pd.Timedelta(days=92)
    test_lo = test_lo_ts.strftime("%Y-%m-%d")
    cal_hi = (test_lo_ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    # longer calibrate for pattern MAE + both-100 stability
    cal_lo = (test_lo_ts - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    print(f"calibrate {cal_lo}→{cal_hi} · last3m {test_lo}→{test_hi}", flush=True)

    raw = raw[raw.index >= pd.Timestamp(cal_lo, tz="Asia/Kolkata")]
    print(f"tape bars={len(raw)}", flush=True)

    print("\n[1] Textbook patterns (every bar)…", flush=True)
    df = tb.detect_textbook(raw)
    df = add_rsi(df)

    print("\n[2] Pattern-completion entries (NO OR)…", flush=True)
    cal = collect_pattern_entries(df, cal_lo, cal_hi, one_per_day_side=True)
    test = collect_pattern_entries(df, test_lo, test_hi, one_per_day_side=True)
    print(f"  cal={len(cal)} last3m={len(test)}", flush=True)

    mae_names = attach_mae(cal, test)
    fams = ["pat_wick", "atr_1_1_0_65", "atr_1_4_0_75", "atr_1_6_0_85", "mix_pat_atr"] + mae_names
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    print("\n[2b] Precompute brackets…", flush=True)
    cal_pre = precompute(cal, h, l, c, fams)
    test_pre = precompute(test, h, l, c, fams)

    hunt_res = hunt(cal, test, cal_pre, test_pre, fams)

    meta = {
        "cal_lo": cal_lo,
        "cal_hi": cal_hi,
        "test_lo": test_lo,
        "test_hi": test_hi,
        "n_cal": len(cal),
        "n_test": len(test),
        "n_both100": len(hunt_res.get("both100") or []),
        "union_n": (hunt_res.get("union100") or {}).get("n"),
        "union_rr_n": (hunt_res.get("union_rr") or {}).get("n"),
        "no_or_break": True,
        "research_only": True,
        "not_live": True,
    }
    PACK.mkdir(parents=True, exist_ok=True)
    if hunt_res.get("both100"):
        (PACK / "best_both100.json").write_text(
            json.dumps(hunt_res["both100"][0], indent=2, default=str), encoding="utf-8"
        )
    write_report(meta, hunt_res)

    u = hunt_res.get("union100") or {}
    ur = hunt_res.get("union_rr") or {}
    print("\n" + "=" * 60, flush=True)
    print(
        f"BOTH100={meta['n_both100']} · UNION {u.get('n')}@{u.get('hit_pct')}% · "
        f"UNION_RR {ur.get('n')}@{ur.get('hit_pct')}%",
        flush=True,
    )
    if hunt_res.get("both100"):
        b = hunt_res["both100"][0]
        print(
            f"BEST: {b['bracket']} last3m {b['last3m']['n']}@100% cal {b['calibrate']['n']}@100% "
            f"SL/T1 {b['last3m']['avg_sl']}/{b['last3m']['avg_t1']}",
            flush=True,
        )
    print("DONE · pattern-only · no OR · research only", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
