"""Confirm FINAL NIFTY F&O = P2F + P2G 10m + CHAMP_PLUS only.

Validates each book against locked golden reports (exact N + hit%),
then combines with collapse UI and asserts **zero blocked** distinct keys.

  python -u prod_live/tests/confirm_final_nifty_3books.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
BUILDERS = Path(__file__).resolve().parent / "builders"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "prod_live"))
import path_setup  # noqa: F401,E402

from accuracy_max_6m import _agg, _champ_floor  # noqa: E402
from research_100pct_deeper_more_calls import gap_map, union_unique_days  # noqa: E402
from research_confirm_dual_tf_deep import _clip  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
from prod_live.logic.accurate_desks import build_all_accurate_desks  # noqa: E402
from prod_live.logic.combined_live_book import (  # noqa: E402
    call_key,
    combine_live_rows,
    final_book_registry,
)
from prod_live.logic.champ_plus_live import (  # noqa: E402
    DESK as CHAMP_DESK,
    EXPECTED as CHAMP_EXP,
    WINDOW_1Y as CHAMP_1Y,
    WINDOW_3Y as CHAMP_3Y,
    WINDOW_5Y as CHAMP_5Y,
    load_held_calls,
)
from prod_live.logic.p2f_day_live import (  # noqa: E402
    EXPECTED_1Y as P2F_DAY_EXP,
    LIVE_DAY_DESKS,
    WINDOW_1Y as P2F_1Y,
    build_p2f_day_desks,
    load_phase2f_day_recipes,
)
from prod_live.logic.p2f_cap2_live import (  # noqa: E402
    EXPECTED_1Y as P2F_CAP2_EXP,
    LIVE_CAP2_DESKS,
    build_p2f_cap2_desks,
)
from prod_live.logic.p2g_10m import (  # noqa: E402
    BASE_KEY_BY_DESK,
    HARD_GATES,
    WINDOW_1Y as P2G_1Y,
    WINDOW_3Y as P2G_3Y,
    WINDOW_5Y as P2G_5Y,
)
from prod_live.logic.p2g_10m_live import (  # noqa: E402
    EXPECTED_1Y as P2G_EXP_1Y,
    EXPECTED_3Y as P2G_EXP_3Y,
    EXPECTED_5Y as P2G_EXP_5Y,
    LIVE_P2G_DESKS,
    load_phase2g_recipes,
    stamp_live as stamp_p2g,
)
from research_acc_phase2g_10m_1y import (  # noqa: E402
    desk_ok,
    load_d10,
    mine_streams,
    universes_p2g,
)
from prod_live.holding_accurate.rebuild_streams import rebuild_all_tags  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y" / "FINAL_NIFTY_3BOOKS_CONFIRM.md"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"
REP_P2G = ROOT / "prod_live" / "reports" / "5y" / "ACC_PHASE2G_10M_5Y.json"
REP_CHAMP = ROOT / "prod_live" / "reports" / "5y" / "CHAMPION_PLUS_T30_SL30_5Y.json"


def _hit(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 2)


def clip_incl(rows: List[dict], a: str, b: str) -> List[dict]:
    """Inclusive [a,b] — CHAMP windows are closed on start day."""
    return [r for r in rows if a <= str(r.get("day") or "") <= b]


def _match(label: str, got_n: int, got_hit: float, exp_n: int, exp_hit: float, tol: float = 0.02) -> Tuple[bool, str]:
    ok_n = got_n == int(exp_n)
    ok_h = abs(float(got_hit) - float(exp_hit)) <= tol
    ok = ok_n and ok_h
    return ok, (
        f"{'PASS' if ok else 'FAIL'} {label}: got {got_n}@{got_hit}% · "
        f"exp {exp_n}@{exp_hit}%"
    )


def rebuild_held_p2g(seed, tags, by_tag, floor):
    cur = list(seed)
    if not desk_ok(cur, floor):
        cur = []
    for tag in tags:
        rows = by_tag.get(tag)
        if rows:
            cur = union_unique_days(cur, rows)
    return cur


def main() -> int:
    t0 = time.time()
    lines = [
        "# FINAL NIFTY F&O — 3-book confirm",
        "",
        "**Books only:** P2F (day+cap2) · P2G 10m · CHAMP_PLUS_T30SL30_CAP4",
        "**Excluded:** `STACK_PLUS_CROWN_HTF_CAP2` · `AGREE_15M_ANY5`",
        "**UI:** same `(day,side,hm)` → 1 call · all tags · accuracy-first · never block",
        "",
    ]
    fails: List[str] = []
    passes: List[str] = []

    # ---- 1) CHAMP_PLUS frozen book ----
    print("1) CHAMP_PLUS…", flush=True)
    champ = load_held_calls()
    for name, win, exp in (
        ("champ_1y", CHAMP_1Y, CHAMP_EXP["1y"]),
        ("champ_3y", CHAMP_3Y, CHAMP_EXP["3y"]),
        ("champ_5y", CHAMP_5Y, CHAMP_EXP["5y"]),
    ):
        rows = clip_incl(champ, win["start"], win["end"])
        ok, msg = _match(name, len(rows), _hit(rows), int(exp["n"]), float(exp["hit_pct"]))
        (passes if ok else fails).append(msg)
        print(f"  {msg}", flush=True)
    # cross-check report JSON
    crep = json.loads(REP_CHAMP.read_text(encoding="utf-8"))
    for k in ("1y", "3y", "5y"):
        b = (crep.get("book") or {}).get(k) or {}
        ok, msg = _match(
            f"champ_report_{k}",
            int(b.get("n") or 0),
            float(b.get("hit_pct") or 0),
            int(CHAMP_EXP[k]["n"]),
            float(CHAMP_EXP[k]["hit_pct"]),
        )
        (passes if ok else fails).append(msg)

    # ---- 2) P2G expected constants vs report ----
    print("2) P2G report constants…", flush=True)
    grep = json.loads(REP_P2G.read_text(encoding="utf-8"))
    for desk in LIVE_P2G_DESKS:
        block = (grep.get("results") or {}).get(desk) or {}
        for win_name, exp_map in (
            ("1y", P2G_EXP_1Y),
            ("3y", P2G_EXP_3Y),
            ("5y", P2G_EXP_5Y),
        ):
            st = block.get(win_name) or {}
            ok, msg = _match(
                f"p2g_report_{desk}_{win_name}",
                int(st.get("n") or 0),
                float(st.get("hit_pct") or 0),
                int(exp_map[desk]["n"]),
                float(exp_map[desk]["hit_pct"]),
            )
            (passes if ok else fails).append(msg)

    # ---- 3) Rebuild P2G held + match 5y ----
    print("3) P2G rebuild held…", flush=True)
    dual = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(5000)
    sess = [d for d in sessions_all if P2G_5Y["start"] < d <= P2G_5Y["end"]]
    active = fs._active_days(sess, fs._load_daily()) if sess else set()
    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ_rows = _champ_floor([dict(r, track="champion") for r in dual["dual15"]["champion"]])
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]
    champ_native = path_u.get("champ_native") or champ_rows
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
    d10 = load_d10()
    univ = universes_p2g(path_u, d10, champ_native)
    streams_all = mine_streams(univ, gaps, active, floor_min=82.71)
    by_tag_p2g = {t: rows for t, rows in streams_all}
    recipes_g = load_phase2g_recipes()
    p2g_books: Dict[str, List[dict]] = {}
    for desk in LIVE_P2G_DESKS:
        floor = HARD_GATES[desk]
        meta = recipes_g.get(desk) or {}
        tags = list(meta.get("stream_tags_research") or [])
        seed = list(phase1.get(BASE_KEY_BY_DESK[desk]) or [])
        rows = rebuild_held_p2g(seed, tags, by_tag_p2g, floor)
        rows = stamp_p2g(rows, desk)
        p2g_books[desk] = rows
        for win_name, win, exp_map in (
            ("1y", P2G_1Y, P2G_EXP_1Y),
            ("3y", P2G_3Y, P2G_EXP_3Y),
            ("5y", P2G_5Y, P2G_EXP_5Y),
        ):
            rs = _clip(rows, win["start"], win["end"])
            ok, msg = _match(
                f"p2g_rebuild_{desk}_{win_name}",
                len(rs),
                _hit(rs),
                int(exp_map[desk]["n"]),
                float(exp_map[desk]["hit_pct"]),
            )
            (passes if ok else fails).append(msg)
            print(f"  {msg}", flush=True)

    # ---- 4) P2F day + cap2 rebuild (1y HTF window — match locked confirm) ----
    print("4) P2F rebuild…", flush=True)
    sess_1y = [d for d in sessions_all if P2F_1Y["start"] < d <= P2F_1Y["end"]]
    active_1y = fs._active_days(sess_1y, fs._load_daily()) if sess_1y else set()
    phase1_1y = build_all_accurate_desks(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=path_u.get("crown_by_risk") or {},
        good_by_risk=path_u.get("good_by_risk") or {},
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active_1y,
    )
    recipes_f = load_phase2f_day_recipes()
    all_tags: List[str] = []
    seen = set()
    for desk in LIVE_DAY_DESKS:
        for t in (recipes_f.get(desk) or {}).get("stream_tags_research") or []:
            if t not in seen:
                seen.add(t)
                all_tags.append(t)
    from prod_live.logic.p2f_cap2_live import load_phase2f_cap2_recipes  # noqa: E402

    recipes_c = load_phase2f_cap2_recipes()
    for desk in LIVE_CAP2_DESKS:
        for t in (recipes_c.get(desk) or {}).get("stream_tags_research") or []:
            if t not in seen:
                seen.add(t)
                all_tags.append(t)
    by_tag = rebuild_all_tags(
        all_tags, path_u, gaps, active_1y, dual15, dual5, proven, champ_rows
    )
    p2f_day = build_p2f_day_desks(phase1_1y, by_tag)
    p2f_cap2 = build_p2f_cap2_desks(phase1_1y, by_tag)
    for desk in LIVE_DAY_DESKS:
        rs = _clip(p2f_day.get(desk) or [], P2F_1Y["start"], P2F_1Y["end"])
        exp = P2F_DAY_EXP[desk]
        ok, msg = _match(
            f"p2f_day_{desk}",
            len(rs),
            _hit(rs),
            int(exp["n"]),
            float(exp["hit_pct"]),
            tol=0.05,
        )
        (passes if ok else fails).append(msg)
        print(f"  {msg}", flush=True)
    for desk in LIVE_CAP2_DESKS:
        rs = _clip(p2f_cap2.get(desk) or [], P2F_1Y["start"], P2F_1Y["end"])
        exp = P2F_CAP2_EXP[desk]
        ok, msg = _match(
            f"p2f_cap2_{desk}",
            len(rs),
            _hit(rs),
            int(exp["n"]),
            float(exp["hit_pct"]),
            tol=0.05,
        )
        (passes if ok else fails).append(msg)
        print(f"  {msg}", flush=True)

    # ---- 5) Combine — never block ----
    print("5) Combine UI…", flush=True)
    combined = combine_live_rows(
        p2f_day=p2f_day,
        p2f_cap2=p2f_cap2,
        p2g_10m=p2g_books,
        champ_plus=champ,
    )
    blocked = int(combined.get("blocked_distinct") or 0)
    if blocked == 0:
        passes.append(f"PASS combine_blocked_distinct=0 · ui={combined['n_ui']} raw={combined['n_raw']} multi={combined['n_multi_desk']}")
    else:
        fails.append(f"FAIL combine_blocked_distinct={blocked}")

    raw_keys = {call_key(r) for r in combined["raw_rows"] if all(call_key(r))}
    ui_keys = {call_key(r) for r in combined["ui_rows"]}
    if raw_keys <= ui_keys or raw_keys == ui_keys or len(raw_keys - ui_keys) == 0:
        passes.append("PASS every distinct raw key appears in UI")
    else:
        fails.append(f"FAIL missing UI keys={len(raw_keys - ui_keys)}")

    # no legacy volume tags as primary
    bad = [
        r
        for r in combined["ui_rows"]
        if r.get("accurate_tag") in ("STACK_PLUS_CROWN_HTF_CAP2", "AGREE_15M_ANY5")
    ]
    if not bad:
        passes.append("PASS no volume/agree primary tags")
    else:
        fails.append(f"FAIL legacy primary tags n={len(bad)}")

    elapsed = round(time.time() - t0, 1)
    verdict = "PASS" if not fails else "FAIL"
    lines.extend(
        [
            f"## Verdict: **{verdict}**",
            "",
            f"Passes: {len(passes)} · Fails: {len(fails)} · Elapsed {elapsed}s",
            "",
            "## Registry",
            "",
            "```json",
            json.dumps(final_book_registry(), indent=2),
            "```",
            "",
            "## Passes",
            "",
        ]
    )
    lines.extend(f"- {m}" for m in passes)
    lines.extend(["", "## Fails", ""])
    if fails:
        lines.extend(f"- {m}" for m in fails)
    else:
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "## Combine",
            "",
            f"| Metric | Value |",
            f"|---|---:|",
            f"| raw firings | {combined['n_raw']} |",
            f"| UI calls | {combined['n_ui']} |",
            f"| multi-desk UI | {combined['n_multi_desk']} |",
            f"| blocked_distinct | {combined['blocked_distinct']} |",
            "",
        ]
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}", flush=True)
    print(f"VERDICT {verdict} · fails={len(fails)}", flush=True)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
