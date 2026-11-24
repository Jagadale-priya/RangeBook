"""Blind test HELD + MACD variants on last 6 months."""
from __future__ import annotations

import pickle
import sys
from collections import defaultdict
from pathlib import Path

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
from _diag_scalp_ma_lastyear_init import WIN_LO, PACK, add_ma_layers, enrich_ma_layers, summarize  # noqa: E402
from _diag_scalp_ma_hold100 import attach_exit_grid  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402
from _diag_scalp_ma_hold100_live_macd import macd_live_tags  # noqa: E402
from _diag_scalp_ma_hold100_picker import MODE, T1  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SCALP_MA_HOLD100_LAST6M.md"


def first_pass(xs, pred):
    for e in sorted(xs, key=lambda x: x["mins"]):
        if pred(e):
            return e
    return None


def oracle_day(xs):
    for e in sorted(xs, key=lambda x: x["mins"]):
        if e.get("_win"):
            return e
    return None


def eval_1day(events, days, pred):
    by = defaultdict(list)
    for e in events:
        by[e["day"]].append(e)
    calls = []
    for d in days:
        e = first_pass(by.get(d, []), pred)
        if e:
            calls.append(e)
    return summarize(calls, len(days)), calls


def main() -> int:
    print("HELD + MACD · last 6 months", flush=True)
    raw = base.load_existing_1m()
    # merge any newer downloaded bars if present in csv/cache already
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    data_hi = str(raw.index.max().date())
    hold_lo = str((pd.Timestamp(data_hi) - pd.DateOffset(months=6) + pd.Timedelta(days=1)).date())
    print(f"window {hold_lo} → {data_hi}", flush=True)

    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    atr = df["atr14"].astype(float).values
    emas = {n: df[f"ema{n}"].astype(float).values for n in (15, 21, 34, 50)}
    mh = df["macd_hist"].astype(float).values
    vix = vixmod.load_vix()

    cache = next(PACK.glob("events_2025-11-17_*.pkl"))
    # last 6m may start before this cache — also need earlier events from wf pack
    xs = pickle.load(cache.open("rb"))
    # if hold_lo before cache start, pull year events
    if hold_lo < "2025-11-17":
        PACK_WF = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_wf100_2021"
        extra = []
        for y in (2025, 2026):
            paths = list(PACK_WF.glob(f"events_{y}-01-01_*.pkl"))
            if not paths:
                continue
            extra.extend(pickle.load(paths[0].open("rb")))
        # prefer unique by day+mins+primary
        seen = {(e["day"], e["mins"], e.get("primary")) for e in xs}
        for e in extra:
            key = (e["day"], e["mins"], e.get("primary"))
            if key not in seen and hold_lo <= e["day"] <= data_hi:
                xs.append(e)
                seen.add(key)

    hold = [e for e in xs if hold_lo <= e["day"] <= data_hi]
    print(f"events in window={len(hold)}", flush=True)

    fwdmod.enrich_evt(hold, h, l, c, o)
    enrich_structure(hold, h, l, c, o, vix)
    enrich_prior3(hold, h, l, c, o)
    enrich_deep(hold, h, l, c, o, df)
    enrich_ma_layers(hold, df)
    enrich_ind(hold, df)
    for e in hold:
        i = int(e["full_i"])
        if 0 <= i < len(mh):
            e["macd_hist"] = round(float(mh[i]), 3)
    attach_exit_grid(hold, h, l, c, emas, atr, [MODE])
    for e in hold:
        sc = e["_exit"][(MODE, T1)]
        e["_win"] = sc["_win"]
        e["_sl"] = float(sc.get("_sl") or 0)
        e["_t1"] = float(sc.get("_t1") or T1)
        macd_live_tags(e)

    days = sorted({e["day"] for e in hold})
    nd = len(days)
    print(f"days={nd} {days[0]}→{days[-1]}", flush=True)

    # oracle
    by = defaultdict(list)
    for e in hold:
        by[e["day"]].append(e)
    or_calls = []
    for d in days:
        e = oracle_day(by[d])
        if e:
            or_calls.append(e)
    st_or = summarize(or_calls, nd)

    filters = [
        ("HELD DI+hard34+VWAP", held_gate),
        ("MACD_live", lambda e: e.get("macd_live")),
        ("MACD+DI", lambda e: e.get("macd_ind_a")),
        ("MACD+DI+VWAP", lambda e: e.get("macd_ind_b")),
        ("MACD+DI+VWAP+hard34", lambda e: e.get("macd_ind_c")),
        ("MACD+DI+hard34+BBmid", lambda e: e.get("macd_ind_d")),
        ("MACD+hard34+mom+close", lambda e: e.get("macd_ind_e")),
        ("MACD+DI+VWAP+hard34+close+!fail", lambda e: e.get("macd_ind_f")),
    ]

    lines = [
        "# MA HOLD100 — **last 6 months**",
        "",
        f"Window **`{hold_lo}` → `{data_hi}`** · **{nd}** days · exit EMA34 trail · T1=**{T1:.0f}** · 1/day first",
        "",
        "| Book | Calls | Hit% | Cover | all_win |",
        "|---|---:|---:|---:|:---:|",
        f"| **ORACLE** | {st_or['n']} | {st_or['hit']}% | {st_or['cover']}% | {st_or['all_win']} |",
    ]
    print(f"ORACLE {st_or}", flush=True)

    best = None
    best_calls = None
    results = []
    for name, pred in filters:
        st, calls = eval_1day(hold, days, pred)
        results.append((name, st, calls))
        print(f"  {name}: {st['n']}@{st['hit']}%/{st['cover']}%", flush=True)
        lines.append(
            f"| `{name}` | {st['n']} | {st['hit']}% | {st['cover']}% | {st['all_win']} |"
        )
        if best is None or (st["hit"], st["cover"]) > (best[1]["hit"], best[1]["cover"]):
            best = (name, st)
            best_calls = calls

    # month table for HELD and best
    def month_block(title, calls):
        rows = [f"### {title}", "", "| Month | n | Hit% | W | L |", "|---|---:|---:|---:|---:|"]
        by_m = defaultdict(list)
        for e in calls:
            by_m[e["day"][:7]].append(e)
        for m in sorted(by_m):
            xs = by_m[m]
            w = sum(1 for e in xs if e["_win"])
            rows.append(f"| {m} | {len(xs)} | {round(100*w/len(xs),2)}% | {w} | {len(xs)-w} |")
        rows.append("")
        return rows

    held_calls = next(c for n, s, c in results if n.startswith("HELD"))
    lines.append("")
    lines += month_block("HELD by month", held_calls)
    if best_calls is not None:
        lines += month_block(f"Best `{best[0]}` by month", best_calls)

    lines += [
        "",
        f"Best blind: `{best[0]}` → **{best[1]['hit']}%** hit · **{best[1]['cover']}%** cover",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"BEST {best[0]} {best[1]}", flush=True)
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
