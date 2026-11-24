"""Accurate NIFTY F&O research book — proven_100 only.

Listing order (one ticket per session)
--------------------------------------
1. 15m proven_100
2. 10m proven_100, only if 15m is silent that day

Champion / baseline / ORB / P2F / P2G are out of this book.

Ticket shape (from dual evaluate caches or live walk):
  day, hm, decision, track, tf, p_t1, entry, stop_loss, target_1,
  win, points, outcome, proven, champion
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

COST_POINTS = 1.0


def _day(row: dict) -> str:
    return str(row.get("day") or "")[:10]


def _side(row: dict) -> str:
    return str(row.get("decision") or "").upper()


def filter_proven(rows: Iterable[dict], *, tf: Optional[str] = None) -> List[dict]:
    out: List[dict] = []
    for row in rows:
        track = str(row.get("track") or "").lower()
        if track not in ("proven_100", "proven"):
            if not row.get("proven"):
                continue
            if track == "champion" and not row.get("proven"):
                continue
        if tf is not None and str(row.get("tf") or "") != tf:
            continue
        # Hard: must be marked proven / proven_100
        if track not in ("proven_100", "proven") and not bool(row.get("proven")):
            continue
        if track == "champion" and not bool(row.get("proven")):
            continue
        # Prefer explicit proven_100 track
        if track == "champion":
            continue
        out.append(dict(row))
    return out


def first_per_day(rows: Sequence[dict]) -> List[dict]:
    """Earliest hm wins; one ticket per day."""
    by_day: Dict[str, List[dict]] = defaultdict(list)
    for row in rows:
        day = _day(row)
        if not day:
            continue
        by_day[day].append(row)
    picked: List[dict] = []
    for day in sorted(by_day):
        group = sorted(by_day[day], key=lambda r: str(r.get("hm") or "99:99"))
        picked.append(group[0])
    return picked


def build_accurate_book(
    proven_15m: Sequence[dict],
    proven_10m: Sequence[dict] | None = None,
) -> List[dict]:
    """15m proven first; 10m proven fills silent days only."""
    p15 = first_per_day(filter_proven(proven_15m, tf="15m") or filter_proven(proven_15m))
    used = {_day(r) for r in p15}
    fills: List[dict] = []
    if proven_10m:
        for row in first_per_day(filter_proven(proven_10m, tf="10m") or filter_proven(proven_10m)):
            if _day(row) in used:
                continue
            fills.append(row)
            used.add(_day(row))
    book = list(p15) + fills
    book.sort(key=lambda r: (_day(r), str(r.get("hm") or "")))
    for row in book:
        row["book"] = "accurate_proven"
        row["desk"] = f"proven_{row.get('tf') or '15m'}"
    return book


def clip_window(rows: Sequence[dict], start: str, end: str) -> List[dict]:
    return [dict(r) for r in rows if start <= _day(r) <= end]


def summarize(rows: Sequence[dict], cost_points: float = COST_POINTS) -> Dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "wins": 0,
            "losses": 0,
            "hit_rate": None,
            "net_points": 0.0,
            "by_desk": {},
            "by_side": {},
            "sessions": 0,
        }
    nets = []
    wins = 0
    by_desk: Dict[str, Dict[str, Any]] = {}
    by_side: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        pts = float(row.get("points") or 0.0) - cost_points
        nets.append(pts)
        won = bool(row.get("win")) if "win" in row else pts > 0.0
        if won:
            wins += 1
        desk = str(row.get("desk") or row.get("tf") or "unknown")
        side = _side(row) or "?"
        for bucket, key in ((by_desk, desk), (by_side, side)):
            slot = bucket.setdefault(key, {"n": 0, "wins": 0, "net": 0.0})
            slot["n"] += 1
            slot["net"] += pts
            if won:
                slot["wins"] += 1
    for bucket in (by_desk, by_side):
        for slot in bucket.values():
            slot["hit_rate"] = None if not slot["n"] else slot["wins"] / slot["n"]
    return {
        "n": len(rows),
        "wins": wins,
        "losses": len(rows) - wins,
        "hit_rate": wins / len(rows),
        "net_points": sum(nets),
        "by_desk": by_desk,
        "by_side": by_side,
        "sessions": len({_day(r) for r in rows}),
    }


def compare_books(
    *,
    proven_15m: Sequence[dict],
    proven_10m: Sequence[dict] | None,
    champion_rows: Sequence[dict] | None,
    start: str,
    end: str,
) -> Dict[str, Any]:
    """Standard research board for the accurate folder."""
    p15 = clip_window(filter_proven(proven_15m), start, end)
    p10 = clip_window(filter_proven(proven_10m or []), start, end)
    accurate = build_accurate_book(p15, p10)
    champ = []
    if champion_rows:
        champ = first_per_day(
            [
                dict(r)
                for r in clip_window(champion_rows, start, end)
                if str(r.get("track") or "").lower() == "champion"
            ]
        )
    return {
        "window": {"start": start, "end": end},
        "proven_15m": {"rows": first_per_day(p15), "summary": summarize(first_per_day(p15))},
        "proven_10m": {"rows": first_per_day(p10), "summary": summarize(first_per_day(p10))},
        "accurate_proven": {"rows": accurate, "summary": summarize(accurate)},
        "champion_any": {"rows": champ, "summary": summarize(champ)},
    }
