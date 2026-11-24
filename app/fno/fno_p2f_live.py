"""Live session hook — annotate NIFTY with FINAL 3 F&O books only.

Books: P2F (day+cap2) · P2G 10m · CHAMP_PLUS_T30SL30_CAP6
No volume stack / AGREE on NIFTY F&O.
Safe no-op if prod_live is unavailable or flag is off.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def annotate(
    result: Dict[str, Any],
    *,
    symbol: str,
    dual_call: Optional[Dict[str, Any]] = None,
    readings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    try:
        import fno_live_config

        if not fno_live_config.enable_p2f_live_accurate():
            return result
    except Exception:
        return result
    try:
        from prod_live.adapters.live_session_final import annotate_analyze_result

        return annotate_analyze_result(
            result,
            symbol=symbol,
            dual_call=dual_call,
            readings=readings,
        )
    except Exception as exc:
        try:
            fa = dict(result.get("fno_analysis") or {})
            fa["final_nifty_fno_error"] = str(exc)
            result["fno_analysis"] = fa
        except Exception:
            pass
        return result
