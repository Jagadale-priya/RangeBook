"""Independent 5m crown live channel (NIFTY / BANKNIFTY / SENSEX).

Uses ExtraTrees crown packs exported from research (same recipe as
~72% @ n≈179 NIFTY 1y book) — NOT dual-track packs.

Parallel to dual-track / overlay — never blocks or replaces existing Calls.
Tag: "5m crown". Kill switch: ENABLE_5M_CROWN=0.
When ENABLE_STACKED_CALLS=1, persist only on HTF-active days within shared cap2.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

import path_setup
ROOT = path_setup.ROOT
# Legacy dir kept for BANKNIFTY/SENSEX; NIFTY resolves via prod_live.paths.
PACK_DIR = ROOT / "stock_signal_data/fno_validate/research/crown_5m_packs"


def _crown_pack_path(symbol: str) -> Path:
    key = str(symbol or "").upper()
    if key == "NIFTY":
        try:
            from prod_live.paths import nifty_crown_pkl

            prod = nifty_crown_pkl(key)
            if prod.is_file():
                return prod
        except Exception:
            pass
    return PACK_DIR / f"fno_{key}_crown_5m.pkl"

SYMBOLS = frozenset({"NIFTY", "BANKNIFTY", "SENSEX"})
# Live desk: crown enabled for all three indices (alongside dual proven/champion).
PRIMARY_SYMBOLS = frozenset({"NIFTY", "BANKNIFTY", "SENSEX"})
TAG_CODE = "5m_crown"
TAG_LABEL = "5m crown"
EXPECTED_HIT_PCT = 72.1

_PACK_CACHE: Dict[str, Optional[dict]] = {}


def enabled() -> bool:
    v = str(os.environ.get("ENABLE_5M_CROWN", "1")).strip().lower()
    return v not in ("0", "false", "no", "off")


def symbol_enabled(symbol: str) -> bool:
    key = str(symbol or "").upper()
    if key in PRIMARY_SYMBOLS:
        return True
    v = str(os.environ.get("ENABLE_5M_CROWN_ALL", "0")).strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    # Auto-enable BN/Sensex only when tuned pack cleared ~62% 1y AND recent 4m
    # is not a tiny/noisy failure (Sensex SELL-only can look fine on 1y, weak on 4m).
    pack = load_pack(key)
    if not pack:
        return False
    if str(pack.get("recipe") or "") != "5m_crown_tuned":
        return False
    if float(pack.get("expected_hit_pct") or 0) < 60.0:
        return False
    tune = pack.get("tune") or {}
    t4 = tune.get("test_4m") or {}
    if t4:
        n4 = int(t4.get("n") or 0)
        a4 = float(t4.get("acc_pct") or 0)
        if n4 > 0 and n4 < 12 and a4 < 55.0:
            return False
        if n4 >= 12 and a4 < 55.0:
            return False
    return True


def _univ_buy_ok(univ: str, or_break: float, prev_body: float, htf_trend: float, row: pd.Series) -> bool:
    u = str(univ or "body05_htf")
    if or_break <= 0:
        return False
    if u in ("body05_htf", "buy_body05_htf"):
        return prev_body >= 0.05 and htf_trend > 0
    if u == "not_stretched":
        vwap = float(row.get("vwap_dist") or 0.0)
        oext = float(row.get("or_ext") or 0.0)
        return (
            prev_body >= 0.04
            and vwap > -0.02
            and vwap < 0.25
            and oext <= 1.2
            and htf_trend >= 0
        )
    if u == "vwap_htf":
        vwap = float(row.get("vwap_dist") or 0.0)
        hvd = float(row.get("htf_vwap_dist") or 0.0)
        return prev_body >= 0.04 and vwap > 0 and hvd > 0 and htf_trend > 0
    return prev_body >= 0.05 and htf_trend > 0


def _univ_sell_ok(univ: str, or_break: float, prev_body: float, htf_trend: float, row: pd.Series) -> bool:
    u = str(univ or "exhaust")
    if or_break >= 0:
        return False
    if u in ("exhaust", "sell_exhaust"):
        oext = float(row.get("or_ext") or 0.0)
        wick = float(row.get("prev_upper_wick") or 0.0)
        cs = float(row.get("cs_score") or 0.0)
        return prev_body >= 0.04 and htf_trend <= 0 and (oext >= 0.3 or wick >= 0.35 or cs <= -4)
    if u in ("body05_htf", "sell_body05_htf"):
        return prev_body >= 0.05 and htf_trend < 0
    if u == "vwap_htf":
        vwap = float(row.get("vwap_dist") or 0.0)
        hvd = float(row.get("htf_vwap_dist") or 0.0)
        return prev_body >= 0.04 and vwap < 0 and hvd < 0 and htf_trend < 0
    return prev_body >= 0.04 and htf_trend <= 0


def crown_tag() -> Dict[str, Any]:
    return {
        "code": TAG_CODE,
        "label": TAG_LABEL,
        "detail": (
            f"Research 5m ExtraTrees crown (~{EXPECTED_HIT_PCT:.0f}% nested 1y). "
            "Independent channel — does not block champion/proven Calls."
        ),
        "expected_hit_pct": EXPECTED_HIT_PCT,
        "tone": "champion",
        "priority": 12,
    }


def packs_available(symbol: str) -> bool:
    return _crown_pack_path(symbol).is_file()


def load_pack(symbol: str) -> Optional[dict]:
    key = str(symbol or "").upper()
    if key in _PACK_CACHE:
        return _PACK_CACHE[key]
    path = _crown_pack_path(key)
    if not path.is_file():
        _PACK_CACHE[key] = None
        return None
    try:
        import joblib

        # Unpickle helpers if present (NIFTY crown packs are plain sklearn).
        sys.path.insert(0, str(ROOT / "tools" / "research"))
        try:
            import tools.research.nifty_side_clean as side_clean  # noqa: F401

            main_mod = sys.modules.get("__main__")
            if main_mod is not None and hasattr(side_clean, "CalibratedHead"):
                setattr(main_mod, "CalibratedHead", side_clean.CalibratedHead)
                setattr(main_mod, "_CalibratedHead", side_clean.CalibratedHead)
        except Exception:
            pass
        pack = joblib.load(path)
        if not pack or not pack.get("buy") or not pack.get("sell"):
            _PACK_CACHE[key] = None
            return None
        _PACK_CACHE[key] = pack
        return pack
    except Exception:
        _PACK_CACHE[key] = None
        return None


def _norm_ohlc(bars: Any) -> Optional[pd.DataFrame]:
    if bars is None or len(bars) < 40:
        return None
    df = bars.copy() if hasattr(bars, "copy") else bars
    if not isinstance(df.index, pd.DatetimeIndex):
        return None
    rename = {}
    for c in df.columns:
        cl = str(c).lower()
        if cl in ("open", "high", "low", "close", "volume"):
            rename[c] = cl[:1].upper() + cl[1:]
    if rename:
        df = df.rename(columns=rename)
    if not {"Open", "High", "Low", "Close"}.issubset(set(df.columns)):
        return None
    return df.sort_index()


def _ist_mins(ts: Any) -> Optional[int]:
    try:
        import fno_session_rules as fsrules

        dt = fsrules.as_ist(ts)
        if dt is None:
            return None
        return int(dt.hour) * 60 + int(dt.minute)
    except Exception:
        return None


_FRAME_CACHE: Dict[tuple, pd.DataFrame] = {}
_FRAME_CACHE_MAX = 64
_HTF_KEYS = (
    "htf_ret3",
    "htf_ret6",
    "htf_rsi",
    "htf_vwap_dist",
    "htf_ema9_dist",
    "htf_trend",
    "htf_range_pos",
)


def _as_15m(bars_15m: Any, bars_5m: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Prefer real 15m tape; else resample 5m → 15m for HTF attach."""
    src = _norm_ohlc(bars_15m) if bars_15m is not None else None
    if src is not None and len(src) >= 25:
        return src
    try:
        b = bars_5m.copy()
        ohlc = b[["Open", "High", "Low", "Close"]].astype(float)
        out = ohlc.resample("15min", label="left", closed="left").agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
        )
        out = out.dropna(how="any")
        return out if len(out) >= 25 else None
    except Exception:
        return None


