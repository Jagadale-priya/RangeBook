"""Confirm Lane B accurate desks @ 3y match locked research report.

Uses same caches + window end as ACC_ALL_DESKS_10Y.md.
Builds desks via logic/accurate_desks.py (combined accurate logic).

  python -u prod_live/tests/confirm_accurate_desks_3y_match.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List

PROD = Path(__file__).resolve().parents[1]  # prod_live
REPO = PROD.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(PROD / "tests" / "builders"))
import path_setup  # noqa: F401,E402
ROOT = PROD  # reports under prod_live

import pandas as pd  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip  # noqa: E402
from research_100pct_deeper_more_calls import gap_map  # noqa: E402
from prod_live.logic.accurate_desks import (  # noqa: E402
    DESK_REGISTRY,
    RESEARCH_END,
    build_all_accurate_desks,
    desks_by_accuracy_range,
    desks_by_band,
)

OUT = ROOT / "reports" / "1y"
LEDGER = REPO / "stock_signal_data/fno_validate/research"
CACHE_DUAL_10Y = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH_10Y = LEDGER / "_cache_path_trusted_10y.json"

END = RESEARCH_END
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_10Y = (pd.Timestamp(END) - timedelta(days=365 * 10)).strftime("%Y-%m-%d")
HIT_TOL = 0.05  # allow tiny float drift


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 2)


def main() -> None:
    t0 = time.time()
    print(f"CONFIRM accurate desks 3y match  {START_3Y} → {END}", flush=True)

    dual = json.loads(CACHE_DUAL_10Y.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH_10Y.read_text(encoding="utf-8"))
    gaps = gap_map()
    # Same HTF universe as ACC_ALL_DESKS_10Y (10y sessions, not 3y-only)
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_10Y < d <= END]
    if len(sess) < 100:
        dual_days = sorted(
            {
                str(r.get("day") or "")
                for pack in (dual.get("dual15") or {}).values()
                if isinstance(pack, list)
                for r in pack
            }
        )
        sess = [d for d in dual_days if START_10Y < d <= END]
    active = fs._active_days(sess, fs._load_daily()) if sess else set()

    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ = _champ_floor([dict(r, track="champion") for r in dual["dual15"]["champion"]])
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]

    print("  build_all_accurate_desks…", flush=True)
    desks = build_all_accurate_desks(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=path_u.get("crown_by_risk") or {},
        good_by_risk=path_u.get("good_by_risk") or {},
        champ_rows=path_u.get("champ_native") or champ,
        gap_pct_by_day=gaps,
        htf_days=active,
    )

    rows_out: List[Dict[str, Any]] = []
    all_pass = True
    for desk_tag, meta in DESK_REGISTRY.items():
        exp = meta.get("research_3y") or {}
        exp_n = int(exp.get("n") or 0)
        exp_hit = float(exp.get("hit_pct") or 0)
        rs = _clip(desks.get(desk_tag) or [], START_3Y, END)
        got_n = len(rs)
        got_hit = hit_pct(rs)
        # stamp check
        range_tag = meta["accuracy_range"]
        bad_stamp = sum(
            1
            for r in rs
            if r.get("accuracy_range_tag") != range_tag or r.get("desk_tag") != desk_tag
        )
        n_ok = got_n == exp_n
        hit_ok = abs(got_hit - exp_hit) <= HIT_TOL
        stamp_ok = bad_stamp == 0
        ok = n_ok and hit_ok and stamp_ok
        if not ok:
            all_pass = False
        rows_out.append(
            {
                "desk": desk_tag,
                "accuracy_range_tag": range_tag,
                "band": meta["band"],
                "expected_n": exp_n,
                "got_n": got_n,
                "expected_hit": exp_hit,
                "got_hit": got_hit,
                "n_match": n_ok,
                "hit_match": hit_ok,
                "stamp_ok": stamp_ok,
                "pass": ok,
                "delta_n": got_n - exp_n,
                "delta_hit": round(got_hit - exp_hit, 4),
            }
        )
        flag = "PASS" if ok else "FAIL"
        print(
            f"  [{flag}] {desk_tag}  range={range_tag}  "
            f"n {got_n}/{exp_n}  hit {got_hit}/{exp_hit}",
            flush=True,
        )

    payload = {
        "status": "HOLDING",
        "lane": "HOLDING",
        "logic_module": "logic/accurate_desks.py",
        "window": {"start": START_3Y, "end": END, "label": "3y"},
        "research_lock": "reports/1y/ACC_ALL_DESKS_10Y.md",
        "hit_tolerance": HIT_TOL,
        "all_pass": all_pass,
        "results": rows_out,
        "by_accuracy_range": desks_by_accuracy_range(),
        "by_band": desks_by_band(),
        "elapsed_s": round(time.time() - t0, 1),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ACC_ACCURATE_3Y_MATCH.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (LEDGER / "ACC_ACCURATE_3Y_MATCH.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Accurate desks — 3y match vs research",
        "",
        f"**Logic file:** `logic/accurate_desks.py` (Lane B HOLDING — separate from LIVE)",
        f"**Window:** `{START_3Y}` → `{END}`",
        f"**Lock:** `ACC_ALL_DESKS_10Y.md` · hit tol ±{HIT_TOL}",
        "",
        f"## Verdict: **{'PASS' if all_pass else 'FAIL'}**",
        "",
        "## Tags by accuracy range (3y→10y research)",
        "",
    ]
    for rng, desks_list in sorted(desks_by_accuracy_range().items()):
        lines.append(f"- `{rng}` → " + ", ".join(f"`{d}`" for d in desks_list))
    lines += [
        "",
        "## 3y compare",
        "",
        "| Pass | Desk | Range tag | Band | Exp N | Got N | Exp Hit | Got Hit | ΔN | ΔHit |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows_out:
        lines.append(
            f"| {'✅' if r['pass'] else '❌'} | `{r['desk']}` | `{r['accuracy_range_tag']}` | "
            f"`{r['band']}` | {r['expected_n']} | {r['got_n']} | {r['expected_hit']} | "
            f"{r['got_hit']} | {r['delta_n']:+d} | {r['delta_hit']:+g} |"
        )

    lines += [
        "",
        "## Bands",
        "",
    ]
    for band, desks_list in sorted(desks_by_band().items()):
        lines.append(f"- `{band}`: " + ", ".join(f"`{d}`" for d in desks_list))

    lines += [
        "",
        f"Elapsed {payload['elapsed_s']}s",
        "",
        "JSON: `ACC_ACCURATE_3Y_MATCH.json`",
        "",
    ]
    md = OUT / "ACC_ACCURATE_3Y_MATCH.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (LEDGER / "ACC_ACCURATE_3Y_MATCH.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", md, flush=True)
    print("ALL_PASS" if all_pass else "ALL_FAIL", flush=True)
    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
