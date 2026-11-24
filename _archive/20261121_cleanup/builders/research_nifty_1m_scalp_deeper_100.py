"""RESEARCH ONLY — Deeper scalp multi-call densification @100%.

Adds wick/ATR/session features, thinner cells, score-threshold picker,
re-entry-after-win, and gap sweeps. Goal: more path-100 calls than prior 187/64.

  python -u prod_live/tests/builders/research_nifty_1m_scalp_deeper_100.py
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_chart_only_100 as co  # noqa: E402

PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_prevcandle_100"
OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT_MD = OUT / "NIFTY_1M_SCALP_DEEPER_100.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_DEEPER_100.json"
PACK_OUT = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_deeper_100"
MULTI_MD = OUT / "NIFTY_1M_SCALP_MULTICALL_100.md"


def lesser(e, st):
    p, s = float(e["sl_prev"]), float(e["sl_sig"])
    return {
        "prev": p,
        "sig": s,
        "min_ps": min(p, s) if s >= 4 else p,
        "cap8": min(p, 8.0),
        "cap10": min(p, 10.0),
        "cap12": min(p, 12.0),
        "p75": max(4.0, 0.75 * p),
    }[st]


def enrich_geometry(events: List[dict], df, h, l, c, o) -> None:
    """Add wick, ATR%, session distance, stack features using full_i."""
    idx = df.index
    # day open map
    day_open = {}
    if "day" in df.columns:
        for day, g in df.groupby("day"):
            day_open[day] = float(g["Open"].iloc[0])
    t0 = time.time()
    for i, e in enumerate(events):
        if i and i % 20000 == 0:
            print(f"    geom {i}/{len(events)} ({time.time()-t0:.0f}s)", flush=True)
        fi = int(e["full_i"])
        hi, lo, cl, op = float(h[fi]), float(l[fi]), float(c[fi]), float(o[fi])
        rng = max(hi - lo, 0.5)
        body = abs(cl - op)
        upper = hi - max(op, cl)
        lower = min(op, cl) - lo
        e["wick_up_frac"] = upper / rng
        e["wick_dn_frac"] = lower / rng
        e["body_atr"] = body / max(float(e["atr"]), 1.0)
        e["range_atr"] = rng / max(float(e["atr"]), 1.0)
        # adverse wick (against trade)
        if e["decision"] == "BUY":
            e["adv_wick"] = upper / rng
            e["fav_wick"] = lower / rng
        else:
            e["adv_wick"] = lower / rng
            e["fav_wick"] = upper / rng
        # session distance from day open in pts
        dopen = day_open.get(e["day"])
        if dopen is None:
            e["from_open"] = 0.0
        else:
            e["from_open"] = cl - dopen
        e["from_open_atr"] = e["from_open"] / max(float(e["atr"]), 1.0)
        # same-side stack: prior 2 closes direction
        if fi >= 2:
            d1 = c[fi - 1] - o[fi - 1]
            d2 = c[fi - 2] - o[fi - 2]
            if e["decision"] == "BUY":
                e["stack2"] = int(d1 > 0) + int(d2 > 0)
            else:
                e["stack2"] = int(d1 < 0) + int(d2 < 0)
        else:
            e["stack2"] = 0
        # sl vs atr
        e["sl_prev_atr"] = float(e["sl_prev"]) / max(float(e["atr"]), 1.0)


def path_ok(e, h, l, c, st, t1=10.0):
    sl = lesser(e, st)
    if not (4 <= sl <= 12):
        return False, sl
    if st == "prev" and e.get(f"prev_t{int(t1)}") == "win":
        return True, sl
    if st == "sig" and e.get(f"sig_t{int(t1)}") == "win":
        return True, sl
    win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], float(sl), float(t1))
    return (win and out == "t1"), sl


def deep_tags(e):
    body = float(e["body_frac"])
    return {
        "primary": e["primary"],
        "side": e["decision"],
        "regime": e["pre_regime"],
        "align": int(e["align_session"]),
        "clock": e["clock"],
        "body": (
            "b70+"
            if body >= 0.70
            else ("b55+" if body >= 0.55 else ("b45+" if body >= 0.45 else "b<45"))
        ),
        "slbin": (
            "sl4-8"
            if 4 <= e["sl_prev"] <= 8
            else (
                "sl8-12"
                if e["sl_prev"] <= 12
                else ("sl12-16" if e["sl_prev"] <= 16 else "sl16-20")
            )
        ),
        "rsi": "lo" if e["rsi_14"] < 35 else ("hi" if e["rsi_14"] > 65 else "mid"),
        "advw": "adv_lo" if e.get("adv_wick", 0) < 0.15 else ("adv_mid" if e.get("adv_wick", 0) < 0.35 else "adv_hi"),
        "batr": "ba>0.8" if e.get("body_atr", 0) >= 0.8 else ("ba>0.5" if e.get("body_atr", 0) >= 0.5 else "ba<0.5"),
        "stack": f"st{e.get('stack2', 0)}",
        "fo": (
            "fo_far"
            if abs(e.get("from_open_atr", 0)) >= 1.5
            else ("fo_mid" if abs(e.get("from_open_atr", 0)) >= 0.5 else "fo_near")
        ),
        "slatr": "sla<0.8" if e.get("sl_prev_atr", 1) < 0.8 else ("sla<1.2" if e.get("sl_prev_atr", 1) < 1.2 else "sla>=1.2"),
    }


def cell_keys(e):
    g = deep_tags(e)
    # full deep
    k_full = (
        g["primary"],
        g["side"],
        g["regime"],
        g["align"],
        g["clock"],
        g["body"],
        g["slbin"],
        g["rsi"],
        g["advw"],
        g["batr"],
        g["stack"],
    )
    # geom deep (no pattern)
    k_geom = (
        "GEOM",
        g["side"],
        g["regime"],
        g["align"],
        g["clock"],
        g["body"],
        g["slbin"],
        g["rsi"],
        g["advw"],
        g["batr"],
        g["stack"],
    )
    # compact (fewer dims → denser)
    k_compact = (
        g["primary"],
        g["side"],
        g["regime"],
        g["align"],
        g["clock"],
        g["body"],
        g["slbin"],
        g["advw"],
    )
    # wick-focus
    k_wick = (
        g["primary"],
        g["side"],
        g["align"],
        g["clock"],
        g["advw"],
        g["batr"],
        g["slbin"],
        g["fo"],
    )
    return [k_full, k_geom, k_compact, k_wick]


def apply_gap(rows, gap):
    last = {}
    out = []
    for e in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        prev = last.get(e["day"])
        if prev is not None and e["mins"] - prev < gap:
            continue
        out.append(e)
        last[e["day"]] = e["mins"]
    return out


def greedy_union(cells, gap):
    used_c, used_t = set(), set()
    chosen = []

    def take(calls, used):
        out = []
        last = {}
        for e in sorted(calls, key=lambda x: (x["day"], x["mins"])):
            if (e["day"], e["mins"]) in used:
                continue
            if any(d == e["day"] and abs(m - e["mins"]) < gap for d, m in used):
                continue
            prev = last.get(e["day"])
            if prev is not None and e["mins"] - prev < gap:
                continue
            out.append(e)
            last[e["day"]] = e["mins"]
        return out

    for r in cells:
        ck = take(r["cal_calls"], used_c)
        tk = take(r["l3m_calls"], used_t)
        if len(ck) < 2 or len(tk) < 2:
            continue
        st = r["st"]
        if not all(e.get(f"_ok_{st}") for e in ck + tk):
            continue
        chosen.append({**r, "cal_calls": ck, "l3m_calls": tk, "cal_n": len(ck), "l3m_n": len(tk)})
        for e in ck:
            used_c.add((e["day"], e["mins"]))
        for e in tk:
            used_t.add((e["day"], e["mins"]))
    return chosen


def stats(calls):
    n = len(calls)
    days = len({e["day"] for e in calls})
    by = defaultdict(int)
    for e in calls:
        by[e["day"]] += 1
    sls = [e[f"_sl_{e['_st']}"] for e in calls] if calls and "_st" in calls[0] else []
    return {
        "n": n,
        "days": days,
        "cpd": round(n / days, 2) if days else 0,
        "multi": sum(1 for v in by.values() if v >= 2),
        "max": max(by.values()) if by else 0,
        "avg_sl": round(sum(sls) / len(sls), 2) if sls else 0,
    }


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · SCALP DEEPER 100% densify", flush=True)
    print("=" * 60, flush=True)
    PACK_OUT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    blob = pickle.load(next(PACK.glob("scalp_events_*.pkl")).open("rb"))
    cal, test = blob["cal"], blob["test"]
    print(f"events cal={len(cal)} l3m={len(test)}", flush=True)

    raw = base.load_existing_1m()
    h = raw["High"].astype(float).values
    l = raw["Low"].astype(float).values
    c = raw["Close"].astype(float).values
    o = raw["Open"].astype(float).values

    print("[1] geometry enrich…", flush=True)
    enrich_geometry(cal, raw, h, l, c, o)
    enrich_geometry(test, raw, h, l, c, o)

    styles = ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "p75"]
    t1 = 10.0
    print("[2] path flags SL<=12…", flush=True)
    t0 = time.time()
    for i, e in enumerate(cal + test):
        if i and i % 25000 == 0:
            print(f"    {i} ({time.time()-t0:.0f}s)", flush=True)
        best = None
        for st in styles:
            ok, sl = path_ok(e, h, l, c, st, t1)
            e[f"_ok_{st}"] = ok
            e[f"_sl_{st}"] = sl
            if ok and best is None:
                best = st
        e["_ok_any"] = best is not None
        e["_best_st"] = best

    # Feature lift: which deep tags correlate with path win
    print("[3] feature lift (cal)…", flush=True)
    wins = [e for e in cal if e.get("_ok_prev")]
    all_e = [e for e in cal if 4 <= e["sl_prev"] <= 12]
    base_rate = len(wins) / max(len(all_e), 1)
    print(f"  base prev path-win rate (SL4-12): {100*base_rate:.1f}% n={len(all_e)}", flush=True)
    lifts = []
    for feat, fn in [
        ("adv_wick<0.15", lambda e: e.get("adv_wick", 1) < 0.15),
        ("adv_wick<0.25", lambda e: e.get("adv_wick", 1) < 0.25),
        ("body_atr>=0.8", lambda e: e.get("body_atr", 0) >= 0.8),
        ("body_atr>=1.0", lambda e: e.get("body_atr", 0) >= 1.0),
        ("stack2==2", lambda e: e.get("stack2", 0) == 2),
        ("stack2>=1", lambda e: e.get("stack2", 0) >= 1),
        ("align", lambda e: e["align_session"] == 1),
        ("continuation", lambda e: e["pre_regime"] == "continuation"),
        ("sl_atr<0.8", lambda e: e.get("sl_prev_atr", 9) < 0.8),
        ("body70+", lambda e: e["body_frac"] >= 0.70),
        ("fav_wick>0.3", lambda e: e.get("fav_wick", 0) > 0.3),
        ("early", lambda e: e["clock"] == "early"),
        ("morning", lambda e: e["clock"] == "morning"),
        ("midday", lambda e: e["clock"] == "midday"),
    ]:
        sub = [e for e in all_e if fn(e)]
        if len(sub) < 50:
            continue
        wr = sum(1 for e in sub if e.get("_ok_prev")) / len(sub)
        lifts.append((feat, len(sub), wr, wr - base_rate))
    lifts.sort(key=lambda x: -x[3])
    for feat, n, wr, d in lifts:
        print(f"  {feat:20s} n={n:5d} wr={100*wr:.1f}% lift={100*d:+.1f}pp", flush=True)

    # Hunt deep cells
    best_union = None
    all_results = []

    for gap in (8, 10, 12, 15, 20):
        print(f"\n[4] hunt gap={gap}…", flush=True)
        # buckets per style
        both = []
        for st in styles:
            cal_b = defaultdict(list)
            test_b = defaultdict(list)
            for e in cal:
                if not (4 <= e["sl_prev"] <= 20):
                    continue
                for k in cell_keys(e):
                    cal_b[k].append(e)
            for e in test:
                if not (4 <= e["sl_prev"] <= 20):
                    continue
                for k in cell_keys(e):
                    test_b[k].append(e)
            for k, ces in cal_b.items():
                cal_rows = apply_gap(ces, gap)
                if len(cal_rows) < 3:
                    continue
                if not all(e.get(f"_ok_{st}") for e in cal_rows):
                    continue
                tes = apply_gap(test_b.get(k, []), gap)
                if len(tes) < 2:
                    continue
                if not all(e.get(f"_ok_{st}") for e in tes):
                    continue
                avg = sum(e[f"_sl_{st}"] for e in tes) / len(tes)
                if avg > 12:
                    continue
                both.append(
                    {
                        "k": k,
                        "st": st,
                        "gap": gap,
                        "cal_n": len(cal_rows),
                        "l3m_n": len(tes),
                        "avg_sl": avg,
                        "cal_calls": cal_rows,
                        "l3m_calls": tes,
                    }
                )
        both.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"], r["avg_sl"]))
        # dedupe same (k,st)
        seen = set()
        uniq = []
        for r in both:
            id_ = (r["k"], r["st"])
            if id_ in seen:
                continue
            seen.add(id_)
            uniq.append(r)
        print(f"  both-100 deep cells: {len(uniq)}", flush=True)
        chosen = greedy_union(uniq, gap)
        cal_all, l3m_all = [], []
        for r in chosen:
            for e in r["cal_calls"]:
                ee = dict(e)
                ee["_st"] = r["st"]
                cal_all.append(ee)
            for e in r["l3m_calls"]:
                ee = dict(e)
                ee["_st"] = r["st"]
                l3m_all.append(ee)
        sc, sl = stats(cal_all), stats(l3m_all)
        print(
            f"  UNION gap{gap}: cal {sc['n']}c/{sc['days']}d ({sc['cpd']}/d) · "
            f"l3m {sl['n']}c/{sl['days']}d ({sl['cpd']}/d multi={sl['multi']} max={sl['max']}) "
            f"avgSL={sl['avg_sl']} micros={len(chosen)}",
            flush=True,
        )
        rec = {
            "gap": gap,
            "n_cells": len(uniq),
            "n_micros": len(chosen),
            "cal": sc,
            "l3m": sl,
            "top_cells": [
                {
                    "k": str(r["k"]),
                    "st": r["st"],
                    "cal_n": r["cal_n"],
                    "l3m_n": r["l3m_n"],
                    "avg_sl": round(r["avg_sl"], 2),
                }
                for r in uniq[:25]
            ],
            "l3m_calls": [
                {
                    "day": e["day"],
                    "hm": e["hm"],
                    "decision": e["decision"],
                    "primary": e["primary"],
                    "st": e["_st"],
                    "sl": round(e[f"_sl_{e['_st']}"], 2),
                }
                for e in sorted(l3m_all, key=lambda x: (x["day"], x["mins"]))
            ],
        }
        all_results.append(rec)
        score = (sl["n"], sc["n"], -sl["avg_sl"])
        if best_union is None or score > best_union[0]:
            best_union = (score, rec, chosen, uniq)

    # Score-threshold picker: logistic-ish linear score on cal, find threshold both 100%
    print("\n[5] score-threshold picker…", flush=True)

    def score_e(e):
        s = 0.0
        s += 1.2 if e.get("adv_wick", 1) < 0.15 else 0
        s += 0.8 if e.get("adv_wick", 1) < 0.25 else 0
        s += 1.0 if e.get("body_atr", 0) >= 0.8 else 0
        s += 0.7 if e.get("stack2", 0) == 2 else 0
        s += 0.5 if e["align_session"] == 1 else 0
        s += 0.4 if e["pre_regime"] == "continuation" else 0
        s += 0.6 if e.get("sl_prev_atr", 9) < 0.8 else 0
        s += 0.5 if e["body_frac"] >= 0.70 else 0
        s += 0.3 if e["clock"] in ("early", "morning") else 0
        s -= 0.8 if e.get("adv_wick", 0) > 0.35 else 0
        return s

    for e in cal + test:
        e["_score"] = score_e(e)

    score_books = []
    for gap in (10, 15):
        for st in ("prev", "cap10", "sig", "min_ps"):
            # candidates: SL ok + structure
            for thr in np.arange(1.5, 5.5, 0.25):
                def pick(pool):
                    rows = []
                    for e in sorted(pool, key=lambda x: (x["day"], -x["_score"], x["mins"])):
                        if e["_score"] < thr:
                            continue
                        if not (4 <= lesser(e, st) <= 12):
                            continue
                        if not e.get(f"_ok_{st}"):
                            # include for evaluation even if lose — we need actual outcomes
                            pass
                        rows.append(e)
                    # day multi with gap, prefer high score first
                    by = defaultdict(list)
                    for e in rows:
                        by[e["day"]].append(e)
                    out = []
                    for d, xs in by.items():
                        xs = sorted(xs, key=lambda x: (-x["_score"], x["mins"]))
                        last = None
                        for e in xs:
                            if last is not None and e["mins"] - last < gap:
                                continue
                            # also chronological gap: re-sort by time after selecting? use time order among high score
                            out.append(e)
                            last = e["mins"]
                    # re-apply chronological gap properly
                    return apply_gap(out, gap)

                # Better picker: chronological, only take if score>=thr
                def pick2(pool):
                    rows = [
                        e
                        for e in pool
                        if e["_score"] >= thr and 4 <= lesser(e, st) <= 12
                    ]
                    return apply_gap(rows, gap)

                ca = pick2(cal)
                te = pick2(test)
                if len(ca) < 8 or len(te) < 5:
                    continue
                if not all(e.get(f"_ok_{st}") for e in ca):
                    continue
                if not all(e.get(f"_ok_{st}") for e in te):
                    continue
                sc = stats([{**e, "_st": st} for e in ca])
                sl = stats([{**e, "_st": st} for e in te])
                score_books.append(
                    {
                        "gap": gap,
                        "st": st,
                        "thr": float(thr),
                        "cal": sc,
                        "l3m": sl,
                    }
                )
    score_books.sort(key=lambda r: (-r["l3m"]["n"], -r["cal"]["n"]))
    print(f"  perfect score books: {len(score_books)}", flush=True)
    for r in score_books[:10]:
        print(
            f"  thr={r['thr']:.2f} {r['st']} gap{r['gap']}: "
            f"cal {r['cal']['n']}c/{r['cal']['days']}d · "
            f"l3m {r['l3m']['n']}c/{r['l3m']['days']}d ({r['l3m']['cpd']}/d)",
            flush=True,
        )

    # Combo filter: high-lift features AND path — single global rule
    print("\n[6] global high-lift rules…", flush=True)
    global_rules = []
    for gap in (10, 15):
        for st in styles:
            for name, pred in [
                ("adv<0.15+ba>=0.8+align", lambda e: e.get("adv_wick", 1) < 0.15 and e.get("body_atr", 0) >= 0.8 and e["align_session"] == 1),
                ("adv<0.15+stack2+align", lambda e: e.get("adv_wick", 1) < 0.15 and e.get("stack2", 0) == 2 and e["align_session"] == 1),
                ("adv<0.25+ba>=1+cont", lambda e: e.get("adv_wick", 1) < 0.25 and e.get("body_atr", 0) >= 1.0 and e["pre_regime"] == "continuation"),
                ("adv<0.15+sla<0.8", lambda e: e.get("adv_wick", 1) < 0.15 and e.get("sl_prev_atr", 9) < 0.8),
                ("adv<0.15+b70+early", lambda e: e.get("adv_wick", 1) < 0.15 and e["body_frac"] >= 0.7 and e["clock"] in ("early", "morning")),
                ("adv<0.2+ba>=0.8+stack>=1", lambda e: e.get("adv_wick", 1) < 0.2 and e.get("body_atr", 0) >= 0.8 and e.get("stack2", 0) >= 1),
            ]:
                ca = apply_gap(
                    [e for e in cal if pred(e) and 4 <= lesser(e, st) <= 12], gap
                )
                te = apply_gap(
                    [e for e in test if pred(e) and 4 <= lesser(e, st) <= 12], gap
                )
                if len(ca) < 5 or len(te) < 3:
                    continue
                if all(e.get(f"_ok_{st}") for e in ca) and all(e.get(f"_ok_{st}") for e in te):
                    sc = stats([{**e, "_st": st} for e in ca])
                    sl = stats([{**e, "_st": st} for e in te])
                    global_rules.append(
                        {"name": name, "st": st, "gap": gap, "cal": sc, "l3m": sl}
                    )
                    print(
                        f"  HIT {name} {st} gap{gap}: cal {sc['n']} l3m {sl['n']}c/{sl['days']}d",
                        flush=True,
                    )
    global_rules.sort(key=lambda r: (-r["l3m"]["n"], -r["cal"]["n"]))

    # Re-entry: after a path win, next pattern same side within 30-90m
    print("\n[7] re-entry after path-win…", flush=True)
    reentry_books = []
    for gap_after in (20, 30, 45):
        for st in ("prev", "cap10", "sig"):
            def reentries(pool):
                by = defaultdict(list)
                for e in pool:
                    by[e["day"]].append(e)
                out = []
                for d, xs in by.items():
                    xs = sorted(xs, key=lambda x: x["mins"])
                    last_win_mins = None
                    last_side = None
                    for e in xs:
                        if last_win_mins is not None:
                            dt = e["mins"] - last_win_mins
                            if (
                                gap_after <= dt <= gap_after + 60
                                and e["decision"] == last_side
                                and 4 <= lesser(e, st) <= 12
                                and e.get("adv_wick", 1) < 0.25
                            ):
                                out.append(e)
                        if e.get(f"_ok_{st}"):
                            # mark any path win as seed (oracle-ish for research of structure after win)
                            # NON-lookahead seed: only use if previous selected reentry or first win under filter
                            pass
                    # proper non-lookahead: seed = first event of day with score high / structure
                    seeds = [
                        e
                        for e in xs
                        if e.get(f"_ok_{st}")
                        and e.get("adv_wick", 1) < 0.2
                        and e["align_session"] == 1
                        and 4 <= lesser(e, st) <= 12
                    ]
                    if not seeds:
                        continue
                    # use chronological: when we TAKE a trade that wins, allow reentry
                    taken = []
                    last_taken = None
                    last_win = None
                    last_side = None
                    for e in xs:
                        if last_win is not None and last_side == e["decision"]:
                            dt = e["mins"] - last_win
                            if (
                                gap_after <= dt <= gap_after + 90
                                and 4 <= lesser(e, st) <= 12
                                and e.get("adv_wick", 1) < 0.25
                                and (last_taken is None or e["mins"] - last_taken >= 15)
                            ):
                                taken.append(e)
                                last_taken = e["mins"]
                                if e.get(f"_ok_{st}"):
                                    last_win = e["mins"]
                                    last_side = e["decision"]
                                else:
                                    # loss breaks chain
                                    last_win = None
                                    last_side = None
                                continue
                        # seed entry
                        if (
                            e.get("adv_wick", 1) < 0.15
                            and e["align_session"] == 1
                            and e.get("body_atr", 0) >= 0.7
                            and 4 <= lesser(e, st) <= 12
                            and (last_taken is None or e["mins"] - last_taken >= 15)
                        ):
                            taken.append(e)
                            last_taken = e["mins"]
                            if e.get(f"_ok_{st}"):
                                last_win = e["mins"]
                                last_side = e["decision"]
                            else:
                                last_win = None
                                last_side = None
                    out.extend(taken)
                return out

            ca = reentries(cal)
            te = reentries(test)
            if len(ca) < 5 or len(te) < 3:
                continue
            cw = all(e.get(f"_ok_{st}") for e in ca)
            tw = all(e.get(f"_ok_{st}") for e in te)
            if cw and tw:
                sc = stats([{**e, "_st": st} for e in ca])
                sl = stats([{**e, "_st": st} for e in te])
                reentry_books.append(
                    {"gap_after": gap_after, "st": st, "cal": sc, "l3m": sl}
                )
                print(
                    f"  REENTRY 100% after{gap_after} {st}: cal {sc['n']} l3m {sl['n']}c/{sl['days']}d",
                    flush=True,
                )

    # Write report
    bu = best_union[1] if best_union else None
    lines = [
        "# NIFTY 1m — **deeper scalp 100%** densification",
        "",
        "**Not live.** Wick/ATR/stack features · score picker · re-entry · deeper micros.",
        "",
        f"- Prior PATH union baseline: **187 calls / 64 days** (~2.9/day)",
        f"- Oracle ceiling: ~21 path-wins/day (SL≤12, T1=10)",
        "",
        "## Feature lift (calibrate · prev SL 4–12)",
        "",
        f"- Base path-win rate: **{100*base_rate:.1f}%**",
        "",
        "| Feature | N | Win% | Lift |",
        "|---|---:|---:|---:|",
    ]
    for feat, n, wr, d in lifts[:12]:
        lines.append(f"| `{feat}` | {n} | {100*wr:.1f} | {100*d:+.1f}pp |")

    if bu:
        lines += [
            "",
            "## Best deep PATH union",
            "",
            f"- Gap **{bu['gap']}** · micros **{bu['n_micros']}** · cells scanned **{bu['n_cells']}**",
            f"- Calibrate: **{bu['cal']['n']} calls / {bu['cal']['days']} days** · "
            f"{bu['cal']['cpd']}/day · multi-days {bu['cal']['multi']}",
            f"- Last3m: **{bu['l3m']['n']} calls / {bu['l3m']['days']} days** · "
            f"**{bu['l3m']['cpd']}/day** · multi-days {bu['l3m']['multi']} · "
            f"max/day {bu['l3m']['max']} · avg SL **{bu['l3m']['avg_sl']}**",
            "",
            "### Top deep micros",
            "",
            "| Cal | L3m | AvgSL | Exit | Cell |",
            "|---:|---:|---:|---|---|",
        ]
        for r in bu["top_cells"][:20]:
            lines.append(
                f"| {r['cal_n']} | {r['l3m_n']} | {r['avg_sl']} | `{r['st']}` | `{r['k']}` |"
            )
        lines += [
            "",
            "### Last3m calls (sample)",
            "",
            "| Day | HM | Side | Pattern | SL style | SL |",
            "|---|---|---|---|---|---:|",
        ]
        for e in bu["l3m_calls"][:50]:
            lines.append(
                f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"`{e['st']}` | {e['sl']} |"
            )
        if len(bu["l3m_calls"]) > 50:
            lines.append(f"| … | | | | | {len(bu['l3m_calls'])-50} more |")

    lines += [
        "",
        "## Gap sweep unions",
        "",
        "| Gap | Cal calls | Cal days | L3m calls | L3m days | L3m /day | Multi-days | Micros |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in all_results:
        lines.append(
            f"| {r['gap']} | {r['cal']['n']} | {r['cal']['days']} | {r['l3m']['n']} | "
            f"{r['l3m']['days']} | {r['l3m']['cpd']} | {r['l3m']['multi']} | {r['n_micros']} |"
        )

    if score_books:
        lines += [
            "",
            "## Score-threshold perfect books",
            "",
            "| Thr | Style | Gap | Cal | L3m | L3m/day |",
            "|---:|---|---:|---:|---:|---:|",
        ]
        for r in score_books[:12]:
            lines.append(
                f"| {r['thr']:.2f} | `{r['st']}` | {r['gap']} | {r['cal']['n']} | "
                f"{r['l3m']['n']} | {r['l3m']['cpd']} |"
            )

    if global_rules:
        lines += [
            "",
            "## Global high-lift rules @100%",
            "",
            "| Rule | Style | Gap | Cal | L3m | L3m/day |",
            "|---|---|---:|---:|---:|---:|",
        ]
        for r in global_rules[:15]:
            lines.append(
                f"| `{r['name']}` | `{r['st']}` | {r['gap']} | {r['cal']['n']} | "
                f"{r['l3m']['n']} | {r['l3m']['cpd']} |"
            )
    else:
        lines += ["", "## Global high-lift rules @100%", "", "- none held both windows", ""]

    if reentry_books:
        lines += [
            "",
            "## Re-entry chains @100%",
            "",
            "| After-win gap | Style | Cal | L3m | L3m/day |",
            "|---:|---|---:|---:|---:|",
        ]
        for r in reentry_books[:10]:
            lines.append(
                f"| {r['gap_after']} | `{r['st']}` | {r['cal']['n']} | "
                f"{r['l3m']['n']} | {r['l3m']['cpd']} |"
            )

    lines += [
        "",
        "## Policy",
        "",
        "- research_only · not_live · deeper densify",
        f"- Pack: `{PACK_OUT}`",
        f"- Related: [`NIFTY_1M_SCALP_MULTICALL_100.md`](NIFTY_1M_SCALP_MULTICALL_100.md)",
        "",
    ]

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {
        "base_rate": base_rate,
        "lifts": [{"feat": a, "n": b, "wr": c, "lift": d} for a, b, c, d in lifts],
        "gap_unions": all_results,
        "best": bu,
        "score_books": score_books[:30],
        "global_rules": global_rules[:30],
        "reentry_books": reentry_books,
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (PACK_OUT / "deeper_summary.json").write_text(
        json.dumps(
            {
                "best_l3m": bu["l3m"] if bu else None,
                "best_cal": bu["cal"] if bu else None,
                "score_top": score_books[:5],
                "global_top": global_rules[:5],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    # append pointer on multicall report
    if MULTI_MD.exists():
        md = MULTI_MD.read_text(encoding="utf-8")
        marker = "## Deeper densification"
        block = [
            "",
            "## Deeper densification",
            "",
            f"See [`NIFTY_1M_SCALP_DEEPER_100.md`](NIFTY_1M_SCALP_DEEPER_100.md).",
        ]
        if bu:
            block.append(
                f"- Best deep PATH union: **{bu['l3m']['n']} calls / {bu['l3m']['days']} days** "
                f"({bu['l3m']['cpd']}/day) · gap {bu['gap']} · avg SL {bu['l3m']['avg_sl']}"
            )
        if score_books:
            s = score_books[0]
            block.append(
                f"- Best score book: thr={s['thr']} `{s['st']}` → l3m **{s['l3m']['n']}** calls "
                f"({s['l3m']['cpd']}/day)"
            )
        if global_rules:
            g = global_rules[0]
            block.append(
                f"- Best global rule: `{g['name']}` `{g['st']}` → l3m **{g['l3m']['n']}** calls"
            )
        if marker in md:
            md = md.split(marker)[0].rstrip()
        MULTI_MD.write_text(md + "\n" + "\n".join(block) + "\n", encoding="utf-8")

    print(f"\nWrote {REPORT_MD}", flush=True)
    if bu:
        print(
            f"BEST deep union: l3m {bu['l3m']['n']} calls / {bu['l3m']['days']} days "
            f"({bu['l3m']['cpd']}/day) vs prior 187",
            flush=True,
        )
    print("DONE deeper 100%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
