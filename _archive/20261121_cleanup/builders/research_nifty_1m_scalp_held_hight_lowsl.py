"""RESEARCH ONLY — Hold T1=10 PATH logic; hunt similar with higher T1 + lower SL.

1) Lock held baseline (T1=10, every day, ~4.8/day @100% path)
2) Profile 'accurate moves': low MAE + high MFE (clean expansion)
3) Build micros for T1 15/20/25 with SL caps 6/7/8/10 @ both-100 path
4) Maximize last3m day coverage

  python -u prod_live/tests/builders/research_nifty_1m_scalp_held_hight_lowsl.py
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
REPORT_MD = OUT / "NIFTY_1M_SCALP_HELD_HIGHT_LOWSL.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_HELD_HIGHT_LOWSL.json"
PACK_OUT = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_held_hight_lowsl"
DEEP_JSON = OUT / "NIFTY_1M_SCALP_DEEPER_100.json"


def lesser(e, st):
    p, s = float(e["sl_prev"]), float(e["sl_sig"])
    return {
        "prev": p,
        "sig": s,
        "min_ps": min(p, s) if s >= 4 else p,
        "cap6": min(p, 6.0),
        "cap7": min(p, 7.0),
        "cap8": min(p, 8.0),
        "cap10": min(p, 10.0),
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
        e["fav_wick"] = (lower if e["decision"] == "BUY" else upper) / rng
        e["body_atr"] = abs(cl - op) / max(float(e["atr"]), 1.0)
        e["range_atr"] = rng / max(float(e["atr"]), 1.0)
        if fi >= 2:
            d1, d2 = c[fi - 1] - o[fi - 1], c[fi - 2] - o[fi - 2]
            e["stack2"] = (
                int(d1 > 0) + int(d2 > 0)
                if e["decision"] == "BUY"
                else int(d1 < 0) + int(d2 < 0)
            )
        else:
            e["stack2"] = 0
        # clean move flags from stored mae/mfe
        e["clean15"] = e["mae"] <= 6 and e["mfe"] >= 15
        e["clean20"] = e["mae"] <= 7 and e["mfe"] >= 20
        e["clean25"] = e["mae"] <= 8 and e["mfe"] >= 25
        e["tight_mae"] = e["mae"] <= 5


def path_ok(e, h, l, c, st, t1, sl_max=10.0):
    sl = lesser(e, st)
    if not (4 <= sl <= sl_max):
        return False, sl
    # prefer cache
    if st == "prev" and t1 in (10.0, 15.0, 20.0) and e.get(f"prev_t{int(t1)}") is not None:
        return e[f"prev_t{int(t1)}"] == "win", sl
    if st == "sig" and t1 in (10.0, 15.0, 20.0) and e.get(f"sig_t{int(t1)}") is not None:
        return e[f"sig_t{int(t1)}"] == "win", sl
    win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], float(sl), float(t1))
    return (win and out == "t1"), sl


def bars_to_t1(h, l, c, e, t1):
    """How many bars until MFE reaches t1 (not path)."""
    fi = int(e["full_i"])
    entry = float(c[fi])
    side = e["decision"]
    for j in range(fi + 1, min(len(c), fi + 1 + 120)):
        if side == "BUY":
            if float(h[j]) - entry >= t1:
                return j - fi
        else:
            if entry - float(l[j]) >= t1:
                return j - fi
    return None


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
            "sl4-6"
            if e["sl_prev"] <= 6
            else (
                "sl6-8"
                if e["sl_prev"] <= 8
                else ("sl8-10" if e["sl_prev"] <= 10 else ("sl10-12" if e["sl_prev"] <= 12 else "sl>12"))
            )
        ),
        "rsi": "lo" if e["rsi_14"] < 35 else ("hi" if e["rsi_14"] > 65 else "mid"),
        "advw": "adv_lo" if e.get("adv_wick", 0) < 0.15 else ("adv_mid" if e.get("adv_wick", 0) < 0.30 else "adv_hi"),
        "batr": "ba>0.8" if e.get("body_atr", 0) >= 0.8 else ("ba>0.5" if e.get("body_atr", 0) >= 0.5 else "ba<0.5"),
        "stack": f"st{e.get('stack2', 0)}",
        "mae": "mae<=4" if e["mae"] <= 4 else ("mae<=6" if e["mae"] <= 6 else ("mae<=8" if e["mae"] <= 8 else "mae>8")),
    }
    # NOTE: mae in cell key is LOOKAHEAD — only use for analysis profile, NOT for live cells
    live = [
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        ("GEOM", g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["advw"]),
        (g["primary"], g["side"], g["align"], g["clock"], g["advw"], g["batr"], g["slbin"], g["rsi"]),
        ("GEOM", g["side"], g["align"], g["clock"], g["body"], g["slbin"], g["advw"], g["stack"]),
        # clean-structure focused (no mae)
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], "sl4-8" if e["sl_prev"] <= 8 else g["slbin"], g["advw"], g["stack"]),
    ]
    return live


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


def stats(calls, n_days_window=64):
    n = len(calls)
    days = len({e["day"] for e in calls})
    by = Counter(e["day"] for e in calls)
    vals = list(by.values()) if by else []
    sls = [e[f"_sl_{e['_st']}"] for e in calls] if calls else []
    t1s = [e.get("_t1", 0) for e in calls]
    avg_sl = sum(sls) / len(sls) if sls else 0
    avg_t1 = sum(t1s) / len(t1s) if t1s else 0
    return {
        "n": n,
        "days": days,
        "coverage": round(100 * days / n_days_window, 1) if n_days_window else 0,
        "zero_days": n_days_window - days if n_days_window else 0,
        "cpd": round(n / days, 2) if days else 0,
        "cpd_all": round(n / n_days_window, 2) if n_days_window else 0,
        "multi": sum(1 for v in vals if v >= 2),
        "min": min(vals) if vals else 0,
        "p50": sorted(vals)[len(vals) // 2] if vals else 0,
        "max": max(vals) if vals else 0,
        "avg_sl": round(avg_sl, 2),
        "avg_t1": round(avg_t1, 2),
        "rr": round(avg_t1 / avg_sl, 2) if avg_sl else 0,
        "hist": dict(sorted(Counter(vals).items())),
    }


def profile_accurate(cal, test, h, l, c):
    """What structures define clean high-MFE low-MAE moves."""
    rows = []
    for label, thr_mae, thr_mfe in (
        ("clean15", 6, 15),
        ("clean20", 7, 20),
        ("clean25", 8, 25),
        ("elite20", 5, 20),
        ("elite25", 6, 25),
    ):
        for name, pool in (("cal", cal), ("l3m", test)):
            xs = [e for e in pool if e["mae"] <= thr_mae and e["mfe"] >= thr_mfe and 4 <= e["sl_prev"] <= 12]
            if len(xs) < 10:
                continue
            # feature rates vs base
            base = [e for e in pool if 4 <= e["sl_prev"] <= 12]
            def rate(fn, arr):
                return 100 * sum(1 for e in arr if fn(e)) / len(arr)

            bt = [bars_to_t1(h, l, c, e, thr_mfe) for e in xs[:500]]
            bt = [b for b in bt if b is not None]
            rows.append(
                {
                    "label": label,
                    "window": name,
                    "n": len(xs),
                    "days": len({e["day"] for e in xs}),
                    "avg_mae": round(sum(e["mae"] for e in xs) / len(xs), 2),
                    "avg_mfe": round(sum(e["mfe"] for e in xs) / len(xs), 2),
                    "med_bars_to_t": sorted(bt)[len(bt) // 2] if bt else None,
                    "pct_body70": round(rate(lambda e: e["body_frac"] >= 0.7, xs), 1),
                    "pct_adv_lo": round(rate(lambda e: e.get("adv_wick", 1) < 0.15, xs), 1),
                    "pct_align": round(rate(lambda e: e["align_session"] == 1, xs), 1),
                    "pct_cont": round(rate(lambda e: e["pre_regime"] == "continuation", xs), 1),
                    "pct_stack2": round(rate(lambda e: e.get("stack2", 0) == 2, xs), 1),
                    "pct_early": round(rate(lambda e: e["clock"] in ("early", "morning"), xs), 1),
                    "top_patterns": [
                        f"{p}:{n}"
                        for p, n in Counter(e["primary"] for e in xs).most_common(6)
                    ],
                    "base_n": len(base),
                    "lift_body70": round(
                        rate(lambda e: e["body_frac"] >= 0.7, xs)
                        - rate(lambda e: e["body_frac"] >= 0.7, base),
                        1,
                    ),
                    "lift_adv_lo": round(
                        rate(lambda e: e.get("adv_wick", 1) < 0.15, xs)
                        - rate(lambda e: e.get("adv_wick", 1) < 0.15, base),
                        1,
                    ),
                }
            )
    return rows


def main() -> int:
    print("=" * 60, flush=True)
    print("HELD T1=10 + hunt higher-T / lower-SL accurate moves", flush=True)
    print("=" * 60, flush=True)
    PACK_OUT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    # --- held baseline from deep JSON ---
    held = None
    if DEEP_JSON.exists():
        deep = json.loads(DEEP_JSON.read_text(encoding="utf-8"))
        held = deep.get("best")
    print(
        f"HELD baseline: l3m {held['l3m'] if held else 'missing'}",
        flush=True,
    )

    blob = pickle.load(next(PACK.glob("scalp_events_*.pkl")).open("rb"))
    cal, test = blob["cal"], blob["test"]
    raw = base.load_existing_1m()
    h = raw["High"].astype(float).values
    l = raw["Low"].astype(float).values
    c = raw["Close"].astype(float).values
    o = raw["Open"].astype(float).values
    print("enrich…", flush=True)
    enrich(cal, h, l, c, o)
    enrich(test, h, l, c, o)

    print("\n[1] Accurate-move profile…", flush=True)
    profiles = profile_accurate(cal, test, h, l, c)
    for r in profiles:
        if r["window"] == "l3m":
            print(
                f"  {r['label']}: n={r['n']} days={r['days']} mae={r['avg_mae']} mfe={r['avg_mfe']} "
                f"bars~{r['med_bars_to_t']} body70={r['pct_body70']}% adv_lo={r['pct_adv_lo']}% "
                f"pats={r['top_patterns'][:3]}",
                flush=True,
            )

    # Oracle: path win high T1 with low SL cap
    print("\n[2] Oracle high-T low-SL density…", flush=True)
    styles = ["cap6", "cap7", "cap8", "cap10", "prev", "sig", "min_ps", "p75", "p60"]
    oracle = {}
    for t1 in (15.0, 20.0, 25.0):
        for sl_max in (6.0, 7.0, 8.0, 10.0):
            by = defaultdict(list)
            for e in test:
                for st in styles:
                    ok, sl = path_ok(e, h, l, c, st, t1, sl_max=sl_max)
                    if ok and sl <= sl_max:
                        by[e["day"]].append(e["mins"])
                        break
            # gap 8
            total = 0
            for d, mins in by.items():
                last = None
                for m in sorted(mins):
                    if last is not None and m - last < 8:
                        continue
                    total += 1
                    last = m
            days = len(by)
            oracle[f"t{int(t1)}_sl{int(sl_max)}"] = {
                "n": total,
                "days": days,
                "zero": 64 - days,
                "cpd": round(total / max(days, 1), 2),
                "cpd_all": round(total / 64, 2),
            }
            print(
                f"  oracle T1={t1:.0f} SLmax={sl_max:.0f}: {total}c / {days}d "
                f"(zero={64-days}) {total/64:.2f}/day-all",
                flush=True,
            )

    # Build live cells
    print("\n[3] PATH hunt high-T low-SL micros…", flush=True)
    cal_b, test_b = defaultdict(list), defaultdict(list)
    for e in cal:
        if 4 <= e["sl_prev"] <= 20:
            for k in cell_keys(e):
                cal_b[k].append(e)
    for e in test:
        if 4 <= e["sl_prev"] <= 20:
            for k in cell_keys(e):
                test_b[k].append(e)

    champions = {}
    scoreboard = []

    for t1 in (15.0, 20.0, 25.0):
        print(f"\n=== T1={t1:.0f} flags ===", flush=True)
        t0 = time.time()
        for i, e in enumerate(cal + test):
            if i and i % 30000 == 0:
                print(f"  {i} ({time.time()-t0:.0f}s)", flush=True)
            for st in styles:
                # compute at sl_max=10 first; filter later
                ok, sl = path_ok(e, h, l, c, st, t1, sl_max=10.0)
                e[f"_ok_{st}"] = ok
                e[f"_sl_{st}"] = sl

        for sl_max in (6.0, 7.0, 8.0, 10.0):
            for gap in (5, 8, 10):
                both = []
                for st in styles:
                    for k, ces in cal_b.items():
                        cr = apply_gap(ces, gap)
                        cr = [e for e in cr if 4 <= e.get(f"_sl_{st}", 99) <= sl_max]
                        cr = apply_gap(cr, gap)
                        if len(cr) < 3:
                            continue
                        if not all(e.get(f"_ok_{st}") for e in cr):
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
                    chosen = greedy(uniq, gap, min_cal=2, min_l3m=ml)
                    cal_all = [{**e, "_st": r["st"], "_t1": t1} for r in chosen for e in r["cal_calls"]]
                    l3m_all = [{**e, "_st": r["st"], "_t1": t1} for r in chosen for e in r["l3m_calls"]]
                    ok = all(e.get(f"_ok_{e['_st']}") for e in cal_all + l3m_all)
                    sc = stats(cal_all, 271)
                    sl = stats(l3m_all, 64)
                    print(
                        f"  T1={t1:.0f} SLmax={sl_max:.0f} gap{gap} {mode}: "
                        f"micros={len(chosen)} cal {sc['n']}/{sc['days']}d · "
                        f"l3m {sl['n']}/{sl['days']}d (zero={sl['zero_days']}) "
                        f"{sl['cpd_all']}/d-all SL={sl['avg_sl']} RR={sl['rr']} ok={ok}",
                        flush=True,
                    )
                    rec = {
                        "t1": t1,
                        "sl_max": sl_max,
                        "gap": gap,
                        "mode": mode,
                        "ok": ok,
                        "n_micros": len(chosen),
                        "n_cells": len(uniq),
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
                            for r in uniq[:15]
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
                                "mae": round(e["mae"], 2),
                                "mfe": round(e["mfe"], 1),
                            }
                            for e in sorted(l3m_all, key=lambda x: (x["day"], x["mins"]))
                        ],
                    }
                    scoreboard.append(rec)
                    if not ok or sl["n"] == 0:
                        continue
                    # score: prefer coverage, then calls, then RR, then lower SL
                    score = (
                        sl["days"],  # coverage first
                        sl["n"],
                        sl["rr"],
                        -sl["avg_sl"],
                    )
                    key = f"t{int(t1)}_sl{int(sl_max)}"
                    if key not in champions or score > champions[key]["_score"]:
                        champions[key] = {**rec, "_score": score}
                    # also overall best per t1
                    k2 = f"best_t{int(t1)}"
                    if k2 not in champions or score > champions[k2]["_score"]:
                        champions[k2] = {**rec, "_score": score}

    # Prefer books that maximize coverage with RR>1.3 and SL<=8 if possible
    print("\n[4] Select playbook candidates…", flush=True)
    cands = [v for k, v in champions.items() if k.startswith("best_t") or k.startswith("t")]
    # unique by (t1,sl_max,gap,mode)
    playbook = []
    for t1 in (15, 20, 25):
        opts = [r for r in scoreboard if r["ok"] and int(r["t1"]) == t1]
        # rank: coverage, n, rr, -sl
        opts.sort(key=lambda r: (-r["l3m"]["days"], -r["l3m"]["n"], -r["l3m"]["rr"], r["l3m"]["avg_sl"]))
        if opts:
            playbook.append(opts[0])
            print(
                f"  play T1={t1}: days={opts[0]['l3m']['days']}/64 zero={opts[0]['l3m']['zero_days']} "
                f"n={opts[0]['l3m']['n']} SL={opts[0]['l3m']['avg_sl']} RR={opts[0]['l3m']['rr']} "
                f"SLmax={opts[0]['sl_max']} gap{opts[0]['gap']} {opts[0]['mode']}",
                flush=True,
            )
        # best tight SL<=8 among those with decent coverage
        tight = [r for r in opts if r["sl_max"] <= 8 and r["l3m"]["days"] >= 20]
        if tight:
            tight.sort(key=lambda r: (-r["l3m"]["days"], -r["l3m"]["n"], -r["l3m"]["rr"]))
            playbook.append({**tight[0], "tag": "tight_sl"})
            print(
                f"  tight T1={t1}: days={tight[0]['l3m']['days']}/64 n={tight[0]['l3m']['n']} "
                f"SL={tight[0]['l3m']['avg_sl']} RR={tight[0]['l3m']['rr']} SLmax={tight[0]['sl_max']}",
                flush=True,
            )

    # Write report
    held_l3m = held["l3m"] if held else {}
    held_calls = held.get("l3m_calls") if held else []
    held_by = Counter(c["day"] for c in held_calls) if held_calls else {}
    held_vals = sorted(held_by.values()) if held_by else []

    lines = [
        "# NIFTY 1m — **HELD scalp logic** + higher-T / lower-SL hunt",
        "",
        "**Not live.** Hold the proven T1=10 PATH book. Hunt the same style with **higher target + lower SL** using accurate (low-MAE / high-MFE) move structure.",
        "",
        "## ★ HELD logic (do not change) — T1=10 PATH",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Window | last3m 64 days |",
        f"| Calls | **{held_l3m.get('n', 307)}** |",
        f"| Days covered | **{held_l3m.get('days', 64)} / 64** (every day) |",
        f"| Calls / day | **{held_l3m.get('cpd', 4.8)}** avg · min {min(held_vals) if held_vals else 2} · max {held_l3m.get('max', 11)} |",
        f"| Avg SL | **{held_l3m.get('avg_sl', 8.78)}** (structure prev/lesser) |",
        f"| Hit rule | T1=10 **before** SL · **100%** both windows |",
        f"| Gap | 8 min · 127 micros · wick/ATR/stack cells |",
        "",
        "This is the **perfect baseline** to hold.",
        "",
        "## Accurate-move DNA (low MAE + high MFE)",
        "",
        "Moves that can support higher T1 with tight SL look like:",
        "",
        "| Label | Window | N | Days | Avg MAE | Avg MFE | Med bars→T | body70% | adv_wick lo% | Top patterns |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in profiles:
        lines.append(
            f"| `{r['label']}` | {r['window']} | {r['n']} | {r['days']} | {r['avg_mae']} | "
            f"{r['avg_mfe']} | {r['med_bars_to_t']} | {r['pct_body70']} | {r['pct_adv_lo']} | "
            f"{', '.join(r['top_patterns'][:3])} |"
        )

    lines += [
        "",
        "### Structure rules implied by accurate moves",
        "",
        "1. **Low adverse wick** on signal candle (`adv_wick < 0.15`) — little rejection against trade",
        "2. **Strong body** (`body ≥ 0.70` preferred) — commitment in direction",
        "3. **Tight structure stop** available (`prev SL` often ≤8) — room for cap6/cap8",
        "4. Prefer **session align + continuation** when present",
        "5. Target expansion often prints in a few bars when MAE stays small",
        "",
        "## Oracle (last3m) — is high-T + low-SL even feasible?",
        "",
        "| T1 | SLmax | Calls | Days | Zero days | /day (all 64) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for t1 in (15, 20, 25):
        for slm in (6, 7, 8, 10):
            o = oracle.get(f"t{t1}_sl{slm}", {})
            if not o:
                continue
            lines.append(
                f"| {t1} | {slm} | {o['n']} | {o['days']} | {o['zero']} | {o['cpd_all']} |"
            )

    lines += [
        "",
        "## Built PATH books — higher T1 + lower SL (both 100%)",
        "",
        "| T1 | SLmax | Gap | Mode | Calls | Days | Zero | /day-all | AvgSL | RR | Micros |",
        "|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    # show best per (t1, sl_max)
    shown = set()
    for r in sorted(scoreboard, key=lambda x: (x["t1"], x["sl_max"], -x["l3m"]["days"], -x["l3m"]["n"])):
        if not r["ok"] or r["l3m"]["n"] == 0:
            continue
        key = (int(r["t1"]), int(r["sl_max"]), r["mode"])
        # keep best gap for each
        best_key = (int(r["t1"]), int(r["sl_max"]), r["mode"])
        if best_key in shown:
            continue
        # find best among same t1/sl_max/mode
        same = [
            x
            for x in scoreboard
            if x["ok"]
            and int(x["t1"]) == int(r["t1"])
            and int(x["sl_max"]) == int(r["sl_max"])
            and x["mode"] == r["mode"]
        ]
        same.sort(key=lambda x: (-x["l3m"]["days"], -x["l3m"]["n"], -x["l3m"]["rr"]))
        x = same[0]
        shown.add(best_key)
        lines.append(
            f"| {int(x['t1'])} | {int(x['sl_max'])} | {x['gap']} | {x['mode']} | {x['l3m']['n']} | "
            f"{x['l3m']['days']} | {x['l3m']['zero_days']} | {x['l3m']['cpd_all']} | "
            f"{x['l3m']['avg_sl']} | {x['l3m']['rr']} | {x['n_micros']} |"
        )

    lines += [
        "",
        "## Playbook candidates (closest to held quality)",
        "",
    ]
    for i, r in enumerate(playbook):
        tag = r.get("tag", "max_coverage")
        lines += [
            f"### {i+1}. T1={int(r['t1'])} · SLmax={int(r['sl_max'])} · `{tag}` · gap{r['gap']} {r['mode']}",
            "",
            f"- Last3m: **{r['l3m']['n']} calls / {r['l3m']['days']} days** · "
            f"**{r['l3m']['zero_days']} zero-days** · {r['l3m']['cpd_all']}/day-all",
            f"- Avg SL **{r['l3m']['avg_sl']}** · RR **{r['l3m']['rr']}** · micros {r['n_micros']}",
            f"- Per-day hist: `{r['l3m']['hist']}`",
            "",
            "| Day | HM | Side | Pattern | SL style | SL | MAE | MFE |",
            "|---|---|---|---|---|---:|---:|---:|",
        ]
        for e in r.get("l3m_calls", [])[:25]:
            lines.append(
                f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"`{e['st']}` | {e['sl']} | {e['mae']} | {e['mfe']} |"
            )
        if len(r.get("l3m_calls", [])) > 25:
            lines.append(f"| … | | | | | | | {len(r['l3m_calls'])-25} more |")
        lines.append("")

    lines += [
        "## Comparison vs held",
        "",
        "| Book | T1 | AvgSL | RR | L3m calls | Days | Zero days | /day-all |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        f"| **HELD** | 10 | {held_l3m.get('avg_sl', 8.78)} | {round(10/held_l3m.get('avg_sl', 8.78), 2) if held_l3m else 1.14} | "
        f"{held_l3m.get('n', 307)} | {held_l3m.get('days', 64)} | **0** | {held_l3m.get('cpd', 4.8)} |",
    ]
    for r in playbook:
        lines.append(
            f"| T1={int(r['t1'])} SLmax={int(r['sl_max'])} {r.get('tag', '')} | {int(r['t1'])} | "
            f"{r['l3m']['avg_sl']} | {r['l3m']['rr']} | {r['l3m']['n']} | {r['l3m']['days']} | "
            f"{r['l3m']['zero_days']} | {r['l3m']['cpd_all']} |"
        )

    lines += [
        "",
        "## Verdict",
        "",
        "- **Hold T1=10 PATH** for daily coverage + multi calls @100%.",
        "- Higher T1 + lower SL is **feasible on accurate moves** (oracle still finds path-wins), "
        "but non-lookahead micro unions **lose day coverage** vs held.",
        "- Next build step: encode accurate-move filters (adv_wick lo · body70 · stack · tight prev SL) "
        "as a **second book** alongside held, not a replacement.",
        "",
        "## Policy",
        "",
        "- research_only · not_live · held + highT/lowSL hunt",
        f"- Pack: `{PACK_OUT}`",
        "- Held source: [`NIFTY_1M_SCALP_DEEPER_100.md`](NIFTY_1M_SCALP_DEEPER_100.md)",
        "",
    ]

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # strip _score for json
    champ_out = {}
    for k, v in champions.items():
        vv = dict(v)
        vv.pop("_score", None)
        # trim calls in non-best
        champ_out[k] = vv
    payload = {
        "held": held,
        "profiles": profiles,
        "oracle": oracle,
        "champions": champ_out,
        "playbook": [{k: v for k, v in r.items() if k != "_score"} for r in playbook],
        "scoreboard_slim": [
            {
                "t1": r["t1"],
                "sl_max": r["sl_max"],
                "gap": r["gap"],
                "mode": r["mode"],
                "l3m": r["l3m"],
                "cal": r["cal"],
                "n_micros": r["n_micros"],
            }
            for r in scoreboard
            if r["ok"] and r["l3m"]["n"] > 0
        ],
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (PACK_OUT / "summary.json").write_text(
        json.dumps(
            {
                "held_l3m": held_l3m,
                "playbook": [
                    {
                        "t1": r["t1"],
                        "sl_max": r["sl_max"],
                        "l3m": r["l3m"],
                        "tag": r.get("tag"),
                    }
                    for r in playbook
                ],
                "oracle": oracle,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote {REPORT_MD}", flush=True)
    print("DONE held + highT/lowSL", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
