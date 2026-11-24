"""Deep research: maximize points AND accuracy from pa_only live-path base.

Primary score window = last 6m (126 sessions). Holdout = last 2 months vs prior 4m.
Same causal 1m scan_session as Option Blue. Does not overwrite live lock unless winner clear.

  python -u prod_live/tests/builders/_research_pa_max_points_accuracy.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
]
import kite_data  # noqa: E402
from prod_live.logic import pa_structure_live as pa  # noqa: E402
from prod_live.tests.builders._research_pa_held_logics_long import (  # noqa: E402
    _install_sr_cache,
    monthly_chunks,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
MD = OUT / "PA_MAX_POINTS_ACCURACY_RESEARCH.md"
JS = OUT / "PA_MAX_POINTS_ACCURACY_RESEARCH.json"


def pa_only() -> pa.PaConfig:
    return pa.PaConfig(
        name="pa_only",
        use_frvp=False,
        sr_gate="none",
        sl_kill_mode="none",
        candle_entry_mode="none",
        candle_trail_mode="base",
        allow_or_retest=True,
        allow_break=True,
        allow_sweep=True,
        trade_lo=9 * 60 + 30,
        trade_hi=14 * 60 + 45,
        max_calls_day=12,
        cooldown_bars=10,
        body_min=0.55,
        or_side_align=True,
        min_risk=3.0,
        max_risk=22.0,
        side_flip_cooldown=12,
        trail_arm_R=1.0,
    )


def variants() -> List[pa.PaConfig]:
    b = pa_only()
    return [
        b,
        # trail
        replace(b, name="pa_pin", candle_trail_mode="pin_protect"),
        # drop OR (accuracy lift historically)
        replace(b, name="pa_no_or", allow_or_retest=False),
        replace(b, name="pa_no_or_pin", allow_or_retest=False, candle_trail_mode="pin_protect"),
        # candles light
        replace(b, name="pa_no_exhaust", candle_entry_mode="no_exhaust"),
        replace(b, name="pa_no_exhaust_no_or", candle_entry_mode="no_exhaust", allow_or_retest=False),
        replace(b, name="pa_read_v3", candle_entry_mode="read_v3", candle_trail_mode="pin_protect"),
        replace(
            b,
            name="pa_read_v3_no_or",
            candle_entry_mode="read_v3",
            candle_trail_mode="pin_protect",
            allow_or_retest=False,
        ),
        # FRVP classic
        replace(
            b,
            name="frvp_vah",
            use_frvp=True,
            frvp_mode="vah_break",
            frvp_anchor="or30",
            frvp_prefer_sl=True,
        ),
        replace(
            b,
            name="frvp_vah_no_or",
            use_frvp=True,
            frvp_mode="vah_break",
            frvp_anchor="or30",
            frvp_prefer_sl=True,
            allow_or_retest=False,
        ),
        replace(
            b,
            name="frvp_no_ex_pin",
            use_frvp=True,
            frvp_mode="vah_break",
            frvp_anchor="or30",
            frvp_prefer_sl=True,
            candle_entry_mode="no_exhaust",
            candle_trail_mode="pin_protect",
        ),
        replace(
            b,
            name="frvp_no_ex_no_or_pin",
            use_frvp=True,
            frvp_mode="vah_break",
            frvp_anchor="or30",
            frvp_prefer_sl=True,
            candle_entry_mode="no_exhaust",
            candle_trail_mode="pin_protect",
            allow_or_retest=False,
        ),
        # soft SR
        replace(b, name="pa_no_trap", sr_gate="no_trap", candle_trail_mode="pin_protect"),
        replace(
            b,
            name="pa_no_trap_no_or",
            sr_gate="no_trap",
            allow_or_retest=False,
            candle_trail_mode="pin_protect",
        ),
        # mid window
        replace(b, name="pa_mid", trade_lo=10 * 60, trade_hi=14 * 60, allow_or_retest=False),
        replace(
            b,
            name="pa_mid_pin",
            trade_lo=10 * 60,
            trade_hi=14 * 60,
            allow_or_retest=False,
            candle_trail_mode="pin_protect",
        ),
        replace(
            b,
            name="pa_mid_no_ex",
            trade_lo=10 * 60,
            trade_hi=14 * 60,
            allow_or_retest=False,
            candle_entry_mode="no_exhaust",
            candle_trail_mode="pin_protect",
        ),
        # body / cooldown
        replace(b, name="pa_body60", body_min=0.60),
        replace(b, name="pa_body60_no_or", body_min=0.60, allow_or_retest=False),
        replace(b, name="pa_cd14", cooldown_bars=14),
        replace(b, name="pa_cd14_no_or", cooldown_bars=14, allow_or_retest=False),
        # SL kill on volume base
        replace(b, name="pa_slkill", sl_kill_mode="chase_v1", candle_trail_mode="pin_protect"),
        replace(
            b,
            name="pa_no_or_slkill",
            allow_or_retest=False,
            sl_kill_mode="chase_v1",
            candle_trail_mode="pin_protect",
        ),
        replace(
            b,
            name="pa_no_ex_no_or_slkill",
            candle_entry_mode="no_exhaust",
            allow_or_retest=False,
            sl_kill_mode="chase_v1",
            candle_trail_mode="pin_protect",
        ),
        replace(
            b,
            name="frvp_no_or_slkill",
            use_frvp=True,
            frvp_mode="vah_break",
            frvp_anchor="or30",
            frvp_prefer_sl=True,
            allow_or_retest=False,
            sl_kill_mode="chase_v1",
            candle_trail_mode="pin_protect",
        ),
        replace(
            b,
            name="frvp_no_ex_no_or_slkill",
            use_frvp=True,
            frvp_mode="vah_break",
            frvp_anchor="or30",
            frvp_prefer_sl=True,
            candle_entry_mode="no_exhaust",
            allow_or_retest=False,
            sl_kill_mode="chase_v1",
            candle_trail_mode="pin_protect",
        ),
        # hybrid point+acc candidates
        replace(
            b,
            name="hyb_A",
            allow_or_retest=False,
            candle_entry_mode="no_exhaust",
            candle_trail_mode="pin_protect",
            trade_lo=9 * 60 + 45,
            trade_hi=14 * 60 + 15,
        ),
        replace(
            b,
            name="hyb_B",
            use_frvp=True,
            frvp_mode="vah_break",
            frvp_anchor="or30",
            frvp_prefer_sl=True,
            allow_or_retest=False,
            candle_entry_mode="no_exhaust",
            candle_trail_mode="pin_protect",
            trade_lo=9 * 60 + 45,
        ),
        replace(
            b,
            name="hyb_C",
            allow_or_retest=False,
            candle_entry_mode="no_exhaust",
            candle_trail_mode="pin_protect",
            sl_kill_mode="chase_v1",
            cooldown_bars=12,
        ),
        replace(
            b,
            name="hyb_D",
            sr_gate="no_trap",
            allow_or_retest=False,
            candle_trail_mode="pin_protect",
            body_min=0.58,
        ),
        replace(
            b,
            name="hyb_E",
            use_frvp=True,
            frvp_mode="vah_break",
            frvp_anchor="or30",
            frvp_prefer_sl=True,
            allow_or_retest=False,
            candle_trail_mode="pin_protect",
            cooldown_bars=12,
            body_min=0.58,
        ),
    ]


def scan_months(bars, days_list: List[str], score_days: set, cfg: pa.PaConfig):
    keep = []
    for score_set, frame_days, ym in monthly_chunks(days_list, lookback=2):
        if not (score_set & score_days):
            continue
        frame = bars[bars.index.strftime("%Y-%m-%d").isin(set(frame_days))]
        if frame.empty:
            continue
        for c in pa.scan_session(frame, settle=True, cfg=cfg):
            if c.day in score_days and c.day in score_set:
                keep.append(c)
    return keep


def pack(calls, n_sess: int) -> Dict[str, Any]:
    s = pa.summarize(calls)
    hard_sl = sum(1 for c in calls if c.exit_why == "sl")
    return {
        "n": s.get("n") or 0,
        "hit_pct": s.get("hit_pct"),
        "avg_R": s.get("avg_R"),
        "sum_pts": s.get("sum_pts") or 0.0,
        "hard_sl": hard_sl,
        "hit_1R_pct": s.get("hit_1R_pct"),
        "avg_per_day": round(len(calls) / max(n_sess, 1), 2),
        "by_setup": s.get("by_setup"),
    }


def score_row(row: Dict[str, Any], base: Dict[str, Any]) -> float:
    """Composite: prefer sum near/above base, then hit, then avgR.

    Points-first with accuracy bonus. Penalize big sum drop.
    """
    sum_pts = float(row.get("sum_pts") or 0)
    hit = float(row.get("hit_pct") or 0)
    avg_r = float(row.get("avg_R") or 0)
    base_sum = float(base.get("sum_pts") or 1)
    base_hit = float(base.get("hit_pct") or 1)
    # normalize
    sum_ratio = sum_pts / base_sum
    hit_lift = (hit - base_hit) / 100.0
    # must keep at least 70% of base points to compete for "most points"
    if sum_ratio < 0.70:
        return -1e9 + sum_pts
    return sum_pts + 800.0 * hit_lift * base_sum + 50.0 * avg_r


def autopsy_base(calls, bars, days_6m):
    work = bars[bars.index.strftime("%Y-%m-%d").isin(set(days_6m))]
    # light autopsy on setups / exits / tod
    wins = [c for c in calls if c.win]
    losses = [c for c in calls if not c.win]
    hard = [c for c in calls if c.exit_why == "sl"]

    def setup_rate(xs):
        return dict(Counter(c.setup for c in xs))

    def tod_bucket(hm):
        hh, mm = map(int, hm.split(":"))
        m = hh * 60 + mm
        if m < 10 * 60 + 30:
            return "0930_1030"
        if m < 12 * 60 + 30:
            return "1030_1230"
        if m < 14 * 60:
            return "1230_1400"
        return "1400_plus"

    return {
        "n_win": len(wins),
        "n_loss": len(losses),
        "n_hard_sl": len(hard),
        "setup_win": setup_rate(wins),
        "setup_loss": setup_rate(losses),
        "setup_hard_sl": setup_rate(hard),
        "tod_win": dict(Counter(tod_bucket(c.hm) for c in wins)),
        "tod_loss": dict(Counter(tod_bucket(c.hm) for c in losses)),
        "exit_loss": dict(Counter(c.exit_why for c in losses)),
    }


def main() -> int:
    _install_sr_cache()
    live = pa.load_locked_cfg()
    print(f"Live lock held: {live.name} (not overwritten here)", flush=True)
    print("Fetching NIFTY 1m…", flush=True)
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=220, keep_partial=False
    )
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    all_days = sorted({str(ts.date()) for ts in bars.index})
    n6 = min(126, len(all_days))
    days_6m = all_days[-n6:]
    score = set(days_6m)
    i0 = max(0, all_days.index(days_6m[0]) - 2)
    days_scan = all_days[i0:]

    # holdout: last 2 calendar months vs prior months in window
    months = []
    for d in days_6m:
        ym = d[:7]
        if not months or months[-1] != ym:
            months.append(ym)
    holdout_months = set(months[-2:]) if len(months) >= 3 else set(months[-1:])
    train_months = set(months) - holdout_months
    train_days = {d for d in days_6m if d[:7] in train_months}
    hold_days = {d for d in days_6m if d[:7] in holdout_months}

    print(
        f"6m {days_6m[0]}→{days_6m[-1]} sess={len(days_6m)} "
        f"train={sorted(train_months)} holdout={sorted(holdout_months)}",
        flush=True,
    )

    cfgs = variants()
    results = []
    base_pack = None
    base_calls = None

    for cfg in cfgs:
        print(f"  try {cfg.name}…", flush=True)
        calls = scan_months(bars, days_scan, score, cfg)
        full = pack(calls, len(days_6m))
        train = pack([c for c in calls if c.day in train_days], len(train_days))
        hold = pack([c for c in calls if c.day in hold_days], len(hold_days))
        row = {
            "name": cfg.name,
            "full": full,
            "train": train,
            "holdout": hold,
        }
        results.append(row)
        print(
            f"    6m n={full['n']} hit={full['hit_pct']} sum={full['sum_pts']} | "
            f"hold n={hold['n']} hit={hold['hit_pct']} sum={hold['sum_pts']}",
            flush=True,
        )
        if cfg.name == "pa_only":
            base_pack = full
            base_calls = calls

    assert base_pack is not None and base_calls is not None
    auto = autopsy_base(base_calls, bars, days_6m)
    base_hold = next(r["holdout"] for r in results if r["name"] == "pa_only")
    base_train = next(r["train"] for r in results if r["name"] == "pa_only")

    for r in results:
        r["score_6m"] = score_row(r["full"], base_pack)
        r["score_hold"] = score_row(r["holdout"], base_hold)

    # Pareto-ish filters
    candidates = []
    for r in results:
        f, h = r["full"], r["holdout"]
        # keep ≥85% of pa_only points on 6m AND hit >= base-1 OR sum>=base
        if (f["sum_pts"] or 0) < 0.85 * (base_pack["sum_pts"] or 1):
            continue
        if (f.get("hit_pct") or 0) < (base_pack.get("hit_pct") or 0) - 1.5:
            if (f["sum_pts"] or 0) < (base_pack["sum_pts"] or 0):
                continue
        # holdout: don't implode (<70% of base hold sum)
        if (h["sum_pts"] or 0) < 0.70 * max(base_hold["sum_pts"] or 1, 1):
            continue
        candidates.append(r)

    candidates.sort(
        key=lambda r: (
            r["score_6m"],
            r["full"].get("hit_pct") or 0,
            r["full"].get("sum_pts") or 0,
        ),
        reverse=True,
    )
    best = candidates[0] if candidates else max(results, key=lambda r: r["score_6m"])

    # also pure max sum and pure max hit with n floor
    by_sum = sorted(results, key=lambda r: r["full"].get("sum_pts") or 0, reverse=True)
    by_hit = sorted(
        [r for r in results if (r["full"].get("n") or 0) >= 200],
        key=lambda r: (r["full"].get("hit_pct") or 0, r["full"].get("sum_pts") or 0),
        reverse=True,
    )

    lines = [
        "# Max points + accuracy research · from `pa_only` live-path base",
        "",
        f"Window 6m `{days_6m[0]}` → `{days_6m[-1]}` ({len(days_6m)} sessions).",
        f"Train months: {sorted(train_months)} · Holdout: {sorted(holdout_months)}.",
        f"Live lock **not changed**: `{live.name}`.",
        "",
        "## pa_only loss autopsy (6m)",
        "",
        f"- Wins / Losses / Hard SL: {auto['n_win']} / {auto['n_loss']} / {auto['n_hard_sl']}",
        f"- Setups on wins: `{auto['setup_win']}`",
        f"- Setups on losses: `{auto['setup_loss']}`",
        f"- Hard SL setups: `{auto['setup_hard_sl']}`",
        f"- TOD wins: `{auto['tod_win']}` · losses: `{auto['tod_loss']}`",
        f"- Loss exits: `{auto['exit_loss']}`",
        "",
        "## Ablation (ranked by 6m composite score)",
        "",
        "| Logic | N | Hit% | AvgR | Sum | Hold hit | Hold sum | Score |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    ranked = sorted(results, key=lambda r: r["score_6m"], reverse=True)
    for r in ranked:
        f, h = r["full"], r["holdout"]
        mark = "**" if r["name"] == best["name"] else ""
        lines.append(
            f"| {mark}{r['name']}{mark} | {f.get('n')} | {f.get('hit_pct')} | {f.get('avg_R')} | "
            f"{f.get('sum_pts')} | {h.get('hit_pct')} | {h.get('sum_pts')} | {round(r['score_6m'],1)} |"
        )

    lines += [
        "",
        "## Recommendation",
        "",
        f"**Best composite (points+accuracy, holdout-safe):** `{best['name']}`",
        f"- 6m: n={best['full'].get('n')} hit={best['full'].get('hit_pct')} "
        f"avgR={best['full'].get('avg_R')} sum={best['full'].get('sum_pts')}",
        f"- Holdout: n={best['holdout'].get('n')} hit={best['holdout'].get('hit_pct')} "
        f"sum={best['holdout'].get('sum_pts')}",
        f"- vs pa_only 6m sum {base_pack.get('sum_pts')} hit {base_pack.get('hit_pct')}",
        "",
        f"**Max sum:** `{by_sum[0]['name']}` sum={by_sum[0]['full'].get('sum_pts')} "
        f"hit={by_sum[0]['full'].get('hit_pct')}",
        f"**Max hit (n≥200):** `{by_hit[0]['name'] if by_hit else None}` "
        f"hit={by_hit[0]['full'].get('hit_pct') if by_hit else None} "
        f"sum={by_hit[0]['full'].get('sum_pts') if by_hit else None}",
        "",
        "_Wire only if composite beats pa_only on 6m sum≈ and hit↑, with holdout OK._",
        "",
    ]

    OUT.mkdir(parents=True, exist_ok=True)
    MD.write_text("\n".join(lines), encoding="utf-8")
    JS.write_text(
        json.dumps(
            {
                "live_lock": live.name,
                "window": {"start": days_6m[0], "end": days_6m[-1], "n": len(days_6m)},
                "train_months": sorted(train_months),
                "holdout_months": sorted(holdout_months),
                "autopsy": auto,
                "base": base_pack,
                "results": results,
                "best": best,
                "best_sum": by_sum[0],
                "best_hit": by_hit[0] if by_hit else None,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"BEST={best['name']}", flush=True)
    print(f"Wrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
