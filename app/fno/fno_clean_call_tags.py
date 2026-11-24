"""Clean-call tags for live NIFTY quality listings.

Two research streams (tagging only — does not change list gates):

1) Morning clean (≤11:00): quality + morning → ~95–100% band
2) Clean multi (winner): quality · p≥0.55 · candle∨overlay · any session
   → ~84% hit / ~78% day-align · more calls (cap2 research)

User sees clear Clean / Clean multi + accuracy tags on the desk.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

# Morning sparse stream — nifty_clean_calls_live_verify (2026-11-13)
CLEAN_RESEARCH: Dict[str, Dict[str, float]] = {
    "qm_only": {
        "hit_6m": 100.0,
        "hit_1y": 97.78,
        "hit_2y": 97.33,
        "n_6m": 26,
        "n_1y": 45,
        "n_2y": 75,
    },
    "qm_p70": {
        "hit_6m": 100.0,
        "hit_1y": 100.0,
        "hit_2y": 100.0,
        "n_6m": 18,
        "n_1y": 25,
        "n_2y": 34,
    },
    "qm_candle_agree": {
        "hit_6m": 100.0,
        "hit_1y": 100.0,
        "hit_2y": 100.0,
        "n_6m": 11,
        "n_1y": 22,
        "n_2y": 33,
    },
    "qm_p70_candle": {
        "hit_6m": 100.0,
        "hit_1y": 100.0,
        "hit_2y": 100.0,
        "n_6m": 8,
        "n_1y": 11,
        "n_2y": 16,
    },
    "qm_nse_mid": {
        "hit_6m": 100.0,
        "hit_1y": 100.0,
        "hit_2y": 100.0,
        "n_6m": 5,
        "n_1y": 7,
        "n_2y": 15,
    },
}

# Winner — nifty_clean_more_calls_best (qc|all|p≥0.55|candle_or_ov|cap2)
CLEAN_MULTI_RESEARCH = {
    "recipe": "qc_p55_candle_or_ov_cap2",
    "hit_6m": 85.5,
    "hit_1y": 86.3,
    "hit_2y": 84.3,
    "align_6m": 67.3,
    "align_1y": 72.5,
    "align_2y": 77.5,
    "n_6m": 55,
    "n_1y": 102,
    "n_2y": 204,
    "against_2y": 5.4,
}

QUALITY_TRACKS = frozenset(
    {
        "proven_100",
        "champion",
        "crown_5m",
        "5m_crown",
        "crown",
        "soft_crown",
    }
)
MORNING_MAX_MINS = 11 * 60  # 11:00 IST
CLEAN_MULTI_P_MIN = 0.55
CLEAN_BAND_LABEL = "95–100%"
CLEAN_TAG_CODE = "clean"
CLEAN_ACC_TAG_CODE = "clean_accuracy"
CLEAN_MULTI_TAG_CODE = "clean_multi"
CLEAN_MULTI_ACC_TAG_CODE = "clean_multi_accuracy"


def _ist_mins(asof: Any = None, mins: Any = None) -> Optional[int]:
    if mins is not None:
        try:
            return int(mins)
        except (TypeError, ValueError):
            pass
    if asof is None:
        return None
    try:
        import fno_session_rules as fsrules

        dt = fsrules.as_ist(asof)
        if dt is None:
            return None
        return int(dt.hour) * 60 + int(dt.minute)
    except Exception:
        try:
            s = str(asof)
            if "T" in s:
                hm = s.split("T", 1)[1][:5]
            else:
                hm = s[11:16] if len(s) >= 16 else ""
            if len(hm) == 5 and hm[2] == ":":
                return int(hm[:2]) * 60 + int(hm[3:5])
        except Exception:
            return None
    return None


def is_morning(*, asof: Any = None, mins: Any = None) -> bool:
    m = _ist_mins(asof, mins)
    return m is not None and m <= MORNING_MAX_MINS


def is_quality_track(track: Any) -> bool:
    return str(track or "").strip().lower() in {t.lower() for t in QUALITY_TRACKS}


def _candle_agrees(decision: str, candle_bias: Any) -> bool:
    bias = str(candle_bias or "").upper()
    side = str(decision or "").upper()
    if side == "BUY":
        return bias in ("BULLISH", "BUY", "LONG")
    if side == "SELL":
        return bias in ("BEARISH", "SELL", "SHORT")
    return False


def _side_from_row(row: Any) -> str:
    if not isinstance(row, dict):
        return ""
    for k in ("decision", "side", "direction"):
        s = str(row.get(k) or "").upper()
        if "BUY" in s or s == "LONG":
            return "BUY"
        if "SELL" in s or s == "SHORT":
            return "SELL"
    return ""


def overlay_agrees(
    decision: str,
    *,
    overlay_agree: Any = None,
    overlay_bias: Any = None,
    overlay_today: Any = None,
    overlay_sig: Any = None,
    snap: Any = None,
) -> bool:
    """True if overlay lean matches call side (live desk context)."""
    side = str(decision or "").upper()
    if overlay_agree is not None and not isinstance(overlay_agree, (list, dict)):
        return bool(overlay_agree)
    if isinstance(overlay_agree, dict) and side in ("BUY", "SELL"):
        if side == "BUY" and overlay_agree.get("ov_buy"):
            return True
        if side == "SELL" and overlay_agree.get("ov_sell"):
            return True
    bias = str(overlay_bias or "").upper()
    if side == "BUY" and bias in ("BULLISH", "BUY", "LONG"):
        return True
    if side == "SELL" and bias in ("BEARISH", "SELL", "SHORT"):
        return True
    rows: List[Any] = []
    if isinstance(overlay_today, list):
        rows.extend(overlay_today)
    if isinstance(snap, dict):
        for k in ("overlay_indication_today", "overlay_indication_open"):
            v = snap.get(k)
            if isinstance(v, list):
                rows.extend(v)
        if overlay_sig is None:
            overlay_sig = snap.get("overlay_indication")
    if isinstance(overlay_sig, dict):
        rows.append(overlay_sig)
    for r in rows:
        if _side_from_row(r) == side:
            return True
    return False


def _nse_mid_ok(asof: Any = None, nse_mid: Any = None) -> bool:
    if isinstance(nse_mid, dict):
        if "allow" in nse_mid:
            return bool(nse_mid.get("allow"))
        if "pass" in nse_mid:
            return bool(nse_mid.get("pass"))
    try:
        import fno_nse_mid_gate as nse_gate

        if not nse_gate.enabled():
            return False
        return bool(nse_gate.passes(asof).get("allow"))
    except Exception:
        return False


def classify_clean_morning(
    *,
    track: Any,
    decision: str,
    p_t1: Any = None,
    asof: Any = None,
    mins: Any = None,
    candle_bias: Any = None,
    nse_mid: Any = None,
) -> Optional[Dict[str, Any]]:
    """Quality + morning ≤11:00 → sparse ~95–100% clean."""
    if not is_quality_track(track):
        return None
    if not is_morning(asof=asof, mins=mins):
        return None
    try:
        p = float(p_t1) if p_t1 is not None else 0.0
    except (TypeError, ValueError):
        p = 0.0
    p70 = p >= 0.70
    candle_ok = _candle_agrees(decision, candle_bias)
    nse_ok = _nse_mid_ok(asof=asof, nse_mid=nse_mid)

    if nse_ok:
        recipe = "qm_nse_mid"
        short = "Clean morning · NSE mid"
    elif p70 and candle_ok:
        recipe = "qm_p70_candle"
        short = "Clean morning · High conf + candle"
    elif candle_ok:
        recipe = "qm_candle_agree"
        short = "Clean morning · Candle"
    elif p70:
        recipe = "qm_p70"
        short = "Clean morning · High conf"
    else:
        recipe = "qm_only"
        short = "Clean morning"

    stats = CLEAN_RESEARCH[recipe]
    hit_1y = float(stats["hit_1y"])
    accuracy_label = f"{short} · Accuracy {CLEAN_BAND_LABEL}"
    if hit_1y >= 99.5:
        accuracy_label = f"{short} · Accuracy ~100%"
    detail = (
        f"Research quality+morning ({recipe}) · "
        f"6m {stats['hit_6m']:.0f}% (n={int(stats['n_6m'])}) · "
        f"1y {stats['hit_1y']:.1f}% (n={int(stats['n_1y'])}) · "
        f"2y {stats['hit_2y']:.1f}% (n={int(stats['n_2y'])})"
    )
    return {
        "clean": True,
        "clean_kind": "morning",
        "recipe": recipe,
        "short": short,
        "accuracy_label": accuracy_label,
        "accuracy_band": CLEAN_BAND_LABEL,
        "expected_hit_pct": hit_1y,
        "hit_6m": float(stats["hit_6m"]),
        "hit_1y": hit_1y,
        "hit_2y": float(stats["hit_2y"]),
        "align_2y": None,
        "p70": p70,
        "candle_agree": candle_ok,
        "overlay_agree": False,
        "nse_mid": nse_ok,
        "morning": True,
        "detail": detail,
    }


def classify_clean_multi(
    *,
    track: Any,
    decision: str,
    p_t1: Any = None,
    candle_bias: Any = None,
    overlay_agree: Any = None,
    overlay_bias: Any = None,
    overlay_today: Any = None,
    overlay_sig: Any = None,
    snap: Any = None,
) -> Optional[Dict[str, Any]]:
    """Quality · p≥0.55 · candle OR overlay · any session (more calls winner)."""
    if not is_quality_track(track):
        return None
    try:
        p = float(p_t1) if p_t1 is not None else 0.0
    except (TypeError, ValueError):
        p = 0.0
    if p < CLEAN_MULTI_P_MIN:
        return None
    candle_ok = _candle_agrees(decision, candle_bias)
    ov_ok = overlay_agrees(
        decision,
        overlay_agree=overlay_agree,
        overlay_bias=overlay_bias,
        overlay_today=overlay_today,
        overlay_sig=overlay_sig,
        snap=snap,
    )
    if not (candle_ok or ov_ok):
        return None

    st = CLEAN_MULTI_RESEARCH
    confirm = (
        "candle+overlay"
        if candle_ok and ov_ok
        else ("candle" if candle_ok else "overlay")
    )
    short = "Clean multi"
    accuracy_label = (
        f"Clean multi · ~{st['hit_2y']:.0f}% hit · ~{st['align_2y']:.0f}% day-align"
    )
    detail = (
        f"Research {st['recipe']} · quality p≥{CLEAN_MULTI_P_MIN} · "
        f"confirm={confirm} (candle∨overlay) · "
        f"6m {st['hit_6m']:.0f}% hit / {st['align_6m']:.0f}% align (n={st['n_6m']}) · "
        f"1y {st['hit_1y']:.0f}% / {st['align_1y']:.0f}% (n={st['n_1y']}) · "
        f"2y {st['hit_2y']:.0f}% / {st['align_2y']:.0f}% (n={st['n_2y']}) · "
        f"against {st['against_2y']:.0f}% · day cap 2 research"
    )
    return {
        "clean": True,
        "clean_kind": "multi",
        "recipe": st["recipe"],
        "short": short,
        "accuracy_label": accuracy_label,
        "accuracy_band": f"~{st['hit_2y']:.0f}%",
        "expected_hit_pct": float(st["hit_2y"]),
        "hit_6m": float(st["hit_6m"]),
        "hit_1y": float(st["hit_1y"]),
        "hit_2y": float(st["hit_2y"]),
        "align_2y": float(st["align_2y"]),
        "p70": p >= 0.70,
        "candle_agree": candle_ok,
        "overlay_agree": ov_ok,
        "confirm": confirm,
        "nse_mid": False,
        "morning": False,
        "detail": detail,
    }


# Back-compat alias
def classify_clean(**kwargs: Any) -> Optional[Dict[str, Any]]:
    return classify_clean_morning(**kwargs)


def build_clean_tags(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Tags for desk pills — kind-specific Clean + accuracy."""
    kind = str(meta.get("clean_kind") or "morning")
    recipe = str(meta.get("recipe") or "")
    hit = float(meta.get("expected_hit_pct") or meta.get("hit_2y") or meta.get("hit_1y") or 0)
    if kind == "multi":
        align = meta.get("align_2y")
        return [
            {
                "code": CLEAN_MULTI_TAG_CODE,
                "label": "Clean multi",
                "detail": str(meta.get("detail") or ""),
                "expected_hit_pct": hit,
                "tone": "proven",
                "priority": 3,
                "clean": True,
                "clean_multi": True,
                "recipe": recipe,
            },
            {
                "code": CLEAN_MULTI_ACC_TAG_CODE,
                "label": (
                    f"~{hit:.0f}% hit · ~{float(align):.0f}% align"
                    if align is not None
                    else f"Accuracy ~{hit:.0f}%"
                ),
                "detail": str(meta.get("detail") or ""),
                "expected_hit_pct": hit,
                "tone": "champion",
                "priority": 4,
                "clean": True,
                "clean_multi": True,
                "recipe": recipe,
            },
        ]
    band = str(meta.get("accuracy_band") or CLEAN_BAND_LABEL)
    return [
        {
            "code": CLEAN_TAG_CODE,
            "label": "Clean morning",
            "detail": str(meta.get("detail") or ""),
            "expected_hit_pct": hit,
            "tone": "proven",
            "priority": 4,
            "clean": True,
            "recipe": recipe,
        },
        {
            "code": CLEAN_ACC_TAG_CODE,
            "label": f"Accuracy {band}" if hit < 99.5 else "Accuracy ~100%",
            "detail": str(meta.get("detail") or ""),
            "expected_hit_pct": hit,
            "tone": "proven",
            "priority": 5,
            "clean": True,
            "recipe": recipe,
        },
    ]


