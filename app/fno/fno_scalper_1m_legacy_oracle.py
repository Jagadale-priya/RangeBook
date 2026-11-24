"""F&O Scalper desk — Oracle T15 (default) + HHLL T15 structure mode.

Modes:
  oracle_t15 — textbook events · EMA34 trail · T15
  hhll_t15   — HL/LH confirm + HTF + ATR≥14 + Desk + streak≥4 · EMA34 trail · T15

  GET /fno/scalper/chart?stock=NIFTY&days=2&chart_days=1&mode=hhll_t15
  GET /fno/scalper/live?stock=NIFTY&notify=1&mode=hhll_t15
  GET /fno/scalper/tick?stock=NIFTY
"""
from __future__ import annotations

import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BUILDERS = ROOT / "prod_live" / "tests" / "builders"
MAX_BARS = 120
GAP_MINS = 15  # min minutes between scalper entries (multi-call OK)
_LIVE_DEDUPE: Dict[str, str] = {}
_LAST_SCAN: Dict[str, float] = {}
_BAR_CACHE: Dict[str, Tuple[float, pd.DataFrame, Optional[str]]] = {}
_BAR_TTL = 25.0  # reuse hist; live path invalidates when last closed minute advances
_LIVE_CACHE_TTL = 2.0  # entry scan reuse — keep short so gates flip faster
# Heavy frame + setup enrich (reuse across mode / chart_days flips)
_FRAME_CACHE: Dict[str, Tuple[float, pd.DataFrame, List[dict], Optional[str]]] = {}
_FRAME_TTL = 90.0
# Assembled scan after path trail (reuse chart_days flip)
_RESULT_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_RESULT_TTL = 45.0
# Oracle live: reuse textbook frame until a new 1m bar closes
_ORACLE_FAST_CACHE: Dict[str, Tuple[str, Dict[str, Any]]] = {}
# Last ENTRY that notified (or was entry_fresh) — chart must show this bar at the same time
_PINNED_ENTRY: Dict[str, dict] = {}
_RESEARCH_WARMED = False
# Index CSV is huge — keep normalized once; slice per request
_CSV_NORM_CACHE: Dict[str, Tuple[float, pd.DataFrame]] = {}
_CSV_NORM_TTL = 300.0
# When Kite access token is dead, skip Connect calls for a while (fail-fast)
_KITE_DEAD_UNTIL = 0.0
_KITE_DEAD_NOTE: Optional[str] = None
_KITE_DEAD_TTL = 180.0
# ENTRY toast grace after bar close (Kite hist / scan lag)
_ENTRY_FRESH_MAX_AGE_MIN = 4
_ENTRY_FRESH_MAX_SEC = 210.0


