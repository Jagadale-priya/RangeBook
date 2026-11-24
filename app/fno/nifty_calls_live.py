"""NIFTY thrust helper for Calls.

Thrust lane (this module):
  - morning strong OR+5 · locked L5_u70_b80 · confident

FINAL books (wired in fill_from_channels / fno_p2f_live.annotate):
  - CHAMP_PLUS lists onto Calls when thrust is silent
  - P2F / P2G stamp accuracy tags (UI merge same day+side+hm)

Not on Calls: dual proven/champion.
Same-refresh multi-thrust → merge. Later thrust archives prior open.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

SOURCE_MORNING = "nifty_morning_strong_thrust_confident"
SOURCE_AFTERNOON = "nifty_afternoon_thrust_confident"


def is_nifty(symbol: Any) -> bool:
    return str(symbol or "").upper() in ("NIFTY", "NIFTY 50", "NIFTY50")


def dual_never_lists() -> bool:
    """NIFTY Calls are thrust-only — dual proven/champion never board."""
    return True


def _afternoon_enabled() -> bool:
    try:
        import fno_live_config

        return bool(fno_live_config.enable_nifty_afternoon_thrust())
    except Exception:
        return False


def extract_payloads(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Collect morning (and afternoon only if enabled) thrust payloads.

    Afternoon is OFF by default and must never block CHAMP/P2F/P2G.
    """
    out: List[Dict[str, Any]] = []
    seen = set()
    allow_aft = _afternoon_enabled()

    def _add(p: Any) -> None:
        if not isinstance(p, dict) or p.get("decision") not in ("BUY", "SELL"):
            return
        if p.get("entry") is None or p.get("stop_loss") is None or p.get("target_1") is None:
            return
        if p.get("afternoon_thrust") and not allow_aft:
            return
        if not p.get("morning_strong_thrust") and not p.get("afternoon_thrust") and not p.get("merged"):
            # only thrust lanes in this helper
            if "thrust" not in str(p.get("source") or ""):
                return
        if p.get("merged") and out:
            return
        key = (
            str(p.get("source") or ""),
            str(p.get("hm") or ""),
            str(p.get("decision") or ""),
            round(float(p["entry"]), 2),
        )
        if key in seen:
            return
        seen.add(key)
        out.append(dict(p))

    fa = result.get("fno_analysis") if isinstance(result.get("fno_analysis"), dict) else {}
    for blob in (
        result.get("nifty_list_payloads"),
        fa.get("nifty_list_payloads"),
    ):
        if isinstance(blob, list) and blob:
            for p in blob:
                if isinstance(p, dict) and not p.get("merged"):
                    _add(p)
            if out:
                return out

    for p in (
        result.get("nifty_morning_strong_thrust_payload"),
        fa.get("nifty_morning_strong_thrust_payload"),
    ):
        _add(p)
    if allow_aft:
        for p in (
            result.get("nifty_afternoon_thrust_payload"),
            fa.get("nifty_afternoon_thrust_payload"),
        ):
            _add(p)
    if out:
        return out

    dual = fa.get("dual_track_call") if isinstance(fa, dict) else None
    if not isinstance(dual, dict):
        dual = result.get("dual_track_call")
    if isinstance(dual, dict) and dual.get("morning_strong_thrust"):
        _add(dual)
    elif isinstance(dual, dict) and allow_aft and dual.get("afternoon_thrust"):
        _add(dual)

    return out


