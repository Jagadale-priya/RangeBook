"""Phase-2d: KEEP GOING — more calls @ same accuracy.

Phase-1 LOCKED. Phase-2c HELD in prod_live/holding_accurate/.
This phase seeds from held P2c recipes + denser mine + more cap2 desks.

  python -u prod_live/tests/builders/research_acc_phase2d_keep_going.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
import path_setup  # noqa: F401,E402

import pandas as pd  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _hm_mins, _side, _ix  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    filt,
    first_day,
    bestp_day,
    gap_map,
    is_perfect,
    time_agree,
    union_unique_days,
)
from prod_live.logic.accurate_desks import (  # noqa: E402
    DESK_REGISTRY,
    RESEARCH_END,
    build_all_accurate_desks,
)
from prod_live.holding_accurate.registry import recipes as load_held_recipes  # noqa: E402
from prod_live.holding_accurate.phase2c.builders import union_day_cap2  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
HOLD = ROOT / "prod_live" / "holding_accurate"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL_10Y = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH_10Y = LEDGER / "_cache_path_trusted_10y.json"

END = RESEARCH_END
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_5Y = (pd.Timestamp(END) - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
START_10Y = (pd.Timestamp(END) - timedelta(days=365 * 10)).strftime("%Y-%m-%d")
MIN_N = 3

EXPAND_TARGETS = [
    "ACC100_MULTI_V5",
    "ACC_WIDE_P92",
    "ACC_WIDE_P90",
    "ACC_WIDE_P85",
    "ACC_WIDE_P85B",
    "ACC_WIDE_P80",
    "ACC_WIDE_P75",
]

CAP2_TARGETS = [
    ("ACC100_MULTI_V5", 100.0),
    ("ACC_WIDE_P92", 99.24),
    ("ACC_WIDE_P90", 95.4),
    ("ACC_WIDE_P85", 89.69),
    ("ACC_WIDE_P85B", 88.4),
]


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 4)


def desk_ok(rows: List[dict], floor: float) -> bool:
    rs3 = _clip(rows, START_3Y, END)
    if floor >= 100.0:
        if not (rs3 and is_perfect(rs3)):
            return False
        soft = 100.0
    else:
        if len(rs3) >= MIN_N and hit_pct(rs3) + 1e-9 < floor:
            return False
        soft = max(floor - 2.0, 70.0)
    for start in (START_5Y, START_1Y):
        rs = _clip(rows, start, END)
        if len(rs) < MIN_N:
            continue
        if floor >= 100.0:
            if not is_perfect(rs):
                return False
        elif hit_pct(rs) + 1e-9 < soft:
            return False
    return True


def stream_ok(rows: List[dict], floor: float) -> bool:
    rs3 = _clip(rows, START_3Y, END)
    if len(rs3) < MIN_N:
        return False
    if floor >= 100.0:
        if not is_perfect(rs3):
            return False
        for start in (START_5Y, START_1Y):
            rs = _clip(rows, start, END)
            if len(rs) >= MIN_N and not is_perfect(rs):
                return False
        return True
    if hit_pct(rs3) + 1e-9 < floor:
        return False
    rs5 = _clip(rows, START_5Y, END)
    if len(rs5) >= MIN_N and hit_pct(rs5) + 1e-9 < max(floor - 2.0, 70.0):
        return False
    return True


# Denser than 2c: more bands, gaps, p-mins
BANDS = [
    ("first15", 9 * 60 + 15, 9 * 60 + 30),
    ("first20", 9 * 60 + 15, 9 * 60 + 35),
    ("first30", 9 * 60 + 15, 9 * 60 + 45),
    ("first45", 9 * 60 + 15, 10 * 60),
    ("open", 9 * 60 + 15, 10 * 60 + 30),
    ("am10", 9 * 60 + 15, 10 * 60 + 45),
    ("am1030", 9 * 60 + 15, 10 * 60 + 30),
    ("am11", 9 * 60 + 15, 11 * 60),
    ("am1115", 9 * 60 + 15, 11 * 60 + 15),
    ("am1130", 9 * 60 + 15, 11 * 60 + 30),
    ("am12", 9 * 60 + 15, 12 * 60),
    ("am1230", 9 * 60 + 15, 12 * 60 + 30),
    ("brunch", 10 * 60 + 15, 12 * 60),
    ("brunch2", 10 * 60, 12 * 60 + 30),
    ("lunch", 11 * 60 + 45, 13 * 60 + 15),
    ("mid", 10 * 60, 13 * 60),
    ("mid2", 10 * 60 + 15, 13 * 60 + 30),
    ("latemid", 10 * 60 + 30, 14 * 60),
    ("earlypm", 11 * 60 + 30, 14 * 60),
    ("pm", 12 * 60 + 30, 15 * 60 + 15),
    ("pm2", 12 * 60, 15 * 60),
    ("last150", 12 * 60 + 45, 15 * 60 + 15),
    ("last120", 13 * 60 + 15, 15 * 60 + 15),
    ("last90", 13 * 60 + 45, 15 * 60 + 15),
    ("last75", 14 * 60, 15 * 60 + 15),
    ("last60", 14 * 60 + 15, 15 * 60 + 15),
    ("last45", 14 * 60 + 30, 15 * 60 + 15),
    ("all", None, None),
]
GAPS = [
    ("nogap", None, False, False),
    ("g010", 0.10, False, False),
    ("g015", 0.15, False, False),
    ("g018", 0.18, False, False),
    ("g020", 0.20, False, False),
    ("g022", 0.22, False, False),
    ("g025", 0.25, False, False),
    ("g028", 0.28, False, False),
    ("g030", 0.30, False, False),
    ("g032", 0.32, False, False),
    ("g035", 0.35, False, False),
    ("g038", 0.38, False, False),
    ("g040", 0.40, False, False),
    ("g045", 0.45, False, False),
    ("g050", 0.50, False, False),
    ("g055", 0.55, False, False),
    ("g060", 0.60, False, False),
    ("g065", 0.65, False, False),
    ("g070", 0.70, False, False),
    ("g075", 0.75, False, False),
    ("g080", 0.80, False, False),
    ("g090", 0.90, False, False),
    ("gdn010", 0.10, True, False),
    ("gdn015", 0.15, True, False),
    ("gdn020", 0.20, True, False),
    ("gdn025", 0.25, True, False),
    ("gdn030", 0.30, True, False),
    ("gdn040", 0.40, True, False),
    ("gdn050", 0.50, True, False),
    ("gdn055", 0.55, True, False),
    ("gup010", 0.10, False, True),
    ("gup015", 0.15, False, True),
    ("gup020", 0.20, False, True),
    ("gup025", 0.25, False, True),
    ("gup030", 0.30, False, True),
    ("gup040", 0.40, False, True),
    ("gup050", 0.50, False, True),
    ("gup055", 0.55, False, True),
]
PMINS = (
    0.0, 0.40, 0.42, 0.45, 0.47, 0.48, 0.49, 0.50, 0.51, 0.52, 0.53, 0.54, 0.55,
    0.56, 0.57, 0.58, 0.59, 0.60, 0.61, 0.62, 0.63, 0.64, 0.65, 0.66, 0.68, 0.70,
    0.72, 0.74, 0.75, 0.76, 0.78, 0.80, 0.82, 0.84, 0.85, 0.86, 0.88, 0.90, 0.92, 0.94,
)


def mine(path_u, gaps, active, dual15, dual5, proven, champ, *, floor_min: float):
    streams: List[Tuple[str, List[dict]]] = []
    universes: Dict[str, List[dict]] = {}
    for rk, rows in (path_u.get("crown_by_risk") or {}).items():
        if str(rk).startswith("_"):
            continue
        universes[f"CR{str(rk).replace('.0', '')}"] = rows
    for rk, rows in (path_u.get("good_by_risk") or {}).items():
        if str(rk).startswith("_") or rk == "native":
            continue
        universes[f"GD{str(rk).replace('.0', '')}"] = rows
    universes["CH"] = path_u.get("champ_native") or champ
    universes["D5"] = dual5
    universes["PR"] = proven
    universes["D15"] = dual15

    n_eval = 0
    for uname, urows in universes.items():
        for side in (None, "BUY", "SELL"):
            for blab, lo, hi in BANDS:
                for glab, gabsm, gdn, gup in GAPS:
                    for use_htf in (False, True):
                        if use_htf and gabsm is not None and gabsm < 0.18 and not gdn and not gup:
                            continue
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
                            ):
                                n_eval += 1
                                rs3 = _clip(vrows, START_3Y, END)
                                if len(rs3) < MIN_N or hit_pct(rs3) + 1e-9 < floor_min:
                                    continue
                                tag = (
                                    f"{uname}_{side or 'BOTH'}_p{int(round(pmin * 100))}_{blab}_"
                                    f"{'htf' if use_htf else 'any'}_{glab}_{vlab}"
                                )
                                streams.append((tag, vrows))

    ix15, ix15p, ix5 = _ix(dual15), _ix(proven), _ix(dual5)
    ix_ch = _ix(path_u.get("champ_native") or champ)
    for tol in (
        2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 20, 22, 25, 28, 30, 35, 40, 45, 50, 55, 60, 75, 90, 105, 120
    ):
        cands = [
            (f"CF_T{tol}_any15_d5", time_agree(ix15, ix5, tol=tol, tag="cf")),
            (f"CF_T{tol}_p15_d5", time_agree(ix15p, ix5, tol=tol, tag="cf")),
            (f"CF_T{tol}_any15_ch", time_agree(ix15, ix_ch, tol=tol, tag="cf")),
            (f"CF_T{tol}_ch_d5", time_agree(ix_ch, ix5, tol=tol, tag="cf")),
            (f"CF_T{tol}_p15_ch", time_agree(ix15p, ix_ch, tol=tol, tag="cf")),
            (f"CF_T{tol}_d5_p15", time_agree(ix5, ix15p, tol=tol, tag="cf")),
            (f"CF_T{tol}_d5_any15", time_agree(ix5, ix15, tol=tol, tag="cf")),
        ]
        for rk, crow in (path_u.get("crown_by_risk") or {}).items():
            if str(rk).startswith("_"):
                continue
            lab = str(rk).replace(".0", "")
            ixcr = _ix(crow)
            cands += [
                (f"CF_T{tol}_any15_cr{lab}", time_agree(ix15, ixcr, tol=tol, tag="cf")),
                (f"CF_T{tol}_d5_cr{lab}", time_agree(ix5, ixcr, tol=tol, tag="cf")),
                (f"CF_T{tol}_ch_cr{lab}", time_agree(ix_ch, ixcr, tol=tol, tag="cf")),
                (f"CF_T{tol}_p15_cr{lab}", time_agree(ix15p, ixcr, tol=tol, tag="cf")),
            ]
        for tag, rows in cands:
            rs3 = _clip(rows, START_3Y, END)
            if len(rs3) >= MIN_N and hit_pct(rs3) + 1e-9 >= floor_min:
                streams.append((tag, rows))

    by_sig: Dict[tuple, Tuple[str, List[dict], Dict[str, Any]]] = {}
    for tag, rows in streams:
        sig = tuple(
            sorted((str(r["day"]), _side(r), str(r.get("hm") or "")) for r in rows)
        )
        rs3 = _clip(rows, START_3Y, END)
        st = {
            "n_3y": len(rs3),
            "hit_3y": hit_pct(rs3),
            "perfect_3y": is_perfect(rs3) if rs3 else False,
        }
        prev = by_sig.get(sig)
        if prev is None or st["n_3y"] > prev[2]["n_3y"] or (
            st["n_3y"] == prev[2]["n_3y"] and st["hit_3y"] > prev[2]["hit_3y"]
        ):
            by_sig[sig] = (tag, rows, st)
    out = list(by_sig.values())
    out.sort(key=lambda x: (x[2]["hit_3y"], x[2]["n_3y"]), reverse=True)
    print(f"  mined eval≈{n_eval} → unique={len(out)} (≥{floor_min:g}% 3y)", flush=True)
    return out


def greedy(
    base: List[dict],
    streams: List[Tuple[str, List[dict], Dict[str, Any]]],
    floor: float,
    *,
    mode: str = "day",
    max_rounds: int = 200,
    used_tags: Optional[Set[str]] = None,
) -> Tuple[List[dict], List[dict]]:
    cur = list(base)
    added: List[dict] = []
    used = set(used_tags or [])
    improved = True
    rounds = 0

    def merge(a, b):
        if mode == "cap2":
            return union_day_cap2(a, b, cap=2)
        return union_unique_days(a, b)

    while improved and rounds < max_rounds:
        improved = False
        rounds += 1
        if mode == "cap2":
            pass
        else:
            days = {str(r.get("day") or "") for r in cur}

        ranked = []
        for tag, rows, st in streams:
            if tag in used:
                continue
            if not stream_ok(rows, floor):
                continue
            if mode == "cap2":
                trial = merge(cur, rows)
                new_n = len(trial) - len(cur)
            else:
                new_n = sum(1 for r in rows if str(r["day"]) not in days)
            if new_n:
                ranked.append((new_n, st.get("hit_3y") or 0, tag, rows))
        ranked.sort(reverse=True)
        for new_n, _h, tag, rows in ranked:
            merged = merge(cur, rows)
            if len(merged) <= len(cur):
                continue
            if not desk_ok(merged, floor):
                continue
            delta = len(merged) - len(cur)
            cur = merged
            used.add(tag)
            d3 = _clip(cur, START_3Y, END)
            added.append(
                {
                    "tag": tag,
                    "new_n": delta,
                    "desk_n_3y": len(d3),
                    "desk_hit_3y": hit_pct(d3),
                }
            )
            print(
                f"    [{mode}] +{delta} {tag} → 3y={len(d3)}@{hit_pct(d3):.2f}%",
                flush=True,
            )
            improved = True
            break
    return cur, added


def summarize(desk: List[dict]) -> Dict[str, Any]:
    out = {}
    for lab, start in (("1y", START_1Y), ("3y", START_3Y), ("5y", START_5Y)):
        rs = _clip(desk, start, END)
        out[lab] = {
            "n": len(rs),
            "hit_pct": hit_pct(rs),
            "perfect": bool(rs) and is_perfect(rs),
            "points": (_agg(rs) or {}).get("points"),
        }
    return out


def replay_tags(
    base: List[dict],
    tags: List[str],
    by_tag: Dict[str, List[dict]],
    floor: float,
    *,
    mode: str = "day",
) -> Tuple[List[dict], Set[str]]:
    cur = list(base)
    used: Set[str] = set()
    merge = (lambda a, b: union_day_cap2(a, b, cap=2)) if mode == "cap2" else union_unique_days
    for tag in tags:
        rows = by_tag.get(tag)
        if not rows:
            continue
        if not stream_ok(rows, floor):
            continue
        merged = merge(cur, rows)
        if len(merged) <= len(cur):
            used.add(tag)
            continue
        if desk_ok(merged, floor):
            cur = merged
            used.add(tag)
    return cur, used


def cand_name(desk_tag: str, n: int, p2c_n: Optional[int], *, mode: str) -> str:
    if mode == "cap2":
        return f"{desk_tag}_CAP2_P2D"
    if desk_tag == "ACC100_MULTI_V5":
        if n > (p2c_n or 199):
            return "ACC100_MULTI_V9"
        if n > 163:
            return "ACC100_MULTI_V8"
        if n > 146:
            return "ACC100_MULTI_V7"
        return "ACC100_MULTI_V6"
    return f"{desk_tag}_P2D"


def main() -> None:
    t0 = time.time()
    print("PHASE-2d KEEP GOING @ same accuracy (P1 locked, P2c held)", flush=True)

    held = load_held_recipes()
    held_cands = held.get("candidates") or {}

    dual = json.loads(CACHE_DUAL_10Y.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH_10Y.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_10Y < d <= END]
    active = fs._active_days(sess, fs._load_daily()) if sess else set()

    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ = _champ_floor([dict(r, track="champion") for r in dual["dual15"]["champion"]])
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]
    champ_native = path_u.get("champ_native") or champ

    print("  rebuild Phase-1…", flush=True)
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

    print("  denser mine (≥75% 3y)…", flush=True)
    all_streams = mine(
        {
            "crown_by_risk": path_u.get("crown_by_risk") or {},
            "good_by_risk": path_u.get("good_by_risk") or {},
            "champ_native": champ_native,
        },
        gaps,
        active,
        dual15,
        dual5,
        proven,
        champ,
        floor_min=75.0,
    )
    by_tag = {t: rows for t, rows, _ in all_streams}
    perfect = [s for s in all_streams if s[2].get("perfect_3y")]

    results: Dict[str, Any] = {}
    for desk_tag in EXPAND_TARGETS:
        meta = DESK_REGISTRY[desk_tag]
        floor = float(meta["research_3y"]["hit_pct"])
        if floor >= 99.999:
            floor = 100.0
            pool = perfect
        else:
            pool = [s for s in all_streams if stream_ok(s[1], floor)]

        base = list(phase1[desk_tag])
        base_sum = summarize(base)
        held_meta = held_cands.get(desk_tag) or {}
        seed_tags = list(held_meta.get("stream_tags_held") or [])
        p2c_n = (held_meta.get("held_3y") or {}).get("n")

        seeded, used = replay_tags(base, seed_tags, by_tag, floor, mode="day")
        seed_sum = summarize(seeded)
        print(
            f"  {desk_tag} floor={floor:g}% P1={base_sum['3y']['n']} "
            f"seedP2c={seed_sum['3y']['n']} (held={p2c_n}) pool={len(pool)}…",
            flush=True,
        )
        desk, added = greedy(
            seeded, pool, floor, mode="day", max_rounds=200, used_tags=used
        )
        got = summarize(desk)
        cand = None
        if got["3y"]["n"] > base_sum["3y"]["n"]:
            cand = cand_name(desk_tag, got["3y"]["n"], p2c_n, mode="day")
        results[desk_tag] = {
            "mode": "day",
            "floor": floor,
            "accuracy_range": meta["accuracy_range"],
            "phase1_3y": meta["research_3y"],
            "phase2c_3y_n": p2c_n,
            "baseline": base_sum,
            "seeded": seed_sum,
            "result": got,
            "delta_vs_phase1_3y": got["3y"]["n"] - base_sum["3y"]["n"],
            "delta_vs_phase2c_3y": (got["3y"]["n"] - p2c_n) if p2c_n is not None else None,
            "seed_tags_applied": len(used),
            "added_streams_new": added,
            "candidate_tag": cand,
        }
        print(
            f"    → 3y {got['3y']['n']}@{got['3y']['hit_pct']}% "
            f"ΔP1={results[desk_tag]['delta_vs_phase1_3y']:+d} "
            f"ΔP2c={results[desk_tag]['delta_vs_phase2c_3y']} cand={cand}",
            flush=True,
        )

    for desk_tag, floor in CAP2_TARGETS:
        meta = DESK_REGISTRY[desk_tag]
        pool = perfect if floor >= 100.0 else [s for s in all_streams if stream_ok(s[1], floor)]
        base = list(phase1[desk_tag])
        held_key = f"{desk_tag}_CAP2"
        held_meta = held_cands.get(held_key) or {}
        seed_tags = list(held_meta.get("stream_tags_held") or [])
        p2c_n = (held_meta.get("held_3y") or {}).get("n")
        seeded, used = replay_tags(base, seed_tags, by_tag, floor, mode="cap2")
        seed_sum = summarize(seeded)
        print(
            f"  {desk_tag} CAP2 floor={floor:g}% seed={seed_sum['3y']['n']} (held={p2c_n})…",
            flush=True,
        )
        desk, added = greedy(
            seeded, pool, floor, mode="cap2", max_rounds=160, used_tags=used
        )
        got = summarize(desk)
        key = f"{desk_tag}_CAP2"
        results[key] = {
            "mode": "cap2",
            "floor": floor,
            "phase2c_3y_n": p2c_n,
            "baseline": summarize(base),
            "seeded": seed_sum,
            "result": got,
            "delta_vs_phase1_3y": got["3y"]["n"] - summarize(base)["3y"]["n"],
            "delta_vs_phase2c_3y": (got["3y"]["n"] - p2c_n) if p2c_n is not None else None,
            "added_streams_new": added,
            "candidate_tag": cand_name(desk_tag, got["3y"]["n"], p2c_n, mode="cap2"),
        }
        print(
            f"    → 3y {got['3y']['n']}@{got['3y']['hit_pct']}% "
            f"ΔP1={results[key]['delta_vs_phase1_3y']:+d} "
            f"ΔP2c={results[key]['delta_vs_phase2c_3y']}",
            flush=True,
        )

    payload = {
        "phase": "2d",
        "phase1_held": True,
        "phase2c_held": True,
        "holding_folder": "prod_live/holding_accurate/",
        "phase1_logic": "logic/accurate_desks.py",
        "phase2c_recipes": "holding_accurate/recipes.json",
        "note": "Keep going — P1 locked, P2c held; denser mine from P2c seeds",
        "window_end": END,
        "streams_mined": len(all_streams),
        "perfect_streams": len(perfect),
        "results": results,
        "elapsed_s": round(time.time() - t0, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ACC_PHASE2D_KEEP_GOING.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (LEDGER / "ACC_PHASE2D_KEEP_GOING.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (HOLD / "reports").mkdir(parents=True, exist_ok=True)
    (HOLD / "reports" / "ACC_PHASE2D_KEEP_GOING.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Phase-2d — keep going @ same accuracy",
        "",
        "**Phase-1 LOCKED.** **Phase-2c HELD** in `holding_accurate/`.",
        "Seeds from held P2c recipes + denser mine + more cap2 desks.",
        "",
        f"Mined ≥75%: {len(all_streams)} · perfect-3y: {len(perfect)} · "
        f"elapsed {payload['elapsed_s']}s",
        "",
        "## Day-dedupe",
        "",
        "| Desk | Floor | P1 | P2c | **P2d** | ΔP1 | ΔP2c | Hit | Candidate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for desk_tag in EXPAND_TARGETS:
        r = results[desk_tag]
        b, g = r["baseline"]["3y"], r["result"]["3y"]
        p2cn = r.get("phase2c_3y_n")
        d2c = r.get("delta_vs_phase2c_3y")
        lines.append(
            f"| `{desk_tag}` | {r['floor']:g} | {b['n']} | {p2cn if p2cn is not None else '—'} | "
            f"**{g['n']}** | {r['delta_vs_phase1_3y']:+d} | "
            f"{('+' + str(d2c)) if isinstance(d2c, int) and d2c >= 0 else (str(d2c) if d2c is not None else '—')} | "
            f"{g['hit_pct']} | `{r['candidate_tag'] or '—'}` |"
        )

    lines += ["", "## Cap2 @ same accuracy", ""]
    lines += [
        "| Desk | Floor | P1 | P2c | Cap2 P2d | ΔP1 | ΔP2c | Hit | Candidate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for key in (k for k in results if k.endswith("_CAP2")):
        r = results[key]
        b, g = r["baseline"]["3y"], r["result"]["3y"]
        p2cn = r.get("phase2c_3y_n")
        d2c = r.get("delta_vs_phase2c_3y")
        lines.append(
            f"| `{key}` | {r['floor']:g} | {b['n']} | {p2cn if p2cn is not None else '—'} | "
            f"**{g['n']}** | {r['delta_vs_phase1_3y']:+d} | "
            f"{('+' + str(d2c)) if isinstance(d2c, int) and d2c >= 0 else (str(d2c) if d2c is not None else '—')} | "
            f"{g['hit_pct']} | `{r['candidate_tag']}` |"
        )

    lines += ["", "## New streams beyond P2c seed (day)", ""]
    for desk_tag in EXPAND_TARGETS:
        r = results[desk_tag]
        lines.append(f"### `{desk_tag}`")
        lines.append("")
        if not r["added_streams_new"]:
            lines.append("_No new streams beyond P2c seed (or seed already maxed)._")
        else:
            lines += ["| # | Tag | + | Desk3y | Hit |", "|---:|---|---:|---:|---:|"]
            for i, a in enumerate(r["added_streams_new"][:40], 1):
                lines.append(
                    f"| {i} | `{a['tag']}` | +{a['new_n']} | {a['desk_n_3y']} | {a['desk_hit_3y']} |"
                )
        lines.append("")

    lines += [
        "## Hold",
        "",
        "Phase-1 locked · Phase-2c held in `holding_accurate/` · P2d = new candidates.",
        "",
        "JSON: `ACC_PHASE2D_KEEP_GOING.json`",
        "",
    ]
    md = OUT / "ACC_PHASE2D_KEEP_GOING.md"
    text = "\n".join(lines)
    md.write_text(text, encoding="utf-8")
    (LEDGER / "ACC_PHASE2D_KEEP_GOING.md").write_text(text, encoding="utf-8")
    (HOLD / "reports" / "ACC_PHASE2D_KEEP_GOING.md").write_text(text, encoding="utf-8")
    print("Wrote", md, flush=True)


if __name__ == "__main__":
    main()
