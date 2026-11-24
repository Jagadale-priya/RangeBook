"""
Price structure: swings, support/resistance, gaps, volume, RS vs benchmark, simple divergences.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore

BENCHMARK_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
}
DEFAULT_BENCHMARK = "^NSEI"


def _swing_points(high: pd.Series, low: pd.Series, window: int = 5) -> Tuple[List[float], List[float]]:
    sh, sl = [], []
    n = len(high)
    if n < window * 2 + 1:
        return sh, sl
    for i in range(window, n - window):
        h_slice = high.iloc[i - window : i + window + 1]
        l_slice = low.iloc[i - window : i + window + 1]
        if high.iloc[i] >= h_slice.max():
            sh.append(float(high.iloc[i]))
        if low.iloc[i] <= l_slice.min():
            sl.append(float(low.iloc[i]))
    return sh[-6:], sl[-6:]


def _cluster_levels(levels: List[float], tolerance_pct: float = 0.008) -> List[float]:
    if not levels:
        return []
    levels = sorted(levels)
    clusters: List[List[float]] = [[levels[0]]]
    for px in levels[1:]:
        ref = clusters[-1][-1]
        if abs(px - ref) / max(ref, 1e-9) <= tolerance_pct:
            clusters[-1].append(px)
        else:
            clusters.append([px])
    return [float(np.mean(c)) for c in clusters[-4:]]


def analyze_gap(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or len(df) < 2:
        return {"type": "NONE", "gap_pct": 0.0, "score_delta": 0}
    last, prev = df.iloc[-1], df.iloc[-2]
    prev_c = float(prev["Close"])
    o, h, l = float(last["Open"]), float(last["High"]), float(last["Low"])
    gap_pct = (o - prev_c) / prev_c * 100 if prev_c else 0.0
    gap_type = "NONE"
    score = 0.0
    if gap_pct > 0.35:
        gap_type = "GAP_UP"
        score += 4 if l > prev_c else 2
    elif gap_pct < -0.35:
        gap_type = "GAP_DOWN"
        score -= 4 if h < prev_c else 2
    if gap_type != "NONE" and abs(gap_pct) > 1.0:
        score += 2 if gap_pct > 0 else -2
    return {
        "type": gap_type,
        "gap_pct": round(gap_pct, 2),
        "filled": bool(
            (gap_type == "GAP_UP" and l <= prev_c) or (gap_type == "GAP_DOWN" and h >= prev_c)
        ),
        "score_delta": max(-8.0, min(8.0, score)),
    }


def analyze_volume(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or len(df) < 21:
        return {"ratio_20d": 1.0, "confirmation": "NEUTRAL", "score_delta": 0}
    v = df["Volume"].astype(float)
    ratio = float(v.iloc[-1] / v.iloc[-21:-1].mean()) if v.iloc[-21:-1].mean() else 1.0
    close_up = float(df["Close"].iloc[-1]) >= float(df["Open"].iloc[-1])
    score = 0.0
    conf = "NEUTRAL"
    if ratio > 1.4:
        conf = "HIGH_VOLUME"
        score += 3 if close_up else -3
    elif ratio < 0.6:
        conf = "LOW_VOLUME"
        score -= 1
    return {
        "ratio_20d": round(ratio, 2),
        "confirmation": conf,
        "score_delta": max(-5.0, min(5.0, score)),
    }


def analyze_trend_structure(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or len(df) < 30:
        return {"structure": "UNKNOWN", "score_delta": 0, "swing_highs": [], "swing_lows": []}
    h, l = df["High"], df["Low"]
    sh, sl = _swing_points(h, l, window=3)
    structure = "RANGE"
    score = 0.0
    if len(sh) >= 2 and len(sl) >= 2:
        hh = sh[-1] > sh[-2]
        hl = sl[-1] > sl[-2]
        lh = sh[-1] < sh[-2]
        ll = sl[-1] < sl[-2]
        if hh and hl:
            structure = "UPTREND"
            score += 6
        elif lh and ll:
            structure = "DOWNTREND"
            score -= 6
    return {
        "structure": structure,
        "swing_highs": [round(x, 2) for x in sh[-3:]],
        "swing_lows": [round(x, 2) for x in sl[-3:]],
        "score_delta": score,
    }


def analyze_support_resistance(df: pd.DataFrame, current_price: float) -> Dict[str, Any]:
    if df is None or len(df) < 20:
        return {"supports": [], "resistances": [], "score_delta": 0}
    tail = df.tail(60)
    sh, sl = _swing_points(tail["High"], tail["Low"], window=2)
    pivots = _cluster_levels(sh + sl + [float(tail["Low"].min()), float(tail["High"].max())])
    supports = sorted([p for p in pivots if p < current_price * 0.998])[-3:]
    resistances = sorted([p for p in pivots if p > current_price * 1.002])[:3]
    score = 0.0
    if supports:
        dist_s = (current_price - supports[-1]) / current_price * 100
        if dist_s < 1.2:
            score += 4
    if resistances:
        dist_r = (resistances[0] - current_price) / current_price * 100
        if dist_r < 1.2:
            score -= 4
    return {
        "supports": [round(x, 2) for x in supports],
        "resistances": [round(x, 2) for x in resistances],
        "nearest_support": round(supports[-1], 2) if supports else None,
        "nearest_resistance": round(resistances[0], 2) if resistances else None,
        "score_delta": max(-6.0, min(6.0, score)),
    }


def _fetch_benchmark_returns(benchmark_symbol: str, days: int = 30) -> Optional[pd.Series]:
    if yf is None:
        return None
    try:
        hist = yf.Ticker(benchmark_symbol).history(period=f"{max(days, 10)}d", auto_adjust=False)
        if hist is None or len(hist) < 5:
            return None
        return hist["Close"].pct_change()
    except Exception:
        return None


def analyze_relative_strength(
    df: pd.DataFrame,
    stock_key: str,
    benchmark_symbol: Optional[str] = None,
) -> Dict[str, Any]:
    if df is None or len(df) < 15:
        return {"available": False, "score_delta": 0, "bias": "NEUTRAL"}
    bench = benchmark_symbol or BENCHMARK_MAP.get(stock_key.upper(), DEFAULT_BENCHMARK)
    stock_ret = df["Close"].pct_change()
    bench_ret = _fetch_benchmark_returns(bench, days=40)
    if bench_ret is None:
        return {"available": False, "benchmark": bench, "score_delta": 0, "bias": "NEUTRAL"}
    aligned = pd.concat([stock_ret, bench_ret], axis=1, join="inner").dropna()
    if len(aligned) < 10:
        return {"available": False, "benchmark": bench, "score_delta": 0, "bias": "NEUTRAL"}
    aligned.columns = ["stock", "bench"]
    rs_5 = (1 + aligned["stock"].tail(5)).prod() - (1 + aligned["bench"].tail(5)).prod()
    rs_20 = (1 + aligned["stock"].tail(20)).prod() - (1 + aligned["bench"].tail(20)).prod()
    score = 0.0
    if rs_5 > 0.01:
        score += 4
    elif rs_5 < -0.01:
        score -= 4
    if rs_20 > 0.02:
        score += 3
    elif rs_20 < -0.02:
        score -= 3
    bias = "OUTPERFORM" if score >= 3 else ("UNDERPERFORM" if score <= -3 else "NEUTRAL")
    return {
        "available": True,
        "benchmark": bench,
        "rs_vs_benchmark_5d_pct": round(float(rs_5) * 100, 2),
        "rs_vs_benchmark_20d_pct": round(float(rs_20) * 100, 2),
        "bias": bias,
        "score_delta": max(-8.0, min(8.0, score)),
    }


def analyze_divergence(df: pd.DataFrame, rsi_series: Optional[pd.Series] = None) -> Dict[str, Any]:
    if df is None or len(df) < 30:
        return {"signal": "NONE", "score_delta": 0}
    close = df["Close"]
    if rsi_series is None:
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi_series = 100 - (100 / (1 + rs))
    tail = df.tail(15)
    rsi_tail = rsi_series.loc[tail.index]
    c1, c2 = float(tail["Close"].iloc[-1]), float(tail["Close"].iloc[-8])
    r1, r2 = float(rsi_tail.iloc[-1]), float(rsi_tail.iloc[-8])
    signal = "NONE"
    score = 0.0
    if c2 > c1 and r2 < r1 - 4:
        signal = "BEARISH_RSI_DIVERGENCE"
        score -= 5
    elif c2 < c1 and r2 > r1 + 4:
        signal = "BULLISH_RSI_DIVERGENCE"
        score += 5
    return {"signal": signal, "score_delta": score}


def run_structural_analysis(
    df: pd.DataFrame,
    current_price: float,
    stock_key: str,
    raw_rsi: Optional[float] = None,
) -> Dict[str, Any]:
    trend = analyze_trend_structure(df)
    sr = analyze_support_resistance(df, current_price)
    gap = analyze_gap(df)
    vol = analyze_volume(df)
    rs = analyze_relative_strength(df, stock_key)
    div = analyze_divergence(df)

    total_delta = (
        trend["score_delta"]
        + sr["score_delta"]
        + gap["score_delta"]
        + vol["score_delta"]
        + rs.get("score_delta", 0)
        + div["score_delta"]
    )
    total_delta = max(-15.0, min(15.0, total_delta))
    bias = "BULLISH" if total_delta >= 4 else ("BEARISH" if total_delta <= -4 else "NEUTRAL")

    return {
        "bias": bias,
        "score_delta": total_delta,
        "trend_structure": trend,
        "support_resistance": sr,
        "gap": gap,
        "volume": vol,
        "relative_strength": rs,
        "divergence": div,
        "combined_adjust": round(total_delta / 100.0 * 0.07, 4),
    }


def structural_reason_lines(struct: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    ts = struct.get("trend_structure") or {}
    if ts.get("structure") and ts["structure"] != "UNKNOWN":
        lines.append(f"Market structure: {ts['structure']} (swing-based).")
    sr = struct.get("support_resistance") or {}
    if sr.get("nearest_support"):
        lines.append(f"Nearest support near ₹{sr['nearest_support']}.")
    if sr.get("nearest_resistance"):
        lines.append(f"Nearest resistance near ₹{sr['nearest_resistance']}.")
    gap = struct.get("gap") or {}
    if gap.get("type") and gap["type"] != "NONE":
        lines.append(f"Session gap {gap['type']} {gap.get('gap_pct', 0):+.2f}%.")
    vol = struct.get("volume") or {}
    if vol.get("confirmation") == "HIGH_VOLUME":
        lines.append(f"Volume {vol.get('ratio_20d', 1):.1f}× 20-day avg — move has participation.")
    rs = struct.get("relative_strength") or {}
    if rs.get("available"):
        lines.append(
            f"Relative strength vs {rs.get('benchmark', 'index')}: "
            f"5d {rs.get('rs_vs_benchmark_5d_pct', 0):+.2f}%, "
            f"20d {rs.get('rs_vs_benchmark_20d_pct', 0):+.2f}% ({rs.get('bias')})."
        )
    div = struct.get("divergence") or {}
    if div.get("signal") and div["signal"] != "NONE":
        lines.append(div["signal"].replace("_", " ").title() + ".")
    return lines