def _ensure_paths() -> None:
    for p in (str(ROOT), str(BUILDERS), str(ROOT / "tools" / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import path_setup  # noqa: F401
    except Exception:
        pass


def _warm_research_imports() -> None:
    """Import heavy research modules once so first dropdown change is not cold."""
    global _RESEARCH_WARMED
    if _RESEARCH_WARMED:
        return
    _ensure_paths()
    try:
        import research_nifty_1m_candle_textbook_deep  # noqa: F401
        import research_nifty_1m_pattern_behavior_then_100  # noqa: F401
        import research_nifty_1m_scalp_prevcandle_100  # noqa: F401
        import research_nifty_1m_scalp_fwd_nov9_hold  # noqa: F401
        import research_nifty_1m_vix_candle_adaptive  # noqa: F401
        from _diag_scalp_ma_lastyear_init import add_ma_layers  # noqa: F401
        from _diag_scalp_ma_hold100_indicators import add_indicators  # noqa: F401
        _RESEARCH_WARMED = True
    except Exception:
        # Still mark warmed to avoid import storm; build_frame will raise clearly
        _RESEARCH_WARMED = True


def _norm_bars(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    if "date" in work.columns and not isinstance(work.index, pd.DatetimeIndex):
        work["date"] = pd.to_datetime(work["date"], utc=False)
        work = work.set_index("date")
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index, utc=False)
    if work.index.tz is None:
        work.index = work.index.tz_localize("Asia/Kolkata")
    else:
        work.index = work.index.tz_convert("Asia/Kolkata")
    rename = {c: str(c).title() for c in work.columns}
    work = work.rename(columns=rename)
    # kite lower-case
    for a, b in (("Open", "Open"), ("High", "High"), ("Low", "Low"), ("Close", "Close"), ("Volume", "Volume")):
        if a not in work.columns:
            for c in list(work.columns):
                if str(c).lower() == a.lower():
                    work = work.rename(columns={c: a})
    keep = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in work.columns]
    work = work[keep].sort_index()
    work = work[~work.index.duplicated(keep="last")]
    # Vectorized session filter (strftime on 500k rows is ~40s)
    mins = work.index.hour * 60 + work.index.minute
    return work[(mins >= 9 * 60 + 15) & (mins <= 15 * 60 + 29)]


def _ws_ticks_alive(key: str = "NIFTY") -> bool:
    """True when F&O chart feed (KiteTicker) has a fresh LTP — token is usable."""
    try:
        import kite_ticker

        tick = kite_ticker.get_tick(key)
        if not tick or tick.get("last_price") is None:
            return False
        # updated within last 2 minutes counts as live session
        raw = tick.get("updated_at_ist")
        if not raw:
            return True
        ts = pd.Timestamp(raw)
        if ts.tzinfo is None:
            ts = ts.tz_localize("Asia/Kolkata")
        age = (_now_ist() - ts.tz_convert("Asia/Kolkata")).total_seconds()
        return age <= 120
    except Exception:
        return False


def _mark_kite_dead(note: Optional[str]) -> None:
    global _KITE_DEAD_UNTIL, _KITE_DEAD_NOTE
    msg = str(note or "")
    if not msg:
        return
    # Never blackhole hist when WS is already proving the session is live
    if _ws_ticks_alive("NIFTY"):
        _KITE_DEAD_UNTIL = 0.0
        _KITE_DEAD_NOTE = None
        return
    low = msg.lower()
    if "token expired" in low or "invalid token" in low or "incorrect `api_key`" in low:
        _KITE_DEAD_UNTIL = time.time() + _KITE_DEAD_TTL
        _KITE_DEAD_NOTE = msg


def _clear_kite_dead() -> None:
    global _KITE_DEAD_UNTIL, _KITE_DEAD_NOTE
    _KITE_DEAD_UNTIL = 0.0
    _KITE_DEAD_NOTE = None


def _kite_is_dead() -> bool:
    if _ws_ticks_alive("NIFTY"):
        return False
    return time.time() < _KITE_DEAD_UNTIL


def _now_ist():
    try:
        from zoneinfo import ZoneInfo

        return pd.Timestamp.now(tz=ZoneInfo("Asia/Kolkata"))
    except Exception:
        return pd.Timestamp.now(tz="Asia/Kolkata")


def _session_open_now() -> bool:
    now = _now_ist()
    if int(now.weekday()) >= 5:
        return False
    mins = int(now.hour * 60 + now.minute)
    return (9 * 60 + 15) <= mins <= (15 * 60 + 30)


def _bust_caches_if_missing_today(key: str) -> None:
    """Drop caches that stop before today, or lag behind expected open minutes."""
    if not _session_open_now():
        return
    today = str(_now_ist().date())
    now_m = int(_now_ist().hour * 60 + _now_ist().minute)
    expect = max(1, min(now_m, 15 * 60 + 29) - (9 * 60 + 15) + 1)

    def _hi_day(df: pd.DataFrame) -> str:
        try:
            return str(pd.Timestamp(df.index.max()).tz_convert("Asia/Kolkata").date())
        except Exception:
            return str(pd.Timestamp(df.index.max()).date())

    def _today_n(df: pd.DataFrame) -> int:
        try:
            return int(sum(1 for ts in df.index if str(pd.Timestamp(ts).tz_convert("Asia/Kolkata").date()) == today))
        except Exception:
            return int(sum(1 for ts in df.index if str(pd.Timestamp(ts).date()) == today))

    for ck in list(_BAR_CACHE.keys()):
        if not ck.startswith(f"{key}:"):
            continue
        _ts0, df, _note = _BAR_CACHE[ck]
        if df is None or df.empty:
            _BAR_CACHE.pop(ck, None)
            continue
        hi = _hi_day(df)
        if hi < today or _today_n(df) < max(1, expect - 2):
            _BAR_CACHE.pop(ck, None)
    for ck in list(_RESULT_CACHE.keys()):
        if ck.startswith(f"{key}:"):
            payload = _RESULT_CACHE[ck][1] if _RESULT_CACHE[ck] else None
            day_hi = str((payload or {}).get("day_hi") or "")
            cdays = list((payload or {}).get("_candle_days") or [])
            today_n = sum(1 for d in cdays if d == today)
            if (day_hi and day_hi < today) or (cdays and today_n < max(1, expect - 2)):
                _RESULT_CACHE.pop(ck, None)
    for ck in list(_FRAME_CACHE.keys()):
        if not ck.startswith(f"{key}:"):
            continue
        hit = _FRAME_CACHE.get(ck)
        if not hit or hit[1] is None or not len(hit[1]):
            _FRAME_CACHE.pop(ck, None)
            continue
        df = hit[1]
        if _hi_day(df) < today or _today_n(df) < max(1, expect - 2):
            _FRAME_CACHE.pop(ck, None)


def _live_quote_ltp(key: str) -> Optional[Dict[str, Any]]:
    try:
        import kite_data

        q, _err = kite_data.fetch_live_quote(key)
        if q and q.get("last_price") is not None:
            return q
    except Exception:
        return None
    return None


def _ensure_today_forming_candle(candles: List[dict], key: str = "NIFTY") -> List[dict]:
    """Append/update today's minute bar from kite_ws so chart isn't stuck on prior close."""
    if not candles:
        candles = []
    else:
        candles = list(candles)
    q = _live_quote_ltp(key)
    if not q or not _session_open_now():
        return candles
    ltp = float(q["last_price"])
    now = _now_ist()
    minute = now.replace(second=0, microsecond=0)
    t_unix = int(minute.timestamp())
    today = str(now.date())
    # Drop trailing prior-day-only gap: if last candle is before today, start a new bar
    if candles:
        last_t = int(candles[-1].get("time") or 0)
        try:
            last_day = str(pd.Timestamp(last_t, unit="s", tz="UTC").tz_convert("Asia/Kolkata").date())
        except Exception:
            last_day = ""
        if last_t == t_unix:
            bar = dict(candles[-1])
            bar["close"] = round(ltp, 2)
            bar["high"] = round(max(float(bar.get("high") or ltp), ltp), 2)
            bar["low"] = round(min(float(bar.get("low") or ltp), ltp), 2)
            candles[-1] = bar
            return candles
        if last_day == today and last_t < t_unix:
            # advance forming minute
            candles.append({
                "time": t_unix,
                "open": round(ltp, 2),
                "high": round(ltp, 2),
                "low": round(ltp, 2),
                "close": round(ltp, 2),
            })
            return candles
        if last_day and last_day < today:
            candles.append({
                "time": t_unix,
                "open": round(ltp, 2),
                "high": round(ltp, 2),
                "low": round(ltp, 2),
                "close": round(ltp, 2),
            })
            return candles
    else:
        candles.append({
            "time": t_unix,
            "open": round(ltp, 2),
            "high": round(ltp, 2),
            "low": round(ltp, 2),
            "close": round(ltp, 2),
        })
    return candles


def _read_csv_tail(path: Path, approx_rows: int = 12000) -> pd.DataFrame:
    """Read only the end of a large kite CSV (header + last ~N rows)."""
    from io import BytesIO

    size = path.stat().st_size
    # ~90 bytes/row for these files; pad for safety
    nbytes = min(size, max(50_000, int(approx_rows) * 120))
    with path.open("rb") as f:
        header = f.readline()
        if size <= nbytes:
            rest = f.read()
        else:
            f.seek(-nbytes, 2)
            f.readline()  # drop partial first line
            rest = f.read()
    return pd.read_csv(BytesIO(header + rest))


def _load_index_csv_norm(csv_stock: str, keep_days: int = 22) -> Optional[pd.DataFrame]:
    """Normalized recent index CSV slice, cached — never norm 500k rows per tick."""
    csv_map = {
        "NIFTY": ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_1m_kite.csv",
        "BANKNIFTY": ROOT / "stock_signal_data" / "fno_validate" / "BANKNIFTY_1m_kite.csv",
        "SENSEX": ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_1m_kite.csv",
    }
    path = csv_map.get(csv_stock)
    if not path or not path.is_file():
        return None
    now = time.time()
    keep_days = int(max(2, min(int(keep_days or 22), 40)))
    cache_key = f"{csv_stock}:{keep_days}"
    hit = _CSV_NORM_CACHE.get(cache_key)
    mtime = path.stat().st_mtime
    if hit and (now - hit[0]) < _CSV_NORM_TTL and hit[1] is not None and len(hit[1]):
        if hit[0] >= mtime:
            return hit[1]
    # Tail-read only (~375 bars/day × keep_days) — full CSV parse was 30–40s
    approx = int((keep_days + 3) * 420) + 500
    df = _read_csv_tail(path, approx_rows=approx)
    if "date" not in df.columns and "Date" in df.columns:
        df = df.rename(columns={"Date": "date"})
    if "date" not in df.columns:
        return None
    df["date"] = pd.to_datetime(df["date"], utc=False)
    hi = df["date"].max()
    if pd.isna(hi):
        return None
    df = df[df["date"] >= (hi - pd.Timedelta(days=keep_days + 2))]
    raw = _norm_bars(df)
    _CSV_NORM_CACHE[cache_key] = (max(now, mtime), raw)
    return raw


def _yf_index_symbol(key: str) -> Optional[str]:
    return {
        "NIFTY": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "SENSEX": "^BSESN",
    }.get(str(key or "").upper())


def _load_yf_index_1m(key: str, days: int) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Yahoo 1m for index spot when Kite hist is dead — keeps Oracle live/notify moving."""
    yf_sym = _yf_index_symbol(key)
    if not yf_sym:
        return None, None
    try:
        import yfinance as yf

        days = int(max(1, min(int(days or 1), 7)))
        # Yahoo 1m max ~7d; prefer short period for speed
        period = "1d" if days <= 1 else ("5d" if days <= 5 else "7d")
        df = yf.download(
            yf_sym,
            interval="1m",
            period=period,
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if df is None or df.empty:
            return None, f"yahoo empty ({yf_sym})"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [str(c[0]).title() for c in df.columns]
        else:
            df.columns = [str(c).title() for c in df.columns]
        raw = _norm_bars(df)
        if raw is None or raw.empty:
            return None, f"yahoo norm empty ({yf_sym})"
        return raw, f"yahoo_1m·{yf_sym}"
    except Exception as exc:
        return None, f"yahoo: {exc}"


def load_1m_bars(stock: str, days: int) -> Tuple[pd.DataFrame, Optional[str]]:
    """Load 1m bars: Kite preferred; Yahoo/CSV fallback for indices when token is dead."""
    import fno_scalper_symbol as sym

    meta = sym.resolve(stock)
    key = str(meta.get("key") or stock or "NIFTY")
    days = int(max(1, min(int(days or 5), 15)))
    cache_key = f"{key}:{days}"
    now = time.time()
    hit = _BAR_CACHE.get(cache_key)
    if hit and (now - hit[0]) < _BAR_TTL and hit[1] is not None and len(hit[1]):
        return hit[1].copy(), hit[2]

    note = None
    try:
        import kite_data

        if kite_data.kite_enabled() and not _kite_is_dead():
            df, err = kite_data.fetch_historical_candles(
                key, interval="minute", days=days + 2, keep_partial=True
            )
            if df is not None and len(df):
                raw = _norm_bars(df)
                if len(raw):
                    _clear_kite_dead()
                    _BAR_CACHE[cache_key] = (now, raw, None)
                    return raw.copy(), None
            note = err or "kite empty"
            _mark_kite_dead(note)
        elif _kite_is_dead():
            # One soft retry: F&O desk may already hold a live vault token
            try:
                import kite_auth

                kite_auth.reload_access_token_from_env_file()
                tok, _terr = kite_auth.get_access_token()
                if tok:
                    _clear_kite_dead()
                    df, err = kite_data.fetch_historical_candles(
                        key, interval="minute", days=days + 2, keep_partial=True
                    )
                    if df is not None and len(df):
                        raw = _norm_bars(df)
                        if len(raw):
                            _BAR_CACHE[cache_key] = (now, raw, None)
                            return raw.copy(), None
                    note = err or _KITE_DEAD_NOTE or "kite empty"
                    _mark_kite_dead(note)
                else:
                    note = _KITE_DEAD_NOTE or "Kite token expired (cached)"
            except Exception:
                note = _KITE_DEAD_NOTE or "Kite token expired (cached)"
    except Exception as exc:
        note = f"kite: {exc}"
        _mark_kite_dead(note)

    # Index fallbacks: prefer live Yahoo 1m over stale CSV when today is missing
    csv_stock = key if ":" not in key else str(meta.get("underlying") or "")
    if meta.get("kind") == "index" or _yf_index_symbol(csv_stock):
        today = _now_ist().strftime("%Y-%m-%d")
        csv_raw = None
        if meta.get("kind") == "index":
            full = _load_index_csv_norm(csv_stock, keep_days=max(days + 3, 10))
            if full is not None and len(full):
                hi = full.index.max()
                lo = hi - pd.Timedelta(days=days + 1)
                csv_raw = full[full.index >= lo]
                csv_has_today = any(str(ts.date()) == today for ts in csv_raw.index)
                if csv_has_today:
                    stale = None
                    combined = note
                    _BAR_CACHE[cache_key] = (now, csv_raw, combined)
                    return csv_raw.copy(), combined

        yf_raw, yf_note = _load_yf_index_1m(csv_stock or key, days=days)
        if yf_raw is not None and len(yf_raw):
            combined = " · ".join(x for x in (note, yf_note) if x)
            _BAR_CACHE[cache_key] = (now, yf_raw, combined or yf_note)
            return yf_raw.copy(), combined or yf_note

        if csv_raw is not None and len(csv_raw):
            hi = csv_raw.index.max()
            stale = f"csv_stale·last {hi.strftime('%Y-%m-%d %H:%M')}"
            combined = " · ".join(x for x in (note, yf_note, stale) if x)
            _BAR_CACHE[cache_key] = (now, csv_raw, combined)
            return csv_raw.copy(), combined

    return pd.DataFrame(), note or "no 1m source"


def path_ma_trail(h, l, c, ma, i, side, t1_pts, max_bars=MAX_BARS):
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    if side == "BUY":
        t1 = entry + t1_pts
        for j in range(i + 1, end + 1):
            hi, cl, m = float(h[j]), float(c[j]), float(ma[j])
            if not np.isfinite(m):
                return False, "bad", entry, i, 0.0
            if hi >= t1:
                return True, "t1", float(t1), j, float(t1_pts)
            if cl < m:
                return False, "ma_sl", cl, j, cl - entry
        px = float(c[end])
        return False, "exp", px, end, px - entry
    t1 = entry - t1_pts
    for j in range(i + 1, end + 1):
        lo, cl, m = float(l[j]), float(c[j]), float(ma[j])
        if not np.isfinite(m):
            return False, "bad", entry, i, 0.0
        if lo <= t1:
            return True, "t1", float(t1), j, float(t1_pts)
        if cl > m:
            return False, "ma_sl", cl, j, entry - cl
    px = float(c[end])
    return False, "exp", px, end, entry - px


def _build_frame(raw: pd.DataFrame):
    _ensure_paths()
    import research_nifty_1m_candle_textbook_deep as tb
    import research_nifty_1m_pattern_behavior_then_100 as beh
    from _diag_scalp_ma_lastyear_init import add_ma_layers
    from _diag_scalp_ma_hold100_indicators import add_indicators

    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    return df


def _collect_events(df: pd.DataFrame, day_lo: str, day_hi: str) -> List[dict]:
    _ensure_paths()
    import research_nifty_1m_scalp_prevcandle_100 as scalp

    return scalp.collect_scalp_events(df, day_lo, day_hi)


def _enrich(events: List[dict], df: pd.DataFrame) -> None:
    _ensure_paths()
    import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod
    import research_nifty_1m_vix_candle_adaptive as vixmod
    from _diag_scalp_structure_vix_analyze import enrich_structure
    from _diag_scalp_fail3_t20_sl10 import enrich_prior3
    from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep
    from _diag_scalp_ma_lastyear_init import enrich_ma_layers
    from _diag_scalp_ma_hold100_indicators import enrich_ind

    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    vix = vixmod.load_vix()
    fwdmod.enrich_evt(events, h, l, c, o)
    enrich_structure(events, h, l, c, o, vix)
    enrich_prior3(events, h, l, c, o)
    enrich_deep(events, h, l, c, o, df)
    enrich_ma_layers(events, df)
    enrich_ind(events, df)


def _held_gate(e: dict) -> bool:
    import fno_scalper_setup as setup

    return setup.held_gate(e)


def _bar_unix(ts) -> int:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("Asia/Kolkata")
    else:
        t = t.tz_convert("Asia/Kolkata")
    return int(t.timestamp())


def _candles_payload(df: pd.DataFrame) -> List[dict]:
    if df is None or df.empty:
        return []
    times = [_bar_unix(ts) for ts in df.index]
    o = df["Open"].astype(float).to_numpy()
    h = df["High"].astype(float).to_numpy()
    l = df["Low"].astype(float).to_numpy()
    c = df["Close"].astype(float).to_numpy()
    return [
        {
            "time": times[i],
            "open": round(float(o[i]), 2),
            "high": round(float(h[i]), 2),
            "low": round(float(l[i]), 2),
            "close": round(float(c[i]), 2),
        }
        for i in range(len(times))
    ]


def _parse_interval_mins(raw: Any) -> int:
    s = str(raw or "1").strip().lower().replace("min", "").replace("m", "")
    try:
        n = int(float(s))
    except (TypeError, ValueError):
        n = 1
    return 5 if n >= 5 else (2 if n >= 2 else 1)


def _resample_minutes(df: pd.DataFrame, mins: int) -> pd.DataFrame:
    """Aggregate 1m OHLC to 2m/5m for chart display (logic stays on 1m)."""
    mins = _parse_interval_mins(mins)
    if mins <= 1 or df is None or df.empty:
        return df
    work = df.copy()
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in work.columns:
        agg["Volume"] = "sum"
    rule = f"{mins}min"
    out = work.resample(rule, label="left", closed="left").agg(agg)
    out = out.dropna(subset=["Open", "High", "Low", "Close"])
    # Display EMA/VWAP on the chart TF (signals still come from 1m scan)
    out["ema34"] = out["Close"].ewm(span=34, adjust=False).mean()
    if "Volume" in out.columns:
        typ = (out["High"] + out["Low"] + out["Close"]) / 3.0
        vol = out["Volume"].fillna(0.0).clip(lower=0.0)
        day = out.index.strftime("%Y-%m-%d")
        pv = typ * vol
        out["vwap"] = pv.groupby(day).cumsum() / vol.groupby(day).cumsum().replace(0, np.nan)
    elif "vwap" in df.columns:
        # sample last 1m vwap into the bar
        out["vwap"] = df["vwap"].resample(rule, label="left", closed="left").last()
    hm = out.index.strftime("%H:%M")
    return out[(hm >= "09:15") & (hm <= "15:29")]


def _snap_marker_time(unix_t: Any, mins: int) -> Any:
    """Floor marker time to the interval bar open (IST session)."""
    mins = _parse_interval_mins(mins)
    if mins <= 1 or unix_t is None:
        return unix_t
    try:
        t = pd.Timestamp(int(unix_t), unit="s", tz="UTC").tz_convert("Asia/Kolkata")
        # Session-relative floor: minutes since 09:15
        sod = t.normalize() + pd.Timedelta(hours=9, minutes=15)
        if t < sod:
            return int(sod.timestamp())
        delta_min = int((t - sod).total_seconds() // 60)
        floored = sod + pd.Timedelta(minutes=(delta_min // mins) * mins)
        return int(floored.timestamp())
    except Exception:
        return unix_t


def _snap_markers(markers: List[dict], mins: int) -> List[dict]:
    mins = _parse_interval_mins(mins)
    if mins <= 1:
        return markers
    out = []
    seen = set()
    for m in markers or []:
        mm = dict(m)
        mm["time"] = _snap_marker_time(mm.get("time"), mins)
        key = (mm.get("time"), mm.get("text"), mm.get("shape"), mm.get("position"))
        if key in seen:
            continue
        seen.add(key)
        out.append(mm)
    return out


def _ema_series(df: pd.DataFrame, col: str = "ema34") -> List[dict]:
    if col not in df.columns or df is None or df.empty:
        return []
    out = []
    vals = df[col].astype(float)
    for ts, val in vals.items():
        if pd.isna(val) or not np.isfinite(val) or float(val) <= 0:
            continue
        out.append({"time": _bar_unix(ts), "value": round(float(val), 2)})
    return out


def _get_prepared_frame(
    key: str,
    days: int,
    raw: pd.DataFrame,
    note: Optional[str],
) -> Tuple[Optional[pd.DataFrame], Optional[List[dict]], Optional[str]]:
    """Return df + setup-enriched events; cache to keep dropdown flips under ~10s."""
    import copy

    import fno_scalper_setup as setup

    _warm_research_imports()
    ck = f"{key}:{int(days)}"
    now = time.time()
    hit = _FRAME_CACHE.get(ck)
    if hit and (now - hit[0]) < _FRAME_TTL and hit[1] is not None and hit[2] is not None:
        cached_df = hit[1]
        # Bust when fresh hist advanced past the cached frame (new minute / new day)
        try:
            if (
                raw is not None
                and len(raw)
                and cached_df is not None
                and len(cached_df)
                and pd.Timestamp(raw.index.max()) > pd.Timestamp(cached_df.index.max())
            ):
                _FRAME_CACHE.pop(ck, None)
            else:
                return hit[1], copy.deepcopy(hit[2]), hit[3]
        except Exception:
            return hit[1], copy.deepcopy(hit[2]), hit[3]

    try:
        df = _build_frame(raw)
    except Exception as exc:
        return None, None, f"frame build failed: {exc}"
    day_lo = str(df.index.min().date())
    day_hi = str(df.index.max().date())
    try:
        events = _collect_events(df, day_lo, day_hi)
        _enrich(events, df)
        setup.apply_setup_enrichment(events, df)
    except Exception as exc:
        return None, None, f"event scan failed: {exc}"

    _FRAME_CACHE[ck] = (now, df, copy.deepcopy(events), note)
    return df, events, note


def _slice_chart_payload(payload: Dict[str, Any], chart_days: int) -> Dict[str, Any]:
    """Fast path: reuse a cached mode scan and only re-slice candles/markers.

    Chart window MUST follow candle calendar days — never call/event days.
    Otherwise before the first today call, keep={yesterday} and all today 1m
    bars are dropped (only a single LTP forming candle remains). That is the
    "stuck on same candles after open" Scalper bug.
    """
    out = dict(payload)
    chart_days = int(max(1, min(int(chart_days or 1), 15)))
    all_candles = list(payload.get("_all_candles") or payload.get("candles") or [])
    all_ema = list(payload.get("_all_ema34") or payload.get("ema34") or [])
    all_vwap = list(payload.get("_all_vwap") or payload.get("vwap") or [])
    all_markers = list(payload.get("_all_markers") or payload.get("markers") or [])
    cdays = list(payload.get("_candle_days") or [])
    # Prefer unique candle days (includes today even when silent on calls)
    day_list = sorted({d for d in cdays if d})
    if not day_list:
        day_list = list(payload.get("_days_sorted") or [])
    if not day_list and payload.get("calls"):
        day_list = sorted({c.get("day") for c in payload["calls"] if c.get("day")})
    keep = set(day_list[-chart_days:]) if day_list else set()
    # Live session: always keep today when we have today bars in the series
    today = str(_now_ist().date())
    if today in set(cdays):
        keep.add(today)
    if keep and all_candles:
        if cdays and len(cdays) == len(all_candles):
            out["candles"] = [c for c, d in zip(all_candles, cdays) if d in keep]
            keep_times = {c["time"] for c in out["candles"]}
            out["ema34"] = [p for p in all_ema if p.get("time") in keep_times]
            out["vwap"] = [p for p in all_vwap if p.get("time") in keep_times]
        else:
            n = max(1, int(round(len(all_candles) * chart_days / max(len(day_list), 1))))
            out["candles"] = all_candles[-n:]
            keep_times = {c["time"] for c in out["candles"]}
            out["ema34"] = [p for p in all_ema if p.get("time") in keep_times]
            out["vwap"] = [p for p in all_vwap if p.get("time") in keep_times]
        marker_days = payload.get("_marker_days") or []
        if marker_days and len(marker_days) == len(all_markers):
            out["markers"] = [m for m, d in zip(all_markers, marker_days) if d in keep]
        else:
            out["markers"] = all_markers
    else:
        out["candles"] = all_candles
        out["ema34"] = all_ema
        out["vwap"] = all_vwap
        out["markers"] = all_markers
    out["chart_days"] = chart_days
    # Morph/append forming minute from LTP — never a substitute for missing hist bars
    key = str(out.get("key") or out.get("stock") or "NIFTY")
    out["candles"] = _ensure_today_forming_candle(list(out.get("candles") or []), key)
    # Strip internal cache helpers from API response
    for k in ("_all_candles", "_all_ema34", "_all_vwap", "_all_markers",
              "_days_sorted", "_candle_days", "_marker_days"):
        out.pop(k, None)
    return out


def _call_row(e: dict, t1: float) -> Dict[str, Any]:
    """Table row only — no Why-panel gates / indicator payload."""
    import fno_scalper_setup as setup

    bits = setup.setup_why_bits(e)
    tier = bits.get("setup_tier")
    entry = round(float(e.get("entry") or 0), 2)
    t1f = float(t1)
    return {
        "day": e.get("day"),
        "hm": e.get("hm"),
        "decision": e.get("decision"),
        "primary": e.get("primary"),
        "entry": entry,
        "t1": t1f,
        "target": round(entry + (t1f if e.get("decision") == "BUY" else -t1f), 2),
        "exit_hm": e.get("_exit_hm"),
        "exit_px": e.get("_exit_px"),
        "reason": e.get("_reason"),
        "pts": e.get("_pts"),
        "win": e.get("_win"),
        "book": e.get("_book"),
        "setup_tier": tier,
        "setup_label": bits.get("setup_label"),
    }


def _resample_15m(raw: pd.DataFrame) -> pd.DataFrame:
    work = raw.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index)
    agg = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
    }
    if "Volume" in work.columns:
        agg["Volume"] = "sum"
    ohlc = work.resample("15min", label="left", closed="left").agg(agg)
    ohlc = ohlc.dropna(subset=["Open", "High", "Low", "Close"])
    if ohlc.empty:
        return ohlc
    hm = ohlc.index.strftime("%H:%M")
    return ohlc[(hm >= "09:15") & (hm <= "15:15")]


def scan_overlay_100(stock: str = "NIFTY", days: int = 5) -> Dict[str, Any]:
    """Retired — overlay indication removed from Scalper."""
    return {
        "ok": False,
        "error": "Overlay indication removed. Use Setup A/B or Oracle; desk calls = dual accurate.",
        "stock": stock,
        "mode": "overlay_100",
        "disabled": True,
        "overlay_100": False,
        "markers": [],
        "calls": [],
        "candles": [],
    }
    # --- retired ---
    _ensure_paths()
    import fno_overlay_indication as foi
    import overlay_indication_store as ois

    # Force 100 floor for this mode regardless of env during scan
    prev = os.environ.get("OVERLAY_ACC_MIN")
    os.environ["OVERLAY_ACC_MIN"] = "100"
    try:
        raw, note = load_1m_bars(stock, days)
        if raw is None or raw.empty:
            return {"ok": False, "error": note or "No 1m bars", "stock": stock, "mode": "overlay_100"}

        all_days = sorted({str(ts.date()) for ts in raw.index})
        keep_days = set(all_days[-int(max(1, min(days, 15))) :])
        raw = raw[[str(ts.date()) in keep_days for ts in raw.index]]
        if raw.empty:
            return {"ok": False, "error": "No bars in selected days", "stock": stock, "mode": "overlay_100"}

        # Warmup history so OR/CPR/prior-day atoms match research
        raw_w, _ = load_1m_bars(stock, max(days, 22))
        if raw_w is None or raw_w.empty:
            raw_w = raw
        df15 = _resample_15m(raw_w)

        calls: List[dict] = []
        markers: List[dict] = []
        seen_bar: set = set()
        last_side_i: Dict[str, int] = {}
        for i in range(max(80, 0), len(df15)):
            day = str(pd.Timestamp(df15.index[i]).tz_convert("Asia/Kolkata").date())
            if day not in keep_days:
                continue
            # Pass full frame + absolute index so ATR/overlays see prior sessions
            sig = foi.evaluate_bar(df15, symbol=stock, i=i)
            if not sig or sig.get("decision") not in ("BUY", "SELL"):
                continue
            if float(sig.get("best_acc_1m") or 0) < 99.5:
                continue
            side = str(sig["decision"])
            hm = pd.Timestamp(df15.index[i]).tz_convert("Asia/Kolkata").strftime("%H:%M")
            dedupe_key = f"{day}|{hm}|{side}"
            if dedupe_key in seen_bar:
                continue
            # Chart hygiene: at most one same-side fire every 4×15m bars (~1h)
            prev_i = last_side_i.get(side)
            if prev_i is not None and (i - prev_i) < 4:
                continue
            seen_bar.add(dedupe_key)
            last_side_i[side] = i

            entry = float(sig.get("entry") or df15["Close"].iloc[i])
            atr = float(sig.get("atr") or 0)
            ts = df15.index[i]
            t_unix = _bar_unix(ts)
            labels = list(sig.get("rule_labels") or [])
            rule_ids = list(sig.get("rule_ids") or [])
            book_lbl = sig.get("book_profit_label") or ""
            stop_lbl = sig.get("stop_label") or ""

            # Research outcome: path-first 0.35×ATR within ~8×15m bars
            win = foi.path_hit(df15, i, side, atr)
            end_j = min(len(df15) - 1, i + foi.PATH_MAX_BARS)
            exit_px = round(float(df15["Close"].iloc[end_j]), 2)
            exit_hm = pd.Timestamp(df15.index[end_j]).tz_convert("Asia/Kolkata").strftime("%H:%M")
            pts = round((exit_px - entry) if side == "BUY" else (entry - exit_px), 2)
            reason = "path" if win is True else ("path_miss" if win is False else None)

            call = {
                "day": day,
                "hm": hm,
                "decision": side,
                "primary": (rule_ids[0] if rule_ids else "overlay_100"),
                "entry": round(entry, 2),
                "t1": None,
                "target": None,
                "exit_hm": exit_hm,
                "exit_px": exit_px,
                "reason": reason,
                "pts": pts,
                "win": win,
                "book": "OVERLAY_100",
                "setup_tier": "100",
                "setup_label": "Overlay 100%",
                "regime": None,
                "rule_ids": rule_ids,
                "rule_labels": labels,
                "accuracy_label": sig.get("accuracy_label"),
                "best_acc_1m": sig.get("best_acc_1m"),
                "book_profit_label": book_lbl,
                "stop_label": stop_lbl,
                "favour_minutes": sig.get("favour_minutes"),
                "med_favour_pts": sig.get("med_favour_pts"),
                "gates_text": (
                    f"GT80 100% · {labels[0] if labels else 'rule'}"
                    + (f" · +{len(labels) - 1} more" if len(labels) > 1 else "")
                ),
                "indicators": {
                    "best_acc": sig.get("best_acc_1m"),
                    "favour_mins": sig.get("favour_minutes"),
                    "med_favour": sig.get("med_favour_pts"),
                    "n_tags": sig.get("n_tags"),
                    "path_atr": foi.PATH_ATR,
                },
                "channel": "overlay_indication",
                "overlay_100": True,
                "source": "GT80_CLEAN",
            }
            calls.append(call)
            # Entry-only marker on the 15m bar (mapped onto 1m chart time)
            markers.append(
                {
                    "time": t_unix,
                    "position": "belowBar" if side == "BUY" else "aboveBar",
                    "color": "#0f766e" if side == "BUY" else "#9a3412",
                    "shape": "arrowUp" if side == "BUY" else "arrowDown",
                    "text": "100↑" if side == "BUY" else "100↓",
                }
            )

        # Persist / live = latest today
        today = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
        today_calls = [c for c in calls if c.get("day") == today]
        live = None
        if today_calls:
            live = dict(today_calls[-1])
            live["live"] = True
            live["note"] = "Overlay 100% (GT80_CLEAN) — chart markers only, no notify."
            try:
                sig_row = {
                    "symbol": stock,
                    "decision": live["decision"],
                    "side": live["decision"],
                    "entry": live["entry"],
                    "stop_loss": None,
                    "target_1": None,
                    "bar_time": f"{live['day']}T{live['hm']}:00+05:30",
                    "accuracy_label": live.get("accuracy_label"),
                    "rule_ids": live.get("rule_ids"),
                    "rule_labels": live.get("rule_labels"),
                    "best_acc_1m": live.get("best_acc_1m"),
                    "favour_minutes": live.get("favour_minutes"),
                    "med_favour_pts": live.get("med_favour_pts"),
                    "book_profit_label": live.get("book_profit_label"),
                    "stop_label": live.get("stop_label"),
                    "notify": False,
                    "overlay_indication": True,
                }
                ois.upsert_signal(sig_row)
            except Exception:
                pass

        wins = sum(1 for c in calls if c.get("win") is True)
        resolved = sum(1 for c in calls if c.get("win") is not None)
        return {
            "ok": True,
            "stock": stock,
            "mode": "overlay_100",
            "t1": None,
            "gap_mins": 15,
            "multi_call": True,
            "setup_filter": False,
            "n_tier_a": 0,
            "n_tier_b": 0,
            "n_setup_events": len(calls),
            "days_requested": days,
            "day_lo": str(pd.Timestamp(raw.index.min()).date()),
            "day_hi": str(pd.Timestamp(raw.index.max()).date()),
            "n_days": len(keep_days),
            "n_events": len(calls),
            "n_calls": len(calls),
            "hit_pct": round(100.0 * wins / resolved, 2) if resolved else None,
            "note": note,
            "disclaimer": (
                "Overlay 100% = GT80_CLEAN rules only (path-acc 100% + avg pts up). "
                "Win = first 0.35×ATR path within ~8×15m bars. Entry markers only — Scalper filter."
            ),
            "candles": _candles_payload(raw),
            "ema34": [],
            "vwap": [],
            "markers": markers,
            "calls": calls,
            "selected": calls[-1] if calls else live,
            "live": live,
            "overlay_100": True,
            "proven_rules": [
                {
                    "id": r["id"],
                    "side": r["side"],
                    "label": r["label"],
                    "n_1m": r.get("n_1m"),
                    "avg_pts": r.get("avg_pts"),
                }
                for r in foi.proven_100_rules(symbol=stock)
            ],
        }
    finally:
        if prev is None:
            os.environ.pop("OVERLAY_ACC_MIN", None)
        else:
            os.environ["OVERLAY_ACC_MIN"] = prev


def _force_refresh_symbol(key: str) -> None:
    """Drop bar/frame/result caches for one symbol so Load gets fresh 1m bars."""
    prefix = f"{str(key)}:"
    for store in (_BAR_CACHE, _FRAME_CACHE, _RESULT_CACHE):
        for ck in list(store.keys()):
            if ck.startswith(prefix):
                store.pop(ck, None)
    # Also drop day-window keys used by live/tick
    for ck in list(_BAR_CACHE.keys()):
        if ck == f"{key}:1" or ck.startswith(prefix):
            _BAR_CACHE.pop(ck, None)
    _clear_kite_dead()


def scan_scalper(
    stock: str = "NIFTY",
    days: int = 2,
    mode: str = "oracle_t15",
    chart_days: int = 1,
    interval: Any = 1,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    import fno_scalper_symbol as sym

    t_start = time.time()
    meta = sym.resolve(stock)
    key = str(meta.get("key") or stock or "NIFTY")
    kind = str(meta.get("kind") or "index")
    display = str(meta.get("display") or key)
    # CE/PE options → BUY only; index/equity → both BUY and SELL
    side_gate = sym.option_call_side(meta)
    interval_mins = _parse_interval_mins(interval)
    if force_refresh:
        _force_refresh_symbol(key)

    mode = str(mode or "oracle_t15").lower().strip()
    use_hhll = mode in ("hhll_t15", "hhll", "hl_lh", "structure_hhll")
    if use_hhll:
        mode = "hhll_t15"
    # Legacy modes → Oracle T15
    elif mode in (
        "setup_t12",
        "oracle_t12",
        "oracle_t15_clean",
        "held_t12",
        "run_ignition_100",
        "ignition_100",
        "ign100",
        "run_ign100",
        "overlay_100",
        "overlay100",
        "ov100",
        "indication_100",
    ) or mode.startswith("held_"):
        mode = "oracle_t15"
    use_ign100 = False
    default_t1 = 15.0
    use_oracle = not use_hhll
    oracle_clean = False
    require_setup = False
    days = int(max(1, min(int(days or 2), 15)))
    chart_days = int(max(1, min(int(chart_days or 1), days)))

    # Fast path: same symbol/days/mode/interval already scanned — only re-slice chart window
    _bust_caches_if_missing_today(key)
    result_key = f"{key}:{days}:{mode}:{side_gate or 'BOTH'}:{interval_mins}m"
    now = time.time()
    cached_result = None if force_refresh else _RESULT_CACHE.get(result_key)
    # Stale cache (>12s) during session → refetch bars so Load/1m chart keeps moving
    if (
        cached_result
        and (now - cached_result[0]) < _RESULT_TTL
        and (now - cached_result[0]) < 12.0
    ):
        out = _slice_chart_payload(cached_result[1], chart_days)
        # Always paint today's forming bar from WS even on cached hist scans
        out["candles"] = _ensure_today_forming_candle(list(out.get("candles") or []), key)
        out["cached"] = True
        out["side_gate"] = side_gate
        out["interval"] = f"{interval_mins}m"
        out["live_feed"] = "kite_ws"
        out["took_ms"] = int((time.time() - t_start) * 1000)
        return _merge_pinned_into_chart(key, out)
    if cached_result and (now - cached_result[0]) < _RESULT_TTL:
        # Keep markers/calls from cache but refresh candle tail from live 1m bars
        _BAR_CACHE.pop(f"{key}:{days}", None)
        _BAR_CACHE.pop(f"{key}:1", None)

    raw, note = load_1m_bars(key, days)
    if raw is None or raw.empty:
        return {
            "ok": False,
            "error": note or "No 1m bars",
            "stock": display,
            "key": key,
            "kind": kind,
            "meta": meta,
            "took_ms": int((time.time() - t_start) * 1000),
        }

    # trim to last N calendar trading days present
    all_days = sorted({str(ts.date()) for ts in raw.index})
    keep_days = set(all_days[-days:])
    raw = raw[[str(ts.date()) in keep_days for ts in raw.index]]
    if raw.empty:
        return {
            "ok": False,
            "error": "No bars in selected days",
            "stock": display,
            "key": key,
            "took_ms": int((time.time() - t_start) * 1000),
        }

    df, events, prep_err = _get_prepared_frame(key, days, raw, note)
    if df is None:
        return {
            "ok": False,
            "error": prep_err or "frame prepare failed",
            "stock": display,
            "key": key,
            "note": note,
            "took_ms": int((time.time() - t_start) * 1000),
        }
    if not use_hhll and events is None:
        return {
            "ok": False,
            "error": prep_err or "frame prepare failed",
            "stock": display,
            "key": key,
            "note": note,
            "took_ms": int((time.time() - t_start) * 1000),
        }
    if prep_err and note is None:
        note = prep_err

    day_lo = str(df.index.min().date())
    day_hi = str(df.index.max().date())
    days_sorted = sorted({str(ts.date()) for ts in df.index})
    gap = GAP_MINS

    # ---- HHLL structure mode (SHIP gate) ----
    if use_hhll:
        import fno_scalper_hhll as hhll

        scored_calls, markers, live_e, marker_days = hhll.scan_hhll(
            df, path_ma_trail=path_ma_trail, gap_mins=gap
        )
        calls = []
        for e in scored_calls:
            if side_gate and e.get("decision") != side_gate:
                continue
            row = _call_row(
                {
                    **e,
                    "_book": "HHLL_T15",
                    "_win": e.get("_win"),
                    "_reason": e.get("_reason"),
                    "_pts": e.get("_pts"),
                    "_exit_hm": e.get("_exit_hm"),
                    "_exit_px": e.get("_exit_px"),
                },
                default_t1,
            )
            row["setup_label"] = e.get("setup_label") or "HHLL_T15"
            row["struct_tag"] = e.get("struct_tag")
            row["atr"] = e.get("atr")
            row["streak"] = e.get("streak")
            row["htf"] = e.get("htf")
            calls.append(row)

        live = None
        if live_e and (not side_gate or live_e.get("decision") == side_gate):
            live = _call_row(
                {
                    **live_e,
                    "_book": "LIVE_HHLL_T15",
                    "_win": live_e.get("_win"),
                    "_reason": live_e.get("_reason"),
                    "_pts": live_e.get("_pts"),
                    "_exit_hm": live_e.get("_exit_hm"),
                    "_exit_px": live_e.get("_exit_px"),
                },
                default_t1,
            )
            live["live"] = True
            live["t1"] = default_t1
            live["underlying"] = meta.get("underlying")
            live["kind"] = kind
            live["setup_label"] = live_e.get("setup_label") or "HHLL_T15"
            live["hhll_t15"] = True
            live["struct_tag"] = live_e.get("struct_tag")
            live["gate_ok"] = True

        chart_df = _resample_minutes(df, interval_mins) if interval_mins > 1 else df
        chart_markers = _snap_markers(markers, interval_mins)
        all_candles = _candles_payload(chart_df)
        candle_days = [str(ts.date()) for ts in chart_df.index]
        all_ema = _ema_series(chart_df, "ema34")
        all_vwap = _ema_series(chart_df, "vwap") if "vwap" in chart_df.columns else []
        wins = sum(1 for c_ in calls if c_.get("win"))
        side_note = " · option→BUY only" if side_gate == "BUY" else ""
        full = {
            "ok": True,
            "stock": display,
            "key": key,
            "kind": kind,
            "meta": meta,
            "mode": mode,
            "side_gate": side_gate,
            "interval": f"{interval_mins}m",
            "interval_mins": interval_mins,
            "t1": default_t1,
            "gap_mins": gap,
            "multi_call": True,
            "hhll_t15": True,
            "days_requested": days,
            "chart_days": chart_days,
            "day_lo": day_lo,
            "day_hi": day_hi,
            "n_days": len(days_sorted),
            "n_events": len(scored_calls),
            "n_calls": len(calls),
            "hit_pct": round(100.0 * wins / len(calls), 2) if calls else None,
            "note": note,
            "disclaimer": (
                f"HHLL T15 · HL/LH confirm + HTF + (ATR≥14·Desk≥3 | ATR≥12·held) + streak≥4 · "
                f"EMA34 trail · gap {gap}m · {kind} · chart {interval_mins}m{side_note}"
            ),
            "calls": calls,
            "selected": calls[-1] if calls else live,
            "live": live,
            "_all_candles": all_candles,
            "_all_ema34": all_ema,
            "_all_vwap": all_vwap,
            "_all_markers": chart_markers,
            "_days_sorted": days_sorted,
            "_candle_days": candle_days,
            "_marker_days": list(marker_days),
        }
        # bust any stale empty caches for this key family
        _RESULT_CACHE[result_key] = (time.time(), full)
        out = _slice_chart_payload(full, chart_days)
        out["cached"] = False
        out["took_ms"] = int((time.time() - t_start) * 1000)
        return _merge_pinned_into_chart(key, out)

    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    atr_col = df["atr14"].astype(float).values if "atr14" in df.columns else None
    pdi = df["plus_di"].astype(float).values if "plus_di" in df.columns else None
    mdi = df["minus_di"].astype(float).values if "minus_di" in df.columns else None
    idx = df.index

    for e in events:
        # Proven ignition mode: score/display from ignition bar, not pattern completion
        if use_ign100 and e.get("run_ignition_ok") and e.get("ignition_i") is not None:
            i = int(e["ignition_i"])
            entry_px = float(e.get("ignition_entry") or c[i])
            e["entry"] = round(entry_px, 2)
            e["hm"] = e.get("ignition_hm") or e.get("hm")
            e["mins"] = int(e.get("ignition_mins") or e.get("mins") or 0)
        else:
            i = int(e["full_i"])
            entry_px = float(e.get("entry") or c[i])
        if pdi is not None and 0 <= i < len(pdi):
            e["plus_di"] = round(float(pdi[i]), 1)
            e["minus_di"] = round(float(mdi[i]), 1)
        atr_i = float(atr_col[i]) if atr_col is not None and 0 <= i < len(atr_col) else e.get("atr")
        t1_e = sym.t1_for(kind, entry_px, atr_i, mode)
        e["_t1"] = t1_e
        ok, reason, exit_px, j, pts = path_ma_trail(h, l, c, ema34, i, e["decision"], t1_e)
        e["_win"] = bool(ok)
        e["_reason"] = reason
        e["_exit_px"] = round(float(exit_px), 2)
        e["_exit_i"] = int(j)
        e["_pts"] = round(float(pts), 2)
        if 0 <= j < len(idx):
            e["_exit_hm"] = pd.Timestamp(idx[j]).tz_convert("Asia/Kolkata").strftime("%H:%M")
            e["_exit_time"] = _bar_unix(idx[j])
        else:
            e["_exit_hm"] = "?"
            e["_exit_time"] = None
        e["_entry_time"] = _bar_unix(idx[i]) if 0 <= i < len(idx) else None
        e["_score_i"] = i

    by = defaultdict(list)
    for e in events:
        by[str(e.get("day") or "")].append(e)

    days_sorted = sorted(k for k in by.keys() if k)
    calls = []
    markers = []
    marker_days: List[str] = []
    # Ignition book allows multiple ≥25pt moves/day — light gap only
    gap = 5 if use_ign100 else int(GAP_MINS)
    n_tier_a = 0
    n_tier_b = 0

    def _passes_side_gate(e: dict) -> bool:
        if not side_gate:
            return True
        return str(e.get("decision") or "").upper() == side_gate

    def _oracle_ema_ok(e: dict) -> bool:
        """Same with-trend filter as live notify (BUY≥EMA34 / SELL≤EMA34)."""
        try:
            i = int(e.get("_score_i"))
            side = str(e.get("decision") or "").upper()
            if side not in ("BUY", "SELL") or not (0 <= i < len(c)):
                return False
            entry = float(e.get("entry") or c[i])
            ema_i = float(ema34[i]) if np.isfinite(ema34[i]) else entry
            if side == "BUY" and entry < ema_i:
                return False
            if side == "SELL" and entry > ema_i:
                return False
            return True
        except Exception:
            return False

    def _eligible(e: dict) -> bool:
        if not _passes_side_gate(e):
            return False
        if use_ign100:
            return bool(e.get("run_ignition_ok"))
        if use_oracle:
            # Clean book stays path-win ∩ tier
            if oracle_clean:
                return bool(e.get("_win") and e.get("setup_ok"))
            # Default Oracle: same as live notify — entry at bar close (do NOT wait for T15)
            return _oracle_ema_ok(e)
        # Live / setup / held chart: only Tier A/B
        return bool(e.get("setup_ok"))

    def _book_tag(e: dict) -> str:
        t1_e = float(e.get("_t1") or default_t1)
        if use_ign100:
            return f"IGN100_T{int(round(t1_e))}"
        if use_oracle:
            if oracle_clean:
                tier = e.get("setup_tier") or "AB"
                return f"ORACLE_CLEAN_{tier}_T{int(round(t1_e))}"
            return f"ORACLE_T{int(round(t1_e))}"
        tier = e.get("setup_tier") or "?"
        return f"SETUP_{tier}_T{int(round(t1_e))}"

    def _marker_color(e: dict, side: str) -> str:
        if use_ign100:
            return "#047857" if side == "BUY" else "#9f1239"
        if use_oracle and not oracle_clean:
            return "#0b6e4f" if side == "BUY" else "#922b21"
        if e.get("setup_tier") == "A":
            return "#0f766e" if side == "BUY" else "#b45309"
        if oracle_clean or e.get("setup_tier") == "B":
            return "#2563eb" if side == "BUY" else "#7c3aed"
        return "#2563eb" if side == "BUY" else "#7c3aed"

    # Build markers for ALL scan days; chart slice filters later (fast dropdown)
    for d in days_sorted:
        rows = sorted(by[d], key=lambda x: x["mins"])
        next_ok_mins = None
        for e in rows:
            if not _eligible(e):
                continue
            mins = int(e["mins"])
            if next_ok_mins is not None and mins < next_ok_mins:
                continue
            e["_book"] = _book_tag(e)
            if e.get("setup_tier") == "A":
                n_tier_a += 1
            elif e.get("setup_tier") == "B":
                n_tier_b += 1
            t1_e = float(e.get("_t1") or default_t1)
            calls.append(_call_row(e, t1_e))
            side = e["decision"]
            tgt = round(
                float(e.get("entry") or 0)
                + (float(e.get("_t1") or default_t1) if side == "BUY" else -float(e.get("_t1") or default_t1)),
                2,
            )
            markers.append(
                {
                    "time": e["_entry_time"],
                    "position": "belowBar" if side == "BUY" else "aboveBar",
                    "color": _marker_color(e, side),
                    "shape": "arrowUp" if side == "BUY" else "arrowDown",
                    "text": f"{e['_book']} {side} → {tgt}",
                }
            )
            marker_days.append(d)
            # Exit marker only once path has a real print (T15 / MA stop) — never delay ENTRY
            if e.get("_exit_time") and (e.get("_win") or e.get("_reason") in ("t1", "ma_sl", "exp")):
                markers.append(
                    {
                        "time": e["_exit_time"],
                        "position": "aboveBar" if side == "BUY" else "belowBar",
                        "color": "#b7950b" if e["_win"] else "#7f8c8d",
                        "shape": "circle",
                        "text": f"{e['_reason']} {e['_pts']:+.0f}",
                    }
                )
                marker_days.append(d)
            # Oracle live/chart share ENTRY gap (15m) — not exit+gap (that desynced notify vs arrows)
            if use_oracle and not oracle_clean:
                next_ok_mins = mins + gap
            else:
                exit_i = e.get("_exit_i")
                if exit_i is not None and 0 <= int(exit_i) < len(idx):
                    ts = pd.Timestamp(idx[int(exit_i)]).tz_convert("Asia/Kolkata")
                    next_ok_mins = int(ts.hour * 60 + ts.minute) + gap
                else:
                    next_ok_mins = mins + gap

    # Live = latest TODAY Oracle call — same entry-at-close book as notify
    today = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
    live = None
    today_calls = [c for c in calls if str(c.get("day") or "") == today]
    if today_calls:
        c_last = today_calls[-1]
        live = dict(c_last)
        live["live"] = True
        live["oracle"] = True
        live["oracle_t15"] = True
        live["event"] = "entry"
        live["book"] = "LIVE_ORACLE_T15"
        live["setup_label"] = c_last.get("primary") or c_last.get("setup_label") or "ORACLE_T15"
        live["n_setup_today"] = len(today_calls)
        live["underlying"] = meta.get("underlying")
        live["kind"] = kind

    # Chart TF may differ; Setup/Oracle logic always runs on 1m, then markers snap.
    chart_df = _resample_minutes(df, interval_mins) if interval_mins > 1 else df
    chart_markers = _snap_markers(markers, interval_mins)
    chart_marker_days = list(marker_days)
    if interval_mins > 1 and chart_markers and marker_days:
        # Keep day tags aligned after dedupe snap
        chart_marker_days = []
        seen_m = set()
        for m, d in zip(markers, marker_days):
            mm = dict(m)
            mm["time"] = _snap_marker_time(mm.get("time"), interval_mins)
            mk = (mm.get("time"), mm.get("text"), mm.get("shape"), mm.get("position"))
            if mk in seen_m:
                continue
            seen_m.add(mk)
            chart_marker_days.append(d)

    all_candles = _candles_payload(chart_df)
    candle_days = [str(ts.date()) for ts in chart_df.index]
    all_ema = _ema_series(chart_df, "ema34")
    all_vwap = _ema_series(chart_df, "vwap") if "vwap" in chart_df.columns else []

    wins = sum(1 for c_ in calls if c_.get("win"))
    n_setup_events = sum(
        1 for e in events if e.get("setup_ok") and _passes_side_gate(e)
    )
    side_note = " · option→BUY only" if side_gate == "BUY" else ""
    full = {
        "ok": True,
        "stock": display,
        "key": key,
        "kind": kind,
        "meta": meta,
        "mode": mode,
        "side_gate": side_gate,
        "interval": f"{interval_mins}m",
        "interval_mins": interval_mins,
        "t1": default_t1,
        "gap_mins": gap,
        "multi_call": True,
        "setup_filter": bool(require_setup and (not use_oracle or oracle_clean)),
        "oracle_clean": bool(oracle_clean),
        "n_tier_a": n_tier_a,
        "n_tier_b": n_tier_b,
        "n_setup_events": n_setup_events,
        "days_requested": days,
        "chart_days": chart_days,
        "day_lo": day_lo,
        "day_hi": day_hi,
        "n_days": len(days_sorted),
        "n_events": len(events),
        "n_calls": len(calls),
        "hit_pct": round(100.0 * wins / len(calls), 2) if calls else None,
        "note": note,
        "disclaimer": (
            f"IGN100 · run2/3 ignition + ctrl + room + bounce + body≥ATR · T25 · gap {gap}m · {kind} · chart {interval_mins}m{side_note}"
            if use_ign100
            else (
                f"Oracle T15 clean · Tier A/B ∩ path-win · gap {gap}m · {kind} · chart {interval_mins}m{side_note}"
                if oracle_clean
                else (
                    f"Oracle T15 · entry-at-close (= notify) · EMA34 · gap {gap}m · {kind} · chart {interval_mins}m{side_note}"
                    if use_oracle
                    else f"Setup A/B · EMA34 trail · multi-call gap {gap}m · {kind} · chart {interval_mins}m{side_note}"
                )
            )
        ),
        "run_ignition_100": bool(use_ign100),
        "n_ignition": sum(1 for e in events if e.get("run_ignition_ok") and _passes_side_gate(e)),
        "calls": calls,
        "selected": calls[-1] if calls else live,
        "live": live,
        # Internal: keep full series for fast chart_days flips
        "_all_candles": all_candles,
        "_all_ema34": all_ema,
        "_all_vwap": all_vwap,
        "_all_markers": chart_markers,
        "_days_sorted": days_sorted,
        "_candle_days": candle_days,
        "_marker_days": chart_marker_days,
    }
    _RESULT_CACHE[result_key] = (time.time(), full)
    out = _slice_chart_payload(full, chart_days)
    out["cached"] = False
    out["took_ms"] = int((time.time() - t_start) * 1000)
    return _merge_pinned_into_chart(key, out)


_LIVE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _pin_live_entry(key: str, live: Optional[dict]) -> None:
    """Remember the ENTRY just toasted so chart arrows match notify time/hm."""
    if not key or not isinstance(live, dict):
        return
    if str(live.get("event") or "entry").lower() != "entry":
        return
    if live.get("decision") not in ("BUY", "SELL"):
        return
    pinned = dict(live)
    pinned["live"] = True
    pinned["pinned"] = True
    pinned["event"] = "entry"
    _PINNED_ENTRY[str(key).upper()] = pinned


def _merge_pinned_into_chart(key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure chart markers/calls include the same ENTRY that notified."""
    pinned = _PINNED_ENTRY.get(str(key).upper())
    if not pinned or not payload.get("ok"):
        return payload
    out = dict(payload)
    day = str(pinned.get("day") or "")
    hm = str(pinned.get("hm") or "")
    side = str(pinned.get("decision") or "")
    entry_t = pinned.get("_entry_time")
    if entry_t is None and day and hm:
        try:
            entry_t = int(
                pd.Timestamp(f"{day} {hm}:00").tz_localize("Asia/Kolkata").timestamp()
            )
        except Exception:
            entry_t = None
    if entry_t is None:
        out["live"] = dict(pinned)
        return out

    markers = [dict(m) for m in (out.get("markers") or [])]
    # Drop prior ORACLE marker on this exact bar, then add pinned ENTRY
    markers = [
        m
        for m in markers
        if not (
            int(m.get("time") or -1) == int(entry_t)
            and "ORACLE" in str(m.get("text") or "").upper()
        )
    ]
    tgt = pinned.get("target")
    text = f"ORACLE_T15 {side}" + (f" → {tgt}" if tgt is not None else "")
    markers.append(
        {
            "time": int(entry_t),
            "position": "belowBar" if side == "BUY" else "aboveBar",
            "color": "#0b6e4f" if side == "BUY" else "#922b21",
            "shape": "arrowUp" if side == "BUY" else "arrowDown",
            "text": text,
        }
    )
    if pinned.get("win") and pinned.get("exit_hm") and day:
        try:
            exit_t = int(
                pd.Timestamp(f"{day} {pinned.get('exit_hm')}:00")
                .tz_localize("Asia/Kolkata")
                .timestamp()
            )
            markers.append(
                {
                    "time": exit_t,
                    "position": "aboveBar" if side == "BUY" else "belowBar",
                    "color": "#1d4ed8",
                    "shape": "circle",
                    "text": (
                        f"T15 {pinned.get('exit_px')}"
                        if pinned.get("reason") == "t1"
                        else str(pinned.get("reason") or "exit")
                    ),
                }
            )
        except Exception:
            pass
    markers.sort(key=lambda m: int(m.get("time") or 0))
    out["markers"] = markers

    calls = [dict(c) for c in (out.get("calls") or [])]
    if not any(
        str(c.get("day")) == day and str(c.get("hm")) == hm and str(c.get("decision")) == side
        for c in calls
    ):
        row = {
            "day": day,
            "hm": hm,
            "mins": pinned.get("mins"),
            "decision": side,
            "primary": pinned.get("primary") or pinned.get("setup_label"),
            "entry": pinned.get("entry"),
            "t1": pinned.get("t1"),
            "target": pinned.get("target"),
            "win": pinned.get("win"),
            "reason": pinned.get("reason"),
            "pts": pinned.get("pts"),
            "exit_hm": pinned.get("exit_hm"),
            "exit_px": pinned.get("exit_px"),
            "book": pinned.get("book") or "LIVE_ORACLE_T15",
            "setup_label": pinned.get("setup_label") or pinned.get("primary"),
            "live": True,
            "oracle": True,
            "oracle_t15": True,
            "pinned": True,
        }
        calls.append(row)
        calls.sort(key=lambda c: (str(c.get("day") or ""), int(c.get("mins") or 0)))
    out["calls"] = calls
    out["n_calls"] = len(calls)
    out["live"] = dict(pinned)
    return out


def _oracle_pattern_side(primary: str, body: float) -> Optional[str]:
    _ensure_paths()
    import research_nifty_1m_candle_textbook_deep as tb

    if primary in tb.BULLISH and body > 0:
        return "BUY"
    if primary in tb.BEARISH and body < 0:
        return "SELL"
    return None


def _last_closed_bar_hm(raw: pd.DataFrame, last_closed_mins: int) -> Optional[str]:
    """Latest fully closed 1m bar label (HH:MM) at/before last_closed_mins."""
    if raw is None or raw.empty:
        return None
    try:
        mins = (raw.index.hour * 60 + raw.index.minute).astype(int)
        closed = raw.loc[mins <= int(last_closed_mins)]
        if closed.empty:
            return None
        ts = pd.Timestamp(closed.index[-1]).tz_convert("Asia/Kolkata")
        return ts.strftime("%H:%M")
    except Exception:
        return None


def _bars_need_refresh(key: str, days: int, last_closed_mins: int) -> bool:
    """Refetch hist only when cache is cold or missing the latest closed minute."""
    ck = f"{key}:{days}"
    hit = _BAR_CACHE.get(ck)
    if not hit or hit[1] is None or not len(hit[1]):
        return True
    age = time.time() - float(hit[0])
    # Avoid stacking Kite hist pulls while a prior fetch is still "fresh enough"
    if age < 1.5:
        return False
    if age >= _BAR_TTL:
        return True
    last_hm = _last_closed_bar_hm(hit[1], last_closed_mins)
    if last_hm is None:
        return True
    want_h, want_m = divmod(int(last_closed_mins), 60)
    want = f"{want_h:02d}:{want_m:02d}"
    return str(last_hm) < want


def _mark_entry_fresh(live: dict, now_m: int) -> None:
    """ENTRY toast window — wide enough for Kite/scan lag; never tied to T15/exit."""
    age = now_m - int(live.get("mins") or 0)
    live["entry_age_mins"] = age
    fresh = 1 <= age <= int(_ENTRY_FRESH_MAX_AGE_MIN)
    try:
        et = live.get("_entry_time")
        if et is not None:
            # bar open unix → close ~+60s; allow grace after close
            sec_since_close = time.time() - (float(et) + 60.0)
            if 0 <= sec_since_close <= float(_ENTRY_FRESH_MAX_SEC):
                fresh = True
    except Exception:
        pass
    live["entry_fresh"] = bool(fresh)


def scan_oracle_live_fast(stock: str = "NIFTY") -> Dict[str, Any]:
    """Oracle live ENTRY for notify — toast at entry bar close only (never at T15).

    Notify rules:
      closed 1m bar · textbook side · close vs EMA34 align · 15m entry gap
      `entry_fresh` = entry bar just closed (grace for hist lag) — NOT when T15 hits

    Chart:
      full scan still paints path-win ORACLE_T15 + exit markers.
      `chart_refresh` = True when a path exit/T15 just printed so UI can refresh
      markers without sending a toast.
    """
    import fno_scalper_symbol as sym

    t_start = time.time()
    meta = sym.resolve(stock)
    key = str(meta.get("key") or stock or "NIFTY")
    display = str(meta.get("display") or key)
    kind = str(meta.get("kind") or "index")
    side_gate = sym.option_call_side(meta)
    default_t1 = 15.0
    gap = int(GAP_MINS)
    now_m = int(_now_ist().hour * 60 + _now_ist().minute)
    today = _now_ist().strftime("%Y-%m-%d")
    last_closed_mins = now_m - 1 if now_m > 0 else now_m

    # 1d hist is enough for live ENTRY; only refetch when a new minute closed
    days = 1
    if _bars_need_refresh(key, days, last_closed_mins):
        _BAR_CACHE.pop(f"{key}:{days}", None)
        # Also drop sibling day windows so tick/chart share fresh tape
        _BAR_CACHE.pop(f"{key}:2", None)
    raw, note = load_1m_bars(key, days=days)
    if raw is None or raw.empty:
        return {
            "ok": False,
            "error": note or "No 1m bars",
            "stock": display,
            "key": key,
            "live": None,
            "fast": True,
            "took_ms": int((time.time() - t_start) * 1000),
        }

    stamp = _last_closed_bar_hm(raw, last_closed_mins) or ""
    cache_stamp = f"{today}:{stamp}:{side_gate or ''}"
    cached = _ORACLE_FAST_CACHE.get(key)
    if cached and cached[0] == cache_stamp and isinstance(cached[1], dict):
        payload = dict(cached[1])
        live = payload.get("live")
        if isinstance(live, dict):
            live = dict(live)
            _mark_entry_fresh(live, now_m)
            payload["live"] = live
        # Recompute chart_refresh against wall clock
        chart_refresh = False
        for e in payload.get("calls") or []:
            em = e.get("exit_mins")
            if em is not None and e.get("win") and 0 <= (now_m - int(em)) <= 2:
                chart_refresh = True
                break
        payload["chart_refresh"] = chart_refresh
        payload["cached"] = True
        payload["took_ms"] = int((time.time() - t_start) * 1000)
        return payload

    _ensure_paths()
    import research_nifty_1m_candle_textbook_deep as tb
    import research_nifty_1m_daily_must_100 as dm

    try:
        # Warm EMA/ATR on a short tail — still enough for textbook + trail
        work = raw.tail(500) if len(raw) > 500 else raw
        df = tb.detect_textbook(work)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"textbook detect failed: {exc}",
            "stock": display,
            "key": key,
            "live": None,
            "fast": True,
            "took_ms": int((time.time() - t_start) * 1000),
        }
    df["ema34"] = df["Close"].astype(float).ewm(span=34, adjust=False).mean()
    if "atr14" not in df.columns:
        prev_c = df["Close"].astype(float).shift(1)
        tr = pd.concat(
            [
                (df["High"] - df["Low"]).astype(float),
                (df["High"].astype(float) - prev_c).abs(),
                (df["Low"].astype(float) - prev_c).abs(),
            ],
            axis=1,
        ).max(axis=1)
        df["atr14"] = tr.rolling(14, min_periods=1).mean()

    df["day"] = df["day"].astype(str)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    idx = df.index
    idx_map = {ts: i for i, ts in enumerate(idx)}

    sess = df[df["day"] == today]
    entries: List[dict] = []
    if len(sess) >= 6:
        for pos in range(5, len(sess)):
            row = sess.iloc[pos]
            mins = int(row["mins"])
            if mins < 9 * 60 + 20 or mins > 15 * 60:
                continue
            # Never signal on the forming minute (flicker)
            if mins > last_closed_mins:
                continue
            body = float(row["Close"]) - float(row["Open"])
            hits = [p for p in dm.PRIORITY if p in sess.columns and int(row[p]) == 1]
            if not hits:
                continue
            primary = hits[0]
            side = _oracle_pattern_side(primary, body)
            if side is None:
                continue
            if side_gate and side != side_gate:
                continue
            entry = round(float(row["Close"]), 2)
            ema_i = float(row["ema34"]) if np.isfinite(row["ema34"]) else entry
            # With-trend filter (cuts counter-EMA noise that is not chart-quality)
            if side == "BUY" and entry < ema_i:
                continue
            if side == "SELL" and entry > ema_i:
                continue
            atr_i = float(row["atr14"]) if np.isfinite(row["atr14"]) else 8.0
            t1_e = float(sym.t1_for(kind, entry, atr_i, "oracle_t15") or default_t1)
            ts = sess.index[pos]
            full_i = idx_map.get(ts)
            # Path score for chart exit markers only — never gates the ENTRY toast
            win = False
            reason = None
            exit_hm = None
            exit_px = None
            exit_mins = None
            pts = None
            if full_i is not None:
                ok, reason, exit_px, j, pts = path_ma_trail(
                    h, l, c, ema34, int(full_i), side, t1_e
                )
                win = bool(ok)
                if 0 <= int(j) < len(idx):
                    ets = pd.Timestamp(idx[int(j)]).tz_convert("Asia/Kolkata")
                    exit_hm = ets.strftime("%H:%M")
                    exit_mins = int(ets.hour * 60 + ets.minute)
                    exit_px = round(float(exit_px), 2)
                    pts = round(float(pts), 2)
            entries.append(
                {
                    "day": today,
                    "hm": str(row["hm"]),
                    "mins": mins,
                    "decision": side,
                    "primary": primary,
                    "entry": entry,
                    "t1": t1_e,
                    "target": round(entry + (t1_e if side == "BUY" else -t1_e), 2),
                    "win": win,
                    "reason": reason,
                    "pts": pts,
                    "exit_hm": exit_hm,
                    "exit_px": exit_px,
                    "exit_mins": exit_mins,
                    "book": "LIVE_ORACLE_T15",
                    "setup_label": primary,
                    "live": True,
                    "oracle": True,
                    "oracle_t15": True,
                    "event": "entry",
                    "kind": kind,
                    "underlying": meta.get("underlying"),
                    "_entry_time": _bar_unix(ts),
                }
            )

    # 15m between ENTRY bars (notify spacing) — not exit+gap
    kept: List[dict] = []
    next_ok = None
    for e in entries:
        if next_ok is not None and int(e["mins"]) < next_ok:
            continue
        kept.append(e)
        next_ok = int(e["mins"]) + gap

    live = None
    chart_refresh = False
    if kept:
        live = dict(kept[-1])
        live["n_setup_today"] = len(kept)
        _mark_entry_fresh(live, now_m)
        # Chart should refresh when T15/exit just printed (no toast)
        for e in kept:
            em = e.get("exit_mins")
            if em is not None and e.get("win") and 0 <= (now_m - int(em)) <= 2:
                chart_refresh = True
                break

    payload = {
        "ok": True,
        "stock": display,
        "key": key,
        "kind": kind,
        "meta": meta,
        "mode": "oracle_t15",
        "live": live,
        "calls": kept[-8:],
        "n_calls": len(kept),
        "day_hi": today,
        "note": note,
        "chart_refresh": chart_refresh,
        "fast": True,
        "fast_path": "oracle_entry_at_close",
        "took_ms": int((time.time() - t_start) * 1000),
    }
    _ORACLE_FAST_CACHE[key] = (
        cache_stamp,
        {k: v for k, v in payload.items() if k != "took_ms"},
    )
    return payload


