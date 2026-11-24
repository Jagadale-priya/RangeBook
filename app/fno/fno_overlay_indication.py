"""Curated 15m overlay indication rules → live multi-tag signals (parallel to model).

No fixed T1/SL prices. Desk hint = favour bars/pts + RULE-based book/stop
(from research JSONs). Does not block dual-track / model calls.

Live default (2026-11-17): fire **100% accuracy rules only**
(`OVERLAY_ACC_MIN=100`). Set OVERLAY_ACC_MIN=80 to include good band.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

import path_setup
ROOT = path_setup.ROOT
FAVOUR_DEFAULTS = (
    ROOT / "stock_signal_data/fno_validate/research/overlay_favour_live_defaults.json"
)
EXIT_DEFAULTS = (
    ROOT / "stock_signal_data/fno_validate/research/nifty_indication_exit_live_defaults.json"
)


def overlay_acc_min() -> float:
    """Minimum 1m research accuracy to list an overlay call.

    Default 100 — proven overlay band only. Override with OVERLAY_ACC_MIN.
    """
    raw = str(os.environ.get("OVERLAY_ACC_MIN", "100")).strip()
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 100.0


def overlay_notify_enabled() -> bool:
    """Desktop/Telegram overlay toasts. Default OFF — Scalper chart only, no notify."""
    v = str(os.environ.get("OVERLAY_NOTIFY", "0")).strip().lower()
    return v not in ("0", "false", "no", "off", "")


# Human labels for exit atom codes (desk-readable).
EXIT_ATOM_LABELS = {
    "donchian:donchian_20_high:hold_res": "Donchian 20 high holds resistance",
    "donchian:donchian_20_low:hold_sup": "Donchian 20 low holds support",
    "opening_range:or_low:break_down": "OR low breaks down",
    "opening_range:or_high:break_up": "OR high breaks up",
    "cont:vwap:cross_up": "VWAP crosses up",
    "cont:vwap:cross_down": "VWAP crosses down",
    "cont:ema20:cross_up": "EMA20 crosses up",
    "cont:ema20:cross_down": "EMA20 crosses down",
    "round_number:round_50:hold_sup": "Round 50 holds support",
    "round_number:round_50:hold_res": "Round 50 holds resistance",
    "ctx:below_ema20_ema50_vwap": "Price below EMA20/EMA50/VWAP stack",
    "ctx:above_ema20_ema50_vwap": "Price above EMA20/EMA50/VWAP stack",
}

# NIFTY 1y research fallback (no fixed pts — event rules only).
EXIT_RULE_FALLBACK = {
    "NIFTY": {
        "BUY": {
            "book_profit_rule": ["donchian:donchian_20_high:hold_res"],
            "book_profit_label": "Donchian 20 high holds resistance",
            "stop_rule": ["opening_range:or_low:break_down"],
            "stop_label": "OR low breaks down",
            "book_alt_rule": ["round_number:round_50:hold_res"],
            "book_alt_label": "Round 50 holds resistance",
            "stop_alt_rule": ["ctx:below_ema20_ema50_vwap"],
            "stop_alt_label": "Price below EMA20/EMA50/VWAP stack",
        },
        "SELL": {
            "book_profit_rule": ["donchian:donchian_20_low:hold_sup"],
            "book_profit_label": "Donchian 20 low holds support",
            "stop_rule": ["cont:vwap:cross_up"],
            "stop_label": "VWAP crosses up",
            "book_alt_rule": ["round_number:round_50:hold_sup"],
            "book_alt_label": "Round 50 holds support",
            "stop_alt_rule": ["opening_range:or_high:break_up"],
            "stop_alt_label": "OR high breaks up",
        },
    }
}

# Accuracy band tags (easy labels)
ACC_TAG_100 = {
    "code": "overlay_acc_100",
    "label": "100% accuracy (1m research)",
    "tone": "proven",
    "priority": 5,
}
ACC_TAG_90 = {
    "code": "overlay_acc_90",
    "label": "High accuracy 90–99%",
    "tone": "champion",
    "priority": 15,
}
ACC_TAG_80 = {
    "code": "overlay_acc_80",
    "label": "Good accuracy 80–89%",
    "tone": "good",
    "priority": 25,
}

# Fallback if favour research JSON missing (5m bars + median favour pts).
FAVOUR_FALLBACK = {
    "NIFTY": {
        "BUY": {
            "interval": "5minute",
            "favour_bars": 12,
            "favour_horizon_bars": 6,
            "med_favour_pts": 24.7,
            "avg_favour_pts": 71.82,
            "med_peak_pts": 46.12,
            "went_up_pct": 100.0,
        },
        "SELL": {
            "interval": "5minute",
            "favour_bars": 20,
            "favour_horizon_bars": 6,
            "med_favour_pts": 22.05,
            "avg_favour_pts": 74.29,
            "med_peak_pts": 42.95,
            "went_up_pct": 100.0,
        },
    },
    "BANKNIFTY": {
        "BUY": {
            "interval": "5minute",
            "favour_bars": 9,
            "favour_horizon_bars": 6,
            "med_favour_pts": 66.7,
            "avg_favour_pts": 165.12,
            "med_peak_pts": 118.53,
            "went_up_pct": 100.0,
        },
        "SELL": {
            "interval": "5minute",
            "favour_bars": 14,
            "favour_horizon_bars": 6,
            "med_favour_pts": 55.55,
            "avg_favour_pts": 171.69,
            "med_peak_pts": 117.03,
            "went_up_pct": 96.8,
        },
    },
    "SENSEX": {
        "BUY": {
            "interval": "5minute",
            "favour_bars": 13,
            "favour_horizon_bars": 6,
            "med_favour_pts": 67.57,
            "avg_favour_pts": 209.43,
            "med_peak_pts": 125.82,
            "went_up_pct": 100.0,
        },
        "SELL": {
            "interval": "5minute",
            "favour_bars": 19,
            "favour_horizon_bars": 6,
            "med_favour_pts": 53.9,
            "avg_favour_pts": 235.79,
            "med_peak_pts": 149.28,
            "went_up_pct": 100.0,
        },
    },
}

# Locked from 15m_overlay_combo_1m_GT80_CLEAN.md (2026-10-01→11-03).
# ONLY rules with path-acc == 100% AND average points UP (weak 100%s excluded).
# Atom aliases accepted in _parts_match (vwap / OR / bb / rnd short forms).
RULES: List[Dict[str, Any]] = [
    # --- NIFTY BUY 100% ---
    {
        "id": "nf_or_vwap",
        "side": "BUY",
        "parts": ["opening_range:or_low:hold_sup", "cont:vwap:cross_up"],
        "acc_1m": 100.0,
        "n_1m": 9,
        "avg_pts": 47.32,
        "label": "OR low hold + VWAP cross_up",
        "symbols": ("NIFTY",),
        "source": "GT80_CLEAN",
    },
    {
        "id": "nf_or_bbmid",
        "side": "BUY",
        "parts": ["opening_range:or_low:hold_sup", "bollinger:bb_mid:cross_up"],
        "acc_1m": 100.0,
        "n_1m": 7,
        "avg_pts": 35.88,
        "label": "OR low hold + BB mid cross_up",
        "symbols": ("NIFTY",),
        "source": "GT80_CLEAN",
    },
    {
        "id": "nf_r50_or_vwap",
        "side": "BUY",
        "parts": [
            "round_number:round_50:hold_sup",
            "opening_range:or_low:hold_sup",
            "cont:vwap:cross_up",
        ],
        "acc_1m": 100.0,
        "n_1m": 6,
        "avg_pts": 55.73,
        "label": "Round50 + OR low + VWAP cross_up",
        "symbols": ("NIFTY",),
        "source": "GT80_CLEAN",
    },
    {
        "id": "nf_or_ema20x",
        "side": "BUY",
        "parts": ["opening_range:or_low:hold_sup", "cont:ema20:cross_up"],
        "acc_1m": 100.0,
        "n_1m": 6,
        "avg_pts": 39.3,
        "label": "OR low hold + EMA20 cross_up",
        "symbols": ("NIFTY",),
        "source": "GT80_CLEAN",
    },
    {
        "id": "nf_r50_vwap_ema20",
        "side": "BUY",
        "parts": [
            "round_number:round_50:hold_sup",
            "cont:vwap:cross_up",
            "cont:ema20:cross_up",
        ],
        "acc_1m": 100.0,
        "n_1m": 5,
        "avg_pts": 70.02,
        "label": "Round50 + VWAP + EMA20 cross_up",
        "symbols": ("NIFTY",),
        "source": "GT80_CLEAN",
    },
    # --- NIFTY SELL 100% ---
    {
        "id": "nf_dc_r50_or",
        "side": "SELL",
        "parts": [
            "donchian:donchian_20_high:hold_res",
            "round_number:round_50:hold_res",
            "opening_range:or_high:hold_res",
        ],
        "acc_1m": 100.0,
        "n_1m": 5,
        "avg_pts": 65.13,
        "label": "Donchian high + Round50 + OR high",
        "symbols": ("NIFTY",),
        "source": "GT80_CLEAN",
    },
    # --- BANKNIFTY BUY 100% ---
    {
        "id": "bn_r100_vwap",
        "side": "BUY",
        "parts": ["round_number:round_100:hold_sup", "cont:vwap:cross_up"],
        "acc_1m": 100.0,
        "n_1m": 12,
        "avg_pts": 65.99,
        "label": "Round100 hold + VWAP cross_up",
        "symbols": ("BANKNIFTY",),
        "source": "GT80_CLEAN",
    },
    {
        "id": "bn_bbmid_cpr",
        "side": "BUY",
        "parts": ["bollinger:bb_mid:hold_sup", "cpr:pivot:hold_sup"],
        "acc_1m": 100.0,
        "n_1m": 6,
        "avg_pts": 95.92,
        "label": "BB mid hold + CPR pivot hold",
        "symbols": ("BANKNIFTY",),
        "source": "GT80_CLEAN",
    },
    {
        "id": "bn_vwap_ema20",
        "side": "BUY",
        "parts": ["cont:vwap:cross_up", "cont:ema20:hold_sup"],
        "acc_1m": 100.0,
        "n_1m": 5,
        "avg_pts": 76.14,
        "label": "VWAP cross_up + EMA20 hold",
        "symbols": ("BANKNIFTY",),
        "source": "GT80_CLEAN",
    },
    {
        "id": "bn_bbx_cpr_bc",
        "side": "BUY",
        "parts": ["bollinger:bb_mid:cross_up", "cpr:bc:hold_sup"],
        "acc_1m": 100.0,
        "n_1m": 5,
        "avg_pts": 46.96,
        "label": "BB mid cross_up + CPR BC hold",
        "symbols": ("BANKNIFTY",),
        "source": "GT80_CLEAN",
    },
    # --- BANKNIFTY SELL 100% ---
    {
        "id": "bn_r100_prior_high",
        "side": "SELL",
        "parts": ["round_number:round_100:hold_res", "prior_day:prior_high:hold_res"],
        "acc_1m": 100.0,
        "n_1m": 5,
        "avg_pts": 268.17,
        "label": "Round100 + prior high hold",
        "symbols": ("BANKNIFTY",),
        "source": "GT80_CLEAN",
    },
    {
        "id": "bn_vwap_or_bb",
        "side": "SELL",
        "parts": [
            "cont:vwap:cross_down",
            "opening_range:or_high:hold_res",
            "bollinger:bb_mid:cross_down",
        ],
        "acc_1m": 100.0,
        "n_1m": 5,
        "avg_pts": 16.71,
        "label": "VWAP cross_down + OR high + BB mid cross_down",
        "symbols": ("BANKNIFTY",),
        "source": "GT80_CLEAN",
    },
    # --- SENSEX BUY 100% ---
    {
        "id": "sx_ema20_stack",
        "side": "BUY",
        "parts": ["cont:ema20:hold_sup", "ctx:above_ema20_ema50_vwap"],
        "acc_1m": 100.0,
        "n_1m": 9,
        "avg_pts": 223.46,
        "label": "EMA20 hold + above stack",
        "symbols": ("SENSEX",),
        "source": "GT80_CLEAN",
    },
    {
        "id": "sx_vwap_bbmid",
        "side": "BUY",
        "parts": ["cont:vwap:cross_up", "bollinger:bb_mid:hold_sup"],
        "acc_1m": 100.0,
        "n_1m": 8,
        "avg_pts": 360.18,
        "label": "VWAP cross_up + BB mid hold",
        "symbols": ("SENSEX",),
        "source": "GT80_CLEAN",
    },
    {
        "id": "sx_fib05",
        "side": "BUY",
        "parts": ["fibonacci:fib_0_5:hold_sup"],
        "acc_1m": 100.0,
        "n_1m": 8,
        "avg_pts": 257.32,
        "label": "Fib 0.5 hold support",
        "symbols": ("SENSEX",),
        "source": "GT80_CLEAN",
    },
    {
        "id": "sx_swing_vwap",
        "side": "BUY",
        "parts": ["swing_sr:swing_cluster:hold_sup", "cont:vwap:cross_up"],
        "acc_1m": 100.0,
        "n_1m": 7,
        "avg_pts": 73.05,
        "label": "Swing hold + VWAP cross_up",
        "symbols": ("SENSEX",),
        "source": "GT80_CLEAN",
    },
    {
        "id": "sx_swing_bbx",
        "side": "BUY",
        "parts": ["swing_sr:swing_cluster:hold_sup", "bollinger:bb_mid:cross_up"],
        "acc_1m": 100.0,
        "n_1m": 5,
        "avg_pts": 120.33,
        "label": "Swing hold + BB mid cross_up",
        "symbols": ("SENSEX",),
        "source": "GT80_CLEAN",
    },
]

# Aliases so GT80 short forms / dual VWAP encodings still match.
_PART_ALIASES: Dict[str, Tuple[str, ...]] = {
    "cont:vwap:cross_up": ("cont:vwap:cross_up", "vwap:session_tp_mean:cross_up"),
    "cont:vwap:cross_down": ("cont:vwap:cross_down", "vwap:session_tp_mean:cross_down"),
    "cont:vwap:hold_sup": ("cont:vwap:hold_sup", "vwap:session_tp_mean:hold_sup"),
    "cont:vwap:hold_res": ("cont:vwap:hold_res", "vwap:session_tp_mean:hold_res"),
    "vwap:session_tp_mean:cross_up": ("cont:vwap:cross_up", "vwap:session_tp_mean:cross_up"),
    "vwap:session_tp_mean:cross_down": ("cont:vwap:cross_down", "vwap:session_tp_mean:cross_down"),
}


def _parts_match(parts: Sequence[str], pool: Set[str]) -> bool:
    for p in parts:
        alts = _PART_ALIASES.get(str(p), (str(p),))
        if not any(a in pool for a in alts):
            return False
    return True


def proven_100_rules(*, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    """Research-proven 100% overlay rules (optionally filtered by symbol)."""
    sym = str(symbol or "").upper().replace(" ", "")
    if sym in ("NIFTY50", "NIFTY 50"):
        sym = "NIFTY"
    out = []
    for r in RULES:
        if float(r.get("acc_1m") or 0) < 99.5:
            continue
        if sym and sym not in (r.get("symbols") or ()):
            continue
        out.append(dict(r))
    return out


def accuracy_tag(acc: float) -> Dict[str, Any]:
    if acc >= 99.5:
        base = dict(ACC_TAG_100)
    elif acc >= 90.0:
        base = dict(ACC_TAG_90)
    else:
        base = dict(ACC_TAG_80)
    base["expected_hit_pct"] = float(acc)
    base["detail"] = f"1-month overlay research path hit ~{acc:.0f}%"
    return base


def _enrich_favour(hint: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize favour hint for UI (bars on 5m + typical points)."""
    h = dict(hint or {})
    bars = int(h.get("favour_bars") or h.get("med_bars_to_peak") or 6)
    interval = str(h.get("interval") or "5minute")
    med_at_h = h.get("med_favour_pts")
    peak = h.get("med_peak_pts") or h.get("avg_favour_pts") or med_at_h
    # Research book/early-kill horizon = MFE@6 window (not full bars-to-peak).
    horizon = int(h.get("favour_horizon_bars") or 6)
    mins = bars * (5 if "5" in interval else 1)
    h["favour_bars"] = bars
    h["favour_horizon_bars"] = horizon
    h["interval"] = interval
    h["favour_minutes"] = mins
    h["med_favour_pts"] = med_at_h
    h["med_peak_pts"] = peak
    h["label"] = (
        f"Typically favour ~{bars}×5m bars (~{mins} min) · "
        f"median ~{med_at_h} pts by {horizon} bars · peak med ~{peak} pts"
    )
    h["note"] = h.get("note") or h["label"]
    return h


