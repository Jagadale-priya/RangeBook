"""Explain R6/R2: calls, density, did we catch moves?"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
from _diag_scalp_pa_bos_choch_fvg import _norm_1m, to_15m  # noqa: E402
from _diag_scalp_pa_range_proven import LOOKBACK_CAL, N_SESSIONS, build_books  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_PA_RANGE_HOW_IT_WORKS.md"
REPORT_JSON = OUT / "NIFTY_1M_PA_RANGE_HOW_IT_WORKS.json"


def day_mfe_mae(t, h, l, c, day):
    i = int(t["full_i"])
    d = t["day"]
    side = t["side"]
    entry = float(t["entry"])
    js = [j for j in range(i + 1, len(c)) if day[j] == d]
    if not js:
        return 0.0, 0.0, 0.0, 0.0
    if side == "BUY":
        mfe = max(float(h[j]) - entry for j in js)
        mae = max(entry - float(l[j]) for j in js)
        rem_hi = float(np.max(h[js]))
        rem_lo = float(np.min(l[[i] + js]))
    else:
        mfe = max(entry - float(l[j]) for j in js)
        mae = max(float(h[j]) - entry for j in js)
        rem_hi = float(np.max(h[[i] + js]))
        rem_lo = float(np.min(l[js]))
    day_range = rem_hi - rem_lo
    share = (mfe / day_range * 100.0) if day_range > 1 else 0.0
    return mfe, mae, share, day_range


def main() -> int:
    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df1 = _norm_1m(raw)
    days_all = sorted({str(ts.date()) for ts in df1.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days = sorted(keep)
    n_days = len(days)
    df1 = df1[[str(ts.date()) in keep for ts in df1.index]]
    df15 = to_15m(df1)
    books = build_books(df1, df15)

    h = df1["High"].astype(float).values
    l = df1["Low"].astype(float).values
    c = df1["Close"].astype(float).values
    day = np.array([str(ts.date()) for ts in df1.index])

    focus = ["R6_break_htf_OR30", "R6_break_htf_OR15", "R2_break_OR30", "R2_break_OR15"]
    out = {"n_days": n_days, "day_lo": days[0], "day_hi": days[-1], "books": {}}

    for name in focus:
        tr = books.get(name, [])
        if not tr:
            continue
        wins = [t for t in tr if t["win"]]
        losses = [t for t in tr if not t["win"]]
        mfes, maes, shares, ranges = [], [], [], []
        catch15 = catch25 = catch40 = 0
        for t in tr:
            mfe, mae, share, dr = day_mfe_mae(t, h, l, c, day)
            mfes.append(mfe)
            maes.append(mae)
            shares.append(share)
            ranges.append(dr)
            if mfe >= 15:
                catch15 += 1
            if mfe >= 25:
                catch25 += 1
            if mfe >= 40:
                catch40 += 1
        # among wins: how big was remaining-day MFE
        win_mfe = []
        for t in wins:
            mfe, _, _, _ = day_mfe_mae(t, h, l, c, day)
            win_mfe.append(mfe)
        buy = sum(1 for t in tr if t["side"] == "BUY")
        days_traded = len({t["day"] for t in tr})
        morning = sum(1 for t in tr if t["hm"] < "11:00")
        mid = sum(1 for t in tr if "11:00" <= t["hm"] < "13:00")
        aft = sum(1 for t in tr if t["hm"] >= "13:00")
        # total expectancy pts
        pts = [float(t["pts"]) for t in tr]
        out["books"][name] = {
            "n": len(tr),
            "cpd": round(len(tr) / n_days, 2),
            "days_with_call": days_traded,
            "day_coverage_pct": round(100.0 * days_traded / n_days, 1),
            "hit_3R": round(100.0 * len(wins) / len(tr), 1),
            "buy_pct": round(100.0 * buy / len(tr), 1),
            "avg_risk": round(float(np.mean([t["risk"] for t in tr])), 1),
            "avg_win_pts": round(float(np.mean([t["pts"] for t in wins])), 1) if wins else None,
            "avg_loss_pts": round(float(np.mean([t["pts"] for t in losses])), 1) if losses else None,
            "sum_pts": round(float(np.sum(pts)), 1),
            "avg_pts": round(float(np.mean(pts)), 2),
            "avg_day_mfe_after_entry": round(float(np.mean(mfes)), 1),
            "med_day_mfe_after_entry": round(float(np.median(mfes)), 1),
            "avg_day_mae_after_entry": round(float(np.mean(maes)), 1),
            "pct_calls_mfe_ge15": round(100.0 * catch15 / len(tr), 1),
            "pct_calls_mfe_ge25": round(100.0 * catch25 / len(tr), 1),
            "pct_calls_mfe_ge40": round(100.0 * catch40 / len(tr), 1),
            "avg_share_of_remaining_day_range": round(float(np.mean(shares)), 1),
            "avg_win_day_mfe": round(float(np.mean(win_mfe)), 1) if win_mfe else None,
            "hm": {"before_11": morning, "11_to_13": mid, "after_13": aft},
            "sample_wins": wins[:6],
            "sample_losses": losses[:4],
        }

    best = out["books"]["R6_break_htf_OR30"]
    lines = [
        "# How OR break+retest works · calls · move catch",
        "",
        f"Window **{out['day_lo']} → {out['day_hi']}** ({n_days} sessions).",
        "",
        "## How it works (best book: `R6_break_htf_OR30`)",
        "",
        "```",
        "09:15–09:44  Build OR30 = high/low of first 30 one-minute bars",
        "             UP zone  = OR high ± 0.5×ATR14",
        "             DOWN zone = OR low  ± 0.5×ATR14",
        "",
        "Later         Price CLOSES beyond OR high (bull break) or OR low (bear break)",
        "              then EXTENDS away from the zone",
        "",
        "Entry         Price comes BACK and retests the broken edge zone",
        "              BUY retest of broken OR-high zone  (only if 15m bias = up)",
        "              SELL retest of broken OR-low zone (only if 15m bias = down)",
        "",
        "Risk          SL beyond far side of that zone",
        "Target        3× risk (3R) · max hold 90 minutes · max 1 call/day",
        "```",
        "",
        "We are **not** fading the open range. We trade the **break continuation** after a retest.",
        "",
        "## How many calls?",
        "",
        "| Book | Calls | /day | Days with a call | Hit @3R | Avg risk | Sum pts |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in focus:
        b = out["books"][name]
        lines.append(
            f"| `{name}` | **{b['n']}** | **{b['cpd']}** | "
            f"{b['days_with_call']} ({b['day_coverage_pct']}%) | {b['hit_3R']}% | "
            f"{b['avg_risk']} | {b['sum_pts']} |"
        )

    lines += [
        "",
        f"**Best book density:** ~**{best['cpd']} call/day** "
        f"(a call on **{best['day_coverage_pct']}%** of sessions — about **{best['days_with_call']}/{n_days}** days).",
        f"Timing mix (R6 OR30): before 11:00 **{best['hm']['before_11']}** · "
        f"11–13 **{best['hm']['11_to_13']}** · after 13:00 **{best['hm']['after_13']}**.",
        "",
        "## Did we catch moves?",
        "",
        "Measured as **remaining-day MFE** after entry (how far price ran in our direction that session), "
        "independent of whether 3R hit first.",
        "",
        "| Book | Avg MFE | Med MFE | Avg adverse | % calls MFE≥15 | % ≥25 | % ≥40 | Avg share of day range |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in focus:
        b = out["books"][name]
        lines.append(
            f"| `{name}` | {b['avg_day_mfe_after_entry']} | {b['med_day_mfe_after_entry']} | "
            f"{b['avg_day_mae_after_entry']} | {b['pct_calls_mfe_ge15']}% | "
            f"{b['pct_calls_mfe_ge25']}% | {b['pct_calls_mfe_ge40']}% | "
            f"{b['avg_share_of_remaining_day_range']}% |"
        )

    lines += [
        "",
        f"On **R6 OR30** specifically:",
        f"- **{best['hit_3R']}%** of calls hit **+3R** (avg win **{best['avg_win_pts']} pts**, avg loss **{best['avg_loss_pts']} pts**).",
        f"- After entry, price still ran **≥15 pts** our way on **{best['pct_calls_mfe_ge15']}%** of calls, "
        f"**≥25 pts** on **{best['pct_calls_mfe_ge25']}%**, **≥40 pts** on **{best['pct_calls_mfe_ge40']}%**.",
        f"- Average remaining-day favorable run ≈ **{best['avg_day_mfe_after_entry']} pts** "
        f"(median **{best['med_day_mfe_after_entry']}**); among 3R winners avg day MFE ≈ **{best['avg_win_day_mfe']} pts**.",
        f"- So yes: when it works it is sitting on a **real continuation move**, not a tiny scalp flicker. "
        f"When it fails, SL is ~**{abs(best['avg_loss_pts']) if best['avg_loss_pts'] else '?'} pts** (the zone width).",
        "",
        "### Sample wins (R6 OR30)",
        "",
        "| Day | HM | Side | Entry | Risk | Pts |",
        "|---|---|---|---:|---:|---:|",
    ]
    for t in best["sample_wins"]:
        lines.append(
            f"| {t['day']} | {t['hm']} | {t['side']} | {t['entry']} | {t['risk']} | {t['pts']} |"
        )
    lines += [
        "",
        "### Sample losses (R6 OR30)",
        "",
        "| Day | HM | Side | Entry | Risk | Pts |",
        "|---|---|---|---:|---:|---:|",
    ]
    for t in best["sample_losses"]:
        lines.append(
            f"| {t['day']} | {t['hm']} | {t['side']} | {t['entry']} | {t['risk']} | {t['pts']} |"
        )

    lines += [
        "",
        "## Plain answer",
        "",
        "1. **How:** wait for open-range **break**, then buy/sell the **retest** with trend (HTF).",
        f"2. **Calls:** ~**{best['cpd']}/day** (1 max) — about **{best['n']}** calls in {n_days} days.",
        f"3. **Catch moves:** yes on a large share — **{best['pct_calls_mfe_ge25']}%** saw ≥25pt continuation after entry; "
        f"**{best['hit_3R']}%** banked full 3R. Not every big day is caught (only days with a clean break+retest+HTF).",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    print(json.dumps(out["books"]["R6_break_htf_OR30"], indent=2, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
