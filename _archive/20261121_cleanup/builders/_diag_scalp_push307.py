"""Push beyond 307 PATH calls: gap5, min_l3m=1, swing2, more key flavors."""
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
MULTI_MD = OUT / "NIFTY_1M_SCALP_MULTICALL_100.md"


def lesser(e, st):
    p, s = float(e["sl_prev"]), float(e["sl_sig"])
    sw = float(e.get("sl_swing2", p))
    return {
        "prev": p,
        "sig": s,
        "swing2": sw,
        "min_ps": min(p, s) if s >= 4 else p,
        "cap8": min(p, 8.0),
        "cap10": min(p, 10.0),
        "cap12": min(p, 12.0),
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


def path_ok(e, h, l, c, st, t1=10.0):
    sl = lesser(e, st)
    if not (4 <= sl <= 12):
        return False, sl
    if st == "prev" and e.get("prev_t10") is not None and t1 == 10:
        return e["prev_t10"] == "win", sl
    if st == "sig" and e.get("sig_t10") is not None and t1 == 10:
        return e["sig_t10"] == "win", sl
    if st == "swing2" and e.get("swing2_t10") is not None and t1 == 10:
        return e["swing2_t10"] == "win", sl
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
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        ("GEOM", g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["advw"]),
        (g["primary"], g["side"], g["align"], g["clock"], g["advw"], g["batr"], g["slbin"], g["rsi"]),
        (g["primary"], g["side"], g["regime"], g["clock"], g["body"], g["slbin"], g["rsi"]),
        ("GEOM", g["side"], g["align"], g["clock"], g["body"], g["slbin"], g["advw"], g["stack"]),
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


def greedy(cells, gap, min_cal=2, min_l3m=1):
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
    }


