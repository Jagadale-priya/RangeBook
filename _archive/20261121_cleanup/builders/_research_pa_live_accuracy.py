"""RESEARCH — lift live-session accuracy on locked pa_sr_full_v1.

Uses real scan_session (production path), not post-filters that drift n/hit.
Autopsy losses → ablate tighter gates → report/wire winners.

  python -u prod_live/tests/builders/_research_pa_live_accuracy.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
MD = OUT / "PA_LIVE_ACCURACY_RESEARCH.md"
JS = OUT / "PA_LIVE_ACCURACY_RESEARCH.json"


def frame_for(bars, days: List[str], lookback: int = 2):
    all_days = sorted({str(ts.date()) for ts in bars.index})
    si = max(0, all_days.index(days[0]) - lookback)
    keep = set(all_days[si:])
    return bars[bars.index.strftime("%Y-%m-%d").isin(keep)], set(days)


def score_day_filter(calls, days_set):
    return [c for c in calls if c.day in days_set]


def autopsy(calls, bars, cfg):
    work = pa.norm_1m(bars)
    o, h, l, c = work["Open"].values, work["High"].values, work["Low"].values, work["Close"].values
    atr = pa.atr14(h, l, c)
    idx = work.index
    hm_to_i = {(pa._day(ts), pa._hm(ts)): i for i, ts in enumerate(idx)}

    rows = []
    for call in calls:
        i = hm_to_i.get((call.day, call.hm))
        if i is None:
            continue
        sr = pa.build_sr_map(o, h, l, c, atr, idx, i, lookback_days=cfg.sr_lookback_days)
        liq = pa.liquidity_read(o, h, l, c, i, call.side, sr)
        rr = pa.reward_risk(call.side, float(call.entry), float(call.stop_loss), sr)
        cf = pa._candle_bar(o, h, l, c, i)
        prev = pa._candle_bar(o, h, l, c, i - 1) if i >= 1 else None
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 10.0
        # time of day buckets
        hm = call.hm
        hh, mm = map(int, hm.split(":"))
        mins = hh * 60 + mm
        tod = (
            "open_930_1030" if mins < 10 * 60 + 30
            else "mid_1030_1230" if mins < 12 * 60 + 30
            else "early_pm_1230_1400" if mins < 14 * 60
            else "late_1400_plus"
        )
        rows.append({
            "win": bool(call.win),
            "exit_why": call.exit_why,
            "setup": call.setup,
            "side": call.side,
            "R": float(call.R or 0),
            "risk": float(call.risk or 0),
            "rr": float(rr["rr"]),
            "liq_favor": liq["liq_favor"],
            "trap": liq["trap_break"],
            "mid": liq["in_mid_range"],
            "body": cf["body_frac"],
            "close_loc": cf["close_loc"],
            "doji": cf["doji"],
            "pin_bull": cf["pin_bull"],
            "pin_bear": cf["pin_bear"],
            "tod": tod,
            "htf": call.htf_bias,
            "mfe": float(call.mfe or 0),
            "mae": float(call.mae or 0),
            "hit_1R": bool(call.hit_1R),
            "near_res_dist": (
                (float(sr["nearest_res"]["price"]) - float(call.entry)) / a
                if sr.get("nearest_res") else None
            ),
            "near_sup_dist": (
                (float(call.entry) - float(sr["nearest_sup"]["price"])) / a
                if sr.get("nearest_sup") else None
            ),
            "prior_exhaust": bool(
                prev and (
                    (call.side == "BUY" and (prev["pin_bear"] or (prev["upper_frac"] >= 0.55 and prev["bull"])))
                    or (call.side == "SELL" and (prev["pin_bull"] or (prev["lower_frac"] >= 0.55 and prev["bear"])))
                )
            ),
            "entry_rng_atr": cf["body_frac"] and ((float(h[i]) - float(l[i])) / a),
            "sweep_setup": call.setup == "SWEEP_RECLAIM",
            "or_setup": call.setup == "OR_RETEST",
            "break_setup": call.setup == "BREAK_HOLD",
        })
    wins = [r for r in rows if r["win"]]
    losses = [r for r in rows if not r["win"]]

    def rate(xs, key):
        if not xs:
            return None
        return round(100.0 * sum(1 for r in xs if r.get(key)) / len(xs), 1)

    def avg(xs, key):
        vs = [r[key] for r in xs if r.get(key) is not None]
        return round(float(np.mean(vs)), 3) if vs else None

    def tod_split(xs):
        c = Counter(r["tod"] for r in xs)
        return dict(c)

    return {
        "n_win": len(wins),
        "n_loss": len(losses),
        "win": {
            "liq_favor%": rate(wins, "liq_favor"),
            "mid%": rate(wins, "mid"),
            "hit_1R%": rate(wins, "hit_1R"),
            "sweep%": rate(wins, "sweep_setup"),
            "or%": rate(wins, "or_setup"),
            "break%": rate(wins, "break_setup"),
            "prior_exhaust%": rate(wins, "prior_exhaust"),
            "avg_rr": avg(wins, "rr"),
            "avg_risk": avg(wins, "risk"),
            "avg_body": avg(wins, "body"),
            "avg_mfe": avg(wins, "mfe"),
            "avg_mae": avg(wins, "mae"),
            "avg_near_res_atr": avg(wins, "near_res_dist"),
            "tod": tod_split(wins),
            "exit": dict(Counter(r["exit_why"] for r in wins)),
            "setup": dict(Counter(r["setup"] for r in wins)),
        },
        "loss": {
            "liq_favor%": rate(losses, "liq_favor"),
            "mid%": rate(losses, "mid"),
            "hit_1R%": rate(losses, "hit_1R"),
            "sweep%": rate(losses, "sweep_setup"),
            "or%": rate(losses, "or_setup"),
            "break%": rate(losses, "break_setup"),
            "prior_exhaust%": rate(losses, "prior_exhaust"),
            "avg_rr": avg(losses, "rr"),
            "avg_risk": avg(losses, "risk"),
            "avg_body": avg(losses, "body"),
            "avg_mfe": avg(losses, "mfe"),
            "avg_mae": avg(losses, "mae"),
            "avg_near_res_atr": avg(losses, "near_res_dist"),
            "tod": tod_split(losses),
            "exit": dict(Counter(r["exit_why"] for r in losses)),
            "setup": dict(Counter(r["setup"] for r in losses)),
        },
        "rows": rows,
    }


# ---- accuracy variants as PaConfig overlays (real scan path) ----

def variants(base: pa.PaConfig) -> List[pa.PaConfig]:
    out = [
        replace(base, name="BASE_full_v1"),
        # tighten RR
        replace(base, name="rr18", min_rr=1.8),
        replace(base, name="rr20", min_rr=2.0),
        # candle stricter
        replace(base, name="v3_trail_base", candle_trail_mode="base"),
        # drop OR_RETEST (often chop)
        replace(base, name="no_or", allow_or_retest=False),
        replace(base, name="no_or_rr18", allow_or_retest=False, min_rr=1.8),
        # only sweep+break
        replace(base, name="sweep_break", allow_or_retest=False),
        # stricter body
        replace(base, name="body60", body_min=0.60),
        replace(base, name="body60_no_or", body_min=0.60, allow_or_retest=False),
        # later open / earlier cut
        replace(base, name="open_1000", trade_lo=10 * 60),
        replace(base, name="open_1000_no_or", trade_lo=10 * 60, allow_or_retest=False),
        replace(base, name="cut_1400", trade_hi=14 * 60),
        replace(base, name="mid_session", trade_lo=10 * 60, trade_hi=14 * 60, allow_or_retest=False),
        # more cooldown = fewer clustered losers
        replace(base, name="cd14", cooldown_bars=14),
        replace(base, name="cd14_no_or", cooldown_bars=14, allow_or_retest=False),
        # flip cooldown longer
        replace(base, name="flip18", side_flip_cooldown=18),
        # full_v3 gate
        replace(base, name="full_v3", sr_gate="full_v3"),
        replace(base, name="full_v3_no_or", sr_gate="full_v3", allow_or_retest=False),
        # no_trap only (volume) for reference
        replace(base, name="no_trap", sr_gate="no_trap", candle_entry_mode="read_v3"),
        # combo accuracy
        replace(
            base,
            name="acc_A",
            allow_or_retest=False,
            min_rr=1.8,
            body_min=0.58,
            cooldown_bars=12,
        ),
        replace(
            base,
            name="acc_B",
            allow_or_retest=False,
            min_rr=1.6,
            trade_lo=10 * 60,
            trade_hi=14 * 60,
            candle_trail_mode="pin_protect",
        ),
        replace(
            base,
            name="acc_C",
            allow_or_retest=False,
            min_rr=1.8,
            trade_lo=9 * 60 + 45,
            cooldown_bars=14,
            side_flip_cooldown=15,
            body_min=0.58,
        ),
        replace(
            base,
            name="acc_D",
            sr_gate="full_v3",
            allow_or_retest=False,
            min_rr=1.5,
            trade_lo=10 * 60,
        ),
        replace(
            base,
            name="acc_E",
            allow_or_retest=False,
            allow_break=True,
            allow_sweep=True,
            min_rr=2.0,
            body_min=0.60,
            trade_lo=10 * 60,
            trade_hi=13 * 60 + 45,
        ),
    ]
    return out


def run_cfg(frame, days_set, cfg) -> Dict[str, Any]:
    calls = score_day_filter(pa.scan_session(frame, settle=True, cfg=cfg), days_set)
    s = pa.summarize(calls)
    return {"summary": s, "n": len(calls), "calls": calls}


def main() -> int:
    base = pa.load_locked_cfg()
    print(f"Base {base.name} sr={base.sr_gate} frvp={base.use_frvp}", flush=True)
    raw, err = kite_data.fetch_historical_candles("NIFTY", "minute", days=40, keep_partial=False)
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    all_days = sorted({str(ts.date()) for ts in bars.index})
    days = all_days[-22:]
    frame, days_set = frame_for(bars, days, lookback=2)
    print(f"Window {days[0]}→{days[-1]} ({len(days)} sessions)", flush=True)

    base_book = run_cfg(frame, days_set, base)
    base_s = base_book["summary"]
    print(
        f"BASE n={base_s.get('n')} hit={base_s.get('hit_pct')} R={base_s.get('avg_R')} sum={base_s.get('sum_pts')}",
        flush=True,
    )

    auto = autopsy(base_book["calls"], frame, base)
    print("AUTOPSY win", {k: v for k, v in auto["win"].items() if k not in ("tod", "exit", "setup")}, flush=True)
    print("AUTOPSY loss", {k: v for k, v in auto["loss"].items() if k not in ("tod", "exit", "setup")}, flush=True)
    print("LOSS setups", auto["loss"]["setup"], "tod", auto["loss"]["tod"], flush=True)
    print("WIN  setups", auto["win"]["setup"], "tod", auto["win"]["tod"], flush=True)

    results = []
    for cfg in variants(base):
        print(f"  try {cfg.name}…", flush=True)
        book = run_cfg(frame, days_set, cfg)
        s = book["summary"]
        results.append({"name": cfg.name, **s, "n": book["n"]})
        print(
            f"    n={s.get('n')} hit={s.get('hit_pct')} R={s.get('avg_R')} sum={s.get('sum_pts')}",
            flush=True,
        )

    ranked = sorted(
        results,
        key=lambda r: ((r.get("hit_pct") or 0), (r.get("avg_R") or 0), (r.get("sum_pts") or 0)),
        reverse=True,
    )
    n_floor = max(18, int(0.55 * (base_s.get("n") or 40)))
    hit_floor = (base_s.get("hit_pct") or 0) + 1.0  # must beat base
    good = [
        r
        for r in ranked
        if (r.get("n") or 0) >= n_floor
        and (r.get("hit_pct") or 0) >= hit_floor
        and (r.get("avg_R") or -9) >= (base_s.get("avg_R") or 0) - 0.05
    ]
    # prefer highest hit then R then sum
    best = good[0] if good else None
    # also best hit overall with n>=15
    best_hit = next((r for r in ranked if (r.get("n") or 0) >= 15), ranked[0] if ranked else None)

    lines = [
        f"# Live accuracy research · `{base.name}`",
        "",
        f"Window {days[0]} → {days[-1]} (**{len(days)} live sessions**). Real `scan_session` path.",
        "",
        f"**BASE:** n={base_s.get('n')} hit={base_s.get('hit_pct')}% avgR={base_s.get('avg_R')} sum={base_s.get('sum_pts')}",
        "",
        "## Loss autopsy (vs wins)",
        "",
        "| Feature | Wins | Losses |",
        "|---|---|---|",
        f"| N | {auto['n_win']} | {auto['n_loss']} |",
        f"| Liq favor % | {auto['win']['liq_favor%']} | {auto['loss']['liq_favor%']} |",
        f"| Mid-range % | {auto['win']['mid%']} | {auto['loss']['mid%']} |",
        f"| Hit 1R % | {auto['win']['hit_1R%']} | {auto['loss']['hit_1R%']} |",
        f"| Prior exhaust % | {auto['win']['prior_exhaust%']} | {auto['loss']['prior_exhaust%']} |",
        f"| Avg soft RR | {auto['win']['avg_rr']} | {auto['loss']['avg_rr']} |",
        f"| Avg risk pts | {auto['win']['avg_risk']} | {auto['loss']['avg_risk']} |",
        f"| Avg body | {auto['win']['avg_body']} | {auto['loss']['avg_body']} |",
        f"| Avg MFE / MAE | {auto['win']['avg_mfe']} / {auto['win']['avg_mae']} | {auto['loss']['avg_mfe']} / {auto['loss']['avg_mae']} |",
        f"| Setups | {auto['win']['setup']} | {auto['loss']['setup']} |",
        f"| Time-of-day | {auto['win']['tod']} | {auto['loss']['tod']} |",
        f"| Exit why | {auto['win']['exit']} | {auto['loss']['exit']} |",
        "",
        "## Ablation (production scan path)",
        "",
        "| Variant | N | Hit% | AvgR | Sum |",
        "|---|---:|---:|---:|---:|",
        f"| **BASE** | {base_s.get('n')} | {base_s.get('hit_pct')} | {base_s.get('avg_R')} | {base_s.get('sum_pts')} |",
    ]
    for r in ranked:
        mark = "**" if best and r["name"] == best["name"] else ""
        lines.append(
            f"| {mark}{r['name']}{mark} | {r.get('n')} | {r.get('hit_pct')} | {r.get('avg_R')} | {r.get('sum_pts')} |"
        )
    lines += [
        "",
        "## Recommendation",
        "",
    ]
    if best:
        lines.append(
            f"**Wire candidate:** `{best['name']}` — n={best.get('n')} hit={best.get('hit_pct')} "
            f"avgR={best.get('avg_R')} sum={best.get('sum_pts')} (beats base hit, n≥{n_floor})"
        )
    else:
        lines.append("No variant beat base hit% with volume floor — keep BASE; see hit-max below.")
    if best_hit:
        lines.append(
            f"**Hit-max (n≥15):** `{best_hit['name']}` — n={best_hit.get('n')} hit={best_hit.get('hit_pct')} "
            f"avgR={best_hit.get('avg_R')} sum={best_hit.get('sum_pts')}"
        )
    lines.append("")
    OUT.mkdir(parents=True, exist_ok=True)
    MD.write_text("\n".join(lines), encoding="utf-8")
    JS.write_text(
        json.dumps(
            {
                "base": base_s,
                "autopsy": {k: v for k, v in auto.items() if k != "rows"},
                "ranked": results,
                "best": best,
                "best_hit": best_hit,
                "window": {"start": days[0], "end": days[-1], "n": len(days)},
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"BEST={best['name'] if best else None}", flush=True)
    print(f"BEST_HIT={best_hit['name'] if best_hit else None}", flush=True)
    print(f"Wrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
