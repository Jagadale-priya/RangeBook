"""Among dual+fb bf20 winners (last 1y), how many dipped against entry before T1.

BUY: Low went below entry before High hit +50
SELL: High went above entry before Low hit -50

  python -u prod_live/tests/builders/_sensex_winners_dip_then_t1_1y.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
import path_setup  # noqa: F401,E402

from research_bn_sensex_final_brackets import load_tape, normalize_cand  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
CANDS = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_full_live_candidates.json"
)
TAPE = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_5m_kite.csv"
SL = T1 = 50.0
MIN_BF = 0.20
END = "2026-11-19"
START = "2025-11-19"


def key_of(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day"))[:10], str(r.get("hm") or "")[:5], str(r.get("decision") or "").upper())


def fallback_row(bars: pd.DataFrame, day: str) -> Optional[dict]:
    db = bars[bars.index.strftime("%Y-%m-%d") == day]
    if len(db) < 2:
        return None
    or_hi = float(db["High"].iloc[0])
    or_lo = float(db["Low"].iloc[0])
    width = or_hi - or_lo
    if width <= 0:
        return None
    entry_ts = None
    for want in ("09:45", "09:30", "10:00", "10:15"):
        hit = db[db.index.strftime("%H:%M") == want]
        if len(hit):
            entry_ts = hit.index[0]
            break
    if entry_ts is None:
        entry_ts = db.index[min(1, len(db) - 1)]
    close = float(db.loc[entry_ts, "Close"])
    if close > or_hi:
        side, bf = "BUY", (close - or_hi) / width
    elif close < or_lo:
        side, bf = "SELL", (or_lo - close) / width
    else:
        return None
    if bf < MIN_BF:
        return None
    hm = f"{entry_ts.hour:02d}:{entry_ts.minute:02d}"
    return {
        "day": day,
        "hm": hm,
        "decision": side,
        "side": side,
        "p_t1": 0.55,
        "source": "fallback",
    }


def build_day(bars, by, day: str) -> List[dict]:
    duals = []
    for r in list(by.get(day) or []):
        if float(r.get("p_t1") or 0) < 0.45:
            continue
        duals.append({**r, "source": "dual"})
    duals = sorted(duals, key=lambda x: (str(x.get("hm") or ""), -float(x.get("p_t1") or 0)))
    fb = fallback_row(bars, day)
    if not duals and not fb:
        return []
    if not fb:
        return duals
    if not duals:
        return [fb]
    out: List[dict] = []
    fb_k = key_of(fb)
    merged = False
    for d in duals:
        if key_of(d) == fb_k:
            row = dict(d)
            row["source"] = "dual+fallback"
            row["p_t1"] = max(float(d.get("p_t1") or 0), float(fb.get("p_t1") or 0))
            out.append(row)
            merged = True
        else:
            out.append(d)
    if not merged:
        out.append(fb)
    return out


def build_ix(bars: pd.DataFrame) -> Dict[Tuple[str, str], int]:
    ix: Dict[Tuple[str, str], int] = {}
    for i, ts in enumerate(bars.index):
        d = str(pd.Timestamp(ts).date())
        hm = f"{pd.Timestamp(ts).hour:02d}:{pd.Timestamp(ts).minute:02d}"
        ix[(d, hm)] = i
    return ix


def path_with_dip(
    bars: pd.DataFrame,
    ix: Dict[Tuple[str, str], int],
    day: str,
    hm: str,
    side: str,
) -> Optional[dict]:
    i = ix.get((day, hm))
    if i is None:
        cands = [(h, j) for (d, h), j in ix.items() if d == day and h >= hm]
        if not cands:
            return None
        i = sorted(cands)[0][1]
        hm = sorted(cands)[0][0]
    entry = float(bars["Close"].iloc[i])
    side = side.upper()
    if side == "BUY":
        sl, t1 = entry - SL, entry + T1
    else:
        sl, t1 = entry + SL, entry - T1

    mae = 0.0  # max adverse pts from entry before exit
    dipped_below_entry = False  # adverse of entry at all
    j = i + 1
    n = len(bars)
    win = False
    outcome = "expired"
    while j < n and str(pd.Timestamp(bars.index[j]).date()) == day:
        hh = float(bars["High"].iloc[j])
        ll = float(bars["Low"].iloc[j])
        if side == "BUY":
            # adverse = downside
            if ll < entry:
                dipped_below_entry = True
                mae = max(mae, entry - ll)
            hit_sl, hit_t1 = ll <= sl, hh >= t1
        else:
            if hh > entry:
                dipped_below_entry = True
                mae = max(mae, hh - entry)
            hit_sl, hit_t1 = hh >= sl, ll <= t1
        if hit_sl and hit_t1:
            win, outcome = False, "same_bar_both"
            break
        if hit_sl:
            win, outcome = False, "sl_before_t1"
            break
        if hit_t1:
            win, outcome = True, "t1_before_sl"
            break
        j += 1

    return {
        "day": day,
        "hm": hm,
        "decision": side,
        "entry": round(entry, 2),
        "win": win if outcome != "expired" else None,
        "outcome": outcome,
        "dipped_against_entry": dipped_below_entry,
        "mae_pts": round(mae, 2),
        "mae_before_t1": round(mae, 2) if win else None,
    }


def main() -> int:
    bars, _ = load_tape(TAPE)
    if getattr(bars.index, "tz", None) is not None:
        bars = bars.copy()
        bars.index = bars.index.tz_localize(None)
    # last 1y window
    end = min(END, str(pd.Timestamp(bars.index.max()).date()))
    start = max(START, str(pd.Timestamp(bars.index.min()).date()))
    # if tape older, still use calendar 1y from end
    start = (pd.Timestamp(end) - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
    start = max(start, str(pd.Timestamp(bars.index.min()).date()))

    ix = build_ix(bars)
    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    by: Dict[str, List[dict]] = defaultdict(list)
    for row in raw:
        n = normalize_cand(row)
        if not n or n["day"] < start or n["day"] > end:
            continue
        n["p_t1"] = float(n.get("p_t1") or 0)
        if row.get("when"):
            try:
                ts = pd.Timestamp(row["when"])
                n["hm"] = f"{ts.hour:02d}:{ts.minute:02d}"
            except Exception:
                pass
        by[n["day"]].append(n)

    sessions = sorted(
        {
            str(pd.Timestamp(t).date())
            for t in bars.index
            if start <= str(pd.Timestamp(t).date()) <= end
        }
    )
    picks: List[dict] = []
    for day in sessions:
        picks.extend(build_day(bars, by, day))

    scored: List[dict] = []
    for p in picks:
        sc = path_with_dip(bars, ix, p["day"], str(p.get("hm") or ""), str(p.get("decision") or ""))
        if not sc:
            continue
        rr = {**p, **sc}
        scored.append(rr)

    wins = [r for r in scored if r.get("win") is True]
    losses = [r for r in scored if r.get("win") is False]
    dip_wins = [r for r in wins if r.get("dipped_against_entry")]
    clean_wins = [r for r in wins if not r.get("dipped_against_entry")]

    def mae_bucket(rows: List[dict]) -> Dict[str, int]:
        b = {
            "any_>0": 0,
            "mae_>=10": 0,
            "mae_>=20": 0,
            "mae_>=30": 0,
            "mae_>=40": 0,
            "mae_>=45": 0,
        }
        for r in rows:
            m = float(r.get("mae_pts") or 0)
            if m > 0:
                b["any_>0"] += 1
            for thr, key in ((10, "mae_>=10"), (20, "mae_>=20"), (30, "mae_>=30"), (40, "mae_>=40"), (45, "mae_>=45")):
                if m >= thr:
                    b[key] += 1
        return b

    buckets = mae_bucket(dip_wins)
    by_side = {
        s: {
            "wins": sum(1 for r in wins if r["decision"] == s),
            "dip_then_t1": sum(1 for r in dip_wins if r["decision"] == s),
            "clean_t1": sum(1 for r in clean_wins if r["decision"] == s),
        }
        for s in ("BUY", "SELL")
    }

    pct = lambda a, b: round(100.0 * a / b, 2) if b else None
    summary = {
        "window": {"start": start, "end": end, "sessions": len(sessions)},
        "logic": "dual p>=0.45 + OR fb bf>=0.20 · ±50/50 · 5m path",
        "n_calls": len(scored),
        "n_wins": len(wins),
        "n_losses": len(losses),
        "winners_dipped_then_t1": len(dip_wins),
        "winners_clean_no_dip": len(clean_wins),
        "pct_of_wins_dipped": pct(len(dip_wins), len(wins)),
        "pct_of_all_calls_dip_then_t1": pct(len(dip_wins), len(scored)),
        "mae_buckets_among_dip_wins": buckets,
        "by_side": by_side,
        "median_mae_dip_wins": (
            float(pd.Series([float(r["mae_pts"]) for r in dip_wins]).median()) if dip_wins else None
        ),
        "avg_mae_dip_wins": (
            round(float(pd.Series([float(r["mae_pts"]) for r in dip_wins]).mean()), 2) if dip_wins else None
        ),
        "max_mae_dip_wins": (
            round(max(float(r["mae_pts"]) for r in dip_wins), 2) if dip_wins else None
        ),
    }

    print(json.dumps(summary, indent=2), flush=True)

    lines = [
        "# SENSEX dual+fb · winners that dipped against entry then hit T1 · 1y",
        "",
        f"**Window:** `{start}` → `{end}` · {len(sessions)} sessions",
        f"**Logic:** dual p≥0.45 + OR fb bf≥0.20 · ±50/50 · **5m path**",
        "",
        "## Question",
        "",
        "Of **winning** calls, how many went **against entry** first "
        "(BUY: below entry · SELL: above entry), then still hit **+50 T1**?",
        "",
        "## Answer",
        "",
        f"- Total calls: **{len(scored)}** · Wins: **{len(wins)}** · Losses: **{len(losses)}**",
        f"- Winners that **dipped then hit T1:** **{len(dip_wins)}** "
        f"(**{summary['pct_of_wins_dipped']}%** of wins)",
        f"- Winners that went straight / never against entry: **{len(clean_wins)}** "
        f"({pct(len(clean_wins), len(wins))}% of wins)",
        f"- Dip-then-T1 as share of all calls: **{summary['pct_of_all_calls_dip_then_t1']}%**",
        "",
        "## Adverse depth (among dip-then-T1 winners)",
        "",
        f"- Median MAE: **{summary['median_mae_dip_wins']}** pts · avg **{summary['avg_mae_dip_wins']}** · max **{summary['max_mae_dip_wins']}**",
        "",
        "| MAE before T1 | N |",
        "|---|---:|",
        f"| any > 0 (against entry) | {buckets['any_>0']} |",
        f"| ≥ 10 pts | {buckets['mae_>=10']} |",
        f"| ≥ 20 pts | {buckets['mae_>=20']} |",
        f"| ≥ 30 pts | {buckets['mae_>=30']} |",
        f"| ≥ 40 pts | {buckets['mae_>=40']} |",
        f"| ≥ 45 pts (near SL) | {buckets['mae_>=45']} |",
        "",
        "## By side",
        "",
        "| Side | Wins | Dip→T1 | Clean T1 |",
        "|---|---:|---:|---:|",
        f"| BUY | {by_side['BUY']['wins']} | {by_side['BUY']['dip_then_t1']} | {by_side['BUY']['clean_t1']} |",
        f"| SELL | {by_side['SELL']['wins']} | {by_side['SELL']['dip_then_t1']} | {by_side['SELL']['clean_t1']} |",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "SENSEX_DUAL_FB_WINNERS_DIP_THEN_T1_1Y.md"
    js = OUT / "SENSEX_DUAL_FB_WINNERS_DIP_THEN_T1_1Y.json"
    payload = {**summary, "dip_wins_sample": dip_wins[:50], "clean_wins_n": len(clean_wins)}
    md.write_text("\n".join(lines), encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
