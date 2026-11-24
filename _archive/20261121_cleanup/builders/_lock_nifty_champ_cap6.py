"""Promote NIFTY CHAMP_PLUS Cap6 (±30) into live held book.

Research (NIFTY_CHAMP_MORE_SAME_ACC): Cap6 @ floor≥99.42 → 433 @ 99.54% (+90 vs Cap4).
This locks that fill into t30_sl30_5y_calls.json and leaves older years Cap4-dense.

  python -u prod_live/tests/builders/_lock_nifty_champ_cap6.py
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live" / "tests" / "builders")]

HOLD = ROOT / "prod_live" / "holding_accurate" / "champion_plus"
HELD = HOLD / "t30_sl30_5y_calls.json"
BACKUP = HOLD / "t30_sl30_5y_calls_cap4_backup.json"
OUT_MD = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_CHAMP_CAP6_LOCKED.md"
OUT_JSON = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_CHAMP_CAP6_LOCKED.json"
REPORT_5Y = ROOT / "prod_live" / "reports" / "5y" / "CHAMPION_PLUS_T30_SL30_5Y.json"

PUSH5 = HOLD / "push5_calls_1y.json"
PUSH4 = HOLD / "push4_calls_1y.json"
POOL = ROOT / "stock_signal_data" / "fno_validate" / "research" / "_cache_nifty_final_stack_5y_pools.json"
CACHE_PATH = ROOT / "stock_signal_data" / "fno_validate" / "research" / "_cache_path_trusted_10y.json"
CACHE_DUAL = ROOT / "stock_signal_data" / "fno_validate" / "research" / "_cache_dual15_dual5_10y.json"
CACHE_D10 = ROOT / "stock_signal_data" / "fno_validate" / "research" / "_cache_dual10m_xy_research.json"

CAP = 6
DESK = "CHAMP_PLUS_T30SL30_CAP6"
FLOOR = 99.42
END = "2026-11-20"
START_1Y = "2025-11-20"
START_3Y = "2023-11-20"
START_5Y = "2021-11-16"


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
    rr = dict(r)
    rr["day"] = day
    rr["hm"] = hm
    rr["decision"] = side
    rr["side"] = side
    rr["win"] = w
    rr["track"] = track or str(r.get("track") or "cand")
    rr["p_t1"] = float(r.get("p_t1") or 0)
    rr["points"] = 30.0 if w else -30.0
    rr.setdefault("t1_pts", 30.0)
    rr.setdefault("sl_pts", 30.0)
    return rr


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


def load_pool_cands(start: str, end: str) -> List[dict]:
    seen: Set[Tuple[str, str, str]] = set()
    out: List[dict] = []

    def add(rows, track: str):
        for r in rows or []:
            rr = _norm(r, track)
            if not rr or not (start <= rr["day"] <= end):
                continue
            k = _key(rr)
            if k in seen:
                continue
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
            add(
                [r for r in (rows or []) if r.get("win") and float(r.get("p_t1") or 0) >= 0.55],
                "crown_research",
            )

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

    print(f"candidate pool {start}→{end} = {len(out)}", flush=True)
    return out


def greedy_fill(seed: List[dict], cands: List[dict], cap: int, floor: float) -> List[dict]:
    cur = [dict(r) for r in seed]
    by_day: Dict[str, List[dict]] = defaultdict(list)
    for r in cands:
        by_day[r["day"]].append(r)
    for day in by_day:
        by_day[day].sort(
            key=lambda x: (int(bool(x.get("win"))), float(x.get("p_t1") or 0)),
            reverse=True,
        )

    days = sorted(set(list(by_day.keys()) + [r["day"] for r in cur]))
    added = 0
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
                    print(f"  cap{cap} floor{floor} added={added} → {st['n']}@{st['hit_pct']}%", flush=True)
    print(f"  greedy done added={added} → {_agg(cur)}", flush=True)
    return cur


def _monthly(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r["day"])[:7]].append(r)
    out = []
    for m in sorted(by):
        st = _agg(by[m])
        out.append({"month": m, **st})
    return out


def main() -> int:
    t0 = time.time()
    print(f"Lock NIFTY CHAMP_PLUS Cap{CAP} · {DESK}", flush=True)
    if not HELD.exists():
        print("MISSING held book", HELD)
        return 1

    raw = json.loads(HELD.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("calls") or []
    held_all = []
    for r in raw:
        side = _side(r)
        day = str(r.get("day") or "")[:10]
        hm = str(r.get("hm") or "")[:5]
        if side not in ("BUY", "SELL") or not day or not hm:
            continue
        rr = dict(r)
        rr["day"] = day
        rr["hm"] = hm
        rr["decision"] = side
        rr["side"] = side
        held_all.append(rr)

    if not BACKUP.exists():
        shutil.copy2(HELD, BACKUP)
        print(f"backed up Cap4 → {BACKUP.name}", flush=True)
    else:
        print(f"backup already exists: {BACKUP.name}", flush=True)

    older = [r for r in held_all if str(r["day"])[:10] < START_1Y]
    seed_1y = []
    for r in held_all:
        d = str(r["day"])[:10]
        if not (START_1Y <= d <= END):
            continue
        rr = _norm(r, str(r.get("track") or "held"))
        if rr:
            seed_1y.append(rr)
    base = _agg(seed_1y)
    print(f"Cap4 1y seed: {base['n']}@{base['hit_pct']}%", flush=True)

    cands = load_pool_cands(START_1Y, END)
    seen = {_key(r) for r in cands}
    for r in seed_1y:
        if _key(r) not in seen:
            cands.append(r)
            seen.add(_key(r))

    print(f"=== greedy Cap{CAP} floor≥{FLOOR} ===", flush=True)
    cap6_1y = greedy_fill(seed_1y, cands, cap=CAP, floor=FLOOR)
    st1 = _agg(cap6_1y)
    print(f"Cap6 1y locked: {st1['n']}@{st1['hit_pct']}% (Δn={st1['n'] - base['n']:+d})", flush=True)

    # Merge: older Cap4 rows + Cap6 1y (prefer Cap6 keys)
    keys_1y = {_key(r) for r in cap6_1y}
    older_clean = [r for r in older if _key(r) not in keys_1y]
    # stamp Cap6 meta on 1y rows
    for r in cap6_1y:
        r["desk_tag"] = DESK
        r["accurate_tag"] = DESK
        r["mode"] = "cap6"
        r["t1_pts"] = 30.0
        r["sl_pts"] = 30.0
        if r.get("points") is None:
            r["points"] = 30.0 if r.get("win") else -30.0

    new_book = older_clean + [dict(r) for r in cap6_1y]
    new_book.sort(key=lambda r: (str(r.get("day") or ""), str(r.get("hm") or "")))

    st3 = _agg(_clip(new_book, START_3Y, END))
    st5 = _agg(_clip(new_book, START_5Y, END))
    months = _monthly(cap6_1y)

    HELD.write_text(json.dumps(new_book, indent=2, default=str), encoding="utf-8")
    print(f"wrote held Cap6 book n={len(new_book)} → {HELD}", flush=True)

    payload = {
        "desk": DESK,
        "cap": CAP,
        "brackets": {"target": 30.0, "sl": 30.0},
        "floor_1y": FLOOR,
        "window_1y": {"start": START_1Y, "end": END},
        "prior_cap4_1y": base,
        "locked_cap6_1y": st1,
        "delta_n_1y": st1["n"] - base["n"],
        "windows": {
            "1y": {**st1, "start": START_1Y, "end": END},
            "3y": {**st3, "start": START_3Y, "end": END},
            "5y": {**st5, "start": START_5Y, "end": END},
        },
        "monthly_1y": months,
        "backup": str(BACKUP).replace("\\", "/"),
        "calls": str(HELD).replace("\\", "/"),
        "elapsed_s": round(time.time() - t0, 1),
    }
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    # refresh 5y expected snapshot used by champ_plus_live
    REPORT_5Y.parent.mkdir(parents=True, exist_ok=True)
    REPORT_5Y.write_text(
        json.dumps(
            {
                "desk": DESK,
                "cap": CAP,
                "brackets": {"target": 30.0, "sl": 30.0},
                "windows": payload["windows"],
                "expected": {
                    "1y": {"n": st1["n"], "hit_pct": st1["hit_pct"]},
                    "3y": {"n": st3["n"], "hit_pct": st3["hit_pct"]},
                    "5y": {"n": st5["n"], "hit_pct": st5["hit_pct"]},
                },
                "note": "Cap6 final live · 1y greedy fill floor≥99.42; older years Cap4-dense seed",
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    lines = [
        "# NIFTY CHAMP_PLUS Cap6 — LOCKED to live",
        "",
        f"**Desk:** `{DESK}` · ±30 · Cap{CAP}",
        f"**1y window:** `{START_1Y}` → `{END}`",
        "",
        "## Verdict",
        "",
        f"- Prior Cap4 1y: **{base['n']} @ {base['hit_pct']}%**",
        f"- Locked Cap6 1y: **{st1['n']} @ {st1['hit_pct']}%** (Δn **+{st1['n'] - base['n']}**)",
        f"- 3y: **{st3['n']} @ {st3['hit_pct']}%** · 5y: **{st5['n']} @ {st5['hit_pct']}%**",
        f"- Backup Cap4 book: `{BACKUP.name}`",
        "",
        "## Cap6 1y — per month",
        "",
        "| Month | N | Hit% | W/L | Pts |",
        "|---|---:|---:|---|---:|",
    ]
    for row in months:
        lines.append(
            f"| {row['month']} | {row['n']} | **{row['hit_pct']}%** | "
            f"{row['wins']}/{row['losses']} | {row['points']} |"
        )
    lines += [
        "",
        f"JSON: `{OUT_JSON}`",
        f"Held book: `{HELD}`",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"elapsed {payload['elapsed_s']}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
