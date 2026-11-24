"""Phase-2b: DEEPER hunt — more calls @ same accuracy (Phase-1 locked).

Starts from Phase-1 desks; denser mine than Phase-2; expands more desks +
optional day_side mode. Does not mutate Phase-1 logic.

  python -u prod_live/tests/builders/research_acc_phase2b_deeper_more.py
"""
from __future__ import annotations

import json
import sys
import time
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

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL_10Y = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH_10Y = LEDGER / "_cache_path_trusted_10y.json"
P2_JSON = OUT / "ACC_PHASE2_SAME_ACC_MORE.json"

END = RESEARCH_END
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_5Y = (pd.Timestamp(END) - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
START_10Y = (pd.Timestamp(END) - timedelta(days=365 * 10)).strftime("%Y-%m-%d")
MIN_N = 4

EXPAND_TARGETS = [
    "ACC100_MULTI_V5",
    "ACC_WIDE_P92",
    "ACC_WIDE_P90",
    "ACC_WIDE_P85",
    "ACC_WIDE_P85B",
    "ACC_WIDE_P80",
    "ACC_WIDE_P75",
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


def union_day_side(base: List[dict], extra: List[dict]) -> List[dict]:
    keys = {(str(r.get("day") or ""), _side(r)) for r in base}
    out = list(base)
    for r in extra:
        k = (str(r.get("day") or ""), _side(r))
        if k in keys:
            continue
        out.append(dict(r))
        keys.add(k)
    return out


BANDS = [
    ("first30", 9 * 60 + 15, 9 * 60 + 45),
    ("first45", 9 * 60 + 15, 10 * 60),
    ("open", 9 * 60 + 15, 10 * 60 + 30),
    ("am11", 9 * 60 + 15, 11 * 60),
    ("am1130", 9 * 60 + 15, 11 * 60 + 30),
    ("am1230", 9 * 60 + 15, 12 * 60 + 30),
    ("lunch", 11 * 60 + 45, 13 * 60 + 15),
    ("mid", 10 * 60, 13 * 60),
    ("latemid", 10 * 60 + 30, 14 * 60),
    ("earlypm", 11 * 60 + 30, 14 * 60),
    ("pm", 12 * 60 + 30, 15 * 60 + 15),
    ("last90", 13 * 60 + 45, 15 * 60 + 15),
    ("last60", 14 * 60 + 15, 15 * 60 + 15),
    ("all", None, None),
]
GAPS = [
    ("nogap", None, False, False),
    ("g020", 0.20, False, False),
    ("g025", 0.25, False, False),
    ("g030", 0.30, False, False),
    ("g035", 0.35, False, False),
    ("g040", 0.40, False, False),
    ("g045", 0.45, False, False),
    ("g050", 0.50, False, False),
    ("g055", 0.55, False, False),
    ("g060", 0.60, False, False),
    ("g065", 0.65, False, False),
    ("g070", 0.70, False, False),
    ("gdn020", 0.20, True, False),
    ("gdn025", 0.25, True, False),
    ("gdn030", 0.30, True, False),
    ("gdn040", 0.40, True, False),
    ("gdn055", 0.55, True, False),
    ("gup020", 0.20, False, True),
    ("gup025", 0.25, False, True),
    ("gup030", 0.30, False, True),
    ("gup040", 0.40, False, True),
    ("gup055", 0.55, False, True),
]
PMINS = (
    0.0, 0.48, 0.50, 0.52, 0.54, 0.55, 0.56, 0.57, 0.58, 0.60, 0.62, 0.64, 0.65,
    0.68, 0.70, 0.72, 0.75, 0.78, 0.80, 0.82, 0.85, 0.88, 0.90,
)


def mine(
    path_u, gaps, active, dual15, dual5, proven, champ, *, floor_min: float
) -> List[Tuple[str, List[dict], Dict[str, Any]]]:
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
    for tol in (5, 8, 10, 12, 15, 20, 25, 30, 35, 40, 45, 60, 75, 90):
        cands = [
            (f"CF_T{tol}_any15_d5", time_agree(ix15, ix5, tol=tol, tag="cf")),
            (f"CF_T{tol}_p15_d5", time_agree(ix15p, ix5, tol=tol, tag="cf")),
            (f"CF_T{tol}_any15_ch", time_agree(ix15, ix_ch, tol=tol, tag="cf")),
            (f"CF_T{tol}_ch_d5", time_agree(ix_ch, ix5, tol=tol, tag="cf")),
            (f"CF_T{tol}_p15_ch", time_agree(ix15p, ix_ch, tol=tol, tag="cf")),
        ]
        for rk, crow in (path_u.get("crown_by_risk") or {}).items():
            if str(rk).startswith("_"):
                continue
            lab = str(rk).replace(".0", "")
            cands.append(
                (f"CF_T{tol}_any15_cr{lab}", time_agree(ix15, _ix(crow), tol=tol, tag="cf"))
            )
            cands.append(
                (f"CF_T{tol}_d5_cr{lab}", time_agree(ix5, _ix(crow), tol=tol, tag="cf"))
            )
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
    max_rounds: int = 100,
) -> Tuple[List[dict], List[dict]]:
    cur = list(base)
    added: List[dict] = []
    improved = True
    rounds = 0

    def merge(a, b):
        return union_day_side(a, b) if mode == "day_side" else union_unique_days(a, b)

    def occ(rows):
        if mode == "day_side":
            return {(str(r.get("day") or ""), _side(r)) for r in rows}
        return {str(r.get("day") or "") for r in rows}

    while improved and rounds < max_rounds:
        improved = False
        rounds += 1
        seen = occ(cur)
        ranked = []
        for tag, rows, st in streams:
            if not stream_ok(rows, floor):
                continue
            if mode == "day_side":
                new_n = sum(
                    1 for r in rows if (str(r.get("day") or ""), _side(r)) not in seen
                )
            else:
                new_n = sum(1 for r in rows if str(r["day"]) not in seen)
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


def main() -> None:
    t0 = time.time()
    print("PHASE-2b DEEPER: more calls @ same accuracy (Phase-1 locked)", flush=True)

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

    print("  rebuild Phase-1…", flush=True)
    phase1 = build_all_accurate_desks(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=path_u.get("crown_by_risk") or {},
        good_by_risk=path_u.get("good_by_risk") or {},
        champ_rows=path_u.get("champ_native") or champ,
        gap_pct_by_day=gaps,
        htf_days=active,
    )

    p2_ref = {}
    if P2_JSON.exists():
        p2 = json.loads(P2_JSON.read_text(encoding="utf-8"))
        for k, v in (p2.get("results") or {}).items():
            p2_ref[k] = (v.get("result") or {}).get("3y") or {}

    print("  denser mine (≥80% 3y)…", flush=True)
    all_streams = mine(
        {
            "crown_by_risk": path_u.get("crown_by_risk") or {},
            "good_by_risk": path_u.get("good_by_risk") or {},
            "champ_native": path_u.get("champ_native") or champ,
        },
        gaps,
        active,
        dual15,
        dual5,
        proven,
        champ,
        floor_min=80.0,
    )
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
        print(
            f"  expand {desk_tag} floor={floor:g}% base={base_sum['3y']['n']} "
            f"pool={len(pool)}…",
            flush=True,
        )
        desk, added = greedy(base, pool, floor, mode="day", max_rounds=120)
        got = summarize(desk)
        p2n = (p2_ref.get(desk_tag) or {}).get("n")
        results[desk_tag] = {
            "mode": "day",
            "accuracy_range": meta["accuracy_range"],
            "floor": floor,
            "phase1_3y": meta["research_3y"],
            "phase2_3y_n": p2n,
            "baseline": base_sum,
            "result": got,
            "delta_vs_phase1_3y": got["3y"]["n"] - base_sum["3y"]["n"],
            "delta_vs_phase2_3y": (got["3y"]["n"] - p2n) if p2n is not None else None,
            "added_streams": added,
            "candidate_tag": f"{desk_tag}_P2B" if got["3y"]["n"] > base_sum["3y"]["n"] else None,
        }
        if desk_tag == "ACC100_MULTI_V5" and got["3y"]["n"] > base_sum["3y"]["n"]:
            results[desk_tag]["candidate_tag"] = (
                "ACC100_MULTI_V6" if got["3y"]["n"] <= 146 else "ACC100_MULTI_V7"
            )
            # V6 was ~146 in P2; beyond that → V7
            if got["3y"]["n"] > 146:
                results[desk_tag]["candidate_tag"] = "ACC100_MULTI_V7"
            elif got["3y"]["n"] > base_sum["3y"]["n"]:
                results[desk_tag]["candidate_tag"] = "ACC100_MULTI_V6"
        print(
            f"    → 3y {got['3y']['n']}@{got['3y']['hit_pct']}% "
            f"ΔP1={results[desk_tag]['delta_vs_phase1_3y']:+d} "
            f"ΔP2={results[desk_tag]['delta_vs_phase2_3y']} "
            f"cand={results[desk_tag]['candidate_tag']}",
            flush=True,
        )

    # day_side at 100% / P92 floors for extra volume without dropping hit
    for desk_tag, floor in (("ACC100_MULTI_V5", 100.0), ("ACC_WIDE_P92", 99.24)):
        meta = DESK_REGISTRY[desk_tag]
        pool = perfect if floor >= 100.0 else [s for s in all_streams if stream_ok(s[1], floor)]
        base = list(phase1[desk_tag])
        print(f"  expand {desk_tag} day_side floor={floor:g}%…", flush=True)
        desk, added = greedy(base, pool, floor, mode="day_side", max_rounds=80)
        got = summarize(desk)
        key = f"{desk_tag}_SIDES"
        results[key] = {
            "mode": "day_side",
            "accuracy_range": meta["accuracy_range"],
            "floor": floor,
            "phase1_3y": meta["research_3y"],
            "baseline": summarize(base),
            "result": got,
            "delta_vs_phase1_3y": got["3y"]["n"] - summarize(base)["3y"]["n"],
            "added_streams": added,
            "candidate_tag": f"{desk_tag}_SIDES_P2B",
        }
        print(
            f"    → 3y {got['3y']['n']}@{got['3y']['hit_pct']}% "
            f"Δ={results[key]['delta_vs_phase1_3y']:+d}",
            flush=True,
        )

    payload = {
        "phase": "2b",
        "phase1_held": True,
        "phase1_logic": "logic/accurate_desks.py",
        "note": "Deeper candidates — Phase-1 unchanged",
        "window_end": END,
        "streams_mined": len(all_streams),
        "perfect_streams": len(perfect),
        "results": results,
        "elapsed_s": round(time.time() - t0, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ACC_PHASE2B_DEEPER_MORE.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (LEDGER / "ACC_PHASE2B_DEEPER_MORE.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Phase-2b — deeper more calls @ same accuracy",
        "",
        "**Phase-1 HELD.** Denser mine than Phase-2; more desks + day_side.",
        "",
        f"Mined ≥80%: {len(all_streams)} · perfect-3y: {len(perfect)} · "
        f"elapsed {payload['elapsed_s']}s",
        "",
        "## Day-dedupe expands",
        "",
        "| Desk | Floor | P1 3y | P2 3y | P2b 3y | Δ vs P1 | Δ vs P2 | Hit | Candidate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for desk_tag in EXPAND_TARGETS:
        r = results[desk_tag]
        b, g = r["baseline"]["3y"], r["result"]["3y"]
        p2n = r.get("phase2_3y_n")
        lines.append(
            f"| `{desk_tag}` | {r['floor']:g} | {b['n']} | {p2n if p2n is not None else '—'} | "
            f"**{g['n']}** | {r['delta_vs_phase1_3y']:+d} | "
            f"{('+' + str(r['delta_vs_phase2_3y'])) if r['delta_vs_phase2_3y'] is not None else '—'} | "
            f"{g['hit_pct']} | `{r['candidate_tag'] or '—'}` |"
        )

    lines += ["", "## Day-side expands", ""]
    lines += [
        "| Desk | Floor | P1 3y | P2b sides 3y | Δ | Hit | Candidate |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for key in (k for k in results if k.endswith("_SIDES")):
        r = results[key]
        b, g = r["baseline"]["3y"], r["result"]["3y"]
        lines.append(
            f"| `{key}` | {r['floor']:g} | {b['n']} | **{g['n']}** | "
            f"{r['delta_vs_phase1_3y']:+d} | {g['hit_pct']} | `{r['candidate_tag']}` |"
        )

    lines += ["", "## Added streams (day mode)", ""]
    for desk_tag in EXPAND_TARGETS:
        r = results[desk_tag]
        lines.append(f"### `{desk_tag}`")
        lines.append("")
        if not r["added_streams"]:
            lines.append("_No growth._")
        else:
            lines += ["| # | Tag | + | Desk3y | Hit |", "|---:|---|---:|---:|---:|"]
            for i, a in enumerate(r["added_streams"][:25], 1):
                lines.append(
                    f"| {i} | `{a['tag']}` | +{a['new_n']} | {a['desk_n_3y']} | {a['desk_hit_3y']} |"
                )
            if len(r["added_streams"]) > 25:
                lines.append(f"| … | _{len(r['added_streams']) - 25} more_ | | | |")
        lines.append("")

    lines += [
        "## Hold",
        "",
        "- Phase-1 locked.",
        "- Phase-2 / 2b are candidates only until promote.",
        "",
        "JSON: `ACC_PHASE2B_DEEPER_MORE.json`",
        "",
    ]
    md = OUT / "ACC_PHASE2B_DEEPER_MORE.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (LEDGER / "ACC_PHASE2B_DEEPER_MORE.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", md, flush=True)


if __name__ == "__main__":
    main()
