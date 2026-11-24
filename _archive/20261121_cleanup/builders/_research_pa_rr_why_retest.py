"""WHY rr_accurate failed + retest better R:R definitions on NIFTY 20d.

Autopsy on BASE pa_no_trap:
  - real vs synthetic target vs win
  - planned RR buckets vs hit / MFE / MAE
  - wall-inside-1R vs hit
  - which BASE winners rr_accurate would have killed

Then ablate gates that match trail@1R reality (path to 1R, not far S/R).
Does NOT overwrite locked_cfg.

  python -u prod_live/tests/builders/_research_pa_rr_why_retest.py
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
MD = OUT / "PA_RR_WHY_RETEST_20D.md"
JS = OUT / "PA_RR_WHY_RETEST_20D.json"
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
        return {"n": 0, "hit": 0.0, "avgR": 0.0, "sum": 0.0, "hit_1R": 0.0, "hard_sl": 0, "wins": 0}
    wins = [c for c in calls if c.win]
    return {
        "n": n,
        "hit": round(100.0 * len(wins) / n, 2),
        "avgR": round(float(np.mean([float(c.R or 0) for c in calls])), 3),
        "sum": round(float(np.sum([float(c.pts or 0) for c in calls])), 2),
        "hit_1R": round(100.0 * sum(1 for c in calls if c.hit_1R) / n, 1),
        "hard_sl": sum(1 for c in calls if c.exit_why == "sl"),
        "wins": len(wins),
        "avg_risk": round(float(np.mean([float(c.risk or 0) for c in calls])), 2),
    }


def _opp_levels(side: str, entry: float, sr: Dict[str, Any], clear: float) -> List[float]:
    cands: List[float] = []
    if side == "BUY":
        if sr.get("nearest_res"):
            cands.append(float(sr["nearest_res"]["price"]))
        if sr.get("range_hi") is not None:
            cands.append(float(sr["range_hi"]))
        if sr.get("pdh") and float(sr["pdh"]) > entry:
            cands.append(float(sr["pdh"]))
        for r in sr.get("resists") or []:
            if float(r["price"]) > entry:
                cands.append(float(r["price"]))
        return sorted({x for x in cands if x > entry + clear})
    if sr.get("nearest_sup"):
        cands.append(float(sr["nearest_sup"]["price"]))
    if sr.get("range_lo") is not None:
        cands.append(float(sr["range_lo"]))
    if sr.get("pdl") and float(sr["pdl"]) < entry:
        cands.append(float(sr["pdl"]))
    for s in sr.get("supports") or []:
        if float(s["price"]) < entry:
            cands.append(float(s["price"]))
    return sorted({x for x in cands if x < entry - clear}, reverse=True)


def enrich_call(call: pa.PaCall, work, o, h, l, c, atr, idx, hm_to_i, cfg) -> Optional[Dict[str, Any]]:
    i = hm_to_i.get((call.day, call.hm))
    if i is None:
        return None
    sr = pa.build_sr_map(o, h, l, c, atr, idx, i, lookback_days=cfg.sr_lookback_days)
    liq = pa.liquidity_read(o, h, l, c, i, call.side, sr)
    risk = float(call.risk or abs(float(call.entry) - float(call.stop_loss)))
    entry = float(call.entry)
    clear = 0.30 * risk
    levels = _opp_levels(call.side, entry, sr, clear)
    rr_syn = pa.reward_risk(call.side, entry, float(call.stop_loss), sr, require_real_target=False)
    rr_real = pa.reward_risk(call.side, entry, float(call.stop_loss), sr, require_real_target=True)
    has_real = bool(rr_real.get("real_target"))
    nearest = levels[0] if levels else None
    dist_R = (abs(nearest - entry) / risk) if nearest is not None and risk > 1e-9 else None
    # wall inside 1R: any opposing level between entry and entry±1R
    one_r = entry + risk if call.side == "BUY" else entry - risk
    wall_in_1R = False
    if nearest is not None:
        if call.side == "BUY" and entry < nearest <= one_r + 1e-9:
            wall_in_1R = True
        if call.side == "SELL" and one_r - 1e-9 <= nearest < entry:
            wall_in_1R = True
    # far empty: real target but very far (>= 3R) — classic inflated RR
    far_empty = bool(has_real and dist_R is not None and dist_R >= 3.0)
    # tight target: real but < 1.0R (can't pay 1R before wall)
    tight_tgt = bool(has_real and dist_R is not None and dist_R < 1.0)
    # would rr_accurate min_rr=1.5 keep?
    keep_rr15 = has_real and float(rr_real.get("rr") or 0) >= 1.5 and not (
        liq["trap_break"] or liq["liq_against"]
    )
    mfe_R = float(call.mfe or 0) / risk if risk > 1e-9 else 0.0
    mae_R = float(call.mae or 0) / risk if risk > 1e-9 else 0.0
    return {
        "day": call.day,
        "hm": call.hm,
        "side": call.side,
        "setup": call.setup,
        "win": bool(call.win),
        "R": float(call.R or 0),
        "pts": float(call.pts or 0),
        "risk": risk,
        "exit": call.exit_why,
        "hit_1R": bool(call.hit_1R),
        "mfe_R": round(mfe_R, 3),
        "mae_R": round(mae_R, 3),
        "has_real": has_real,
        "rr_synth": round(float(rr_syn["rr"]), 3),
        "rr_real": round(float(rr_real["rr"]), 3) if has_real else None,
        "dist_R": round(dist_R, 3) if dist_R is not None else None,
        "wall_in_1R": wall_in_1R,
        "far_empty": far_empty,
        "tight_tgt": tight_tgt,
        "trap": bool(liq["trap_break"] or liq["liq_against"]),
        "mid": bool(liq["in_mid_range"]),
        "keep_rr15": keep_rr15,
        "killed_reason": (
            "trap"
            if (liq["trap_break"] or liq["liq_against"])
            else ("no_real_target" if not has_real else ("rr_lt_min" if float(rr_real.get("rr") or 0) < 1.5 else "kept"))
        ),
    }


def bucket_table(rows: List[Dict[str, Any]], key: str, edges: List[Tuple[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for label, pred in edges:
        xs = [r for r in rows if pred(r)]
        n = len(xs)
        if n == 0:
            out.append({"bucket": label, "n": 0, "hit": None, "avgR": None, "sum": 0, "hit_1R": None})
            continue
        out.append(
            {
                "bucket": label,
                "n": n,
                "hit": round(100.0 * sum(1 for r in xs if r["win"]) / n, 1),
                "avgR": round(float(np.mean([r["R"] for r in xs])), 3),
                "sum": round(float(np.sum([r["pts"] for r in xs])), 1),
                "hit_1R": round(100.0 * sum(1 for r in xs if r["hit_1R"]) / n, 1),
            }
        )
    return out


def rate(rows, pred) -> Dict[str, Any]:
    xs = [r for r in rows if pred(r)]
    n = len(xs)
    if not n:
        return {"n": 0, "hit": None, "sum": 0, "avgR": None}
    return {
        "n": n,
        "hit": round(100.0 * sum(1 for r in xs if r["win"]) / n, 1),
        "sum": round(float(np.sum([r["pts"] for r in xs])), 1),
        "avgR": round(float(np.mean([r["R"] for r in xs])), 3),
    }


# ---- new gates as sr_gate modes (research-only via monkeypatch-style wrappers) ----

def gate_clear_1R(o, h, l, c, atr, idx, i, side, entry, sl, cfg) -> Tuple[bool, str]:
    """no_trap + reject if opposing wall sits inside the first 1R path."""
    sr = pa.build_sr_map(o, h, l, c, atr, idx, i, lookback_days=cfg.sr_lookback_days)
    liq = pa.liquidity_read(o, h, l, c, i, side, sr)
    if liq["trap_break"] or liq["liq_against"]:
        return False, "sr_block_trap"
    risk = abs(entry - sl)
    clear = 0.15 * risk  # any wall meaningfully inside 1R
    levels = _opp_levels(side, entry, sr, clear)
    one_r = entry + risk if side == "BUY" else entry - risk
    for lv in levels:
        if side == "BUY" and entry < lv <= one_r:
            return False, "sr_block_wall_in_1R"
        if side == "SELL" and one_r <= lv < entry:
            return False, "sr_block_wall_in_1R"
    return True, "sr_ok_clear_1R"


def gate_reject_far_empty(o, h, l, c, atr, idx, i, side, entry, sl, cfg) -> Tuple[bool, str]:
    """no_trap + reject far empty air (nearest real opp >= 3R) — inverted RR filter."""
    sr = pa.build_sr_map(o, h, l, c, atr, idx, i, lookback_days=cfg.sr_lookback_days)
    liq = pa.liquidity_read(o, h, l, c, i, side, sr)
    if liq["trap_break"] or liq["liq_against"]:
        return False, "sr_block_trap"
    risk = abs(entry - sl)
    levels = _opp_levels(side, entry, sr, 0.30 * risk)
    if levels:
        dist_R = abs(levels[0] - entry) / risk if risk > 1e-9 else 99.0
        if dist_R >= 3.0:
            return False, f"sr_block_far_empty={dist_R:.1f}R"
    return True, "sr_ok_not_far_empty"


def gate_path_1R_or_tight_ok(o, h, l, c, atr, idx, i, side, entry, sl, cfg) -> Tuple[bool, str]:
    """no_trap + (clear 1R OR tight real target that we treat as scale — still allow).
    Actually: allow if NOT (wall in 1R). Same as clear_1R. Kept for naming.
    """
    return gate_clear_1R(o, h, l, c, atr, idx, i, side, entry, sl, cfg)


def gate_rr_soft_synth(o, h, l, c, atr, idx, i, side, entry, sl, cfg) -> Tuple[bool, str]:
    """no_trap + min_rr on synth-allowed RR (old optimistic). Research contrast."""
    sr = pa.build_sr_map(o, h, l, c, atr, idx, i, lookback_days=cfg.sr_lookback_days)
    liq = pa.liquidity_read(o, h, l, c, i, side, sr)
    if liq["trap_break"] or liq["liq_against"]:
        return False, "sr_block_trap"
    rr = pa.reward_risk(side, entry, sl, sr, require_real_target=False)
    if float(rr["rr"]) < float(cfg.min_rr):
        return False, f"sr_block_rr={rr['rr']:.2f}"
    return True, f"sr_ok_soft_rr={rr['rr']:.2f}"


def gate_no_tight_wall(o, h, l, c, atr, idx, i, side, entry, sl, cfg) -> Tuple[bool, str]:
    """no_trap + reject only when nearest wall < 1.0R (can't reach trail arm cleanly)."""
    sr = pa.build_sr_map(o, h, l, c, atr, idx, i, lookback_days=cfg.sr_lookback_days)
    liq = pa.liquidity_read(o, h, l, c, i, side, sr)
    if liq["trap_break"] or liq["liq_against"]:
        return False, "sr_block_trap"
    risk = abs(entry - sl)
    levels = _opp_levels(side, entry, sr, 0.10 * risk)
    if levels:
        dist_R = abs(levels[0] - entry) / risk if risk > 1e-9 else 99.0
        if dist_R < 1.0:
            return False, f"sr_block_tight_wall={dist_R:.2f}R"
    return True, "sr_ok_no_tight_wall"


CUSTOM_GATES = {
    "clear_1R": gate_clear_1R,
    "reject_far_empty": gate_reject_far_empty,
    "soft_rr_15": gate_rr_soft_synth,
    "no_tight_wall": gate_no_tight_wall,
    "clear_1R_and_no_far": None,  # composed below
}


def gate_clear_1R_and_no_far(o, h, l, c, atr, idx, i, side, entry, sl, cfg) -> Tuple[bool, str]:
    ok, note = gate_clear_1R(o, h, l, c, atr, idx, i, side, entry, sl, cfg)
    if not ok:
        return ok, note
    return gate_reject_far_empty(o, h, l, c, atr, idx, i, side, entry, sl, cfg)


CUSTOM_GATES["clear_1R_and_no_far"] = gate_clear_1R_and_no_far


def scan_with_custom_gate(frame, score_days, cfg, gate_fn) -> List[pa.PaCall]:
    """Temporarily wrap sr_gate_ok for custom research gates."""
    orig = pa.sr_gate_ok

    def wrapped(o, h, l, c, atr, idx, i, side, entry, sl, cfg_inner):
        # If cfg asks for a custom name via sr_gate marker, use gate_fn
        return gate_fn(o, h, l, c, atr, idx, i, side, entry, sl, cfg_inner)

    pa.sr_gate_ok = wrapped  # type: ignore
    try:
        # force sr_gate non-none so scan_session calls sr_gate_ok
        cfg2 = replace(cfg, sr_gate="custom_research")
        calls = pa.scan_session(frame, settle=True, cfg=cfg2)
        return [c for c in calls if c.day in score_days]
    finally:
        pa.sr_gate_ok = orig  # type: ignore


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
    print("Scan BASE …", flush=True)
    base_calls = [c for c in pa.scan_session(frame, settle=True, cfg=base_cfg) if c.day in score_days]
    base_sc = score(base_calls)
    print(f"  BASE n={base_sc['n']} hit={base_sc['hit']} sum={base_sc['sum']}", flush=True)

    work = pa.norm_1m(frame)
    o, h, l, c = work["Open"].values, work["High"].values, work["Low"].values, work["Close"].values
    atr = pa.atr14(h, l, c)
    idx = work.index
    hm_to_i = {(pa._day(idx[i]), pa._hm(idx[i])): i for i in range(len(work))}

    rows = []
    for call in base_calls:
        e = enrich_call(call, work, o, h, l, c, atr, idx, hm_to_i, base_cfg)
        if e:
            rows.append(e)

    wins = [r for r in rows if r["win"]]
    losses = [r for r in rows if not r["win"]]
    killed_wins = [r for r in wins if not r["keep_rr15"]]
    kept = [r for r in rows if r["keep_rr15"]]

    why = {
        "base": base_sc,
        "real_target": {
            "all": rate(rows, lambda r: r["has_real"]),
            "no_real": rate(rows, lambda r: not r["has_real"]),
            "wins_pct_real": round(100.0 * sum(1 for r in wins if r["has_real"]) / max(len(wins), 1), 1),
            "loss_pct_real": round(100.0 * sum(1 for r in losses if r["has_real"]) / max(len(losses), 1), 1),
        },
        "killed_by_rr_acc_15": {
            "n_killed": len(rows) - len(kept),
            "n_kept": len(kept),
            "killed_wins": len(killed_wins),
            "killed_losses": sum(1 for r in losses if not r["keep_rr15"]),
            "kept_score": rate(kept, lambda r: True),
            "kill_reasons_all": dict(Counter(r["killed_reason"] for r in rows)),
            "kill_reasons_wins": dict(Counter(r["killed_reason"] for r in wins)),
            "kill_reasons_losses": dict(Counter(r["killed_reason"] for r in losses)),
        },
        "rr_real_buckets": bucket_table(
            [r for r in rows if r["rr_real"] is not None],
            "rr_real",
            [
                ("rr<1.0", lambda r: r["rr_real"] is not None and r["rr_real"] < 1.0),
                ("1.0-1.5", lambda r: r["rr_real"] is not None and 1.0 <= r["rr_real"] < 1.5),
                ("1.5-2.5", lambda r: r["rr_real"] is not None and 1.5 <= r["rr_real"] < 2.5),
                ("2.5-4", lambda r: r["rr_real"] is not None and 2.5 <= r["rr_real"] < 4.0),
                (">=4 far", lambda r: r["rr_real"] is not None and r["rr_real"] >= 4.0),
            ],
        ),
        "dist_R_buckets": bucket_table(
            rows,
            "dist_R",
            [
                ("no_real", lambda r: r["dist_R"] is None),
                ("<1R tight", lambda r: r["dist_R"] is not None and r["dist_R"] < 1.0),
                ("1-2R", lambda r: r["dist_R"] is not None and 1.0 <= r["dist_R"] < 2.0),
                ("2-3R", lambda r: r["dist_R"] is not None and 2.0 <= r["dist_R"] < 3.0),
                (">=3R far", lambda r: r["dist_R"] is not None and r["dist_R"] >= 3.0),
            ],
        ),
        "wall_in_1R": {
            "yes": rate(rows, lambda r: r["wall_in_1R"]),
            "no": rate(rows, lambda r: not r["wall_in_1R"]),
        },
        "far_empty": {
            "yes": rate(rows, lambda r: r["far_empty"]),
            "no": rate(rows, lambda r: not r["far_empty"]),
        },
        "mfe_vs_planned": {
            "wins_avg_mfe_R": round(float(np.mean([r["mfe_R"] for r in wins])), 3) if wins else None,
            "loss_avg_mfe_R": round(float(np.mean([r["mfe_R"] for r in losses])), 3) if losses else None,
            "wins_avg_rr_real": round(
                float(np.mean([r["rr_real"] for r in wins if r["rr_real"] is not None])), 3
            )
            if any(r["rr_real"] is not None for r in wins)
            else None,
            "loss_avg_rr_real": round(
                float(np.mean([r["rr_real"] for r in losses if r["rr_real"] is not None])), 3
            )
            if any(r["rr_real"] is not None for r in losses)
            else None,
            "corr_rr_real_vs_R": None,
        },
    }
    pair = [(r["rr_real"], r["R"]) for r in rows if r["rr_real"] is not None]
    if len(pair) >= 5:
        xs = np.array([p[0] for p in pair], dtype=float)
        ys = np.array([p[1] for p in pair], dtype=float)
        if np.std(xs) > 1e-9 and np.std(ys) > 1e-9:
            why["mfe_vs_planned"]["corr_rr_real_vs_R"] = round(float(np.corrcoef(xs, ys)[0, 1]), 3)

    print("Autopsy kill reasons (wins):", why["killed_by_rr_acc_15"]["kill_reasons_wins"], flush=True)
    print("dist_R buckets:", why["dist_R_buckets"], flush=True)

    # ---- retest gates ----
    print("Retest gates …", flush=True)
    retest = []
    # native gates
    for cfg in [
        replace(base_cfg, name="BASE_pa_no_trap"),
        replace(base_cfg, name="rr_acc_15", sr_gate="rr_accurate", require_real_target=True, min_rr=1.5),
    ]:
        calls = [c for c in pa.scan_session(frame, settle=True, cfg=cfg) if c.day in score_days]
        sc = score(calls)
        retest.append({"name": cfg.name, **sc})
        print(f"  {cfg.name}: n={sc['n']} hit={sc['hit']} sum={sc['sum']}", flush=True)

    for gname, gfn in CUSTOM_GATES.items():
        if gfn is None:
            continue
        cfg = replace(base_cfg, name=gname, min_rr=1.5)
        calls = scan_with_custom_gate(frame, score_days, cfg, gfn)
        sc = score(calls)
        retest.append({"name": gname, **sc})
        print(f"  {gname}: n={sc['n']} hit={sc['hit']} sum={sc['sum']}", flush=True)

    # rank: prefer hit then sum then avgR; must not wreck sum vs base badly
    ranked = sorted(retest, key=lambda r: (r["hit"], r["sum"], r["avgR"]), reverse=True)

    # markdown
    lines = [
        "# Why R:R-accurate failed · autopsy + retest · NIFTY 20d",
        "",
        f"**Window:** `{days[0]}` → `{days[-1]}` · live lock `{base_cfg.name}` unchanged.",
        "",
        "## 1) Why `rr_accurate` hurt",
        "",
        f"- BASE: n={base_sc['n']} hit={base_sc['hit']}% avgR={base_sc['avgR']} sum={base_sc['sum']}",
        f"- rr_acc would **keep** {why['killed_by_rr_acc_15']['n_kept']} / **kill** {why['killed_by_rr_acc_15']['n_killed']}",
        f"- Of kills: **{why['killed_by_rr_acc_15']['killed_wins']} winners** removed, "
        f"{why['killed_by_rr_acc_15']['killed_losses']} losers removed",
        f"- Kill reasons (wins): `{why['killed_by_rr_acc_15']['kill_reasons_wins']}`",
        f"- Kill reasons (losses): `{why['killed_by_rr_acc_15']['kill_reasons_losses']}`",
        "",
        "### Real target presence",
        "",
        f"- Wins with real tgt: **{why['real_target']['wins_pct_real']}%** · "
        f"Losses with real tgt: **{why['real_target']['loss_pct_real']}%**",
        f"- Book **with** real tgt: {why['real_target']['all']}",
        f"- Book **without** real tgt: {why['real_target']['no_real']}",
        "",
        "### Planned real RR buckets (only rows with real tgt)",
        "",
        "| Bucket | N | Hit% | AvgR | Sum | Hit1R% |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for b in why["rr_real_buckets"]:
        lines.append(
            f"| {b['bucket']} | {b['n']} | {b['hit']} | {b['avgR']} | {b['sum']} | {b['hit_1R']} |"
        )
    lines += [
        "",
        "### Distance to nearest opposing level (R units)",
        "",
        "| Bucket | N | Hit% | AvgR | Sum | Hit1R% |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for b in why["dist_R_buckets"]:
        lines.append(
            f"| {b['bucket']} | {b['n']} | {b['hit']} | {b['avgR']} | {b['sum']} | {b['hit_1R']} |"
        )
    lines += [
        "",
        "### Path / emptiness checks",
        "",
        f"- Wall inside 1R **yes**: {why['wall_in_1R']['yes']}",
        f"- Wall inside 1R **no**: {why['wall_in_1R']['no']}",
        f"- Far empty (≥3R) **yes**: {why['far_empty']['yes']}",
        f"- Far empty **no**: {why['far_empty']['no']}",
        "",
        "### Planned RR vs realized",
        "",
        f"- Wins avg MFE_R={why['mfe_vs_planned']['wins_avg_mfe_R']} · "
        f"avg planned RR_real={why['mfe_vs_planned']['wins_avg_rr_real']}",
        f"- Loss avg MFE_R={why['mfe_vs_planned']['loss_avg_mfe_R']} · "
        f"avg planned RR_real={why['mfe_vs_planned']['loss_avg_rr_real']}",
        f"- Corr(planned RR_real, realized R) = **{why['mfe_vs_planned']['corr_rr_real_vs_R']}**",
        "",
        "## Root cause (plain)",
        "",
        "1. This book **pays via trail@1R**, not by hitting a far S/R target — so large planned R:R ≠ edge.",
        "2. Requiring a **real far opposing level** kills many winners that had **no nearby S/R** (open air) but still worked.",
        "3. High planned RR often = **far empty air**; those rows reverse more → losses show *higher* planned RR than wins.",
        "4. Useful R:R for this system ≈ **room to reach +1R without a wall**, not distance to PDH/range extreme.",
        "",
        "## 2) Retest — better R:R definitions",
        "",
        "| Logic | N | Hit% | AvgR | Sum | Hit1R% | Hard SL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in retest:
        lines.append(
            f"| `{r['name']}` | {r['n']} | {r['hit']} | {r['avgR']} | {r['sum']} | {r['hit_1R']} | {r['hard_sl']} |"
        )
    best = ranked[0]
    lines += [
        "",
        f"**Best on this window (hit→sum→avgR):** `{best['name']}` "
        f"n={best['n']} hit={best['hit']}% sum={best['sum']}",
        "",
        "Live lock **not** wired. Prefer a gate that lifts hit without collapsing sum vs BASE.",
        "",
    ]
    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    JS.write_text(
        json.dumps(
            {"days": days, "why": why, "retest": retest, "rows": rows, "ranked": ranked},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote {MD}", flush=True)


if __name__ == "__main__":
    main()
