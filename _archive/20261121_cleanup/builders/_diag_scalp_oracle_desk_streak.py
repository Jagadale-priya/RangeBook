"""RESEARCH ONLY — Oracle T15 + Desk (Fib·EMA·VWAP·BB) + same-color streak 4–6.

Goal: accurate ENTRY (side + when), not denser calls.
  - Oracle path: textbook event → EMA34 trail → T15 win (same exit as scalper)
  - Desk marks: VWAP / EMA9·20·50 / BB / Fib proximity + side alignment
  - Streak: require 4, 5, or 6 consecutive same-color 1m bars at entry

  python -u prod_live/tests/builders/_diag_scalp_oracle_desk_streak.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ORACLE_DESK_STREAK.md"
REPORT_JSON = OUT / "NIFTY_1M_ORACLE_DESK_STREAK.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 120
LOOKBACK_CAL = 240
T15 = 15.0
GAP = 15
ZONE_ATR = 0.45
FIB_RATIOS = (0.382, 0.5, 0.618)


def pack(rows, key, mid):
    if not rows:
        return {"n": 0, "prec": None, "train_n": 0, "train_prec": None, "oos_n": 0, "oos_prec": None,
                "avg_pts": None}
    tr = [r for r in rows if r["day"] < mid]
    oo = [r for r in rows if r["day"] >= mid]

    def _p(rs):
        if not rs:
            return None, 0
        return round(100.0 * sum(1 for x in rs if x.get(key)) / len(rs), 2), len(rs)

    p, n = _p(rows)
    pt, nt = _p(tr)
    po, no = _p(oo)
    pts = [r.get("pts") for r in rows if r.get("pts") is not None]
    return {
        "n": n,
        "prec": p,
        "train_n": nt,
        "train_prec": pt,
        "oos_n": no,
        "oos_prec": po,
        "avg_pts": round(float(np.mean(pts)), 2) if pts else None,
    }


def one_per_day(rows):
    byd = {}
    for r in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        if r["day"] not in byd:
            byd[r["day"]] = r
    return list(byd.values())


def verdict(st, min_n=20, min_half=8):
    if not st or st["n"] < min_n:
        return "THIN"
    if (st["prec"] or 0) >= 85 and (st["train_prec"] or 0) >= 80 and (st["oos_prec"] or 0) >= 80:
        return "HIGH_85"
    if (st["prec"] or 0) >= 75 and (st["train_prec"] or 0) >= 70 and (st["oos_prec"] or 0) >= 70:
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
    print("ORACLE T15 × DESK × same-color streak 4–6 — deep entry accuracy", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    df = add_ad_obv_proxy(df)

    # Desk series
    close = df["Close"].astype(float)
    df["ema9"] = close.ewm(span=9, adjust=False).mean()
    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()
    mid = close.rolling(20, min_periods=20).mean()
    std = close.rolling(20, min_periods=20).std(ddof=0)
    df["bb_mid"] = mid
    df["bb_up"] = mid + 2 * std
    df["bb_lo"] = mid - 2 * std

    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    mid_day = days_sorted[n_days // 2]
    df = df[[str(ts.date()) in keep for ts in df.index]]
    print(f"window {day_lo}→{day_hi} n={n_days} OOS≥{mid_day}", flush=True)

    day_lo_s, day_hi_s = day_lo, day_hi
    events = scalper._collect_events(df, day_lo_s, day_hi_s)
    scalper._enrich(events, df)
    setup.apply_setup_enrichment(events, df)
    print(f"textbook events: {len(events)}", flush=True)

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
    day = np.array([str(ts.date()) for ts in df.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df.index])
    idx = df.index
    n = len(c)

    def same_color_streak_ending(i, side):
        """Count consecutive same-color bars ending at i (inclusive)."""
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

    def near(level, px, a):
        if level is None or not np.isfinite(level):
            return False
        return abs(float(level) - px) <= ZONE_ATR * a

    rows = []
    for e in events:
        i = int(e.get("full_i") or e.get("i") or -1)
        if i < 0 or i >= n:
            continue
        d = day[i]
        if d not in keep or not (MINS_LO <= mins[i] <= MINS_HI):
            continue
        side = str(e.get("decision") or "")
        if side not in ("BUY", "SELL"):
            continue
        entry = float(e.get("entry") or c[i])
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        ok, reason, exit_px, j, pts = scalper.path_ma_trail(h, l, c, ema34, i, side, T15)
        streak = same_color_streak_ending(i, side)

        # Desk confluence
        vw = float(vwap[i]) if np.isfinite(vwap[i]) else entry
        e9, e20, e50 = float(ema9[i]), float(ema20[i]), float(ema50[i])
        bu, bl, bm = float(bb_up[i]), float(bb_lo[i]), float(bb_mid[i])
        vwap_with = (side == "BUY" and entry >= vw) or (side == "SELL" and entry <= vw)
        ema_stack_bull = np.isfinite(e9) and np.isfinite(e20) and e9 >= e20
        ema_stack_bear = np.isfinite(e9) and np.isfinite(e20) and e9 <= e20
        ema_with = (side == "BUY" and ema_stack_bull) or (side == "SELL" and ema_stack_bear)
        ema50_with = (side == "BUY" and np.isfinite(e50) and entry >= e50) or (
            side == "SELL" and np.isfinite(e50) and entry <= e50
        )
        # BB: bounce from lower (BUY) / upper (SELL) or break mid with
        bb_bounce = (side == "BUY" and near(bl, entry, a) and c[i] > o[i]) or (
            side == "SELL" and near(bu, entry, a) and c[i] < o[i]
        )
        bb_mid_with = (side == "BUY" and entry >= bm) or (side == "SELL" and entry <= bm)
        # Fib from recent swings
        sh, sl = swings(h, l, i)
        fib_near = False
        if sh and sl:
            hi_s, lo_s = max(sh[-3:]) if len(sh) >= 1 else None, min(sl[-3:]) if len(sl) >= 1 else None
            if hi_s is not None and lo_s is not None and hi_s > lo_s:
                span = hi_s - lo_s
                for r in FIB_RATIOS:
                    lvl = hi_s - r * span  # retracement from high
                    if near(lvl, entry, a):
                        fib_near = True
                        break
                    lvl2 = lo_s + r * span
                    if near(lvl2, entry, a):
                        fib_near = True
                        break

        desk_hits = sum(
            [
                bool(vwap_with),
                bool(ema_with),
                bool(ema50_with),
                bool(bb_bounce),
                bool(bb_mid_with),
                bool(fib_near),
            ]
        )
        desk_ge2 = desk_hits >= 2
        desk_ge3 = desk_hits >= 3
        desk_ge4 = desk_hits >= 4

        held = bool(e.get("held") or (e.get("di_ok") and e.get("gate_hard34") and e.get("vwap_with")))
        setup_ok = bool(e.get("setup_ok"))
        ctrl = bool(e.get("control_with") or e.get("ctrl"))

        rows.append(
            {
                "day": d,
                "hm": idx[i].strftime("%H:%M"),
                "mins": int(mins[i]),
                "side": side,
                "entry": round(entry, 2),
                "primary": e.get("primary"),
                "t15_win": bool(ok),
                "reason": reason,
                "pts": round(float(pts), 2) if pts is not None else None,
                "streak": int(streak),
                "streak4": streak >= 4,
                "streak5": streak >= 5,
                "streak6": streak >= 6,
                "vwap_with": bool(vwap_with),
                "ema_with": bool(ema_with),
                "ema50_with": bool(ema50_with),
                "bb_bounce": bool(bb_bounce),
                "bb_mid_with": bool(bb_mid_with),
                "fib_near": bool(fib_near),
                "desk_hits": int(desk_hits),
                "desk_ge2": desk_ge2,
                "desk_ge3": desk_ge3,
                "desk_ge4": desk_ge4,
                "held": held,
                "setup_ok": setup_ok,
                "ctrl": ctrl,
            }
        )

    print(f"scored rows: {len(rows)}  raw T15 win%={100*sum(1 for r in rows if r['t15_win'])/max(len(rows),1):.1f}%", flush=True)

    # Baseline books
    books = []

    def add(name, pred, key="t15_win"):
        hit = [r for r in rows if pred(r)]
        one = one_per_day(hit)
        # gap book (oracle-style multi with gap)
        gap_rows = []
        byd = defaultdict(list)
        for r in hit:
            byd[r["day"]].append(r)
        for d, rs in byd.items():
            next_ok = None
            for r in sorted(rs, key=lambda x: x["mins"]):
                if next_ok is not None and r["mins"] < next_ok:
                    continue
                gap_rows.append(r)
                next_ok = r["mins"] + GAP
        st1 = pack(one, key, mid_day)
        stg = pack(gap_rows, key, mid_day)
        sta = pack(hit, key, mid_day)
        v = verdict(st1)
        books.append(
            {
                "name": name,
                "verdict": v,
                "one": st1,
                "gap": stg,
                "all": sta,
                "samples": one[:8],
            }
        )
        print(
            f"  {name}: 1d n={st1['n']} prec={st1['prec']}% oos={st1['oos_prec']}% "
            f"| gap n={stg['n']} prec={stg['prec']}% | all n={sta['n']} → {v}",
            flush=True,
        )

    print("\n--- baselines ---", flush=True)
    add("Oracle raw (all textbook)", lambda r: True)
    add("Oracle + setup_ok", lambda r: r["setup_ok"])
    add("Oracle + held", lambda r: r["held"])
    add("Oracle + streak≥4", lambda r: r["streak4"])
    add("Oracle + streak≥5", lambda r: r["streak5"])
    add("Oracle + streak≥6", lambda r: r["streak6"])

    print("\n--- desk alone / combo ---", flush=True)
    add("desk≥2", lambda r: r["desk_ge2"])
    add("desk≥3", lambda r: r["desk_ge3"])
    add("desk≥4", lambda r: r["desk_ge4"])
    add("vwap_with", lambda r: r["vwap_with"])
    add("ema_with", lambda r: r["ema_with"])
    add("bb_bounce", lambda r: r["bb_bounce"])
    add("fib_near", lambda r: r["fib_near"])

    print("\n--- streak × desk (core ask) ---", flush=True)
    for sk, spred in (("streak≥4", lambda r: r["streak4"]), ("streak≥5", lambda r: r["streak5"]), ("streak≥6", lambda r: r["streak6"])):
        add(f"{sk}", spred)
        add(f"{sk}+desk≥2", lambda r, sp=spred: sp(r) and r["desk_ge2"])
        add(f"{sk}+desk≥3", lambda r, sp=spred: sp(r) and r["desk_ge3"])
        add(f"{sk}+vwap+ema", lambda r, sp=spred: sp(r) and r["vwap_with"] and r["ema_with"])
        add(f"{sk}+vwap+ema+bbmid", lambda r, sp=spred: sp(r) and r["vwap_with"] and r["ema_with"] and r["bb_mid_with"])
        add(f"{sk}+desk≥2+held", lambda r, sp=spred: sp(r) and r["desk_ge2"] and r["held"])
        add(f"{sk}+desk≥3+held", lambda r, sp=spred: sp(r) and r["desk_ge3"] and r["held"])
        add(f"{sk}+desk≥2+setup", lambda r, sp=spred: sp(r) and r["desk_ge2"] and r["setup_ok"])
        add(f"{sk}+vwap+ema+fib", lambda r, sp=spred: sp(r) and r["vwap_with"] and r["ema_with"] and r["fib_near"])
        add(f"{sk}+bb_bounce+vwap", lambda r, sp=spred: sp(r) and r["bb_bounce"] and r["vwap_with"])

    # Exhaustive small hunt on streak4/5 + desk flags
    print("\n--- hunt ---", flush=True)
    feat = ["streak4", "streak5", "streak6", "vwap_with", "ema_with", "ema50_with", "bb_bounce", "bb_mid_with", "fib_near", "held", "setup_ok", "desk_ge2", "desk_ge3"]
    hunt = []
    for k in (2, 3, 4):
        for combo in combinations(feat, k):
            # must include a streak requirement
            if not any(x.startswith("streak") for x in combo):
                continue
            hit = [r for r in rows if all(r.get(f) for f in combo)]
            one = one_per_day(hit)
            st = pack(one, "t15_win", mid_day)
            if st["n"] < 15 or st["prec"] is None or st["prec"] < 65:
                continue
            hunt.append({"name": "+".join(combo), **st, "verdict": verdict(st), "samples": one[:6]})
    hunt.sort(key=lambda x: (0 if x["verdict"] == "HIGH_85" else 1 if x["verdict"] == "HIGH_75" else 2, -(x["prec"] or 0), -(x["oos_prec"] or 0), -x["n"]))
    seen = set()
    hunt_u = []
    for hrow in hunt:
        if hrow["name"] in seen:
            continue
        seen.add(hrow["name"])
        hunt_u.append(hrow)
    hunt_u = hunt_u[:30]
    for hrow in hunt_u[:12]:
        print(
            f"  {hrow['verdict']} {hrow['name']}: n={hrow['n']} prec={hrow['prec']}% "
            f"tr={hrow['train_prec']}% oos={hrow['oos_prec']}%",
            flush=True,
        )

    # Rank curated
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
    if hunt_u and (
        best is None
        or (hunt_u[0]["prec"] or 0) > (best["one"]["prec"] or 0)
        or hunt_u[0]["verdict"] in ("HIGH_85", "HIGH_75") and best["verdict"] in ("WEAK", "OK_65", "THIN")
    ):
        best_show = {
            "name": "hunt|" + hunt_u[0]["name"],
            "verdict": hunt_u[0]["verdict"],
            "one": hunt_u[0],
            "samples": hunt_u[0].get("samples"),
        }
    else:
        best_show = best

    # How desk marks behave on winners vs losers (among streak≥4)
    st4 = [r for r in rows if r["streak4"]]
    win4 = [r for r in st4 if r["t15_win"]]
    lose4 = [r for r in st4 if not r["t15_win"]]

    def rate(rs, key):
        if not rs:
            return None
        return round(100.0 * sum(1 for r in rs if r.get(key)) / len(rs), 1)

    lines = [
        "# NIFTY 1m — **Oracle T15 × Desk (Fib·EMA·VWAP·BB) × same-color 4–6**",
        "",
        "> Deep entry accuracy. Target later. Metric = **T15 win** under EMA34 trail (same as scalper Oracle T15).",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS **{mid_day}**. Events **{len(rows)}**.",
        "",
        "## Recipe under test",
        "",
        "```",
        "1) Textbook pattern event (Oracle universe)",
        "2) Require 4–6 consecutive same-color 1m bars ending at entry",
        "3) Desk confluence: VWAP / EMA9-20 stack / EMA50 / BB / Fib nearby",
        "4) Side = pattern decision · Exit check = EMA34 trail · T15",
        "```",
        "",
        "## 0) Raw Oracle vs streak cut",
        "",
        f"- Raw textbook T15 win (all signals): **{100*sum(1 for r in rows if r['t15_win'])/max(len(rows),1):.1f}%** n={len(rows)}",
        f"- Among streak≥4: T15 win **{100*sum(1 for r in st4 if r['t15_win'])/max(len(st4),1):.1f}%** n={len(st4)}",
        "",
        "## 1) Desk marks on streak≥4 winners vs losers",
        "",
        "| Mark | % of Winners | % of Losers | Lift pp |",
        "|---|---:|---:|---:|",
    ]
    for k in ("vwap_with", "ema_with", "ema50_with", "bb_bounce", "bb_mid_with", "fib_near", "held", "setup_ok", "desk_ge2", "desk_ge3", "desk_ge4"):
        rw, rl = rate(win4, k), rate(lose4, k)
        lift = round((rw or 0) - (rl or 0), 1) if rw is not None and rl is not None else None
        lines.append(f"| `{k}` | {rw} | {rl} | {lift} |")

    lines += [
        "",
        "## 2) Curated gates (1/day · T15 win%)",
        "",
        "| Gate | Verdict | n | T15% | Train | OOS | gap n/prec | avg pts |",
        "|---|---|---:|---:|---:|---:|---|---:|",
    ]
    for b in ranked:
        s = b["one"]
        g = b["gap"]
        lines.append(
            f"| `{b['name']}` | **{b['verdict']}** | {s['n']} | **{s['prec']}** | {s['train_prec']} | "
            f"{s['oos_prec']} | {g['n']}/{g['prec']} | {s['avg_pts']} |"
        )

    lines += ["", "## 3) Hunt ≥65% T15 (1/day, n≥15)", ""]
    if not hunt_u:
        lines.append("_None._")
    else:
        lines += [
            "| Rule | Verdict | n | T15% | Train | OOS |",
            "|---|---|---:|---:|---:|---:|",
        ]
        for hrow in hunt_u[:20]:
            lines.append(
                f"| `{hrow['name']}` | **{hrow['verdict']}** | {hrow['n']} | **{hrow['prec']}** | "
                f"{hrow['train_prec']} | {hrow['oos_prec']} |"
            )

    lines += ["", "## 4) Most accurate entry (this pass)", ""]
    if best_show:
        s = best_show["one"] if "one" in best_show else best_show
        lines += [
            f"**Best effort:** `{best_show['name']}` · **{best_show.get('verdict')}**",
            f"- 1/day T15 **{s.get('prec')}%** · TRAIN **{s.get('train_prec')}%** · OOS **{s.get('oos_prec')}%** · n={s.get('n')}",
            "",
            "### How it moves with indication",
            "",
            "1. Wait for **4–6 same-color** 1m bars (direction locked).",
            "2. Prefer entry when **Desk** agrees: VWAP side + EMA stack (+ BB/Fib if present).",
            "3. Take **Oracle textbook** event at that bar (side from pattern).",
            "4. Manage with **EMA34 trail · T15** (same as scalper).",
            "",
            "### Samples",
            "",
            "| Day | HM | Side | Entry | streak | desk | T15 |",
            "|---|---|---|---:|---:|---:|---|",
        ]
        for x in (best_show.get("samples") or [])[:10]:
            lines.append(
                f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | "
                f"{x.get('streak')} | {x.get('desk_hits')} | {x.get('t15_win')} |"
            )
    else:
        lines.append("_No viable gate._")

    high = [b for b in ranked if b["verdict"] in ("HIGH_85", "HIGH_75")] + [
        h for h in hunt_u if h["verdict"] in ("HIGH_85", "HIGH_75")
    ]
    lines += [
        "",
        "## 5) Verdict for live scalper",
        "",
        f"- Gates ≥75% T15 walk-forward: **{len(high)}**",
        "- If best ≥75% OOS-stable: candidate filter = streak 4–6 + desk confluence on Oracle T15.",
        "- If still <70%: streak cuts noise but desk alone does not unlock near-certain entries.",
        "",
        f"_Generated in {time.time() - t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "books": [
                    {"name": b["name"], "verdict": b["verdict"], "one": b["one"], "gap": b["gap"]}
                    for b in ranked
                ],
                "hunt": hunt_u,
                "best": best_show["name"] if best_show else None,
                "desk_lift_streak4": {
                    k: {"win": rate(win4, k), "lose": rate(lose4, k)}
                    for k in ("vwap_with", "ema_with", "ema50_with", "bb_bounce", "bb_mid_with", "fib_near", "held", "setup_ok")
                },
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT}", flush=True)
    if best_show:
        s = best_show["one"] if "one" in best_show else best_show
        print(f"BEST={best_show['name']} {best_show.get('verdict')} T15={s.get('prec')}%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