def load_favour_defaults() -> Dict[str, Any]:
    """Favour-bar hints from 5m/1m research (no T1/SL)."""
    out: Dict[str, Any] = {
        "source": "fallback",
        "symbols": {k: {s: _enrich_favour(v) for s, v in sides.items()} for k, sides in FAVOUR_FALLBACK.items()},
    }
    if FAVOUR_DEFAULTS.is_file():
        try:
            rep = json.loads(FAVOUR_DEFAULTS.read_text(encoding="utf-8"))
            syms = rep.get("symbols") or {}
            merged = {}
            for sym, sides in FAVOUR_FALLBACK.items():
                merged[sym] = {}
                for side, fb in sides.items():
                    raw = (syms.get(sym) or {}).get(side) or fb
                    # Attach peak from research multi med_mfe when present in raw note fields
                    enriched = _enrich_favour(raw)
                    if raw.get("avg_favour_pts") and not raw.get("med_peak_pts"):
                        enriched["med_peak_pts"] = raw.get("avg_favour_pts")
                        enriched = _enrich_favour(enriched)
                    merged[sym][side] = enriched
            out["symbols"] = merged
            out["source"] = "overlay_favour_bars_5m_1m"
            out["generated_at"] = rep.get("generated_at")
        except Exception:
            pass
    return out