def merge_payloads(payloads: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge 2+ same-refresh thrust fires into one Calls payload."""
    rows = [p for p in payloads if isinstance(p, dict)]
    if not rows:
        return {}
    if len(rows) == 1:
        return dict(rows[0])

    # Prefer afternoon levels when both; keep earliest hm for taken_at hint.
    aft = next((p for p in rows if p.get("afternoon_thrust")), None)
    morn = next((p for p in rows if p.get("morning_strong_thrust")), None)
    primary = aft or morn or rows[-1]
    merged = dict(primary)
    sources = []
    labels = []
    hms = []
    tags: List[Any] = []
    for p in rows:
        src = str(p.get("source") or ("afternoon" if p.get("afternoon_thrust") else "morning"))
        if src not in sources:
            sources.append(src)
        lab = str(p.get("accuracy_label") or src)
        if lab not in labels:
            labels.append(lab)
        hm = str(p.get("hm") or "")
        if hm and hm not in hms:
            hms.append(hm)
        for t in p.get("accuracy_tags") or []:
            if t not in tags:
                tags.append(t)

    merged["merged"] = True
    merged["merged_sources"] = sources
    merged["merged_hms"] = hms
    merged["source"] = "+".join(sources) if sources else str(merged.get("source") or "nifty_merged_confident")
    merged["track"] = "confident"
    merged["dual_track"] = False
    merged["morning_strong_thrust"] = bool(morn)
    merged["afternoon_thrust"] = bool(aft)
    merged["accuracy_label"] = "Merged · " + " + ".join(labels)
    merged["accuracy_tags"] = tags or [
        {
            "code": "confident",
            "label": merged["accuracy_label"],
            "tone": "research",
            "priority": 70,
        }
    ]
    # Levels: afternoon preferred; else primary.
    for k in ("entry", "stop_loss", "target_1", "p_t1"):
        if aft and aft.get(k) is not None:
            merged[k] = aft[k]
    return merged


def stamp_merged_readings(readings: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    readings["dual_track"] = False
    readings["track"] = "confident"
    readings["source"] = str(payload.get("source") or "nifty_merged_confident")
    readings["accuracy_label"] = str(payload.get("accuracy_label") or "NIFTY confident")
    readings["accuracy_tags"] = list(payload.get("accuracy_tags") or [])
    readings["history_eligible"] = True
    readings["live_confluence"] = False
    readings["listable"] = True
    readings["priority"] = 70
    readings["proven_100"] = False
    if payload.get("merged"):
        readings["merged"] = True
        readings["merged_sources"] = list(payload.get("merged_sources") or [])
        readings["merged_hms"] = list(payload.get("merged_hms") or [])
    readings["morning_strong_thrust"] = bool(payload.get("morning_strong_thrust"))
    readings["afternoon_thrust"] = bool(payload.get("afternoon_thrust"))
    if payload.get("p_t1") is not None:
        readings["p_t1"] = payload.get("p_t1")
    return readings


def _hm_of(ticket_or_payload: Optional[dict]) -> str:
    if not isinstance(ticket_or_payload, dict):
        return ""
    hm = str(ticket_or_payload.get("hm") or "")
    if hm:
        return hm[:5]
    readings = ticket_or_payload.get("readings")
    if isinstance(readings, dict):
        src = str(readings.get("source") or "")
        # taken_at embeds hm sometimes; prefer explicit
        for key in ("merged_hms",):
            hms = readings.get(key)
            if isinstance(hms, list) and hms:
                return str(hms[0])[:5]
    taken = str(ticket_or_payload.get("taken_at") or "")
    if "T" in taken and len(taken) >= 16:
        return taken[11:16]
    return ""


def same_fire(open_ticket: Optional[dict], payload: Dict[str, Any]) -> bool:
    """True when open board ticket is the same thrust fire (merge in place)."""
    if not isinstance(open_ticket, dict) or not isinstance(payload, dict):
        return False
    side_a = str(open_ticket.get("decision") or "").upper()
    side_b = str(payload.get("decision") or "").upper()
    if side_a != side_b or side_a not in ("BUY", "SELL"):
        return False
    hm_a = _hm_of(open_ticket)
    hm_b = str(payload.get("hm") or "")[:5]
    if hm_a and hm_b and hm_a == hm_b:
        return True
    readings = open_ticket.get("readings") if isinstance(open_ticket.get("readings"), dict) else {}
    if payload.get("merged") and readings.get("merged"):
        return True
    # Same entry within 1pt + same confident family
    try:
        if abs(float(open_ticket.get("entry")) - float(payload.get("entry"))) <= 1.0:
            if readings.get("track") == "confident" or readings.get("afternoon_thrust") or readings.get(
                "morning_strong_thrust"
            ):
                return True
    except (TypeError, ValueError):
        pass
    return False


def fill_board(
    result: Dict[str, Any],
    *,
    symbol: str,
    session_ticket: Optional[dict] = None,
    bars: Any = None,
    live_quote: Any = None,
    db_path: Optional[str] = None,
    asof: Any = None,
) -> Optional[dict]:
    """List NIFTY research thrusts onto Calls — merge same-time, never skip."""
    import fno_session_rules as fsrules

    ticket = session_ticket if session_ticket is not None else result.get("session_ticket")
    payloads = extract_payloads(result)
    if not payloads:
        return ticket

    payload = merge_payloads(payloads) if len(payloads) > 1 else dict(payloads[0])
    if not payload:
        return ticket

    side = str(payload.get("decision") or "").upper()
    if side not in ("BUY", "SELL"):
        return ticket

    day = str(asof)[:10] if asof else None
    if not day:
        from datetime import datetime

        day = datetime.now().strftime("%Y-%m-%d")
    hm = str(payload.get("hm") or "")
    taken = f"{day}T{hm}:00+05:30" if hm else asof

    readings: Dict[str, Any] = {
        "dual_track": False,
        "track": "confident",
        "interval": "15minute" if payload.get("afternoon_thrust") else "5minute",
    }
    if payload.get("morning_strong_thrust") and not payload.get("afternoon_thrust"):
        import nifty_morning_strong_thrust as nmst

        nmst.stamp_readings(readings, payload)
    elif payload.get("afternoon_thrust") and not payload.get("morning_strong_thrust"):
        import nifty_afternoon_thrust as nat

        nat.stamp_readings(readings, payload)
    else:
        stamp_merged_readings(readings, payload)

    # Same-fire → merge readings onto open ticket (no skip, no duplicate).
    live = fsrules.open_ticket(ticket)
    if live and same_fire(live, payload):
        live_readings = dict(live.get("readings") or {})
        live_readings.update(readings)
        if payload.get("merged") or live_readings.get("merged"):
            stamp_merged_readings(live_readings, payload)
        live = dict(live)
        live["readings"] = live_readings
        live["entry"] = payload.get("entry", live.get("entry"))
        live["stop_loss"] = payload.get("stop_loss", live.get("stop_loss"))
        live["target_1"] = payload.get("target_1", live.get("target_1"))
        live["p_t1"] = payload.get("p_t1", live.get("p_t1"))
        # Rebuild session pack with updated open row.
        pack = dict(ticket or {})
        pack.update(
            {
                "decision": live.get("decision"),
                "entry": live.get("entry"),
                "stop_loss": live.get("stop_loss"),
                "target_1": live.get("target_1"),
                "p_t1": live.get("p_t1"),
                "readings": live_readings,
                "status": "open",
            }
        )
        result["session_ticket"] = pack
        result["nifty_call_merged"] = True
        if db_path:
            try:
                import session_calls

                session_calls.sync_session(
                    db_path,
                    stock="NIFTY",
                    product="fno",
                    session_ticket=pack,
                    extra={"source": str(readings.get("source") or "nifty_merged")},
                )
            except Exception:
                pass
        return pack

    # Different fire (or empty board): persist — rules archive prior open, never skip thrust.
    new_ticket = fsrules.persist_new_ticket(
        ticket,
        decision=side,
        stop_loss=payload.get("stop_loss"),
        target_1=payload.get("target_1"),
        taken_at=taken,
        session_date_value=day,
        entry=payload.get("entry"),
        p_t1=payload.get("p_t1"),
        p_meta=payload.get("p_t1"),
        regime="confident",
        readings=readings,
        symbol="NIFTY",
        bars=bars,
        live_quote=live_quote,
    )
    if db_path and new_ticket is not None:
        try:
            import session_calls

            session_calls.sync_session(
                db_path,
                stock="NIFTY",
                product="fno",
                session_ticket=new_ticket,
                extra={"source": str(readings.get("source") or "nifty_thrust")},
            )
        except Exception:
            pass
    result["session_ticket"] = new_ticket
    if payload.get("merged"):
        result["nifty_call_merged"] = True
    return new_ticket
