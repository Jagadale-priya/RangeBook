"""NIFTY 2015 OOS — HELD proven logic (DI+hard34+VWAP · EMA34 trail · T1=12).

Window: 2015-01-01 → 2015-12-30
Downloads 1m via Kite if local cache missing.

  python -u prod_live/tests/builders/_diag_scalp_ma_hold100_nifty_2015.py
"""
from __future__ import annotations

import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
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
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import enrich_prior3  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers, enrich_ma_layers, summarize  # noqa: E402
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402

LEDGER = ROOT / "stock_signal_data" / "fno_validate" / "research"
CACHE_2015 = LEDGER / "_cache_nifty_1m_2015.parquet"
PACK = LEDGER / "nifty_1m_scalp_held_2015"
OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_HELD_2015_OOS.md"
REPORT_JSON = OUT / "NIFTY_1M_HELD_2015_OOS.json"

WIN_LO, WIN_HI = "2015-01-01", "2015-12-30"
T12, T15 = 12.0, 15.0
MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30


def in_session(e) -> bool:
    return MINS_LO <= int(e["mins"]) < MINS_HI


def load_or_download_2015() -> pd.DataFrame:
    if CACHE_2015.is_file():
        raw = base._norm(pd.read_parquet(CACHE_2015))
        print(f"  cache {CACHE_2015.name}: {len(raw)} bars {raw.index.min()}→{raw.index.max()}", flush=True)
        return raw

    print(f"Downloading NIFTY 1m {WIN_LO}→{WIN_HI} via Kite…", flush=True)
    fresh, note = base.download_1m_range(WIN_LO, WIN_HI)
    if note:
        print(f"  note: {note}", flush=True)
    if fresh is None or len(fresh) == 0:
        raise SystemExit(
            f"ERROR: no 2015 1m bars downloaded ({note}). "
            "Kite minute history often does not reach 2015 — need another source."
        )
    CACHE_2015.parent.mkdir(parents=True, exist_ok=True)
    fresh.to_parquet(CACHE_2015)
    print(f"  wrote {CACHE_2015} bars={len(fresh)}", flush=True)
    return fresh


def first_pass(xs, pred):
    for e in sorted(xs, key=lambda x: x["mins"]):
        if pred(e):
            return e
    return None


def score_t1(events, h, l, c, ema34, t1):
    for e in events:
        ok, reason, sl, t1v = path_ma_trail_strict(
            h, l, c, ema34, int(e["full_i"]), e["decision"], t1
        )
        e["_win"] = bool(ok)
        e["_reason"] = reason
        e["_sl"] = float(sl or 0)
        e["_t1"] = float(t1v)
        e["_pts"] = float(t1v) if ok else -abs(float(sl or 0))


