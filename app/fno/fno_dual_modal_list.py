"""List tested dual-modal channels onto the F&O Calls board.

Sources (ExtraTrees single stays off):
  - 15m dual proven/champion — annotate only when SUPPRESS_DUAL_LIST=1
  - NIFTY morning/afternoon confident thrust — preferred over CHAMP when ready;
    may replace an open suppressed dual-family ticket on Calls
  - 10m dual / CHAMP_PLUS — promote live_fire adds when board empty
  - 5m crown — promote new crown signal when no open call
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def _open(ticket: Optional[dict]) -> bool:
    try:
        import fno_session_rules as fsrules

        return bool(fsrules.open_ticket(ticket))
    except Exception:
        return False


# 15m dual proven/champion family — suppressed from Calls when SUPPRESS_DUAL_LIST.
# 10m CHAMP (dual10m/champ_plus) still fills empty boards; afternoon thrust may
# replace those open tickets when it fires (see fill_from_channels / persist).
_SUPPRESSED_DUAL_TRACKS = frozenset(
    {
        "proven_100",
        "champion",
        "baseline",
        "proven_research",
        "dual5_research",
    }
)
_DUAL_FAMILY_TRACKS = frozenset(
    {
        "proven_100",
        "champion",
        "baseline",
        "dual10m",
        "champ_plus",
        "p2g_10m",
        "dual5_research",
        "proven_research",
    }
)


def _ticket_track(ticket: Optional[dict]) -> str:
    if not isinstance(ticket, dict):
        return ""
    readings = ticket.get("readings") if isinstance(ticket.get("readings"), dict) else {}
    return str(readings.get("track") or readings.get("source") or ticket.get("source") or "")


def _is_dual_family_ticket(ticket: Optional[dict]) -> bool:
    if not isinstance(ticket, dict):
        return False
    readings = ticket.get("readings") if isinstance(ticket.get("readings"), dict) else {}
    if readings.get("afternoon_thrust") or readings.get("morning_strong_thrust"):
        return False
    if readings.get("track") == "confident" or "thrust_confident" in str(
        readings.get("source") or ""
    ):
        return False
    if readings.get("dual_track"):
        return True
    return _ticket_track(ticket) in _DUAL_FAMILY_TRACKS


def _suppress_dual_list_for(symbol: str) -> bool:
    try:
        import fno_live_config

        return bool(fno_live_config.suppress_dual_list_for(symbol))
    except Exception:
        return True


def _readings(
    *,
    track: str,
    source: str,
    p_t1: Any,
    accuracy_label: str,
    accuracy_tags: Optional[List[Any]] = None,
    interval: str = "",
) -> Dict[str, Any]:
    return {
        "dual_track": True,
        "track": track,
        "source": source,
        "p_t1": p_t1,
        "accuracy_label": accuracy_label,
        "accuracy_tags": list(accuracy_tags or []),
        "history_eligible": True,
        "interval": interval,
        "live_confluence": False,
        "priority": 100 if track == "proven_100" else (80 if track in ("champion", "dual10m", "champ_plus") else 70),
    }


def _persist(
    session_ticket: Optional[dict],
    *,
    symbol: str,
    decision: str,
    entry: Any,
    stop_loss: Any,
    target_1: Any,
    p_t1: Any,
    taken_at: Any,
    session_date: Any,
    readings: dict,
    bars: Any = None,
    live_quote: Any = None,
    db_path: Optional[str] = None,
    extra_source: str = "dual_modal",
) -> Optional[dict]:
    try:
        import fno_session_rules as fsrules
        import session_calls
    except Exception:
        return session_ticket
    side = str(decision or "").upper()
    if side not in ("BUY", "SELL"):
        return session_ticket
    try:
        ticket = fsrules.persist_new_ticket(
            session_ticket,
            decision=side,
            stop_loss=stop_loss,
            target_1=target_1,
            taken_at=taken_at,
            session_date_value=session_date,
            entry=entry,
            p_t1=p_t1,
            p_meta=p_t1,
            regime=readings.get("track"),
            readings=readings,
            symbol=symbol,
            bars=bars,
            live_quote=live_quote,
        )
    except Exception:
        return session_ticket
    if db_path and ticket is not None:
        try:
            session_calls.sync_session(
                db_path,
                stock=str(symbol).upper(),
                product="fno",
                session_ticket=ticket,
                extra={"source": extra_source},
            )
        except Exception:
            pass
    return ticket


def _from_champ(
    result: Dict[str, Any],
    session_ticket: Optional[dict],
    *,
    symbol: str,
    bars: Any,
    live_quote: Any,
    db_path: Optional[str],
    asof: Any,
) -> Optional[dict]:
    meta = (result.get("champ_plus_live") or (result.get("fno_analysis") or {}).get("champ_plus_live") or {})
    if not isinstance(meta, dict):
        return session_ticket
    # Only newly added live fires — never re-list the whole day ledger.
    added = [r for r in (meta.get("added") or []) if isinstance(r, dict)]
    if not added:
        return session_ticket
    day = str(asof)[:10] if asof else datetime.now().strftime("%Y-%m-%d")
    for row in added:
        side = str(row.get("decision") or row.get("side") or "").upper()
        if side not in ("BUY", "SELL"):
            continue
        entry, sl, t1 = row.get("entry"), row.get("stop_loss"), row.get("target_1")
        if entry is None or sl is None or t1 is None:
            continue
        track = str(row.get("track") or "dual10m")
        if track not in (
            "dual10m",
            "champion",
            "proven_100",
            "proven_research",
            "dual5_research",
            "confident",
            "good_prod2",
            "crown_research",
        ):
            track = "dual10m"
        # SUPPRESS_DUAL_LIST: never promote 15m proven/champion onto Calls.
        # Thrust / crown_research / good_prod2 / 10m CHAMP still eligible.
        if (
            _suppress_dual_list_for(symbol)
            and track in _SUPPRESSED_DUAL_TRACKS
            and not (row.get("afternoon_thrust") or row.get("morning_strong_thrust") or track == "confident")
        ):
            continue
        hm = str(row.get("hm") or "")
        taken = f"{row.get('day') or day}T{hm}:00+05:30" if hm else (row.get("fired_at") or asof or datetime.now().isoformat())
        label = str(
            row.get("accuracy_tag")
            or row.get("accuracy_label")
            or (
                "Priority · High accuracy · afternoon thrust (~92%)"
                if track == "confident"
                else "CHAMP_PLUS · 10m dual"
            )
        )
        readings = _readings(
            track=track if track != "proven_research" else "proven_100",
            source=(
                "nifty_afternoon_thrust_confident"
                if track == "confident"
                else ("dual10m" if "10" in track or track == "dual10m" else track)
            ),
            p_t1=row.get("p_t1"),
            accuracy_label=label,
            accuracy_tags=row.get("tags") or [label],
            interval="15minute" if track == "confident" else "10minute",
        )
        if row.get("morning_strong_thrust"):
            readings["morning_strong_thrust"] = True
            readings["dual_track"] = False
            readings["track"] = "confident"
        elif row.get("afternoon_thrust"):
            readings["afternoon_thrust"] = True
            readings["dual_track"] = False
        # Same (day, side, hm) as open → merge tags (P2F/P2G/CHAMP) into one call.
        live = None
        try:
            import fno_session_rules as fsrules

            live = fsrules.open_ticket(session_ticket)
        except Exception:
            live = None
        if (
            live
            and str(live.get("decision") or "").upper() == side
            and hm
            and str(live.get("taken_at") or "")[11:16] == hm[:5]
        ):
            live_r = dict(live.get("readings") or {})
            tags = list(live_r.get("accuracy_tags") or [])
            for t in readings.get("accuracy_tags") or []:
                if t not in tags:
                    tags.append(t)
            for t in (row.get("tags") or []):
                if t not in tags:
                    tags.append(t)
            for t in (label, "CHAMP_PLUS_T30SL30_CAP6", "FINAL_NIFTY_3BOOKS"):
                if t and t not in tags:
                    tags.append(t)
            live_r["accuracy_tags"] = tags
            live_r["tags"] = tags
            live_r["champ_plus"] = True
            if readings.get("accuracy_label"):
                live_r["accuracy_label"] = (
                    f"{live_r.get('accuracy_label') or ''} · {readings.get('accuracy_label')}"
                ).strip(" ·")
            pack = dict(session_ticket or {})
            pack["readings"] = live_r
            session_ticket = pack
            if db_path:
                try:
                    import session_calls

                    session_calls.sync_session(
                        db_path,
                        stock=str(symbol).upper(),
                        product="fno",
                        session_ticket=pack,
                        extra={"source": "champ_tag_merge"},
                    )
                except Exception:
                    pass
            continue
        ticket = _persist(
            session_ticket,
            symbol=symbol,
            decision=side,
            entry=entry,
            stop_loss=sl,
            target_1=t1,
            p_t1=row.get("p_t1"),
            taken_at=taken,
            session_date=row.get("day") or day,
            readings=readings,
            bars=bars,
            live_quote=live_quote,
            db_path=db_path,
            extra_source="dual10m_champ",
        )
        session_ticket = ticket if ticket is not None else session_ticket
        # NIFTY Cap6: keep scanning remaining adds — do not stop after first open.
        if str(symbol or "").upper() in ("NIFTY", "NIFTY 50", "NIFTY50"):
            continue
        if ticket is not None and _open(ticket):
            return ticket
    return session_ticket


def _from_crown(
    result: Dict[str, Any],
    session_ticket: Optional[dict],
    *,
    symbol: str,
    bars: Any,
    live_quote: Any,
    db_path: Optional[str],
    asof: Any,
) -> Optional[dict]:
    block = result.get("crown_5m") or {}
    if not isinstance(block, dict) or not block.get("enabled"):
        return session_ticket
    saved = block.get("saved") or {}
    sig = block.get("signal")
    if not isinstance(sig, dict):
        return session_ticket
    # Only newly created crown signals list onto Calls
    if not (saved.get("ok") and saved.get("created")):
        return session_ticket
    side = str(sig.get("decision") or "").upper()
    if side not in ("BUY", "SELL"):
        return session_ticket
    readings = _readings(
        track="crown_5m",
        source="fno_5m_crown",
        p_t1=sig.get("p_t1"),
        accuracy_label=str(sig.get("accuracy_label") or "5m crown"),
        accuracy_tags=sig.get("accuracy_tags") or [],
        interval="5minute",
    )
    return _persist(
        session_ticket,
        symbol=symbol,
        decision=side,
        entry=sig.get("entry"),
        stop_loss=sig.get("stop_loss"),
        target_1=sig.get("target_1"),
        p_t1=sig.get("p_t1"),
        taken_at=sig.get("taken_at") or sig.get("bar_time") or asof,
        session_date=sig.get("session_date") or (str(asof)[:10] if asof else None),
        readings=readings,
        bars=bars,
        live_quote=live_quote,
        db_path=db_path,
        extra_source="dual5m_crown",
    )


def _from_afternoon_thrust(
    result: Dict[str, Any],
    session_ticket: Optional[dict],
    *,
    symbol: str,
    bars: Any,
    live_quote: Any,
    db_path: Optional[str],
    asof: Any,
) -> Optional[dict]:
    """List confident afternoon thrust when dual path held but payload is ready."""
    fa = result.get("fno_analysis") or {}
    dual = fa.get("dual_track_call") if isinstance(fa, dict) else None
    if not isinstance(dual, dict) or not dual.get("afternoon_thrust"):
        dual = result.get("dual_track_call")
    if not isinstance(dual, dict) or not dual.get("afternoon_thrust"):
        return session_ticket
    side = str(dual.get("decision") or "").upper()
    if side not in ("BUY", "SELL"):
        return session_ticket
    entry, sl, t1 = dual.get("entry"), dual.get("stop_loss"), dual.get("target_1")
    if entry is None or sl is None or t1 is None:
        return session_ticket
    readings = _readings(
        track="confident",
        source=str(dual.get("source") or "nifty_afternoon_thrust_confident"),
        p_t1=dual.get("p_t1"),
        accuracy_label=str(
            dual.get("accuracy_label")
            or "Priority · High accuracy · afternoon thrust (~92%)"
        ),
        accuracy_tags=dual.get("accuracy_tags") or [],
        interval="15minute",
    )
    readings["dual_track"] = False
    readings["afternoon_thrust"] = True
    readings["listable"] = True
    return _persist(
        session_ticket,
        symbol=symbol,
        decision=side,
        entry=entry,
        stop_loss=sl,
        target_1=t1,
        p_t1=dual.get("p_t1"),
        taken_at=dual.get("hm") and f"{(str(asof)[:10] if asof else datetime.now().strftime('%Y-%m-%d'))}T{dual.get('hm')}:00+05:30" or asof,
        session_date=str(asof)[:10] if asof else datetime.now().strftime("%Y-%m-%d"),
        readings=readings,
        bars=bars,
        live_quote=live_quote,
        db_path=db_path,
        extra_source="nifty_afternoon_thrust_confident",
    )


def _from_morning_strong_thrust(
    result: Dict[str, Any],
    session_ticket: Optional[dict],
    *,
    symbol: str,
    bars: Any,
    live_quote: Any,
    db_path: Optional[str],
    asof: Any,
) -> Optional[dict]:
    """List confident morning strong OR+5 fill when payload is ready."""
    fa = result.get("fno_analysis") or {}
    dual = fa.get("dual_track_call") if isinstance(fa, dict) else None
    if not isinstance(dual, dict) or not dual.get("morning_strong_thrust"):
        dual = result.get("dual_track_call")
    if not isinstance(dual, dict) or not dual.get("morning_strong_thrust"):
        return session_ticket
    side = str(dual.get("decision") or "").upper()
    if side not in ("BUY", "SELL"):
        return session_ticket
    entry, sl, t1 = dual.get("entry"), dual.get("stop_loss"), dual.get("target_1")
    if entry is None or sl is None or t1 is None:
        return session_ticket
    readings = _readings(
        track="confident",
        source=str(dual.get("source") or "nifty_morning_strong_thrust_confident"),
        p_t1=dual.get("p_t1"),
        accuracy_label=str(
            dual.get("accuracy_label")
            or "Priority · High accuracy · morning strong OR+5 (~80–90%)"
        ),
        accuracy_tags=dual.get("accuracy_tags") or [],
        interval="5minute",
    )
    readings["dual_track"] = False
    readings["morning_strong_thrust"] = True
    readings["listable"] = True
    return _persist(
        session_ticket,
        symbol=symbol,
        decision=side,
        entry=entry,
        stop_loss=sl,
        target_1=t1,
        p_t1=dual.get("p_t1"),
        taken_at=dual.get("hm")
        and f"{(str(asof)[:10] if asof else datetime.now().strftime('%Y-%m-%d'))}T{dual.get('hm')}:00+05:30"
        or asof,
        session_date=str(asof)[:10] if asof else datetime.now().strftime("%Y-%m-%d"),
        readings=readings,
        bars=bars,
        live_quote=live_quote,
        db_path=db_path,
        extra_source="nifty_morning_strong_thrust_confident",
    )


def fill_from_channels(
    result: Dict[str, Any],
    *,
    symbol: str,
    session_ticket: Optional[dict] = None,
    bars: Any = None,
    live_quote: Any = None,
    db_path: Optional[str] = None,
    asof: Any = None,
) -> Optional[dict]:
    """Route Calls fills.

    NIFTY (accuracy desk — no silent blockers):
      1. Morning strong L5_u70_b80 when it fires
      2. CHAMP_PLUS always considered (merge same hm · list distinct)
      P2F/P2G stamp tags via annotate. Afternoon does not block.
      Dual proven/champion still do not list.
    BN/Sensex: CHAMP / crown when board empty.
    """
    ticket = session_ticket if session_ticket is not None else result.get("session_ticket")
    key = str(symbol or "").upper()
    if key in ("NIFTY", "NIFTY 50", "NIFTY50"):
        try:
            import nifty_calls_live

            ticket = nifty_calls_live.fill_board(
                result,
                symbol=key,
                session_ticket=ticket,
                bars=bars,
                live_quote=live_quote,
                db_path=db_path,
                asof=asof,
            )
            result["session_ticket"] = ticket
        except Exception as exc:
            result["nifty_calls_live_error"] = str(exc)
        # FINAL CHAMP_PLUS + P2F/P2G tags — never blocked by morning/afternoon.
        ticket = _from_champ(
            result, ticket, symbol=key, bars=bars, live_quote=live_quote, db_path=db_path, asof=asof
        )
        result["session_ticket"] = ticket
        return ticket
    if _open(ticket):
        return ticket
    ticket = _from_champ(
        result, ticket, symbol=key, bars=bars, live_quote=live_quote, db_path=db_path, asof=asof
    )
    if _open(ticket):
        result["session_ticket"] = ticket
        return ticket
    ticket = _from_crown(
        result, ticket, symbol=key, bars=bars, live_quote=live_quote, db_path=db_path, asof=asof
    )
    result["session_ticket"] = ticket
    return ticket
