"""1-minute MA cross: 3 closes on the new side of the average.

Rules are scored on sessions before 2025-11-16. The last year is only reported.
A win is the first target printing before the stop, same session.
Same bar touching both is a loss. Unresolved at the close is not a win.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"c:\Users\Priyanka\Agent")
CSV = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_1m_kite.csv"
OUT = ROOT / "prod_live" / "reports" / "1y" / "MA3_1M_5Y.json"
SELECT_END = np.datetime64("2025-11-16")
LENGTHS = (8, 10, 15, 20, 30)
BRACKETS = ((15, 15), (20, 20), (25, 30), (30, 30))
SLOPE_LOOK = 10


def _load() -> pd.DataFrame:
    df = pd.read_csv(CSV, parse_dates=["date"])
    df = df.sort_values("date")
    ts = df["date"]
    mins = ts.dt.hour * 60 + ts.dt.minute
    df = df.loc[(mins >= 9 * 60 + 15) & (mins <= 15 * 60 + 29)].copy()
    df["day"] = ts.dt.tz_convert("Asia/Kolkata").dt.strftime("%Y-%m-%d")
    return df


def _outcomes(high: np.ndarray, low: np.ndarray, entry_i: int, entry: float, side: int, sl: float, t1: float) -> str:
    if side > 0:
        stop = entry - sl
        target = entry + t1
    else:
        stop = entry + sl
        target = entry - t1
    for j in range(entry_i + 1, len(high)):
        hi = float(high[j])
        lo = float(low[j])
        if side > 0:
            hit_sl = lo <= stop
            hit_t1 = hi >= target
        else:
            hit_sl = hi >= stop
            hit_t1 = lo <= target
        if hit_sl and hit_t1:
            return "loss"
        if hit_sl:
            return "loss"
        if hit_t1:
            return "win"
    return "open"


def _signals(close: np.ndarray, length: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return index, side, chop20, slope_pts for a fresh 3-close cross."""
    n = len(close)
    ma = np.full(n, np.nan)
    if n < length + 4:
        return np.array([], dtype=int), np.array([]), np.array([]), np.array([])
    csum = np.cumsum(close)
    ma[length - 1] = csum[length - 1] / length
    ma[length:] = (csum[length:] - csum[:-length]) / length
    above = close > ma
    idx = []
    side = []
    chop = []
    slope = []
    flips = np.zeros(n, dtype=np.int8)
    flips[1:] = (above[1:] != above[:-1]).astype(np.int8)
    # rolling flip count over the prior 20 bars, not including the 3 confirm bars' internal flips fully:
    # count flips in [i-22, i-3] so the signal itself is not the chop score.
    run = np.cumsum(flips)
    for i in range(length + 3, n - 1):
        if not (above[i] and above[i - 1] and above[i - 2]) and not (
            (not above[i]) and (not above[i - 1]) and (not above[i - 2])
        ):
            continue
        crossed = above[i - 2] != above[i - 3]
        if not crossed or np.isnan(ma[i]) or np.isnan(ma[i - SLOPE_LOOK]):
            continue
        s = 1 if above[i] else -1
        lo = i - 22
        if lo < 1:
            continue
        flips20 = int(run[i - 3] - run[lo])
        slp = float(ma[i] - ma[i - SLOPE_LOOK])
        idx.append(i)
        side.append(s)
        chop.append(flips20)
        slope.append(slp)
    return (
        np.asarray(idx, dtype=int),
        np.asarray(side, dtype=int),
        np.asarray(chop, dtype=int),
        np.asarray(slope, dtype=float),
    )


