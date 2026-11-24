"""Score a historical audit run honestly: base-rate baselines and paper P&L.

Raw "label_correct" accuracy is misleading here. It counts a HOLD as wrong whenever the
market happened to move, and it flatters a model that simply matches the market's drift.
This module reports the numbers that decide whether a signal is tradeable:
  * hit rate restricted to days the model made a directional call AND price actually moved
  * the always-long baseline on those same days
  * the same split per signal_quality bucket
  * paper P&L for a single quality bucket, after costs
"""

from __future__ import annotations

import math
import os
import sqlite3
from typing import Any, Dict, List, Optional

QUALITIES = ("HIGH", "MEDIUM", "LOW")


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    conn.row_factory = sqlite3.Row
    return conn


def _fetch(db_path: str, audit_run_id: int) -> List[sqlite3.Row]:
    if not os.path.isfile(db_path):
        return []
    conn = _connect(db_path)
    try:
        return conn.execute(
            """
            SELECT stock, as_of_date, predicted_decision, predicted_side, signal_quality,
                   signals_agree, ml_probability, technical_score, combined_score,
                   knowledge_adjust, news_count, actual_return_1d, actual_side, label_correct,
                   base_rate, confidence_lift
            FROM daily_audit_outcomes
            WHERE audit_run_id = ?
            ORDER BY as_of_date, stock
            """,
            (audit_run_id,),
        ).fetchall()
    finally:
        conn.close()


def _hit_rate(rows: List[sqlite3.Row]) -> Optional[float]:
    if not rows:
        return None
    hits = sum(1 for r in rows if r["predicted_side"] == r["actual_side"])
    return hits / len(rows)


def slice_run(db_path: str, audit_run_id: int) -> Dict[str, Any]:
    """Break a run into the slices that actually say whether the model has an edge."""
    rows = _fetch(db_path, audit_run_id)
    if not rows:
        return {"audit_run_id": audit_run_id, "error": "no outcomes for run"}

    decisions: Dict[str, int] = {}
    pred_sides: Dict[str, int] = {}
    actual_sides: Dict[str, int] = {}
    for r in rows:
        decisions[r["predicted_decision"]] = decisions.get(r["predicted_decision"], 0) + 1
        pred_sides[r["predicted_side"]] = pred_sides.get(r["predicted_side"], 0) + 1
        actual_sides[r["actual_side"]] = actual_sides.get(r["actual_side"], 0) + 1

    actionable = [r for r in rows if r["predicted_side"] in ("UP", "DOWN")]
    moved = [r for r in actionable if r["actual_side"] in ("UP", "DOWN")]

    by_quality: Dict[str, Any] = {}
    for q in QUALITIES:
        subset = [r for r in moved if (r["signal_quality"] or "LOW") == q]
        by_quality[q] = {"n": len(subset), "hit_rate": _hit_rate(subset)}

    all_moved = [r for r in rows if r["actual_side"] in ("UP", "DOWN")]
    always_up = (
        sum(1 for r in all_moved if r["actual_side"] == "UP") / len(all_moved)
        if all_moved else None
    )

    bullish = sum(v for k, v in decisions.items() if "BUY" in k)
    bearish = sum(v for k, v in decisions.items() if "SELL" in k)
    return {
        "audit_run_id": audit_run_id,
        "total": len(rows),
        "decision_counts": decisions,
        "predicted_sides": pred_sides,
        "actual_sides": actual_sides,
        "bullish_calls": bullish,
        "bearish_calls": bearish,
        "direction_balance": (
            round(abs(bullish - bearish) / max(bullish, bearish), 4)
            if max(bullish, bearish) else None
        ),
        "raw_label_accuracy": sum(r["label_correct"] for r in rows) / len(rows),
        "flat_share": pred_sides.get("FLAT", 0) / len(rows),
        "actionable": len(actionable),
        "actionable_with_move": len(moved),
        "actionable_hit_rate": _hit_rate(moved),
        "by_quality": by_quality,
        "baseline_always_up": always_up,
        "edge_vs_baseline": (
            round(_hit_rate(moved) - always_up, 4)
            if moved and always_up is not None else None
        ),
        "knowledge_adjust_active": sum(
            1 for r in rows if abs(r["knowledge_adjust"] or 0) > 1e-4
        ),
        "days_with_news": sum(1 for r in rows if (r["news_count"] or 0) > 0),
    }


