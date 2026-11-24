"""Live desk channel switches.

USE_DUAL_TRACK=1 (default off when ENABLE_PRE_DUAL_SINGLE=1):
  proven/champion dual evaluation (and listing unless SUPPRESS_DUAL_LIST).

SUPPRESS_DUAL_LIST=1 (default ON):
  Keep dual proven/champion scoring + annotate, but do **not** list those
  tickets on Calls. Board then fills from CHAMP_PLUS / crown (and any other
  fill channels). Set SUPPRESS_DUAL_LIST=0 to restore proven→champion first.

ENABLE_PRE_DUAL_SINGLE=1:
  Pre-dual single fno_model listing (research prod2 / issued_prod recipe).
  Tagged **good** (~71% research 1y/2y). Soft gates: no hard HOLD from
  shallow OR poke / NIFTY entry_issue — alerts only; model BUY/SELL lists.

ENABLE_EXTRA_TREES_SINGLE=1:
  Raw ExtraTrees / rule_fno 15m single modal may list on Calls.
  Default OFF — dual proven/champion is the live path. Does not disable
  dual-track evaluation or proven/champion listing.

ENABLE_STACKED_CALLS=1:
  Research final stack_plus_crown_htf_cap2 — union proven ∪ good ∪ champion
  ∪ HTF-gated crown, day cap 2, same side. Keeps pre-dual good as core and
  evaluates dual tracks as higher/lower priority add-ons.
  NIFTY champion live floors: BUY p>=0.55 · SELL p>=0.58
  (BUY raised from 0.50 after 3y stabilize research).

ENABLE_NSE_MID_GATE=1:
  Frozen Nov prior-day NSE mid-tercile filter on stacked listings.
  Default col AbsChangePct in [0.6276, 1.6866). Optional NSE_MID_GATE_COLS.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


def _truthy(name: str, default: str = "0") -> bool:
    v = str(os.environ.get(name, default)).strip().lower()
    return v not in ("0", "false", "no", "off", "")


def enable_pre_dual_single() -> bool:
    """Prod single-modal listing (research prod2)."""
    return _truthy("ENABLE_PRE_DUAL_SINGLE", "0")


def enable_stacked_calls() -> bool:
    """Prod stacked union (research stack_plus_crown_htf_cap2)."""
    return _truthy("ENABLE_STACKED_CALLS", "0")


def enable_extra_trees_single() -> bool:
    """Explicit research override to list raw ExtraTrees 15m singles."""
    return _truthy("ENABLE_EXTRA_TREES_SINGLE", "0")


def allow_extra_trees_single_list() -> bool:
    """Whether ExtraTrees / rule_fno core may create a Calls ticket.

    Dual-exclusive desk (USE_DUAL_TRACK=1, pre-dual/stack off): False — only
    proven/champion dual_call lists. Pre-dual / stacked good channel: True.
    ENABLE_EXTRA_TREES_SINGLE=1: True for research.
    """
    if enable_extra_trees_single():
        return True
    if enable_pre_dual_single() or enable_stacked_calls():
        return True
    return False


def suppress_core_list_if_needed(
    decision: str,
    *,
    dual_call: Optional[Dict[str, Any]] = None,
) -> str:
    """HOLD ExtraTrees fall-through when dual desk did not fire a listable call."""
    side = str(decision or "HOLD").upper()
    if side not in ("BUY", "SELL"):
        return side or "HOLD"
    if isinstance(dual_call, dict) and dual_call.get("decision") in ("BUY", "SELL"):
        return side
    if allow_extra_trees_single_list():
        return side
    return "HOLD"


def enable_p2f_live_accurate() -> bool:
    """Annotate NIFTY with promoted P2F day+Cap2 accurate books (additive).

    Does not change volume stack selection. Default ON.
    Set ENABLE_P2F_LIVE_ACCURATE=0 to disable.
    """
    return _truthy("ENABLE_P2F_LIVE_ACCURATE", "1")


# Live F&O index desk — NIFTY + SENSEX only (BANKNIFTY removed to cut processing).
FNO_LIVE_INDEXES = ("NIFTY", "SENSEX")


def fno_live_indexes() -> tuple:
    """Symbols on the live F&O desk / 90s refresh / dual-track watch."""
    return FNO_LIVE_INDEXES


def is_fno_live_index(symbol: str) -> bool:
    return str(symbol or "").strip().upper() in FNO_LIVE_INDEXES


def enable_bn_final_live() -> bool:
    """BANKNIFTY FINAL books — OFF by default (BN removed from live F&O desk).

    Set ENABLE_BN_FINAL_LIVE=1 only for research. NIFTY path untouched.
    """
    return _truthy("ENABLE_BN_FINAL_LIVE", "0")


def enable_sensex_final_live() -> bool:
    """Annotate SENSEX with locked dual+fb bf≥20% ±50 FINAL book. Default ON.

    Set ENABLE_SENSEX_FINAL_LIVE=0 to disable. NIFTY path untouched.
    """
    return _truthy("ENABLE_SENSEX_FINAL_LIVE", "1")


def enable_nifty_afternoon_thrust() -> bool:
    """NIFTY post-13:00 BUY thrust lane — OFF by default for accuracy.

    Research thrust2_up30 was ~92% on a 60-session slice, but full 1y/3y/5y
    replay is ~50–57% @ ±30 — too weak for the accuracy desk.
    Set ENABLE_NIFTY_AFTERNOON_THRUST=1 to force on after a better gate.
    """
    return _truthy("ENABLE_NIFTY_AFTERNOON_THRUST", "0")


def enable_nifty_morning_strong_thrust() -> bool:
    """NIFTY morning strong BUY — locked L5_u70_b80 (100% 1y/3y/5y research).

    15m thrust → 5m OR+5 fill · ±30 · Cap 1/day · confident.
    Default ON. Set ENABLE_NIFTY_MORNING_STRONG_THRUST=0 to disable.
    """
    return _truthy("ENABLE_NIFTY_MORNING_STRONG_THRUST", "1")


def enable_nse_mid_gate() -> bool:
    """Frozen Nov NSE mid-tercile gate on stacked PROD listings."""
    return _truthy("ENABLE_NSE_MID_GATE", "0")


def use_dual_track() -> bool:
    """When False, live Calls follow pre-dual single fno_model path.

    Stacked mode keeps this False so good/prod2 stays the core path; dual
    proven/champion are evaluated separately via fno_stacked_calls.
    """
    if enable_pre_dual_single() or enable_stacked_calls():
        return False
    return _truthy("USE_DUAL_TRACK", "1")


def suppress_dual_list() -> bool:
    """Evaluate dual proven/champion but do not list them on Calls.

    Default ON so CHAMP_PLUS / crown fills are the live board path while dual
    packs still run for annotate / debug. Set SUPPRESS_DUAL_LIST=0 to restore
    proven_100 → champion as the primary list track.
    """
    return _truthy("SUPPRESS_DUAL_LIST", "1")


def suppress_dual_list_for(symbol: str) -> bool:
    """Per-symbol suppress. NIFTY Calls are thrust-only (dual never lists).

    SENSEX EVERYDAY must list dual/OR-fallback for 1/day.
    """
    sym = str(symbol or "").upper()
    # NIFTY: only morning strong + afternoon thrust board. Dual champion/proven
    # stay annotate-only always — removes SUPPRESS maze for NIFTY Calls.
    if sym in ("NIFTY", "NIFTY 50", "NIFTY50"):
        return True
    if not suppress_dual_list():
        return False
    if sym in ("SENSEX", "BSESENSEX", "BSE SENSEX"):
        try:
            from prod_live.logic import sensex_final_live as sx

            desk = str(getattr(sx, "DESK_CHAMP", "") or "")
            if ("EVERYDAY" in desk.upper()) or ("DUAL_2PD" in desk.upper()) or ("DUAL_FB_COMBINE" in desk.upper()) or desk.upper().startswith("SENSEX_DUAL"):
                return False
        except Exception:
            pass
    return True


def pre_dual_soft_gates() -> bool:
    """No hard HOLD / entry_issue / shallow block on pre-dual good path.

    Default ON whenever pre-dual single is enabled. Set
    PRE_DUAL_SOFT_GATES=0 to restore hard shallow/entry blocks.
    """
    if enable_stacked_calls() and enable_pre_dual_single():
        return _truthy("PRE_DUAL_SOFT_GATES", "1")
    if not enable_pre_dual_single() and use_dual_track():
        return False
    if enable_pre_dual_single() or not use_dual_track():
        return _truthy("PRE_DUAL_SOFT_GATES", "1")
    return False


# Research-route measured (full12y_candidates · prod2)
GOOD_HIT_PCT = 71.3
GOOD_HIT_PCT_2Y = 71.1
GOOD_TAG_CODE = "good"
GOOD_TRACK = "pre_dual_single"

# Final stack research (nifty_final_stack_2y / 6m)
STACK_HIT_PCT_6M = 78.6
STACK_HIT_PCT_1Y = 75.3
STACK_HIT_PCT_2Y = 73.4
STACK_TAG_CODE = "stacked"
STACK_TRACK = "stack_plus_crown_htf_cap2"

# Frozen Nov NSE mid gate (AbsChangePct default) on stacked PROD
NSE_MID_HIT_LIFT_5Y = 1.62
NSE_MID_TAG_CODE = "nse_mid"


def good_accuracy_tags(*, decision: str = "") -> List[Dict[str, Any]]:
    side = str(decision or "").upper()
    detail = (
        f"Research prod2 single modal · ~{GOOD_HIT_PCT:.0f}% hit on 1y "
        f"(~{GOOD_HIT_PCT_2Y:.0f}% on 2y) · issued_prod max 2/day"
    )
    tags = [
        {
            "code": GOOD_TAG_CODE,
            "label": "Good · ~71% research",
            "detail": detail,
            "expected_hit_pct": GOOD_HIT_PCT,
            "tone": "good",
            "priority": 20,
        },
        {
            "code": "pre_dual_single",
            "label": "Pre-dual single (prod2)",
            "detail": (
                "Live listing from core fno_model (pre dual-track). "
                "Soft gates — no hard shallow/entry HOLD."
            ),
            "expected_hit_pct": GOOD_HIT_PCT,
            "tone": "good",
            "priority": 25,
        },
    ]
    if side in ("BUY", "SELL"):
        tags.append(
            {
                "code": "side_note",
                "label": f"{side} · good track",
                "detail": f"Listed {side} on good pre-dual single path",
                "expected_hit_pct": GOOD_HIT_PCT,
                "tone": "good",
                "priority": 40,
            }
        )
    return tags


def stamp_good_readings(readings: Any, *, decision: str = "") -> Any:
    if not isinstance(readings, dict):
        return readings
    readings["dual_track"] = False
    readings["track"] = GOOD_TRACK
    readings["source"] = GOOD_TRACK
    readings["accuracy_label"] = "Good · pre-dual single"
    readings["accuracy_tags"] = good_accuracy_tags(decision=decision)
    readings["history_eligible"] = True
    readings["priority"] = 75
    readings["live_confluence"] = False
    readings["proven_100"] = False
    readings["good"] = True
    readings["soft_gates"] = True
    if enable_stacked_calls():
        readings["stacked_calls"] = True
        readings["stack_track"] = STACK_TRACK
        tags = list(readings.get("accuracy_tags") or [])
        tags.insert(
            0,
            {
                "code": STACK_TAG_CODE,
                "label": f"Stacked · ~{STACK_HIT_PCT_6M:.0f}% 6m research",
                "detail": (
                    f"stack_plus_crown_htf_cap2 · 6m {STACK_HIT_PCT_6M}% / "
                    f"1y {STACK_HIT_PCT_1Y}% / 2y {STACK_HIT_PCT_2Y}% · "
                    "proven>good>champ>HTF-crown · cap2 same-side"
                ),
                "expected_hit_pct": STACK_HIT_PCT_1Y,
                "tone": "good",
                "priority": 10,
            },
        )
        if enable_nse_mid_gate():
            readings["nse_mid_gate"] = True
            tags.insert(
                0,
                {
                    "code": NSE_MID_TAG_CODE,
                    "label": "NSE mid · AbsChangePct",
                    "detail": (
                        "Frozen Nov prior-day AbsChangePct mid [0.6276,1.6866) · "
                        f"~+{NSE_MID_HIT_LIFT_5Y:.1f}pt hit vs base on 5y PROD"
                    ),
                    "expected_hit_pct": STACK_HIT_PCT_1Y + NSE_MID_HIT_LIFT_5Y,
                    "tone": "good",
                    "priority": 8,
                },
            )
        readings["accuracy_tags"] = tags
    return readings


def stamp_stack_dual_readings(readings: Any, *, dual_call: Dict[str, Any]) -> Any:
    """Mark dual proven/champ listings that were chosen under stacked mode."""
    if not isinstance(readings, dict) or not isinstance(dual_call, dict):
        return readings
    track = str(dual_call.get("track") or "champion")
    readings["stacked_calls"] = True
    readings["stack_track"] = STACK_TRACK
    readings["dual_track"] = True
    readings["track"] = track
    readings["source"] = track
    readings["accuracy_label"] = dual_call.get("accuracy_label")
    if dual_call.get("accuracy_tags"):
        readings["accuracy_tags"] = list(dual_call.get("accuracy_tags") or [])
    readings["proven_100"] = track == "proven_100"
    readings["history_eligible"] = True
    readings["priority"] = 100 if track == "proven_100" else 80
    readings["live_confluence"] = False
    readings["good"] = False
    tags = list(readings.get("accuracy_tags") or [])
    tags.insert(
        0,
        {
            "code": STACK_TAG_CODE,
            "label": f"Stacked · {track}",
            "detail": (
                f"Listed via {STACK_TRACK} priority · research "
                f"~{STACK_HIT_PCT_6M:.0f}% 6m / ~{STACK_HIT_PCT_1Y:.0f}% 1y"
            ),
            "expected_hit_pct": STACK_HIT_PCT_1Y,
            "tone": "good",
            "priority": 10,
        },
    )
    if enable_nse_mid_gate():
        readings["nse_mid_gate"] = True
        tags.insert(
            0,
            {
                "code": NSE_MID_TAG_CODE,
                "label": "NSE mid · AbsChangePct",
                "detail": (
                    "Frozen Nov prior-day AbsChangePct mid [0.6276,1.6866)"
                ),
                "expected_hit_pct": STACK_HIT_PCT_1Y + NSE_MID_HIT_LIFT_5Y,
                "tone": "good",
                "priority": 8,
            },
        )
    readings["accuracy_tags"] = tags
    # Clean + accuracy band for quality morning dual listings (mins on payload).
    # NSE mid / candle confirms are enriched later in fno_ws_rescore with live context.
    try:
        import fno_clean_call_tags as clean_tags

        clean_tags.enrich_readings_clean(
            readings,
            dual_call=dual_call,
            asof=dual_call.get("bars_asof") or dual_call.get("taken_at"),
        )
        if readings.get("clean") and dual_call.get("accuracy_label"):
            readings["accuracy_label"] = dual_call.get("accuracy_label")
            readings["accuracy_tags"] = list(
                dual_call.get("accuracy_tags") or readings.get("accuracy_tags") or []
            )
    except Exception:
        pass
    return readings
