"""Path-true accuracy stream desks (HOLDING — not live).

Desks (KEEP ALL — do not drop earlier versions):
  ACC100_MULTI_V1..V5 — nested 100% desks (V5 ~141 @ 100% 3y)
  ACC_WIDE_P92 / P90 / P85 / P85B / P80 / P75 — day-dedupe volume ladder
  ACC_WIDE_P80_CAP2 / P75_CAP2 — day-cap2 volume (filter later)

Hard constraints: each stream locks its own path risk / gap / HTF gates.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set

from .confirm_dual_tf import (
    TAG_CONFIRM,
    build_confirm_rows,
    merge_proven15_plus_confirm,
)

TAG_CROWN = "ACC100_CROWN_BUY_AM1130_T20"
TAG_GOOD = "ACC100_GOOD_BUY_LATEMID_GAP045_T30"
TAG_DESK = "ACC100_MULTI_V1"
TAG_DESK_V2 = "ACC100_MULTI_V2"
TAG_DESK_V3 = "ACC100_MULTI_V3"
TAG_DESK_V4 = "ACC100_MULTI_V4"
TAG_DESK_V5 = "ACC100_MULTI_V5"
TAG_WIDE_P92 = "ACC_WIDE_P92"
TAG_WIDE_P90 = "ACC_WIDE_P90"
TAG_WIDE_P85 = "ACC_WIDE_P85"
TAG_WIDE_P85B = "ACC_WIDE_P85B"
TAG_WIDE_P80 = "ACC_WIDE_P80"
TAG_WIDE_P75 = "ACC_WIDE_P75"
TAG_WIDE_P80_CAP2 = "ACC_WIDE_P80_CAP2"
TAG_WIDE_P75_CAP2 = "ACC_WIDE_P75_CAP2"
STATUS = "HOLDING"

CROWN_RISK = 20.0
CROWN_HM_LO = 9 * 60 + 15
CROWN_HM_HI = 11 * 60 + 30  # inclusive window used in research ≤11:30

GOOD_RISK = 30.0
GOOD_HM_LO = 10 * 60 + 30
GOOD_HM_HI = 14 * 60
GOOD_GAP_ABS = 0.45


def _hm_mins(hm: str) -> int:
    try:
        h, m = str(hm).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 12 * 60


def _side(r: dict) -> str:
    return str(r.get("decision") or "").upper()


def filter_crown_buy_am1130(rows: Iterable[dict]) -> List[dict]:
    """First BUY crown of day with hm in [09:15, 11:30]. Caller must path-score @ T20."""
    cands: Dict[str, List[dict]] = {}
    for r in rows:
        if _side(r) != "BUY":
            continue
        hm = _hm_mins(str(r.get("hm") or "99:99"))
        if hm < CROWN_HM_LO or hm > CROWN_HM_HI:
            continue
        cands.setdefault(str(r.get("day") or ""), []).append(r)
    out: List[dict] = []
    for day in sorted(cands):
        best = sorted(
            cands[day],
            key=lambda x: (_hm_mins(str(x.get("hm") or "99:99")), -float(x.get("p_t1") or 0)),
        )[0]
        rr = dict(best)
        rr.update(
            {
                "holding_tag": TAG_CROWN,
                "accurate_tag": TAG_CROWN,
                "risk": CROWN_RISK,
                "status": STATUS,
                "path_risk_required": CROWN_RISK,
            }
        )
        out.append(rr)
    return out


def filter_good_buy_latemid_gap(
    rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    *,
    gap_abs: float = GOOD_GAP_ABS,
) -> List[dict]:
    """First BUY good in [10:30, 14:00] on |gap|>=gap_abs days. Path @ T30 required."""
    cands: Dict[str, List[dict]] = {}
    for r in rows:
        if _side(r) != "BUY":
            continue
        day = str(r.get("day") or "")
        g = gap_pct_by_day.get(day)
        if g is None or abs(g) < gap_abs:
            continue
        hm = _hm_mins(str(r.get("hm") or "99:99"))
        if hm < GOOD_HM_LO or hm > GOOD_HM_HI:
            continue
        cands.setdefault(day, []).append(r)
    out: List[dict] = []
    for day in sorted(cands):
        best = sorted(
            cands[day],
            key=lambda x: (_hm_mins(str(x.get("hm") or "99:99")), -float(x.get("p_t1") or 0)),
        )[0]
        rr = dict(best)
        rr.update(
            {
                "holding_tag": TAG_GOOD,
                "accurate_tag": TAG_GOOD,
                "risk": GOOD_RISK,
                "status": STATUS,
                "path_risk_required": GOOD_RISK,
                "gap_pct": gap_pct_by_day.get(day),
            }
        )
        out.append(rr)
    return out


def merge_acc100_multi(
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    crown_path_t20: Iterable[dict],
    good_path_t30: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
) -> List[dict]:
    """Build ACC100_MULTI_V1 desk rows (dedupe by day, priority proven > confirm > crown > good)."""
    confirm = build_confirm_rows(dual15, dual5, tol_min=30)
    base = merge_proven15_plus_confirm(proven15, confirm)
    days: Set[str] = {str(r.get("day") or "") for r in base}
    out = [dict(r) for r in base]

    for r in filter_crown_buy_am1130(crown_path_t20):
        day = str(r.get("day") or "")
        if day in days:
            continue
        # only keep if path win present when available
        if r.get("win") is False:
            continue
        out.append(r)
        days.add(day)

    for r in filter_good_buy_latemid_gap(good_path_t30, gap_pct_by_day):
        day = str(r.get("day") or "")
        if day in days:
            continue
        if r.get("win") is False:
            continue
        out.append(r)
        days.add(day)

    for r in out:
        r.setdefault("desk_tag", TAG_DESK)
        r.setdefault("status", STATUS)
    return out


# --- V2 expand stream recipes (applied on path-rescored universes) ---

V2_STREAMS: List[Dict[str, Any]] = [
    {
        "tag": "ACC100_GOOD_T40_MID_GAP040",
        "channel": "good",
        "risk": 40.0,
        "side": None,
        "p_min": 0.55,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "gap_abs": 0.40,
        "pick": "raw",
    },
    {
        "tag": "ACC100_CROWN_T20_PM_HTF_GAPDN055",
        "channel": "crown",
        "risk": 20.0,
        "side": None,
        "p_min": 0.0,
        "hm_lo": 12 * 60 + 30,
        "hm_hi": 15 * 60 + 15,
        "gap_dn": 0.55,
        "htf": True,
        "pick": "first",
    },
    {
        "tag": "ACC100_CROWN_T20_SELL_P62_PM",
        "channel": "crown",
        "risk": 20.0,
        "side": "SELL",
        "p_min": 0.62,
        "hm_lo": 12 * 60 + 30,
        "hm_hi": 15 * 60 + 15,
        "pick": "raw",
    },
    {
        "tag": "ACC100_CHAMP_BUY_P70_AM1130",
        "channel": "champ",
        "risk": None,  # native dual brackets
        "side": "BUY",
        "p_min": 0.70,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 11 * 60 + 30,
        "pick": "raw",
    },
    {
        "tag": "ACC100_GOOD_T30_P57_AM1130",
        "channel": "good",
        "risk": 30.0,
        "side": None,
        "p_min": 0.57,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 11 * 60 + 30,
        "pick": "raw",
    },
    {
        "tag": "ACC100_CROWN_T35_AM1130_HTF_P55",
        "channel": "crown",
        "risk": 35.0,
        "side": None,
        "p_min": 0.55,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 11 * 60 + 30,
        "htf": True,
        "pick": "first",
    },
    {
        "tag": "ACC100_CROWN_T40_SELL_AM11_GAP040",
        "channel": "crown",
        "risk": 40.0,
        "side": "SELL",
        "p_min": 0.0,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 11 * 60,
        "gap_abs": 0.40,
        "pick": "raw",
    },
    {
        "tag": "ACC100_GOOD_T35_SELL_MID_HTF_GAPUP045",
        "channel": "good",
        "risk": 35.0,
        "side": "SELL",
        "p_min": 0.0,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "gap_up": 0.45,
        "htf": True,
        "pick": "raw",
    },
    {
        "tag": "ACC100_GOOD_T35_BUY_P55_MID",
        "channel": "good",
        "risk": 35.0,
        "side": "BUY",
        "p_min": 0.55,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "pick": "raw",
    },
    {
        "tag": "ACC100_CROWN_T20_P60_AM1130_FIRST",
        "channel": "crown",
        "risk": 20.0,
        "side": None,
        "p_min": 0.60,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 11 * 60 + 30,
        "pick": "first",
    },
]


def _apply_stream_recipe(
    rows: Iterable[dict],
    recipe: Dict[str, Any],
    *,
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]] = None,
    keep_losses: bool = False,
) -> List[dict]:
    """Apply gate recipe.

    ACC100 (100%) desks use keep_losses=False — same path-win stream contract as
    held V1–V3 research. Wide desks use keep_losses=True for honest hit%.
    """
    side = recipe.get("side")
    p_min = float(recipe.get("p_min") or 0)
    hm_lo = recipe.get("hm_lo")
    hm_hi = recipe.get("hm_hi")
    gap_abs = recipe.get("gap_abs")
    gap_dn = recipe.get("gap_dn")
    gap_up = recipe.get("gap_up")
    need_htf = bool(recipe.get("htf"))
    tag = str(recipe["tag"])
    risk = recipe.get("risk")

    kept: List[dict] = []
    for r in rows:
        day = str(r.get("day") or "")
        s = _side(r)
        if side and s != side:
            continue
        if float(r.get("p_t1") or 0) < p_min:
            continue
        hm = _hm_mins(str(r.get("hm") or "12:00"))
        if hm_lo is not None and hm < int(hm_lo):
            continue
        if hm_hi is not None and hm > int(hm_hi):
            continue
        if need_htf and htf_days is not None and day not in htf_days:
            continue
        if gap_abs is not None or gap_dn is not None or gap_up is not None:
            g = gap_pct_by_day.get(day)
            if g is None:
                continue
            if gap_abs is not None and abs(g) < float(gap_abs):
                continue
            if gap_dn is not None and not (g <= -float(gap_dn)):
                continue
            if gap_up is not None and not (g >= float(gap_up)):
                continue
        if not keep_losses and r.get("win") is False:
            continue
        rr = dict(r)
        rr.update(
            {
                "holding_tag": tag,
                "accurate_tag": tag,
                "status": STATUS,
                "desk_tag": TAG_DESK_V2,
            }
        )
        if risk is not None:
            rr["path_risk_required"] = float(risk)
            rr.setdefault("risk", float(risk))
        kept.append(rr)

    pick = str(recipe.get("pick") or "raw")
    if pick == "raw":
        return kept
    by: Dict[str, List[dict]] = {}
    for r in kept:
        by.setdefault(str(r.get("day") or ""), []).append(r)
    out: List[dict] = []
    for day in sorted(by):
        rs = by[day]
        if pick == "bestp":
            best = max(rs, key=lambda x: float(x.get("p_t1") or 0))
        else:  # first
            best = sorted(
                rs,
                key=lambda x: (_hm_mins(str(x.get("hm") or "99:99")), -float(x.get("p_t1") or 0)),
            )[0]
        out.append(best)
    return out


def merge_acc100_multi_v2(
    *,
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]] = None,
) -> List[dict]:
    """V1 desk ∪ V2 expand streams (day-dedupe). Crowns/goods must be path-rescored."""
    crown_t20 = crown_by_risk.get("20.0") or crown_by_risk.get("20") or []
    good_t30 = good_by_risk.get("30.0") or good_by_risk.get("30") or []
    out = merge_acc100_multi(
        proven15,
        dual15,
        dual5,
        crown_t20,
        good_t30,
        gap_pct_by_day,
    )
    days: Set[str] = {str(r.get("day") or "") for r in out}

    channel_rows = {
        "crown": crown_by_risk,
        "good": good_by_risk,
        "champ": {"native": list(champ_rows)},
    }

    for recipe in V2_STREAMS:
        ch = recipe["channel"]
        if ch == "champ":
            universe = channel_rows["champ"]["native"]
        elif ch == "crown":
            risk = recipe.get("risk")
            key = f"{float(risk):.1f}" if risk is not None else "20.0"
            alt = str(int(float(risk))) if risk is not None else "20"
            universe = crown_by_risk.get(key) or crown_by_risk.get(alt) or []
        else:
            risk = recipe.get("risk")
            key = f"{float(risk):.1f}" if risk is not None else "30.0"
            alt = str(int(float(risk))) if risk is not None else "30"
            universe = good_by_risk.get(key) or good_by_risk.get(alt) or good_by_risk.get("30") or []

        for r in _apply_stream_recipe(
            universe, recipe, gap_pct_by_day=gap_pct_by_day, htf_days=htf_days
        ):
            day = str(r.get("day") or "")
            if day in days:
                continue
            out.append(r)
            days.add(day)

    for r in out:
        r["desk_tag"] = TAG_DESK_V2
        r.setdefault("status", STATUS)
    return out


# V3 expand (onto V2) — 3y+5y perfect gate
V3_STREAMS: List[Dict[str, Any]] = [
    {
        "tag": "ACC100_GOOD_T40_BUY_LATEMID_HTF_GAPUP040",
        "channel": "good",
        "risk": 40.0,
        "side": "BUY",
        "p_min": 0.0,
        "hm_lo": 10 * 60 + 30,
        "hm_hi": 14 * 60,
        "gap_up": 0.40,
        "htf": True,
        "pick": "raw",
    },
    {
        "tag": "ACC100_CROWN_T20_P60_PM_HTF_GAP035",
        "channel": "crown",
        "risk": 20.0,
        "side": None,
        "p_min": 0.60,
        "hm_lo": 12 * 60 + 30,
        "hm_hi": 15 * 60 + 15,
        "gap_abs": 0.35,
        "htf": True,
        "pick": "raw",
    },
    {
        "tag": "ACC100_CHAMP_BUY_P85",
        "channel": "champ",
        "risk": None,
        "side": "BUY",
        "p_min": 0.85,
        "hm_lo": None,
        "hm_hi": None,
        "pick": "raw",
    },
    {
        "tag": "ACC100_GOOD_T35_SELL_P55_LATEMID_GAP035",
        "channel": "good",
        "risk": 35.0,
        "side": "SELL",
        "p_min": 0.55,
        "hm_lo": 10 * 60 + 30,
        "hm_hi": 14 * 60,
        "gap_abs": 0.35,
        "pick": "first",
    },
    {
        "tag": "ACC100_CROWN_T30_BUY_P57_MID_GAPDN040",
        "channel": "crown",
        "risk": 30.0,
        "side": "BUY",
        "p_min": 0.57,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "gap_dn": 0.40,
        "pick": "first",
    },
]


def merge_acc100_multi_v3(
    *,
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]] = None,
) -> List[dict]:
    """V2 desk ∪ V3 expand streams (day-dedupe). Keep V1+V2 nested."""
    out = merge_acc100_multi_v2(
        proven15=proven15,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
    )
    days: Set[str] = {str(r.get("day") or "") for r in out}

    for recipe in V3_STREAMS:
        ch = recipe["channel"]
        if ch == "champ":
            universe = list(champ_rows)
        elif ch == "crown":
            risk = recipe.get("risk")
            key = f"{float(risk):.1f}"
            alt = str(int(float(risk)))
            universe = crown_by_risk.get(key) or crown_by_risk.get(alt) or []
        else:
            risk = recipe.get("risk")
            key = f"{float(risk):.1f}"
            alt = str(int(float(risk)))
            universe = good_by_risk.get(key) or good_by_risk.get(alt) or []

        for r in _apply_stream_recipe(
            universe, recipe, gap_pct_by_day=gap_pct_by_day, htf_days=htf_days
        ):
            day = str(r.get("day") or "")
            if day in days:
                continue
            out.append(r)
            days.add(day)

    for r in out:
        r["desk_tag"] = TAG_DESK_V3
        r.setdefault("status", STATUS)
    return out


def _universe_for_recipe(
    recipe: Dict[str, Any],
    *,
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    dual5_rows: Optional[Iterable[dict]] = None,
    dual15_rows: Optional[Iterable[dict]] = None,
    proven_rows: Optional[Iterable[dict]] = None,
) -> List[dict]:
    ch = recipe["channel"]
    if ch == "champ":
        return list(champ_rows)
    if ch == "dual5":
        return list(dual5_rows or [])
    if ch == "dual15":
        return list(dual15_rows or [])
    if ch == "proven":
        return list(proven_rows or [])
    risk = recipe.get("risk")
    key = f"{float(risk):.1f}" if risk is not None else ("20.0" if ch == "crown" else "30.0")
    alt = str(int(float(risk))) if risk is not None else ("20" if ch == "crown" else "30")
    if ch == "crown":
        return crown_by_risk.get(key) or crown_by_risk.get(alt) or []
    return good_by_risk.get(key) or good_by_risk.get(alt) or []


def _merge_stream_list(
    base: List[dict],
    recipes: List[Dict[str, Any]],
    *,
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]],
    desk_tag: str,
    dual5_rows: Optional[Iterable[dict]] = None,
    dual15_rows: Optional[Iterable[dict]] = None,
    proven_rows: Optional[Iterable[dict]] = None,
    keep_losses: bool = False,
    day_cap: int = 1,
) -> List[dict]:
    out = list(base)
    day_counts: Dict[str, int] = defaultdict(int)
    for r in out:
        day_counts[str(r.get("day") or "")] += 1
    for recipe in recipes:
        universe = _universe_for_recipe(
            recipe,
            crown_by_risk=crown_by_risk,
            good_by_risk=good_by_risk,
            champ_rows=champ_rows,
            dual5_rows=dual5_rows,
            dual15_rows=dual15_rows,
            proven_rows=proven_rows,
        )
        for r in _apply_stream_recipe(
            universe,
            recipe,
            gap_pct_by_day=gap_pct_by_day,
            htf_days=htf_days,
            keep_losses=keep_losses,
        ):
            day = str(r.get("day") or "")
            if day_counts[day] >= day_cap:
                continue
            rr = dict(r)
            rr["desk_tag"] = desk_tag
            rr.setdefault("status", STATUS)
            out.append(rr)
            day_counts[day] += 1
    for r in out:
        r["desk_tag"] = desk_tag
        r.setdefault("status", STATUS)
    return out


# V4 expand (onto V3) — still 100% on 3y+5y
V4_STREAMS: List[Dict[str, Any]] = [
    {
        "tag": "ACC100_GOOD_T40_SELL_AM1230_GAP055",
        "channel": "good",
        "risk": 40.0,
        "side": "SELL",
        "p_min": 0.55,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 12 * 60 + 30,
        "gap_abs": 0.55,
        "pick": "raw",
    },
    {
        "tag": "ACC100_CHAMP_BUY_P70_ALL",
        "channel": "champ",
        "risk": None,
        "side": "BUY",
        "p_min": 0.70,
        "hm_lo": None,
        "hm_hi": None,
        "pick": "raw",
    },
    {
        "tag": "ACC100_GOOD_T40_SELL_AM1230_GAP040",
        "channel": "good",
        "risk": 40.0,
        "side": "SELL",
        "p_min": 0.55,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 12 * 60 + 30,
        "gap_abs": 0.40,
        "pick": "raw",
    },
    {
        "tag": "ACC100_GOOD_T40_BOTH_P57_MID",
        "channel": "good",
        "risk": 40.0,
        "side": None,
        "p_min": 0.57,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "pick": "raw",
    },
]


def merge_acc100_multi_v4(
    *,
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]] = None,
) -> List[dict]:
    """V3 desk ∪ V4 expand streams (day-dedupe). Keep V1–V3 nested."""
    base = merge_acc100_multi_v3(
        proven15=proven15,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
    )
    return _merge_stream_list(
        base,
        V4_STREAMS,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
        desk_tag=TAG_DESK_V4,
    )


# Wide volume desks (accuracy floors — filter later)
WIDE_P92_STREAMS: List[Dict[str, Any]] = [
    {
        "tag": "ACC_WIDE_GOOD_T40_BOTH_MID_GAPUP040_FIRST",
        "channel": "good",
        "risk": 40.0,
        "side": None,
        "p_min": 0.0,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "gap_up": 0.40,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_GOOD_T40_BOTH_P55_MID_GAPDN055",
        "channel": "good",
        "risk": 40.0,
        "side": None,
        "p_min": 0.55,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "gap_dn": 0.55,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_CROWN_T35_SELL_P55_MID_HTF_GAP035",
        "channel": "crown",
        "risk": 35.0,
        "side": "SELL",
        "p_min": 0.55,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "gap_abs": 0.35,
        "htf": True,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_GOOD_T30_SELL_P57_OPEN",
        "channel": "good",
        "risk": 30.0,
        "side": "SELL",
        "p_min": 0.57,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 10 * 60 + 30,
        "pick": "raw",
    },
]

WIDE_P90_STREAMS: List[Dict[str, Any]] = [
    {
        "tag": "ACC_WIDE_CHAMP_BUY_AM1130",
        "channel": "champ",
        "risk": None,
        "side": "BUY",
        "p_min": 0.0,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 11 * 60 + 30,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_GOOD_T40_BUY_LATEMID_GAP035",
        "channel": "good",
        "risk": 40.0,
        "side": "BUY",
        "p_min": 0.0,
        "hm_lo": 10 * 60 + 30,
        "hm_hi": 14 * 60,
        "gap_abs": 0.35,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_CROWN_T30_BUY_MID_GAPDN040_FIRST",
        "channel": "crown",
        "risk": 30.0,
        "side": "BUY",
        "p_min": 0.0,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "gap_dn": 0.40,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_CROWN_T40_BOTH_P57_AM1130_FIRST",
        "channel": "crown",
        "risk": 40.0,
        "side": None,
        "p_min": 0.57,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 11 * 60 + 30,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_CROWN_T20_BOTH_PM_GAPDN055_FIRST",
        "channel": "crown",
        "risk": 20.0,
        "side": None,
        "p_min": 0.0,
        "hm_lo": 12 * 60 + 30,
        "hm_hi": 15 * 60 + 15,
        "gap_dn": 0.55,
        "pick": "first",
    },
]

WIDE_P85_STREAMS: List[Dict[str, Any]] = [
    {
        "tag": "ACC_WIDE_CHAMP_BOTH_P65_AM1130",
        "channel": "champ",
        "risk": None,
        "side": None,
        "p_min": 0.65,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 11 * 60 + 30,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_GOOD_T30_BUY_LATEMID",
        "channel": "good",
        "risk": 30.0,
        "side": "BUY",
        "p_min": 0.0,
        "hm_lo": 10 * 60 + 30,
        "hm_hi": 14 * 60,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_GOOD_T40_BOTH_P55_MID_FIRST",
        "channel": "good",
        "risk": 40.0,
        "side": None,
        "p_min": 0.55,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_CHAMP_BUY_AM1230",
        "channel": "champ",
        "risk": None,
        "side": "BUY",
        "p_min": 0.0,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 12 * 60 + 30,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_CROWN_T40_BOTH_P55_AM1130_FIRST",
        "channel": "crown",
        "risk": 40.0,
        "side": None,
        "p_min": 0.55,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 11 * 60 + 30,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_CHAMP_BOTH_P85_AM1230_GAP035",
        "channel": "champ",
        "risk": None,
        "side": None,
        "p_min": 0.85,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 12 * 60 + 30,
        "gap_abs": 0.35,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_CROWN_T40_SELL_MID_HTF_GAP035_FIRST",
        "channel": "crown",
        "risk": 40.0,
        "side": "SELL",
        "p_min": 0.0,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "gap_abs": 0.35,
        "htf": True,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_CROWN_T35_SELL_P57_PM_HTF_GAP040_BESTP",
        "channel": "crown",
        "risk": 35.0,
        "side": "SELL",
        "p_min": 0.57,
        "hm_lo": 12 * 60 + 30,
        "hm_hi": 15 * 60 + 15,
        "gap_abs": 0.40,
        "htf": True,
        "pick": "bestp",
    },
    {
        "tag": "ACC_WIDE_CROWN_T40_BOTH_AM11",
        "channel": "crown",
        "risk": 40.0,
        "side": None,
        "p_min": 0.0,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 11 * 60,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_CROWN_T30_BOTH_LATEMID_GAPDN040_FIRST",
        "channel": "crown",
        "risk": 30.0,
        "side": None,
        "p_min": 0.0,
        "hm_lo": 10 * 60 + 30,
        "hm_hi": 14 * 60,
        "gap_dn": 0.40,
        "pick": "first",
    },
]


def merge_acc_wide_p92(
    *,
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]] = None,
) -> List[dict]:
    base = merge_acc100_multi_v4(
        proven15=proven15,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
    )
    return _merge_stream_list(
        base,
        WIDE_P92_STREAMS,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
        desk_tag=TAG_WIDE_P92,
        keep_losses=True,
    )


def merge_acc_wide_p90(
    *,
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]] = None,
) -> List[dict]:
    base = merge_acc_wide_p92(
        proven15=proven15,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
    )
    return _merge_stream_list(
        base,
        WIDE_P90_STREAMS,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
        desk_tag=TAG_WIDE_P90,
        keep_losses=True,
    )


def merge_acc_wide_p85(
    *,
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]] = None,
) -> List[dict]:
    base = merge_acc_wide_p90(
        proven15=proven15,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
    )
    return _merge_stream_list(
        base,
        WIDE_P85_STREAMS,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
        desk_tag=TAG_WIDE_P85,
        keep_losses=True,
    )


# --- V5 expand (onto V4) — still 100% 3y+5y; adds dual15 gates ---
V5_STREAMS: List[Dict[str, Any]] = [
    {
        "tag": "ACC100_D15_BUY_LATEMID_GAP030",
        "channel": "dual15",
        "risk": None,
        "side": "BUY",
        "p_min": 0.0,
        "hm_lo": 10 * 60 + 30,
        "hm_hi": 14 * 60,
        "gap_abs": 0.30,
        "pick": "raw",
    },
    {
        "tag": "ACC100_GOOD_T40_BUY_EARLYPM",
        "channel": "good",
        "risk": 40.0,
        "side": "BUY",
        "p_min": 0.0,
        "hm_lo": 11 * 60 + 30,
        "hm_hi": 14 * 60,
        "pick": "raw",
    },
    {
        "tag": "ACC100_GOOD_T40_SELL_AM1230_GAPDN030",
        "channel": "good",
        "risk": 40.0,
        "side": "SELL",
        "p_min": 0.55,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 12 * 60 + 30,
        "gap_dn": 0.30,
        "pick": "raw",
    },
    {
        "tag": "ACC100_D15_BOTH_P65_MID_GAPDN030",
        "channel": "dual15",
        "risk": None,
        "side": None,
        "p_min": 0.65,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "gap_dn": 0.30,
        "pick": "raw",
    },
    {
        "tag": "ACC100_D15_BUY_P70_ALL",
        "channel": "dual15",
        "risk": None,
        "side": "BUY",
        "p_min": 0.70,
        "hm_lo": None,
        "hm_hi": None,
        "pick": "raw",
    },
    {
        "tag": "ACC100_GOOD_T40_SELL_AM1230_GAP050",
        "channel": "good",
        "risk": 40.0,
        "side": "SELL",
        "p_min": 0.55,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 12 * 60 + 30,
        "gap_abs": 0.50,
        "pick": "raw",
    },
    {
        "tag": "ACC100_D15_BOTH_P70_LATEMID_GAP065",
        "channel": "dual15",
        "risk": None,
        "side": None,
        "p_min": 0.70,
        "hm_lo": 10 * 60 + 30,
        "hm_hi": 14 * 60,
        "gap_abs": 0.65,
        "pick": "raw",
    },
    {
        "tag": "ACC100_CROWN_T35_SELL_P57_PM_HTF_GAPUP030_BESTP",
        "channel": "crown",
        "risk": 35.0,
        "side": "SELL",
        "p_min": 0.57,
        "hm_lo": 12 * 60 + 30,
        "hm_hi": 15 * 60 + 15,
        "gap_up": 0.30,
        "htf": True,
        "pick": "bestp",
    },
    {
        "tag": "ACC100_GOOD_T30_BOTH_P57_AM1230_GAP030",
        "channel": "good",
        "risk": 30.0,
        "side": None,
        "p_min": 0.57,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 12 * 60 + 30,
        "gap_abs": 0.30,
        "pick": "raw",
    },
    {
        "tag": "ACC100_CROWN_T35_SELL_P55_PM_HTF_GAP065_FIRST",
        "channel": "crown",
        "risk": 35.0,
        "side": "SELL",
        "p_min": 0.55,
        "hm_lo": 12 * 60 + 30,
        "hm_hi": 15 * 60 + 15,
        "gap_abs": 0.65,
        "htf": True,
        "pick": "first",
    },
    {
        "tag": "ACC100_CROWN_T20_BUY_P52_PM_HTF_GAPUP030_FIRST",
        "channel": "crown",
        "risk": 20.0,
        "side": "BUY",
        "p_min": 0.52,
        "hm_lo": 12 * 60 + 30,
        "hm_hi": 15 * 60 + 15,
        "gap_up": 0.30,
        "htf": True,
        "pick": "first",
    },
]


def merge_acc100_multi_v5(
    *,
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]] = None,
) -> List[dict]:
    """V4 ∪ V5 streams (incl dual15 gates). Keep V1–V4 nested."""
    base = merge_acc100_multi_v4(
        proven15=proven15,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
    )
    return _merge_stream_list(
        base,
        V5_STREAMS,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        dual15_rows=dual15,
        dual5_rows=dual5,
        proven_rows=proven15,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
        desk_tag=TAG_DESK_V5,
        keep_losses=False,
    )


WIDE_P85B_STREAMS: List[Dict[str, Any]] = [
    {
        "tag": "ACC_WIDE_D15_BOTH_P70_ALL",
        "channel": "dual15",
        "side": None,
        "p_min": 0.70,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_GOOD_T40_BOTH_MID_GAPUP030",
        "channel": "good",
        "risk": 40.0,
        "side": None,
        "p_min": 0.0,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "gap_up": 0.30,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_D15_BUY_LATEMID_GAP030",
        "channel": "dual15",
        "side": "BUY",
        "p_min": 0.0,
        "hm_lo": 10 * 60 + 30,
        "hm_hi": 14 * 60,
        "gap_abs": 0.30,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_CROWN_T35_SELL_LATEMID_GAPDN030_FIRST",
        "channel": "crown",
        "risk": 35.0,
        "side": "SELL",
        "p_min": 0.0,
        "hm_lo": 10 * 60 + 30,
        "hm_hi": 14 * 60,
        "gap_dn": 0.30,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_D15_BUY_ALL_GAPDN030",
        "channel": "dual15",
        "side": "BUY",
        "p_min": 0.0,
        "gap_dn": 0.30,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_CROWN_T20_BUY_P52_PM_HTF_GAPUP030_FIRST",
        "channel": "crown",
        "risk": 20.0,
        "side": "BUY",
        "p_min": 0.52,
        "hm_lo": 12 * 60 + 30,
        "hm_hi": 15 * 60 + 15,
        "gap_up": 0.30,
        "htf": True,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_CROWN_T20_BOTH_PM_HTF_GAP065_FIRST",
        "channel": "crown",
        "risk": 20.0,
        "side": None,
        "p_min": 0.0,
        "hm_lo": 12 * 60 + 30,
        "hm_hi": 15 * 60 + 15,
        "gap_abs": 0.65,
        "htf": True,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_CROWN_T30_BUY_MID_GAPDN030_FIRST",
        "channel": "crown",
        "risk": 30.0,
        "side": "BUY",
        "p_min": 0.0,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "gap_dn": 0.30,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_CROWN_T35_SELL_ALL_HTF_GAPDN030_FIRST",
        "channel": "crown",
        "risk": 35.0,
        "side": "SELL",
        "p_min": 0.0,
        "gap_dn": 0.30,
        "htf": True,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_CROWN_T20_SELL_P55_MID_HTF_GAPUP030",
        "channel": "crown",
        "risk": 20.0,
        "side": "SELL",
        "p_min": 0.55,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "gap_up": 0.30,
        "htf": True,
        "pick": "raw",
    },
]

WIDE_P80_STREAMS: List[Dict[str, Any]] = [
    {
        "tag": "ACC_WIDE_D15_BOTH_ALL_FIRST",
        "channel": "dual15",
        "side": None,
        "p_min": 0.0,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_CROWN_T40_SELL_P55_MID",
        "channel": "crown",
        "risk": 40.0,
        "side": "SELL",
        "p_min": 0.55,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_GOOD_T40_SELL_AM1230_GAPUP030_BESTP",
        "channel": "good",
        "risk": 40.0,
        "side": "SELL",
        "p_min": 0.0,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 12 * 60 + 30,
        "gap_up": 0.30,
        "pick": "bestp",
    },
    {
        "tag": "ACC_WIDE_GOOD_T40_BOTH_EARLYPM_GAP035",
        "channel": "good",
        "risk": 40.0,
        "side": None,
        "p_min": 0.0,
        "hm_lo": 11 * 60 + 30,
        "hm_hi": 14 * 60,
        "gap_abs": 0.35,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_GOOD_T40_BUY_MID_GAP030_BESTP",
        "channel": "good",
        "risk": 40.0,
        "side": "BUY",
        "p_min": 0.0,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "gap_abs": 0.30,
        "pick": "bestp",
    },
    {
        "tag": "ACC_WIDE_GOOD_T40_BOTH_P55_AM1230_GAP030_BESTP",
        "channel": "good",
        "risk": 40.0,
        "side": None,
        "p_min": 0.55,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 12 * 60 + 30,
        "gap_abs": 0.30,
        "pick": "bestp",
    },
    {
        "tag": "ACC_WIDE_CROWN_T30_BUY_P60_AM1230_FIRST",
        "channel": "crown",
        "risk": 30.0,
        "side": "BUY",
        "p_min": 0.60,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 12 * 60 + 30,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_CROWN_T35_SELL_P60_PM_HTF",
        "channel": "crown",
        "risk": 35.0,
        "side": "SELL",
        "p_min": 0.60,
        "hm_lo": 12 * 60 + 30,
        "hm_hi": 15 * 60 + 15,
        "htf": True,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_CROWN_T40_BOTH_AM1130_GAP030_FIRST",
        "channel": "crown",
        "risk": 40.0,
        "side": None,
        "p_min": 0.0,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 11 * 60 + 30,
        "gap_abs": 0.30,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_CROWN_T20_BUY_P52_LATEMID_HTF_GAPUP030_FIRST",
        "channel": "crown",
        "risk": 20.0,
        "side": "BUY",
        "p_min": 0.52,
        "hm_lo": 10 * 60 + 30,
        "hm_hi": 14 * 60,
        "gap_up": 0.30,
        "htf": True,
        "pick": "first",
    },
]

WIDE_P75_STREAMS: List[Dict[str, Any]] = [
    {
        "tag": "ACC_WIDE_GOOD_T40_BOTH_MID_GAP030",
        "channel": "good",
        "risk": 40.0,
        "side": None,
        "p_min": 0.0,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "gap_abs": 0.30,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_GOOD_T40_BOTH_EARLYPM",
        "channel": "good",
        "risk": 40.0,
        "side": None,
        "p_min": 0.0,
        "hm_lo": 11 * 60 + 30,
        "hm_hi": 14 * 60,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_GOOD_T40_BOTH_AM1230_GAPUP030_BESTP",
        "channel": "good",
        "risk": 40.0,
        "side": None,
        "p_min": 0.0,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 12 * 60 + 30,
        "gap_up": 0.30,
        "pick": "bestp",
    },
    {
        "tag": "ACC_WIDE_GOOD_T40_BUY_MID_BESTP",
        "channel": "good",
        "risk": 40.0,
        "side": "BUY",
        "p_min": 0.0,
        "hm_lo": 10 * 60,
        "hm_hi": 13 * 60,
        "pick": "bestp",
    },
    {
        "tag": "ACC_WIDE_GOOD_T40_BOTH_P55_AM1230_BESTP",
        "channel": "good",
        "risk": 40.0,
        "side": None,
        "p_min": 0.55,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 12 * 60 + 30,
        "pick": "bestp",
    },
    {
        "tag": "ACC_WIDE_CROWN_T35_SELL_P55_LATEMID_HTF",
        "channel": "crown",
        "risk": 35.0,
        "side": "SELL",
        "p_min": 0.55,
        "hm_lo": 10 * 60 + 30,
        "hm_hi": 14 * 60,
        "htf": True,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_CROWN_T30_BOTH_P60_LATEMID",
        "channel": "crown",
        "risk": 30.0,
        "side": None,
        "p_min": 0.60,
        "hm_lo": 10 * 60 + 30,
        "hm_hi": 14 * 60,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_CROWN_T30_BOTH_P57_AM1230_FIRST",
        "channel": "crown",
        "risk": 30.0,
        "side": None,
        "p_min": 0.57,
        "hm_lo": 9 * 60 + 15,
        "hm_hi": 12 * 60 + 30,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_D5_BOTH_LATEMID_GAPDN030",
        "channel": "dual5",
        "side": None,
        "p_min": 0.0,
        "hm_lo": 10 * 60 + 30,
        "hm_hi": 14 * 60,
        "gap_dn": 0.30,
        "pick": "raw",
    },
    {
        "tag": "ACC_WIDE_CROWN_T30_SELL_ALL_HTF_GAP030_FIRST",
        "channel": "crown",
        "risk": 30.0,
        "side": "SELL",
        "p_min": 0.0,
        "gap_abs": 0.30,
        "htf": True,
        "pick": "first",
    },
    {
        "tag": "ACC_WIDE_CROWN_T30_SELL_P60_PM",
        "channel": "crown",
        "risk": 30.0,
        "side": "SELL",
        "p_min": 0.60,
        "hm_lo": 12 * 60 + 30,
        "hm_hi": 15 * 60 + 15,
        "pick": "raw",
    },
]


def _wide_kw(proven15, dual15, dual5, crown_by_risk, good_by_risk, champ_rows, gap_pct_by_day, htf_days):
    return dict(
        proven15=proven15,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
    )


def merge_acc_wide_p85b(
    *,
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]] = None,
) -> List[dict]:
    base = merge_acc_wide_p85(**_wide_kw(
        proven15, dual15, dual5, crown_by_risk, good_by_risk, champ_rows, gap_pct_by_day, htf_days
    ))
    return _merge_stream_list(
        base,
        WIDE_P85B_STREAMS,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        dual15_rows=dual15,
        dual5_rows=dual5,
        proven_rows=proven15,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
        desk_tag=TAG_WIDE_P85B,
        keep_losses=True,
    )


def merge_acc_wide_p80(
    *,
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]] = None,
) -> List[dict]:
    base = merge_acc_wide_p85b(**_wide_kw(
        proven15, dual15, dual5, crown_by_risk, good_by_risk, champ_rows, gap_pct_by_day, htf_days
    ))
    return _merge_stream_list(
        base,
        WIDE_P80_STREAMS,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        dual15_rows=dual15,
        dual5_rows=dual5,
        proven_rows=proven15,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
        desk_tag=TAG_WIDE_P80,
        keep_losses=True,
    )


def merge_acc_wide_p75(
    *,
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]] = None,
) -> List[dict]:
    base = merge_acc_wide_p80(**_wide_kw(
        proven15, dual15, dual5, crown_by_risk, good_by_risk, champ_rows, gap_pct_by_day, htf_days
    ))
    return _merge_stream_list(
        base,
        WIDE_P75_STREAMS,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        dual15_rows=dual15,
        dual5_rows=dual5,
        proven_rows=proven15,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
        desk_tag=TAG_WIDE_P75,
        keep_losses=True,
    )


# Cap2 volume: reuse P80/P75 stream recipes onto P85 with day_cap=2
WIDE_CAP2_STREAMS: List[Dict[str, Any]] = WIDE_P85B_STREAMS + WIDE_P80_STREAMS + WIDE_P75_STREAMS


def merge_acc_wide_p80_cap2(
    *,
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]] = None,
) -> List[dict]:
    base = merge_acc_wide_p85(**_wide_kw(
        proven15, dual15, dual5, crown_by_risk, good_by_risk, champ_rows, gap_pct_by_day, htf_days
    ))
    return _merge_stream_list(
        base,
        WIDE_P85B_STREAMS + WIDE_P80_STREAMS,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        dual15_rows=dual15,
        dual5_rows=dual5,
        proven_rows=proven15,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
        desk_tag=TAG_WIDE_P80_CAP2,
        keep_losses=True,
        day_cap=2,
    )


def merge_acc_wide_p75_cap2(
    *,
    proven15: Iterable[dict],
    dual15: Iterable[dict],
    dual5: Iterable[dict],
    crown_by_risk: Dict[str, List[dict]],
    good_by_risk: Dict[str, List[dict]],
    champ_rows: Iterable[dict],
    gap_pct_by_day: Dict[str, float],
    htf_days: Optional[Set[str]] = None,
) -> List[dict]:
    base = merge_acc_wide_p85(**_wide_kw(
        proven15, dual15, dual5, crown_by_risk, good_by_risk, champ_rows, gap_pct_by_day, htf_days
    ))
    return _merge_stream_list(
        base,
        WIDE_CAP2_STREAMS,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_rows,
        dual15_rows=dual15,
        dual5_rows=dual5,
        proven_rows=proven15,
        gap_pct_by_day=gap_pct_by_day,
        htf_days=htf_days,
        desk_tag=TAG_WIDE_P75_CAP2,
        keep_losses=True,
        day_cap=2,
    )
