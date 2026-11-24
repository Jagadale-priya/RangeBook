"""Hold locked P2G_10m recipes · confirm / test on **3y** window.

Does NOT re-greedy expand. Rebuilds each desk from Phase-1 seed + locked
`stream_tags_research` in recipe order, then scores 3y (and 1y side).

  python -u prod_live/tests/builders/research_acc_phase2g_10m_3y.py
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
)
from research_acc_phase2g_10m_1y import (  # noqa: E402
    desk_ok,
    load_d10,
    mine_streams,
    stamp,
    universes_p2g,
)

OUT = ROOT / "prod_live" / "reports" / "3y"
HOLD = ROOT / "prod_live" / "holding_accurate"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
RECIPES = HOLD / "phase2g" / "recipes_research.json"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"

START_3Y, END = WINDOW_3Y["start"], WINDOW_3Y["end"]
START_1Y = WINDOW_1Y["start"]


def year_splits(rows: List[dict]) -> List[Dict[str, Any]]:
    """Calendar year buckets inside the 3y window."""
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in _clip(rows, START_3Y, END):
        day = str(r.get("day") or "")
        if len(day) >= 4:
            by[day[:4]].append(r)
    out = []
    for y in sorted(by):
        sc = _agg(by[y])
        out.append({"year": y, "n": sc.get("n"), "hit_pct": sc.get("hit_pct"), "wins": sc.get("wins")})
    return out


def monthly(rows: List[dict]) -> List[Dict[str, Any]]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in _clip(rows, START_3Y, END):
        day = str(r.get("day") or "")
        if len(day) >= 7:
            by[day[:7]].append(r)
    out = []
    for m in sorted(by):
        sc = _agg(by[m])
        out.append({"month": m, "n": sc.get("n"), "hit_pct": sc.get("hit_pct"), "wins": sc.get("wins")})
    return out


def rebuild_held(
    seed: List[dict],
    tags: List[str],
    by_tag: Dict[str, List[dict]],
    floor: float,
) -> Tuple[List[dict], List[str], List[str], bool]:
    """Apply locked stream tags in order (same seed rule as greedy_expand)."""
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
    print(f"P2G_10M HOLD · 3y test {START_3Y} → {END}", flush=True)
    recipes = json.loads(RECIPES.read_text(encoding="utf-8"))
    cand = recipes.get("candidates") or {}
    print(f"  locked recipes desks={len(cand)} from {RECIPES.name}", flush=True)

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

    print("  score D10…", flush=True)
    d10 = load_d10()
    univ = universes_p2g(path_u, d10, champ_native)

    print("  mine streams (materialize locked tags)…", flush=True)
    streams_all = mine_streams(univ, gaps, active, floor_min=82.71)
    by_tag = {t: rows for t, rows in streams_all}

    results: Dict[str, Any] = {}
    books: Dict[str, List[dict]] = {}
    lines = [
        "# Phase-2G HOLD — 10m dual · 3y confirm",
        "",
        "**Status:** RESEARCH · **not live** · logic **held** (no re-greedy)",
        f"**Recipes:** `holding_accurate/phase2g/recipes_research.json`",
        f"**Window 3y:** `{START_3Y}` → `{END}` · 1y side `{START_1Y}` → `{END}`",
        f"D10 n={len(d10)} · mined streams={len(streams_all)}",
        "",
        "## Desk ladder (held logic)",
        "",
        "| P2G desk | Floor | 3y N@hit | Floor OK | 1y N@hit | Streams applied | Missing |",
        "|---|---:|---|---|---|---:|---:|",
    ]

    for desk in DAY_DESKS:
        floor = HARD_GATES[desk]
        base_key = BASE_KEY_BY_DESK[desk]
        meta = cand.get(base_key) or {}
        tags = list(meta.get("stream_tags_research") or [])
        seed = list(phase1.get(base_key) or [])
        print(f"  rebuild {desk} seed={len(seed)} tags={len(tags)}…", flush=True)
        rows, applied, missing, seed_kept = rebuild_held(seed, tags, by_tag, floor)
        rows = stamp(rows, desk)
        books[desk] = rows
        sc3 = _agg(_clip(rows, START_3Y, END))
        sc1 = _agg(_clip(rows, START_1Y, END))
        ok = desk_ok(rows, floor)
        ys = year_splits(rows)
        results[desk] = {
            "floor": floor,
            "base": base_key,
            "ok": ok,
            "seed_kept": seed_kept,
            "n_streams_locked": len(tags),
            "n_streams_applied": len(applied),
            "missing_tags": missing,
            "3y": sc3,
            "1y": sc1,
            "by_year": ys,
            "recipe_3y": meta.get("research_3y"),
            "recipe_1y": meta.get("research_1y"),
        }
        lines.append(
            f"| `{desk}` | {floor} | {sc3.get('n')}@{sc3.get('hit_pct')} | "
            f"{'Y' if ok else 'N'} | {sc1.get('n')}@{sc1.get('hit_pct')} | "
            f"{len(applied)}/{len(tags)} | {len(missing)} |"
        )
        print(
            f"    → 3y {sc3.get('n')}@{sc3.get('hit_pct')}% ok={ok} "
            f"seed_kept={seed_kept} applied={len(applied)} miss={len(missing)}",
            flush=True,
        )

    # Year splits for each desk
    lines.extend(["", "## Year splits (inside 3y)", ""])
    for desk in DAY_DESKS:
        lines.append(f"### `{desk}`")
        lines.append("")
        lines.append("| Year | N | Hit% | W |")
        lines.append("|---|---:|---:|---:|")
        for y in results[desk]["by_year"]:
            lines.append(
                f"| {y['year']} | {y['n']} | {y['hit_pct']} | {y.get('wins', '')} |"
            )
        lines.append("")

    # Monthly for top 100% desk
    top = DAY_DESKS[0]
    top_rows = books[top]
    lines.extend(
        [
            f"## Monthly — `{top}` (3y)",
            "",
            "| Month | N | Hit% | W |",
            "|---|---:|---:|---:|",
        ]
    )
    for m in monthly(top_rows):
        lines.append(f"| {m['month']} | {m['n']} | {m['hit_pct']} | {m.get('wins', '')} |")

    # Sample 3y calls (first/last chunks)
    sample = sorted(_clip(top_rows, START_3Y, END), key=lambda x: (x.get("day"), x.get("hm")))
    lines.extend(
        [
            "",
            f"## Sample 3y calls — `{top}` (first 25 + last 25)",
            "",
            "| Day | HM | Side | Win | p |",
            "|---|---|---|---|---:|",
        ]
    )
    show = sample[:25] + (sample[-25:] if len(sample) > 50 else sample[25:])
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

    # Verdict
    top_sc = results[top]["3y"]
    top_ok = results[top]["ok"]
    all_ok = all(results[d]["ok"] for d in DAY_DESKS)
    miss_any = any(results[d]["missing_tags"] for d in DAY_DESKS)
    if top_ok and float(top_sc.get("hit_pct") or 0) >= 99.9 and (top_sc.get("n") or 0) >= 50:
        verdict = (
            f"HOLD OK — `{top}` 3y {top_sc.get('n')}@{top_sc.get('hit_pct')}% · "
            f"floors {'all clear' if all_ok else 'some soft'} · still RESEARCH."
        )
    elif top_ok:
        verdict = (
            f"HOLD PARTIAL — `{top}` clears floor on 3y "
            f"({top_sc.get('n')}@{top_sc.get('hit_pct')}%) but thin or mixed."
        )
    else:
        verdict = f"HOLD FAIL — `{top}` breaks 3y floor under locked recipes."
    if miss_any:
        verdict += " Some locked stream tags missing from remine — check recipe drift."

    elapsed = round(time.time() - t0, 1)
    lines.extend(["", "## Verdict", "", verdict, "", f"Elapsed {elapsed}s", ""])

    # Update recipes research_3y from held rebuild (keep stream tags)
    for desk in DAY_DESKS:
        base_key = BASE_KEY_BY_DESK[desk]
        if base_key in cand:
            cand[base_key]["research_3y"] = {
                "n": results[desk]["3y"].get("n"),
                "hit_pct": results[desk]["3y"].get("hit_pct"),
            }
            cand[base_key]["research_1y"] = {
                "n": results[desk]["1y"].get("n"),
                "hit_pct": results[desk]["1y"].get("hit_pct"),
            }
            cand[base_key]["held_3y_ok"] = results[desk]["ok"]
    recipes["window_3y"] = WINDOW_3Y
    recipes["last_3y_confirm"] = {
        "verdict": verdict,
        "elapsed_s": elapsed,
        "end": END,
    }
    RECIPES.write_text(json.dumps(recipes, indent=2, default=str), encoding="utf-8")

    payload = {
        "status": "RESEARCH",
        "not_live": True,
        "phase": "2g",
        "mode": "hold_confirm_3y",
        "dual_model": "10m_train",
        "window_3y": WINDOW_3Y,
        "window_1y": WINDOW_1Y,
        "results": results,
        "verdict": verdict,
        "elapsed_s": elapsed,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "ACC_PHASE2G_10M_3Y.md"
    js = OUT / "ACC_PHASE2G_10M_3Y.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    # Point PHASE2G_LOGIC at 3y confirm
    logic_md = HOLD / "phase2g" / "PHASE2G_LOGIC.md"
    if logic_md.exists():
        text = logic_md.read_text(encoding="utf-8")
        if "ACC_PHASE2G_10M_3Y" not in text:
            text = text.rstrip() + (
                "\n\n**3y confirm (held recipes):** "
                "`prod_live/tests/builders/research_acc_phase2g_10m_3y.py`  \n"
                "**Report:** `prod_live/reports/3y/ACC_PHASE2G_10M_3Y.md`\n"
            )
            logic_md.write_text(text, encoding="utf-8")

    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
