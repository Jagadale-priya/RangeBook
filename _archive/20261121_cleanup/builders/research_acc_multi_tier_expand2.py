"""Hold V1–V4 + P92/P90/P85; hunt MORE calls same way.

Phases:
  A) denser stream mine (≥75% 3y)
  B) greedy more onto P85 at 85% floor
  C) ladder 80 / 75 (day-dedupe)
  D) parallel volume modes: day+side dedupe, day-cap2

  python -u prod_live/tests/builders/research_acc_multi_tier_expand2.py
"""
from __future__ import annotations

import json
import re
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
from prod_live.logic.acc100_streams import (  # noqa: E402
    merge_acc100_multi_v4,
    merge_acc_wide_p85,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL_10Y = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH_10Y = LEDGER / "_cache_path_trusted_10y.json"

END = "2026-11-13"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_5Y = (pd.Timestamp(END) - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
MIN_N = 4
FLOORS = (100.0, 85.0, 80.0, 75.0)


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 4)


def meets_floor(rows: List[dict], floor: float, *, start: str) -> bool:
    rs = _clip(rows, start, END)
    if len(rs) < MIN_N:
        return True
    if floor >= 100.0:
        return is_perfect(rs)
    return hit_pct(rs) + 1e-9 >= floor


def desk_ok(rows: List[dict], floor: float) -> bool:
    if not meets_floor(rows, floor, start=START_3Y):
        return False
    soft = floor if floor >= 100.0 else max(floor - 2.0, 70.0)
    if not meets_floor(rows, soft, start=START_5Y):
        return False
    if not meets_floor(rows, soft, start=START_1Y):
        return False
    return True


def stream_ok(rows: List[dict], floor: float) -> bool:
    rs3 = _clip(rows, START_3Y, END)
    if len(rs3) < MIN_N:
        return False
    if floor >= 100.0:
        if not is_perfect(rs3):
            return False
        return meets_floor(rows, 100.0, start=START_5Y) and meets_floor(
            rows, 100.0, start=START_1Y
        )
    if hit_pct(rs3) + 1e-9 < floor:
        return False
    rs5 = _clip(rows, START_5Y, END)
    if len(rs5) >= MIN_N and hit_pct(rs5) + 1e-9 < max(floor - 2.0, 70.0):
        return False
    return True


BANDS = [
    ("first45", 9 * 60 + 15, 10 * 60),
    ("open", 9 * 60 + 15, 10 * 60 + 30),
    ("am11", 9 * 60 + 15, 11 * 60),
    ("am1130", 9 * 60 + 15, 11 * 60 + 30),
    ("am1230", 9 * 60 + 15, 12 * 60 + 30),
    ("mid", 10 * 60, 13 * 60),
    ("latemid", 10 * 60 + 30, 14 * 60),
    ("earlypm", 11 * 60 + 30, 14 * 60),
    ("pm", 12 * 60 + 30, 15 * 60 + 15),
    ("last90", 13 * 60 + 45, 15 * 60 + 15),
    ("all", None, None),
]
GAPS = [
    ("nogap", None, False, False),
    ("g030", 0.30, False, False),
    ("g035", 0.35, False, False),
    ("g040", 0.40, False, False),
    ("g045", 0.45, False, False),
    ("g050", 0.50, False, False),
    ("g055", 0.55, False, False),
    ("g065", 0.65, False, False),
    ("gdn030", 0.30, True, False),
    ("gdn040", 0.40, True, False),
    ("gdn055", 0.55, True, False),
    ("gup030", 0.30, False, True),
    ("gup040", 0.40, False, True),
    ("gup055", 0.55, False, True),
]
PMINS = (
    0.0,
    0.50,
    0.52,
    0.55,
    0.57,
    0.58,
    0.60,
    0.62,
    0.65,
    0.68,
    0.70,
    0.72,
    0.75,
    0.78,
    0.80,
    0.85,
    0.90,
)


def union_day_side(base: List[dict], extra: List[dict]) -> List[dict]:
    keys = {(str(r.get("day") or ""), _side(r)) for r in base}
    out = list(base)
    for r in extra:
        k = (str(r.get("day") or ""), _side(r))
        if k in keys:
            continue
        out.append(dict(r))
        keys.add(k)
    return out


def union_day_cap2(base: List[dict], extra: List[dict], *, cap: int = 2) -> List[dict]:
    """Allow up to `cap` calls/day (prefer earlier hm then higher p)."""
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in base:
        by[str(r.get("day") or "")].append(dict(r))
    for r in extra:
        day = str(r.get("day") or "")
        cur = by[day]
        # skip exact hm+side dup
        sig = (_side(r), str(r.get("hm") or ""))
        if any((_side(x), str(x.get("hm") or "")) == sig for x in cur):
            continue
        cur.append(dict(r))
        cur.sort(
            key=lambda x: (_hm_mins(str(x.get("hm") or "99:99")), -float(x.get("p_t1") or 0))
        )
        by[day] = cur[:cap]
    out: List[dict] = []
    for day in sorted(by):
        out.extend(by[day])
    return out


def mine_all(
    path_u: dict,
    gaps: dict,
    active: set,
    dual15,
    dual5,
    proven,
    champ,
    *,
    floor_min: float = 75.0,
) -> List[Tuple[str, List[dict], Dict[str, Any]]]:
    streams: List[Tuple[str, List[dict]]] = []
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
    # dual15 any as extra universe
    universes["D15"] = dual15

    n_eval = 0
    for uname, urows in universes.items():
        for side in (None, "BUY", "SELL"):
            for blab, lo, hi in BANDS:
                for glab, gabsm, gdn, gup in GAPS:
                    for use_htf in (False, True):
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
                                ("raw", base),
                                ("first", first_day(base)),
                                ("bestp", bestp_day(base)),
                            ):
                                n_eval += 1
                                rs3 = _clip(vrows, START_3Y, END)
                                if len(rs3) < MIN_N:
                                    continue
                                if hit_pct(rs3) + 1e-9 < floor_min:
                                    continue
                                tag = (
                                    f"{uname}_{side or 'BOTH'}_p{int(round(pmin * 100))}_{blab}_"
                                    f"{'htf' if use_htf else 'any'}_{glab}_{vlab}"
                                )
                                streams.append((tag, vrows))

    ix15 = _ix(dual15)
    ix15p = _ix(proven)
    ix5 = _ix(dual5)
    ix_ch = _ix(path_u.get("champ_native") or champ)
    for tol in (5, 10, 15, 20, 25, 30, 40, 45, 60, 90):
        for tag, rows in (
            (f"CF_T{tol}_any15_d5", time_agree(ix15, ix5, tol=tol, tag="cf")),
            (f"CF_T{tol}_p15_d5", time_agree(ix15p, ix5, tol=tol, tag="cf")),
            (f"CF_T{tol}_any15_ch", time_agree(ix15, ix_ch, tol=tol, tag="cf")),
            (f"CF_T{tol}_ch_d5", time_agree(ix_ch, ix5, tol=tol, tag="cf")),
        ):
            rs3 = _clip(rows, START_3Y, END)
            if len(rs3) >= MIN_N and hit_pct(rs3) + 1e-9 >= floor_min:
                streams.append((tag, rows))
        for rk, crow in (path_u.get("crown_by_risk") or {}).items():
            if str(rk).startswith("_"):
                continue
            for tag, rows in (
                (
                    f"CF_T{tol}_any15_cr{str(rk).replace('.0', '')}",
                    time_agree(ix15, _ix(crow), tol=tol, tag="cf"),
                ),
                (
                    f"CF_T{tol}_d5_cr{str(rk).replace('.0', '')}",
                    time_agree(ix5, _ix(crow), tol=tol, tag="cf"),
                ),
            ):
                rs3 = _clip(rows, START_3Y, END)
                if len(rs3) >= MIN_N and hit_pct(rs3) + 1e-9 >= floor_min:
                    streams.append((tag, rows))

    by_sig: Dict[tuple, Tuple[str, List[dict], Dict[str, Any]]] = {}
    for tag, rows in streams:
        sig = tuple(
            sorted((str(r["day"]), _side(r), str(r.get("hm") or "")) for r in rows)
        )
        rs3 = _clip(rows, START_3Y, END)
        st = {
            "n_3y": len(rs3),
            "hit_3y": hit_pct(rs3),
            "n_5y": len(_clip(rows, START_5Y, END)),
            "hit_5y": hit_pct(_clip(rows, START_5Y, END)),
            "perfect_3y": is_perfect(rs3) if rs3 else False,
        }
        prev = by_sig.get(sig)
        if prev is None or st["n_3y"] > prev[2]["n_3y"] or (
            st["n_3y"] == prev[2]["n_3y"] and st["hit_3y"] > prev[2]["hit_3y"]
        ):
            by_sig[sig] = (tag, rows, st)
    out = list(by_sig.values())
    out.sort(key=lambda x: (x[2]["hit_3y"], x[2]["n_3y"]), reverse=True)
    print(f"  mined eval≈{n_eval} → unique={len(out)} (≥{floor_min}% 3y)", flush=True)
    return out


