"""Test nifty_minute_guide on last ~1 month of NIFTY 1m sessions.

  python -u prod_live/tests/builders/_diag_nifty_minute_guide_1m.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live" / "tests" / "builders"),
    str(ROOT / "app"),
    str(ROOT / "app" / "market"),
]
import path_setup  # noqa: F401,E402

from _diag_nifty_state_conditional_1m import load_1m  # noqa: E402
from prod_live.logic.nifty_minute_guide import (  # noqa: E402
    FLAT_AT,
    LAST_ENTRY,
    MAX_RISK,
    MIN_RISK,
    PAYOFF,
    PROFILES,
    run,
    summarize,
)

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_CSV = OUT_DIR / "NIFTY_MINUTE_GUIDE_1M.csv"
OUT_CALLS = OUT_DIR / "NIFTY_MINUTE_GUIDE_1M_CALLS.csv"
OUT_MD = OUT_DIR / "NIFTY_MINUTE_GUIDE_1M.md"
OUT_JSON = OUT_DIR / "NIFTY_MINUTE_GUIDE_1M.json"
COST = 1.0
TEST_CALENDAR_DAYS = 31
WARM_SESSIONS = 80
FOCUS = "avoid_stop"


def _pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{100.0 * x:.1f}%"


def _f(x: float | None, nd: int = 2) -> str:
    if x is None:
        return "n/a"
    return f"{x:.{nd}f}"


def _pair_trades(rows: List[dict]) -> List[Dict[str, Any]]:
    trades: List[Dict[str, Any]] = []
    pending: dict | None = None
    for row in rows:
        if row["action"] in ("BUY", "SELL"):
            pending = row
            continue
        if row["action"] == "DROP" and pending is not None and row["points"] is not None:
            pts = float(row["points"])
            trades.append(
                {
                    "date": pending["date"],
                    "side": pending["direction"],
                    "entry_signal": pending["time"],
                    "entry": pending["entry"],
                    "stop": pending["stop"],
                    "target": pending["target"],
                    "score_entry": pending["score"],
                    "efficiency": pending.get("efficiency"),
                    "vwap_z": pending.get("vwap_z"),
                    "pressure": pending.get("pressure"),
                    "exit_time": row["time"],
                    "exit_reason": row["reason"],
                    "score_exit": row["score"],
                    "points": pts,
                    "net": pts - COST,
                }
            )
            pending = None
    return trades


def _profile_block(label: str, summary: dict, trades: List[dict]) -> str:
    reasons = Counter(t["exit_reason"] for t in trades)
    stops = reasons.get("stop", 0)
    stop_share = None if not trades else stops / len(trades)
    return (
        f"| {label} | {summary['closed_calls']} | {_pct(summary['hit_rate'])} | "
        f"{_f(summary['net_points'])} | {stops} ({_pct(stop_share)}) | "
        f"{reasons.get('target', 0)} | {reasons.get('score_turned', 0)} |"
    )


def main() -> int:
    raw, source, _days = load_1m(WARM_SESSIONS)
    if not raw:
        print("no 1m bars", flush=True)
        return 1

    all_dates = sorted({r["datetime"].date() for r in raw})
    hi = all_dates[-1]
    lo = hi - timedelta(days=TEST_CALENDAR_DAYS)
    test_days = [d for d in all_dates if d >= lo]
    test_set = set(test_days)
    test_raw = [r for r in raw if r["datetime"].date() in test_set]
    print(
        f"test window: {test_days[0]} → {test_days[-1]} · {len(test_days)} sessions · "
        f"{len(test_raw)} bars · source={source}",
        flush=True,
    )

    results: Dict[str, Any] = {}
    for name in ("baseline", "avoid_stop"):
        rows = run(test_raw, profile=name)
        summary = summarize(rows, cost_points=COST)
        trades = _pair_trades(rows)
        results[name] = {"rows": rows, "summary": summary, "trades": trades}
        stop_n = sum(1 for t in trades if t["exit_reason"] == "stop")
        print(
            f"profile={name} closed={summary['closed_calls']} hit={_pct(summary['hit_rate'])} "
            f"net={_f(summary['net_points'])} stops={stop_n}",
            flush=True,
        )

    focus = results[FOCUS]
    rows = focus["rows"]
    summary = focus["summary"]
    trades = focus["trades"]
    profile = PROFILES[FOCUS]

    by_day: Dict[str, List[dict]] = defaultdict(list)
    for t in trades:
        by_day[t["date"]].append(t)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)
    pd.DataFrame(trades).to_csv(OUT_CALLS, index=False)

    reason_counts = Counter(t["exit_reason"] for t in trades)
    wait_reasons = Counter(
        r["reason"] for r in rows if r["action"] == "WAIT" and r["reason"] not in ("score_flat", "too_late")
    )
    day_lines = []
    for d in sorted(by_day):
        day_trades = by_day[d]
        net = sum(t["net"] for t in day_trades)
        n_buy = sum(1 for t in day_trades if t["side"] == "buy")
        n_sell = sum(1 for t in day_trades if t["side"] == "sell")
        wins = sum(1 for t in day_trades if t["net"] > 0)
        stops = sum(1 for t in day_trades if t["exit_reason"] == "stop")
        day_lines.append(
            f"| {d} | {len(day_trades)} | {n_buy}/{n_sell} | "
            f"{wins}/{len(day_trades) - wins} | {stops} | {_f(net)} |"
        )

    show = trades[:25] + ([{"_sep": True}] if len(trades) > 35 else []) + trades[-10:]
    trade_lines = []
    for t in show:
        if t.get("_sep"):
            trade_lines.append("| … | … | … | … | … | … | … | … | … | … | … |")
            continue
        trade_lines.append(
            f"| {t['date']} | {t['side']} | {t['entry_signal'][11:16]} | "
            f"{_f(t['entry'])} | {_f(t['stop'])} | {_f(t['target'])} | "
            f"{t['score_entry']:.3f} | {t['exit_time'][11:16]} | {t['exit_reason']} | "
            f"{_f(t['points'])} | {_f(t['net'])} |"
        )
    calls_per_day = (
        None if not by_day else sum(len(v) for v in by_day.values()) / len(by_day)
    )
    stop_share = (
        None if not trades else reason_counts.get("stop", 0) / len(trades)
    )

    payload = {
        "source": source,
        "cost": COST,
        "window": {
            "lo": test_days[0].isoformat(),
            "hi": test_days[-1].isoformat(),
            "sessions": len(test_days),
        },
        "focus_profile": FOCUS,
        "profiles": {
            name: {
                "summary": results[name]["summary"],
                "stops": sum(1 for t in results[name]["trades"] if t["exit_reason"] == "stop"),
                "stop_share": (
                    None
                    if not results[name]["trades"]
                    else sum(1 for t in results[name]["trades"] if t["exit_reason"] == "stop")
                    / len(results[name]["trades"])
                ),
            }
            for name in results
        },
        "params": {
            "profile": FOCUS,
            "enter": profile.enter,
            "drop_line": profile.drop_line,
            "min_efficiency": profile.min_efficiency,
            "min_vwap_align": profile.min_vwap_align,
            "min_pressure_align": profile.min_pressure_align,
            "MIN_RISK": MIN_RISK,
            "MAX_RISK": MAX_RISK,
            "PAYOFF": PAYOFF,
            "LAST_ENTRY": str(LAST_ENTRY),
            "FLAT_AT": str(FLAT_AT),
        },
        "summary": summary,
        "wait_skip_reasons": dict(wait_reasons),
        "trades": trades,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    md = f"""# NIFTY minute guide · last 1 month (avoid_stop)

