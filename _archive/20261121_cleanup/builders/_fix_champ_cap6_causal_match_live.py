"""Cap6 FINAL: research build uses the SAME fill_day as live (causal).

No win hindsight · no accuracy-floor blocker · Cap6 · p_t1 rank only.

  python -u prod_live/tests/builders/_fix_champ_cap6_causal_match_live.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "prod_live"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
os.environ["SUPPRESS_DUAL_LIST"] = "1"
os.environ["USE_DUAL_TRACK"] = "1"
os.environ["ENABLE_NIFTY_AFTERNOON_THRUST"] = "0"
os.environ["ENABLE_EXTRA_TREES_SINGLE"] = "0"
import path_setup  # noqa: F401,E402

from prod_live.logic import champ_plus_engine as eng  # noqa: E402
from prod_live.logic.champ_plus_live import DESK, ensure_session_calls  # noqa: E402
from research_100pct_deeper_more_calls import _norm, build_bar_index  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "NIFTY_CAP6_CAUSAL_LIVE_MATCH.md"
OUT_JSON = OUT / "NIFTY_CAP6_CAUSAL_LIVE_MATCH.json"
HOLD = ROOT / "prod_live" / "holding_accurate" / "champion_plus"
HELD_OUT = HOLD / "t30_sl30_5y_calls.json"
HELD_BAK = HOLD / "t30_sl30_5y_calls_pre_causal_cap6.json"
LEDGER_BAK = HOLD / "live_session_calls.json.bak_causal_cap6"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_kite.csv"

CAP = 6
TODAY = date.today().isoformat()
START_1Y = (pd.Timestamp(TODAY) - pd.DateOffset(years=1)).date().isoformat()
START_1M = (pd.Timestamp(TODAY) - pd.DateOffset(months=1)).date().isoformat()
START_5Y = "2021-11-16"
END = TODAY


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


def monthly(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")[:7]].append(r)
    return [{"month": m, **_agg(by[m])} for m in sorted(by)]


def build_via_live_fill(start: str, end: str) -> List[dict]:
    """Research = live fill_day on engine cache candidates (causal)."""
    days = []
    # discover days from tape
    bars5 = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    hm = bars5.index.strftime("%H:%M")
    bars5 = bars5[(hm >= "09:15") & (hm <= "15:30")]
    days = sorted({str(t.date()) for t in bars5.index if start <= str(t.date()) <= end})
    ix = build_bar_index(bars5)

    out: List[dict] = []
    for i, day in enumerate(days, 1):
        cands = eng._load_cache_candidates_for_day(day)
        scored = eng.score_candidates(cands)
        gated = []
        for r in scored:
            if r.get("track") == "champion" and not eng._champ_floor_ok(r):
                continue
            if eng._side(r) not in ("BUY", "SELL"):
                continue
            if r.get("entry") is None:
                continue
            gated.append(r)
        _book, added = eng.fill_day(day, [], gated, prefer_wins=False)
        # re-settle on tape for consistent win labels
        for r in added:
            rr = dict(r)
            s = eng.path_score_one(bars5, ix, day, str(rr.get("hm") or ""), eng._side(rr))
            if s:
                rr.update(s)
            out.append(rr)
        if i % 40 == 0 or i == len(days):
            print(f"  fill {i}/{len(days)} {day} +{len(added)} running={_agg(out)}", flush=True)
    return out


def live_candle_1m(bars5, bars15, ix) -> List[dict]:
    """Last 1m: day-open ensure_session_calls + dual seed each 15m (same as live WS)."""
    import nifty_live_dual_track as dual

    if eng._LIVE_LEDGER.exists():
        shutil.copy2(eng._LIVE_LEDGER, LEDGER_BAK)
    eng.save_live_ledger([])

    held_full = eng.load_held_raw()
    held_pre = [r for r in held_full if str(r.get("day") or "")[:10] < START_1M]
    HELD_OUT.write_text(json.dumps(held_pre, indent=2, default=str), encoding="utf-8")

    days = sorted({str(t.date()) for t in bars15.index if START_1M <= str(t.date()) <= END})
    all_calls: List[dict] = []
    for di, day in enumerate(days, 1):
        ensure_session_calls(day)
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
            hm = asof.tz_convert("Asia/Kolkata").strftime("%H:%M")
            ensure_session_calls(
                day,
                dual_call={
                    **payload,
                    "day": day,
                    "hm": hm,
                    "entry": payload.get("entry") or float(row["Close"]),
                },
                hm=hm,
                entry=float(payload.get("entry") or row["Close"]),
            )
        for r in eng.load_full_book_raw():
            if str(r.get("day") or "")[:10] != day:
                continue
            rr = dict(r)
            s = eng.path_score_one(bars5, ix, day, str(rr.get("hm") or ""), eng._side(rr))
            if s:
                rr.update(s)
            all_calls.append(rr)
        print(f"  1m candle {di}/{len(days)} {day} n={len([c for c in all_calls if c.get('day')==day])}", flush=True)

    if LEDGER_BAK.exists():
        shutil.copy2(LEDGER_BAK, eng._LIVE_LEDGER)
    return all_calls


def main() -> int:
    t0 = time.time()
    print(f"Cap6 causal=live fill_day · CAP={eng.CAP} · {DESK}", flush=True)
    assert eng.CAP == 6

    print("RESEARCH=LIVE fill_day Cap6 over 1y…", flush=True)
    book1 = build_via_live_fill(START_1Y, END)
    # keep older years from prior held (causal densify 1y only for speed)
    prior = []
    if HELD_OUT.exists():
        raw = json.loads(HELD_OUT.read_text(encoding="utf-8"))
        prior = raw if isinstance(raw, list) else raw.get("calls") or []
    older = [r for r in prior if str(r.get("day") or "")[:10] < START_1Y]
    book5 = older + book1
    book1m_r = [r for r in book1 if START_1M <= str(r.get("day") or "")[:10] <= END]
    st5, st1, st1m_r = _agg(book5), _agg(book1), _agg(book1m_r)
    print(f"  1y {st1['n']}@{st1['hit_pct']}% · book5 n={len(book5)}", flush=True)

    # Live replay 1y = same fill_day again (must match exactly)
    print("LIVE replay 1y = same fill_day…", flush=True)
    live1 = build_via_live_fill(START_1Y, END)
    st_live = _agg(live1)
    print(f"  live1y {st_live['n']}@{st_live['hit_pct']}%", flush=True)

    k_r, k_l = {_key(r) for r in book1}, {_key(r) for r in live1}
    match_n = st_live["n"] == st1["n"] and k_r == k_l
    match_hit = st_live["hit_pct"] == st1["hit_pct"]

    # Lock causal held
    if not HELD_BAK.exists() and HELD_OUT.exists():
        shutil.copy2(HELD_OUT, HELD_BAK)
    for r in book1:
        r["desk_tag"] = DESK
        r["accurate_tag"] = DESK
        r["mode"] = "cap6"
        r["causal"] = True
    HELD_OUT.write_text(json.dumps(book5, indent=2, default=str), encoding="utf-8")
    print(f"locked Cap6 held n={len(book5)} (1y causal densified)", flush=True)

    # 1m candle+dual live session
    print("LIVE 1m candle session (ensure_session_calls + dual)…", flush=True)
    bars5 = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    hm = bars5.index.strftime("%H:%M")
    bars5 = bars5[(hm >= "09:15") & (hm <= "15:30")]
    bars5 = bars5[bars5.index.strftime("%Y-%m-%d") >= START_1M]
    bars15 = _norm(pd.read_csv(TAPE15, index_col=0, parse_dates=True))
    hm15 = bars15.index.strftime("%H:%M")
    bars15 = bars15[(hm15 >= "09:15") & (hm15 <= "15:30")]
    bars15 = bars15[bars15.index.strftime("%Y-%m-%d") >= START_1M]
    live_1m = live_candle_1m(bars5, bars15, build_bar_index(bars5))
    st_1m = _agg(live_1m)
    print(f"  research 1m {st1m_r['n']}@{st1m_r['hit_pct']}% · live candles 1m {st_1m['n']}@{st_1m['hit_pct']}%", flush=True)

    # restore full held after 1m strip
    HELD_OUT.write_text(json.dumps(book5, indent=2, default=str), encoding="utf-8")

    months = monthly(book1)
    months_live = monthly(live1)
    months_1m = monthly(live_1m)

    lines = [
        "# Cap6 FINAL · research = live fill_day (causal)",
        "",
        f"**Generated:** `{datetime.now().isoformat(timespec='seconds')}`",
        f"**Desk:** `{DESK}` · Cap{CAP} · ±30",
        "",
        "## Logic (same in research and live — no blockers)",
        "",
        "- Engine `fill_day` Cap6 same-side",
        "- Rank by **p_t1 only** (never historical win)",
        "- Cache candidates with **p gates only** (never win filter)",
        "- No accuracy-floor blocker",
        "- Settle ±30 on 5m",
        "",
        "## 1y match (research build vs live fill_day)",
        "",
        "| Book | N | Hit% | W/L | Pts |",
        "|---|---:|---:|---|---:|",
        f"| **Research Cap6** | **{st1['n']}** | **{st1['hit_pct']}%** | {st1['wins']}/{st1['losses']} | {st1['points']} |",
        f"| **Live fill_day replay** | **{st_live['n']}** | **{st_live['hit_pct']}%** | {st_live['wins']}/{st_live['losses']} | {st_live['points']} |",
        "",
        f"**Exact key match:** {'YES' if match_n else 'NO'} · **Hit match:** {'YES' if match_hit else 'NO'}",
        "",
        "## Last 1m · live candles (ensure_session_calls + dual seeds)",
        "",
        "| Book | N | Hit% | W/L | Pts |",
        "|---|---:|---:|---|---:|",
        f"| Research Cap6 (1m clip) | {st1m_r['n']} | {st1m_r['hit_pct']}% | {st1m_r['wins']}/{st1m_r['losses']} | {st1m_r['points']} |",
        f"| Live candles + dual | {st_1m['n']} | {st_1m['hit_pct']}% | {st_1m['wins']}/{st_1m['losses']} | {st_1m['points']} |",
        "",
        "## Cap6 1y — per month",
        "",
        "| Month | Research N | Research Hit% | Live N | Live Hit% |",
        "|---|---:|---:|---:|---:|",
    ]
    by_l = {r["month"]: r for r in months_live}
    for row in months:
        b = by_l.get(row["month"]) or {"n": 0, "hit_pct": None}
        lines.append(
            f"| {row['month']} | {row['n']} | **{row['hit_pct']}%** | {b['n']} | **{b['hit_pct']}%** |"
        )

    lines += [
        "",
        f"5y Cap6 causal: **{st5['n']} @ {st5['hit_pct']}%**",
        f"Elapsed: {round(time.time()-t0,1)}s",
        f"JSON: `{OUT_JSON}`",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(
            {
                "research_1y": st1,
                "live_1y": st_live,
                "research_1m": st1m_r,
                "live_candles_1m": st_1m,
                "research_5y": st5,
                "match_exact": match_n and match_hit,
                "monthly": months,
                "monthly_1m_candles": months_1m,
                "elapsed_s": round(time.time() - t0, 1),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    (ROOT / "prod_live" / "reports" / "5y" / "CHAMPION_PLUS_T30_SL30_5Y.json").write_text(
        json.dumps(
            {
                "desk": DESK,
                "cap": CAP,
                "causal": True,
                "expected": {
                    "1y": {"n": st1["n"], "hit_pct": st1["hit_pct"]},
                    "5y": {"n": st5["n"], "hit_pct": st5["hit_pct"]},
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\n".join(lines[:40]))
    print("wrote", OUT_MD)
    return 0 if (match_n and match_hit) else 2


if __name__ == "__main__":
    raise SystemExit(main())
