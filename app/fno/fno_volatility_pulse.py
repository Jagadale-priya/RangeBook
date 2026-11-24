"""Short-horizon volatility pulse for index F&O.

Samples LTP on every live poll and F&O refresh, then flags when the market
can whip up or down quickly (roughly one-minute moves). Indication only —
does not change BUY/SELL/HOLD.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

# Index-specific 1-minute move thresholds (percent and points).
_LIMITS = {
    "NIFTY": {"warn_pct": 0.09, "crit_pct": 0.16, "warn_pts": 18.0, "crit_pts": 32.0},
    "BANKNIFTY": {"warn_pct": 0.11, "crit_pct": 0.19, "warn_pts": 45.0, "crit_pts": 80.0},
    "FINNIFTY": {"warn_pct": 0.10, "crit_pct": 0.17, "warn_pts": 18.0, "crit_pts": 32.0},
}
_DEFAULT = _LIMITS["NIFTY"]
_WINDOW_SEC = 300
_MIN_SPAN_SEC = 30.0
_ONE_MIN = 60.0
_THREE_MIN = 180.0


def _limits(symbol: str) -> Dict[str, float]:
    return _LIMITS.get(str(symbol or "").upper(), _DEFAULT)


def _ts_unix(ts: Any = None) -> float:
    if ts is None:
        return time.time()
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        from datetime import datetime

        if isinstance(ts, datetime):
            return ts.timestamp()
        import pandas as pd

        return pd.Timestamp(ts).timestamp()
    except Exception:
        return time.time()


def push_sample(
    samples: Optional[List[Dict[str, Any]]],
    price: float,
    *,
    ts: Any = None,
) -> List[Dict[str, Any]]:
    """Append a price sample and drop anything older than five minutes."""
    now = _ts_unix(ts)
    try:
        px = float(price)
    except (TypeError, ValueError):
        return list(samples or [])
    if px <= 0:
        return list(samples or [])
    hist = list(samples or [])
    hist.append({"t": now, "p": round(px, 2)})
    cutoff = now - _WINDOW_SEC
    hist = [h for h in hist if float(h.get("t") or 0) >= cutoff]
    if len(hist) > 220:
        hist = hist[-220:]
    return hist


def _baseline_sample(samples: List[Dict[str, Any]], end_t: float, lookback_sec: float) -> Optional[Dict[str, Any]]:
    """Price at or just before (end - lookback); else oldest point in the buffer."""
    target = end_t - lookback_sec
    upto = [s for s in samples if float(s["t"]) <= end_t]
    if len(upto) < 2:
        return None
    at_or_before = [s for s in upto if float(s["t"]) <= target]
    if at_or_before:
        return at_or_before[-1]
    return upto[0]


def _window_stats(
    samples: List[Dict[str, Any]], span_sec: float
) -> Optional[Tuple[float, float, float, float, float]]:
    """Return (move_pts, move_pct, swing_pts, swing_pct, span_sec_actual)."""
    if len(samples) < 2:
        return None
    end_t = float(samples[-1]["t"])
    base_row = _baseline_sample(samples, end_t, span_sec)
    if base_row is None:
        return None
    base_t = float(base_row["t"])
    actual_span = end_t - base_t
    if actual_span < _MIN_SPAN_SEC:
        return None
    win = [s for s in samples if base_t <= float(s["t"]) <= end_t]
    prices = [float(s["p"]) for s in win]
    base = float(base_row["p"])
    last = float(samples[-1]["p"])
    if base <= 0:
        return None
    move = last - base
    move_pct = move / base * 100.0
    swing = max(prices) - min(prices)
    swing_pct = swing / base * 100.0
    return move, move_pct, swing, swing_pct, actual_span


def _tier(
    symbol: str,
    move_pct: float,
    swing_pct: float,
    move_pts: float,
    swing_pts: float,
) -> str:
    lim = _limits(symbol)
    score = 0
    for pct, pts in ((abs(move_pct), abs(move_pts)), (swing_pct, swing_pts)):
        if pct >= lim["crit_pct"] or pts >= lim["crit_pts"]:
            score = max(score, 2)
        elif pct >= lim["warn_pct"] or pts >= lim["warn_pts"]:
            score = max(score, 1)
    if score >= 2:
        return "critical"
    if score >= 1:
        return "warning"
    return "calm"


def assess(
    samples: Optional[List[Dict[str, Any]]],
    symbol: str,
    *,
    vix_level: float = 0.0,
    vix_change_pct: Optional[float] = None,
    micro: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the pulse read from stored samples."""
    hist = list(samples or [])
    sym = str(symbol or "NIFTY").upper()
    empty = {
        "available": False,
        "active": False,
        "level": "calm",
        "severity": "info",
        "headline": "Volatility pulse warming up — need a minute of live prices.",
        "detail": "",
        "move_1m_pts": None,
        "move_1m_pct": None,
        "swing_1m_pts": None,
        "swing_1m_pct": None,
        "samples": len(hist),
    }
    if len(hist) < 3:
        return empty

    one = _window_stats(hist, _ONE_MIN)
    three = _window_stats(hist, _THREE_MIN)
    if one is None:
        out = dict(empty)
        out["available"] = True
        out["samples"] = len(hist)
        out["headline"] = "Collecting live prices for a 1-minute volatility read…"
        return out

    move, move_pct, swing, swing_pct, span = one
    tier = _tier(sym, move_pct, swing_pct, move, swing)

    if vix_change_pct is not None:
        try:
            if abs(float(vix_change_pct)) >= 6.0 and tier == "calm":
                tier = "warning"
            elif abs(float(vix_change_pct)) >= 10.0:
                tier = "critical" if tier != "calm" else "warning"
        except (TypeError, ValueError):
            pass

    micro = micro or {}
    if micro.get("five_min_conflict") and tier == "calm" and swing_pct >= _limits(sym)["warn_pct"] * 0.85:
        tier = "warning"

    if vix_level >= 20 and tier == "calm" and swing_pct >= _limits(sym)["warn_pct"] * 0.9:
        tier = "warning"

    active = tier in ("warning", "critical")
    severity = "critical" if tier == "critical" else ("warning" if tier == "warning" else "info")
    dir_word = "up" if move > 0 else ("down" if move < 0 else "flat")
    headline = "Market is calm on the last minute of tape."
    detail = ""
    if active:
        headline = (
            f"Fast market — about {abs(move):.0f} pts ({abs(move_pct):.2f}%) "
            f"{dir_word} in ~{int(span)}s; {swing:.0f} pts whipsaw. "
            f"Size and stops can be hit quickly."
        )
        if tier == "critical":
            headline = "Very volatile — " + headline
        detail = "Indication only. The call badge does not change; tighten risk or wait for a settle."
    elif three:
        _, m3, _, s3, _ = three
        if abs(m3) > 0 or s3 > 0:
            detail = f"3m: {m3:+.2f}% move, {s3:.2f}% range."

    return {
        "available": True,
        "active": active,
        "level": tier,
        "severity": severity,
        "headline": headline,
        "detail": detail,
        "move_1m_pts": round(move, 2),
        "move_1m_pct": round(move_pct, 3),
        "swing_1m_pts": round(swing, 2),
        "swing_1m_pct": round(swing_pct, 3),
        "samples": len(hist),
        "span_sec": round(span, 1),
    }


def record_and_assess(
    samples: Optional[List[Dict[str, Any]]],
    symbol: str,
    price: float,
    *,
    ts: Any = None,
    vix_level: float = 0.0,
    vix_change_pct: Optional[float] = None,
    micro: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    hist = push_sample(samples, price, ts=ts)
    pulse = assess(
        hist,
        symbol,
        vix_level=vix_level,
        vix_change_pct=vix_change_pct,
        micro=micro,
    )
    return hist, pulse


def attach_pulse_alert(alerts: List[Dict[str, Any]], pulse: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add a volatility alert when the pulse is hot (for notifications + Reasons)."""
    if not pulse or not pulse.get("active"):
        return alerts
    out = list(alerts)
    out.append(
        {
            "code": "VOLATILITY_SPIKE",
            "severity": pulse.get("severity") or "warning",
            "message": pulse.get("headline") or "Short-term volatility elevated.",
        }
    )
    return out
