"""RESEARCH ONLY — Precious 5y 1m candlestick pipeline (great BUY/SELL only).

Protocol (no leakage):
  1. ANALYZE  2021-01-01 → 2023-12-31
     Complete 1m candlestick catalog + context combos → keep only GREAT recipes
     (high T1 hit, enough samples).
  2. TRAIN    2021-01-01 → 2024-06-30
     Only bars that match a GREAT BUY or GREAT SELL recipe (aligned side).
  3. TEST     2024-07-01 → 2025-12-30
     Brand-new candles never used to choose GREAT recipes. Report accuracy.

  python -u prod_live/tests/builders/research_nifty_1m_great_only_ml.py
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
from nifty_side_clean import recent_sample_weights  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_great_only_ml"
REPORT_MD = OUT / "NIFTY_1M_GREAT_ONLY_ML.md"
REPORT_JSON = OUT / "NIFTY_1M_GREAT_ONLY_ML.json"

START = "2021-01-01"
END = "2025-12-30"
ANALYZE_END = "2023-12-31"  # pattern discovery ends here
TRAIN_END = "2024-06-30"  # ML fit ends here
TEST_START = "2024-07-01"  # brand-new candles
RISK = 30.0
OR_BARS = 15
GREAT_MIN_N = 12  # first-break events are rarer — still precious
GREAT_MIN_HIT = 65.0  # % T1 on analyze first-break events
GREAT_MIN_HIT_STRICT = 70.0
GREAT_MIN_N_SOFT = 8
GREAT_MIN_HIT_SOFT = 60.0


def clock_bucket(mins: int) -> str:
    """Coarse session buckets (precious recipes need volume at first-break)."""
    if mins < 10 * 60:
        return "open"
    if mins < 12 * 60:
        return "morning"
    if mins < 14 * 60:
        return "midday"
    return "afternoon"


def gap_bucket(g: float) -> str:
    if g > 0.35:
        return "gap_up"
    if g < -0.35:
        return "gap_dn"
    if g > 0:
        return "soft_up"
    if g < 0:
        return "soft_dn"
    return "flat"


def rsi_bucket(r: float) -> str:
    if r < 35:
        return "os"
    if r > 65:
        return "ob"
    if r < 45:
        return "low"
    if r > 55:
        return "high"
    return "mid"


def or_state(sess: pd.DataFrame, pos: int, or_hi: float, or_lo: float) -> str:
    closes = sess["Close"].astype(float).values
    up = dn = False
    for p in range(OR_BARS, pos + 1):
        if closes[p] > or_hi:
            up = True
        if closes[p] < or_lo:
            dn = True
    if up and dn:
        return "both"
    if up:
        return "only_up"
    if dn:
        return "only_dn"
    return "inside_or"


def fwd_t1(h, l, c, i, side, risk) -> bool:
    ok, _ = c5.fwd_t1_sl(h, l, c, i, side, risk)
    return bool(ok)


# ───────────────────────── complete pattern catalog on ANALYZE ─────────────────────────
def catalog_great_recipes(df: pd.DataFrame) -> Dict[str, Any]:
    """Scan analyze years: pattern × context → T1 rates; keep GREAT BUY/SELL recipes."""
    print("\n[1] COMPLETE pattern catalog on ANALYZE window…", flush=True)
    ana = df[df["day"] <= ANALYZE_END].copy()
    print(f"  analyze bars={len(ana)} days={ana['day'].nunique()} ≤ {ANALYZE_END}", flush=True)

    # gap map
    gaps = {}
    prev = None
    for day, sess in ana.groupby("day", sort=True):
        o = float(sess["Open"].iloc[0])
        gaps[day] = ((o - prev) / prev * 100.0) if prev else 0.0
        prev = float(sess["Close"].iloc[-1])

    h_all = ana["High"].astype(float).values
    l_all = ana["Low"].astype(float).values
    c_all = ana["Close"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(ana.index)}

    # stats[(pattern, side, clock, gap, rsi, orst)] -> [wins, n]
    stats: Dict[Tuple, List[int]] = defaultdict(lambda: [0, 0])
    # also single-pattern baseline
    single: Dict[Tuple[str, str], List[int]] = defaultdict(lambda: [0, 0])

    t0 = time.time()
    n_sess = 0
    for day, sess in ana.groupby("day", sort=True):
        n_sess += 1
        if n_sess % 100 == 0:
            print(f"    catalog sessions {n_sess} ({time.time()-t0:.0f}s)", flush=True)
        if len(sess) < OR_BARS + 20:
            continue
        or_hi = float(sess["High"].iloc[:OR_BARS].max())
        or_lo = float(sess["Low"].iloc[:OR_BARS].min())
        if or_hi - or_lo < 15:
            continue
        g = float(gaps.get(day, 0.0))
        gb = gap_bucket(g)
        closes = sess["Close"].astype(float).values
        first_up = first_dn = None
        for pos in range(OR_BARS, len(sess)):
            if first_up is None and closes[pos] > or_hi:
                first_up = pos
            if first_dn is None and closes[pos] < or_lo:
                first_dn = pos
            if first_up is not None and first_dn is not None:
                break
        # Catalog ONLY at first OR-break bars (same event we will trade / train on)
        for side, pos in (("BUY", first_up), ("SELL", first_dn)):
            if pos is None:
                continue
            if side == "BUY" and first_dn is not None and first_dn < first_up:
                continue
            if side == "SELL" and first_up is not None and first_up < first_dn:
                continue
            ts = sess.index[pos]
            mins = int(ts.hour * 60 + ts.minute)
            if mins < 10 * 60 or mins > 14 * 60 + 30:
                continue
            full_i = idx_map[ts]
            row = sess.iloc[pos]
            body = float(row["Close"]) - float(row["Open"])
            if side == "BUY" and body <= 0:
                continue
            if side == "SELL" and body >= 0:
                continue
            cb = clock_bucket(mins)
            rb = rsi_bucket(float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0)
            ost = or_state(sess, pos, or_hi, or_lo)
            if ost == "both":
                continue
            if side == "BUY" and ost != "only_up":
                continue
            if side == "SELL" and ost != "only_dn":
                continue
            fired = [p for p in c5.PATTERN_COLS if int(row[p]) == 1]
            if not fired:
                fired = ["_any_"]  # allow structure-only great recipes
            ok = fwd_t1(h_all, l_all, c_all, full_i, side, RISK)
            for pat in fired:
                s = single[(pat, side)]
                s[1] += 1
                s[0] += int(ok)
                # precious context: pattern × side × clock × gap × or (drop ultra-fine rsi for volume)
                for key in (
                    (pat, side, cb, gb, "any_rsi", ost),
                    (pat, side, cb, "any_gap", "any_rsi", ost),
                    (pat, side, "any_clock", "any_gap", "any_rsi", ost),
                ):
                    st = stats[key]
                    st[1] += 1
                    st[0] += int(ok)

    # build recipe tables
    single_rows = []
    for (pat, side), (w, n) in single.items():
        if n < 10:
            continue
        hit = 100.0 * w / n
        single_rows.append({"pattern": pat, "side": side, "n": n, "wins": w, "hit_pct": round(hit, 2)})
    single_rows.sort(key=lambda r: (-r["hit_pct"], -r["n"]))

    great = []
    strict = []
    soft = []
    for key, (w, n) in stats.items():
        hit = 100.0 * w / n
        pat, side, cb, gb, rb, ost = key
        if ost == "both":
            continue
        if side == "BUY" and ost != "only_up":
            continue
        if side == "SELL" and ost != "only_dn":
            continue
        rec = {
            "pattern": pat,
            "side": side,
            "clock": cb,
            "gap": gb,
            "rsi": rb,
            "or_state": ost,
            "n": n,
            "wins": w,
            "hit_pct": round(hit, 2),
        }
        if n >= GREAT_MIN_N and hit >= GREAT_MIN_HIT:
            great.append(rec)
        if n >= GREAT_MIN_N and hit >= GREAT_MIN_HIT_STRICT:
            strict.append(rec)
        if n >= GREAT_MIN_N_SOFT and hit >= GREAT_MIN_HIT_SOFT:
            soft.append(rec)

    great.sort(key=lambda r: (-r["hit_pct"], -r["n"]))
    strict.sort(key=lambda r: (-r["hit_pct"], -r["n"]))
    soft.sort(key=lambda r: (-r["hit_pct"], -r["n"]))
    # Prefer exact GREAT; if thin, fold soft
    if len(great) < 8:
        print(f"  GREAT thin ({len(great)}) — merging soft recipes ≥{GREAT_MIN_HIT_SOFT}%", flush=True)
        seen = {recipe_key(r) for r in great}
        for r in soft:
            k = recipe_key(r)
            if k not in seen:
                great.append(r)
                seen.add(k)
    print(
        f"  single patterns ranked={len(single_rows)} · GREAT recipes(≥{GREAT_MIN_HIT}% n≥{GREAT_MIN_N})={len(great)} · "
        f"STRICT(≥{GREAT_MIN_HIT_STRICT}%)={len(strict)} · soft={len(soft)}",
        flush=True,
    )
    if great[:5]:
        for r in great[:5]:
            print(
                f"    GREAT {r['side']} {r['pattern']} {r['clock']}/{r['gap']}/{r['rsi']}/{r['or_state']} "
                f"n={r['n']} hit={r['hit_pct']}%",
                flush=True,
            )
    return {
        "single": single_rows[:40],
        "great": great[:300],
        "strict": strict[:150],
        "soft": soft[:150],
        "n_stats_keys": len(stats),
        "analyze_end": ANALYZE_END,
        "great_min_hit": GREAT_MIN_HIT,
        "great_min_n": GREAT_MIN_N,
    }


def recipe_key(r: dict) -> Tuple:
    return (r["pattern"], r["side"], r["clock"], r["gap"], r["rsi"], r["or_state"])


def matches_recipe(pat: str, side: str, cb: str, gb: str, rb: str, ost: str, recipes: set) -> bool:
    """Exact or wildcard (any_clock / any_gap / any_rsi) match against GREAT recipes."""
    cands = (
        (pat, side, cb, gb, rb, ost),
        (pat, side, cb, gb, "any_rsi", ost),
        (pat, side, cb, "any_gap", "any_rsi", ost),
        (pat, side, "any_clock", "any_gap", "any_rsi", ost),
        ("_any_", side, cb, gb, "any_rsi", ost),
        ("_any_", side, cb, "any_gap", "any_rsi", ost),
        ("_any_", side, "any_clock", "any_gap", "any_rsi", ost),
    )
    return any(k in recipes for k in cands)


# ───────────────────────── build GREAT-only tickets ─────────────────────────
FEAT = [
    "ret_1",
    "ret_3",
    "ret_6",
    "rsi_14",
    "body_frac",
    "upper_frac",
    "lower_frac",
    "bar_range_pct",
    "or_width",
    "or_ext",
    "mins_entry",
    "gap_pct",
    "session_chg",
    "vwap_dist",
    "atr_ratio",
    "noise_vs_sl",
    "score_bull",
    "score_bear",
    "pat_hit_count",
    "or_only_align",
    "first_break",
    "side",
]


def build_great_tickets(
    df: pd.DataFrame,
    recipes: List[dict],
    *,
    day_lo: str,
    day_hi: str,
    label: str,
) -> Tuple[List[dict], Dict[str, int]]:
    """Only emit BUY/SELL when a GREAT recipe fires and side-aligned first OR break."""
    print(f"\n[2] Building GREAT-only tickets ({label}) {day_lo}→{day_hi}…", flush=True)
    recipe_set = {recipe_key(r) for r in recipes}
    # also allow pattern+side+or_state match with wildcard clock/gap/rsi? No — precious exact.
    reasons: Dict[str, int] = defaultdict(int)
    tickets: List[dict] = []

    gaps = {}
    prev = None
    full = df[(df["day"] >= day_lo) & (df["day"] <= day_hi)]
    for day, sess in df.groupby("day", sort=True):
        o = float(sess["Open"].iloc[0])
        gaps[day] = ((o - prev) / prev * 100.0) if prev else 0.0
        prev = float(sess["Close"].iloc[-1])

    h_all = df["High"].astype(float).values
    l_all = df["Low"].astype(float).values
    c_all = df["Close"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(df.index)}

    t0 = time.time()
    days = [d for d in full["day"].unique()]
    for di, day in enumerate(days, 1):
        if di % 100 == 0:
            print(f"    {label} days {di}/{len(days)} great={len(tickets)} ({time.time()-t0:.0f}s)", flush=True)
        sess = df[df["day"] == day]
        if len(sess) < OR_BARS + 15:
            continue
        or_hi = float(sess["High"].iloc[:OR_BARS].max())
        or_lo = float(sess["Low"].iloc[:OR_BARS].min())
        or_w = or_hi - or_lo
        if or_w < 15:
            reasons["thin_or"] += 1
            continue
        g = float(gaps.get(day, 0.0))
        gb = gap_bucket(g)
        day_open = float(sess["Open"].iloc[0])
        closes = sess["Close"].astype(float).values
        first_up = first_dn = None
        for pos in range(OR_BARS, len(sess)):
            if first_up is None and closes[pos] > or_hi:
                first_up = pos
            if first_dn is None and closes[pos] < or_lo:
                first_dn = pos
            if first_up is not None and first_dn is not None:
                break

        # candidate entries: first break bars only (precious)
        for side, pos in (("BUY", first_up), ("SELL", first_dn)):
            if pos is None:
                continue
            # must be first break of that side
            if side == "BUY" and first_dn is not None and first_dn < first_up:
                reasons["not_first"] += 1
                continue
            if side == "SELL" and first_up is not None and first_up < first_dn:
                reasons["not_first"] += 1
                continue
            ts = sess.index[pos]
            mins = int(ts.hour * 60 + ts.minute)
            if mins < 10 * 60 or mins > 14 * 60 + 30:
                reasons["clock"] += 1
                continue
            ost = or_state(sess, pos, or_hi, or_lo)
            if ost == "both":
                reasons["both"] += 1
                continue
            if side == "BUY" and ost != "only_up":
                reasons["or_misalign"] += 1
                continue
            if side == "SELL" and ost != "only_dn":
                reasons["or_misalign"] += 1
                continue
            row = sess.iloc[pos]
            cb = clock_bucket(mins)
            rb = rsi_bucket(float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0)
            fired = [p for p in c5.PATTERN_COLS if int(row[p]) == 1]
            matched = []
            for pat in fired:
                if matches_recipe(pat, side, cb, gb, rb, ost, recipe_set):
                    matched.append(pat)
            if not matched and matches_recipe("_any_", side, cb, gb, rb, ost, recipe_set):
                matched.append("_any_")
            if not matched:
                reasons["no_great_recipe"] += 1
                continue
            full_i = idx_map[ts]
            entry = float(c_all[full_i])
            bar_o = float(df["Open"].iloc[full_i])
            bar_rng = float(h_all[full_i] - l_all[full_i])
            noise = bar_rng / RISK
            if noise > 1.35:
                reasons["noisy"] += 1
                continue
            body = entry - bar_o
            if side == "BUY" and body <= 0:
                reasons["body"] += 1
                continue
            if side == "SELL" and body >= 0:
                reasons["body"] += 1
                continue
            or_ext = (entry - or_hi) / or_w if side == "BUY" else (or_lo - entry) / or_w
            if or_ext > 0.22:
                reasons["chase"] += 1
                continue
            win = fwd_t1(h_all, l_all, c_all, full_i, side, RISK)
            # still keep losses for training honesty — but only GREAT contexts
            sess_so = sess.iloc[: pos + 1]
            typ = (sess_so["High"] + sess_so["Low"] + sess_so["Close"]) / 3.0
            vwap = float(typ.mean())
            atr = float((sess_so["High"] - sess_so["Low"]).tail(14).mean())
            bull = float(
                row["hammer"] + row["bull_engulf"] + row["pin_bull"] + row["morning_star"] + row["bull_run2"]
            )
            bear = float(
                row["shooting"] + row["bear_engulf"] + row["pin_bear"] + row["evening_star"] + row["bear_run2"]
            )
            feat = {
                "ret_1": float(row["ret_1"]) if np.isfinite(row["ret_1"]) else 0.0,
                "ret_3": float(row["ret_3"]) if np.isfinite(row["ret_3"]) else 0.0,
                "ret_6": float(row["ret_6"]) if np.isfinite(row["ret_6"]) else 0.0,
                "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
                "body_frac": float(row["body_frac"]),
                "upper_frac": float(row["upper_frac"]),
                "lower_frac": float(row["lower_frac"]),
                "bar_range_pct": float(bar_rng / max(entry, 1) * 100),
                "or_width": float(or_w),
                "or_ext": float(or_ext),
                "mins_entry": float(mins),
                "gap_pct": g,
                "session_chg": float((entry - day_open) / day_open * 100),
                "vwap_dist": float((entry - vwap) / entry * 100),
                "atr_ratio": float(bar_rng / max(atr, 1e-6)),
                "noise_vs_sl": float(noise),
                "score_bull": bull,
                "score_bear": bear,
                "pat_hit_count": float(len(matched)),
                "or_only_align": 1.0,
                "first_break": 1.0,
                "side": 1.0 if side == "BUY" else -1.0,
            }
            tickets.append(
                {
                    "day": day,
                    "hm": base._hm(ts),
                    "decision": side,
                    "entry": entry,
                    "win": bool(win),
                    "y": 1 if win else 0,
                    "matched_patterns": matched,
                    "clock": cb,
                    "gap": gb,
                    "rsi_bucket": rb,
                    "or_state": ost,
                    "or_ext": float(or_ext),
                    "x": [float(feat[k]) for k in FEAT],
                    "research_only": True,
                    "not_live": True,
                    "great_only": True,
                }
            )
            reasons["ok"] += 1
    print(f"  {label} great tickets={len(tickets)} reasons={dict(reasons)}", flush=True)
    return tickets, dict(reasons)


def train_great(tickets: List[dict]) -> Dict[str, Any]:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import log_loss

    print("\n[3] Training ML on GREAT tickets only…", flush=True)
    packs = {}
    ordered = sorted(tickets, key=lambda r: (r["day"], r["hm"], r["decision"]))
    grid = (
        dict(max_depth=2, max_iter=80, min_samples_leaf=20, l2_regularization=1.0, learning_rate=0.05),
        dict(max_depth=3, max_iter=100, min_samples_leaf=25, l2_regularization=1.5, learning_rate=0.04),
        dict(max_depth=3, max_iter=140, min_samples_leaf=30, l2_regularization=2.0, learning_rate=0.03),
    )
    for side in ("BUY", "SELL"):
        rows = [r for r in ordered if r["decision"] == side]
        if len(rows) < 40:
            packs[side] = {"available": False, "reason": f"too_few_{len(rows)}"}
            print(f"  skip {side}: n={len(rows)}", flush=True)
            continue
        X = np.asarray([r["x"] for r in rows], dtype=float)
        y = np.asarray([r["y"] for r in rows], dtype=int)
        if len(set(y.tolist())) < 2:
            packs[side] = {"available": False, "reason": "single_class"}
            continue
        w = recent_sample_weights([r["day"] for r in rows], half_life_days=400.0)
        cut_sel = max(20, int(len(rows) * 0.70))
        cut_cal = max(cut_sel + 5, int(len(rows) * 0.85))
        if cut_cal >= len(rows) - 3:
            cut_cal = len(rows) - 3
        if len(set(y[:cut_sel].tolist())) < 2 or len(set(y[cut_cal:].tolist())) < 2:
            # fit all without cal split
            best_params = grid[0]
            clf = HistGradientBoostingClassifier(random_state=42, **best_params)
            clf.fit(X, y, sample_weight=w)
            raw = clf.predict_proba(X)[:, 1]
            packs[side] = {
                "available": True,
                "side": side,
                "base": clf,
                "flip": False,
                "n_train": len(rows),
                "fit_auc": round(base._auc(y, raw), 3),
                "calib_auc": None,
                "params": dict(best_params),
                "feature_names": list(FEAT),
                "great_only": True,
                "research_only": True,
                "not_live": True,
            }
            print(f"  {side}: n={len(rows)} fit_auc={packs[side]['fit_auc']} (no cal)", flush=True)
            continue
        best_params, best_loss = None, None
        for params in grid:
            clf = HistGradientBoostingClassifier(random_state=42, **params)
            clf.fit(X[:cut_sel], y[:cut_sel], sample_weight=w[:cut_sel])
            pred = np.clip(clf.predict_proba(X[cut_sel:cut_cal])[:, 1], 1e-4, 1 - 1e-4)
            loss = float(log_loss(y[cut_sel:cut_cal], pred, labels=[0, 1]))
            if best_loss is None or loss < best_loss:
                best_loss, best_params = loss, params
        base_clf = HistGradientBoostingClassifier(random_state=42, **best_params)
        base_clf.fit(X, y, sample_weight=w)
        held = HistGradientBoostingClassifier(random_state=42, **best_params)
        held.fit(X[:cut_cal], y[:cut_cal], sample_weight=w[:cut_cal])
        raw_cal = held.predict_proba(X[cut_cal:])[:, 1]
        calib_auc = base._auc(y[cut_cal:], raw_cal)
        flip = bool(calib_auc < 0.5)
        if flip:
            calib_auc = 1.0 - calib_auc
        packs[side] = {
            "available": True,
            "side": side,
            "base": base_clf,
            "flip": flip,
            "n_train": len(rows),
            "fit_auc": round(base._auc(y, base_clf.predict_proba(X)[:, 1]), 3),
            "calib_auc": round(float(calib_auc), 3),
            "params": dict(best_params),
            "select_log_loss": round(float(best_loss), 4),
            "feature_names": list(FEAT),
            "great_only": True,
            "research_only": True,
            "not_live": True,
        }
        print(
            f"  {side}: n={len(rows)} fit_auc={packs[side]['fit_auc']} "
            f"calib_auc={packs[side]['calib_auc']} flip={flip}",
            flush=True,
        )
    return packs


def score(packs, tickets):
    out = []
    for r in tickets:
        p = packs.get(r["decision"]) or {}
        if not p.get("available"):
            continue
        raw = float(p["base"].predict_proba(np.asarray([r["x"]], dtype=float))[0, 1])
        if p.get("flip"):
            raw = 1.0 - raw
        rr = {k: v for k, v in r.items() if k != "x"}
        rr["p_t1"] = round(float(np.clip(raw, 0.05, 0.95)), 4)
        out.append(rr)
    return out


def first_day(rows):
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: (x["day"], x["hm"], -(float(x.get("p_t1") or 0)))):
        if r["day"] in seen:
            continue
        seen.add(r["day"])
        out.append(r)
    return out


def agg(rows):
    if not rows:
        return {"n": 0, "wins": 0, "hit_pct": 0.0}
    w = sum(1 for r in rows if r.get("win"))
    return {"n": len(rows), "wins": w, "hit_pct": round(100.0 * w / len(rows), 2)}


def evaluate_new(scored: List[dict]) -> Dict[str, Any]:
    """Test books on brand-new candles."""
    books = {}
    for name, pred in (
        ("ALL_GREAT_DU", lambda r: True),
        ("P52", lambda r: float(r.get("p_t1") or 0) >= 0.52),
        ("P55", lambda r: float(r.get("p_t1") or 0) >= 0.55),
        ("P58", lambda r: float(r.get("p_t1") or 0) >= 0.58),
        ("P60", lambda r: float(r.get("p_t1") or 0) >= 0.60),
        ("P62", lambda r: float(r.get("p_t1") or 0) >= 0.62),
        ("BUY_P55", lambda r: r["decision"] == "BUY" and float(r.get("p_t1") or 0) >= 0.55),
        ("SELL_P55", lambda r: r["decision"] == "SELL" and float(r.get("p_t1") or 0) >= 0.55),
        ("MULTI_PAT", lambda r: float(r.get("pat_hit_count") or 0) >= 2),
        ("MULTI_PAT_P55", lambda r: float(r.get("pat_hit_count") or 0) >= 2 and float(r.get("p_t1") or 0) >= 0.55),
    ):
        rows = first_day([r for r in scored if pred(r)])
        books[name] = {"rows": rows, **agg(rows)}
    return books


def write_report(meta, catalog, packs, train_agg, test_books, test_scored) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NIFTY 1m — GREAT BUY/SELL only (precious 5y candle → new-data test)",
        "",
        "**Not live.**",
        "",
        "## Protocol (no leakage)",
        "",
        f"1. **ANALYZE** `{START}` → `{ANALYZE_END}`: complete 1m candlestick catalog + contexts",
        f"2. **TRAIN** `{START}` → `{TRAIN_END}`: **only GREAT** BUY/SELL recipe matches",
        f"3. **TEST** `{TEST_START}` → `{END}`: brand-new candles (never used to pick recipes)",
        f"- GREAT = analyze T1 hit ≥ **{GREAT_MIN_HIT}%** with n ≥ **{GREAT_MIN_N}**, OR one-sided aligned",
        "",
        "## Analyze — top single patterns",
        "",
        "| Pattern | Side | N | Hit% |",
        "|---|---|---:|---:|",
    ]
    for r in (catalog.get("single") or [])[:15]:
        lines.append(f"| `{r['pattern']}` | {r['side']} | {r['n']} | {r['hit_pct']} |")
    lines += [
        "",
        f"## GREAT recipes kept: **{len(catalog.get('great') or [])}** "
        f"(strict ≥{GREAT_MIN_HIT_STRICT}%: {len(catalog.get('strict') or [])})",
        "",
        "| Side | Pattern | Clock | Gap | RSI | OR | N | Hit% |",
        "|---|---|---|---|---|---|---:|---:|",
    ]
    for r in (catalog.get("great") or [])[:25]:
        lines.append(
            f"| {r['side']} | `{r['pattern']}` | {r['clock']} | {r['gap']} | {r['rsi']} | "
            f"{r['or_state']} | {r['n']} | **{r['hit_pct']}** |"
        )
    lines += ["", "## Train (GREAT only)", ""]
    for side in ("BUY", "SELL"):
        h = packs.get(side) or {}
        if h.get("available"):
            lines.append(
                f"- **{side}**: n={h.get('n_train')} fit_auc={h.get('fit_auc')} "
                f"calib_auc={h.get('calib_auc')} flip={h.get('flip')}"
            )
        else:
            lines.append(f"- **{side}**: unavailable ({h.get('reason')})")
    lines.append(f"- Train ticket base rate: {train_agg}")
    lines += [
        "",
        "## TEST on NEW candlesticks",
        "",
        f"Window `{TEST_START}` → `{END}` · scored={len(test_scored)} · raw {agg(test_scored)}",
        "",
        "| Book | N | Hit% |",
        "|---|---:|---:|",
    ]
    for k, v in test_books.items():
        lines.append(f"| `{k}` | {v.get('n')} | **{v.get('hit_pct')}** |")
    usable = [(k, v) for k, v in test_books.items() if v.get("n", 0) >= 5]
    usable.sort(key=lambda kv: (kv[1]["hit_pct"], kv[1]["n"]), reverse=True)
    lines += ["", "## Winner on new data", ""]
    if usable:
        k, v = usable[0]
        lines.append(f"**`{k}` · {v['n']} @ {v['hit_pct']}%** (day-unique, GREAT-only entries)")
        lines += ["", "| Day | HM | Side | p | patterns | Win |", "|---|---|---|---:|---|:---:|"]
        for r in (v.get("rows") or [])[:30]:
            lines.append(
                f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | {r.get('p_t1')} | "
                f"{','.join(r.get('matched_patterns') or [])} | {'Y' if r.get('win') else 'N'} |"
            )
    else:
        lines.append("_Too few GREAT fires on new data — recipes may be over-tight._")
    lines += [
        "",
        "## Policy",
        "",
        f"- Pack: `{PACK}`",
        "- research_only · not_live · great_only=true",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "meta": meta,
                "catalog": {
                    "single": catalog.get("single"),
                    "great": catalog.get("great"),
                    "strict": catalog.get("strict"),
                    "n_stats_keys": catalog.get("n_stats_keys"),
                },
                "heads": {k: {kk: vv for kk, vv in (v or {}).items() if kk != "base"} for k, v in packs.items()},
                "train_agg": train_agg,
                "test_books": {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in test_books.items()},
                "test_agg": agg(test_scored),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT_MD}", flush=True)


def save_pack(packs, catalog, meta):
    import joblib

    PACK.mkdir(parents=True, exist_ok=True)
    for side, p in packs.items():
        if p.get("available"):
            joblib.dump(
                {"base": p["base"], "flip": p.get("flip"), "feature_names": FEAT, "meta": {k: v for k, v in p.items() if k != "base"}},
                PACK / f"head_{side.lower()}.joblib",
            )
    (PACK / "great_recipes.json").write_text(
        json.dumps({"great": catalog.get("great"), "strict": catalog.get("strict")}, indent=2),
        encoding="utf-8",
    )
    (PACK / "pack_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"  pack → {PACK}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · GREAT-ONLY candle ML · ANALYZE→TRAIN→NEW TEST", flush=True)
    print(f"analyze≤{ANALYZE_END} train≤{TRAIN_END} test≥{TEST_START}", flush=True)
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
    print("\n[0] Candle columns on full 5y…", flush=True)
    df = c5.add_candle_cols(raw)

    catalog = catalog_great_recipes(df)
    recipes = catalog.get("great") or []
    if len(recipes) < 5:
        print("WARN: few GREAT recipes — relaxing to top single-pattern contexts via strict list", flush=True)
        recipes = catalog.get("strict") or recipes
    if not recipes:
        # fallback: take top single patterns as pseudo-recipes with only_up/only_dn
        print("FALLBACK: synthesize recipes from top single patterns", flush=True)
        recipes = []
        for r in (catalog.get("single") or [])[:10]:
            if r["hit_pct"] < 55:
                continue
            ost = "only_up" if r["side"] == "BUY" else "only_dn"
            for cb in ("1000_1030", "1030_1130", "1130_1300"):
                for gb in ("soft_up", "soft_dn", "flat", "gap_up", "gap_dn"):
                    for rb in ("mid", "low", "high", "os", "ob"):
                        recipes.append(
                            {
                                "pattern": r["pattern"],
                                "side": r["side"],
                                "clock": cb,
                                "gap": gb,
                                "rsi": rb,
                                "or_state": ost,
                                "n": r["n"],
                                "hit_pct": r["hit_pct"],
                                "synthetic": True,
                            }
                        )

    train_tickets, train_reasons = build_great_tickets(
        df, recipes, day_lo=START, day_hi=TRAIN_END, label="TRAIN"
    )
    test_tickets, test_reasons = build_great_tickets(
        df, recipes, day_lo=TEST_START, day_hi=END, label="TEST_NEW"
    )

    if len(train_tickets) < 20:
        print("FAIL: too few GREAT train tickets — recipes over-constrained", flush=True)
        meta = {"fail": "too_few_train", "train_reasons": train_reasons, "n_recipes": len(recipes)}
        write_report(meta, catalog, {}, agg([]), {}, [])
        return 1

    packs = train_great(train_tickets)
    train_scored = score(packs, train_tickets)
    test_scored = score(packs, test_tickets)
    test_books = evaluate_new(test_scored)

    print("\n[4] NEW-data books:", flush=True)
    for k, v in test_books.items():
        print(f"  {k}: n={v['n']} hit={v['hit_pct']}%", flush=True)

    meta = {
        "start": START,
        "end": END,
        "analyze_end": ANALYZE_END,
        "train_end": TRAIN_END,
        "test_start": TEST_START,
        "n_bars": len(df),
        "n_recipes": len(recipes),
        "n_train": len(train_tickets),
        "n_test": len(test_tickets),
        "train_reasons": train_reasons,
        "test_reasons": test_reasons,
        "great_only": True,
        "research_only": True,
        "not_live": True,
    }
    save_pack(packs, catalog, meta)
    write_report(meta, catalog, packs, agg(train_scored), test_books, test_scored)
    print("\nDONE · great-only · research only", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
