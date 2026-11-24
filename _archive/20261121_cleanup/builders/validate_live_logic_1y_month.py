"""Replay current LIVE NIFTY logic for last 1y + current month.

Live Calls board (today):
  SUPPRESS_DUAL_LIST=1 → dual proven/champion does NOT list
  CHAMP_PLUS T30SL30 Cap4 (+ crown fill) lists when board empty
  P2F / P2G annotate + UI combine (FINAL 3 books)

Uses the same loaders / rebuild / combine code as live & confirm_final.

  python -u prod_live/tests/builders/validate_live_logic_1y_month.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "prod_live"))
os.environ.setdefault("SUPPRESS_DUAL_LIST", "1")
os.environ.setdefault("USE_DUAL_TRACK", "1")
os.environ.setdefault("ENABLE_EXTRA_TREES_SINGLE", "0")
os.environ.setdefault("ENABLE_PRE_DUAL_SINGLE", "0")
os.environ.setdefault("ENABLE_STACKED_CALLS", "0")
import path_setup  # noqa: F401,E402

from accuracy_max_6m import _champ_floor  # noqa: E402
from research_100pct_deeper_more_calls import gap_map, union_unique_days  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _side  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
from prod_live.logic.accurate_desks import build_all_accurate_desks  # noqa: E402
from prod_live.logic.combined_live_book import call_key, combine_live_rows  # noqa: E402
from prod_live.logic.champ_plus_live import (  # noqa: E402
    ACCURACY_TAG as CHAMP_ACC,
    DESK as CHAMP_DESK,
    EXPECTED as CHAMP_EXP,
    WINDOW_1Y as CHAMP_1Y,
    load_held_calls,
    load_live_book,
    stamp_live,
)
from prod_live.logic import champ_plus_engine as eng  # noqa: E402
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
    load_phase2f_cap2_recipes,
)
from prod_live.logic.p2g_10m import (  # noqa: E402
    BASE_KEY_BY_DESK,
    HARD_GATES,
    WINDOW_5Y,
)
from prod_live.logic.p2g_10m_live import (  # noqa: E402
    LIVE_P2G_DESKS,
    load_phase2g_recipes,
    stamp_live as stamp_p2g,
)
from research_acc_phase2g_10m_1y import desk_ok, load_d10, mine_streams, universes_p2g  # noqa: E402
from prod_live.holding_accurate.rebuild_streams import rebuild_all_tags  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "NIFTY_LIVE_LOGIC_1Y_AND_MONTH.md"
OUT_JSON = OUT / "NIFTY_LIVE_LOGIC_1Y_AND_MONTH.json"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"

# Locked CHAMP 1y window (same as live expected snapshot)
WIN_1Y_START = CHAMP_1Y["start"]
WIN_1Y_END = CHAMP_1Y["end"]
# Current month to available data
MONTH_START = "2026-11-01"


def clip_incl(rows: List[dict], a: str, b: str) -> List[dict]:
    return [r for r in rows if a <= str(r.get("day") or "")[:10] <= b]


def hit(rows: List[dict]) -> float:
    known = [r for r in rows if r.get("win") is not None]
    if not known:
        return 0.0
    return round(100.0 * sum(1 for r in known if r.get("win")) / len(known), 2)


def net_pts(rows: List[dict]) -> float:
    s = 0.0
    for r in rows:
        try:
            s += float(r.get("points") or 0)
        except Exception:
            pass
    return round(s, 1)


def stats(rows: List[dict]) -> Dict[str, Any]:
    known = [r for r in rows if r.get("win") is not None]
    wins = sum(1 for r in known if r.get("win"))
    tracks: Dict[str, int] = defaultdict(int)
    for r in rows:
        tracks[str(r.get("track") or r.get("accurate_tag") or "?")] += 1
    return {
        "n": len(rows),
        "settled": len(known),
        "wins": wins,
        "losses": len(known) - wins,
        "hit_pct": hit(rows),
        "net_pts": net_pts(rows),
        "tracks": dict(sorted(tracks.items(), key=lambda kv: -kv[1])),
    }


def rebuild_held_p2g(seed, tags, by_tag, floor):
    cur = list(seed)
    if not desk_ok(cur, floor):
        cur = []
    for tag in tags:
        rows = by_tag.get(tag)
        if rows:
            cur = union_unique_days(cur, rows)
    return cur


def month_rollup(rows: List[dict]) -> Dict[str, Dict[str, Any]]:
    by_m: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by_m[str(r.get("day") or "")[:7]].append(r)
    return {m: stats(rs) for m, rs in sorted(by_m.items())}


def desk_table(title: str, book: Dict[str, List[dict]]) -> List[str]:
    lines = [f"### {title}", "", "| Desk | N | Hit% |", "|---|---:|---:|"]
    for d, rs in book.items():
        lines.append(f"| `{d}` | {len(rs)} | {hit(rs)} |")
    lines.append("")
    return lines


def main() -> int:
    t0 = time.time()
    print("NIFTY LIVE logic · 1y + current month", flush=True)
    print(
        f"  flags: SUPPRESS_DUAL_LIST={os.environ.get('SUPPRESS_DUAL_LIST')} "
        f"USE_DUAL_TRACK={os.environ.get('USE_DUAL_TRACK')}",
        flush=True,
    )

    # Data end from live book
    champ_all = load_live_book()
    data_end = max((str(r.get("day") or "")[:10] for r in champ_all), default=WIN_1Y_END)
    end_1y = min(WIN_1Y_END, data_end)
    month_end = data_end
    print(f"  windows: 1y {WIN_1Y_START}→{end_1y} · month {MONTH_START}→{month_end}", flush=True)

    print("  load caches…", flush=True)
    dual = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(5000)
    sess_1y = [d for d in sessions_all if P2F_1Y["start"] < d <= P2F_1Y["end"]]
    active_1y = fs._active_days(sess_1y, fs._load_daily()) if sess_1y else set()
    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ_rows = _champ_floor(
        [dict(r, track="champion") for r in dual["dual15"]["champion"]]
    )
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]
    champ_native = path_u.get("champ_native") or champ_rows

    print("  P2F rebuild…", flush=True)
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
    recipes_c = load_phase2f_cap2_recipes()
    all_tags: List[str] = []
    seen = set()
    for desk in list(LIVE_DAY_DESKS) + list(LIVE_CAP2_DESKS):
        meta = recipes_f.get(desk) or recipes_c.get(desk) or {}
        for t in meta.get("stream_tags_research") or []:
            if t not in seen:
                seen.add(t)
                all_tags.append(t)
    by_tag = rebuild_all_tags(
        all_tags, path_u, gaps, active_1y, dual15, dual5, proven, champ_rows
    )
    p2f_day_full = build_p2f_day_desks(phase1_1y, by_tag)
    p2f_cap2_full = build_p2f_cap2_desks(phase1_1y, by_tag)

    print("  P2G rebuild…", flush=True)
    sess_5y = [d for d in sessions_all if WINDOW_5Y["start"] < d <= WINDOW_5Y["end"]]
    active_5y = fs._active_days(sess_5y, fs._load_daily()) if sess_5y else set()
    phase1_5y = build_all_accurate_desks(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=path_u.get("crown_by_risk") or {},
        good_by_risk=path_u.get("good_by_risk") or {},
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active_5y,
    )
    d10 = load_d10()
    univ = universes_p2g(path_u, d10, champ_native)
    streams_all = mine_streams(univ, gaps, active_5y, floor_min=82.71)
    by_tag_g = {t: rows for t, rows in streams_all}
    recipes_g = load_phase2g_recipes()
    p2g_full: Dict[str, List[dict]] = {}
    for desk in LIVE_P2G_DESKS:
        floor = HARD_GATES[desk]
        meta = recipes_g.get(desk) or {}
        tags = list(meta.get("stream_tags_research") or [])
        seed = list(phase1_5y.get(BASE_KEY_BY_DESK[desk]) or [])
        p2g_full[desk] = stamp_p2g(rebuild_held_p2g(seed, tags, by_tag_g, floor), desk)

    champ_held = load_held_calls()
    champ_full = champ_all  # held ∪ live ledger (stamped)

    def slice_books(a: str, b: str) -> Dict[str, Any]:
        champ_h = clip_incl(champ_held, a, b)
        champ_f = clip_incl(champ_full, a, b)
        p2f_day = {d: clip_incl(p2f_day_full.get(d) or [], a, b) for d in LIVE_DAY_DESKS}
        p2f_cap2 = {
            d: clip_incl(p2f_cap2_full.get(d) or [], a, b) for d in LIVE_CAP2_DESKS
        }
        p2g = {d: clip_incl(p2g_full.get(d) or [], a, b) for d in LIVE_P2G_DESKS}
        combined = combine_live_rows(
            p2f_day=p2f_day,
            p2f_cap2=p2f_cap2,
            p2g_10m=p2g,
            champ_plus=champ_f,
        )
        return {
            "window": {"start": a, "end": b},
            "calls_board_champ_plus": stats(champ_f),
            "champ_held_only": stats(champ_h),
            "combine": {
                "n_raw": combined["n_raw"],
                "n_ui": combined["n_ui"],
                "n_multi": combined["n_multi_desk"],
                "blocked_distinct": int(combined.get("blocked_distinct") or 0),
                "hit_pct_ui": hit(combined["ui_rows"]),
                "ui": stats(combined["ui_rows"]),
            },
            "by_month_champ": month_rollup(champ_f),
            "by_month_ui": month_rollup(combined["ui_rows"]),
            "p2f_day": {d: stats(p2f_day[d]) for d in LIVE_DAY_DESKS},
            "p2f_cap2": {d: stats(p2f_cap2[d]) for d in LIVE_CAP2_DESKS},
            "p2g": {d: stats(p2g[d]) for d in LIVE_P2G_DESKS},
            "_rows": {
                "champ": champ_f,
                "ui": combined["ui_rows"],
                "p2f_day": p2f_day,
                "p2f_cap2": p2f_cap2,
                "p2g": p2g,
            },
        }

    print("  slice 1y…", flush=True)
    y1 = slice_books(WIN_1Y_START, end_1y)
    print("  slice month…", flush=True)
    mo = slice_books(MONTH_START, month_end)

    # Golden checks on locked CHAMP 1y expected (held)
    champ_locked = clip_incl(champ_held, CHAMP_1Y["start"], CHAMP_1Y["end"])
    exp = CHAMP_EXP["1y"]
    checks = []
    ok_n = len(champ_locked) == int(exp["n"])
    ok_h = abs(hit(champ_locked) - float(exp["hit_pct"])) <= 0.05
    checks.append(
        {
            "name": "champ_held_1y_golden",
            "ok": ok_n and ok_h,
            "detail": (
                f"got {len(champ_locked)}@{hit(champ_locked)} · "
                f"exp {exp['n']}@{exp['hit_pct']}"
            ),
        }
    )
    checks.append(
        {
            "name": "1y_blocked_0",
            "ok": y1["combine"]["blocked_distinct"] == 0,
            "detail": f"blocked={y1['combine']['blocked_distinct']}",
        }
    )
    checks.append(
        {
            "name": "month_blocked_0",
            "ok": mo["combine"]["blocked_distinct"] == 0,
            "detail": f"blocked={mo['combine']['blocked_distinct']}",
        }
    )

    # P2F day golden on locked P2F window
    p2f_ok = True
    p2f_details = []
    for desk in LIVE_DAY_DESKS:
        rs = _clip(p2f_day_full.get(desk) or [], P2F_1Y["start"], P2F_1Y["end"])
        exp_d = P2F_DAY_EXP[desk]
        ok = len(rs) == int(exp_d["n"]) and abs(hit(rs) - float(exp_d["hit_pct"])) <= 0.05
        p2f_ok = p2f_ok and ok
        p2f_details.append(f"{desk}:{len(rs)}@{hit(rs)}")
    checks.append(
        {"name": "p2f_day_1y_golden", "ok": p2f_ok, "detail": "; ".join(p2f_details[:3]) + "…"}
    )

    fails = [c for c in checks if not c["ok"]]
    verdict = "PASS" if not fails else "FAIL"
    elapsed = round(time.time() - t0, 1)

    def dump_slice(title: str, sl: Dict[str, Any]) -> List[str]:
        cb = sl["calls_board_champ_plus"]
        ui = sl["combine"]
        lines = [
            f"## {title}",
            "",
            f"**Window:** `{sl['window']['start']}` → `{sl['window']['end']}`",
            "",
            "### Calls board (live listing = CHAMP_PLUS)",
            "",
            "| Slice | N | Wins | Hit% | Net pts |",
            "|---|---:|---:|---:|---:|",
            f"| **CHAMP_PLUS held ∪ live engine** | {cb['n']} | {cb['wins']} | **{cb['hit_pct']}** | {cb['net_pts']} |",
            f"| Held book only | {sl['champ_held_only']['n']} | {sl['champ_held_only']['wins']} | {sl['champ_held_only']['hit_pct']} | {sl['champ_held_only']['net_pts']} |",
            "",
            "Track mix (board): "
            + ", ".join(
                f"{k}:{v}"
                for k, v in list((cb.get("tracks") or {}).items())[:8]
            ),
            "",
            "### FINAL UI combine (P2F + P2G + CHAMP_PLUS)",
            "",
            f"raw={ui['n_raw']} · ui={ui['n_ui']} · multi={ui['n_multi']} · "
            f"**blocked={ui['blocked_distinct']}** · UI hit=**{ui['hit_pct_ui']}%**",
            "",
            "### By month · Calls board (CHAMP_PLUS)",
            "",
            "| Month | N | Hit% | Net |",
            "|---|---:|---:|---:|",
        ]
        for m, st in (sl.get("by_month_champ") or {}).items():
            lines.append(f"| {m} | {st['n']} | {st['hit_pct']} | {st['net_pts']} |")
        lines.append("")
        lines.append("### By month · FINAL UI")
        lines.append("")
        lines.append("| Month | N | Hit% |")
        lines.append("|---|---:|---:|")
        for m, st in (sl.get("by_month_ui") or {}).items():
            lines.append(f"| {m} | {st['n']} | {st['hit_pct']} |")
        lines.append("")
        rows = sl["_rows"]
        lines.extend(desk_table("P2F day", rows["p2f_day"]))
        lines.extend(desk_table("P2F Cap2", rows["p2f_cap2"]))
        lines.extend(desk_table("P2G 10m", rows["p2g"]))
        # call list for month (compact)
        if title.startswith("Current"):
            lines.extend(
                [
                    "### Month call list · CHAMP_PLUS (Calls board)",
                    "",
                    "| Day | HM | Side | Track | Win | Pts |",
                    "|---|---|---|---|---|---:|",
                ]
            )
            for r in sorted(
                rows["champ"],
                key=lambda x: (str(x.get("day")), str(x.get("hm") or "")),
            ):
                w = "W" if r.get("win") else ("L" if r.get("win") is False else "?")
                lines.append(
                    f"| {r.get('day')} | {r.get('hm')} | "
                    f"{str(r.get('decision') or r.get('side') or '').upper()} | "
                    f"{r.get('track') or '—'} | {w} | {r.get('points') or ''} |"
                )
            lines.append("")
        return lines

    lines = [
        "# NIFTY — LIVE logic replay · 1y + current month",
        "",
        "**Live path (code):** `SUPPRESS_DUAL_LIST=1` · dual proven/champion **does not list** · "
        "**CHAMP_PLUS** fills Calls · P2F/P2G annotate + FINAL UI combine.",
        f"**Desk:** `{CHAMP_DESK}` · `{CHAMP_ACC}` · brackets ±30 · Cap4",
        f"**Data end:** `{data_end}`",
        f"**Elapsed:** {elapsed}s",
        "",
        "## Headline",
        "",
        "| Window | Calls board N | Board hit% | FINAL UI N | UI hit% | Blocked |",
        "|---|---:|---:|---:|---:|---:|",
        (
            f"| **1y** `{WIN_1Y_START}`→`{end_1y}` | "
            f"{y1['calls_board_champ_plus']['n']} | "
            f"**{y1['calls_board_champ_plus']['hit_pct']}** | "
            f"{y1['combine']['n_ui']} | {y1['combine']['hit_pct_ui']} | "
            f"{y1['combine']['blocked_distinct']} |"
        ),
        (
            f"| **Month** `{MONTH_START}`→`{month_end}` | "
            f"{mo['calls_board_champ_plus']['n']} | "
            f"**{mo['calls_board_champ_plus']['hit_pct']}** | "
            f"{mo['combine']['n_ui']} | {mo['combine']['hit_pct_ui']} | "
            f"{mo['combine']['blocked_distinct']} |"
        ),
        "",
    ]
    lines.extend(dump_slice(f"Last 1 year (`{WIN_1Y_START}` → `{end_1y}`)", y1))
    lines.extend(dump_slice(f"Current month (`{MONTH_START}` → `{month_end}`)", mo))
    lines.extend(
        [
            "## Validation",
            "",
        ]
    )
    for c in checks:
        lines.append(f"- {'PASS' if c['ok'] else 'FAIL'} `{c['name']}` — {c['detail']}")
    lines.extend(
        [
            "",
            f"## Verdict: **{verdict}**",
            "",
            "Restore dual-first listing: `SUPPRESS_DUAL_LIST=0`",
            "",
            "_Generated by `tests/builders/validate_live_logic_1y_month.py`_",
            "",
        ]
    )

    # JSON without heavy _rows
    def slim(sl: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in sl.items() if k != "_rows"}

    payload = {
        "live_flags": {
            "SUPPRESS_DUAL_LIST": os.environ.get("SUPPRESS_DUAL_LIST", "1"),
            "USE_DUAL_TRACK": os.environ.get("USE_DUAL_TRACK", "1"),
            "calls_board": "CHAMP_PLUS_T30SL30_CAP4",
            "annotate": ["P2F", "P2G", "CHAMP_PLUS"],
        },
        "data_end": data_end,
        "1y": slim(y1),
        "month": slim(mo),
        "checks": checks,
        "verdict": verdict,
        "elapsed_s": elapsed,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print(f"\n=== {verdict} ===", flush=True)
    print(
        f"1y board {y1['calls_board_champ_plus']['n']} @ {y1['calls_board_champ_plus']['hit_pct']}%",
        flush=True,
    )
    print(
        f"month board {mo['calls_board_champ_plus']['n']} @ {mo['calls_board_champ_plus']['hit_pct']}%",
        flush=True,
    )
    print(f"wrote {OUT_MD} · {elapsed}s", flush=True)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
