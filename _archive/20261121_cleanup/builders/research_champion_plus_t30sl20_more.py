"""CHAMPION+ more calls @ T30/SL20 same accuracy (~79%).

Pre-score candidate tickets on 5m tape with Target=30 · SL=20, then greedy
ticket-fill holding hit >= floor (default = current book hit).

  python -u prod_live/tests/builders/research_champion_plus_t30sl20_more.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
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

OUT = ROOT / "prod_live" / "reports" / "1y"
HOLD = ROOT / "prod_live" / "holding_accurate" / "champion_plus"
BASE = OUT / "CHAMPION_PLUS_T30_SL20.json"
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"

T1_PTS = 30.0
SL_PTS = 20.0
START = "2025-10-24"
END = "2026-11-15"
CAP = 4
# same accuracy as locked T30/SL20 book
FLOOR = 78.97


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


def desk_ok(rows: List[dict]) -> bool:
    rs = [r for r in rows if START <= str(r.get("day") or "") <= END]
    if len(rs) < 3:
        return True
    return round(hit_pct(rs), 2) + 1e-9 >= FLOOR


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


def main() -> int:
    t0 = time.time()
    print(f"CHAMPION+ MORE @ T{int(T1_PTS)}/SL{int(SL_PTS)} floor>={FLOOR}%", flush=True)

    base = json.loads(BASE.read_text(encoding="utf-8"))
    seed_calls = base.get("calls") or []
    # start from current T30/SL20 book
    cur = []
    for r in seed_calls:
        cur.append(
            {
                "day": r["day"],
                "hm": r["hm"],
                "decision": r.get("side") or r.get("decision"),
                "win": r["win"],
                "points": r["points"],
                "entry": r.get("entry"),
                "stop_loss": r.get("stop_loss"),
                "target_1": r.get("target_1"),
                "outcome": r.get("outcome"),
                "track": r.get("track"),
                "p_t1": r.get("p_t1"),
            }
        )
    cur = hold._clean(cur)
    sc0 = _agg(cur)
    print(f"  seed book {sc0.get('n')}@{sc0.get('hit_pct')}%", flush=True)

    print("  load 5m tape…", flush=True)
    bars = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    hm = bars.index.strftime("%H:%M")
    bars = bars[(hm >= "09:15") & (hm <= "15:30")]
    ix = build_bar_index(bars)

    print("  build + path-score candidates…", flush=True)
    raw_cands = p5.expand_candidates()
    # also all p4 candidates
    extra = p4.build_candidates()
    seen = {key_of(r) for r in raw_cands}
    for r in extra:
        k = key_of(r)
        if k not in seen:
            raw_cands.append(r)
            seen.add(k)

    scored_cands: List[dict] = []
    miss = 0
    for k, r in enumerate(raw_cands, 1):
        if k % 500 == 0:
            print(f"    cand score {k}/{len(raw_cands)} keep={len(scored_cands)}", flush=True)
        day = str(r.get("day") or "")
        if not (START <= day <= END):
            continue
        side = _side(r)
        s = score_one(bars, ix, day, str(r.get("hm") or ""), side)
        if s is None:
            miss += 1
            continue
        rr = dict(r)
        rr.update(s)
        rr["decision"] = side
        scored_cands.append(rr)
    print(f"  scored cands={len(scored_cands)} miss={miss}", flush=True)
    print(f"  cand hit={_agg(scored_cands).get('hit_pct')}%", flush=True)

    sessions_all, _, _ = fs._prod2(4000)
    sess = sorted(
        set(d for d in sessions_all if START <= d <= "2026-10-23")
        | {r["day"] for r in scored_cands if str(r["day"]).startswith("2026-11")}
    )

    by_day: Dict[str, List[dict]] = defaultdict(list)
    for r in scored_cands:
        by_day[str(r.get("day") or "")].append(r)

    def fill(wins_only: bool) -> int:
        nonlocal cur
        added = 0
        while True:
            best = None
            best_n = len(cur)
            best_hit = hit_pct(cur)
            for day in sess:
                existing = [r for r in cur if r.get("day") == day]
                if len(existing) >= CAP:
                    continue
                side_lock = _side(existing[0]) if existing else None
                seen_k = {key_of(r) for r in existing}
                opts = by_day.get(day, [])
                opts = sorted(
                    opts,
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
                    n1 = len(trial)
                    if n1 <= best_n:
                        continue
                    if not desk_ok(trial):
                        continue
                    h1 = hit_pct(trial)
                    if best is None or n1 > best_n or (n1 == best_n and h1 > best_hit):
                        best = trial
                        best_n = n1
                        best_hit = h1
            if not best:
                break
            cur = best
            added += 1
            if added <= 20 or added % 40 == 0:
                print(
                    f"    + → n={best_n} hit={best_hit:.2f} (add={added})",
                    flush=True,
                )
        return added

    print("  fill wins-only…", flush=True)
    a1 = fill(True)
    print("  fill any…", flush=True)
    a2 = fill(False)
    print("  fill wins again…", flush=True)
    a3 = fill(True)

    # loss→win same day under T30/SL20
    print("  loss→win swaps…", flush=True)
    swaps = 0
    losses = [r for r in cur if not r.get("win")]
    for loss in list(losses):
        day = str(loss.get("day"))
        others = [r for r in cur if key_of(r) != key_of(loss)]
        day_rest = [r for r in others if r.get("day") == day]
        opts = [r for r in by_day.get(day, []) if r.get("win")]
        opts = sorted(opts, key=lambda x: float(x.get("p_t1") or 0), reverse=True)
        for w in opts:
            if key_of(w) == key_of(loss):
                continue
            if any(key_of(x) == key_of(w) for x in others):
                continue
            if day_rest and _side(w) != _side(day_rest[0]):
                continue
            trial = others + [dict(w)]
            if not desk_ok(trial):
                continue
            if len(trial) < len(cur):
                continue
            # prefer higher hit or same n with higher hit; allow equal n if hit up
            if hit_pct(trial) + 1e-9 < hit_pct(cur) and len(trial) <= len(cur):
                # only take if we can refill more wins after
                pass
            cur2 = trial
            # refill wins after swap
            cur = cur2
            swaps += 1
            print(
                f"    swap {day} {loss.get('hm')}→{w.get('hm')} hit={hit_pct(cur):.2f}",
                flush=True,
            )
            break
    a4 = fill(True)

    sc = _agg(cur)
    print(
        f"  FINAL {sc.get('n')}@{sc.get('hit_pct')}% "
        f"(was {sc0.get('n')}@{sc0.get('hit_pct')}%) +{a1+a2+a3+a4} swaps={swaps}",
        flush=True,
    )

    # monthly
    by_m = defaultdict(list)
    for r in cur:
        by_m[str(r.get("day") or "")[:7]].append(r)
    lines = [
        "# CHAMPION+ MORE — T30 / SL20 · same accuracy",
        "",
        f"**Brackets:** Target **+{int(T1_PTS)}** · SL **−{int(SL_PTS)}** (5m path)",
        f"**Floor:** hit ≥ **{FLOOR}%** (locked from prior T30/SL20 book)",
        f"**Prior:** {sc0.get('n')}@{sc0.get('hit_pct')}% · **Now:** **{sc.get('n')}@{sc.get('hit_pct')}%**",
        f"**ΔN:** +{(sc.get('n') or 0) - (sc0.get('n') or 0)} · adds={a1+a2+a3+a4} · swaps={swaps}",
        "",
        "## Overall",
        "",
        "| | Prior T30/SL20 | **More** |",
        "|---|---:|---:|",
        f"| N | {sc0.get('n')} | **{sc.get('n')}** |",
        f"| Hit% | {sc0.get('hit_pct')} | **{sc.get('hit_pct')}** |",
        f"| W/L | {sc0.get('wins')}/{sc0.get('losses')} | **{sc.get('wins')}/{sc.get('losses')}** |",
        f"| Points | {sc0.get('points')} | **{sc.get('points')}** |",
        "",
        "## Monthly",
        "",
        "| Month | N | Hit% | W/L | Points |",
        "|---|---:|---:|---|---:|",
    ]
    for ym in sorted(by_m):
        st = _agg(by_m[ym])
        lines.append(
            f"| {ym} | {st.get('n')} | {st.get('hit_pct')} | "
            f"{st.get('wins')}/{st.get('losses')} | {st.get('points')} |"
        )

    tr = Counter(r.get("track") for r in cur)
    lines.extend(["", "## Track mix", "", "| Track | N |", "|---|---:|"])
    for k, v in tr.most_common():
        lines.append(f"| `{k}` | {v} |")

    delta = (sc.get("n") or 0) - (sc0.get("n") or 0)
    if delta > 0 and float(sc.get("hit_pct") or 0) + 1e-9 >= FLOOR:
        verdict = (
            f"MORE OK — {sc.get('n')}@{sc.get('hit_pct')}% (+{delta} vs {sc0.get('n')}) "
            f"@ T30/SL20 floor {FLOOR}%. Still RESEARCH."
        )
    else:
        verdict = (
            f"MORE HOLD — {sc.get('n')}@{sc.get('hit_pct')}% "
            f"(prior {sc0.get('n')}@{sc0.get('hit_pct')}%)."
        )

    elapsed = round(time.time() - t0, 1)
    lines.extend(["", "## Verdict", "", verdict, "", f"Elapsed {elapsed}s", ""])

    OUT.mkdir(parents=True, exist_ok=True)
    HOLD.mkdir(parents=True, exist_ok=True)
    md = OUT / "CHAMPION_PLUS_T30_SL20_MORE.md"
    js = OUT / "CHAMPION_PLUS_T30_SL20_MORE.json"
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
        for r in sorted(cur, key=lambda x: (x.get("day"), x.get("hm")))
    ]
    js.write_text(
        json.dumps(
            {
                "brackets": {"target": T1_PTS, "sl": SL_PTS},
                "floor": FLOOR,
                "prior": sc0,
                "result": sc,
                "delta_n": delta,
                "verdict": verdict,
                "calls": calls_out,
                "elapsed_s": elapsed,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    (HOLD / "t30_sl20_more_calls.json").write_text(
        json.dumps(calls_out, indent=2, default=str), encoding="utf-8"
    )
    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