def main() -> int:
    print("Push beyond 307", flush=True)
    blob = pickle.load(next(PACK.glob("scalp_events_*.pkl")).open("rb"))
    cal, test = blob["cal"], blob["test"]
    raw = base.load_existing_1m()
    h = raw["High"].astype(float).values
    l = raw["Low"].astype(float).values
    c = raw["Close"].astype(float).values
    o = raw["Open"].astype(float).values
    enrich(cal, h, l, c, o)
    enrich(test, h, l, c, o)

    styles = ["prev", "sig", "swing2", "min_ps", "cap8", "cap10", "cap12", "p75"]
    print("path flags…", flush=True)
    for i, e in enumerate(cal + test):
        if i and i % 30000 == 0:
            print(f"  {i}", flush=True)
        for st in styles:
            ok, sl = path_ok(e, h, l, c, st, 10.0)
            e[f"_ok_{st}"] = ok
            e[f"_sl_{st}"] = sl

    cal_b, test_b = defaultdict(list), defaultdict(list)
    for e in cal:
        if 4 <= e["sl_prev"] <= 20:
            for k in cell_keys(e):
                cal_b[k].append(e)
    for e in test:
        if 4 <= e["sl_prev"] <= 20:
            for k in cell_keys(e):
                test_b[k].append(e)

    best = None
    rows_out = []
    for gap in (4, 5, 6, 8, 10):
        both = []
        for st in styles:
            for k, ces in cal_b.items():
                cal_rows = apply_gap(ces, gap)
                if len(cal_rows) < 3:
                    continue
                if not all(e.get(f"_ok_{st}") for e in cal_rows):
                    continue
                tes = apply_gap(test_b.get(k, []), gap)
                if len(tes) < 1:
                    continue
                if len(tes) == 1 and len(cal_rows) < 4:
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
        seen, uniq = set(), []
        for r in both:
            id_ = (r["k"], r["st"])
            if id_ in seen:
                continue
            seen.add(id_)
            uniq.append(r)

        for mode, mc, ml in (("strict2", 2, 2), ("push1", 2, 1), ("push1_cal3", 3, 1)):
            chosen = greedy(uniq, gap, min_cal=mc, min_l3m=ml)
            cal_all, l3m_all = [], []
            for r in chosen:
                for e in r["cal_calls"]:
                    cal_all.append({**e, "_st": r["st"]})
                for e in r["l3m_calls"]:
                    l3m_all.append({**e, "_st": r["st"]})
            ok = all(e.get(f"_ok_{e['_st']}") for e in cal_all + l3m_all)
            sc, sl = stats(cal_all), stats(l3m_all)
            print(
                f"gap{gap} {mode}: cells={len(uniq)} micros={len(chosen)} "
                f"cal {sc['n']}/{sc['days']}d · l3m {sl['n']}/{sl['days']}d "
                f"({sl['cpd']}/d multi={sl['multi']} max={sl['max']}) SL={sl['avg_sl']} ok={ok}",
                flush=True,
            )
            rec = {
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
                ],
            }
            rows_out.append(rec)
            if ok:
                score = (sl["n"], sc["n"], -sl["avg_sl"])
                if best is None or score > best[0]:
                    best = (score, rec)

    assert best
    b = best[1]
    print(
        f"\nBEST: gap{b['gap']} {b['mode']} → l3m {b['l3m']['n']} calls / {b['l3m']['days']}d "
        f"({b['l3m']['cpd']}/day) cal {b['cal']['n']} avgSL={b['l3m']['avg_sl']}",
        flush=True,
    )

    lines = [
        "",
        "## Push beyond 307",
        "",
        f"- **New best PATH**: gap **{b['gap']}** `{b['mode']}` → "
        f"**{b['l3m']['n']} calls / {b['l3m']['days']} days ({b['l3m']['cpd']}/day)** · "
        f"multi-days {b['l3m']['multi']} · max {b['l3m']['max']}/day · avg SL {b['l3m']['avg_sl']}",
        f"- Calibrate: **{b['cal']['n']} / {b['cal']['days']}** · micros {b['n_micros']}",
        "",
        "| Gap | Mode | Cal | L3m | /day | Multi | Max | AvgSL | Micros |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows_out:
        if not r["ok"]:
            continue
        lines.append(
            f"| {r['gap']} | {r['mode']} | {r['cal']['n']} | {r['l3m']['n']} | "
            f"{r['l3m']['cpd']} | {r['l3m']['multi']} | {r['l3m']['max']} | "
            f"{r['l3m']['avg_sl']} | {r['n_micros']} |"
        )

    md = DEEP_MD.read_text(encoding="utf-8")
    marker = "## Push beyond 307"
    if marker in md:
        md = md.split(marker)[0].rstrip()
    DEEP_MD.write_text(md + "\n" + "\n".join(lines) + "\n", encoding="utf-8")

    payload = json.loads(DEEP_JSON.read_text(encoding="utf-8")) if DEEP_JSON.exists() else {}
    payload["push307"] = {"best": b, "sweep": [{k: r[k] for k in ("gap", "mode", "cal", "l3m", "n_micros") if k in r} for r in rows_out if r["ok"]]}
    DEEP_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    if MULTI_MD.exists():
        m = MULTI_MD.read_text(encoding="utf-8")
        mark = "## Latest densify scoreboard"
        block = [
            "",
            "## Latest densify scoreboard",
            "",
            "| Book | L3m calls | Days | /day | Avg SL | Notes |",
            "|---|---:|---:|---:|---:|---|",
            "| Prior multicall dense | 187 | 64 | 2.92 | 8.6 | path micros |",
            "| Deep wick/ATR union gap8 | 307 | 64 | 4.8 | 8.78 | both-100 |",
            f"| **Push best gap{b['gap']} {b['mode']}** | **{b['l3m']['n']}** | **{b['l3m']['days']}** | "
            f"**{b['l3m']['cpd']}** | **{b['l3m']['avg_sl']}** | see deeper report |",
            "",
            "Detail: [`NIFTY_1M_SCALP_DEEPER_100.md`](NIFTY_1M_SCALP_DEEPER_100.md)",
        ]
        if mark in m:
            m = m.split(mark)[0].rstrip()
        MULTI_MD.write_text(m + "\n" + "\n".join(block) + "\n", encoding="utf-8")

    print("DONE push", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
