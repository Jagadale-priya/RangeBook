"""RESEARCH ONLY — Prove / reject PA BOS·CHoCH·FVG logic on NIFTY (walk-forward).

External evidence (Google, Nov 2026):
  - BOS or CHoCH alone ≈ zero edge (s4u: PF~1.00 on 9k+ trades)
  - CHoCH + FVG barely positive (PF 1.03)
  - Best published chain: liquidity sweep → CHoCH → retest (~38% @3R, PF 1.16)
  - Raw FVG 'hold' ≈ random band (TradingEdgeJournal ES/NQ)
  - Mechanical FVG mid/CE can be +EV only with size/displacement filters

House prove rules (this script):
  PASS only if TRAIN and OOS both:
    n≥30, hit@3R ≥35%, exp_R ≥0.20, and OOS t-score ≥1.5
  Soft PROMISING: OOS n≥20, hit≥32%, exp_R≥0.10, train exp_R>0
  else NOT PROVEN

  python -u prod_live/tests/builders/_diag_scalp_pa_proven_logic.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
from _diag_scalp_pa_bos_choch_fvg import (  # noqa: E402
    SESSION_OPEN_HI,
    SESSION_OPEN_LO,
    TRADE_HI,
    TRADE_LO,
    _norm_1m,
    build_htf_bias,
    detect_fvg,
    htf_bias_lookup,
    path_rr,
    structure_events,
    to_15m,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_PA_PROVEN_LOGIC.md"
REPORT_JSON = OUT / "NIFTY_1M_PA_PROVEN_LOGIC.json"

RR = 3.0
MAX_HOLD = 90
N_SESSIONS = 220  # ~1 trading year
LOOKBACK_CAL = 420

# Prove thresholds
MIN_N = 30
MIN_HIT = 35.0
MIN_EXP = 0.20
MIN_T = 1.5
SOFT_N, SOFT_HIT, SOFT_EXP = 20, 32.0, 0.10


def _mins(ts) -> int:
    return int(ts.hour * 60 + ts.minute)


def summarize_R(trades: List[dict]) -> Dict[str, Any]:
    if not trades:
        return {"n": 0, "hit": None, "exp_R": None, "t": None, "wins": 0, "cpd": None}
    wins = [t for t in trades if t.get("win")]
    rs = np.array([float(t["R"]) for t in trades], dtype=float)
    n = len(trades)
    mean = float(np.mean(rs))
    sd = float(np.std(rs, ddof=1)) if n > 1 else 0.0
    t = (mean / (sd / np.sqrt(n))) if sd > 1e-12 else (99.0 if mean > 0 else 0.0)
    return {
        "n": n,
        "hit": round(100.0 * len(wins) / n, 2),
        "exp_R": round(mean, 3),
        "t": round(t, 2),
        "wins": len(wins),
        "losses": n - len(wins),
        "avg_pts": round(float(np.mean([t["pts"] for t in trades])), 2),
    }


def verdict(train: Dict[str, Any], oos: Dict[str, Any]) -> str:
    def hard(s):
        return (
            s["n"] >= MIN_N
            and s["hit"] is not None
            and s["hit"] >= MIN_HIT
            and s["exp_R"] is not None
            and s["exp_R"] >= MIN_EXP
            and s["t"] is not None
            and s["t"] >= MIN_T
        )

    def soft(s):
        return (
            s["n"] >= SOFT_N
            and s["hit"] is not None
            and s["hit"] >= SOFT_HIT
            and s["exp_R"] is not None
            and s["exp_R"] >= SOFT_EXP
        )

    if hard(train) and hard(oos):
        return "PROVEN"
    if soft(train) and soft(oos) and (train["exp_R"] or 0) > 0 and (oos["exp_R"] or 0) > 0:
        return "PROMISING"
    return "NOT_PROVEN"


def score_row(h, l, c, entry_i, side, entry, sl, meta: dict) -> Optional[dict]:
    risk = abs(entry - sl)
    if risk < 2.0 or risk > 80.0:
        return None
    ok, reason, pts, _ = path_rr(h, l, c, entry_i, side, entry, sl, RR, max_bars=MAX_HOLD)
    R = float(RR if ok else -1.0)
    if reason == "exp":
        R = float(pts / risk) if risk else -1.0
        # clamp expired to [-1, RR]
        R = max(-1.0, min(RR, R))
    out = {
        **meta,
        "side": side,
        "entry": round(float(entry), 2),
        "sl": round(float(sl), 2),
        "risk": round(float(risk), 2),
        "win": bool(ok),
        "reason": reason,
        "pts": round(float(pts if ok else -risk), 2),
        "R": round(R, 3),
        "full_i": int(entry_i),
    }
    return out


def detect_sweeps(h, l, c, struct: List[dict], lookback=8) -> List[dict]:
    """Liquidity sweep: wick beyond recent swing, body closes back inside, before a CHoCH."""
    # Build running last swing high/low from structure confirmation times is hard;
    # approximate: for each bar, swing = max/min of prior lookback confirmed local extremes.
    sweeps = []
    n = len(c)
    for i in range(lookback + 2, n):
        prior_high = float(np.max(h[i - lookback : i]))
        prior_low = float(np.min(l[i - lookback : i]))
        # bullish sweep: wick below prior_low, close back above
        if float(l[i]) < prior_low and float(c[i]) > prior_low:
            sweeps.append({"i": i, "side": "BUY", "level": prior_low})
        # bearish sweep: wick above prior_high, close back below
        if float(h[i]) > prior_high and float(c[i]) < prior_high:
            sweeps.append({"i": i, "side": "SELL", "level": prior_high})
    return sweeps


def build_candidates(df1: pd.DataFrame, df15: pd.DataFrame) -> Dict[str, List[dict]]:
    """Generate scored trade lists for each candidate logic (causal, 1/day)."""
    o = df1["Open"].astype(float).values
    h = df1["High"].astype(float).values
    l = df1["Low"].astype(float).values
    c = df1["Close"].astype(float).values
    idx = df1.index
    day = np.array([str(ts.date()) for ts in idx])
    mins = np.array([_mins(ts) for ts in idx])

    struct15 = structure_events(df15)
    bias15 = build_htf_bias(df15, struct15)
    struct1 = structure_events(df1)
    fvgs = detect_fvg(o, h, l, c)
    choch = [e for e in struct1 if e["kind"] == "CHOCH"]
    bos = [e for e in struct1 if e["kind"] == "BOS"]
    sweeps = detect_sweeps(h, l, c, struct1)

    # index helpers
    fvg_by_side: Dict[str, List[dict]] = {"BUY": [], "SELL": []}
    for f in fvgs:
        fvg_by_side[f["side"]].append(f)

    def next_fvg(side, i0, within=30, min_size=1.5):
        for f in fvg_by_side[side]:
            if f["i_confirm"] <= i0:
                continue
            if f["i_confirm"] > i0 + within:
                return None
            if f["size"] < min_size:
                continue
            return f
        return None

    def pull_mid(f, d, max_wait=45):
        for j in range(f["i_confirm"] + 1, min(len(c), f["i_confirm"] + max_wait)):
            if day[j] != d:
                break
            if float(l[j]) <= f["mid"] <= float(h[j]):
                if f["side"] == "BUY":
                    sl = float(l[f["i_mid"]]) - 0.5
                else:
                    sl = float(h[f["i_mid"]]) + 0.5
                return j, float(f["mid"]), sl
        return None

    def htf_ok(ts, side) -> Tuple[bool, Optional[str]]:
        hb = htf_bias_lookup(bias15, ts)
        if hb is None:
            return False, None
        ok = (hb == "up" and side == "BUY") or (hb == "down" and side == "SELL")
        return ok, hb

    books: Dict[str, List[dict]] = defaultdict(list)
    used: Dict[str, set] = defaultdict(set)

    def take(book: str, d: str) -> bool:
        if d in used[book]:
            return False
        used[book].add(d)
        return True

    # ---- A: transcript CHoCH → FVG mid (HTF required) ----
    for ch in choch:
        i = int(ch["i"])
        if not (TRADE_LO <= mins[i] <= TRADE_HI) or mins[i] < SESSION_OPEN_LO:
            continue
        d = day[i]
        side = ch["side"]
        ok_htf, hb = htf_ok(idx[i], side)
        f = next_fvg(side, i)
        if f is None:
            continue
        got = pull_mid(f, d)
        if got is None:
            continue
        ei, entry, sl = got
        meta = {
            "book": "A_choch_fvg_htf",
            "day": d,
            "hm": idx[ei].strftime("%H:%M"),
            "htf": hb,
            "open_win": SESSION_OPEN_LO <= mins[i] <= SESSION_OPEN_HI,
            "fvg_size": round(f["size"], 2),
        }
        # ungated causal (for gate tests later) — still require HTF for this book
        if not ok_htf:
            # also store counter-htf separately
            row = score_row(h, l, c, ei, side, entry, sl, {**meta, "book": "A_choch_fvg_nohtf", "htf": hb})
            if row and take("A_choch_fvg_nohtf", d):
                books["A_choch_fvg_nohtf"].append(row)
            continue
        row = score_row(h, l, c, ei, side, entry, sl, meta)
        if row and take("A_choch_fvg_htf", d):
            books["A_choch_fvg_htf"].append(row)
            # gated clones
            if meta["open_win"] and take("A_open_only", d):
                books["A_open_only"].append({**row, "book": "A_open_only"})
            if f["size"] >= 5.0 and take("A_fvg5", d):
                books["A_fvg5"].append({**row, "book": "A_fvg5"})
            if meta["open_win"] and f["size"] >= 4.0 and take("A_open_fvg4", d):
                books["A_open_fvg4"].append({**row, "book": "A_open_fvg4"})
            if 5.0 <= row["risk"] <= 25.0 and take("A_risk5_25", d):
                books["A_risk5_25"].append({**row, "book": "A_risk5_25"})

    # ---- B: ICT CHoCH + confirming BOS → FVG (HTF) ----
    for ch in choch:
        i = int(ch["i"])
        if not (TRADE_LO <= mins[i] <= TRADE_HI) or mins[i] < SESSION_OPEN_LO:
            continue
        d = day[i]
        side = ch["side"]
        ok_htf, hb = htf_ok(idx[i], side)
        if not ok_htf:
            continue
        conf = None
        for b in bos:
            if b["i"] <= i:
                continue
            if b["side"] != side:
                continue
            if b["i"] > i + 40:
                break
            conf = b
            break
        if conf is None:
            continue
        f = next_fvg(side, int(conf["i"]))
        if f is None:
            continue
        got = pull_mid(f, d)
        if got is None:
            continue
        ei, entry, sl = got
        row = score_row(
            h,
            l,
            c,
            ei,
            side,
            entry,
            sl,
            {"book": "B_choch_bos_fvg", "day": d, "hm": idx[ei].strftime("%H:%M"), "htf": hb},
        )
        if row and take("B_choch_bos_fvg", d):
            books["B_choch_bos_fvg"].append(row)

    # ---- C: BOS continuation → FVG (HTF) ----
    for b in bos:
        i = int(b["i"])
        if not (TRADE_LO <= mins[i] <= TRADE_HI) or mins[i] < SESSION_OPEN_LO:
            continue
        d = day[i]
        side = b["side"]
        ok_htf, hb = htf_ok(idx[i], side)
        if not ok_htf:
            continue
        f = next_fvg(side, i, min_size=2.0)
        if f is None:
            continue
        # displacement proxy: mid candle range ≥ 1.2x median of last 20 ranges
        mid = f["i_mid"]
        ranges = h[max(0, mid - 20) : mid] - l[max(0, mid - 20) : mid]
        med = float(np.median(ranges)) if len(ranges) else 0.0
        disp = (float(h[mid]) - float(l[mid])) >= 1.2 * med if med > 0 else True
        got = pull_mid(f, d)
        if got is None:
            continue
        ei, entry, sl = got
        row = score_row(
            h,
            l,
            c,
            ei,
            side,
            entry,
            sl,
            {
                "book": "C_bos_fvg",
                "day": d,
                "hm": idx[ei].strftime("%H:%M"),
                "htf": hb,
                "disp": disp,
            },
        )
        if row and take("C_bos_fvg", d):
            books["C_bos_fvg"].append(row)
            if disp and take("C_bos_fvg_disp", d):
                books["C_bos_fvg_disp"].append({**row, "book": "C_bos_fvg_disp"})

    # ---- D: CHoCH break+retest (HTF) ----
    for ch in choch:
        i = int(ch["i"])
        if not (TRADE_LO <= mins[i] <= TRADE_HI) or mins[i] < SESSION_OPEN_LO:
            continue
        d = day[i]
        side = ch["side"]
        level = float(ch["level"])
        ok_htf, hb = htf_ok(idx[i], side)
        if not ok_htf:
            continue
        away = False
        ei = None
        entry = sl = None
        for j in range(i + 1, min(len(c), i + 60)):
            if day[j] != d:
                break
            if side == "SELL":
                if float(h[j]) < level - 2.0:
                    away = True
                if away and float(h[j]) >= level:
                    ei, entry, sl = j, level, float(h[j]) + 0.5
                    break
            else:
                if float(l[j]) > level + 2.0:
                    away = True
                if away and float(l[j]) <= level:
                    ei, entry, sl = j, level, float(l[j]) - 0.5
                    break
        if ei is None:
            continue
        row = score_row(
            h,
            l,
            c,
            ei,
            side,
            entry,
            sl,
            {"book": "D_choch_retest", "day": d, "hm": idx[ei].strftime("%H:%M"), "htf": hb},
        )
        if row and take("D_choch_retest", d):
            books["D_choch_retest"].append(row)

    # ---- E: EXTERNAL BEST — sweep → CHoCH → retest (HTF) ----
    # Find CHoCH that follows a same-side sweep within 20 bars, then retest CHoCH level
    for ch in choch:
        i = int(ch["i"])
        if not (TRADE_LO <= mins[i] <= TRADE_HI) or mins[i] < SESSION_OPEN_LO:
            continue
        d = day[i]
        side = ch["side"]
        ok_htf, hb = htf_ok(idx[i], side)
        if not ok_htf:
            continue
        # prior sweep same direction within 20 bars
        sw = None
        for s in sweeps:
            if s["i"] >= i:
                break
            if i - s["i"] > 20:
                continue
            if s["side"] != side:
                continue
            sw = s
        if sw is None:
            continue
        level = float(ch["level"])
        away = False
        ei = entry = sl = None
        for j in range(i + 1, min(len(c), i + 60)):
            if day[j] != d:
                break
            if side == "SELL":
                if float(h[j]) < level - 2.0:
                    away = True
                if away and float(h[j]) >= level:
                    ei, entry, sl = j, level, float(h[j]) + 0.5
                    break
            else:
                if float(l[j]) > level + 2.0:
                    away = True
                if away and float(l[j]) <= level:
                    ei, entry, sl = j, level, float(l[j]) - 0.5
                    break
        if ei is None:
            continue
        row = score_row(
            h,
            l,
            c,
            ei,
            side,
            entry,
            sl,
            {
                "book": "E_sweep_choch_retest",
                "day": d,
                "hm": idx[ei].strftime("%H:%M"),
                "htf": hb,
            },
        )
        if row and take("E_sweep_choch_retest", d):
            books["E_sweep_choch_retest"].append(row)
            # also FVG mid after sweep+CHoCH
            f = next_fvg(side, i, min_size=2.0)
            if f is not None:
                got = pull_mid(f, d)
                if got is not None:
                    ei2, entry2, sl2 = got
                    row2 = score_row(
                        h,
                        l,
                        c,
                        ei2,
                        side,
                        entry2,
                        sl2,
                        {
                            "book": "E2_sweep_choch_fvg",
                            "day": d,
                            "hm": idx[ei2].strftime("%H:%M"),
                            "htf": hb,
                        },
                    )
                    if row2 and take("E2_sweep_choch_fvg", d):
                        books["E2_sweep_choch_fvg"].append(row2)

    return dict(books)


def split_wf(trades: List[dict], days_sorted: List[str]) -> Tuple[List[dict], List[dict]]:
    if not days_sorted:
        return [], []
    mid = days_sorted[len(days_sorted) // 2]
    train = [t for t in trades if t["day"] < mid]
    oos = [t for t in trades if t["day"] >= mid]
    return train, oos


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("PA PROVEN-LOGIC research (RESEARCH ONLY)", flush=True)
    print(
        "External: BOS/CHoCH alone≈0 edge; sweep→CHoCH→retest best published (~38%@3R PF1.16)",
        flush=True,
    )

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
    df15 = to_15m(df1)
    print(f"window {day_lo}→{day_hi} n_days={n_days} mid(OOS≥)={mid_day}", flush=True)

    books = build_candidates(df1, df15)
    print(f"books built: { {k: len(v) for k, v in books.items()} }", flush=True)

    rows = []
    for name, trades in sorted(books.items(), key=lambda kv: kv[0]):
        train, oos = split_wf(trades, days_sorted)
        st, so = summarize_R(train), summarize_R(oos)
        sf = summarize_R(trades)
        v = verdict(st, so)
        # attach cpd
        for s, nd in ((st, n_days // 2), (so, n_days - n_days // 2), (sf, n_days)):
            s["cpd"] = round(s["n"] / nd, 2) if nd else 0.0
        rows.append(
            {
                "book": name,
                "verdict": v,
                "full": sf,
                "train": st,
                "oos": so,
            }
        )
        print(
            f"  {name}: FULL n={sf['n']} hit={sf['hit']}% exp={sf['exp_R']} | "
            f"TRAIN {st['n']}/{st['hit']}%/{st['exp_R']}R | "
            f"OOS {so['n']}/{so['hit']}%/{so['exp_R']}R t={so['t']} → {v}",
            flush=True,
        )

    proven = [r for r in rows if r["verdict"] == "PROVEN"]
    promising = [r for r in rows if r["verdict"] == "PROMISING"]
    # rank promising/proven by OOS exp then hit
    ranked = sorted(
        proven + promising,
        key=lambda r: (r["oos"]["exp_R"] or -9, r["oos"]["hit"] or 0, r["oos"]["n"]),
        reverse=True,
    )
    best = ranked[0] if ranked else None
    # also show best OOS by exp among n≥20 even if NOT_PROVEN
    oos_rank = sorted(
        [r for r in rows if (r["oos"]["n"] or 0) >= 15],
        key=lambda r: (r["oos"]["exp_R"] or -9, r["oos"]["hit"] or 0),
        reverse=True,
    )

    payload = {
        "ok": True,
        "research_only": True,
        "window": {"day_lo": day_lo, "day_hi": day_hi, "n_days": n_days, "oos_from": mid_day},
        "prove_rules": {
            "PROVEN": f"TRAIN+OOS: n≥{MIN_N}, hit@3R≥{MIN_HIT}%, exp_R≥{MIN_EXP}, OOS t≥{MIN_T}",
            "PROMISING": f"TRAIN+OOS: n≥{SOFT_N}, hit≥{SOFT_HIT}%, exp_R≥{SOFT_EXP}, both exp>0",
            "else": "NOT_PROVEN",
            "target": f"{RR}R path, hold≤{MAX_HOLD}m, 1/day",
        },
        "external_evidence": {
            "bos_choch_alone": "≈ zero edge (s4u 9k+ trades PF~1.00)",
            "choch_fvg": "barely +EV PF 1.03 (s4u)",
            "best_chain": "liquidity sweep → CHoCH → retest: ~38.2%@3R PF1.16 +0.095R (s4u 2209 trades)",
            "fvg_hold_vs_random": "FVG hold ≈ random band on ES/NQ (TradingEdgeJournal)",
            "fvg_mechanical": "Valid FVG retrace ~38% WR +0.29R on DXY daily (DoesItRepeat) with filters",
            "urls": [
                "https://s4u.pro/en/bos-choch-strategy/",
                "https://doesitrepeat.com/blog/ict-fair-value-gap-backtest",
                "https://tradingedgejournal.com/blog/do-fair-value-gaps-work/",
                "https://doesitrepeat.com/blog/ict-strategy-guide-backtest",
            ],
        },
        "books": rows,
        "proven": [r["book"] for r in proven],
        "promising": [r["book"] for r in promising],
        "best": best,
        "oos_rank_top": oos_rank[:5],
        "took_sec": round(time.time() - t0, 1),
    }

    lines = [
        "# NIFTY — PA **PROVEN LOGIC** gate (BOS / CHoCH / FVG)",
        "",
        "> **RESEARCH ONLY.** No Scalper mode ships until verdict = **PROVEN**.",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days} sessions). Walk-forward split OOS from **{mid_day}**.",
        f"Target **{RR}R**, hold ≤{MAX_HOLD}m, **1 trade/day**.",
        "",
        "## 0) External evidence (must shape what we test)",
        "",
        "| Claim | Evidence | Implication |",
        "|---|---|---|",
        "| BOS / CHoCH alone | ~0 edge, PF≈1.00 on 9k+ trades ([s4u](https://s4u.pro/en/bos-choch-strategy/)) | Structure signal ≠ entry |",
        "| CHoCH + FVG | PF 1.03 | Too weak to ship alone |",
        "| **Sweep → CHoCH → retest** | 38.2%@3R, PF 1.16, +0.095R / 2209 trades ([s4u](https://s4u.pro/en/bos-choch-strategy/)) | Best published chain |",
        "| FVG 'hold' rate | ≈ random band on ES/NQ ([TEJ](https://tradingedgejournal.com/blog/do-fair-value-gaps-work/)) | Need structure + filters, not bare FVG |",
        "| Filtered FVG retrace | ~38% WR, +0.29R on DXY ([DoesItRepeat](https://doesitrepeat.com/blog/ict-fair-value-gap-backtest)) | Size/validity filters matter |",
        "",
        "Prior 44d sample (41.7%@3R, n=12) is **insufficient** — below prove floor.",
        "",
        "## 1) Prove rules (this repo)",
        "",
        f"- **PROVEN:** TRAIN + OOS each `n≥{MIN_N}`, hit@3R `≥{MIN_HIT}%`, exp_R `≥{MIN_EXP}`, OOS t-score `≥{MIN_T}`",
        f"- **PROMISING:** TRAIN + OOS each `n≥{SOFT_N}`, hit `≥{SOFT_HIT}%`, exp_R `≥{SOFT_EXP}`, both exp>0",
        "- Else **NOT_PROVEN** — do not wire live.",
        "",
        "## 2) Walk-forward results",
        "",
        "| Book | Verdict | Full n/hit/expR | Train n/hit/expR | OOS n/hit/expR/t |",
        "|---|---|---|---|---|",
    ]

    order = sorted(rows, key=lambda r: (0 if r["verdict"] == "PROVEN" else 1 if r["verdict"] == "PROMISING" else 2, -(r["oos"]["exp_R"] or -9)))
    for r in order:
        f, tr, o = r["full"], r["train"], r["oos"]
        lines.append(
            f"| `{r['book']}` | **{r['verdict']}** | "
            f"{f['n']}/{f['hit']}%/{f['exp_R']} | "
            f"{tr['n']}/{tr['hit']}%/{tr['exp_R']} | "
            f"{o['n']}/{o['hit']}%/{o['exp_R']}/t={o['t']} |"
        )

    lines += ["", "## 3) Verdict", ""]
    if proven:
        lines.append(f"**PROVEN books:** {', '.join('`'+p['book']+'`' for p in proven)}")
        lines.append("")
        lines.append("Ship candidate = best OOS exp among PROVEN.")
    elif promising:
        lines.append("**No PROVEN book.** PROMISING only — needs more sample / tighter gate before live.")
        lines.append(f"Top promising: `{best['book']}` OOS hit={best['oos']['hit']}% exp={best['oos']['exp_R']}R n={best['oos']['n']}")
    else:
        lines.append("**NOT PROVEN.** No book cleared TRAIN+OOS floors on this 1Y NIFTY walk-forward.")
        if oos_rank:
            top = oos_rank[0]
            lines.append(
                f"Closest OOS (n≥15): `{top['book']}` hit={top['oos']['hit']}% exp={top['oos']['exp_R']}R "
                f"n={top['oos']['n']} t={top['oos']['t']} — still **not** shippable."
            )

    lines += [
        "",
        "## 4) What this means vs the transcript",
        "",
        "1. The transcript framework is **conceptually correct** (direction → confirm → invalidate).",
        "2. It is **not automatically a proven NIFTY 1m entry model** — external + our WF both say bare CHoCH/FVG is thin.",
        "3. If anything can prove, it should be the **sweep → CHoCH → retest** chain (or a gated FVG mid with HTF+size), not more indicators.",
        "4. Oracle T15 clean remains the **existing proven-ish Scalper path** (hindsight path-wins ∩ TierAB); PA is a separate causal track.",
        "5. Do **not** flip Scalper default until a book is **PROVEN** here.",
        "",
        f"_Generated in {payload['took_sec']}s._",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    print(
        f"PROVEN={len(proven)} PROMISING={len(promising)} BEST={best['book'] if best else None}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
