"""RESEARCH — understand candles before entry & during moves; improve call/trail.

Locked frvp_vah_break base. Tests candle-aware entry gates + trail rules.
Does not destroy held logic — reports best add-ons.

  python -u prod_live/tests/builders/_research_pa_candle_aware.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
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
MD = OUT / "PA_CANDLE_AWARE_RESEARCH.md"
JS = OUT / "PA_CANDLE_AWARE_RESEARCH.json"


def candle_feats(o, h, l, c, i: int) -> Dict[str, Any]:
    op, hi, lo, cl = float(o[i]), float(h[i]), float(l[i]), float(c[i])
    rng = max(hi - lo, 1e-9)
    body = abs(cl - op)
    body_frac = body / rng
    upper = hi - max(op, cl)
    lower = min(op, cl) - lo
    bull = cl > op
    bear = cl < op
    doji = body_frac < 0.18
    maru = body_frac >= 0.75 and upper / rng < 0.12 and lower / rng < 0.12
    pin_bull = lower / rng >= 0.55 and body_frac <= 0.35 and upper / rng <= 0.25
    pin_bear = upper / rng >= 0.55 and body_frac <= 0.35 and lower / rng <= 0.25
    # engulf vs prev
    eng_bull = eng_bear = False
    if i >= 1:
        po, pc = float(o[i - 1]), float(c[i - 1])
        eng_bull = bull and (cl >= max(po, pc)) and (op <= min(po, pc)) and body > abs(pc - po)
        eng_bear = bear and (cl <= min(po, pc)) and (op >= max(po, pc)) and body > abs(pc - po)
    inside = False
    if i >= 1:
        inside = hi <= float(h[i - 1]) and lo >= float(l[i - 1])
    return {
        "bull": bull,
        "bear": bear,
        "body_frac": round(body_frac, 3),
        "upper_frac": round(upper / rng, 3),
        "lower_frac": round(lower / rng, 3),
        "doji": doji,
        "maru": maru,
        "pin_bull": pin_bull,
        "pin_bear": pin_bear,
        "eng_bull": eng_bull,
        "eng_bear": eng_bear,
        "inside": inside,
        "close_loc": round((cl - lo) / rng, 3),  # 1=close at high
    }


def pre_pattern(o, h, l, c, i: int, side: str) -> Dict[str, Any]:
    """Candle story in last 3 bars including entry."""
    feats = [candle_feats(o, h, l, c, j) for j in range(max(0, i - 2), i + 1)]
    entry = feats[-1]
    prev = feats[-2] if len(feats) > 1 else None
    # streak of closes in direction
    streak = 0
    for j in range(i, max(0, i - 5) - 1, -1):
        if side == "BUY" and float(c[j]) > float(o[j]):
            streak += 1
        elif side == "SELL" and float(c[j]) < float(o[j]):
            streak += 1
        else:
            break
    # prior bar opposing rejection (good) vs same-direction exhaustion
    prior_reject = False
    prior_exhaust = False
    if prev:
        if side == "BUY":
            prior_reject = prev["pin_bull"] or prev["eng_bull"] or (prev["lower_frac"] >= 0.45)
            prior_exhaust = prev["pin_bear"] or (prev["upper_frac"] >= 0.55 and prev["bull"])
        else:
            prior_reject = prev["pin_bear"] or prev["eng_bear"] or (prev["upper_frac"] >= 0.45)
            prior_exhaust = prev["pin_bull"] or (prev["lower_frac"] >= 0.55 and prev["bear"])
    # entry quality
    if side == "BUY":
        entry_ok_close = entry["close_loc"] >= 0.55 and entry["bull"]
        entry_reject = entry["pin_bull"] or entry["eng_bull"]
        entry_weak = entry["doji"] or entry["pin_bear"] or entry["close_loc"] < 0.40
    else:
        entry_ok_close = entry["close_loc"] <= 0.45 and entry["bear"]
        entry_reject = entry["pin_bear"] or entry["eng_bear"]
        entry_weak = entry["doji"] or entry["pin_bull"] or entry["close_loc"] > 0.60
    return {
        "streak": streak,
        "prior_reject": prior_reject,
        "prior_exhaust": prior_exhaust,
        "entry_ok_close": entry_ok_close,
        "entry_reject": entry_reject,
        "entry_weak": entry_weak,
        "entry_maru": entry["maru"],
        "entry_body": entry["body_frac"],
        "entry_close_loc": entry["close_loc"],
        "entry_doji": entry["doji"],
        "inside_bar": entry["inside"],
        "engulf": entry["eng_bull"] if side == "BUY" else entry["eng_bear"],
    }


def during_path_feats(o, h, l, c, entry_i: int, side: str, entry: float, risk: float, max_bars: int = 30) -> Dict[str, Any]:
    """Candle behavior while trade runs (until ~1R or 30 bars)."""
    n_opp = n_doji = n_pin_against = n_strong = 0
    hit_1r_bar = None
    for j in range(entry_i + 1, min(len(c), entry_i + 1 + max_bars)):
        f = candle_feats(o, h, l, c, j)
        hi, lo = float(h[j]), float(l[j])
        if side == "BUY":
            fav = hi - entry
            if hit_1r_bar is None and fav >= risk:
                hit_1r_bar = j - entry_i
            if f["bear"]:
                n_opp += 1
            if f["pin_bear"]:
                n_pin_against += 1
            if f["bull"] and f["body_frac"] >= 0.55:
                n_strong += 1
        else:
            fav = entry - lo
            if hit_1r_bar is None and fav >= risk:
                hit_1r_bar = j - entry_i
            if f["bull"]:
                n_opp += 1
            if f["pin_bull"]:
                n_pin_against += 1
            if f["bear"] and f["body_frac"] >= 0.55:
                n_strong += 1
        if f["doji"]:
            n_doji += 1
        if hit_1r_bar is not None and (j - entry_i) >= hit_1r_bar + 3:
            break
    return {
        "bars_to_1r": hit_1r_bar,
        "opp_candles": n_opp,
        "doji_candles": n_doji,
        "pin_against": n_pin_against,
        "strong_with": n_strong,
    }


def settle_candle_trail(
    o, h, l, c, idx, entry_i, side, entry, sl0, risk, cfg, *,
    trail_mode: str = "base",
) -> Dict[str, Any]:
    """settle_path variants with candle-aware trailing."""
    sl = float(sl0)
    mfe = mae = 0.0
    hit_1 = hit_2 = hit_3 = False
    day0 = pa._day(idx[entry_i])
    armed = False
    arm_R = float(cfg.trail_arm_R)
    consec_opp = 0

    for j in range(entry_i + 1, min(len(c), entry_i + 1 + cfg.max_hold_bars)):
        if pa._day(idx[j]) != day0:
            px = float(c[j - 1]) if j > entry_i else entry
            pts = (px - entry) if side == "BUY" else (entry - px)
            return _pack(pa._hm(idx[j - 1]), px, "session_end", pts, risk, mfe, mae, hit_1, hit_2, hit_3)
        hi, lo, cl = float(h[j]), float(l[j]), float(c[j])
        f = candle_feats(o, h, l, c, j)
        if side == "BUY":
            fav, adv = hi - entry, entry - lo
            if lo <= sl:
                pts = sl - entry
                return _pack(pa._hm(idx[j]), sl, "sl" if not armed else "trail_sl", pts, risk, max(mfe, fav), max(mae, adv), hit_1 or fav >= risk, hit_2 or fav >= 2 * risk, hit_3 or fav >= 3 * risk)
            mfe, mae = max(mfe, fav), max(mae, adv)
            if fav >= arm_R * risk:
                hit_1 = hit_1 or fav >= risk
                armed = True
            if fav >= 2 * risk:
                hit_2 = True
            if fav >= 3 * risk:
                hit_3 = True
            # candle trail rules
            if armed:
                trail = float(l[j - 1]) - cfg.sl_buffer
                if trail_mode == "candle_tight":
                    # ratchet only on bullish close; on bearish pin tighten to that low
                    if f["bull"] and trail > sl:
                        sl = trail
                    elif f["pin_bear"] or (f["bear"] and f["body_frac"] >= 0.5):
                        tight = lo - cfg.sl_buffer
                        if tight > sl:
                            sl = tight
                elif trail_mode == "candle_hold":
                    # only trail after strong-with candle; exit early on 2 opp closes
                    if f["bear"]:
                        consec_opp += 1
                    else:
                        consec_opp = 0
                    if consec_opp >= 2 and cl < float(c[j - 1]):
                        pts = cl - entry
                        return _pack(pa._hm(idx[j]), cl, "candle_opp_exit", pts, risk, mfe, mae, hit_1, hit_2, hit_3)
                    if f["bull"] and f["body_frac"] >= 0.45 and trail > sl:
                        sl = trail
                else:  # base
                    if trail > sl:
                        sl = trail
            if j >= 3 and armed and trail_mode == "base":
                sw = float(np.min(l[j - 3 : j]))
                if cl < sw:
                    pts = cl - entry
                    return _pack(pa._hm(idx[j]), cl, "structure_fail", pts, risk, mfe, mae, hit_1, hit_2, hit_3)
        else:
            fav, adv = entry - lo, hi - entry
            if hi >= sl:
                pts = entry - sl
                return _pack(pa._hm(idx[j]), sl, "sl" if not armed else "trail_sl", pts, risk, max(mfe, fav), max(mae, adv), hit_1 or fav >= risk, hit_2 or fav >= 2 * risk, hit_3 or fav >= 3 * risk)
            mfe, mae = max(mfe, fav), max(mae, adv)
            if fav >= arm_R * risk:
                hit_1 = hit_1 or fav >= risk
                armed = True
            if fav >= 2 * risk:
                hit_2 = True
            if fav >= 3 * risk:
                hit_3 = True
            if armed:
                trail = float(h[j - 1]) + cfg.sl_buffer
                if trail_mode == "candle_tight":
                    if f["bear"] and trail < sl:
                        sl = trail
                    elif f["pin_bull"] or (f["bull"] and f["body_frac"] >= 0.5):
                        tight = hi + cfg.sl_buffer
                        if tight < sl:
                            sl = tight
                elif trail_mode == "candle_hold":
                    if f["bull"]:
                        consec_opp += 1
                    else:
                        consec_opp = 0
                    if consec_opp >= 2 and cl > float(c[j - 1]):
                        pts = entry - cl
                        return _pack(pa._hm(idx[j]), cl, "candle_opp_exit", pts, risk, mfe, mae, hit_1, hit_2, hit_3)
                    if f["bear"] and f["body_frac"] >= 0.45 and trail < sl:
                        sl = trail
                else:
                    if trail < sl:
                        sl = trail
            if j >= 3 and armed and trail_mode == "base":
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


def entry_gate(pre: Dict[str, Any], mode: str) -> bool:
    if mode == "none":
        return True
    if mode == "no_weak":
        return not pre["entry_weak"]
    if mode == "ok_close":
        return pre["entry_ok_close"] and not pre["entry_doji"]
    if mode == "reject_or_maru":
        return (pre["entry_reject"] or pre["entry_maru"] or pre["engulf"]) and not pre["entry_weak"]
    if mode == "streak2":
        return pre["streak"] >= 2 and not pre["entry_weak"]
    if mode == "no_exhaust":
        return not pre["prior_exhaust"] and not pre["entry_weak"]
    if mode == "quality":
        # best combo hypothesis
        return (
            pre["entry_ok_close"]
            and not pre["entry_doji"]
            and not pre["prior_exhaust"]
            and (pre["entry_body"] >= 0.50 or pre["entry_reject"] or pre["engulf"])
        )
    if mode == "quality_soft":
        return pre["entry_ok_close"] and not pre["entry_doji"] and not pre["inside_bar"]
    return True


def run_book(bars, cfg, *, entry_mode: str, trail_mode: str, days_set: set) -> Dict[str, Any]:
    work = pa.norm_1m(bars)
    work = work[work.index.strftime("%Y-%m-%d").isin(days_set)]
    if work.empty:
        return pa.summarize([])
    # get base entries from locked scan, then re-settle / filter
    base_calls = pa.scan_session(work, settle=False, cfg=cfg)
    o = work["Open"].values
    h = work["High"].values
    l = work["Low"].values
    c = work["Close"].values
    atr = pa.atr14(h, l, c)
    idx = work.index
    # map day+hm to index
    hm_to_i = {}
    for i, ts in enumerate(idx):
        hm_to_i[(pa._day(ts), pa._hm(ts))] = i

    out_calls = []
    for call in base_calls:
        i = hm_to_i.get((call.day, call.hm))
        if i is None:
            continue
        pre = pre_pattern(o, h, l, c, i, call.side)
        if not entry_gate(pre, entry_mode):
            continue
        path = settle_candle_trail(
            o, h, l, c, idx, i, call.side, float(call.entry), float(call.stop_loss),
            float(call.risk), cfg, trail_mode=trail_mode,
        )
        for k, v in path.items():
            setattr(call, k, v)
        call.cfg_name = f"{cfg.name}|{entry_mode}|{trail_mode}"
        out_calls.append(call)
    return {"summary": pa.summarize(out_calls), "n": len(out_calls), "calls": out_calls}


def main() -> int:
    cfg = pa.load_locked_cfg()
    print(f"Base locked={cfg.name}", flush=True)
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=40, keep_partial=False
    )
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    days = sorted({str(ts.date()) for ts in bars.index})[-22:]
    days_set = set(days)
    window = bars[bars.index.strftime("%Y-%m-%d").isin(days_set)]
    print(f"Window {days[0]}→{days[-1]} ({len(days)} sessions)", flush=True)

    # --- autopsy on base settled calls ---
    base = pa.scan_session(window, settle=True, cfg=cfg)
    o = window["Open"].values
    h = window["High"].values
    l = window["Low"].values
    c = window["Close"].values
    idx = window.index
    hm_to_i = {(pa._day(ts), pa._hm(ts)): i for i, ts in enumerate(idx)}

    win_pre = []
    sl_pre = []
    win_dur = []
    sl_dur = []
    for call in base:
        i = hm_to_i.get((call.day, call.hm))
        if i is None:
            continue
        pre = pre_pattern(o, h, l, c, i, call.side)
        dur = during_path_feats(o, h, l, c, i, call.side, float(call.entry), float(call.risk))
        if call.exit_why == "sl":
            sl_pre.append(pre)
            sl_dur.append(dur)
        elif call.win:
            win_pre.append(pre)
            win_dur.append(dur)

    def rate(rows, key):
        if not rows:
            return None
        return round(100.0 * sum(1 for r in rows if r.get(key)) / len(rows), 1)

    def avg(rows, key):
        xs = [r[key] for r in rows if r.get(key) is not None]
        return round(float(np.mean(xs)), 2) if xs else None

    autopsy = {
        "win": {
            "n": len(win_pre),
            "entry_weak%": rate(win_pre, "entry_weak"),
            "entry_ok_close%": rate(win_pre, "entry_ok_close"),
            "entry_reject%": rate(win_pre, "entry_reject"),
            "engulf%": rate(win_pre, "engulf"),
            "maru%": rate(win_pre, "entry_maru"),
            "prior_exhaust%": rate(win_pre, "prior_exhaust"),
            "prior_reject%": rate(win_pre, "prior_reject"),
            "avg_streak": avg(win_pre, "streak"),
            "avg_body": avg(win_pre, "entry_body"),
            "avg_bars_to_1r": avg(win_dur, "bars_to_1r"),
            "avg_opp_candles": avg(win_dur, "opp_candles"),
            "avg_pin_against": avg(win_dur, "pin_against"),
        },
        "sl": {
            "n": len(sl_pre),
            "entry_weak%": rate(sl_pre, "entry_weak"),
            "entry_ok_close%": rate(sl_pre, "entry_ok_close"),
            "entry_reject%": rate(sl_pre, "entry_reject"),
            "engulf%": rate(sl_pre, "engulf"),
            "maru%": rate(sl_pre, "entry_maru"),
            "prior_exhaust%": rate(sl_pre, "prior_exhaust"),
            "prior_reject%": rate(sl_pre, "prior_reject"),
            "avg_streak": avg(sl_pre, "streak"),
            "avg_body": avg(sl_pre, "entry_body"),
            "avg_bars_to_1r": avg(sl_dur, "bars_to_1r"),
            "avg_opp_candles": avg(sl_dur, "opp_candles"),
            "avg_pin_against": avg(sl_dur, "pin_against"),
        },
    }
    print("AUTOPSY win", autopsy["win"], flush=True)
    print("AUTOPSY sl ", autopsy["sl"], flush=True)

    entry_modes = ["none", "no_weak", "ok_close", "quality_soft", "quality", "reject_or_maru", "streak2", "no_exhaust"]
    trail_modes = ["base", "candle_tight", "candle_hold"]

    results = []
    for em in entry_modes:
        for tm in trail_modes:
            # skip expensive combos that aren't useful
            if em != "none" and tm != "base" and em not in ("quality_soft", "no_weak", "quality"):
                continue
            name = f"{em}+{tm}"
            print(f"  try {name}…", flush=True)
            book = run_book(bars, cfg, entry_mode=em, trail_mode=tm, days_set=days_set)
            s = book["summary"]
            results.append({"name": name, "entry": em, "trail": tm, **s, "n": book["n"]})
            print(
                f"    n={s.get('n')} hit={s.get('hit_pct')} R={s.get('avg_R')} sum={s.get('sum_pts')}",
                flush=True,
            )

    base_s = pa.summarize(base)
    ranked = sorted(
        results,
        key=lambda r: (
            (r.get("hit_pct") or 0),
            (r.get("avg_R") or 0),
            (r.get("sum_pts") or 0),
        ),
        reverse=True,
    )
    # prefer: hit >= base-1, n >= 0.7*base, better avgR or fewer losses feel
    good = [
        r
        for r in ranked
        if (r.get("n") or 0) >= max(40, int(0.65 * (base_s.get("n") or 1)))
        and (r.get("hit_pct") or 0) >= (base_s.get("hit_pct") or 0) - 1.0
        and (r.get("avg_R") or -9) >= (base_s.get("avg_R") or 0) - 0.05
    ]
    best = good[0] if good else ranked[0]

    # also pick best that improves hit with candle entry only (trail base)
    entry_only = [r for r in ranked if r["trail"] == "base"]
    best_entry = entry_only[0] if entry_only else best

    lines = [
        f"# Candle-aware research · locked `{cfg.name}`",
        "",
        f"Window {days[0]} → {days[-1]} ({len(days)} sessions). Understanding candles **before** entry and **during** the move.",
        "",
        "## What candles say (autopsy)",
        "",
        "| Feature | Wins | Hard SL |",
        "|---|---|---|",
        f"| N | {autopsy['win']['n']} | {autopsy['sl']['n']} |",
        f"| Entry weak (doji/pin against/poor close) % | {autopsy['win']['entry_weak%']} | {autopsy['sl']['entry_weak%']} |",
        f"| Entry OK close location % | {autopsy['win']['entry_ok_close%']} | {autopsy['sl']['entry_ok_close%']} |",
        f"| Entry reject (pin/engulf) % | {autopsy['win']['entry_reject%']} | {autopsy['sl']['entry_reject%']} |",
        f"| Engulf % | {autopsy['win']['engulf%']} | {autopsy['sl']['engulf%']} |",
        f"| Marubozu % | {autopsy['win']['maru%']} | {autopsy['sl']['maru%']} |",
        f"| Prior exhaust % | {autopsy['win']['prior_exhaust%']} | {autopsy['sl']['prior_exhaust%']} |",
        f"| Prior reject % | {autopsy['win']['prior_reject%']} | {autopsy['sl']['prior_reject%']} |",
        f"| Avg green/red streak | {autopsy['win']['avg_streak']} | {autopsy['sl']['avg_streak']} |",
        f"| Avg entry body | {autopsy['win']['avg_body']} | {autopsy['sl']['avg_body']} |",
        f"| Avg bars to 1R | {autopsy['win']['avg_bars_to_1r']} | {autopsy['sl']['avg_bars_to_1r']} |",
        f"| Avg opposing candles to 1R | {autopsy['win']['avg_opp_candles']} | {autopsy['sl']['avg_opp_candles']} |",
        f"| Avg pin-against during path | {autopsy['win']['avg_pin_against']} | {autopsy['sl']['avg_pin_against']} |",
        "",
        "## Ablation (entry candle gate × trail mode)",
        "",
        f"Base locked: n={base_s.get('n')} hit={base_s.get('hit_pct')}% avgR={base_s.get('avg_R')} sum={base_s.get('sum_pts')}",
        "",
        "| Variant | N | Hit% | AvgR | Sum |",
        "|---|---:|---:|---:|---:|",
        f"| **BASE** | {base_s.get('n')} | {base_s.get('hit_pct')} | {base_s.get('avg_R')} | {base_s.get('sum_pts')} |",
    ]
    for r in ranked:
        mark = "**" if r["name"] == best["name"] else ""
        lines.append(
            f"| {mark}{r['name']}{mark} | {r.get('n')} | {r.get('hit_pct')} | {r.get('avg_R')} | {r.get('sum_pts')} |"
        )

    lines += [
        "",
        f"## Recommended candle handling",
        "",
        f"**Best overall (research):** `{best['name']}` — n={best.get('n')} hit={best.get('hit_pct')} avgR={best.get('avg_R')} sum={best.get('sum_pts')}",
        f"**Best entry-only:** `{best_entry['name']}` — n={best_entry.get('n')} hit={best_entry.get('hit_pct')} avgR={best_entry.get('avg_R')}",
        "",
        "### Rules to teach the engine",
        "",
        "1. **Before entry:** prefer close in direction (BUY close in upper half), skip doji / pin-against / inside-bar fluff.",
        "2. **Before entry:** skip if prior bar was exhaustion (long wick against our side).",
        "3. **During move:** after 1R, trail under bullish structure; on bearish pin / strong opposing candle, tighten or exit.",
        "4. **During move:** two consecutive opposing closes after trail armed → protect (candle_hold).",
        "",
        "_Held live base remains; candle modes available as Option Blue research upgrade._",
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
                "best": best,
                "best_entry": best_entry,
                "window": {"start": days[0], "end": days[-1], "n": len(days)},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"BEST={best['name']}", flush=True)
    print(f"Wrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
