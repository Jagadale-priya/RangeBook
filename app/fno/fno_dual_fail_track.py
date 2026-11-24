"""Track dual-track SL fails (esp. range first-break champion reverses).

Append-only JSONL under stock_signal_data/fno_validate/research/
Does not change listing — research / desk review only.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import path_setup

ROOT = path_setup.ROOT
LOG = ROOT / "stock_signal_data/fno_validate/research/dual_sl_fails.jsonl"


def _safe(v: Any) -> Any:
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def classify_fail(readings: Optional[dict], *, decision: str = "") -> str:
    rd = readings if isinstance(readings, dict) else {}
    regime = str(rd.get("regime") or "").lower()
    first = bool(rd.get("first_break") or (rd.get("model_view") or {}).get("first_break"))
    track = str(rd.get("track") or rd.get("source") or "")
    if track == "champion" and first and regime == "range":
        return "range_fb_champion_reverse"
    if track == "champion" and first:
        return "champion_fb_sl"
    if track == "proven_100":
        return "proven_sl"
    return "dual_sl"


def maybe_log_closed_ticket(
    ticket: Optional[dict],
    *,
    symbol: str = "NIFTY",
    closed_row: Optional[dict] = None,
) -> Optional[dict]:
    """Log when a dual-track ticket closes on SL. Safe no-op on errors."""
    try:
        live = closed_row
        if live is None and isinstance(ticket, dict):
            hist = list(ticket.get("history") or [])
            live = hist[-1] if hist else ticket
        if not isinstance(live, dict):
            return None
        status = str(live.get("status") or "")
        if status not in ("sl_before_t1", "same_bar_both", "early_drop"):
            return None
        readings = live.get("readings") if isinstance(live.get("readings"), dict) else {}
        if not readings and isinstance(ticket, dict):
            readings = ticket.get("readings") if isinstance(ticket.get("readings"), dict) else {}
        dualish = bool(readings.get("dual_track")) or str(
            readings.get("track") or readings.get("source") or ""
        ) in ("proven_100", "champion", "dual10m", "crown_5m")
        if not dualish:
            return None

        pattern = classify_fail(readings, decision=str(live.get("decision") or ""))
        row = {
            "logged_at": datetime.now().isoformat(timespec="seconds"),
            "symbol": str(symbol or "").upper(),
            "pattern": pattern,
            "decision": live.get("decision"),
            "status": status,
            "track": readings.get("track") or readings.get("source"),
            "regime": readings.get("regime")
            or (readings.get("model_view") or {}).get("regime"),
            "first_break": readings.get("first_break")
            or (readings.get("model_view") or {}).get("first_break"),
            "or_ext": readings.get("or_ext")
            or (readings.get("model_view") or {}).get("or_ext"),
            "p_t1": live.get("p_t1") or readings.get("p_t1"),
            "entry": live.get("entry"),
            "stop_loss": live.get("stop_loss"),
            "target_1": live.get("target_1"),
            "taken_at": live.get("taken_at"),
            "closed_at": live.get("closed_at"),
            "points": live.get("points"),
            "exit_price": live.get("exit_price"),
        }
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({k: _safe(v) for k, v in row.items()}, default=str) + "\n")
        return row
    except Exception:
        return None
