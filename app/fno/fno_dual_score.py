"""Shared dual-track side scoring for NIFTY / BANKNIFTY / SENSEX.

Research side packs drive proven/champion. When a research pack HOLDs under the
production desk score (common on Sensex — research BUY pack ~49% while
`fno_SENSEX.pkl` clears ~53%), fall back to the production F&O pack so
**baseline** (research buy_min_p=0.50) still lists the same calls the live
core path would.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _regime_from_feat(feat: Any) -> str:
    if not isinstance(feat, dict):
        return "mixed"
    if float(feat.get("regime_trend") or 0) >= 0.5:
        return "trend"
    if float(feat.get("regime_volatile") or 0) >= 0.5:
        return "volatile"
    if float(feat.get("regime_range") or 0) >= 0.5:
        return "range"
    return "mixed"


def _clip_levels(symbol: str, entry: float, decision: str, bars: Any) -> Optional[tuple]:
    try:
        import fno_risk_engine as fre

        atr = fre.bar_atr(bars)
        sl_pts, t1_pts, _t2, _ = fre.clip_points(symbol, float(entry), atr=atr)
        if str(decision).upper() == "BUY":
            return float(entry) - sl_pts, float(entry) + t1_pts
        return float(entry) + sl_pts, float(entry) - t1_pts
    except Exception:
        return None


def _production_pack(symbol: str) -> Optional[dict]:
    try:
        import fno_model

        pack = fno_model.load(symbol=str(symbol).upper())
        if isinstance(pack, dict) and pack.get("available"):
            return pack
    except Exception:
        return None
    return None


def _run_snap(
    bars: Any,
    *,
    symbol: str,
    pack: Optional[dict],
    day_range: Optional[dict],
    asof: Any,
    soft_baseline: bool = True,
) -> Dict[str, Any]:
    import fno_session_replay

    soft = dict(pack or {})
    if soft_baseline:
        # Research baseline floor is 0.50 — soft-open pack so dual gates own listing.
        soft["buy_p"] = min(float(soft.get("buy_p") or 0.50), 0.50)
        soft["buy_gates"] = None
    return fno_session_replay.score_snapshot(
        bars,
        symbol=str(symbol).upper(),
        day_range=day_range,
        model_pack=soft if soft else None,
        primary=True,
        asof=asof,
        session_ticket=None,
        indications=None,
    )


def score_production_issued(
    bars: Any,
    *,
    symbol: str,
    day_range: Optional[dict],
    asof: Any,
    force_decision: Optional[str] = None,
) -> Optional[dict]:
    """Pre-dual prod2 path: production pack as-is, only if desk issued a ticket."""
    prod = _production_pack(symbol)
    if prod is None:
        return None
    try:
        snap = _run_snap(
            bars,
            symbol=symbol,
            pack=prod,
            day_range=day_range,
            asof=asof,
            soft_baseline=False,
        )
        issued = snap.get("issued_ticket") or {}
        want = str(force_decision or issued.get("decision") or "").upper()
        if want not in ("BUY", "SELL"):
            return None
        if str(issued.get("decision") or "").upper() != want:
            return None
        scored = _from_snap(
            snap,
            bars=bars,
            symbol=symbol,
            force_decision=want,
            baseline_min_p=0.0,
            score_source="production_issued_prod2",
        )
        if scored and scored["decision"] == want:
            scored["issued"] = True
            return scored
    except Exception:
        return None
    return None


def _from_snap(
    snap: Dict[str, Any],
    *,
    bars: Any,
    symbol: str,
    force_decision: Optional[str],
    baseline_min_p: float,
    score_source: str,
) -> Optional[dict]:
    head = snap.get("fno_head") or {}
    issued = snap.get("issued_ticket")
    p_t1 = float(head.get("p_t1") or 0.0)
    feat = head.get("features") or {}
    want = str(force_decision or "").upper()

    if issued:
        decision = str(issued.get("decision") or "HOLD")
        entry = float(issued.get("entry"))
        stop = float(issued.get("stop_loss"))
        target = float(issued.get("target_1"))
    else:
        decision = str(head.get("decision") or snap.get("decision") or "HOLD")
        entry = float(snap.get("price") or 0)
        stop = snap.get("stop_loss")
        target = snap.get("target_1")

    # Dual gates own listing: OR side + research baseline floor.
    if decision not in ("BUY", "SELL") and want in ("BUY", "SELL") and p_t1 >= float(baseline_min_p):
        decision = want

    if decision not in ("BUY", "SELL"):
        return None

    if stop is None or target is None or entry <= 0:
        clipped = _clip_levels(symbol, entry if entry > 0 else float(snap.get("price") or 0), decision, bars)
        if not clipped:
            return None
        entry = float(entry if entry > 0 else snap.get("price") or 0)
        stop, target = clipped

    return {
        "decision": decision,
        "entry": round(float(entry), 2),
        "stop_loss": round(float(stop), 2),
        "target_1": round(float(target), 2),
        "p_t1": round(p_t1, 4),
        "p_sl": round(max(0.0, min(1.0, 1.0 - p_t1)), 4),
        "features": feat,
        "regime": _regime_from_feat(feat),
        "head": head,
        "snap": snap,
        "score_source": score_source,
    }


def score_side(
    bars: Any,
    *,
    symbol: str,
    pack: dict,
    day_range: Optional[dict],
    asof: Any,
    force_decision: Optional[str] = None,
    baseline_min_p: float = 0.50,
) -> Optional[dict]:
    """Score OR side for dual-track.

    1) Research / side pack (softened to baseline 0.50)
    2) If miss — production `fno_{SYMBOL}.pkl` (same head live core uses)
    """
    try:
        snap = _run_snap(
            bars, symbol=symbol, pack=pack, day_range=day_range, asof=asof
        )
        scored = _from_snap(
            snap,
            bars=bars,
            symbol=symbol,
            force_decision=force_decision,
            baseline_min_p=baseline_min_p,
            score_source="research_pack",
        )
        if scored and scored["decision"] == str(force_decision or scored["decision"]).upper():
            return scored
        # Research pack missed or wrong side — production baseline fallback.
        prod = _production_pack(symbol)
        if prod is None:
            return scored
        snap2 = _run_snap(
            bars, symbol=symbol, pack=prod, day_range=day_range, asof=asof
        )
        return _from_snap(
            snap2,
            bars=bars,
            symbol=symbol,
            force_decision=force_decision,
            baseline_min_p=baseline_min_p,
            score_source="production_pack",
        )
    except Exception:
        return None
