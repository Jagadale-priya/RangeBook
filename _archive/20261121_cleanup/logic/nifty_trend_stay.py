"""One Nifty futures trend-day call.

This is the long-stay rule:
- the first hour, 09:15 to 10:15, is the balance
- a 15-minute close must break that balance and agree with VWAP
- entry is the first pullback to the broken level, not the break itself
- the stop starts 15 points back inside the level
- the stop then trails the completed 15-minute swing (only after the fill)
- a 15-minute close back through VWAP ends the trade
- there is no fixed 20-point target

The published trend-following record supports this shape: fewer winners,
larger winners. It does not support a high hit rate on every session.

Use the same 5-minute futures file / prepare_bars path as nifty_orb30_vwap_fut.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from prod_live.logic.nifty_orb30_vwap_fut import load_bars, prepare_bars

BALANCE_START = time(9, 15)
BALANCE_END = time(10, 15)
LAST_ENTRY = time(13, 30)
SESSION_END = time(14, 45)
MIN_WIDTH = 25.0
MAX_WIDTH = 160.0
STOP_BUFFER = 15.0
MAX_CHASE = 25.0
TOUCH_BUFFER = 2.0
PROBABILITY_THRESHOLD = 0.60
MAX_PULLBACK_RISK = 40.0


@dataclass(frozen=True)
class TrendProfile:
    name: str
    min_width: float
    max_width: float
    last_signal: time
    max_risk: float
    max_entry_ext: float
    max_chase: float
    max_break_ext: float = 999.0
    min_vwap_sep: float = 0.0
    sides: Tuple[str, ...] = ("buy", "sell")


PROFILES = {
    "baseline": TrendProfile(
        name="baseline",
        min_width=MIN_WIDTH,
        max_width=MAX_WIDTH,
        last_signal=LAST_ENTRY,
        max_risk=MAX_PULLBACK_RISK,
        max_entry_ext=999.0,
        max_chase=MAX_CHASE,
    ),
    # Research: SELL-only + morning break lifted hit to ~46% (N=13, 80d).
    # Trend-follow will not reach ORB-style 60%+ while keeping large winners.
    "accurate": TrendProfile(
        name="accurate",
        min_width=25.0,
        max_width=160.0,
        last_signal=time(12, 0),
        max_risk=30.0,
        max_entry_ext=15.0,
        max_chase=20.0,
        sides=("sell",),
    ),
}


def resolve_profile(profile: str | TrendProfile = "baseline") -> TrendProfile:
    if isinstance(profile, TrendProfile):
        return profile
    key = str(profile or "baseline").strip().lower()
    if key not in PROFILES:
        raise ValueError(f"Unknown trend profile {profile!r}; expected {sorted(PROFILES)}")
    return PROFILES[key]


@dataclass(frozen=True)
class TrendCall:
    date: pd.Timestamp
    status: str
    direction: Optional[str]
    balance_high: Optional[float]
    balance_low: Optional[float]
    balance_width: Optional[float]
    signal_time: Optional[pd.Timestamp]
    entry_time: Optional[pd.Timestamp]
    entry: Optional[float]
    initial_stop: Optional[float]
    exit_time: Optional[pd.Timestamp]
    exit: Optional[float]
    points: Optional[float]
    max_favorable: Optional[float]
    reason: str
    probability: Optional[float]


def _vwap(day: pd.DataFrame) -> pd.Series:
    typical = (day["high"] + day["low"] + day["close"]) / 3.0
    volume = day["volume"].clip(lower=0.0)
    if float(volume.sum()) <= 0.0:
        return typical.expanding().mean()
    traded = typical * volume
    return traded.cumsum() / volume.cumsum().replace(0.0, np.nan)


def _bucket_start(timestamp: pd.Timestamp) -> pd.Timestamp:
    minutes_from_open = timestamp.hour * 60 + timestamp.minute - (9 * 60 + 15)
    bucket = max(minutes_from_open, 0) // 15 * 15
    start = timestamp.normalize() + pd.Timedelta(minutes=9 * 60 + 15 + bucket)
    if timestamp.tzinfo is not None and start.tzinfo is None:
        return start.tz_localize(timestamp.tz)
    return start


def _fifteen_minute(day: pd.DataFrame, vwap: pd.Series) -> pd.DataFrame:
    frame = day.copy()
    frame["vwap"] = vwap
    frame["bucket"] = [_bucket_start(timestamp) for timestamp in frame.index]
    grouped = frame.groupby("bucket", sort=True)
    bars = pd.DataFrame(
        {
            "open": grouped["open"].first(),
            "high": grouped["high"].max(),
            "low": grouped["low"].min(),
            "close": grouped["close"].last(),
            "vwap": grouped["vwap"].last(),
        }
    )
    if "buy_probability" in frame.columns:
        bars["buy_probability"] = grouped["buy_probability"].last()
    if "sell_probability" in frame.columns:
        bars["sell_probability"] = grouped["sell_probability"].last()
    return bars


def _blank(date: pd.Timestamp, reason: str, **values: object) -> TrendCall:
    payload = {
        "date": date,
        "status": "no_call",
        "direction": None,
        "balance_high": None,
        "balance_low": None,
        "balance_width": None,
        "signal_time": None,
        "entry_time": None,
        "entry": None,
        "initial_stop": None,
        "exit_time": None,
        "exit": None,
        "points": None,
        "max_favorable": None,
        "reason": reason,
        "probability": None,
    }
    payload.update(values)
    return TrendCall(**payload)


def _stop_fill(bar: pd.Series, direction: str, stop: float) -> Optional[float]:
    """Fill a stop on this bar. A gap through the stop is filled at the open."""
    if direction == "buy" and float(bar["low"]) <= stop:
        return min(stop, float(bar["open"]))
    if direction == "sell" and float(bar["high"]) >= stop:
        return max(stop, float(bar["open"]))
    return None


def _close_bucket(
    direction: str,
    stop: float,
    bucket_low: float,
    bucket_high: float,
    bucket_close: float,
    bucket_vwap: float,
) -> Tuple[Optional[float], float]:
    """Finished 15m bucket: VWAP exit, or tighten stop for later bars."""
    if direction == "buy":
        if bucket_close < bucket_vwap:
            return bucket_close, stop
        return None, max(stop, bucket_low)
    if bucket_close > bucket_vwap:
        return bucket_close, stop
    return None, min(stop, bucket_high)


def _manage_trade(
    day: pd.DataFrame,
    vwap: pd.Series,
    direction: str,
    entry_time: pd.Timestamp,
    entry: float,
    stop: float,
) -> Tuple[pd.Timestamp, float, float, str]:
    """Manage the fill on later 5-minute bars.

    Trail uses only completed 15m swings *after* the entry bar. Pre-entry
    pullback lows/highs must not stop the trade.
    """
    path = day[day.index > entry_time]
    if path.empty:
        return entry_time, entry, 0.0, "no_path"

    best = entry
    current_bucket = None
    bucket_time = entry_time
    bucket_low = np.inf
    bucket_high = -np.inf
    bucket_close = entry
    bucket_vwap = float(vwap.loc[entry_time])

    for timestamp, bar in path.iterrows():
        bucket = _bucket_start(timestamp)
        if current_bucket is None:
            current_bucket = bucket
        elif bucket != current_bucket:
            # Close the *completed* post-entry bucket: VWAP exit or trail tighten.
            exit_price, stop = _close_bucket(
                direction, stop, bucket_low, bucket_high, bucket_close, bucket_vwap
            )
            if exit_price is not None:
                favorable = best - entry if direction == "buy" else entry - best
                return bucket_time, exit_price, favorable, "vwap_exit"
            current_bucket = bucket
            bucket_low = np.inf
            bucket_high = -np.inf

        fill = _stop_fill(bar, direction, stop)
        if direction == "buy":
            best = max(best, float(bar["high"]))
        else:
            best = min(best, float(bar["low"]))
        if fill is not None:
            favorable = best - entry if direction == "buy" else entry - best
            return timestamp, fill, favorable, "stop"

        bucket_time = timestamp
        bucket_low = min(bucket_low, float(bar["low"]))
        bucket_high = max(bucket_high, float(bar["high"]))
        bucket_close = float(bar["close"])
        bucket_vwap = float(vwap.loc[timestamp])
        if timestamp.time() >= SESSION_END:
            favorable = best - entry if direction == "buy" else entry - best
            return timestamp, float(bar["close"]), favorable, "session_end"

    exit_price, _ = _close_bucket(
        direction, stop, bucket_low, bucket_high, bucket_close, bucket_vwap
    )
    favorable = best - entry if direction == "buy" else entry - best
    if exit_price is not None:
        return bucket_time, exit_price, favorable, "vwap_exit"
    return bucket_time, bucket_close, favorable, "session_end"


def evaluate_day(
    day: pd.DataFrame,
    probability_threshold: float = PROBABILITY_THRESHOLD,
    require_probability: bool = False,
    profile: str | TrendProfile = "baseline",
) -> TrendCall:
    cfg = resolve_profile(profile)
    date = pd.Timestamp(day.index[0]).normalize()
    clock = day.index.time
    balance = day[(clock >= BALANCE_START) & (clock < BALANCE_END)]
    if balance.empty:
        return _blank(date, "missing_balance")

    balance_high = float(balance["high"].max())
    balance_low = float(balance["low"].min())
    width = balance_high - balance_low
    levels = {
        "balance_high": balance_high,
        "balance_low": balance_low,
        "balance_width": width,
    }
    if width < cfg.min_width or width > cfg.max_width:
        return _blank(date, "balance_width_out_of_range", **levels)

    vwap = _vwap(day)
    bars = _fifteen_minute(day, vwap)
    candidates = bars[(bars.index.time >= BALANCE_END) & (bars.index.time < cfg.last_signal)]
    has_buy = "buy_probability" in bars.columns
    has_sell = "sell_probability" in bars.columns
    if require_probability and not (has_buy and has_sell):
        raise ValueError(
            "require_probability=True needs buy_probability and sell_probability columns."
        )

    for signal_time, signal in candidates.iterrows():
        close = float(signal["close"])
        fair = float(signal["vwap"])
        buy_break = close > balance_high and close > fair
        sell_break = close < balance_low and close < fair
        if not buy_break and not sell_break:
            continue

        direction = "buy" if buy_break else "sell"
        if direction not in cfg.sides:
            continue
        level = balance_high if direction == "buy" else balance_low
        if abs(close - level) > cfg.max_break_ext:
            continue
        if abs(close - fair) < cfg.min_vwap_sep:
            continue

        probability = None
        if direction == "buy" and has_buy:
            probability = float(signal["buy_probability"])
        elif direction == "sell" and has_sell:
            probability = float(signal["sell_probability"])
        probability_missing = probability is None or (
            isinstance(probability, float) and np.isnan(probability)
        )
        if require_probability and (
            probability_missing or float(probability) < probability_threshold
        ):
            continue
        if not probability_missing and float(probability) < probability_threshold:
            continue

        # First bar after the completed 15m signal bucket.
        later = day[day.index > signal_time + pd.Timedelta(minutes=14)]
        entry_time = None
        entry = None
        touched = False
        ran_away = False
        for bar_time, bar in later.iterrows():
            if bar_time.time() >= LAST_ENTRY:
                break
            if direction == "buy":
                if float(bar["high"]) >= balance_high + cfg.max_chase and not touched:
                    ran_away = True
                    break
                if float(bar["low"]) <= balance_high + TOUCH_BUFFER:
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
                if float(bar["low"]) <= balance_low - cfg.max_chase and not touched:
                    ran_away = True
                    break
                if float(bar["high"]) >= balance_low - TOUCH_BUFFER:
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
                return _blank(
                    date,
                    "price_ran_away_before_pullback",
                    direction=direction,
                    signal_time=signal_time,
                    probability=probability,
                    **levels,
                )
            # Try next break signal; day not consumed by a break without pullback yet.
            continue

        if abs(entry - level) > cfg.max_entry_ext:
            continue

        initial_stop = (
            balance_high - STOP_BUFFER if direction == "buy" else balance_low + STOP_BUFFER
        )
        risk = entry - initial_stop if direction == "buy" else initial_stop - entry
        if risk <= 0.0 or risk > cfg.max_risk:
            return _blank(
                date,
                "pullback_risk_out_of_range",
                direction=direction,
                signal_time=signal_time,
                entry_time=entry_time,
                entry=entry,
                initial_stop=initial_stop,
                probability=probability,
                **levels,
            )

        exit_time, exit_price, favorable, reason = _manage_trade(
            day, vwap, direction, entry_time, entry, initial_stop
        )
        points = exit_price - entry if direction == "buy" else entry - exit_price
        return TrendCall(
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
            probability=probability,
        )

    return _blank(date, "no_pullback_after_break", **levels)


def generate_calls(
    bars: pd.DataFrame,
    probability_threshold: float = PROBABILITY_THRESHOLD,
    require_probability: bool = False,
    profile: str | TrendProfile = "baseline",
) -> pd.DataFrame:
    frame = prepare_bars(bars)
    calls = [
        evaluate_day(day, probability_threshold, require_probability, profile=profile)
        for _, day in frame.groupby(frame.index.normalize())
    ]
    return pd.DataFrame(call.__dict__ for call in calls)


def summarize(calls: pd.DataFrame, cost_points_per_call: float = 0.0) -> dict[str, float]:
    taken = calls[calls["entry"].notna()].copy()
    if taken.empty:
        return {
            "sessions": float(len(calls)),
            "calls": 0.0,
            "wins": 0.0,
            "losses": 0.0,
            "hit_rate": np.nan,
            "average_winner": np.nan,
            "average_loser": np.nan,
            "winner_loser_ratio": np.nan,
            "net_points": 0.0,
            "no_call_days": float(len(calls)),
        }
    net = taken["points"].astype(float) - cost_points_per_call
    winners = net[net > 0]
    losers = net[net < 0]
    avg_w = float(winners.mean()) if not winners.empty else np.nan
    avg_l = float(losers.mean()) if not losers.empty else np.nan
    ratio = (
        float(avg_w / abs(avg_l))
        if (not winners.empty and not losers.empty and avg_l != 0)
        else np.nan
    )
    return {
        "sessions": float(len(calls)),
        "calls": float(len(taken)),
        "wins": float(len(winners)),
        "losses": float(len(losers)),
        "hit_rate": float(len(winners) / len(taken)),
        "average_winner": avg_w,
        "average_loser": avg_l,
        "winner_loser_ratio": ratio,
        "net_points": float(net.sum()),
        "no_call_days": float((calls["entry"].isna()).sum()),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate one Nifty trend-day call per session.")
    parser.add_argument("csv", help="5-minute Nifty futures CSV")
    parser.add_argument("--threshold", type=float, default=PROBABILITY_THRESHOLD)
    parser.add_argument("--require-probability", action="store_true")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="baseline")
    parser.add_argument("--cost-points", type=float, default=1.0)
    parser.add_argument("--output", default="nifty_trend_calls.csv")
    args = parser.parse_args()

    result = generate_calls(
        load_bars(args.csv),
        probability_threshold=args.threshold,
        require_probability=args.require_probability,
        profile=args.profile,
    )
    result.to_csv(args.output, index=False)
    print(summarize(result, cost_points_per_call=args.cost_points))
    print(f"Wrote {args.output}")