def greedy(
    base: List[dict],
    streams: List[Tuple[str, List[dict], Dict[str, Any]]],
    floor: float,
    *,
    mode: str = "day",
    max_rounds: int = 120,
) -> Tuple[List[dict], List[dict]]:
    cur = list(base)
    added: List[dict] = []
    improved = True
    rounds = 0

    def merge(a, b):
        if mode == "day_side":
            return union_day_side(a, b)
        if mode == "cap2":
            return union_day_cap2(a, b, cap=2)
        return union_unique_days(a, b)

    def occupied(rows: List[dict]):
        if mode == "day_side":
            return {(str(r.get("day") or ""), _side(r)) for r in rows}
        if mode == "cap2":
            # count per day
            c: Dict[str, int] = defaultdict(int)
            for r in rows:
                c[str(r.get("day") or "")] += 1
            return c
        return {str(r.get("day") or "") for r in rows}

    while improved and rounds < max_rounds:
        improved = False
        rounds += 1
        occ = occupied(cur)
        ranked = []
        for tag, rows, st in streams:
            if not stream_ok(rows, floor):
                continue
            if mode == "day":
                new_n = sum(1 for r in rows if str(r["day"]) not in occ)
            elif mode == "day_side":
                new_n = sum(
                    1
                    for r in rows
                    if (str(r.get("day") or ""), _side(r)) not in occ
                )
            else:  # cap2
                new_n = 0
                for r in rows:
                    day = str(r.get("day") or "")
                    if occ.get(day, 0) < 2:
                        # rough: count if day has room
                        new_n += 1
                # tighter: simulate
                trial = merge(cur, rows)
                new_n = len(trial) - len(cur)
            if new_n > 0:
                ranked.append((new_n, st.get("hit_3y") or 0, tag, rows))
        ranked.sort(reverse=True)
        for new_n, _h, tag, rows in ranked[:80]:  # try top candidates
            merged = merge(cur, rows)
            if len(merged) <= len(cur):
                continue
            if not desk_ok(merged, floor):
                continue
            delta_n = len(merged) - len(cur)
            cur = merged
            d3 = _clip(cur, START_3Y, END)
            added.append(
                {
                    "tag": tag,
                    "new_n": delta_n,
                    "desk_n": len(cur),
                    "desk_n_3y": len(d3),
                    "desk_hit_3y": hit_pct(d3),
                    "stream_n": len(rows),
                }
            )
            print(
                f"    [{floor:g}%/{mode}] +{delta_n} {tag} → desk3y={len(d3)}@{hit_pct(d3):.1f}%",
                flush=True,
            )
            improved = True
            break
    return cur, added


