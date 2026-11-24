"""RESEARCH ONLY — OR-line cross with Swing + EMA already with side (v2).

v1: trigger = EMA20 cross → USER OR·Swing context ≈40% T15 (path~67%).
v2: trigger = price crosses OR high/low (the OR line you watch),
    require Swing stacked on that OR + EMA20 already with side (above for BUY).

Also: Swing-level cross with EMA with + OR context.

  python -u prod_live/tests/builders/_diag_scalp_desk_or_swing_ema_v2.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
from _diag_scalp_pa_bos_choch_fvg import (  # noqa: E402
    to_15m, structure_events, build_htf_bias, htf_bias_lookup,
)

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_1m as scalper  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_DESK_OR_SWING_EMA_V2.md"
REPORT_JSON = OUT / "NIFTY_1M_DESK_OR_SWING_EMA_V2.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 120
LOOKBACK_CAL = 240
T15 = 15.0
OR_BARS = 15
SWING_L = 3
ZONE_ATR = 0.45
PATH_ATR = 0.35
PATH_BARS = 8
FWD = 30


def pack(rows, key, mid):
    if not rows:
        return {"n": 0, "prec": None, "train_n": 0, "train_prec": None,
                "oos_n": 0, "oos_prec": None, "avg_pts": None, "avg_mfe": None}
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
    mfes = [r["mfe"] for r in rows if r.get("mfe") is not None]
    return {
        "n": n, "prec": p, "train_n": nt, "train_prec": pt,
        "oos_n": no, "oos_prec": po,
        "avg_pts": round(float(np.mean(pts)), 2) if pts else None,
        "avg_mfe": round(float(np.mean(mfes)), 2) if mfes else None,
    }


def one_per_day(rows):
    byd = {}
    for r in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        if r["day"] not in byd:
            byd[r["day"]] = r
    return list(byd.values())


def verdict(st, min_n=15):
    if not st or st["n"] < min_n:
        return "THIN"
    if (st["prec"] or 0) >= 75 and (st["oos_prec"] or 0) >= 70 and (st["train_prec"] or 0) >= 70:
        return "HIGH_75"
    if (st["prec"] or 0) >= 70 and (st["oos_prec"] or 0) >= 65 and (st["train_prec"] or 0) >= 65:
        return "OK_70"
    if (st["prec"] or 0) >= 65 and (st["oos_prec"] or 0) >= 60:
        return "OK_65"
    return "WEAK"


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("v2: OR-line cross + Swing stack + EMA with (1m)", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)

    close = df["Close"].astype(float)
    df["ema9"] = close.ewm(span=9, adjust=False).mean()
    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()

    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    mid_day = days_sorted[n_days // 2]
    df = df[[str(ts.date()) in keep for ts in df.index]].copy()
    print(f"window {day_lo}→{day_hi} n={n_days} OOS≥{mid_day}", flush=True)

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
    pdi = df["plus_di"].astype(float).values
    mdi = df["minus_di"].astype(float).values
    day = np.array([str(ts.date()) for ts in df.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df.index])
    idx = df.index
    n = len(c)

    # OR
    or_hi = np.full(n, np.nan)
    or_lo = np.full(n, np.nan)
    sess_i = np.zeros(n, dtype=int)
    by_day = defaultdict(list)
    for i in range(n):
        by_day[day[i]].append(i)
    for d, ixs in by_day.items():
        for k, i in enumerate(ixs):
            sess_i[i] = k
        if len(ixs) >= OR_BARS:
            hi_or = float(np.max(h[ixs[:OR_BARS]]))
            lo_or = float(np.min(l[ixs[:OR_BARS]]))
            for i in ixs[OR_BARS:]:
                or_hi[i] = hi_or
                or_lo[i] = lo_or

    # swings confirmed
    conf_hi = np.zeros(n, dtype=bool)
    conf_lo = np.zeros(n, dtype=bool)
    for j in range(SWING_L, n - SWING_L):
        if h[j] >= np.max(h[j - SWING_L : j + SWING_L + 1]) - 1e-9:
            conf_hi[j + SWING_L] = True
        if l[j] <= np.min(l[j - SWING_L : j + SWING_L + 1]) + 1e-9:
            conf_lo[j + SWING_L] = True

    sh_run: List[Tuple[int, float]] = []
    sl_run: List[Tuple[int, float]] = []
    levels_at: List[List[float]] = [[] for _ in range(n)]
    for i in range(n):
        if conf_hi[i] and i >= SWING_L:
            sh_run.append((i - SWING_L, float(h[i - SWING_L])))
            sh_run = sh_run[-12:]
        if conf_lo[i] and i >= SWING_L:
            sl_run.append((i - SWING_L, float(l[i - SWING_L])))
            sl_run = sl_run[-12:]
        recent = [(ii, pp) for ii, pp in (sh_run + sl_run) if i - ii <= 80]
        recent = sorted(recent, key=lambda x: x[1])
        out = []
        if recent:
            cur = [recent[0]]
            for p in recent[1:]:
                span = max(abs(p[1]) * 0.0025, 4.0)
                if abs(p[1] - cur[-1][1]) <= span:
                    cur.append(p)
                else:
                    out.append(float(np.mean([x[1] for x in cur])))
                    cur = [p]
            out.append(float(np.mean([x[1] for x in cur])))
        levels_at[i] = out[-6:]

    def near(a, b, atr_v):
        return abs(float(a) - float(b)) <= ZONE_ATR * atr_v

    cands = []
    for i in range(1, n):
        if day[i] not in keep or day[i - 1] != day[i]:
            continue
        if not (MINS_LO <= mins[i] <= MINS_HI) or sess_i[i] < OR_BARS:
            continue
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        entry = float(c[i])
        prev = float(c[i - 1])
        oh, ol = float(or_hi[i]), float(or_lo[i])
        if not (np.isfinite(oh) and np.isfinite(ol) and oh > ol):
            continue
        e20 = float(ema20[i])
        e9 = float(ema9[i])
        e50 = float(ema50[i])
        vw = float(vwap[i]) if np.isfinite(vwap[i]) else entry
        e34 = float(ema34[i]) if np.isfinite(ema34[i]) else entry

        # Triggers on OR line
        or_x_up = prev < oh <= entry   # close crosses OR high
        or_x_dn = prev > ol >= entry   # close crosses OR low down
        or_hold_sup = l[i] <= ol and entry >= ol
        or_hold_res = h[i] >= oh and entry <= oh
        # reclaim: was below OR high, now above (or vice versa) — includes break
        reclaim_up = prev <= oh and entry > oh
        reclaim_dn = prev >= ol and entry < ol

        lv = levels_at[i]
        swing_on_or_hi = any(near(oh, p, a) for p in lv)
        swing_on_or_lo = any(near(ol, p, a) for p in lv)
        # swing cross
        swing_x_up = False
        swing_x_dn = False
        for p in lv:
            if prev < p <= entry:
                swing_x_up = True
            if prev > p >= entry:
                swing_x_dn = True

        # Emit candidates for each trigger type
        triggers = []
        if or_x_up or reclaim_up:
            triggers.append(("or_cross_up", "BUY", swing_on_or_hi or swing_on_or_lo))
        if or_x_dn or reclaim_dn:
            triggers.append(("or_cross_dn", "SELL", swing_on_or_hi or swing_on_or_lo))
        if or_hold_sup:
            triggers.append(("or_hold_sup", "BUY", swing_on_or_lo))
        if or_hold_res:
            triggers.append(("or_hold_res", "SELL", swing_on_or_hi))
        if swing_x_up:
            triggers.append(("swing_cross_up", "BUY", swing_on_or_hi or swing_on_or_lo or near(oh, entry, a) or near(ol, entry, a)))
        if swing_x_dn:
            triggers.append(("swing_cross_dn", "SELL", swing_on_or_hi or swing_on_or_lo or near(oh, entry, a) or near(ol, entry, a)))

        if not triggers:
            continue

        for mode, side, swing_stack in triggers:
            ema_with = (side == "BUY" and entry >= e20) or (side == "SELL" and entry <= e20)
            ema_stack = (side == "BUY" and e9 >= e20) or (side == "SELL" and e9 <= e20)
            ema50_with = (side == "BUY" and entry >= e50) or (side == "SELL" and entry <= e50)
            # EMA9/20 cross same bar
            e9p, e20p = float(ema9[i - 1]), float(ema20[i - 1])
            ema_cross = (
                (side == "BUY" and e9p <= e20p and e9 > e20)
                or (side == "SELL" and e9p >= e20p and e9 < e20)
            )
            vwap_with = (side == "BUY" and entry >= vw) or (side == "SELL" and entry <= vw)
            di_ok = (side == "BUY" and pdi[i] > mdi[i]) or (side == "SELL" and mdi[i] > pdi[i])
            gate34 = (side == "BUY" and entry >= e34) or (side == "SELL" and entry <= e34)
            held = bool(di_ok and gate34 and vwap_with)
            htf = htf_bias_lookup(bias15, idx[i])
            htf_with = (side == "BUY" and htf == "up") or (side == "SELL" and htf == "down")
            atr_hi = a >= 10.0
            atr_12 = a >= 12.0

            ok, reason, exit_px, j, pts = scalper.path_ma_trail(h, l, c, ema34, i, side, T15)
            # path + mfe
            mfe = mae = 0.0
            path_ok = None
            need = PATH_ATR * a
            d = day[i]
            for j2 in range(i + 1, min(n - 1, i + FWD) + 1):
                if day[j2] != d:
                    break
                if side == "BUY":
                    mfe = max(mfe, float(h[j2]) - entry)
                    mae = max(mae, entry - float(l[j2]))
                else:
                    mfe = max(mfe, entry - float(l[j2]))
                    mae = max(mae, float(h[j2]) - entry)
            for j2 in range(i + 1, min(n - 1, i + PATH_BARS) + 1):
                if day[j2] != d:
                    break
                if side == "BUY" and float(h[j2]) - entry >= need:
                    path_ok = True
                    break
                if side == "SELL" and entry - float(l[j2]) >= need:
                    path_ok = True
                    break
                if side == "BUY" and entry - float(l[j2]) >= need:
                    path_ok = False
                    break
                if side == "SELL" and float(h[j2]) - entry >= need:
                    path_ok = False
                    break

            # USER visual: OR line move + swing + EMA with
            user = bool(swing_stack and ema_with)
            user_cross = bool(swing_stack and ema_cross)
            user_stack = bool(swing_stack and ema_with and ema_stack)

            cands.append({
                "day": day[i], "hm": idx[i].strftime("%H:%M"), "mins": int(mins[i]),
                "mode": mode, "side": side, "entry": round(entry, 2), "atr": round(a, 2),
                "t15_win": bool(ok), "pts": round(float(pts), 2) if pts is not None else None,
                "mfe": round(mfe, 2), "path_ok": path_ok is True,
                "swing_stack": bool(swing_stack),
                "ema_with": bool(ema_with),
                "ema_stack": bool(ema_stack),
                "ema_cross": bool(ema_cross),
                "ema50_with": bool(ema50_with),
                "vwap_with": bool(vwap_with),
                "held": held, "htf_with": bool(htf_with),
                "atr_hi": bool(atr_hi), "atr_12": bool(atr_12),
                "user": user, "user_cross": user_cross, "user_stack": user_stack,
                "is_or_cross": mode in ("or_cross_up", "or_cross_dn"),
                "is_or_hold": mode in ("or_hold_sup", "or_hold_res"),
                "is_swing_cross": mode in ("swing_cross_up", "swing_cross_dn"),
            })

    print(f"candidates: {len(cands)}", flush=True)
    books = []

    def add(name, pred):
        hit = [r for r in cands if pred(r)]
        one = one_per_day(hit)
        st1 = pack(one, "t15_win", mid_day)
        path_rows = [r for r in one if r.get("path_ok") is not None]
        path_p = round(100.0 * sum(1 for r in path_rows if r["path_ok"]) / len(path_rows), 2) if path_rows else None
        v = verdict(st1)
        books.append({"name": name, "verdict": v, "one": st1, "path_prec": path_p, "samples": one[:8]})
        print(f"  {name}: 1d n={st1['n']} T15={st1['prec']}% oos={st1['oos_prec']}% path={path_p}% → {v}", flush=True)

    print("\n--- OR-line triggers ---", flush=True)
    add("OR cross (any)", lambda r: r["is_or_cross"])
    add("OR cross + EMA with", lambda r: r["is_or_cross"] and r["ema_with"])
    add("OR cross + Swing on OR", lambda r: r["is_or_cross"] and r["swing_stack"])
    add("OR cross + Swing + EMA with (USER)", lambda r: r["is_or_cross"] and r["user"])
    add("OR cross + Swing + EMA9/20 cross", lambda r: r["is_or_cross"] and r["user_cross"])
    add("OR cross + Swing + EMA stack", lambda r: r["is_or_cross"] and r["user_stack"])
    add("USER + held", lambda r: r["is_or_cross"] and r["user"] and r["held"])
    add("USER + held + HTF", lambda r: r["is_or_cross"] and r["user"] and r["held"] and r["htf_with"])
    add("USER + held + HTF + ATR≥10", lambda r: r["is_or_cross"] and r["user"] and r["held"] and r["htf_with"] and r["atr_hi"])
    add("USER + held + HTF + ATR≥12", lambda r: r["is_or_cross"] and r["user"] and r["held"] and r["htf_with"] and r["atr_12"])
    add("USER + VWAP with + HTF + ATR≥10", lambda r: r["is_or_cross"] and r["user"] and r["vwap_with"] and r["htf_with"] and r["atr_hi"])

    print("\n--- OR hold (bounce) ---", flush=True)
    add("OR hold + Swing + EMA", lambda r: r["is_or_hold"] and r["user"])
    add("OR hold USER + held + HTF + ATR≥10", lambda r: r["is_or_hold"] and r["user"] and r["held"] and r["htf_with"] and r["atr_hi"])

    print("\n--- Swing cross near OR ---", flush=True)
    add("Swing cross near OR + EMA", lambda r: r["is_swing_cross"] and r["user"])
    add("Swing cross USER + held + HTF + ATR≥10", lambda r: r["is_swing_cross"] and r["user"] and r["held"] and r["htf_with"] and r["atr_hi"])

    # Side split on best-looking raw USER
    add("USER OR-cross BUY only", lambda r: r["is_or_cross"] and r["user"] and r["side"] == "BUY")
    add("USER OR-cross SELL only", lambda r: r["is_or_cross"] and r["user"] and r["side"] == "SELL")

    ranked = sorted([b for b in books if b["one"]["n"] >= 12], key=lambda b: (-(b["one"]["prec"] or 0), -b["one"]["n"]))
    best = ranked[0] if ranked else None
    best70 = next((b for b in ranked if (b["one"]["prec"] or 0) >= 70 and (b["one"]["oos_prec"] or 0) >= 65), None)
    pick = best70 or best

    lines = [
        "# NIFTY 1m — Desk OR-line cross × Swing × EMA (v2)",
        "",
        "> Trigger = **price crosses OR high/low** (the OR line).",
        "> Require **Swing stacked on OR** + **EMA20 with side** (up=BUY / below=SELL).",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS **{mid_day}**. Candidates **{len(cands)}**.",
        "",
        "## Gates (1/day · T15)",
        "",
        "| Gate | Verdict | n | T15% | Train | OOS | path% | avg MFE | avg pts |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for b in ranked:
        o1 = b["one"]
        lines.append(
            f"| `{b['name']}` | **{b['verdict']}** | {o1['n']} | **{o1['prec']}** | "
            f"{o1['train_prec']} | {o1['oos_prec']} | {b['path_prec']} | {o1['avg_mfe']} | {o1['avg_pts']} |"
        )

    lines += ["", "## Best", ""]
    if pick:
        o1 = pick["one"]
        lines += [
            f"**`{pick['name']}`** · **{pick['verdict']}**",
            f"- T15 **{o1['prec']}%** · TRAIN {o1['train_prec']}% · OOS {o1['oos_prec']}% · n={o1['n']}",
            f"- path **{pick['path_prec']}%** · MFE **{o1['avg_mfe']}**",
            "",
            "```",
            "WATCH : OR high / OR low (after 09:30)",
            "STACK : Swing cluster sitting on that OR line",
            "EMA   : price already above EMA20 (BUY) / below (SELL)",
            "ENTRY : close crosses OR line in that direction",
            "QUALITY: held + HTF15 + ATR≥10 when aiming for T15 accuracy",
            "EXIT  : EMA34 trail · T15",
            "```",
            "",
            "| Day | HM | Side | Entry | mode | ATR | T15 | MFE |",
            "|---|---|---|---:|---|---:|---|---:|",
        ]
        for x in pick["samples"]:
            lines.append(
                f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | "
                f"{x['mode']} | {x['atr']} | {x['t15_win']} | {x['mfe']} |"
            )
    lines += [
        "",
        "## vs what you see",
        "",
        "- The **visual** (OR + Swing + EMA direction) is real and common on 1m Desk.",
        "- Short bounce (0.35×ATR path) often looks right — that is why it *feels* accurate.",
        "- For **Oracle T15** (EMA34 trail +15), raw visual alone is not enough; need held/HTF/ATR.",
        "",
        f"_Generated in {time.time()-t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({
        "books": [{"name": b["name"], "verdict": b["verdict"], "one": b["one"], "path": b["path_prec"]} for b in ranked],
        "best": {"name": pick["name"], "one": pick["one"]} if pick else None,
    }, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    if pick:
        print(f"BEST: {pick['name']} T15={pick['one']['prec']}%", flush=True)
    print(f"done in {time.time()-t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
