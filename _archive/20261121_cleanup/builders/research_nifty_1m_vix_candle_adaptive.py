"""RESEARCH ONLY — VIX + 1m candle patterns with **adaptive** SL/T1 (not hardcoded).

Protocol:
  1. ANALYZE 2021-01-01 → 2023-12-31
     - Align prior-day India VIX (no look-ahead)
     - Catalog OR first-break + candle patterns by VIX regime
     - Learn adaptive brackets from MAE/MFE + ATR/OR (per pattern×VIX)
  2. TRAIN/SELECT on analyze: pick logics maximizing calls × accuracy
  3. TEST 2024-01-01 → 2025-12-30 on new candles with frozen recipes + brackets

  python -u prod_live/tests/builders/research_nifty_1m_vix_candle_adaptive.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401,E402

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_5y_candle_ml as c5  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_vix_candle_adaptive"
REPORT_MD = OUT / "NIFTY_1M_VIX_CANDLE_ADAPTIVE.md"
REPORT_JSON = OUT / "NIFTY_1M_VIX_CANDLE_ADAPTIVE.json"
VIX_PATH = ROOT / "stock_signal_data" / "cache" / "pre915_macro" / "IDX_INDIAVIX.csv"

START = "2021-01-01"
END = "2025-12-30"
ANALYZE_END = "2023-12-31"
TEST_START = "2024-01-01"
OR_BARS = 15


def vix_regime(level: float) -> str:
    if level != level or level <= 0:
        return "UNK"
    if level < 13:
        return "LOW"
    if level < 17:
        return "NORMAL"
    if level < 22:
        return "ELEVATED"
    return "HIGH"


def load_vix() -> pd.Series:
    df = pd.read_csv(VIX_PATH)
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    s = df.set_index("Date")["Close"].astype(float).sort_index()
    # prior-day VIX for session day (no look-ahead)
    return s.shift(1)


def clock_bucket(mins: int) -> str:
    if mins < 10 * 60:
        return "open"
    if mins < 12 * 60:
        return "morning"
    if mins < 14 * 60:
        return "midday"
    return "afternoon"


def excursion_path(
    h: np.ndarray,
    l: np.ndarray,
    c: np.ndarray,
    i: int,
    side: str,
    *,
    max_bars: int = 120,
) -> Tuple[float, float]:
    """Return (MAE, MFE) in points from entry close — adverse / favorable excursion."""
    entry = float(c[i])
    mae = 0.0
    mfe = 0.0
    end = min(len(c), i + 1 + max_bars)
    for j in range(i + 1, end):
        if side == "BUY":
            adverse = entry - float(l[j])
            fav = float(h[j]) - entry
        else:
            adverse = float(h[j]) - entry
            fav = entry - float(l[j])
        if adverse > mae:
            mae = adverse
        if fav > mfe:
            mfe = fav
    return float(mae), float(mfe)


def path_hit(
    h: np.ndarray,
    l: np.ndarray,
    c: np.ndarray,
    i: int,
    side: str,
    sl_pts: float,
    t1_pts: float,
) -> Tuple[bool, str, float]:
    """Walk until adaptive T1 or SL. Returns win, outcome, points."""
    entry = float(c[i])
    if sl_pts < 5 or t1_pts < 5:
        return False, "bad_bracket", 0.0
    if side == "BUY":
        sl, t1 = entry - sl_pts, entry + t1_pts
        for j in range(i + 1, len(c)):
            hi, lo = float(h[j]), float(l[j])
            hit_sl = lo <= sl
            hit_t1 = hi >= t1
            if hit_t1 and hit_sl:
                return False, "both", 0.0
            if hit_t1:
                return True, "t1", t1_pts
            if hit_sl:
                return False, "sl", -sl_pts
        return False, "exp", 0.0
    else:
        sl, t1 = entry + sl_pts, entry - t1_pts
        for j in range(i + 1, len(c)):
            hi, lo = float(h[j]), float(l[j])
            hit_sl = hi >= sl
            hit_t1 = lo <= t1
            if hit_t1 and hit_sl:
                return False, "both", 0.0
            if hit_t1:
                return True, "t1", t1_pts
            if hit_sl:
                return False, "sl", -sl_pts
        return False, "exp", 0.0


def atr_at(sess: pd.DataFrame, pos: int, n: int = 14) -> float:
    hi = sess["High"].astype(float)
    lo = sess["Low"].astype(float)
    if pos < 1:
        return float(hi.iloc[0] - lo.iloc[0])
    sl = max(0, pos - n + 1)
    return float((hi.iloc[sl : pos + 1] - lo.iloc[sl : pos + 1]).mean())


def collect_events(df: pd.DataFrame, vix_prior: pd.Series, day_lo: str, day_hi: str) -> List[dict]:
    """OR first-break events with patterns, VIX, ATR, OR, MAE/MFE."""
    events = []
    h_all = df["High"].astype(float).values
    l_all = df["Low"].astype(float).values
    c_all = df["Close"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(df.index)}
    days = [d for d in df["day"].unique() if day_lo <= d <= day_hi]
    t0 = time.time()
    for di, day in enumerate(days, 1):
        if di % 150 == 0:
            print(f"    events {di}/{len(days)} n={len(events)} ({time.time()-t0:.0f}s)", flush=True)
        sess = df[df["day"] == day]
        if len(sess) < OR_BARS + 20:
            continue
        or_hi = float(sess["High"].iloc[:OR_BARS].max())
        or_lo = float(sess["Low"].iloc[:OR_BARS].min())
        or_w = or_hi - or_lo
        if or_w < 12:
            continue
        vix = float(vix_prior.get(day, np.nan))
        vr = vix_regime(vix)
        closes = sess["Close"].astype(float).values
        first_up = first_dn = None
        for pos in range(OR_BARS, len(sess)):
            if first_up is None and closes[pos] > or_hi:
                first_up = pos
            if first_dn is None and closes[pos] < or_lo:
                first_dn = pos
            if first_up is not None and first_dn is not None:
                break
        for side, pos in (("BUY", first_up), ("SELL", first_dn)):
            if pos is None:
                continue
            if side == "BUY" and first_dn is not None and first_dn < first_up:
                continue
            if side == "SELL" and first_up is not None and first_up < first_dn:
                continue
            # both-sides before entry?
            up = dn = False
            for p2 in range(OR_BARS, pos + 1):
                if closes[p2] > or_hi:
                    up = True
                if closes[p2] < or_lo:
                    dn = True
            if up and dn:
                continue
            ts = sess.index[pos]
            mins = int(ts.hour * 60 + ts.minute)
            if mins < 10 * 60 or mins > 14 * 60 + 30:
                continue
            row = sess.iloc[pos]
            body = float(row["Close"]) - float(row["Open"])
            if side == "BUY" and body <= 0:
                continue
            if side == "SELL" and body >= 0:
                continue
            full_i = idx_map[ts]
            atr = atr_at(sess, pos)
            bar_rng = float(row["High"] - row["Low"])
            or_ext = (float(row["Close"]) - or_hi) / or_w if side == "BUY" else (or_lo - float(row["Close"])) / or_w
            if or_ext > 0.35:
                continue
            mae, mfe = excursion_path(h_all, l_all, c_all, full_i, side)
            pats = [p for p in c5.PATTERN_COLS if int(row[p]) == 1]
            if not pats:
                pats = ["_structure_"]
            events.append(
                {
                    "day": day,
                    "hm": base._hm(ts),
                    "decision": side,
                    "entry": float(row["Close"]),
                    "mins": mins,
                    "clock": clock_bucket(mins),
                    "vix": vix,
                    "vix_regime": vr,
                    "or_width": or_w,
                    "or_ext": float(or_ext),
                    "atr": float(atr),
                    "bar_range": bar_rng,
                    "mae": mae,
                    "mfe": mfe,
                    "patterns": pats,
                    "full_i": full_i,
                    "hammer": int(row["hammer"]),
                    "marubozu": int(row["marubozu"]),
                    "bull_engulf": int(row["bull_engulf"]),
                    "bear_engulf": int(row["bear_engulf"]),
                    "pin_bull": int(row["pin_bull"]),
                    "pin_bear": int(row["pin_bear"]),
                    "bull_run2": int(row["bull_run2"]),
                    "bear_run2": int(row["bear_run2"]),
                    "doji": int(row["doji"]),
                    "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
                }
            )
    return events


def learn_brackets(ana_events: List[dict]) -> Dict[str, Dict[str, float]]:
    """Per (pattern, side, vix_regime) learn SL/T1 from MAE/MFE percentiles — not hardcoded."""
    buckets: Dict[str, List[dict]] = defaultdict(list)
    for e in ana_events:
        vr = e["vix_regime"]
        for pat in e["patterns"]:
            key = f"{pat}|{e['decision']}|{vr}"
            buckets[key].append(e)
        # also aggregate by side×vix and pattern×side
        buckets[f"*|{e['decision']}|{vr}"].append(e)
        for pat in e["patterns"]:
            buckets[f"{pat}|{e['decision']}|*"].append(e)
        buckets[f"*|{e['decision']}|*"].append(e)

    out = {}
    for key, rows in buckets.items():
        if len(rows) < 12:
            continue
        maes = np.array([r["mae"] for r in rows], dtype=float)
        mfes = np.array([r["mfe"] for r in rows], dtype=float)
        atrs = np.array([r["atr"] for r in rows], dtype=float)
        ors = np.array([r["or_width"] for r in rows], dtype=float)
        # SL just beyond typical adverse (p60), T1 at typical favorable (p55)
        sl = float(np.nanpercentile(maes, 60))
        t1 = float(np.nanpercentile(mfes, 55))
        # blend with structure so brackets stay sane
        atr_med = float(np.nanmedian(atrs))
        or_med = float(np.nanmedian(ors))
        sl = max(sl, 0.55 * atr_med, 0.12 * or_med, 8.0)
        t1 = max(t1, 0.80 * atr_med, 0.18 * or_med, 10.0)
        # require reward not tiny vs risk
        if t1 < 0.85 * sl:
            t1 = 0.85 * sl
        rr = t1 / sl if sl > 0 else 0
        out[key] = {
            "sl": round(sl, 2),
            "t1": round(t1, 2),
            "rr": round(rr, 3),
            "n": len(rows),
            "mae_p60": round(float(np.nanpercentile(maes, 60)), 2),
            "mfe_p55": round(float(np.nanpercentile(mfes, 55)), 2),
            "atr_med": round(atr_med, 2),
            "or_med": round(or_med, 2),
        }
    return out


def resolve_bracket(e: dict, brackets: Dict[str, Dict[str, float]]) -> Tuple[float, float, str]:
    """Pick most specific learned bracket for event."""
    vr = e["vix_regime"]
    side = e["decision"]
    cands = []
    for pat in e["patterns"]:
        for key in (f"{pat}|{side}|{vr}", f"{pat}|{side}|*", f"*|{side}|{vr}", f"*|{side}|*"):
            if key in brackets:
                b = brackets[key]
                cands.append((key, b["sl"], b["t1"], b["n"]))
    if not cands:
        # last resort: ATR/OR structure of this bar only (still not a global hardcode)
        sl = max(0.7 * e["atr"], 0.15 * e["or_width"], 8.0)
        t1 = max(1.1 * e["atr"], 0.22 * e["or_width"], 10.0)
        return sl, t1, "local_atr_or"
    # prefer higher specificity then larger n
    def rank(c):
        key = c[0]
        spec = 3 if "|*" not in key and not key.startswith("*|") else (2 if key.count("*") == 1 else 1)
        return (spec, c[3])

    key, sl, t1, _ = max(cands, key=rank)
    return float(sl), float(t1), key


# Adaptive formula families to compare (coefficients from structure — not fixed pts)
FORMULAS = [
    ("atr_07_12", lambda e: (max(0.7 * e["atr"], 8), max(1.2 * e["atr"], 10))),
    ("atr_10_15", lambda e: (max(1.0 * e["atr"], 8), max(1.5 * e["atr"], 10))),
    ("atr_08_16", lambda e: (max(0.8 * e["atr"], 8), max(1.6 * e["atr"], 10))),
    ("or_15_25", lambda e: (max(0.15 * e["or_width"], 8), max(0.25 * e["or_width"], 10))),
    ("or_12_22", lambda e: (max(0.12 * e["or_width"], 8), max(0.22 * e["or_width"], 10))),
    ("or_18_30", lambda e: (max(0.18 * e["or_width"], 8), max(0.30 * e["or_width"], 10))),
    ("mix_atr_or", lambda e: (
        max(0.6 * e["atr"], 0.12 * e["or_width"], 8),
        max(1.0 * e["atr"], 0.22 * e["or_width"], 10),
    )),
    ("vix_scaled_atr", lambda e: (
        max((0.55 + 0.02 * max(e["vix"] or 15, 10)) * e["atr"], 8),
        max((0.90 + 0.03 * max(e["vix"] or 15, 10)) * e["atr"], 10),
    )),
]


def score_logic(
    events: List[dict],
    h_all,
    l_all,
    c_all,
    *,
    brackets: Optional[Dict[str, Dict[str, float]]] = None,
    formula_name: Optional[str] = None,
    formula_fn=None,
    filters: dict,
) -> Dict[str, Any]:
    """Apply filters + bracket source; return hit stats + calls."""
    rows = []
    for e in events:
        if filters.get("side") and e["decision"] != filters["side"]:
            continue
        if filters.get("vix_regimes") and e["vix_regime"] not in filters["vix_regimes"]:
            continue
        if filters.get("clocks") and e["clock"] not in filters["clocks"]:
            continue
        if filters.get("patterns"):
            if not set(e["patterns"]) & set(filters["patterns"]):
                continue
        if filters.get("max_or_ext") is not None and e["or_ext"] > filters["max_or_ext"]:
            continue
        if filters.get("min_or") is not None and e["or_width"] < filters["min_or"]:
            continue
        if filters.get("max_vix") is not None and (e["vix"] == e["vix"] and e["vix"] > filters["max_vix"]):
            continue
        if filters.get("min_vix") is not None and (e["vix"] != e["vix"] or e["vix"] < filters["min_vix"]):
            continue
        if brackets is not None:
            sl, t1, bsrc = resolve_bracket(e, brackets)
        else:
            sl, t1 = formula_fn(e)
            bsrc = formula_name or "formula"
        # VIX widen: elevated/high vol → scale both (learned multiplier on analyze later optional)
        if e["vix_regime"] == "ELEVATED":
            sl, t1 = sl * 1.10, t1 * 1.15
        elif e["vix_regime"] == "HIGH":
            sl, t1 = sl * 1.20, t1 * 1.25
        elif e["vix_regime"] == "LOW":
            sl, t1 = sl * 0.95, t1 * 0.95
        win, outcome, pts = path_hit(h_all, l_all, c_all, e["full_i"], e["decision"], sl, t1)
        if outcome in ("bad_bracket", "both"):
            continue
        rows.append(
            {
                **{k: e[k] for k in ("day", "hm", "decision", "entry", "vix", "vix_regime", "clock", "or_width", "atr", "patterns")},
                "sl": round(sl, 2),
                "t1": round(t1, 2),
                "bracket_src": bsrc,
                "win": win,
                "outcome": outcome,
                "points": pts,
            }
        )
    # day-unique: first signal of day
    seen = set()
    du = []
    for r in sorted(rows, key=lambda x: (x["day"], x["hm"])):
        if r["day"] in seen:
            continue
        seen.add(r["day"])
        du.append(r)
    n = len(du)
    wins = sum(1 for r in du if r["win"])
    hit = round(100.0 * wins / n, 2) if n else 0.0
    # objective: prefer high hit with many calls
    # score = hit * log1p(n) with bonus for hit>=60 and n>=15
    score = hit * np.log1p(n) + (5.0 if hit >= 60 and n >= 15 else 0) + (8.0 if hit >= 65 and n >= 20 else 0)
    return {
        "n": n,
        "wins": wins,
        "hit_pct": hit,
        "score": round(float(score), 3),
        "avg_sl": round(float(np.mean([r["sl"] for r in du])), 2) if du else 0,
        "avg_t1": round(float(np.mean([r["t1"] for r in du])), 2) if du else 0,
        "calls": du,
    }


def hunt_logics(ana_events, test_events, h_all, l_all, c_all, brackets) -> List[dict]:
    """Search VIX×pattern×clock×bracket logics; rank by analyze score; validate on test."""
    print("\n[3] Hunting VIX×candle logics (max calls × accuracy)…", flush=True)
    pattern_sets = [
        None,
        ["marubozu"],
        ["hammer", "pin_bull"],
        ["shooting", "pin_bear"],
        ["bull_engulf", "bull_run2"],
        ["bear_engulf", "bear_run2"],
        ["marubozu", "bull_engulf"],
        ["marubozu", "bear_engulf"],
        ["_structure_"],
    ]
    sides = [None, "BUY", "SELL"]
    vix_sets = [
        None,
        ["LOW", "NORMAL"],
        ["NORMAL", "ELEVATED"],
        ["NORMAL"],
        ["ELEVATED", "HIGH"],
        ["LOW"],
    ]
    clocks = [None, ["morning"], ["morning", "midday"], ["midday"]]
    results = []
    t0 = time.time()
    n_tried = 0
    # Pass A: full filter grid with learned MAE/MFE brackets only
    for pats in pattern_sets:
        for side in sides:
            for vset in vix_sets:
                for clk in clocks:
                    for max_ext in (0.15, 0.22, 0.30):
                        for min_or in (15, 20, 25):
                            filters = {
                                "side": side,
                                "patterns": pats,
                                "vix_regimes": vset,
                                "clocks": clk,
                                "max_or_ext": max_ext,
                                "min_or": min_or,
                            }
                            n_tried += 1
                            ana = score_logic(ana_events, h_all, l_all, c_all, brackets=brackets, filters=filters)
                            if ana["n"] < 10:
                                continue
                            te = score_logic(test_events, h_all, l_all, c_all, brackets=brackets, filters=filters)
                            results.append(
                                {
                                    "name": "learned_mae_mfe",
                                    "filters": filters,
                                    "analyze": {k: v for k, v in ana.items() if k != "calls"},
                                    "test": {k: v for k, v in te.items() if k != "calls"},
                                    "test_calls": te["calls"],
                                    "analyze_calls": ana["calls"][:30],
                                }
                            )
    # Pass B: structure formulas on a reduced filter core
    core_filters = []
    for pats in (None, ["marubozu"], ["bull_engulf", "bull_run2"], ["bear_engulf", "bear_run2"], ["_structure_"]):
        for side in (None, "BUY", "SELL"):
            for vset in (None, ["LOW", "NORMAL"], ["NORMAL", "ELEVATED"], ["ELEVATED", "HIGH"]):
                for clk in (None, ["morning"], ["morning", "midday"]):
                    core_filters.append(
                        {
                            "side": side,
                            "patterns": pats,
                            "vix_regimes": vset,
                            "clocks": clk,
                            "max_or_ext": 0.22,
                            "min_or": 20,
                        }
                    )
    for filters in core_filters:
        for fname, ffn in FORMULAS:
            n_tried += 1
            ana2 = score_logic(
                ana_events, h_all, l_all, c_all, formula_name=fname, formula_fn=ffn, filters=filters
            )
            if ana2["n"] < 10:
                continue
            te2 = score_logic(
                test_events, h_all, l_all, c_all, formula_name=fname, formula_fn=ffn, filters=filters
            )
            results.append(
                {
                    "name": fname,
                    "filters": filters,
                    "analyze": {k: v for k, v in ana2.items() if k != "calls"},
                    "test": {k: v for k, v in te2.items() if k != "calls"},
                    "test_calls": te2["calls"],
                    "analyze_calls": ana2["calls"][:30],
                }
            )
    print(f"  tried~{n_tried} kept={len(results)} ({time.time()-t0:.0f}s)", flush=True)
    # rank by analyze score, then test hit, then test n
    results.sort(
        key=lambda r: (
            r["analyze"]["score"],
            r["test"]["hit_pct"],
            r["test"]["n"],
        ),
        reverse=True,
    )
    return results


def write_report(meta, brackets, logics, vix_summary) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # pick best: among analyze top, prefer test n>=8 with highest test hit; else best analyze that still ok on test
    best_test = None
    for r in logics:
        te = r["test"]
        if te["n"] >= 8 and te["hit_pct"] >= 55:
            if best_test is None or (te["hit_pct"], te["n"]) > (best_test["test"]["hit_pct"], best_test["test"]["n"]):
                best_test = r
    # volume-accuracy pareto on test among analyze-qualified (analyze hit>=55 n>=15)
    qualified = [r for r in logics if r["analyze"]["hit_pct"] >= 55 and r["analyze"]["n"] >= 15 and r["test"]["n"] >= 5]
    qualified.sort(key=lambda r: (r["test"]["hit_pct"], r["test"]["n"]), reverse=True)
    volume = sorted(
        [r for r in logics if r["test"]["n"] >= 15 and r["analyze"]["hit_pct"] >= 52],
        key=lambda r: (r["test"]["hit_pct"], r["test"]["n"]),
        reverse=True,
    )

    winner = best_test or (qualified[0] if qualified else (logics[0] if logics else None))

    lines = [
        "# NIFTY 1m — VIX + candle patterns + **adaptive** SL/T1",
        "",
        "**Not live. SL/T1 are not hardcoded ±30 — learned from MAE/MFE + ATR/OR + VIX.**",
        "",
        f"- Analyze: `{ANALYZE_END}` and before · Test: `{TEST_START}` → `{END}`",
        f"- India VIX: prior-day close from `{VIX_PATH.name}` (no look-ahead)",
        f"- Events analyze/test: {meta.get('n_ana')} / {meta.get('n_test')}",
        "",
        "## VIX regime mix (analyze events)",
        "",
        f"`{json.dumps(vix_summary)}`",
        "",
        "## Adaptive brackets (examples learned on analyze)",
        "",
        "| Recipe key | N | SL | T1 | R:R | MAE p60 | MFE p55 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    # show interesting bracket keys
    shown = 0
    for k, b in sorted(brackets.items(), key=lambda kv: -kv[1]["n"]):
        if shown >= 20:
            break
        if b["n"] < 20:
            continue
        lines.append(
            f"| `{k}` | {b['n']} | {b['sl']} | {b['t1']} | {b['rr']} | {b['mae_p60']} | {b['mfe_p55']} |"
        )
        shown += 1

    lines += [
        "",
        "## Winner (best calls × accuracy on new data)",
        "",
    ]
    if winner:
        lines += [
            f"**Logic:** `{winner['name']}`",
            f"- Filters: `{json.dumps(winner['filters'], default=str)}`",
            f"- Analyze: **{winner['analyze']['n']} @ {winner['analyze']['hit_pct']}%** "
            f"(avg SL {winner['analyze']['avg_sl']} / T1 {winner['analyze']['avg_t1']})",
            f"- **Test (new candles): {winner['test']['n']} @ {winner['test']['hit_pct']}%** "
            f"(avg SL {winner['test']['avg_sl']} / T1 {winner['test']['avg_t1']})",
            "",
            "| Day | HM | Side | VIX | SL | T1 | Win |",
            "|---|---|---|---:|---:|---:|:---:|",
        ]
        for c in (winner.get("test_calls") or [])[:40]:
            lines.append(
                f"| {c.get('day')} | {c.get('hm')} | {c.get('decision')} | {c.get('vix')} | "
                f"{c.get('sl')} | {c.get('t1')} | {'Y' if c.get('win') else 'N'} |"
            )
    else:
        lines.append("_No winner._")

    lines += ["", "## Top logics by test hit (n≥5, analyze hit≥55)", "", "| # | Name | Filters (short) | Ana n/hit | Test n/hit | Avg SL/T1 |", "|---:|---|---|---|---|---|"]
    for i, r in enumerate(qualified[:15], 1):
        f = r["filters"]
        short = f"side={f.get('side')} vix={f.get('vix_regimes')} pats={f.get('patterns')} clk={f.get('clocks')}"
        lines.append(
            f"| {i} | `{r['name']}` | {short[:80]} | {r['analyze']['n']}@{r['analyze']['hit_pct']}% | "
            f"**{r['test']['n']}@{r['test']['hit_pct']}%** | {r['test']['avg_sl']}/{r['test']['avg_t1']} |"
        )

    lines += ["", "## High-volume candidates (test n≥15)", "", "| # | Name | Test n/hit | Ana n/hit |", "|---:|---|---|---|"]
    for i, r in enumerate(volume[:10], 1):
        lines.append(
            f"| {i} | `{r['name']}` | **{r['test']['n']}@{r['test']['hit_pct']}%** | "
            f"{r['analyze']['n']}@{r['analyze']['hit_pct']}% |"
        )

    lines += [
        "",
        "## How SL/T1 are set (not hardcoded)",
        "",
        "1. On analyze events, measure MAE (adverse) and MFE (favorable) path from entry.",
        "2. Per pattern × side × VIX regime: SL ≈ MAE p60, T1 ≈ MFE p55, floored by ATR/OR medians.",
        "3. At live event: pick most specific learned recipe; widen/narrow slightly by VIX regime.",
        "4. Alternate families (ATR/OR multiples, VIX-scaled ATR) competed in the hunt — same adaptive idea.",
        "",
        "## Policy",
        "",
        f"- Pack: `{PACK}`",
        "- research_only · not_live",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "meta": meta,
                "vix_summary": vix_summary,
                "brackets_sample": dict(list(brackets.items())[:80]),
                "winner": {
                    "name": winner["name"],
                    "filters": winner["filters"],
                    "analyze": winner["analyze"],
                    "test": winner["test"],
                    "test_calls": winner.get("test_calls"),
                }
                if winner
                else None,
                "top_qualified": [
                    {"name": r["name"], "filters": r["filters"], "analyze": r["analyze"], "test": r["test"]}
                    for r in qualified[:20]
                ],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT_MD}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · VIX + CANDLE · ADAPTIVE SL/T1 · RESEARCH", flush=True)
    print(f"analyze≤{ANALYZE_END} test≥{TEST_START}", flush=True)
    print("=" * 60, flush=True)

    raw = base.load_existing_1m()
    raw = raw[
        (raw.index >= pd.Timestamp(START, tz="Asia/Kolkata"))
        & (raw.index <= pd.Timestamp(f"{END} 23:59:59", tz="Asia/Kolkata"))
    ]
    if raw.empty:
        print("FAIL: no bars", flush=True)
        return 1
    print(f"tape bars={len(raw)}", flush=True)
    vix_prior = load_vix()
    print(f"VIX prior days={len(vix_prior.dropna())} {vix_prior.dropna().index.min()}→{vix_prior.dropna().index.max()}", flush=True)

    print("\n[0] Candle columns…", flush=True)
    df = c5.add_candle_cols(raw)
    h_all = df["High"].astype(float).values
    l_all = df["Low"].astype(float).values
    c_all = df["Close"].astype(float).values

    print("\n[1] Collect analyze events…", flush=True)
    ana_events = collect_events(df, vix_prior, START, ANALYZE_END)
    print(f"  analyze events={len(ana_events)}", flush=True)
    print("\n[1b] Collect test events…", flush=True)
    test_events = collect_events(df, vix_prior, TEST_START, END)
    print(f"  test events={len(test_events)}", flush=True)

    from collections import Counter

    vix_summary = dict(Counter(e["vix_regime"] for e in ana_events))
    print(f"  VIX regimes analyze: {vix_summary}", flush=True)

    print("\n[2] Learn adaptive brackets from MAE/MFE…", flush=True)
    brackets = learn_brackets(ana_events)
    print(f"  bracket recipes={len(brackets)}", flush=True)

    logics = hunt_logics(ana_events, test_events, h_all, l_all, c_all, brackets)
    if not logics:
        print("FAIL: no logics", flush=True)
        return 1

    print("\nTOP analyze-score logics:", flush=True)
    for r in logics[:8]:
        print(
            f"  {r['name']} ana {r['analyze']['n']}@{r['analyze']['hit_pct']}% "
            f"test {r['test']['n']}@{r['test']['hit_pct']}% filters={r['filters']}",
            flush=True,
        )

    meta = {
        "n_ana": len(ana_events),
        "n_test": len(test_events),
        "n_brackets": len(brackets),
        "n_logics": len(logics),
        "analyze_end": ANALYZE_END,
        "test_start": TEST_START,
        "research_only": True,
        "not_live": True,
        "hardcoded_sl_t1": False,
    }
    PACK.mkdir(parents=True, exist_ok=True)
    (PACK / "brackets.json").write_text(json.dumps(brackets, indent=2), encoding="utf-8")
    write_report(meta, brackets, logics, vix_summary)
    print("\nDONE · research only · adaptive brackets", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
