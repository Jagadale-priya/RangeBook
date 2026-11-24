"""Rescore CHAMPION+ book with fixed Target=30 · SL=20 on 5m tape.

Same call keys (day/hm/side) as monthly-to-date book; path replay with
asymmetric brackets. Report overall + monthly.

  python -u prod_live/tests/builders/research_champion_plus_t30_sl20.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

from accuracy_max_6m import _agg  # noqa: E402
from research_confirm_dual_tf_deep import _side  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    _day,
    _norm,
    build_bar_index,
)
import research_nifty_final_stack_2y as fs  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
HOLD = ROOT / "prod_live" / "holding_accurate" / "champion_plus"
SRC = OUT / "CHAMPION_PLUS_MONTHLY_TODATE.json"
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"

T1_PTS = 30.0
SL_PTS = 20.0
START = "2025-10-24"
END = "2026-11-15"


def load_calls() -> List[dict]:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    out = []
    for m in data.get("monthly") or []:
        for r in m.get("calls") or []:
            out.append(
                {
                    "day": r["day"],
                    "hm": r["hm"],
                    "decision": r.get("side") or r.get("decision"),
                    "track": r.get("track"),
                    "p_t1": r.get("p_t1"),
                    "old_win": r.get("win"),
                    "old_points": r.get("points"),
                    "old_entry": r.get("entry"),
                    "old_sl": r.get("stop_loss"),
                    "old_t1": r.get("target_1"),
                }
            )
    return out


def score_asymmetric(
    bars: pd.DataFrame,
    ix: Dict[Tuple[str, str], int],
    *,
    day: str,
    hm: str,
    side: str,
    entry: Optional[float] = None,
) -> Optional[dict]:
    """Path score with T1=30 and SL=20 (asymmetric)."""
    i = ix.get((day, hm))
    if i is None:
        # nearest same-day bar at/after hm
        target = hm
        cands = [(h, j) for (d, h), j in ix.items() if d == day and h >= target]
        if not cands:
            cands = [(h, j) for (d, h), j in ix.items() if d == day]
        if not cands:
            return None
        i = sorted(cands)[0][1]
    px = float(bars["Close"].iloc[i]) if entry is None else float(entry)
    side = side.upper()
    if side == "BUY":
        sl, t1 = px - SL_PTS, px + T1_PTS
    else:
        sl, t1 = px + SL_PTS, px - T1_PTS

    j = i + 1
    n = len(bars)
    win = False
    pts = -SL_PTS
    outcome = "expired"
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
        "risk_note": f"T{int(T1_PTS)}_SL{int(SL_PTS)}",
    }


def month_block(rows: List[dict], sess: List[str]) -> List[dict]:
    by_m_days = defaultdict(list)
    for d in sess:
        by_m_days[d[:7]].append(d)
    by_m_rows = defaultdict(list)
    for r in rows:
        by_m_rows[str(r.get("day") or "")[:7]].append(r)
    # include months that only appear in rows (nov proxy)
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
                "calls": sub,
            }
        )
    return months


def main() -> int:
    t0 = time.time()
    print(f"CHAMPION+ rescore T{int(T1_PTS)} / SL{int(SL_PTS)} · {START}→{END}", flush=True)
    calls = load_calls()
    print(f"  calls={len(calls)}", flush=True)

    print("  load 5m tape…", flush=True)
    bars = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    # session hours
    hm = bars.index.strftime("%H:%M")
    bars = bars[(hm >= "09:15") & (hm <= "15:30")]
    ix = build_bar_index(bars)
    print(f"  bars={len(bars)} ix={len(ix)}", flush=True)

    scored = []
    miss = 0
    flipped = 0
    for k, r in enumerate(calls, 1):
        if k % 100 == 0:
            print(f"  score {k}/{len(calls)}", flush=True)
        side = _side(r)
        # prefer close at hm; ignore old entry so brackets are clean T30/SL20 from signal bar
        s = score_asymmetric(bars, ix, day=str(r["day"]), hm=str(r["hm"]), side=side, entry=None)
        if s is None:
            # fallback: path_score_row with custom via entry from old if bar missing
            miss += 1
            continue
        rr = dict(r)
        rr.update(s)
        rr["side"] = side
        if bool(rr.get("old_win")) != bool(rr.get("win")):
            flipped += 1
        scored.append(rr)

    print(f"  scored={len(scored)} miss={miss} flipped_vs_old={flipped}", flush=True)
    overall = _agg(scored)
    old_wins = sum(1 for r in scored if r.get("old_win"))
    print(
        f"  NEW {overall.get('n')}@{overall.get('hit_pct')}% pts={overall.get('points')} "
        f"(old wins on same set≈{old_wins})",
        flush=True,
    )

    sessions_all, _, _ = fs._prod2(4000)
    sess = sorted(d for d in sessions_all if START <= d <= "2026-10-23")
    # add nov days from scored
    sess = sorted(set(sess) | {r["day"] for r in scored if str(r["day"]).startswith("2026-11")})
    months = month_block(scored, sess)

    lines = [
        "# CHAMPION+ — Target 30 / SL 20 path rescore",
        "",
        f"**Same calls** as monthly-to-date book · **new brackets:** Target **+{int(T1_PTS)}** · SL **−{int(SL_PTS)}**",
        f"**Tape:** 5m NIFTY · window `{START}` → `{END}`",
        f"**Scored:** {len(scored)} / {len(calls)} · flipped vs old outcome: {flipped}",
        "",
        "## Overall",
        "",
        "| Metric | Old brackets* | **T30 / SL20** |",
        "|---|---:|---:|",
    ]
    # old approx from source file
    src = json.loads(SRC.read_text(encoding="utf-8"))
    old = src.get("overall") or {}
    lines.extend(
        [
            f"| N | {old.get('n')} | **{overall.get('n')}** |",
            f"| Hit% | {old.get('hit_pct')} | **{overall.get('hit_pct')}** |",
            f"| W/L | {old.get('wins')}/{old.get('losses')} | "
            f"**{overall.get('wins')}/{overall.get('losses')}** |",
            f"| Points | {old.get('points')} | **{overall.get('points')}** |",
            "",
            "\\* Old = mixed native risks (~20–30+ pts per ticket).",
            "",
            "## Monthly scorecard (T30 / SL20)",
            "",
            "| Month | N | Hit% | W/L | Points | Days w/ call |",
            "|---|---:|---:|---|---:|---:|",
        ]
    )
    for m in months:
        if not m["n"]:
            continue
        lines.append(
            f"| {m['month']} | {m['n']} | {m['hit_pct']} | "
            f"{m['wins']}/{m['losses']} | {m['points']} | {m['days_with_call']} |"
        )

    for m in months:
        if not m["n"]:
            continue
        lines.extend(
            [
                "",
                f"## {m['month']} — calls (T30/SL20)",
                "",
                f"N={m['n']} · hit {m['hit_pct']}% · points {m['points']}",
                "",
                "| # | Day | HM | Side | Win | OldW | Track | Entry | SL (−20) | Target (+30) | Points | Outcome |",
                "|---:|---|---|---|---|---|---|---:|---:|---:|---:|---|",
            ]
        )
        for i, r in enumerate(m["calls"], 1):
            lines.append(
                f"| {i} | {r.get('day')} | {r.get('hm')} | {r.get('side')} | "
                f"{'W' if r.get('win') else 'L'} | "
                f"{'W' if r.get('old_win') else 'L'} | {r.get('track')} | "
                f"{r.get('entry')} | {r.get('stop_loss')} | {r.get('target_1')} | "
                f"{r.get('points')} | {r.get('outcome')} |"
            )

    verdict = (
        f"T30/SL20 → {overall.get('n')}@{overall.get('hit_pct')}% · "
        f"{overall.get('wins')}W/{overall.get('losses')}L · pts {overall.get('points')} "
        f"(was {old.get('n')}@{old.get('hit_pct')}% · pts {old.get('points')})."
    )
    elapsed = round(time.time() - t0, 1)
    lines.extend(["", "## Verdict", "", verdict, "", f"Elapsed {elapsed}s", ""])

    md = OUT / "CHAMPION_PLUS_T30_SL20.md"
    js = OUT / "CHAMPION_PLUS_T30_SL20.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(
        json.dumps(
            {
                "brackets": {"target": T1_PTS, "sl": SL_PTS},
                "overall": overall,
                "old_overall": old,
                "flipped": flipped,
                "miss": miss,
                "monthly": [
                    {k: v for k, v in m.items() if k != "calls"}
                    for m in months
                    if m["n"]
                ],
                "calls": [
                    {
                        "day": r.get("day"),
                        "hm": r.get("hm"),
                        "side": r.get("side"),
                        "win": r.get("win"),
                        "old_win": r.get("old_win"),
                        "track": r.get("track"),
                        "entry": r.get("entry"),
                        "stop_loss": r.get("stop_loss"),
                        "target_1": r.get("target_1"),
                        "points": r.get("points"),
                        "outcome": r.get("outcome"),
                    }
                    for r in scored
                ],
                "verdict": verdict,
                "elapsed_s": elapsed,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    (HOLD / "t30_sl20_calls.json").write_text(
        json.dumps(
            [
                {
                    "day": r.get("day"),
                    "hm": r.get("hm"),
                    "side": r.get("side"),
                    "win": r.get("win"),
                    "points": r.get("points"),
                    "entry": r.get("entry"),
                    "stop_loss": r.get("stop_loss"),
                    "target_1": r.get("target_1"),
                    "outcome": r.get("outcome"),
                    "track": r.get("track"),
                }
                for r in scored
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
