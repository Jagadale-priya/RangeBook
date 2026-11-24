"""CONFIRM dual-TF research (not finalized / not live).

Prod facts:
  - 15m dual `proven_100` is already in the live stack
  - 5m has NO proven — only `crown_5m` in prod
  - Replaying dual packs on 5m is research-only (~52% alone)

Deep hunt winners (3y, both-year 100%):
  1) `CONFIRM_DUAL15_DUAL5_TIME30` — pure 5m entry, timed agree · n=11
  2) `PROVEN15_PLUS_CONFIRM_T30` — prod proven ∪ (1) on non-proven days · n=49

Crown timed-agree with dual15 is empty at ±30m — do not use crown as timed confirm entry.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

TAG_CONFIRM = "CONFIRM_DUAL15_DUAL5_TIME30"
TAG_PLUS = "PROVEN15_PLUS_CONFIRM_T30"
TOL_MIN = 30
STATUS = "RESEARCH"


def _side(r: dict) -> str:
    return str(r.get("decision") or "").upper()


def _hm_mins(hm: str) -> int:
    try:
        h, m = str(hm).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 12 * 60


def _p(r: dict) -> float:
    try:
        return float(r.get("p_t1") or 0)
    except Exception:
        return 0.0


def build_confirm_rows(
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    *,
    tol_min: int = TOL_MIN,
) -> List[dict]:
    """Same day+side, clocks within ±tol; entry = best p 5m dual ticket."""
    by15: Dict[Tuple[str, str], List[dict]] = {}
    for r in dual15:
        side = _side(r)
        if side not in ("BUY", "SELL"):
            continue
        by15.setdefault((str(r.get("day") or ""), side), []).append(r)

    by5: Dict[Tuple[str, str], List[dict]] = {}
    for r in dual5:
        side = _side(r)
        if side not in ("BUY", "SELL"):
            continue
        by5.setdefault((str(r.get("day") or ""), side), []).append(r)

    out: List[dict] = []
    for key, grows in by15.items():
        frows = by5.get(key) or []
        if not frows:
            continue
        picked: Optional[dict] = None
        agree_hm = None
        gate_track = None
        for g in sorted(grows, key=lambda x: _hm_mins(str(x.get("hm") or "99:99"))):
            gm = _hm_mins(str(g.get("hm") or "12:00"))
            near = [
                f
                for f in frows
                if abs(gm - _hm_mins(str(f.get("hm") or "12:00"))) <= tol_min
            ]
            if not near:
                continue
            best = max(near, key=_p)
            picked = dict(best)
            agree_hm = g.get("hm")
            gate_track = g.get("track")
            break
        if picked is None:
            continue
        picked.update(
            {
                "accurate": True,
                "accurate_tag": TAG_CONFIRM,
                "confirm_tag": TAG_CONFIRM,
                "agree_15m_hm": agree_hm,
                "agree_15m_track": gate_track,
                "src": "5m",
                "status": STATUS,
            }
        )
        out.append(picked)
    return out


def merge_proven15_plus_confirm(
    proven15: Iterable[dict],
    confirm5: Iterable[dict],
) -> List[dict]:
    """Prod 15m proven ∪ timed 5m confirms on days proven did not fire."""
    proven_rows = [dict(r) for r in proven15]
    proven_days: Set[str] = {str(r.get("day") or "") for r in proven_rows}
    extras = []
    for r in confirm5:
        day = str(r.get("day") or "")
        if day in proven_days:
            continue
        rr = dict(r)
        rr["holding_tag"] = TAG_PLUS
        rr["accurate_tag"] = TAG_CONFIRM
        rr["status"] = STATUS
        extras.append(rr)
    for r in proven_rows:
        r.setdefault("track", "proven_100")
        r.setdefault("accurate_tag", None)
    return proven_rows + extras
