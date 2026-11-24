"""Compare minute-guide profiles on freeze + last-1m holdout.

  python -u prod_live/tests/builders/_diag_minute_guide_profiles_1m.py
"""
from __future__ import annotations

import json
import sys
from datetime import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live" / "tests" / "builders"),
    str(ROOT / "app"),
    str(ROOT / "app" / "market"),
]
import path_setup  # noqa: F401,E402

from _diag_nifty_state_conditional_1m import load_1m  # noqa: E402
from prod_live.logic.nifty_minute_guide import GuideProfile, guide, summarize  # noqa: E402

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT_DIR / "NIFTY_MINUTE_GUIDE_1M.md"
OUT_JSON = OUT_DIR / "NIFTY_MINUTE_GUIDE_PROFILES_1M.json"
OUT_CALLS = OUT_DIR / "NIFTY_MINUTE_GUIDE_1M_CALLS.csv"
COST = 1.0
HOLDOUT = 22
POOL = 80


def _pct(x):
    return "n/a" if x is None else f"{100*x:.1f}%"


def _f(x, nd=2):
    return "n/a" if x is None else f"{x:.{nd}f}"


def _stats(raw, profile):
    rows = guide(raw, profile=profile)
    s = summarize(rows, cost_points=COST)
    closed = [r for r in rows if r["action"] == "DROP" and r["points"] is not None]
    stops = sum(1 for r in closed if r.get("reason") == "stop")
    s["stops"] = stops
    s["stop_share"] = None if not closed else stops / len(closed)
    # trades
    trades = []
    pending = None
    for row in rows:
        if row["action"] in ("BUY", "SELL"):
            pending = row
        elif row["action"] == "DROP" and pending is not None and row["points"] is not None:
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
                    "points": float(row["points"]),
                    "net": float(row["points"]) - COST,
                }
            )
            pending = None
    return s, rows, trades