def eval_book(events, days, pred):
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
    PACK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    print("NIFTY 2015 OOS · HELD proven logic", flush=True)

    raw = load_or_download_2015()
    raw = raw[(raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")) & (raw.index <= pd.Timestamp(WIN_HI, tz="Asia/Kolkata") + pd.Timedelta(days=1))]
    if raw.empty:
        raise SystemExit("ERROR: empty frame after date filter")
    print(f"window bars={len(raw)} {raw.index.min()}→{raw.index.max()}", flush=True)

    # warm-up: include Dec 2014 if present in cache, else first bars of 2015 only
    print("[1] textbook + MA + indicators…", flush=True)
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    vix = vixmod.load_vix()

    day_lo = str(raw.index.min().date())
    day_hi = str(raw.index.max().date())
    ev_cache = PACK / f"events_{day_lo}_{day_hi}.pkl"
    if ev_cache.exists():
        xs = pickle.load(ev_cache.open("rb"))
        print(f"[2] events cache n={len(xs)}", flush=True)
    else:
        print(f"[2] collect events {day_lo}→{day_hi}…", flush=True)
        xs = scalp.collect_scalp_events(df, day_lo, day_hi)
        pickle.dump(xs, ev_cache.open("wb"), protocol=pickle.HIGHEST_PROTOCOL)
        print(f"    n={len(xs)}", flush=True)

    print("[3] enrich…", flush=True)
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)
    enrich_ind(xs, df)

    days = sorted({e["day"] for e in xs})
    nd = len(days)
    print(f"days={nd} {days[0]}→{days[-1]}", flush=True)

    books = []
    for t1, name, pred in (
        (T12, "ORACLE T12", None),
        (T12, "HELD T12", held_gate),
        (T12, "HELD T12 session 09:30–14:30", lambda e: in_session(e) and held_gate(e)),
        (T15, "HELD T15", held_gate),
        (T15, "ORACLE T15", None),
    ):
        score_t1(xs, h, l, c, ema34, t1)
        if name.startswith("ORACLE"):

            def picker(rows):
                for e in sorted(rows, key=lambda x: x["mins"]):
                    if e["_win"]:
                        return e
                return None

            by = defaultdict(list)
            for e in xs:
                by[e["day"]].append(e)
            calls = []
            for d in days:
                e = picker(by[d])
                if e:
                    calls.append(e)
            st = summarize(calls, nd)
        else:
            st, calls = eval_book(xs, days, pred)
        pts = [float(e.get("_pts", 0)) for e in calls]
        avg_pts = round(float(np.mean(pts)), 2) if pts else 0.0
        tot_pts = round(float(np.sum(pts)), 2) if pts else 0.0
        print(f"  {name}: {st['n']}@{st['hit']}%/{st['cover']}% avg_pts={avg_pts} tot={tot_pts}", flush=True)
        books.append((name, st, calls, avg_pts, tot_pts, t1))

    # month breakdown for HELD T12
    held = next(b for b in books if b[0] == "HELD T12")
    by_m = defaultdict(list)
    for e in held[2]:
        by_m[e["day"][:7]].append(e)

    lines = [
        "# NIFTY 1m — HELD proven logic · **2015 OOS**",
        "",
        f"Window **`{day_lo}` → `{day_hi}`** · **{nd}** days",
        "",
        "## Logic (locked)",
        "",
        "- Entry: textbook candle + **DI_ok ∧ gate_hard34 ∧ vwap_with** · 1/day first",
        "- Exit: **EMA34 trail strict** · **T1=12** (also report T15)",
        "- This year is **far OOS** vs 2025–26 research window",
        "",
        "| Book | n | Hit% | Cover | Avg pts | Total pts | all_win |",
        "|---|---:|---:|---:|---:|---:|:---:|",
    ]
    for name, st, calls, avg_pts, tot_pts, t1 in books:
        lines.append(
            f"| `{name}` | {st['n']} | **{st['hit']}%** | {st['cover']}% | "
            f"{avg_pts} | {tot_pts} | {st['all_win']} |"
        )

    lines += [
        "",
        "## HELD T12 by month",
        "",
        "| Month | n | Hit% | W | L | Avg pts |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for m in sorted(by_m):
        xs_m = by_m[m]
        w = sum(1 for e in xs_m if e["_win"])
        pts = [float(e["_pts"]) for e in xs_m]
        lines.append(
            f"| {m} | {len(xs_m)} | {round(100*w/len(xs_m),2)}% | {w} | {len(xs_m)-w} | "
            f"{round(float(np.mean(pts)),2)} |"
        )

    lines += [
        "",
        "## HELD T12 trade sample (first/last 15)",
        "",
        "| Day | Entry | Side | Pattern | Reason | Pts |",
        "|---|---|---|---|---|---:|",
    ]
    sample = held[2][:15] + ([{"_sep": True}] if len(held[2]) > 30 else []) + held[2][-15:]
    for e in sample:
        if e.get("_sep"):
            lines.append("| … | … | … | … | … | … |")
            continue
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
            f"`{e['_reason']}` | {e['_pts']:+.1f} |"
        )

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    import json

    REPORT_JSON.write_text(
        json.dumps(
            {
                "window": [day_lo, day_hi],
                "days": nd,
                "books": {
                    name: {**st, "avg_pts": avg, "total_pts": tot}
                    for name, st, _, avg, tot, _ in books
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
