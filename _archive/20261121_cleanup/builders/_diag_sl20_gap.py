"""Diagnose SL≤20 daily 100% gap + find working oracle/rule."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401,E402

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_chart_only_100 as co  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_daily_must_100 as dm  # noqa: E402
import research_nifty_1m_daily_must_sl20 as S  # noqa: E402


def main() -> int:
    raw = base.load_existing_1m()
    end = raw.index.max()
    test_hi = end.strftime("%Y-%m-%d")
    test_lo_ts = end - pd.Timedelta(days=92)
    test_lo = test_lo_ts.strftime("%Y-%m-%d")
    cal_hi = (test_lo_ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    cal_lo = (test_lo_ts - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    raw = raw[raw.index >= pd.Timestamp(cal_lo, tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = dm.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values

    print("collect…", flush=True)
    cal_by = S.collect_all_cands(df, cal_lo, cal_hi, (560, 750))
    test_by = S.collect_all_cands(df, test_lo, test_hi, (560, 750))

    for t1_need in (5.0, 6.0, 8.0, 10.0):
        for label, by in (("cal", cal_by), ("l3m", test_by)):
            bad = []
            for day, cands in by.items():
                ok = any(e["mae"] < 20 - 1e-6 and e["mfe"] >= t1_need for e in cands)
                if not ok:
                    # best mae among mfe>=t1 or best mfe among mae<20
                    best = min(cands, key=lambda e: e["mae"] if e["mfe"] >= t1_need else 1e9)
                    bad.append((day, best["mae"], best["mfe"], best["hm"], best["decision"], best["primary"]))
            print(f"t1>={t1_need} {label} infeas={len(bad)}/{len(by)}", flush=True)
            for b in bad[:5]:
                print(f"  {b}", flush=True)

    # Can every day win with fixed SL=20 T1=5 via path_hit on some cand?
    def oracle_fixed(by, sl, t1):
        miss = []
        for day, cands in by.items():
            hit = False
            for e in cands:
                if e["mae"] >= sl - 1e-9 or e["mfe"] < t1 - 1e-9:
                    continue
                win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
                if win and out == "t1":
                    hit = True
                    break
            if not hit:
                miss.append(day)
        return miss

    for sl, t1 in [(20, 5), (20, 8), (20, 10), (18, 5), (15, 5), (12, 5), (10, 5)]:
        cm = oracle_fixed(cal_by, sl, t1)
        tm = oracle_fixed(test_by, sl, t1)
        print(
            f"oracle fixed SL={sl} T1={t1}: cal miss {len(cm)} {cm[:3]} | l3m miss {len(tm)} {tm[:3]}",
            flush=True,
        )

    # Also try SL = min(1.2*candle, 20) dynamic per cand — oracle any win
    def oracle_dyn_candle(by, sl_k, t1_floor):
        miss = []
        for day, cands in by.items():
            hit = False
            for e in cands:
                sl = min(max(sl_k * e["sl_candle"], 4.0), 20.0)
                t1 = max(t1_floor, min(1.0 * e["t1_body"], 25.0))
                if t1 < 5:
                    t1 = t1_floor
                if e["mae"] >= sl - 1e-9 or e["mfe"] < t1 - 1e-9:
                    continue
                win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
                if win and out == "t1":
                    hit = True
                    break
            if not hit:
                miss.append(day)
        return miss

    for sl_k, t1f in [(1.0, 5), (1.2, 5), (1.5, 5), (1.0, 8), (1.2, 8)]:
        cm = oracle_dyn_candle(cal_by, sl_k, t1f)
        tm = oracle_dyn_candle(test_by, sl_k, t1f)
        print(
            f"oracle ccap sl_k={sl_k} t1f={t1f}: cal miss {len(cm)} | l3m miss {len(tm)} {tm[:3]}",
            flush=True,
        )

    # Expand window / dual probe: for miss days of SL20 T1=5, scan ALL bars both sides
    cm = oracle_fixed(cal_by, 20, 5)
    tm = oracle_fixed(test_by, 20, 5)
    print("\nDeep scan miss days both sides all bars 9:20-15:15…", flush=True)
    idx_map = {ts: i for i, ts in enumerate(df.index)}
    for day in (cm + tm)[:10]:
        sess = df[df["day"] == day]
        found = None
        for pos in range(3, len(sess)):
            row = sess.iloc[pos]
            mins = int(row["mins"])
            if mins < 560 or mins > 915:
                continue
            for side in ("BUY", "SELL"):
                entry = float(row["Close"])
                full_i = idx_map[sess.index[pos]]
                mae, mfe = co.excursion(h, l, c, full_i, side, max_bars=200)
                if mae >= 19.99 or mfe < 5:
                    continue
                win, out = co.path_hit(h, l, c, full_i, side, 20.0, 5.0)
                if win and out == "t1":
                    found = (row["hm"], side, mae, mfe)
                    break
            if found:
                break
        print(f"  {day} deep={found}", flush=True)

    print("DONE gap diag", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