def parse_recipe(tag: str) -> Optional[Dict[str, Any]]:
    m = re.match(
        r"^(CR|GD|CH|D5|PR|D15)(\d*)_(BUY|SELL|BOTH)_p(\d+)_(.+?)_(htf|any)_(.+?)_(raw|first|bestp)$",
        tag,
    )
    if not m:
        return {"source_tag": tag, "channel": "confirm_or_complex", "raw": True}
    ch_raw, risk_s, side, p_s, blab, htf, glab, pick = m.groups()
    channel = {
        "CR": "crown",
        "GD": "good",
        "CH": "champ",
        "D5": "dual5",
        "PR": "proven",
        "D15": "dual15",
    }[ch_raw]
    band = {b[0]: (b[1], b[2]) for b in BANDS}
    lo, hi = band.get(blab, (None, None))
    recipe: Dict[str, Any] = {
        "tag": f"ACC_WIDE_{tag}",
        "source_tag": tag,
        "channel": channel,
        "risk": float(risk_s) if risk_s else None,
        "side": None if side == "BOTH" else side,
        "p_min": int(p_s) / 100.0,
        "hm_lo": lo,
        "hm_hi": hi,
        "htf": htf == "htf",
        "pick": pick,
    }
    if glab.startswith("gdn") and glab[3:].isdigit():
        recipe["gap_dn"] = int(glab[3:]) / 100.0
    elif glab.startswith("gup") and glab[3:].isdigit():
        recipe["gap_up"] = int(glab[3:]) / 100.0
    elif glab.startswith("g") and glab[1:].isdigit():
        recipe["gap_abs"] = int(glab[1:]) / 100.0
    return recipe


