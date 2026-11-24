"""Independent daily_fill channel — waterfall_fill_any (up to 2 calls/day).

NIFTY research-aligned policy (same logic that printed ~70% @ ~100% cov on 3m):
  - Call 1: proven/champ immediate, else gated waterfall from 14:15
    (proven → champ → crown → fill-baseline → fill-classic), then
    soft_crown → noon_fill → force_or. Soft fills lock ≥15:15. No soft_dual.
  - Fill-only baseline/classic probes keep the old research fuel even when
    those desk channels are retired from live listing.
  - Call 2 (tight): proven_100 / champion / 5m_crown p≥0.55 gap≥45m.

Modes (DAILY_FILL_MODE):
  - coverage (default): research waterfall, target ~100% day coverage
  - accuracy: skip noon/force last-resort fills (~72% hit / ~64% cov on 1y)

Long-term prove:
  - DAILY_FILL_SHADOW=1 → evaluate + persist, no desk ticket / no notify
  - tools/validate/fno_daily_fill_prove.py → rolling 3m/6m/12m pass bars

BN/Sensex: same pending timing; max 2 with same 2nd-call gate.
Kill switch: ENABLE_DAILY_FILL=0 (shadow still works via DAILY_FILL_SHADOW=1)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

import path_setup
ROOT = path_setup.ROOT

SYMBOLS = frozenset({"NIFTY", "BANKNIFTY", "SENSEX"})
TAG_CODE = "daily_fill"
TAG_LABEL = "daily fill"
# Best-of-day: gated waterfall from 14:15; soft fills wait until 15:15 so
# late crown/champ can win and noon open-ret uses a fuller session (~+5pp fill).
DECISION_MINS = 14 * 60 + 15  # 14:15 IST — gated primary pick
FILL_LOCK_MINS = 15 * 60 + 15  # 15:15 IST — soft/noon/force only
IMMEDIATE_TRACKS = frozenset({"proven_100", "champion"})
MAX_CALLS_PER_DAY = 2
# 2nd call gate (research k2_proven_champ_crown)
SECOND_CALL_TRACKS = frozenset({"proven_100", "champion", "5m_crown"})
SECOND_CALL_MIN_P = 0.55
SECOND_CALL_MIN_GAP_MINS = 45
EXPECTED_HIT = {
    # Old 3m live-like SL/T1 @ ~100% day cov (confirmed on 1y last-3m ≈71%).
    "NIFTY": 69.9,
    "BANKNIFTY": 46.8,
    "SENSEX": 54.8,
}

PRIMARY = ("proven_100", "champion", "5m_crown", "baseline", "15m_classic")
FILL = ("soft_dual", "soft_crown", "noon_fill", "force_or")
PRIORITY = {
    "proven_100": 0,
    "champion": 1,
    "5m_crown": 2,
    "baseline": 3,
    "15m_classic": 4,
    "soft_crown": 5,
    "noon_fill": 6,
    "force_or": 7,
    "soft_dual": 8,
}
# NIFTY: crown over fill-baseline/classic; soft_crown → noon → force_or.
# Acc-lift research: drop soft_dual (weak). Keep noon after soft_crown for cov.
PRIORITY_NIFTY = {
    "proven_100": 0,
    "champion": 1,
    "5m_crown": 2,
    "baseline": 3,
    "15m_classic": 4,
    "soft_crown": 5,
    "noon_fill": 6,
    "force_or": 7,
    "soft_dual": 9,  # excluded in _pick_waterfall for NIFTY
}


# Promotion bars for long-term prove (rolling windows).
PROVE_BARS = {
    "coverage": {"hit_3m": 68.0, "hit_6m": 65.0, "min_cov_3m": 95.0},
    "accuracy": {"hit_3m": 70.0, "hit_6m": 68.0, "min_cov_3m": 55.0},
}


def shadow_enabled() -> bool:
    """Paper/shadow: score + store, never notify / never desk-list."""
    v = str(os.environ.get("DAILY_FILL_SHADOW", "0")).strip().lower()
    return v in ("1", "true", "yes", "on")


def live_enabled() -> bool:
    """Full live desk channel (notify allowed)."""
    v = str(os.environ.get("ENABLE_DAILY_FILL", "0")).strip().lower()
    return v not in ("0", "false", "no", "off")


def enabled() -> bool:
    # Live OR shadow — attach runs in either case.
    return live_enabled() or shadow_enabled()


def is_shadow_only() -> bool:
    return shadow_enabled() and not live_enabled()


def fill_mode(override: Optional[str] = None) -> str:
    """coverage = research 100% cov waterfall; accuracy = skip noon/force fills."""
    if override:
        v = str(override).strip().lower()
    else:
        # Shadow default = accuracy (cleaner long-term prove). Live default = coverage.
        default = "accuracy" if is_shadow_only() else "coverage"
        v = str(os.environ.get("DAILY_FILL_MODE", default)).strip().lower()
    if v in ("accuracy", "acc", "quality", "high"):
        return "accuracy"
    return "coverage"


def daily_fill_tag(*, fill_used: bool = False, track: str = "", call_n: int = 1) -> Dict[str, Any]:
    detail = (
        f"Up to {MAX_CALLS_PER_DAY}/day waterfall "
        "(proven→champion→crown→baseline→classic), then soft/noon if empty. "
        "2nd call only gated proven/champ/crown. Independent of dual/crown/classic."
    )
    if fill_used:
        detail = f"Fill track `{track}` — empty-day cover. " + detail
    if call_n >= 2:
        detail = f"Call #{call_n} (tight 2nd gate). " + detail
    return {
        "code": TAG_CODE,
        "label": TAG_LABEL,
        "detail": detail,
        "tone": "baseline" if fill_used else "champion",
        "priority": 35,
    }


def max_calls_per_day() -> int:
    try:
        return max(1, int(os.environ.get("DAILY_FILL_MAX_PER_DAY", MAX_CALLS_PER_DAY)))
    except Exception:
        return MAX_CALLS_PER_DAY


def _second_call_ok(cand: dict, prior: List[dict]) -> bool:
    """Tight gate for call #2 — research k2_proven_champ_crown."""
    if not prior:
        return True
    track = str(cand.get("track") or "")
    if track not in SECOND_CALL_TRACKS:
        return False
    if not cand.get("gated"):
        return False
    if float(cand.get("p_t1") or 0) < SECOND_CALL_MIN_P:
        return False
    mins = int(cand.get("mins") or 0)
    for p in prior:
        if (
            str(p.get("track") or "") == track
            and str(p.get("decision") or "") == str(cand.get("decision") or "")
            and int(p.get("mins") or 0) == mins
        ):
            return False
        gap = abs(mins - int(p.get("mins") or 0))
        if gap < SECOND_CALL_MIN_GAP_MINS:
            return False
    return True


