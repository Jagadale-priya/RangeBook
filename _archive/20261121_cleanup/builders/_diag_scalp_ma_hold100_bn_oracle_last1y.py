"""BANKNIFTY 1m — ORACLE path (EMA34 trail) last ~1 year.

Same exit family as NIFTY HOLD100: T1 before close flips vs EMA34.
Oracle = ≥1 path-win event that day (1/day first-win).

  python -u prod_live/tests/builders/_diag_scalp_ma_hold100_bn_oracle_last1y.py
"""
from __future__ import annotations

import pickle
import sys
from collections import defaultdict
from pathlib import Path

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
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers, summarize  # noqa: E402

BN_CSV = ROOT / "stock_signal_data" / "fno_validate" / "BANKNIFTY_1m_kite.csv"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "banknifty_1m_scalp_ma_oracle"
OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "BANKNIFTY_1M_SCALP_MA_ORACLE_LAST1Y.md"

# locked NIFTY T1 + BN-scaled grid (BN ~2× NIFTY points)
T1_GRID = (12.0, 20.0, 25.0, 30.0, 40.0, 50.0)


def load_bn_1m() -> pd.DataFrame:
    if not BN_CSV.is_file():
        raise FileNotFoundError(BN_CSV)
    raw = base._norm(pd.read_csv(BN_CSV))
    print(f"  BANKNIFTY_1m_kite.csv: {len(raw)} bars {raw.index.min()} → {raw.index.max()}", flush=True)
    return raw


def oracle_day(xs):
    for e in sorted(xs, key=lambda x: x["mins"]):
        if e.get("_win"):
            return e
    return None


def month_block(title, calls):
    rows = [f"### {title}", "", "| Month | n | Hit% | W | L |", "|---|---:|---:|---:|---:|"]
    by_m = defaultdict(list)
    for e in calls:
        by_m[e["day"][:7]].append(e)
    for m in sorted(by_m):
        xs = by_m[m]
        w = sum(1 for e in xs if e["_win"])
        rows.append(f"| {m} | {len(xs)} | {round(100 * w / len(xs), 2)}% | {w} | {len(xs) - w} |")
    rows.append("")
    return rows


def main() -> int:
    PACK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    print("BANKNIFTY ORACLE · EMA34 trail · last 1 year", flush=True)
    raw = load_bn_1m()
    data_hi = str(raw.index.max().date())
    hold_lo = str((pd.Timestamp(data_hi) - pd.DateOffset(years=1) + pd.Timedelta(days=1)).date())
    data_lo = str(raw.index.min().date())
    hold_lo = max(hold_lo, data_lo)
    print(f"window {hold_lo} → {data_hi}", flush=True)

    # warmup bars before window for EMA/ATR
    warm = (pd.Timestamp(hold_lo, tz="Asia/Kolkata") - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    raw = raw[raw.index >= pd.Timestamp(warm, tz="Asia/Kolkata")]

    print("[1] textbook + RSI + MA…", flush=True)
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values

    ev_cache = PACK / f"events_{hold_lo}_{data_hi}.pkl"
    if ev_cache.exists():
        xs = pickle.load(ev_cache.open("rb"))
        print(f"[2] events cache n={len(xs)}", flush=True)
    else:
        print(f"[2] collect events {hold_lo}→{data_hi}…", flush=True)
        xs = scalp.collect_scalp_events(df, hold_lo, data_hi)
        pickle.dump(xs, ev_cache.open("wb"), protocol=pickle.HIGHEST_PROTOCOL)
        print(f"    n={len(xs)}", flush=True)

    days = sorted({e["day"] for e in xs})
    nd = len(days)
    print(f"days={nd} {days[0]}→{days[-1]} events={len(xs)}", flush=True)

    lines = [
        "# BANKNIFTY 1m — ORACLE last 1 year",
        "",
        f"Window **`{hold_lo}` → `{data_hi}`** · **{nd}** days · exit EMA34 trail strict · 1/day first-win",
        "",
        "Same event universe as NIFTY scalp (textbook patterns). Oracle = day has ≥1 path win.",
        "",
        "| T1 | Oracle calls | Hit% | Cover | all_win | avg_sl |",
        "|---:|---:|---:|---:|:---:|---:|",
    ]

    best_locked = None
    for t1 in T1_GRID:
        for e in xs:
            ok, reason, sl, t1v = path_ma_trail_strict(
                h, l, c, ema34, int(e["full_i"]), e["decision"], t1
            )
            e["_win"] = bool(ok)
            e["_sl"] = float(sl or 0)
            e["_t1"] = float(t1v)
            e["_reason"] = reason

        by = defaultdict(list)
        for e in xs:
            by[e["day"]].append(e)
        or_calls = [oracle_day(by[d]) for d in days]
        or_calls = [e for e in or_calls if e]
        st = summarize(or_calls, nd)
        tag = " **(NIFTY lock)**" if t1 == 12.0 else ""
        print(f"  T1={t1:.0f}{tag}: ORACLE {st}", flush=True)
        lines.append(
            f"| **{t1:.0f}**{tag} | {st['n']} | {st['hit']}% | {st['cover']}% | {st['all_win']} | {st['avg_sl']} |"
        )
        if t1 == 12.0:
            best_locked = (st, or_calls)

    lines.append("")
    if best_locked:
        st, calls = best_locked
        lines += month_block("ORACLE T1=12 by month", calls)
        lines += [
            f"Locked T1=12: **{st['hit']}%** hit · **{st['cover']}%** cover · n={st['n']} / {nd} days",
            "",
        ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
