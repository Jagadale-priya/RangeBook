"""Deeper Sensex ±50/50 research — more calls at HELD accuracy floors.

Held baseline (ACC100-WIDE @ ±50):
  1y 36@86.11% · 3y 55@80.0% · 3m 12@100%

Target: maximize N subject to hit_1y ≥ 86.0 and hit_3y ≥ 80.0
(same accuracy band), then near-miss (≥85/79) for options.

Expansions:
  - denser p / or_ext / time / cont / cap / regime grids
  - entry rankers: max p_t1 · earliest hm · first_break prefer
  - stream unions of complementary gate sets (unique day/side/hm)

  python -u prod_live/tests/builders/research_sensex_t50_more_calls_same_acc.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import timedelta
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live" / "tests" / "builders")]
import path_setup  # noqa: F401,E402

from research_bn_sensex_final_brackets import (  # noqa: E402
    day_cap,
    load_tape,
    normalize_cand,
    path_score_pool,
)
from research_sensex_modal_1y_deep import apply_policy, hit_pct, month_rollup  # noqa: E402
from research_sensex_acc100_ladder_sl_probe import day1_accurate  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "SENSEX_T50_MORE_CALLS_SAME_ACC.md"
OUT_JSON = OUT / "SENSEX_T50_MORE_CALLS_SAME_ACC.json"
CANDS = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_full_live_candidates.json"
)
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_5m_kite.csv"

END = "2026-11-19"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_3M = (pd.Timestamp(END) - timedelta(days=92)).strftime("%Y-%m-%d")
SL = T1 = 50.0

FLOOR_1Y = 86.0
FLOOR_3Y = 80.0
NEAR_1Y = 85.0
NEAR_3Y = 79.0

HELD_POL = {
    "name": "HELD_WIDE",
    "buy_min_p": 0.55,
    "sell_min_p": 0.70,
    "buy_first_only": True,
    "sell_first_only": True,
    "allow_sell_cont": False,
    "buy_max_or_ext": 0.15,
    "buy_regimes": ["range", "mixed", "trend", "volatile"],
}


def key(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day"))[:10], str(r.get("decision")), str(r.get("hm"))[:5])


def win_stats(rows: List[dict], a: str, b: str) -> Dict[str, Any]:
    rr = [r for r in rows if a <= str(r.get("day") or "")[:10] <= b]
    known = [r for r in rr if r.get("win") is not None]
    w = sum(1 for r in known if r.get("win"))
    return {
        "n": len(rr),
        "hit_pct": hit_pct(rr),
        "wins": w,
        "losses": len(known) - w,
        "expect_pts": round((w * T1 - (len(known) - w) * SL) / len(rr), 2) if rr else None,
        "by_month": month_rollup(rr),
        "by_side": {
            s: sum(1 for r in rr if r.get("decision") == s) for s in ("BUY", "SELL")
        },
    }


def rank_day_side(rows: List[dict], how: str) -> List[dict]:
    """Cap-style but with explicit ranking within day+side."""
    from collections import defaultdict

    by: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for r in rows:
        by[(str(r.get("day"))[:10], str(r.get("decision")))].append(r)

    def sort_key(r: dict):
        p = float(r.get("p_t1") or 0)
        hm = str(r.get("hm") or "")
        fb = 0 if r.get("first_break") else 1
        if how == "max_p":
            return (-p, hm)
        if how == "earliest":
            return (hm, -p)
        if how == "first_break_p":
            return (fb, -p, hm)
        return (-p, hm)

    out: List[dict] = []
    for _, grp in by.items():
        grp = sorted(grp, key=sort_key)
        seen = set()
        for r in grp:
            hm = str(r.get("hm") or "")
            if hm in seen:
                continue
            seen.add(hm)
            out.append(r)
            # caller applies numeric cap separately
    return out


def score_pool(
    bars,
    ix,
    pool: List[dict],
    *,
    cap: int,
    mode: str,
    rank: str = "max_p",
) -> List[dict]:
    scored = path_score_pool(bars, ix, pool, SL, T1)
    if mode == "day":
        return day1_accurate(scored)
    # re-rank then day_cap
    ranked = rank_day_side(scored, rank)
    return day_cap(ranked, cap)


def eval_pol(
    bars,
    ix,
    cands: List[dict],
    pol: Dict[str, Any],
    *,
    cap: int = 3,
    mode: str = "cap",
    rank: str = "max_p",
) -> Dict[str, Any]:
    pool = apply_policy(cands, pol)
    scored = score_pool(bars, ix, pool, cap=cap, mode=mode, rank=rank)
    return {
        "policy": pol,
        "cap": cap,
        "mode": mode,
        "rank": rank,
        "pool_n": len(pool),
        "1y": win_stats(scored, START_1Y, END),
        "3y": win_stats(scored, START_3Y, END),
        "3m": win_stats(scored, START_3M, END),
        "calls": scored,
    }


def meets(r: Dict[str, Any], f1: float, f3: float) -> bool:
    h1, h3 = r["1y"]["hit_pct"], r["3y"]["hit_pct"]
    return (
        h1 is not None
        and h3 is not None
        and h1 + 1e-9 >= f1
        and h3 + 1e-9 >= f3
        and r["1y"]["n"] >= 10
    )


def slim(r: Dict[str, Any]) -> Dict[str, Any]:
    p = r["policy"]
    return {
        "name": p.get("name"),
        "buy_min_p": p.get("buy_min_p"),
        "sell_min_p": p.get("sell_min_p"),
        "buy_max_or_ext": p.get("buy_max_or_ext"),
        "sell_max_or_ext": p.get("sell_max_or_ext"),
        "max_mins": p.get("max_mins"),
        "allow_sell_cont": p.get("allow_sell_cont"),
        "buy_regimes_n": len(p.get("buy_regimes") or []),
        "cap": r.get("cap"),
        "mode": r.get("mode"),
        "rank": r.get("rank"),
        "n_1y": r["1y"]["n"],
        "hit_1y": r["1y"]["hit_pct"],
        "n_3y": r["3y"]["n"],
        "hit_3y": r["3y"]["hit_pct"],
        "n_3m": r["3m"]["n"],
        "hit_3m": r["3m"]["hit_pct"],
        "expect_1y": r["1y"]["expect_pts"],
        "side_1y": r["1y"]["by_side"],
    }


def union_streams(
    bars,
    ix,
    stream_rows: List[List[dict]],
    *,
    cap: int,
    rank: str = "max_p",
) -> List[dict]:
    """Union unique day/side/hm then re-cap."""
    m: Dict[Tuple[str, str, str], dict] = {}
    for rows in stream_rows:
        for r in rows:
            k = key(r)
            if k not in m:
                m[k] = r
            else:
                # keep higher p
                if float(r.get("p_t1") or 0) > float(m[k].get("p_t1") or 0):
                    m[k] = r
    merged = list(m.values())
    return score_pool(bars, ix, merged, cap=cap, mode="cap", rank=rank)


def main() -> int:
    t0 = time.time()
    print(
        f"Sensex ±50 deeper · floors 1y≥{FLOOR_1Y}% 3y≥{FLOOR_3Y}%",
        flush=True,
    )
    bars, ix = load_tape(TAPE5)
    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    cands: List[dict] = []
    for row in raw:
        n = normalize_cand(row)
        if not n or n["day"] < START_3Y or n["day"] > END:
            continue
        n["or_ext"] = float(row.get("or_ext") if row.get("or_ext") is not None else 9)
        n["regime"] = str(row.get("regime") or "")
        n["mins"] = row.get("mins")
        n["first_break"] = bool(row.get("first_break"))
        cands.append(n)

    held = eval_pol(bars, ix, cands, HELD_POL, cap=3, mode="cap", rank="max_p")
    print(
        f"  HELD: 1y {held['1y']['n']}@{held['1y']['hit_pct']}% · "
        f"3y {held['3y']['n']}@{held['3y']['hit_pct']}% · "
        f"3m {held['3m']['n']}@{held['3m']['hit_pct']}%",
        flush=True,
    )

    # Focused grid: held is already tight; search nearby expansions only.
    buy_mins = [0.50, 0.55, 0.58]
    sell_mins = [0.62, 0.65, 0.68, 0.70, 0.72, 0.75]
    buy_ors: List[Optional[float]] = [0.10, 0.15, 0.20, 0.25, None]
    sell_ors: List[Optional[float]] = [None, 0.40]
    max_mins_opts: List[Optional[int]] = [None, 12 * 60 + 30, 14 * 60]
    caps = [2, 3, 4]
    ranks = ["max_p", "earliest"]
    buy_regs = [
        ["range", "mixed", "trend", "volatile"],
        ["range", "mixed"],
    ]

    kept_same: List[Dict[str, Any]] = []
    kept_near: List[Dict[str, Any]] = []
    n_tried = 0

    # Phase A: first-only around held gates (~3*6*5*2*3*2*3*2 ≈ 6500)
    for buy_min, sell_min, buy_or, sell_or, max_mins, regs, cap, rank in product(
        buy_mins,
        sell_mins,
        buy_ors,
        sell_ors,
        max_mins_opts,
        buy_regs,
        caps,
        ranks,
    ):
        # prune weak/redundant
        if buy_min < 0.55 and buy_or is None and sell_min < 0.68:
            continue  # too loose for 86/80 usually
        if rank == "earliest" and cap == 2 and sell_or is not None:
            continue
        pol = {
            "name": (
                f"b{buy_min}_s{sell_min}_bor{buy_or}_sor{sell_or}_m{max_mins}"
                f"_r{len(regs)}_C{cap}_{rank}"
            ),
            "buy_min_p": buy_min,
            "sell_min_p": sell_min,
            "buy_first_only": True,
            "sell_first_only": True,
            "allow_sell_cont": False,
            "buy_max_or_ext": buy_or,
            "sell_max_or_ext": sell_or,
            "max_mins": max_mins,
            "buy_regimes": regs,
        }
        n_tried += 1
        res = eval_pol(bars, ix, cands, pol, cap=cap, mode="cap", rank=rank)
        if meets(res, FLOOR_1Y, FLOOR_3Y):
            kept_same.append(res)
        elif meets(res, NEAR_1Y, NEAR_3Y):
            kept_near.append(res)
        if n_tried % 500 == 0:
            print(
                f"  …{n_tried} · same_acc={len(kept_same)} near={len(kept_near)}",
                flush=True,
            )

    print(f"  phaseA tried={n_tried} same={len(kept_same)} near={len(kept_near)}", flush=True)

    # Phase B: limited SELL-cont around best first-only seeds
    seeds = sorted(
        kept_same or kept_near,
        key=lambda r: (-r["1y"]["n"], -float(r["1y"]["hit_pct"])),
    )[:25]
    for seed in seeds:
        sp = dict(seed["policy"])
        for cont_min, cont_max, cont_p_boost, cap in product(
            [0.10, 0.15], [0.40, 0.50], [0.0, 0.03], [3, 4]
        ):
            pol = {
                **sp,
                "allow_sell_cont": True,
                "cont_sell_min_p": float(sp["sell_min_p"]) + cont_p_boost,
                "cont_min_or_ext": cont_min,
                "cont_max_or_ext": cont_max,
                "cont_max_mins": 12 * 60 + 30,
                "name": f"{sp.get('name')}_CONT_{cont_min}_{cont_max}_C{cap}",
            }
            n_tried += 1
            res = eval_pol(
                bars, ix, cands, pol, cap=cap, mode="cap", rank=seed.get("rank") or "max_p"
            )
            if meets(res, FLOOR_1Y, FLOOR_3Y):
                kept_same.append(res)
            elif meets(res, NEAR_1Y, NEAR_3Y):
                kept_near.append(res)

    print(f"  phaseB after cont · same={len(kept_same)} near={len(kept_near)}", flush=True)

    # Phase C: stream unions — take diverse high-N same-acc policies and union
    def dedupe_res(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        out = []
        for r in rows:
            sig = (
                r["1y"]["n"],
                r["1y"]["hit_pct"],
                r["3y"]["n"],
                r["3y"]["hit_pct"],
                r["policy"].get("buy_min_p"),
                r["policy"].get("sell_min_p"),
                r["policy"].get("buy_max_or_ext"),
                r["policy"].get("sell_max_or_ext"),
                r["policy"].get("max_mins"),
                r["policy"].get("allow_sell_cont"),
                r.get("cap"),
                r.get("rank"),
                tuple(r["policy"].get("buy_regimes") or []),
            )
            if sig in seen:
                continue
            seen.add(sig)
            out.append(r)
        return out

    kept_same = dedupe_res(kept_same)
    kept_near = dedupe_res(kept_near)

    union_hits: List[Dict[str, Any]] = []
    # build call lists for top same-acc streams
    top_streams = sorted(kept_same, key=lambda r: (-r["1y"]["n"], -float(r["1y"]["hit_pct"])))[:12]
    # also include held
    stream_calls = [held["calls"]] + [r["calls"] for r in top_streams]

    # pairwise + triple unions of distinct streams
    from itertools import combinations

    for k in (2, 3):
        for combo in combinations(range(len(stream_calls)), k):
            rows = [stream_calls[i] for i in combo]
            for cap in (3, 4):
                merged = union_streams(bars, ix, rows, cap=cap, rank="max_p")
                # wrap as eval-like
                res = {
                    "policy": {
                        "name": f"UNION_{'+'.join(str(i) for i in combo)}_C{cap}",
                        "buy_min_p": None,
                        "sell_min_p": None,
                        "allow_sell_cont": None,
                        "buy_regimes": [],
                        "streams": list(combo),
                    },
                    "cap": cap,
                    "mode": "union",
                    "rank": "max_p",
                    "1y": win_stats(merged, START_1Y, END),
                    "3y": win_stats(merged, START_3Y, END),
                    "3m": win_stats(merged, START_3M, END),
                    "calls": merged,
                }
                n_tried += 1
                if meets(res, FLOOR_1Y, FLOOR_3Y):
                    union_hits.append(res)
                elif meets(res, NEAR_1Y, NEAR_3Y):
                    kept_near.append(res)

    print(f"  unions same_acc={len(union_hits)}", flush=True)
    all_same = dedupe_res(kept_same + union_hits)

    def best(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not rows:
            return None
        return sorted(
            rows,
            key=lambda r: (
                -r["1y"]["n"],
                -float(r["1y"]["hit_pct"]),
                -float(r["3y"]["hit_pct"]),
                -float(r["1y"]["expect_pts"] or 0),
            ),
        )[0]

    best_same = best(all_same)
    best_near = best(kept_near)
    # also best hit among same-acc with n >= held
    best_quality = None
    cq = [r for r in all_same if r["1y"]["n"] >= held["1y"]["n"]]
    if cq:
        best_quality = sorted(
            cq,
            key=lambda r: (
                -float(r["1y"]["hit_pct"]),
                -r["1y"]["n"],
                -float(r["3y"]["hit_pct"]),
            ),
        )[0]

    elapsed = round(time.time() - t0, 1)

    top_same = sorted(all_same, key=lambda r: (-r["1y"]["n"], -float(r["1y"]["hit_pct"])))[:20]
    top_near = sorted(kept_near, key=lambda r: (-r["1y"]["n"], -float(r["1y"]["hit_pct"])))[:15]

    payload = {
        "clip": {"sl": SL, "t1": T1},
        "floors": {"1y": FLOOR_1Y, "3y": FLOOR_3Y, "near_1y": NEAR_1Y, "near_3y": NEAR_3Y},
        "elapsed_s": elapsed,
        "tried": n_tried,
        "held": slim(held),
        "held_by_month_1y": held["1y"]["by_month"],
        "n_same_acc": len(all_same),
        "n_near": len(kept_near),
        "best_same_acc": slim(best_same) if best_same else None,
        "best_near": slim(best_near) if best_near else None,
        "best_quality_same_acc": slim(best_quality) if best_quality else None,
        "top_same_acc": [slim(r) for r in top_same],
        "top_near": [slim(r) for r in top_near],
        "best_same_calls_1y": [
            {
                "day": r.get("day"),
                "hm": r.get("hm"),
                "decision": r.get("decision"),
                "p_t1": r.get("p_t1"),
                "win": r.get("win"),
                "points": r.get("points"),
                "outcome": r.get("outcome"),
            }
            for r in (
                [x for x in (best_same or {}).get("calls", []) if START_1Y <= str(x.get("day"))[:10] <= END]
                if best_same
                else []
            )
        ],
        "best_same_by_month_1y": (best_same or {}).get("1y", {}).get("by_month") if best_same else None,
        "delta_vs_held": None,
    }
    if best_same:
        payload["delta_vs_held"] = {
            "dn_1y": best_same["1y"]["n"] - held["1y"]["n"],
            "dhit_1y": round(float(best_same["1y"]["hit_pct"]) - float(held["1y"]["hit_pct"]), 2),
            "dn_3m": best_same["3m"]["n"] - held["3m"]["n"],
            "dhit_3m": round(
                float(best_same["3m"]["hit_pct"] or 0) - float(held["3m"]["hit_pct"] or 0), 2
            ),
        }

    OUT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def fmt(r: Optional[dict]) -> str:
        if not r:
            return "none"
        return (
            f"1y {r['n_1y']}@{r['hit_1y']}% · 3y {r['n_3y']}@{r['hit_3y']}% · "
            f"3m {r['n_3m']}@{r['hit_3m']}% · Cap{r.get('cap')} {r.get('mode')}/{r.get('rank')} · "
            f"B≥{r.get('buy_min_p')} S≥{r.get('sell_min_p')} bor={r.get('buy_max_or_ext')} "
            f"sor={r.get('sell_max_or_ext')} mins={r.get('max_mins')} "
            f"{'CONT' if r.get('allow_sell_cont') else 'first'} · `{r.get('name')}`"
        )

    lines = [
        "# SENSEX ±50 · more calls at same accuracy",
        "",
        f"**Clip:** ±{SL:g}/{T1:g}",
        f"**Floors (same acc):** 1y ≥ {FLOOR_1Y}% · 3y ≥ {FLOOR_3Y}%",
        f"**Near band:** 1y ≥ {NEAR_1Y}% · 3y ≥ {NEAR_3Y}%",
        f"**Tried:** {n_tried} · same-acc hits={len(all_same)} · near={len(kept_near)} · {elapsed}s",
        "",
        "## Held baseline",
        "",
        f"- {fmt(slim(held))}",
        "",
        "## Best at same accuracy",
        "",
        f"- **max N:** {fmt(payload['best_same_acc'])}",
        f"- **best hit (≥ held N):** {fmt(payload['best_quality_same_acc'])}",
        f"- **delta vs held:** {payload['delta_vs_held']}",
        "",
        "## Best near band (if useful)",
        "",
        f"- {fmt(payload['best_near'])}",
        "",
        "## Top same-acc (max N)",
        "",
        "| N1y | Hit1y | N3y | Hit3y | N3m | Hit3m | B≥ | S≥ | bor | Cont | Cap | Rank |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|",
    ]
    for r in payload["top_same_acc"]:
        lines.append(
            f"| {r['n_1y']} | {r['hit_1y']} | {r['n_3y']} | {r['hit_3y']} | {r['n_3m']} | {r['hit_3m']} | "
            f"{r.get('buy_min_p')} | {r.get('sell_min_p')} | {r.get('buy_max_or_ext')} | "
            f"{'Y' if r.get('allow_sell_cont') else 'N'} | {r.get('cap')} | {r.get('rank')} |"
        )

    if best_same:
        lines += [
            "",
            "### Best same-acc · 1y per month",
            "",
            "| Month | N | Hit | W/L |",
            "|---|---:|---:|---|",
        ]
        for m, st in (payload.get("best_same_by_month_1y") or {}).items():
            lines.append(f"| {m} | {st['n']} | {st['hit_pct']} | {st['wins']}/{st['losses']} |")

        lines += [
            "",
            "### Best same-acc · 1y calls",
            "",
            "| Day | HM | Side | p_t1 | Win | Pts | Outcome |",
            "|---|---|---|---:|---|---:|---|",
        ]
        for r in payload["best_same_calls_1y"]:
            w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "open")
            lines.append(
                f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | {r.get('p_t1')} | "
                f"{w} | {r.get('points')} | {r.get('outcome')} |"
            )

    lines += [
        "",
        "_Generated by `tests/builders/research_sensex_t50_more_calls_same_acc.py`_",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_MD}", flush=True)
    print(f"HELD  {fmt(slim(held))}", flush=True)
    print(f"BEST  {fmt(payload['best_same_acc'])}", flush=True)
    print(f"DELTA {payload['delta_vs_held']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
