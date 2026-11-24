"""Diagnose residual noise on 1m clean tickets using path MAE / both-sides."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"c:\Users\Priyanka\Agent")
CACHE = ROOT / "stock_signal_data/fno_validate/research/_cache_nifty_1m_2021_2025.parquet"
TICKETS = ROOT / "stock_signal_data/fno_validate/research/nifty_1m_dual_clean_research/clean_tickets.json"
FREEZE = "2024-09-10"
RISK = 30.0

bars = pd.read_parquet(CACHE)
if not isinstance(bars.index, pd.DatetimeIndex):
    if "date" in bars.columns:
        bars = bars.set_index("date")
    bars.index = pd.to_datetime(bars.index)
if bars.index.tz is None:
    bars.index = bars.index.tz_localize("Asia/Kolkata")
else:
    bars.index = bars.index.tz_convert("Asia/Kolkata")
rename = {c: str(c).title() for c in bars.columns}
bars = bars.rename(columns=rename)
idx = {ts: i for i, ts in enumerate(bars.index)}


def day(ts):
    return pd.Timestamp(ts).tz_convert("Asia/Kolkata").strftime("%Y-%m-%d")


def hm(ts):
    return pd.Timestamp(ts).tz_convert("Asia/Kolkata").strftime("%H:%M")


rows = json.loads(TICKETS.read_text(encoding="utf-8"))
# enrich
day_key = pd.Index([day(ts) for ts in bars.index])
groups = bars.groupby(day_key, sort=True)

enriched = []
for r in rows:
    d = r["day"]
    ts_guess = None
    # find bar by day+hm
    sess = groups.get_group(d) if d in groups.groups else None
    if sess is None or sess.empty:
        continue
    target_hm = r["hm"]
    match = [ts for ts in sess.index if hm(ts) == target_hm]
    if not match:
        continue
    ts = match[0]
    i = idx[ts]
    entry = float(r["entry"])
    side = r["decision"]
    sl = float(r["stop_loss"])
    t1 = float(r["target_1"])
    # MAE until resolution
    mae = 0.0
    mfe = 0.0
    bars_to_res = None
    for j in range(i + 1, len(bars)):
        if day(bars.index[j]) != d:
            break
        hi = float(bars["High"].iloc[j])
        lo = float(bars["Low"].iloc[j])
        if side == "BUY":
            mae = max(mae, entry - lo)
            mfe = max(mfe, hi - entry)
            if lo <= sl or hi >= t1:
                bars_to_res = j - i
                break
        else:
            mae = max(mae, hi - entry)
            mfe = max(mfe, entry - lo)
            if hi >= sl or lo <= t1:
                bars_to_res = j - i
                break
    # both sides OR break before entry?
    or_hi = float(sess["High"].iloc[:15].max()) if len(sess) >= 15 else float(sess["High"].iloc[: min(15, len(sess))].max())
    or_lo = float(sess["Low"].iloc[:15].min()) if len(sess) >= 15 else float(sess["Low"].iloc[: min(15, len(sess))].min())
    up = dn = False
    for ts2 in sess.index:
        if hm(ts2) > target_hm:
            break
        c = float(sess.loc[ts2, "Close"])
        if c > or_hi:
            up = True
        if c < or_lo:
            dn = True
    both = up and dn
    body = float(sess.loc[ts, "Close"] - sess.loc[ts, "Open"])
    body_ok = (side == "BUY" and body > 0) or (side == "SELL" and body < 0)
    enriched.append(
        {
            **r,
            "mae": round(mae, 2),
            "mfe": round(mfe, 2),
            "mae_frac": round(mae / RISK, 3),
            "mfe_frac": round(mfe / RISK, 3),
            "bars_to_res": bars_to_res,
            "both_sides": both,
            "body_ok": body_ok,
            "after_10": int(r["mins_entry"]) >= 10 * 60,
            "or_ext_abs": abs(float(r.get("or_ext") or 0)),
        }
    )

oos = [r for r in enriched if r["day"] > FREEZE]


def bucket(name, pred):
    sub = [r for r in oos if pred(r)]
    if not sub:
        print(name, "n=0")
        return
    hit = 100 * sum(1 for r in sub if r["win"]) / len(sub)
    print(f"{name}: n={len(sub)} hit={hit:.1f}%")


print("OOS base n", len(oos), "hit", round(100 * sum(1 for r in oos if r["win"]) / len(oos), 1))
bucket("first_break", lambda r: r.get("first_break"))
bucket("NOT both_sides", lambda r: not r["both_sides"])
bucket("FB + not both", lambda r: r.get("first_break") and not r["both_sides"])
bucket("body_ok", lambda r: r["body_ok"])
bucket("FB+body", lambda r: r.get("first_break") and r["body_ok"])
bucket("after_10", lambda r: r["after_10"])
bucket("FB+after10", lambda r: r.get("first_break") and r["after_10"])
bucket("or_ext<=0.25", lambda r: r["or_ext_abs"] <= 0.25)
bucket("or_ext<=0.15", lambda r: r["or_ext_abs"] <= 0.15)
bucket("mae_frac<=0.5", lambda r: r["mae_frac"] <= 0.5)  # in-sample path leak if used as train filter carefully
bucket("mae_frac<=0.35", lambda r: r["mae_frac"] <= 0.35)
bucket("FB+notBoth+ext<=0.25", lambda r: r.get("first_break") and not r["both_sides"] and r["or_ext_abs"] <= 0.25)
bucket("FB+notBoth+ext<=0.15+body", lambda r: r.get("first_break") and not r["both_sides"] and r["or_ext_abs"] <= 0.15 and r["body_ok"])
bucket("FB+notBoth+after10+ext<=0.20", lambda r: r.get("first_break") and not r["both_sides"] and r["after_10"] and r["or_ext_abs"] <= 0.20)
bucket("FB+notBoth+after10+body+ext<=0.20", lambda r: r.get("first_break") and not r["both_sides"] and r["after_10"] and r["body_ok"] and r["or_ext_abs"] <= 0.20)

# MAE distributions
for lab, sub in [("win", [r for r in oos if r["win"]]), ("loss", [r for r in oos if not r["win"]])]:
    maes = [r["mae_frac"] for r in sub]
    print(lab, "mae_frac p50", round(float(np.median(maes)), 3), "p75", round(float(np.percentile(maes, 75)), 3), "mean", round(float(np.mean(maes)), 3))