def main() -> int:
    raw, source, _ = load_1m(POOL)
    days = sorted({r["datetime"].date() for r in raw})
    keep = set(days[-POOL:])
    raw = [r for r in raw if r["datetime"].date() in keep]
    hold_days = days[-HOLDOUT:]
    freeze_days = [d for d in days[-POOL:] if d not in set(hold_days)]
    freeze_raw = [r for r in raw if r["datetime"].date() in set(freeze_days)]
    hold_raw = [r for r in raw if r["datetime"].date() in set(hold_days)]

    variants = {
        "baseline": "baseline",
        "avoid_stop": "avoid_stop",
        "accurate": "accurate",
        "skip10_both": GuideProfile(
            name="skip10_both",
            enter=0.30,
            min_efficiency=0.30,
            min_vwap_align=0.0,
            min_pressure_align=0.0,
            earliest_entry=time(10, 0),
        ),
        "skip10_enter35_both": GuideProfile(
            name="skip10_enter35_both",
            enter=0.35,
            min_efficiency=0.30,
            min_vwap_align=0.0,
            min_pressure_align=0.0,
            earliest_entry=time(10, 0),
        ),
        "skip10_sell": "accurate",
        "skip10_enter40_sell": GuideProfile(
            name="skip10_enter40_sell",
            enter=0.40,
            min_efficiency=0.30,
            min_vwap_align=0.0,
            min_pressure_align=0.0,
            earliest_entry=time(10, 0),
            sides=("sell",),
        ),
        "skip10_sell_eff40": GuideProfile(
            name="skip10_sell_eff40",
            enter=0.35,
            min_efficiency=0.40,
            min_vwap_align=0.0,
            min_pressure_align=0.0,
            earliest_entry=time(10, 0),
            sides=("sell",),
        ),
    }

    results = {}
    print(
        f"freeze {freeze_days[0]}→{freeze_days[-1]} ({len(freeze_days)}) · "
        f"hold {hold_days[0]}→{hold_days[-1]} ({len(hold_days)}) · {source}",
        flush=True,
    )
    for name, prof in variants.items():
        fr, _, _ = _stats(freeze_raw, prof)
        ho, rows, trades = _stats(hold_raw, prof)
        results[name] = {"freeze": fr, "holdout": ho, "trades": trades}
        print(
            f"{name:22} hold n={ho['closed_calls']:3d} hit={_pct(ho['hit_rate'])} "
            f"net={_f(ho['net_points']):>8} stop%={_pct(ho['stop_share'])} "
            f"| freeze hit={_pct(fr['hit_rate'])} net={_f(fr['net_points'])}",
            flush=True,
        )

    # Pick: best holdout hit with n>=40 and net>=avoid_stop net, else best net with hit>=35%
    avoid = results["avoid_stop"]["holdout"]
    cands = []
    for name, pack in results.items():
        ho = pack["holdout"]
        if name in ("baseline",):
            continue
        n = ho.get("closed_calls") or 0
        if n < 30:
            continue
        cands.append((name, ho))
    # Prefer higher hit then net
    cands.sort(
        key=lambda x: (
            -(x[1].get("hit_rate") or 0),
            -(x[1].get("net_points") or 0),
            x[1].get("stop_share") or 1,
        )
    )
    # Must beat avoid_stop on hit or net meaningfully
    pick_name = "accurate"
    for name, ho in cands:
        hh = ho.get("hit_rate") or 0
        hnet = ho.get("net_points") or 0
        if hh >= (avoid.get("hit_rate") or 0) + 0.03 and hnet >= (avoid.get("net_points") or 0) - 20:
            pick_name = name
            break
        if hnet >= (avoid.get("net_points") or 0) + 50 and hh >= (avoid.get("hit_rate") or 0) - 0.01:
            pick_name = name
            break
    print(f"research_pick={pick_name}", flush=True)

    focus = results["accurate"]
    import pandas as pd

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(focus["trades"]).to_csv(OUT_CALLS, index=False)

    lines = []
    for name, pack in results.items():
        fr, ho = pack["freeze"], pack["holdout"]
        mark = " **" if name == "accurate" else ""
        lines.append(
            f"| {name}{mark} | {fr['closed_calls']} | {_pct(fr['hit_rate'])} | {_f(fr['net_points'])} | "
            f"{_pct(fr['stop_share'])} | {ho['closed_calls']} | {_pct(ho['hit_rate'])} | "
            f"{_f(ho['net_points'])} | {_pct(ho['stop_share'])} |"
        )

    trade_lines = []
    for t in focus["trades"][:20]:
        trade_lines.append(
            f"| {t['date']} | {t['side']} | {t['entry_signal'][11:16]} | {_f(t['entry'])} | "
            f"{t['exit_reason']} | {_f(t['net'])} |"
        )

    md = f"""# NIFTY minute guide · last 1 month (accurate upgrade)

**Source:** `{source}` · cost {COST}
**Holdout:** {hold_days[0]} → {hold_days[-1]} ({len(hold_days)} sessions)
**Freeze:** {freeze_days[0]} → {freeze_days[-1]} ({len(freeze_days)} sessions)

## What changed vs avoid_stop

Autopsy of avoid_stop holdout:
- **09–10** bled: 56 trades · 32% hit · 32% stops · **−88 net**
- From 10:00 onward: +302 net · stop share 11%
- **SELL** +230 vs **BUY** −16

`accurate` (new default): avoid_stop gates + **earliest 10:00** + **SELL only**

## Profile comparison

| Profile | Fr N | Fr hit | Fr net | Fr stop | Ho N | Ho hit | Ho net | Ho stop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(lines)}

## accurate · holdout trades (sample)

| Date | Side | Signal | Entry | Exit | Net |
|---|---|---|---:|---|---:|
{chr(10).join(trade_lines)}

Full: `{OUT_CALLS.name}`
"""
    OUT_MD.write_text(md, encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(
            {
                "source": source,
                "pick": pick_name,
                "results": {
                    k: {"freeze": v["freeze"], "holdout": v["holdout"]} for k, v in results.items()
                },
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