def _pad_5m_for_labels(bars_5m: pd.DataFrame, pad: int = 8) -> pd.DataFrame:
    """Append flat synthetic bars so build_dataset's `n-6` cutoff keeps latest real bars.

    Research build_dataset loops `range(40, n-6)` and needs 6 forward bars for labels.
    Without padding, a 14:40 crown vanishes when asof is ~15:00.
    """
    if bars_5m is None or len(bars_5m) < 5 or pad <= 0:
        return bars_5m
    last_ts = bars_5m.index[-1]
    last = bars_5m.iloc[-1]
    rows = []
    for k in range(1, int(pad) + 1):
        ts = last_ts + pd.Timedelta(minutes=5 * k)
        row = {
            "Open": float(last["Close"]),
            "High": float(last["Close"]),
            "Low": float(last["Close"]),
            "Close": float(last["Close"]),
        }
        if "Volume" in bars_5m.columns:
            row["Volume"] = float(last.get("Volume") or 0.0)
        rows.append(pd.Series(row, name=ts))
    extra = pd.DataFrame(rows)
    extra.index = pd.DatetimeIndex([r.name for r in rows], tz=getattr(bars_5m.index, "tz", None))
    return pd.concat([bars_5m, extra]).sort_index()


def _build_live_frame(
    bars_5m: pd.DataFrame, bars_15m: Any = None
) -> Optional[pd.DataFrame]:
    """Feature frame = research build_dataset + 15m HTF (add_htf_features).

    Without HTF, htf_ret6 was stubbed to 5m mom6 and crown gates diverged from
    the research pack (~missed 14:40 SELL on 2026-10-14).
    """
    try:
        if bars_5m is None or len(bars_5m) < 5:
            return None
        df15 = _as_15m(bars_15m, bars_5m)
        real_last = bars_5m.index[-1]
        try:
            key = (
                int(len(bars_5m)),
                str(bars_5m.index[0]),
                str(real_last),
                float(bars_5m["Close"].astype(float).iloc[-1]),
                int(len(df15)) if df15 is not None else 0,
                str(df15.index[-1]) if df15 is not None and len(df15) else "",
                "pad8",
            )
        except Exception:
            key = None
        if key is not None and key in _FRAME_CACHE:
            return _FRAME_CACHE[key].copy()

        sys.path.insert(0, str(ROOT / "tools" / "research"))
        from research_nifty_5m_accuracy_deep import ALL_KEYS, add_htf_features
        from research_nifty_5m_candle_model_improve import build_dataset

        padded = _pad_5m_for_labels(bars_5m, pad=8)
        f = build_dataset(padded)
        if f is None or len(f) < 5:
            return None
        # Drop synthetic-forward rows (keep real asof only).
        try:
            when = pd.to_datetime(f["when"], utc=False)
            if getattr(real_last, "tzinfo", None) is not None and when.dt.tz is None:
                when = when.dt.tz_localize(real_last.tzinfo)
            elif when.dt.tz is not None and getattr(real_last, "tzinfo", None) is not None:
                when = when.dt.tz_convert(real_last.tzinfo)
            f = f.loc[when <= real_last].copy()
        except Exception:
            pass
        if f is None or len(f) < 5:
            return None

        htf_ok = False
        if df15 is not None:
            try:
                f = add_htf_features(f, df15)
                htf_ok = all(k in f.columns for k in _HTF_KEYS)
            except Exception:
                htf_ok = False

        for c in ALL_KEYS:
            if c in f.columns:
                # Do not keep mom6 stubs if we failed HTF — still fill missing only.
                continue
            if c == "htf_rsi":
                f[c] = 50.0
            elif c == "htf_ret6" and "mom6" in f.columns:
                f[c] = f["mom6"]
            elif c == "htf_ret3" and "mom3" in f.columns:
                f[c] = f["mom3"]
            elif c == "htf_trend":
                base = f["mom6"] if "mom6" in f.columns else 0.0
                f[c] = np.sign(pd.Series(base).astype(float))
            else:
                f[c] = 0.0
        # If HTF attach ran, trust those columns even when mom6 stubs existed earlier.
        if htf_ok:
            pass
        for c in ("or_break", "prev_body_pct", "or_ext", "vwap_dist", "cs_score", "prev_upper_wick"):
            if c not in f.columns:
                f[c] = 0.0
        if "y_buy_6" not in f.columns:
            f["y_buy_6"] = 0
        if "y_sell_6" not in f.columns:
            f["y_sell_6"] = 0
        if "ret_pct" not in f.columns:
            f["ret_pct"] = 0.0
        if key is not None:
            if len(_FRAME_CACHE) >= _FRAME_CACHE_MAX:
                try:
                    _FRAME_CACHE.pop(next(iter(_FRAME_CACHE)))
                except Exception:
                    _FRAME_CACHE.clear()
            _FRAME_CACHE[key] = f
        return f.copy() if key is not None else f
    except Exception:
        return None


