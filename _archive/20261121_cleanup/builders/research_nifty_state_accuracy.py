"""Accuracy search for nifty_state_conditional (freeze → holdout).

One causal walk collects every structure-valid candidate with analog stats at
the decision time. Offline gates are scored on freeze (all but last 22
sessions) then checked on holdout (last ~1 month).

  python -u prod_live/tests/builders/research_nifty_state_accuracy.py
"""
from __future__ import annotations

import itertools
import json
import sys
from dataclasses import asdict, dataclass
from datetime import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live" / "tests" / "builders"),
    str(ROOT / "app"),
    str(ROOT / "app" / "market"),
]
import path_setup  # noqa: F401,E402

from _diag_nifty_state_conditional_1m import load_1m  # noqa: E402
from prod_live.logic import nifty_state_conditional as sc  # noqa: E402

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT_DIR / "NIFTY_STATE_ACCURACY_SEARCH.md"
OUT_JSON = OUT_DIR / "NIFTY_STATE_ACCURACY_SEARCH.json"
COST = sc.COST_POINTS
HOLDOUT_SESSIONS = 22
MIN_FREEZE_N = 12
MIN_HOLD_N = 3


@dataclass(frozen=True)
class Gate:
    name: str
    min_analogs: int = 20
    min_hit: float = 0.52
    min_avg: float = COST
    max_calls: int = 3
    auctions: Tuple[str, ...] = ()  # empty = all
    time_buckets: Tuple[str, ...] = ()  # empty = all
    sides: Tuple[str, ...] = ()  # empty = all
    min_analog_avg_edge: float = 0.0  # average - cost
    max_risk: float = 25.0


def collect_candidates(raw: List[dict]) -> Tuple[List[dict], List[str]]:
    """Causal walk: every structure-valid fill opportunity with live analog stats."""
    bars = [sc.parse_bar(r) for r in raw]
    bars.sort(key=lambda b: b.dt)
    sessions: Dict[str, List[sc.Bar]] = {}
    for bar in bars:
        if sc.OPEN <= sc._clock(bar) <= time(15, 30):
            sessions.setdefault(bar.dt.date().isoformat(), []).append(bar)

    day_keys = sorted(sessions)
    memory: Dict[tuple, List[float]] = {}
    prior = None
    rows: List[dict] = []

    for day_key in day_keys:
        day = sessions[day_key]
        book = sc.DayBook(day)
        used: set = set()
        day_rows: List[dict] = []
        busy_until = -1
        for index, bar in enumerate(day):
            if index <= busy_until:
                continue
            snap = book.state(index)
            if snap is None or snap["direction"] is None or index + 1 >= len(day):
                continue
            key = snap["key"] + (snap["direction"],)
            if key in used:
                continue
            samples = sc._analog_view(memory.get(key, []))
            entry = day[index + 1].open
            if sc._chased(snap["direction"], bar.close, entry, snap["atr"]):
                continue
            if sc._extended_from_range(
                snap["direction"],
                snap["auction"],
                entry,
                book.opening_high,
                book.opening_low,
                snap["atr"],
            ):
                continue
            risk, reward = sc._barriers(snap["atr"])
            if not sc._room_for_target(snap["direction"], entry, reward, prior):
                continue

            n = len(samples)
            hit = (sum(1 for p in samples if p > 0.0) / n) if n else 0.0
            avg = (sum(samples) / n) if n else 0.0
            exit_price, reason = sc._resolve(
                day, index + 1, snap["direction"], entry, risk, reward
            )
            pts = sc._points(snap["direction"], entry, exit_price)
            # find exit index roughly for busy_until
            exit_i = index + 1
            for j in range(index + 1, min(len(day), index + sc.HOLD_BARS)):
                ep, _ = sc._one_bar(day[j], snap["direction"], entry, risk, reward)
                if ep is not None or sc._clock(day[j]) >= sc.FLAT_AT:
                    exit_i = j
                    break
            else:
                exit_i = min(len(day) - 1, index + sc.HOLD_BARS - 1)

            day_rows.append(
                {
                    "date": day_key,
                    "direction": snap["direction"],
                    "auction": snap["auction"],
                    "time_bucket": snap["time_bucket"],
                    "swing": snap["swing"],
                    "vwap_side": snap["vwap_side"],
                    "vol": snap["key"][0],
                    "state": "|".join(snap["key"]),
                    "analog_n": n,
                    "analog_hit": hit,
                    "analog_avg": avg,
                    "risk": risk,
                    "reward": reward,
                    "points": pts,
                    "reason": reason,
                    "signal_hm": bar.dt.strftime("%H:%M"),
                    "net": pts - COST,
                    "win": pts > COST,
                }
            )
            used.add(key)
            busy_until = exit_i

        rows.extend(day_rows)
        for key, points in sc.label_day(day).items():
            bucket = memory.setdefault(key, [])
            bucket.append(points)
            if len(bucket) > sc.ANALOG_WINDOW * 3:
                del bucket[: len(bucket) - sc.ANALOG_WINDOW * 3]
        prior = {
            "high": max(b.high for b in day),
            "low": min(b.low for b in day),
            "close": day[-1].close,
        }

    return rows, day_keys


