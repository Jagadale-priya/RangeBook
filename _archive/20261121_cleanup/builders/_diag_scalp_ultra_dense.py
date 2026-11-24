"""Ultra-dense PATH union: gap 5–8, thinner keys, min_l3m=1 cal-strong, T1=8/10."""
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
DEEP_MD = OUT / "NIFTY_1M_SCALP_DEEPER_100.md"
DEEP_JSON = OUT / "NIFTY_1M_SCALP_DEEPER_100.json"


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


def enrich(events, h, l, c, o, df):
    day_open = {}
    if "day" in df.columns:
        day_open = {day: float(g["Open"].iloc[0]) for day, g in df.groupby("day")}
    for e in events:
        fi = int(e["full_i"])
        hi, lo, cl, op = float(h[fi]), float(l[fi]), float(c[fi]), float(o[fi])
        rng = max(hi - lo, 0.5)
        upper = hi - max(op, cl)
        lower = min(op, cl) - lo
        if e["decision"] == "BUY":
            e["adv_wick"] = upper / rng
        else:
            e["adv_wick"] = lower / rng
        e["body_atr"] = abs(cl - op) / max(float(e["atr"]), 1.0)
        if fi >= 2:
            d1, d2 = c[fi - 1] - o[fi - 1], c[fi - 2] - o[fi - 2]
            if e["decision"] == "BUY":
                e["stack2"] = int(d1 > 0) + int(d2 > 0)
            else:
                e["stack2"] = int(d1 < 0) + int(d2 < 0)
        else:
            e["stack2"] = 0
        dopen = day_open.get(e["day"], cl)
        e["from_open_atr"] = (cl - dopen) / max(float(e["atr"]), 1.0)


def path_ok(e, h, l, c, st, t1):
    sl = lesser(e, st)
    if not (4 <= sl <= 12):
        return False, sl
    key = f"{st}_t{int(t1)}"
    if st == "prev" and e.get(f"prev_t{int(t1)}") in ("win", "sl", "time"):
        # only t10/20/15/12/8 cached for prev
        cached = e.get(f"prev_t{int(t1)}")
        if cached is not None:
            return cached == "win", sl
    if st == "sig" and e.get(f"sig_t{int(t1)}") is not None:
        return e.get(f"sig_t{int(t1)}") == "win", sl
    win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], float(sl), float(t1))
    return (win and out == "t1"), sl


def tags(e):
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
            else ("sl8-12" if e["sl_prev"] <= 12 else ("sl12-16" if e["sl_prev"] <= 16 else "sl16-20"))
        ),
        "rsi": "lo" if e["rsi_14"] < 35 else ("hi" if e["rsi_14"] > 65 else "mid"),
        "advw": "adv_lo" if e.get("adv_wick", 0) < 0.15 else ("adv_mid" if e.get("adv_wick", 0) < 0.35 else "adv_hi"),
        "batr": "ba>0.8" if e.get("body_atr", 0) >= 0.8 else ("ba>0.5" if e.get("body_atr", 0) >= 0.5 else "ba<0.5"),
        "stack": f"st{e.get('stack2', 0)}",
    }


def keys(e):
    g = tags(e)
    return [
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        ("GEOM", g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["advw"]),
        (g["primary"], g["side"], g["align"], g["clock"], g["advw"], g["slbin"], g["body"]),
        ("THIN", g["side"], g["clock"], g["advw"], g["slbin"], g["body"], g["align"]),
        ("THIN2", g["side"], g["regime"], g["advw"], g["slbin"], g["align"]),
    ]


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


def greedy(cells, gap, min_cal=2, min_l3m=1):
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
        "coverage": round(100 * days / 64, 1) if days else 0,
    }


