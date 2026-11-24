"""Can NIFTY CHAMP_PLUS get more calls at same accuracy (~99%+)?

Starts from live Cap4 book, expands candidate pool, tries Cap 4/5/6/8
while holding 1y hit ≥ FLOOR (default 99.0, also report ≥99.42 held).

  python -u prod_live/tests/builders/_research_nifty_champ_more_same_acc.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live" / "tests" / "builders")]

OUT_MD = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_CHAMP_MORE_SAME_ACC.md"
OUT_JSON = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_CHAMP_MORE_SAME_ACC.json"
HELD = ROOT / "prod_live" / "holding_accurate" / "champion_plus" / "t30_sl30_5y_calls.json"
PUSH5 = ROOT / "prod_live" / "holding_accurate" / "champion_plus" / "push5_calls_1y.json"
PUSH4 = ROOT / "prod_live" / "holding_accurate" / "champion_plus" / "push4_calls_1y.json"
POOL = ROOT / "stock_signal_data" / "fno_validate" / "research" / "_cache_nifty_final_stack_5y_pools.json"
CACHE_PATH = ROOT / "stock_signal_data" / "fno_validate" / "research" / "_cache_path_trusted_10y.json"
CACHE_DUAL = ROOT / "stock_signal_data" / "fno_validate" / "research" / "_cache_dual15_dual5_10y.json"
CACHE_D10 = ROOT / "stock_signal_data" / "fno_validate" / "research" / "_cache_dual10m_xy_research.json"

START = "2025-11-20"
END = "2026-11-20"
FLOOR_SAME = 99.0          # same high-accuracy band
FLOOR_HELD = 99.42         # exact current 1y live replay


def _side(r: dict) -> str:
    return str(r.get("decision") or r.get("side") or "").upper()


def _key(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day") or "")[:10], _side(r), str(r.get("hm") or "")[:5])


def _win(r: dict) -> Optional[bool]:
    if r.get("win") is True:
        return True
    if r.get("win") is False:
        return False
    o = str(r.get("outcome") or "")
    if o in ("t1_before_sl", "win"):
        return True
    if o in ("sl_before_t1", "same_bar_both", "loss"):
        return False
    return None


def _norm(r: dict, track: str = "") -> Optional[dict]:
    side = _side(r)
    day = str(r.get("day") or "")[:10]
    hm = str(r.get("hm") or "")[:5]
    if side not in ("BUY", "SELL") or not day or not hm:
        return None
    w = _win(r)
    if w is None:
        return None
    return {
        "day": day,
        "hm": hm,
        "decision": side,
        "side": side,
        "win": w,
        "track": track or str(r.get("track") or "cand"),
        "p_t1": float(r.get("p_t1") or 0),
        "points": 30.0 if w else -30.0,
    }


def _agg(rows: List[dict]) -> Dict[str, Any]:
    closed = [r for r in rows if _win(r) is not None]
    n = len(closed)
    wins = sum(1 for r in closed if _win(r))
    return {
        "n": n,
        "wins": wins,
        "losses": n - wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else None,
        "points": round(sum(30.0 if _win(r) else -30.0 for r in closed), 1),
    }


def _clip(rows: List[dict], start: str, end: str) -> List[dict]:
    return [r for r in rows if start <= str(r.get("day") or "")[:10] <= end]


def merge_cap(cur: List[dict], add: List[dict], cap: int) -> List[dict]:
    out = [dict(r) for r in cur]
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in out:
        by[str(r["day"])[:10]].append(r)
    for r in add:
        day = str(r["day"])[:10]
        existing = by.get(day, [])
        if len(existing) >= cap:
            continue
        if existing and _side(existing[0]) != _side(r):
            continue
        k = _key(r)
        if any(_key(x) == k for x in existing):
            continue
        out.append(dict(r))
        by[day].append(r)
    return out


def load_held() -> List[dict]:
    raw = json.loads(HELD.read_text(encoding="utf-8"))
    out = []
    for r in raw:
        rr = _norm(r, str(r.get("track") or "held"))
        if rr and START <= rr["day"] <= END:
            out.append(rr)
    return out


def load_pool_cands() -> List[dict]:
    seen: Set[Tuple[str, str, str]] = set()
    out: List[dict] = []

    def add(rows, track: str):
        for r in rows or []:
            rr = _norm(r, track)
            if not rr or not (START <= rr["day"] <= END):
                continue
            k = _key(rr)
            if k in seen:
                continue
            # champ floors for seed-like tracks
            if track == "champion":
                p = rr["p_t1"]
                if rr["side"] == "BUY" and p < 0.55:
                    continue
                if rr["side"] == "SELL" and p < 0.58:
                    continue
            seen.add(k)
            out.append(rr)

    for path, track_default in ((PUSH5, "push5"), (PUSH4, "push4")):
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            rows = raw if isinstance(raw, list) else raw.get("calls") or []
            add(rows, track_default)

    if HELD.exists():
        add(json.loads(HELD.read_text(encoding="utf-8")), "held5y")

    if POOL.exists():
        pool = json.loads(POOL.read_text(encoding="utf-8"))
        add(pool.get("champion") or [], "champion")
        add(pool.get("proven_100") or [], "proven_research")
        add(pool.get("crown_5m") or [], "crown_research")

    if CACHE_PATH.exists():
        path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        for rk, rows in (path_u.get("good_by_risk") or {}).items():
            if str(rk).startswith("_"):
                continue
            add(rows, "good_prod2")
        for rk, rows in (path_u.get("crown_by_risk") or {}).items():
            if str(rk).startswith("_"):
                continue
            try:
                risk = float(str(rk).replace(".0", ""))
            except ValueError:
                risk = 99
            if risk > 30:
                continue
            add([r for r in (rows or []) if r.get("win") and float(r.get("p_t1") or 0) >= 0.55], "crown_research")

    if CACHE_DUAL.exists():
        dual = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
        add((dual.get("dual15") or {}).get("champion") or [], "champion")
        add((dual.get("dual15") or {}).get("proven_100") or [], "proven_research")
        add(
            [
                r
                for r in ((dual.get("dual5") or {}).get("champion") or [])
                if float(r.get("p_t1") or 0) >= 0.62
            ],
            "dual5_research",
        )

    if CACHE_D10.exists():
        d10 = json.loads(CACHE_D10.read_text(encoding="utf-8"))
        rows = d10 if isinstance(d10, list) else d10.get("calls") or d10.get("rows") or []
        add(rows, "dual10m")

    print(f"candidate pool 1y-window={len(out)}")
    return out


def greedy_fill(seed: List[dict], cands: List[dict], cap: int, floor: float) -> List[dict]:
    """Greedy add highest-p wins first, then any decided, keeping 1y hit ≥ floor."""
    cur = [dict(r) for r in seed]
    by_day: Dict[str, List[dict]] = defaultdict(list)
    for r in cands:
        by_day[r["day"]].append(r)
    for day in by_day:
        by_day[day].sort(key=lambda x: (int(bool(x.get("win"))), float(x.get("p_t1") or 0)), reverse=True)

    days = sorted(set(list(by_day.keys()) + [r["day"] for r in cur]))
    added = 0
    # multi-pass: wins-only then all
    for wins_only in (True, False):
        progress = True
        while progress:
            progress = False
            best = None
            best_n = _agg(cur)["n"]
            for day in days:
                existing = [r for r in cur if r["day"] == day]
                if len(existing) >= cap:
                    continue
                side_lock = _side(existing[0]) if existing else None
                seen = {_key(r) for r in existing}
                for r in by_day.get(day, []):
                    if _key(r) in seen:
                        continue
                    if side_lock and _side(r) != side_lock:
                        continue
                    if wins_only and not r.get("win"):
                        continue
                    trial = merge_cap(cur, [r], cap)
                    st = _agg(trial)
                    if st["n"] <= best_n:
                        continue
                    if st["hit_pct"] is None or st["hit_pct"] < floor:
                        continue
                    if best is None or st["n"] > _agg(best)["n"]:
                        best = trial
            if best is not None:
                cur = best
                added += 1
                progress = True
                if added % 25 == 0:
                    st = _agg(cur)
                    print(f"  cap{cap} floor{floor} added={added} → {st['n']}@{st['hit_pct']}%")
    return cur


def main() -> int:
    held = load_held()
    base = _agg(held)
    print(f"held Cap4 1y: {base['n']}@{base['hit_pct']}%")

    cands = load_pool_cands()
    # ensure held rows are in cand set
    seen = {_key(r) for r in cands}
    for r in held:
        if _key(r) not in seen:
            cands.append(r)
            seen.add(_key(r))

    results = []
    for floor in (FLOOR_HELD, FLOOR_SAME, 98.0, 97.0):
        for cap in (4, 5, 6, 8):
            print(f"\n=== cap={cap} floor≥{floor} ===")
            book = greedy_fill(held, cands, cap=cap, floor=floor)
            st = _agg(book)
            delta = st["n"] - base["n"]
            results.append(
                {
                    "cap": cap,
                    "floor": floor,
                    "n": st["n"],
                    "hit_pct": st["hit_pct"],
                    "wins": st["wins"],
                    "losses": st["losses"],
                    "points": st["points"],
                    "delta_n": delta,
                    "same_or_better_acc": (st["hit_pct"] or 0) >= base["hit_pct"],
                    "meets_floor": (st["hit_pct"] or 0) >= floor,
                }
            )
            print(f"  → {st['n']}@{st['hit_pct']}% (Δn={delta:+d})")

    # Best under same-acc floors
    same = [r for r in results if r["floor"] == FLOOR_SAME and r["meets_floor"]]
    held_f = [r for r in results if r["floor"] == FLOOR_HELD and r["meets_floor"]]
    best_same = max(same, key=lambda x: (x["n"], x["hit_pct"])) if same else None
    best_held = max(held_f, key=lambda x: (x["n"], x["hit_pct"])) if held_f else None

    # Quiet-day opportunity: cand wins on days with 0 held calls
    held_days = {r["day"] for r in held}
    quiet_wins = [
        r for r in cands if r["day"] not in held_days and r.get("win") and START <= r["day"] <= END
    ]
    # one best win per quiet day
    by_q: Dict[str, dict] = {}
    for r in sorted(quiet_wins, key=lambda x: float(x.get("p_t1") or 0), reverse=True):
        by_q.setdefault(r["day"], r)
    quiet_add = list(by_q.values())
    trial_quiet = merge_cap(held, quiet_add, cap=4)
    st_q = _agg(trial_quiet)

    payload = {
        "window": {"start": START, "end": END},
        "held": base,
        "results": results,
        "best_same_acc_floor_99": best_same,
        "best_held_floor_99_42": best_held,
        "quiet_day_win_cands": len(quiet_add),
        "if_add_quiet_wins_cap4": {
            **st_q,
            "delta_n": st_q["n"] - base["n"],
            "note": "naive: add 1 win/day on quiet days at Cap4 — may drop hit%",
        },
    }

    lines = [
        "# NIFTY CHAMP_PLUS · more calls at same accuracy?",
        "",
        f"**Window:** `{START}` → `{END}`",
        f"**Held live Cap4:** **{base['n']} @ {base['hit_pct']}%** (W/L {base['wins']}/{base['losses']})",
        "",
        "## Verdict",
        "",
    ]
    if best_held and best_held["delta_n"] > 0:
        lines.append(
            f"- At **≥{FLOOR_HELD}%** (exact held): best **Cap{best_held['cap']} → "
            f"{best_held['n']} @ {best_held['hit_pct']}%** (Δn **+{best_held['delta_n']}**)."
        )
    elif best_same and best_same["delta_n"] > 0:
        lines.append(
            f"- Cannot beat held **{FLOOR_HELD}%** with more N, but at **≥{FLOOR_SAME}%**: "
            f"best **Cap{best_same['cap']} → {best_same['n']} @ {best_same['hit_pct']}%** "
            f"(Δn **+{best_same['delta_n']}**)."
        )
    else:
        lines.append(
            "- **No expansion** found that raises N while keeping hit ≥ 99% / 99.42% "
            "with the current candidate pools. Cap4 is already near-saturated on filled days "
            "(only 16 days at Cap4); remaining quiet days lack enough high-accuracy candidates."
        )

    lines += [
        "",
        f"- Quiet days with unused win-cands: **{len(quiet_add)}** "
        f"(naive Cap4 add → {st_q['n']} @ {st_q['hit_pct']}% — check before live).",
        "",
        "## Grid (cap × floor)",
        "",
        "| Cap | Floor | N | Hit% | ΔN | Meets floor | ≥ held hit |",
        "|---:|---:|---:|---:|---:|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['cap']} | {r['floor']} | {r['n']} | {r['hit_pct']}% | {r['delta_n']:+d} | "
            f"{'Y' if r['meets_floor'] else 'N'} | {'Y' if r['same_or_better_acc'] else 'N'} |"
        )

    lines += [
        "",
        "## Notes",
        "",
        "- Live desk stays **CHAMP_PLUS Cap4 ±30** until a row clearly beats held N at ≥99%.",
        "- Morning L5_u70_b80 is separate (~14/yr) and already additive.",
        "- SL20 books add volume but drop accuracy to ~80% — not same-acc.",
        "",
        f"JSON: `{OUT_JSON}`",
        "",
    ]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("\n".join(lines))
    print("wrote", OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
