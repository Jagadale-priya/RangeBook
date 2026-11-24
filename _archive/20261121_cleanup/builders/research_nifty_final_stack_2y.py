"""NIFTY final stack helpers — reconstructed for prod 1y confirm.

Provides `_prod2`, `_load_daily`, `_active_days`, `_union` used by
`live_final_1y_months_accurate` / dual_tf builders.
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("TELEGRAM_NOTIFY", "0")
os.environ.setdefault("WHATSAPP_NOTIFY", "0")
os.environ.setdefault("ENABLE_5M_CROWN", "1")
os.environ.setdefault("ENABLE_5M_CROWN_ALL", "0")
os.environ.setdefault("CROWN_BUILD_QUIET", "1")
warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

import fno_complete_call_report as base  # noqa: E402
import research_large_window_profit as large  # noqa: E402
import research_pdf_deep_algo as deep  # noqa: E402

OUT_DIR = ROOT / "stock_signal_data/fno_validate/research"
CANDS = OUT_DIR / "full12y_candidates.json"
DAILY = ROOT / "stock_signal_data/fno_validate/NIFTY_daily_5y_nse.csv"
if not DAILY.exists():
    DAILY = ROOT / "stock_signal_data/fno_validate/NIFTY_daily_nse.csv"
POOL_CACHE = OUT_DIR / "_cache_nifty_final_stack_2y_pools.json"

PRIORITY = {
    "proven_100": 0,
    "good_prod2": 1,
    "champion": 2,
    "crown_5m": 3,
}


def _hm_key(hm: Any) -> str:
    s = str(hm or "").strip()
    if not s:
        return ""
    # Full timestamp from candidates: "2025-10-24 11:15:00+05:30"
    if len(s) >= 16 and ("-" in s or "T" in s):
        try:
            return pd.Timestamp(s).strftime("%H:%M")
        except Exception:
            pass
    if ":" in s:
        parts = s.split(":")
        if len(parts) >= 2:
            return f"{parts[0][-2:].zfill(2)}:{parts[1][:2].zfill(2)}"
    return s.split(".")[0]


def _norm_row(c: dict, track: str) -> Optional[dict]:
    try:
        day = str(c.get("day") or "")[:10]
        if not day:
            return None
        o = c.get("outcome")
        win = c.get("win")
        if win is None:
            if o == "t1_before_sl":
                win = True
            elif o in ("sl_before_t1", "same_bar_both"):
                win = False
        pts = float(c.get("points") or 0)
        entry = float(c.get("entry") or c.get("entry_px") or 0)
        t1 = float(c.get("t1") or c.get("target") or 0)
        sl = float(c.get("sl") or c.get("stop") or 0)
        side = str(c.get("decision") or c.get("side") or "").upper()
        if "BUY" in side:
            side = "BUY"
        elif "SELL" in side:
            side = "SELL"
        p = float(c.get("p_t1") or c.get("p") or c.get("score") or 0)
        hm = _hm_key(c.get("hm") or c.get("time") or c.get("when") or "")
        return {
            "day": day,
            "decision": side,
            "hm": hm,
            "p_t1": p,
            "win": bool(win) if win is not None else None,
            "points": pts,
            "entry": entry,
            "t1": t1,
            "sl": sl,
            "outcome": o,
            "track": track,
            "priority": PRIORITY.get(track, 9),
        }
    except Exception:
        return None


def _load_daily() -> pd.DataFrame:
    d = pd.read_csv(DAILY)
    d["Date"] = pd.to_datetime(d["Date"])
    return d.sort_values("Date").reset_index(drop=True)


def _prior(daily: pd.DataFrame, day: str):
    prior = daily[daily["Date"] < pd.Timestamp(day)]
    if prior.empty:
        return None
    return prior.iloc[-1]


def _active_days(sessions: List[str], daily: pd.DataFrame) -> set:
    """HTF active: prior Volume >= P40 OR prior range% >= median (lookback feats)."""
    feats: List[Tuple[str, float, float]] = []
    for day in sessions:
        p = _prior(daily, day)
        if p is None:
            continue
        rng = (float(p["High"]) - float(p["Low"])) / float(p["Close"]) * 100.0
        feats.append((day, float(p["Volume"]), rng))
    if not feats:
        return set(sessions)
    vols = pd.Series([f[1] for f in feats])
    rngs = pd.Series([f[2] for f in feats])
    vcut = float(vols.quantile(0.4))
    rcut = float(rngs.median())
    return {d for d, v, r in feats if v >= vcut or r >= rcut}


def _prod2(days_back: int = 1400):
    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    cands = raw if isinstance(raw, list) else (raw.get("candidates") or [])
    for c in cands:
        day = str(c.get("day") or "")
        c["day"] = day[:10] if day else ""
    days = sorted({c["day"] for c in cands if c.get("day")})
    if not days:
        return [], [], ""
    last = datetime.strptime(days[-1], "%Y-%m-%d").date()
    cut = (last - timedelta(days=int(days_back))).isoformat()
    day_list = [d for d in days if d >= cut]
    day_set = set(day_list)
    scoped = [c for c in cands if c.get("day") in day_set]
    picked = deep._pick(scoped, large._issued, max_n=2)
    rows: List[dict] = []
    for c in picked:
        r = _norm_row(c, "good_prod2")
        if r:
            rows.append(r)
    return day_list, rows, days[-1]


def _union(tracks: Dict[str, List[dict]], day_cap: int = 2) -> List[dict]:
    by_day: Dict[str, List[dict]] = defaultdict(list)
    for rows in tracks.values():
        for r in rows:
            by_day[r["day"]].append(dict(r))
    out: List[dict] = []
    for day in sorted(by_day):
        cands = sorted(
            by_day[day],
            key=lambda r: (
                int(r.get("priority", 9)),
                -float(r.get("p_t1") or 0),
                str(r.get("hm") or ""),
            ),
        )
        picked: List[dict] = []
        for r in cands:
            if len(picked) >= day_cap:
                break
            k2 = (r["day"], r.get("decision"), r.get("hm"))
            if any((x["day"], x.get("decision"), x.get("hm")) == k2 for x in picked):
                continue
            if any(str(x.get("decision")) != str(r.get("decision")) for x in picked):
                continue
            picked.append(r)
        out.extend(picked)
    return out


def _agg(rows: List[dict], sessions: Optional[List[str]] = None) -> Dict[str, Any]:
    if not rows:
        return {"n": 0, "hit_pct": None, "wins": 0, "losses": 0, "points": 0.0, "by_track": {}}
    wins = sum(1 for r in rows if r.get("win"))
    n = len(rows)
    by_tr: Dict[str, List] = defaultdict(list)
    for r in rows:
        by_tr[str(r.get("track") or "?")].append(r)
    return {
        "n": n,
        "hit_pct": round(100.0 * wins / n, 2),
        "wins": wins,
        "losses": n - wins,
        "points": round(sum(float(r.get("points") or 0) for r in rows), 1),
        "by_track": {
            k: {
                "n": len(rs),
                "hit_pct": round(100.0 * sum(1 for r in rs if r.get("win")) / len(rs), 2),
            }
            for k, rs in by_tr.items()
        },
    }
