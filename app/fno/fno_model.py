"""Dedicated same-session F&O model. Separate from the cash / Intraday ensemble.

Label is T1-before-SL on the live clips (not a 0.05% close-to-close drift).
A second head scores P(continue) = T2-before-SL for the runner only.
Walk-forward holdout is the reported metric. Live path never retrains per tick.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import joblib
except ImportError:
    joblib = None  # type: ignore

try:
    from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
except ImportError:
    ExtraTreesClassifier = None  # type: ignore
    HistGradientBoostingClassifier = None  # type: ignore

import analysis_engine
import fno_risk_engine
import fno_select
import fno_session_model
import fno_structure
import triple_barrier

try:
    from sklearn.mixture import GaussianMixture
except ImportError:
    GaussianMixture = None  # type: ignore

MODEL_VERSION = "fno_clip_t1_2.5"
LABEL_REVISION = "nifty_sequential_ticket_v1"
HORIZON_BARS = 4  # kept for pack metadata; labels use the rest of the session
MIN_MOVE = 0.0005
# Nested chronological selection on the five-year NIFTY tape chose 0.52 for
# the regularized Extra Trees head. The final 241 sessions were evaluated once.
BUY_P = 0.52
FIRST_BREAK_P = 0.52
RECLAIM_P = 0.52
SELL_P = 0.42  # unused for clip labels; kept so older callers do not break
CONTINUE_P = 0.42  # P(T2 before SL) to show the runner
HOLDOUT_FRAC = 0.20
MIN_TRAIN_SAMPLES = 160
MIN_TRAIN_DAYS = 15
TRAIN_LOOKBACK_DAYS = 185
ENTRY_START_MINS = 9 * 60 + 30
# First-break tag may fire from the 9:15 bar clock; labels still start at 9:30.
FIRST_BREAK_START_MINS = 9 * 60 + 15
ENTRY_END_MINS = 11 * 60 + 30  # legacy OR-follow-through window (metadata only)
# Labels must cover the same clock the desk trades: 09:30 through the last bar
# that still has a following bar to resolve the clip (15:15 close).
LABEL_END_MINS = 15 * 60 + 15
# 09:45–10:15 may use FIRST_BREAK_P; later first clips need BUY_P (3 Sep 11:00).
FIRST_CLIP_LATE_MINS = 10 * 60 + 15
# A finished 15m bar closing against the side is part of the model bar, not a session rule.
BAR_GATE_BLOCKS = True

FEATURE_NAMES = fno_session_model.FEATURE_NAMES + (
    "session_chg",
    "gap_pct",
    "news_delta",
    "vix_level",
    "pcr",
    "oi_imbalance",
    "oi_change",
    "iv_atm",
    "fut_basis_pct",
    "side",
    "or_width_frac",
    "or_ext",
    "mins_entry",
    "body_frac",
    "gap_aligned",
    "both_sides",
    "first_break",
    "confirms",
    "prior_range_frac",
    "dist_prior_extreme",
    "session_range_frac",
    "vwap_sess",
    "poc_dist",
    "adx_14",
    "atr_expand",
    "rv_vel",
    "regime_range",
    "regime_trend",
    "regime_volatile",
    "noise_vs_sl",
    "gex_flip",
    "pcr_chg",
    "iv_skew",
    "deriv_present",
    "dix",
    "dix_present",
) + (
    "htf_bias_num",
    "level_path_frac",
    "noise_vs_stop",
    "target_cover",
) + fno_structure.STRUCTURE_NAMES + (
    "gmm_low",
    "gmm_calm",
    "gmm_hot",
    "gmm_stress",
)

GMM_NAMES = ("gmm_low", "gmm_calm", "gmm_hot", "gmm_stress")
GMM_INPUTS = (
    "adx_14",
    "atr_ratio",
    "rv_vel",
    "bb_width",
    "vwap_z",
    "noise_vs_sl",
    "donch_pos",
    "body_ratio",
)

import path_setup
ROOT = str(path_setup.ROOT)
MODEL_DIR = os.path.join(ROOT, "stock_signal_data", "models")
CACHE_DIR = os.path.join(ROOT, "stock_signal_data", "fno_validate")


def model_path(symbol: str) -> str:
    key = symbol.strip().upper()
    if key == "NIFTY":
        try:
            from prod_live.paths import nifty_prod2_pkl

            prod = nifty_prod2_pkl()
            if prod.is_file():
                return str(prod)
        except Exception:
            pass
    return os.path.join(MODEL_DIR, f"fno_{key}.pkl")


def _deriv_features(derivatives: Optional[Dict[str, Any]]) -> Dict[str, float]:
    d = derivatives or {}
    pcr = d.get("pcr")
    ce = (d.get("atm_ce") or {}).get("oi")
    pe = (d.get("atm_pe") or {}).get("oi")
    iv = (d.get("atm_ce") or {}).get("implied_volatility")
    if iv is None:
        iv = (d.get("future") or {}).get("implied_volatility")
    basis = d.get("futures_basis")
    oi_imb = 0.0
    try:
        if ce and pe and (float(ce) + float(pe)) > 0:
            oi_imb = (float(pe) - float(ce)) / (float(pe) + float(ce))
    except (TypeError, ValueError):
        oi_imb = 0.0
    oi_change = d.get("oi_change")
    try:
        oi_change_f = float(oi_change) if oi_change is not None else 0.0
    except (TypeError, ValueError):
        oi_change_f = 0.0
    vix = d.get("vix_level")
    try:
        import math as _math
        vix_f = float(vix) if vix is not None else 0.0
        if not _math.isfinite(vix_f):
            vix_f = 0.0
    except (TypeError, ValueError):
        vix_f = 0.0
    gex = d.get("gex") if isinstance(d.get("gex"), dict) else {}
    gex_flip = float(gex.get("flip") or 0) if gex.get("available") else 0.0
    iv_skew = gex.get("iv_skew")
    if iv_skew is None:
        iv_skew = d.get("iv_skew")
    try:
        iv_skew_f = float(iv_skew or 0)
    except (TypeError, ValueError):
        iv_skew_f = 0.0
    present = 1.0 if (pcr is not None or gex.get("available") or iv is not None) else 0.0
    pcr_chg = 0.0
    try:
        if pcr is not None and d.get("pcr_prev") is not None:
            pcr_chg = float(pcr) - float(d.get("pcr_prev"))
    except (TypeError, ValueError):
        pcr_chg = 0.0
    try:
        dix_raw = d.get("dix")
        if isinstance(dix_raw, dict):
            dix_raw = dix_raw.get("dix") if dix_raw.get("available") else None
        dix_f = float(dix_raw) if dix_raw is not None else 0.0
        dix_present = 1.0 if dix_raw is not None else 0.0
    except (TypeError, ValueError):
        dix_f = 0.0
        dix_present = 0.0
    return {
        "pcr": float(pcr) if pcr is not None else 0.0,
        "oi_imbalance": float(oi_imb),
        "oi_change": oi_change_f,
        "iv_atm": float(iv) if iv is not None else 0.0,
        "fut_basis_pct": float(basis or 0) / 100.0,
        "vix_level": vix_f,
        "gex_flip": gex_flip,
        "pcr_chg": pcr_chg,
        "iv_skew": iv_skew_f,
        "deriv_present": present,
        "dix": dix_f,
        "dix_present": dix_present,
    }


def _ist_mins(ts) -> float:
    dt = pd.Timestamp(ts)
    if dt.tzinfo is not None:
        dt = dt.tz_convert("Asia/Kolkata")
    return float(dt.hour * 60 + dt.minute) + float(dt.second) / 60.0


def _session_date(ts):
    dt = pd.Timestamp(ts)
    if dt.tzinfo is not None:
        dt = dt.tz_convert("Asia/Kolkata")
    return dt.date()


def clip_for(symbol: str, work: pd.DataFrame) -> Tuple[float, float, float, Optional[float]]:
    """Stop / T1 / T2 points and the 15m ATR they came from, as of the last bar of `work`."""
    atr = fno_risk_engine.bar_atr(work)
    px = float(work["Close"].astype(float).iloc[-1])
    sl_pts, t1_pts, t2_pts, _ = fno_risk_engine.clip_points(symbol, px, atr=atr)
    return sl_pts, t1_pts, t2_pts, atr


def _clip_outcome(future: pd.DataFrame, bearish: bool, sl: float, t1: float) -> str:
    return triple_barrier.path_outcome(future, bearish=bearish, stop=sl, target=t1)


def _clip_resolution(
    future: pd.DataFrame, bearish: bool, sl: float, target: float
) -> Tuple[str, Optional[int]]:
    """Return the conservative barrier outcome and bars until the ticket closes."""
    if future is None or len(future) == 0:
        return "expired", None
    for bars_after_entry, (_, row) in enumerate(future.iterrows(), 1):
        high = float(row["High"])
        low = float(row["Low"])
        stop_hit = high >= sl if bearish else low <= sl
        target_hit = low <= target if bearish else high >= target
        if stop_hit and target_hit:
            return "same_bar_both", bars_after_entry
        if target_hit:
            return "t1_before_sl", bars_after_entry
        if stop_hit:
            return "sl_before_t1", bars_after_entry
    return "expired", None


def _empty_entry_features() -> Dict[str, float]:
    return {
        "side": 0.0,
        "or_width_frac": 0.0,
        "or_ext": 0.0,
        "mins_entry": 0.0,
        "body_frac": 0.0,
        "gap_aligned": 0.0,
        "both_sides": 0.0,
        "first_break": 0.0,
        "confirms": 0.0,
        "prior_range_frac": 0.0,
        "dist_prior_extreme": 0.0,
        "session_range_frac": 0.0,
    }


def _entry_features(work: pd.DataFrame, *, gap_pct: float, force_side: float = 0.0) -> Dict[str, float]:
    """Parameters known at the last bar close — no future path."""
    out = _empty_entry_features()
    if work is None or len(work) < 2:
        return out
    last_ts = work.index[-1]
    out["mins_entry"] = _ist_mins(last_ts)
    px = float(work["Close"].astype(float).iloc[-1])
    o = float(work["Open"].astype(float).iloc[-1])
    h = float(work["High"].astype(float).iloc[-1])
    l = float(work["Low"].astype(float).iloc[-1])
    rng = max(h - l, abs(px) * 0.0001)
    out["body_frac"] = (px - o) / rng
    day = _session_date(last_ts)
    session = work[[_session_date(i) == day for i in work.index]]
    if len(session) < 1:
        return out
    or_hi = float(session["High"].astype(float).iloc[0])
    or_lo = float(session["Low"].astype(float).iloc[0])
    width = or_hi - or_lo
    if px > 0:
        out["or_width_frac"] = max(width, 0.0) / px
    if width > 0:
        if px > or_hi:
            out["side"] = 1.0
            out["or_ext"] = (px - or_hi) / width
        elif px < or_lo:
            out["side"] = -1.0
            out["or_ext"] = (or_lo - px) / width
    if force_side:
        out["side"] = float(np.sign(force_side))
        out["or_ext"] = ((px - or_hi) if force_side > 0 else (or_lo - px)) / max(width, 1.0)
    closes = session["Close"].astype(float)
    tagged_up = bool((closes > or_hi).any())
    tagged_dn = bool((closes < or_lo).any())
    out["both_sides"] = 1.0 if tagged_up and tagged_dn else 0.0
    side = out["side"]
    if side > 0:
        beyond = closes > or_hi
    elif side < 0:
        beyond = closes < or_lo
    else:
        beyond = closes == closes
    out["confirms"] = float(beyond.sum()) if side != 0 else 0.0
    first_idx = None
    for ts, val in beyond.items():
        if side != 0 and bool(val) and _ist_mins(ts) >= FIRST_BREAK_START_MINS:
            first_idx = ts
            break
    out["first_break"] = 1.0 if first_idx is not None and first_idx == last_ts else 0.0
    out["gap_aligned"] = float(np.sign(gap_pct) * side) if side != 0 else 0.0
    prev = work[[_session_date(i) < day for i in work.index]]
    if len(prev):
        prev_day = _session_date(prev.index[-1])
        prev_sess = prev[[_session_date(i) == prev_day for i in prev.index]]
        prev_hi = float(prev_sess["High"].astype(float).max())
        prev_lo = float(prev_sess["Low"].astype(float).min())
        prev_span = max(prev_hi - prev_lo, 1.0)
        if px > 0:
            out["prior_range_frac"] = prev_span / px
            if side > 0:
                out["dist_prior_extreme"] = (prev_hi - px) / px
            elif side < 0:
                out["dist_prior_extreme"] = (px - prev_lo) / px
    sess_span = float(session["High"].astype(float).max() - session["Low"].astype(float).min())
    if px > 0:
        out["session_range_frac"] = sess_span / px
    return out


def _empty_tape() -> Dict[str, float]:
    return {
        "vwap_sess": 0.0,
        "poc_dist": 0.0,
        "adx_14": 0.0,
        "atr_expand": 1.0,
        "rv_vel": 0.0,
        "regime_range": 0.0,
        "regime_trend": 0.0,
        "regime_volatile": 0.0,
        "noise_vs_sl": 0.0,
    }


def _tape_micro(work: pd.DataFrame, symbol: str = "NIFTY") -> Dict[str, float]:
    """Session microstructure from OHLC. Volume bars are not used: index tapes often have volume 0."""
    out = _empty_tape()
    if work is None or len(work) < 4:
        return out
    day = _session_date(work.index[-1])
    sess = work[[_session_date(i) == day for i in work.index]]
    if len(sess) < 2:
        sess = work.tail(min(len(work), 20))
    h = sess["High"].astype(float)
    l = sess["Low"].astype(float)
    c = sess["Close"].astype(float)
    v = sess["Volume"].astype(float) if "Volume" in sess.columns else pd.Series(0.0, index=sess.index)
    last = float(c.iloc[-1])
    if last <= 0:
        return out
    typical = (h + l + c) / 3.0
    vol_sum = float(v.sum())
    if vol_sum > 1.0:
        vwap = float((typical * v).sum() / vol_sum)
        weights = v.to_numpy(dtype=float)
    else:
        vwap = float(typical.mean())
        weights = (h - l).clip(lower=0).to_numpy(dtype=float)
    out["vwap_sess"] = (last - vwap) / last * 100.0
    lo_px = float(l.min())
    hi_px = float(h.max())
    if hi_px > lo_px and float(np.nansum(weights)) > 0:
        bins = 12
        edges = np.linspace(lo_px, hi_px, bins + 1)
        idx = np.clip(np.digitize(typical.to_numpy(dtype=float), edges) - 1, 0, bins - 1)
        bucket = np.zeros(bins)
        for i, w in zip(idx, weights):
            bucket[int(i)] += float(w)
        poc_i = int(np.argmax(bucket))
        poc = (edges[poc_i] + edges[poc_i + 1]) / 2.0
        out["poc_dist"] = (last - poc) / last * 100.0
    rets = c.pct_change().dropna()
    if len(rets) >= 8:
        short = float(rets.tail(4).std() or 0)
        long = float(rets.tail(min(16, len(rets))).std() or 0)
        if long > 0:
            out["rv_vel"] = short / long - 1.0
    look = sess if len(sess) >= 18 else work.tail(min(len(work), 40))
    adx = fno_select._wilder_adx(look)
    expand = fno_select._atr_expand(look)
    out["adx_14"] = adx
    out["atr_expand"] = expand
    if expand >= 1.35:
        out["regime_volatile"] = 1.0
    elif adx >= 25:
        out["regime_trend"] = 1.0
    elif 0 < adx < 20:
        out["regime_range"] = 1.0
    try:
        sl_pts = clip_for(symbol, work)[0]
        bar = float(h.iloc[-1] - l.iloc[-1])
        if sl_pts > 0:
            out["noise_vs_sl"] = bar / float(sl_pts)
    except Exception:
        pass
    return out


def _fit_features(work: pd.DataFrame, *, symbol: str, side: float) -> Dict[str, float]:
    """Level room, clip/volatility fit and 60m trend as model inputs (used once
    a pack is trained with them; older packs simply ignore unknown names)."""
    out = {"htf_bias_num": 0.0, "level_path_frac": 1.0, "noise_vs_stop": 0.0, "target_cover": 0.0}
    try:
        import fno_levels

        htf = fno_levels.htf_bias(work)
        if htf.get("available"):
            out["htf_bias_num"] = 1.0 if htf["bias"] == "BULLISH" else (-1.0 if htf["bias"] == "BEARISH" else 0.0)
        px = float(work["Close"].astype(float).iloc[-1])
        sl_pts, t1_pts, _, _ = clip_for(symbol, work)
        vol = fno_levels.volatility_fit(work, sl_pts=sl_pts, t1_pts=t1_pts, asof=work.index[-1])
        if vol.get("available"):
            out["noise_vs_stop"] = float(vol.get("noise_vs_stop") or 0.0)
            out["target_cover"] = float(vol.get("target_cover") or 0.0)
        if side:
            decision = "BUY" if side > 0 else "SELL"
            sl = px - sl_pts if side > 0 else px + sl_pts
            t1 = px + t1_pts if side > 0 else px - t1_pts
            room = fno_levels.level_room(decision, px, sl, t1, fno_levels.key_levels(work, symbol=symbol))
            if room.get("blocking"):
                out["level_path_frac"] = min(float(b["path_frac"]) for b in room["blocking"])
    except Exception:
        pass
    return out


def features_from_bars(
    df: Any,
    *,
    derivatives: Optional[Dict[str, Any]] = None,
    news_delta: float = 0.0,
    vix_level: float = 0.0,
    symbol: str = "NIFTY",
    force_side: float = 0.0,
    legacy_features: bool = False,
) -> Optional[Dict[str, float]]:
    """15m tape features plus empty-safe derivative slots and entry-time clip context."""
    base = fno_session_model.features_from_bars(df, legacy=legacy_features)
    if not base:
        return None
    work = fno_session_model._norm(df)
    session_chg = 0.0
    gap_pct = 0.0
    oi_change = 0.0
    if work is not None and len(work):
        try:
            day = _session_date(work.index[-1])
            session = work[[_session_date(i) == day for i in work.index]]
            o = float(session["Open"].astype(float).iloc[0])
            c = float(session["Close"].astype(float).iloc[-1])
            if o:
                session_chg = (c - o) / o * 100.0
            prev = work[[_session_date(i) < day for i in work.index]]
            if len(prev) and o:
                prev_c = float(prev["Close"].astype(float).iloc[-1])
                if prev_c:
                    gap_pct = (o - prev_c) / prev_c * 100.0
        except Exception:
            session_chg = 0.0
        raw = df if isinstance(df, pd.DataFrame) else None
        if raw is not None and "oi" in {str(col).lower() for col in raw.columns}:
            col = next(col for col in raw.columns if str(col).lower() == "oi")
            series = raw[col].astype(float)
            if len(series) >= 2 and pd.notna(series.iloc[-1]) and pd.notna(series.iloc[-2]):
                prev_oi = float(series.iloc[-2]) or 1.0
                oi_change = (float(series.iloc[-1]) - prev_oi) / abs(prev_oi) * 100.0
    orb = (
        analysis_engine.detect_opening_range(work, analysis_engine.OPENING_RANGE_BARS)
        if work is not None
        else {}
    )
    or_break = 0.0
    if orb.get("available") and orb.get("broken"):
        or_break = 1.0 if orb.get("bias") == "BULLISH" else -1.0
    deriv = dict(derivatives or {})
    if vix_level and "vix_level" not in deriv:
        deriv["vix_level"] = vix_level
    if oi_change and not deriv.get("oi_change"):
        deriv["oi_change"] = oi_change
    out = dict(base)
    out["or_break"] = or_break
    out["session_chg"] = session_chg
    out["gap_pct"] = gap_pct
    out["news_delta"] = float(news_delta)
    packed = _deriv_features(deriv)
    out.update(packed)
    if not out.get("vix_level") and vix_level:
        out["vix_level"] = float(vix_level)
    if work is not None:
        out.update(_entry_features(work, gap_pct=gap_pct, force_side=force_side))
        out.update(_tape_micro(work, symbol=symbol))
        out.update(fno_structure.structure_features(work))
        out.update(_fit_features(work, symbol=symbol, side=float(out.get("side") or 0.0)))
    else:
        out.update(_empty_entry_features())
        out.update(_empty_tape())
        out.update(fno_structure.empty_structure())
    for name in GMM_NAMES:
        out.setdefault(name, 0.0)
    if float(out.get("dix_present") or 0) < 1 and work is not None and len(work):
        import dark_pool

        lagged = dark_pool.dix_before(_session_date(work.index[-1]))
        if lagged is not None:
            out["dix"] = float(lagged["dix"])
            out["dix_present"] = 1.0
    return out


def feature_vector(
    df: Any,
    *,
    derivatives: Optional[Dict[str, Any]] = None,
    news_delta: float = 0.0,
) -> Optional[np.ndarray]:
    feat = features_from_bars(df, derivatives=derivatives, news_delta=news_delta)
    if not feat:
        return None
    return np.asarray([[float(feat.get(k, 0.0)) for k in FEATURE_NAMES]], dtype=float)


def _feat_row(feat: Dict[str, float], names: Tuple[str, ...]) -> List[float]:
    return [float(feat.get(k, 0.0)) for k in names]


def _xy(
    df: pd.DataFrame,
    symbol: str = "NIFTY",
    chain_db: Optional[str] = None,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    """Up to three sequential live-style tickets per session.

    A new row can be sampled only after the prior ticket reaches T1/SL. Labels
    use the remaining session and resolve conservatively when both barriers
    print in one candle.
    """
    work = fno_session_model._norm(df)
    if work is None or len(work) < 50:
        return None, None, None, None
    dates = [_session_date(i) for i in work.index]
    day_s = pd.Series(dates, index=work.index)
    rows: List[List[float]] = []
    labels: List[int] = []
    runners: List[int] = []
    days: List[str] = []
    prints: List[Dict[str, Any]] = []
    if chain_db:
        import chain_flow

        prints = chain_flow.snapshot_rows(symbol, db_path=chain_db)
    for day in sorted(set(dates)):
        sess = work[day_s == day]
        if len(sess) < 8:
            continue
        or_hi = float(sess["High"].astype(float).iloc[0])
        or_lo = float(sess["Low"].astype(float).iloc[0])
        if or_hi <= or_lo:
            continue
        closes = sess["Close"].astype(float)
        up_locations = np.flatnonzero(closes.to_numpy() > or_hi)
        down_locations = np.flatnonzero(closes.to_numpy() < or_lo)
        first_up_i = int(up_locations[0]) if len(up_locations) else None
        first_dn_i = int(down_locations[0]) if len(down_locations) else None
        i = 1
        tickets = 0
        while i < len(sess) - 1 and tickets < 3:
            ts = sess.index[i]
            mins = _ist_mins(ts)
            if mins < ENTRY_START_MINS or mins > LABEL_END_MINS:
                i += 1
                continue
            px = float(sess["Close"].astype(float).iloc[i])
            up = px > or_hi
            dn = px < or_lo
            if not up and not dn:
                i += 1
                continue
            bearish = dn
            first = i == (first_dn_i if bearish else first_up_i)
            loc = work.index.get_loc(ts)
            gi = int(loc.stop - 1) if isinstance(loc, slice) else int(np.asarray(loc).reshape(-1)[-1])
            prefix = work.iloc[max(0, gi - 140) : gi + 1]
            deriv = None
            if prints:
                import chain_flow

                deriv = chain_flow.reading_from_prints(prints, ts) or None
            feat = features_from_bars(prefix, symbol=symbol, derivatives=deriv)
            if not feat:
                i += 1
                continue
            feat["first_break"] = 1.0 if first else 0.0
            feat["side"] = -1.0 if bearish else 1.0
            sl_pts, t1_pts, t2_pts, _ = clip_for(symbol, prefix)
            sl = px + sl_pts if bearish else px - sl_pts
            t1 = px - t1_pts if bearish else px + t1_pts
            t2 = px - t2_pts if bearish else px + t2_pts
            future = sess.iloc[i + 1 :]
            outcome, bars_to_close = _clip_resolution(future, bearish, sl, t1)
            y = 1 if outcome == "t1_before_sl" else 0
            y_run = 1 if _clip_outcome(future, bearish, sl, t2) == "t1_before_sl" else 0
            rows.append(_feat_row(feat, FEATURE_NAMES))
            labels.append(y)
            runners.append(y_run)
            days.append(str(day))
            tickets += 1
            if bars_to_close is None:
                break
            # A ticket resolved within this future bar. Live scoring can issue
            # the next ticket at that same bar's close after marking the exit.
            i += max(1, int(bars_to_close))
    if len(rows) < 40:
        return None, None, None, None
    return (
        np.asarray(rows, dtype=float),
        np.asarray(labels, dtype=int),
        np.asarray(runners, dtype=int),
        np.asarray(days),
    )


def _xy_cached(
    df: pd.DataFrame,
    symbol: str,
    chain_db: Optional[str],
    data_sha256: Optional[str],
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    """Cache deterministic bar features so full-history policy research is repeatable and fast."""
    if chain_db or not data_sha256:
        return _xy(df, symbol=symbol, chain_db=chain_db)
    digest = str(data_sha256)[:16]
    revision = LABEL_REVISION.replace("/", "_").replace("\\", "_")
    path = os.path.join(
        CACHE_DIR, f"{str(symbol).upper()}_fno_xy_{revision}_{digest}.npz"
    )
    legacy_paths = []
    if os.path.isdir(CACHE_DIR):
        legacy_paths = [
            os.path.join(CACHE_DIR, name)
            for name in os.listdir(CACHE_DIR)
            if name.startswith(f"{str(symbol).upper()}_fno_xy_")
            and name.endswith(f"_{digest}.npz")
        ]
    for candidate in [path, *legacy_paths]:
        if not os.path.isfile(candidate):
            continue
        try:
            with np.load(candidate, allow_pickle=False) as cached:
                if (
                    str(cached["data_sha256"].item()) == str(data_sha256)
                    and tuple(cached["feature_names"].tolist()) == tuple(FEATURE_NAMES)
                    and "label_revision" in cached.files
                    and str(cached["label_revision"].item()) == LABEL_REVISION
                ):
                    return cached["X"], cached["y"], cached["y_run"], cached["days"]
        except (OSError, ValueError, KeyError):
            pass
    result = _xy(df, symbol=symbol, chain_db=chain_db)
    X, y, y_run, days = result
    if X is None or y is None or y_run is None or days is None:
        return result
    os.makedirs(CACHE_DIR, exist_ok=True)
    fd, staged = tempfile.mkstemp(prefix=".fno_xy_", suffix=".npz", dir=CACHE_DIR)
    os.close(fd)
    try:
        np.savez_compressed(
            staged,
            X=X,
            y=y,
            y_run=y_run,
            days=days.astype(str),
            data_sha256=np.asarray(str(data_sha256)),
            feature_names=np.asarray(FEATURE_NAMES),
            label_revision=np.asarray(LABEL_REVISION),
        )
        os.replace(staged, path)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)
    return result


def _holdout_split(days: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    uniq = sorted(set(days.tolist()))
    cut = max(1, int(len(uniq) * (1.0 - HOLDOUT_FRAC)))
    train_days = set(uniq[:cut])
    train_ix = np.array([d in train_days for d in days])
    test_ix = ~train_ix
    if int(test_ix.sum()) < 8:
        n = len(days)
        split = max(20, int(n * (1.0 - HOLDOUT_FRAC)))
        train_ix = np.zeros(n, dtype=bool)
        train_ix[:split] = True
        test_ix = ~train_ix
    return train_ix, test_ix


def _proba_pos(model, X: np.ndarray) -> np.ndarray:
    proba = model.predict_proba(X)
    classes = list(model.classes_)
    if 1 in classes:
        return proba[:, classes.index(1)]
    return np.zeros(len(X), dtype=float)


def _threshold_table(p: np.ndarray, y: np.ndarray, thresholds: Tuple[float, ...]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for thr in thresholds:
        pick = p >= thr
        n = int(pick.sum())
        hits = int(y[pick].sum()) if n else 0
        out[str(thr)] = {"n": n, "t1": hits, "hit": None if n == 0 else round(hits / n, 4)}
    out["always"] = {
        "n": int(len(y)),
        "t1": int(y.sum()),
        "hit": None if len(y) == 0 else round(float(y.mean()), 4),
    }
    return out


def _choose_continue_p(bands: Optional[Dict[str, Any]]) -> float:
    """Use a runner cut only when holdout T2 hit beats the base rate with enough tickets."""
    if not bands:
        return 1.0
    base = (bands.get("always") or {}).get("hit") or 0.0
    best: Optional[Tuple[float, float, int]] = None
    for key, rec in bands.items():
        if key == "always":
            continue
        try:
            thr = float(key)
        except (TypeError, ValueError):
            continue
        hit = rec.get("hit")
        n = int(rec.get("n") or 0)
        if hit is None or n < 15 or hit < float(base) + 0.05:
            continue
        if best is None or hit > best[1] or (hit == best[1] and n > best[2]):
            best = (thr, float(hit), n)
    return best[0] if best else 1.0


def _fit_head(X: np.ndarray, y: np.ndarray):
    if HistGradientBoostingClassifier is None:
        return None
    if len(set(y.tolist())) < 2:
        return None
    model = HistGradientBoostingClassifier(
        max_depth=3, max_iter=80, learning_rate=0.08, random_state=11
    )
    model.fit(X, y)
    return model


def _fit_t1_head(X: np.ndarray, y: np.ndarray):
    """Estimator selected before the final chronological NIFTY evaluation."""
    if ExtraTreesClassifier is None or len(set(y.tolist())) < 2:
        return None
    model = ExtraTreesClassifier(
        n_estimators=300,
        max_depth=10,
        min_samples_leaf=50,
        max_features="sqrt",
        n_jobs=1,
        random_state=11,
    )
    model.fit(X, y)
    return model


def rule_p_t1(feat: Dict[str, float]) -> float:
    """Fallback when no pack: small lift from gap-with-break, no-chase, first break."""
    raw = 0.45
    if feat.get("side", 0) == 0:
        return 0.45
    raw += 0.03 if feat.get("gap_aligned", 0) > 0 else -0.02
    raw += 0.02 if 0 < feat.get("or_ext", 99) <= 0.20 else -0.015
    raw += 0.02 if feat.get("first_break", 0) >= 1 else -0.01
    raw += 0.015 if feat.get("body_frac", 0) * feat.get("side", 0) > 0 else -0.01
    raw += 0.01 if feat.get("both_sides", 0) < 1 else -0.03
    if feat.get("noise_vs_sl", 0) > 1.2:
        raw -= 0.03
    if feat.get("regime_range", 0) >= 1:
        raw -= 0.02
    side = float(feat.get("side") or 0)
    if side and float(feat.get("pat_engulf") or 0) * side > 0:
        raw += 0.01
    if side and float(feat.get("donch_break") or 0) * side > 0:
        raw += 0.01
    bb = float(feat.get("bb_pctb") or 0.5)
    if (side > 0 and bb > 1.05) or (side < 0 and bb < -0.05):
        raw -= 0.01
    return max(0.05, min(0.90, raw))


def _gmm_matrix(X: np.ndarray, names: List[str]) -> np.ndarray:
    idx = [names.index(n) for n in GMM_INPUTS]
    return np.asarray(X[:, idx], dtype=float)


def _apply_gmm(feat: Dict[str, float], pack: Optional[Dict[str, Any]]) -> None:
    """Write train-fit regime probabilities. Missing pack leaves the four slots at 0."""
    if not pack or pack.get("gmm") is None:
        return
    try:
        raw = np.asarray([[float(feat.get(n, 0.0)) for n in pack.get("gmm_inputs") or GMM_INPUTS]], dtype=float)
        mu = np.asarray(pack.get("gmm_mean"), dtype=float)
        sd = np.asarray(pack.get("gmm_scale"), dtype=float)
        order = list(pack.get("gmm_order") or range(4))
        z = (raw - mu) / np.where(sd < 1e-6, 1.0, sd)
        proba = pack["gmm"].predict_proba(z)[0]
        for j, name in enumerate(GMM_NAMES):
            feat[name] = float(proba[int(order[j])])
    except Exception:
        return


def _fit_gmm(X: np.ndarray, train_ix: np.ndarray, names: List[str]):
    """Fit a 4-state mixture on the training days only, then score every row."""
    if GaussianMixture is None:
        return None
    try:
        raw = _gmm_matrix(X, names)
        mu = raw[train_ix].mean(axis=0)
        sd = raw[train_ix].std(axis=0)
        sd = np.where(sd < 1e-6, 1.0, sd)
        z = (raw - mu) / sd
        z_train = z[train_ix]
        if len(z_train) < 80:
            return None
        gmm = GaussianMixture(
            n_components=4,
            covariance_type="diag",
            random_state=11,
            n_init=2,
            max_iter=80,
        )
        gmm.fit(z_train)
        proba = gmm.predict_proba(z)
        atr_col = GMM_INPUTS.index("atr_ratio")
        order = list(np.argsort(gmm.means_[:, atr_col]))
        for j, name in enumerate(GMM_NAMES):
            X[:, names.index(name)] = proba[:, int(order[j])]
        return {
            "gmm": gmm,
            "gmm_mean": mu,
            "gmm_scale": sd,
            "gmm_inputs": list(GMM_INPUTS),
            "gmm_order": order,
        }
    except Exception:
        return None


def train(df: Any, symbol: str = "NIFTY", chain_db: Optional[str] = None) -> Dict[str, Any]:
    """Fit T1-before-SL and continue (T2-before-SL) heads. Reports walk-forward holdout."""
    data_audit = None
    if str(symbol).upper() == "NIFTY":
        from nifty_fno_data import audit, normalize

        data_audit = audit(df)
        df = normalize(df)
    work = fno_session_model._norm(df if isinstance(df, pd.DataFrame) else df)
    if work is None:
        return {"available": False, "reason": "not_enough_rows_or_sklearn", "model_version": MODEL_VERSION}
    X, y, y_run, days = _xy_cached(
        work,
        symbol=symbol,
        chain_db=chain_db,
        data_sha256=(data_audit or {}).get("sha256")
        if (data_audit or {}).get("deep_history_ok") else None,
    )
    if X is None or HistGradientBoostingClassifier is None or ExtraTreesClassifier is None:
        return {"available": False, "reason": "not_enough_rows_or_sklearn", "model_version": MODEL_VERSION}
    train_ix, test_ix = _holdout_split(days)
    if int(train_ix.sum()) < 24 or int(test_ix.sum()) < 8:
        return {"available": False, "reason": "holdout_too_small", "model_version": MODEL_VERSION}
    names = list(FEATURE_NAMES)
    gmm_pack = _fit_gmm(X, train_ix, names) or {}
    model = _fit_t1_head(X[train_ix], y[train_ix])
    if model is None:
        return {"available": False, "reason": "single_class_labels", "model_version": MODEL_VERSION}
    # The selected policy is the global head. Regime-specific blending was not
    # part of the nested selection and therefore stays disabled in this pack.
    range_model = trend_model = None
    p_te = _proba_pos(model, X[test_ix])
    y_te = y[test_ix]
    thresholds = tuple(sorted({0.50, BUY_P, 0.55, 0.58, 0.62, 0.66, 0.70}))
    bands = _threshold_table(p_te, y_te, thresholds)
    at_cut = bands.get(str(BUY_P)) or bands["always"]
    runner = _fit_head(X[train_ix], y_run[train_ix])
    runner_bands = None
    continue_p = CONTINUE_P
    if runner is not None:
        p_run = _proba_pos(runner, X[test_ix])
        runner_bands = _threshold_table(p_run, y_run[test_ix], (0.30, 0.36, 0.42, 0.50, 0.58))
        continue_p = _choose_continue_p(runner_bands)
    # The models above remain an untouched chronological evaluation. Once the
    # threshold is frozen, refit the deployable heads on every labelled day.
    deploy_ix = np.ones(len(y), dtype=bool)
    deploy_gmm = _fit_gmm(X, deploy_ix, names) or gmm_pack
    deploy_model = _fit_t1_head(X, y)
    deploy_runner = _fit_head(X, y_run)
    deploy_range = deploy_trend = None
    if deploy_model is None:
        return {"available": False, "reason": "deployment_fit_failed", "model_version": MODEL_VERSION}
    coverage = {}
    for j, name in enumerate(names):
        col = np.asarray(X[:, j], dtype=float)
        coverage[name] = {
            "nonzero_fraction": round(float(np.mean(np.abs(col) > 1e-12)), 4),
            "unique": int(len(np.unique(col))),
        }
    sl_pts, t1_pts, t2_pts, clip_name = fno_risk_engine.clip_points(
        symbol, float(work["Close"].astype(float).iloc[-1])
    )
    return {
        "available": True,
        "score_kind": "uncalibrated_t1_strategy_score",
        "estimator_kind": "extra_trees_leaf50_nested_chronological",
        "model": deploy_model,
        "range_model": deploy_range,
        "trend_model": deploy_trend,
        "gmm": deploy_gmm.get("gmm"),
        "gmm_mean": deploy_gmm.get("gmm_mean"),
        "gmm_scale": deploy_gmm.get("gmm_scale"),
        "gmm_inputs": deploy_gmm.get("gmm_inputs"),
        "gmm_order": deploy_gmm.get("gmm_order"),
        "runner_model": deploy_runner,
        "feature_names": list(FEATURE_NAMES),
        "label": "t1_before_sl",
        "label_revision": LABEL_REVISION,
        "runner_label": "t2_before_sl",
        "clip": {"name": clip_name, "sl": sl_pts, "t1": t1_pts, "t2": t2_pts, "atr_mult": fno_risk_engine.ATR_STOP_MULT},
        "holdout_accuracy": at_cut.get("hit"),
        "holdout_base_hit": bands["always"]["hit"],
        "holdout_thresholds": bands,
        "holdout_runner_thresholds": runner_bands,
        "n_train": int(train_ix.sum()),
        "n_holdout": int(test_ix.sum()),
        "n_days_train": int(len(set(days[train_ix].tolist()))),
        "n_days_holdout": int(len(set(days[test_ix].tolist()))),
        "n_deploy": int(len(y)),
        "n_days_deploy": int(len(set(days.tolist()))),
        "train_first_day": str(min(days[train_ix].tolist())),
        "train_through_day": str(max(days[train_ix].tolist())),
        "deploy_through_day": str(max(days.tolist())),
        "evaluation_first_day": str(min(days[test_ix].tolist())),
        "evaluation_through_day": str(max(days[test_ix].tolist())),
        "data_audit": data_audit,
        "data_sha256": (data_audit or {}).get("sha256"),
        "feature_coverage": coverage,
        "feature_revision": "nifty_point_in_time_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "build_id": f"{MODEL_VERSION}-{((data_audit or {}).get('sha256') or 'nohash')[:12]}-{str(max(days.tolist()))}",
        "model_version": MODEL_VERSION,
        "interval": "15minute",
        "horizon_bars": HORIZON_BARS,
        "buy_p": BUY_P,
        "sell_p": SELL_P,
        "continue_p": continue_p,
    }


def save(pack: Dict[str, Any], path: Optional[str] = None, symbol: str = "NIFTY") -> str:
    dest = path or model_path(symbol)
    if joblib is None or not pack.get("available"):
        return dest
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    payload = {k: v for k, v in pack.items()}
    fd, staged = tempfile.mkstemp(prefix=".fno_model_", suffix=".pkl", dir=os.path.dirname(dest) or ".")
    os.close(fd)
    try:
        joblib.dump(payload, staged)
        check = joblib.load(staged)
        if not pack_usable(check):
            raise ValueError("staged F&O model failed validation")
        if os.path.isfile(dest):
            shutil.copy2(dest, dest + ".previous")
        os.replace(staged, dest)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)
    return dest


def promotion_check(pack: Optional[Dict[str, Any]], current: Optional[Dict[str, Any]] = None,
                    *, symbol: str = "NIFTY") -> Tuple[bool, str]:
    """Keep scheduled retraining from replacing a stronger or unverified pack."""
    if not pack_usable(pack):
        return False, "candidate pack is not usable"
    if str(symbol).upper() == "NIFTY":
        audit = (pack or {}).get("data_audit") or {}
        if not audit.get("promotion_data_ok"):
            return False, "NIFTY tape has missing rows, incomplete sessions, or long gaps"
        if not audit.get("deep_history_ok"):
            return False, "NIFTY tape does not contain at least 4.5 years and 1,000 complete sessions"
        band = ((pack or {}).get("holdout_thresholds") or {}).get(str(BUY_P)) or {}
        if int(band.get("n") or 0) < 30:
            return False, "fewer than 30 untouched evaluation calls"
        accuracy = (pack or {}).get("holdout_accuracy")
        if accuracy is None or float(accuracy) < 0.55:
            return False, "untouched evaluation hit rate is below the 55% promotion floor"
        old_audit = (current or {}).get("data_audit") or {}
        old_accuracy = (
            (current or {}).get("holdout_accuracy")
            if current and old_audit.get("deep_history_ok") else None
        )
        if old_accuracy is not None and float(accuracy) < float(old_accuracy):
            return False, "candidate evaluation hit rate is below the active pack"
    return True, "promotion checks passed"


def _looks_like_symbol(value: str) -> bool:
    text = str(value or "").strip()
    if not text or text.lower().endswith(".pkl"):
        return False
    if os.path.sep in text or "/" in text or "\\" in text:
        return False
    return text.replace("_", "").replace("-", "").isalnum()


def pack_usable(pack: Optional[Dict[str, Any]]) -> bool:
    """Reject version-mismatched or too-short packs (the 10-day live train)."""
    if not pack or not pack.get("available") or pack.get("model") is None:
        return False
    if pack.get("model_version") != MODEL_VERSION:
        return False
    if int(pack.get("n_train") or 0) < MIN_TRAIN_SAMPLES:
        return False
    if int(pack.get("n_days_train") or 0) < MIN_TRAIN_DAYS:
        return False
    return True


def cached_15m(symbol: str) -> Optional[pd.DataFrame]:
    key = symbol.strip().upper()
    candidates = []
    for name in (f"{key}_15m_5y.csv", f"{key}_15m_6m.csv", f"{key}_15m.csv"):
        path = os.path.join(CACHE_DIR, name)
        if not os.path.isfile(path):
            continue
        try:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            if df is not None and len(df) >= 80:
                if key != "NIFTY":
                    return df
                from nifty_fno_data import audit

                report = audit(df)
                last = pd.Timestamp(report["last"]).value if report.get("last") else 0
                candidates.append(((bool(report.get("promotion_data_ok")), last, len(df)), df))
        except Exception:
            continue
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def bars_for_train(symbol: str, live_df: Any = None) -> Any:
    """Prefer the 5y validation CSV, then merge any fresher live 15m bars."""
    cached = cached_15m(symbol)
    if cached is None:
        return live_df
    if live_df is None or getattr(live_df, "__len__", lambda: 0)() == 0:
        return cached
    a = fno_session_model._norm(cached)
    b = fno_session_model._norm(live_df)
    if a is None:
        return b if b is not None else live_df
    if b is None:
        return a
    out = pd.concat([a, b])
    return out[~out.index.duplicated(keep="last")].sort_index()


def load(path: Optional[str] = None, symbol: str = "NIFTY") -> Dict[str, Any]:
    if path and _looks_like_symbol(str(path)) and not os.path.isfile(str(path)):
        symbol = str(path)
        path = None
    dest = path or model_path(symbol)
    if joblib is None or not os.path.isfile(dest):
        return {"available": False, "model_version": MODEL_VERSION}
    try:
        pack = joblib.load(dest)
        if pack.get("model_version") != MODEL_VERSION or pack.get("model") is None:
            return {"available": False, "reason": "version_mismatch", "model_version": MODEL_VERSION}
        if not pack_usable({**pack, "available": True}):
            return {
                "available": False,
                "reason": "train_window_too_short",
                "model_version": MODEL_VERSION,
                "n_train": pack.get("n_train"),
                "n_days_train": pack.get("n_days_train"),
            }
        pack["available"] = True
        return pack
    except Exception:
        return {"available": False, "model_version": MODEL_VERSION}


def load_or_train(df: Any, symbol: str = "NIFTY") -> Dict[str, Any]:
    pack = load(symbol=symbol)
    if pack_usable(pack):
        return pack
    pack = train(bars_for_train(symbol, df), symbol=symbol)
    if pack_usable(pack):
        save(pack, symbol=symbol)
    return pack


def last_bar_fights(work: Any, side: float, asof: Any = None) -> Optional[str]:
    """The live side is 'still outside the opening range', which stays true all day.
    13 Oct: NIFTY was bought at 10:49 and 11:39 while the last finished 15m bar
    had already closed down (10:30 close 22511, 11:15 close 22486). Both stops
    were that pullback, not a fresh break."""
    if work is None or len(work) < 2 or not side:
        return None
    bar_i = -1
    last_ts = pd.Timestamp(work.index[-1])
    if last_ts.tzinfo is None:
        try:
            last_ts = last_ts.tz_localize("Asia/Kolkata")
        except Exception:
            pass
    end = last_ts + timedelta(minutes=15)
    try:
        if asof is not None:
            now = pd.Timestamp(asof)
        else:
            import market_symbols

            now = pd.Timestamp(market_symbols.ist_now())
        if now.tzinfo is None and last_ts.tzinfo is not None:
            now = now.tz_localize(last_ts.tzinfo)
        elif now.tzinfo is not None and last_ts.tzinfo is None:
            now = now.tz_localize(None)
        if end.tzinfo is None and now.tzinfo is not None:
            end = end.tz_localize(now.tzinfo)
        elif end.tzinfo is not None and now.tzinfo is None:
            now = now.tz_localize(end.tzinfo)
        if end > now:
            bar_i = -2
            last_ts = pd.Timestamp(work.index[-2])
    except Exception:
        bar_i = -1
    # The 9:15 bar *is* the opening range; the break is judged on the bar after it.
    judged_ts = work.index[bar_i]
    judged_day = _session_date(judged_ts)
    if next(i for i in work.index if _session_date(i) == judged_day) == judged_ts:
        return None
    bar = work.iloc[bar_i]
    try:
        o = float(bar["Open"])
        h = float(bar["High"])
        l = float(bar["Low"])
        c = float(bar["Close"])
    except (TypeError, ValueError, KeyError):
        return None
    pos = (c - l) / max(h - l, 1e-9)
    clock = str(last_ts)[11:16]
    if side > 0 and not (c > o and pos >= 0.55):
        return (
            f"Last finished 15m bar ({clock}) closed down. "
            "Model waits for a 15m bar to close up before a BUY."
        )
    if side < 0 and not (c < o and pos <= 0.45):
        return (
            f"Last finished 15m bar ({clock}) closed up. "
            "Model waits for a 15m bar to close down before a SELL."
        )
    return None


def structure_confirms(feat: Dict[str, float], side: float) -> bool:
    """Independent tape checks. None of these is a probability.

    A call needs the break to be real but not chased, the session VWAP and the
    higher-timeframe bias on the same side, and the last candle to close that way.
    A day that has already broken both sides of the opening range does not qualify.
    """
    try:
        side_f = float(side)
        vwap = float((feat or {}).get("vwap_sess") or 0.0)
        htf = float((feat or {}).get("htf_bias_num") or 0.0)
        ext = float((feat or {}).get("or_ext") or 0.0)
        body = float((feat or {}).get("body_frac") or 0.0)
        both = float((feat or {}).get("both_sides") or 0.0)
    except (TypeError, ValueError):
        return False
    if side_f == 0.0 or both >= 1.0:
        return False
    if not 0.0 < ext <= 1.0:
        return False
    if side_f * vwap <= 0.0 or side_f * body <= 0.0 or side_f * htf < 0.0:
        return False
    return True


def regime_structure_note(p_t1: float, buy_p: float, feat: Dict[str, float], side: float) -> Optional[str]:
    """Waive a raised regime cutoff after the 52% floor and the tape both agree."""
    try:
        score = float(p_t1)
        cutoff = float(buy_p)
    except (TypeError, ValueError):
        return None
    if score + 1e-9 < BUY_P or score + 1e-9 >= cutoff:
        return None
    if not structure_confirms(feat, side):
        return None
    return (
        f"Score {score:.0%} cleared {BUY_P:.0%}. "
        "VWAP, the higher timeframe, and the last 15m candle agree, and the break is not extended, "
        f"so the higher {cutoff:.0%} regime cutoff is waived."
    )


def take_signal(
    p_t1: float,
    *,
    side: float,
    first_break: float = 0.0,
    buy_p: float = BUY_P,
    force_side: float = 0.0,
    first_clip: bool = False,
    mins_entry: float = 0.0,
) -> bool:
    """A repeat after 10:15 needs the full bar. The first close outside the range does not."""
    if force_side:
        # Reclaim is not a free trade. 1 Oct BANKNIFTY sold at p=0.39 and hit the stop.
        return float(p_t1) >= float(RECLAIM_P)
    if float(side) == 0:
        return False
    fresh_break = float(first_break) >= 1.0
    cheap_first = (first_clip or fresh_break) and float(p_t1) >= FIRST_BREAK_P
    if cheap_first:
        # 7 Oct NIFTY first closed under the range at 13:00 with p=0.52 and was skipped.
        late = (not fresh_break) and float(mins_entry or 0) > FIRST_CLIP_LATE_MINS
        if not late:
            return True
        return float(p_t1) >= float(buy_p)
    return float(p_t1) >= float(buy_p)


def infer(
    df: Any,
    model_pack: Optional[Dict[str, Any]] = None,
    *,
    derivatives: Optional[Dict[str, Any]] = None,
    news_delta: float = 0.0,
    vix_level: float = 0.0,
    five_min_conflict: bool = False,
    daily_decision: Optional[str] = None,
    gex: Optional[Dict[str, Any]] = None,
    force_side: float = 0.0,
    first_clip: bool = False,
    symbol: str = "NIFTY",
    context: Optional[Dict[str, Any]] = None,
    asof: Any = None,
) -> Dict[str, Any]:
    """`context` carries the daily stack read (ml_proba, adj_tech, news_delta,
    candle_bias, session_bias). It moves the cutoff, never the side."""
    if str(symbol).upper() == "NIFTY":
        from nifty_fno_data import completed

        df = completed(df, asof)
    feat = features_from_bars(
        df, derivatives=derivatives, news_delta=news_delta, vix_level=vix_level, symbol=symbol,
        force_side=force_side,
        legacy_features=bool(model_pack and model_pack.get("model") is not None and not model_pack.get("feature_revision")),
    )
    if not feat:
        return {"available": False, "p_up": 0.5, "p_t1": 0.45, "decision": "HOLD", "source": "none"}
    _apply_gmm(feat, model_pack)
    p_rule = rule_p_t1(feat)
    names = tuple((model_pack or {}).get("feature_names") or FEATURE_NAMES)
    p_t1 = p_rule
    p_runner = None
    source = "rule_fno"
    if model_pack and model_pack.get("available") and model_pack.get("model") is not None:
        try:
            x = np.asarray([_feat_row(feat, names)], dtype=float)
            p_t1 = float(_proba_pos(model_pack["model"], x)[0])
            source = "extra_trees_fno_t1"
            spec = None
            if model_pack.get("use_regime_blend"):
                if float(feat.get("regime_trend") or 0) >= 1 and model_pack.get("trend_model") is not None:
                    spec = model_pack["trend_model"]
                elif float(feat.get("regime_range") or 0) >= 1 and model_pack.get("range_model") is not None:
                    spec = model_pack["range_model"]
            if spec is not None:
                p_spec = float(_proba_pos(spec, x)[0])
                p_t1 = 0.55 * p_spec + 0.45 * p_t1
                source = "hgb_fno_t1_regime"
            runner = model_pack.get("runner_model")
            if runner is not None:
                p_runner = float(_proba_pos(runner, x)[0])
        except Exception:
            p_t1 = p_rule
            source = "rule_fno"
    p_t1 = max(0.05, min(0.95, float(p_t1)))
    if p_runner is not None:
        p_runner = max(0.05, min(0.95, float(p_runner)))
    side = float(force_side or feat.get("side") or 0)
    import chain_flow

    flow = chain_flow.adjust(p_t1, side=side, derivatives=derivatives)
    p_t1 = float(flow["p_t1"])
    work = fno_session_model._norm(df)
    gex = gex or (derivatives or {}).get("gex")
    regime = fno_select.classify_regime(
        work,
        vix_level=vix_level or float(feat.get("vix_level") or 0),
        gex=gex if isinstance(gex, dict) else None,
    )
    align = fno_select.timeframe_align(
        int(side), five_min_conflict=five_min_conflict, daily_decision=daily_decision
    )
    ctx_in = dict(context or {})
    import fno_levels

    try:
        htf = fno_levels.htf_bias(work)
    except Exception:
        htf = {"available": False, "bias": "NEUTRAL"}
    try:
        levels = fno_levels.key_levels(work, symbol=symbol)
    except Exception:
        levels = {"available": False, "levels": {}}
    vix_dir = ctx_in.get("vix_bias") or fno_levels.vix_bias(ctx_in.get("vix"))
    vol_fit: Dict[str, Any] = {"available": False, "hold": None}
    level_vote: Optional[str] = None
    try:
        if work is not None and len(work):
            px_now = float(work["Close"].astype(float).iloc[-1])
            sl_pts, t1_pts, _, _ = clip_for(symbol, work)
            vol_fit = fno_levels.volatility_fit(work, sl_pts=sl_pts, t1_pts=t1_pts, asof=work.index[-1])
            if side:
                room = fno_levels.level_room(
                    "BUY" if side > 0 else "SELL",
                    px_now,
                    px_now - sl_pts if side > 0 else px_now + sl_pts,
                    px_now + t1_pts if side > 0 else px_now - t1_pts,
                    levels,
                )
                if room.get("bias") in ("BULLISH", "BEARISH"):
                    level_vote = room["bias"]
    except Exception:
        vol_fit = {"available": False, "hold": None}
    ctx_align = fno_select.context_align(
        int(side),
        ml_proba=ctx_in.get("ml_proba"),
        adj_tech=ctx_in.get("adj_tech"),
        news_delta=ctx_in.get("news_delta", news_delta if news_delta else None),
        candle_bias=ctx_in.get("candle_bias"),
        session_bias=ctx_in.get("session_bias"),
        htf_bias=htf.get("bias") if htf.get("available") else None,
        vix_bias=vix_dir if vix_dir != "NEUTRAL" else None,
        level_bias=level_vote,
    )
    base_buy_p = float((model_pack or {}).get("buy_p") or BUY_P)
    buy_p = fno_select.meta_cutoff(base_buy_p, regime, align, ctx_align)
    continue_p = float((model_pack or {}).get("continue_p") or CONTINUE_P)
    should_trade = take_signal(
        p_t1,
        side=float(feat.get("side") or 0),
        first_break=float(feat.get("first_break") or 0),
        buy_p=buy_p,
        force_side=float(force_side or 0),
        first_clip=bool(first_clip),
        mins_entry=float(feat.get("mins_entry") or 0),
    )
    bar_note = None
    if side and not force_side:
        bar_note = last_bar_fights(work, side, asof=asof)
        if bar_note and BAR_GATE_BLOCKS:
            should_trade = False
    structure_note = None
    # The validated floor stays 52%. A higher regime cutoff can still waive when
    # the tape itself agrees. Two weeks of NIFTY (8-22 Oct 2026): every bar that
    # cleared 52% and these checks hit the target. Bars under 52% did not.
    if not should_trade and not force_side and not bar_note:
        structure_note = regime_structure_note(p_t1, buy_p, feat, side)
        if structure_note:
            should_trade = True
    # 21 Oct 2026 09:49: the desk bought NIFTY because the hand rule printed 55.5%
    # while the saved model was not the score (source rule_fno, cutoff 50%).
    # That buy stopped 14 minutes later. A requested pack that did not score stays a hold.
    if model_pack is not None and source == "rule_fno":
        should_trade = False
        structure_note = None
        if not bar_note:
            bar_note = "Saved model did not score this bar. The hand rule is not a call."
    fresh_break = float(feat.get("first_break") or 0) >= 1.0
    late_first = bool(
        not force_side
        and not fresh_break
        and first_clip
        and float(feat.get("mins_entry") or 0) > FIRST_CLIP_LATE_MINS
    )
    used_p = (
        RECLAIM_P
        if force_side
        else (
            buy_p
            if late_first
            else (FIRST_BREAK_P if (first_clip or float(feat.get("first_break") or 0) >= 1.0) else buy_p)
        )
    )
    if side > 0 and should_trade:
        decision = "BUY"
        p_up = p_t1
    elif side < 0 and should_trade:
        decision = "SELL"
        p_up = 1.0 - p_t1
    else:
        decision = "HOLD"
        if side > 0:
            p_up = p_t1
        elif side < 0:
            p_up = 1.0 - p_t1
        else:
            p_up = 0.5
    continue_ok = bool(p_runner is not None and p_runner >= continue_p and decision != "HOLD")
    confidence = round(p_t1 * 100, 1)
    pcr = feat.get("pcr")
    pcr_prev = (derivatives or {}).get("pcr_prev")
    pcr_chg = None
    try:
        if pcr is not None and pcr_prev is not None:
            pcr_chg = round(float(pcr) - float(pcr_prev), 4)
    except (TypeError, ValueError):
        pcr_chg = None
    return {
        "available": True,
        "score_kind": "uncalibrated_t1_strategy_score",
        "p_up": round(p_up, 4),
        "p_t1": round(p_t1, 4),
        "p_meta": round(p_t1, 4),
        "p_runner": None if p_runner is None else round(p_runner, 4),
        "p_rule": round(p_rule, 4),
        "buy_p": used_p,
        "meta_buy_p": buy_p,
        "should_trade": should_trade,
        "bar_note": bar_note,
        "structure_note": structure_note,
        "continue_ok": continue_ok,
        "side": int(side),
        "first_clip": bool(first_clip and not force_side),
        "reclaim": bool(force_side),
        "decision": decision,
        "confidence": confidence,
        "source": source,
        "model_version": MODEL_VERSION,
        "label": "t1_before_sl",
        "regime": regime,
        "alignment": align,
        "context": ctx_align,
        "htf": htf,
        "levels": levels,
        "vol_fit": vol_fit,
        "bars_asof": str(work.index[-1]) if work is not None and len(work) else None,
        "clip_atr": None if work is None else fno_risk_engine.bar_atr(work),
        "pcr_chg": pcr_chg,
        "flow_adjust": flow.get("delta"),
        "flow_reasons": flow.get("reasons") or [],
        "dix": None if float(feat.get("dix_present") or 0) < 1 else round(float(feat.get("dix") or 0), 4),
        "holdout_accuracy": (model_pack or {}).get("holdout_accuracy"),
        "holdout_base_hit": (model_pack or {}).get("holdout_base_hit"),
        "features": {k: round(float(feat.get(k, 0.0)), 4) for k in FEATURE_NAMES},
    }