_CLEAN_CODES = frozenset(
    {
        CLEAN_TAG_CODE,
        CLEAN_ACC_TAG_CODE,
        CLEAN_MULTI_TAG_CODE,
        CLEAN_MULTI_ACC_TAG_CODE,
    }
)


def _strip_prior_clean(tags: Sequence[Any]) -> List[Any]:
    out: List[Any] = []
    for t in tags or []:
        if not isinstance(t, dict):
            out.append(t)
            continue
        code = str(t.get("code") or "").lower()
        if code in _CLEAN_CODES or t.get("clean") or t.get("clean_multi"):
            continue
        out.append(t)
    return out


def merge_clean_tags(
    tags: Optional[Sequence[Any]],
    *metas: Optional[Dict[str, Any]],
) -> List[Any]:
    base = _strip_prior_clean(list(tags or []))
    built: List[Any] = []
    for meta in metas:
        if meta:
            built.extend(build_clean_tags(meta))
    return built + base


def stamp_clean(
    payload: Any,
    *,
    asof: Any = None,
    mins: Any = None,
    candle_bias: Any = None,
    nse_mid: Any = None,
    overlay_agree: Any = None,
    overlay_bias: Any = None,
    overlay_today: Any = None,
    overlay_sig: Any = None,
    snap: Any = None,
    track: Any = None,
    decision: Any = None,
    p_t1: Any = None,
) -> Optional[Dict[str, Any]]:
    """Mutate call/readings with Clean morning and/or Clean multi tags."""
    if not isinstance(payload, dict):
        return None
    tr = track if track is not None else payload.get("track") or payload.get("source")
    side = str(
        decision
        if decision is not None
        else payload.get("decision")
        or (payload.get("model_view") or {}).get("side")
        or ""
    ).upper()
    p = p_t1
    if p is None:
        p = payload.get("p_t1")
        if p is None:
            p = (payload.get("model_view") or {}).get("p_t1")
    use_mins = mins
    if use_mins is None:
        use_mins = payload.get("mins")
        if use_mins is None:
            use_mins = (payload.get("model_view") or {}).get("mins")
        if use_mins is None:
            use_mins = (payload.get("or_state") or {}).get("mins")
    use_candle = (
        candle_bias if candle_bias is not None else payload.get("candle_bias")
    )

    morning_meta = classify_clean_morning(
        track=tr,
        decision=side,
        p_t1=p,
        asof=asof,
        mins=use_mins,
        candle_bias=use_candle,
        nse_mid=nse_mid if nse_mid is not None else payload.get("nse_mid"),
    )
    multi_meta = classify_clean_multi(
        track=tr,
        decision=side,
        p_t1=p,
        candle_bias=use_candle,
        overlay_agree=overlay_agree
        if overlay_agree is not None
        else payload.get("overlay_agree"),
        overlay_bias=overlay_bias,
        overlay_today=overlay_today,
        overlay_sig=overlay_sig,
        snap=snap,
    )

    if not morning_meta and not multi_meta:
        payload.pop("clean", None)
        payload.pop("clean_multi", None)
        payload.pop("clean_recipe", None)
        payload.pop("clean_meta", None)
        payload.pop("clean_kind", None)
        if "accuracy_tags" in payload:
            payload["accuracy_tags"] = _strip_prior_clean(
                payload.get("accuracy_tags") or []
            )
        return None

    # Lead with multi when both (clearer volume stream); morning tags still attached.
    primary = multi_meta or morning_meta
    assert primary is not None
    tags = merge_clean_tags(
        payload.get("accuracy_tags") or payload.get("tags"),
        multi_meta,
        morning_meta,
    )
    payload["accuracy_tags"] = tags
    if "tags" in payload:
        payload["tags"] = tags
    payload["clean"] = True
    payload["clean_multi"] = bool(multi_meta)
    payload["clean_morning"] = bool(morning_meta)
    payload["clean_kind"] = primary["clean_kind"]
    payload["clean_recipe"] = primary["recipe"]
    payload["clean_meta"] = {
        "primary": primary,
        "morning": morning_meta,
        "multi": multi_meta,
    }
    payload["accuracy_band"] = primary["accuracy_band"]

    prior = str(payload.get("accuracy_label") or "").strip()
    clean_label = str(primary["accuracy_label"])
    # If both, prefer multi headline but note morning
    if multi_meta and morning_meta:
        clean_label = (
            f"{multi_meta['accuracy_label']} · also Clean morning"
        )
    if prior and "clean" not in prior.lower() and prior.lower() not in clean_label.lower():
        payload["accuracy_label"] = f"{clean_label} · {prior}"
    else:
        payload["accuracy_label"] = clean_label

    try:
        cur = float(payload.get("expected_hit_pct") or 0)
    except (TypeError, ValueError):
        cur = 0.0
    # Prefer higher research hit for display when morning (~98) beats multi (~84)
    best_hit = max(
        float(morning_meta["expected_hit_pct"]) if morning_meta else 0.0,
        float(multi_meta["expected_hit_pct"]) if multi_meta else 0.0,
    )
    if best_hit >= cur:
        payload["expected_hit_pct"] = best_hit

    mv = payload.get("model_view")
    if isinstance(mv, dict):
        mv = dict(mv)
        mv["clean"] = True
        mv["clean_multi"] = bool(multi_meta)
        mv["clean_morning"] = bool(morning_meta)
        mv["clean_recipe"] = primary["recipe"]
        mv["expected_hit_pct"] = best_hit
        msg = str(mv.get("message") or "")
        prefix = f"{primary['short']} ({primary['accuracy_label']}). "
        if "Clean" not in msg[:48]:
            mv["message"] = prefix + msg
        payload["model_view"] = mv
    return primary


