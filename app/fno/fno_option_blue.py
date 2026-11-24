"""Option Blue — REMOVED.

Final live desk is Scalper (`fno_scalper_1m`) with locked PA `pa_no_trap`.
API routes `/fno/option-blue/*` return HTTP 410. Stubs keep old imports safe.
"""
from __future__ import annotations

from typing import Any, Dict


def scan_option_blue(*_a: Any, **_k: Any) -> Dict[str, Any]:
    return {
        "ok": False,
        "error": "Option Blue removed. Use Scalper tab (PA pa_no_trap).",
        "desk": "REMOVED",
        "calls": [],
    }


def live_option_blue(*_a: Any, **_k: Any) -> Dict[str, Any]:
    return {
        "ok": False,
        "error": "Option Blue removed. Use /fno/scalper/live.",
        "desk": "REMOVED",
        "live": False,
    }


def option_side_gate(_meta: Any = None):
    return None
