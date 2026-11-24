"""RESEARCH ONLY — Enter when same-color streak first hits 4/5/6 + Desk + Oracle side.

v1: pattern bar already had streak → ~63% T15 max.
v2: wait until streak reaches N bars, enter at that close, side from streak,
    require Desk confluence; optional: a textbook event earlier in the streak.

  python -u prod_live/tests/builders/_diag_scalp_oracle_desk_streak_v2.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
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

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_1m as scalper  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ORACLE_DESK_STREAK_V2.md"
REPORT_JSON = OUT / "NIFTY_1M_ORACLE_DESK_STREAK_V2.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 120
LOOKBACK_CAL = 240
T15 = 15.0
ZONE_ATR = 0.45
FIB_RATIOS = (0.382, 0.5, 0.618)


def pack(rows, key, mid):
    if not rows:
        return {"n": 0, "prec": None, "train_n": 0, "train_prec": None, "oos_n": 0, "oos_prec": None, "avg_pts": None}
    tr = [r for r in rows if r["day"] < mid]
    oo = [r for r in rows if r["day"] >= mid]

    def _p(rs):
        if not rs:
            return None, 0
        return round(100.0 * sum(1 for x in rs if x.get(key)) / len(rs), 2), len(rs)

    p, n = _p(rows)
    pt, nt = _p(tr)
    po, no = _p(oo)
    pts = [r["pts"] for r in rows if r.get("pts") is not None]
    return {
        "n": n, "prec": p, "train_n": nt, "train_prec": pt, "oos_n": no, "oos_prec": po,
        "avg_pts": round(float(np.mean(pts)), 2) if pts else None,
    }


def one_per_day(rows):
    byd = {}
    for r in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        if r["day"] not in byd:
            byd[r["day"]] = r
    return list(byd.values())


def verdict(st, min_n=20):
    if not st or st["n"] < min_n:
        return "THIN"
    if (st["prec"] or 0) >= 85 and (st["oos_prec"] or 0) >= 80 and (st["train_prec"] or 0) >= 80:
        return "HIGH_85"
    if (st["prec"] or 0) >= 75 and (st["oos_prec"] or 0) >= 70 and (st["train_prec"] or 0) >= 70:
        return "HIGH_75"
    if (st["prec"] or 0) >= 65 and (st["oos_prec"] or 0) >= 60:
        return "OK_65"
    return "WEAK"


def swings(h, l, i, L=3, look=80):
    lo = max(L, i - look)
    sh, sl = [], []
    for j in range(lo, i - L):
        if h[j] >= np.max(h[j - L : j + L + 1]) - 1e-9:
            sh.append(float(h[j]))
        if l[j] <= np.min(l[j - L : j + L + 1]) + 1e-9:
            sl.append(float(l[j]))
    return sh, sl


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("v2: enter at streak hit 4/5/6 + desk", flush=True)

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
    mid = close.rolling(20, min_periods=20).mean()
    std = close.rolling(20, min_periods=20).std(ddof=0)
    df["bb_mid"], df["bb_up"], df["bb_lo"] = mid, mid + 2 * std, mid - 2 * std

    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    mid_day = days_sorted[n_days // 2]
    df = df[[str(ts.date()) in keep for ts in df.index]]
    print(f"window {day_lo}→{day_hi} OOS≥{mid_day}", flush=True)

    # Oracle event bars (for optional "pattern in streak" flag)
    events = scalper._collect_events(df, day_lo, day_hi)
    event_at = set()
    for e in events:
        i = int(e.get("full_i") or -1)
        side = e.get("decision")
        if i >= 0 and side in ("BUY", "SELL"):
            event_at.add((i, side))

    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    atr = df["atr14"].astype(float).values
    vwap = df["vwap"].astype(float).values if "vwap" in df.columns else c.copy()
    ema9 = df["ema9"].astype(float).values
    ema20 = df["ema20"].astype(float).values
    ema50 = df["ema50"].astype(float).values
    bb_up = df["bb_up"].astype(float).values
    bb_lo = df["bb_lo"].astype(float).values
    bb_mid = df["bb_mid"].astype(float).values
    pdi = df["plus_di"].astype(float).values if "plus_di" in df.columns else np.zeros(len(c))
    mdi = df["minus_di"].astype(float).values if "minus_di" in df.columns else np.zeros(len(c))
    day = np.array([str(ts.date()) for ts in df.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df.index])
    idx = df.index
    n = len(c)

    def near(level, px, a):
        return level is not None and np.isfinite(level) and abs(float(level) - px) <= ZONE_ATR * a

    cands = []
    i = 1
    while i < n - 1:
        if day[i] not in keep or not (MINS_LO <= mins[i] <= MINS_HI):
            i += 1
            continue
        green, red = c[i] > o[i], c[i] < o[i]
        if not green and not red:
            i += 1
            continue
        side = "BUY" if green else "SELL"
        # streak length ending at i
        s = i
        while s - 1 >= 0 and day[s - 1] == day[i]:
            if side == "BUY" and c[s - 1] > o[s - 1]:
                s -= 1
            elif side == "SELL" and c[s - 1] < o[s - 1]:
                s -= 1
            else:
                break
        streak = i - s + 1
        # emit only when streak FIRST hits 4, 5, or 6
        if streak not in (4, 5, 6):
            i += 1
            continue

        entry = float(c[i])
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        ok, reason, exit_px, j, pts = scalper.path_ma_trail(h, l, c, ema34, i, side, T15)

        vw = float(vwap[i]) if np.isfinite(vwap[i]) else entry
        e9, e20, e50 = float(ema9[i]), float(ema20[i]), float(ema50[i])
        bu, bl, bm = float(bb_up[i]), float(bb_lo[i]), float(bb_mid[i])
        vwap_with = (side == "BUY" and entry >= vw) or (side == "SELL" and entry <= vw)
        ema_with = (side == "BUY" and np.isfinite(e9) and np.isfinite(e20) and e9 >= e20) or (
            side == "SELL" and np.isfinite(e9) and np.isfinite(e20) and e9 <= e20
        )
        ema50_with = (side == "BUY" and np.isfinite(e50) and entry >= e50) or (
            side == "SELL" and np.isfinite(e50) and entry <= e50
        )
        bb_bounce = (side == "BUY" and near(bl, entry, a)) or (side == "SELL" and near(bu, entry, a))
        bb_mid_with = (side == "BUY" and entry >= bm) or (side == "SELL" and entry <= bm)
        sh, sl = swings(h, l, i)
        fib_near = False
        if sh and sl:
            hi_s, lo_s = max(sh[-3:]), min(sl[-3:])
            if hi_s > lo_s:
                span = hi_s - lo_s
                for r in FIB_RATIOS:
                    if near(hi_s - r * span, entry, a) or near(lo_s + r * span, entry, a):
                        fib_near = True
                        break
        desk_hits = sum([vwap_with, ema_with, ema50_with, bb_bounce, bb_mid_with, fib_near])
        di_ok = (side == "BUY" and pdi[i] > mdi[i]) or (side == "SELL" and mdi[i] > pdi[i])
        gate34 = (side == "BUY" and entry >= float(ema34[i])) or (side == "SELL" and entry <= float(ema34[i]))
        held = bool(di_ok and gate34 and vwap_with)
        # textbook event somewhere in this streak
        has_oracle_evt = any((k, side) in event_at for k in range(s, i + 1))

        cands.append(
            {
                "day": day[i],
                "hm": idx[i].strftime("%H:%M"),
                "mins": int(mins[i]),
                "side": side,
                "entry": round(entry, 2),
                "streak": streak,
                "t15_win": bool(ok),
                "pts": round(float(pts), 2) if pts is not None else None,
                "vwap_with": vwap_with,
                "ema_with": ema_with,
                "ema50_with": ema50_with,
                "bb_bounce": bb_bounce,
                "bb_mid_with": bb_mid_with,
                "fib_near": fib_near,
                "desk_ge2": desk_hits >= 2,
                "desk_ge3": desk_hits >= 3,
                "desk_ge4": desk_hits >= 4,
                "desk_hits": desk_hits,
                "held": held,
                "has_oracle_evt": has_oracle_evt,
            }
        )
        i += 1

    print(f"streak-hit cands: {len(cands)}", flush=True)
    books = []

    def add(name, pred):
        hit = [r for r in cands if pred(r)]
        one = one_per_day(hit)
        st = pack(one, "t15_win", mid_day)
        sta = pack(hit, "t15_win", mid_day)
        v = verdict(st)
        books.append({"name": name, "verdict": v, "one": st, "all": sta, "samples": one[:10]})
        print(
            f"  {name}: 1d n={st['n']} T15={st['prec']}% tr={st['train_prec']}% oos={st['oos_prec']}% "
            f"| all n={sta['n']} prec={sta['prec']}% → {v}",
            flush=True,
        )

    for N in (4, 5, 6):
        add(f"hit{N}", lambda r, N=N: r["streak"] == N)
        add(f"hit{N}+desk≥2", lambda r, N=N: r["streak"] == N and r["desk_ge2"])
        add(f"hit{N}+desk≥3", lambda r, N=N: r["streak"] == N and r["desk_ge3"])
        add(f"hit{N}+vwap+ema", lambda r, N=N: r["streak"] == N and r["vwap_with"] and r["ema_with"])
        add(f"hit{N}+vwap+ema+held", lambda r, N=N: r["streak"] == N and r["vwap_with"] and r["ema_with"] and r["held"])
        add(f"hit{N}+desk≥3+held", lambda r, N=N: r["streak"] == N and r["desk_ge3"] and r["held"])
        add(f"hit{N}+oracle_evt+desk≥2", lambda r, N=N: r["streak"] == N and r["has_oracle_evt"] and r["desk_ge2"])
        add(f"hit{N}+oracle_evt+desk≥3+held", lambda r, N=N: r["streak"] == N and r["has_oracle_evt"] and r["desk_ge3"] and r["held"])
        add(f"hit{N}+vwap+ema+ema50", lambda r, N=N: r["streak"] == N and r["vwap_with"] and r["ema_with"] and r["ema50_with"])
        add(f"hit{N}+FULL", lambda r, N=N: r["streak"] == N and r["vwap_with"] and r["ema_with"] and r["ema50_with"] and r["held"] and r["desk_ge3"])

    # also ≥N (first touch already exact N)
    add("any4-6+desk≥3+held", lambda r: r["streak"] in (4, 5, 6) and r["desk_ge3"] and r["held"])
    add("any4-6+oracle+desk≥3+held", lambda r: r["streak"] in (4, 5, 6) and r["has_oracle_evt"] and r["desk_ge3"] and r["held"])
    add("any4-6+vwap+ema+held", lambda r: r["streak"] in (4, 5, 6) and r["vwap_with"] and r["ema_with"] and r["held"])

    ranked = sorted(
        books,
        key=lambda b: (
            0 if b["verdict"] == "HIGH_85" else 1 if b["verdict"] == "HIGH_75" else 2 if b["verdict"] == "OK_65" else 3,
            -(b["one"]["prec"] or 0),
            -(b["one"]["oos_prec"] or 0),
            -b["one"]["n"],
        ),
    )
    best = ranked[0] if ranked else None

    lines = [
        "# NIFTY 1m — Oracle/Desk streak **v2** (enter when streak hits 4/5/6)",
        "",
        "> Entry = close of the bar where same-color streak **first reaches** 4, 5, or 6.",
        "> Side = streak direction. Desk = Fib·EMA·VWAP·BB. Optional: textbook event inside streak.",
        "> Metric = EMA34 trail **T15** win (scalper Oracle exit).",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS **{mid_day}**. Candidates **{len(cands)}**.",
        "",
        "| Gate | Verdict | n | T15% | Train | OOS | all n/prec | avg pts |",
        "|---|---|---:|---:|---:|---:|---|---:|",
    ]
    for b in ranked:
        s, a = b["one"], b["all"]
        lines.append(
            f"| `{b['name']}` | **{b['verdict']}** | {s['n']} | **{s['prec']}** | {s['train_prec']} | "
            f"{s['oos_prec']} | {a['n']}/{a['prec']} | {s['avg_pts']} |"
        )

    lines += ["", "## Best accurate entry", ""]
    if best:
        s = best["one"]
        lines += [
            f"**`{best['name']}`** · {best['verdict']}",
            f"- 1/day T15 **{s['prec']}%** · TRAIN {s['train_prec']}% · OOS **{s['oos_prec']}%** · n={s['n']}",
            "",
            "```",
            "WAIT  : 4–6 consecutive same-color 1m candles",
            "ENTER : close of the bar that completes the count",
            "FILTER: Desk confluence (VWAP + EMA stack ± held / hits≥3)",
            "SIDE  : streak direction (BUY green / SELL red)",
            "EXIT  : EMA34 trail · T15 (Oracle T15 geometry)",
            "```",
            "",
            "| Day | HM | Side | Entry | streak | desk | T15 |",
            "|---|---|---|---:|---:|---:|---|",
        ]
        for x in best.get("samples") or []:
            lines.append(
                f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | "
                f"{x['streak']} | {x['desk_hits']} | {x['t15_win']} |"
            )
    lines += [
        "",
        "## vs v1",
        "",
        "- v1 (pattern already had streak): best ~**63%** T15",
        f"- v2 (enter at streak hit): best **{best['one']['prec'] if best else 'n/a'}%**",
        "",
        f"_Generated in {time.time() - t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({"books": books, "best": best}, indent=2, default=str), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    if best:
        print(f"BEST={best['name']} {best['verdict']} T15={best['one']['prec']}%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
