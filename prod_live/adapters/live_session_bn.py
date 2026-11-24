"""Annotate live analyze results with BANKNIFTY FINAL books only.

NIFTY / SENSEX are untouched by this adapter.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from prod_live.logic import bn_final_live as bn


def _session_hm(dual_call: Optional[dict], readings: Optional[dict]) -> Optional[str]:
    for obj in (dual_call, readings):
        if not isinstance(obj, dict):
            continue
        for k in ("hm", "time", "bar_hm"):
            v = obj.get(k)
            if v:
                return str(v)[:5]
    now = datetime.now()
    m = (now.minute // 5) * 5
    return f"{now.hour:02d}:{m:02d}"


def _session_entry(dual_call: Optional[dict], readings: Optional[dict]) -> Optional[float]:
    for obj in (dual_call, readings):
        if not isinstance(obj, dict):
            continue
        for k in ("entry", "price", "ltp", "close"):
            if obj.get(k) is not None:
                try:
                    return float(obj.get(k))
                except (TypeError, ValueError):
                    pass
    return None


def annotate_analyze_result(
    result: Dict[str, Any],
    *,
    symbol: str,
    dual_call: Optional[Dict[str, Any]] = None,
    readings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if str(symbol or "").upper() not in ("BANKNIFTY", "NIFTY BANK", "BANK NIFTY"):
        return result
    if not bn.enabled():
        return result

    snap = bn.book_registry()
    fa = dict(result.get("fno_analysis") or {})
    fa["final_bn_fno"] = snap

    today = date.today().isoformat()
    hm = _session_hm(dual_call, readings)
    entry = _session_entry(dual_call, readings)
    try:
        meta = bn.ensure_session_calls(
            today, dual_call=dual_call if isinstance(dual_call, dict) else None, hm=hm, entry=entry
        )
        fa["bn_final_live"] = {
            "desk": bn.DESK_CHAMP,
            "accuracy_tag": bn.ACCURACY_TAG,
            "day": meta.get("day"),
            "n_day": meta.get("n_day"),
            "n_added": meta.get("n_added"),
            "blocked": False,
            "live_engine": True,
            "brackets": dict(bn.BRACKETS),
        }
    except Exception as exc:
        fa["bn_final_live_error"] = str(exc)

    result["fno_analysis"] = fa
    result["final_bn_fno"] = snap

    markers = [
        bn.DESK_CHAMP,
        bn.DESK_PROVEN,
        bn.ACCURACY_TAG,
        "FINAL_BN_BOOKS",
        "LANE_LIVE",
    ]
    for obj in (dual_call, readings):
        if not isinstance(obj, dict):
            continue
        tags = list(obj.get("tags") or [])
        seen = set(str(t) for t in tags)
        for m in markers:
            if m not in seen:
                tags.append(m)
                seen.add(m)
        obj["tags"] = tags
        obj["accuracy_tag"] = obj.get("accuracy_tag") or bn.ACCURACY_TAG
        obj["accurate_tag"] = obj.get("accurate_tag") or bn.DESK_CHAMP
        if dual_call is obj and dual_call.get("decision") in ("BUY", "SELL"):
            try:
                px = float(dual_call.get("entry") or entry or 0)
            except (TypeError, ValueError):
                px = 0.0
            if px > 0:
                lv = bn.levels(px, str(dual_call.get("decision")))
                dual_call["stop_loss"] = lv["stop_loss"]
                dual_call["target_1"] = lv["target_1"]
                dual_call["t1_pts"] = lv["t1_pts"]
                dual_call["sl_pts"] = lv["sl_pts"]
    return result
