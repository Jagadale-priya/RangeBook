"""Fixed Range Volume Profile (FRVP) — chart-only levels.

TradingView / CBOT-style:
  - Split selected window High–Low into N equal rows
  - Spread each bar's volume across overlapping rows
  - POC = max-volume row mid
  - Value area grows from POC to ~70% of total volume

No Calls / dual / live-logic wiring. Groww is not used.
Index volume on Kite is often tick-like — treat as relative activity.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

DEFAULT_ROWS = 48  # finer rows → lower bar height + sharper POC/VA edges
DEFAULT_VA_PCT = 0.70  # TradingView default — do not confuse with histogram width
MAX_VP_BARS = 5000  # TradingView FRVP lower-TF bar cap
# Approx NSE cash session bars / calendar day (overestimate → safer TF pick)
BARS_PER_DAY = {"minute": 375, "5minute": 75, "15minute": 25}
CHART_INTERVAL_SEC = {
    "minute": 60,
    "1m": 60,
    "1minute": 60,
    "5minute": 300,
    "5m": 300,
    "15minute": 900,
    "15m": 900,
}
INDEX_VOLUME_NOTE = (
    "Index volume on Kite is often tick/update-like, not cash-market share "
    "volume. FRVP is a relative activity map — visual context only, not Calls."
)


def chart_bar_seconds(interval: Any) -> int:
    key = str(interval or "minute").strip().lower()
    return int(CHART_INTERVAL_SEC.get(key, 60))


def suggest_n_rows(price_low: float, price_high: float) -> int:
    """More rows on wide ranges so each histogram bar is shorter and sharper."""
    span = abs(float(price_high) - float(price_low))
    if span <= 50:
        return 36
    if span <= 150:
        return 48
    if span <= 300:
        return 64
    if span <= 600:
        return 80
    if span <= 1000:
        return 96
    return 120


def pick_calc_intervals(
    span_calendar_days: int,
    *,
    chart_interval: str = "minute",
) -> List[str]:
    """TradingView-style: prefer finest TF with estimated bars < 5000."""
    span = max(1, int(span_calendar_days))
    chart = str(chart_interval or "minute").strip().lower()
    if chart in ("1m", "1minute"):
        chart = "minute"
    if chart in ("5m",):
        chart = "5minute"
    if chart in ("15m",):
        chart = "15minute"
    # Prefer lower than chart when possible, then chart TF as fallback
    seq = ["minute", "5minute", "15minute"]
    chosen: List[str] = []
    for iv in seq:
        est = span * int(BARS_PER_DAY.get(iv, 25))
        if est < MAX_VP_BARS:
            chosen.append(iv)
    if not chosen:
        chosen = ["15minute"]
    # Ensure chart TF is attempted if not already (deep history / missing LTF)
    if chart in ("minute", "5minute", "15minute") and chart not in chosen:
        chosen.append(chart)
    return chosen


def inclusive_window_end(end: Any, chart_interval: Any) -> pd.Timestamp:
    """Click is bar open time — extend to include the full last chart bar."""
    t1 = _as_ts(end)
    if t1 is None:
        raise ValueError("bad end")
    sec = int(chart_bar_seconds(chart_interval))
    # last bar [open, open+sec) → include through open+sec-1s
    return t1 + pd.Timedelta(seconds=int(max(0, sec - 1)))


def _norm_bars(bars: Any) -> Optional[pd.DataFrame]:
    if bars is None:
        return None
    try:
        if hasattr(bars, "empty") and bars.empty:
            return None
        work = bars.copy()
        if not isinstance(work.index, pd.DatetimeIndex):
            if "date" in work.columns:
                work = work.set_index("date")
            work.index = pd.to_datetime(work.index)
        rename = {}
        for c in work.columns:
            cl = str(c).strip().lower()
            if cl in ("open", "o"):
                rename[c] = "Open"
            elif cl in ("high", "h"):
                rename[c] = "High"
            elif cl in ("low", "l"):
                rename[c] = "Low"
            elif cl in ("close", "c"):
                rename[c] = "Close"
            elif cl in ("volume", "vol", "v"):
                rename[c] = "Volume"
        if rename:
            work = work.rename(columns=rename)
        need = {"Open", "High", "Low", "Close"}
        if not need.issubset(set(work.columns)):
            return None
        for col in need:
            work[col] = pd.to_numeric(work[col], errors="coerce")
        if "Volume" not in work.columns:
            work["Volume"] = 1.0
        else:
            work["Volume"] = pd.to_numeric(work["Volume"], errors="coerce").fillna(0.0)
        work = work.dropna(subset=list(need))
        if getattr(work.index, "tz", None) is not None:
            work.index = work.index.tz_convert("Asia/Kolkata")
        return work if len(work) >= 1 else None
    except Exception:
        return None


def _as_ts(x: Any) -> Optional[pd.Timestamp]:
    if x is None:
        return None
    try:
        ts = pd.Timestamp(x)
        if ts.tzinfo is None:
            ts = ts.tz_localize("Asia/Kolkata")
        else:
            ts = ts.tz_convert("Asia/Kolkata")
        return ts
    except Exception:
        return None


def slice_window(
    bars: pd.DataFrame,
    start: Any,
    end: Any,
) -> pd.DataFrame:
    """Inclusive window on bar index (IST)."""
    t0 = _as_ts(start)
    t1 = _as_ts(end)
    if t0 is None or t1 is None:
        return bars.iloc[0:0]
    if t1 < t0:
        t0, t1 = t1, t0
    idx = bars.index
    if idx.tz is None:
        # already normalized in _norm_bars; belt-and-suspenders
        pass
    return bars[(idx >= t0) & (idx <= t1)]


def _distribute_bar(
    vol: float,
    lo: float,
    hi: float,
    edges: np.ndarray,
    up: bool,
    totals: np.ndarray,
    ups: np.ndarray,
    downs: np.ndarray,
) -> None:
    n = len(totals)
    if vol <= 0 or n == 0:
        return
    if hi < lo:
        lo, hi = hi, lo
    if hi == lo:
        # point bar → nearest row by mid
        mids = 0.5 * (edges[:-1] + edges[1:])
        j = int(np.argmin(np.abs(mids - lo)))
        j = max(0, min(n - 1, j))
        totals[j] += vol
        if up:
            ups[j] += vol
        else:
            downs[j] += vol
        return
    span = hi - lo
    for i in range(n):
        r_lo = float(edges[i])
        r_hi = float(edges[i + 1])
        overlap = max(0.0, min(hi, r_hi) - max(lo, r_lo))
        if overlap <= 0:
            continue
        share = vol * (overlap / span)
        totals[i] += share
        if up:
            ups[i] += share
        else:
            downs[i] += share


def _value_area_bounds(
    totals: np.ndarray,
    edges: np.ndarray,
    poc_i: int,
    va_pct: float,
) -> Tuple[float, float, List[int]]:
    """Grow VA from POC per TradingView Volume Profile rules.

    Start with POC, then repeatedly add the busier immediate neighbor
    (above vs below). Tie → closer to POC, then the row above.
    Stop without adding if the next row would push cumulative volume
    past the target (default 70%) — do not overshoot.
    VAH / VAL = outer edges of the included rows (Support = VAL, Resist = VAH).
    """
    n = len(totals)
    total = float(totals.sum())
    if total <= 0 or n == 0:
        return float(edges[0]), float(edges[-1]), [poc_i]
    target = float(va_pct) * total
    included = {int(poc_i)}
    cum = float(totals[poc_i])
    lo_i = hi_i = int(poc_i)

    def pick_next() -> Optional[int]:
        above = hi_i + 1
        below = lo_i - 1
        has_a = above < n
        has_b = below >= 0
        if not has_a and not has_b:
            return None
        if has_a and not has_b:
            return above
        if has_b and not has_a:
            return below
        va = float(totals[above])
        vb = float(totals[below])
        if va > vb:
            return above
        if vb > va:
            return below
        # equal volume → closer to POC; if still tied → above (TradingView)
        da = abs(above - poc_i)
        db = abs(below - poc_i)
        if da < db:
            return above
        if db < da:
            return below
        return above

    while cum + 1e-12 < target:
        nxt = pick_next()
        if nxt is None:
            break
        next_vol = float(totals[nxt])
        # TradingView: if adding would exceed remaining target, stop (no overshoot)
        if cum + next_vol > target + 1e-12:
            break
        included.add(nxt)
        cum += next_vol
        if nxt > hi_i:
            hi_i = nxt
        if nxt < lo_i:
            lo_i = nxt

    vah = float(edges[hi_i + 1])
    val = float(edges[lo_i])
    return vah, val, sorted(included)


def compute_fixed_range_vp(
    bars: Any,
    *,
    start: Any = None,
    end: Any = None,
    n_rows: int = DEFAULT_ROWS,
    va_pct: float = DEFAULT_VA_PCT,
    row_size: Optional[float] = None,
) -> Dict[str, Any]:
    """Compute FRVP for bars (optionally sliced to start/end).

    Returns JSON-serializable dict with rows, poc, vah, val, totals.
    """
    work = _norm_bars(bars)
    if work is None or work.empty:
        return {
            "ok": False,
            "error": "no_bars",
            "rows": [],
            "poc": None,
            "vah": None,
            "val": None,
            "total_vol": 0.0,
            "meta": {"note": INDEX_VOLUME_NOTE},
        }
    if start is not None and end is not None:
        work = slice_window(work, start, end)
    if work.empty:
        return {
            "ok": False,
            "error": "empty_window",
            "rows": [],
            "poc": None,
            "vah": None,
            "val": None,
            "total_vol": 0.0,
            "meta": {"note": INDEX_VOLUME_NOTE},
        }

    p_low = float(work["Low"].min())
    p_high = float(work["High"].max())
    if p_high < p_low:
        p_low, p_high = p_high, p_low
    if p_high == p_low:
        p_high = p_low + 1e-6

    n = int(n_rows) if n_rows else DEFAULT_ROWS
    n = max(4, min(200, n))
    if row_size is not None and float(row_size) > 0:
        h = float(row_size)
        n = max(4, int(np.ceil((p_high - p_low) / h)))
        n = min(200, n)
        # snap high so last edge covers
        p_high = p_low + n * h
    else:
        h = (p_high - p_low) / n

    edges = np.linspace(p_low, p_high, n + 1)
    totals = np.zeros(n, dtype=float)
    ups = np.zeros(n, dtype=float)
    downs = np.zeros(n, dtype=float)

    for _, row in work.iterrows():
        v = float(row["Volume"] or 0.0)
        if v <= 0:
            v = 1.0  # ensure relative shape when volume missing
        lo = float(row["Low"])
        hi = float(row["High"])
        up = float(row["Close"]) >= float(row["Open"])
        _distribute_bar(v, lo, hi, edges, up, totals, ups, downs)

    total_vol = float(totals.sum())
    poc_i = int(np.argmax(totals)) if total_vol > 0 else n // 2
    poc = float(0.5 * (edges[poc_i] + edges[poc_i + 1]))
    va = float(va_pct) if va_pct and va_pct > 0 else DEFAULT_VA_PCT
    va = min(0.99, max(0.5, va))
    vah, val, va_idx = _value_area_bounds(totals, edges, poc_i, va)

    rows_out: List[Dict[str, Any]] = []
    for i in range(n):
        rows_out.append(
            {
                "i": i,
                "price_lo": round(float(edges[i]), 4),
                "price_hi": round(float(edges[i + 1]), 4),
                "price_mid": round(float(0.5 * (edges[i] + edges[i + 1])), 4),
                "vol": round(float(totals[i]), 4),
                "up": round(float(ups[i]), 4),
                "down": round(float(downs[i]), 4),
                "pct": round(100.0 * float(totals[i]) / total_vol, 3) if total_vol else 0.0,
                "in_va": i in va_idx,
                "is_poc": i == poc_i,
            }
        )

    t0 = work.index[0]
    t1 = work.index[-1]
    va_vol = float(sum(float(totals[i]) for i in va_idx))
    return {
        "ok": True,
        "error": None,
        "rows": rows_out,
        "poc": round(poc, 4),
        "vah": round(vah, 4),
        "val": round(val, 4),
        # FRVP-derived S/R aliases (same prices; chart labels)
        "support": round(val, 4),
        "resistance": round(vah, 4),
        "fair_value": round(poc, 4),
        "range_high": round(p_high, 4),
        "range_low": round(p_low, 4),
        "poc_index": poc_i,
        "va_indices": va_idx,
        "va_volume": round(va_vol, 4),
        "va_coverage": round(va_vol / total_vol, 6) if total_vol else 0.0,
        "total_vol": round(total_vol, 4),
        "n_rows": n,
        "row_height": round(float(h), 6),
        "price_low": round(p_low, 4),
        "price_high": round(p_high, 4),
        "va_pct": va,
        "bar_count": int(len(work)),
        "start": t0.isoformat() if hasattr(t0, "isoformat") else str(t0),
        "end": t1.isoformat() if hasattr(t1, "isoformat") else str(t1),
        "meta": {
            "note": INDEX_VOLUME_NOTE,
            "chart_only": True,
            "no_calls_link": True,
            "va_rule": "tradingview_no_overshoot",
            "histogram_side": "left",
        },
    }


def _load_tape_csv(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    """Local kite CSV fallback (no Groww)."""
    try:
        from pathlib import Path
        import path_setup

        root = Path(path_setup.ROOT)
        key = str(symbol or "").upper().replace(" ", "")
        if key in ("NIFTY50", "NIFTY_50"):
            key = "NIFTY"
        if key in ("BSESENSEX",):
            key = "SENSEX"
        name = {
            ("NIFTY", "minute"): "NIFTY_1m_kite.csv",
            ("NIFTY", "5minute"): "NIFTY_5m_kite.csv",
            ("NIFTY", "15minute"): "NIFTY_15m_kite.csv",
            ("SENSEX", "minute"): "SENSEX_1m_kite.csv",
            ("SENSEX", "5minute"): "SENSEX_5m_kite.csv",
            ("SENSEX", "15minute"): "SENSEX_15m_kite.csv",
        }.get((key, interval))
        if not name:
            return None
        path = root / "stock_signal_data" / "fno_validate" / name
        if not path.exists():
            return None
        raw = pd.read_csv(path, index_col=0, parse_dates=True)
        return _norm_bars(raw)
    except Exception:
        return None


def load_bars_for_profile(
    symbol: str,
    *,
    start: Any,
    end: Any,
    prefer: str = "minute",
    chart_interval: Optional[str] = None,
) -> Tuple[Optional[pd.DataFrame], str, Optional[str]]:
    """Load bars for any selected range (1d–10d+).

    - Extends ``end`` by one chart-bar so the last clicked candle is fully included.
    - Picks lower TF like TradingView (finest with < ~5000 bars): 1m → 5m → 15m.
    - Fetches enough history from *now back to start* (not just span length).
    Groww unused.
    """
    t0 = _as_ts(start)
    t1 = _as_ts(end)
    if t0 is None or t1 is None:
        return None, "none", "bad_window"
    if t1 < t0:
        t0, t1 = t1, t0
    chart_iv = chart_interval or prefer or "minute"
    try:
        t1_incl = inclusive_window_end(t1, chart_iv)
    except Exception:
        t1_incl = t1
    span_days = max(1, int((t1_incl.normalize() - t0.normalize()).days) + 1)
    now = pd.Timestamp.now(tz="Asia/Kolkata")
    days_back = max(span_days, int((now.normalize() - t0.normalize()).days) + 2)

    intervals = pick_calc_intervals(span_days, chart_interval=str(chart_iv))
    # Honor explicit prefer by trying it first when present
    pref = str(prefer or "").strip().lower()
    if pref in ("1m", "1minute"):
        pref = "minute"
    if pref in ("5m",):
        pref = "5minute"
    if pref in ("15m",):
        pref = "15minute"
    if pref in ("minute", "5minute", "15minute") and pref in intervals:
        intervals = [pref] + [x for x in intervals if x != pref]

    last_err = None
    for iv in intervals:
        try:
            import kite_data

            cap = 60 if iv == "minute" else (100 if iv == "5minute" else 200)
            fetch_days = min(cap, max(days_back, span_days) + 2)
            df, err = kite_data.fetch_historical_candles(
                symbol, interval=iv, days=fetch_days, keep_partial=True
            )
            if err or df is None or getattr(df, "empty", True):
                last_err = err or "empty"
                tape = _load_tape_csv(symbol, iv)
                if tape is not None and not tape.empty:
                    sliced = slice_window(tape, t0, t1_incl)
                    if not sliced.empty:
                        return sliced, f"tape:{iv}", None
                continue
            work = _norm_bars(df)
            if work is None or work.empty:
                last_err = "norm_empty"
                continue
            sliced = slice_window(work, t0, t1_incl)
            if sliced.empty:
                last_err = "slice_empty"
                continue
            # Ensure fetch actually covered the requested start
            if sliced.index.min() > t0 + pd.Timedelta(minutes=30):
                last_err = "coverage_short"
                # still usable if we have data — keep, but try coarser TF too only if tiny
            return sliced, f"kite:{iv}", None
        except Exception as exc:
            last_err = str(exc)
            tape = _load_tape_csv(symbol, iv if iv != "minute" else "5minute")
            if tape is not None and not tape.empty:
                sliced = slice_window(tape, t0, t1_incl)
                if not sliced.empty:
                    return sliced, f"tape:{iv}", None
    for iv in ("15minute", "5minute", "minute"):
        tape = _load_tape_csv(symbol, iv)
        if tape is not None and not tape.empty:
            sliced = slice_window(tape, t0, t1_incl)
            if not sliced.empty:
                return sliced, f"tape:{iv}", None
    return None, "none", last_err or "no_bars"


def build_profile_for_symbol(
    symbol: str,
    *,
    start: Any,
    end: Any,
    n_rows: Any = DEFAULT_ROWS,
    va_pct: float = DEFAULT_VA_PCT,
    row_size: Optional[float] = None,
    prefer_interval: str = "minute",
    chart_interval: Optional[str] = None,
) -> Dict[str, Any]:
    """End-to-end FRVP for API: fetch bars + compute. Chart-only.

    Works for any clicked range on 1m / 5m / 15m charts (days-long OK).
    """
    chart_iv = chart_interval or prefer_interval or "minute"
    bars, src, err = load_bars_for_profile(
        symbol,
        start=start,
        end=end,
        prefer=prefer_interval,
        chart_interval=chart_iv,
    )
    if bars is None or bars.empty:
        return {
            "ok": False,
            "error": err or "no_bars",
            "symbol": str(symbol or "").upper(),
            "source": src,
            "rows": [],
            "poc": None,
            "vah": None,
            "val": None,
            "total_vol": 0.0,
            "meta": {"note": INDEX_VOLUME_NOTE, "chart_only": True, "no_calls_link": True},
        }
    auto_rows = False
    rows_arg = n_rows
    if rows_arg is None or str(rows_arg).strip().lower() in ("", "auto"):
        auto_rows = True
        n_use = suggest_n_rows(float(bars["Low"].min()), float(bars["High"].max()))
    else:
        try:
            n_use = int(rows_arg)
        except (TypeError, ValueError):
            auto_rows = True
            n_use = suggest_n_rows(float(bars["Low"].min()), float(bars["High"].max()))
    out = compute_fixed_range_vp(
        bars, n_rows=n_use, va_pct=va_pct, row_size=row_size
    )
    out["symbol"] = str(symbol or "").upper()
    out["source"] = src
    out["request_start"] = str(start)
    out["request_end"] = str(end)
    out["chart_interval"] = str(chart_iv)
    out["selection_start"] = str(start)
    out["selection_end"] = str(end)
    out.setdefault("meta", {})
    if isinstance(out["meta"], dict):
        out["meta"]["auto_rows"] = auto_rows
        out["meta"]["chart_interval"] = str(chart_iv)
        out["meta"]["va_pct_note"] = (
            "VA% controls Support/Resist band (default 70%). "
            "Histogram bar *width* is a separate chart scale — not VA%."
        )
    return out


def profile_from_ohlcv_records(
    records: Sequence[Dict[str, Any]],
    *,
    start: Any = None,
    end: Any = None,
    n_rows: int = DEFAULT_ROWS,
    va_pct: float = DEFAULT_VA_PCT,
    row_size: Optional[float] = None,
) -> Dict[str, Any]:
    """Helper for API: list of {time/open/high/low/close/volume}."""
    if not records:
        return compute_fixed_range_vp(None)
    rows = []
    idx = []
    for r in records:
        ts = r.get("time") or r.get("date") or r.get("ts")
        idx.append(ts)
        rows.append(
            {
                "Open": r.get("open"),
                "High": r.get("high"),
                "Low": r.get("low"),
                "Close": r.get("close"),
                "Volume": r.get("volume", 0),
            }
        )
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(idx)
    return compute_fixed_range_vp(
        df, start=start, end=end, n_rows=n_rows, va_pct=va_pct, row_size=row_size
    )
