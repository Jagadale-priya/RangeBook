"""Replay Cap6 FINAL live logic · last 3y · monthly vs Cap4.

1) Locked live Cap6 held book clipped to 3y (Cap6 denser in last 1y)
2) Full Cap6 greedy expand over entire 3y window (same fill as lock, floor=Cap4 3y hit)

  python -u prod_live/tests/builders/_report_live_nifty_cap6_3y_months.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live" / "tests" / "builders")]

OUT_MD = ROOT / "prod_live" / "reports" / "3y" / "LIVE_NIFTY_CAP6_3Y_MONTHLY.md"
OUT_JSON = ROOT / "prod_live" / "reports" / "3y" / "LIVE_NIFTY_CAP6_3Y_MONTHLY.json"

HOLD = ROOT / "prod_live" / "holding_accurate" / "champion_plus"
HELD_CAP6 = HOLD / "t30_sl30_5y_calls.json"
HELD_CAP4 = HOLD / "t30_sl30_5y_calls_cap4_backup.json"
SENSEX = ROOT / "prod_live" / "holding_accurate" / "sensex_final" / "champ_plus_t50_sl50_calls.json"
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_kite.csv"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"

PUSH5 = HOLD / "push5_calls_1y.json"
PUSH4 = HOLD / "push4_calls_1y.json"
POOL = ROOT / "stock_signal_data" / "fno_validate" / "research" / "_cache_nifty_final_stack_5y_pools.json"
CACHE_PATH = ROOT / "stock_signal_data" / "fno_validate" / "research" / "_cache_path_trusted_10y.json"
CACHE_DUAL = ROOT / "stock_signal_data" / "fno_validate" / "research" / "_cache_dual15_dual5_10y.json"
CACHE_D10 = ROOT / "stock_signal_data" / "fno_validate" / "research" / "_cache_dual10m_xy_research.json"

TODAY = date.today().isoformat()
START = (pd.Timestamp(TODAY) - pd.DateOffset(years=3)).date().isoformat()
END = TODAY
CAP = 6


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


def _agg(rows: List[dict], pts: float = 30.0) -> Dict[str, Any]:
    closed = [r for r in rows if _win(r) is not None]
    n = len(closed)
    wins = sum(1 for r in closed if _win(r))
    return {
        "n": n,
        "wins": wins,
        "losses": n - wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else None,
        "points": round(sum(pts if _win(r) else -pts for r in closed), 1),
    }


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
    rr.update(
        {
            "day": day,
            "hm": hm,
            "decision": side,
            "side": side,
            "win": w,
            "track": track or str(r.get("track") or "cand"),
            "p_t1": float(r.get("p_t1") or 0),
            "points": 30.0 if w else -30.0,
        }
    )
    return rr


def _load_book(path: Path, start: str, end: str) -> List[dict]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else raw.get("calls") or []
    out = []
    for r in rows:
        d = str(r.get("day") or "")[:10]
        if start <= d <= end:
            rr = dict(r)
            if not rr.get("decision"):
                rr["decision"] = rr.get("side")
            out.append(rr)
    return out


def _monthly(rows: List[dict], sess_by_m: Dict[str, int], pts: float = 30.0) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        d = str(r.get("day") or "")[:10]
        if len(d) >= 7:
            by[d[:7]].append(r)
    out = []
    for m in sorted(by):
        st = _agg(by[m], pts=pts)
        days = sorted({str(r.get("day"))[:10] for r in by[m]})
        sess = int(sess_by_m.get(m) or 0)
        out.append(
            {
                "month": m,
                **st,
                "days_with_call": len(days),
                "sessions": sess or None,
                "quiet_days": max(0, sess - len(days)) if sess else None,
            }
        )
    return out


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

    for path, track in ((PUSH5, "push5"), (PUSH4, "push4"), (HELD_CAP4, "held_cap4"), (HELD_CAP6, "held_cap6")):
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            rows = raw if isinstance(raw, list) else raw.get("calls") or []
            add(rows, track)

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

    print(f"candidate pool 3y={len(out)}", flush=True)
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
                if added % 50 == 0:
                    st = _agg(cur)
                    print(f"  cap{cap} floor{floor} added={added} → {st['n']}@{st['hit_pct']}%", flush=True)
    print(f"  greedy done added={added} → {_agg(cur)}", flush=True)
    return cur


def _sess_by_month() -> Dict[str, int]:
    if not TAPE15.exists():
        return {}
    df = pd.read_csv(TAPE15, index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("Asia/Kolkata")
    else:
        df.index = df.index.tz_convert("Asia/Kolkata")
    by_m: Dict[str, int] = defaultdict(int)
    for d in {str(t.date()) for t in df.index}:
        by_m[d[:7]] += 1
    return dict(by_m)


def _morning_l5(start: str, end: str) -> List[dict]:
    if not TAPE15.exists() or not TAPE5.exists():
        return []
    import importlib.util

    path = ROOT / "prod_live" / "tests" / "builders" / "_compare_nifty_live_vs_research_windows.py"
    spec = importlib.util.spec_from_file_location("cmp_nifty_windows", path)
    cmp = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(cmp)
    bars15 = cmp._load(TAPE15)
    bars5 = cmp._load(TAPE5)
    bars15["__d"] = [cmp._day(t) for t in bars15.index]
    bars5["__d"] = [cmp._day(t) for t in bars5.index]
    g15 = {d: g.drop(columns="__d") for d, g in bars15.groupby("__d", sort=True)}
    g5 = {d: g.drop(columns="__d") for d, g in bars5.groupby("__d", sort=True)}
    out = []
    for d in sorted(g15.keys()):
        if d < start or d > end:
            continue
        sess5 = g5.get(d)
        if sess5 is None:
            continue
        r = cmp.morning_day(g15[d], sess5)
        if not r:
            continue
        w = r.get("out")
        out.append(
            {
                "day": r["d"],
                "hm": r.get("fill") or r.get("sig"),
                "decision": "BUY",
                "side": "BUY",
                "track": "morning_L5_u70_b80",
                "win": True if w == "win" else (False if w == "loss" else None),
                "points": 30.0 if w == "win" else (-30.0 if w == "loss" else 0.0),
            }
        )
    return out


def main() -> int:
    t0 = time.time()
    print(f"3y Cap6 test · {START} → {END}", flush=True)
    sess_by_m = _sess_by_month()

    locked6 = _load_book(HELD_CAP6, START, END)
    cap4 = _load_book(HELD_CAP4, START, END)
    # normalize decided rows for fill seed
    seed = []
    for r in cap4:
        rr = _norm(r, str(r.get("track") or "held"))
        if rr:
            seed.append(rr)
    st4 = _agg(seed)
    floor = float(st4["hit_pct"] or 99.0)
    print(f"Cap4 3y seed: {st4['n']}@{st4['hit_pct']}% · floor={floor}", flush=True)

    cands = load_pool_cands(START, END)
    seen = {_key(r) for r in cands}
    for r in seed:
        if _key(r) not in seen:
            cands.append(r)
            seen.add(_key(r))

    print(f"=== full Cap6 expand 3y floor≥{floor} ===", flush=True)
    full6 = greedy_fill(seed, cands, cap=CAP, floor=floor)
    st6_full = _agg(full6)
    st6_locked = _agg([r for r in locked6 if _win(r) is not None] or locked6)

    morning = _morning_l5(START, END)
    st_m = _agg(morning)
    seen_k = {_key(r) for r in full6}
    comb = list(full6)
    for r in morning:
        rr = dict(r)
        rr["day"] = str(rr.get("day") or "")[:10]
        rr["hm"] = str(rr.get("hm") or "")[:5]
        if _key(rr) not in seen_k and _win(rr) is not None:
            comb.append(rr)
            seen_k.add(_key(rr))
    st_comb = _agg(comb)

    sensex = _load_book(SENSEX, START, END)
    st_sx = _agg(sensex, pts=50.0)

    m6 = _monthly(full6, sess_by_m)
    m4 = _monthly(seed, sess_by_m)
    m_locked = _monthly(locked6, sess_by_m)
    m_morn = _monthly(morning, sess_by_m)
    m_comb = _monthly(comb, sess_by_m)
    m_sx = _monthly(sensex, {}, pts=50.0)

    # yearly rollups
    def by_year(rows: List[dict]) -> Dict[str, Dict[str, Any]]:
        yb: Dict[str, List[dict]] = defaultdict(list)
        for r in rows:
            yb[str(r.get("day") or "")[:4]].append(r)
        return {y: _agg(yb[y]) for y in sorted(yb)}

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "window": {"start": START, "end": END},
        "desk": "CHAMP_PLUS_T30SL30_CAP6",
        "cap": CAP,
        "floor_used": floor,
        "cap4_3y": st4,
        "cap6_full_3y_expand": st6_full,
        "cap6_locked_live_book_3y": _agg(locked6),
        "delta_full_vs_cap4": {
            "delta_n": st6_full["n"] - st4["n"],
            "hit_cap6": st6_full["hit_pct"],
            "hit_cap4": st4["hit_pct"],
        },
        "morning_l5": st_m,
        "combined_full6_morning": st_comb,
        "sensex": st_sx,
        "by_year_cap6_full": by_year(full6),
        "by_year_cap4": by_year(seed),
        "monthly_cap6_full": m6,
        "monthly_cap4": m4,
        "monthly_cap6_locked": m_locked,
        "monthly_morning": m_morn,
        "monthly_combined": m_comb,
        "monthly_sensex": m_sx,
        "elapsed_s": round(time.time() - t0, 1),
    }

    lines = [
        "# Live NIFTY Cap6 FINAL · last 3y monthly",
        "",
        f"**Generated:** `{payload['generated_at']}`",
        f"**Window:** `{START}` → `{END}`",
        f"**Desk:** `CHAMP_PLUS_T30SL30_CAP6` · ±30 · Cap{CAP}",
        "",
        "## Totals (3y)",
        "",
        "| Book | N | Hit% | W/L | Points |",
        "|---|---:|---:|---|---:|",
        f"| **Cap6 FULL expand (same logic)** | **{st6_full['n']}** | **{st6_full['hit_pct']}%** | {st6_full['wins']}/{st6_full['losses']} | {st6_full['points']} |",
        f"| Cap4 prior | {st4['n']} | **{st4['hit_pct']}%** | {st4['wins']}/{st4['losses']} | {st4['points']} |",
        f"| Cap6 − Cap4 | **{st6_full['n'] - st4['n']:+d}** | {st6_full['hit_pct']}% vs {st4['hit_pct']}% | — | {st6_full['points'] - st4['points']:+.1f} |",
        f"| Cap6 locked live book (1y-expand only) | {_agg(locked6)['n']} | **{_agg(locked6)['hit_pct']}%** | {_agg(locked6)['wins']}/{_agg(locked6)['losses']} | {_agg(locked6)['points']} |",
        f"| Morning L5 | {st_m['n']} | **{st_m['hit_pct']}%** | {st_m['wins']}/{st_m['losses']} | {st_m['points']} |",
        f"| Cap6 full ∪ morning | {st_comb['n']} | **{st_comb['hit_pct']}%** | {st_comb['wins']}/{st_comb['losses']} | {st_comb['points']} |",
        f"| SENSEX ±50 | {st_sx['n']} | **{st_sx['hit_pct']}%** | {st_sx['wins']}/{st_sx['losses']} | {st_sx['points']} |",
        "",
        f"Floor held for Cap6 expand: **≥{floor}%** (Cap4 3y hit).",
        "",
        "## By calendar year",
        "",
        "| Year | Cap4 N | Cap4 Hit% | Cap6 N | Cap6 Hit% | ΔN |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    years = sorted(set(list(payload["by_year_cap4"]) + list(payload["by_year_cap6_full"])))
    for y in years:
        a = payload["by_year_cap4"].get(y) or {"n": 0, "hit_pct": None}
        b = payload["by_year_cap6_full"].get(y) or {"n": 0, "hit_pct": None}
        lines.append(
            f"| {y} | {a['n']} | {a['hit_pct']}% | {b['n']} | **{b['hit_pct']}%** | {b['n'] - a['n']:+d} |"
        )

    lines += [
        "",
        "## Cap6 FULL expand — per month",
        "",
        "| Month | Sess | Calls | Hit% | W/L | Pts | Days w/ call | Quiet |",
        "|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for row in m6:
        lines.append(
            f"| {row['month']} | {row.get('sessions') or '—'} | {row['n']} | **{row['hit_pct']}%** | "
            f"{row['wins']}/{row['losses']} | {row['points']} | {row['days_with_call']} | "
            f"{row['quiet_days'] if row['quiet_days'] is not None else '—'} |"
        )

    by4 = {r["month"]: r for r in m4}
    by6 = {r["month"]: r for r in m6}
    lines += [
        "",
        "## Cap6 vs Cap4 — per month",
        "",
        "| Month | Cap4 N | Cap4 Hit% | Cap6 N | Cap6 Hit% | ΔN |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for m in sorted(set(list(by4) + list(by6))):
        a = by4.get(m) or {"n": 0, "hit_pct": None}
        b = by6.get(m) or {"n": 0, "hit_pct": None}
        lines.append(
            f"| {m} | {a['n']} | {a['hit_pct']}% | {b['n']} | **{b['hit_pct']}%** | {b['n'] - a['n']:+d} |"
        )

    lines += [
        "",
        "## Morning L5 — per month",
        "",
        "| Month | Calls | Hit% | W/L | Pts |",
        "|---|---:|---:|---|---:|",
    ]
    for row in m_morn:
        lines.append(
            f"| {row['month']} | {row['n']} | **{row['hit_pct']}%** | {row['wins']}/{row['losses']} | {row['points']} |"
        )
    if not m_morn:
        lines.append("| — | 0 | — | — | — |")

    lines += [
        "",
        "## Notes",
        "",
        "- **Cap6 FULL expand** = same ticket-fill as live Cap6 lock (cap6 · prefer wins · floor ≥ Cap4 3y hit) over the whole 3y window.",
        "- **Cap6 locked live book** only densified the last 1y at promote time; older years stay Cap4-dense in the held file.",
        "- Brackets ±30. Afternoon OFF. P2F/P2G annotate-only.",
        "",
        f"JSON: `{OUT_JSON}`",
        f"Elapsed: {payload['elapsed_s']}s",
        "",
    ]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("\n".join(lines[:90]))
    print("...")
    print("wrote", OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
