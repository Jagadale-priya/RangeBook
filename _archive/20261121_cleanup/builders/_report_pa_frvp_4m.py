"""Last 4 months performance · locked PA+FRVP (same as live session logic).

Holds locked_cfg untouched. Same rules as 1m report, longer window.

  python -u prod_live/tests/builders/_report_pa_frvp_4m.py
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
MD = OUT / "PA_FRVP_4M_PERFORMANCE.md"
JS = OUT / "PA_FRVP_4M_PERFORMANCE.json"

# ~4 months trading sessions
N_SESSIONS = 85
PULL_DAYS = 140


def main() -> int:
    cfg = pa.load_locked_cfg()
    print(
        f"LOCKED (unchanged) cfg={cfg.name} frvp={cfg.use_frvp}/{cfg.frvp_mode} "
        f"max_calls={cfg.max_calls_day}",
        flush=True,
    )
    print(f"Pulling NIFTY 1m · {PULL_DAYS}d …", flush=True)
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=PULL_DAYS, keep_partial=False
    )
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    days_all = sorted({str(ts.date()) for ts in bars.index})
    month_days = days_all[-N_SESSIONS:] if len(days_all) >= N_SESSIONS else days_all
    start, end = month_days[0], month_days[-1]
    window = bars[bars.index.strftime("%Y-%m-%d").isin(set(month_days))]
    print(
        f"Window {start} → {end} · {len(month_days)} sessions · bars={len(window)}",
        flush=True,
    )

    print("Scanning locked live logic…", flush=True)
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

    # monthly buckets
    by_month: dict = defaultdict(list)
    for c in calls:
        by_month[c.day[:7]].append(c)
    month_rows = []
    for m in sorted(by_month.keys()):
        st = pa.summarize(by_month[m])
        month_rows.append({"month": m, **st, "n_days": len({c.day for c in by_month[m]})})

    risks = [float(c.risk) for c in calls if c.risk]
    exits = Counter(c.exit_why for c in calls)
    sides = Counter(c.side for c in calls)
    setups = summ.get("by_setup") or {}
    risk_unique = len(set(round(r, 1) for r in risks))
    cpd = round(len(calls) / max(1, len(month_days)), 2)

    # last-1m slice inside 4m for comparison
    last22 = set(month_days[-22:]) if len(month_days) >= 22 else set(month_days)
    c1 = [c for c in calls if c.day in last22]
    s1 = pa.summarize(c1)

    payload = {
        "cfg_name": cfg.name,
        "locked_untouched": True,
        "use_frvp": cfg.use_frvp,
        "frvp_mode": cfg.frvp_mode,
        "max_calls_day": cfg.max_calls_day,
        "window": {"start": start, "end": end, "sessions": len(month_days)},
        "summary": summ,
        "last_1m_inside": s1,
        "avg_calls_per_day": cpd,
        "days_with_calls": sum(1 for r in day_rows if r["n"] > 0),
        "side_counts": dict(sides),
        "exit_why": dict(exits),
        "risk": {
            "avg": round(sum(risks) / len(risks), 2) if risks else None,
            "min": round(min(risks), 2) if risks else None,
            "max": round(max(risks), 2) if risks else None,
            "unique_rounded": risk_unique,
        },
        "by_month": month_rows,
        "by_day": day_rows,
        "calls": [c.to_dict() for c in calls],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    JS.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# PA+FRVP · last 4 months · `{cfg.name}` (live logic held)",
        "",
        f"**Window:** {start} → {end} ({len(month_days)} sessions) · NIFTY **1m** · causal",
        "",
        "Same locked live rules: structure SL · trail after 1R · FRVP vah_break · no fixed target.",
        "**No OR_RETEST drop / no extra indicator filters** — logic held as-is.",
        "",
        "## 4-month summary",
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
        f"| Avg calls/day | {cpd} |",
        f"| Days with ≥1 call | {payload['days_with_calls']} / {len(month_days)} |",
        f"| BUY / SELL | {sides.get('BUY', 0)} / {sides.get('SELL', 0)} |",
        "",
        "### vs last 1m (inside same run)",
        "",
        f"| | Last 1m | **Full 4m** |",
        f"|---|---|---|",
        f"| N | {s1.get('n')} | **{summ.get('n')}** |",
        f"| Hit% | {s1.get('hit_pct')} | **{summ.get('hit_pct')}** |",
        f"| Avg R | {s1.get('avg_R')} | **{summ.get('avg_R')}** |",
        f"| Sum pts | {s1.get('sum_pts')} | **{summ.get('sum_pts')}** |",
        "",
        "### Structure SL",
        "",
        f"| Risk avg / min–max | {payload['risk']['avg']} / {payload['risk']['min']}–{payload['risk']['max']} |",
        f"| Distinct risk sizes | {risk_unique} |",
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
        "## By calendar month",
        "",
        "| Month | N | Hit% | Avg R | Sum pts | Days w/ calls |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in month_rows:
        lines.append(
            f"| {r['month']} | {r.get('n')} | {r.get('hit_pct')} | {r.get('avg_R')} | "
            f"{r.get('sum_pts')} | {r.get('n_days')} |"
        )

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
    lines += ["", f"_Locked `{cfg.name}` held — live-ready._", ""]
    MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"4M n={summ.get('n')} hit={summ.get('hit_pct')}% avgR={summ.get('avg_R')} "
        f"sum={summ.get('sum_pts')} cpd={cpd}",
        flush=True,
    )
    print(
        f"1M-inside n={s1.get('n')} hit={s1.get('hit_pct')}% sum={s1.get('sum_pts')}",
        flush=True,
    )
    print(f"Wrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
