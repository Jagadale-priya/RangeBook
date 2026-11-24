"""Rebuild path-true rows from held stream tags (P2c…P2f)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from research_confirm_dual_tf_deep import _ix  # type: ignore
from research_100pct_deeper_more_calls import filt, time_agree  # type: ignore
from prod_live.holding_accurate.replay import (
    bestp_day,
    first_day,
    last_day,
    mid_day,
    second_day,
    weekday_filt,
)

_BAND: Dict[str, tuple] = {
    "first10": (9 * 60 + 15, 9 * 60 + 25),
    "first15": (9 * 60 + 15, 9 * 60 + 30),
    "first20": (9 * 60 + 15, 9 * 60 + 35),
    "first25": (9 * 60 + 15, 9 * 60 + 40),
    "first30": (9 * 60 + 15, 9 * 60 + 45),
    "first35": (9 * 60 + 15, 9 * 60 + 50),
    "first45": (9 * 60 + 15, 10 * 60),
    "first50": (9 * 60 + 15, 10 * 60 + 5),
    "open": (9 * 60 + 15, 10 * 60 + 30),
    "open2": (9 * 60 + 15, 10 * 60 + 15),
    "am10": (9 * 60 + 15, 10 * 60 + 45),
    "am1015": (9 * 60 + 15, 10 * 60 + 15),
    "am1030": (9 * 60 + 15, 10 * 60 + 30),
    "am11": (9 * 60 + 15, 11 * 60),
    "am1115": (9 * 60 + 15, 11 * 60 + 15),
    "am1120": (9 * 60 + 15, 11 * 60 + 20),
    "am1130": (9 * 60 + 15, 11 * 60 + 30),
    "am1145": (9 * 60 + 15, 11 * 60 + 45),
    "am12": (9 * 60 + 15, 12 * 60),
    "am1215": (9 * 60 + 15, 12 * 60 + 15),
    "am1230": (9 * 60 + 15, 12 * 60 + 30),
    "brunch": (10 * 60 + 15, 12 * 60),
    "brunch2": (10 * 60, 12 * 60 + 30),
    "brunch3": (10 * 60 + 30, 12 * 60 + 15),
    "lunch": (11 * 60 + 45, 13 * 60 + 15),
    "lunch2": (11 * 60 + 30, 13 * 60 + 30),
    "mid": (10 * 60, 13 * 60),
    "mid2": (10 * 60 + 15, 13 * 60 + 30),
    "mid3": (10 * 60 + 45, 13 * 60 + 15),
    "core": (10 * 60, 14 * 60),
    "latemid": (10 * 60 + 30, 14 * 60),
    "latemid2": (11 * 60, 14 * 60 + 15),
    "earlypm": (11 * 60 + 30, 14 * 60),
    "earlypm2": (12 * 60, 14 * 60 + 30),
    "pm": (12 * 60 + 30, 15 * 60 + 15),
    "pm2": (12 * 60, 15 * 60),
    "pm3": (12 * 60 + 15, 15 * 60 + 15),
    "last150": (12 * 60 + 45, 15 * 60 + 15),
    "last135": (13 * 60, 15 * 60 + 15),
    "last120": (13 * 60 + 15, 15 * 60 + 15),
    "last105": (13 * 60 + 30, 15 * 60 + 15),
    "last90": (13 * 60 + 45, 15 * 60 + 15),
    "last80": (13 * 60 + 55, 15 * 60 + 15),
    "last75": (14 * 60, 15 * 60 + 15),
    "last60": (14 * 60 + 15, 15 * 60 + 15),
    "last55": (14 * 60 + 20, 15 * 60 + 15),
    "last45": (14 * 60 + 30, 15 * 60 + 15),
    "last40": (14 * 60 + 35, 15 * 60 + 15),
    "m915": (9 * 60 + 15, 9 * 60 + 20),
    "m920": (9 * 60 + 20, 9 * 60 + 30),
    "m930": (9 * 60 + 30, 9 * 60 + 45),
    "m945": (9 * 60 + 45, 10 * 60),
    "m1000": (10 * 60, 10 * 60 + 20),
    "m1020": (10 * 60 + 20, 10 * 60 + 45),
    "m1045": (10 * 60 + 45, 11 * 60 + 15),
    "m1115": (11 * 60 + 15, 11 * 60 + 45),
    "m1145": (11 * 60 + 45, 12 * 60 + 30),
    "m1230": (12 * 60 + 30, 13 * 60 + 15),
    "m1315": (13 * 60 + 15, 14 * 60),
    "m1400": (14 * 60, 14 * 60 + 30),
    "m1430": (14 * 60 + 30, 15 * 60 + 15),
    "all": (None, None),
}

_GAP: Dict[str, tuple] = {}
for lab, a, d, u in [
    ("nogap", None, False, False),
    ("g010", 0.10, False, False), ("g012", 0.12, False, False), ("g013", 0.13, False, False),
    ("g015", 0.15, False, False), ("g016", 0.16, False, False), ("g017", 0.17, False, False),
    ("g018", 0.18, False, False), ("g019", 0.19, False, False), ("g020", 0.20, False, False),
    ("g021", 0.21, False, False), ("g022", 0.22, False, False), ("g023", 0.23, False, False),
    ("g024", 0.24, False, False), ("g025", 0.25, False, False), ("g027", 0.27, False, False),
    ("g028", 0.28, False, False), ("g029", 0.29, False, False), ("g030", 0.30, False, False),
    ("g032", 0.32, False, False), ("g033", 0.33, False, False), ("g034", 0.34, False, False),
    ("g035", 0.35, False, False), ("g036", 0.36, False, False), ("g038", 0.38, False, False),
    ("g040", 0.40, False, False), ("g041", 0.41, False, False), ("g042", 0.42, False, False),
    ("g045", 0.45, False, False), ("g047", 0.47, False, False), ("g048", 0.48, False, False),
    ("g050", 0.50, False, False), ("g052", 0.52, False, False), ("g053", 0.53, False, False),
    ("g055", 0.55, False, False), ("g058", 0.58, False, False), ("g060", 0.60, False, False),
    ("g062", 0.62, False, False), ("g065", 0.65, False, False), ("g068", 0.68, False, False),
    ("g070", 0.70, False, False), ("g075", 0.75, False, False), ("g080", 0.80, False, False),
    ("g085", 0.85, False, False), ("g090", 0.90, False, False), ("g100", 1.0, False, False),
    ("gdn010", 0.10, True, False), ("gdn012", 0.12, True, False), ("gdn013", 0.13, True, False),
    ("gdn015", 0.15, True, False), ("gdn017", 0.17, True, False), ("gdn018", 0.18, True, False),
    ("gdn020", 0.20, True, False), ("gdn022", 0.22, True, False), ("gdn023", 0.23, True, False),
    ("gdn025", 0.25, True, False), ("gdn028", 0.28, True, False), ("gdn030", 0.30, True, False),
    ("gdn034", 0.34, True, False), ("gdn035", 0.35, True, False), ("gdn040", 0.40, True, False),
    ("gdn045", 0.45, True, False), ("gdn050", 0.50, True, False), ("gdn055", 0.55, True, False),
    ("gdn060", 0.60, True, False),
    ("gup010", 0.10, False, True), ("gup012", 0.12, False, True), ("gup013", 0.13, False, True),
    ("gup015", 0.15, False, True), ("gup017", 0.17, False, True), ("gup018", 0.18, False, True),
    ("gup020", 0.20, False, True), ("gup022", 0.22, False, True), ("gup023", 0.23, False, True),
    ("gup025", 0.25, False, True), ("gup028", 0.28, False, True), ("gup030", 0.30, False, True),
    ("gup034", 0.34, False, True), ("gup035", 0.35, False, True), ("gup040", 0.40, False, True),
    ("gup045", 0.45, False, True), ("gup050", 0.50, False, True), ("gup055", 0.55, False, True),
    ("gup060", 0.60, False, True),
]:
    _GAP[lab] = (a, d, u)

_WD = {
    "wd_mtw": {0, 1, 2},
    "wd_wrf": {2, 3, 4},
    "wd_mf": {0, 4},
    "wd_tt": {1, 3},
    "wd_all": {0, 1, 2, 3, 4},
}


def universes(path_u, dual15, dual5, proven, champ) -> Dict[str, List[dict]]:
    u: Dict[str, List[dict]] = {}
    for rk, rows in (path_u.get("crown_by_risk") or {}).items():
        if not str(rk).startswith("_"):
            u[f"CR{str(rk).replace('.0', '')}"] = rows
    for rk, rows in (path_u.get("good_by_risk") or {}).items():
        if not str(rk).startswith("_") and rk != "native":
            u[f"GD{str(rk).replace('.0', '')}"] = rows
    u["CH"] = path_u.get("champ_native") or champ
    u["D5"] = dual5
    u["PR"] = proven
    u["D15"] = dual15
    return u


def rebuild_tag(
    tag: str,
    univ: Dict[str, List[dict]],
    gaps: Dict[str, float],
    active: Set[str],
    ix_map: Dict[str, Any],
) -> Optional[List[dict]]:
    raw = tag
    for pref in ("E_", "F_"):
        if raw.startswith(pref):
            raw = raw[len(pref) :]
            break

    if raw.startswith("CF3_T"):
        parts = raw.split("_")
        try:
            tol = int(parts[1][1:])
        except Exception:
            return None
        if len(parts) < 5:
            return None
        a, b, c = parts[2], parts[3], parts[4]
        if a not in ix_map or b not in ix_map or c not in ix_map:
            return None
        ab = time_agree(ix_map[a], ix_map[b], tol=tol, tag="cf")
        return time_agree(_ix(ab), ix_map[c], tol=tol, tag="cf3")

    if raw.startswith("CF_T"):
        parts = raw.split("_")
        try:
            tol = int(parts[1][1:])
        except Exception:
            return None
        rest = "_".join(parts[2:])
        legacy = {
            "any15_d5": ("d15", "d5"), "p15_d5": ("p15", "d5"), "any15_ch": ("d15", "ch"),
            "ch_d5": ("ch", "d5"), "p15_ch": ("p15", "ch"), "d5_p15": ("d5", "p15"),
            "d5_any15": ("d5", "d15"),
        }
        pair = legacy.get(rest)
        if pair is None and rest.startswith("any15_cr"):
            pair = ("d15", "cr" + rest[8:])
        elif pair is None and rest.startswith("d5_cr"):
            pair = ("d5", "cr" + rest[5:])
        elif pair is None and rest.startswith("ch_cr"):
            pair = ("ch", "cr" + rest[5:])
        elif pair is None and rest.startswith("p15_cr"):
            pair = ("p15", "cr" + rest[6:])
        elif pair is None:
            bits = rest.split("_")
            if len(bits) == 2:
                pair = (bits[0], bits[1])
        if not pair or pair[0] not in ix_map or pair[1] not in ix_map:
            return None
        return time_agree(ix_map[pair[0]], ix_map[pair[1]], tol=tol, tag="cf")

    parts = raw.split("_")
    if len(parts) < 6:
        return None
    uname, side_s, p_s = parts[0], parts[1], parts[2]
    if uname not in univ or not p_s.startswith("p"):
        return None
    try:
        digits = p_s[1:]
        pmin = int(digits) / (1000.0 if len(digits) >= 3 else 100.0)
    except Exception:
        return None
    side = None if side_s == "BOTH" else side_s
    variant = parts[-1]
    # F-style with weekday: ..._htf_gap_wd_xxx_variant
    wlab = None
    if len(parts) >= 7 and parts[-2].startswith("wd_"):
        wlab = parts[-2]
        glab = parts[-3]
        htf_s = parts[-4]
        blab = "_".join(parts[3:-4])
    else:
        glab = parts[-2]
        htf_s = parts[-3]
        blab = "_".join(parts[3:-3])
    if blab not in _BAND or glab not in _GAP:
        return None
    lo, hi = _BAND[blab]
    gabsm, gdn, gup = _GAP[glab]
    base = filt(
        univ[uname],
        p_min=pmin,
        side=side,
        hm_lo=lo,
        hm_hi=hi,
        htf=active if htf_s == "htf" else None,
        gaps=gaps if gabsm is not None or gdn or gup else None,
        gap_abs=gabsm,
        gap_dn=gdn,
        gap_up=gup,
    )
    if wlab and wlab in _WD and wlab != "wd_all":
        base = weekday_filt(base, _WD[wlab])
    if variant == "first":
        return first_day(base)
    if variant == "bestp":
        return bestp_day(base)
    if variant == "last":
        return last_day(base)
    if variant == "mid":
        return mid_day(base)
    if variant == "second":
        return second_day(base)
    return base


def rebuild_all_tags(
    tags: List[str],
    path_u,
    gaps,
    active,
    dual15,
    dual5,
    proven,
    champ,
) -> Dict[str, List[dict]]:
    univ = universes(path_u, dual15, dual5, proven, champ)
    ix_map = {
        "d15": _ix(dual15),
        "p15": _ix(proven),
        "d5": _ix(dual5),
        "ch": _ix(path_u.get("champ_native") or champ),
        "any15": _ix(dual15),
    }
    for rk, crow in (path_u.get("crown_by_risk") or {}).items():
        if not str(rk).startswith("_"):
            ix_map[f"cr{str(rk).replace('.0', '')}"] = _ix(crow)
    for rk, grow in (path_u.get("good_by_risk") or {}).items():
        if not str(rk).startswith("_") and rk != "native":
            ix_map[f"gd{str(rk).replace('.0', '')}"] = _ix(grow)
    out: Dict[str, List[dict]] = {}
    ok = fail = 0
    for tag in tags:
        if tag in out:
            continue
        rows = rebuild_tag(tag, univ, gaps, active, ix_map)
        if rows is None:
            fail += 1
            continue
        out[tag] = rows
        ok += 1
    print(f"  rebuilt tags ok={ok} fail={fail}", flush=True)
    return out
