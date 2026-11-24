"""Replay held stream-tag recipes onto Phase-1 desks (all levels)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from prod_live.holding_accurate.phase2c.builders import union_day_cap2, union_unique_days


def _hm_mins(hm: str) -> int:
    try:
        h, m = str(hm).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 12 * 60


def _side(r: dict) -> str:
    return str(r.get("decision") or "").upper()


def first_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")].append(r)
    out = []
    for day in sorted(by):
        out.append(
            sorted(
                by[day],
                key=lambda x: (_hm_mins(str(x.get("hm") or "99:99")), -float(x.get("p_t1") or 0)),
            )[0]
        )
    return out


def bestp_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")].append(r)
    out = []
    for day in sorted(by):
        out.append(max(by[day], key=lambda x: float(x.get("p_t1") or 0)))
    return out


def last_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")].append(r)
    out = []
    for day in sorted(by):
        out.append(
            sorted(
                by[day],
                key=lambda x: (_hm_mins(str(x.get("hm") or "00:00")), float(x.get("p_t1") or 0)),
                reverse=True,
            )[0]
        )
    return out


def mid_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")].append(r)
    out = []
    for day in sorted(by):
        ordered = sorted(by[day], key=lambda x: _hm_mins(str(x.get("hm") or "99:99")))
        out.append(ordered[len(ordered) // 2])
    return out


def second_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")].append(r)
    out = []
    for day in sorted(by):
        ordered = sorted(
            by[day],
            key=lambda x: (_hm_mins(str(x.get("hm") or "99:99")), -float(x.get("p_t1") or 0)),
        )
        if len(ordered) >= 2:
            out.append(ordered[1])
    return out


def weekday_filt(rows: List[dict], weekdays: Set[int]) -> List[dict]:
    import pandas as pd

    out = []
    for r in rows:
        try:
            wd = pd.Timestamp(str(r.get("day") or "")).weekday()
        except Exception:
            continue
        if wd in weekdays:
            out.append(r)
    return out


def stamp(
    rows: Iterable[dict],
    desk_tag: str,
    *,
    level: str,
    accuracy_range: str = "",
    accuracy_lo: Optional[float] = None,
    accuracy_hi: Optional[float] = None,
    accuracy_band: str = "",
    tags: Optional[List[str]] = None,
) -> List[dict]:
    """Stamp desk + accuracy multi-tags onto rows."""
    out = []
    for r in rows:
        rr = dict(r)
        accurate = rr.get("holding_tag") or rr.get("accurate_tag") or desk_tag
        rr["desk_tag"] = desk_tag
        rr["accurate_tag"] = accurate
        rr["logic_level"] = level
        rr["lane"] = "HOLDING"
        rr["status"] = "HOLDING"
        if accuracy_range:
            rr["accuracy_tag"] = accuracy_range
            rr["accuracy_range_tag"] = accuracy_range
        if accuracy_lo is not None:
            rr["accuracy_lo"] = accuracy_lo
        if accuracy_hi is not None:
            rr["accuracy_hi"] = accuracy_hi
        if accuracy_band:
            rr["accuracy_band"] = accuracy_band
        if tags:
            rr["tags"] = list(tags)
        elif accuracy_range:
            band_t = f"ACC_BAND_{accuracy_band}" if accuracy_band else None
            built = [accurate, accuracy_range]
            if band_t:
                built.append(band_t)
            built.append(f"LOGIC_{level}")
            seen: Set[str] = set()
            rr["tags"] = [t for t in built if t and not (t in seen or seen.add(t))]
        out.append(rr)
    return out


def replay_tags(
    base: List[dict],
    tags: List[str],
    by_tag: Dict[str, List[dict]],
    *,
    mode: str = "day",
) -> List[dict]:
    cur = list(base)
    merge = (lambda a, b: union_day_cap2(a, b, cap=2)) if mode == "cap2" else union_unique_days
    for tag in tags:
        rows = by_tag.get(tag)
        if not rows:
            continue
        merged = merge(cur, rows)
        if len(merged) > len(cur):
            cur = merged
    return cur
