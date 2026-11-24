"""Desk tape alignment & confluence — indication only (no call / entry changes)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _side_from_decision(decision: str) -> Optional[bool]:
    d = (decision or "").upper()
    if "BUY" in d:
        return True
    if "SELL" in d:
        return False
    return None


def _reference_decision(
    decision: str,
    *,
    active_call: Optional[Dict[str, Any]] = None,
    core_decision: Optional[str] = None,
    fno_model: Optional[Dict[str, Any]] = None,
) -> str:
    if active_call and active_call.get("decision"):
        return str(active_call["decision"])
    if _side_from_decision(decision) is not None:
        return decision
    fm = fno_model or {}
    fd = str(fm.get("decision") or "")
    if _side_from_decision(fd) is not None:
        return fd
    return str(core_decision or decision or "HOLD")


def build_tape_indication(
    *,
    decision: str,
    live_context: Optional[Dict[str, Any]] = None,
    alerts: Optional[List[Dict[str, Any]]] = None,
    fno_model: Optional[Dict[str, Any]] = None,
    active_call: Optional[Dict[str, Any]] = None,
    core_decision: Optional[str] = None,
    confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """Confluence of live tape vs reference direction (open call or desk bias)."""
    ctx = live_context or {}
    session = ctx.get("session") or {}
    micro = ctx.get("microstructure") or {}
    live_p = float(ctx.get("live_probability_up") or ctx.get("live_p") or 0.5)
    ref = _reference_decision(
        decision,
        active_call=active_call,
        core_decision=core_decision,
        fno_model=fno_model,
    )
    side = _side_from_decision(ref)
    alert_list = list(alerts or [])
    critical = sum(1 for a in alert_list if a.get("severity") == "critical")
    warning = sum(1 for a in alert_list if a.get("severity") == "warning")

    checks: List[Dict[str, Any]] = []

    if side is not None:
        # Tighter than a coin-flip so soft p(up)~50% cannot pad "Aligned" on a dump.
        live_ok = (side and live_p >= 0.52) or ((not side) and live_p <= 0.48)
        checks.append({
            "id": "live_p",
            "label": "Live probability",
            "agree": live_ok,
            "note": f"p(up) {live_p * 100:.1f}% vs {ref}",
        })
    else:
        checks.append({
            "id": "live_p",
            "label": "Live probability",
            "agree": 0.44 <= live_p <= 0.56,
            "note": f"No open direction — tape edge {live_p * 100:.1f}%",
        })

    if session.get("available"):
        chg = float(session.get("change_from_open_pct") or 0)
        if side is True:
            sess_ok = chg >= -0.15
        elif side is False:
            sess_ok = chg <= 0.15
        else:
            sess_ok = abs(chg) < 0.35
        checks.append({
            "id": "session",
            "label": "Session vs open",
            "agree": sess_ok,
            "note": f"{chg:+.2f}% from open",
        })
    else:
        checks.append({
            "id": "session",
            "label": "Session vs open",
            "agree": False,
            "note": "No live session read",
        })

    if micro.get("available"):
        mb = str(micro.get("micro_bias") or "NEUTRAL").upper()
        if side is True:
            micro_ok = mb != "BEARISH"
        elif side is False:
            micro_ok = mb != "BULLISH"
        else:
            micro_ok = mb == "NEUTRAL" or mb in ("BULLISH", "BEARISH")
        checks.append({
            "id": "micro",
            "label": "5m / 15m micro",
            "agree": micro_ok,
            "note": f"{mb} · score {micro.get('micro_score', '—')}",
        })
        fm_conflict = bool(micro.get("five_min_conflict"))
        checks.append({
            "id": "five_fifteen",
            "label": "5m vs 15m",
            "agree": not fm_conflict,
            "note": micro.get("five_min_note") or ("Aligned" if not fm_conflict else "5m conflicts 15m"),
        })
        # Recent 15m candle stack vs reference — stops "Aligned 7/7" while price dumps.
        cs15 = micro.get("micro_candlestick_15m") or micro.get("micro_candlestick") or {}
        cs_bias = str(cs15.get("bias") or "NEUTRAL").upper()
        cs_score = float(cs15.get("score_delta") or 0)
        if side is True:
            recent_ok = not (cs_bias == "BEARISH" and cs_score <= -6)
        elif side is False:
            recent_ok = not (cs_bias == "BULLISH" and cs_score >= 6)
        else:
            recent_ok = abs(cs_score) < 8
        checks.append({
            "id": "recent_15m",
            "label": "Recent 15m stack",
            "agree": recent_ok,
            "note": f"{cs_bias} · score {cs_score:+.0f}" if cs15 else "No 15m candle read",
        })
    else:
        checks.append({
            "id": "micro",
            "label": "5m / 15m micro",
            "agree": False,
            "note": "Micro stack unavailable",
        })
        checks.append({
            "id": "five_fifteen",
            "label": "5m vs 15m",
            "agree": True,
            "note": "Not evaluated",
        })
        checks.append({
            "id": "recent_15m",
            "label": "Recent 15m stack",
            "agree": False,
            "note": "Micro stack unavailable",
        })

    conflict = bool(ctx.get("live_core_conflict"))
    checks.append({
        "id": "core_live",
        "label": "Swing vs live",
        "agree": not conflict,
        "note": "Live disagrees with core" if conflict else "No swing–live fight",
    })

    fm = fno_model or {}
    p_t1 = fm.get("p_t1")
    buy_p = fm.get("buy_p")
    if side is not None and p_t1 is not None and buy_p is not None:
        pt1_ok = float(p_t1) + 1e-9 >= float(buy_p)
        checks.append({
            "id": "p_t1",
            "label": "Target odds (model)",
            "agree": pt1_ok,
            "note": f"p(T1) {(float(p_t1) * 100):.0f}% · need {(float(buy_p) * 100):.0f}%",
        })
    else:
        checks.append({
            "id": "p_t1",
            "label": "Target odds (model)",
            "agree": critical == 0,
            "note": "Model threshold N/A" if p_t1 is None else "No directional reference",
        })

    alerts_ok = critical == 0 and warning <= 1
    checks.append({
        "id": "alerts",
        "label": "Tape warnings",
        "agree": alerts_ok,
        "note": f"{critical} critical · {warning} warning",
    })

    total = len(checks)
    agree = sum(1 for c in checks if c.get("agree"))
    ratio = agree / total if total else 0.0

    recent = next((c for c in checks if c.get("id") == "recent_15m"), None)
    recent_fights = bool(side is not None and recent is not None and not recent.get("agree"))

    if critical >= 1 or (side is not None and warning >= 2 and agree <= 3):
        level = "against"
        headline = "Tape against your reference — review size or wait."
    elif recent_fights:
        level = "caution"
        headline = "Recent 15m stack fights the desk reference — not aligned."
    elif warning >= 2 or agree <= 3:
        level = "caution"
        headline = "Mixed tape — not high confluence."
    elif agree >= 6 and critical == 0:
        level = "supportive"
        headline = "Tape aligned with desk reference — indication only, not a call."
    else:
        level = "neutral"
        headline = "Neutral confluence — no strong push either way."

    if active_call and level == "against":
        headline = f"Open {ref} call — tape turning against you (indication only)."

    return {
        "level": level,
        "reference_decision": ref,
        "agree_count": agree,
        "total_checks": total,
        "agree_ratio": round(ratio, 3),
        "checks": checks,
        "headline": headline,
        "critical_alerts": critical,
        "warning_alerts": warning,
        "indication_only": True,
        "disclaimer": (
            "Tape Aligned is confluence vs the desk reference (open call or bias), "
            "not a prediction that price will continue that way. "
            "Not a profit guarantee or auto-trade signal."
        ),
    }
