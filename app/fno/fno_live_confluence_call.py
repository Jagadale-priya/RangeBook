"""Accurate live-confluence calls when the model HOLDs (lower priority).

Design (research-backed, paper-trade oriented)
---------------------------------------------
Classic pattern literature and ORB practice agree on the same idea: a shape
alone is weak; a *confirmed break* plus independent agreement is what you trade.

- Double top/bottom: act on neckline *break* (close through), not on forming
  shapes. Soft Fib/testing zones are not entries (common whipsaw source).
- ORB: trade a break that agrees with short-horizon lean + candle/micro, with
  stop beyond the opposite OR edge or ATR — not a tick poke.
- Multi-factor confluence (MTF lean + candle + micro/checklist) filters noise
  better than any single pattern score.

Two entry paths (model BUY/SELL always wins first):
  A) Pattern-break — W / M / ORB *broken*, plus >=2 independent confirms
  B) Momentum — strong 5m lean + hard break + candle/micro confirm

Today-only in History UI; tagged so paper results can be reviewed later.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import fno_risk_engine

# Path B (momentum) — only strong, accurate tape moves
MIN_AGREE_MOM = 4
MIN_WEIGHT_MOM = 7
MIN_P_SIDE_MOM = 0.74

# Path A (pattern-break) — hard W/M/ORB break + strong lean + price action
MIN_CONFIRM_A = 3
MIN_P_SIDE_A = 0.68

MIN_CANDLE_DELTA = 6.0
MIN_MICRO_BUY = 64.0
MIN_MICRO_SELL = 36.0
MIN_CHECKLIST_MARGIN = 2
STOP_ATR = 1.5
T1_ATR = 1.5
MIN_STOP_PTS = 25.0

HARD_STRUCTURE_PREFIXES = ("orb_", "w_", "m_")

# Index peers must not fight the live side (avoids NIFTY BUY vs BANKNIFTY SELL).
INDEX_PEERS = {
    "NIFTY": ("BANKNIFTY", "SENSEX"),
    "BANKNIFTY": ("NIFTY", "SENSEX"),
    "SENSEX": ("NIFTY", "BANKNIFTY"),
}
PEER_LEAN_MIN_P = 0.60


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _side_from_lean(lean: Any) -> Optional[str]:
    L = str(lean or "").upper()
    if L in ("BULLISH", "UP", "BUY"):
        return "BUY"
    if L in ("BEARISH", "DOWN", "SELL"):
        return "SELL"
    return None


def _levels(
    side: str,
    price: float,
    atr: float,
    *,
    orb: Optional[Dict[str, Any]] = None,
    pattern: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[float], Optional[float]]:
    if atr <= 0 or price <= 0:
        return None, None
    atr_sl = max(MIN_STOP_PTS, round(STOP_ATR * atr, 1))
    atr_t1 = max(MIN_STOP_PTS, round(T1_ATR * atr, 1))
    sl_pts = atr_sl
    t1_pts = atr_t1

    # Prefer structural stop: beyond opposite OR edge or pattern extreme.
    if isinstance(orb, dict) and orb.get("available"):
        hi = _f(orb.get("or_high") or orb.get("high"))
        lo = _f(orb.get("or_low") or orb.get("low"))
        if hi is not None and lo is not None and hi > lo:
            if side == "BUY" and lo < price:
                sl_pts = max(sl_pts, round(price - lo + max(atr * 0.15, 4.0), 1))
            if side == "SELL" and hi > price:
                sl_pts = max(sl_pts, round(hi - price + max(atr * 0.15, 4.0), 1))

    if isinstance(pattern, dict):
        trig = _f(pattern.get("trigger") or pattern.get("neckline"))
        hi2 = _f(pattern.get("high_2") or pattern.get("high_1"))
        lo2 = _f(pattern.get("low_2") or pattern.get("low_1"))
        if side == "BUY" and lo2 is not None and lo2 < price:
            sl_pts = max(sl_pts, round(price - lo2 + max(atr * 0.1, 3.0), 1))
        if side == "SELL" and hi2 is not None and hi2 > price:
            sl_pts = max(sl_pts, round(hi2 - price + max(atr * 0.1, 3.0), 1))
        if side == "BUY" and trig is not None and trig < price:
            # Neckline retest buffer for W/ORB high break.
            pass
        if side == "SELL" and trig is not None and trig > price:
            pass

    # Cap extreme stops so paper size stays sane (3.5 ATR).
    sl_pts = min(sl_pts, max(MIN_STOP_PTS, round(3.5 * atr, 1)))
    if side == "BUY":
        return round(price - sl_pts, 2), round(price + t1_pts, 2)
    return round(price + sl_pts, 2), round(price - t1_pts, 2)


def _is_soft_noise(pat: Dict[str, Any]) -> bool:
    key = str(pat.get("key") or "").lower()
    name = str(pat.get("name") or "").lower()
    status = str(pat.get("status") or "").lower()
    if key.startswith("fib_") or "fibonacci" in name or "fib " in name:
        return True
    if status in ("testing", "forming", "at_zone"):
        return True
    if key.startswith("ema9_touch") or key.startswith("candle_"):
        return True
    return False


def _hard_pattern(pat: Dict[str, Any]) -> bool:
    """True for tradable structure: W/M/ORB *broken* (research: break, not form)."""
    if _is_soft_noise(pat):
        return False
    status = str(pat.get("status") or "").lower()
    if status != "broken":
        return False
    key = str(pat.get("key") or "").lower()
    name = str(pat.get("name") or "").lower()
    if any(key.startswith(p) for p in HARD_STRUCTURE_PREFIXES):
        return True
    if "orb" in key or "neck" in key or "double top" in name or "double bottom" in name:
        return True
    if name.startswith("w ") or name.startswith("m ") or "w ·" in name or "m ·" in name:
        return True
    return False


def live_cooldown_block(
    session_ticket: Optional[Dict[str, Any]],
    *,
    asof: Any = None,
) -> Optional[str]:
    """Only block while a listed call is still open.

    No daily cap, no post-SL ban, no time cooldown — user may skip clips;
    we still surface every accurate indication. One open ticket at a time
    (desk persist also enforces that).
    """
    del asof  # reserved for future clock filters; unused on purpose
    if not isinstance(session_ticket, dict):
        return None
    if str(session_ticket.get("status") or "") == "open" and str(
        session_ticket.get("decision") or ""
    ) not in ("", "HOLD", "None"):
        return "A call is already open — next live indication waits until it closes."
    return None


def _peer_side_from_snap(snap: Optional[Dict[str, Any]]) -> Tuple[Optional[str], float, str]:
    """Return (BUY/SELL/None, confidence, source) from a peer snapshot."""
    if not isinstance(snap, dict):
        return None, 0.0, ""
    ticket = snap.get("session_ticket") if isinstance(snap.get("session_ticket"), dict) else {}
    if str(ticket.get("status") or "") == "open":
        dec = str(ticket.get("decision") or "").upper()
        if dec in ("BUY", "SELL"):
            return dec, 1.0, "open_call"
    fa = snap.get("fno_analysis") if isinstance(snap.get("fno_analysis"), dict) else {}
    sh = fa.get("short_horizon") if isinstance(fa.get("short_horizon"), dict) else {}
    if not sh:
        sh = snap.get("short_horizon") if isinstance(snap.get("short_horizon"), dict) else {}
    sh_side = str(sh.get("side") or "").upper()
    p = _f(sh.get("p_side")) or 0.0
    if sh_side == "UP" and p >= PEER_LEAN_MIN_P:
        return "BUY", p, "short_horizon"
    if sh_side == "DOWN" and p >= PEER_LEAN_MIN_P:
        return "SELL", p, "short_horizon"
    micro = ((fa.get("live_context") or snap.get("live_context") or {}).get("microstructure") or {})
    if isinstance(micro, dict):
        m_side = _side_from_lean(micro.get("micro_bias"))
        ms = _f(micro.get("micro_score"))
        if m_side == "BUY" and ms is not None and ms >= MIN_MICRO_BUY:
            return "BUY", ms / 100.0, "micro"
        if m_side == "SELL" and ms is not None and ms <= MIN_MICRO_SELL:
            return "SELL", (100.0 - ms) / 100.0, "micro"
    return None, 0.0, ""


def peer_coherence_block(
    symbol: Optional[str],
    side: str,
) -> Optional[str]:
    """Block live listing when peer indices already lean / call the opposite way.

    Stops confusing desks where NIFTY live BUY fights BANKNIFTY live SELL.
    """
    key = str(symbol or "").strip().upper()
    peers = INDEX_PEERS.get(key)
    if not peers or side not in ("BUY", "SELL"):
        return None
    opposite = "SELL" if side == "BUY" else "BUY"
    fights: List[str] = []
    try:
        import fno_ws_rescore
    except Exception:
        return None
    for peer in peers:
        try:
            snap = fno_ws_rescore.get_snapshot(peer)
        except Exception:
            snap = None
        peer_side, conf, src = _peer_side_from_snap(snap)
        if peer_side == opposite:
            fights.append(f"{peer} {peer_side} via {src} ({conf:.0%})")
    if len(fights) >= 1 and any("open_call" in f for f in fights):
        return (
            f"Peer index already has the opposite live call — "
            f"{'; '.join(fights)}. Wait for coherence."
        )
    if len(fights) >= 2:
        return (
            f"Peer indices lean against this {side} — "
            f"{'; '.join(fights)}. Live call blocked for coherence."
        )
    return None


def _pattern_list(structure_scan: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scan = structure_scan or {}
    out: List[Dict[str, Any]] = []
    top = scan.get("top") if isinstance(scan.get("top"), dict) else None
    if top:
        out.append(top)
    for p in (scan.get("patterns") or [])[:10]:
        if isinstance(p, dict) and (not top or p.get("key") != top.get("key")):
            out.append(p)
    return out


def _collect_confirms(
    *,
    side: str,
    short_horizon: Optional[Dict[str, Any]],
    indications: Optional[Dict[str, Any]],
    live_context: Optional[Dict[str, Any]],
    candlestick: Optional[Dict[str, Any]],
    min_p_side: float,
    min_micro_buy: float = MIN_MICRO_BUY,
    min_micro_sell: float = MIN_MICRO_SELL,
    min_candle_delta: float = MIN_CANDLE_DELTA,
    min_checklist_margin: int = MIN_CHECKLIST_MARGIN,
) -> List[Dict[str, Any]]:
    """Independent non-structure confirms for a chosen side."""
    votes: List[Dict[str, Any]] = []
    sh = short_horizon or {}
    sh_side = str(sh.get("side") or "").upper()
    p_side = _f(sh.get("p_side")) or 0.0
    want = "UP" if side == "BUY" else "DOWN"
    if sh_side == want and p_side >= min_p_side:
        votes.append({
            "id": "short_horizon",
            "side": side,
            "label": f"5m lean {sh_side} {int(round(p_side * 100))}%",
            "detail": sh.get("headline") or "",
            "weight": 3 if p_side >= 0.72 else 2,
            "hard": False,
            "confirm": True,
            "p_side": p_side,
        })

    ind = indications or {}
    summary = ind.get("summary") if isinstance(ind, dict) else None
    if isinstance(summary, dict):
        lean_side = _side_from_lean(summary.get("lean"))
        bull = int(summary.get("bullish") or 0)
        bear = int(summary.get("bearish") or 0)
        margin = (bull - bear) if side == "BUY" else (bear - bull)
        if lean_side == side and margin >= min_checklist_margin and (bull + bear) >= 6:
            votes.append({
                "id": "checklist",
                "side": lean_side,
                "label": f"Checklist {bull}↑/{bear}↓",
                "detail": f"Live checklist leans {lean_side}.",
                "weight": 2 if margin >= 4 else 1,
                "hard": False,
                "confirm": True,
            })

    live = live_context or {}
    micro = live.get("microstructure") or {}
    micro_side = _side_from_lean(micro.get("micro_bias"))
    ms = _f(micro.get("micro_score"))
    if micro_side == side and ms is not None:
        ok = (side == "BUY" and ms >= min_micro_buy) or (side == "SELL" and ms <= min_micro_sell)
        if ok:
            votes.append({
                "id": "micro",
                "side": micro_side,
                "label": f"Micro {micro.get('micro_bias')} ({ms:.0f})",
                "detail": "Microstructure agrees.",
                "weight": 2 if abs(ms - 50) >= 18 else 1,
                "hard": False,
                "confirm": True,
            })

    candle = candlestick if isinstance(candlestick, dict) else None
    if not candle:
        candle = micro.get("micro_candlestick_15m") or micro.get("micro_candlestick")
    if isinstance(candle, dict):
        c_side = _side_from_lean(candle.get("bias"))
        delta = abs(_f(candle.get("score_delta")) or 0)
        pats = candle.get("patterns") or []
        if c_side == side and (delta >= min_candle_delta or (pats and delta >= 3)):
            name = pats[0] if pats else f"Candle {candle.get('bias')}"
            votes.append({
                "id": "candle",
                "side": c_side,
                "label": str(name)[:48],
                "detail": f"Candle bias {candle.get('bias')} (score {candle.get('score_delta')}).",
                "weight": 3 if delta >= 7 else 2,
                "hard": False,
                "confirm": True,
            })

    return votes


def _hard_votes(
    structure_scan: Optional[Dict[str, Any]],
    live_context: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    votes: List[Dict[str, Any]] = []
    for pat in _pattern_list(structure_scan):
        if not _hard_pattern(pat):
            continue
        lean_side = _side_from_lean(pat.get("lean"))
        if not lean_side:
            continue
        score = int(pat.get("score") or 0)
        votes.append({
            "id": str(pat.get("key") or "structure"),
            "side": lean_side,
            "label": str(pat.get("name") or pat.get("key") or "Structure"),
            "detail": str(pat.get("note") or ""),
            "weight": 3 if score >= 3 else 2,
            "trigger": pat.get("trigger") or pat.get("neckline"),
            "hard": True,
            "confirm": False,
            "pattern": pat,
        })

    live = live_context or {}
    micro = live.get("microstructure") or {}
    orb = micro.get("opening_range") if isinstance(micro.get("opening_range"), dict) else {}
    if orb.get("available") and orb.get("broken"):
        orb_side = _side_from_lean(orb.get("bias"))
        # Avoid double-counting if structure_scan already has orb_*
        already = {v.get("id") for v in votes}
        if orb_side and "orb_high" not in already and "orb_low" not in already and "orb_break" not in already:
            votes.append({
                "id": "orb_break",
                "side": orb_side,
                "label": "ORB break",
                "detail": f"Opening-range break to the {orb_side} side.",
                "weight": 3,
                "trigger": orb.get("or_high") if orb_side == "BUY" else orb.get("or_low"),
                "hard": True,
                "confirm": False,
                "pattern": {
                    "key": "orb_break",
                    "high_1": orb.get("or_high"),
                    "low_1": orb.get("or_low"),
                    "trigger": orb.get("or_high") if orb_side == "BUY" else orb.get("or_low"),
                },
            })
    return votes


def _against_count(
    side: str,
    *,
    short_horizon: Optional[Dict[str, Any]],
    indications: Optional[Dict[str, Any]],
    live_context: Optional[Dict[str, Any]],
    candlestick: Optional[Dict[str, Any]],
) -> int:
    """How many independent reads fight the trade side."""
    other = "SELL" if side == "BUY" else "BUY"
    fights = _collect_confirms(
        side=other,
        short_horizon=short_horizon,
        indications=indications,
        live_context=live_context,
        candlestick=candlestick,
        min_p_side=0.58,
    )
    return len(fights)


def _build_payload(
    *,
    side: str,
    price: float,
    agree: List[Dict[str, Any]],
    path: str,
    short_horizon: Optional[Dict[str, Any]],
    live_context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    live = live_context or {}
    micro = live.get("microstructure") or {}
    orb = micro.get("opening_range") if isinstance(micro.get("opening_range"), dict) else {}
    hard_pat = next((v.get("pattern") for v in agree if v.get("hard") and v.get("pattern")), None)
    atr = fno_risk_engine.bar_atr(live.get("bars_5m")) or fno_risk_engine.bar_atr(live.get("bars_15m"))
    atr_v = _f(atr) or max(price * 0.002, MIN_STOP_PTS)
    sl, t1 = _levels(side, price, float(atr_v), orb=orb, pattern=hard_pat if isinstance(hard_pat, dict) else None)
    if sl is None or t1 is None:
        raise ValueError("levels")

    sh = short_horizon or {}
    sh_p = _f(sh.get("p_side")) or 0.0
    want = "UP" if side == "BUY" else "DOWN"
    if str(sh.get("side") or "").upper() == want and sh_p > 0:
        p_side = sh_p
    else:
        total_w = sum(int(v.get("weight") or 1) for v in agree) or 1
        p_side = 0.58 + 0.2 * min(1.0, total_w / 8.0)
    p_t1 = round(max(0.55, min(0.78, float(p_side) * 0.92)), 4)
    p_sl = round(max(0.22, min(0.45, 1.0 - p_t1)), 4)

    weight = sum(int(v.get("weight") or 1) for v in agree)
    path_label = "Pattern break" if path == "pattern_break" else "Momentum confluence"
    reasons = [f"{v['label']}: {v.get('detail') or ''}".strip(": ") for v in agree[:6]]
    reason_lines = [r for r in reasons if r]
    tags = [
        {"code": "live_confluence", "label": "Live confluence", "tone": "warning"},
        {"code": "priority_low", "label": "Lower priority · not model", "tone": "warning"},
        {"code": "model_hold", "label": "Model did not pass", "tone": "neutral"},
        {"code": path, "label": path_label, "tone": "warning"},
        {"code": "agree", "label": f"{len(agree)} live signals agree", "tone": "warning"},
    ]
    for v in agree[:4]:
        tags.append({
            "code": str(v.get("id") or "signal"),
            "label": str(v.get("label") or "Signal")[:40],
            "tone": "warning",
        })

    basis = (
        f"Model HOLD — {path_label.lower()} ({len(agree)} signals). "
        + " · ".join(str(v.get("label") or "") for v in agree[:4])
        + ". Today only · your risk — not proven/champion."
    )
    message = (
        f"{side} via live {path_label.lower()} (model HOLD). "
        f"Est. T1 {p_t1 * 100:.0f}% / SL {p_sl * 100:.0f}%. "
        + " | ".join(reason_lines[:3])
    )
    return {
        "available": True,
        "decision": side,
        "entry": round(price, 2),
        "stop_loss": sl,
        "target_1": t1,
        "p_t1": p_t1,
        "track": "live_confluence",
        "source": "live_confluence",
        "path": path,
        "dual_track": False,
        "live_confluence": True,
        "history_eligible": False,
        "priority": 10,
        "accuracy_label": f"Live confluence · {path_label} · model HOLD · today only · your risk",
        "accuracy_tags": tags,
        "model_view": {
            "p_t1": p_t1,
            "p_sl": p_sl,
            "head": "LIVE_CONFLUENCE",
            "message": message,
            "reasons": reason_lines,
            "model_passed": False,
            "path": path,
        },
        "basis": basis,
        "agree_count": len(agree),
        "agree_weight": weight,
        "triggers": [
            {
                "id": v.get("id"),
                "label": v.get("label"),
                "detail": v.get("detail"),
                "trigger": v.get("trigger"),
                "hard": bool(v.get("hard")),
            }
            for v in agree
        ],
        "risk_note": (
            "Not a proven/champion model call. Confirmed live pattern/momentum clip — "
            "size down, manage tightly, excluded from History."
        ),
    }


def _confirms_strong_enough(
    confirms: List[Dict[str, Any]],
    *,
    path: str,
    suggestion_mode: bool = False,
) -> bool:
    """Listing needs full confluence; suggestions accept structure + partial confirms."""
    ids = {c.get("id") for c in confirms}
    if suggestion_mode:
        # Broken W/M/ORB may suggest with checklist + any price-action/lean agree.
        if "checklist" not in ids:
            return False
        return bool(ids & {"short_horizon", "candle", "micro"})
    if "short_horizon" not in ids:
        return False
    if "checklist" not in ids:
        return False
    # Path A needs candle AND micro; Path B needs at least one strong PA read.
    if path == "pattern_break":
        return "candle" in ids and "micro" in ids
    return "candle" in ids or "micro" in ids


def _collect_confirms_for_mode(
    *,
    side: str,
    short_horizon: Optional[Dict[str, Any]],
    indications: Optional[Dict[str, Any]],
    live_context: Optional[Dict[str, Any]],
    candlestick: Optional[Dict[str, Any]],
    suggestion_mode: bool,
    path: str,
) -> List[Dict[str, Any]]:
    if suggestion_mode:
        return _collect_confirms(
            side=side,
            short_horizon=short_horizon,
            indications=indications,
            live_context=live_context,
            candlestick=candlestick,
            min_p_side=0.55 if path == "pattern_break" else 0.62,
            min_micro_buy=58.0,
            min_micro_sell=42.0,
            min_candle_delta=4.0,
            min_checklist_margin=2,
        )
    return _collect_confirms(
        side=side,
        short_horizon=short_horizon,
        indications=indications,
        live_context=live_context,
        candlestick=candlestick,
        min_p_side=MIN_P_SIDE_A if path == "pattern_break" else MIN_P_SIDE_MOM,
    )


def evaluate(
    *,
    price: Optional[float],
    short_horizon: Optional[Dict[str, Any]] = None,
    structure_scan: Optional[Dict[str, Any]] = None,
    indications: Optional[Dict[str, Any]] = None,
    live_context: Optional[Dict[str, Any]] = None,
    candlestick: Optional[Dict[str, Any]] = None,
    open_call: Optional[Dict[str, Any]] = None,
    model_decision: Optional[str] = None,
    session_ticket: Optional[Dict[str, Any]] = None,
    asof: Any = None,
    symbol: Optional[str] = None,
    suggestion_mode: bool = False,
) -> Optional[Dict[str, Any]]:
    """Return a tagged live-confluence payload, or None.

    ``suggestion_mode=True`` uses softer confirms so a broken W/M can still
    surface under Suggestions (never lists on Calls).
    """
    if open_call and open_call.get("decision") not in (None, "HOLD"):
        return None
    md = str(model_decision or "HOLD").upper()
    if "BUY" in md or "SELL" in md:
        return None
    if not suggestion_mode:
        cool = live_cooldown_block(session_ticket, asof=asof)
        if cool:
            return None
    px = _f(price)
    if px is None or px <= 0:
        return None

    hard = _hard_votes(structure_scan, live_context)
    if not hard:
        return None

    # Prefer the strongest hard vote side (weight, then W/M over generic).
    buy_hard = [v for v in hard if v.get("side") == "BUY"]
    sell_hard = [v for v in hard if v.get("side") == "SELL"]
    buy_hw = sum(int(v.get("weight") or 1) for v in buy_hard)
    sell_hw = sum(int(v.get("weight") or 1) for v in sell_hard)

    # Conflicting hard structure (W buy vs M sell both broken) → no live call.
    if buy_hard and sell_hard and buy_hw > 0 and sell_hw > 0:
        if abs(buy_hw - sell_hw) < 2:
            return None

    max_against = 2 if suggestion_mode else 1
    min_confirm = 2 if suggestion_mode else MIN_CONFIRM_A

    candidates: List[Tuple[str, str, List[Dict[str, Any]], int]] = []
    # Path A: hard break + confirms
    for side, group, hw in (("BUY", buy_hard, buy_hw), ("SELL", sell_hard, sell_hw)):
        if not group or hw <= 0:
            continue
        peer_note = peer_coherence_block(symbol, side)
        if peer_note and (
            not suggestion_mode or "opposite live call" in (peer_note or "").lower()
        ):
            continue
        confirms = _collect_confirms_for_mode(
            side=side,
            short_horizon=short_horizon,
            indications=indications,
            live_context=live_context,
            candlestick=candlestick,
            suggestion_mode=suggestion_mode,
            path="pattern_break",
        )
        if len(confirms) < min_confirm:
            continue
        if not _confirms_strong_enough(
            confirms, path="pattern_break", suggestion_mode=suggestion_mode
        ):
            continue
        if _against_count(
            side,
            short_horizon=short_horizon,
            indications=indications,
            live_context=live_context,
            candlestick=candlestick,
        ) >= max_against:
            continue
        agree = group + confirms
        candidates.append(
            (side, "pattern_break", agree, hw + sum(int(c.get("weight") or 1) for c in confirms))
        )

    # Path B: momentum — strong lean first (stricter even in suggestion mode)
    sh = short_horizon or {}
    sh_side = str(sh.get("side") or "").upper()
    sh_p = _f(sh.get("p_side")) or 0.0
    mom_p = 0.62 if suggestion_mode else MIN_P_SIDE_MOM
    if sh_side in ("UP", "DOWN") and sh_p >= mom_p:
        side = "BUY" if sh_side == "UP" else "SELL"
        group = buy_hard if side == "BUY" else sell_hard
        peer_note = peer_coherence_block(symbol, side)
        peer_blocks = bool(peer_note) and (
            not suggestion_mode or "opposite live call" in peer_note.lower()
        )
        if group and not peer_blocks:
            confirms = _collect_confirms_for_mode(
                side=side,
                short_horizon=short_horizon,
                indications=indications,
                live_context=live_context,
                candlestick=candlestick,
                suggestion_mode=suggestion_mode,
                path="momentum",
            )
            if _confirms_strong_enough(
                confirms, path="momentum", suggestion_mode=suggestion_mode
            ):
                agree = group + confirms
                n = len(agree)
                w = sum(int(v.get("weight") or 1) for v in agree)
                against = _against_count(
                    side,
                    short_horizon=short_horizon,
                    indications=indications,
                    live_context=live_context,
                    candlestick=candlestick,
                )
                need_n = 3 if suggestion_mode else MIN_AGREE_MOM
                need_w = 5 if suggestion_mode else MIN_WEIGHT_MOM
                if n >= need_n and w >= need_w and against < max_against:
                    candidates.append((side, "momentum", agree, w))

    if not candidates:
        return None

    # Highest weight wins; pattern_break preferred on ties (clearer structural thesis).
    candidates.sort(key=lambda x: (x[3], 1 if x[1] == "pattern_break" else 0), reverse=True)
    side, path, agree, _w = candidates[0]
    if not suggestion_mode:
        block = peer_coherence_block(symbol, side)
        if block:
            return None
    # Deduplicate by id
    seen = set()
    uniq: List[Dict[str, Any]] = []
    for v in agree:
        vid = v.get("id")
        if vid in seen:
            continue
        seen.add(vid)
        uniq.append(v)
    try:
        payload = _build_payload(
            side=side,
            price=px,
            agree=uniq,
            path=path,
            short_horizon=short_horizon,
            live_context=live_context,
        )
        if symbol:
            payload["symbol"] = str(symbol).upper()
        if suggestion_mode:
            payload["suggestion_only"] = True
            payload["listable"] = False
        return payload
    except ValueError:
        return None


def as_suggestion(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Map a live-confluence evaluate payload to Suggestions-only (never listed)."""
    side = str(payload.get("decision") or "HOLD").upper()
    return {
        "available": True,
        "decision": side,
        "entry": payload.get("entry"),
        "stop_loss": payload.get("stop_loss"),
        "target_1": payload.get("target_1"),
        "p_t1": payload.get("p_t1"),
        "dual_track": False,
        "live_confluence": True,
        "listable": False,
        "history_eligible": False,
        "track": "live_confluence_suggest",
        "source": "live_confluence",
        "path": payload.get("path"),
        "suggestion_tag": "Live indication · suggest only",
        "tag_tone": "warning",
        "basis": (
            "Live structure/momentum indication — suggestion only, "
            "not added to Calls. Paper-trade at your own risk."
        ),
        "accuracy_label": payload.get("accuracy_label"),
        "accuracy_tags": payload.get("accuracy_tags"),
        "model_view": payload.get("model_view"),
        "triggers": payload.get("triggers"),
        "risk_note": payload.get("risk_note"),
        "agree_count": payload.get("agree_count"),
        "agree_weight": payload.get("agree_weight"),
    }


