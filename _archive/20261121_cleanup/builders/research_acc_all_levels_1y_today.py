"""Complete 1y→today report: ALL held logic levels side-by-side.

Phase-1 locked + P2c/P2d/P2e/P2f held recipes + LIVE AGREE channel.

  python -u prod_live/tests/builders/research_acc_all_levels_1y_today.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _side  # noqa: E402
from research_100pct_deeper_more_calls import gap_map, is_perfect  # noqa: E402
from prod_live.logic.accurate_desks import (  # noqa: E402
    DESK_REGISTRY,
    build_all_accurate_desks,
)
from prod_live.logic.agree_accurate import build_agree_rows  # noqa: E402
from prod_live.holding_accurate.rebuild_streams import rebuild_all_tags  # noqa: E402
from prod_live.holding_accurate.replay import replay_tags, stamp  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
HOLD = ROOT / "prod_live" / "holding_accurate"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL_10Y = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH_10Y = LEDGER / "_cache_path_trusted_10y.json"

END = date.today().strftime("%Y-%m-%d")
START_1Y = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")

# Focus expand desks present across levels
EXPAND = [
    "ACC100_MULTI_V5",
    "ACC_WIDE_P92",
    "ACC_WIDE_P90",
    "ACC_WIDE_P85",
    "ACC_WIDE_P85B",
    "ACC_WIDE_P80",
    "ACC_WIDE_P75",
]
CAP2_KEYS = [
    "ACC100_MULTI_V5_CAP2",
    "ACC_WIDE_P92_CAP2",
    "ACC_WIDE_P90_CAP2",
    "ACC_WIDE_P85_CAP2",
    "ACC_WIDE_P85B_CAP2",
    "ACC_WIDE_P80_CAP2",
]

LEVEL_FILES = [
    ("P2C", HOLD / "recipes.json", "HELD"),
    ("P2D", HOLD / "phase2d" / "recipes_research.json", "HELD"),
    ("P2E", HOLD / "phase2e" / "recipes_research.json", "HELD"),
    ("P2F", HOLD / "phase2f" / "recipes_research.json", "HELD"),
]

ACCURACY_BY_BASE = {
    "ACC100_MULTI_V5": "ACC_RANGE_98_100",
    "ACC_WIDE_P92": "ACC_RANGE_91_100",
    "ACC_WIDE_P90": "ACC_RANGE_89_96",
    "ACC_WIDE_P85": "ACC_RANGE_84_90",
    "ACC_WIDE_P85B": "ACC_RANGE_81_89",
    "ACC_WIDE_P80": "ACC_RANGE_76_85",
    "ACC_WIDE_P75": "ACC_RANGE_75_83",
}


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
            }
        )
    return out


def score(rows: List[dict]) -> Dict[str, Any]:
    rs = _clip(rows, START_1Y, END)
    days = sorted({str(r.get("day") or "") for r in rs})
    return {
        "n": len(rs),
        "hit_pct": hit_pct(rs),
        "perfect": bool(rs) and is_perfect(rs),
        "points": (_agg(rs) or {}).get("points") if rs else 0,
        "wins": sum(1 for r in rs if r.get("win")),
        "losses": sum(1 for r in rs if not r.get("win")),
        "buy": sum(1 for r in rs if _side(r) == "BUY"),
        "sell": sum(1 for r in rs if _side(r) == "SELL"),
        "call_days": len(days),
        "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "months": month_table(rs),
    }


def load_level_recipes(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("candidates") or {}


def main() -> None:
    t0 = time.time()
    print(f"ALL LEVELS 1y→today {START_1Y} → {END}", flush=True)

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
    champ_native = path_u.get("champ_native") or champ

    print("  Phase-1 desks…", flush=True)
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

    # Collect all stream tags across levels
    level_recipes: Dict[str, Dict[str, Any]] = {}
    all_tags: List[str] = []
    seen: set = set()
    for lab, path, _status in LEVEL_FILES:
        cands = load_level_recipes(path)
        level_recipes[lab] = cands
        for meta in cands.values():
            for t in meta.get("stream_tags_held") or meta.get("stream_tags_research") or []:
                if t not in seen:
                    seen.add(t)
                    all_tags.append(t)

    print(f"  rebuild {len(all_tags)} stream tags…", flush=True)
    by_tag = rebuild_all_tags(
        all_tags, path_u, gaps, active, dual15, dual5, proven, champ
    )

    results: Dict[str, Any] = {}

    # Phase-1 nested + wide
    p1_names = [
        "PROVEN15_PLUS_CONFIRM_T30",
        "ACC100_MULTI_V1",
        "ACC100_MULTI_V2",
        "ACC100_MULTI_V3",
        "ACC100_MULTI_V4",
        "ACC100_MULTI_V5",
        "ACC_WIDE_P92",
        "ACC_WIDE_P90",
        "ACC_WIDE_P85",
        "ACC_WIDE_P85B",
        "ACC_WIDE_P80",
        "ACC_WIDE_P75",
        "ACC_WIDE_P80_CAP2",
        "ACC_WIDE_P75_CAP2",
    ]
    for name in p1_names:
        rows = phase1.get(name) or []
        meta = DESK_REGISTRY.get(name) or {}
        sc = score(rows)
        results[f"P1|{name}"] = {
            "level": "P1",
            "desk": name,
            "candidate_tag": name,
            "accuracy_range": meta.get("accuracy_range"),
            "mode": "day" if "CAP2" not in name else "cap2",
            "status": "LOCKED",
            **sc,
        }
        print(f"  P1 {name}: {sc['n']}@{sc['hit_pct']}%", flush=True)

    # Expanded levels
    for lab, _path, status in LEVEL_FILES:
        cands = level_recipes.get(lab) or {}
        for key in EXPAND + CAP2_KEYS:
            meta = cands.get(key)
            if not meta:
                # try without _CAP2 mapping for P2c naming
                continue
            base = meta.get("base_desk") or key.replace("_CAP2", "")
            mode = meta.get("mode") or ("cap2" if key.endswith("_CAP2") else "day")
            tags = list(meta.get("stream_tags_held") or meta.get("stream_tags_research") or [])
            if base not in phase1:
                continue
            desk = replay_tags(list(phase1[base]), tags, by_tag, mode=mode)
            cand = meta.get("candidate_tag") or f"{key}_{lab}"
            ar = ACCURACY_BY_BASE.get(base, "")
            stamped = stamp(desk, cand, level=lab, accuracy_range=ar)
            sc = score(stamped)
            results[f"{lab}|{cand}"] = {
                "level": lab,
                "desk": key,
                "base_desk": base,
                "candidate_tag": cand,
                "accuracy_range": ar,
                "mode": mode,
                "status": status,
                "streams": len(tags),
                **sc,
            }
            print(f"  {lab} {cand}: {sc['n']}@{sc['hit_pct']}%", flush=True)

    # LIVE AGREE channel (GOOD_PROD2 15m ∩ any 5m)
    print("  LIVE AGREE_15M_ANY5…", flush=True)
    _sess, good_all, _ = fs._prod2(4000)
    good15 = [
        dict(r, track="good_prod2")
        for r in good_all
        if START_1Y <= str(r.get("day") or "") <= END
    ]
    proven5 = [dict(r, track="proven_100") for r in (dual["dual5"].get("proven_100") or [])]
    champ5 = [dict(r, track="champion") for r in (dual["dual5"].get("champion") or [])]
    # crown HTF from path cache (native / 20 risk common)
    crown_raw = (
        path_u.get("crown_by_risk", {}).get("20.0")
        or path_u.get("crown_by_risk", {}).get("20")
        or []
    )
    crown5 = [dict(r, track="crown_5m") for r in crown_raw if str(r.get("day") or "") in active]
    agree = build_agree_rows(good15, proven5, champ5, crown5)
    agree_rows = stamp(agree or [], "AGREE_15M_ANY5", level="LIVE", accuracy_range="LIVE_AGREE")
    sc_agree = score(agree_rows)
    results["LIVE|AGREE_15M_ANY5"] = {
        "level": "LIVE",
        "desk": "AGREE_15M_ANY5",
        "candidate_tag": "AGREE_15M_ANY5",
        "accuracy_range": "LIVE_AGREE",
        "mode": "agree",
        "status": "FINALIZED",
        **sc_agree,
    }
    print(f"  LIVE AGREE: {sc_agree['n']}@{sc_agree['hit_pct']}%", flush=True)

    payload = {
        "status": "HOLDING",
        "not_live_holding": True,
        "window": {"start": START_1Y, "end": END, "label": "1y_to_today"},
        "levels_held": ["P1", "P2C", "P2D", "P2E", "P2F"],
        "results": results,
        "elapsed_s": round(time.time() - t0, 1),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (HOLD / "reports").mkdir(parents=True, exist_ok=True)
    for dest in (OUT, LEDGER, HOLD / "reports"):
        (dest / "ACC_ALL_LEVELS_1Y_TODAY.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )

    # --- Markdown report ---
    lines = [
        f"# All logic levels — 1y to today ({END})",
        "",
        f"**Window:** `{START_1Y}` → `{END}` (365 days through today)",
        "",
        "Every level **held** (P1 locked · P2c–P2f kept). LIVE AGREE shown for channel compare.",
        "",
        f"Elapsed {payload['elapsed_s']}s",
        "",
        "## Headline — 100% family (V5 ladder)",
        "",
        "| Level | Tag | N | Hit | W | L | Pts | Call days |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    def row_md(key: str) -> Optional[str]:
        r = results.get(key)
        if not r:
            return None
        return (
            f"| {r['level']} | `{r['candidate_tag']}` | {r['n']} | {r['hit_pct']} | "
            f"{r['wins']} | {r['losses']} | {r['points']} | {r['call_days']} |"
        )

    for key in (
        "P1|ACC100_MULTI_V5",
        "P2C|ACC100_MULTI_V8",
        "P2D|ACC100_MULTI_V9",
        "P2E|ACC100_MULTI_V10",
        "P2F|ACC100_MULTI_V11",
        "LIVE|AGREE_15M_ANY5",
    ):
        # P2C candidate may be ACC100_MULTI_V8 from recipes
        if key.startswith("P2C|") and key not in results:
            # find P2C V5-family
            for k, v in results.items():
                if v.get("level") == "P2C" and v.get("desk") == "ACC100_MULTI_V5":
                    lines.append(row_md(k) or "")
                    break
            continue
        if key.startswith("P2D|") and key not in results:
            for k, v in results.items():
                if v.get("level") == "P2D" and v.get("desk") == "ACC100_MULTI_V5":
                    lines.append(row_md(k) or "")
                    break
            continue
        if key.startswith("P2E|") and key not in results:
            for k, v in results.items():
                if v.get("level") == "P2E" and v.get("desk") == "ACC100_MULTI_V5":
                    lines.append(row_md(k) or "")
                    break
            continue
        if key.startswith("P2F|") and key not in results:
            for k, v in results.items():
                if v.get("level") == "P2F" and v.get("desk") == "ACC100_MULTI_V5":
                    lines.append(row_md(k) or "")
                    break
            continue
        line = row_md(key)
        if line:
            lines.append(line)

    lines += ["", "## Full comparison — day desks by level", ""]
    lines += [
        "| Base | P1 N/Hit | P2C N/Hit | P2D N/Hit | P2E N/Hit | **P2F N/Hit** |",
        "|---|---|---|---|---|---|",
    ]

    def find(level: str, desk: str) -> Optional[Dict[str, Any]]:
        for v in results.values():
            if v.get("level") == level and (v.get("desk") == desk or v.get("candidate_tag") == desk):
                return v
            if v.get("level") == level and v.get("base_desk") == desk and v.get("mode") == "day":
                return v
            if level == "P1" and v.get("desk") == desk:
                return v
        return None

    def cell(v: Optional[Dict[str, Any]]) -> str:
        if not v:
            return "—"
        return f"{v['n']} @ {v['hit_pct']}%"

    for base in EXPAND:
        p1 = find("P1", base)
        cells = [cell(p1)]
        for lab in ("P2C", "P2D", "P2E", "P2F"):
            cells.append(cell(find(lab, base)))
        lines.append(f"| `{base}` | " + " | ".join(cells) + " |")

    lines += ["", "## Cap2 comparison", ""]
    lines += [
        "| Base CAP2 | P2C | P2D | P2E | **P2F** |",
        "|---|---|---|---|---|",
    ]
    for key in CAP2_KEYS:
        cells = []
        for lab in ("P2C", "P2D", "P2E", "P2F"):
            cells.append(cell(find(lab, key)))
        lines.append(f"| `{key}` | " + " | ".join(cells) + " |")

    lines += ["", "## Phase-1 nested (locked) — 1y", ""]
    lines += [
        "| Desk | N | Hit | W | L | Pts | Acc range |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name in p1_names:
        r = results.get(f"P1|{name}")
        if not r:
            continue
        lines.append(
            f"| `{name}` | {r['n']} | {r['hit_pct']} | {r['wins']} | {r['losses']} | "
            f"{r['points']} | `{r.get('accuracy_range') or '—'}` |"
        )

    # Month tables for recommended live tags
    focus_keys = []
    for lab, desk in (("P1", "ACC100_MULTI_V5"), ("P2F", "ACC100_MULTI_V5"), ("P2F", "ACC100_MULTI_V5_CAP2")):
        v = find(lab, desk)
        if v:
            focus_keys.append((lab, v))
    # also P92 P2F and LIVE
    for lab, desk in (("P2F", "ACC_WIDE_P92"), ("LIVE", "AGREE_15M_ANY5")):
        v = find(lab, desk) if lab != "LIVE" else results.get("LIVE|AGREE_15M_ANY5")
        if lab == "LIVE":
            v = results.get("LIVE|AGREE_15M_ANY5")
        if v:
            focus_keys.append((lab, v))

    lines += ["", "## Month-by-month (key channels)", ""]
    seen_f = set()
    for lab, v in focus_keys:
        tag = v["candidate_tag"]
        if tag in seen_f:
            continue
        seen_f.add(tag)
        lines += [f"### `{tag}` ({lab}) — {v['n']} @ {v['hit_pct']}%", ""]
        if not v.get("months"):
            lines.append("_No rows._")
        else:
            lines += ["| Month | N | Hit | W | L | Pts |", "|---|---:|---:|---:|---:|---:|"]
            for m in v["months"]:
                lines.append(
                    f"| {m['month']} | {m['n']} | {m['hit_pct']} | {m['wins']} | "
                    f"{m['losses']} | {m['points']} |"
                )
        lines.append("")

    lines += [
        "## Live tagging recommendation",
        "",
        "When issuing **live calls**, keep Lane A volume as today, and stamp **holding accurate** channels in parallel:",
        "",
        "| Priority | Tag to stamp | Why | 1y hit (this report) |",
        "|---:|---|---|---|",
        "| 1 | `ACC100_MULTI_V11` (P2F) / fallback `ACC100_MULTI_V5` | Highest 100% path desk | see V5 ladder above |",
        "| 2 | `ACC100_MULTI_V5_CAP2_P2F` | Same 100% floor, more calls (cap2) | see Cap2 |",
        "| 3 | `ACC_WIDE_P92_P2F` | High-90s channel for more volume | see table |",
        "| LIVE | `AGREE_15M_ANY5` | Current live accurate stamp (keep) | LIVE row |",
        "",
        "Stamp fields: `desk_tag` · `accurate_tag` · `accuracy_range_tag` · `logic_level` · `lane=HOLDING`.",
        "",
        "Do **not** replace LIVE `AGREE_15M_ANY5` until you explicitly promote.",
        "",
        "See `holding_accurate/LIVE_CHANNELS.md`.",
        "",
        "JSON: `ACC_ALL_LEVELS_1Y_TODAY.json`",
        "",
    ]

    text = "\n".join(lines)
    for dest in (OUT, LEDGER, HOLD / "reports"):
        (dest / "ACC_ALL_LEVELS_1Y_TODAY.md").write_text(text, encoding="utf-8")
    print("Wrote", OUT / "ACC_ALL_LEVELS_1Y_TODAY.md", flush=True)


if __name__ == "__main__":
    main()
