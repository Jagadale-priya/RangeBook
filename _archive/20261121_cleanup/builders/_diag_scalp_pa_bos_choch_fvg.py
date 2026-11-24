"""RESEARCH ONLY — Price-action BOS / CHoCH / FVG framework (transcript model).

Verified definitions (Google / ICT / SMC sources, Nov 2026):
  BOS   = body close beyond last swing WITH the trend (continuation)
  CHoCH = first body close beyond last swing AGAINST the trend (flip warning)
  FVG   = 3-candle wick imbalance: bullish if low[3]>high[1]; bearish if high[3]<low[1]
          mid = Consequent Encroachment (CE); SL beyond mid candle extreme
  Break+retest = polarity flip after close beyond level, then return/test

Transcript model mapped to NIFTY:
  HTF = 15m structure (direction + BOS/CHoCH)
  LTF = 1m entry: session open → structure → FVG → pullback to mid-gap
  Risk = beyond FVG middle candle; target = 3R and 4R
  NY open → NSE cash open window 09:15–10:00 IST

Books tested:
  A) transcript_choch_fvg   — CHoCH then FVG mid (literal transcript)
  B) ict_choch_bos_fvg      — CHoCH + confirming BOS then FVG (ICT-strict)
  C) bos_continuation_fvg   — BOS with HTF bias then FVG ("trend is friend")
  D) choch_break_retest     — CHoCH level break+retest entry (invalidation key)

  python -u prod_live/tests/builders/_diag_scalp_pa_bos_choch_fvg.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_PA_BOS_CHOCH_FVG.md"
REPORT_JSON = OUT / "NIFTY_1M_PA_BOS_CHOCH_FVG.json"

SWING_L = 2
SESSION_OPEN_LO, SESSION_OPEN_HI = 9 * 60 + 15, 10 * 60
TRADE_LO, TRADE_HI = 9 * 60 + 20, 14 * 60 + 30
RR_LIST = (3.0, 4.0)
MAX_HOLD_1M = 90
N_SESSIONS = 44  # ~2 months for stronger sample
LOOKBACK_CAL_DAYS = 100


def _norm_1m(raw: pd.DataFrame) -> pd.DataFrame:
    work = raw.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index)
    if work.index.tz is None:
        work.index = work.index.tz_localize("Asia/Kolkata")
    else:
        work.index = work.index.tz_convert("Asia/Kolkata")
    rename = {c: str(c).title() for c in work.columns}
    work = work.rename(columns=rename)
    for a in ("Open", "High", "Low", "Close", "Volume"):
        if a not in work.columns:
            for c in list(work.columns):
                if str(c).lower() == a.lower():
                    work = work.rename(columns={c: a})
    keep = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in work.columns]
    work = work[keep].sort_index()
    work = work[~work.index.duplicated(keep="last")]
    hm = work.index.strftime("%H:%M")
    return work[(hm >= "09:15") & (hm <= "15:29")]


def to_15m(df1: pd.DataFrame) -> pd.DataFrame:
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in df1.columns:
        agg["Volume"] = "sum"
    out = df1.resample("15min", label="left", closed="left").agg(agg).dropna(subset=["Open", "Close"])
    hm = out.index.strftime("%H:%M")
    return out[(hm >= "09:15") & (hm <= "15:15")]


def swing_points(h, l, L=SWING_L) -> Tuple[List[int], List[int]]:
    sh, sl = [], []
    n = len(h)
    for i in range(L, n - L):
        if h[i] == np.max(h[i - L : i + L + 1]) and h[i] > np.max(h[i - L : i]):
            sh.append(i)
        if l[i] == np.min(l[i - L : i + L + 1]) and l[i] < np.min(l[i - L : i]):
            sl.append(i)
    return sh, sl


def detect_fvg(o, h, l, c) -> List[dict]:
    """Strict wick FVG at mid candle i; confirmed at i+1."""
    out = []
    n = len(c)
    for i in range(1, n - 1):
        if l[i + 1] > h[i - 1]:
            bot, top = float(h[i - 1]), float(l[i + 1])
            if top > bot:
                out.append(
                    {
                        "side": "BUY",
                        "i_mid": i,
                        "i_confirm": i + 1,
                        "bot": bot,
                        "top": top,
                        "mid": (bot + top) / 2.0,
                        "size": top - bot,
                    }
                )
        if h[i + 1] < l[i - 1]:
            top, bot = float(l[i - 1]), float(h[i + 1])
            if top > bot:
                out.append(
                    {
                        "side": "SELL",
                        "i_mid": i,
                        "i_confirm": i + 1,
                        "bot": bot,
                        "top": top,
                        "mid": (bot + top) / 2.0,
                        "size": top - bot,
                    }
                )
    return out


def structure_events(df: pd.DataFrame) -> List[dict]:
    """Walk forward BOS / CHoCH on body close beyond confirmed swings."""
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    idx = df.index
    sh_idx, sl_idx = swing_points(h, l)
    sh_set, sl_set = set(sh_idx), set(sl_idx)

    bias = None
    last_sh = None
    last_sl = None
    events = []
    confirmed_swings_h: List[Tuple[int, float]] = []
    confirmed_swings_l: List[Tuple[int, float]] = []
    bos_armed = True  # after BOS wait for new opposite swing before next BOS spam

    for i in range(len(c)):
        if i - SWING_L in sh_set:
            confirmed_swings_h.append((i - SWING_L, float(h[i - SWING_L])))
            last_sh = confirmed_swings_h[-1]
            if bias == "down":
                bos_armed = True
        if i - SWING_L in sl_set:
            confirmed_swings_l.append((i - SWING_L, float(l[i - SWING_L])))
            last_sl = confirmed_swings_l[-1]
            if bias == "up":
                bos_armed = True

        if last_sh is None or last_sl is None:
            continue

        if bias is None and len(confirmed_swings_h) >= 2 and len(confirmed_swings_l) >= 2:
            if (
                confirmed_swings_h[-1][1] > confirmed_swings_h[-2][1]
                and confirmed_swings_l[-1][1] > confirmed_swings_l[-2][1]
            ):
                bias = "up"
                bos_armed = True
            elif (
                confirmed_swings_h[-1][1] < confirmed_swings_h[-2][1]
                and confirmed_swings_l[-1][1] < confirmed_swings_l[-2][1]
            ):
                bias = "down"
                bos_armed = True

        if bias is None:
            continue

        px = float(c[i])
        if bias == "up":
            if bos_armed and px > last_sh[1]:
                events.append(
                    {
                        "kind": "BOS",
                        "side": "BUY",
                        "i": i,
                        "level": last_sh[1],
                        "bias": bias,
                        "time": idx[i],
                    }
                )
                last_sh = (i, float(h[i]))
                bos_armed = False
            elif px < last_sl[1]:
                events.append(
                    {
                        "kind": "CHOCH",
                        "side": "SELL",
                        "i": i,
                        "level": last_sl[1],
                        "bias": bias,
                        "time": idx[i],
                    }
                )
                bias = "down"
                last_sh = (i, float(h[i]))
                bos_armed = True
        else:
            if bos_armed and px < last_sl[1]:
                events.append(
                    {
                        "kind": "BOS",
                        "side": "SELL",
                        "i": i,
                        "level": last_sl[1],
                        "bias": bias,
                        "time": idx[i],
                    }
                )
                last_sl = (i, float(l[i]))
                bos_armed = False
            elif px > last_sh[1]:
                events.append(
                    {
                        "kind": "CHOCH",
                        "side": "BUY",
                        "i": i,
                        "level": last_sh[1],
                        "bias": bias,
                        "time": idx[i],
                    }
                )
                bias = "up"
                last_sl = (i, float(l[i]))
                bos_armed = True

    return events


def path_rr(h, l, c, i_entry, side, entry, sl, rr: float, max_bars=MAX_HOLD_1M) -> Tuple[bool, str, float, int]:
    risk = abs(entry - sl)
    if risk < 1e-6:
        return False, "bad_risk", 0.0, i_entry
    if side == "BUY":
        tp = entry + rr * risk
        for j in range(i_entry + 1, min(len(c), i_entry + max_bars + 1)):
            if float(l[j]) <= sl:
                return False, "sl", float(sl - entry), j
            if float(h[j]) >= tp:
                return True, "tp", float(rr * risk), j
        j_end = min(len(c) - 1, i_entry + max_bars)
        return False, "exp", float(c[j_end] - entry), j_end
    tp = entry - rr * risk
    for j in range(i_entry + 1, min(len(c), i_entry + max_bars + 1)):
        if float(h[j]) >= sl:
            return False, "sl", float(entry - sl), j
        if float(l[j]) <= tp:
            return True, "tp", float(rr * risk), j
    j_end = min(len(c) - 1, i_entry + max_bars)
    return False, "exp", float(entry - c[j_end]), j_end


def build_htf_bias(df15: pd.DataFrame, struct15: List[dict]) -> Dict[Any, str]:
    bias_at_15: Dict[Any, str] = {}
    cur = None
    ev_by_i = {e["i"]: e for e in struct15}
    for i15 in range(len(df15)):
        if i15 in ev_by_i:
            e = ev_by_i[i15]
            cur = "up" if e["side"] == "BUY" else "down"
        if cur:
            bias_at_15[df15.index[i15]] = cur
    return bias_at_15


def htf_bias_lookup(bias_at_15: Dict[Any, str], ts) -> Optional[str]:
    t = pd.Timestamp(ts).floor("15min")
    for _ in range(24):
        if t in bias_at_15:
            return bias_at_15[t]
        t = t - pd.Timedelta(minutes=15)
    return None


def _fvg_entry_after(
    fvgs: List[dict],
    h,
    l,
    c,
    idx,
    day,
    d: str,
    side: str,
    i_start: int,
    max_fvg_wait: int = 30,
    max_pull_wait: int = 45,
    min_fvg: float = 1.5,
) -> Optional[Tuple[int, float, float, dict]]:
    fvg = None
    for f in fvgs:
        if f["i_confirm"] <= i_start:
            continue
        if f["side"] != side:
            continue
        if f["i_confirm"] > i_start + max_fvg_wait:
            break
        if f["size"] < min_fvg:
            continue
        fvg = f
        break
    if fvg is None:
        return None

    for j in range(fvg["i_confirm"] + 1, min(len(c), fvg["i_confirm"] + max_pull_wait)):
        if day[j] != d:
            break
        if float(l[j]) <= fvg["mid"] <= float(h[j]):
            if side == "BUY":
                sl = float(l[fvg["i_mid"]]) - 0.5
            else:
                sl = float(h[fvg["i_mid"]]) + 0.5
            entry_px = float(fvg["mid"])
            risk = abs(entry_px - sl)
            if risk < 2.0 or risk > 80.0:
                return None
            return j, entry_px, sl, fvg
    return None


def _score_trade(h, l, c, entry_i, side, entry_px, sl, extra: dict) -> dict:
    row = {
        **extra,
        "hm": extra.get("idx")[entry_i].strftime("%H:%M") if "idx" in extra else None,
        "side": side,
        "entry": round(entry_px, 2),
        "sl": round(sl, 2),
        "risk": round(abs(entry_px - sl), 2),
        "full_i": entry_i,
    }
    if "idx" in row:
        del row["idx"]
    for rr in RR_LIST:
        ok, reason, pts, _j = path_rr(h, l, c, entry_i, side, entry_px, sl, rr)
        risk = abs(entry_px - sl)
        row[f"w{int(rr)}r"] = bool(ok)
        row[f"r{int(rr)}r"] = reason
        row[f"pts{int(rr)}r"] = round(float(pts if ok else -risk), 2)
        row[f"exp{int(rr)}r"] = round((1.0 if ok else -1.0) * (rr if ok else 1.0), 2)
    return row


def simulate_book(
    mode: str,
    df1: pd.DataFrame,
    bias_at_15: Dict[Any, str],
    struct1: List[dict],
    fvgs: List[dict],
    one_per_day: bool = True,
) -> List[dict]:
    h = df1["High"].astype(float).values
    l = df1["Low"].astype(float).values
    c = df1["Close"].astype(float).values
    idx = df1.index
    day = np.array([str(ts.date()) for ts in idx])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in idx])

    choch1 = [e for e in struct1 if e["kind"] == "CHOCH"]
    bos1 = [e for e in struct1 if e["kind"] == "BOS"]
    trades: List[dict] = []
    used_days = set()

    def take(day_s: str) -> bool:
        if not one_per_day:
            return True
        if day_s in used_days:
            return False
        used_days.add(day_s)
        return True

    if mode in ("transcript_choch_fvg", "ict_choch_bos_fvg"):
        for ch in choch1:
            i_ch = int(ch["i"])
            if not (TRADE_LO <= mins[i_ch] <= TRADE_HI):
                continue
            if mins[i_ch] < SESSION_OPEN_LO:
                continue
            d = day[i_ch]
            side = ch["side"]
            hb = htf_bias_lookup(bias_at_15, idx[i_ch])
            aligned = (hb == "up" and side == "BUY") or (hb == "down" and side == "SELL")

            i_trig = i_ch
            confirm_bos = None
            if mode == "ict_choch_bos_fvg":
                # ICT: CHoCH is warning; wait confirming BOS in new direction
                confirm_bos = None
                for b in bos1:
                    if b["i"] <= i_ch:
                        continue
                    if b["side"] != side:
                        continue
                    if b["i"] > i_ch + 40:
                        break
                    confirm_bos = b
                    break
                if confirm_bos is None:
                    continue
                i_trig = int(confirm_bos["i"])

            got = _fvg_entry_after(fvgs, h, l, c, idx, day, d, side, i_trig)
            if got is None:
                continue
            entry_i, entry_px, sl, fvg = got
            if not take(d):
                continue
            trades.append(
                _score_trade(
                    h,
                    l,
                    c,
                    entry_i,
                    side,
                    entry_px,
                    sl,
                    {
                        "book": mode,
                        "day": d,
                        "idx": idx,
                        "trig_hm": idx[i_trig].strftime("%H:%M"),
                        "choch_hm": idx[i_ch].strftime("%H:%M"),
                        "htf_bias": hb,
                        "htf_aligned": bool(aligned and hb is not None),
                        "fvg_size": round(fvg["size"], 2),
                    },
                )
            )

    elif mode == "bos_continuation_fvg":
        for b in bos1:
            i_b = int(b["i"])
            if not (TRADE_LO <= mins[i_b] <= TRADE_HI):
                continue
            if mins[i_b] < SESSION_OPEN_LO:
                continue
            d = day[i_b]
            side = b["side"]
            hb = htf_bias_lookup(bias_at_15, idx[i_b])
            # Require HTF alignment for continuation book
            if hb is None:
                continue
            if not ((hb == "up" and side == "BUY") or (hb == "down" and side == "SELL")):
                continue
            got = _fvg_entry_after(fvgs, h, l, c, idx, day, d, side, i_b)
            if got is None:
                continue
            entry_i, entry_px, sl, fvg = got
            if not take(d):
                continue
            trades.append(
                _score_trade(
                    h,
                    l,
                    c,
                    entry_i,
                    side,
                    entry_px,
                    sl,
                    {
                        "book": mode,
                        "day": d,
                        "idx": idx,
                        "trig_hm": idx[i_b].strftime("%H:%M"),
                        "choch_hm": None,
                        "htf_bias": hb,
                        "htf_aligned": True,
                        "fvg_size": round(fvg["size"], 2),
                    },
                )
            )

    elif mode == "choch_break_retest":
        for ch in choch1:
            i_ch = int(ch["i"])
            if not (TRADE_LO <= mins[i_ch] <= TRADE_HI):
                continue
            if mins[i_ch] < SESSION_OPEN_LO:
                continue
            d = day[i_ch]
            side = ch["side"]
            level = float(ch["level"])
            hb = htf_bias_lookup(bias_at_15, idx[i_ch])
            aligned = (hb == "up" and side == "BUY") or (hb == "down" and side == "SELL")

            # After CHoCH close beyond level: wait for retest of opposite side, enter on touch
            entry_i = None
            entry_px = None
            sl = None
            away = False
            for j in range(i_ch + 1, min(len(c), i_ch + 60)):
                if day[j] != d:
                    break
                if side == "SELL":
                    # broke below HL → level should act as resistance
                    if float(h[j]) < level - 2.0:
                        away = True
                    if away and float(h[j]) >= level:
                        entry_i = j
                        entry_px = level
                        sl = float(h[j]) + max(3.0, abs(float(h[j]) - level) + 1.0)
                        # better SL: above retest wick
                        sl = float(h[j]) + 0.5
                        break
                else:
                    if float(l[j]) > level + 2.0:
                        away = True
                    if away and float(l[j]) <= level:
                        entry_i = j
                        entry_px = level
                        sl = float(l[j]) - 0.5
                        break
            if entry_i is None or entry_px is None or sl is None:
                continue
            risk = abs(entry_px - sl)
            if risk < 2.0 or risk > 80.0:
                continue
            if not take(d):
                continue
            trades.append(
                _score_trade(
                    h,
                    l,
                    c,
                    entry_i,
                    side,
                    entry_px,
                    sl,
                    {
                        "book": mode,
                        "day": d,
                        "idx": idx,
                        "trig_hm": idx[i_ch].strftime("%H:%M"),
                        "choch_hm": idx[i_ch].strftime("%H:%M"),
                        "htf_bias": hb,
                        "htf_aligned": bool(aligned and hb is not None),
                        "fvg_size": None,
                    },
                )
            )

    return trades


def summarize(trades: List[dict], key: str, n_days: int) -> Dict[str, Any]:
    if not trades:
        return {"n": 0, "hit": None, "cpd": 0.0, "avg_pts": None, "exp_R": None}
    pk = "pts3r" if "3" in key else "pts4r"
    ek = "exp3r" if "3" in key else "exp4r"
    w = sum(1 for t in trades if t.get(key))
    pts = [float(t.get(pk) or 0) for t in trades]
    exp = [float(t.get(ek) or 0) for t in trades]
    return {
        "n": len(trades),
        "hit": round(100.0 * w / len(trades), 2),
        "cpd": round(len(trades) / n_days, 2) if n_days else 0.0,
        "avg_pts": round(float(np.mean(pts)), 2),
        "exp_R": round(float(np.mean(exp)), 3),
        "wins": w,
        "losses": len(trades) - w,
    }


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("PA BOS/CHoCH/FVG research (RESEARCH ONLY)", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL_DAYS)]
    df1 = _norm_1m(raw)
    days_all = sorted({str(ts.date()) for ts in df1.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    day_lo, day_hi = min(keep), max(keep)
    n_days = len(keep)
    df1 = df1[[str(ts.date()) in keep for ts in df1.index]]
    df15 = to_15m(df1)
    print(f"window {day_lo}→{day_hi} n_days={n_days} 1m={len(df1)} 15m={len(df15)}", flush=True)

    struct15 = structure_events(df15)
    n_bos15 = sum(1 for e in struct15 if e["kind"] == "BOS")
    n_choch15 = sum(1 for e in struct15 if e["kind"] == "CHOCH")
    bias_at_15 = build_htf_bias(df15, struct15)
    print(f"15m structure: BOS={n_bos15} CHOCH={n_choch15}", flush=True)

    o = df1["Open"].astype(float).values
    h = df1["High"].astype(float).values
    l = df1["Low"].astype(float).values
    c = df1["Close"].astype(float).values
    fvgs = detect_fvg(o, h, l, c)
    struct1 = structure_events(df1)
    n_bos1 = sum(1 for e in struct1 if e["kind"] == "BOS")
    n_choch1 = sum(1 for e in struct1 if e["kind"] == "CHOCH")
    print(f"1m structure: BOS={n_bos1} CHOCH={n_choch1} FVG={len(fvgs)}", flush=True)

    modes = [
        "transcript_choch_fvg",
        "ict_choch_bos_fvg",
        "bos_continuation_fvg",
        "choch_break_retest",
    ]
    books: Dict[str, Any] = {}
    all_trades: Dict[str, List[dict]] = {}

    for mode in modes:
        tr = simulate_book(mode, df1, bias_at_15, struct1, fvgs, one_per_day=True)
        tr_al = [t for t in tr if t.get("htf_aligned")]
        all_trades[mode] = tr
        books[mode] = {
            "all_3R": summarize(tr, "w3r", n_days),
            "all_4R": summarize(tr, "w4r", n_days),
            "htf_aligned_3R": summarize(tr_al, "w3r", n_days),
            "htf_aligned_4R": summarize(tr_al, "w4r", n_days),
        }
        a3 = books[mode]["htf_aligned_3R"]
        print(
            f"  {mode}: n={len(tr)} aligned={len(tr_al)} "
            f"3R hit={books[mode]['all_3R']['hit']}% "
            f"aligned3R={a3['hit']}% expR={a3['exp_R']}",
            flush=True,
        )

    # Pick best by HTF-aligned 3R expectancy (min n=8)
    best_name, best_exp, best_hit, best_n = None, -999.0, None, 0
    for mode, b in books.items():
        s = b["htf_aligned_3R"]
        if s["n"] >= 8 and s["exp_R"] is not None and s["exp_R"] > best_exp:
            best_name, best_exp, best_hit, best_n = mode, s["exp_R"], s["hit"], s["n"]

    # Oracle clean reference (from prior report — hindsight path-wins, not apples-to-apples)
    oracle_ref = {
        "note": "Oracle T15 clean is hindsight path-win ∩ TierAB — not a live PA model",
        "oracle_gap15_n": 314,
        "clean_tierAB_n": 35,
        "clean_cut_pct": 88.85,
        "comparison": "PA books are live-causal; Oracle clean is ceiling after filters",
    }

    payload = {
        "ok": True,
        "research_only": True,
        "window": {"day_lo": day_lo, "day_hi": day_hi, "n_days": n_days},
        "definitions": {
            "BOS": "Body close beyond last swing WITH trend (continuation). Wick-only = liquidity sweep, not BOS.",
            "CHOCH": "First body close beyond last swing AGAINST trend (potential flip warning).",
            "FVG": "3-candle wick gap: bullish if low3>high1; bearish if high3<low1. Mid = CE.",
            "break_retest": "Close beyond level → polarity flip → pullback test → continue.",
            "entry_transcript": "1m CHOCH → FVG mid pullback; SL beyond FVG mid candle; TP 3–4R",
            "session": "NSE 09:15–10:00 IST (NY-open analogue)",
            "sources": [
                "https://www.ictkillzone.com/ict-bos",
                "https://www.ictkillzone.com/ict-choch",
                "https://velotrade.com/blog/break-of-structure",
                "https://ictradingconcepts.com/ict/fair-value-gap/",
                "https://grandalgo.com/blog/ict-bos-vs-choch-explained",
                "https://therighttrader.com/learn/trend-analysis/breakout-retest",
            ],
        },
        "htf_15m": {"bos": n_bos15, "choch": n_choch15},
        "ltf_1m": {"bos": n_bos1, "choch": n_choch1, "fvg": len(fvgs)},
        "books": books,
        "best_htf_aligned_3R": {
            "mode": best_name,
            "hit": best_hit,
            "exp_R": best_exp,
            "n": best_n,
        },
        "oracle_clean_ref": oracle_ref,
        "trades_sample": {
            m: (all_trades[m][:20]) for m in modes
        },
        "took_sec": round(time.time() - t0, 1),
    }

    lines = [
        "# NIFTY — Price Action **BOS / CHoCH / FVG** (transcript model)",
        "",
        "> **RESEARCH ONLY — not live Scalper yet.**",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days} sessions).",
        "",
        "## 0) Accurate definitions (Google / ICT cross-checked)",
        "",
        "| Term | Accurate definition | Key rule |",
        "|---|---|---|",
        "| **BOS** | Body **close** beyond last swing **with** the trend | Continuation. Wick-only = liquidity sweep, **not** BOS ([ICT BOS](https://www.ictkillzone.com/ict-bos), [Velotrade](https://velotrade.com/blog/break-of-structure)) |",
        "| **CHoCH** | First body close beyond last swing **against** the trend | Flip *warning*, not a guaranteed reversal ([ICT CHoCH](https://www.ictkillzone.com/ict-choch)) |",
        "| **FVG** | 3 candles; bullish if `low[3] > high[1]`; bearish if `high[3] < low[1]` | Wick-to-wick gap; mid = CE; body close beyond far edge invalidates ([IC Trading](https://ictradingconcepts.com/ict/fair-value-gap/)) |",
        "| **Break+retest** | Close beyond level → polarity flip → return/test → continue | Enter on retest reaction; stop beyond retest extreme ([Right Trader](https://therighttrader.com/learn/trend-analysis/breakout-retest)) |",
        "| **HTF / LTF** | 15m = map · 1m = turn-by-turn entry | Exact transcript framing |",
        "| **Session open** | NSE **09:15–10:00** IST | Analogue of transcript NY open volume window |",
        "",
        "**Transcript core (3 keys):** Direction (HH/HL or LH/LL + BOS + trendline) → Confirmation (response / FVG, not knife-catch) → Invalidation (break+retest + CHoCH).",
        "",
        "Simple ≠ risk-free. We measure **repeatable R-multiple hit rate** and **expectancy in R**.",
        "",
        f"## 1) Structure density ({n_days}d)",
        "",
        f"- 15m: BOS **{n_bos15}** · CHoCH **{n_choch15}**",
        f"- 1m: BOS **{n_bos1}** · CHoCH **{n_choch1}** · FVG **{len(fvgs)}**",
        "",
        "## 2) Entry books (1/day, TP 3R / 4R, hold ≤90m)",
        "",
        "| Book | What it encodes | n | 3R Hit% | exp R | HTF-al n | HTF-al 3R% | HTF-al expR |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    labels = {
        "transcript_choch_fvg": "A · Transcript CHoCH→FVG mid",
        "ict_choch_bos_fvg": "B · ICT CHoCH+BOS→FVG",
        "bos_continuation_fvg": "C · BOS continuation→FVG (trend friend)",
        "choch_break_retest": "D · CHoCH break+retest",
    }
    for mode in modes:
        b = books[mode]
        a, al = b["all_3R"], b["htf_aligned_3R"]
        lines.append(
            f"| {labels[mode]} | — | {a['n']} | {a['hit']} | {a['exp_R']} | "
            f"{al['n']} | {al['hit']} | {al['exp_R']} |"
        )

    lines += [
        "",
        f"**Best HTF-aligned 3R (n≥8):** `{best_name}` · hit **{best_hit}%** · exp **{best_exp}R** · n={best_n}",
        "",
        "### Expectancy note",
        "",
        "At 3R, breakeven hit ≈ **25%**. Above that → positive expectancy if costs ≈0.",
        "At 4R, breakeven hit ≈ **20%**.",
        "",
        "## 3) Sample trades — best book (HTF-aligned preferred)",
        "",
        "| Day | HM | Side | Entry | SL | Risk | 3R | 4R | HTF | Book |",
        "|---|---|---|---:|---:|---:|---|---|---|---|",
    ]

    sample_mode = best_name or "transcript_choch_fvg"
    sample = [t for t in all_trades[sample_mode] if t.get("htf_aligned")] or all_trades[sample_mode]
    for t in sample[:25]:
        lines.append(
            f"| {t['day']} | {t['hm']} | {t['side']} | {t['entry']} | {t['sl']} | {t['risk']} | "
            f"{'WIN' if t.get('w3r') else t.get('r3r')} | {'WIN' if t.get('w4r') else t.get('r4r')} | "
            f"{t.get('htf_bias')} | {t.get('book')} |"
        )

    # Also show transcript book samples
    lines += [
        "",
        "### Transcript book A samples",
        "",
        "| Day | HM | Side | Entry | SL | 3R | HTF |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for t in all_trades["transcript_choch_fvg"][:15]:
        lines.append(
            f"| {t['day']} | {t['hm']} | {t['side']} | {t['entry']} | {t['sl']} | "
            f"{'WIN' if t.get('w3r') else t.get('r3r')} | {t.get('htf_bias')} |"
        )

    lines += [
        "",
        "## 4) vs Oracle T15 clean (not apples-to-apples)",
        "",
        "| Model | Nature | Density | Accuracy framing |",
        "|---|---|---|---|",
        "| **Oracle T15 ∩ TierAB clean** | Hindsight path-wins then filter | ~1.6 cpd (35/22d prior) | High by construction on T15 path |",
        "| **PA BOS/CHoCH/FVG** | Live-causal structure + imbalance | ~0.3–1.0 cpd | True out-of-sample path R-hit |",
        "",
        "- Oracle clean answers: *among textbook T15 winners, which filters keep quality?*",
        "- PA answers: *can we enter from structure alone without path-win peek?*",
        "- Misses on major `run2/run3` often look like **displacement + FVG** — this PA book targets that language.",
        "- If a PA book holds **>35% @ 3R with HTF align**, it is expectancy-positive and worth a Scalper research mode `pa_fvg_1m`.",
        "",
        "## 5) Practical reading (what the transcript got right)",
        "",
        "1. **Strip indicators** — BOS/CHoCH/FVG are pure OHLC structure.",
        "2. **Direction first** — zoom out (15m) before 1m entries.",
        "3. **Confirm, don't predict** — FVG pullback / retest > knife-catch at a line.",
        "4. **Invalidation** — CHoCH + break/retest is the flip language; ICT adds: wait for confirming BOS after CHoCH.",
        "5. **Simple ≠ easy** — losses are opportunity cost; size for the model, not for zero losses.",
        "6. **NSE adaptation** — use 09:15–10:00 IST, not NY open.",
        "",
        f"_Generated in {payload['took_sec']}s._",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    print(f"BEST={best_name} hit={best_hit}% expR={best_exp} n={best_n}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
