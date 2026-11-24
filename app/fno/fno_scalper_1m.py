"""F&O Scalper desk — FINAL logic = locked PA `pa_no_trap` (structure SL + pin trail).

Replaces Oracle/HHLL modes. Same engine for index / equity / CE-PE underlyings.
  · CE/PE option strip → BUY signals only
  · Index & stocks → BUY and SELL
  · Chart returns 1m candles + S/R / OR / PDH-PDL levels + full call trail detail

  GET /fno/scalper/chart?stock=NIFTY&days=5&chart_days=5&scope=today|history
  GET /fno/scalper/live?stock=NIFTY&notify=1
  GET /fno/scalper/tick?stock=NIFTY
"""
from __future__ import annotations

import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
IST = ZoneInfo("Asia/Kolkata")

LOGIC_NAME = "PA_NO_TRAP"
LOGIC_VER = "v3d_final"

_BAR_CACHE: Dict[str, Tuple[float, Optional[pd.DataFrame], Optional[str]]] = {}
_BAR_TTL = 25.0
_RESULT_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_RESULT_TTL = 20.0
_LIVE_DEDUPE: Dict[str, str] = {}
_KITE_DEAD_UNTIL = 0.0
_KITE_DEAD_NOTE: Optional[str] = None
_KITE_DEAD_TTL = 180.0


def _paths() -> None:
    for p in (
        str(ROOT),
        str(ROOT / "app"),
        str(ROOT / "app" / "fno"),
        str(ROOT / "app" / "market"),
        str(ROOT / "prod_live"),
    ):
        if p not in sys.path:
            sys.path.insert(0, p)


def _today() -> str:
    return datetime.now(IST).date().isoformat()


def reload_scalper_module() -> Dict[str, Any]:
    """Clear caches (hot reload)."""
    import importlib

    n = {
        "bar": len(_BAR_CACHE),
        "result": len(_RESULT_CACHE),
        "live": len(_LIVE_DEDUPE),
    }
    _BAR_CACHE.clear()
    _RESULT_CACHE.clear()
    _LIVE_DEDUPE.clear()
    _paths()
    for mod_name in ("binance_data", "prod_live.logic.pa_structure_live"):
        try:
            mod = sys.modules.get(mod_name)
            if mod is not None:
                importlib.reload(mod)
        except Exception:
            pass
    try:
        import binance_data

        if hasattr(binance_data, "_KLINE_CACHE"):
            binance_data._KLINE_CACHE.clear()
    except Exception:
        pass
    return {"cleared": n}


def _mark_kite_dead(note: str) -> None:
    global _KITE_DEAD_UNTIL, _KITE_DEAD_NOTE
    _KITE_DEAD_UNTIL = time.time() + _KITE_DEAD_TTL
    _KITE_DEAD_NOTE = note


def _kite_is_dead() -> Optional[str]:
    if time.time() < _KITE_DEAD_UNTIL:
        return _KITE_DEAD_NOTE or "kite_token_dead"
    return None


def _norm_crypto_1m(df: pd.DataFrame) -> pd.DataFrame:
    """24×7 crypto bars — keep all hours (PA Indian session filter off)."""
    w = df.copy()
    if getattr(w.index, "tz", None) is not None:
        w.index = w.index.tz_convert("Asia/Kolkata")
    else:
        w.index = w.index.tz_localize("Asia/Kolkata")
    rename = {c: str(c).title() for c in w.columns}
    w = w.rename(columns=rename)
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in w.columns]
    w = w[cols].astype(float).sort_index()
    return w[~w.index.duplicated(keep="last")]


