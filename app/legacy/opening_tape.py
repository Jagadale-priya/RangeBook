"""Opening drive read from candles and news. Separate from the ML ticket.

Flags a shock when the first 15m bar drives through yesterday's close and
closes near the extreme. News or a crude spike can confirm it. This does
not change the model decision.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore

IST = ZoneInfo("Asia/Kolkata")

# First bar must travel this far beyond yesterday's close.
DRIVE_FRAC = 0.0045
# Close in the outer 40% of that bar (near the low on a down drive).
CLOSE_EDGE = 0.40
# Crude up this much is a bearish confirm for India (oil importer).
CRUDE_CONFIRM_PCT = 0.8
# Lesser target: 0.75 times the stop distance. Measured on confirmed drives, 5y 15m.
TARGET_R = 0.75
MIN_RISK_FRAC = 0.0004
# Minimum target once the confirming-bar stop is at least this wide. 15m tape, 5y.
# Bank Nifty 20–25 points hits often but loses: the stop is much wider than 25.
MIN_TARGET_PTS = {"NIFTY": 25.0, "BANKNIFTY": 60.0}
# Full sample of the shipped rule: 0.75R, raised to the minimum when the stop allows it.
PROOF = {
    "NIFTY": {"n": 136, "t1_before_sl": 0.566, "sl_first": 0.426, "unresolved": 0.007, "expectancy_pts": 1.4},
    "BANKNIFTY": {"n": 139, "t1_before_sl": 0.554, "sl_first": 0.439, "unresolved": 0.007, "expectancy_pts": 3.2},
}

FOLLOW_THROUGH_NOTE = (
    "This is the tape read, not the model. "
    "On five years of Nifty and Bank Nifty, the first 15m drive alone continued to the close only about half the time, "
    "and about one session in three closed back through the open. "
    "A call is issued only if the next 15m bar continues. That confirmed set held for the next hour about 74% of the time "
    "and still reversed through the open by the close about 24% of the time."
)

_CRUDE_CACHE: Dict[str, Any] = {"at": 0.0, "chg": None}
_BAR_CACHE: Dict[str, Any] = {}


def _ist_today():
    return datetime.now(IST).date()


def _norm(df: Any) -> Optional[pd.DataFrame]:
    if df is None or not isinstance(df, pd.DataFrame) or len(df) < 2:
        return None
    work = df.copy()
    rename = {}
    for src, dst in (
        ("open", "Open"),
        ("high", "High"),
        ("low", "Low"),
        ("close", "Close"),
    ):
        if src in work.columns and dst not in work.columns:
            rename[src] = dst
    if rename:
        work = work.rename(columns=rename)
    if not {"Open", "High", "Low", "Close"}.issubset(work.columns):
        return None
    idx = work.index
    if not isinstance(idx, pd.DatetimeIndex):
        return None
    if idx.tz is None:
        work.index = idx.tz_localize(IST)
    else:
        work.index = idx.tz_convert(IST)
    return work.sort_index()


def _session_date(ts) -> Any:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize(IST)
    else:
        t = t.tz_convert(IST)
    return t.date()


def _covers_today(df: Optional[pd.DataFrame]) -> bool:
    if df is None or len(df) == 0:
        return False
    return _session_date(df.index[-1]) == _ist_today()


def _yahoo_symbol(symbol: str) -> str:
    key = symbol.strip().upper()
    if key == "NIFTY":
        return "^NSEI"
    if key == "BANKNIFTY":
        return "^NSEBANK"
    if key.endswith(".NS") or key.startswith("^"):
        return key
    return f"{key}.NS"


def _yahoo_15m(symbol: str) -> Optional[pd.DataFrame]:
    if yf is None:
        return None
    try:
        try:
            hist = yf.Ticker(_yahoo_symbol(symbol)).history(period="5d", interval="15m", auto_adjust=False, timeout=5)
        except TypeError:
            hist = yf.Ticker(_yahoo_symbol(symbol)).history(period="5d", interval="15m", auto_adjust=False)
    except Exception:
        return None
    return _norm(hist)


def crude_change_pct() -> Optional[float]:
    now = time.time()
    if now - float(_CRUDE_CACHE["at"]) < 600:
        return _CRUDE_CACHE["chg"]
    chg = None
    if yf is not None:
        try:
            try:
                hist = yf.Ticker("CL=F").history(period="5d", auto_adjust=False, timeout=5)
            except TypeError:
                hist = yf.Ticker("CL=F").history(period="5d", auto_adjust=False)
            if hist is not None and len(hist) >= 2:
                close = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                if prev:
                    chg = round((close / prev - 1.0) * 100.0, 2)
        except Exception:
            chg = None
    _CRUDE_CACHE["at"] = now
    _CRUDE_CACHE["chg"] = chg
    return chg


def bars_for_read(symbol: str, live_df: Any = None) -> Tuple[Optional[pd.DataFrame], str]:
    live = _norm(live_df)
    if _covers_today(live):
        return live, "kite"
    cached = None
    try:
        import fno_model

        cached = _norm(fno_model.cached_15m(symbol))
    except Exception:
        cached = None
    key = symbol.strip().upper()
    hit = _BAR_CACHE.get(key)
    yahoo = None
    if hit and time.time() - float(hit["at"]) < 120 and _covers_today(hit["df"]):
        yahoo = hit["df"]
    else:
        yahoo = _yahoo_15m(symbol)
        if _covers_today(yahoo):
            _BAR_CACHE[key] = {"at": time.time(), "df": yahoo}
    if _covers_today(yahoo):
        if cached is not None:
            out = pd.concat([cached, yahoo])
            out = out[~out.index.duplicated(keep="last")].sort_index()
            return out, "yahoo_15m"
        return yahoo, "yahoo_15m"
    if live is not None:
        return live, "stale"
    if cached is not None:
        return cached, "stale"
    return None, "no_bars"


def _news_side(news: Optional[Dict[str, Any]], crude: Optional[float]) -> Tuple[str, str]:
    tone = str((news or {}).get("tone") or "NEUTRAL").upper()
    try:
        delta = float((news or {}).get("score_delta") or 0)
    except (TypeError, ValueError):
        delta = 0.0
    bits = []
    side = "NEUTRAL"
    if tone == "BEARISH" or delta <= -3:
        side = "SELL"
        bits.append(f"headlines {tone.lower()} ({delta:+.0f})")
    elif tone == "BULLISH" or delta >= 3:
        side = "BUY"
        bits.append(f"headlines {tone.lower()} ({delta:+.0f})")
    if crude is not None and crude >= CRUDE_CONFIRM_PCT:
        side = "SELL"
        bits.append(f"crude {crude:+.1f}%")
    elif crude is not None and crude <= -CRUDE_CONFIRM_PCT and side != "SELL":
        side = "BUY"
        bits.append(f"crude {crude:+.1f}%")
    elif crude is not None:
        bits.append(f"crude {crude:+.1f}%")
    return side, ", ".join(bits) if bits else "no crude or headline confirm"


def read_opening(
    symbol: str,
    df: Any = None,
    *,
    news: Optional[Dict[str, Any]] = None,
    crude_pct: Optional[float] = None,
    fetch_bars: bool = True,
) -> Dict[str, Any]:
    """Score today's first 15m bar. Model decision is left untouched."""
    source = "given"
    work = _norm(df)
    if work is not None:
        from nifty_fno_data import completed

        work = _norm(completed(work))
    if work is None and fetch_bars:
        work, source = bars_for_read(symbol, None)
    elif work is not None and fetch_bars and not _covers_today(work):
        fresh, fresh_src = bars_for_read(symbol, None)
        if fresh is not None and _covers_today(fresh):
            work, source = fresh, fresh_src
        else:
            source = "stale"
    if work is None or len(work) < 8:
        return {
            "available": False,
            "call": "WATCH",
            "separate_from_model": True,
            "headline": "Tape read needs 15m candles. None loaded for this symbol.",
            "note": FOLLOW_THROUGH_NOTE,
        }

    days = sorted({_session_date(i) for i in work.index})
    day = days[-1]
    sess = work[[_session_date(i) == day for i in work.index]]
    prev = work[[_session_date(i) == days[-2] for i in work.index]] if len(days) >= 2 else None
    if prev is None or len(prev) < 2 or len(sess) < 1:
        return {
            "available": False,
            "call": "WATCH",
            "separate_from_model": True,
            "session_date": str(day),
            "headline": "Tape read needs yesterday and today's first bar.",
            "note": FOLLOW_THROUGH_NOTE,
        }

    prev_c = float(prev["Close"].astype(float).iloc[-1])
    prev_low = float(prev["Low"].astype(float).min())
    prev_high = float(prev["High"].astype(float).max())
    bar = sess.iloc[0]
    o = float(bar["Open"])
    h = float(bar["High"])
    l = float(bar["Low"])
    c = float(bar["Close"])
    span = max(h - l, 1e-9)
    close_pos = (c - l) / span
    gap = o - prev_c
    down_travel = (prev_c - l) / prev_c if prev_c else 0.0
    up_travel = (h - prev_c) / prev_c if prev_c else 0.0
    bearish_body = c < o
    bullish_body = c > o
    broke_prior_low = l < prev_low
    broke_prior_high = h > prev_high

    drive = "NONE"
    if down_travel >= DRIVE_FRAC and close_pos <= CLOSE_EDGE and bearish_body:
        drive = "DOWN"
    elif up_travel >= DRIVE_FRAC and close_pos >= (1.0 - CLOSE_EDGE) and bullish_body:
        drive = "UP"

    # Bar 2 must keep going. The first bar alone is a coin flip on the five-year tape.
    bar2_confirms = False
    if drive != "NONE" and len(sess) >= 2:
        c2 = float(sess["Close"].astype(float).iloc[1])
        bar2_confirms = (c2 < c) if drive == "DOWN" else (c2 > c)

    if crude_pct is None and drive != "NONE":
        crude_pct = crude_change_pct()
    news_side, news_text = _news_side(news, crude_pct)

    stale = day != _ist_today()
    call = "WATCH"
    stage = "none"
    if drive == "NONE":
        stage = "none"
    elif len(sess) < 2:
        stage = "wait_bar2"
    elif bar2_confirms:
        stage = "confirmed"
        call = "SELL" if drive == "DOWN" else "BUY"
    else:
        stage = "faded"
    news_agrees = (drive == "DOWN" and news_side == "SELL") or (drive == "UP" and news_side == "BUY")

    parts = [
        f"{day} first 15m",
        f"gap {gap:+.1f} pts",
        f"bar {o:.1f}–{c:.1f} (low {l:.1f}, high {h:.1f})",
    ]
    if broke_prior_low:
        parts.append("broke prior-day low")
    if broke_prior_high:
        parts.append("broke prior-day high")
    parts.append(news_text)

    if stale:
        headline = (
            f"Tape has no bar for today yet (last session {day}). "
            "This read is not today's open."
        )
        call = "WATCH"
        stage = "stale"
    elif stage == "wait_bar2":
        side = "down" if drive == "DOWN" else "up"
        headline = (
            f"Opening drive {side} on the first 15m bar — not a call yet. "
            "Waiting for the next 15m bar to continue."
            + (" News agrees." if news_agrees else " News has not confirmed.")
        )
    elif stage == "confirmed":
        side = "down" if drive == "DOWN" else "up"
        headline = (
            f"Opening drive {side} confirmed by the next 15m bar."
            + (" Candle and news agree." if news_agrees else " Candle only; news did not confirm.")
        )
    elif stage == "faded":
        side = "down" if drive == "DOWN" else "up"
        headline = f"Opening drive {side} faded on the next 15m bar. No call."
    else:
        headline = "No opening drive on the first 15m bar."

    ticket = _confirmed_ticket(symbol, sess, drive, call, stage)

    return {
        "available": True,
        "separate_from_model": True,
        "symbol": symbol.strip().upper(),
        "session_date": str(day),
        "stale": stale,
        "source": source,
        "call": call,
        "stage": stage,
        "drive": drive,
        "bar2_confirms": bar2_confirms,
        "news_confirms": bool(news_agrees and stage == "confirmed"),
        "news_side": news_side,
        "gap_points": round(gap, 2),
        "drive_down_pct": round(down_travel * 100, 2),
        "drive_up_pct": round(up_travel * 100, 2),
        "close_pos": round(close_pos, 2),
        "prior_close": round(prev_c, 2),
        "first_open": round(o, 2),
        "first_high": round(h, 2),
        "first_low": round(l, 2),
        "first_close": round(c, 2),
        "broke_prior_low": broke_prior_low,
        "broke_prior_high": broke_prior_high,
        "crude_change_pct": crude_pct,
        "detail": " · ".join(parts),
        "headline": headline,
        "note": FOLLOW_THROUGH_NOTE,
        "ticket": ticket,
    }


