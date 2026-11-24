"""Deep entry-intelligence research — NIFTY 1m last 2 months.

Goal: find WHEN entries are accurate (favour first), NOT exits.
No SL / T1 scoring as primary — path favour + MFE quality only.

Indications studied:
  - Support / resistance (swing pivots, session, prior day, VWAP)
  - Liquidity proxies (equal highs/lows, session extremes, wick sweeps)
  - Buyer/seller control (close location, DI, VWAP, run bars)
  - Regime: compress · trend · hold-break attempt · failed break · flip

  python -u prod_live/tests/builders/_diag_scalp_entry_intel_2m.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
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
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers, enrich_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ENTRY_INTEL_2M.md"
REPORT_JSON = OUT / "NIFTY_1M_ENTRY_INTEL_2M.json"

PIVOT_L = 3
LOOK = 150
MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
EQ_TOL = 3.0  # pts — equal high/low liquidity pool
FAV_PTS = 8.0
ADV_PTS = 5.0


def in_session(e) -> bool:
    return MINS_LO <= int(e["mins"]) < MINS_HI


def swings(h, l, i, L=PIVOT_L, look=LOOK):
    lo = max(L, i - look)
    hi_i, lo_i = [], []
    for j in range(lo, i - L):
        if h[j] >= np.max(h[j - L : j + L + 1]) - 1e-9:
            hi_i.append(j)
        if l[j] <= np.min(l[j - L : j + L + 1]) + 1e-9:
            lo_i.append(j)
    return hi_i, lo_i


def nearest_above(levels, px):
    above = [x for x in levels if x > px + 0.05]
    return min(above) if above else None


def nearest_below(levels, px):
    below = [x for x in levels if x < px - 0.05]
    return max(below) if below else None


def cluster_levels(vals, tol=EQ_TOL):
    if not vals:
        return []
    vals = sorted(float(v) for v in vals)
    clusters = []
    cur = [vals[0]]
    for v in vals[1:]:
        if abs(v - cur[-1]) <= tol:
            cur.append(v)
        else:
            clusters.append(cur)
            cur = [v]
    clusters.append(cur)
    out = []
    for c in clusters:
        out.append({"px": round(float(np.mean(c)), 2), "n": len(c), "span": round(c[-1] - c[0], 2)})
    return out


def enrich_sr_liq(events, df):
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    idx = df.index
    day = df["day"].astype(str).values if "day" in df.columns else np.array([str(ts.date()) for ts in idx])
    vwap = df["vwap"].astype(float).values if "vwap" in df.columns else c.copy()
    atr = df["atr14"].astype(float).values if "atr14" in df.columns else np.full(len(c), 8.0)

    # prior day H/L/C
    by_day = {}
    for d in sorted(set(day)):
        m = day == d
        by_day[d] = {
            "o": float(o[m][0]),
            "h": float(np.max(h[m])),
            "l": float(np.min(l[m])),
            "c": float(c[m][-1]),
        }
    days = sorted(by_day.keys())
    prior = {}
    for k, d in enumerate(days):
        prior[d] = by_day[days[k - 1]] if k else None

    for e in events:
        i = int(e["full_i"])
        entry = float(e["entry"])
        side = e["decision"]
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        d = e["day"]
        hi_i, lo_i = swings(h, l, i)
        swing_hi = [float(h[j]) for j in hi_i]
        swing_lo = [float(l[j]) for j in lo_i]
        levels = list(swing_hi) + list(swing_lo)
        pd_ = prior.get(d)
        if pd_:
            levels += [pd_["h"], pd_["l"], pd_["c"], pd_["o"]]
        # session so far
        sess = np.where(day == d)[0]
        sess = sess[sess < i]
        if len(sess):
            sh, sl = float(np.max(h[sess])), float(np.min(l[sess]))
            so = float(o[sess[0]])
            levels += [sh, sl, so]
            e["sess_high"] = round(sh, 2)
            e["sess_low"] = round(sl, 2)
            e["day_open"] = round(so, 2)
            e["dist_sess_high"] = round(sh - entry, 2)
            e["dist_sess_low"] = round(entry - sl, 2)
        else:
            e["sess_high"] = e["sess_low"] = e["day_open"] = None
            e["dist_sess_high"] = e["dist_sess_low"] = None

        vw = float(vwap[i]) if np.isfinite(vwap[i]) else entry
        levels.append(vw)
        uniq = sorted({round(x, 1) for x in levels if np.isfinite(x)})
        resist = nearest_above(uniq, entry)
        support = nearest_below(uniq, entry)
        e["sr_resist"] = None if resist is None else round(resist, 2)
        e["sr_support"] = None if support is None else round(support, 2)
        e["room_up"] = 999.0 if resist is None else round(resist - entry, 2)
        e["room_dn"] = 999.0 if support is None else round(entry - support, 2)
        e["room_fav"] = e["room_up"] if side == "BUY" else e["room_dn"]
        e["room_against"] = e["room_dn"] if side == "BUY" else e["room_up"]
        e["vwap"] = round(vw, 2)
        e["vwap_side"] = "above" if entry >= vw else "below"
        e["atr"] = round(a, 2)

        # liquidity pools: clustered equal highs/lows
        hi_cl = cluster_levels(swing_hi)
        lo_cl = cluster_levels(swing_lo)
        e["liq_eq_highs"] = [x for x in hi_cl if x["n"] >= 2]
        e["liq_eq_lows"] = [x for x in lo_cl if x["n"] >= 2]
        # nearest liquidity pool above/below
        liq_above = [x for x in e["liq_eq_highs"] if x["px"] > entry]
        liq_below = [x for x in e["liq_eq_lows"] if x["px"] < entry]
        e["liq_above"] = min(liq_above, key=lambda x: x["px"]) if liq_above else None
        e["liq_below"] = max(liq_below, key=lambda x: x["px"]) if liq_below else None
        e["liq_fav"] = e["liq_above"] if side == "BUY" else e["liq_below"]
        e["liq_against"] = e["liq_below"] if side == "BUY" else e["liq_above"]
        dist_liq_fav = None
        if e["liq_fav"]:
            dist_liq_fav = abs(e["liq_fav"]["px"] - entry)
        e["dist_liq_fav"] = None if dist_liq_fav is None else round(dist_liq_fav, 2)

        # wick sweep at entry bar (liquidity grab)
        rng = max(float(h[i]) - float(l[i]), 0.05)
        upper = float(h[i]) - max(float(o[i]), float(c[i]))
        lower = min(float(o[i]), float(c[i])) - float(l[i])
        e["sweep_up"] = upper / rng >= 0.45 and float(c[i]) < float(o[i])  # reject high
        e["sweep_dn"] = lower / rng >= 0.45 and float(c[i]) > float(o[i])  # reject low
        e["sweep_with"] = (side == "BUY" and e["sweep_dn"]) or (side == "SELL" and e["sweep_up"])
        e["sweep_against"] = (side == "BUY" and e["sweep_up"]) or (side == "SELL" and e["sweep_dn"])

        # near session extreme = liquidity magnet
        e["near_sess_high"] = e["dist_sess_high"] is not None and e["dist_sess_high"] <= max(8.0, 1.0 * a)
        e["near_sess_low"] = e["dist_sess_low"] is not None and e["dist_sess_low"] <= max(8.0, 1.0 * a)
        e["at_liq_magnet"] = (
            (side == "BUY" and e["near_sess_low"]) or (side == "SELL" and e["near_sess_high"])
        )
        e["into_sess_extreme"] = (
            (side == "BUY" and e["near_sess_high"]) or (side == "SELL" and e["near_sess_low"])
        )


def enrich_control_regime(events, df):
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    pdi = df["plus_di"].astype(float).values if "plus_di" in df.columns else np.zeros(len(c))
    mdi = df["minus_di"].astype(float).values if "minus_di" in df.columns else np.zeros(len(c))
    ema34 = df["ema34"].astype(float).values if "ema34" in df.columns else c.copy()
    atr = df["atr14"].astype(float).values if "atr14" in df.columns else np.full(len(c), 8.0)

    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        # buyer/seller control on signal bar
        rng = max(float(h[i]) - float(l[i]), 0.05)
        loc = (float(c[i]) - float(l[i])) / rng  # 1=close at high
        e["close_loc"] = round(loc, 2)
        e["buyer_bar"] = loc >= 0.65 and float(c[i]) > float(o[i])
        e["seller_bar"] = loc <= 0.35 and float(c[i]) < float(o[i])
        e["control_with"] = (side == "BUY" and e["buyer_bar"]) or (side == "SELL" and e["seller_bar"])
        e["control_against"] = (side == "BUY" and e["seller_bar"]) or (side == "SELL" and e["buyer_bar"])
        e["di_spread"] = round(float(pdi[i]) - float(mdi[i]), 1)
        e["di_strong"] = abs(e["di_spread"]) >= 5

        # recent 10-bar momentum / compression
        j0 = max(0, i - 10)
        window = c[j0 : i + 1]
        hw, lw = float(np.max(h[j0 : i + 1])), float(np.min(l[j0 : i + 1]))
        span = hw - lw
        e["pre10_span"] = round(span, 2)
        e["compress"] = span <= 1.2 * a
        e["expand"] = span >= 2.5 * a
        chg = float(c[i]) - float(c[j0])
        e["pre10_chg"] = round(chg, 2)
        e["mom_with"] = (side == "BUY" and chg > 0.3 * a) or (side == "SELL" and chg < -0.3 * a)
        e["mom_against"] = (side == "BUY" and chg < -0.3 * a) or (side == "SELL" and chg > 0.3 * a)

        # hold-break: price pressed against opposing S/R then closed with
        room_ag = float(e.get("room_against") or 999)
        room_fv = float(e.get("room_fav") or 999)
        e["hold_break_setup"] = bool(
            room_ag <= 1.0 * a and room_fv >= 1.0 * a and e["control_with"] and e.get("sweep_with")
        )
        e["break_attempt"] = bool(room_fv <= 0.8 * a and e["mom_with"])  # pushing into fav wall
        e["failed_break_risk"] = bool(e["into_sess_extreme"] and e["break_attempt"])

        # flip: prior 10 against, now control with
        e["flip_setup"] = bool(e["mom_against"] and e["control_with"] and e.get("sweep_with"))

        # trend continuation: mom with + DI with + above/below ema
        above = float(c[i]) >= float(ema34[i]) if np.isfinite(ema34[i]) else True
        e["trend_cont"] = bool(
            e["mom_with"]
            and ((side == "BUY" and above and e["di_spread"] > 0) or (side == "SELL" and (not above) and e["di_spread"] < 0))
            and not e["compress"]
        )

        # dynamic regime tag
        if e["flip_setup"]:
            e["regime"] = "flip"
        elif e["hold_break_setup"]:
            e["regime"] = "hold_break"
        elif e["failed_break_risk"]:
            e["regime"] = "failed_break_risk"
        elif e["trend_cont"]:
            e["regime"] = "trend"
        elif e["compress"]:
            e["regime"] = "compress"
        elif e["break_attempt"]:
            e["regime"] = "break_attempt"
        else:
            e["regime"] = "mixed"


def score_entry_quality(events, df):
    """Favour-first / MFE quality — NO SL or T1 exits."""
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        entry = float(c[i])
        end = min(len(c) - 1, i + 60)
        fav_first = None
        mfe = 0.0
        mae = 0.0
        t_fav8 = None
        t_adv5 = None
        for j in range(i + 1, end + 1):
            if side == "BUY":
                up = float(h[j]) - entry
                dn = entry - float(l[j])
            else:
                up = entry - float(l[j])
                dn = float(h[j]) - entry
            mfe = max(mfe, up)
            mae = max(mae, dn)
            if t_fav8 is None and up >= FAV_PTS:
                t_fav8 = j - i
            if t_adv5 is None and dn >= ADV_PTS:
                t_adv5 = j - i
            if fav_first is None:
                if up >= FAV_PTS:
                    fav_first = True
                elif dn >= ADV_PTS:
                    fav_first = False
        # closes
        def fwd(n):
            j = min(len(c) - 1, i + n)
            px = float(c[j])
            return (px - entry) if side == "BUY" else (entry - px)

        e["mfe60"] = round(mfe, 2)
        e["mae60"] = round(mae, 2)
        e["fav_first"] = fav_first  # None = neither threshold hit
        # Multiple accuracy lenses (still NO SL/T exits):
        e["entry_ok"] = bool(fav_first is True)  # strict: +8 before -5
        e["entry_bad"] = bool(fav_first is False)
        e["ok_edge"] = bool(mfe >= 12 and mfe > mae)  # got ≥12 favour and won the path race
        e["ok_dom"] = bool(mfe >= 12 and mfe >= 1.5 * max(mae, 1.0))  # dominated adverse
        e["ok_fwd"] = bool(fwd(10) > 0 and mfe >= 8)  # still green after 10m + had favour
        e["t_fav8"] = t_fav8
        e["t_adv5"] = t_adv5
        e["fwd5"] = round(fwd(5), 2)
        e["fwd10"] = round(fwd(10), 2)
        e["fwd20"] = round(fwd(20), 2)
        e["mfe_ge8"] = mfe >= 8
        e["mfe_ge12"] = mfe >= 12
        e["mfe_ge15"] = mfe >= 15
        e["edge"] = round(mfe - mae, 2)


def summarize(rows, label):
    n = len(rows)
    empty = {
        "label": label,
        "n": 0,
        "decided": 0,
        "ok": 0,
        "bad": 0,
        "acc": None,
        "acc_edge": None,
        "acc_dom": None,
        "acc_fwd": None,
        "mfe8_pct": None,
        "mfe12_pct": None,
        "mfe15_pct": None,
        "avg_mfe": None,
        "avg_mae": None,
        "avg_edge": None,
        "avg_fwd10": None,
        "median_t_fav8": None,
    }
    if not n:
        return empty
    ok = [e for e in rows if e.get("entry_ok")]
    bad = [e for e in rows if e.get("entry_bad")]
    decided = [e for e in rows if e.get("fav_first") is not None]
    acc = 100.0 * len(ok) / len(decided) if decided else None

    def pct(key):
        return round(100.0 * sum(1 for e in rows if e.get(key)) / n, 2)

    return {
        "label": label,
        "n": n,
        "decided": len(decided),
        "ok": len(ok),
        "bad": len(bad),
        "acc": None if acc is None else round(acc, 2),
        "acc_edge": pct("ok_edge"),
        "acc_dom": pct("ok_dom"),
        "acc_fwd": pct("ok_fwd"),
        "mfe8_pct": pct("mfe_ge8"),
        "mfe12_pct": pct("mfe_ge12"),
        "mfe15_pct": pct("mfe_ge15"),
        "avg_mfe": round(float(np.mean([e["mfe60"] for e in rows])), 2),
        "avg_mae": round(float(np.mean([e["mae60"] for e in rows])), 2),
        "avg_edge": round(float(np.mean([e["edge"] for e in rows])), 2),
        "avg_fwd10": round(float(np.mean([e["fwd10"] for e in rows])), 2),
        "median_t_fav8": None
        if not ok
        else int(np.median([e["t_fav8"] for e in ok if e.get("t_fav8") is not None] or [0])),
    }


def gate_table(pool):
    gates = [
        ("ALL textbook sess", lambda e: True),
        ("HELD", held_gate),
        ("HELD + control_with", lambda e: held_gate(e) and e.get("control_with")),
        ("HELD + sweep_with", lambda e: held_gate(e) and e.get("sweep_with")),
        ("HELD + control + sweep", lambda e: held_gate(e) and e.get("control_with") and e.get("sweep_with")),
        ("HELD + room_fav≥ATR", lambda e: held_gate(e) and e.get("room_fav", 0) >= e.get("atr", 8)),
        ("HELD + room_fav≥1.5ATR", lambda e: held_gate(e) and e.get("room_fav", 0) >= 1.5 * e.get("atr", 8)),
        ("HELD + !into_sess_extreme", lambda e: held_gate(e) and not e.get("into_sess_extreme")),
        ("HELD + at_liq_magnet", lambda e: held_gate(e) and e.get("at_liq_magnet")),
        ("HELD + liq_fav within 25", lambda e: held_gate(e) and e.get("dist_liq_fav") is not None and e["dist_liq_fav"] <= 25),
        ("HELD + trend", lambda e: held_gate(e) and e.get("regime") == "trend"),
        ("HELD + hold_break", lambda e: held_gate(e) and e.get("regime") == "hold_break"),
        ("HELD + flip", lambda e: held_gate(e) and e.get("regime") == "flip"),
        ("HELD + !failed_break_risk", lambda e: held_gate(e) and e.get("regime") != "failed_break_risk"),
        ("HELD + !compress", lambda e: held_gate(e) and not e.get("compress")),
        ("HELD + di_strong + control", lambda e: held_gate(e) and e.get("di_strong") and e.get("control_with")),
        (
            "INTEL: HELD+control+sweep+room≥ATR+!into_extreme",
            lambda e: held_gate(e)
            and e.get("control_with")
            and e.get("sweep_with")
            and e.get("room_fav", 0) >= e.get("atr", 8)
            and not e.get("into_sess_extreme"),
        ),
        (
            "INTEL2: HELD+control+!failed_break+room≥ATR",
            lambda e: held_gate(e)
            and e.get("control_with")
            and e.get("regime") != "failed_break_risk"
            and e.get("room_fav", 0) >= e.get("atr", 8),
        ),
        (
            "INTEL3: HELD+(hold_break|flip|trend)+control",
            lambda e: held_gate(e)
            and e.get("control_with")
            and e.get("regime") in ("hold_break", "flip", "trend"),
        ),
        (
            "INTEL4: HELD+control+sweep+(hold_break|flip|trend)",
            lambda e: held_gate(e)
            and e.get("control_with")
            and e.get("sweep_with")
            and e.get("regime") in ("hold_break", "flip", "trend"),
        ),
        (
            "INTEL5: HELD+at_liq+control+room≥ATR",
            lambda e: held_gate(e)
            and e.get("at_liq_magnet")
            and e.get("control_with")
            and e.get("room_fav", 0) >= e.get("atr", 8),
        ),
        (
            "SETUP: hold_break + control + room_against≤ATR",
            lambda e: held_gate(e)
            and e.get("regime") == "hold_break"
            and e.get("control_with")
            and float(e.get("room_against") or 999) <= float(e.get("atr") or 8),
        ),
        (
            "SETUP: hold_break + sweep + !into_extreme",
            lambda e: held_gate(e)
            and e.get("regime") == "hold_break"
            and e.get("sweep_with")
            and not e.get("into_sess_extreme"),
        ),
        (
            "SETUP: hold_break|flip + control + sweep + !into_extreme",
            lambda e: held_gate(e)
            and e.get("regime") in ("hold_break", "flip")
            and e.get("control_with")
            and e.get("sweep_with")
            and not e.get("into_sess_extreme"),
        ),
        (
            "SETUP: trend + control + sweep + room≥ATR + !into_extreme",
            lambda e: held_gate(e)
            and e.get("regime") == "trend"
            and e.get("control_with")
            and e.get("sweep_with")
            and float(e.get("room_fav") or 0) >= float(e.get("atr") or 8)
            and not e.get("into_sess_extreme"),
        ),
    ]
    rows = []
    for name, fn in gates:
        sub = [e for e in pool if fn(e)]
        rows.append(summarize(sub, name))
    # Rank by dominated-path accuracy, then edge accuracy, then n
    rows.sort(
        key=lambda r: (
            -(r.get("acc_dom") if r.get("acc_dom") is not None else -1),
            -(r.get("acc_edge") if r.get("acc_edge") is not None else -1),
            -(r.get("avg_edge") if r.get("avg_edge") is not None else -999),
            -int(r.get("n") or 0),
        )
    )
    return rows


def one_per_day(rows):
    by = defaultdict(list)
    for e in rows:
        by[e["day"]].append(e)
    out = []
    for d in sorted(by.keys()):
        # earliest HELD-quality if any else earliest
        day_rows = sorted(by[d], key=lambda x: x["mins"])
        pick = next((e for e in day_rows if held_gate(e)), None)
        out.append(pick or day_rows[0])
    return out


def md_table(rows):
    lines = [
        "| Gate | n | Dom% | Edge% | Fav1st% | Fwd10% | MFE≥12% | avg MFE | avg MAE | edge |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        if not r["n"]:
            continue
        lines.append(
            f"| `{r['label']}` | {r['n']} | **{r.get('acc_dom')}** | {r.get('acc_edge')} | {r.get('acc')} | "
            f"{r.get('acc_fwd')} | {r['mfe12_pct']} | {r['avg_mfe']} | {r['avg_mae']} | {r['avg_edge']} |"
        )
    return lines


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("ENTRY INTEL · NIFTY 1m last 2 months", flush=True)

    raw = base.load_existing_1m()
    if raw is None or raw.empty:
        print("no bars", flush=True)
        return 1
    hi = raw.index.max()
    lo = hi - pd.Timedelta(days=65)
    raw = raw[raw.index >= lo]
    print(f"bars={len(raw)}  {raw.index.min().date()} → {raw.index.max().date()}", flush=True)

    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    day_lo = str(df.index.min().date())
    day_hi = str(df.index.max().date())
    print("collect events…", flush=True)
    events = scalp.collect_scalp_events(df, day_lo, day_hi)
    print(f"events={len(events)}", flush=True)
    enrich_ma_layers(events, df)
    enrich_ind(events, df)
    enrich_sr_liq(events, df)
    enrich_control_regime(events, df)
    score_entry_quality(events, df)

    pool = [e for e in events if in_session(e)]
    days = sorted({e["day"] for e in pool})
    # last ~45 calendar trading days ≈ 2m
    keep = set(days[-45:]) if len(days) > 45 else set(days)
    pool = [e for e in pool if e["day"] in keep]
    days = sorted(keep)
    print(f"session pool={len(pool)} days={len(days)} {days[0]}→{days[-1]}", flush=True)

    # map levels for last 1 month vs 2 month context
    last_1m_days = set(days[-22:]) if len(days) >= 22 else set(days)
    pool_1m = [e for e in pool if e["day"] in last_1m_days]
    pool_2m = pool

    # daily S/R / liquidity map from last day bars
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    day_arr = df["day"].astype(str).values
    map_days = days[-22:]
    day_maps = []
    for d in map_days:
        m = np.where(day_arr == d)[0]
        if len(m) < 30:
            continue
        sh, sl, so, sc = float(np.max(h[m])), float(np.min(l[m])), float(df["Open"].iloc[m[0]]), float(c[m[-1]])
        # pivots inside day
        hi_i, lo_i = [], []
        for j in range(m[0] + PIVOT_L, m[-1] - PIVOT_L):
            if h[j] >= np.max(h[j - PIVOT_L : j + PIVOT_L + 1]) - 1e-9:
                hi_i.append(float(h[j]))
            if l[j] <= np.min(l[j - PIVOT_L : j + PIVOT_L + 1]) + 1e-9:
                lo_i.append(float(l[j]))
        day_maps.append(
            {
                "day": d,
                "open": round(so, 2),
                "high": round(sh, 2),
                "low": round(sl, 2),
                "close": round(sc, 2),
                "range": round(sh - sl, 2),
                "eq_highs": cluster_levels(hi_i),
                "eq_lows": cluster_levels(lo_i),
            }
        )

    # regime mix
    reg = Counter(e.get("regime") for e in pool_2m)
    held_pool = [e for e in pool_2m if held_gate(e)]
    reg_held = Counter(e.get("regime") for e in held_pool)

    # accuracy by regime (HELD)
    by_reg = []
    for rname in ("trend", "hold_break", "flip", "compress", "break_attempt", "failed_break_risk", "mixed"):
        sub = [e for e in held_pool if e.get("regime") == rname]
        by_reg.append(summarize(sub, f"HELD · {rname}"))

    gates_2m = gate_table(pool_2m)
    gates_1m = gate_table(pool_1m)
    # 1 call/day on best INTEL gate candidates
    intel_fn = lambda e: (
        held_gate(e)
        and e.get("control_with")
        and e.get("sweep_with")
        and e.get("regime") in ("hold_break", "flip", "trend")
    )
    intel_rows = [e for e in pool_2m if intel_fn(e)]
    intel_1cpd = one_per_day(intel_rows)
    held_1cpd = one_per_day(held_pool)

    # recent map summary: most touched liquidity clusters last 1m
    touch_hi = Counter()
    touch_lo = Counter()
    for dm in day_maps:
        for x in dm["eq_highs"]:
            if x["n"] >= 2:
                touch_hi[round(x["px"] / 5) * 5] += x["n"]
        for x in dm["eq_lows"]:
            if x["n"] >= 2:
                touch_lo[round(x["px"] / 5) * 5] += x["n"]

    top_res = touch_hi.most_common(8)
    top_sup = touch_lo.most_common(8)

    best = gates_2m[0] if gates_2m else {}
    lines = [
        "# NIFTY 1m — Entry Intelligence (last 2 months)",
        "",
        f"Window: **{days[0]} → {days[-1]}** · session 09:30–14:30 · textbook events scored by **favour-first** (not SL/T).",
        "",
        "## Accuracy definitions (entry only — no SL/T)",
        "",
        f"- **Fav1st**: +{FAV_PTS:.0f} favour before -{ADV_PTS:.0f} adverse (strict timing).",
        "- **Edge%**: MFE≥12 and MFE>MAE (path eventually favour-dominant).",
        "- **Dom%**: MFE≥12 and MFE≥1.5×MAE (strong dominance — primary rank).",
        "- **Fwd10%**: close +ve after 10 bars and MFE≥8.",
        "",
        "## Market structure map (last ~1 month)",
        "",
        "Liquidity proxies = **equal highs/lows** (stop pools) + session extremes. Volume unavailable on index CSV → structure used.",
        "",
        "### Most-visited resistance liquidity (equal highs, rounded 5)",
        "",
    ]
    for px, n in top_res:
        lines.append(f"- **{px:.0f}** · touches/weight {n}")
    lines += ["", "### Most-visited support liquidity (equal lows, rounded 5)", ""]
    for px, n in top_sup:
        lines.append(f"- **{px:.0f}** · touches/weight {n}")

    lines += [
        "",
        "### Latest session levels (last 5 mapped days)",
        "",
        "| Day | Open | High | Low | Close | Range |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for dm in day_maps[-5:]:
        lines.append(
            f"| {dm['day']} | {dm['open']} | {dm['high']} | {dm['low']} | {dm['close']} | {dm['range']} |"
        )

    lines += [
        "",
        "## Regime mix (all textbook · 2m)",
        "",
        "```",
        str(dict(reg)),
        "```",
        "",
        "### HELD accuracy by regime (favour-first)",
        "",
    ]
    lines += md_table(by_reg)

    lines += [
        "",
        "## Gate sweep — last 2 months (entry accuracy)",
        "",
    ]
    lines += md_table(gates_2m)

    lines += [
        "",
        "## Gate sweep — last ~1 month",
        "",
    ]
    lines += md_table(gates_1m)

    lines += [
        "",
        "## 1-call-per-day books",
        "",
    ]
    lines += md_table(
        [
            summarize(held_1cpd, "HELD 1cpd"),
            summarize(intel_1cpd, "INTEL4 1cpd (control+sweep+regime)"),
        ]
    )

    # example accurate INTEL calls
    good = [e for e in intel_rows if e.get("entry_ok")][:12]
    bad = [e for e in intel_rows if e.get("entry_bad")][:8]
    lines += [
        "",
        "## Sample accurate INTEL entries",
        "",
        "| Day | HM | Side | Pattern | Regime | Entry | room_fav | MFE | MAE | fwd10 |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for e in good:
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | {e.get('regime')} | "
            f"{e['entry']} | {e.get('room_fav')} | {e['mfe60']} | {e['mae60']} | {e['fwd10']} |"
        )
    lines += [
        "",
        "## Sample failed INTEL entries (learn)",
        "",
        "| Day | HM | Side | Pattern | Regime | Entry | into_extreme | MFE | MAE |",
        "|---|---|---|---|---|---:|---|---:|---:|",
    ]
    for e in bad:
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | {e.get('regime')} | "
            f"{e['entry']} | {e.get('into_sess_extreme')} | {e['mfe60']} | {e['mae60']} |"
        )

    lines += [
        "",
        "## Locked entry logic (proposed — no SL/T yet)",
        "",
        "Only fire when **setup forms**. Dynamic regime decides style:",
        "",
        "1. **Base gates (always):** textbook candle · DI_ok · hard34 · VWAP_with · session 09:30–14:30",
        "2. **Control:** signal bar must show **buyer_bar** (BUY) or **seller_bar** (SELL) — close in favour third",
        "3. **Liquidity / structure:**",
        "   - Prefer **room_fav ≥ 1×ATR** (space to opposing S/R)",
        "   - Prefer **not into session extreme** in trade direction (avoid buying highs / selling lows)",
        "   - Bonus: **at_liq_magnet** (BUY near sess low / SELL near sess high) + sweep_with (grab then reverse)",
        "4. **Regime router:**",
        "   - `hold_break` — pressed against backing S/R, sweep_with, control_with → take",
        "   - `flip` — prior momentum against, now control+sweep → take",
        "   - `trend` — mom_with + DI aligned + not compress → take",
        "   - `failed_break_risk` / naked `break_attempt` into extreme → **skip**",
        "   - `compress` alone → **skip** (wait for expansion / control)",
        "5. **1 call/day** earliest that passes INTEL4 (or wait — no force)",
        "",
        f"Best gate this window (by Dom%): **{best.get('label')}** · Dom **{best.get('acc_dom')}%** · "
        f"Edge **{best.get('acc_edge')}%** · n={best.get('n')} · path edge={best.get('avg_edge')}",
        "",
        f"Elapsed {time.time() - t0:.0f}s",
        "",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {
        "day_lo": days[0],
        "day_hi": days[-1],
        "n_events": len(pool_2m),
        "regime_all": dict(reg),
        "regime_held": dict(reg_held),
        "gates_2m": gates_2m,
        "gates_1m": gates_1m,
        "held_1cpd": summarize(held_1cpd, "HELD 1cpd"),
        "intel_1cpd": summarize(intel_1cpd, "INTEL4 1cpd"),
        "top_resistance_liq": top_res,
        "top_support_liq": top_sup,
        "day_maps_tail": day_maps[-10:],
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    print(f"best {best.get('label')} acc={best.get('acc')} n={best.get('n')}", flush=True)
    print(f"INTEL4 1cpd {summarize(intel_1cpd, 'x')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
