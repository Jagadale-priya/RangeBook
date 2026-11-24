"""Hold all ACC desks; 1y report through today's date.

  python -u prod_live/tests/builders/research_acc_all_desks_1y_today.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _side  # noqa: E402
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

END = date.today().strftime("%Y-%m-%d")
START_1Y = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 2)


def month_table(rows: List[dict]) -> List[Dict[str, Any]]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        day = str(r.get("day") or "")
        if len(day) >= 7:
            by[day[:7]].append(r)
    out = []
    for ym in sorted(by):
        rs = by[ym]
        out.append(
            {
                "month": ym,
                "n": len(rs),
                "hit_pct": hit_pct(rs),
                "wins": sum(1 for r in rs if r.get("win")),
                "losses": sum(1 for r in rs if not r.get("win")),
                "points": (_agg(rs) or {}).get("points"),
                "buy": sum(1 for r in rs if _side(r) == "BUY"),
                "sell": sum(1 for r in rs if _side(r) == "SELL"),
            }
        )
    return out


def score_1y(desk: List[dict]) -> Dict[str, Any]:
    rs = _clip(desk, START_1Y, END)
    st = _agg(rs) if rs else {"n": 0, "hit_pct": 0.0, "points": 0.0}
    days = sorted({str(r.get("day") or "") for r in rs})
    return {
        "n": len(rs),
        "hit_pct": hit_pct(rs),
        "perfect": bool(rs) and is_perfect(rs),
        "points": st.get("points"),
        "wins": sum(1 for r in rs if r.get("win")),
        "losses": sum(1 for r in rs if not r.get("win")),
        "buy": sum(1 for r in rs if _side(r) == "BUY"),
        "sell": sum(1 for r in rs if _side(r) == "SELL"),
        "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "months": month_table(rs),
        "rows": [
            {
                "day": r.get("day"),
                "hm": r.get("hm"),
                "side": _side(r),
                "win": bool(r.get("win")),
                "p_t1": r.get("p_t1"),
                "holding_tag": r.get("holding_tag") or r.get("accurate_tag") or r.get("track"),
                "desk_tag": r.get("desk_tag"),
                "points": r.get("points"),
            }
            for r in sorted(rs, key=lambda x: (str(x.get("day") or ""), str(x.get("hm") or "")))
        ],
    }


def main() -> None:
    t0 = time.time()
    print(f"HOLD all desks — 1y report {START_1Y} → {END}", flush=True)

    dual = json.loads(CACHE_DUAL_10Y.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH_10Y.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_1Y < d <= END]
    active = fs._active_days(sess, fs._load_daily()) if sess else set()

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
        print(f"  {name}…", flush=True)
        sc = score_1y(fn(**kw))
        results[name] = sc
        print(
            f"    n={sc['n']} hit={sc['hit_pct']}% W/L={sc['wins']}/{sc['losses']} "
            f"pts={sc['points']} · {sc['first_day']}→{sc['last_day']}",
            flush=True,
        )

    payload = {
        "status": "HOLDING",
        "not_live": True,
        "keep_all": [d[0] for d in desks],
        "window": {"start": START_1Y, "end": END, "label": "1y_to_today"},
        "results": {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in results.items()},
        "rows_by_desk": {k: v["rows"] for k, v in results.items()},
        "elapsed_s": round(time.time() - t0, 1),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ACC_ALL_DESKS_1Y_TODAY.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (LEDGER / "ACC_ALL_DESKS_1Y_TODAY.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    # Focus month table on V5 + P85 + P75 + P75_CAP2
    focus = [
        "ACC100_MULTI_V5",
        "ACC_WIDE_P92",
        "ACC_WIDE_P85",
        "ACC_WIDE_P80",
        "ACC_WIDE_P75",
        "ACC_WIDE_P75_CAP2",
    ]

    lines = [
        f"# All held ACC desks — 1y to today ({END})",
        "",
        "**Status: HOLDING** — keep all desks; not live.",
        "",
        f"**Window:** `{START_1Y}` → `{END}` (last 365 days through today)",
        "",
        f"Elapsed {payload['elapsed_s']}s",
        "",
        "## Summary",
        "",
        "| Desk | N | Hit | W | L | Points | Buy | Sell | First | Last |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for name, _ in desks:
        r = results[name]
        lines.append(
            f"| `{name}` | {r['n']} | {r['hit_pct']} | {r['wins']} | {r['losses']} | "
            f"{r['points']} | {r['buy']} | {r['sell']} | {r['first_day']} | {r['last_day']} |"
        )

    lines += ["", "## Month-by-month (focus desks)", ""]
    for name in focus:
        r = results[name]
        lines += [f"### `{name}` — {r['n']} @ {r['hit_pct']}%", ""]
        if not r["months"]:
            lines.append("_No rows in window._")
        else:
            lines += ["| Month | N | Hit | W | L | Pts | B/S |", "|---|---:|---:|---:|---:|---:|---|"]
            for m in r["months"]:
                lines.append(
                    f"| {m['month']} | {m['n']} | {m['hit_pct']} | {m['wins']} | {m['losses']} | "
                    f"{m['points']} | {m['buy']}/{m['sell']} |"
                )
        lines.append("")

    lines += [
        "## Call list — `ACC100_MULTI_V5` (100% desk)",
        "",
        "| Day | HM | Side | Win | Tag |",
        "|---|---|---|---|---|",
    ]
    for row in results["ACC100_MULTI_V5"]["rows"]:
        lines.append(
            f"| {row['day']} | {row['hm']} | {row['side']} | "
            f"{'W' if row['win'] else 'L'} | `{row['holding_tag']}` |"
        )

    lines += [
        "",
        "## Hold",
        "",
        "Keep **all** desks. Full row dumps in JSON `rows_by_desk`.",
        "",
        "JSON: `ACC_ALL_DESKS_1Y_TODAY.json`",
        "",
    ]
    md = OUT / "ACC_ALL_DESKS_1Y_TODAY.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (LEDGER / "ACC_ALL_DESKS_1Y_TODAY.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", md, flush=True)


if __name__ == "__main__":
    main()
