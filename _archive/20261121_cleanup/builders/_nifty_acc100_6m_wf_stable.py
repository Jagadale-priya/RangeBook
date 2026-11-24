"""Find NIFTY ACC100 gates that stay 100% on walk-forward holdout, max N on 6m."""
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

from research_100pct_deeper_more_calls import _norm  # noqa: E402
from research_nifty_acc100_more_calls_6m import (  # noqa: E402
    END,
    OUT,
    OUT_MD,
    OUT_JSON,
    START_6M,
    T1,
    SL,
    TAPE5,
    build_live_pool,
    clip,
    deep_search,
    prior_lock_gate,
)
from research_nifty_sensex_100pct_last20 import apply_gate, gate_from_row  # noqa: E402

OUT_STABLE = OUT / "NIFTY_ACC100_MORE_CALLS_6M_WF_STABLE.json"


def main() -> int:
    print("rebuild pool…", flush=True)
    bars = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    hm = bars.index.strftime("%H:%M")
    bars = bars[(hm >= "09:15") & (hm <= "15:30")]
    days = sorted(
        {str(t.date()) for t in bars.index if START_6M <= str(t.date()) <= END}
    )
    pool = build_live_pool(days)
    pool = [r for r in pool if r.get("win") is not None]
    split = (pd.Timestamp(END) - pd.DateOffset(months=2)).date().isoformat()
    train = clip(pool, START_6M, split)
    test = [
        r
        for r in clip(pool, split, END)
        if str(r.get("day") or "")[:10] > split
    ]
    print(f"train={len(train)} test={len(test)} pool={len(pool)}", flush=True)

    train_res = deep_search(train, min_n=5)
    perfect = [r for r in train_res if (r.get("hit_pct") or 0) >= 99.999]
    print(f"train perfect={len(perfect)}", flush=True)

    stable = []
    for row in perfect:
        g = gate_from_row(row)
        te = apply_gate(test, g, t1=T1, sl=SL)
        if te["n"] < 1:
            continue
        if (te.get("hit_pct") or 0) < 99.999:
            continue
        full = apply_gate(pool, g, t1=T1, sl=SL)
        if (full.get("hit_pct") or 0) < 99.999:
            continue
        stable.append(
            {
                "gate": {
                    k: (sorted(v) if isinstance(v, set) else v) for k, v in g.items()
                },
                "train_row": row,
                "test2m": {k: te[k] for k in te if k != "calls"},
                "full6m": {k: full[k] for k in full if k != "calls"},
                "calls": full.get("calls"),
            }
        )
    stable.sort(
        key=lambda x: (-x["full6m"]["n"], -x["test2m"]["n"], -x["full6m"]["points"])
    )
    print(f"WF-stable 100% train+test+full6m: {len(stable)}", flush=True)
    for s in stable[:15]:
        print(
            " full",
            s["full6m"]["n"],
            s["full6m"]["hit_pct"],
            " test",
            s["test2m"]["n"],
            s["test2m"]["hit_pct"],
            " gate",
            s["gate"],
            flush=True,
        )

    g19 = {
        "cap": 1,
        "pmin": 0.55,
        "tracks": {"champion", "good_prod2", "proven_research"},
        "hm_lo": "10:00",
        "hm_hi": "14:00",
        "max_or_ext": None,
        "first_only": False,
        "sides": None,
        "buy_p": None,
        "sell_p": None,
    }
    prior = prior_lock_gate()
    checks = {
        "in_sample_densest_19_on_test": {
            k: v
            for k, v in apply_gate(test, g19, t1=T1, sl=SL).items()
            if k != "calls"
        },
        "in_sample_densest_19_on_full": {
            k: v
            for k, v in apply_gate(pool, g19, t1=T1, sl=SL).items()
            if k != "calls"
        },
        "prior_lock_on_test": {
            k: v
            for k, v in apply_gate(test, prior, t1=T1, sl=SL).items()
            if k != "calls"
        },
        "prior_lock_on_full": {
            k: v
            for k, v in apply_gate(pool, prior, t1=T1, sl=SL).items()
            if k != "calls"
        },
    }
    print("checks", json.dumps(checks, indent=2), flush=True)

    best = stable[0] if stable else None
    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "split": split,
        "checks": checks,
        "wf_stable_count": len(stable),
        "best_wf_stable": best,
        "top_wf_stable": stable[:20],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_STABLE.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    # patch main MD with WF-stable recommendation
    base = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    base["wf_stable"] = out
    if best:
        base["recommended_lock"] = {
            "desk": "NIFTY_ACC100_DENSE_WF",
            "gate": best["gate"],
            "full6m": best["full6m"],
            "test2m": best["test2m"],
            "evidence": (
                f"{best['full6m']['n']}@100% on 6m · "
                f"{best['test2m']['n']}@100% on WF holdout · "
                f"vs Cap6 {base['baseline_cap6_6m']['n']}@"
                f"{base['baseline_cap6_6m']['hit_pct']}%"
            ),
        }
    OUT_JSON.write_text(json.dumps(base, indent=2, default=str), encoding="utf-8")

    lines = [
        "",
        "## WF-stable densest 100% (honest)",
        "",
        "In-sample densest **19@100%** (hm 10:00–14:00) **fails** walk-forward "
        f"(`{checks['in_sample_densest_19_on_test']}`).",
        f"Prior Cap1 lock on full 6m: `{checks['prior_lock_on_full']}` "
        "(not perfect on 6m).",
        "",
    ]
    if best:
        lines += [
            f"**Recommended denser lock:** `{best['gate']}`",
            f"- Full 6m: **{best['full6m']['n']} @ {best['full6m']['hit_pct']}%**",
            f"- WF test (~2m): **{best['test2m']['n']} @ {best['test2m']['hit_pct']}%**",
            "",
            "| Day | HM | Side | p | Track | Win | Pts |",
            "|---|---|---|---:|---|---|---:|",
        ]
        for c in best.get("calls") or []:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['side']} | {c['p_t1']} | {c['track']} | "
                f"{'W' if c['win'] else 'L'} | {c['points']} |"
            )
    else:
        lines.append(
            "**No gate stayed 100% on both train and holdout with N≥5 train.** "
            "Keep sparse prior Cap1 lock for accuracy; denser books are in-sample only."
        )
    lines += ["", f"WF JSON: `{OUT_STABLE}`", ""]
    OUT_MD.write_text(OUT_MD.read_text(encoding="utf-8") + "\n".join(lines), encoding="utf-8")
    print("Wrote", OUT_STABLE, flush=True)
    if best:
        print("BEST WF-stable full6m n=", best["full6m"]["n"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
