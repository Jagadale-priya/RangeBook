"""P2G 10m — unique call counts per desk (1y / Oct / Nov).

  python -u prod_live/tests/builders/research_p2g_10m_unique_by_desk.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _champ_floor, _agg  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _side  # noqa: E402
from research_100pct_deeper_more_calls import gap_map  # noqa: E402
from prod_live.logic.accurate_desks import build_all_accurate_desks  # noqa: E402
from prod_live.logic.p2g_10m import BASE_KEY_BY_DESK, DAY_DESKS, HARD_GATES  # noqa: E402
from research_acc_phase2g_10m_1y import (  # noqa: E402
    greedy_expand,
    load_d10,
    mine_streams,
    stamp,
    stream_ok,
    universes_p2g,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
START, END = "2025-11-15", "2026-11-15"
OCT_A, OCT_B = "2026-10-01", "2026-10-31"
NOV_A, NOV_B = "2026-11-01", "2026-11-15"

Key = Tuple[str, str, str]


def keys(rows: List[dict], a: str, b: str) -> Set[Key]:
    return {
        (str(r.get("day") or ""), _side(r), str(r.get("hm") or ""))
        for r in _clip(rows, a, b)
    }


def main() -> int:
    print("P2G 10m unique-by-desk…", flush=True)
    dual = json.loads((LEDGER / "_cache_dual15_dual5_10y.json").read_text(encoding="utf-8"))
    path_u = json.loads((LEDGER / "_cache_path_trusted_10y.json").read_text(encoding="utf-8"))
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
    d10 = load_d10()
    univ = universes_p2g(path_u, d10, champ_native)
    streams_all = mine_streams(univ, gaps, active, floor_min=82.71)

    book: Dict[str, List[dict]] = {}
    for desk in DAY_DESKS:
        floor = HARD_GATES[desk]
        seed = list(phase1.get(BASE_KEY_BY_DESK[desk]) or [])
        usable = [(t, r) for t, r in streams_all if stream_ok(r, floor)]
        rows, _ = greedy_expand(seed, usable, floor)
        book[desk] = stamp(rows, desk)
        print(f"  {desk} done", flush=True)

    windows = {
        "1y": (START, END),
        "oct2026": (OCT_A, OCT_B),
        "nov2026": (NOV_A, NOV_B),
    }

    lines = [
        "# P2G 10m — unique calls per desk",
        "",
        "**Unique key:** `(day, side, hm)`",
        "",
        "| Desk | Floor | 1y unique | 1y hit% | Oct unique | Oct hit% | Nov unique | Nov hit% |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    payload = {"desks": {}, "union": {}}

    running: Set[Key] = set()
    for desk in DAY_DESKS:
        rows = book[desk]
        row = {"floor": HARD_GATES[desk]}
        cells = [f"| `{desk}` | {HARD_GATES[desk]}"]
        for wname, (a, b) in windows.items():
            ks = keys(rows, a, b)
            rs = _clip(rows, a, b)
            st = _agg(rs)
            row[wname] = {
                "unique": len(ks),
                "n": st.get("n"),
                "hit_pct": st.get("hit_pct"),
                "wins": st.get("wins"),
                "losses": st.get("losses"),
            }
            cells.append(f" | {len(ks)} | {st.get('hit_pct')}")
        lines.append("".join(cells) + " |")
        payload["desks"][desk] = row
        running |= keys(rows, START, END)

    # cumulative union as we go down ladder (accuracy-first)
    lines.extend(
        [
            "",
            "## Cumulative unique (accuracy-first ladder)",
            "",
            "| Include through desk | 1y union unique | Oct union | Nov union |",
            "|---|---:|---:|---:|",
        ]
    )
    cum: Set[Key] = set()
    cum_oct: Set[Key] = set()
    cum_nov: Set[Key] = set()
    for desk in DAY_DESKS:
        cum |= keys(book[desk], START, END)
        cum_oct |= keys(book[desk], OCT_A, OCT_B)
        cum_nov |= keys(book[desk], NOV_A, NOV_B)
        lines.append(f"| … `{desk}` | {len(cum)} | {len(cum_oct)} | {len(cum_nov)} |")
        payload["union"][desk] = {
            "1y": len(cum),
            "oct2026": len(cum_oct),
            "nov2026": len(cum_nov),
        }

    lines.extend(
        [
            "",
            f"**Full ladder union 1y:** {len(running)}",
            f"**Full ladder union Oct:** {len(cum_oct)}",
            f"**Full ladder union Nov:** {len(cum_nov)}",
            "",
        ]
    )

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "P2G_10M_UNIQUE_BY_DESK.md"
    js = OUT / "P2G_10M_UNIQUE_BY_DESK.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    for desk in DAY_DESKS:
        d = payload["desks"][desk]
        print(
            f"  {desk}: 1y={d['1y']['unique']} oct={d['oct2026']['unique']} nov={d['nov2026']['unique']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