def _cfg_pa_final(underlying: str, atr_last: float = 10.0, *, crypto: bool = False):
    """Locked pa_no_trap with risk bands scaled for BN / Sensex / equities / crypto."""
    from prod_live.logic import pa_structure_live as pa

    base = pa.load_locked_cfg()
    cfg = replace(
        base,
        name="pa_no_trap",
        sr_gate="no_trap",
        sl_kill_mode="none",
        candle_entry_mode="none",
        candle_trail_mode="pin_protect",
        use_frvp=False,
        require_real_target=False,
    )
    a = float(atr_last) if atr_last and atr_last > 0 else 10.0
    if crypto:
        # 24h session · ATR-scaled risk (works for BTC ~tens of $ and alts)
        return replace(
            cfg,
            trade_lo=0,
            trade_hi=24 * 60 - 1,
            min_risk=max(round(0.40 * a, 6), round(a * 0.25, 6)),
            max_risk=max(round(3.5 * a, 6), round(a * 2.0, 6)),
            sl_buffer=max(round(0.10 * a, 6), round(a * 0.05, 6)),
            max_calls_day=24,
        )
    u = str(underlying or "NIFTY").upper()
    if u == "BANKNIFTY":
        return replace(cfg, min_risk=10.0, max_risk=70.0, sl_buffer=2.0)
    if u == "SENSEX":
        return replace(cfg, min_risk=8.0, max_risk=60.0, sl_buffer=1.5)
    if u not in ("NIFTY", "FINNIFTY", "MIDCPNIFTY"):
        return replace(
            cfg,
            min_risk=max(3.0, round(0.35 * a, 2)),
            max_risk=max(22.0, round(min(2.8 * a, 8.0 * a), 2)),
            sl_buffer=max(0.75, round(0.08 * a, 2)),
        )
    return cfg


