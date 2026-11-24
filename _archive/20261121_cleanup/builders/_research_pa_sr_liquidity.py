"""RESEARCH — replace FRVP with multi-day candle S/R + liquidity + R:R PA.

Runtime concepts from candles (last ~2 sessions + today):
  • Support / resistance / range from swing clusters + touch behavior
  • Liquidity sweeps (wick beyond level → reclaim) vs trap breaks
  • Candlestick quality at entry
  • Min reward:risk vs next opposing level
  • Structure trail + pin_protect

  python -u prod_live/tests/builders/_research_pa_sr_liquidity.py
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
MD = OUT / "PA_SR_LIQUIDITY_RESEARCH.md"
JS = OUT / "PA_SR_LIQUIDITY_RESEARCH.json"


# ---------------------------------------------------------------------------
# Multi-day S/R + range from candle behavior
# ---------------------------------------------------------------------------

def _swings(h, l, c, i0: int, i1: int, left: int = 3, right: int = 3) -> Tuple[List[float], List[float]]:
    """Fractal swing highs/lows in [i0, i1)."""
    sh, sl = [], []
    for i in range(max(i0 + left, left), min(i1 - right, len(c) - right)):
        hi = float(h[i])
        lo = float(l[i])
        if all(hi >= float(h[i - k]) for k in range(1, left + 1)) and all(
            hi > float(h[i + k]) for k in range(1, right + 1)
        ):
            sh.append(hi)
        if all(lo <= float(l[i - k]) for k in range(1, left + 1)) and all(
            lo < float(l[i + k]) for k in range(1, right + 1)
        ):
            sl.append(lo)
    return sh, sl


def _cluster_levels(levels: List[float], atr: float, tol_atr: float = 0.35) -> List[Dict[str, Any]]:
    if not levels:
        return []
    tol = max(3.0, tol_atr * atr)
    xs = sorted(float(x) for x in levels)
    clusters: List[List[float]] = [[xs[0]]]
    for x in xs[1:]:
        if abs(x - clusters[-1][-1]) <= tol:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    out = []
    for cl in clusters:
        mid = float(np.mean(cl))
        out.append({"price": mid, "n": len(cl), "lo": min(cl), "hi": max(cl)})
    return out


def _touch_score(h, l, c, level: float, i0: int, i1: int, zone: float) -> Dict[str, Any]:
    touches = rejects_up = rejects_dn = crosses = time_near = 0
    for i in range(i0, i1):
        hi, lo, cl = float(h[i]), float(l[i]), float(c[i])
        near = abs(cl - level) <= zone or (lo <= level <= hi)
        if near:
            time_near += 1
            touches += 1
            # rejection: wick through, close back
            if lo < level - 0.15 * zone and cl > level:
                rejects_up += 1  # swept below, closed above = support reject
            if hi > level + 0.15 * zone and cl < level:
                rejects_dn += 1  # swept above, closed below = resist reject
            # cross close through
            if i > i0:
                prev = float(c[i - 1])
                if (prev < level <= cl) or (prev > level >= cl):
                    crosses += 1
    return {
        "touches": touches,
        "rejects_up": rejects_up,
        "rejects_dn": rejects_dn,
        "crosses": crosses,
        "time_near": time_near,
        "strength": touches + 1.5 * rejects_up + 1.5 * rejects_dn - 0.5 * crosses,
    }


def build_sr_map(
    o, h, l, c, atr, idx, i: int, *, lookback_days: int = 2
) -> Dict[str, Any]:
    """Causal S/R/range from last `lookback_days` sessions + today so far."""
    day = pa._day(idx[i])
    # find day starts
    days = []
    last = None
    day_start = {}
    for j in range(0, i + 1):
        d = pa._day(idx[j])
        if d != last:
            days.append(d)
            day_start[d] = j
            last = d
    use_days = days[-(lookback_days + 1) :]  # prior N + today
    i0 = day_start[use_days[0]]
    a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 10.0
    zone = max(4.0, 0.35 * a)

    sh, slv = _swings(h, l, c, i0, i + 1, left=3, right=3)
    # prior day high/low
    pdh = pdl = None
    if len(use_days) >= 2:
        prev = use_days[-2]
        j0 = day_start[prev]
        j1 = day_start[use_days[-1]]
        pdh = float(np.max(h[j0:j1]))
        pdl = float(np.min(l[j0:j1]))
        sh.append(pdh)
        slv.append(pdl)

    # today session so far extremes
    j_today = day_start[day]
    tdh = float(np.max(h[j_today : i + 1]))
    tdl = float(np.min(l[j_today : i + 1]))

    # OR of today if available (~30 bars)
    or_hi = or_lo = None
    if i - j_today >= 29:
        or_hi = float(np.max(h[j_today : j_today + 30]))
        or_lo = float(np.min(l[j_today : j_today + 30]))
        sh.append(or_hi)
        slv.append(or_lo)

    res_clusters = _cluster_levels(sh, a)
    sup_clusters = _cluster_levels(slv, a)

    supports, resists = [], []
    for cl in sup_clusters:
        sc = _touch_score(h, l, c, cl["price"], i0, i + 1, zone)
        supports.append({**cl, **sc, "kind": "support"})
    for cl in res_clusters:
        sc = _touch_score(h, l, c, cl["price"], i0, i + 1, zone)
        resists.append({**cl, **sc, "kind": "resist"})

    supports.sort(key=lambda x: (-x["strength"], -x["n"]))
    resists.sort(key=lambda x: (-x["strength"], -x["n"]))

    # range: densest price band from closes histogram (where price "stayed")
    closes = [float(c[j]) for j in range(max(i0, i - 400), i + 1)]
    rng_lo = rng_hi = rng_mid = None
    if len(closes) >= 40:
        lo_p, hi_p = np.percentile(closes, 15), np.percentile(closes, 85)
        # refine: bin and find mode cluster
        bins = np.linspace(min(closes), max(closes), 24)
        hist, edges = np.histogram(closes, bins=bins)
        top = int(np.argmax(hist))
        # expand while dense
        left = right = top
        thr = max(1, 0.45 * hist[top])
        while left > 0 and hist[left - 1] >= thr:
            left -= 1
        while right < len(hist) - 1 and hist[right + 1] >= thr:
            right += 1
        rng_lo = float(edges[left])
        rng_hi = float(edges[right + 1])
        rng_mid = 0.5 * (rng_lo + rng_hi)

    entry = float(c[i])
    # nearest support below / resist above
    sup_below = [s for s in supports if s["price"] <= entry + zone]
    res_above = [r for r in resists if r["price"] >= entry - zone]
    nearest_sup = max(sup_below, key=lambda s: s["price"]) if sup_below else None
    nearest_res = min(res_above, key=lambda r: r["price"]) if res_above else None

    return {
        "atr": a,
        "zone": zone,
        "supports": supports[:8],
        "resists": resists[:8],
        "nearest_sup": nearest_sup,
        "nearest_res": nearest_res,
        "pdh": pdh,
        "pdl": pdl,
        "tdh": tdh,
        "tdl": tdl,
        "or_hi": or_hi,
        "or_lo": or_lo,
        "range_lo": rng_lo,
        "range_hi": rng_hi,
        "range_mid": rng_mid,
    }


def liquidity_read(o, h, l, c, atr, i: int, side: str, sr: Dict[str, Any]) -> Dict[str, Any]:
    """Detect liquidity grab vs trap at runtime candle behavior."""
    a = sr["atr"]
    zone = sr["zone"]
    cur = pa._candle_bar(o, h, l, c, i)
    prev = pa._candle_bar(o, h, l, c, i - 1) if i >= 1 else None
    entry = float(c[i])

    # levels to watch
    levels = []
    for s in sr.get("supports") or []:
        levels.append(("S", s["price"], s.get("strength", 0)))
    for r in sr.get("resists") or []:
        levels.append(("R", r["price"], r.get("strength", 0)))
    if sr.get("pdh"):
        levels.append(("R", sr["pdh"], 2.0))
    if sr.get("pdl"):
        levels.append(("S", sr["pdl"], 2.0))
    if sr.get("or_hi"):
        levels.append(("R", sr["or_hi"], 1.5))
    if sr.get("or_lo"):
        levels.append(("S", sr["or_lo"], 1.5))

    swept_sup = swept_res = False
    sweep_level = None
    for kind, lv, _st in levels:
        if kind == "S" and float(l[i]) < lv - 0.1 * zone and entry > lv:
            # swept support liquidity then reclaimed
            swept_sup = True
            sweep_level = lv
        if kind == "R" and float(h[i]) > lv + 0.1 * zone and entry < lv:
            swept_res = True
            sweep_level = lv

    # trap: break beyond level with close beyond, but tiny body / long wick against next
    trap_break = False
    if side == "BUY" and sr.get("nearest_res"):
        lv = sr["nearest_res"]["price"]
        # chasing into resistance / closing into it
        if entry >= lv - 0.4 * zone and cur["upper_frac"] >= 0.45:
            trap_break = True
        # breakout bar that is exhaustion (long upper wick)
        if entry > lv and cur["upper_frac"] >= 0.50 and cur["body_frac"] < 0.45:
            trap_break = True
    if side == "SELL" and sr.get("nearest_sup"):
        lv = sr["nearest_sup"]["price"]
        if entry <= lv + 0.4 * zone and cur["lower_frac"] >= 0.45:
            trap_break = True
        if entry < lv and cur["lower_frac"] >= 0.50 and cur["body_frac"] < 0.45:
            trap_break = True

    # liquidity grab favoring our side (classic stop-run then go)
    liq_favor = (side == "BUY" and swept_sup) or (side == "SELL" and swept_res)
    # fake break against us
    liq_against = (side == "BUY" and swept_res and not cur["bull"]) or (
        side == "SELL" and swept_sup and not cur["bear"]
    )

    # inside range mid = chop trap risk
    in_mid_range = False
    if sr.get("range_lo") is not None and sr.get("range_hi") is not None:
        span = max(sr["range_hi"] - sr["range_lo"], 1e-9)
        loc = (entry - sr["range_lo"]) / span
        in_mid_range = 0.35 <= loc <= 0.65

    return {
        "swept_sup": swept_sup,
        "swept_res": swept_res,
        "sweep_level": sweep_level,
        "liq_favor": liq_favor,
        "liq_against": liq_against,
        "trap_break": trap_break,
        "in_mid_range": in_mid_range,
        "pin_favor": (side == "BUY" and cur["pin_bull"]) or (side == "SELL" and cur["pin_bear"]),
        "engulf_favor": False,  # filled below if needed
    }


def reward_risk(side: str, entry: float, sl: float, sr: Dict[str, Any]) -> Dict[str, Any]:
    risk = abs(entry - sl)
    if risk < 1e-9:
        return {"risk": risk, "reward": 0.0, "rr": 0.0, "target": None}
    if side == "BUY":
        # target = nearest strong resist above, else range_hi / pdh
        cands = []
        if sr.get("nearest_res"):
            cands.append(sr["nearest_res"]["price"])
        if sr.get("range_hi"):
            cands.append(sr["range_hi"])
        if sr.get("pdh") and sr["pdh"] > entry:
            cands.append(sr["pdh"])
        if sr.get("tdh") and sr["tdh"] > entry:
            cands.append(sr["tdh"] + sr["atr"])  # room beyond today high
        tgt = min([x for x in cands if x > entry + 0.3 * risk], default=entry + 2.0 * risk)
    else:
        cands = []
        if sr.get("nearest_sup"):
            cands.append(sr["nearest_sup"]["price"])
        if sr.get("range_lo"):
            cands.append(sr["range_lo"])
        if sr.get("pdl") and sr["pdl"] < entry:
            cands.append(sr["pdl"])
        if sr.get("tdl") and sr["tdl"] < entry:
            cands.append(sr["tdl"] - sr["atr"])
        tgt = max([x for x in cands if x < entry - 0.3 * risk], default=entry - 2.0 * risk)
    reward = abs(tgt - entry)
    return {"risk": risk, "reward": reward, "rr": reward / risk, "target": tgt}


def entry_gate_sr(
    side: str,
    o, h, l, c, i: int,
    sr: Dict[str, Any],
    liq: Dict[str, Any],
    rr: Dict[str, Any],
    mode: str,
) -> Tuple[bool, str]:
    """Composite runtime gate — no FRVP."""
    # always apply candle read_v3-ish base if mode asks
    c_ok, c_note = pa.candle_entry_ok(o, h, l, c, i, side, "read_v3" if "v3" in mode or mode.startswith("full") else "no_exhaust")
    if mode in ("pa_only",):
        return True, "pa_only"
    if mode == "no_trap":
        if liq["trap_break"] or liq["liq_against"]:
            return False, "block_trap"
        return True, "ok_no_trap"
    if mode == "liq_favor":
        if not liq["liq_favor"]:
            return False, "need_liq_grab"
        if liq["trap_break"]:
            return False, "block_trap"
        return True, "ok_liq"
    if mode == "rr15":
        if rr["rr"] < 1.5:
            return False, f"rr<{rr['rr']:.2f}"
        if liq["trap_break"]:
            return False, "block_trap"
        return True, f"ok_rr{rr['rr']:.1f}"
    if mode == "rr20":
        if rr["rr"] < 2.0:
            return False, f"rr<{rr['rr']:.2f}"
        if liq["trap_break"]:
            return False, "block_trap"
        return True, f"ok_rr{rr['rr']:.1f}"
    if mode == "edge":
        # prefer break/hold at range edge, not mid
        if liq["in_mid_range"] and not liq["liq_favor"]:
            return False, "mid_range"
        if liq["trap_break"] or liq["liq_against"]:
            return False, "block_trap"
        return True, "ok_edge"
    if mode == "sr_align":
        # BUY near support or above range mid after reclaim; SELL near resist
        if side == "BUY":
            ns = sr.get("nearest_sup")
            if ns and (entry_dist := abs(float(c[i]) - ns["price"])) > 1.2 * sr["atr"]:
                if not liq["liq_favor"] and sr.get("range_mid") and float(c[i]) < sr["range_mid"]:
                    return False, "far_from_support"
        else:
            nr = sr.get("nearest_res")
            if nr and abs(float(c[i]) - nr["price"]) > 1.2 * sr["atr"]:
                if not liq["liq_favor"] and sr.get("range_mid") and float(c[i]) > sr["range_mid"]:
                    return False, "far_from_resist"
        if liq["trap_break"]:
            return False, "block_trap"
        return True, "ok_sr_align"
    if mode == "full_v1":
        # accuracy stack: candle v3 + no trap + rr>=1.5 + not mid-range unless liq grab
        if not c_ok:
            return False, c_note or "candle"
        if liq["trap_break"] or liq["liq_against"]:
            return False, "block_trap"
        if rr["rr"] < 1.5:
            return False, "rr_low"
        if liq["in_mid_range"] and not liq["liq_favor"]:
            return False, "mid_range"
        return True, f"full_v1 rr={rr['rr']:.1f}"
    if mode == "full_v2":
        # looser rr, require candle no_exhaust + no trap + (liq_favor OR edge)
        c_ok2, _ = pa.candle_entry_ok(o, h, l, c, i, side, "no_exhaust")
        if not c_ok2:
            return False, "candle"
        if liq["trap_break"] or liq["liq_against"]:
            return False, "block_trap"
        if rr["rr"] < 1.2:
            return False, "rr_low"
        if liq["in_mid_range"] and not liq["liq_favor"] and not liq["pin_favor"]:
            return False, "mid_range"
        return True, f"full_v2 rr={rr['rr']:.1f}"
    if mode == "full_v3":
        # max accuracy: v3 candle + liq_favor OR (rr>=2 and edge) + no trap
        if not c_ok:
            return False, c_note or "candle"
        if liq["trap_break"] or liq["liq_against"]:
            return False, "block_trap"
        if liq["liq_favor"]:
            return True, "full_v3_liq"
        if rr["rr"] >= 2.0 and not liq["in_mid_range"]:
            return True, f"full_v3_rr{rr['rr']:.1f}"
        return False, "need_liq_or_rr2"
    return True, "pass"


def sl_from_sr(side: str, entry: float, struct_sl: float, sr: Dict[str, Any], mode: str) -> Tuple[float, str]:
    """Optionally bias SL to nearest structural support/resist beyond structure."""
    if mode == "struct":
        return struct_sl, "struct"
    ns = sr.get("nearest_sup")
    nr = sr.get("nearest_res")
    buf = 0.75
    if side == "BUY":
        cands = [struct_sl]
        if ns and ns["price"] < entry:
            cands.append(ns["price"] - buf)
        if sr.get("pdl") and sr["pdl"] < entry:
            cands.append(sr["pdl"] - buf)
        # tighter of structure and nearest support (but keep risk sane)
        sl = max(cands) if mode == "sr_tight" else min(cands)  # sr_tight = closer to entry
        if mode == "sr_prefer":
            # prefer support SL if not much wider than structure
            if ns and ns["price"] < entry:
                cand = ns["price"] - buf
                if entry - cand <= 1.35 * (entry - struct_sl):
                    sl = cand
                else:
                    sl = struct_sl
            else:
                sl = struct_sl
        return float(sl), mode
    cands = [struct_sl]
    if nr and nr["price"] > entry:
        cands.append(nr["price"] + buf)
    if sr.get("pdh") and sr["pdh"] > entry:
        cands.append(sr["pdh"] + buf)
    if mode == "sr_tight":
        sl = min(cands)
    elif mode == "sr_prefer":
        if nr and nr["price"] > entry:
            cand = nr["price"] + buf
            if cand - entry <= 1.35 * (struct_sl - entry):
                sl = cand
            else:
                sl = struct_sl
        else:
            sl = struct_sl
    else:
        sl = struct_sl
    return float(sl), mode


def settle_trail(o, h, l, c, idx, entry_i, side, entry, sl0, risk, cfg, trail_mode: str):
    # reuse pa settle with cfg candle_trail_mode
    cfg2 = replace(cfg, candle_trail_mode=trail_mode, use_frvp=False)
    return pa.settle_path(o, h, l, c, idx, entry_i, side, entry, sl0, risk, cfg2)


def run_variant(
    bars, base_cfg, days_set, *, gate: str, sl_mode: str, trail: str, lookback_days: int = 2
) -> Dict[str, Any]:
    cfg = replace(
        base_cfg,
        use_frvp=False,
        name=f"sr_{gate}_{sl_mode}_{trail}",
        candle_entry_mode="none",  # we gate ourselves
        candle_trail_mode=trail,
    )
    work = pa.norm_1m(bars)
    work = work[work.index.strftime("%Y-%m-%d").isin(days_set)]
    # Get PA setups without FRVP/candle — raw structure
    raw = pa.scan_session(work, settle=False, cfg=cfg)
    o = work["Open"].values
    h = work["High"].values
    l = work["Low"].values
    c = work["Close"].values
    atr = pa.atr14(h, l, c)
    idx = work.index
    hm_to_i = {(pa._day(ts), pa._hm(ts)): i for i, ts in enumerate(idx)}

    out = []
    for call in raw:
        i = hm_to_i.get((call.day, call.hm))
        if i is None:
            continue
        sr = build_sr_map(o, h, l, c, atr, idx, i, lookback_days=lookback_days)
        liq = liquidity_read(o, h, l, c, atr, i, call.side, sr)
        struct_sl, struct_risk, _ = pa.structure_sl(call.side, o, h, l, c, i, cfg)
        sl, _slm = sl_from_sr(call.side, float(call.entry), struct_sl, sr, sl_mode)
        risk = abs(float(call.entry) - sl)
        if risk < cfg.min_risk or risk > cfg.max_risk:
            continue
        rr = reward_risk(call.side, float(call.entry), sl, sr)
        ok, note = entry_gate_sr(call.side, o, h, l, c, i, sr, liq, rr, gate)
        if not ok:
            continue
        path = settle_trail(o, h, l, c, idx, i, call.side, float(call.entry), sl, risk, cfg, trail)
        for k, v in path.items():
            setattr(call, k, v)
        call.stop_loss = round(sl, 2)
        call.risk = round(risk, 2)
        call.reason = f"{call.reason} · {note} · RR~{rr['rr']:.1f}"
        call.cfg_name = cfg.name
        out.append(call)
    return {"summary": pa.summarize(out), "n": len(out), "calls": out}


def main() -> int:
    locked = pa.load_locked_cfg()
    print(f"Compare vs locked={locked.name} frvp={locked.use_frvp} candle={locked.candle_entry_mode}", flush=True)
    raw, err = kite_data.fetch_historical_candles("NIFTY", "minute", days=40, keep_partial=False)
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    days = sorted({str(ts.date()) for ts in bars.index})[-22:]
    days_set = set(days)
    # need extra lookback days in the frame
    all_days = sorted({str(ts.date()) for ts in bars.index})
    # keep 2 days before window start for S/R
    start_i = max(0, all_days.index(days[0]) - 2)
    research_days = set(all_days[start_i:])
    window_bars = bars[bars.index.strftime("%Y-%m-%d").isin(research_days)]

    # baseline locked (with FRVP)
    base_locked = pa.scan_session(
        bars[bars.index.strftime("%Y-%m-%d").isin(days_set)], settle=True, cfg=locked
    )
    base_s = pa.summarize(base_locked)
    print(f"LOCKED n={base_s.get('n')} hit={base_s.get('hit_pct')} R={base_s.get('avg_R')} sum={base_s.get('sum_pts')}", flush=True)

    # PA only no FRVP
    no_frvp = replace(locked, use_frvp=False, name="pa_no_frvp", candle_entry_mode="none", candle_trail_mode="base")
    base_pa = pa.scan_session(
        bars[bars.index.strftime("%Y-%m-%d").isin(days_set)], settle=True, cfg=no_frvp
    )
    pa_s = pa.summarize(base_pa)
    print(f"PA_NO_FRVP n={pa_s.get('n')} hit={pa_s.get('hit_pct')} R={pa_s.get('avg_R')} sum={pa_s.get('sum_pts')}", flush=True)

    gates = [
        "pa_only",
        "no_trap",
        "edge",
        "sr_align",
        "rr15",
        "rr20",
        "liq_favor",
        "full_v1",
        "full_v2",
        "full_v3",
    ]
    sl_modes = ["struct", "sr_prefer"]
    trails = ["base", "pin_protect"]

    results = []
    # prioritize combos
    combos = []
    for g in gates:
        combos.append((g, "struct", "pin_protect"))
    for g in ("full_v1", "full_v2", "full_v3", "no_trap", "rr15", "edge"):
        combos.append((g, "sr_prefer", "pin_protect"))
    for g in ("full_v1", "full_v2", "no_trap"):
        combos.append((g, "struct", "base"))

    seen = set()
    for g, slm, tr in combos:
        key = f"{g}|{slm}|{tr}"
        if key in seen:
            continue
        seen.add(key)
        print(f"  try {key}…", flush=True)
        book = run_variant(window_bars, locked, days_set, gate=g, sl_mode=slm, trail=tr, lookback_days=2)
        s = book["summary"]
        results.append({"name": key, "gate": g, "sl": slm, "trail": tr, **s, "n": book["n"]})
        print(f"    n={s.get('n')} hit={s.get('hit_pct')} R={s.get('avg_R')} sum={s.get('sum_pts')}", flush=True)

    ranked = sorted(
        results,
        key=lambda r: ((r.get("hit_pct") or 0), (r.get("avg_R") or 0), (r.get("sum_pts") or 0)),
        reverse=True,
    )
    n_floor = max(25, int(0.45 * (base_s.get("n") or 50)))
    practical = [
        r
        for r in ranked
        if (r.get("n") or 0) >= n_floor
        and (r.get("hit_pct") or 0) >= max(65.0, (base_s.get("hit_pct") or 0) - 2)
    ]
    practical_sum = sorted(
        practical,
        key=lambda r: ((r.get("hit_pct") or 0), (r.get("avg_R") or 0), (r.get("sum_pts") or 0)),
        reverse=True,
    )
    best = practical_sum[0] if practical_sum else (ranked[0] if ranked else None)
    best_sum = sorted(
        [r for r in ranked if (r.get("n") or 0) >= n_floor],
        key=lambda r: ((r.get("sum_pts") or 0), (r.get("hit_pct") or 0)),
        reverse=True,
    )
    best_sum_pick = best_sum[0] if best_sum else best

    lines = [
        "# PA S/R + Liquidity research (NO FRVP)",
        "",
        f"Window {days[0]} → {days[-1]} (22 sessions). S/R from last 2 sessions’ candle behavior.",
        "",
        "## Baselines",
        "",
        f"| Book | N | Hit% | AvgR | Sum |",
        f"|---|---:|---:|---:|---:|",
        f"| Locked FRVP+read_v3 | {base_s.get('n')} | {base_s.get('hit_pct')} | {base_s.get('avg_R')} | {base_s.get('sum_pts')} |",
        f"| PA only (no FRVP/candle) | {pa_s.get('n')} | {pa_s.get('hit_pct')} | {pa_s.get('avg_R')} | {pa_s.get('sum_pts')} |",
        "",
        "## Runtime concepts tested",
        "",
        "1. **Multi-day S/R** — swing clusters + PDH/PDL + OR + touch/reject/cross scores",
        "2. **Range** — where price stayed (histogram density band)",
        "3. **Liquidity** — wick beyond level then reclaim (favor) vs trap break into level",
        "4. **R:R** — distance to next opposing level / risk",
        "5. **Candles** — read_v3 / no_exhaust nested in full_* gates",
        "6. **Trail** — structure + pin_protect",
        "",
        "## Ablation",
        "",
        "| Variant | N | Hit% | AvgR | Sum |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in ranked:
        mark = "**" if best and r["name"] == best["name"] else ""
        lines.append(
            f"| {mark}{r['name']}{mark} | {r.get('n')} | {r.get('hit_pct')} | {r.get('avg_R')} | {r.get('sum_pts')} |"
        )
    lines += [
        "",
        "## Recommendation",
        "",
        f"**Best accuracy (volume floor {n_floor}):** `{best['name'] if best else None}` — "
        f"n={best.get('n') if best else None} hit={best.get('hit_pct') if best else None} "
        f"avgR={best.get('avg_R') if best else None} sum={best.get('sum_pts') if best else None}",
        f"**Best sum:** `{best_sum_pick['name'] if best_sum_pick else None}` — "
        f"n={best_sum_pick.get('n') if best_sum_pick else None} hit={best_sum_pick.get('hit_pct') if best_sum_pick else None} "
        f"sum={best_sum_pick.get('sum_pts') if best_sum_pick else None}",
        "",
        "_Wire winner with use_frvp=false into locked cfg._",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    MD.write_text("\n".join(lines), encoding="utf-8")
    JS.write_text(
        json.dumps(
            {
                "locked": base_s,
                "pa_no_frvp": pa_s,
                "ranked": results,
                "best": best,
                "best_sum": best_sum_pick,
                "window": {"start": days[0], "end": days[-1]},
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"BEST={best['name'] if best else None}", flush=True)
    print(f"Wrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