def _dual_mod(symbol: str):
    if symbol == "NIFTY":
        import nifty_live_dual_track as m
    elif symbol == "BANKNIFTY":
        import banknifty_live_dual_track as m
    else:
        import sensex_live_dual_track as m
    return m


def _norm_ohlc(bars: Any) -> Optional[pd.DataFrame]:
    if bars is None or len(bars) < 20:
        return None
    df = bars.copy() if hasattr(bars, "copy") else bars
    if not isinstance(df.index, pd.DatetimeIndex):
        return None
    rename = {}
    for c in df.columns:
        cl = str(c).lower()
        if cl in ("open", "high", "low", "close", "volume"):
            rename[c] = cl[:1].upper() + cl[1:]
    if rename:
        df = df.rename(columns=rename)
    if not {"Open", "High", "Low", "Close"}.issubset(set(df.columns)):
        return None
    return df.sort_index()


def _ist_mins(asof: Any) -> Optional[int]:
    try:
        ts = pd.Timestamp(asof)
        if ts.tzinfo is not None:
            ts = ts.tz_convert("Asia/Kolkata")
        return int(ts.hour * 60 + ts.minute)
    except Exception:
        return None


def _levels_atr(entry: float, decision: str, bars: pd.DataFrame) -> Tuple[float, float]:
    try:
        import fno_dual_score

        # symbol-agnostic clip via ATR fallback below if needed
    except Exception:
        pass
    atr = float((bars["High"] - bars["Low"]).astype(float).tail(14).mean() or entry * 0.002)
    if decision == "BUY":
        return round(entry - 1.2 * atr, 2), round(entry + 1.8 * atr, 2)
    return round(entry + 1.2 * atr, 2), round(entry - 1.8 * atr, 2)


