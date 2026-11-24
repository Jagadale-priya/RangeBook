"""Compare P2F (15m dual) vs P2G_10m unique calls · 1y + Nov 2026.

  python -u prod_live/tests/builders/research_compare_p2f_p2g_unique_nov.py
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
from accuracy_max_6m import _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _side  # noqa: E402
from research_100pct_deeper_more_calls import gap_map  # noqa: E402
from prod_live.logic.accurate_desks import build_all_accurate_desks  # noqa: E402
from prod_live.logic.p2f_day_live import (  # noqa: E402
    LIVE_DAY_DESKS,
    WINDOW_1Y,
    build_p2f_day_desks,
    load_phase2f_day_recipes,
)
from prod_live.holding_accurate.rebuild_streams import rebuild_all_tags  # noqa: E402
from prod_live.logic.p2g_10m import (  # noqa: E402
    BASE_KEY_BY_DESK,
    DAY_DESKS as P2G_DESKS,
    HARD_GATES,
)
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
START, END = WINDOW_1Y["start"], WINDOW_1Y["end"]
NOV_A, NOV_B = "2026-11-01", "2026-11-15"

Key = Tuple[str, str, str]


def keys(rows: List[dict], a: str, b: str) -> Set[Key]:
    return {
        (str(r.get("day") or ""), _side(r), str(r.get("hm") or ""))
        for r in _clip(rows, a, b)
    }


def union_keys(desks: List[str], book: Dict[str, List[dict]], a: str, b: str) -> Set[Key]:
    u: Set[Key] = set()
    for d in desks:
        u |= keys(book.get(d) or [], a, b)
    return u


def fmt_keys(ks: Set[Key]) -> List[str]:
    return [f"{d} {hm} {s}" for d, s, hm in sorted(ks)]


def main() -> int:
    print(f"Compare P2F vs P2G unique · 1y {START}→{END} · Nov {NOV_A}→{NOV_B}", flush=True)
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

    recipes = load_phase2f_day_recipes()
    all_tags: List[str] = []
    seen = set()
    for desk in LIVE_DAY_DESKS:
        for t in (recipes.get(desk) or {}).get("stream_tags_research") or []:
            if t not in seen:
                seen.add(t)
                all_tags.append(t)
    print(f"  rebuild P2F tags={len(all_tags)}…", flush=True)
    by_tag = rebuild_all_tags(all_tags, path_u, gaps, active, dual15, dual5, proven, champ)
    p2f = build_p2f_day_desks(phase1, by_tag)

    print("  rebuild P2G…", flush=True)
    d10 = load_d10()
    univ = universes_p2g(path_u, d10, champ_native)
    streams_all = mine_streams(univ, gaps, active, floor_min=82.71)
    p2g: Dict[str, List[dict]] = {}
    for desk in P2G_DESKS:
        floor = HARD_GATES[desk]
        seed = list(phase1.get(BASE_KEY_BY_DESK[desk]) or [])
        usable = [(t, r) for t, r in streams_all if stream_ok(r, floor)]
        rows, _tags = greedy_expand(seed, usable, floor)
        p2g[desk] = stamp(rows, desk)
        print(f"    {desk} 1y n={len(_clip(rows, START, END))}", flush=True)

    p2f100 = keys(p2f.get("ACC100_MULTI_V11") or [], START, END)
    p2g100 = keys(p2g.get("ACC100_MULTI_V12_P2G_10M") or [], START, END)
    p2f_all = union_keys(LIVE_DAY_DESKS, p2f, START, END)
    p2g_all = union_keys(P2G_DESKS, p2g, START, END)

    p2f100_nov = keys(p2f.get("ACC100_MULTI_V11") or [], NOV_A, NOV_B)
    p2g100_nov = keys(p2g.get("ACC100_MULTI_V12_P2G_10M") or [], NOV_A, NOV_B)
    p2f_all_nov = union_keys(LIVE_DAY_DESKS, p2f, NOV_A, NOV_B)
    p2g_all_nov = union_keys(P2G_DESKS, p2g, NOV_A, NOV_B)

    # per-desk Nov counts
    nov_desk_rows = []
    for d in LIVE_DAY_DESKS:
        ks = keys(p2f.get(d) or [], NOV_A, NOV_B)
        nov_desk_rows.append(f"| P2F `{d}` | {len(ks)} | {', '.join(fmt_keys(ks)) or '—'} |")
    for d in P2G_DESKS:
        ks = keys(p2g.get(d) or [], NOV_A, NOV_B)
        nov_desk_rows.append(f"| P2G `{d}` | {len(ks)} | {', '.join(fmt_keys(ks)) or '—'} |")

    lines = [
        "# P2F (15m dual) vs P2G (10m dual) — unique calls",
        "",
        f"**1y window:** `{START}` → `{END}`",
        f"**Nov window:** `{NOV_A}` → `{NOV_B}` (month-to-date)",
        "**Unique key:** `(day, side, hm)`",
        "",
        "## 1y unique calls",
        "",
        "| Book | Unique N | Overlap | Only this book |",
        "|---|---:|---:|---:|",
        f"| P2F top `ACC100_MULTI_V11` (15m) | {len(p2f100)} | {len(p2f100 & p2g100)} | {len(p2f100 - p2g100)} |",
        f"| P2G top `ACC100_MULTI_V12_P2G_10M` (10m) | {len(p2g100)} | {len(p2f100 & p2g100)} | {len(p2g100 - p2f100)} |",
        f"| P2F **all day desks** union | {len(p2f_all)} | {len(p2f_all & p2g_all)} | {len(p2f_all - p2g_all)} |",
        f"| P2G **all day desks** union | {len(p2g_all)} | {len(p2f_all & p2g_all)} | {len(p2g_all - p2f_all)} |",
        "",
        "## November 2026 unique calls",
        "",
        "| Book | Unique N | Calls |",
        "|---|---:|---|",
        f"| P2F top V11 | {len(p2f100_nov)} | {', '.join(fmt_keys(p2f100_nov)) or '—'} |",
        f"| P2G top V12 | {len(p2g100_nov)} | {', '.join(fmt_keys(p2g100_nov)) or '—'} |",
        f"| P2F all desks union | {len(p2f_all_nov)} | {', '.join(fmt_keys(p2f_all_nov)) or '—'} |",
        f"| P2G all desks union | {len(p2g_all_nov)} | {', '.join(fmt_keys(p2g_all_nov)) or '—'} |",
        "",
        "### Nov overlap / only",
        "",
        f"- Overlap 100% tops: {', '.join(fmt_keys(p2f100_nov & p2g100_nov)) or '—'}",
        f"- Only P2F 100%: {', '.join(fmt_keys(p2f100_nov - p2g100_nov)) or '—'}",
        f"- Only P2G 100%: {', '.join(fmt_keys(p2g100_nov - p2f100_nov)) or '—'}",
        f"- Overlap all-desks: {', '.join(fmt_keys(p2f_all_nov & p2g_all_nov)) or '—'}",
        f"- Only P2F all: {', '.join(fmt_keys(p2f_all_nov - p2g_all_nov)) or '—'}",
        f"- Only P2G all: {', '.join(fmt_keys(p2g_all_nov - p2f_all_nov)) or '—'}",
        "",
        "### Nov by desk",
        "",
        "| Desk | N | Calls |",
        "|---|---:|---|",
        *nov_desk_rows,
        "",
    ]

    payload = {
        "window_1y": {"start": START, "end": END},
        "nov": {"start": NOV_A, "end": NOV_B},
        "y1": {
            "p2f_v11": len(p2f100),
            "p2g_v12": len(p2g100),
            "overlap_100": len(p2f100 & p2g100),
            "only_p2f_100": len(p2f100 - p2g100),
            "only_p2g_100": len(p2g100 - p2f100),
            "p2f_all": len(p2f_all),
            "p2g_all": len(p2g_all),
            "overlap_all": len(p2f_all & p2g_all),
            "only_p2f_all": len(p2f_all - p2g_all),
            "only_p2g_all": len(p2g_all - p2f_all),
        },
        "nov_counts": {
            "p2f_v11": len(p2f100_nov),
            "p2g_v12": len(p2g100_nov),
            "p2f_all": len(p2f_all_nov),
            "p2g_all": len(p2g_all_nov),
            "p2f_v11_calls": fmt_keys(p2f100_nov),
            "p2g_v12_calls": fmt_keys(p2g100_nov),
            "p2f_all_calls": fmt_keys(p2f_all_nov),
            "p2g_all_calls": fmt_keys(p2g_all_nov),
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "COMPARE_P2F_P2G_UNIQUE_NOV.md"
    js = OUT / "COMPARE_P2F_P2G_UNIQUE_NOV.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    print(
        f"1y V11={len(p2f100)} V12={len(p2g100)} | "
        f"Nov V11={len(p2f100_nov)} V12={len(p2g100_nov)} "
        f"allF={len(p2f_all_nov)} allG={len(p2g_all_nov)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
