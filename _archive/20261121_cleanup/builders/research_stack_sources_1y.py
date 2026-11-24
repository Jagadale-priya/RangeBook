"""What are PROVEN / GOOD / CHAMP / CROWN — test each alone on last 1y.

Same pools + window as live golden stack (no merge priority across tracks).

  python -u prod_live/tests/builders/research_stack_sources_1y.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _agg, _champ_floor  # noqa: E402
from prod_live.logic.stack import union_day_cap2  # noqa: E402
import live_final_1y_months_accurate as hold  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
START, END = hold.START, hold.END  # golden live 1y


def month_rows(rows: List[dict]) -> List[Dict[str, Any]]:
    from collections import defaultdict

    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")[:7]].append(r)
    out = []
    for m in sorted(by):
        sc = _agg(by[m])
        out.append({"month": m, "n": sc.get("n"), "hit_pct": sc.get("hit_pct"), "wins": sc.get("wins")})
    return out


def main() -> int:
    print(f"Stack sources alone · 1y {START} → {END}", flush=True)
    live = hold._build_live_stack(START, END)
    proven = live["proven"]
    good = live["good"]
    champ = live["champ"]
    crown = live["crown_htf"]
    stack = live["stack"]

    # Each alone with same cap2 rule (only that track)
    alone = {
        "PROVEN_100": union_day_cap2({"proven_100": proven}),
        "GOOD_PROD2": union_day_cap2({"good_prod2": good}),
        "CHAMPION": union_day_cap2({"champion": champ}),
        "CROWN_DUAL_HTF": union_day_cap2({"crown_5m": crown}),
    }
    raw = {
        "PROVEN_100": proven,
        "GOOD_PROD2": good,
        "CHAMPION": champ,
        "CROWN_DUAL_HTF": crown,
    }

    defs = {
        "PROVEN_100": (
            "Dual-15m **proven** tickets — historically perfect / locked "
            "OR-break + model lane. Highest stack priority (0)."
        ),
        "GOOD_PROD2": (
            "Prod2 **15m good** tickets from live session scoring. "
            "Volume backbone. Priority 1."
        ),
        "CHAMPION": (
            "Dual-15m **champion** tickets after champ floor filter. "
            "Priority 2."
        ),
        "CROWN_DUAL_HTF": (
            "5m **crown** tickets, only on `HTF_ACTIVE_DAY`. "
            "Lowest priority (3); fill when higher tracks quiet."
        ),
    }

    lines = [
        "# Stack sources alone — last 1y",
        "",
        f"**Window (live golden):** `{START}` → `{END}`",
        "**Book rule when alone:** same day-cap2 · same-side (as stack, but one track only)",
        "",
        "## What each is",
        "",
    ]
    for name, desc in defs.items():
        lines.append(f"- **`{name}`** — {desc}")

    lines.extend(
        [
            "",
            "## Alone (cap2) vs raw pool",
            "",
            "| Source | Raw N@hit | Alone cap2 N@hit | In full stack* |",
            "|---|---|---|---|",
        ]
    )

    # track share inside full stack
    from collections import Counter

    tr = Counter(r.get("track") for r in stack)
    results: Dict[str, Any] = {"window": {"start": START, "end": END}, "sources": {}}

    track_key = {
        "PROVEN_100": "proven_100",
        "GOOD_PROD2": "good_prod2",
        "CHAMPION": "champion",
        "CROWN_DUAL_HTF": "crown_5m",
    }

    for name in defs:
        sc_raw = _agg(hold._clean(raw[name]))
        alone_rows = hold._clean(alone[name])
        sc_al = _agg(alone_rows)
        in_stack = [r for r in stack if r.get("track") == track_key[name]]
        sc_in = _agg(in_stack)
        results["sources"][name] = {
            "definition": defs[name],
            "raw": sc_raw,
            "alone_cap2": sc_al,
            "in_full_stack": sc_in,
            "monthly_alone_cap2": month_rows(alone_rows),
        }
        lines.append(
            f"| `{name}` | {sc_raw.get('n')}@{sc_raw.get('hit_pct')} | "
            f"**{sc_al.get('n')}@{sc_al.get('hit_pct')}** | "
            f"{sc_in.get('n')}@{sc_in.get('hit_pct')} |"
        )
        print(
            f"  {name}: raw {sc_raw.get('n')}@{sc_raw.get('hit_pct')}% · "
            f"alone_cap2 {sc_al.get('n')}@{sc_al.get('hit_pct')}% · "
            f"in_stack {sc_in.get('n')}@{sc_in.get('hit_pct')}%",
            flush=True,
        )

    sc_stack = _agg(stack)
    results["full_stack"] = sc_stack
    results["stack_by_track"] = {
        k: {"n": v, "share_pct": round(100.0 * v / max(sc_stack.get("n") or 1, 1), 1)}
        for k, v in sorted(tr.items())
    }
    lines.extend(
        [
            "",
            f"\\* *In full stack* = calls that survived merge priority inside "
            f"`STACK_PLUS_CROWN_HTF_CAP2` ({sc_stack.get('n')}@{sc_stack.get('hit_pct')}%).",
            "",
            "## Full stack track mix",
            "",
            "| Track | N in stack | Share |",
            "|---|---:|---:|",
        ]
    )
    for k, v in sorted(tr.items(), key=lambda kv: -kv[1]):
        share = round(100.0 * v / max(len(stack), 1), 1)
        lines.append(f"| `{k}` | {v} | {share}% |")

    lines.extend(["", f"**Full stack:** N={sc_stack.get('n')} · hit **{sc_stack.get('hit_pct')}%**", ""])

    # Monthly for each alone
    for name in defs:
        lines.extend(
            [
                f"## Monthly alone cap2 — `{name}`",
                "",
                "| Month | N | Hit% | W |",
                "|---|---:|---:|---:|",
            ]
        )
        for m in results["sources"][name]["monthly_alone_cap2"]:
            lines.append(
                f"| {m['month']} | {m['n']} | {m['hit_pct']} | {m.get('wins', '')} |"
            )
        lines.append("")

    lines.extend(
        [
            "## How they combine (live)",
            "",
            "1. Score all four pools on the session.",
            "2. Merge with priority **proven > good > champ > crown**.",
            "3. Cap **2 calls/day**, **same side** only.",
            "4. Crown only if day is HTF-active.",
            "",
            "That merge = `STACK_PLUS_CROWN_HTF_CAP2` (volume live).",
            "",
        ]
    )

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "STACK_SOURCES_ALONE_1Y.md"
    js = OUT / "STACK_SOURCES_ALONE_1Y.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    print(
        f"Full stack {sc_stack.get('n')}@{sc_stack.get('hit_pct')}%",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
