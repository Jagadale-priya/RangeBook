"""NIFTY deep research — maximize calls at 100% accuracy on last 6 months.

Same live candidate family as Cap6 (cache → path settle ±30 on 5m).
Gates are causal only (no win hindsight). Objective: max N subject to hit=100%.

Also:
  · Cap6 baseline on same 6m
  · Prior ACC100 Cap1 lock measured on 6m
  · Walk-forward: tune on first 4m, hold out last 2m
  · Among 100% books, prefer higher N (multi-lot friendly)

  python -u prod_live/tests/builders/research_nifty_acc100_more_calls_6m.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
import path_setup  # noqa: F401,E402

from prod_live.logic import champ_plus_engine as eng  # noqa: E402
from research_100pct_deeper_more_calls import _norm, build_bar_index  # noqa: E402
from research_nifty_sensex_100pct_last20 import (  # noqa: E402
    agg,
    apply_gate,
    fill,
    gate_from_row,
    key,
    side,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "NIFTY_ACC100_MORE_CALLS_6M.md"
OUT_JSON = OUT / "NIFTY_ACC100_MORE_CALLS_6M.json"
LOCK_IN = ROOT / "prod_live" / "holding_accurate" / "acc100_last20_locks.json"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
CAP6_JSON = (
    ROOT / "prod_live" / "holding_accurate" / "champion_plus" / "t30_sl30_5y_calls.json"
)

T1 = SL = 30.0
END = datetime.now().date().isoformat()
START_6M = (pd.Timestamp(END) - pd.DateOffset(months=6)).date().isoformat()


def build_live_pool(days: Sequence[str]) -> List[dict]:
    """Full live-family candidates for days, settled on 5m (same as Cap6 research)."""
    bars = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    hm = bars.index.strftime("%H:%M")
    bars = bars[(hm >= "09:15") & (hm <= "15:30")]
    ix = build_bar_index(bars)

    pool: List[dict] = []
    seen: Set[Tuple[str, str, str]] = set()
    for i, day in enumerate(days, 1):
        cands = eng._load_cache_candidates_for_day(day)
        scored = eng.score_candidates(cands)
        for r in scored:
            if r.get("track") == "champion" and not eng._champ_floor_ok(r):
                continue
            sd = side(r)
            if sd not in ("BUY", "SELL"):
                continue
            if r.get("win") is None and r.get("entry") is None:
                continue
            # Ensure tape settle when win missing
            if r.get("win") is None:
                s = eng.path_score_one(bars, ix, day, str(r.get("hm") or ""), sd)
                if not s:
                    continue
                r = dict(r)
                r.update(s)
            k = key(r)
            if k in seen:
                continue
            seen.add(k)
            rr = dict(r)
            rr["decision"] = sd
            rr["side"] = sd
            rr["day"] = day
            rr["hm"] = str(r.get("hm") or "")[:5]
            rr["p_t1"] = float(r.get("p_t1") or 0)
            rr["track"] = str(r.get("track") or "")
            if r.get("or_ext") is not None:
                try:
                    rr["or_ext"] = float(r["or_ext"])
                except Exception:
                    rr["or_ext"] = None
            else:
                rr["or_ext"] = None
            fb = r.get("first_break")
            rr["first_break"] = bool(fb) if fb is not None else None
            pool.append(rr)
        if i % 20 == 0 or i == len(days):
            print(f"  pool days {i}/{len(days)} n={len(pool)}", flush=True)
    return pool


def clip(rows: List[dict], a: str, b: str) -> List[dict]:
    return [r for r in rows if a <= str(r.get("day") or "")[:10] <= b]


def sessions(rows: List[dict]) -> List[str]:
    return sorted({str(r.get("day") or "")[:10] for r in rows})


def _eval_gate(
    pool: List[dict],
    *,
    cap: int,
    pmin: float,
    tracks: Optional[Set[str]],
    hm_lo: Optional[str],
    hm_hi: Optional[str],
    max_or: Optional[float],
    first_only: bool,
    sides: Optional[Set[str]],
    buy_p: Optional[float],
    sell_p: Optional[float],
    min_n: int,
    t1: float = T1,
    sl: float = SL,
) -> Optional[dict]:
    book = fill(
        pool,
        cap,
        pmin=pmin,
        tracks=tracks,
        hm_lo=hm_lo,
        hm_hi=hm_hi,
        buy_p=buy_p,
        sell_p=sell_p,
        max_or_ext=max_or,
        first_only=first_only,
        sides=sides,
    )
    st = agg(book, t1=t1, sl=sl)
    if not st["n"] or st["n"] < min_n:
        return None
    return {
        "cap": cap,
        "pmin": pmin,
        "tracks": sorted(tracks) if tracks else "ALL",
        "hm_lo": hm_lo or "*",
        "hm_hi": hm_hi or "*",
        "max_or_ext": max_or,
        "first_only": first_only,
        "sides": sorted(sides) if sides else "BOTH",
        "buy_p": buy_p,
        "sell_p": sell_p,
        **st,
    }


def deep_search(
    pool: List[dict], *, min_n: int = 5, t1: float = T1, sl: float = SL
) -> List[dict]:
    """Phased search — find 100% cores, then push Cap/N higher."""
    tracks_opts: List[Optional[Set[str]]] = [
        None,
        {"champion"},
        {"proven_research"},
        {"good_prod2"},
        {"champion", "proven_research"},
        {"champion", "good_prod2"},
        {"champion", "good_prod2", "proven_research"},
        {"champion", "proven_research", "dual10m"},
        {"champion", "good_prod2", "proven_research", "dual10m"},
        {"proven_research", "good_prod2"},
        {"dual10m", "champion"},
    ]
    pmins = [0.55, 0.58, 0.60, 0.62, 0.65, 0.70, 0.75, 0.80]
    hm_windows = [
        (None, None),
        ("09:30", "14:30"),
        ("09:45", "13:30"),
        ("09:45", "14:00"),
        ("10:00", "14:00"),
        ("10:00", "13:00"),
        ("09:45", "12:30"),
        ("11:00", "14:00"),
    ]
    or_exts: List[Optional[float]] = [None, 0.10, 0.15, 0.20, 0.30]
    first_opts = [False, True]
    side_opts: List[Optional[Set[str]]] = [None, {"BUY"}, {"SELL"}]
    buy_sell_floors = [
        (None, None),
        (0.55, 0.62),
        (0.58, 0.62),
        (0.60, 0.65),
        (0.62, 0.70),
    ]

    results: List[dict] = []
    seen_keys: Set[Tuple] = set()

    def add_row(row: Optional[dict]) -> None:
        if not row:
            return
        k = (
            row["cap"],
            row["pmin"],
            tuple(row["tracks"]) if isinstance(row["tracks"], list) else row["tracks"],
            row["hm_lo"],
            row["hm_hi"],
            row["max_or_ext"],
            row["first_only"],
            tuple(row["sides"]) if isinstance(row["sides"], list) else row["sides"],
            row["buy_p"],
            row["sell_p"],
        )
        if k in seen_keys:
            return
        seen_keys.add(k)
        results.append(row)

    # Phase 1 — Cap1 cores (accuracy)
    print("  phase1 Cap1…", flush=True)
    for pmin in pmins:
        for tracks in tracks_opts:
            for hm_lo, hm_hi in hm_windows:
                for max_or in or_exts:
                    for first_only in first_opts:
                        for sides in side_opts:
                            for buy_p, sell_p in buy_sell_floors:
                                add_row(
                                    _eval_gate(
                                        pool,
                                        cap=1,
                                        pmin=pmin,
                                        tracks=tracks,
                                        hm_lo=hm_lo,
                                        hm_hi=hm_hi,
                                        max_or=max_or,
                                        first_only=first_only,
                                        sides=sides,
                                        buy_p=buy_p,
                                        sell_p=sell_p,
                                        min_n=min_n,
                                        t1=t1,
                                        sl=sl,
                                    )
                                )

    perfect_cores = [
        r for r in results if (r.get("hit_pct") or 0) >= 99.999
    ]
    print(f"  phase1 perfect cores={len(perfect_cores)} / rows={len(results)}", flush=True)

    # Phase 2 — raise Cap on perfect Cap1 cores (more calls/day)
    print("  phase2 Cap2–4 on perfect cores…", flush=True)
    for core in perfect_cores:
        tracks = None if core["tracks"] == "ALL" else set(core["tracks"])
        sides = None if core["sides"] == "BOTH" else set(core["sides"])
        hm_lo = None if core["hm_lo"] == "*" else core["hm_lo"]
        hm_hi = None if core["hm_hi"] == "*" else core["hm_hi"]
        for cap in (2, 3, 4):
            add_row(
                _eval_gate(
                    pool,
                    cap=cap,
                    pmin=float(core["pmin"]),
                    tracks=tracks,
                    hm_lo=hm_lo,
                    hm_hi=hm_hi,
                    max_or=core["max_or_ext"],
                    first_only=bool(core["first_only"]),
                    sides=sides,
                    buy_p=core["buy_p"],
                    sell_p=core["sell_p"],
                    min_n=min_n,
                    t1=t1,
                    sl=sl,
                )
            )

    # Phase 3 — densify: slightly lower p / widen hm on top perfect Cap≥2 survivors
    print("  phase3 densify around top perfect…", flush=True)
    perfect_all = [r for r in results if (r.get("hit_pct") or 0) >= 99.999]
    perfect_all.sort(key=lambda x: (-x["n"], -x["points"]))
    for core in perfect_all[:40]:
        tracks = None if core["tracks"] == "ALL" else set(core["tracks"])
        sides = None if core["sides"] == "BOTH" else set(core["sides"])
        hm_lo = None if core["hm_lo"] == "*" else core["hm_lo"]
        hm_hi = None if core["hm_hi"] == "*" else core["hm_hi"]
        for pmin in sorted({float(core["pmin"]), max(0.50, float(core["pmin"]) - 0.03), max(0.50, float(core["pmin"]) - 0.05)}):
            for cap in (1, 2, 3, 4):
                for hm2 in (
                    (hm_lo, hm_hi),
                    ("09:30", "14:30"),
                    ("09:45", "14:00"),
                    ("10:00", "14:00"),
                    (None, None),
                ):
                    add_row(
                        _eval_gate(
                            pool,
                            cap=cap,
                            pmin=pmin,
                            tracks=tracks,
                            hm_lo=hm2[0],
                            hm_hi=hm2[1],
                            max_or=core["max_or_ext"],
                            first_only=bool(core["first_only"]),
                            sides=sides,
                            buy_p=core["buy_p"],
                            sell_p=core["sell_p"],
                            min_n=min_n,
                            t1=t1,
                            sl=sl,
                        )
                    )

    results.sort(
        key=lambda x: (
            0 if (x.get("hit_pct") or 0) >= 99.999 else 1,
            -(x.get("hit_pct") or 0),
            -x["n"],
            -x["points"],
        )
    )
    return results


def densest_100(results: List[dict], *, min_n: int = 5) -> Optional[dict]:
    perfect = [r for r in results if (r.get("hit_pct") or 0) >= 99.999 and r["n"] >= min_n]
    if not perfect:
        return None
    perfect.sort(key=lambda x: (-x["n"], -x["points"], x["cap"]))
    return perfect[0]


def prior_lock_gate() -> Dict[str, Any]:
    if LOCK_IN.exists():
        d = json.loads(LOCK_IN.read_text(encoding="utf-8"))
        g = (d.get("nifty") or {}).get("gate") or {}
        tracks = g.get("tracks")
        return {
            "cap": int(g.get("cap") or 1),
            "pmin": float(g.get("pmin") or 0.55),
            "tracks": set(tracks) if isinstance(tracks, list) else None,
            "hm_lo": g.get("hm_lo"),
            "hm_hi": g.get("hm_hi"),
            "max_or_ext": g.get("max_or_ext"),
            "first_only": bool(g.get("first_only")),
            "sides": None,
            "buy_p": g.get("buy_p"),
            "sell_p": g.get("sell_p"),
        }
    return {
        "cap": 1,
        "pmin": 0.55,
        "tracks": {"champion", "good_prod2", "proven_research"},
        "hm_lo": "09:45",
        "hm_hi": "13:30",
        "max_or_ext": None,
        "first_only": False,
        "sides": None,
        "buy_p": None,
        "sell_p": None,
    }


def cap6_baseline(pool: List[dict]) -> Dict[str, Any]:
    g = {
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
    return apply_gate(pool, g, t1=T1, sl=SL)


def write_report(payload: dict) -> None:
    b6 = payload["baseline_cap6_6m"]
    prior = payload["prior_lock_6m"]
    best = payload.get("densest_100_6m") or {}
    wf = payload.get("walk_forward") or {}
    lines = [
        "# NIFTY · ACC100 more calls · last 6 months (deep)",
        "",
        f"**Generated:** `{payload['generated']}`",
        f"**Window:** `{payload['start']}` → `{payload['end']}` · {payload['n_sessions']} sessions",
        "",
        "## Method",
        "",
        "- Live candidate family (champion / proven / good_prod2 / dual10m / crown) · path settle ±30 on 5m",
        "- Causal gates only — **never** filter on `win`",
        "- Goal: **max N @ 100% hit** on 6m (multi-lot OK)",
        "- Walk-forward: tune on first ~4m · hold out last ~2m",
        "",
        "## Headline",
        "",
        f"- Cap6 live-style baseline 6m: **{b6.get('n')} @ {b6.get('hit_pct')}%**",
        f"- Prior ACC100 Cap1 lock on 6m: **{prior.get('n')} @ {prior.get('hit_pct')}%**",
    ]
    if best.get("last20") or best.get("stats"):
        st = best.get("stats") or best.get("last20") or {}
        lines.append(
            f"- **Densest 100% on 6m:** **{st.get('n')} @ {st.get('hit_pct')}%** "
            f"(W/L {st.get('wins')}/{st.get('losses')}, pts {st.get('points')})"
        )
        lines.append(f"- Gate: `{best.get('gate_str')}`")
    if wf:
        lines.append(
            f"- Walk-forward holdout: train `{wf.get('train_stats')}` → "
            f"test `{wf.get('test_stats')}`"
        )
    lines += ["", "## Densest 100% gates on 6m (top 15 by N)", "", 
              "| N | Hit | Cap | pmin | Tracks | HM | or≤ | first | sides | buy/sell | Pts |",
              "|---:|---:|---:|---:|---|---|---:|---|---|---|---:|"]
    for r in payload.get("top_perfect_6m") or []:
        lines.append(
            f"| {r['n']} | **{r['hit_pct']}** | {r['cap']} | {r['pmin']} | {r['tracks']} | "
            f"{r['hm_lo']}-{r['hm_hi']} | {r['max_or_ext']} | {r['first_only']} | "
            f"{r['sides']} | {r['buy_p']}/{r['sell_p']} | {r['points']} |"
        )
    if best.get("calls"):
        lines += [
            "",
            "## Densest-100 calls (6m)",
            "",
            "| Day | HM | Side | p | Track | Win | Pts |",
            "|---|---|---|---:|---|---|---:|",
        ]
        for c in best["calls"]:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['side']} | {c['p_t1']} | {c['track']} | "
                f"{'W' if c['win'] else 'L'} | {c['points']} |"
            )
    if wf.get("test_calls") is not None:
        lines += [
            "",
            "## Walk-forward test calls (last ~2m holdout)",
            "",
            f"Train gate: `{wf.get('gate_str')}`",
            f"Test: `{wf.get('test_stats')}`",
            "",
            "| Day | HM | Side | p | Track | Win | Pts |",
            "|---|---|---|---:|---|---|---:|",
        ]
        for c in wf.get("test_calls") or []:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['side']} | {c['p_t1']} | {c['track']} | "
                f"{'W' if c['win'] else 'L'} | {c['points']} |"
            )
    lines += [
        "",
        "## Recommendation",
        "",
        "1. If densest-100 N ≫ prior Cap1 lock and walk-forward test stays 100% → promote that gate.",
        "2. If walk-forward test slips below 100% → keep prior Cap1 lock (honest sparse 100%).",
        "3. Cap6 stays volume mode — not the accuracy desk.",
        "",
        f"JSON: `{OUT_JSON}`",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    t0 = time.time()
    print(f"NIFTY ACC100 more calls · 6m {START_6M}→{END}", flush=True)
    bars = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    hm = bars.index.strftime("%H:%M")
    bars = bars[(hm >= "09:15") & (hm <= "15:30")]
    days_tape = sorted({str(t.date()) for t in bars.index if START_6M <= str(t.date()) <= END})
    print(f"tape sessions in 6m: {len(days_tape)}", flush=True)

    print("building live candidate pool…", flush=True)
    pool = build_live_pool(days_tape)
    pool = [r for r in pool if r.get("win") is not None]
    print(f"settled pool={len(pool)} · {agg(pool, t1=T1, sl=SL)}", flush=True)

    base = cap6_baseline(pool)
    print(f"Cap6 baseline: n={base['n']} hit={base['hit_pct']}%", flush=True)

    prior_g = prior_lock_gate()
    prior = apply_gate(pool, prior_g, t1=T1, sl=SL)
    print(f"Prior ACC100 lock on 6m: n={prior['n']} hit={prior['hit_pct']}%", flush=True)

    print("deep gate search on 6m…", flush=True)
    t1 = time.time()
    results = deep_search(pool, min_n=5)
    print(f"  grid rows={len(results)} in {time.time()-t1:.1f}s", flush=True)
    perfect = [r for r in results if (r.get("hit_pct") or 0) >= 99.999]
    perfect.sort(key=lambda x: (-x["n"], -x["points"]))
    print(f"  perfect 100% books: {len(perfect)}", flush=True)
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
        print(
            f"DENSEST 100%: n={book['n']} hit={book['hit_pct']}% pts={book['points']}",
            flush=True,
        )

    # Walk-forward: first 4 months train / last 2 months test
    split = (pd.Timestamp(END) - pd.DateOffset(months=2)).date().isoformat()
    train = clip(pool, START_6M, split)
    test = clip(pool, split, END)
    # exclude split day from both double-count — test starts day after split
    test = [r for r in test if str(r.get("day") or "")[:10] > split]
    print(
        f"walk-forward train≤{split} n={len(train)} · test>{split} n={len(test)}",
        flush=True,
    )
    wf: Dict[str, Any] = {}
    if train and test:
        train_res = deep_search(train, min_n=5)
        train_best = densest_100(train_res, min_n=5)
        if train_best:
            g = gate_from_row(train_best)
            tr = apply_gate(train, g, t1=T1, sl=SL)
            te = apply_gate(test, g, t1=T1, sl=SL)
            wf = {
                "split": split,
                "gate": {k: (sorted(v) if isinstance(v, set) else v) for k, v in g.items()},
                "gate_str": densest.get("gate_str")
                if densest.get("gate") == {k: (sorted(v) if isinstance(v, set) else v) for k, v in g.items()}
                else (
                    f"cap={g['cap']} p≥{g['pmin']} tracks={g['tracks']} "
                    f"hm={g['hm_lo']}-{g['hm_hi']} or≤{g['max_or_ext']} "
                    f"first={g['first_only']} sides={g['sides']} "
                    f"buy/sell={g['buy_p']}/{g['sell_p']}"
                ),
                "train_stats": {k: tr[k] for k in tr if k != "calls"},
                "test_stats": {k: te[k] for k in te if k != "calls"},
                "test_calls": te.get("calls"),
                "train_hit_row": train_best,
            }
            print(
                f"WF train {tr['n']}@{tr['hit_pct']}% → test {te['n']}@{te['hit_pct']}%",
                flush=True,
            )

    # Also measure densest-100 gate on last20 inside 6m
    last20_days = sessions(pool)[-20:]
    last20_pool = [r for r in pool if str(r.get("day") or "")[:10] in set(last20_days)]
    last20_meas = None
    if densest.get("gate"):
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
        last20_meas = {
            k: v
            for k, v in apply_gate(last20_pool, g2, t1=T1, sl=SL).items()
            if k != "calls"
        }

    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "start": START_6M,
        "end": END,
        "n_sessions": len(days_tape),
        "pool_n": len(pool),
        "baseline_cap6_6m": {k: base[k] for k in base if k != "calls"},
        "prior_lock_6m": {k: prior[k] for k in prior if k != "calls"},
        "prior_lock_gate": {
            k: (sorted(v) if isinstance(v, set) else v) for k, v in prior_g.items()
        },
        "densest_100_6m": densest,
        "densest_100_on_last20": last20_meas,
        "top_perfect_6m": perfect[:15],
        "near_perfect_ge95": [
            r for r in results if (r.get("hit_pct") or 0) >= 95 and r["n"] >= 15
        ][:15],
        "walk_forward": wf,
        "elapsed_s": round(time.time() - t0, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    write_report(payload)
    print(f"Wrote {OUT_MD}", flush=True)
    print(f"Wrote {OUT_JSON}", flush=True)
    print(f"Elapsed {time.time()-t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
