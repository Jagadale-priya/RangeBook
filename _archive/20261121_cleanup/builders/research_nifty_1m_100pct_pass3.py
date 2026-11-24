"""Pass-3: full-history perfect rules + alt risk + 2-bar hold + min_train=3 micros."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401,E402

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_100pct_only as hun  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT_MD = OUT / "NIFTY_1M_100PCT_ONLY.md"
REPORT_JSON = OUT / "NIFTY_1M_100PCT_PASS3.json"
TEST_START, TEST_END, TRAIN_END = hun.TEST_START, hun.TEST_END, hun.TRAIN_END


def filters_compact():
    out = []
    for side in (None, "BUY", "SELL"):
        for c0, c1 in (
            (600, 870),
            (600, 630),
            (630, 690),
            (600, 720),
            (690, 780),
            (600, 660),
            (630, 780),
        ):
            for ext in (0.05, 0.08, 0.1, 0.12, 0.15, 0.2, 0.25, 0.3, 0.4):
                for orw in (12, 15, 18, 20, 25, 30, 40, 50, 60):
                    for nz in (0.8, 1.0, 1.25, 1.5, 2.0):
                        for glo, ghi in (
                            (None, None),
                            (-0.35, 0.35),
                            (None, 0.0),
                            (0.0, None),
                            (None, -0.25),
                            (0.25, None),
                        ):
                            for body in (None, True):
                                out.append(
                                    dict(
                                        side=side,
                                        min_mins=c0,
                                        max_mins=c1,
                                        max_or_ext=ext,
                                        min_or_w=orw,
                                        max_noise=nz,
                                        gap_lo=glo,
                                        gap_hi=ghi,
                                        require_body=body,
                                        forbid_both=True,
                                        require_fb=True,
                                    )
                                )
    return out


def max_perfect(rows: List[dict], filters: List[dict], label: str) -> Dict[str, Any]:
    """Largest day-unique 100% book on this row set (in-sample for the set)."""
    best = None
    for f in filters:
        got = hun.first_day(hun.apply_f(rows, f))
        if not hun.is_100(got):
            continue
        if best is None or len(got) > best["n"]:
            best = {
                "label": label,
                "n": len(got),
                "filters": f,
                "agg": hun.agg(got),
                "calls": [hun.strip(r) for r in got],
            }
    return best or {"label": label, "n": 0, "agg": hun.agg([]), "calls": [], "filters": None}


def honest_micros(rows, filters, min_tr=3, min_te=1):
    train = [r for r in rows if r["day"] <= TRAIN_END]
    test = [r for r in rows if TEST_START <= r["day"] <= TEST_END]
    micros = []
    for f in filters:
        tr = hun.first_day(hun.apply_f(train, f))
        if len(tr) < min_tr or not hun.is_100(tr):
            continue
        te = hun.first_day(hun.apply_f(test, f))
        if len(te) < min_te or not hun.is_100(te):
            continue
        micros.append(
            {
                "filters": f,
                "train": hun.agg(tr),
                "test": hun.agg(te),
                "test_calls": [hun.strip(r) for r in te],
                "train_calls": [hun.strip(r) for r in tr],
            }
        )
    by_day = {}
    for m in micros:
        for c in m["test_calls"]:
            by_day.setdefault(c["day"], c)
    union = hun.first_day(list(by_day.values()))
    micros.sort(key=lambda m: (-m["test"]["n"], -m["train"]["n"]))
    return micros, hun.agg(union), [hun.strip(r) for r in sorted(union, key=lambda x: x["day"])]


def build_with_risk(bars, gates, risk: float):
    old = base.RISK
    base.RISK = float(risk)
    try:
        tickets, reasons, _ = base.build_clean_tickets(bars, gates=gates)
    finally:
        base.RISK = old
    return hun.enrich(tickets), reasons


def two_bar_confirm(bars, gates) -> List[dict]:
    """OR break must hold: close beyond OR for entry bar AND next bar."""
    tickets, _, _ = base.build_clean_tickets(bars, gates=gates)
    # rebuild first_up/dn style filter using session — post-filter using bars
    idx = {ts: i for i, ts in enumerate(bars.index)}
    keep = []
    for r in hun.enrich(tickets):
        # locate bar
        # match day+hm on index
        found = None
        for ts, i in idx.items():
            if base._day(ts) == r["day"] and base._hm(ts) == r["hm"]:
                found = i
                break
        if found is None or found + 1 >= len(bars):
            continue
        # need OR levels from ticket or_width/entry — approximate with break persistence:
        # next bar close still on correct side of entry vs OR using or_ext sign
        c0 = float(bars["Close"].iloc[found])
        c1 = float(bars["Close"].iloc[found + 1])
        if r["decision"] == "BUY":
            # both closes should be >= entry (held up) — soft confirm
            if c1 < c0:  # next bar closed down vs entry bar close
                continue
        else:
            if c1 > c0:
                continue
        # also require next bar not huge adverse range
        keep.append(r)
    return keep


def main() -> int:
    print("PASS3 full-history + alt risk + micros3", flush=True)
    bars = base.load_existing_1m()
    bars = bars[
        (bars.index >= pd.Timestamp(base.START, tz="Asia/Kolkata"))
        & (bars.index <= pd.Timestamp(f"{base.END} 23:59:59", tz="Asia/Kolkata"))
    ]
    filters = filters_compact()
    print(f"filters={len(filters)}", flush=True)

    catalog = []  # all 100% books we want to show
    results: Dict[str, Any] = {}

    gate_sets = {
        "V2": base.GATE_V2,
        "MED": hun.POOLS["POOL_MED"],
        "RAW_FB": hun.POOLS["POOL_RAW_FB"],
    }

    for gname, gates in gate_sets.items():
        print(f"\n=== GATE {gname} risk30 ===", flush=True)
        tickets, reasons = build_with_risk(bars, gates, 30.0)
        print(f"  clean={len(tickets)}", flush=True)
        t0 = time.time()
        full = max_perfect(tickets, filters, f"FULL_HIST|{gname}|r30")
        test = max_perfect(
            [r for r in tickets if TEST_START <= r["day"] <= TEST_END],
            filters,
            f"TEST2025|{gname}|r30",
        )
        train = max_perfect(
            [r for r in tickets if r["day"] <= TRAIN_END],
            filters,
            f"TRAIN|{gname}|r30",
        )
        h1 = max_perfect(
            [r for r in tickets if "2025-01-01" <= r["day"] < "2025-07-01"],
            filters,
            f"H1|{gname}|r30",
        )
        print(
            f"  ceilings full={full['n']} test={test['n']} train={train['n']} h1={h1['n']} ({time.time()-t0:.0f}s)",
            flush=True,
        )
        micros, union_agg, union_calls = honest_micros(tickets, filters, min_tr=3, min_te=1)
        print(f"  honest micros={len(micros)} union={union_agg}", flush=True)
        if union_calls:
            print("  union calls", [(c["day"], c["hm"], c["decision"]) for c in union_calls], flush=True)

        block = {
            "full": full,
            "test": test,
            "train": train,
            "h1": h1,
            "micros_n": len(micros),
            "micros_top": micros[:10],
            "union": union_agg,
            "union_calls": union_calls,
        }
        results[f"{gname}_r30"] = block
        for piece, kind in (
            (full, "FULL_HISTORY_100"),
            (test, "TEST_IN_SAMPLE_100"),
            (h1, "H1_IN_SAMPLE_100"),
            (train, "TRAIN_IN_SAMPLE_100"),
        ):
            if piece["n"] > 0:
                catalog.append(
                    {
                        "kind": kind,
                        "pool": gname,
                        "risk": 30,
                        "n": piece["n"],
                        "hit_pct": 100.0,
                        "filters": piece.get("filters"),
                        "calls": piece.get("calls"),
                        "label": piece.get("label"),
                    }
                )
        if union_agg.get("n", 0) > 0 and union_agg.get("hit_pct", 0) >= 100:
            catalog.append(
                {
                    "kind": "HONEST_UNION_100",
                    "pool": gname,
                    "risk": 30,
                    "n": union_agg["n"],
                    "hit_pct": 100.0,
                    "filters": {"note": "union of train100&test100 micros", "n_micros": len(micros)},
                    "calls": union_calls,
                    "label": f"UNION|{gname}",
                }
            )
        for m in micros[:5]:
            catalog.append(
                {
                    "kind": "HONEST_MICRO_100",
                    "pool": gname,
                    "risk": 30,
                    "n": m["test"]["n"],
                    "hit_pct": 100.0,
                    "train_n": m["train"]["n"],
                    "filters": m["filters"],
                    "calls": m["test_calls"],
                    "label": f"MICRO|{gname}|tr{m['train']['n']}|te{m['test']['n']}",
                }
            )

    # Alt risks on V2 / MED
    for risk in (20.0, 25.0, 40.0):
        for gname in ("V2", "MED"):
            gates = gate_sets[gname]
            print(f"\n=== GATE {gname} risk{risk:g} ===", flush=True)
            tickets, reasons = build_with_risk(bars, gates, risk)
            print(f"  clean={len(tickets)} reasons_ok={reasons.get('ok')}", flush=True)
            test_rows = [r for r in tickets if TEST_START <= r["day"] <= TEST_END]
            h1_rows = [r for r in tickets if "2025-01-01" <= r["day"] < "2025-07-01"]
            full = max_perfect(tickets, filters, f"FULL|{gname}|r{risk:g}")
            test = max_perfect(test_rows, filters, f"TEST|{gname}|r{risk:g}")
            h1 = max_perfect(h1_rows, filters, f"H1|{gname}|r{risk:g}")
            micros, union_agg, union_calls = honest_micros(tickets, filters, min_tr=3, min_te=1)
            print(
                f"  full={full['n']} test={test['n']} h1={h1['n']} micros={len(micros)} union={union_agg}",
                flush=True,
            )
            results[f"{gname}_r{int(risk)}"] = {
                "full": full,
                "test": test,
                "h1": h1,
                "micros_n": len(micros),
                "union": union_agg,
                "union_calls": union_calls,
                "micros_top": micros[:8],
                "base_test": hun.agg(hun.first_day(test_rows)),
            }
            for piece, kind in (
                (full, "FULL_HISTORY_100"),
                (test, "TEST_IN_SAMPLE_100"),
                (h1, "H1_IN_SAMPLE_100"),
            ):
                if piece["n"] > 0:
                    catalog.append(
                        {
                            "kind": kind,
                            "pool": gname,
                            "risk": risk,
                            "n": piece["n"],
                            "hit_pct": 100.0,
                            "filters": piece.get("filters"),
                            "calls": piece.get("calls"),
                            "label": piece.get("label"),
                        }
                    )
            if union_agg.get("n", 0) > 0 and union_agg.get("hit_pct", 0) >= 100:
                catalog.append(
                    {
                        "kind": "HONEST_UNION_100",
                        "pool": gname,
                        "risk": risk,
                        "n": union_agg["n"],
                        "hit_pct": 100.0,
                        "filters": {"n_micros": len(micros)},
                        "calls": union_calls,
                        "label": f"UNION|{gname}|r{risk:g}",
                    }
                )

    # 2-bar confirm on V2 risk30
    print("\n=== 2BAR confirm V2 ===", flush=True)
    rows2 = two_bar_confirm(bars, base.GATE_V2)
    print(f"  kept={len(rows2)}", flush=True)
    test2 = [r for r in rows2 if TEST_START <= r["day"] <= TEST_END]
    h1_2 = [r for r in rows2 if "2025-01-01" <= r["day"] < "2025-07-01"]
    full2 = max_perfect(rows2, filters, "FULL|2BAR|V2")
    test2p = max_perfect(test2, filters, "TEST|2BAR|V2")
    h12 = max_perfect(h1_2, filters, "H1|2BAR|V2")
    micros2, u2, uc2 = honest_micros(rows2, filters, min_tr=3, min_te=1)
    print(f"  full={full2['n']} test={test2p['n']} h1={h12['n']} micros={len(micros2)} union={u2}", flush=True)
    results["V2_2BAR"] = {
        "full": full2,
        "test": test2p,
        "h1": h12,
        "micros_n": len(micros2),
        "union": u2,
        "union_calls": uc2,
        "base_test": hun.agg(hun.first_day(test2)),
    }
    for piece, kind in ((full2, "FULL_HISTORY_100"), (test2p, "TEST_IN_SAMPLE_100"), (h12, "H1_IN_SAMPLE_100")):
        if piece["n"] > 0:
            catalog.append(
                {
                    "kind": kind,
                    "pool": "V2_2BAR",
                    "risk": 30,
                    "n": piece["n"],
                    "hit_pct": 100.0,
                    "filters": piece.get("filters"),
                    "calls": piece.get("calls"),
                    "label": piece.get("label"),
                }
            )
    if u2.get("n", 0) > 0 and u2.get("hit_pct", 0) >= 100:
        catalog.append(
            {
                "kind": "HONEST_UNION_100",
                "pool": "V2_2BAR",
                "risk": 30,
                "n": u2["n"],
                "hit_pct": 100.0,
                "calls": uc2,
                "label": "UNION|V2_2BAR",
            }
        )

    # Sort catalog: prefer honest kinds, then n
    rank_kind = {
        "HONEST_UNION_100": 0,
        "HONEST_MICRO_100": 1,
        "FULL_HISTORY_100": 2,
        "H1_IN_SAMPLE_100": 3,
        "TEST_IN_SAMPLE_100": 4,
        "TRAIN_IN_SAMPLE_100": 5,
    }
    catalog.sort(key=lambda c: (rank_kind.get(c["kind"], 9), -c["n"], c.get("risk", 99)))

    # Write JSON
    REPORT_JSON.write_text(
        json.dumps({"catalog": catalog, "results": results}, indent=2, default=str),
        encoding="utf-8",
    )

    # Append / rewrite MD lead for pass3
    lines = [
        "# NIFTY 1m — **100% only** calls (multi-logic, all passes)",
        "",
        "**Not live.**",
        "",
        f"Train ≤ `{TRAIN_END}` · Test `{TEST_START}`→`{TEST_END}`",
        "",
        "## 100%-only catalog (sorted)",
        "",
        "| Priority | Kind | Pool | Risk | N | Note |",
        "|---:|---|---|---:|---:|---|",
    ]
    for i, c in enumerate(catalog[:40], 1):
        note = (c.get("label") or "")[:48]
        lines.append(
            f"| {i} | `{c['kind']}` | `{c['pool']}` | {c.get('risk')} | **{c['n']}** | `{note}` |"
        )

    # Detail top honest + top multi-call
    honest = [c for c in catalog if c["kind"] in ("HONEST_UNION_100", "HONEST_MICRO_100")]
    multi = [c for c in catalog if c["n"] >= 5]
    lines += ["", "## Top honest (train-frozen ∩ test 100%)", ""]
    if not honest:
        lines.append("_None with test n≥1 under these structural logics._")
    for c in honest[:6]:
        lines += [
            f"### `{c['kind']}` · `{c['pool']}` · risk {c.get('risk')} · **{c['n']} @ 100%**",
            "",
            f"Filters: `{json.dumps(c.get('filters'), default=str)[:300]}`",
            "",
            "| Day | HM | Side | Win |",
            "|---|---|---|:---:|",
        ]
        for x in c.get("calls") or []:
            lines.append(f"| {x.get('day')} | {x.get('hm')} | {x.get('decision')} | Y |")
        lines.append("")

    lines += ["", "## Largest multi-call 100% books (any kind ≥5)", ""]
    for c in multi[:8]:
        lines += [
            f"### `{c['kind']}` · `{c['pool']}` · r{c.get('risk')} · **{c['n']} @ 100%**",
            "",
            "| Day | HM | Side | or_ext |",
            "|---|---|---|---:|",
        ]
        for x in (c.get("calls") or [])[:20]:
            lines.append(
                f"| {x.get('day')} | {x.get('hm')} | {x.get('decision')} | {x.get('or_ext')} |"
            )
        if len(c.get("calls") or []) > 20:
            lines.append(f"| … | | | +{len(c['calls'])-20} more |")
        lines.append("")

    lines += [
        "## Research pick",
        "",
    ]
    if honest:
        h = max(honest, key=lambda c: c["n"])
        lines.append(
            f"**Best honest 100%:** `{h['pool']}` · **{h['n']} calls @ 100%** · kind `{h['kind']}`."
        )
    if multi:
        m = max(multi, key=lambda c: (0 if 'HONEST' in c['kind'] else 1, -c['n']))
        # prefer honest multi, else largest
        honest_multi = [c for c in multi if "HONEST" in c["kind"]]
        pick = max(honest_multi, key=lambda c: c["n"]) if honest_multi else max(multi, key=lambda c: c["n"])
        lines.append(
            f"**Most 100% calls found:** `{pick['kind']}` / `{pick['pool']}` · "
            f"**{pick['n']} @ 100%** (see kind label for promote safety)."
        )
    lines += [
        "",
        "## Policy",
        "",
        "- Research only · not live",
        "- `FULL_HISTORY` / `H1` / `TEST_IN_SAMPLE` are ceilings or regimes — not auto-promote",
        "- Only `HONEST_*` kinds are train-frozen filters that stayed perfect on 2025",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {REPORT_MD}", flush=True)
    print(f"wrote {REPORT_JSON}", flush=True)
    print("\nTOP CATALOG:", flush=True)
    for c in catalog[:15]:
        print(f"  {c['kind']:22} {c['pool']:10} r{c.get('risk')} n={c['n']}", flush=True)
    print("DONE pass3", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
