"""Current-month LIVE logic test — same books as live sessions + P2F day/Cap2.

Never blocks. Month summary + every call with multi-tags.

  python -u prod_live/tests/builders/research_live_logic_month_multitag.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Set

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "prod_live"))
import path_setup  # noqa: F401,E402

from accuracy_max_6m import _champ_floor, _agg  # noqa: E402
from research_confirm_dual_tf_deep import _clip  # noqa: E402
from research_100pct_deeper_more_calls import gap_map  # noqa: E402
from prod_live.logic.accurate_desks import build_all_accurate_desks  # noqa: E402
from prod_live.logic.p2f_day_live import (  # noqa: E402
    LIVE_DAY_DESKS,
    build_p2f_day_desks,
    load_phase2f_day_recipes,
)
from prod_live.logic.p2f_cap2_live import (  # noqa: E402
    LIVE_CAP2_DESKS,
    build_p2f_cap2_desks,
    load_phase2f_cap2_recipes,
)
from prod_live.logic.combined_live_book import combine_live_rows  # noqa: E402
from prod_live.holding_accurate.rebuild_streams import rebuild_all_tags  # noqa: E402
from prod_live.holding_accurate.registry import stamp_fields_for  # noqa: E402

import research_live_logic_1y_multitag as base  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"

TODAY = date.today()
START = TODAY.replace(day=1).isoformat()
END = TODAY.isoformat()
YM = TODAY.strftime("%Y-%m")


def main() -> None:
    t0 = time.time()
    print(f"LIVE logic current month {START} → {END}", flush=True)

    print("  volume stack…", flush=True)
    vol = base.build_volume(START, END)
    sess = vol["sess"]

    print("  P2F day + Cap2…", flush=True)
    dual = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gaps = gap_map()
    active = vol["active"]
    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ = _champ_floor(
        [dict(r, track="champion") for r in dual["dual15"]["champion"]]
    )
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]
    champ_native = path_u.get("champ_native") or champ
    phase1 = build_all_accurate_desks(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=path_u.get("crown_by_risk") or {},
        good_by_risk=path_u.get("good_by_risk") or {},
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active,
    )

    day_recipes = load_phase2f_day_recipes()
    cap2_recipes = load_phase2f_cap2_recipes()
    all_tags: List[str] = []
    seen: Set[str] = set()
    for recipes in (day_recipes, cap2_recipes):
        for meta in recipes.values():
            for t in meta.get("stream_tags_research") or []:
                if t not in seen:
                    seen.add(t)
                    all_tags.append(t)
    print(f"  rebuild {len(all_tags)} stream tags…", flush=True)
    by_tag = rebuild_all_tags(
        all_tags, path_u, gaps, active, dual15, dual5, proven, champ
    )
    p2f_day_raw = build_p2f_day_desks(phase1, by_tag)
    p2f_cap2_raw = build_p2f_cap2_desks(phase1, by_tag)

    p2f_day = {
        k: [base.enrich_p2f_row(r, k) for r in _clip(v, START, END)]
        for k, v in p2f_day_raw.items()
    }
    p2f_cap2 = {
        k: [base.enrich_p2f_row(r, k) for r in _clip(v, START, END)]
        for k, v in p2f_cap2_raw.items()
    }

    combined = combine_live_rows(
        volume_rows=vol["volume_all"],
        p2f_day=p2f_day,
        p2f_cap2=p2f_cap2,
    )
    # Prefer volume sessions; fall back to call days so sparse months still list
    call_days = sorted(
        {str(r.get("day") or "") for r in combined["all_rows"] if r.get("day")}
    )
    sess_for_month = sess or call_days
    months = base.month_tables(combined["all_rows"], sess_for_month)
    month = next((m for m in months if m["month"] == YM), None)
    if month is None:
        # Force current-month bucket from combined rows
        sub = [
            r
            for r in combined["all_rows"]
            if str(r.get("day") or "").startswith(YM)
        ]
        fake_sess = sorted({str(r.get("day") or "") for r in sub})
        months = base.month_tables(sub, fake_sess or [f"{YM}-01"])
        month = next((m for m in months if m["month"] == YM), None)
    if month is None:
        month = {
            "month": YM,
            "sessions": len(sess),
            "n_all": 0,
            "n_primary": 0,
            "hit_all": 0.0,
            "hit_primary": 0.0,
            "volume_n": 0,
            "volume_hit": 0.0,
            "p2f_day_n": 0,
            "p2f_day_hit": 0.0,
            "p2f_cap2_n": 0,
            "p2f_cap2_hit": 0.0,
            "notify_n": 0,
            "blocked": 0,
            "calls": [],
        }
    # Keep volume session count honest in rollup
    month["volume_sessions"] = len(sess)
    month["note"] = (
        None
        if sess
        else "Volume pool has 0 sessions this month so far; P2F path calls still listed"
    )

    components: Dict[str, Any] = {
        "volume_stack": base.score(vol["stack"]),
        "agree_extras": base.score(vol["extras"]),
        "volume_plus_agree": base.score(vol["volume_all"]),
    }
    for desk in LIVE_DAY_DESKS:
        components[f"day|{desk}"] = base.score(p2f_day.get(desk) or [])
    for desk in LIVE_CAP2_DESKS:
        components[f"cap2|{desk}"] = base.score(p2f_cap2.get(desk) or [])

    ca = {
        "n_all_rows": combined["n_all"],
        "n_primary": combined["n_primary"],
        "overlap_days": combined["overlap_days"],
        "hit_all": base.hit_pct(combined["all_rows"]),
        "hit_primary": base.hit_pct(combined["primary_rows"]),
        "score_all": base.score(combined["all_rows"]),
        "score_primary": base.score(combined["primary_rows"]),
    }

    payload = {
        "window": {"start": START, "end": END, "sessions": len(sess), "month": YM},
        "policy": "notify_override_never_block",
        "blocked": 0,
        "combined": ca,
        "components": components,
        "month": month,
        "elapsed_s": round(time.time() - t0, 1),
    }

    lines = [
        f"# LIVE logic — current month {YM}",
        "",
        f"**Window:** `{START}` → `{END}` · volume sessions: **{len(sess)}**",
        "**Books:** volume stack + AGREE + P2F day + Cap2 (same as live)",
        "**Overlap:** never block · `ALREADY_OPEN_OTHER_DESK` · primary override only",
        "**Blocked:** **0**",
    ]
    if not sess:
        lines.append(
            "**Note:** volume pool has **0** sessions in this window so far "
            "(live stack silent); P2F path desks may still fire."
        )
    lines.extend(
        [
            "",
            "## Headline",
            "",
            "| Slice | N | Hit | Wins | Losses | Points |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for label, key in (
        ("Volume stack", "volume_stack"),
        ("Volume + AGREE extras", "volume_plus_agree"),
    ):
        s = components[key]
        lines.append(
            f"| {label} | {s['n']} | {s['hit_pct']}% | {s['wins']} | {s['losses']} | {s.get('points')} |"
        )
    for desk in LIVE_DAY_DESKS:
        s = components[f"day|{desk}"]
        lines.append(
            f"| P2F day `{desk}` | {s['n']} | {s['hit_pct']}% | {s['wins']} | {s['losses']} | {s.get('points')} |"
        )
    for desk in LIVE_CAP2_DESKS:
        s = components[f"cap2|{desk}"]
        lines.append(
            f"| P2F Cap2 `{desk}` | {s['n']} | {s['hit_pct']}% | {s['wins']} | {s['losses']} | {s.get('points')} |"
        )
    lines.extend(
        [
            f"| **Combined all** | **{ca['n_all_rows']}** | **{ca['hit_all']}%** | "
            f"{ca['score_all']['wins']} | {ca['score_all']['losses']} | {ca['score_all'].get('points')} |",
            f"| **Primary only** | **{ca['n_primary']}** | **{ca['hit_primary']}%** | "
            f"{ca['score_primary']['wins']} | {ca['score_primary']['losses']} | {ca['score_primary'].get('points')} |",
            "",
            f"Overlap days: **{ca['overlap_days']}**",
            "",
            "## Month rollup",
            "",
            "| Month | Sess | All N | All hit | Primary N | Primary hit | Vol | Day | Cap2 | Notify | Blocked |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            f"| {month['month']} | {month.get('volume_sessions', month['sessions'])} | "
            f"{month['n_all']} | {month['hit_all']}% | "
            f"{month['n_primary']} | {month['hit_primary']}% | {month['volume_n']} | "
            f"{month['p2f_day_n']} | {month['p2f_cap2_n']} | {month['notify_n']} | 0 |",
            "",
            f"## All calls this month ({month['n_all']} rows)",
            "",
            "| Day | HM | Side | Book | accurate_tag | accuracy_tag | Primary | Notify | Win | Multi-tags |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for c0 in month.get("calls") or []:
        tags = ", ".join(str(t) for t in (c0.get("tags") or [])[:8])
        if len(c0.get("tags") or []) > 8:
            tags += ", …"
        lines.append(
            f"| {c0['day']} | {c0.get('hm') or ''} | {c0.get('decision') or ''} | "
            f"{c0.get('book') or ''} | `{c0.get('accurate_tag') or c0.get('source_desk') or ''}` | "
            f"`{c0.get('accuracy_tag') or ''}` | "
            f"{'Y' if c0.get('is_primary') else ''} | "
            f"{c0.get('notify_code') or ''} | "
            f"{'W' if c0.get('win') else 'L'} | {tags} |"
        )

    lines.append("")
    lines.append("## Primary calls only")
    lines.append("")
    lines.append(
        "| Day | HM | Side | Book | accurate_tag | accuracy_tag | Win | Multi-tags |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for c0 in month.get("calls") or []:
        if not c0.get("is_primary"):
            continue
        tags = ", ".join(str(t) for t in (c0.get("tags") or [])[:6])
        lines.append(
            f"| {c0['day']} | {c0.get('hm') or ''} | {c0.get('decision') or ''} | "
            f"{c0.get('book') or ''} | `{c0.get('accurate_tag') or ''}` | "
            f"`{c0.get('accuracy_tag') or ''}` | "
            f"{'W' if c0.get('win') else 'L'} | {tags} |"
        )

    lines.extend(
        [
            "",
            f"Elapsed {payload['elapsed_s']}s",
            "",
            "JSON: `LIVE_LOGIC_MONTH_MULTITAG.json`",
        ]
    )

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "LIVE_LOGIC_MONTH_MULTITAG.md"
    js = OUT / "LIVE_LOGIC_MONTH_MULTITAG.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("\n".join(lines), flush=True)
    print(f"Wrote {md}", flush=True)


if __name__ == "__main__":
    main()
