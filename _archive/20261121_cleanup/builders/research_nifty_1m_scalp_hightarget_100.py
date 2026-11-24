"""RESEARCH ONLY — Scalp multi-call @100% with HIGH targets (T1 15–40).

Same structure as deep PATH union: wick/ATR/stack micros, prev/lesser SL 4–12,
gap sweep, both-window 100% path (T1 before SL).

  python -u prod_live/tests/builders/research_nifty_1m_scalp_hightarget_100.py
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import defaultdict
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
REPORT_MD = OUT / "NIFTY_1M_SCALP_HIGHTARGET_100.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_HIGHTARGET_100.json"
PACK_OUT = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_hightarget_100"

T1S = [15.0, 20.0, 25.0, 30.0, 35.0, 40.0]
STYLES = ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "p75"]
# allow slightly wider SL for bigger targets (still structural)
SL_MAX = 20.0


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


def path_ok(e, h, l, c, st, t1, sl_max=SL_MAX):
    sl = lesser(e, st)
    if not (4 <= sl <= sl_max):
        return False, sl
    # cache hits for common T1s
    if st == "prev" and t1 in (15.0, 20.0) and e.get(f"prev_t{int(t1)}") is not None:
        return e[f"prev_t{int(t1)}"] == "win", sl
    if st == "sig" and t1 in (15.0, 20.0) and e.get(f"sig_t{int(t1)}") is not None:
        return e[f"sig_t{int(t1)}"] == "win", sl
    win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], float(sl), float(t1))
    return (win and out == "t1"), sl


def cell_keys(e):
    body = float(e["body_frac"])
    g = {
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
        "advw": "adv_lo"
        if e.get("adv_wick", 0) < 0.15
        else ("adv_mid" if e.get("adv_wick", 0) < 0.35 else "adv_hi"),
        "batr": "ba>0.8"
        if e.get("body_atr", 0) >= 0.8
        else ("ba>0.5" if e.get("body_atr", 0) >= 0.5 else "ba<0.5"),
        "stack": f"st{e.get('stack2', 0)}",
    }
    return [
        (
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
        ),
        (
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
        ),
        (
            g["primary"],
            g["side"],
            g["regime"],
            g["align"],
            g["clock"],
            g["body"],
            g["slbin"],
            g["advw"],
        ),
        (
            g["primary"],
            g["side"],
            g["align"],
            g["clock"],
            g["advw"],
            g["batr"],
            g["slbin"],
            g["rsi"],
        ),
    ]


def apply_gap(rows, gap):
    last, out = {}, []
    for e in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        prev = last.get(e["day"])
        if prev is not None and e["mins"] - prev < gap:
            continue
        out.append(e)
        last[e["day"]] = e["mins"]
    return out


def greedy(cells, gap):
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
    sls = [e[f"_sl_{e['_st']}"] for e in calls]
    return {
        "n": n,
        "days": days,
        "cpd": round(n / days, 2) if days else 0,
        "multi": sum(1 for v in by.values() if v >= 2),
        "max": max(by.values()) if by else 0,
        "avg_sl": round(sum(sls) / len(sls), 2) if sls else 0,
        "avg_rr": round((sum(e["_t1"] for e in calls) / n) / (sum(sls) / n), 2)
        if n and sls and sum(sls) > 0
        else 0,
    }


def mfe_union(cal, test, t1, gap, sl_cap=12.0):
    """Target-reached both-100 cells (MFE>=T1), SL=insurance."""
    styles = ["prev", "cap10", "cap12", "cap15", "cap20"]

    def tags(e):
        body = float(e["body_frac"])
        return (
            e["primary"],
            e["decision"],
            e["pre_regime"],
            int(e["align_session"]),
            e["clock"],
            "b70+" if body >= 0.7 else ("b45+" if body >= 0.45 else "b<45"),
            "sl<=10" if e["sl_prev"] <= 10 else ("sl<=15" if e["sl_prev"] <= 15 else "sl<=20"),
            "rsi_lo" if e["rsi_14"] < 40 else ("rsi_hi" if e["rsi_14"] > 60 else "rsi_mid"),
        )

    cal_b, test_b = defaultdict(list), defaultdict(list)
    for e in cal:
        if 4 <= e["sl_prev"] <= 20:
            cal_b[tags(e)].append(e)
    for e in test:
        if 4 <= e["sl_prev"] <= 20:
            test_b[tags(e)].append(e)

    cells = []
    for k, ces in cal_b.items():
        cr = apply_gap(ces, gap)
        if len(cr) < 3 or any(e["mfe"] < t1 for e in cr):
            continue
        tr = apply_gap(test_b.get(k, []), gap)
        if len(tr) < 2 or any(e["mfe"] < t1 for e in tr):
            continue
        avg = sum(min(e["sl_prev"], sl_cap) for e in tr) / len(tr)
        cells.append(
            {
                "k": k,
                "st": "prev",
                "cal_calls": cr,
                "l3m_calls": tr,
                "cal_n": len(cr),
                "l3m_n": len(tr),
                "avg_sl": avg,
            }
        )
    cells.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"], r["avg_sl"]))
    # greedy by (day,mins)
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
        if len(ck) < 2 or len(tk) < 2:
            continue
        chosen.append({**r, "cal_calls": ck, "l3m_calls": tk})
        for e in ck:
            used_c.add((e["day"], e["mins"]))
        for e in tk:
            used_t.add((e["day"], e["mins"]))
    cal_all = [{**e, "_st": "prev", "_t1": t1, f"_sl_prev": min(e["sl_prev"], sl_cap)} for r in chosen for e in r["cal_calls"]]
    l3m_all = [{**e, "_st": "prev", "_t1": t1, f"_sl_prev": min(e["sl_prev"], sl_cap)} for r in chosen for e in r["l3m_calls"]]
    # patch sl field name for stats
    for e in cal_all + l3m_all:
        e["_sl_prev"] = min(float(e["sl_prev"]), sl_cap)
    return chosen, cal_all, l3m_all


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · SCALP HIGH-TARGET 100%", flush=True)
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
    enrich(cal, h, l, c, o)
    enrich(test, h, l, c, o)

    styles = STYLES + ["cap15", "cap20"]
    scoreboard = []
    champions = {}

    # Oracle density per T1
    print("\n[A] Oracle path density (any style, SL 4–20)…", flush=True)
    oracle = {}
    for t1 in T1S:
        for name, pool in (("cal", cal), ("l3m", test)):
            by = defaultdict(list)
            for e in pool:
                hit = False
                best_sl = None
                for st in styles:
                    ok, sl = path_ok(e, h, l, c, st, t1, sl_max=20)
                    if ok:
                        hit = True
                        best_sl = sl
                        break
                if hit:
                    by[e["day"]].append((e["mins"], best_sl))
            total = 0
            multi = 0
            max_d = 0
            for d, xs in by.items():
                xs = sorted(xs)
                kept = []
                last = None
                for mins, sl in xs:
                    if last is not None and mins - last < 8:
                        continue
                    kept.append(sl)
                    last = mins
                total += len(kept)
                if len(kept) >= 2:
                    multi += 1
                max_d = max(max_d, len(kept))
            days = len(by)
            oracle[f"{name}_t{int(t1)}"] = {
                "n": total,
                "days": days,
                "cpd": round(total / days, 2) if days else 0,
                "multi": multi,
                "max": max_d,
            }
        print(
            f"  T1={t1:.0f}: cal {oracle[f'cal_t{int(t1)}']['n']}c/"
            f"{oracle[f'cal_t{int(t1)}']['days']}d ({oracle[f'cal_t{int(t1)}']['cpd']}/d) · "
            f"l3m {oracle[f'l3m_t{int(t1)}']['n']}c/{oracle[f'l3m_t{int(t1)}']['days']}d "
            f"({oracle[f'l3m_t{int(t1)}']['cpd']}/d)",
            flush=True,
        )

    cal_b = defaultdict(list)
    test_b = defaultdict(list)
    for e in cal:
        if 4 <= e["sl_prev"] <= 20:
            for k in cell_keys(e):
                cal_b[k].append(e)
    for e in test:
        if 4 <= e["sl_prev"] <= 20:
            for k in cell_keys(e):
                test_b[k].append(e)

    for t1 in T1S:
        print(f"\n[B] PATH hunt T1={t1:.0f}…", flush=True)
        t0 = time.time()
        for i, e in enumerate(cal + test):
            if i and i % 30000 == 0:
                print(f"    flags {i} ({time.time()-t0:.0f}s)", flush=True)
            for st in styles:
                ok, sl = path_ok(e, h, l, c, st, t1, sl_max=20)
                e[f"_ok_{st}"] = ok
                e[f"_sl_{st}"] = sl

        best_t = None
        for gap in (8, 10, 15, 20):
            for sl_max in (12.0, 15.0, 20.0):
                both = []
                for st in styles:
                    for k, ces in cal_b.items():
                        cal_rows = apply_gap(ces, gap)
                        if len(cal_rows) < 3:
                            continue
                        # filter SL max
                        cal_rows = [e for e in cal_rows if 4 <= e[f"_sl_{st}"] <= sl_max]
                        cal_rows = apply_gap(cal_rows, gap)
                        if len(cal_rows) < 3:
                            continue
                        if not all(e.get(f"_ok_{st}") for e in cal_rows):
                            continue
                        tes = apply_gap(test_b.get(k, []), gap)
                        tes = [e for e in tes if 4 <= e[f"_sl_{st}"] <= sl_max]
                        tes = apply_gap(tes, gap)
                        if len(tes) < 2:
                            continue
                        if not all(e.get(f"_ok_{st}") for e in tes):
                            continue
                        avg = sum(e[f"_sl_{st}"] for e in tes) / len(tes)
                        both.append(
                            {
                                "k": k,
                                "st": st,
                                "cal_calls": cal_rows,
                                "l3m_calls": tes,
                                "cal_n": len(cal_rows),
                                "l3m_n": len(tes),
                                "avg_sl": avg,
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
                chosen = greedy(uniq, gap)
                cal_all, l3m_all = [], []
                for r in chosen:
                    for e in r["cal_calls"]:
                        cal_all.append({**e, "_st": r["st"], "_t1": t1})
                    for e in r["l3m_calls"]:
                        l3m_all.append({**e, "_st": r["st"], "_t1": t1})
                ok = all(e.get(f"_ok_{e['_st']}") for e in cal_all + l3m_all)
                sc, sl = stats(cal_all), stats(l3m_all)
                rr = round(t1 / sl["avg_sl"], 2) if sl["avg_sl"] else 0
                print(
                    f"  T1={t1:.0f} gap{gap} SLmax{sl_max:.0f}: cells={len(uniq)} micros={len(chosen)} "
                    f"cal {sc['n']}/{sc['days']}d · l3m {sl['n']}/{sl['days']}d "
                    f"({sl['cpd']}/d) SL={sl['avg_sl']} RR~{rr} ok={ok}",
                    flush=True,
                )
                rec = {
                    "mode": "path",
                    "t1": t1,
                    "gap": gap,
                    "sl_max": sl_max,
                    "ok": ok,
                    "n_cells": len(uniq),
                    "n_micros": len(chosen),
                    "cal": sc,
                    "l3m": sl,
                    "rr": rr,
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
                            "t1": t1,
                            "mfe": round(e["mfe"], 1),
                        }
                        for e in sorted(l3m_all, key=lambda x: (x["day"], x["mins"]))
                    ],
                }
                scoreboard.append(rec)
                if ok and sl["n"] > 0:
                    score = (sl["n"], sc["n"], rr, -sl["avg_sl"])
                    if best_t is None or score > best_t[0]:
                        best_t = (score, rec)
        if best_t:
            champions[f"path_t{int(t1)}"] = best_t[1]
            b = best_t[1]
            print(
                f"  >> BEST T1={t1:.0f}: l3m {b['l3m']['n']}c/{b['l3m']['days']}d "
                f"({b['l3m']['cpd']}/d) RR~{b['rr']} gap{b['gap']} SLmax{b['sl_max']}",
                flush=True,
            )

        # MFE high-target union
        print(f"  MFE union T1={t1:.0f}…", flush=True)
        for gap in (8, 15):
            ch, ca, la = mfe_union(cal, test, t1, gap, sl_cap=15.0)
            for e in ca + la:
                e["_st"] = "prev"
                e["_t1"] = t1
            sc = {
                "n": len(ca),
                "days": len({e["day"] for e in ca}),
                "cpd": round(len(ca) / max(len({e["day"] for e in ca}), 1), 2),
                "multi": 0,
                "max": 0,
                "avg_sl": round(sum(e["_sl_prev"] for e in ca) / len(ca), 2) if ca else 0,
            }
            by = defaultdict(int)
            for e in la:
                by[e["day"]] += 1
            sl = {
                "n": len(la),
                "days": len(by),
                "cpd": round(len(la) / max(len(by), 1), 2),
                "multi": sum(1 for v in by.values() if v >= 2),
                "max": max(by.values()) if by else 0,
                "avg_sl": round(sum(e["_sl_prev"] for e in la) / len(la), 2) if la else 0,
            }
            path_w = (
                sum(1 for e in la if e.get("prev_t10") == "win" or e["mfe"] >= t1)
                / len(la)
                if la
                else 0
            )
            # real path at this t1 with prev sl
            pw = 0
            for e in la:
                ok, _ = path_ok(e, h, l, c, "prev", t1, sl_max=20)
                pw += int(ok)
            pw = 100 * pw / len(la) if la else 0
            print(
                f"    MFE gap{gap}: cal {sc['n']}/{sc['days']}d · l3m {sl['n']}/{sl['days']}d "
                f"({sl['cpd']}/d) SL={sl['avg_sl']} pathWin@{t1:.0f}={pw:.0f}%",
                flush=True,
            )
            mrec = {
                "mode": "mfe",
                "t1": t1,
                "gap": gap,
                "ok": True,
                "cal": sc,
                "l3m": sl,
                "path_win_pct": round(pw, 1),
                "n_micros": len(ch),
                "rr": round(t1 / sl["avg_sl"], 2) if sl["avg_sl"] else 0,
            }
            scoreboard.append(mrec)
            key = f"mfe_t{int(t1)}"
            if key not in champions or sl["n"] > champions[key]["l3m"]["n"]:
                champions[key] = mrec

    # Write report
    path_best = sorted(
        [v for k, v in champions.items() if k.startswith("path_")],
        key=lambda r: (-r["l3m"]["n"], -r["rr"]),
    )
    lines = [
        "# NIFTY 1m — **high-target scalp 100%**",
        "",
        "**Not live.** Same PATH micro-union logic as deep scalp, with **T1 = 15 / 20 / 25 / 30 / 35 / 40**.",
        "",
        "- SL = prev candle / lesser caps (8–20) · gap 8–20m",
        "- Win = T1 prints **before** structure SL (path)",
        "- Also report MFE (target-reached) density for comparison",
        "",
        "## Oracle ceiling (path · any structure SL 4–20 · gap8)",
        "",
        "| T1 | Cal calls | Cal /day | L3m calls | L3m /day |",
        "|---:|---:|---:|---:|---:|",
    ]
    for t1 in T1S:
        oc, ol = oracle[f"cal_t{int(t1)}"], oracle[f"l3m_t{int(t1)}"]
        lines.append(
            f"| {int(t1)} | {oc['n']} | {oc['cpd']} | {ol['n']} | {ol['cpd']} |"
        )

    lines += [
        "",
        "## Best PATH books by target (both windows 100%)",
        "",
        "| T1 | Gap | SLmax | Cal calls | Cal days | L3m calls | L3m days | /day | Multi | AvgSL | RR | Micros |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for t1 in T1S:
        key = f"path_t{int(t1)}"
        if key not in champions:
            lines.append(f"| {int(t1)} | — | — | 0 | 0 | 0 | 0 | 0 | 0 | — | — | 0 |")
            continue
        b = champions[key]
        lines.append(
            f"| {int(t1)} | {b['gap']} | {b['sl_max']} | {b['cal']['n']} | {b['cal']['days']} | "
            f"{b['l3m']['n']} | {b['l3m']['days']} | {b['l3m']['cpd']} | {b['l3m']['multi']} | "
            f"{b['l3m']['avg_sl']} | {b['rr']} | {b['n_micros']} |"
        )

    if path_best:
        b = path_best[0]
        lines += [
            "",
            f"## ★ PATH champion among high targets — T1={int(b['t1'])}",
            "",
            f"- Gap **{b['gap']}** · SLmax **{b['sl_max']}** · micros **{b['n_micros']}**",
            f"- Calibrate: **{b['cal']['n']} calls / {b['cal']['days']} days** ({b['cal']['cpd']}/day)",
            f"- Last3m: **{b['l3m']['n']} calls / {b['l3m']['days']} days** ({b['l3m']['cpd']}/day) · "
            f"multi-days {b['l3m']['multi']} · max {b['l3m']['max']}/day · "
            f"avg SL **{b['l3m']['avg_sl']}** · RR ~**{b['rr']}**",
            "",
            "### Top micros",
            "",
            "| Cal | L3m | AvgSL | Exit | Cell |",
            "|---:|---:|---:|---|---|",
        ]
        for r in b.get("top", [])[:15]:
            lines.append(
                f"| {r['cal_n']} | {r['l3m_n']} | {r['avg_sl']} | `{r['st']}` | `{r['k']}` |"
            )
        lines += [
            "",
            "### Last3m calls",
            "",
            "| Day | HM | Side | Pattern | SL style | SL | T1 | MFE |",
            "|---|---|---|---|---|---:|---:|---:|",
        ]
        for e in b.get("l3m_calls", [])[:50]:
            lines.append(
                f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"`{e['st']}` | {e['sl']} | {e['t1']} | {e['mfe']} |"
            )
        if len(b.get("l3m_calls", [])) > 50:
            lines.append(f"| … | | | | | | | {len(b['l3m_calls'])-50} more |")

    lines += [
        "",
        "## MFE (target-reached) high-T1 density",
        "",
        "| T1 | Gap | Cal calls | L3m calls | L3m /day | AvgSL | Path-win% | RR |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for t1 in T1S:
        key = f"mfe_t{int(t1)}"
        if key not in champions:
            continue
        m = champions[key]
        lines.append(
            f"| {int(t1)} | {m['gap']} | {m['cal']['n']} | {m['l3m']['n']} | {m['l3m']['cpd']} | "
            f"{m['l3m']['avg_sl']} | {m.get('path_win_pct', '')} | {m['rr']} |"
        )

    lines += [
        "",
        "## vs T1=10 deep champion",
        "",
        "| Book | T1 | L3m calls | /day | AvgSL | RR |",
        "|---|---:|---:|---:|---:|---:|",
        "| Deep PATH (prior) | 10 | 307 | 4.8 | 8.78 | 1.14 |",
    ]
    for t1 in T1S:
        key = f"path_t{int(t1)}"
        if key in champions:
            b = champions[key]
            lines.append(
                f"| High-T PATH | {int(t1)} | {b['l3m']['n']} | {b['l3m']['cpd']} | "
                f"{b['l3m']['avg_sl']} | {b['rr']} |"
            )

    lines += [
        "",
        "## Policy",
        "",
        "- research_only · not_live · high-target scalp",
        f"- Pack: `{PACK_OUT}`",
        "- Related: [`NIFTY_1M_SCALP_DEEPER_100.md`](NIFTY_1M_SCALP_DEEPER_100.md)",
        "",
    ]

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {"oracle": oracle, "champions": champions, "scoreboard": scoreboard}
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (PACK_OUT / "hightarget_summary.json").write_text(
        json.dumps(
            {
                "path": {k: v for k, v in champions.items() if k.startswith("path_")},
                "mfe": {k: {"l3m": v["l3m"], "rr": v.get("rr"), "path_win_pct": v.get("path_win_pct")} for k, v in champions.items() if k.startswith("mfe_")},
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote {REPORT_MD}", flush=True)
    print("DONE high-target", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