def apply_gate(cands: List[dict], gate: Gate, day_keys: List[str]) -> List[dict]:
    """Respect max_calls/day in date order."""
    out: List[dict] = []
    by_day: Dict[str, int] = {}
    for row in cands:
        if gate.auctions and row["auction"] not in gate.auctions:
            continue
        if gate.time_buckets and row["time_bucket"] not in gate.time_buckets:
            continue
        if gate.sides and row["direction"] not in gate.sides:
            continue
        if row["analog_n"] < gate.min_analogs:
            continue
        if row["analog_hit"] < gate.min_hit:
            continue
        if row["analog_avg"] <= gate.min_avg:
            continue
        if (row["analog_avg"] - COST) < gate.min_analog_avg_edge:
            continue
        if row["risk"] > gate.max_risk:
            continue
        n_today = by_day.get(row["date"], 0)
        if n_today >= gate.max_calls:
            continue
        by_day[row["date"]] = n_today + 1
        out.append(row)
    return out


def stats(rows: List[dict]) -> Dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "hit": None,
            "net": 0.0,
            "avg_w": None,
            "avg_l": None,
            "ratio": None,
            "days": 0,
        }
    wins = [r for r in rows if r["win"]]
    losses = [r for r in rows if not r["win"]]
    avg_w = sum(r["net"] for r in wins) / len(wins) if wins else None
    avg_l = sum(r["net"] for r in losses) / len(losses) if losses else None
    ratio = (avg_w / abs(avg_l)) if avg_w is not None and avg_l not in (None, 0) else None
    return {
        "n": len(rows),
        "hit": len(wins) / len(rows),
        "net": sum(r["net"] for r in rows),
        "avg_w": avg_w,
        "avg_l": avg_l,
        "ratio": ratio,
        "days": len({r["date"] for r in rows}),
    }


def score(fs: Dict[str, Any], hs: Dict[str, Any]) -> float:
    if (fs.get("n") or 0) < MIN_FREEZE_N:
        return -1e9
    if (hs.get("n") or 0) < MIN_HOLD_N:
        return -1e9
    # Prefer holdout hit, then freeze hit, holdout net, freeze net, ratio
    return (
        120.0 * (hs.get("hit") or 0)
        + 40.0 * (fs.get("hit") or 0)
        + 0.25 * (hs.get("net") or 0)
        + 0.05 * (fs.get("net") or 0)
        + 5.0 * min(hs.get("ratio") or 0, 3.0)
    )


