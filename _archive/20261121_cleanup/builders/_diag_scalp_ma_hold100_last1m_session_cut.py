"""NIFTY last 1m — session cut + higher T1.

Skip entries 09:15–09:30 and 14:30–15:15.
Allow: 09:30 ≤ entry < 14:30 only.
Same HELD gate (DI+hard34+VWAP) · EMA34 trail · 1/day first.
Compare T1 grid (12 lock + higher).

  python -u prod_live/tests/builders/_diag_scalp_ma_hold100_last1m_session_cut.py
"""
from __future__ import annotations

import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
import research_nifty_1m_vix_candle_adaptive as vixmod  # noqa: E402
import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import enrich_prior3  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402
from _diag_scalp_ma_lastyear_init import WIN_LO, PACK, add_ma_layers, enrich_ma_layers, summarize  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SCALP_MA_HOLD100_LAST1M_SESSION_CUT.md"

# minutes from midnight
MINS_AFTER_930 = 9 * 60 + 30  # 570 — allow from 09:30 inclusive
MINS_BEFORE_230 = 14 * 60 + 30  # 870 — exclude from 14:30 onward
T1_GRID = (12.0, 20.0, 25.0, 30.0, 40.0, 50.0)
MAX_BARS = 120


def in_session(e) -> bool:
    m = int(e["mins"])
    return MINS_AFTER_930 <= m < MINS_BEFORE_230


def held_session(e) -> bool:
    return in_session(e) and held_gate(e)


def path_detail(h, l, c, ma, i, side, t1_pts, max_bars=MAX_BARS):
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    if side == "BUY":
        t1 = entry + t1_pts
        for j in range(i + 1, end + 1):
            hi, cl, m = float(h[j]), float(c[j]), float(ma[j])
            if not np.isfinite(m):
                return False, "bad", entry, i, 0.0
            if hi >= t1:
                return True, "t1", t1, j, float(t1_pts)
            if cl < m:
                return False, "ma_sl", cl, j, cl - entry
        px = float(c[end])
        return False, "exp", px, end, px - entry
    t1 = entry - t1_pts
    for j in range(i + 1, end + 1):
        lo, cl, m = float(l[j]), float(c[j]), float(ma[j])
        if not np.isfinite(m):
            return False, "bad", entry, i, 0.0
        if lo <= t1:
            return True, "t1", t1, j, float(t1_pts)
        if cl > m:
            return False, "ma_sl", cl, j, entry - cl
    px = float(c[end])
    return False, "exp", px, end, entry - px


def first_pass(xs, pred):
    for e in sorted(xs, key=lambda x: x["mins"]):
        if pred(e):
            return e
    return None


def oracle_day(xs, pred=None):
    for e in sorted(xs, key=lambda x: x["mins"]):
        if pred is not None and not pred(e):
            continue
        if e.get("_win"):
            return e
    return None


def score_all(events, h, l, c, ema34, idx, t1):
    for e in events:
        i = int(e["full_i"])
        ok, reason, exit_px, j, pts = path_detail(h, l, c, ema34, i, e["decision"], t1)
        e["_win"] = bool(ok)
        e["_reason"] = reason
        e["_exit_px"] = round(float(exit_px), 2)
        e["_pts"] = round(float(pts), 2)
        e["_bars_held"] = int(j - i)
        e["_t1"] = float(t1)
        m0 = float(ema34[i]) if np.isfinite(ema34[i]) else float(e["entry"])
        e["_sl"] = round(max(abs(float(e["entry"]) - m0), 4.0), 2)
        if 0 <= j < len(idx):
            e["_exit_hm"] = pd.Timestamp(idx[j]).tz_convert("Asia/Kolkata").strftime("%H:%M")
        else:
            e["_exit_hm"] = "?"


def trade_rows(calls):
    lines = [
        "| Day | Entry | Side | Pattern | Entry₹ | Exit | Exit₹ | Reason | Pts | Bars | Result |",
        "|---|---|---|---|---:|---|---:|---|---:|---:|---|",
    ]
    for e in calls:
        res = "WIN" if e["_win"] else "LOSS"
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
            f"{e['entry']:.2f} | {e.get('_exit_hm','?')} | {e.get('_exit_px',0):.2f} | "
            f"`{e.get('_reason')}` | {e.get('_pts',0):+.2f} | {e.get('_bars_held',0)} | **{res}** |"
        )
    return lines