def apply_if_hold(
    result: Dict[str, Any],
    *,
    price: Optional[float],
    open_call: Optional[Dict[str, Any]] = None,
    session_ticket: Optional[Dict[str, Any]] = None,
    asof: Any = None,
    symbol: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """If result is HOLD, maybe attach a live-confluence *suggestion* (never lists a call).

    Decision stays HOLD. Payload is stored under fno_analysis.live_confluence_call
    and result.suggestion when no dual-track suggestion already won.
    """
    decision = str(result.get("decision") or "HOLD").upper()
    if "BUY" in decision or "SELL" in decision:
        return None
    fa = result.get("fno_analysis") if isinstance(result.get("fno_analysis"), dict) else {}
    sym = (
        symbol
        or result.get("symbol")
        or result.get("stock_input")
        or (fa.get("symbol") if isinstance(fa, dict) else None)
    )
    # Suggestions ignore open-ticket lock so research can still surface a lean.
    _ = session_ticket  # listed-call cooldown does not apply to suggest-only
    payload = evaluate(
        price=price,
        short_horizon=fa.get("short_horizon") or result.get("short_horizon"),
        structure_scan=fa.get("structure_scan") or result.get("structure_scan"),
        indications=fa.get("indications") or result.get("indications"),
        live_context=fa.get("live_context") or result.get("live_context"),
        candlestick=result.get("candlestick")
        or (fa.get("candle_guidance") if isinstance(fa.get("candle_guidance"), dict) else None),
        open_call=None,
        model_decision="HOLD",
        session_ticket=None,  # never blocked by open listed ticket — suggest-only path
        asof=asof,
        symbol=sym,
        suggestion_mode=True,
    )
    if not payload:
        return None
    suggestion = as_suggestion(payload)
    fa = dict(fa)
    fa["live_confluence_call"] = {**payload, "listable": False, "suggestion_only": True}
    fa["suggestion"] = suggestion
    # Keep desk decision HOLD — never flip into Calls.
    fa["decision"] = "HOLD"
    result["fno_analysis"] = fa
    result["decision"] = "HOLD"
    prior = result.get("suggestion") if isinstance(result.get("suggestion"), dict) else None
    if not (isinstance(prior, dict) and prior.get("dual_track") and prior.get("decision") in ("BUY", "SELL")):
        result["suggestion"] = suggestion
    notes = list(fa.get("desk_alerts") or [])
    msg = (
        f"Live indication suggests {suggestion.get('decision')} "
        f"(suggest only — not listed on Calls)."
    )
    if msg not in notes:
        notes.insert(0, msg)
    fa["desk_alerts"] = notes
    result["fno_analysis"] = fa
    return suggestion
