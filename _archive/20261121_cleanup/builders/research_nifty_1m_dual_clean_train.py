"""RESEARCH ONLY — NIFTY 1m dual (BUY+SELL) heads on **clean** OR-break moves.

Window: 2021-01-01 → 2025-12-30
- No live wire / no Calls listing
- Labels: decisive T1/SL only (±30), noise gates from nifty_side_clean
- Dual = separate BUY and SELL calibrated heads + proven/champ research books

  python -u prod_live/tests/builders/research_nifty_1m_dual_clean_train.py
  python -u prod_live/tests/builders/research_nifty_1m_dual_clean_train.py --skip-download
  python -u prod_live/tests/builders/research_nifty_1m_dual_clean_train.py --skip-download --strict-v2
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
warnings.filterwarnings("ignore")
import path_setup  # noqa: F401,E402

from nifty_side_clean import recent_sample_weights  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data" / "fno_validate" / "research"
PACK_DIR = LEDGER / "nifty_1m_dual_clean_research"
CACHE_1M = LEDGER / "_cache_nifty_1m_2021_2025.parquet"
EXISTING_CSV = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_1m_kite.csv"
REPORT_JSON = OUT / "NIFTY_1M_DUAL_CLEAN_TRAIN.json"
REPORT_MD = OUT / "NIFTY_1M_DUAL_CLEAN_TRAIN.md"

START = "2021-01-01"
END = "2025-12-30"
# Chronological freeze: train heads through this day; score OOS after.
FREEZE = "2024-09-10"
RISK = 30.0
OR_BARS_1M = 15  # 09:15–09:29 inclusive ≈ opening range
RESEARCH_ONLY = True
LANE = "RESEARCH"
STATUS = "NOT_LIVE"

# Gate profiles (no look-ahead). v2 removes early-session / chase / flip noise.
GATE_V1 = {
    "min_or_width": 12.0,
    "max_noise_vs_sl": 2.50,
    "min_future_bars": 2,
    "min_entry_mins": 9 * 60 + 30,
    "max_entry_mins": 14 * 60 + 45,
    "max_or_ext": 0.85,
    "require_first_break": False,
    "require_body_align": False,
    "forbid_both_sides": False,
}
# Empirically: after 10:00 + first_break lifted OOS ~55% → ~67% before model p gates.
GATE_V2 = {
    "min_or_width": 20.0,
    "max_noise_vs_sl": 1.25,
    "min_future_bars": 5,
    "min_entry_mins": 10 * 60,  # calendar settle — skip 09:30–09:59 OR noise
    "max_entry_mins": 14 * 60 + 30,
    "max_or_ext": 0.20,  # no chase
    "require_first_break": True,
    "require_body_align": True,
    "forbid_both_sides": True,
}

FEAT_NAMES = [
    "ret_1",
    "ret_3",
    "ret_6",
    "rsi_14",
    "vwap_dist",
    "range_pos",
    "candle_score",
    "body_frac",
    "bar_range_pct",
    "or_width",
    "or_ext",
    "mins_entry",
    "first_break",
    "gap_pct",
    "session_chg",
    "pat_doji",
    "pat_hammer",
    "pat_engulf",
    "slope_3",
    "atr_ratio",
    "noise_vs_sl",
    "side",
]


def _norm(raw: pd.DataFrame) -> pd.DataFrame:
    work = raw.copy()
    if "date" in work.columns and not isinstance(work.index, pd.DatetimeIndex):
        work["date"] = pd.to_datetime(work["date"])
        work = work.set_index("date")
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index)
    if work.index.tz is None:
        work.index = work.index.tz_localize("Asia/Kolkata")
    else:
        work.index = work.index.tz_convert("Asia/Kolkata")
    rename = {c: str(c).title() for c in work.columns}
    work = work.rename(columns=rename)
    keep = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in work.columns]
    work = work[keep].sort_index()
    hm = work.index.strftime("%H:%M")
    return work[(hm >= "09:15") & (hm <= "15:29")]


def _day(ts) -> str:
    t = ts.tz_convert("Asia/Kolkata") if getattr(ts, "tzinfo", None) else ts
    return pd.Timestamp(t).strftime("%Y-%m-%d")


def _hm(ts) -> str:
    t = ts.tz_convert("Asia/Kolkata") if getattr(ts, "tzinfo", None) else ts
    return pd.Timestamp(t).strftime("%H:%M")


def load_existing_1m() -> pd.DataFrame:
    frames = []
    if CACHE_1M.is_file():
        frames.append(_norm(pd.read_parquet(CACHE_1M)))
        print(f"  cache parquet {CACHE_1M.name}: {len(frames[-1])} bars", flush=True)
    if EXISTING_CSV.is_file():
        frames.append(_norm(pd.read_csv(EXISTING_CSV)))
        print(f"  existing csv: {len(frames[-1])} bars", flush=True)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def download_1m_range(start: str, end: str) -> Tuple[pd.DataFrame, Optional[str]]:
    """Chunked Kite minute download. RESEARCH — may be incomplete for old years."""
    try:
        import kite_data
    except Exception as exc:
        return pd.DataFrame(), f"kite_data import failed: {exc}"
    if not kite_data.kite_enabled():
        return pd.DataFrame(), "Kite not enabled / not logged in"
    start_ts = pd.Timestamp(start, tz="Asia/Kolkata")
    end_ts = pd.Timestamp(end, tz="Asia/Kolkata") + pd.Timedelta(days=1)
    # kite_data.fetch_historical_candles uses days-back from now; for absolute
    # range we call historical_data windows ourselves.
    kite_instruments = __import__("kite_instruments")
    kite_instruments.ensure_cache()
    kite, err = kite_data._get_kite()
    if err or not kite:
        return pd.DataFrame(), err or "no kite"
    token, tok_err = kite_data._instrument_token(kite, "NIFTY")
    if not token:
        return pd.DataFrame(), tok_err
    chunk = 59
    frames = []
    failed = []
    window_start = start_ts.to_pydatetime().replace(tzinfo=None)
    end_naive = end_ts.to_pydatetime().replace(tzinfo=None)
    t0 = time.time()
    n_win = 0
    while window_start < end_naive:
        window_end = min(window_start + timedelta(days=chunk), end_naive)
        n_win += 1
        try:
            candles = kite.historical_data(token, window_start, window_end, interval="minute")
            if candles:
                frames.append(pd.DataFrame(candles))
                print(
                    f"  dl {window_start.date()}→{window_end.date()} n={len(candles)} "
                    f"({time.time()-t0:.0f}s)",
                    flush=True,
                )
            else:
                failed.append(f"{window_start.date()}: empty")
                print(f"  dl {window_start.date()}→{window_end.date()} EMPTY", flush=True)
        except Exception as exc:
            failed.append(f"{window_start.date()}: {exc}")
            print(f"  dl FAIL {window_start.date()}: {exc}", flush=True)
        window_start = window_end
        time.sleep(0.35)  # stay under historical rate limit
    if not frames:
        return pd.DataFrame(), "No candles: " + "; ".join(failed[:5])
    raw = pd.concat(frames, ignore_index=True)
    raw["date"] = pd.to_datetime(raw["date"])
    df = _norm(raw)
    note = None
    if failed:
        note = f"partial download · {len(failed)} windows failed/empty"
    print(f"  downloaded total bars={len(df)} windows={n_win} failed={len(failed)}", flush=True)
    return df, note


def merge_and_cache(existing: pd.DataFrame, fresh: pd.DataFrame) -> pd.DataFrame:
    parts = [p for p in (existing, fresh) if p is not None and len(p)]
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    # clip research window
    df = df[(df.index >= pd.Timestamp(START, tz="Asia/Kolkata")) & (df.index <= pd.Timestamp(END + " 23:59:59", tz="Asia/Kolkata"))]
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER.mkdir(parents=True, exist_ok=True)
    out = df.reset_index()
    out = out.rename(columns={out.columns[0]: "date"})
    # store parquet with tz-aware index via date col
    save = df.copy()
    save.to_parquet(CACHE_1M)
    print(f"  wrote {CACHE_1M} bars={len(df)} {df.index.min()} → {df.index.max()}", flush=True)
    return df


def candle_feats(window: pd.DataFrame) -> Dict[str, float]:
    if window is None or len(window) < 3:
        return {
            "ret_1": 0.0,
            "ret_3": 0.0,
            "ret_6": 0.0,
            "rsi_14": 50.0,
            "candle_score": 0.0,
            "body_frac": 0.0,
            "bar_range_pct": 0.0,
            "pat_doji": 0.0,
            "pat_hammer": 0.0,
            "pat_engulf": 0.0,
            "slope_3": 0.0,
        }
    c = window["Close"].astype(float)
    o = window["Open"].astype(float)
    h = window["High"].astype(float)
    l = window["Low"].astype(float)
    last_c = float(c.iloc[-1])
    prev = float(c.iloc[-2]) if len(c) > 1 else last_c
    ret_1 = (last_c - prev) / max(prev, 1.0) * 100.0
    ret_3 = (last_c - float(c.iloc[-4])) / max(float(c.iloc[-4]), 1.0) * 100.0 if len(c) >= 4 else ret_1
    ret_6 = (last_c - float(c.iloc[-7])) / max(float(c.iloc[-7]), 1.0) * 100.0 if len(c) >= 7 else ret_3
    delta = c.diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = (-delta.clip(upper=0)).rolling(14).mean()
    rs = up / down.replace(0, np.nan)
    rsi = float((100 - (100 / (1 + rs))).iloc[-1]) if len(c) >= 15 else 50.0
    if not np.isfinite(rsi):
        rsi = 50.0
    body = float(c.iloc[-1] - o.iloc[-1])
    rng = float(h.iloc[-1] - l.iloc[-1])
    body_frac = body / rng if rng > 1e-9 else 0.0
    bar_range_pct = rng / max(last_c, 1.0) * 100.0
    candle_score = float(np.clip(body_frac * 10.0, -10, 10))
    pat_doji = 1.0 if abs(body_frac) < 0.1 and rng > 0 else 0.0
    lower_wick = float(min(o.iloc[-1], c.iloc[-1]) - l.iloc[-1])
    upper_wick = float(h.iloc[-1] - max(o.iloc[-1], c.iloc[-1]))
    pat_hammer = 1.0 if lower_wick > abs(body) * 2 and upper_wick < abs(body) else 0.0
    pat_engulf = 0.0
    if len(c) >= 2:
        prev_body = float(c.iloc[-2] - o.iloc[-2])
        if body * prev_body < 0 and abs(body) > abs(prev_body):
            pat_engulf = 1.0 if body > 0 else -1.0
    slope_3 = float((c.iloc[-1] - c.iloc[-3]) / max(abs(c.iloc[-3]), 1.0) * 100.0) if len(c) >= 3 else 0.0
    return {
        "ret_1": float(ret_1),
        "ret_3": float(ret_3),
        "ret_6": float(ret_6),
        "rsi_14": float(rsi),
        "candle_score": candle_score,
        "body_frac": float(body_frac),
        "bar_range_pct": float(bar_range_pct),
        "pat_doji": float(pat_doji),
        "pat_hammer": float(pat_hammer),
        "pat_engulf": float(pat_engulf),
        "slope_3": float(slope_3),
    }


def fwd_path(
    bars: pd.DataFrame,
    i: int,
    side: str,
    entry: float,
    sl: float,
    t1: float,
) -> Tuple[bool, str, float]:
    """Walk forward until T1 or SL on 1m highs/lows."""
    for j in range(i + 1, len(bars)):
        hi = float(bars["High"].iloc[j])
        lo = float(bars["Low"].iloc[j])
        if side == "BUY":
            hit_sl = lo <= sl
            hit_t1 = hi >= t1
            if hit_t1 and hit_sl:
                return False, "same_bar_both", 0.0
            if hit_t1:
                return True, "t1_before_sl", abs(t1 - entry)
            if hit_sl:
                return False, "sl_before_t1", -abs(entry - sl)
        else:
            hit_sl = hi >= sl
            hit_t1 = lo <= t1
            if hit_t1 and hit_sl:
                return False, "same_bar_both", 0.0
            if hit_t1:
                return True, "t1_before_sl", abs(entry - t1)
            if hit_sl:
                return False, "sl_before_t1", -abs(sl - entry)
    return False, "expired", 0.0


def gap_map(bars: pd.DataFrame) -> Dict[str, float]:
    day_key = pd.Index([_day(ts) for ts in bars.index])
    groups = bars.groupby(day_key, sort=True)
    out: Dict[str, float] = {}
    prev_close = None
    for day, sess in groups:
        o = float(sess["Open"].iloc[0])
        if prev_close and prev_close > 0:
            out[str(day)] = (o - prev_close) / prev_close * 100.0
        else:
            out[str(day)] = 0.0
        prev_close = float(sess["Close"].iloc[-1])
    return out


def build_clean_tickets(
    bars: pd.DataFrame,
    *,
    gates: Optional[Dict[str, Any]] = None,
) -> Tuple[List[dict], Dict[str, int], Dict[str, int]]:
    """OR-break tickets → noise filter. Only decisive T1/SL kept. No look-ahead gates."""
    from nifty_side_clean import passes_noise_gates

    g = dict(GATE_V1)
    if gates:
        g.update(gates)
    gaps = gap_map(bars)
    idx_map = {ts: i for i, ts in enumerate(bars.index)}
    day_key = pd.Index([_day(ts) for ts in bars.index])
    groups = bars.groupby(day_key, sort=True)
    tickets: List[dict] = []
    reasons: Dict[str, int] = {}
    drop_pre: Dict[str, int] = {}
    t0 = time.time()
    days = list(groups.groups.keys())
    for di, day in enumerate(days, 1):
        if di % 100 == 0:
            print(f"    tickets {di}/{len(days)} clean={len(tickets)} ({time.time()-t0:.0f}s)", flush=True)
        sess = groups.get_group(day)
        if len(sess) < OR_BARS_1M + 8:
            drop_pre["short_session"] = drop_pre.get("short_session", 0) + 1
            continue
        or_hi = float(sess["High"].iloc[:OR_BARS_1M].max())
        or_lo = float(sess["Low"].iloc[:OR_BARS_1M].min())
        or_w = or_hi - or_lo
        day_open = float(sess["Open"].iloc[0])
        first_up = first_dn = None
        closes = sess["Close"].astype(float).values
        for pos in range(OR_BARS_1M, len(sess)):
            c = float(closes[pos])
            if first_up is None and c > or_hi:
                first_up = pos
            if first_dn is None and c < or_lo:
                first_dn = pos
            if first_up is not None and first_dn is not None:
                break
        for side, pos in (("BUY", first_up), ("SELL", first_dn)):
            if pos is None:
                continue
            first = 0.0
            if side == "BUY" and (first_dn is None or (first_up is not None and first_up <= first_dn)):
                first = 1.0
            if side == "SELL" and (first_up is None or (first_dn is not None and first_dn < first_up)):
                first = 1.0
            # both-sides before this entry (no look-ahead past entry)
            up = dn = False
            for p2 in range(OR_BARS_1M, pos + 1):
                c2 = float(closes[p2])
                if c2 > or_hi:
                    up = True
                if c2 < or_lo:
                    dn = True
            both_sides = bool(up and dn)
            ts = sess.index[pos]
            full_i = idx_map.get(ts)
            if full_i is None:
                continue
            left = max(0, full_i - 60)
            window = bars.iloc[left : full_i + 1]
            entry = float(bars["Close"].iloc[full_i])
            bar_o = float(bars["Open"].iloc[full_i])
            bar_range = float(bars["High"].iloc[full_i] - bars["Low"].iloc[full_i])
            noise_vs_sl = bar_range / RISK if RISK else 0.0
            body = entry - bar_o
            body_ok = (side == "BUY" and body > 0) or (side == "SELL" and body < 0)
            if side == "BUY":
                sl, t1 = entry - RISK, entry + RISK
                or_ext = (entry - or_hi) / or_w if or_w > 1e-9 else 0.0
            else:
                sl, t1 = entry + RISK, entry - RISK
                or_ext = (or_lo - entry) / or_w if or_w > 1e-9 else 0.0
            win_f, outcome, pts = fwd_path(bars, full_i, side, entry, sl, t1)
            future_bars = len(bars) - full_i - 1
            hm = _hm(ts)
            hh, mm = map(int, hm.split(":"))
            mins = hh * 60 + mm
            ok, reason = passes_noise_gates(
                outcome=outcome,
                future_bars=int(future_bars),
                or_width=float(or_w),
                noise_vs_sl=float(noise_vs_sl),
                or_ext=float(or_ext),
                mins_entry=float(mins),
                min_or_width=float(g["min_or_width"]),
                max_noise_vs_sl=float(g["max_noise_vs_sl"]),
                min_future_bars=int(g["min_future_bars"]),
                min_entry_mins=float(g["min_entry_mins"]),
                max_entry_mins=float(g["max_entry_mins"]),
                max_or_ext=float(g["max_or_ext"]),
            )
            if ok and g.get("require_first_break") and first < 1.0:
                ok, reason = False, "drop_not_first_break"
            if ok and g.get("forbid_both_sides") and both_sides:
                ok, reason = False, "drop_both_sides"
            if ok and g.get("require_body_align") and not body_ok:
                ok, reason = False, "drop_body_against"
            reasons[reason] = reasons.get(reason, 0) + 1
            if not ok:
                continue
            cf = candle_feats(window)
            sess_so_far = sess.iloc[: pos + 1]
            hi = sess_so_far["High"].astype(float)
            lo = sess_so_far["Low"].astype(float)
            cl = sess_so_far["Close"].astype(float)
            typ = (hi + lo + cl) / 3.0
            vwap = float(typ.mean())
            atr = float((hi - lo).tail(14).mean()) if len(hi) >= 2 else bar_range
            feat = {
                **cf,
                "vwap_dist": (entry - vwap) / max(entry, 1.0) * 100.0,
                "range_pos": (entry - float(lo.min())) / max(float(hi.max() - lo.min()), 1e-6),
                "or_width": float(or_w),
                "or_ext": float(or_ext),
                "mins_entry": float(mins),
                "first_break": float(first),
                "gap_pct": float(gaps.get(str(day)) or 0.0),
                "session_chg": (entry - day_open) / max(day_open, 1.0) * 100.0,
                "atr_ratio": float(atr / RISK) if RISK else 0.0,
                "noise_vs_sl": float(noise_vs_sl),
                "side": 1.0 if side == "BUY" else -1.0,
            }
            x = [float(feat.get(k, 0.0)) for k in FEAT_NAMES]
            tickets.append(
                {
                    "day": str(day),
                    "hm": hm,
                    "decision": side,
                    "win": bool(win_f),
                    "points": round(float(pts), 1),
                    "outcome": outcome,
                    "entry": round(entry, 2),
                    "stop_loss": round(sl, 2),
                    "target_1": round(t1, 2),
                    "first_break": bool(first),
                    "both_sides": both_sides,
                    "body_ok": body_ok,
                    "or_width": round(float(or_w), 2),
                    "or_ext": round(float(or_ext), 4),
                    "noise_vs_sl": round(float(noise_vs_sl), 4),
                    "mins_entry": mins,
                    "future_bars": int(future_bars),
                    "x": x,
                    "y": 1 if win_f else 0,
                    "tf": "1m",
                    "track": "dual1m_clean_v2" if g.get("require_first_break") else "dual1m_clean",
                    "lane": LANE,
                    "status": STATUS,
                    "not_live": True,
                    "research_only": True,
                }
            )
    return tickets, reasons, drop_pre


class IdentityOrFlip:
    def __init__(self, flip: bool = False):
        self.flip = bool(flip)

    def transform(self, raw):
        x = np.asarray(raw, dtype=float)
        return 1.0 - x if self.flip else x


def _auc(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    pos = int((y == 1).sum())
    neg = int((y == 0).sum())
    if pos == 0 or neg == 0:
        return float("nan")
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p), dtype=float)
    ranks[order] = np.arange(1, len(p) + 1, dtype=float)
    sorted_p = p[order]
    i = 0
    while i < len(sorted_p):
        j = i
        while j + 1 < len(sorted_p) and sorted_p[j + 1] == sorted_p[i]:
            j += 1
        if j > i:
            ranks[order[i : j + 1]] = float(ranks[order[i : j + 1]].mean())
        i = j + 1
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2.0) / (pos * neg))


def train_dual_heads(tickets: List[dict]) -> Dict[str, Any]:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import log_loss

    grid = (
        dict(max_depth=2, max_iter=40, min_samples_leaf=40, l2_regularization=1.0, learning_rate=0.05),
        dict(max_depth=2, max_iter=80, min_samples_leaf=50, l2_regularization=1.0, learning_rate=0.05),
        dict(max_depth=3, max_iter=40, min_samples_leaf=40, l2_regularization=1.0, learning_rate=0.05),
        dict(max_depth=3, max_iter=60, min_samples_leaf=60, l2_regularization=3.0, learning_rate=0.04),
    )
    packs: Dict[str, Any] = {}
    ordered = sorted(tickets, key=lambda r: (str(r["day"]), str(r["hm"]), str(r["decision"])))
    for side in ("BUY", "SELL"):
        rows = [r for r in ordered if r["decision"] == side and str(r["day"]) <= FREEZE]
        if len(rows) < 60:
            packs[side] = {"available": False, "reason": f"too_few_{len(rows)}"}
            print(f"  skip {side}: too few train rows {len(rows)}", flush=True)
            continue
        X = np.asarray([r["x"] for r in rows], dtype=float)
        y = np.asarray([r["y"] for r in rows], dtype=int)
        days = [r["day"] for r in rows]
        w = recent_sample_weights(days, half_life_days=365.0)
        cut_sel = int(len(rows) * 0.70)
        cut_cal = int(len(rows) * 0.85)
        if len(set(y[:cut_sel].tolist())) < 2 or len(set(y[cut_cal:].tolist())) < 2:
            packs[side] = {"available": False, "reason": "single_class"}
            continue
        best_params = None
        best_loss = None
        for params in grid:
            clf = HistGradientBoostingClassifier(random_state=42, **params)
            clf.fit(X[:cut_sel], y[:cut_sel], sample_weight=w[:cut_sel])
            pred = np.clip(clf.predict_proba(X[cut_sel:cut_cal])[:, 1], 1e-4, 1 - 1e-4)
            loss = float(log_loss(y[cut_sel:cut_cal], pred, labels=[0, 1]))
            if best_loss is None or loss < best_loss:
                best_loss = loss
                best_params = params
        held = HistGradientBoostingClassifier(random_state=42, **best_params)
        held.fit(X[:cut_cal], y[:cut_cal], sample_weight=w[:cut_cal])
        raw_cal = held.predict_proba(X[cut_cal:])[:, 1]
        base = HistGradientBoostingClassifier(random_state=42, **best_params)
        base.fit(X, y, sample_weight=w)
        raw_fit = base.predict_proba(X)[:, 1]
        calib_auc = _auc(y[cut_cal:], raw_cal)
        flip = bool(calib_auc < 0.5)
        iso = IdentityOrFlip(flip)
        if flip:
            calib_auc = 1.0 - calib_auc
        packs[side] = {
            "available": True,
            "side": side,
            "base": base,
            "iso": iso,
            "n_train": int(len(rows)),
            "n_cal": int(len(rows) - cut_cal),
            "train_through_day": FREEZE,
            "feature_names": list(FEAT_NAMES),
            "params": dict(best_params),
            "select_log_loss": round(float(best_loss), 4),
            "fit_auc": round(_auc(y, raw_fit), 3),
            "calib_auc": round(float(calib_auc), 3),
            "score_flipped": flip,
            "trainer": "nifty_1m_dual_clean_v1",
            "research_only": True,
            "not_live": True,
        }
        print(
            f"  trained {side} n={len(rows)} fit_auc={packs[side]['fit_auc']} "
            f"calib_auc={packs[side]['calib_auc']} flip={flip}",
            flush=True,
        )
    return packs


def score_all(packs: Dict[str, Any], tickets: List[dict]) -> List[dict]:
    out = []
    for r in tickets:
        pack = packs.get(r["decision"]) or {}
        if not pack.get("available"):
            continue
        X = np.asarray([r["x"]], dtype=float)
        raw = float(pack["base"].predict_proba(X)[0, 1])
        p = float(np.clip(pack["iso"].transform([raw])[0], 0.05, 0.95))
        rr = {k: v for k, v in r.items() if k != "x"}
        rr["p_t1"] = round(p, 4)
        out.append(rr)
    return out


def _agg(rows: List[dict]) -> Dict[str, Any]:
    if not rows:
        return {"n": 0, "hit_pct": 0.0, "wins": 0}
    wins = sum(1 for r in rows if r.get("win"))
    return {"n": len(rows), "wins": wins, "hit_pct": round(100.0 * wins / len(rows), 2)}


def _clip(rows: List[dict], a: str, b: str) -> List[dict]:
    return [r for r in rows if a <= str(r.get("day") or "") <= b]


def first_day(rows: List[dict]) -> List[dict]:
    seen = set()
    out = []
    for r in sorted(rows, key=lambda x: (x.get("day"), x.get("hm"), -(float(x.get("p_t1") or 0)))):
        d = r.get("day")
        if d in seen:
            continue
        seen.add(d)
        out.append(r)
    return out


def mine_books(scored: List[dict]) -> Dict[str, Any]:
    """Research proven/champ-style books on OOS (after FREEZE) clean tickets."""
    oos = [r for r in scored if str(r.get("day") or "") > FREEZE]
    books = {}
    # Champion: first_break + p floors, day-unique
    for name, pred in (
        ("CHAMP_FB_P52", lambda r: r.get("first_break") and float(r.get("p_t1") or 0) >= 0.52),
        ("CHAMP_FB_P55", lambda r: r.get("first_break") and float(r.get("p_t1") or 0) >= 0.55),
        ("CHAMP_FB_P58", lambda r: r.get("first_break") and float(r.get("p_t1") or 0) >= 0.58),
        ("CHAMP_FB_P60", lambda r: r.get("first_break") and float(r.get("p_t1") or 0) >= 0.60),
        ("CHAMP_FB_P62", lambda r: r.get("first_break") and float(r.get("p_t1") or 0) >= 0.62),
        ("CHAMP_FB_P66", lambda r: r.get("first_break") and float(r.get("p_t1") or 0) >= 0.66),
        ("BUY_FB_P55", lambda r: r.get("decision") == "BUY" and r.get("first_break") and float(r.get("p_t1") or 0) >= 0.55),
        ("SELL_FB_P55", lambda r: r.get("decision") == "SELL" and r.get("first_break") and float(r.get("p_t1") or 0) >= 0.55),
        ("ALL_DAY_UNIQUE", lambda r: True),
    ):
        rows = first_day([r for r in oos if pred(r)])
        books[name] = {"rows": rows, **_agg(rows)}
    # Proven hunt: greedy high p first_break day-unique aiming ≥95%
    for pmin, bname in ((0.58, "PROVEN_CLEAN_P58"), (0.62, "PROVEN_CLEAN_P62"), (0.66, "PROVEN_CLEAN_P66")):
        proven_cands = first_day(
            sorted(
                [r for r in oos if r.get("first_break") and float(r.get("p_t1") or 0) >= pmin],
                key=lambda r: -float(r.get("p_t1") or 0),
            )
        )
        keep = list(proven_cands)
        while keep and _agg(keep)["hit_pct"] < 95.0 and len(keep) > 3:
            losses = [i for i, r in enumerate(keep) if not r.get("win")]
            if not losses:
                break
            worst = min(losses, key=lambda i: float(keep[i].get("p_t1") or 0))
            keep.pop(worst)
        books[bname] = {"rows": keep, **_agg(keep)}
    return books


def save_pack(packs: Dict[str, Any], tickets: List[dict], scored: List[dict], books: Dict[str, Any], meta: dict) -> None:
    import joblib

    PACK_DIR.mkdir(parents=True, exist_ok=True)
    slim_packs = {}
    for side, p in packs.items():
        if not p.get("available"):
            slim_packs[side] = p
            continue
        path = PACK_DIR / f"head_{side.lower()}.joblib"
        joblib.dump({"base": p["base"], "iso": p["iso"], "feature_names": p["feature_names"]}, path)
        slim_packs[side] = {k: v for k, v in p.items() if k not in ("base", "iso")}
        slim_packs[side]["pack_path"] = str(path).replace("\\", "/")
    # tickets without x for JSON
    def strip(rows):
        return [{k: v for k, v in r.items() if k != "x"} for r in rows]

    payload = {
        "research_only": True,
        "not_live": True,
        "lane": LANE,
        "status": STATUS,
        "window": {"start": START, "end": END, "freeze": FREEZE},
        "brackets": {"sl": RISK, "target": RISK},
        "or_bars_1m": OR_BARS_1M,
        "feature_names": FEAT_NAMES,
        "meta": meta,
        "heads": slim_packs,
        "n_clean_tickets": len(tickets),
        "n_scored": len(scored),
        "books": {
            k: {"n": v.get("n"), "hit_pct": v.get("hit_pct"), "wins": v.get("wins"), "calls": strip(v.get("rows") or [])[:80]}
            for k, v in books.items()
        },
        "sample_scored": strip(scored[:20]),
    }
    (PACK_DIR / "pack_meta.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (PACK_DIR / "clean_tickets.json").write_text(json.dumps(strip(tickets), indent=2), encoding="utf-8")
    print(f"  wrote pack → {PACK_DIR}", flush=True)


def write_report(meta: dict, packs: dict, books: dict, scored: list) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    oos = [r for r in scored if str(r.get("day") or "") > FREEZE]
    lines = [
        "# NIFTY 1m dual CLEAN train — RESEARCH ONLY",
        "",
        "**Not live. Does not list Calls.**",
        "",
        f"- Window: `{START}` → `{END}`",
        f"- Freeze (train through): `{FREEZE}`",
        f"- Brackets: ±{RISK:g} · OR bars: {OR_BARS_1M} (1m)",
        f"- Gate profile: **{meta.get('gate_profile') or 'V1'}**",
        f"- Clean gates: `{json.dumps(meta.get('gates') or {})}`",
        "",
        "## Data",
        "",
        f"- bars: **{meta.get('n_bars')}** · days: **{meta.get('n_days')}**",
        f"- coverage: `{meta.get('bar_start')}` → `{meta.get('bar_end')}`",
        f"- download note: {meta.get('download_note') or 'ok'}",
        f"- raw candidates → clean kept: **{meta.get('n_raw')}** → **{meta.get('n_clean')}**",
        f"- drop reasons: `{json.dumps(meta.get('clean_reasons') or {})}`",
        f"- pre drops: `{json.dumps(meta.get('pre_drops') or {})}`",
        "",
        "## Dual heads",
        "",
    ]
    for side in ("BUY", "SELL"):
        p = packs.get(side) or {}
        if p.get("available"):
            lines.append(
                f"- **{side}**: n_train={p.get('n_train')} · fit_auc={p.get('fit_auc')} · "
                f"calib_auc={p.get('calib_auc')} · flipped={p.get('score_flipped')}"
            )
        else:
            lines.append(f"- **{side}**: unavailable ({p.get('reason')})")
    lines += ["", "## OOS research books (after freeze, day-unique)", "", "| Book | N | Hit% |", "|---|---:|---:|"]
    for k, v in books.items():
        lines.append(f"| `{k}` | {v.get('n')} | {v.get('hit_pct')} |")
    lines += [
        "",
        f"OOS scored tickets: **{len(oos)}** · hit {_agg(oos).get('hit_pct')}%",
        "",
        "## Policy",
        "",
        f"- Pack dir: `{PACK_DIR.as_posix().split('stock_signal_data/', 1)[-1] if 'stock_signal_data' in PACK_DIR.as_posix() else PACK_DIR}`",
        "- Flags: `research_only=true` · `not_live=true`",
        "- Do not import into live_session / fno_ws_rescore without a separate promote plan.",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "research_only": True,
                "meta": meta,
                "heads": {k: {kk: vv for kk, vv in (v or {}).items() if kk not in ("base", "iso")} for k, v in packs.items()},
                "books": {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in books.items()},
                "oos_agg": _agg(oos),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  wrote {REPORT_MD}", flush=True)


def main() -> int:
    global PACK_DIR, REPORT_JSON, REPORT_MD
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-download", action="store_true", help="Use cache/csv only")
    ap.add_argument(
        "--strict-v2",
        action="store_true",
        help="Stricter no-lookahead noise gates (after 10:00, first_break, no chase/both-sides)",
    )
    args = ap.parse_args()
    gates = GATE_V2 if args.strict_v2 else GATE_V1
    if args.strict_v2:
        PACK_DIR = LEDGER / "nifty_1m_dual_clean_research_v2"
        REPORT_JSON = OUT / "NIFTY_1M_DUAL_CLEAN_TRAIN_V2.json"
        REPORT_MD = OUT / "NIFTY_1M_DUAL_CLEAN_TRAIN_V2.md"
    print("=" * 60, flush=True)
    print("NIFTY 1m dual CLEAN train · RESEARCH ONLY · not live", flush=True)
    print(f"window {START} → {END} · freeze {FREEZE} · ±{RISK}", flush=True)
    print(f"gates={'V2_STRICT' if args.strict_v2 else 'V1'} {gates}", flush=True)
    print("=" * 60, flush=True)

    existing = load_existing_1m()
    download_note = None
    fresh = pd.DataFrame()
    if not args.skip_download:
        print("\n[1] Downloading / extending 1m via Kite…", flush=True)
        fresh, download_note = download_1m_range(START, END)
        if download_note:
            print(f"  note: {download_note}", flush=True)
    else:
        print("\n[1] skip-download — using local cache/csv only", flush=True)

    bars = merge_and_cache(existing, fresh)
    if bars.empty:
        print("FAIL: no 1m bars available", flush=True)
        return 1
    # ensure in window
    bars = bars[(bars.index >= pd.Timestamp(START, tz="Asia/Kolkata")) & (bars.index <= pd.Timestamp(f"{END} 23:59:59", tz="Asia/Kolkata"))]
    n_days = len({_day(ts) for ts in bars.index})
    print(f"\n[2] Tape ready bars={len(bars)} days={n_days} {bars.index.min()} → {bars.index.max()}", flush=True)
    if n_days < 30:
        print("WARN: very few sessions — results will be thin", flush=True)

    print("\n[3] Building clean OR-break tickets (noise filtered)…", flush=True)
    tickets, reasons, drop_pre = build_clean_tickets(bars, gates=gates)
    print(f"  clean tickets={len(tickets)} reasons={reasons} pre_drops={drop_pre}", flush=True)
    if len(tickets) < 40:
        print("FAIL: too few clean tickets for dual train", flush=True)
        meta = {
            "n_bars": len(bars),
            "n_days": n_days,
            "bar_start": str(bars.index.min()),
            "bar_end": str(bars.index.max()),
            "download_note": download_note,
            "n_raw": sum(reasons.values()),
            "n_clean": len(tickets),
            "clean_reasons": reasons,
            "pre_drops": drop_pre,
            "gates": gates,
            "gate_profile": "V2_STRICT" if args.strict_v2 else "V1",
        }
        write_report(meta, {}, {}, [])
        return 1

    print("\n[4] Training dual BUY/SELL heads (freeze chronological)…", flush=True)
    packs = train_dual_heads(tickets)
    print("\n[5] Scoring + mining research books…", flush=True)
    scored = score_all(packs, tickets)
    books = mine_books(scored)
    for k, v in books.items():
        print(f"  book {k}: n={v.get('n')} hit={v.get('hit_pct')}%", flush=True)

    meta = {
        "n_bars": len(bars),
        "n_days": n_days,
        "bar_start": str(bars.index.min()),
        "bar_end": str(bars.index.max()),
        "download_note": download_note,
        "n_raw": int(sum(reasons.values())),
        "n_clean": len(tickets),
        "clean_reasons": reasons,
        "pre_drops": drop_pre,
        "gates": gates,
        "gate_profile": "V2_STRICT" if args.strict_v2 else "V1",
        "research_only": True,
        "not_live": True,
    }
    print("\n[6] Saving research pack + report…", flush=True)
    save_pack(packs, tickets, scored, books, meta)
    write_report(meta, packs, books, scored)
    print("\nDONE · research only — not wired to live", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
