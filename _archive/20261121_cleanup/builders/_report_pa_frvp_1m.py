"""Last 1 month performance · locked PA+FRVP (structure SL, trail exits).

  python -u prod_live/tests/builders/_report_pa_frvp_1m.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
]
import kite_data  # noqa: E402
from prod_live.logic import pa_structure_live as pa  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
MD = OUT / "PA_FRVP_1M_PERFORMANCE.md"
JS = OUT / "PA_FRVP_1M_PERFORMANCE.json"


def main() -> int:
    cfg = pa.load_locked_cfg()
    print(
        f"Locked cfg={cfg.name} use_frvp={cfg.use_frvp} mode={cfg.frvp_mode} "
        f"max_calls={cfg.max_calls_day}",
        flush=True,
    )
    print("Pulling NIFTY 1m · 40d (cover ~1m sessions)…", flush=True)
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=40, keep_partial=False
    )
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    days_all = sorted({str(ts.date()) for ts in bars.index})
    # last ~22 sessions ≈ 1 month trading
    month_days = days_all[-22:] if len(days_all) >= 22 else days_all
    start, end = month_days[0], month_days[-1]
    mask = bars.index.strftime("%Y-%m-%d").isin(set(month_days))
    window = bars[mask]
    print(f"Window {start} → {end} · {len(month_days)} sessions · bars={len(window)}", flush=True)

    calls = pa.scan_session(window, settle=True, cfg=cfg)
    summ = pa.summarize(calls)
    by_day: dict = defaultdict(list)
    for c in calls:
        by_day[c.day].append(c)

    day_rows = []
    for d in month_days:
        rows = by_day.get(d) or []
        st = pa.summarize(rows)
        day_rows.append(
            {
                "day": d,
                "n": st.get("n") or 0,
                "hit_pct": st.get("hit_pct"),
                "sum_pts": st.get("sum_pts") or 0,
                "avg_R": st.get("avg_R"),
                "wins": st.get("wins") or 0,
                "losses": st.get("losses") or 0,
            }
        )

    # SL anatomy
    risks = [float(c.risk) for c in calls if c.risk]
    exits = Counter(c.exit_why for c in calls)
    setups = summ.get("by_setup") or {}
    sides = Counter(c.side for c in calls)

    # structure SL check: risk varies (not constant)
    risk_unique = len(set(round(r, 1) for r in risks))

    payload = {
        "cfg_name": cfg.name,
        "use_frvp": cfg.use_frvp,
        "frvp_mode": cfg.frvp_mode,
        "max_calls_day": cfg.max_calls_day,
        "window": {"start": start, "end": end, "sessions": len(month_days)},
        "summary": summ,
        "avg_calls_per_day": round(len(calls) / max(1, len(month_days)), 2),
        "days_with_calls": sum(1 for r in day_rows if r["n"] > 0),
        "side_counts": dict(sides),
        "exit_why": dict(exits),
        "risk": {
            "avg": round(sum(risks) / len(risks), 2) if risks else None,
            "min": round(min(risks), 2) if risks else None,
            "max": round(max(risks), 2) if risks else None,
            "unique_rounded": risk_unique,
            "note": "variable = structure SL (not fixed pts)",
        },
        "by_day": day_rows,
        "calls": [c.to_dict() for c in calls],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    JS.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# PA+FRVP · last 1 month · `{cfg.name}`",
        "",
        f"**Window:** {start} → {end} ({len(month_days)} sessions) · NIFTY **1m** Kite · causal",
        "",
        "## How SL / target work",
        "",
        "| Piece | Rule |",
        "|---|---|",
        "| **Stop loss** | Structure: prev candle low/high + swing lookback ±0.75 "
        "(optional FRVP VAL/VAH bias) — **not fixed pts** |",
        "| **Target** | None fixed — trail after +1R, structure fail, or time cut |",
        f"| FRVP | `{cfg.use_frvp}` · mode=`{cfg.frvp_mode}` · OR30 POC/VAH/VAL quality |",
        f"| Cap | max {cfg.max_calls_day}/day · cooldown {cfg.cooldown_bars} |",
        "",
        "## Month summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Calls | **{summ.get('n')}** |",
        f"| Hit (pts>0) | **{summ.get('hit_pct')}%** |",
        f"| Wins / Losses | {summ.get('wins')} / {summ.get('losses')} |",
        f"| Avg R | **{summ.get('avg_R')}** |",
        f"| Sum pts | **{summ.get('sum_pts')}** |",
        f"| Avg pts/call | {summ.get('avg_pts')} |",
        f"| Touched 1R | {summ.get('hit_1R_pct')}% |",
        f"| Touched 2R | {summ.get('hit_2R_pct')}% |",
        f"| Avg calls/day | {payload['avg_calls_per_day']} |",
        f"| Days with ≥1 call | {payload['days_with_calls']} / {len(month_days)} |",
        f"| BUY / SELL | {sides.get('BUY', 0)} / {sides.get('SELL', 0)} |",
        "",
        "### Structure SL proof (variable risk)",
        "",
        f"| Risk avg | {payload['risk']['avg']} |",
        f"| Risk min–max | {payload['risk']['min']} – {payload['risk']['max']} |",
        f"| Distinct risk sizes | {risk_unique} (fixed-SL books would be ~1) |",
        "",
        "### Exits",
        "",
        "| Exit why | N |",
        "|---|---:|",
    ]
    for k, v in exits.most_common():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "### By setup",
        "",
        "| Setup | N | Hit% |",
        "|---|---:|---:|",
    ]
    for s, st in setups.items():
        lines.append(f"| {s} | {st['n']} | {st['hit']} |")

    lines += [
        "",
        "## Per day",
        "",
        "| Day | N | Hit% | W/L | Sum pts | Avg R |",
        "|---|---:|---:|---|---:|---:|",
    ]
    for r in day_rows:
        hit = r["hit_pct"] if r["n"] else "—"
        ar = r["avg_R"] if r["n"] else "—"
        lines.append(
            f"| {r['day']} | {r['n']} | {hit} | {r['wins']}/{r['losses']} | "
            f"{r['sum_pts']} | {ar} |"
        )

    lines += [
        "",
        "## All calls",
        "",
        "| Day | HM | Side | Setup | Entry | SL | Risk | Exit | Pts | R | MFE |",
        "|---|---|---|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for c in calls:
        lines.append(
            f"| {c.day} | {c.hm} | {c.side} | {c.setup} | {c.entry} | {c.stop_loss} | "
            f"{c.risk} | {c.exit_why} | {c.pts} | {c.R} | {c.mfe} |"
        )

    lines += ["", f"_Generated from locked_cfg `{cfg.name}`._", ""]
    MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"1M n={summ.get('n')} hit={summ.get('hit_pct')}% avgR={summ.get('avg_R')} "
        f"sum={summ.get('sum_pts')} cpd={payload['avg_calls_per_day']}",
        flush=True,
    )
    print(f"Wrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
