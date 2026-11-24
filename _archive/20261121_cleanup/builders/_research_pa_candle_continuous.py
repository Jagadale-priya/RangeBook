"""RESEARCH — continuous candle reading on top of locked frvp_vah_break+no_exhaust.

Goal: understand candles ALL the time (pre / entry / during / trail) and lift accuracy
without wrecking the held book.

  python -u prod_live/tests/builders/_research_pa_candle_continuous.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
]
import kite_data  # noqa: E402
from prod_live.logic import pa_structure_live as pa  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
MD = OUT / "PA_CANDLE_CONTINUOUS_RESEARCH.md"
JS = OUT / "PA_CANDLE_CONTINUOUS_RESEARCH.json"


def bar(o, h, l, c, i: int) -> Dict[str, Any]:
    op, hi, lo, cl = float(o[i]), float(h[i]), float(l[i]), float(c[i])
    rng = max(hi - lo, 1e-9)
    body = abs(cl - op)
    bf = body / rng
    upper = hi - max(op, cl)
    lower = min(op, cl) - lo
    bull = cl > op
    bear = cl < op
    return {
        "o": op,
        "h": hi,
        "l": lo,
        "c": cl,
        "rng": rng,
        "body": body,
        "body_frac": bf,
        "upper_frac": upper / rng,
        "lower_frac": lower / rng,
        "bull": bull,
        "bear": bear,
        "doji": bf < 0.18,
        "maru": bf >= 0.75 and upper / rng < 0.12 and lower / rng < 0.12,
        "pin_bull": lower / rng >= 0.55 and bf <= 0.35 and upper / rng <= 0.25,
        "pin_bear": upper / rng >= 0.55 and bf <= 0.35 and lower / rng <= 0.25,
        "close_loc": (cl - lo) / rng,
        "inside": i >= 1 and hi <= float(h[i - 1]) and lo >= float(l[i - 1]),
        "outside": i >= 1 and hi >= float(h[i - 1]) and lo <= float(l[i - 1]),
    }


def story_pre(o, h, l, c, atr, i: int, side: str, look: int = 5) -> Dict[str, Any]:
    """Continuous read of last `look` bars including entry."""
    j0 = max(0, i - look + 1)
    feats = [bar(o, h, l, c, j) for j in range(j0, i + 1)]
    entry = feats[-1]
    a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 10.0

    with_n = opp_n = doji_n = pin_with = pin_opp = maru_n = inside_n = 0
    bodies = []
    closes_up = 0
    for f in feats:
        bodies.append(f["body_frac"])
        if side == "BUY":
            if f["bull"]:
                with_n += 1
            if f["bear"]:
                opp_n += 1
            if f["pin_bull"]:
                pin_with += 1
            if f["pin_bear"]:
                pin_opp += 1
            if f["c"] > f["o"]:
                closes_up += 1
        else:
            if f["bear"]:
                with_n += 1
            if f["bull"]:
                opp_n += 1
            if f["pin_bear"]:
                pin_with += 1
            if f["pin_bull"]:
                pin_opp += 1
        if f["doji"]:
            doji_n += 1
        if f["maru"]:
            maru_n += 1
        if f["inside"]:
            inside_n += 1

    # squeeze: shrinking ranges into entry
    rngs = [f["rng"] for f in feats]
    squeeze = len(rngs) >= 3 and rngs[-1] < rngs[0] * 0.7 and rngs[-1] < a * 0.55
    # expansion at entry
    expand = entry["rng"] >= a * 0.85 and entry["body_frac"] >= 0.45
    # pullback-then-resume: opp then with in last 3
    pb_resume = False
    if len(feats) >= 3:
        a2, a1, a0 = feats[-3], feats[-2], feats[-1]
        if side == "BUY":
            pb_resume = (a2["bear"] or a2["pin_bull"]) and a1["bull"] and a0["bull"] and a0["close_loc"] >= 0.55
        else:
            pb_resume = (a2["bull"] or a2["pin_bear"]) and a1["bear"] and a0["bear"] and a0["close_loc"] <= 0.45
    # momentum stack: 2+ with closes ending strong
    if side == "BUY":
        mom = entry["bull"] and entry["close_loc"] >= 0.60 and with_n >= 2
        weak_entry = entry["doji"] or entry["pin_bear"] or entry["close_loc"] < 0.40
        close_ok = entry["bull"] and entry["close_loc"] >= 0.55
    else:
        mom = entry["bear"] and entry["close_loc"] <= 0.40 and with_n >= 2
        weak_entry = entry["doji"] or entry["pin_bull"] or entry["close_loc"] > 0.60
        close_ok = entry["bear"] and entry["close_loc"] <= 0.45

    # prior exhaust (same as locked)
    prior = feats[-2] if len(feats) > 1 else None
    if side == "BUY":
        prior_exhaust = bool(prior and (prior["pin_bear"] or (prior["upper_frac"] >= 0.55 and prior["bull"])))
        prior_reject = bool(prior and (prior["pin_bull"] or prior["lower_frac"] >= 0.45))
    else:
        prior_exhaust = bool(prior and (prior["pin_bull"] or (prior["lower_frac"] >= 0.55 and prior["bear"])))
        prior_reject = bool(prior and (prior["pin_bear"] or prior["upper_frac"] >= 0.45))

    # net directional impulse over window (pts / atr)
    impulse = (feats[-1]["c"] - feats[0]["o"]) / a
    if side == "SELL":
        impulse = -impulse

    return {
        "with_n": with_n,
        "opp_n": opp_n,
        "doji_n": doji_n,
        "pin_with": pin_with,
        "pin_opp": pin_opp,
        "maru_n": maru_n,
        "inside_n": inside_n,
        "avg_body": round(float(np.mean(bodies)), 3) if bodies else 0.0,
        "entry_body": round(entry["body_frac"], 3),
        "entry_close_loc": round(entry["close_loc"], 3),
        "entry_rng_atr": round(entry["rng"] / a, 3),
        "squeeze": squeeze,
        "expand": expand,
        "pb_resume": pb_resume,
        "mom": mom,
        "weak_entry": weak_entry,
        "close_ok": close_ok,
        "prior_exhaust": prior_exhaust,
        "prior_reject": prior_reject,
        "impulse": round(float(impulse), 3),
        "noisy": opp_n >= 3 and with_n <= 2,
        "clean": with_n >= 3 and opp_n <= 1 and not prior_exhaust,
    }


def path_read(
    o, h, l, c, atr, entry_i: int, side: str, entry: float, risk: float, exit_i: Optional[int] = None
) -> Dict[str, Any]:
    """Continuous candle read while trade is live (until exit or 1R+5)."""
    a = float(atr[entry_i]) if np.isfinite(atr[entry_i]) and atr[entry_i] > 0 else 10.0
    end = exit_i if exit_i is not None else min(len(c) - 1, entry_i + 40)
    n_opp = n_with = n_doji = n_pin_opp = n_strong = n_inside = 0
    bars_to_05 = bars_to_1r = None
    max_opp_streak = opp_streak = 0
    giveback_after_1r = 0.0
    peak_after_1r = 0.0
    hit_1r = False

    for j in range(entry_i + 1, end + 1):
        f = bar(o, h, l, c, j)
        hi, lo, cl = f["h"], f["l"], f["c"]
        if side == "BUY":
            fav = hi - entry
            fav_c = cl - entry
            with_c = f["bull"]
            opp_c = f["bear"]
            pin_opp = f["pin_bear"]
            strong = f["bull"] and f["body_frac"] >= 0.55
        else:
            fav = entry - lo
            fav_c = entry - cl
            with_c = f["bear"]
            opp_c = f["bull"]
            pin_opp = f["pin_bull"]
            strong = f["bear"] and f["body_frac"] >= 0.55

        if bars_to_05 is None and fav >= 0.5 * risk:
            bars_to_05 = j - entry_i
        if bars_to_1r is None and fav >= risk:
            bars_to_1r = j - entry_i
            hit_1r = True

        if with_c:
            n_with += 1
            opp_streak = 0
        if opp_c:
            n_opp += 1
            opp_streak += 1
            max_opp_streak = max(max_opp_streak, opp_streak)
        if f["doji"]:
            n_doji += 1
        if pin_opp:
            n_pin_opp += 1
        if strong:
            n_strong += 1
        if f["inside"]:
            n_inside += 1

        if hit_1r:
            peak_after_1r = max(peak_after_1r, fav_c / risk if risk else 0)
            giveback_after_1r = max(giveback_after_1r, peak_after_1r - (fav_c / risk if risk else 0))

        if bars_to_1r is not None and (j - entry_i) >= bars_to_1r + 8:
            break

    return {
        "bars_to_05": bars_to_05,
        "bars_to_1r": bars_to_1r,
        "n_opp": n_opp,
        "n_with": n_with,
        "n_doji": n_doji,
        "n_pin_opp": n_pin_opp,
        "n_strong": n_strong,
        "n_inside": n_inside,
        "max_opp_streak": max_opp_streak,
        "giveback_R": round(giveback_after_1r, 3),
        "peak_R": round(peak_after_1r, 3),
        "stall": bars_to_05 is None or (bars_to_05 is not None and bars_to_05 > 12),
        "fast_1r": bars_to_1r is not None and bars_to_1r <= 8,
        "messy": n_opp >= n_with and n_opp >= 4,
    }


# --- continuous trail variants (on top of structure) ---
def settle_continuous(
    o, h, l, c, atr, idx, entry_i, side, entry, sl0, risk, cfg, *, mode: str
) -> Dict[str, Any]:
    sl = float(sl0)
    mfe = mae = 0.0
    hit_1 = hit_2 = hit_3 = False
    day0 = pa._day(idx[entry_i])
    armed = False
    arm_R = float(cfg.trail_arm_R)
    opp_streak = 0
    bars_since_entry = 0
    saw_05 = False

    for j in range(entry_i + 1, min(len(c), entry_i + 1 + cfg.max_hold_bars)):
        bars_since_entry += 1
        if pa._day(idx[j]) != day0:
            px = float(c[j - 1]) if j > entry_i else entry
            pts = (px - entry) if side == "BUY" else (entry - px)
            return _pack(pa._hm(idx[j - 1]), px, "session_end", pts, risk, mfe, mae, hit_1, hit_2, hit_3)

        f = bar(o, h, l, c, j)
        hi, lo, cl = f["h"], f["l"], f["c"]
        a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else 10.0

        if side == "BUY":
            fav, adv = hi - entry, entry - lo
            if lo <= sl:
                pts = sl - entry
                return _pack(
                    pa._hm(idx[j]), sl, "sl" if not armed else "trail_sl", pts, risk,
                    max(mfe, fav), max(mae, adv), hit_1 or fav >= risk, hit_2 or fav >= 2 * risk, hit_3 or fav >= 3 * risk,
                )
            mfe, mae = max(mfe, fav), max(mae, adv)
            if fav >= 0.5 * risk:
                saw_05 = True
            if fav >= arm_R * risk:
                hit_1 = hit_1 or fav >= risk
                armed = True
            if fav >= 2 * risk:
                hit_2 = True
            if fav >= 3 * risk:
                hit_3 = True

            with_c, opp_c = f["bull"], f["bear"]
            pin_opp = f["pin_bear"]
            strong_with = f["bull"] and f["body_frac"] >= 0.45

            if opp_c:
                opp_streak += 1
            else:
                opp_streak = 0

            # stall: no 0.5R by bar 15 → exit at close (continuous read: dead tape)
            if mode in ("stall_cut", "read_full") and not saw_05 and bars_since_entry >= 15:
                pts = cl - entry
                return _pack(pa._hm(idx[j]), cl, "stall_cut", pts, risk, mfe, mae, hit_1, hit_2, hit_3)

            if armed:
                trail = float(l[j - 1]) - cfg.sl_buffer
                if mode == "base":
                    if trail > sl:
                        sl = trail
                elif mode == "with_only":
                    # only ratchet on with-side candle (let opposing wick breathe)
                    if strong_with and trail > sl:
                        sl = trail
                elif mode == "pin_protect":
                    if trail > sl:
                        sl = trail
                    if pin_opp or (opp_c and f["body_frac"] >= 0.55):
                        tight = lo - cfg.sl_buffer
                        if tight > sl:
                            sl = tight
                elif mode == "opp2_protect":
                    if trail > sl:
                        sl = trail
                    if opp_streak >= 2 and cl < float(c[j - 1]):
                        # move SL to just under last with low (or close exit)
                        pts = cl - entry
                        return _pack(pa._hm(idx[j]), cl, "candle_opp2", pts, risk, mfe, mae, hit_1, hit_2, hit_3)
                elif mode == "read_full":
                    # with-only ratchet + pin tighten + stall already above
                    if strong_with and trail > sl:
                        sl = trail
                    elif pin_opp:
                        tight = lo - cfg.sl_buffer
                        if tight > sl:
                            sl = tight
                    if opp_streak >= 3:
                        pts = cl - entry
                        return _pack(pa._hm(idx[j]), cl, "candle_messy", pts, risk, mfe, mae, hit_1, hit_2, hit_3)

            if j >= 3 and armed and mode in ("base", "with_only", "pin_protect", "stall_cut", "read_full", "opp2_protect"):
                if mode == "base" or mode == "stall_cut":
                    sw = float(np.min(l[j - 3 : j]))
                    if cl < sw:
                        pts = cl - entry
                        return _pack(pa._hm(idx[j]), cl, "structure_fail", pts, risk, mfe, mae, hit_1, hit_2, hit_3)

        else:
            fav, adv = entry - lo, hi - entry
            if hi >= sl:
                pts = entry - sl
                return _pack(
                    pa._hm(idx[j]), sl, "sl" if not armed else "trail_sl", pts, risk,
                    max(mfe, fav), max(mae, adv), hit_1 or fav >= risk, hit_2 or fav >= 2 * risk, hit_3 or fav >= 3 * risk,
                )
            mfe, mae = max(mfe, fav), max(mae, adv)
            if fav >= 0.5 * risk:
                saw_05 = True
            if fav >= arm_R * risk:
                hit_1 = hit_1 or fav >= risk
                armed = True
            if fav >= 2 * risk:
                hit_2 = True
            if fav >= 3 * risk:
                hit_3 = True

            with_c, opp_c = f["bear"], f["bull"]
            pin_opp = f["pin_bull"]
            strong_with = f["bear"] and f["body_frac"] >= 0.45
            if opp_c:
                opp_streak += 1
            else:
                opp_streak = 0

            if mode in ("stall_cut", "read_full") and not saw_05 and bars_since_entry >= 15:
                pts = entry - cl
                return _pack(pa._hm(idx[j]), cl, "stall_cut", pts, risk, mfe, mae, hit_1, hit_2, hit_3)

            if armed:
                trail = float(h[j - 1]) + cfg.sl_buffer
                if mode == "base":
                    if trail < sl:
                        sl = trail
                elif mode == "with_only":
                    if strong_with and trail < sl:
                        sl = trail
                elif mode == "pin_protect":
                    if trail < sl:
                        sl = trail
                    if pin_opp or (opp_c and f["body_frac"] >= 0.55):
                        tight = hi + cfg.sl_buffer
                        if tight < sl:
                            sl = tight
                elif mode == "opp2_protect":
                    if trail < sl:
                        sl = trail
                    if opp_streak >= 2 and cl > float(c[j - 1]):
                        pts = entry - cl
                        return _pack(pa._hm(idx[j]), cl, "candle_opp2", pts, risk, mfe, mae, hit_1, hit_2, hit_3)
                elif mode == "read_full":
                    if strong_with and trail < sl:
                        sl = trail
                    elif pin_opp:
                        tight = hi + cfg.sl_buffer
                        if tight < sl:
                            sl = tight
                    if opp_streak >= 3:
                        pts = entry - cl
                        return _pack(pa._hm(idx[j]), cl, "candle_messy", pts, risk, mfe, mae, hit_1, hit_2, hit_3)

            if j >= 3 and armed and mode in ("base", "stall_cut"):
                sw = float(np.max(h[j - 3 : j]))
                if cl > sw:
                    pts = entry - cl
                    return _pack(pa._hm(idx[j]), cl, "structure_fail", pts, risk, mfe, mae, hit_1, hit_2, hit_3)

    last = min(len(c) - 1, entry_i + cfg.max_hold_bars)
    px = float(c[last])
    pts = (px - entry) if side == "BUY" else (entry - px)
    return _pack(pa._hm(idx[last]), px, "time_cut", pts, risk, mfe, mae, hit_1, hit_2, hit_3)


def _pack(hm, px, why, pts, risk, mfe, mae, h1, h2, h3):
    return {
        "exit_hm": hm,
        "exit_px": round(float(px), 2),
        "exit_why": why,
        "pts": round(float(pts), 2),
        "R": round(float(pts) / risk, 3) if risk else 0.0,
        "win": pts > 0,
        "mfe": round(float(mfe), 2),
        "mae": round(float(mae), 2),
        "hit_1R": h1,
        "hit_2R": h2,
        "hit_3R": h3,
    }


def entry_extra_gate(pre: Dict[str, Any], mode: str) -> bool:
    """Extra continuous-candle gates ON TOP of locked no_exhaust."""
    if mode == "none":
        return True
    if mode == "close_ok":
        return pre["close_ok"]
    if mode == "expand":
        return pre["expand"] and pre["close_ok"]
    if mode == "pb_resume":
        return pre["pb_resume"]
    if mode == "mom":
        return pre["mom"] and not pre["noisy"]
    if mode == "clean":
        return pre["clean"]
    if mode == "not_noisy":
        return not pre["noisy"] and pre["close_ok"]
    if mode == "impulse_pos":
        return pre["impulse"] > 0 and pre["close_ok"]
    if mode == "reject_ctx":
        return pre["prior_reject"] and pre["close_ok"]
    if mode == "read_v1":
        # continuous: close ok + not noisy + (expand OR pb_resume OR mom)
        return pre["close_ok"] and not pre["noisy"] and (pre["expand"] or pre["pb_resume"] or pre["mom"])
    if mode == "read_v2":
        # softer continuous: close ok + impulse >= 0 + not messy window
        return pre["close_ok"] and pre["impulse"] >= -0.15 and pre["opp_n"] <= 2
    if mode == "read_v3":
        # close ok + avg body decent + no pin-against in window
        return pre["close_ok"] and pre["avg_body"] >= 0.40 and pre["pin_opp"] == 0
    return True


def run_variant(bars, cfg, days_set, *, entry_mode: str, trail_mode: str) -> Dict[str, Any]:
    work = pa.norm_1m(bars)
    work = work[work.index.strftime("%Y-%m-%d").isin(days_set)]
    # base entries from locked scan (already has no_exhaust)
    base_calls = pa.scan_session(work, settle=False, cfg=cfg)
    o = work["Open"].values
    h = work["High"].values
    l = work["Low"].values
    c = work["Close"].values
    atr = pa.atr14(h, l, c)
    idx = work.index
    hm_to_i = {(pa._day(ts), pa._hm(ts)): i for i, ts in enumerate(idx)}

    out = []
    for call in base_calls:
        i = hm_to_i.get((call.day, call.hm))
        if i is None:
            continue
        pre = story_pre(o, h, l, c, atr, i, call.side)
        if not entry_extra_gate(pre, entry_mode):
            continue
        path = settle_continuous(
            o, h, l, c, atr, idx, i, call.side, float(call.entry), float(call.stop_loss),
            float(call.risk), cfg, mode=trail_mode,
        )
        for k, v in path.items():
            setattr(call, k, v)
        call.cfg_name = f"{cfg.name}|{entry_mode}|{trail_mode}"
        out.append(call)
    return {"summary": pa.summarize(out), "n": len(out), "calls": out}


def _rate(rows, key):
    if not rows:
        return None
    return round(100.0 * sum(1 for r in rows if r.get(key)) / len(rows), 1)


def _avg(rows, key):
    xs = [r[key] for r in rows if r.get(key) is not None]
    return round(float(np.mean(xs)), 3) if xs else None


def main() -> int:
    cfg = pa.load_locked_cfg()
    print(f"Base locked={cfg.name} candle={cfg.candle_entry_mode}", flush=True)
    raw, err = kite_data.fetch_historical_candles("NIFTY", "minute", days=40, keep_partial=False)
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    days = sorted({str(ts.date()) for ts in bars.index})[-22:]
    days_set = set(days)
    window = bars[bars.index.strftime("%Y-%m-%d").isin(days_set)]
    print(f"Window {days[0]}→{days[-1]} ({len(days)} sessions)", flush=True)

    # --- deep autopsy on locked settled book ---
    base = pa.scan_session(window, settle=True, cfg=cfg)
    o = window["Open"].values
    h = window["High"].values
    l = window["Low"].values
    c = window["Close"].values
    atr = pa.atr14(h, l, c)
    idx = window.index
    hm_to_i = {(pa._day(ts), pa._hm(ts)): i for i, ts in enumerate(idx)}

    win_pre, sl_pre, win_path, sl_path = [], [], [], []
    for call in base:
        i = hm_to_i.get((call.day, call.hm))
        if i is None:
            continue
        pre = story_pre(o, h, l, c, atr, i, call.side)
        # approximate exit index from exit_hm
        exit_i = None
        if call.exit_hm:
            exit_i = hm_to_i.get((call.day, call.exit_hm))
        pr = path_read(o, h, l, c, atr, i, call.side, float(call.entry), float(call.risk), exit_i)
        if call.exit_why == "sl" or (call.win is False and call.exit_why in ("sl", "trail_sl") and (call.R or 0) <= -0.9):
            if call.exit_why == "sl":
                sl_pre.append(pre)
                sl_path.append(pr)
        if call.win:
            win_pre.append(pre)
            win_path.append(pr)

    autopsy = {
        "win_pre": {
            "n": len(win_pre),
            "close_ok%": _rate(win_pre, "close_ok"),
            "expand%": _rate(win_pre, "expand"),
            "pb_resume%": _rate(win_pre, "pb_resume"),
            "mom%": _rate(win_pre, "mom"),
            "clean%": _rate(win_pre, "clean"),
            "noisy%": _rate(win_pre, "noisy"),
            "squeeze%": _rate(win_pre, "squeeze"),
            "prior_reject%": _rate(win_pre, "prior_reject"),
            "avg_impulse": _avg(win_pre, "impulse"),
            "avg_with": _avg(win_pre, "with_n"),
            "avg_opp": _avg(win_pre, "opp_n"),
            "avg_entry_body": _avg(win_pre, "entry_body"),
        },
        "sl_pre": {
            "n": len(sl_pre),
            "close_ok%": _rate(sl_pre, "close_ok"),
            "expand%": _rate(sl_pre, "expand"),
            "pb_resume%": _rate(sl_pre, "pb_resume"),
            "mom%": _rate(sl_pre, "mom"),
            "clean%": _rate(sl_pre, "clean"),
            "noisy%": _rate(sl_pre, "noisy"),
            "squeeze%": _rate(sl_pre, "squeeze"),
            "prior_reject%": _rate(sl_pre, "prior_reject"),
            "avg_impulse": _avg(sl_pre, "impulse"),
            "avg_with": _avg(sl_pre, "with_n"),
            "avg_opp": _avg(sl_pre, "opp_n"),
            "avg_entry_body": _avg(sl_pre, "entry_body"),
        },
        "win_path": {
            "n": len(win_path),
            "fast_1r%": _rate(win_path, "fast_1r"),
            "stall%": _rate(win_path, "stall"),
            "messy%": _rate(win_path, "messy"),
            "avg_bars_05": _avg(win_path, "bars_to_05"),
            "avg_bars_1r": _avg(win_path, "bars_to_1r"),
            "avg_opp": _avg(win_path, "n_opp"),
            "avg_with": _avg(win_path, "n_with"),
            "avg_pin_opp": _avg(win_path, "n_pin_opp"),
            "avg_opp_streak": _avg(win_path, "max_opp_streak"),
            "avg_giveback_R": _avg(win_path, "giveback_R"),
        },
        "sl_path": {
            "n": len(sl_path),
            "fast_1r%": _rate(sl_path, "fast_1r"),
            "stall%": _rate(sl_path, "stall"),
            "messy%": _rate(sl_path, "messy"),
            "avg_bars_05": _avg(sl_path, "bars_to_05"),
            "avg_bars_1r": _avg(sl_path, "bars_to_1r"),
            "avg_opp": _avg(sl_path, "n_opp"),
            "avg_with": _avg(sl_path, "n_with"),
            "avg_pin_opp": _avg(sl_path, "n_pin_opp"),
            "avg_opp_streak": _avg(sl_path, "max_opp_streak"),
            "avg_giveback_R": _avg(sl_path, "giveback_R"),
        },
    }
    print("AUTOPSY win_pre", autopsy["win_pre"], flush=True)
    print("AUTOPSY sl_pre ", autopsy["sl_pre"], flush=True)
    print("AUTOPSY win_path", autopsy["win_path"], flush=True)
    print("AUTOPSY sl_path ", autopsy["sl_path"], flush=True)

    entry_modes = [
        "none", "close_ok", "not_noisy", "impulse_pos", "expand", "mom",
        "clean", "pb_resume", "reject_ctx", "read_v1", "read_v2", "read_v3",
    ]
    trail_modes = ["base", "with_only", "pin_protect", "opp2_protect", "stall_cut", "read_full"]

    results = []
    # full grid would be huge — prioritize: all entry×base, then none×all trails, then top entry×top trails
    combos = []
    for em in entry_modes:
        combos.append((em, "base"))
    for tm in trail_modes:
        if tm != "base":
            combos.append(("none", tm))
    for em in ("close_ok", "not_noisy", "read_v2", "read_v3", "impulse_pos"):
        for tm in ("with_only", "stall_cut", "pin_protect"):
            combos.append((em, tm))

    seen = set()
    for em, tm in combos:
        key = f"{em}+{tm}"
        if key in seen:
            continue
        seen.add(key)
        print(f"  try {key}…", flush=True)
        book = run_variant(bars, cfg, days_set, entry_mode=em, trail_mode=tm)
        s = book["summary"]
        results.append({"name": key, "entry": em, "trail": tm, **s, "n": book["n"]})
        print(f"    n={s.get('n')} hit={s.get('hit_pct')} R={s.get('avg_R')} sum={s.get('sum_pts')}", flush=True)

    base_s = pa.summarize(base)
    ranked = sorted(
        results,
        key=lambda r: ((r.get("hit_pct") or 0), (r.get("avg_R") or 0), (r.get("sum_pts") or 0)),
        reverse=True,
    )
    # practical: keep volume, lift hit or sum
    n_floor = max(45, int(0.70 * (base_s.get("n") or 1)))
    practical = [
        r for r in ranked
        if (r.get("n") or 0) >= n_floor
        and (r.get("hit_pct") or 0) >= (base_s.get("hit_pct") or 0) - 0.5
        and (
            (r.get("avg_R") or -9) >= (base_s.get("avg_R") or 0) - 0.02
            or (r.get("sum_pts") or -9e9) >= (base_s.get("sum_pts") or 0)
        )
    ]
    # prefer higher sum then hit among practical
    practical_sum = sorted(
        practical,
        key=lambda r: ((r.get("sum_pts") or 0), (r.get("hit_pct") or 0), (r.get("avg_R") or 0)),
        reverse=True,
    )
    best_practical = practical_sum[0] if practical_sum else None
    best_hit = ranked[0]

    lines = [
        f"# Continuous candle research · locked `{cfg.name}` + `{cfg.candle_entry_mode}`",
        "",
        f"Window {days[0]} → {days[-1]} ({len(days)} sessions). Candles read **before / at / during** every call.",
        "",
        "## Autopsy — candles before entry (5-bar story)",
        "",
        "| Feature | Wins | Hard SL |",
        "|---|---|---|",
        f"| N | {autopsy['win_pre']['n']} | {autopsy['sl_pre']['n']} |",
        f"| Close OK % | {autopsy['win_pre']['close_ok%']} | {autopsy['sl_pre']['close_ok%']} |",
        f"| Expand (range+body) % | {autopsy['win_pre']['expand%']} | {autopsy['sl_pre']['expand%']} |",
        f"| Pullback-resume % | {autopsy['win_pre']['pb_resume%']} | {autopsy['sl_pre']['pb_resume%']} |",
        f"| Momentum stack % | {autopsy['win_pre']['mom%']} | {autopsy['sl_pre']['mom%']} |",
        f"| Clean window % | {autopsy['win_pre']['clean%']} | {autopsy['sl_pre']['clean%']} |",
        f"| Noisy window % | {autopsy['win_pre']['noisy%']} | {autopsy['sl_pre']['noisy%']} |",
        f"| Squeeze into entry % | {autopsy['win_pre']['squeeze%']} | {autopsy['sl_pre']['squeeze%']} |",
        f"| Prior reject % | {autopsy['win_pre']['prior_reject%']} | {autopsy['sl_pre']['prior_reject%']} |",
        f"| Avg impulse (ATR) | {autopsy['win_pre']['avg_impulse']} | {autopsy['sl_pre']['avg_impulse']} |",
        f"| Avg with / opp bars | {autopsy['win_pre']['avg_with']} / {autopsy['win_pre']['avg_opp']} | {autopsy['sl_pre']['avg_with']} / {autopsy['sl_pre']['avg_opp']} |",
        f"| Avg entry body | {autopsy['win_pre']['avg_entry_body']} | {autopsy['sl_pre']['avg_entry_body']} |",
        "",
        "## Autopsy — candles during the move",
        "",
        "| Feature | Wins | Hard SL |",
        "|---|---|---|",
        f"| Fast to 1R (≤8 bars) % | {autopsy['win_path']['fast_1r%']} | {autopsy['sl_path']['fast_1r%']} |",
        f"| Stall (no 0.5R soon) % | {autopsy['win_path']['stall%']} | {autopsy['sl_path']['stall%']} |",
        f"| Messy path % | {autopsy['win_path']['messy%']} | {autopsy['sl_path']['messy%']} |",
        f"| Avg bars to 0.5R / 1R | {autopsy['win_path']['avg_bars_05']} / {autopsy['win_path']['avg_bars_1r']} | {autopsy['sl_path']['avg_bars_05']} / {autopsy['sl_path']['avg_bars_1r']} |",
        f"| Avg with / opp on path | {autopsy['win_path']['avg_with']} / {autopsy['win_path']['avg_opp']} | {autopsy['sl_path']['avg_with']} / {autopsy['sl_path']['avg_opp']} |",
        f"| Avg pin-against | {autopsy['win_path']['avg_pin_opp']} | {autopsy['sl_path']['avg_pin_opp']} |",
        f"| Avg max opp streak | {autopsy['win_path']['avg_opp_streak']} | {autopsy['sl_path']['avg_opp_streak']} |",
        f"| Avg giveback after 1R (R) | {autopsy['win_path']['avg_giveback_R']} | {autopsy['sl_path']['avg_giveback_R']} |",
        "",
        "## Ablation (extra entry read × trail read) on locked book",
        "",
        f"Locked base: n={base_s.get('n')} hit={base_s.get('hit_pct')}% avgR={base_s.get('avg_R')} sum={base_s.get('sum_pts')}",
        "",
        "| Variant | N | Hit% | AvgR | Sum |",
        "|---|---:|---:|---:|---:|",
        f"| **LOCKED BASE** | {base_s.get('n')} | {base_s.get('hit_pct')} | {base_s.get('avg_R')} | {base_s.get('sum_pts')} |",
    ]
    for r in ranked:
        mark = "**" if best_practical and r["name"] == best_practical["name"] else ""
        lines.append(
            f"| {mark}{r['name']}{mark} | {r.get('n')} | {r.get('hit_pct')} | {r.get('avg_R')} | {r.get('sum_pts')} |"
        )

    lines += [
        "",
        "## Recommendation",
        "",
    ]
    if best_practical:
        lines.append(
            f"**Practical best (volume kept):** `{best_practical['name']}` — "
            f"n={best_practical.get('n')} hit={best_practical.get('hit_pct')} "
            f"avgR={best_practical.get('avg_R')} sum={best_practical.get('sum_pts')}"
        )
    lines.append(
        f"**Hit-max (may cut calls):** `{best_hit['name']}` — "
        f"n={best_hit.get('n')} hit={best_hit.get('hit_pct')} avgR={best_hit.get('avg_R')}"
    )
    lines += [
        "",
        "### Continuous candle rules that matter",
        "",
        "1. **Pre-entry window:** avoid noisy 5-bar tapes (many opposing closes); prefer close in direction + non-negative impulse.",
        "2. **Entry bar:** close location + body still dominate; expand/mom help but are rare — don't require them alone.",
        "3. **During move:** wins are fast to 0.5R/1R; stalling tape is a loss signature — stall_cut is the main trail add-on to test.",
        "4. **Trail:** structure trail remains default; aggressive candle exits often cut winners — only adopt if sum & hit both hold.",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    MD.write_text("\n".join(lines), encoding="utf-8")
    JS.write_text(
        json.dumps(
            {
                "autopsy": autopsy,
                "base": base_s,
                "ranked": results,
                "best_practical": best_practical,
                "best_hit": best_hit,
                "window": {"start": days[0], "end": days[-1], "n": len(days)},
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"BEST_PRACTICAL={best_practical['name'] if best_practical else None}", flush=True)
    print(f"BEST_HIT={best_hit['name']}", flush=True)
    print(f"Wrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
