"""RESEARCH ONLY — Maximize multi scalping calls @100% (both windows).

Modes:
  path  = T1 before structure SL (prev / lesser caps)
  mfe   = target reached (MFE>=T1); SL = insurance

Builds micro-cells, keeps both-100, greedy-unions for max calls (with gap).

  python -u prod_live/tests/builders/research_nifty_1m_scalp_multicall_100.py
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
REPORT_MD = OUT / "NIFTY_1M_SCALP_MULTICALL_100.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_MULTICALL_100.json"
PACK_OUT = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_multicall_100"


def lesser(e: dict, st: str) -> float:
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


def tags(e: dict) -> dict:
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


def cell_key(e: dict, geom: bool = False) -> tuple:
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


def ensure_path(events: List[dict], h, l, c, styles: List[str], t1s: List[float]) -> None:
    t0 = time.time()
    for i, e in enumerate(events):
        if i and i % 20000 == 0:
            print(f"    path {i}/{len(events)} ({time.time()-t0:.0f}s)", flush=True)
        for st in styles:
            sl = lesser(e, st)
            e[f"sl_{st}"] = float(sl)
            for t1 in t1s:
                key = f"{st}_t{int(t1)}"
                if key in e and e[key] in ("win", "sl", "time", "bad_sl"):
                    # may already have prev/sig from cache with different naming
                    pass
                if st == "prev" and f"prev_t{int(t1)}" in e:
                    e[key] = e[f"prev_t{int(t1)}"]
                    continue
                if st == "sig" and f"sig_t{int(t1)}" in e:
                    e[key] = e[f"sig_t{int(t1)}"]
                    continue
                if sl < 4.0:
                    e[key] = "bad_sl"
                    continue
                win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], float(sl), float(t1))
                e[key] = "win" if (win and out == "t1") else out


def bucket(events: List[dict]) -> Dict[tuple, List[dict]]:
    out = defaultdict(list)
    for e in events:
        if not (4 <= e["sl_prev"] <= 20):
            continue
        out[cell_key(e, False)].append(e)
        out[cell_key(e, True)].append(e)
    return out


def all_pass(rows: List[dict], mode: str, path_key: str, t1: float) -> bool:
    if mode == "path":
        return all(e.get(path_key) == "win" for e in rows)
    return all(e["mfe"] >= t1 for e in rows)


def apply_gap(rows: List[dict], gap: int) -> List[dict]:
    last = {}
    out = []
    for e in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        prev = last.get(e["day"])
        if prev is not None and e["mins"] - prev < gap:
            continue
        out.append(e)
        last[e["day"]] = e["mins"]
    return out


def hunt_cells(
    cal_b: Dict[tuple, List[dict]],
    test_b: Dict[tuple, List[dict]],
    path_key: str,
    mode: str,
    gap: int,
    min_cal: int = 4,
    min_l3m: int = 3,
    max_avg_sl: float = 12.0,
) -> List[dict]:
    t1 = float(path_key.split("_t")[-1])
    st = path_key.rsplit("_t", 1)[0]
    cells = []
    for k, ces in cal_b.items():
        cal_rows = apply_gap(ces, gap)
        if len(cal_rows) < min_cal:
            continue
        if not all_pass(cal_rows, mode, path_key, t1):
            continue
        tes = test_b.get(k, [])
        test_rows = apply_gap(tes, gap)
        if len(test_rows) < min_l3m:
            continue
        if not all_pass(test_rows, mode, path_key, t1):
            continue
        avg_sl = sum(e.get(f"sl_{st}", e["sl_prev"]) for e in test_rows) / len(test_rows)
        if avg_sl > max_avg_sl:
            continue
        path_w = sum(1 for e in test_rows if e.get(path_key) == "win") / len(test_rows)
        cells.append(
            {
                "k": k,
                "st": st,
                "t1": t1,
                "mode": mode,
                "gap": gap,
                "path_key": path_key,
                "cal_n": len(cal_rows),
                "l3m_n": len(test_rows),
                "cal_days": len({e["day"] for e in cal_rows}),
                "l3m_days": len({e["day"] for e in test_rows}),
                "avg_sl": avg_sl,
                "path_win": path_w,
                "cal_calls": cal_rows,
                "l3m_calls": test_rows,
                "cal_dayset": {e["day"] for e in cal_rows},
                "l3m_dayset": {e["day"] for e in test_rows},
            }
        )
    cells.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"], r["avg_sl"]))
    return cells


def greedy_union(cells: List[dict], gap: int) -> Tuple[List[dict], List[dict], List[dict]]:
    """Union micros; avoid overlapping same (day,mins) call; allow multi/day via gap."""
    chosen = []
    used_cal = set()  # (day, mins)
    used_l3m = set()

    def free(calls, used):
        out = []
        last = {}
        for e in sorted(calls, key=lambda x: (x["day"], x["mins"])):
            key = (e["day"], e["mins"])
            if key in used:
                continue
            prev = last.get(e["day"])
            if prev is not None and e["mins"] - prev < gap:
                continue
            # also check against already-used same day mins spacing
            day_used = sorted(m for (d, m) in used if d == e["day"])
            if any(abs(e["mins"] - m) < gap for m in day_used):
                continue
            out.append(e)
            last[e["day"]] = e["mins"]
        return out

    for r in cells:
        cal_keep = free(r["cal_calls"], used_cal)
        l3m_keep = free(r["l3m_calls"], used_l3m)
        if len(cal_keep) < 2 or len(l3m_keep) < 2:
            continue
        # re-check 100% on kept (should still hold)
        t1 = r["t1"]
        if r["mode"] == "path":
            if any(e.get(r["path_key"]) != "win" for e in cal_keep + l3m_keep):
                continue
        else:
            if any(e["mfe"] < t1 for e in cal_keep + l3m_keep):
                continue
        chosen.append({**r, "cal_calls": cal_keep, "l3m_calls": l3m_keep, "cal_n": len(cal_keep), "l3m_n": len(l3m_keep)})
        for e in cal_keep:
            used_cal.add((e["day"], e["mins"]))
        for e in l3m_keep:
            used_l3m.add((e["day"], e["mins"]))

    cal_all = []
    l3m_all = []
    for r in chosen:
        cal_all.extend(r["cal_calls"])
        l3m_all.extend(r["l3m_calls"])
    cal_all = sorted(cal_all, key=lambda x: (x["day"], x["mins"]))
    l3m_all = sorted(l3m_all, key=lambda x: (x["day"], x["mins"]))
    return chosen, cal_all, l3m_all


def summarize(calls: List[dict], st: str, t1: float, mode: str, path_key: str) -> dict:
    n = len(calls)
    days = len({e["day"] for e in calls})
    if mode == "path":
        wins = sum(1 for e in calls if e.get(path_key) == "win")
    else:
        wins = sum(1 for e in calls if e["mfe"] >= t1)
    sls = [e.get(f"sl_{st}", e["sl_prev"]) for e in calls]
    by_day = defaultdict(int)
    for e in calls:
        by_day[e["day"]] += 1
    multi_days = sum(1 for v in by_day.values() if v >= 2)
    return {
        "n": n,
        "days": days,
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else 0,
        "avg_sl": round(sum(sls) / len(sls), 2) if sls else 0,
        "med_sl": round(sorted(sls)[len(sls) // 2], 2) if sls else 0,
        "calls_per_day": round(n / days, 2) if days else 0,
        "multi_call_days": multi_days,
        "max_calls_one_day": max(by_day.values()) if by_day else 0,
    }


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · SCALP MULTI-CALL 100%", flush=True)
    print("=" * 60, flush=True)
    PACK_OUT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    blob = pickle.load(next(PACK.glob("scalp_events_*.pkl")).open("rb"))
    cal, test = blob["cal"], blob["test"]
    print(f"events cal={len(cal)} last3m={len(test)}", flush=True)

    print("load bars…", flush=True)
    raw = base.load_existing_1m()
    h = raw["High"].astype(float).values
    l = raw["Low"].astype(float).values
    c = raw["Close"].astype(float).values

    styles = ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "p75"]
    t1s = [10.0, 20.0]
    print("enrich lesser-SL paths…", flush=True)
    ensure_path(cal, h, l, c, styles, t1s)
    ensure_path(test, h, l, c, styles, t1s)

    cal_b, test_b = bucket(cal), bucket(test)
    print(f"cells cal={len(cal_b)} test_keys overlapping later", flush=True)

    results = {
        "path_cells": [],
        "mfe_cells": [],
        "unions": {},
    }

    best_path_union = None
    best_mfe_union = None

    for gap in (10, 15, 20, 30):
        for st in styles:
            for t1 in t1s:
                path_key = f"{st}_t{int(t1)}"
                pc = hunt_cells(cal_b, test_b, path_key, "path", gap, min_cal=4, min_l3m=3, max_avg_sl=12)
                mc = hunt_cells(cal_b, test_b, path_key, "mfe", gap, min_cal=4, min_l3m=3, max_avg_sl=12)
                print(
                    f"  gap{gap} {path_key}: path_cells={len(pc)} mfe_cells={len(mc)}",
                    flush=True,
                )
                if pc:
                    results["path_cells"].append(
                        {
                            "gap": gap,
                            "key": path_key,
                            "n_cells": len(pc),
                            "top": [
                                {
                                    "k": str(r["k"]),
                                    "cal_n": r["cal_n"],
                                    "l3m_n": r["l3m_n"],
                                    "avg_sl": round(r["avg_sl"], 2),
                                    "cal_days": r["cal_days"],
                                    "l3m_days": r["l3m_days"],
                                }
                                for r in pc[:8]
                            ],
                        }
                    )
                if mc:
                    results["mfe_cells"].append(
                        {
                            "gap": gap,
                            "key": path_key,
                            "n_cells": len(mc),
                            "top": [
                                {
                                    "k": str(r["k"]),
                                    "cal_n": r["cal_n"],
                                    "l3m_n": r["l3m_n"],
                                    "avg_sl": round(r["avg_sl"], 2),
                                    "path_win": round(r["path_win"] * 100, 1),
                                }
                                for r in mc[:8]
                            ],
                        }
                    )

                if pc:
                    ch, ca, la = greedy_union(pc, gap)
                    # unify path_key for summary — mixed styles possible; tag each call
                    # evaluate per-call with its cell path_key
                    def pack_calls(calls, cells_chosen):
                        # attach path_key from owning cell
                        owned = []
                        for r in cells_chosen:
                            for e in r["cal_calls"] if False else []:
                                pass
                        return calls

                    # build annotated lists
                    cal_ann, l3m_ann = [], []
                    for r in ch:
                        for e in r["cal_calls"]:
                            ee = dict(e)
                            ee["_pk"] = r["path_key"]
                            ee["_st"] = r["st"]
                            ee["_t1"] = r["t1"]
                            cal_ann.append(ee)
                        for e in r["l3m_calls"]:
                            ee = dict(e)
                            ee["_pk"] = r["path_key"]
                            ee["_st"] = r["st"]
                            ee["_t1"] = r["t1"]
                            l3m_ann.append(ee)
                    # verify 100
                    ok = all(e.get(e["_pk"]) == "win" for e in cal_ann + l3m_ann)
                    if ok and la:
                        sc = summarize(cal_ann, "prev", 10, "path", "prev_t10")
                        # custom summarize
                        def sum2(xs):
                            n = len(xs)
                            days = len({e["day"] for e in xs})
                            sls = [e.get(f"sl_{e['_st']}", e["sl_prev"]) for e in xs]
                            by = defaultdict(int)
                            for e in xs:
                                by[e["day"]] += 1
                            return {
                                "n": n,
                                "days": days,
                                "hit_pct": 100.0,
                                "avg_sl": round(sum(sls) / n, 2) if n else 0,
                                "calls_per_day": round(n / days, 2) if days else 0,
                                "multi_call_days": sum(1 for v in by.values() if v >= 2),
                                "max_calls_one_day": max(by.values()) if by else 0,
                                "micros": len(ch),
                            }

                        u = {
                            "mode": "path",
                            "gap": gap,
                            "seed": path_key,
                            "cal": sum2(cal_ann),
                            "l3m": sum2(l3m_ann),
                            "micros": [
                                {
                                    "k": str(r["k"]),
                                    "st": r["st"],
                                    "t1": r["t1"],
                                    "cal_n": r["cal_n"],
                                    "l3m_n": r["l3m_n"],
                                    "avg_sl": round(r["avg_sl"], 2),
                                }
                                for r in ch[:20]
                            ],
                            "l3m_calls": [
                                {
                                    "day": e["day"],
                                    "hm": e["hm"],
                                    "decision": e["decision"],
                                    "primary": e["primary"],
                                    "st": e["_st"],
                                    "sl": round(e.get(f"sl_{e['_st']}", e["sl_prev"]), 2),
                                    "t1": e["_t1"],
                                }
                                for e in sorted(l3m_ann, key=lambda x: (x["day"], x["mins"]))
                            ],
                        }
                        results["unions"][f"path_g{gap}_{path_key}"] = {
                            "cal": u["cal"],
                            "l3m": u["l3m"],
                            "n_micros": len(ch),
                        }
                        print(
                            f"    PATH union gap{gap} {path_key}: "
                            f"cal {u['cal']['n']}calls/{u['cal']['days']}d · "
                            f"l3m {u['l3m']['n']}calls/{u['l3m']['days']}d · "
                            f"multiDays={u['l3m']['multi_call_days']} micros={len(ch)}",
                            flush=True,
                        )
                        score = (u["l3m"]["n"], u["cal"]["n"], -u["l3m"]["avg_sl"])
                        if best_path_union is None or score > best_path_union[0]:
                            best_path_union = (score, u)

                if mc:
                    ch, ca, la = greedy_union(mc, gap)
                    cal_ann, l3m_ann = [], []
                    for r in ch:
                        for e in r["cal_calls"]:
                            ee = dict(e)
                            ee["_pk"] = r["path_key"]
                            ee["_st"] = r["st"]
                            ee["_t1"] = r["t1"]
                            cal_ann.append(ee)
                        for e in r["l3m_calls"]:
                            ee = dict(e)
                            ee["_pk"] = r["path_key"]
                            ee["_st"] = r["st"]
                            ee["_t1"] = r["t1"]
                            l3m_ann.append(ee)
                    if cal_ann and l3m_ann and all(e["mfe"] >= e["_t1"] for e in cal_ann + l3m_ann):

                        def sum2(xs):
                            n = len(xs)
                            days = len({e["day"] for e in xs})
                            sls = [e.get(f"sl_{e['_st']}", e["sl_prev"]) for e in xs]
                            by = defaultdict(int)
                            for e in xs:
                                by[e["day"]] += 1
                            pw = sum(1 for e in xs if e.get(e["_pk"]) == "win") / n
                            return {
                                "n": n,
                                "days": days,
                                "hit_pct": 100.0,
                                "avg_sl": round(sum(sls) / n, 2) if n else 0,
                                "calls_per_day": round(n / days, 2) if days else 0,
                                "multi_call_days": sum(1 for v in by.values() if v >= 2),
                                "max_calls_one_day": max(by.values()) if by else 0,
                                "path_win_pct": round(100 * pw, 1),
                                "micros": len(ch),
                            }

                        u = {
                            "mode": "mfe",
                            "gap": gap,
                            "seed": path_key,
                            "cal": sum2(cal_ann),
                            "l3m": sum2(l3m_ann),
                            "micros": [
                                {
                                    "k": str(r["k"]),
                                    "st": r["st"],
                                    "t1": r["t1"],
                                    "cal_n": r["cal_n"],
                                    "l3m_n": r["l3m_n"],
                                    "avg_sl": round(r["avg_sl"], 2),
                                    "path_win": round(r["path_win"] * 100, 1),
                                }
                                for r in ch[:25]
                            ],
                            "l3m_calls": [
                                {
                                    "day": e["day"],
                                    "hm": e["hm"],
                                    "decision": e["decision"],
                                    "primary": e["primary"],
                                    "st": e["_st"],
                                    "sl": round(e.get(f"sl_{e['_st']}", e["sl_prev"]), 2),
                                    "t1": e["_t1"],
                                    "mfe": round(e["mfe"], 1),
                                    "path": e.get(e["_pk"]),
                                }
                                for e in sorted(l3m_ann, key=lambda x: (x["day"], x["mins"]))
                            ],
                        }
                        results["unions"][f"mfe_g{gap}_{path_key}"] = {
                            "cal": u["cal"],
                            "l3m": u["l3m"],
                            "n_micros": len(ch),
                        }
                        print(
                            f"    MFE  union gap{gap} {path_key}: "
                            f"cal {u['cal']['n']}c/{u['cal']['days']}d · "
                            f"l3m {u['l3m']['n']}c/{u['l3m']['days']}d · "
                            f"multi={u['l3m']['multi_call_days']} "
                            f"pathWin={u['l3m']['path_win_pct']}%",
                            flush=True,
                        )
                        score = (u["l3m"]["n"], u["cal"]["n"], -u["l3m"]["avg_sl"])
                        if best_mfe_union is None or score > best_mfe_union[0]:
                            best_mfe_union = (score, u)

    # Also: cross-style mega union — collect ALL path cells across styles for best gap
    print("\n[C] Cross-style mega unions…", flush=True)
    mega = {}
    for gap in (15, 20):
        all_pc, all_mc = [], []
        for st in styles:
            for t1 in t1s:
                path_key = f"{st}_t{int(t1)}"
                all_pc.extend(
                    hunt_cells(cal_b, test_b, path_key, "path", gap, min_cal=4, min_l3m=3, max_avg_sl=12)
                )
                all_mc.extend(
                    hunt_cells(cal_b, test_b, path_key, "mfe", gap, min_cal=4, min_l3m=3, max_avg_sl=12)
                )
        all_pc.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"], r["avg_sl"]))
        all_mc.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"], r["avg_sl"]))
        # dedupe identical (k, path_key)
        seen = set()
        pc2 = []
        for r in all_pc:
            id_ = (r["k"], r["path_key"])
            if id_ in seen:
                continue
            seen.add(id_)
            pc2.append(r)
        seen = set()
        mc2 = []
        for r in all_mc:
            id_ = (r["k"], r["path_key"])
            if id_ in seen:
                continue
            seen.add(id_)
            mc2.append(r)

        for label, pool, mode in (("path", pc2, "path"), ("mfe", mc2, "mfe")):
            ch, _, _ = greedy_union(pool, gap)
            cal_ann, l3m_ann = [], []
            for r in ch:
                for e in r["cal_calls"]:
                    ee = dict(e)
                    ee["_pk"] = r["path_key"]
                    ee["_st"] = r["st"]
                    ee["_t1"] = r["t1"]
                    cal_ann.append(ee)
                for e in r["l3m_calls"]:
                    ee = dict(e)
                    ee["_pk"] = r["path_key"]
                    ee["_st"] = r["st"]
                    ee["_t1"] = r["t1"]
                    l3m_ann.append(ee)
            if not cal_ann or not l3m_ann:
                continue
            if mode == "path" and not all(e.get(e["_pk"]) == "win" for e in cal_ann + l3m_ann):
                continue
            if mode == "mfe" and not all(e["mfe"] >= e["_t1"] for e in cal_ann + l3m_ann):
                continue

            def sum2(xs):
                n = len(xs)
                days = len({e["day"] for e in xs})
                sls = [e.get(f"sl_{e['_st']}", e["sl_prev"]) for e in xs]
                by = defaultdict(int)
                for e in xs:
                    by[e["day"]] += 1
                pw = sum(1 for e in xs if e.get(e["_pk"]) == "win") / n
                return {
                    "n": n,
                    "days": days,
                    "hit_pct": 100.0,
                    "avg_sl": round(sum(sls) / n, 2),
                    "calls_per_day": round(n / days, 2),
                    "multi_call_days": sum(1 for v in by.values() if v >= 2),
                    "max_calls_one_day": max(by.values()),
                    "path_win_pct": round(100 * pw, 1),
                    "micros": len(ch),
                }

            u = {
                "mode": mode,
                "gap": gap,
                "seed": "cross_style",
                "cal": sum2(cal_ann),
                "l3m": sum2(l3m_ann),
                "micros": [
                    {
                        "k": str(r["k"]),
                        "st": r["st"],
                        "t1": r["t1"],
                        "cal_n": r["cal_n"],
                        "l3m_n": r["l3m_n"],
                        "avg_sl": round(r["avg_sl"], 2),
                    }
                    for r in ch[:30]
                ],
                "l3m_calls": [
                    {
                        "day": e["day"],
                        "hm": e["hm"],
                        "decision": e["decision"],
                        "primary": e["primary"],
                        "st": e["_st"],
                        "sl": round(e.get(f"sl_{e['_st']}", e["sl_prev"]), 2),
                        "t1": e["_t1"],
                        "mfe": round(e["mfe"], 1),
                    }
                    for e in sorted(l3m_ann, key=lambda x: (x["day"], x["mins"]))
                ],
            }
            mega[f"{mode}_g{gap}"] = u
            print(
                f"  MEGA {mode} gap{gap}: cal {u['cal']['n']}c/{u['cal']['days']}d · "
                f"l3m {u['l3m']['n']}c/{u['l3m']['days']}d · "
                f"cpd={u['l3m']['calls_per_day']} multiDays={u['l3m']['multi_call_days']} "
                f"max/day={u['l3m']['max_calls_one_day']} micros={len(ch)}",
                flush=True,
            )
            if mode == "path":
                score = (u["l3m"]["n"], u["cal"]["n"], -u["l3m"]["avg_sl"])
                if best_path_union is None or score > best_path_union[0]:
                    best_path_union = (score, u)
            else:
                score = (u["l3m"]["n"], u["cal"]["n"], -u["l3m"]["avg_sl"])
                if best_mfe_union is None or score > best_mfe_union[0]:
                    best_mfe_union = (score, u)

    # write report
    lines = [
        "# NIFTY 1m — **scalp multi-call 100%**",
        "",
        "**Not live.** Maximize number of scalping calls with **100%** on calibrate + last3m.",
        "",
        "- T1 **10 / 20** · SL = prev candle or lesser (`cap8/10/12`, `min(prev,sig)`, `0.75×prev`)",
        "- Multi-call with time gap 10–30 min",
        "- Two win definitions: **path** (T1 before SL) · **mfe** (target prints; SL insurance)",
        "",
    ]

    if best_path_union:
        u = best_path_union[1]
        lines += [
            "## Best PATH multi-call book (T1 before SL · both 100%)",
            "",
            f"- Gap **{u['gap']}** min · seed `{u['seed']}`",
            f"- Calibrate: **{u['cal']['n']} calls / {u['cal']['days']} days** · "
            f"{u['cal']['calls_per_day']}/day · multi-days {u['cal']['multi_call_days']}",
            f"- Last3m: **{u['l3m']['n']} calls / {u['l3m']['days']} days** · "
            f"{u['l3m']['calls_per_day']}/day · multi-days {u['l3m']['multi_call_days']} · "
            f"max/day {u['l3m']['max_calls_one_day']} · avg SL {u['l3m']['avg_sl']}",
            f"- Micros used: **{u['l3m'].get('micros', len(u.get('micros', [])))}**",
            "",
            "### Micros",
            "",
            "| Cal | L3m | AvgSL | Exit | Cell |",
            "|---:|---:|---:|---|---|",
        ]
        for r in u.get("micros", [])[:20]:
            lines.append(
                f"| {r['cal_n']} | {r['l3m_n']} | {r['avg_sl']} | `{r['st']}_t{int(r['t1'])}` | `{r['k']}` |"
            )
        lines += [
            "",
            "### Last3m calls",
            "",
            "| Day | HM | Side | Pattern | SL style | SL | T1 |",
            "|---|---|---|---|---|---:|---:|",
        ]
        for e in u.get("l3m_calls", [])[:60]:
            lines.append(
                f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"`{e['st']}` | {e['sl']} | {e['t1']} |"
            )
        if len(u.get("l3m_calls", [])) > 60:
            lines.append(f"| … | | | | | | {len(u['l3m_calls'])-60} more |")

    if best_mfe_union:
        u = best_mfe_union[1]
        lines += [
            "",
            "## Best TARGET-REACHED multi-call book (MFE≥T1 · both 100%)",
            "",
            f"- Gap **{u['gap']}** · seed `{u['seed']}`",
            f"- Calibrate: **{u['cal']['n']} calls / {u['cal']['days']} days** · "
            f"{u['cal']['calls_per_day']}/day · multi-days {u['cal']['multi_call_days']}",
            f"- Last3m: **{u['l3m']['n']} calls / {u['l3m']['days']} days** · "
            f"{u['l3m']['calls_per_day']}/day · multi-days {u['l3m']['multi_call_days']} · "
            f"max/day {u['l3m']['max_calls_one_day']} · avg SL {u['l3m']['avg_sl']} · "
            f"path-win {u['l3m'].get('path_win_pct', '?')}%",
            "",
            "### Top micros",
            "",
            "| Cal | L3m | AvgSL | Path% | Exit | Cell |",
            "|---:|---:|---:|---:|---|---|",
        ]
        for r in u.get("micros", [])[:20]:
            lines.append(
                f"| {r['cal_n']} | {r['l3m_n']} | {r['avg_sl']} | {r.get('path_win', '')} | "
                f"`{r['st']}_t{int(r['t1'])}` | `{r['k']}` |"
            )
        lines += [
            "",
            "### Last3m sample calls",
            "",
            "| Day | HM | Side | Pattern | SL | T1 | MFE |",
            "|---|---|---|---|---:|---:|---:|",
        ]
        for e in u.get("l3m_calls", [])[:40]:
            lines.append(
                f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"{e['sl']} | {e['t1']} | {e.get('mfe', '')} |"
            )

    lines += [
        "",
        "## Policy",
        "",
        "- research_only · not_live · multi-scalp · structure SL",
        f"- Pack: `{PACK_OUT}`",
        f"- Source events: `{PACK}`",
        "",
    ]

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {
        "best_path": best_path_union[1] if best_path_union else None,
        "best_mfe": best_mfe_union[1] if best_mfe_union else None,
        "mega": {k: {"cal": v["cal"], "l3m": v["l3m"]} for k, v in mega.items()},
        "union_index": results["unions"],
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (PACK_OUT / "multicall_summary.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nWrote {REPORT_MD}", flush=True)
    print("DONE multicall 100%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
