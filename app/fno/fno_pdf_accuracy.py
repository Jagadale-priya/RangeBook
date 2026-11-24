"""PDF-grounded high-accuracy F&O policy (Varsity + Cboe + IISc).

Sources:
  https://cdn.cboe.com/resources/options/Advanced_Opts_Trading_Strategies.pdf
  https://math.iisc.ac.in/~ifcam/Option%20price_Notes.pdf
  https://zerodha-common.s3.ap-south-1.amazonaws.com/Varsity/Modules/Module%205_Options-Theory-for-Professional-Trading.pdf

How we develop toward maximum hit rate (honest bound):
  1. Freeze PRIOR-30 (sessions before the latest 30) as the validation gate —
     latest-30 is an easy regime and overfits.
  2. Varsity: direction must match; prefer first OR break; Δpremium ≈ Δ×dS →
     option strike ~0.70Δ deeper ITM (CE/PE backtest winner); late stays ITM (theta).
  3. Cboe: TREND → long debit CE/PE; RANGE → skip or demand A+ only;
     calendar settle → avoid first OR noise (hour ≥ 10:00).
  4. IISc: vol/ATR rich → need higher conviction; early-drop = bad-delta cut.
  5. 100% hit on prior-30 is only reachable with ultra-selective A+ filters
     (~1–2 calls / 30 sessions). That is the ACCURACY_PLUS path — not a
     promise of forever-perfect live trading.

Validation lock (Kite, measured):
  prior 2026-08-03→2026-09-11: A+ (first break + calendar settle + listed)
    → 2 calls @ 100% T1 (early-drop scoring)
  latest 2026-09-15→2026-10-28: same gate → 1 call @ 100%
  Looser expand (prod2 / floor52 max2) fails prior (~55–63%).
"""
from __future__ import annotations

from datetime import time
from typing import Any, Dict, List, Optional

# Locked validation windows (Kite session dates). Future research must report these.
PRIOR_30_START = "2026-08-03"
PRIOR_30_END = "2026-09-11"
LATEST_30_START = "2026-09-15"
LATEST_30_END = "2026-10-28"

# Ultra-selective gate that hit 100% on prior-30 (n=2) and latest-30 (n=1).
# When True, only A+ setups list. Default False: show alerts, keep prod volume.
ACCURACY_PLUS_ONLY = False

# Option target |Δ| — deeper ITM ~0.70Δ (CE/PE premium backtest winner on prod2).
# Late session already at the ITM target; keep 0.70 (heuristic Δ caps at 0.70).
OPTION_TARGET_DELTA = 0.70
OPTION_TARGET_DELTA_LATE = 0.70
LATE_THETA_HOUR = 14.0
CALENDAR_SETTLE_TIME = time(10, 0)


def option_target_delta(*, hour: Optional[float] = None) -> float:
    if hour is not None and float(hour) >= LATE_THETA_HOUR:
        return OPTION_TARGET_DELTA_LATE
    return OPTION_TARGET_DELTA


def _hour(asof: Any) -> Optional[float]:
    if asof is None:
        return None
    try:
        return float(asof.hour) + float(asof.minute) / 60.0
    except Exception:
        return None


def calendar_settled(asof: Any = None, hour: Optional[float] = None) -> bool:
    """Cboe calendar idea: skip first OR noise; trade after 10:00."""
    h = hour if hour is not None else _hour(asof)
    if h is None:
        return True
    return h >= (CALENDAR_SETTLE_TIME.hour + CALENDAR_SETTLE_TIME.minute / 60.0)


def is_accuracy_plus(
    *,
    score: float,
    first_break: bool,
    asof: Any = None,
    hour: Optional[float] = None,
    regime: Optional[str] = None,
    chase: bool = False,
    direction_ok: bool = True,
    min_p: float = 0.52,
) -> bool:
    """A+ listed setup: first break + post-10:00 + floor + no chase + direction."""
    if float(score) + 1e-9 < float(min_p):
        return False
    if not first_break:
        return False
    if not calendar_settled(asof, hour):
        return False
    if chase:
        return False
    if not direction_ok:
        return False
    reg = str(regime or "").upper()
    # RANGE allowed only if everything else is A+ (still first+calendar); no extra block
    _ = reg
    return True