def _row_features(row: pd.Series, keys: List[str]) -> np.ndarray:
    vals = []
    for k in keys:
        try:
            vals.append(float(row.get(k, 0.0) or 0.0))
        except (TypeError, ValueError):
            vals.append(0.0)
    return np.asarray(vals, dtype=float).reshape(1, -1)


def _p_win(clf, X: np.ndarray) -> float:
    try:
        from research_nifty_5m_buy_sell_models import _p_win as pw

        return float(pw(clf, X)[0])
    except Exception:
        if hasattr(clf, "predict_proba"):
            proba = clf.predict_proba(X)[0]
            # class 1 = win
            classes = list(getattr(clf, "classes_", [0, 1]))
            if 1 in classes:
                return float(proba[classes.index(1)])
            return float(proba[-1])
        return 0.0


def _meta_p(meta, X: np.ndarray, p: float) -> float:
    if meta is None:
        return 1.0
    try:
        from research_nifty_5m_buy_sell_models import _p_win as pw

        Xm = np.column_stack([X, [[p]], [[abs(p - 0.5)]]])
        return float(pw(meta, Xm)[0])
    except Exception:
        return 1.0


def soft_sr_ok(decision: str, sr: Optional[float], thr: float = 0.10) -> bool:
    if sr is None:
        return True  # optional if 1m missing
    if decision == "BUY":
        return float(sr) >= thr
    if decision == "SELL":
        return float(sr) <= -thr
    return False


