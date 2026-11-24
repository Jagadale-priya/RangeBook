"""Unit tests for Fixed Range Volume Profile engine."""
from __future__ import annotations

import numpy as np
import pandas as pd

import fno_fixed_range_vp as vp


def _toy_bars() -> pd.DataFrame:
    """Three price bands: most volume around 100–102."""
    idx = pd.date_range("2026-11-19 09:15", periods=12, freq="1min", tz="Asia/Kolkata")
    rows = []
    # low band
    for i in range(3):
        rows.append({"Open": 98.0, "High": 99.0, "Low": 97.5, "Close": 98.5, "Volume": 10})
    # POC band — heavy
    for i in range(6):
        rows.append({"Open": 100.0, "High": 102.0, "Low": 100.0, "Close": 101.5, "Volume": 100})
    # high band
    for i in range(3):
        rows.append({"Open": 103.0, "High": 104.0, "Low": 102.5, "Close": 103.5, "Volume": 10})
    return pd.DataFrame(rows, index=idx)


def test_compute_ok_and_poc_in_heavy_band():
    out = vp.compute_fixed_range_vp(_toy_bars(), n_rows=10, va_pct=0.70)
    assert out["ok"] is True
    assert out["total_vol"] > 0
    assert out["poc"] is not None
    assert 99.5 <= out["poc"] <= 102.5
    assert out["val"] <= out["poc"] <= out["vah"]
    assert len(out["rows"]) == 10
    poc_rows = [r for r in out["rows"] if r["is_poc"]]
    assert len(poc_rows) == 1
    assert poc_rows[0]["vol"] == max(r["vol"] for r in out["rows"])


def test_value_area_covers_majority():
    out = vp.compute_fixed_range_vp(_toy_bars(), n_rows=10, va_pct=0.70)
    va_vol = sum(r["vol"] for r in out["rows"] if r["in_va"])
    ratio = va_vol / out["total_vol"]
    # POC is always in VA; if POC alone > 70%, coverage may exceed target (TV still keeps POC)
    poc_vol = next(r["vol"] for r in out["rows"] if r["is_poc"])
    if poc_vol / out["total_vol"] <= 0.70 + 1e-9 and len(out["va_indices"]) > 1:
        assert ratio <= 0.70 + 1e-9
    assert ratio >= poc_vol / out["total_vol"] - 1e-9
    assert out["support"] == out["val"]
    assert out["resistance"] == out["vah"]
    assert out["fair_value"] == out["poc"]
    assert out["val"] <= out["poc"] <= out["vah"]
    assert out["range_low"] == out["price_low"]
    assert out["range_high"] == out["price_high"]


def test_value_area_no_overshoot():
    """Adding the next busier neighbor must not be possible without exceeding 70% (unless POC alone > 70%)."""
    out = vp.compute_fixed_range_vp(_toy_bars(), n_rows=20, va_pct=0.70)
    assert out["ok"]
    assert out["meta"]["va_rule"] == "tradingview_no_overshoot"
    totals = np.array([r["vol"] for r in out["rows"]], dtype=float)
    target = 0.70 * float(totals.sum())
    va_idx = set(out["va_indices"])
    cum = float(sum(totals[i] for i in va_idx))
    lo_i = min(va_idx)
    hi_i = max(va_idx)
    candidates = []
    if hi_i + 1 < len(totals):
        candidates.append(hi_i + 1)
    if lo_i - 1 >= 0:
        candidates.append(lo_i - 1)
    if not candidates:
        return
    # Next pick would be busier neighbor (TV tie-break not needed if one side only)
    if len(candidates) == 1:
        nxt = candidates[0]
    else:
        a, b = hi_i + 1, lo_i - 1
        nxt = a if totals[a] >= totals[b] else b
    # Either POC alone already past target, or next row would exceed
    poc_vol = float(totals[out["poc_index"]])
    if poc_vol > target + 1e-9:
        assert va_idx == {out["poc_index"]} or cum >= poc_vol
    else:
        assert cum + float(totals[nxt]) > target + 1e-9 or cum + 1e-12 >= target
        assert cum <= target + 1e-9


def test_window_slice():
    bars = _toy_bars()
    out = vp.compute_fixed_range_vp(
        bars,
        start="2026-11-19 09:18:00+05:30",
        end="2026-11-19 09:23:00+05:30",
        n_rows=8,
    )
    assert out["ok"] is True
    assert out["bar_count"] <= 6


def test_empty_window():
    out = vp.compute_fixed_range_vp(
        _toy_bars(),
        start="2020-01-01",
        end="2020-01-02",
    )
    assert out["ok"] is False
    assert out["error"] == "empty_window"


def test_up_down_split():
    idx = pd.date_range("2026-11-19 10:00", periods=2, freq="1min", tz="Asia/Kolkata")
    df = pd.DataFrame(
        [
            {"Open": 100, "High": 101, "Low": 99, "Close": 100.5, "Volume": 50},  # up
            {"Open": 100, "High": 101, "Low": 99, "Close": 99.5, "Volume": 50},  # down
        ],
        index=idx,
    )
    out = vp.compute_fixed_range_vp(df, n_rows=6)
    assert out["ok"]
    assert abs(sum(r["up"] for r in out["rows"]) - 50) < 1e-3
    assert abs(sum(r["down"] for r in out["rows"]) - 50) < 1e-3


def test_row_size_mode():
    out = vp.compute_fixed_range_vp(_toy_bars(), row_size=1.0)
    assert out["ok"]
    assert out["row_height"] == 1.0
    assert out["n_rows"] >= 4


def test_meta_chart_only():
    out = vp.compute_fixed_range_vp(_toy_bars())
    assert out["meta"]["chart_only"] is True
    assert out["meta"]["no_calls_link"] is True
    assert "Index volume" in out["meta"]["note"]


def test_profile_from_records():
    recs = [
        {"time": "2026-11-19T09:15:00+05:30", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 20},
        {"time": "2026-11-19T09:16:00+05:30", "open": 100.5, "high": 102, "low": 100, "close": 101, "volume": 80},
    ]
    out = vp.profile_from_ohlcv_records(recs, n_rows=6)
    assert out["ok"] is True


def test_pick_calc_intervals_multiday():
    # 4 calendar days → 1m under 5000 bars
    ivs = vp.pick_calc_intervals(4, chart_interval="15minute")
    assert ivs[0] == "minute"
    # Very long span → coarser first candidates only when 1m would exceed cap
    ivs_long = vp.pick_calc_intervals(20, chart_interval="15minute")
    assert "minute" not in ivs_long or ivs_long[0] in ("5minute", "15minute", "minute")
    assert "15minute" in ivs_long or "5minute" in ivs_long


def test_inclusive_window_end_15m():
    end = vp.inclusive_window_end("2026-11-19 09:15:00+05:30", "15minute")
    # last 15m bar covers through 09:29:59
    assert end.hour == 9 and end.minute == 29


def test_suggest_n_rows_scales():
    assert vp.suggest_n_rows(100, 120) <= vp.suggest_n_rows(100, 500)
    assert 36 <= vp.suggest_n_rows(25000, 25300) <= 120
