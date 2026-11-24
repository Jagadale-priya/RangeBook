"""CBRT price-action book — Consolidation → Breakout → Retest → Pullback.

Causal 1m only. Structure SL (prev/swing). No fixed ±target.
Designed for accuracy: prefer retest-hold entries over chase breaks.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from prod_live.logic.pa_structure_live import (
    CFG_V1,
    DESK,
    PaCall,
    PaConfig,
    atr14,
    htf_bias_15m,
    lookup_htf,
    norm_1m,
    settle_path,
    structure_sl,
    summarize,
    _day,
    _hm,
    _mins,
    _strong_close,
)


@dataclass
class CbrtConfig:
    name: str = "cbrt"
    # box
    or_bars: int = 30
    consol_min_bars: int = 12
    consol_max_atr: float = 2.8  # box width <= this * ATR to count as consol
    consol_min_width: float = 8.0
    # break
    break_body_min: float = 0.55
    break_atr_frac: float = 0.20  # close beyond edge by this*ATR
    # must extend BEFORE retest is allowed (classic break→thrust→retest)
    extend_atr: float = 0.55
    extend_min_bars: int = 2
    # retest
    retest_zone_atr: float = 0.40
    retest_max_bars: int = 50
    retest_hold_body: float = 0.50
    retest_require_reject: bool = True  # wick beyond edge, close back hold
    # pullback
    allow_pullback: bool = True
    pullback_max_retr: float = 0.55
    pullback_min_bars: int = 4
    pullback_max_bars: int = 30
    # continuation after valid break (structure-style, same direction)
    allow_continue: bool = True
    continue_swing_n: int = 5
    continue_body: float = 0.55
    # risk / session
    sl_buffer: float = 0.75
    swing_n: int = 5
    min_risk: float = 8.0
    max_risk: float = 22.0
    trade_lo: int = 9 * 60 + 50
    trade_hi: int = 14 * 60 + 15
    max_hold_bars: int = 90
    max_calls_day: int = 3
    cooldown_bars: int = 14
    require_htf: bool = True
    trail_arm_R: float = 1.0
    # modes
    entry_retest: bool = True
    entry_pullback: bool = True
    entry_break_chase: bool = False
    midday_boxes: bool = True
    midday_every: int = 20
    # fail break only on full reclaim of box (not mid touch)
    fail_on_mid: bool = False


def _to_pa_cfg(c: CbrtConfig) -> PaConfig:
    """Map CBRT knobs into PaConfig for shared SL/settle helpers."""
    return replace(
        CFG_V1,
        name=c.name,
        or_bars=c.or_bars,
        swing_n=c.swing_n,
        sl_buffer=c.sl_buffer,
        min_risk=c.min_risk,
        max_risk=c.max_risk,
        trade_lo=c.trade_lo,
        trade_hi=c.trade_hi,
        max_hold_bars=c.max_hold_bars,
        max_calls_day=c.max_calls_day,
        cooldown_bars=c.cooldown_bars,
        body_min=c.break_body_min,
        trail_arm_R=c.trail_arm_R,
        or_side_align=True,
        strict_htf=c.require_htf,
    )


def _box_ok(hi: float, lo: float, atr: float, cfg: CbrtConfig) -> bool:
    w = hi - lo
    if w < cfg.consol_min_width:
        return False
    a = atr if atr > 0 else 10.0
    return w <= cfg.consol_max_atr * a


def scan_cbrt(
    df1: pd.DataFrame, *, settle: bool = True, cfg: Optional[CbrtConfig] = None
) -> List[PaCall]:
    cfg = cfg or CbrtConfig()
    pa_cfg = _to_pa_cfg(cfg)
    if df1 is None or df1.empty:
        return []
    work = norm_1m(df1)
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

    for i in range(len(work)):
        d = _day(idx[i])
        m = _mins(idx[i])
        st = day_state.setdefault(
            d,
            {
                "bars": 0,
                "phase": "CONSOL",  # CONSOL|EXTEND|WAIT_RETEST|POST_RETEST|FAILED
                "box_hi": None,
                "box_lo": None,
                "box_end": None,
                "break_side": None,
                "break_i": None,
                "break_ext": None,
                "extended": False,
                "retest_done": False,
                "pullback_armed": False,
                "pullback_done": False,
                "n_calls": 0,
                "last_i": -999,
                "failed": False,
            },
        )
        st["bars"] += 1
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 10.0
        cl = float(c[i])
        hi = float(h[i])
        lo = float(l[i])

        # --- build / refresh consolidation box ---
        if st["phase"] == "CONSOL":
            if st["bars"] <= cfg.or_bars:
                if st["box_hi"] is None:
                    st["box_hi"], st["box_lo"] = hi, lo
                else:
                    st["box_hi"] = max(st["box_hi"], hi)
                    st["box_lo"] = min(st["box_lo"], lo)
                if st["bars"] == cfg.or_bars and _box_ok(st["box_hi"], st["box_lo"], a, cfg):
                    st["box_end"] = i
                elif st["bars"] == cfg.or_bars:
                    # wide open — still use as OR box (range day)
                    st["box_end"] = i
            elif cfg.midday_boxes and st["box_end"] is not None:
                # idle consol: if still inside box long enough, keep; else start new box window
                pass

        if st["box_hi"] is None or st["bars"] < cfg.or_bars:
            continue

        box_hi, box_lo = float(st["box_hi"]), float(st["box_lo"])
        zone = max(4.0, cfg.retest_zone_atr * a)

        # --- detect breakout ---
        if st["phase"] in ("CONSOL", "FAILED"):
            up_brk = cl > box_hi + cfg.break_atr_frac * a and _strong_close(
                "BUY", o, h, l, c, i, cfg.break_body_min
            )
            dn_brk = cl < box_lo - cfg.break_atr_frac * a and _strong_close(
                "SELL", o, h, l, c, i, cfg.break_body_min
            )
            if up_brk or dn_brk:
                side = "BUY" if up_brk else "SELL"
                htf = lookup_htf(bias_map, idx[i])
                if cfg.require_htf:
                    if side == "BUY" and htf == "down":
                        continue
                    if side == "SELL" and htf == "up":
                        continue
                st["phase"] = "EXTEND"
                st["break_side"] = side
                st["break_i"] = i
                st["break_ext"] = hi if side == "BUY" else lo
                st["extended"] = False
                st["retest_done"] = False
                st["pullback_done"] = False
                st["failed"] = False
                if (
                    cfg.entry_break_chase
                    and cfg.trade_lo <= m <= cfg.trade_hi
                    and st["n_calls"] < cfg.max_calls_day
                    and i - st["last_i"] >= cfg.cooldown_bars
                ):
                    call = _try_entry(
                        work, o, h, l, c, atr, idx, i, side, "BREAKOUT",
                        f"break {side} box {box_hi:.1f}/{box_lo:.1f}",
                        htf, settle, pa_cfg, cfg,
                    )
                    if call:
                        calls.append(call)
                        st["n_calls"] += 1
                        st["last_i"] = i
            continue

        side = st["break_side"]
        if side is None:
            continue

        # track extension
        if side == "BUY":
            st["break_ext"] = max(float(st["break_ext"] or hi), hi)
        else:
            st["break_ext"] = min(float(st["break_ext"] or lo), lo)

        # --- failed break: full box reclaim (optional mid) ---
        mid = 0.5 * (box_hi + box_lo)
        if cfg.fail_on_mid:
            fail = (side == "BUY" and cl < mid) or (side == "SELL" and cl > mid)
        else:
            fail = (side == "BUY" and cl < box_lo) or (side == "SELL" and cl > box_hi)
        if fail:
            st["phase"] = "FAILED"
            st["break_side"] = None
            continue

        # --- EXTEND phase: require thrust beyond edge before retest ---
        if st["phase"] == "EXTEND" and st["break_i"] is not None:
            bars_since = i - int(st["break_i"])
            ext = float(st["break_ext"])
            if side == "BUY":
                thrust = ext - box_hi
            else:
                thrust = box_lo - ext
            if bars_since >= cfg.extend_min_bars and thrust >= cfg.extend_atr * a:
                st["extended"] = True
                st["phase"] = "WAIT_RETEST"
            elif bars_since > cfg.retest_max_bars:
                st["phase"] = "FAILED"
                st["break_side"] = None
            continue

        # timeout retest window → midday consol rebuild
        if (
            st["phase"] == "WAIT_RETEST"
            and st["break_i"] is not None
            and i - int(st["break_i"]) > cfg.retest_max_bars
        ):
            if cfg.midday_boxes:
                j0 = max(0, i - cfg.consol_min_bars + 1)
                nh, nl = float(np.max(h[j0 : i + 1])), float(np.min(l[j0 : i + 1]))
                if _box_ok(nh, nl, a, cfg):
                    st["box_hi"], st["box_lo"] = nh, nl
                    st["box_end"] = i
                    st["phase"] = "CONSOL"
                    st["break_side"] = None
                else:
                    st["phase"] = "FAILED"
            else:
                st["phase"] = "FAILED"
            continue

        if not (cfg.trade_lo <= m <= cfg.trade_hi):
            continue
        if st["n_calls"] >= cfg.max_calls_day:
            continue
        if i - st["last_i"] < cfg.cooldown_bars:
            continue

        htf = lookup_htf(bias_map, idx[i])
        if cfg.require_htf:
            if side == "BUY" and htf == "down":
                continue
            if side == "SELL" and htf == "up":
                continue

        # --- RETEST entry (only after extension) ---
        if (
            st["phase"] == "WAIT_RETEST"
            and cfg.entry_retest
            and st["extended"]
            and not st["retest_done"]
        ):
            if side == "BUY":
                in_zone = lo <= box_hi + zone and hi >= box_hi - zone
                reject = (not cfg.retest_require_reject) or (lo <= box_hi + 0.15 * a)
                holds = cl >= box_hi - 0.10 * zone and (
                    _strong_close("BUY", o, h, l, c, i, cfg.retest_hold_body)
                    or (cl > float(o[i]) and cl >= lo + 0.60 * max(hi - lo, 1e-9))
                )
            else:
                in_zone = hi >= box_lo - zone and lo <= box_lo + zone
                reject = (not cfg.retest_require_reject) or (hi >= box_lo - 0.15 * a)
                holds = cl <= box_lo + 0.10 * zone and (
                    _strong_close("SELL", o, h, l, c, i, cfg.retest_hold_body)
                    or (cl < float(o[i]) and cl <= hi - 0.60 * max(hi - lo, 1e-9))
                )
            if in_zone and reject and holds:
                edge = box_hi if side == "BUY" else box_lo
                call = _try_entry(
                    work, o, h, l, c, atr, idx, i, side, "RETEST",
                    f"retest hold {side} edge={edge:.1f} after extend",
                    htf, settle, pa_cfg, cfg,
                )
                if call:
                    calls.append(call)
                    st["n_calls"] += 1
                    st["last_i"] = i
                    st["retest_done"] = True
                    st["phase"] = "POST_RETEST"
                    st["pullback_armed"] = cfg.entry_pullback and cfg.allow_pullback
            continue

        # --- CONTINUATION (break-hold in trend after valid break) ---
        if (
            cfg.allow_continue
            and st["phase"] in ("WAIT_RETEST", "POST_RETEST")
            and st["extended"]
        ):
            sn = cfg.continue_swing_n
            if i >= sn + 1:
                sw_hi = float(np.max(h[i - sn : i]))
                sw_lo = float(np.min(l[i - sn : i]))
                cont = False
                if side == "BUY" and cl > sw_hi and _strong_close(
                    "BUY", o, h, l, c, i, cfg.continue_body
                ):
                    cont = True
                if side == "SELL" and cl < sw_lo and _strong_close(
                    "SELL", o, h, l, c, i, cfg.continue_body
                ):
                    cont = True
                if cont:
                    call = _try_entry(
                        work, o, h, l, c, atr, idx, i, side, "CONTINUE",
                        f"continuation {side} after consol break",
                        htf, settle, pa_cfg, cfg,
                    )
                    if call:
                        calls.append(call)
                        st["n_calls"] += 1
                        st["last_i"] = i
                        if st["phase"] == "WAIT_RETEST":
                            st["phase"] = "POST_RETEST"
                            st["pullback_armed"] = cfg.entry_pullback and cfg.allow_pullback
                        continue

        # --- PULLBACK entry ---
        if (
            st["phase"] == "POST_RETEST"
            and st["pullback_armed"]
            and not st["pullback_done"]
            and cfg.entry_pullback
            and st["break_i"] is not None
        ):
            bi = int(st["break_i"])
            bars_since = i - bi
            if bars_since < cfg.pullback_min_bars:
                continue
            if bars_since > cfg.pullback_max_bars + cfg.retest_max_bars:
                st["pullback_armed"] = False
                continue
            ext = float(st["break_ext"] or cl)
            if side == "BUY":
                thrust = max(ext - box_hi, 1e-9)
                retr = (ext - lo) / thrust
                deep_ok = 0.30 <= retr <= cfg.pullback_max_retr
                holds = cl > float(o[i]) and cl >= lo + 0.55 * max(hi - lo, 1e-9)
                near_struct = lo <= box_hi + 1.5 * zone
                if deep_ok and holds and near_struct:
                    call = _try_entry(
                        work, o, h, l, c, atr, idx, i, side, "PULLBACK",
                        f"pullback {retr:.2f} of thrust after break/retest",
                        htf, settle, pa_cfg, cfg,
                    )
                    if call:
                        calls.append(call)
                        st["n_calls"] += 1
                        st["last_i"] = i
                        st["pullback_done"] = True
                        st["pullback_armed"] = False
            else:
                thrust = max(box_lo - ext, 1e-9)
                retr = (hi - ext) / thrust
                deep_ok = 0.30 <= retr <= cfg.pullback_max_retr
                holds = cl < float(o[i]) and cl <= hi - 0.55 * max(hi - lo, 1e-9)
                near_struct = hi >= box_lo - 1.5 * zone
                if deep_ok and holds and near_struct:
                    call = _try_entry(
                        work, o, h, l, c, atr, idx, i, side, "PULLBACK",
                        f"pullback {retr:.2f} of thrust after break/retest",
                        htf, settle, pa_cfg, cfg,
                    )
                    if call:
                        calls.append(call)
                        st["n_calls"] += 1
                        st["last_i"] = i
                        st["pullback_done"] = True
                        st["pullback_armed"] = False

    return calls


def _try_entry(
    work, o, h, l, c, atr, idx, i, side, setup, reason, htf, settle, pa_cfg, cfg
) -> Optional[PaCall]:
    sl, risk, sl_note = structure_sl(side, o, h, l, c, i, pa_cfg)
    # tighten SL to retest bar extreme when setup is RETEST/PULLBACK
    if setup in ("RETEST", "PULLBACK"):
        if side == "BUY":
            sl2 = float(l[i]) - cfg.sl_buffer
            if sl2 > sl:  # tighter (less risk) only if still below entry
                if float(c[i]) - sl2 >= cfg.min_risk:
                    sl = sl2
                    risk = abs(float(c[i]) - sl)
                    sl_note = f"SL under setup bar low={float(l[i]):.1f}"
            else:
                # prefer setup bar if wider but still within max
                sl_cand = min(sl, sl2)
                risk_cand = abs(float(c[i]) - sl_cand)
                if cfg.min_risk <= risk_cand <= cfg.max_risk:
                    sl, risk = sl_cand, risk_cand
                    sl_note = f"SL under setup/swing low"
        else:
            sl2 = float(h[i]) + cfg.sl_buffer
            if sl2 < sl:
                if sl2 - float(c[i]) >= cfg.min_risk:  # wait abs
                    if abs(float(c[i]) - sl2) >= cfg.min_risk:
                        sl = sl2
                        risk = abs(float(c[i]) - sl)
                        sl_note = f"SL above setup bar high={float(h[i]):.1f}"
            else:
                sl_cand = max(sl, sl2)
                risk_cand = abs(float(c[i]) - sl_cand)
                if cfg.min_risk <= risk_cand <= cfg.max_risk:
                    sl, risk = sl_cand, risk_cand
                    sl_note = f"SL above setup/swing high"

    if risk < cfg.min_risk or risk > cfg.max_risk:
        return None
    entry = float(c[i])
    call = PaCall(
        day=_day(idx[i]),
        hm=_hm(idx[i]),
        side=side,
        setup=setup,
        entry=round(entry, 2),
        stop_loss=round(sl, 2),
        risk=round(risk, 2),
        reason=f"{reason} · {sl_note}",
        bar_i=i,
        htf_bias=htf,
        logic_ver="cbrt",
        cfg_name=cfg.name,
    )
    if settle:
        path = settle_path(o, h, l, c, idx, i, side, entry, sl, risk, pa_cfg)
        for k, v in path.items():
            setattr(call, k, v)
    return call


def cbrt_profiles() -> Dict[str, CbrtConfig]:
    base = CbrtConfig(name="cbrt_v2")
    return {
        "cbrt_v2": base,
        "cbrt_v2_retest": replace(
            base,
            name="cbrt_v2_retest",
            entry_pullback=False,
            allow_pullback=False,
            allow_continue=False,
        ),
        "cbrt_v2_cont": replace(
            base,
            name="cbrt_v2_cont",
            entry_retest=True,
            entry_pullback=False,
            allow_pullback=False,
            allow_continue=True,
        ),
        "cbrt_v2_soft": replace(base, name="cbrt_v2_soft", require_htf=False, min_risk=7.0),
        "cbrt_v2_tight": replace(
            base,
            name="cbrt_v2_tight",
            extend_atr=0.70,
            retest_hold_body=0.55,
            min_risk=9.0,
            max_calls_day=2,
            entry_pullback=False,
        ),
        "cbrt_v2_chase": replace(base, name="cbrt_v2_chase", entry_break_chase=True),
        "cbrt_v2_wide": replace(
            base, name="cbrt_v2_wide", retest_zone_atr=0.55, extend_atr=0.45, min_risk=7.0
        ),
    }


__all__ = [
    "CbrtConfig",
    "scan_cbrt",
    "cbrt_profiles",
    "summarize",
]
