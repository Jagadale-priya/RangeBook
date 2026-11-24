"""State-conditional Nifty futures calls.

This is different from a fixed opening-range or VWAP rule.
A bar is converted into a state. The state is traded only when the same
state, on earlier days, reached its target before its stop often enough.

Pseudocode
----------
for each completed prior day:
    for each 1-minute bar after 09:45:
        state = (vix bucket, auction, vwap side, swing, time bucket)
        direction = hypothesis(state)
        if direction is empty:
            continue
        result = walk forward one hour with stop first
        remember the first result of this state for this day

for today, using only that memory (prior session days only; rolling last 80):
    while flat and calls today < 3:
        state = state of the latest closed bar
        if state was already used today:
            continue
        if similar past results < 20:
            continue
        if win rate < 0.52 or average points <= cost:
            continue
        if the model's probability for that direction is below 0.60:
            continue
        buy or sell at the next bar's open
        stop = 0.6 ATR, limited to 12..25 points
        target = 1.7 times the stop
        exit on stop, target, 60 one-minute bars, or 14:45

No library beyond Python itself is required.
Bars are dictionaries:
datetime, open, high, low, close, volume
optional: india_vix, buy_probability, sell_probability
datetime values are IST.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional, Tuple

OPEN = time(9, 15)
READY = time(9, 45)
CHOP_START = time(12, 0)
CHOP_END = time(13, 15)
LAST_SIGNAL = time(14, 10)
FLAT_AT = time(14, 45)
MIN_RISK = 12.0
MAX_RISK = 25.0
PAYOFF = 1.7
# Evidence gates (calibrated on Nifty 1m): frozen 30@58% left zero eligible
# states after the VIX-proxy fix. 20 analogs @ 52% hit still demands a majority
# edge and avg points above cost before a call is allowed.
MIN_ANALOGS = 20
MIN_HIT_RATE = 0.52
MAX_CALLS = 3
HOLD_BARS = 60
PIVOT_SPAN = 5
ATR_PERIOD = 20
FAIL_WINDOW = 30
SESSION_BARS = 375
PROBABILITY_MIN = 0.60
COST_POINTS = 1.0
# Only the latest N prior-day results count toward hit/avg (old losses must not
# permanently kill a state). Memory still stores history; gates use this window.
ANALOG_WINDOW = 80


@dataclass(frozen=True)
class StateProfile:
    """baseline = volume path · accurate = freeze/holdout research gate."""

    name: str
    min_analogs: int
    min_hit_rate: float
    max_calls: int
    min_avg_edge: float = 0.0  # analog avg − cost must clear this
    auctions: Tuple[str, ...] = ()
    time_buckets: Tuple[str, ...] = ()


PROFILES = {
    "baseline": StateProfile(
        name="baseline",
        min_analogs=MIN_ANALOGS,
        min_hit_rate=MIN_HIT_RATE,
        max_calls=MAX_CALLS,
    ),
    # Research n22_h54_c1: freeze 29@41% · holdout 4@75% (+45 net) vs baseline hold 50%.
    # Requires freeze hit ≥40% and holdout N≥3 — not the max-hold cherry pick.
    "accurate": StateProfile(
        name="accurate",
        min_analogs=22,
        min_hit_rate=0.54,
        max_calls=1,
        min_avg_edge=0.0,
    ),
}


def resolve_profile(profile: str | StateProfile = "baseline") -> StateProfile:
    if isinstance(profile, StateProfile):
        return profile
    key = str(profile or "baseline").strip().lower()
    if key not in PROFILES:
        raise ValueError(f"Unknown state profile {profile!r}; expected {sorted(PROFILES)}")
    return PROFILES[key]


@dataclass
class Bar:
    dt: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    india_vix: Optional[float] = None
    buy_probability: Optional[float] = None
    sell_probability: Optional[float] = None


def parse_bar(raw: dict) -> Bar:
    value = raw["datetime"]
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value).replace("Z", ""))
    return Bar(
        dt=value,
        open=float(raw["open"]),
        high=float(raw["high"]),
        low=float(raw["low"]),
        close=float(raw["close"]),
        volume=float(raw.get("volume") or 0.0),
        india_vix=None if raw.get("india_vix") in (None, "") else float(raw["india_vix"]),
        buy_probability=(
            None if raw.get("buy_probability") in (None, "") else float(raw["buy_probability"])
        ),
        sell_probability=(
            None
            if raw.get("sell_probability") in (None, "")
            else float(raw["sell_probability"])
        ),
    )


def _clock(bar: Bar) -> time:
    return bar.dt.time()


def _session_math(
    day: list[Bar],
) -> tuple[
    list[Optional[float]],
    list[Optional[float]],
    list[Optional[float]],
    list[Optional[float]],
]:
    """Return VWAP, sigma, ATR, and close-location for each bar. Early ATR values stay empty."""
    cumulative_weight = 0.0
    cumulative_price = 0.0
    cumulative_square = 0.0
    vwap: list[Optional[float]] = []
    sigma: list[Optional[float]] = []
    true_ranges: list[float] = []
    for index, bar in enumerate(day):
        typical = (bar.high + bar.low + bar.close) / 3.0
        weight = bar.volume if bar.volume > 0.0 else 1.0
        cumulative_weight += weight
        cumulative_price += typical * weight
        cumulative_square += typical * typical * weight
        current_vwap = cumulative_price / cumulative_weight
        variance = max(0.0, cumulative_square / cumulative_weight - current_vwap * current_vwap)
        vwap.append(current_vwap)
        sigma.append(math.sqrt(variance))
        if index == 0:
            true_ranges.append(bar.high - bar.low)
        else:
            previous = day[index - 1].close
            true_ranges.append(
                max(bar.high - bar.low, abs(bar.high - previous), abs(bar.low - previous))
            )
    atr: list[Optional[float]] = [None] * len(day)
    if len(true_ranges) >= ATR_PERIOD:
        smoothed = sum(true_ranges[:ATR_PERIOD]) / ATR_PERIOD
        atr[ATR_PERIOD - 1] = smoothed
        for index in range(ATR_PERIOD, len(true_ranges)):
            smoothed = ((ATR_PERIOD - 1) * smoothed + true_ranges[index]) / ATR_PERIOD
            atr[index] = smoothed
    location: list[Optional[float]] = []
    for bar in day:
        span = bar.high - bar.low
        location.append(None if span <= 0.0 else (bar.close - bar.low) / span)
    return vwap, sigma, atr, location


def _opening_range(day: list[Bar]) -> Optional[tuple[float, float]]:
    opening = [bar for bar in day if OPEN <= _clock(bar) < READY]
    if len(opening) < 3:
        return None
    return max(bar.high for bar in opening), min(bar.low for bar in opening)


def _swings(day: list[Bar]) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    span = PIVOT_SPAN
    for index in range(span, len(day) - span):
        high_window = [day[pos].high for pos in range(index - span, index + span + 1)]
        low_window = [day[pos].low for pos in range(index - span, index + span + 1)]
        if day[index].high == max(high_window) and high_window.count(day[index].high) == 1:
            highs.append((index + span, day[index].high))
        if day[index].low == min(low_window) and low_window.count(day[index].low) == 1:
            lows.append((index + span, day[index].low))
    return highs, lows


def _bias(
    position: int, highs: list[tuple[int, float]], lows: list[tuple[int, float]]
) -> str:
    known_highs = [price for known_at, price in highs if known_at <= position]
    known_lows = [price for known_at, price in lows if known_at <= position]
    if len(known_highs) < 2 or len(known_lows) < 2:
        return "neutral"
    up = known_highs[-1] > known_highs[-2] and known_lows[-1] > known_lows[-2]
    down = known_highs[-1] < known_highs[-2] and known_lows[-1] < known_lows[-2]
    if up and not down:
        return "up"
    if down and not up:
        return "down"
    return "neutral"


def _vix_bucket(bar: Bar, atr: Optional[float]) -> str:
    """India VIX when present; else day-range % from 1m ATR (not raw annualized 1m vol).

    Bug fix: the old proxy `(atr/close)*sqrt(252*375)*100` pushed almost every
    Nifty session into ``high``, collapsing the state key so analogs never
    diversified and hit rates stayed stuck under 0.58.
    """
    if bar.india_vix is not None:
        value = float(bar.india_vix)
        if value < 12.0:
            return "low"
        if value < 18.0:
            return "normal"
        return "high"
    if atr is None or bar.close <= 0.0:
        return "unknown"
    # Scale 1m ATR up to a session-range estimate, then as % of price.
    day_range_pct = (float(atr) * math.sqrt(SESSION_BARS) / float(bar.close)) * 100.0
    # Bands chosen so Nifty 1m ATR sessions spread across low/normal/high
    # instead of collapsing into a single bucket.
    if day_range_pct < 0.80:
        return "low"
    if day_range_pct < 1.40:
        return "normal"
    return "high"


def _analog_view(samples: list[float]) -> list[float]:
    """Recent prior-day results only (session-day memory, rolling)."""
    if not samples:
        return []
    if len(samples) <= ANALOG_WINDOW:
        return samples
    return samples[-ANALOG_WINDOW:]


def _time_bucket(clock: time) -> Optional[str]:
    if READY <= clock < time(11, 0):
        return "morning"
    if time(11, 0) <= clock < CHOP_START:
        return "late_morning"
    if CHOP_END <= clock < LAST_SIGNAL:
        return "afternoon"
    return None


def _barriers(atr: float) -> tuple[float, float]:
    risk = min(MAX_RISK, max(MIN_RISK, 0.6 * atr))
    return risk, PAYOFF * risk


def _resolve(
    day: list[Bar], start: int, direction: str, entry: float, risk: float, reward: float
) -> tuple[float, str]:
    """Walk forward from the fill. A bar that touches both prices takes the stop."""
    stop = entry - risk if direction == "buy" else entry + risk
    target = entry + reward if direction == "buy" else entry - reward
    last = min(len(day) - 1, start + HOLD_BARS - 1)
    for index in range(start, last + 1):
        bar = day[index]
        if direction == "buy":
            if bar.open <= stop:
                return bar.open, "stop"
            if bar.low <= stop:
                return stop, "stop"
            if bar.open >= target:
                return bar.open, "target"
            if bar.high >= target:
                return target, "target"
        else:
            if bar.open >= stop:
                return bar.open, "stop"
            if bar.high >= stop:
                return stop, "stop"
            if bar.open <= target:
                return bar.open, "target"
            if bar.low <= target:
                return target, "target"
        if _clock(bar) >= FLAT_AT:
            return bar.close, "session_end"
    return day[last].close, "time_stop"


def _extended_from_range(
    direction: str,
    auction: str,
    entry: float,
    opening_high: float,
    opening_low: float,
    atr: float,
) -> bool:
    """An opening-range call is valid only while the fill is still near that range."""
    limit = max(40.0, atr * 2.0)
    if direction == "buy" and auction == "above":
        return entry - opening_high > limit
    if direction == "sell" and auction == "below":
        return opening_low - entry > limit
    return False


def _chased(direction: str, signal_close: float, entry: float, atr: float) -> bool:
    """A fill more than half an ATR beyond the signal close is no longer the same call."""
    limit = max(10.0, 0.5 * atr)
    if direction == "buy":
        return entry - signal_close > limit
    return signal_close - entry > limit


def _room_for_target(
    direction: str, entry: float, reward: float, prior: Optional[dict[str, float]]
) -> bool:
    """A prior-day extreme blocks a target only while price has not already cleared it."""
    if prior is None:
        return True
    if direction == "buy" and entry < prior["high"]:
        return prior["high"] - entry >= reward
    if direction == "sell" and entry > prior["low"]:
        return entry - prior["low"] >= reward
    return True


def _points(direction: str, entry: float, exit_price: float) -> float:
    return exit_price - entry if direction == "buy" else entry - exit_price


def _hypothesis(
    auction: str, vwap_side: str, swing: str, location: Optional[float]
) -> Optional[str]:
    """Direction is allowed only when the candle also closes in that direction."""
    direction = None
    if auction == "above" and vwap_side == "above" and swing != "down":
        direction = "buy"
    elif auction == "below" and vwap_side == "below" and swing != "up":
        direction = "sell"
    elif auction == "failed_up" and vwap_side == "below" and swing != "up":
        direction = "sell"
    elif auction == "failed_down" and vwap_side == "above" and swing != "down":
        direction = "buy"
    if direction == "buy" and (location is None or location < 0.60):
        return None
    if direction == "sell" and (location is None or location > 0.40):
        return None
    return direction


def _probability_blocks(bar: Bar, direction: str) -> bool:
    value = bar.buy_probability if direction == "buy" else bar.sell_probability
    return value is not None and value < PROBABILITY_MIN


class DayBook:
    """One session, with the auction state updated only from closed bars."""

    def __init__(self, day: list[Bar]):
        self.day = day
        self.vwap, self.sigma, self.atr, self.location = _session_math(day)
        opening = _opening_range(day)
        self.opening_high = None if opening is None else opening[0]
        self.opening_low = None if opening is None else opening[1]
        self.highs, self.lows = _swings(day)
        self.break_side: Optional[str] = None
        self.fail_side: Optional[str] = None
        self.fail_until = -1
        self.vol_bucket: Optional[str] = None

    def state(self, index: int) -> Optional[dict]:
        bar = self.day[index]
        clock = _clock(bar)
        if self.opening_high is None or self.opening_low is None:
            return None
        if clock >= READY:
            if bar.close > self.opening_high:
                self.break_side = "buy"
                self.fail_side = None
            elif bar.close < self.opening_low:
                self.break_side = "sell"
                self.fail_side = None
            elif self.break_side == "buy":
                self.fail_side = "failed_up"
                self.fail_until = index + FAIL_WINDOW
                self.break_side = None
            elif self.break_side == "sell":
                self.fail_side = "failed_down"
                self.fail_until = index + FAIL_WINDOW
                self.break_side = None
        if self.fail_side is not None and index > self.fail_until:
            self.fail_side = None
        bucket = _time_bucket(clock)
        if self.vol_bucket is None and self.atr[index] is not None:
            self.vol_bucket = _vix_bucket(bar, self.atr[index])
        if (
            bucket is None
            or self.vwap[index] is None
            or self.sigma[index] is None
            or self.atr[index] is None
            or self.vol_bucket is None
        ):
            return None
        if self.fail_side is not None:
            auction = self.fail_side
        elif bar.close > self.opening_high:
            auction = "above"
        elif bar.close < self.opening_low:
            auction = "below"
        else:
            auction = "inside"
        band = max(2.0, float(self.sigma[index]) * 0.15)
        if bar.close > float(self.vwap[index]) + band:
            vwap_side = "above"
        elif bar.close < float(self.vwap[index]) - band:
            vwap_side = "below"
        else:
            vwap_side = "neutral"
        swing = _bias(index, self.highs, self.lows)
        direction = _hypothesis(auction, vwap_side, swing, self.location[index])
        return {
            "key": (self.vol_bucket, auction, vwap_side, swing, bucket),
            "direction": direction,
            "auction": auction,
            "vwap_side": vwap_side,
            "swing": swing,
            "time_bucket": bucket,
            "vwap": float(self.vwap[index]),
            "sigma": float(self.sigma[index]),
            "atr": float(self.atr[index]),
            "location": self.location[index],
        }


def label_day(day: list[Bar]) -> dict[tuple, float]:
    """First completed result of each state. Later days may learn from it."""
    book = DayBook(day)
    stored: dict[tuple, float] = {}
    for index in range(len(day) - 1):
        snapshot = book.state(index)
        if snapshot is None or snapshot["direction"] is None:
            continue
        key = snapshot["key"] + (snapshot["direction"],)
        if key in stored:
            continue
        entry_bar = day[index + 1]
        if _chased(snapshot["direction"], day[index].close, entry_bar.open, snapshot["atr"]):
            continue
        if _extended_from_range(
            snapshot["direction"],
            snapshot["auction"],
            entry_bar.open,
            book.opening_high,
            book.opening_low,
            snapshot["atr"],
        ):
            continue
        risk, reward = _barriers(snapshot["atr"])
        exit_price, _reason = _resolve(
            day, index + 1, snapshot["direction"], entry_bar.open, risk, reward
        )
        stored[key] = _points(snapshot["direction"], entry_bar.open, exit_price)
    return stored


def scan_day(
    day: list[Bar],
    memory: dict[tuple, list[float]],
    prior: Optional[dict[str, float]],
    profile: str | StateProfile = "baseline",
) -> list[dict]:
    cfg = resolve_profile(profile)
    book = DayBook(day)
    calls: list[dict] = []
    position: Optional[dict] = None
    used_keys: set[tuple] = set()
    for index, bar in enumerate(day):
        snapshot = book.state(index)
        if position is not None:
            risk = float(position["risk"])
            reward = float(position["reward"])
            exit_price, reason = _one_bar(
                bar, position["direction"], float(position["entry"]), risk, reward
            )
            if exit_price is None and (
                _clock(bar) >= FLAT_AT or index - int(position["entry_index"]) >= HOLD_BARS - 1
            ):
                exit_price, reason = (
                    bar.close,
                    "session_end" if _clock(bar) >= FLAT_AT else "time_stop",
                )
            if exit_price is not None:
                position["exit_time"] = bar.dt.isoformat(sep=" ")
                position["exit"] = exit_price
                position["reason"] = reason
                position["points"] = _points(
                    position["direction"], float(position["entry"]), exit_price
                )
                calls.append(position)
                position = None
            continue
        if (
            snapshot is None
            or snapshot["direction"] is None
            or index + 1 >= len(day)
            or len(calls) >= cfg.max_calls
        ):
            continue
        if cfg.auctions and snapshot["auction"] not in cfg.auctions:
            continue
        if cfg.time_buckets and snapshot["time_bucket"] not in cfg.time_buckets:
            continue
        key = snapshot["key"] + (snapshot["direction"],)
        if key in used_keys or _probability_blocks(bar, snapshot["direction"]):
            continue
        samples = _analog_view(memory.get(key, []))
        if len(samples) < cfg.min_analogs:
            continue
        wins = sum(1 for points in samples if points > 0.0)
        hit_rate = wins / len(samples)
        average = sum(samples) / len(samples)
        if hit_rate < cfg.min_hit_rate or average <= COST_POINTS:
            continue
        if (average - COST_POINTS) < cfg.min_avg_edge:
            continue
        entry = day[index + 1].open
        risk, reward = _barriers(snapshot["atr"])
        if _chased(snapshot["direction"], bar.close, entry, snapshot["atr"]):
            continue
        if _extended_from_range(
            snapshot["direction"],
            snapshot["auction"],
            entry,
            book.opening_high,
            book.opening_low,
            snapshot["atr"],
        ):
            continue
        if not _room_for_target(snapshot["direction"], entry, reward, prior):
            continue
        stop = entry - risk if snapshot["direction"] == "buy" else entry + risk
        target = entry + reward if snapshot["direction"] == "buy" else entry - reward
        position = {
            "date": bar.dt.date().isoformat(),
            "direction": snapshot["direction"],
            "state": "|".join(snapshot["key"]),
            "signal_time": bar.dt.isoformat(sep=" "),
            "entry_time": day[index + 1].dt.isoformat(sep=" "),
            "entry_index": index + 1,
            "entry": entry,
            "stop": stop,
            "target": target,
            "risk": risk,
            "reward": reward,
            "analog_count": len(samples),
            "analog_hit_rate": round(hit_rate, 4),
            "analog_average_points": round(average, 2),
            "profile": cfg.name,
            "indications": (
                f"profile={cfg.name}; state={snapshot['key']}; vwap={snapshot['vwap']:.2f}; "
                f"sigma={snapshot['sigma']:.2f}; atr={snapshot['atr']:.2f}; "
                f"swing={snapshot['swing']}; auction={snapshot['auction']}; "
                f"analogs={len(samples)}; hit_rate={hit_rate:.3f}; average={average:.2f}"
            ),
        }
        used_keys.add(key)
    if position is not None:
        last = day[-1]
        position["exit_time"] = last.dt.isoformat(sep=" ")
        position["exit"] = last.close
        position["reason"] = "session_end"
        position["points"] = _points(position["direction"], float(position["entry"]), last.close)
        calls.append(position)
    return calls


def _one_bar(
    bar: Bar, direction: str, entry: float, risk: float, reward: float
) -> tuple[Optional[float], Optional[str]]:
    stop = entry - risk if direction == "buy" else entry + risk
    target = entry + reward if direction == "buy" else entry - reward
    if direction == "buy":
        if bar.open <= stop or bar.low <= stop:
            return (bar.open if bar.open <= stop else stop), "stop"
        if bar.open >= target or bar.high >= target:
            return (bar.open if bar.open >= target else target), "target"
        return None, None
    if bar.open >= stop or bar.high >= stop:
        return (bar.open if bar.open >= stop else stop), "stop"
    if bar.open <= target or bar.low <= target:
        return (bar.open if bar.open <= target else target), "target"
    return None, None


def validate_calls(calls: list[dict], max_calls: int = MAX_CALLS) -> None:
    by_day: dict[str, list[dict]] = {}
    for call in calls:
        entry = float(call["entry"])
        stop = float(call["stop"])
        target = float(call["target"])
        if call["direction"] == "buy" and not stop < entry < target:
            raise ValueError("Buy prices are in the wrong order.")
        if call["direction"] == "sell" and not target < entry < stop:
            raise ValueError("Sell prices are in the wrong order.")
        risk = abs(entry - stop)
        if abs(abs(target - entry) / risk - PAYOFF) > 0.02:
            raise ValueError("Target is not 1.7 times the risk.")
        if datetime.fromisoformat(call["entry_time"]) <= datetime.fromisoformat(
            call["signal_time"]
        ):
            raise ValueError("Entry is not after the signal.")
        by_day.setdefault(call["date"], []).append(call)
    for day_calls in by_day.values():
        if len(day_calls) > max_calls:
            raise ValueError("A session has more than the profile call cap.")
        previous_exit = None
        for call in day_calls:
            entry_time = datetime.fromisoformat(call["entry_time"])
            if previous_exit is not None and entry_time < previous_exit:
                raise ValueError("Two calls overlap.")
            previous_exit = datetime.fromisoformat(str(call["exit_time"]))


def run(raw_bars: list[dict], profile: str | StateProfile = "baseline") -> list[dict]:
    cfg = resolve_profile(profile)
    bars = [parse_bar(raw) for raw in raw_bars]
    bars.sort(key=lambda bar: bar.dt)
    sessions: dict[str, list[Bar]] = {}
    for bar in bars:
        if OPEN <= _clock(bar) <= time(15, 30):
            sessions.setdefault(bar.dt.date().isoformat(), []).append(bar)
    memory: dict[tuple, list[float]] = {}
    calls: list[dict] = []
    prior = None
    for day_key in sorted(sessions):
        day = sessions[day_key]
        # Scan uses only *prior* session days in memory (today not labeled yet).
        calls.extend(scan_day(day, memory, prior, profile=cfg))
        for key, points in label_day(day).items():
            bucket = memory.setdefault(key, [])
            bucket.append(points)
            # Cap stored history so memory tracks recent regimes.
            if len(bucket) > ANALOG_WINDOW * 3:
                del bucket[: len(bucket) - ANALOG_WINDOW * 3]
        prior = {
            "high": max(bar.high for bar in day),
            "low": min(bar.low for bar in day),
            "close": day[-1].close,
        }
    validate_calls(calls, max_calls=cfg.max_calls)
    return calls


def summarize(calls: list[dict], cost_points: float = COST_POINTS) -> dict:
    if not calls:
        return {"calls": 0, "hit_rate": None, "net_points": 0.0, "calls_per_day": None}
    nets = [float(call["points"]) - cost_points for call in calls]
    wins = sum(1 for value in nets if value > 0.0)
    days = len({call["date"] for call in calls})
    return {
        "calls": len(calls),
        "wins": wins,
        "losses": sum(1 for value in nets if value < 0.0),
        "hit_rate": wins / len(calls),
        "net_points": sum(nets),
        "calls_per_day": len(calls) / days if days else None,
    }


if __name__ == "__main__":
    import argparse
    import csv
    import json

    parser = argparse.ArgumentParser(description="State-conditional Nifty futures calls.")
    parser.add_argument("csv", help="1-minute Nifty futures CSV")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="baseline")
    parser.add_argument("--cost-points", type=float, default=COST_POINTS)
    parser.add_argument("--output", default="nifty_state_calls.csv")
    args = parser.parse_args()

    with open(args.csv, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    # normalize column names
    raw = []
    for row in rows:
        lower = {str(k).lower(): v for k, v in row.items()}
        if "datetime" not in lower:
            for alt in ("date", "timestamp", "time"):
                if alt in lower:
                    lower["datetime"] = lower[alt]
                    break
        raw.append(lower)
    calls = run(raw, profile=args.profile)
    if calls:
        with open(args.output, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(calls[0].keys()))
            writer.writeheader()
            writer.writerows(calls)
    print(json.dumps(summarize(calls, cost_points=args.cost_points), indent=2))
    print(f"Wrote {args.output} · {len(calls)} calls")
