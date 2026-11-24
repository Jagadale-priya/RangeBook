"""Confirm frozen MORNING_CALIBRATED_V1 NIFTY >=95% full-containment metrics.

Accuracy = (Low >= box_lo) AND (High <= box_hi).
Method: ATR14 * calibrated mult, open-locked + pre915 prior-close box.

Run: python -u prod_live/tests/confirm_morning_context_1y_match.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "legacy"))

import morning_session_context as msc  # noqa: E402

NIFTY_PATH = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_daily_nse.csv"
EPS_INSIDE = 0.015
EPS_WIDTH = 0.005


def load_nifty() -> pd.DataFrame:
    df = pd.read_csv(NIFTY_PATH)
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.normalize()
    for c in ("Open", "High", "Low", "Close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["Open", "High", "Low", "Close"]).sort_values("Date").reset_index(drop=True)


def open_locked_stats(df: pd.DataFrame, n: int) -> dict:
    h, l, c, o = df["High"], df["Low"], df["Close"], df["Open"]
    atr = msc.wilder_atr(h, l, c, 14)
    prev_c = c.shift(1)
    atr_prev = atr.shift(1)
    width = np.maximum(atr_prev * msc.ATR_MULT, prev_c * msc.FLOOR_PCT)
    half = width / 2.0
    hi = o + half * msc.UP_HALF_MULT
    lo = o - half * msc.DN_HALF_MULT
    gap = o - prev_c
    big = (gap.abs() / prev_c) >= 0.0035
    extra = np.minimum(gap.abs(), width * 0.35)
    hi = np.where(big & (gap > 0), hi + extra, hi)
    lo = np.where(big & (gap < 0), lo - extra, lo)
    full = (l >= lo) & (h <= hi)
    eff_w = (hi - lo) / prev_c
    use = full.notna() & width.notna() & (width > 0) & prev_c.notna()
    idx = df.index[use][-n:]
    return {
        "days": int(len(idx)),
        "inside_pct": float(full.loc[idx].mean()),
        "median_width_pct": float(pd.Series(eff_w, index=df.index).loc[idx].median()),
        "end": str(df.loc[idx[-1], "Date"].date()) if len(idx) else None,
    }


def main() -> int:
    df = load_nifty()
    got1 = open_locked_stats(df, 252)
    got3 = open_locked_stats(df, 756)
    got5 = open_locked_stats(df, 1260)
    fails = []

    if msc.LOGIC_TAG != "MORNING_CTX_V4":
        fails.append(f"logic_tag {msc.LOGIC_TAG}")
    for label, got, floor in (("1y", got1, 0.95), ("3y", got3, 0.95), ("5y", got5, 0.95)):
        if got["inside_pct"] < floor:
            fails.append(f"{label} containment {got['inside_pct']:.4f} < {floor}")
    if abs(got1["inside_pct"] - msc.LOCKED_1Y["range_open_inside_pct"]) > EPS_INSIDE:
        fails.append(f"1y {got1['inside_pct']:.4f} vs locked {msc.LOCKED_1Y['range_open_inside_pct']}")
    if abs(got3["inside_pct"] - msc.LOCKED_3Y["range_open_inside_pct"]) > EPS_INSIDE:
        fails.append(f"3y {got3['inside_pct']:.4f} vs locked {msc.LOCKED_3Y['range_open_inside_pct']}")
    if abs(got5["inside_pct"] - msc.LOCKED_5Y["range_open_inside_pct"]) > EPS_INSIDE:
        fails.append(f"5y {got5['inside_pct']:.4f} vs locked {msc.LOCKED_5Y['range_open_inside_pct']}")
    if abs(got3["median_width_pct"] - msc.LOCKED_3Y["range_open_median_width_pct"]) > EPS_WIDTH:
        fails.append(f"3y width {got3['median_width_pct']:.4f} vs locked {msc.LOCKED_3Y['range_open_median_width_pct']}")

    row = msc.build_session_context("NIFTY", df.tail(300), open_px=None, vix_level=16.0)
    try:
        msc.assert_no_calls(row)
    except AssertionError as exc:
        fails.append(str(exc))
    if row.get("bias") != "NEUTRAL":
        fails.append("bias must be NEUTRAL")
    if row.get("gap") != "NATURAL":
        fails.append("pre915 gap must be NATURAL")
    if row.get("mode") != "pre915":
        fails.append(f"mode {row.get('mode')}")
    if "pre915_atr35x" not in str((row.get("day_range") or {}).get("method")):
        fails.append(f"pre915 method {row.get('day_range')}")

    # PRE915 provisional containment (center prior close, ATR*3.5 dn120)
    h, l, c = df["High"], df["Low"], df["Close"]
    atr = msc.wilder_atr(h, l, c, 14)
    prev_c = c.shift(1)
    atr_prev = atr.shift(1)
    width = np.maximum(atr_prev * msc.PRE915_ATR_MULT, prev_c * msc.FLOOR_PCT)
    half = width / 2.0
    hi = prev_c + half * msc.UP_HALF_MULT
    lo = prev_c - half * msc.DN_HALF_MULT
    full = (l >= lo) & (h <= hi)
    use = full.notna() & width.notna() & prev_c.notna()
    pre3 = float(full.loc[df.index[use][-756:]].mean())
    if pre3 < 0.95:
        fails.append(f"pre915 3y containment {pre3:.4f} < 0.95")
    if abs(pre3 - msc.LOCKED_PRE915["3y_inside_pct"]) > 0.02:
        fails.append(f"pre915 3y {pre3:.4f} vs locked {msc.LOCKED_PRE915['3y_inside_pct']}")

    print({
        "logic_tag": msc.LOGIC_TAG,
        "got_1y_openlocked": got1,
        "got_3y_openlocked": got3,
        "got_5y_openlocked": got5,
        "pre915_3y_containment": round(pre3, 4),
        "status": "FAIL" if fails else "PASS",
        "fails": fails,
    })
    print("CONFIRM FAIL" if fails else "CONFIRM PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