def summarize(desk: List[dict]) -> Dict[str, Any]:
    d3 = _clip(desk, START_3Y, END)
    d5 = _clip(desk, START_5Y, END)
    d1 = _clip(desk, START_1Y, END)
    return {
        "n_3y": len(d3),
        "hit_3y": hit_pct(d3),
        "perfect_3y": is_perfect(d3) if d3 else False,
        "points_3y": _agg(d3).get("points"),
        "n_5y": len(d5),
        "hit_5y": hit_pct(d5),
        "perfect_5y": is_perfect(d5) if d5 else False,
        "points_5y": _agg(d5).get("points"),
        "n_1y": len(d1),
        "hit_1y": hit_pct(d1),
    }


def main() -> None:
    t0 = time.time()
    print("EXPAND2 — more calls beyond held P85 (keep all prior desks)", flush=True)

    dual = json.loads(CACHE_DUAL_10Y.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH_10Y.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_5Y < d <= END]
    active = fs._active_days(sess, fs._load_daily())

    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ = _champ_floor([dict(r, track="champion") for r in dual["dual15"]["champion"]])
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]
    crown_by_risk = path_u.get("crown_by_risk") or {}
    good_by_risk = path_u.get("good_by_risk") or {}
    champ_native = path_u.get("champ_native") or champ

    kw = dict(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active,
    )

    print("  rebuild V4 + P85…", flush=True)
    v4 = merge_acc100_multi_v4(**kw)
    p85 = merge_acc_wide_p85(**kw)
    v4s, p85s = summarize(v4), summarize(p85)
    print(f"  V4  3y={v4s['n_3y']}@{v4s['hit_3y']}%", flush=True)
    print(f"  P85 3y={p85s['n_3y']}@{p85s['hit_3y']}%", flush=True)

    print("  mining denser streams (≥75% 3y)…", flush=True)
    path_bundle = {
        "crown_by_risk": crown_by_risk,
        "good_by_risk": good_by_risk,
        "champ_native": champ_native,
    }
    all_streams = mine_all(
        path_bundle, gaps, active, dual15, dual5, proven, champ, floor_min=75.0
    )
    perfect = [s for s in all_streams if s[2].get("perfect_3y")]
    print(f"  perfect-3y={len(perfect)}", flush=True)

    tiers: Dict[str, Any] = {}

    # more 100% onto V4
    print("  greedy 100% onto V4…", flush=True)
    d100, a100 = greedy(v4, perfect, 100.0, mode="day", max_rounds=60)
    tiers["100"] = {
        "desk_tag": "ACC100_MULTI_V5" if summarize(d100)["n_3y"] > v4s["n_3y"] else "ACC100_MULTI_V4",
        "mode": "day",
        "floor": 100.0,
        "result": summarize(d100),
        "delta_vs_p85_3y": summarize(d100)["n_3y"] - p85s["n_3y"],
        "delta_vs_v4_3y": summarize(d100)["n_3y"] - v4s["n_3y"],
        "added_streams": a100,
        "recipes": [parse_recipe(a["tag"]) for a in a100],
    }

    # more at 85 onto P85
    print("  greedy more @85% onto P85 (day)…", flush=True)
    el85 = [s for s in all_streams if stream_ok(s[1], 85.0)]
    d85, a85 = greedy(p85, el85, 85.0, mode="day", max_rounds=120)
    tiers["85_more"] = {
        "desk_tag": "ACC_WIDE_P85B",
        "mode": "day",
        "floor": 85.0,
        "result": summarize(d85),
        "delta_vs_p85_3y": summarize(d85)["n_3y"] - p85s["n_3y"],
        "added_streams": a85,
        "recipes": [parse_recipe(a["tag"]) for a in a85],
        "streams_eligible": len(el85),
    }

    prev = d85
    for floor in (80.0, 75.0):
        key = str(int(floor))
        print(f"  greedy {floor:g}% day onto prior…", flush=True)
        el = [s for s in all_streams if stream_ok(s[1], floor)]
        desk, added = greedy(prev, el, floor, mode="day", max_rounds=120)
        tiers[key] = {
            "desk_tag": f"ACC_WIDE_P{key}",
            "mode": "day",
            "floor": floor,
            "result": summarize(desk),
            "delta_vs_p85_3y": summarize(desk)["n_3y"] - p85s["n_3y"],
            "added_streams": added,
            "recipes": [parse_recipe(a["tag"]) for a in added],
            "streams_eligible": len(el),
        }
        prev = desk

    # volume modes from P85
    for mode, tag, floor in (
        ("day_side", "ACC_WIDE_P85_SIDES", 85.0),
        ("cap2", "ACC_WIDE_P80_CAP2", 80.0),
        ("cap2", "ACC_WIDE_P75_CAP2", 75.0),
    ):
        print(f"  greedy {floor:g}% mode={mode} from P85…", flush=True)
        el = [s for s in all_streams if stream_ok(s[1], floor)]
        desk, added = greedy(p85, el, floor, mode=mode, max_rounds=100)
        tiers[f"{int(floor)}_{mode}"] = {
            "desk_tag": tag,
            "mode": mode,
            "floor": floor,
            "result": summarize(desk),
            "delta_vs_p85_3y": summarize(desk)["n_3y"] - p85s["n_3y"],
            "added_streams": added,
            "recipes": [parse_recipe(a["tag"]) for a in added],
        }

    payload = {
        "keep_held": [
            "ACC100_MULTI_V1",
            "ACC100_MULTI_V2",
            "ACC100_MULTI_V3",
            "ACC100_MULTI_V4",
            "ACC_WIDE_P92",
            "ACC_WIDE_P90",
            "ACC_WIDE_P85",
        ],
        "baselines": {"v4": v4s, "p85": p85s},
        "streams_mined": len(all_streams),
        "perfect_streams": len(perfect),
        "tiers": tiers,
        "elapsed_s": round(time.time() - t0, 1),
        "note": "HOLDING — filter later; not live",
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ACC_MULTI_TIER_EXPAND2.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (LEDGER / "ACC_MULTI_TIER_EXPAND2.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Multi-tier expand 2 (more calls beyond P85)",
        "",
        "Keep held V1–V4 + P92/P90/P85. Hunt more volume same way.",
        "",
        f"Baselines: V4 **{v4s['n_3y']}** @ {v4s['hit_3y']}% · "
        f"P85 **{p85s['n_3y']}** @ {p85s['hit_3y']}%",
        "",
        f"Mined ≥75%: {len(all_streams)} · perfect-3y: {len(perfect)} · "
        f"elapsed {payload['elapsed_s']}s",
        "",
        "## Desk ladder",
        "",
        "| Desk | Mode | Floor | 3y N | 3y Hit | 5y N | 5y Hit | Δ vs P85 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
        f"| `ACC_WIDE_P85` | day | 85 | {p85s['n_3y']} | {p85s['hit_3y']} | "
        f"{p85s['n_5y']} | {p85s['hit_5y']} | 0 |",
    ]
    for k, t in tiers.items():
        r = t["result"]
        lines.append(
            f"| `{t['desk_tag']}` | {t['mode']} | {t['floor']:g} | {r['n_3y']} | "
            f"{r['hit_3y']} | {r['n_5y']} | {r['hit_5y']} | {t['delta_vs_p85_3y']:+d} |"
        )

    lines += ["", "## Added streams", ""]
    for k, t in tiers.items():
        lines.append(f"### `{t['desk_tag']}`")
        lines.append("")
        if not t["added_streams"]:
            lines.append("_No new stream._")
        else:
            lines += ["| # | Tag | + | Desk3y | Hit3y |", "|---:|---|---:|---:|---:|"]
            for i, a in enumerate(t["added_streams"], 1):
                lines.append(
                    f"| {i} | `{a['tag']}` | +{a['new_n']} | {a.get('desk_n_3y')} | "
                    f"{a.get('desk_hit_3y')} |"
                )
        lines.append("")

    lines += [
        "## Verdict",
        "",
        "- Keep all prior desks.",
        "- Hold any new desks that grow n at target floors.",
        "",
        "JSON: `ACC_MULTI_TIER_EXPAND2.json`",
        "",
    ]
    md = OUT / "ACC_MULTI_TIER_EXPAND2.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (LEDGER / "ACC_MULTI_TIER_EXPAND2.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", md, flush=True)
    print(json.dumps({k: tiers[k]["result"] for k in tiers}, indent=2), flush=True)


if __name__ == "__main__":
    main()
