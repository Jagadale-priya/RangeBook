"""One Nifty futures call per day — 30-minute opening-range rule.

Frozen structure (description):
- OR built 09:15–09:45 (ORH, ORL, width = ORH − ORL)
- Skip day if width < 30 (noise) or width > 90 (move already spent)
- Session VWAP from 09:15: sum(typical×volume)/sum(volume),
  typical = (H+L+C)/3; if volume is 0, expanding mean of typical
- India VIX expected range = price × (VIX/100) / √252 (context / annotate)
- Buy: completed 5m close above ORH, within 10 pts of ORH, close > VWAP
- Sell: completed 5m close below ORL, within 10 pts of ORL, close < VWAP
- Probability model is a mandatory gate when columns are present / required
- Entry: at ORH/ORL when the next bar still trades the level; else next
  trade only if still within 10 pts past the level (no chase)
- Stop: 12 pts back through the level (ORH−12 / ORL+12)
- Target: 20 pts from the fill
- Flat 14:45 if neither hit; one attempt; a stop is never reversed

Hit rate is whatever unseen sessions produce — this file does not guarantee
a daily 20-point profit.

Expected columns: open, high, low, close, volume on an IST datetime index.
Optional: buy_probability, sell_probability, india_vix.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Optional, Tuple

import numpy as np
import pandas as pd

ORB_START = time(9, 15)
ORB_END = time(9, 45)
SESSION_END = time(14, 45)
MIN_WIDTH = 30.0
MAX_WIDTH = 90.0
MAX_EXTENSION = 10.0
STOP_POINTS = 12.0
TARGET_POINTS = 20.0
PROBABILITY_THRESHOLD = 0.60
# Description reference: ~215 pts day range at 24,500 × VIX 14 / √252
VIX_RANGE_REF_POINTS = 215.0
TRADING_DAYS_YEAR = 252.0


@dataclass(frozen=True)
class OrbProfile:
    """baseline = description defaults · accurate = freeze/holdout research gate."""

    name: str
    min_width: float
    max_width: float
    max_entry_ext: float
    last_signal: time = SESSION_END


PROFILES = {
    "baseline": OrbProfile("baseline", MIN_WIDTH, MAX_WIDTH, MAX_EXTENSION),
    # Research ACC_C: entry within 5 pts of ORH/ORL · width 40–100
    # freeze 60d ~54.8% · holdout 20d 50% (N small) · 80d entry_ext<=5 → 63.2%
    "accurate": OrbProfile("accurate", 40.0, 100.0, 5.0),
}


def resolve_profile(profile: str | OrbProfile = "baseline") -> OrbProfile:
    if isinstance(profile, OrbProfile):
        return profile
    key = str(profile or "baseline").strip().lower()
    if key not in PROFILES:
        raise ValueError(f"Unknown ORB profile {profile!r}; expected {sorted(PROFILES)}")
    return PROFILES[key]


@dataclass(frozen=True)
class DayCall:
    date: pd.Timestamp
    status: str
    direction: Optional[str]
    opening_high: Optional[float]
    opening_low: Optional[float]
    opening_width: Optional[float]
    expected_range: Optional[float]
    vwap_at_signal: Optional[float]
    signal_time: Optional[pd.Timestamp]
    entry_time: Optional[pd.Timestamp]
    entry: Optional[float]
    entry_mode: Optional[str]
    stop: Optional[float]
    target: Optional[float]
    exit_time: Optional[pd.Timestamp]
    exit: Optional[float]
    points: Optional[float]
    reason: str
    probability: Optional[float]
    india_vix: Optional[float]


def prepare_bars(bars: pd.DataFrame) -> pd.DataFrame:
    """Return a sorted 5-minute bar frame with the columns this rule needs."""
    frame = bars.copy()
    if "datetime" in frame.columns:
        frame["datetime"] = pd.to_datetime(frame["datetime"])
        frame = frame.set_index("datetime")
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    frame.index.name = "datetime"

    required = ["open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")

    prices = frame[required[:4]].apply(pd.to_numeric, errors="coerce")
    frame[required[:4]] = prices
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0.0)
    if frame[required[:4]].isna().any().any():
        raise ValueError("Price columns contain blank or non-numeric values.")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("A bar has a high below its open, close, or low.")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("A bar has a low above its open, close, or high.")
    for optional in ("buy_probability", "sell_probability", "india_vix"):
        if optional in frame.columns:
            frame[optional] = pd.to_numeric(frame[optional], errors="coerce")
    return frame


def expected_day_range(price: float, india_vix: float) -> float:
    """future price × (India VIX / 100) / √252."""
    return float(price) * (float(india_vix) / 100.0) / np.sqrt(TRADING_DAYS_YEAR)


def _session_vwap(day: pd.DataFrame) -> pd.Series:
    typical = (day["high"] + day["low"] + day["close"]) / 3.0
    volume = day["volume"].clip(lower=0.0)
    if float(volume.sum()) <= 0.0:
        return typical.expanding().mean()
    traded = typical * volume
    return traded.cumsum() / volume.cumsum().replace(0.0, np.nan)


def _resolve_exit(
    path: pd.DataFrame, direction: str, stop: float, target: float
) -> Tuple[pd.Timestamp, float, str]:
    """Walk bars from the fill bar. Same-bar stop+target → stop wins."""
    for timestamp, bar in path.iterrows():
        if direction == "buy":
            stop_hit = float(bar["low"]) <= stop
            target_hit = float(bar["high"]) >= target
        else:
            stop_hit = float(bar["high"]) >= stop
            target_hit = float(bar["low"]) <= target

        if stop_hit and target_hit:
            return timestamp, stop, "stop_same_bar"
        if stop_hit:
            return timestamp, stop, "stop"
        if target_hit:
            return timestamp, target, "target"
        if timestamp.time() >= SESSION_END:
            return timestamp, float(bar["close"]), "session_end"
    last_time = path.index[-1]
    return last_time, float(path.iloc[-1]["close"]), "session_end"


def _blank_call(date: pd.Timestamp, status: str, reason: str, **values: object) -> DayCall:
    payload = {
        "date": date,
        "status": status,
        "direction": None,
        "opening_high": None,
        "opening_low": None,
        "opening_width": None,
        "expected_range": None,
        "vwap_at_signal": None,
        "signal_time": None,
        "entry_time": None,
        "entry": None,
        "entry_mode": None,
        "stop": None,
        "target": None,
        "exit_time": None,
        "exit": None,
        "points": None,
        "reason": reason,
        "probability": None,
        "india_vix": None,
    }
    payload.update(values)
    return DayCall(**payload)


def _bar_vix(bar: pd.Series, day: pd.DataFrame) -> Optional[float]:
    if "india_vix" not in day.columns:
        return None
    val = bar.get("india_vix")
    if pd.isna(val):
        return None
    return float(val)


def _resolve_entry(
    direction: str,
    level: float,
    entry_bar: pd.Series,
) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """Fill at the level when traded; else next trade within 10 pts past.

    Returns (entry, entry_mode, fail_reason).
    """
    o = float(entry_bar["open"])
    h = float(entry_bar["high"])
    lo = float(entry_bar["low"])

    if direction == "buy":
        # Ideal: next bar still trades ORH → fill at the level.
        if lo <= level <= h and o <= level + MAX_EXTENSION:
            if o <= level:
                return level, "at_level", None
            # Opened above level but still within 10 — next trade.
            return o, "next_trade", None
        # Gapped through level without trading back; accept only if ≤10 past.
        if o > level:
            if o - level > MAX_EXTENSION:
                return None, None, "entry_moved_too_far_from_level"
            return o, "next_trade", None
        return None, None, "entry_failed_to_hold_level"

    # sell
    if lo <= level <= h and o >= level - MAX_EXTENSION:
        if o >= level:
            return level, "at_level", None
        return o, "next_trade", None
    if o < level:
        if level - o > MAX_EXTENSION:
            return None, None, "entry_moved_too_far_from_level"
        return o, "next_trade", None
    return None, None, "entry_failed_to_hold_level"


def evaluate_day(
    day: pd.DataFrame,
    probability_threshold: float = PROBABILITY_THRESHOLD,
    require_probability: bool = False,
    profile: str | OrbProfile = "baseline",
) -> DayCall:
    """Return the single call, or the reason the session has no call."""
    cfg = resolve_profile(profile)
    date = pd.Timestamp(day.index[0]).normalize()
    clock = day.index.time
    opening = day[(clock >= ORB_START) & (clock < ORB_END)]
    if opening.empty:
        return _blank_call(date, "no_call", "missing_opening_range")

    opening_high = float(opening["high"].max())
    opening_low = float(opening["low"].min())
    width = opening_high - opening_low
    open_ref = float(opening.iloc[0]["open"])
    vix_open = _bar_vix(opening.iloc[0], day)
    exp_range = expected_day_range(open_ref, vix_open) if vix_open and vix_open > 0 else None

    range_values = {
        "opening_high": opening_high,
        "opening_low": opening_low,
        "opening_width": width,
        "expected_range": exp_range,
        "india_vix": vix_open,
    }
    if width < cfg.min_width or width > cfg.max_width:
        return _blank_call(date, "no_call", "opening_width_out_of_range", **range_values)

    later = day[clock >= ORB_END]
    if later.empty:
        return _blank_call(date, "no_call", "no_bars_after_opening_range", **range_values)

    vwap = _session_vwap(day)
    has_buy_probability = "buy_probability" in day.columns
    has_sell_probability = "sell_probability" in day.columns
    if require_probability and not (has_buy_probability and has_sell_probability):
        raise ValueError(
            "require_probability=True needs buy_probability and sell_probability columns."
        )

    last_fail_reason = "no_valid_break"
    for signal_time, bar in later.iterrows():
        if signal_time.time() >= cfg.last_signal or signal_time.time() >= SESSION_END:
            break
        close = float(bar["close"])
        fair_price = float(vwap.loc[signal_time])
        buy_extension = close - opening_high
        sell_extension = opening_low - close
        buy_break = 0.0 < buy_extension <= MAX_EXTENSION and close > fair_price
        sell_break = 0.0 < sell_extension <= MAX_EXTENSION and close < fair_price
        if not buy_break and not sell_break:
            continue

        # One direction only; if both somehow true prefer the side with smaller extension.
        if buy_break and sell_break:
            direction = "buy" if buy_extension <= sell_extension else "sell"
        else:
            direction = "buy" if buy_break else "sell"

        probability = None
        if direction == "buy" and has_buy_probability:
            probability = float(bar["buy_probability"])
        elif direction == "sell" and has_sell_probability:
            probability = float(bar["sell_probability"])

        # Mandatory gate when required, or whenever a score is present on the bar.
        if require_probability or probability is not None:
            if probability is None or np.isnan(probability) or probability < probability_threshold:
                last_fail_reason = "probability_gate"
                continue

        following = day[day.index > signal_time]
        if following.empty:
            return _blank_call(
                date,
                "no_call",
                "no_bar_available_for_entry",
                direction=direction,
                vwap_at_signal=fair_price,
                signal_time=signal_time,
                probability=probability,
                **range_values,
            )

        entry_time = following.index[0]
        entry_bar = following.iloc[0]
        level = opening_high if direction == "buy" else opening_low
        entry, entry_mode, entry_fail = _resolve_entry(direction, level, entry_bar)
        if entry is None:
            # Failed fill is not a trade — keep scanning for a later valid break.
            last_fail_reason = entry_fail or "entry_moved_too_far_from_level"
            continue
        if abs(entry - level) > cfg.max_entry_ext:
            last_fail_reason = "entry_extension_above_profile"
            continue

        # Stop through the level (not from a chased fill). Target from the fill.
        if direction == "buy":
            stop = opening_high - STOP_POINTS
            target = entry + TARGET_POINTS
        else:
            stop = opening_low + STOP_POINTS
            target = entry - TARGET_POINTS

        # Path includes the fill bar (open already used as entry / level fill).
        exit_time, exit_price, exit_reason = _resolve_exit(following, direction, stop, target)
        points = exit_price - entry if direction == "buy" else entry - exit_price
        india_vix = _bar_vix(bar, day)
        if india_vix is not None and exp_range is None:
            exp_range = expected_day_range(entry, india_vix)

        return DayCall(
            date=date,
            status=exit_reason,
            direction=direction,
            opening_high=opening_high,
            opening_low=opening_low,
            opening_width=width,
            expected_range=exp_range,
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
            probability=probability,
            india_vix=india_vix if india_vix is not None else vix_open,
        )

    return _blank_call(date, "no_call", last_fail_reason, **range_values)


def generate_calls(
    bars: pd.DataFrame,
    probability_threshold: float = PROBABILITY_THRESHOLD,
    require_probability: bool = False,
    profile: str | OrbProfile = "baseline",
) -> pd.DataFrame:
    """Evaluate every session and return one row per day."""
    frame = prepare_bars(bars)
    calls = [
        evaluate_day(day, probability_threshold, require_probability, profile=profile)
        for _, day in frame.groupby(frame.index.normalize())
    ]
    return pd.DataFrame(call.__dict__ for call in calls)


def summarize(calls: pd.DataFrame, cost_points_per_call: float = 0.0) -> dict[str, float]:
    """Summarize taken calls. Costs are round-trip futures costs in index points."""
    taken = calls[calls["entry"].notna()].copy()
    if taken.empty:
        return {
            "sessions": float(len(calls)),
            "calls": 0.0,
            "wins": 0.0,
            "losses": 0.0,
            "hit_rate": np.nan,
            "average_win": np.nan,
            "average_loss": np.nan,
            "average_points": np.nan,
            "net_points": 0.0,
            "no_call_days": float(len(calls)),
        }
    net = taken["points"].astype(float) - cost_points_per_call
    wins_mask = net > 0
    losses_mask = net < 0
    wins = int(wins_mask.sum())
    losses = int(losses_mask.sum())
    return {
        "sessions": float(len(calls)),
        "calls": float(len(taken)),
        "wins": float(wins),
        "losses": float(losses),
        "hit_rate": wins / len(taken),
        "average_win": float(net[wins_mask].mean()) if wins else np.nan,
        "average_loss": float(net[losses_mask].mean()) if losses else np.nan,
        "average_points": float(net.mean()),
        "net_points": float(net.sum()),
        "no_call_days": float((calls["entry"].isna()).sum()),
    }


def load_bars(path: str) -> pd.DataFrame:
    raw = pd.read_csv(path)
    if "datetime" not in raw.columns and raw.columns[0].lower() in ("date", "datetime", "timestamp"):
        raw = raw.rename(columns={raw.columns[0]: "datetime"})
    raw = raw.rename(columns={c: str(c).lower() for c in raw.columns})
    return prepare_bars(raw)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate one Nifty opening-range call per day.")
    parser.add_argument("csv", help="5-minute Nifty futures CSV")
    parser.add_argument("--threshold", type=float, default=PROBABILITY_THRESHOLD)
    parser.add_argument("--require-probability", action="store_true")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="baseline")
    parser.add_argument("--cost-points", type=float, default=1.0)
    parser.add_argument("--output", default="nifty_calls.csv")
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
