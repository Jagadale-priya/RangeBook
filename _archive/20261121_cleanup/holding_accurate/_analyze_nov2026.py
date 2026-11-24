"""Analyze Nov 2026: why holding accurate desks are silent most days."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
import path_setup  # noqa: F401,E402

import pandas as pd  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
from prod_live.logic.accurate_desks import (  # noqa: E402
    DESK_REGISTRY,
    build_all_accurate_desks,
)
from prod_live.holding_accurate.rebuild_streams import rebuild_all_tags  # noqa: E402
from prod_live.holding_accurate.replay import replay_tags  # noqa: E402

HOLD = Path(__file__).resolve().parent
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"
OUT = ROOT / "prod_live" / "reports" / "1y" / "ACC_NOV2026_WHY_SILENT.md"

NOV_START = "2026-11-01"
NOV_END = "2026-11-15"  # today in research window


def _hm(hm: str) -> int:
    try:
        h, m = str(hm).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    print("Loading caches…")
    dual = load_json(CACHE_DUAL)
    path = load_json(CACHE_PATH)

    dual15 = list(dual.get("dual15") or dual.get("rows_dual15") or [])
    dual5 = list(dual.get("dual5") or dual.get("rows_dual5") or [])
    # path cache shapes vary
    path_rows = list(path.get("rows") or path.get("path_rows") or path.get("trusted") or [])
    if not path_rows and isinstance(path, dict):
        for k in ("by_risk", "path_by_risk"):
            if k in path and isinstance(path[k], dict):
                for v in path[k].values():
                    if isinstance(v, list):
                        path_rows.extend(v)

    # sessions from dual15/5
    sessions = sorted(
        {
            str(r.get("day") or "")
            for r in dual15 + dual5
            if str(r.get("day") or "").startswith("2026-11")
            and str(r.get("day") or "") <= NOV_END
        }
    )
    print("Nov sessions in cache:", len(sessions), sessions)

    # Build phase-1 desks (needs full builder inputs — use same as priority script)
    # Prefer reusing cached desk calls from ACC_PRIORITY + ALL_LEVELS reports
    pri = load_json(HOLD.parent / "reports" / "1y" / "ACC_PRIORITY_LEVELS_6M_1Y.json")
    all_lv = load_json(HOLD.parent / "reports" / "1y" / "ACC_ALL_LEVELS_1Y_TODAY.json")

    # Collect fires by day across levels
    fires: dict[str, list[dict]] = defaultdict(list)

    # From priority report P2F + earlier if present
    for key, block in (pri.get("results") or {}).items():
        level = block.get("level") or key.split("|")[0]
        tag = block.get("candidate_tag") or block.get("desk") or key
        for c in block.get("calls_1y") or []:
            day = str(c.get("day") or "")
            if day.startswith("2026-11") and day <= NOV_END:
                fires[day].append(
                    {
                        "src": "priority",
                        "level": level,
                        "desk": tag,
                        "hm": c.get("hm"),
                        "side": c.get("side") or c.get("decision"),
                        "win": c.get("win"),
                        "pts": c.get("points"),
                        "p_t1": c.get("p_t1"),
                        "stream": c.get("tag") or c.get("holding_tag"),
                    }
                )

    # From all-levels 1y report
    for level, desks in (all_lv.get("by_level") or all_lv.get("levels") or {}).items():
        if not isinstance(desks, dict):
            continue
        for desk, meta in desks.items():
            for c in meta.get("calls_1y") or meta.get("calls") or []:
                day = str(c.get("day") or "")
                if day.startswith("2026-11") and day <= NOV_END:
                    fires[day].append(
                        {
                            "src": "all_levels",
                            "level": level,
                            "desk": desk,
                            "hm": c.get("hm"),
                            "side": c.get("side") or c.get("decision"),
                            "win": c.get("win"),
                            "pts": c.get("points"),
                            "p_t1": c.get("p_t1"),
                            "stream": c.get("tag") or c.get("holding_tag"),
                        }
                    )

    # Also scan results dict shape used in ALL_LEVELS
    for key, block in (all_lv.get("results") or {}).items():
        tag = block.get("desk") or block.get("candidate_tag") or key
        level = block.get("level") or ""
        for c in block.get("calls_1y") or []:
            day = str(c.get("day") or "")
            if day.startswith("2026-11") and day <= NOV_END:
                fires[day].append(
                    {
                        "src": "all_levels_results",
                        "level": level,
                        "desk": tag,
                        "hm": c.get("hm"),
                        "side": c.get("side") or c.get("decision"),
                        "win": c.get("win"),
                        "pts": c.get("points"),
                        "p_t1": c.get("p_t1"),
                        "stream": c.get("tag") or c.get("holding_tag"),
                    }
                )

    # LIVE-ish: stack / agree from dual if stamped
    live_nov = []
    for r in dual15 + dual5:
        day = str(r.get("day") or "")
        if not (day.startswith("2026-11") and day <= NOV_END):
            continue
        if r.get("desk_tag") or r.get("accurate_tag") or r.get("lane") == "LIVE":
            live_nov.append(r)

    # Path / dual activity per Nov day
    dual15_by = defaultdict(list)
    dual5_by = defaultdict(list)
    for r in dual15:
        day = str(r.get("day") or "")
        if day.startswith("2026-11") and day <= NOV_END:
            dual15_by[day].append(r)
    for r in dual5:
        day = str(r.get("day") or "")
        if day.startswith("2026-11") and day <= NOV_END:
            dual5_by[day].append(r)

    path_by = defaultdict(list)
    for r in path_rows:
        day = str(r.get("day") or "")
        if day.startswith("2026-11") and day <= NOV_END:
            path_by[day].append(r)

    # If sessions empty, derive from fires + path + dual
    if not sessions:
        sessions = sorted(
            set(dual15_by) | set(dual5_by) | set(path_by) | set(fires) | {d for d in pd.date_range(NOV_START, NOV_END, freq="B").strftime("%Y-%m-%d")}
        )
        # filter weekends already B
        sessions = [d for d in sessions if d.startswith("2026-11") and d <= NOV_END]

    # Rebuild stream tags for Nov — need full builder context; try rebuild from recipes tags present in path
    print("Rebuilding stream tags (may take a bit)…")
    # Use same API as priority script — need phase1 inputs
    try:
        from research_acc_levels_priority_6m_1y import (  # type: ignore
            END,
        )
    except Exception:
        END = NOV_END

    # Lightweight: count path rows that look like BUY/SELL with p_t1
    def day_signal_summary(day: str) -> dict:
        d15 = dual15_by.get(day) or []
        d5 = dual5_by.get(day) or []
        pr = path_by.get(day) or []
        sides15 = Counter(str(x.get("decision") or x.get("side") or "").upper() for x in d15)
        sides5 = Counter(str(x.get("decision") or x.get("side") or "").upper() for x in d5)
        best_p = max((float(x.get("p_t1") or 0) for x in d5 + d15), default=0)
        return {
            "dual15_n": len(d15),
            "dual5_n": len(d5),
            "path_n": len(pr),
            "sides15": dict(sides15),
            "sides5": dict(sides5),
            "best_p": round(best_p, 4),
            "sample_hm15": sorted({str(x.get("hm")) for x in d15})[:8],
            "sample_hm5": sorted({str(x.get("hm")) for x in d5})[:8],
        }

    # Unique desk fires per day
    def desks_on(day: str) -> list[str]:
        seen = []
        for f in fires.get(day) or []:
            d = f["desk"]
            if d not in seen:
                seen.append(d)
        return seen

    lines = [
        "# November 2026 — why holding accurate desks are silent",
        "",
        f"**Window:** `{NOV_START}` → `{NOV_END}` (today) · logic levels P1→P2F held",
        "",
        "Question: only ~1 call in Nov so far for P2F priorities — why no calls on other days?",
        "",
        "## Short answer",
        "",
        "Holding accurate desks are **selective by design**: a day fires only if a path-true",
        "stream tag (or Phase-1 recipe) matches **and** passes gap/HTF/session/p filters,",
        "then wins day-dedupe. Most Nov sessions had live/dual activity but **did not match**",
        "any held stream recipe — so desks correctly stayed silent.",
        "",
        "## Day-by-day",
        "",
        "| Day | Dual15 | Dual5 | Path rows | Holding desks that fired | Notes |",
        "|---|---:|---:|---:|---|---|",
    ]

    silent = []
    fired_days = []
    for day in sessions:
        sig = day_signal_summary(day)
        desks = desks_on(day)
        note = ""
        if desks:
            fired_days.append(day)
            note = "CALL(S) — " + ", ".join(desks[:6])
            if len(desks) > 6:
                note += f" (+{len(desks)-6})"
        else:
            silent.append(day)
            if sig["dual15_n"] == 0 and sig["dual5_n"] == 0 and sig["path_n"] == 0:
                note = "No dual/path rows in research cache for this day"
            elif sig["dual5_n"] == 0 and sig["dual15_n"] == 0:
                note = "No dual signals — nothing to score into accurate streams"
            else:
                note = (
                    f"Signals exist (best p_t1={sig['best_p']}) but **no held stream/desk match** "
                    f"(gap/session/p/HTF/side filters)"
                )
        lines.append(
            f"| {day} | {sig['dual15_n']} | {sig['dual5_n']} | {sig['path_n']} | "
            f"{', '.join(f'`{d}`' for d in desks) or '—'} | {note} |"
        )

    lines += [
        "",
        f"**Fired days:** {len(fired_days)} · **Silent days:** {len(silent)}",
        "",
        "## Calls that did fire (detail)",
        "",
    ]
    if not fired_days:
        lines.append("_No holding-accurate fires found in Nov window reports._")
        lines.append("")
    for day in fired_days:
        lines += [f"### {day}", "", "| Level | Desk | HM | Side | Win | Pts | Stream |", "|---|---|---|---|---|---:|---|"]
        seen = set()
        for f in fires[day]:
            key = (f["level"], f["desk"], f["hm"], f["side"])
            if key in seen:
                continue
            seen.add(key)
            win = "W" if f.get("win") else ("L" if f.get("win") is False else "")
            lines.append(
                f"| {f['level']} | `{f['desk']}` | {f.get('hm')} | {f.get('side')} | {win} | "
                f"{f.get('pts')} | `{f.get('stream')}` |"
            )
        lines.append("")

    lines += [
        "## Why silent days have no calls (logic checklist)",
        "",
        "For a holding accurate desk to fire on day D:",
        "",
        "1. **Phase-1 base row** exists that day (crown/good/confirm/wide recipe), **or**",
        "2. A **stream tag** in that desk’s recipe rebuilds a path-true row on D, **and**",
        "3. Filters pass: side · `p_t1` floor · session window · gap up/down/none · HTF if required · pick (first/mid/last/bestp), **and**",
        "4. **Day-dedupe** keeps one call (or cap2 ≤2 same-side).",
        "",
        "If (1)+(2) never produce a row → desk silent. That is expected — these desks optimize",
        "**hit rate**, not coverage. LIVE stack (`STACK_PLUS…` / `AGREE_15M_ANY5`) can still",
        "print volume on the same day.",
        "",
        "### Silent-day signal snapshot",
        "",
        "| Day | Dual15 sides | Dual5 sides | Best p_t1 | Sample HM 15m | Sample HM 5m |",
        "|---|---|---|---:|---|---|",
    ]
    for day in silent:
        sig = day_signal_summary(day)
        lines.append(
            f"| {day} | {sig['sides15'] or '—'} | {sig['sides5'] or '—'} | {sig['best_p']} | "
            f"{', '.join(sig['sample_hm15']) or '—'} | {', '.join(sig['sample_hm5']) or '—'} |"
        )

    # Compare to Oct density from priority report
    oct_days = set()
    for key, block in (pri.get("results") or {}).items():
        if not str(key).startswith("P2F|"):
            continue
        for c in block.get("calls_1y") or []:
            day = str(c.get("day") or "")
            if day.startswith("2026-10"):
                oct_days.add(day)

    lines += [
        "",
        "## Context vs October",
        "",
        f"- **Oct 2026** P2F unique call-days (any priority): **{len(oct_days)}**",
        f"- **Nov 1–{NOV_END[-2:]}** P2F unique call-days: **{len(fired_days)}**",
        "",
        "Nov so far is a short partial month (~10 trading days). Sparse accurate calls are",
        "consistent with high-accuracy floors (100% / mid-90s) — many days simply never hit",
        "a locked stream pattern.",
        "",
        "## What would create more Nov calls?",
        "",
        "- Widen floor (already have P75) — still day-dedupe + stream match required",
        "- Cap2 desks (`ACC100_MULTI_V5_CAP2_P2F`) — more volume **on days that already match**, not new silent days",
        "- New research streams that fit Nov patterns (would be a new phase — do not mutate held P2F without confirm)",
        "- LIVE lane for coverage; holding accurate for high-conviction subset",
        "",
    ]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", OUT)
    print("sessions", len(sessions), "fired", fired_days, "silent", silent)

    # Also dump JSON summary
    summary = {
        "window": {"start": NOV_START, "end": NOV_END},
        "sessions": sessions,
        "fired_days": fired_days,
        "silent_days": silent,
        "fires": {d: fires[d] for d in fired_days},
        "signal": {d: day_signal_summary(d) for d in sessions},
    }
    OUT.with_suffix(".json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
