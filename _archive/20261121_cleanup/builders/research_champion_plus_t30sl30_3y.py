"""CHAMPION+ with Target=30 · SL=30 · 3y test (1y known · prior 2y focus).

Same ticket-fill logic as 1y CHAMPION+ research. Path-score every candidate
on 5m tape with symmetric 30/30. Report yearly + monthly.

  python -u prod_live/tests/builders/research_champion_plus_t30sl30_3y.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

from accuracy_max_6m import POOL, _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _side  # noqa: E402
from research_100pct_deeper_more_calls import _day, _norm, build_bar_index  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
import research_champion_plus_push4_1y as p4  # noqa: E402
import research_champion_plus_push5_1y as p5  # noqa: E402
import live_final_1y_months_accurate as hold  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "3y"
HOLD = ROOT / "prod_live" / "holding_accurate" / "champion_plus"
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"

T1_PTS = 30.0
SL_PTS = 30.0
END = "2026-11-15"
START_1Y = hold.START  # 2025-10-24
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
# prior 2y inside 3y (before locked 1y)
EXTRA_A, EXTRA_B = START_3Y, (pd.Timestamp(START_1Y) - timedelta(days=1)).strftime("%Y-%m-%d")
CAP = 4
# floor set after scoring 1y champ seed under T30/SL30 (filled at runtime)
FLOOR_1Y = 70.0


def key_of(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day") or ""), _side(r), str(r.get("hm") or ""))


def score_one(bars, ix, day: str, hm: str, side: str) -> Optional[dict]:
    i = ix.get((day, hm))
    if i is None:
        cands = [(h, j) for (d, h), j in ix.items() if d == day and h >= hm]
        if not cands:
            cands = [(h, j) for (d, h), j in ix.items() if d == day]
        if not cands:
            return None
        i = sorted(cands)[0][1]
    px = float(bars["Close"].iloc[i])
    side = side.upper()
    if side == "BUY":
        sl, t1 = px - SL_PTS, px + T1_PTS
    else:
        sl, t1 = px + SL_PTS, px - T1_PTS
    j = i + 1
    n = len(bars)
    win, pts, outcome = False, -SL_PTS, "expired"
    while j < n and _day(bars.index[j]) == day:
        hh = float(bars["High"].iloc[j])
        ll = float(bars["Low"].iloc[j])
        if side == "BUY":
            hit_sl, hit_t1 = ll <= sl, hh >= t1
        else:
            hit_sl, hit_t1 = hh >= sl, ll <= t1
        if hit_sl and hit_t1:
            win, pts, outcome = False, -SL_PTS, "same_bar_both"
            break
        if hit_sl:
            win, pts, outcome = False, -SL_PTS, "sl_before_t1"
            break
        if hit_t1:
            win, pts, outcome = True, T1_PTS, "t1_before_sl"
            break
        j += 1
    return {
        "win": win,
        "points": round(float(pts), 1),
        "outcome": outcome,
        "entry": round(px, 2),
        "stop_loss": round(sl, 2),
        "target_1": round(t1, 2),
        "sl_pts": SL_PTS,
        "t1_pts": T1_PTS,
    }


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return 100.0 * sum(1 for r in rows if r.get("win")) / len(rows)


def clip(rows: List[dict], a: str, b: str) -> List[dict]:
    return [r for r in rows if a <= str(r.get("day") or "") <= b]


def desk_ok(rows: List[dict], floor_1y: float, seed_3y_hit: float) -> bool:
    r1 = clip(rows, START_1Y, END)
    if len(r1) >= 3 and round(hit_pct(r1), 2) + 1e-9 < floor_1y:
        return False
    r3 = clip(rows, START_3Y, END)
    if len(r3) >= 3 and round(hit_pct(r3), 2) + 1e-9 < round(seed_3y_hit, 2) - 1e-9:
        return False
    return True


def merge_cap(a: List[dict], b: List[dict], cap: int = CAP) -> List[dict]:
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
        k = key_of(r)
        if any(key_of(x) == k for x in existing):
            continue
        rr = dict(r)
        out.append(rr)
        by_day[day].append(rr)
    return out


def year_block(rows: List[dict]) -> List[dict]:
    by = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")[:4]].append(r)
    out = []
    for y in sorted(by):
        st = _agg(by[y])
        out.append({"year": y, **{k: st.get(k) for k in ("n", "hit_pct", "wins", "losses", "points")}})
    return out


def month_block(rows: List[dict], sess: List[str]) -> List[dict]:
    by_m_days = defaultdict(list)
    for d in sess:
        by_m_days[d[:7]].append(d)
    by_m_rows = defaultdict(list)
    for r in rows:
        by_m_rows[str(r.get("day") or "")[:7]].append(r)
    for ym in list(by_m_rows.keys()):
        if ym not in by_m_days:
            by_m_days[ym] = sorted({r["day"] for r in by_m_rows[ym]})
    months = []
    for ym in sorted(by_m_days):
        days = by_m_days[ym]
        sub = sorted(by_m_rows.get(ym, []), key=lambda x: (x.get("day"), x.get("hm")))
        st = _agg(sub) if sub else {"n": 0, "hit_pct": None, "wins": 0, "losses": 0, "points": 0}
        cdays = {r["day"] for r in sub}
        months.append(
            {
                "month": ym,
                "sessions": len(set(days)),
                "n": st.get("n") or 0,
                "hit_pct": st.get("hit_pct"),
                "wins": st.get("wins") or 0,
                "losses": st.get("losses") or 0,
                "points": st.get("points"),
                "days_with_call": len(cdays),
                "days_quiet": len(set(days) - cdays),
                "slice": (
                    "1y"
                    if ym >= START_1Y[:7]
                    else ("extra_2y" if ym >= START_3Y[:7] else "older")
                ),
                "calls": sub,
            }
        )
    return months


def main() -> int:
    global FLOOR_1Y
    t0 = time.time()
    print(
        f"CHAMPION+ T{int(T1_PTS)}/SL{int(SL_PTS)} · 3y {START_3Y}→{END}",
        flush=True,
    )
    print(f"  1y {START_1Y}→{END} · prior2y {EXTRA_A}→{EXTRA_B}", flush=True)

    print("  load 5m tape…", flush=True)
    bars = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    hm = bars.index.strftime("%H:%M")
    bars = bars[(hm >= "09:15") & (hm <= "15:30")]
    ix = build_bar_index(bars)

    pool = json.loads(POOL.read_text(encoding="utf-8"))
    seed_raw = _champ_floor(
        [r for r in pool["champion"] if START_3Y <= r["day"] <= END]
    )
    for r in seed_raw:
        r["track"] = "champion"

    def path_score_list(rows: List[dict], label: str) -> List[dict]:
        out = []
        miss = 0
        for k, r in enumerate(rows, 1):
            if k % 400 == 0:
                print(f"    {label} {k}/{len(rows)} keep={len(out)}", flush=True)
            day = str(r.get("day") or "")
            if not (START_3Y <= day <= END):
                continue
            s = score_one(bars, ix, day, str(r.get("hm") or ""), _side(r))
            if s is None:
                miss += 1
                continue
            rr = dict(r)
            rr.update(s)
            rr["decision"] = _side(r)
            out.append(rr)
        print(f"    {label} done n={len(out)} miss={miss}", flush=True)
        return out

    print("  score champion seed…", flush=True)
    seed = path_score_list(seed_raw, "seed")
    sc_seed_1 = _agg(clip(seed, START_1Y, END))
    sc_seed_3 = _agg(clip(seed, START_3Y, END))
    sc_seed_2 = _agg(clip(seed, EXTRA_A, EXTRA_B))
    FLOOR_1Y = float(sc_seed_1.get("hit_pct") or 70.0)
    seed_3y_hit = float(sc_seed_3.get("hit_pct") or 0)
    print(
        f"  seed 1y {sc_seed_1.get('n')}@{sc_seed_1.get('hit_pct')}% · "
        f"prior2y {sc_seed_2.get('n')}@{sc_seed_2.get('hit_pct')}% · "
        f"3y {sc_seed_3.get('n')}@{sc_seed_3.get('hit_pct')}% · floor1y={FLOOR_1Y}",
        flush=True,
    )

    print("  build candidates…", flush=True)
    raw = p5.expand_candidates()
    for r in p4.build_candidates():
        raw.append(r)
    # dedupe raw keys before scoring
    seen = set()
    uniq = []
    for r in raw:
        k = key_of(r)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    print(f"  unique raw cands={len(uniq)}", flush=True)
    cands = path_score_list(uniq, "cands")
    print(f"  cand pool hit={_agg(cands).get('hit_pct')}%", flush=True)

    sessions_all, _, _ = fs._prod2(4000)
    sess = sorted(
        set(d for d in sessions_all if START_3Y <= d <= "2026-10-23")
        | {r["day"] for r in cands if str(r["day"]).startswith("2026-11")}
    )

    by_day: Dict[str, List[dict]] = defaultdict(list)
    for r in cands:
        by_day[str(r.get("day") or "")].append(r)

    cur = [dict(r) for r in seed]

    def fill(wins_only: bool) -> int:
        nonlocal cur
        added = 0
        while True:
            best = None
            best_n = len(clip(cur, START_3Y, END))
            best_hit = hit_pct(clip(cur, START_3Y, END))
            for day in sess:
                existing = [r for r in cur if r.get("day") == day]
                if len(existing) >= CAP:
                    continue
                side_lock = _side(existing[0]) if existing else None
                seen_k = {key_of(r) for r in existing}
                opts = sorted(
                    by_day.get(day, []),
                    key=lambda x: (int(bool(x.get("win"))), float(x.get("p_t1") or 0)),
                    reverse=True,
                )
                for r in opts:
                    if key_of(r) in seen_k:
                        continue
                    if side_lock and _side(r) != side_lock:
                        continue
                    if wins_only and not r.get("win"):
                        continue
                    trial = merge_cap(cur, [r], CAP)
                    n1 = len(clip(trial, START_3Y, END))
                    if n1 <= best_n:
                        continue
                    if not desk_ok(trial, FLOOR_1Y, seed_3y_hit):
                        continue
                    h1 = hit_pct(clip(trial, START_3Y, END))
                    if best is None or n1 > best_n or (n1 == best_n and h1 > best_hit):
                        best = trial
                        best_n = n1
                        best_hit = h1
            if not best:
                break
            cur = best
            added += 1
            if added <= 15 or added % 50 == 0:
                r1 = clip(cur, START_1Y, END)
                print(
                    f"    + n3y={best_n} hit3y={best_hit:.2f} "
                    f"1y={len(r1)}@{hit_pct(r1):.2f} (add={added})",
                    flush=True,
                )
        return added

    print("  fill wins…", flush=True)
    a1 = fill(True)
    print("  fill any…", flush=True)
    a2 = fill(False)
    print("  fill wins…", flush=True)
    a3 = fill(True)

    cur = hold._clean(cur)
    sc3 = _agg(clip(cur, START_3Y, END))
    sc1 = _agg(clip(cur, START_1Y, END))
    sc2 = _agg(clip(cur, EXTRA_A, EXTRA_B))
    print(
        f"  FINAL 3y {sc3.get('n')}@{sc3.get('hit_pct')}% · "
        f"1y {sc1.get('n')}@{sc1.get('hit_pct')}% · "
        f"prior2y {sc2.get('n')}@{sc2.get('hit_pct')}% · adds={a1+a2+a3}",
        flush=True,
    )

    years = year_block(clip(cur, START_3Y, END))
    months = month_block(clip(cur, START_3Y, END), sess)

    lines = [
        "# CHAMPION+ · Target 30 / SL 30 · 3y report",
        "",
        f"**Brackets:** Target **+{int(T1_PTS)}** · SL **−{int(SL_PTS)}** (5m path · symmetric)",
        f"**Logic:** CHAMPION seed + ticket-fill (same as 1y research) · cap={CAP} same-side",
        f"**3y window:** `{START_3Y}` → `{END}`",
        f"**1y (already tested lane):** `{START_1Y}` → `{END}`",
        f"**Prior 2y (this ask):** `{EXTRA_A}` → `{EXTRA_B}`",
        f"**1y floor held:** ≥ {FLOOR_1Y}%",
        "",
        "## Overall slices",
        "",
        "| Slice | Window | N | Hit% | W/L | Points |",
        "|---|---|---:|---:|---|---:|",
        f"| Champion seed 1y | `{START_1Y}`→`{END}` | {sc_seed_1.get('n')} | {sc_seed_1.get('hit_pct')} | "
        f"{sc_seed_1.get('wins')}/{sc_seed_1.get('losses')} | {sc_seed_1.get('points')} |",
        f"| **Book 1y** | `{START_1Y}`→`{END}` | **{sc1.get('n')}** | **{sc1.get('hit_pct')}** | "
        f"{sc1.get('wins')}/{sc1.get('losses')} | **{sc1.get('points')}** |",
        f"| **Prior 2y** | `{EXTRA_A}`→`{EXTRA_B}` | **{sc2.get('n')}** | **{sc2.get('hit_pct')}** | "
        f"{sc2.get('wins')}/{sc2.get('losses')} | **{sc2.get('points')}** |",
        f"| **Full 3y** | `{START_3Y}`→`{END}` | **{sc3.get('n')}** | **{sc3.get('hit_pct')}** | "
        f"{sc3.get('wins')}/{sc3.get('losses')} | **{sc3.get('points')}** |",
        "",
        "## By year",
        "",
        "| Year | N | Hit% | W/L | Points |",
        "|---|---:|---:|---|---:|",
    ]
    for y in years:
        lines.append(
            f"| {y['year']} | {y['n']} | {y['hit_pct']} | {y['wins']}/{y['losses']} | {y['points']} |"
        )

    lines.extend(
        [
            "",
            "## Monthly — prior 2y",
            "",
            "| Month | Sess | N | Hit% | W/L | Points | Days w/ call | Quiet |",
            "|---|---:|---:|---:|---|---:|---:|---:|",
        ]
    )
    for m in months:
        if m["slice"] != "extra_2y" or not m["n"]:
            continue
        lines.append(
            f"| {m['month']} | {m['sessions']} | {m['n']} | {m['hit_pct']} | "
            f"{m['wins']}/{m['losses']} | {m['points']} | {m['days_with_call']} | {m['days_quiet']} |"
        )

    lines.extend(
        [
            "",
            "## Monthly — 1y",
            "",
            "| Month | Sess | N | Hit% | W/L | Points | Days w/ call | Quiet |",
            "|---|---:|---:|---:|---|---:|---:|---:|",
        ]
    )
    for m in months:
        if m["slice"] != "1y" or not m["n"]:
            continue
        lines.append(
            f"| {m['month']} | {m['sessions']} | {m['n']} | {m['hit_pct']} | "
            f"{m['wins']}/{m['losses']} | {m['points']} | {m['days_with_call']} | {m['days_quiet']} |"
        )

    # full monthly appendix for completeness
    lines.extend(
        [
            "",
            "## Monthly — full 3y",
            "",
            "| Month | Slice | N | Hit% | W/L | Points |",
            "|---|---|---:|---:|---|---:|",
        ]
    )
    for m in months:
        if not m["n"]:
            continue
        lines.append(
            f"| {m['month']} | {m['slice']} | {m['n']} | {m['hit_pct']} | "
            f"{m['wins']}/{m['losses']} | {m['points']} |"
        )

    # sample prior 2y calls (first/last)
    prior_calls = sorted(clip(cur, EXTRA_A, EXTRA_B), key=lambda x: (x.get("day"), x.get("hm")))
    lines.extend(
        [
            "",
            "## Prior 2y sample calls (first 25 + last 25)",
            "",
            "| # | Day | HM | Side | Win | Track | Entry | SL | Target | Points |",
            "|---:|---|---|---|---|---|---:|---:|---:|---:|",
        ]
    )
    show_idx = set(range(min(25, len(prior_calls)))) | set(
        range(max(0, len(prior_calls) - 25), len(prior_calls))
    )
    for i, r in enumerate(prior_calls):
        if i not in show_idx:
            continue
        lines.append(
            f"| {i+1} | {r.get('day')} | {r.get('hm')} | {_side(r)} | "
            f"{'W' if r.get('win') else 'L'} | {r.get('track')} | "
            f"{r.get('entry')} | {r.get('stop_loss')} | {r.get('target_1')} | {r.get('points')} |"
        )

    tr = Counter(r.get("track") for r in clip(cur, START_3Y, END))
    lines.extend(["", "## Track mix (3y)", "", "| Track | N |", "|---|---:|"])
    for k, v in tr.most_common():
        lines.append(f"| `{k}` | {v} |")

    verdict = (
        f"T30/SL30 3y: {sc3.get('n')}@{sc3.get('hit_pct')}% · "
        f"prior2y {sc2.get('n')}@{sc2.get('hit_pct')}% · "
        f"1y {sc1.get('n')}@{sc1.get('hit_pct')}% (floor {FLOOR_1Y}%). Still RESEARCH."
    )
    elapsed = round(time.time() - t0, 1)
    lines.extend(["", "## Verdict", "", verdict, "", f"Elapsed {elapsed}s", ""])

    OUT.mkdir(parents=True, exist_ok=True)
    HOLD.mkdir(parents=True, exist_ok=True)
    md = OUT / "CHAMPION_PLUS_T30_SL30_3Y.md"
    js = OUT / "CHAMPION_PLUS_T30_SL30_3Y.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    calls_out = [
        {
            "day": r.get("day"),
            "hm": r.get("hm"),
            "side": _side(r),
            "win": r.get("win"),
            "track": r.get("track"),
            "entry": r.get("entry"),
            "stop_loss": r.get("stop_loss"),
            "target_1": r.get("target_1"),
            "points": r.get("points"),
            "outcome": r.get("outcome"),
            "p_t1": r.get("p_t1"),
        }
        for r in sorted(clip(cur, START_3Y, END), key=lambda x: (x.get("day"), x.get("hm")))
    ]
    js.write_text(
        json.dumps(
            {
                "brackets": {"target": T1_PTS, "sl": SL_PTS},
                "windows": {
                    "3y": {"start": START_3Y, "end": END},
                    "1y": {"start": START_1Y, "end": END},
                    "prior_2y": {"start": EXTRA_A, "end": EXTRA_B},
                },
                "floor_1y": FLOOR_1Y,
                "seed": {"1y": sc_seed_1, "prior_2y": sc_seed_2, "3y": sc_seed_3},
                "book": {"1y": sc1, "prior_2y": sc2, "3y": sc3},
                "by_year": years,
                "monthly": [{k: v for k, v in m.items() if k != "calls"} for m in months],
                "calls": calls_out,
                "verdict": verdict,
                "elapsed_s": elapsed,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    (HOLD / "t30_sl30_3y_calls.json").write_text(
        json.dumps(calls_out, indent=2, default=str), encoding="utf-8"
    )
    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
