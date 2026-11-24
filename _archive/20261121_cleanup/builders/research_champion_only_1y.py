"""CHAMPION only — last 1y deep test (no proven/good/crown).

  python -u prod_live/tests/builders/research_champion_only_1y.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

from accuracy_max_6m import _agg  # noqa: E402
from prod_live.logic.stack import union_day_cap2  # noqa: E402
import live_final_1y_months_accurate as hold  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
START, END = hold.START, hold.END


def main() -> int:
    print(f"CHAMPION only · 1y {START} → {END}", flush=True)
    live = hold._build_live_stack(START, END)
    champ = hold._clean(live["champ"])
    alone = hold._clean(union_day_cap2({"champion": champ}))
    sess = live["sess"]

    sc_raw = _agg(champ)
    sc = _agg(alone)

    # monthly
    by_m: Dict[str, List[dict]] = defaultdict(list)
    for r in alone:
        by_m[str(r.get("day") or "")[:7]].append(r)
    sess_m: Dict[str, List[str]] = defaultdict(list)
    for d in sess:
        sess_m[d[:7]].append(d)

    lines = [
        "# CHAMPION only — 1y",
        "",
        f"**Window:** `{START}` → `{END}` · sessions {len(sess)}",
        "**Rule:** champion pool alone · day-cap2 · same-side (no proven/good/crown)",
        "**Floors:** BUY p≥0.55 · SELL p≥0.58 (`_champ_floor`)",
        "",
        f"| Slice | N | Hit% | W/L | Points |",
        f"|---|---:|---:|---|---:|",
        f"| Raw champ pool | {sc_raw.get('n')} | {sc_raw.get('hit_pct')} | "
        f"{sc_raw.get('wins')}/{sc_raw.get('losses')} | {sc_raw.get('points')} |",
        f"| **Alone cap2** | **{sc.get('n')}** | **{sc.get('hit_pct')}** | "
        f"{sc.get('wins')}/{sc.get('losses')} | {sc.get('points')} |",
        "",
        "## Monthly",
        "",
        "| Month | Sessions | N | Hit% | W/L | Days w/ call | Days quiet |",
        "|---|---:|---:|---:|---|---:|---:|",
    ]

    monthly = []
    for ym in sorted(sess_m):
        days = sess_m[ym]
        rows = by_m.get(ym, [])
        st = _agg(rows)
        cdays = {r["day"] for r in rows}
        monthly.append(
            {
                "month": ym,
                "sessions": len(days),
                "n": st.get("n"),
                "hit_pct": st.get("hit_pct"),
                "wins": st.get("wins"),
                "losses": st.get("losses"),
                "days_with_call": len(cdays),
                "days_no_call": len(set(days) - cdays),
            }
        )
        lines.append(
            f"| {ym} | {len(days)} | {st.get('n')} | {st.get('hit_pct')} | "
            f"{st.get('wins')}/{st.get('losses')} | {len(cdays)} | "
            f"{len(set(days) - cdays)} |"
        )

    # side split
    buys = [r for r in alone if str(r.get("decision") or "").upper().startswith("B")]
    sells = [r for r in alone if str(r.get("decision") or "").upper().startswith("S")]
    sb, ss = _agg(buys), _agg(sells)
    lines.extend(
        [
            "",
            "## By side",
            "",
            "| Side | N | Hit% | W/L |",
            "|---|---:|---:|---|",
            f"| BUY | {sb.get('n')} | {sb.get('hit_pct')} | {sb.get('wins')}/{sb.get('losses')} |",
            f"| SELL | {ss.get('n')} | {ss.get('hit_pct')} | {ss.get('wins')}/{ss.get('losses')} |",
            "",
            "## All calls",
            "",
            "| # | Day | HM | Side | Win | p_t1 | Points |",
            "|---:|---|---|---|---|---:|---:|",
        ]
    )

    calls_out = []
    for i, r in enumerate(sorted(alone, key=lambda x: (x.get("day"), x.get("hm"))), 1):
        side = str(r.get("decision") or "").upper()
        w = "W" if r.get("win") else "L"
        lines.append(
            f"| {i} | {r.get('day')} | {r.get('hm')} | {side} | {w} | "
            f"{r.get('p_t1')} | {r.get('points')} |"
        )
        calls_out.append(
            {
                "day": r.get("day"),
                "hm": r.get("hm"),
                "side": side,
                "win": r.get("win"),
                "p_t1": r.get("p_t1"),
                "points": r.get("points"),
            }
        )

    lines.extend(
        [
            "",
            f"**N={sc.get('n')}** · hit **{sc.get('hit_pct')}%** "
            f"({sc.get('wins')}W / {sc.get('losses')}L)",
            "",
            "## Verdict",
            "",
            f"CHAMPION alone: **{sc.get('n')}@{sc.get('hit_pct')}%** on golden 1y. "
            f"Higher hit than full stack (75.11%) but much thinner than GOOD/CROWN volume.",
            "",
        ]
    )

    payload = {
        "window": {"start": START, "end": END, "sessions": len(sess)},
        "raw": sc_raw,
        "alone_cap2": sc,
        "by_side": {"BUY": sb, "SELL": ss},
        "monthly": monthly,
        "calls": calls_out,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "CHAMPION_ONLY_1Y.md"
    js = OUT / "CHAMPION_ONLY_1Y.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    print(
        f"CHAMPION alone {sc.get('n')}@{sc.get('hit_pct')}% "
        f"({sc.get('wins')}W/{sc.get('losses')}L)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
