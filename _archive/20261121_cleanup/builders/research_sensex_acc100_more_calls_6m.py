"""SENSEX deep research — maximize calls at 100% accuracy on last 6 months.

Live-style: full Sensex candidates · path settle ±50 on 5m.
Causal gates only (no win hindsight). Max N @ 100% + walk-forward holdout.

  python -u prod_live/tests/builders/research_sensex_acc100_more_calls_6m.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
import path_setup  # noqa: F401,E402

from research_bn_sensex_final_brackets import (  # noqa: E402
    load_tape,
    normalize_cand,
    path_score_pool,
)
from research_nifty_acc100_more_calls_6m import (  # noqa: E402
    deep_search,
    densest_100,
)
from research_nifty_sensex_100pct_last20 import (  # noqa: E402
    agg,
    apply_gate,
    gate_from_row,
    side,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "SENSEX_ACC100_MORE_CALLS_6M.md"
OUT_JSON = OUT / "SENSEX_ACC100_MORE_CALLS_6M.json"
OUT_STABLE = OUT / "SENSEX_ACC100_MORE_CALLS_6M_WF_STABLE.json"
LOCK_PATH = ROOT / "prod_live" / "holding_accurate" / "acc100_last20_locks.json"
CANDS = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_full_live_candidates.json"
)
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_5m_kite.csv"
LOCKED_T50 = (
    ROOT
    / "prod_live"
    / "holding_accurate"
    / "sensex_final"
    / "champ_plus_t50_sl50_calls.json"
)

T1 = SL = 50.0
END = datetime.now().date().isoformat()
START_6M = (pd.Timestamp(END) - pd.DateOffset(months=6)).date().isoformat()


def clip(rows: List[dict], a: str, b: str) -> List[dict]:
    return [r for r in rows if a <= str(r.get("day") or "")[:10] <= b]


def build_pool() -> List[dict]:
    bars, ix = load_tape(TAPE5)
    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("candidates") or raw.get("calls") or raw.get("rows") or []
    cands: List[dict] = []
    for r in raw:
        n = normalize_cand(r)
        if not n:
            continue
        day = n["day"]
        if not (START_6M <= day <= END):
            continue
        # Tag like live: first_break ≈ champion family; else continuation
        n["track"] = "champion" if n.get("first_break") else "continuation"
        cands.append(n)
    print(f"  raw cands in 6m window: {len(cands)}", flush=True)
    scored = path_score_pool(bars, ix, cands, SL, T1, prefer_native_outcome=False)
    scored = [r for r in scored if r.get("win") is not None]
    # keep only days present on tape session
    return scored


def live_t50_policy() -> Dict[str, Any]:
    return {
        "cap": 3,
        "pmin": 0.55,
        "tracks": None,  # current lock filters via first + side floors
        "hm_lo": None,
        "hm_hi": None,
        "max_or_ext": 0.10,
        "first_only": True,
        "sides": None,
        "buy_p": 0.55,
        "sell_p": 0.62,
    }


def prior_acc100_gate() -> Dict[str, Any]:
    if LOCK_PATH.exists():
        d = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        g = (d.get("sensex") or {}).get("gate") or {}
        tracks = g.get("tracks")
        return {
            "cap": int(g.get("cap") or 1),
            "pmin": float(g.get("pmin") or 0.55),
            "tracks": set(tracks) if isinstance(tracks, list) else {"champion"},
            "hm_lo": g.get("hm_lo"),
            "hm_hi": g.get("hm_hi"),
            "max_or_ext": g.get("max_or_ext"),
            "first_only": bool(g.get("first_only", True)),
            "sides": None,
            "buy_p": g.get("buy_p", 0.55),
            "sell_p": g.get("sell_p", 0.62),
        }
    return {
        "cap": 1,
        "pmin": 0.55,
        "tracks": {"champion"},
        "hm_lo": None,
        "hm_hi": None,
        "max_or_ext": None,
        "first_only": True,
        "sides": None,
        "buy_p": 0.55,
        "sell_p": 0.62,
    }


def write_report(payload: dict) -> None:
    b = payload["baseline_t50_6m"]
    prior = payload["prior_acc100_6m"]
    densest = payload.get("densest_100_6m") or {}
    wf = payload.get("walk_forward") or {}
    best = payload.get("recommended_lock") or {}
    lines = [
        "# SENSEX · ACC100 more calls · last 6 months (deep)",
        "",
        f"**Generated:** `{payload['generated']}`",
        f"**Window:** `{payload['start']}` → `{payload['end']}` · {payload['n_sessions']} sessions",
        "",
        "## Method",
        "",
        "- Live Sensex candidate book · path settle **±50** on 5m kite tape",
        "- Causal gates only — **never** filter on `win`",
        "- Goal: **max N @ 100%** on 6m (multi-lot OK)",
        "- Walk-forward: tune on first ~4m · hold out last ~2m · require 100% on both",
        "",
        "## Headline",
        "",
        f"- Live T50 Cap3 policy 6m: **{b.get('n')} @ {b.get('hit_pct')}%**",
        f"- Prior ACC100 Cap1 first 6m: **{prior.get('n')} @ {prior.get('hit_pct')}%**",
    ]
    if densest.get("stats"):
        st = densest["stats"]
        lines.append(
            f"- In-sample densest 100%: **{st.get('n')} @ {st.get('hit_pct')}%** · `{densest.get('gate_str')}`"
        )
    if best:
        lines.append(
            f"- **Recommended WF-stable lock:** **{best['full6m']['n']} @ {best['full6m']['hit_pct']}%** "
            f"(holdout {best['test2m']['n']} @ {best['test2m']['hit_pct']}%)"
        )
        lines.append(f"- Gate: `{best.get('gate')}`")
    if wf.get("test_stats"):
        lines.append(f"- Naive densest WF (may fail): test `{wf.get('test_stats')}`")
    lines += [
        "",
        "## Top in-sample 100% gates (by N)",
        "",
        "| N | Hit | Cap | pmin | Tracks | HM | or≤ | first | sides | buy/sell | Pts |",
        "|---:|---:|---:|---:|---|---|---:|---|---|---|---:|",
    ]
    for r in payload.get("top_perfect_6m") or []:
        lines.append(
            f"| {r['n']} | **{r['hit_pct']}** | {r['cap']} | {r['pmin']} | {r['tracks']} | "
            f"{r['hm_lo']}-{r['hm_hi']} | {r['max_or_ext']} | {r['first_only']} | "
            f"{r['sides']} | {r['buy_p']}/{r['sell_p']} | {r['points']} |"
        )
    if best.get("calls"):
        lines += [
            "",
            "## Recommended lock calls (6m)",
            "",
            "| Day | HM | Side | p | Track | Win | Pts |",
            "|---|---|---|---:|---|---|---:|",
        ]
        for c in best["calls"]:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['side']} | {c['p_t1']} | {c['track']} | "
                f"{'W' if c['win'] else 'L'} | {c['points']} |"
            )
    lines += [
        "",
        "## Recommendation",
        "",
        "1. Prefer **WF-stable** densest 100% over pure in-sample max N.",
        "2. Cap6-style volume (T50 Cap3) stays the volume desk — not ACC100.",
        "3. Scale returns with **lots** on ACC100 calls.",
        "",
        f"JSON: `{OUT_JSON}`",
        f"WF: `{OUT_STABLE}`",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def find_wf_stable(pool: List[dict], train: List[dict], test: List[dict]) -> List[dict]:
    train_res = deep_search(train, min_n=5, t1=T1, sl=SL)
    perfect = [r for r in train_res if (r.get("hit_pct") or 0) >= 99.999]
    print(f"  train perfect cores≈{len(perfect)}", flush=True)
    stable = []
    for row in perfect:
        g = gate_from_row(row)
        te = apply_gate(test, g, t1=T1, sl=SL)
        if te["n"] < 1 or (te.get("hit_pct") or 0) < 99.999:
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
    return stable


def main() -> int:
    t0 = time.time()
    print(f"SENSEX ACC100 more calls · 6m {START_6M}→{END}", flush=True)
    if not CANDS.exists() or not TAPE5.exists():
        print("missing candidates or tape", flush=True)
        return 1

    print("building pool…", flush=True)
    pool = build_pool()
    sessions = sorted({str(r.get("day") or "")[:10] for r in pool})
    print(f"settled pool={len(pool)} sessions={len(sessions)} · {agg(pool, t1=T1, sl=SL)}", flush=True)

    base = apply_gate(pool, live_t50_policy(), t1=T1, sl=SL)
    print(f"T50 live policy: n={base['n']} hit={base['hit_pct']}%", flush=True)
    prior_g = prior_acc100_gate()
    prior = apply_gate(pool, prior_g, t1=T1, sl=SL)
    print(f"Prior ACC100: n={prior['n']} hit={prior['hit_pct']}%", flush=True)

    print("deep search 6m…", flush=True)
    results = deep_search(pool, min_n=5, t1=T1, sl=SL)
    perfect = [r for r in results if (r.get("hit_pct") or 0) >= 99.999]
    perfect.sort(key=lambda x: (-x["n"], -x["points"]))
    best_row = densest_100(results, min_n=5)
    densest: Dict[str, Any] = {}
    if best_row:
        g = gate_from_row(best_row)
        book = apply_gate(pool, g, t1=T1, sl=SL)
        densest = {
            "gate": {k: (sorted(v) if isinstance(v, set) else v) for k, v in g.items()},
            "gate_str": (
                f"cap={g['cap']} p≥{g['pmin']} tracks={g['tracks']} "
                f"hm={g['hm_lo']}-{g['hm_hi']} or≤{g['max_or_ext']} "
                f"first={g['first_only']} sides={g['sides']} "
                f"buy/sell={g['buy_p']}/{g['sell_p']}"
            ),
            "stats": {k: book[k] for k in book if k != "calls"},
            "calls": book.get("calls"),
            "hit_row": best_row,
        }
        print(f"DENSEST in-sample: n={book['n']} hit={book['hit_pct']}%", flush=True)

    split = (pd.Timestamp(END) - pd.DateOffset(months=2)).date().isoformat()
    train = clip(pool, START_6M, split)
    test = [r for r in clip(pool, split, END) if str(r.get("day") or "")[:10] > split]
    print(f"WF train≤{split} n={len(train)} · test n={len(test)}", flush=True)

    wf: Dict[str, Any] = {}
    if densest.get("gate") and train and test:
        # naive densest applied to holdout
        g = densest["gate"]
        g2 = {
            "cap": g["cap"],
            "pmin": g["pmin"],
            "tracks": set(g["tracks"]) if isinstance(g["tracks"], list) else None,
            "hm_lo": None if g.get("hm_lo") in (None, "*") else g.get("hm_lo"),
            "hm_hi": None if g.get("hm_hi") in (None, "*") else g.get("hm_hi"),
            "max_or_ext": g.get("max_or_ext"),
            "first_only": bool(g.get("first_only")),
            "sides": None if g.get("sides") in (None, "BOTH") else set(g["sides"]),
            "buy_p": g.get("buy_p"),
            "sell_p": g.get("sell_p"),
        }
        te = apply_gate(test, g2, t1=T1, sl=SL)
        wf = {
            "split": split,
            "naive_densest_test": {k: te[k] for k in te if k != "calls"},
        }
        print(f"naive densest on test: {te['n']}@{te['hit_pct']}%", flush=True)

    print("WF-stable search…", flush=True)
    stable = find_wf_stable(pool, train, test) if train and test else []
    print(f"WF-stable count={len(stable)}", flush=True)
    recommended = None
    if stable:
        s0 = stable[0]
        recommended = {
            "desk": "SENSEX_ACC100_DENSE_WF",
            "gate": s0["gate"],
            "full6m": s0["full6m"],
            "test2m": s0["test2m"],
            "calls": s0["calls"],
            "evidence": (
                f"{s0['full6m']['n']}@100% on 6m · {s0['test2m']['n']}@100% holdout · "
                f"vs T50 {base['n']}@{base['hit_pct']}%"
            ),
        }
        print(
            f"BEST WF-stable: full {s0['full6m']['n']}@100% · test {s0['test2m']['n']}@100%",
            flush=True,
        )
        for s in stable[:10]:
            print(
                " ",
                s["full6m"]["n"],
                s["full6m"]["hit_pct"],
                "test",
                s["test2m"]["n"],
                s["gate"],
                flush=True,
            )

    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "start": START_6M,
        "end": END,
        "n_sessions": len(sessions),
        "pool_n": len(pool),
        "baseline_t50_6m": {k: base[k] for k in base if k != "calls"},
        "prior_acc100_6m": {k: prior[k] for k in prior if k != "calls"},
        "prior_acc100_gate": {
            k: (sorted(v) if isinstance(v, set) else v) for k, v in prior_g.items()
        },
        "densest_100_6m": densest,
        "top_perfect_6m": perfect[:15],
        "walk_forward": wf,
        "recommended_lock": recommended,
        "elapsed_s": round(time.time() - t0, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    OUT_STABLE.write_text(
        json.dumps(
            {
                "generated": payload["generated"],
                "split": split,
                "wf_stable_count": len(stable),
                "best_wf_stable": recommended,
                "top_wf_stable": [
                    {
                        "gate": s["gate"],
                        "full6m": s["full6m"],
                        "test2m": s["test2m"],
                    }
                    for s in stable[:20]
                ],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    write_report(payload)

    # update combined locks file
    locks = {}
    if LOCK_PATH.exists():
        locks = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    if recommended:
        locks["sensex"] = {
            "desk": recommended["desk"],
            "gate": recommended["gate"],
            "full6m": recommended["full6m"],
            "test2m": recommended["test2m"],
            "evidence": recommended["evidence"],
            "note": "Densest WF-stable 100% on last 6m Sensex live sessions",
        }
        LOCK_PATH.write_text(json.dumps(locks, indent=2), encoding="utf-8")

    print(f"Wrote {OUT_MD}", flush=True)
    print(f"Wrote {OUT_JSON}", flush=True)
    print(f"Elapsed {time.time()-t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
