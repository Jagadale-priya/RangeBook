"""1y LIVE logic test — same books as live sessions + P2F day/Cap2.

Never blocks calls (notify/override on overlap).
Report: month summary + every call with multi-tags.

  python -u prod_live/tests/builders/research_live_logic_1y_multitag.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "prod_live"))
import path_setup  # noqa: F401,E402

import dual_tf_15m_5m_agree as d  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import POOL, PRIORITY, _champ_floor, _agg  # noqa: E402
from research_confirm_dual_tf_deep import _clip  # noqa: E402
from research_100pct_deeper_more_calls import gap_map  # noqa: E402
from prod_live.logic.accurate_desks import build_all_accurate_desks  # noqa: E402
from prod_live.logic.p2f_day_live import (  # noqa: E402
    LIVE_DAY_DESKS,
    WINDOW_1Y,
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

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"

START = WINDOW_1Y["start"]  # 2025-11-15
END = WINDOW_1Y["end"]  # 2026-11-15


def _clean(rows: List[dict]) -> List[dict]:
    out = []
    for r in rows:
        if r is None:
            continue
        rr = dict(r)
        if "win" not in rr:
            o = rr.get("outcome")
            if o == "t1_before_sl":
                rr["win"] = True
            elif o in ("sl_before_t1", "same_bar_both"):
                rr["win"] = False
        out.append(rr)
    return out


def _key(r: dict) -> Tuple[str, str, str]:
    return (r["day"], str(r.get("decision") or "").upper(), str(r.get("hm") or ""))


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 2)


def score(rows: List[dict]) -> Dict[str, Any]:
    a = _agg(rows) or {}
    return {
        "n": len(rows),
        "hit_pct": hit_pct(rows),
        "wins": sum(1 for r in rows if r.get("win")),
        "losses": sum(1 for r in rows if not r.get("win")),
        "points": a.get("points"),
    }


def build_volume(start: str, end: str) -> Dict[str, Any]:
    """Same path as live sessions / live_final_1y_months_accurate."""
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    sessions_all, prod2_all, _ = fs._prod2(1400)
    sess = sorted(d for d in sessions_all if start <= d <= end)

    proven = [
        dict(r, track="proven_100", priority=PRIORITY["proven_100"])
        for r in pool["proven_100"]
        if start <= r["day"] <= end
    ]
    champ = _champ_floor([r for r in pool["champion"] if start <= r["day"] <= end])
    for r in champ:
        r["track"] = "champion"
        r["priority"] = PRIORITY["champion"]
    crown = [
        dict(r, track="crown_5m", priority=PRIORITY["crown_5m"])
        for r in pool["crown_5m"]
        if start <= r["day"] <= end
    ]
    good = [
        dict(r, track="good_prod2", priority=PRIORITY["good_prod2"])
        for r in prod2_all
        if start <= r["day"] <= end
    ]
    daily = fs._load_daily()
    active = fs._active_days(sess, daily)
    crown_htf = [r for r in crown if r["day"] in active]
    stack = _clean(
        fs._union(
            {
                "proven_100": proven,
                "good_prod2": good,
                "champion": champ,
                "crown_5m": crown_htf,
            },
            day_cap=2,
        )
    )
    books = d.build_books(
        {
            "sess": sess,
            "stack": stack,
            "good": good,
            "proven": proven,
            "champ": champ,
            "champ_raw": champ,
            "crown": crown_htf,
            "crown_htf": crown_htf,
            "active": active,
        }
    )
    agree_rows = _clean(books["agree_any5_5mentry"])
    agree_exact = {_key(r) for r in agree_rows}
    stamped = []
    for r in stack:
        rr = dict(r)
        ok = _key(rr) in agree_exact
        rr["accurate"] = ok
        rr["accurate_tag"] = "AGREE_15M_ANY5" if ok else None
        rr["book"] = "volume"
        stamped.append(rr)
    extras = []
    seen = {_key(r) for r in stamped}
    for r in agree_rows:
        if _key(r) in seen:
            continue
        rr = dict(r)
        rr["track"] = "agree_15m_any5"
        rr["accurate"] = True
        rr["accurate_tag"] = "AGREE_15M_ANY5"
        rr["book"] = "agree_extra"
        extras.append(rr)
        seen.add(_key(rr))
    return {
        "sess": sess,
        "stack": stamped,
        "extras": extras,
        "volume_all": stamped + extras,
        "active": active,
    }


def enrich_p2f_row(r: dict, desk: str) -> dict:
    """Ensure registry multi-tags are on the row."""
    rr = dict(r)
    fields = stamp_fields_for(desk)
    for k, v in fields.items():
        if k == "tags":
            existing = list(rr.get("tags") or [])
            seen = set(existing)
            for t in v or []:
                if t and t not in seen:
                    existing.append(t)
                    seen.add(t)
            rr["tags"] = existing
        elif v is not None and (rr.get(k) is None or k in ("lane", "status", "not_live")):
            rr[k] = v
    rr["accurate_tag"] = desk
    rr["desk_tag"] = desk
    return rr


def call_record(r: dict) -> Dict[str, Any]:
    return {
        "day": r.get("day"),
        "hm": r.get("hm"),
        "decision": str(r.get("decision") or "").upper(),
        "track": r.get("track"),
        "win": bool(r.get("win")),
        "points": r.get("points"),
        "p_t1": r.get("p_t1"),
        "book": r.get("book"),
        "source_desk": r.get("source_desk") or r.get("desk_tag"),
        "desk_tag": r.get("desk_tag"),
        "accurate_tag": r.get("accurate_tag"),
        "accuracy_tag": r.get("accuracy_tag") or r.get("accuracy_range_tag"),
        "accuracy_lo": r.get("accuracy_lo"),
        "accuracy_hi": r.get("accuracy_hi"),
        "accuracy_band": r.get("accuracy_band"),
        "logic_level": r.get("logic_level"),
        "lane": r.get("lane"),
        "status": r.get("status"),
        "mode": r.get("mode"),
        "tags": list(r.get("tags") or []),
        "is_primary": bool(r.get("is_primary")),
        "notify_code": r.get("notify_code"),
        "notify_msg": r.get("notify_msg"),
        "override_of": r.get("override_of"),
        "also_satisfies": list(r.get("also_satisfies") or []),
        "parallel_desks_same_day": list(r.get("parallel_desks_same_day") or []),
    }


def month_tables(rows: List[dict], sess: List[str]) -> List[Dict[str, Any]]:
    by_m_days: Dict[str, List[str]] = defaultdict(list)
    for day in sess:
        by_m_days[day[:7]].append(day)
    by_m: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        day = str(r.get("day") or "")
        if len(day) >= 7:
            by_m[day[:7]].append(r)
            # Include call days even when volume session list is empty
            if day not in by_m_days[day[:7]]:
                by_m_days[day[:7]].append(day)
    out = []
    for ym in sorted(by_m_days):
        days = sorted(set(by_m_days[ym]))
        sub = by_m.get(ym, [])
        prim = [r for r in sub if r.get("is_primary")]
        vol = [r for r in sub if r.get("book") in ("volume", "agree_extra")]
        dayb = [r for r in sub if r.get("book") == "p2f_day"]
        cap2 = [r for r in sub if r.get("book") == "p2f_cap2"]
        notify_n = sum(1 for r in sub if r.get("notify_code"))
        out.append(
            {
                "month": ym,
                "sessions": len(days),
                "n_all": len(sub),
                "n_primary": len(prim),
                "hit_all": hit_pct(sub),
                "hit_primary": hit_pct(prim),
                "volume_n": len(vol),
                "volume_hit": hit_pct(vol),
                "p2f_day_n": len(dayb),
                "p2f_day_hit": hit_pct(dayb),
                "p2f_cap2_n": len(cap2),
                "p2f_cap2_hit": hit_pct(cap2),
                "notify_n": notify_n,
                "blocked": 0,
                "calls": [call_record(r) for r in sorted(sub, key=lambda x: (str(x.get("day")), str(x.get("hm") or "")))],
            }
        )
    return out


def main() -> None:
    t0 = time.time()
    print(f"LIVE logic 1y multi-tag {START} → {END}", flush=True)

    print("  volume stack (same as live sessions)…", flush=True)
    vol = build_volume(START, END)
    sess = vol["sess"]

    print("  P2F day + Cap2 desks…", flush=True)
    dual = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gaps = gap_map()
    active = vol["active"]
    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ = _champ_floor([dict(r, track="champion") for r in dual["dual15"]["champion"]])
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
        k: [enrich_p2f_row(r, k) for r in _clip(v, START, END)]
        for k, v in p2f_day_raw.items()
    }
    p2f_cap2 = {
        k: [enrich_p2f_row(r, k) for r in _clip(v, START, END)]
        for k, v in p2f_cap2_raw.items()
    }

    print("  combine (never block)…", flush=True)
    combined = combine_live_rows(
        volume_rows=vol["volume_all"],
        p2f_day=p2f_day,
        p2f_cap2=p2f_cap2,
    )
    months = month_tables(combined["all_rows"], sess)

    # Component scores
    components = {
        "volume_stack": score(vol["stack"]),
        "agree_extras": score(vol["extras"]),
        "volume_plus_agree": score(vol["volume_all"]),
    }
    for desk in LIVE_DAY_DESKS:
        components[f"day|{desk}"] = score(p2f_day.get(desk) or [])
    for desk in LIVE_CAP2_DESKS:
        components[f"cap2|{desk}"] = score(p2f_cap2.get(desk) or [])

    payload = {
        "window": {"start": START, "end": END, "sessions": len(sess)},
        "policy": "notify_override_never_block",
        "blocked": 0,
        "combined": {
            "n_all_rows": combined["n_all"],
            "n_primary": combined["n_primary"],
            "overlap_days": combined["overlap_days"],
            "hit_all": hit_pct(combined["all_rows"]),
            "hit_primary": hit_pct(combined["primary_rows"]),
            "score_all": score(combined["all_rows"]),
            "score_primary": score(combined["primary_rows"]),
        },
        "components": components,
        "months": months,
        "elapsed_s": round(time.time() - t0, 1),
    }

    # Markdown
    lines = [
        "# LIVE logic 1y — multi-tag session report",
        "",
        f"**Window:** `{START}` → `{END}` · **{len(sess)}** sessions",
        "**Books (same as live):** volume `STACK_PLUS_CROWN_HTF_CAP2` + `AGREE_15M_ANY5` "
        "+ promoted P2F **day** + **Cap2**",
        "**Overlap policy:** never block · notify `ALREADY_OPEN_OTHER_DESK` · primary override only",
        f"**Blocked calls:** **{payload['blocked']}**",
        "",
        "## Headline",
        "",
        f"| Slice | N | Hit | Wins | Losses | Points |",
        f"|---|---:|---:|---:|---:|---:|",
    ]
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
    ca = payload["combined"]
    lines.extend(
        [
            f"| **Combined all rows** | **{ca['n_all_rows']}** | **{ca['hit_all']}%** | "
            f"{ca['score_all']['wins']} | {ca['score_all']['losses']} | {ca['score_all'].get('points')} |",
            f"| **Combined primary only** | **{ca['n_primary']}** | **{ca['hit_primary']}%** | "
            f"{ca['score_primary']['wins']} | {ca['score_primary']['losses']} | {ca['score_primary'].get('points')} |",
            "",
            f"Overlap days (multi-desk): **{ca['overlap_days']}** · notify rows kept (not dropped).",
            "",
            "## Month summary",
            "",
            "| Month | Sess | All N | All hit | Primary N | Primary hit | Vol N | Day N | Cap2 N | Notify | Blocked |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for m in months:
        lines.append(
            f"| {m['month']} | {m['sessions']} | {m['n_all']} | {m['hit_all']}% | "
            f"{m['n_primary']} | {m['hit_primary']}% | {m['volume_n']} | {m['p2f_day_n']} | "
            f"{m['p2f_cap2_n']} | {m['notify_n']} | {m['blocked']} |"
        )

    lines.extend(["", "## Per-month calls (multi-tags)", ""])
    for m in months:
        lines.append(f"### {m['month']} — {m['n_all']} rows (primary {m['n_primary']})")
        lines.append("")
        lines.append(
            "| Day | HM | Side | Book | Desk / accurate_tag | Accuracy tag | Primary | Notify | Win | Tags |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for c in m["calls"]:
            tags = ", ".join(str(t) for t in (c.get("tags") or [])[:8])
            if len(c.get("tags") or []) > 8:
                tags += ", …"
            lines.append(
                f"| {c['day']} | {c.get('hm') or ''} | {c.get('decision') or ''} | "
                f"{c.get('book') or ''} | `{c.get('accurate_tag') or c.get('source_desk') or ''}` | "
                f"`{c.get('accuracy_tag') or ''}` | "
                f"{'Y' if c.get('is_primary') else ''} | "
                f"{c.get('notify_code') or ''} | "
                f"{'W' if c.get('win') else 'L'} | {tags} |"
            )
        lines.append("")

    lines.extend(
        [
            f"Elapsed {payload['elapsed_s']}s",
            "",
            "JSON (full fields): `LIVE_LOGIC_1Y_MULTITAG.json`",
        ]
    )

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "LIVE_LOGIC_1Y_MULTITAG.md"
    js = OUT / "LIVE_LOGIC_1Y_MULTITAG.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # JSON without huge duplication — keep months.calls
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("\n".join(lines[:40]), flush=True)
    print(f"… wrote {md}", flush=True)
    print(f"… wrote {js}", flush=True)
    print(
        f"DONE blocked={payload['blocked']} all={ca['n_all_rows']} primary={ca['n_primary']} "
        f"overlap_days={ca['overlap_days']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
