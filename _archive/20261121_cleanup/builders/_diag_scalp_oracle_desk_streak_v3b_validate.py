"""RESEARCH ONLY — Validate v3 HIGH_75 gate (hit6 + desk + held + HTF + ATR_hi).

Checks:
  1) ATR threshold sweep (8..14)
  2) 3-fold walk-forward (not just mid-split)
  3) Coverage (days with signal / 120)
  4) Compare lean gate vs fat gate (desk optional?)
  5) Side split BUY/SELL

  python -u prod_live/tests/builders/_diag_scalp_oracle_desk_streak_v3b_validate.py
"""
from __future__ import annotations

import json
import sys
import time
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
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators  # noqa: E402
from _diag_scalp_ad_sr_entry_1m import add_ad_obv_proxy  # noqa: E402
from _diag_scalp_pa_bos_choch_fvg import (  # noqa: E402
    to_15m,
    structure_events,
    build_htf_bias,
    htf_bias_lookup,
)

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_1m as scalper  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ORACLE_DESK_STREAK_V3B_VALIDATE.md"
REPORT_JSON = OUT / "NIFTY_1M_ORACLE_DESK_STREAK_V3B_VALIDATE.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 120
LOOKBACK_CAL = 240
T15 = 15.0


def one_per_day(rows):
    byd = {}
    for r in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        if r["day"] not in byd:
            byd[r["day"]] = r
    return list(byd.values())


def prec(rows):
    if not rows:
        return None, 0
    return round(100.0 * sum(1 for r in rows if r["t15_win"]) / len(rows), 2), len(rows)


def color_side(o, c, i):
    if c[i] > o[i]:
        return "BUY"
    if c[i] < o[i]:
        return "SELL"
    return None


