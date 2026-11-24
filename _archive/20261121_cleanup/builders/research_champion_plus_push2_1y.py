"""CHAMPION+ push2 — beat prior 69@92.75% while holding >=92.5%.

Warm-start prior recipe streams, then keep adding. Stream pool = mix of
high-hit + high-N candidates (no crown / proven tracks).

  python -u prod_live/tests/builders/research_champion_plus_push2_1y.py
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
PRIOR = HOLD / "recipes_research.json"

START_1Y, END = hold.START, hold.END
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
FLOOR_1Y = 92.5
MIN_N = 3
PRIOR_N = 69

# Prior winning streams (fallback if recipe missing)
PRIOR_TAGS = [
    "CP_GD40_BOTH_p0_mid_any_gup025_bestp",
    "CP_GD40_BOTH_p55_mid_any_g020_raw",
    "CP_GD40_BUY_p0_mid_any_g020_bestp",
    "CP_GD40_BOTH_p0_pm_htf_nogap_raw",
    "CP_D10_BOTH_p55_open_any_g020_raw",
    "CP_D10_BOTH_p55_mid_any_g040_raw",
]

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
    ("g015", 0.15, False, False),
    ("g020", 0.20, False, False),
    ("g030", 0.30, False, False),
    ("g040", 0.40, False, False),
    ("gdn025", 0.25, True, False),
    ("gup025", 0.25, False, True),
    ("gup040", 0.40, False, True),
]
PMINS = (0.0, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70, 0.75)


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
    r1 = _clip(rows, START_1Y, END)
    if len(r1) >= 2 and hit_pct(r1) >= 70.0:
        return True
    r3 = _clip(rows, START_3Y, END)
    return len(r3) >= MIN_N and hit_pct(r3) >= 70.0


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
    out = []
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
        out.append(rr)
    return out


def mine_all(univ, gaps, active) -> Dict[str, List[dict]]:
    """Return tag→rows for all soft-ok streams (dict)."""
    keys = [k for k in ("CH", "GDN", "GD40", "GD35", "GD30", "D10") if k in univ]
    by: Dict[str, List[dict]] = {}
    n_eval = 0
    for uname in keys:
        for side in (None, "BUY", "SELL"):
            for blab, lo, hi in BANDS:
                for glab, gabsm, gdn, gup in GAPS:
                    for use_htf in (False, True):
                        for pmin in PMINS:
                            base = filt(
                                univ[uname],
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
                                n = len(_clip(vrows, START_1Y, END))
                                if tag not in by or n > len(_clip(by[tag], START_1Y, END)):
                                    by[tag] = vrows
    print(f"  mined eval={n_eval} unique soft tags={len(by)}", flush=True)
    return by


def pool_mix(by: Dict[str, List[dict]], prior_tags: List[str], lim: int = 12000) -> List[Tuple[str, List[dict]]]:
    """Mix high-hit + high-N + prior tags."""
    items = list(by.items())
    by_hit = sorted(
        items,
        key=lambda kv: (hit_pct(_clip(kv[1], START_1Y, END)), len(_clip(kv[1], START_1Y, END))),
        reverse=True,
    )
    by_n = sorted(
        items,
        key=lambda kv: (len(_clip(kv[1], START_1Y, END)), hit_pct(_clip(kv[1], START_1Y, END))),
        reverse=True,
    )
    seen = set()
    out: List[Tuple[str, List[dict]]] = []
    for tag in prior_tags:
        if tag in by and tag not in seen:
            out.append((tag, by[tag]))
            seen.add(tag)
    for src in (by_hit, by_n):
        for tag, rows in src:
            if tag in seen:
                continue
            out.append((tag, rows))
            seen.add(tag)
            if len(out) >= lim:
                return out
    return out


def merge_cap(a, b, cap=2):
    tracks: Dict[str, List[dict]] = defaultdict(list)
    for r in a + b:
        tracks[str(r.get("track") or "champ_plus")].append(r)
    return union_day_cap2(dict(tracks), day_cap=cap)


def greedy(
    seed: List[dict],
    streams: List[Tuple[str, List[dict]]],
    seed_3y_hit: float,
    *,
    cap: int = 2,
    max_add: int = 200,
    warm_tags: List[str] | None = None,
) -> Tuple[List[dict], List[str]]:
    cur = list(seed)
    used: List[str] = []
    by = dict(streams)
    # warm-start prior tags in order
    for tag in warm_tags or []:
        rows = by.get(tag)
        if not rows or tag in used:
            continue
        merged = merge_cap(cur, rows, cap)
        if desk_ok(merged, seed_3y_hit) and len(_clip(merged, START_1Y, END)) >= len(
            _clip(cur, START_1Y, END)
        ):
            cur = merged
            used.append(tag)
            print(
                f"    warm {tag[:64]} → n={len(_clip(cur, START_1Y, END))} "
                f"hit={hit_pct(_clip(cur, START_1Y, END)):.2f}",
                flush=True,
            )

    improved = True
    while improved and len(used) < max_add:
        improved = False
        best = None
        best_n = len(_clip(cur, START_1Y, END))
        best_hit = hit_pct(_clip(cur, START_1Y, END))
        for tag, rows in streams:
            if tag in used:
                continue
            merged = merge_cap(cur, rows, cap)
            n1 = len(_clip(merged, START_1Y, END))
            if n1 <= best_n:
                continue
            if not desk_ok(merged, seed_3y_hit):
                continue
            h1 = hit_pct(_clip(merged, START_1Y, END))
            if best is None or n1 > best_n or (n1 == best_n and h1 > best_hit):
                best = (tag, merged, h1)
                best_n = n1
                best_hit = h1
        if best:
            used.append(best[0])
            cur = best[1]
            improved = True
            if len(used) <= 15 or len(used) % 10 == 0:
                print(
                    f"    +{best[0][:72]} → n={best_n} hit={best_hit:.2f}",
                    flush=True,
                )
    return cur, used


def main() -> int:
    t0 = time.time()
    print(f"CHAMPION+ PUSH2 · beat {PRIOR_N} @>={FLOOR_1Y}%", flush=True)

    prior_tags = list(PRIOR_TAGS)
    if PRIOR.exists():
        prior_tags = list(
            (json.loads(PRIOR.read_text(encoding="utf-8")).get("stream_tags_research") or PRIOR_TAGS)
        )

    pool = json.loads(POOL.read_text(encoding="utf-8"))
    seed = hold._clean(
        _champ_floor([r for r in pool["champion"] if START_3Y <= r["day"] <= END])
    )
    for r in seed:
        r["track"] = "champion"
    sc0 = _agg(_clip(seed, START_1Y, END))
    sc0_3 = _agg(_clip(seed, START_3Y, END))
    seed_3y_hit = float(sc0_3.get("hit_pct") or 0)
    print(f"  seed {sc0.get('n')}@{sc0.get('hit_pct')}%", flush=True)

    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_3Y < d <= END]
    active = fs._active_days(sess, fs._load_daily()) if sess else set()
    gbr = path_u.get("good_by_risk") or {}

    print("  D10…", flush=True)
    d10 = load_d10()
    univ = {
        "CH": seed,
        "GDN": gbr.get("native") or [],
        "GD40": gbr.get("40.0") or gbr.get("40") or [],
        "GD35": gbr.get("35.0") or gbr.get("35") or [],
        "GD30": gbr.get("30.0") or gbr.get("30") or [],
        "D10": d10,
    }

    by = mine_all(univ, gaps, active)
    streams = pool_mix(by, prior_tags, lim=15000)
    print(f"  pool_mix streams={len(streams)}", flush=True)

    results = {"seed": {"1y": sc0, "3y": sc0_3}}
    lines = [
        "# CHAMPION+ PUSH2 — more calls @ ≥92.5%",
        "",
        f"**Prior best:** {PRIOR_N}@92.75% · **Seed:** {sc0.get('n')}@{sc0.get('hit_pct')}%",
        f"**Floor:** 1y ≥ {FLOOR_1Y}% · window `{START_1Y}`→`{END}`",
        "",
        "| Book | 1y N@hit | Δ vs seed | Δ vs prior | Streams |",
        "|---|---|---:|---:|---:|",
        f"| seed | {sc0.get('n')}@{sc0.get('hit_pct')} | 0 | {sc0.get('n')-PRIOR_N} | 0 |",
    ]

    best_mode = None
    best_n = -1
    best_rows = []
    best_tags: List[str] = []

    for cap in (2, 3):
        mode = f"cap{cap}"
        print(f"  greedy {mode} (warm prior)…", flush=True)
        rows, tags = greedy(seed, streams, seed_3y_hit, cap=cap, warm_tags=prior_tags)
        rows = hold._clean(rows)
        sc1 = _agg(_clip(rows, START_1Y, END))
        sc3 = _agg(_clip(rows, START_3Y, END))
        n = sc1.get("n") or 0
        results[mode] = {
            "ok": desk_ok(rows, seed_3y_hit),
            "1y": sc1,
            "3y": sc3,
            "streams": tags,
            "n_streams": len(tags),
            "delta_seed": n - (sc0.get("n") or 0),
            "delta_prior": n - PRIOR_N,
        }
        lines.append(
            f"| `CHAMPION_PLUS_{mode}` | **{n}@{sc1.get('hit_pct')}** | "
            f"+{n - (sc0.get('n') or 0)} | {n - PRIOR_N:+d} | {len(tags)} |"
        )
        print(
            f"    → {n}@{sc1.get('hit_pct')}% Δprior={n-PRIOR_N:+d} streams={len(tags)}",
            flush=True,
        )
        if results[mode]["ok"] and n > best_n:
            best_mode, best_n, best_rows, best_tags = mode, n, rows, tags

    if best_mode:
        calls = sorted(_clip(best_rows, START_1Y, END), key=lambda x: (x.get("day"), x.get("hm")))
        lines.extend(
            [
                "",
                f"## Calls — `{best_mode}`",
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
                f"**N={sc.get('n')}** · **{sc.get('hit_pct')}%** "
                f"({sc.get('wins')}W/{sc.get('losses')}L)",
                "",
                "### Streams",
                "",
            ]
        )
        for t in best_tags:
            lines.append(f"- `{t}`")
        lines.append("")

    if best_n > PRIOR_N:
        verdict = (
            f"PUSH2 OK — `{best_mode}` **{best_n}@"
            f"{results[best_mode]['1y'].get('hit_pct')}%** "
            f"(prior {PRIOR_N} · seed {sc0.get('n')}). Still RESEARCH."
        )
    elif best_n >= PRIOR_N:
        verdict = f"PUSH2 HOLD — matched prior {best_n}@{results[best_mode]['1y'].get('hit_pct')}%."
    else:
        verdict = (
            f"PUSH2 PARTIAL — best {best_n} below prior {PRIOR_N} "
            f"(still above seed {sc0.get('n')})."
        )

    elapsed = round(time.time() - t0, 1)
    lines.extend(["## Verdict", "", verdict, "", f"Elapsed {elapsed}s", ""])

    OUT.mkdir(parents=True, exist_ok=True)
    HOLD.mkdir(parents=True, exist_ok=True)
    md = OUT / "CHAMPION_PLUS_PUSH2_1Y.md"
    js = OUT / "CHAMPION_PLUS_PUSH2_1Y.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(
        json.dumps(
            {
                "verdict": verdict,
                "best_mode": best_mode,
                "results": results,
                "elapsed_s": elapsed,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    if best_mode and best_n >= PRIOR_N:
        (HOLD / "recipes_research.json").write_text(
            json.dumps(
                {
                    "status": "RESEARCH",
                    "desk": f"CHAMPION_PLUS_{best_mode.upper()}",
                    "seed": "CHAMPION",
                    "floor_1y": FLOOR_1Y,
                    "stream_tags_research": best_tags,
                    "research_1y": results[best_mode]["1y"],
                    "research_3y": results[best_mode]["3y"],
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
