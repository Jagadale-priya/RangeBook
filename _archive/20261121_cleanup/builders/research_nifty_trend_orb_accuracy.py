"""Find higher-accuracy gates on trend-stay + ORB structure.

Freeze: older sessions · Holdout: last 20 sessions.
Does not invent a new strategy — only additive filters on the frozen shapes.

  python -u prod_live/tests/builders/research_nifty_trend_orb_accuracy.py
"""
from __future__ import annotations

import itertools
import json
import sys
from dataclasses import asdict, dataclass
from datetime import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live" / "tests" / "builders"),
    str(ROOT / "app"),
    str(ROOT / "app" / "market"),
]
import path_setup  # noqa: F401,E402

from _diag_nifty_orb30_vwap_last10d import load_5m, last_n_sessions  # noqa: E402
import prod_live.logic.nifty_trend_stay as ts  # noqa: E402
import prod_live.logic.nifty_orb30_vwap_fut as orb  # noqa: E402

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT_DIR / "NIFTY_TREND_ORB_ACCURACY_SEARCH.md"
OUT_JSON = OUT_DIR / "NIFTY_TREND_ORB_ACCURACY_SEARCH.json"
COST = 1.0
HOLDOUT_N = 20
MIN_FREEZE_CALLS = 8
MIN_HOLD_CALLS = 3


@dataclass(frozen=True)
class TrendGate:
    name: str
    min_width: float = 25.0
    max_width: float = 160.0
    last_signal: str = "13:30"  # HH:MM on 15m bucket start
    max_break_ext: float = 999.0  # pts past IBH/IBL on signal close
    max_risk: float = 40.0
    max_entry_ext: float = 999.0  # |entry - level|
    min_vwap_sep: float = 0.0  # |close - vwap| at signal
    stop_buffer: float = 15.0
    max_chase: float = 25.0


@dataclass(frozen=True)
class OrbGate:
    name: str
    min_width: float = 30.0
    max_width: float = 90.0
    last_signal: str = "14:45"
    at_level_only: bool = False
    max_entry_ext: float = 10.0


