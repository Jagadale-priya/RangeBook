"""Current / next 5m market lean — compact probability + expected points.

Uses the forming 5-minute candle (live LTP), live p(up), checklist votes, and
5m/15m micro. Expected move comes from recent 5-minute ATR.
Indication only — never opens or flips a call.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import fno_risk_engine

BAR_MINUTES = 5


def _f(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(p: float, lo: float = 0.05, hi: float = 0.95) -> float:
    return max(lo, min(hi, float(p)))


def _now(asof: Any = None) -> datetime:
    if asof is None:
        return datetime.now()
    try:
        if hasattr(asof, "to_pydatetime"):
            dt = asof.to_pydatetime()
        elif isinstance(asof, datetime):
            dt = asof
        else:
            dt = datetime.fromisoformat(str(asof).replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return datetime.now()


def patch_forming_5m(bars_5m: Any, price: Optional[float], *, asof: Any = None) -> Any:
    """Patch the unfinished last 5m bar with live LTP (keeps OHLC coherent)."""
    px = _f(price)
    if bars_5m is None or px is None:
        return bars_5m
    try:
        if getattr(bars_5m, "empty", True) or len(bars_5m) < 1:
            return bars_5m
        work = bars_5m.copy()
        last_ts = work.index[-1]
        start = last_ts.to_pydatetime() if hasattr(last_ts, "to_pydatetime") else last_ts
        if getattr(start, "tzinfo", None) is not None:
            start = start.astimezone().replace(tzinfo=None)
        end = start + timedelta(minutes=BAR_MINUTES)
        now = _now(asof)
        # Only patch while this bar is still open.
        if now >= end:
            return work
        # Column names may vary slightly.
        cols = {str(c).lower(): c for c in work.columns}
        o_col = cols.get("open")
        h_col = cols.get("high")
        l_col = cols.get("low")
        c_col = cols.get("close")
        if c_col is None:
            return work
        if o_col is not None:
            o = float(work.iloc[-1][o_col])
        else:
            o = px
        hi = float(work.iloc[-1][h_col]) if h_col is not None else max(o, px)
        lo = float(work.iloc[-1][l_col]) if l_col is not None else min(o, px)
        work.iloc[-1, work.columns.get_loc(c_col)] = px
        if h_col is not None:
            work.iloc[-1, work.columns.get_loc(h_col)] = max(hi, px, o)
        if l_col is not None:
            work.iloc[-1, work.columns.get_loc(l_col)] = min(lo, px, o)
        return work
    except Exception:
        return bars_5m


def _forming_candle(bars_5m: Any, price: Optional[float], *, asof: Any = None) -> Optional[Dict[str, Any]]:
    """Describe the 5m candle currently filling (or None if only finished bars)."""
    px = _f(price)
    if bars_5m is None or px is None:
        return None
    try:
        if getattr(bars_5m, "empty", True) or len(bars_5m) < 2:
            return None
        last_ts = bars_5m.index[-1]
        start = last_ts.to_pydatetime() if hasattr(last_ts, "to_pydatetime") else last_ts
        if getattr(start, "tzinfo", None) is not None:
            start = start.astimezone().replace(tzinfo=None)
        end = start + timedelta(minutes=BAR_MINUTES)
        now = _now(asof)
        forming = now < end
        cols = {str(c).lower(): c for c in bars_5m.columns}
        o_col = cols.get("open")
        h_col = cols.get("high")
        l_col = cols.get("low")
        c_col = cols.get("close")
        if o_col is None or c_col is None:
            return None
        o = float(bars_5m.iloc[-1][o_col])
        hi = float(bars_5m.iloc[-1][h_col]) if h_col is not None else max(o, px)
        lo = float(bars_5m.iloc[-1][l_col]) if l_col is not None else min(o, px)
        close = px if forming else float(bars_5m.iloc[-1][c_col])
        elapsed = max(0.0, (min(now, end) - start).total_seconds())
        remain = max(0.0, (end - now).total_seconds()) if forming else 0.0
        progress = min(1.0, elapsed / (BAR_MINUTES * 60.0))
        move = close - o
        return {
            "forming": forming,
            "start": start.strftime("%H:%M"),
            "end": end.strftime("%H:%M"),
            "open": round(o, 2),
            "high": round(max(hi, close, o), 2),
            "low": round(min(lo, close, o), 2),
            "ltp": round(close, 2),
            "change_pts": round(move, 2),
            "elapsed_sec": int(elapsed),
            "remain_sec": int(remain),
            "progress_pct": round(progress * 100.0, 1),
        }
    except Exception:
        return None


def _candle_p_up(candle: Optional[Dict[str, Any]], atr: Optional[float]) -> Optional[float]:
    if not candle:
        return None
    move = _f(candle.get("change_pts"))
    if move is None:
        return None
    scale = max(_f(atr) or 0.0, 8.0) * 0.45
    # Soft map of in-candle move → close-above-open probability.
    raw = 0.5 + (move / scale) * 0.35
    # Confidence grows as the bar fills.
    progress = max(0.15, min(1.0, float(candle.get("progress_pct") or 0) / 100.0))
    pulled = 0.5 + (raw - 0.5) * (0.55 + 0.45 * progress)
    return _clamp(pulled, 0.08, 0.92)


def _checklist_p_up(indications: Optional[Dict[str, Any]]) -> Optional[float]:
    summary = (indications or {}).get("summary") or {}
    bull = _f(summary.get("bullish"))
    bear = _f(summary.get("bearish"))
    if bull is None or bear is None:
        return None
    total = bull + bear
    if total <= 0:
        return 0.5
    return _clamp(bull / total, 0.08, 0.92)


def _micro_p_up(micro: Optional[Dict[str, Any]]) -> Optional[float]:
    m = micro or {}
    if not m.get("available") and m.get("micro_score") is None and not m.get("micro_bias"):
        return None
    score = _f(m.get("micro_score"))
    if score is not None:
        # micro_score is ~0–100; 50 = flat
        return _clamp(0.5 + (score - 50.0) / 100.0, 0.08, 0.92)
    bias = str(m.get("micro_bias") or "").upper()
    if bias == "BULLISH":
        return 0.62
    if bias == "BEARISH":
        return 0.38
    return 0.5


def _momentum_p_up(bars_5m: Any, atr: Optional[float]) -> Optional[float]:
    """Closed-bar 5m momentum (last 1–3 finished candles) → p(up).

    Research-style short-horizon: recent closed direction is a stronger tell
    for the next 5–10m than soft checklist alone.
    """
    if bars_5m is None:
        return None
    try:
        if getattr(bars_5m, "empty", True) or len(bars_5m) < 4:
            return None
        cols = {str(c).lower(): c for c in bars_5m.columns}
        o_col, c_col = cols.get("open"), cols.get("close")
        if o_col is None or c_col is None:
            return None
        # Skip forming last bar — use prior finished closes.
        finished = bars_5m.iloc[:-1]
        if len(finished) < 3:
            return None
        tail = finished.tail(3)
        moves = [float(r[c_col]) - float(r[o_col]) for _, r in tail.iterrows()]
        # Weight recent bar more.
        weights = [0.2, 0.3, 0.5][-len(moves) :]
        net = sum(m * w for m, w in zip(moves, weights))
        scale = max(_f(atr) or 0.0, 8.0) * 0.55
        raw = 0.5 + (net / scale) * 0.42
        return _clamp(raw, 0.10, 0.90)
    except Exception:
        return None


def _blend_p_up(
    live_p: Optional[float],
    checklist_p: Optional[float],
    micro_p: Optional[float],
    candle_p: Optional[float] = None,
    *,
    candle_weight: float = 0.0,
    mom_p: Optional[float] = None,
) -> Dict[str, Any]:
    parts: List[Tuple[str, float, float]] = []
    # When the forming candle is available, give it real weight so UI tracks *this* bar.
    w_live, w_check, w_micro, w_mom = 0.28, 0.14, 0.14, 0.18
    w_candle = max(0.0, min(0.40, float(candle_weight or 0.0)))
    base = w_live + w_check + w_micro + w_mom
    if candle_p is not None and w_candle > 0:
        parts.append(("candle", _clamp(candle_p), w_candle))
        remain = max(0.05, 1.0 - w_candle)
        scale = remain / base
        w_live *= scale
        w_check *= scale
        w_micro *= scale
        w_mom *= scale
    else:
        w_live, w_check, w_micro, w_mom = 0.34, 0.18, 0.18, 0.30
    if live_p is not None:
        parts.append(("live_p", _clamp(live_p), w_live))
    if checklist_p is not None:
        parts.append(("checklist", _clamp(checklist_p), w_check))
    if micro_p is not None:
        parts.append(("micro", _clamp(micro_p), w_micro))
    if mom_p is not None:
        parts.append(("momentum", _clamp(mom_p), w_mom))
    if not parts:
        return {"p_up": 0.5, "weights": {}, "inputs": {}}
    wsum = sum(w for _, _, w in parts)
    p = sum(v * w for _, v, w in parts) / wsum
    # Conflict damping: if live tape and micro disagree hard, pull toward 0.5.
    if live_p is not None and micro_p is not None:
        if (live_p >= 0.58 and micro_p <= 0.42) or (live_p <= 0.42 and micro_p >= 0.58):
            p = 0.5 + (p - 0.5) * 0.45
    return {
        "p_up": round(_clamp(p), 4),
        "weights": {name: round(w / wsum, 3) for name, _, w in parts},
        "inputs": {name: round(v, 4) for name, v, _ in parts},
    }


def _atr_5m(bars_5m: Any) -> Optional[float]:
    atr = fno_risk_engine.bar_atr(bars_5m)
    return _f(atr)


def _expected_points(atr: Optional[float], horizon_min: int) -> Optional[float]:
    if atr is None or atr <= 0:
        return None
    # Typical finished-bar excursion ≈ 0.55×ATR for 5m; scale with sqrt(time).
    base = 0.55 * float(atr)
    scale = (float(horizon_min) / 5.0) ** 0.5
    pts = base * scale
    return round(max(1.0, pts), 1)


def _direction(p_up: float) -> Dict[str, Any]:
    if p_up >= 0.55:
        return {
            "side": "UP",
            "p_side": round(p_up, 4),
            "tone": "up",
        }
    if p_up <= 0.45:
        return {
            "side": "DOWN",
            "p_side": round(1.0 - p_up, 4),
            "tone": "down",
        }
    # Near coin-flip — report the stronger lean but mark sideways.
    if p_up >= 0.5:
        return {"side": "SIDEWAYS", "p_side": round(p_up, 4), "tone": "flat", "lean": "UP"}
    return {"side": "SIDEWAYS", "p_side": round(1.0 - p_up, 4), "tone": "flat", "lean": "DOWN"}


def _headline(
    side: str,
    p_side: float,
    pts5: Optional[float],
    *,
    candle: Optional[Dict[str, Any]] = None,
    remain_pts: Optional[float] = None,
) -> str:
    pct = int(round(p_side * 100))
    if candle and candle.get("forming"):
        window = f"{candle.get('start')}–{candle.get('end')}"
        so_far = _f(candle.get("change_pts"))
        so_far_txt = f" · {so_far:+.0f} pts so far" if so_far is not None else ""
        left = f" · ~{remain_pts:.0f} pts room left" if remain_pts else ""
        remain_m = max(0, int(round(float(candle.get("remain_sec") or 0) / 60.0)))
        clock = f" · {remain_m}m left" if remain_m else ""
        if side == "UP":
            return f"This 5m candle ({window}) leaning UP ({pct}%){so_far_txt}{left}{clock}."
        if side == "DOWN":
            return f"This 5m candle ({window}) leaning DOWN ({pct}%){so_far_txt}{left}{clock}."
        lean = "slightly higher" if p_side >= 0.5 else "slightly lower"
        return f"This 5m candle ({window}) mixed ({pct}% lean {lean}){so_far_txt}{clock}."
    if side == "UP":
        move = f" by about {pts5:.0f} pts" if pts5 else ""
        return f"Next 5 min — market can go UP ({pct}%){move}."
    if side == "DOWN":
        move = f" by about {pts5:.0f} pts" if pts5 else ""
        return f"Next 5 min — market can go DOWN ({pct}%){move}."
    lean = "slightly higher" if p_side >= 0.5 else "slightly lower"
    return f"Next 5 min — mostly sideways ({pct}% lean {lean})."


def build(
    *,
    live_context: Optional[Dict[str, Any]] = None,
    indications: Optional[Dict[str, Any]] = None,
    price: Optional[float] = None,
    active_call: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compact forecast for the forming 5m candle (falls back to next-bar)."""
    live = live_context or {}
    micro = live.get("microstructure") or {}
    px = _f(price) or _f(live.get("last")) or _f(live.get("ltp"))
    asof = live.get("asof") or micro.get("asof") or live.get("received_at_ist")
    bars = patch_forming_5m(live.get("bars_5m"), px, asof=asof)
    atr = _atr_5m(bars)
    candle = _forming_candle(bars, px, asof=asof)
    candle_p = _candle_p_up(candle, atr)
    # Weight grows as the candle fills (15% → 40%).
    candle_w = 0.0
    if candle and candle.get("forming") and candle_p is not None:
        prog = max(0.0, min(1.0, float(candle.get("progress_pct") or 0) / 100.0))
        candle_w = 0.15 + 0.25 * prog

    live_p = _f(live.get("live_probability_up"))
    if live_p is None:
        live_p = _f(live.get("live_p"))
    checklist_p = _checklist_p_up(indications)
    micro_p = _micro_p_up(micro)
    mom_p = _momentum_p_up(bars, atr)
    blend = _blend_p_up(
        live_p, checklist_p, micro_p, candle_p, candle_weight=candle_w, mom_p=mom_p
    )
    p_up = float(blend["p_up"])
    pts5 = _expected_points(atr, 5)
    pts10 = _expected_points(atr, 10)
    # Confidence-scale expected points: weak lean → smaller stated move.
    conf_scale = max(0.35, min(1.0, abs(p_up - 0.5) / 0.25))
    if pts5 is not None:
        pts5 = round(max(1.0, pts5 * conf_scale), 1)
    if pts10 is not None:
        pts10 = round(max(1.0, pts10 * conf_scale), 1)
    # Remaining expected move shrinks as the bar progresses.
    remain_pts = None
    if pts5 is not None and candle and candle.get("forming"):
        left_frac = max(0.15, 1.0 - float(candle.get("progress_pct") or 0) / 100.0)
        remain_pts = round(max(1.0, pts5 * left_frac), 1)
    direction = _direction(p_up)
    side = direction["side"]
    p_side = float(direction["p_side"])
    summary = (indications or {}).get("summary") or {}
    bull = int(summary.get("bullish") or 0)
    bear = int(summary.get("bearish") or 0)
    flat = int(summary.get("neutral") or 0)

    vs_call = None
    if active_call and active_call.get("decision"):
        dec = str(active_call.get("decision") or "").upper()
        call_buy = "BUY" in dec
        helps = (side == "UP" and call_buy) or (side == "DOWN" and not call_buy)
        fights = (side == "UP" and not call_buy) or (side == "DOWN" and call_buy)
        label_bar = "This 5m candle" if (candle and candle.get("forming")) else "Next bar"
        if helps:
            vs_call = {"tone": "supportive", "label": f"{label_bar} supports your call"}
        elif fights:
            vs_call = {"tone": "against", "label": f"{label_bar} fights your call — stay alert"}
        else:
            vs_call = {"tone": "neutral", "label": f"{label_bar} is mixed vs your call"}

    use_pts = remain_pts if remain_pts is not None else pts5
    up_level = round(px + use_pts, 1) if px is not None and use_pts else None
    down_level = round(px - use_pts, 1) if px is not None and use_pts else None

    return {
        "available": True,
        "horizon_min": 5,
        "horizon_alt_min": 10,
        "mode": "forming" if (candle and candle.get("forming")) else "next",
        "p_up": round(p_up, 4),
        "p_down": round(1.0 - p_up, 4),
        "side": side,
        "p_side": round(p_side, 4),
        "tone": direction["tone"],
        "lean": direction.get("lean"),
        "expected_points_5m": pts5,
        "expected_points_10m": pts10,
        "remain_points": remain_pts,
        "atr_5m": round(atr, 2) if atr is not None else None,
        "react_up": up_level,
        "react_down": down_level,
        "candle": candle,
        "mom_p_up": round(mom_p, 4) if mom_p is not None else None,
        "votes": {
            "bullish": bull,
            "bearish": bear,
            "neutral": flat,
        },
        "blend": blend,
        "headline": _headline(side, p_side, pts5, candle=candle, remain_pts=remain_pts),
        "headline_10m": (
            f"Next 10 min — lean {side} ({int(round(p_side * 100))}%)"
            + (f" by about {pts10:.0f} pts." if pts10 else ".")
        ),
        "vs_call": vs_call,
        "disclaimer": (
            "Short-horizon indication from live 5m candle + closed-bar momentum "
            "+ checklist/micro — logged for quality; not a listed call."
        ),
        "asof": asof,
        "logged_for_quality": True,
    }


