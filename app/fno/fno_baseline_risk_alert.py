"""Baseline SL-risk alert flags for F&O dual-track (NIFTY 6m walk-forward).

Alert-only: does not change proven / champion / baseline entry gates.
Validated on NIFTY 6m baseline (OOS HIGH ~81% SL; SELL ≥3 flags ~87% SL).

Use score_baseline_risk() + risk_accuracy_tag() from live dual-track evaluate().
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Locked thresholds from NIFTY 6m research (chrono OOS held).
SELL_FLAG_RULES = (
    {
        "id": "or_ext_high",
        "param": "or_ext",
        "dir": "high",
        "thr": 1.3212,
        "label": "stretched past opening range",
    },
    {
        "id": "noise_tight",
        "param": "noise_vs_sl",
        "dir": "low",
        "thr": 0.7186,
        "label": "stop too tight vs bar noise",
    },
    {
        "id": "atr_not_expanding",
        "param": "atr_expand",
        "dir": "low",
        "thr": 0.9661,
        "label": "volatility not expanding with move",
    },
    {
        "id": "confirms_late",
        "param": "confirms",
        "dir": "high",
        "thr": 9.0,
        "label": "late in the move (many confirms)",
    },
    {
        "id": "adx_weak",
        "param": "adx_14",
        "dir": "low",
        "thr": 21.2457,
        "label": "weak trend strength",
    },
    {
        "id": "p_t1_soft",
        "param": "p_t1",
        "dir": "low",
        "thr": 0.6957,
        "label": "soft model T1 score",
    },
)

# Desk-facing tier copy — plain language for new users (6m research rates).
# priority: lower number shows first on the desk (red risk before green priority).
TIER_COPY = {
    "HIGH": {
        "label": "High risk · Often hits stop-loss",
        "tone": "risk",  # desk: red
        "priority": 0,
        "action": "Prefer skip or use a very small size",
        "expected_sl_pct": 75.0,
        "detail_prefix": "Similar setups often hit stop-loss before the first target (~75–80%)",
    },
    "MED": {
        "label": "Elevated risk · Stop more likely",
        "tone": "risk",  # desk: red
        "priority": 1,
        "action": "Consider half size",
        "expected_sl_pct": 55.0,
        "detail_prefix": "Two warning signs — stop-loss is more likely than on a clean setup",
    },
    "LOW": {
        "label": "Some risk · Watch the stop-loss",
        "tone": "risk",  # desk: red
        "priority": 2,
        "action": "Normal size is OK · stay alert",
        "expected_sl_pct": 40.0,
        "detail_prefix": "One mild warning sign — keep an eye on the stop",
    },
    "OK": {
        "label": "Safer setup · Lower stop risk",
        "tone": "good",  # desk: green
        "priority": 25,
        "action": "No elevated stop-loss flags on this setup",
        "expected_sl_pct": 20.0,
        "detail_prefix": "No elevated stop-loss warning flags",
    },
}

# Fallback sort when a tag has no explicit priority.
_CODE_PRIORITY = {
    "sl_risk_high": 0,
    "sl_risk_med": 1,
    "sl_risk_low": 2,
    "proven_100": 10,
    "most_accurate": 11,
    "side_accuracy": 40,
    "sl_risk_ok": 25,
    "lower_accuracy": 30,
    "baseline_accuracy": 31,
}


def _f(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fires(value: Optional[float], direction: str, thr: float) -> bool:
    if value is None:
        return False
    return value >= thr if direction == "high" else value <= thr


def score_baseline_risk(
    *,
    decision: str,
    first_break: bool,
    p_t1: float,
    or_ext: float,
    features: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return risk_tier / flags for a dual-track call.

    Policy:
      HIGH — BUY, or SELL with ≥3 sell-flags
      MED  — SELL with ≥2 sell-flags
      LOW  — SELL with 1 sell-flag
      OK   — SELL with 0 sell-flags
    """
    feat = dict(features or {})
    values = {
        "or_ext": _f(or_ext if or_ext is not None else feat.get("or_ext")),
        "noise_vs_sl": _f(feat.get("noise_vs_sl")),
        "atr_expand": _f(feat.get("atr_expand")),
        "confirms": _f(feat.get("confirms")),
        "adx_14": _f(feat.get("adx_14")),
        "p_t1": _f(p_t1),
    }

    side = str(decision or "").upper()
    if side == "BUY":
        copy = TIER_COPY["HIGH"]
        return {
            "risk_tier": "HIGH",
            "risk_score": 3,
            "risk_label": "High risk · This BUY often hits stop-loss",
            "risk_action": copy["action"],
            "expected_sl_pct": 65.0,  # BUY baseline ~65% SL in 6m sample
            "sell_flag_n": 0,
            "risk_flags": ["buy_first_break"],
            "risk_flag_labels": [
                "BUY first-break baseline setups often hit stop-loss before target"
            ],
            "params_used": {**values, "first_break": bool(first_break)},
            "policy": "buy_first_break_high",
            "alert_only": True,
        }

    flags: List[str] = []
    labels: List[str] = []
    if side == "SELL":
        for rule in SELL_FLAG_RULES:
            if _fires(values.get(rule["param"]), rule["dir"], float(rule["thr"])):
                flags.append(rule["id"])
                labels.append(rule["label"])

    n = len(flags)
    if n >= 3:
        tier, score = "HIGH", 3
    elif n >= 2:
        tier, score = "MED", 2
    elif n == 1:
        tier, score = "LOW", 1
    else:
        tier, score = "OK", 0

    copy = TIER_COPY[tier]
    return {
        "risk_tier": tier,
        "risk_score": score,
        "risk_label": copy["label"],
        "risk_action": copy["action"],
        "expected_sl_pct": copy["expected_sl_pct"],
        "sell_flag_n": n,
        "risk_flags": flags,
        "risk_flag_labels": labels,
        "params_used": values,
        "policy": "sell_flag_count",
        "alert_only": True,
    }


