"""Path labels: which barrier prints first (target, stop, or time).

F&O uses fixed clip points. Cash daily uses next-bar high/low vs ATR.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


def path_outcome(
    future: Optional[pd.DataFrame],
    *,
    bearish: bool,
    stop: float,
    target: float,
) -> str:
    """Walk later bars. Same-bar both barriers counts as a stop."""
    if future is None or len(future) == 0:
        return "expired"
    for _, row in future.iterrows():
        h = float(row["High"])
        l = float(row["Low"])
        if bearish:
            hit_sl = h >= stop
            hit_t1 = l <= target
        else:
            hit_sl = l <= stop
            hit_t1 = h >= target
        if hit_t1 and hit_sl:
            return "same_bar_both"
        if hit_t1:
            return "t1_before_sl"
        if hit_sl:
            return "sl_before_t1"
    return "expired"


def daily_next_bar_labels(df: pd.DataFrame, atr: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Next session: 2×ATR target vs 1×ATR stop. Both hit → neither label (noise)."""
    close = df["Close"].astype(float)
    nxt_h = df["High"].astype(float).shift(-1)
    nxt_l = df["Low"].astype(float).shift(-1)
    span = atr.astype(float).where(atr.astype(float) > 0)
    span = span.fillna(close.abs() * 0.01).clip(lower=close.abs() * 0.001)
    upper = close + 2.0 * span
    lower = close - 1.0 * span
    hit_up = nxt_h >= upper
    hit_dn = nxt_l <= lower
    y_up = (hit_up & ~hit_dn).fillna(False).astype(int)
    y_down = (hit_dn & ~hit_up).fillna(False).astype(int)
    return y_up, y_down
