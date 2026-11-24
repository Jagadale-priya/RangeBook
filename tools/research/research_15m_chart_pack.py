"""15m chart overlay pack for desk visual validation (never lists Calls).

Includes Groww/Zerodha-style desk indications on the last N sessions:
  OR, swing S/R, prior day, round, Fib, EMA, VWAP, Bollinger, CPR,
  W/M patterns, rising/falling trendlines.

Research-gate tags still mark proven vs desk_visual — none feed Calls.

Usage:
  python tools/research/research_15m_chart_pack.py --symbol NIFTY --sessions 15
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import fno_chart_overlays as overlays  # noqa: E402

TAPE = {
    "NIFTY": ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_12y.csv",
    "BANKNIFTY": ROOT / "stock_signal_data" / "fno_validate" / "BANKNIFTY_15m_12y.csv",
    "SENSEX": ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_15m_12y.csv",
}
TAPE_1M = {
    "NIFTY": ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_1m_kite.csv",
    "BANKNIFTY": ROOT / "stock_signal_data" / "fno_validate" / "BANKNIFTY_1m_kite.csv",
    "SENSEX": ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_1m_kite.csv",
}
# Wall-clock OR ≈ 15 minutes on each TF
OR_BARS_BY_INTERVAL = {
    "minute": 15,
    "1minute": 15,
    "5minute": 3,
    "15minute": 1,
}
DEFAULT_SESSIONS = {
    "minute": 5,
    "1minute": 5,
    "5minute": 8,
    "15minute": 15,
}
OUT_DIR = ROOT / "stock_signal_data" / "fno_validate" / "research"

# Proven / near-proven by bounce-vs-random research
PROVEN_FAMILIES = ("opening_range", "swing_sr", "prior_day", "round_number")
# Desk visuals (Groww/Zerodha-style) — chart only, not Calls
DESK_FAMILIES = ("fibonacci", "ema", "vwap", "bollinger", "cpr", "donchian")
ALL_LEVEL_FAMILIES = PROVEN_FAMILIES + DESK_FAMILIES

MAX_SWING = 6
MAX_ROUND = 4
MAX_FIB = 5
MAX_CPR = 5

STYLE = {
    "opening_range": {"color": "#2563eb", "lineStyle": 0, "lineWidth": 2, "label": "OR"},
    "swing_sr": {"color": "#059669", "lineStyle": 2, "lineWidth": 1, "label": "Swing"},
    "prior_day": {"color": "#7c3aed", "lineStyle": 1, "lineWidth": 1, "label": "Prior"},
    "round_number": {"color": "#64748b", "lineStyle": 1, "lineWidth": 1, "label": "Round"},
    "fibonacci": {"color": "#ea580c", "lineStyle": 2, "lineWidth": 1, "label": "Fib"},
    "ema": {"color": "#0891b2", "lineStyle": 0, "lineWidth": 1, "label": "EMA"},
    "vwap": {"color": "#c026d3", "lineStyle": 0, "lineWidth": 2, "label": "VWAP"},
    "bollinger": {"color": "#78716c", "lineStyle": 2, "lineWidth": 1, "label": "BB"},
    "cpr": {"color": "#4f46e5", "lineStyle": 1, "lineWidth": 1, "label": "CPR"},
    "donchian": {"color": "#0f766e", "lineStyle": 2, "lineWidth": 1, "label": "Don"},
}

SERIES_STYLE = {
    "ema_9": {"color": "#06b6d4", "lineWidth": 1, "title": "EMA 9"},
    "ema_20": {"color": "#0284c7", "lineWidth": 2, "title": "EMA 20"},
    "ema_50": {"color": "#1d4ed8", "lineWidth": 2, "title": "EMA 50"},
    "vwap": {"color": "#c026d3", "lineWidth": 2, "title": "VWAP"},
    "bb_mid": {"color": "#a8a29e", "lineWidth": 1, "title": "BB mid"},
    "bb_upper": {"color": "#a8a29e", "lineWidth": 1, "title": "BB up", "lineStyle": 2},
    "bb_lower": {"color": "#a8a29e", "lineWidth": 1, "title": "BB lo", "lineStyle": 2},
}


def _norm(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    work = overlays._norm(df)
    if work is None:
        return None
    if not isinstance(work.index, pd.DatetimeIndex):
        work = work.copy()
        work.index = pd.to_datetime(work.index)
    if work.index.tz is None:
        work.index = work.index.tz_localize("Asia/Kolkata")
    else:
        work.index = work.index.tz_convert("Asia/Kolkata")
    return work


def _session_days(index: pd.DatetimeIndex) -> List[Any]:
    days = []
    seen = set()
    for ts in index:
        d = ts.date() if hasattr(ts, "date") else pd.Timestamp(ts).date()
        if d not in seen:
            seen.add(d)
            days.append(d)
    return days


def _slice_last_sessions(df: pd.DataFrame, sessions: int) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    days = _session_days(pd.DatetimeIndex(df.index))
    keep_days = set(days[-max(1, sessions) :])
    mask = [((t.date() if hasattr(t, "date") else pd.Timestamp(t).date()) in keep_days) for t in df.index]
    tail = df.iloc[[i for i, m in enumerate(mask) if m]]
    markers: List[Dict[str, Any]] = []
    prev = None
    for ts in tail.index:
        d = ts.date() if hasattr(ts, "date") else pd.Timestamp(ts).date()
        if d != prev:
            markers.append({
                "time": int(pd.Timestamp(ts).timestamp()),
                "position": "belowBar",
                "color": "#94a3b8",
                "shape": "arrowUp",
                "text": str(d)[5:],
            })
            prev = d
    return tail, markers


def _title_for(fam: str, lvl: Dict[str, Any]) -> str:
    st = STYLE.get(fam) or {"label": fam}
    code = str(lvl.get("code") or "")
    pretty = {
        "or_high": "high",
        "or_low": "low",
        "prior_high": "high",
        "prior_low": "low",
        "session_vwap": "",
        "session_tp_mean": "TP",
        "bb_mid": "mid",
        "bb_upper": "up",
        "bb_lower": "lo",
        "donchian_20_high": "20H",
        "donchian_20_low": "20L",
        "pivot": "P",
        "tc": "TC",
        "bc": "BC",
        "r1": "R1",
        "s1": "S1",
        "r2": "R2",
        "s2": "S2",
        "ema_9": "9",
        "ema_20": "20",
        "ema_50": "50",
    }.get(code)
    if pretty is None:
        if code.startswith("fib_"):
            pretty = code.replace("fib_", "").replace("_", ".")
        elif code.startswith("round_"):
            return f"Rnd {int(float(lvl.get('price') or 0))}"
        elif code.startswith("ema_"):
            pretty = code.replace("ema_", "")
        else:
            pretty = code.replace("_", " ")
    role = str(lvl.get("role") or "")
    if fam == "swing_sr":
        return f"Swing {role[:3]}".strip()
    return f"{st['label']} {pretty}".strip()


def _decorate(lvl: Dict[str, Any], *, confidence: str) -> Dict[str, Any]:
    fam = str(lvl.get("family") or "")
    st = STYLE.get(fam) or {"color": "#64748b", "lineStyle": 1, "lineWidth": 1, "label": fam}
    return {
        **lvl,
        "confidence": confidence,
        "draw": True,
        "title": _title_for(fam, lvl),
        "group": "proven" if fam in PROVEN_FAMILIES else "desk",
        "style": {
            "color": st["color"],
            "lineStyle": st["lineStyle"],
            "lineWidth": st["lineWidth"],
        },
    }


def _pick_levels(raw: Sequence[Dict[str, Any]], price: float) -> List[Dict[str, Any]]:
    by_fam: Dict[str, List[Dict[str, Any]]] = {f: [] for f in ALL_LEVEL_FAMILIES}
    for lvl in raw:
        fam = str(lvl.get("family") or "")
        if fam in by_fam:
            by_fam[fam].append(lvl)

    out: List[Dict[str, Any]] = []

    for fam in ("opening_range", "prior_day", "vwap"):
        conf = "proven_for_ui" if fam == "opening_range" else (
            "watchlist" if fam in PROVEN_FAMILIES else "desk_visual"
        )
        for lvl in by_fam.get(fam) or []:
            # Skip flat EMA-as-level when we also draw series (keep last print only if no series)
            out.append(_decorate(lvl, confidence=conf))

    swings = sorted(
        by_fam.get("swing_sr") or [],
        key=lambda L: abs(float(L.get("price") or 0) - price),
    )[:MAX_SWING]
    for lvl in swings:
        out.append(_decorate(lvl, confidence="watchlist"))

    rounds = sorted(
        by_fam.get("round_number") or [],
        key=lambda L: abs(float(L.get("price") or 0) - price),
    )[:MAX_ROUND]
    for lvl in rounds:
        out.append(_decorate(lvl, confidence="watchlist"))

    fibs = sorted(
        by_fam.get("fibonacci") or [],
        key=lambda L: abs(float(L.get("price") or 0) - price),
    )[:MAX_FIB]
    for lvl in fibs:
        out.append(_decorate(lvl, confidence="desk_visual"))

    # CPR: pivot + nearest bands (skip far R2/S2 clutter if many)
    cprs = by_fam.get("cpr") or []
    prefer = {"pivot", "tc", "bc", "r1", "s1"}
    cpr_keep = [L for L in cprs if str(L.get("code")) in prefer][:MAX_CPR]
    if not cpr_keep:
        cpr_keep = sorted(cprs, key=lambda L: abs(float(L.get("price") or 0) - price))[:MAX_CPR]
    for lvl in cpr_keep:
        out.append(_decorate(lvl, confidence="desk_visual"))

    for fam in ("bollinger", "donchian"):
        for lvl in by_fam.get(fam) or []:
            out.append(_decorate(lvl, confidence="desk_visual"))

    # EMA last-print levels skipped — drawn as series instead
    return out


def _series_payload(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for key, pts in (raw or {}).items():
        st = SERIES_STYLE.get(key)
        if not st or not pts:
            continue
        out.append({
            "id": key,
            "family": "ema" if key.startswith("ema") else ("bollinger" if key.startswith("bb") else "vwap"),
            "title": st["title"],
            "group": "desk",
            "confidence": "desk_visual",
            "style": {
                "color": st["color"],
                "lineWidth": st.get("lineWidth", 1),
                "lineStyle": st.get("lineStyle", 0),
            },
            "points": pts,
        })
    return out


def _norm_interval(interval: str) -> str:
    iv = str(interval or "15minute").strip().lower()
    if iv in ("minute", "1m", "1minute"):
        return "minute"
    if iv in ("5minute", "5m"):
        return "5minute"
    return "15minute"


def build_pack_from_frame(
    df: pd.DataFrame,
    *,
    symbol: str,
    sessions: int = 15,
    source: str = "tape",
    interval: str = "15minute",
) -> Dict[str, Any]:
    iv = _norm_interval(interval)
    or_bars = int(OR_BARS_BY_INTERVAL.get(iv, 1))
    work = _norm(df)
    if work is None or len(work) < 20:
        return {
            "available": False,
            "symbol": symbol,
            "interval": iv,
            "error": f"not enough {iv} bars",
            "candles": [],
            "overlays": [],
            "series": [],
            "patterns": [],
            "trendlines": [],
            "research_only": True,
            "listable_calls": False,
        }
    tail, session_markers = _slice_last_sessions(work, sessions)
    lookback = min(len(tail), 800 if iv == "minute" else 400)
    pack = overlays.build_overlays(tail, lookback=lookback, or_bars=or_bars)
    price = float((pack.get("indicators") or {}).get("price") or tail["Close"].iloc[-1])
    levels = _pick_levels(pack.get("levels") or [], price)
    series = _series_payload(pack.get("series") or {})
    patterns = list(pack.get("patterns") or [])
    trendlines = pack.get("trendlines") or []
    # HL/LH stack is tuned for 15m — skip on 1m/5m to avoid noise
    if iv == "15minute":
        try:
            import fno_hl_lh_stack

            hl_pats = fno_hl_lh_stack.chart_patterns(tail, max_keep=12)
            if hl_pats:
                patterns.extend(hl_pats)
        except Exception:
            pass
    for pat in patterns:
        neck = pat.get("neckline")
        if neck is None:
            continue
        levels.append({
            "family": "pattern",
            "code": f"{pat.get('code')}_neck",
            "price": float(neck),
            "role": "resistance" if pat.get("code") == "W" else "support",
            "confidence": "desk_visual",
            "draw": True,
            "group": "pattern",
            "title": f"{pat.get('code')} neck",
            "style": {
                "color": pat.get("color") or "#64748b",
                "lineStyle": 2,
                "lineWidth": 1,
            },
            "meta": {"hint": pat.get("hint")},
        })
    candles = []
    for ts, row in tail.iterrows():
        candles.append({
            "time": int(pd.Timestamp(ts).timestamp()),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
        })
    fams = sorted({L["family"] for L in levels} | {s["family"] for s in series})
    if patterns:
        fams = sorted(set(fams) | {"pattern"})
    if trendlines:
        fams = sorted(set(fams) | {"trendline"})
    return {
        "available": True,
        "symbol": symbol,
        "interval": iv,
        "or_bars": or_bars,
        "sessions": sessions,
        "source": source,
        "research_only": True,
        "research_only_calls": True,
        "listable_calls": False,
        "candles": candles,
        "overlays": levels,
        "series": series,
        "patterns": patterns,
        "trendlines": trendlines,
        "session_markers": session_markers,
        "indicators": pack.get("indicators") or {},
        "families_drawn": fams,
        "note": (
            f"{iv} desk overlays (OR≈15m wall-clock / swing S/R / prior / round + "
            "Fib/EMA/VWAP/BB + patterns). Visual only — not Calls."
        ),
    }


def build_pack(symbol: str, *, n_bars: int = 120, sessions: Optional[int] = None) -> Dict[str, Any]:
    path = TAPE[symbol]
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    if sessions is None:
        sessions = max(1, int(round(n_bars / 25.0)))
    return build_pack_from_frame(
        df, symbol=symbol, sessions=sessions, source=path.name, interval="15minute"
    )


def build_live_pack(
    symbol: str,
    *,
    sessions: Optional[int] = None,
    interval: str = "15minute",
) -> Dict[str, Any]:
    """Prefer live Kite for interval; fall back to local tape when available."""
    key = str(symbol or "").upper()
    iv = _norm_interval(interval)
    if sessions is None:
        sessions = int(DEFAULT_SESSIONS.get(iv, 15))
    sessions = max(1, min(int(sessions), 30 if iv == "15minute" else 15))
    bars_per_day = 375 if iv == "minute" else (75 if iv == "5minute" else 25)
    days = max(sessions + 5, 12)
    limit = max(sessions * bars_per_day, 120)
    kite_iv = "minute" if iv == "minute" else iv
    try:
        import kite_data

        if kite_data.kite_enabled():
            day_cap = 10 if iv == "minute" else (30 if iv == "5minute" else 60)
            df, err = kite_data.fetch_historical_candles(
                key, interval=kite_iv, days=min(days, day_cap), keep_partial=True
            )
            if err is None and df is not None and len(df) >= 20:
                return build_pack_from_frame(
                    df.tail(limit),
                    symbol=key,
                    sessions=sessions,
                    source=f"kite_{iv}",
                    interval=iv,
                )
    except Exception:
        pass
    # Local fallbacks
    if iv == "15minute" and key in TAPE and TAPE[key].is_file():
        return build_pack(key, sessions=sessions)
    if iv == "minute" and key in TAPE_1M and TAPE_1M[key].is_file():
        df = pd.read_csv(TAPE_1M[key], index_col=0, parse_dates=True)
        return build_pack_from_frame(
            df.tail(limit),
            symbol=key,
            sessions=sessions,
            source=TAPE_1M[key].name,
            interval=iv,
        )
    return {
        "available": False,
        "symbol": key,
        "interval": iv,
        "error": f"no kite and no local {iv} tape",
        "candles": [],
        "overlays": [],
        "series": [],
        "patterns": [],
        "trendlines": [],
        "research_only": True,
        "listable_calls": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="NIFTY", choices=sorted(TAPE))
    ap.add_argument("--sessions", type=int, default=15)
    ap.add_argument("--bars", type=int, default=0, help="legacy; ignored if --sessions set")
    args = ap.parse_args()
    pack = build_pack(args.symbol.upper(), sessions=args.sessions)
    out = OUT_DIR / f"chart_pack_15m_{args.symbol.upper()}.json"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    print(
        f"wrote {out} candles={len(pack.get('candles') or [])} "
        f"overlays={len(pack.get('overlays') or [])} "
        f"series={len(pack.get('series') or [])} "
        f"patterns={len(pack.get('patterns') or [])} "
        f"trendlines={len(pack.get('trendlines') or [])} "
        f"sessions={args.sessions}"
    )
    print("families", pack.get("families_drawn"))


if __name__ == "__main__":
    main()
