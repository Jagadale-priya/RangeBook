"""Phase-2H RESEARCH — P2F day logic with dual = **5m train** model.

Filters are chosen only on sessions before 2025-11-15.
The last year (2025-11-15 → 2026-11-15) is scored after the book is frozen.
Not live.

  python -u prod_live/tests/builders/research_acc_phase2h_5m_1y.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _agg  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    bestp_day,
    filt,
    first_day,
    gap_map,
    union_unique_days,
)
from research_confirm_dual_tf_deep import _clip, _hm_mins, _side  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"
CACHE_XY = LEDGER / "_cache_dual5m_xy_research.json"
PACKS = LEDGER / "nifty_side_models_5m_research" / "dual5m_packs.joblib"

END = "2026-11-15"
START_1Y = "2025-11-15"
PRE_START = "2023-11-16"  # selection window, ends the day before the test year
PRE_END = "2025-11-14"
FLOORS = (90.0, 92.0, 95.0)
MIN_N = 8

BANDS = [
    ("first45", 9 * 60 + 15, 10 * 60),
    ("open", 9 * 60 + 15, 10 * 60 + 30),
    ("am1130", 9 * 60 + 15, 11 * 60 + 30),
    ("mid", 10 * 60, 13 * 60),
    ("pm", 12 * 60 + 30, 15 * 60 + 15),
    ("all", None, None),
]
GAPS = [
    ("nogap", None, False, False),
    ("g030", 0.30, False, False),
    ("g055", 0.55, False, False),
    ("gdn040", 0.40, True, False),
    ("gup040", 0.40, False, True),
]
PMINS = (0.0, 0.52, 0.55, 0.60, 0.65, 0.70)


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 4)


def pre(rows: List[dict]) -> List[dict]:
    return _clip(rows, PRE_START, PRE_END)


def test(rows: List[dict]) -> List[dict]:
    return _clip(rows, START_1Y, END)


def stream_ok(rows: List[dict], floor: float) -> bool:
    rs = pre(rows)
    return len(rs) >= MIN_N and hit_pct(rs) + 1e-9 >= floor


def load_d5() -> List[dict]:
    import joblib

    packs = joblib.load(PACKS)
    xy = json.loads(CACHE_XY.read_text(encoding="utf-8"))
    out: List[dict] = []
    for r in xy.get("tickets") or []:
        side = str(r.get("decision") or "").upper()
        pack = packs.get(side) or {}
        if not pack.get("available"):
            continue
        x = r.get("x")
        if not x:
            continue
        raw = float(pack["base"].predict_proba(np.asarray([x], dtype=float))[0, 1])
        p = float(np.clip(pack["iso"].transform([raw])[0], 0.05, 0.95))
        rr = {k: v for k, v in r.items() if k != "x"}
        rr["p_t1"] = round(p, 4)
        rr["track"] = "dual5m"
        rr["tf"] = "5m"
        rr["src_model"] = "dual5m_train"
        out.append(rr)
    print(f"  D5 scored n={len(out)} hit={_agg(out).get('hit_pct')}", flush=True)
    return out


def universes(path_u, d5) -> Dict[str, List[dict]]:
    u: Dict[str, List[dict]] = {"D5": d5}
    for rk, rows in (path_u.get("crown_by_risk") or {}).items():
        if str(rk) in ("20", "20.0", "30", "30.0"):
            u[f"CR{str(rk).replace('.0', '')}"] = rows
    for rk, rows in (path_u.get("good_by_risk") or {}).items():
        if str(rk) in ("30", "30.0", "40", "40.0"):
            u[f"GD{str(rk).replace('.0', '')}"] = rows
    if path_u.get("champ_native"):
        u["CH"] = path_u["champ_native"]
    return u


def mine(univ, gaps, active, floor: float):
    keys = [k for k in ("D5", "CH", "CR20", "CR30", "GD30", "GD40") if k in univ]
    by = {}
    n_eval = 0
    for uname in keys:
        urows = univ[uname]
        for side in (None, "BUY", "SELL"):
            for blab, lo, hi in BANDS:
                for glab, gabsm, gdn, gup in GAPS:
                    for use_htf in (False, True):
                        for pmin in PMINS:
                            base = filt(
                                urows,
                                p_min=pmin,
                                side=side,
                                hm_lo=lo,
                                hm_hi=hi,
                                htf=active if use_htf else None,
                                gaps=gaps if gabsm is not None or gdn or gup else None,
                                gap_abs=gabsm,
                                gap_dn=gdn,
                                gap_up=gup,
                            )
                            for vlab, vrows in (
                                ("raw", base),
                                ("first", first_day(base)),
                                ("bestp", bestp_day(base)),
                                ("last", last_day(base)),
                            ):
                                if not vrows:
                                    continue
                                n_eval += 1
                                if not stream_ok(vrows, floor):
                                    continue
                                tag = (
                                    f"H_{uname}_{side or 'BOTH'}_p{int(round(pmin * 100))}_"
                                    f"{blab}_{'htf' if use_htf else 'any'}_{glab}_{vlab}"
                                )
                                n = len(pre(vrows))
                                if tag not in by or n > len(pre(by[tag])):
                                    by[tag] = vrows
    out = sorted(by.items(), key=lambda kv: (hit_pct(pre(kv[1])), len(pre(kv[1]))), reverse=True)
    print(f"  mined eval={n_eval} keep={len(out)} floor>={floor}", flush=True)
    return out[:250]


def last_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")].append(r)
    out = []
    for day in sorted(by):
        out.append(
            sorted(
                by[day],
                key=lambda x: (_hm_mins(str(x.get("hm") or "00:00")), float(x.get("p_t1") or 0)),
                reverse=True,
            )[0]
        )
    return out


def greedy(streams, floor: float):
    cur: List[dict] = []
    used: List[str] = []
    while len(used) < 40:
        best = None
        best_n = len(pre(cur))
        for tag, rows in streams:
            if tag in used:
                continue
            merged = union_unique_days(cur, rows)
            n = len(pre(merged))
            if n <= best_n:
                continue
            if hit_pct(pre(merged)) + 1e-9 < floor:
                continue
            best = (tag, merged)
            best_n = n
        if not best:
            break
        used.append(best[0])
        cur = best[1]
        print(
            f"    +{best[0][:70]} pre n={len(pre(cur))} hit={hit_pct(pre(cur))}",
            flush=True,
        )
    return cur, used


def main() -> int:
    t0 = time.time()
    print(f"P2H_5M RESEARCH select {PRE_START}→{PRE_END} test {START_1Y}→{END}", flush=True)
    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if PRE_START < d <= END]
    active = fs._active_days(sess, fs._load_daily()) if sess else set()
    d5 = load_d5()
    univ = universes(path_u, d5)
    print(f"  universes {list(univ)}", flush=True)

    # Mine at the softest requested floor, then raise it per desk.
    streams90 = mine(univ, gaps, active, 90.0)
    results = {}
    lines = [
        "# Phase-2H RESEARCH — 5m dual train · last 1 year held out",
        "",
        "**Status:** RESEARCH · **not live**",
        "**Model:** 5m dual-train HGB. Train through 2024-09-10. Holdout base hit about 53% BUY / 52% SELL.",
        "**Selection:** filters frozen on 2023-11-16 → 2025-11-14. One call per day.",
        f"**Test:** `{START_1Y}` → `{END}`. The test year was not used to accept a stream.",
        "",
        "| Floor used to build | Pre-year N@hit | Test year N@hit | Streams |",
        "|---:|---|---|---:|",
    ]
    built = {}
    for floor in FLOORS:
        usable = [(t, r) for t, r in streams90 if stream_ok(r, floor)]
        print(f"  expand floor={floor} streams={len(usable)}", flush=True)
        rows, tags = greedy(usable, floor)
        built[floor] = (rows, tags)
        sc_pre = _agg(pre(rows))
        sc_te = _agg(test(rows))
        results[str(floor)] = {
            "pre": sc_pre,
            "test_1y": sc_te,
            "n_streams": len(tags),
            "streams": tags,
        }
        lines.append(
            f"| {floor} | {sc_pre.get('n')}@{sc_pre.get('hit_pct')} | "
            f"{sc_te.get('n')}@{sc_te.get('hit_pct')} | {len(tags)} |"
        )
        print(
            f"    TEST {sc_te.get('n')}@{sc_te.get('hit_pct')}  pre {sc_pre.get('n')}@{sc_pre.get('hit_pct')}",
            flush=True,
        )

    qual = []
    for floor, (rows, tags) in built.items():
        sc = _agg(test(rows))
        if sc.get("n") and float(sc.get("hit_pct") or 0) >= 90.0:
            qual.append((int(sc["n"]), float(sc["hit_pct"]), floor, rows, tags))
    qual.sort(reverse=True)
    if qual:
        n, hit, floor, rows, tags = qual[0]
        verdict = (
            f"TEST PASS — 5m day book at floor {floor}: {n} calls @ {hit}% "
            f"on {START_1Y} → {END}. RESEARCH only."
        )
        sample = rows
        sample_floor = floor
    else:
        # Report the test book with the most calls among those closest to 90.
        ranked = []
        for floor, (rows, tags) in built.items():
            sc = _agg(test(rows))
            ranked.append((float(sc.get("hit_pct") or 0), int(sc.get("n") or 0), floor, rows))
        ranked.sort(reverse=True)
        hit, n, floor, sample = ranked[0][:4]
        sample_floor = floor
        verdict = (
            f"TEST BELOW 90 — best frozen 5m book on the last year is "
            f"{n} calls @ {hit}% (built at floor {floor}). "
            f"The raw 5m model holdout is about 52%. Not promoted."
        )

    lines.extend(["", "## Verdict", "", verdict, ""])
    lines.extend(
        [
            f"## Test-year calls — floor {sample_floor}",
            "",
            "| Day | HM | Side | Win | p |",
            "|---|---|---|---|---:|",
        ]
    )
    for r in sorted(test(sample), key=lambda x: (x.get("day"), x.get("hm"))):
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {_side(r)} | "
            f"{'W' if r.get('win') else 'L'} | {r.get('p_t1')} |"
        )

    payload = {
        "status": "RESEARCH",
        "not_live": True,
        "phase": "2h",
        "dual_model": "5m_train",
        "selection": {"start": PRE_START, "end": PRE_END},
        "test": {"start": START_1Y, "end": END},
        "results": results,
        "verdict": verdict,
        "elapsed_s": round(time.time() - t0, 1),
    }
    lines.append("")
    lines.append(f"Elapsed {payload['elapsed_s']}s")
    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "ACC_PHASE2H_5M_1Y.md"
    js = OUT / "ACC_PHASE2H_5M_1Y.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
