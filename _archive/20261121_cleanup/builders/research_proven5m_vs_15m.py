"""RESEARCH only — try proven track from dual **5m** vs locked dual **15m**.

Does NOT change LIVE / golden / P2F.

Compares:
  A) Standalone proven_100: dual15 vs dual5
  B) Volume stack STACK_PLUS_CROWN_HTF_CAP2 with proven swapped to dual5
     (good / champ / crown HTF unchanged from live pool)

  python -u prod_live/tests/builders/research_proven5m_vs_15m.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import POOL, PRIORITY, _agg, _champ_floor  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"

WINDOWS = {
    "golden_1y": ("2025-10-24", "2026-10-23"),
    "holding_1y": ("2025-11-15", "2026-11-15"),
    "last_6m": ("2026-05-16", "2026-11-15"),
}


def _clip(rows: List[dict], start: str, end: str) -> List[dict]:
    return [r for r in rows if start <= str(r.get("day") or "") <= end]


def _clean(rows: List[dict]) -> List[dict]:
    out = []
    for r in rows:
        if r is None:
            continue
        rr = dict(r)
        if "win" not in rr:
            o = rr.get("outcome")
            if o == "t1_before_sl":
                rr["win"] = True
            elif o in ("sl_before_t1", "same_bar_both"):
                rr["win"] = False
        out.append(rr)
    return out


def _score(rows: List[dict]) -> Dict[str, Any]:
    return _agg(_clean(rows))


def _build_stack(
    *,
    start: str,
    end: str,
    proven_rows: List[dict],
    pool: dict,
    prod2_all: List[dict],
    sessions_all: List[str],
) -> Dict[str, Any]:
    sess = sorted(d for d in sessions_all if start <= d <= end)
    proven = [
        dict(r, track="proven_100", priority=PRIORITY["proven_100"])
        for r in proven_rows
        if start <= str(r.get("day") or "") <= end
    ]
    champ = _champ_floor(
        [r for r in (pool.get("champion") or []) if start <= r["day"] <= end]
    )
    for r in champ:
        r["track"] = "champion"
        r["priority"] = PRIORITY["champion"]
    crown = [
        dict(r, track="crown_5m", priority=PRIORITY["crown_5m"])
        for r in (pool.get("crown_5m") or [])
        if start <= r["day"] <= end
    ]
    good = [
        dict(r, track="good_prod2", priority=PRIORITY["good_prod2"])
        for r in prod2_all
        if start <= r["day"] <= end
    ]
    daily = fs._load_daily()
    active = fs._active_days(sess, daily) if sess else set()
    crown_htf = [r for r in crown if r["day"] in active]
    stack = fs._union(
        {
            "proven_100": proven,
            "good_prod2": good,
            "champion": champ,
            "crown_5m": crown_htf,
        },
        day_cap=2,
    )
    return {
        "sess_n": len(sess),
        "stack": _clean(stack),
        "proven_n": len(proven),
        "tracks": _agg(_clean(stack)).get("by_track") or {},
    }


def main() -> int:
    t0 = time.time()
    print("RESEARCH proven 5m vs 15m (not live)", flush=True)

    dual = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    sessions_all, prod2_all, _ = fs._prod2(4000)

    proven15_all = list(dual["dual15"].get("proven_100") or [])
    proven5_all = list(dual["dual5"].get("proven_100") or [])
    # Live pool proven is the locked 15m channel (sanity baseline for stack)
    pool_proven = list(pool.get("proven_100") or [])

    lines = [
        "# RESEARCH — Proven 5m model vs locked Proven 15m",
        "",
        "**Status:** RESEARCH only · **not live** · does not change golden / P2F",
        "",
        "Question: what if volume-stack `proven_100` came from dual **5m** instead of dual **15m**?",
        "",
        "| Pack | Role today |",
        "|---|---|",
        "| `dual15.proven_100` | LIVE proven track (locked) |",
        "| `dual5.proven_100` | used in AGREE / D5 streams — **not** volume proven |",
        "| crown 5m / champ / good | unchanged in this swap test |",
        "",
    ]

    payload: Dict[str, Any] = {
        "status": "RESEARCH",
        "not_live": True,
        "question": "proven track from dual5 vs dual15",
        "windows": {},
    }

    for wname, (start, end) in WINDOWS.items():
        print(f"  window {wname} {start}→{end}", flush=True)
        p15 = _clip(proven15_all, start, end)
        p5 = _clip(proven5_all, start, end)
        s15 = _score(p15)
        s5 = _score(p5)

        base = _build_stack(
            start=start,
            end=end,
            proven_rows=pool_proven,
            pool=pool,
            prod2_all=prod2_all,
            sessions_all=sessions_all,
        )
        swap = _build_stack(
            start=start,
            end=end,
            proven_rows=proven5_all,
            pool=pool,
            prod2_all=prod2_all,
            sessions_all=sessions_all,
        )
        a_base = _agg(base["stack"])
        a_swap = _agg(swap["stack"])

        block = {
            "start": start,
            "end": end,
            "proven15_standalone": s15,
            "proven5_standalone": s5,
            "stack_baseline_proven15": {
                **a_base,
                "proven_n": base["proven_n"],
                "sess_n": base["sess_n"],
            },
            "stack_swap_proven5": {
                **a_swap,
                "proven_n": swap["proven_n"],
                "sess_n": swap["sess_n"],
            },
            "delta_stack_hit": None
            if a_base["hit_pct"] is None or a_swap["hit_pct"] is None
            else round(float(a_swap["hit_pct"]) - float(a_base["hit_pct"]), 2),
            "delta_stack_n": a_swap["n"] - a_base["n"],
        }
        payload["windows"][wname] = block

        lines.extend(
            [
                f"## {wname} (`{start}` → `{end}`)",
                "",
                "### Standalone proven_100",
                "",
                "| Source | N | Hit | W | L | Days |",
                "|---|---:|---:|---:|---:|---:|",
                f"| dual15 (locked) | {s15['n']} | {s15['hit_pct']} | {s15['wins']} | {s15['losses']} | {s15['days']} |",
                f"| dual5 (research) | {s5['n']} | {s5['hit_pct']} | {s5['wins']} | {s5['losses']} | {s5['days']} |",
                "",
                "### Volume stack (good/champ/crown HTF same; proven swapped)",
                "",
                "| Book | N | Hit | Proven N | Δhit vs baseline |",
                "|---|---:|---:|---:|---:|",
                f"| Baseline proven=15m (pool) | {a_base['n']} | {a_base['hit_pct']} | {base['proven_n']} | — |",
                f"| Swap proven=5m (dual5) | {a_swap['n']} | {a_swap['hit_pct']} | {swap['proven_n']} | {block['delta_stack_hit']} |",
                "",
            ]
        )

    # Verdict on golden (live lock window)
    g = payload["windows"]["golden_1y"]
    p5h = g["proven5_standalone"]["hit_pct"]
    keep15 = (
        g["proven15_standalone"]["hit_pct"] is not None
        and float(g["proven15_standalone"]["hit_pct"]) >= 95.0
        and (
            p5h is None
            or float(p5h) < float(g["proven15_standalone"]["hit_pct"]) - 5
            or g["proven5_standalone"]["n"] < g["proven15_standalone"]["n"] // 2
        )
    )
    verdict = (
        "KEEP dual15 proven for LIVE — dual5 proven is weaker / thinner on locked windows."
        if keep15
        else "REVIEW — dual5 proven competitive enough to dig deeper (still RESEARCH)."
    )
    payload["verdict"] = verdict
    payload["elapsed_s"] = round(time.time() - t0, 1)

    lines.extend(
        [
            "## Verdict",
            "",
            verdict,
            "",
            f"Elapsed {payload['elapsed_s']}s",
            "",
        ]
    )

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "RESEARCH_PROVEN_5M_VS_15M.md"
    js = OUT / "RESEARCH_PROVEN_5M_VS_15M.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
