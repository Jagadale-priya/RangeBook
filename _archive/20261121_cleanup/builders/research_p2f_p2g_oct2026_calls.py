"""List every Oct 2026 call for P2F (15m) and P2G (10m) day desks.

  python -u prod_live/tests/builders/research_p2f_p2g_oct2026_calls.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

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
from prod_live.logic.p2f_day_live import (  # noqa: E402
    LIVE_DAY_DESKS,
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
OCT_A, OCT_B = "2026-10-01", "2026-10-31"
START_1Y, END_1Y = "2025-11-15", "2026-11-15"


def call_key(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day") or ""), _side(r), str(r.get("hm") or ""))


def desks_for_key(book: Dict[str, List[dict]], desks: List[str], key: Tuple[str, str, str]) -> List[str]:
    hit = []
    for d in desks:
        for r in book.get(d) or []:
            if call_key(r) == key and OCT_A <= str(r.get("day") or "") <= OCT_B:
                hit.append(d)
                break
    return hit


def row_for_key(book: Dict[str, List[dict]], desks: List[str], key: Tuple[str, str, str]) -> dict:
    for d in desks:
        for r in book.get(d) or []:
            if call_key(r) == key and OCT_A <= str(r.get("day") or "") <= OCT_B:
                return r
    return {}


def main() -> int:
    print(f"Oct 2026 calls P2F vs P2G · {OCT_A}→{OCT_B}", flush=True)
    dual = json.loads((LEDGER / "_cache_dual15_dual5_10y.json").read_text(encoding="utf-8"))
    path_u = json.loads((LEDGER / "_cache_path_trusted_10y.json").read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_1Y < d <= END_1Y]
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
    print(f"  P2F rebuild {len(all_tags)} tags…", flush=True)
    by_tag = rebuild_all_tags(all_tags, path_u, gaps, active, dual15, dual5, proven, champ)
    p2f = build_p2f_day_desks(phase1, by_tag)

    print("  P2G rebuild…", flush=True)
    d10 = load_d10()
    univ = universes_p2g(path_u, d10, champ_native)
    streams_all = mine_streams(univ, gaps, active, floor_min=82.71)
    p2g: Dict[str, List[dict]] = {}
    for desk in P2G_DESKS:
        floor = HARD_GATES[desk]
        seed = list(phase1.get(BASE_KEY_BY_DESK[desk]) or [])
        usable = [(t, r) for t, r in streams_all if stream_ok(r, floor)]
        rows, _ = greedy_expand(seed, usable, floor)
        p2g[desk] = stamp(rows, desk)

    # Collect unique Oct keys per book (all day desks)
    p2f_keys = set()
    p2g_keys = set()
    for d in LIVE_DAY_DESKS:
        for r in _clip(p2f.get(d) or [], OCT_A, OCT_B):
            p2f_keys.add(call_key(r))
    for d in P2G_DESKS:
        for r in _clip(p2g.get(d) or [], OCT_A, OCT_B):
            p2g_keys.add(call_key(r))

    all_keys = sorted(p2f_keys | p2g_keys)

    lines = [
        "# October 2026 — every call · P2F (15m) vs P2G (10m)",
        "",
        f"**Month:** `{OCT_A}` → `{OCT_B}`",
        "**Unique key:** `(day, side, hm)` · desks = full day ladder each book",
        "",
        f"| Book | Unique Oct calls |",
        f"|---|---:|",
        f"| P2F 15m (all day desks) | **{len(p2f_keys)}** |",
        f"| P2G 10m (all day desks) | **{len(p2g_keys)}** |",
        f"| Union | **{len(all_keys)}** |",
        f"| Both | {len(p2f_keys & p2g_keys)} |",
        f"| Only P2F | {len(p2f_keys - p2g_keys)} |",
        f"| Only P2G | {len(p2g_keys - p2f_keys)} |",
        "",
        "## All October calls (combined calendar)",
        "",
        "| Day | HM | Side | Win | In P2F | In P2G | P2F desks (highest first) | P2G desks (highest first) | p_t1 |",
        "|---|---|---|---|---|---|---|---|---:|",
    ]

    rows_out = []
    for key in all_keys:
        day, side, hm = key
        in_f = key in p2f_keys
        in_g = key in p2g_keys
        fd = desks_for_key(p2f, LIVE_DAY_DESKS, key)
        gd = desks_for_key(p2g, P2G_DESKS, key)
        src = row_for_key(p2f, LIVE_DAY_DESKS, key) or row_for_key(p2g, P2G_DESKS, key)
        win = src.get("win")
        w = "W" if win else ("L" if win is False else "?")
        p = src.get("p_t1")
        lines.append(
            f"| {day} | {hm} | {side} | {w} | "
            f"{'Y' if in_f else ''} | {'Y' if in_g else ''} | "
            f"{', '.join(fd) or '—'} | {', '.join(gd) or '—'} | {p if p is not None else ''} |"
        )
        rows_out.append(
            {
                "day": day,
                "hm": hm,
                "side": side,
                "win": win,
                "in_p2f": in_f,
                "in_p2g": in_g,
                "p2f_desks": fd,
                "p2g_desks": gd,
                "p_t1": p,
            }
        )

    # Separate full lists per book (every desk row, may repeat same key across desks — show primary per unique)
    def book_section(title: str, book: Dict[str, List[dict]], desks: List[str], uniq: set) -> List[str]:
        out = ["", f"## {title}", "", "| # | Day | HM | Side | Win | Highest desk | All desks | p_t1 |", "|---:|---|---|---|---|---|---|---:|"]
        for i, key in enumerate(sorted(uniq), 1):
            day, side, hm = key
            ds = desks_for_key(book, desks, key)
            r = row_for_key(book, desks, key)
            w = "W" if r.get("win") else ("L" if r.get("win") is False else "?")
            out.append(
                f"| {i} | {day} | {hm} | {side} | {w} | `{ds[0] if ds else ''}` | "
                f"{', '.join(ds)} | {r.get('p_t1') if r.get('p_t1') is not None else ''} |"
            )
        # hit
        wins = sum(1 for k in uniq if (row_for_key(book, desks, k) or {}).get("win"))
        n = len(uniq)
        hit = round(100.0 * wins / n, 2) if n else None
        out.extend(["", f"**N={n}** · hit **{hit}%** ({wins}W / {n - wins}L)", ""])
        return out

    lines.extend(book_section("P2F 15m — October calls (unique)", p2f, LIVE_DAY_DESKS, p2f_keys))
    lines.extend(book_section("P2G 10m — October calls (unique)", p2g, P2G_DESKS, p2g_keys))

    # Top-100% desk only lists
    def top_section(title: str, rows: List[dict]) -> List[str]:
        rs = sorted(_clip(rows, OCT_A, OCT_B), key=lambda x: (x.get("day"), x.get("hm")))
        out = ["", f"## {title}", "", "| # | Day | HM | Side | Win | p_t1 |", "|---:|---|---|---|---|---:|"]
        for i, r in enumerate(rs, 1):
            w = "W" if r.get("win") else "L"
            out.append(
                f"| {i} | {r.get('day')} | {r.get('hm')} | {_side(r)} | {w} | {r.get('p_t1')} |"
            )
        st = _agg(rs)
        out.extend(["", f"**N={st.get('n')}** · hit **{st.get('hit_pct')}%**", ""])
        return out

    lines.extend(
        top_section(
            "P2F top only — `ACC100_MULTI_V11`",
            p2f.get("ACC100_MULTI_V11") or [],
        )
    )
    lines.extend(
        top_section(
            "P2G top only — `ACC100_MULTI_V12_P2G_10M`",
            p2g.get("ACC100_MULTI_V12_P2G_10M") or [],
        )
    )

    payload = {
        "month": {"start": OCT_A, "end": OCT_B},
        "counts": {
            "p2f_all": len(p2f_keys),
            "p2g_all": len(p2g_keys),
            "union": len(all_keys),
            "both": len(p2f_keys & p2g_keys),
            "only_p2f": len(p2f_keys - p2g_keys),
            "only_p2g": len(p2g_keys - p2f_keys),
            "p2f_v11": len(_clip(p2f.get("ACC100_MULTI_V11") or [], OCT_A, OCT_B)),
            "p2g_v12": len(_clip(p2g.get("ACC100_MULTI_V12_P2G_10M") or [], OCT_A, OCT_B)),
        },
        "calls": rows_out,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "P2F_P2G_OCT2026_CALLS.md"
    js = OUT / "P2F_P2G_OCT2026_CALLS.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    print(
        f"Oct P2F={len(p2f_keys)} P2G={len(p2g_keys)} union={len(all_keys)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
