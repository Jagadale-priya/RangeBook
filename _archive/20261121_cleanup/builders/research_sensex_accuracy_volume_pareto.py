"""Sensex deep Pareto — max accuracy with multiple calls (1y + 3y check).

Expands modal v2 research:
  - denser p / or_ext / time / cont grids
  - clip × cap
  - Pareto: max hit @ N≥{15,20,30,40,50,60} and max N @ hit≥{90,92,94,95,96,97}

  python -u prod_live/tests/builders/research_sensex_accuracy_volume_pareto.py
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

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "SENSEX_ACCURACY_VOLUME_PARETO.md"
OUT_JSON = OUT / "SENSEX_ACCURACY_VOLUME_PARETO.json"
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


def score(
    bars,
    ix,
    cands: List[dict],
    pol: Dict[str, Any],
    sl: float,
    t1: float,
    cap: int,
) -> Dict[str, Any]:
    pool = apply_policy(cands, pol)
    scored = day_cap(path_score_pool(bars, ix, pool, sl, t1), cap)
    known = [r for r in scored if r.get("win") is not None]
    w = sum(1 for r in known if r.get("win"))
    return {
        "policy": pol,
        "clip": {"sl": sl, "t1": t1},
        "cap": cap,
        "pool_n": len(pool),
        "n": len(scored),
        "settled": len(known),
        "hit_pct": hit_pct(scored),
        "wins": w,
        "losses": len(known) - w,
        "expect_pts": round((w * t1 - (len(known) - w) * sl) / len(scored), 2) if scored else None,
        "by_side": {
            s: sum(1 for r in scored if r.get("decision") == s) for s in ("BUY", "SELL")
        },
        "by_month": month_rollup(scored),
    }


def clip_1y(cands: List[dict]) -> List[dict]:
    return [c for c in cands if START_1Y <= c["day"] <= END]


def clip_3y(cands: List[dict]) -> List[dict]:
    return [c for c in cands if START_3Y <= c["day"] <= END]


def main() -> int:
    t0 = time.time()
    print(f"Sensex accuracy×volume Pareto · 1y {START_1Y}→{END}", flush=True)
    bars, ix = load_tape(TAPE5)
    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    all_cands: List[dict] = []
    for row in raw:
        n = normalize_cand(row)
        if not n or n["day"] < START_3Y or n["day"] > END:
            continue
        n["or_ext"] = float(row.get("or_ext") if row.get("or_ext") is not None else 9)
        n["regime"] = str(row.get("regime") or "")
        n["mins"] = row.get("mins")
        n["first_break"] = bool(row.get("first_break"))
        all_cands.append(n)
    c1 = clip_1y(all_cands)
    print(f"  cands 1y={len(c1)} 3y={len(all_cands)} tape={len(bars)}", flush=True)

    # baselines
    baselines = [
        ("v2_locked", {"buy_min_p": 0.55, "sell_min_p": 0.55, "buy_first_only": True,
                       "sell_first_only": True, "allow_sell_cont": False,
                       "buy_regimes": ["range", "mixed", "trend", "volatile"]}, 120, 120, 3),
        ("prior_070", {"buy_min_p": 0.55, "sell_min_p": 0.70, "buy_first_only": True,
                       "sell_first_only": True, "allow_sell_cont": False,
                       "buy_regimes": ["range", "mixed", "trend", "volatile"]}, 100, 100, 3),
        ("elite_065_t120", {"buy_min_p": 0.55, "sell_min_p": 0.65, "buy_first_only": True,
                            "sell_first_only": True, "allow_sell_cont": False,
                            "buy_regimes": ["range", "mixed", "trend", "volatile"]}, 120, 120, 3),
    ]

    base_rows = []
    for name, pol, sl, t1, cap in baselines:
        pol = {**pol, "name": name}
        r = score(bars, ix, c1, pol, float(sl), float(t1), cap)
        # 3y check same gates
        r3 = score(bars, ix, all_cands, pol, float(sl), float(t1), cap)
        r["hit_3y"] = r3["hit_pct"]
        r["n_3y"] = r3["n"]
        base_rows.append(r)
        print(f"  BASE {name}: 1y {r['n']}@{r['hit_pct']}% · 3y {r3['n']}@{r3['hit_pct']}%", flush=True)

    buy_mins = [0.50, 0.55, 0.58, 0.60, 0.62]
    sell_mins = [0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70, 0.72, 0.75]
    clips = [
        (80.0, 80.0),
        (100.0, 100.0),
        (120.0, 120.0),
        (100.0, 120.0),
        (80.0, 120.0),
        (120.0, 150.0),
        (150.0, 150.0),
    ]
    caps = [2, 3, 4]
    cont_opts = [False, True]
    # time / or filters (SELL first)
    sell_max_or_opts: List[Optional[float]] = [None, 0.25, 0.40, 0.60]
    buy_max_or_opts: List[Optional[float]] = [None, 0.15, 0.25, 0.40]
    max_mins_opts: List[Optional[int]] = [None, 12 * 60 + 30, 13 * 60, 14 * 60]
    buy_reg_opts = [
        ["range", "mixed", "trend", "volatile"],
        ["range", "mixed"],
        ["range", "mixed", "trend"],
    ]

    # Phase A: core dense grid (no or/time) — fast cover
    grid: List[Dict[str, Any]] = []
    for buy_min, sell_min, (sl, t1), cap, cont, regs in product(
        buy_mins, sell_mins, clips, caps, cont_opts, buy_reg_opts
    ):
        pol = {
            "name": f"b{buy_min}_s{sell_min}_{'c' if cont else 'f'}_r{len(regs)}_T{int(t1)}SL{int(sl)}_C{cap}",
            "buy_min_p": buy_min,
            "sell_min_p": sell_min,
            "buy_first_only": True,
            "sell_first_only": True,
            "allow_sell_cont": cont,
            "cont_sell_min_p": max(sell_min, 0.58),
            "cont_min_or_ext": 0.15,
            "cont_max_or_ext": 0.40,
            "cont_max_mins": 12 * 60 + 30,
            "buy_regimes": regs,
        }
        r = score(bars, ix, c1, pol, sl, t1, cap)
        if r["n"] < 8 or r["hit_pct"] is None:
            continue
        grid.append({k: v for k, v in r.items() if k != "by_month"})

    print(f"  phaseA kept={len(grid)}", flush=True)

    # Phase B: refine top hit configs with or_ext / time filters (first-only only)
    seeds = sorted(grid, key=lambda r: (-float(r["hit_pct"]), -r["n"]))[:40]
    seeds += sorted(
        [r for r in grid if r["hit_pct"] >= 94 and r["n"] >= 25],
        key=lambda r: (-r["n"], -float(r["hit_pct"])),
    )[:40]
    # unique by policy name+clip+cap
    seen = set()
    refine_seeds = []
    for r in seeds:
        key = (r["policy"]["name"], r["clip"]["sl"], r["clip"]["t1"], r["cap"])
        if key in seen:
            continue
        seen.add(key)
        refine_seeds.append(r)

    refined: List[Dict[str, Any]] = []
    for seed in refine_seeds:
        base_pol = dict(seed["policy"])
        if base_pol.get("allow_sell_cont"):
            continue  # keep cont as-is from phase A
        for buy_or, sell_or, max_mins in product(buy_max_or_opts, sell_max_or_opts, max_mins_opts):
            pol = {
                **base_pol,
                "buy_max_or_ext": buy_or,
                "sell_max_or_ext": sell_or,
                "max_mins": max_mins,
                "name": (
                    f"{base_pol['name']}_bor{buy_or}_sor{sell_or}_m{max_mins}"
                ),
            }
            r = score(
                bars,
                ix,
                c1,
                pol,
                seed["clip"]["sl"],
                seed["clip"]["t1"],
                int(seed["cap"]),
            )
            if r["n"] < 8 or r["hit_pct"] is None:
                continue
            refined.append({k: v for k, v in r.items() if k != "by_month"})

    print(f"  phaseB refined={len(refined)}", flush=True)
    all_rows = grid + refined

    # dedupe by (n, hit, clip, cap, key gates)
    def sig(r):
        p = r["policy"]
        return (
            r["n"],
            r["hit_pct"],
            r["clip"]["sl"],
            r["clip"]["t1"],
            r["cap"],
            p.get("buy_min_p"),
            p.get("sell_min_p"),
            p.get("allow_sell_cont"),
            p.get("buy_max_or_ext"),
            p.get("sell_max_or_ext"),
            p.get("max_mins"),
            tuple(p.get("buy_regimes") or []),
        )

    uniq = {}
    for r in all_rows:
        uniq[sig(r)] = r
    rows = list(uniq.values())
    print(f"  unique={len(rows)}", flush=True)

    def best_hit_at_n(n_min: int) -> Optional[dict]:
        c = [r for r in rows if r["n"] >= n_min and r["hit_pct"] is not None]
        if not c:
            return None
        return sorted(c, key=lambda r: (-float(r["hit_pct"]), -r["n"], -float(r["expect_pts"] or 0)))[0]

    def best_n_at_hit(floor: float) -> Optional[dict]:
        c = [r for r in rows if r["hit_pct"] is not None and r["hit_pct"] + 1e-9 >= floor and r["n"] >= 10]
        if not c:
            return None
        return sorted(c, key=lambda r: (-r["n"], -float(r["hit_pct"]), -float(r["expect_pts"] or 0)))[0]

    def best_expect_at_hit(floor: float, n_min: int = 20) -> Optional[dict]:
        c = [
            r
            for r in rows
            if r["hit_pct"] is not None
            and r["hit_pct"] + 1e-9 >= floor
            and r["n"] >= n_min
            and r.get("expect_pts") is not None
        ]
        if not c:
            return None
        return sorted(c, key=lambda r: (-float(r["expect_pts"]), -r["n"], -float(r["hit_pct"])))[0]

    picks = {
        "best_hit_n15": best_hit_at_n(15),
        "best_hit_n20": best_hit_at_n(20),
        "best_hit_n30": best_hit_at_n(30),
        "best_hit_n40": best_hit_at_n(40),
        "best_hit_n50": best_hit_at_n(50),
        "best_hit_n60": best_hit_at_n(60),
        "max_n_hit90": best_n_at_hit(90),
        "max_n_hit92": best_n_at_hit(92),
        "max_n_hit94": best_n_at_hit(94),
        "max_n_hit95": best_n_at_hit(95),
        "max_n_hit96": best_n_at_hit(96),
        "max_n_hit97": best_n_at_hit(97),
        "best_expect_hit94_n20": best_expect_at_hit(94, 20),
        "best_expect_hit95_n20": best_expect_at_hit(95, 20),
        "best_expect_hit96_n20": best_expect_at_hit(96, 20),
    }

    # recommend: highest hit with N≥30 and hit≥94; else best hit N≥30; prefer first-only
    cand_rec = [
        r
        for r in rows
        if r["n"] >= 30
        and r["hit_pct"] is not None
        and r["hit_pct"] >= 94
        and not r["policy"].get("allow_sell_cont")
    ]
    if not cand_rec:
        cand_rec = [r for r in rows if r["n"] >= 30 and r["hit_pct"] is not None]
    recommended = sorted(
        cand_rec,
        key=lambda r: (-float(r["hit_pct"]), -r["n"], -float(r["expect_pts"] or 0)),
    )[0]

    # 3y validate recommended + v2 + elite
    def with_3y(r: dict) -> dict:
        rr = dict(r)
        r3 = score(
            bars,
            ix,
            all_cands,
            r["policy"],
            r["clip"]["sl"],
            r["clip"]["t1"],
            int(r["cap"]),
        )
        rr["n_3y"] = r3["n"]
        rr["hit_3y"] = r3["hit_pct"]
        rr["expect_3y"] = r3["expect_pts"]
        rr["by_month"] = month_rollup(
            day_cap(
                path_score_pool(
                    bars,
                    ix,
                    apply_policy(c1, r["policy"]),
                    r["clip"]["sl"],
                    r["clip"]["t1"],
                ),
                int(r["cap"]),
            )
        )
        return rr

    recommended = with_3y(recommended)
    for k, v in list(picks.items()):
        if v:
            picks[k] = with_3y(v)

    # top 20 by hit (n≥25) and top 20 by n (hit≥94)
    top_hit = sorted(
        [r for r in rows if r["n"] >= 25],
        key=lambda r: (-float(r["hit_pct"]), -r["n"]),
    )[:20]
    top_vol = sorted(
        [r for r in rows if r["hit_pct"] is not None and r["hit_pct"] >= 94],
        key=lambda r: (-r["n"], -float(r["hit_pct"])),
    )[:20]

    elapsed = round(time.time() - t0, 1)

    def slim(r: Optional[dict]) -> Optional[dict]:
        if not r:
            return None
        p = r["policy"]
        return {
            "n": r["n"],
            "hit_pct": r["hit_pct"],
            "expect_pts": r.get("expect_pts"),
            "n_3y": r.get("n_3y"),
            "hit_3y": r.get("hit_3y"),
            "clip": r["clip"],
            "cap": r["cap"],
            "buy_min_p": p.get("buy_min_p"),
            "sell_min_p": p.get("sell_min_p"),
            "allow_sell_cont": p.get("allow_sell_cont"),
            "buy_max_or_ext": p.get("buy_max_or_ext"),
            "sell_max_or_ext": p.get("sell_max_or_ext"),
            "max_mins": p.get("max_mins"),
            "buy_regimes_n": len(p.get("buy_regimes") or []),
            "name": p.get("name"),
            "by_month": r.get("by_month"),
        }

    payload = {
        "window_1y": {"start": START_1Y, "end": END},
        "window_3y": {"start": START_3Y, "end": END},
        "elapsed_s": elapsed,
        "grid_unique": len(rows),
        "baselines": [slim(r) for r in base_rows],
        "recommended": slim(recommended),
        "picks": {k: slim(v) for k, v in picks.items()},
        "top_hit_n25": [slim(r) for r in top_hit],
        "top_vol_hit94": [slim(r) for r in top_vol],
        "verdict": (
            "Prefer highest 1y hit with N≥30, first-only, and 3y hit not collapsing "
            "below ~88%. Volume via SELL-cont usually caps near 88–90%."
        ),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def fmt(r: Optional[dict]) -> str:
        if not r:
            return "none"
        return (
            f"n={r['n']} hit={r['hit_pct']}% E={r.get('expect_pts')} · "
            f"3y {r.get('n_3y')}@{r.get('hit_3y')}% · "
            f"±{r['clip']['sl']:g}/{r['clip']['t1']:g} Cap{r['cap']} · "
            f"B≥{r['buy_min_p']} S≥{r['sell_min_p']} "
            f"{'CONT' if r.get('allow_sell_cont') else 'first'} "
            f"bor={r.get('buy_max_or_ext')} sor={r.get('sell_max_or_ext')} mins={r.get('max_mins')}"
        )

    lines = [
        "# SENSEX · accuracy × volume Pareto (deep)",
        "",
        f"**1y:** `{START_1Y}` → `{END}` · **3y check** on same gates",
        f"**Configs scored:** {len(rows)} unique · elapsed {elapsed}s",
        "",
        "## Baselines",
        "",
    ]
    for r in payload["baselines"]:
        lines.append(f"- `{r['name'] if False else ''}` {fmt(r)}")
    # fix baselines names from original
    lines = [
        "# SENSEX · accuracy × volume Pareto (deep)",
        "",
        f"**1y:** `{START_1Y}` → `{END}` · **3y check** on same gates",
        f"**Configs scored:** {len(rows)} unique · elapsed {elapsed}s",
        "",
        "## Baselines",
        "",
    ]
    for b, r in zip(baselines, payload["baselines"]):
        lines.append(f"- **{b[0]}:** {fmt(r)}")

    rec = payload["recommended"]
    lines += [
        "",
        "## Recommended (high accuracy + multiple calls)",
        "",
        f"- **{fmt(rec)}**",
        "",
        "| Month | N | Hit% | W/L |",
        "|---|---:|---:|---|",
    ]
    for m, st in (rec.get("by_month") or {}).items():
        lines.append(f"| {m} | {st['n']} | {st['hit_pct']} | {st['wins']}/{st['losses']} |")

    lines += ["", "## Pareto — best hit at N floor", ""]
    for k in ("best_hit_n15", "best_hit_n20", "best_hit_n30", "best_hit_n40", "best_hit_n50", "best_hit_n60"):
        lines.append(f"- **{k}:** {fmt(payload['picks'].get(k))}")

    lines += ["", "## Pareto — max N at hit floor", ""]
    for k in ("max_n_hit90", "max_n_hit92", "max_n_hit94", "max_n_hit95", "max_n_hit96", "max_n_hit97"):
        lines.append(f"- **{k}:** {fmt(payload['picks'].get(k))}")

    lines += ["", "## Best expectancy @ high hit", ""]
    for k in ("best_expect_hit94_n20", "best_expect_hit95_n20", "best_expect_hit96_n20"):
        lines.append(f"- **{k}:** {fmt(payload['picks'].get(k))}")

    lines += [
        "",
        "## Top hit (N≥25)",
        "",
        "| N | Hit% | E | 3y N/Hit | B≥ | S≥ | Cont | Clip | Cap |",
        "|---:|---:|---:|---|---:|---:|---|---|---:|",
    ]
    for r in payload["top_hit_n25"]:
        lines.append(
            f"| {r['n']} | {r['hit_pct']} | {r.get('expect_pts')} | "
            f"{r.get('n_3y')}@{r.get('hit_3y')} | {r['buy_min_p']} | {r['sell_min_p']} | "
            f"{'Y' if r.get('allow_sell_cont') else 'N'} | "
            f"{r['clip']['sl']:g}/{r['clip']['t1']:g} | {r['cap']} |"
        )

    lines += [
        "",
        "## Top volume (hit≥94%)",
        "",
        "| N | Hit% | E | 3y N/Hit | B≥ | S≥ | Cont | Clip | Cap |",
        "|---:|---:|---:|---|---:|---:|---|---|---:|",
    ]
    for r in payload["top_vol_hit94"]:
        lines.append(
            f"| {r['n']} | {r['hit_pct']} | {r.get('expect_pts')} | "
            f"{r.get('n_3y')}@{r.get('hit_3y')} | {r['buy_min_p']} | {r['sell_min_p']} | "
            f"{'Y' if r.get('allow_sell_cont') else 'N'} | "
            f"{r['clip']['sl']:g}/{r['clip']['t1']:g} | {r['cap']} |"
        )

    lines += [
        "",
        "## Takeaway",
        "",
        payload["verdict"],
        "",
        "_Generated by `tests/builders/research_sensex_accuracy_volume_pareto.py`_",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_MD}", flush=True)
    print(f"RECOMMENDED: {fmt(rec)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
