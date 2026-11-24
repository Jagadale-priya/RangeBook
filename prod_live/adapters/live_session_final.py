"""Annotate live analyze results with FINAL NIFTY F&O books only.

Books: P2F (day+cap2) · P2G 10m · CHAMP_PLUS_T30SL30_CAP6
CHAMP_PLUS runs live ticket-fill on the session day (no blockers).
No volume stack / AGREE on NIFTY F&O.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from prod_live.logic.combined_live_book import final_book_registry
from prod_live.logic.champ_plus_live import (
    ACCURACY_TAG as CHAMP_ACC,
    DESK as CHAMP_DESK,
    ensure_session_calls,
)
from prod_live.logic.p2f_day_live import LIVE_DAY_DESKS
from prod_live.logic.p2f_cap2_live import LIVE_CAP2_DESKS
from prod_live.logic.p2g_10m_live import LIVE_P2G_DESKS
from prod_live.logic.accuracy_notify import (
    build_accuracy_notify,
    emit_accuracy_notify,
)


def book_snapshot() -> Dict[str, Any]:
    reg = final_book_registry()
    return {
        **reg,
        "primary_day": LIVE_DAY_DESKS[0],
        "primary_cap2": LIVE_CAP2_DESKS[0],
        "primary_p2g": LIVE_P2G_DESKS[0],
        "primary_champ": CHAMP_DESK,
        "champ_live_engine": True,
        "confirm": {
            "final": "prod_live/tests/confirm_final_nifty_3books.py",
            "p2f_day": "prod_live/tests/confirm_p2f_day_live_1y.py",
            "p2f_cap2": "prod_live/tests/confirm_p2f_cap2_live_1y.py",
            "champ_live": "prod_live/tests/confirm_champ_plus_live_engine.py",
            "p2g_5y": "prod_live/reports/5y/ACC_PHASE2G_10M_5Y.md",
            "champ_5y": "prod_live/reports/5y/CHAMPION_PLUS_T30_SL30_5Y.md",
        },
    }


def _append_tag(tags: List[Any], value: str) -> List[Any]:
    seen = {str(t) for t in tags}
    if value not in seen:
        tags.append(value)
    return tags


def _session_hm(dual_call: Optional[dict], readings: Optional[dict]) -> Optional[str]:
    for obj in (dual_call, readings):
        if not isinstance(obj, dict):
            continue
        for k in ("hm", "time", "bar_hm"):
            v = obj.get(k)
            if v:
                return str(v)
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
    emit_notify: bool = True,
) -> Dict[str, Any]:
    if str(symbol or "").upper() not in ("NIFTY", "NIFTY 50", "NIFTY50"):
        return result
    snap = book_snapshot()
    fa = dict(result.get("fno_analysis") or {})
    fa["final_nifty_fno"] = snap
    fa.pop("p2f_live", None)

    # --- CHAMP_PLUS live ticket-fill for today (never blocks other desks) ---
    # IST session date — UTC date.today() can lag the desk after midnight UTC.
    try:
        from zoneinfo import ZoneInfo

        today = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
    except Exception:
        today = date.today().isoformat()
    hm = _session_hm(dual_call, readings)
    entry = _session_entry(dual_call, readings)
    champ_meta: Dict[str, Any] = {}
    try:
        champ_meta = ensure_session_calls(
            today,
            dual_call=dual_call if isinstance(dual_call, dict) else None,
            hm=hm,
            entry=entry,
        )
        fa["champ_plus_live"] = {
            "desk": CHAMP_DESK,
            "accuracy_tag": CHAMP_ACC,
            "day": champ_meta.get("day"),
            "n_day": champ_meta.get("n_day"),
            "n_added": champ_meta.get("n_added"),
            "blocked": False,
            "live_engine": True,
            "day_calls": [
                {
                    "day": r.get("day"),
                    "hm": r.get("hm"),
                    "side": r.get("decision"),
                    "entry": r.get("entry"),
                    "stop_loss": r.get("stop_loss"),
                    "target_1": r.get("target_1"),
                    "accuracy_tag": r.get("accuracy_tag"),
                    "track": r.get("track"),
                    "live_fire": r.get("live_fire"),
                }
                for r in (champ_meta.get("day_calls") or [])
            ],
            "added": [
                {
                    "day": r.get("day"),
                    "hm": r.get("hm"),
                    "decision": r.get("decision"),
                    "side": r.get("decision") or r.get("side"),
                    "entry": r.get("entry"),
                    "stop_loss": r.get("stop_loss"),
                    "target_1": r.get("target_1"),
                    "p_t1": r.get("p_t1"),
                    "track": r.get("track"),
                    "accuracy_tag": r.get("accuracy_tag") or r.get("accuracy_label"),
                    "accuracy_label": r.get("accuracy_label"),
                    "tags": r.get("tags"),
                    "live_fire": r.get("live_fire"),
                    "fired_at": r.get("fired_at"),
                    "afternoon_thrust": r.get("afternoon_thrust"),
                    "morning_strong_thrust": r.get("morning_strong_thrust"),
                }
                for r in (champ_meta.get("added") or [])
            ],
        }
        # accuracy-tag notify for newly fired CHAMP calls
        if emit_notify:
            for r in champ_meta.get("added") or []:
                try:
                    payload = build_accuracy_notify(r, dry_run=False)
                    emit_accuracy_notify(payload)
                except Exception:
                    pass
    except Exception as exc:
        fa["champ_plus_live_error"] = str(exc)
        champ_meta = {"blocked": False, "error": str(exc)}

    result["fno_analysis"] = fa
    result["final_nifty_fno"] = snap
    result["champ_plus_live"] = fa.get("champ_plus_live")

    markers = [
        snap["primary_day"],
        "ACC_RANGE_98_100",
        snap["primary_p2g"],
        "ACC_RANGE_94_100",
        CHAMP_DESK,
        CHAMP_ACC,
        snap["primary_cap2"],
        "LANE_LIVE",
        "FINAL_NIFTY_3BOOKS",
        "CHAMP_PLUS_LIVE_ENGINE",
    ]

    for obj in (dual_call, readings):
        if not isinstance(obj, dict):
            continue
        tags = list(obj.get("accuracy_tags") or obj.get("tags") or [])
        tags = [
            t
            for t in tags
            if str(t)
            not in (
                "STACK_PLUS_CROWN_HTF_CAP2",
                "AGREE_15M_ANY5",
                "BOOK_VOLUME",
                "LIVE_AGREE",
            )
        ]
        # If session dual matches a CHAMP day call (same side), stamp CHAMP tags
        try:
            side = str(obj.get("decision") or "").upper()
            for r in champ_meta.get("day_calls") or []:
                if str(r.get("decision") or "").upper() == side:
                    tags = _append_tag(tags, CHAMP_DESK)
                    tags = _append_tag(tags, CHAMP_ACC)
                    obj["champ_plus_match"] = True
                    obj["champ_plus_call"] = {
                        "hm": r.get("hm"),
                        "entry": r.get("entry"),
                        "stop_loss": r.get("stop_loss"),
                        "target_1": r.get("target_1"),
                        "accuracy_tag": CHAMP_ACC,
                    }
                    break
        except Exception:
            pass
        merged: List[Any] = []
        for m in markers:
            merged = _append_tag(merged, m)
        for t in tags:
            merged = _append_tag(merged, t)
        obj["accuracy_tags"] = merged
        obj["tags"] = merged
        obj["final_nifty_fno"] = {
            "books": ["p2f", "p2g_10m", "champ_plus"],
            "champ_live_engine": True,
            "ui_combine": "same day+side+hm → 1 call, tags accuracy-first, never block",
            "excluded": ["STACK_PLUS_CROWN_HTF_CAP2", "AGREE_15M_ANY5"],
        }
    return result
