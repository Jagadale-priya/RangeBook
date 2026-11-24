"""Clean-label helpers for Nifty side-specific research packs (BUY vs SELL).

Research-only. No live imports required beyond numpy typing.
Logic here is unit-tested: filters must be deterministic and side-pure.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np


class CalibratedHead:
    """Drop-in predict_proba wrapper for isotonic-calibrated side heads.

    Defined here (not in __main__) so joblib packs unpickle cleanly.
    """

    def __init__(self, base, iso, classes):
        self.base = base
        self.iso = iso
        self.classes_ = np.asarray(classes)

    def predict_proba(self, X):
        # Local import avoids circular import at module load.
        import fno_model

        raw = fno_model._proba_pos(self.base, np.asarray(X, dtype=float))
        cal = np.clip(self.iso.transform(raw), 0.05, 0.95)
        out = np.zeros((len(cal), len(self.classes_)), dtype=float)
        classes = list(self.classes_)
        i1 = classes.index(1) if 1 in classes else 0
        i0 = classes.index(0) if 0 in classes else 1 - i1
        out[:, i1] = cal
        out[:, i0] = 1.0 - cal
        return out

# --- Noise / cleanliness gates (documented defaults) -----------------------------
# Ambiguous barrier prints are not usable as supervised targets.
DROP_OUTCOMES = frozenset({"expired", "same_bar_both"})
# Keep only decisive T1 or SL.
KEEP_OUTCOMES = frozenset({"t1_before_sl", "sl_before_t1"})

# Opening-range too tight → break is noise.
MIN_OR_WIDTH_PTS = 12.0
# Entry bar vs stop: only drop extreme one-bar noise (ATR stop often ~bar size).
MAX_NOISE_VS_SL = 2.50
# Need at least this many future bars to resolve (else near close / truncated).
MIN_FUTURE_BARS = 2
# Skip ultra-late entries that often expire into the close.
MAX_ENTRY_MINS = 14 * 60 + 45  # 14:45 IST from midnight
MIN_ENTRY_MINS = 9 * 60 + 30   # 09:30
# OR extension chase: allow normal follow-through; drop only extreme chase.
MAX_OR_EXT = 0.85


@dataclass(frozen=True)
class CleanRow:
    """One supervised ticket candidate before/after cleaning."""

    day: str
    side: float  # +1 BUY, -1 SELL
    y: int  # 1 T1, 0 SL (only set when outcome kept)
    outcome: str
    bars_to_close: Optional[int]
    future_bars: int
    or_width: float
    noise_vs_sl: float
    or_ext: float
    mins_entry: float
    first_break: float
    x: np.ndarray


def is_buy(side: float) -> bool:
    return float(side) > 0


def is_sell(side: float) -> bool:
    return float(side) < 0


def outcome_is_decisive(outcome: str) -> bool:
    return str(outcome) in KEEP_OUTCOMES


def passes_noise_gates(
    *,
    outcome: str,
    future_bars: int,
    or_width: float,
    noise_vs_sl: float,
    or_ext: float,
    mins_entry: float,
    min_or_width: float = MIN_OR_WIDTH_PTS,
    max_noise_vs_sl: float = MAX_NOISE_VS_SL,
    min_future_bars: int = MIN_FUTURE_BARS,
    min_entry_mins: float = MIN_ENTRY_MINS,
    max_entry_mins: float = MAX_ENTRY_MINS,
    max_or_ext: float = MAX_OR_EXT,
) -> Tuple[bool, str]:
    """Return (keep, reason). reason is 'ok' or a drop code."""
    if str(outcome) in DROP_OUTCOMES:
        return False, f"drop_outcome:{outcome}"
    if str(outcome) not in KEEP_OUTCOMES:
        return False, f"drop_outcome:{outcome}"
    if int(future_bars) < int(min_future_bars):
        return False, "drop_short_future"
    if float(or_width) < float(min_or_width):
        return False, "drop_thin_or"
    if float(noise_vs_sl) > float(max_noise_vs_sl):
        return False, "drop_noisy_bar"
    if float(or_ext) > float(max_or_ext):
        return False, "drop_chase_ext"
    if float(mins_entry) < float(min_entry_mins) or float(mins_entry) > float(max_entry_mins):
        return False, "drop_entry_clock"
    return True, "ok"


def clean_rows(
    rows: Sequence[CleanRow],
    **gate_kwargs: Any,
) -> Tuple[List[CleanRow], Dict[str, int]]:
    """Apply noise gates; returns kept rows + drop reason counts."""
    kept: List[CleanRow] = []
    reasons: Dict[str, int] = {}
    for row in rows:
        ok, reason = passes_noise_gates(
            outcome=row.outcome,
            future_bars=row.future_bars,
            or_width=row.or_width,
            noise_vs_sl=row.noise_vs_sl,
            or_ext=row.or_ext,
            mins_entry=row.mins_entry,
            **gate_kwargs,
        )
        if not ok:
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        y = 1 if row.outcome == "t1_before_sl" else 0
        kept.append(
            CleanRow(
                day=row.day,
                side=row.side,
                y=y,
                outcome=row.outcome,
                bars_to_close=row.bars_to_close,
                future_bars=row.future_bars,
                or_width=row.or_width,
                noise_vs_sl=row.noise_vs_sl,
                or_ext=row.or_ext,
                mins_entry=row.mins_entry,
                first_break=row.first_break,
                x=row.x,
            )
        )
        reasons["ok"] = reasons.get("ok", 0) + 1
    return kept, reasons


def split_by_side(rows: Sequence[CleanRow]) -> Tuple[List[CleanRow], List[CleanRow]]:
    """Strict side split. Raises if a row has side==0."""
    buys: List[CleanRow] = []
    sells: List[CleanRow] = []
    for row in rows:
        if abs(float(row.side)) < 1e-12:
            raise ValueError("side==0 row is invalid for side models")
        if is_buy(row.side):
            buys.append(row)
        elif is_sell(row.side):
            sells.append(row)
        else:
            raise ValueError(f"invalid side {row.side}")
    return buys, sells


def assert_side_pure(rows: Sequence[CleanRow], expect: str) -> None:
    """Test helper: every row must be BUY or SELL as named."""
    if expect not in ("BUY", "SELL"):
        raise ValueError("expect must be BUY or SELL")
    for row in rows:
        if expect == "BUY" and not is_buy(row.side):
            raise AssertionError(f"SELL leaked into BUY set day={row.day}")
        if expect == "SELL" and not is_sell(row.side):
            raise AssertionError(f"BUY leaked into SELL set day={row.day}")


def chronological_holdout_days(
    days: Sequence[str],
    holdout_frac: float = 0.20,
) -> Tuple[set, set]:
    """Time-ordered day split. No shuffle — prevents leakage."""
    if not 0.05 <= float(holdout_frac) <= 0.50:
        raise ValueError("holdout_frac out of range")
    uniq = sorted(set(str(d) for d in days))
    if len(uniq) < 10:
        raise ValueError("need at least 10 unique days")
    cut = max(1, int(len(uniq) * (1.0 - float(holdout_frac))))
    # Ensure both sides non-empty
    cut = min(max(cut, 1), len(uniq) - 1)
    train_days = set(uniq[:cut])
    hold_days = set(uniq[cut:])
    if train_days & hold_days:
        raise RuntimeError("train/hold day leakage")
    return train_days, hold_days


def matrix_from_rows(rows: Sequence[CleanRow]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """X, y, days arrays."""
    if not rows:
        return np.zeros((0, 1)), np.zeros(0, dtype=int), np.zeros(0, dtype=object)
    X = np.asarray([r.x for r in rows], dtype=float)
    y = np.asarray([r.y for r in rows], dtype=int)
    days = np.asarray([r.day for r in rows], dtype=object)
    return X, y, days


def recent_sample_weights(
    days: Sequence[str],
    *,
    half_life_days: float = 365.0,
) -> np.ndarray:
    """Exponential recency weights. Full history kept; recent days weigh more."""
    if half_life_days <= 0:
        raise ValueError("half_life_days must be > 0")
    # Parse ISO dates YYYY-MM-DD
    ord_days = []
    for d in days:
        parts = str(d)[:10].split("-")
        if len(parts) != 3:
            ord_days.append(0)
            continue
        y, m, dd = int(parts[0]), int(parts[1]), int(parts[2])
        # rough ordinal
        ord_days.append(y * 372 + m * 31 + dd)
    arr = np.asarray(ord_days, dtype=float)
    if len(arr) == 0:
        return np.zeros(0, dtype=float)
    latest = float(arr.max())
    age = np.maximum(0.0, latest - arr)
    # map ordinal-diff to ~day units (372≈year → /372*365)
    age_days = age * (365.0 / 372.0)
    w = 0.5 ** (age_days / float(half_life_days))
    return np.asarray(w, dtype=float)


def threshold_table(
    p: np.ndarray,
    y: np.ndarray,
    thresholds: Sequence[float],
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    for thr in thresholds:
        pick = p >= float(thr)
        n = int(pick.sum())
        t1 = int(y[pick].sum()) if n else 0
        out[str(thr)] = {
            "n": n,
            "t1": t1,
            "hit": None if n == 0 else round(t1 / n, 4),
        }
    out["always"] = {
        "n": int(len(y)),
        "t1": int(y.sum()),
        "hit": None if len(y) == 0 else round(float(y.mean()), 4),
    }
    return out


def choose_buy_p(
    p: np.ndarray,
    y: np.ndarray,
    *,
    thresholds: Sequence[float] = (0.50, 0.52, 0.55, 0.58, 0.60, 0.62, 0.66, 0.70),
    min_n: int = 25,
    min_lift: float = 0.03,
) -> Tuple[float, Dict[str, Dict[str, Any]]]:
    """Accuracy-first threshold on holdout probabilities."""
    bands = threshold_table(p, y, thresholds)
    base = float((bands["always"].get("hit") or 0.0))
    best_thr = 0.52
    best_hit = -1.0
    best_n = 0
    for thr in thresholds:
        rec = bands[str(thr)]
        n = int(rec["n"])
        hit = rec["hit"]
        if hit is None or n < min_n:
            continue
        if float(hit) + 1e-12 < base + float(min_lift):
            continue
        if float(hit) > best_hit + 1e-12 or (abs(float(hit) - best_hit) < 1e-12 and n > best_n):
            best_thr, best_hit, best_n = float(thr), float(hit), n
    return best_thr, bands


def hit_stats(y_true: np.ndarray, p: np.ndarray, thr: float) -> Dict[str, Any]:
    pick = np.asarray(p, dtype=float) >= float(thr)
    n = int(pick.sum())
    t1 = int(np.asarray(y_true, dtype=int)[pick].sum()) if n else 0
    return {
        "n": n,
        "t1": t1,
        "sl": n - t1,
        "hit_pct": round(100.0 * t1 / n, 1) if n else 0.0,
    }