def risk_accuracy_tag(risk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Desk pill for accuracy_tags (baseline track)."""
    if not risk:
        return None
    tier = str(risk.get("risk_tier") or "OK")
    copy = TIER_COPY.get(tier) or TIER_COPY["OK"]
    flags = list(risk.get("risk_flag_labels") or [])
    why = "; ".join(flags) if flags else copy["detail_prefix"]
    detail = f"{copy['detail_prefix']}. {why}. → {risk.get('risk_action') or copy['action']}"
    label = str(risk.get("risk_label") or copy["label"])
    return {
        "code": f"sl_risk_{tier.lower()}",
        "label": label,
        "detail": detail,
        "tone": copy["tone"],
        "priority": int(copy.get("priority", 50)),
        "risk_tier": tier,
        "risk_flags": list(risk.get("risk_flags") or []),
        "risk_action": risk.get("risk_action") or copy["action"],
        "expected_sl_pct": risk.get("expected_sl_pct"),
    }


def desk_tag_priority(tag: Dict[str, Any]) -> int:
    """Lower number = higher desk priority (show first)."""
    if not tag:
        return 99
    raw = tag.get("priority")
    if raw is not None and raw != "":
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    code = str(tag.get("code") or tag.get("key") or "").lower()
    if code in _CODE_PRIORITY:
        return _CODE_PRIORITY[code]
    tone = str(tag.get("tone") or "").lower()
    if tone == "risk":
        return 2
    if tone in ("proven", "champion", "strong"):
        return 12
    if tone == "good":
        return 25
    return 50


def sort_desk_tags(tags: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Red risk first, then green Priority / accuracy, then the rest."""
    items = [t for t in (tags or []) if t]
    return sorted(items, key=desk_tag_priority)


def payload_risk_fields(risk: Dict[str, Any]) -> Dict[str, Any]:
    """Fields to merge into call_payload / suggestion_payload / model_view."""
    if not risk:
        return {}
    return {
        "risk_tier": risk.get("risk_tier"),
        "risk_score": risk.get("risk_score"),
        "risk_label": risk.get("risk_label"),
        "risk_action": risk.get("risk_action"),
        "risk_flags": risk.get("risk_flags"),
        "risk_flag_labels": risk.get("risk_flag_labels"),
        "sell_flag_n": risk.get("sell_flag_n"),
        "expected_sl_pct": risk.get("expected_sl_pct"),
    }


def apply_baseline_risk(
    *,
    decision: str,
    first_break: bool,
    p_t1: float,
    or_ext: float,
    features: Optional[Dict[str, Any]],
    tags: List[Dict[str, Any]],
    is_baseline: bool,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Score risk; append desk tag when this is a baseline-listed setup."""
    risk = score_baseline_risk(
        decision=decision,
        first_break=first_break,
        p_t1=p_t1,
        or_ext=or_ext,
        features=features,
    )
    out_tags = list(tags or [])
    if is_baseline:
        tag = risk_accuracy_tag(risk)
        if tag:
            out_tags.append(tag)
    return risk, sort_desk_tags(out_tags)


def risk_message_suffix(risk: Dict[str, Any]) -> str:
    if not risk:
        return ""
    label = risk.get("risk_label") or risk.get("risk_tier")
    action = risk.get("risk_action")
    if action:
        return f"{label}. {action}."
    return f"{label}."
