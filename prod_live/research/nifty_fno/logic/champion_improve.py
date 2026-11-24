"""Improve weak champion tickets (esp. 5m / 10m) without touching proven.

Raw 1y caches (approx):
  15m champion ~ high hit — keep as reference only
  5m  champion ~ 40% hit — needs gates
  10m champion ~ 33% hit — needs gates

This module only **filters** existing champion rows by stricter gates.
It does not retrain packs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .proven_book import first_per_day, summarize


@dataclass(frozen=True)
class ChampGate:
    name: str
    min_p_buy: float = 0.55
    min_p_sell: float = 0.58
    require_first_break_buy: bool = True
    allow_sell_cont: bool = True
    max_or_ext: Optional[float] = None
    min_or_ext: Optional[float] = None
    buy_regimes: Optional[tuple] = None
    sell_regimes: Optional[tuple] = None
    max_mins: Optional[int] = None  # IST minutes since 00:00
    sides: Optional[tuple] = None  # ("BUY",) / ("SELL",) / both


# Live-ish baseline (for compare)
LIVE_LIKE = ChampGate(name="live_like")

# Research candidates aimed at 5m/10m accuracy
GATES: Dict[str, ChampGate] = {
    "live_like": LIVE_LIKE,
    "p_up": ChampGate(name="p_up", min_p_buy=0.62, min_p_sell=0.65),
    "first_only": ChampGate(
        name="first_only",
        min_p_buy=0.58,
        min_p_sell=0.62,
        require_first_break_buy=True,
        allow_sell_cont=False,
    ),
    "tight_ext": ChampGate(
        name="tight_ext",
        min_p_buy=0.58,
        min_p_sell=0.62,
        max_or_ext=0.25,
    ),
    "sell_only_strong": ChampGate(
        name="sell_only_strong",
        min_p_sell=0.70,
        allow_sell_cont=True,
        sides=("SELL",),
        sell_regimes=("trend",),
    ),
    "buy_range_mixed": ChampGate(
        name="buy_range_mixed",
        min_p_buy=0.62,
        require_first_break_buy=True,
        sides=("BUY",),
        buy_regimes=("range", "mixed"),
        max_or_ext=0.10,
    ),
    # Combined accuracy pick candidate
    "accurate_champ": ChampGate(
        name="accurate_champ",
        min_p_buy=0.62,
        min_p_sell=0.70,
        require_first_break_buy=True,
        allow_sell_cont=False,
        max_or_ext=0.20,
        buy_regimes=("range", "mixed"),
        sell_regimes=("trend",),
        max_mins=14 * 60,  # before 14:00
    ),
}


def _mins(row: dict) -> Optional[int]:
    if row.get("mins") is not None:
        try:
            return int(row["mins"])
        except (TypeError, ValueError):
            pass
    hm = str(row.get("hm") or "")
    try:
        h, m = hm.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def passes(row: dict, gate: ChampGate) -> bool:
    if str(row.get("track") or "").lower() not in ("champion",):
        return False
    side = str(row.get("decision") or "").upper()
    if gate.sides is not None and side not in gate.sides:
        return False
    try:
        p = float(row.get("p_t1"))
    except (TypeError, ValueError):
        return False
    # Cache rows may omit first_break / regime / or_ext — only enforce when present.
    has_first = "first_break" in row and row.get("first_break") is not None
    first = bool(row.get("first_break")) if has_first else None
    regime_raw = row.get("regime")
    regime = str(regime_raw).lower() if regime_raw not in (None, "") else None
    try:
        or_ext = float(row["or_ext"]) if row.get("or_ext") is not None else None
    except (TypeError, ValueError):
        or_ext = None
    mins = _mins(row)

    if side == "BUY":
        if p < gate.min_p_buy:
            return False
        if gate.require_first_break_buy and first is False:
            return False
        if gate.buy_regimes is not None and regime is not None and regime not in gate.buy_regimes:
            return False
    elif side == "SELL":
        if p < gate.min_p_sell:
            return False
        if first is False and not gate.allow_sell_cont:
            return False
        if gate.sell_regimes is not None and regime is not None and regime not in gate.sell_regimes:
            return False
    else:
        return False

    if gate.max_or_ext is not None and or_ext is not None and or_ext > gate.max_or_ext:
        return False
    if gate.min_or_ext is not None and or_ext is not None and or_ext < gate.min_or_ext:
        return False
    if gate.max_mins is not None and mins is not None and mins > gate.max_mins:
        return False
    return True


def apply_gate(rows: Iterable[dict], gate: ChampGate | str) -> List[dict]:
    if isinstance(gate, str):
        gate = GATES[gate]
    out = [dict(r) for r in rows if passes(r, gate)]
    for r in out:
        r["champ_gate"] = gate.name
    return first_per_day(out)


def sweep_gates(
    rows: Sequence[dict],
    *,
    start: str,
    end: str,
    min_n: int = 8,
) -> List[Dict[str, Any]]:
    clipped = [r for r in rows if start <= str(r.get("day") or "")[:10] <= end]
    board = []
    for name, gate in GATES.items():
        picked = apply_gate(clipped, gate)
        summary = summarize(picked)
        summary["gate"] = name
        summary["ok"] = (summary["n"] >= min_n) and (
            (summary["hit_rate"] or 0) >= 0.70
        )
        board.append({"gate": name, "summary": summary, "rows": picked})
    board.sort(
        key=lambda b: (
            -(b["summary"].get("hit_rate") or 0),
            -(b["summary"].get("net_points") or 0),
            -(b["summary"].get("n") or 0),
        )
    )
    return board
