"""STACK_PLUS_CROWN_HTF_CAP2 — volume desk union + accurate stamp."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

PRIORITY = {
    "proven_100": 0,
    "good_prod2": 1,
    "pre_dual_single": 1,
    "champion": 2,
    "crown_5m": 3,
}
DAY_CAP = 2


def _hm(r: dict) -> str:
    return str(r.get("hm") or "")


def _side(r: dict) -> str:
    return str(r.get("decision") or "").upper()


def _p(r: dict) -> float:
    for k in ("p_t1", "score", "p"):
        if r.get(k) is not None:
            try:
                return float(r[k])
            except Exception:
                pass
    return 0.0


def union_day_cap2(
    tracks: Dict[str, List[dict]],
    *,
    day_cap: int = DAY_CAP,
) -> List[dict]:
    """Priority proven > good > champ > crown; day cap; same side only."""
    by_day: Dict[str, List[dict]] = defaultdict(list)
    for track, rows in tracks.items():
        pri = PRIORITY.get(track, 9)
        for r in rows:
            rr = dict(r)
            rr["track"] = track
            rr["priority"] = pri
            by_day[rr["day"]].append(rr)

    out: List[dict] = []
    for day in sorted(by_day):
        cands = sorted(
            by_day[day],
            key=lambda r: (r.get("priority", 9), -_p(r), _hm(r)),
        )
        picked: List[dict] = []
        side_lock: Optional[str] = None
        seen: Set[Tuple[str, str, str]] = set()
        for r in cands:
            if len(picked) >= day_cap:
                break
            side = _side(r)
            if side_lock is None:
                side_lock = side
            elif side != side_lock:
                continue
            key = (day, side, _hm(r))
            if key in seen:
                continue
            seen.add(key)
            picked.append(r)
        out.extend(picked)
    return out


def call_key(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day") or ""), _side(r), _hm(r))


def stamp_accurate(
    stack_rows: Iterable[dict],
    agree_exact_keys: Set[Tuple[str, str, str]],
    *,
    tag: str = "AGREE_15M_ANY5",
) -> List[dict]:
    """Stamp accurate_tag on exact Part G agree entries inside the stack."""
    out = []
    for r in stack_rows:
        rr = dict(r)
        ok = call_key(rr) in agree_exact_keys
        rr["accurate"] = ok
        rr["accurate_tag"] = tag if ok else None
        out.append(rr)
    return out


def merge_stack_plus_agree(
    stack_rows: List[dict],
    agree_rows: List[dict],
) -> List[dict]:
    """Additive desk: stack first, then agree extras not exact-duped."""
    seen = {call_key(r) for r in stack_rows}
    out = [dict(r) for r in stack_rows]
    for r in agree_rows:
        k = call_key(r)
        if k in seen:
            continue
        rr = dict(r)
        rr["track"] = "agree_15m_any5"
        rr["accurate"] = True
        rr["accurate_tag"] = "AGREE_15M_ANY5"
        out.append(rr)
        seen.add(k)
    return out
