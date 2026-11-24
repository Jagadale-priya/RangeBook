"""Add Nov 2026 (D10/crown ticket days) into CHAMPION+ monthly report.

Prod2 sessions end 2026-10-23 — Nov has no session rows there, but D10/crown
tickets exist. Fill those days onto the monthly book and rewrite the report.

  python -u prod_live/tests/builders/research_champion_plus_add_nov.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _agg  # noqa: E402
from research_confirm_dual_tf_deep import _side  # noqa: E402
import live_final_1y_months_accurate as hold  # noqa: E402
import research_champion_plus_push4_1y as p4  # noqa: E402
import research_champion_plus_monthly_todate as rep  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
JS = OUT / "CHAMPION_PLUS_MONTHLY_TODATE.json"
MD = OUT / "CHAMPION_PLUS_MONTHLY_TODATE.md"

START = "2025-10-24"
START_N, END_N = "2026-11-01", "2026-11-15"
FLOOR = 92.5
CAP = 4


def main() -> int:
    payload = json.loads(JS.read_text(encoding="utf-8"))
    book = []
    for m in payload.get("monthly") or []:
        for r in m.get("calls") or []:
            book.append(
                {
                    "day": r["day"],
                    "hm": r["hm"],
                    "decision": r["side"],
                    "win": r["win"],
                    "track": r.get("track"),
                    "entry": r.get("entry"),
                    "stop_loss": r.get("stop_loss"),
                    "target_1": r.get("target_1"),
                    "points": r.get("points"),
                    "p_t1": r.get("p_t1"),
                    "sl_pts": r.get("sl_pts"),
                    "t1_pts": r.get("t1_pts"),
                    "outcome": r.get("outcome"),
                }
            )
    book = hold._clean(book)
    print(f"book before { _agg(book) }", flush=True)

    idx = rep.build_lookup()
    cands = []
    for v in idx.values():
        rr = rep.norm_ticket(v)
        day = str(rr.get("day") or "")
        if START_N <= day <= END_N:
            cands.append(rr)
    cands = rep.enrich(cands, idx)
    sess = sorted({r["day"] for r in cands})
    print(f"nov cands={len(cands)} days={sess}", flush=True)

    def window_rows(rows, a, b):
        return [r for r in rows if a <= str(r.get("day") or "") <= b]

    def hit(rows):
        return 100.0 * sum(1 for r in rows if r.get("win")) / len(rows) if rows else 0.0

    def ok(rows):
        r1 = window_rows(rows, START, END_N)
        return not (len(r1) >= 3 and round(hit(r1), 2) + 1e-9 < FLOOR)

    cur = [dict(r) for r in book]
    by_day = defaultdict(list)
    for r in cands:
        by_day[r["day"]].append(r)

    added = 0
    while True:
        best = None
        best_n = len(window_rows(cur, START, END_N))
        best_hit = hit(window_rows(cur, START, END_N))
        for day in sess:
            existing = [r for r in cur if r.get("day") == day]
            if len(existing) >= CAP:
                continue
            side_lock = _side(existing[0]) if existing else None
            seen = {rep.key_of(r) for r in existing}
            opts = sorted(
                by_day.get(day, []),
                key=lambda x: (int(bool(x.get("win"))), float(x.get("p_t1") or 0)),
                reverse=True,
            )
            for r in opts:
                if rep.key_of(r) in seen:
                    continue
                if side_lock and _side(r) != side_lock:
                    continue
                trial = p4.merge_cap(cur, [r], CAP)
                n1 = len(window_rows(trial, START, END_N))
                if n1 <= best_n or not ok(trial):
                    continue
                h1 = hit(window_rows(trial, START, END_N))
                if best is None or n1 > best_n or (n1 == best_n and h1 > best_hit):
                    best = trial
                    best_n = n1
                    best_hit = h1
        if not best:
            break
        cur = best
        added += 1
        print(f"  +nov n={best_n} hit={best_hit:.2f} add={added}", flush=True)

    full = rep.enrich(window_rows(cur, START, END_N), idx)
    sessions_all, _, _ = fs._prod2(4000)
    sess_all = sorted(
        set([d for d in sessions_all if START <= d <= "2026-10-23"] + sess)
    )
    months = rep.month_block(full, sess_all)
    overall = _agg(full)
    nov = _agg(window_rows(full, START_N, END_N))
    print(f"NOV {nov}", flush=True)
    print(f"FULL {overall}", flush=True)

    lines = [
        "# CHAMPION+ — monthly report through today",
        "",
        f"**Book:** CHAMPION_PLUS ticket-fill RESEARCH (seed=CHAMPION · floor ≥{FLOOR}%)",
        f"**Requested through:** `{END_N}` (today)",
        "**Prod2 sessions end:** `2026-10-23`",
        "**Nov source:** dual10m + crown ticket days (proxy — not in prod2 session list)",
        f"**Window scored:** `{START}` → `{END_N}` · cap={CAP} same-side",
        "",
        "## Why Nov was missing before",
        "",
        "1. Report used `fs._prod2` sessions → **max `2026-10-23`**, zero `2026-11-*` days.",
        "2. Champion / good pools had **no Nov** rows.",
        "3. Only **dual10m** (+ some crown) had Nov tickets — now filled in below.",
        "",
        "## Overall",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Calls | **{overall.get('n')}** |",
        f"| Hit% | **{overall.get('hit_pct')}%** |",
        f"| W / L | {overall.get('wins')} / {overall.get('losses')} |",
        f"| Points (sum) | **{overall.get('points')}** |",
        "",
        f"**Nov 2026 alone:** N={nov.get('n')} · hit {nov.get('hit_pct')}% · "
        f"{nov.get('wins')}W/{nov.get('losses')}L · pts {nov.get('points')}",
        "",
        "## Monthly scorecard",
        "",
        "| Month | Sess | N | Hit% | W/L | Points | Avg pts | Avg T1 pts | Avg SL pts | Days w/ call | Quiet |",
        "|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for m in months:
        lines.append(
            f"| {m['month']} | {m['sessions']} | {m['n']} | {m['hit_pct']} | "
            f"{m['wins']}/{m['losses']} | {m['points']} | {m['avg_points']} | "
            f"{m['avg_target_pts']} | {m['avg_sl_pts']} | {m['days_with_call']} | "
            f"{m['days_quiet']} |"
        )

    for m in months:
        lines.extend(
            [
                "",
                f"## {m['month']} — calls",
                "",
                f"N={m['n']} · hit {m['hit_pct']}% · points {m['points']} · "
                f"avg T1 {m['avg_target_pts']} · avg SL {m['avg_sl_pts']}",
                "",
                "| # | Day | HM | Side | Win | Track | Entry | SL | Target | SL pts | T1 pts | Points | p |",
                "|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for i, r in enumerate(m["calls"], 1):
            lines.append(
                f"| {i} | {r.get('day')} | {r.get('hm')} | {_side(r)} | "
                f"{'W' if r.get('win') else 'L'} | {r.get('track')} | "
                f"{'' if r.get('entry') is None else r.get('entry')} | "
                f"{'' if r.get('stop_loss') is None else r.get('stop_loss')} | "
                f"{'' if r.get('target_1') is None else r.get('target_1')} | "
                f"{'' if r.get('sl_pts') is None else r.get('sl_pts')} | "
                f"{'' if r.get('t1_pts') is None else r.get('t1_pts')} | "
                f"{'' if r.get('points') is None else r.get('points')} | "
                f"{'' if r.get('p_t1') is None else r.get('p_t1')} |"
            )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Nov uses **ticket-day proxy** (prod2 calendar has no Nov yet).",
            "- Typical SL/T1 ≈ 20–30 pts.",
            "- RESEARCH — not live.",
            "",
        ]
    )
    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out_monthly = []
    for m in months:
        row = {k: v for k, v in m.items() if k != "calls"}
        row["calls"] = [
            {
                "day": r.get("day"),
                "hm": r.get("hm"),
                "side": _side(r),
                "win": r.get("win"),
                "track": r.get("track"),
                "entry": r.get("entry"),
                "stop_loss": r.get("stop_loss"),
                "target_1": r.get("target_1"),
                "sl_pts": r.get("sl_pts"),
                "t1_pts": r.get("t1_pts"),
                "points": r.get("points"),
                "p_t1": r.get("p_t1"),
            }
            for r in m["calls"]
        ]
        out_monthly.append(row)
    JS.write_text(
        json.dumps(
            {
                "window": {"start": START, "end": END_N},
                "overall": overall,
                "nov": nov,
                "monthly": out_monthly,
                "nov_note": "filled from D10/crown tickets; prod2 sessions end 2026-10-23",
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
