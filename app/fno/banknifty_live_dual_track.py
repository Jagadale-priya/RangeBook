"""BANKNIFTY live multi-track: proven 100% → champion only (baseline retired from prod).

Gates mirror NIFTY structure; thresholds and tag hit rates load from
banknifty_proven_100_final.json when present (freeze-OOS research).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fno_baseline_risk_alert

import path_setup
ROOT = path_setup.ROOT
SYMBOL = "BANKNIFTY"
SIDE_DIR = ROOT / "stock_signal_data" / "fno_validate" / "research" / "banknifty_side_models"
RESEARCH_FINAL = SIDE_DIR / "banknifty_proven_100_final.json"
BUY_PACK = SIDE_DIR / "fno_BANKNIFTY_BUY_research.pkl"
SELL_PACK = SIDE_DIR / "fno_BANKNIFTY_SELL_research.pkl"
SELL_CONT_Q_PACK = SIDE_DIR / "fno_BANKNIFTY_SELL_CONT_Q_research.pkl"
SELL_CONT_FALLBACK = SIDE_DIR / "fno_BANKNIFTY_SELL_CONT_research.pkl"

PROVEN_100_HIT_PCT = 100.0
PROVEN_100_N = 12
CHAMPION_HIT_PCT = 93.1
BASELINE_HIT_PCT = 52.8
CHAMPION_BUY_HIT = 93.1
CHAMPION_SELL_HIT = 52.4

# Champion: BUY first any regime (SELL stays on baseline).
CHAMPION_BUY_REGIMES = frozenset({"range", "mixed", "trend", "volatile"})
CHAMPION_SELL_CONT_MIN_EXT = 0.15
CHAMPION_SELL_CONT_MAX_EXT = 0.40
CHAMPION_SELL_CONT_MAX_MINS = 12 * 60 + 30
BASELINE_BUY_MIN_P = 0.50
BASELINE_BUY_CONT_MIN_EXT = 0.08
BASELINE_BUY_CONT_MAX_MINS = 14 * 60  # 14:00 IST
BASELINE_SELL_MIN_P = 0.58
CHAMPION_BUY_MIN_P = 0.50
CHAMPION_SELL_MIN_P = 9.0  # disable SELL on champion

# Proven: BUY first or_ext≤0.15 → 12/12 WF.
PROVEN_BUY_REGIMES = frozenset({"range", "mixed", "trend", "volatile"})
PROVEN_BUY_MIN_P = 0.50
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
    global CHAMPION_BUY_REGIMES, CHAMPION_BUY_MIN_P, CHAMPION_SELL_MIN_P
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
    champ = (tracks.get("live_champion") or {}).get("full") or {}
    base = (tracks.get("live_baseline") or {}).get("full") or {}
    champ_pol = (tracks.get("live_champion") or {}).get("policy") or {}
    verdict = doc.get("verdict") or {}
    if champ.get("hit_pct") is not None:
        CHAMPION_HIT_PCT = float(champ["hit_pct"])
    if champ.get("buy_hit_pct") is not None:
        CHAMPION_BUY_HIT = float(champ["buy_hit_pct"])
    if champ.get("sell_hit_pct") is not None:
        CHAMPION_SELL_HIT = float(champ["sell_hit_pct"])
    if base.get("hit_pct") is not None:
        BASELINE_HIT_PCT = float(base["hit_pct"])
    base_pol = (tracks.get("live_baseline") or {}).get("policy") or {}
    if base_pol.get("buy_min_p") is not None:
        BASELINE_BUY_MIN_P = float(base_pol["buy_min_p"])
    if base_pol.get("sell_min_p") is not None:
        BASELINE_SELL_MIN_P = float(base_pol["sell_min_p"])
    if champ_pol.get("buy_regimes"):
        CHAMPION_BUY_REGIMES = frozenset(str(x) for x in champ_pol["buy_regimes"])
    if champ_pol.get("buy_min_p") is not None:
        CHAMPION_BUY_MIN_P = float(champ_pol["buy_min_p"])
    # Champion sell_min_p=9.0 means BUY-only; keep SELL off champion track.
    if champ_pol.get("sell_min_p") is not None:
        CHAMPION_SELL_MIN_P = float(champ_pol["sell_min_p"])
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
    r2_path = SIDE_DIR / "banknifty_proven_100_r2_report.json"
    if r2_path.is_file() and not PROVEN_TRACK_ENABLED:
        try:
            r2 = json.loads(r2_path.read_text(encoding="utf-8"))
            best = (r2.get("recommended") or {}).get("best_overall") or {}
            bf = best.get("full") or {}
            if best.get("mode") == "resolved" and int(bf.get("n") or 0) >= 8:
                rpol = best.get("policy") or {}
                PROVEN_TRACK_ENABLED = True
                PROVEN_100_N = int(bf["n"])
                PROVEN_100_HIT_PCT = float(bf.get("hit_pct") or 100.0)
                if rpol.get("buy_min_p") is not None:
                    PROVEN_BUY_MIN_P = float(rpol["buy_min_p"])
                if rpol.get("buy_max_or_ext") is not None:
                    PROVEN_BUY_MAX_OR_EXT = float(rpol["buy_max_or_ext"])
                if rpol.get("buy_regimes"):
                    PROVEN_BUY_REGIMES = frozenset(str(x) for x in rpol["buy_regimes"])
        except Exception:
            pass


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
        return float(p_t1) >= CHAMPION_BUY_MIN_P
    # BANKNIFTY champion is BUY-first only (SELL cont stays on baseline).
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
    """Score BANKNIFTY dual-track. Safe no-op dict when packs/OR unavailable."""
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

    # FINAL locked brackets (T75/SL75) — never inherit ATR-widened desk levels
    try:
        from prod_live.logic import bn_final_live as bn_final

        lv = bn_final.levels(float(entry), want)
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
        "source": "banknifty_dual_track",
        **risk_fields,
    }

    # Listed Calls: proven → champion only.
    call_payload = None
    if is_proven:
        call_payload = {
            **levels,
            "track": "proven_100",
            "list_priority": 0,
            "accuracy_label": "Priority · Confident 100% proven",
        }
    elif is_champ:
        call_payload = {
            **levels,
            "track": "champion",
            "list_priority": 1,
            "accuracy_label": f"Priority · High accuracy (~{CHAMPION_HIT_PCT:.0f}% hit target)",
        }

    suggestion_payload = None
    if is_champ or is_proven:
        if is_proven:
            sug_src = "banknifty_dual_track_proven_100"
            sug_track = "proven_100"
            sug_label = "Priority · Confident 100% proven"
        else:
            sug_src = "banknifty_dual_track_champion"
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
            "source": "banknifty_dual_track",
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


def apply_to_analyze_result(
    result: Dict[str, Any],
    *,
    bars: Any,
    asof: Any,
    session_ticket: Optional[dict],
    price: Any,
    day_range: Optional[dict] = None,
) -> Dict[str, Any]:
    """Mutate analyze result with dual-track call/suggestion fields for BANKNIFTY."""
    ev = evaluate(
        bars,
        asof=asof,
        day_range=day_range or result.get("day_range_forecast"),
        session_ticket=session_ticket,
        price=price,
    )
    result["banknifty_dual_track"] = {
        "available": ev.get("available"),
        "proven_100": ev.get("proven_100"),
        "champion": ev.get("champion"),
        "baseline": ev.get("baseline"),
        "tags": ev.get("tags") or [],
        "model_view": ev.get("model_view"),
        "reason": ev.get("reason"),
    }
    if not ev.get("available"):
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
                "source": "banknifty_dual_track",
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