def paper_pnl(
    db_path: str,
    audit_run_id: int,
    quality: str = "HIGH",
    cost_bps: float = 5.0,
    allow_short: bool = True,
) -> Dict[str, Any]:
    """Next-close paper P&L for one quality bucket. cost_bps is charged per round trip."""
    rows = [
        r for r in _fetch(db_path, audit_run_id)
        if (r["signal_quality"] or "LOW") == quality and r["predicted_side"] in ("UP", "DOWN")
    ]
    if not rows:
        return {"quality": quality, "trades": 0, "error": "no trades in bucket"}

    trades: List[Dict[str, Any]] = []
    for r in rows:
        ret = float(r["actual_return_1d"] or 0.0)
        if r["predicted_side"] == "DOWN":
            if not allow_short:
                continue
            pnl = -ret
        else:
            pnl = ret
        trades.append({
            "date": r["as_of_date"],
            "stock": r["stock"],
            "side": r["predicted_side"],
            "gross_pct": pnl,
            "net_pct": pnl - cost_bps / 100.0,
        })
    if not trades:
        return {"quality": quality, "trades": 0, "error": "no trades after filters"}

    nets = [t["net_pct"] for t in trades]
    equity, peak, max_dd = 0.0, 0.0, 0.0
    for p in nets:
        equity += p
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)

    mean = sum(nets) / len(nets)
    var = sum((p - mean) ** 2 for p in nets) / (len(nets) - 1) if len(nets) > 1 else 0.0
    sd = math.sqrt(var)
    wins = [p for p in nets if p > 0]
    losses = [p for p in nets if p < 0]
    return {
        "quality": quality,
        "cost_bps_per_trade": cost_bps,
        "trades": len(trades),
        "long_trades": sum(1 for t in trades if t["side"] == "UP"),
        "short_trades": sum(1 for t in trades if t["side"] == "DOWN"),
        "win_rate": len(wins) / len(trades),
        "total_net_pct": round(sum(nets), 3),
        "avg_net_pct_per_trade": round(mean, 4),
        "median_net_pct": round(sorted(nets)[len(nets) // 2], 4),
        "best_pct": round(max(nets), 3),
        "worst_pct": round(min(nets), 3),
        "avg_win_pct": round(sum(wins) / len(wins), 4) if wins else 0.0,
        "avg_loss_pct": round(sum(losses) / len(losses), 4) if losses else 0.0,
        "profit_factor": (
            round(sum(wins) / abs(sum(losses)), 3) if losses and sum(losses) else None
        ),
        # Per-trade Sharpe scaled to a ~250-trade year; indicative, not annualised truth.
        "sharpe_like": round(mean / sd * math.sqrt(250), 3) if sd > 0 else None,
        "max_drawdown_pct": round(max_dd, 3),
    }


def lift_sweep(
    db_path: str,
    audit_run_id: int,
    thresholds=(0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0),
    cost_bps: float = 5.0,
) -> List[Dict[str, Any]]:
    """Hit rate and P&L as the confidence bar rises, so the gate is chosen from data.

    A usable gate should show hit rate climbing monotonically with the threshold; if it
    does not, the confidence measure is not ranking days by genuine information.
    """
    rows = [
        r for r in _fetch(db_path, audit_run_id)
        if r["predicted_side"] in ("UP", "DOWN") and r["confidence_lift"] is not None
    ]
    out = []
    for thr in thresholds:
        subset = [r for r in rows if abs(r["confidence_lift"]) >= thr]
        moved = [r for r in subset if r["actual_side"] in ("UP", "DOWN")]
        nets = [
            (r["actual_return_1d"] or 0.0) * (1 if r["predicted_side"] == "UP" else -1)
            - cost_bps / 100.0
            for r in subset
        ]
        out.append({
            "min_lift": thr,
            "trades": len(subset),
            "moved": len(moved),
            "hit_rate": _hit_rate(moved),
            "total_net_pct": round(sum(nets), 2) if nets else None,
            "avg_net_pct": round(sum(nets) / len(nets), 4) if nets else None,
        })
    return out


def full_report(db_path: str, audit_run_id: int, cost_bps: float = 5.0) -> Dict[str, Any]:
    out = slice_run(db_path, audit_run_id)
    if "error" in out:
        return out
    out["paper_pnl"] = {q: paper_pnl(db_path, audit_run_id, q, cost_bps) for q in QUALITIES}
    out["lift_sweep"] = lift_sweep(db_path, audit_run_id, cost_bps=cost_bps)
    return out


def compare_runs(db_path: str, run_a: int, run_b: int) -> Dict[str, Any]:
    """Before/after view of two runs over the same window."""
    a, b = slice_run(db_path, run_a), slice_run(db_path, run_b)
    if "error" in a or "error" in b:
        return {"error": "one or both runs have no outcomes", "a": a, "b": b}
    keys = [
        "total", "raw_label_accuracy", "flat_share", "bullish_calls", "bearish_calls",
        "direction_balance", "actionable_with_move", "actionable_hit_rate",
        "baseline_always_up", "edge_vs_baseline",
    ]
    return {
        "run_a": run_a,
        "run_b": run_b,
        "metrics": {k: {"a": a.get(k), "b": b.get(k)} for k in keys},
        "high_quality": {"a": a["by_quality"]["HIGH"], "b": b["by_quality"]["HIGH"]},
    }


def format_report(report: Dict[str, Any]) -> str:
    if "error" in report:
        return f"Audit run {report.get('audit_run_id')}: {report['error']}"
    lines = [
        f"Audit run {report['audit_run_id']} — {report['total']} day-decisions",
        f"  raw label accuracy    {report['raw_label_accuracy']:.1%}  (counts HOLD-on-a-moving-day as wrong)",
        f"  HOLD share            {report['flat_share']:.1%}",
        f"  calls                 {report['bullish_calls']} bullish / {report['bearish_calls']} bearish"
        f"  (imbalance {report['direction_balance']:.1%})" if report["direction_balance"] is not None else "",
        f"  actionable + moved    n={report['actionable_with_move']}",
    ]
    if report["actionable_hit_rate"] is not None:
        lines.append(f"  hit rate              {report['actionable_hit_rate']:.1%}")
    if report["baseline_always_up"] is not None:
        lines.append(f"  always-long baseline  {report['baseline_always_up']:.1%}")
    if report["edge_vs_baseline"] is not None:
        lines.append(f"  edge vs baseline      {report['edge_vs_baseline']:+.1%}")
    for q in QUALITIES:
        b = report["by_quality"][q]
        if b["n"]:
            lines.append(f"    {q:<7} n={b['n']:<5} hit {b['hit_rate']:.1%}")
    sweep = [s for s in report.get("lift_sweep", []) if s["trades"]]
    if sweep:
        lines.append("  confidence sweep (min |lift| -> trades / hit / net):")
        for s in sweep:
            hit = f"{s['hit_rate']:.1%}" if s["hit_rate"] is not None else "n/a"
            lines.append(
                f"    >={s['min_lift']:<5} n={s['trades']:<5} hit {hit:<7} net {s['total_net_pct']:+.1f}%"
            )
    pnl = report.get("paper_pnl", {})
    for q in QUALITIES:
        p = pnl.get(q) or {}
        if p.get("trades"):
            lines.append(
                f"  paper P&L {q:<7} {p['trades']} trades, win {p['win_rate']:.1%}, "
                f"net {p['total_net_pct']:+.1f}%, avg {p['avg_net_pct_per_trade']:+.3f}%/trade, "
                f"maxDD {p['max_drawdown_pct']:.1f}%"
            )
    return "\n".join(l for l in lines if l)
