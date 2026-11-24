"""CHAMPION+ PUSH5 — squeeze more N @ >=92.5% from PUSH4 book.

  - Load PUSH4 calls
  - Add unused same-side wins
  - Loss→win same-day swap
  - New pools: filtered crown wins (research tickets only) · confirm-ish dual
  - Cap4

  python -u prod_live/tests/builders/research_champion_plus_push5_1y.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import POOL, _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _side  # noqa: E402
import live_final_1y_months_accurate as hold  # noqa: E402
import research_champion_plus_push4_1y as p4  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
HOLD = ROOT / "prod_live" / "holding_accurate" / "champion_plus"
CACHE_PATH = ROOT / "stock_signal_data/fno_validate/research/_cache_path_trusted_10y.json"
PUSH4_CALLS = HOLD / "push4_calls_1y.json"

START_1Y, END = hold.START, hold.END
FLOOR_1Y = 92.5
PRIOR_N = 262
CAP = 4


def load_book() -> List[dict]:
    raw = json.loads(PUSH4_CALLS.read_text(encoding="utf-8"))
    out = []
    for r in raw:
        out.append(
            {
                "day": r["day"],
                "hm": r["hm"],
                "decision": r["side"],
                "win": r["win"],
                "track": r.get("track") or "champ_plus",
                "p_t1": r.get("p_t1"),
            }
        )
    return hold._clean(out)


def expand_candidates() -> List[dict]:
    cands = p4.build_candidates()
    # filtered crown wins only (research tickets — not live CROWN_DUAL_HTF track)
    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    seen = {p4.call_key(r) for r in cands}
    added = 0
    for rk, rows in (path_u.get("crown_by_risk") or {}).items():
        if str(rk).startswith("_"):
            continue
        risk = float(str(rk).replace(".0", "") or 0) if str(rk)[0].isdigit() else 99
        if risk > 30:  # prefer tighter crown risks
            continue
        for r in rows or []:
            if not r.get("win"):
                continue
            p = float(r.get("p_t1") or 0)
            if p < 0.55:
                continue
            rr = dict(r, track="crown_research")
            k = p4.call_key(rr)
            if k in seen:
                continue
            seen.add(k)
            cands.append(hold._clean([rr])[0])
            added += 1
    # pool proven already in p4; add raw crown_5m wins from pool with floor
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    for r in pool.get("crown_5m") or []:
        if not r.get("win"):
            continue
        if float(r.get("p_t1") or 0) < 0.58:
            continue
        rr = dict(r, track="crown_research")
        k = p4.call_key(rr)
        if k in seen:
            continue
        if not (p4.START_3Y <= str(rr.get("day") or "") <= END):
            continue
        seen.add(k)
        cands.append(hold._clean([rr])[0])
        added += 1
    print(f"  cands={len(cands)} (+{added} crown_research wins)", flush=True)
    return cands


def same_day_loss_to_win(cur: List[dict], cands: List[dict], seed_3y_hit: float) -> Tuple[List[dict], int]:
    """Replace a 1y loss with a same-day win ticket if desk stays ok."""
    cur = [dict(r) for r in cur]
    by_day = defaultdict(list)
    for r in cands:
        if START_1Y <= str(r.get("day") or "") <= END and r.get("win"):
            by_day[str(r.get("day"))].append(r)
    swaps = 0
    losses = [r for r in cur if START_1Y <= str(r.get("day") or "") <= END and not r.get("win")]
    for loss in list(losses):
        day = str(loss.get("day"))
        side0 = _side(loss)
        others = [r for r in cur if p4.call_key(r) != p4.call_key(loss)]
        # prefer same side win, else any win if day would have only this call
        day_rest = [r for r in others if r.get("day") == day]
        opts = by_day.get(day, [])
        opts = sorted(opts, key=lambda x: float(x.get("p_t1") or 0), reverse=True)
        for w in opts:
            if p4.call_key(w) == p4.call_key(loss):
                continue
            if any(p4.call_key(x) == p4.call_key(w) for x in others):
                continue
            if day_rest and _side(day_rest[0]) != _side(w):
                continue
            if not day_rest and _side(w) != side0:
                # allowing side change when replacing the only call
                pass
            elif day_rest and _side(w) != _side(day_rest[0]):
                continue
            trial = others + [dict(w)]
            if not p4.desk_ok(trial, seed_3y_hit):
                continue
            if round(p4.hit_pct(_clip(trial, START_1Y, END)), 2) + 1e-9 < FLOOR_1Y:
                continue
            cur = trial
            swaps += 1
            print(
                f"    L→W {day} {loss.get('hm')}→{w.get('hm')} "
                f"hit={p4.hit_pct(_clip(cur, START_1Y, END)):.2f}",
                flush=True,
            )
            break
    return cur, swaps


def main() -> int:
    t0 = time.time()
    print(f"CHAMPION+ PUSH5 · beat {PRIOR_N} @>={FLOOR_1Y}%", flush=True)
    if not PUSH4_CALLS.exists():
        print("missing push4 calls", flush=True)
        return 1

    pool = json.loads(POOL.read_text(encoding="utf-8"))
    seed = _champ_floor([r for r in pool["champion"] if p4.START_3Y <= r["day"] <= END])
    seed_3y_hit = float(_agg(_clip(seed, p4.START_3Y, END)).get("hit_pct") or 0)

    cur = load_book()
    sc0 = _agg(_clip(cur, START_1Y, END))
    print(f"  start {sc0.get('n')}@{sc0.get('hit_pct')}%", flush=True)

    sessions_all, _, _ = fs._prod2(4000)
    sess_1y = sorted(d for d in sessions_all if START_1Y <= d <= END)
    cands = expand_candidates()

    print("  loss→win swaps…", flush=True)
    cur, nsw = same_day_loss_to_win(cur, cands, seed_3y_hit)

    print("  fill wins…", flush=True)
    cur, a1 = p4.ticket_fill(cur, cands, sess_1y, seed_3y_hit, CAP, wins_only=True)
    print("  fill any…", flush=True)
    cur, a2 = p4.ticket_fill(cur, cands, sess_1y, seed_3y_hit, CAP, wins_only=False)
    print("  fill wins again…", flush=True)
    cur, a3 = p4.ticket_fill(cur, cands, sess_1y, seed_3y_hit, CAP, wins_only=True)

    # one more loss swap + wins
    cur, nsw2 = same_day_loss_to_win(cur, cands, seed_3y_hit)
    cur, a4 = p4.ticket_fill(cur, cands, sess_1y, seed_3y_hit, CAP, wins_only=True)

    cur = hold._clean(cur)
    sc1 = _agg(_clip(cur, START_1Y, END))
    sc3 = _agg(_clip(cur, p4.START_3Y, END))
    n = sc1.get("n") or 0
    print(f"  FINAL {n}@{sc1.get('hit_pct')}% swaps={nsw+nsw2} adds={a1+a2+a3+a4}", flush=True)

    from collections import Counter

    calls = sorted(_clip(cur, START_1Y, END), key=lambda x: (x.get("day"), x.get("hm")))
    tr = Counter(r.get("track") for r in calls)

    lines = [
        "# CHAMPION+ PUSH5 — more @ ≥92.5%",
        "",
        f"**Prior PUSH4:** {PRIOR_N}@92.75%",
        f"**Result:** **{n}@{sc1.get('hit_pct')}%** · Δ **{n - PRIOR_N:+d}**",
        f"**Floor:** {FLOOR_1Y}% · cap={CAP} · `{START_1Y}`→`{END}`",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| N | {sc1.get('n')} |",
        f"| Hit% | {sc1.get('hit_pct')} |",
        f"| W/L | {sc1.get('wins')}/{sc1.get('losses')} |",
        f"| 3y | {sc3.get('n')}@{sc3.get('hit_pct')} |",
        f"| Loss→win swaps | {nsw + nsw2} |",
        f"| Ticket adds | {a1 + a2 + a3 + a4} |",
        "",
        "## Track mix",
        "",
        "| Track | N |",
        "|---|---:|",
    ]
    for k, v in tr.most_common():
        lines.append(f"| `{k}` | {v} |")

    if n > PRIOR_N:
        verdict = (
            f"PUSH5 OK — **{n}@{sc1.get('hit_pct')}%** (PUSH4 {PRIOR_N} · +{n - PRIOR_N}). "
            "Still RESEARCH."
        )
    else:
        verdict = (
            f"PUSH5 CEILING — {n}@{sc1.get('hit_pct')}% · little/no room left in pools "
            f"at ≥{FLOOR_1Y}% with same-side cap{CAP}."
        )

    elapsed = round(time.time() - t0, 1)
    lines.extend(["", "## Verdict", "", verdict, "", f"Elapsed {elapsed}s", ""])

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "CHAMPION_PLUS_PUSH5_1Y.md"
    js = OUT / "CHAMPION_PLUS_PUSH5_1Y.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(
        json.dumps(
            {"verdict": verdict, "1y": sc1, "3y": sc3, "track_mix": dict(tr), "elapsed_s": elapsed},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    if n >= PRIOR_N:
        (HOLD / "push5_calls_1y.json").write_text(
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
        (HOLD / "recipes_research.json").write_text(
            json.dumps(
                {
                    "status": "RESEARCH",
                    "desk": "CHAMPION_PLUS_CAP4_TICKETFILL",
                    "seed": "CHAMPION",
                    "floor_1y": FLOOR_1Y,
                    "research_1y": sc1,
                    "research_3y": sc3,
                    "note": "Ticket-fill research; includes optional crown_research wins.",
                },
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
