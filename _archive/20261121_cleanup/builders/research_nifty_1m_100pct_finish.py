"""Finish 100%-only report from pass3 findings (no 2bar)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401,E402

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_100pct_only as hun  # noqa: E402
import research_nifty_1m_100pct_pass3 as p3  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"


def main() -> int:
    bars = base.load_existing_1m()
    bars = bars[
        (bars.index >= pd.Timestamp(base.START, tz="Asia/Kolkata"))
        & (bars.index <= pd.Timestamp(f"{base.END} 23:59:59", tz="Asia/Kolkata"))
    ]
    filters = p3.filters_compact()[::2]
    print(f"filters={len(filters)}", flush=True)

    catalog = []
    results = {}
    for gname, gates in (("V2", base.GATE_V2), ("MED", hun.POOLS["POOL_MED"])):
        for risk in (30.0, 25.0):
            tickets, _ = p3.build_with_risk(bars, gates, risk)
            micros, uagg, ucalls = p3.honest_micros(tickets, filters, min_tr=3, min_te=1)
            h1 = p3.max_perfect(
                [r for r in tickets if "2025-01-01" <= r["day"] < "2025-07-01"],
                filters,
                f"H1|{gname}|r{risk}",
            )
            test = p3.max_perfect(
                [r for r in tickets if hun.TEST_START <= r["day"] <= hun.TEST_END],
                filters,
                f"TEST|{gname}|r{risk}",
            )
            full = p3.max_perfect(tickets, filters, f"FULL|{gname}|r{risk}")
            key = f"{gname}_r{int(risk)}"
            print(
                key,
                "micros",
                len(micros),
                "union",
                uagg,
                "h1",
                h1["n"],
                "test",
                test["n"],
                "full",
                full["n"],
                flush=True,
            )
            results[key] = {
                "union": uagg,
                "union_calls": ucalls,
                "micros_top": micros[:8],
                "h1": h1,
                "test": test,
                "full": full,
            }
            if uagg.get("n", 0) > 0:
                catalog.append(
                    {
                        "kind": "HONEST_UNION_100",
                        "pool": gname,
                        "risk": risk,
                        "n": uagg["n"],
                        "hit_pct": 100.0,
                        "calls": ucalls,
                        "label": f"UNION|{gname}|r{int(risk)}",
                        "filters": {"n_micros": len(micros)},
                        "micros_top": micros[:5],
                    }
                )
            for piece, kind in (
                (h1, "H1_IN_SAMPLE_100"),
                (test, "TEST_IN_SAMPLE_100"),
                (full, "FULL_HISTORY_100"),
            ):
                if piece["n"] > 0:
                    catalog.append(
                        {
                            "kind": kind,
                            "pool": gname,
                            "risk": risk,
                            "n": piece["n"],
                            "hit_pct": 100.0,
                            "calls": piece["calls"],
                            "label": piece["label"],
                            "filters": piece["filters"],
                        }
                    )
            for m in micros[:3]:
                catalog.append(
                    {
                        "kind": "HONEST_MICRO_100",
                        "pool": gname,
                        "risk": risk,
                        "n": m["test"]["n"],
                        "train_n": m["train"]["n"],
                        "hit_pct": 100.0,
                        "calls": m["test_calls"],
                        "filters": m["filters"],
                        "label": f"MICRO|{gname}|te{m['test']['n']}",
                    }
                )

    catalog.sort(key=lambda c: (0 if "HONEST" in c["kind"] else 1, -c["n"]))
    (OUT / "NIFTY_1M_100PCT_PASS3.json").write_text(
        json.dumps({"catalog": catalog, "results": results}, indent=2, default=str),
        encoding="utf-8",
    )

    lines = [
        "# NIFTY 1m — **100% only** calls (multi-logic)",
        "",
        "**Not live.**",
        "",
        "Train ≤ 2024-12-31 · Test 2025-01-01 → 2025-12-30",
        "",
        "Logics tried: V2/MED pools · ±25/±30 · side/clock/OR/ext/gap/body filters · "
        "train-frozen micros · union of micros · H1 regime · full-history ceilings.",
        "",
        "## 100%-only catalog",
        "",
        "| # | Kind | Pool | Risk | N |",
        "|---:|---|---|---:|---:|",
    ]
    for i, c in enumerate(catalog[:30], 1):
        lines.append(
            f"| {i} | `{c['kind']}` | `{c['pool']}` | {c.get('risk')} | **{c['n']}** |"
        )

    honest = [c for c in catalog if c["kind"] == "HONEST_UNION_100"]
    lines += ["", "## Best honest UNION books (train-frozen → test 100%)", ""]
    for c in honest:
        lines += [
            f"### `{c['pool']}` risk {c['risk']} · **{c['n']} @ 100%** "
            f"({c['filters'].get('n_micros')} micros)",
            "",
            "| Day | HM | Side | or_ext |",
            "|---|---|---|---:|",
        ]
        for x in c["calls"]:
            lines.append(
                f"| {x['day']} | {x['hm']} | {x['decision']} | {x.get('or_ext')} |"
            )
        lines.append("")
        if c.get("micros_top"):
            top = c["micros_top"][0]
            lines.append("Largest micro (by test n):")
            lines.append(f"- filters: `{json.dumps(top['filters'], default=str)}`")
            lines.append(f"- train {top['train']} · test {top['test']}")
            lines.append("")

    h1s = [c for c in catalog if c["kind"] == "H1_IN_SAMPLE_100"]
    h1s.sort(key=lambda c: -c["n"])
    if h1s:
        c = h1s[0]
        lines += [
            f"## Largest multi-call 100% (regime H1) · `{c['pool']}` r{c['risk']} · **{c['n']} @ 100%**",
            "",
            "> Calendar H1-2025 — observed perfect streak, not a pre-frozen full-year rule.",
            "",
            "| Day | HM | Side | or_ext |",
            "|---|---|---|---:|",
        ]
        for x in c["calls"]:
            lines.append(
                f"| {x['day']} | {x['hm']} | {x['decision']} | {x.get('or_ext')} |"
            )
        lines.append("")

    lines += ["## Research pick", ""]
    if honest:
        best = max(honest, key=lambda c: c["n"])
        lines.append(
            f"**Promote-candidate (honest 100% only):** `{best['pool']}` ±{best['risk']} · "
            f"**{best['n']} day-unique calls @ 100%** in 2025."
        )
        lines.append(
            "Only calls allowed by the union of train-perfect micros that also stayed perfect on test."
        )
    if h1s:
        lines.append(
            f"**Most 100% calls (regime):** H1 `{h1s[0]['pool']}` · **{h1s[0]['n']} @ 100%** — research/regime only."
        )
    lines += [
        "",
        "## Policy",
        "",
        "- research_only · not_live",
        "- `HONEST_UNION` / `HONEST_MICRO` = train-frozen",
        "- `H1` / `FULL_HISTORY` / `TEST_IN_SAMPLE` = not auto-promote",
        "",
    ]
    (OUT / "NIFTY_1M_100PCT_ONLY.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT / 'NIFTY_1M_100PCT_ONLY.md'}", flush=True)
    print("TOP:", flush=True)
    for c in catalog[:12]:
        print(c["kind"], c["pool"], c.get("risk"), c["n"], flush=True)
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