def _emit_scalper_notify(
    *,
    display: str,
    resolved: str,
    meta: dict,
    live: dict,
    mode: str,
    cache_key: str,
) -> Tuple[bool, Optional[str]]:
    # Entry toasts only — never a separate "T15 target hit" event
    if str(live.get("event") or "entry").lower() != "entry":
        return False, None
    if live.get("entry_fresh") is False:
        return False, None
    # One toast per bar+side (ignore primary flicker on same minute)
    dedupe = (
        f"entry:{resolved}:{live.get('day')}:{live.get('hm')}:"
        f"{live.get('decision')}"
    )
    if _LIVE_DEDUPE.get(cache_key) == dedupe:
        return False, None
    # Soft anti-spam only (same-bar dedupe is the real gate)
    rate_key = f"{cache_key}:rate"
    last_ts = _LAST_SCAN.get(rate_key) or 0.0
    if (time.time() - float(last_ts)) < 8.0:
        return False, None
    try:
        import desktop_notify

        is_hhll = mode == "hhll_t15"
        title_mode = "HHLL ENTRY" if is_hhll else "Oracle ENTRY"
        tgt = live.get("target")
        ok_send = desktop_notify.notify(
            title=f"Scalper {display} · {title_mode}",
            message=(
                f"ENTRY {live.get('decision')} @ {live.get('hm')} · {live.get('entry')}"
                + (f" → T15 {tgt}" if tgt is not None else "")
                + (f" · {live.get('setup_label') or live.get('primary')}" if (live.get("setup_label") or live.get("primary")) else "")
            ),
            stock=display,
            kind="scalper_hhll_t15" if is_hhll else "scalper_oracle_t15",
            decision=str(live.get("decision") or ""),
            entry=float(live.get("entry") or 0),
            target_1=float(tgt) if tgt is not None else None,
            dedupe_key=dedupe,
            product="fno_scalper",
            payload={
                **(live or {}),
                "underlying": meta.get("underlying"),
                "kind": meta.get("kind"),
                "event": "entry",
            },
        )
        if ok_send:
            _LIVE_DEDUPE[cache_key] = dedupe
            _LAST_SCAN[rate_key] = time.time()
            return True, None
        return False, "desktop_notify returned False"
    except Exception as exc:
        return False, str(exc)