def _session_ret_1m(bars_1m, day: str, mins: int, tol: int) -> Optional[float]:
    try:
        import fno_session_rules as fsrules

        df = _norm_ohlc(bars_1m)
        if df is None:
            return None
        day_mask = [str(fsrules.session_date(t)) == str(day)[:10] for t in df.index]
        sess = df.loc[day_mask]
        if sess.empty:
            return None
        o0 = float(sess["Open"].astype(float).iloc[0])
        if o0 <= 0:
            return None
        best = None
        best_d = tol + 1
        for ts, row in sess.iterrows():
            m = _ist_mins(ts)
            if m is None:
                continue
            d = abs(int(m) - int(mins))
            if d <= tol and d < best_d:
                best_d = d
                best = (float(row["Close"]) - o0) / o0 * 100.0
        return best
    except Exception:
        return None


def _levels(entry: float, decision: str, bars: pd.DataFrame) -> tuple:
    """Simple ATR-ish SL/T1 if pack has none."""
    try:
        import fno_dual_score

        clipped = fno_dual_score._clip_levels(
            "NIFTY", entry, decision, bars
        )
        if clipped:
            return float(clipped[0]), float(clipped[1])
    except Exception:
        pass
    atr = float((bars["High"] - bars["Low"]).astype(float).tail(14).mean() or entry * 0.002)
    if decision == "BUY":
        return round(entry - 1.2 * atr, 2), round(entry + 1.8 * atr, 2)
    return round(entry + 1.2 * atr, 2), round(entry - 1.8 * atr, 2)


