"""Phase-2G RESEARCH — P2F day logic with dual = **10m train** model · 1y test.

Same as P2F: hard floors · Phase-1 bases · day merge (1/day) · path good/crown/champ.
Different: dual universe = D10 (10m dual-train scored tickets), not D15/D5.

  python -u prod_live/tests/builders/research_acc_phase2g_10m_1y.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _hm_mins, _side  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    bestp_day,
    filt,
    first_day,
    gap_map,
    is_perfect,
    union_unique_days,
)
from prod_live.logic.accurate_desks import build_all_accurate_desks  # noqa: E402
from prod_live.logic.p2g_10m import (  # noqa: E402
    ACCURACY_TAG_BY_DESK,
    BASE_KEY_BY_DESK,
    DAY_DESKS,
    HARD_GATES,
    LOGIC_LEVEL,
    P2F_1Y_REF,
    WINDOW_1Y,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
HOLD = ROOT / "prod_live" / "holding_accurate"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"
CACHE_XY = LEDGER / "_cache_dual10m_xy_research.json"
PACKS = LEDGER / "nifty_side_models_10m_research" / "dual10m_packs.joblib"
RECIPES_OUT = HOLD / "phase2g" / "recipes_research.json"

END = WINDOW_1Y["end"]
START_1Y = WINDOW_1Y["start"]
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
MIN_N = 3

# Lighter grid than full P2F (runtime) — same filter family
BANDS = [
    ("first45", 9 * 60 + 15, 10 * 60),
    ("open", 9 * 60 + 15, 10 * 60 + 30),
    ("am1130", 9 * 60 + 15, 11 * 60 + 30),
    ("am1230", 9 * 60 + 15, 12 * 60 + 30),
    ("mid", 10 * 60, 13 * 60),
    ("latemid", 10 * 60 + 30, 14 * 60),
    ("pm", 12 * 60 + 30, 15 * 60 + 15),
    ("all", None, None),
]
GAPS = [
    ("nogap", None, False, False),
    ("g020", 0.20, False, False),
    ("g030", 0.30, False, False),
    ("g040", 0.40, False, False),
    ("g055", 0.55, False, False),
    ("gdn025", 0.25, True, False),
    ("gdn040", 0.40, True, False),
    ("gup025", 0.25, False, True),
    ("gup040", 0.40, False, True),
]
PMINS = (0.0, 0.50, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70, 0.72, 0.75)


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 4)


def desk_ok(rows: List[dict], floor: float) -> bool:
    rs3 = _clip(rows, START_3Y, END)
    if floor >= 100.0:
        if not (rs3 and is_perfect(rs3)):
            return False
        rs1 = _clip(rows, START_1Y, END)
        if len(rs1) >= MIN_N and not is_perfect(rs1):
            return False
        return True
    if len(rs3) >= MIN_N and hit_pct(rs3) + 1e-9 < floor:
        return False
    rs1 = _clip(rows, START_1Y, END)
    if len(rs1) >= MIN_N and hit_pct(rs1) + 1e-9 < max(floor - 2.0, 70.0):
        return False
    return True


def stream_ok(rows: List[dict], floor: float) -> bool:
    rs3 = _clip(rows, START_3Y, END)
    if len(rs3) < MIN_N:
        return False
    if floor >= 100.0:
        return is_perfect(rs3)
    return hit_pct(rs3) + 1e-9 >= floor


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


def mid_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")].append(r)
    out = []
    for day in sorted(by):
        ordered = sorted(by[day], key=lambda x: _hm_mins(str(x.get("hm") or "99:99")))
        out.append(ordered[len(ordered) // 2])
    return out


def load_d10() -> List[dict]:
    """Score all 10m dual-train tickets → D10 universe."""
    import joblib

    packs = joblib.load(PACKS)
    xy = json.loads(CACHE_XY.read_text(encoding="utf-8"))
    tickets = xy.get("tickets") or []
    out: List[dict] = []
    for r in tickets:
        side = str(r.get("decision") or "").upper()
        pack = packs.get(side) or {}
        if not pack.get("available"):
            continue
        x = r.get("x")
        if not x:
            continue
        X = np.asarray([x], dtype=float)
        raw = float(pack["base"].predict_proba(X)[0, 1])
        p = float(np.clip(pack["iso"].transform([raw])[0], 0.05, 0.95))
        rr = {k: v for k, v in r.items() if k != "x"}
        rr["p_t1"] = round(p, 4)
        rr["track"] = "dual10m"
        rr["tf"] = "10m"
        rr["src_model"] = "dual10m_train"
        out.append(rr)
    print(f"  D10 scored n={len(out)} hit={_agg(out).get('hit_pct')}", flush=True)
    return out


def universes_p2g(path_u, d10, champ) -> Dict[str, List[dict]]:
    u: Dict[str, List[dict]] = {}
    for rk, rows in (path_u.get("crown_by_risk") or {}).items():
        if not str(rk).startswith("_"):
            u[f"CR{str(rk).replace('.0', '')}"] = rows
    for rk, rows in (path_u.get("good_by_risk") or {}).items():
        if not str(rk).startswith("_") and rk != "native":
            u[f"GD{str(rk).replace('.0', '')}"] = rows
    u["CH"] = path_u.get("champ_native") or champ
    u["D10"] = d10  # replaces D15/D5
    return u


def mine_streams(univ: Dict[str, List[dict]], gaps, active, floor_min: float):
    # Focus universes: D10 + key path (same family as P2F, dual swapped)
    keys = [k for k in ("D10", "CH", "CR20", "CR30", "GD30", "GD40") if k in univ]
    streams: List[Tuple[str, List[dict]]] = []
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
                                ("mid", mid_day(base)),
                                ("last", last_day(base)),
                            ):
                                if not vrows:
                                    continue
                                n_eval += 1
                                if not stream_ok(vrows, floor_min):
                                    continue
                                tag = (
                                    f"G_{uname}_{side or 'BOTH'}_p{int(round(pmin * 100))}_"
                                    f"{blab}_{'htf' if use_htf else 'any'}_{glab}_{vlab}"
                                )
                                streams.append((tag, vrows))
    print(f"  mined eval={n_eval} keep={len(streams)} floor>={floor_min}", flush=True)
    # dedupe by tag keep max n
    by = {}
    for tag, rows in streams:
        n = len(_clip(rows, START_3Y, END))
        if tag not in by or n > len(_clip(by[tag], START_3Y, END)):
            by[tag] = rows
    out = sorted(
        by.items(),
        key=lambda kv: (hit_pct(_clip(kv[1], START_3Y, END)), len(_clip(kv[1], START_3Y, END))),
        reverse=True,
    )
    return out


def greedy_expand(
    seed: List[dict],
    streams: List[Tuple[str, List[dict]]],
    floor: float,
    *,
    max_add: int = 120,
) -> Tuple[List[dict], List[str]]:
    cur = list(seed)
    used: List[str] = []
    if not desk_ok(cur, floor):
        # if phase1 seed fails floor on window, start empty and build from streams only
        cur = []
    improved = True
    while improved and len(used) < max_add:
        improved = False
        best = None
        best_n = len(_clip(cur, START_3Y, END))
        for tag, rows in streams:
            if tag in used:
                continue
            merged = union_unique_days(cur, rows)
            if len(_clip(merged, START_3Y, END)) <= best_n:
                continue
            if not desk_ok(merged, floor):
                continue
            best = (tag, merged)
            best_n = len(_clip(merged, START_3Y, END))
        if best:
            used.append(best[0])
            cur = best[1]
            improved = True
            if len(used) <= 8 or len(used) % 15 == 0:
                print(
                    f"    +{best[0][:64]} → 3y n={len(_clip(cur, START_3Y, END))} "
                    f"hit={hit_pct(_clip(cur, START_3Y, END))}",
                    flush=True,
                )
    return cur, used


def stamp(rows: List[dict], desk: str) -> List[dict]:
    ar = ACCURACY_TAG_BY_DESK.get(desk, "")
    floor = HARD_GATES[desk]
    tags = [desk, ar, f"LOGIC_{LOGIC_LEVEL}", "LANE_RESEARCH", "MODE_DAY", "DUAL_10M"]
    out = []
    for r in rows:
        rr = dict(r)
        rr["desk_tag"] = desk
        rr["accurate_tag"] = desk
        rr["accuracy_tag"] = ar
        rr["logic_level"] = LOGIC_LEVEL
        rr["lane"] = "RESEARCH"
        rr["status"] = "RESEARCH"
        rr["mode"] = "day"
        rr["hard_gate"] = floor
        existing = list(rr.get("tags") or [])
        seen = set(existing)
        for t in tags:
            if t and t not in seen:
                existing.append(t)
                seen.add(t)
        rr["tags"] = existing
        out.append(rr)
    return out


def main() -> int:
    t0 = time.time()
    print(f"P2G_10M RESEARCH 1y {START_1Y} → {END}", flush=True)

    dual = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_3Y < d <= END]
    active = fs._active_days(sess, fs._load_daily()) if sess else set()

    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ = _champ_floor([dict(r, track="champion") for r in dual["dual15"]["champion"]])
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]
    champ_native = path_u.get("champ_native") or champ

    print("  Phase-1 bases…", flush=True)
    phase1 = build_all_accurate_desks(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=path_u.get("crown_by_risk") or {},
        good_by_risk=path_u.get("good_by_risk") or {},
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active,
    )

    print("  load/score D10 (10m dual train)…", flush=True)
    d10 = load_d10()
    univ = universes_p2g(path_u, d10, champ_native)
    print(f"  universes: {list(univ.keys())}", flush=True)

    # Mine once at softest floor; filter per desk
    print("  mine streams (floor>=82.71)…", flush=True)
    streams_all = mine_streams(univ, gaps, active, floor_min=82.71)

    recipes: Dict[str, Any] = {
        "status": "RESEARCH",
        "phase": "2g",
        "dual_model": "10m_train",
        "not_live": True,
        "window_1y": WINDOW_1Y,
        "candidates": {},
    }
    results: Dict[str, Any] = {}
    lines = [
        "# Phase-2G RESEARCH — 10m dual train · P2F-style day desks · 1y",
        "",
        "**Status:** RESEARCH · **not live**",
        "**Logic:** same as P2F (hard floors · 1 call/day · Phase-1 seed · path GD/CR/CH)",
        "**Dual:** `D10` = 10m dual-train HGB BUY/SELL (replaces D15/D5)",
        "",
        f"**Window 1y:** `{START_1Y}` → `{END}` · 3y gate `{START_3Y}` → `{END}`",
        f"D10 universe n={len(d10)} · mined streams={len(streams_all)}",
        "",
        "## Desk ladder (1y vs P2F ref)",
        "",
        "| P2G desk | Floor | 3y N@hit | 1y N@hit | Streams | vs P2F 1y |",
        "|---|---:|---|---|---:|---|",
    ]

    for desk in DAY_DESKS:
        floor = HARD_GATES[desk]
        base_key = BASE_KEY_BY_DESK[desk]
        seed = list(phase1.get(base_key) or [])
        print(f"  expand {desk} floor={floor} seed={len(seed)}…", flush=True)
        # streams that clear this floor
        usable = [(t, r) for t, r in streams_all if stream_ok(r, floor)]
        rows, tags = greedy_expand(seed, usable, floor)
        rows = stamp(rows, desk)
        sc3 = _agg(_clip(rows, START_3Y, END))
        sc1 = _agg(_clip(rows, START_1Y, END))
        # map to p2f ref by floor family
        p2f_name = {
            100.0: "ACC100_MULTI_V11",
            99.24: "ACC_WIDE_P92_P2F",
            95.4: "ACC_WIDE_P90_P2F",
            89.69: "ACC_WIDE_P85_P2F",
            88.4: "ACC_WIDE_P85B_P2F",
            84.72: "ACC_WIDE_P80_P2F",
            82.71: "ACC_WIDE_P75_P2F",
        }.get(floor)
        ref = P2F_1Y_REF.get(p2f_name or "", {})
        ref_s = f"{ref.get('n')}@{ref.get('hit_pct')}" if ref else "—"
        ok = desk_ok(rows, floor)
        results[desk] = {
            "floor": floor,
            "base": base_key,
            "ok": ok,
            "streams": tags,
            "n_streams": len(tags),
            "3y": sc3,
            "1y": sc1,
            "p2f_ref_1y": ref,
        }
        recipes["candidates"][base_key] = {
            "base_desk": base_key,
            "mode": "day",
            "candidate_tag": desk,
            "hard_gate": floor,
            "dual_model": "10m_train",
            "stream_tags_research": tags,
            "research_1y": {"n": sc1.get("n"), "hit_pct": sc1.get("hit_pct")},
            "research_3y": {"n": sc3.get("n"), "hit_pct": sc3.get("hit_pct")},
        }
        lines.append(
            f"| `{desk}` | {floor} | {sc3.get('n')}@{sc3.get('hit_pct')} | "
            f"{sc1.get('n')}@{sc1.get('hit_pct')} | {len(tags)} | {ref_s} |"
        )
        print(
            f"    → 1y {sc1.get('n')}@{sc1.get('hit_pct')}% 3y {sc3.get('n')}@{sc3.get('hit_pct')}% "
            f"streams={len(tags)} ok={ok}",
            flush=True,
        )

    # sample top desk 1y calls
    top = DAY_DESKS[0]
    top_rows = stamp(
        # rebuild from recipes last candidate — use results streams already applied via greedy;
        # re-run expand quickly from saved recipe for sample
        [],
        top,
    )
    # recover from last expand stored in results — need actual rows; re-expand once for sample
    seed0 = list(phase1.get(BASE_KEY_BY_DESK[top]) or [])
    usable0 = [(t, r) for t, r in streams_all if stream_ok(r, HARD_GATES[top])]
    sample_rows, _ = greedy_expand(seed0, usable0, HARD_GATES[top])
    sample_rows = stamp(sample_rows, top)

    lines.extend(
        [
            "",
            f"## Sample 1y calls — `{top}`",
            "",
            "| Day | HM | Side | Win | p |",
            "|---|---|---|---|---:|",
        ]
    )
    for r in sorted(_clip(sample_rows, START_1Y, END), key=lambda x: (x.get("day"), x.get("hm")))[:40]:
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {_side(r)} | "
            f"{'W' if r.get('win') else 'L'} | {r.get('p_t1')} |"
        )

    # verdict
    best = results.get(DAY_DESKS[0], {})
    b1 = best.get("1y") or {}
    ref100 = P2F_1Y_REF["ACC100_MULTI_V11"]
    if best.get("ok") and (b1.get("n") or 0) >= ref100["n"] and float(b1.get("hit_pct") or 0) >= 99.9:
        verdict = (
            f"PROMISING — P2G 100% desk {b1.get('n')}@100% on 1y ≥ P2F V11 "
            f"{ref100['n']}@100%. Still RESEARCH."
        )
    elif best.get("ok") and (b1.get("n") or 0) >= 20:
        verdict = (
            f"PARTIAL — P2G 100% desk alive ({b1.get('n')}@{b1.get('hit_pct')}% 1y) "
            f"but below P2F V11 ({ref100['n']}@100%)."
        )
    elif any(results[d].get("ok") for d in DAY_DESKS):
        verdict = "THIN — some P2G floors clear, but dual-10m does not match P2F dual-15 volume yet."
    else:
        verdict = "FAIL soft — P2G_10m could not hold P2F floors with useful N; keep P2F/dual15."

    payload = {
        "status": "RESEARCH",
        "not_live": True,
        "phase": "2g",
        "dual_model": "10m_train",
        "window": WINDOW_1Y,
        "results": results,
        "verdict": verdict,
        "elapsed_s": round(time.time() - t0, 1),
    }
    lines.extend(["", "## Verdict", "", verdict, "", f"Elapsed {payload['elapsed_s']}s", ""])

    OUT.mkdir(parents=True, exist_ok=True)
    (HOLD / "phase2g").mkdir(parents=True, exist_ok=True)
    RECIPES_OUT.write_text(json.dumps(recipes, indent=2, default=str), encoding="utf-8")
    md = OUT / "ACC_PHASE2G_10M_1Y.md"
    js = OUT / "ACC_PHASE2G_10M_1Y.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