def live_scalper_check(
    stock: str = "NIFTY",
    notify: bool = False,
    mode: str = "oracle_t15",
) -> Dict[str, Any]:
    """Live ENTRY check for one stock. Notify only when caller asks (open Scalper window)."""
    import fno_scalper_symbol as sym

    meta = sym.resolve(stock)
    resolved = str(meta.get("key") or stock or "NIFTY")
    display = str(meta.get("display") or resolved)
    mode = str(mode or "oracle_t15").lower().strip()
    if mode in ("hhll_t15", "hhll", "hl_lh", "structure_hhll"):
        mode = "hhll_t15"
    else:
        mode = "oracle_t15"
    cache_key = f"{resolved}:{mode}"
    now = time.time()

    # Oracle: lean ENTRY path. HHLL keeps full scan.
    if mode == "oracle_t15":
        payload = scan_oracle_live_fast(resolved)
        if not payload.get("live"):
            cached = _LIVE_CACHE.get(cache_key)
            if cached and (now - cached[0]) < _LIVE_CACHE_TTL and (cached[1] or {}).get("live"):
                payload = dict(cached[1])
                payload["cached"] = True
        elif payload.get("ok"):
            _LIVE_CACHE[cache_key] = (now, {k: v for k, v in payload.items() if k not in ("candles", "ema34", "vwap", "markers")})
    else:
        cached = _LIVE_CACHE.get(cache_key)
        if cached and (now - cached[0]) < _LIVE_CACHE_TTL:
            payload = dict(cached[1])
            payload["cached"] = True
        else:
            _LAST_SCAN[resolved] = now
            payload = scan_scalper(stock=resolved, days=2, mode=mode, chart_days=1)
            if payload.get("ok"):
                slim = {
                    k: v
                    for k, v in payload.items()
                    if k not in ("candles", "ema34", "vwap", "markers")
                }
                # Mark HHLL live as entry event for notify gate
                if slim.get("live") and isinstance(slim["live"], dict):
                    slim["live"] = dict(slim["live"])
                    slim["live"].setdefault("event", "entry")
                    lm = slim["live"]
                    try:
                        _mark_entry_fresh(lm, int(_now_ist().hour * 60 + _now_ist().minute))
                    except Exception:
                        lm["entry_fresh"] = False
                _LIVE_CACHE[cache_key] = (now, slim)
                payload = slim

    if not payload.get("ok"):
        return payload
    live = payload.get("live")
    notified = False
    is_hhll = mode == "hhll_t15"
    setup_ok = bool(
        live
        and (
            (
                is_hhll
                and (
                    live.get("hhll_t15")
                    or live.get("gate_ok")
                    or str(live.get("book") or "").startswith("LIVE_HHLL")
                    or str(live.get("book") or "").startswith("HHLL")
                )
            )
            or live.get("oracle")
            or live.get("oracle_t15")
            or str(live.get("book") or "").startswith("LIVE_ORACLE")
            or str(live.get("book") or "").startswith("ORACLE")
            or (not is_hhll and live.get("decision") in ("BUY", "SELL"))
        )
    )
    # Toast only for fresh ENTRY on the stock this open window is polling
    if live and notify and setup_ok and live.get("entry_fresh"):
        notified, nerr = _emit_scalper_notify(
            display=display,
            resolved=resolved,
            meta=meta,
            live=live,
            mode=mode,
            cache_key=cache_key,
        )
        if nerr:
            payload["notify_error"] = nerr
        if notified or live.get("entry_fresh"):
            # Pin so chart reload paints this exact hm (e.g. 12:40) with the toast
            _pin_live_entry(resolved, live)
    elif live and setup_ok and live.get("entry_fresh"):
        _pin_live_entry(resolved, live)
    payload["notified"] = notified
    payload["mode"] = mode
    payload["key"] = resolved
    payload["stock"] = display
    payload["kite_dead"] = _kite_is_dead() and not bool(live)
    if _kite_is_dead() and not live:
        payload["feed_note"] = _KITE_DEAD_NOTE or "Kite token expired — live entry scan uses last CSV bars"
    if live and _PINNED_ENTRY.get(resolved):
        payload["pinned_entry"] = _PINNED_ENTRY.get(resolved)
    return payload


