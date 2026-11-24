"""Live path-health indications for an open F&O call (12y-proven).

One family: Kite index path vs entry / stop / target —
  favor (MFE), against (MAE), signed_close, peak.

States (research: prod2_proven_indications + sl_each_deep_save_report):
  CONFIDENT         peak≥70%×reward AND signed≥50%×reward AND against<40%×risk
  WARN_GIVEBACK     had ≥50%×reward THEN signed≤−20 AND against≥40%×risk
  WARN_NEG_NEVER    bars≥2 AND peak<1 AND against≥35%×risk
  WARN_NEG_DEEP     bars≥4 AND peak<30%×reward AND against≥85%×risk
                    AND signed≤−25  (per-SL deep hunt; 94% loss precision OOS)
  WARN_NEG_WEAK     bars≥2 AND never hit 50% AND peak<50%×reward
                    AND against≥70%×risk AND signed≤−15
  BOOK_PULLBACK     had ≥50%×reward, still green, but gave back ≥50% of peak
                    (alert only — auto-book cuts too many T1s on 12y paths)

Issuance stays prod2. Live settle auto-closes GIVEBACK + NEVER + DEEP.
WARN_NEG_WEAK, BOOK_PULLBACK, and CONFIDENT stay alert-only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Locked to full-12y proven package (do not loosen without re-validation).
CONF_PEAK_FRAC = 0.70
CONF_SIGNED_FRAC = 0.50
CONF_AGAINST_MAX = 0.40

GB_HIT_FRAC = 0.50
GB_SIGNED_MAX = -20.0
GB_AGAINST_MIN = 0.40

# Still-green pullback after a 50% run — hint only (book50_lock_hunt).
BOOK_PEAK_KEEP_FRAC = 0.50  # signed < 50% of peak → gave half the run back

NEVER_PEAK_MAX = 1.0
NEVER_AGAINST_MIN = 0.35
NEVER_MIN_BARS = 2

# Per-SL deep save (sl_each_deep_save_report): high precision, tiny T1 damage.
DEEP_PEAK_FRAC_MAX = 0.30
DEEP_AGAINST_MIN = 0.85
DEEP_SIGNED_MAX = -25.0
DEEP_MIN_BARS = 4

WEAK_PEAK_FRAC_MAX = 0.50
WEAK_AGAINST_MIN = 0.70
WEAK_SIGNED_MAX = -15.0
WEAK_MIN_BARS = 2


def _f(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bullish(decision: Any) -> Optional[bool]:
    d = str(decision or "").upper()
    if "BUY" in d:
        return True
    if "SELL" in d:
        return False
    return None


def path_metrics(
    *,
    decision: Any,
    entry: float,
    stop_loss: float,
    target_1: float,
    last: float,
    path_high: float,
    path_low: float,
    bars_since_entry: int = 0,
) -> Optional[Dict[str, float]]:
    """Compute favor / against / signed / peak from live path extremes."""
    side = _bullish(decision)
    if side is None:
        return None
    entry = float(entry)
    stop = float(stop_loss)
    target = float(target_1)
    last = float(last)
    hi = float(path_high)
    lo = float(path_low)
    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk <= 0 or reward <= 0:
        return None
    if side:
        favor = max(0.0, hi - entry)
        against = max(0.0, entry - lo)
        signed = last - entry
    else:
        favor = max(0.0, entry - lo)
        against = max(0.0, hi - entry)
        signed = entry - last
    peak = favor  # extremes already max MFE on path
    return {
        "favor": round(favor, 2),
        "against": round(against, 2),
        "signed": round(signed, 2),
        "peak": round(peak, 2),
        "risk": round(risk, 2),
        "reward": round(reward, 2),
        "against_frac": round(against / risk, 4),
        "peak_frac_reward": round(peak / reward, 4),
        "signed_frac_reward": round(signed / reward, 4),
        "hit50": 1.0 if peak >= GB_HIT_FRAC * reward else 0.0,
        "bars": float(max(0, int(bars_since_entry))),
    }


def bars_since_taken(bars: Any, taken_at: Any) -> int:
    try:
        import fno_session_rules as rules

        after = rules.bars_after_fill(bars, taken_at)
        return int(len(after)) if after is not None else 0
    except Exception:
        return 0


def assess(metrics: Dict[str, float]) -> Dict[str, Any]:
    """Return state + codes. Priority: giveback > never > deep > weak > confident > none."""
    peak = float(metrics["peak"])
    against_frac = float(metrics["against_frac"])
    signed = float(metrics["signed"])
    reward = float(metrics["reward"])
    risk = float(metrics["risk"])
    bars = int(metrics["bars"])
    hit50 = bool(metrics["hit50"])
    peak_frac = float(metrics["peak_frac_reward"])

    state = "NONE"
    code = None
    severity = "info"
    message = None

    # WARN_GIVEBACK (50% then deeply red) — highest-stakes protect
    if hit50 and signed <= GB_SIGNED_MAX and against_frac >= GB_AGAINST_MIN:
        state = "WARN_GIVEBACK"
        code = "PATH_WARN_GIVEBACK"
        severity = "critical"
        message = (
            f"GIVEBACK WARN — call had ≥50% of target (peak {peak:.0f} / reward {reward:.0f}), "
            f"now {signed:.0f} pts vs entry with {against_frac:.0%} of stop used. "
            f"Consider protecting / dropping."
        )
    # WARN never-ran
    elif bars >= NEVER_MIN_BARS and peak < NEVER_PEAK_MAX and against_frac >= NEVER_AGAINST_MIN:
        state = "WARN_NEG_NEVER"
        code = "PATH_WARN_NEVER"
        severity = "critical"
        message = (
            f"NEGATIVE WARN — never ran (peak {peak:.1f} pts) and "
            f"{against_frac:.0%} of stop used after {bars} bars. Drop risk high."
        )
    # WARN deep weak (stricter than WEAK — auto-close; 94% loss precision on 12y/OOS)
    elif (
        bars >= DEEP_MIN_BARS
        and not hit50
        and peak_frac < DEEP_PEAK_FRAC_MAX
        and against_frac >= DEEP_AGAINST_MIN
        and signed <= DEEP_SIGNED_MAX
    ):
        state = "WARN_NEG_DEEP"
        code = "PATH_WARN_DEEP"
        severity = "critical"
        message = (
            f"DEEP WEAK WARN — after {bars} bars peak only {peak:.0f} "
            f"({peak_frac:.0%} of target), {against_frac:.0%} of stop used, "
            f"signed {signed:.0f}. High drop risk."
        )
    # WARN weak (<50% run, deep against, red) — alert only
    elif (
        bars >= WEAK_MIN_BARS
        and not hit50
        and peak_frac < WEAK_PEAK_FRAC_MAX
        and against_frac >= WEAK_AGAINST_MIN
        and signed <= WEAK_SIGNED_MAX
    ):
        state = "WARN_NEG_WEAK"
        code = "PATH_WARN_WEAK"
        severity = "critical"
        message = (
            f"NEGATIVE WARN — weak run (peak {peak:.0f} = {peak_frac:.0%} of target), "
            f"signed {signed:.0f}, {against_frac:.0%} of stop used. Consider dropping."
        )
    # BOOK hint: ran ≥50% of target, still green, but gave ≥half the peak back.
    # Alert only — auto-exit here cut ~3–5k pts vs hold on prod2 (book50_lock_hunt).
    elif hit50 and peak > 0 and signed >= 0 and signed < BOOK_PEAK_KEEP_FRAC * peak:
        kept_pct = 100.0 * signed / peak if peak else 0.0
        state = "BOOK_PULLBACK"
        code = "PATH_BOOK_PULLBACK"
        severity = "warning"
        message = (
            f"BOOK HINT — ran ≥50% of target (peak {peak:.0f} / reward {reward:.0f}), "
            f"now pulled back to {signed:.0f} pts ({kept_pct:.0f}% of peak left). "
            f"Still green — consider booking this profit before it fades. Not auto-closed."
        )
    # CONFIDENT toward T1
    elif (
        peak_frac >= CONF_PEAK_FRAC
        and signed >= CONF_SIGNED_FRAC * reward
        and against_frac < CONF_AGAINST_MAX
    ):
        state = "CONFIDENT"
        code = "PATH_CONFIDENT"
        severity = "positive"
        message = (
            f"CONFIDENT — tracking target (peak {peak:.0f} = {peak_frac:.0%} of reward, "
            f"live {signed:.0f} pts, only {against_frac:.0%} of stop used)."
        )

    if state == "CONFIDENT":
        tone = "green"
    elif state.startswith("WARN") or state == "BOOK_PULLBACK":
        tone = "red" if state.startswith("WARN") else "amber"
    else:
        tone = "neutral"
    return {
        "state": state,
        "code": code,
        "severity": severity,
        "message": message,
        "metrics": metrics,
        "tone": tone,
    }


def assess_open_ticket(
    ticket: Optional[Dict[str, Any]],
    *,
    last: float,
    path_high: Optional[float] = None,
    path_low: Optional[float] = None,
    bars: Any = None,
) -> Optional[Dict[str, Any]]:
    """Assess an open session ticket from live price + path extremes."""
    if not ticket:
        return None
    entry = _f(ticket.get("entry"))
    stop = _f(ticket.get("stop_loss"))
    t1 = _f(ticket.get("target_1"))
    if entry is None or stop is None or t1 is None:
        return None
    px = float(last)
    hi = float(path_high if path_high is not None else px)
    lo = float(path_low if path_low is not None else px)
    n_bars = bars_since_taken(bars, ticket.get("taken_at"))
    metrics = path_metrics(
        decision=ticket.get("decision"),
        entry=entry,
        stop_loss=stop,
        target_1=t1,
        last=px,
        path_high=hi,
        path_low=lo,
        bars_since_entry=n_bars,
    )
    if not metrics:
        return None
    out = assess(metrics)
    out["decision"] = ticket.get("decision")
    out["entry"] = entry
    return out


def alerts_from_assessment(assessment: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not assessment or not assessment.get("code") or not assessment.get("message"):
        return []
    return [
        {
            "code": assessment["code"],
            "severity": assessment["severity"],
            "tone": assessment.get("tone") or "neutral",
            "message": assessment["message"],
            "path_health": assessment.get("state"),
            "metrics": assessment.get("metrics"),
        }
    ]


def attach_path_health_alerts(
    alerts: List[Dict[str, Any]],
    assessment: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Prepend path-health alerts so they surface first; dedupe by code."""
    extra = alerts_from_assessment(assessment)
    if not extra:
        return list(alerts or [])
    codes = {a.get("code") for a in extra}
    kept = [a for a in (alerts or []) if a.get("code") not in codes]
    return extra + kept


def research_state_from_step(step: Dict[str, Any], *, bars: int) -> str:
    """Mirror assess() for research-path steps (unit/compare tests)."""
    metrics = {
        "favor": float(step["favor"]),
        "against": float(step["against"]),
        "signed": float(step["signed_close"]),
        "peak": float(step["favor"]),
        "risk": float(step["risk"]),
        "reward": float(step["reward"]),
        "against_frac": float(step["against_frac"]),
        "peak_frac_reward": float(step["favor"]) / float(step["reward"]) if float(step["reward"]) else 0.0,
        "signed_frac_reward": float(step["signed_close"]) / float(step["reward"]) if float(step["reward"]) else 0.0,
        "hit50": 1.0 if float(step["favor"]) >= GB_HIT_FRAC * float(step["reward"]) else 0.0,
        "bars": float(bars),
    }
    # peak should be running max — caller must pass cumulative favor as peak in step["favor"] when walking
    return str(assess(metrics)["state"])
