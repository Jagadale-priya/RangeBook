"""Live-session annotate for PA_STRUCTURE_SL_LIVE (structure SL, no fixed target).

Call on each new closed 1m (or from the poller). Never blocks Cap6 / other desks.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from prod_live.logic.pa_structure_live import (
    ACC_TAG,
    DESK,
    evaluate_bar_live,
    load_ledger,
    norm_1m,
)


def book_snapshot() -> Dict[str, Any]:
    return {
        "desk": DESK,
        "accuracy_tag": ACC_TAG,
        "sl": "prev_candle_swing_structure",
        "target": "none_fixed_trail_after_1R",
        "live_engine": True,
        "ledger": "prod_live/holding_accurate/pa_structure/live_session_calls.json",
    }


def _emit_pa_notify(call: dict) -> bool:
    """Desktop toast: entry + structure SL only (no constant target)."""
    try:
        import desktop_notify
    except Exception:
        return False
    side = str(call.get("side") or "").upper()
    setup = str(call.get("setup") or "")
    entry = call.get("entry")
    sl = call.get("stop_loss")
    risk = call.get("risk")
    hm = call.get("hm")
    reason = str(call.get("reason") or "")[:120]
    title = f"PA {side} · {setup}"
    msg = (
        f"NIFTY {hm} entry {entry} · SL {sl} (risk {risk}) · "
        f"no fixed TP · trail after 1R · {reason}"
    )
    dedupe = f"pa_structure|{call.get('day')}|{hm}|{side}|{setup}"
    return bool(
        desktop_notify.notify(
            title,
            msg,
            stock="NIFTY",
            kind="pa_structure",
            decision=side,
            entry=float(entry) if entry is not None else None,
            stop_loss=float(sl) if sl is not None else None,
            target_1=None,
            dedupe_key=dedupe,
            product="fno",
            payload={
                "desk": DESK,
                "accuracy_tag": ACC_TAG,
                "setup": setup,
                "risk": risk,
                "htf_bias": call.get("htf_bias"),
                "reason": call.get("reason"),
            },
        )
    )


def annotate_from_1m(
    bars_1m: pd.DataFrame,
    *,
    emit_notify: bool = True,
) -> Dict[str, Any]:
    """Rescan today's 1m; append new fires; optional toast."""
    meta = evaluate_bar_live(norm_1m(bars_1m) if bars_1m is not None else bars_1m)
    notified: List[dict] = []
    if emit_notify:
        for row in meta.get("added") or []:
            if _emit_pa_notify(row):
                notified.append(
                    {
                        "hm": row.get("hm"),
                        "side": row.get("side"),
                        "setup": row.get("setup"),
                        "entry": row.get("entry"),
                        "stop_loss": row.get("stop_loss"),
                    }
                )
    return {
        **book_snapshot(),
        "day": (meta.get("day_calls") or [{}])[0].get("day")
        if meta.get("day_calls")
        else None,
        "n_day": len(meta.get("day_calls") or []),
        "n_added": meta.get("n_added"),
        "added": meta.get("added"),
        "notified": notified,
        "summary": meta.get("summary"),
        "day_calls": meta.get("day_calls"),
        "evaluated_at": datetime.now().isoformat(timespec="seconds"),
    }


def ledger_today(day: Optional[str] = None) -> List[dict]:
    data = load_ledger()
    rows = data.get("calls") or []
    if day:
        return [r for r in rows if str(r.get("day")) == day]
    return list(rows)
