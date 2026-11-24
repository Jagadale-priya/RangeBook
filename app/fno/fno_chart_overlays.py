"""Causal 15m chart overlay levels for research (not live UI yet).

Builds the geometric / arithmetic lines a desk would draw on a 15m chart:
swing-cluster S/R, CPR/pivots, opening range, VWAP, EMAs, Fib, Donchian,
Bollinger mid, prior-day H/L, round numbers.

All levels are computed from bars ``[:asof]`` only (no look-ahead). Live chart
wiring waits until ``tools/research/research_15m_chart_overlays.py`` proves a
family beats a matched random-level control on index 15m tape.

References used for methodology (not for trading claims):
- Ong & Chen 2022 (Mathematics): ZigZag/SHSLDA swing clustering for S/R
- Tsinaslanidis et al. 2021 (ESWA): Fib zones vs non-Fib bounce control
- Osler / DE price-level literature: failed-penetration (wick touch, body same side)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

FIB_RATIOS = (0.236, 0.382, 0.5, 0.618, 0.786)


@dataclass(frozen=True)
class OverlayLevel:
    family: str
    code: str
    price: float
    role: str  # support | resistance | mid | band
    meta: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "family": self.family,
            "code": self.code,
            "price": round(float(self.price), 2),
            "role": self.role,
            "meta": dict(self.meta or {}),
        }


def _norm(bars: Any) -> Optional[pd.DataFrame]:
    if bars is None:
        return None
    try:
        if hasattr(bars, "empty") and bars.empty:
            return None
        work = bars.copy()
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
        if "Volume" in work.columns:
            work["Volume"] = pd.to_numeric(work["Volume"], errors="coerce").fillna(0.0)
        work = work.dropna(subset=list(need))
        return work if len(work) >= 5 else None
    except Exception:
        return None


def _atr(df: pd.DataFrame, n: int = 14) -> float:
    if len(df) < 2:
        return 1.0
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    c = df["Close"].astype(float)
    prev = c.shift(1)
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    val = float(tr.tail(n).mean())
    return val if val == val and val > 0 else 1.0


def _ema(series: pd.Series, span: int) -> Optional[float]:
    if len(series) < span:
        return None
    return float(series.astype(float).ewm(span=span, adjust=False).mean().iloc[-1])


def _swings(
    high: np.ndarray,
    low: np.ndarray,
    *,
    depth: int = 3,
) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """SHSLDA-style local extrema (depth bars each side). Causal up to last usable index."""
    highs: List[Tuple[int, float]] = []
    lows: List[Tuple[int, float]] = []
    n = len(high)
    # Right confirmation needed → last confirmed swing ends at n - depth - 1
    last = n - depth
    for i in range(depth, last):
        wh = high[i - depth : i + depth + 1]
        wl = low[i - depth : i + depth + 1]
        if high[i] >= float(np.max(wh)) - 1e-12:
            highs.append((i, float(high[i])))
        if low[i] <= float(np.min(wl)) + 1e-12:
            lows.append((i, float(low[i])))
    return highs, lows


def _cluster_swings(
    points: Sequence[Tuple[int, float]],
    *,
    span_pct: float,
    min_touches: int = 2,
    max_age: int,
    now_i: int,
) -> List[Dict[str, Any]]:
    """Average nearby swing endpoints into candidate S/R (Ong & Chen span clustering)."""
    if not points:
        return []
    ordered = sorted(points, key=lambda x: x[1])
    clusters: List[List[Tuple[int, float]]] = [[ordered[0]]]
    for pt in ordered[1:]:
        ref = float(np.mean([p for _, p in clusters[-1]]))
        if abs(pt[1] - ref) / max(abs(ref), 1e-9) <= span_pct:
            clusters[-1].append(pt)
        else:
            clusters.append([pt])
    out: List[Dict[str, Any]] = []
    for cluster in clusters:
        idxs = [i for i, _ in cluster]
        prices = [p for _, p in cluster]
        age = now_i - max(idxs)
        if age > max_age:
            continue
        if len(cluster) < min_touches and age > max_age // 2:
            continue
        if len(cluster) < min_touches:
            # Keep strong single recent extremes as weak candidates (tagged).
            strength = "weak"
        else:
            strength = "validated" if len(cluster) >= min_touches and age <= max_age else "candidate"
        out.append(
            {
                "price": float(np.mean(prices)),
                "touches": len(cluster),
                "age_bars": int(age),
                "strength": strength,
                "last_idx": int(max(idxs)),
            }
        )
    return out


def _cpr(prev_high: float, prev_low: float, prev_close: float) -> Dict[str, float]:
    p = (prev_high + prev_low + prev_close) / 3.0
    bc = (prev_high + prev_low) / 2.0
    tc = 2 * p - bc
    return {
        "pivot": p,
        "tc": max(tc, bc),
        "bc": min(tc, bc),
        "r1": 2 * p - prev_low,
        "s1": 2 * p - prev_high,
        "r2": p + (prev_high - prev_low),
        "s2": p - (prev_high - prev_low),
    }


def _fib_from_swings(
    highs: List[Tuple[int, float]],
    lows: List[Tuple[int, float]],
) -> List[OverlayLevel]:
    if not highs or not lows:
        return []
    last_hi, last_lo = highs[-1], lows[-1]
    if last_hi[0] > last_lo[0]:
        lo_p, hi_p = last_lo[1], last_hi[1]
        direction = "upswing"
    else:
        hi_p, lo_p = last_hi[1], last_lo[1]
        direction = "downswing"
    span = abs(hi_p - lo_p)
    if span <= 0:
        return []
    out: List[OverlayLevel] = []
    for ratio in FIB_RATIOS:
        if direction == "upswing":
            px = hi_p - span * ratio
            role = "support"
        else:
            px = lo_p + span * ratio
            role = "resistance"
        out.append(
            OverlayLevel(
                family="fibonacci",
                code=f"fib_{str(ratio).replace('.', '_')}",
                price=px,
                role=role,
                meta={"ratio": ratio, "swing": direction, "span": round(span, 2)},
            )
        )
    return out


def _round_levels(price: float, step: float = 50.0, count: int = 2) -> List[OverlayLevel]:
    if price <= 0 or step <= 0:
        return []
    base = round(price / step) * step
    out: List[OverlayLevel] = []
    for k in range(-count, count + 1):
        px = base + k * step
        if abs(px - price) < step * 0.05:
            continue
        out.append(
            OverlayLevel(
                family="round_number",
                code=f"round_{int(step)}",
                price=px,
                role="support" if px < price else "resistance",
                meta={"step": step},
            )
        )
    return out


def _bar_unix(ts: Any) -> int:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("Asia/Kolkata")
    else:
        t = t.tz_convert("Asia/Kolkata")
    return int(t.timestamp())


def _ema_series(series: pd.Series, span: int) -> List[Optional[float]]:
    if len(series) < max(3, span // 2):
        return [None] * len(series)
    vals = series.astype(float).ewm(span=span, adjust=False).mean()
    out: List[Optional[float]] = []
    for i, v in enumerate(vals):
        if i < span - 1 or v != v:
            out.append(None)
        else:
            out.append(round(float(v), 2))
    return out


def _indicator_series(df: pd.DataFrame, times: Sequence[int]) -> Dict[str, List[Dict[str, Any]]]:
    """Desk-style moving overlays as time series (EMA / VWAP / Bollinger)."""
    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    out: Dict[str, List[Dict[str, Any]]] = {}

    for span, key in ((9, "ema_9"), (20, "ema_20"), (50, "ema_50")):
        pts = []
        for t, v in zip(times, _ema_series(close, span)):
            if v is None:
                continue
            pts.append({"time": int(t), "value": v})
        out[key] = pts

    # Session-reset VWAP / TP mean
    vwap_pts: List[Dict[str, Any]] = []
    days = []
    for ts in df.index:
        t = pd.Timestamp(ts)
        if t.tzinfo is None:
            days.append(t.tz_localize("Asia/Kolkata").date())
        else:
            days.append(t.tz_convert("Asia/Kolkata").date())
    cum_pv = 0.0
    cum_v = 0.0
    prev_day = None
    for i, (t, d) in enumerate(zip(times, days)):
        if d != prev_day:
            cum_pv = 0.0
            cum_v = 0.0
            prev_day = d
        tp = (float(high.iloc[i]) + float(low.iloc[i]) + float(close.iloc[i])) / 3.0
        vol = float(df["Volume"].iloc[i]) if "Volume" in df.columns else 0.0
        if vol > 0:
            cum_pv += tp * vol
            cum_v += vol
            val = cum_pv / cum_v if cum_v > 0 else tp
        else:
            # Equal-weight typical-price mean within session
            cum_pv += tp
            cum_v += 1.0
            val = cum_pv / cum_v
        vwap_pts.append({"time": int(t), "value": round(float(val), 2)})
    out["vwap"] = vwap_pts

    bb_mid: List[Dict[str, Any]] = []
    bb_up: List[Dict[str, Any]] = []
    bb_lo: List[Dict[str, Any]] = []
    for i, t in enumerate(times):
        if i + 1 < 20:
            continue
        window = close.iloc[i - 19 : i + 1]
        mid = float(window.mean())
        std = float(window.std(ddof=0))
        if std != std:
            continue
        bb_mid.append({"time": int(t), "value": round(mid, 2)})
        bb_up.append({"time": int(t), "value": round(mid + 2 * std, 2)})
        bb_lo.append({"time": int(t), "value": round(mid - 2 * std, 2)})
    out["bb_mid"] = bb_mid
    out["bb_upper"] = bb_up
    out["bb_lower"] = bb_lo
    return out


def _detect_wm_patterns(
    highs: Sequence[Tuple[int, float]],
    lows: Sequence[Tuple[int, float]],
    high: np.ndarray,
    low: np.ndarray,
    times: Sequence[int],
    *,
    tol_pct: float = 0.0035,
) -> List[Dict[str, Any]]:
    """Double-bottom (W) / double-top (M) from confirmed swings — visual markers only."""
    patterns: List[Dict[str, Any]] = []
    # W: two lows within tol, with a higher peak between them
    for i in range(1, len(lows)):
        i1, p1 = lows[i - 1]
        i2, p2 = lows[i]
        if i2 - i1 < 4 or i2 - i1 > 80:
            continue
        if abs(p1 - p2) / max(abs(p1), 1e-9) > tol_pct:
            continue
        mid_hi = float(np.max(high[i1 : i2 + 1])) if i2 > i1 else p1
        neck = (p1 + p2) / 2.0
        if mid_hi <= max(p1, p2) * 1.001:
            continue
        patterns.append({
            "code": "W",
            "name": "Double bottom (W)",
            "role": "bullish",
            "hint": "Break above neckline → bias up; lose second low → bias down",
            "neckline": round(mid_hi, 2),
            "support": round(neck, 2),
            "points": [
                {"time": int(times[i1]), "price": round(p1, 2), "label": "W1"},
                {"time": int(times[i2]), "price": round(p2, 2), "label": "W2"},
            ],
            "marker_time": int(times[i2]),
            "color": "#0d9e6c",
        })
    # M: two highs within tol, with a lower trough between
    for i in range(1, len(highs)):
        i1, p1 = highs[i - 1]
        i2, p2 = highs[i]
        if i2 - i1 < 4 or i2 - i1 > 80:
            continue
        if abs(p1 - p2) / max(abs(p1), 1e-9) > tol_pct:
            continue
        mid_lo = float(np.min(low[i1 : i2 + 1])) if i2 > i1 else p1
        if mid_lo >= min(p1, p2) * 0.999:
            continue
        patterns.append({
            "code": "M",
            "name": "Double top (M)",
            "role": "bearish",
            "hint": "Break below neckline → bias down; reclaim second high → bias up",
            "neckline": round(mid_lo, 2),
            "resistance": round((p1 + p2) / 2.0, 2),
            "points": [
                {"time": int(times[i1]), "price": round(p1, 2), "label": "M1"},
                {"time": int(times[i2]), "price": round(p2, 2), "label": "M2"},
            ],
            "marker_time": int(times[i2]),
            "color": "#dc2c42",
        })
    # Keep most recent few of each type
    w = [p for p in patterns if p["code"] == "W"][-2:]
    m = [p for p in patterns if p["code"] == "M"][-2:]
    return w + m


def _project_line(
    i1: int, p1: float, i2: int, p2: float, times: Sequence[int], now_i: int
) -> Optional[Dict[str, Any]]:
    if i2 <= i1 or i2 >= len(times) or i1 < 0:
        return None
    slope = (p2 - p1) / float(i2 - i1)
    # Extend a bit past now for readability
    end_i = min(len(times) - 1, max(now_i, i2 + 2))
    pts = []
    for i in (i1, i2, end_i):
        px = p1 + slope * (i - i1)
        pts.append({"time": int(times[i]), "value": round(float(px), 2)})
    # Dedup times
    seen = set()
    clean = []
    for pt in pts:
        if pt["time"] in seen:
            continue
        seen.add(pt["time"])
        clean.append(pt)
    if len(clean) < 2:
        return None
    return {"points": clean, "slope": round(slope, 4), "broken_hint": None}


def _build_trendlines(
    highs: Sequence[Tuple[int, float]],
    lows: Sequence[Tuple[int, float]],
    times: Sequence[int],
    *,
    now_i: int,
) -> List[Dict[str, Any]]:
    """Ascending support / descending resistance from last swing pairs (desk visual)."""
    lines: List[Dict[str, Any]] = []
    if len(lows) >= 2:
        # Prefer rising support (higher lows)
        low_pairs = [(-2, -1)]
        if len(lows) >= 3:
            low_pairs.append((-3, -1))
        for a, b in low_pairs:
            i1, p1 = lows[a]
            i2, p2 = lows[b]
            if p2 <= p1:
                continue
            proj = _project_line(i1, p1, i2, p2, times, now_i)
            if not proj:
                continue
            last = proj["points"][-1]["value"]
            lines.append({
                "code": "asc_support",
                "name": "Rising support",
                "role": "support",
                "hint": "Hold = bias up; break below = bias down",
                "color": "#059669",
                "lineStyle": 0,
                "lineWidth": 2,
                **proj,
                "last_value": last,
            })
            break
    if len(highs) >= 2:
        high_pairs = [(-2, -1)]
        if len(highs) >= 3:
            high_pairs.append((-3, -1))
        for a, b in high_pairs:
            i1, p1 = highs[a]
            i2, p2 = highs[b]
            if p2 >= p1:
                continue
            proj = _project_line(i1, p1, i2, p2, times, now_i)
            if not proj:
                continue
            last = proj["points"][-1]["value"]
            lines.append({
                "code": "desc_resistance",
                "name": "Falling resistance",
                "role": "resistance",
                "hint": "Hold = bias down; break above = bias up",
                "color": "#dc2c42",
                "lineStyle": 0,
                "lineWidth": 2,
                **proj,
                "last_value": last,
            })
            break
    return lines


def build_overlays(
    bars: Any,
    *,
    asof_ilocs: Optional[int] = None,
    or_bars: int = 1,
    swing_depth: int = 3,
    swing_span_pct: float = 0.0025,
    swing_max_age: int = 80,
    lookback: int = 320,
) -> Dict[str, Any]:
    """Return causal overlay pack at ``bars.iloc[asof_ilocs]`` (inclusive).

    ``lookback`` limits history for swing clustering speed on long tapes.
    """
    df0 = _norm(bars)
    if df0 is None:
        return {"available": False, "reason": "bad_bars", "levels": [], "indicators": {}}
    end = len(df0) - 1 if asof_ilocs is None else int(asof_ilocs)
    end = max(0, min(end, len(df0) - 1))
    start = max(0, end + 1 - int(lookback))
    df = df0.iloc[start : end + 1]
    if len(df) < 20:
        return {"available": False, "reason": "short", "levels": [], "indicators": {}}

    price = float(df["Close"].iloc[-1])
    atr = _atr(df)
    high = df["High"].astype(float).to_numpy()
    low = df["Low"].astype(float).to_numpy()
    close = df["Close"].astype(float)
    now_i = len(df) - 1
    levels: List[OverlayLevel] = []

    # --- Swing cluster S/R (SHSLDA-inspired) ---
    sh, sl = _swings(high, low, depth=swing_depth)
    clustered = _cluster_swings(
        sh + sl,
        span_pct=swing_span_pct,
        min_touches=2,
        max_age=swing_max_age,
        now_i=now_i,
    )
    for row in clustered:
        px = float(row["price"])
        # Always S/R by side of last close — never "mid" (mid is reserved for VWAP/BB mid/pivot).
        role = "support" if px <= price else "resistance"
        levels.append(
            OverlayLevel(
                family="swing_sr",
                code="swing_cluster",
                price=px,
                role=role,
                meta={
                    "touches": row["touches"],
                    "age_bars": row["age_bars"],
                    "strength": row["strength"],
                },
            )
        )

    # --- Session OR (first N 15m bars of the day) ---
    idx = df.index
    day = idx[-1].date() if hasattr(idx[-1], "date") else pd.Timestamp(idx[-1]).date()
    day_mask = np.array(
        [(t.date() if hasattr(t, "date") else pd.Timestamp(t).date()) == day for t in df.index],
        dtype=bool,
    )
    sess = df.iloc[np.flatnonzero(day_mask)]
    if len(sess) >= or_bars:
        orb = sess.iloc[:or_bars]
        or_hi = float(orb["High"].max())
        or_lo = float(orb["Low"].min())
        levels.append(
            OverlayLevel(
                family="opening_range",
                code="or_high",
                price=or_hi,
                role="resistance",
                meta={"or_bars": or_bars},
            )
        )
        levels.append(
            OverlayLevel(
                family="opening_range",
                code="or_low",
                price=or_lo,
                role="support",
                meta={"or_bars": or_bars},
            )
        )

    # --- Session VWAP (volume-weighted); index CSVs often have Volume=0 → TP mean ---
    vwap = None
    vwap_mode = None
    if len(sess):
        tp = (sess["High"].astype(float) + sess["Low"].astype(float) + sess["Close"].astype(float)) / 3.0
        if "Volume" in sess.columns and float(sess["Volume"].sum()) > 0:
            vwap = float((tp * sess["Volume"].astype(float)).sum() / sess["Volume"].astype(float).sum())
            vwap_mode = "volume"
        else:
            vwap = float(tp.mean())
            vwap_mode = "typical_price_mean"
        levels.append(
            OverlayLevel(
                family="vwap",
                code="session_vwap" if vwap_mode == "volume" else "session_tp_mean",
                price=vwap,
                role="mid",
                meta={"mode": vwap_mode},
            )
        )

    # --- EMAs ---
    for span in (9, 20, 50):
        ema = _ema(close, span)
        if ema is None:
            continue
        levels.append(
            OverlayLevel(
                family="ema",
                code=f"ema_{span}",
                price=ema,
                role="support" if ema <= price else "resistance",
                meta={"span": span},
            )
        )

    # --- Prior day H/L + CPR ---
    if getattr(idx, "tz", None) is not None:
        days = pd.Series(idx.tz_convert("Asia/Kolkata").date, index=df.index)
    else:
        days = pd.Series(pd.DatetimeIndex(idx).date, index=df.index)
    unique_days = list(dict.fromkeys(days.tolist()))
    if len(unique_days) >= 2:
        prev_day = unique_days[-2]
        prev = df.loc[days == prev_day]
        if len(prev):
            ph, pl, pc = float(prev["High"].max()), float(prev["Low"].min()), float(prev["Close"].iloc[-1])
            levels.append(
                OverlayLevel(
                    family="prior_day",
                    code="prior_high",
                    price=ph,
                    role="resistance",
                    meta={},
                )
            )
            levels.append(
                OverlayLevel(
                    family="prior_day",
                    code="prior_low",
                    price=pl,
                    role="support",
                    meta={},
                )
            )
            piv = _cpr(ph, pl, pc)
            for code, role in (
                ("pivot", "mid"),
                ("tc", "resistance"),
                ("bc", "support"),
                ("r1", "resistance"),
                ("s1", "support"),
                ("r2", "resistance"),
                ("s2", "support"),
            ):
                levels.append(
                    OverlayLevel(
                        family="cpr",
                        code=code,
                        price=float(piv[code]),
                        role=role,
                        meta={},
                    )
                )

    # --- Fib from last confirmed swing pair ---
    levels.extend(_fib_from_swings(sh, sl))

    # --- Donchian 20 ---
    if len(df) >= 20:
        d_hi = float(df["High"].tail(20).max())
        d_lo = float(df["Low"].tail(20).min())
        levels.append(
            OverlayLevel(
                family="donchian",
                code="donchian_20_high",
                price=d_hi,
                role="resistance",
                meta={"window": 20},
            )
        )
        levels.append(
            OverlayLevel(
                family="donchian",
                code="donchian_20_low",
                price=d_lo,
                role="support",
                meta={"window": 20},
            )
        )

    # --- Bollinger mid (20, 2) ---
    if len(close) >= 20:
        mid = float(close.tail(20).mean())
        std = float(close.tail(20).std(ddof=0))
        levels.append(
            OverlayLevel(
                family="bollinger",
                code="bb_mid",
                price=mid,
                role="mid",
                meta={"window": 20},
            )
        )
        if std == std and std > 0:
            levels.append(
                OverlayLevel(
                    family="bollinger",
                    code="bb_upper",
                    price=mid + 2 * std,
                    role="resistance",
                    meta={"window": 20, "k": 2},
                )
            )
            levels.append(
                OverlayLevel(
                    family="bollinger",
                    code="bb_lower",
                    price=mid - 2 * std,
                    role="support",
                    meta={"window": 20, "k": 2},
                )
            )

    # --- Round numbers (both 50 + 100 — GT80 rules use round_50 on NIFTY, round_100 on BN/SX)
    levels.extend(_round_levels(price, step=50.0, count=2))
    levels.extend(_round_levels(price, step=100.0, count=2))

    indicators = {
        "price": round(price, 2),
        "atr": round(atr, 2),
        "vwap": round(vwap, 2) if vwap is not None else None,
        "ema_9": next((L.price for L in levels if L.code == "ema_9"), None),
        "ema_20": next((L.price for L in levels if L.code == "ema_20"), None),
        "ema_50": next((L.price for L in levels if L.code == "ema_50"), None),
        "asof": str(df.index[-1]),
        "bars_used": len(df),
    }
    # Deduplicate near-identical prices within a family
    deduped: List[OverlayLevel] = []
    seen: Dict[str, List[float]] = {}
    for lvl in levels:
        bucket = seen.setdefault(lvl.family, [])
        if any(abs(lvl.price - p) / max(abs(p), 1e-9) < 0.00015 for p in bucket):
            continue
        bucket.append(lvl.price)
        deduped.append(lvl)

    times = [_bar_unix(ts) for ts in df.index]
    series_map = _indicator_series(df, times)
    patterns = _detect_wm_patterns(sh, sl, high, low, times)
    trendlines = _build_trendlines(sh, sl, times, now_i=now_i)

    return {
        "available": True,
        "levels": [L.as_dict() for L in deduped],
        "indicators": indicators,
        "families": sorted({L.family for L in deduped}),
        "series": series_map,
        "patterns": patterns,
        "trendlines": trendlines,
    }


def failed_penetration(
    bar: pd.Series,
    level: float,
    *,
    tol: float,
) -> Optional[str]:
    """Return 'support_hold' / 'resistance_hold' if wick tags level but body stays same side.

    Matches the failed-penetration definition used in price-level literature
    (wick touch; open and close on the same side of the level).
    """
    o = float(bar["Open"])
    h = float(bar["High"])
    l = float(bar["Low"])
    c = float(bar["Close"])
    if h < level - tol or l > level + tol:
        return None
    # Body entirely above → support hold (bounce up from level)
    if min(o, c) >= level - tol and l <= level + tol:
        return "support_hold"
    # Body entirely below → resistance hold
    if max(o, c) <= level + tol and h >= level - tol:
        return "resistance_hold"
    return None


def forward_reaction(
    bars: pd.DataFrame,
    i: int,
    level: float,
    role: str,
    *,
    horizon: int = 3,
    atr: float,
) -> Dict[str, Any]:
    """After a touch at bar i, did price move away from the level in the role's favor?"""
    if i + 1 >= len(bars):
        return {"reacted": False, "move_atr": 0.0}
    future = bars.iloc[i + 1 : i + 1 + horizon]
    if future.empty:
        return {"reacted": False, "move_atr": 0.0}
    entry = float(bars["Close"].iloc[i])
    end = float(future["Close"].iloc[-1])
    move = end - entry
    band = max(atr * 0.15, 1.0)
    if role == "support":
        reacted = move >= band
    elif role == "resistance":
        reacted = move <= -band
    else:
        # Mid / magnet (VWAP, BB mid, pivot): price should move closer to the level.
        before = abs(entry - level)
        after = abs(end - level)
        reacted = after + band * 0.25 < before
    return {
        "reacted": bool(reacted),
        "move_atr": round(move / max(atr, 1e-9), 3),
        "move_pts": round(move, 2),
    }
