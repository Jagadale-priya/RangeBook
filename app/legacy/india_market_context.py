"""
India-specific pre-market context: FII/DII, India VIX, Nifty direction proxy, session thesis.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore

import time

import nse_session

FII_DII_URL = "https://www.nseindia.com/api/fiidiiTradeReact"
NSE_PREOPEN_URL = "https://www.nseindia.com/api/market-data-pre-open"
FII_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "stock_signal_data", "cache", "fii_dii_latest.json"
)
# NSE posts one cash print per session, then sometimes revises it.
# Re-read every 5 minutes so a new print is on the desk inside a 1–10 minute window.
_FII_TTL_SEC = 300.0
_CTX_TTL_SEC = 300.0
_CTX_CACHE: Dict[str, Any] = {"at": 0.0, "data": None}
_FII_CACHE: Dict[str, Any] = {"until": 0.0, "data": None}
_FII_LOCK = threading.Lock()


def _yf_change_pct(ticker: str) -> Optional[Dict[str, Any]]:
    if yf is None:
        return None
    try:
        try:
            hist = yf.Ticker(ticker).history(period="10d", auto_adjust=False, timeout=5)
        except TypeError:
            hist = yf.Ticker(ticker).history(period="10d", auto_adjust=False)
        if hist is None or len(hist) < 2:
            return None
        close = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2])
        if close != close or prev != prev:  # NaN guards
            return None
        chg = (close / prev - 1) * 100 if prev else 0.0
        if chg != chg:
            chg = 0.0
        bar_date = str(hist.index[-1].date()) if hasattr(hist.index[-1], "date") else str(hist.index[-1])[:10]
        return {
            "close": round(close, 2),
            "prev_close": round(prev, 2),
            "change_pct": round(chg, 2),
            "bar_date": bar_date,
        }
    except Exception:
        return None


def _parse_fii_rows(rows: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        return None
    parsed = []
    score = 0.0
    for row in rows:
        if not isinstance(row, dict):
            continue
        cat = str(row.get("category") or "")
        try:
            net = float(row.get("netValue") or 0)
            buy = float(row.get("buyValue") or 0)
            sell = float(row.get("sellValue") or 0)
        except (TypeError, ValueError):
            continue
        parsed.append({
            "category": cat,
            "date": row.get("date"),
            "net_value_cr": round(net, 2),
            "buy_cr": round(buy, 2),
            "sell_cr": round(sell, 2),
        })
        upper = cat.upper()
        if "FII" in upper or "FPI" in upper:
            if net > 500:
                score += 2
            elif net < -500:
                score -= 2
        if upper == "DII" and net > 500:
            score += 0.5
    if not parsed:
        return None
    return {
        "available": True,
        "flows": parsed,
        "bias": "FII_BUY" if score >= 1.5 else ("FII_SELL" if score <= -1.5 else "NEUTRAL"),
        "score_delta": max(-3.0, min(3.0, score)),
    }


def _read_fii_disk() -> Optional[Dict[str, Any]]:
    try:
        with open(FII_CACHE_PATH, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return None
    data = payload.get("payload") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or not data.get("available") or not data.get("flows"):
        return None
    return data


def _write_fii_disk(payload: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(FII_CACHE_PATH), exist_ok=True)
        staged = FII_CACHE_PATH + ".tmp"
        with open(staged, "w", encoding="utf-8") as fh:
            json.dump({"saved_at": datetime.now().isoformat(), "payload": payload}, fh)
        os.replace(staged, FII_CACHE_PATH)
    except OSError:
        pass


def _saved_fii(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Last good print, with no connection error attached."""
    out = dict(payload)
    out.pop("error", None)
    out.pop("stale", None)
    out["available"] = True
    return out


