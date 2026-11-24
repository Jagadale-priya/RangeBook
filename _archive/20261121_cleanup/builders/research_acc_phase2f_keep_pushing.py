"""Phase-2f: KEEP PUSHING — more calls @ same accuracy.

Seeds from salvaged Phase-2e (+ P2d). New axes: micro-bands, weekday, mid pick, triple-CF.
Day + priority cap2 only (faster finish). Phase-1 locked, Phase-2c held.

  python -u prod_live/tests/builders/research_acc_phase2f_keep_pushing.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
import path_setup  # noqa: F401,E402

import pandas as pd  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _hm_mins, _side, _ix  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    filt,
    first_day,
    bestp_day,
    gap_map,
    is_perfect,
    time_agree,
    union_unique_days,
)
from prod_live.logic.accurate_desks import (  # noqa: E402
    DESK_REGISTRY,
    RESEARCH_END,
    build_all_accurate_desks,
)
from prod_live.holding_accurate.phase2c.builders import union_day_cap2  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
HOLD = ROOT / "prod_live" / "holding_accurate"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL_10Y = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH_10Y = LEDGER / "_cache_path_trusted_10y.json"
P2E_RECIPES = HOLD / "phase2e" / "recipes_research.json"

END = RESEARCH_END
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_5Y = (pd.Timestamp(END) - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
START_10Y = (pd.Timestamp(END) - timedelta(days=365 * 10)).strftime("%Y-%m-%d")
MIN_N = 3

EXPAND_TARGETS = [
    "ACC100_MULTI_V5",
    "ACC_WIDE_P92",
    "ACC_WIDE_P90",
    "ACC_WIDE_P85",
    "ACC_WIDE_P85B",
    "ACC_WIDE_P80",
    "ACC_WIDE_P75",
]
CAP2_TARGETS = [
    ("ACC100_MULTI_V5", 100.0),
    ("ACC_WIDE_P92", 99.24),
    ("ACC_WIDE_P90", 95.4),
    ("ACC_WIDE_P85", 89.69),
]


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 4)


def desk_ok(rows: List[dict], floor: float) -> bool:
    rs3 = _clip(rows, START_3Y, END)
    if floor >= 100.0:
        if not (rs3 and is_perfect(rs3)):
            return False
        soft = 100.0
    else:
        if len(rs3) >= MIN_N and hit_pct(rs3) + 1e-9 < floor:
            return False
        soft = max(floor - 2.0, 70.0)
    for start in (START_5Y, START_1Y):
        rs = _clip(rows, start, END)
        if len(rs) < MIN_N:
            continue
        if floor >= 100.0:
            if not is_perfect(rs):
                return False
        elif hit_pct(rs) + 1e-9 < soft:
            return False
    return True


def stream_ok(rows: List[dict], floor: float) -> bool:
    rs3 = _clip(rows, START_3Y, END)
    if len(rs3) < MIN_N:
        return False
    if floor >= 100.0:
        if not is_perfect(rs3):
            return False
        for start in (START_5Y, START_1Y):
            rs = _clip(rows, start, END)
            if len(rs) >= MIN_N and not is_perfect(rs):
                return False
        return True
    if hit_pct(rs3) + 1e-9 < floor:
        return False
    rs5 = _clip(rows, START_5Y, END)
    if len(rs5) >= MIN_N and hit_pct(rs5) + 1e-9 < max(floor - 2.0, 70.0):
        return False
    return True


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


def weekday_filt(rows: List[dict], *, weekdays: Set[int]) -> List[dict]:
    out = []
    for r in rows:
        try:
            wd = pd.Timestamp(str(r.get("day") or "")).weekday()
        except Exception:
            continue
        if wd in weekdays:
            out.append(r)
    return out


BANDS = [
    ("m915", 9 * 60 + 15, 9 * 60 + 20),
    ("m920", 9 * 60 + 20, 9 * 60 + 30),
    ("m930", 9 * 60 + 30, 9 * 60 + 45),
    ("m945", 9 * 60 + 45, 10 * 60),
    ("m1000", 10 * 60, 10 * 60 + 20),
    ("m1020", 10 * 60 + 20, 10 * 60 + 45),
    ("m1045", 10 * 60 + 45, 11 * 60 + 15),
    ("m1115", 11 * 60 + 15, 11 * 60 + 45),
    ("m1145", 11 * 60 + 45, 12 * 60 + 30),
    ("m1230", 12 * 60 + 30, 13 * 60 + 15),
    ("m1315", 13 * 60 + 15, 14 * 60),
    ("m1400", 14 * 60, 14 * 60 + 30),
    ("m1430", 14 * 60 + 30, 15 * 60 + 15),
    ("open2", 9 * 60 + 15, 10 * 60 + 15),
    ("core", 10 * 60, 14 * 60),
    ("all", None, None),
]
GAPS = [
    ("nogap", None, False, False),
    ("g013", 0.13, False, False),
    ("g017", 0.17, False, False),
    ("g023", 0.23, False, False),
    ("g029", 0.29, False, False),
    ("g034", 0.34, False, False),
    ("g041", 0.41, False, False),
    ("g047", 0.47, False, False),
    ("g053", 0.53, False, False),
    ("g068", 0.68, False, False),
    ("gdn013", 0.13, True, False),
    ("gdn017", 0.17, True, False),
    ("gdn023", 0.23, True, False),
    ("gdn034", 0.34, True, False),
    ("gup013", 0.13, False, True),
    ("gup017", 0.17, False, True),
    ("gup023", 0.23, False, True),
    ("gup034", 0.34, False, True),
]
PMINS = (0.0, 0.46, 0.51, 0.54, 0.56, 0.58, 0.61, 0.63, 0.67, 0.71, 0.73, 0.77, 0.81, 0.87, 0.91)
WEEKDAY_SETS = [
    ("wd_mtw", {0, 1, 2}),
    ("wd_wrf", {2, 3, 4}),
    ("wd_mf", {0, 4}),
    ("wd_tt", {1, 3}),
    ("wd_all", {0, 1, 2, 3, 4}),
]

# Band/gap maps for seed rebuild (union of known labels)
_BAND_SEED = {b[0]: (b[1], b[2]) for b in BANDS}
_BAND_SEED.update(
    {
        "first15": (9 * 60 + 15, 9 * 60 + 30),
        "first20": (9 * 60 + 15, 9 * 60 + 35),
        "first30": (9 * 60 + 15, 9 * 60 + 45),
        "first45": (9 * 60 + 15, 10 * 60),
        "first50": (9 * 60 + 15, 10 * 60 + 5),
        "open": (9 * 60 + 15, 10 * 60 + 30),
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
        "all": (None, None),
    }
)
_GAP_SEED = {g[0]: (g[1], g[2], g[3]) for g in GAPS}
for lab, a, d, u in [
    ("nogap", None, False, False),
    ("g010", 0.10, False, False), ("g012", 0.12, False, False), ("g015", 0.15, False, False),
    ("g016", 0.16, False, False), ("g018", 0.18, False, False), ("g019", 0.19, False, False),
    ("g020", 0.20, False, False), ("g021", 0.21, False, False), ("g022", 0.22, False, False),
    ("g024", 0.24, False, False), ("g025", 0.25, False, False), ("g027", 0.27, False, False),
    ("g028", 0.28, False, False), ("g030", 0.30, False, False), ("g032", 0.32, False, False),
    ("g033", 0.33, False, False), ("g035", 0.35, False, False), ("g036", 0.36, False, False),
    ("g038", 0.38, False, False), ("g040", 0.40, False, False), ("g042", 0.42, False, False),
    ("g045", 0.45, False, False), ("g048", 0.48, False, False), ("g050", 0.50, False, False),
    ("g052", 0.52, False, False), ("g055", 0.55, False, False), ("g058", 0.58, False, False),
    ("g060", 0.60, False, False), ("g062", 0.62, False, False), ("g065", 0.65, False, False),
    ("g070", 0.70, False, False), ("g075", 0.75, False, False), ("g080", 0.80, False, False),
    ("g085", 0.85, False, False), ("g090", 0.90, False, False), ("g100", 1.0, False, False),
    ("gdn010", 0.10, True, False), ("gdn012", 0.12, True, False), ("gdn015", 0.15, True, False),
    ("gdn018", 0.18, True, False), ("gdn020", 0.20, True, False), ("gdn022", 0.22, True, False),
    ("gdn025", 0.25, True, False), ("gdn028", 0.28, True, False), ("gdn030", 0.30, True, False),
    ("gdn035", 0.35, True, False), ("gdn040", 0.40, True, False), ("gdn045", 0.45, True, False),
    ("gdn050", 0.50, True, False), ("gdn055", 0.55, True, False), ("gdn060", 0.60, True, False),
    ("gup010", 0.10, False, True), ("gup012", 0.12, False, True), ("gup015", 0.15, False, True),
    ("gup018", 0.18, False, True), ("gup020", 0.20, False, True), ("gup022", 0.22, False, True),
    ("gup025", 0.25, False, True), ("gup028", 0.28, False, True), ("gup030", 0.30, False, True),
    ("gup035", 0.35, False, True), ("gup040", 0.40, False, True), ("gup045", 0.45, False, True),
    ("gup050", 0.50, False, True), ("gup055", 0.55, False, True), ("gup060", 0.60, False, True),
]:
    _GAP_SEED[lab] = (a, d, u)


def _universes(path_u, dual15, dual5, proven, champ):
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


def rebuild_seed_tag(tag, universes, gaps, active, ix_map):
    raw = tag[2:] if tag.startswith("E_") else tag
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
    if uname not in universes or not p_s.startswith("p"):
        return None
    try:
        digits = p_s[1:]
        pmin = int(digits) / (1000.0 if len(digits) >= 3 else 100.0)
    except Exception:
        return None
    side = None if side_s == "BOTH" else side_s
    variant, glab, htf_s = parts[-1], parts[-2], parts[-3]
    blab = "_".join(parts[3:-3])
    if blab not in _BAND_SEED or glab not in _GAP_SEED:
        return None
    lo, hi = _BAND_SEED[blab]
    gabsm, gdn, gup = _GAP_SEED[glab]
    base = filt(
        universes[uname],
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
    if variant == "first":
        return first_day(base)
    if variant == "bestp":
        return bestp_day(base)
    if variant == "last":
        return last_day(base)
    if variant == "mid":
        return mid_day(base)
    if variant == "second":
        by: Dict[str, List[dict]] = defaultdict(list)
        for r in base:
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
    return base


def rebuild_seeds(tags, path_u, gaps, active, dual15, dual5, proven, champ):
    universes = _universes(path_u, dual15, dual5, proven, champ)
    ix_map = {
        "d15": _ix(dual15), "p15": _ix(proven), "d5": _ix(dual5),
        "ch": _ix(path_u.get("champ_native") or champ), "any15": _ix(dual15),
    }
    for rk, crow in (path_u.get("crown_by_risk") or {}).items():
        if not str(rk).startswith("_"):
            ix_map[f"cr{str(rk).replace('.0', '')}"] = _ix(crow)
    for rk, grow in (path_u.get("good_by_risk") or {}).items():
        if not str(rk).startswith("_") and rk != "native":
            ix_map[f"gd{str(rk).replace('.0', '')}"] = _ix(grow)
    out, ok, fail = {}, 0, 0
    for tag in tags:
        if tag in out:
            continue
        rows = rebuild_seed_tag(tag, universes, gaps, active, ix_map)
        if rows is None:
            fail += 1
            continue
        out[tag] = rows
        ok += 1
    print(f"  rebuilt seeds ok={ok} fail={fail}", flush=True)
    return out


def _dedupe(streams):
    by_tag = {}
    for tag, rows in streams:
        rs3 = _clip(rows, START_3Y, END)
        st = {"n_3y": len(rs3), "hit_3y": hit_pct(rs3), "perfect_3y": bool(rs3) and is_perfect(rs3)}
        prev = by_tag.get(tag)
        if prev is None or st["n_3y"] > prev[2]["n_3y"]:
            by_tag[tag] = (tag, rows, st)
    out = list(by_tag.values())
    out.sort(key=lambda x: (x[2]["hit_3y"], x[2]["n_3y"]), reverse=True)
    return out


def mine_alt(path_u, gaps, active, dual15, dual5, proven, champ, *, floor_min: float):
    streams: List[Tuple[str, List[dict]]] = []
    universes = _universes(path_u, dual15, dual5, proven, champ)
    n_eval = 0
    for uname, urows in universes.items():
        for side in (None, "BUY", "SELL"):
            for blab, lo, hi in BANDS:
                for glab, gabsm, gdn, gup in GAPS:
                    for use_htf in (False, True):
                        if use_htf and gabsm is not None and gabsm < 0.15 and not gdn and not gup:
                            continue
                        for pmin in PMINS:
                            base = filt(
                                urows, p_min=pmin, side=side, hm_lo=lo, hm_hi=hi,
                                htf=active if use_htf else None,
                                gaps=gaps if gabsm is not None or gdn or gup else None,
                                gap_abs=gabsm, gap_dn=gdn, gap_up=gup,
                            )
                            # wd_all: all picks; other weekdays: first+mid only (runtime)
                            for wlab, wset in WEEKDAY_SETS:
                                scoped = base if wlab == "wd_all" else weekday_filt(base, weekdays=wset)
                                if not scoped:
                                    continue
                                variants = (
                                    (("first", first_day(scoped)), ("bestp", bestp_day(scoped)),
                                     ("last", last_day(scoped)), ("mid", mid_day(scoped)), ("raw", scoped))
                                    if wlab == "wd_all"
                                    else (("first", first_day(scoped)), ("mid", mid_day(scoped)))
                                )
                                for vlab, vrows in variants:
                                    if not vrows:
                                        continue
                                    n_eval += 1
                                    rs3 = _clip(vrows, START_3Y, END)
                                    if len(rs3) < MIN_N or hit_pct(rs3) + 1e-9 < floor_min:
                                        continue
                                    tag = (
                                        f"F_{uname}_{side or 'BOTH'}_p{int(round(pmin * 100))}_"
                                        f"{blab}_{'htf' if use_htf else 'any'}_{glab}_{wlab}_{vlab}"
                                    )
                                    streams.append((tag, vrows))

    ix = {
        "d15": _ix(dual15), "p15": _ix(proven), "d5": _ix(dual5),
        "ch": _ix(path_u.get("champ_native") or champ),
    }
    for rk, crow in (path_u.get("crown_by_risk") or {}).items():
        if not str(rk).startswith("_"):
            ix[f"cr{str(rk).replace('.0', '')}"] = _ix(crow)
    for rk, grow in (path_u.get("good_by_risk") or {}).items():
        if not str(rk).startswith("_") and rk != "native":
            ix[f"gd{str(rk).replace('.0', '')}"] = _ix(grow)

    # pairwise + light triple (agree A∩B then ∩C via second agree on rows)
    pairs = [
        ("d15", "d5"), ("d15", "ch"), ("d5", "ch"), ("d15", "gd30"), ("d5", "gd40"),
        ("gd30", "cr20"), ("gd40", "cr30"), ("ch", "cr20"), ("p15", "gd30"), ("d15", "cr20"),
    ]
    for tol in (3, 5, 8, 12, 18, 25, 35, 50, 70, 100):
        for a, b in pairs:
            if a not in ix or b not in ix:
                continue
            rows = time_agree(ix[a], ix[b], tol=tol, tag="cf")
            rs3 = _clip(rows, START_3Y, END)
            if len(rs3) >= MIN_N and hit_pct(rs3) + 1e-9 >= floor_min:
                streams.append((f"CF_T{tol}_{a}_{b}", rows))
            # triple: (a∩b) ∩ c
            for c in ("ch", "cr20", "gd30", "d5"):
                if c in (a, b) or c not in ix:
                    continue
                trip = time_agree(_ix(rows), ix[c], tol=tol, tag="cf3")
                rs3t = _clip(trip, START_3Y, END)
                if len(rs3t) >= MIN_N and hit_pct(rs3t) + 1e-9 >= floor_min:
                    streams.append((f"CF3_T{tol}_{a}_{b}_{c}", trip))

    out = _dedupe(streams)
    print(f"  alt mine eval≈{n_eval} → unique={len(out)}", flush=True)
    return out


def greedy(base, streams, floor, *, mode="day", max_rounds=160, used_tags=None):
    cur = list(base)
    added, used = [], set(used_tags or [])
    improved, rounds = True, 0
    merge = (lambda a, b: union_day_cap2(a, b, cap=2)) if mode == "cap2" else union_unique_days
    while improved and rounds < max_rounds:
        improved = False
        rounds += 1
        days = {str(r.get("day") or "") for r in cur} if mode == "day" else None
        ranked = []
        for tag, rows, st in streams:
            if tag in used or not stream_ok(rows, floor):
                continue
            if mode == "cap2":
                new_n = len(merge(cur, rows)) - len(cur)
            else:
                new_n = sum(1 for r in rows if str(r["day"]) not in days)
            if new_n:
                ranked.append((new_n, st.get("hit_3y") or 0, tag, rows))
        ranked.sort(reverse=True)
        # only try top 80 candidates per round for speed
        for new_n, _h, tag, rows in ranked[:80]:
            merged = merge(cur, rows)
            if len(merged) <= len(cur) or not desk_ok(merged, floor):
                continue
            delta = len(merged) - len(cur)
            cur = merged
            used.add(tag)
            d3 = _clip(cur, START_3Y, END)
            added.append({"tag": tag, "new_n": delta, "desk_n_3y": len(d3), "desk_hit_3y": hit_pct(d3)})
            print(f"    [{mode}] +{delta} {tag} → 3y={len(d3)}@{hit_pct(d3):.2f}%", flush=True)
            improved = True
            break
    return cur, added


def summarize(desk):
    out = {}
    for lab, start in (("1y", START_1Y), ("3y", START_3Y), ("5y", START_5Y)):
        rs = _clip(desk, start, END)
        out[lab] = {
            "n": len(rs), "hit_pct": hit_pct(rs),
            "perfect": bool(rs) and is_perfect(rs),
            "points": (_agg(rs) or {}).get("points"),
        }
    return out


def replay_tags(base, tags, by_tag, floor, *, mode="day"):
    cur, used = list(base), set()
    merge = (lambda a, b: union_day_cap2(a, b, cap=2)) if mode == "cap2" else union_unique_days
    for tag in tags:
        rows = by_tag.get(tag)
        if not rows or not stream_ok(rows, floor):
            continue
        merged = merge(cur, rows)
        if len(merged) <= len(cur):
            used.add(tag)
            continue
        if desk_ok(merged, floor):
            cur = merged
            used.add(tag)
    return cur, used


def cand_name(desk_tag, n, p2e_n, *, mode):
    if mode == "cap2":
        return f"{desk_tag}_CAP2_P2F"
    if desk_tag == "ACC100_MULTI_V5":
        if p2e_n is not None and n > p2e_n:
            return "ACC100_MULTI_V11"
        if n > 241:
            return "ACC100_MULTI_V11"
        if n > 216:
            return "ACC100_MULTI_V10"
        return "ACC100_MULTI_V9"
    return f"{desk_tag}_P2F"


def main():
    t0 = time.time()
    print("PHASE-2f KEEP PUSHING @ same accuracy (P1 locked, P2c held, seed P2e)", flush=True)

    p2e = {}
    if P2E_RECIPES.exists():
        p2e = json.loads(P2E_RECIPES.read_text(encoding="utf-8")).get("candidates") or {}

    dual = json.loads(CACHE_DUAL_10Y.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH_10Y.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_10Y < d <= END]
    active = fs._active_days(sess, fs._load_daily()) if sess else set()

    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ = _champ_floor([dict(r, track="champion") for r in dual["dual15"]["champion"]])
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]
    champ_native = path_u.get("champ_native") or champ

    print("  rebuild Phase-1…", flush=True)
    phase1 = build_all_accurate_desks(
        proven15=proven, dual15=dual15, dual5=dual5,
        crown_by_risk=path_u.get("crown_by_risk") or {},
        good_by_risk=path_u.get("good_by_risk") or {},
        champ_rows=champ_native, gap_pct_by_day=gaps, htf_days=active,
    )

    seed_tags, seen = [], set()
    for meta in p2e.values():
        for t in meta.get("stream_tags_research") or []:
            if t not in seen:
                seen.add(t)
                seed_tags.append(t)
    print(f"  rebuild {len(seed_tags)} P2e seeds + F-mine…", flush=True)
    seed_map = rebuild_seeds(
        seed_tags, path_u, gaps, active, dual15, dual5, proven, champ
    )
    seed_streams = []
    for tag, rows in seed_map.items():
        rs3 = _clip(rows, START_3Y, END)
        seed_streams.append((tag, rows, {
            "n_3y": len(rs3), "hit_3y": hit_pct(rs3),
            "perfect_3y": bool(rs3) and is_perfect(rs3),
        }))
    alt = mine_alt(
        {"crown_by_risk": path_u.get("crown_by_risk") or {},
         "good_by_risk": path_u.get("good_by_risk") or {},
         "champ_native": champ_native},
        gaps, active, dual15, dual5, proven, champ, floor_min=75.0,
    )
    by_tag_map: Dict[str, Tuple[str, List[dict], Dict[str, Any]]] = {}
    for tag, rows, st in seed_streams + alt:
        prev = by_tag_map.get(tag)
        if prev is None or st["n_3y"] > prev[2]["n_3y"]:
            by_tag_map[tag] = (tag, rows, st)
    all_streams = list(by_tag_map.values())
    by_tag = {t: rows for t, rows, _ in all_streams}
    perfect = [s for s in all_streams if s[2].get("perfect_3y")]
    print(f"  combined tags={len(all_streams)} perfect={len(perfect)}", flush=True)

    results = {}
    for desk_tag in EXPAND_TARGETS:
        meta = DESK_REGISTRY[desk_tag]
        floor = float(meta["research_3y"]["hit_pct"])
        if floor >= 99.999:
            floor = 100.0
            pool = perfect
        else:
            pool = [s for s in all_streams if stream_ok(s[1], floor)]
        base = list(phase1[desk_tag])
        base_sum = summarize(base)
        held = p2e.get(desk_tag) or {}
        seed_list = list(held.get("stream_tags_research") or [])
        p2e_n = (held.get("research_3y") or {}).get("n")
        seeded, used = replay_tags(base, seed_list, by_tag, floor, mode="day")
        seed_sum = summarize(seeded)
        print(
            f"  {desk_tag} floor={floor:g}% P1={base_sum['3y']['n']} "
            f"seedP2e={seed_sum['3y']['n']} (ref={p2e_n}) pool={len(pool)}…",
            flush=True,
        )
        desk, added = greedy(seeded, pool, floor, mode="day", max_rounds=160, used_tags=used)
        got = summarize(desk)
        cand = cand_name(desk_tag, got["3y"]["n"], p2e_n, mode="day") if got["3y"]["n"] > base_sum["3y"]["n"] else None
        results[desk_tag] = {
            "mode": "day", "floor": floor,
            "phase1_3y": meta["research_3y"], "phase2e_3y_n": p2e_n,
            "baseline": base_sum, "seeded": seed_sum, "result": got,
            "delta_vs_phase1_3y": got["3y"]["n"] - base_sum["3y"]["n"],
            "delta_vs_phase2e_3y": (got["3y"]["n"] - p2e_n) if p2e_n is not None else None,
            "added_streams_new": added, "candidate_tag": cand,
        }
        print(
            f"    → 3y {got['3y']['n']}@{got['3y']['hit_pct']}% "
            f"ΔP1={results[desk_tag]['delta_vs_phase1_3y']:+d} "
            f"ΔP2e={results[desk_tag]['delta_vs_phase2e_3y']} cand={cand}",
            flush=True,
        )

    for desk_tag, floor in CAP2_TARGETS:
        pool = perfect if floor >= 100.0 else [s for s in all_streams if stream_ok(s[1], floor)]
        base = list(phase1[desk_tag])
        held = p2e.get(f"{desk_tag}_CAP2") or {}
        seed_list = list(held.get("stream_tags_research") or [])
        p2e_n = (held.get("research_3y") or {}).get("n")
        seeded, used = replay_tags(base, seed_list, by_tag, floor, mode="cap2")
        print(f"  {desk_tag} CAP2 floor={floor:g}% seed={summarize(seeded)['3y']['n']} (ref={p2e_n})…", flush=True)
        desk, added = greedy(seeded, pool, floor, mode="cap2", max_rounds=120, used_tags=used)
        got = summarize(desk)
        key = f"{desk_tag}_CAP2"
        results[key] = {
            "mode": "cap2", "floor": floor, "phase2e_3y_n": p2e_n,
            "baseline": summarize(base), "seeded": summarize(seeded), "result": got,
            "delta_vs_phase1_3y": got["3y"]["n"] - summarize(base)["3y"]["n"],
            "delta_vs_phase2e_3y": (got["3y"]["n"] - p2e_n) if p2e_n is not None else None,
            "added_streams_new": added,
            "candidate_tag": cand_name(desk_tag, got["3y"]["n"], p2e_n, mode="cap2"),
        }
        print(
            f"    → 3y {got['3y']['n']}@{got['3y']['hit_pct']}% "
            f"ΔP1={results[key]['delta_vs_phase1_3y']:+d} ΔP2e={results[key]['delta_vs_phase2e_3y']}",
            flush=True,
        )

    payload = {
        "phase": "2f", "phase1_held": True, "phase2c_held": True, "phase2e_seed": True,
        "partial_note": "Seeded from salvaged P2e partial",
        "window_end": END, "streams_mined": len(all_streams), "perfect_streams": len(perfect),
        "results": results, "elapsed_s": round(time.time() - t0, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for dest in (OUT, LEDGER, HOLD / "reports"):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "ACC_PHASE2F_KEEP_PUSHING.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )

    lines = [
        "# Phase-2f — keep pushing @ same accuracy",
        "",
        "**Phase-1 LOCKED · Phase-2c HELD.** Seeds from salvaged Phase-2e partial.",
        "New axes: micro-bands · weekday · mid pick · triple-CF.",
        "",
        f"Tags={len(all_streams)} · perfect={len(perfect)} · elapsed {payload['elapsed_s']}s",
        "",
        "## Day-dedupe vs held / P2e",
        "",
        "| Desk | Floor | P1 | P2c* | P2e | **P2f** | ΔP2e | Hit | Candidate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    p2c_ref = {"ACC100_MULTI_V5": 199, "ACC_WIDE_P92": 203, "ACC_WIDE_P90": 237,
               "ACC_WIDE_P85": 293, "ACC_WIDE_P85B": 303, "ACC_WIDE_P80": 341, "ACC_WIDE_P75": 372}
    for desk_tag in EXPAND_TARGETS:
        r = results[desk_tag]
        b, g = r["baseline"]["3y"], r["result"]["3y"]
        p2en = r.get("phase2e_3y_n")
        d = r.get("delta_vs_phase2e_3y")
        ds = "—" if d is None else (f"+{d}" if d >= 0 else str(d))
        lines.append(
            f"| `{desk_tag}` | {r['floor']:g} | {b['n']} | {p2c_ref.get(desk_tag, '—')} | "
            f"{p2en if p2en is not None else '—'} | **{g['n']}** | {ds} | {g['hit_pct']} | "
            f"`{r['candidate_tag'] or '—'}` |"
        )
    lines += ["", "## Cap2", "",
              "| Desk | P1 | P2e | **P2f** | ΔP2e | Hit | Candidate |",
              "|---|---:|---:|---:|---:|---:|---|"]
    for key in (k for k in results if k.endswith("_CAP2")):
        r = results[key]
        b, g = r["baseline"]["3y"], r["result"]["3y"]
        p2en = r.get("phase2e_3y_n")
        d = r.get("delta_vs_phase2e_3y")
        ds = "—" if d is None else (f"+{d}" if d >= 0 else str(d))
        lines.append(
            f"| `{key}` | {b['n']} | {p2en if p2en is not None else '—'} | **{g['n']}** | "
            f"{ds} | {g['hit_pct']} | `{r['candidate_tag']}` |"
        )
    lines += ["", "*P2c = held in `holding_accurate/recipes.json`", "",
              "JSON: `ACC_PHASE2F_KEEP_PUSHING.json`", ""]
    text = "\n".join(lines)
    for dest in (OUT, LEDGER, HOLD / "reports"):
        (dest / "ACC_PHASE2F_KEEP_PUSHING.md").write_text(text, encoding="utf-8")
    print("Wrote", OUT / "ACC_PHASE2F_KEEP_PUSHING.md", flush=True)


if __name__ == "__main__":
    main()
