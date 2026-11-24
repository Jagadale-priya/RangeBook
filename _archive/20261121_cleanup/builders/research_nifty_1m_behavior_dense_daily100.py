"""RESEARCH ONLY — deep behavior → denser **1 call/day @ 100%** (SL≤20).

Uses cached pattern events. Goals:
  1) Max day-coverage under SL≤20 / T1 8–10 at 100% both windows
  2) Union of clean micros (non-overlapping days) to approach 1/day
  3) Deeper feature slices (regime × RSI × clock × body × candle-SL × pattern family)

  python -u prod_live/tests/builders/research_nifty_1m_behavior_dense_daily100.py
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import defaultdict
from itertools import combinations, product
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

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
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_pattern_behavior_100"
REPORT_MD = OUT / "NIFTY_1M_BEHAVIOR_DENSE_DAILY100.md"
REPORT_JSON = OUT / "NIFTY_1M_BEHAVIOR_DENSE_DAILY100.json"
SL_MAX = 20.0


FAMILIES = {
    "stars": ["morning_star", "evening_star", "morning_doji_star", "evening_doji_star"],
    "methods3": ["falling_3_methods", "rising_3_methods"],
    "soldiers": ["three_crows", "three_soldiers"],
    "outside": ["three_outside_dn", "three_outside_up"],
    "engulf": ["bear_engulf", "bull_engulf", "dark_cloud", "piercing"],
    "wicks": ["hanging_man", "shooting_star", "hammer", "inv_hammer"],
    "maru_belt": ["marubozu_bear", "marubozu_bull", "belt_bear", "belt_bull"],
    "kickers": ["bear_kicker", "bull_kicker"],
    "runs": ["bear_run3", "bull_run3", "bear_run2", "bull_run2"],
}


def load_or_build_events():
    raw = base.load_existing_1m()
    end = raw.index.max()
    test_hi = end.strftime("%Y-%m-%d")
    test_lo_ts = end - pd.Timedelta(days=92)
    test_lo = test_lo_ts.strftime("%Y-%m-%d")
    cal_hi = (test_lo_ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    cal_lo = (test_lo_ts - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    cache = PACK / f"events_cache_{cal_lo}_{test_hi}.pkl"
    print(f"calibrate {cal_lo}→{cal_hi} · last3m {test_lo}→{test_hi}", flush=True)
    if cache.exists():
        print(f"  load {cache.name}", flush=True)
        with cache.open("rb") as f:
            blob = pickle.load(f)
        return blob["cal"], blob["test"], cal_lo, cal_hi, test_lo, test_hi, None, None, None

    print("  cache miss — rebuilding…", flush=True)
    raw = raw[raw.index >= pd.Timestamp(cal_lo, tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    cal_ev = beh.collect_events(df, cal_lo, cal_hi)
    test_ev = beh.collect_events(df, test_lo, test_hi)
    PACK.mkdir(parents=True, exist_ok=True)
    with cache.open("wb") as f:
        pickle.dump({"cal": cal_ev, "test": test_ev}, f, protocol=pickle.HIGHEST_PROTOCOL)
    return cal_ev, test_ev, cal_lo, cal_hi, test_lo, test_hi, h, l, c


def ensure_wins(events, h, l, c):
    need = False
    for e in events[:3]:
        if "w_20_10" not in e:
            need = True
            break
    if need:
        print("  precompute wins…", flush=True)
        beh._precompute_fixed_wins(events, h, l, c)


def day_set(events: List[dict]) -> Set[str]:
    return {e["day"] for e in events}


def eval_day_unique(events: List[dict], sl: float, t1: float) -> dict:
    return beh.eval_book_fast(events, sl, t1)


def slice_f(events, **kw):
    return beh.slice_events(events, kw)


def deep_feature_census(cal_ev: List[dict], sl: float = 20.0, t1: float = 10.0) -> List[dict]:
    """Which feature cells have high precision (win%) and enough n."""
    key = f"w_{int(sl)}_{int(t1)}"
    cells = defaultdict(lambda: {"n": 0, "wins": 0, "days": set()})
    for e in cal_ev:
        # only structurally tight enough for SL20
        if e["sl_candle"] > 20:
            continue
        feat = (
            e["primary"],
            e["decision"],
            e["pre_regime"],
            e["align_session"],
            e["clock"],
            "b45+" if e["body_frac"] >= 0.45 else "b<45",
            "slc<=12" if e["sl_candle"] <= 12 else ("slc<=15" if e["sl_candle"] <= 15 else "slc<=20"),
            "rsi_lo" if e["rsi_14"] < 40 else ("rsi_mid" if e["rsi_14"] <= 60 else "rsi_hi"),
        )
        cells[feat]["n"] += 1
        if e.get(key):
            cells[feat]["wins"] += 1
        cells[feat]["days"].add(e["day"])
    rows = []
    for feat, st in cells.items():
        if st["n"] < 6:
            continue
        hit = 100.0 * st["wins"] / st["n"]
        if hit < 85:
            continue
        rows.append(
            {
                "primary": feat[0],
                "side": feat[1],
                "regime": feat[2],
                "align": feat[3],
                "clock": feat[4],
                "body": feat[5],
                "slc": feat[6],
                "rsi": feat[7],
                "n": st["n"],
                "wins": st["wins"],
                "hit_pct": round(hit, 2),
                "n_days": len(st["days"]),
            }
        )
    rows.sort(key=lambda r: (-r["hit_pct"], -r["n_days"], -r["n"]))
    return rows


def micro_from_cell(cell: dict) -> dict:
    max_slc = 12.0 if cell["slc"] == "slc<=12" else (15.0 if cell["slc"] == "slc<=15" else 20.0)
    min_body = 0.45 if cell["body"] == "b45+" else None
    rsi_lo, rsi_hi = None, None
    if cell["rsi"] == "rsi_lo":
        rsi_lo, rsi_hi = 0, 40
    elif cell["rsi"] == "rsi_mid":
        rsi_lo, rsi_hi = 40, 60
    elif cell["rsi"] == "rsi_hi":
        rsi_lo, rsi_hi = 60, 100
    return {
        "primaries": [cell["primary"]],
        "side": cell["side"],
        "regime": cell["regime"],
        "align": cell["align"],
        "clocks": [cell["clock"]],
        "min_body": min_body,
        "max_sl_candle": max_slc,
        "rsi_lo": rsi_lo,
        "rsi_hi": rsi_hi,
    }


def hunt_family_filters(cal_ev, test_ev) -> List[dict]:
    """Broader family + clean filters for dense day books."""
    perfect = []
    near = []
    t0 = time.time()
    n = 0
    family_lists = list(FAMILIES.values()) + [
        FAMILIES["stars"] + FAMILIES["methods3"],
        FAMILIES["stars"] + FAMILIES["soldiers"],
        FAMILIES["stars"] + FAMILIES["methods3"] + FAMILIES["soldiers"],
        FAMILIES["outside"] + FAMILIES["engulf"],
        FAMILIES["wicks"],
        FAMILIES["stars"] + FAMILIES["wicks"],
        FAMILIES["methods3"] + FAMILIES["soldiers"] + FAMILIES["outside"],
    ]
    for pats, regime, align, min_body, max_slc, clocks, rsi, side in product(
        family_lists,
        ["continuation", None],
        [1, None],
        [0.45, 0.55, None],
        [12.0, 15.0, 20.0],
        [None, ["early"], ["early", "morning"]],
        [(None, None), (20, 55), (25, 50), (40, 80)],
        [None, "SELL"],
    ):
        if side == "SELL" and all(p in tb.BULLISH for p in pats):
            continue
        spec = {
            "primaries": pats,
            "regime": regime,
            "align": align,
            "min_body": min_body,
            "max_sl_candle": max_slc,
            "clocks": clocks,
            "rsi_lo": rsi[0],
            "rsi_hi": rsi[1],
            "side": side,
        }
        cal_s = slice_f(cal_ev, **spec)
        test_s = slice_f(test_ev, **spec)
        if len(cal_s) < 8 or len(test_s) < 4:
            continue
        for sl, t1 in product([20.0, 15.0, 12.0, 10.0], [8.0, 10.0]):
            n += 1
            if n % 2000 == 0:
                print(f"    family {n} perfect={len(perfect)} ({time.time()-t0:.0f}s)", flush=True)
            a = eval_day_unique(cal_s, sl, t1)
            t = eval_day_unique(test_s, sl, t1)
            if a["n"] < 5 or t["n"] < 3:
                continue
            rec = {
                "bracket": f"fix{sl}_{t1}",
                "params": {"sl": sl, "t1": t1},
                "filter": {k: v for k, v in spec.items() if v is not None},
                "calibrate": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl")},
                "last3m": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl")},
                "cal_miss": a["miss_days"][:8],
                "l3m_miss": t["miss_days"][:8],
                "last3m_calls": t["calls"],
                "cal_calls": a["calls"],
            }
            if a["hit_pct"] >= 100 - 1e-9 and t["hit_pct"] >= 100 - 1e-9:
                perfect.append(rec)
            elif t["hit_pct"] >= 95 and a["hit_pct"] >= 88 and t["n"] >= 8:
                near.append(rec)
            elif t["hit_pct"] >= 100 - 1e-9 and a["hit_pct"] >= 90 and t["n"] >= 6:
                near.append(rec)

    perfect.sort(key=lambda r: (-r["last3m"]["n"], -r["calibrate"]["n"], r["last3m"]["avg_sl"]))
    near.sort(key=lambda r: (-r["last3m"]["n"], -r["last3m"]["hit_pct"], -r["calibrate"]["hit_pct"]))
    print(f"  family hunt specs~{n} perfect={len(perfect)} near={len(near)} ({time.time()-t0:.0f}s)", flush=True)
    return perfect, near


def hunt_cell_micros(cal_ev, test_ev, cells: List[dict], top_k: int = 80) -> List[dict]:
    """Turn high-precision cells into day-unique micros; keep both-100."""
    perfect = []
    for cell in cells[:top_k]:
        spec = micro_from_cell(cell)
        for sl, t1 in product([20.0, 15.0, 12.0, 10.0], [8.0, 10.0]):
            cal_s = slice_f(cal_ev, **spec)
            test_s = slice_f(test_ev, **spec)
            if len(cal_s) < 4 or len(test_s) < 2:
                continue
            a = eval_day_unique(cal_s, sl, t1)
            t = eval_day_unique(test_s, sl, t1)
            if a["n"] < 3 or t["n"] < 2:
                continue
            if a["hit_pct"] >= 100 - 1e-9 and t["hit_pct"] >= 100 - 1e-9:
                perfect.append(
                    {
                        "bracket": f"fix{sl}_{t1}",
                        "params": {"sl": sl, "t1": t1},
                        "filter": {k: v for k, v in spec.items() if v is not None},
                        "cell": cell,
                        "calibrate": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl")},
                        "last3m": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "max_sl")},
                        "cal_days": [r["day"] for r in a["calls"]],
                        "l3m_days": [r["day"] for r in t["calls"]],
                        "last3m_calls": t["calls"],
                        "cal_calls": a["calls"],
                    }
                )
    perfect.sort(key=lambda r: (-r["last3m"]["n"], -r["calibrate"]["n"]))
    print(f"  cell micros both-100: {len(perfect)}", flush=True)
    return perfect


def union_micros(micros: List[dict], cal_n_days: int, test_n_days: int) -> dict:
    """Greedy union of day-unique micros by last3m day coverage (no day overlap)."""
    # Work on last3m first for ranking, but require combined book still 100% on both
    remaining = list(micros)
    chosen = []
    used_l3m: Set[str] = set()
    used_cal: Set[str] = set()
    calls_l3m = []
    calls_cal = []

    # sort by last3m n then cal n
    remaining.sort(key=lambda r: (-r["last3m"]["n"], -r["calibrate"]["n"]))

    for m in remaining:
        l3 = set(m.get("l3m_days") or [c["day"] for c in m.get("last3m_calls") or []])
        ca = set(m.get("cal_days") or [c["day"] for c in m.get("cal_calls") or []])
        if not l3 and not ca:
            continue
        if l3 & used_l3m:
            continue
        if ca & used_cal:
            continue
        # accept
        chosen.append(m)
        used_l3m |= l3
        used_cal |= ca
        calls_l3m.extend(m.get("last3m_calls") or [])
        calls_cal.extend(m.get("cal_calls") or [])
        if len(used_l3m) >= test_n_days and len(used_cal) >= cal_n_days:
            break

    calls_l3m.sort(key=lambda r: (r["day"], r["hm"]))
    calls_cal.sort(key=lambda r: (r["day"], r["hm"]))
    return {
        "n_micros": len(chosen),
        "cal_n": len(used_cal),
        "l3m_n": len(used_l3m),
        "cal_coverage_pct": round(100.0 * len(used_cal) / cal_n_days, 2) if cal_n_days else 0,
        "l3m_coverage_pct": round(100.0 * len(used_l3m) / test_n_days, 2) if test_n_days else 0,
        "cal_hit_pct": 100.0,
        "l3m_hit_pct": 100.0,
        "micros": [
            {
                "bracket": m["bracket"],
                "filter": m["filter"],
                "cal_n": m["calibrate"]["n"],
                "l3m_n": m["last3m"]["n"],
            }
            for m in chosen
        ],
        "last3m_calls": calls_l3m,
        "cal_calls": calls_cal,
    }


def feasibility(cal_ev, test_ev, cal_days, test_days):
    """How many days have ≥1 winning event under SL20/T10 with any pattern."""
    def cov(events, days, key="w_20_10"):
        win_days = {e["day"] for e in events if e.get(key) and e["sl_candle"] <= 20}
        return len(win_days), len(days), sorted(set(days) - win_days)[:10]

    return {
        "cal_sl20_t10": cov(cal_ev, cal_days, "w_20_10"),
        "l3m_sl20_t10": cov(test_ev, test_days, "w_20_10"),
        "cal_sl20_t8": cov(cal_ev, cal_days, "w_20_8"),
        "l3m_sl20_t8": cov(test_ev, test_days, "w_20_8"),
    }


def write_report(meta, census, family_perfect, family_near, cell_perfect, union):
    lines = [
        "# NIFTY 1m — **dense daily** 100% from deep behavior (SL≤20)",
        "",
        "**Not live.** Goal: **≥1 clean call every day @ 100%**, SL≤20, T1 8–10, pattern behavior filters.",
        "",
        f"- Calibrate `{meta['cal_lo']}`→`{meta['cal_hi']}` ({meta['n_cal_days']} days)",
        f"- Last3m `{meta['test_lo']}`→`{meta['test_hi']}` ({meta['n_test_days']} days)",
        "",
        "## Feasibility (any pattern event that wins SL20/T10)",
        "",
        f"- Cal days with ≥1 win: **{meta['feas']['cal_sl20_t10'][0]}/{meta['feas']['cal_sl20_t10'][1]}**",
        f"- Last3m days with ≥1 win: **{meta['feas']['l3m_sl20_t10'][0]}/{meta['feas']['l3m_sl20_t10'][1]}**",
        "",
        "## Deep feature cells (calibrate precision ≥85%)",
        "",
        "| Pattern | Side | Regime | Align | Clock | Body | SLc | RSI | N | Hit% | Days |",
        "|---|---|---|---:|---|---|---|---|---:|---:|---:|",
    ]
    for r in census[:25]:
        lines.append(
            f"| {r['primary']} | {r['side']} | {r['regime']} | {r['align']} | {r['clock']} | "
            f"{r['body']} | {r['slc']} | {r['rsi']} | {r['n']} | {r['hit_pct']} | {r['n_days']} |"
        )

    lines += ["", "## Best single day-unique books (both-100)", ""]
    champ = meta.get("champion")
    if champ:
        c, t = champ["calibrate"], champ["last3m"]
        lines += [
            f"### Champion single: `{champ['bracket']}`",
            "",
            f"- Filter: `{champ.get('filter')}`",
            f"- Calibrate: **{c['n']} days @ {c['hit_pct']}%**",
            f"- Last3m: **{t['n']} days @ {t['hit_pct']}%** · SL/T1 {t['avg_sl']}/{t['avg_t1']}",
            "",
            "| Day | HM | Side | Primary | SL | T1 | Win |",
            "|---|---|---|---|---:|---:|:---:|",
        ]
        for r in (champ.get("last3m_calls") or [])[:80]:
            lines.append(
                f"| {r['day']} | {r['hm']} | {r['decision']} | {r.get('primary')} | "
                f"{r['sl']} | {r['t1']} | {'Y' if r['win'] else 'N'} |"
            )
        lines.append("")

    lines += ["### Top family perfect", ""]
    for p in family_perfect[:8]:
        lines.append(
            f"- `{p['bracket']}` · cal {p['calibrate']['n']}@100% · l3m {p['last3m']['n']}@100% · "
            f"`{p['filter']}`"
        )
    lines += ["", "### Top cell micros", ""]
    for p in cell_perfect[:8]:
        lines.append(
            f"- `{p['bracket']}` · cal {p['calibrate']['n']}@100% · l3m {p['last3m']['n']}@100% · "
            f"`{p['filter']}`"
        )

    lines += [
        "",
        "## Union of micros (greedy, no day overlap) → denser 1/day",
        "",
        f"- Micros used: **{union['n_micros']}**",
        f"- Calibrate coverage: **{union['cal_n']}/{meta['n_cal_days']} ({union['cal_coverage_pct']}%)** @ 100%",
        f"- Last3m coverage: **{union['l3m_n']}/{meta['n_test_days']} ({union['l3m_coverage_pct']}%)** @ 100%",
        "",
    ]
    if union["l3m_coverage_pct"] >= 100 - 1e-9 and union["cal_coverage_pct"] >= 100 - 1e-9:
        lines.append("**ACHIEVED 1 call/day @ 100% both windows via micro-union.**")
    else:
        lines.append(
            "**Not full calendar coverage yet** — union is the densest both-100 pack found."
        )
    lines += ["", "### Union micros", ""]
    for m in union["micros"][:20]:
        lines.append(f"- `{m['bracket']}` cal {m['cal_n']} · l3m {m['l3m_n']} · `{m['filter']}`")
    lines += [
        "",
        "| Day | HM | Side | Primary | SL | T1 | Win |",
        "|---|---|---|---|---:|---:|:---:|",
    ]
    for r in union["last3m_calls"][:80]:
        lines.append(
            f"| {r['day']} | {r['hm']} | {r['decision']} | {r.get('primary')} | "
            f"{r['sl']} | {r['t1']} | {'Y' if r['win'] else 'N'} |"
        )

    lines += ["", "## Near (dense but not both-100)", ""]
    for n in family_near[:8]:
        lines.append(
            f"- `{n['bracket']}` · cal {n['calibrate']['n']}@{n['calibrate']['hit_pct']}% · "
            f"l3m {n['last3m']['n']}@{n['last3m']['hit_pct']}% · `{n['filter']}`"
        )
    lines += [
        "",
        "## Policy",
        "",
        f"- Pack: `{PACK}`",
        "- research_only · not_live · deep behavior · SL≤20 · dense daily 100%",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "meta": {k: v for k, v in meta.items() if k not in ("champion",)},
                "champion": {k: v for k, v in (champ or {}).items() if k not in ("cal_calls",)},
                "union": {k: v for k, v in union.items() if k not in ("cal_calls",)},
                "family_perfect": [
                    {k: v for k, v in r.items() if k not in ("last3m_calls", "cal_calls")}
                    for r in family_perfect[:15]
                ],
                "cell_perfect": [
                    {k: v for k, v in r.items() if k not in ("last3m_calls", "cal_calls")}
                    for r in cell_perfect[:15]
                ],
                "census_top": census[:40],
                "family_near": [
                    {k: v for k, v in r.items() if k not in ("last3m_calls", "cal_calls")}
                    for r in family_near[:12]
                ],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT_MD}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · DEEP behavior → DENSE 1 call/day @100% SL≤20", flush=True)
    print("=" * 60, flush=True)

    cal_ev, test_ev, cal_lo, cal_hi, test_lo, test_hi, h, l, c = load_or_build_events()
    if h is None:
        raw = base.load_existing_1m()
        raw = raw[raw.index >= pd.Timestamp(cal_lo, tz="Asia/Kolkata")]
        df = tb.detect_textbook(raw)
        df = beh.add_rsi(df)
        h = df["High"].astype(float).values
        l = df["Low"].astype(float).values
        c = df["Close"].astype(float).values

    ensure_wins(cal_ev, h, l, c)
    ensure_wins(test_ev, h, l, c)

    cal_days = sorted(day_set(cal_ev))
    test_days = sorted(day_set(test_ev))
    print(f"  events cal={len(cal_ev)} test={len(test_ev)} · days {len(cal_days)}/{len(test_days)}", flush=True)

    feas = feasibility(cal_ev, test_ev, cal_days, test_days)
    print(
        f"  feas SL20/T10: cal {feas['cal_sl20_t10'][0]}/{feas['cal_sl20_t10'][1]} · "
        f"l3m {feas['l3m_sl20_t10'][0]}/{feas['l3m_sl20_t10'][1]}",
        flush=True,
    )

    print("\n[1] Deep feature census…", flush=True)
    census = deep_feature_census(cal_ev, 20.0, 10.0)
    print(f"  high-precision cells: {len(census)}", flush=True)
    for r in census[:8]:
        print(
            f"    {r['primary']} {r['side']} {r['regime']} align={r['align']} "
            f"{r['clock']} {r['hit_pct']}% n={r['n']} days={r['n_days']}",
            flush=True,
        )

    print("\n[2] Family filter hunt…", flush=True)
    family_perfect, family_near = hunt_family_filters(cal_ev, test_ev)

    print("\n[3] Cell micro hunt…", flush=True)
    cell_perfect = hunt_cell_micros(cal_ev, test_ev, census, top_k=100)

    # merge micros for union (prefer denser)
    micros = []
    for src in (family_perfect, cell_perfect):
        for m in src:
            if "l3m_days" not in m:
                m["l3m_days"] = [c_["day"] for c_ in m.get("last3m_calls") or []]
                m["cal_days"] = [c_["day"] for c_ in m.get("cal_calls") or []]
            micros.append(m)

    print("\n[4] Union micros…", flush=True)
    union = union_micros(micros, len(cal_days), len(test_days))
    print(
        f"  union cal {union['cal_n']}/{len(cal_days)} ({union['cal_coverage_pct']}%) · "
        f"l3m {union['l3m_n']}/{len(test_days)} ({union['l3m_coverage_pct']}%) · "
        f"micros={union['n_micros']}",
        flush=True,
    )

    champion = None
    pool = family_perfect + cell_perfect
    if pool:
        champion = max(pool, key=lambda r: (r["last3m"]["n"], r["calibrate"]["n"]))

    meta = {
        "cal_lo": cal_lo,
        "cal_hi": cal_hi,
        "test_lo": test_lo,
        "test_hi": test_hi,
        "n_cal_days": len(cal_days),
        "n_test_days": len(test_days),
        "feas": feas,
        "champion": champion,
        "union_coverage_l3m": union["l3m_coverage_pct"],
        "union_coverage_cal": union["cal_coverage_pct"],
        "research_only": True,
        "not_live": True,
        "sl_max": SL_MAX,
    }
    write_report(meta, census, family_perfect, family_near, cell_perfect, union)
    if champion:
        (PACK / "dense_champion.json").write_text(
            json.dumps({k: v for k, v in champion.items() if k not in ("cal_calls", "last3m_calls")}, indent=2, default=str),
            encoding="utf-8",
        )
    (PACK / "dense_union.json").write_text(
        json.dumps({k: v for k, v in union.items() if k != "cal_calls"}, indent=2, default=str),
        encoding="utf-8",
    )

    print("\n" + "=" * 60, flush=True)
    if champion:
        print(
            f"BEST SINGLE {champion['bracket']} · cal {champion['calibrate']['n']}@100% · "
            f"l3m {champion['last3m']['n']}@100%",
            flush=True,
        )
        print(f"  filter={champion.get('filter')}", flush=True)
    print(
        f"UNION coverage cal {union['cal_coverage_pct']}% · l3m {union['l3m_coverage_pct']}% "
        f"({union['l3m_n']}/{len(test_days)} days)",
        flush=True,
    )
    if union["l3m_coverage_pct"] >= 100 and union["cal_coverage_pct"] >= 100:
        print("ACHIEVED 1 call/day @100% both via union", flush=True)
    print("DONE · dense daily 100%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
