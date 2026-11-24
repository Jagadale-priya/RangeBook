"""CHAMPION-only live direction — more calls @ same accuracy (~92.5%).

Dropped from volume stack (by design): PROVEN_100 · GOOD_PROD2 · CROWN_DUAL_HTF.
Kept: CHAMPION seed. Expand with filtered streams (path-good + dual10m) —
NOT as live good/crown tracks — greedy keep 1y hit >= champion baseline.

  python -u prod_live/tests/builders/research_champion_plus_more_1y.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import POOL, _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _hm_mins, _side  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    bestp_day,
    filt,
    first_day,
    gap_map,
    union_unique_days,
)
from prod_live.logic.stack import union_day_cap2  # noqa: E402
import live_final_1y_months_accurate as hold  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
HOLD = ROOT / "prod_live" / "holding_accurate"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"
CACHE_XY = LEDGER / "_cache_dual10m_xy_research.json"
PACKS = LEDGER / "nifty_side_models_10m_research" / "dual10m_packs.joblib"

# Golden live 1y (match CHAMPION_ONLY_1Y)
START_1Y, END = hold.START, hold.END
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
FLOOR_1Y = 92.5  # same as champion alone (1y target)
# Champ seed itself is ~83.6% on 3y — do not gate harder than seed
FLOOR_3Y_DELTA = 0.0  # merged 3y hit must be >= seed 3y hit
MIN_N = 3
SEED_3Y_HIT = 83.64  # filled at runtime from seed

BANDS = [
    ("first45", 9 * 60 + 15, 10 * 60),
    ("open", 9 * 60 + 15, 10 * 60 + 30),
    ("am1130", 9 * 60 + 15, 11 * 60 + 30),
    ("am1230", 9 * 60 + 15, 12 * 60 + 30),
    ("mid", 10 * 60, 13 * 60),
    ("latemid", 10 * 60 + 30, 14 * 60),
    ("pm", 12 * 60 + 30, 15 * 60 + 15),
    ("all", None, None),
]
GAPS = [
    ("nogap", None, False, False),
    ("g020", 0.20, False, False),
    ("g030", 0.30, False, False),
    ("g040", 0.40, False, False),
    ("gdn025", 0.25, True, False),
    ("gup025", 0.25, False, True),
]
PMINS = (0.0, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70, 0.72, 0.75, 0.80)


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return 100.0 * sum(1 for r in rows if r.get("win")) / len(rows)


def desk_ok(rows: List[dict], seed_3y_hit: float = SEED_3Y_HIT) -> bool:
    """Keep 1y >= champion accuracy; 3y not worse than champ seed."""
    r1 = _clip(rows, START_1Y, END)
    if len(r1) >= MIN_N and hit_pct(r1) + 1e-9 < FLOOR_1Y:
        return False
    r3 = _clip(rows, START_3Y, END)
    if len(r3) >= MIN_N and hit_pct(r3) + 1e-9 < seed_3y_hit - 1e-9:
        return False
    return True


def stream_ok(rows: List[dict], seed_3y_hit: float = SEED_3Y_HIT) -> bool:
    r1 = _clip(rows, START_1Y, END)
    if len(r1) < MIN_N:
        r3 = _clip(rows, START_3Y, END)
        return len(r3) >= MIN_N and hit_pct(r3) + 1e-9 >= seed_3y_hit
    if hit_pct(r1) + 1e-9 < FLOOR_1Y:
        return False
    r3 = _clip(rows, START_3Y, END)
    if len(r3) >= MIN_N and hit_pct(r3) + 1e-9 < seed_3y_hit - 1e-9:
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


def load_d10() -> List[dict]:
    import joblib

    packs = joblib.load(PACKS)
    xy = json.loads(CACHE_XY.read_text(encoding="utf-8"))
    out: List[dict] = []
    for r in xy.get("tickets") or []:
        side = str(r.get("decision") or "").upper()
        pack = packs.get(side) or {}
        if not pack.get("available"):
            continue
        x = r.get("x")
        if not x:
            continue
        X = np.asarray([x], dtype=float)
        raw = float(pack["base"].predict_proba(X)[0, 1])
        p = float(np.clip(pack["iso"].transform([raw])[0], 0.05, 0.95))
        rr = {k: v for k, v in r.items() if k != "x"}
        rr["p_t1"] = round(p, 4)
        rr["track"] = "dual10m"
        rr["tf"] = "10m"
        out.append(rr)
    return out


def mine(
    univ: Dict[str, List[dict]],
    gaps,
    active,
    seed_3y_hit: float,
) -> List[Tuple[str, List[dict]]]:
    keys = [k for k in ("CH", "GD40", "GD30", "D10") if k in univ]
    streams: List[Tuple[str, List[dict]]] = []
    n_eval = 0
    for uname in keys:
        urows = univ[uname]
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
                                ("last", last_day(base)),
                            ):
                                if not vrows:
                                    continue
                                n_eval += 1
                                if not stream_ok(vrows, seed_3y_hit):
                                    continue
                                tag = (
                                    f"CP_{uname}_{side or 'BOTH'}_p{int(round(pmin * 100))}_"
                                    f"{blab}_{'htf' if use_htf else 'any'}_{glab}_{vlab}"
                                )
                                streams.append((tag, vrows))
    print(f"  mined eval={n_eval} keep={len(streams)}", flush=True)
    by: Dict[str, List[dict]] = {}
    for tag, rows in streams:
        n = len(_clip(rows, START_1Y, END))
        if tag not in by or n > len(_clip(by[tag], START_1Y, END)):
            by[tag] = rows
    return sorted(
        by.items(),
        key=lambda kv: (hit_pct(_clip(kv[1], START_1Y, END)), len(_clip(kv[1], START_1Y, END))),
        reverse=True,
    )


def merge_day(a: List[dict], b: List[dict]) -> List[dict]:
    return union_unique_days(a, b)


def merge_cap2(a: List[dict], b: List[dict]) -> List[dict]:
    # stamp tracks then union_day_cap2
    tracks: Dict[str, List[dict]] = defaultdict(list)
    for r in a + b:
        tr = str(r.get("track") or "champ_plus")
        tracks[tr].append(r)
    return union_day_cap2(dict(tracks), day_cap=2)


def greedy(
    seed: List[dict],
    streams: List[Tuple[str, List[dict]]],
    merge_fn,
    seed_3y_hit: float,
    *,
    max_add: int = 80,
) -> Tuple[List[dict], List[str]]:
    # Always keep champion seed (1y already @~92.5%)
    cur = list(seed)
    used: List[str] = []
    improved = True
    while improved and len(used) < max_add:
        improved = False
        best = None
        best_n = len(_clip(cur, START_1Y, END))
        for tag, rows in streams:
            if tag in used:
                continue
            merged = merge_fn(cur, rows)
            n1 = len(_clip(merged, START_1Y, END))
            if n1 <= best_n:
                continue
            if not desk_ok(merged, seed_3y_hit):
                continue
            best = (tag, merged)
            best_n = n1
        if best:
            used.append(best[0])
            cur = best[1]
            improved = True
            if len(used) <= 10 or len(used) % 10 == 0:
                print(
                    f"    +{best[0][:70]} → 1y n={len(_clip(cur, START_1Y, END))} "
                    f"hit={hit_pct(_clip(cur, START_1Y, END)):.2f}",
                    flush=True,
                )
    return cur, used


def main() -> int:
    t0 = time.time()
    print(f"CHAMPION+ more @>={FLOOR_1Y}% · 1y {START_1Y}→{END}", flush=True)
    print("  drop: PROVEN · GOOD_PROD2 · CROWN_DUAL_HTF · keep CHAMPION", flush=True)

    live = hold._build_live_stack(START_1Y, END)
    seed = hold._clean([dict(r, track="champion") for r in live["champ"]])
    # also load 3y champ for seed richness
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    champ_3y = _champ_floor(
        [r for r in pool["champion"] if START_3Y <= r["day"] <= END]
    )
    for r in champ_3y:
        r["track"] = "champion"
    seed_full = hold._clean(champ_3y)
    sc0 = _agg(_clip(seed_full, START_1Y, END))
    sc0_3 = _agg(_clip(seed_full, START_3Y, END))
    seed_3y_hit = float(sc0_3.get("hit_pct") or 0)
    print(
        f"  seed champ 1y {sc0.get('n')}@{sc0.get('hit_pct')}% · "
        f"3y {sc0_3.get('n')}@{sc0_3.get('hit_pct')}%",
        flush=True,
    )

    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_3Y < d <= END]
    active = fs._active_days(sess, fs._load_daily()) if sess else set()

    print("  load D10…", flush=True)
    d10 = load_d10()
    gd40 = path_u.get("good_by_risk", {}).get("40.0") or path_u.get("good_by_risk", {}).get("40") or []
    gd30 = path_u.get("good_by_risk", {}).get("30.0") or path_u.get("good_by_risk", {}).get("30") or []
    # NO crown universe — user removed CROWN_DUAL_HTF
    univ = {
        "CH": seed_full,
        "GD40": gd40,
        "GD30": gd30,
        "D10": d10,
    }
    print(
        f"  univ sizes CH={len(univ['CH'])} GD40={len(gd40)} GD30={len(gd30)} D10={len(d10)}",
        flush=True,
    )

    print("  mine streams…", flush=True)
    streams = mine(univ, gaps, active, seed_3y_hit)

    results: Dict[str, Any] = {}
    lines = [
        "# CHAMPION+ — more calls @ same accuracy",
        "",
        "**Status:** RESEARCH · not live",
        "**Dropped:** `PROVEN_100` · `GOOD_PROD2` · `CROWN_DUAL_HTF`",
        "**Kept seed:** `CHAMPION` (BUY p≥0.55 · SELL p≥0.58)",
        f"**Floor:** 1y hit ≥ **{FLOOR_1Y}%** · 3y ≥ champ seed ({seed_3y_hit}%)",
        f"**Window 1y:** `{START_1Y}` → `{END}` · 3y `{START_3Y}` → `{END}`",
        "",
        "> Expand streams may use path-good / dual10m **filters** (not as live stack tracks). No crown.",
        "",
        "| Book | Mode | 1y N@hit | 3y N@hit | Δ vs champ | Streams |",
        "|---|---|---|---|---:|---:|",
    ]

    # baseline alone
    base_day = merge_day([], seed_full)  # unique days from seed
    # seed already ~1/day mostly; use clip
    base_cap2 = union_day_cap2({"champion": seed_full})
    for label, rows in (
        ("CHAMPION_ONLY", _clip(seed_full, START_1Y, END)),
        ("CHAMPION_ONLY_CAP2", _clip(hold._clean(base_cap2), START_1Y, END)),
    ):
        pass

    sc_seed_1 = _agg(_clip(seed_full, START_1Y, END))
    sc_seed_3 = _agg(_clip(seed_full, START_3Y, END))
    lines.append(
        f"| `CHAMPION` seed | day/raw | {sc_seed_1.get('n')}@{sc_seed_1.get('hit_pct')} | "
        f"{sc_seed_3.get('n')}@{sc_seed_3.get('hit_pct')} | 0 | 0 |"
    )
    results["seed"] = {"1y": sc_seed_1, "3y": sc_seed_3}

    for mode, merge_fn in (("day", merge_day), ("cap2", merge_cap2)):
        print(f"  greedy expand mode={mode}…", flush=True)
        rows, tags = greedy(seed_full, streams, merge_fn, seed_3y_hit)
        rows = hold._clean(rows)
        for r in rows:
            r["desk_tag"] = f"CHAMPION_PLUS_{mode.upper()}"
            r["lane"] = "RESEARCH"
        sc1 = _agg(_clip(rows, START_1Y, END))
        sc3 = _agg(_clip(rows, START_3Y, END))
        delta = (sc1.get("n") or 0) - (sc_seed_1.get("n") or 0)
        ok = desk_ok(rows, seed_3y_hit)
        results[mode] = {
            "ok": ok,
            "streams": tags,
            "n_streams": len(tags),
            "1y": sc1,
            "3y": sc3,
            "delta_n_1y": delta,
            "calls_1y": [
                {
                    "day": r.get("day"),
                    "hm": r.get("hm"),
                    "side": _side(r),
                    "win": r.get("win"),
                    "p_t1": r.get("p_t1"),
                    "track": r.get("track"),
                }
                for r in sorted(
                    _clip(rows, START_1Y, END),
                    key=lambda x: (x.get("day"), x.get("hm")),
                )
            ],
        }
        lines.append(
            f"| `CHAMPION_PLUS` | {mode} | **{sc1.get('n')}@{sc1.get('hit_pct')}** | "
            f"{sc3.get('n')}@{sc3.get('hit_pct')} | +{delta} | {len(tags)} |"
        )
        print(
            f"    → {mode} 1y {sc1.get('n')}@{sc1.get('hit_pct')}% "
            f"3y {sc3.get('n')}@{sc3.get('hit_pct')}% +{delta} streams={len(tags)} ok={ok}",
            flush=True,
        )

    # pick best mode by 1y N among ok
    best_mode = None
    best_n = -1
    for mode in ("day", "cap2"):
        r = results[mode]
        if r.get("ok") and (r["1y"].get("n") or 0) > best_n:
            best_mode = mode
            best_n = r["1y"].get("n") or 0

    if best_mode:
        calls = results[best_mode]["calls_1y"]
        lines.extend(
            [
                "",
                f"## 1y calls — `CHAMPION_PLUS` ({best_mode})",
                "",
                "| # | Day | HM | Side | Win | Track | p |",
                "|---:|---|---|---|---|---|---:|",
            ]
        )
        for i, r in enumerate(calls, 1):
            lines.append(
                f"| {i} | {r['day']} | {r['hm']} | {r['side']} | "
                f"{'W' if r['win'] else 'L'} | {r.get('track')} | {r.get('p_t1')} |"
            )
        sc = results[best_mode]["1y"]
        lines.extend(
            [
                "",
                f"**N={sc.get('n')}** · hit **{sc.get('hit_pct')}%** · "
                f"streams={results[best_mode]['n_streams']}",
                "",
            ]
        )

    seed_n = sc_seed_1.get("n") or 0
    if best_mode and best_n > seed_n:
        verdict = (
            f"PROMISING — CHAMPION_PLUS ({best_mode}) {best_n}@"
            f"{results[best_mode]['1y'].get('hit_pct')}% vs seed {seed_n}@"
            f"{sc_seed_1.get('hit_pct')}% (+{best_n - seed_n}). Still RESEARCH."
        )
    elif best_mode and best_n == seed_n:
        verdict = (
            f"THIN — no extra calls cleared {FLOOR_1Y}% floor beyond champ seed "
            f"({seed_n}@{sc_seed_1.get('hit_pct')}%). Need new ticket sources."
        )
    else:
        verdict = f"FAIL — could not hold {FLOOR_1Y}% while expanding."

    elapsed = round(time.time() - t0, 1)
    lines.extend(["## Verdict", "", verdict, "", f"Elapsed {elapsed}s", ""])

    payload = {
        "status": "RESEARCH",
        "not_live": True,
        "dropped": ["PROVEN_100", "GOOD_PROD2", "CROWN_DUAL_HTF"],
        "kept": ["CHAMPION"],
        "floor_1y": FLOOR_1Y,
        "floor_3y_min": seed_3y_hit,
        "window_1y": {"start": START_1Y, "end": END},
        "results": results,
        "best_mode": best_mode,
        "verdict": verdict,
        "elapsed_s": elapsed,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (HOLD / "champion_plus").mkdir(parents=True, exist_ok=True)
    md = OUT / "CHAMPION_PLUS_MORE_1Y.md"
    js = OUT / "CHAMPION_PLUS_MORE_1Y.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    # save recipe for best mode
    if best_mode:
        recipe = {
            "status": "RESEARCH",
            "desk": f"CHAMPION_PLUS_{best_mode.upper()}",
            "seed": "CHAMPION",
            "floor_1y": FLOOR_1Y,
            "stream_tags_research": results[best_mode]["streams"],
            "research_1y": results[best_mode]["1y"],
            "research_3y": results[best_mode]["3y"],
        }
        (HOLD / "champion_plus" / "recipes_research.json").write_text(
            json.dumps(recipe, indent=2, default=str), encoding="utf-8"
        )
    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
