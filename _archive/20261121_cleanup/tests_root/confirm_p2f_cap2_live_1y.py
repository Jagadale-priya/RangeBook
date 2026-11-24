"""Confirm promoted P2F Cap2 LIVE desks match locked 1y numbers.

Window: 2025-11-15 → 2026-11-15
Does NOT change STACK_PLUS_CROWN_HTF_CAP2 golden.

  python -u prod_live/tests/confirm_p2f_cap2_live_1y.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
BUILDERS = Path(__file__).resolve().parent / "builders"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "prod_live"))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip  # noqa: E402
from research_100pct_deeper_more_calls import gap_map  # noqa: E402
from prod_live.logic.accurate_desks import build_all_accurate_desks  # noqa: E402
from prod_live.logic.p2f_cap2_live import (  # noqa: E402
    EXPECTED_1Y,
    LIVE_CAP2_DESKS,
    LIVE_HIT_FLOOR_1Y,
    WINDOW_1Y,
    build_p2f_cap2_desks,
    load_phase2f_cap2_recipes,
)
from prod_live.holding_accurate.rebuild_streams import rebuild_all_tags  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"

START = WINDOW_1Y["start"]
END = WINDOW_1Y["end"]


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 2)


def _near(a, b, tol=0.05):
    return abs(float(a) - float(b)) <= tol


def main() -> int:
    t0 = time.time()
    print(f"CONFIRM P2F Cap2 LIVE 1y {START} → {END}", flush=True)

    dual = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START < d <= END]
    active = fs._active_days(sess, fs._load_daily()) if sess else set()

    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ = _champ_floor([dict(r, track="champion") for r in dual["dual15"]["champion"]])
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]
    champ_native = path_u.get("champ_native") or champ

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

    recipes = load_phase2f_cap2_recipes()
    all_tags: List[str] = []
    seen = set()
    for desk in LIVE_CAP2_DESKS:
        for t in (recipes.get(desk) or {}).get("stream_tags_research") or []:
            if t not in seen:
                seen.add(t)
                all_tags.append(t)

    print(f"  rebuild {len(all_tags)} stream tags…", flush=True)
    by_tag = rebuild_all_tags(
        all_tags, path_u, gaps, active, dual15, dual5, proven, champ
    )
    desks = build_p2f_cap2_desks(phase1, by_tag)

    rows_out: Dict[str, Any] = {}
    fails: List[str] = []
    lines = [
        "# P2F Cap2 LIVE — 1y confirm",
        "",
        f"**Window:** `{START}` → `{END}`",
        f"**Mode:** Cap2 ≤2 same-side/day · **Lane:** LIVE",
        f"**Hard gates:** Phase-2F floors kept · soft live bar 1y hit > {LIVE_HIT_FLOOR_1Y}%",
        "",
        "| Desk | Expected N @ hit | Got N @ hit | Soft>87% | Gate |",
        "|---|---|---|---|---|",
    ]

    for desk in LIVE_CAP2_DESKS:
        rs = _clip(desks.get(desk) or [], START, END)
        n = len(rs)
        hp = hit_pct(rs)
        exp = EXPECTED_1Y[desk]
        n_ok = n == int(exp["n"])
        h_ok = _near(hp, exp["hit_pct"], tol=0.05)
        soft_ok = hp > LIVE_HIT_FLOOR_1Y
        gate = "PASS" if (n_ok and h_ok and soft_ok) else "FAIL"
        if gate != "PASS":
            fails.append(
                f"{desk}: got {n}@{hp} expected {exp['n']}@{exp['hit_pct']} soft_ok={soft_ok}"
            )
        rows_out[desk] = {
            "n": n,
            "hit_pct": hp,
            "expected": exp,
            "soft_gt_87": soft_ok,
            "gate": gate,
            "lane": "LIVE",
            "mode": "cap2",
        }
        lines.append(
            f"| `{desk}` | {int(exp['n'])} @ {exp['hit_pct']}% | {n} @ {hp}% | "
            f"{'YES' if soft_ok else 'NO'} | **{gate}** |"
        )

    overall = "PASS" if not fails else "FAIL"
    lines.extend(
        [
            "",
            f"**Overall:** **{overall}**",
            f"Elapsed {time.time() - t0:.1f}s",
            "",
            "Volume golden separate — `confirm_final_hold_1y_match.py`.",
            "Day desks — `confirm_p2f_day_live_1y.py`.",
        ]
    )

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "P2F_CAP2_LIVE_1Y_CONFIRM.md"
    js = OUT / "P2F_CAP2_LIVE_1Y_CONFIRM.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(
        json.dumps(
            {"window": WINDOW_1Y, "overall": overall, "desks": rows_out, "fails": fails},
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\n".join(lines), flush=True)
    print(f"Wrote {md}", flush=True)
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