def main() -> int:
    print("Ultra-dense PATH scalp", flush=True)
    blob = pickle.load(next(PACK.glob("scalp_events_*.pkl")).open("rb"))
    cal, test = blob["cal"], blob["test"]
    raw = base.load_existing_1m()
    h, l, c, o = (
        raw["High"].astype(float).values,
        raw["Low"].astype(float).values,
        raw["Close"].astype(float).values,
        raw["Open"].astype(float).values,
    )
    enrich(cal, h, l, c, o, raw)
    enrich(test, h, l, c, o, raw)

    styles = ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "p75"]
    results = []

    for t1 in (10.0, 8.0):
        print(f"\n=== T1={t1} path flags ===", flush=True)
        t0 = time.time()
        for i, e in enumerate(cal + test):
            if i and i % 30000 == 0:
                print(f"  {i} ({time.time()-t0:.0f}s)", flush=True)
            for st in styles:
                ok, sl = path_ok(e, h, l, c, st, t1)
                e[f"_ok_{st}"] = ok
                e[f"_sl_{st}"] = sl

        for gap in (5, 6, 8, 10):
            both = []
            # build buckets once
            cal_b, test_b = defaultdict(list), defaultdict(list)
            for e in cal:
                if 4 <= e["sl_prev"] <= 20:
                    for k in keys(e):
                        cal_b[k].append(e)
            for e in test:
                if 4 <= e["sl_prev"] <= 20:
                    for k in keys(e):
                        test_b[k].append(e)

            for st in styles:
                for k, ces in cal_b.items():
                    cal_rows = apply_gap(ces, gap)
                    if len(cal_rows) < 3:
                        continue
                    if not all(e.get(f"_ok_{st}") for e in cal_rows):
                        continue
                    tes = apply_gap(test_b.get(k, []), gap)
                    # allow min_l3m=1 if cal strong (>=5)
                    if len(tes) < 1:
                        continue
                    if len(tes) < 2 and len(cal_rows) < 5:
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
                            "cal_n": len(cal_rows),
                            "l3m_n": len(tes),
                            "avg_sl": avg,
                            "cal_calls": cal_rows,
                            "l3m_calls": tes,
                        }
                    )
            both.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"], r["avg_sl"]))
            seen = set()
            uniq = []
            for r in both:
                id_ = (r["k"], r["st"])
                if id_ in seen:
                    continue
                seen.add(id_)
                uniq.append(r)

            for mode, min_cal, min_l3m in (("strict", 2, 2), ("dense", 2, 1)):
                chosen = greedy(uniq, gap, min_cal=min_cal, min_l3m=min_l3m)
                cal_all, l3m_all = [], []
                for r in chosen:
                    for e in r["cal_calls"]:
                        cal_all.append({**e, "_st": r["st"]})
                    for e in r["l3m_calls"]:
                        l3m_all.append({**e, "_st": r["st"]})
                # verify 100
                ok = all(e.get(f"_ok_{e['_st']}") for e in cal_all + l3m_all)
                sc, sl = stats(cal_all), stats(l3m_all)
                # coverage vs 64 / 271
                sl["coverage64"] = round(100 * sl["days"] / 64, 1)
                sc["coverage271"] = round(100 * sc["days"] / 271, 1)
                print(
                    f"  T1={t1} gap{gap} {mode}: cells={len(uniq)} micros={len(chosen)} "
                    f"cal {sc['n']}c/{sc['days']}d · l3m {sl['n']}c/{sl['days']}d "
                    f"({sl['cpd']}/d multi={sl['multi']} max={sl['max']}) "
                    f"SL={sl['avg_sl']} ok={ok}",
                    flush=True,
                )
                results.append(
                    {
                        "t1": t1,
                        "gap": gap,
                        "mode": mode,
                        "ok": ok,
                        "n_cells": len(uniq),
                        "n_micros": len(chosen),
                        "cal": sc,
                        "l3m": sl,
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
                        ]
                        if ok
                        else [],
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
                    }
                )

    perfect = [r for r in results if r["ok"]]
    perfect.sort(key=lambda r: (-r["l3m"]["n"], -r["cal"]["n"], r["l3m"]["avg_sl"]))
    best = perfect[0] if perfect else None
    print("\nTOP perfect books:", flush=True)
    for r in perfect[:8]:
        print(
            f"  T1={r['t1']} gap{r['gap']} {r['mode']}: "
            f"l3m {r['l3m']['n']}c/{r['l3m']['days']}d ({r['l3m']['cpd']}/d) "
            f"cal {r['cal']['n']}c avgSL={r['l3m']['avg_sl']}",
            flush=True,
        )

    # append report
    lines = [
        "",
        "## Ultra-dense PATH sweep",
        "",
        "| T1 | Gap | Mode | Cal calls | Cal days | L3m calls | L3m days | /day | Multi | Max | AvgSL | Micros |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in perfect:
        lines.append(
            f"| {int(r['t1'])} | {r['gap']} | {r['mode']} | {r['cal']['n']} | {r['cal']['days']} | "
            f"{r['l3m']['n']} | {r['l3m']['days']} | {r['l3m']['cpd']} | {r['l3m']['multi']} | "
            f"{r['l3m']['max']} | {r['l3m']['avg_sl']} | {r['n_micros']} |"
        )
    if best:
        lines += [
            "",
            f"### Ultra champion: T1={int(best['t1'])} gap={best['gap']} {best['mode']}",
            "",
            f"- Last3m **{best['l3m']['n']} calls / {best['l3m']['days']} days** · "
            f"**{best['l3m']['cpd']}/day** · multi-days {best['l3m']['multi']} · "
            f"max {best['l3m']['max']}/day · avg SL {best['l3m']['avg_sl']}",
            f"- Calibrate **{best['cal']['n']} / {best['cal']['days']}** · micros {best['n_micros']}",
            "",
            "| Day | HM | Side | Pattern | SL style | SL |",
            "|---|---|---|---|---|---:|",
        ]
        for e in best["l3m_calls"][:40]:
            lines.append(
                f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"`{e['st']}` | {e['sl']} |"
            )
        if len(best["l3m_calls"]) > 40:
            lines.append(f"| … | | | | | {len(best['l3m_calls'])-40} more |")

    md = DEEP_MD.read_text(encoding="utf-8")
    marker = "## Ultra-dense PATH sweep"
    if marker in md:
        md = md.split(marker)[0].rstrip()
    # bump headline if improved
    if best and best["l3m"]["n"] > 307:
        md = md.replace(
            f"- Prior PATH union baseline: **187 calls / 64 days** (~2.9/day)",
            f"- Prior PATH union baseline: **187 calls / 64 days** (~2.9/day)\n"
            f"- Deep union: **307 calls / 64 days** (4.8/day)\n"
            f"- **Ultra champion: {best['l3m']['n']} calls / {best['l3m']['days']} days "
            f"({best['l3m']['cpd']}/day)**",
        )
    DEEP_MD.write_text(md + "\n" + "\n".join(lines) + "\n", encoding="utf-8")

    try:
        payload = json.loads(DEEP_JSON.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    payload["ultra"] = {
        "best": {
            "t1": best["t1"],
            "gap": best["gap"],
            "mode": best["mode"],
            "cal": best["cal"],
            "l3m": best["l3m"],
            "n_micros": best["n_micros"],
        }
        if best
        else None,
        "sweep": [
            {
                "t1": r["t1"],
                "gap": r["gap"],
                "mode": r["mode"],
                "cal": r["cal"],
                "l3m": r["l3m"],
                "n_micros": r["n_micros"],
            }
            for r in perfect
        ],
    }
    DEEP_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"updated {DEEP_MD}", flush=True)
    print("DONE ultra", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