def _load_1m(
    key: str,
    days: int = 7,
    *,
    crypto: bool = False,
    force_refresh: bool = False,
    hours: Optional[int] = None,
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    _paths()
    now = time.time()
    cache_k = (
        f"{'C:' if crypto else 'I:'}{key}:h{int(hours)}"
        if hours is not None
        else f"{'C:' if crypto else 'I:'}{key}:d{int(days)}"
    )
    if not force_refresh:
        hit = _BAR_CACHE.get(cache_k)
        if hit and (now - hit[0]) < _BAR_TTL:
            return hit[1], hit[2]

    if crypto:
        import binance_data

        raw, err = binance_data.fetch_klines_1m(
            key,
            days=int(max(1, min(int(days), 30))),
            hours=hours,
            force_refresh=force_refresh,
        )
        if err or raw is None:
            _BAR_CACHE[cache_k] = (now, None, err or "no_bars")
            return None, err or "no_bars"
        bars = _norm_crypto_1m(raw)
        if bars is None or bars.empty:
            _BAR_CACHE[cache_k] = (now, None, "empty_bars")
            return None, "empty_bars"
        _BAR_CACHE[cache_k] = (now, bars, None)
        return bars, None

    import kite_data
    from prod_live.logic.pa_structure_live import norm_1m

    dead = _kite_is_dead()
    if dead:
        return None, dead

    try:
        raw, err = kite_data.fetch_historical_candles(
            key, "minute", days=int(max(3, min(int(days), 25))), keep_partial=False
        )
    except Exception as exc:
        msg = str(exc)
        if "token" in msg.lower() or "api_key" in msg.lower() or "403" in msg:
            _mark_kite_dead(msg)
        _BAR_CACHE[cache_k] = (now, None, msg)
        return None, msg

    if err or raw is None:
        msg = err or "no bars"
        if "token" in str(msg).lower() or "Incorrect" in str(msg):
            _mark_kite_dead(str(msg))
        _BAR_CACHE[cache_k] = (now, None, msg)
        return None, msg

    bars = norm_1m(raw)
    if bars is None or bars.empty:
        _BAR_CACHE[cache_k] = (now, None, "empty_bars")
        return None, "empty_bars"
    _BAR_CACHE[cache_k] = (now, bars, None)
    return bars, None


def _ts_unix(ts) -> int:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("Asia/Kolkata")
    else:
        t = t.tz_convert("Asia/Kolkata")
    return int(t.timestamp())


def _price_nd(price: float) -> int:
    """Decimals for payload rounding — crypto needs finer ticks."""
    p = abs(float(price or 0))
    if p >= 1000:
        return 2
    if p >= 1:
        return 4
    return 6


def _candles_payload(
    bars: pd.DataFrame,
    chart_days: int = 1,
    *,
    hours: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Chart candles: calendar days (India session) or rolling hours (crypto 24h)."""
    if bars is None or bars.empty:
        return []
    if hours is not None and hours > 0:
        last_ts = bars.index[-1]
        cut = last_ts - pd.Timedelta(hours=int(hours))
        subset = bars[bars.index >= cut]
    else:
        days = sorted({str(ts.date()) for ts in bars.index})
        keep = set(days[-max(1, int(chart_days)) :])
        subset = bars[bars.index.strftime("%Y-%m-%d").isin(keep)]
    out = []
    for ts, row in subset.iterrows():
        cl = float(row["Close"])
        nd = _price_nd(cl)
        out.append(
            {
                "time": _ts_unix(ts),
                "open": round(float(row["Open"]), nd),
                "high": round(float(row["High"]), nd),
                "low": round(float(row["Low"]), nd),
                "close": round(cl, nd),
            }
        )
    return out


def _levels_at(
    bars: pd.DataFrame,
    cfg,
    *,
    all_hours: bool = False,
    live_spot: Optional[float] = None,
) -> Dict[str, Any]:
    """Clean chart levels only — OR, nearest support/resistance, PDH/PDL, swing."""
    from prod_live.logic import pa_structure_live as pa

    if bars is None or bars.empty:
        return {"spot": None, "atr": None, "levels": [], "process": []}
    # Crypto must keep 24h bars — NSE 09:15–15:29 filter would pick a stale "spot"
    work = pa.norm_1m(bars, all_hours=bool(all_hours))
    if work.empty:
        return {"spot": None, "atr": None, "levels": [], "process": []}
    o = work["Open"].values
    h = work["High"].values
    l = work["Low"].values
    c = work["Close"].values
    atr = pa.atr14(h, l, c)
    idx = work.index
    i = len(work) - 1
    sr = pa.build_sr_map(o, h, l, c, atr, idx, i, lookback_days=int(cfg.sr_lookback_days))

    day = pa._day(idx[i])
    j0 = i
    while j0 > 0 and pa._day(idx[j0 - 1]) == day:
        j0 -= 1
    or_end = min(j0 + int(cfg.or_bars) - 1, i)
    or_hi = float(np.max(h[j0 : or_end + 1])) if or_end >= j0 else None
    or_lo = float(np.min(l[j0 : or_end + 1])) if or_end >= j0 else None
    j_sw = max(j0, i - int(cfg.swing_n))
    swing_hi = float(np.max(h[j_sw : i + 1])) if i >= j_sw else None
    swing_lo = float(np.min(l[j_sw : i + 1])) if i >= j_sw else None
    last_close = float(c[i])
    spot_raw = float(live_spot) if live_spot is not None and float(live_spot) > 0 else last_close
    nd = _price_nd(spot_raw)
    spot = round(spot_raw, nd)
    atr_v = round(float(atr[i]) if np.isfinite(atr[i]) else 0.0, nd)
    near_res = float(sr["nearest_res"]["price"]) if sr.get("nearest_res") else None
    near_sup = float(sr["nearest_sup"]["price"]) if sr.get("nearest_sup") else None

    def _lvl(price, label, kind):
        if price is None:
            return None
        return {"price": round(float(price), 2), "label": label, "kind": kind}

    # Chart: only live support / resistance (+ OR used for setups). No PDH/swing clutter.
    raw = [
        _lvl(or_hi, "OR High", "or"),
        _lvl(or_lo, "OR Low", "or"),
        _lvl(near_res, "Resistance", "resistance"),
        _lvl(near_sup, "Support", "support"),
    ]
    seen = set()
    levels = []
    for lv in raw:
        if not lv:
            continue
        k = round(lv["price"], 1)
        if k in seen:
            continue
        seen.add(k)
        levels.append(lv)

    def _sit_vs(level: Optional[float], above: str, below: str, flat: str = "at level") -> str:
        if level is None:
            return "n/a"
        if spot > level + 0.5:
            return above
        if spot < level - 0.5:
            return below
        return flat

    or_mid = (0.5 * (or_hi + or_lo)) if (or_hi is not None and or_lo is not None) else None
    conditions = [
        {
            "name": "Logic",
            "condition": "PA pa_no_trap (final)",
            "value": LOGIC_NAME,
            "situation": "1m causal · structure SL · pin trail @ +1R",
            "status": "active",
        },
        {
            "name": "Live price",
            "condition": "Binance LTP" if all_hours else "Last 1m close / LTP",
            "value": spot,
            "situation": f"ATR {atr_v}" + (
                f" · 1m close {round(last_close, nd)}" if live_spot is not None else ""
            ),
            "status": "live",
        },
        {
            "name": "Opening range",
            "condition": f"First {int(cfg.or_bars)} × 1m bars",
            "value": f"{or_lo} – {or_hi}" if or_lo is not None else "building",
            "situation": (
                _sit_vs(or_mid, "above OR mid (bull bias)", "below OR mid (bear bias)", "inside OR")
                if or_mid is not None
                else "OR not ready"
            ),
            "status": "ok" if or_hi is not None else "wait",
        },
        {
            "name": "Support",
            "condition": "Nearest multi-day support (S/R map)",
            "value": near_sup if near_sup is not None else "—",
            "situation": _sit_vs(near_sup, "price above support", "price below support", "holding support"),
            "status": "ok" if near_sup is not None else "wait",
        },
        {
            "name": "Resistance",
            "condition": "Nearest multi-day resistance (S/R map)",
            "value": near_res if near_res is not None else "—",
            "situation": _sit_vs(near_res, "price above resistance", "price below resistance", "at resistance"),
            "status": "ok" if near_res is not None else "wait",
        },
        {
            "name": "OR High",
            "condition": "Break / retest reference",
            "value": or_hi if or_hi is not None else "—",
            "situation": _sit_vs(or_hi, "broke above OR high", "below OR high", "at OR high"),
            "status": "ok" if or_hi is not None else "wait",
        },
        {
            "name": "OR Low",
            "condition": "Break / retest reference",
            "value": or_lo if or_lo is not None else "—",
            "situation": _sit_vs(or_lo, "above OR low", "broke below OR low", "at OR low"),
            "status": "ok" if or_lo is not None else "wait",
        },
        {
            "name": "Entry setups",
            "condition": "BREAK_HOLD · SWEEP_RECLAIM · OR_RETEST",
            "value": "armed",
            "situation": "Fire only when setup + no trap against side",
            "status": "active",
        },
        {
            "name": "Risk / trail",
            "condition": f"Risk band {cfg.min_risk}–{cfg.max_risk} pts · trail_arm {cfg.trail_arm_R}R",
            "value": f"SL buffer {cfg.sl_buffer}",
            "situation": "Structure SL · pin_protect after +1R · no fixed hard target",
            "status": "active",
        },
        {
            "name": "Option gate",
            "condition": "CE/PE strip → BUY only · index/stock → BUY+SELL",
            "value": "symbol-dependent",
            "situation": "Applied after PA scan on underlying 1m",
            "status": "active",
        },
    ]
    process = [
        f"{c['name']}: {c['value']} · {c['situation']}" for c in conditions
    ]
    return {
        "atr": atr_v,
        "spot": spot,
        "or_hi": or_hi,
        "or_lo": or_lo,
        "pdh": sr.get("pdh"),
        "pdl": sr.get("pdl"),
        "nearest_res": near_res,
        "nearest_sup": near_sup,
        "swing_hi": swing_hi,
        "swing_lo": swing_lo,
        "levels": levels,
        "process": process,
        "conditions": conditions,
    }


def _soft_targets(side: str, entry: float, risk: float) -> Dict[str, float]:
    if side == "BUY":
        return {
            "soft_1r": round(entry + risk, 2),
            "soft_2r": round(entry + 2 * risk, 2),
            "soft_3r": round(entry + 3 * risk, 2),
        }
    return {
        "soft_1r": round(entry - risk, 2),
        "soft_2r": round(entry - 2 * risk, 2),
        "soft_3r": round(entry - 3 * risk, 2),
    }


def _enrich_call(c: Any, underlying: str, loaded_opt: Optional[str], cfg) -> Dict[str, Any]:
    entry = float(c.entry)
    sl = float(c.stop_loss)
    risk = float(c.risk)
    side = str(c.side).upper()
    soft = _soft_targets(side, entry, risk)
    pts = float(c.pts) if c.pts is not None else None
    mfe = float(c.mfe) if c.mfe is not None else None
    return {
        "day": c.day,
        "hm": c.hm,
        "side": side,
        "setup": c.setup,
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "stop_loss": round(sl, 2),
        "risk": round(risk, 2),
        "target": soft["soft_1r"],          # trail arm (+1R)
        "target_1": soft["soft_1r"],
        "target_2": soft["soft_2r"],
        "mfe_pts": round(mfe, 2) if mfe is not None else None,  # best points in favour
        "pts": round(pts, 2) if pts is not None else None,
        "R": round(float(c.R), 3) if c.R is not None else None,
        "exit_hm": c.exit_hm,
        "exit_why": c.exit_why,
        "exit_px": c.exit_px,
        "win": c.win,
        "reason": c.reason,
        "option_right": "CE" if side == "BUY" else "PE",
        "loaded_option": loaded_opt,
        "time": None,
    }


def _markers_from_calls(calls: List[Dict[str, Any]], bars: pd.DataFrame) -> List[Dict[str, Any]]:
    from prod_live.logic import pa_structure_live as pa

    hm_map: Dict[Tuple[str, str], int] = {}
    for i, ts in enumerate(bars.index):
        hm_map[(pa._day(ts), pa._hm(ts))] = _ts_unix(ts)
    markers = []
    for c in calls:
        t = hm_map.get((c["day"], c["hm"]))
        if t is None:
            continue
        c["time"] = t
        side = c["side"]
        color = "#16a34a" if side == "BUY" else "#dc2626"
        markers.append(
            {
                "time": t,
                "position": "belowBar" if side == "BUY" else "aboveBar",
                "color": color,
                "shape": "arrowUp" if side == "BUY" else "arrowDown",
                "text": side[0],
            }
        )
    return markers


def _resolve_scan_key(
    stock: str, *, market: str = "india"
) -> Tuple[Dict[str, Any], str, Optional[str], Optional[str], bool]:
    """Return meta, scan_key, side_gate, loaded_opt, is_crypto."""
    _paths()
    import binance_data
    import fno_scalper_symbol as sym

    mkt = str(market or "india").lower()
    raw = str(stock or "").strip()
    if mkt == "crypto" or binance_data.is_crypto_symbol(raw):
        meta = binance_data.resolve_crypto(raw or "BTCUSDT")
        return meta, str(meta["key"]), None, None, True

    meta = sym.resolve(stock)
    key = str(meta.get("key") or stock or "NIFTY")
    kind = str(meta.get("kind") or "index")
    underlying = str(meta.get("underlying") or key).upper()
    side_gate = sym.option_call_side(meta)  # BUY for CE/PE else None
    loaded_opt = None
    if kind == "option":
        loaded_opt = str(meta.get("tradingsymbol") or meta.get("display") or "")
        scan_key = underlying if underlying else "NIFTY"
    else:
        scan_key = key
    if underlying in ("NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY") and kind == "option":
        scan_key = underlying
    return meta, scan_key, side_gate, loaded_opt, False


def scan_scalper(
    stock: str = "NIFTY",
    *,
    days: int = 5,
    mode: str = "pa_no_trap",  # ignored — final logic only
    chart_days: int = 5,
    interval: str = "1m",
    force_refresh: bool = False,
    scope: str = "history",  # today | history
    market: str = "india",  # india | crypto
    **_kwargs: Any,
) -> Dict[str, Any]:
    """Main scalper chart+calls API.

    Live (scope=today): lean fetch — crypto last ~36h (24h chart), India ~3 sessions.
    History: full multi-day fetch for Call history tab only.
    """
    _paths()
    from prod_live.logic import pa_structure_live as pa

    t0 = time.time()
    meta, scan_key, side_gate, loaded_opt, is_crypto = _resolve_scan_key(
        stock, market=market
    )
    days = int(max(1, min(int(days or 5), 40)))
    chart_days = int(max(1, min(int(chart_days or 1), 10)))
    scope = str(scope or "history").lower()
    if scope not in ("today", "history"):
        scope = "history"
    live = scope == "today"

    cache_k = f"{'C' if is_crypto else 'I'}:{scan_key}:{side_gate or 'BOTH'}:{days}:{chart_days}:{scope}:live{int(live)}"
    now = time.time()
    if not force_refresh:
        hit = _RESULT_CACHE.get(cache_k)
        if hit and (now - hit[0]) < _RESULT_TTL:
            out = dict(hit[1])
            out["cached"] = True
            return out

    # Live = fast path. History keeps multi-day bars for Call history.
    fetch_hours: Optional[int] = None
    if live and is_crypto:
        fetch_hours = 36  # 24h chart + SR lookback (~2 Binance pages)
        fetch_days = 2
    elif live:
        fetch_days = 3  # today + 2 sessions SR lookback
    else:
        fetch_days = max(days + 2, 5)

    bars, err = _load_1m(
        scan_key,
        days=fetch_days,
        crypto=is_crypto,
        force_refresh=force_refresh,
        hours=fetch_hours,
    )
    if err or bars is None or bars.empty:
        return {
            "ok": False,
            "error": err or "no_bars",
            "stock": stock,
            "underlying": scan_key,
            "meta": meta,
            "market": "crypto" if is_crypto else "india",
            "logic": LOGIC_NAME,
            "calls": [],
            "candles": [],
            "levels": {},
        }

    work0 = bars if is_crypto else pa.norm_1m(bars)
    if work0 is None or work0.empty:
        work0 = bars
    atr = pa.atr14(work0["High"].values, work0["Low"].values, work0["Close"].values)
    atr_last = float(atr[-1]) if len(atr) and np.isfinite(atr[-1]) else 10.0
    cfg = _cfg_pa_final(scan_key, atr_last, crypto=is_crypto)

    all_days = sorted({str(ts.date()) for ts in bars.index})
    if live:
        # Logic window = what we fetched (lean). Score last 1–2 sessions.
        score_n = 2 if is_crypto else 1
        score_days = all_days[-min(score_n, len(all_days)) :]
    else:
        score_days = all_days[-min(days, len(all_days)) :]
    if not score_days:
        return {"ok": False, "error": "no_sessions", "stock": stock, "calls": [], "candles": []}
    si = max(0, all_days.index(score_days[0]) - (0 if live and is_crypto else 2))
    frame = bars[bars.index.strftime("%Y-%m-%d").isin(set(all_days[si:]))]

    raw_calls = pa.scan_session(frame, settle=True, cfg=cfg, all_hours=is_crypto)
    scored = [c for c in raw_calls if c.day in set(score_days)]
    if side_gate:
        scored = [c for c in scored if str(c.side).upper() == side_gate]

    today = _today()
    hist_n = min(max(int(days), 1), len(score_days))
    hist_days = score_days[-hist_n:]
    if scope == "today":
        if is_crypto and len(frame):
            cut = frame.index[-1] - pd.Timedelta(hours=24)
            view_calls = []
            for c in scored:
                try:
                    cts = pd.Timestamp(f"{c.day} {c.hm}", tz=IST)
                except Exception:
                    continue
                if cts >= cut:
                    view_calls.append(c)
            if not view_calls:
                view_calls = [c for c in scored if c.day == today] or [
                    c for c in scored if c.day == score_days[-1]
                ]
        else:
            view_calls = [c for c in scored if c.day == today]
    else:
        view_calls = [c for c in scored if c.day in set(hist_days)]

    # Chart: crypto = last 24h · India = live session (today)
    chart_win = 1
    chart_hours = 24 if (live and is_crypto) else None
    rows = [_enrich_call(c, scan_key, loaded_opt, cfg) for c in view_calls]
    candles = _candles_payload(frame, chart_win, hours=chart_hours)
    # Levels from chart window so S/R matches what user sees
    live_spot = None
    if is_crypto:
        try:
            import binance_data

            live_spot, _ = binance_data.fetch_ltp(scan_key)
        except Exception:
            live_spot = None
        if live_spot is None and candles:
            live_spot = float(candles[-1]["close"])
    if chart_hours and len(frame):
        cut_lv = frame.index[-1] - pd.Timedelta(hours=int(chart_hours))
        levels = _levels_at(
            frame[frame.index >= cut_lv],
            cfg,
            all_hours=is_crypto,
            live_spot=live_spot,
        )
    else:
        levels = _levels_at(frame, cfg, all_hours=is_crypto, live_spot=live_spot)
    # No call markers on chart — keep candles + S/R zones only
    markers: List[Dict[str, Any]] = []
    summ = pa.summarize(view_calls)

    # Per-day rollup for history UI
    by_day: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        d = by_day.setdefault(r["day"], {"n": 0, "wins": 0, "sum": 0.0})
        d["n"] += 1
        d["wins"] += int(bool(r.get("win")))
        d["sum"] += float(r["pts"] or 0)

    out = {
        "ok": True,
        "error": None,
        "cached": False,
        "stock": stock,
        "underlying": scan_key,
        "meta": meta,
        "market": "crypto" if is_crypto else "india",
        "feed": "binance" if is_crypto else "kite",
        "desk": "SCALPER",
        "logic": LOGIC_NAME,
        "logic_ver": LOGIC_VER,
        "cfg_name": cfg.name,
        "sr_gate": cfg.sr_gate,
        "mode": "pa_no_trap",
        "scope": scope,
        "side_gate": side_gate,
        "side_note": (
            "crypto · BUY+SELL · 24h"
            if is_crypto
            else ("option→BUY only" if side_gate == "BUY" else "BUY+SELL")
        ),
        "days": days,
        "chart_days": chart_win,
        "chart_hours": chart_hours,
        "live_fast": live,
        "n_days": len(score_days),
        "sessions": score_days,
        "n_calls": len(rows),
        "hit_pct": summ.get("hit_pct"),
        "avg_R": summ.get("avg_R"),
        "sum_pts": summ.get("sum_pts"),
        "summary": summ,
        "by_day": by_day,
        "calls": rows,
        "candles": candles,
        "markers": markers,
        "levels": levels,
        "ema34": [],  # unused — final PA has no EMA overlay requirement
        "vwap": [],
        "interval": "1m",
        "took_ms": int((time.time() - t0) * 1000),
        "live": None,
    }
    _RESULT_CACHE[cache_k] = (now, out)
    return out


def live_scalper_check(
    stock: str = "NIFTY",
    *,
    notify: bool = False,
    mode: str = "pa_no_trap",
    market: str = "india",
    **_kwargs: Any,
) -> Dict[str, Any]:
    """Evaluate today's open/latest PA call; optional desktop notify on new fire."""
    _paths()
    from prod_live.logic import pa_structure_live as pa

    meta, scan_key, side_gate, loaded_opt, is_crypto = _resolve_scan_key(
        stock, market=market
    )
    # Live poll: lean bars (crypto ~36h / India ~3d) — same as live chart path
    bars, err = _load_1m(
        scan_key,
        days=3 if not is_crypto else 2,
        crypto=is_crypto,
        force_refresh=True,
        hours=36 if is_crypto else None,
    )
    if err or bars is None or bars.empty:
        return {
            "ok": False,
            "error": err or "no_bars",
            "stock": stock,
            "market": "crypto" if is_crypto else "india",
            "live": False,
        }

    work0 = bars if is_crypto else pa.norm_1m(bars)
    atr = pa.atr14(work0["High"].values, work0["Low"].values, work0["Close"].values)
    atr_last = float(atr[-1]) if len(atr) and np.isfinite(atr[-1]) else 10.0
    cfg = _cfg_pa_final(scan_key, atr_last, crypto=is_crypto)

    today = _today()
    calls = pa.scan_session(bars, settle=False, cfg=cfg, all_hours=is_crypto)
    today_calls = [c for c in calls if c.day == today]
    if side_gate:
        today_calls = [c for c in today_calls if str(c.side).upper() == side_gate]

    if not today_calls:
        return {
            "ok": True,
            "live": False,
            "stock": stock,
            "underlying": scan_key,
            "market": "crypto" if is_crypto else "india",
            "logic": LOGIC_NAME,
            "message": "no_call_today",
        }

    latest = today_calls[-1]
    row = _enrich_call(latest, scan_key, loaded_opt, cfg)
    key = f"{scan_key}:{latest.day}:{latest.hm}:{latest.side}"
    fresh = key not in _LIVE_DEDUPE
    if fresh:
        _LIVE_DEDUPE[key] = time.strftime("%H:%M:%S")

    if notify and fresh:
        try:
            from fno_desktop_notify import notify_scalper_entry  # type: ignore

            notify_scalper_entry(row)
        except Exception:
            try:
                import fno_notify  # type: ignore

                if hasattr(fno_notify, "notify"):
                    fno_notify.notify(
                        f"SCALPER {row['side']} {scan_key} @ {row['entry']} SL {row['sl']}"
                    )
            except Exception:
                pass

    return {
        "ok": True,
        "live": True,
        "entry_fresh": fresh,
        "stock": stock,
        "underlying": scan_key,
        "market": "crypto" if is_crypto else "india",
        "logic": LOGIC_NAME,
        "decision": row["side"],
        "day": row["day"],
        "hm": row["hm"],
        "call": row,
        "n_today": len(today_calls),
    }


def scalper_tick(stock: str = "NIFTY", *, market: str = "india") -> Dict[str, Any]:
    """Latest 1m bar + live LTP for chart append (crypto uses Binance ticker)."""
    _paths()
    meta, scan_key, _, _, is_crypto = _resolve_scan_key(stock, market=market)

    if is_crypto:
        import binance_data

        ltp, ltp_err = binance_data.fetch_ltp(scan_key)
        # Prefer cached recent bars; only refresh lightly if missing
        bars, err = _load_1m(
            scan_key, days=1, crypto=True, force_refresh=False, hours=3
        )
        if bars is None or (hasattr(bars, "empty") and bars.empty):
            bars, err = _load_1m(
                scan_key, days=1, crypto=True, force_refresh=True, hours=3
            )
        if err or bars is None or bars.empty:
            # Still return LTP so UI note/details stay live
            if ltp is not None:
                now_min = int(time.time() // 60) * 60
                nd = _price_nd(float(ltp))
                px = round(float(ltp), nd)
                return {
                    "ok": True,
                    "stock": stock,
                    "underlying": scan_key,
                    "market": "crypto",
                    "feed": "binance",
                    "live": True,
                    "quote": {"last_price": px, "source": "binance"},
                    "bar": {
                        "time": now_min,
                        "open": px,
                        "high": px,
                        "low": px,
                        "close": px,
                    },
                    "candle": {
                        "time": now_min,
                        "open": px,
                        "high": px,
                        "low": px,
                        "close": px,
                    },
                }
            return {
                "ok": False,
                "error": err or ltp_err or "no_bars",
                "stock": stock,
                "market": "crypto",
            }
        ts = bars.index[-1]
        row = bars.iloc[-1]
        o = float(row["Open"])
        h = float(row["High"])
        l = float(row["Low"])
        cl = float(row["Close"])
        px = float(ltp) if ltp is not None else cl
        nd = _price_nd(px)
        # Morph last/forming minute with live LTP
        bar = {
            "time": _ts_unix(ts),
            "open": round(o, nd),
            "high": round(max(h, px), nd),
            "low": round(min(l, px), nd),
            "close": round(px, nd),
        }
        # If kline is a closed older minute, open current minute at LTP
        now_min = int(time.time() // 60) * 60
        if int(bar["time"]) < now_min:
            bar = {
                "time": now_min,
                "open": round(px, nd),
                "high": round(px, nd),
                "low": round(px, nd),
                "close": round(px, nd),
            }
        return {
            "ok": True,
            "stock": stock,
            "underlying": scan_key,
            "market": "crypto",
            "feed": "binance",
            "live": True,
            "quote": {
                "last_price": round(px, nd),
                "source": "binance",
            },
            "bar": bar,
            "candle": bar,
        }

    bars, err = _load_1m(scan_key, days=2, crypto=False, force_refresh=True)
    if err or bars is None or bars.empty:
        return {
            "ok": False,
            "error": err or "no_bars",
            "stock": stock,
            "market": "india",
        }
    ts = bars.index[-1]
    row = bars.iloc[-1]
    bar = {
        "time": _ts_unix(ts),
        "open": round(float(row["Open"]), 2),
        "high": round(float(row["High"]), 2),
        "low": round(float(row["Low"]), 2),
        "close": round(float(row["Close"]), 2),
    }
    return {
        "ok": True,
        "stock": stock,
        "underlying": scan_key,
        "market": "india",
        "feed": "kite",
        "bar": bar,
        "candle": bar,
    }


def crypto_top10() -> Dict[str, Any]:
    _paths()
    import binance_data

    return {"ok": True, "market": "crypto", "results": binance_data.list_top10()}


# Compat aliases used by older UI paths
def scan_oracle_live_fast(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return live_scalper_check(*args, **kwargs)