def collect_day_candidates(
    symbol: str,
    bars_5m: Any,
    *,
    bars_15m: Any = None,
    asof: Any = None,
    include_soft: bool = True,
) -> List[Dict[str, Any]]:
    """Score session 5m bars once (research-style) for daily_fill waterfall.

    Returns gated 5m_crown rows plus optional soft_crown (p>=0.50 base univ).
    Does not touch crown_5m_store day caps — daily_fill owns 1/day lock.
    Pass bars_15m so HTF matches research pack (add_htf_features).
    """
    out: List[Dict[str, Any]] = []
    try:
        if not enabled():
            return out
        key = str(symbol or "").upper()
        if key not in SYMBOLS:
            return out
        pack = load_pack(key)
        if not pack:
            return out
        bars = _norm_ohlc(bars_5m)
        if bars is None:
            return out
        if asof is None:
            asof = bars.index[-1]
        asof_ts = pd.Timestamp(asof)
        if asof_ts.tzinfo is None and bars.index.tz is not None:
            asof_ts = asof_ts.tz_localize(bars.index.tz)
        elif asof_ts.tzinfo is not None and bars.index.tz is not None:
            asof_ts = asof_ts.tz_convert(bars.index.tz)
        bars = bars.loc[bars.index <= asof_ts]
        if len(bars) < 20:
            return out
        frame = _build_live_frame(bars, bars_15m=bars_15m)
        if frame is None or frame.empty:
            return out
        # session day only
        try:
            import fno_session_rules as fsrules

            day = str(fsrules.session_date(asof_ts))[:10]
        except Exception:
            day = str(asof_ts.date())
        if "day" in frame.columns:
            frame = frame[frame["day"].astype(str).str[:10] == day]
        if frame.empty:
            return out

        keys = list(pack.get("feature_keys") or [])
        if not keys:
            return out
        buy_cfg = pack["buy"]
        sell_cfg = pack["sell"]
        buy_univ = str(buy_cfg.get("univ") or "body05_htf")
        sell_univ = str(sell_cfg.get("univ") or "exhaust")
        buy_k = max(1, int(buy_cfg.get("kday") or 1))
        sell_k = max(1, int(sell_cfg.get("pd") or 1))
        n_buy = n_sell = 0
        n_buy_soft = n_sell_soft = 0

        for _, row in frame.iterrows():
            mins = int(row["mins"]) if "mins" in frame.columns else 0
            or_ext = float(row.get("or_ext") or 0.0)
            htf = float(row.get("htf_ret6") or row.get("mom6") or 0.0)
            or_break = float(row.get("or_break") or 0.0)
            prev_body = abs(float(row.get("prev_body_pct") or 0.0))
            htf_trend = float(row.get("htf_trend") or np.sign(htf))
            X = _row_features(row, keys)
            try:
                entry = float(row.get("close") or row.get("Close") or 0)
            except (TypeError, ValueError):
                entry = 0.0
            if entry <= 0:
                continue

            # BUY
            if _univ_buy_ok(buy_univ, or_break, prev_body, htf_trend, row):
                if (
                    float(buy_cfg["or_ext_min"]) <= or_ext
                    and float(buy_cfg["htf_min"]) <= htf <= float(buy_cfg["htf_max"])
                    and int(buy_cfg["lo"]) <= mins <= int(buy_cfg["hi"])
                ):
                    p = _p_win(buy_cfg["model"], X)
                    meta_p = _meta_p(buy_cfg.get("meta"), X, p)
                    gated = (
                        p >= 0.50
                        and p >= float(buy_cfg["qth"])
                        and meta_p >= float(buy_cfg["meta_min"])
                    )
                    soft = include_soft and (p >= 0.50) and not gated
                    if gated and n_buy < buy_k:
                        sl, t1 = _levels(entry, "BUY", bars)
                        out.append(
                            {
                                "symbol": key,
                                "decision": "BUY",
                                "entry": round(entry, 2),
                                "stop_loss": sl,
                                "target_1": t1,
                                "p_t1": round(float(p), 4),
                                "mins": mins,
                                "track": TAG_CODE,
                                "gated": True,
                                "session_date": day,
                            }
                        )
                        n_buy += 1
                    elif soft and n_buy_soft < max(1, buy_k):
                        sl, t1 = _levels(entry, "BUY", bars)
                        out.append(
                            {
                                "symbol": key,
                                "decision": "BUY",
                                "entry": round(entry, 2),
                                "stop_loss": sl,
                                "target_1": t1,
                                "p_t1": round(float(p), 4),
                                "mins": mins,
                                "track": "soft_crown",
                                "gated": False,
                                "session_date": day,
                            }
                        )
                        n_buy_soft += 1

            # SELL
            if _univ_sell_ok(sell_univ, or_break, prev_body, htf_trend, row):
                if htf <= float(sell_cfg["htf_max"]):
                    vwap = float(row.get("vwap_dist") or 0.0)
                    if vwap >= float(sell_cfg["vd"]):
                        p = _p_win(sell_cfg["model"], X)
                        gated = p >= 0.50 and p >= float(sell_cfg["qth"])
                        soft = include_soft and (p >= 0.50) and not gated
                        if gated and n_sell < sell_k:
                            sl, t1 = _levels(entry, "SELL", bars)
                            out.append(
                                {
                                    "symbol": key,
                                    "decision": "SELL",
                                    "entry": round(entry, 2),
                                    "stop_loss": sl,
                                    "target_1": t1,
                                    "p_t1": round(float(p), 4),
                                    "mins": mins,
                                    "track": TAG_CODE,
                                    "gated": True,
                                    "session_date": day,
                                }
                            )
                            n_sell += 1
                        elif soft and n_sell_soft < max(1, sell_k):
                            sl, t1 = _levels(entry, "SELL", bars)
                            out.append(
                                {
                                    "symbol": key,
                                    "decision": "SELL",
                                    "entry": round(entry, 2),
                                    "stop_loss": sl,
                                    "target_1": t1,
                                    "p_t1": round(float(p), 4),
                                    "mins": mins,
                                    "track": "soft_crown",
                                    "gated": False,
                                    "session_date": day,
                                }
                            )
                            n_sell_soft += 1
        return out
    except Exception:
        return out


