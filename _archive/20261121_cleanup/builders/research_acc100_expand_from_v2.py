"""Keep held V1+V2; hunt more path-true 100% streams beyond V2.

Accept new streams only if union stays perfect on **3y and 5y**.
Uses 10y dual + path caches.

  python -u prod_live/tests/builders/research_acc100_expand_from_v2.py
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

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _hm_mins, _side, _ix, _side_days  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    filt,
    first_day,
    bestp_day,
    gap_map,
    is_perfect,
    time_agree,
    union_unique_days,
)
from prod_live.logic.acc100_streams import merge_acc100_multi_v2  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL_10Y = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH_10Y = LEDGER / "_cache_path_trusted_10y.json"

END = "2026-11-13"
START_1Y = (pd_ts := __import__("pandas").Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (__import__("pandas").Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_5Y = (__import__("pandas").Timestamp(END) - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
MIN_N = 5


def win_ok(rows: List[dict], start: str) -> bool:
    rs = _clip(rows, start, END)
    if len(rs) < 5:
        return True
    return is_perfect(rs)


def mine(path_u: dict, gaps: dict, active: set, dual15, dual5, proven, champ) -> List[Tuple[str, List[dict]]]:
    streams: List[Tuple[str, List[dict]]] = []

    def add(tag: str, rows: List[dict]) -> None:
        rows = _clip(rows, START_5Y, END)  # need 5y material
        if len(rows) < MIN_N:
            return
        if not is_perfect(_clip(rows, START_3Y, END)):
            return
        if not win_ok(rows, START_3Y) or not win_ok(rows, START_5Y):
            return
        if not win_ok(rows, START_1Y):
            return
        streams.append((tag, rows))

    bands = [
        ("first45", 9 * 60 + 15, 10 * 60),
        ("open", 9 * 60 + 15, 10 * 60 + 30),
        ("am11", 9 * 60 + 15, 11 * 60),
        ("am1130", 9 * 60 + 15, 11 * 60 + 30),
        ("am1230", 9 * 60 + 15, 12 * 60 + 30),
        ("mid", 10 * 60, 13 * 60),
        ("latemid", 10 * 60 + 30, 14 * 60),
        ("pm", 12 * 60 + 30, 15 * 60 + 15),
        ("all", None, None),
    ]
    gaps_opts = [
        ("nogap", None, False, False),
        ("g035", 0.35, False, False),
        ("g040", 0.40, False, False),
        ("g045", 0.45, False, False),
        ("g050", 0.50, False, False),
        ("g060", 0.60, False, False),
        ("gdn040", 0.40, True, False),
        ("gdn055", 0.55, True, False),
        ("gup040", 0.40, False, True),
        ("gup055", 0.55, False, True),
    ]

    # crown / good / champ / dual5 universes
    universes: Dict[str, List[dict]] = {}
    for rk, rows in (path_u.get("crown_by_risk") or {}).items():
        if str(rk).startswith("_"):
            continue
        universes[f"CR{str(rk).replace('.0','')}"] = rows
    for rk, rows in (path_u.get("good_by_risk") or {}).items():
        if str(rk).startswith("_") or rk == "native":
            continue
        universes[f"GD{str(rk).replace('.0','')}"] = rows
    universes["CH"] = path_u.get("champ_native") or champ
    universes["D5"] = dual5

    for uname, urows in universes.items():
        for side in (None, "BUY", "SELL"):
            for blab, lo, hi in bands:
                for glab, gabsm, gdn, gup in gaps_opts:
                    for use_htf in (False, True):
                        for pmin in (0.0, 0.52, 0.55, 0.57, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70, 0.75, 0.80, 0.85):
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
                                add(
                                    f"{uname}_{side or 'BOTH'}_p{int(pmin*100)}_{blab}_"
                                    f"{'htf' if use_htf else 'any'}_{glab}_{vlab}",
                                    vrows,
                                )

    # timed confirms
    ix15 = _ix(dual15)
    ix15p = _ix(proven)
    ix5 = _ix(dual5)
    for tol in (5, 10, 15, 20, 25, 30, 40, 45, 60, 90):
        add(f"CF_T{tol}_any15_d5", time_agree(ix15, ix5, tol=tol, tag="cf"))
        add(f"CF_T{tol}_p15_d5", time_agree(ix15p, ix5, tol=tol, tag="cf"))
        for rk, crow in (path_u.get("crown_by_risk") or {}).items():
            if str(rk).startswith("_"):
                continue
            add(
                f"CF_T{tol}_any15_cr{str(rk).replace('.0','')}",
                time_agree(ix15, _ix(crow), tol=tol, tag="cf"),
            )

    # dedupe by day-side-hm signature
    by_sig: Dict[tuple, Tuple[str, List[dict]]] = {}
    for tag, rows in streams:
        sig = tuple(sorted((str(r["day"]), _side(r), str(r.get("hm") or "")) for r in rows))
        prev = by_sig.get(sig)
        if prev is None or len(rows) > len(prev[1]):
            by_sig[sig] = (tag, rows)
    out = list(by_sig.values())
    out.sort(key=lambda x: len(x[1]), reverse=True)
    return out


def greedy(base: List[dict], streams: List[Tuple[str, List[dict]]]) -> Tuple[List[dict], List[dict]]:
    cur = list(base)
    added = []
    improved = True
    rounds = 0
    while improved and rounds < 40:
        improved = False
        rounds += 1
        cur_days = {str(r["day"]) for r in cur}
        ranked = []
        for tag, rows in streams:
            new_n = sum(1 for r in rows if str(r["day"]) not in cur_days)
            if new_n:
                ranked.append((new_n, tag, rows))
        ranked.sort(reverse=True)
        for new_n, tag, rows in ranked:
            merged = union_unique_days(cur, rows)
            if len(merged) <= len(cur):
                continue
            if not is_perfect(_clip(merged, START_3Y, END)):
                continue
            if not win_ok(merged, START_3Y) or not win_ok(merged, START_5Y):
                continue
            if not win_ok(merged, START_1Y):
                continue
            cur = merged
            added.append({"tag": tag, "new_n": new_n, "desk_n": len(cur), "stream_n": len(rows)})
            print(f"    +{new_n} {tag} → n={len(cur)}", flush=True)
            improved = True
            break
    return cur, added


def main() -> None:
    t0 = time.time()
    print("EXPAND from held ACC100_MULTI_V2 (keep V1+V2)", flush=True)

    dual = json.loads(CACHE_DUAL_10Y.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH_10Y.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_5Y < d <= END]
    daily = fs._load_daily()
    active = fs._active_days(sess, daily)

    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ = _champ_floor([dict(r, track="champion") for r in dual["dual15"]["champion"]])
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]

    crown_by_risk = path_u.get("crown_by_risk") or {}
    good_by_risk = path_u.get("good_by_risk") or {}
    champ_native = path_u.get("champ_native") or champ

    print("  rebuild V2 desk…", flush=True)
    v2 = merge_acc100_multi_v2(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active,
    )
    v2_3 = _clip(v2, START_3Y, END)
    v2_5 = _clip(v2, START_5Y, END)
    print(
        f"  V2 3y n={len(v2_3)} hit={_agg(v2_3).get('hit_pct')} | "
        f"5y n={len(v2_5)} hit={_agg(v2_5).get('hit_pct')}",
        flush=True,
    )
    base_n3 = len(v2_3)

    print("  mining streams…", flush=True)
    path_bundle = {
        "crown_by_risk": crown_by_risk,
        "good_by_risk": good_by_risk,
        "champ_native": champ_native,
    }
    streams = mine(path_bundle, gaps, active, dual15, dual5, proven, champ)
    print(f"  unique perfect streams (3y+5y)={len(streams)}", flush=True)

    print("  greedy onto V2…", flush=True)
    desk, added = greedy(v2, streams)
    # re-filter desk to union on full hist but score windows
    d3 = _clip(desk, START_3Y, END)
    d5 = _clip(desk, START_5Y, END)
    d1 = _clip(desk, START_1Y, END)

    payload = {
        "keep_held": ["ACC100_MULTI_V1", "ACC100_MULTI_V2"],
        "v2_baseline_3y_n": base_n3,
        "result": {
            "n_3y": len(d3),
            "hit_3y": _agg(d3).get("hit_pct"),
            "perfect_3y": is_perfect(d3),
            "points_3y": _agg(d3).get("points"),
            "n_5y": len(d5),
            "hit_5y": _agg(d5).get("hit_pct"),
            "perfect_5y": is_perfect(d5),
            "points_5y": _agg(d5).get("points"),
            "n_1y": len(d1),
            "hit_1y": _agg(d1).get("hit_pct"),
            "delta_vs_v2_3y": len(d3) - base_n3,
        },
        "added_streams": added,
        "streams_mined": len(streams),
        "elapsed_s": round(time.time() - t0, 1),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ACC100_EXPAND_FROM_V2.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (LEDGER / "ACC100_EXPAND_FROM_V2.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Expand beyond held ACC100_MULTI_V2",
        "",
        "**Keep held:** `ACC100_MULTI_V1` + `ACC100_MULTI_V2`",
        "",
        f"V2 baseline 3y n≈{base_n3}",
        "",
        f"**Result:** 3y **{payload['result']['n_3y']}** @ {payload['result']['hit_3y']}% "
        f"(Δ {payload['result']['delta_vs_v2_3y']:+d}) · "
        f"5y **{payload['result']['n_5y']}** @ {payload['result']['hit_5y']}% · "
        f"1y {payload['result']['n_1y']} @ {payload['result']['hit_1y']}%",
        "",
        f"Mined streams: {len(streams)} · elapsed {payload['elapsed_s']}s",
        "",
        "## Added onto V2",
        "",
    ]
    if not added:
        lines.append("_No new stream cleared 3y+5y perfect union._")
    else:
        lines += ["| # | Tag | +days | Desk n |", "|---:|---|---:|---:|"]
        for i, a in enumerate(added, 1):
            lines.append(f"| {i} | `{a['tag']}` | +{a['new_n']} | {a['desk_n']} |")

    lines += ["", "## Verdict", ""]
    if added and payload["result"]["perfect_3y"] and payload["result"]["perfect_5y"]:
        lines.append(
            f"**Candidate ACC100_MULTI_V3** — keep V1+V2 nested; +{payload['result']['delta_vs_v2_3y']} on 3y."
        )
    else:
        lines.append("V1+V2 remain best under 3y+5y perfect gate. Continue hunting.")
    lines += ["", "JSON: `ACC100_EXPAND_FROM_V2.json`", ""]

    md = OUT / "ACC100_EXPAND_FROM_V2.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (LEDGER / "ACC100_EXPAND_FROM_V2.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", md, flush=True)
    print(json.dumps(payload["result"], indent=2), flush=True)
    print("added", json.dumps(added, indent=2), flush=True)


if __name__ == "__main__":
    main()
