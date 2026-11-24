"""Replay NIFTY F&O modal dual-track calls for last 2 sessions (NOT scalper).

Walks every 15m bar after OR like live ws rescore / modal dual_track call_payload.

  python -u prod_live/tests/builders/_diag_nifty_fno_modal_calls_last2d.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
    str(ROOT / "tools" / "research"),
]
import path_setup  # noqa: F401

OUT = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_FNO_MODAL_CALLS_LAST2D.json"
TAPE = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_12y.csv"


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
            "NIFTY", "15minute", days=12, keep_partial=True
        )
        if df is not None and len(df):
            print(f"kite 15m: {len(df)} bars · {df.index[0]} → {df.index[-1]}", flush=True)
            return _norm(df)
        print(f"kite miss: {err} — using CSV", flush=True)
    except Exception as exc:
        print(f"kite err: {exc} — using CSV", flush=True)
    return _norm(pd.read_csv(TAPE, index_col=0, parse_dates=True))


def _fwd(bars: pd.DataFrame, i: int, decision: str, sl: float, t1: float) -> Optional[str]:
    import fno_session_replay as fsr

    future = bars.iloc[i + 1 :]
    if len(future) < 1:
        return None
    return fsr._forward_outcome(future, bearish=decision == "SELL", sl=sl, t1=t1)


def _settle_ticket(ticket: Optional[dict], bars: pd.DataFrame, i: int) -> Optional[dict]:
    """Mark open ticket closed if SL/T1 hit by bar i high/low."""
    if not ticket or str(ticket.get("status")) != "open":
        return ticket
    import fno_session_rules as fsrules

    try:
        return fsrules.mark(
            ticket,
            last=float(bars["Close"].iloc[i]),
            bars=bars.iloc[: i + 1],
            asof=bars.index[i],
        )
    except Exception:
        # fallback crude
        dec = str(ticket.get("decision"))
        sl = float(ticket["stop_loss"])
        t1 = float(ticket["target_1"])
        hi = float(bars["High"].iloc[i])
        lo = float(bars["Low"].iloc[i])
        out = dict(ticket)
        if dec == "BUY":
            if lo <= sl:
                out["status"] = "sl"
            elif hi >= t1:
                out["status"] = "t1"
        else:
            if hi >= sl:
                out["status"] = "sl"
            elif lo <= t1:
                out["status"] = "t1"
        return out


def main() -> int:
    import fno_session_rules as fsrules
    import nifty_live_dual_track as mod

    bars = load_15m()
    days_all = sorted({str(fsrules.session_date(t)) for t in bars.index})
    want = days_all[-2:]
    print(f"sessions under test: {want}", flush=True)
    print(f"packs_available={mod.packs_available()}", flush=True)

    lookback = pd.Timedelta(days=12)
    rows: List[Dict[str, Any]] = []
    day_stats: Dict[str, Any] = {}
    gate_fails: List[dict] = []

    for day in want:
        sess_mask = [str(fsrules.session_date(t)) == day for t in bars.index]
        sess_idx = [i for i, m in enumerate(sess_mask) if m]
        if len(sess_idx) < 4:
            day_stats[day] = {"n_bars": len(sess_idx), "calls": 0, "note": "too_few_bars"}
            continue

        sess = bars.iloc[sess_idx]
        or_hi = float(sess["High"].astype(float).iloc[0])
        or_lo = float(sess["Low"].astype(float).iloc[0])
        ticket = None
        day_calls: List[dict] = []
        evals = 0
        holds = 0
        no_or = 0

        # Walk every bar after first OR bar (live-style rescore)
        for pos, full_i in enumerate(sess_idx):
            if pos < 1:
                continue
            ts = bars.index[full_i]
            mins = int(ts.hour) * 60 + int(ts.minute)
            if mins < 9 * 60 + 30 or mins > 15 * 60:
                continue

            ticket = _settle_ticket(ticket, bars, full_i)
            if ticket and str(ticket.get("status")) == "open":
                continue  # one open modal call at a time

            left = bars.index.searchsorted(ts - lookback)
            win = bars.iloc[int(left) : full_i + 1]
            price = float(bars["Close"].iloc[full_i])
            asof = ts + pd.Timedelta(minutes=15)
            ev = mod.evaluate(win, asof=asof, price=price, session_ticket=ticket)
            evals += 1

            call = (ev or {}).get("call_payload") or {}
            dec = call.get("decision")
            reason = (ev or {}).get("reason")
            if not (ev or {}).get("available"):
                if reason == "no_or_break":
                    no_or += 1
                elif reason == "gates_fail":
                    dbg = (ev or {}).get("debug") or {}
                    holds += 1
                    if len(gate_fails) < 12:
                        gate_fails.append({"day": day, "hm": ts.strftime("%H:%M"), **dbg})
                continue

            if dec not in ("BUY", "SELL"):
                holds += 1
                continue

            entry = float(call.get("entry") or price)
            sl = float(call["stop_loss"])
            t1 = float(call["target_1"])
            outcome = _fwd(bars, full_i, str(dec), sl, t1)
            win_flag = outcome == "t1_before_sl"
            lose = outcome in ("sl_before_t1", "same_bar_both")
            track = call.get("track") or (
                "proven_100" if ev.get("proven_100") else "champion" if ev.get("champion") else "baseline"
            )
            row = {
                "day": day,
                "hm": ts.strftime("%H:%M"),
                "decision": dec,
                "track": track,
                "proven_100": bool(ev.get("proven_100")),
                "champion": bool(ev.get("champion")),
                "entry": round(entry, 2),
                "stop_loss": round(sl, 2),
                "target_1": round(t1, 2),
                "p_t1": call.get("p_t1"),
                "accuracy_label": call.get("accuracy_label"),
                "outcome": outcome,
                "result": "WIN" if win_flag else "LOSS" if lose else str(outcome or "open"),
            }
            day_calls.append(row)
            rows.append(row)
            print(
                f"  CALL {day} {row['hm']} {dec} {track} entry={row['entry']} "
                f"SL={row['stop_loss']} T1={row['target_1']} → {row['result']}",
                flush=True,
            )
            ticket = {
                "status": "open",
                "decision": dec,
                "entry": entry,
                "stop_loss": sl,
                "target_1": t1,
                "history": [],
            }

        day_stats[day] = {
            "n_bars": int(len(sess_idx)),
            "or_hi": round(or_hi, 2),
            "or_lo": round(or_lo, 2),
            "evals": evals,
            "no_or_break": no_or,
            "gates_fail_or_hold": holds,
            "calls": len(day_calls),
            "calls_detail": day_calls,
        }
        print(
            f"{day}: calls={len(day_calls)} evals={evals} no_or={no_or} gates_fail/hold={holds}",
            flush=True,
        )

    payload = {
        "mode": "fno_modal_dual_track_bar_walk_not_scalper",
        "symbol": "NIFTY",
        "sessions": want,
        "n_calls_total": len(rows),
        "by_day": {d: day_stats[d]["calls"] for d in want},
        "day_stats": day_stats,
        "calls": rows,
        "gate_fail_samples": gate_fails,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("\n=== NIFTY F&O MODAL (dual-track) last 2 days ===", flush=True)
    print(f"TOTAL modal calls: {len(rows)}", flush=True)
    for d in want:
        print(f"  {d}: {day_stats[d]['calls']} call(s)", flush=True)
    if gate_fails:
        print("sample gates_fail:", flush=True)
        for g in gate_fails[:6]:
            print(f"  {g}", flush=True)
    print(f"wrote {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
