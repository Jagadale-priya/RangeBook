"""RESEARCH — PA_RR_ACCURATE vs locked pa_no_trap on NIFTY last 20 sessions.

No trade-count / loss-pause holds. Gate = honest R:R (real opposing S/R + min_rr).
Does NOT overwrite locked_cfg.

  python -u prod_live/tests/builders/_research_pa_rr_accurate_20d.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

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
MD = OUT / "PA_RR_ACCURATE_20D.md"
JS = OUT / "PA_RR_ACCURATE_20D.json"
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
            "avg_risk": 0.0,
            "hit_1R": 0.0,
            "hit_2R": 0.0,
            "wins": 0,
            "hard_sl": 0,
            "trail_sl": 0,
            "time": 0,
            "by_day": {},
            "setups": {},
            "exits": {},
        }
    wins = [c for c in calls if c.win]
    Rs = [float(c.R or 0) for c in calls]
    pts = [float(c.pts or 0) for c in calls]
    risks = [float(c.risk or 0) for c in calls]
    by_day: Dict[str, Dict[str, Any]] = {}
    for c in calls:
        d = by_day.setdefault(c.day, {"n": 0, "wins": 0, "sum": 0.0, "Rs": []})
        d["n"] += 1
        d["wins"] += int(bool(c.win))
        d["sum"] += float(c.pts or 0)
        d["Rs"].append(float(c.R or 0))
    for d, v in by_day.items():
        v["hit"] = round(100.0 * v["wins"] / v["n"], 1) if v["n"] else 0.0
        v["avgR"] = round(float(np.mean(v["Rs"])), 3) if v["Rs"] else 0.0
        v["sum"] = round(v["sum"], 2)
        del v["Rs"]
    return {
        "n": n,
        "hit": round(100.0 * len(wins) / n, 2),
        "avgR": round(float(np.mean(Rs)), 3),
        "sum": round(float(np.sum(pts)), 2),
        "avg_risk": round(float(np.mean(risks)), 2),
        "hit_1R": round(100.0 * sum(1 for c in calls if c.hit_1R) / n, 1),
        "hit_2R": round(100.0 * sum(1 for c in calls if c.hit_2R) / n, 1),
        "wins": len(wins),
        "hard_sl": sum(1 for c in calls if c.exit_why == "sl"),
        "trail_sl": sum(1 for c in calls if c.exit_why == "trail_sl"),
        "time": sum(1 for c in calls if c.exit_why == "time"),
        "by_day": dict(sorted(by_day.items())),
        "setups": dict(Counter(c.setup for c in calls)),
        "exits": dict(Counter(c.exit_why for c in calls)),
    }


def planned_rr_stats(calls: List[pa.PaCall], frame: pd.DataFrame, cfg: pa.PaConfig) -> Dict[str, Any]:
    """Recompute honest planned R:R at entry for taken calls."""
    if not calls:
        return {"n": 0}
    work = pa.norm_1m(frame)
    o = work["Open"].values
    h = work["High"].values
    l = work["Low"].values
    c = work["Close"].values
    atr = pa.atr14(h, l, c)
    idx = work.index
    hm_to_i = {}
    for i in range(len(work)):
        hm_to_i[(pa._day(idx[i]), pa._hm(idx[i]))] = i

    rows = []
    for call in calls:
        i = hm_to_i.get((call.day, call.hm))
        if i is None:
            continue
        sr = pa.build_sr_map(o, h, l, c, atr, idx, i, lookback_days=cfg.sr_lookback_days)
        rr_syn = pa.reward_risk(call.side, float(call.entry), float(call.stop_loss), sr, require_real_target=False)
        rr_real = pa.reward_risk(call.side, float(call.entry), float(call.stop_loss), sr, require_real_target=True)
        rows.append(
            {
                "day": call.day,
                "hm": call.hm,
                "side": call.side,
                "win": bool(call.win),
                "R_realized": float(call.R or 0),
                "pts": float(call.pts or 0),
                "risk": float(call.risk or 0),
                "rr_synth": float(rr_syn["rr"]),
                "rr_real": float(rr_real["rr"]) if rr_real.get("real_target") else None,
                "has_real_tgt": bool(rr_real.get("real_target")),
                "tgt": rr_real.get("target"),
                "exit": call.exit_why,
                "setup": call.setup,
            }
        )
    if not rows:
        return {"n": 0}
    with_real = [r for r in rows if r["has_real_tgt"]]
    return {
        "n": len(rows),
        "pct_real_target": round(100.0 * len(with_real) / len(rows), 1),
        "avg_rr_synth": round(float(np.mean([r["rr_synth"] for r in rows])), 3),
        "avg_rr_real": round(float(np.mean([r["rr_real"] for r in with_real])), 3) if with_real else None,
        "wins_avg_rr_real": round(
            float(np.mean([r["rr_real"] for r in with_real if r["win"] and r["rr_real"] is not None])), 3
        )
        if any(r["win"] and r["rr_real"] is not None for r in with_real)
        else None,
        "loss_avg_rr_real": round(
            float(np.mean([r["rr_real"] for r in with_real if (not r["win"]) and r["rr_real"] is not None])), 3
        )
        if any((not r["win"]) and r["rr_real"] is not None for r in with_real)
        else None,
        "rows": rows,
    }


def variants(base: pa.PaConfig) -> List[pa.PaConfig]:
    """R:R-accurate overlays — no call-cap / pause changes."""
    return [
        replace(base, name="BASE_pa_no_trap"),
        replace(
            base,
            name="rr_acc_15",
            sr_gate="rr_accurate",
            require_real_target=True,
            min_rr=1.5,
            candle_trail_mode="pin_protect",
        ),
        replace(
            base,
            name="rr_acc_18",
            sr_gate="rr_accurate",
            require_real_target=True,
            min_rr=1.8,
            candle_trail_mode="pin_protect",
        ),
        replace(
            base,
            name="rr_acc_20",
            sr_gate="rr_accurate",
            require_real_target=True,
            min_rr=2.0,
            candle_trail_mode="pin_protect",
        ),
        replace(
            base,
            name="rr_acc_25",
            sr_gate="rr_accurate",
            require_real_target=True,
            min_rr=2.5,
            candle_trail_mode="pin_protect",
        ),
        # no_trap + enforce min_rr with real target (same gate path)
        replace(
            base,
            name="no_trap_plus_rr15_real",
            sr_gate="rr_accurate",
            require_real_target=True,
            min_rr=1.5,
        ),
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Fetching NIFTY 1m …", flush=True)
    raw, err = kite_data.fetch_historical_candles("NIFTY", "minute", days=40, keep_partial=False)
    if err or raw is None or raw.empty:
        raise SystemExit(f"fetch failed: {err}")
    bars = pa.norm_1m(raw)
    frame, days, score_days = live_frame(bars, N_SESSIONS, lookback=2)
    print(f"Sessions: {days[0]} → {days[-1]} ({len(days)} days)", flush=True)

    base = pa.load_locked_cfg()
    results: List[Dict[str, Any]] = []
    call_dumps: Dict[str, List[Dict[str, Any]]] = {}

    for cfg in variants(base):
        print(f"  scan {cfg.name} …", flush=True)
        all_calls = pa.scan_session(frame, settle=True, cfg=cfg)
        calls = [c for c in all_calls if c.day in score_days]
        sc = score(calls)
        rr_st = planned_rr_stats(calls, frame, cfg)
        row = {"name": cfg.name, "cfg": {"sr_gate": cfg.sr_gate, "min_rr": cfg.min_rr, "require_real_target": cfg.require_real_target}, **sc, "planned_rr": {k: v for k, v in rr_st.items() if k != "rows"}}
        results.append(row)
        call_dumps[cfg.name] = [
            {
                "day": c.day,
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
            for c in calls
        ]
        print(
            f"    n={sc['n']} hit={sc['hit']}% avgR={sc['avgR']} sum={sc['sum']} "
            f"hit1R={sc['hit_1R']}% hardSL={sc['hard_sl']}",
            flush=True,
        )

    base_row = next(r for r in results if r["name"] == "BASE_pa_no_trap")
    lines = [
        "# PA R:R Accurate · NIFTY last 20 sessions",
        "",
        f"**Window:** `{days[0]}` → `{days[-1]}` ({len(days)} sessions)",
        f"**Path:** causal `scan_session` 1m (same as live). **Live lock unchanged:** `{base.name}`.",
        "",
        "Gate = trap block + **real opposing S/R target** + `min_rr`. No day-call caps / loss pauses added.",
        "",
        "## Summary",
        "",
        "| Logic | N | Hit% | AvgR | Sum pts | Avg risk | Hit1R% | Hit2R% | Hard SL | Trail SL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| `{r['name']}` | {r['n']} | {r['hit']} | {r['avgR']} | {r['sum']} | "
            f"{r['avg_risk']} | {r['hit_1R']} | {r['hit_2R']} | {r['hard_sl']} | {r['trail_sl']} |"
        )

    lines += ["", "## Planned R:R quality (at entry)", ""]
    lines.append("| Logic | % with real tgt | Avg RR synth | Avg RR real | Wins RR real | Loss RR real |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for r in results:
        p = r.get("planned_rr") or {}
        lines.append(
            f"| `{r['name']}` | {p.get('pct_real_target')} | {p.get('avg_rr_synth')} | "
            f"{p.get('avg_rr_real')} | {p.get('wins_avg_rr_real')} | {p.get('loss_avg_rr_real')} |"
        )

    # Daily for best rr_acc vs base
    best = max(
        [r for r in results if r["name"].startswith("rr_acc")],
        key=lambda r: (r["hit"], r["sum"], r["avgR"]),
        default=results[0],
    )
    lines += ["", f"## Daily — BASE vs best (`{best['name']}`)", ""]
    lines.append("| Day | BASE n | BASE hit | BASE sum | BEST n | BEST hit | BEST sum |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for d in days:
        b = (base_row.get("by_day") or {}).get(d, {})
        k = (best.get("by_day") or {}).get(d, {})
        lines.append(
            f"| {d} | {b.get('n', 0)} | {b.get('hit', '-')} | {b.get('sum', 0)} | "
            f"{k.get('n', 0)} | {k.get('hit', '-')} | {k.get('sum', 0)} |"
        )

    lines += [
        "",
        "## Verdict",
        "",
        f"- BASE (`pa_no_trap`): n={base_row['n']} hit={base_row['hit']}% avgR={base_row['avgR']} sum={base_row['sum']}",
        f"- Best R:R-accurate by hit then sum: `{best['name']}` → n={best['n']} hit={best['hit']}% avgR={best['avgR']} sum={best['sum']}",
        "",
        "Live lock **not** changed. Wire only if R:R-accurate clearly lifts hit and avgR without wrecking sum.",
        "",
    ]
    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    JS.write_text(
        json.dumps(
            {
                "days": days,
                "live_lock": base.name,
                "results": results,
                "calls": call_dumps,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote {MD}", flush=True)
    print(f"Wrote {JS}", flush=True)


if __name__ == "__main__":
    main()