def _cand(
    *,
    symbol: str,
    track: str,
    decision: str,
    p: float,
    entry: float,
    sl: float,
    t1: float,
    bar_time: str,
    day: str,
    mins: int,
    gated: bool,
) -> Dict[str, Any]:
    fill_used = track in FILL
    expect = float(EXPECTED_HIT.get(symbol, 60.0))
    return {
        "symbol": symbol,
        "decision": decision,
        "entry": round(float(entry), 2),
        "stop_loss": round(float(sl), 2),
        "target_1": round(float(t1), 2),
        "p_t1": round(float(p), 4),
        "bar_time": bar_time,
        "session_date": day[:10],
        "taken_at": bar_time,
        "mins": int(mins),
        "track": track,
        "source": "fno_daily_fill",
        "channel": TAG_LABEL,
        "accuracy_label": (
            f"{TAG_LABEL} · {track}" + (" · FILL" if fill_used else "")
        ),
        "accuracy_tags": [daily_fill_tag(fill_used=fill_used, track=track)],
        "expected_hit_pct": expect,
        "call_n": 1,
        "dual_track": False,
        "independent": True,
        "gated": bool(gated),
        "fill_used": fill_used,
        "daily_fill": fill_used,
        "recipe": "waterfall_fill_any",
        "message": (
            f"{decision} daily fill · {track} · p={p*100:.0f}%"
            + (" (empty-day fill)" if fill_used else "")
        ),
    }


def _priority_map(symbol: str) -> Dict[str, int]:
    return PRIORITY_NIFTY if str(symbol or "").upper() == "NIFTY" else PRIORITY


def _pick_waterfall(
    cands: List[dict],
    *,
    symbol: str = "",
    mode: Optional[str] = None,
) -> Optional[dict]:
    """Research waterfall_fill_any: best priority among gated, else best fill."""
    if not cands:
        return None
    sym = str(symbol or (cands[0].get("symbol") if cands else "")).upper()
    pri = _priority_map(sym)
    mode = fill_mode(mode)
    gated = [c for c in cands if c.get("gated") and c.get("track") in PRIMARY]
    if gated:
        gated.sort(
            key=lambda c: (pri.get(c["track"], 99), -float(c.get("p_t1") or 0))
        )
        return gated[0]
    fills = [c for c in cands if c.get("track") in FILL]
    # NIFTY: soft_dual ~20% on fill days — drop entirely; soft_crown/noon/force cover.
    if sym == "NIFTY":
        fills = [c for c in fills if c.get("track") != "soft_dual"]
    if mode == "accuracy":
        # High-acc mode: soft_crown only (no noon/force) — ~72% hit / ~64% cov on 1y.
        fills = [c for c in fills if c.get("track") == "soft_crown"]
    if not fills:
        return None
    fills.sort(key=lambda c: (pri.get(c["track"], 99), -float(c.get("p_t1") or 0)))
    return fills[0]


def _session_slice(bars: pd.DataFrame, asof: Any) -> pd.DataFrame:
    asof_ts = pd.Timestamp(asof)
    if asof_ts.tzinfo is None and bars.index.tz is not None:
        asof_ts = asof_ts.tz_localize(bars.index.tz)
    elif asof_ts.tzinfo is not None and bars.index.tz is not None:
        asof_ts = asof_ts.tz_convert(bars.index.tz)
    day = asof_ts.date()
    sess = bars.loc[[t.date() == day for t in bars.index]]
    return sess if len(sess) else bars.tail(25)