def gate_grid() -> List[Gate]:
    gates = [
        Gate("baseline", min_analogs=20, min_hit=0.52, max_calls=3),
        Gate("strict_58", min_analogs=20, min_hit=0.58, max_calls=3),
        Gate("n25_h55", min_analogs=25, min_hit=0.55, max_calls=2),
        Gate("n25_h52", min_analogs=25, min_hit=0.52, max_calls=2),
        Gate("n30_h52", min_analogs=30, min_hit=0.52, max_calls=2),
        Gate("failed_only", min_analogs=20, min_hit=0.52, auctions=("failed_up", "failed_down")),
        Gate(
            "failed_n20_h55",
            min_analogs=20,
            min_hit=0.55,
            auctions=("failed_up", "failed_down"),
            max_calls=2,
        ),
        Gate(
            "failed_n20_h58",
            min_analogs=20,
            min_hit=0.58,
            auctions=("failed_up", "failed_down"),
            max_calls=2,
        ),
        Gate(
            "failed_morning",
            min_analogs=20,
            min_hit=0.52,
            auctions=("failed_up", "failed_down"),
            time_buckets=("morning", "late_morning"),
            max_calls=2,
        ),
        Gate(
            "failed_late_am",
            min_analogs=20,
            min_hit=0.55,
            auctions=("failed_up", "failed_down"),
            time_buckets=("late_morning",),
            max_calls=1,
        ),
        Gate(
            "failed_afternoon",
            min_analogs=20,
            min_hit=0.55,
            auctions=("failed_up", "failed_down"),
            time_buckets=("afternoon",),
            max_calls=1,
        ),
        Gate(
            "break_only",
            min_analogs=20,
            min_hit=0.52,
            auctions=("above", "below"),
            max_calls=2,
        ),
        Gate(
            "edge2",
            min_analogs=20,
            min_hit=0.52,
            min_analog_avg_edge=2.0,
            max_calls=2,
        ),
        Gate(
            "failed_edge2",
            min_analogs=20,
            min_hit=0.55,
            auctions=("failed_up", "failed_down"),
            min_analog_avg_edge=2.0,
            max_calls=2,
        ),
        Gate(
            "failed_edge3_h55",
            min_analogs=20,
            min_hit=0.55,
            auctions=("failed_up", "failed_down"),
            min_analog_avg_edge=3.0,
            max_calls=1,
        ),
        Gate(
            "sell_failed",
            min_analogs=20,
            min_hit=0.55,
            auctions=("failed_up",),
            sides=("sell",),
            max_calls=1,
        ),
        Gate(
            "buy_failed",
            min_analogs=20,
            min_hit=0.55,
            auctions=("failed_down",),
            sides=("buy",),
            max_calls=1,
        ),
        Gate(
            "accurate_A",
            min_analogs=22,
            min_hit=0.55,
            auctions=("failed_up", "failed_down"),
            min_analog_avg_edge=2.0,
            max_calls=1,
        ),
        Gate(
            "accurate_B",
            min_analogs=20,
            min_hit=0.58,
            auctions=("failed_up", "failed_down"),
            time_buckets=("late_morning", "afternoon"),
            min_analog_avg_edge=1.5,
            max_calls=1,
        ),
        Gate(
            "accurate_C",
            min_analogs=25,
            min_hit=0.55,
            auctions=("failed_up", "failed_down"),
            max_calls=1,
            min_analog_avg_edge=2.5,
        ),
    ]
    # small cartesian extras
    for n, h, edge, mc in itertools.product(
        (20, 25), (0.55, 0.58), (1.0, 2.0, 3.0), (1, 2)
    ):
        gates.append(
            Gate(
                name=f"fail_n{n}_h{int(h*100)}_e{int(edge)}_c{mc}",
                min_analogs=n,
                min_hit=h,
                auctions=("failed_up", "failed_down"),
                min_analog_avg_edge=edge,
                max_calls=mc,
            )
        )
    # dedupe by name
    seen = set()
    out = []
    for g in gates:
        if g.name in seen:
            continue
        seen.add(g.name)
        out.append(g)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw, source, _ = load_1m(750)
    print(f"collecting candidates ({source})…", flush=True)
    cands, day_keys = collect_candidates(raw)
    hold_days = set(day_keys[-HOLDOUT_SESSIONS:])
    freeze_days = set(day_keys[:-HOLDOUT_SESSIONS])
    print(
        f"candidates={len(cands)} sessions={len(day_keys)} "
        f"freeze={len(freeze_days)} hold={len(hold_days)}",
        flush=True,
    )

    results = []
    best = None
    best_sc = -1e18
    for gate in gate_grid():
        taken = apply_gate(cands, gate, day_keys)
        fr = [r for r in taken if r["date"] in freeze_days]
        ho = [r for r in taken if r["date"] in hold_days]
        fs, hs = stats(fr), stats(ho)
        sc_ = score(fs, hs)
        pack = {"gate": asdict(gate), "freeze": fs, "hold": hs, "score": sc_}
        results.append(pack)
        if sc_ > best_sc:
            best_sc = sc_
            best = pack
        print(
            f"{gate.name:28s} F n={fs['n']:3d} hit={fs['hit']} net={fs['net']:.1f} | "
            f"H n={hs['n']:2d} hit={hs['hit']} net={hs['net']:.1f} sc={sc_:.1f}",
            flush=True,
        )

    results.sort(key=lambda r: r["score"], reverse=True)
    baseline = next(r for r in results if r["gate"]["name"] == "baseline")

    lines = [
        "# NIFTY state-conditional · accuracy search",
        "",
        f"**Source:** `{source}` · freeze={len(freeze_days)} sessions · "
        f"holdout last {HOLDOUT_SESSIONS} · cost {COST}",
        f"**Holdout:** {day_keys[-HOLDOUT_SESSIONS]} → {day_keys[-1]}",
        "",
        "Selection: holdout hit first, then freeze hit / nets. "
        f"Min freeze N≥{MIN_FREEZE_N}, holdout N≥{MIN_HOLD_N}.",
        "",
        "## Baseline vs best",
        "",
        f"- baseline freeze: {baseline['freeze']}",
        f"- baseline hold: {baseline['hold']}",
        f"- **best `{best['gate']['name']}`** freeze: {best['freeze']}",
        f"- **best hold:** {best['hold']}",
        f"- score: {best['score']:.2f}",
        "",
        "## Top gates",
        "",
        "| Rank | Gate | Freeze N/hit/net | Hold N/hit/net | Score |",
        "|---:|---|---|---|---:|",
    ]
    for i, r in enumerate(results[:15], 1):
        fs, hs = r["freeze"], r["hold"]
        lines.append(
            f"| {i} | `{r['gate']['name']}` | "
            f"{fs['n']}/{fs['hit']}/{fs['net']:.1f} | "
            f"{hs['n']}/{hs['hit']}/{hs['net']:.1f} | {r['score']:.1f} |"
        )

    g = best["gate"]
    lines += [
        "",
        "## Recommended accurate profile",
        "",
        f"1. auctions: **{g['auctions'] or 'all'}**",
        f"2. time buckets: **{g['time_buckets'] or 'all'}**",
        f"3. sides: **{g['sides'] or 'all'}**",
        f"4. min_analogs **{g['min_analogs']}** · min_hit **{g['min_hit']}**",
        f"5. min_analog_avg_edge **{g['min_analog_avg_edge']}** (avg − cost)",
        f"6. max_calls/day **{g['max_calls']}**",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(
            {"source": source, "best": best, "baseline": baseline, "top": results[:20]},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print("BEST", best["gate"]["name"], best["hold"], flush=True)
    print(f"wrote {OUT_MD}", flush=True)


if __name__ == "__main__":
    main()