def call_live_track(
    *,
    active_call: Optional[Dict[str, Any]],
    fno_model: Optional[Dict[str, Any]] = None,
    live_context: Optional[Dict[str, Any]] = None,
    path_health: Optional[Dict[str, Any]] = None,
    short_horizon: Optional[Dict[str, Any]] = None,
    combined_score: Optional[float] = None,
    confidence: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Entry vs live scores for an open call — high-alert tracking payload."""
    if not active_call or active_call.get("decision") in (None, "HOLD"):
        return None
    # Caller should pass an already-open ticket (open_ticket()). Also accept
    # explicit open flags for UI payloads.
    st = str(active_call.get("status") or "open").lower()
    if active_call.get("open") is False or st in ("closed", "hit_sl", "hit_t1", "expired", "cancelled"):
        return None
    readings = active_call.get("readings") if isinstance(active_call.get("readings"), dict) else {}
    fm = fno_model or {}
    live = live_context or {}
    micro = live.get("microstructure") or {}

    entry_pt1 = _f(readings.get("p_t1"))
    if entry_pt1 is None:
        entry_pt1 = _f(active_call.get("p_t1"))
    live_pt1 = _f(fm.get("p_t1"))
    entry_micro = _f(readings.get("micro_score"))
    live_micro = _f(micro.get("micro_score"))
    entry_buy_p = _f(readings.get("buy_p"))
    live_buy_p = _f(fm.get("buy_p"))
    live_p = _f(live.get("live_probability_up"))
    if live_p is None:
        live_p = _f(live.get("live_p"))

    decision = str(active_call.get("decision") or "").upper()
    call_buy = "BUY" in decision
    # Side-aligned live probability for the open call.
    if live_p is not None:
        live_side_p = live_p if call_buy else (1.0 - live_p)
    else:
        live_side_p = None

    p_sl = None
    if live_pt1 is not None:
        p_sl = round(max(0.0, min(1.0, 1.0 - live_pt1)), 4)
    elif entry_pt1 is not None:
        p_sl = round(max(0.0, min(1.0, 1.0 - entry_pt1)), 4)

    ph = path_health or {}
    sh = short_horizon or {}
    vs = sh.get("vs_call") or {}

    guide_bits: List[str] = []
    if ph.get("message"):
        guide_bits.append(str(ph["message"]))
    if vs.get("label"):
        guide_bits.append(str(vs["label"]))
    if live_side_p is not None:
        pct = int(round(live_side_p * 100))
        guide_bits.append(f"Live tape favors this {decision} at {pct}%.")

    return {
        "available": True,
        "decision": decision,
        "entry_p_t1": round(entry_pt1, 4) if entry_pt1 is not None else None,
        "live_p_t1": round(live_pt1, 4) if live_pt1 is not None else None,
        "p_sl": p_sl,
        "entry_buy_p": round(entry_buy_p, 4) if entry_buy_p is not None else None,
        "live_buy_p": round(live_buy_p, 4) if live_buy_p is not None else None,
        "entry_micro_score": round(entry_micro, 1) if entry_micro is not None else None,
        "live_micro_score": round(live_micro, 1) if live_micro is not None else None,
        "live_side_p": round(live_side_p, 4) if live_side_p is not None else None,
        "combined_score": round(float(combined_score), 4) if combined_score is not None else None,
        "confidence": round(float(confidence), 1) if confidence is not None else None,
        "path_state": ph.get("state"),
        "path_tone": ph.get("tone"),
        "path_message": ph.get("message"),
        "next_bar": {
            "side": sh.get("side"),
            "p_side": sh.get("p_side"),
            "expected_points_5m": sh.get("expected_points_5m"),
            "vs_call": vs,
            "headline": sh.get("headline"),
        },
        "guide": guide_bits[:4],
        "high_alert": bool(
            (ph.get("state") or "").startswith("WARN")
            or (vs.get("tone") == "against")
            or (live_side_p is not None and live_side_p < 0.42)
        ),
    }