def _probe_bar_candidates(
    key: str,
    bars: pd.DataFrame,
    *,
    asof: Any,
    price: float,
    day: str,
    box: dict,
    bars_5m: Any = None,
    include_fills: bool = True,
) -> List[dict]:
    """Collect dual/classic/crown (+ optional fills) at one asof."""
    cands: List[dict] = []
    mins = _ist_mins(asof) or 0
    bar_ts = bars.index[-1]
    bar_time = bar_ts.isoformat() if hasattr(bar_ts, "isoformat") else str(bar_ts)
    win = bars.tail(200)

    # dual gated / fill-baseline / soft
    try:
        mod = _dual_mod(key)
        ev = mod.evaluate(
            win, asof=asof, price=price, day_range=box or {}, session_ticket=None
        )
        call = (ev or {}).get("call_payload") or {}
        if call.get("decision") in ("BUY", "SELL"):
            track = str(
                call.get("track")
                or (
                    "proven_100"
                    if ev.get("proven_100")
                    else "champion"
                    if ev.get("champion")
                    else "baseline"
                )
            )
            cands.append(
                _cand(
                    symbol=key,
                    track=track,
                    decision=str(call["decision"]),
                    p=float(call.get("p_t1") or 0),
                    entry=float(call.get("entry") or price),
                    sl=float(call["stop_loss"]),
                    t1=float(call["target_1"]),
                    bar_time=bar_time,
                    day=day,
                    mins=mins,
                    gated=True,
                )
            )
        else:
            # Live dual no longer lists baseline — still harvest fill-baseline
            # when research baseline_ok passes (restores old ~70% @ 100% cov fuel).
            dbg = (ev or {}).get("debug") or {}
            soft_dec = str(dbg.get("decision") or "")
            soft_p = float(dbg.get("p_t1") or 0)
            first = bool(dbg.get("first_break"))
            or_ext = float(dbg.get("or_ext") or 0)
            if soft_dec in ("BUY", "SELL") and soft_p >= 0.40:
                try:
                    st = mod._or_state(win, asof)
                    first = bool((st or {}).get("first_break", first))
                    packs = mod.load_packs()
                    if soft_dec == "BUY":
                        pack = packs.get("buy")
                    else:
                        pack = (
                            packs.get("sell")
                            if first
                            else (packs.get("sell_cont") or packs.get("sell"))
                        )
                    scored = (
                        mod._score_side(
                            win,
                            pack=pack,
                            day_range=box or {},
                            asof=asof,
                            force_decision=soft_dec,
                        )
                        if pack
                        else None
                    )
                except Exception:
                    scored = None
                if scored and scored.get("decision") == soft_dec:
                    p_use = float(scored.get("p_t1") or soft_p)
                    try:
                        is_base = bool(
                            mod.baseline_ok(
                                decision=soft_dec,
                                first_break=first,
                                p_t1=p_use,
                                or_ext=or_ext,
                                mins=mins,
                            )
                        )
                    except Exception:
                        is_base = False
                    if is_base:
                        cands.append(
                            _cand(
                                symbol=key,
                                track="baseline",
                                decision=soft_dec,
                                p=p_use,
                                entry=float(scored.get("entry") or price),
                                sl=float(scored["stop_loss"]),
                                t1=float(scored["target_1"]),
                                bar_time=bar_time,
                                day=day,
                                mins=mins,
                                gated=True,
                            )
                        )
                    else:
                        cands.append(
                            _cand(
                                symbol=key,
                                track="soft_dual",
                                decision=soft_dec,
                                p=p_use,
                                entry=price,
                                sl=float(scored["stop_loss"]),
                                t1=float(scored["target_1"]),
                                bar_time=bar_time,
                                day=day,
                                mins=mins,
                                gated=False,
                            )
                        )
    except Exception:
        pass

    # classic — fill-only probe (desk channel may be off)
    try:
        import fno_15m_classic as classic

        classic_sig = classic.evaluate_latest(
            key,
            win,
            price=price,
            asof=asof,
            day_range=box,
            ignore_enable=True,
        )
        if classic_sig and classic_sig.get("decision") in ("BUY", "SELL"):
            cands.append(
                _cand(
                    symbol=key,
                    track="15m_classic",
                    decision=str(classic_sig["decision"]),
                    p=float(classic_sig.get("p_t1") or 0),
                    entry=float(classic_sig.get("entry") or price),
                    sl=float(classic_sig["stop_loss"]),
                    t1=float(classic_sig["target_1"]),
                    bar_time=str(classic_sig.get("bar_time") or bar_time),
                    day=day,
                    mins=mins,
                    gated=True,
                )
            )
    except Exception:
        pass

    # crown gated (+ soft_crown fill) — pass 15m so HTF matches research pack
    try:
        import fno_5m_crown as crown

        src5 = bars_5m if bars_5m is not None else win
        crown_sig = crown.evaluate_latest(
            key,
            src5,
            bars_15m=win,
            price=price,
            asof=asof,
            day_range=box,
        )
        if crown_sig and crown_sig.get("decision") in ("BUY", "SELL"):
            cands.append(
                _cand(
                    symbol=key,
                    track="5m_crown",
                    decision=str(crown_sig["decision"]),
                    p=float(crown_sig.get("p_t1") or crown_sig.get("p") or 0),
                    entry=float(crown_sig.get("entry") or price),
                    sl=float(crown_sig["stop_loss"]),
                    t1=float(crown_sig["target_1"]),
                    bar_time=str(crown_sig.get("bar_time") or bar_time),
                    day=day,
                    mins=int(crown_sig.get("mins") or mins),
                    gated=True,
                )
            )
        else:
            # soft_crown always available to waterfall (research fill fuel)
            soft = crown.evaluate_latest(
                key,
                src5,
                bars_15m=win,
                price=price,
                asof=asof,
                day_range=box,
                soft_fill=True,
            )
            if soft and soft.get("decision") in ("BUY", "SELL"):
                cands.append(
                    _cand(
                        symbol=key,
                        track="soft_crown",
                        decision=str(soft["decision"]),
                        p=float(soft.get("p_t1") or 0),
                        entry=float(soft.get("entry") or price),
                        sl=float(soft["stop_loss"]),
                        t1=float(soft["target_1"]),
                        bar_time=str(soft.get("bar_time") or bar_time),
                        day=day,
                        mins=int(soft.get("mins") or mins),
                        gated=False,
                    )
                )
    except Exception:
        pass

    if include_fills:
        sess = _session_slice(bars, asof)
        try:
            # Prefer noon→now return when available (research note); else open→now.
            ref = None
            for t, row in sess.iterrows():
                if int(t.hour) * 60 + int(t.minute) >= 12 * 60:
                    ref = float(row["Open"])
                    break
            if ref is None or ref <= 0:
                ref = float(sess["Open"].astype(float).iloc[0])
            c = float(sess["Close"].astype(float).iloc[-1])
            ret = (c - ref) / ref * 100.0 if ref else 0.0
            dec = "BUY" if ret >= 0 else "SELL"
            sl, t1 = _levels_atr(price, dec, bars.tail(40))
            cands.append(
                _cand(
                    symbol=key,
                    track="noon_fill",
                    decision=dec,
                    p=min(0.65, 0.50 + abs(ret) / 100.0),
                    entry=price,
                    sl=sl,
                    t1=t1,
                    bar_time=bar_time,
                    day=day,
                    mins=mins,
                    gated=False,
                )
            )
        except Exception:
            pass
        try:
            or_hi = float(sess["High"].astype(float).iloc[0])
            or_lo = float(sess["Low"].astype(float).iloc[0])
            if or_hi > or_lo and (price > or_hi or price < or_lo):
                dec = "BUY" if price > or_hi else "SELL"
                sl, t1 = _levels_atr(price, dec, bars.tail(40))
                cands.append(
                    _cand(
                        symbol=key,
                        track="force_or",
                        decision=dec,
                        p=0.50,
                        entry=price,
                        sl=sl,
                        t1=t1,
                        bar_time=bar_time,
                        day=day,
                        mins=mins,
                        gated=False,
                    )
                )
        except Exception:
            pass
    return cands


