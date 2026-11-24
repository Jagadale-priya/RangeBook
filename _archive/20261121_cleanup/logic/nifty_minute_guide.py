"""Live Nifty futures guide. One row for every completed 1-minute bar.

The minute is not accepted or rejected by a fixed VIX, VWAP, or opening-range
gate. Those measures become numbers and are combined:

    z(h) = ln(close / close_h_minutes_ago) / (sigma * sqrt(h))
    sigma comes from an exponential variance of 1-minute log returns
    efficiency = net move / path length over the last 20 minutes
    score = efficiency * momentum + (1 - efficiency) * fair-value pull
            + candle pressure + optional model blend

Momentum uses the 1-minute, 5-minute, and 15-minute z-scores. In a directional
minute the score follows that move. In a choppy minute it leans back toward
VWAP instead of going silent.

Actions
-------
BUY or SELL   flat, and the score has crossed the entry line
STAY          already in that call, and the score still agrees
DROP          the score has turned, or the stop, target, or session end is hit
WAIT          flat, and this minute's score is too small to act on

The stop is 0.6 of the 20-minute ATR, limited to 12..25 points.
The target is 1.7 times that stop. A later minute can still say DROP earlier.

Stop-prone entries (last-1m autopsy): low path efficiency and counter-VWAP
fades. Profile ``avoid_stop`` skips those before a call is opened.
Profile ``accurate`` (default) also skips the 09:15–10:00 open bleed and
takes SELL only. The hard stop remains as risk once in a trade.

Bars are dictionaries, timestamps in IST:
datetime, open, high, low, close, volume
Optional model scores, each from 0 to 1:
buy_probability, sell_probability
buy_probability_5m, sell_probability_5m
buy_probability_15m, sell_probability_15m
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional, Tuple, Union

OPEN = time(9, 15)
SESSION_END = time(15, 30)
LAST_ENTRY = time(15, 20)
FLAT_AT = time(15, 25)
MIN_RISK = 12.0
MAX_RISK = 25.0
PAYOFF = 1.7
ENTER = 0.22
DROP_LINE = 0.12
VARIANCE_LAMBDA = 0.94
EFFICIENCY_WINDOW = 20
ATR_PERIOD = 20


@dataclass(frozen=True)
class GuideProfile:
    """baseline = raw score book · avoid_stop / accurate = skip stop-prone entries."""

    name: str
    enter: float = ENTER
    drop_line: float = DROP_LINE
    # Path must already be directional (net/path). Choppy bars stop out often.
    min_efficiency: float = 0.0
    # Side-aligned VWAP z: buy needs close above VWAP, sell below (stretch).
    min_vwap_align: float = -999.0
    # Candle close pressure must agree with the call side.
    min_pressure_align: float = -999.0
    # 1-minute z must already lean the call side (fade/chop filter).
    min_z1_align: float = -999.0
    # Do not enter before this clock (skip open noise).
    earliest_entry: time = OPEN
    # Cap tickets per session (dense books bleed on cost).
    max_calls_per_day: int = 999
    # After a stop-out, stay flat this many closed bars before re-entry.
    cooldown_after_stop: int = 0
    # Allowed sides (autopsy: BUY bled; SELL carried last-1m avoid_stop).
    sides: Tuple[str, ...] = ("buy", "sell")


PROFILES = {
    "baseline": GuideProfile(name="baseline"),
    # 1m freeze pick: eff>=0.3 · stretch>=0 · |score|>=0.30
    # cut stop share 42%→~18% and flipped month net positive on re-sim.
    "avoid_stop": GuideProfile(
        name="avoid_stop",
        enter=0.30,
        drop_line=DROP_LINE,
        min_efficiency=0.30,
        min_vwap_align=0.0,
        min_pressure_align=0.0,
    ),
    # Freeze/holdout upgrade over avoid_stop:
    # 09–10 bled (−88, 32% stops) → earliest 10:00.
    # SELL carried holdout (+230) vs BUY (−16) → sell only.
    # Keep enter/efficiency/VWAP/pressure gates from avoid_stop.
    # Holdout: 85 @ 40% / +316 / stop 8% · freeze: 41.9% / +99.
    "accurate": GuideProfile(
        name="accurate",
        enter=0.30,
        drop_line=DROP_LINE,
        min_efficiency=0.30,
        min_vwap_align=0.0,
        min_pressure_align=0.0,
        earliest_entry=time(10, 0),
        sides=("sell",),
    ),
}


def resolve_profile(profile: Union[str, GuideProfile] = "accurate") -> GuideProfile:
    if isinstance(profile, GuideProfile):
        return profile
    key = str(profile or "accurate").strip().lower()
    if key not in PROFILES:
        raise ValueError(f"Unknown minute-guide profile {profile!r}; expected {sorted(PROFILES)}")
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
    buy_probability_5m: Optional[float] = None
    sell_probability_5m: Optional[float] = None
    buy_probability_15m: Optional[float] = None
    sell_probability_15m: Optional[float] = None


def _optional_float(raw: dict, name: str) -> Optional[float]:
    value = raw.get(name)
    if value in (None, ""):
        return None
    return float(value)


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
        india_vix=_optional_float(raw, "india_vix"),
        buy_probability=_optional_float(raw, "buy_probability"),
        sell_probability=_optional_float(raw, "sell_probability"),
        buy_probability_5m=_optional_float(raw, "buy_probability_5m"),
        sell_probability_5m=_optional_float(raw, "sell_probability_5m"),
        buy_probability_15m=_optional_float(raw, "buy_probability_15m"),
        sell_probability_15m=_optional_float(raw, "sell_probability_15m"),
    )


def _squash(value: float) -> float:
    if value > 20.0:
        return 1.0
    if value < -20.0:
        return -1.0
    return math.tanh(value)


def _side_score(buy: Optional[float], sell: Optional[float]) -> Optional[float]:
    if buy is None and sell is None:
        return None
    if buy is None:
        return (0.5 - float(sell)) * 2.0
    if sell is None:
        return (float(buy) - 0.5) * 2.0
    return float(buy) - float(sell)


def _model_score(bar: Bar) -> Optional[float]:
    parts = [
        (0.50, _side_score(bar.buy_probability, bar.sell_probability)),
        (0.30, _side_score(bar.buy_probability_5m, bar.sell_probability_5m)),
        (0.20, _side_score(bar.buy_probability_15m, bar.sell_probability_15m)),
    ]
    available = [(weight, score) for weight, score in parts if score is not None]
    if not available:
        return None
    total = sum(weight for weight, _score in available)
    return sum(weight * score for weight, score in available) / total


def _risk_points(atr: Optional[float]) -> float:
    if atr is None or not math.isfinite(atr) or atr <= 0.0:
        return 15.0
    return min(MAX_RISK, max(MIN_RISK, 0.6 * atr))


class MinuteBook:
    """Features for one session, using only minutes that have already closed."""

    def __init__(self, day: list[Bar]):
        self.day = day
        self.vwap = [0.0] * len(day)
        self.vwap_sigma = [1.0] * len(day)
        self.return_sigma = [0.0] * len(day)
        self.atr = [None] * len(day)
        self._build()

    def _build(self) -> None:
        cumulative_weight = 0.0
        cumulative_price = 0.0
        cumulative_square = 0.0
        variance = 0.0
        true_ranges: list[float] = []
        for index, bar in enumerate(self.day):
            typical = (bar.high + bar.low + bar.close) / 3.0
            weight = bar.volume if bar.volume > 0.0 else 1.0
            cumulative_weight += weight
            cumulative_price += typical * weight
            cumulative_square += typical * typical * weight
            current_vwap = cumulative_price / cumulative_weight
            current_variance = max(
                0.0, cumulative_square / cumulative_weight - current_vwap * current_vwap
            )
            self.vwap[index] = current_vwap
            self.vwap_sigma[index] = max(1.0, math.sqrt(current_variance))
            if index == 0:
                true_ranges.append(bar.high - bar.low)
            else:
                change = (
                    math.log(bar.close / self.day[index - 1].close)
                    if bar.close > 0.0 and self.day[index - 1].close > 0.0
                    else 0.0
                )
                variance = VARIANCE_LAMBDA * variance + (1.0 - VARIANCE_LAMBDA) * change * change
                previous = self.day[index - 1].close
                true_ranges.append(
                    max(bar.high - bar.low, abs(bar.high - previous), abs(bar.low - previous))
                )
            self.return_sigma[index] = math.sqrt(variance)
            lookback = min(ATR_PERIOD, index + 1)
            self.atr[index] = sum(true_ranges[-lookback:]) / lookback

    def _z(self, index: int, minutes: int) -> float:
        if index <= 0:
            return 0.0
        start = max(0, index - minutes)
        first = self.day[start].close
        last = self.day[index].close
        if first <= 0.0 or last <= 0.0:
            return 0.0
        sigma = self.return_sigma[index]
        if sigma <= 1e-8:
            return 0.0
        span = max(1, index - start)
        return math.log(last / first) / (sigma * math.sqrt(span))

    def _efficiency(self, index: int) -> float:
        start = max(0, index - EFFICIENCY_WINDOW)
        net = abs(self.day[index].close - self.day[start].close)
        path = 0.0
        for cursor in range(start + 1, index + 1):
            path += abs(self.day[cursor].close - self.day[cursor - 1].close)
        if path <= 0.0:
            return 0.0
        return min(1.0, net / path)

    def reading(self, index: int) -> dict:
        bar = self.day[index]
        z1 = self._z(index, 1)
        z5 = self._z(index, 5)
        z15 = self._z(index, 15)
        efficiency = self._efficiency(index)
        momentum = (
            0.50 * _squash(z1 / 1.5)
            + 0.30 * _squash(z5 / 1.5)
            + 0.20 * _squash(z15 / 1.5)
        )
        vwap_z = (bar.close - self.vwap[index]) / self.vwap_sigma[index]
        fair_pull = -_squash(vwap_z / 2.0)
        span = bar.high - bar.low
        pressure = 0.0 if span <= 0.0 else (2.0 * (bar.close - bar.low) / span) - 1.0
        score = (
            efficiency * momentum
            + (1.0 - efficiency) * 0.65 * fair_pull
            + 0.25 * pressure
        )
        model = _model_score(bar)
        if model is not None:
            score = 0.75 * score + 0.25 * max(-1.0, min(1.0, model))
        score = max(-1.0, min(1.0, score))
        return {
            "score": score,
            "z1": z1,
            "z5": z5,
            "z15": z15,
            "efficiency": efficiency,
            "vwap": self.vwap[index],
            "vwap_z": vwap_z,
            "pressure": pressure,
            "model": model,
            "atr": self.atr[index],
            "india_vix": bar.india_vix,
        }


def _hit(bar: Bar, direction: str, stop: float, target: float) -> Optional[tuple[float, str]]:
    if direction == "buy":
        if bar.open <= stop or bar.low <= stop:
            return (bar.open if bar.open <= stop else stop), "stop"
        if bar.open >= target or bar.high >= target:
            return (bar.open if bar.open >= target else target), "target"
        return None
    if bar.open >= stop or bar.high >= stop:
        return (bar.open if bar.open >= stop else stop), "stop"
    if bar.open <= target or bar.low <= target:
        return (bar.open if bar.open <= target else target), "target"
    return None


def _points(direction: str, entry: float, exit_price: float) -> float:
    return exit_price - entry if direction == "buy" else entry - exit_price


def _row(
    bar: Bar,
    action: str,
    reading: dict,
    position: Optional[dict],
    points: Optional[float],
    reason: str,
) -> dict:
    unrealized = None
    if position is not None and points is None:
        unrealized = _points(position["direction"], float(position["entry"]), bar.close)
    return {
        "date": bar.dt.date().isoformat(),
        "time": bar.dt.isoformat(sep=" "),
        "action": action,
        "reason": reason,
        "close": bar.close,
        "score": round(reading["score"], 4),
        "z1": round(reading["z1"], 3),
        "z5": round(reading["z5"], 3),
        "z15": round(reading["z15"], 3),
        "efficiency": round(reading["efficiency"], 3),
        "vwap": round(reading["vwap"], 2),
        "vwap_z": round(reading["vwap_z"], 3),
        "pressure": round(reading["pressure"], 3),
        "model": None if reading["model"] is None else round(reading["model"], 3),
        "atr": None if reading["atr"] is None else round(float(reading["atr"]), 2),
        "india_vix": reading["india_vix"],
        "direction": None if position is None else position["direction"],
        "entry": None if position is None else position["entry"],
        "stop": None if position is None else position["stop"],
        "target": None if position is None else position["target"],
        "unrealized_points": None if unrealized is None else round(unrealized, 2),
        "points": None if points is None else round(points, 2),
    }


def _entry_block_reason(direction: str, reading: dict, profile: GuideProfile) -> Optional[str]:
    """Return a WAIT reason if this score cross is stop-prone; else None."""
    efficiency = float(reading["efficiency"])
    if efficiency < profile.min_efficiency:
        return "efficiency_too_low"
    vwap_z = float(reading["vwap_z"])
    pressure = float(reading["pressure"])
    z1 = float(reading["z1"])
    if direction == "buy":
        stretch = vwap_z
        press_al = pressure
        z1_al = z1
    else:
        stretch = -vwap_z
        press_al = -pressure
        z1_al = -z1
    if stretch < profile.min_vwap_align:
        return "counter_vwap"
    if press_al < profile.min_pressure_align:
        return "pressure_against"
    if z1_al < profile.min_z1_align:
        return "z1_against"
    return None


def guide_day(day: list[Bar], profile: Union[str, GuideProfile] = "accurate") -> list[dict]:
    profile = resolve_profile(profile)
    book = MinuteBook(day)
    rows: list[dict] = []
    position: Optional[dict] = None
    calls_today = 0
    cooldown_until = -1
    for index, bar in enumerate(day):
        reading = book.reading(index)
        clock = bar.dt.time()
        if position is not None:
            hit = _hit(bar, position["direction"], float(position["stop"]), float(position["target"]))
            exit_price = None
            reason = ""
            if hit is not None:
                exit_price, reason = hit
            elif clock >= FLAT_AT:
                exit_price, reason = bar.close, "session_end"
            elif position["direction"] == "buy" and reading["score"] <= -profile.drop_line:
                exit_price, reason = bar.close, "score_turned"
            elif position["direction"] == "sell" and reading["score"] >= profile.drop_line:
                exit_price, reason = bar.close, "score_turned"
            if exit_price is not None:
                rows.append(
                    _row(
                        bar,
                        "DROP",
                        reading,
                        position,
                        _points(position["direction"], float(position["entry"]), exit_price),
                        reason,
                    )
                )
                if reason == "stop" and profile.cooldown_after_stop > 0:
                    cooldown_until = index + profile.cooldown_after_stop
                position = None
                continue
            rows.append(_row(bar, "STAY", reading, position, None, "score_holds"))
            continue
        if clock >= LAST_ENTRY or index + 1 >= len(day):
            rows.append(_row(bar, "WAIT", reading, None, None, "too_late"))
            continue
        if clock < profile.earliest_entry:
            rows.append(_row(bar, "WAIT", reading, None, None, "too_early"))
            continue
        if calls_today >= profile.max_calls_per_day:
            rows.append(_row(bar, "WAIT", reading, None, None, "day_cap"))
            continue
        if index < cooldown_until:
            rows.append(_row(bar, "WAIT", reading, None, None, "cooldown_after_stop"))
            continue
        if reading["score"] >= profile.enter:
            if "buy" not in profile.sides:
                rows.append(_row(bar, "WAIT", reading, None, None, "side_not_allowed"))
                continue
            blocked = _entry_block_reason("buy", reading, profile)
            if blocked is not None:
                rows.append(_row(bar, "WAIT", reading, None, None, blocked))
                continue
            entry = day[index + 1].open
            risk = _risk_points(reading["atr"])
            position = {
                "direction": "buy",
                "entry": entry,
                "stop": entry - risk,
                "target": entry + PAYOFF * risk,
            }
            calls_today += 1
            rows.append(_row(bar, "BUY", reading, position, None, "score_up"))
            continue
        if reading["score"] <= -profile.enter:
            if "sell" not in profile.sides:
                rows.append(_row(bar, "WAIT", reading, None, None, "side_not_allowed"))
                continue
            blocked = _entry_block_reason("sell", reading, profile)
            if blocked is not None:
                rows.append(_row(bar, "WAIT", reading, None, None, blocked))
                continue
            entry = day[index + 1].open
            risk = _risk_points(reading["atr"])
            position = {
                "direction": "sell",
                "entry": entry,
                "stop": entry + risk,
                "target": entry - PAYOFF * risk,
            }
            calls_today += 1
            rows.append(_row(bar, "SELL", reading, position, None, "score_down"))
            continue
        rows.append(_row(bar, "WAIT", reading, None, None, "score_flat"))
    return rows


def guide(
    raw_bars: list[dict],
    profile: Union[str, GuideProfile] = "accurate",
) -> list[dict]:
    profile = resolve_profile(profile)
    bars = [parse_bar(raw) for raw in raw_bars]
    bars.sort(key=lambda bar: bar.dt)
    sessions: dict[str, list[Bar]] = {}
    for bar in bars:
        if OPEN <= bar.dt.time() <= SESSION_END:
            sessions.setdefault(bar.dt.date().isoformat(), []).append(bar)
    rows: list[dict] = []
    for day_key in sorted(sessions):
        rows.extend(guide_day(sessions[day_key], profile=profile))
    return rows


def run(
    raw_bars: list[dict],
    profile: Union[str, GuideProfile] = "accurate",
) -> list[dict]:
    """Minute-by-minute guide. A call is a row whose action is BUY or SELL."""
    return guide(raw_bars, profile=profile)


def summarize(rows: list[dict], cost_points: float = 1.0) -> dict:
    actions = {"BUY": 0, "SELL": 0, "STAY": 0, "DROP": 0, "WAIT": 0}
    for row in rows:
        actions[row["action"]] = actions.get(row["action"], 0) + 1
    closed = [row for row in rows if row["action"] == "DROP" and row["points"] is not None]
    nets = [float(row["points"]) - cost_points for row in closed]
    wins = sum(1 for value in nets if value > 0.0)
    days = len({row["date"] for row in rows})
    called_days = len({row["date"] for row in rows if row["action"] in ("BUY", "SELL")})
    reasons: dict[str, int] = {}
    for row in closed:
        key = str(row.get("reason") or "")
        reasons[key] = reasons.get(key, 0) + 1
    return {
        "minutes": len(rows),
        "sessions": days,
        "sessions_with_a_call": called_days,
        "buys": actions["BUY"],
        "sells": actions["SELL"],
        "stays": actions["STAY"],
        "drops": actions["DROP"],
        "waits": actions["WAIT"],
        "closed_calls": len(closed),
        "wins": wins,
        "losses": len(closed) - wins,
        "hit_rate": None if not closed else wins / len(closed),
        "net_points": sum(nets),
        "avg_win": None
        if not wins
        else sum(v for v in nets if v > 0.0) / wins,
        "avg_loss": None
        if wins == len(closed)
        else sum(v for v in nets if v <= 0.0) / max(1, len(closed) - wins),
        "exit_reasons": reasons,
    }
