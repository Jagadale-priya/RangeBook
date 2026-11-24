"""Daily breakdown for research cfg adv_near15_chase_read (NIFTY last 20 sessions).

Does not change live lock.

  python -u prod_live/tests/builders/_report_pa_adv_near15_chase_read_daily.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

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
MD = OUT / "PA_ADV_NEAR15_CHASE_READ_DAILY.md"
JS = OUT / "PA_ADV_NEAR15_CHASE_READ_DAILY.json"
N_SESSIONS = 20


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Fetching NIFTY 1m …", flush=True)
    raw, err = kite_data.fetch_historical_candles("NIFTY", "minute", days=40, keep_partial=False)
    if err or raw is None or raw.empty:
        raise SystemExit(f"fetch failed: {err}")

    bars = pa.norm_1m(raw)
    all_days = sorted({str(ts.date()) for ts in bars.index})
    days = all_days[-N_SESSIONS:]
    si = max(0, all_days.index(days[0]) - 2)
    frame = bars[bars.index.strftime("%Y-%m-%d").isin(set(all_days[si:]))]
    score_days = set(days)

    live = pa.load_locked_cfg()
    cfg = replace(
        live,
        name="adv_near15_chase_read",
        sr_gate="adv_near_wall",
        near_wall_max_R=1.5,
        sl_kill_mode="chase_v1",
        candle_entry_mode="read_v3",
        candle_trail_mode="pin_protect",
        require_real_target=False,
    )
    print(
        f"scan {cfg.name} near={cfg.near_wall_max_R} kill={cfg.sl_kill_mode} candle={cfg.candle_entry_mode}",
        flush=True,
    )
    calls = [c for c in pa.scan_session(frame, settle=True, cfg=cfg) if c.day in score_days]

    by: Dict[str, List[pa.PaCall]] = {d: [] for d in days}
    for c in calls:
        by.setdefault(c.day, []).append(c)

    wins = sum(1 for c in calls if c.win)
    pts = float(np.sum([float(c.pts or 0) for c in calls])) if calls else 0.0
    Rs = [float(c.R or 0) for c in calls]
    avgR = float(np.mean(Rs)) if Rs else 0.0

    lines: List[str] = [
        "# adv_near15_chase_read · daily (NIFTY 20 sessions)",
        "",
        f"**Window:** `{days[0]}` → `{days[-1]}`",
        (
            "**Cfg:** `sr_gate=adv_near_wall` · `near_wall_max_R=1.5` · "
            "`sl_kill=chase_v1` · `candle_entry=read_v3` · `trail=pin_protect`"
        ),
        f"**Live lock unchanged:** `{live.name}` (this is research-only).",
        "",
        "## Totals",
        "",
        f"- **N={len(calls)}** hit=**{100.0 * wins / max(len(calls), 1):.2f}%** "
        f"avgR=**{avgR:.3f}** sum=**{pts:.2f}**",
        (
            f"- Hard SL={sum(1 for c in calls if c.exit_why == 'sl')} · "
            f"trail_sl={sum(1 for c in calls if c.exit_why == 'trail_sl')} · "
            f"time={sum(1 for c in calls if c.exit_why == 'time')}"
        ),
        "",
        "## Per day summary",
        "",
        "| Day | N | Hit% | Sum pts | AvgR | W/L | Hard SL | Snapshot |",
        "|---|---:|---:|---:|---:|---|---:|---|",
    ]

    daily_json: List[Dict[str, Any]] = []
    for d in days:
        cs = by.get(d, [])
        if not cs:
            lines.append(f"| {d} | 0 | — | 0 | — | — | 0 | — |")
            daily_json.append({"day": d, "n": 0, "hit": None, "sum": 0, "avgR": None, "calls": []})
            continue
        w = sum(1 for c in cs if c.win)
        s = float(np.sum([float(c.pts or 0) for c in cs]))
        ar = float(np.mean([float(c.R or 0) for c in cs]))
        hsl = sum(1 for c in cs if c.exit_why == "sl")
        snap = "; ".join(
            f"{c.hm} {c.side[0]}/{c.setup} R={float(c.R or 0):+.2f} {c.exit_why}" for c in cs
        )
        lines.append(
            f"| {d} | {len(cs)} | {100.0 * w / len(cs):.1f} | {s:.2f} | {ar:.3f} | "
            f"{w}/{len(cs) - w} | {hsl} | {snap} |"
        )
        daily_json.append(
            {
                "day": d,
                "n": len(cs),
                "hit": round(100.0 * w / len(cs), 1),
                "sum": round(s, 2),
                "avgR": round(ar, 3),
                "wins": w,
                "hard_sl": hsl,
                "calls": [
                    {
                        "hm": c.hm,
                        "side": c.side,
                        "setup": c.setup,
                        "entry": c.entry,
                        "sl": c.stop_loss,
                        "risk": c.risk,
                        "pts": c.pts,
                        "R": c.R,
                        "win": c.win,
                        "exit": c.exit_why,
                        "hit_1R": c.hit_1R,
                        "hit_2R": c.hit_2R,
                        "reason": c.reason,
                    }
                    for c in cs
                ],
            }
        )

    lines += ["", "## Call detail by day", ""]
    for block in daily_json:
        lines.append(f"### {block['day']}  (n={block['n']})")
        if not block["calls"]:
            lines.append("_No trades_")
            lines.append("")
            continue
        lines.append("| Time | Side | Setup | Entry | SL | Risk | Pts | R | Exit | 1R | Why |")
        lines.append("|---|---|---|---:|---:|---:|---:|---:|---|---|---|")
        for c in block["calls"]:
            why = (c.get("reason") or "")[:80].replace("|", "/")
            lines.append(
                f"| {c['hm']} | {c['side']} | {c['setup']} | {float(c['entry']):.1f} | "
                f"{float(c['sl']):.1f} | {float(c['risk']):.1f} | {float(c['pts'] or 0):+.1f} | "
                f"{float(c['R'] or 0):+.3f} | {c['exit']} | {c['hit_1R']} | {why} |"
            )
        lines.append("")

    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    JS.write_text(
        json.dumps(
            {
                "cfg": {
                    "name": cfg.name,
                    "sr_gate": cfg.sr_gate,
                    "near_wall_max_R": cfg.near_wall_max_R,
                    "sl_kill_mode": cfg.sl_kill_mode,
                    "candle_entry_mode": cfg.candle_entry_mode,
                },
                "live_lock": live.name,
                "days": days,
                "totals": {
                    "n": len(calls),
                    "hit": round(100.0 * wins / max(len(calls), 1), 2),
                    "sum": round(pts, 2),
                    "avgR": round(avgR, 3),
                },
                "daily": daily_json,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {MD}", flush=True)
    print(f"totals n={len(calls)} hit={100.0 * wins / max(len(calls), 1):.2f}% sum={pts:.2f}", flush=True)


if __name__ == "__main__":
    main()
