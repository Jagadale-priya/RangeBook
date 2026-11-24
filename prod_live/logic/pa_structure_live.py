"""Causal price-action live book — structure SL, no fixed ±target.

v2 improvements (from loss autopsy):
  • MIN_RISK ↑ — losses clustered on tight SL / noise
  • Strict HTF — no flat
  • OR-side align — only with break direction vs OR mid
  • Sweep quality — depth + wick + reclaim beyond prior extreme
  • Break momentum — 2-of-3 closes agree
  • Side-flip + post-loss cooldown
  • Later open (after OR settled)

Live: evaluate on each new closed bar; notify entry with dynamic SL.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HOLD = ROOT / "prod_live" / "holding_accurate" / "pa_structure"
LEDGER = HOLD / "live_session_calls.json"

DESK = "PA_STRUCTURE_SL_LIVE"
ACC_TAG = "PA_STRUCTURE_RESEARCH"
LOGIC_VER = "v3d"


@dataclass
class PaConfig:
    """PA structure + runtime S/R/liquidity from candles (FRVP optional/off)."""

    name: str = "pa_sr"
    or_bars: int = 30
    swing_n: int = 5
    sl_buffer: float = 0.75
    min_risk: float = 3.0
    max_risk: float = 22.0
    trade_lo: int = 9 * 60 + 30
    trade_hi: int = 14 * 60 + 45
    max_hold_bars: int = 90
    max_calls_day: int = 12  # not hard-3 — cooldown gates spam
    cooldown_bars: int = 10
    body_min: float = 0.55
    break_atr_frac: float = 0.15
    sweep_depth_atr: float = 0.10
    sweep_wick_frac: float = 0.0
    reclaim_beyond: float = 0.0
    strict_htf: bool = False
    or_side_align: bool = True
    require_break_mom: bool = False
    allow_sweep: bool = True
    allow_break: bool = True
    allow_or_retest: bool = True
    side_flip_cooldown: int = 12
    loss_extra_cooldown: int = 0
    trail_arm_R: float = 1.0
    # --- continuous candle read (entry window + trail) ---
    # none | no_exhaust | quality_soft | quality | read_v3
    candle_entry_mode: str = "none"
    # base | pin_protect
    candle_trail_mode: str = "base"
    # --- multi-day candle S/R + liquidity (replaces FRVP when set) ---
    # none | full_v1 | full_v3 | no_trap | rr_accurate
    # adv_real_tgt | adv_near_wall | adv_no_far | adv_v1
    sr_gate: str = "none"
    sr_lookback_days: int = 2
    min_rr: float = 1.5
    # When True (rr_accurate gate): refuse synthetic entry±2R; need real opposing S/R
    require_real_target: bool = False
    # adv_* knobs (R units to nearest opposing S/R)
    near_wall_max_R: float = 1.5
    far_empty_min_R: float = 3.0
    # --- SL-only kill (Option Blue research: never remove winners) ---
    # none | chase_v1
    sl_kill_mode: str = "none"
    # --- FRVP (legacy; kept off in locked v3) ---
    use_frvp: bool = False
    frvp_mode: str = "near_level"  # near_level | bounce_sr | vah_break
    frvp_anchor: str = "or30"  # or30 | session_expand
    frvp_zone_atr: float = 0.40
    frvp_rows: int = 48
    frvp_refresh_every: int = 15
    frvp_prefer_sl: bool = True


LOCKED_CFG_PATH = HOLD / "locked_cfg.json"


def _cfg_from_dict(d: Dict[str, Any]) -> PaConfig:
    fields = {f.name for f in PaConfig.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    return PaConfig(**{k: v for k, v in d.items() if k in fields})


def load_locked_cfg() -> PaConfig:
    HOLD.mkdir(parents=True, exist_ok=True)
    if LOCKED_CFG_PATH.exists():
        try:
            return _cfg_from_dict(json.loads(LOCKED_CFG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return PaConfig(name="v2")


def save_locked_cfg(cfg: PaConfig) -> None:
    HOLD.mkdir(parents=True, exist_ok=True)
    LOCKED_CFG_PATH.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")


# Live default — overwritten by locked_cfg.json when present
CFG = load_locked_cfg()

# v1 snapshot for A/B
CFG_V1 = PaConfig(
    name="v1",
    min_risk=3.0,
    max_risk=22.0,
    trade_lo=9 * 60 + 30,
    trade_hi=14 * 60 + 45,
    max_calls_day=4,
    cooldown_bars=12,
    body_min=0.45,
    break_atr_frac=0.15,
    sweep_depth_atr=0.10,
    sweep_wick_frac=0.0,
    reclaim_beyond=0.0,
    strict_htf=False,
    or_side_align=False,
    require_break_mom=False,
    side_flip_cooldown=0,
    loss_extra_cooldown=0,
)


@dataclass
class PaCall:
    day: str
    hm: str
    side: str
    setup: str
    entry: float
    stop_loss: float
    risk: float
    reason: str
    bar_i: int
    htf_bias: Optional[str] = None
    logic_ver: str = LOGIC_VER
    cfg_name: str = "v2"
    exit_hm: Optional[str] = None
    exit_px: Optional[float] = None
    exit_why: Optional[str] = None
    pts: Optional[float] = None
    R: Optional[float] = None
    win: Optional[bool] = None
    mfe: Optional[float] = None
    mae: Optional[float] = None
    hit_1R: Optional[bool] = None
    hit_2R: Optional[bool] = None
    hit_3R: Optional[bool] = None
    live_fire: bool = False
    fired_at: Optional[str] = None
    desk: str = DESK
    accuracy_tag: str = ACC_TAG
    tags: List[str] = field(default_factory=lambda: [DESK, ACC_TAG])

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _hm(ts) -> str:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("Asia/Kolkata")
    return f"{int(t.hour):02d}:{int(t.minute):02d}"


def _mins(ts) -> int:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("Asia/Kolkata")
    return int(t.hour * 60 + t.minute)


def _day(ts) -> str:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("Asia/Kolkata")
    return str(t.date())


def norm_1m(df: pd.DataFrame, *, all_hours: bool = False) -> pd.DataFrame:
    w = df.copy()
    if getattr(w.index, "tz", None) is not None:
        w.index = w.index.tz_convert("Asia/Kolkata")
    else:
        w.index = w.index.tz_localize("Asia/Kolkata")
    rename = {c: str(c).title() for c in w.columns}
    w = w.rename(columns=rename)
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in w.columns]
    w = w[cols].astype(float).sort_index()
    w = w[~w.index.duplicated(keep="last")]
    if all_hours:
        return w
    hm = w.index.strftime("%H:%M")
    return w[(hm >= "09:15") & (hm <= "15:29")]


def _candle_bar(o, h, l, c, i: int) -> Dict[str, Any]:
    """Single-bar candle anatomy for entry / trail decisions."""
    op, hi, lo, cl = float(o[i]), float(h[i]), float(l[i]), float(c[i])
    rng = max(hi - lo, 1e-9)
    body = abs(cl - op)
    body_frac = body / rng
    upper = hi - max(op, cl)
    lower = min(op, cl) - lo
    bull = cl > op
    bear = cl < op
    return {
        "bull": bull,
        "bear": bear,
        "body_frac": body_frac,
        "upper_frac": upper / rng,
        "lower_frac": lower / rng,
        "doji": body_frac < 0.18,
        "pin_bull": lower / rng >= 0.55 and body_frac <= 0.35 and upper / rng <= 0.25,
        "pin_bear": upper / rng >= 0.55 and body_frac <= 0.35 and lower / rng <= 0.25,
        "close_loc": (cl - lo) / rng,
        "inside": (
            i >= 1 and hi <= float(h[i - 1]) and lo >= float(l[i - 1])
        ),
    }


def _window_candle_stats(o, h, l, c, i: int, side: str, look: int = 5) -> Dict[str, Any]:
    """Continuous 5-bar candle story ending at entry."""
    j0 = max(0, i - look + 1)
    bodies: List[float] = []
    pin_opp = 0
    for j in range(j0, i + 1):
        f = _candle_bar(o, h, l, c, j)
        bodies.append(float(f["body_frac"]))
        if side == "BUY" and f["pin_bear"]:
            pin_opp += 1
        elif side == "SELL" and f["pin_bull"]:
            pin_opp += 1
    return {
        "avg_body": float(np.mean(bodies)) if bodies else 0.0,
        "pin_opp": pin_opp,
    }


def candle_entry_ok(o, h, l, c, i: int, side: str, mode: str) -> Tuple[bool, str]:
    """Gate calls by continuous candle read before/at entry. Returns (ok, note).

    Research (22 sessions on locked frvp_vah_break):
      • no_exhaust: prior exhaust is poison (SL 18.5% vs win 5.6%)
      • read_v3: close-ok + avg body ≥0.40 + no pin-against in 5-bar window → ~78–80% hit
      • stall_cut / with_only trails underperform; pin_protect is the trail add-on that holds
    """
    if not mode or mode == "none":
        return True, ""
    cur = _candle_bar(o, h, l, c, i)
    prev = _candle_bar(o, h, l, c, i - 1) if i >= 1 else None

    if side == "BUY":
        ok_close = cur["close_loc"] >= 0.55 and cur["bull"]
        weak = cur["doji"] or cur["pin_bear"] or cur["close_loc"] < 0.40
        exhaust = bool(
            prev
            and (prev["pin_bear"] or (prev["upper_frac"] >= 0.55 and prev["bull"]))
        )
        reject = cur["pin_bull"]
    else:
        ok_close = cur["close_loc"] <= 0.45 and cur["bear"]
        weak = cur["doji"] or cur["pin_bull"] or cur["close_loc"] > 0.60
        exhaust = bool(
            prev
            and (prev["pin_bull"] or (prev["lower_frac"] >= 0.55 and prev["bear"]))
        )
        reject = cur["pin_bear"]

    if mode == "no_exhaust":
        if exhaust or weak:
            return False, "candle_block_exhaust/weak"
        return True, "candle_ok_no_exhaust"
    if mode == "quality_soft":
        if not ok_close or cur["doji"] or cur["inside"]:
            return False, "candle_block_soft"
        return True, "candle_ok_soft"
    if mode == "quality":
        body_ok = cur["body_frac"] >= 0.50 or reject
        if not (ok_close and not cur["doji"] and not exhaust and body_ok):
            return False, "candle_block_quality"
        return True, "candle_ok_quality"
    if mode == "read_v3":
        # continuous: no_exhaust + close in direction + solid window bodies + no pin-against
        if exhaust or weak:
            return False, "candle_block_exhaust/weak"
        if not ok_close:
            return False, "candle_block_close"
        win = _window_candle_stats(o, h, l, c, i, side, look=5)
        if win["avg_body"] < 0.40 or win["pin_opp"] > 0:
            return False, "candle_block_window"
        return True, "candle_ok_read_v3"
    return True, ""


# ---------------------------------------------------------------------------
# Multi-day candle S/R + range + liquidity (runtime, no FRVP)
# ---------------------------------------------------------------------------

def _swing_points(h, l, i0: int, i1: int, left: int = 3, right: int = 3) -> Tuple[List[float], List[float]]:
    sh: List[float] = []
    sl: List[float] = []
    for i in range(max(i0 + left, left), min(i1 - right, len(h) - right)):
        hi, lo = float(h[i]), float(l[i])
        if all(hi >= float(h[i - k]) for k in range(1, left + 1)) and all(
            hi > float(h[i + k]) for k in range(1, right + 1)
        ):
            sh.append(hi)
        if all(lo <= float(l[i - k]) for k in range(1, left + 1)) and all(
            lo < float(l[i + k]) for k in range(1, right + 1)
        ):
            sl.append(lo)
    return sh, sl


def _cluster_px(levels: List[float], atr: float, tol_atr: float = 0.35) -> List[Dict[str, Any]]:
    if not levels:
        return []
    tol = max(3.0, tol_atr * atr)
    xs = sorted(float(x) for x in levels)
    groups: List[List[float]] = [[xs[0]]]
    for x in xs[1:]:
        if abs(x - groups[-1][-1]) <= tol:
            groups[-1].append(x)
        else:
            groups.append([x])
    return [{"price": float(np.mean(g)), "n": len(g)} for g in groups]


def build_sr_map(o, h, l, c, atr, idx, i: int, *, lookback_days: int = 2) -> Dict[str, Any]:
    """Causal support/resistance/range from last N sessions + today so far."""
    day = _day(idx[i])
    days: List[str] = []
    day_start: Dict[str, int] = {}
    last = None
    for j in range(0, i + 1):
        d = _day(idx[j])
        if d != last:
            days.append(d)
            day_start[d] = j
            last = d
    use = days[-(lookback_days + 1) :]
    i0 = day_start[use[0]]
    a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 10.0
    zone = max(4.0, 0.35 * a)

    sh, slv = _swing_points(h, l, i0, i + 1)
    pdh = pdl = None
    if len(use) >= 2:
        prev = use[-2]
        j0, j1 = day_start[prev], day_start[use[-1]]
        pdh, pdl = float(np.max(h[j0:j1])), float(np.min(l[j0:j1]))
        sh.append(pdh)
        slv.append(pdl)
    j_today = day_start[day]
    if i - j_today >= 29:
        sh.append(float(np.max(h[j_today : j_today + 30])))
        slv.append(float(np.min(l[j_today : j_today + 30])))

    supports = _cluster_px(slv, a)
    resists = _cluster_px(sh, a)
    # touch / reject strength
    for lvl in supports + resists:
        touches = rejects = 0
        px = lvl["price"]
        for j in range(i0, i + 1):
            hi, lo, cl = float(h[j]), float(l[j]), float(c[j])
            if abs(cl - px) <= zone or (lo <= px <= hi):
                touches += 1
                if lo < px - 0.15 * zone and cl > px:
                    rejects += 1
                if hi > px + 0.15 * zone and cl < px:
                    rejects += 1
        lvl["strength"] = touches + 1.5 * rejects

    supports.sort(key=lambda x: (-x.get("strength", 0), -x["n"]))
    resists.sort(key=lambda x: (-x.get("strength", 0), -x["n"]))

    closes = [float(c[j]) for j in range(max(i0, i - 400), i + 1)]
    rng_lo = rng_hi = rng_mid = None
    if len(closes) >= 40:
        bins = np.linspace(min(closes), max(closes), 24)
        hist, edges = np.histogram(closes, bins=bins)
        top = int(np.argmax(hist))
        left = right = top
        thr = max(1, 0.45 * hist[top])
        while left > 0 and hist[left - 1] >= thr:
            left -= 1
        while right < len(hist) - 1 and hist[right + 1] >= thr:
            right += 1
        rng_lo, rng_hi = float(edges[left]), float(edges[right + 1])
        rng_mid = 0.5 * (rng_lo + rng_hi)

    entry = float(c[i])
    sup_below = [s for s in supports if s["price"] <= entry + zone]
    res_above = [r for r in resists if r["price"] >= entry - zone]
    return {
        "atr": a,
        "zone": zone,
        "supports": supports[:8],
        "resists": resists[:8],
        "nearest_sup": max(sup_below, key=lambda s: s["price"]) if sup_below else None,
        "nearest_res": min(res_above, key=lambda r: r["price"]) if res_above else None,
        "pdh": pdh,
        "pdl": pdl,
        "range_lo": rng_lo,
        "range_hi": rng_hi,
        "range_mid": rng_mid,
    }


def liquidity_read(o, h, l, c, i: int, side: str, sr: Dict[str, Any]) -> Dict[str, Any]:
    """Liquidity grab vs trap from candle behavior at levels."""
    zone = float(sr["zone"])
    cur = _candle_bar(o, h, l, c, i)
    entry = float(c[i])
    levels: List[Tuple[str, float]] = []
    for s in sr.get("supports") or []:
        levels.append(("S", float(s["price"])))
    for r in sr.get("resists") or []:
        levels.append(("R", float(r["price"])))
    if sr.get("pdh"):
        levels.append(("R", float(sr["pdh"])))
    if sr.get("pdl"):
        levels.append(("S", float(sr["pdl"])))

    swept_sup = swept_res = False
    for kind, lv in levels:
        if kind == "S" and float(l[i]) < lv - 0.1 * zone and entry > lv:
            swept_sup = True
        if kind == "R" and float(h[i]) > lv + 0.1 * zone and entry < lv:
            swept_res = True

    trap_break = False
    if side == "BUY" and sr.get("nearest_res"):
        lv = float(sr["nearest_res"]["price"])
        if entry >= lv - 0.4 * zone and cur["upper_frac"] >= 0.45:
            trap_break = True
        if entry > lv and cur["upper_frac"] >= 0.50 and cur["body_frac"] < 0.45:
            trap_break = True
    if side == "SELL" and sr.get("nearest_sup"):
        lv = float(sr["nearest_sup"]["price"])
        if entry <= lv + 0.4 * zone and cur["lower_frac"] >= 0.45:
            trap_break = True
        if entry < lv and cur["lower_frac"] >= 0.50 and cur["body_frac"] < 0.45:
            trap_break = True

    in_mid_range = False
    if sr.get("range_lo") is not None and sr.get("range_hi") is not None:
        span = max(float(sr["range_hi"]) - float(sr["range_lo"]), 1e-9)
        loc = (entry - float(sr["range_lo"])) / span
        in_mid_range = 0.35 <= loc <= 0.65

    liq_favor = (side == "BUY" and swept_sup) or (side == "SELL" and swept_res)
    liq_against = (side == "BUY" and swept_res and not cur["bull"]) or (
        side == "SELL" and swept_sup and not cur["bear"]
    )
    return {
        "liq_favor": liq_favor,
        "liq_against": liq_against,
        "trap_break": trap_break,
        "in_mid_range": in_mid_range,
    }


def reward_risk(
    side: str,
    entry: float,
    sl: float,
    sr: Dict[str, Any],
    *,
    require_real_target: bool = False,
    min_clearance_R: float = 0.30,
) -> Dict[str, Any]:
    """Honest planned R:R to first opposing S/R.

    When require_real_target=True, do NOT invent entry±2R — return target=None / rr=0
    if no real level exists beyond clearance. Also shrink target to the nearest wall
    on the path so R:R is not optimistic past a denser level.
    """
    risk = abs(entry - sl)
    if risk < 1e-9:
        return {
            "rr": 0.0,
            "target": None,
            "risk": risk,
            "reward": 0.0,
            "real_target": False,
            "synthetic": False,
        }
    clear = min_clearance_R * risk
    if side == "BUY":
        cands: List[float] = []
        if sr.get("nearest_res"):
            cands.append(float(sr["nearest_res"]["price"]))
        if sr.get("range_hi") is not None:
            cands.append(float(sr["range_hi"]))
        if sr.get("pdh") and float(sr["pdh"]) > entry:
            cands.append(float(sr["pdh"]))
        for r in sr.get("resists") or []:
            px = float(r["price"])
            if px > entry:
                cands.append(px)
        above = sorted({x for x in cands if x > entry + clear})
        if above:
            tgt = above[0]
            real = True
            synthetic = False
        else:
            tgt = entry + 2.0 * risk
            real = False
            synthetic = True
    else:
        cands = []
        if sr.get("nearest_sup"):
            cands.append(float(sr["nearest_sup"]["price"]))
        if sr.get("range_lo") is not None:
            cands.append(float(sr["range_lo"]))
        if sr.get("pdl") and float(sr["pdl"]) < entry:
            cands.append(float(sr["pdl"]))
        for s in sr.get("supports") or []:
            px = float(s["price"])
            if px < entry:
                cands.append(px)
        below = sorted({x for x in cands if x < entry - clear}, reverse=True)
        if below:
            tgt = below[0]
            real = True
            synthetic = False
        else:
            tgt = entry - 2.0 * risk
            real = False
            synthetic = True

    if require_real_target and not real:
        return {
            "rr": 0.0,
            "target": None,
            "risk": risk,
            "reward": 0.0,
            "real_target": False,
            "synthetic": True,
        }

    reward = abs(float(tgt) - entry)
    return {
        "rr": reward / risk,
        "target": float(tgt),
        "risk": risk,
        "reward": reward,
        "real_target": real,
        "synthetic": synthetic,
    }


def sl_kill_block(
    o, h, l, c, atr, idx, i: int, side: str, entry: float, risk: float, cfg: PaConfig
) -> Tuple[bool, str]:
    """Block entries that historically hard-SL without touching winners.

    Option Blue research (22 sessions, base pa_sr_acc_mid):
      chase_v1 killed 5/5 hard-SLs and 0/24 winners → 100% hit on kept book.
    """
    mode = getattr(cfg, "sl_kill_mode", "none") or "none"
    if mode in ("", "none"):
        return False, ""

    a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 10.0
    sr = build_sr_map(
        o, h, l, c, atr, idx, i, lookback_days=int(getattr(cfg, "sr_lookback_days", 2))
    )
    if side == "BUY":
        opp_d = (
            (float(sr["nearest_res"]["price"]) - entry) / a
            if sr.get("nearest_res")
            else 9.0
        )
    else:
        opp_d = (
            (entry - float(sr["nearest_sup"]["price"])) / a
            if sr.get("nearest_sup")
            else 9.0
        )
    prev_rng = max(float(h[i - 1]) - float(l[i - 1]), 1e-9) if i >= 1 else a
    expand = (float(h[i]) - float(l[i])) / prev_rng
    body = float(_candle_bar(o, h, l, c, i)["body_frac"])

    if mode == "chase_v1":
        # 1) expanding bar into/through opposing S/R
        if expand >= 1.5 and opp_d <= 0.20:
            return True, "sl_kill_chase_expand"
        # 2) tiny structure risk (noise SL)
        if risk <= 6.0:
            return True, "sl_kill_tiny_risk"
        # 3) marubozu already through opposing level
        if body >= 0.95 and opp_d <= 0.0:
            return True, "sl_kill_maru_through"
        return False, ""

    return False, ""


def _opp_dist_R(side: str, entry: float, sr: Dict[str, Any], risk: float) -> Optional[float]:
    """Distance in R to nearest opposing S/R (None if none beyond noise clearance)."""
    if risk < 1e-9:
        return None
    clear = 0.30 * risk
    cands: List[float] = []
    if side == "BUY":
        if sr.get("nearest_res"):
            cands.append(float(sr["nearest_res"]["price"]))
        if sr.get("range_hi") is not None:
            cands.append(float(sr["range_hi"]))
        if sr.get("pdh") and float(sr["pdh"]) > entry:
            cands.append(float(sr["pdh"]))
        for r in sr.get("resists") or []:
            px = float(r["price"])
            if px > entry:
                cands.append(px)
        above = [x for x in cands if x > entry + clear]
        if not above:
            return None
        return (min(above) - entry) / risk
    if sr.get("nearest_sup"):
        cands.append(float(sr["nearest_sup"]["price"]))
    if sr.get("range_lo") is not None:
        cands.append(float(sr["range_lo"]))
    if sr.get("pdl") and float(sr["pdl"]) < entry:
        cands.append(float(sr["pdl"]))
    for s in sr.get("supports") or []:
        px = float(s["price"])
        if px < entry:
            cands.append(px)
    below = [x for x in cands if x < entry - clear]
    if not below:
        return None
    return (entry - max(below)) / risk


def sr_gate_ok(
    o, h, l, c, atr, idx, i: int, side: str, entry: float, sl: float, cfg: PaConfig
) -> Tuple[bool, str]:
    """Apply locked sr_gate using multi-day candle S/R + liquidity + R:R."""
    gate = getattr(cfg, "sr_gate", "none") or "none"
    if gate == "none":
        return True, ""

    sr = build_sr_map(
        o, h, l, c, atr, idx, i, lookback_days=int(getattr(cfg, "sr_lookback_days", 2))
    )
    liq = liquidity_read(o, h, l, c, i, side, sr)
    need_real = bool(getattr(cfg, "require_real_target", False)) or gate == "rr_accurate"
    rr = reward_risk(side, entry, sl, sr, require_real_target=need_real)
    min_rr = float(getattr(cfg, "min_rr", 1.5))

    if gate == "no_trap":
        if liq["trap_break"] or liq["liq_against"]:
            return False, "sr_block_trap"
        return True, "sr_ok_no_trap"

    if gate == "rr_accurate":
        # Accurate R:R only — no trade-count / loss holds.
        # Keep trap block (falsifies reward path); require real target + min_rr.
        if liq["trap_break"] or liq["liq_against"]:
            return False, "sr_block_trap"
        if not rr.get("real_target") or rr.get("target") is None:
            return False, "sr_block_no_real_target"
        if float(rr["rr"]) < min_rr:
            return False, f"sr_block_rr={rr['rr']:.2f}"
        note = f"sr_rr_acc rr={rr['rr']:.2f} tgt~{float(rr['target']):.0f}"
        return True, note

    # --- Advanced accuracy gates (20d autopsy: near wall helps; far empty / large RR hurts) ---
    risk = abs(float(entry) - float(sl))
    dist_R = _opp_dist_R(side, float(entry), sr, risk)

    if gate == "adv_real_tgt":
        # Real opposing S/R exists — no min_rr (large RR was inverted edge).
        if liq["trap_break"] or liq["liq_against"]:
            return False, "sr_block_trap"
        if not rr.get("real_target") or rr.get("target") is None:
            return False, "sr_block_no_real_target"
        dshow = dist_R if dist_R is not None else -1.0
        return True, f"sr_adv_real_tgt distR={dshow:.2f}"

    if gate == "adv_near_wall":
        # Trade into/near structure (best BASE bucket was <1R wall).
        if liq["trap_break"] or liq["liq_against"]:
            return False, "sr_block_trap"
        max_r = float(getattr(cfg, "near_wall_max_R", 1.5))
        if dist_R is None or dist_R > max_r:
            return False, f"sr_block_not_near_wall distR={dist_R}"
        return True, f"sr_adv_near_wall distR={dist_R:.2f}"

    if gate == "adv_no_far":
        # Drop only far-empty air (nearest opp >= far_empty_min_R).
        if liq["trap_break"] or liq["liq_against"]:
            return False, "sr_block_trap"
        far_r = float(getattr(cfg, "far_empty_min_R", 3.0))
        if dist_R is not None and dist_R >= far_r:
            return False, f"sr_block_far_empty={dist_R:.1f}R"
        return True, "sr_adv_no_far"

    if gate == "adv_v1":
        # Structure engagement + no far empty (accuracy stack, no call caps).
        if liq["trap_break"] or liq["liq_against"]:
            return False, "sr_block_trap"
        if not rr.get("real_target") or rr.get("target") is None:
            return False, "sr_block_no_real_target"
        max_r = float(getattr(cfg, "near_wall_max_R", 1.5))
        far_r = float(getattr(cfg, "far_empty_min_R", 3.0))
        if dist_R is None or dist_R > max_r:
            return False, f"sr_block_not_near_wall distR={dist_R}"
        if dist_R >= far_r:
            return False, f"sr_block_far_empty={dist_R:.1f}R"
        return True, f"sr_adv_v1 distR={dist_R:.2f}"

    if gate == "full_v1":
        # research best accuracy: read_v3 + no trap + rr>=1.5 + not mid-range unless liq grab
        c_ok, c_note = candle_entry_ok(o, h, l, c, i, side, "read_v3")
        if not c_ok:
            return False, c_note or "sr_block_candle"
        if liq["trap_break"] or liq["liq_against"]:
            return False, "sr_block_trap"
        if rr["rr"] < min_rr:
            return False, f"sr_block_rr={rr['rr']:.1f}"
        if liq["in_mid_range"] and not liq["liq_favor"]:
            return False, "sr_block_mid_range"
        note = f"sr_full_v1 rr={rr['rr']:.1f}"
        if liq["liq_favor"]:
            note += " liq_grab"
        if rr.get("target") is not None:
            note += f" tgt~{rr['target']:.0f}"
        return True, note

    if gate == "full_v3":
        c_ok, c_note = candle_entry_ok(o, h, l, c, i, side, "read_v3")
        if not c_ok:
            return False, c_note or "sr_block_candle"
        if liq["trap_break"] or liq["liq_against"]:
            return False, "sr_block_trap"
        if liq["liq_favor"]:
            return True, "sr_full_v3_liq"
        if rr["rr"] >= 2.0 and not liq["in_mid_range"]:
            return True, f"sr_full_v3_rr={rr['rr']:.1f}"
        return False, "sr_need_liq_or_rr2"

    return True, ""


def atr14(h: np.ndarray, l: np.ndarray, c: np.ndarray) -> np.ndarray:
    n = len(c)
    tr = np.zeros(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    out = np.full(n, np.nan)
    if n < 14:
        out[:] = np.nanmean(tr) if n else 10.0
        return out
    out[13] = float(np.mean(tr[:14]))
    for i in range(14, n):
        out[i] = (out[i - 1] * 13 + tr[i]) / 14
    out[:13] = out[13]
    return out


def htf_bias_15m(df1: pd.DataFrame) -> Dict[str, str]:
    if df1.empty:
        return {}
    o = df1["Open"].resample("15min", label="left", closed="left").first()
    h = df1["High"].resample("15min", label="left", closed="left").max()
    l = df1["Low"].resample("15min", label="left", closed="left").min()
    c = df1["Close"].resample("15min", label="left", closed="left").last()
    bars = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c}).dropna()
    bias: Dict[str, str] = {}
    out: Dict[str, str] = {}
    for i in range(1, len(bars)):
        ts = bars.index[i]
        cl = float(bars["Close"].iloc[i])
        prev = float(bars["Close"].iloc[i - 1])
        hi = float(bars["High"].iloc[i])
        lo = float(bars["Low"].iloc[i])
        prev_hi = float(bars["High"].iloc[i - 1])
        prev_lo = float(bars["Low"].iloc[i - 1])
        if cl > prev and hi >= prev_hi:
            b = "up"
        elif cl < prev and lo <= prev_lo:
            b = "down"
        elif cl > prev:
            b = "up"
        elif cl < prev:
            b = "down"
        else:
            b = "flat"
        key = _day(ts) + _hm(ts)
        bias[key] = b
        out[key] = b
    return out


def lookup_htf(bias_map: Dict[str, str], ts) -> Optional[str]:
    t = pd.Timestamp(ts).tz_convert("Asia/Kolkata")
    bucket_m = (t.minute // 15) * 15
    key = f"{t.date()}{t.hour:02d}:{bucket_m:02d}"
    return bias_map.get(key)


def structure_sl(
    side: str, o, h, l, c, i: int, cfg: PaConfig
) -> Tuple[float, float, str]:
    entry = float(c[i])
    lo_prev = float(l[i - 1]) if i >= 1 else float(l[i])
    hi_prev = float(h[i - 1]) if i >= 1 else float(h[i])
    j0 = max(0, i - cfg.swing_n)
    swing_lo = float(np.min(l[j0:i])) if i > j0 else lo_prev
    swing_hi = float(np.max(h[j0:i])) if i > j0 else hi_prev
    if side == "BUY":
        sl = min(lo_prev, swing_lo) - cfg.sl_buffer
        note = f"SL under prev_low={lo_prev:.1f}/swing_lo={swing_lo:.1f}"
    else:
        sl = max(hi_prev, swing_hi) + cfg.sl_buffer
        note = f"SL above prev_high={hi_prev:.1f}/swing_hi={swing_hi:.1f}"
    risk = abs(entry - sl)
    return sl, risk, note


def _strong_close(side: str, o, h, l, c, i: int, body_min: float) -> bool:
    rng = max(float(h[i]) - float(l[i]), 1e-9)
    body = abs(float(c[i]) - float(o[i])) / rng
    if body < body_min:
        return False
    if side == "BUY":
        return float(c[i]) > float(o[i]) and float(c[i]) >= float(l[i]) + 0.58 * rng
    return float(c[i]) < float(o[i]) and float(c[i]) <= float(h[i]) - 0.58 * rng


def _mom_ok(side: str, c, i: int) -> bool:
    if i < 3:
        return True
    ups = sum(1 for k in range(i - 2, i + 1) if float(c[k]) > float(c[k - 1]))
    dns = sum(1 for k in range(i - 2, i + 1) if float(c[k]) < float(c[k - 1]))
    return ups >= 2 if side == "BUY" else dns >= 2


def _htf_ok(side: str, htf: Optional[str], cfg: PaConfig) -> bool:
    if cfg.strict_htf:
        if side == "BUY":
            return htf == "up"
        return htf == "down"
    if htf == "up" and side != "BUY":
        return False
    if htf == "down" and side != "SELL":
        return False
    return True


def _or_align(
    side: str, cl: float, or_hi: float, or_lo: float, broke_up: bool, broke_dn: bool, cfg: PaConfig
) -> bool:
    if not cfg.or_side_align:
        return True
    mid = 0.5 * (or_hi + or_lo)
    if side == "BUY":
        return bool(broke_up) and cl >= mid
    return bool(broke_dn) and cl <= mid


def detect_setup(
    o, h, l, c, atr, i: int,
    or_hi: float, or_lo: float, broke_up: bool, broke_dn: bool,
    htf: Optional[str],
    cfg: PaConfig,
) -> Optional[Tuple[str, str, str]]:
    if i < cfg.swing_n + 2:
        return None
    a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 10.0
    cl = float(c[i])
    hi = float(h[i])
    lo = float(l[i])
    op = float(o[i])
    j0 = i - cfg.swing_n
    swing_hi = float(np.max(h[j0:i]))
    swing_lo = float(np.min(l[j0:i]))
    prev_hi = float(h[i - 1])
    prev_lo = float(l[i - 1])
    rng = max(hi - lo, 1e-9)

    # A: BREAK_HOLD
    if cfg.allow_break:
        if (
            cl > swing_hi + cfg.break_atr_frac * a
            and _strong_close("BUY", o, h, l, c, i, cfg.body_min)
            and (not cfg.require_break_mom or _mom_ok("BUY", c, i))
            and _htf_ok("BUY", htf, cfg)
            and _or_align("BUY", cl, or_hi, or_lo, broke_up, broke_dn, cfg)
        ):
            return ("BUY", "BREAK_HOLD", f"close {cl:.1f} > swing_hi {swing_hi:.1f}")
        if (
            cl < swing_lo - cfg.break_atr_frac * a
            and _strong_close("SELL", o, h, l, c, i, cfg.body_min)
            and (not cfg.require_break_mom or _mom_ok("SELL", c, i))
            and _htf_ok("SELL", htf, cfg)
            and _or_align("SELL", cl, or_hi, or_lo, broke_up, broke_dn, cfg)
        ):
            return ("SELL", "BREAK_HOLD", f"close {cl:.1f} < swing_lo {swing_lo:.1f}")

    # B: SWEEP_RECLAIM (quality)
    if cfg.allow_sweep:
        lower_wick = min(op, cl) - lo
        upper_wick = hi - max(op, cl)
        depth_buy = prev_lo - lo
        depth_sell = hi - prev_hi
        if (
            depth_buy >= cfg.sweep_depth_atr * a
            and lower_wick / rng >= cfg.sweep_wick_frac
            and cl > prev_lo + cfg.reclaim_beyond * a
            and _strong_close("BUY", o, h, l, c, i, cfg.body_min)
            and _htf_ok("BUY", htf, cfg)
            and _or_align("BUY", cl, or_hi, or_lo, broke_up, broke_dn, cfg)
        ):
            return (
                "BUY",
                "SWEEP_RECLAIM",
                f"swept {lo:.1f} < prev_lo {prev_lo:.1f}, reclaim close",
            )
        if (
            depth_sell >= cfg.sweep_depth_atr * a
            and upper_wick / rng >= cfg.sweep_wick_frac
            and cl < prev_hi - cfg.reclaim_beyond * a
            and _strong_close("SELL", o, h, l, c, i, cfg.body_min)
            and _htf_ok("SELL", htf, cfg)
            and _or_align("SELL", cl, or_hi, or_lo, broke_up, broke_dn, cfg)
        ):
            return (
                "SELL",
                "SWEEP_RECLAIM",
                f"swept {hi:.1f} > prev_hi {prev_hi:.1f}, reclaim close",
            )

    # C: OR_RETEST
    if cfg.allow_or_retest:
        zone = max(4.0, 0.5 * a)
        if (
            broke_up
            and (or_hi - zone) <= lo <= (or_hi + zone)
            and cl >= or_hi - 0.25 * zone
            and (_strong_close("BUY", o, h, l, c, i, cfg.body_min) or cl > op)
            and _htf_ok("BUY", htf, cfg)
            and _or_align("BUY", cl, or_hi, or_lo, broke_up, broke_dn, cfg)
        ):
            return ("BUY", "OR_RETEST", f"retest OR_hi {or_hi:.1f} after break")
        if (
            broke_dn
            and (or_lo - zone) <= hi <= (or_lo + zone)
            and cl <= or_lo + 0.25 * zone
            and (_strong_close("SELL", o, h, l, c, i, cfg.body_min) or cl < op)
            and _htf_ok("SELL", htf, cfg)
            and _or_align("SELL", cl, or_hi, or_lo, broke_up, broke_dn, cfg)
        ):
            return ("SELL", "OR_RETEST", f"retest OR_lo {or_lo:.1f} after break")

    return None


def settle_path(
    o, h, l, c, idx, entry_i: int, side: str, entry: float, sl0: float, risk: float,
    cfg: Optional[PaConfig] = None,
) -> Dict[str, Any]:
    cfg = cfg or CFG
    sl = float(sl0)
    mfe = 0.0
    mae = 0.0
    hit_1 = hit_2 = hit_3 = False
    day0 = _day(idx[entry_i])
    armed_trail = False
    arm_R = float(cfg.trail_arm_R)

    for j in range(entry_i + 1, min(len(c), entry_i + 1 + cfg.max_hold_bars)):
        if _day(idx[j]) != day0:
            px = float(c[j - 1]) if j > entry_i else entry
            pts = (px - entry) if side == "BUY" else (entry - px)
            return {
                "exit_hm": _hm(idx[j - 1]),
                "exit_px": round(px, 2),
                "exit_why": "session_end",
                "pts": round(pts, 2),
                "R": round(pts / risk, 3) if risk else 0.0,
                "win": pts > 0,
                "mfe": round(mfe, 2),
                "mae": round(mae, 2),
                "hit_1R": hit_1,
                "hit_2R": hit_2,
                "hit_3R": hit_3,
            }
        hi = float(h[j])
        lo = float(l[j])
        cl = float(c[j])
        if side == "BUY":
            fav = hi - entry
            adv = entry - lo
            if lo <= sl:
                pts = sl - entry
                return {
                    "exit_hm": _hm(idx[j]),
                    "exit_px": round(sl, 2),
                    "exit_why": "sl" if not armed_trail else "trail_sl",
                    "pts": round(pts, 2),
                    "R": round(pts / risk, 3) if risk else 0.0,
                    "win": pts > 0,
                    "mfe": round(max(mfe, fav), 2),
                    "mae": round(max(mae, adv), 2),
                    "hit_1R": hit_1 or fav >= risk,
                    "hit_2R": hit_2 or fav >= 2 * risk,
                    "hit_3R": hit_3 or fav >= 3 * risk,
                }
            mfe = max(mfe, fav)
            mae = max(mae, adv)
            if fav >= arm_R * risk:
                hit_1 = hit_1 or fav >= risk
                armed_trail = True
            if fav >= 2 * risk:
                hit_2 = True
            if fav >= 3 * risk:
                hit_3 = True
            if armed_trail:
                trail = float(l[j - 1]) - cfg.sl_buffer
                if trail > sl:
                    sl = trail
                # continuous candle trail: tighten on opposing pin / strong opposing body
                if getattr(cfg, "candle_trail_mode", "base") == "pin_protect":
                    cf = _candle_bar(o, h, l, c, j)
                    if cf["pin_bear"] or (cf["bear"] and cf["body_frac"] >= 0.55):
                        tight = lo - cfg.sl_buffer
                        if tight > sl:
                            sl = tight
            if j >= 3 and armed_trail:
                sw = float(np.min(l[j - 3 : j]))
                if cl < sw:
                    pts = cl - entry
                    return {
                        "exit_hm": _hm(idx[j]),
                        "exit_px": round(cl, 2),
                        "exit_why": "structure_fail",
                        "pts": round(pts, 2),
                        "R": round(pts / risk, 3) if risk else 0.0,
                        "win": pts > 0,
                        "mfe": round(mfe, 2),
                        "mae": round(mae, 2),
                        "hit_1R": hit_1,
                        "hit_2R": hit_2,
                        "hit_3R": hit_3,
                    }
        else:
            fav = entry - lo
            adv = hi - entry
            if hi >= sl:
                pts = entry - sl
                return {
                    "exit_hm": _hm(idx[j]),
                    "exit_px": round(sl, 2),
                    "exit_why": "sl" if not armed_trail else "trail_sl",
                    "pts": round(pts, 2),
                    "R": round(pts / risk, 3) if risk else 0.0,
                    "win": pts > 0,
                    "mfe": round(max(mfe, fav), 2),
                    "mae": round(max(mae, adv), 2),
                    "hit_1R": hit_1 or fav >= risk,
                    "hit_2R": hit_2 or fav >= 2 * risk,
                    "hit_3R": hit_3 or fav >= 3 * risk,
                }
            mfe = max(mfe, fav)
            mae = max(mae, adv)
            if fav >= arm_R * risk:
                hit_1 = hit_1 or fav >= risk
                armed_trail = True
            if fav >= 2 * risk:
                hit_2 = True
            if fav >= 3 * risk:
                hit_3 = True
            if armed_trail:
                trail = float(h[j - 1]) + cfg.sl_buffer
                if trail < sl:
                    sl = trail
                if getattr(cfg, "candle_trail_mode", "base") == "pin_protect":
                    cf = _candle_bar(o, h, l, c, j)
                    if cf["pin_bull"] or (cf["bull"] and cf["body_frac"] >= 0.55):
                        tight = hi + cfg.sl_buffer
                        if tight < sl:
                            sl = tight
            if j >= 3 and armed_trail:
                sw = float(np.max(h[j - 3 : j]))
                if cl > sw:
                    pts = entry - cl
                    return {
                        "exit_hm": _hm(idx[j]),
                        "exit_px": round(cl, 2),
                        "exit_why": "structure_fail",
                        "pts": round(pts, 2),
                        "R": round(pts / risk, 3) if risk else 0.0,
                        "win": pts > 0,
                        "mfe": round(mfe, 2),
                        "mae": round(mae, 2),
                        "hit_1R": hit_1,
                        "hit_2R": hit_2,
                        "hit_3R": hit_3,
                    }

    last = min(len(c) - 1, entry_i + cfg.max_hold_bars)
    px = float(c[last])
    pts = (px - entry) if side == "BUY" else (entry - px)
    return {
        "exit_hm": _hm(idx[last]),
        "exit_px": round(px, 2),
        "exit_why": "time_cut",
        "pts": round(pts, 2),
        "R": round(pts / risk, 3) if risk else 0.0,
        "win": pts > 0,
        "mfe": round(mfe, 2),
        "mae": round(mae, 2),
        "hit_1R": hit_1,
        "hit_2R": hit_2,
        "hit_3R": hit_3,
    }


def _frvp_levels_from_slice(bars_slice: pd.DataFrame, n_rows: int = 48) -> Optional[Dict[str, Any]]:
    """Causal FRVP on a bar slice → POC / VAH / VAL / HVNs."""
    import sys

    try:
        import fno_fixed_range_vp as frvp
    except Exception:
        root = Path(__file__).resolve().parents[2]
        for p in (root / "app" / "fno", root / "app"):
            sp = str(p)
            if sp not in sys.path:
                sys.path.insert(0, sp)
        try:
            import fno_fixed_range_vp as frvp  # type: ignore
        except Exception:
            return None
    out = frvp.compute_fixed_range_vp(bars_slice, n_rows=n_rows, va_pct=0.70)
    if not out.get("ok"):
        return None
    rows = out.get("rows") or []
    ranked = sorted(rows, key=lambda r: float(r.get("vol") or 0), reverse=True)
    hvns = [float(r["price_mid"]) for r in ranked[:3] if float(r.get("vol") or 0) > 0]
    return {
        "poc": float(out["poc"]),
        "vah": float(out["vah"]),
        "val": float(out["val"]),
        "hvns": hvns,
        "support": float(out.get("support") or out["val"]),
        "resistance": float(out.get("resistance") or out["vah"]),
    }


def _near(px: float, level: float, zone: float) -> bool:
    return abs(px - level) <= zone


def frvp_quality(
    side: str,
    entry: float,
    lo: float,
    hi: float,
    cl: float,
    levels: Dict[str, Any],
    atr: float,
    cfg: PaConfig,
) -> Tuple[bool, str, Optional[float]]:
    """Return (ok, note, optional_sl_hint)."""
    zone = max(4.0, cfg.frvp_zone_atr * max(atr, 1.0))
    poc, vah, val = levels["poc"], levels["vah"], levels["val"]
    hvns = levels.get("hvns") or []
    all_lvls = [poc, vah, val] + list(hvns)

    if cfg.frvp_mode == "near_level":
        hit = any(_near(entry, lv, zone) or _near(lo, lv, zone) or _near(hi, lv, zone) for lv in all_lvls)
        if not hit:
            return False, "frvp_not_near_POC/VAH/VAL/HVN", None
        # SL hint: BUY prefer under VAL if near support cluster
        sl_hint = None
        if cfg.frvp_prefer_sl:
            if side == "BUY":
                cand = min(val, poc) - cfg.sl_buffer
                sl_hint = cand
            else:
                cand = max(vah, poc) + cfg.sl_buffer
                sl_hint = cand
        which = min(all_lvls, key=lambda lv: abs(entry - lv))
        return True, f"frvp_near {which:.1f} (POC={poc:.1f} VAH={vah:.1f} VAL={val:.1f})", sl_hint

    if cfg.frvp_mode == "bounce_sr":
        if side == "BUY":
            # bounce at VAL / POC / lower HVN
            supports = [val, poc] + [x for x in hvns if x <= poc]
            touch = any(lo <= lv + zone and cl >= lv - 0.25 * zone for lv in supports)
            if not touch:
                return False, "frvp_no_support_bounce", None
            sl_hint = min(supports) - cfg.sl_buffer if cfg.frvp_prefer_sl else None
            return True, f"frvp_bounce_support VAL={val:.1f}/POC={poc:.1f}", sl_hint
        resists = [vah, poc] + [x for x in hvns if x >= poc]
        touch = any(hi >= lv - zone and cl <= lv + 0.25 * zone for lv in resists)
        if not touch:
            return False, "frvp_no_resist_bounce", None
        sl_hint = max(resists) + cfg.sl_buffer if cfg.frvp_prefer_sl else None
        return True, f"frvp_bounce_resist VAH={vah:.1f}/POC={poc:.1f}", sl_hint

    if cfg.frvp_mode == "vah_break":
        if side == "BUY":
            # accept above VAH (break) or retest VAH from above
            ok = cl >= vah - 0.15 * zone and (entry >= vah - zone)
            if not ok:
                return False, f"frvp_not_above_VAH={vah:.1f}", None
            sl_hint = vah - cfg.sl_buffer if cfg.frvp_prefer_sl else None
            return True, f"frvp_VAH_break/hold {vah:.1f}", sl_hint
        ok = cl <= val + 0.15 * zone and (entry <= val + zone)
        if not ok:
            return False, f"frvp_not_below_VAL={val:.1f}", None
        sl_hint = val + cfg.sl_buffer if cfg.frvp_prefer_sl else None
        return True, f"frvp_VAL_break/hold {val:.1f}", sl_hint

    return True, "frvp_mode_off", None


def scan_session(
    df1: pd.DataFrame,
    *,
    settle: bool = True,
    cfg: Optional[PaConfig] = None,
    all_hours: bool = False,
) -> List[PaCall]:
    cfg = cfg or CFG
    if df1 is None or df1.empty:
        return []
    # Crypto / 24h: keep all hours when trade window spans full day or caller asks
    use_all = bool(all_hours) or (
        int(getattr(cfg, "trade_lo", 0) or 0) <= 0
        and int(getattr(cfg, "trade_hi", 0) or 0) >= (24 * 60 - 1)
    )
    work = norm_1m(df1, all_hours=use_all)
    if work.empty:
        return []
    o = work["Open"].values
    h = work["High"].values
    l = work["Low"].values
    c = work["Close"].values
    atr = atr14(h, l, c)
    idx = work.index
    bias_map = htf_bias_15m(work)

    calls: List[PaCall] = []
    day_state: Dict[str, Dict[str, Any]] = {}
    # day start indices for FRVP slices
    day_start_i: Dict[str, int] = {}

    for i in range(len(work)):
        d = _day(idx[i])
        m = _mins(idx[i])
        if d not in day_start_i:
            day_start_i[d] = i
        st = day_state.setdefault(
            d,
            {
                "or_hi": None,
                "or_lo": None,
                "or_done": False,
                "broke_up": False,
                "broke_dn": False,
                "n_calls": 0,
                "last_i": -999,
                "last_side": None,
                "last_side_i": -999,
                "cooldown_until": -1,
                "bars": 0,
                "frvp": None,
                "frvp_last_i": -999,
                "or_end_i": None,
            },
        )
        st["bars"] += 1
        if not st["or_done"]:
            if st["or_hi"] is None:
                st["or_hi"] = float(h[i])
                st["or_lo"] = float(l[i])
            else:
                st["or_hi"] = max(st["or_hi"], float(h[i]))
                st["or_lo"] = min(st["or_lo"], float(l[i]))
            if st["bars"] >= cfg.or_bars:
                st["or_done"] = True
                st["or_end_i"] = i
                if cfg.use_frvp:
                    j0 = day_start_i[d]
                    st["frvp"] = _frvp_levels_from_slice(
                        work.iloc[j0 : i + 1], n_rows=cfg.frvp_rows
                    )
                    st["frvp_last_i"] = i

        if not st["or_done"]:
            continue
        if float(c[i]) > st["or_hi"]:
            st["broke_up"] = True
        if float(c[i]) < st["or_lo"]:
            st["broke_dn"] = True

        # expanding FRVP refresh (causal)
        if (
            cfg.use_frvp
            and cfg.frvp_anchor == "session_expand"
            and i - int(st["frvp_last_i"] or -999) >= cfg.frvp_refresh_every
        ):
            j0 = day_start_i[d]
            st["frvp"] = _frvp_levels_from_slice(
                work.iloc[j0 : i + 1], n_rows=cfg.frvp_rows
            )
            st["frvp_last_i"] = i

        if not (cfg.trade_lo <= m <= cfg.trade_hi):
            continue
        if st["n_calls"] >= cfg.max_calls_day:
            continue
        if i < st["cooldown_until"]:
            continue
        if i - st["last_i"] < cfg.cooldown_bars:
            continue

        htf = lookup_htf(bias_map, idx[i])
        got = detect_setup(
            o, h, l, c, atr, i, st["or_hi"], st["or_lo"], st["broke_up"], st["broke_dn"], htf, cfg
        )
        if not got:
            continue
        side, setup, reason = got

        if (
            cfg.side_flip_cooldown > 0
            and st["last_side"]
            and side != st["last_side"]
            and i - st["last_side_i"] < cfg.side_flip_cooldown
        ):
            continue

        entry = float(c[i])
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 10.0
        frvp_note = ""
        sl_hint = None
        if cfg.use_frvp:
            levels = st.get("frvp")
            if not levels:
                continue
            ok_f, frvp_note, sl_hint = frvp_quality(
                side, entry, float(l[i]), float(h[i]), float(c[i]), levels, a, cfg
            )
            if not ok_f:
                continue

        sl, risk, sl_note = structure_sl(side, o, h, l, c, i, cfg)
        if sl_hint is not None and cfg.frvp_prefer_sl:
            if side == "BUY":
                cand = min(sl, float(sl_hint))
                if entry - cand >= cfg.min_risk and entry - cand <= cfg.max_risk:
                    sl = cand
                    risk = entry - sl
                    sl_note = f"{sl_note} + FRVP_SL"
            else:
                cand = max(sl, float(sl_hint))
                if cand - entry >= cfg.min_risk and cand - entry <= cfg.max_risk:
                    sl = cand
                    risk = cand - entry
                    sl_note = f"{sl_note} + FRVP_SL"

        if risk < cfg.min_risk or risk > cfg.max_risk:
            continue

        # Runtime S/R + liquidity + R:R (replaces FRVP when sr_gate set)
        sr_note = ""
        gate = getattr(cfg, "sr_gate", "none") or "none"
        if gate not in ("", "none", None):
            sr_ok, sr_note = sr_gate_ok(o, h, l, c, atr, idx, i, side, entry, sl, cfg)
            if not sr_ok:
                continue
            # full_v1/v3 already include candle read — skip duplicate; other gates keep candle_entry_mode
            if gate in ("full_v1", "full_v3"):
                c_mode = "none"
            else:
                c_mode = cfg.candle_entry_mode
        else:
            c_mode = cfg.candle_entry_mode

        c_ok, c_note = candle_entry_ok(o, h, l, c, i, side, c_mode)
        if not c_ok:
            continue

        # SL-only killer: block chase/tiny-risk traps; never tuned to cut winners.
        # Still consume cooldown so skipping a bad entry does not open a replacement slot.
        kill, kill_note = sl_kill_block(o, h, l, c, atr, idx, i, side, entry, risk, cfg)
        if kill:
            st["last_i"] = i
            st["last_side"] = side
            st["last_side_i"] = i
            continue

        full_reason = f"{reason} · {sl_note}"
        if frvp_note:
            full_reason = f"{full_reason} · {frvp_note}"
        if sr_note:
            full_reason = f"{full_reason} · {sr_note}"
        if c_note:
            full_reason = f"{full_reason} · {c_note}"
        call = PaCall(
            day=d,
            hm=_hm(idx[i]),
            side=side,
            setup=setup,
            entry=round(entry, 2),
            stop_loss=round(sl, 2),
            risk=round(risk, 2),
            reason=full_reason,
            bar_i=i,
            htf_bias=htf,
            logic_ver=LOGIC_VER,
            cfg_name=cfg.name,
        )
        if settle:
            path = settle_path(o, h, l, c, idx, i, side, entry, sl, risk, cfg)
            for k, v in path.items():
                setattr(call, k, v)
            # causal post-loss cooldown
            if call.win is False and cfg.loss_extra_cooldown > 0:
                st["cooldown_until"] = i + cfg.loss_extra_cooldown
        calls.append(call)
        st["n_calls"] += 1
        st["last_i"] = i
        st["last_side"] = side
        st["last_side_i"] = i

    return calls


def summarize(calls: List[PaCall]) -> Dict[str, Any]:
    if not calls:
        return {"n": 0, "hit_pct": None, "avg_R": None, "avg_pts": None, "hit_1R_pct": None}
    settled = [c for c in calls if c.win is not None]
    wins = [c for c in settled if c.win]
    rs = [float(c.R) for c in settled if c.R is not None]
    pts = [float(c.pts) for c in settled if c.pts is not None]
    h1 = [c for c in settled if c.hit_1R]
    return {
        "n": len(settled),
        "wins": len(wins),
        "losses": len(settled) - len(wins),
        "hit_pct": round(100.0 * len(wins) / len(settled), 2) if settled else None,
        "avg_R": round(float(np.mean(rs)), 3) if rs else None,
        "avg_pts": round(float(np.mean(pts)), 2) if pts else None,
        "sum_pts": round(float(np.sum(pts)), 2) if pts else None,
        "hit_1R_pct": round(100.0 * len(h1) / len(settled), 2) if settled else None,
        "hit_2R_pct": round(
            100.0 * len([c for c in settled if c.hit_2R]) / len(settled), 2
        )
        if settled
        else None,
        "by_setup": {
            s: {
                "n": len([c for c in settled if c.setup == s]),
                "hit": round(
                    100.0
                    * len([c for c in settled if c.setup == s and c.win])
                    / max(1, len([c for c in settled if c.setup == s])),
                    1,
                ),
            }
            for s in sorted({c.setup for c in settled})
        },
    }


def load_ledger() -> Dict[str, Any]:
    HOLD.mkdir(parents=True, exist_ok=True)
    if not LEDGER.exists():
        return {"desk": DESK, "calls": []}
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {"desk": DESK, "calls": []}


def save_ledger(data: Dict[str, Any]) -> None:
    HOLD.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(data, indent=2), encoding="utf-8")


def append_live_calls(calls: List[PaCall], *, mark_fire: bool = True) -> Dict[str, Any]:
    data = load_ledger()
    existing = data.get("calls") or []
    keys = {
        (str(r.get("day")), str(r.get("hm")), str(r.get("side")), str(r.get("setup")), str(r.get("cfg_name") or ""))
        for r in existing
    }
    added = []
    now = datetime.now().isoformat(timespec="seconds")
    for c in calls:
        k = (c.day, c.hm, c.side, c.setup, c.cfg_name)
        if k in keys:
            continue
        if mark_fire:
            c.live_fire = True
            c.fired_at = now
        row = c.to_dict()
        existing.append(row)
        added.append(row)
        keys.add(k)
    data["calls"] = existing
    data["desk"] = DESK
    data["logic_ver"] = LOGIC_VER
    data["updated_at"] = now
    save_ledger(data)
    return {"n_added": len(added), "added": added, "n_total": len(existing)}


def evaluate_bar_live(df1_today: pd.DataFrame) -> Dict[str, Any]:
    calls = scan_session(df1_today, settle=False, cfg=CFG)
    settled = scan_session(df1_today, settle=True, cfg=CFG)
    by_key = {(c.day, c.hm, c.side, c.setup): c for c in settled}
    out_calls = []
    for c in calls:
        s = by_key.get((c.day, c.hm, c.side, c.setup))
        out_calls.append(s or c)
    meta = append_live_calls(out_calls, mark_fire=True)
    meta["summary"] = summarize(out_calls)
    meta["day_calls"] = [c.to_dict() for c in out_calls]
    return meta


def profiles() -> Dict[str, PaConfig]:
    """Ablation set."""
    return {
        "v1": CFG_V1,
        "v2": CFG,
        "v2_nosweep": replace(CFG, name="v2_nosweep", allow_sweep=False),
        "v2_break_only": replace(
            CFG, name="v2_break_only", allow_sweep=False, allow_or_retest=False
        ),
        "v2_soft_htf": replace(CFG, name="v2_soft_htf", strict_htf=False),
        "v2_minrisk7": replace(CFG, name="v2_minrisk7", min_risk=7.0),
        "v2_trail08": replace(CFG, name="v2_trail08", trail_arm_R=0.8),
    }
