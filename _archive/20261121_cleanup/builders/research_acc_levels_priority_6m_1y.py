"""Per-priority (V5→P75) report for every held level — 6m + 1y, monthly, dup check.

Latest held = Phase-2f. All prior levels kept.

  python -u prod_live/tests/builders/research_acc_levels_priority_6m_1y.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _side  # noqa: E402
from research_100pct_deeper_more_calls import gap_map, is_perfect  # noqa: E402
from prod_live.logic.accurate_desks import build_all_accurate_desks  # noqa: E402
from prod_live.holding_accurate.rebuild_streams import rebuild_all_tags  # noqa: E402
from prod_live.holding_accurate.replay import replay_tags, stamp  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
HOLD = ROOT / "prod_live" / "holding_accurate"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL_10Y = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH_10Y = LEDGER / "_cache_path_trusted_10y.json"

END = date.today().strftime("%Y-%m-%d")
START_1Y = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")
START_6M = (date.today() - timedelta(days=182)).strftime("%Y-%m-%d")

# Priority ladder (day-dedupe desks) — through P75
PRIORITY = [
    ("P100", "ACC100_MULTI_V5", "100% family"),
    ("P92", "ACC_WIDE_P92", "high-90"),
    ("P90", "ACC_WIDE_P90", "mid-90"),
    ("P85", "ACC_WIDE_P85", "mid-85"),
    ("P85B", "ACC_WIDE_P85B", "mid-85b"),
    ("P80", "ACC_WIDE_P80", "vol-80"),
    ("P75", "ACC_WIDE_P75", "vol-75"),
]

LEVEL_FILES = [
    ("P1", None, "LOCKED"),
    ("P2C", HOLD / "recipes.json", "HELD"),
    ("P2D", HOLD / "phase2d" / "recipes_research.json", "HELD"),
    ("P2E", HOLD / "phase2e" / "recipes_research.json", "HELD"),
    ("P2F", HOLD / "phase2f" / "recipes_research.json", "HELD"),  # LATEST
]


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 2)


def month_stats(rows: List[dict]) -> List[Dict[str, Any]]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        day = str(r.get("day") or "")
        if len(day) >= 7:
            by[day[:7]].append(r)
    out = []
    for ym in sorted(by):
        rs = by[ym]
        out.append(
            {
                "month": ym,
                "n": len(rs),
                "hit_pct": hit_pct(rs),
                "wins": sum(1 for r in rs if r.get("win")),
                "losses": sum(1 for r in rs if not r.get("win")),
                "points": (_agg(rs) or {}).get("points"),
                "buy": sum(1 for r in rs if _side(r) == "BUY"),
                "sell": sum(1 for r in rs if _side(r) == "SELL"),
                "days": sorted({str(r.get("day") or "") for r in rs}),
            }
        )
    return out


def dup_check(rows: List[dict]) -> Dict[str, Any]:
    """Day-dedupe desks: at most one call per day. Also check (day,side,hm)."""
    by_day: Dict[str, int] = defaultdict(int)
    by_sig: Dict[Tuple[str, str, str], int] = defaultdict(int)
    for r in rows:
        day = str(r.get("day") or "")
        sig = (day, _side(r), str(r.get("hm") or ""))
        by_day[day] += 1
        by_sig[sig] += 1
    day_dups = {d: n for d, n in by_day.items() if d and n > 1}
    sig_dups = {f"{a}|{b}|{c}": n for (a, b, c), n in by_sig.items() if n > 1}
    return {
        "n": len(rows),
        "unique_days": len([d for d in by_day if d]),
        "day_duplicate_count": len(day_dups),
        "day_duplicates": dict(sorted(day_dups.items())[:20]),
        "sig_duplicate_count": len(sig_dups),
        "sig_duplicates": dict(sorted(sig_dups.items())[:20]),
        "ok_day_unique": len(day_dups) == 0,
        "ok_sig_unique": len(sig_dups) == 0,
    }


def score_window(rows: List[dict], start: str, end: str) -> Dict[str, Any]:
    rs = _clip(rows, start, end)
    days = sorted({str(r.get("day") or "") for r in rs if r.get("day")})
    return {
        "n": len(rs),
        "hit_pct": hit_pct(rs),
        "perfect": bool(rs) and is_perfect(rs),
        "points": (_agg(rs) or {}).get("points") if rs else 0,
        "wins": sum(1 for r in rs if r.get("win")),
        "losses": sum(1 for r in rs if not r.get("win")),
        "buy": sum(1 for r in rs if _side(r) == "BUY"),
        "sell": sum(1 for r in rs if _side(r) == "SELL"),
        "call_days": len(days),
        "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "months": month_stats(rs),
        "dup": dup_check(rs),
        "calls": [
            {
                "day": r.get("day"),
                "hm": r.get("hm"),
                "side": _side(r),
                "win": bool(r.get("win")),
                "p_t1": r.get("p_t1"),
                "points": r.get("points"),
                "tag": r.get("holding_tag") or r.get("accurate_tag") or r.get("desk_tag"),
            }
            for r in sorted(rs, key=lambda x: (str(x.get("day") or ""), str(x.get("hm") or "")))
        ],
    }


def load_cands(path: Optional[Path]) -> Dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("candidates") or {}


def main() -> None:
    t0 = time.time()
    print(f"PRIORITY ladder report 6m+1y → {END} (latest=P2F)", flush=True)

    dual = json.loads(CACHE_DUAL_10Y.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH_10Y.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_1Y < d <= END]
    active = fs._active_days(sess, fs._load_daily()) if sess else set()

    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ = _champ_floor([dict(r, track="champion") for r in dual["dual15"]["champion"]])
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]
    champ_native = path_u.get("champ_native") or champ

    print("  Phase-1…", flush=True)
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

    level_cands: Dict[str, Dict[str, Any]] = {}
    all_tags: List[str] = []
    seen: Set[str] = set()
    for lab, path, _ in LEVEL_FILES:
        cands = load_cands(path)
        level_cands[lab] = cands
        for meta in cands.values():
            for t in meta.get("stream_tags_held") or meta.get("stream_tags_research") or []:
                if t not in seen:
                    seen.add(t)
                    all_tags.append(t)

    print(f"  rebuild {len(all_tags)} tags…", flush=True)
    by_tag = rebuild_all_tags(
        all_tags, path_u, gaps, active, dual15, dual5, proven, champ
    )

    # Build desk rows per level × priority
    desks: Dict[str, Dict[str, List[dict]]] = {}  # level -> pri_key -> rows
    meta_out: Dict[str, Dict[str, Any]] = {}

    for lab, path, status in LEVEL_FILES:
        desks[lab] = {}
        meta_out[lab] = {}
        for pri, base, label in PRIORITY:
            if lab == "P1":
                rows = list(phase1.get(base) or [])
                cand = base
            else:
                cands = level_cands.get(lab) or {}
                meta = cands.get(base) or {}
                tags = list(meta.get("stream_tags_held") or meta.get("stream_tags_research") or [])
                cand = meta.get("candidate_tag") or f"{base}_{lab}"
                if not tags:
                    # fallback to phase1 if level missing this desk
                    rows = list(phase1.get(base) or [])
                    cand = base
                else:
                    rows = replay_tags(list(phase1.get(base) or []), tags, by_tag, mode="day")
            rows = stamp(rows, cand, level=lab)
            desks[lab][pri] = rows
            meta_out[lab][pri] = {
                "priority": pri,
                "base_desk": base,
                "candidate_tag": cand,
                "label": label,
                "status": status,
                "level": lab,
                "latest": lab == "P2F",
            }
            print(f"  {lab} {pri} ({cand}): built n={len(rows)}", flush=True)

    # Score 6m + 1y
    results: Dict[str, Any] = {}
    for lab in desks:
        for pri, rows in desks[lab].items():
            key = f"{lab}|{pri}"
            results[key] = {
                **meta_out[lab][pri],
                "w6m": score_window(rows, START_6M, END),
                "w1y": score_window(rows, START_1Y, END),
            }
            w = results[key]["w1y"]
            print(
                f"  {key}: 1y {w['n']}@{w['hit_pct']}% dup_day={w['dup']['day_duplicate_count']} "
                f"dup_sig={w['dup']['sig_duplicate_count']}",
                flush=True,
            )

    # Cross-priority day overlap within latest P2F (nested channels, not dups)
    overlap: Dict[str, Any] = {}
    if "P2F" in desks:
        days_by_pri: Dict[str, Set[str]] = {}
        for pri, _, _ in PRIORITY:
            rs = _clip(desks["P2F"][pri], START_1Y, END)
            days_by_pri[pri] = {str(r.get("day") or "") for r in rs if r.get("day")}
        order = [p for p, _, _ in PRIORITY]
        nest = {}
        for i, a in enumerate(order):
            for b in order[i + 1 :]:
                inter = days_by_pri[a] & days_by_pri[b]
                only_a = days_by_pri[a] - days_by_pri[b]
                nest[f"{a}_vs_{b}"] = {
                    "shared_days": len(inter),
                    "only_in_tighter": len(only_a),
                    "tighter_subset_of_wider": len(only_a) == 0,
                }
        overlap = {
            "P2F_1y_day_counts": {k: len(v) for k, v in days_by_pri.items()},
            "pairwise": nest,
            "note": "Separate priority channels may share days; within each desk days are unique",
        }

    payload = {
        "latest_held_level": "P2F",
        "latest_tag_100": "ACC100_MULTI_V11",
        "window_end": END,
        "windows": {"6m": {"start": START_6M, "end": END}, "1y": {"start": START_1Y, "end": END}},
        "priority_order": [p[0] for p in PRIORITY],
        "levels": [x[0] for x in LEVEL_FILES],
        "results": {
            k: {
                **{kk: vv for kk, vv in v.items() if kk not in ("w6m", "w1y")},
                "w6m": {kk: vv for kk, vv in v["w6m"].items() if kk != "calls"},
                "w1y": {kk: vv for kk, vv in v["w1y"].items() if kk != "calls"},
                "calls_6m": v["w6m"]["calls"],
                "calls_1y": v["w1y"]["calls"],
            }
            for k, v in results.items()
        },
        "overlap_note": overlap,
        "elapsed_s": round(time.time() - t0, 1),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (HOLD / "reports").mkdir(parents=True, exist_ok=True)
    for dest in (OUT, LEDGER, HOLD / "reports"):
        (dest / "ACC_PRIORITY_LEVELS_6M_1Y.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )

    # ---- Markdown ----
    lines = [
        f"# Priority ladder (→ P75) — all held levels · 6m + 1y to {END}",
        "",
        f"**Latest held logic: Phase-2f** (`ACC100_MULTI_V11` / P92…P75_P2F).",
        "Prior levels kept: P1 locked · P2C · P2D · P2E · **P2F**.",
        "",
        f"**6m:** `{START_6M}` → `{END}`  ·  **1y:** `{START_1Y}` → `{END}`",
        "",
        f"Elapsed {payload['elapsed_s']}s",
        "",
        "## Duplicate-call check (day desks)",
        "",
        "Each priority desk is **day-dedupe** (one call per day). Check below:",
        "",
        "| Level | Priority | 1y N | Unique days | Day dups | Sig dups | OK? |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    all_ok = True
    for lab, _, _ in LEVEL_FILES:
        for pri, _, _ in PRIORITY:
            r = results[f"{lab}|{pri}"]["w1y"]["dup"]
            ok = r["ok_day_unique"] and r["ok_sig_unique"]
            all_ok = all_ok and ok
            lines.append(
                f"| {lab} | {pri} | {r['n']} | {r['unique_days']} | "
                f"{r['day_duplicate_count']} | {r['sig_duplicate_count']} | "
                f"{'YES' if ok else 'NO'} |"
            )
    lines += [
        "",
        f"**Overall within-desk duplicates:** {'NONE — clean' if all_ok else 'FOUND — see JSON'}",
        "",
        "Note: Wider priorities (e.g. P75) **may share days** with tighter ones (P100) — that is nested coverage, not a bug. Each desk is its own channel.",
        "",
        "## 6-month summary — per priority × level",
        "",
        "| Priority | P1 | P2C | P2D | P2E | **P2F (latest)** |",
        "|---|---|---|---|---|---|",
    ]
    for pri, base, _ in PRIORITY:
        cells = []
        for lab, _, _ in LEVEL_FILES:
            w = results[f"{lab}|{pri}"]["w6m"]
            cells.append(f"{w['n']} @ {w['hit_pct']}%")
        lines.append(f"| `{pri}` (`{base}`) | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## 1-year summary — per priority × level",
        "",
        "| Priority | P1 | P2C | P2D | P2E | **P2F (latest)** |",
        "|---|---|---|---|---|---|",
    ]
    for pri, base, _ in PRIORITY:
        cells = []
        for lab, _, _ in LEVEL_FILES:
            w = results[f"{lab}|{pri}"]["w1y"]
            cells.append(f"{w['n']} @ {w['hit_pct']}%")
        lines.append(f"| `{pri}` (`{base}`) | " + " | ".join(cells) + " |")

    # Monthly detail — latest P2F all priorities + P1 P100 for compare
    lines += ["", "## Monthly detail — **P2F latest** (all priorities)", ""]
    for pri, base, label in PRIORITY:
        r = results[f"P2F|{pri}"]
        w = r["w1y"]
        lines += [
            f"### P2F `{r['candidate_tag']}` ({pri} · {label}) — 1y {w['n']} @ {w['hit_pct']}%",
            "",
            "| Month | N | Hit | W | L | Pts | B/S |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
        for m in w["months"]:
            lines.append(
                f"| {m['month']} | {m['n']} | {m['hit_pct']} | {m['wins']} | {m['losses']} | "
                f"{m['points']} | {m['buy']}/{m['sell']} |"
            )
        lines.append("")
        # 6m months only subset note
        w6 = r["w6m"]
        lines += [
            f"**6m only:** {w6['n']} @ {w6['hit_pct']}% · {w6['first_day']} → {w6['last_day']}",
            "",
            "| Month (6m window) | N | Hit | W | L | Pts |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for m in w6["months"]:
            lines.append(
                f"| {m['month']} | {m['n']} | {m['hit_pct']} | {m['wins']} | {m['losses']} | {m['points']} |"
            )
        lines.append("")

    # Call lists for P2F P100 and P75 (1y)
    for pri in ("P100", "P75"):
        r = results[f"P2F|{pri}"]
        calls = r["w1y"]["calls"]
        lines += [
            f"## Call list — P2F `{r['candidate_tag']}` (1y, {len(calls)} calls)",
            "",
            "| Day | HM | Side | Win | Tag |",
            "|---|---|---|---|---|",
        ]
        for c in calls:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['side']} | "
                f"{'W' if c['win'] else 'L'} | `{c['tag']}` |"
            )
        lines.append("")

    lines += [
        "## Confirm",
        "",
        f"- Latest held = **P2F**",
        f"- Within each desk: day-unique = **{'YES' if all_ok else 'NO'}**",
        "- Full call dumps + 6m lists in JSON `calls_6m` / `calls_1y`",
        "",
        "JSON: `ACC_PRIORITY_LEVELS_6M_1Y.json`",
        "",
    ]

    text = "\n".join(lines)
    for dest in (OUT, LEDGER, HOLD / "reports"):
        (dest / "ACC_PRIORITY_LEVELS_6M_1Y.md").write_text(text, encoding="utf-8")
    print("Wrote", OUT / "ACC_PRIORITY_LEVELS_6M_1Y.md", flush=True)


if __name__ == "__main__":
    main()
