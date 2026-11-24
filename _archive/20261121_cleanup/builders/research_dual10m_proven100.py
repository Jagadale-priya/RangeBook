"""RESEARCH — train dual-style BUY/SELL heads on **10m** candles, hunt Proven@100% high-N.

Pipeline:
  1) Resample NIFTY 5m → 10m
  2) OR-break tickets + candlestick / microstructure features (bar-only)
  3) Chronological freeze train HGB BUY + SELL heads
  4) OOS score → mine filters → greedy day-union at hard **100%** floor

Also baselines locked dual15 / dual5 proven for compare.

Does NOT promote to LIVE.

  python -u prod_live/tests/builders/research_dual10m_proven100.py
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
warnings.filterwarnings("ignore")
import path_setup  # noqa: F401,E402

from accuracy_max_6m import _agg  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    bestp_day,
    filt,
    first_day,
    gap_map,
    is_perfect,
    mine_perfect,
    union_unique_days,
)
from research_confirm_dual_tf_deep import _clip, _hm_mins, _side  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_XY = LEDGER / "_cache_dual10m_xy_research.json"
CACHE_OOS = LEDGER / "_cache_dual10m_oos_tickets.json"
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"
PACK_DIR = LEDGER / "nifty_side_models_10m_research"
PACK_DIR.mkdir(parents=True, exist_ok=True)

END = "2026-11-13"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_6M = (pd.Timestamp(END) - timedelta(days=183)).strftime("%Y-%m-%d")
# Match dual BUY pack freeze roughly
FREEZE = "2024-09-10"
RISK = 30.0
OR_BARS = 3  # first 30m on 10m tape
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
    "side",
]


def _norm(raw: pd.DataFrame) -> pd.DataFrame:
    work = raw.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index)
    if work.index.tz is None:
        work.index = work.index.tz_localize("Asia/Kolkata")
    else:
        work.index = work.index.tz_convert("Asia/Kolkata")
    work = work.rename(columns={c: str(c).title() for c in work.columns})
    return work.sort_index()


def resample_10m(bars5: pd.DataFrame) -> pd.DataFrame:
    ohlc = bars5.resample("10min", label="left", closed="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    )
    ohlc = ohlc.dropna(subset=["Open", "High", "Low", "Close"])
    # keep session hours
    hm = ohlc.index.strftime("%H:%M")
    return ohlc[(hm >= "09:15") & (hm <= "15:20")]


def _day(ts) -> str:
    t = ts.tz_convert("Asia/Kolkata") if hasattr(ts, "tz_convert") else ts
    return t.strftime("%Y-%m-%d")


def _hm(ts) -> str:
    t = ts.tz_convert("Asia/Kolkata") if hasattr(ts, "tz_convert") else ts
    return t.strftime("%H:%M")


def _rsi(close: np.ndarray, n: int = 14) -> float:
    if len(close) < n + 1:
        return 50.0
    d = np.diff(close[-(n + 1) :])
    up = np.clip(d, 0, None).mean()
    dn = np.clip(-d, 0, None).mean()
    if dn <= 1e-12:
        return 100.0
    rs = up / dn
    return float(100 - 100 / (1 + rs))


def candle_feats(window: pd.DataFrame) -> Dict[str, float]:
    c = window["Close"].astype(float).values
    o = window["Open"].astype(float).values
    h = window["High"].astype(float).values
    l = window["Low"].astype(float).values
    last_o, last_h, last_l, last_c = float(o[-1]), float(h[-1]), float(l[-1]), float(c[-1])
    prev_o = float(o[-2]) if len(o) > 1 else last_o
    prev_c = float(c[-2]) if len(c) > 1 else last_c
    rng = max(last_h - last_l, 1e-6)
    body = abs(last_c - last_o)
    body_frac = body / rng
    upper = last_h - max(last_c, last_o)
    lower = min(last_c, last_o) - last_l
    doji = 1.0 if body_frac < 0.12 else 0.0
    hammer = 1.0 if (lower > 2 * body and upper < body) else 0.0
    engulf = 0.0
    if (last_c > last_o and prev_c < prev_o and last_c >= prev_o and last_o <= prev_c) or (
        last_c < last_o and prev_c > prev_o and last_c <= prev_o and last_o >= prev_c
    ):
        engulf = 1.0
    candle_score = (1.0 if last_c > last_o else -1.0) * body_frac + 0.25 * engulf - 0.15 * doji
    if len(c) >= 4:
        slope = (c[-1] - c[-4]) / max(abs(c[-4]), 1.0) * 100.0
    else:
        slope = 0.0
    return {
        "candle_score": float(candle_score),
        "body_frac": float(body_frac),
        "bar_range_pct": float(rng / max(last_c, 1.0) * 100.0),
        "pat_doji": doji,
        "pat_hammer": hammer,
        "pat_engulf": engulf,
        "slope_3": float(slope),
        "rsi_14": _rsi(c, 14),
        "ret_1": float((c[-1] / c[-2] - 1) * 100) if len(c) > 1 else 0.0,
        "ret_3": float((c[-1] / c[-4] - 1) * 100) if len(c) > 3 else 0.0,
        "ret_6": float((c[-1] / c[-7] - 1) * 100) if len(c) > 6 else 0.0,
    }


def fwd_path(
    bars: pd.DataFrame, i: int, side: str, entry: float, sl: float, t1: float
) -> Tuple[bool, str, float]:
    day = _day(bars.index[i])
    win = False
    pts = -abs(entry - sl)
    outcome = "expired"
    n = len(bars)
    j = i + 1
    while j < n and _day(bars.index[j]) == day:
        hh = float(bars["High"].iloc[j])
        ll = float(bars["Low"].iloc[j])
        if side == "BUY":
            hit_sl, hit_t1 = ll <= sl, hh >= t1
            if hit_sl and hit_t1:
                return False, "same_bar_both", -abs(entry - sl)
            if hit_sl:
                return False, "sl_before_t1", -abs(entry - sl)
            if hit_t1:
                return True, "t1_before_sl", abs(t1 - entry)
        else:
            hit_sl, hit_t1 = hh >= sl, ll <= t1
            if hit_sl and hit_t1:
                return False, "same_bar_both", -abs(sl - entry)
            if hit_sl:
                return False, "sl_before_t1", -abs(sl - entry)
            if hit_t1:
                return True, "t1_before_sl", abs(entry - t1)
        j += 1
    return win, outcome, pts


def build_tickets(bars10: pd.DataFrame, gaps: Dict[str, float]) -> List[dict]:
    # Precompute global integer index for forward path
    idx_map = {ts: i for i, ts in enumerate(bars10.index)}
    day_key = pd.Index([_day(ts) for ts in bars10.index])
    groups = bars10.groupby(day_key, sort=True)
    days = list(groups.groups.keys())
    out: List[dict] = []
    t0 = time.time()
    for di, day in enumerate(days, 1):
        if di % 200 == 0:
            print(f"    tickets {di}/{len(days)} n={len(out)} ({time.time()-t0:.0f}s)", flush=True)
        sess = groups.get_group(day)
        if len(sess) < OR_BARS + 4:
            continue
        or_hi = float(sess["High"].iloc[:OR_BARS].max())
        or_lo = float(sess["Low"].iloc[:OR_BARS].min())
        or_w = or_hi - or_lo
        if or_w < 8:
            continue
        day_open = float(sess["Open"].iloc[0])
        first_up = first_dn = None
        closes = sess["Close"].astype(float).values
        for pos in range(OR_BARS, len(sess)):
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
            if side == "BUY" and first_up is not None and (first_dn is None or first_up <= first_dn):
                first = 1.0
            if side == "SELL" and first_dn is not None and (first_up is None or first_dn < first_up):
                first = 1.0
            ts = sess.index[pos]
            full_i = idx_map.get(ts)
            if full_i is None:
                continue
            left = max(0, full_i - 40)
            window = bars10.iloc[left : full_i + 1]
            entry = float(bars10["Close"].iloc[full_i])
            if side == "BUY":
                sl, t1 = entry - RISK, entry + RISK
                or_ext = (entry - or_hi) / or_w
            else:
                sl, t1 = entry + RISK, entry - RISK
                or_ext = (or_lo - entry) / or_w
            win_f, outcome, pts = fwd_path(bars10, full_i, side, entry, sl, t1)
            if outcome not in ("t1_before_sl", "sl_before_t1"):
                continue
            cf = candle_feats(window)
            sess_so_far = sess.iloc[: pos + 1]
            hi = sess_so_far["High"].astype(float)
            lo = sess_so_far["Low"].astype(float)
            cl = sess_so_far["Close"].astype(float)
            typ = (hi + lo + cl) / 3.0
            vwap = float(typ.mean())
            atr = float((hi - lo).tail(14).mean())
            hm = _hm(ts)
            hh, mm = map(int, hm.split(":"))
            mins = hh * 60 + mm
            feat = {
                **cf,
                "vwap_dist": (entry - vwap) / max(entry, 1.0) * 100.0,
                "range_pos": (entry - float(lo.min())) / max(float(hi.max() - lo.min()), 1e-6),
                "or_width": or_w,
                "or_ext": float(or_ext),
                "mins_entry": float(mins),
                "first_break": float(first),
                "gap_pct": float(gaps.get(day) or 0.0),
                "session_chg": (entry - day_open) / max(day_open, 1.0) * 100.0,
                "atr_ratio": atr / RISK if RISK else 0.0,
                "side": 1.0 if side == "BUY" else -1.0,
            }
            x = [float(feat.get(k, 0.0)) for k in FEAT_NAMES]
            out.append(
                {
                    "day": day,
                    "hm": hm,
                    "decision": side,
                    "win": bool(win_f),
                    "points": round(float(pts), 1),
                    "outcome": outcome,
                    "entry": round(entry, 2),
                    "stop_loss": round(sl, 2),
                    "target_1": round(t1, 2),
                    "p_t1": None,
                    "track": "dual10m",
                    "tf": "10m",
                    "first_break": bool(first),
                    "x": x,
                    "y": 1 if win_f else 0,
                }
            )
    return out


def train_heads(tickets: List[dict]) -> Dict[str, Any]:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.isotonic import IsotonicRegression

    packs: Dict[str, Any] = {}
    for side in ("BUY", "SELL"):
        rows = [r for r in tickets if r["decision"] == side and str(r["day"]) <= FREEZE]
        if len(rows) < 40:
            packs[side] = {"available": False, "reason": f"too_few_{len(rows)}"}
            continue
        X = np.asarray([r["x"] for r in rows], dtype=float)
        y = np.asarray([r["y"] for r in rows], dtype=int)
        # chronological 80/20 inside train window for calibration
        cut = max(20, int(len(rows) * 0.8))
        Xtr, ytr = X[:cut], y[:cut]
        Xcal, ycal = X[cut:], y[cut:]
        if len(set(ytr.tolist())) < 2:
            packs[side] = {"available": False, "reason": "single_class"}
            continue
        base = HistGradientBoostingClassifier(
            max_depth=5, learning_rate=0.06, max_iter=200, random_state=42
        )
        base.fit(Xtr, ytr)
        raw = base.predict_proba(Xcal)[:, 1] if len(Xcal) else base.predict_proba(Xtr)[:, 1]
        y_iso = ycal if len(Xcal) else ytr
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(raw, y_iso)
        # refit base on all freeze rows
        base2 = HistGradientBoostingClassifier(
            max_depth=5, learning_rate=0.06, max_iter=200, random_state=42
        )
        base2.fit(X, y)
        packs[side] = {
            "available": True,
            "side": side,
            "base": base2,
            "iso": iso,
            "n_train": int(len(rows)),
            "train_through_day": FREEZE,
            "feature_names": list(FEAT_NAMES),
            "holdout_base_hit": round(100.0 * float(y.mean()), 2),
        }
        print(
            f"  trained {side} n={len(rows)} base_hit={packs[side]['holdout_base_hit']}%",
            flush=True,
        )
    return packs


def score_ticket(packs: Dict[str, Any], row: dict) -> Optional[float]:
    side = row["decision"]
    pack = packs.get(side) or {}
    if not pack.get("available"):
        return None
    X = np.asarray([row["x"]], dtype=float)
    raw = float(pack["base"].predict_proba(X)[0, 1])
    cal = float(np.clip(pack["iso"].transform([raw])[0], 0.05, 0.95))
    return cal


def mine_and_union(
    rows: List[dict],
    *,
    active: Set[str],
    gaps: Dict[str, float],
) -> Tuple[List[dict], List[str], List[Tuple[str, Dict[str, Any]]]]:
    streams = mine_perfect("D10", rows, active=active, gaps=gaps, min_n=5)
    # extra first-break only streams at high p
    extra = []
    for pmin in (0.55, 0.58, 0.62, 0.65, 0.68, 0.70, 0.72, 0.75, 0.78, 0.80, 0.85, 0.90):
        for side in (None, "BUY", "SELL"):
            base = [r for r in rows if float(r.get("p_t1") or 0) >= pmin]
            if side:
                base = [r for r in base if _side(r) == side]
            base_fb = [r for r in base if r.get("first_break")]
            for lab, rs in (("any", base), ("firstbreak", base_fb)):
                for vlab, vrows in (("raw", rs), ("first", first_day(rs)), ("bestp", bestp_day(rs))):
                    if len(vrows) < 5 or not is_perfect(vrows):
                        continue
                    tag = f"D10_{side or 'BOTH'}_p{int(pmin*100)}_{lab}_{vlab}"
                    extra.append((tag, vrows, _agg(vrows)))
    streams = streams + extra
    streams.sort(key=lambda x: (x[2].get("n") or 0, x[2].get("points") or 0), reverse=True)

    cur: List[dict] = []
    used: List[str] = []
    for tag, rs, _st in streams:
        seed = _clip(rs, START_3Y, END)
        if not seed or not is_perfect(seed):
            continue
        s1 = _clip(rs, START_1Y, END)
        if len(s1) >= 5 and not is_perfect(s1):
            continue
        cur, used = list(seed), [tag]
        break
    if not cur:
        return [], [], [(t, s) for t, _r, s in streams[:20]]

    improved = True
    while improved and len(used) < 80:
        improved = False
        best = None
        best_n = len(cur)
        for tag, rs, _st in streams:
            if tag in used:
                continue
            cand = _clip(rs, START_3Y, END)
            merged = union_unique_days(cur, cand)
            if len(merged) <= best_n or not is_perfect(merged):
                continue
            m1 = _clip(merged, START_1Y, END)
            if len(m1) >= 5 and not is_perfect(m1):
                continue
            best = (tag, merged)
            best_n = len(merged)
        if best:
            used.append(best[0])
            cur = best[1]
            improved = True
            print(f"    +{best[0][:70]} → n={len(cur)}", flush=True)
    return cur, used, [(t, s) for t, _r, s in streams[:25]]


def score_windows(rows: List[dict]) -> Dict[str, Any]:
    out = {}
    for label, a, b in (
        ("3y", START_3Y, END),
        ("1y", START_1Y, END),
        ("6m", START_6M, END),
        ("oos_from_freeze", (pd.Timestamp(FREEZE) + timedelta(days=1)).strftime("%Y-%m-%d"), END),
    ):
        rs = _clip(rows, a, b)
        st = _agg(rs)
        out[label] = {**st, "perfect": (not rs) or is_perfect(rs)}
    return out


def main() -> int:
    t0 = time.time()
    print("RESEARCH dual@10m train + Proven@100% high-N hunt", flush=True)
    gaps = gap_map()
    dual = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    p15 = [dict(r) for r in dual["dual15"].get("proven_100") or []]
    p5 = [dict(r) for r in dual["dual5"].get("proven_100") or []]

    # --- tickets ---
    if CACHE_XY.is_file():
        raw = json.loads(CACHE_XY.read_text(encoding="utf-8"))
        if raw.get("end") == END and raw.get("freeze") == FREEZE and raw.get("risk") == RISK:
            tickets = raw["tickets"]
            print(f"  XY cache hit n={len(tickets)}", flush=True)
        else:
            tickets = None
    else:
        tickets = None

    if tickets is None:
        print("  load 5m → resample 10m…", flush=True)
        bars5 = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
        # speed: use from 2018 for train depth without full 2015
        bars5 = bars5[bars5.index >= "2018-01-01"]
        bars10 = resample_10m(bars5)
        print(f"  10m bars={len(bars10)} {bars10.index.min().date()}→{bars10.index.max().date()}", flush=True)
        print("  build OR-break tickets…", flush=True)
        tickets = build_tickets(bars10, gaps)
        # drop heavy x duplication in cache? keep x for train
        CACHE_XY.write_text(
            json.dumps(
                {"end": END, "freeze": FREEZE, "risk": RISK, "feat": FEAT_NAMES, "tickets": tickets},
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"  tickets={len(tickets)} saved", flush=True)

    # ensure x present
    for r in tickets:
        if "x" not in r and "feat" in r:
            r["x"] = [float(r["feat"].get(k, 0.0)) for k in FEAT_NAMES]

    print("  train BUY/SELL heads…", flush=True)
    packs = train_heads(tickets)
    # persist lightweight meta (not full sklearn in json)
    meta = {
        k: {kk: vv for kk, vv in v.items() if kk not in ("base", "iso")}
        for k, v in packs.items()
    }
    (PACK_DIR / "dual10m_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    try:
        import joblib

        joblib.dump(packs, PACK_DIR / "dual10m_packs.joblib")
    except Exception as e:
        print(f"  pack dump skip: {e}", flush=True)

    # score all post-freeze + also score freeze for diagnostics
    print("  score tickets…", flush=True)
    scored: List[dict] = []
    for r in tickets:
        p = score_ticket(packs, r)
        if p is None:
            continue
        rr = {k: v for k, v in r.items() if k != "x"}
        rr["p_t1"] = round(float(p), 4)
        scored.append(rr)

    oos = [r for r in scored if str(r["day"]) > FREEZE]
    print(
        f"  scored={len(scored)} oos={len(oos)} oos_hit={_agg(oos).get('hit_pct')}",
        flush=True,
    )
    CACHE_OOS.write_text(
        json.dumps({"freeze": FREEZE, "end": END, "oos": oos}, default=str),
        encoding="utf-8",
    )

    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_3Y < d <= END]
    daily = fs._load_daily()
    active = fs._active_days(sess, daily) if sess else set()

    # hunt on OOS path-true rows that fall in last 3y window
    hunt_rows = _clip(oos, START_3Y, END)
    print(f"  mine/union on OOS∩3y n={len(hunt_rows)} hit={_agg(hunt_rows).get('hit_pct')}", flush=True)
    day_rows, day_tags, top = mine_and_union(hunt_rows, active=active, gaps=gaps)

    books = {
        "BASE_dual15_proven": p15,
        "BASE_dual5_proven": p5,
        "D10_OOS_ALL": oos,
        "D10_PROVEN100_DAY": day_rows,
    }
    # also high-p raw OOS first/day
    for pmin in (0.70, 0.75, 0.80, 0.85, 0.90):
        rs = [r for r in hunt_rows if float(r.get("p_t1") or 0) >= pmin]
        books[f"D10_p{int(pmin*100)}_raw"] = rs
        books[f"D10_p{int(pmin*100)}_day"] = first_day(rs)

    payload: Dict[str, Any] = {
        "status": "RESEARCH",
        "not_live": True,
        "interval": "10m",
        "risk": RISK,
        "freeze": FREEZE,
        "train_meta": meta,
        "n_tickets": len(tickets),
        "n_oos": len(oos),
        "day_stream_tags": day_tags,
        "top_streams": [{"tag": t, **s} for t, s in top],
        "books": {},
    }

    lines = [
        "# RESEARCH — Dual@10m train → Proven@100% high-N",
        "",
        "**Status:** RESEARCH only · **not live**",
        "**Data:** 5m tape resampled → **10m** candles · OR-break tickets · candlestick features",
        f"**Train freeze:** ≤ `{FREEZE}` · OOS after · risk `{RISK}` pts · hard floor **100%**",
        "",
        f"Tickets: **{len(tickets)}** · OOS: **{len(oos)}** @ {_agg(oos).get('hit_pct')}%",
        f"Day 100% desk streams: **{len(day_tags)}**",
        "",
        "## Train meta",
        "",
        "| Side | Available | N train | Base hit% |",
        "|---|---|---:|---:|",
    ]
    for side in ("BUY", "SELL"):
        m = meta.get(side) or {}
        lines.append(
            f"| {side} | {m.get('available')} | {m.get('n_train', '—')} | {m.get('holdout_base_hit', '—')} |"
        )

    lines.extend(
        [
            "",
            "## Books",
            "",
            "| Book | 3y | 1y | 6m | OOS | Perfect3y |",
            "|---|---|---|---|---|---|",
        ]
    )
    for name, rows in books.items():
        sc = score_windows(rows)
        payload["books"][name] = sc

        def fmt(w: str) -> str:
            x = sc[w]
            n = x.get("n") or 0
            return f"{n}@{x.get('hit_pct')}" if n else "0"

        lines.append(
            f"| `{name}` | {fmt('3y')} | {fmt('1y')} | {fmt('6m')} | {fmt('oos_from_freeze')} | "
            f"{'Y' if sc['3y'].get('perfect') else 'N'} |"
        )

    d1 = payload["books"]["D10_PROVEN100_DAY"]["1y"]
    d3 = payload["books"]["D10_PROVEN100_DAY"]["3y"]
    b15 = payload["books"]["BASE_dual15_proven"]["1y"]

    if day_rows and d3.get("perfect") and d1.get("perfect") and (d1.get("n") or 0) >= max(20, b15.get("n") or 0):
        verdict = (
            f"PROMISING — dual10m day desk {d1.get('n')}@100% on 1y "
            f"(dual15 proven {b15.get('n')}@{b15.get('hit_pct')}%). Still RESEARCH."
        )
    elif day_rows and d3.get("perfect") and (d1.get("n") or 0) >= 10:
        verdict = (
            f"PARTIAL — dual10m 100% day desk {d1.get('n')}@100% 1y; "
            f"below/near dual15 proven ({b15.get('n')}@{b15.get('hit_pct')}%)."
        )
    elif day_rows and d3.get("perfect"):
        verdict = f"THIN — 100% desk exists ({d3.get('n')}@100% 3y) but call count still low."
    else:
        verdict = (
            "FAIL soft — 10m dual train did not yield a high-N Proven@100 desk yet; "
            "keep dual15 proven for LIVE."
        )

    payload["verdict"] = verdict
    payload["elapsed_s"] = round(time.time() - t0, 1)

    lines.extend(["", "## Day stream order", ""])
    for i, t in enumerate(day_tags, 1):
        lines.append(f"{i}. `{t}`")
    lines.extend(
        [
            "",
            "## Sample 1y day calls",
            "",
            "| Day | HM | Side | Win | p |",
            "|---|---|---|---|---:|",
        ]
    )
    for r in sorted(_clip(day_rows, START_1Y, END), key=lambda x: (x.get("day"), x.get("hm")))[:40]:
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {_side(r)} | "
            f"{'W' if r.get('win') else 'L'} | {r.get('p_t1')} |"
        )
    lines.extend(["", "## Verdict", "", verdict, "", f"Elapsed {payload['elapsed_s']}s", ""])

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "RESEARCH_DUAL10M_PROVEN100.md"
    js = OUT / "RESEARCH_DUAL10M_PROVEN100.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
