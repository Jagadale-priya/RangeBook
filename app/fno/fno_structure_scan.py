"""Live structure / pattern scan for F&O desks (idle + open-call).

Detects classic shapes on 5m/15m tape: W / M (double bottom/top), Fibonacci
zones, opening-range proximity, EMA ribbon, plus candle catalog patterns.
Produces short user guidance — never opens a call by itself.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

FIB_LEVELS = (0.236, 0.382, 0.5, 0.618, 0.786)


def _norm(bars: Any) -> Optional[pd.DataFrame]:
    if bars is None:
        return None
    try:
        if hasattr(bars, "empty") and bars.empty:
            return None
        work = bars.copy()
        rename = {}
        for c in work.columns:
            cl = str(c).strip().lower()
            if cl in ("open", "o"):
                rename[c] = "Open"
            elif cl in ("high", "h"):
                rename[c] = "High"
            elif cl in ("low", "l"):
                rename[c] = "Low"
            elif cl in ("close", "c"):
                rename[c] = "Close"
        if rename:
            work = work.rename(columns=rename)
        need = {"Open", "High", "Low", "Close"}
        if not need.issubset(set(work.columns)):
            return None
        for col in need:
            work[col] = pd.to_numeric(work[col], errors="coerce")
        work = work.dropna(subset=list(need))
        return work if len(work) >= 8 else None
    except Exception:
        return None


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _dedupe_swings(points: List[Tuple[int, float]], *, keep_high: bool) -> List[Tuple[int, float]]:
    """Collapse clustered swing prints; keep the extreme in each cluster."""
    if not points:
        return []
    out: List[Tuple[int, float]] = [points[0]]
    for idx, price in points[1:]:
        prev_i, prev_p = out[-1]
        if idx - prev_i <= 2:
            if keep_high and price >= prev_p:
                out[-1] = (idx, price)
            elif (not keep_high) and price <= prev_p:
                out[-1] = (idx, price)
            continue
        out.append((idx, price))
    return out


def _swings(high: np.ndarray, low: np.ndarray, left: int = 2, right: int = 2) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """Local swing highs / lows (index, price)."""
    highs: List[Tuple[int, float]] = []
    lows: List[Tuple[int, float]] = []
    n = len(high)
    for i in range(left, n - right):
        window_h = high[i - left : i + right + 1]
        window_l = low[i - left : i + right + 1]
        if high[i] >= float(np.max(window_h)) - 1e-9:
            highs.append((i, float(high[i])))
        if low[i] <= float(np.min(window_l)) + 1e-9:
            lows.append((i, float(low[i])))
    return _dedupe_swings(highs, keep_high=True), _dedupe_swings(lows, keep_high=False)


def _double_bottom(lows: List[Tuple[int, float]], highs: List[Tuple[int, float]], price: float, tol: float) -> Optional[Dict[str, Any]]:
    if len(lows) < 2:
        return None
    (i1, l1), (i2, l2) = lows[-2], lows[-1]
    if i2 - i1 < 3:
        return None
    mid = [h for h in highs if i1 < h[0] < i2]
    if not mid:
        return None
    neck = max(h[1] for h in mid)
    span = abs(l1 - l2)
    if span > tol:
        return None
    # Second low should not smash far below first.
    if l2 < l1 - tol * 0.5:
        return None
    broken = price > neck
    dist = neck - price
    return {
        "key": "w_double_bottom",
        "name": "W · double bottom",
        "lean": "BULLISH",
        "status": "broken" if broken else "forming",
        "neckline": round(neck, 1),
        "low_1": round(l1, 1),
        "low_2": round(l2, 1),
        "note": (
            f"W neckline {neck:.0f} broken — upside continuation watch."
            if broken
            else f"W forming · neckline {neck:.0f} ({dist:.0f} pts above). 5m close above may unlock BUY path."
        ),
        "trigger": round(neck, 1),
        "score": 3 if broken else 2,
    }


def _double_top(highs: List[Tuple[int, float]], lows: List[Tuple[int, float]], price: float, tol: float) -> Optional[Dict[str, Any]]:
    if len(highs) < 2:
        return None
    (i1, h1), (i2, h2) = highs[-2], highs[-1]
    if i2 - i1 < 3:
        return None
    mid = [l for l in lows if i1 < l[0] < i2]
    if not mid:
        return None
    neck = min(l[1] for l in mid)
    if abs(h1 - h2) > tol:
        return None
    if h2 > h1 + tol * 0.5:
        return None
    broken = price < neck
    dist = price - neck
    return {
        "key": "m_double_top",
        "name": "M · double top",
        "lean": "BEARISH",
        "status": "broken" if broken else "forming",
        "neckline": round(neck, 1),
        "high_1": round(h1, 1),
        "high_2": round(h2, 1),
        "note": (
            f"M neckline {neck:.0f} broken — downside continuation watch."
            if broken
            else f"M forming · neckline {neck:.0f} ({dist:.0f} pts below). 5m close below may unlock SELL path."
        ),
        "trigger": round(neck, 1),
        "score": 3 if broken else 2,
    }


def _fib_zone(highs: List[Tuple[int, float]], lows: List[Tuple[int, float]], price: float, atr: float) -> Optional[Dict[str, Any]]:
    if not highs or not lows:
        return None
    # Last major swing: prefer recent high after low (upswing) or low after high (downswing).
    last_hi = highs[-1]
    last_lo = lows[-1]
    if last_hi[0] > last_lo[0]:
        # Upswing from lo → hi; retrace down into fib.
        lo_p, hi_p = last_lo[1], last_hi[1]
        direction = "upswing"
    else:
        hi_p, lo_p = last_hi[1], last_lo[1]
        direction = "downswing"
    span = abs(hi_p - lo_p)
    if span < max(atr * 1.5, 8.0):
        return None
    near = None
    for lvl in FIB_LEVELS:
        if direction == "upswing":
            level = hi_p - span * lvl
        else:
            level = lo_p + span * lvl
        dist = abs(price - level)
        if dist <= max(atr * 0.45, 4.0):
            if near is None or dist < near["dist"]:
                near = {
                    "level": lvl,
                    "price": round(level, 1),
                    "dist": dist,
                }
    if not near:
        return None
    lean = "BULLISH" if direction == "upswing" else "BEARISH"
    pct = f"{near['level'] * 100:.1f}".rstrip("0").rstrip(".")
    return {
        "key": f"fib_{pct.replace('.', '_')}",
        "name": f"Fibonacci {pct}%",
        "lean": lean,
        "status": "at_zone",
        "level_price": near["price"],
        "fib": near["level"],
        "swing": direction,
        "note": (
            f"Price at Fib {pct}% ({near['price']:.0f}) on {direction}. "
            f"Next 5m reaction here often decides the clip."
        ),
        "trigger": near["price"],
        "score": 2 if near["level"] in (0.382, 0.5, 0.618) else 1,
    }


def _orb_watch(micro: Dict[str, Any], price: float, atr: float) -> Optional[Dict[str, Any]]:
    orb = micro.get("opening_range") if isinstance(micro.get("opening_range"), dict) else {}
    hi = _f(orb.get("or_high") or orb.get("high"))
    lo = _f(orb.get("or_low") or orb.get("low"))
    if hi is None or lo is None or hi <= lo:
        return None
    band = max(atr * 0.35, 3.0)
    if abs(price - hi) <= band:
        broken = price > hi
        return {
            "key": "orb_high",
            "name": "Opening-range high",
            "lean": "BULLISH",
            "status": "broken" if broken else "testing",
            "trigger": round(hi, 1),
            "note": (
                f"Above OR high {hi:.0f} — breakout watch."
                if broken
                else f"Testing OR high {hi:.0f}. 5m close above can start a BUY setup."
            ),
            "score": 2 if broken else 2,
        }
    if abs(price - lo) <= band:
        broken = price < lo
        return {
            "key": "orb_low",
            "name": "Opening-range low",
            "lean": "BEARISH",
            "status": "broken" if broken else "testing",
            "trigger": round(lo, 1),
            "note": (
                f"Below OR low {lo:.0f} — breakdown watch."
                if broken
                else f"Testing OR low {lo:.0f}. 5m close below can start a SELL setup."
            ),
            "score": 2 if broken else 2,
        }
    return None


def _ema_ribbon(work: pd.DataFrame, price: float) -> Optional[Dict[str, Any]]:
    if len(work) < 50:
        return None
    close = work["Close"].astype(float)
    e9 = float(close.ewm(span=9, adjust=False).mean().iloc[-1])
    e20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    e50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
    stacked_up = e9 > e20 > e50 and price > e9
    stacked_dn = e9 < e20 < e50 and price < e9
    if stacked_up:
        return {
            "key": "ema_stack_up",
            "name": "EMA 9>20>50 stack",
            "lean": "BULLISH",
            "status": "active",
            "note": f"Bullish EMA ribbon (9 {e9:.0f} · 20 {e20:.0f} · 50 {e50:.0f}). Pullbacks to 9/20 are watch zones.",
            "trigger": round(e9, 1),
            "score": 1,
        }
    if stacked_dn:
        return {
            "key": "ema_stack_down",
            "name": "EMA 9<20<50 stack",
            "lean": "BEARISH",
            "status": "active",
            "note": f"Bearish EMA ribbon (9 {e9:.0f} · 20 {e20:.0f} · 50 {e50:.0f}). Rallies to 9/20 are watch zones.",
            "trigger": round(e9, 1),
            "score": 1,
        }
    # Price hugging EMA9
    if abs(price - e9) <= max(abs(e9) * 0.0004, 3.0):
        lean = "BULLISH" if e9 >= e20 else "BEARISH"
        return {
            "key": "ema9_touch",
            "name": "EMA9 touch",
            "lean": lean,
            "status": "testing",
            "note": f"Price kissing EMA9 ({e9:.0f}). Next 5m bounce/reject is the tell.",
            "trigger": round(e9, 1),
            "score": 1,
        }
    return None


def _candle_items(work: pd.DataFrame) -> List[Dict[str, Any]]:
    try:
        import analysis_engine

        raw = analysis_engine.detect_candlestick_window(work.tail(8))
    except Exception:
        return []
    patterns = list(raw.get("patterns") or [])
    bias = str(raw.get("bias") or "NEUTRAL").upper()
    out: List[Dict[str, Any]] = []
    for name in patterns[:6]:
        lean = "NEUTRAL"
        low = str(name).lower()
        if any(k in low for k in ("bull", "hammer", "morning", "piercing", "soldier", "dragonfly")):
            lean = "BULLISH"
        elif any(k in low for k in ("bear", "shooting", "evening", "dark cloud", "crow", "gravestone", "hanging")):
            lean = "BEARISH"
        elif bias in ("BULLISH", "BEARISH"):
            lean = bias
        out.append({
            "key": "candle_" + "".join(ch if ch.isalnum() else "_" for ch in low)[:40],
            "name": str(name),
            "lean": lean,
            "status": "active",
            "note": f"Candle: {name}.",
            "score": 1,
        })
    return out


def _atr(work: pd.DataFrame) -> float:
    try:
        import fno_risk_engine

        v = fno_risk_engine.bar_atr(work)
        if v is not None and float(v) > 0:
            return float(v)
    except Exception:
        pass
    # Fallback true-range mean
    h = work["High"].astype(float)
    l = work["Low"].astype(float)
    return float((h - l).tail(14).mean() or 10.0)


def _setup_guide(
    patterns: List[Dict[str, Any]],
    short_horizon: Optional[Dict[str, Any]],
    decision: str,
    has_open: bool,
) -> Dict[str, Any]:
    sh = short_horizon or {}
    side = str(sh.get("side") or "SIDEWAYS")
    p_side = _f(sh.get("p_side")) or 0.5
    pts = _f(sh.get("expected_points_5m"))
    top = patterns[0] if patterns else None

    if has_open:
        lines = [
            sh.get("headline") or "Live tape still updating beside the open call.",
        ]
        if top:
            lines.append(top.get("note") or top.get("name"))
        return {
            "mode": "call_open",
            "headline": "Call open — structure scan stays on high alert.",
            "lines": [x for x in lines if x][:4],
            "trigger": (top or {}).get("trigger"),
            "watch_for": (top or {}).get("name"),
        }

    if decision not in (None, "", "HOLD") and not has_open:
        # Listed call about to show / same payload
        return {
            "mode": "call_ready",
            "headline": f"Listed {decision} call is on the board.",
            "lines": [sh.get("headline") or "", (top or {}).get("note") or ""],
            "trigger": None,
            "watch_for": None,
        }

    # Idle — no listed call
    lines: List[str] = []
    if top and top.get("status") in ("forming", "testing", "at_zone"):
        lines.append(top["note"])
        trigger = top.get("trigger")
        lean = top.get("lean")
        if trigger and lean == "BULLISH":
            lines.append(
                f"If next 5m closes above {float(trigger):.0f}, desk rules may print a BUY call."
            )
        elif trigger and lean == "BEARISH":
            lines.append(
                f"If next 5m closes below {float(trigger):.0f}, desk rules may print a SELL call."
            )
    elif top and top.get("status") == "broken":
        lines.append(top["note"])
        lines.append("Pattern already triggered — waiting for model gate / levels to list a call.")
    else:
        move = f" (~{pts:.0f} pts)" if pts else ""
        if side == "UP":
            lines.append(
                f"No listed call yet. Next 5m leans UP ({int(round(p_side * 100))}%){move} — watching for a clean break setup."
            )
        elif side == "DOWN":
            lines.append(
                f"No listed call yet. Next 5m leans DOWN ({int(round(p_side * 100))}%){move} — watching for a clean break setup."
            )
        else:
            lines.append("No listed call yet. Tape is mixed — scanning W/M, Fib, ORB, and candles each refresh.")

    if sh.get("headline") and (not lines or sh["headline"] not in lines[0]):
        lines.insert(0, sh["headline"])

    headline = "Scanning for the next setup"
    if top:
        headline = f"Watching {top.get('name')} — no call yet"

    return {
        "mode": "scan",
        "headline": headline,
        "lines": [x for x in lines if x][:4],
        "trigger": (top or {}).get("trigger"),
        "watch_for": (top or {}).get("name"),
    }


def build(
    *,
    live_context: Optional[Dict[str, Any]] = None,
    price: Optional[float] = None,
    candlestick: Optional[Dict[str, Any]] = None,
    short_horizon: Optional[Dict[str, Any]] = None,
    decision: str = "HOLD",
    active_call: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    live = live_context or {}
    micro = live.get("microstructure") or {}
    px = _f(price) or _f(live.get("last")) or _f(live.get("ltp"))
    # Never ``df or other`` — pandas truthiness is ambiguous.
    try:
        import fno_session_rules

        raw15 = fno_session_rules.first_frame(
            live.get("bars_15m"),
            live.get("bars"),
            micro.get("bars_15m"),
        )
    except Exception:
        raw15 = live.get("bars_15m")
        if raw15 is None:
            raw15 = live.get("bars")
        if raw15 is None:
            raw15 = micro.get("bars_15m")
    bars15 = _norm(raw15)
    bars5 = _norm(live.get("bars_5m"))
    if bars5 is not None and len(bars5) >= 20:
        work = bars5
    elif bars15 is not None and len(bars15) >= 20:
        work = bars15
    else:
        work = bars5 if bars5 is not None else bars15
    patterns: List[Dict[str, Any]] = []

    if work is not None and px is not None:
        atr = _atr(work)
        tol = max(atr * 0.55, 8.0)
        high = work["High"].astype(float).to_numpy()
        low = work["Low"].astype(float).to_numpy()
        # Use recent window for structure (last ~40 bars)
        start = max(0, len(work) - 48)
        highs, lows = _swings(high[start:], low[start:], left=2, right=2)
        # Remap indices to absolute
        highs = [(i + start, p) for i, p in highs]
        lows = [(i + start, p) for i, p in lows]
        for fn in (
            lambda: _double_bottom(lows, highs, px, tol),
            lambda: _double_top(highs, lows, px, tol),
            lambda: _fib_zone(highs, lows, px, atr),
            lambda: _orb_watch(micro, px, atr),
            lambda: _ema_ribbon(work, px),
        ):
            try:
                hit = fn()
            except Exception:
                hit = None
            if hit:
                patterns.append(hit)
        patterns.extend(_candle_items(work))
    elif candlestick and (candlestick.get("patterns") or []):
        for name in (candlestick.get("patterns") or [])[:5]:
            patterns.append({
                "key": "candle",
                "name": str(name),
                "lean": str(candlestick.get("bias") or "NEUTRAL").upper(),
                "status": "active",
                "note": f"Candle: {name}.",
                "score": 1,
            })

    # Rank: higher score first, prefer structure over plain candles
    patterns.sort(key=lambda p: (-int(p.get("score") or 0), str(p.get("name") or "")))
    # Dedupe by key
    seen = set()
    uniq: List[Dict[str, Any]] = []
    for p in patterns:
        k = p.get("key") or p.get("name")
        if k in seen:
            continue
        seen.add(k)
        uniq.append(p)
    patterns = uniq[:10]

    has_open = bool(active_call and active_call.get("decision") not in (None, "HOLD"))
    guide = _setup_guide(patterns, short_horizon, str(decision or "HOLD"), has_open)

    bull = sum(1 for p in patterns if p.get("lean") == "BULLISH")
    bear = sum(1 for p in patterns if p.get("lean") == "BEARISH")

    return {
        "available": True,
        "patterns": patterns,
        "count": len(patterns),
        "bullish": bull,
        "bearish": bear,
        "top": patterns[0] if patterns else None,
        "guide": guide,
        "frame": "5m" if bars5 is not None and work is bars5 else ("15m" if work is not None else "none"),
        "disclaimer": "Pattern scan is indication only — listed calls still require the desk gate.",
    }
