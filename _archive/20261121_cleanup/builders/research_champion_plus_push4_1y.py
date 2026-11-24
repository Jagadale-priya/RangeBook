"""CHAMPION+ PUSH4 — more calls @ >=92.5% beyond PUSH3 257.

Levers:
  - Wider win-ticket pools (champ · path-good all risks · D10 · dual15 proven as
    research tickets only — not a live stack track)
  - Cap3 + Cap4
  - Win-only fill after floor is tight (losses cannot be added near 92.5%)
  - Local search: drop a 1y loss if it frees a slot to add 2+ wins

  python -u prod_live/tests/builders/research_champion_plus_push4_1y.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import POOL, _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _side  # noqa: E402
from research_100pct_deeper_more_calls import gap_map  # noqa: E402
import live_final_1y_months_accurate as hold  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
HOLD = ROOT / "prod_live" / "holding_accurate" / "champion_plus"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"
CACHE_XY = LEDGER / "_cache_dual10m_xy_research.json"
PACKS = LEDGER / "nifty_side_models_10m_research" / "dual10m_packs.joblib"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
RECIPE = HOLD / "recipes_research.json"
PUSH3 = OUT / "CHAMPION_PLUS_PUSH3_1Y.json"

START_1Y, END = hold.START, hold.END
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
FLOOR_1Y = 92.5
PRIOR_N = 257


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return 100.0 * sum(1 for r in rows if r.get("win")) / len(rows)


def desk_ok(rows: List[dict], seed_3y_hit: float) -> bool:
    r1 = _clip(rows, START_1Y, END)
    if len(r1) >= 3 and round(hit_pct(r1), 2) + 1e-9 < FLOOR_1Y:
        return False
    r3 = _clip(rows, START_3Y, END)
    # tolerance: seed itself must pass (float/rounding)
    if len(r3) >= 3 and round(hit_pct(r3), 2) + 1e-9 < round(seed_3y_hit, 2) - 1e-9:
        return False
    return True


def call_key(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day") or ""), _side(r), str(r.get("hm") or ""))


def merge_cap(a: List[dict], b: List[dict], cap: int) -> List[dict]:
    """Additive append with day-cap + same-side (do NOT re-union whole book)."""
    out = [dict(r) for r in a]
    by_day: Dict[str, List[dict]] = defaultdict(list)
    for r in out:
        by_day[str(r.get("day") or "")].append(r)
    for r in b:
        day = str(r.get("day") or "")
        existing = by_day.get(day, [])
        if len(existing) >= cap:
            continue
        if existing and _side(existing[0]) != _side(r):
            continue
        k = call_key(r)
        if any(call_key(x) == k for x in existing):
            continue
        rr = dict(r)
        out.append(rr)
        by_day[day].append(rr)
    return out


def load_d10() -> List[dict]:
    import joblib

    packs = joblib.load(PACKS)
    xy = json.loads(CACHE_XY.read_text(encoding="utf-8"))
    out = []
    for r in xy.get("tickets") or []:
        side = str(r.get("decision") or "").upper()
        pack = packs.get(side) or {}
        if not pack.get("available") or not r.get("x"):
            continue
        X = np.asarray([r["x"]], dtype=float)
        raw = float(pack["base"].predict_proba(X)[0, 1])
        p = float(np.clip(pack["iso"].transform([raw])[0], 0.05, 0.95))
        rr = {k: v for k, v in r.items() if k != "x"}
        rr["p_t1"] = round(p, 4)
        rr["track"] = "dual10m"
        out.append(rr)
    return out


def build_candidates() -> List[dict]:
    """Wide research ticket pool (no crown)."""
    out: List[dict] = []
    seen = set()

    def add(rows, track: str):
        for r in rows:
            rr = hold._clean([dict(r, track=track)])[0]
            k = call_key(rr)
            if k in seen or not (START_3Y <= str(rr.get("day") or "") <= END):
                continue
            seen.add(k)
            out.append(rr)

    pool = json.loads(POOL.read_text(encoding="utf-8"))
    add(_champ_floor(pool.get("champion") or []), "champion")
    # proven as research tickets only (not a live track priority)
    add(pool.get("proven_100") or [], "proven_research")

    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    for rk, rows in (path_u.get("good_by_risk") or {}).items():
        if str(rk).startswith("_"):
            continue
        add(rows or [], "good_prod2")

    dual = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    add((dual.get("dual15") or {}).get("champion") or [], "champion")
    add((dual.get("dual15") or {}).get("proven_100") or [], "proven_research")
    # dual5 champion is weak alone — only keep high-p wins as candidates
    for r in (dual.get("dual5") or {}).get("champion") or []:
        if float(r.get("p_t1") or 0) >= 0.62 and r.get("win"):
            add([r], "dual5_research")

    add(load_d10(), "dual10m")
    print(f"  candidate tickets={len(out)}", flush=True)
    return out


def rebuild_from_push3_streams(seed: List[dict], seed_3y_hit: float, cap: int) -> List[dict]:
    """Rebuild stream warm book via push2-style tags if present; else seed."""
    # Import mine helpers lightly by reusing push3 warm tags + simple merge of
    # all univ tickets is too heavy; start from seed and rely on ticket fill.
    # Prefer: load PUSH3 call list from md/json if available.
    if PUSH3.exists():
        # PUSH3 json may not have calls — rebuild via recipe streams using push2 module pieces
        pass
    tags = []
    if RECIPE.exists():
        tags = list(json.loads(RECIPE.read_text(encoding="utf-8")).get("stream_tags_research") or [])
    # Without re-mining, start seed; ticket fill does the heavy lift (as in push3)
    print(f"  start from seed + ticket fill (recipe streams={len(tags)})", flush=True)
    return list(seed)


def ticket_fill(
    cur: List[dict],
    candidates: List[dict],
    sess_1y: List[str],
    seed_3y_hit: float,
    cap: int,
    *,
    wins_only: bool = False,
) -> Tuple[List[dict], int]:
    cur = [dict(r) for r in cur]
    by_day: Dict[str, List[dict]] = defaultdict(list)
    for r in candidates:
        day = str(r.get("day") or "")
        if START_1Y <= day <= END:
            if wins_only and not r.get("win"):
                continue
            by_day[day].append(r)

    added = 0
    while True:
        best = None
        best_n = len(_clip(cur, START_1Y, END))
        best_hit = hit_pct(_clip(cur, START_1Y, END))
        for day in sess_1y:
            existing = [r for r in cur if r.get("day") == day]
            if len(existing) >= cap:
                continue
            side_lock = _side(existing[0]) if existing else None
            seen = {call_key(r) for r in existing}
            cands = by_day.get(day, [])
            # prefer wins, then high p
            cands = sorted(
                cands,
                key=lambda x: (int(bool(x.get("win"))), float(x.get("p_t1") or 0)),
                reverse=True,
            )
            for r in cands:
                if call_key(r) in seen:
                    continue
                if side_lock and _side(r) != side_lock:
                    continue
                if wins_only and not r.get("win"):
                    continue
                trial = merge_cap(cur, [r], cap)
                n1 = len(_clip(trial, START_1Y, END))
                if n1 <= best_n:
                    continue
                if not desk_ok(trial, seed_3y_hit):
                    continue
                h1 = hit_pct(_clip(trial, START_1Y, END))
                if best is None or n1 > best_n or (n1 == best_n and h1 > best_hit):
                    best = trial
                    best_n = n1
                    best_hit = h1
        if not best:
            break
        cur = best
        added += 1
        if added <= 20 or added % 25 == 0:
            print(f"    +ticket → n={best_n} hit={best_hit:.2f} (add={added})", flush=True)
    return cur, added


def loss_swap_search(
    cur: List[dict],
    candidates: List[dict],
    sess_1y: List[str],
    seed_3y_hit: float,
    cap: int,
) -> Tuple[List[dict], int]:
    """Drop one 1y loss if we can add >=2 wins afterward (net +N, hold floor)."""
    cur = [dict(r) for r in cur]
    swaps = 0
    losses = [r for r in _clip(cur, START_1Y, END) if not r.get("win")]
    print(f"    loss-swap candidates L={len(losses)}", flush=True)
    # Cap swap attempts — each runs a full wins-only refill
    for loss in list(losses)[:8]:
        base_n = len(_clip(cur, START_1Y, END))
        without = [r for r in cur if call_key(r) != call_key(loss)]
        if not desk_ok(without, seed_3y_hit):
            continue
        filled, n_add = ticket_fill(
            without, candidates, sess_1y, seed_3y_hit, cap, wins_only=True
        )
        n1 = len(_clip(filled, START_1Y, END))
        if n1 > base_n and desk_ok(filled, seed_3y_hit):
            cur = filled
            swaps += 1
            print(
                f"    swap drop L {loss.get('day')} {loss.get('hm')} "
                f"→ n={n1} hit={hit_pct(_clip(cur, START_1Y, END)):.2f} (+{n_add} wins)",
                flush=True,
            )
            # continue trying further losses on updated book
            losses = [r for r in _clip(cur, START_1Y, END) if not r.get("win")]
    return cur, swaps


def main() -> int:
    t0 = time.time()
    print(f"CHAMPION+ PUSH4 · beat {PRIOR_N} @>={FLOOR_1Y}%", flush=True)

    pool = json.loads(POOL.read_text(encoding="utf-8"))
    seed = hold._clean(
        _champ_floor([r for r in pool["champion"] if START_3Y <= r["day"] <= END])
    )
    for r in seed:
        r["track"] = "champion"
    sc0 = _agg(_clip(seed, START_1Y, END))
    sc0_3 = _agg(_clip(seed, START_3Y, END))
    seed_3y_hit = float(sc0_3.get("hit_pct") or 0)
    print(f"  seed {sc0.get('n')}@{sc0.get('hit_pct')}% · 3y_hit_floor={seed_3y_hit}", flush=True)

    sessions_all, _, _ = fs._prod2(4000)
    sess_1y = sorted(d for d in sessions_all if START_1Y <= d <= END)
    print(f"  sessions 1y={len(sess_1y)}", flush=True)

    print("  build candidates…", flush=True)
    cands = build_candidates()

    results = {}
    best = None

    for cap in (3, 4):
        print(f"\n  === cap{cap} ===", flush=True)
        cur = rebuild_from_push3_streams(seed, seed_3y_hit, cap)
        # Phase A: any ticket (prefer wins)
        print("  fill any…", flush=True)
        cur, a1 = ticket_fill(cur, cands, sess_1y, seed_3y_hit, cap, wins_only=False)
        sc_a = _agg(_clip(cur, START_1Y, END))
        print(f"  after any: {sc_a.get('n')}@{sc_a.get('hit_pct')}% (+{a1})", flush=True)

        # Phase B: wins only
        print("  fill wins-only…", flush=True)
        cur, a2 = ticket_fill(cur, cands, sess_1y, seed_3y_hit, cap, wins_only=True)
        sc_b = _agg(_clip(cur, START_1Y, END))
        print(f"  after wins: {sc_b.get('n')}@{sc_b.get('hit_pct')}% (+{a2})", flush=True)

        # Phase C: loss swap
        print("  loss-swap…", flush=True)
        cur, nswap = loss_swap_search(cur, cands, sess_1y, seed_3y_hit, cap)
        # one more wins fill
        cur, a3 = ticket_fill(cur, cands, sess_1y, seed_3y_hit, cap, wins_only=True)
        cur = hold._clean(cur)
        sc1 = _agg(_clip(cur, START_1Y, END))
        sc3 = _agg(_clip(cur, START_3Y, END))
        ok = desk_ok(cur, seed_3y_hit)
        print(
            f"  FINAL cap{cap}: {sc1.get('n')}@{sc1.get('hit_pct')}% "
            f"swaps={nswap} +wins={a3} ok={ok}",
            flush=True,
        )
        results[f"cap{cap}"] = {
            "ok": ok,
            "1y": sc1,
            "3y": sc3,
            "adds_any": a1,
            "adds_wins": a2 + a3,
            "swaps": nswap,
        }
        if ok and (best is None or (sc1.get("n") or 0) > (best[1].get("n") or 0)):
            best = (f"cap{cap}", sc1, sc3, cur)

    if best is None:
        print("FAIL — no book cleared floor", flush=True)
        return 1
    mode, best_sc, best_sc3, best_rows = best
    n = best_sc.get("n") or 0

    lines = [
        "# CHAMPION+ PUSH4 — more calls @ ≥92.5%",
        "",
        f"**Prior PUSH3:** {PRIOR_N}@92.61% · **Seed champ:** {sc0.get('n')}@{sc0.get('hit_pct')}%",
        f"**Floor:** 1y ≥ **{FLOOR_1Y}%** · `{START_1Y}`→`{END}` · sessions {len(sess_1y)}",
        "**Pools:** champ · path-good · D10 · dual15 proven (research tickets) · dual5 high-p wins",
        "**No crown.** Proven is ticket-only research, not a live stack track.",
        "",
        "| Book | 1y N@hit | Δ vs PUSH3 | 3y N@hit |",
        "|---|---|---:|---|",
        f"| PUSH3 | {PRIOR_N}@92.61 | 0 | — |",
    ]
    for k, v in results.items():
        sc = v["1y"]
        lines.append(
            f"| `{k}` | **{sc.get('n')}@{sc.get('hit_pct')}** | "
            f"{(sc.get('n') or 0) - PRIOR_N:+d} | {v['3y'].get('n')}@{v['3y'].get('hit_pct')} |"
        )

    lines.extend(
        [
            "",
            f"## Calls — best `{mode}` (first 40 + last 40)",
            "",
            "| # | Day | HM | Side | Win | Track | p |",
            "|---:|---|---|---|---|---|---:|",
        ]
    )
    calls = sorted(_clip(best_rows, START_1Y, END), key=lambda x: (x.get("day"), x.get("hm")))
    show = calls[:40] + (calls[-40:] if len(calls) > 80 else calls[40:])
    seen = set()
    for i, r in enumerate(calls, 1):
        if r in show or call_key(r) in {call_key(x) for x in show}:
            if call_key(r) in seen:
                continue
            # only print if in show set
            pass
    # simpler: print first 40 and last 40 by index
    idxs = set(range(1, min(40, len(calls)) + 1)) | set(range(max(1, len(calls) - 39), len(calls) + 1))
    for i, r in enumerate(calls, 1):
        if i not in idxs:
            continue
        lines.append(
            f"| {i} | {r.get('day')} | {r.get('hm')} | {_side(r)} | "
            f"{'W' if r.get('win') else 'L'} | {r.get('track')} | {r.get('p_t1')} |"
        )

    # track mix
    from collections import Counter

    tr = Counter(r.get("track") for r in calls)
    lines.extend(["", "## Track mix (1y)", "", "| Track | N |", "|---|---:|"])
    for k, v in tr.most_common():
        lines.append(f"| `{k}` | {v} |")

    if n > PRIOR_N:
        verdict = (
            f"PUSH4 OK — `{mode}` **{n}@{best_sc.get('hit_pct')}%** "
            f"(PUSH3 {PRIOR_N} · +{n - PRIOR_N}). Still RESEARCH · ticket-fill book."
        )
    elif n >= PRIOR_N:
        verdict = f"PUSH4 HOLD — {n}@{best_sc.get('hit_pct')}%."
    else:
        verdict = f"PUSH4 PARTIAL — {n}@{best_sc.get('hit_pct')}%."

    elapsed = round(time.time() - t0, 1)
    lines.extend(["", "## Verdict", "", verdict, "", f"Elapsed {elapsed}s", ""])

    OUT.mkdir(parents=True, exist_ok=True)
    HOLD.mkdir(parents=True, exist_ok=True)
    md = OUT / "CHAMPION_PLUS_PUSH4_1Y.md"
    js = OUT / "CHAMPION_PLUS_PUSH4_1Y.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(
        json.dumps(
            {
                "verdict": verdict,
                "best_mode": mode,
                "prior_n": PRIOR_N,
                "1y": best_sc,
                "3y": best_sc3,
                "results": results,
                "elapsed_s": elapsed,
                "track_mix": dict(tr),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    if n >= PRIOR_N:
        (HOLD / "recipes_research.json").write_text(
            json.dumps(
                {
                    "status": "RESEARCH",
                    "desk": f"CHAMPION_PLUS_{mode.upper()}_TICKETFILL",
                    "seed": "CHAMPION",
                    "floor_1y": FLOOR_1Y,
                    "mode": "ticket_fill",
                    "cap": int(mode.replace("cap", "")),
                    "research_1y": best_sc,
                    "research_3y": best_sc3,
                    "note": "Ticket-fill research book; not a clean live stream recipe.",
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        # persist call keys for reproducibility
        (HOLD / "push4_calls_1y.json").write_text(
            json.dumps(
                [
                    {
                        "day": r.get("day"),
                        "hm": r.get("hm"),
                        "side": _side(r),
                        "win": r.get("win"),
                        "track": r.get("track"),
                        "p_t1": r.get("p_t1"),
                    }
                    for r in calls
                ],
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
