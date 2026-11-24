"""Prod stacked Calls · research stack_plus_crown_htf_cap2.

Priority: proven_100 > good_prod2 > champion > crown_5m(HTF-active)
Day cap: 2 · same side only.

Flag: ENABLE_STACKED_CALLS=1 (see fno_live_config.enable_stacked_calls).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

import path_setup
ROOT = path_setup.ROOT
DAILY_CSV = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_daily_5y_nse.csv"

PRIORITY = {
    "proven_100": 0,
    "good_prod2": 1,
    "pre_dual_single": 1,
    "champion": 2,
    "crown_5m": 3,
}

_DAILY_CACHE: Optional[pd.DataFrame] = None
_DAILY_MTIME: Optional[float] = None


def enabled() -> bool:
    try:
        import fno_live_config

        return bool(fno_live_config.enable_stacked_calls())
    except Exception:
        return False


def _load_daily() -> Optional[pd.DataFrame]:
    global _DAILY_CACHE, _DAILY_MTIME
    try:
        if not DAILY_CSV.exists():
            return None
        mtime = DAILY_CSV.stat().st_mtime
        if _DAILY_CACHE is not None and _DAILY_MTIME == mtime:
            return _DAILY_CACHE
        d = pd.read_csv(DAILY_CSV)
        d["Date"] = pd.to_datetime(d["Date"])
        _DAILY_CACHE = d.sort_values("Date").reset_index(drop=True)
        _DAILY_MTIME = mtime
        return _DAILY_CACHE
    except Exception:
        return None


def _as_day(asof: Any) -> str:
    if asof is None:
        return datetime.now().strftime("%Y-%m-%d")
    if hasattr(asof, "strftime"):
        return asof.strftime("%Y-%m-%d")
    s = str(asof)
    return s[:10]


def htf_active(
    asof: Any = None,
    *,
    lookback_sessions: int = 252,
) -> Dict[str, Any]:
    """Prior-day Volume >= P40 OR prior range% >= median (research definition).

    Uses NIFTY daily CSV as market HTF context for index desk.
    Fail-open (active=True) if daily file missing so crown is not silently killed.
    """
    day = _as_day(asof)
    daily = _load_daily()
    if daily is None or daily.empty:
        return {
            "active": True,
            "reason": "daily_missing_fail_open",
            "day": day,
        }
    prior = daily[daily["Date"] < pd.Timestamp(day)]
    if prior.empty:
        return {"active": True, "reason": "no_prior_fail_open", "day": day}
    window = prior.tail(max(20, int(lookback_sessions)))
    last = window.iloc[-1]
    vols = window["Volume"].astype(float)
    rng = ((window["High"] - window["Low"]) / window["Close"] * 100).astype(float)
    vcut = float(vols.quantile(0.4))
    rcut = float(rng.median())
    pv = float(last["Volume"])
    pr = float(
        (float(last["High"]) - float(last["Low"])) / float(last["Close"]) * 100
    )
    active = bool(pv >= vcut or pr >= rcut)
    return {
        "active": active,
        "reason": "htf_ok" if active else "htf_inactive",
        "day": day,
        "prior_date": str(last["Date"])[:10],
        "prior_volume": pv,
        "volume_p40": vcut,
        "prior_range_pct": round(pr, 4),
        "range_median": round(rcut, 4),
    }


def _ticket_side(row: Dict[str, Any]) -> Optional[str]:
    d = str(row.get("decision") or "").upper()
    if "BUY" in d:
        return "BUY"
    if "SELL" in d:
        return "SELL"
    return None


def model_day_stats(session_ticket: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Listed model tickets today: count + locked side (same-side rule)."""
    import fno_session_rules as fsrules

    if not session_ticket:
        return {"count": 0, "side": None, "open": False}
    side = None
    count = 0
    open_row = fsrules.open_ticket(session_ticket)
    if open_row and not fsrules.is_live_confluence_ticket(session_ticket):
        count += 1
        side = _ticket_side(open_row) or side
    for h in session_ticket.get("history") or []:
        if not isinstance(h, dict):
            continue
        if fsrules._history_row_is_live_clip(h):
            continue
        st = str(h.get("status") or "")
        if st and st not in getattr(fsrules, "CLOSED_STATUSES", set()) and st != "open":
            # count closed + any historic listed
            pass
        if st in getattr(
            fsrules,
            "CLOSED_STATUSES",
            {"closed", "stopped", "target", "cancelled", "early_drop", "superseded_by_model"},
        ) or st == "open":
            count += 1
            side = _ticket_side(h) or side
    # Prefer authoritative closed count + open for cap
    closed_n = int(fsrules.closed_ticket_count(session_ticket) or 0)
    open_n = 1 if (open_row and not fsrules.is_live_confluence_ticket(session_ticket)) else 0
    count = closed_n + open_n
    if open_row and not fsrules.is_live_confluence_ticket(session_ticket):
        side = _ticket_side(open_row) or side
    elif not side:
        for h in session_ticket.get("history") or []:
            if isinstance(h, dict) and not fsrules._history_row_is_live_clip(h):
                side = _ticket_side(h) or side
                if side:
                    break
    return {"count": count, "side": side, "open": bool(open_n)}


def crown_day_count(symbol: str, asof: Any = None) -> int:
    try:
        import crown_5m_store as store

        return int(store.count_today(str(symbol).upper(), _as_day(asof)) or 0)
    except Exception:
        return 0


