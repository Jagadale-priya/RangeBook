"""Per-month report for held PA logics over last ~6 months (live-path 1m).

  python -u prod_live/tests/builders/_report_pa_held_6m_monthly.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Set

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
]
import kite_data  # noqa: E402
from prod_live.logic import pa_structure_live as pa  # noqa: E402
from prod_live.tests.builders._research_pa_held_logics_long import (  # noqa: E402
    _install_sr_cache,
    held_cfgs,
    monthly_chunks,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
MD = OUT / "PA_HELD_LOGICS_6M_MONTHLY.md"
JS = OUT / "PA_HELD_LOGICS_6M_MONTHLY.json"


def main() -> int:
    _install_sr_cache()
    print("Fetching NIFTY 1m…", flush=True)
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=220, keep_partial=False
    )
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    all_days = sorted({str(ts.date()) for ts in bars.index})
    # last ~126 sessions ≈ 6m
    n6 = min(126, len(all_days))
    days_6m = all_days[-n6:]
    score_days = set(days_6m)
    i0 = max(0, all_days.index(days_6m[0]) - 2)
    days_for_scan = all_days[i0:]

    # month labels in order within 6m window
    months: List[str] = []
    for d in days_6m:
        ym = d[:7]
        if not months or months[-1] != ym:
            months.append(ym)

    print(
        f"6m window {days_6m[0]}→{days_6m[-1]} sessions={len(days_6m)} months={months}",
        flush=True,
    )

    cfgs = held_cfgs()
    # name -> month -> calls summary
    table: Dict[str, Dict[str, Any]] = {}
    for cfg in cfgs:
        print(f"\nSCAN {cfg.name}…", flush=True)
        by_month_calls: Dict[str, List] = defaultdict(list)
        for score_set, frame_days, ym in monthly_chunks(days_for_scan, lookback=2):
            if ym not in months:
                continue
            if not (score_set & score_days):
                continue
            frame = bars[bars.index.strftime("%Y-%m-%d").isin(set(frame_days))]
            print(f"  {ym} bars={len(frame)}…", flush=True)
            calls = pa.scan_session(frame, settle=True, cfg=cfg)
            for c in calls:
                if c.day in score_days and c.day[:7] == ym:
                    by_month_calls[ym].append(c)

        month_rows = {}
        for ym in months:
            calls = by_month_calls.get(ym, [])
            s = pa.summarize(calls)
            hard_sl = sum(1 for c in calls if c.exit_why == "sl")
            sess = sum(1 for d in days_6m if d.startswith(ym))
            month_rows[ym] = {
                "n": s.get("n") or 0,
                "hit_pct": s.get("hit_pct"),
                "avg_R": s.get("avg_R"),
                "sum_pts": s.get("sum_pts") or 0,
                "hard_sl": hard_sl,
                "sessions": sess,
                "avg_per_day": round(len(calls) / max(sess, 1), 2),
            }
            print(
                f"  {ym}: n={month_rows[ym]['n']} hit={month_rows[ym]['hit_pct']} "
                f"sum={month_rows[ym]['sum_pts']}",
                flush=True,
            )
        # 6m total
        all_c = [c for ym in months for c in by_month_calls.get(ym, [])]
        tot = pa.summarize(all_c)
        table[cfg.name] = {
            "months": month_rows,
            "total_6m": {
                "n": tot.get("n"),
                "hit_pct": tot.get("hit_pct"),
                "avg_R": tot.get("avg_R"),
                "sum_pts": tot.get("sum_pts"),
                "hard_sl": sum(1 for c in all_c if c.exit_why == "sl"),
            },
        }

    lines = [
        "# Held PA logics · last 6 months **by month**",
        "",
        f"NIFTY 1m live-path · `{days_6m[0]}` → `{days_6m[-1]}` ({len(days_6m)} sessions).",
        f"Months: {', '.join(months)}",
        f"Live lock unchanged: `{pa.load_locked_cfg().name}`.",
        "",
    ]

    # one section per month
    for ym in months:
        sess = sum(1 for d in days_6m if d.startswith(ym))
        rows = []
        for name, blob in table.items():
            r = blob["months"][ym]
            rows.append({"name": name, **r})
        rows.sort(key=lambda r: (r.get("sum_pts") or 0), reverse=True)
        lines += [
            f"## {ym} ({sess} sessions)",
            "",
            "| Logic | N | Hit% | AvgR | Sum pts | Hard SL | /day |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for r in rows:
            mark = "**" if r is rows[0] else ""
            lines.append(
                f"| {mark}{r['name']}{mark} | {r.get('n')} | {r.get('hit_pct')} | "
                f"{r.get('avg_R')} | {r.get('sum_pts')} | {r.get('hard_sl')} | "
                f"{r.get('avg_per_day')} |"
            )
        lines.append("")

    # 6m totals ranked by sum
    lines += [
        "## 6m totals (all months)",
        "",
        "| Logic | N | Hit% | AvgR | Sum pts | Hard SL |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    totals = [
        {"name": name, **blob["total_6m"]} for name, blob in table.items()
    ]
    totals.sort(key=lambda r: (r.get("sum_pts") or 0), reverse=True)
    for r in totals:
        mark = "**" if r is totals[0] else ""
        lines.append(
            f"| {mark}{r['name']}{mark} | {r.get('n')} | {r.get('hit_pct')} | "
            f"{r.get('avg_R')} | {r.get('sum_pts')} | {r.get('hard_sl')} |"
        )
    lines.append("")

    # pivot: logic × month sum
    lines += [
        "## Sum pts by logic × month",
        "",
        "| Logic | " + " | ".join(months) + " | 6m total |",
        "|---|" + "|".join(["---:" for _ in months]) + "|---:|",
    ]
    for name, blob in table.items():
        cells = [str(blob["months"][ym].get("sum_pts") or 0) for ym in months]
        tot = blob["total_6m"].get("sum_pts") or 0
        lines.append(f"| {name} | " + " | ".join(cells) + f" | {tot} |")
    lines.append("")

    OUT.mkdir(parents=True, exist_ok=True)
    MD.write_text("\n".join(lines), encoding="utf-8")
    JS.write_text(
        json.dumps(
            {
                "window": {"start": days_6m[0], "end": days_6m[-1], "n": len(days_6m)},
                "months": months,
                "table": table,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
