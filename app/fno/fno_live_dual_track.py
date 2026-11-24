"""Dispatch NIFTY / SENSEX dual-track live overlays (BANKNIFTY disabled)."""
from __future__ import annotations

from typing import Any, Dict, Optional


def _norm_bars(bars: Any) -> Any:
    """Kite history uses open/high/low/close; dual-track OR logic needs Open/High/Low/Close."""
    try:
        import fno_levels

        normed = fno_levels._norm(bars)
        return normed if normed is not None else bars
    except Exception:
        return bars


def apply_to_analyze_result(
    stock_key: str,
    result: Dict[str, Any],
    *,
    bars: Any,
    asof: Any,
    session_ticket: Optional[dict],
    price: Any,
    day_range: Optional[dict] = None,
) -> Optional[Dict[str, Any]]:
    key = str(stock_key or "").upper()
    bars = _norm_bars(bars)
    if key == "NIFTY":
        import nifty_live_dual_track

        return nifty_live_dual_track.apply_to_analyze_result(
            result,
            bars=bars,
            asof=asof,
            session_ticket=session_ticket,
            price=price,
            day_range=day_range,
        )
    # BANKNIFTY removed from live F&O desk — no dual-track / pack load.
    if key == "SENSEX":
        import sensex_live_dual_track

        return sensex_live_dual_track.apply_to_analyze_result(
            result,
            bars=bars,
            asof=asof,
            session_ticket=session_ticket,
            price=price,
            day_range=day_range,
        )
    return None
