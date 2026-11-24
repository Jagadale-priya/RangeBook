"""Hold finalized MA+indicator logic; blind test on LARGE OOS window.

HELD LOGIC (locked):
  1. Entry: textbook 1m candle
  2. Gate: DI align + EMA34 hard stack/slope/align + VWAP with side
  3. Hold/exit: EMA34 trail — T1=12 before close flips vs EMA34
  4. 1 call/day: first gated match

Protocol:
  Train: 2021-01-01 → 2024-12-31  (build confirmation only; gate is rule-based)
  Test : 2025-01-01 → data end     (LARGE unknown ~2y)
  Also report yearly + last-3m slices inside test.
"""
from __future__ import annotations

import pickle
import sys
import time
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
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import enrich_prior3  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers, enrich_ma_layers, summarize  # noqa: E402
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK_WF = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_wf100_2021"
PACK_OUT = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_ma_hold100"
LEDGER = ROOT / "stock_signal_data" / "fno_validate" / "research"
CACHE_2020 = LEDGER / "_cache_nifty_1m_2020.parquet"
REPORT = OUT / "NIFTY_1M_SCALP_MA_HOLD100_LARGE_TEST.md"

TRAIN_LO, TRAIN_HI = "2021-01-01", "2024-12-31"
TEST_LO = "2025-01-01"
T1 = 12.0
MODE = "trail34"


def held_gate(e) -> bool:
    """Locked entry filter: DI + EMA34 hard + VWAP with."""
    return bool(e.get("di_ok") and e.get("gate_hard34") and e.get("vwap_with"))


def load_all_bars():
    frames = []
    if CACHE_2020.is_file():
        frames.append(base._norm(pd.read_parquet(CACHE_2020)))
        print(f"  2020 cache: {len(frames[-1])}", flush=True)
    main = base.load_existing_1m()
    frames.append(main)
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def ensure_year_events(df, years, data_hi):
    PACK_WF.mkdir(parents=True, exist_ok=True)
    out = {}
    for y in years:
        lo, hi = f"{y}-01-01", f"{y}-12-31"
        if y == int(data_hi[:4]):
            hi = min(hi, data_hi)
        cache = PACK_WF / f"events_{lo}_{hi}.pkl"
        if cache.exists():
            xs = pickle.load(cache.open("rb"))
            print(f"  events {y}: cache {len(xs)}", flush=True)
        else:
            print(f"  collect events {y} {lo}→{hi}…", flush=True)
            xs = scalp.collect_scalp_events(df, lo, hi)
            pickle.dump(xs, cache.open("wb"), protocol=pickle.HIGHEST_PROTOCOL)
            print(f"    n={len(xs)}", flush=True)
        for e in xs:
            e["_year"] = y
        out[y] = xs
    return out


def score_exit(events, h, l, c, ema34):
    for e in events:
        ok, reason, sl, t1 = path_ma_trail_strict(
            h, l, c, ema34, int(e["full_i"]), e["decision"], T1
        )
        e["_win"] = bool(ok)
        e["_reason"] = reason
        e["_sl"] = float(sl or 0)
        e["_t1"] = float(t1)


def one_per_day_gate(events, gate):
    by = defaultdict(list)
    for e in events:
        if gate(e):
            by[e["day"]].append(e)
    calls = []
    for d, xs in sorted(by.items()):
        e = sorted(xs, key=lambda x: x["mins"])[0]
        calls.append(e)
    return calls


def oracle_one_per_day(events):
    by = defaultdict(list)
    for e in events:
        by[e["day"]].append(e)
    calls = []
    for d, xs in sorted(by.items()):
        hit = None
        for e in sorted(xs, key=lambda x: x["mins"]):
            if e.get("_win"):
                hit = e
                break
        if hit:
            calls.append(hit)
    return calls


def slice_stats(calls, days):
    return summarize(calls, len(days))


