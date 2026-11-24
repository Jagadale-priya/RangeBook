"""LONG hunt for additional 100% accuracy call books.

Held already:
  - PROVEN_100 (prod)
  - CONFIRM_DUAL15_DUAL5_TIME30 / PROVEN15_PLUS_CONFIRM_T30

This script searches hard for MORE perfect (100%) books:
  channel alone + p/time/side/HTF/gap gates, 2-way intersects,
  stack hygiene subsets, confirm-style clocks, morning bands.

Takes longer by design (broad grid). Research only.

  python -u prod_live/tests/builders/research_hunt_100pct_long.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import timedelta
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import POOL, PRIORITY, _agg, _champ_floor, _union  # noqa: E402
from research_confirm_dual_tf_deep import (  # noqa: E402
    _clip,
    _hm_mins,
    _ix,
    _pack,
    _side,
    _side_days,
)
from prod_live.logic.confirm_dual_tf import (  # noqa: E402
    build_confirm_rows,
    merge_proven15_plus_confirm,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = ROOT / "stock_signal_data/fno_validate/research/_cache_dual15_dual5_confirm.json"
DAILY = ROOT / "stock_signal_data/fno_validate/NIFTY_daily_nse.csv"
GATED = ROOT / "analysis/nifty_5m_buy_20pt_1y/gated_both_calls.csv"

END = "2026-11-13"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_NOV = "2026-11-01"
MIN_N_PERFECT = 8
MIN_N_REPORT = 5


def _best_p(rows: List[dict]) -> Optional[dict]:
    if not rows:
        return None
    return max(rows, key=lambda x: float(x.get("p_t1") or 0))


def time_agree(
    gate_ix: Dict[Tuple[str, str], List[dict]],
    entry_ix: Dict[Tuple[str, str], List[dict]],
    *,
    tol: int,
    tag: str,
) -> List[dict]:
    out: List[dict] = []
    for (day, side), grows in gate_ix.items():
        frows = entry_ix.get((day, side)) or []
        if not frows:
            continue
        picked = None
        agree_hm = None
        for g in sorted(grows, key=lambda x: _hm_mins(str(x.get("hm") or "99:99"))):
            gm = _hm_mins(str(g.get("hm") or "12:00"))
            near = [
                f
                for f in frows
                if abs(gm - _hm_mins(str(f.get("hm") or "12:00"))) <= tol
            ]
            if not near:
                continue
            picked = dict(_best_p(near))
            agree_hm = g.get("hm")
            break
        if picked is None:
            continue
        picked.update({"track": tag, "agree_hm": agree_hm, "src": "entry"})
        out.append(picked)
    return out


def day_side_keep(entry: List[dict], gate_sides: Dict[str, Set[str]], tag: str) -> List[dict]:
    out = []
    for r in entry:
        if _side(r) in gate_sides.get(str(r["day"]), set()):
            out.append(dict(r, track=tag))
    return out


def load_gap_map() -> Dict[str, float]:
    """gap% = (open - prior_close)/prior_close*100 keyed by day."""
    if not DAILY.is_file():
        return {}
    df = pd.read_csv(DAILY)
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values("Date")
    # need Open + prior Close
    cols = {c.lower(): c for c in df.columns}
    ocol = cols.get("open") or cols.get("openprice")
    ccol = cols.get("close") or cols.get("closeprice")
    if not ocol or not ccol:
        return {}
    closes = df[ccol].astype(float).tolist()
    opens = df[ocol].astype(float).tolist()
    days = df["Date"].tolist()
    out = {}
    for i in range(1, len(days)):
        pc = closes[i - 1]
        if pc <= 0:
            continue
        out[days[i]] = (opens[i] - pc) / pc * 100.0
    return out


def load_gated() -> List[dict]:
    if not GATED.is_file():
        return []
    df = pd.read_csv(GATED)
    rows = []
    for _, r in df.iterrows():
        day = str(r.get("day") or "")[:10]
        side = str(r.get("side") or "").upper()
        decision = "BUY" if side.startswith("B") else "SELL"
        rows.append(
            {
                "day": day,
                "hm": str(r.get("time") or r.get("hm") or "")[:5],
                "decision": decision,
                "track": "gated_both",
                "p_t1": float(r.get("p_t1") or 0.55),
                "win": bool(int(r["win"])) if str(r.get("win")).strip() not in ("", "nan") else bool(r.get("win")),
                "points": float(r.get("points") or 0),
            }
        )
    return rows


def filt(
    rows: List[dict],
    *,
    p_min: float = 0.0,
    side: Optional[str] = None,
    hm_lo: Optional[int] = None,
    hm_hi: Optional[int] = None,
    htf: Optional[Set[str]] = None,
    gap_map: Optional[Dict[str, float]] = None,
    gap_abs_min: Optional[float] = None,
    gap_down: bool = False,
    gap_up: bool = False,
    days_allow: Optional[Set[str]] = None,
) -> List[dict]:
    out = []
    for r in rows:
        day = str(r.get("day") or "")
        if days_allow is not None and day not in days_allow:
            continue
        s = _side(r)
        if side and s != side:
            continue
        if float(r.get("p_t1") or 0) < p_min:
            continue
        hm = _hm_mins(str(r.get("hm") or "12:00"))
        if hm_lo is not None and hm < hm_lo:
            continue
        if hm_hi is not None and hm > hm_hi:
            continue
        if htf is not None and day not in htf:
            continue
        if gap_map is not None and (gap_abs_min is not None or gap_down or gap_up):
            g = gap_map.get(day)
            if g is None:
                continue
            if gap_abs_min is not None and abs(g) < gap_abs_min:
                continue
            if gap_down and g >= 0:
                continue
            if gap_up and g <= 0:
                continue
        out.append(dict(r))
    return out


def first_per_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r["day"])].append(r)
    out = []
    for day in sorted(by):
        best = sorted(
            by[day],
            key=lambda x: (_hm_mins(str(x.get("hm") or "99:99")), -float(x.get("p_t1") or 0)),
        )[0]
        out.append(best)
    return out


def best_p_per_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r["day"])].append(r)
    return [_best_p(rs) for rs in by.values() if _best_p(rs)]


def is_perfect(rows: List[dict]) -> bool:
    return bool(rows) and all(bool(r.get("win")) for r in rows)


def register(
    books: Dict[str, List[dict]],
    name: str,
    rows: List[dict],
    *,
    seen: Set[str],
) -> None:
    if name in seen:
        return
    # skip empty / tiny later
    books[name] = rows
    seen.add(name)


def main() -> None:
    t0 = time.time()
    print("LONG 100% accuracy hunt (held confirm locked)", flush=True)

    cached = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    dual15 = cached["dual15"]
    dual5 = cached["dual5"]
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    sessions_all, prod2_all, _ = fs._prod2(1400)
    sess = [d for d in sessions_all if START_3Y < d <= END]
    daily = fs._load_daily()
    active = fs._active_days(sess, daily)
    gap_map = load_gap_map()
    print(f"  sessions={len(sess)} active={len(active)} gap_days={len(gap_map)}", flush=True)

    proven = [dict(r, track="proven_100") for r in dual15["proven_100"]]
    # also pool proven for longer hist overlap
    pool_proven = [dict(r, track="proven_100") for r in pool["proven_100"]]
    champ = _champ_floor([dict(r, track="champion") for r in dual15["champion"]])
    pool_champ = _champ_floor([dict(r, track="champion") for r in pool["champion"]])
    good = [dict(r, track="good_prod2") for r in prod2_all]
    crown_all = [dict(r, track="crown_5m") for r in pool["crown_5m"]]
    crown_htf = [r for r in crown_all if r["day"] in active]
    d5_any = [dict(r) for r in dual5["proven_100"] + dual5["champion"]]
    d5_champ = [dict(r) for r in dual5["champion"]]
    d5_proven = [dict(r) for r in dual5["proven_100"]]
    gated = load_gated()
    print(
        f"  proven={len(proven)} champ={len(champ)} good={len(good)} "
        f"crown_htf={len(crown_htf)} dual5={len(d5_any)} gated={len(gated)}",
        flush=True,
    )

    # held confirm rebuild
    confirm = build_confirm_rows(
        dual15["proven_100"] + dual15["champion"],
        dual5["proven_100"] + dual5["champion"],
        tol_min=30,
    )
    plus = merge_proven15_plus_confirm(proven, confirm)

    books: Dict[str, List[dict]] = {}
    seen: Set[str] = set()
    register(books, "HELD_proven_100", proven, seen=seen)
    register(books, "HELD_CONFIRM_T30", confirm, seen=seen)
    register(books, "HELD_PROVEN15_PLUS_CONFIRM_T30", plus, seen=seen)

    bases: Dict[str, List[dict]] = {
        "proven": proven,
        "pool_proven": _clip(pool_proven, START_3Y, END),
        "champ": champ,
        "pool_champ": _clip(pool_champ, START_3Y, END),
        "good": _clip(good, START_3Y, END),
        "crown_htf": _clip(crown_htf, START_3Y, END),
        "crown_all": _clip(crown_all, START_3Y, END),
        "dual5_any": d5_any,
        "dual5_champ": d5_champ,
        "dual5_proven": d5_proven,
        "gated": _clip(gated, START_3Y, END),
    }

    # stack for hygiene
    stack = fs._union(
        {
            "proven_100": proven,
            "good_prod2": _clip(good, START_3Y, END),
            "champion": champ,
            "crown_5m": _clip(crown_htf, START_3Y, END),
        },
        day_cap=2,
    )
    bases["stack"] = stack

    print("  phase A: single-channel gate grids…", flush=True)
    p_grid = [0.0, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70, 0.75, 0.80, 0.85, 0.90]
    time_bands = [
        (None, None, "allday"),
        (9 * 60 + 15, 10 * 60 + 30, "open_1030"),
        (9 * 60 + 15, 11 * 60 + 30, "am1130"),
        (9 * 60 + 15, 12 * 60 + 30, "am1230"),
        (10 * 60, 14 * 60, "mid"),
        (12 * 60 + 30, 15 * 60 + 15, "pm"),
        (9 * 60 + 15, 10 * 60, "first45"),
    ]
    gap_opts = [
        (None, False, False, "nogap"),
        (0.40, False, False, "gap040"),
        (0.55, False, False, "gap055"),
        (0.70, False, False, "gap070"),
        (0.55, True, False, "gapdn055"),
        (0.55, False, True, "gapup055"),
    ]

    n_a = 0
    for bname, brows in bases.items():
        for side in (None, "BUY", "SELL"):
            for pmin in p_grid:
                for hm_lo, hm_hi, tlab in time_bands:
                    for use_htf in (False, True):
                        for gabsm, gdn, gup, glab in gap_opts:
                            # prune absurd combos early
                            if bname in ("proven", "pool_proven") and pmin > 0.62:
                                continue
                            if bname.startswith("dual5") and use_htf:
                                continue
                            rows = filt(
                                brows,
                                p_min=pmin,
                                side=side,
                                hm_lo=hm_lo,
                                hm_hi=hm_hi,
                                htf=active if use_htf else None,
                                gap_map=gap_map if gabsm is not None or gdn or gup else None,
                                gap_abs_min=gabsm,
                                gap_down=gdn,
                                gap_up=gup,
                            )
                            # also first/best-day variants for larger pools
                            variants = [("raw", rows)]
                            if bname in ("champ", "pool_champ", "good", "crown_htf", "crown_all", "stack", "gated"):
                                variants.append(("first", first_per_day(rows)))
                                variants.append(("bestp", best_p_per_day(rows)))
                            for vlab, vrows in variants:
                                if len(vrows) < MIN_N_REPORT:
                                    continue
                                if not is_perfect(vrows):
                                    continue
                                side_l = side or "BOTH"
                                p_l = f"p{int(pmin*100)}" if pmin else "p0"
                                h_l = "htf" if use_htf else "anyday"
                                name = f"A_{bname}_{side_l}_{p_l}_{tlab}_{h_l}_{glab}_{vlab}"
                                register(books, name, vrows, seen=seen)
                                n_a += 1
        print(f"    done base={bname} perfect_so_far={n_a} books={len(books)}", flush=True)

    print(f"  phase A perfect books={n_a}", flush=True)

    print("  phase B: 2-way day+side intersects + timed…", flush=True)
    # prepare indexes on 3y clip
    clipped = {k: _clip(v, START_3Y, END) for k, v in bases.items()}
    clipped["dual15_any"] = _clip(proven + champ, START_3Y, END)
    idxs = {k: _ix(v) for k, v in clipped.items()}
    sides = {k: _side_days(v) for k, v in clipped.items()}

    pair_list = [
        ("proven", "champ"),
        ("proven", "good"),
        ("proven", "crown_htf"),
        ("proven", "dual5_any"),
        ("champ", "good"),
        ("champ", "crown_htf"),
        ("champ", "dual5_any"),
        ("good", "crown_htf"),
        ("good", "dual5_any"),
        ("dual15_any", "dual5_any"),
        ("dual15_any", "crown_htf"),
        ("pool_proven", "crown_htf"),
        ("pool_proven", "dual5_any"),
        ("gated", "proven"),
        ("gated", "champ"),
        ("gated", "crown_htf"),
        ("gated", "good"),
    ]
    n_b = 0
    for a, b in pair_list:
        if a not in idxs or b not in idxs:
            continue
        # day+side: keep b if a same side
        rows = day_side_keep(clipped[b], sides[a], f"B_{b}_if_{a}")
        if len(rows) >= MIN_N_REPORT and is_perfect(rows):
            register(books, f"B_{b}_if_{a}_dayside", rows, seen=seen)
            n_b += 1
        rows2 = day_side_keep(clipped[a], sides[b], f"B_{a}_if_{b}")
        if len(rows2) >= MIN_N_REPORT and is_perfect(rows2):
            register(books, f"B_{a}_if_{b}_dayside", rows2, seen=seen)
            n_b += 1
        # timed agree entry=b
        for tol in (10, 15, 20, 30, 45, 60, 90):
            trows = time_agree(idxs[a], idxs[b], tol=tol, tag=f"B_T{tol}_{a}_x_{b}")
            if len(trows) >= MIN_N_REPORT and is_perfect(trows):
                register(books, f"B_T{tol}_{a}_gate_{b}_entry", trows, seen=seen)
                n_b += 1
            # reverse entry=a
            trows2 = time_agree(idxs[b], idxs[a], tol=tol, tag=f"B_T{tol}_{b}_x_{a}")
            if len(trows2) >= MIN_N_REPORT and is_perfect(trows2):
                register(books, f"B_T{tol}_{b}_gate_{a}_entry", trows2, seen=seen)
                n_b += 1
        print(f"    pair {a}×{b} perfect_pairs={n_b}", flush=True)

    print(f"  phase B perfect books={n_b}", flush=True)

    print("  phase C: stack hygiene → perfect subsets…", flush=True)
    n_c = 0
    stack_rows = clipped["stack"]
    # drop tracks
    for drop in (
        ("good_prod2",),
        ("crown_5m",),
        ("champion",),
        ("good_prod2", "crown_5m"),
        ("champion", "crown_5m"),
        ("good_prod2", "champion"),
    ):
        kept = [r for r in stack_rows if str(r.get("track")) not in drop]
        for vlab, vrows in (
            ("raw", kept),
            ("first", first_per_day(kept)),
            ("bestp", best_p_per_day(kept)),
        ):
            if len(vrows) >= MIN_N_REPORT and is_perfect(vrows):
                register(
                    books,
                    f"C_stack_drop_{'_'.join(drop)}_{vlab}",
                    vrows,
                    seen=seen,
                )
                n_c += 1
    # stack only proven+champ
    pc = [r for r in stack_rows if str(r.get("track")) in ("proven_100", "champion")]
    for pmin in (0.0, 0.58, 0.60, 0.62, 0.65, 0.70):
        for side in (None, "BUY", "SELL"):
            rows = filt(pc, p_min=pmin, side=side)
            if len(rows) >= MIN_N_REPORT and is_perfect(rows):
                register(
                    books,
                    f"C_stack_PC_{side or 'BOTH'}_p{int(pmin*100)}",
                    rows,
                    seen=seen,
                )
                n_c += 1
    # stack SELL-only / BUY-only / am
    for side in ("BUY", "SELL"):
        for hm_lo, hm_hi, tlab in time_bands:
            rows = filt(stack_rows, side=side, hm_lo=hm_lo, hm_hi=hm_hi)
            if len(rows) >= MIN_N_REPORT and is_perfect(rows):
                register(books, f"C_stack_{side}_{tlab}", rows, seen=seen)
                n_c += 1
    print(f"  phase C perfect books={n_c}", flush=True)

    print("  phase D: held-plus expand with other perfect extras…", flush=True)
    n_d = 0
    held_days = {r["day"] for r in plus}
    # any other perfect book extras not overlapping held days → merge if still perfect
    # score candidate perfect books first on full 3y clip inside books later

    def eval_map(start: str, end: str) -> Dict[str, Dict[str, Any]]:
        sess_w = [d for d in sess if start < d <= end]
        out = {}
        for name, rows in books.items():
            rs = _clip(rows, start, end)
            if not rs:
                out[name] = _pack(name, [], sess_w)
                continue
            out[name] = _pack(name, rs, sess_w)
        return out

    print("  scoring windows…", flush=True)
    s3 = eval_map(START_3Y, END)
    s1 = eval_map(START_1Y, END)
    sn = eval_map(START_NOV, END)

    # perfect on 3y with n>=MIN_N_PERFECT and also 1y perfect if n1>=5 (or n1==0 skip)
    perfect_3y = [
        r
        for r in s3.values()
        if r.get("perfect") and (r.get("n") or 0) >= MIN_N_PERFECT
    ]
    perfect_3y.sort(key=lambda r: (r["n"], r.get("points") or 0), reverse=True)

    both = []
    for r3 in perfect_3y:
        r1 = s1.get(r3["name"]) or {}
        n1 = r1.get("n") or 0
        if n1 >= 5 and not r1.get("perfect"):
            continue
        if n1 >= 5 and (r1.get("hit_pct") or 0) < 100:
            continue
        both.append(
            {
                "name": r3["name"],
                "n_3y": r3["n"],
                "hit_3y": r3["hit_pct"],
                "points_3y": r3.get("points"),
                "day_3y": r3.get("day_cov_pct"),
                "n_1y": n1,
                "hit_1y": r1.get("hit_pct"),
                "n_nov": (sn.get(r3["name"]) or {}).get("n") or 0,
                "hit_nov": (sn.get(r3["name"]) or {}).get("hit_pct"),
                "held": r3["name"].startswith("HELD_"),
            }
        )

    # try merge: held plus + other perfect books' rows on new days
    print("  phase D merges onto held plus…", flush=True)
    merge_hits = []
    base_plus = _clip(plus, START_3Y, END)
    base_days = {r["day"] for r in base_plus}
    for r3 in perfect_3y[:80]:
        name = r3["name"]
        if name.startswith("HELD_"):
            continue
        cand = _clip(books[name], START_3Y, END)
        extras = [dict(r, track=f"merge_{name}") for r in cand if r["day"] not in base_days]
        if not extras:
            continue
        merged = base_plus + extras
        if is_perfect(merged) and len(merged) > len(base_plus):
            mname = f"D_HELDPLUS_u_{name}"
            register(books, mname, merged, seen=seen)
            st = _pack(mname, merged, [d for d in sess if START_3Y < d <= END])
            merge_hits.append(st)
            n_d += 1
    merge_hits.sort(key=lambda r: r["n"], reverse=True)
    print(f"  phase D successful merges={n_d}", flush=True)

    # re-score after D
    for st in merge_hits:
        s3[st["name"]] = st
        s1[st["name"]] = _pack(
            st["name"], _clip(books[st["name"]], START_1Y, END), [d for d in sess if START_1Y < d <= END]
        )

    # refresh both list with merges
    for st in merge_hits:
        r1 = s1.get(st["name"]) or {}
        if (r1.get("n") or 0) >= 5 and not r1.get("perfect"):
            continue
        both.append(
            {
                "name": st["name"],
                "n_3y": st["n"],
                "hit_3y": st["hit_pct"],
                "points_3y": st.get("points"),
                "day_3y": st.get("day_cov_pct"),
                "n_1y": r1.get("n") or 0,
                "hit_1y": r1.get("hit_pct"),
                "n_nov": 0,
                "hit_nov": None,
                "held": False,
                "merge": True,
            }
        )
    both.sort(key=lambda r: (r["n_3y"], r.get("points_3y") or 0), reverse=True)

    # new discoveries = not held, n>= held confirm extras path
    discoveries = [b for b in both if not b.get("held")]
    held_n = next((b["n_3y"] for b in both if b["name"] == "HELD_PROVEN15_PLUS_CONFIRM_T30"), 49)

    payload = {
        "goal": "Long hunt for more 100% accuracy calls beyond held confirm",
        "held": {
            "PROVEN_100": "prod finalized",
            "CONFIRM_DUAL15_DUAL5_TIME30": "holding",
            "PROVEN15_PLUS_CONFIRM_T30": "holding",
        },
        "counts": {
            "books_scored": len(books),
            "perfect_3y_n8": len(perfect_3y),
            "both_year_ok": len(both),
            "discoveries": len(discoveries),
            "held_plus_merges": n_d,
        },
        "perfect_3y_top": perfect_3y[:60],
        "both_year_top": both[:60],
        "discoveries_top": discoveries[:40],
        "merge_onto_held_top": merge_hits[:20],
        "held_plus_n": held_n,
        "elapsed_s": round(time.time() - t0, 1),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "HUNT_100PCT_LONG.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (LEDGER / "HUNT_100PCT_LONG.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Long hunt — more 100% accuracy calls",
        "",
        "**Held (locked):** `PROVEN_100` · `CONFIRM_DUAL15_DUAL5_TIME30` · `PROVEN15_PLUS_CONFIRM_T30`",
        "",
        f"Scored **{len(books)}** books · perfect 3y n≥8: **{len(perfect_3y)}** · "
        f"both-year OK: **{len(both)}** · new discoveries: **{len(discoveries)}**",
        "",
        f"Elapsed **{payload['elapsed_s']}s**",
        "",
        "## Held baseline",
        "",
        "| Book | 3y N | Hit |",
        "|---|---:|---:|",
    ]
    for name in (
        "HELD_proven_100",
        "HELD_CONFIRM_T30",
        "HELD_PROVEN15_PLUS_CONFIRM_T30",
    ):
        r = s3.get(name) or {}
        lines.append(f"| `{name}` | {r.get('n')} | **{r.get('hit_pct')}%** |")

    lines += [
        "",
        "## Perfect 3y books (n≥8) — by size",
        "",
        "| Book | N | Points | Day | 1y n/hit | New? |",
        "|---|---:|---:|---:|---|---|",
    ]
    for r in perfect_3y[:50]:
        r1 = s1.get(r["name"]) or {}
        new = "held" if r["name"].startswith("HELD_") else "**NEW**"
        lines.append(
            f"| `{r['name']}` | {r['n']} | {r.get('points')} | {r.get('day_cov_pct')}% | "
            f"{r1.get('n')}/{r1.get('hit_pct')}% | {new} |"
        )

    lines += [
        "",
        "## Both-year 100% (1y perfect if n≥5)",
        "",
        "| Book | 3y | 1y | Nov |",
        "|---|---|---|---|",
    ]
    for b in both[:40]:
        lines.append(
            f"| `{b['name']}` | **{b['n_3y']}** @ {b['hit_3y']}% | "
            f"{b['n_1y']} @ {b['hit_1y']}% | {b['n_nov']} @ {b['hit_nov']}% |"
        )

    lines += [
        "",
        "## Merges onto held plus (still 100%)",
        "",
    ]
    if not merge_hits:
        lines.append("_No merge beat held plus while staying perfect._")
    else:
        lines += ["| Merge | N | Points | vs held 49 |", "|---|---:|---:|---|"]
        for r in merge_hits[:25]:
            lines.append(
                f"| `{r['name']}` | {r['n']} | {r.get('points')} | +{r['n'] - held_n} |"
            )

    # best new independent (not subset of proven alone naming)
    best_new = None
    for b in discoveries:
        if b["n_3y"] >= MIN_N_PERFECT:
            best_new = b
            break

    lines += [
        "",
        "## Best new find",
        "",
    ]
    if best_new:
        lines.append(
            f"**`{best_new['name']}`** → 3y **{best_new['n_3y']} @ {best_new['hit_3y']}%** "
            f"(1y {best_new['n_1y']} @ {best_new['hit_1y']}%)"
        )
        if best_new["n_3y"] > held_n:
            lines.append(f"- Beats held plus n={held_n}")
        else:
            lines.append(f"- Does not beat held plus n={held_n}; keep as parallel / hygiene candidate")
    else:
        lines.append("_No new both-year perfect book beyond held set._")

    lines += [
        "",
        "## Verdict",
        "",
        "- Held `PROVEN15_PLUS_CONFIRM_T30` stays the primary 100% expand desk.",
        "- This long hunt lists every other perfect gate found for further holding.",
        "- Prefer discoveries that are **rule-simple**, both-year perfect, and add n beyond held.",
        "- Still **not live**.",
        "",
        "JSON: `prod_live/reports/1y/HUNT_100PCT_LONG.json`",
        "",
    ]
    md = OUT / "HUNT_100PCT_LONG.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (LEDGER / "HUNT_100PCT_LONG.md").write_text("\n".join(lines), encoding="utf-8")
    ra = Path(r"C:\Users\Priyanka\research-and-analysis\feature\final-logic-ledger")
    if ra.is_dir():
        (ra / "HUNT_100PCT_LONG.md").write_text("\n".join(lines), encoding="utf-8")

    print("Wrote", md, flush=True)
    print(
        json.dumps(
            {
                "books": len(books),
                "perfect_3y": len(perfect_3y),
                "both_year": len(both),
                "discoveries": len(discoveries),
                "merges": n_d,
                "top5": [
                    {"name": b["name"], "n": b["n_3y"], "held": b.get("held")}
                    for b in both[:5]
                ],
                "best_merge": (merge_hits[0]["name"], merge_hits[0]["n"]) if merge_hits else None,
                "elapsed_s": payload["elapsed_s"],
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
