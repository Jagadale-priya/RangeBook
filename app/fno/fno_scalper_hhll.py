"""HH/HL/LH/LL structure entry for Scalper (SHIP-validated on 500d).

Gate (live + chart calls) — either SHIP recipe:
  A) HTF + ATR≥14 + Desk≥3 + streak≥4  (~79% T15, rarer)
  B) HTF + held + ATR≥12 + streak≥4     (~73% T15, more calls)

  HL confirm (BUY) / LH confirm (SELL) while 1m bias matches.

Exit geometry: EMA34 trail · T15 (same as Oracle).

Research: NIFTY_1M_HHLL_LARGE_STABILIZE.md (500d multi-fold SHIP).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

L = 3
T15 = 15.0
ATR_STRICT = 14.0
ATR_HELD = 12.0
STREAK_MIN = 4
MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30


def _ensure_desk_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    c = out["Close"].astype(float)
    if "ema9" not in out.columns:
        out["ema9"] = c.ewm(span=9, adjust=False).mean()
    if "ema20" not in out.columns:
        out["ema20"] = c.ewm(span=20, adjust=False).mean()
    if "ema50" not in out.columns:
        out["ema50"] = c.ewm(span=50, adjust=False).mean()
    if "ema34" not in out.columns:
        out["ema34"] = c.ewm(span=34, adjust=False).mean()
    if "atr14" not in out.columns:
        prev = c.shift(1)
        tr = pd.concat(
            [
                (out["High"].astype(float) - out["Low"].astype(float)),
                (out["High"].astype(float) - prev).abs(),
                (out["Low"].astype(float) - prev).abs(),
            ],
            axis=1,
        ).max(axis=1)
        out["atr14"] = tr.rolling(14, min_periods=14).mean()
    if "plus_di" not in out.columns or "minus_di" not in out.columns:
        up = out["High"].astype(float).diff()
        dn = -out["Low"].astype(float).diff()
        plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
        minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
        tr = pd.concat(
            [
                (out["High"].astype(float) - out["Low"].astype(float)),
                (out["High"].astype(float) - c.shift(1)).abs(),
                (out["Low"].astype(float) - c.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        tr_s = tr.rolling(14, min_periods=14).sum().replace(0, np.nan)
        out["plus_di"] = 100 * pd.Series(plus_dm, index=out.index).rolling(14, min_periods=14).sum() / tr_s
        out["minus_di"] = 100 * pd.Series(minus_dm, index=out.index).rolling(14, min_periods=14).sum() / tr_s
    if "vwap" not in out.columns:
        day = pd.Series([str(ts.date()) for ts in out.index], index=out.index)
        typ = (out["High"].astype(float) + out["Low"].astype(float) + c) / 3.0
        vol = out["Volume"].astype(float) if "Volume" in out.columns else pd.Series(1.0, index=out.index)
        if float(vol.sum() or 0) <= 0:
            vol = pd.Series(1.0, index=out.index)
        out["vwap"] = (typ * vol).groupby(day).cumsum() / vol.groupby(day).cumsum().replace(0, np.nan)
    return out


def _htf_bias_series(df: pd.DataFrame) -> Dict[Any, str]:
    """15m structure bias lookup; fallback = 15m close vs EMA34."""
    try:
        from _diag_scalp_pa_bos_choch_fvg import (  # type: ignore
            to_15m,
            structure_events,
            build_htf_bias,
        )

        df15 = to_15m(df)
        return build_htf_bias(df15, structure_events(df15))
    except Exception:
        pass
    # fallback
    rule = "15min"
    ohlc = df[["Open", "High", "Low", "Close"]].astype(float)
    df15 = ohlc.resample(rule, label="left", closed="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    ).dropna()
    ema = df15["Close"].ewm(span=34, adjust=False).mean()
    out: Dict[Any, str] = {}
    for ts, row in df15.iterrows():
        e = float(ema.loc[ts]) if ts in ema.index else float("nan")
        if not np.isfinite(e):
            continue
        out[ts] = "up" if float(row["Close"]) >= e else "down"
    return out


def _htf_at(bias_map: Dict[Any, str], ts) -> Optional[str]:
    if not bias_map:
        return None
    try:
        from _diag_scalp_pa_bos_choch_fvg import htf_bias_lookup  # type: ignore

        return htf_bias_lookup(bias_map, ts)
    except Exception:
        pass
    # nearest prior key
    keys = sorted(bias_map.keys())
    hit = None
    for k in keys:
        if k <= ts:
            hit = k
        else:
            break
    return bias_map.get(hit) if hit is not None else None


def detect_hhll_entries(df: pd.DataFrame) -> List[dict]:
    """Return causal HL/LH confirm candidates with gate flags (not yet path-scored)."""
    df = _ensure_desk_cols(df)
    bias_map = _htf_bias_series(df)

    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    atr = df["atr14"].astype(float).values
    vwap = df["vwap"].astype(float).values
    ema9 = df["ema9"].astype(float).values
    ema20 = df["ema20"].astype(float).values
    ema50 = df["ema50"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    pdi = df["plus_di"].astype(float).values
    mdi = df["minus_di"].astype(float).values
    day = np.array([str(ts.date()) for ts in df.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df.index])
    idx = df.index
    n = len(c)

    is_sh = np.zeros(n, dtype=bool)
    is_sl = np.zeros(n, dtype=bool)
    for i in range(L, n - L):
        if h[i] >= np.max(h[i - L : i + L + 1]) - 1e-9:
            is_sh[i] = True
        if l[i] <= np.min(l[i - L : i + L + 1]) + 1e-9:
            is_sl[i] = True

    last_sh_px = last_sl_px = None
    last_hh = last_hl = last_lh = last_ll = None
    bias = None
    out: List[dict] = []

    def upd_bias() -> None:
        nonlocal bias
        if last_hh and last_hl and (not last_lh or last_hh[0] > last_lh[0]) and (
            not last_ll or last_hl[0] > last_ll[0]
        ):
            bias = "up"
        elif last_lh and last_ll and (not last_hh or last_lh[0] > last_hh[0]) and (
            not last_hl or last_ll[0] > last_hl[0]
        ):
            bias = "down"

    for i in range(n):
        new_high_tag = new_low_tag = None
        new_high_px = new_low_px = None

        if i >= L and is_sh[i - L]:
            j = i - L
            px = float(h[j])
            tag = None
            if last_sh_px is not None:
                tag = "HH" if px > last_sh_px else "LH"
            last_sh_px = px
            if tag:
                new_high_tag, new_high_px = tag, px
                if tag == "HH":
                    last_hh = (i, j, px)
                else:
                    last_lh = (i, j, px)

        if i >= L and is_sl[i - L]:
            j = i - L
            px = float(l[j])
            tag = None
            if last_sl_px is not None:
                tag = "HL" if px > last_sl_px else "LL"
            last_sl_px = px
            if tag:
                new_low_tag, new_low_px = tag, px
                if tag == "HL":
                    last_hl = (i, j, px)
                else:
                    last_ll = (i, j, px)

        upd_bias()
        if not (MINS_LO <= mins[i] <= MINS_HI):
            continue

        side = tag = level = None
        if new_low_tag == "HL" and bias == "up":
            side, tag, level = "BUY", "HL", new_low_px
        elif new_high_tag == "LH" and bias == "down":
            side, tag, level = "SELL", "LH", new_high_px
        if side is None:
            continue

        entry = float(c[i])
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        vw = float(vwap[i]) if np.isfinite(vwap[i]) else entry
        e9, e20, e50 = float(ema9[i]), float(ema20[i]), float(ema50[i])
        e34 = float(ema34[i]) if np.isfinite(ema34[i]) else entry
        vwap_with = (side == "BUY" and entry >= vw) or (side == "SELL" and entry <= vw)
        ema_with = (side == "BUY" and e9 >= e20) or (side == "SELL" and e9 <= e20)
        ema50_with = (side == "BUY" and entry >= e50) or (side == "SELL" and entry <= e50)
        gate34 = (side == "BUY" and entry >= e34) or (side == "SELL" and entry <= e34)
        desk_hits = sum([vwap_with, ema_with, ema50_with, gate34])
        desk_ge3 = desk_hits >= 3
        di_ok = (side == "BUY" and pdi[i] > mdi[i]) or (side == "SELL" and mdi[i] > pdi[i])
        held = bool(di_ok and gate34 and vwap_with)
        htf = _htf_at(bias_map, idx[i])
        htf_with = (side == "BUY" and htf == "up") or (side == "SELL" and htf == "down")

        st = 0
        if (side == "BUY" and c[i] > o[i]) or (side == "SELL" and c[i] < o[i]):
            s = i
            while s - 1 >= 0 and day[s - 1] == day[i]:
                if side == "BUY" and c[s - 1] > o[s - 1]:
                    s -= 1
                elif side == "SELL" and c[s - 1] < o[s - 1]:
                    s -= 1
                else:
                    break
            st = i - s + 1

        streak_ok = st >= STREAK_MIN
        gate_strict = bool(htf_with and a >= ATR_STRICT and desk_ge3 and streak_ok)
        gate_held = bool(htf_with and held and a >= ATR_HELD and streak_ok)
        gate_ok = gate_strict or gate_held
        gate_name = "ATR14+desk" if gate_strict else ("ATR12+held" if gate_held else None)

        out.append(
            {
                "full_i": i,
                "day": day[i],
                "hm": idx[i].strftime("%H:%M"),
                "mins": int(mins[i]),
                "decision": side,
                "entry": round(entry, 2),
                "primary": f"HHLL_{tag}",
                "family": "hhll",
                "struct_tag": tag,
                "struct_level": round(float(level), 2),
                "bias_1m": bias,
                "htf": htf,
                "htf_with": bool(htf_with),
                "atr": round(a, 2),
                "atr_ok": a >= ATR_HELD,
                "desk_hits": int(desk_hits),
                "desk_ge3": desk_ge3,
                "streak": int(st),
                "streak_ok": streak_ok,
                "held": held,
                "gate_ok": gate_ok,
                "gate_name": gate_name,
                "setup_label": (
                    f"HL/LH · {tag} · {gate_name}" if gate_name else f"HL/LH · {tag}"
                ),
            }
        )
    return out


def scan_hhll(
    df: pd.DataFrame,
    *,
    path_ma_trail,
    gap_mins: int = 15,
    chart_only_ungated: bool = True,
) -> Tuple[List[dict], List[dict], Optional[dict], List[str]]:
    """Score HHLL entries with EMA34 trail T15.

    Returns (calls_for_table, markers, live_row, marker_days).
    Chart shows gated winners; live = latest gated causal confirm today.
    """
    cands = detect_hhll_entries(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    idx = df.index

    scored = []
    for e in cands:
        i = int(e["full_i"])
        side = e["decision"]
        ok, reason, exit_px, j, pts = path_ma_trail(h, l, c, ema34, i, side, T15)
        e = {
            **e,
            "_win": bool(ok),
            "_reason": reason,
            "_pts": round(float(pts), 2) if pts is not None else None,
            "_exit_i": j,
            "_exit_px": round(float(exit_px), 2) if exit_px is not None else None,
            "_t1": T15,
        }
        if j is not None and 0 <= int(j) < len(idx):
            e["_exit_hm"] = idx[int(j)].strftime("%H:%M")
        scored.append(e)

    # Chart markers: gated winners (and optional ungated confirms as dots)
    markers: List[dict] = []
    marker_days: List[str] = []
    calls: List[dict] = []
    by_day: Dict[str, List[dict]] = {}
    for e in scored:
        by_day.setdefault(e["day"], []).append(e)

    for d, rows in by_day.items():
        rows = sorted(rows, key=lambda x: x["mins"])
        next_ok = None
        for e in rows:
            if not e.get("gate_ok"):
                if chart_only_ungated:
                    # faint structure mark (indication only)
                    ts = pd.Timestamp(idx[int(e["full_i"])])
                    if ts.tzinfo is None:
                        ts = ts.tz_localize("Asia/Kolkata")
                    else:
                        ts = ts.tz_convert("Asia/Kolkata")
                    markers.append(
                        {
                            "time": int(ts.timestamp()),
                            "position": "belowBar" if e["decision"] == "BUY" else "aboveBar",
                            "color": "#94a3b8",
                            "shape": "circle",
                            "text": e.get("struct_tag") or "HHLL",
                        }
                    )
                    marker_days.append(d)
                continue
            mins = int(e["mins"])
            if next_ok is not None and mins < next_ok:
                continue
            # table/call: gated only; chart highlight if path win
            calls.append(e)
            ts = pd.Timestamp(idx[int(e["full_i"])])
            if ts.tzinfo is None:
                ts = ts.tz_localize("Asia/Kolkata")
            else:
                ts = ts.tz_convert("Asia/Kolkata")
            side = e["decision"]
            win = bool(e.get("_win"))
            markers.append(
                {
                    "time": int(ts.timestamp()),
                    "position": "belowBar" if side == "BUY" else "aboveBar",
                    "color": "#0d9e6c" if (side == "BUY" and win) else (
                        "#dc2c42" if (side == "SELL" and win) else "#64748b"
                    ),
                    "shape": "arrowUp" if side == "BUY" else "arrowDown",
                    "text": f"HHLL {e.get('struct_tag')} {'✓' if win else e.get('_reason') or 'x'}",
                }
            )
            marker_days.append(d)
            if win and e.get("_exit_i") is not None:
                ets = pd.Timestamp(idx[int(e["_exit_i"])]).tz_convert("Asia/Kolkata")
                next_ok = int(ets.hour * 60 + ets.minute) + gap_mins
            else:
                next_ok = mins + gap_mins

    # Live: latest gated confirm today (causal — not requiring _win)
    today = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
    live = None
    today_gated = [e for e in sorted(by_day.get(today, []), key=lambda x: x["mins"]) if e.get("gate_ok")]
    if today_gated:
        # gap filter
        kept = []
        next_ok = None
        for e in today_gated:
            if next_ok is not None and e["mins"] < next_ok:
                continue
            kept.append(e)
            next_ok = e["mins"] + gap_mins
        if kept:
            live = kept[-1]

    return calls, markers, live, marker_days
