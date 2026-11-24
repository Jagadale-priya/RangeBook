"""RESEARCH ONLY — Hold T1=10 & T1=15 books; deep densify more T1=15/20 PATH @100%.

Focus:
  1) Map zero-days vs oracle wins
  2) Session-split + pattern-family + ultra-thin cells
  3) Mega cross-style union with min_l3m=1 / min_cal=2
  4) Fill uncovered days with secondary micros that stay both-100

  python -u prod_live/tests/builders/research_nifty_1m_scalp_t15_t20_deeper.py
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

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
REPORT_MD = OUT / "NIFTY_1M_SCALP_T15_T20_DEEPER.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_T15_T20_DEEPER.json"
PACK_OUT = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_t15_t20_deeper"
HELD10 = OUT / "NIFTY_1M_SCALP_DEEPER_100.json"
HELD15 = OUT / "NIFTY_1M_SCALP_HIGHT_MORECALLS_100.json"

STYLES = ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "cap15", "cap20", "p75", "p60"]
FAMILIES = {
    "runs": {"bull_run2", "bull_run3", "bear_run2", "bear_run3"},
    "engulf": {"bull_engulf", "bear_engulf", "dark_cloud", "piercing"},
    "belt_maru": {"belt_bull", "belt_bear", "marubozu_bull", "marubozu_bear"},
    "stars": {"morning_star", "evening_star", "morning_doji_star", "evening_doji_star"},
    "three": {"three_outside_up", "three_outside_dn", "three_crows", "three_soldiers"},
    "kick": {"bull_kicker", "bear_kicker"},
}


def lesser(e, st):
    p, s = float(e["sl_prev"]), float(e["sl_sig"])
    return {
        "prev": p,
        "sig": s,
        "min_ps": min(p, s) if s >= 4 else p,
        "cap8": min(p, 8.0),
        "cap10": min(p, 10.0),
        "cap12": min(p, 12.0),
        "cap15": min(p, 15.0),
        "cap20": min(p, 20.0),
        "p75": max(4.0, 0.75 * p),
        "p60": max(4.0, 0.60 * p),
    }[st]


def enrich(events, h, l, c, o):
    for e in events:
        fi = int(e["full_i"])
        hi, lo, cl, op = float(h[fi]), float(l[fi]), float(c[fi]), float(o[fi])
        rng = max(hi - lo, 0.5)
        upper = hi - max(op, cl)
        lower = min(op, cl) - lo
        e["adv_wick"] = (upper if e["decision"] == "BUY" else lower) / rng
        e["body_atr"] = abs(cl - op) / max(float(e["atr"]), 1.0)
        if fi >= 2:
            d1, d2 = c[fi - 1] - o[fi - 1], c[fi - 2] - o[fi - 2]
            e["stack2"] = (
                int(d1 > 0) + int(d2 > 0)
                if e["decision"] == "BUY"
                else int(d1 < 0) + int(d2 < 0)
            )
        else:
            e["stack2"] = 0
        # family
        e["family"] = "other"
        for fname, pats in FAMILIES.items():
            if e["primary"] in pats:
                e["family"] = fname
                break
        # session half
        e["half"] = "am" if e["mins"] < 720 else "pm"  # before/after 12:00
        e["slot"] = (
            "open"
            if e["mins"] < 600
            else (
                "morn"
                if e["mins"] < 690
                else ("mid" if e["mins"] < 780 else ("aft" if e["mins"] < 870 else "close"))
            )
        )


def path_ok(e, h, l, c, st, t1, sl_max=20.0):
    sl = lesser(e, st)
    if not (4 <= sl <= sl_max):
        return False, sl
    if st == "prev" and t1 in (15.0, 20.0) and e.get(f"prev_t{int(t1)}") is not None:
        return e[f"prev_t{int(t1)}"] == "win", sl
    if st == "sig" and t1 in (15.0, 20.0) and e.get(f"sig_t{int(t1)}") is not None:
        return e[f"sig_t{int(t1)}"] == "win", sl
    win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], float(sl), float(t1))
    return (win and out == "t1"), sl


def apply_gap(rows, gap):
    last, out = {}, []
    for e in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        prev = last.get(e["day"])
        if prev is not None and e["mins"] - prev < gap:
            continue
        out.append(e)
        last[e["day"]] = e["mins"]
    return out


def deep_keys(e):
    body = float(e["body_frac"])
    g = {
        "primary": e["primary"],
        "family": e["family"],
        "side": e["decision"],
        "regime": e["pre_regime"],
        "align": int(e["align_session"]),
        "clock": e["clock"],
        "half": e["half"],
        "slot": e["slot"],
        "body": "b70+" if body >= 0.70 else ("b55+" if body >= 0.55 else ("b45+" if body >= 0.45 else "b<45")),
        "slbin": (
            "sl4-8"
            if e["sl_prev"] <= 8
            else ("sl8-12" if e["sl_prev"] <= 12 else ("sl12-16" if e["sl_prev"] <= 16 else "sl16-20"))
        ),
        "rsi": "lo" if e["rsi_14"] < 35 else ("hi" if e["rsi_14"] > 65 else "mid"),
        "advw": "adv_lo" if e["adv_wick"] < 0.15 else ("adv_mid" if e["adv_wick"] < 0.30 else "adv_hi"),
        "batr": "ba>0.8" if e.get("body_atr", 0) >= 0.8 else ("ba>0.5" if e.get("body_atr", 0) >= 0.5 else "ba<0.5"),
        "stack": f"st{e.get('stack2', 0)}",
    }
    return [
        # prior deep
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        ("GEOM", g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        # family + session
        (g["family"], g["side"], g["regime"], g["align"], g["half"], g["body"], g["slbin"], g["advw"]),
        (g["family"], g["side"], g["align"], g["slot"], g["body"], g["slbin"], g["advw"], g["stack"]),
        ("FAM", g["family"], g["side"], g["regime"], g["align"], g["clock"], g["advw"], g["slbin"]),
        # slot focused
        (g["primary"], g["side"], g["slot"], g["align"], g["body"], g["slbin"], g["advw"]),
        ("SLOT", g["side"], g["slot"], g["regime"], g["align"], g["body"], g["slbin"], g["advw"]),
        # ultra thin primary
        (g["primary"], g["side"], g["align"], g["clock"], g["advw"], g["slbin"]),
        (g["primary"], g["side"], g["half"], g["advw"], g["body"]),
        # rsi-light
        (g["primary"], g["side"], g["regime"], g["clock"], g["body"], g["slbin"], g["advw"]),
    ]


def greedy(cells, gap, min_cal=2, min_l3m=1, used_c=None, used_t=None):
    used_c = used_c if used_c is not None else set()
    used_t = used_t if used_t is not None else set()
    chosen = []

    def take(calls, used):
        out, last = [], {}
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
        ck, tk = take(r["cal_calls"], used_c), take(r["l3m_calls"], used_t)
        if len(ck) < min_cal or len(tk) < min_l3m:
            continue
        st = r["st"]
        if not all(e.get(f"_ok_{st}") for e in ck + tk):
            continue
        chosen.append({**r, "cal_calls": ck, "l3m_calls": tk})
        for e in ck:
            used_c.add((e["day"], e["mins"]))
        for e in tk:
            used_t.add((e["day"], e["mins"]))
    return chosen, used_c, used_t


def stats(calls, n_window=64):
    by = Counter(e["day"] for e in calls)
    n, days = len(calls), len(by)
    vals = list(by.values()) if by else []
    sls = [e[f"_sl_{e['_st']}"] for e in calls] if calls else []
    t1 = calls[0]["_t1"] if calls else 0
    avg_sl = sum(sls) / len(sls) if sls else 0
    return {
        "n": n,
        "days": days,
        "zero": n_window - days,
        "cpd": round(n / days, 2) if days else 0,
        "cpd_all": round(n / n_window, 2),
        "multi": sum(1 for v in vals if v >= 2),
        "min": min(vals) if vals else 0,
        "p50": sorted(vals)[len(vals) // 2] if vals else 0,
        "max": max(vals) if vals else 0,
        "avg_sl": round(avg_sl, 2),
        "rr": round(t1 / avg_sl, 2) if avg_sl else 0,
        "hist": dict(sorted(Counter(vals).items())),
        "dayset": sorted(by.keys()),
    }


def hunt_cells(cal_b, test_b, styles, gap, sl_max, min_cal=3, min_l3m_full=2):
    both = []
    for st in styles:
        for k, ces in cal_b.items():
            cr = apply_gap(ces, gap)
            cr = [e for e in cr if 4 <= e.get(f"_sl_{st}", 99) <= sl_max]
            cr = apply_gap(cr, gap)
            if len(cr) < min_cal:
                continue
            if not all(e.get(f"_ok_{st}") for e in cr):
                continue
            tr = apply_gap(test_b.get(k, []), gap)
            tr = [e for e in tr if 4 <= e.get(f"_sl_{st}", 99) <= sl_max]
            tr = apply_gap(tr, gap)
            if len(tr) < 1:
                continue
            if len(tr) < min_l3m_full and len(cr) < 4:
                continue
            if not all(e.get(f"_ok_{st}") for e in tr):
                continue
            both.append(
                {
                    "k": k,
                    "st": st,
                    "cal_calls": cr,
                    "l3m_calls": tr,
                    "cal_n": len(cr),
                    "l3m_n": len(tr),
                    "avg_sl": sum(e[f"_sl_{st}"] for e in tr) / len(tr),
                }
            )
    both.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"], r["avg_sl"]))
    seen, uniq = set(), []
    for r in both:
        id_ = (r["k"], r["st"])
        if id_ in seen:
            continue
        seen.add(id_)
        uniq.append(r)
    return uniq


def analyze_zero_days(test, h, l, c, t1, covered_days, sl_max=20.0):
    """On uncovered days, what oracle path-wins look like."""
    all_days = sorted({e["day"] for e in test})
    zero = [d for d in all_days if d not in covered_days]
    rows = []
    feat = Counter()
    pats = Counter()
    n_oracle = 0
    for d in zero:
        es = [e for e in test if e["day"] == d]
        wins = []
        for e in es:
            for st in STYLES:
                ok, sl = path_ok(e, h, l, c, st, t1, sl_max=sl_max)
                if ok:
                    wins.append((e, st, sl))
                    break
        n_oracle += len(wins)
        for e, st, sl in wins[:5]:
            pats[e["primary"]] += 1
            feat[f"adv_lo"] += int(e["adv_wick"] < 0.15)
            feat[f"body70"] += int(e["body_frac"] >= 0.70)
            feat[f"align"] += int(e["align_session"] == 1)
            feat[f"cont"] += int(e["pre_regime"] == "continuation")
            feat[f"am"] += int(e["half"] == "am")
            feat[f"family:{e['family']}"] += 1
            feat[f"slot:{e['slot']}"] += 1
        rows.append({"day": d, "oracle_wins": len(wins), "sample": [
            {
                "hm": e["hm"],
                "primary": e["primary"],
                "side": e["decision"],
                "st": st,
                "sl": round(sl, 2),
                "adv": round(e["adv_wick"], 2),
                "body": round(e["body_frac"], 2),
                "family": e["family"],
                "slot": e["slot"],
            }
            for e, st, sl in wins[:3]
        ]})
    return {
        "zero_days": zero,
        "n_zero": len(zero),
        "oracle_wins_on_zero": n_oracle,
        "top_patterns": pats.most_common(10),
        "feat_counts": dict(feat),
        "day_rows": rows,
    }


def main() -> int:
    print("=" * 60, flush=True)
    print("DEEP densify T1=15/20 · hold T1=10 & prior T1=15", flush=True)
    print("=" * 60, flush=True)
    PACK_OUT.mkdir(parents=True, exist_ok=True)

    held10 = json.loads(HELD10.read_text(encoding="utf-8")).get("best") if HELD10.exists() else None
    held15 = None
    if HELD15.exists():
        j15 = json.loads(HELD15.read_text(encoding="utf-8"))
        held15 = (j15.get("by_t1") or {}).get("15", {}).get("best_coverage")
    print(f"HELD10: {held10['l3m'] if held10 else None}", flush=True)
    print(f"HELD15: {held15['l3m'] if held15 else None}", flush=True)

    blob = pickle.load(next(PACK.glob("scalp_events_*.pkl")).open("rb"))
    cal, test = blob["cal"], blob["test"]
    raw = base.load_existing_1m()
    h = raw["High"].astype(float).values
    l = raw["Low"].astype(float).values
    c = raw["Close"].astype(float).values
    o = raw["Open"].astype(float).values
    enrich(cal, h, l, c, o)
    enrich(test, h, l, c, o)

    results = {"held10": held10["l3m"] if held10 else None, "held15": held15["l3m"] if held15 else None, "t1": {}}

    for t1 in (15.0, 20.0):
        print(f"\n######## DEEP T1={t1:.0f} ########", flush=True)
        t0 = time.time()
        for i, e in enumerate(cal + test):
            if i and i % 30000 == 0:
                print(f"  flags {i} ({time.time()-t0:.0f}s)", flush=True)
            for st in STYLES:
                ok, sl = path_ok(e, h, l, c, st, t1, sl_max=20.0)
                e[f"_ok_{st}"] = ok
                e[f"_sl_{st}"] = sl
            e["_keys"] = deep_keys(e)

        cal_b, test_b = defaultdict(list), defaultdict(list)
        for e in cal:
            if 4 <= e["sl_prev"] <= 20:
                for k in e["_keys"]:
                    cal_b[k].append(e)
        for e in test:
            if 4 <= e["sl_prev"] <= 20:
                for k in e["_keys"]:
                    test_b[k].append(e)
        print(f"  bucket keys cal={len(cal_b)}", flush=True)

        books = []
        best = None
        for sl_max in (12.0, 15.0, 20.0):
            for gap in (4, 5, 6, 8):
                uniq = hunt_cells(cal_b, test_b, STYLES, gap, sl_max, min_cal=3, min_l3m_full=2)
                # also softer min_cal=2 cells
                uniq2 = hunt_cells(cal_b, test_b, STYLES, gap, sl_max, min_cal=2, min_l3m_full=1)
                # merge unique
                seen = {(r["k"], r["st"]) for r in uniq}
                for r in uniq2:
                    if (r["k"], r["st"]) not in seen:
                        uniq.append(r)
                        seen.add((r["k"], r["st"]))
                uniq.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"], r["avg_sl"]))

                for mode, ml in (("strict", 2), ("dense", 1)):
                    chosen, _, _ = greedy(uniq, gap, min_cal=2, min_l3m=ml)
                    cal_all = [{**e, "_st": r["st"], "_t1": t1} for r in chosen for e in r["cal_calls"]]
                    l3m_all = [{**e, "_st": r["st"], "_t1": t1} for r in chosen for e in r["l3m_calls"]]
                    if not l3m_all or not all(e.get(f"_ok_{e['_st']}") for e in cal_all + l3m_all):
                        continue
                    sc, sl = stats(cal_all, 271), stats(l3m_all, 64)
                    rec = {
                        "kind": f"deep_{mode}",
                        "t1": t1,
                        "sl_max": sl_max,
                        "gap": gap,
                        "n_micros": len(chosen),
                        "n_cells": len(uniq),
                        "cal": {k: v for k, v in sc.items() if k != "dayset"},
                        "l3m": {k: v for k, v in sl.items() if k != "dayset"},
                        "dayset": sl["dayset"],
                        "top": [
                            {
                                "k": str(r["k"]),
                                "st": r["st"],
                                "cal_n": r["cal_n"],
                                "l3m_n": r["l3m_n"],
                                "avg_sl": round(r["avg_sl"], 2),
                            }
                            for r in uniq[:15]
                        ],
                        "l3m_calls": [
                            {
                                "day": e["day"],
                                "hm": e["hm"],
                                "decision": e["decision"],
                                "primary": e["primary"],
                                "family": e["family"],
                                "slot": e["slot"],
                                "st": e["_st"],
                                "sl": round(e[f"_sl_{e['_st']}"], 2),
                            }
                            for e in sorted(l3m_all, key=lambda x: (x["day"], x["mins"]))
                        ],
                    }
                    books.append(rec)
                    print(
                        f"  {rec['kind']} SLmax={sl_max:.0f} gap{gap}: "
                        f"{sl['n']}c/{sl['days']}d zero={sl['zero']} "
                        f"{sl['cpd_all']}/d SL={sl['avg_sl']} RR={sl['rr']} micros={len(chosen)}",
                        flush=True,
                    )
                    score = (sl["days"], sl["n"], sl["rr"], -sl["avg_sl"])
                    if best is None or score > best[0]:
                        best = (score, rec)

                # two-pass fill: take best dense pack, then add micros that only hit zero days
                if best and best[1]["sl_max"] == sl_max and best[1]["gap"] == gap:
                    pass

        # Explicit fill pass on overall best so far for this t1
        books.sort(key=lambda r: (-r["l3m"]["days"], -r["l3m"]["n"], -r["l3m"]["rr"]))
        if books:
            base_rec = books[0]
            print(
                f"  base best: {base_rec['l3m']['n']}c/{base_rec['l3m']['days']}d zero={base_rec['l3m']['zero']}",
                flush=True,
            )
            covered = set(base_rec["dayset"])
            zero_info = analyze_zero_days(test, h, l, c, t1, covered, sl_max=20.0)
            print(
                f"  zero-days={zero_info['n_zero']} oracle_wins_on_them={zero_info['oracle_wins_on_zero']}",
                flush=True,
            )
            print(f"  zero top pats: {zero_info['top_patterns'][:5]}", flush=True)

            # rebuild cells preferring structures common on zero days
            # fill: greedy again but prioritize cells that have l3m calls on zero days
            sl_max = base_rec["sl_max"]
            gap = base_rec["gap"]
            uniq = hunt_cells(cal_b, test_b, STYLES, gap, sl_max, min_cal=2, min_l3m_full=1)
            zero_set = set(zero_info["zero_days"])

            def zero_hits(r):
                return sum(1 for e in r["l3m_calls"] if e["day"] in zero_set)

            uniq_fill = sorted(uniq, key=lambda r: (-zero_hits(r), -r["l3m_n"], -r["cal_n"], r["avg_sl"]))
            # seed with base calls
            used_c = {(e["day"], e["mins"]) for e in [] }  # rebuild from base calls
            used_t = set()
            # reconstruct used from base_rec calls — need cal too; re-greedy all with zero-first order
            chosen, used_c, used_t = greedy(uniq_fill, gap, min_cal=2, min_l3m=1)
            cal_all = [{**e, "_st": r["st"], "_t1": t1} for r in chosen for e in r["cal_calls"]]
            l3m_all = [{**e, "_st": r["st"], "_t1": t1} for r in chosen for e in r["l3m_calls"]]
            if l3m_all and all(e.get(f"_ok_{e['_st']}") for e in cal_all + l3m_all):
                sc, sl = stats(cal_all, 271), stats(l3m_all, 64)
                fill_rec = {
                    "kind": "zero_fill_dense",
                    "t1": t1,
                    "sl_max": sl_max,
                    "gap": gap,
                    "n_micros": len(chosen),
                    "cal": {k: v for k, v in sc.items() if k != "dayset"},
                    "l3m": {k: v for k, v in sl.items() if k != "dayset"},
                    "dayset": sl["dayset"],
                    "zero_analysis": {
                        "n_zero_before": zero_info["n_zero"],
                        "oracle_on_zero": zero_info["oracle_wins_on_zero"],
                        "top_patterns": zero_info["top_patterns"][:8],
                        "feat_counts": zero_info["feat_counts"],
                        "sample_zero_days": zero_info["day_rows"][:8],
                    },
                    "l3m_calls": [
                        {
                            "day": e["day"],
                            "hm": e["hm"],
                            "decision": e["decision"],
                            "primary": e["primary"],
                            "family": e["family"],
                            "slot": e["slot"],
                            "st": e["_st"],
                            "sl": round(e[f"_sl_{e['_st']}"], 2),
                        }
                        for e in sorted(l3m_all, key=lambda x: (x["day"], x["mins"]))
                    ],
                    "top": [
                        {
                            "k": str(r["k"]),
                            "st": r["st"],
                            "cal_n": r["cal_n"],
                            "l3m_n": r["l3m_n"],
                            "avg_sl": round(r["avg_sl"], 2),
                            "zero_hits": zero_hits(r),
                        }
                        for r in uniq_fill[:15]
                    ],
                }
                print(
                    f"  zero-fill: {sl['n']}c/{sl['days']}d zero={sl['zero']} "
                    f"SL={sl['avg_sl']} RR={sl['rr']} micros={len(chosen)}",
                    flush=True,
                )
                books.insert(0, fill_rec)
                books.sort(key=lambda r: (-r["l3m"]["days"], -r["l3m"]["n"], -r["l3m"]["rr"]))

        champ = books[0] if books else None
        # also best by call count
        by_calls = sorted(books, key=lambda r: (-r["l3m"]["n"], -r["l3m"]["days"]))
        results["t1"][int(t1)] = {
            "best_coverage": champ,
            "best_calls": by_calls[0] if by_calls else None,
            "top": [
                {
                    "kind": b["kind"],
                    "sl_max": b["sl_max"],
                    "gap": b["gap"],
                    "l3m": b["l3m"],
                    "n_micros": b.get("n_micros"),
                }
                for b in books[:12]
            ],
            "improvement_vs_held15": None,
        }
        if champ and t1 == 15.0 and held15:
            results["t1"][15]["improvement_vs_held15"] = {
                "calls_delta": champ["l3m"]["n"] - held15["l3m"]["n"],
                "days_delta": champ["l3m"]["days"] - held15["l3m"]["days"],
                "zero_delta": champ["l3m"]["zero"] - held15["l3m"]["zero"],
            }
        if champ:
            print(
                f"  >> CHAMP T1={t1:.0f}: {champ['kind']} {champ['l3m']['n']}c/"
                f"{champ['l3m']['days']}d zero={champ['l3m']['zero']} RR={champ['l3m']['rr']}",
                flush=True,
            )

    # Report
    lines = [
        "# NIFTY 1m — **T1=15/20 deeper densify** (held books locked)",
        "",
        "**Not live.** Hold T1=10 and prior T1=15 more-calls logic. Deepen T1=15 & T1=20 for **more PATH@100% calls**.",
        "",
        "## Held baselines (locked)",
        "",
        "| Book | T1 | Calls | Days | Zero | /day | AvgSL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    if held10:
        lines.append(
            f"| HELD10 | 10 | {held10['l3m']['n']} | {held10['l3m']['days']} | 0 | "
            f"{held10['l3m']['cpd']} | {held10['l3m']['avg_sl']} |"
        )
    if held15:
        lines.append(
            f"| HELD15 | 15 | {held15['l3m']['n']} | {held15['l3m']['days']} | "
            f"{held15['l3m']['zero']} | {held15['l3m']['cpd_all']} | {held15['l3m']['avg_sl']} |"
        )

    lines += [
        "",
        "## New deep champions",
        "",
        "| T1 | Kind | SLmax | Gap | Calls | Days | Zero | /day-all | AvgSL | RR | vs HELD15 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for t1 in (15, 20):
        block = results["t1"].get(t1) or {}
        for label in ("best_coverage", "best_calls"):
            b = block.get(label)
            if not b:
                continue
            imp = ""
            if t1 == 15 and block.get("improvement_vs_held15") and label == "best_coverage":
                d = block["improvement_vs_held15"]
                imp = f"Δcalls {d['calls_delta']:+d} · Δdays {d['days_delta']:+d}"
            lines.append(
                f"| {t1} | {b['kind']} / {label} | {b['sl_max']} | {b['gap']} | {b['l3m']['n']} | "
                f"{b['l3m']['days']} | {b['l3m']['zero']} | {b['l3m']['cpd_all']} | "
                f"{b['l3m']['avg_sl']} | {b['l3m']['rr']} | {imp} |"
            )

    for t1 in (15, 20):
        b = (results["t1"].get(t1) or {}).get("best_coverage")
        if not b:
            continue
        lines += [
            "",
            f"## T1={t1} deep champion — `{b['kind']}`",
            "",
            f"- **{b['l3m']['n']} calls / {b['l3m']['days']} days** · zero **{b['l3m']['zero']}** · "
            f"{b['l3m']['cpd_all']}/day-all · avg SL **{b['l3m']['avg_sl']}** · RR **{b['l3m']['rr']}**",
            f"- SLmax={b['sl_max']} gap={b['gap']} micros={b.get('n_micros')}",
            f"- Hist: `{b['l3m']['hist']}`",
            "",
        ]
        za = b.get("zero_analysis")
        if za:
            lines += [
                "### Zero-day oracle autopsy (before fill)",
                "",
                f"- Zero days: **{za['n_zero_before']}** · oracle path-wins on them: **{za['oracle_on_zero']}**",
                f"- Top patterns on zero days: {za['top_patterns']}",
                f"- Feature hits: `{za['feat_counts']}`",
                "",
            ]
        lines += [
            "### Calls (sample)",
            "",
            "| Day | HM | Side | Pattern | Family | Slot | SL style | SL |",
            "|---|---|---|---|---|---|---|---:|",
        ]
        for e in b.get("l3m_calls", [])[:45]:
            lines.append(
                f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"{e.get('family','')} | {e.get('slot','')} | `{e['st']}` | {e['sl']} |"
            )
        if len(b.get("l3m_calls", [])) > 45:
            lines.append(f"| … | | | | | | | {len(b['l3m_calls'])-45} more |")

        lines += [
            "",
            f"### T1={t1} top packs",
            "",
            "| Kind | SLmax | Gap | Calls | Days | Zero | RR |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for x in (results["t1"].get(t1) or {}).get("top") or []:
            lines.append(
                f"| {x['kind']} | {x['sl_max']} | {x['gap']} | {x['l3m']['n']} | "
                f"{x['l3m']['days']} | {x['l3m']['zero']} | {x['l3m']['rr']} |"
            )

    lines += [
        "",
        "## Policy",
        "",
        "- **HELD10** T1=10 deep PATH — locked",
        "- **HELD15** prior more-calls T1=15 — locked; deeper pack is additive if better",
        f"- Pack: `{PACK_OUT}`",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # slim json (drop huge daysets duplication)
    slim = {
        "held10": results["held10"],
        "held15": results["held15"],
        "t1": {},
    }
    for t1, block in results["t1"].items():
        slim["t1"][t1] = {}
        for label in ("best_coverage", "best_calls"):
            b = block.get(label)
            if not b:
                continue
            slim["t1"][t1][label] = {
                k: b[k]
                for k in (
                    "kind",
                    "t1",
                    "sl_max",
                    "gap",
                    "n_micros",
                    "cal",
                    "l3m",
                    "l3m_calls",
                    "top",
                    "zero_analysis",
                )
                if k in b
            }
        slim["t1"][t1]["top"] = block.get("top")
        slim["t1"][t1]["improvement_vs_held15"] = block.get("improvement_vs_held15")

    REPORT_JSON.write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")
    (PACK_OUT / "summary.json").write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")

    # append pointer on morecalls report
    if HELD15.exists():
        # actually append to md morecalls
        more_md = OUT / "NIFTY_1M_SCALP_HIGHT_MORECALLS_100.md"
        if more_md.exists():
            md = more_md.read_text(encoding="utf-8")
            marker = "## Deeper T15/T20 densify"
            block = [
                "",
                "## Deeper T15/T20 densify",
                "",
                "Held T1=10 + prior T1=15. Deep pass: [`NIFTY_1M_SCALP_T15_T20_DEEPER.md`](NIFTY_1M_SCALP_T15_T20_DEEPER.md).",
            ]
            for t1 in (15, 20):
                b = (results["t1"].get(t1) or {}).get("best_coverage")
                if b:
                    block.append(
                        f"- T1={t1} deep: **{b['l3m']['n']} calls / {b['l3m']['days']} days** "
                        f"(zero {b['l3m']['zero']}) · RR {b['l3m']['rr']} · `{b['kind']}`"
                    )
            if marker in md:
                md = md.split(marker)[0].rstrip()
            more_md.write_text(md + "\n" + "\n".join(block) + "\n", encoding="utf-8")

    print(f"\nWrote {REPORT_MD}", flush=True)
    print("DONE t15/t20 deeper", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