def enrich_readings_clean(
    readings: Any,
    *,
    dual_call: Any = None,
    asof: Any = None,
    candle_bias: Any = None,
    nse_mid: Any = None,
    overlay_agree: Any = None,
    overlay_bias: Any = None,
    overlay_today: Any = None,
    overlay_sig: Any = None,
    snap: Any = None,
) -> Any:
    """Stamp clean morning + clean multi tags onto live readings / dual_call."""
    if not isinstance(dual_call, dict) and not isinstance(readings, dict):
        return readings
    stamp_kwargs = dict(
        asof=asof,
        candle_bias=candle_bias,
        nse_mid=nse_mid,
        overlay_agree=overlay_agree,
        overlay_bias=overlay_bias,
        overlay_today=overlay_today,
        overlay_sig=overlay_sig,
        snap=snap,
    )
    meta = None
    if isinstance(dual_call, dict):
        meta = stamp_clean(dual_call, **stamp_kwargs)
    if isinstance(readings, dict):
        if meta or is_quality_track(readings.get("track") or readings.get("source")):
            stamp_clean(
                readings,
                mins=(dual_call or {}).get("mins")
                if isinstance(dual_call, dict)
                else readings.get("mins"),
                track=(dual_call or {}).get("track")
                if isinstance(dual_call, dict)
                else readings.get("track"),
                decision=(dual_call or {}).get("decision")
                if isinstance(dual_call, dict)
                else readings.get("decision"),
                p_t1=(dual_call or {}).get("p_t1")
                if isinstance(dual_call, dict)
                else readings.get("p_t1"),
                **stamp_kwargs,
            )
            if isinstance(dual_call, dict) and dual_call.get("clean"):
                for k in (
                    "clean",
                    "clean_multi",
                    "clean_morning",
                    "clean_recipe",
                    "clean_meta",
                    "clean_kind",
                    "accuracy_label",
                    "accuracy_band",
                ):
                    if k in dual_call:
                        readings[k] = dual_call.get(k)
                readings["accuracy_tags"] = list(
                    dual_call.get("accuracy_tags")
                    or readings.get("accuracy_tags")
                    or []
                )
    return readings
