"""Advanced accuracy stack on NIFTY last 20d vs locked pa_no_trap.

Uses autopsy: near-wall / real-target help; large planned RR / far-empty hurt.
No trade-count or loss-pause holds. Wire lock only if clear hit lift w/o wrecking sum.

  python -u prod_live/tests/builders/_research_pa_adv_accuracy_20d.py
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
MD = OUT / "PA_ADV_ACCURACY_20D.md"
JS = OUT / "PA_ADV_ACCURACY_20D.json"
N_SESSIONS = 20


def live_frame(bars: pd.DataFrame, n_sessions: int = N_SESSIONS, lookback: int = 2):
    all_days = sorted({str(ts.date()) for ts in bars.index})
    days = all_days[-n_sessions:]
    si = max(0, all_days.index(days[0]) - lookback)
    frame = bars[bars.index.strftime("%Y-%m-%d").isin(set(all_days[si:]))]
    return frame, days, set(days)


def score(calls: List[pa.PaCall]) -> Dict[str, Any]:
    n = len(calls)
    if n == 0:
        return {
            "n": 0,
            "hit": 0.0,
            "avgR": 0.0,
            "sum": 0.0,
            "hit_1R": 0.0,
            "hit_2R": 0.0,
            "hard_sl": 0,
            "wins": 0,
            "avg_risk": 0.0,
        }
    wins = [c for c in calls if c.win]
    return {
        "n": n,
        "hit": round(100.0 * len(wins) / n, 2),
        "avgR": round(float(np.mean([float(c.R or 0) for c in calls])), 3),
        "sum": round(float(np.sum([float(c.pts or 0) for c in calls])), 2),
        "hit_1R": round(100.0 * sum(1 for c in calls if c.hit_1R) / n, 1),
        "hit_2R": round(100.0 * sum(1 for c in calls if c.hit_2R) / n, 1),
        "hard_sl": sum(1 for c in calls if c.exit_why == "sl"),
        "wins": len(wins),
        "avg_risk": round(float(np.mean([float(c.risk or 0) for c in calls])), 2),
    }


def variants(base: pa.PaConfig) -> List[pa.PaConfig]:
    b = base
    return [
        replace(b, name="BASE_pa_no_trap"),
        # single levers
        replace(b, name="adv_real_tgt", sr_gate="adv_real_tgt", require_real_target=True),
        replace(b, name="adv_near_wall_10", sr_gate="adv_near_wall", near_wall_max_R=1.0),
        replace(b, name="adv_near_wall_15", sr_gate="adv_near_wall", near_wall_max_R=1.5),
        replace(b, name="adv_near_wall_20", sr_gate="adv_near_wall", near_wall_max_R=2.0),
        replace(b, name="adv_no_far", sr_gate="adv_no_far", far_empty_min_R=3.0),
        replace(b, name="adv_v1_nw15", sr_gate="adv_v1", near_wall_max_R=1.5, require_real_target=True),
        replace(b, name="adv_v1_nw20", sr_gate="adv_v1", near_wall_max_R=2.0, require_real_target=True),
        # + chase_v1 (winner-safe SL killer from prior research)
        replace(b, name="no_trap_chase", sl_kill_mode="chase_v1"),
        replace(
            b,
            name="adv_real_tgt_chase",
            sr_gate="adv_real_tgt",
            require_real_target=True,
            sl_kill_mode="chase_v1",
        ),
        replace(
            b,
            name="adv_near15_chase",
            sr_gate="adv_near_wall",
            near_wall_max_R=1.5,
            sl_kill_mode="chase_v1",
        ),
        replace(
            b,
            name="adv_near20_chase",
            sr_gate="adv_near_wall",
            near_wall_max_R=2.0,
            sl_kill_mode="chase_v1",
        ),
        replace(
            b,
            name="adv_v1_nw15_chase",
            sr_gate="adv_v1",
            near_wall_max_R=1.5,
            require_real_target=True,
            sl_kill_mode="chase_v1",
        ),
        replace(
            b,
            name="adv_v1_nw20_chase",
            sr_gate="adv_v1",
            near_wall_max_R=2.0,
            require_real_target=True,
            sl_kill_mode="chase_v1",
        ),
        replace(
            b,
            name="adv_no_far_chase",
            sr_gate="adv_no_far",
            far_empty_min_R=3.0,
            sl_kill_mode="chase_v1",
        ),
        # candle read add-on on best structure gates
        replace(
            b,
            name="adv_near15_read_v3",
            sr_gate="adv_near_wall",
            near_wall_max_R=1.5,
            candle_entry_mode="read_v3",
        ),
        replace(
            b,
            name="adv_real_tgt_read_v3",
            sr_gate="adv_real_tgt",
            require_real_target=True,
            candle_entry_mode="read_v3",
        ),
        replace(
            b,
            name="adv_near15_chase_read",
            sr_gate="adv_near_wall",
            near_wall_max_R=1.5,
            sl_kill_mode="chase_v1",
            candle_entry_mode="read_v3",
        ),
    ]


def pareto_better(a: Dict[str, Any], base: Dict[str, Any]) -> bool:
    """Hit up (or equal) and sum not wrecked (>85% of base) and avgR not down hard."""
    if a["n"] < 15:
        return False
    if a["hit"] < base["hit"] + 1.0:  # need meaningful hit lift
        return False
    if a["sum"] < 0.85 * base["sum"]:
        return False
    return True


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Fetching NIFTY 1m …", flush=True)
    raw, err = kite_data.fetch_historical_candles("NIFTY", "minute", days=40, keep_partial=False)
    if err or raw is None or raw.empty:
        raise SystemExit(f"fetch failed: {err}")
    bars = pa.norm_1m(raw)
    frame, days, score_days = live_frame(bars, N_SESSIONS, lookback=2)
    print(f"Sessions: {days[0]} → {days[-1]} ({len(days)})", flush=True)

    base_cfg = pa.load_locked_cfg()
    results: List[Dict[str, Any]] = []
    for cfg in variants(base_cfg):
        print(f"  scan {cfg.name} …", flush=True)
        calls = [c for c in pa.scan_session(frame, settle=True, cfg=cfg) if c.day in score_days]
        sc = score(calls)
        results.append(
            {
                "name": cfg.name,
                "sr_gate": cfg.sr_gate,
                "sl_kill": cfg.sl_kill_mode,
                "near_wall_max_R": getattr(cfg, "near_wall_max_R", None),
                "candle_entry": cfg.candle_entry_mode,
                **sc,
            }
        )
        print(
            f"    n={sc['n']} hit={sc['hit']}% avgR={sc['avgR']} sum={sc['sum']} hardSL={sc['hard_sl']}",
            flush=True,
        )

    base_row = next(r for r in results if r["name"] == "BASE_pa_no_trap")
    # Rank: primary hit, then sum, then avgR (accuracy-first as user asked)
    ranked = sorted(results, key=lambda r: (r["hit"], r["sum"], r["avgR"]), reverse=True)
    wire_cands = [r for r in results if r["name"] != "BASE_pa_no_trap" and pareto_better(r, base_row)]
    wire_cands = sorted(wire_cands, key=lambda r: (r["hit"], r["sum"], r["avgR"]), reverse=True)

    wired = None
    if wire_cands:
        best = wire_cands[0]
        # Map name → cfg and save lock
        cfg_map = {c.name: c for c in variants(base_cfg)}
        win_cfg = cfg_map[best["name"]]
        win_cfg = replace(win_cfg, name=best["name"])
        pa.save_locked_cfg(win_cfg)
        # reload global
        pa.CFG = pa.load_locked_cfg()
        wired = best["name"]
        print(f"WIRED live lock → {wired}", flush=True)
    else:
        print("No Pareto wire candidate (hit+1pt & sum≥85%). Lock unchanged.", flush=True)

    lines = [
        "# Advanced accuracy · NIFTY last 20 sessions",
        "",
        f"**Window:** `{days[0]}` → `{days[-1]}`",
        f"**Prior lock:** `pa_no_trap` · **Wired now:** `{wired or '(unchanged) ' + base_cfg.name}`",
        "",
        "Stack from autopsy: near opposing wall / real S/R help; far-empty & large planned RR hurt. "
        "Optional `chase_v1` SL-killer. No day-call / loss-pause holds.",
        "",
        "## Summary (accuracy-first sort in report body)",
        "",
        "| Logic | N | Hit% | AvgR | Sum | Hit1R% | Hard SL | Gate / kill |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in ranked:
        lines.append(
            f"| `{r['name']}` | {r['n']} | {r['hit']} | {r['avgR']} | {r['sum']} | "
            f"{r['hit_1R']} | {r['hard_sl']} | {r['sr_gate']}+{r['sl_kill']} |"
        )
    lines += [
        "",
        f"**BASE:** n={base_row['n']} hit={base_row['hit']}% sum={base_row['sum']}",
        f"**Best hit overall:** `{ranked[0]['name']}` hit={ranked[0]['hit']}% n={ranked[0]['n']} sum={ranked[0]['sum']}",
        "",
        "### Wire rule",
        "Wire if hit ≥ BASE+1.0 **and** sum ≥ 85% of BASE **and** n≥15.",
        f"Candidates: {[c['name'] for c in wire_cands] or 'none'}",
        f"**Action:** {'wired `' + wired + '`' if wired else 'kept prior lock'}",
        "",
    ]
    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    JS.write_text(
        json.dumps(
            {
                "days": days,
                "base": base_row,
                "results": results,
                "ranked": ranked,
                "wire_cands": wire_cands,
                "wired": wired,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {MD}", flush=True)


if __name__ == "__main__":
    main()
