"""1y call-day vs no-call-day coverage for all held ACC desks (through today).

  python -u prod_live/tests/builders/research_acc_1y_call_coverage.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Set

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _side  # noqa: E402
from research_100pct_deeper_more_calls import gap_map  # noqa: E402
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
DAILY = ROOT / "stock_signal_data/fno_validate/NIFTY_daily_nse.csv"

END = date.today().strftime("%Y-%m-%d")
START = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 2)


def trading_sessions(start: str, end: str) -> List[str]:
    """NSE sessions from daily file; fallback to prod2."""
    sessions: List[str] = []
    if DAILY.exists():
        import pandas as pd

        df = pd.read_csv(DAILY)
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
        sessions = sorted(d for d in df["Date"].tolist() if start < d <= end)
    if len(sessions) < 50:
        all_s, _, _ = fs._prod2(4000)
        sessions = sorted(d for d in all_s if start < d <= end)
    return sessions


def coverage(desk_rows: List[dict], sessions: List[str]) -> Dict[str, Any]:
    call_days: Set[str] = {str(r.get("day") or "") for r in desk_rows}
    sess_set = set(sessions)
    call_in = sorted(d for d in call_days if d in sess_set)
    # also count call days outside session list (shouldn't happen often)
    call_extra = sorted(d for d in call_days if d not in sess_set)
    no_call = sorted(d for d in sessions if d not in call_days)
    by_m_call: Dict[str, int] = defaultdict(int)
    by_m_sess: Dict[str, int] = defaultdict(int)
    by_m_nocall: Dict[str, int] = defaultdict(int)
    for d in sessions:
        by_m_sess[d[:7]] += 1
    for d in call_in:
        by_m_call[d[:7]] += 1
    for d in no_call:
        by_m_nocall[d[:7]] += 1
    months = []
    for ym in sorted(by_m_sess):
        s = by_m_sess[ym]
        c = by_m_call.get(ym, 0)
        n = by_m_nocall.get(ym, 0)
        months.append(
            {
                "month": ym,
                "sessions": s,
                "call_days": c,
                "no_call_days": n,
                "call_day_pct": round(100.0 * c / s, 1) if s else 0.0,
                "calls": sum(1 for r in desk_rows if str(r.get("day") or "").startswith(ym)),
            }
        )
    return {
        "sessions": len(sessions),
        "call_days": len(call_in),
        "no_call_days": len(no_call),
        "call_day_pct": round(100.0 * len(call_in) / len(sessions), 1) if sessions else 0.0,
        "calls": len(desk_rows),
        "hit_pct": hit_pct(desk_rows),
        "wins": sum(1 for r in desk_rows if r.get("win")),
        "losses": sum(1 for r in desk_rows if not r.get("win")),
        "buy": sum(1 for r in desk_rows if _side(r) == "BUY"),
        "sell": sum(1 for r in desk_rows if _side(r) == "SELL"),
        "multi_call_days": sum(
            1
            for d, n in (
                (d, sum(1 for r in desk_rows if str(r.get("day") or "") == d))
                for d in call_in
            )
            if n > 1
        ),
        "call_days_outside_calendar": call_extra,
        "months": months,
        "no_call_day_list": no_call,
        "call_day_list": call_in,
    }


def main() -> None:
    t0 = time.time()
    print(f"1y call coverage {START} → {END}", flush=True)
    sessions = trading_sessions(START, END)
    print(f"  trading sessions={len(sessions)}", flush=True)

    dual = json.loads(CACHE_DUAL_10Y.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH_10Y.read_text(encoding="utf-8"))
    gaps = gap_map()
    active = fs._active_days(sessions, fs._load_daily()) if sessions else set()
    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ = _champ_floor([dict(r, track="champion") for r in dual["dual15"]["champion"]])
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]
    crown_by_risk = path_u.get("crown_by_risk") or {}
    good_by_risk = path_u.get("good_by_risk") or {}
    champ_native = path_u.get("champ_native") or champ
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
        rows = _clip(fn(**kw), START, END)
        cov = coverage(rows, sessions)
        results[name] = cov
        print(
            f"  {name}: calls={cov['calls']} | call_days={cov['call_days']} | "
            f"no_call={cov['no_call_days']} / {cov['sessions']} ({cov['call_day_pct']}%)",
            flush=True,
        )

    payload = {
        "status": "HOLDING",
        "window": {"start": START, "end": END},
        "trading_sessions": len(sessions),
        "session_first": sessions[0] if sessions else None,
        "session_last": sessions[-1] if sessions else None,
        "results": results,
        "elapsed_s": round(time.time() - t0, 1),
    }
    # slim JSON for ledger: drop long day lists from non-focus except keep V5/P75 lists
    slim = {
        **payload,
        "results": {
            k: {
                **{kk: vv for kk, vv in v.items() if kk not in ("no_call_day_list", "call_day_list")},
                **(
                    {
                        "no_call_day_list": v["no_call_day_list"],
                        "call_day_list": v["call_day_list"],
                    }
                    if k in ("ACC100_MULTI_V5", "ACC_WIDE_P75", "ACC_WIDE_P75_CAP2")
                    else {}
                ),
            }
            for k, v in results.items()
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ACC_1Y_CALL_COVERAGE.json").write_text(
        json.dumps(slim, indent=2, default=str), encoding="utf-8"
    )
    (LEDGER / "ACC_1Y_CALL_COVERAGE.json").write_text(
        json.dumps(slim, indent=2, default=str), encoding="utf-8"
    )

    n_sess = len(sessions)
    lines = [
        f"# ACC desks — 1y call days vs no-call days (to {END})",
        "",
        "**Status: HOLDING**",
        "",
        f"**Window:** `{START}` → `{END}`",
        f"**NSE trading sessions:** **{n_sess}** "
        f"(`{sessions[0]}` → `{sessions[-1]}`)" if sessions else "",
        "",
        "## Complete coverage",
        "",
        "| Desk | Calls | Call days | No-call days | Sessions | Call-day % | Hit % | Multi-call days |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, _ in desks:
        r = results[name]
        lines.append(
            f"| `{name}` | {r['calls']} | **{r['call_days']}** | **{r['no_call_days']}** | "
            f"{r['sessions']} | {r['call_day_pct']}% | {r['hit_pct']} | {r['multi_call_days']} |"
        )

    # Focus month tables
    focus = [
        "ACC100_MULTI_V5",
        "ACC_WIDE_P90",
        "ACC_WIDE_P85",
        "ACC_WIDE_P75",
        "ACC_WIDE_P75_CAP2",
    ]
    lines += ["", "## Month-by-month (sessions / call days / no-call days)", ""]
    for name in focus:
        r = results[name]
        lines += [
            f"### `{name}` — {r['call_days']} call days · {r['no_call_days']} no-call · "
            f"{r['calls']} calls @ {r['hit_pct']}%",
            "",
            "| Month | Sessions | Call days | No-call | Call-day % | Calls |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for m in r["months"]:
            lines.append(
                f"| {m['month']} | {m['sessions']} | {m['call_days']} | {m['no_call_days']} | "
                f"{m['call_day_pct']}% | {m['calls']} |"
            )
        lines.append("")

    # V5 no-call list by month summary + full list
    v5 = results["ACC100_MULTI_V5"]
    lines += [
        "## `ACC100_MULTI_V5` — days with a call",
        "",
        f"**{v5['call_days']}** days with call · **{v5['no_call_days']}** days with no call "
        f"(of {v5['sessions']} sessions)",
        "",
        "<details><summary>Call days list</summary>",
        "",
        ", ".join(f"`{d}`" for d in v5["call_day_list"]),
        "",
        "</details>",
        "",
        "<details><summary>No-call days list</summary>",
        "",
        ", ".join(f"`{d}`" for d in v5["no_call_day_list"]),
        "",
        "</details>",
        "",
        "## Hold",
        "",
        "All desks remain HOLDING. JSON: `ACC_1Y_CALL_COVERAGE.json`",
        "",
        f"Elapsed {payload['elapsed_s']}s",
        "",
    ]
    md = OUT / "ACC_1Y_CALL_COVERAGE.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (LEDGER / "ACC_1Y_CALL_COVERAGE.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", md, flush=True)


if __name__ == "__main__":
    main()