def evaluate_latest(
    symbol: str,
    bars_15m: Any,
    *,
    bars_5m: Any = None,
    price: Optional[float] = None,
    asof: Any = None,
    day_range: Optional[dict] = None,
    result: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
    mode: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """NIFTY/BN/SX: proven/champ early; else accumulate + waterfall at/after 14:15.

    Before 14:15 IST: only lock proven_100/champion. All other candidates are
    stashed in daily_fill_pending (no day lock). At/after 14:15: pick research
    waterfall across pending + this bar (incl. noon/force fills) for 100% cov.
    """
    try:
        if not enabled():
            return None
        mode_use = fill_mode(mode)
        key = str(symbol or "").upper()
        if key not in SYMBOLS:
            return None
        bars = _norm_ohlc(bars_15m)
        if bars is None:
            return None
        if asof is None:
            asof = bars.index[-1]
        mins = _ist_mins(asof)
        if mins is None:
            return None

        import fno_session_rules as fsrules
        import fno_session_replay as fsr
        import daily_fill_store as store

        day = str(fsrules.session_date(asof))[:10]
        cap = max_calls_per_day()
        prior_rows = store.list_today_signals(key, day, db_path=db_path)
        n_today = len(prior_rows)
        if n_today >= cap:
            return None
        prior_cands = [
            {
                "track": r.get("track"),
                "decision": r.get("decision"),
                "mins": int(
                    (
                        pd.Timestamp(r.get("bar_time")).hour * 60
                        + pd.Timestamp(r.get("bar_time")).minute
                    )
                    if r.get("bar_time")
                    else 0
                ),
                "p_t1": r.get("p_t1"),
                "gated": not bool(r.get("fill_used")),
            }
            for r in prior_rows
        ]
        # Repair mins from payload when possible
        for i, r in enumerate(prior_rows):
            try:
                payload = json.loads(r.get("payload_json") or "{}")
                if payload.get("mins") is not None:
                    prior_cands[i]["mins"] = int(payload["mins"])
                if payload.get("gated") is not None:
                    prior_cands[i]["gated"] = bool(payload["gated"])
            except Exception:
                pass

        try:
            entry_px = float(price) if price is not None else float(bars["Close"].iloc[-1])
        except (TypeError, ValueError):
            return None
        if entry_px <= 0:
            return None

        box = day_range
        if not box:
            try:
                box = fsr.session_day_range(_session_slice(bars, asof), lookback=2)
            except Exception:
                box = {}

        at_decision = mins >= DECISION_MINS
        at_fill_lock = mins >= FILL_LOCK_MINS
        bar_cands = _probe_bar_candidates(
            key,
            bars,
            asof=asof,
            price=entry_px,
            day=day,
            box=box or {},
            bars_5m=bars_5m,
            include_fills=at_decision,  # noon/force available from 14:15 but lock later
        )
        # Merge already-attached crown/classic from live result
        result = result or {}
        try:
            crown_sig = (result.get("crown_5m") or {}).get("signal")
            if crown_sig and crown_sig.get("decision") in ("BUY", "SELL"):
                bar_cands.append(
                    _cand(
                        symbol=key,
                        track="5m_crown",
                        decision=str(crown_sig["decision"]),
                        p=float(crown_sig.get("p_t1") or crown_sig.get("p") or 0),
                        entry=float(crown_sig.get("entry") or entry_px),
                        sl=float(crown_sig["stop_loss"]),
                        t1=float(crown_sig["target_1"]),
                        bar_time=str(crown_sig.get("bar_time") or bars.index[-1]),
                        day=day,
                        mins=int(crown_sig.get("mins") or mins),
                        gated=True,
                    )
                )
        except Exception:
            pass
        try:
            classic_sig = (result.get("classic_15m") or {}).get("signal")
            if classic_sig and classic_sig.get("decision") in ("BUY", "SELL"):
                bar_cands.append(
                    _cand(
                        symbol=key,
                        track="15m_classic",
                        decision=str(classic_sig["decision"]),
                        p=float(classic_sig.get("p_t1") or 0),
                        entry=float(classic_sig.get("entry") or entry_px),
                        sl=float(classic_sig["stop_loss"]),
                        t1=float(classic_sig["target_1"]),
                        bar_time=str(classic_sig.get("bar_time") or bars.index[-1]),
                        day=day,
                        mins=mins,
                        gated=True,
                    )
                )
        except Exception:
            pass

        # Stash for best-of-day (skip weak noon/force until decision bar already gated)
        store.upsert_pending(bar_cands, db_path=db_path)

        def _finalize(picked: Optional[dict]) -> Optional[dict]:
            if not picked:
                return None
            if n_today >= 1 and not _second_call_ok(picked, prior_cands):
                return None
            out = dict(picked)
            out["call_n"] = int(n_today) + 1
            out["fill_mode"] = mode_use
            out["shadow"] = bool(is_shadow_only())
            try:
                tags = [
                    daily_fill_tag(
                        fill_used=bool(out.get("fill_used")),
                        track=str(out.get("track") or ""),
                        call_n=int(out["call_n"]),
                    )
                ]
                out["accuracy_tags"] = tags
            except Exception:
                pass
            return out

        # Proven/champion may lock immediately any time (including after 14:15).
        early = [
            c
            for c in bar_cands
            if c.get("track") in IMMEDIATE_TRACKS and c.get("gated")
        ]
        if early:
            early.sort(
                key=lambda c: (
                    _priority_map(key).get(c["track"], 99),
                    -float(c.get("p_t1") or 0),
                )
            )
            return _finalize(early[0])

        if not at_decision:
            return None

        # Densify crown/soft_crown from full 5m session at/after 14:15
        if bars_5m is not None:
            try:
                import fno_5m_crown as crown

                for raw in crown.collect_day_candidates(
                    key,
                    bars_5m,
                    bars_15m=bars,
                    asof=asof,
                    include_soft=True,
                ):
                    track = str(raw.get("track") or "")
                    if track not in ("5m_crown", "soft_crown"):
                        continue
                    if raw.get("decision") not in ("BUY", "SELL"):
                        continue
                    bar_cands.append(
                        _cand(
                            symbol=key,
                            track=track,
                            decision=str(raw["decision"]),
                            p=float(raw.get("p_t1") or 0),
                            entry=float(raw.get("entry") or entry_px),
                            sl=float(raw["stop_loss"]),
                            t1=float(raw["target_1"]),
                            bar_time=str(asof),
                            day=day,
                            mins=int(raw.get("mins") or mins),
                            gated=bool(raw.get("gated")) and track == "5m_crown",
                        )
                    )
                store.upsert_pending(bar_cands, db_path=db_path)
            except Exception:
                pass

        day_cands = store.list_pending(key, day, db_path=db_path)
        seen = {
            (c.get("track"), c.get("decision"), c.get("mins"), round(float(c.get("p_t1") or 0), 4))
            for c in day_cands
        }
        for c in bar_cands:
            k = (
                c.get("track"),
                c.get("decision"),
                c.get("mins"),
                round(float(c.get("p_t1") or 0), 4),
            )
            if k not in seen:
                day_cands.append(c)

        # Call #2: only tight gated tracks (no soft fill as 2nd).
        if n_today >= 1:
            seconds = [c for c in day_cands if _second_call_ok(c, prior_cands)]
            if not seconds:
                return None
            seconds.sort(
                key=lambda c: (
                    _priority_map(key).get(str(c.get("track") or ""), 99),
                    -float(c.get("p_t1") or 0),
                )
            )
            return _finalize(seconds[0])

        picked = _pick_waterfall(day_cands, symbol=key, mode=mode_use)
        if not picked:
            return None
        # Soft fills wait until 15:15 so late gated bars can still arrive.
        if picked.get("track") in FILL and not at_fill_lock:
            return None
        return _finalize(picked)
    except Exception:
        return None


def settle_open_calls(
    symbol: str,
    bars_15m: Any,
    *,
    asof: Any = None,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Close open daily_fill rows when SL/T1 is reached on later 15m bars."""
    closed: List[Dict[str, Any]] = []
    try:
        import daily_fill_store as store
        import fno_session_replay as fsr

        key = str(symbol or "").upper()
        bars = _norm_ohlc(bars_15m)
        if bars is None or key not in SYMBOLS:
            return closed
        asof_ts = pd.Timestamp(asof or bars.index[-1])
        if asof_ts.tzinfo is None and bars.index.tz is not None:
            asof_ts = asof_ts.tz_localize(bars.index.tz)
        elif asof_ts.tzinfo is not None and bars.index.tz is not None:
            asof_ts = asof_ts.tz_convert(bars.index.tz)
        for row in store.list_open(key, db_path=db_path):
            try:
                bt = pd.Timestamp(row.get("bar_time"))
                if bt.tzinfo is None and bars.index.tz is not None:
                    bt = bt.tz_localize(bars.index.tz)
                i = int(bars.index.get_indexer([bt])[0])
                if i < 0:
                    continue
                future = bars.iloc[i + 1 :]
                future = future[future.index <= asof_ts]
                if len(future) < 1:
                    continue
                decision = str(row.get("decision") or "").upper()
                sl = float(row.get("stop_loss"))
                t1 = float(row.get("target_1"))
                outcome = fsr._forward_outcome(
                    future, bearish=decision == "SELL", sl=sl, t1=t1
                )
                if outcome not in ("t1_before_sl", "sl_before_t1", "same_bar_both"):
                    continue
                if store.close_call(int(row["id"]), status=str(outcome), db_path=db_path):
                    closed.append({"id": int(row["id"]), "status": outcome})
            except Exception:
                continue
    except Exception:
        return closed
    return closed


def attach_to_result(
    result: Dict[str, Any],
    symbol: str,
    bars_15m: Any,
    *,
    bars_5m: Any = None,
    price: Optional[float] = None,
    asof: Any = None,
    day_range: Optional[dict] = None,
) -> Dict[str, Any]:
    """Evaluate, persist; notify only when live (not shadow). Never raises."""
    out: Dict[str, Any] = {"ok": False}
    try:
        if not enabled():
            result["daily_fill"] = {"enabled": False, "shadow": False}
            return {"ok": True, "enabled": False}
        key = str(symbol or "").upper()
        shadow = is_shadow_only()
        mode = fill_mode()
        # Settle prior opens before new picks (needed for shadow prove hit rate).
        try:
            settled = settle_open_calls(key, bars_15m, asof=asof)
            if settled:
                result.setdefault("daily_fill_settled", settled)
        except Exception:
            pass
        if key not in SYMBOLS:
            result["daily_fill"] = {
                "enabled": True,
                "shadow": shadow,
                "mode": mode,
                "signal": None,
                "reason": "symbol",
            }
            return {"ok": True, "reason": "symbol"}

        sig = evaluate_latest(
            key,
            bars_15m,
            bars_5m=bars_5m,
            price=price,
            asof=asof,
            day_range=day_range,
            result=result,
            mode=mode,
        )
        if sig:
            sig["shadow"] = shadow
            sig["fill_mode"] = mode
            if shadow:
                sig["accuracy_label"] = (
                    f"{TAG_LABEL} · SHADOW · {mode} · {sig.get('track')}"
                )
        result["daily_fill"] = {
            "enabled": True,
            "shadow": shadow,
            "mode": mode,
            "signal": sig,
            "desk_listed": False if shadow else True,
        }
        if not sig:
            return {"ok": True, "signal": None, "shadow": shadow, "mode": mode}

        import daily_fill_store as store

        saved = store.upsert_signal(sig, max_per_day=max_calls_per_day())
        result["daily_fill"]["saved"] = saved
        out = {
            "ok": True,
            "signal": sig,
            "saved": saved,
            "shadow": shadow,
            "mode": mode,
        }

        # Shadow: persist for prove journal, never notify / never desk ticket.
        if (
            (not shadow)
            and live_enabled()
            and saved.get("ok")
            and saved.get("created")
            and saved.get("id") is not None
        ):
            rid = int(saved["id"])
            if store.claim_notify(rid):
                try:
                    import desktop_notify

                    ok = desktop_notify.notify_daily_fill_call(
                        key,
                        sig["decision"],
                        entry=sig.get("entry"),
                        stop=sig.get("stop_loss"),
                        target=sig.get("target_1"),
                        accuracy_label=sig.get("accuracy_label") or TAG_LABEL,
                        track=sig.get("track"),
                        fill_used=bool(sig.get("fill_used")),
                        row_id=rid,
                    )
                    result["daily_fill"]["notified"] = bool(ok)
                    out["notified"] = bool(ok)
                except Exception as exc:
                    result["daily_fill"]["notify_error"] = str(exc)
        else:
            result["daily_fill"]["notified"] = False

        try:
            day = sig.get("session_date")
            if day:
                result["daily_fill_today"] = store.list_today(key, day)
        except Exception:
            pass
        return out
    except Exception as exc:
        result["daily_fill_error"] = str(exc)
        return {"ok": False, "error": str(exc)}
