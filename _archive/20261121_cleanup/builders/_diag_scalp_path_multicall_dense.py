"""Dense path multi-call: min_l3m=2, cal-perfect templates, gap union, oracle density."""
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
REPORT_MD = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_1M_SCALP_MULTICALL_100.md"
REPORT_JSON = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_1M_SCALP_MULTICALL_100.json"


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


def tags(e):
    rng = max(float(e["candle_range"]), 0.5)
    atr = max(float(e["atr"]), 1.0)
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
        "rng": "r>atr" if rng > atr else ("r>0.7a" if rng > 0.7 * atr else "r_sm"),
        "pre": (
            "p_str"
            if abs(e["pre_chg_5"]) >= 12
            else ("p_med" if abs(e["pre_chg_5"]) >= 5 else "p_flat")
        ),
    }


def cell_key(e, geom=False):
    g = tags(e)
    head = "GEOM" if geom else g["primary"]
    return (
        head,
        g["side"],
        g["regime"],
        g["align"],
        g["clock"],
        g["body"],
        g["slbin"],
        g["rsi"],
        g["rng"],
        g["pre"],
    )


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


def main() -> int:
    print("Dense PATH multi-call hunt", flush=True)
    blob = pickle.load(next(PACK.glob("scalp_events_*.pkl")).open("rb"))
    cal, test = blob["cal"], blob["test"]
    raw = base.load_existing_1m()
    h = raw["High"].astype(float).values
    l = raw["Low"].astype(float).values
    c = raw["Close"].astype(float).values

    styles = ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "p75"]
    t1 = 10.0
    gap = 15

    # Oracle density: max path-wins/day with SL<=12
    print("\n[Oracle multi density T1=10 SL<=12]", flush=True)
    for name, pool in (("cal", cal), ("l3m", test)):
        by = defaultdict(list)
        for e in pool:
            for st in styles:
                ok, sl = path_ok(e, h, l, c, st, t1)
                if ok:
                    by[e["day"]].append((e["mins"], st, sl, e))
                    break  # one style enough for oracle count of events
        # recount properly: any event that wins under ANY style
        by2 = defaultdict(list)
        for e in pool:
            best = None
            for st in styles:
                ok, sl = path_ok(e, h, l, c, st, t1)
                if ok:
                    best = (e, st, sl)
                    break
            if best:
                by2[e["day"]].append(best)
        total_calls = 0
        multi = 0
        max_d = 0
        for d, xs in by2.items():
            xs = apply_gap([x[0] for x in xs], gap)
            # re-filter gap on annotated
            n = len(xs)
            total_calls += n
            if n >= 2:
                multi += 1
            max_d = max(max_d, n)
        days = len(by2)
        print(
            f"  {name}: {total_calls} path-wins / {days} days · "
            f"{total_calls/max(days,1):.1f}/day · multiDays={multi} max/day={max_d}",
            flush=True,
        )

    # Precompute best style win flag for each event (tight SL)
    print("\nprecompute path flags…", flush=True)
    t0 = time.time()
    for i, e in enumerate(cal + test):
        if i and i % 25000 == 0:
            print(f"  {i} ({time.time()-t0:.0f}s)", flush=True)
        best_st, best_sl = None, None
        for st in styles:
            ok, sl = path_ok(e, h, l, c, st, t1)
            e[f"_ok_{st}"] = ok
            e[f"_sl_{st}"] = sl
            if ok and best_st is None:
                best_st, best_sl = st, sl
        e["_ok_any"] = best_st is not None
        e["_best_st"] = best_st
        e["_best_sl"] = best_sl

    # Build cells: structure must be 100% path under a FIXED style
    def build_cells(pool, style, min_n):
        buckets = defaultdict(list)
        for e in pool:
            if not (4 <= e["sl_prev"] <= 20):
                continue
            buckets[cell_key(e, False)].append(e)
            buckets[cell_key(e, True)].append(e)
        good = {}
        for k, es in buckets.items():
            rows = apply_gap(es, gap)
            if len(rows) < min_n:
                continue
            if all(e.get(f"_ok_{style}") for e in rows):
                avg = sum(e[f"_sl_{style}"] for e in rows) / len(rows)
                if avg <= 12:
                    good[k] = {"rows": rows, "avg_sl": avg, "style": style}
        return good

    print("build cal-perfect cells per style…", flush=True)
    cal_cells = {}
    for st in styles:
        g = build_cells(cal, st, min_n=3)
        print(f"  {st}: {len(g)} cal-perfect cells", flush=True)
        for k, v in g.items():
            cal_cells[(k, st)] = v

    # Validate on last3m: cell must have >=2 calls AND 100% path
    both = []
    test_buckets = defaultdict(list)
    for e in test:
        if not (4 <= e["sl_prev"] <= 20):
            continue
        test_buckets[cell_key(e, False)].append(e)
        test_buckets[cell_key(e, True)].append(e)

    for (k, st), v in cal_cells.items():
        tes = apply_gap(test_buckets.get(k, []), gap)
        if len(tes) < 2:
            continue
        if not all(e.get(f"_ok_{st}") for e in tes):
            continue
        avg = sum(e[f"_sl_{st}"] for e in tes) / len(tes)
        both.append(
            {
                "k": k,
                "st": st,
                "cal_n": len(v["rows"]),
                "l3m_n": len(tes),
                "avg_sl": avg,
                "cal_calls": v["rows"],
                "l3m_calls": tes,
            }
        )
    both.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"], r["avg_sl"]))
    print(f"both-100 path cells (min_l3m=2): {len(both)}", flush=True)
    for r in both[:12]:
        print(
            f"  l3m{r['l3m_n']} cal{r['cal_n']} avgSL={r['avg_sl']:.1f} {r['st']} {r['k']}",
            flush=True,
        )

    # Greedy union maximizing calls
    used_c, used_t = set(), set()
    chosen = []
    for r in both:
        def take(calls, used):
            out = []
            last = {}
            for e in sorted(calls, key=lambda x: (x["day"], x["mins"])):
                key = (e["day"], e["mins"])
                if key in used:
                    continue
                if any(d == e["day"] and abs(m - e["mins"]) < gap for d, m in used):
                    continue
                prev = last.get(e["day"])
                if prev is not None and e["mins"] - prev < gap:
                    continue
                out.append(e)
                last[e["day"]] = e["mins"]
            return out

        ck = take(r["cal_calls"], used_c)
        tk = take(r["l3m_calls"], used_t)
        if len(ck) < 2 or len(tk) < 2:
            continue
        if not all(e.get(f"_ok_{r['st']}") for e in ck + tk):
            continue
        chosen.append({**r, "cal_calls": ck, "l3m_calls": tk, "cal_n": len(ck), "l3m_n": len(tk)})
        for e in ck:
            used_c.add((e["day"], e["mins"]))
        for e in tk:
            used_t.add((e["day"], e["mins"]))

    def stats(calls, st_field=True):
        n = len(calls)
        days = len({e["day"] for e in calls})
        by = defaultdict(int)
        for e in calls:
            by[e["day"]] += 1
        return {
            "n": n,
            "days": days,
            "cpd": round(n / days, 2) if days else 0,
            "multi": sum(1 for v in by.values() if v >= 2),
            "max": max(by.values()) if by else 0,
        }

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

    sc = stats(cal_all)
    sl = stats(l3m_all)
    asl = (
        sum(e[f"_sl_{e['_st']}"] for e in l3m_all) / len(l3m_all) if l3m_all else 0
    )
    print(
        f"\nPATH UNION both-100: cal {sc['n']}c/{sc['days']}d ({sc['cpd']}/d multi={sc['multi']}) · "
        f"l3m {sl['n']}c/{sl['days']}d ({sl['cpd']}/d multi={sl['multi']} max={sl['max']}) "
        f"avgSL={asl:.1f} micros={len(chosen)}",
        flush=True,
    )

    # Also: single fixed rule multi — top GEOM/pattern filters with multi>=1
    print("\nTop multi-capable both-100 cells:", flush=True)
    multi_cells = [r for r in both if r["l3m_n"] >= 3 or r["cal_n"] >= 5]
    for r in multi_cells[:15]:
        cd = len({e["day"] for e in r["cal_calls"]})
        ld = len({e["day"] for e in r["l3m_calls"]})
        print(
            f"  cal{r['cal_n']}/{cd}d l3m{r['l3m_n']}/{ld}d SL={r['avg_sl']:.1f} {r['st']} {r['k']}",
            flush=True,
        )

    # Append to report
    lines = [
        "",
        "## Dense PATH multi-call (min_l3m=2 · SL≤12 · gap=15)",
        "",
        f"- Both-100 path micros: **{len(both)}**",
        f"- Union: cal **{sc['n']} calls / {sc['days']} days** ({sc['cpd']}/day, multi-days {sc['multi']})",
        f"- Union: last3m **{sl['n']} calls / {sl['days']} days** ({sl['cpd']}/day, "
        f"multi-days {sl['multi']}, max/day {sl['max']}) · avg SL **{asl:.1f}** · micros **{len(chosen)}**",
        "",
        "### Path micros (multi-capable)",
        "",
        "| Cal | L3m | AvgSL | Exit | Cell |",
        "|---:|---:|---:|---|---|",
    ]
    for r in (multi_cells or both)[:20]:
        lines.append(
            f"| {r['cal_n']} | {r['l3m_n']} | {r['avg_sl']:.1f} | `{r['st']}` | `{r['k']}` |"
        )
    lines += [
        "",
        "### Last3m path union calls",
        "",
        "| Day | HM | Side | Pattern | SL style | SL |",
        "|---|---|---|---|---|---:|",
    ]
    for e in sorted(l3m_all, key=lambda x: (x["day"], x["mins"])):
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
            f"`{e['_st']}` | {e[f'_sl_{e['_st']}']:.1f} |"
        )

    md = REPORT_MD.read_text(encoding="utf-8")
    marker = "## Dense PATH multi-call"
    if marker in md:
        md = md.split(marker)[0].rstrip()
    REPORT_MD.write_text(md + "\n" + "\n".join(lines) + "\n", encoding="utf-8")

    # update json
    try:
        payload = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    payload["dense_path_union"] = {
        "cal": sc,
        "l3m": {**sl, "avg_sl": round(asl, 2)},
        "n_micros": len(chosen),
        "n_both_cells": len(both),
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
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"updated {REPORT_MD}", flush=True)
    print("DONE dense path", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
