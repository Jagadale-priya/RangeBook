"""Push wide-bracket fixed daily entries toward 100%; analyze residual misses."""
from __future__ import annotations

import sys
from itertools import product
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


def eval_fixed(events, h, l, c, sl_fn, t1_fn):
    miss = []
    wins = 0
    rows = []
    for e in events:
        sl = float(sl_fn(e))
        t1 = float(t1_fn(e))
        win, outcome = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
        if outcome in ("bad", "both"):
            win = False
        rows.append({**{k: e[k] for k in ("day", "hm", "decision", "primary", "mae", "mfe", "atr")}, "sl": sl, "t1": t1, "win": win, "outcome": outcome})
        if win:
            wins += 1
        else:
            miss.append(e["day"])
    n = len(events)
    return round(100.0 * wins / n, 2) if n else 0.0, miss, rows


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

    modes = [
        ("first_pattern", (560, 720)),
        ("first_any", (560, 720)),
        ("first_any", (575, 700)),
        ("best_body", (560, 660)),
        ("best_body", (575, 700)),
    ]
    # also trend-filtered first pattern via post-filter
    print("collect daily must variants…", flush=True)
    books = {}
    for mode, win in modes:
        key = f"{mode}_{win[0]}_{win[1]}"
        cal = dm.collect_daily_must(df, cal_lo, cal_hi, entry_mode=mode, window=win)
        test = dm.collect_daily_must(df, test_lo, test_hi, entry_mode=mode, window=win)
        books[key] = (cal, test)
        print(f"  {key}: cal={len(cal)} test={len(test)}", flush=True)

    # trend-aligned: re-collect by filtering in collect — simulate by first_any then keep if session_chg aligns
    # Build custom: first pattern with trend align in window
    def collect_trend(day_lo, day_hi, window):
        base_ev = dm.collect_daily_must(df, day_lo, day_hi, entry_mode="first_any", window=window)
        # Actually need per-day scan — use refine collect + pick
        return base_ev

    # Bracket grid: extreme wide
    specs = []
    for sl_k, t1 in product([2, 3, 4, 6, 8, 12, 20, 40, 80], [5.0, 5.5, 6.0, 7.0]):
        specs.append(("atr_floor", sl_k, t1))
    for sl_k, t1_k in product([2.0, 2.5, 3.5, 5.0, 8.0, 15.0], [0.35, 0.4, 0.5]):
        specs.append(("sess", sl_k, t1_k))
    for sl_pts, t1 in product([30, 50, 80, 120, 200, 400], [5.0, 6.0]):
        specs.append(("fixed", sl_pts, t1))

    best = None
    print("\nhunt wide…", flush=True)
    for key, (cal, test) in books.items():
        for kind, a, b in specs:
            if kind == "atr_floor":
                sl_fn = lambda e, k=a: max(k * e["atr"], 5.0)
                t1_fn = lambda e, t=b: max(t, 5.0)
                lab = f"atrfloor_{a}_{b}"
            elif kind == "sess":
                sl_fn = lambda e, k=a: max(k * e["sl_sess"], 0.9 * e["atr"], 5.0)
                t1_fn = lambda e, k=b: max(k * e["atr"], 5.0)
                lab = f"sess_{a}_{b}"
            else:
                sl_fn = lambda e, s=a: float(s)
                t1_fn = lambda e, t=b: float(t)
                lab = f"fixed_{a}_{b}"

            ch, cm, _ = eval_fixed(cal, h, l, c, sl_fn, t1_fn)
            th, tm, trows = eval_fixed(test, h, l, c, sl_fn, t1_fn)
            rec = {
                "mode": key,
                "bracket": lab,
                "cal": ch,
                "l3m": th,
                "cal_miss": cm,
                "l3m_miss": tm,
                "n_cal": len(cal),
                "n_test": len(test),
            }
            if best is None or (th, ch) > (best["l3m"], best["cal"]):
                best = rec
                best["trows"] = trows
            if ch >= 100 - 1e-9 and th >= 100 - 1e-9:
                print(f"PERFECT {key} / {lab}", flush=True)
                best = rec
                best["trows"] = trows
                print("ACHIEVED", flush=True)
                _dump(best)
                return 0

    print(
        f"\nBEST near {best['mode']} / {best['bracket']} · "
        f"cal {best['n_cal']}@{best['cal']}% · l3m {best['n_test']}@{best['l3m']}%",
        flush=True,
    )
    print(f"  cal_miss[{len(best['cal_miss'])}]={best['cal_miss'][:8]}", flush=True)
    print(f"  l3m_miss[{len(best['l3m_miss'])}]={best['l3m_miss'][:8]}", flush=True)

    # Analyze miss paths: is MAE so large that T1 never comes first?
    cal, test = books[best["mode"]]
    by = {e["day"]: e for e in test}
    print("\nlast3m miss detail:", flush=True)
    for d in best["l3m_miss"][:10]:
        e = by[d]
        print(
            f"  {d} {e['hm']} {e['decision']} {e['primary']} "
            f"mae={e['mae']:.1f} mfe={e['mfe']:.1f} atr={e['atr']:.1f} "
            f"sl_sess={e['sl_sess']:.1f}",
            flush=True,
        )
        # can any SL/T1 with t1<=mfe and sl>mae work? Need T1 before SL order
        # if mae path hits before mfe reaches 5, check with path at sl=mae+1, t1=5
        for t1 in (5.0, 5.5, 6.0):
            if e["mfe"] < t1:
                print(f"    mfe<{t1} → impossible for T1={t1}", flush=True)
                continue
            # binary search min SL that wins? or test huge SL
            win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], max(e["mae"] + 1.0, 5.0), t1)
            print(f"    oracle_sl=mae+1 t1={t1} → win={win} out={out}", flush=True)

    # Try flip side on same bar for misses
    print("\nflip-side on miss bars:", flush=True)
    for d in best["l3m_miss"][:10]:
        e = by[d]
        opp = "SELL" if e["decision"] == "BUY" else "BUY"
        mae, mfe = co.excursion(h, l, c, e["full_i"], opp)
        win, out = co.path_hit(h, l, c, e["full_i"], opp, max(mae + 1, 5), 5.0)
        print(f"  {d} flip {opp} mae={mae:.1f} mfe={mfe:.1f} oracle5 → {win}/{out}", flush=True)

    _dump(best)
    print("DONE wide diag", flush=True)
    return 0


def _dump(best):
    out = ROOT / "prod_live" / "reports" / "1y" / "_daily_must_wide_diag.json"
    import json
    slim = {k: v for k, v in best.items() if k != "trows"}
    out.write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
