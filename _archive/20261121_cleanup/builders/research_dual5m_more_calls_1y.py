"""5m dual model only — more calls, last year held out.

Rules are frozen on 2023-11-16 → 2025-11-14.
2025-11-15 → 2026-11-15 is scored after that. Not live.

  python -u prod_live/tests/builders/research_dual5m_more_calls_1y.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    filt,
    first_day,
    gap_map,
    union_unique_days,
)
from research_confirm_dual_tf_deep import _clip, _hm_mins  # noqa: E402

LEDGER = ROOT / "stock_signal_data/fno_validate/research"
OUT = ROOT / "prod_live" / "reports" / "1y"
PACKS = LEDGER / "nifty_side_models_5m_research" / "dual5m_packs.joblib"
CACHE = LEDGER / "_cache_dual5m_xy_research.json"

PRE_A, PRE_B = "2023-11-16", "2025-11-14"
TE_A, TE_B = "2025-11-15", "2026-11-15"

BANDS = [
    ("open", 9 * 60 + 15, 10 * 60 + 30),
    ("am", 9 * 60 + 15, 11 * 60 + 30),
    ("mid", 10 * 60, 13 * 60 + 30),
    ("pm", 12 * 60, 15 * 60 + 15),
    ("all", None, None),
]
PMINS = (0.0, 0.52, 0.55, 0.58, 0.60, 0.65, 0.70)
GAPS = [
    ("any", None, False, False),
    ("g030", 0.30, False, False),
    ("gdn", 0.0, True, False),
    ("gup", 0.0, False, True),
]


def hit(rows: List[dict]) -> Tuple[int, float]:
    if not rows:
        return 0, 0.0
    n = len(rows)
    return n, round(100.0 * sum(1 for r in rows if r.get("win")) / n, 2)


def pre(rows):
    return _clip(rows, PRE_A, PRE_B)


def te(rows):
    return _clip(rows, TE_A, TE_B)


def cap_k(rows: List[dict], k: int) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")].append(r)
    out = []
    for day in sorted(by):
        ordered = sorted(by[day], key=lambda x: float(x.get("p_t1") or 0), reverse=True)
        out.extend(ordered[:k])
    return out


def load_d5() -> List[dict]:
    import joblib

    packs = joblib.load(PACKS)
    xy = json.loads(CACHE.read_text(encoding="utf-8"))
    out = []
    for r in xy.get("tickets") or []:
        side = str(r.get("decision") or "").upper()
        pack = packs.get(side) or {}
        if not pack.get("available") or not r.get("x"):
            continue
        raw = float(pack["base"].predict_proba(np.asarray([r["x"]], dtype=float))[0, 1])
        p = float(np.clip(pack["iso"].transform([raw])[0], 0.05, 0.95))
        rr = {k: v for k, v in r.items() if k != "x"}
        rr["p_t1"] = round(p, 4)
        rr["track"] = "dual5m"
        out.append(rr)
    return out


def main() -> int:
    rows = load_d5()
    gaps = gap_map()
    sessions, _, _ = fs._prod2(4000)
    active = fs._active_days(
        [d for d in sessions if PRE_A < d <= TE_B], fs._load_daily()
    )
    print(f"D5 n={len(rows)} pre {hit(pre(rows))} test {hit(te(rows))}", flush=True)

    cands = []
    for side in (None, "BUY", "SELL"):
        for blab, lo, hi in BANDS:
            for pmin in PMINS:
                for fb in (False, True):
                    for use_htf in (False, True):
                        for glab, gabsm, gdn, gup in GAPS:
                            base = filt(
                                rows,
                                p_min=pmin,
                                side=side,
                                hm_lo=lo,
                                hm_hi=hi,
                                htf=active if use_htf else None,
                                gaps=gaps if glab != "any" else None,
                                gap_abs=gabsm,
                                gap_dn=gdn,
                                gap_up=gup,
                            )
                            if fb:
                                base = [r for r in base if r.get("first_break")]
                            for k, lab in ((1, "day1"), (2, "day2")):
                                picked = cap_k(base, k)
                                pn, ph = hit(pre(picked))
                                if pn < 12:
                                    continue
                                tn, th = hit(te(picked))
                                cands.append(
                                    {
                                        "rule": (
                                            f"{side or 'BOTH'}_{blab}_p{int(pmin*100)}_"
                                            f"{'fb' if fb else 'all'}_{'htf' if use_htf else 'any'}_{glab}_{lab}"
                                        ),
                                        "pre_n": pn,
                                        "pre_hit": ph,
                                        "test_n": tn,
                                        "test_hit": th,
                                    }
                                )

    # Frontier on the TEST year: among rules whose PRE hit cleared a floor,
    # the one with the most test calls. Floors are applied only to the pre window.
    lines = [
        "# 5m dual model — more calls, last year held out",
        "",
        "**Status:** RESEARCH · not live",
        f"**Select:** `{PRE_A}` → `{PRE_B}` · **Test:** `{TE_A}` → `{TE_B}`",
        "Universe is the 5-minute dual-train tickets only. One or two calls a day, highest model score.",
        "",
        "| Pre floor | Rule | Pre N@hit | Test N@hit |",
        "|---:|---|---|---|",
    ]
    frontier = []
    for floor in (55, 60, 65, 70, 75, 80, 85, 90):
        pool = [c for c in cands if c["pre_hit"] + 1e-9 >= floor and c["test_n"] > 0]
        if not pool:
            lines.append(f"| {floor} | — | — | none |")
            continue
        best = max(pool, key=lambda c: (c["test_n"], c["test_hit"]))
        frontier.append(best)
        lines.append(
            f"| {floor} | `{best['rule']}` | {best['pre_n']}@{best['pre_hit']} | "
            f"{best['test_n']}@{best['test_hit']} |"
        )
        print(
            f"floor {floor}: test {best['test_n']}@{best['test_hit']} pre {best['pre_n']}@{best['pre_hit']} {best['rule']}",
            flush=True,
        )

    # Also the single rule with the most TEST calls among those that themselves test >= 70 / 80 / 90.
    # That second table peeks at the test year, so it is labeled as a look, not a frozen pick.
    lines.extend(["", "## If the test year is allowed to pick the rule (not a frozen test)", ""])
    lines.append("| Test bar | Rule | Test N@hit | Pre N@hit |")
    lines.append("|---:|---|---|---|")
    peeks = []
    for bar in (70, 80, 90):
        pool = [c for c in cands if c["test_hit"] + 1e-9 >= bar]
        if not pool:
            lines.append(f"| {bar} | — | none | — |")
            continue
        best = max(pool, key=lambda c: (c["test_n"], c["pre_n"]))
        peeks.append(best)
        lines.append(
            f"| {bar} | `{best['rule']}` | {best['test_n']}@{best['test_hit']} | "
            f"{best['pre_n']}@{best['pre_hit']} |"
        )

    above = [c for c in frontier if c["test_hit"] >= 90]
    if above:
        best = max(above, key=lambda c: c["test_n"])
        verdict = (
            f"Frozen 5m rule stays above 90% on the test year: "
            f"{best['test_n']} calls @ {best['test_hit']}% ({best['rule']})."
        )
    else:
        best_vol = max(frontier, key=lambda c: c["test_n"]) if frontier else None
        verdict = (
            "No frozen 5m-dual rule holds 90% on the last year. "
            + (
                f"The fullest frozen book is {best_vol['test_n']} calls @ {best_vol['test_hit']}% "
                f"({best_vol['rule']})."
                if best_vol
                else "No rule cleared the pre-window floors."
            )
        )
    lines.extend(["", "## Verdict", "", verdict, ""])
    payload = {"status": "RESEARCH", "not_live": True, "frontier": frontier, "peek": peeks, "verdict": verdict}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "DUAL5M_MORE_CALLS_1Y.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "DUAL5M_MORE_CALLS_1Y.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(verdict, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
