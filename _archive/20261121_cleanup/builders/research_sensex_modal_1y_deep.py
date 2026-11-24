"""Deep Sensex modal research — 1y gate/clip grid + recommended live policy.

Problem: live dual.evaluate under-fires vs research champ pool (p_t1 drift /
tight SELL≥0.70). This script:
  1) Profiles 1y candidate pool
  2) Grid-searches champion (+proven) policies · Cap3 · path-score on 5m
  3) Picks Pareto policies (max N s.t. hit≥floor)
  4) Writes 1y per-month report + recommended live gate patch

  python -u prod_live/tests/builders/research_sensex_modal_1y_deep.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
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
    score_one,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "SENSEX_MODAL_1Y_DEEP.md"
OUT_JSON = OUT / "SENSEX_MODAL_1Y_DEEP.json"
CANDS = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_full_live_candidates.json"
)
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_5m_kite.csv"
FINAL = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_proven_100_final.json"
)

END = "2026-11-19"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
CAP = 3
FLOOR_PRIMARY = 88.0
FLOOR_STRICT = 92.0
FLOOR_ELITE = 94.0


def hit_pct(rows: List[dict]) -> Optional[float]:
    known = [r for r in rows if r.get("win") is not None]
    if not known:
        return None
    return round(100.0 * sum(1 for r in known if r.get("win")) / len(known), 2)


def month_rollup(rows: List[dict]) -> Dict[str, Any]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")[:7]].append(r)
    out = {}
    for m, rs in sorted(by.items()):
        known = [x for x in rs if x.get("win") is not None]
        w = sum(1 for x in known if x.get("win"))
        out[m] = {
            "n": len(rs),
            "settled": len(known),
            "hit_pct": round(100.0 * w / len(known), 2) if known else None,
            "wins": w,
            "losses": len(known) - w,
        }
    return out


def apply_policy(cands: List[dict], pol: Dict[str, Any]) -> List[dict]:
    """Filter candidates with a champion-style policy (proven optional)."""
    out: List[dict] = []
    buy_min = float(pol["buy_min_p"])
    sell_min = float(pol["sell_min_p"])
    buy_first = bool(pol.get("buy_first_only", True))
    sell_first = bool(pol.get("sell_first_only", True))
    buy_regimes = set(pol.get("buy_regimes") or ["range", "mixed", "trend", "volatile"])
    sell_regimes = set(pol.get("sell_regimes") or ["range", "mixed", "trend", "volatile"])
    buy_max_or = pol.get("buy_max_or_ext")
    sell_min_or = pol.get("sell_min_or_ext")
    sell_max_or = pol.get("sell_max_or_ext")
    max_mins = pol.get("max_mins")
    allow_sell_cont = bool(pol.get("allow_sell_cont", False))
    cont_sell_min = float(pol.get("cont_sell_min_p") or sell_min)
    cont_min_or = float(pol.get("cont_min_or_ext") or 0.15)
    cont_max_or = float(pol.get("cont_max_or_ext") or 0.40)
    cont_max_mins = int(pol.get("cont_max_mins") or (12 * 60 + 30))

    for r in cands:
        side = str(r.get("decision") or "").upper()
        p = float(r.get("p_t1") or 0)
        fb = bool(r.get("first_break"))
        reg = str(r.get("regime") or "")
        or_ext = float(r.get("or_ext") if r.get("or_ext") is not None else 9)
        mins = r.get("mins")
        track = "champion"

        if side == "BUY":
            if buy_first and not fb:
                continue
            if reg not in buy_regimes:
                continue
            if p < buy_min:
                continue
            if buy_max_or is not None and or_ext > float(buy_max_or) + 1e-9:
                continue
            if max_mins is not None and mins is not None and int(mins) > int(max_mins):
                continue
            # proven-style tag when stricter
            if (
                fb
                and buy_max_or is not None
                and or_ext <= float(buy_max_or) + 1e-9
                and p >= max(buy_min, 0.55)
            ):
                track = "proven_100" if float(buy_max_or) <= 0.15 and p >= 0.55 else "champion"
            out.append({**r, "track": track if track == "proven_100" else "champion"})
            continue

        if side == "SELL":
            if fb:
                if sell_first is False:
                    pass
                if reg not in sell_regimes:
                    continue
                if p < sell_min:
                    continue
                if sell_min_or is not None and or_ext < float(sell_min_or) - 1e-9:
                    continue
                if sell_max_or is not None and or_ext > float(sell_max_or) + 1e-9:
                    continue
                if max_mins is not None and mins is not None and int(mins) > int(max_mins):
                    continue
                out.append({**r, "track": "champion"})
                continue
            # continuation
            if not allow_sell_cont:
                continue
            if p < cont_sell_min:
                continue
            if not (cont_min_or - 1e-9 <= or_ext <= cont_max_or + 1e-9):
                continue
            if mins is not None and int(mins) > cont_max_mins:
                continue
            out.append({**r, "track": "champion"})
    return out


def score_policy(
    bars,
    ix,
    cands: List[dict],
    pol: Dict[str, Any],
    sl: float,
    t1: float,
) -> Dict[str, Any]:
    pool = apply_policy(cands, pol)
    scored = path_score_pool(bars, ix, pool, sl, t1, prefer_native_outcome=False)
    scored = day_cap(scored, CAP)
    known = [r for r in scored if r.get("win") is not None]
    return {
        "policy": pol,
        "clip": {"sl": sl, "t1": t1},
        "pool_n": len(pool),
        "n": len(scored),
        "settled": len(known),
        "hit_pct": hit_pct(scored),
        "wins": sum(1 for r in known if r.get("win")),
        "losses": sum(1 for r in known if not r.get("win")),
        "by_side": dict(Counter(str(r.get("decision")) for r in scored)),
        "by_track": dict(Counter(str(r.get("track")) for r in scored)),
        "by_month": month_rollup(scored),
        "calls": scored,
    }


def main() -> int:
    t0 = time.time()
    print(f"Sensex modal deep · 1y {START_1Y}→{END}", flush=True)
    bars, ix = load_tape(TAPE5)
    print(f"  tape5 n={len(bars)} max={bars.index.max()}", flush=True)

    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    cands: List[dict] = []
    for row in raw:
        n = normalize_cand(row)
        if n and START_1Y <= n["day"] <= END:
            # keep or_ext/regime/mins/first_break from normalize + raw
            n["or_ext"] = float(row.get("or_ext") if row.get("or_ext") is not None else n.get("or_ext") or 9)
            n["regime"] = str(row.get("regime") or n.get("regime") or "")
            n["mins"] = row.get("mins")
            n["first_break"] = bool(row.get("first_break"))
            n["native_outcome"] = str(row.get("outcome") or "")
            n["native_win"] = str(row.get("outcome") or "") == "t1_before_sl"
            cands.append(n)
    print(f"  1y cands={len(cands)}", flush=True)

    # ---- baseline: current live champion ----
    current = {
        "name": "LIVE_current_champ",
        "buy_min_p": 0.55,
        "sell_min_p": 0.70,
        "buy_first_only": True,
        "sell_first_only": True,
        "allow_sell_cont": False,
        "buy_regimes": ["range", "mixed", "trend", "volatile"],
    }
    current_res = score_policy(bars, ix, cands, current, 100.0, 100.0)
    print(
        f"  CURRENT ±100 Cap3: n={current_res['n']} hit={current_res['hit_pct']}%",
        flush=True,
    )

    # ---- grid ----
    buy_mins = [0.50, 0.55, 0.58, 0.60]
    sell_mins = [0.55, 0.58, 0.62, 0.65, 0.68, 0.70]
    clips = [(80.0, 100.0), (100.0, 100.0), (80.0, 80.0), (120.0, 120.0), (100.0, 120.0)]
    sell_cont_opts = [False, True]
    buy_regime_opts = [
        ["range", "mixed", "trend", "volatile"],
        ["range", "mixed"],
    ]

    grid_rows: List[Dict[str, Any]] = []
    for buy_min, sell_min, (sl, t1), cont, regs in product(
        buy_mins, sell_mins, clips, sell_cont_opts, buy_regime_opts
    ):
        # skip silly: cont with very high sell_min already rare
        pol = {
            "name": f"b{buy_min}_s{sell_min}_{'cont' if cont else 'first'}_reg{len(regs)}_T{int(t1)}SL{int(sl)}",
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
        res = score_policy(bars, ix, cands, pol, sl, t1)
        slim = {k: v for k, v in res.items() if k != "calls"}
        grid_rows.append(slim)

    # rank helpers
    def ok(r, floor):
        return r["n"] >= 8 and r["hit_pct"] is not None and r["hit_pct"] + 1e-9 >= floor

    def best_for(floor: float) -> Optional[Dict[str, Any]]:
        cands_ok = [r for r in grid_rows if ok(r, floor)]
        if not cands_ok:
            return None
        return sorted(
            cands_ok,
            key=lambda r: (-r["n"], -float(r["hit_pct"]), r["clip"]["sl"]),
        )[0]

    pick_88 = best_for(FLOOR_PRIMARY)
    pick_92 = best_for(FLOOR_STRICT)
    pick_94 = best_for(FLOOR_ELITE)

    # also: best hit at n>=20 and n>=30
    def best_hit_at_least(n_min: int) -> Optional[Dict[str, Any]]:
        cands_ok = [r for r in grid_rows if r["n"] >= n_min and r["hit_pct"] is not None]
        if not cands_ok:
            return None
        return sorted(cands_ok, key=lambda r: (-float(r["hit_pct"]), -r["n"]))[0]

    pick_n20 = best_hit_at_least(20)
    pick_n30 = best_hit_at_least(30)

    # recommended: prefer ≥92% with decent N, else ≥88% max N, prefer ±100 for live continuity
    recommended = pick_92 or pick_88 or current_res
    # among near-best, prefer clip 100/100 if within 2 calls and hit within 1pp
    if pick_92:
        near = [
            r
            for r in grid_rows
            if ok(r, FLOOR_STRICT)
            and r["n"] >= pick_92["n"] - 2
            and r["clip"] == {"sl": 100.0, "t1": 100.0}
        ]
        if near:
            recommended = sorted(near, key=lambda r: (-r["n"], -float(r["hit_pct"])))[0]
        else:
            recommended = pick_92

    # recompute full calls for recommended + current
    rec_full = score_policy(
        bars,
        ix,
        cands,
        recommended["policy"],
        recommended["clip"]["sl"],
        recommended["clip"]["t1"],
    )
    cur_full = current_res

    # top 15 by n at ≥88%
    top_vol = sorted(
        [r for r in grid_rows if ok(r, FLOOR_PRIMARY)],
        key=lambda r: (-r["n"], -float(r["hit_pct"])),
    )[:15]
    # top 15 by hit at n≥15
    top_hit = sorted(
        [r for r in grid_rows if r["n"] >= 15 and r["hit_pct"] is not None],
        key=lambda r: (-float(r["hit_pct"]), -r["n"]),
    )[:15]

    # diagnose: why live under-fires — compare candidate p vs path at current gates
    cur_pool = apply_policy(cands, current)
    print(f"  current pool (cand p gates) n={len(cur_pool)}", flush=True)

    elapsed = round(time.time() - t0, 1)
    payload = {
        "symbol": "SENSEX",
        "window": {"start": START_1Y, "end": END},
        "cap": CAP,
        "floors": {"primary": FLOOR_PRIMARY, "strict": FLOOR_STRICT, "elite": FLOOR_ELITE},
        "elapsed_s": elapsed,
        "cand_n_1y": len(cands),
        "current_live": {k: v for k, v in cur_full.items() if k != "calls"},
        "recommended": {k: v for k, v in rec_full.items() if k != "calls"},
        "picks": {
            "max_n_hit88": {k: v for k, v in (pick_88 or {}).items() if k != "calls"},
            "max_n_hit92": {k: v for k, v in (pick_92 or {}).items() if k != "calls"},
            "max_n_hit94": {k: v for k, v in (pick_94 or {}).items() if k != "calls"},
            "best_hit_n20": {k: v for k, v in (pick_n20 or {}).items() if k != "calls"},
            "best_hit_n30": {k: v for k, v in (pick_n30 or {}).items() if k != "calls"},
        },
        "top_volume_ge88": top_vol,
        "top_hit_n15": top_hit,
        "recommended_calls": [
            {
                "day": r.get("day"),
                "hm": r.get("hm"),
                "decision": r.get("decision"),
                "track": r.get("track"),
                "p_t1": r.get("p_t1"),
                "win": r.get("win"),
                "points": r.get("points"),
                "outcome": r.get("outcome"),
            }
            for r in rec_full["calls"]
        ],
        "current_calls": [
            {
                "day": r.get("day"),
                "hm": r.get("hm"),
                "decision": r.get("decision"),
                "track": r.get("track"),
                "p_t1": r.get("p_t1"),
                "win": r.get("win"),
                "points": r.get("points"),
                "outcome": r.get("outcome"),
            }
            for r in cur_full["calls"]
        ],
        "grid_n": len(grid_rows),
        "live_patch": {
            "CHAMPION_BUY_MIN_P": recommended["policy"]["buy_min_p"],
            "CHAMPION_SELL_MIN_P": recommended["policy"]["sell_min_p"],
            "CHAMPION_SELL_FIRST_ONLY": not recommended["policy"].get("allow_sell_cont", False),
            "CHAMPION_BUY_REGIMES": recommended["policy"].get("buy_regimes"),
            "allow_sell_cont": recommended["policy"].get("allow_sell_cont"),
            "clip": recommended["clip"],
            "desk": (
                f"SENSEX_CHAMP_PLUS_T{int(recommended['clip']['t1'])}"
                f"SL{int(recommended['clip']['sl'])}_CAP{CAP}"
            ),
        },
        "note": (
            "Path-score is honest 5m ±clip Cap3. Candidate p_t1 comes from "
            "freeze research packs; live evaluate can drift — after patching "
            "gates, re-smoke live.evaluate on recent days."
        ),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def fmt_pick(label: str, r: Optional[dict]) -> List[str]:
        if not r:
            return [f"- **{label}:** none"]
        pol = r["policy"]
        return [
            f"- **{label}:** n={r['n']} hit={r['hit_pct']}% · "
            f"clip ±{r['clip']['sl']:g}/{r['clip']['t1']:g} · "
            f"BUY≥{pol['buy_min_p']} SELL≥{pol['sell_min_p']} · "
            f"{'SELL-cont ON' if pol.get('allow_sell_cont') else 'first-only'} · "
            f"regimes={len(pol.get('buy_regimes') or [])} · `{pol.get('name')}`"
        ]

    lines = [
        "# SENSEX modal · 1y deep research",
        "",
        f"**Window:** `{START_1Y}` → `{END}` · candidates={len(cands)} · Cap{CAP}",
        f"**Method:** gate×clip grid ({len(grid_rows)} configs) · 5m path-score (not native dual outcome)",
        f"**Elapsed:** {elapsed}s",
        "",
        "## Problem",
        "",
        "Live Sensex modal barely fires (SELL champion p≥0.70 first-only). "
        "2m kite replay → only 2 board calls. Research champ pool is richer; "
        "live pack p_t1 often sits just below the 0.70 cut.",
        "",
        "## Current live policy (path-scored ±100)",
        "",
        f"- n=**{cur_full['n']}** · hit=**{cur_full['hit_pct']}%** · "
        f"W/L={cur_full['wins']}/{cur_full['losses']} · side=`{cur_full['by_side']}`",
        "",
        "| Month | N | Hit% | W/L |",
        "|---|---:|---:|---|",
    ]
    for m, st in (cur_full.get("by_month") or {}).items():
        lines.append(
            f"| {m} | {st['n']} | {st['hit_pct']} | {st['wins']}/{st['losses']} |"
        )

    lines += [
        "",
        "## Recommended policy",
        "",
        f"- n=**{rec_full['n']}** · hit=**{rec_full['hit_pct']}%** · "
        f"W/L={rec_full['wins']}/{rec_full['losses']} · side=`{rec_full['by_side']}`",
        f"- clip **±{rec_full['clip']['sl']:g}/{rec_full['clip']['t1']:g}** · "
        f"BUY≥{rec_full['policy']['buy_min_p']} · SELL≥{rec_full['policy']['sell_min_p']} · "
        f"{'SELL continuation ON' if rec_full['policy'].get('allow_sell_cont') else 'SELL first-only'}",
        f"- desk tag: `{payload['live_patch']['desk']}`",
        "",
        "| Month | N | Hit% | W/L |",
        "|---|---:|---:|---|",
    ]
    for m, st in (rec_full.get("by_month") or {}).items():
        lines.append(
            f"| {m} | {st['n']} | {st['hit_pct']} | {st['wins']}/{st['losses']} |"
        )

    lines += ["", "## Pareto picks", ""]
    for label, pick in (
        ("max N @ ≥88%", pick_88),
        ("max N @ ≥92%", pick_92),
        ("max N @ ≥94%", pick_94),
        ("best hit @ N≥20", pick_n20),
        ("best hit @ N≥30", pick_n30),
    ):
        lines.extend(fmt_pick(label, pick))

    lines += [
        "",
        "## Top volume (≥88% hit)",
        "",
        "| N | Hit% | BUY≥ | SELL≥ | Cont | Clip | Regimes |",
        "|---:|---:|---:|---:|---|---|---:|",
    ]
    for r in top_vol:
        p = r["policy"]
        lines.append(
            f"| {r['n']} | {r['hit_pct']} | {p['buy_min_p']} | {p['sell_min_p']} | "
            f"{'Y' if p.get('allow_sell_cont') else 'N'} | "
            f"{r['clip']['sl']:g}/{r['clip']['t1']:g} | {len(p.get('buy_regimes') or [])} |"
        )

    lines += [
        "",
        "## Top hit (N≥15)",
        "",
        "| N | Hit% | BUY≥ | SELL≥ | Cont | Clip |",
        "|---:|---:|---:|---:|---|---|",
    ]
    for r in top_hit:
        p = r["policy"]
        lines.append(
            f"| {r['n']} | {r['hit_pct']} | {p['buy_min_p']} | {p['sell_min_p']} | "
            f"{'Y' if p.get('allow_sell_cont') else 'N'} | "
            f"{r['clip']['sl']:g}/{r['clip']['t1']:g} |"
        )

    lines += [
        "",
        "## Recommended calls (1y board)",
        "",
        "| Day | HM | Side | Track | p_t1 | Win | Pts |",
        "|---|---|---|---|---:|---|---:|",
    ]
    for r in rec_full["calls"]:
        w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "open")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | "
            f"{r.get('track')} | {r.get('p_t1')} | {w} | {r.get('points')} |"
        )

    lines += [
        "",
        "## Live patch proposal",
        "",
        "```",
        json.dumps(payload["live_patch"], indent=2),
        "```",
        "",
        "_Generated by `tests/builders/research_sensex_modal_1y_deep.py`_",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_MD}", flush=True)
    print(
        f"RECOMMENDED n={rec_full['n']} @{rec_full['hit_pct']}% vs CURRENT n={cur_full['n']} @{cur_full['hit_pct']}%",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
