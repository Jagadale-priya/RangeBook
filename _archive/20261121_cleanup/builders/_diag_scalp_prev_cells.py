"""Deep cells for prev-candle SL scalp — find both-100 micros + T1-reached stats."""
from __future__ import annotations

import json
import pickle
import sys
from collections import defaultdict
from itertools import product
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401,E402

import research_nifty_1m_scalp_prevcandle_100 as S  # noqa: E402

PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_prevcandle_100"
OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT_MD = OUT / "NIFTY_1M_SCALP_PREVCANDLE_100.md"


def cell_key(e):
    return (
        e["primary"],
        e["decision"],
        e["pre_regime"],
        int(e["align_session"]),
        e["clock"],
        "b45+" if e["body_frac"] >= 0.45 else "b<45",
        "sl<=10" if e["sl_prev"] <= 10 else ("sl<=15" if e["sl_prev"] <= 15 else ("sl<=20" if e["sl_prev"] <= 20 else "sl>20")),
        "rsi_lo" if e["rsi_14"] < 40 else ("rsi_mid" if e["rsi_14"] <= 60 else "rsi_hi"),
    )


def main() -> int:
    cache = next(PACK.glob("scalp_events_*.pkl"))
    blob = pickle.load(cache.open("rb"))
    cal, test = blob["cal"], blob["test"]
    print(f"loaded {cache.name} cal={len(cal)} test={len(test)}", flush=True)

    # Target-reached (MFE) vs path-win (T1 before prev SL)
    for t1 in (10.0, 20.0):
        mfe_hit = sum(1 for e in cal if e["mfe"] >= t1 and e["sl_prev"] >= 4) / max(
            1, sum(1 for e in cal if e["sl_prev"] >= 4)
        )
        key = f"prev_t{int(t1)}"
        path_hit = sum(1 for e in cal if e.get(key) == "win") / max(
            1, sum(1 for e in cal if e.get(key) not in (None, "bad_sl", "missing"))
        )
        print(f"T1={t1}: MFE>={t1} rate={100*mfe_hit:.1f}% · path-win prevSL={100*path_hit:.1f}%", flush=True)

    # Build cells for path-win prev T1=10 and T1=20
    perfect = []
    for t1 in (10.0, 20.0, 15.0):
        key = f"prev_t{int(t1)}"
        cal_c = defaultdict(list)
        test_c = defaultdict(list)
        for e in cal:
            if e.get(key) in (None, "bad_sl", "missing"):
                continue
            if e["sl_prev"] > 25:
                continue
            cal_c[cell_key(e)].append(e)
        for e in test:
            if e.get(key) in (None, "bad_sl", "missing"):
                continue
            if e["sl_prev"] > 25:
                continue
            test_c[cell_key(e)].append(e)

        for k, es in cal_c.items():
            if len(es) < 4:
                continue
            a = S.eval_book(es, "prev", t1, day_unique=True)
            if a["n"] < 3 or a["hit_pct"] < 100 - 1e-9:
                continue
            te = test_c.get(k, [])
            if len(te) < 1:
                continue
            t = S.eval_book(te, "prev", t1, day_unique=True)
            if t["n"] < 1:
                continue
            if t["hit_pct"] >= 100 - 1e-9:
                perfect.append(
                    {
                        "t1": t1,
                        "key": k,
                        "cal_n": a["n"],
                        "l3m_n": t["n"],
                        "avg_sl": t["avg_sl"],
                        "med_sl": t["med_sl"],
                        "last3m_calls": t["calls"],
                        "cal_calls": a["calls"],
                    }
                )

    perfect.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"], r["avg_sl"]))
    print(f"\nboth-100 prev-candle cells: {len(perfect)}", flush=True)
    for r in perfect[:15]:
        print(
            f"  T1={r['t1']} cal{r['cal_n']} l3m{r['l3m_n']} medSL={r['med_sl']} {r['key']}",
            flush=True,
        )

    # Union greedy
    used_c, used_t = set(), set()
    chosen, calls_t = [], []
    for r in perfect:
        ca = {x["day"] for x in r["cal_calls"]}
        lt = {x["day"] for x in r["last3m_calls"]}
        if ca & used_c or lt & used_t:
            continue
        chosen.append(r)
        used_c |= ca
        used_t |= lt
        calls_t.extend(r["last3m_calls"])
    print(
        f"UNION cells cal {len(used_c)} days · l3m {len(used_t)} days · micros={len(chosen)}",
        flush=True,
    )

    # Also: MFE-only 100% cells (target reached, ignore SL order) — user insight
    mfe_perfect = []
    for t1 in (10.0, 20.0):
        cal_c = defaultdict(list)
        test_c = defaultdict(list)
        for e in cal:
            if e["sl_prev"] < 4 or e["sl_prev"] > 25:
                continue
            cal_c[cell_key(e)].append(e)
        for e in test:
            if e["sl_prev"] < 4 or e["sl_prev"] > 25:
                continue
            test_c[cell_key(e)].append(e)
        for k, es in cal_c.items():
            # day unique first
            by = {}
            for e in sorted(es, key=lambda x: x["mins"]):
                by.setdefault(e["day"], e)
            rows = list(by.values())
            if len(rows) < 3:
                continue
            if any(e["mfe"] < t1 for e in rows):
                continue
            te = test_c.get(k, [])
            by2 = {}
            for e in sorted(te, key=lambda x: x["mins"]):
                by2.setdefault(e["day"], e)
            rows2 = list(by2.values())
            if len(rows2) < 1:
                continue
            if any(e["mfe"] < t1 for e in rows2):
                continue
            mfe_perfect.append(
                {
                    "t1": t1,
                    "key": k,
                    "cal_n": len(rows),
                    "l3m_n": len(rows2),
                    "avg_sl": round(float(np.mean([e["sl_prev"] for e in rows2])), 2),
                    "note": "MFE_only_target_reached",
                }
            )
    mfe_perfect.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"]))
    print(f"\nMFE-only both-100 cells (target reached): {len(mfe_perfect)}", flush=True)
    for r in mfe_perfect[:12]:
        print(f"  T1={r['t1']} cal{r['cal_n']} l3m{r['l3m_n']} avgSL={r['avg_sl']} {r['key']}", flush=True)

    # Patch report with deep findings
    md = REPORT_MD.read_text(encoding="utf-8") if REPORT_MD.exists() else ""
    extra = [
        "",
        "## Deep cell analysis (added)",
        "",
        "### Path-win both-100 (T1 before prev-candle stop)",
        "",
        f"- Cells: **{len(perfect)}** · Union days cal **{len(used_c)}** · last3m **{len(used_t)}**",
        "",
    ]
    if perfect:
        extra += [
            "| T1 | Cal days | L3m days | Med SL | Cell |",
            "|---:|---:|---:|---:|---|",
        ]
        for r in perfect[:12]:
            extra.append(
                f"| {r['t1']} | {r['cal_n']} | {r['l3m_n']} | {r['med_sl']} | `{r['key']}` |"
            )
        extra += ["", "### Union last3m calls", "", "| Day | HM | Side | Primary | SL | T1 | Win |", "|---|---|---|---|---:|---:|:---:|"]
        for r in sorted(calls_t, key=lambda x: (x["day"], x["hm"]))[:40]:
            extra.append(
                f"| {r['day']} | {r['hm']} | {r['decision']} | {r['primary']} | "
                f"{r['sl']} | {r['t1']} | Y |"
            )
    else:
        extra.append("- none with day-unique both-100 under prev-candle stop")

    extra += [
        "",
        "### Target-reached only (MFE ≥ T1, SL order ignored)",
        "",
        f"- Cells where every selected day reached T1: **{len(mfe_perfect)}**",
        "",
        "This matches the insight: if the scalp target always prints, the stop is only "
        "structure insurance — accuracy is defined by **target hit**.",
        "",
    ]
    if mfe_perfect:
        extra += ["| T1 | Cal days | L3m days | Avg prev-SL | Cell |", "|---:|---:|---:|---:|---|"]
        for r in mfe_perfect[:12]:
            extra.append(
                f"| {r['t1']} | {r['cal_n']} | {r['l3m_n']} | {r['avg_sl']} | `{r['key']}` |"
            )

    # Replace empty perfect section note
    if "## Deep cell analysis" not in md:
        REPORT_MD.write_text(md.rstrip() + "\n" + "\n".join(extra) + "\n", encoding="utf-8")
    print(f"updated {REPORT_MD}", flush=True)

    payload = {
        "path_perfect": [
            {k: v for k, v in r.items() if k not in ("last3m_calls", "cal_calls")}
            for r in perfect[:30]
        ],
        "union_l3m_n": len(used_t),
        "union_cal_n": len(used_c),
        "mfe_perfect": mfe_perfect[:30],
    }
    (OUT / "NIFTY_1M_SCALP_PREVCANDLE_100_CELLS.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    print("DONE cells", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