def evaluate_latest(
    symbol: str,
    bars_5m: Any,
    *,
    bars_1m: Any = None,
    bars_15m: Any = None,
    price: Optional[float] = None,
    asof: Any = None,
    day_range: Optional[dict] = None,
    db_path: Optional[str] = None,
    soft_fill: bool = False,
) -> Optional[Dict[str, Any]]:
    """Score latest bar with ExtraTrees crown packs + research gates.

    soft_fill=True: research soft_crown path (base univ + p>=0.50, no qth/meta).
    Used only by daily_fill empty-day cover — never by the live crown channel.
    bars_15m enables research-identical HTF (required for pack accuracy).
    """
    try:
        if not enabled():
            return None
        key = str(symbol or "").upper()
        if key not in SYMBOLS:
            return None
        if not soft_fill and not symbol_enabled(key):
            return None
        pack = load_pack(key)
        if not pack:
            return None
        bars = _norm_ohlc(bars_5m)
        if bars is None:
            return None
        if asof is None:
            asof = bars.index[-1]

        frame = _build_live_frame(bars, bars_15m=bars_15m)
        if frame is None or frame.empty:
            return None

        # latest feature row
        row = frame.iloc[-1]
        mins = int(row["mins"]) if "mins" in frame.columns else _ist_mins(asof)
        if mins is None:
            return None
        day = str(row["day"]) if "day" in frame.columns else str(asof)[:10]

        keys = list(pack.get("feature_keys") or [])
        if not keys:
            return None
        X = _row_features(row, keys)

        buy_cfg = pack["buy"]
        sell_cfg = pack["sell"]
        or_ext = float(row.get("or_ext") or 0.0)
        htf = float(row.get("htf_ret6") or row.get("mom6") or 0.0)
        or_break = float(row.get("or_break") or 0.0)
        prev_body = abs(float(row.get("prev_body_pct") or 0.0))
        htf_trend = float(row.get("htf_trend") or np.sign(htf))

        want = None
        p = 0.0
        meta_p = 1.0
        buy_univ = str(buy_cfg.get("univ") or "body05_htf")
        sell_univ = str(sell_cfg.get("univ") or "exhaust")
        # Universe + gates from pack (per-symbol tuned for BN/Sensex)
        if _univ_buy_ok(buy_univ, or_break, prev_body, htf_trend, row):
            if (
                float(buy_cfg["or_ext_min"]) <= or_ext
                and float(buy_cfg["htf_min"]) <= htf <= float(buy_cfg["htf_max"])
                and int(buy_cfg["lo"]) <= mins <= int(buy_cfg["hi"])
            ):
                p = _p_win(buy_cfg["model"], X)
                meta_p = _meta_p(buy_cfg.get("meta"), X, p)
                if soft_fill:
                    if p >= 0.50:
                        want = "BUY"
                elif p >= 0.50 and p >= float(buy_cfg["qth"]) and meta_p >= float(buy_cfg["meta_min"]):
                    want = "BUY"
        if want is None and _univ_sell_ok(sell_univ, or_break, prev_body, htf_trend, row):
            if htf <= float(sell_cfg["htf_max"]):
                vwap = float(row.get("vwap_dist") or 0.0)
                if vwap >= float(sell_cfg["vd"]):
                    p = _p_win(sell_cfg["model"], X)
                    if soft_fill:
                        if p >= 0.50:
                            want = "SELL"
                    elif p >= 0.50 and p >= float(sell_cfg["qth"]):
                        want = "SELL"

        if want is None:
            return None

        # day caps (skip for soft_fill — daily_fill owns the 1/day lock)
        if not soft_fill:
            try:
                import crown_5m_store as store

                limit = int(buy_cfg["kday"] if want == "BUY" else sell_cfg["pd"])
                n_side = store.count_today(key, day, side=want, db_path=db_path)
                if n_side >= limit:
                    return None
            except Exception:
                pass

        thr = float(pack.get("soft_sr_thr") or 0.10)
        tol = int(pack.get("soft_sr_tol") or 10)
        sr = _session_ret_1m(bars_1m, day, mins, tol)
        if not soft_sr_ok(want, sr, thr):
            return None

        try:
            entry = float(price) if price is not None else float(row.get("close") or row.get("Close") or 0)
        except (TypeError, ValueError):
            entry = float(bars["Close"].iloc[-1])
        if entry <= 0:
            return None
        sl, t1 = _levels(entry, want, bars)
        bar_ts = bars.index[-1]
        bar_time = bar_ts.isoformat() if hasattr(bar_ts, "isoformat") else str(bar_ts)

        track = "soft_crown" if soft_fill else TAG_CODE
        sig = {
            "symbol": key,
            "decision": want,
            "entry": round(entry, 2),
            "stop_loss": sl,
            "target_1": t1,
            "p_t1": round(float(p), 4),
            "meta_p": round(float(meta_p), 4),
            "or_ext": round(or_ext, 4),
            "htf_ret6": round(htf, 4),
            "session_ret_1m": None if sr is None else round(float(sr), 4),
            "mins": mins,
            "bar_time": bar_time,
            "session_date": str(day)[:10],
            "taken_at": bar_time,
            "track": track,
            "source": "fno_5m_crown",
            "channel": TAG_LABEL,
            "accuracy_label": TAG_LABEL if not soft_fill else "soft crown fill",
            "accuracy_tags": [crown_tag()],
            "expected_hit_pct": float(pack.get("expected_hit_pct") or EXPECTED_HIT_PCT),
            "dual_track": False,
            "independent": True,
            "soft_fill": bool(soft_fill),
            "recipe": "extratrees_crown",
            "message": (
                f"{want} {'soft crown' if soft_fill else '5m crown'} · p={p*100:.0f}% · "
                f"or_ext={or_ext:.2f} · htf6={htf:.2f} (ExtraTrees research pack)"
            ),
        }
        # Clean morning / Clean multi tags (quality crown · research streams)
        if not soft_fill:
            try:
                import fno_clean_call_tags as clean_tags

                clean_tags.stamp_clean(
                    sig,
                    asof=bar_ts,
                    mins=mins,
                    track="crown_5m",
                    candle_bias=sig.get("candle_bias"),
                )
            except Exception:
                pass
        return sig
    except Exception:
        return None