def fetch_fii_dii() -> Dict[str, Any]:
    """Last published FII/DII cash. A reset from NSE serves the saved figure."""
    now = time.time()
    with _FII_LOCK:
        cached = _FII_CACHE.get("data")
        if cached and now < float(_FII_CACHE.get("until") or 0):
            return dict(cached)
        if requests is None:
            disk = _read_fii_disk()
            if disk:
                return _saved_fii(disk)
            return {"available": False, "error": "Waiting for today's NSE cash figure."}
        session = nse_session.nse_session()
        error = "NSE session unavailable"
        parsed = None
        if session is not None:
            try:
                response = session.get(FII_DII_URL, timeout=8)
                if response.status_code == 200:
                    parsed = _parse_fii_rows(response.json())
                    if parsed is None:
                        error = "unexpected payload"
                else:
                    error = f"HTTP {response.status_code}"
            except Exception as exc:
                error = nse_session.friendly_error(exc)
        if parsed is not None:
            _write_fii_disk(parsed)
            _FII_CACHE["until"] = time.time() + _FII_TTL_SEC
            _FII_CACHE["data"] = parsed
            return dict(parsed)
        previous = cached if isinstance(cached, dict) and cached.get("flows") else _read_fii_disk()
        if previous:
            # The failed socket is already closed. Show the last print and dial again in a minute.
            saved = _saved_fii(previous)
            _FII_CACHE["until"] = time.time() + 60.0
            _FII_CACHE["data"] = saved
            return dict(saved)
        return {"available": False, "error": "Waiting for today's NSE cash figure."}


def fetch_india_vix() -> Dict[str, Any]:
    data = _yf_change_pct("^INDIAVIX")
    if not data:
        return {"available": False, "symbol": "^INDIAVIX"}
    level = data["close"]
    chg = data["change_pct"]
    score = 0.0
    if level > 18:
        score -= 1.5
    elif level < 13:
        score += 0.5
    if chg > 5:
        score -= 1
    elif chg < -5:
        score += 0.5
    return {
        "available": True,
        "symbol": "^INDIAVIX",
        "level": level,
        "change_pct": chg,
        "bar_date": data["bar_date"],
        "bias": "FEAR" if score <= -1 else ("CALM" if score >= 0.5 else "NEUTRAL"),
        "score_delta": max(-2.5, min(1.5, score)),
    }


def fetch_nifty_open_proxy() -> Dict[str, Any]:
    """GIFT Nifty live is session-limited; use Nifty 50 spot change + optional NSE pre-open IEP."""
    spot = _yf_change_pct("^NSEI")
    preopen_iep = None
    if requests is not None:
        session = nse_session.nse_session()
        if session is not None:
            try:
                r = session.get(NSE_PREOPEN_URL, params={"key": "NIFTY"}, timeout=4)
                if r.status_code == 200:
                    payload = r.json()
                    for block in payload.get("data") or []:
                        meta = block.get("metadata") or {}
                        if meta.get("symbol") in ("NIFTY 50", "NIFTY", "Nifty 50"):
                            preopen_iep = meta.get("iep") or meta.get("lastPrice")
                            break
                    if preopen_iep is None and payload.get("data"):
                        meta = (payload["data"][0] or {}).get("metadata") or {}
                        preopen_iep = meta.get("iep")
            except Exception:
                pass

    if not spot and preopen_iep is None:
        return {"available": False}

    score = 0.0
    if spot:
        if spot["change_pct"] > 0.4:
            score += 2
        elif spot["change_pct"] < -0.4:
            score -= 2

    note = (
        "Pre-open IEP from NSE when auction is active; otherwise Nifty spot vs prior close (GIFT proxy)."
    )
    return {
        "available": True,
        "proxy": preopen_iep is None,
        "nifty_spot": spot,
        "preopen_iep": round(float(preopen_iep), 2) if preopen_iep else None,
        "note": note,
        "score_delta": max(-2.5, min(2.5, score)),
    }


def fetch_india_market_context() -> Dict[str, Any]:
    now = time.time()
    cached = _CTX_CACHE.get("data")
    if cached and now - float(_CTX_CACHE.get("at") or 0) < _CTX_TTL_SEC:
        return cached
    fii = fetch_fii_dii()
    vix = fetch_india_vix()
    nifty = fetch_nifty_open_proxy()
    score = (
        float(fii.get("score_delta") or 0)
        + float(vix.get("score_delta") or 0)
        + float(nifty.get("score_delta") or 0)
    )
    score = max(-6.0, min(6.0, score))
    if score >= 2:
        bias = "BULLISH_FOR_INDIA"
    elif score <= -2:
        bias = "BEARISH_FOR_INDIA"
    else:
        bias = "MIXED"
    out = {
        "available": bool(fii.get("available") or vix.get("available") or nifty.get("available")),
        "fii_dii": fii,
        "india_vix": vix,
        "nifty_open_proxy": nifty,
        "bias": bias,
        "score_delta": round(score, 2),
        "combined_adjust": round(score / 100.0 * 0.06, 4),
        "fetched_at": datetime.now().isoformat(),
    }
    if out.get("available"):
        _CTX_CACHE["at"] = time.time()
        _CTX_CACHE["data"] = out
    return out


