"""SENSEX last 1y — same HELD T12 / T15 UNION / COMBINE stack as BN.

Priority 1/day COMBINED:
  1) TOP-20 train-proven T15 fingerprints → T1=15 EMA34 trail
  2) Else HELD (DI+hard34+VWAP) → T1=12 EMA34 trail

Train = before last 1y cut is N/A — for last 1y TEST we purify keys on
first half of available history before test window when possible;
if data is short, train = all bars before test_lo (last 1y start).

  python -u prod_live/tests/builders/_diag_scalp_ma_hold100_sensex_t15_t12_last1y.py
"""
from __future__ import annotations

import json
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
from _diag_scalp_ma_hold100 import keys_hold  # noqa: E402
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402

SX_CSV = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_1m_kite.csv"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "sensex_1m_scalp_t15_t12"
OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "SENSEX_1M_T15_T12_COMBINE_LAST1Y.md"
REPORT_JSON = OUT / "SENSEX_1M_T15_T12_COMBINE_LAST1Y.json"

T12, T15 = 12.0, 15.0
MIN_N, TOP_K = 3, 20
MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30


def load_sx_1m() -> pd.DataFrame:
    raw = base._norm(pd.read_csv(SX_CSV))
    print(f"  SENSEX 1m: {len(raw)} bars {raw.index.min()} → {raw.index.max()}", flush=True)
    return raw


def in_session(e) -> bool:
    return MINS_LO <= int(e["mins"]) < MINS_HI


def score_at(events, h, l, c, ema34, t1):
    for e in events:
        ok, reason, sl, t1v = path_ma_trail_strict(
            h, l, c, ema34, int(e["full_i"]), e["decision"], t1
        )
        e["_win"] = bool(ok)
        e["_reason"] = reason
        e["_sl"] = float(sl or 0)
        e["_t1"] = float(t1v)
        e["_keys"] = set(keys_hold(e))


def purify_keys(train, min_n=MIN_N):
    bucket = defaultdict(list)
    for e in train:
        for k in e["_keys"]:
            bucket[k].append(bool(e["_win"]))
    return {
        k
        for k, rows in bucket.items()
        if (not any(not ok for ok in rows)) and sum(rows) >= min_n
    }


def first_pass(xs, pred):
    for e in sorted(xs, key=lambda x: x["mins"]):
        if pred(e):
            return e
    return None


def eval_book(events, days, picker):
    by = defaultdict(list)
    for e in events:
        by[e["day"]].append(e)
    calls = []
    for d in days:
        e = picker(by.get(d, []))
        if e:
            calls.append(e)
    return summarize(calls, len(days)), calls