def reload_scalper_module() -> Dict[str, Any]:
    """Clear caches so next live/chart call uses fresh code+data (no process restart)."""
    n = {
        "bar": len(_BAR_CACHE),
        "frame": len(_FRAME_CACHE),
        "result": len(_RESULT_CACHE),
        "live": len(_LIVE_CACHE),
        "csv": len(_CSV_NORM_CACHE),
        "oracle_fast": len(_ORACLE_FAST_CACHE),
        "pinned": len(_PINNED_ENTRY),
    }
    _BAR_CACHE.clear()
    _FRAME_CACHE.clear()
    _RESULT_CACHE.clear()
    _LIVE_CACHE.clear()
    _CSV_NORM_CACHE.clear()
    _ORACLE_FAST_CACHE.clear()
    _PINNED_ENTRY.clear()
    _clear_kite_dead()
    return {"ok": True, "cleared": n}


def scalper_tick(stock: str = "NIFTY") -> Dict[str, Any]:
    """Ultra-light last 1m candle for live chart append (no enrich / no notify)."""
    import fno_scalper_symbol as sym

    t0 = time.time()
    meta = sym.resolve(stock)
    key = str(meta.get("key") or stock or "NIFTY")
    display = str(meta.get("display") or key)
    # Only bust the 1-day tick cache when due — never re-read other day windows
    tick_ck = f"{key}:1"
    hit = _BAR_CACHE.get(tick_ck)
    if hit and (time.time() - hit[0]) > 20:
        _BAR_CACHE.pop(tick_ck, None)
    raw, note = load_1m_bars(key, days=1)
    if raw is None or raw.empty:
        return {
            "ok": False,
            "error": note or "No 1m bars",
            "stock": display,
            "key": key,
            "kind": meta.get("kind"),
            "feed": "dead",
            "kite_dead": _kite_is_dead(),
            "took_ms": int((time.time() - t0) * 1000),
        }
    row = raw.iloc[-1]
    ts = raw.index[-1]
    candle = {
        "time": _bar_unix(ts),
        "open": round(float(row["Open"]), 2),
        "high": round(float(row["High"]), 2),
        "low": round(float(row["Low"]), 2),
        "close": round(float(row["Close"]), 2),
    }
    quote = None
    quote_err = None
    # Quotes must NOT depend on historical-token health — F&O desk uses kite_ws LTP
    # even when Connect historical says token expired.
    try:
        import kite_data

        if ":" in key:
            rows, _e2 = kite_data.quote_many([key])
            raw_q = None
            if rows:
                raw_q = rows.get(key) or next(iter(rows.values()), None)
            if isinstance(raw_q, dict) and raw_q.get("last_price") is not None:
                quote = {
                    "last_price": raw_q.get("last_price"),
                    "source": raw_q.get("source") or "kite_quote",
                }
            else:
                quote_err = _e2
        else:
            q, _err = kite_data.fetch_live_quote(key)
            if q and q.get("last_price") is not None:
                quote = {
                    "last_price": q.get("last_price"),
                    "source": q.get("source") or "kite_quote",
                }
            else:
                quote_err = _err
        # WS live price means feed is alive — clear false "dead" from hist-only errors
        if quote and str(quote.get("source") or "").startswith("kite"):
            _clear_kite_dead()
    except Exception as exc:
        quote_err = str(exc)

    # Yahoo LTP when Kite quote is dead (same bars we already loaded via yahoo_1m)
    if quote is None and note and "yahoo_1m" in str(note):
        quote = {
            "last_price": round(float(row["Close"]), 2),
            "source": "yahoo_1m",
        }

    # Morph forming candle with LTP (same behavior as F&O desk applyFnoLiveQuote)
    live_now = False
    if quote and quote.get("last_price") is not None:
        ltp = float(quote["last_price"])
        live_now = True
        try:
            from datetime import datetime as _dt
            from zoneinfo import ZoneInfo

            now_ist = _dt.now(ZoneInfo("Asia/Kolkata"))
            bar_ts = pd.Timestamp(ts)
            if bar_ts.tzinfo is None:
                bar_ts = bar_ts.tz_localize("Asia/Kolkata")
            else:
                bar_ts = bar_ts.tz_convert("Asia/Kolkata")
            bar_day = bar_ts.date()
            # Prior-session CSV + live WS → paint today's minute bar at LTP
            if bar_day < now_ist.date() and (9 * 60 + 15) <= (now_ist.hour * 60 + now_ist.minute) <= (15 * 60 + 30):
                minute = now_ist.replace(second=0, microsecond=0)
                candle = {
                    "time": int(minute.timestamp()),
                    "open": round(ltp, 2),
                    "high": round(ltp, 2),
                    "low": round(ltp, 2),
                    "close": round(ltp, 2),
                }
            else:
                candle["close"] = round(ltp, 2)
                candle["high"] = round(max(float(candle["high"]), ltp), 2)
                candle["low"] = round(min(float(candle["low"]), ltp), 2)
        except Exception:
            candle["close"] = round(ltp, 2)
            candle["high"] = round(max(float(candle["high"]), ltp), 2)
            candle["low"] = round(min(float(candle["low"]), ltp), 2)

    src = str((quote or {}).get("source") or "")
    if live_now and "ws" in src:
        feed = "kite_ws"
    elif live_now and src.startswith("yahoo"):
        feed = "yahoo_1m"
    elif live_now and not note:
        feed = "kite"
    elif live_now:
        feed = "ws_over_csv"
    elif note and "yahoo_1m" in str(note):
        feed = "yahoo_1m"
    elif note and "csv_stale" in str(note):
        feed = "csv_stale"
    elif not note:
        feed = "kite_hist"
    else:
        feed = "stale"
    today = str(_now_ist().date())
    now_m = int(_now_ist().hour * 60 + _now_ist().minute)
    expect_today = 0
    if _session_open_now():
        expect_today = max(0, min(now_m, 15 * 60 + 29) - (9 * 60 + 15) + 1)
    try:
        today_n = int(
            sum(
                1
                for ts in raw.index
                if str(pd.Timestamp(ts).tz_convert("Asia/Kolkata").date()) == today
            )
        )
    except Exception:
        today_n = int(sum(1 for ts in raw.index if str(pd.Timestamp(ts).date()) == today))
    need_chart_refresh = bool(
        _session_open_now() and expect_today > 0 and today_n < max(1, expect_today - 2)
    )
    return {
        "ok": True,
        "stock": display,
        "key": key,
        "kind": meta.get("kind"),
        "meta": meta,
        "candle": candle,
        "quote": quote,
        "note": note,
        "quote_error": quote_err,
        "feed": feed,
        "live": live_now,
        "kite_dead": _kite_is_dead() and not live_now,
        "bar_time": str(pd.Timestamp(ts)),
        "today_n": today_n,
        "expect_today": expect_today,
        "need_chart_refresh": need_chart_refresh,
        "took_ms": int((time.time() - t0) * 1000),
    }