def main() -> int:
    t0 = time.time()
    PACK_OUT.mkdir(parents=True, exist_ok=True)
    print("=" * 60, flush=True)
    print("MA HOLD100 LARGE TEST · locked DI+hard34+VWAP · trail34 t12", flush=True)
    print("=" * 60, flush=True)

    raw = load_all_bars()
    data_hi = str(raw.index.max().date())
    # need bars from 2021 for train+test (2020 optional for future)
    raw = raw[raw.index >= pd.Timestamp("2021-01-01", tz="Asia/Kolkata")]
    print(f"bars={len(raw)} {raw.index.min()} → {raw.index.max()}", flush=True)

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

    years = list(range(2021, int(data_hi[:4]) + 1))
    print("[2] events…", flush=True)
    by_year = ensure_year_events(df, years, data_hi)

    print("[3] enrich + score exit…", flush=True)
    all_ev = []
    for y, xs in by_year.items():
        fwdmod.enrich_evt(xs, h, l, c, o)
        enrich_structure(xs, h, l, c, o, vix)
        enrich_prior3(xs, h, l, c, o)
        enrich_deep(xs, h, l, c, o, df)
        enrich_ma_layers(xs, df)
        enrich_ind(xs, df)
        score_exit(xs, h, l, c, ema34)
        print(f"  enriched {y}={len(xs)}", flush=True)
        all_ev.extend(xs)

    train = [e for e in all_ev if TRAIN_LO <= e["day"] <= TRAIN_HI]
    test = [e for e in all_ev if e["day"] >= TEST_LO]
    train_days = sorted({e["day"] for e in train})
    test_days = sorted({e["day"] for e in test})
    print(f"train {len(train_days)}d · test {len(test_days)}d ({test_days[0]}→{test_days[-1]})", flush=True)

    # evaluate
    tr_calls = one_per_day_gate(train, held_gate)
    te_calls = one_per_day_gate(test, held_gate)
    tr_or = oracle_one_per_day(train)
    te_or = oracle_one_per_day(test)
    st_tr = slice_stats(tr_calls, train_days)
    st_te = slice_stats(te_calls, test_days)
    st_tr_or = slice_stats(tr_or, train_days)
    st_te_or = slice_stats(te_or, test_days)

    print(f"HELD train={st_tr}", flush=True)
    print(f"HELD test ={st_te}", flush=True)
    print(f"ORACLE test={st_te_or}", flush=True)

    lines = [
        "# MA HOLD100 — **LARGE blind test**",
        "",
        "## Locked logic",
        "1. **Entry:** textbook 1m candle pattern (bull→BUY / bear→SELL)",
        "2. **Gate:** `DI_ok` + `gate_hard34` (EMA34 align+stack+slope) + `VWAP_with`",
        "3. **Hold/exit:** stay while close on right side of **EMA34**; win if **T1=12** before MA flip",
        "4. **Pace:** 1 call/day (first gated match)",
        "",
        f"Train `{TRAIN_LO}`→`{TRAIN_HI}` (**{len(train_days)}** days) · "
        f"Test `{TEST_LO}`→`{data_hi}` (**{len(test_days)}** days) — LARGE OOS",
        "",
        "| Book | Window | Calls | Hit% | Cover | all_win |",
        "|---|---|---:|---:|---:|:---:|",
        f"| ORACLE | train | {st_tr_or['n']} | {st_tr_or['hit']}% | {st_tr_or['cover']}% | {st_tr_or['all_win']} |",
        f"| **HELD** | train | {st_tr['n']} | {st_tr['hit']}% | {st_tr['cover']}% | {st_tr['all_win']} |",
        f"| ORACLE | **TEST large** | {st_te_or['n']} | {st_te_or['hit']}% | {st_te_or['cover']}% | {st_te_or['all_win']} |",
        f"| **HELD** | **TEST large** | {st_te['n']} | {st_te['hit']}% | {st_te['cover']}% | {st_te['all_win']} |",
        "",
        "## Test by year",
        "",
        "| Year | HELD n@hit cover | ORACLE n@hit cover |",
        "|---|---|---|",
    ]

    for y in sorted({int(d[:4]) for d in test_days}):
        days_y = [d for d in test_days if d.startswith(str(y))]
        te_y = [e for e in test if e["day"] in set(days_y)]
        c_h = one_per_day_gate(te_y, held_gate)
        c_o = oracle_one_per_day(te_y)
        sh, so = slice_stats(c_h, days_y), slice_stats(c_o, days_y)
        print(f"  year {y}: held {sh['n']}@{sh['hit']}%/{sh['cover']}% oracle {so['hit']}%/{so['cover']}%", flush=True)
        lines.append(
            f"| {y} | {sh['n']}@{sh['hit']}% {sh['cover']}% | {so['n']}@{so['hit']}% {so['cover']}% |"
        )

    # month rollup on test
    lines += ["", "## Test by month", "", "| Month | n | Hit% | W | L | Days |", "|---|---:|---:|---:|---:|---:|"]
    by_m = defaultdict(list)
    for e in te_calls:
        by_m[e["day"][:7]].append(e)
    for m in sorted(by_m):
        xs = by_m[m]
        w = sum(1 for e in xs if e["_win"])
        md = len([d for d in test_days if d.startswith(m)])
        hit = round(100.0 * w / len(xs), 2)
        lines.append(f"| {m} | {len(xs)} | {hit}% | {w} | {len(xs)-w} | {len({e['day'] for e in xs})}/{md} |")

    # last 3m inside test
    last3_lo = str((pd.Timestamp(data_hi) - pd.DateOffset(months=3) + pd.Timedelta(days=1)).date())
    te_l3 = [e for e in test if e["day"] >= last3_lo]
    d_l3 = sorted({e["day"] for e in te_l3})
    c_l3 = one_per_day_gate(te_l3, held_gate)
    o_l3 = oracle_one_per_day(te_l3)
    st_l3, st_l3o = slice_stats(c_l3, d_l3), slice_stats(o_l3, d_l3)
    lines += [
        "",
        f"## Last-3m slice inside test (`{last3_lo}`→`{data_hi}`)",
        "",
        f"- HELD: **{st_l3['hit']}%** hit · **{st_l3['cover']}%** cover · n={st_l3['n']}",
        f"- ORACLE: **{st_l3o['hit']}%** hit · **{st_l3o['cover']}%** cover · n={st_l3o['n']}",
        "",
    ]

    # sample losses on large test (first 40)
    loss = [e for e in te_calls if not e["_win"]]
    lines += [
        f"## Test losses sample ({len(loss)} total, show 40)",
        "",
        "| Day | HM | Side | Pattern | MFE | reason |",
        "|---|---|---|---|---:|---|",
    ]
    for e in sorted(loss, key=lambda x: (x["day"], x["mins"]))[:40]:
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
            f"{e.get('mfe',0):.1f} | {e.get('_reason')} |"
        )

    lines += [
        "",
        f"Elapsed: {time.time()-t0:.1f}s",
        f"Pack: `{PACK_OUT}`",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    (PACK_OUT / "HELD_LOGIC_LARGE_TEST.pkl").write_bytes(
        pickle.dumps(
            {
                "logic": {
                    "gate": "di_ok && gate_hard34 && vwap_with",
                    "exit": "ema34_trail",
                    "t1": T1,
                    "pace": "1/day first",
                },
                "train": st_tr,
                "test": st_te,
                "oracle_test": st_te_or,
                "last3m": st_l3,
                "test_lo": TEST_LO,
                "data_hi": data_hi,
            },
            protocol=pickle.HIGHEST_PROTOCOL,
        )
    )
    print(f"Wrote {REPORT}", flush=True)
    print(f"SUMMARY held test {st_te['hit']}%/{st_te['cover']}% oracle {st_te_or['hit']}%/{st_te_or['cover']}%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
