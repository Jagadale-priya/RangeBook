"""Serious PA research · today session + recent days · structure SL live book.

Pulls Kite 1m NIFTY, walks bar-by-bar causally (PA_STRUCTURE_SL_LIVE):
  BREAK_HOLD / SWEEP_RECLAIM / OR_RETEST
  SL = prev candle + swing extreme (not fixed pts)
  Exit = trail after 1R / structure fail / time — no fixed target

Writes:
  prod_live/reports/1y/PA_STRUCTURE_TODAY_LIVE.md
  prod_live/reports/1y/PA_STRUCTURE_TODAY_LIVE.json
  prod_live/holding_accurate/pa_structure/live_session_calls.json

  python -u prod_live/tests/builders/_research_pa_structure_today_live.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
import path_setup  # noqa: F401,E402
import kite_data  # noqa: E402

from prod_live.logic.pa_structure_live import (  # noqa: E402
    DESK,
    append_live_calls,
    norm_1m,
    scan_session,
    summarize,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
MD = OUT / "PA_STRUCTURE_TODAY_LIVE.md"
JS = OUT / "PA_STRUCTURE_TODAY_LIVE.json"


def fetch_1m(days: int = 25) -> pd.DataFrame:
    print(f"Pulling Kite NIFTY 1m · {days}d …", flush=True)
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=days, keep_partial=False
    )
    if err or raw is None:
        raise RuntimeError(f"kite 1m failed: {err}")
    bars = norm_1m(raw)
    print(
        f"  bars={len(bars)}  {bars.index.min()} → {bars.index.max()}",
        flush=True,
    )
    return bars


def session_days(bars: pd.DataFrame) -> list[str]:
    return sorted({str(ts.date()) for ts in bars.index})


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    bars = fetch_1m(25)
    days = session_days(bars)
    today = days[-1]
    print(f"sessions={len(days)}  today={today}", flush=True)

    # --- today ---
    today_bars = bars[bars.index.strftime("%Y-%m-%d") == today]
    today_calls = scan_session(today_bars, settle=True)
    today_sum = summarize(today_calls)
    print(f"TODAY {today}: n={today_sum['n']} hit={today_sum.get('hit_pct')} "
          f"avgR={today_sum.get('avg_R')} sum_pts={today_sum.get('sum_pts')}", flush=True)
    for c in today_calls:
        print(
            f"  {c.hm} {c.side:4} {c.setup:14} entry={c.entry} SL={c.stop_loss} "
            f"risk={c.risk} → {c.exit_why} pts={c.pts} R={c.R} "
            f"MFE={c.mfe} 1R={c.hit_1R} 2R={c.hit_2R} | {c.reason}",
            flush=True,
        )

    # --- recent window (all days in pull) ---
    all_calls = scan_session(bars, settle=True)
    all_sum = summarize(all_calls)
    # last 10 sessions only
    last10 = set(days[-10:])
    c10 = [c for c in all_calls if c.day in last10]
    s10 = summarize(c10)

    # persist today into live ledger
    ledger_meta = append_live_calls(today_calls, mark_fire=True)

    payload = {
        "desk": DESK,
        "today": today,
        "today_summary": today_sum,
        "today_calls": [c.to_dict() for c in today_calls],
        "window_days": len(days),
        "window_first": days[0],
        "window_last": days[-1],
        "window_summary": all_sum,
        "last10_summary": s10,
        "last10_calls": [c.to_dict() for c in c10],
        "ledger": ledger_meta,
        "rules": {
            "setups": ["BREAK_HOLD", "SWEEP_RECLAIM", "OR_RETEST"],
            "sl": "prev candle extreme + swing lookback −/+ buffer (not fixed pts)",
            "exit": "trail after 1R · structure fail · time cut — no fixed target",
            "max_calls_day": 4,
            "causal": True,
        },
    }
    JS.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# PA Structure Live · {today}",
        "",
        f"**Desk:** `{DESK}` · causal 1m · structure SL · no fixed ±target",
        "",
        "## Rules",
        "",
        "| Piece | Rule |",
        "|---|---|",
        "| Setups | BREAK_HOLD · SWEEP_RECLAIM · OR_RETEST |",
        "| SL | Prev candle low/high + swing lookback ±0.75 (not constant pts) |",
        "| Exit | Trail after +1R · structure fail · time cut (≤90m) |",
        "| Cap | ≤4 calls/day · 12-bar cooldown · HTF 15m align |",
        "| Causal | Closed bars only · no win lookahead |",
        "",
        f"## Today ({today})",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Calls | **{today_sum.get('n', 0)}** |",
        f"| Hit (pts>0) | **{today_sum.get('hit_pct')}%** |"
        if today_sum.get("hit_pct") is not None
        else f"| Hit (pts>0) | — |",
        f"| Avg R | {today_sum.get('avg_R')} |",
        f"| Sum pts | {today_sum.get('sum_pts')} |",
        f"| Touched 1R | {today_sum.get('hit_1R_pct')}% |",
        f"| Touched 2R | {today_sum.get('hit_2R_pct')}% |",
        "",
        "### Today calls",
        "",
        "| HM | Side | Setup | Entry | SL | Risk | Exit | Pts | R | MFE | 1R | 2R |",
        "|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|",
    ]
    # fix the hit line properly
    lines = [
        f"# PA Structure Live · {today}",
        "",
        f"**Desk:** `{DESK}` · causal 1m · structure SL · no fixed ±target",
        "",
        "## Rules",
        "",
        "| Piece | Rule |",
        "|---|---|",
        "| Setups | BREAK_HOLD · SWEEP_RECLAIM · OR_RETEST |",
        "| SL | Prev candle low/high + swing lookback ±0.75 (not constant pts) |",
        "| Exit | Trail after +1R · structure fail · time cut (≤90m) |",
        "| Cap | ≤4 calls/day · 12-bar cooldown · HTF 15m align |",
        "| Causal | Closed bars only · no win lookahead |",
        "",
        f"## Today ({today})",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Calls | **{today_sum.get('n', 0)}** |",
        f"| Hit (pts>0) | **{today_sum.get('hit_pct')}%** |"
        if today_sum.get("n")
        else "| Hit (pts>0) | — |",
        f"| Avg R | {today_sum.get('avg_R')} |",
        f"| Sum pts | {today_sum.get('sum_pts')} |",
        f"| Touched 1R | {today_sum.get('hit_1R_pct')}% |",
        f"| Touched 2R | {today_sum.get('hit_2R_pct')}% |",
        "",
        "### Today calls",
        "",
        "| HM | Side | Setup | Entry | SL | Risk | Exit | Pts | R | MFE | 1R | 2R |",
        "|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|",
    ]
    # rebuild cleanly without the ternary mess
    hit_line = (
        f"| Hit (pts>0) | **{today_sum.get('hit_pct')}%** |"
        if today_sum.get("n")
        else "| Hit (pts>0) | — |"
    )
    lines = [
        f"# PA Structure Live · {today}",
        "",
        f"**Desk:** `{DESK}` · causal 1m · structure SL · no fixed ±target",
        "",
        "## Rules",
        "",
        "| Piece | Rule |",
        "|---|---|",
        "| Setups | BREAK_HOLD · SWEEP_RECLAIM · OR_RETEST |",
        "| SL | Prev candle low/high + swing lookback ±0.75 (not constant pts) |",
        "| Exit | Trail after +1R · structure fail · time cut (≤90m) |",
        "| Cap | ≤4 calls/day · 12-bar cooldown · HTF 15m align |",
        "| Causal | Closed bars only · no win lookahead |",
        "",
        f"## Today ({today})",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Calls | **{today_sum.get('n', 0)}** |",
        hit_line,
        f"| Avg R | {today_sum.get('avg_R')} |",
        f"| Sum pts | {today_sum.get('sum_pts')} |",
        f"| Touched 1R | {today_sum.get('hit_1R_pct')}% |",
        f"| Touched 2R | {today_sum.get('hit_2R_pct')}% |",
        "",
        "### Today calls",
        "",
        "| HM | Side | Setup | Entry | SL | Risk | Exit | Pts | R | MFE | 1R | 2R |",
        "|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|",
    ]
    for c in today_calls:
        lines.append(
            f"| {c.hm} | {c.side} | {c.setup} | {c.entry} | {c.stop_loss} | {c.risk} | "
            f"{c.exit_why} | {c.pts} | {c.R} | {c.mfe} | "
            f"{'Y' if c.hit_1R else '—'} | {'Y' if c.hit_2R else '—'} |"
        )
    if not today_calls:
        lines.append("| — | — | no PA setup cleared gates | — | — | — | — | — | — | — | — | — |")

    lines += [
        "",
        "### Today call reasons",
        "",
    ]
    for c in today_calls:
        lines.append(f"- **{c.hm} {c.side} {c.setup}** — {c.reason}")

    lines += [
        "",
        f"## Recent window ({days[0]} → {days[-1]}, {len(days)} sessions)",
        "",
        "| Scope | N | Hit% | Avg R | Sum pts | 1R% | 2R% |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| Full pull | {all_sum.get('n')} | {all_sum.get('hit_pct')} | {all_sum.get('avg_R')} | "
        f"{all_sum.get('sum_pts')} | {all_sum.get('hit_1R_pct')} | {all_sum.get('hit_2R_pct')} |",
        f"| Last 10 sessions | {s10.get('n')} | {s10.get('hit_pct')} | {s10.get('avg_R')} | "
        f"{s10.get('sum_pts')} | {s10.get('hit_1R_pct')} | {s10.get('hit_2R_pct')} |",
        "",
        "### By setup (full pull)",
        "",
        "| Setup | N | Hit% |",
        "|---|---:|---:|",
    ]
    for s, st in (all_sum.get("by_setup") or {}).items():
        lines.append(f"| {s} | {st['n']} | {st['hit']} |")

    lines += [
        "",
        "## Live arming",
        "",
        f"- Ledger: `prod_live/holding_accurate/pa_structure/live_session_calls.json`",
        f"- Today rows stamped: **{ledger_meta.get('n_added')}** added "
        f"(total ledger {ledger_meta.get('n_total')})",
        "- Next open: run same evaluate on each closed 1m → notify entry + structure SL",
        "",
        "_Research desk — expect mixed accuracy; structure SL keeps loss size to prior candle._",
        "",
    ]
    MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {MD}", flush=True)
    print(f"Wrote {JS}", flush=True)
    print(f"Ledger added={ledger_meta.get('n_added')} total={ledger_meta.get('n_total')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
