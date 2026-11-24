"""Accurate proven book — last 1 year test.

Uses cached dual walks:
  - 15m / 5m: stock_signal_data/fno_validate/research/_cache_dual15_dual5_10y.json
  - 10m packs: _cache_dual_packs_on_10m_1y.json

Primary accurate book = 15m proven_100, then 10m proven_100 on silent days.
Champion excluded.

  python -u prod_live/research/nifty_fno/run_proven_1y.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live" / "research" / "nifty_fno")]

from logic.proven_book import (  # noqa: E402
    build_accurate_book,
    clip_window,
    compare_books,
    filter_proven,
    first_per_day,
    summarize,
)

LEDGER = ROOT / "stock_signal_data" / "fno_validate" / "research"
CACHE_15_5 = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_10 = LEDGER / "_cache_dual_packs_on_10m_1y.json"
OUT = Path(__file__).resolve().parent / "reports"
OUT_MD = OUT / "PROVEN_ACCURATE_1Y.md"
OUT_JSON = OUT / "PROVEN_ACCURATE_1Y.json"
OUT_CSV = OUT / "PROVEN_ACCURATE_1Y_CALLS.csv"

END = "2026-11-13"
START_1Y = (pd.Timestamp(END) - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
COST = 1.0


def _pct(x):
    return "n/a" if x is None else f"{100.0 * x:.1f}%"


def _f(x, nd=2):
    return "n/a" if x is None else f"{x:.{nd}f}"


def _load():
    d = json.loads(CACHE_15_5.read_text(encoding="utf-8"))
    d10 = json.loads(CACHE_10.read_text(encoding="utf-8")) if CACHE_10.is_file() else {"dual10": {}}
    return d, d10


def main() -> int:
    if not CACHE_15_5.is_file():
        print(f"missing cache {CACHE_15_5}", flush=True)
        return 1
    d, d10 = _load()
    p15 = d["dual15"]["proven_100"]
    c15 = d["dual15"]["champion"]
    p5 = d["dual5"]["proven_100"]
    c5 = d["dual5"]["champion"]
    p10 = (d10.get("dual10") or {}).get("proven_100") or []
    c10 = (d10.get("dual10") or {}).get("champion") or []

    board = compare_books(
        proven_15m=p15,
        proven_10m=p10,
        champion_rows=c15 + c5 + c10,
        start=START_1Y,
        end=END,
    )

    # Extra reference rows
    refs = {
        "proven_5m": summarize(
            first_per_day(clip_window(filter_proven(p5), START_1Y, END))
        ),
        "champ_15m": summarize(
            first_per_day(
                [r for r in clip_window(c15, START_1Y, END) if str(r.get("track")) == "champion"]
            )
        ),
        "champ_5m": summarize(
            first_per_day(
                [r for r in clip_window(c5, START_1Y, END) if str(r.get("track")) == "champion"]
            )
        ),
        "champ_10m": summarize(
            first_per_day(
                [r for r in clip_window(c10, START_1Y, END) if str(r.get("track")) == "champion"]
            )
        ),
    }
    # proven15 + champ15 silent-day fill (reference only — not accurate book)
    p15_days = first_per_day(clip_window(filter_proven(p15), START_1Y, END))
    used = {str(r.get("day"))[:10] for r in p15_days}
    champ_fill = []
    for r in first_per_day(
        [x for x in clip_window(c15, START_1Y, END) if str(x.get("track")) == "champion"]
    ):
        if str(r.get("day"))[:10] in used:
            continue
        champ_fill.append(r)
    refs["proven15_plus_champ15"] = summarize(p15_days + champ_fill)

    accurate = board["accurate_proven"]
    rows = accurate["rows"]
    summary = accurate["summary"]

    OUT.mkdir(parents=True, exist_ok=True)
    import pandas as pd_csv

    pd_csv.DataFrame(rows).to_csv(OUT_CSV, index=False)

    def line(name, s):
        return (
            f"| {name} | {s.get('n', 0)} | {_pct(s.get('hit_rate'))} | "
            f"{s.get('wins', 0)}/{s.get('losses', 0)} | {_f(s.get('net_points'))} |"
        )

    trade_lines = []
    for r in rows:
        trade_lines.append(
            f"| {r.get('day')} | {r.get('desk')} | {r.get('decision')} | {r.get('hm')} | "
            f"{r.get('p_t1')} | {r.get('entry')} | {r.get('outcome')} | {r.get('points')} |"
        )

    desk_lines = []
    for desk, slot in (summary.get("by_desk") or {}).items():
        desk_lines.append(
            f"| {desk} | {slot['n']} | {_pct(slot.get('hit_rate'))} | {_f(slot['net'])} |"
        )

    md = f"""# NIFTY F&O accurate proven book · last 1y

**Window:** {START_1Y} → {END} · cost {COST}
**Folder:** `prod_live/research/nifty_fno`
**Rule:** 15m `proven_100` first · 10m `proven_100` fills silent days · **no champion**

## Accurate book

| Metric | Value |
|---|---|
| tickets | {summary['n']} |
| hit | {_pct(summary['hit_rate'])} |
| wins / losses | {summary['wins']} / {summary['losses']} |
| net points | {_f(summary['net_points'])} |
| sessions with call | {summary['sessions']} |

### By desk

| Desk | N | Hit | Net |
|---|---:|---:|---:|
{chr(10).join(desk_lines) if desk_lines else "| — | 0 | — | 0 |"}

## Comparison (why champion is out)

| Book | N | Hit | W/L | Net |
|---|---:|---:|---|---:|
{line("**accurate = proven15 + proven10 fill**", summary)}
{line("proven 15m only", board["proven_15m"]["summary"])}
{line("proven 10m only", board["proven_10m"]["summary"])}
{line("proven 5m only", refs["proven_5m"])}
{line("champion 15m", refs["champ_15m"])}
{line("champion 5m", refs["champ_5m"])}
{line("champion 10m", refs["champ_10m"])}
{line("proven15 + champ15 fill (not used)", refs["proven15_plus_champ15"])}

## Trade log (accurate)

| Day | Desk | Side | HM | p_t1 | Entry | Outcome | Pts |
|---|---|---|---|---:|---:|---|---:|
{chr(10).join(trade_lines) if trade_lines else "| — | — | — | — | — | — | — | — |"}

## Notes

- 5m / 10m **champion** drag accuracy — kept out of this book.
- Champion gate research: `run_champion_improve_1y.py`
- Caches: `{CACHE_15_5.name}` · `{CACHE_10.name}`
"""
    OUT_MD.write_text(md, encoding="utf-8")
    payload = {
        "window": {"start": START_1Y, "end": END},
        "accurate": summary,
        "board": {
            k: v["summary"] for k, v in board.items() if k != "window" and isinstance(v, dict) and "summary" in v
        },
        "refs": refs,
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(
        f"accurate n={summary['n']} hit={_pct(summary['hit_rate'])} "
        f"net={_f(summary['net_points'])}",
        flush=True,
    )
    print(f"wrote {OUT_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
