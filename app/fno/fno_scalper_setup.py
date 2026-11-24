"""Scalper setup router — Tier A/B + proven run_ignition_100 gate.

Tier A (primary): HELD + hold_break (backed S/R + control + sweep-with)
Tier B (secondary): HELD + control + sweep, preferably flip/hold_break, never into session extreme

run_ignition_100 (proven ≥25pt research):
  bull/bear run2|3 → entry at ignition close
  + control_with + clear_path + sr_bounce + ignition body ≥ 1×ATR
  Outputs: decision (BUY/SELL) + ignition_entry only

Live / HELD chart calls fire when a tier is assigned, or when IGN100 mode is selected.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

PIVOT_L = 3
LOOK = 150
EQ_TOL = 3.0
MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30


def in_session(e: dict) -> bool:
    return MINS_LO <= int(e.get("mins") or 0) < MINS_HI


def held_gate(e: dict) -> bool:
    return bool(e.get("di_ok") and e.get("gate_hard34") and e.get("vwap_with"))


def _swings(h, l, i, L=PIVOT_L, look=LOOK):
    lo = max(L, i - look)
    hi_i, lo_i = [], []
    for j in range(lo, i - L):
        if h[j] >= np.max(h[j - L : j + L + 1]) - 1e-9:
            hi_i.append(j)
        if l[j] <= np.min(l[j - L : j + L + 1]) + 1e-9:
            lo_i.append(j)
    return hi_i, lo_i


def _nearest_above(levels, px):
    above = [x for x in levels if x > px + 0.05]
    return min(above) if above else None


def _nearest_below(levels, px):
    below = [x for x in levels if x < px - 0.05]
    return max(below) if below else None


def _cluster_levels(vals, tol=EQ_TOL):
    if not vals:
        return []
    vals = sorted(float(v) for v in vals)
    clusters, cur = [], [vals[0]]
    for v in vals[1:]:
        if abs(v - cur[-1]) <= tol:
            cur.append(v)
        else:
            clusters.append(cur)
            cur = [v]
    clusters.append(cur)
    return [
        {"px": round(float(np.mean(c)), 2), "n": len(c), "span": round(c[-1] - c[0], 2)}
        for c in clusters
    ]


def enrich_sr_liq(events: List[dict], df: pd.DataFrame) -> None:
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    day = df["day"].astype(str).values if "day" in df.columns else np.array(
        [str(ts.date()) for ts in df.index]
    )
    vwap = df["vwap"].astype(float).values if "vwap" in df.columns else c.copy()
    atr = df["atr14"].astype(float).values if "atr14" in df.columns else np.full(len(c), 8.0)

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
    prior = {d: (by_day[days[k - 1]] if k else None) for k, d in enumerate(days)}

    for e in events:
        i = int(e["full_i"])
        entry = float(e["entry"])
        side = e["decision"]
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        d = e["day"]
        hi_i, lo_i = _swings(h, l, i)
        swing_hi = [float(h[j]) for j in hi_i]
        swing_lo = [float(l[j]) for j in lo_i]
        levels = list(swing_hi) + list(swing_lo)
        pd_ = prior.get(d)
        if pd_:
            levels += [pd_["h"], pd_["l"], pd_["c"], pd_["o"]]
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
        resist = _nearest_above(uniq, entry)
        support = _nearest_below(uniq, entry)
        e["sr_resist"] = None if resist is None else round(resist, 2)
        e["sr_support"] = None if support is None else round(support, 2)
        e["room_up"] = 999.0 if resist is None else round(resist - entry, 2)
        e["room_dn"] = 999.0 if support is None else round(entry - support, 2)
        e["room_fav"] = e["room_up"] if side == "BUY" else e["room_dn"]
        e["room_against"] = e["room_dn"] if side == "BUY" else e["room_up"]
        e["vwap_px"] = round(vw, 2)
        e["atr"] = round(a, 2)

        # Scale equal-high/low cluster tolerance with ATR (options / equities)
        tol = float(max(EQ_TOL, round(a * 0.15, 2)))
        hi_cl = _cluster_levels(swing_hi, tol=tol)
        lo_cl = _cluster_levels(swing_lo, tol=tol)
        e["liq_eq_highs"] = [x for x in hi_cl if x["n"] >= 2]
        e["liq_eq_lows"] = [x for x in lo_cl if x["n"] >= 2]
        liq_above = [x for x in e["liq_eq_highs"] if x["px"] > entry]
        liq_below = [x for x in e["liq_eq_lows"] if x["px"] < entry]
        e["liq_above"] = min(liq_above, key=lambda x: x["px"]) if liq_above else None
        e["liq_below"] = max(liq_below, key=lambda x: x["px"]) if liq_below else None

        rng = max(float(h[i]) - float(l[i]), 0.05)
        upper = float(h[i]) - max(float(o[i]), float(c[i]))
        lower = min(float(o[i]), float(c[i])) - float(l[i])
        e["sweep_up"] = bool(upper / rng >= 0.45 and float(c[i]) < float(o[i]))
        e["sweep_dn"] = bool(lower / rng >= 0.45 and float(c[i]) > float(o[i]))
        e["sweep_with"] = (side == "BUY" and e["sweep_dn"]) or (side == "SELL" and e["sweep_up"])
        e["sweep_against"] = (side == "BUY" and e["sweep_up"]) or (side == "SELL" and e["sweep_dn"])

        e["near_sess_high"] = e["dist_sess_high"] is not None and e["dist_sess_high"] <= max(8.0, a)
        e["near_sess_low"] = e["dist_sess_low"] is not None and e["dist_sess_low"] <= max(8.0, a)
        e["at_liq_magnet"] = (side == "BUY" and e["near_sess_low"]) or (
            side == "SELL" and e["near_sess_high"]
        )
        e["into_sess_extreme"] = (side == "BUY" and e["near_sess_high"]) or (
            side == "SELL" and e["near_sess_low"]
        )


def enrich_control_regime(events: List[dict], df: pd.DataFrame) -> None:
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
        rng = max(float(h[i]) - float(l[i]), 0.05)
        loc = (float(c[i]) - float(l[i])) / rng
        e["close_loc"] = round(loc, 2)
        e["buyer_bar"] = bool(loc >= 0.65 and float(c[i]) > float(o[i]))
        e["seller_bar"] = bool(loc <= 0.35 and float(c[i]) < float(o[i]))
        e["control_with"] = (side == "BUY" and e["buyer_bar"]) or (side == "SELL" and e["seller_bar"])
        e["control_against"] = (side == "BUY" and e["seller_bar"]) or (
            side == "SELL" and e["buyer_bar"]
        )
        e["di_spread"] = round(float(pdi[i]) - float(mdi[i]), 1)
        e["di_strong"] = abs(e["di_spread"]) >= 5

        j0 = max(0, i - 10)
        hw, lw = float(np.max(h[j0 : i + 1])), float(np.min(l[j0 : i + 1]))
        span = hw - lw
        e["pre10_span"] = round(span, 2)
        e["compress"] = span <= 1.2 * a
        e["expand"] = span >= 2.5 * a
        chg = float(c[i]) - float(c[j0])
        e["pre10_chg"] = round(chg, 2)
        e["mom_with"] = (side == "BUY" and chg > 0.3 * a) or (side == "SELL" and chg < -0.3 * a)
        e["mom_against"] = (side == "BUY" and chg < -0.3 * a) or (side == "SELL" and chg > 0.3 * a)

        room_ag = float(e.get("room_against") or 999)
        room_fv = float(e.get("room_fav") or 999)
        e["hold_break_setup"] = bool(
            room_ag <= 1.0 * a and room_fv >= 1.0 * a and e["control_with"] and e.get("sweep_with")
        )
        e["break_attempt"] = bool(room_fv <= 0.8 * a and e["mom_with"])
        e["failed_break_risk"] = bool(e.get("into_sess_extreme") and e["break_attempt"])
        e["flip_setup"] = bool(e["mom_against"] and e["control_with"] and e.get("sweep_with"))

        above = float(c[i]) >= float(ema34[i]) if np.isfinite(ema34[i]) else True
        e["trend_cont"] = bool(
            e["mom_with"]
            and (
                (side == "BUY" and above and e["di_spread"] > 0)
                or (side == "SELL" and (not above) and e["di_spread"] < 0)
            )
            and not e["compress"]
        )

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


def classify_setup_tier(e: dict) -> Optional[str]:
    """Return 'A', 'B', or None. Live/HELD calls require a tier."""
    if not held_gate(e) or not in_session(e):
        return None
    if e.get("into_sess_extreme") or e.get("regime") == "failed_break_risk":
        return None

    # Tier A — hold_break (research primary)
    if e.get("regime") == "hold_break" and e.get("control_with"):
        return "A"
    if e.get("hold_break_setup"):
        return "A"

    # Tier B — control + sweep (prefer flip/hold_break)
    if e.get("control_with") and e.get("sweep_with"):
        return "B"
    return None


def enrich_path_flags(events: List[dict], df: pd.DataFrame) -> None:
    """clear_path / sr_bounce / runway — needed by run_ignition_100 (and research gates)."""
    for e in events:
        a = float(e.get("atr") or 8.0)
        if not np.isfinite(a) or a <= 0:
            a = 8.0
        entry = float(e.get("entry") or 0)
        side = e.get("decision")
        support = e.get("sr_support")
        resist = e.get("sr_resist")
        room_fav = float(e.get("room_fav") or 999)
        near_sup = support is not None and (entry - float(support)) <= 0.6 * a
        near_res = resist is not None and (float(resist) - entry) <= 0.6 * a
        e["sr_bounce"] = (side == "BUY" and near_sup) or (side == "SELL" and near_res)
        e["runway_2atr"] = room_fav >= 2.0 * a
        e["backed"] = float(e.get("room_against") or 999) <= 1.0 * a
        e["clear_path"] = bool(room_fav >= 1.5 * a and not e.get("into_sess_extreme"))


RUN_PATS = frozenset({"bull_run2", "bull_run3", "bear_run2", "bear_run3"})


def run_pattern_kind(e: dict) -> Optional[str]:
    prim = str(e.get("primary") or "")
    if prim in RUN_PATS:
        return prim
    for p in e.get("patterns") or []:
        if p in RUN_PATS:
            return str(p)
    return None


def tag_run_ignition_100(events: List[dict], df: pd.DataFrame) -> None:
    """Proven gate: run2|3 ignition + control + clear_path + body≥1×ATR + bounce.

    Entry = close of ignition bar (first candle of the run).
    Outputs that matter: decision (BUY/SELL) + ignition_entry.
    """
    o = df["Open"].astype(float).values
    c = df["Close"].astype(float).values
    atr = df["atr14"].astype(float).values if "atr14" in df.columns else np.full(len(c), 8.0)
    day = np.array([str(ts.date()) for ts in df.index])
    idx = df.index

    for e in events:
        e["run_ignition_ok"] = False
        e["ignition_i"] = None
        e["ignition_entry"] = None
        e["ignition_hm"] = None
        kind = run_pattern_kind(e)
        if not kind or not in_session(e):
            continue
        if not (e.get("control_with") and e.get("clear_path") and e.get("sr_bounce")):
            continue
        i = int(e["full_i"])
        ig = i - 2 if kind.endswith("run3") else i - 1
        if ig < 0 or day[ig] != day[i]:
            continue
        side = e.get("decision")
        if kind.startswith("bull") and side != "BUY":
            continue
        if kind.startswith("bear") and side != "SELL":
            continue
        a = float(atr[ig]) if np.isfinite(atr[ig]) and atr[ig] > 0 else float(e.get("atr") or 8.0)
        body = abs(float(c[ig]) - float(o[ig]))
        if body < 1.0 * a:
            continue
        e["run_ignition_ok"] = True
        e["ignition_i"] = int(ig)
        e["ignition_entry"] = round(float(c[ig]), 2)
        ts = pd.Timestamp(idx[ig])
        if ts.tzinfo is None:
            ts = ts.tz_localize("Asia/Kolkata")
        else:
            ts = ts.tz_convert("Asia/Kolkata")
        e["ignition_hm"] = ts.strftime("%H:%M")
        e["ignition_mins"] = int(ts.hour * 60 + ts.minute)
        e["setup_label"] = f"IGN100 · {kind}"


def apply_setup_enrichment(events: List[dict], df: pd.DataFrame) -> None:
    enrich_sr_liq(events, df)
    enrich_control_regime(events, df)
    enrich_path_flags(events, df)
    for e in events:
        tier = classify_setup_tier(e)
        e["setup_tier"] = tier
        e["setup_ok"] = tier is not None
        if tier == "A":
            e["setup_label"] = "Tier A · hold_break"
        elif tier == "B":
            e["setup_label"] = "Tier B · control+sweep"
        else:
            e["setup_label"] = None
    tag_run_ignition_100(events, df)


def setup_why_bits(e: dict) -> Dict[str, Any]:
    return {
        "setup_tier": e.get("setup_tier"),
        "setup_label": e.get("setup_label"),
        "regime": e.get("regime"),
        "control_with": bool(e.get("control_with")),
        "sweep_with": bool(e.get("sweep_with")),
        "buyer_bar": bool(e.get("buyer_bar")),
        "seller_bar": bool(e.get("seller_bar")),
        "room_fav": e.get("room_fav"),
        "room_against": e.get("room_against"),
        "sr_support": e.get("sr_support"),
        "sr_resist": e.get("sr_resist"),
        "into_sess_extreme": bool(e.get("into_sess_extreme")),
        "at_liq_magnet": bool(e.get("at_liq_magnet")),
        "hold_break_setup": bool(e.get("hold_break_setup")),
        "flip_setup": bool(e.get("flip_setup")),
        "clear_path": bool(e.get("clear_path")),
        "sr_bounce": bool(e.get("sr_bounce")),
        "run_ignition_ok": bool(e.get("run_ignition_ok")),
        "ignition_entry": e.get("ignition_entry"),
        "ignition_hm": e.get("ignition_hm"),
    }
