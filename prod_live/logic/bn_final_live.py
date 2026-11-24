"""LIVE book — BANKNIFTY FINAL (PROVEN100 + CHAMP_PLUS). NIFTY untouched."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

LANE = "LIVE"
STATUS = "PROMOTED"
SYMBOL = "BANKNIFTY"

_HOLD = Path(__file__).resolve().parents[1] / "holding_accurate" / "banknifty_final"
_REPORT = Path(__file__).resolve().parents[1] / "reports" / "5y" / "BN_FINAL_CHAMP_PLUS_5Y.json"
_LIVE_LEDGER = _HOLD / "live_session_calls.json"

# Locked from research_bn_sensex_final_brackets.py (2026-11-16)
DESK_CHAMP = "BN_CHAMP_PLUS_T75SL75_CAP3"
DESK_PROVEN = "BN_PROVEN100_T75SL60"
ACCURACY_TAG = "ACC_RANGE_92_100"
ACCURACY_LO = 92.11
ACCURACY_HI = 100.0
BRACKETS = {"target": 75.0, "sl": 75.0, "risk": 75.0}
CAP = 3

WINDOW_1Y = {"start": "2025-10-24", "end": "2026-11-15"}
WINDOW_3Y = {"start": "2023-11-16", "end": "2026-11-15"}
WINDOW_5Y = {"start": "2021-11-16", "end": "2026-11-15"}


def _load_report() -> Dict[str, Any]:
    if not _REPORT.is_file():
        return {}
    return json.loads(_REPORT.read_text(encoding="utf-8"))


def expected_from_report() -> Dict[str, Any]:
    rep = _load_report()
    exp = rep.get("expected") or {}
    return {
        "1y": exp.get("1y") or {"n": 0, "hit_pct": 0.0},
        "3y": exp.get("3y") or {"n": 0, "hit_pct": 0.0},
        "5y": exp.get("5y") or {"n": 0, "hit_pct": 0.0},
    }


EXPECTED = expected_from_report()


def enabled() -> bool:
    return os.environ.get("ENABLE_BN_FINAL_LIVE", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def stamp_fields_for(desk: str = DESK_CHAMP) -> Dict[str, Any]:
    return {
        "lane": LANE,
        "status": STATUS,
        "not_live": False,
        "symbol": SYMBOL,
        "logic_level": "BN_FINAL",
        "desk_tag": desk,
        "accurate_tag": desk,
        "accuracy_tag": ACCURACY_TAG,
        "accuracy_lo": ACCURACY_LO,
        "accuracy_hi": ACCURACY_HI,
        "brackets": dict(BRACKETS),
        "tags": [
            desk,
            ACCURACY_TAG,
            "FINAL_BN_BOOKS",
            "LANE_LIVE",
        ],
    }


def stamp_live(rows: Iterable[dict], desk: str = DESK_CHAMP) -> List[dict]:
    meta = stamp_fields_for(desk)
    tags = list(meta["tags"])
    out = []
    for r in rows:
        rr = dict(r)
        side = str(rr.get("decision") or rr.get("side") or "").upper()
        if side and not rr.get("decision"):
            rr["decision"] = side
        rr.update(
            {
                "lane": LANE,
                "status": STATUS,
                "not_live": False,
                "symbol": SYMBOL,
                "logic_level": "BN_FINAL",
                "desk_tag": desk,
                "accurate_tag": desk,
                "accuracy_tag": ACCURACY_TAG,
                "book": "bn_final",
                "source_desk": desk,
                "brackets": dict(BRACKETS),
                "t1_pts": BRACKETS["target"],
                "sl_pts": BRACKETS["sl"],
            }
        )
        existing = list(rr.get("tags") or [])
        seen = set(existing)
        for t in tags:
            if t and t not in seen:
                existing.append(t)
                seen.add(t)
        rr["tags"] = existing
        out.append(rr)
    return out


def load_held_calls() -> List[dict]:
    rep = _load_report()
    path = Path(rep.get("calls_path") or (_HOLD / "champ_plus_t75_sl75_calls.json"))
    if not path.is_file():
        # fallback glob
        cands = list(_HOLD.glob("champ_plus_*.json"))
        if not cands:
            return []
        path = cands[0]
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("calls") or []
    return stamp_live(raw, DESK_CHAMP)


def load_proven_calls() -> List[dict]:
    path = _HOLD / "proven100_calls.json"
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("calls") or []
    return stamp_live(raw, DESK_PROVEN)


def _ledger_load() -> List[dict]:
    if not _LIVE_LEDGER.is_file():
        return []
    try:
        raw = json.loads(_LIVE_LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(raw, dict):
        return list(raw.get("calls") or [])
    return list(raw or [])


def _ledger_save(rows: List[dict]) -> None:
    _HOLD.mkdir(parents=True, exist_ok=True)
    _LIVE_LEDGER.write_text(json.dumps({"calls": rows}, indent=2), encoding="utf-8")


def levels(entry: float, side: str) -> Dict[str, float]:
    side = side.upper()
    sl_pts, t1_pts = BRACKETS["sl"], BRACKETS["target"]
    if side == "BUY":
        return {
            "entry": round(float(entry), 2),
            "stop_loss": round(float(entry) - sl_pts, 2),
            "target_1": round(float(entry) + t1_pts, 2),
            "t1_pts": t1_pts,
            "sl_pts": sl_pts,
        }
    return {
        "entry": round(float(entry), 2),
        "stop_loss": round(float(entry) + sl_pts, 2),
        "target_1": round(float(entry) - t1_pts, 2),
        "t1_pts": t1_pts,
        "sl_pts": sl_pts,
    }


def ensure_session_calls(
    day: Optional[str] = None,
    *,
    dual_call: Optional[dict] = None,
    hm: Optional[str] = None,
    entry: Optional[float] = None,
) -> Dict[str, Any]:
    """Append today's dual-track fire into BN FINAL ledger (cap3). Never blocks."""
    day = (day or date.today().isoformat())[:10]
    ledger = _ledger_load()
    day_rows = [r for r in ledger if str(r.get("day") or "")[:10] == day]
    added: List[dict] = []
    if isinstance(dual_call, dict):
        side = str(dual_call.get("decision") or "").upper()
        if side in ("BUY", "SELL"):
            use_hm = str(hm or dual_call.get("hm") or dual_call.get("time") or "")[:5]
            px = entry
            if px is None:
                try:
                    px = float(dual_call.get("entry") or dual_call.get("price") or 0) or None
                except (TypeError, ValueError):
                    px = None
            if use_hm and px:
                same = sum(1 for r in day_rows if str(r.get("decision") or "").upper() == side)
                exists = any(
                    str(r.get("hm") or "") == use_hm and str(r.get("decision") or "").upper() == side
                    for r in day_rows
                )
                if not exists and same < CAP:
                    row = {
                        "day": day,
                        "hm": use_hm,
                        "decision": side,
                        "side": side,
                        "p_t1": dual_call.get("p_t1"),
                        "track": dual_call.get("track") or "champion",
                        "live_fire": True,
                        **levels(float(px), side),
                    }
                    ledger.append(row)
                    day_rows.append(row)
                    added.append(row)
                    _ledger_save(ledger)
    return {
        "day": day,
        "n_day": len(day_rows),
        "n_added": len(added),
        "day_calls": stamp_live(day_rows),
        "added": stamp_live(added),
        "blocked": False,
        "desk": DESK_CHAMP,
        "accuracy_tag": ACCURACY_TAG,
        "live_engine": True,
    }


def book_registry() -> Dict[str, Any]:
    return {
        "symbol": SYMBOL,
        "desks": [DESK_PROVEN, DESK_CHAMP],
        "primary": DESK_CHAMP,
        "accuracy_tag": ACCURACY_TAG,
        "brackets": dict(BRACKETS),
        "expected": EXPECTED,
        "windows": {"1y": WINDOW_1Y, "3y": WINDOW_3Y, "5y": WINDOW_5Y},
        "report": str(_REPORT).replace("\\", "/"),
        "enabled": enabled(),
    }