def main() -> int:
    print("NIFTY last 1m · session cut 09:30–14:30 · high T1", flush=True)
    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    data_hi = str(raw.index.max().date())
    hold_lo = str((pd.Timestamp(data_hi) - pd.DateOffset(months=1) + pd.Timedelta(days=1)).date())
    hold_lo = max(hold_lo, WIN_LO)
    print(f"window {hold_lo} → {data_hi}", flush=True)

    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    idx = df.index
    vix = vixmod.load_vix()

    cache = next(PACK.glob("events_2025-11-17_*.pkl"))
    xs = pickle.load(cache.open("rb"))
    hold = [e for e in xs if hold_lo <= e["day"] <= data_hi]
    print(f"events={len(hold)} (all hours)", flush=True)

    fwdmod.enrich_evt(hold, h, l, c, o)
    enrich_structure(hold, h, l, c, o, vix)
    enrich_prior3(hold, h, l, c, o)
    enrich_deep(hold, h, l, c, o, df)
    enrich_ma_layers(hold, df)
    enrich_ind(hold, df)

    sess = [e for e in hold if in_session(e)]
    print(f"events in 09:30–14:30 = {len(sess)}", flush=True)

    days = sorted({e["day"] for e in hold})  # calendar days with any event
    # prefer days that still have a session-window event
    days_sess = sorted({e["day"] for e in sess})
    nd = len(days_sess)
    print(f"session days={nd} {days_sess[0]}→{days_sess[-1]}", flush=True)

    by = defaultdict(list)
    for e in hold:
        by[e["day"]].append(e)

    lines = [
        "# NIFTY 1m — last 1 month · session cut + high T1",
        "",
        f"Window **`{hold_lo}` → `{data_hi}`** · session days **{nd}**",
        "",
        "## Rules",
        "",
        "- **Skip entry** before **09:30** and from **14:30–15:15** (no late entries)",
        "- **Allow entry** only **09:30 ≤ t < 14:30**",
        "- **HELD:** `DI_ok` ∧ `gate_hard34` ∧ `vwap_with` · first / day",
        "- **Exit:** EMA34 trail strict · T1 varies · max ~120 bars",
        "- ORACLE = first path-win in the same session window (peek)",
        "",
        "| T1 | HELD n | HELD Hit% | HELD Cover | ORACLE Hit% | ORACLE Cover |",
        "|---:|---:|---:|---:|---:|---:|",
    ]

    best_t1 = None
    best_calls = None
    best_st = None

    for t1 in T1_GRID:
        score_all(hold, h, l, c, ema34, idx, t1)
        held_calls, or_calls = [], []
        for d in days_sess:
            rows = by[d]
            hc = first_pass(rows, held_session)
            if hc:
                held_calls.append(hc)
            oc = oracle_day(rows, in_session)
            if oc:
                or_calls.append(oc)
        st_h = summarize(held_calls, nd)
        st_o = summarize(or_calls, nd)
        tag = " *(lock)*" if t1 == 12 else ""
        print(
            f"  T1={t1:.0f}{tag}: HELD {st_h['n']}@{st_h['hit']}%/{st_h['cover']}%  "
            f"ORACLE {st_o['n']}@{st_o['hit']}%/{st_o['cover']}%",
            flush=True,
        )
        lines.append(
            f"| **{t1:.0f}**{tag} | {st_h['n']} | {st_h['hit']}% | {st_h['cover']}% | "
            f"{st_o['hit']}% | {st_o['cover']}% |"
        )
        # prefer higher T1 among solid hit+cover; keep ledger for best hit then cover then t1
        key = (st_h["hit"], st_h["cover"], t1)
        if best_st is None or key > (best_st["hit"], best_st["cover"], best_t1 or 0):
            best_t1, best_calls, best_st = t1, list(held_calls), st_h

    def snapshot_calls(t1):
        score_all(hold, h, l, c, ema34, idx, t1)
        out = []
        for d in days_sess:
            hc = first_pass(by[d], held_session)
            if not hc:
                continue
            out.append(
                {
                    "day": hc["day"],
                    "hm": hc["hm"],
                    "decision": hc["decision"],
                    "primary": hc["primary"],
                    "entry": hc["entry"],
                    "_exit_hm": hc.get("_exit_hm"),
                    "_exit_px": hc.get("_exit_px"),
                    "_reason": hc.get("_reason"),
                    "_pts": hc.get("_pts"),
                    "_bars_held": hc.get("_bars_held"),
                    "_win": hc.get("_win"),
                }
            )
        return out

    # ledgers for lock T1=12 and high T1=30 (immutable snapshots)
    calls_12 = snapshot_calls(12.0)
    calls_30 = snapshot_calls(30.0)

    for label, calls in (("12", calls_12), ("30", calls_30)):
        w = sum(1 for e in calls if e["_win"])
        lines += [
            f"## HELD trades @ T1={label} (entry 09:30–14:30)",
            "",
            *trade_rows(calls),
            "",
            f"n={len(calls)} · W={w} L={len(calls)-w} · "
            f"**{round(100 * w / len(calls), 2) if calls else 0}%** hit",
            "",
        ]

    print("\n=== HELD T1=12 session-cut ===", flush=True)
    for e in calls_12:
        print(
            f"  {e['day']} {e['hm']} {e['decision']:4} {e['primary']:16} "
            f"in={e['entry']:.1f} → {e['_exit_hm']} out={e['_exit_px']:.1f} "
            f"{e['_reason']:5} {e['_pts']:+.1f} {'WIN' if e['_win'] else 'LOSS'}",
            flush=True,
        )
    print("\n=== HELD T1=30 session-cut ===", flush=True)
    for e in calls_30:
        print(
            f"  {e['day']} {e['hm']} {e['decision']:4} {e['primary']:16} "
            f"in={e['entry']:.1f} → {e['_exit_hm']} out={e['_exit_px']:.1f} "
            f"{e['_reason']:5} {e['_pts']:+.1f} {'WIN' if e['_win'] else 'LOSS'}",
            flush=True,
        )

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