def _confirmed_ticket(symbol, sess, drive, call, stage) -> Optional[Dict[str, Any]]:
    """Small target, stop beyond the confirming bar. Only after bar 2 continues."""
    if stage != "confirmed" or call not in ("BUY", "SELL") or len(sess) < 2:
        return None
    bar = sess.iloc[1]
    entry = float(bar["Close"])
    bearish = call == "SELL"
    sl = float(bar["High"] if bearish else bar["Low"])
    risk = (sl - entry) if bearish else (entry - sl)
    if entry <= 0 or risk <= 0 or risk / entry < MIN_RISK_FRAC:
        return None
    key = symbol.strip().upper()
    dist = TARGET_R * risk
    floor = MIN_TARGET_PTS.get(key)
    used_floor = False
    if floor and risk >= floor and dist < floor:
        dist = floor
        used_floor = True
    t1 = entry - dist if bearish else entry + dist
    proof = PROOF.get(key) or {
        "n": PROOF["NIFTY"]["n"] + PROOF["BANKNIFTY"]["n"],
        "t1_before_sl": 0.567,
        "sl_first": 0.425,
        "unresolved": 0.007,
        "expectancy_pts": None,
        "note": "Hit rate is the Nifty and Bank Nifty average. This symbol was not in that sample.",
    }
    hit = float(proof["t1_before_sl"])
    return {
        "available": True,
        "call": call,
        "entry": round(entry, 2),
        "stop_loss": round(sl, 2),
        "target_1": round(t1, 2),
        "risk_points": round(risk, 2),
        "target_r": TARGET_R,
        "target_points": round(dist, 2),
        "min_target_points": floor,
        "used_min_target": used_floor,
        "proof": proof,
        "confidence": round(hit * 100, 1),
        "sl_reason": "Stop is the high of the confirming 15m bar" if bearish else "Stop is the low of the confirming 15m bar",
        "t1_reason": (
            f"Target set to {floor:.0f} points — the stop is wide enough"
            if used_floor
            else (
                f"Target {dist:.1f} points ({TARGET_R:.2f} times the stop)"
                + (f", above the {floor:.0f} point floor" if floor and dist >= floor else "")
            )
        ),
        "note": (
            f"5y confirmed opening drives, stop at the confirming bar, target {TARGET_R:.2f}R: "
            f"target hit first {hit:.1%}, stop hit first {float(proof['sl_first']):.1%}, "
            f"neither by the close {float(proof['unresolved']):.1%} (n={proof['n']}). "
            "The stop is the level that ends the drive. The call can still be wrong."
        ),
    }


