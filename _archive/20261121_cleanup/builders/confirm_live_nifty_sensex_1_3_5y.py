"""Confirm CURRENT live desks · 6m / 1y / 3y / 5y (5m path settle).

NIFTY live:  CHAMP_PLUS_T30SL30_CAP6 (±30 Cap6)
SENSEX live: SENSEX_DUAL_FB_BF20_T50 (±50 · held dual+fb book)

  python -u prod_live/tests/builders/confirm_live_nifty_sensex_1_3_5y.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

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
from research_nifty_sensex_100pct_last20 import agg, apply_gate  # noqa: E402

OUT_MD = OUT / "LIVE_NIFTY_SENSEX_1_3_5Y.md"
OUT_JSON = OUT / "LIVE_NIFTY_SENSEX_1_3_5Y.json"

# Live Cap6 = day-cap 6, no extra p/track/hm filters (book already Cap6-filled)
NIFTY_LIVE = {
    "cap": 6,
    "pmin": 0.0,
    "tracks": None,
    "hm_lo": None,
    "hm_hi": None,
    "max_or_ext": None,
    "first_only": False,
    "sides": None,
    "buy_p": None,
    "sell_p": None,
}
# Live Sensex dual_fb book is pre-filtered; measure full pool (cap 99)
SENSEX_LIVE = {
    "cap": 99,
    "pmin": 0.0,
    "tracks": None,
    "hm_lo": None,
    "hm_hi": None,
    "max_or_ext": None,
    "first_only": False,
    "sides": None,
    "buy_p": None,
    "sell_p": None,
}


def measure(pool: List[dict], gate: Dict[str, Any], *, t1: float, sl: float, end: str) -> Dict[str, Any]:
    wins = windows(end)
    out: Dict[str, Any] = {}
    for label, start in wins.items():
        st = apply_gate(clip(pool, start, end), gate, t1=t1, sl=sl)
        out[label] = {
            "start": start,
            "end": end,
            **{k: st[k] for k in st if k != "calls"},
        }
    return out


def main() -> int:
    t0 = time.time()
    print(f"Confirm LIVE desks · 1y/3y/5y · end={END}", flush=True)

    nifty = prep_symbol("NIFTY Cap6", NIFTY_CALLS, NIFTY_5M, sl=30.0, t1=30.0)
    sensex = prep_symbol("SENSEX DUAL_FB", SENSEX_CALLS, SENSEX_5M, sl=50.0, t1=50.0)

    n_meas = measure(nifty, NIFTY_LIVE, t1=30.0, sl=30.0, end=END)
    s_meas = measure(sensex, SENSEX_LIVE, t1=50.0, sl=50.0, end=END)

    # uncapped raw pool stats for sanity (should match live if book already filtered)
    print("\n=== LIVE RESULTS ===", flush=True)
    print(f"\n{'':4} {'NIFTY Cap6':^22}  {'SENSEX DUAL_FB':^22}", flush=True)
    print(f"{'Win':<4} {'N':>6} {'Hit':>7} {'Pts':>8}  {'N':>6} {'Hit':>7} {'Pts':>8}", flush=True)
    for w in ("6m", "1y", "3y", "5y"):
        a, b = n_meas[w], s_meas[w]
        print(
            f"{w:<4} {a['n']:>6} {a['hit_pct']:>7} {a['points']:>8}  "
            f"{b['n']:>6} {b['hit_pct']:>7} {b['points']:>8}",
            flush=True,
        )

    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "end": END,
        "desks": {
            "nifty": "CHAMP_PLUS_T30SL30_CAP6",
            "sensex": "SENSEX_DUAL_FB_BF20_T50",
            "brackets": {"nifty": "±30", "sensex": "±50"},
        },
        "nifty": n_meas,
        "sensex": s_meas,
        "pool_agg": {
            "nifty": agg(nifty, t1=30.0, sl=30.0),
            "sensex": agg(sensex, t1=50.0, sl=50.0),
        },
        "elapsed_s": round(time.time() - t0, 1),
    }

    lines = [
        "# Live NIFTY + SENSEX · 6m / 1y / 3y / 5y",
        "",
        f"**Generated:** `{payload['generated']}` · end `{END}`",
        "",
        "Current live desks, 5m path-settled (first touch SL vs T1).",
        "",
        "| Index | Desk | Brackets |",
        "|---|---|---|",
        "| **NIFTY** | `CHAMP_PLUS_T30SL30_CAP6` | ±30 Cap6 |",
        "| **SENSEX** | `SENSEX_DUAL_FB_BF20_T50` | ±50 |",
        "",
        "## Totals",
        "",
        "| Window | NIFTY N | NIFTY Hit | NIFTY W/L | NIFTY Pts | SENSEX N | SENSEX Hit | SENSEX W/L | SENSEX Pts |",
        "|---|---:|---:|---|---:|---:|---:|---|---:|",
    ]
    for w in ("6m", "1y", "3y", "5y"):
        a, b = n_meas[w], s_meas[w]
        lines.append(
            f"| {w} | {a['n']} | **{a['hit_pct']}** | {a['wins']}/{a['losses']} | {a['points']} | "
            f"{b['n']} | **{b['hit_pct']}** | {b['wins']}/{b['losses']} | {b['points']} |"
        )
    lines += [
        "",
        f"- NIFTY book: `{NIFTY_CALLS.name}`",
        f"- SENSEX book: `{SENSEX_CALLS.name}`",
        "- Sensex 3y≈5y when tape/book only covers ~3y.",
        "",
        f"JSON: `{OUT_JSON}`",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {OUT_MD}", flush=True)
    print(f"Elapsed {payload['elapsed_s']}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
