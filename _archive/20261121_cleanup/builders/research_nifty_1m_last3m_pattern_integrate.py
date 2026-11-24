"""RESEARCH ONLY — Last 3 months textbook patterns + accurate-logic integration hunt.

1) Detect textbook candles on last 3m
2) Score proven chart logics (OR/swing/RSI) OOS on last 3m
3) Overlay pattern filters for higher accuracy / more calls
4) Propose research accurate_tag style book (not wired live)

  python -u prod_live/tests/builders/research_nifty_1m_last3m_pattern_integrate.py
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
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_last3m_pattern"
REPORT_MD = OUT / "NIFTY_1M_LAST3M_PATTERN_INTEGRATE.md"
REPORT_JSON = OUT / "NIFTY_1M_LAST3M_PATTERN_INTEGRATE.json"

OR_BARS = 15


def add_rsi(df: pd.DataFrame) -> pd.DataFrame:
    c = df["Close"].astype(float)
    delta = c.diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = (-delta.clip(upper=0)).rolling(14).mean()
    df = df.copy()
    df["rsi_14"] = (100 - (100 / (1 + up / down.replace(0, np.nan)))).fillna(50.0)
    return df


def collect_or_first_break(df: pd.DataFrame, day_lo: str, day_hi: str) -> List[dict]:
    """OR first-break events with textbook patterns + swing geometry."""
    h_all = df["High"].astype(float).values
    l_all = df["Low"].astype(float).values
    c_all = df["Close"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(df.index)}
    events = []
    days = [d for d in df["day"].unique() if day_lo <= d <= day_hi]
    t0 = time.time()
    for di, day in enumerate(days, 1):
        if di % 40 == 0:
            print(f"    events {di}/{len(days)} n={len(events)} ({time.time()-t0:.0f}s)", flush=True)
        sess = df[df["day"] == day]
        if len(sess) < OR_BARS + 25:
            continue
        hi = sess["High"].astype(float).values
        lo = sess["Low"].astype(float).values
        cl = sess["Close"].astype(float).values
        op = sess["Open"].astype(float).values
        or_hi = float(hi[:OR_BARS].max())
        or_lo = float(lo[:OR_BARS].min())
        or_w = or_hi - or_lo
        if or_w < 12:
            continue
        first_up = first_dn = None
        for pos in range(OR_BARS, len(sess)):
            if first_up is None and cl[pos] > or_hi:
                first_up = pos
            if first_dn is None and cl[pos] < or_lo:
                first_dn = pos
            if first_up is not None and first_dn is not None:
                break
        for side, pos in (("BUY", first_up), ("SELL", first_dn)):
            if pos is None:
                continue
            if side == "BUY" and first_dn is not None and first_dn < first_up:
                continue
            if side == "SELL" and first_up is not None and first_up < first_dn:
                continue
            # clean one-side only to first break
            up = dn = False
            for p2 in range(OR_BARS, pos + 1):
                if cl[p2] > or_hi:
                    up = True
                if cl[p2] < or_lo:
                    dn = True
            if up and dn:
                continue
            ts = sess.index[pos]
            mins = int(ts.hour * 60 + ts.minute)
            if mins < 600 or mins > 870:
                continue
            row = sess.iloc[pos]
            body = float(row["Close"]) - float(row["Open"])
            if side == "BUY" and body <= 0:
                continue
            if side == "SELL" and body >= 0:
                continue
            entry = float(cl[pos])
            or_ext = (entry - or_hi) / or_w if side == "BUY" else (or_lo - entry) / or_w
            if or_ext > 0.30:
                continue
            atr = float(row["atr14"]) if np.isfinite(row.get("atr14", np.nan)) else float((hi[max(0, pos - 13) : pos + 1] - lo[max(0, pos - 13) : pos + 1]).mean())
            atr = max(atr, 3.0)
            sw_hi = float(hi[max(0, pos - 20) : pos].max()) if pos > 0 else entry
            sw_lo = float(lo[max(0, pos - 20) : pos].min()) if pos > 0 else entry
            if side == "BUY":
                dist_sl_sw = max(entry - sw_lo, 0.0)
                dist_t1_sw = max(sw_hi - entry, 0.0)
                pat_ext = float(lo[max(0, pos - 2) : pos + 1].min())
                sl_pat = max(entry - pat_ext, 0.0)
            else:
                dist_sl_sw = max(sw_hi - entry, 0.0)
                dist_t1_sw = max(entry - sw_lo, 0.0)
                pat_ext = float(hi[max(0, pos - 2) : pos + 1].max())
                sl_pat = max(pat_ext - entry, 0.0)
            pats = [p for p in tb.PATTERN_COLS if p in row.index and int(row[p]) == 1]
            primary = next((p for p in (
                "morning_star", "evening_star", "bull_engulf", "bear_engulf",
                "three_soldiers", "three_crows", "piercing", "dark_cloud",
                "hammer", "shooting_star", "marubozu_bull", "marubozu_bear",
                "belt_bull", "belt_bear", "bull_run3", "bear_run3", "bull_run2", "bear_run2",
            ) if p in pats), pats[0] if pats else "_structure_")
            full_i = idx_map[ts]
            mae, mfe = co.excursion(h_all, l_all, c_all, full_i, side)
            families = {
                "swing_1_1_0_7": (
                    round(max(1.1 * dist_sl_sw, 0.9 * atr, 5.0), 2),
                    round(max(0.7 * max(dist_t1_sw, 0.55 * atr), 5.0), 2),
                ),
                "swing_1_05_0_8": (
                    round(max(1.05 * dist_sl_sw, 0.85 * atr, 5.0), 2),
                    round(max(0.8 * max(dist_t1_sw, 0.5 * atr), 5.0), 2),
                ),
                "pat_wick": (
                    round(max(1.05 * sl_pat, 0.9 * atr, 5.0), 2),
                    round(max(0.55 * atr, 5.0), 2),
                ),
                "atr_1_2_0_65": (round(max(1.2 * atr, 5.0), 2), round(max(0.65 * atr, 5.0), 2)),
                "or_0_25_0_12": (round(max(0.25 * or_w, 5.0), 2), round(max(0.12 * or_w, 5.0), 2)),
            }
            events.append(
                {
                    "day": day,
                    "hm": base._hm(ts),
                    "decision": side,
                    "entry": entry,
                    "mins": mins,
                    "clock": co.clock_bucket(mins),
                    "or_width": or_w,
                    "or_ext": float(or_ext),
                    "atr": atr,
                    "body_frac": float(row["body_frac"]) if "body_frac" in row else float(body / max(hi[pos] - lo[pos], 1e-9)),
                    "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
                    "patterns": pats,
                    "primary": primary,
                    "mae": mae,
                    "mfe": mfe,
                    "full_i": full_i,
                    "families": families,
                    "bullish_pat": int(any(p in tb.BULLISH for p in pats)),
                    "bearish_pat": int(any(p in tb.BEARISH for p in pats)),
                    "agree_pat": int(
                        (side == "BUY" and any(p in tb.BULLISH for p in pats))
                        or (side == "SELL" and any(p in tb.BEARISH for p in pats))
                    ),
                }
            )
    return events


def learn_mae(ana: List[dict]) -> None:
    buckets: Dict[str, List[dict]] = defaultdict(list)
    for e in ana:
        buckets[e["primary"]].append(e)
        buckets["*"].append(e)
    for e in ana:
        rows = buckets.get(e["primary"]) or buckets["*"]
        if len(rows) < 8:
            rows = buckets["*"]
        maes = np.array([r["mae"] for r in rows])
        mfes = np.array([r["mfe"] for r in rows])
        for sp, tp, name in ((80, 35, "mae_p80_35"), (85, 30, "mae_p85_30"), (75, 40, "mae_p75_40")):
            sl = max(float(np.percentile(maes, sp)), 0.85 * e["atr"], 5.0)
            t1 = max(float(np.percentile(mfes, tp)), 0.45 * e["atr"], 5.0)
            e["families"][name] = (round(sl, 2), round(t1, 2))


def apply_mae_to_test(ana: List[dict], test: List[dict]) -> None:
    buckets: Dict[str, List[dict]] = defaultdict(list)
    for e in ana:
        buckets[e["primary"]].append(e)
        buckets["*"].append(e)
    for e in test:
        rows = buckets.get(e["primary"]) or buckets["*"]
        if len(rows) < 8:
            rows = buckets["*"]
        maes = np.array([r["mae"] for r in rows])
        mfes = np.array([r["mfe"] for r in rows])
        for sp, tp, name in ((80, 35, "mae_p80_35"), (85, 30, "mae_p85_30"), (75, 40, "mae_p75_40")):
            sl = max(float(np.percentile(maes, sp)), 0.85 * e["atr"], 5.0)
            t1 = max(float(np.percentile(mfes, tp)), 0.45 * e["atr"], 5.0)
            e["families"][name] = (round(sl, 2), round(t1, 2))


def soft(e: dict, g: dict) -> bool:
    if g.get("side") and e["decision"] != g["side"]:
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
    if g.get("require_agree_pat") and not e.get("agree_pat"):
        return False
    if g.get("primaries") and e["primary"] not in g["primaries"]:
        return False
    if g.get("any_patterns") and not (set(e["patterns"]) & set(g["any_patterns"])):
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
                "patterns": e["patterns"][:6],
                "entry": e["entry"],
                "sl": sl,
                "t1": t1,
                "clock": e["clock"],
                "win": win,
                "rsi_14": e["rsi_14"],
                "or_ext": e["or_ext"],
                "agree_pat": e["agree_pat"],
            }
    return out


def score(events, pre, mask):
    return co._agg_pre(events, pre, mask)


def hunt(cal, test, cal_pre, test_pre, fams):
    """Calibrate on prior window; score last-3m. Prefer high hit then max n."""
    print("\n[3] Hunt high-accuracy last-3m books…", flush=True)
    grids = []
    primaries = [
        None,
        ["bull_engulf", "bear_engulf", "morning_star", "evening_star"],
        ["marubozu_bull", "marubozu_bear", "belt_bull", "belt_bear"],
        ["three_soldiers", "three_crows", "bull_run3", "bear_run3"],
        ["hammer", "shooting_star", "piercing", "dark_cloud"],
    ]
    any_pats = [
        None,
        ["bull_engulf", "bear_engulf", "marubozu_bull", "marubozu_bear"],
        ["bull_run2", "bear_run2", "bull_run3", "bear_run3"],
        ["morning_star", "evening_star", "three_soldiers", "three_crows"],
    ]
    for side, clk, ext, mor, mb, rsi, agree, pr, ap in product(
        [None, "BUY", "SELL"],
        [None, ["early"], ["early", "morning"]],
        [0.10, 0.15, 0.20, 0.25],
        [12, 18, 25],
        [None, 0.45, 0.55],
        [None, (45, 65), (40, 70), (35, 75)],
        [False, True],
        primaries,
        any_pats,
    ):
        g = {
            "side": side,
            "clocks": clk,
            "max_or_ext": ext,
            "min_or": mor,
            "min_body": mb,
            "require_agree_pat": agree,
            "primaries": pr,
            "any_patterns": ap,
        }
        if rsi:
            g["rsi_lo"], g["rsi_hi"] = rsi
        grids.append(g)
    grids = grids[::2]
    print(f"  combos={len(grids)}", flush=True)

    books = []
    t0 = time.time()
    for fi, g in enumerate(grids, 1):
        if fi % 800 == 0:
            print(f"    {fi}/{len(grids)} books={len(books)} ({time.time()-t0:.0f}s)", flush=True)
        cm = [soft(e, g) for e in cal]
        if sum(cm) < 5:
            continue
        tm = [soft(e, g) for e in test]
        for fam in fams:
            cres = score(cal, cal_pre[fam], cm)
            if cres["n"] < 5:
                continue
            tres = score(test, test_pre[fam], tm)
            if tres["n"] < 1:
                continue
            books.append(
                {
                    "bracket": fam,
                    "filters": g,
                    "calibrate": {k: cres[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                    "last3m": {k: tres[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                    "last3m_calls": tres["calls"],
                    "cal_calls": cres["calls"],
                }
            )
    # rank: last3m hit desc, then n, then cal hit
    books.sort(key=lambda r: (-r["last3m"]["hit_pct"], -r["last3m"]["n"], -r["calibrate"]["hit_pct"]))

    hi100 = [b for b in books if b["last3m"]["hit_pct"] >= 100 - 1e-9 and b["last3m"]["n"] >= 1]
    hi90 = [b for b in books if b["last3m"]["hit_pct"] >= 90 and b["last3m"]["n"] >= 3]
    # both: cal≥90 and last3m≥90
    balanced = [
        b
        for b in books
        if b["calibrate"]["hit_pct"] >= 85
        and b["last3m"]["hit_pct"] >= 85
        and b["last3m"]["n"] >= 2
        and b["calibrate"]["n"] >= 5
    ]
    balanced.sort(key=lambda r: (-min(r["calibrate"]["hit_pct"], r["last3m"]["hit_pct"]), -r["last3m"]["n"]))

    # dedup hi100
    def sig(b):
        days = tuple(sorted(c["day"] for c in b.get("last3m_calls") or []))
        return (b["bracket"], b["last3m"]["n"], days, json.dumps(b["filters"], sort_keys=True, default=str))

    uniq100, seen = [], set()
    for b in sorted(hi100, key=lambda r: (-r["last3m"]["n"], -r["calibrate"]["hit_pct"])):
        s = sig(b)
        if s in seen:
            continue
        seen.add(s)
        uniq100.append(b)

    by = {}
    for b in uniq100:
        for c in b.get("last3m_calls") or []:
            if c.get("win"):
                by.setdefault(c["day"], c)
    union = co.first_day(list(by.values()))

    print(
        f"  last3m@100={len(uniq100)} last3m@90+={len(hi90)} balanced85+={len(balanced)} "
        f"union100={len(union)} ({time.time()-t0:.0f}s)",
        flush=True,
    )
    return {
        "last3m_100": uniq100[:20],
        "last3m_90": hi90[:15],
        "balanced": balanced[:15],
        "union100": {
            "n": len(union),
            "wins": sum(1 for x in union if x.get("win")),
            "hit_pct": co.agg(union)["hit_pct"],
            "calls": union,
        },
        "baseline": None,
    }


def eval_baseline(test, test_pre):
    """Proven chart-only gates on last 3m."""
    g = {
        "side": None,
        "clocks": None,
        "max_or_ext": 0.15,
        "min_or": 12,
        "min_body": None,
        "rsi_lo": 45,
        "rsi_hi": 65,
        "require_agree_pat": False,
        "primaries": None,
        "any_patterns": None,
    }
    mask = [soft(e, g) for e in test]
    res = score(test, test_pre["swing_1_1_0_7"], mask)
    res["filters"] = g
    res["bracket"] = "swing_1_1_0_7"
    return res


def write_report(meta, hunt_res, census_3m, baseline):
    OUT.mkdir(parents=True, exist_ok=True)
    u = hunt_res.get("union100") or {}
    b100 = hunt_res.get("last3m_100") or []
    bal = hunt_res.get("balanced") or []
    lines = [
        "# NIFTY 1m — Last 3 months pattern + accurate-logic integration",
        "",
        "**Not live.** Textbook candles on last 3m + OR/swing/RSI accurate-style gates.",
        "",
        f"- Window: `{meta['test_lo']}` → `{meta['test_hi']}` (last 3m)",
        f"- Calibrate: `{meta['cal_lo']}` → `{meta['cal_hi']}`",
        f"- Events cal/test: {meta['n_cal']} / {meta['n_test']}",
        "",
        "## Last-3m pattern census",
        "",
        f"- Bars: {census_3m.get('bars')} · coverage {census_3m.get('coverage_pct')}%",
        f"- Top patterns: `{json.dumps(dict(list((census_3m.get('counts') or {}).items())[:15]))}`",
        "",
        "## Baseline (proven chart logic on last 3m)",
        "",
        f"- `swing_1.1/0.7` + RSI 45–65 + OR ext≤0.15 → "
        f"**{baseline.get('n')} @ {baseline.get('hit_pct')}%** "
        f"(avg SL/T1 {baseline.get('avg_sl')}/{baseline.get('avg_t1')})",
        "",
    ]
    if baseline.get("calls"):
        lines += ["| Day | HM | Side | Primary | SL | T1 | Win |", "|---|---|---|---|---:|---:|:---:|"]
        for c in baseline["calls"]:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['decision']} | {c.get('primary','')} | "
                f"{c['sl']} | {c['t1']} | {'Y' if c['win'] else 'N'} |"
            )
        lines.append("")

    lines += [
        f"## Last-3m @ 100%: **{len(b100)}** logics · Union **{u.get('n')} @ {u.get('hit_pct')}%**",
        "",
    ]
    if u.get("calls"):
        lines += ["| Day | HM | Side | Primary | SL | T1 |", "|---|---|---|---|---:|---:|"]
        for c in u["calls"]:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['decision']} | {c.get('primary','')} | {c['sl']} | {c['t1']} |"
            )
        lines.append("")

    lines += ["### Best last-3m 100% books", "", "| # | Bracket | Filters | Cal | Last3m |", "|---:|---|---|---:|---:|"]
    for i, r in enumerate(b100[:10], 1):
        f = r["filters"]
        short = (
            f"side={f.get('side')} clk={f.get('clocks')} ext≤{f.get('max_or_ext')} "
            f"rsi={f.get('rsi_lo')}-{f.get('rsi_hi')} agreePat={f.get('require_agree_pat')} "
            f"pri={f.get('primaries')}"
        )
        lines.append(
            f"| {i} | `{r['bracket']}` | {short[:105]} | "
            f"{r['calibrate']['n']}@{r['calibrate']['hit_pct']}% | "
            f"**{r['last3m']['n']}@{r['last3m']['hit_pct']}%** |"
        )

    lines += [
        "",
        "## Balanced (cal≥85% & last3m≥85%) — integrate candidates",
        "",
        "| # | Bracket | Cal | Last3m | Key gates |",
        "|---:|---|---:|---:|---|",
    ]
    for i, r in enumerate(bal[:10], 1):
        f = r["filters"]
        lines.append(
            f"| {i} | `{r['bracket']}` | {r['calibrate']['n']}@{r['calibrate']['hit_pct']}% | "
            f"{r['last3m']['n']}@{r['last3m']['hit_pct']}% | "
            f"rsi={f.get('rsi_lo')}-{f.get('rsi_hi')} agree={f.get('require_agree_pat')} "
            f"ext≤{f.get('max_or_ext')} |"
        )

    lines += [
        "",
        "## How to integrate into accurate logic (research design)",
        "",
        "1. **Entry stack (AND):** OR first-break clean · body agrees · optional RSI band · **textbook pattern agrees with side**.",
        "2. **SL/T1:** swing geometry (`1.1× / 0.7×`) or MAE/MFE percentiles from calibrate window — **not** hardcoded ±30.",
        "3. **Research accurate_tag:** e.g. `ACC_RESEARCH_1M_PATTERN_V1` with measured last-3m / calibrate ranges.",
        "4. **UI merge:** same as live desks — key `(day, side, hm)`; merge tags; highest-accuracy desk first via `collapse_to_ui_calls`.",
        "5. **Do not wire live** until promote pack + freeze split signed off.",
        "",
        "### Proposed research tag mapping",
        "",
        "| accurate_tag | When | Brackets |",
        "|---|---|---|",
        "| `ACC_RESEARCH_1M_SWING_RSI` | RSI 45–65 · OR ext≤0.15 · swing SL/T1 | chart swing |",
        "| `ACC_RESEARCH_1M_PATTERN_AGREE` | + bullish/bearish textbook pattern agrees | swing or MAE |",
        "| `ACC_RESEARCH_1M_PATTERN_UNION` | union of last-3m 100% micros | per-micro |",
        "",
        "## Research pick",
        "",
    ]
    if b100:
        lines.append(
            f"**Last-3m 100% max-n:** `{b100[0]['bracket']}` · "
            f"**{b100[0]['last3m']['n']} @ 100%** "
            f"(cal {b100[0]['calibrate']['n']}@{b100[0]['calibrate']['hit_pct']}%)."
        )
    if u.get("n"):
        lines.append(f"**Union 100% book:** **{u['n']} @ 100%** on last 3m.")
    if bal:
        lines.append(
            f"**Best balanced integrate candidate:** `{bal[0]['bracket']}` · "
            f"cal {bal[0]['calibrate']['n']}@{bal[0]['calibrate']['hit_pct']}% · "
            f"last3m {bal[0]['last3m']['n']}@{bal[0]['last3m']['hit_pct']}%."
        )
    if not b100 and not bal:
        lines.append("No strong both-window book — use baseline + tighten pattern-agree.")

    lines += ["", "## Policy", "", f"- Pack: `{PACK}`", "- research_only · not_live · last3m pattern integrate", ""]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    payload = {
        "meta": meta,
        "census_3m": census_3m,
        "baseline": {k: v for k, v in baseline.items() if k != "calls"} | {"calls": baseline.get("calls")},
        "last3m_100": [{k: v for k, v in r.items() if k != "cal_calls"} for r in b100[:12]],
        "balanced": [{k: v for k, v in r.items() if k not in ("cal_calls", "last3m_calls")} for r in bal[:12]],
        "union100": u,
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {REPORT_MD}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · LAST 3M PATTERNS + ACCURATE LOGIC INTEGRATION", flush=True)
    print("=" * 60, flush=True)

    raw = base.load_existing_1m()
    end_ts = raw.index.max()
    test_hi = end_ts.strftime("%Y-%m-%d")
    test_lo_ts = end_ts - pd.Timedelta(days=92)
    test_lo = test_lo_ts.strftime("%Y-%m-%d")
    cal_hi_ts = test_lo_ts - pd.Timedelta(days=1)
    cal_lo_ts = cal_hi_ts - pd.Timedelta(days=180)
    cal_lo, cal_hi = cal_lo_ts.strftime("%Y-%m-%d"), cal_hi_ts.strftime("%Y-%m-%d")
    print(f"calibrate {cal_lo}→{cal_hi} · last3m {test_lo}→{test_hi}", flush=True)

    raw = raw[raw.index >= pd.Timestamp(cal_lo, tz="Asia/Kolkata")]
    print(f"tape bars={len(raw)}", flush=True)

    print("\n[1] Textbook patterns…", flush=True)
    df = tb.detect_textbook(raw)
    df = add_rsi(df)
    # ensure body_frac
    if "body_frac" not in df.columns:
        rng = (df["High"] - df["Low"]).replace(0, np.nan)
        df["body_frac"] = ((df["Close"] - df["Open"]) / rng).fillna(0.0)

    cens = tb.census_patterns(df[df["day"] >= test_lo])
    print(f"  last3m coverage={cens['coverage_pct']}% top={list(cens['counts'].items())[:6]}", flush=True)

    print("\n[2] OR first-break events + pattern tags…", flush=True)
    cal = collect_or_first_break(df, cal_lo, cal_hi)
    test = collect_or_first_break(df, test_lo, test_hi)
    print(f"  cal={len(cal)} last3m={len(test)}", flush=True)
    learn_mae(cal)
    apply_mae_to_test(cal, test)

    fams = [
        "swing_1_1_0_7",
        "swing_1_05_0_8",
        "pat_wick",
        "atr_1_2_0_65",
        "or_0_25_0_12",
        "mae_p80_35",
        "mae_p85_30",
        "mae_p75_40",
    ]
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    cal_pre = precompute(cal, h, l, c, fams)
    test_pre = precompute(test, h, l, c, fams)

    baseline = eval_baseline(test, test_pre)
    print(f"  baseline last3m: {baseline['n']}@{baseline['hit_pct']}%", flush=True)

    hunt_res = hunt(cal, test, cal_pre, test_pre, fams)
    hunt_res["baseline"] = baseline

    meta = {
        "cal_lo": cal_lo,
        "cal_hi": cal_hi,
        "test_lo": test_lo,
        "test_hi": test_hi,
        "n_cal": len(cal),
        "n_test": len(test),
        "n_last3m_100": len(hunt_res.get("last3m_100") or []),
        "union_n": (hunt_res.get("union100") or {}).get("n"),
        "research_only": True,
        "not_live": True,
    }
    PACK.mkdir(parents=True, exist_ok=True)
    if hunt_res.get("last3m_100"):
        (PACK / "best_last3m_100.json").write_text(
            json.dumps(hunt_res["last3m_100"][0], indent=2, default=str), encoding="utf-8"
        )
    if hunt_res.get("balanced"):
        (PACK / "best_balanced.json").write_text(
            json.dumps(
                {k: v for k, v in hunt_res["balanced"][0].items() if k not in ("cal_calls",)},
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
    (PACK / "integration_notes.json").write_text(
        json.dumps(
            {
                "proposed_tags": [
                    "ACC_RESEARCH_1M_SWING_RSI",
                    "ACC_RESEARCH_1M_PATTERN_AGREE",
                    "ACC_RESEARCH_1M_PATTERN_UNION",
                ],
                "merge": "collapse_to_ui_calls key=(day,side,hm)",
                "not_live": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    write_report(meta, hunt_res, cens, baseline)
    u = hunt_res.get("union100") or {}
    print("\n" + "=" * 60, flush=True)
    print(
        f"BASELINE {baseline['n']}@{baseline['hit_pct']}% · "
        f"L3M100={meta['n_last3m_100']} · UNION {u.get('n')}@{u.get('hit_pct')}%",
        flush=True,
    )
    if hunt_res.get("last3m_100"):
        b = hunt_res["last3m_100"][0]
        print(f"BEST100: {b['bracket']} last3m {b['last3m']['n']}@100% cal {b['calibrate']['n']}@{b['calibrate']['hit_pct']}%", flush=True)
    if hunt_res.get("balanced"):
        b = hunt_res["balanced"][0]
        print(
            f"BALANCED: {b['bracket']} cal {b['calibrate']['n']}@{b['calibrate']['hit_pct']}% "
            f"l3m {b['last3m']['n']}@{b['last3m']['hit_pct']}%",
            flush=True,
        )
    print("DONE · last3m pattern integrate · research only", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