def load_live_defaults() -> Dict[str, Any]:
    """Back-compat alias → favour defaults (no T1/SL levels)."""
    return load_favour_defaults()


def favour_for(symbol: str, side: str) -> Dict[str, Any]:
    pack = load_favour_defaults()
    sym = str(symbol or "NIFTY").upper()
    return ((pack.get("symbols") or {}).get(sym) or {}).get(side) or _enrich_favour(
        FAVOUR_FALLBACK.get("NIFTY", {}).get(side) or {}
    )


def _human_exit_parts(parts: List[str]) -> str:
    bits = [EXIT_ATOM_LABELS.get(p, p) for p in parts]
    return " + ".join(bits)


def load_exit_defaults() -> Dict[str, Any]:
    """Book-profit / stop RULES (no price levels) from 1y NIFTY research."""
    nifty = dict(EXIT_RULE_FALLBACK.get("NIFTY") or {})
    out: Dict[str, Any] = {
        "source": "fallback",
        "symbols": {
            "NIFTY": nifty,
            "BANKNIFTY": nifty,
            "SENSEX": nifty,
        },
    }
    if EXIT_DEFAULTS.is_file():
        try:
            rep = json.loads(EXIT_DEFAULTS.read_text(encoding="utf-8"))
            # File is flat NIFTY BUY/SELL; normalize to symbols map
            merged = dict(EXIT_RULE_FALLBACK.get("NIFTY") or {})
            for side in ("BUY", "SELL"):
                raw = rep.get(side) or {}
                if not raw:
                    continue
                book = list(raw.get("book_profit_rule") or merged[side]["book_profit_rule"])
                stop = list(raw.get("stop_rule") or merged[side]["stop_rule"])
                merged[side] = {
                    **merged[side],
                    "book_profit_rule": book,
                    "book_profit_label": raw.get("book_profit_label")
                    or _human_exit_parts(book),
                    "stop_rule": stop,
                    "stop_label": raw.get("stop_label") or _human_exit_parts(stop),
                    "plain": raw.get("plain") or {},
                    "stats": raw.get("stats") or {},
                }
            out["symbols"] = {"NIFTY": merged}
            # Apply NIFTY rules to BN/Sensex until per-index research exists
            for sym in ("BANKNIFTY", "SENSEX"):
                out["symbols"][sym] = merged
            out["source"] = "nifty_indication_exit_rules_1y"
            out["generated_at"] = rep.get("generated_at")
        except Exception:
            pass
    return out


