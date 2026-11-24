"""Live session hook — annotate SENSEX with FINAL books.

Safe no-op for other symbols / when flag off / prod_live missing.
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

        if not getattr(fno_live_config, "enable_sensex_final_live", lambda: True)():
            return result
    except Exception:
        pass
    try:
        from prod_live.adapters.live_session_sensex import annotate_analyze_result

        return annotate_analyze_result(
            result, symbol=symbol, dual_call=dual_call, readings=readings
        )
    except Exception as exc:
        try:
            fa = dict(result.get("fno_analysis") or {})
            fa["final_sensex_fno_error"] = str(exc)
            result["fno_analysis"] = fa
        except Exception:
            pass
        return result