**Source:** `{source}` 1m · cost {COST}
**Window:** {test_days[0]} → {test_days[-1]} ({len(test_days)} sessions)
**Module:** `prod_live/logic/nifty_minute_guide.py`
**Default profile:** `{FOCUS}`

## Stop-avoidance logic added

Skip a score cross (WAIT) when any of these fail — autopsy of stop-outs on the raw book:

1. **efficiency ≥ {profile.min_efficiency}** — choppy path (low net/path) stopped out ~50%+
2. **VWAP side aligned** (stretch ≥ {profile.min_vwap_align}) — no fade against VWAP
3. **pressure aligned** (≥ {profile.min_pressure_align}) — candle close agrees with side
4. **|score| ≥ {profile.enter}** (raised from 0.22)

Hard stop (0.6×ATR clipped {MIN_RISK}–{MAX_RISK}) still protects open trades; we just open fewer stop-prone ones.

## Baseline vs avoid_stop

| Profile | Closed | Hit | Net | Stops (share) | Targets | Score turn |
|---|---:|---:|---:|---|---:|---:|
{_profile_block("baseline", results["baseline"]["summary"], results["baseline"]["trades"])}
{_profile_block("**avoid_stop**", summary, trades)}

## avoid_stop · summary

| Metric | Value |
|---|---|
| minutes | {summary['minutes']} |
| sessions | {summary['sessions']} |
| sessions with a call | {summary['sessions_with_a_call']} |
| BUY / SELL | {summary['buys']} / {summary['sells']} |
| closed calls | {summary['closed_calls']} |
| wins / losses | {summary.get('wins')} / {summary.get('losses')} |
| hit rate | {_pct(summary['hit_rate'])} |
| net points (after cost) | {_f(summary['net_points'])} |
| avg win / avg loss | {_f(summary.get('avg_win'))} / {_f(summary.get('avg_loss'))} |
| calls / day (avg) | {_f(calls_per_day)} |
| stop share | {_pct(stop_share)} |

### Exit reasons

| Reason | N |
|---|---:|
| stop | {reason_counts.get('stop', 0)} |
| target | {reason_counts.get('target', 0)} |
| score_turned | {reason_counts.get('score_turned', 0)} |
| session_end | {reason_counts.get('session_end', 0)} |

### Skipped entries (WAIT)

```
{dict(wait_reasons)}
```

## Calls by day

| Date | N | Buy/Sell | W/L | Stops | Net pts |
|---|---:|---|---|---:|---:|
{chr(10).join(day_lines) if day_lines else "| — | 0 | — | — | 0 | 0 |"}

## Trade log (sample)

Full log: `{OUT_CALLS.name}` ({len(trades)} rows).

| Date | Side | Signal | Entry | Stop | Target | Score | Exit | Reason | Pts | Net |
|---|---|---|---:|---:|---:|---:|---|---|---:|---:|
{chr(10).join(trade_lines) if trade_lines else "| — | — | — | — | — | — | — | — | — | — | — |"}

## Artifacts

- `{OUT_CSV.name}` — every minute row (avoid_stop)
- `{OUT_CALLS.name}` — closed trades
- `{OUT_JSON.name}` — machine summary
"""
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"wrote {OUT_MD}", flush=True)
    print(f"wrote {OUT_CALLS}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
