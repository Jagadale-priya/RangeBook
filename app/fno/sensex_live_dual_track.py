"""SENSEX live multi-track: proven 100% → champion only (baseline retired from prod).

Gates mirror NIFTY structure; thresholds and tag hit rates load from
sensex_proven_100_final.json when present (freeze-OOS research).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fno_baseline_risk_alert

import path_setup
ROOT = path_setup.ROOT
SYMBOL = "SENSEX"
SIDE_DIR = ROOT / "stock_signal_data" / "fno_validate" / "research" / "sensex_side_models"
RESEARCH_FINAL = SIDE_DIR / "sensex_proven_100_final.json"
BUY_PACK = SIDE_DIR / "fno_SENSEX_BUY_research.pkl"
SELL_PACK = SIDE_DIR / "fno_SENSEX_SELL_research.pkl"
SELL_CONT_Q_PACK = SIDE_DIR / "fno_SENSEX_SELL_CONT_Q_research.pkl"
SELL_CONT_FALLBACK = SIDE_DIR / "fno_SENSEX_SELL_CONT_research.pkl"

PROVEN_100_HIT_PCT = 100.0
PROVEN_100_N = 18
# modal v2 path-score 1y (SELL/BUY first p≥0.55 ±120 Cap3) ~94%
CHAMPION_HIT_PCT = 77.4
BASELINE_HIT_PCT = 58.0
CHAMPION_BUY_HIT = 96.0
CHAMPION_SELL_HIT = 93.0

# Champion HOLD ±50/50: BUY first p≥0.55 + or_ext≤0.15 + SELL first p≥0.70 (no SELL-cont).
# Path 1y 36@86.11% · 3m 12@100.0%.
CHAMPION_BUY_REGIMES = frozenset({"range", "mixed", "trend", "volatile"})
CHAMPION_SELL_CONT_MIN_EXT = 0.15
CHAMPION_SELL_CONT_MAX_EXT = 0.40
CHAMPION_SELL_CONT_MAX_MINS = 12 * 60 + 30
BASELINE_BUY_MIN_P = 0.50
BASELINE_BUY_CONT_MIN_EXT = 0.08
BASELINE_BUY_CONT_MAX_MINS = 14 * 60  # 14:00 IST
BASELINE_SELL_MIN_P = 0.50
CHAMPION_BUY_MIN_P = 0.45
CHAMPION_SELL_MIN_P = 0.45
CHAMPION_SELL_FIRST_ONLY = False
CHAMPION_BUY_MAX_OR_EXT = None

# Proven: BUY first or_ext≤0.15 p≥0.55 → 18/18 WF.
PROVEN_BUY_REGIMES = frozenset({"range", "mixed", "trend", "volatile"})
PROVEN_BUY_MIN_P = 0.55
PROVEN_BUY_MAX_OR_EXT = 0.15
PROVEN_BUY_MAX_MINS = 15 * 60
PROVEN_SELL_REGIMES = frozenset()
PROVEN_SELL_MIN_P = 9.0
PROVEN_TRACK_ENABLED = True
PROVEN_BUY_ONLY = True

_PACK_CACHE: Dict[str, Optional[dict]] = {}


def _apply_research_final() -> None:
    global PROVEN_100_N, PROVEN_100_HIT_PCT, CHAMPION_HIT_PCT, BASELINE_HIT_PCT
    global CHAMPION_BUY_HIT, CHAMPION_SELL_HIT, PROVEN_TRACK_ENABLED
    global CHAMPION_BUY_REGIMES, CHAMPION_BUY_MIN_P, CHAMPION_SELL_MIN_P, CHAMPION_BUY_MAX_OR_EXT
    global CHAMPION_SELL_FIRST_ONLY
    global BASELINE_BUY_MIN_P, BASELINE_SELL_MIN_P
    global PROVEN_BUY_MIN_P, PROVEN_BUY_MAX_OR_EXT, PROVEN_BUY_MAX_MINS, PROVEN_BUY_REGIMES
    global CHAMPION_SELL_CONT_MIN_EXT, CHAMPION_SELL_CONT_MAX_EXT, CHAMPION_SELL_CONT_MAX_MINS
    if not RESEARCH_FINAL.is_file():
        return
    try:
        doc = json.loads(RESEARCH_FINAL.read_text(encoding="utf-8"))
    except Exception:
        return
    tracks = doc.get("tracks") or {}
    verdict = doc.get("verdict") or {}
    champ = (tracks.get("live_champion") or {}).get("full") or {}
    base = (tracks.get("live_baseline") or {}).get("full") or {}
    champ_pol = (tracks.get("live_champion") or {}).get("policy") or {}
    if champ.get("hit_pct") is not None:
        CHAMPION_HIT_PCT = float(champ["hit_pct"])
    if champ.get("buy_hit_pct") is not None:
        CHAMPION_BUY_HIT = float(champ["buy_hit_pct"])
    if champ.get("sell_hit_pct") is not None:
        CHAMPION_SELL_HIT = float(champ["sell_hit_pct"])
    if base.get("hit_pct") is not None:
        BASELINE_HIT_PCT = float(base["hit_pct"])
    # Hit rate above was measured at these cuts. Leaving the module defaults
    # (SELL 0.58) would label a different gate with this study's 58%.
    base_pol = (tracks.get("live_baseline") or {}).get("policy") or {}
    if base_pol.get("buy_min_p") is not None:
        BASELINE_BUY_MIN_P = float(base_pol["buy_min_p"])
    if base_pol.get("sell_min_p") is not None:
        BASELINE_SELL_MIN_P = float(base_pol["sell_min_p"])
    if champ_pol.get("buy_regimes"):
        CHAMPION_BUY_REGIMES = frozenset(str(x) for x in champ_pol["buy_regimes"])
    if champ_pol.get("buy_min_p") is not None:
        CHAMPION_BUY_MIN_P = float(champ_pol["buy_min_p"])
    if champ_pol.get("sell_min_p") is not None:
        CHAMPION_SELL_MIN_P = float(champ_pol["sell_min_p"])
    if "buy_max_or_ext" in champ_pol:
        _bor = champ_pol.get("buy_max_or_ext")
        CHAMPION_BUY_MAX_OR_EXT = float(_bor) if _bor is not None else None
    if champ_pol.get("sell_first_only") is not None:
        CHAMPION_SELL_FIRST_ONLY = bool(champ_pol["sell_first_only"])
    pol = verdict.get("recommended_policy") or {}
    if int(verdict.get("full_n") or 0) >= 8 and float(verdict.get("full_hit_pct") or 0) >= 99.0:
        PROVEN_TRACK_ENABLED = True
        PROVEN_100_N = int(verdict["full_n"])
        PROVEN_100_HIT_PCT = float(verdict.get("full_hit_pct") or 100.0)
        if pol.get("buy_min_p") is not None:
            PROVEN_BUY_MIN_P = float(pol["buy_min_p"])
        if pol.get("buy_max_or_ext") is not None:
            PROVEN_BUY_MAX_OR_EXT = float(pol["buy_max_or_ext"])
        if pol.get("buy_regimes"):
            PROVEN_BUY_REGIMES = frozenset(str(x) for x in pol["buy_regimes"])
        elif not pol.get("buy_regimes"):
            PROVEN_BUY_REGIMES = frozenset({"range", "mixed", "trend", "volatile"})


_apply_research_final()


def packs_available() -> bool:
    return BUY_PACK.is_file() and SELL_PACK.is_file() and (
        SELL_CONT_Q_PACK.is_file() or SELL_CONT_FALLBACK.is_file()
    )


def _load_pack(path: Path) -> Optional[dict]:
    key = str(path)
    if key in _PACK_CACHE:
        return _PACK_CACHE[key]
    if not path.is_file():
        _PACK_CACHE[key] = None
        return None
    try:
        import joblib
        import tools.research.nifty_side_clean as side_clean

        main_mod = sys.modules.get("__main__")
        if main_mod is not None:
            setattr(main_mod, "_CalibratedHead", side_clean.CalibratedHead)
            setattr(main_mod, "CalibratedHead", side_clean.CalibratedHead)
        pack = joblib.load(path)
        if not pack or pack.get("model") is None:
            _PACK_CACHE[key] = None
            return None
        out = dict(pack)
        out["available"] = True
        out["buy_gates"] = None  # apply gates in this module
        _PACK_CACHE[key] = out
        return out
    except Exception:
        _PACK_CACHE[key] = None
        return None


def load_packs() -> Dict[str, Optional[dict]]:
    cont = _load_pack(SELL_CONT_Q_PACK) or _load_pack(SELL_CONT_FALLBACK)
    return {
        "buy": _load_pack(BUY_PACK),
        "sell": _load_pack(SELL_PACK),
        "sell_cont": cont,
    }


def regime_from_feat(feat: Optional[dict]) -> str:
    feat = feat or {}
    if float(feat.get("regime_volatile") or 0) >= 0.5:
        return "volatile"
    if float(feat.get("regime_trend") or 0) >= 0.5:
        return "trend"
    if float(feat.get("regime_range") or 0) >= 0.5:
        return "range"
    return "mixed"


def _ist_mins(ts: Any) -> Optional[int]:
    try:
        import fno_session_rules as fsrules

        dt = fsrules.as_ist(ts)
        if dt is None:
            return None
        return int(dt.hour) * 60 + int(dt.minute)
    except Exception:
        return None


def _or_state(bars: Any, asof: Any) -> Optional[Dict[str, Any]]:
    """Opening range + first-break flags for the session containing asof."""
    if bars is None or len(bars) < 8:
        return None
    try:
        import pandas as pd
        import fno_session_rules as fsrules

        work = bars
        if not isinstance(work.index, pd.DatetimeIndex):
            return None
        day = fsrules.session_date(asof)
        if day is None:
            return None
        day_mask = [fsrules.session_date(t) == day for t in work.index]
        sess = work.loc[day_mask]
        if len(sess) < 2:
            return None
        or_hi = float(sess["High"].astype(float).iloc[0])
        or_lo = float(sess["Low"].astype(float).iloc[0])
        if or_hi <= or_lo:
            return None
        closes = sess["Close"].astype(float)
        first_up = first_dn = None
        for pos in range(len(sess)):
            c = float(closes.iloc[pos])
            if first_up is None and c > or_hi:
                first_up = pos
            if first_dn is None and c < or_lo:
                first_dn = pos
        # last bar at/before asof
        ts = pd.Timestamp(asof)
        if ts.tzinfo is None and work.index.tz is not None:
            ts = ts.tz_localize(work.index.tz)
        elif work.index.tz is not None:
            ts = ts.tz_convert(work.index.tz)
        loc = sess.index.searchsorted(ts, side="right") - 1
        if loc < 0:
            return None
        pos = int(loc)
        close = float(closes.iloc[pos])
        up = close > or_hi
        dn = close < or_lo
        first = (up and pos == first_up) or (dn and pos == first_dn)
        or_ext = abs(close - (or_lo if dn else or_hi)) / (or_hi - or_lo) if (up or dn) else 0.0
        return {
            "or_hi": or_hi,
            "or_lo": or_lo,
            "or_width": or_hi - or_lo,
            "pos": pos,
            "close": close,
            "up": up,
            "dn": dn,
            "first_break": bool(first),
            "or_ext": float(or_ext),
            "mins": _ist_mins(sess.index[pos]),
        }
    except Exception:
        return None


def _last_closed_was_sl(session_ticket: Optional[dict]) -> bool:
    if not session_ticket:
        return False
    hist = list(session_ticket.get("history") or [])
    last = None
    if hist:
        last = hist[-1]
    elif str(session_ticket.get("status") or "") not in ("", "open"):
        last = session_ticket
    if not last:
        return False
    st = str(last.get("status") or "")
    return st in ("sl_before_t1", "same_bar_both")


def _score_side(
    bars: Any,
    *,
    pack: dict,
    day_range: Optional[dict],
    asof: Any,
    force_decision: Optional[str] = None,
) -> Optional[dict]:
    import fno_dual_score

    return fno_dual_score.score_side(
        bars,
        symbol=SYMBOL,
        pack=pack,
        day_range=day_range,
        asof=asof,
        force_decision=force_decision,
        baseline_min_p=BASELINE_BUY_MIN_P if str(force_decision or "").upper() == "BUY" else BASELINE_SELL_MIN_P,
    )


def champion_ok(
    *,
    decision: str,
    first_break: bool,
    regime: str,
    p_t1: float,
    or_ext: float,
    mins: Optional[int],
    skip_after_sl: bool,
) -> bool:
    if skip_after_sl:
        return False
    if decision == "BUY":
        if not first_break:
            return False
        if regime not in CHAMPION_BUY_REGIMES:
            return False
        if CHAMPION_BUY_MAX_OR_EXT is not None and float(or_ext) > float(CHAMPION_BUY_MAX_OR_EXT) + 1e-9:
            return False
        return float(p_t1) >= CHAMPION_BUY_MIN_P
    if decision == "SELL":
        # SENSEX Calls: first-break SELL only (continuation stays on baseline).
        if CHAMPION_SELL_FIRST_ONLY and not first_break:
            return False
        return float(p_t1) >= CHAMPION_SELL_MIN_P
    return False


def baseline_ok(
    *,
    decision: str,
    first_break: bool,
    p_t1: float,
    or_ext: float = 0.0,
    mins: Optional[int] = None,
) -> bool:
    if decision == "BUY":
        if float(p_t1) < BASELINE_BUY_MIN_P:
            return False
        if first_break:
            return True
        if mins is not None and int(mins) > BASELINE_BUY_CONT_MAX_MINS:
            return False
        return float(or_ext) >= BASELINE_BUY_CONT_MIN_EXT
    if decision == "SELL":
        return float(p_t1) >= BASELINE_SELL_MIN_P
    return False


def proven_100_ok(
    *,
    decision: str,
    first_break: bool,
    regime: str,
    p_t1: float,
    or_ext: float,
    mins: Optional[int],
    skip_after_sl: bool,
) -> bool:
    """Walk-forward BUY-only resolved-perfect when research enables it."""
    if not PROVEN_TRACK_ENABLED:
        return False
    if skip_after_sl:
        return False
    if decision == "BUY":
        if not first_break:
            return False
        if regime not in PROVEN_BUY_REGIMES:
            return False
        if float(p_t1) < PROVEN_BUY_MIN_P:
            return False
        if float(or_ext) > PROVEN_BUY_MAX_OR_EXT:
            return False
        if mins is None or int(mins) > PROVEN_BUY_MAX_MINS:
            return False
        return True
    return False


def build_tags(
    *,
    proven_100: bool,
    champion: bool,
    baseline: bool,
    decision: str,
) -> List[Dict[str, Any]]:
    tags: List[Dict[str, Any]] = []
    if proven_100:
        tags.append(
            {
                "code": "proven_100",
                "label": "Priority · Confident 100%",
                "detail": (
                    f"Highest priority: every similar past call ({PROVEN_100_N}/{PROVEN_100_N}) "
                    "hit the first target before stop-loss"
                ),
                "expected_hit_pct": PROVEN_100_HIT_PCT,
                "tone": "proven",
                "priority": 10,
            }
        )
    if champion:
        tags.append(
            {
                "code": "most_accurate",
                "label": "Priority · High accuracy",
                "detail": (
                    f"High priority: strong history — about {CHAMPION_HIT_PCT:.0f}% hit "
                    "first target before stop-loss"
                ),
                "expected_hit_pct": CHAMPION_HIT_PCT,
                "tone": "champion",
                "priority": 11,
            }
        )
        side_hit = CHAMPION_BUY_HIT if decision == "BUY" else CHAMPION_SELL_HIT
        tags.append(
            {
                "code": "side_accuracy",
                "label": f"~{side_hit:.0f}% of {decision}s hit target",
                "detail": f"Past {decision} calls on this strong track hit target about {side_hit:.0f}% of the time",
                "expected_hit_pct": side_hit,
                "tone": "good",
                "priority": 40,
            }
        )
    if baseline:
        tags.append(
            {
                "code": "lower_accuracy",
                "label": "Lower accuracy · your own risk",
                "detail": (
                    f"About {BASELINE_HIT_PCT:.0f}% hit first target — weaker track; "
                    "size and risk are your call"
                ),
                "expected_hit_pct": BASELINE_HIT_PCT,
                "tone": "neutral",
                "priority": 30,
            }
        )
        if not champion and not proven_100:
            tags.append(
                {
                    "code": "baseline_accuracy",
                    "label": f"About {BASELINE_HIT_PCT:.0f}% hit target · your risk",
                    "detail": "Baseline track — lower hit rate; take on your own risk",
                    "expected_hit_pct": BASELINE_HIT_PCT,
                    "tone": "neutral",
                    "priority": 31,
                }
            )
    return tags


def evaluate(
    bars: Any,
    *,
    asof: Any,
    day_range: Optional[dict] = None,
    session_ticket: Optional[dict] = None,
    price: Any = None,
) -> Dict[str, Any]:
    """Score SENSEX dual-track. Safe no-op dict when packs/OR unavailable."""
    empty = {
        "available": False,
        "proven_100": False,
        "champion": False,
        "baseline": False,
        "decision": "HOLD",
        "tags": [],
        "model_view": None,
        "call_payload": None,
        "suggestion_payload": None,
    }
    try:
        import fno_levels

        normed = fno_levels._norm(bars)
        if normed is not None:
            bars = normed
    except Exception:
        pass
    if not packs_available():
        empty["reason"] = "packs_missing"
        return empty
    packs = load_packs()
    if not packs.get("buy") or not packs.get("sell"):
        empty["reason"] = "packs_unusable"
        return empty
    st = _or_state(bars, asof)
    if not st or (not st["up"] and not st["dn"]):
        empty["reason"] = "no_or_break"
        return empty

    first = bool(st["first_break"])
    if st["up"]:
        pack = packs["buy"]
        want = "BUY"
        head_name = "BUY"
    else:
        want = "SELL"
        if first:
            pack = packs["sell"]
            head_name = "SELL"
        else:
            pack = packs["sell_cont"] or packs["sell"]
            head_name = "SELL_CONT_Q" if packs.get("sell_cont") else "SELL"

    scored = _score_side(
        bars, pack=pack, day_range=day_range, asof=asof, force_decision=want
    )
    if not scored or scored["decision"] != want:
        empty["reason"] = "side_score_miss"
        return empty

    regime = scored["regime"]
    p_t1 = float(scored["p_t1"])
    or_ext = float(st["or_ext"])
    mins = st.get("mins")
    skip_sl = _last_closed_was_sl(session_ticket)

    is_proven = proven_100_ok(
        decision=want,
        first_break=first,
        regime=regime,
        p_t1=p_t1,
        or_ext=or_ext,
        mins=mins,
        skip_after_sl=skip_sl,
    )
    is_champ = champion_ok(
        decision=want,
        first_break=first,
        regime=regime,
        p_t1=p_t1,
        or_ext=or_ext,
        mins=mins,
        skip_after_sl=skip_sl,
    )
    # Baseline track retired from live desk — proven + champion only.
    is_base = False
    if not is_proven and not is_champ:
        empty["reason"] = "gates_fail"
        empty["debug"] = {
            "decision": want,
            "p_t1": p_t1,
            "first_break": first,
            "regime": regime,
            "or_ext": or_ext,
            "mins": mins,
            "skip_after_sl": skip_sl,
        }
        return empty

    tags = build_tags(
        proven_100=is_proven, champion=is_champ, baseline=False, decision=want
    )
    risk, tags = fno_baseline_risk_alert.apply_baseline_risk(
        decision=want,
        first_break=first,
        p_t1=p_t1,
        or_ext=or_ext,
        features=scored.get("features") if isinstance(scored.get("features"), dict) else {},
        tags=tags,
        is_baseline=False,
    )
    risk_fields = fno_baseline_risk_alert.payload_risk_fields(risk)
    try:
        entry = float(price) if price is not None else float(scored["entry"])
    except (TypeError, ValueError):
        entry = float(scored["entry"])

    # FINAL locked brackets (T100/SL100) — never inherit ATR-widened desk levels
    try:
        from prod_live.logic import sensex_final_live as sx_final

        lv = sx_final.levels(float(entry), want)
        scored = dict(scored)
        scored["stop_loss"] = lv["stop_loss"]
        scored["target_1"] = lv["target_1"]
        scored["t1_pts"] = lv["t1_pts"]
        scored["sl_pts"] = lv["sl_pts"]
    except Exception:
        pass

    if is_proven:
        expect_hit = PROVEN_100_HIT_PCT
        track_msg = "Confident 100% walk-forward proven gate."
    else:
        expect_hit = CHAMPION_HIT_PCT
        track_msg = f"Champion quality (~{CHAMPION_HIT_PCT:.0f}% proven)."

    model_view = {
        "side": want,
        "head": head_name,
        "p_t1": scored["p_t1"],
        "p_sl": scored["p_sl"],
        "p_t1_pct": round(100.0 * scored["p_t1"], 1),
        "p_sl_pct": round(100.0 * scored["p_sl"], 1),
        "entry": round(entry, 2),
        "stop_loss": scored["stop_loss"],
        "target_1": scored["target_1"],
        "first_break": first,
        "regime": regime,
        "or_ext": round(or_ext, 4),
        "mins": mins,
        "track_proven_100": is_proven,
        "track_champion": is_champ,
        "track_baseline": False,
        "expected_hit_pct": expect_hit,
        **risk_fields,
        "message": (
            f"{want} via {head_name}: model T1 {scored['p_t1']*100:.0f}% / "
            f"SL {scored['p_sl']*100:.0f}%. {track_msg} "
            f"{fno_baseline_risk_alert.risk_message_suffix(risk)}"
        ),
    }

    levels = {
        "decision": want,
        "entry": round(entry, 2),
        "stop_loss": scored["stop_loss"],
        "target_1": scored["target_1"],
        "target_2": None,
        "p_t1": scored["p_t1"],
        "p_sl": scored["p_sl"],
        "regime": regime,
        "first_break": first,
        "accuracy_tags": tags,
        "model_view": model_view,
        "dual_track": True,
        "source": "sensex_dual_track",
        **risk_fields,
    }

    # Listed Calls: proven → champion only.
    try:
        import fno_session_rules as fsrules

        asof_ist = fsrules.as_ist(asof)
        bar_hm = (
            f"{int(asof_ist.hour):02d}:{int(asof_ist.minute):02d}" if asof_ist is not None else None
        )
    except Exception:
        bar_hm = None
    call_payload = None
    if is_proven:
        call_payload = {
            **levels,
            "track": "proven_100",
            "list_priority": 0,
            "accuracy_label": "Priority · Confident 100% proven",
            "hm": bar_hm,
            "source": "dual",
        }
    elif is_champ:
        call_payload = {
            **levels,
            "track": "champion",
            "list_priority": 1,
            "accuracy_label": f"Priority · High accuracy (~{CHAMPION_HIT_PCT:.0f}% hit target)",
            "hm": bar_hm,
            "source": "dual",
        }

    suggestion_payload = None
    if is_champ or is_proven:
        if is_proven:
            sug_src = "sensex_dual_track_proven_100"
            sug_track = "proven_100"
            sug_label = "Priority · Confident 100% proven"
        else:
            sug_src = "sensex_dual_track_champion"
            sug_track = "champion"
            sug_label = f"Priority · High accuracy (~{CHAMPION_HIT_PCT:.0f}% hit target)"
        suggestion_payload = {
            "kind": "suggestion",
            "source": sug_src,
            "decision": want,
            "entry": round(entry, 2),
            "stop_loss": scored["stop_loss"],
            "target_1": scored["target_1"],
            "target_2": None,
            "p_t1": scored["p_t1"],
            "p_sl": scored["p_sl"],
            "need": CHAMPION_SELL_MIN_P if want == "SELL" else CHAMPION_BUY_MIN_P,
            "accuracy_tags": tags,
            "model_view": model_view,
            "dual_track": True,
            "track": sug_track,
            "accuracy_label": sug_label,
            **risk_fields,
            "candle_bias": "BULLISH" if want == "BUY" else "BEARISH",
            "ema_lean": "BULLISH" if want == "BUY" else "BEARISH",
            "candle_patterns": [f"dual_track_{sug_track}"],
            "message": model_view["message"],
            "bars_asof": str(asof),
            "interval": "15minute",
        }

    # Soft head overlay so desk UI sees dual-track probs
    head_overlay = dict(scored.get("head") or {})
    head_overlay.update(
        {
            "available": True,
            "decision": want if (is_proven or is_champ) else "HOLD",
            "p_t1": scored["p_t1"],
            "p_sl": scored["p_sl"],
            "p_meta": scored["p_t1"],
            "should_trade": bool(is_proven or is_champ),
            "dual_track": True,
            "accuracy_tags": tags,
            "model_view": model_view,
            "source": "sensex_dual_track",
            **risk_fields,
            "regime": {"name": regime},
        }
    )

    return {
        "available": True,
        "proven_100": is_proven,
        "champion": is_champ,
        "baseline": False,
        "decision": want,
        "tags": tags,
        "model_view": model_view,
        "call_payload": call_payload,
        "suggestion_payload": suggestion_payload,
        "fno_head_overlay": head_overlay,
        "or_state": {k: st[k] for k in ("first_break", "or_ext", "mins", "up", "dn")},
        "skip_after_sl": skip_sl,
    }



def _try_combine_fallback(
    result: Dict[str, Any],
    ev: Dict[str, Any],
    *,
    bars: Any,
    asof: Any,
    price: Any,
) -> Dict[str, Any]:
    """OR fallback always evaluated; if dual already fired same hm+side, merge tags into 1 call."""
    try:
        import pandas as pd
        from prod_live.logic import sensex_everyday_fallback as sx_fb
        from prod_live.logic import sensex_final_live as sx_final

        ts = pd.Timestamp(asof) if asof is not None else None
        mins = (ts.hour * 60 + ts.minute) if ts is not None else 0
        if mins < (9 * 60 + 45):
            return ev
        fb = sx_fb.or_fallback_call(bars, asof=asof, price=price)
        if not (isinstance(fb, dict) and fb.get("decision") in ("BUY", "SELL")):
            return ev
        side = str(fb["decision"]).upper()
        hm = str(fb.get("hm") or "")[:5]
        entry_px = float(fb.get("entry") or price or 0)
        lv = sx_final.levels(entry_px, side) if entry_px > 0 else {}
        tags_fb = ["fallback", "OR_09:45", sx_final.DESK_CHAMP, sx_final.ACCURACY_TAG]

        existing = ev.get("call_payload") if isinstance(ev.get("call_payload"), dict) else None
        exist_hm = str((existing or {}).get("hm") or (existing or {}).get("time") or "")[:5]
        # Same hm+side only (empty hm is NOT a match — avoids tagging every dual after 09:45).
        if (
            isinstance(existing, dict)
            and str(existing.get("decision") or "").upper() == side
            and exist_hm
            and exist_hm == hm
        ):
            # same-time: ONE call, combine tags
            merged = dict(existing)

            tags = list(merged.get("accuracy_tags") or merged.get("tags") or [])
            for t in (tags_fb + ["dual", "fallback", "COMBINED"]):
                if t not in tags:
                    tags.append(t)
            merged["accuracy_tags"] = tags
            merged["tags"] = tags
            merged["source"] = "dual+fallback"
            merged["track"] = "dual_fb_combined"
            merged["combined"] = True
            merged["accuracy_label"] = "Dual + OR fallback · combined"
            ev = dict(ev)
            ev["call_payload"] = merged
            ev["combined_dual_fallback"] = True
            fa = dict(result.get("fno_analysis") or {})
            fa["sensex_dual_fb_combined"] = True
            result["fno_analysis"] = fa
            return ev

        # dual silent or different — still allow fallback call (no mutual block)
        if isinstance(existing, dict) and existing.get("decision") in ("BUY", "SELL"):
            # dual already listed different setup — leave dual; annotate fallback parallel
            fa = dict(result.get("fno_analysis") or {})
            fa["sensex_or_fallback_parallel"] = {**fb, **lv, "accuracy_tags": tags_fb}
            result["fno_analysis"] = fa
            return ev

        call_payload = {
            **fb,
            **lv,
            "list_priority": 2,
            "dual_track": False,
            "source": "fallback",
            "track": "or_fallback",
            "accuracy_tags": tags_fb,
            "accuracy_label": "OR fallback · 09:45",
        }
        ev = dict(ev or {})
        ev["available"] = True
        ev["decision"] = side
        ev["call_payload"] = call_payload
        ev["everyday_fallback"] = True
        result["suggestion"] = {
            "kind": "suggestion",
            "source": "sensex_everyday_fallback",
            "decision": side,
            "entry": lv.get("entry", entry_px),
            "stop_loss": lv.get("stop_loss"),
            "target_1": lv.get("target_1"),
            "p_t1": 0.50,
            "track": "or_fallback",
            "accuracy_tags": tags_fb,
            "accuracy_label": call_payload["accuracy_label"],
            "message": f"{side} via OR fallback (±50).",
        }
        fa = dict(result.get("fno_analysis") or {})
        fa["suggestion"] = result["suggestion"]
        fa["sensex_everyday_fallback"] = True
        result["fno_analysis"] = fa
        return ev
    except Exception:
        return ev


def apply_to_analyze_result(
    result: Dict[str, Any],
    *,
    bars: Any,
    asof: Any,
    session_ticket: Optional[dict],
    price: Any,
    day_range: Optional[dict] = None,
) -> Dict[str, Any]:
    """Mutate analyze result with dual-track call/suggestion fields for SENSEX."""
    ev = evaluate(
        bars,
        asof=asof,
        day_range=day_range or result.get("day_range_forecast"),
        session_ticket=session_ticket,
        price=price,
    )
    result["sensex_dual_track"] = {
        "available": ev.get("available"),
        "proven_100": ev.get("proven_100"),
        "champion": ev.get("champion"),
        "baseline": ev.get("baseline"),
        "tags": ev.get("tags") or [],
        "model_view": ev.get("model_view"),
        "reason": ev.get("reason"),
    }
    ev = _try_combine_fallback(result, ev, bars=bars, asof=asof, price=price)
    if not ev.get("available") and not ev.get("call_payload"):
        return ev

    # Overlay head for UI probs when dual-track fires
    overlay = ev.get("fno_head_overlay")
    if overlay:
        head = dict(result.get("fno_model") or {})
        head.update(
            {
                "p_t1": overlay.get("p_t1"),
                "p_sl": overlay.get("p_sl"),
                "p_meta": overlay.get("p_meta"),
                "dual_track": True,
                "accuracy_tags": overlay.get("accuracy_tags"),
                "model_view": overlay.get("model_view"),
                "source": "sensex_dual_track",
            }
        )
        if ev.get("proven_100") or ev.get("champion"):
            head["decision"] = ev["decision"]
            head["should_trade"] = True
        result["fno_model"] = head
        live_ctx = dict(result.get("live_context") or {})
        live_ctx["fno_model"] = head
        result["live_context"] = live_ctx

    if ev.get("suggestion_payload"):
        result["suggestion"] = ev["suggestion_payload"]
        fa = dict(result.get("fno_analysis") or {})
        fa["suggestion"] = ev["suggestion_payload"]
        result["fno_analysis"] = fa

    return ev
