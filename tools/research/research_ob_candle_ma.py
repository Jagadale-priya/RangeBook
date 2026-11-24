"""Order-block scalp: candle shape and moving-average filters.

The base trade is unchanged: 15-minute block, two 1-minute candles inside it,
stop at those candles, target at the nearest swing. Each row is tagged with
the candle shape and the 10, 15 and 20 moving averages known at that close.
A moving-average-only book, with no order block, is scored the same way.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research_ob_scalp_20d import _bars_15, _load, _order_blocks, _pivot_target, _walk

OUT = Path(r"c:\Users\Priyanka\Agent\prod_live\reports\1y\OB_CANDLE_MA.json")


def _ma(close: np.ndarray, length: int) -> np.ndarray:
    n = len(close)
    out = np.full(n, np.nan)
    if n < length:
        return out
    csum = np.cumsum(close)
    out[length - 1] = csum[length - 1] / length
    if n > length:
        out[length:] = (csum[length:] - csum[:-length]) / length
    return out


def _shape(open_, high, low, close, i, side) -> dict:
    def rng(k):
        return max(float(high[k] - low[k]), 0.05)

    body = abs(float(close[i] - open_[i])) / rng(i)
    # 1 means the close finished at the trade extreme.
    if side < 0:
        strong = (float(high[i] - close[i])) / rng(i)
        wick = (float(high[i - 1] - max(open_[i - 1], close[i - 1]))) / rng(i - 1)
        stair = high[i] < high[i - 1] and low[i] < low[i - 1]
        engulf = open_[i] >= open_[i - 1] and close[i] <= close[i - 1]
    else:
        strong = (float(close[i] - low[i])) / rng(i)
        wick = (float(min(open_[i - 1], close[i - 1]) - low[i - 1])) / rng(i - 1)
        stair = high[i] > high[i - 1] and low[i] > low[i - 1]
        engulf = open_[i] <= open_[i - 1] and close[i] >= close[i - 1]
    inside = high[i] <= high[i - 1] and low[i] >= low[i - 1]
    return {
        "strong_close": strong <= 0.33,
        "reject_wick": wick >= 0.45,
        "stair": bool(stair),
        "engulf": bool(engulf),
        "inside": bool(inside),
        "wide_body": body >= 0.55,
    }


def _ma_flags(close, mas, i, side) -> dict:
    flags = {}
    for length, ma in mas.items():
        if i < 5 or np.isnan(ma[i]) or np.isnan(ma[i - 5]):
            flags[f"ma{length}_side"] = False
            flags[f"ma{length}_both"] = False
            flags[f"ma{length}_slope"] = False
            continue
        side_ok = (float(close[i]) - float(ma[i])) * side > 0
        both = side_ok and (float(close[i - 1]) - float(ma[i - 1])) * side > 0
        slope = (float(ma[i]) - float(ma[i - 5])) * side > 0
        flags[f"ma{length}_side"] = bool(side_ok)
        flags[f"ma{length}_both"] = bool(both)
        flags[f"ma{length}_slope"] = bool(slope)
    return flags


def _collect(n_score: int) -> tuple[list[dict], list[dict]]:
    df = _load()
    days = list(dict.fromkeys(df["day"].tolist()))
    score_days = days[-n_score:]
    context = set(days[-(n_score + 3) :])
    df = df[df["day"].isin(context)].copy()
    blocks = _order_blocks(_bars_15(df))
    ob_rows = []
    ma_rows = []
    for day in score_days:
        g = df[df["day"] == day].reset_index(drop=True)
        high = g["High"].to_numpy(float)
        low = g["Low"].to_numpy(float)
        open_ = g["Open"].to_numpy(float)
        close = g["Close"].to_numpy(float)
        ts = list(g["date"])
        mas = {10: _ma(close, 10), 15: _ma(close, 15), 20: _ma(close, 20)}
        alive = [
            b
            for b in blocks
            if (not b["used"]) and (not b["dead"]) and b["day"] <= day and b["ready"] <= ts[-1]
        ]
        for i in range(16, len(g) - 1):
            now = ts[i]
            for b in alive:
                if b["used"] or b["dead"] or b["ready"] > now:
                    continue
                if b["side"] < 0 and close[i] > b["zhi"]:
                    b["dead"] = True
                elif b["side"] > 0 and close[i] < b["zlo"]:
                    b["dead"] = True
            bear2 = close[i] < open_[i] and close[i - 1] < open_[i - 1]
            bull2 = close[i] > open_[i] and close[i - 1] > open_[i - 1]
            if not bear2 and not bull2:
                continue
            side = -1 if bear2 else 1
            entry = float(close[i])
            shape = _shape(open_, high, low, close, i, side)
            maflags = _ma_flags(close, mas, i, side)
            # moving average only: three closes on the new side of the 15-average
            ma = mas[15]
            if (
                i >= 18
                and not np.isnan(ma[i])
                and (close[i] > ma[i]) == (close[i - 1] > ma[i - 1]) == (close[i - 2] > ma[i - 2])
                and (close[i - 2] > ma[i - 2]) != (close[i - 3] > ma[i - 3])
                and ((side > 0 and close[i] > ma[i]) or (side < 0 and close[i] < ma[i]))
            ):
                stop = float(np.max(high[i - 2 : i + 1])) if side < 0 else float(np.min(low[i - 2 : i + 1]))
                target = _pivot_target(high, low, i, side)
                risk = (stop - entry) if side < 0 else (entry - stop)
                if target is not None and risk > 0.25:
                    reward = (entry - target) if side < 0 else (target - entry)
                    if reward > 0.25:
                        result = _walk(high, low, i, side, stop, float(target))
                        points = reward if result == "win" else (-risk if result == "loss" else 0.0)
                        ma_rows.append({"result": result, "points": points, "rr": reward / risk, **shape, **maflags})
            for b in alive:
                if b["used"] or b["dead"] or b["side"] != side or b["ready"] > now:
                    continue
                if not (b["zlo"] <= entry <= b["zhi"]):
                    continue
                if not (low[i] <= b["zhi"] and high[i] >= b["zlo"] and low[i - 1] <= b["zhi"] and high[i - 1] >= b["zlo"]):
                    continue
                stop = float(max(high[i - 1], high[i])) if side < 0 else float(min(low[i - 1], low[i]))
                target = _pivot_target(high, low, i, side)
                risk = (stop - entry) if side < 0 else (entry - stop)
                if target is None or risk <= 0.25:
                    continue
                reward = (entry - target) if side < 0 else (target - entry)
                if reward <= 0.25:
                    continue
                result = _walk(high, low, i, side, stop, target)
                points = reward if result == "win" else (-risk if result == "loss" else 0.0)
                b["used"] = True
                ob_rows.append(
                    {
                        "result": result,
                        "points": points,
                        "rr": reward / risk,
                        **shape,
                        **maflags,
                    }
                )
                break
    return ob_rows, ma_rows


def _pack(rows: list[dict]) -> dict:
    done = [t for t in rows if t["result"] in ("win", "loss")]
    w = sum(t["result"] == "win" for t in done)
    d = len(done)
    pts = round(sum(t["points"] for t in done), 2)
    return {
        "n": d,
        "win": w,
        "loss": d - w,
        "hit": None if d == 0 else round(100.0 * w / d, 2),
        "points": pts,
    }


def main() -> None:
    rules = {
        "base_ob": lambda t: True,
        "stair": lambda t: t["stair"],
        "engulf": lambda t: t["engulf"],
        "strong_close": lambda t: t["strong_close"],
        "reject_wick": lambda t: t["reject_wick"],
        "wide_body": lambda t: t["wide_body"],
        "inside": lambda t: t["inside"],
        "ma15_side": lambda t: t["ma15_side"],
        "ma15_slope": lambda t: t["ma15_slope"],
        "ma15_side_slope": lambda t: t["ma15_side"] and t["ma15_slope"],
        "ma10_side": lambda t: t["ma10_side"],
        "ma20_side": lambda t: t["ma20_side"],
        "stair_ma15": lambda t: t["stair"] and t["ma15_side"] and t["ma15_slope"],
        "engulf_ma15": lambda t: t["engulf"] and t["ma15_side"],
        "strong_ma15": lambda t: t["strong_close"] and t["ma15_side"],
    }
    report = {}
    for n, label in ((20, "d20"), (120, "d120")):
        ob, ma = _collect(n)
        print(label, "ob", len(ob), "ma_only_first", len(ma), flush=True)
        block = {"ob": {}, "ma_only": _pack(ma)}
        ranked = []
        for name, fn in rules.items():
            part = [t for t in ob if fn(t)]
            block["ob"][name] = _pack(part)
            hit = block["ob"][name]["hit"]
            if hit is not None and block["ob"][name]["n"] >= (12 if n == 20 else 40):
                ranked.append((hit, block["ob"][name]["n"], block["ob"][name]["points"], name))
        ranked.sort(key=lambda x: (-x[0], -x[1]))
        block["rank"] = [{"rule": a, "hit": b, "n": c, "points": d} for b, c, d, a in ranked]
        # fix rank tuple order
        block["rank"] = [{"rule": name, "hit": hit, "n": n_, "points": pts} for hit, n_, pts, name in ranked]
        report[label] = block
        print(label, "base", block["ob"]["base_ob"], "ma_only", block["ma_only"])
        for row in block["rank"][:8]:
            print(" ", row)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