def main() -> int:
    PACK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    print("SENSEX · HELD T12 / T15 UNION / COMBINE · last 1y", flush=True)

    raw = load_sx_1m()
    data_hi = str(raw.index.max().date())
    data_lo = str(raw.index.min().date())
    test_lo = str((pd.Timestamp(data_hi) - pd.DateOffset(years=1) + pd.Timedelta(days=1)).date())
    test_lo = max(test_lo, data_lo)
    print(f"full {data_lo}→{data_hi} · TEST last1y {test_lo}→{data_hi}", flush=True)

    work = raw[raw.index >= pd.Timestamp(data_lo, tz="Asia/Kolkata")].copy()
    print("[1] textbook + MA + indicators…", flush=True)
    df = tb.detect_textbook(work)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    vix = vixmod.load_vix()

    ev_cache = PACK / f"events_{data_lo}_{data_hi}.pkl"
    if ev_cache.exists():
        xs = pickle.load(ev_cache.open("rb"))
        print(f"[2] events cache n={len(xs)}", flush=True)
    else:
        print(f"[2] collect events {data_lo}→{data_hi}…", flush=True)
        xs = scalp.collect_scalp_events(df, data_lo, data_hi)
        pickle.dump(xs, ev_cache.open("wb"), protocol=pickle.HIGHEST_PROTOCOL)
        print(f"    n={len(xs)}", flush=True)

    print("[3] enrich…", flush=True)
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)
    enrich_ind(xs, df)

    train = [e for e in xs if e["day"] < test_lo]
    test = [e for e in xs if e["day"] >= test_lo]
    tr_days = sorted({e["day"] for e in train})
    te_days = sorted({e["day"] for e in test})
    print(f"train days={len(tr_days)} test days={len(te_days)}", flush=True)
    if len(tr_days) < 20:
        print("WARNING: short train before last-1y — T15 keys may be weak; HELD still valid", flush=True)

    # T15 purify on train
    score_at(xs, h, l, c, ema34, T15)
    train = [e for e in xs if e["day"] < test_lo]
    test = [e for e in xs if e["day"] >= test_lo]
    allow_raw = purify_keys(train, MIN_N) if train else set()
    print(f"T15 raw clean keys={len(allow_raw)}", flush=True)

    by_tr = defaultdict(list)
    for e in train:
        by_tr[e["day"]].append(e)
    scored_keys = []
    for k in allow_raw:
        calls_k = []
        for d in tr_days:
            hit = None
            for e in sorted(by_tr.get(d, []), key=lambda x: x["mins"]):
                if k in e["_keys"]:
                    hit = e
                    break
            if hit:
                calls_k.append(hit)
        if len(calls_k) >= MIN_N and all(e["_win"] for e in calls_k):
            scored_keys.append((len(calls_k), k))
    scored_keys.sort(key=lambda x: -x[0])
    keys15 = {k for _, k in scored_keys[:TOP_K]}
    print(f"T15 single-key PROVEN={len(scored_keys)} · TOP_{TOP_K}={len(keys15)}", flush=True)

    def pick_t15(rows, ks=keys15):
        for e in sorted(rows, key=lambda x: x["mins"]):
            if e["_keys"] & ks:
                return e
        return None

    def pick_held(rows):
        return first_pass(rows, held_gate)

    def pick_held_sess(rows):
        return first_pass(rows, lambda e: in_session(e) and held_gate(e))

    def pick_oracle(rows):
        for e in sorted(rows, key=lambda x: x["mins"]):
            if e["_win"]:
                return e
        return None

    st15_tr, _ = eval_book(train, tr_days, pick_t15) if tr_days else ({"n": 0, "hit": 0, "cover": 0, "all_win": True}, [])
    st15_te, _ = eval_book(test, te_days, pick_t15)
    st15_h_te, _ = eval_book(test, te_days, pick_held)
    st15_or_te, _ = eval_book(test, te_days, pick_oracle)
    print(f"UNION T15 train {st15_tr} test {st15_te['n']}@{st15_te['hit']}%/{st15_te['cover']}%", flush=True)
    print(f"HELD  T15 test {st15_h_te['n']}@{st15_h_te['hit']}%/{st15_h_te['cover']}%", flush=True)

    # T12
    score_at(xs, h, l, c, ema34, T12)
    train = [e for e in xs if e["day"] < test_lo]
    test = [e for e in xs if e["day"] >= test_lo]
    for e in xs:
        e["_keys"] = set(keys_hold(e))

    st12_h_tr, _ = eval_book(train, tr_days, pick_held) if tr_days else ({"n": 0, "hit": 0, "cover": 0}, [])
    st12_h_te, _ = eval_book(test, te_days, pick_held)
    st12_hs_te, _ = eval_book(test, te_days, pick_held_sess)
    st12_or_te, _ = eval_book(test, te_days, pick_oracle)
    print(f"HELD  T12 train {st12_h_tr.get('n',0)}@{st12_h_tr.get('hit',0)}% test {st12_h_te['n']}@{st12_h_te['hit']}%/{st12_h_te['cover']}%", flush=True)

    # dual scores for combine
    for e in xs:
        i = int(e["full_i"])
        ok15, r15, sl15, _ = path_ma_trail_strict(h, l, c, ema34, i, e["decision"], T15)
        ok12, r12, sl12, _ = path_ma_trail_strict(h, l, c, ema34, i, e["decision"], T12)
        e["_ok15"], e["_ok12"] = bool(ok15), bool(ok12)
        e["_r15"], e["_r12"] = r15, r12
        e["_pts15"] = float(T15) if ok15 else -abs(float(sl15 or 0))
        e["_pts12"] = float(T12) if ok12 else -abs(float(sl12 or 0))
        e["_keys"] = set(keys_hold(e))

    by = defaultdict(list)
    for e in test:
        by[e["day"]].append(e)

    combined = []
    for d in te_days:
        rows = by.get(d, [])
        e15 = pick_t15(rows)
        if e15 is not None:
            combined.append(
                {
                    **e15,
                    "_win": e15["_ok15"],
                    "_t1": T15,
                    "_pts": e15["_pts15"],
                    "_reason": e15["_r15"],
                    "_book": "T15_UNION",
                    "_sl": abs(e15["_pts15"]) if not e15["_ok15"] else 0,
                }
            )
            continue
        e12 = pick_held(rows)
        if e12 is not None:
            combined.append(
                {
                    **e12,
                    "_win": e12["_ok12"],
                    "_t1": T12,
                    "_pts": e12["_pts12"],
                    "_reason": e12["_r12"],
                    "_book": "T12_HELD",
                    "_sl": abs(e12["_pts12"]) if not e12["_ok12"] else 0,
                }
            )

    st_comb = summarize(combined, len(te_days))
    pts = [float(e["_pts"]) for e in combined]
    avg_pts = round(float(np.mean(pts)), 2) if pts else 0.0
    tot_pts = round(float(np.sum(pts)), 2) if pts else 0.0
    n15 = sum(1 for e in combined if e["_book"] == "T15_UNION")
    n12 = sum(1 for e in combined if e["_book"] == "T12_HELD")
    w15 = sum(1 for e in combined if e["_book"] == "T15_UNION" and e["_win"])
    w12 = sum(1 for e in combined if e["_book"] == "T12_HELD" and e["_win"])
    print(
        f"COMBINED {st_comb['n']}@{st_comb['hit']}%/{st_comb['cover']}% avg={avg_pts} tot={tot_pts} T15={n15}({w15}W) T12={n12}({w12}W)",
        flush=True,
    )

    # session combined
    combined_sess = []
    for d in te_days:
        rows = [e for e in by.get(d, []) if in_session(e)]
        e15 = pick_t15(rows)
        if e15 is not None:
            combined_sess.append(
                {
                    **e15,
                    "_win": e15["_ok15"],
                    "_t1": T15,
                    "_pts": e15["_pts15"],
                    "_reason": e15["_r15"],
                    "_book": "T15_UNION",
                    "_sl": abs(e15["_pts15"]) if not e15["_ok15"] else 0,
                }
            )
            continue
        e12 = pick_held(rows)
        if e12 is not None:
            combined_sess.append(
                {
                    **e12,
                    "_win": e12["_ok12"],
                    "_t1": T12,
                    "_pts": e12["_pts12"],
                    "_reason": e12["_r12"],
                    "_book": "T12_HELD",
                    "_sl": abs(e12["_pts12"]) if not e12["_ok12"] else 0,
                }
            )
    st_cs = summarize(combined_sess, len(te_days))
    pts_s = [float(e["_pts"]) for e in combined_sess]
    avg_s = round(float(np.mean(pts_s)), 2) if pts_s else 0.0
    tot_s = round(float(np.sum(pts_s)), 2) if pts_s else 0.0

    # UNION ledger with ok15
    c15_ledger = []
    for d in te_days:
        e = pick_t15(by.get(d, []))
        if e:
            c15_ledger.append(
                {
                    **e,
                    "_win": e["_ok15"],
                    "_t1": T15,
                    "_pts": e["_pts15"],
                    "_reason": e["_r15"],
                    "_sl": abs(e["_pts15"]) if not e["_ok15"] else 0,
                }
            )
    st15_te2 = summarize(c15_ledger, len(te_days))

    lines = [
        "# SENSEX 1m — T15 UNION + T12 HELD · last 1 year",
        "",
        f"Data `{data_lo}`→`{data_hi}` · **TEST** `{test_lo}`→`{data_hi}` (**{len(te_days)}** days)",
        f"Train (T15 key purify) days=**{len(tr_days)}** · TOP-{TOP_K} keys=**{len(keys15)}**",
        "",
        "## Logic (same as BN stack)",
        "",
        "1. TOP-20 Sensex-train-proven fingerprint → **T1=15** EMA34 trail",
        "2. Else **HELD** DI+hard34+VWAP → **T1=12** EMA34 trail",
        "3. 1 call/day first match",
        "",
        "## Test results (last 1y)",
        "",
        "| Book | n | Hit% | Cover | Notes |",
        "|---|---:|---:|---:|---|",
        f"| ORACLE T12 | {st12_or_te['n']} | {st12_or_te['hit']}% | {st12_or_te['cover']}% | ceiling |",
        f"| ORACLE T15 | {st15_or_te['n']} | {st15_or_te['hit']}% | {st15_or_te['cover']}% | ceiling |",
        f"| **HELD T12** | {st12_h_te['n']} | **{st12_h_te['hit']}%** | {st12_h_te['cover']}% | blind primary |",
        f"| HELD T12 session 09:30–14:30 | {st12_hs_te['n']} | {st12_hs_te['hit']}% | {st12_hs_te['cover']}% | |",
        f"| HELD T15 | {st15_h_te['n']} | {st15_h_te['hit']}% | {st15_h_te['cover']}% | |",
        f"| UNION T15 (TOP-{TOP_K}) | {st15_te2['n']} | {st15_te2['hit']}% | {st15_te2['cover']}% | train {st15_tr.get('n',0)}@{st15_tr.get('hit',0)}% |",
        f"| **COMBINED T15→T12** | **{st_comb['n']}** | **{st_comb['hit']}%** | **{st_comb['cover']}%** | avg **{avg_pts}** · tot **{tot_pts}** · T15:{n15}({w15}W) T12:{n12}({w12}W) |",
        f"| COMBINED + session | {st_cs['n']} | {st_cs['hit']}% | {st_cs['cover']}% | avg {avg_s} · tot {tot_s} |",
        "",
        "## Combined ledger (last 1y)",
        "",
        "| Day | Book | Entry | Side | Pattern | T1 | Reason | Pts | Result |",
        "|---|---|---|---|---|---:|---|---:|---|",
    ]
    for e in combined:
        lines.append(
            f"| {e['day']} | `{e['_book']}` | {e['hm']} | {e['decision']} | {e['primary']} | "
            f"{e['_t1']:.0f} | `{e['_reason']}` | {e['_pts']:+.1f} | "
            f"{'WIN' if e['_win'] else 'LOSS'} |"
        )
    lines += [
        "",
        "## Verdict",
        "",
        "- Prefer the book with highest test hit among HELD T12 vs COMBINED.",
        "- Same pattern as BN if COMBINED < HELD T12 → do not upgrade with T15 UNION.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    blob = {
        "test_lo": test_lo,
        "data_hi": data_hi,
        "n_keys15": len(keys15),
        "train_days": len(tr_days),
        "test_days": len(te_days),
        "held_t12": st12_h_te,
        "held_t15": st15_h_te,
        "union_t15": st15_te2,
        "combined": {**st_comb, "avg_pts": avg_pts, "total_pts": tot_pts, "n15": n15, "n12": n12},
        "combined_sess": {**st_cs, "avg_pts": avg_s, "total_pts": tot_s},
    }
    REPORT_JSON.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
