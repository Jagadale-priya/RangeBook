"""Push CHAMPION+ harder — more calls, hold 1y hit >= 92.5%.

Changes vs first expand:
  - Soft stream gate (merge desk_ok is the real floor) → more additive candidates
  - Wider univ: GD native/30/35/40 · D10 · CH · dual15 champ
  - Modes: day · cap2 · cap3
  - Seed = full champion (always kept)
  - No PROVEN / CROWN as stack tracks; no raw good_prod2 track

  python -u prod_live/tests/builders/research_champion_plus_push_1y.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
HOLD = ROOT / "prod_live" / "holding_accurate" / "champion_plus"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"
CACHE_XY = LEDGER / "_cache_dual10m_xy_research.json"
PACKS = LEDGER / "nifty_side_models_10m_research" / "dual10m_packs.joblib"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"

START_1Y, END = hold.START, hold.END
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
FLOOR_1Y = 92.5
MIN_N = 3

BANDS = [
    ("first30", 9 * 60 + 15, 9 * 60 + 45),
    ("first45", 9 * 60 + 15, 10 * 60),
    ("open", 9 * 60 + 15, 10 * 60 + 30),
    ("am1130", 9 * 60 + 15, 11 * 60 + 30),
    ("am1230", 9 * 60 + 15, 12 * 60 + 30),
    ("mid", 10 * 60, 13 * 60),
    ("latemid", 10 * 60 + 30, 14 * 60),
    ("pm", 12 * 60 + 30, 15 * 60 + 15),
    ("late", 13 * 60, 15 * 60 + 15),
    ("all", None, None),
]
GAPS = [
    ("nogap", None, False, False),
    ("g015", 0.15, False, False),
    ("g020", 0.20, False, False),
    ("g030", 0.30, False, False),
    ("g040", 0.40, False, False),
    ("g055", 0.55, False, False),
    ("gdn025", 0.25, True, False),
    ("gdn040", 0.40, True, False),
    ("gup025", 0.25, False, True),
    ("gup040", 0.40, False, True),
]
PMINS = (0.0, 0.50, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70, 0.72, 0.75, 0.78, 0.82)


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return 100.0 * sum(1 for r in rows if r.get("win")) / len(rows)


def desk_ok(rows: List[dict], seed_3y_hit: float) -> bool:
    r1 = _clip(rows, START_1Y, END)
    if len(r1) >= MIN_N and hit_pct(r1) + 1e-9 < FLOOR_1Y:
        return False
    r3 = _clip(rows, START_3Y, END)
    if len(r3) >= MIN_N and hit_pct(r3) + 1e-9 < seed_3y_hit - 1e-9:
        return False
    return True


def stream_soft_ok(rows: List[dict]) -> bool:
    """Soft: enough mass + not terrible alone. Real floor = desk_ok on merge."""
    r1 = _clip(rows, START_1Y, END)
    r3 = _clip(rows, START_3Y, END)
    if len(r1) >= MIN_N:
        return hit_pct(r1) + 1e-9 >= 75.0  # soft alone
    return len(r3) >= MIN_N and hit_pct(r3) + 1e-9 >= 75.0


def mid_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")].append(r)
    out = []
    for day in sorted(by):
        ordered = sorted(by[day], key=lambda x: _hm_mins(str(x.get("hm") or "99:99")))
        out.append(ordered[len(ordered) // 2])
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


def load_d10() -> List[dict]:
    import joblib

    packs = joblib.load(PACKS)
    xy = json.loads(CACHE_XY.read_text(encoding="utf-8"))
    out: List[dict] = []
    for r in xy.get("tickets") or []:
        side = str(r.get("decision") or "").upper()
        pack = packs.get(side) or {}
        if not pack.get("available") or not r.get("x"):
            continue
        X = np.asarray([r["x"]], dtype=float)
        raw = float(pack["base"].predict_proba(X)[0, 1])
        p = float(np.clip(pack["iso"].transform([raw])[0], 0.05, 0.95))
        rr = {k: v for k, v in r.items() if k != "x"}
        rr["p_t1"] = round(p, 4)
        rr["track"] = "dual10m"
        rr["tf"] = "10m"
        out.append(rr)
    return out


def mine(univ: Dict[str, List[dict]], gaps, active) -> List[Tuple[str, List[dict]]]:
    keys = [k for k in ("CH", "GDN", "GD40", "GD35", "GD30", "D10", "D15C") if k in univ]
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
                                ("mid", mid_day(base)),
                                ("last", last_day(base)),
                            ):
                                if not vrows:
                                    continue
                                n_eval += 1
                                if not stream_soft_ok(vrows):
                                    continue
                                tag = (
                                    f"CP_{uname}_{side or 'BOTH'}_p{int(round(pmin * 100))}_"
                                    f"{blab}_{'htf' if use_htf else 'any'}_{glab}_{vlab}"
                                )
                                streams.append((tag, vrows))
    print(f"  mined eval={n_eval} soft-keep={len(streams)}", flush=True)
    by: Dict[str, List[dict]] = {}
    for tag, rows in streams:
        n = len(_clip(rows, START_1Y, END))
        if tag not in by or n > len(_clip(by[tag], START_1Y, END)):
            by[tag] = rows
    # Prefer high-hit then high-n streams first for greedy quality
    return sorted(
        by.items(),
        key=lambda kv: (
            hit_pct(_clip(kv[1], START_1Y, END)),
            len(_clip(kv[1], START_1Y, END)),
        ),
        reverse=True,
    )


def merge_day(a: List[dict], b: List[dict]) -> List[dict]:
    return union_unique_days(a, b)


def merge_cap(a: List[dict], b: List[dict], cap: int) -> List[dict]:
    tracks: Dict[str, List[dict]] = defaultdict(list)
    for r in a + b:
        tracks[str(r.get("track") or "champ_plus")].append(r)
    return union_day_cap2(dict(tracks), day_cap=cap)


def greedy(
    seed: List[dict],
    streams: List[Tuple[str, List[dict]]],
    merge_fn,
    seed_3y_hit: float,
    *,
    max_add: int = 150,
) -> Tuple[List[dict], List[str]]:
    cur = list(seed)
    used: List[str] = []
    improved = True
    while improved and len(used) < max_add:
        improved = False
        best = None
        best_n = len(_clip(cur, START_1Y, END))
        best_hit = hit_pct(_clip(cur, START_1Y, END))
        for tag, rows in streams:
            if tag in used:
                continue
            merged = merge_fn(cur, rows)
            n1 = len(_clip(merged, START_1Y, END))
            if n1 <= best_n:
                continue
            if not desk_ok(merged, seed_3y_hit):
                continue
            h1 = hit_pct(_clip(merged, START_1Y, END))
            # prefer more N; tie-break higher hit
            if best is None or n1 > best_n or (n1 == best_n and h1 > best_hit):
                best = (tag, merged)
                best_n = n1
                best_hit = h1
        if best:
            used.append(best[0])
            cur = best[1]
            improved = True
            if len(used) <= 12 or len(used) % 15 == 0:
                print(
                    f"    +{best[0][:72]} → 1y n={best_n} hit={best_hit:.2f}",
                    flush=True,
                )
    return cur, used


def main() -> int:
    t0 = time.time()
    print(f"CHAMPION+ PUSH · more calls @>={FLOOR_1Y}% · {START_1Y}→{END}", flush=True)

    pool = json.loads(POOL.read_text(encoding="utf-8"))
    seed_full = hold._clean(
        _champ_floor([r for r in pool["champion"] if START_3Y <= r["day"] <= END])
    )
    for r in seed_full:
        r["track"] = "champion"
    sc0 = _agg(_clip(seed_full, START_1Y, END))
    sc0_3 = _agg(_clip(seed_full, START_3Y, END))
    seed_3y_hit = float(sc0_3.get("hit_pct") or 0)
    print(
        f"  seed 1y {sc0.get('n')}@{sc0.get('hit_pct')}% · 3y {sc0_3.get('n')}@{sc0_3.get('hit_pct')}%",
        flush=True,
    )

    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_3Y < d <= END]
    active = fs._active_days(sess, fs._load_daily()) if sess else set()

    gbr = path_u.get("good_by_risk") or {}
    dual = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    d15c = [
        dict(r, track="champion")
        for r in (dual.get("dual15") or {}).get("champion") or []
    ]

    print("  load D10…", flush=True)
    d10 = load_d10()
    univ = {
        "CH": seed_full,
        "D15C": d15c,
        "GDN": gbr.get("native") or [],
        "GD40": gbr.get("40.0") or gbr.get("40") or [],
        "GD35": gbr.get("35.0") or gbr.get("35") or [],
        "GD30": gbr.get("30.0") or gbr.get("30") or [],
        "D10": d10,
    }
    print(
        "  univ "
        + " ".join(f"{k}={len(v)}" for k, v in univ.items()),
        flush=True,
    )

    print("  mine (soft gate)…", flush=True)
    streams = mine(univ, gaps, active)
    # keep top ~4k by sort order already — truncate for runtime if huge
    if len(streams) > 8000:
        streams = streams[:8000]
        print(f"  truncated streams→{len(streams)}", flush=True)

    results: Dict[str, Any] = {"seed": {"1y": sc0, "3y": sc0_3}}
    lines = [
        "# CHAMPION+ PUSH — more calls @ same accuracy",
        "",
        "**Status:** RESEARCH · not live",
        "**Seed:** CHAMPION · **Dropped tracks:** PROVEN / GOOD_PROD2 / CROWN",
        f"**Floor:** 1y ≥ **{FLOOR_1Y}%** · 3y ≥ seed ({seed_3y_hit}%)",
        f"**Window:** `{START_1Y}` → `{END}`",
        f"Soft-mined streams={len(streams)}",
        "",
        "| Book | 1y N@hit | 3y N@hit | ΔN | Streams |",
        "|---|---|---|---:|---:|",
        f"| `CHAMPION` seed | {sc0.get('n')}@{sc0.get('hit_pct')} | "
        f"{sc0_3.get('n')}@{sc0_3.get('hit_pct')} | 0 | 0 |",
    ]

    modes = [
        ("day", lambda a, b: merge_day(a, b)),
        ("cap2", lambda a, b: merge_cap(a, b, 2)),
        ("cap3", lambda a, b: merge_cap(a, b, 3)),
    ]
    best_mode = None
    best_n = -1
    books: Dict[str, List[dict]] = {}

    for mode, merge_fn in modes:
        print(f"  greedy {mode}…", flush=True)
        rows, tags = greedy(seed_full, streams, merge_fn, seed_3y_hit, max_add=150)
        rows = hold._clean(rows)
        for r in rows:
            r["desk_tag"] = f"CHAMPION_PLUS_{mode.upper()}"
            r["lane"] = "RESEARCH"
        books[mode] = rows
        sc1 = _agg(_clip(rows, START_1Y, END))
        sc3 = _agg(_clip(rows, START_3Y, END))
        delta = (sc1.get("n") or 0) - (sc0.get("n") or 0)
        ok = desk_ok(rows, seed_3y_hit)
        results[mode] = {
            "ok": ok,
            "streams": tags,
            "n_streams": len(tags),
            "1y": sc1,
            "3y": sc3,
            "delta_n_1y": delta,
        }
        lines.append(
            f"| `CHAMPION_PLUS_{mode}` | **{sc1.get('n')}@{sc1.get('hit_pct')}** | "
            f"{sc3.get('n')}@{sc3.get('hit_pct')} | +{delta} | {len(tags)} |"
        )
        print(
            f"    → {mode} {sc1.get('n')}@{sc1.get('hit_pct')}% +{delta} "
            f"streams={len(tags)} ok={ok}",
            flush=True,
        )
        if ok and (sc1.get("n") or 0) > best_n:
            best_mode = mode
            best_n = sc1.get("n") or 0

    if best_mode:
        calls = sorted(
            _clip(books[best_mode], START_1Y, END),
            key=lambda x: (x.get("day"), x.get("hm")),
        )
        lines.extend(
            [
                "",
                f"## Best 1y calls — `CHAMPION_PLUS_{best_mode}`",
                "",
                "| # | Day | HM | Side | Win | Track | p |",
                "|---:|---|---|---|---|---|---:|",
            ]
        )
        for i, r in enumerate(calls, 1):
            lines.append(
                f"| {i} | {r.get('day')} | {r.get('hm')} | {_side(r)} | "
                f"{'W' if r.get('win') else 'L'} | {r.get('track')} | {r.get('p_t1')} |"
            )
        sc = results[best_mode]["1y"]
        lines.extend(
            [
                "",
                f"**N={sc.get('n')}** · hit **{sc.get('hit_pct')}%** "
                f"({sc.get('wins')}W/{sc.get('losses')}L)",
                "",
                "### Streams used",
                "",
            ]
        )
        for t in results[best_mode]["streams"]:
            lines.append(f"- `{t}`")
        lines.append("")

    prev_n = 69  # prior cap2 push
    if best_mode and best_n > prev_n:
        verdict = (
            f"PUSH OK — best `{best_mode}` {best_n}@"
            f"{results[best_mode]['1y'].get('hit_pct')}% "
            f"(was {prev_n}@92.75% · seed {sc0.get('n')}@92.68%). Still RESEARCH."
        )
    elif best_mode and best_n > (sc0.get("n") or 0):
        verdict = (
            f"PUSH PARTIAL — `{best_mode}` {best_n}@"
            f"{results[best_mode]['1y'].get('hit_pct')}% "
            f"vs seed {sc0.get('n')} · not above prior {prev_n}."
        )
    else:
        verdict = "PUSH FAIL — no gain over seed at floor."

    elapsed = round(time.time() - t0, 1)
    lines.extend(["## Verdict", "", verdict, "", f"Elapsed {elapsed}s", ""])

    payload = {
        "status": "RESEARCH",
        "not_live": True,
        "floor_1y": FLOOR_1Y,
        "window_1y": {"start": START_1Y, "end": END},
        "results": results,
        "best_mode": best_mode,
        "verdict": verdict,
        "elapsed_s": elapsed,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    HOLD.mkdir(parents=True, exist_ok=True)
    md = OUT / "CHAMPION_PLUS_PUSH_1Y.md"
    js = OUT / "CHAMPION_PLUS_PUSH_1Y.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    if best_mode:
        recipe = {
            "status": "RESEARCH",
            "desk": f"CHAMPION_PLUS_{best_mode.upper()}",
            "seed": "CHAMPION",
            "floor_1y": FLOOR_1Y,
            "stream_tags_research": results[best_mode]["streams"],
            "research_1y": results[best_mode]["1y"],
            "research_3y": results[best_mode]["3y"],
            "prior_cap2_n": prev_n,
        }
        (HOLD / "recipes_research.json").write_text(
            json.dumps(recipe, indent=2, default=str), encoding="utf-8"
        )
    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