def exit_rules_for(symbol: str, side: str) -> Dict[str, Any]:
    pack = load_exit_defaults()
    sym = str(symbol or "NIFTY").upper()
    side = str(side or "BUY").upper()
    base = ((pack.get("symbols") or {}).get(sym) or {}).get(side) or (
        EXIT_RULE_FALLBACK.get("NIFTY", {}).get(side) or {}
    )
    h = dict(base)
    book = list(h.get("book_profit_rule") or [])
    stop = list(h.get("stop_rule") or [])
    h["book_profit_rule"] = book
    h["stop_rule"] = stop
    # Always prefer human desk labels over raw atom codes
    h["book_profit_label"] = _human_exit_parts(book) if book else (h.get("book_profit_label") or "")
    h["stop_label"] = _human_exit_parts(stop) if stop else (h.get("stop_label") or "")
    alt_b = list(h.get("book_alt_rule") or [])
    alt_s = list(h.get("stop_alt_rule") or [])
    h["book_alt_rule"] = alt_b
    h["stop_alt_rule"] = alt_s
    h["book_alt_label"] = _human_exit_parts(alt_b) if alt_b else (h.get("book_alt_label") or "")
    h["stop_alt_label"] = _human_exit_parts(alt_s) if alt_s else (h.get("stop_alt_label") or "")
    return h


