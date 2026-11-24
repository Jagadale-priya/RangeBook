"""Find densest ACC100 gates that stay 100% on full 1y; report 3y/5y too."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
import path_setup  # noqa: F401,E402

from confirm_nifty_sensex_acc100_1_3_5y import (  # noqa: E402
    END,
    NIFTY_5M,
    NIFTY_CALLS,
    OUT,
    SENSEX_5M,
    SENSEX_CALLS,
    clip,
    prep_symbol,
    windows,
)
from research_nifty_acc100_more_calls_6m import deep_search, densest_100  # noqa: E402
from research_nifty_sensex_100pct_last20 import apply_gate, gate_from_row  # noqa: E402

OUT_MD = OUT / "NIFTY_SENSEX_ACC100_1Y_STABLE.md"
OUT_JSON = OUT / "NIFTY_SENSEX_ACC100_1Y_STABLE.json"


def measure_all(pool, gate, t1, sl, end):
    wins = windows(end)
    out = {}
    for label, start in wins.items():
        st = apply_gate(clip(pool, start, end), gate, t1=t1, sl=sl)
        out[label] = {k: st[k] for k in st if k != "calls"}
    return out


def run_sym(name, pool, t1, sl):
    wins = windows(END)
    pool_1y = clip(pool, wins["1y"], END)
    print(f"\n{name} deep search on 1y n={len(pool_1y)}…", flush=True)
    results = deep_search(pool_1y, min_n=5, t1=t1, sl=sl)
    best = densest_100(results, min_n=5)
    if not best:
        return {"ok": False, "error": "no_100pct"}
    g = gate_from_row(best)
    # require 100% on full 1y
    st1 = apply_gate(pool_1y, g, t1=t1, sl=sl)
    if (st1.get("hit_pct") or 0) < 99.999:
        # take densest from perfect list
        perfect = [r for r in results if (r.get("hit_pct") or 0) >= 99.999]
        perfect.sort(key=lambda x: (-x["n"], -x["points"]))
        if not perfect:
            return {"ok": False, "error": "no_perfect"}
        g = gate_from_row(perfect[0])
        st1 = apply_gate(pool_1y, g, t1=t1, sl=sl)
    meas = measure_all(pool, g, t1, sl, END)
    calls = apply_gate(pool_1y, g, t1=t1, sl=sl).get("calls")
    return {
        "ok": True,
        "gate": {k: (sorted(v) if isinstance(v, set) else v) for k, v in g.items()},
        "windows": meas,
        "calls_1y": calls,
        "hit_row": best,
    }


def main() -> int:
    nifty = prep_symbol("NIFTY", NIFTY_CALLS, NIFTY_5M, sl=30.0, t1=30.0)
    sensex = prep_symbol("SENSEX", SENSEX_CALLS, SENSEX_5M, sl=50.0, t1=50.0)
    n = run_sym("NIFTY", nifty, 30.0, 30.0)
    s = run_sym("SENSEX", sensex, 50.0, 50.0)
    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "end": END,
        "nifty": n,
        "sensex": s,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# NIFTY + SENSEX · densest ACC100 stable on **1y** (then 3y/5y)",
        "",
        f"**Generated:** `{payload['generated']}`",
        "",
        "Search densest causal 100% on **full 1y**, then measure same gate on 6m/3y/5y.",
        "",
    ]
    for key, title, t in (("nifty", "NIFTY ±30", 30), ("sensex", "SENSEX ±50", 50)):
        block = payload[key]
        lines.append(f"## {title}")
        lines.append("")
        if not block.get("ok"):
            lines.append(f"ERROR: {block.get('error')}")
            lines.append("")
            continue
        lines.append(f"Gate: `{block['gate']}`")
        lines.append("")
        lines.append("| Window | N | Hit | W/L | Pts |")
        lines.append("|---|---:|---:|---|---:|")
        for w in ("6m", "1y", "3y", "5y"):
            a = block["windows"][w]
            lines.append(
                f"| {w} | {a['n']} | **{a['hit_pct']}** | {a['wins']}/{a['losses']} | {a['points']} |"
            )
        lines.append("")
        print(title, block["gate"], flush=True)
        for w in ("6m", "1y", "3y", "5y"):
            a = block["windows"][w]
            print(f"  {w}: {a['n']}@{a['hit_pct']}%", flush=True)
    lines += [f"JSON: `{OUT_JSON}`", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", OUT_MD, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
