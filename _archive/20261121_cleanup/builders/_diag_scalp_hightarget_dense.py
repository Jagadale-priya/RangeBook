"""Densify high-T PATH (15/20) with min_l3m=1 + gap5 like deep T1=10."""
from __future__ import annotations

import json
import pickle
import sys
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
REPORT_MD = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_1M_SCALP_HIGHTARGET_100.md"
REPORT_JSON = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_1M_SCALP_HIGHTARGET_100.json"


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


def path_ok(e, h, l, c, st, t1):
    sl = lesser(e, st)
    if not (4 <= sl <= 20):
        return False, sl
    if st == "prev" and t1 in (15.0, 20.0) and e.get(f"prev_t{int(t1)}") is not None:
        return e[f"prev_t{int(t1)}"] == "win", sl
    if st == "sig" and t1 in (15.0, 20.0) and e.get(f"sig_t{int(t1)}") is not None:
        return e[f"sig_t{int(t1)}"] == "win", sl
    win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], float(sl), float(t1))
    return (win and out == "t1"), sl


def keys(e):
    body = float(e["body_frac"])
    g = {
        "primary": e["primary"],
        "side": e["decision"],
        "regime": e["pre_regime"],
        "align": int(e["align_session"]),
        "clock": e["clock"],
        "body": "b70+" if body >= 0.7 else ("b55+" if body >= 0.55 else ("b45+" if body >= 0.45 else "b<45")),
        "slbin": "sl4-8" if e["sl_prev"] <= 8 else ("sl8-12" if e["sl_prev"] <= 12 else ("sl12-16" if e["sl_prev"] <= 16 else "sl16-20")),
        "rsi": "lo" if e["rsi_14"] < 35 else ("hi" if e["rsi_14"] > 65 else "mid"),
        "advw": "adv_lo" if e.get("adv_wick", 0) < 0.15 else ("adv_mid" if e.get("adv_wick", 0) < 0.35 else "adv_hi"),
        "batr": "ba>0.8" if e.get("body_atr", 0) >= 0.8 else ("ba>0.5" if e.get("body_atr", 0) >= 0.5 else "ba<0.5"),
        "stack": f"st{e.get('stack2', 0)}",
    }
    return [
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        ("GEOM", g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["advw"]),
        (g["primary"], g["side"], g["align"], g["clock"], g["advw"], g["batr"], g["slbin"], g["rsi"]),
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


def greedy(cells, gap, min_l3m=1):
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
        if len(ck) < 2 or len(tk) < min_l3m:
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
    print("Dense high-T 15/20", flush=True)
    blob = pickle.load(next(PACK.glob("scalp_events_*.pkl")).open("rb"))
    cal, test = blob["cal"], blob["test"]
    raw = base.load_existing_1m()
    h = raw["High"].astype(float).values
    l = raw["Low"].astype(float).values
    c = raw["Close"].astype(float).values
    o = raw["Open"].astype(float).values
    enrich(cal, h, l, c, o)
    enrich(test, h, l, c, o)

    styles = ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "cap15", "cap20", "p75"]
    cal_b, test_b = defaultdict(list), defaultdict(list)
    for e in cal:
        if 4 <= e["sl_prev"] <= 20:
            for k in keys(e):
                cal_b[k].append(e)
    for e in test:
        if 4 <= e["sl_prev"] <= 20:
            for k in keys(e):
                test_b[k].append(e)

    bests = {}
    for t1 in (15.0, 20.0):
        print(f"T1={t1}", flush=True)
        for e in cal + test:
            for st in styles:
                ok, sl = path_ok(e, h, l, c, st, t1)
                e[f"_ok_{st}"] = ok
                e[f"_sl_{st}"] = sl
        best = None
        for gap in (5, 8, 10):
            both = []
            for st in styles:
                for k, ces in cal_b.items():
                    cr = apply_gap(ces, gap)
                    cr = [e for e in cr if 4 <= e[f"_sl_{st}"] <= 20]
                    cr = apply_gap(cr, gap)
                    if len(cr) < 3 or not all(e.get(f"_ok_{st}") for e in cr):
                        continue
                    tr = apply_gap(test_b.get(k, []), gap)
                    tr = [e for e in tr if 4 <= e[f"_sl_{st}"] <= 20]
                    tr = apply_gap(tr, gap)
                    if len(tr) < 1:
                        continue
                    if len(tr) < 2 and len(cr) < 4:
                        continue
                    if not all(e.get(f"_ok_{st}") for e in tr):
                        continue
                    avg = sum(e[f"_sl_{st}"] for e in tr) / len(tr)
                    both.append(
                        {
                            "k": k,
                            "st": st,
                            "cal_calls": cr,
                            "l3m_calls": tr,
                            "cal_n": len(cr),
                            "l3m_n": len(tr),
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
            for mode, ml in (("strict", 2), ("dense", 1)):
                chosen = greedy(uniq, gap, min_l3m=ml)
                cal_all = [{**e, "_st": r["st"]} for r in chosen for e in r["cal_calls"]]
                l3m_all = [{**e, "_st": r["st"]} for r in chosen for e in r["l3m_calls"]]
                ok = all(e.get(f"_ok_{e['_st']}") for e in cal_all + l3m_all)
                sc, sl = stats(cal_all), stats(l3m_all)
                rr = round(t1 / sl["avg_sl"], 2) if sl["avg_sl"] else 0
                print(
                    f"  gap{gap} {mode}: micros={len(chosen)} cal {sc['n']}/{sc['days']} "
                    f"l3m {sl['n']}/{sl['days']} ({sl['cpd']}/d) SL={sl['avg_sl']} RR={rr} ok={ok}",
                    flush=True,
                )
                if ok and sl["n"]:
                    score = (sl["n"], sc["n"], rr)
                    if best is None or score > best[0]:
                        best = (
                            score,
                            {
                                "t1": t1,
                                "gap": gap,
                                "mode": mode,
                                "cal": sc,
                                "l3m": sl,
                                "rr": rr,
                                "n_micros": len(chosen),
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
                            },
                        )
        if best:
            bests[int(t1)] = best[1]
            b = best[1]
            print(
                f"  BEST T1={t1}: {b['l3m']['n']}c/{b['l3m']['days']}d ({b['l3m']['cpd']}/d) RR={b['rr']}",
                flush=True,
            )

    lines = [
        "",
        "## Dense pack (min_l3m=1 · gap5–10 · T1 15/20)",
        "",
        "| T1 | Gap | Mode | Cal | L3m | /day | Multi | AvgSL | RR | Micros |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for t1, b in bests.items():
        lines.append(
            f"| {t1} | {b['gap']} | {b['mode']} | {b['cal']['n']} | {b['l3m']['n']} | "
            f"{b['l3m']['cpd']} | {b['l3m']['multi']} | {b['l3m']['avg_sl']} | {b['rr']} | {b['n_micros']} |"
        )
    if 15 in bests:
        b = bests[15]
        lines += [
            "",
            "### Dense T1=15 last3m sample",
            "",
            "| Day | HM | Side | Pattern | SL style | SL |",
            "|---|---|---|---|---|---:|",
        ]
        for e in b["l3m_calls"][:30]:
            lines.append(
                f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | `{e['st']}` | {e['sl']} |"
            )

    md = REPORT_MD.read_text(encoding="utf-8")
    marker = "## Dense pack (min_l3m=1 · gap5–10 · T1 15/20)"
    if marker in md:
        md = md.split(marker)[0].rstrip()
    REPORT_MD.write_text(md + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    payload = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    payload["dense_15_20"] = bests
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("DONE dense high-T", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