def _ensure_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Kite frames often use lowercase open/high/low/close — research helpers need Title case."""
    if df is None or getattr(df, "empty", True):
        return df
    work = df.copy()
    rename = {}
    for c in work.columns:
        cl = str(c).strip().lower()
        if cl in ("open", "o") and "Open" not in work.columns:
            rename[c] = "Open"
        elif cl in ("high", "h") and "High" not in work.columns:
            rename[c] = "High"
        elif cl in ("low", "l") and "Low" not in work.columns:
            rename[c] = "Low"
        elif cl in ("close", "c") and "Close" not in work.columns:
            rename[c] = "Close"
        elif cl in ("volume", "vol", "v") and "Volume" not in work.columns:
            rename[c] = "Volume"
    if rename:
        work = work.rename(columns=rename)
    return work


def _atr_series(df: pd.DataFrame, n: int = 14) -> np.ndarray:
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    c = df["Close"].astype(float)
    prev = c.shift(1)
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    out = tr.ewm(alpha=1.0 / n, adjust=False).mean().to_numpy(dtype=float)
    return out


def _session_vwap(df: pd.DataFrame) -> np.ndarray:
    """Per-session VWAP (or TP mean when volume is empty)."""
    n = len(df)
    out = np.full(n, np.nan, dtype=float)
    if n == 0:
        return out
    idx = df.index
    days = np.array(
        [(t.date() if hasattr(t, "date") else pd.Timestamp(t).date()) for t in idx]
    )
    tp = (
        df["High"].astype(float).to_numpy()
        + df["Low"].astype(float).to_numpy()
        + df["Close"].astype(float).to_numpy()
    ) / 3.0
    vol = (
        df["Volume"].astype(float).to_numpy()
        if "Volume" in df.columns
        else np.zeros(n, dtype=float)
    )
    i = 0
    while i < n:
        d = days[i]
        j = i
        while j < n and days[j] == d:
            j += 1
        seg_tp = tp[i:j]
        seg_v = vol[i:j]
        cum_pv = 0.0
        cum_v = 0.0
        for k, (tpx, vx) in enumerate(zip(seg_tp, seg_v)):
            cum_pv += float(tpx) * max(float(vx), 0.0)
            cum_v += max(float(vx), 0.0)
            if cum_v > 0:
                out[i + k] = cum_pv / cum_v
            else:
                # TP mean fallback (index tapes often Volume=0)
                out[i + k] = float(np.mean(seg_tp[: k + 1]))
        i = j
    return out


def _atomic_from_levels(
    levels: Sequence[Dict[str, Any]],
    *,
    o: float,
    h: float,
    l: float,
    c: float,
    prev_c: float,
    atr: float,
) -> Set[str]:
    """Map overlay levels → BUY|family:code:event / SELL|… atoms."""
    atoms: Set[str] = set()
    band = max(float(atr) * 0.15, 1.0)

    def _add(side: str, family: str, code: str, event: str) -> None:
        atoms.add(f"{side}|{family}:{code}:{event}")

    for lvl in levels or []:
        if not isinstance(lvl, dict):
            continue
        family = str(lvl.get("family") or "")
        code = str(lvl.get("code") or "")
        try:
            px = float(lvl.get("price"))
        except (TypeError, ValueError):
            continue
        if not family or not code or not np.isfinite(px):
            continue
        # Support hold: wick tags/pierces level, close at or above (research atom)
        if l <= px and c >= px:
            _add("BUY", family, code, "hold_sup")
        if prev_c >= px and c < px and l < px - band * 0.25:
            _add("SELL", family, code, "break_down")
        # Resistance hold: wick tags/pierces level, close at or below
        if h >= px and c <= px:
            _add("SELL", family, code, "hold_res")
        if prev_c <= px and c > px and h > px + band * 0.25:
            _add("BUY", family, code, "break_up")
        # Cross events vs prior close
        if prev_c < px <= c:
            _add("BUY", family, code, "cross_up")
        if prev_c > px >= c:
            _add("SELL", family, code, "cross_down")
    return atoms


def _continuous_events(
    df: pd.DataFrame,
    i: int,
    atr: float,
    vwap: np.ndarray,
    ema20: np.ndarray,
    ema50: np.ndarray,
) -> Set[str]:
    """VWAP / EMA continuous atoms + stack context."""
    atoms: Set[str] = set()
    if i <= 0 or i >= len(df):
        return atoms
    c = float(df["Close"].iloc[i])
    prev = float(df["Close"].iloc[i - 1])
    h = float(df["High"].iloc[i])
    l = float(df["Low"].iloc[i])
    band = max(float(atr) * 0.15, 1.0)

    def _line_events(name: str, cur: float, prev_line: float) -> None:
        if not np.isfinite(cur) or not np.isfinite(prev_line):
            return
        if l <= cur and c >= cur:
            atoms.add(f"BUY|cont:{name}:hold_sup")
        if h >= cur and c <= cur:
            atoms.add(f"SELL|cont:{name}:hold_res")
        if prev < prev_line and c >= cur:
            atoms.add(f"BUY|cont:{name}:cross_up")
        if prev > prev_line and c <= cur:
            atoms.add(f"SELL|cont:{name}:cross_down")
        # Also mirror as vwap:session_tp_mean for VWAP
        if name == "vwap":
            if prev < prev_line and c >= cur:
                atoms.add("BUY|vwap:session_tp_mean:cross_up")
            if prev > prev_line and c <= cur:
                atoms.add("SELL|vwap:session_tp_mean:cross_down")
            if l <= cur and c >= cur:
                atoms.add("BUY|vwap:session_tp_mean:hold_sup")
            if h >= cur and c <= cur:
                atoms.add("SELL|vwap:session_tp_mean:hold_res")

    v_now = float(vwap[i]) if i < len(vwap) else float("nan")
    v_prev = float(vwap[i - 1]) if i - 1 < len(vwap) else v_now
    e20 = float(ema20[i]) if i < len(ema20) else float("nan")
    e20p = float(ema20[i - 1]) if i - 1 < len(ema20) else e20
    e50 = float(ema50[i]) if i < len(ema50) else float("nan")
    e50p = float(ema50[i - 1]) if i - 1 < len(ema50) else e50
    _line_events("vwap", v_now, v_prev)
    _line_events("ema20", e20, e20p)
    _line_events("ema50", e50, e50p)
    # EMA family aliases used by curated rules
    if np.isfinite(e20) and l <= e20 and c >= e20:
        atoms.add("BUY|ema:ema_20:hold_sup")
    if np.isfinite(e50) and l <= e50 and c >= e50:
        atoms.add("BUY|ema:ema_50:hold_sup")
    if np.isfinite(e20) and h >= e20 and c <= e20:
        atoms.add("SELL|ema:ema_20:hold_res")
    if np.isfinite(e50) and h >= e50 and c <= e50:
        atoms.add("SELL|ema:ema_50:hold_res")
    if all(np.isfinite(x) for x in (e20, e50, v_now)):
        if c > e20 and c > e50 and c > v_now:
            atoms.add("BUY|ctx:above_ema20_ema50_vwap")
        if c < e20 and c < e50 and c < v_now:
            atoms.add("SELL|ctx:below_ema20_ema50_vwap")
    return atoms


def _session_bar_index(df: pd.DataFrame, i: int) -> int:
    """0-based bar index within the IST session day."""
    if i < 0 or i >= len(df):
        return -1
    ts = pd.Timestamp(df.index[i])
    if ts.tzinfo is None:
        ts = ts.tz_localize("Asia/Kolkata")
    else:
        ts = ts.tz_convert("Asia/Kolkata")
    day = ts.date()
    n = 0
    for k in range(i + 1):
        t = pd.Timestamp(df.index[k])
        if t.tzinfo is None:
            t = t.tz_localize("Asia/Kolkata")
        else:
            t = t.tz_convert("Asia/Kolkata")
        if t.date() == day:
            n += 1
    return n - 1


def _atoms_at_bar(df: pd.DataFrame, i: int, *, or_bars: int = 1) -> Tuple[Set[str], Set[str], float]:
    """Return (buy_atoms, sell_atoms, atr) for bar i.

    OR atoms only after the opening-range window has closed (no self-hold on OR bar).
    VWAP/EMA crosses require prior bar in the same session (no overnight fake cross).
    """
    import fno_chart_overlays as ov

    df = _ensure_ohlc(df)
    atr_s = _atr_series(df)
    a = float(atr_s[i] or 0)
    if a <= 0 or np.isnan(a):
        return set(), set(), 0.0
    vwap = _session_vwap(df)
    close = df["Close"].astype(float)
    ema20 = close.ewm(span=20, adjust=False).mean().to_numpy()
    ema50 = close.ewm(span=50, adjust=False).mean().to_numpy()
    pack = ov.build_overlays(df.iloc[: i + 1], lookback=280, or_bars=or_bars)
    if not pack.get("available"):
        return set(), set(), a
    o = float(df["Open"].iloc[i])
    h = float(df["High"].iloc[i])
    l = float(df["Low"].iloc[i])
    c = float(df["Close"].iloc[i])
    prev_c = float(df["Close"].iloc[i - 1]) if i > 0 else c
    atoms = _atomic_from_levels(
        pack.get("levels") or [], o=o, h=h, l=l, c=c, prev_c=prev_c, atr=a
    )
    sess_i = _session_bar_index(df, i)
    # Drop OR events until OR window is complete (no self-hold on the OR bar)
    if sess_i < int(or_bars):
        atoms = {x for x in atoms if "opening_range:" not in x}
    same_session_prev = sess_i > 0
    if same_session_prev:
    atoms |= _continuous_events(df, i, a, vwap, ema20, ema50)
    else:
        # First session bar: holds/stack OK; no overnight fake crosses (levels or cont)
        cont = _continuous_events(df, i, a, vwap, ema20, ema50)
        atoms |= {x for x in cont if ":cross_" not in x}
        atoms = {x for x in atoms if ":cross_" not in x}
    buy = {x.split("|", 1)[1] for x in atoms if x.startswith("BUY|")}
    sell = {x.split("|", 1)[1] for x in atoms if x.startswith("SELL|")}
    return buy, sell, a


PATH_ATR = 0.35
PATH_MAX_BARS = 8


def path_hit(
    df: pd.DataFrame,
    i: int,
    side: str,
    atr: float,
    *,
    max_bars: int = PATH_MAX_BARS,
) -> Optional[bool]:
    """Research path win: first touch of 0.35×ATR in favour within ~8 bars."""
    if atr is None or not np.isfinite(atr) or atr <= 0:
        return None
    if i < 0 or i >= len(df) - 1:
        return None  # live/open bar — unresolved
    side = str(side or "").upper()
    need = PATH_ATR * float(atr)
    entry = float(df["Close"].iloc[i])
    end = min(len(df) - 1, i + int(max_bars))
    touched = False
    for j in range(i + 1, end + 1):
        hi = float(df["High"].iloc[j])
        lo = float(df["Low"].iloc[j])
        if side == "BUY":
            if hi - entry >= need:
                return True
            if entry - lo >= need:
                return False
        else:
            if entry - lo >= need:
                return True
            if hi - entry >= need:
                return False
        touched = True
    if not touched:
        return None
    # Window complete with no 0.35×ATR touch either way → miss
    return False


def evaluate_bar(
    df: pd.DataFrame,
    *,
    symbol: str,
    i: Optional[int] = None,
    asof: Any = None,
) -> Optional[Dict[str, Any]]:
    """Overlay indication channel retired — always no signal.

    Dual proven/champion is the only live call path for NIFTY/BN/SENSEX.
    """
    return None
    # --- retired ---
    if df is None or len(df) < 80:
        return None
    df = _ensure_ohlc(df)
    sym = str(symbol or "").upper().replace(" ", "")
    if sym in ("NIFTY50", "NIFTY 50"):
        sym = "NIFTY"
    if i is None:
        i = len(df) - 1
    # Skip first session bar — OR/VWAP/stack not reliable at the open print
    if _session_bar_index(df, i) <= 0:
        return None
    buy, sell, atr = _atoms_at_bar(df, i)
    prev_buy: Set[str] = set()
    prev_sell: Set[str] = set()
    if i > 0:
        prev_buy, prev_sell, _ = _atoms_at_bar(df, i - 1)
    acc_floor = overlay_acc_min()
    matched: List[Dict[str, Any]] = []
    for rule in RULES:
        if sym not in rule.get("symbols", ()):
            continue
        if float(rule.get("acc_1m") or 0) < acc_floor:
            continue
        pool = buy if rule["side"] == "BUY" else sell
        prev_pool = prev_buy if rule["side"] == "BUY" else prev_sell
        if not _parts_match(rule["parts"], pool):
            continue
        # Rising-edge only: skip if the same combo already true on prior bar
        if _parts_match(rule["parts"], prev_pool):
            continue
            matched.append(rule)
    if not matched:
        return None

    # One call: majority side; attach all matching tags on that side
    sides = [r["side"] for r in matched]
    side = max(set(sides), key=sides.count)
    side_rules = [r for r in matched if r["side"] == side]
    # Prefer 100% tags when mixed (should be rare once floor=100)
    side_rules = sorted(side_rules, key=lambda r: float(r.get("acc_1m") or 0), reverse=True)
    entry = float(df["Close"].iloc[i])
    favour = favour_for(sym, side)
    exits = exit_rules_for(sym, side)
    tags: List[Dict[str, Any]] = []
    # Channel tag
    tags.append(
        {
            "code": "overlay_indication",
            "label": "Overlay indication",
            "detail": "15m overlay research — favour bars + book/stop RULES (no price levels)",
            "tone": "info",
            "priority": 50,
        }
    )
    # Favour-bar tag (research)
    tags.append(
        {
            "code": "favour_bars",
            "label": (
                f"~{favour.get('favour_bars')}×5m favour "
                f"(~{favour.get('favour_minutes')} min)"
            ),
            "detail": favour.get("label") or favour.get("note"),
            "tone": "good",
            "priority": 20,
        }
    )
    if favour.get("med_favour_pts") is not None:
        tags.append(
            {
                "code": "favour_pts",
                "label": f"Med ~{favour.get('med_favour_pts')} pts by 6×5m",
                "detail": f"Peak med ~{favour.get('med_peak_pts')} pts on 5m path research",
                "tone": "neutral",
                "priority": 21,
            }
        )
    tags.append(
        {
            "code": "book_profit_rule",
            "label": f"Book: {exits.get('book_profit_label')}",
            "detail": (exits.get("plain") or {}).get("book")
            or f"Book profit when {_human_exit_parts(exits.get('book_profit_rule') or [])}",
            "tone": "good",
            "priority": 18,
        }
    )
    tags.append(
        {
            "code": "stop_rule",
            "label": f"Stop: {exits.get('stop_label')}",
            "detail": (exits.get("plain") or {}).get("stop")
            or f"Invalidate when {_human_exit_parts(exits.get('stop_rule') or [])}",
            "tone": "warn",
            "priority": 19,
        }
    )
    # Accuracy bands present
    accs = sorted({float(r["acc_1m"]) for r in side_rules}, reverse=True)
    for acc in accs:
        tags.append(accuracy_tag(acc))
    # Per-rule tags
    for r in side_rules:
        tags.append(
            {
                "code": f"rule_{r['id']}",
                "label": r["label"],
                "detail": f"1m path ~{r['acc_1m']:.0f}%",
                "expected_hit_pct": r["acc_1m"],
                "tone": "neutral",
                "priority": 60,
            }
        )
    best_acc = max(float(r["acc_1m"]) for r in side_rules)
    if best_acc >= 99.5:
        accuracy_label = "100% accuracy (overlay research)"
    elif best_acc >= 90.0:
        accuracy_label = f"High accuracy ~{best_acc:.0f}% (overlay)"
    else:
        accuracy_label = f"Good accuracy ~{best_acc:.0f}% (overlay)"

    ts = df.index[i]
    return {
        "available": True,
        "channel": "overlay_indication",
        "symbol": sym,
        "side": side,
        "decision": side,
        "entry": round(entry, 2),
        # No fixed ticket levels — favour bars + event rules for book/stop
        "stop_loss": None,
        "target_1": None,
        "favour": favour,
        "favour_bars": favour.get("favour_bars"),
        "favour_horizon_bars": favour.get("favour_horizon_bars"),
        "favour_minutes": favour.get("favour_minutes"),
        "med_favour_pts": favour.get("med_favour_pts"),
        "med_peak_pts": favour.get("med_peak_pts"),
        "favour_label": favour.get("label"),
        "exit_rules": exits,
        "book_profit_rule": exits.get("book_profit_rule"),
        "book_profit_label": exits.get("book_profit_label"),
        "stop_rule": exits.get("stop_rule"),
        "stop_label": exits.get("stop_label"),
        "book_alt_rule": exits.get("book_alt_rule"),
        "book_alt_label": exits.get("book_alt_label"),
        "stop_alt_rule": exits.get("stop_alt_rule"),
        "stop_alt_label": exits.get("stop_alt_label"),
        "atr": round(atr, 2),
        "bar_time": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
        "rule_ids": [r["id"] for r in side_rules],
        "rule_labels": [r["label"] for r in side_rules],
        "n_tags": len(side_rules),
        "best_acc_1m": best_acc,
        "accuracy_label": accuracy_label,
        "accuracy_tags": tags,
        "levels_mode": "favour_bars_plus_exit_rules",
        "t1_sl_source": None,
        "history_eligible": True,
        "live_confluence": False,
        "overlay_indication": True,
        "notify": False,  # overlay desk toasts disabled (OVERLAY_NOTIFY=0)
        "disclaimer": (
            "Overlay indication — no stop/target prices. "
            "Book profit and stop are RULES (overlay events), plus favour-bar hints. "
            "No desktop notify."
        ),
    }


def evaluate_latest(df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    return evaluate_bar(df, symbol=symbol)


def evaluate_exit_on_bar(
    df: pd.DataFrame,
    *,
    side: str,
    book_rule: Optional[Sequence[str]] = None,
    stop_rule: Optional[Sequence[str]] = None,
    i: Optional[int] = None,
    symbol: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Check latest (or given) bar for book-profit / stop RULE hits. No prices.

    BUY book/stop look at SELL-side atoms (resistance / breakdown).
    SELL book/stop look at BUY-side atoms (support / breakout).
    Stop wins if both fire on the same bar (conservative).
    """
    if df is None or len(df) < 80:
        return None
    df = _ensure_ohlc(df)
    side = str(side or "").upper()
    if side not in ("BUY", "SELL"):
        return None
    if i is None:
        i = len(df) - 1
    buy, sell, _atr = _atoms_at_bar(df, i)
    # Exit pool: opposite-direction event set
    pool = sell if side == "BUY" else buy
    if not book_rule and not stop_rule and symbol:
        exits = exit_rules_for(symbol, side)
        book_rule = exits.get("book_profit_rule")
        stop_rule = exits.get("stop_rule")
    book_parts = [str(p) for p in (book_rule or [])]
    stop_parts = [str(p) for p in (stop_rule or [])]
    book_hit = bool(book_parts) and all(p in pool for p in book_parts)
    stop_hit = bool(stop_parts) and all(p in pool for p in stop_parts)
    if stop_hit and book_hit:
        hit = "stopped"
        which = "stop"
    elif stop_hit:
        hit = "stopped"
        which = "stop"
    elif book_hit:
        hit = "booked"
        which = "book"
    else:
        return {
            "hit": None,
            "status": None,
            "book_hit": False,
            "stop_hit": False,
            "bar_time": (
                df.index[i].isoformat()
                if hasattr(df.index[i], "isoformat")
                else str(df.index[i])
            ),
        }
    return {
        "hit": which,
        "status": hit,
        "book_hit": book_hit,
        "stop_hit": stop_hit,
        "book_rule": book_parts,
        "stop_rule": stop_parts,
        "book_label": _human_exit_parts(book_parts) if book_parts else "",
        "stop_label": _human_exit_parts(stop_parts) if stop_parts else "",
        "bar_time": (
            df.index[i].isoformat()
            if hasattr(df.index[i], "isoformat")
            else str(df.index[i])
        ),
    }
