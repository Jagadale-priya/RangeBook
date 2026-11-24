"""Sensex DUAL_FB_BF20_T50 · same test as NIFTY causal=live.

Research rebuild = live lock rules (no win hindsight):
  - Dual OR-break p≥0.45
  - Fallback OR break @09:45 with break_frac≥0.20
  - Combine same hm+side
  - Settle ±50 on 5m

Also: last 1m candle walk via sensex dual.evaluate + fallback.

  python -u prod_live/tests/builders/_fix_sensex_causal_live_match.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "prod_live"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
os.environ.setdefault("USE_DUAL_TRACK", "1")
os.environ.setdefault("ENABLE_SENSEX_FINAL_LIVE", "1")
import path_setup  # noqa: F401,E402

from research_bn_sensex_final_brackets import (  # noqa: E402
    load_tape,
    normalize_cand,
    path_score_pool,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "SENSEX_CAUSAL_LIVE_MATCH.md"
OUT_JSON = OUT / "SENSEX_CAUSAL_LIVE_MATCH.json"
HELD = ROOT / "prod_live" / "holding_accurate" / "sensex_final" / "champ_plus_t50_sl50_calls.json"
CANDS = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_full_live_candidates.json"
)
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_5m_kite.csv"
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_15m_kite.csv"

DESK = "SENSEX_DUAL_FB_BF20_T50"
SL = T1 = 50.0
MIN_BF = 0.20
P_MIN = 0.45
TODAY = date.today().isoformat()
START_1Y = (pd.Timestamp(TODAY) - pd.DateOffset(years=1)).date().isoformat()
START_1M = (pd.Timestamp(TODAY) - pd.DateOffset(months=1)).date().isoformat()
END = TODAY


def key_of(r: dict) -> Tuple[str, str, str]:
    return (
        str(r.get("day") or "")[:10],
        str(r.get("hm") or "")[:5],
        str(r.get("decision") or r.get("side") or "").upper(),
    )


def win(r: dict) -> Optional[bool]:
    if r.get("win") is True:
        return True
    if r.get("win") is False:
        return False
    if r.get("native_win") is True:
        return True
    if r.get("native_win") is False:
        return False
    o = str(r.get("outcome") or "")
    if o in ("t1_before_sl", "win"):
        return True
    if o in ("sl_before_t1", "same_bar_both", "loss"):
        return False
    return None


def agg(rows: List[dict]) -> Dict[str, Any]:
    c = [r for r in rows if win(r) is not None]
    n = len(c)
    w = sum(1 for r in c if win(r))
    return {
        "n": n,
        "wins": w,
        "losses": n - w,
        "hit_pct": round(100.0 * w / n, 2) if n else None,
        "points": round(sum(float(SL) if win(r) else -float(SL) for r in c), 1),
    }


def monthly(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")[:7]].append(r)
    return [{"month": m, **agg(by[m])} for m in sorted(by)]


def sessions(bars: pd.DataFrame, a: str, b: str) -> List[str]:
    return sorted(
        {
            str(pd.Timestamp(t).date())
            for t in bars.index
            if a <= str(pd.Timestamp(t).date()) <= b
        }
    )


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
        side = "BUY"
        bf = (close - or_hi) / width
    elif close < or_lo:
        side = "SELL"
        bf = (or_lo - close) / width
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
        "first_break": True,
        "track": "or_fallback",
        "source": "fallback",
        "break_frac": bf,
        "tags": ["fallback", "OR_09:45", "fb_break", f"bf>={MIN_BF}"],
    }


def build_day(bars, by, day: str) -> List[dict]:
    """Same as lock — dual p≥0.45 + fb bf20 · no win filter."""
    duals = []
    for r in list(by.get(day) or []):
        if float(r.get("p_t1") or 0) < P_MIN:
            continue
        duals.append(
            {
                **r,
                "source": "dual",
                "track": r.get("track") or "champion",
                "tags": ["dual", "OR_break"],
            }
        )
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
            tags = list(
                dict.fromkeys(
                    (row.get("tags") or [])
                    + (fb.get("tags") or [])
                    + ["dual", "fallback", "COMBINED"]
                )
            )
            row["tags"] = tags
            row["source"] = "dual+fallback"
            row["track"] = "dual_fb_combined"
            row["combined"] = True
            row["p_t1"] = max(float(d.get("p_t1") or 0), float(fb.get("p_t1") or 0))
            out.append(row)
            merged = True
        else:
            out.append(d)
    if not merged:
        out.append(fb)
    return out


def load_held(start: str, end: str) -> List[dict]:
    blob = json.loads(HELD.read_text(encoding="utf-8"))
    rows = blob.get("calls") or []
    return [r for r in rows if start <= str(r.get("day") or "")[:10] <= end]


def build_causal(start: str, end: str) -> List[dict]:
    bars, ix = load_tape(TAPE5)
    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    by: Dict[str, List[dict]] = defaultdict(list)
    for row in raw:
        n = normalize_cand(row)
        if not n:
            continue
        d = str(n["day"])[:10]
        if not (start <= d <= end):
            continue
        n["or_ext"] = float(row.get("or_ext") if row.get("or_ext") is not None else 9)
        n["regime"] = str(row.get("regime") or "")
        n["first_break"] = bool(row.get("first_break"))
        n["p_t1"] = float(row.get("p_t1") or n.get("p_t1") or 0)
        by[d].append(n)

    picks: List[dict] = []
    for day in sessions(bars, start, end):
        picks.extend(build_day(bars, by, day))
    scored = path_score_pool(bars, ix, picks, SL, T1)
    for r in scored:
        r["sl_pts"] = SL
        r["t1_pts"] = T1
    return scored


def candle_1m(start: str, end: str) -> List[dict]:
    """Walk 15m candles · dual.evaluate + day fallback · settle ±50."""
    import sensex_live_dual_track as dual
    from research_bn_sensex_final_brackets import score_one

    bars5, ix5 = load_tape(TAPE5)
    if not TAPE15.exists():
        return []
    bars15 = pd.read_csv(TAPE15, index_col=0, parse_dates=True)
    if bars15.index.tz is None:
        bars15.index = bars15.index.tz_localize("Asia/Kolkata")
    else:
        bars15.index = bars15.index.tz_convert("Asia/Kolkata")
    bars15 = bars15.rename(columns={c: str(c).title() for c in bars15.columns})
    hm = bars15.index.strftime("%H:%M")
    bars15 = bars15[(hm >= "09:15") & (hm <= "15:30")]
    bars15 = bars15[bars15.index.strftime("%Y-%m-%d") >= start]
    bars15 = bars15[bars15.index.strftime("%Y-%m-%d") <= end]

    days = sessions(bars15, start, end)
    # also need fallback from 5m OR
    by_fb: Dict[str, dict] = {}
    for day in days:
        fb = fallback_row(bars5, day)
        if fb:
            by_fb[day] = fb

    seen = set()
    picks: List[dict] = []
    for di, day in enumerate(days, 1):
        day15 = bars15[bars15.index.strftime("%Y-%m-%d") == day]
        for ts, row in day15.iterrows():
            asof = pd.Timestamp(ts)
            window = bars15[bars15.index <= asof].tail(80)
            if len(window) < 20:
                continue
            try:
                ev = dual.evaluate(
                    window, asof=asof.to_pydatetime(), price=float(row["Close"])
                )
            except Exception:
                continue
            payload = ev.get("call_payload") if isinstance(ev, dict) else None
            if not (isinstance(payload, dict) and payload.get("decision") in ("BUY", "SELL")):
                continue
            # Live DUAL_FB desk uses p≥0.45 on dual fires
            if float(payload.get("p_t1") or 0) < P_MIN:
                continue
            hm = asof.tz_convert("Asia/Kolkata").strftime("%H:%M")
            rr = {
                "day": day,
                "hm": hm,
                "decision": payload["decision"],
                "side": payload["decision"],
                "p_t1": float(payload.get("p_t1") or 0),
                "track": payload.get("track") or "champion",
                "source": "dual_live",
                "first_break": bool(payload.get("first_break")),
                "entry": float(payload.get("entry") or row["Close"]),
            }
            k = key_of(rr)
            if k in seen:
                continue
            seen.add(k)
            picks.append(rr)
        fb = by_fb.get(day)
        if fb:
            k = key_of(fb)
            if k not in seen:
                seen.add(k)
                picks.append(dict(fb))
            else:
                # merge tag onto existing
                for p in picks:
                    if key_of(p) == k:
                        p["source"] = "dual+fallback" if p.get("source") != "fallback" else p["source"]
                        break
        if di % 5 == 0 or di == len(days):
            print(f"  candle {di}/{len(days)} {day} picks={len(picks)}", flush=True)

    # settle
    out = []
    for r in picks:
        s = score_one(bars5, ix5, r["day"], r["hm"], str(r["decision"]), SL, T1)
        if not s:
            continue
        rr = dict(r)
        rr.update(s)
        out.append(rr)
    return out


def main() -> int:
    t0 = time.time()
    print(f"Sensex causal=live · {DESK} · ±{SL} · {START_1Y}→{END}", flush=True)

    held1 = load_held(START_1Y, END)
    st_held = agg(held1)
    print(f"HELD book 1y: {st_held['n']}@{st_held['hit_pct']}%", flush=True)

    print("Rebuild CAUSAL (dual p≥0.45 + fb bf≥0.20)…", flush=True)
    causal1 = build_causal(START_1Y, END)
    st_c = agg(causal1)
    print(f"CAUSAL rebuild 1y: {st_c['n']}@{st_c['hit_pct']}%", flush=True)

    # key overlap
    kh, kc = {key_of(r) for r in held1}, {key_of(r) for r in causal1}
    only_h, only_c = kh - kc, kc - kh
    match_n = st_c["n"] == st_held["n"]
    match_hit = (
        st_c["hit_pct"] is not None
        and st_held["hit_pct"] is not None
        and abs(st_c["hit_pct"] - st_held["hit_pct"]) <= 0.5
    )
    print(
        f"keys held={len(kh)} causal={len(kc)} only_held={len(only_h)} only_causal={len(only_c)}",
        flush=True,
    )

    print("LIVE 1m candle walk…", flush=True)
    live_1m = candle_1m(START_1M, END)
    causal_1m = [r for r in causal1 if START_1M <= str(r.get("day") or "")[:10] <= END]
    st_l1m, st_c1m = agg(live_1m), agg(causal_1m)
    print(f"CAUSAL 1m: {st_c1m['n']}@{st_c1m['hit_pct']}% · LIVE candles 1m: {st_l1m['n']}@{st_l1m['hit_pct']}%", flush=True)

    months_c = monthly(causal1)
    months_h = monthly(held1)
    months_l = monthly(live_1m)

    lines = [
        "# Sensex DUAL_FB_BF20_T50 · causal = live match",
        "",
        f"**Generated:** `{datetime.now().isoformat(timespec='seconds')}`",
        f"**Desk:** `{DESK}` · ±{SL} · dual p≥{P_MIN} + fb break_frac≥{MIN_BF}",
        f"**Window 1y:** `{START_1Y}` → `{END}`",
        "",
        "## Rules (causal — no win hindsight)",
        "",
        "1. Dual OR-break candidates with **p_t1 ≥ 0.45**",
        "2. Fallback OR break @ ~09:45 with **break_frac ≥ 0.20**",
        "3. Same hm+side → merge tags (no mutual block)",
        "4. Settle **±50** on 5m",
        "",
        "## 1y match",
        "",
        "| Book | N | Hit% | W/L | Pts |",
        "|---|---:|---:|---|---:|",
        f"| **Held live book** | **{st_held['n']}** | **{st_held['hit_pct']}%** | {st_held['wins']}/{st_held['losses']} | {st_held['points']} |",
        f"| **Causal rebuild (same rules)** | **{st_c['n']}** | **{st_c['hit_pct']}%** | {st_c['wins']}/{st_c['losses']} | {st_c['points']} |",
        "",
        "MATCH_LINE_PLACEHOLDER",
        f"Only-in-held: {len(only_h)} · Only-in-causal: {len(only_c)}",
        "",
        "## Last 1m · candle live vs causal",
        "",
        "| Book | N | Hit% | W/L | Pts |",
        "|---|---:|---:|---|---:|",
        f"| Causal clip | {st_c1m['n']} | {st_c1m['hit_pct']}% | {st_c1m['wins']}/{st_c1m['losses']} | {st_c1m['points']} |",
        f"| Live candles (dual.evaluate + fb) | {st_l1m['n']} | {st_l1m['hit_pct']}% | {st_l1m['wins']}/{st_l1m['losses']} | {st_l1m['points']} |",
        "",
        "## Causal 1y — per month",
        "",
        "| Month | Held N | Held Hit% | Causal N | Causal Hit% |",
        "|---|---:|---:|---:|---:|",
    ]
    by_h = {r["month"]: r for r in months_h}
    for row in months_c:
        h = by_h.get(row["month"]) or {"n": 0, "hit_pct": None}
        lines.append(
            f"| {row['month']} | {h['n']} | {h['hit_pct']}% | {row['n']} | **{row['hit_pct']}%** |"
        )

    lines += [
        "",
        "## Live candles 1m — per month",
        "",
        "| Month | N | Hit% | W/L | Pts |",
        "|---|---:|---:|---|---:|",
    ]
    for row in months_l:
        lines.append(
            f"| {row['month']} | {row['n']} | **{row['hit_pct']}%** | {row['wins']}/{row['losses']} | {row['points']} |"
        )
    if not months_l:
        lines.append("| — | 0 | — | — | — |")

    lines += [
        "",
        "## Notes",
        "",
        "- Sensex held book was built with these same dual+fb rules (already mostly causal).",
        "- Unlike old NIFTY Cap6, this desk does **not** prefer historical wins to inflate hit%.",
        f"- Elapsed: {round(time.time() - t0, 1)}s",
        f"- JSON: `{OUT_JSON}`",
        "",
    ]

    OUT.mkdir(parents=True, exist_ok=True)
    match_line = (
        f"**N match:** YES · **Hit match (±0.5):** {'YES' if match_hit else 'NO'}"
        if match_n
        else (
            f"**N match:** NO (Δ {st_c['n'] - st_held['n']:+d}) · "
            f"**Hit match (±0.5):** {'YES' if match_hit else 'NO'}"
        )
    )
    out_lines = [match_line if x == "MATCH_LINE_PLACEHOLDER" else x for x in lines]
    OUT_MD.write_text("\n".join(out_lines), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(
            {
                "desk": DESK,
                "brackets": {"sl": SL, "t1": T1},
                "held_1y": st_held,
                "causal_1y": st_c,
                "causal_1m": st_c1m,
                "live_candles_1m": st_l1m,
                "match_n": match_n,
                "match_hit": match_hit,
                "only_held": len(only_h),
                "only_causal": len(only_c),
                "monthly_causal": months_c,
                "monthly_held": months_h,
                "monthly_live_1m": months_l,
                "elapsed_s": round(time.time() - t0, 1),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print("\n".join(out_lines[:45]))
    print("wrote", OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
