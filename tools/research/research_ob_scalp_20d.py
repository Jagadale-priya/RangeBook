"""Last 20 Nifty sessions: 15-minute order block, then a 1-minute scalp.

Bearish block: a 15-minute bar closes down and under the prior four lows.
The zone is the last up candle before that bar. Bullish block is the mirror.
The zone is tradable only after that 15-minute bar has closed, and only while
price has not closed through it.

Entry: price is inside the zone and two 1-minute candles close in the trade
direction. Stop is the high (short) or low (long) of that rejection. Target is
the nearest confirmed 1-minute swing beyond the entry. One trade per block.

Same bar touching stop and target counts as a loss.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"c:\Users\Priyanka\Agent")
CSV = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_1m_kite.csv"
OUT = ROOT / "prod_live" / "reports" / "1y" / "OB_SCALP_20D.json"


def _load() -> pd.DataFrame:
    df = pd.read_csv(CSV, parse_dates=["date"])
    df = df.sort_values("date")
    ts = df["date"]
    mins = ts.dt.hour * 60 + ts.dt.minute
    df = df.loc[(mins >= 9 * 60 + 15) & (mins <= 15 * 60 + 29)].copy()
    df["day"] = ts.dt.tz_convert("Asia/Kolkata").dt.strftime("%Y-%m-%d")
    return df.reset_index(drop=True)


def _bars_15(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["bucket"] = x["date"].dt.floor("15min")
    g = x.groupby("bucket", sort=True)
    out = g.agg(
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
        day=("day", "first"),
    )
    out = out.reset_index().rename(columns={"bucket": "start"})
    out["ready"] = out["start"] + pd.Timedelta(minutes=15)
    return out


def _order_blocks(b15: pd.DataFrame) -> list[dict]:
    high = b15["High"].to_numpy(float)
    low = b15["Low"].to_numpy(float)
    open_ = b15["Open"].to_numpy(float)
    close = b15["Close"].to_numpy(float)
    blocks = []
    for i in range(4, len(b15)):
        if close[i] < open_[i] and low[i] < float(np.min(low[i - 4 : i])):
            src = next((j for j in range(i - 1, i - 5, -1) if close[j] > open_[j]), i - 1)
            blocks.append(_zone(-1, low, high, src, b15, i))
        if close[i] > open_[i] and high[i] > float(np.max(high[i - 4 : i])):
            src = next((j for j in range(i - 1, i - 5, -1) if close[j] < open_[j]), i - 1)
            blocks.append(_zone(1, low, high, src, b15, i))
    return blocks


def _zone(side, low, high, src, b15, i) -> dict:
    return {
        "side": side,
        "zlo": float(low[src]),
        "zhi": float(high[src]),
        "ready": b15["ready"].iloc[i],
        "born": str(b15["start"].iloc[i]),
        "day": str(b15["day"].iloc[i]),
        "used": False,
        "dead": False,
    }


def _pivot_target(high, low, i, side) -> float | None:
    """Nearest confirmed swing beyond the entry. A swing needs a bar on each side."""
    entry_level = None
    for j in range(i - 2, max(1, i - 31), -1):
        if side < 0 and low[j] < low[j - 1] and low[j] < low[j + 1] and low[j] < low[i]:
            return float(low[j])
        if side > 0 and high[j] > high[j - 1] and high[j] > high[j + 1] and high[j] > high[i]:
            return float(high[j])
    return entry_level


def _walk(high, low, i, side, stop, target) -> str:
    for j in range(i + 1, len(high)):
        hi = float(high[j])
        lo = float(low[j])
        hit_sl = hi >= stop if side < 0 else lo <= stop
        hit_tp = lo <= target if side < 0 else hi >= target
        if hit_sl:
            return "loss"
        if hit_tp:
            return "win"
    return "open"


def _pack(rows: list[dict]) -> dict:
    w = sum(t["result"] == "win" for t in rows)
    l = sum(t["result"] == "loss" for t in rows)
    o = sum(t["result"] == "open" for t in rows)
    d = w + l
    pts = round(sum(t["points"] for t in rows if t["result"] != "open"), 2)
    return {
        "n": len(rows),
        "win": w,
        "loss": l,
        "open": o,
        "hit": None if d == 0 else round(100.0 * w / d, 2),
        "points": pts,
    }


def main() -> None:
    df = _load()
    days = list(dict.fromkeys(df["day"].tolist()))
    score_days = days[-20:]
    context_days = set(days[-23:])
    df = df[df["day"].isin(context_days)].copy()
    blocks = _order_blocks(_bars_15(df))
    trades = []
    for day in score_days:
        g = df[df["day"] == day].reset_index(drop=True)
        high = g["High"].to_numpy(float)
        low = g["Low"].to_numpy(float)
        open_ = g["Open"].to_numpy(float)
        close = g["Close"].to_numpy(float)
        ts = list(g["date"])
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
                    continue
                if b["side"] > 0 and close[i] < b["zlo"]:
                    b["dead"] = True
                    continue
            bear2 = close[i] < open_[i] and close[i - 1] < open_[i - 1]
            bull2 = close[i] > open_[i] and close[i - 1] > open_[i - 1]
            if not bear2 and not bull2:
                continue
            side = -1 if bear2 else 1
            entry = float(close[i])
            for b in alive:
                if b["used"] or b["dead"] or b["side"] != side or b["ready"] > now:
                    continue
                if not (b["zlo"] <= entry <= b["zhi"]):
                    continue
                if not (low[i] <= b["zhi"] and high[i] >= b["zlo"]):
                    continue
                if not (low[i - 1] <= b["zhi"] and high[i - 1] >= b["zlo"]):
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
                points = round(reward if result == "win" else (-risk if result == "loss" else 0.0), 2)
                b["used"] = True
                trades.append(
                    {
                        "day": day,
                        "time": str(now.tz_convert("Asia/Kolkata"))[11:16],
                        "side": "SELL" if side < 0 else "BUY",
                        "entry": round(entry, 2),
                        "stop": round(stop, 2),
                        "target": round(target, 2),
                        "risk": round(risk, 2),
                        "reward": round(reward, 2),
                        "rr": round(reward / risk, 2),
                        "points": points,
                        "zone": [round(b["zlo"], 2), round(b["zhi"], 2)],
                        "block_born": b["born"][5:16],
                        "result": result,
                    }
                )
                break
    near = [t for t in trades if t["rr"] < 1.25]
    mid = [t for t in trades if 1.25 <= t["rr"] < 2]
    twos = [t for t in trades if 2 <= t["rr"] < 3]
    far = [t for t in trades if t["rr"] >= 3]
    report = {
        "sessions": score_days,
        "trades": trades,
        "all": _pack(trades),
        "sell": _pack([t for t in trades if t["side"] == "SELL"]),
        "buy": _pack([t for t in trades if t["side"] == "BUY"]),
        "rr_under_1.25": _pack(near),
        "rr_1.25_to_2": _pack(mid),
        "rr_2_to_3": _pack(twos),
        "rr_over_3": _pack(far),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("sessions", score_days[0], "->", score_days[-1], "trades", len(trades))
    for name in ("all", "sell", "buy", "rr_under_1.25", "rr_1.25_to_2", "rr_2_to_3", "rr_over_3"):
        print(name, report[name])
    for t in trades:
        print(
            f"{t['day']} {t['time']} {t['side']:4} e {t['entry']} sl {t['stop']} tg {t['target']} "
            f"rr {t['rr']} {t['points']:+} {t['result']} zone {t['zone']} born {t['block_born']}"
        )


if __name__ == "__main__":
    main()
