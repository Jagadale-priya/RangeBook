"""RESEARCH — Option Blue live base: eliminate hard-SL entries only.

Base = locked Option Blue cfg (load_locked_cfg → pa_sr_acc_mid).
Same production scan_session path as live Option Blue.

Hard rule: do NOT remove winners / positive calls. Only block SL-hit entries.

  python -u prod_live/tests/builders/_research_pa_kill_sl_only.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

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
MD = OUT / "PA_KILL_SL_ONLY_RESEARCH.md"
JS = OUT / "PA_KILL_SL_ONLY_RESEARCH.json"


def live_frame(bars, n_sessions: int = 22, lookback: int = 2):
    all_days = sorted({str(ts.date()) for ts in bars.index})
    days = all_days[-n_sessions:]
    si = max(0, all_days.index(days[0]) - lookback)
    frame = bars[bars.index.strftime("%Y-%m-%d").isin(set(all_days[si:]))]
    return frame, days, set(days)


def feats_at_entry(call, o, h, l, c, atr, idx, hm_to_i, cfg) -> Optional[Dict[str, Any]]:
    i = hm_to_i.get((call.day, call.hm))
    if i is None:
        return None
    sr = pa.build_sr_map(o, h, l, c, atr, idx, i, lookback_days=cfg.sr_lookback_days)
    liq = pa.liquidity_read(o, h, l, c, i, call.side, sr)
    rr = pa.reward_risk(call.side, float(call.entry), float(call.stop_loss), sr)
    cf = pa._candle_bar(o, h, l, c, i)
    a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 10.0
    hh, mm = map(int, call.hm.split(":"))
    mins = hh * 60 + mm

    with_n = opp_n = 0
    for j in range(max(0, i - 2), i + 1):
        f = pa._candle_bar(o, h, l, c, j)
        if call.side == "BUY":
            with_n += int(f["bull"])
            opp_n += int(f["bear"])
        else:
            with_n += int(f["bear"])
            opp_n += int(f["bull"])

    if call.side == "BUY":
        opp_dist = (
            (float(sr["nearest_res"]["price"]) - float(call.entry)) / a
            if sr.get("nearest_res")
            else 9.0
        )
        base_dist = (
            (float(call.entry) - float(sr["nearest_sup"]["price"])) / a
            if sr.get("nearest_sup")
            else 9.0
        )
    else:
        opp_dist = (
            (float(call.entry) - float(sr["nearest_sup"]["price"])) / a
            if sr.get("nearest_sup")
            else 9.0
        )
        base_dist = (
            (float(sr["nearest_res"]["price"]) - float(call.entry)) / a
            if sr.get("nearest_res")
            else 9.0
        )

    return {
        "key": (call.day, call.hm, call.side, round(float(call.entry), 2)),
        "win": bool(call.win),
        "hard_sl": call.exit_why == "sl",
        "exit_why": call.exit_why,
        "setup": call.setup,
        "side": call.side,
        "R": float(call.R or 0),
        "risk": float(call.risk or 0),
        "rr": float(rr["rr"]),
        "mins": mins,
        "tod_early": mins < 10 * 60 + 20,
        "tod_late": mins >= 13 * 60 + 30,
        "body": float(cf["body_frac"]),
        "close_loc": float(cf["close_loc"]),
        "pin_against": (call.side == "BUY" and cf["pin_bear"])
        or (call.side == "SELL" and cf["pin_bull"]),
        "wick_against": (call.side == "BUY" and cf["upper_frac"] >= 0.35)
        or (call.side == "SELL" and cf["lower_frac"] >= 0.35),
        "inside": bool(cf["inside"]),
        "liq_favor": bool(liq["liq_favor"]),
        "liq_against": bool(liq["liq_against"]),
        "trap": bool(liq["trap_break"]),
        "mid": bool(liq["in_mid_range"]),
        "opp_dist_atr": float(opp_dist),
        "base_dist_atr": float(base_dist),
        "with3": with_n,
        "opp3": opp_n,
        "htf_against": (call.side == "BUY" and call.htf_bias == "down")
        or (call.side == "SELL" and call.htf_bias == "up"),
        "close_to_opp": opp_dist < 0.40,
        "very_close_opp": opp_dist < 0.25,
        "far_from_base": base_dist > 1.6,
        "body_lt60": cf["body_frac"] < 0.60,
        "body_lt65": cf["body_frac"] < 0.65,
        "close_weak": (call.side == "BUY" and cf["close_loc"] < 0.65)
        or (call.side == "SELL" and cf["close_loc"] > 0.35),
        "opp_majority": opp_n >= 2,
        "rr_lt18": float(rr["rr"]) < 1.8,
        "rr_lt20": float(rr["rr"]) < 2.0,
        "rr_lt25": float(rr["rr"]) < 2.5,
        "risk_ge18": float(call.risk or 0) >= 18.0,
        "risk_le10": float(call.risk or 0) <= 10.0,
        "sweep": call.setup == "SWEEP_RECLAIM",
        "break": call.setup == "BREAK_HOLD",
        "no_liq": not liq["liq_favor"],
        "call": call,
        "i": i,
    }


def rate(rows, key):
    if not rows:
        return None
    return round(100.0 * sum(1 for r in rows if r.get(key)) / len(rows), 1)


def avg(rows, key):
    xs = [r[key] for r in rows if r.get(key) is not None]
    return round(float(np.mean(xs)), 3) if xs else None


# Candidate SL-kill rules: True means BLOCK this entry
# Evaluated offline on base book first (winner-safe check), then re-run live scan with gate.

RuleFn = Callable[[Dict[str, Any]], bool]


def build_rules() -> List[Tuple[str, RuleFn]]:
    return [
        ("close_to_opp", lambda r: r["close_to_opp"]),
        ("very_close_opp", lambda r: r["very_close_opp"]),
        ("wick_against", lambda r: r["wick_against"]),
        ("body_lt60", lambda r: r["body_lt60"]),
        ("body_lt65", lambda r: r["body_lt65"]),
        ("close_weak", lambda r: r["close_weak"]),
        ("opp_majority", lambda r: r["opp_majority"]),
        ("htf_against", lambda r: r["htf_against"]),
        ("tod_early", lambda r: r["tod_early"]),
        ("tod_late", lambda r: r["tod_late"]),
        ("rr_lt18", lambda r: r["rr_lt18"]),
        ("rr_lt20", lambda r: r["rr_lt20"]),
        ("rr_lt25", lambda r: r["rr_lt25"]),
        ("risk_ge18", lambda r: r["risk_ge18"]),
        ("far_from_base", lambda r: r["far_from_base"]),
        ("no_liq_and_close_opp", lambda r: r["no_liq"] and r["close_to_opp"]),
        ("no_liq_and_wick", lambda r: r["no_liq"] and r["wick_against"]),
        ("wick_and_close_opp", lambda r: r["wick_against"] and r["close_to_opp"]),
        ("body60_and_close_opp", lambda r: r["body_lt60"] and r["close_to_opp"]),
        ("close_weak_and_opp", lambda r: r["close_weak"] and r["close_to_opp"]),
        ("opp_maj_and_no_liq", lambda r: r["opp_majority"] and r["no_liq"]),
        ("early_and_break", lambda r: r["tod_early"] and r["break"]),
        ("late_and_no_liq", lambda r: r["tod_late"] and r["no_liq"]),
        ("rr20_and_wick", lambda r: r["rr_lt20"] and r["wick_against"]),
        ("rr20_and_close_opp", lambda r: r["rr_lt20"] and r["close_to_opp"]),
        # stacks aimed at SL only
        (
            "sl_stack_A",
            lambda r: (r["close_to_opp"] or r["wick_against"]) and r["no_liq"],
        ),
        (
            "sl_stack_B",
            lambda r: r["close_to_opp"] and (r["wick_against"] or r["body_lt60"] or r["close_weak"]),
        ),
        (
            "sl_stack_C",
            lambda r: (r["very_close_opp"] or (r["close_to_opp"] and r["wick_against"]))
            and not r["liq_favor"],
        ),
        (
            "sl_stack_D",
            lambda r: r["htf_against"] or (r["close_to_opp"] and r["wick_against"]),
        ),
        (
            "sl_stack_E",
            lambda r: (r["tod_early"] and not r["liq_favor"])
            or (r["close_to_opp"] and r["wick_against"]),
        ),
        (
            "sl_stack_F",
            lambda r: r["very_close_opp"]
            or (r["close_to_opp"] and r["body_lt65"] and r["no_liq"]),
        ),
        (
            "sl_stack_G",
            lambda r: (r["opp_majority"] and r["close_to_opp"])
            or (r["wick_against"] and r["rr_lt20"]),
        ),
    ]


def eval_rule_on_book(rows: List[Dict[str, Any]], rule: RuleFn) -> Dict[str, Any]:
    """Offline: how many SL blocked vs winners blocked (must be 0 winners ideally)."""
    wins = [r for r in rows if r["win"]]
    sls = [r for r in rows if r["hard_sl"]]
    other_loss = [r for r in rows if (not r["win"]) and (not r["hard_sl"])]
    w_kill = sum(1 for r in wins if rule(r))
    s_kill = sum(1 for r in sls if rule(r))
    o_kill = sum(1 for r in other_loss if rule(r))
    return {
        "win_total": len(wins),
        "sl_total": len(sls),
        "win_killed": w_kill,
        "sl_killed": s_kill,
        "other_loss_killed": o_kill,
        "winner_safe": w_kill == 0,
        "sl_kill_pct": round(100.0 * s_kill / len(sls), 1) if sls else 0.0,
    }


def apply_sl_kill_gate(cfg: pa.PaConfig, rule_name: str, rule: RuleFn, frame, days_set):
    """Filter base Option Blue calls with pre-entry rule (winner-safe offline check).

    Same calls Option Blue would have fired; we only drop the ones matching the SL-kill rule.
    """
    work = pa.norm_1m(frame)
    o = work["Open"].values
    h = work["High"].values
    l = work["Low"].values
    c = work["Close"].values
    atr = pa.atr14(h, l, c)
    idx = work.index
    hm_to_i = {(pa._day(ts), pa._hm(ts)): i for i, ts in enumerate(idx)}
    base_calls = pa.scan_session(work, settle=True, cfg=cfg)
    kept = []
    for call in base_calls:
        if call.day not in days_set:
            continue
        feat = feats_at_entry(call, o, h, l, c, atr, idx, hm_to_i, cfg)
        if feat is None:
            continue
        if rule(feat):
            continue
        kept.append(call)
    return kept


def main() -> int:
    cfg = pa.load_locked_cfg()
    print(
        f"Option Blue BASE={cfg.name} sr={cfg.sr_gate} or_retest={cfg.allow_or_retest} "
        f"lo={cfg.trade_lo} hi={cfg.trade_hi} trail={cfg.candle_trail_mode} frvp={cfg.use_frvp}",
        flush=True,
    )
    raw, err = kite_data.fetch_historical_candles("NIFTY", "minute", days=40, keep_partial=False)
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    frame, days, days_set = live_frame(bars, 22, 2)
    print(f"Window {days[0]}→{days[-1]} ({len(days)} live sessions)", flush=True)

    base_calls = [c for c in pa.scan_session(frame, settle=True, cfg=cfg) if c.day in days_set]
    base_s = pa.summarize(base_calls)
    print(
        f"BASE n={base_s.get('n')} hit={base_s.get('hit_pct')} R={base_s.get('avg_R')} sum={base_s.get('sum_pts')}",
        flush=True,
    )

    work = pa.norm_1m(frame)
    o, h, l, c = work["Open"].values, work["High"].values, work["Low"].values, work["Close"].values
    atr = pa.atr14(h, l, c)
    idx = work.index
    hm_to_i = {(pa._day(ts), pa._hm(ts)): i for i, ts in enumerate(idx)}

    rows = []
    for call in base_calls:
        f = feats_at_entry(call, o, h, l, c, atr, idx, hm_to_i, cfg)
        if f:
            rows.append(f)

    wins = [r for r in rows if r["win"]]
    sls = [r for r in rows if r["hard_sl"]]
    print(f"Autopsy wins={len(wins)} hard_SL={len(sls)}", flush=True)

    feat_keys = [
        "close_to_opp",
        "very_close_opp",
        "wick_against",
        "body_lt60",
        "close_weak",
        "opp_majority",
        "htf_against",
        "tod_early",
        "tod_late",
        "rr_lt18",
        "rr_lt20",
        "no_liq",
        "liq_favor",
        "trap",
        "far_from_base",
        "risk_ge18",
    ]
    print("Feature rates win vs SL:", flush=True)
    autopsy_tbl = []
    for k in feat_keys:
        wr, sr = rate(wins, k), rate(sls, k)
        autopsy_tbl.append({"feat": k, "win%": wr, "sl%": sr, "lift_sl": (sr or 0) - (wr or 0)})
        print(f"  {k:20s} win={wr}%  sl={sr}%", flush=True)

    rules = build_rules()
    offline = []
    for name, fn in rules:
        ev = eval_rule_on_book(rows, fn)
        offline.append({"name": name, **ev})
        if ev["winner_safe"] and ev["sl_killed"] > 0:
            print(
                f"  SAFE {name}: kill SL {ev['sl_killed']}/{ev['sl_total']} "
                f"({ev['sl_kill_pct']}%) winners untouched",
                flush=True,
            )

    # Prefer winner-safe rules; among them maximize SL kills then keep sum
    safe = [r for r in offline if r["winner_safe"] and r["sl_killed"] > 0]
    safe.sort(key=lambda r: (r["sl_killed"], r["sl_kill_pct"]), reverse=True)

    # Also allow near-safe: at most 1 winner killed if kills ≥3 SL (report separately)
    near = [
        r
        for r in offline
        if r["win_killed"] <= 1 and r["sl_killed"] >= 2 and r["sl_killed"] > r["win_killed"]
    ]
    near.sort(key=lambda r: (r["sl_killed"] - 2 * r["win_killed"], r["sl_killed"]), reverse=True)

    # Apply top safe rules as live filters and measure book
    live_results = []
    tested = []
    for r in safe[:8]:
        tested.append(r["name"])
    for r in near[:5]:
        if r["name"] not in tested:
            tested.append(r["name"])

    rule_map = dict(rules)
    for name in tested:
        fn = rule_map[name]
        kept = apply_sl_kill_gate(cfg, name, fn, frame, days_set)
        s = pa.summarize(kept)
        off = next(x for x in offline if x["name"] == name)
        live_results.append(
            {
                "name": name,
                **s,
                "n": len(kept),
                "winner_safe": off["winner_safe"],
                "win_killed": off["win_killed"],
                "sl_killed": off["sl_killed"],
                "sl_kill_pct": off["sl_kill_pct"],
            }
        )
        print(
            f"  live {name}: n={s.get('n')} hit={s.get('hit_pct')} R={s.get('avg_R')} "
            f"sum={s.get('sum_pts')} (SL_kill={off['sl_killed']} win_kill={off['win_killed']})",
            flush=True,
        )

    # Best: winner_safe, max hit then sum; must not kill winners
    live_safe = [r for r in live_results if r.get("winner_safe")]
    live_safe.sort(
        key=lambda r: ((r.get("hit_pct") or 0), (r.get("avg_R") or 0), (r.get("sum_pts") or 0)),
        reverse=True,
    )
    best = live_safe[0] if live_safe else None

    lines = [
        f"# Kill-SL-only research · Option Blue base `{cfg.name}`",
        "",
        f"Window {days[0]} → {days[-1]} ({len(days)} live sessions). Same `scan_session` as Option Blue.",
        "",
        f"**BASE:** n={base_s.get('n')} hit={base_s.get('hit_pct')}% avgR={base_s.get('avg_R')} "
        f"sum={base_s.get('sum_pts')} · wins={len(wins)} · hard_SL={len(sls)}",
        "",
        "## Constraint",
        "",
        "Ignore / do not change entries that hit target or finish positive. "
        "Only eliminate hard stop-loss entries.",
        "",
        "## Feature autopsy (pre-entry) — win% vs hard-SL%",
        "",
        "| Feature | Win% | Hard-SL% | SL−Win |",
        "|---|---:|---:|---:|",
    ]
    for row in sorted(autopsy_tbl, key=lambda x: -(x["lift_sl"] or 0)):
        lines.append(
            f"| {row['feat']} | {row['win%']} | {row['sl%']} | {row['lift_sl']:.1f} |"
        )

    lines += [
        "",
        "## Winner-safe rules (0 winners killed)",
        "",
        "| Rule | SL killed | SL% | Win killed |",
        "|---|---:|---:|---:|",
    ]
    for r in safe:
        lines.append(
            f"| {r['name']} | {r['sl_killed']}/{r['sl_total']} | {r['sl_kill_pct']} | {r['win_killed']} |"
        )
    if not safe:
        lines.append("| _(none fully winner-safe with SL>0)_ | | | |")

    lines += [
        "",
        "## Live filtered books",
        "",
        "| Variant | N | Hit% | AvgR | Sum | SL_kill | Win_kill | Safe |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
        f"| **BASE** | {base_s.get('n')} | {base_s.get('hit_pct')} | {base_s.get('avg_R')} | {base_s.get('sum_pts')} | 0 | 0 | — |",
    ]
    for r in sorted(live_results, key=lambda x: (-(x.get("hit_pct") or 0), -(x.get("sum_pts") or 0))):
        mark = "**" if best and r["name"] == best["name"] else ""
        lines.append(
            f"| {mark}{r['name']}{mark} | {r.get('n')} | {r.get('hit_pct')} | {r.get('avg_R')} | "
            f"{r.get('sum_pts')} | {r.get('sl_killed')} | {r.get('win_killed')} | {r.get('winner_safe')} |"
        )

    lines += ["", "## Recommendation", ""]
    if best:
        lines.append(
            f"**Wire:** `{best['name']}` — n={best.get('n')} hit={best.get('hit_pct')} "
            f"avgR={best.get('avg_R')} sum={best.get('sum_pts')} · "
            f"killed {best.get('sl_killed')} hard-SLs · **0 winners removed**"
        )
    else:
        lines.append("No fully winner-safe rule lifted the book; inspect near-safe table in JSON.")
    lines.append("")

    OUT.mkdir(parents=True, exist_ok=True)
    MD.write_text("\n".join(lines), encoding="utf-8")
    JS.write_text(
        json.dumps(
            {
                "base_cfg": cfg.name,
                "base": base_s,
                "n_wins": len(wins),
                "n_hard_sl": len(sls),
                "autopsy": autopsy_tbl,
                "offline": offline,
                "safe": safe,
                "near": near,
                "live": live_results,
                "best": best,
                "window": {"start": days[0], "end": days[-1], "n": len(days)},
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"BEST={best['name'] if best else None}", flush=True)
    print(f"Wrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
