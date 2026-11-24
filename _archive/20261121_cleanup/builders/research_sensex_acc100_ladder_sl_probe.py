"""Sensex ACC100 ladder research (NIFTY-style) + SL50/SL100 probe.

Levels:
  L1 ACC100 — hit 100% on BOTH 1y and 3y (maximize N)
  L2 DAY1   — exactly 1 call/day · accurate entry (max p_t1, else earliest hm)
              prefer 100/100; else best joint hit with N≥20

Same locked gate sets scored at SL/T ∈ {50/50, 100/100, 120/120, 150/150}.

  python -u prod_live/tests/builders/research_sensex_acc100_ladder_sl_probe.py
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
OUT_MD = OUT / "SENSEX_ACC100_LADDER_SL_PROBE.md"
OUT_JSON = OUT / "SENSEX_ACC100_LADDER_SL_PROBE.json"
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

CLIPS = [(50.0, 50.0), (100.0, 100.0), (120.0, 120.0), (150.0, 150.0)]


def day1_accurate(rows: List[dict]) -> List[dict]:
    """Exactly 1 call per calendar day — highest p_t1, tie → earliest hm."""
    by: Dict[str, dict] = {}
    for r in rows:
        d = str(r.get("day") or "")[:10]
        if not d:
            continue
        cur = by.get(d)
        if cur is None:
            by[d] = r
            continue
        p_new, p_old = float(r.get("p_t1") or 0), float(cur.get("p_t1") or 0)
        if p_new > p_old + 1e-12:
            by[d] = r
        elif abs(p_new - p_old) <= 1e-12 and str(r.get("hm") or "") < str(cur.get("hm") or ""):
            by[d] = r
    return sorted(by.values(), key=lambda x: (str(x.get("day")), str(x.get("hm"))))


def win_clip(rows: List[dict], a: str, b: str) -> List[dict]:
    return [r for r in rows if a <= str(r.get("day") or "")[:10] <= b]


def stats(rows: List[dict]) -> Dict[str, Any]:
    known = [r for r in rows if r.get("win") is not None]
    w = sum(1 for r in known if r.get("win"))
    return {
        "n": len(rows),
        "settled": len(known),
        "hit_pct": hit_pct(rows),
        "wins": w,
        "losses": len(known) - w,
        "by_side": {
            s: sum(1 for r in rows if str(r.get("decision")) == s) for s in ("BUY", "SELL")
        },
        "by_month": month_rollup(rows),
    }


def score_mode(
    bars,
    ix,
    cands: List[dict],
    pol: Dict[str, Any],
    sl: float,
    t1: float,
    mode: str,
) -> Dict[str, Any]:
    pool = apply_policy(cands, pol)
    scored = path_score_pool(bars, ix, pool, sl, t1)
    if mode == "day":
        scored = day1_accurate(scored)
    else:
        scored = day_cap(scored, 3)
    r1 = win_clip(scored, START_1Y, END)
    r3 = win_clip(scored, START_3Y, END)
    s1, s3 = stats(r1), stats(r3)
    return {
        "policy": pol,
        "clip": {"sl": sl, "t1": t1},
        "mode": mode,
        "pool_n": len(pool),
        "1y": s1,
        "3y": s3,
        "calls_1y": [
            {
                "day": r.get("day"),
                "hm": r.get("hm"),
                "decision": r.get("decision"),
                "p_t1": r.get("p_t1"),
                "track": r.get("track"),
                "win": r.get("win"),
                "points": r.get("points"),
                "outcome": r.get("outcome"),
                "entry": r.get("entry"),
            }
            for r in r1
        ],
        "perfect_both": bool(
            s1["hit_pct"] == 100.0
            and s3["hit_pct"] == 100.0
            and s1["n"] >= 5
            and s3["n"] >= 8
        ),
    }


def main() -> int:
    t0 = time.time()
    print(f"Sensex ACC100 ladder · 1y {START_1Y} · 3y {START_3Y} → {END}", flush=True)
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
    print(f"  cands={len(cands)} tape={len(bars)}", flush=True)

    # ---- policy search (discover at ±150; SL probe later) ----
    # Keep grid tight: perfect books need strict gates.
    buy_mins = [0.55, 0.58, 0.60, 0.62, 0.65, 0.70]
    sell_mins = [9.0, 0.75, 0.70, 0.65]  # 9.0 = BUY-only
    buy_ors: List[Optional[float]] = [0.10, 0.15, 0.20, None]
    sell_ors: List[Optional[float]] = [None, 0.30]
    max_mins_opts: List[Optional[int]] = [None, 12 * 60, 13 * 60]
    buy_regs = [
        ["range", "mixed"],
        ["range", "mixed", "trend", "volatile"],
    ]
    discover_clips = [(150.0, 150.0), (120.0, 120.0)]

    perfect: List[Dict[str, Any]] = []
    near: List[Dict[str, Any]] = []  # both ≥98
    day_perfect: List[Dict[str, Any]] = []
    day_best: List[Dict[str, Any]] = []

    n_tried = 0
    for buy_min, sell_min, buy_or, sell_or, max_mins, regs, (sl, t1) in product(
        buy_mins, sell_mins, buy_ors, sell_ors, max_mins_opts, buy_regs, discover_clips
    ):
        if sell_min >= 9.0 and sell_or is not None:
            continue
        pol = {
            "name": (
                f"b{buy_min}_s{sell_min}_bor{buy_or}_sor{sell_or}_m{max_mins}"
                f"_r{len(regs)}_T{int(t1)}SL{int(sl)}"
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
        for mode in ("cap3", "day"):
            n_tried += 1
            res = score_mode(bars, ix, cands, pol, sl, t1, mode)
            h1, h3 = res["1y"]["hit_pct"], res["3y"]["hit_pct"]
            n1 = res["1y"]["n"]
            if h1 is None or h3 is None or n1 < 5:
                continue
            slim = {k: v for k, v in res.items() if k not in ("calls_1y",)}
            slim["calls_1y_n"] = len(res["calls_1y"])
            if res["perfect_both"]:
                if mode == "day":
                    day_perfect.append(slim)
                else:
                    perfect.append(slim)
            elif h1 >= 98 and h3 >= 98 and n1 >= 8:
                near.append(slim)
            if mode == "day" and n1 >= 15:
                day_best.append(slim)
            if n_tried % 500 == 0:
                print(
                    f"  …{n_tried} tried · perfect={len(perfect)} day_perfect={len(day_perfect)}",
                    flush=True,
                )

    def rank_perfect(rows: List[dict]) -> List[dict]:
        return sorted(
            rows,
            key=lambda r: (
                -r["1y"]["n"],
                -r["3y"]["n"],
                r["clip"]["sl"],  # prefer tighter clip among equals
            ),
        )

    perfect = rank_perfect(perfect)
    day_perfect = rank_perfect(day_perfect)
    near = sorted(
        near,
        key=lambda r: (
            -(min(r["1y"]["hit_pct"], r["3y"]["hit_pct"])),
            -r["1y"]["n"],
            -r["3y"]["n"],
        ),
    )
    # day_best: prefer perfect, else max min(hit1,hit3), then n
    day_best = sorted(
        day_best,
        key=lambda r: (
            0 if r.get("perfect_both") else 1,
            -min(float(r["1y"]["hit_pct"] or 0), float(r["3y"]["hit_pct"] or 0)),
            -r["1y"]["n"],
            -r["3y"]["n"],
        ),
    )

    print(f"  tried={n_tried} perfect_cap3={len(perfect)} perfect_day={len(day_perfect)}", flush=True)

    # Level picks
    l1 = perfect[0] if perfect else None
    l2 = day_perfect[0] if day_perfect else (day_best[0] if day_best else None)

    # If L1 missing, take best near-perfect
    if l1 is None and near:
        l1 = near[0]
        l1_note = "NEAR (not strict 100/100)"
    else:
        l1_note = "ACC100 both windows" if l1 and l1.get("perfect_both") else "FALLBACK"

    def probe_sl(level: Optional[dict], label: str) -> Dict[str, Any]:
        if not level:
            return {"label": label, "error": "no level"}
        pol = level["policy"]
        mode = level["mode"]
        out = {"label": label, "policy": pol, "mode": mode, "by_clip": {}}
        for sl, t1 in CLIPS:
            res = score_mode(bars, ix, cands, pol, sl, t1, mode)
            out["by_clip"][f"{int(sl)}/{int(t1)}"] = {
                "1y": res["1y"],
                "3y": res["3y"],
                "perfect_both": res["perfect_both"],
                "calls_1y": res["calls_1y"],
            }
            print(
                f"  {label} ±{int(sl)}/{int(t1)} {mode}: "
                f"1y {res['1y']['n']}@{res['1y']['hit_pct']}% · "
                f"3y {res['3y']['n']}@{res['3y']['hit_pct']}% "
                f"{'PERFECT' if res['perfect_both'] else ''}",
                flush=True,
            )
        return out

    print("Probe L1 ACC100…", flush=True)
    l1_probe = probe_sl(l1, "L1_ACC100")
    print("Probe L2 DAY1…", flush=True)
    l2_probe = probe_sl(l2, "L2_DAY1")

    # Also probe classic proven BUY and elite S0.70 as reference
    refs = []
    for name, pol in (
        (
            "REF_proven_BUY",
            {
                "name": "proven_BUY",
                "buy_min_p": 0.55,
                "sell_min_p": 9.0,
                "buy_first_only": True,
                "sell_first_only": True,
                "allow_sell_cont": False,
                "buy_max_or_ext": 0.15,
                "buy_regimes": ["range", "mixed", "trend", "volatile"],
            },
        ),
        (
            "REF_champ_S070",
            {
                "name": "champ_S070",
                "buy_min_p": 0.55,
                "sell_min_p": 0.70,
                "buy_first_only": True,
                "sell_first_only": True,
                "allow_sell_cont": False,
                "buy_regimes": ["range", "mixed", "trend", "volatile"],
            },
        ),
    ):
        # attach as synthetic level for probe
        refs.append(probe_sl({"policy": pol, "mode": "day"}, name))

    elapsed = round(time.time() - t0, 1)

    def slim_level(r: Optional[dict]) -> Optional[dict]:
        if not r:
            return None
        return {
            "policy": r["policy"],
            "clip": r["clip"],
            "mode": r["mode"],
            "1y": {k: v for k, v in r["1y"].items() if k != "by_month"},
            "3y": {k: v for k, v in r["3y"].items() if k != "by_month"},
            "by_month_1y": r["1y"].get("by_month"),
            "perfect_both": r.get("perfect_both"),
        }

    payload = {
        "windows": {"1y": {"start": START_1Y, "end": END}, "3y": {"start": START_3Y, "end": END}},
        "elapsed_s": elapsed,
        "tried": n_tried,
        "n_perfect_cap3": len(perfect),
        "n_perfect_day": len(day_perfect),
        "l1_note": l1_note,
        "L1_ACC100": slim_level(l1),
        "L2_DAY1": slim_level(l2),
        "L1_SL_probe": {
            k: {kk: vv for kk, vv in blk.items() if kk != "calls_1y"}
            if isinstance(blk, dict)
            else blk
            for k, blk in (l1_probe.get("by_clip") or {}).items()
        },
        "L2_SL_probe": {
            k: {kk: vv for kk, vv in blk.items() if kk != "calls_1y"}
            if isinstance(blk, dict)
            else blk
            for k, blk in (l2_probe.get("by_clip") or {}).items()
        },
        "L1_calls_by_clip": {
            k: blk.get("calls_1y") for k, blk in (l1_probe.get("by_clip") or {}).items()
        },
        "L2_calls_by_clip": {
            k: blk.get("calls_1y") for k, blk in (l2_probe.get("by_clip") or {}).items()
        },
        "top_perfect_cap3": [slim_level(r) for r in perfect[:15]],
        "top_perfect_day": [slim_level(r) for r in day_perfect[:15]],
        "refs": [
            {
                "label": r["label"],
                "by_clip": {
                    k: {kk: vv for kk, vv in blk.items() if kk != "calls_1y"}
                    for k, blk in (r.get("by_clip") or {}).items()
                },
            }
            for r in refs
        ],
    }

    OUT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def fmt_level(r: Optional[dict]) -> str:
        if not r:
            return "none"
        p = r["policy"]
        return (
            f"mode={r['mode']} ±{r['clip']['sl']:g}/{r['clip']['t1']:g} · "
            f"1y {r['1y']['n']}@{r['1y']['hit_pct']}% · 3y {r['3y']['n']}@{r['3y']['hit_pct']}% · "
            f"B≥{p.get('buy_min_p')} S≥{p.get('sell_min_p')} bor={p.get('buy_max_or_ext')} "
            f"sor={p.get('sell_max_or_ext')} mins={p.get('max_mins')} reg={len(p.get('buy_regimes') or [])}"
        )

    lines = [
        "# SENSEX ACC100 ladder · SL50 / SL100 probe",
        "",
        f"**Windows:** 1y `{START_1Y}`→`{END}` · 3y `{START_3Y}`→`{END}`",
        f"**Search:** {n_tried} configs · perfect cap3={len(perfect)} · perfect day={len(day_perfect)} · {elapsed}s",
        "",
        "NIFTY-style levels:",
        "1. **L1 ACC100** — 100% hit on **both** 1y and 3y",
        "2. **L2 DAY1** — exactly **1 call/day** (max p_t1 entry) · prefer 100/100",
        "3. Same gates re-scored at **±50** and **±100** (also ±120/±150)",
        "",
        f"## L1 ACC100 ({l1_note})",
        "",
        f"- {fmt_level(l1)}",
        "",
        "### SL probe (same gates)",
        "",
        "| Clip | 1y N | 1y Hit | 3y N | 3y Hit | Perfect both |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for clip, blk in (payload.get("L1_SL_probe") or {}).items():
        lines.append(
            f"| ±{clip} | {blk['1y']['n']} | {blk['1y']['hit_pct']} | "
            f"{blk['3y']['n']} | {blk['3y']['hit_pct']} | "
            f"{'YES' if blk.get('perfect_both') else 'no'} |"
        )

    if l1:
        lines += [
            "",
            "### L1 per month @ discovery clip",
            "",
            "| Month | N | Hit | W/L |",
            "|---|---:|---:|---|",
        ]
        for m, st in (l1.get("1y", {}).get("by_month") or {}).items():
            lines.append(f"| {m} | {st['n']} | {st['hit_pct']} | {st['wins']}/{st['losses']} |")

    lines += [
        "",
        "## L2 DAY1 (1 call/day · accurate entry)",
        "",
        f"- {fmt_level(l2)}",
        "",
        "### SL probe (same gates)",
        "",
        "| Clip | 1y N | 1y Hit | 3y N | 3y Hit | Perfect both |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for clip, blk in (payload.get("L2_SL_probe") or {}).items():
        lines.append(
            f"| ±{clip} | {blk['1y']['n']} | {blk['1y']['hit_pct']} | "
            f"{blk['3y']['n']} | {blk['3y']['hit_pct']} | "
            f"{'YES' if blk.get('perfect_both') else 'no'} |"
        )

    if l2:
        lines += [
            "",
            "### L2 per month @ discovery clip",
            "",
            "| Month | N | Hit | W/L |",
            "|---|---:|---:|---|",
        ]
        for m, st in (l2.get("1y", {}).get("by_month") or {}).items():
            lines.append(f"| {m} | {st['n']} | {st['hit_pct']} | {st['wins']}/{st['losses']} |")

    lines += [
        "",
        "## Reference desks (day mode)",
        "",
    ]
    for ref in payload["refs"]:
        lines.append(f"### {ref['label']}")
        lines += [
            "",
            "| Clip | 1y N/Hit | 3y N/Hit | Perfect |",
            "|---|---|---|---|",
        ]
        for clip, blk in (ref.get("by_clip") or {}).items():
            lines.append(
                f"| ±{clip} | {blk['1y']['n']}@{blk['1y']['hit_pct']}% | "
                f"{blk['3y']['n']}@{blk['3y']['hit_pct']}% | "
                f"{'YES' if blk.get('perfect_both') else 'no'} |"
            )
        lines.append("")

    lines += [
        "## Top perfect ACC100 books (cap3)",
        "",
        "| 1y N/Hit | 3y N/Hit | Clip | B≥ | S≥ | bor | mode |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for r in payload["top_perfect_cap3"][:12]:
        p = r["policy"]
        lines.append(
            f"| {r['1y']['n']}@{r['1y']['hit_pct']} | {r['3y']['n']}@{r['3y']['hit_pct']} | "
            f"±{r['clip']['sl']:g}/{r['clip']['t1']:g} | {p.get('buy_min_p')} | {p.get('sell_min_p')} | "
            f"{p.get('buy_max_or_ext')} | {r['mode']} |"
        )

    lines += [
        "",
        "## L1 calls @ ±100 (1y)",
        "",
        "| Day | HM | Side | p_t1 | Win | Pts | Outcome |",
        "|---|---|---|---:|---|---:|---|",
    ]
    for r in (payload.get("L1_calls_by_clip") or {}).get("100/100") or []:
        w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "open")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | {r.get('p_t1')} | "
            f"{w} | {r.get('points')} | {r.get('outcome')} |"
        )

    lines += [
        "",
        "## L1 calls @ ±50 (1y)",
        "",
        "| Day | HM | Side | p_t1 | Win | Pts | Outcome |",
        "|---|---|---|---:|---|---:|---|",
    ]
    for r in (payload.get("L1_calls_by_clip") or {}).get("50/50") or []:
        w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "open")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | {r.get('p_t1')} | "
            f"{w} | {r.get('points')} | {r.get('outcome')} |"
        )

    lines += [
        "",
        "## L2 DAY1 calls @ ±100 (1y)",
        "",
        "| Day | HM | Side | p_t1 | Win | Pts | Outcome |",
        "|---|---|---|---:|---|---:|---|",
    ]
    for r in (payload.get("L2_calls_by_clip") or {}).get("100/100") or []:
        w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "open")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | {r.get('p_t1')} | "
            f"{w} | {r.get('points')} | {r.get('outcome')} |"
        )

    lines += [
        "",
        "_Generated by `tests/builders/research_sensex_acc100_ladder_sl_probe.py`_",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_MD}", flush=True)
    print(f"L1: {fmt_level(l1)}", flush=True)
    print(f"L2: {fmt_level(l2)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