def build_session_thesis(
    stock_key: str,
    decision: str,
    day_range: Dict[str, Any],
    india_context: Dict[str, Any],
    structural: Dict[str, Any],
    stop_loss: float,
    signal_quality: str,
) -> Dict[str, Any]:
    lo = day_range.get("expected_low")
    hi = day_range.get("expected_high")
    inv = lo if "BUY" in decision else (hi if "SELL" in decision else None)
    if inv is None and structural.get("support_resistance"):
        sr = structural["support_resistance"]
        inv = sr.get("nearest_support") if "BUY" in decision else sr.get("nearest_resistance")

    india_bias = india_context.get("bias", "MIXED")
    fii_line = ""
    fii = india_context.get("fii_dii") or {}
    if fii.get("available") and fii.get("flows"):
        parts = [f"{x['category']} net ₹{x['net_value_cr']} Cr" for x in fii["flows"][:2]]
        fii_line = "; ".join(parts)

    thesis = (
        f"{stock_key}: {decision} bias for session — watch ₹{lo}–₹{hi}. "
        f"India context {india_bias}"
        + (f" ({fii_line})" if fii_line else "")
        + f". Quality {signal_quality}."
    )
    if inv is not None:
        thesis += f" Invalidate below/above ₹{inv}."
    return {
        "one_line": thesis,
        "session_bias": day_range.get("session_bias", "NEUTRAL"),
        "expected_low": lo,
        "expected_high": hi,
        "invalidation_level": inv,
        "india_market_bias": india_bias,
    }


def compute_trading_gate(decision: str, signal_quality: str, signals_agree: bool) -> Dict[str, Any]:
    """Prod-safe: discourage acting on low-quality or HOLD-like signals."""
    actionable = decision in ("BUY", "SELL", "STRONG BUY", "STRONG SELL")
    allowed = actionable and signal_quality in ("HIGH", "MEDIUM") and signals_agree
    if decision in ("STRONG BUY", "STRONG SELL") and signal_quality != "HIGH":
        allowed = False
    recommended = decision if allowed else "WAIT"
    if not actionable:
        recommended = "WAIT"
    reasons: List[str] = []
    if signal_quality == "LOW":
        reasons.append("Signal quality is LOW — ML and technicals disagree or weak.")
    if not signals_agree:
        reasons.append("ML and technical signals do not agree.")
    if decision in ("STRONG BUY", "STRONG SELL") and signal_quality != "HIGH":
        reasons.append("Strong labels require HIGH quality gate.")
    if not reasons and allowed:
        reasons.append("Gate passed — still verify price and risk before orders.")
    if not allowed and not reasons:
        reasons.append("No actionable edge — wait for alignment.")
    return {
        "allowed_to_act_on_signal": bool(allowed),
        "recommended_action": recommended,
        "reasons": reasons,
        "disclaimer": "Automated gate only; not investment advice or broker instruction.",
    }


def india_reason_lines(ctx: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    fii = ctx.get("fii_dii") or {}
    if fii.get("available"):
        for row in fii.get("flows") or []:
            lines.append(
                f"FII/DII {row.get('date')}: {row.get('category')} net ₹{row.get('net_value_cr')} Cr."
            )
    vix = ctx.get("india_vix") or {}
    if vix.get("available"):
        chg = vix.get("change_pct")
        chg_s = f"{chg:+.2f}%" if chg is not None else "n/a"
        lines.append(
            f"India VIX {vix.get('level')} ({chg_s} vs prior day) — {vix.get('bias')}."
        )
    n = ctx.get("nifty_open_proxy") or {}
    if n.get("available"):
        if n.get("preopen_iep"):
            lines.append(f"NSE pre-open IEP (Nifty): {n.get('preopen_iep')}.")
        spot = n.get("nifty_spot") or {}
        if spot:
            lines.append(
                f"Nifty 50 spot {spot.get('change_pct'):+.2f}% vs prior close (open-direction proxy)."
            )
    return lines
