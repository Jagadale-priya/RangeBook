"""Confirm NIFTY + SENSEX ACC100 locks on 1y / 3y / 5y (path settle).

Uses locked live call books + 5m re-settle. Reports Cap volume baseline vs ACC100 gate.

  python -u prod_live/tests/builders/confirm_nifty_sensex_acc100_1_3_5y.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
import path_setup  # noqa: F401,E402

from research_nifty_sensex_100pct_last20 import (  # noqa: E402
    agg,
    apply_gate,
    build_bar_index,
    load_calls,
    resettle,
    side,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "NIFTY_SENSEX_ACC100_1_3_5Y.md"
OUT_JSON = OUT / "NIFTY_SENSEX_ACC100_1_3_5Y.json"
LOCKS = ROOT / "prod_live" / "holding_accurate" / "acc100_last20_locks.json"

NIFTY_CALLS = (
    ROOT / "prod_live" / "holding_accurate" / "champion_plus" / "t30_sl30_5y_calls.json"
)
SENSEX_CALLS = (
    ROOT
    / "prod_live"
    / "holding_accurate"
    / "sensex_final"
    / "champ_plus_t50_sl50_calls.json"
)
NIFTY_5M = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
SENSEX_5M = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_5m_kite.csv"

END = datetime.now().date().isoformat()


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    w = df.copy()
    if getattr(w.index, "tz", None) is not None:
        w.index = w.index.tz_convert("Asia/Kolkata")
    else:
        w.index = w.index.tz_localize("Asia/Kolkata")
    w = w.rename(columns={c: str(c).title() for c in w.columns})
    cols = [c for c in ("Open", "High", "Low", "Close") if c in w.columns]
    w = w[cols].astype(float).sort_index()
    w = w[~w.index.duplicated(keep="last")]
    hm = w.index.strftime("%H:%M")
    return w[(hm >= "09:15") & (hm <= "15:30")]


def windows(end: str) -> Dict[str, str]:
    e = pd.Timestamp(end)
    return {
        "1y": (e - pd.DateOffset(years=1)).date().isoformat(),
        "3y": (e - pd.DateOffset(years=3)).date().isoformat(),
        "5y": (e - pd.DateOffset(years=5)).date().isoformat(),
        "6m": (e - pd.DateOffset(months=6)).date().isoformat(),
    }


def parse_gate(g: dict) -> Dict[str, Any]:
    tracks = g.get("tracks")
    sides = g.get("sides")
    return {
        "cap": int(g.get("cap") or 1),
        "pmin": float(g.get("pmin") or 0.0),
        "tracks": set(tracks) if isinstance(tracks, list) else None,
        "hm_lo": None if g.get("hm_lo") in (None, "*") else g.get("hm_lo"),
        "hm_hi": None if g.get("hm_hi") in (None, "*") else g.get("hm_hi"),
        "max_or_ext": g.get("max_or_ext"),
        "first_only": bool(g.get("first_only")),
        "sides": None if sides in (None, "BOTH") else set(sides),
        "buy_p": g.get("buy_p"),
        "sell_p": g.get("sell_p"),
    }


def clip(rows: List[dict], a: str, b: str) -> List[dict]:
    return [r for r in rows if a <= str(r.get("day") or "")[:10] <= b]


def prep_symbol(
    name: str,
    calls_path: Path,
    tape_path: Path,
    *,
    sl: float,
    t1: float,
) -> List[dict]:
    print(f"\n=== {name}: load + resettle ===", flush=True)
    raw = load_calls(calls_path)
    bars = _norm(pd.read_csv(tape_path, index_col=0, parse_dates=True))
    by = build_bar_index(bars)
    raw = [r for r in raw if str(r.get("day") or "")[:10] in by]
    # Sensex locked book may lack track on some rows — keep as-is
    for r in raw:
        if not r.get("track"):
            r["track"] = "champion" if r.get("first_break") else "continuation"
        if r.get("decision") is None:
            r["decision"] = side(r)
    scored = resettle(raw, by, sl_pts=sl, t1_pts=t1)
    print(f"  settled={len(scored)} · {agg(scored, t1=t1, sl=sl)}", flush=True)
    return scored


def measure(
    pool: List[dict],
    gate: Dict[str, Any],
    *,
    t1: float,
    sl: float,
    end: str,
) -> Dict[str, Any]:
    wins = windows(end)
    out: Dict[str, Any] = {}
    for label, start in wins.items():
        sub = clip(pool, start, end)
        st = apply_gate(sub, gate, t1=t1, sl=sl)
        out[label] = {
            "start": start,
            "end": end,
            **{k: st[k] for k in st if k != "calls"},
        }
    return out


def main() -> int:
    t0 = time.time()
    print(f"Confirm ACC100 · 1y/3y/5y · end={END}", flush=True)
    locks = json.loads(LOCKS.read_text(encoding="utf-8")) if LOCKS.exists() else {}

    nifty_gate = parse_gate((locks.get("nifty") or {}).get("gate") or {
        "cap": 1,
        "pmin": 0.55,
        "tracks": ["champion", "good_prod2", "proven_research"],
        "hm_lo": "10:00",
        "hm_hi": "14:00",
    })
    sensex_gate = parse_gate((locks.get("sensex") or {}).get("gate") or {
        "cap": 1,
        "pmin": 0.5,
        "tracks": None,
        "hm_lo": "10:00",
        "hm_hi": "14:00",
        "first_only": True,
    })

    nifty_cap6 = {
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
    sensex_t50 = {
        "cap": 3,
        "pmin": 0.55,
        "tracks": None,
        "hm_lo": None,
        "hm_hi": None,
        "max_or_ext": 0.10,
        "first_only": True,
        "sides": None,
        "buy_p": 0.55,
        "sell_p": 0.62,
    }

    nifty_pool = prep_symbol("NIFTY", NIFTY_CALLS, NIFTY_5M, sl=30.0, t1=30.0)
    sensex_pool = prep_symbol("SENSEX", SENSEX_CALLS, SENSEX_5M, sl=50.0, t1=50.0)

    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "end": END,
        "nifty": {
            "acc100_gate": {
                k: (sorted(v) if isinstance(v, set) else v) for k, v in nifty_gate.items()
            },
            "acc100": measure(nifty_pool, nifty_gate, t1=30.0, sl=30.0, end=END),
            "cap6": measure(nifty_pool, nifty_cap6, t1=30.0, sl=30.0, end=END),
            "desk": (locks.get("nifty") or {}).get("desk"),
        },
        "sensex": {
            "acc100_gate": {
                k: (sorted(v) if isinstance(v, set) else v)
                for k, v in sensex_gate.items()
            },
            "acc100": measure(sensex_pool, sensex_gate, t1=50.0, sl=50.0, end=END),
            "t50": measure(sensex_pool, sensex_t50, t1=50.0, sl=50.0, end=END),
            "desk": (locks.get("sensex") or {}).get("desk"),
        },
        "elapsed_s": None,
    }

    # Print table
    print("\n=== RESULTS ===", flush=True)
    for sym, vol_key in (("nifty", "cap6"), ("sensex", "t50")):
        print(f"\n{sym.upper()}", flush=True)
        print(f"{'Win':<4} {'ACC100 N':>8} {'Hit':>7} {'Vol N':>8} {'Vol Hit':>8}", flush=True)
        for w in ("6m", "1y", "3y", "5y"):
            a = payload[sym]["acc100"][w]
            v = payload[sym][vol_key][w]
            print(
                f"{w:<4} {a.get('n'):>8} {a.get('hit_pct'):>7} {v.get('n'):>8} {v.get('hit_pct'):>8}",
                flush=True,
            )

    lines = [
        "# NIFTY + SENSEX · ACC100 locks · 1y / 3y / 5y confirm",
        "",
        f"**Generated:** `{payload['generated']}` · end `{END}`",
        "",
        "Re-settled on 5m tape (first touch SL vs T1). Gates from `acc100_last20_locks.json`.",
        "",
        "## NIFTY (±30)",
        "",
        f"ACC100 desk: `{(locks.get('nifty') or {}).get('desk')}`",
        f"Gate: `{payload['nifty']['acc100_gate']}`",
        "",
        "| Window | ACC100 N | Hit | W/L | Pts | Cap6 N | Cap6 Hit |",
        "|---|---:|---:|---|---:|---:|---:|",
    ]
    for w in ("6m", "1y", "3y", "5y"):
        a = payload["nifty"]["acc100"][w]
        v = payload["nifty"]["cap6"][w]
        lines.append(
            f"| {w} | {a['n']} | **{a['hit_pct']}** | {a['wins']}/{a['losses']} | {a['points']} | "
            f"{v['n']} | {v['hit_pct']} |"
        )
    lines += [
        "",
        "## SENSEX (±50)",
        "",
        f"ACC100 desk: `{(locks.get('sensex') or {}).get('desk')}`",
        f"Gate: `{payload['sensex']['acc100_gate']}`",
        "",
        "| Window | ACC100 N | Hit | W/L | Pts | T50 N | T50 Hit |",
        "|---|---:|---:|---|---:|---:|---:|",
    ]
    for w in ("6m", "1y", "3y", "5y"):
        a = payload["sensex"]["acc100"][w]
        v = payload["sensex"]["t50"][w]
        lines.append(
            f"| {w} | {a['n']} | **{a['hit_pct']}** | {a['wins']}/{a['losses']} | {a['points']} | "
            f"{v['n']} | {v['hit_pct']} |"
        )
    lines += [
        "",
        "## Read",
        "",
        "- If ACC100 stays **100%** on 1y/3y/5y → lock is robust for live.",
        "- If it slips on longer windows → keep as 6m-accurate sparse desk; do not claim multi-year 100%.",
        "- Volume desks (Cap6 / T50) remain the denser lower-accuracy book.",
        "",
        f"JSON: `{OUT_JSON}`",
        "",
    ]
    payload["elapsed_s"] = round(time.time() - t0, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {OUT_MD}", flush=True)
    print(f"Wrote {OUT_JSON}", flush=True)
    print(f"Elapsed {payload['elapsed_s']}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
