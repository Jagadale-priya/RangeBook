"""Performance of frozen MORNING_CTX_V1 over the last ~3 years (NIFTY + stocks).

Does not re-fit. Reports holdout metrics for the held recipes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "legacy"))

import morning_session_context as msc  # noqa: E402

NIFTY_PATH = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_daily_nse.csv"
BANK_PATH = ROOT / "stock_signal_data" / "cache" / "IDX_NSEBANK.csv"
CACHE = ROOT / "stock_signal_data" / "cache"
OUT_JSON = ROOT / "prod_live" / "reports" / "1y" / "MORNING_CONTEXT_3Y_PERF.json"
OUT_MD = ROOT / "prod_live" / "reports" / "1y" / "MORNING_CONTEXT_3Y_PERF.md"
STOCKS = [
    "RELIANCE", "HDFCBANK", "INFY", "TCS", "SBIN", "ICICIBANK",
    "BAJFINANCE", "BHARTIARTL", "AXISBANK", "ITC",
]
SESSIONS_3Y = 756  # ~3 trading years


def load_ohlc(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], utc=False).dt.tz_localize(None).dt.normalize()
    for c in ("Open", "High", "Low", "Close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["Open", "High", "Low", "Close"]).sort_values("Date").reset_index(drop=True)


def eval_symbol(name: str, df: pd.DataFrame, n: int = SESSIONS_3Y) -> Dict[str, Any]:
    if len(df) < n + 80:
        n = max(100, len(df) - 80)
    work = df.tail(n + 80).reset_index(drop=True)
    h, l, c, o = work["High"], work["Low"], work["Close"], work["Open"]
    atr = msc.wilder_atr(h, l, c, 14)
    prev_c = c.shift(1)
    atr_prev = atr.shift(1)
    width = np.maximum(atr_prev * msc.ATR_MULT, prev_c * msc.FLOOR_PCT)
    half = width / 2.0

    # open-locked (+ gap asymmetric)
    hi = o + half
    lo = o - half
    gap = o - prev_c
    big = (gap.abs() / prev_c) >= 0.0035
    extra = np.minimum(gap.abs(), width * 0.35)
    hi = np.where(big & (gap > 0), hi + extra, hi)
    lo = np.where(big & (gap < 0), lo - extra, lo)
    inside_open = (l >= lo) & (h <= hi)

    # premarket provisional
    hi_p = prev_c + half
    lo_p = prev_c - half
    inside_pre = (l >= lo_p) & (h <= hi_p)

    use = inside_open.notna() & width.notna() & (width > 0) & prev_c.notna()
    idx = work.index[use][-n:]
    dates = work.loc[idx, "Date"]

    gap_pct = (o - prev_c) / prev_c * 100
    actual_gap = np.where(gap_pct > msc.GAP_TH_PCT, "GAP_UP", np.where(gap_pct < -msc.GAP_TH_PCT, "GAP_DOWN", "NATURAL"))
    nat_hit = pd.Series(actual_gap, index=work.index).loc[idx] == "NATURAL"

    atr_pct = atr_prev / prev_c * 100
    q33 = atr_pct.expanding(60).quantile(0.33)
    q66 = atr_pct.expanding(60).quantile(0.66)
    vol_pred = np.where(atr_pct >= q66, "HIGH", np.where(atr_pct <= q33, "LOW", "NORMAL"))
    realized = (h - l) / prev_c * 100
    rq33 = realized.expanding(60).quantile(0.33)
    rq66 = realized.expanding(60).quantile(0.66)
    vol_act = np.where(realized >= rq66, "HIGH", np.where(realized <= rq33, "LOW", "NORMAL"))
    vol_hit = (pd.Series(vol_pred, index=work.index) == pd.Series(vol_act, index=work.index)).loc[idx]

    vp = pd.Series(vol_pred, index=work.index).loc[idx]
    va = pd.Series(vol_act, index=work.index).loc[idx]
    high_n = int((va == "HIGH").sum())
    # Frozen guidance: HIGH pred -> SPREAD (good on high days); LOW pred -> INDEX_FUT (bad if day is HIGH)
    spread_ok = int(((va == "HIGH") & (vp == "HIGH")).sum())
    fut_wrong = int(((va == "HIGH") & (vp == "LOW")).sum())

    close_up = (c > prev_c).loc[idx]
    wp = (width / prev_c).loc[idx]
    ins = inside_open.loc[idx]
    insp = inside_pre.loc[idx]

    by_year: List[Dict[str, Any]] = []
    for y, g in dates.groupby(dates.dt.year):
        ii = g.index
        by_year.append({
            "year": int(y),
            "days": int(len(ii)),
            "open_inside_pct": round(float(ins.loc[ii].mean()), 4),
            "pre_inside_pct": round(float(insp.loc[ii].mean()), 4),
            "median_width_pct": round(float(wp.loc[ii].median()), 4),
            "gap_natural_acc": round(float(nat_hit.loc[ii].mean()), 4),
            "vol_hit": round(float(vol_hit.loc[ii].mean()), 4),
            "close_up_rate": round(float(close_up.loc[ii].mean()), 4),
        })

    return {
        "symbol": name,
        "window_start": str(dates.iloc[0].date()),
        "window_end": str(dates.iloc[-1].date()),
        "days": int(len(idx)),
        "range_open_inside_pct": round(float(ins.mean()), 4),
        "range_pre_inside_pct": round(float(insp.mean()), 4),
        "median_width_pct": round(float(wp.median()), 4),
        "gap_always_natural_acc": round(float(nat_hit.mean()), 4),
        "close_up_base_rate": round(float(close_up.mean()), 4),
        "vol_tercile_hit": round(float(vol_hit.mean()), 4),
        "high_vol_days": high_n,
        "pred_high_on_realized_high_pct": round(spread_ok / high_n, 4) if high_n else None,
        "pred_low_fut_on_realized_high_pct": round(fut_wrong / high_n, 4) if high_n else None,
        "bias_note": "NEUTRAL_DEFAULT — no directional accuracy claimed",
        "by_year": by_year,
    }


def to_md(payload: Dict[str, Any]) -> str:
    n = payload["symbols"]["NIFTY"]
    lines = [
        "# MORNING_CTX_V1 — 3y performance (frozen, no re-fit)",
        "",
        f"**Window (NIFTY):** `{n['window_start']}` → `{n['window_end']}` · **{n['days']}** sessions",
        f"**Generated:** `{payload['generated_at']}`",
        "",
        "Recipes unchanged from HELD `MORNING_CTX_V1`. No BUY/SELL calls.",
        "",
        "## NIFTY summary",
        "",
        f"| Metric | 3y |",
        f"|---|---:|",
        f"| Open-locked range inside | **{n['range_open_inside_pct']:.1%}** |",
        f"| Premarket range inside | {n['range_pre_inside_pct']:.1%} |",
        f"| Median width | {n['median_width_pct']:.2%} |",
        f"| Gap = always NATURAL hit | {n['gap_always_natural_acc']:.1%} |",
        f"| Vol tercile hit | {n['vol_tercile_hit']:.1%} |",
        f"| Close-up base rate (why bias=NEUTRAL) | {n['close_up_base_rate']:.1%} |",
        f"| On HIGH-vol days, pred also HIGH (→SPREAD) | {n['pred_high_on_realized_high_pct']} |",
        f"| On HIGH-vol days, pred LOW (would hint FUT) | {n['pred_low_fut_on_realized_high_pct']} |",
        "",
        "### NIFTY by year",
        "",
        "| Year | Days | Open inside | Pre inside | Width | Gap NATURAL | Vol hit |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for y in n["by_year"]:
        lines.append(
            f"| {y['year']} | {y['days']} | {y['open_inside_pct']:.1%} | {y['pre_inside_pct']:.1%} | "
            f"{y['median_width_pct']:.2%} | {y['gap_natural_acc']:.1%} | {y['vol_hit']:.1%} |"
        )
    lines += ["", "## Other symbols (3y)", "", "| Symbol | Days | Open inside | Pre | Width | Gap NATURAL | Vol |", "|---|---:|---:|---:|---:|---:|---:|"]
    for sym, block in payload["symbols"].items():
        if sym == "NIFTY" or block.get("error"):
            continue
        lines.append(
            f"| {sym} | {block['days']} | {block['range_open_inside_pct']:.1%} | "
            f"{block['range_pre_inside_pct']:.1%} | {block['median_width_pct']:.2%} | "
            f"{block['gap_always_natural_acc']:.1%} | {block['vol_tercile_hit']:.1%} |"
        )
    lines += [
        "",
        "## Read",
        "",
        "- Open-locked box is the useful morning-after-9:15 range (~50%+ inside on NIFTY).",
        "- Premarket box is provisional and much weaker — expected.",
        "- Bias stays NEUTRAL: close-up rate ~50%, no edge to claim.",
        "- Chain style still leans SPREAD when vol pred is HIGH; few HIGH days wrongly get LOW/FUT hint.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    payload: Dict[str, Any] = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "logic_tag": msc.LOGIC_TAG,
        "sessions_target": SESSIONS_3Y,
        "symbols": {},
    }
    nifty = load_ohlc(NIFTY_PATH)
    payload["symbols"]["NIFTY"] = eval_symbol("NIFTY", nifty)

    if BANK_PATH.is_file():
        payload["symbols"]["BANKNIFTY"] = eval_symbol("BANKNIFTY", load_ohlc(BANK_PATH))

    for sym in STOCKS:
        path = CACHE / f"{sym}_NS.csv"
        if not path.is_file():
            payload["symbols"][sym] = {"symbol": sym, "error": "missing"}
            continue
        payload["symbols"][sym] = eval_symbol(sym, load_ohlc(path))

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    OUT_MD.write_text(to_md(payload), encoding="utf-8")
    n = payload["symbols"]["NIFTY"]
    print(json.dumps({
        "wrote": str(OUT_MD),
        "nifty_3y": {
            "window": f"{n['window_start']} -> {n['window_end']}",
            "days": n["days"],
            "open_inside": n["range_open_inside_pct"],
            "pre_inside": n["range_pre_inside_pct"],
            "width": n["median_width_pct"],
            "gap_natural": n["gap_always_natural_acc"],
            "vol_hit": n["vol_tercile_hit"],
            "by_year": n["by_year"],
        },
    }, indent=2))


if __name__ == "__main__":
    main()