def apply_fno_call(
    result: Dict[str, Any],
    tape: Optional[Dict[str, Any]],
    *,
    allow_override: bool = True,
) -> Dict[str, Any]:
    """Attach the opening-drive ticket. Override the badge only for the first call
    when the dedicated T1 model is HOLD. Later tickets stay on the clip model."""
    ticket = (tape or {}).get("ticket") or {}
    if not ticket.get("available"):
        return result
    result.setdefault("tape_read", tape)
    result["opening_ticket"] = ticket
    if not allow_override:
        fa = dict(result.get("fno_analysis") or {})
        fa["opening_drive"] = ticket
        result["fno_analysis"] = fa
        return result
    call = ticket["call"]
    # News read against the drive is an alert on the card, not a reason to hide the call.
    news_side = str((tape or {}).get("news_side") or "WATCH").upper()
    news_note = None
    if (call == "BUY" and news_side == "SELL") or (call == "SELL" and news_side == "BUY"):
        news_note = f"News leans {news_side} against this opening-drive {call}. Higher risk."
    live_px = result.get("current_price")
    if live_px is None:
        live_px = (result.get("live_market") or {}).get("last_price")
    if live_px is not None:
        import fno_session_rules as fsrules

        room = fsrules.live_room_hold(call, live_px, ticket.get("stop_loss"), ticket.get("target_1"))
        if room:
            fa = dict(result.get("fno_analysis") or {})
            fa["opening_drive"] = ticket
            fa["opening_drive_skipped"] = room
            result["fno_analysis"] = fa
            result["opening_ticket"] = ticket
            return result
    fa = dict(result.get("fno_analysis") or {})
    model_decision = fa.get("decision") or result.get("decision")
    fa["model_decision"] = model_decision
    fa["decision"] = call
    fa["setup_type"] = "opening_drive"
    fa["confidence"] = ticket["confidence"]
    fa["headline"] = (
        f"F&O {call} — opening drive, small target. Model was {model_decision}."
    )
    if news_note:
        notes = list(fa.get("desk_alerts") or [])
        alerts = list(fa.get("alerts") or [])
        if news_note not in notes:
            notes.append(news_note)
            alerts.append({"code": "desk_notice", "severity": "warning", "message": news_note})
        fa["desk_alerts"] = notes
        fa["alerts"] = alerts
        fa["reasons"] = list(fa.get("reasons") or []) + [news_note]
    trade = {
        "stop_loss": ticket["stop_loss"],
        "target_1": ticket["target_1"],
        "target_2": None,
        "horizon": "opening_drive",
        "levels_fit": True,
        "setup_type": "opening_drive",
        "sl_reason": ticket["sl_reason"],
        "t1_reason": ticket["t1_reason"],
        "note": ticket["note"],
        "entry": ticket["entry"],
    }
    fa["risk"] = {"fno_trade": trade}
    result["fno_analysis"] = fa
    result["model_decision"] = model_decision
    result["decision"] = call
    result["confidence"] = ticket["confidence"]
    result["summary"] = fa["headline"]
    risk = dict(result.get("risk_management") or {})
    risk["fno_trade"] = trade
    result["risk_management"] = risk
    result["opening_ticket"] = ticket
    return result