def main() -> None:
    df = _load()
    days = df["day"].unique()
    print("rows", len(df), "sessions", len(days), "first", days[0], "last", days[-1], flush=True)
    # tickets: day, length, side, chop, slope, green3, results per bracket
    rows = []
    for day, g in df.groupby("day", sort=True):
        close = g["Close"].to_numpy(dtype=float)
        high = g["High"].to_numpy(dtype=float)
        low = g["Low"].to_numpy(dtype=float)
        open_ = g["Open"].to_numpy(dtype=float)
        pre = np.datetime64(day) < SELECT_END
        for length in LENGTHS:
            idx, side, chop, slope = _signals(close, length)
            for k in range(len(idx)):
                i = int(idx[k])
                s = int(side[k])
                bodies = close[i - 2 : i + 1] - open_[i - 2 : i + 1]
                green3 = bool(np.all(bodies > 0)) if s > 0 else bool(np.all(bodies < 0))
                rec = {
                    "day": day,
                    "pre": bool(pre),
                    "length": length,
                    "side": s,
                    "chop": int(chop[k]),
                    "slope": float(slope[k]),
                    "green3": green3,
                    "entry": float(close[i]),
                }
                for sl, t1 in BRACKETS:
                    rec[f"{sl}_{t1}"] = _outcomes(high, low, i, float(close[i]), s, sl, t1)
                rows.append(rec)
        if len(rows) and len(rows) % 50000 < 400:
            print("tickets", len(rows), "through", day, flush=True)
    tix = pd.DataFrame(rows)
    print("tickets", len(tix), flush=True)

    def agg(frame: pd.DataFrame, col: str) -> dict:
        if frame.empty:
            return {"n": 0, "win": 0, "loss": 0, "open": 0, "hit": None}
        vc = frame[col].value_counts()
        w = int(vc.get("win", 0))
        l = int(vc.get("loss", 0))
        o = int(vc.get("open", 0))
        decided = w + l
        return {
            "n": int(len(frame)),
            "win": w,
            "loss": l,
            "open": o,
            "hit": None if decided == 0 else round(100.0 * w / decided, 2),
        }

    filters = {
        "raw": lambda d: d,
        "green3": lambda d: d[d["green3"]],
        "slope_agree": lambda d: d[((d["side"] > 0) & (d["slope"] > 0)) | ((d["side"] < 0) & (d["slope"] < 0))],
        "slope_1pt": lambda d: d[
            ((d["side"] > 0) & (d["slope"] >= 1.0)) | ((d["side"] < 0) & (d["slope"] <= -1.0))
        ],
        "slope_3pt": lambda d: d[
            ((d["side"] > 0) & (d["slope"] >= 3.0)) | ((d["side"] < 0) & (d["slope"] <= -3.0))
        ],
        "chop_le2": lambda d: d[d["chop"] <= 2],
        "chop_le4": lambda d: d[d["chop"] <= 4],
        "trend_chop2_slope1": lambda d: d[
            (d["chop"] <= 2)
            & (((d["side"] > 0) & (d["slope"] >= 1.0)) | ((d["side"] < 0) & (d["slope"] <= -1.0)))
        ],
        "trend_chop2_slope3_green": lambda d: d[
            (d["chop"] <= 2)
            & d["green3"]
            & (((d["side"] > 0) & (d["slope"] >= 3.0)) | ((d["side"] < 0) & (d["slope"] <= -3.0)))
        ],
    }

    report = {"select_before": "2025-11-16", "lengths": list(LENGTHS), "brackets": list(BRACKETS), "books": []}
    best = []
    for length in LENGTHS:
        base = tix[tix["length"] == length]
        for name, fn in filters.items():
            part = fn(base)
            for sl, t1 in BRACKETS:
                col = f"{sl}_{t1}"
                pre = agg(part[part["pre"]], col)
                post = agg(part[~part["pre"]], col)
                row = {
                    "length": length,
                    "filter": name,
                    "sl": sl,
                    "t1": t1,
                    "pre": pre,
                    "test": post,
                }
                report["books"].append(row)
                if pre["n"] >= 30 and pre["hit"] is not None:
                    best.append((pre["hit"], pre["n"], post["hit"], post["n"], row))
    best.sort(key=lambda x: (-x[0], -x[1]))
    report["best_pre_n30"] = [
        {
            "pre_hit": a,
            "pre_n": b,
            "test_hit": c,
            "test_n": d,
            "length": r["length"],
            "filter": r["filter"],
            "sl": r["sl"],
            "t1": r["t1"],
            "pre": r["pre"],
            "test": r["test"],
        }
        for a, b, c, d, r in best[:25]
    ]
    # any 100% on test with n>=20
    hundred = [
        b
        for b in report["books"]
        if b["test"]["hit"] == 100.0 and b["test"]["win"] >= 20
    ]
    report["test_100_n20"] = hundred
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", OUT)
    print("TOP pre")
    for item in report["best_pre_n30"][:12]:
        print(
            f"L{item['length']} {item['filter']} {item['sl']}/{item['t1']} "
            f"pre {item['pre']['win']}/{item['pre']['win']+item['pre']['loss']}={item['pre_hit']} "
            f"n {item['pre_n']} open {item['pre']['open']} | "
            f"test {item['test']['win']}/{item['test']['win']+item['test']['loss']}={item['test_hit']} "
            f"n {item['test_n']}"
        )
    print("test 100 with n>=20", len(hundred))


if __name__ == "__main__":
    main()
