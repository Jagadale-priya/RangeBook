"""Test nifty_trend_stay (long-stay pullback) on last 10 + context windows.

Structure only — probability gate off (no model cols on kite/CSV tape).
Cost = 1.0 pt. Judge by avg winner vs avg loser (target ≥2×), hit ~40–55%.

  python -u prod_live/tests/builders/_diag_nifty_trend_stay_last10d.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live" / "tests" / "builders"),
    str(ROOT / "app"),
    str(ROOT / "app" / "market"),
]
import path_setup  # noqa: F401,E402

from _diag_nifty_orb30_vwap_last10d import load_5m, last_n_sessions  # noqa: E402
from prod_live.logic.nifty_trend_stay import generate_calls, summarize  # noqa: E402

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_CSV = OUT_DIR / "NIFTY_TREND_STAY_LAST10D.csv"
OUT_MD = OUT_DIR / "NIFTY_TREND_STAY_LAST10D.md"
OUT_JSON = OUT_DIR / "NIFTY_TREND_STAY_LAST10D.json"
COST = 1.0
WINDOWS = (10, 20, 40, 60)


def _fmt(v: Any, *, pct: bool = False) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "n/a"
    if pct:
        return f"{100.0 * float(v):.1f}%"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def run_window(bars: pd.DataFrame, n: int) -> Dict[str, Any]:
    clip = last_n_sessions(bars, n)
    calls = generate_calls(clip, require_probability=False)
    stats = summarize(calls, cost_points_per_call=COST)
    return {
        "n": n,
        "stats": {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in stats.items()},
        "reasons": calls["reason"].value_counts().to_dict(),
        "calls": calls,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bars, source = load_5m(days=100)
    results = {n: run_window(bars, n) for n in WINDOWS}
    primary = results[10]
    calls = primary["calls"]
    stats = primary["stats"]
    calls.to_csv(OUT_CSV, index=False)

    lines = [
        "# NIFTY trend-stay · long-stay pullback rule",
        "",
        f"**Source:** `{source}` 5m · **cost:** {COST} pt · **probability gate:** off (no model cols)",
        "",
        "## Rule (frozen)",
        "",
        "- Balance 09:15–10:15 · width 25–160",
        "- 15m close beyond IBH/IBL + same side of VWAP",
        "- Entry = first pullback touch + close back in break direction (not the break)",
        "- Chase >25 pts without touch → no call",
        "- Initial stop 15 pts inside level · reject risk >40",
        "- Trail completed post-entry 15m swing · VWAP close exit · flat 14:45 · no reverse",
        "- Module: `prod_live/logic/nifty_trend_stay.py`",
        "",
        "## Last 10 sessions",
        "",
        f"- sessions: **{int(stats['sessions'])}**",
        f"- calls: **{int(stats['calls'])}**",
        f"- wins / losses: **{int(stats['wins'])} / {int(stats['losses'])}**",
        f"- hit rate: **{_fmt(stats['hit_rate'], pct=True)}**",
        f"- avg winner / loser: **{_fmt(stats.get('average_winner'))} / {_fmt(stats.get('average_loser'))}**",
        f"- winner÷|loser|: **{_fmt(stats.get('winner_loser_ratio'))}** (keep if ≥2)",
        f"- net points: **{_fmt(stats['net_points'])}**",
        f"- no-call days: **{int(stats.get('no_call_days') or 0)}**",
        f"- reasons: `{primary['reasons']}`",
        "",
        "### Day-by-day",
        "",
        "| Date | Status | Side | Width | Signal | Entry | Stop0 | Exit | Pts | MFE | Reason |",
        "|---|---|---|---:|---|---:|---:|---|---:|---:|---|",
    ]
    for _, row in calls.iterrows():
        d = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
        side = row["direction"] or "—"
        width = f"{row['balance_width']:.1f}" if pd.notna(row["balance_width"]) else "—"
        sig = (
            pd.Timestamp(row["signal_time"]).strftime("%H:%M")
            if pd.notna(row["signal_time"])
            else "—"
        )
        ent_t = (
            pd.Timestamp(row["entry_time"]).strftime("%H:%M")
            if pd.notna(row["entry_time"])
            else "—"
        )
        ent = f"{row['entry']:.2f}" if pd.notna(row["entry"]) else "—"
        stop = f"{row['initial_stop']:.2f}" if pd.notna(row["initial_stop"]) else "—"
        xt = (
            pd.Timestamp(row["exit_time"]).strftime("%H:%M")
            if pd.notna(row["exit_time"])
            else "—"
        )
        pts = f"{row['points']:.1f}" if pd.notna(row["points"]) else "—"
        mfe = f"{row['max_favorable']:.1f}" if pd.notna(row["max_favorable"]) else "—"
        lines.append(
            f"| {d} | {row['status']} | {side} | {width} | {sig} | "
            f"{ent_t}/{ent} | {stop} | {xt} | {pts} | {mfe} | {row['reason']} |"
        )

    lines += [
        "",
        "## Context windows",
        "",
        "| Window | Calls | W/L | Hit | Avg W | Avg L | W÷|L| | Net | No-call |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for n in WINDOWS:
        s = results[n]["stats"]
        lines.append(
            f"| last {n} | {int(s['calls'])} | {int(s['wins'])}/{int(s['losses'])} | "
            f"{_fmt(s['hit_rate'], pct=True)} | {_fmt(s.get('average_winner'))} | "
            f"{_fmt(s.get('average_loser'))} | {_fmt(s.get('winner_loser_ratio'))} | "
            f"{_fmt(s['net_points'])} | {int(s.get('no_call_days') or 0)} |"
        )

    taken40 = results[40]["calls"]
    taken40 = taken40[taken40["entry"].notna()]
    if len(taken40):
        lines += [
            "",
            "### Taken calls · last 40",
            "",
            "| Date | Side | Width | Entry | Stop0 | Status | Pts | MFE |",
            "|---|---|---:|---:|---:|---|---:|---:|",
        ]
        for _, row in taken40.iterrows():
            d = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
            lines.append(
                f"| {d} | {row['direction']} | {row['balance_width']:.1f} | "
                f"{row['entry']:.2f} | {row['initial_stop']:.2f} | {row['status']} | "
                f"{row['points']:.1f} | {row['max_favorable']:.1f} |"
            )

    lines += ["", f"CSV: `{OUT_CSV.relative_to(ROOT).as_posix()}`", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    payload = {
        "source": source,
        "cost_points": COST,
        "require_probability": False,
        "windows": {
            str(n): {"stats": results[n]["stats"], "reasons": results[n]["reasons"]}
            for n in WINDOWS
        },
        "last10_calls": json.loads(calls.to_json(orient="records", date_format="iso")),
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["windows"], indent=2), flush=True)
    print(f"wrote {OUT_MD}", flush=True)


if __name__ == "__main__":
    main()
