"""Expand beyond held ACC100_MULTI_V1 (n=70 @ 100%) with more path-true streams.

Baseline held (do not change):
  proven ∪ confirm_t30 ∪ crown_BUY_am1130_T20 ∪ good_BUY_latemid_gap045_T30

Hunt: mine many path-trusted perfect streams; greedy-union onto V1 if still
3y+1y perfect. Hold V2 only if n>70.

  python -u prod_live/tests/builders/research_acc100_expand_from_v1.py
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
from accuracy_max_6m import _agg  # noqa: E402
from research_confirm_dual_tf_deep import _clip  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    START_1Y,
    START_3Y,
    START_NOV,
    END,
    filt,
    first_day,
    bestp_day,
    gap_map,
    is_perfect,
    time_agree,
    union_unique_days,
    path_rescore_list,
    build_bar_index,
    _norm,
    TAPE15,
    TAPE5,
)
from research_confirm_dual_tf_deep import _ix, _side_days, _hm_mins, _side  # noqa: E402
from prod_live.logic.confirm_dual_tf import (  # noqa: E402
    build_confirm_rows,
    merge_proven15_plus_confirm,
)
from prod_live.logic.acc100_streams import (  # noqa: E402
    filter_crown_buy_am1130,
    filter_good_buy_latemid_gap,
    TAG_DESK,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_confirm.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_calls.json"
CACHE_EXTRA = LEDGER / "_cache_path_trusted_extra_risks.json"

HELD_N = 70
MIN_STREAM_N = 5


def months_perfect(rows: List[dict], start: str, end: str) -> bool:
    rs = _clip(rows, start, end)
    if len(rs) < 5:
        return True  # too thin to reject
    return is_perfect(rs)


def build_v1(
    cached: dict,
    path_u: dict,
    gaps: Dict[str, float],
) -> List[dict]:
    proven = [dict(r, track="proven_100") for r in cached["dual15"]["proven_100"]]
    dual15 = cached["dual15"]["proven_100"] + cached["dual15"]["champion"]
    dual5 = cached["dual5"]["proven_100"] + cached["dual5"]["champion"]
    confirm = build_confirm_rows(dual15, dual5, tol_min=30)
    base = merge_proven15_plus_confirm(proven, confirm)
    crown = filter_crown_buy_am1130(path_u["crown_by_risk"]["20.0"])
    # only path winners
    crown = [r for r in crown if r.get("win")]
    good = filter_good_buy_latemid_gap(path_u["good_t30"], gaps, gap_abs=0.45)
    good = [r for r in good if r.get("win")]
    out = union_unique_days(base, _clip(crown, START_3Y, END))
    out = union_unique_days(out, _clip(good, START_3Y, END))
    return out


def mine_streams(
    *,
    path_u: dict,
    gaps: Dict[str, float],
    active: Set[str],
    dual15: List[dict],
    dual5: List[dict],
    proven: List[dict],
    champ: List[dict],
) -> List[Tuple[str, List[dict]]]:
    streams: List[Tuple[str, List[dict]]] = []

    def add(tag: str, rows: List[dict]) -> None:
        rows = _clip(rows, START_3Y, END)
        if len(rows) < MIN_STREAM_N:
            return
        if not is_perfect(rows):
            return
        if not months_perfect(rows, START_1Y, END):
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
    gap_opts = [
        ("nogap", None, False, False),
        ("g040", 0.40, False, False),
        ("g045", 0.45, False, False),
        ("g050", 0.50, False, False),
        ("g055", 0.55, False, False),
        ("gdn045", 0.45, True, False),
        ("gup045", 0.45, False, True),
        ("gdn055", 0.55, True, False),
        ("gup055", 0.55, False, True),
    ]

    # --- crown all risks / sides / bands ---
    for risk, crow in path_u["crown_by_risk"].items():
        rk = risk.replace(".0", "")
        for side in (None, "BUY", "SELL"):
            for blab, lo, hi in bands:
                for glab, gabsm, gdn, gup in gap_opts:
                    for use_htf in (False, True):
                        for pmin in (0.0, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.70):
                            base = filt(
                                crow,
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
                                # skip exact held crown stream clone later in greedy
                                tag = (
                                    f"CR_T{rk}_{side or 'BOTH'}_p{int(pmin*100)}_"
                                    f"{blab}_{'htf' if use_htf else 'any'}_{glab}_{vlab}"
                                )
                                add(tag, vrows)

    # --- good at multiple path risks ---
    good_map = {
        "30": path_u["good_t30"],
        "native": path_u["good_native"],
    }
    for extra_k, extra_rows in (path_u.get("good_by_risk") or {}).items():
        good_map[extra_k] = extra_rows

    for gk, grows in good_map.items():
        for side in (None, "BUY", "SELL"):
            for blab, lo, hi in bands:
                for glab, gabsm, gdn, gup in gap_opts:
                    for use_htf in (False, True):
                        for pmin in (0.0, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.70, 0.75):
                            base = filt(
                                grows,
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
                                tag = (
                                    f"GD_{gk}_{side or 'BOTH'}_p{int(pmin*100)}_"
                                    f"{blab}_{'htf' if use_htf else 'any'}_{glab}_{vlab}"
                                )
                                add(tag, vrows)

    # --- champ / dual5 ---
    for label, rows in (
        ("CH", path_u["champ_native"]),
        ("D5", path_u["dual5_native"]),
    ):
        for side in (None, "BUY", "SELL"):
            for blab, lo, hi in bands:
                for pmin in (0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70, 0.75, 0.80, 0.85, 0.90):
                    for glab, gabsm, gdn, gup in gap_opts[:5]:
                        base = filt(
                            rows,
                            p_min=pmin,
                            side=side,
                            hm_lo=lo,
                            hm_hi=hi,
                            gaps=gaps if gabsm else None,
                            gap_abs=gabsm,
                            gap_dn=gdn,
                            gap_up=gup,
                        )
                        for vlab, vrows in (("raw", base), ("first", first_day(base)), ("bestp", bestp_day(base))):
                            add(
                                f"{label}_{side or 'BOTH'}_p{int(pmin*100)}_{blab}_{glab}_{vlab}",
                                vrows,
                            )

    # --- timed agrees / day-side intersects ---
    ix15 = _ix(dual15)
    ix15p = _ix(proven)
    ix15c = _ix(champ)
    ix5 = _ix(dual5)
    for tol in (10, 15, 20, 30, 45, 60, 90):
        for gname, gix in (("any15", ix15), ("p15", ix15p), ("c15", ix15c)):
            add(f"CF_T{tol}_{gname}_d5", time_agree(gix, ix5, tol=tol, tag="cf"))
            for rk, crow in path_u["crown_by_risk"].items():
                add(
                    f"CF_T{tol}_{gname}_cr{rk.replace('.0','')}",
                    time_agree(gix, _ix(crow), tol=tol, tag="cf"),
                )

    for gname, sides in (
        ("any15", _side_days(dual15)),
        ("p15", _side_days(proven)),
        ("c15", _side_days(champ)),
    ):
        for rk, crow in list(path_u["crown_by_risk"].items())[:3]:
            kept = [dict(r) for r in crow if _side(r) in sides.get(str(r["day"]), set())]
            for side in (None, "BUY", "SELL"):
                for pmin in (0.55, 0.58, 0.60, 0.62):
                    for blab, lo, hi in (("am1130", 9 * 60 + 15, 11 * 60 + 30), ("am1230", 9 * 60 + 15, 12 * 60 + 30), ("all", None, None)):
                        base = filt(kept, side=side, p_min=pmin, hm_lo=lo, hm_hi=hi)
                        add(
                            f"CRIF_{gname}_{rk.replace('.0','')}_{side or 'BOTH'}_p{int(pmin*100)}_{blab}_first",
                            first_day(base),
                        )

    # dedupe identical day-sets keep max points tag
    by_sig: Dict[Tuple[Tuple[str, str, str], ...], Tuple[str, List[dict]]] = {}
    for tag, rows in streams:
        sig = tuple(sorted((str(r["day"]), _side(r), str(r.get("hm") or "")) for r in rows))
        prev = by_sig.get(sig)
        if prev is None or len(rows) > len(prev[1]):
            by_sig[sig] = (tag, rows)
    uniq = list(by_sig.values())
    uniq.sort(key=lambda x: len(x[1]), reverse=True)
    return uniq


def greedy_union(
    base: List[dict],
    streams: List[Tuple[str, List[dict]]],
) -> Tuple[List[dict], List[Dict[str, Any]]]:
    cur = list(base)
    added: List[Dict[str, Any]] = []
    base_days = {str(r["day"]) for r in cur}
    # prioritize streams with most new days vs current
    improved = True
    round_i = 0
    while improved and round_i < 30:
        improved = False
        round_i += 1
        ranked = []
        cur_days = {str(r["day"]) for r in cur}
        for tag, rows in streams:
            new_rows = [r for r in rows if str(r["day"]) not in cur_days]
            if not new_rows:
                continue
            ranked.append((len(new_rows), tag, rows, new_rows))
        ranked.sort(reverse=True)
        for nnew, tag, rows, new_rows in ranked:
            merged = union_unique_days(cur, rows)
            if len(merged) <= len(cur):
                continue
            if not is_perfect(merged):
                continue
            if not months_perfect(merged, START_1Y, END):
                continue
            # also 6m sanity
            if not months_perfect(merged, "2026-05-14", END):
                continue
            cur = merged
            st = _agg(new_rows)
            added.append(
                {
                    "tag": tag,
                    "new_n": nnew,
                    "desk_n": len(cur),
                    "stream_n": len(rows),
                    "stream_points": st.get("points"),
                }
            )
            print(
                f"    +{nnew} from {tag} → desk n={len(cur)}",
                flush=True,
            )
            improved = True
            break  # restart ranking after accept
    return cur, added


def main() -> None:
    t0 = time.time()
    print("EXPAND from ACC100_MULTI_V1 (held n=70)", flush=True)

    cached = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))["universe"]
    gaps = gap_map()
    sessions_all, prod2_all, _ = fs._prod2(1400)
    sess = [d for d in sessions_all if START_3Y < d <= END]
    daily = fs._load_daily()
    active = fs._active_days(sess, daily)

    # extra good path risks if missing
    if not path_u.get("good_by_risk"):
        print("  path-scoring good @ T20/T25/T35…", flush=True)
        import pandas as pd

        bars15 = _norm(pd.read_csv(TAPE15, index_col=0, parse_dates=True))
        ix15 = build_bar_index(bars15)
        good_raw = []
        for r in prod2_all:
            if START_3Y < str(r.get("day") or "") <= END:
                good_raw.append(dict(r, track="good_prod2"))
        good_by_risk = {}
        for risk in (20.0, 25.0, 35.0, 40.0):
            good_by_risk[str(int(risk))] = path_rescore_list(
                good_raw, bars15, ix15, risk=risk, label=f"good_T{int(risk)}"
            )
        path_u["good_by_risk"] = good_by_risk
        # persist extra
        full = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        full["universe"]["good_by_risk"] = good_by_risk
        CACHE_PATH.write_text(json.dumps(full, indent=2, default=str), encoding="utf-8")

    v1 = build_v1(cached, path_u, gaps)
    st1 = _agg(_clip(v1, START_3Y, END))
    print(f"  V1 baseline n={st1['n']} hit={st1['hit_pct']}% pts={st1.get('points')}", flush=True)
    assert st1["n"] >= 65 and st1.get("hit_pct") == 100.0, st1

    proven = [dict(r, track="proven_100") for r in cached["dual15"]["proven_100"]]
    champ = [dict(r, track="champion") for r in cached["dual15"]["champion"]]
    dual15 = proven + champ
    dual5 = [dict(r) for r in cached["dual5"]["proven_100"] + cached["dual5"]["champion"]]

    print("  mining streams (broad grid)…", flush=True)
    streams = mine_streams(
        path_u=path_u,
        gaps=gaps,
        active=active,
        dual15=dual15,
        dual5=dual5,
        proven=proven,
        champ=champ,
    )
    print(f"  unique perfect streams={len(streams)}", flush=True)

    # exclude exact V1 component signatures roughly by skipping tags that are held clones with 0 new days
    print("  greedy union onto V1…", flush=True)
    desk, added = greedy_union(v1, streams)

    st = _agg(_clip(desk, START_3Y, END))
    st1y = _agg(_clip(desk, START_1Y, END))
    stn = _agg(_clip(desk, START_NOV, END))
    print(
        f"  RESULT n={st['n']} hit={st['hit_pct']}% (+{st['n']-HELD_N} vs V1) "
        f"1y={st1y['n']}@{st1y['hit_pct']}% nov={stn['n']}",
        flush=True,
    )

    # top unused streams by new days vs final desk
    final_days = {str(r["day"]) for r in desk}
    leftovers = []
    for tag, rows in streams:
        new_n = sum(1 for r in rows if str(r["day"]) not in final_days)
        if new_n <= 0:
            continue
        # test if would break
        merged = union_unique_days(desk, rows)
        leftovers.append(
            {
                "tag": tag,
                "new_n": new_n,
                "stream_n": len(rows),
                "would_perfect": is_perfect(merged),
                "would_n": len(merged),
            }
        )
    leftovers.sort(key=lambda x: (x["would_perfect"], x["new_n"]), reverse=True)

    payload = {
        "held_v1_n": HELD_N,
        "v1_check": st1,
        "result": {
            "n_3y": st["n"],
            "hit_3y": st["hit_pct"],
            "points_3y": st.get("points"),
            "n_1y": st1y["n"],
            "hit_1y": st1y["hit_pct"],
            "n_nov": stn["n"],
            "hit_nov": stn.get("hit_pct"),
            "delta_vs_v1": st["n"] - HELD_N,
        },
        "added_streams": added,
        "streams_mined": len(streams),
        "leftovers_top": leftovers[:30],
        "elapsed_s": round(time.time() - t0, 1),
    }

    # save desk rows for holding
    (OUT / "ACC100_MULTI_V2_CANDIDATE.json").write_text(
        json.dumps(
            {
                **payload,
                "desk_rows": [
                    {
                        "day": r.get("day"),
                        "hm": r.get("hm"),
                        "decision": r.get("decision"),
                        "track": r.get("track"),
                        "holding_tag": r.get("holding_tag") or r.get("accurate_tag") or r.get("confirm_tag"),
                        "win": r.get("win"),
                        "points": r.get("points"),
                        "p_t1": r.get("p_t1"),
                        "risk": r.get("risk") or r.get("path_risk"),
                    }
                    for r in sorted(desk, key=lambda x: str(x.get("day") or ""))
                ],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    lines = [
        "# Expand ACC100_MULTI_V1 → more 100% calls",
        "",
        f"**Held V1:** n={HELD_N} @ 100% (locked)",
        "",
        f"**Result desk:** n=**{st['n']}** @ {st['hit_pct']}% · Δ **+{st['n']-HELD_N}**",
        f"1y: {st1y['n']} @ {st1y['hit_pct']}% · Nov: {stn['n']} @ {stn.get('hit_pct')}%",
        "",
        f"Mined unique perfect streams: **{len(streams)}** · elapsed {payload['elapsed_s']}s",
        "",
        "## Streams added onto V1",
        "",
    ]
    if not added:
        lines.append("_No additional stream cleared 3y+1y+6m perfect union._")
    else:
        lines += ["| Order | Tag | +days | Desk n |", "|---:|---|---:|---:|"]
        for i, a in enumerate(added, 1):
            lines.append(f"| {i} | `{a['tag']}` | +{a['new_n']} | {a['desk_n']} |")

    lines += ["", "## Near-miss leftovers (new days but break perfect)", ""]
    broken = [x for x in leftovers if not x["would_perfect"]][:15]
    okish = [x for x in leftovers if x["would_perfect"]][:15]
    if okish:
        lines.append("Still-perfect leftovers (should have been greedily taken — check):")
        for x in okish:
            lines.append(f"- `{x['tag']}` +{x['new_n']} → would n={x['would_n']}")
    if broken:
        lines.append("")
        lines.append("Break perfect if added:")
        for x in broken:
            lines.append(f"- `{x['tag']}` +{x['new_n']}")

    lines += [
        "",
        "## Verdict",
        "",
    ]
    if st["n"] > HELD_N and st.get("hit_pct") == 100.0:
        lines += [
            f"**Promote candidate `ACC100_MULTI_V2`** with n={st['n']} @ 100%.",
            "V1 remains nested inside; new streams listed above.",
        ]
    else:
        lines += [
            "V1 remains best. No safe expand found under path-true + both-year gates.",
            "Keep hunting with richer features / new models.",
        ]
    lines += ["", "JSON: `prod_live/reports/1y/ACC100_MULTI_V2_CANDIDATE.json`", ""]

    md = OUT / "ACC100_EXPAND_FROM_V1.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (LEDGER / "ACC100_EXPAND_FROM_V1.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "ACC100_EXPAND_FROM_V1.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    print("Wrote", md, flush=True)
    print(json.dumps(payload["result"], indent=2), flush=True)
    print("added", json.dumps(added, indent=2), flush=True)


if __name__ == "__main__":
    main()
