"""NIFTY live logic · last ~2 months (fast).

1) Clip dual15 / dual5 proven→champion caches (same packs as live modal)
2) Clip FINAL P2F / P2G 10m / CHAMP from LIVE_LOGIC_3M replay books
3) Smoke last 5 sessions with live nifty_live_dual_track.evaluate

  python -u prod_live/tests/builders/_diag_nifty_live_logic_2m.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
]
os.environ.setdefault("ENABLE_EXTRA_TREES_SINGLE", "0")
os.environ.setdefault("USE_DUAL_TRACK", "1")
os.environ.setdefault("ENABLE_PRE_DUAL_SINGLE", "0")
os.environ.setdefault("ENABLE_5M_CROWN", "1")
import path_setup  # noqa: F401

warnings.filterwarnings("ignore", category=DeprecationWarning)

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_JSON = OUT / "NIFTY_LIVE_LOGIC_2M.json"
OUT_MD = OUT / "NIFTY_LIVE_LOGIC_2M.md"
CACHE = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "_cache_dual15_dual5_10y.json"
)
PRIOR_3M = OUT / "LIVE_LOGIC_3M_BAR_REPLAY.json"
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_12y.csv"

END = "2026-11-15"
START = (pd.Timestamp(END) - timedelta(days=62)).strftime("%Y-%m-%d")


def clip(rows: List[dict], a: str, b: str) -> List[dict]:
    return [r for r in rows if a <= str(r.get("day") or "")[:10] <= b]


def hit(rows: List[dict]) -> Dict[str, Any]:
    known = [r for r in rows if r.get("win") is not None]
    wins = sum(1 for r in known if r.get("win"))
    return {
        "n": len(rows),
        "settled": len(known),
        "wins": wins,
        "losses": len(known) - wins,
        "hit_pct": round(100.0 * wins / len(known), 2) if known else None,
        "by_side": dict(
            Counter(str(r.get("decision") or r.get("side") or "?") for r in rows)
        ),
    }


def load_dual_cache(start: str, end: str) -> Dict[str, Any]:
    raw = json.loads(CACHE.read_text(encoding="utf-8"))
    out: Dict[str, Any] = {}
    for tf in ("dual15", "dual5"):
        blk = raw.get(tf) or {}
        proven = clip(blk.get("proven_100") or [], start, end)
        champ = clip(blk.get("champion") or [], start, end)
        # live desk: proven first, then champion (no baseline)
        listed = []
        seen = set()
        for r in proven + champ:
            k = (str(r.get("day"))[:10], str(r.get("hm")), str(r.get("decision")))
            if k in seen:
                continue
            seen.add(k)
            listed.append(r)
        out[tf] = {
            "proven_100": hit(proven),
            "champion": hit(champ),
            "live_desk_union": hit(listed),
            "calls": [
                {
                    "day": r.get("day"),
                    "hm": r.get("hm"),
                    "decision": r.get("decision"),
                    "track": r.get("track"),
                    "p_t1": r.get("p_t1"),
                    "entry": r.get("entry"),
                    "win": r.get("win"),
                    "outcome": r.get("outcome"),
                    "points": r.get("points"),
                }
                for r in listed
            ],
        }
    return out


def load_final_2m(start: str, end: str) -> Dict[str, Any]:
    if not PRIOR_3M.is_file():
        return {"available": False, "error": "missing LIVE_LOGIC_3M_BAR_REPLAY.json"}
    raw = json.loads(PRIOR_3M.read_text(encoding="utf-8"))
    books = raw.get("books") or {}

    def clip_map(m: dict) -> Dict[str, Any]:
        return {k: hit(clip(v or [], start, end)) for k, v in (m or {}).items()}

    # Prefer desk maps from books; fall back to summary keys in 3m json
    p2f_day = books.get("p2f_day") or {}
    p2f_cap2 = books.get("p2f_cap2") or {}
    p2g = books.get("p2g_10m") or books.get("p2g") or {}
    champ_rows = books.get("champ_plus") or books.get("champ_full") or []

    # 3m file may only have summary — use summary clipped ratios from window keys
    summary = {
        "p2f_day_3m": raw.get("p2f_day_3m"),
        "p2g_3m": raw.get("p2g_3m"),
        "champ_held_3m": raw.get("champ_held_3m"),
        "champ_full_3m": raw.get("champ_full_3m"),
        "combine_3m": raw.get("combine"),
        "note": "3m report summaries; desk row clip used when books present",
    }

    from prod_live.logic.champ_plus_live import load_live_book
    from prod_live.logic.combined_live_book import combine_live_rows

    champ = clip(load_live_book(), start, end)

    if p2f_day or p2g:
        combined = combine_live_rows(
            p2f_day={k: clip(v or [], start, end) for k, v in p2f_day.items()},
            p2f_cap2={k: clip(v or [], start, end) for k, v in p2f_cap2.items()},
            p2g_10m={k: clip(v or [], start, end) for k, v in p2g.items()},
            champ_plus=champ,
        )
        ui = combined.get("ui_rows") or []
        return {
            "available": True,
            "champ": hit(champ),
            "p2f_day": clip_map(p2f_day),
            "p2f_cap2": clip_map(p2f_cap2),
            "p2g_10m": clip_map(p2g),
            "ui_combine": {
                "n": len(ui),
                "blocked_distinct": combined.get("blocked_distinct"),
                "hit": hit(ui),
            },
            "summary_3m_ref": summary,
        }

    # No desk rows in 3m json — report champ clip + 3m summary as reference
    return {
        "available": True,
        "champ": hit(champ),
        "p2f_day": raw.get("p2f_day_3m"),
        "p2g_10m": raw.get("p2g_3m"),
        "ui_combine": {
            "n": (raw.get("combine") or {}).get("n_ui"),
            "blocked_distinct": (raw.get("combine") or {}).get("blocked_distinct"),
            "hit": None,
            "note": "from 3m window — desk-level 2m clip unavailable in prior json",
        },
        "summary_3m_ref": summary,
        "window_note": "P2F/P2G figures below are 3m report refs; CHAMP is true 2m clip",
    }


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    import fno_session_replay as fsr

    work = df.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index)
    if work.index.tz is None:
        work.index = work.index.tz_localize("Asia/Kolkata")
    else:
        work.index = work.index.tz_convert("Asia/Kolkata")
    work = work.rename(columns={c: str(c).title() for c in work.columns})
    return fsr._norm(work)


def load_15m() -> pd.DataFrame:
    try:
        import kite_data

        df, err = kite_data.fetch_historical_candles(
            "NIFTY", "15minute", days=80, keep_partial=True
        )
        if df is not None and len(df):
            return _norm(df)
        print(f"kite miss: {err}", flush=True)
    except Exception as exc:
        print(f"kite err: {exc}", flush=True)
    return _norm(pd.read_csv(TAPE15, index_col=0, parse_dates=True))


def smoke_live_dual(bars: pd.DataFrame, days: List[str]) -> Dict[str, Any]:
    """Bar-walk last few sessions with live evaluate (confirms code path)."""
    import fno_session_rules as fsrules
    import nifty_live_dual_track as mod

    want = days[-5:]
    lookback = pd.Timedelta(days=12)
    rows: List[dict] = []
    reasons = Counter()
    print(f"live smoke sessions={want} packs={mod.packs_available()}", flush=True)
    for day in want:
        sess_idx = [
            i for i, t in enumerate(bars.index) if str(fsrules.session_date(t)) == day
        ]
        ticket = None
        for pos, full_i in enumerate(sess_idx):
            if pos < 1:
                continue
            ts = bars.index[full_i]
            mins = int(ts.hour) * 60 + int(ts.minute)
            if mins < 9 * 60 + 30 or mins > 15 * 60:
                continue
            if ticket and str(ticket.get("status")) == "open":
                try:
                    ticket = fsrules.mark(
                        ticket,
                        last=float(bars["Close"].iloc[full_i]),
                        bars=bars.iloc[: full_i + 1],
                        asof=ts,
                    )
                except Exception:
                    pass
                if ticket and str(ticket.get("status")) == "open":
                    continue
            left = int(bars.index.searchsorted(ts - lookback))
            win = bars.iloc[left : full_i + 1]
            price = float(bars["Close"].iloc[full_i])
            asof = ts + pd.Timedelta(minutes=15)
            ev = mod.evaluate(win, asof=asof, price=price, session_ticket=ticket)
            call = (ev or {}).get("call_payload") or {}
            dec = call.get("decision")
            reason = (ev or {}).get("reason") or (
                "listed" if dec in ("BUY", "SELL") else "hold"
            )
            reasons[reason] += 1
            if dec not in ("BUY", "SELL"):
                continue
            track = call.get("track") or (
                "proven_100"
                if ev.get("proven_100")
                else "champion"
                if ev.get("champion")
                else "?"
            )
            rows.append(
                {
                    "day": day,
                    "hm": ts.strftime("%H:%M"),
                    "decision": dec,
                    "track": track,
                    "p_t1": call.get("p_t1"),
                    "entry": call.get("entry") or price,
                    "stop_loss": call.get("stop_loss"),
                    "target_1": call.get("target_1"),
                    "accuracy_label": call.get("accuracy_label"),
                }
            )
            ticket = {
                "status": "open",
                "decision": dec,
                "entry": float(call.get("entry") or price),
                "stop_loss": float(call["stop_loss"]),
                "target_1": float(call["target_1"]),
                "history": [],
            }
            print(
                f"  LIVE CALL {day} {rows[-1]['hm']} {dec} {track} p={call.get('p_t1')}",
                flush=True,
            )
    return {
        "sessions": want,
        "n_calls": len(rows),
        "reasons": dict(reasons),
        "calls": rows,
    }


def write_md(payload: dict) -> None:
    d15 = payload["dual_cache"]["dual15"]
    d5 = payload["dual_cache"]["dual5"]
    lines = [
        "# NIFTY live logic · last 2 months",
        "",
        f"**Window:** `{payload['start']}` → `{payload['end']}`",
        "",
        "ExtraTrees single **OFF**. Live desk = dual proven→champion (15m) + dual5 + FINAL 10m/P2F/CHAMP.",
        "",
        "## 15m dual (cache = live packs)",
        "",
        f"| Book | N | Hit% | W/L |",
        f"|---|---:|---:|---|",
        f"| proven_100 | {d15['proven_100']['n']} | {d15['proven_100']['hit_pct']} | "
        f"{d15['proven_100']['wins']}/{d15['proven_100']['losses']} |",
        f"| champion | {d15['champion']['n']} | {d15['champion']['hit_pct']} | "
        f"{d15['champion']['wins']}/{d15['champion']['losses']} |",
        f"| **live union** | **{d15['live_desk_union']['n']}** | "
        f"**{d15['live_desk_union']['hit_pct']}** | "
        f"{d15['live_desk_union']['wins']}/{d15['live_desk_union']['losses']} |",
        "",
        "## 5m dual (cache)",
        "",
        f"| Book | N | Hit% |",
        f"|---|---:|---:|",
        f"| proven_100 | {d5['proven_100']['n']} | {d5['proven_100']['hit_pct']} |",
        f"| champion | {d5['champion']['n']} | {d5['champion']['hit_pct']} |",
        f"| **live union** | **{d5['live_desk_union']['n']}** | "
        f"**{d5['live_desk_union']['hit_pct']}** |",
        "",
        "## FINAL books",
        "",
    ]
    fb = payload.get("final_books") or {}
    if fb.get("champ"):
        lines.append(f"- CHAMP 2m clip: `{fb['champ']}`")
    if fb.get("ui_combine"):
        lines.append(f"- UI combine: `{fb['ui_combine']}`")
    if isinstance(fb.get("p2g_10m"), dict):
        lines.append("- P2G 10m (top desks):")
        for k, v in list(fb["p2g_10m"].items())[:5]:
            lines.append(f"  - `{k}`: {v}")
    if isinstance(fb.get("p2f_day"), dict):
        lines.append("- P2F day (top desks):")
        for k, v in list(fb["p2f_day"].items())[:5]:
            lines.append(f"  - `{k}`: {v}")
    smoke = payload.get("live_smoke") or {}
    lines += [
        "",
        "## Live smoke (last 5 sessions · evaluate())",
        "",
        f"- sessions: `{smoke.get('sessions')}`",
        f"- calls: **{smoke.get('n_calls')}**",
        f"- reasons: `{smoke.get('reasons')}`",
        "",
    ]
    if smoke.get("calls"):
        lines += ["| Day | HM | Side | Track | p_t1 |", "|---|---|---|---|---:|"]
        for r in smoke["calls"]:
            lines.append(
                f"| {r['day']} | {r['hm']} | {r['decision']} | {r['track']} | {r.get('p_t1')} |"
            )
    lines += ["", "## Dual15 live-union calls", "", "| Day | HM | Side | Track | Win |", "|---|---|---|---|---|"]
    for r in d15["calls"]:
        lines.append(
            f"| {r['day']} | {r['hm']} | {r['decision']} | {r['track']} | {r.get('win')} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    t0 = time.time()
    print(f"NIFTY LIVE LOGIC 2M · {START} → {END}", flush=True)

    dual = load_dual_cache(START, END)
    print(
        f"dual15 union N={dual['dual15']['live_desk_union']['n']} "
        f"hit={dual['dual15']['live_desk_union']['hit_pct']}%",
        flush=True,
    )
    print(
        f"dual5 union N={dual['dual5']['live_desk_union']['n']} "
        f"hit={dual['dual5']['live_desk_union']['hit_pct']}%",
        flush=True,
    )

    final_books = load_final_2m(START, END)
    print(f"final books: {final_books.get('champ') or final_books.get('error')}", flush=True)

    bars = load_15m()
    import fno_session_rules as fsrules

    days = sorted(
        {
            str(fsrules.session_date(t))
            for t in bars.index
            if START <= str(fsrules.session_date(t)) <= END
        }
    )
    if not days:
        days = sorted({str(fsrules.session_date(t)) for t in bars.index})[-45:]
    smoke = smoke_live_dual(bars, days)

    payload = {
        "symbol": "NIFTY",
        "start": START,
        "end": END,
        "elapsed_sec": round(time.time() - t0, 1),
        "flags": {
            "ENABLE_EXTRA_TREES_SINGLE": "0",
            "USE_DUAL_TRACK": "1",
            "ENABLE_5M_CROWN": "1",
        },
        "dual_cache": dual,
        "final_books": final_books,
        "live_smoke": smoke,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    write_md(payload)

    print("\n=== NIFTY LIVE LOGIC · 2M ===", flush=True)
    u15 = dual["dual15"]["live_desk_union"]
    u5 = dual["dual5"]["live_desk_union"]
    print(
        f"15m dual desk: N={u15['n']} hit={u15['hit_pct']}% "
        f"(proven {dual['dual15']['proven_100']['n']} / champ {dual['dual15']['champion']['n']})",
        flush=True,
    )
    print(
        f"5m dual desk:  N={u5['n']} hit={u5['hit_pct']}% "
        f"(proven {dual['dual5']['proven_100']['n']} / champ {dual['dual5']['champion']['n']})",
        flush=True,
    )
    if final_books.get("champ"):
        print(f"CHAMP 2m:      {final_books['champ']}", flush=True)
    print(
        f"live smoke:    {smoke['n_calls']} call(s) on {smoke['sessions']}",
        flush=True,
    )
    print(f"wrote {OUT_MD} · {payload['elapsed_sec']}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
