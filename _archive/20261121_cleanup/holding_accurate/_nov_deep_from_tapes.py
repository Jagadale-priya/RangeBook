"""Nov 2026 deep calls from tapes: LIVE crown/pool + 1-day empty-fill + ACC report.

Uses 5m/daily for sessions (frozen prod2 pool ends ~Oct 23).
Consumes live stack JSON if present from fno_nifty_nov1_stack_live_report.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
import path_setup  # noqa: F401,E402

from accuracy_max_6m import POOL, PRIORITY  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
from prod_live.logic.empty_fill import (  # noqa: E402
    ENTRY_HM,
    GAP_MIN_PCT,
    RISK,
    TAG as FILL_TAG,
    build_empty_fill_row,
    merge_stack_plus_empty_fill,
)

OUT = ROOT / "prod_live" / "reports" / "nov1_14"
DAILY = ROOT / "stock_signal_data/fno_validate/NIFTY_daily_nse.csv"
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"
LIVE_JSON = ROOT / "stock_signal_data/fno_validate/research/fno_nifty_nov1_stack_live_report.json"
PRI_JSON = ROOT / "prod_live" / "reports" / "1y" / "ACC_PRIORITY_LEVELS_6M_1Y.json"

START = "2026-11-01"
END = "2026-11-15"


def _hm_mins(hm: str) -> int:
    try:
        h, m = str(hm).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0


def load_bars5() -> pd.DataFrame:
    df = pd.read_csv(TAPE5)
    df["date"] = pd.to_datetime(df["date"])
    if df["date"].dt.tz is None:
        df["date"] = df["date"].dt.tz_localize("Asia/Kolkata")
    else:
        df["date"] = df["date"].dt.tz_convert("Asia/Kolkata")
    df = df.set_index("date").sort_index()
    df["_day"] = [ts.strftime("%Y-%m-%d") for ts in df.index]
    df["_hm"] = [ts.strftime("%H:%M") for ts in df.index]
    return df


def sessions_from_bars(bars5: pd.DataFrame) -> List[str]:
    days = sorted({d for d in bars5["_day"].unique() if START <= d <= END})
    # require morning session bars
    out = []
    for d in days:
        sess = bars5[(bars5["_day"] == d) & (bars5["_hm"] >= "09:15") & (bars5["_hm"] <= "15:15")]
        if len(sess) >= 4:
            out.append(d)
    return out


def load_daily_gap(bars5: pd.DataFrame, sess: List[str]) -> Dict[str, dict]:
    d = pd.read_csv(DAILY)
    d["Date"] = pd.to_datetime(d["Date"]).dt.strftime("%Y-%m-%d")
    d = d.sort_values("Date")
    by_date = {}
    prev_c = None
    for _, r in d.iterrows():
        day = str(r["Date"])[:10]
        o, c = float(r["Open"]), float(r["Close"])
        gap = None if prev_c is None or prev_c <= 0 else (o - prev_c) / prev_c * 100.0
        by_date[day] = {"open": o, "close": c, "prior_close": prev_c, "gap_pct": None if gap is None else round(gap, 4)}
        prev_c = c
    # fill missing Nov days from 5m (open = first 09:15, prior = prev session last close)
    all_days = sorted(set(bars5["_day"].unique()))
    for day in sess:
        if day in by_date and by_date[day].get("prior_close") is not None:
            continue
        day_bars = bars5[(bars5["_day"] == day) & (bars5["_hm"] >= "09:15")]
        if day_bars.empty:
            continue
        o = float(day_bars["Open"].iloc[0])
        # prior session close
        prev_days = [x for x in all_days if x < day]
        if not prev_days:
            continue
        prev = prev_days[-1]
        prev_bars = bars5[(bars5["_day"] == prev) & (bars5["_hm"] <= "15:30")]
        if prev_bars.empty:
            continue
        pc = float(prev_bars["Close"].iloc[-1])
        gap = (o - pc) / pc * 100.0
        by_date[day] = {"open": o, "close": float(day_bars["Close"].iloc[-1]), "prior_close": pc, "gap_pct": round(gap, 4)}
    return by_date


def path_score(bars5: pd.DataFrame, day: str, hm: str, side: str, entry: float, risk: float) -> Tuple[Optional[bool], Optional[float], str]:
    day_bars = bars5[bars5["_day"] == day]
    if day_bars.empty:
        return None, None, "no_bars"
    target = _hm_mins(hm)
    idxs = [i for i, ts in enumerate(day_bars.index) if _hm_mins(ts.strftime("%H:%M")) >= target]
    if not idxs:
        return None, None, "no_entry_bar"
    i0 = idxs[0]
    entry_px = float(entry)
    sl = entry_px - risk if side == "BUY" else entry_px + risk
    t1 = entry_px + risk if side == "BUY" else entry_px - risk
    fut = day_bars.iloc[i0 + 1 :]
    if fut.empty:
        return False, -risk, "no_future"
    for _, row in fut.iterrows():
        hi, lo = float(row["High"]), float(row["Low"])
        if side == "BUY":
            hit_sl, hit_t1 = lo <= sl, hi >= t1
            if hit_sl and hit_t1:
                return False, -risk, "same_bar_both"
            if hit_sl:
                return False, -risk, "sl_before_t1"
            if hit_t1:
                return True, risk, "t1_before_sl"
        else:
            hit_sl, hit_t1 = hi >= sl, lo <= t1
            if hit_sl and hit_t1:
                return False, -risk, "same_bar_both"
            if hit_sl:
                return False, -risk, "sl_before_t1"
            if hit_t1:
                return True, risk, "t1_before_sl"
    return False, -risk, "expired"


def stack_from_live_json() -> List[dict]:
    if not LIVE_JSON.exists():
        return []
    data = json.loads(LIVE_JSON.read_text(encoding="utf-8"))
    calls = data.get("calls") or data.get("live_calls") or data.get("stack") or []
    out = []
    for r in calls:
        day = str(r.get("day") or "")
        if START <= day <= END:
            rr = dict(r)
            rr["lane"] = "LIVE"
            rr["desk_tag"] = "STACK_PLUS_CROWN_HTF_CAP2"
            track = str(rr.get("track") or "")
            tags = ["STACK_PLUS_CROWN_HTF_CAP2", track, "LOGIC_LIVE"]
            if track == "proven_100":
                tags += ["PROVEN_100", "ACC_RANGE_100_100"]
                rr["accurate_tag"] = "PROVEN_100"
                rr["accuracy_tag"] = "ACC_RANGE_100_100"
            rr["tags"] = tags
            out.append(rr)
    return out


def stack_from_pool_fallback(sess: List[str], active: Set[str]) -> List[dict]:
    """Frozen pool: only Nov crown on 11-06 typically."""
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    rows = []
    for r in pool.get("proven_100") or []:
        if START <= r["day"] <= END and r["day"] in sess:
            rows.append(dict(r, track="proven_100", priority=PRIORITY["proven_100"]))
    for r in pool.get("champion") or []:
        if START <= r["day"] <= END and r["day"] in sess:
            rows.append(dict(r, track="champion", priority=PRIORITY["champion"]))
    for r in pool.get("crown_5m") or []:
        if START <= r["day"] <= END and r["day"] in sess and r["day"] in active:
            rows.append(dict(r, track="crown_5m", priority=PRIORITY["crown_5m"]))
    if not rows:
        return []
    stack = fs._union(
        {
            "proven_100": [r for r in rows if r["track"] == "proven_100"],
            "good_prod2": [],
            "champion": [r for r in rows if r["track"] == "champion"],
            "crown_5m": [r for r in rows if r["track"] == "crown_5m"],
        },
        day_cap=2,
    )
    out = []
    for r in stack:
        rr = dict(r)
        if "win" not in rr and rr.get("outcome") == "t1_before_sl":
            rr["win"] = True
        elif "win" not in rr and rr.get("outcome") in ("sl_before_t1", "same_bar_both"):
            rr["win"] = False
        # keep pool points; if missing but win known, use risk distance
        if rr.get("points") is None and rr.get("win") is True:
            try:
                e = float(rr.get("entry") or 0)
                t1 = float(rr.get("target_1") or 0)
                rr["points"] = abs(t1 - e) if t1 and e else 20.0
            except Exception:
                rr["points"] = 20.0
        rr["lane"] = "LIVE"
        rr["desk_tag"] = "STACK_PLUS_CROWN_HTF_CAP2"
        rr["tags"] = ["STACK_PLUS_CROWN_HTF_CAP2", rr.get("track"), "LOGIC_LIVE", "SOURCE_POOL"]
        out.append(rr)
    return out


def build_fills(sess, stack_days, daily_gap, bars5):
    fills = []
    for day in sess:
        if day in stack_days:
            continue
        info = daily_gap.get(day) or {}
        o, prev = info.get("open"), info.get("prior_close")
        if o is None or prev is None:
            continue
        day_bars = bars5[(bars5["_day"] == day) & (bars5["_hm"] >= ENTRY_HM)]
        if day_bars.empty:
            continue
        entry_px = float(day_bars["Close"].iloc[0])
        row = build_empty_fill_row(
            day=day, open_px=float(o), prior_close=float(prev), entry_px=entry_px
        )
        if not row:
            continue
        win, pts, outcome = path_score(bars5, day, ENTRY_HM, row["decision"], entry_px, RISK)
        row.update(
            {
                "win": win,
                "points": pts,
                "outcome": outcome,
                "desk_tag": FILL_TAG,
                "lane": "HOLDING",
                "logic_level": "EMPTY_FILL",
                "tags": [FILL_TAG, "LOGIC_EMPTY_FILL", "ONE_DAY_CALL"],
            }
        )
        fills.append(row)
    return fills


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("Loading 5m + gaps…", flush=True)
    bars5 = load_bars5()
    sess = sessions_from_bars(bars5)
    daily_gap = load_daily_gap(bars5, sess)
    print("sessions", sess)

    daily = fs._load_daily()
    active = fs._active_days(sess, daily) if sess else set()

    live_stack = stack_from_live_json()
    source = "live_report_json" if live_stack else "pool_fallback"
    if not live_stack:
        live_stack = stack_from_pool_fallback(sess, active)
    print(f"LIVE stack source={source} n={len(live_stack)}")

    stack_days = {str(r["day"]) for r in live_stack}
    fills = build_fills(sess, stack_days, daily_gap, bars5)
    print(f"empty fills n={len(fills)}")
    desk = merge_stack_plus_empty_fill(live_stack, fills, day_cap=2)

    # ACC from held report
    acc_by = defaultdict(list)
    if PRI_JSON.exists():
        pri = json.loads(PRI_JSON.read_text(encoding="utf-8"))
        for key in ["P2F|P100", "P1|P100", "P2F|P75"]:
            for c in (pri.get("results") or {}).get(key, {}).get("calls_1y") or []:
                day = str(c.get("day") or "")
                if START <= day <= END:
                    acc_by[day].append({**c, "book": key})

    def summ(rows):
        scored = [r for r in rows if r.get("win") is not None]
        n = len(scored)
        w = sum(1 for r in scored if r.get("win"))
        return {
            "n": len(rows),
            "scored": n,
            "wins": w,
            "losses": n - w,
            "hit_pct": round(100 * w / n, 2) if n else None,
            "points": round(sum(float(r.get("points") or 0) for r in scored), 1),
        }

    s_live, s_fill, s_desk = summ(live_stack), summ(fills), summ(desk)

    lines = [
        "# Deep Nov 2026 · proven LIVE + 1-day empty-fill calls",
        "",
        f"**Window:** `{START}` → `{END}` · sessions **{len(sess)}** · stack source: `{source}`",
        "",
        "## Books",
        "",
        "| Book | Role |",
        "|---|---|",
        "| `STACK_PLUS_CROWN_HTF_CAP2` | LIVE proven > good > champ > crown HTF · cap2 |",
        "| `EMPTY_FILL_FADE1030_GAP055_T35` | **1-day call** on stack-silent + `|gap|≥0.55` · 10:30 fade T35 |",
        "| `STACK_PLUS_EMPTY_FILL_GAP055_T35` | Holding desk = stack ∪ fill |",
        "| `ACC100_MULTI_V11` / P2F | Holding accurate (high hit) — report overlay |",
        "",
        "## Summary",
        "",
        "| Book | N | W/L | Hit% | Points |",
        "|---|---:|---|---:|---:|",
        f"| LIVE stack | {s_live['n']} | {s_live['wins']}/{s_live['losses']} | {s_live['hit_pct']} | {s_live['points']} |",
        f"| 1-day empty-fill | {s_fill['n']} | {s_fill['wins']}/{s_fill['losses']} | {s_fill['hit_pct']} | {s_fill['points']} |",
        f"| **Holding desk (stack+fill)** | **{s_desk['n']}** | {s_desk['wins']}/{s_desk['losses']} | **{s_desk['hit_pct']}** | **{s_desk['points']}** |",
        "",
        "## Day-by-day from 1 Nov",
        "",
        "| Day | Gap% | LIVE | 1-day fill | Holding desk | ACC P2F |",
        "|---|---:|---|---|---|---|",
    ]

    fill_by = {str(r["day"]): r for r in fills}
    stack_by = defaultdict(list)
    for r in live_stack:
        stack_by[str(r["day"])].append(r)
    desk_by = defaultdict(list)
    for r in desk:
        desk_by[str(r["day"])].append(r)

    for day in sess:
        gap = (daily_gap.get(day) or {}).get("gap_pct")
        gap_s = "—" if gap is None else f"{gap:+.2f}"
        st = stack_by.get(day) or []
        live_s = (
            "; ".join(
                f"{r.get('hm')} {r.get('decision')} `{r.get('track')}` "
                f"{'W' if r.get('win') else 'L' if r.get('win') is False else '?'} {r.get('points')}"
                for r in st
            )
            or "—"
        )
        fl = fill_by.get(day)
        if fl:
            fill_s = (
                f"**{fl.get('hm')} {fl.get('decision')}** gap={fl.get('gap_pct')} "
                f"{'W' if fl.get('win') else 'L' if fl.get('win') is False else '?'} "
                f"{fl.get('points')} `{FILL_TAG}`"
            )
        elif day in stack_days:
            fill_s = "(off — stack has call)"
        elif gap is not None and abs(float(gap)) < GAP_MIN_PCT:
            fill_s = f"no — abs(gap) {abs(float(gap)):.2f} < 0.55"
        else:
            fill_s = "—"
        dk = desk_by.get(day) or []
        desk_s = (
            "; ".join(
                f"{r.get('hm')} {r.get('decision')} "
                f"`{r.get('holding_tag') or r.get('track')}` "
                f"{'W' if r.get('win') else 'L' if r.get('win') is False else '?'}"
                for r in dk
            )
            or "—"
        )
        acc = acc_by.get(day) or []
        acc_s = (
            "; ".join(f"{c.get('hm')} {c.get('side')} `{c.get('tag')}`" for c in acc)
            if acc
            else "—"
        )
        lines.append(f"| {day} | {gap_s} | {live_s} | {fill_s} | {desk_s} | {acc_s} |")

    # weekends / missing
    lines += [
        "",
        "### Non-sessions",
        "",
        "- `2026-11-01` Sat · `2026-11-07` Sat · `2026-11-10` holiday · `2026-11-14` Sat · `2026-11-15` Sun",
        "- Daily NSE file ends ~`2026-11-11`; later gaps filled from 5m open vs prior close when needed.",
        "",
        "## All holding-desk calls (list)",
        "",
        "| Day | HM | Side | Source tag | Win | Pts | Multi-tags |",
        "|---|---|---|---|---|---:|---|",
    ]
    for r in desk:
        win = "W" if r.get("win") else ("L" if r.get("win") is False else "?")
        tag = r.get("holding_tag") or r.get("track") or r.get("desk_tag")
        tags = ", ".join(f"`{t}`" for t in (r.get("tags") or []) if t)
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | `{tag}` | {win} | "
            f"{r.get('points')} | {tags} |"
        )

    lines += [
        "",
        "## Logic notes",
        "",
        "1. **Proven LIVE** needs dual OR-break + gates — frozen pool has **0** Nov proven/good/champ; only crown `11-06` in pool.",
        "2. Fresh live tape rebuild (`fno_nifty_nov1_stack_live_report`) may add dual/good/champ when finished — re-run this script to merge.",
        "3. **1-day empty-fill** is the held way to get calls on silent gap days (≥0.55).",
        "4. **ACC/P2F** stays selective (Nov: crown stream on 11-06 only).",
        "",
    ]
    if source != "live_report_json":
        lines += [
            f"> LIVE stack currently from **`{source}`** (live report JSON not ready yet).",
            f"> Expected path: `{LIVE_JSON}`",
            "",
        ]

    md = OUT / "NOV2026_DEEP_CALLS.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (ROOT / "prod_live" / "reports" / "1y" / "NOV2026_DEEP_CALLS.md").write_text("\n".join(lines), encoding="utf-8")
    payload = {
        "window": {"start": START, "end": END},
        "sessions": sess,
        "stack_source": source,
        "summary": {"live": s_live, "fill": s_fill, "desk": s_desk},
        "live_stack": live_stack,
        "empty_fills": fills,
        "holding_desk": desk,
        "daily_gap": {d: daily_gap.get(d) for d in sess},
    }
    (OUT / "NOV2026_DEEP_CALLS.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("Wrote", md)
    print("LIVE", s_live, "FILL", s_fill, "DESK", s_desk)


if __name__ == "__main__":
    main()