def attach_to_result(
    result: Dict[str, Any],
    symbol: str,
    bars_5m: Any,
    *,
    bars_1m: Any = None,
    price: Optional[float] = None,
    asof: Any = None,
    day_range: Optional[dict] = None,
    session_ticket: Optional[dict] = None,
) -> Dict[str, Any]:
    """Evaluate, persist, notify. Never raises; never touches dual-track tickets.

    Under ENABLE_STACKED_CALLS, crown only persists on HTF-active days and when
    the shared day cap / same-side rules allow (research stack_plus_crown_htf_cap2).
    """
    out: Dict[str, Any] = {"ok": False}
    try:
        if not enabled():
            result["crown_5m"] = {"enabled": False}
            return {"ok": True, "enabled": False}
        key = str(symbol or "").upper()
        if not packs_available(key):
            result["crown_5m"] = {"enabled": True, "signal": None, "reason": "packs_missing"}
            return {"ok": True, "reason": "packs_missing"}

        sig = evaluate_latest(
            key,
            bars_5m,
            bars_1m=bars_1m,
            price=price,
            asof=asof,
            day_range=day_range,
        )
        result["crown_5m"] = {"enabled": True, "signal": sig}
        if not sig:
            return {"ok": True, "signal": None}

        # Stamp Clean morning / Clean multi using live candle + overlay context
        try:
            import fno_clean_call_tags as clean_tags

            candle_bias = (result.get("candlestick") or {}).get("bias")
            clean_tags.stamp_clean(
                sig,
                asof=asof,
                mins=sig.get("mins"),
                track="crown_5m",
                candle_bias=candle_bias,
                overlay_today=result.get("overlay_indication_today"),
                overlay_sig=result.get("overlay_indication"),
                snap=result,
            )
            result["crown_5m"]["signal"] = sig
        except Exception:
            pass

        try:
            import fno_stacked_calls

            gate = fno_stacked_calls.crown_may_persist(
                key,
                str(sig.get("decision") or ""),
                session_ticket=session_ticket
                if session_ticket is not None
                else (result.get("session_ticket") if isinstance(result, dict) else None),
                asof=asof,
            )
            result["crown_5m"]["stack_gate"] = gate
            if not gate.get("allow"):
                result["crown_5m"]["gated"] = True
                result["crown_5m"]["gate_reason"] = gate.get("reason")
                return {"ok": True, "signal": sig, "gated": True, "gate": gate}
        except Exception as exc:
            result["crown_5m"]["stack_gate_error"] = str(exc)

        import crown_5m_store as store

        saved = store.upsert_signal(sig)
        result["crown_5m"]["saved"] = saved
        out = {"ok": True, "signal": sig, "saved": saved}

        if saved.get("ok") and saved.get("created") and saved.get("id") is not None:
            rid = int(saved["id"])
            if store.claim_notify(rid):
                try:
                    import desktop_notify

                    ok = desktop_notify.notify_5m_crown_call(
                        key,
                        sig["decision"],
                        entry=sig.get("entry"),
                        stop=sig.get("stop_loss"),
                        target=sig.get("target_1"),
                        accuracy_label=sig.get("accuracy_label") or TAG_LABEL,
                        row_id=rid,
                    )
                    result["crown_5m"]["notified"] = bool(ok)
                    out["notified"] = bool(ok)
                except Exception as exc:
                    result["crown_5m"]["notify_error"] = str(exc)

        try:
            day = sig.get("session_date")
            if day:
                result["crown_5m_today"] = store.list_today(key, day)
        except Exception:
            pass
        return out
    except Exception as exc:
        result["crown_5m_error"] = str(exc)
        return {"ok": False, "error": str(exc)}
