"""NIFTY last 1 month — entry + exit ledger (same EMA34 trail · T1=12).

Shows HELD (blind DI+hard34+VWAP) and ORACLE (first path-win) 1/day:
  where entry fired, where exit happened, reason, pts.

  python -u prod_live/tests/builders/_diag_scalp_ma_hold100_last1m_trades.py
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
REPORT = OUT / "NIFTY_1M_SCALP_MA_HOLD100_LAST1M_TRADES.md"
T1 = 12.0
MAX_BARS = 120


def path_ma_trail_detail(h, l, c, ma, i, side, t1_pts, max_bars=MAX_BARS):
    """Same as path_ma_trail_strict + exit bar / price / signed pts."""
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


def oracle_day(xs):
    for e in sorted(xs, key=lambda x: x["mins"]):
        if e.get("_win"):
            return e
    return None


def score_detail(e, h, l, c, ema34, idx):
    i = int(e["full_i"])
    ok, reason, exit_px, j, pts = path_ma_trail_detail(
        h, l, c, ema34, i, e["decision"], T1
    )
    e["_win"] = bool(ok)
    e["_reason"] = reason
    e["_exit_px"] = round(float(exit_px), 2)
    e["_exit_i"] = int(j)
    e["_pts"] = round(float(pts), 2)
    e["_bars_held"] = int(j - i)
    e["_t1"] = float(T1)
    # trail SL distance ≈ |entry − EMA34| at entry (informational)
    m0 = float(ema34[i]) if np.isfinite(ema34[i]) else float(e["entry"])
    e["_sl"] = round(max(abs(float(e["entry"]) - m0), 4.0), 2)
    if 0 <= j < len(idx):
        e["_exit_hm"] = pd.Timestamp(idx[j]).tz_convert("Asia/Kolkata").strftime("%H:%M")
    else:
        e["_exit_hm"] = "?"


def trade_table(title, calls):
    rows = [
        f"### {title}",
        "",
        "| Day | Entry | Side | Pattern | Entry₹ | Exit | Exit₹ | Reason | Pts | Bars | Result |",
        "|---|---|---|---|---:|---|---:|---|---:|---:|---|",
    ]
    w = l = 0
    for e in calls:
        res = "WIN" if e["_win"] else "LOSS"
        if e["_win"]:
            w += 1
        else:
            l += 1
        rows.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
            f"{e['entry']:.2f} | {e.get('_exit_hm','?')} | {e.get('_exit_px',0):.2f} | "
            f"`{e.get('_reason')}` | {e.get('_pts',0):+.2f} | {e.get('_bars_held',0)} | **{res}** |"
        )
    n = len(calls)
    hit = round(100 * w / n, 2) if n else 0.0
    rows += ["", f"n={n} · W={w} L={l} · **{hit}%** hit", ""]
    return rows, hit, n, w


def main() -> int:
    print("NIFTY last 1m · entry/exit ledger · EMA34 trail T1=12", flush=True)
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
    print(f"events={len(hold)}", flush=True)

    fwdmod.enrich_evt(hold, h, l, c, o)
    enrich_structure(hold, h, l, c, o, vix)
    enrich_prior3(hold, h, l, c, o)
    enrich_deep(hold, h, l, c, o, df)
    enrich_ma_layers(hold, df)
    enrich_ind(hold, df)

    for e in hold:
        score_detail(e, h, l, c, ema34, idx)

    days = sorted({e["day"] for e in hold})
    nd = len(days)
    by = defaultdict(list)
    for e in hold:
        by[e["day"]].append(e)

    held_calls = []
    or_calls = []
    for d in days:
        rows = by[d]
        hcall = first_pass(rows, held_gate)
        if hcall:
            held_calls.append(hcall)
        ocall = oracle_day(rows)
        if ocall:
            or_calls.append(ocall)

    st_h = summarize(held_calls, nd)
    st_o = summarize(or_calls, nd)
    print(f"days={nd} {days[0]}→{days[-1]}", flush=True)
    print(f"HELD   {st_h}", flush=True)
    print(f"ORACLE {st_o}", flush=True)

    lines = [
        "# NIFTY 1m — last 1 month entry/exit ledger",
        "",
        f"Window **`{hold_lo}` → `{data_hi}`** · **{nd}** days",
        "",
        "## Logic",
        "",
        "- **Entry universe:** textbook 1m candle patterns",
        "- **HELD filter (blind):** `DI_ok` ∧ `gate_hard34` ∧ `vwap_with` · first pass / day",
        "- **ORACLE:** first event that day that path-wins (peek — not live)",
        "- **Exit:** EMA34 trail strict · **T1=12** · win if T1 before close flips vs EMA34; else `ma_sl`",
        "- Max hold ~120 bars (~2h)",
        "",
        f"| Book | Calls | Hit% | Cover |",
        f"|---|---:|---:|---:|",
        f"| **HELD** | {st_h['n']} | {st_h['hit']}% | {st_h['cover']}% |",
        f"| **ORACLE** | {st_o['n']} | {st_o['hit']}% | {st_o['cover']}% |",
        "",
    ]

    h_rows, h_hit, h_n, h_w = trade_table("HELD trades (live-style 1/day)", held_calls)
    o_rows, o_hit, o_n, o_w = trade_table("ORACLE trades (first path-win / day)", or_calls)
    lines += h_rows + o_rows

    # compact console dump
    print("\n=== HELD entry → exit ===", flush=True)
    for e in held_calls:
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
