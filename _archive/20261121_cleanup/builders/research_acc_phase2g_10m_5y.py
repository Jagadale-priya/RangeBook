"""Hold locked P2G_10m recipes · confirm on **5y** (extra 2y beyond held 3y).

3y already confirmed. This scores full 5y + the older 2y slice only
(`2021-11-16` → `2023-11-15`), same held stream tags / no re-greedy.

  python -u prod_live/tests/builders/research_acc_phase2g_10m_5y.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _side  # noqa: E402
from research_100pct_deeper_more_calls import gap_map, union_unique_days  # noqa: E402
from prod_live.logic.accurate_desks import build_all_accurate_desks  # noqa: E402
from prod_live.logic.p2g_10m import (  # noqa: E402
    BASE_KEY_BY_DESK,
    DAY_DESKS,
    HARD_GATES,
    WINDOW_1Y,
    WINDOW_3Y,
    WINDOW_5Y,
    WINDOW_EXTRA_2Y,
)
from research_acc_phase2g_10m_1y import (  # noqa: E402
    desk_ok,
    load_d10,
    mine_streams,
    stamp,
    universes_p2g,
)

OUT = ROOT / "prod_live" / "reports" / "5y"
HOLD = ROOT / "prod_live" / "holding_accurate"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
RECIPES = HOLD / "phase2g" / "recipes_research.json"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"

START_5Y, END = WINDOW_5Y["start"], WINDOW_5Y["end"]
START_3Y = WINDOW_3Y["start"]
START_1Y = WINDOW_1Y["start"]
EXTRA_A, EXTRA_B = WINDOW_EXTRA_2Y["start"], WINDOW_EXTRA_2Y["end"]


def hit_ok(rows: List[dict], a: str, b: str, floor: float, min_n: int = 3) -> bool:
    rs = _clip(rows, a, b)
    if len(rs) < min_n:
        return True  # thin slice — don't fail floor on sparse older window
    hit = 100.0 * sum(1 for r in rs if r.get("win")) / len(rs)
    return hit + 1e-9 >= floor


def year_splits(rows: List[dict], a: str, b: str) -> List[Dict[str, Any]]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in _clip(rows, a, b):
        day = str(r.get("day") or "")
        if len(day) >= 4:
            by[day[:4]].append(r)
    out = []
    for y in sorted(by):
        sc = _agg(by[y])
        out.append({"year": y, "n": sc.get("n"), "hit_pct": sc.get("hit_pct"), "wins": sc.get("wins")})
    return out


def rebuild_held(
    seed: List[dict],
    tags: List[str],
    by_tag: Dict[str, List[dict]],
    floor: float,
) -> Tuple[List[dict], List[str], List[str], bool]:
    cur = list(seed)
    seed_kept = True
    if not desk_ok(cur, floor):
        cur = []
        seed_kept = False
    applied: List[str] = []
    missing: List[str] = []
    for tag in tags:
        rows = by_tag.get(tag)
        if not rows:
            missing.append(tag)
            continue
        cur = union_unique_days(cur, rows)
        applied.append(tag)
    return cur, applied, missing, seed_kept


def main() -> int:
    t0 = time.time()
    print(f"P2G_10M HOLD · 5y test {START_5Y} → {END}", flush=True)
    print(f"  extra 2y (beyond 3y): {EXTRA_A} → {EXTRA_B}", flush=True)
    recipes = json.loads(RECIPES.read_text(encoding="utf-8"))
    cand = recipes.get("candidates") or {}

    dual = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    # HTF active over full 5y so older streams rebuild consistently
    sess = [d for d in sessions_all if START_5Y < d <= END]
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

    print("  score D10…", flush=True)
    d10 = load_d10()
    univ = universes_p2g(path_u, d10, champ_native)

    print("  mine streams (materialize locked tags)…", flush=True)
    streams_all = mine_streams(univ, gaps, active, floor_min=82.71)
    by_tag = {t: rows for t, rows in streams_all}

    results: Dict[str, Any] = {}
    books: Dict[str, List[dict]] = {}
    lines = [
        "# Phase-2G HOLD — 10m dual · 5y confirm",
        "",
        "**Status:** RESEARCH · **not live** · logic **held** (no re-greedy)",
        f"**Recipes:** `holding_accurate/phase2g/recipes_research.json`",
        f"**Window 5y:** `{START_5Y}` → `{END}`",
        f"**Already held 3y:** `{START_3Y}` → `{END}`",
        f"**Extra 2y only:** `{EXTRA_A}` → `{EXTRA_B}`",
        f"D10 n={len(d10)} · mined streams={len(streams_all)}",
        "",
        "> Note: crown path denser from ~2024-05 — older 2y is thinner (mostly GD/D10/CH).",
        "",
        "## Desk ladder",
        "",
        "| P2G desk | Floor | Extra2y N@hit | Extra OK | 3y N@hit | 5y N@hit | 5y OK | 1y N@hit |",
        "|---|---:|---|---|---|---|---|---|",
    ]

    for desk in DAY_DESKS:
        floor = HARD_GATES[desk]
        base_key = BASE_KEY_BY_DESK[desk]
        meta = cand.get(base_key) or {}
        tags = list(meta.get("stream_tags_research") or [])
        seed = list(phase1.get(base_key) or [])
        print(f"  rebuild {desk} tags={len(tags)}…", flush=True)
        rows, applied, missing, seed_kept = rebuild_held(seed, tags, by_tag, floor)
        rows = stamp(rows, desk)
        books[desk] = rows

        sc5 = _agg(_clip(rows, START_5Y, END))
        sc3 = _agg(_clip(rows, START_3Y, END))
        sc1 = _agg(_clip(rows, START_1Y, END))
        sc2 = _agg(_clip(rows, EXTRA_A, EXTRA_B))
        ok3 = desk_ok(rows, floor)
        ok5 = hit_ok(rows, START_5Y, END, floor)
        ok2 = hit_ok(rows, EXTRA_A, EXTRA_B, floor, min_n=3)

        results[desk] = {
            "floor": floor,
            "base": base_key,
            "seed_kept": seed_kept,
            "ok_3y_gate": ok3,
            "ok_5y": ok5,
            "ok_extra_2y": ok2,
            "n_streams_applied": len(applied),
            "missing_tags": missing,
            "extra_2y": sc2,
            "3y": sc3,
            "5y": sc5,
            "1y": sc1,
            "by_year_5y": year_splits(rows, START_5Y, END),
        }
        lines.append(
            f"| `{desk}` | {floor} | {sc2.get('n')}@{sc2.get('hit_pct')} | "
            f"{'Y' if ok2 else 'N'} | {sc3.get('n')}@{sc3.get('hit_pct')} | "
            f"{sc5.get('n')}@{sc5.get('hit_pct')} | {'Y' if ok5 else 'N'} | "
            f"{sc1.get('n')}@{sc1.get('hit_pct')} |"
        )
        print(
            f"    → extra2y {sc2.get('n')}@{sc2.get('hit_pct')}%  "
            f"5y {sc5.get('n')}@{sc5.get('hit_pct')}% ok5={ok5}",
            flush=True,
        )

    # Year splits top + all
    lines.extend(["", "## Year splits (inside 5y)", ""])
    for desk in DAY_DESKS:
        lines.append(f"### `{desk}`")
        lines.append("")
        lines.append("| Year | N | Hit% | W |")
        lines.append("|---|---:|---:|---:|")
        for y in results[desk]["by_year_5y"]:
            lines.append(
                f"| {y['year']} | {y['n']} | {y['hit_pct']} | {y.get('wins', '')} |"
            )
        lines.append("")

    # Extra 2y call list for top desk
    top = DAY_DESKS[0]
    extra_rows = sorted(
        _clip(books[top], EXTRA_A, EXTRA_B),
        key=lambda x: (x.get("day"), x.get("hm")),
    )
    lines.extend(
        [
            f"## Extra 2y calls — `{top}` (`{EXTRA_A}` → `{EXTRA_B}`)",
            "",
            "| # | Day | HM | Side | Win | p |",
            "|---:|---|---|---|---|---:|",
        ]
    )
    for i, r in enumerate(extra_rows, 1):
        lines.append(
            f"| {i} | {r.get('day')} | {r.get('hm')} | {_side(r)} | "
            f"{'W' if r.get('win') else 'L'} | {r.get('p_t1')} |"
        )
    sc_ex = results[top]["extra_2y"]
    lines.extend(
        [
            "",
            f"**N={sc_ex.get('n')}** · hit **{sc_ex.get('hit_pct')}%** "
            f"({sc_ex.get('wins')}W)",
            "",
        ]
    )

    # Sample full 5y (first/last of top)
    sample = sorted(_clip(books[top], START_5Y, END), key=lambda x: (x.get("day"), x.get("hm")))
    lines.extend(
        [
            f"## Sample 5y — `{top}` (first 20 + last 20)",
            "",
            "| Day | HM | Side | Win | p |",
            "|---|---|---|---|---:|",
        ]
    )
    show = sample[:20] + (sample[-20:] if len(sample) > 40 else sample[20:])
    seen = set()
    for r in show:
        key = (r.get("day"), r.get("hm"), _side(r))
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {_side(r)} | "
            f"{'W' if r.get('win') else 'L'} | {r.get('p_t1')} |"
        )

    top5 = results[top]["5y"]
    top2 = results[top]["extra_2y"]
    all5 = all(results[d]["ok_5y"] for d in DAY_DESKS)
    all2 = all(results[d]["ok_extra_2y"] for d in DAY_DESKS)
    if results[top]["ok_5y"] and float(top5.get("hit_pct") or 0) >= 99.9:
        verdict = (
            f"HOLD OK 5y — `{top}` {top5.get('n')}@{top5.get('hit_pct')}% · "
            f"extra2y {top2.get('n')}@{top2.get('hit_pct')}% · "
            f"floors {'all clear' if all5 else 'some soft on 5y'} · "
            f"extra2y floors {'all clear' if all2 else 'some soft'} · still RESEARCH."
        )
    elif results[top]["ok_5y"]:
        verdict = (
            f"HOLD PARTIAL 5y — `{top}` {top5.get('n')}@{top5.get('hit_pct')}% · "
            f"extra2y {top2.get('n')}@{top2.get('hit_pct')}%."
        )
    else:
        verdict = (
            f"HOLD FAIL 5y — `{top}` breaks floor · "
            f"{top5.get('n')}@{top5.get('hit_pct')}% · "
            f"extra2y {top2.get('n')}@{top2.get('hit_pct')}%."
        )

    elapsed = round(time.time() - t0, 1)
    lines.extend(["", "## Verdict", "", verdict, "", f"Elapsed {elapsed}s", ""])

    for desk in DAY_DESKS:
        base_key = BASE_KEY_BY_DESK[desk]
        if base_key in cand:
            cand[base_key]["research_5y"] = {
                "n": results[desk]["5y"].get("n"),
                "hit_pct": results[desk]["5y"].get("hit_pct"),
            }
            cand[base_key]["research_extra_2y"] = {
                "n": results[desk]["extra_2y"].get("n"),
                "hit_pct": results[desk]["extra_2y"].get("hit_pct"),
                "window": WINDOW_EXTRA_2Y,
            }
            cand[base_key]["held_5y_ok"] = results[desk]["ok_5y"]
    recipes["window_5y"] = WINDOW_5Y
    recipes["window_extra_2y"] = WINDOW_EXTRA_2Y
    recipes["last_5y_confirm"] = {"verdict": verdict, "elapsed_s": elapsed, "end": END}
    RECIPES.write_text(json.dumps(recipes, indent=2, default=str), encoding="utf-8")

    payload = {
        "status": "RESEARCH",
        "not_live": True,
        "phase": "2g",
        "mode": "hold_confirm_5y",
        "dual_model": "10m_train",
        "window_5y": WINDOW_5Y,
        "window_extra_2y": WINDOW_EXTRA_2Y,
        "window_3y": WINDOW_3Y,
        "window_1y": WINDOW_1Y,
        "results": results,
        "verdict": verdict,
        "elapsed_s": elapsed,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "ACC_PHASE2G_10M_5Y.md"
    js = OUT / "ACC_PHASE2G_10M_5Y.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    logic_md = HOLD / "phase2g" / "PHASE2G_LOGIC.md"
    if logic_md.exists():
        text = logic_md.read_text(encoding="utf-8")
        if "ACC_PHASE2G_10M_5Y" not in text:
            text = text.rstrip() + (
                "\n\n**5y confirm (held recipes · extra 2y beyond 3y):** "
                "`prod_live/tests/builders/research_acc_phase2g_10m_5y.py`  \n"
                "**Report:** `prod_live/reports/5y/ACC_PHASE2G_10M_5Y.md`\n"
            )
            logic_md.write_text(text, encoding="utf-8")

    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
