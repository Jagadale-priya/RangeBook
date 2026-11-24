"""Phase-2 research: MORE calls at SAME accuracy as Phase-1 held desks.

Phase-1 locked in logic/accurate_desks.py + ACC_ACCURATE_3Y_MATCH PASS.
This hunt does NOT modify Phase-1. Candidates only.

Targets (day-dedupe greedy):
  - 100% onto V5          → maybe ACC100_MULTI_V6
  - same hit onto P92/P90/P85/P85B/P80/P75 (floor = that desk's locked 3y hit)

  python -u prod_live/tests/builders/research_acc_phase2_same_acc_more.py
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

END = RESEARCH_END
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_5Y = (pd.Timestamp(END) - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
START_10Y = (pd.Timestamp(END) - timedelta(days=365 * 10)).strftime("%Y-%m-%d")
MIN_N = 4

# Expand these Phase-1 desks (same accuracy = keep ≥ locked 3y hit; 100% stays perfect)
EXPAND_TARGETS = [
    "ACC100_MULTI_V5",
    "ACC_WIDE_P92",
    "ACC_WIDE_P90",
    "ACC_WIDE_P85",
    "ACC_WIDE_P85B",
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


BANDS = [
    ("first45", 9 * 60 + 15, 10 * 60),
    ("open", 9 * 60 + 15, 10 * 60 + 30),
    ("am11", 9 * 60 + 15, 11 * 60),
    ("am1130", 9 * 60 + 15, 11 * 60 + 30),
    ("am1230", 9 * 60 + 15, 12 * 60 + 30),
    ("mid", 10 * 60, 13 * 60),
    ("latemid", 10 * 60 + 30, 14 * 60),
    ("earlypm", 11 * 60 + 30, 14 * 60),
    ("pm", 12 * 60 + 30, 15 * 60 + 15),
    ("last90", 13 * 60 + 45, 15 * 60 + 15),
    ("all", None, None),
]
GAPS = [
    ("nogap", None, False, False),
    ("g025", 0.25, False, False),
    ("g030", 0.30, False, False),
    ("g035", 0.35, False, False),
    ("g040", 0.40, False, False),
    ("g045", 0.45, False, False),
    ("g050", 0.50, False, False),
    ("g055", 0.55, False, False),
    ("g065", 0.65, False, False),
    ("gdn025", 0.25, True, False),
    ("gdn030", 0.30, True, False),
    ("gdn040", 0.40, True, False),
    ("gdn055", 0.55, True, False),
    ("gup025", 0.25, False, True),
    ("gup030", 0.30, False, True),
    ("gup040", 0.40, False, True),
    ("gup055", 0.55, False, True),
]
PMINS = (
    0.0, 0.50, 0.52, 0.55, 0.57, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70, 0.72, 0.75, 0.78, 0.80, 0.85, 0.90,
)


def mine(
    path_u: dict,
    gaps: dict,
    active: set,
    dual15,
    dual5,
    proven,
    champ,
    *,
    floor_min: float,
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
                                if len(rs3) < MIN_N:
                                    continue
                                if hit_pct(rs3) + 1e-9 < floor_min:
                                    continue
                                tag = (
                                    f"{uname}_{side or 'BOTH'}_p{int(round(pmin * 100))}_{blab}_"
                                    f"{'htf' if use_htf else 'any'}_{glab}_{vlab}"
                                )
                                streams.append((tag, vrows))

    ix15, ix15p, ix5 = _ix(dual15), _ix(proven), _ix(dual5)
    ix_ch = _ix(path_u.get("champ_native") or champ)
    for tol in (5, 10, 15, 20, 25, 30, 40, 45, 60, 90):
        for tag, rows in (
            (f"CF_T{tol}_any15_d5", time_agree(ix15, ix5, tol=tol, tag="cf")),
            (f"CF_T{tol}_p15_d5", time_agree(ix15p, ix5, tol=tol, tag="cf")),
            (f"CF_T{tol}_any15_ch", time_agree(ix15, ix_ch, tol=tol, tag="cf")),
            (f"CF_T{tol}_ch_d5", time_agree(ix_ch, ix5, tol=tol, tag="cf")),
        ):
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
    max_rounds: int = 80,
) -> Tuple[List[dict], List[dict]]:
    cur = list(base)
    added: List[dict] = []
    improved = True
    rounds = 0
    while improved and rounds < max_rounds:
        improved = False
        rounds += 1
        cur_days = {str(r.get("day") or "") for r in cur}
        ranked = []
        for tag, rows, st in streams:
            if not stream_ok(rows, floor):
                continue
            new_n = sum(1 for r in rows if str(r["day"]) not in cur_days)
            if new_n:
                ranked.append((new_n, st.get("hit_3y") or 0, tag, rows))
        ranked.sort(reverse=True)
        for new_n, _h, tag, rows in ranked:
            merged = union_unique_days(cur, rows)
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
                f"    +{delta} {tag} → 3y={len(d3)}@{hit_pct(d3):.2f}%",
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
    print("PHASE-2: more calls @ same accuracy (Phase-1 held)", flush=True)

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
    crown_by_risk = path_u.get("crown_by_risk") or {}
    good_by_risk = path_u.get("good_by_risk") or {}
    champ_native = path_u.get("champ_native") or champ

    print("  rebuild Phase-1 desks…", flush=True)
    phase1 = build_all_accurate_desks(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active,
    )

    print("  mine streams (≥85% then filter per target)…", flush=True)
    path_bundle = {
        "crown_by_risk": crown_by_risk,
        "good_by_risk": good_by_risk,
        "champ_native": champ_native,
    }
    all_streams = mine(
        path_bundle, gaps, active, dual15, dual5, proven, champ, floor_min=85.0
    )
    perfect = [s for s in all_streams if s[2].get("perfect_3y")]

    results: Dict[str, Any] = {}
    for desk_tag in EXPAND_TARGETS:
        meta = DESK_REGISTRY[desk_tag]
        lock = meta["research_3y"]
        floor = float(lock["hit_pct"])
        # same accuracy: for 100% desks keep perfect; else keep ≥ locked 3y hit
        if floor >= 99.999:
            floor = 100.0
            pool = perfect
        else:
            pool = [s for s in all_streams if stream_ok(s[1], floor)]
        base = list(phase1[desk_tag])
        base_sum = summarize(base)
        print(
            f"  expand {desk_tag} floor={floor:g}%  "
            f"base3y={base_sum['3y']['n']}@{base_sum['3y']['hit_pct']}%  "
            f"pool={len(pool)}…",
            flush=True,
        )
        desk, added = greedy(base, pool, floor, max_rounds=60)
        got = summarize(desk)
        results[desk_tag] = {
            "accuracy_range": meta["accuracy_range"],
            "band": meta["band"],
            "floor": floor,
            "phase1_3y": lock,
            "baseline": base_sum,
            "result": got,
            "delta_3y_n": got["3y"]["n"] - base_sum["3y"]["n"],
            "added_streams": added,
            "candidate_tag": (
                "ACC100_MULTI_V6"
                if desk_tag == "ACC100_MULTI_V5" and got["3y"]["n"] > base_sum["3y"]["n"]
                else f"{desk_tag}_P2"
                if got["3y"]["n"] > base_sum["3y"]["n"]
                else None
            ),
        }
        print(
            f"    → 3y {got['3y']['n']}@{got['3y']['hit_pct']}% "
            f"(Δ{results[desk_tag]['delta_3y_n']:+d}) "
            f"cand={results[desk_tag]['candidate_tag']}",
            flush=True,
        )

    payload = {
        "phase": 2,
        "phase1_held": True,
        "phase1_logic": "logic/accurate_desks.py",
        "note": "Candidates only — Phase-1 unchanged until promote",
        "window_end": END,
        "results": results,
        "streams_mined": len(all_streams),
        "perfect_streams": len(perfect),
        "elapsed_s": round(time.time() - t0, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ACC_PHASE2_SAME_ACC_MORE.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (LEDGER / "ACC_PHASE2_SAME_ACC_MORE.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Phase-2 — more calls @ same accuracy",
        "",
        "**Phase-1 HELD** (`accurate_desks.py` + 3y PASS). This report is research only.",
        "",
        f"Mined ≥85%: {len(all_streams)} · perfect-3y: {len(perfect)} · elapsed {payload['elapsed_s']}s",
        "",
        "## Results",
        "",
        "| Base desk | Range | Floor | Base 3y | New 3y | Δ | Hit | Candidate |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for desk_tag in EXPAND_TARGETS:
        r = results[desk_tag]
        b, g = r["baseline"]["3y"], r["result"]["3y"]
        lines.append(
            f"| `{desk_tag}` | `{r['accuracy_range']}` | {r['floor']:g} | "
            f"{b['n']}@{b['hit_pct']}% | **{g['n']}@{g['hit_pct']}%** | "
            f"{r['delta_3y_n']:+d} | {g['hit_pct']} | `{r['candidate_tag'] or '—'}` |"
        )

    lines += ["", "## Added streams", ""]
    for desk_tag in EXPAND_TARGETS:
        r = results[desk_tag]
        lines.append(f"### `{desk_tag}` → `{r['candidate_tag'] or 'no growth'}`")
        lines.append("")
        if not r["added_streams"]:
            lines.append("_No stream cleared same-accuracy gate._")
        else:
            lines += ["| # | Tag | + | Desk3y | Hit |", "|---:|---|---:|---:|---:|"]
            for i, a in enumerate(r["added_streams"], 1):
                lines.append(
                    f"| {i} | `{a['tag']}` | +{a['new_n']} | {a['desk_n_3y']} | {a['desk_hit_3y']} |"
                )
        lines.append("")

    lines += [
        "## Next",
        "",
        "- Keep Phase-1 locked.",
        "- Promote any candidate only after packaging + `confirm_accurate_desks_3y_match` still PASS for Phase-1.",
        "",
        "JSON: `ACC_PHASE2_SAME_ACC_MORE.json`",
        "",
    ]
    md = OUT / "ACC_PHASE2_SAME_ACC_MORE.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (LEDGER / "ACC_PHASE2_SAME_ACC_MORE.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", md, flush=True)


if __name__ == "__main__":
    main()
