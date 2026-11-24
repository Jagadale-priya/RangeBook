"""RESEARCH ONLY — Expansion candle × liquidity (sweep / FVG) on NIFTY 1m.

Question: can expansion + liquidity context clear PROVEN walk-forward gates,
as a standalone book or as a filter on Oracle-style textbook entries?

Prove rules (same house gate as PA_PROVEN_LOGIC):
  PROVEN: TRAIN+OOS n≥30, hit@3R≥35%, exp_R≥0.20, OOS t≥1.5
  PROMISING: TRAIN+OOS n≥20, hit≥32%, exp_R≥0.10, both exp>0
  else NOT_PROVEN

  python -u prod_live/tests/builders/_diag_scalp_expansion_liquidity.py
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
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_daily_must_100 as dm  # noqa: E402
from _diag_scalp_pa_bos_choch_fvg import (  # noqa: E402
    _norm_1m,
    detect_fvg,
    path_rr,
    to_15m,
)
from _diag_scalp_pa_proven_logic import (  # noqa: E402
    MAX_HOLD,
    MIN_EXP,
    MIN_HIT,
    MIN_N,
    MIN_T,
    N_SESSIONS,
    LOOKBACK_CAL,
    RR,
    SOFT_EXP,
    SOFT_HIT,
    SOFT_N,
    summarize_R,
    verdict,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_EXPANSION_LIQUIDITY.md"
REPORT_JSON = OUT / "NIFTY_1M_EXPANSION_LIQUIDITY.json"

TRADE_LO = 9 * 60 + 20
TRADE_HI = 15 * 60
GAP_MINS = 15
SWEEP_LB = 8
EXP_ATR_K = 1.0  # body ≥ 1.0 × ATR14
EXP_BODY_FRAC = 0.62  # body / range
T15 = 15.0


def _mins(ts) -> int:
    return int(ts.hour) * 60 + int(ts.minute)


def atr14(h, l, c) -> np.ndarray:
    prev = np.roll(c, 1)
    prev[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))
    out = pd.Series(tr).rolling(14, min_periods=1).mean().to_numpy(dtype=float)
    return out


def detect_expansions(o, h, l, c, atr, k=EXP_ATR_K, body_frac=EXP_BODY_FRAC) -> List[dict]:
    """Large-body displacement bars (expansion / impulse candles)."""
    out = []
    n = len(c)
    for i in range(14, n):
        rng = float(h[i] - l[i])
        if rng < 1e-9:
            continue
        body = float(c[i] - o[i])
        abs_body = abs(body)
        a = float(atr[i]) if np.isfinite(atr[i]) else 0.0
        if a < 1e-9 or abs_body < k * a:
            continue
        if abs_body / rng < body_frac:
            continue
        # close in extreme quartile of range
        pos = (float(c[i]) - float(l[i])) / rng
        if body > 0 and pos < 0.75:
            continue
        if body < 0 and pos > 0.25:
            continue
        side = "BUY" if body > 0 else "SELL"
        out.append(
            {
                "i": i,
                "side": side,
                "body": abs_body,
                "atr": a,
                "body_atr": abs_body / a,
                "body_frac": abs_body / rng,
            }
        )
    return out


def detect_sweeps(h, l, c, lookback=SWEEP_LB) -> List[dict]:
    """Wick beyond recent extreme, body closes back inside."""
    sweeps = []
    n = len(c)
    for i in range(lookback + 2, n):
        prior_high = float(np.max(h[i - lookback : i]))
        prior_low = float(np.min(l[i - lookback : i]))
        if float(l[i]) < prior_low and float(c[i]) > prior_low:
            sweeps.append({"i": i, "side": "BUY", "level": prior_low})
        if float(h[i]) > prior_high and float(c[i]) < prior_high:
            sweeps.append({"i": i, "side": "SELL", "level": prior_high})
    return sweeps


def oracle_pattern_side(primary: str, body: float) -> Optional[str]:
    if primary in tb.BULLISH and body > 0:
        return "BUY"
    if primary in tb.BEARISH and body < 0:
        return "SELL"
    return None


def detect_oracle_entries(df: pd.DataFrame, ema34, atr) -> List[dict]:
    """Same spirit as live Oracle: textbook primary + EMA align at bar close."""
    work = tb.detect_textbook(df)
    o = work["Open"].astype(float).values
    c = work["Close"].astype(float).values
    out = []
    for i in range(34, len(work)):
        row = work.iloc[i]
        body = float(c[i] - o[i])
        hits = [p for p in dm.PRIORITY if p in work.columns and int(row[p]) == 1]
        if not hits:
            continue
        primary = hits[0]
        side = oracle_pattern_side(primary, body)
        if side is None:
            continue
        entry = float(c[i])
        ema_i = float(ema34[i]) if np.isfinite(ema34[i]) else entry
        if side == "BUY" and entry < ema_i:
            continue
        if side == "SELL" and entry > ema_i:
            continue
        out.append({"i": i, "side": side, "primary": primary, "entry": entry})
    return out


def score_entry(
    h, l, c, ema, i: int, side: str, entry: float, *, mode: str, atr_i: float
) -> Optional[dict]:
    """Score with 3R stop beyond 0.5×ATR wick buffer OR fixed T15 path."""
    a = max(float(atr_i), 2.0)
    if mode == "t15":
        # Oracle-like: fixed T15, trail invalidation approximated as EMA cross after entry
        t1 = T15
        if side == "BUY":
            sl = entry - max(8.0, 0.6 * a)
            tp = entry + t1
        else:
            sl = entry + max(8.0, 0.6 * a)
            tp = entry - t1
        # use path_rr with rr = t1/risk so TP distance matches T15
        risk = abs(entry - sl)
        rr = t1 / risk if risk > 1e-9 else RR
        ok, reason, pts, j = path_rr(h, l, c, i, side, entry, sl, rr, max_bars=MAX_HOLD)
        R = (t1 / risk) if ok else (pts / risk if risk > 1e-9 else 0.0)
        if not ok and reason == "sl":
            R = -1.0
        elif not ok:
            R = float(pts) / risk if risk > 1e-9 else 0.0
        return {
            "win": bool(ok),
            "reason": reason,
            "pts": round(float(pts if ok else pts), 2),
            "R": round(float(R), 3),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "mode": "t15",
        }

    # 3R: stop beyond expansion extreme buffer
    if side == "BUY":
        sl = float(l[i]) - 0.15 * a
    else:
        sl = float(h[i]) + 0.15 * a
    risk = abs(entry - sl)
    if risk < 1.5:
        return None
    ok, reason, pts, j = path_rr(h, l, c, i, side, entry, sl, RR, max_bars=MAX_HOLD)
    if ok:
        R = float(RR)
    elif reason == "sl":
        R = -1.0
    else:
        R = float(pts) / risk
    return {
        "win": bool(ok),
        "reason": reason,
        "pts": round(float(pts), 2),
        "R": round(float(R), 3),
        "sl": round(sl, 2),
        "mode": "3r",
    }


def one_per_day(trades: List[dict]) -> List[dict]:
    by = defaultdict(list)
    for t in trades:
        by[t["day"]].append(t)
    out = []
    for d in sorted(by):
        rows = sorted(by[d], key=lambda x: x["mins"])
        next_ok = None
        for t in rows:
            if next_ok is not None and t["mins"] < next_ok:
                continue
            out.append(t)
            next_ok = int(t["mins"]) + GAP_MINS
    return out


def make_trade(df, i, side, entry, scored, tag, extra=None) -> dict:
    ts = df.index[i]
    t = {
        "day": str(ts.date()),
        "hm": ts.strftime("%H:%M"),
        "mins": _mins(ts),
        "side": side,
        "decision": side,
        "entry": round(float(entry), 2),
        "full_i": int(i),
        "book": tag,
        "win": scored["win"],
        "reason": scored["reason"],
        "pts": scored["pts"],
        "R": scored["R"],
    }
    if extra:
        t.update(extra)
    return t


def build_books(df: pd.DataFrame) -> Dict[str, List[dict]]:
    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    atr = atr14(h, l, c)
    ema34 = pd.Series(c).ewm(span=34, adjust=False).mean().to_numpy(dtype=float)
    mins = np.array([_mins(ts) for ts in df.index])

    expansions = detect_expansions(o, h, l, c, atr)
    sweeps = detect_sweeps(h, l, c)
    fvgs = detect_fvg(o, h, l, c)
    oracle = detect_oracle_entries(df, ema34, atr)

    exp_by_i = {e["i"]: e for e in expansions}
    sweeps_buy = [s for s in sweeps if s["side"] == "BUY"]
    sweeps_sell = [s for s in sweeps if s["side"] == "SELL"]
    fvg_buy = [f for f in fvgs if f["side"] == "BUY"]
    fvg_sell = [f for f in fvgs if f["side"] == "SELL"]
    oracle_by_i = {e["i"]: e for e in oracle}

    def recent_sweep(side: str, i: int, within: int = 8) -> Optional[dict]:
        pool = sweeps_buy if side == "BUY" else sweeps_sell
        best = None
        for s in pool:
            if s["i"] >= i:
                break
            if i - s["i"] <= within:
                best = s
        return best

    def ema_ok(side: str, i: int, entry: float) -> bool:
        ema_i = float(ema34[i]) if np.isfinite(ema34[i]) else entry
        if side == "BUY" and entry < ema_i:
            return False
        if side == "SELL" and entry > ema_i:
            return False
        return True

    books: Dict[str, List[dict]] = defaultdict(list)

    # --- A: chase expansion close ---
    for e in expansions:
        i = e["i"]
        if not (TRADE_LO <= mins[i] <= TRADE_HI):
            continue
        side = e["side"]
        entry = float(c[i])
        if not ema_ok(side, i, entry):
            continue
        for mode in ("3r", "t15"):
            sc = score_entry(h, l, c, ema34, i, side, entry, mode=mode, atr_i=e["atr"])
            if not sc:
                continue
            books[f"A_exp_chase_{mode}"].append(
                make_trade(df, i, side, entry, sc, f"A_exp_chase_{mode}", {"body_atr": round(e["body_atr"], 2)})
            )

    # --- B: sweep then expansion within 5 bars (enter expansion close) ---
    for e in expansions:
        i = e["i"]
        if not (TRADE_LO <= mins[i] <= TRADE_HI):
            continue
        side = e["side"]
        sw = recent_sweep(side, i, within=5)
        if not sw:
            continue
        entry = float(c[i])
        if not ema_ok(side, i, entry):
            continue
        for mode in ("3r", "t15"):
            sc = score_entry(h, l, c, ema34, i, side, entry, mode=mode, atr_i=e["atr"])
            if not sc:
                continue
            books[f"B_sweep_exp_{mode}"].append(
                make_trade(
                    df,
                    i,
                    side,
                    entry,
                    sc,
                    f"B_sweep_exp_{mode}",
                    {"sweep_i": sw["i"], "gap_bars": i - sw["i"], "body_atr": round(e["body_atr"], 2)},
                )
            )

    # --- C: sweep → expansion → FVG mid fill (classic ICT entry) ---
    for e in expansions:
        i = e["i"]
        if not (TRADE_LO <= mins[i] <= TRADE_HI):
            continue
        side = e["side"]
        sw = recent_sweep(side, i, within=5)
        if not sw:
            continue
        # FVG confirmed at/after expansion mid around i
        pool = fvg_buy if side == "BUY" else fvg_sell
        fvg = None
        for f in pool:
            if f["i_confirm"] >= i - 1 and f["i_confirm"] <= i + 2 and f["size"] >= 1.5:
                fvg = f
                break
        if not fvg:
            continue
        # wait for touch of mid after confirm
        entry_i = None
        entry_px = None
        for j in range(fvg["i_confirm"] + 1, min(len(c), fvg["i_confirm"] + 31)):
            if not (TRADE_LO <= mins[j] <= TRADE_HI):
                continue
            if side == "BUY" and float(l[j]) <= fvg["mid"] <= float(h[j]):
                entry_i, entry_px = j, float(fvg["mid"])
                break
            if side == "SELL" and float(l[j]) <= fvg["mid"] <= float(h[j]):
                entry_i, entry_px = j, float(fvg["mid"])
                break
        if entry_i is None:
            continue
        if not ema_ok(side, entry_i, entry_px):
            continue
        for mode in ("3r", "t15"):
            sc = score_entry(
                h, l, c, ema34, entry_i, side, entry_px, mode=mode, atr_i=float(atr[entry_i])
            )
            if not sc:
                continue
            books[f"C_sweep_exp_fvg_{mode}"].append(
                make_trade(
                    df,
                    entry_i,
                    side,
                    entry_px,
                    sc,
                    f"C_sweep_exp_fvg_{mode}",
                    {"exp_i": i, "sweep_i": sw["i"], "fvg_size": round(fvg["size"], 2)},
                )
            )

    # --- D: expansion signal, enter NEXT bar open (no chase) ---
    for e in expansions:
        i = e["i"]
        j = i + 1
        if j >= len(c):
            continue
        if not (TRADE_LO <= mins[j] <= TRADE_HI):
            continue
        side = e["side"]
        entry = float(o[j])
        if not ema_ok(side, j, entry):
            continue
        sw = recent_sweep(side, i, within=5)
        tag_base = "D_exp_next_open_sweep" if sw else "D_exp_next_open"
        for mode in ("3r", "t15"):
            sc = score_entry(h, l, c, ema34, j, side, entry, mode=mode, atr_i=float(atr[j]))
            if not sc:
                continue
            books[f"{tag_base}_{mode}"].append(
                make_trade(df, j, side, entry, sc, f"{tag_base}_{mode}", {"exp_i": i, "had_sweep": bool(sw)})
            )

    # --- E: Oracle baseline + Oracle∩sweep + Oracle∩expansion ---
    for e in oracle:
        i = e["i"]
        if not (TRADE_LO <= mins[i] <= TRADE_HI):
            continue
        side = e["side"]
        entry = float(e["entry"])
        for mode in ("3r", "t15"):
            sc = score_entry(h, l, c, ema34, i, side, entry, mode=mode, atr_i=float(atr[i]))
            if not sc:
                continue
            books[f"E_oracle_{mode}"].append(
                make_trade(df, i, side, entry, sc, f"E_oracle_{mode}", {"primary": e["primary"]})
            )
            if recent_sweep(side, i, within=8):
                books[f"E_oracle_sweep_{mode}"].append(
                    make_trade(df, i, side, entry, sc, f"E_oracle_sweep_{mode}", {"primary": e["primary"]})
                )
            if i in exp_by_i and exp_by_i[i]["side"] == side:
                books[f"E_oracle_exp_{mode}"].append(
                    make_trade(df, i, side, entry, sc, f"E_oracle_exp_{mode}", {"primary": e["primary"]})
                )
            if recent_sweep(side, i, within=8) and i in exp_by_i and exp_by_i[i]["side"] == side:
                books[f"E_oracle_sweep_exp_{mode}"].append(
                    make_trade(df, i, side, entry, sc, f"E_oracle_sweep_exp_{mode}", {"primary": e["primary"]})
                )

    # --- F: strong expansion only (body ≥ 1.5 ATR) after sweep ---
    for e in expansions:
        if e["body_atr"] < 1.5:
            continue
        i = e["i"]
        if not (TRADE_LO <= mins[i] <= TRADE_HI):
            continue
        side = e["side"]
        if not recent_sweep(side, i, within=6):
            continue
        entry = float(c[i])
        if not ema_ok(side, i, entry):
            continue
        for mode in ("3r", "t15"):
            sc = score_entry(h, l, c, ema34, i, side, entry, mode=mode, atr_i=e["atr"])
            if not sc:
                continue
            books[f"F_strong_exp_sweep_{mode}"].append(
                make_trade(df, i, side, entry, sc, f"F_strong_exp_sweep_{mode}", {"body_atr": round(e["body_atr"], 2)})
            )

    # 1/day-ish gap spacing
    return {k: one_per_day(v) for k, v in books.items()}


def split_wf(trades: List[dict], days_sorted: List[str]):
    mid = days_sorted[len(days_sorted) // 2]
    train = [t for t in trades if t["day"] < mid]
    oos = [t for t in trades if t["day"] >= mid]
    return train, oos


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("Expansion × Liquidity research (RESEARCH ONLY)", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df1 = _norm_1m(raw)
    days_all = sorted({str(ts.date()) for ts in df1.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    mid_day = days_sorted[n_days // 2]
    df1 = df1[[str(ts.date()) in keep for ts in df1.index]]
    print(f"window {day_lo}→{day_hi} n_days={n_days} OOS≥{mid_day}", flush=True)

    books = build_books(df1)
    print(f"books: { {k: len(v) for k, v in sorted(books.items())} }", flush=True)

    rows = []
    for name, trades in sorted(books.items()):
        train, oos = split_wf(trades, days_sorted)
        st, so, sf = summarize_R(train), summarize_R(oos), summarize_R(trades)
        for s, nd in ((st, n_days // 2), (so, n_days - n_days // 2), (sf, n_days)):
            s["cpd"] = round(s["n"] / nd, 2) if nd else 0.0
        v = verdict(st, so)
        rows.append({"book": name, "verdict": v, "full": sf, "train": st, "oos": so})
        print(
            f"  {name}: FULL {sf['n']}/{sf['hit']}%/{sf['exp_R']}R | "
            f"TR {st['n']}/{st['hit']}%/{st['exp_R']} | "
            f"OOS {so['n']}/{so['hit']}%/{so['exp_R']} t={so['t']} → {v}",
            flush=True,
        )

    proven = [r for r in rows if r["verdict"] == "PROVEN"]
    promising = [r for r in rows if r["verdict"] == "PROMISING"]
    ranked = sorted(
        proven + promising,
        key=lambda r: (r["oos"]["exp_R"] or -9, r["oos"]["hit"] or 0),
        reverse=True,
    )
    oos_rank = sorted(
        [r for r in rows if (r["oos"]["n"] or 0) >= 15],
        key=lambda r: (r["oos"]["exp_R"] or -9, r["oos"]["hit"] or 0),
        reverse=True,
    )

    # lift vs oracle baseline (same mode)
    lifts = []
    for mode in ("3r", "t15"):
        base_name = f"E_oracle_{mode}"
        base_row = next((r for r in rows if r["book"] == base_name), None)
        if not base_row:
            continue
        for filt in (f"E_oracle_sweep_{mode}", f"E_oracle_exp_{mode}", f"E_oracle_sweep_exp_{mode}"):
            fr = next((r for r in rows if r["book"] == filt), None)
            if not fr or not base_row["oos"]["hit"] or not fr["oos"]["hit"]:
                continue
            lifts.append(
                {
                    "mode": mode,
                    "filter": filt,
                    "base_oos_hit": base_row["oos"]["hit"],
                    "filt_oos_hit": fr["oos"]["hit"],
                    "hit_lift_pp": round(fr["oos"]["hit"] - base_row["oos"]["hit"], 2),
                    "base_oos_exp": base_row["oos"]["exp_R"],
                    "filt_oos_exp": fr["oos"]["exp_R"],
                    "exp_lift": round((fr["oos"]["exp_R"] or 0) - (base_row["oos"]["exp_R"] or 0), 3),
                    "filt_n_oos": fr["oos"]["n"],
                    "verdict": fr["verdict"],
                }
            )

    payload = {
        "ok": True,
        "research_only": True,
        "window": {"day_lo": day_lo, "day_hi": day_hi, "n_days": n_days, "oos_from": mid_day},
        "defs": {
            "expansion": f"body≥{EXP_ATR_K}×ATR14, body/range≥{EXP_BODY_FRAC}, close in extreme quartile",
            "sweep": f"wick beyond {SWEEP_LB}-bar extreme, close back inside",
            "fvg": "3-candle wick gap; entry at mid on first touch",
            "oracle": "textbook PRIORITY + EMA34 align (live Oracle spirit)",
        },
        "prove_rules": {
            "PROVEN": f"TRAIN+OOS n≥{MIN_N}, hit≥{MIN_HIT}%, exp_R≥{MIN_EXP}, OOS t≥{MIN_T}",
            "PROMISING": f"TRAIN+OOS n≥{SOFT_N}, hit≥{SOFT_HIT}%, exp_R≥{SOFT_EXP}",
        },
        "rows": rows,
        "lifts_vs_oracle": lifts,
        "proven": [r["book"] for r in proven],
        "promising": [r["book"] for r in promising],
        "best": ranked[0]["book"] if ranked else None,
        "took_sec": round(time.time() - t0, 1),
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# NIFTY 1m — Expansion candle × Liquidity",
        "",
        "> **RESEARCH ONLY.** Same PROVEN gate as `NIFTY_1M_PA_PROVEN_LOGIC`.",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days} sessions). OOS from **{mid_day}**.",
        "",
        "## Definitions",
        "",
        f"- **Expansion:** body ≥ {EXP_ATR_K}×ATR14, body/range ≥ {EXP_BODY_FRAC}, close in extreme 25% of bar.",
        f"- **Liquidity sweep:** wick beyond prior {SWEEP_LB}-bar high/low, close back inside.",
        "- **FVG entry:** after sweep+expansion, first touch of FVG mid.",
        "- **Oracle:** textbook pattern + EMA34 with-trend (live Scalper spirit).",
        "",
        "## Walk-forward results",
        "",
        "| Book | Verdict | Full n/hit/expR | Train | OOS n/hit/expR/t |",
        "|---|---|---|---|---|",
    ]
    order = sorted(
        rows,
        key=lambda r: (
            0 if r["verdict"] == "PROVEN" else 1 if r["verdict"] == "PROMISING" else 2,
            -(r["oos"]["exp_R"] or -9),
        ),
    )
    for r in order:
        f, tr, o = r["full"], r["train"], r["oos"]
        lines.append(
            f"| `{r['book']}` | **{r['verdict']}** | "
            f"{f['n']}/{f['hit']}%/{f['exp_R']} | "
            f"{tr['n']}/{tr['hit']}%/{tr['exp_R']} | "
            f"{o['n']}/{o['hit']}%/{o['exp_R']}/t={o['t']} |"
        )

    lines += ["", "## Lift vs Oracle (OOS)", ""]
    if lifts:
        lines += [
            "| Filter | Mode | Base hit → Filt hit | Δhit pp | Base exp → Filt exp | Δexp | n_oos | Verdict |",
            "|---|---|---|---:|---|---:|---:|---|",
        ]
        for L in sorted(lifts, key=lambda x: x["hit_lift_pp"], reverse=True):
            lines.append(
                f"| `{L['filter']}` | {L['mode']} | {L['base_oos_hit']}% → {L['filt_oos_hit']}% | "
                f"{L['hit_lift_pp']:+.1f} | {L['base_oos_exp']} → {L['filt_oos_exp']} | "
                f"{L['exp_lift']:+.3f} | {L['filt_n_oos']} | {L['verdict']} |"
            )
    else:
        lines.append("_No comparable Oracle filter rows._")

    lines += ["", "## Verdict", ""]
    if proven:
        lines.append("**PROVEN:** " + ", ".join(f"`{p}`" for p in proven))
        lines.append("Ship candidate = best OOS exp among PROVEN.")
    elif promising:
        lines.append("**No PROVEN.** PROMISING only — not live yet.")
        lines.append("Promising: " + ", ".join(f"`{p}`" for p in promising))
    else:
        lines.append("**NOT PROVEN.** No expansion×liquidity book cleared TRAIN+OOS floors.")

    if oos_rank:
        lines += ["", "### Best OOS by exp (n≥15, any verdict)", ""]
        for r in oos_rank[:8]:
            o = r["oos"]
            lines.append(
                f"- `{r['book']}` · {r['verdict']} · OOS {o['n']}/{o['hit']}%/{o['exp_R']}R t={o['t']}"
            )

    lines += [
        "",
        "## What this means",
        "",
        "1. Chasing the expansion close is usually the worst structural fill — we measure it explicitly (`A_exp_chase_*`).",
        "2. Sweep → expansion → FVG mid is the textbook ICT entry (`C_sweep_exp_fvg_*`).",
        "3. Most useful near-term path may be **Oracle ∩ liquidity/expansion filter** if lift is real and sample holds.",
        "4. Do **not** wire a new Scalper mode unless verdict = PROVEN.",
        "",
        f"_Generated in {payload['took_sec']}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    print(
        f"PROVEN={len(proven)} PROMISING={len(promising)} BEST={ranked[0]['book'] if ranked else None}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
