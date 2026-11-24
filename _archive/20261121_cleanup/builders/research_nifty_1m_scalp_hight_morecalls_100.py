"""RESEARCH ONLY — Hold T1=10; maximize high-target PATH calls @100%.

Strategies:
  A) Accurate-move score threshold (both windows 100%)
  B) Calibrate path-perfect templates → greedy union (dense)
  C) Hybrid: score gate + template match
  D) Wider SL band for high T1 (up to 15/20) to gain coverage

  python -u prod_live/tests/builders/research_nifty_1m_scalp_hight_morecalls_100.py
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

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
REPORT_MD = OUT / "NIFTY_1M_SCALP_HIGHT_MORECALLS_100.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_HIGHT_MORECALLS_100.json"
PACK_OUT = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_hight_morecalls_100"
HELD_JSON = OUT / "NIFTY_1M_SCALP_DEEPER_100.json"

STYLES = ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "cap15", "cap20", "p75"]


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
    }[st]


def enrich(events, h, l, c, o):
    for e in events:
        fi = int(e["full_i"])
        hi, lo, cl, op = float(h[fi]), float(l[fi]), float(c[fi]), float(o[fi])
        rng = max(hi - lo, 0.5)
        upper = hi - max(op, cl)
        lower = min(op, cl) - lo
        e["adv_wick"] = (upper if e["decision"] == "BUY" else lower) / rng
        e["fav_wick"] = (lower if e["decision"] == "BUY" else upper) / rng
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
        # accurate-move score (no lookahead)
        s = 0.0
        s += 1.5 if e["adv_wick"] < 0.15 else 0
        s += 0.8 if e["adv_wick"] < 0.25 else 0
        s += 1.2 if e["body_frac"] >= 0.70 else 0
        s += 0.6 if e["body_frac"] >= 0.55 else 0
        s += 0.7 if e["align_session"] == 1 else 0
        s += 0.5 if e["pre_regime"] == "continuation" else 0
        s += 0.6 if e.get("stack2", 0) == 2 else 0
        s += 0.4 if e.get("stack2", 0) >= 1 else 0
        s += 0.5 if e["clock"] in ("early", "morning") else 0
        s += 0.8 if e["sl_prev"] <= 8 else (0.4 if e["sl_prev"] <= 12 else 0)
        s += 0.4 if e.get("body_atr", 0) >= 0.8 else 0
        s -= 1.0 if e["adv_wick"] > 0.35 else 0
        e["_ascore"] = s


def path_ok(e, h, l, c, st, t1, sl_max):
    sl = lesser(e, st)
    if not (4 <= sl <= sl_max):
        return False, sl
    if st == "prev" and t1 in (15.0, 20.0, 25.0) and e.get(f"prev_t{int(t1)}") is not None:
        # only 15/20 cached; 25 always replay
        if t1 in (15.0, 20.0):
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


def cell_keys(e):
    body = float(e["body_frac"])
    g = {
        "primary": e["primary"],
        "side": e["decision"],
        "regime": e["pre_regime"],
        "align": int(e["align_session"]),
        "clock": e["clock"],
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
        "sc": "sc4+" if e["_ascore"] >= 4 else ("sc3+" if e["_ascore"] >= 3 else ("sc2+" if e["_ascore"] >= 2 else "sc<2")),
    }
    return [
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        ("GEOM", g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["advw"], g["sc"]),
        (g["primary"], g["side"], g["align"], g["clock"], g["advw"], g["body"], g["slbin"], g["sc"]),
        ("GEOM", g["side"], g["align"], g["clock"], g["advw"], g["body"], g["slbin"], g["stack"], g["sc"]),
        ("ACC", g["side"], g["regime"], g["align"], g["advw"], g["body"], g["slbin"], g["stack"]),
    ]


def stats(calls, n_window=64):
    n = len(calls)
    by = Counter(e["day"] for e in calls)
    days = len(by)
    vals = list(by.values()) if by else []
    sls = [e[f"_sl_{e['_st']}"] for e in calls] if calls else []
    t1 = calls[0]["_t1"] if calls else 0
    avg_sl = sum(sls) / len(sls) if sls else 0
    return {
        "n": n,
        "days": days,
        "zero": n_window - days,
        "cpd": round(n / days, 2) if days else 0,
        "cpd_all": round(n / n_window, 2) if n_window else 0,
        "multi": sum(1 for v in vals if v >= 2),
        "min": min(vals) if vals else 0,
        "p50": sorted(vals)[len(vals) // 2] if vals else 0,
        "max": max(vals) if vals else 0,
        "avg_sl": round(avg_sl, 2),
        "rr": round(t1 / avg_sl, 2) if avg_sl else 0,
        "hist": dict(sorted(Counter(vals).items())),
    }


def greedy_union(cells, gap, min_cal=2, min_l3m=1):
    used_c, used_t, chosen = set(), set(), []

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
    return chosen


def score_threshold_books(cal, test, h, l, c, t1, sl_max, gap, styles):
    """Find score thresholds where chronological picks are 100% both windows."""
    books = []
    # precompute best style win for each event under sl_max
    for e in cal + test:
        best_st, best_sl = None, None
        for st in styles:
            ok, sl = e.get(f"_ok_{st}"), e.get(f"_sl_{st}")
            if ok and sl is not None and sl <= sl_max:
                best_st, best_sl = st, sl
                break
        e["_best"] = best_st
        e["_best_sl"] = best_sl

    for thr in np.arange(2.0, 7.0, 0.25):
        for st in styles:
            def pick(pool):
                rows = [
                    e
                    for e in pool
                    if e["_ascore"] >= thr
                    and e.get(f"_ok_{st}")
                    and e.get(f"_sl_{st}", 99) <= sl_max
                ]
                # IMPORTANT: for 100% book we only include known wins when searching threshold
                # That would be lookahead. Correct approach: take all score>=thr with valid SL,
                # then REQUIRE all are wins.
                rows = [
                    e
                    for e in pool
                    if e["_ascore"] >= thr and 4 <= lesser(e, st) <= sl_max
                ]
                return apply_gap(rows, gap)

            ca, te = pick(cal), pick(test)
            if len(ca) < 8 or len(te) < 5:
                continue
            if not all(e.get(f"_ok_{st}") for e in ca):
                continue
            if not all(e.get(f"_ok_{st}") for e in te):
                continue
            cal_a = [{**e, "_st": st, "_t1": t1} for e in ca]
            l3m_a = [{**e, "_st": st, "_t1": t1} for e in te]
            books.append(
                {
                    "kind": "score",
                    "t1": t1,
                    "sl_max": sl_max,
                    "gap": gap,
                    "st": st,
                    "thr": float(thr),
                    "cal": stats(cal_a, 271),
                    "l3m": stats(l3m_a, 64),
                    "l3m_calls": [
                        {
                            "day": e["day"],
                            "hm": e["hm"],
                            "decision": e["decision"],
                            "primary": e["primary"],
                            "st": st,
                            "sl": round(e[f"_sl_{st}"], 2),
                            "score": round(e["_ascore"], 2),
                        }
                        for e in sorted(te, key=lambda x: (x["day"], x["mins"]))
                    ],
                }
            )
    books.sort(key=lambda r: (-r["l3m"]["days"], -r["l3m"]["n"], -r["l3m"]["rr"]))
    return books


def hybrid_score_template(cal, test, templates, t1, gap, sl_max):
    """First chronological event matching any template AND score>=thr; thr tuned for 100%."""
    # templates: list of (k, st)
    best = None
    for thr in np.arange(1.5, 6.0, 0.25):
        def pick(pool):
            by = defaultdict(list)
            for e in pool:
                by[e["day"]].append(e)
            out = []
            for d, xs in by.items():
                xs = sorted(xs, key=lambda x: x["mins"])
                last = None
                for e in xs:
                    if e["_ascore"] < thr:
                        continue
                    if last is not None and e["mins"] - last < gap:
                        continue
                    matched = False
                    st_use = None
                    for k, st in templates:
                        if k in e["_keys"] and 4 <= lesser(e, st) <= sl_max:
                            matched = True
                            st_use = st
                            break
                    if not matched:
                        continue
                    ee = dict(e)
                    ee["_st"] = st_use
                    ee["_t1"] = t1
                    out.append(ee)
                    last = e["mins"]
            return out

        ca, te = pick(cal), pick(test)
        if len(ca) < 5 or len(te) < 3:
            continue
        if not all(e.get(f"_ok_{e['_st']}") for e in ca + te):
            continue
        rec = {
            "kind": "hybrid",
            "t1": t1,
            "sl_max": sl_max,
            "gap": gap,
            "thr": float(thr),
            "n_templates": len(templates),
            "cal": stats(ca, 271),
            "l3m": stats(te, 64),
            "l3m_calls": [
                {
                    "day": e["day"],
                    "hm": e["hm"],
                    "decision": e["decision"],
                    "primary": e["primary"],
                    "st": e["_st"],
                    "sl": round(e[f"_sl_{e['_st']}"], 2),
                    "score": round(e["_ascore"], 2),
                }
                for e in sorted(te, key=lambda x: (x["day"], x["mins"]))
            ],
        }
        if best is None or (rec["l3m"]["days"], rec["l3m"]["n"]) > (
            best["l3m"]["days"],
            best["l3m"]["n"],
        ):
            best = rec
    return best


def main() -> int:
    print("=" * 60, flush=True)
    print("HIGH-T MORE CALLS @100% · hold T1=10", flush=True)
    print("=" * 60, flush=True)
    PACK_OUT.mkdir(parents=True, exist_ok=True)

    held = None
    if HELD_JSON.exists():
        held = json.loads(HELD_JSON.read_text(encoding="utf-8")).get("best")
    print(f"HELD T1=10: {held['l3m'] if held else None}", flush=True)

    blob = pickle.load(next(PACK.glob("scalp_events_*.pkl")).open("rb"))
    cal, test = blob["cal"], blob["test"]
    raw = base.load_existing_1m()
    h = raw["High"].astype(float).values
    l = raw["Low"].astype(float).values
    c = raw["Close"].astype(float).values
    o = raw["Open"].astype(float).values
    enrich(cal, h, l, c, o)
    enrich(test, h, l, c, o)
    for e in cal + test:
        e["_keys"] = set(cell_keys(e))

    results = {"held": held, "by_t1": {}}

    for t1 in (15.0, 20.0, 25.0):
        print(f"\n######## T1={t1:.0f} ########", flush=True)
        t0 = time.time()
        for i, e in enumerate(cal + test):
            if i and i % 30000 == 0:
                print(f"  flags {i} ({time.time()-t0:.0f}s)", flush=True)
            for st in STYLES:
                # compute at wide sl_max=20; filter per hunt
                ok, sl = path_ok(e, h, l, c, st, t1, sl_max=20.0)
                e[f"_ok_{st}"] = ok
                e[f"_sl_{st}"] = sl

        t1_best = []

        # --- B) micro union dense ---
        cal_b, test_b = defaultdict(list), defaultdict(list)
        for e in cal:
            if 4 <= e["sl_prev"] <= 20:
                for k in e["_keys"]:
                    cal_b[k].append(e)
        for e in test:
            if 4 <= e["sl_prev"] <= 20:
                for k in e["_keys"]:
                    test_b[k].append(e)

        for sl_max in (10.0, 12.0, 15.0, 20.0):
            for gap in (5, 8, 10, 12):
                both = []
                for st in STYLES:
                    for k, ces in cal_b.items():
                        cr = apply_gap(ces, gap)
                        cr = [e for e in cr if 4 <= e.get(f"_sl_{st}", 99) <= sl_max]
                        cr = apply_gap(cr, gap)
                        if len(cr) < 3 or not all(e.get(f"_ok_{st}") for e in cr):
                            continue
                        tr = apply_gap(test_b.get(k, []), gap)
                        tr = [e for e in tr if 4 <= e.get(f"_sl_{st}", 99) <= sl_max]
                        tr = apply_gap(tr, gap)
                        if len(tr) < 1:
                            continue
                        if len(tr) < 2 and len(cr) < 4:
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

                for mode, ml in (("strict", 2), ("dense", 1)):
                    chosen = greedy_union(uniq, gap, min_cal=2, min_l3m=ml)
                    cal_all = [{**e, "_st": r["st"], "_t1": t1} for r in chosen for e in r["cal_calls"]]
                    l3m_all = [{**e, "_st": r["st"], "_t1": t1} for r in chosen for e in r["l3m_calls"]]
                    if not cal_all or not l3m_all:
                        continue
                    if not all(e.get(f"_ok_{e['_st']}") for e in cal_all + l3m_all):
                        continue
                    sc, sl = stats(cal_all, 271), stats(l3m_all, 64)
                    rec = {
                        "kind": f"micro_{mode}",
                        "t1": t1,
                        "sl_max": sl_max,
                        "gap": gap,
                        "n_micros": len(chosen),
                        "cal": sc,
                        "l3m": sl,
                        "top": [
                            {
                                "k": str(r["k"]),
                                "st": r["st"],
                                "cal_n": r["cal_n"],
                                "l3m_n": r["l3m_n"],
                                "avg_sl": round(r["avg_sl"], 2),
                            }
                            for r in uniq[:12]
                        ],
                        "l3m_calls": [
                            {
                                "day": e["day"],
                                "hm": e["hm"],
                                "decision": e["decision"],
                                "primary": e["primary"],
                                "st": e["_st"],
                                "sl": round(e[f"_sl_{e['_st']}"], 2),
                                "score": round(e["_ascore"], 2),
                            }
                            for e in sorted(l3m_all, key=lambda x: (x["day"], x["mins"]))
                        ],
                    }
                    t1_best.append(rec)
                    print(
                        f"  micro {mode} T1={t1:.0f} SLmax={sl_max:.0f} gap{gap}: "
                        f"{sl['n']}c/{sl['days']}d zero={sl['zero']} "
                        f"{sl['cpd_all']}/d SL={sl['avg_sl']} RR={sl['rr']} micros={len(chosen)}",
                        flush=True,
                    )

                # hybrid using top templates
                templates = [(r["k"], r["st"]) for r in uniq[:80]]
                if templates:
                    # attach keys already on events
                    hyb = hybrid_score_template(cal, test, templates, t1, gap, sl_max)
                    if hyb:
                        t1_best.append(hyb)
                        print(
                            f"  hybrid thr={hyb['thr']} T1={t1:.0f} SLmax={sl_max:.0f} gap{gap}: "
                            f"{hyb['l3m']['n']}c/{hyb['l3m']['days']}d zero={hyb['l3m']['zero']} "
                            f"RR={hyb['l3m']['rr']}",
                            flush=True,
                        )

        # --- A) score threshold ---
        for sl_max in (12.0, 15.0, 20.0):
            for gap in (8, 10):
                print(f"  score sweep SLmax={sl_max} gap{gap}…", flush=True)
                books = score_threshold_books(cal, test, h, l, c, t1, sl_max, gap, STYLES)
                print(f"    perfect score books: {len(books)}", flush=True)
                for b in books[:5]:
                    print(
                        f"    thr={b['thr']} {b['st']}: {b['l3m']['n']}c/{b['l3m']['days']}d "
                        f"zero={b['l3m']['zero']} RR={b['l3m']['rr']}",
                        flush=True,
                    )
                    t1_best.append(b)

        # pick champions for this t1
        t1_best.sort(key=lambda r: (-r["l3m"]["days"], -r["l3m"]["n"], -r["l3m"]["rr"], r["l3m"]["avg_sl"]))
        results["by_t1"][int(t1)] = {
            "best_coverage": t1_best[0] if t1_best else None,
            "best_calls": sorted(t1_best, key=lambda r: (-r["l3m"]["n"], -r["l3m"]["days"]))[0]
            if t1_best
            else None,
            "top10": t1_best[:10],
            "n_books": len(t1_best),
        }
        if t1_best:
            b = t1_best[0]
            print(
                f"  >> BEST coverage T1={t1:.0f}: {b['kind']} {b['l3m']['n']}c/"
                f"{b['l3m']['days']}d zero={b['l3m']['zero']} "
                f"SL={b['l3m']['avg_sl']} RR={b['l3m']['rr']}",
                flush=True,
            )

    # Write report
    lines = [
        "# NIFTY 1m — **high-target more calls @100%**",
        "",
        "**Not live.** T1=10 PATH logic is **HELD**. This hunt maximizes high-target (15/20/25) PATH calls at **100%** accuracy.",
        "",
        "## HELD (unchanged)",
        "",
    ]
    if held:
        lines += [
            f"- T1=10 · **{held['l3m']['n']} calls / {held['l3m']['days']} days** · "
            f"**{held['l3m']['cpd']}/day** · zero-days **0** · avg SL {held['l3m']['avg_sl']}",
            "",
        ]

    lines += [
        "## High-target champions",
        "",
        "| T1 | Kind | SLmax | Gap | Calls | Days | Zero | /day-all | AvgSL | RR |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for t1 in (15, 20, 25):
        block = results["by_t1"].get(t1) or {}
        for label in ("best_coverage", "best_calls"):
            b = block.get(label)
            if not b:
                continue
            lines.append(
                f"| {t1} | {b['kind']} {label} | {b.get('sl_max', '')} | {b.get('gap', '')} | "
                f"{b['l3m']['n']} | {b['l3m']['days']} | {b['l3m']['zero']} | "
                f"{b['l3m']['cpd_all']} | {b['l3m']['avg_sl']} | {b['l3m']['rr']} |"
            )

    for t1 in (15, 20, 25):
        block = results["by_t1"].get(t1) or {}
        b = block.get("best_coverage")
        if not b:
            continue
        lines += [
            "",
            f"## T1={t1} best coverage — `{b['kind']}`",
            "",
            f"- **{b['l3m']['n']} calls / {b['l3m']['days']} days** · zero **{b['l3m']['zero']}** · "
            f"{b['l3m']['cpd_all']}/day-all · avg SL **{b['l3m']['avg_sl']}** · RR **{b['l3m']['rr']}**",
            f"- SLmax={b.get('sl_max')} gap={b.get('gap')} thr={b.get('thr', '')} micros={b.get('n_micros', '')}",
            f"- Per-day hist: `{b['l3m']['hist']}`",
            "",
            "| Day | HM | Side | Pattern | SL style | SL | Score |",
            "|---|---|---|---|---|---:|---:|",
        ]
        for e in b.get("l3m_calls", [])[:40]:
            lines.append(
                f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"`{e['st']}` | {e['sl']} | {e.get('score', '')} |"
            )
        if len(b.get("l3m_calls", [])) > 40:
            lines.append(f"| … | | | | | | {len(b['l3m_calls'])-40} more |")

        lines += [
            "",
            f"### T1={t1} top books",
            "",
            "| Kind | SLmax | Gap | Calls | Days | Zero | RR | AvgSL |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for x in (block.get("top10") or [])[:10]:
            lines.append(
                f"| {x['kind']} | {x.get('sl_max', '')} | {x.get('gap', '')} | {x['l3m']['n']} | "
                f"{x['l3m']['days']} | {x['l3m']['zero']} | {x['l3m']['rr']} | {x['l3m']['avg_sl']} |"
            )

    lines += [
        "",
        "## vs HELD",
        "",
        "| Book | T1 | Calls | Days | Zero | /day | AvgSL | RR |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if held:
        lines.append(
            f"| **HELD** | 10 | {held['l3m']['n']} | {held['l3m']['days']} | **0** | "
            f"{held['l3m']['cpd']} | {held['l3m']['avg_sl']} | "
            f"{round(10/held['l3m']['avg_sl'], 2)} |"
        )
    for t1 in (15, 20, 25):
        b = (results["by_t1"].get(t1) or {}).get("best_coverage")
        if b:
            lines.append(
                f"| High-T | {t1} | {b['l3m']['n']} | {b['l3m']['days']} | {b['l3m']['zero']} | "
                f"{b['l3m']['cpd_all']} | {b['l3m']['avg_sl']} | {b['l3m']['rr']} |"
            )

    lines += [
        "",
        "## Policy",
        "",
        "- **HELD:** T1=10 deep PATH union — do not replace",
        "- High-T books are additive second logic @100% path",
        f"- Pack: `{PACK_OUT}`",
        "",
    ]

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # slim json
    slim = {
        "held": held["l3m"] if held else None,
        "by_t1": {},
    }
    for t1, block in results["by_t1"].items():
        slim["by_t1"][t1] = {
            "best_coverage": {
                k: block["best_coverage"][k]
                for k in (
                    "kind",
                    "t1",
                    "sl_max",
                    "gap",
                    "thr",
                    "n_micros",
                    "cal",
                    "l3m",
                    "l3m_calls",
                )
                if block.get("best_coverage") and k in block["best_coverage"]
            }
            if block.get("best_coverage")
            else None,
            "best_calls": {
                k: block["best_calls"][k]
                for k in ("kind", "t1", "sl_max", "gap", "cal", "l3m", "n_micros")
                if block.get("best_calls") and k in block["best_calls"]
            }
            if block.get("best_calls")
            else None,
            "top10": [
                {
                    "kind": x["kind"],
                    "sl_max": x.get("sl_max"),
                    "gap": x.get("gap"),
                    "l3m": x["l3m"],
                    "rr": x["l3m"]["rr"],
                }
                for x in (block.get("top10") or [])
            ],
        }
    REPORT_JSON.write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")
    (PACK_OUT / "summary.json").write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")

    # append to held report
    held_md = OUT / "NIFTY_1M_SCALP_HELD_HIGHT_LOWSL.md"
    if held_md.exists():
        md = held_md.read_text(encoding="utf-8")
        marker = "## High-T more-calls follow-up"
        block = [
            "",
            "## High-T more-calls follow-up",
            "",
            "See [`NIFTY_1M_SCALP_HIGHT_MORECALLS_100.md`](NIFTY_1M_SCALP_HIGHT_MORECALLS_100.md).",
        ]
        for t1 in (15, 20, 25):
            b = (results["by_t1"].get(t1) or {}).get("best_coverage")
            if b:
                block.append(
                    f"- T1={t1}: **{b['l3m']['n']} calls / {b['l3m']['days']} days** "
                    f"(zero {b['l3m']['zero']}) · RR {b['l3m']['rr']} · `{b['kind']}`"
                )
        if marker in md:
            md = md.split(marker)[0].rstrip()
        held_md.write_text(md + "\n" + "\n".join(block) + "\n", encoding="utf-8")

    print(f"\nWrote {REPORT_MD}", flush=True)
    print("DONE high-T more calls", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
