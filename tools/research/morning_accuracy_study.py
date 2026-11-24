"""Honest morning-box study on NSE Nifty daily bars.

Rules are fixed before the run. The winner is chosen on dates before 2024-01-01.
2024-01-01 onward is only a report. No parameter is fit on the report window.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(r"C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\NIFTY_daily_nse.csv")
SPLIT = "2024-01-01"


def wilder_atr(high, low, close, n=14):
    prev_c = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_c).abs(), (low - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def main():
    df = pd.read_csv(SRC, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
    h, l, c = df["High"], df["Low"], df["Close"]
    day_rng = (h - l).clip(lower=0)
    atr = wilder_atr(h, l, c, 14)
    # Everything used for day t must be known at the prior close.
    prev_c = c.shift(1)
    prev_rng = day_rng.shift(1)
    atr_prev = atr.shift(1)
    med20 = day_rng.shift(1).rolling(20).median()
    p80 = day_rng.shift(1).rolling(20).quantile(0.80)
    ret = c.pct_change()
    vol20 = ret.shift(1).rolling(20).std()
    sma50 = c.shift(1).rolling(50).mean()
    # RSI 14 on prior closes
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / down.replace(0, np.nan))).shift(1)

    price = prev_c
    floor = price * 0.004
    methods = {
        "current_max_yday_atr_floor": np.maximum(np.maximum(prev_rng, atr_prev), floor),
        "yesterday_range": prev_rng,
        "atr14": np.maximum(atr_prev, floor),
        "median_20_ranges": med20,
        "p80_20_ranges": p80,
        "vol20_1sd": (vol20 * price),
        "vol20_1_5sd": (vol20 * price * 1.5),
    }

    rows = []
    for name, width in methods.items():
        half = width / 2.0
        lo = price - half
        hi = price + half
        inside = (l >= lo) & (h <= hi)
        use = inside.notna() & width.notna() & (width > 0) & price.notna()
        part = pd.DataFrame({
            "date": df["Date"],
            "inside": inside,
            "width_pct": width / price,
        }).loc[use]
        for label, mask in (
            ("train", part["date"] < SPLIT),
            ("test", part["date"] >= SPLIT),
        ):
            sl = part.loc[mask]
            rows.append({
                "method": name,
                "window": label,
                "days": int(len(sl)),
                "inside_pct": round(float(sl["inside"].mean()), 4),
                "median_width_pct": round(float(sl["width_pct"].median()), 4),
                "score": round(float(sl["inside"].mean() / sl["width_pct"].median()), 4),
            })

    train = [r for r in rows if r["window"] == "train"]
    winner = max(train, key=lambda r: r["score"])
    current_train = next(r for r in train if r["method"] == "current_max_yday_atr_floor")
    test_winner = next(r for r in rows if r["window"] == "test" and r["method"] == winner["method"])
    test_current = next(r for r in rows if r["window"] == "test" and r["method"] == "current_max_yday_atr_floor")

    # Direction: next close vs prior close. Base rate is the share of up days.
    up = (c > prev_c)
    mom = ret.shift(1) > 0
    fade = ret.shift(1) < 0
    above_sma = prev_c > sma50
    rsi_up = rsi > 50
    rules = {
        "always_up": pd.Series(True, index=df.index),
        "yesterday_up_continues": mom,
        "yesterday_up_fades": fade,
        "above_sma50": above_sma,
        "rsi14_above_50": rsi_up,
    }
    dir_rows = []
    for name, pred_up in rules.items():
        ok = up.notna() & pred_up.notna()
        for label, mask in (("train", df["Date"] < SPLIT), ("test", df["Date"] >= SPLIT)):
            sl_ok = ok & mask
            pred = pred_up[sl_ok]
            actual = up[sl_ok]
            hit = (pred == actual)
            dir_rows.append({
                "rule": name,
                "window": label,
                "days": int(sl_ok.sum()),
                "up_day_rate": round(float(actual.mean()), 4),
                "accuracy": round(float(hit.mean()), 4),
            })

    # After 9:15 the same width is seated on the cash open. Still no look-ahead in the width.
    open_px = df["Open"]
    locked = []
    for name, width in (
        ("current_max_yday_atr_floor", methods["current_max_yday_atr_floor"]),
        ("p80_20_ranges", methods["p80_20_ranges"]),
    ):
        half = width / 2.0
        lo = open_px - half
        hi = open_px + half
        inside = (l >= lo) & (h <= hi)
        close_in = (c >= lo) & (c <= hi)
        use = inside.notna() & width.notna() & (width > 0) & open_px.notna()
        part = pd.DataFrame({"date": df["Date"], "inside": inside, "close_in": close_in, "width_pct": width / prev_c}).loc[use]
        for label, mask in (("train", part["date"] < SPLIT), ("test", part["date"] >= SPLIT)):
            sl = part.loc[mask]
            locked.append({
                "method": name,
                "anchor": "session_open",
                "window": label,
                "days": int(len(sl)),
                "high_low_inside_pct": round(float(sl["inside"].mean()), 4),
                "close_inside_pct": round(float(sl["close_in"].mean()), 4),
                "median_width_pct": round(float(sl["width_pct"].median()), 4),
            })

    out = {
        "source": str(SRC),
        "split": SPLIT,
        "note": "Box is centered on the prior close. Width uses only earlier bars. Score = inside rate / median width as a fraction of price. Winner is the highest train score.",
        "range": rows,
        "train_winner": winner["method"],
        "train_current_score": current_train["score"],
        "train_winner_score": winner["score"],
        "test_current": test_current,
        "test_winner": test_winner,
        "direction": dir_rows,
        "open_locked": locked,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