def streak_len_at(o, c, day, i, side):
    if side == "BUY" and not (c[i] > o[i]):
        return 0
    if side == "SELL" and not (c[i] < o[i]):
        return 0
    s = i
    while s - 1 >= 0 and day[s - 1] == day[i]:
        if side == "BUY" and c[s - 1] > o[s - 1]:
            s -= 1
        elif side == "SELL" and c[s - 1] < o[s - 1]:
            s -= 1
        else:
            break
    return i - s + 1


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("v3b validate: ATR sweep + 3-fold WF on hit6 gate", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    df = add_ad_obv_proxy(df)

    close = df["Close"].astype(float)
    df["ema9"] = close.ewm(span=9, adjust=False).mean()
    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()
    midb = close.rolling(20, min_periods=20).mean()
    std = close.rolling(20, min_periods=20).std(ddof=0)
    df["bb_mid"] = midb

    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    df = df[[str(ts.date()) in keep for ts in df.index]]

    df15 = to_15m(df)
    bias15 = build_htf_bias(df15, structure_events(df15))

    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    atr = df["atr14"].astype(float).values
    vwap = df["vwap"].astype(float).values
    ema9 = df["ema9"].astype(float).values
    ema20 = df["ema20"].astype(float).values
    ema50 = df["ema50"].astype(float).values
    bb_mid = df["bb_mid"].astype(float).values
    pdi = df["plus_di"].astype(float).values
    mdi = df["minus_di"].astype(float).values
    ad_r = df["ad_rising"].astype(bool).values
    ad_f = df["ad_falling"].astype(bool).values
    day = np.array([str(ts.date()) for ts in df.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df.index])
    idx = df.index
    n = len(c)

    rows = []
    for i in range(n):
        if day[i] not in keep or not (MINS_LO <= mins[i] <= MINS_HI):
            continue
        side = color_side(o, c, i)
        if side is None:
            continue
        st = streak_len_at(o, c, day, i, side)
        if st != 6:
            continue
        # first hit 6 only
        if i > 0 and day[i - 1] == day[i]:
            if color_side(o, c, i - 1) == side and streak_len_at(o, c, day, i - 1, side) == 5:
                pass
            else:
                continue
        else:
            continue

        entry = float(c[i])
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        vw = float(vwap[i]) if np.isfinite(vwap[i]) else entry
        e9, e20, e50 = float(ema9[i]), float(ema20[i]), float(ema50[i])
        bm = float(bb_mid[i]) if np.isfinite(bb_mid[i]) else entry
        e34 = float(ema34[i]) if np.isfinite(ema34[i]) else entry

        vwap_with = (side == "BUY" and entry >= vw) or (side == "SELL" and entry <= vw)
        ema_with = (side == "BUY" and e9 >= e20) or (side == "SELL" and e9 <= e20)
        ema50_with = (side == "BUY" and entry >= e50) or (side == "SELL" and entry <= e50)
        bb_mid_with = (side == "BUY" and entry >= bm) or (side == "SELL" and entry <= bm)
        desk_hits = sum([vwap_with, ema_with, ema50_with, bb_mid_with])
        di_ok = (side == "BUY" and pdi[i] > mdi[i]) or (side == "SELL" and mdi[i] > pdi[i])
        gate34 = (side == "BUY" and entry >= e34) or (side == "SELL" and entry <= e34)
        held = bool(di_ok and gate34 and vwap_with)
        ad = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))
        htf_raw = htf_bias_lookup(bias15, idx[i])
        htf_with = (side == "BUY" and htf_raw == "up") or (side == "SELL" and htf_raw == "down")
        ok, reason, exit_px, j, pts = scalper.path_ma_trail(h, l, c, ema34, i, side, T15)

        rows.append({
            "day": day[i],
            "hm": idx[i].strftime("%H:%M"),
            "mins": int(mins[i]),
            "side": side,
            "entry": round(entry, 2),
            "atr": round(a, 2),
            "desk_ge3": desk_hits >= 3,
            "held": held,
            "htf_with": bool(htf_with),
            "ad": bool(ad),
            "t15_win": bool(ok),
            "pts": round(float(pts), 2) if pts is not None else None,
        })

    print(f"hit6 first-touch rows: {len(rows)}", flush=True)

    # ATR sweep
    sweep = []
    for thr in (8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0):
        for name, pred in [
            (f"atr≥{thr:.0f}", lambda r, thr=thr: r["atr"] >= thr),
            (f"held+htf+atr≥{thr:.0f}", lambda r, thr=thr: r["held"] and r["htf_with"] and r["atr"] >= thr),
            (f"desk≥3+held+htf+atr≥{thr:.0f}", lambda r, thr=thr: r["desk_ge3"] and r["held"] and r["htf_with"] and r["atr"] >= thr),
            (f"desk≥3+held+htf+ad+atr≥{thr:.0f}", lambda r, thr=thr: r["desk_ge3"] and r["held"] and r["htf_with"] and r["ad"] and r["atr"] >= thr),
        ]:
            hit = [r for r in rows if pred(r)]
            one = one_per_day(hit)
            p, nn = prec(one)
            pa, na = prec(hit)
            # 3-fold
            folds = []
            for fi in range(3):
                lo = days_sorted[fi * 40]
                hi_d = days_sorted[min(n_days - 1, (fi + 1) * 40 - 1)]
                fr = [r for r in one if lo <= r["day"] <= hi_d]
                fp, fn = prec(fr)
                folds.append({"fold": fi + 1, "lo": lo, "hi": hi_d, "n": fn, "prec": fp})
            fold_precs = [f["prec"] for f in folds if f["prec"] is not None]
            sweep.append({
                "name": name,
                "n_1d": nn,
                "prec_1d": p,
                "n_all": na,
                "prec_all": pa,
                "coverage_pct": round(100.0 * nn / n_days, 1),
                "folds": folds,
                "fold_min": min(fold_precs) if fold_precs else None,
                "fold_avg": round(float(np.mean(fold_precs)), 2) if fold_precs else None,
            })
            print(
                f"  {name}: 1d n={nn} T15={p}% cov={100*nn/n_days:.0f}% "
                f"folds={[f['prec'] for f in folds]} min={min(fold_precs) if fold_precs else None}",
                flush=True,
            )

    # Recommended gate detail
    gate = [r for r in rows if r["desk_ge3"] and r["held"] and r["htf_with"] and r["atr"] >= 10]
    one = one_per_day(gate)
    buy = [r for r in one if r["side"] == "BUY"]
    sell = [r for r in one if r["side"] == "SELL"]
    pb, nb = prec(buy)
    ps, ns = prec(sell)

    # lean vs fat at ATR10
    lean = one_per_day([r for r in rows if r["held"] and r["htf_with"] and r["atr"] >= 10])
    fat = one
    pl, nl = prec(lean)
    pf, nf = prec(fat)

    lines = [
        "# NIFTY 1m — Oracle×Desk×streak **v3b validate**",
        "",
        "> Validate HIGH_75 candidate: **hit6 + desk≥3 + held + HTF + ATR≥10**",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). hit6 first-touch **{len(rows)}**.",
        "",
        "## 1) ATR threshold sweep (1/day)",
        "",
        "| Gate | n | T15% | cov% | fold1 | fold2 | fold3 | fold_min | fold_avg |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in sweep:
        f1, f2, f3 = s["folds"][0]["prec"], s["folds"][1]["prec"], s["folds"][2]["prec"]
        lines.append(
            f"| `{s['name']}` | {s['n_1d']} | **{s['prec_1d']}** | {s['coverage_pct']} | "
            f"{f1} | {f2} | {f3} | {s['fold_min']} | {s['fold_avg']} |"
        )

    # pick best stable: n≥25, fold_min≥65, prec≥70
    stable = [
        s for s in sweep
        if (s["n_1d"] or 0) >= 25
        and (s["prec_1d"] or 0) >= 70
        and (s["fold_min"] or 0) >= 65
    ]
    stable.sort(key=lambda x: (-(x["fold_min"] or 0), -(x["prec_1d"] or 0), -x["n_1d"]))

    lines += [
        "",
        "## 2) Stable picks (n≥25 · T15≥70 · fold_min≥65)",
        "",
    ]
    if not stable:
        lines.append("_None._")
    else:
        lines += ["| Gate | n | T15% | fold_min | fold_avg | cov% |", "|---|---:|---:|---:|---:|---:|"]
        for s in stable[:15]:
            lines.append(
                f"| `{s['name']}` | {s['n_1d']} | **{s['prec_1d']}** | {s['fold_min']} | "
                f"{s['fold_avg']} | {s['coverage_pct']} |"
            )

    lines += [
        "",
        "## 3) Recommended gate detail (ATR≥10 · desk≥3 · held · HTF)",
        "",
        f"- 1/day n=**{nf}** T15=**{pf}%** coverage **{100*nf/n_days:.0f}%** of days",
        f"- Lean (held+HTF+ATR≥10, no desk): n=**{nl}** T15=**{pl}%**",
        f"- BUY: n={nb} T15={pb}% · SELL: n={ns} T15={ps}%",
        "",
        "### Samples",
        "",
        "| Day | HM | Side | Entry | ATR | T15 | pts |",
        "|---|---|---|---:|---:|---|---:|",
    ]
    for x in one[:15]:
        lines.append(
            f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | "
            f"{x['atr']} | {x['t15_win']} | {x['pts']} |"
        )

    best = stable[0] if stable else None
    lines += [
        "",
        "## 4) Verdict",
        "",
    ]
    if best:
        lines += [
            f"**Validated:** `{best['name']}`",
            f"- 1/day T15 **{best['prec_1d']}%** · fold_min **{best['fold_min']}%** · cov **{best['coverage_pct']}%**",
            "",
            "```",
            "WAIT  : 6 consecutive same-color 1m bars (first hit)",
            "FILTER: Desk≥3 (VWAP+EMA stack+EMA50/BBmid)",
            "        held = DI + EMA34 side + VWAP with",
            "        HTF15 bias with side",
            "        ATR14 ≥ 10 (volatility regime)",
            "SIDE  : streak color",
            "EXIT  : EMA34 trail · T15",
            "```",
        ]
    else:
        lines.append("No gate passed n≥25 + T15≥70 + fold_min≥65. Treat v3 HIGH_75 as fragile.")

    lines += ["", f"_Generated in {time.time()-t0:.1f}s._", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps({"sweep": sweep, "best": best, "side": {"buy": [pb, nb], "sell": [ps, ns]}}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {REPORT}", flush=True)
    if best:
        print(f"VALIDATED BEST: {best['name']} T15={best['prec_1d']}% fold_min={best['fold_min']}", flush=True)
    print(f"done in {time.time()-t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
