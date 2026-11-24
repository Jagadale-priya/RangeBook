"""Pattern exits for the 1-minute 3-close MA cross.

No fixed point stop or target. Each trade takes its stop and target from that cross.
Select window is every session before 2025-11-16. The last year is reported after.
Same bar touching stop and target counts as a loss. Still open at 15:29 is not a win.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"c:\Users\Priyanka\Agent")
CSV = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_1m_kite.csv"
OUT = ROOT / "prod_live" / "reports" / "1y" / "MA3_1M_PATTERN.json"
SELECT_END = np.datetime64("2025-11-16")
LENGTHS = (10, 15, 20, 30)
IMPULSE = 40


def _load() -> pd.DataFrame:
    df = pd.read_csv(CSV, parse_dates=["date"])
    df = df.sort_values("date")
    ts = df["date"]
    mins = ts.dt.hour * 60 + ts.dt.minute
    df = df.loc[(mins >= 9 * 60 + 15) & (mins <= 15 * 60 + 29)].copy()
    df["day"] = ts.dt.tz_convert("Asia/Kolkata").dt.strftime("%Y-%m-%d")
    return df


def _ma(close: np.ndarray, length: int) -> np.ndarray:
    n = len(close)
    ma = np.full(n, np.nan)
    if n < length:
        return ma
    csum = np.cumsum(close)
    ma[length - 1] = csum[length - 1] / length
    if n > length:
        ma[length:] = (csum[length:] - csum[:-length]) / length
    return ma


def _walk(high, low, i, side, stop, target) -> str:
    for j in range(i + 1, len(high)):
        hi = float(high[j])
        lo = float(low[j])
        if side > 0:
            hit_sl = lo <= stop
            hit_t1 = hi >= target
        else:
            hit_sl = hi >= stop
            hit_t1 = lo <= target
        if hit_sl:
            return "loss"
        if hit_t1:
            return "win"
    return "open"


def _mfe_before_stop(high, low, i, side, stop, risk) -> float:
    """Favorable points reached on bars that did not touch the pattern stop."""
    if risk <= 0:
        return 0.0
    mfe = 0.0
    for j in range(i + 1, len(high)):
        hi = float(high[j])
        lo = float(low[j])
        if side > 0:
            if lo <= stop:
                return mfe / risk
            mfe = max(mfe, hi - float(high[i]))  # placeholder, replaced below
        else:
            if hi >= stop:
                return mfe / risk
    return mfe / risk


def _session(close, high, low, length: int) -> list[dict]:
    n = len(close)
    ma = _ma(close, length)
    above = close > ma
    out = []
    if n < length + 8:
        return out
    for i in range(length + 3, n - 1):
        if np.isnan(ma[i]) or np.isnan(ma[i - 10]):
            continue
        up3 = bool(above[i] and above[i - 1] and above[i - 2])
        dn3 = bool((not above[i]) and (not above[i - 1]) and (not above[i - 2]))
        if not up3 and not dn3:
            continue
        if above[i - 2] == above[i - 3]:
            continue
        side = 1 if up3 else -1
        q = i - 3
        while q > 0 and bool(above[q]) != (side > 0):
            q -= 1
        had_prior = bool(above[q]) == (side > 0) and q < i - 3
        dip_start = int(q + 1) if had_prior else int(i - 2)
        if side > 0:
            stop = float(np.min(low[dip_start : i + 1]))
            box_lo = float(np.min(low[i - 2 : i + 1]))
            box_hi = float(np.max(high[i - 2 : i + 1]))
            left = max(0, dip_start - IMPULSE)
            impulse = float(np.max(high[left:dip_start])) if had_prior and dip_start > left else np.nan
        else:
            stop = float(np.max(high[dip_start : i + 1]))
            box_lo = float(np.min(low[i - 2 : i + 1]))
            box_hi = float(np.max(high[i - 2 : i + 1]))
            left = max(0, dip_start - IMPULSE)
            impulse = float(np.min(low[left:dip_start])) if had_prior and dip_start > left else np.nan
        entry = float(close[i])
        risk = (entry - stop) if side > 0 else (stop - entry)
        if risk <= 0.05:
            continue
        box_h = box_hi - box_lo
        if side > 0:
            box_tgt = box_hi + box_h
            swing_ok = (not np.isnan(impulse)) and impulse > entry
        else:
            box_tgt = box_lo - box_h
            swing_ok = (not np.isnan(impulse)) and impulse < entry
        reward = abs(float(impulse) - entry) if swing_ok else np.nan
        # flips in the 20 bars before the 3-candle run
        lo_i = max(1, i - 22)
        flips = int(np.sum(above[lo_i : i - 2] != above[lo_i - 1 : i - 3])) if i - 3 > lo_i else 0
        slope = float(ma[i] - ma[i - 10])
        ma_dist = (entry - float(ma[i])) * side
        out.append(
            {
                "i": i,
                "side": side,
                "entry": entry,
                "dip_bars": int(i - dip_start + 1),
                "ma_dist": float(ma_dist),
                "stop": stop,
                "risk": risk,
                "impulse": float(impulse) if swing_ok else None,
                "reward": float(reward) if swing_ok else None,
                "box_tgt": float(box_tgt),
                "box_h": float(box_h),
                "chop": flips,
                "slope": slope,
            }
        )
    return out


def _agg(flags: list[str]) -> dict:
    w = sum(x == "win" for x in flags)
    l = sum(x == "loss" for x in flags)
    o = sum(x == "open" for x in flags)
    d = w + l
    return {"n": len(flags), "win": w, "loss": l, "open": o, "hit": None if d == 0 else round(100.0 * w / d, 2)}


def main() -> None:
    df = _load()
    print("rows", len(df), "sessions", df["day"].nunique(), flush=True)
    books = {L: {"swing": [], "box": [], "flip": [], "pre_swing_rr": []} for L in LENGTHS}
    # store per-length rows for filters
    rows = []
    for day, g in df.groupby("day", sort=True):
        close = g["Close"].to_numpy(float)
        high = g["High"].to_numpy(float)
        low = g["Low"].to_numpy(float)
        pre = np.datetime64(day) < SELECT_END
        for length in LENGTHS:
            sigs = _session(close, high, low, length)
            for ai, a in enumerate(sigs):
                # flip exit: next opposite 3-close, else the session close
                exit_px = float(close[-1])
                for b in sigs[ai + 1 :]:
                    if b["side"] != a["side"]:
                        exit_px = b["entry"]
                        break
                pts = (exit_px - a["entry"]) * a["side"]
                flip = "win" if pts > 0 else "loss"
                swing = "skip"
                if a["impulse"] is not None and a["reward"] is not None and a["reward"] + 1e-9 >= a["risk"]:
                    swing = _walk(high, low, a["i"], a["side"], a["stop"], a["impulse"])
                box = "skip"
                if a["box_h"] > 0.05:
                    beyond = (a["side"] > 0 and a["box_tgt"] > a["entry"]) or (a["side"] < 0 and a["box_tgt"] < a["entry"])
                    if beyond:
                        box = _walk(high, low, a["i"], a["side"], a["stop"], a["box_tgt"])
                rows.append(
                    {
                        "day": day,
                        "pre": bool(pre),
                        "length": length,
                        "side": a["side"],
                        "risk": a["risk"],
                        "reward": a["reward"] if a["reward"] is not None else None,
                        "chop": a["chop"],
                        "slope": a["slope"],
                        "swing": swing,
                        "box": box,
                        "flip": flip,
                        "flip_pts": pts,
                    }
                )
        if len(rows) and len(rows) % 80000 < 500:
            print("rows", len(rows), day, flush=True)
    tix = pd.DataFrame(rows)
    print("signals", len(tix), flush=True)

    def take(frame, kind):
        if frame.empty:
            return _agg([])
        flags = [x for x in frame[kind].tolist() if x != "skip"]
        return _agg(flags)

    filters = {
        "pattern": lambda d: pd.Series(True, index=d.index),
        "room_ge_risk": lambda d: d["reward"].notna() & (d["reward"] >= d["risk"]),
        "room_1_5": lambda d: d["reward"].notna() & (d["reward"] >= 1.5 * d["risk"]),
        "slope_with": lambda d: ((d["side"] > 0) & (d["slope"] > 0)) | ((d["side"] < 0) & (d["slope"] < 0)),
        "chop_le2": lambda d: d["chop"] <= 2,
        "clean": lambda d: (d["chop"] <= 2)
        & (((d["side"] > 0) & (d["slope"] > 0)) | ((d["side"] < 0) & (d["slope"] < 0)))
        & d["reward"].notna()
        & (d["reward"] >= d["risk"]),
    }
    report = {"select_before": "2025-11-16", "impulse_bars": IMPULSE, "books": []}
    ranked = []
    for length in LENGTHS:
        base = tix[tix["length"] == length]
        for fname, fn in filters.items():
            part = base[fn(base)]
            for kind in ("swing", "box", "flip"):
                pre = take(part[part["pre"]], kind)
                post = take(part[~part["pre"]], kind)
                # flip points
                extra = {}
                if kind == "flip":
                    pre_pts = part[part["pre"]]["flip_pts"]
                    post_pts = part[~part["pre"]]["flip_pts"]
                    extra = {
                        "pre_median_pts": None if pre_pts.empty else round(float(pre_pts.median()), 2),
                        "test_median_pts": None if post_pts.empty else round(float(post_pts.median()), 2),
                    }
                row = {"length": length, "filter": fname, "exit": kind, "pre": pre, "test": post, **extra}
                report["books"].append(row)
                if kind == "swing" and pre["n"] >= 80 and pre["hit"] is not None:
                    ranked.append((pre["hit"], pre["n"], post.get("hit"), post["n"], row))
    ranked.sort(key=lambda x: (-x[0], -x[1]))
    report["best_swing_pre"] = [
        {"pre_hit": a, "pre_n": b, "test_hit": c, "test_n": d, "length": r["length"], "filter": r["filter"], "pre": r["pre"], "test": r["test"]}
        for a, b, c, d, r in ranked[:15]
    ]
    # risk / reward picture on clean MA15 swing trades, train only
    m15 = tix[(tix["length"] == 15) & (tix["pre"]) & tix["reward"].notna() & (tix["reward"] >= tix["risk"])]
    if len(m15):
        report["ma15_train_pattern_size"] = {
            "n": int(len(m15)),
            "median_risk_pts": round(float(m15["risk"].median()), 2),
            "median_target_pts": round(float(m15["reward"].median()), 2),
            "median_rr": round(float((m15["reward"] / m15["risk"]).median()), 2),
        }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", OUT)
    for item in report["best_swing_pre"][:8]:
        print(
            f"SWING L{item['length']} {item['filter']} pre {item['pre']['win']}/{item['pre']['win']+item['pre']['loss']}="
            f"{item['pre_hit']} n={item['pre_n']} open={item['pre']['open']} | "
            f"test {item['test']['win']}/{item['test']['win']+item['test']['loss']}={item['test_hit']} n={item['test_n']}"
        )
    for b in report["books"]:
        if b["length"] == 15 and b["filter"] in ("pattern", "room_ge_risk", "clean") and b["exit"] in ("swing", "box", "flip"):
            print(
                f"L15 {b['exit']:5} {b['filter']:12} pre {b['pre']['hit']} n={b['pre']['n']} | test {b['test']['hit']} n={b['test']['n']} {b.get('pre_median_pts','')} {b.get('test_median_pts','')}"
            )


if __name__ == "__main__":
    main()