def shared_day_count(symbol: str, session_ticket: Optional[Dict[str, Any]], asof: Any = None) -> int:
    return int(model_day_stats(session_ticket)["count"]) + int(crown_day_count(symbol, asof))


def allow_list(
    *,
    symbol: str,
    decision: str,
    session_ticket: Optional[Dict[str, Any]],
    asof: Any = None,
    track: str,
    include_crown_in_cap: bool = True,
) -> Tuple[bool, str]:
    """Day cap 2 + same-side gate for stacked mode (+ optional NSE mid)."""
    side = str(decision or "").upper()
    if side not in ("BUY", "SELL"):
        return False, "not_trade"
    # NIFTY only — NSE daily tape is index-specific research
    if str(symbol or "").upper() in ("NIFTY", "NIFTY 50", "NIFTY50"):
        try:
            import fno_nse_mid_gate as nse_gate

            if nse_gate.enabled():
                g = nse_gate.passes(asof)
                if not g.get("allow"):
                    return False, str(g.get("reason") or "nse_mid_fail")
        except Exception:
            pass
    stats = model_day_stats(session_ticket)
    used = int(stats["count"])
    if include_crown_in_cap and track == "crown_5m":
        used = shared_day_count(symbol, session_ticket, asof)
    elif include_crown_in_cap:
        # model list also shares cap with crown already taken
        used = shared_day_count(symbol, session_ticket, asof)
    # If replacing an open ticket, slot is reusable — cap checked in persist too
    import fno_session_rules as fsrules

    if fsrules.open_ticket(session_ticket) and not fsrules.is_live_confluence_ticket(
        session_ticket
    ):
        # replacement path — allow if same side or empty side rule
        locked = stats.get("side")
        if locked and locked != side:
            return False, "opposite_side"
        return True, "replace_open"
    if used >= 2:
        return False, "day_cap"
    locked = stats.get("side")
    if track == "crown_5m":
        # also lock side from crown rows
        try:
            import crown_5m_store as store

            rows = store.list_today(str(symbol).upper(), _as_day(asof))
            for r in rows or []:
                cs = _ticket_side(r if isinstance(r, dict) else {})
                if cs:
                    locked = locked or cs
                    break
        except Exception:
            pass
    if locked and locked != side:
        return False, "opposite_side"
    return True, "ok"


def choose_list_source(
    *,
    dual_call: Optional[Dict[str, Any]],
    good_decision: str,
    session_ticket: Optional[Dict[str, Any]],
    symbol: str,
    asof: Any = None,
) -> Dict[str, Any]:
    """Pick proven > good > champion among currently firing channels."""
    cands: List[Dict[str, Any]] = []
    if isinstance(dual_call, dict) and dual_call.get("decision") in ("BUY", "SELL"):
        tr = str(dual_call.get("track") or "champion")
        if tr in ("proven_100", "champion"):
            ok, why = allow_list(
                symbol=symbol,
                decision=str(dual_call["decision"]),
                session_ticket=session_ticket,
                asof=asof,
                track=tr,
            )
            if ok:
                cands.append(
                    {
                        "track": tr,
                        "priority": PRIORITY[tr],
                        "decision": str(dual_call["decision"]),
                        "call_payload": dual_call,
                        "why": why,
                    }
                )
    gd = str(good_decision or "").upper()
    if gd in ("BUY", "SELL"):
        ok, why = allow_list(
            symbol=symbol,
            decision=gd,
            session_ticket=session_ticket,
            asof=asof,
            track="good_prod2",
        )
        if ok:
            cands.append(
                {
                    "track": "good_prod2",
                    "priority": PRIORITY["good_prod2"],
                    "decision": gd,
                    "call_payload": None,
                    "why": why,
                }
            )
    cands.sort(key=lambda c: (c["priority"],))
    htf = htf_active(asof)
    if not cands:
        return {
            "track": None,
            "decision": None,
            "call_payload": None,
            "use_dual_payload": False,
            "use_good": False,
            "htf": htf,
            "candidates": [],
            "reason": "no_candidate",
        }
    best = cands[0]
    nse = None
    try:
        import fno_nse_mid_gate as nse_gate

        if nse_gate.enabled() and str(symbol or "").upper() in (
            "NIFTY",
            "NIFTY 50",
            "NIFTY50",
        ):
            nse = nse_gate.passes(asof)
    except Exception:
        nse = None
    return {
        "track": best["track"],
        "decision": best["decision"],
        "call_payload": best.get("call_payload"),
        "use_dual_payload": best["track"] in ("proven_100", "champion"),
        "use_good": best["track"] == "good_prod2",
        "htf": htf,
        "nse_mid": nse,
        "candidates": [
            {"track": c["track"], "decision": c["decision"], "priority": c["priority"]}
            for c in cands
        ],
        "reason": best.get("why") or "picked",
    }


def crown_may_persist(
    symbol: str,
    decision: str,
    *,
    session_ticket: Optional[Dict[str, Any]] = None,
    asof: Any = None,
) -> Dict[str, Any]:
    """Gate crown listing under stacked mode (HTF-active + shared cap + same side)."""
    if not enabled():
        return {"allow": True, "reason": "stacked_off", "htf": None}
    htf = htf_active(asof)
    if not htf.get("active"):
        return {"allow": False, "reason": "htf_inactive", "htf": htf}
    ok, why = allow_list(
        symbol=symbol,
        decision=decision,
        session_ticket=session_ticket,
        asof=asof,
        track="crown_5m",
        include_crown_in_cap=True,
    )
    return {"allow": ok, "reason": why, "htf": htf}