def _hm(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def _parse_hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def evaluate_trend_gated(day: pd.DataFrame, gate: TrendGate) -> ts.TrendCall:
    """Same long-stay shape with research gates applied."""
    date = pd.Timestamp(day.index[0]).normalize()
    clock = day.index.time
    balance = day[(clock >= ts.BALANCE_START) & (clock < ts.BALANCE_END)]
    if balance.empty:
        return ts._blank(date, "missing_balance")

    balance_high = float(balance["high"].max())
    balance_low = float(balance["low"].min())
    width = balance_high - balance_low
    levels = {
        "balance_high": balance_high,
        "balance_low": balance_low,
        "balance_width": width,
    }
    if width < gate.min_width or width > gate.max_width:
        return ts._blank(date, "balance_width_out_of_range", **levels)

    vwap = ts._vwap(day)
    bars = ts._fifteen_minute(day, vwap)
    last_sig = _parse_hm(gate.last_signal)
    candidates = bars[(bars.index.time >= ts.BALANCE_END) & (bars.index.time < last_sig)]

    for signal_time, signal in candidates.iterrows():
        close = float(signal["close"])
        fair = float(signal["vwap"])
        buy_break = close > balance_high and close > fair
        sell_break = close < balance_low and close < fair
        if not buy_break and not sell_break:
            continue
        direction = "buy" if buy_break else "sell"
        level = balance_high if direction == "buy" else balance_low
        ext = abs(close - level)
        if ext > gate.max_break_ext:
            continue
        if abs(close - fair) < gate.min_vwap_sep:
            continue

        later = day[day.index > signal_time + pd.Timedelta(minutes=14)]
        entry_time = None
        entry = None
        touched = False
        ran_away = False
        for bar_time, bar in later.iterrows():
            if bar_time.time() >= ts.LAST_ENTRY:
                break
            if direction == "buy":
                if float(bar["high"]) >= balance_high + gate.max_chase and not touched:
                    ran_away = True
                    break
                if float(bar["low"]) <= balance_high + ts.TOUCH_BUFFER:
                    touched = True
                if (
                    touched
                    and float(bar["close"]) > balance_high
                    and float(bar["close"]) > float(vwap.loc[bar_time])
                ):
                    entry_time = bar_time
                    entry = float(bar["close"])
                    break
            else:
                if float(bar["low"]) <= balance_low - gate.max_chase and not touched:
                    ran_away = True
                    break
                if float(bar["high"]) >= balance_low - ts.TOUCH_BUFFER:
                    touched = True
                if (
                    touched
                    and float(bar["close"]) < balance_low
                    and float(bar["close"]) < float(vwap.loc[bar_time])
                ):
                    entry_time = bar_time
                    entry = float(bar["close"])
                    break

        if entry is None:
            if ran_away:
                return ts._blank(
                    date,
                    "price_ran_away_before_pullback",
                    direction=direction,
                    signal_time=signal_time,
                    **levels,
                )
            continue

        if abs(entry - level) > gate.max_entry_ext:
            continue

        initial_stop = (
            balance_high - gate.stop_buffer
            if direction == "buy"
            else balance_low + gate.stop_buffer
        )
        risk = entry - initial_stop if direction == "buy" else initial_stop - entry
        if risk <= 0.0 or risk > gate.max_risk:
            return ts._blank(
                date,
                "pullback_risk_out_of_range",
                direction=direction,
                signal_time=signal_time,
                entry_time=entry_time,
                entry=entry,
                initial_stop=initial_stop,
                **levels,
            )

        exit_time, exit_price, favorable, reason = ts._manage_trade(
            day, vwap, direction, entry_time, entry, initial_stop
        )
        points = exit_price - entry if direction == "buy" else entry - exit_price
        return ts.TrendCall(
            date=date,
            status=reason,
            direction=direction,
            balance_high=balance_high,
            balance_low=balance_low,
            balance_width=width,
            signal_time=signal_time,
            entry_time=entry_time,
            entry=entry,
            initial_stop=initial_stop,
            exit_time=exit_time,
            exit=exit_price,
            points=points,
            max_favorable=favorable,
            reason=reason,
            probability=None,
        )

    return ts._blank(date, "no_pullback_after_break", **levels)


def evaluate_orb_gated(day: pd.DataFrame, gate: OrbGate) -> orb.DayCall:
    date = pd.Timestamp(day.index[0]).normalize()
    clock = day.index.time
    opening = day[(clock >= orb.ORB_START) & (clock < orb.ORB_END)]
    if opening.empty:
        return orb._blank_call(date, "no_call", "missing_opening_range")

    opening_high = float(opening["high"].max())
    opening_low = float(opening["low"].min())
    width = opening_high - opening_low
    range_values = {
        "opening_high": opening_high,
        "opening_low": opening_low,
        "opening_width": width,
        "expected_range": None,
        "india_vix": None,
    }
    if width < gate.min_width or width > gate.max_width:
        return orb._blank_call(date, "no_call", "opening_width_out_of_range", **range_values)

    later = day[clock >= orb.ORB_END]
    if later.empty:
        return orb._blank_call(date, "no_call", "no_bars_after_opening_range", **range_values)

    vwap = orb._session_vwap(day)
    last_sig = _parse_hm(gate.last_signal)

    for signal_time, bar in later.iterrows():
        if signal_time.time() >= last_sig or signal_time.time() >= orb.SESSION_END:
            break
        close = float(bar["close"])
        fair_price = float(vwap.loc[signal_time])
        buy_extension = close - opening_high
        sell_extension = opening_low - close
        buy_break = 0.0 < buy_extension <= orb.MAX_EXTENSION and close > fair_price
        sell_break = 0.0 < sell_extension <= orb.MAX_EXTENSION and close < fair_price
        if not buy_break and not sell_break:
            continue
        if buy_break and sell_break:
            direction = "buy" if buy_extension <= sell_extension else "sell"
        else:
            direction = "buy" if buy_break else "sell"

        following = day[day.index > signal_time]
        if following.empty:
            continue
        entry_time = following.index[0]
        entry_bar = following.iloc[0]
        level = opening_high if direction == "buy" else opening_low
        entry, entry_mode, entry_fail = orb._resolve_entry(direction, level, entry_bar)
        if entry is None:
            continue
        if gate.at_level_only and entry_mode != "at_level":
            continue
        if abs(entry - level) > gate.max_entry_ext:
            continue

        if direction == "buy":
            stop = opening_high - orb.STOP_POINTS
            target = entry + orb.TARGET_POINTS
        else:
            stop = opening_low + orb.STOP_POINTS
            target = entry - orb.TARGET_POINTS

        exit_time, exit_price, exit_reason = orb._resolve_exit(
            following, direction, stop, target
        )
        points = exit_price - entry if direction == "buy" else entry - exit_price
        return orb.DayCall(
            date=date,
            status=exit_reason,
            direction=direction,
            opening_high=opening_high,
            opening_low=opening_low,
            opening_width=width,
            expected_range=None,
            vwap_at_signal=fair_price,
            signal_time=signal_time,
            entry_time=entry_time,
            entry=entry,
            entry_mode=entry_mode,
            stop=stop,
            target=target,
            exit_time=exit_time,
            exit=exit_price,
            points=points,
            reason=exit_reason,
            probability=None,
            india_vix=None,
        )

    return orb._blank_call(date, "no_call", "no_valid_break", **range_values)


def _stats(calls: pd.DataFrame) -> Dict[str, Any]:
    if "points" in calls.columns:
        s = ts.summarize(calls, cost_points_per_call=COST)
    else:
        s = orb.summarize(calls, cost_points_per_call=COST)
        # normalize keys
        s = {
            "sessions": s["sessions"],
            "calls": s["calls"],
            "wins": s["wins"],
            "losses": s["losses"],
            "hit_rate": s["hit_rate"],
            "average_winner": s.get("average_win", s.get("average_winner")),
            "average_loser": s.get("average_loss", s.get("average_loser")),
            "winner_loser_ratio": (
                float(s["average_win"] / abs(s["average_loss"]))
                if s.get("average_win") is not None
                and s.get("average_loss") is not None
                and not pd.isna(s.get("average_win"))
                and not pd.isna(s.get("average_loss"))
                and s["average_loss"] != 0
                else np.nan
            ),
            "net_points": s["net_points"],
            "no_call_days": s.get("no_call_days", s["sessions"] - s["calls"]),
        }
    return {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in s.items()}


def run_trend(bars: pd.DataFrame, gate: TrendGate) -> pd.DataFrame:
    rows = [
        evaluate_trend_gated(day, gate).__dict__
        for _, day in bars.groupby(bars.index.normalize())
    ]
    return pd.DataFrame(rows)


def run_orb(bars: pd.DataFrame, gate: OrbGate) -> pd.DataFrame:
    rows = [
        evaluate_orb_gated(day, gate).__dict__
        for _, day in bars.groupby(bars.index.normalize())
    ]
    return pd.DataFrame(rows)


def split_bars(bars: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, List[pd.Timestamp]]:
    days = sorted(bars.index.normalize().unique())
    hold_days = days[-HOLDOUT_N:]
    freeze_days = days[:-HOLDOUT_N]
    freeze = bars[bars.index.normalize().isin(freeze_days)]
    hold = bars[bars.index.normalize().isin(hold_days)]
    return freeze, hold, list(hold_days)


def score_gate(freeze_s: Dict[str, Any], hold_s: Dict[str, Any]) -> float:
    """Higher is better. Prefer holdout accuracy + positive net + enough N."""
    if (freeze_s.get("calls") or 0) < MIN_FREEZE_CALLS:
        return -1e9
    if (hold_s.get("calls") or 0) < MIN_HOLD_CALLS:
        return -1e9
    fh = freeze_s.get("hit_rate") or 0.0
    hh = hold_s.get("hit_rate") or 0.0
    hn = hold_s.get("net_points") or 0.0
    wr = hold_s.get("winner_loser_ratio") or 0.0
    # Accuracy-first, then holdout net, then ratio
    return 100.0 * hh + 40.0 * fh + 0.15 * hn + 8.0 * min(wr, 3.0)


def trend_gates() -> List[TrendGate]:
    base = []
    widths = [
        (25, 160),
        (40, 140),
        (50, 130),
        (40, 120),
        (60, 140),
        (30, 120),
        (50, 160),
        (70, 150),
    ]
    last_sigs = ["11:30", "12:00", "12:30", "13:00", "13:30"]
    break_exts = [20.0, 30.0, 40.0, 999.0]
    risks = [25.0, 30.0, 35.0, 40.0]
    entry_exts = [8.0, 12.0, 20.0, 999.0]
    vwap_seps = [0.0, 5.0, 10.0]
    # Full cartesian is huge — sample structured combos
    for (mn, mx), ls, be, rk, ee, vs in itertools.product(
        widths, last_sigs, break_exts, risks, entry_exts, vwap_seps
    ):
        # prune obviously loose/tight noise
        if be == 999.0 and ee == 999.0 and vs == 0.0 and ls == "13:30" and rk == 40.0 and (mn, mx) == (25, 160):
            name = "baseline"
        else:
            name = f"w{int(mn)}-{int(mx)}_sig{ls.replace(':','')}_ext{int(be)}_risk{int(rk)}_eext{int(ee)}_vw{int(vs)}"
        # skip ultra-permissive duplicates of baseline
        if name != "baseline" and be >= 999 and ee >= 999 and vs == 0 and rk >= 40 and ls == "13:30":
            continue
        base.append(
            TrendGate(
                name=name,
                min_width=mn,
                max_width=mx,
                last_signal=ls,
                max_break_ext=be,
                max_risk=rk,
                max_entry_ext=ee,
                min_vwap_sep=vs,
            )
        )
    # Always include baseline first
    out = [g for g in base if g.name == "baseline"]
    out += [g for g in base if g.name != "baseline"]
    return out


def orb_gates() -> List[OrbGate]:
    gates = [
        OrbGate("baseline"),
        OrbGate("w35-100", min_width=35, max_width=100),
        OrbGate("w40-100", min_width=40, max_width=100),
        OrbGate("w40-110", min_width=40, max_width=110),
        OrbGate("w30-100", min_width=30, max_width=100),
        OrbGate("w45-100", min_width=45, max_width=100),
        OrbGate("at_level", at_level_only=True),
        OrbGate("at_level_w40-100", min_width=40, max_width=100, at_level_only=True),
        OrbGate("early_1130", last_signal="11:30"),
        OrbGate("early_1200", last_signal="12:00"),
        OrbGate("w40-100_early", min_width=40, max_width=100, last_signal="12:00"),
        OrbGate("w40-100_at_level", min_width=40, max_width=100, at_level_only=True),
        OrbGate("eext5", max_entry_ext=5.0),
        OrbGate("w40-100_eext5", min_width=40, max_width=100, max_entry_ext=5.0),
    ]
    return gates


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bars, source = load_5m(days=120)
    # Use last 80 sessions for stable freeze/hold (~60 freeze / 20 hold)
    bars = last_n_sessions(bars, 80)
    freeze, hold, hold_days = split_bars(bars)
    print(
        f"source={source} freeze_days={freeze.index.normalize().nunique()} "
        f"hold={hold.index.normalize().nunique()} "
        f"hold_span={hold_days[0].date()}→{hold_days[-1].date()}",
        flush=True,
    )

    # ---- Trend sweep (chunked: prioritize promising axis first) ----
    # Stage 1: width × last_signal × break_ext with fixed risk40 entry999 vwap0
    stage1 = []
    for (mn, mx), ls, be in itertools.product(
        [(25, 160), (40, 140), (50, 130), (40, 120), (60, 140), (30, 120), (50, 160)],
        ["11:30", "12:00", "12:30", "13:00", "13:30"],
        [20.0, 30.0, 40.0, 999.0],
    ):
        stage1.append(
            TrendGate(
                name=f"s1_w{int(mn)}-{int(mx)}_sig{ls.replace(':','')}_ext{int(be)}",
                min_width=mn,
                max_width=mx,
                last_signal=ls,
                max_break_ext=be,
            )
        )
    stage1 = [TrendGate("baseline")] + stage1

    trend_rows = []
    best_s1 = None
    best_s1_score = -1e18
    for i, gate in enumerate(stage1):
        fr = run_trend(freeze, gate)
        ho = run_trend(hold, gate)
        fs, hs = _stats(fr), _stats(ho)
        sc = score_gate(fs, hs)
        row = {"family": "trend", "stage": 1, "gate": asdict(gate), "freeze": fs, "hold": hs, "score": sc}
        trend_rows.append(row)
        if sc > best_s1_score:
            best_s1_score = sc
            best_s1 = gate
        if i % 25 == 0:
            print(f"trend s1 {i}/{len(stage1)} best={best_s1.name if best_s1 else None} sc={best_s1_score:.1f}", flush=True)

    assert best_s1 is not None
    # Stage 2: refine risk / entry_ext / vwap around best width+signal+break_ext
    stage2 = []
    for rk, ee, vs, chase in itertools.product(
        [25.0, 30.0, 35.0, 40.0],
        [8.0, 12.0, 15.0, 20.0, 999.0],
        [0.0, 5.0, 10.0, 15.0],
        [15.0, 20.0, 25.0],
    ):
        stage2.append(
            TrendGate(
                name=(
                    f"s2_w{int(best_s1.min_width)}-{int(best_s1.max_width)}_"
                    f"sig{best_s1.last_signal.replace(':','')}_ext{int(best_s1.max_break_ext)}_"
                    f"risk{int(rk)}_eext{int(ee)}_vw{int(vs)}_ch{int(chase)}"
                ),
                min_width=best_s1.min_width,
                max_width=best_s1.max_width,
                last_signal=best_s1.last_signal,
                max_break_ext=best_s1.max_break_ext,
                max_risk=rk,
                max_entry_ext=ee,
                min_vwap_sep=vs,
                max_chase=chase,
            )
        )

    best_trend = best_s1
    best_trend_score = best_s1_score
    best_trend_pack = None
    for i, gate in enumerate(stage2):
        fr = run_trend(freeze, gate)
        ho = run_trend(hold, gate)
        fs, hs = _stats(fr), _stats(ho)
        sc = score_gate(fs, hs)
        row = {"family": "trend", "stage": 2, "gate": asdict(gate), "freeze": fs, "hold": hs, "score": sc}
        trend_rows.append(row)
        if sc > best_trend_score:
            best_trend_score = sc
            best_trend = gate
            best_trend_pack = row
        if i % 30 == 0:
            print(f"trend s2 {i}/{len(stage2)} best={best_trend.name} sc={best_trend_score:.1f}", flush=True)

    if best_trend_pack is None:
        # best still stage1
        best_trend_pack = max(
            (r for r in trend_rows if r["gate"]["name"] == best_trend.name),
            key=lambda r: r["score"],
        )

    # ---- ORB sweep ----
    orb_rows = []
    best_orb = None
    best_orb_score = -1e18
    best_orb_pack = None
    for gate in orb_gates():
        fr = run_orb(freeze, gate)
        ho = run_orb(hold, gate)
        fs, hs = _stats(fr), _stats(ho)
        # ORB uses average_win keys — already normalized in _stats for trend;
        # recompute ratio for orb via summarize keys
        if hs.get("average_winner") is None and "average_points" in hs:
            pass
        sc = score_gate(fs, hs)
        row = {"family": "orb", "stage": 1, "gate": asdict(gate), "freeze": fs, "hold": hs, "score": sc}
        orb_rows.append(row)
        if sc > best_orb_score:
            best_orb_score = sc
            best_orb = gate
            best_orb_pack = row
        print(f"orb {gate.name}: hold_hit={hs.get('hit_rate')} n={hs.get('calls')} net={hs.get('net_points')} sc={sc:.1f}", flush=True)

    # Top tables
    def top_n(rows: List[dict], n: int = 12) -> List[dict]:
        return sorted(rows, key=lambda r: r["score"], reverse=True)[:n]

    trend_top = top_n(trend_rows, 15)
    orb_top = top_n(orb_rows, 10)

    # Baseline refs
    base_trend = next(r for r in trend_rows if r["gate"]["name"] == "baseline")
    base_orb = next(r for r in orb_rows if r["gate"]["name"] == "baseline")

    def fmt_block(title: str, pack: dict) -> List[str]:
        g = pack["gate"]
        fs, hs = pack["freeze"], pack["hold"]
        return [
            f"### {title}",
            "",
            f"- gate: `{g}`",
            f"- freeze: N={fs.get('calls')} hit={fs.get('hit_rate')} "
            f"W/L={fs.get('wins')}/{fs.get('losses')} net={fs.get('net_points')} "
            f"avgW={fs.get('average_winner')} avgL={fs.get('average_loser')} "
            f"ratio={fs.get('winner_loser_ratio')}",
            f"- holdout: N={hs.get('calls')} hit={hs.get('hit_rate')} "
            f"W/L={hs.get('wins')}/{hs.get('losses')} net={hs.get('net_points')} "
            f"avgW={hs.get('average_winner')} avgL={hs.get('average_loser')} "
            f"ratio={hs.get('winner_loser_ratio')}",
            f"- score: **{pack['score']:.2f}**",
            "",
        ]

    lines = [
        "# NIFTY accuracy search · trend-stay + ORB gates",
        "",
        f"**Source:** `{source}` 5m · cost={COST} · freeze=first "
        f"{freeze.index.normalize().nunique()} of last 80 · holdout=last {HOLDOUT_N}",
        f"**Holdout span:** {hold_days[0].date()} → {hold_days[-1].date()}",
        "",
        "Selection prefers **holdout hit rate**, then freeze hit, holdout net, W/L ratio. "
        "Min freeze calls ≥8, holdout calls ≥3.",
        "",
        "## Trend-stay · baseline vs best",
        "",
    ]
    lines += fmt_block("Baseline trend-stay", base_trend)
    lines += fmt_block("Best trend-stay gate", best_trend_pack)
    lines += [
        "## Trend-stay · top gates",
        "",
        "| Rank | Name | Freeze N/hit/net | Hold N/hit/net | Ratio(h) | Score |",
        "|---:|---|---|---|---:|---:|",
    ]
    for i, r in enumerate(trend_top, 1):
        fs, hs = r["freeze"], r["hold"]
        lines.append(
            f"| {i} | `{r['gate']['name'][:60]}` | "
            f"{int(fs['calls'] or 0)}/{fs.get('hit_rate')} / {fs.get('net_points')} | "
            f"{int(hs['calls'] or 0)}/{hs.get('hit_rate')} / {hs.get('net_points')} | "
            f"{hs.get('winner_loser_ratio')} | {r['score']:.1f} |"
        )

    lines += ["", "## ORB · baseline vs best", ""]
    lines += fmt_block("Baseline ORB", base_orb)
    lines += fmt_block("Best ORB gate", best_orb_pack)
    lines += [
        "## ORB · top gates",
        "",
        "| Rank | Name | Freeze N/hit/net | Hold N/hit/net | Score |",
        "|---:|---|---|---|---:|",
    ]
    for i, r in enumerate(orb_top, 1):
        fs, hs = r["freeze"], r["hold"]
        lines.append(
            f"| {i} | `{r['gate']['name']}` | "
            f"{int(fs['calls'] or 0)}/{fs.get('hit_rate')} / {fs.get('net_points')} | "
            f"{int(hs['calls'] or 0)}/{hs.get('hit_rate')} / {hs.get('net_points')} | "
            f"{r['score']:.1f} |"
        )

    # Recommend accurate recipe
    bt = best_trend_pack["gate"]
    bo = best_orb_pack["gate"]
    lines += [
        "",
        "## Recommended accurate recipe (freeze→holdout)",
        "",
        "### Trend-stay accurate",
        "",
        f"1. Balance width **{bt['min_width']}–{bt['max_width']}** (was 25–160)",
        f"2. Signal 15m break only before **{bt['last_signal']}**",
        f"3. Break close within **{bt['max_break_ext']}** pts of IBH/IBL"
        if bt["max_break_ext"] < 900
        else "3. Break extension uncapped",
        f"4. Max pullback risk **{bt['max_risk']}**",
        f"5. Entry within **{bt['max_entry_ext']}** pts of level"
        if bt["max_entry_ext"] < 900
        else "5. Entry extension uncapped",
        f"6. Min |close−VWAP| at signal **{bt['min_vwap_sep']}**",
        f"7. Max chase before pullback **{bt['max_chase']}**",
        "",
        "### ORB accurate",
        "",
        f"1. OR width **{bo['min_width']}–{bo['max_width']}**",
        f"2. Last signal **{bo['last_signal']}**",
        f"3. at_level_only={bo['at_level_only']} · max_entry_ext={bo['max_entry_ext']}",
        "",
        "Note: trend-following will not sustain 70%+ hit *and* large open-ended winners. "
        "Gates here raise accuracy by skipping weak structure, not by changing the hold.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    payload = {
        "source": source,
        "holdout_n": HOLDOUT_N,
        "holdout_span": [str(hold_days[0].date()), str(hold_days[-1].date())],
        "best_trend": best_trend_pack,
        "best_orb": best_orb_pack,
        "baseline_trend": base_trend,
        "baseline_orb": base_orb,
        "trend_top": trend_top,
        "orb_top": orb_top,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("BEST TREND", best_trend.name, best_trend_pack["hold"], flush=True)
    print("BEST ORB", best_orb.name, best_orb_pack["hold"], flush=True)
    print(f"wrote {OUT_MD}", flush=True)


if __name__ == "__main__":
    main()