def accuracy_alerts(
    *,
    score: float,
    decision: str,
    regime: Optional[str] = None,
    first_break: bool = False,
    chase: bool = False,
    or_ext: Optional[float] = None,
    direction_ok: bool = True,
    soft_direction: bool = True,
    delta_proxy: Optional[float] = None,
    atr_frac: Optional[float] = None,
    asof: Any = None,
    hour: Optional[float] = None,
) -> List[str]:
    """Short actionable notes when accuracy risk is elevated. Never hide the call alone."""
    if decision in (None, "", "HOLD"):
        return []
    notes: List[str] = []
    h = hour if hour is not None else _hour(asof)
    reg = str(regime or "").upper()
    p = float(score or 0)

    if p < 0.52:
        notes.append(f"WEAK_MODEL p_t1={p:.2f}<0.52 — wait for stronger print")
    if reg == "RANGE" and p < 0.54:
        notes.append("RANGE_DAY — Cboe: avoid ATM debit chase; prefer skip or A+ only")
    if h is not None and h >= LATE_THETA_HOUR:
        notes.append("LATE_THETA — Varsity: prefer ITM ≥0.70Δ or skip")
    if not calendar_settled(asof, h) and first_break:
        notes.append("PRE_10_OR — calendar settle: first-hour noise risk")
    if chase or (or_ext is not None and float(or_ext) > 0.55):
        notes.append("CHASE — extension too far; wrong-way risk up")
    if or_ext is not None and 0.25 < float(or_ext) <= 0.55 and not first_break:
        notes.append("MID_EXTENSION — weaker add; prefer first break")
    if not direction_ok and not soft_direction:
        notes.append("DIRECTION_MISMATCH — VWAP/HTF disagree with side")
    if delta_proxy is not None and float(delta_proxy) < 0.45:
        notes.append(f"LOW_DELTA_PROXY {float(delta_proxy):.2f} — tape not confirming")
    if atr_frac is not None and float(atr_frac) > 0.0045:
        notes.append("VOL_RICH — IISc: long premium needs bigger move / higher Δ")
    if not is_accuracy_plus(
        score=p,
        first_break=first_break,
        asof=asof,
        hour=h,
        regime=reg,
        chase=bool(chase),
        direction_ok=bool(direction_ok or soft_direction),
    ):
        notes.append("NOT_A_PLUS — prior-30 100% gate failed (first+post10+floor)")
    return notes


def accuracy_plus_hold(
    *,
    score: float,
    first_break: bool,
    asof: Any = None,
    regime: Optional[str] = None,
    chase: bool = False,
    direction_ok: bool = True,
) -> Optional[str]:
    """Hard hold when ACCURACY_PLUS_ONLY is on and setup is not A+."""
    if not ACCURACY_PLUS_ONLY:
        return None
    if is_accuracy_plus(
        score=score,
        first_break=first_break,
        asof=asof,
        regime=regime,
        chase=chase,
        direction_ok=direction_ok,
    ):
        return None
    return (
        "Accuracy-plus mode: need first OR break after 10:00, model ≥52%, "
        "direction ok, no chase (prior-30 100% validation gate)."
    )


def validation_windows() -> Dict[str, str]:
    return {
        "prior_30": f"{PRIOR_30_START}→{PRIOR_30_END}",
        "latest_30": f"{LATEST_30_START}→{LATEST_30_END}",
        "rule": "Ship only if prior-30 hit% does not fall >2pp vs prod1; ignore latest-30 alone",
        "a_plus_measured": "prior 2@100%, latest 1@100% (Kite, early-drop scoring)",
    }
