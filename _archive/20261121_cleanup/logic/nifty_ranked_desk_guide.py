"""Nifty futures guide, ranked by the measured desk results.

One ticket per session. No reverse after it closes. Every 1-minute bar is
BUY, SELL, STAY, DROP, or WAIT.

Listing order
1. proven_100, when the 15-minute pack columns are present.
   Buy: regime range or mixed, buy probability >= 0.62, opening extension <= 0.10, before 13:00.
   Sell: regime trend, sell probability >= 0.58.
   Bracket: 30 points each side.
2. champion, only if proven_100 is silent.
   Buy probability >= 0.55. Sell probability >= 0.58.
   Bracket: stop 20, target 30.
3. ORB accurate, only if both dual tracks are silent.
   09:15-09:45 width 40-100. Five-minute close within 5 points of the range and on the VWAP side.
   Stop 12 points through the level. Target 20 points from the fill. Flat 14:45.

A buy below 0.55 is never taken. Two opposite passes on the same bar produce no call.
P2F and P2G tags are not a second entry.

Optional columns on the 1-minute bars:
regime, buy_probability, sell_probability, or_extension
datetime is IST. Prices are the future.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional

OPEN = time(9, 15)
OR_END = time(9, 45)
PROVEN_BUY_END = time(13, 0)
FLAT_AT = time(14, 45)
SESSION_END = time(15, 30)
MIN_WIDTH = 40.0
MAX_WIDTH = 100.0
ORB_TOUCH = 5.0
ORB_STOP = 12.0
ORB_TARGET = 20.0


@dataclass
class Bar:
    dt: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    regime: Optional[str] = None
    buy_probability: Optional[float] = None
    sell_probability: Optional[float] = None
    or_extension: Optional[float] = None


def _optional_float(raw: dict, name: str) -> Optional[float]:
    value = raw.get(name)
    if value in (None, ""):
        return None
    return float(value)


def parse_bar(raw: dict) -> Bar:
    value = raw["datetime"]
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value).replace("Z", ""))
    regime = raw.get("regime")
    return Bar(
        dt=value,
        open=float(raw["open"]),
        high=float(raw["high"]),
        low=float(raw["low"]),
        close=float(raw["close"]),
        volume=float(raw.get("volume") or 0.0),
        regime=None if regime in (None, "") else str(regime).strip().lower(),
        buy_probability=_optional_float(raw, "buy_probability"),
        sell_probability=_optional_float(raw, "sell_probability"),
        or_extension=_optional_float(raw, "or_extension"),
    )


@dataclass
class FiveBar:
    start: datetime
    end: datetime
    open: float
    high: float
    low: float
    close: float
    vwap: float
    regime: Optional[str]
    buy_probability: Optional[float]
    sell_probability: Optional[float]
    or_extension: Optional[float]


def _vwap_path(day: list[Bar]) -> list[float]:
    cumulative_weight = 0.0
    cumulative_price = 0.0
    path: list[float] = []
    for bar in day:
        typical = (bar.high + bar.low + bar.close) / 3.0
        weight = bar.volume if bar.volume > 0.0 else 1.0
        cumulative_weight += weight
        cumulative_price += typical * weight
        path.append(cumulative_price / cumulative_weight)
    return path


def _five_minute(day: list[Bar], vwap: list[float]) -> list[FiveBar]:
    groups: dict[int, list[int]] = {}
    for index, bar in enumerate(day):
        minute = bar.dt.hour * 60 + bar.dt.minute
        origin = 9 * 60 + 15
        if minute < origin:
            continue
        slot = origin + ((minute - origin) // 5) * 5
        groups.setdefault(slot, []).append(index)
    built: list[FiveBar] = []
    for slot in sorted(groups):
        indexes = groups[slot]
        first = day[indexes[0]]
        last = day[indexes[-1]]
        last_named = last
        built.append(
            FiveBar(
                start=first.dt,
                end=last.dt,
                open=first.open,
                high=max(day[index].high for index in indexes),
                low=min(day[index].low for index in indexes),
                close=last.close,
                vwap=vwap[indexes[-1]],
                regime=last_named.regime,
                buy_probability=last_named.buy_probability,
                sell_probability=last_named.sell_probability,
                or_extension=last_named.or_extension,
            )
        )
    return built


def _dual_side(bar: FiveBar) -> Optional[tuple[str, str, float, float]]:
    """Return side, desk, stop distance, target distance. Proven outranks champion."""
    buy = bar.buy_probability
    sell = bar.sell_probability
    if buy is None and sell is None:
        return None
    proven_buy = (
        buy is not None
        and buy >= 0.62
        and bar.regime in {"range", "mixed"}
        and bar.or_extension is not None
        and bar.or_extension <= 0.10
        and bar.end.time() < PROVEN_BUY_END
    )
    proven_sell = sell is not None and sell >= 0.58 and bar.regime == "trend"
    if proven_buy and proven_sell:
        return None
    if proven_buy:
        return "buy", "proven_100", 30.0, 30.0
    if proven_sell:
        return "sell", "proven_100", 30.0, 30.0
    champion_buy = buy is not None and buy >= 0.55
    champion_sell = sell is not None and sell >= 0.58
    if champion_buy and champion_sell:
        return None
    if champion_buy:
        return "buy", "champion", 20.0, 30.0
    if champion_sell:
        return "sell", "champion", 20.0, 30.0
    return None


def _opening_range(fives: list[FiveBar]) -> Optional[tuple[float, float]]:
    opening = [bar for bar in fives if OPEN <= bar.start.time() < OR_END]
    if len(opening) < 3:
        return None
    high = max(bar.high for bar in opening)
    low = min(bar.low for bar in opening)
    if not MIN_WIDTH <= high - low <= MAX_WIDTH:
        return None
    return high, low


def _orb_side(bar: FiveBar, opening_high: float, opening_low: float) -> Optional[str]:
    if bar.start.time() < OR_END:
        return None
    buy_distance = bar.close - opening_high
    sell_distance = opening_low - bar.close
    buy = 0.0 < buy_distance <= ORB_TOUCH and bar.close > bar.vwap
    sell = 0.0 < sell_distance <= ORB_TOUCH and bar.close < bar.vwap
    if buy and sell:
        return None
    if buy:
        return "buy"
    if sell:
        return "sell"
    return None


def _fill_is_close(side: str, price: float, level: float) -> bool:
    distance = price - level if side == "buy" else level - price
    return 0.0 <= distance <= ORB_TOUCH


@dataclass
class Ticket:
    desk: str
    side: str
    signal_time: datetime
    entry_time: datetime
    entry: float
    stop: float
    target: float


def _manage(bar: Bar, ticket: Ticket) -> Optional[tuple[float, str]]:
    if ticket.side == "buy":
        if bar.open <= ticket.stop or bar.low <= ticket.stop:
            return (bar.open if bar.open <= ticket.stop else ticket.stop), "stop"
        if bar.open >= ticket.target or bar.high >= ticket.target:
            return (bar.open if bar.open >= ticket.target else ticket.target), "target"
    else:
        if bar.open >= ticket.stop or bar.high >= ticket.stop:
            return (bar.open if bar.open >= ticket.stop else ticket.stop), "stop"
        if bar.open <= ticket.target or bar.low <= ticket.target:
            return (bar.open if bar.open <= ticket.target else ticket.target), "target"
    if bar.dt.time() >= FLAT_AT:
        return bar.close, "session_end"
    return None


def _points(side: str, entry: float, exit_price: float) -> float:
    return exit_price - entry if side == "buy" else entry - exit_price


def _guide_row(
    bar: Bar,
    action: str,
    reason: str,
    ticket: Optional[Ticket],
    points: Optional[float],
) -> dict:
    unrealized = None
    if ticket is not None and points is None and action == "STAY":
        unrealized = round(_points(ticket.side, ticket.entry, bar.close), 2)
    return {
        "date": bar.dt.date().isoformat(),
        "time": bar.dt.isoformat(sep=" "),
        "action": action,
        "reason": reason,
        "desk": None if ticket is None else ticket.desk,
        "direction": None if ticket is None else ticket.side,
        "close": bar.close,
        "entry": None if ticket is None else ticket.entry,
        "stop": None if ticket is None else ticket.stop,
        "target": None if ticket is None else ticket.target,
        "unrealized_points": unrealized,
        "points": None if points is None else round(points, 2),
    }


def _plan_ticket(fives: list[FiveBar]) -> Optional[Ticket]:
    opening = _opening_range(fives)
    for index, bar in enumerate(fives[:-1]):
        dual = _dual_side(bar)
        if dual is not None:
            side, desk, stop_points, target_points = dual
            entry_bar = fives[index + 1]
            entry = entry_bar.open
            if side == "buy":
                return Ticket(
                    desk,
                    side,
                    bar.end,
                    entry_bar.start,
                    entry,
                    entry - stop_points,
                    entry + target_points,
                )
            return Ticket(
                desk,
                side,
                bar.end,
                entry_bar.start,
                entry,
                entry + stop_points,
                entry - target_points,
            )
        if opening is None:
            continue
        opening_high, opening_low = opening
        side = _orb_side(bar, opening_high, opening_low)
        if side is None:
            continue
        level = opening_high if side == "buy" else opening_low
        entry_bar = fives[index + 1]
        if not _fill_is_close(side, entry_bar.open, level):
            continue
        entry = entry_bar.open
        if side == "buy":
            return Ticket(
                "orb_accurate",
                side,
                bar.end,
                entry_bar.start,
                entry,
                opening_high - ORB_STOP,
                entry + ORB_TARGET,
            )
        return Ticket(
            "orb_accurate",
            side,
            bar.end,
            entry_bar.start,
            entry,
            opening_low + ORB_STOP,
            entry - ORB_TARGET,
        )
    return None


def guide_day(
    day: list[Bar],
    ticket: Optional[Ticket] = None,
    *,
    use_planner: bool = True,
) -> list[dict]:
    """If ``use_planner`` is False, a None ticket means a silent session (no re-plan)."""
    if not day:
        return []
    vwap = _vwap_path(day)
    if use_planner and ticket is None:
        ticket = _plan_ticket(_five_minute(day, vwap))
    rows: list[dict] = []
    active: Optional[Ticket] = None
    closed = False
    for bar in day:
        if closed or ticket is None:
            rows.append(
                _guide_row(
                    bar,
                    "WAIT",
                    "no_quality_ticket" if ticket is None else "done",
                    None,
                    None,
                )
            )
            continue
        if active is None:
            if bar.dt < ticket.entry_time:
                rows.append(_guide_row(bar, "WAIT", "waiting_for_fill", None, None))
                continue
            active = ticket
            rows.append(
                _guide_row(
                    bar,
                    "BUY" if ticket.side == "buy" else "SELL",
                    ticket.desk,
                    ticket,
                    None,
                )
            )
            outcome = _manage(bar, ticket)
            if outcome is not None:
                exit_price, reason = outcome
                rows[-1]["action"] = "DROP"
                rows[-1]["reason"] = reason
                rows[-1]["points"] = round(_points(ticket.side, ticket.entry, exit_price), 2)
                active = None
                closed = True
            continue
        outcome = _manage(bar, active)
        if outcome is None:
            rows.append(_guide_row(bar, "STAY", "holding", active, None))
            continue
        exit_price, reason = outcome
        rows.append(
            _guide_row(
                bar,
                "DROP",
                reason,
                active,
                _points(active.side, active.entry, exit_price),
            )
        )
        active = None
        closed = True
    return rows


def guide(raw_bars: list[dict]) -> list[dict]:
    bars = [parse_bar(raw) for raw in raw_bars]
    bars.sort(key=lambda bar: bar.dt)
    sessions: dict[str, list[Bar]] = {}
    for bar in bars:
        if OPEN <= bar.dt.time() <= SESSION_END:
            sessions.setdefault(bar.dt.date().isoformat(), []).append(bar)
    rows: list[dict] = []
    for day_key in sorted(sessions):
        rows.extend(guide_day(sessions[day_key]))
    return rows


def run(raw_bars: list[dict]) -> list[dict]:
    """Minute guide. Entries are the rows whose action is BUY or SELL."""
    return guide(raw_bars)


def summarize(rows: list[dict], cost_points: float = 1.0) -> dict:
    closed = [row for row in rows if row["action"] == "DROP" and row["points"] is not None]
    nets = [float(row["points"]) - cost_points for row in closed]
    wins = sum(1 for value in nets if value > 0.0)
    by_desk: dict[str, dict] = {}
    for row in closed:
        desk = str(row.get("desk") or "unknown")
        bucket = by_desk.setdefault(desk, {"n": 0, "wins": 0, "net": 0.0})
        pts = float(row["points"]) - cost_points
        bucket["n"] += 1
        bucket["net"] += pts
        if pts > 0.0:
            bucket["wins"] += 1
    for desk, bucket in by_desk.items():
        bucket["hit_rate"] = None if not bucket["n"] else bucket["wins"] / bucket["n"]
    return {
        "minutes": len(rows),
        "sessions": len({row["date"] for row in rows}),
        "entries": sum(1 for row in rows if row["action"] in ("BUY", "SELL")),
        "closed_calls": len(closed),
        "hit_rate": None if not closed else wins / len(closed),
        "net_points": sum(nets),
        "wins": wins,
        "losses": len(closed) - wins,
        "by_desk": by_desk,
        "silent_sessions": len(
            {
                row["date"]
                for row in rows
                if row["action"] == "WAIT" and row["reason"] == "no_quality_ticket"
            }
            - {row["date"] for row in rows if row["action"] in ("BUY", "SELL", "DROP")}
        ),
    }
