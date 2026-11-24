"""Hold ALL ACC100 + wide desks; score 1y / 3y / 5y / 10y on path-true caches.

Uses existing 10y dual + path caches (no rebuild unless missing).

  python -u prod_live/tests/builders/research_acc_all_desks_10y.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
import path_setup  # noqa: F401,E402

import pandas as pd  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip  # noqa: E402
from research_100pct_deeper_more_calls import gap_map, is_perfect  # noqa: E402
from prod_live.logic.acc100_streams import (  # noqa: E402
    merge_acc100_multi,
    merge_acc100_multi_v2,
    merge_acc100_multi_v3,
    merge_acc100_multi_v4,
    merge_acc100_multi_v5,
    merge_acc_wide_p75,
    merge_acc_wide_p75_cap2,
    merge_acc_wide_p80,
    merge_acc_wide_p80_cap2,
    merge_acc_wide_p85,
    merge_acc_wide_p85b,
    merge_acc_wide_p90,
    merge_acc_wide_p92,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL_10Y = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH_10Y = LEDGER / "_cache_path_trusted_10y.json"

END = "2026-11-13"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_5Y = (pd.Timestamp(END) - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
START_10Y = (pd.Timestamp(END) - timedelta(days=365 * 10)).strftime("%Y-%m-%d")
WINDOWS = [
    ("1y", START_1Y),
    ("3y", START_3Y),
    ("5y", START_5Y),
    ("10y", START_10Y),
]


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 2)


def score_desk(desk: List[dict]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for lab, start in WINDOWS:
        rs = _clip(desk, start, END)
        st = _agg(rs) if rs else {"n": 0, "hit_pct": 0.0, "points": 0.0}
        out[lab] = {
            "n": len(rs),
            "hit_pct": hit_pct(rs),
            "perfect": bool(rs) and is_perfect(rs),
            "points": st.get("points"),
            "wins": sum(1 for r in rs if r.get("win")),
            "losses": sum(1 for r in rs if not r.get("win")),
        }
    return out


def main() -> None:
    t0 = time.time()
    print("HOLD all ACC desks — 1y/3y/5y/10y path-true test", flush=True)

    dual = json.loads(CACHE_DUAL_10Y.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH_10Y.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    # HTF active over longest window we care about
    sess = [d for d in sessions_all if START_10Y < d <= END]
    # prod2 may not cover 10y — fall back to dual session days
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
    crown_by_risk = path_u.get("crown_by_risk") or {}
    good_by_risk = path_u.get("good_by_risk") or {}
    champ_native = path_u.get("champ_native") or champ

    print(
        f"  dual15 proven={len(proven)} champ={len(dual['dual15']['champion'])} | "
        f"path crown risks={list(crown_by_risk)[:8]} | active_htf≈{len(active)}",
        flush=True,
    )

    kw = dict(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active,
    )

    def v1_merge(**_):
        return merge_acc100_multi(
            proven,
            dual15,
            dual5,
            crown_by_risk.get("20.0") or crown_by_risk.get("20") or [],
            good_by_risk.get("30.0") or good_by_risk.get("30") or [],
            gaps,
        )

    desks: List[tuple[str, Callable[..., List[dict]]]] = [
        ("ACC100_MULTI_V1", v1_merge),
        ("ACC100_MULTI_V2", merge_acc100_multi_v2),
        ("ACC100_MULTI_V3", merge_acc100_multi_v3),
        ("ACC100_MULTI_V4", merge_acc100_multi_v4),
        ("ACC100_MULTI_V5", merge_acc100_multi_v5),
        ("ACC_WIDE_P92", merge_acc_wide_p92),
        ("ACC_WIDE_P90", merge_acc_wide_p90),
        ("ACC_WIDE_P85", merge_acc_wide_p85),
        ("ACC_WIDE_P85B", merge_acc_wide_p85b),
        ("ACC_WIDE_P80", merge_acc_wide_p80),
        ("ACC_WIDE_P75", merge_acc_wide_p75),
        ("ACC_WIDE_P80_CAP2", merge_acc_wide_p80_cap2),
        ("ACC_WIDE_P75_CAP2", merge_acc_wide_p75_cap2),
    ]

    results: Dict[str, Any] = {}
    for name, fn in desks:
        print(f"  build {name}…", flush=True)
        desk = fn(**kw)
        sc = score_desk(desk)
        results[name] = sc
        print(
            f"    3y {sc['3y']['n']}@{sc['3y']['hit_pct']}% | "
            f"5y {sc['5y']['n']}@{sc['5y']['hit_pct']}% | "
            f"10y {sc['10y']['n']}@{sc['10y']['hit_pct']}% "
            f"(L={sc['10y']['losses']})",
            flush=True,
        )

    payload = {
        "status": "HOLDING",
        "not_live": True,
        "keep_all": [d[0] for d in desks],
        "windows": {lab: start for lab, start in WINDOWS},
        "end": END,
        "results": results,
        "elapsed_s": round(time.time() - t0, 1),
        "note": "10y path-true on cached dual+path; crown streams sparse pre-2024-05",
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ACC_ALL_DESKS_10Y.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (LEDGER / "ACC_ALL_DESKS_10Y.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# All held ACC desks — 1y / 3y / 5y / 10y",
        "",
        "**Status: HOLDING** — keep all desks; not live.",
        "",
        f"Window end `{END}` · starts 1y=`{START_1Y}` · 3y=`{START_3Y}` · "
        f"5y=`{START_5Y}` · 10y=`{START_10Y}`",
        "",
        f"Elapsed {payload['elapsed_s']}s · caches: `_cache_dual15_dual5_10y` + "
        "`_cache_path_trusted_10y`",
        "",
        "## Ladder",
        "",
        "| Desk | 1y N | 1y Hit | 3y N | 3y Hit | 5y N | 5y Hit | 10y N | 10y Hit | 10y L |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, _ in desks:
        r = results[name]
        lines.append(
            f"| `{name}` | {r['1y']['n']} | {r['1y']['hit_pct']} | "
            f"{r['3y']['n']} | {r['3y']['hit_pct']} | "
            f"{r['5y']['n']} | {r['5y']['hit_pct']} | "
            f"{r['10y']['n']} | {r['10y']['hit_pct']} | {r['10y']['losses']} |"
        )

    lines += [
        "",
        "## Notes",
        "",
        "- **100% desks (V1–V5):** perfect on 3y+5y by construction; 10y may drop "
        "(older proven/confirm + sparse crown history).",
        "- **Wide / cap2:** honest losses kept; use for volume filter.",
        "- Crown path pools are denser from ~2024-05 — 10y N is not linear vs 3y.",
        "",
        "## Hold",
        "",
        "Keep **all** desks listed above for later filter. Do not promote until asked.",
        "",
        "JSON: `ACC_ALL_DESKS_10Y.json`",
        "",
    ]
    md = OUT / "ACC_ALL_DESKS_10Y.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (LEDGER / "ACC_ALL_DESKS_10Y.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", md, flush=True)


if __name__ == "__main__":
    main()
