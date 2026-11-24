"""Phase-2e: MORE CALLS @ same accuracy.

Phase-1 LOCKED. Phase-2c HELD. Phase-2d = research seed.
New axes: last/second day picks · cross-universe CF · day_side · more cap2.

  python -u prod_live/tests/builders/research_acc_phase2e_more_calls.py
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
P2D_RECIPES = HOLD / "phase2d" / "recipes_research.json"

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
    ("ACC_WIDE_P85B", 88.4),
    ("ACC_WIDE_P80", 84.72),
    ("ACC_WIDE_P75", 82.71),
]

DAY_SIDE_TARGETS = [
    ("ACC100_MULTI_V5", 100.0),
    ("ACC_WIDE_P92", 99.24),
    ("ACC_WIDE_P90", 95.4),
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
        best = sorted(
            by[day],
            key=lambda x: (_hm_mins(str(x.get("hm") or "00:00")), float(x.get("p_t1") or 0)),
            reverse=True,
        )[0]
        out.append(best)
    return out


def second_day(rows: List[dict]) -> List[dict]:
    """Second-earliest of day (skip first) — useful for cap2 extras."""
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


def union_day_side(base: List[dict], extra: List[dict]) -> List[dict]:
    """At most one call per (day, side)."""
    seen: Set[Tuple[str, str]] = set()
    out: List[dict] = []
    for r in list(base) + list(extra):
        key = (str(r.get("day") or ""), _side(r))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        out.append(dict(r))
    out.sort(key=lambda x: (str(x.get("day") or ""), _hm_mins(str(x.get("hm") or "99:99"))))
    return out


# Medium grid + new bands 2d didn't emphasize; keep runtime sane vs full 2d remine
BANDS = [
    ("first10", 9 * 60 + 15, 9 * 60 + 25),
    ("first15", 9 * 60 + 15, 9 * 60 + 30),
    ("first25", 9 * 60 + 15, 9 * 60 + 40),
    ("first35", 9 * 60 + 15, 9 * 60 + 50),
    ("first50", 9 * 60 + 15, 10 * 60 + 5),
    ("open", 9 * 60 + 15, 10 * 60 + 30),
    ("am1015", 9 * 60 + 15, 10 * 60 + 15),
    ("am11", 9 * 60 + 15, 11 * 60),
    ("am1120", 9 * 60 + 15, 11 * 60 + 20),
    ("am1145", 9 * 60 + 15, 11 * 60 + 45),
    ("am1215", 9 * 60 + 15, 12 * 60 + 15),
    ("brunch3", 10 * 60 + 30, 12 * 60 + 15),
    ("lunch2", 11 * 60 + 30, 13 * 60 + 30),
    ("mid3", 10 * 60 + 45, 13 * 60 + 15),
    ("latemid2", 11 * 60, 14 * 60 + 15),
    ("earlypm2", 12 * 60, 14 * 60 + 30),
    ("pm3", 12 * 60 + 15, 15 * 60 + 15),
    ("last135", 13 * 60, 15 * 60 + 15),
    ("last105", 13 * 60 + 30, 15 * 60 + 15),
    ("last80", 13 * 60 + 55, 15 * 60 + 15),
    ("last55", 14 * 60 + 20, 15 * 60 + 15),
    ("last40", 14 * 60 + 35, 15 * 60 + 15),
    ("all", None, None),
]
GAPS = [
    ("nogap", None, False, False),
    ("g012", 0.12, False, False),
    ("g016", 0.16, False, False),
    ("g019", 0.19, False, False),
    ("g021", 0.21, False, False),
    ("g024", 0.24, False, False),
    ("g027", 0.27, False, False),
    ("g033", 0.33, False, False),
    ("g036", 0.36, False, False),
    ("g042", 0.42, False, False),
    ("g048", 0.48, False, False),
    ("g052", 0.52, False, False),
    ("g058", 0.58, False, False),
    ("g062", 0.62, False, False),
    ("g085", 0.85, False, False),
    ("g100", 1.00, False, False),
    ("gdn012", 0.12, True, False),
    ("gdn018", 0.18, True, False),
    ("gdn022", 0.22, True, False),
    ("gdn028", 0.28, True, False),
    ("gdn035", 0.35, True, False),
    ("gdn045", 0.45, True, False),
    ("gdn060", 0.60, True, False),
    ("gup012", 0.12, False, True),
    ("gup018", 0.18, False, True),
    ("gup022", 0.22, False, True),
    ("gup028", 0.28, False, True),
    ("gup035", 0.35, False, True),
    ("gup045", 0.45, False, True),
    ("gup060", 0.60, False, True),
]
# Odd fractions 2d skipped
PMINS = (
    0.0, 0.41, 0.43, 0.44, 0.46, 0.485, 0.495, 0.505, 0.515, 0.525, 0.535, 0.545,
    0.555, 0.565, 0.575, 0.585, 0.595, 0.605, 0.615, 0.625, 0.635, 0.655, 0.675,
    0.695, 0.715, 0.735, 0.755, 0.775, 0.795, 0.815, 0.835, 0.855, 0.875, 0.895, 0.915, 0.935,
)


# 2d-compat grid so P2d seed tags rematch
BANDS_2D = [
    ("first15", 9 * 60 + 15, 9 * 60 + 30),
    ("first20", 9 * 60 + 15, 9 * 60 + 35),
    ("first30", 9 * 60 + 15, 9 * 60 + 45),
    ("first45", 9 * 60 + 15, 10 * 60),
    ("open", 9 * 60 + 15, 10 * 60 + 30),
    ("am10", 9 * 60 + 15, 10 * 60 + 45),
    ("am1030", 9 * 60 + 15, 10 * 60 + 30),
    ("am11", 9 * 60 + 15, 11 * 60),
    ("am1115", 9 * 60 + 15, 11 * 60 + 15),
    ("am1130", 9 * 60 + 15, 11 * 60 + 30),
    ("am12", 9 * 60 + 15, 12 * 60),
    ("am1230", 9 * 60 + 15, 12 * 60 + 30),
    ("brunch", 10 * 60 + 15, 12 * 60),
    ("brunch2", 10 * 60, 12 * 60 + 30),
    ("lunch", 11 * 60 + 45, 13 * 60 + 15),
    ("mid", 10 * 60, 13 * 60),
    ("mid2", 10 * 60 + 15, 13 * 60 + 30),
    ("latemid", 10 * 60 + 30, 14 * 60),
    ("earlypm", 11 * 60 + 30, 14 * 60),
    ("pm", 12 * 60 + 30, 15 * 60 + 15),
    ("pm2", 12 * 60, 15 * 60),
    ("last150", 12 * 60 + 45, 15 * 60 + 15),
    ("last120", 13 * 60 + 15, 15 * 60 + 15),
    ("last90", 13 * 60 + 45, 15 * 60 + 15),
    ("last75", 14 * 60, 15 * 60 + 15),
    ("last60", 14 * 60 + 15, 15 * 60 + 15),
    ("last45", 14 * 60 + 30, 15 * 60 + 15),
    ("all", None, None),
]
GAPS_2D = [
    ("nogap", None, False, False),
    ("g010", 0.10, False, False),
    ("g015", 0.15, False, False),
    ("g018", 0.18, False, False),
    ("g020", 0.20, False, False),
    ("g022", 0.22, False, False),
    ("g025", 0.25, False, False),
    ("g028", 0.28, False, False),
    ("g030", 0.30, False, False),
    ("g032", 0.32, False, False),
    ("g035", 0.35, False, False),
    ("g038", 0.38, False, False),
    ("g040", 0.40, False, False),
    ("g045", 0.45, False, False),
    ("g050", 0.50, False, False),
    ("g055", 0.55, False, False),
    ("g060", 0.60, False, False),
    ("g065", 0.65, False, False),
    ("g070", 0.70, False, False),
    ("g075", 0.75, False, False),
    ("g080", 0.80, False, False),
    ("g090", 0.90, False, False),
    ("gdn010", 0.10, True, False),
    ("gdn015", 0.15, True, False),
    ("gdn020", 0.20, True, False),
    ("gdn025", 0.25, True, False),
    ("gdn030", 0.30, True, False),
    ("gdn040", 0.40, True, False),
    ("gdn050", 0.50, True, False),
    ("gdn055", 0.55, True, False),
    ("gup010", 0.10, False, True),
    ("gup015", 0.15, False, True),
    ("gup020", 0.20, False, True),
    ("gup025", 0.25, False, True),
    ("gup030", 0.30, False, True),
    ("gup040", 0.40, False, True),
    ("gup050", 0.50, False, True),
    ("gup055", 0.55, False, True),
]
PMINS_2D = (
    0.0, 0.40, 0.42, 0.45, 0.47, 0.48, 0.49, 0.50, 0.51, 0.52, 0.53, 0.54, 0.55,
    0.56, 0.57, 0.58, 0.59, 0.60, 0.61, 0.62, 0.63, 0.64, 0.65, 0.66, 0.68, 0.70,
    0.72, 0.74, 0.75, 0.76, 0.78, 0.80, 0.82, 0.84, 0.85, 0.86, 0.88, 0.90, 0.92, 0.94,
)


def _universes(path_u, dual15, dual5, proven, champ):
    universes: Dict[str, List[dict]] = {}
    for rk, rows in (path_u.get("crown_by_risk") or {}).items():
        if str(rk).startswith("_"):
            continue
        universes[f"CR{str(rk).replace('.0', '')}"] = rows
    for rk, rows in (path_u.get("good_by_risk") or {}).items():
        if str(rk).startswith("_") or rk == "native":
            continue
        universes[f"GD{str(rk).replace('.0', '')}"] = rows
    universes["CH"] = path_u.get("champ_native") or champ
    universes["D5"] = dual5
    universes["PR"] = proven
    universes["D15"] = dual15
    return universes


def _dedupe_streams(streams: List[Tuple[str, List[dict]]]):
    by_sig: Dict[tuple, Tuple[str, List[dict], Dict[str, Any]]] = {}
    for tag, rows in streams:
        sig = tuple(
            sorted((str(r["day"]), _side(r), str(r.get("hm") or "")) for r in rows)
        )
        rs3 = _clip(rows, START_3Y, END)
        st = {
            "n_3y": len(rs3),
            "hit_3y": hit_pct(rs3),
            "perfect_3y": is_perfect(rs3) if rs3 else False,
        }
        prev = by_sig.get(sig)
        if prev is None or st["n_3y"] > prev[2]["n_3y"] or (
            st["n_3y"] == prev[2]["n_3y"] and st["hit_3y"] > prev[2]["hit_3y"]
        ):
            by_sig[sig] = (tag, rows, st)
    out = list(by_sig.values())
    out.sort(key=lambda x: (x[2]["hit_3y"], x[2]["n_3y"]), reverse=True)
    return out


_BAND_MAP = {b[0]: (b[1], b[2]) for b in BANDS_2D + BANDS}
_GAP_MAP = {g[0]: (g[1], g[2], g[3]) for g in GAPS_2D + GAPS}


def rebuild_seed_tag(
    tag: str,
    universes: Dict[str, List[dict]],
    gaps: Dict[str, float],
    active: Set[str],
    ix_map: Dict[str, Any],
) -> Optional[List[dict]]:
    """Parse a research stream tag and rebuild rows (for P2d seed rematch)."""
    if tag.startswith("CF_T"):
        # CF_T{tol}_{a}_{b}  or legacy CF_T{tol}_any15_d5 / d5_cr20 etc.
        parts = tag.split("_")
        try:
            tol = int(parts[1][1:])  # T40 → wait parts[1] is T40
        except Exception:
            return None
        rest = "_".join(parts[2:])
        legacy = {
            "any15_d5": ("d15", "d5"),
            "p15_d5": ("p15", "d5"),
            "any15_ch": ("d15", "ch"),
            "ch_d5": ("ch", "d5"),
            "p15_ch": ("p15", "ch"),
            "d5_p15": ("d5", "p15"),
            "d5_any15": ("d5", "d15"),
        }
        pair = legacy.get(rest)
        if pair is None and rest.startswith("any15_cr"):
            pair = ("d15", "cr" + rest[len("any15_cr") :])
        elif pair is None and rest.startswith("d5_cr"):
            pair = ("d5", "cr" + rest[len("d5_cr") :])
        elif pair is None and rest.startswith("ch_cr"):
            pair = ("ch", "cr" + rest[len("ch_cr") :])
        elif pair is None and rest.startswith("p15_cr"):
            pair = ("p15", "cr" + rest[len("p15_cr") :])
        elif pair is None:
            bits = rest.split("_")
            if len(bits) == 2:
                pair = (bits[0], bits[1])
        if not pair:
            return None
        a, b = pair
        if a not in ix_map or b not in ix_map:
            return None
        return time_agree(ix_map[a], ix_map[b], tol=tol, tag="cf")

    # UNAME_SIDE_pXX_band_htf|any_gap_variant
    # e.g. D15_BUY_p0_first15_htf_nogap_raw
    parts = tag.split("_")
    if len(parts) < 6:
        return None
    uname = parts[0]
    side_s = parts[1]
    p_s = parts[2]
    # band may be multi? usually one token; variant/gap/htf at end
    if not p_s.startswith("p") or uname not in universes:
        return None
    try:
        pmin = int(p_s[1:]) / 100.0
    except Exception:
        return None
    side = None if side_s == "BOTH" else side_s
    variant = parts[-1]
    glab = parts[-2]
    htf_s = parts[-3]
    blab = "_".join(parts[3:-3])
    if blab not in _BAND_MAP or glab not in _GAP_MAP:
        return None
    lo, hi = _BAND_MAP[blab]
    gabsm, gdn, gup = _GAP_MAP[glab]
    use_htf = htf_s == "htf"
    base = filt(
        universes[uname],
        p_min=pmin,
        side=side,
        hm_lo=lo,
        hm_hi=hi,
        htf=active if use_htf else None,
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
    if variant == "second":
        return second_day(base)
    return base


def rebuild_seeds(
    tags: List[str],
    path_u,
    gaps,
    active,
    dual15,
    dual5,
    proven,
    champ,
) -> Dict[str, List[dict]]:
    universes = _universes(path_u, dual15, dual5, proven, champ)
    ix_map = {
        "d15": _ix(dual15),
        "p15": _ix(proven),
        "d5": _ix(dual5),
        "ch": _ix(path_u.get("champ_native") or champ),
        "any15": _ix(dual15),
    }
    for rk, crow in (path_u.get("crown_by_risk") or {}).items():
        if str(rk).startswith("_"):
            continue
        ix_map[f"cr{str(rk).replace('.0', '')}"] = _ix(crow)
    for rk, grow in (path_u.get("good_by_risk") or {}).items():
        if str(rk).startswith("_") or rk == "native":
            continue
        ix_map[f"gd{str(rk).replace('.0', '')}"] = _ix(grow)

    out: Dict[str, List[dict]] = {}
    ok = fail = 0
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


def mine_alt(path_u, gaps, active, dual15, dual5, proven, champ, *, floor_min: float):
    """New axes only: last/second picks + odd grids + cross-CF (trimmed for runtime)."""
    streams: List[Tuple[str, List[dict]]] = []
    universes = _universes(path_u, dual15, dual5, proven, champ)
    # Trim: only new variants last/second; skip raw/first/bestp (seed covers those)
    n_eval = 0
    for uname, urows in universes.items():
        for side in (None, "BUY", "SELL"):
            for blab, lo, hi in BANDS:
                for glab, gabsm, gdn, gup in GAPS:
                    for use_htf in (False, True):
                        if use_htf and gabsm is not None and gabsm < 0.16 and not gdn and not gup:
                            continue
                        for pmin in PMINS:
                            base = filt(
                                urows,
                                p_min=pmin,
                                side=side,
                                hm_lo=lo,
                                hm_hi=hi,
                                htf=active if use_htf else None,
                                gaps=gaps if gabsm is not None or gdn or gup else None,
                                gap_abs=gabsm,
                                gap_dn=gdn,
                                gap_up=gup,
                            )
                            for vlab, vrows in (
                                ("last", last_day(base)),
                                ("second", second_day(base)),
                                ("raw", base),  # raw on odd grid still new vs 2d
                            ):
                                if not vrows:
                                    continue
                                n_eval += 1
                                rs3 = _clip(vrows, START_3Y, END)
                                if len(rs3) < MIN_N or hit_pct(rs3) + 1e-9 < floor_min:
                                    continue
                                tag = (
                                    f"E_{uname}_{side or 'BOTH'}_p{int(round(pmin * 1000))}_{blab}_"
                                    f"{'htf' if use_htf else 'any'}_{glab}_{vlab}"
                                )
                                streams.append((tag, vrows))

    ix = {
        "d15": _ix(dual15),
        "p15": _ix(proven),
        "d5": _ix(dual5),
        "ch": _ix(path_u.get("champ_native") or champ),
    }
    for rk, crow in (path_u.get("crown_by_risk") or {}).items():
        if str(rk).startswith("_"):
            continue
        ix[f"cr{str(rk).replace('.0', '')}"] = _ix(crow)
    for rk, grow in (path_u.get("good_by_risk") or {}).items():
        if str(rk).startswith("_") or rk == "native":
            continue
        ix[f"gd{str(rk).replace('.0', '')}"] = _ix(grow)

    pairs = [
        ("d15", "d5"), ("p15", "d5"), ("d15", "ch"), ("ch", "d5"), ("p15", "ch"),
        ("d5", "p15"), ("d15", "gd30"), ("d5", "gd30"), ("ch", "gd30"),
        ("d15", "gd40"), ("d5", "gd40"), ("p15", "gd40"),
        ("gd30", "cr20"), ("gd40", "cr20"), ("gd30", "cr30"), ("gd40", "cr30"),
        ("gd35", "cr20"), ("d5", "cr20"), ("d5", "cr30"), ("ch", "cr20"),
        ("ch", "cr30"), ("d15", "cr20"), ("d15", "cr35"), ("gd30", "ch"), ("gd40", "ch"),
    ]
    for tol in (2, 4, 6, 7, 9, 11, 14, 16, 19, 22, 24, 27, 32, 38, 42, 48, 55, 65, 80, 95, 110):
        for a, b in pairs:
            if a not in ix or b not in ix:
                continue
            tag = f"CF_T{tol}_{a}_{b}"
            rows = time_agree(ix[a], ix[b], tol=tol, tag="cf")
            rs3 = _clip(rows, START_3Y, END)
            if len(rs3) >= MIN_N and hit_pct(rs3) + 1e-9 >= floor_min:
                streams.append((tag, rows))
    out = _dedupe_streams(streams)
    print(f"  alt mine eval≈{n_eval} → unique={len(out)}", flush=True)
    return out


def mine(
    path_u,
    gaps,
    active,
    dual15,
    dual5,
    proven,
    champ,
    *,
    floor_min: float,
    seed_tags: List[str],
):
    print("  rebuild P2d seed tags…", flush=True)
    seed_map = rebuild_seeds(
        seed_tags, path_u, gaps, active, dual15, dual5, proven, champ
    )
    seed_streams = []
    for tag, rows in seed_map.items():
        rs3 = _clip(rows, START_3Y, END)
        st = {
            "n_3y": len(rs3),
            "hit_3y": hit_pct(rs3),
            "perfect_3y": is_perfect(rs3) if rs3 else False,
        }
        seed_streams.append((tag, rows, st))

    print("  alt mine (last/second + cross-CF)…", flush=True)
    alt = mine_alt(path_u, gaps, active, dual15, dual5, proven, champ, floor_min=floor_min)

    by_tag: Dict[str, Tuple[str, List[dict], Dict[str, Any]]] = {}
    for tag, rows, st in seed_streams + alt:
        prev = by_tag.get(tag)
        if prev is None or st["n_3y"] > prev[2]["n_3y"]:
            by_tag[tag] = (tag, rows, st)
    out = list(by_tag.values())
    out.sort(key=lambda x: (x[2]["hit_3y"], x[2]["n_3y"]), reverse=True)
    print(f"  combined unique-tags={len(out)} (≥{floor_min:g}% 3y)", flush=True)
    return out


def greedy(
    base: List[dict],
    streams: List[Tuple[str, List[dict], Dict[str, Any]]],
    floor: float,
    *,
    mode: str = "day",
    max_rounds: int = 220,
    used_tags: Optional[Set[str]] = None,
) -> Tuple[List[dict], List[dict]]:
    cur = list(base)
    added: List[dict] = []
    used = set(used_tags or [])
    improved = True
    rounds = 0

    def merge(a, b):
        if mode == "cap2":
            return union_day_cap2(a, b, cap=2)
        if mode == "day_side":
            return union_day_side(a, b)
        return union_unique_days(a, b)

    while improved and rounds < max_rounds:
        improved = False
        rounds += 1
        if mode == "day":
            keys = {str(r.get("day") or "") for r in cur}
        elif mode == "day_side":
            keys = {(str(r.get("day") or ""), _side(r)) for r in cur}
        else:
            keys = None

        ranked = []
        for tag, rows, st in streams:
            if tag in used:
                continue
            if not stream_ok(rows, floor):
                continue
            if mode == "cap2":
                new_n = len(merge(cur, rows)) - len(cur)
            elif mode == "day_side":
                new_n = sum(
                    1
                    for r in rows
                    if (str(r.get("day") or ""), _side(r)) not in keys
                )
            else:
                new_n = sum(1 for r in rows if str(r["day"]) not in keys)
            if new_n:
                ranked.append((new_n, st.get("hit_3y") or 0, tag, rows))
        ranked.sort(reverse=True)
        for new_n, _h, tag, rows in ranked:
            merged = merge(cur, rows)
            if len(merged) <= len(cur):
                continue
            if not desk_ok(merged, floor):
                continue
            delta = len(merged) - len(cur)
            cur = merged
            used.add(tag)
            d3 = _clip(cur, START_3Y, END)
            added.append(
                {
                    "tag": tag,
                    "new_n": delta,
                    "desk_n_3y": len(d3),
                    "desk_hit_3y": hit_pct(d3),
                }
            )
            print(
                f"    [{mode}] +{delta} {tag} → 3y={len(d3)}@{hit_pct(d3):.2f}%",
                flush=True,
            )
            improved = True
            break
    return cur, added


def summarize(desk: List[dict]) -> Dict[str, Any]:
    out = {}
    for lab, start in (("1y", START_1Y), ("3y", START_3Y), ("5y", START_5Y)):
        rs = _clip(desk, start, END)
        out[lab] = {
            "n": len(rs),
            "hit_pct": hit_pct(rs),
            "perfect": bool(rs) and is_perfect(rs),
            "points": (_agg(rs) or {}).get("points"),
        }
    return out


def replay_tags(
    base: List[dict],
    tags: List[str],
    by_tag: Dict[str, List[dict]],
    floor: float,
    *,
    mode: str = "day",
) -> Tuple[List[dict], Set[str]]:
    cur = list(base)
    used: Set[str] = set()
    if mode == "cap2":
        merge = lambda a, b: union_day_cap2(a, b, cap=2)
    elif mode == "day_side":
        merge = union_day_side
    else:
        merge = union_unique_days
    for tag in tags:
        rows = by_tag.get(tag)
        if not rows:
            continue
        if not stream_ok(rows, floor):
            continue
        merged = merge(cur, rows)
        if len(merged) <= len(cur):
            used.add(tag)
            continue
        if desk_ok(merged, floor):
            cur = merged
            used.add(tag)
    return cur, used


def cand_name(desk_tag: str, n: int, p2d_n: Optional[int], *, mode: str) -> str:
    if mode == "cap2":
        return f"{desk_tag}_CAP2_P2E"
    if mode == "day_side":
        return f"{desk_tag}_SIDES_P2E"
    if desk_tag == "ACC100_MULTI_V5":
        if p2d_n is not None and n > p2d_n:
            return "ACC100_MULTI_V10"
        if n > 216:
            return "ACC100_MULTI_V10"
        if n > 199:
            return "ACC100_MULTI_V9"
        return "ACC100_MULTI_V8"
    return f"{desk_tag}_P2E"


def main() -> None:
    t0 = time.time()
    print("PHASE-2e MORE CALLS @ same accuracy (P1 locked, P2c held, seed P2d)", flush=True)

    p2d = {}
    if P2D_RECIPES.exists():
        p2d = json.loads(P2D_RECIPES.read_text(encoding="utf-8")).get("candidates") or {}

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
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=path_u.get("crown_by_risk") or {},
        good_by_risk=path_u.get("good_by_risk") or {},
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active,
    )

    seed_tags: List[str] = []
    seen_seed: Set[str] = set()
    for meta in p2d.values():
        for t in meta.get("stream_tags_research") or []:
            if t not in seen_seed:
                seen_seed.add(t)
                seed_tags.append(t)
    print(f"  alt mine (≥75% 3y) + rebuild {len(seed_tags)} P2d seed tags…", flush=True)
    all_streams = mine(
        {
            "crown_by_risk": path_u.get("crown_by_risk") or {},
            "good_by_risk": path_u.get("good_by_risk") or {},
            "champ_native": champ_native,
        },
        gaps,
        active,
        dual15,
        dual5,
        proven,
        champ,
        floor_min=75.0,
        seed_tags=seed_tags,
    )
    by_tag = {t: rows for t, rows, _ in all_streams}
    perfect = [s for s in all_streams if s[2].get("perfect_3y")]

    results: Dict[str, Any] = {}
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
        held_meta = p2d.get(desk_tag) or {}
        seed_tags = list(held_meta.get("stream_tags_research") or [])
        p2d_n = (held_meta.get("research_3y") or {}).get("n")
        p2c_n = held_meta.get("phase2c_3y_n")

        seeded, used = replay_tags(base, seed_tags, by_tag, floor, mode="day")
        seed_sum = summarize(seeded)
        print(
            f"  {desk_tag} floor={floor:g}% P1={base_sum['3y']['n']} "
            f"seedP2d={seed_sum['3y']['n']} (ref={p2d_n}) pool={len(pool)}…",
            flush=True,
        )
        desk, added = greedy(
            seeded, pool, floor, mode="day", max_rounds=220, used_tags=used
        )
        got = summarize(desk)
        cand = None
        if got["3y"]["n"] > base_sum["3y"]["n"]:
            cand = cand_name(desk_tag, got["3y"]["n"], p2d_n, mode="day")
        results[desk_tag] = {
            "mode": "day",
            "floor": floor,
            "accuracy_range": meta["accuracy_range"],
            "phase1_3y": meta["research_3y"],
            "phase2c_3y_n": p2c_n,
            "phase2d_3y_n": p2d_n,
            "baseline": base_sum,
            "seeded": seed_sum,
            "result": got,
            "delta_vs_phase1_3y": got["3y"]["n"] - base_sum["3y"]["n"],
            "delta_vs_phase2d_3y": (got["3y"]["n"] - p2d_n) if p2d_n is not None else None,
            "added_streams_new": added,
            "candidate_tag": cand,
        }
        print(
            f"    → 3y {got['3y']['n']}@{got['3y']['hit_pct']}% "
            f"ΔP1={results[desk_tag]['delta_vs_phase1_3y']:+d} "
            f"ΔP2d={results[desk_tag]['delta_vs_phase2d_3y']} cand={cand}",
            flush=True,
        )

    for desk_tag, floor in CAP2_TARGETS:
        pool = perfect if floor >= 100.0 else [s for s in all_streams if stream_ok(s[1], floor)]
        base = list(phase1[desk_tag])
        held_key = f"{desk_tag}_CAP2"
        held_meta = p2d.get(held_key) or {}
        seed_tags = list(held_meta.get("stream_tags_research") or [])
        p2d_n = (held_meta.get("research_3y") or {}).get("n")
        seeded, used = replay_tags(base, seed_tags, by_tag, floor, mode="cap2")
        print(
            f"  {desk_tag} CAP2 floor={floor:g}% seed={summarize(seeded)['3y']['n']} (ref={p2d_n})…",
            flush=True,
        )
        desk, added = greedy(
            seeded, pool, floor, mode="cap2", max_rounds=180, used_tags=used
        )
        got = summarize(desk)
        key = f"{desk_tag}_CAP2"
        results[key] = {
            "mode": "cap2",
            "floor": floor,
            "phase2d_3y_n": p2d_n,
            "baseline": summarize(base),
            "seeded": summarize(seeded),
            "result": got,
            "delta_vs_phase1_3y": got["3y"]["n"] - summarize(base)["3y"]["n"],
            "delta_vs_phase2d_3y": (got["3y"]["n"] - p2d_n) if p2d_n is not None else None,
            "added_streams_new": added,
            "candidate_tag": cand_name(desk_tag, got["3y"]["n"], p2d_n, mode="cap2"),
        }
        print(
            f"    → 3y {got['3y']['n']}@{got['3y']['hit_pct']}% "
            f"ΔP1={results[key]['delta_vs_phase1_3y']:+d} "
            f"ΔP2d={results[key]['delta_vs_phase2d_3y']}",
            flush=True,
        )

    for desk_tag, floor in DAY_SIDE_TARGETS:
        pool = perfect if floor >= 100.0 else [s for s in all_streams if stream_ok(s[1], floor)]
        base = list(phase1[desk_tag])
        held_meta = p2d.get(desk_tag) or {}
        seed_tags = list(held_meta.get("stream_tags_research") or [])
        seeded, used = replay_tags(base, seed_tags, by_tag, floor, mode="day_side")
        print(
            f"  {desk_tag} DAY_SIDE floor={floor:g}% seed={summarize(seeded)['3y']['n']}…",
            flush=True,
        )
        desk, added = greedy(
            seeded, pool, floor, mode="day_side", max_rounds=160, used_tags=used
        )
        got = summarize(desk)
        key = f"{desk_tag}_SIDES"
        results[key] = {
            "mode": "day_side",
            "floor": floor,
            "baseline": summarize(base),
            "seeded": summarize(seeded),
            "result": got,
            "delta_vs_phase1_3y": got["3y"]["n"] - summarize(base)["3y"]["n"],
            "added_streams_new": added,
            "candidate_tag": cand_name(desk_tag, got["3y"]["n"], None, mode="day_side"),
        }
        print(
            f"    → 3y {got['3y']['n']}@{got['3y']['hit_pct']}% "
            f"ΔP1={results[key]['delta_vs_phase1_3y']:+d}",
            flush=True,
        )

    payload = {
        "phase": "2e",
        "phase1_held": True,
        "phase2c_held": True,
        "phase2d_seed": True,
        "holding_folder": "prod_live/holding_accurate/",
        "note": "More calls — P1 locked, P2c held; alt mine from P2d seeds",
        "window_end": END,
        "streams_mined": len(all_streams),
        "perfect_streams": len(perfect),
        "results": results,
        "elapsed_s": round(time.time() - t0, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ACC_PHASE2E_MORE_CALLS.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (LEDGER / "ACC_PHASE2E_MORE_CALLS.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (HOLD / "reports").mkdir(parents=True, exist_ok=True)
    (HOLD / "reports" / "ACC_PHASE2E_MORE_CALLS.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Phase-2e — more calls @ same accuracy",
        "",
        "**Phase-1 LOCKED · Phase-2c HELD.** Seeds from Phase-2d research.",
        "New axes: last/second picks · cross-CF · day_side · more cap2.",
        "",
        f"Mined ≥75%: {len(all_streams)} · perfect-3y: {len(perfect)} · "
        f"elapsed {payload['elapsed_s']}s",
        "",
        "## Day-dedupe",
        "",
        "| Desk | Floor | P1 | P2d | **P2e** | ΔP1 | ΔP2d | Hit | Candidate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for desk_tag in EXPAND_TARGETS:
        r = results[desk_tag]
        b, g = r["baseline"]["3y"], r["result"]["3y"]
        p2dn = r.get("phase2d_3y_n")
        d2d = r.get("delta_vs_phase2d_3y")
        d2d_s = "—" if d2d is None else (f"+{d2d}" if d2d >= 0 else str(d2d))
        lines.append(
            f"| `{desk_tag}` | {r['floor']:g} | {b['n']} | {p2dn if p2dn is not None else '—'} | "
            f"**{g['n']}** | {r['delta_vs_phase1_3y']:+d} | {d2d_s} | {g['hit_pct']} | "
            f"`{r['candidate_tag'] or '—'}` |"
        )

    lines += ["", "## Cap2 @ same accuracy", ""]
    lines += [
        "| Desk | Floor | P1 | P2d | Cap2 P2e | ΔP1 | ΔP2d | Hit | Candidate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for key in (k for k in results if k.endswith("_CAP2")):
        r = results[key]
        b, g = r["baseline"]["3y"], r["result"]["3y"]
        p2dn = r.get("phase2d_3y_n")
        d2d = r.get("delta_vs_phase2d_3y")
        d2d_s = "—" if d2d is None else (f"+{d2d}" if d2d >= 0 else str(d2d))
        lines.append(
            f"| `{key}` | {r['floor']:g} | {b['n']} | {p2dn if p2dn is not None else '—'} | "
            f"**{g['n']}** | {r['delta_vs_phase1_3y']:+d} | {d2d_s} | {g['hit_pct']} | "
            f"`{r['candidate_tag']}` |"
        )

    lines += ["", "## Day-side @ same accuracy", ""]
    lines += [
        "| Desk | Floor | P1 | DaySide P2e | ΔP1 | Hit | Candidate |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for key in (k for k in results if k.endswith("_SIDES")):
        r = results[key]
        b, g = r["baseline"]["3y"], r["result"]["3y"]
        lines.append(
            f"| `{key}` | {r['floor']:g} | {b['n']} | **{g['n']}** | "
            f"{r['delta_vs_phase1_3y']:+d} | {g['hit_pct']} | `{r['candidate_tag']}` |"
        )

    lines += ["", "## New streams beyond P2d seed (day)", ""]
    for desk_tag in EXPAND_TARGETS:
        r = results[desk_tag]
        lines.append(f"### `{desk_tag}`")
        lines.append("")
        if not r["added_streams_new"]:
            lines.append("_No new streams beyond P2d seed (or seed already maxed)._")
        else:
            lines += ["| # | Tag | + | Desk3y | Hit |", "|---:|---|---:|---:|---:|"]
            for i, a in enumerate(r["added_streams_new"][:40], 1):
                lines.append(
                    f"| {i} | `{a['tag']}` | +{a['new_n']} | {a['desk_n_3y']} | {a['desk_hit_3y']} |"
                )
        lines.append("")

    lines += [
        "## Hold",
        "",
        "Phase-1 locked · Phase-2c held · P2d/P2e = research candidates.",
        "",
        "JSON: `ACC_PHASE2E_MORE_CALLS.json`",
        "",
    ]
    text = "\n".join(lines)
    md = OUT / "ACC_PHASE2E_MORE_CALLS.md"
    md.write_text(text, encoding="utf-8")
    (LEDGER / "ACC_PHASE2E_MORE_CALLS.md").write_text(text, encoding="utf-8")
    (HOLD / "reports" / "ACC_PHASE2E_MORE_CALLS.md").write_text(text, encoding="utf-8")
    print("Wrote", md, flush=True)


if __name__ == "__main__":
    main()
