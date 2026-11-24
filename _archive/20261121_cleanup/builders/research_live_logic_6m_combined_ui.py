"""6m LIVE logic — UI-combined calls (1 entry → 1 call, tags accuracy-first).

Never blocks distinct (day, side, hm) calls.
Retest after collapse redesign.

  python -u prod_live/tests/builders/research_live_logic_6m_combined_ui.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Set

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "prod_live"))
import path_setup  # noqa: F401,E402

from accuracy_max_6m import _champ_floor  # noqa: E402
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
from prod_live.logic.combined_live_book import (  # noqa: E402
    call_key,
    combine_live_rows,
)
from prod_live.holding_accurate.rebuild_streams import rebuild_all_tags  # noqa: E402

import research_live_logic_1y_multitag as base  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"

END = date.today().isoformat()
START = (date.today() - timedelta(days=183)).isoformat()


def call_record(r: dict) -> Dict[str, Any]:
    return {
        "day": r.get("day"),
        "hm": r.get("hm"),
        "decision": str(r.get("decision") or "").upper(),
        "track": r.get("track"),
        "win": bool(r.get("win")),
        "points": r.get("points"),
        "book": r.get("book"),
        "accurate_tag": r.get("accurate_tag"),
        "accuracy_tag": r.get("accuracy_tag"),
        "desks_satisfied": list(r.get("desks_satisfied") or []),
        "also_satisfies": list(r.get("also_satisfies") or []),
        "desk_count": r.get("desk_count"),
        "tags": list(r.get("tags") or r.get("accuracy_tags") or []),
        "multi_desk": bool(r.get("multi_desk")),
        "notify_code": r.get("notify_code"),
        "ui_combined": bool(r.get("ui_combined")),
    }


def main() -> None:
    t0 = time.time()
    print(f"LIVE logic 6m UI-combined {START} → {END}", flush=True)

    vol = base.build_volume(START, END)
    sess = vol["sess"]

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
    phase1 = build_all_accurate_desks(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=path_u.get("crown_by_risk") or {},
        good_by_risk=path_u.get("good_by_risk") or {},
        champ_rows=path_u.get("champ_native") or champ,
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
    print(f"  rebuild {len(all_tags)} tags…", flush=True)
    by_tag = rebuild_all_tags(
        all_tags, path_u, gaps, active, dual15, dual5, proven, champ
    )
    p2f_day = {
        k: [base.enrich_p2f_row(r, k) for r in _clip(v, START, END)]
        for k, v in build_p2f_day_desks(phase1, by_tag).items()
    }
    p2f_cap2 = {
        k: [base.enrich_p2f_row(r, k) for r in _clip(v, START, END)]
        for k, v in build_p2f_cap2_desks(phase1, by_tag).items()
    }

    combined = combine_live_rows(
        volume_rows=vol["volume_all"],
        p2f_day=p2f_day,
        p2f_cap2=p2f_cap2,
    )
    ui = combined["ui_rows"]
    raw = combined["raw_rows"]

    # Gates
    raw_keys = {call_key(r) for r in raw}
    ui_keys = {call_key(r) for r in ui}
    missing = raw_keys - ui_keys
    # Every UI key must exist in raw
    extra = ui_keys - raw_keys
    gate_no_block = combined["blocked_distinct"] == 0 and not missing and not extra
    # Tags on multi-desk calls: first tag should be highest-acc desk
    bad_order = []
    for r in ui:
        desks = r.get("desks_satisfied") or []
        if len(desks) >= 2:
            tags = r.get("tags") or []
            if not tags or tags[0] != desks[0]:
                bad_order.append(
                    {
                        "key": call_key(r),
                        "desks": desks,
                        "tags0": tags[0] if tags else None,
                    }
                )
    gate_order = len(bad_order) == 0

    months = base.month_tables(ui, sess or sorted({str(r.get("day")) for r in ui if r.get("day")}))
    # Patch month calls with richer records
    for m in months:
        m["calls"] = [call_record(r) for r in ui if str(r.get("day") or "").startswith(m["month"])]
        m["multi_desk_n"] = sum(1 for c in m["calls"] if c.get("multi_desk"))

    ca = {
        "n_raw": combined["n_raw"],
        "n_ui": combined["n_ui"],
        "n_multi_desk": combined["n_multi_desk"],
        "hit_ui": base.hit_pct(ui),
        "score_ui": base.score(ui),
        "blocked_distinct": combined["blocked_distinct"],
        "gate_no_block": gate_no_block,
        "gate_accuracy_first": gate_order,
        "bad_order_n": len(bad_order),
    }

    overall = "PASS" if gate_no_block and gate_order else "FAIL"
    payload = {
        "window": {"start": START, "end": END, "sessions": len(sess)},
        "policy": combined["policy"],
        "overall": overall,
        "combined": ca,
        "components": {
            "volume": base.score(vol["volume_all"]),
            **{f"day|{d}": base.score(p2f_day.get(d) or []) for d in LIVE_DAY_DESKS},
            **{f"cap2|{d}": base.score(p2f_cap2.get(d) or []) for d in LIVE_CAP2_DESKS},
        },
        "months": months,
        "bad_order_sample": bad_order[:10],
        "elapsed_s": round(time.time() - t0, 1),
    }

    lines = [
        "# LIVE logic 6m — UI combined calls (accuracy-first tags)",
        "",
        f"**Window:** `{START}` → `{END}` · **{len(sess)}** volume sessions",
        "**Rule:** same `(day, side, hm)` → **1 UI call** with all desk tags merged; "
        "**highest accuracy tag first**",
        "**Distinct calls:** never blocked/dropped",
        f"**Overall:** **{overall}**",
        "",
        "## Headline",
        "",
        f"| Metric | Value |",
        f"|---|---:|",
        f"| Raw desk firings | {ca['n_raw']} |",
        f"| UI combined calls | **{ca['n_ui']}** |",
        f"| Multi-desk combined | {ca['n_multi_desk']} |",
        f"| UI hit% | {ca['hit_ui']}% |",
        f"| Blocked distinct | **{ca['blocked_distinct']}** |",
        f"| Gate no-block | {'PASS' if gate_no_block else 'FAIL'} |",
        f"| Gate accuracy-first tags | {'PASS' if gate_order else 'FAIL'} |",
        "",
        "## Month summary (UI calls)",
        "",
        "| Month | Sess | UI N | Hit | Multi-desk | Blocked |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for m in months:
        lines.append(
            f"| {m['month']} | {m['sessions']} | {m['n_all']} | {m['hit_all']}% | "
            f"{m.get('multi_desk_n', 0)} | 0 |"
        )

    lines.extend(["", "## Per-month UI calls", ""])
    for m in months:
        lines.append(
            f"### {m['month']} — {m['n_all']} UI calls "
            f"({m.get('multi_desk_n', 0)} multi-desk)"
        )
        lines.append("")
        lines.append(
            "| Day | HM | Side | Primary accurate_tag | accuracy_tag | "
            "Desks satisfied | Win | Tags (acc-first) |"
        )
        lines.append("|---|---|---|---|---|---|---|---|")
        for c0 in m["calls"]:
            desks = ", ".join(f"`{d}`" for d in (c0.get("desks_satisfied") or [])[:6])
            if len(c0.get("desks_satisfied") or []) > 6:
                desks += ", …"
            tags = ", ".join(str(t) for t in (c0.get("tags") or [])[:8])
            if len(c0.get("tags") or []) > 8:
                tags += ", …"
            lines.append(
                f"| {c0['day']} | {c0.get('hm') or ''} | {c0.get('decision') or ''} | "
                f"`{c0.get('accurate_tag') or ''}` | `{c0.get('accuracy_tag') or ''}` | "
                f"{desks} | {'W' if c0.get('win') else 'L'} | {tags} |"
            )
        lines.append("")

    lines.append(f"Elapsed {payload['elapsed_s']}s")

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "LIVE_LOGIC_6M_COMBINED_UI.md"
    js = OUT / "LIVE_LOGIC_6M_COMBINED_UI.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("\n".join(lines[:45]), flush=True)
    print(f"Wrote {md}", flush=True)
    print(f"OVERALL {overall} ui={ca['n_ui']} raw={ca['n_raw']} blocked={ca['blocked_distinct']}", flush=True)
    raise SystemExit(0 if overall == "PASS" else 1)


if __name__ == "__main__":
    main()
