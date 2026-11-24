"""RESEARCH ONLY — Double Top SECOND LEG DOWN prove hunt.

User structure (exact):
  1) Push to high (H1 / HH attempt)
  2) First move DOWN (valley) — NOT the trade
  3) Push UP again (H2 / second attempt into supply)
  4) SECOND move DOWN with strength — THIS is the setup

Setups (all require confirmed strong 2nd leg after H2):
  A) leg2      — short next open after strong 2nd-leg expansion (neck break)
  B) leg2_retest — after leg2, leave MA then retest MA from below → short next open

  python -u prod_live/tests/builders/_diag_scalp_dt_ma_retest_prove.py
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
sys.path[:0] = [str(ROOT), str(BUILDERS), str(ROOT / "tools" / "research")]
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
from _diag_scalp_pa_bos_choch_fvg import _norm_1m, path_rr  # noqa: E402
from _diag_scalp_pa_proven_logic import (  # noqa: E402
    LOOKBACK_CAL,
    MAX_HOLD,
    MIN_EXP,
    MIN_HIT,
    MIN_N,
    MIN_T,
    N_SESSIONS,
    summarize_R,
    verdict,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_DT_H2_NOBREAK_PROVE.md"
REPORT_JSON = OUT / "NIFTY_1M_DT_H2_NOBREAK_PROVE.json"

TRADE_LO = 9 * 60 + 20
TRADE_HI = 14 * 60 + 45
SWING_L = 3
SL_GRID = (6.0, 8.0, 10.0, 12.0, 15.0, 20.0)
T_GRID = (12.0, 15.0, 18.0, 20.0, 25.0, 30.0, 40.0)
MA_SPANS = (20, 34)
DT_TOL_ATR = (0.35, 0.55, 0.80)
VALLEY_ATR_MIN = 0.50
# strong 2nd leg expansion
LEG2_BODY_ATR = (0.85, 1.0)
LEG2_BODY_FRAC = 0.55
LEAVE_ATR = 0.35
TOUCH_ATR = 0.25
RETEST_MAX_BARS = 45
LEG2_MAX_BARS = 50


def _mins(ts) -> int:
    return int(ts.hour) * 60 + int(ts.minute)


def atr14(h, l, c) -> np.ndarray:
    prev = np.roll(c, 1)
    prev[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))
    return pd.Series(tr).rolling(14, min_periods=1).mean().to_numpy(dtype=float)


def swing_highs(h: np.ndarray, L: int = SWING_L) -> List[Tuple[int, float]]:
    out = []
    for i in range(L, len(h) - L):
        w = h[i - L : i + L + 1]
        if h[i] >= np.max(w) - 1e-12:
            out.append((i, float(h[i])))
    return out


def detect_double_tops(h, l, atr, tol_atr: float) -> List[dict]:
    """H1 → 1st down → H2≤H1 (NO break of H1). If H2 breaks H1 → not a setup."""
    sh = swing_highs(h)
    dts = []
    for a in range(len(sh) - 1):
        i1, p1 = sh[a]
        for b in range(a + 1, min(a + 12, len(sh))):
            i2, p2 = sh[b]
            if i2 - i1 < 8 or i2 - i1 > 100:
                continue
            a_ref = float(atr[i2]) if np.isfinite(atr[i2]) else 8.0
            tol = max(4.0, tol_atr * a_ref)
            # STRICT: H2 must NOT break H1 (allow 0.5pt tick only)
            if p2 > p1 + 0.5:
                continue
            # H2 must still be a real second push near H1 (not a weak lower high far away)
            if p1 - p2 > tol:
                continue
            valley_i = int(i1 + np.argmin(l[i1 : i2 + 1]))
            valley = float(l[valley_i])
            # first move down must be real (valley between peaks)
            if valley_i <= i1 + 2 or valley_i >= i2 - 2:
                continue
            depth = min(p1, p2) - valley
            if depth < VALLEY_ATR_MIN * a_ref:
                continue
            # require bounce from valley up into H2 (second up-leg)
            bounce = p2 - valley
            if bounce < VALLEY_ATR_MIN * a_ref:
                continue
            # between valley and H2, never break H1
            if float(np.max(h[valley_i : i2 + 1])) > p1 + 0.5:
                continue
            dts.append(
                {
                    "i1": i1,
                    "i2": i2,
                    "valley_i": valley_i,
                    "p1": round(p1, 2),
                    "p2": round(p2, 2),
                    "neck": round(valley, 2),
                    "tol": round(tol, 2),
                    # swing H2 confirmed; 2nd leg search starts after confirm
                    "confirm_i": i2 + SWING_L,
                }
            )
            break
    return dts


def is_strong_bear_leg(o, h, l, c, atr, i: int, body_atr_k: float) -> bool:
    """Strong 2nd move down candle (expansion / displacement)."""
    rng = float(h[i] - l[i])
    if rng < 1e-9:
        return False
    body = float(c[i] - o[i])
    if body >= 0:
        return False
    abs_body = abs(body)
    a = float(atr[i]) if np.isfinite(atr[i]) else 0.0
    if a < 1e-9 or abs_body < body_atr_k * a:
        return False
    if abs_body / rng < LEG2_BODY_FRAC:
        return False
    pos = (float(c[i]) - float(l[i])) / rng
    # close in lower quartile of range
    if pos > 0.25:
        return False
    return True


def one_per_day(trades: List[dict]) -> List[dict]:
    best: Dict[str, dict] = {}
    for t in trades:
        d = t["day"]
        if d not in best or t["i_entry"] < best[d]["i_entry"]:
            best[d] = t
    return [best[k] for k in sorted(best)]


def split_wf(trades: List[dict], days_sorted: List[str]) -> Tuple[List[dict], List[dict]]:
    mid = days_sorted[len(days_sorted) // 2]
    tr = [t for t in trades if t["day"] < mid]
    oos = [t for t in trades if t["day"] >= mid]
    return tr, oos


def score_fixed(
    h, l, c, i_entry: int, side: str, entry: float, sl_pts: float, t1: float
) -> Optional[dict]:
    if side != "SELL":
        return None
    sl = entry + sl_pts
    risk = sl_pts
    rr = t1 / risk
    ok, reason, pts, j = path_rr(h, l, c, i_entry, side, entry, sl, rr, max_bars=MAX_HOLD)
    if ok:
        R = t1 / risk
    elif reason == "sl":
        R = -1.0
        pts = -risk
    else:
        R = float(pts) / risk if risk > 1e-9 else 0.0
    return {
        "win": bool(ok),
        "reason": reason,
        "pts": round(float(pts), 2),
        "R": round(float(R), 3),
        "sl": round(sl, 2),
        "tp": round(entry - t1, 2),
        "sl_pts": sl_pts,
        "t1": t1,
        "exit_i": j,
    }


def mfe_mae_sell(h, l, c, i_entry: int, entry: float, max_bars: int = MAX_HOLD) -> dict:
    mae = 0.0
    mfe = 0.0
    end = min(len(c) - 1, i_entry + max_bars)
    for j in range(i_entry + 1, end + 1):
        mae = max(mae, float(h[j]) - entry)
        mfe = max(mfe, entry - float(l[j]))
    return {"mae": round(mae, 2), "mfe": round(mfe, 2)}


def build_signals(
    df: pd.DataFrame,
    ema: np.ndarray,
    atr: np.ndarray,
    dts: List[dict],
    ma_span: int,
    body_atr_k: float,
) -> Dict[str, List[dict]]:
    """
    Only enter after SECOND move down is confirmed.
    First valley (H1→neck) is structure only — never an entry trigger.
    """
    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    idx = df.index
    day = np.array([str(ts.date()) for ts in idx])
    mins = np.array([_mins(ts) for ts in idx])
    n = len(c)

    leg2_raw: List[dict] = []
    ret_raw: List[dict] = []
    used = set()

    for dt in dts:
        confirm = int(dt["confirm_i"])
        if confirm >= n - 3:
            continue
        neck = float(dt["neck"])
        i2 = int(dt["i2"])
        p1 = float(dt["p1"])
        key = (day[i2], round(dt["p1"], 1), round(dt["p2"], 1), round(neck, 1))
        if key in used:
            continue

        # --- find strong SECOND leg down AFTER H2 ---
        # Rule: if ANY high breaks H1 after H2 → setup INVALID (no trade)
        leg2_i = None
        invalidated = False
        for i in range(max(confirm, i2 + 1), min(n - 2, confirm + LEG2_MAX_BARS)):
            if float(h[i]) > p1 + 0.5:
                invalidated = True
                break
            if not (TRADE_LO <= mins[i] <= TRADE_HI):
                continue
            if i <= i2:
                continue
            # must be turning down after H2 (close below H2 / below prior bar high zone)
            if float(c[i]) >= float(dt["p2"]):
                continue
            if not is_strong_bear_leg(o, h, l, c, atr, i, body_atr_k):
                continue
            e = float(ema[i]) if np.isfinite(ema[i]) else float(c[i])
            under_ma = float(c[i]) < e
            if not under_ma:
                continue
            if float(c[i]) > neck and float(l[i]) >= neck:
                continue
            # 2nd leg must push down into/through neck
            if float(l[i]) > neck + 0.15 * (float(atr[i]) if np.isfinite(atr[i]) else 8.0):
                continue
            leg2_i = i
            break

        if invalidated or leg2_i is None:
            continue
        used.add(key)

        # Setup A — short next open after strong 2nd leg candle
        ei = leg2_i + 1
        if ei < n and TRADE_LO <= mins[ei] <= TRADE_HI:
            leg2_raw.append(
                {
                    "setup": "leg2",
                    "side": "SELL",
                    "i_sig": leg2_i,
                    "i_entry": ei,
                    "entry": float(o[ei]),
                    "day": day[ei],
                    "neck": neck,
                    "p1": dt["p1"],
                    "p2": dt["p2"],
                    "ma_span": ma_span,
                    "body_k": body_atr_k,
                    "t": str(idx[ei]),
                }
            )

        # Setup B — after 2nd leg, MA retest from below (premium supply)
        # still invalidate if H1 breaks before retest entry
        left = False
        for i in range(leg2_i + 1, min(n - 2, leg2_i + RETEST_MAX_BARS)):
            if float(h[i]) > p1 + 0.5:
                break  # H1 broken → no setup
            if not (TRADE_LO <= mins[i] <= TRADE_HI):
                continue
            e = float(ema[i]) if np.isfinite(ema[i]) else float(c[i])
            a = float(atr[i]) if np.isfinite(atr[i]) else 8.0
            if float(c[i]) > e + TOUCH_ATR * a:
                break  # reclaim cancels
            if float(h[i]) < e - LEAVE_ATR * a:
                left = True
                continue
            if left and float(h[i]) >= e - TOUCH_ATR * a and float(c[i]) < e:
                rng = max(float(h[i] - l[i]), 0.05)
                loc = (float(c[i]) - float(l[i])) / rng
                if float(c[i]) <= float(o[i]) or loc <= 0.45:
                    ei = i + 1
                    if ei < n and TRADE_LO <= mins[ei] <= TRADE_HI:
                        ret_raw.append(
                            {
                                "setup": "leg2_retest",
                                "side": "SELL",
                                "i_sig": i,
                                "i_entry": ei,
                                "entry": float(o[ei]),
                                "day": day[ei],
                                "neck": neck,
                                "p1": dt["p1"],
                                "p2": dt["p2"],
                                "ma_span": ma_span,
                                "body_k": body_atr_k,
                                "t": str(idx[ei]),
                            }
                        )
                    break

    return {"leg2": leg2_raw, "leg2_retest": ret_raw}


def eval_book(
    raw: List[dict],
    h, l, c,
    days_sorted: List[str],
    tag: str,
    sl_pts: float,
    t1: float,
) -> Optional[Dict[str, Any]]:
    scored = []
    maes, mfes = [], []
    for r in raw:
        sc = score_fixed(h, l, c, r["i_entry"], r["side"], r["entry"], sl_pts, t1)
        if sc is None:
            continue
        mm = mfe_mae_sell(h, l, c, r["i_entry"], r["entry"])
        maes.append(mm["mae"])
        mfes.append(mm["mfe"])
        scored.append({**r, **sc, **mm})
    scored = one_per_day(scored)
    if len(scored) < 40:
        return None
    tr, oos = split_wf(scored, days_sorted)
    st, so = summarize_R(tr), summarize_R(oos)
    if st["n"] < 25 or so["n"] < 25:
        return None
    v = verdict(st, so)
    return {
        "book": tag,
        "verdict": v,
        "n": len(scored),
        "train": st,
        "oos": so,
        "sl_pts": sl_pts,
        "t1": t1,
        "mae_p80": round(float(np.percentile(maes, 80)), 2) if maes else None,
        "mfe_p50": round(float(np.percentile(mfes, 50)), 2) if mfes else None,
        "mfe_p80": round(float(np.percentile(mfes, 80)), 2) if mfes else None,
    }


def best_pack(rows: List[dict]) -> Dict[str, Any]:
    if not rows:
        return {}
    pr = [r for r in rows if r["verdict"] == "PROVEN"]
    pool = pr or rows
    best = max(pool, key=lambda r: (r["oos"]["exp_R"] or -9, r["oos"]["hit"] or 0))
    if pr:
        max_sl = max(pr, key=lambda r: r["sl_pts"])
        min_sl = min(pr, key=lambda r: r["sl_pts"])
        max_t = max(pr, key=lambda r: r["t1"])
        best_r = max(pr, key=lambda r: r["oos"]["exp_R"] or -9)
    else:
        max_sl = min_sl = max_t = best_r = best
    return {
        "best_book": best["book"],
        "best_verdict": best["verdict"],
        "best_oos": best["oos"],
        "max_sl_proven": max_sl["sl_pts"] if pr else None,
        "min_sl_proven": min_sl["sl_pts"] if pr else None,
        "max_t_proven": max_t["t1"] if pr else None,
        "best_R_book": best_r["book"],
        "mae_p80": best.get("mae_p80"),
        "mfe_p50": best.get("mfe_p50"),
        "mfe_p80": best.get("mfe_p80"),
        "n_proven": len(pr),
        "n_tested": len(rows),
    }


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("DT STRICT: H1 top · H2 must NOT break H1 · then down only", flush=True)
    print("If H2 breaks H1 (or later breaks H1) → NO SETUP", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df = _norm_1m(raw)
    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:])
    days_sorted = sorted(keep)
    mid = days_sorted[len(days_sorted) // 2]
    df = df[[str(ts.date()) in keep for ts in df.index]].copy()
    print(f"window {days_sorted[0]} → {days_sorted[-1]} · OOS from {mid} · bars={len(df)}", flush=True)

    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    atr = atr14(h, l, c)

    books: List[Dict[str, Any]] = []
    signal_stats = []

    for ma_span in MA_SPANS:
        ema = df["Close"].astype(float).ewm(span=ma_span, adjust=False).mean().to_numpy(dtype=float)
        for tol in DT_TOL_ATR:
            dts = detect_double_tops(h, l, atr, tol)
            for body_k in LEG2_BODY_ATR:
                sigs = build_signals(df, ema, atr, dts, ma_span, body_k)
                signal_stats.append(
                    {
                        "ma": ma_span,
                        "tol": tol,
                        "body_k": body_k,
                        "dts": len(dts),
                        "leg2": len(sigs["leg2"]),
                        "leg2_retest": len(sigs["leg2_retest"]),
                    }
                )
                print(
                    f"EMA{ma_span} tol{tol} k{body_k}: DT={len(dts)} "
                    f"leg2={len(sigs['leg2'])} retest={len(sigs['leg2_retest'])}",
                    flush=True,
                )
                for setup, raw_list in sigs.items():
                    for sl_pts in SL_GRID:
                        for t1 in T_GRID:
                            tag = (
                                f"SELL_{setup}_ema{ma_span}_tol{int(tol*100)}"
                                f"_k{int(body_k*100)}_sl{int(sl_pts)}_t{int(t1)}"
                            )
                            row = eval_book(raw_list, h, l, c, days_sorted, tag, sl_pts, t1)
                            if row:
                                books.append(row)

    books.sort(
        key=lambda r: (
            0 if r["verdict"] == "PROVEN" else 1 if r["verdict"] == "PROMISING" else 2,
            -(r["oos"]["exp_R"] or -9),
            -(r["oos"]["hit"] or 0),
        )
    )
    proven = [b for b in books if b["verdict"] == "PROVEN"]
    promising = [b for b in books if b["verdict"] == "PROMISING"]

    by_setup: Dict[str, List[dict]] = {"leg2": [], "leg2_retest": []}
    for b in books:
        if "_leg2_retest_" in b["book"]:
            by_setup["leg2_retest"].append(b)
        elif "_leg2_" in b["book"]:
            by_setup["leg2"].append(b)
    setup_summary = {k: best_pack(v) for k, v in by_setup.items()}

    payload = {
        "mode": "research_only",
        "logic": "double_top_SECOND_LEG_down_only",
        "structure": "H1 -> first_down(valley) -> H2 -> strong_second_down -> entry",
        "note": "First valley is NEVER an entry. Only 2nd move after H2.",
        "window": {"start": days_sorted[0], "end": days_sorted[-1], "oos_from": mid},
        "gates": {"MIN_N": MIN_N, "MIN_HIT": MIN_HIT, "MIN_EXP": MIN_EXP, "MIN_T": MIN_T},
        "signal_stats": signal_stats,
        "n_books": len(books),
        "n_proven": len(proven),
        "n_promising": len(promising),
        "setup_summary": setup_summary,
        "top": books[:40],
        "proven": proven[:30],
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# NIFTY 1m — Double Top **H2 must NOT break H1** · then down",
        "",
        "> **RESEARCH ONLY.** If H2 breaks H1 → NO SETUP. After H2 must go down only.",
        "",
        f"Window **{days_sorted[0]} → {days_sorted[-1]}** · OOS from **{mid}**.",
        "",
        "## Structure (required — strict)",
        "",
        "```",
        "H1 (top)",
        "  └─ 1st move DOWN → neck        ← NOT a trade",
        "H2 ≤ H1 (must NOT break H1)",
        "  └─ if any high > H1 → INVALID",
        "  └─ 2nd move DOWN with strength ← ONLY then entry",
        "```",
        "",
        "Strong 2nd leg = bearish expansion (body≥k×ATR, body/range≥0.55, close in lower quartile),",
        "under EMA, piercing/breaking neckline. H1 break at any point before entry cancels.",
        "",
        f"## Result: **{len(proven)} PROVEN** · **{len(promising)} PROMISING** · {len(books)} books",
        "",
    ]
    for setup, pack in setup_summary.items():
        lines.append(f"### Setup `{setup}`")
        if not pack:
            lines.append("- no scored books\n")
            continue
        lines.append(f"- tested: {pack.get('n_tested')} · proven: {pack.get('n_proven')}")
        lines.append(f"- best: `{pack.get('best_book')}` · {pack.get('best_verdict')} · OOS {pack.get('best_oos')}")
        lines.append(
            f"- **max SL PROVEN**: {pack.get('max_sl_proven')} · **min SL**: {pack.get('min_sl_proven')} · **max T**: {pack.get('max_t_proven')}"
        )
        lines.append(
            f"- MAE80≈{pack.get('mae_p80')} · MFE50≈{pack.get('mfe_p50')} · MFE80≈{pack.get('mfe_p80')}"
        )
        lines.append("")

    lines += [
        "## Top books",
        "",
        "| Book | Verdict | Train n/hit/exp | OOS n/hit/exp/t | MAE80 | MFE50 |",
        "|---|---|---|---|---|---|",
    ]
    for b in books[:25]:
        tr, so = b["train"], b["oos"]
        lines.append(
            f"| `{b['book']}` | **{b['verdict']}** | "
            f"{tr['n']}/{tr['hit']}%/{tr['exp_R']} | "
            f"{so['n']}/{so['hit']}%/{so['exp_R']}/t={so['t']} | "
            f"{b.get('mae_p80')} | {b.get('mfe_p50')} |"
        )
    lines += [
        "",
        "## Signal counts",
        "",
        "| EMA | tol | body_k | DTs | leg2 | leg2_retest |",
        "|---|---|---|---|---|---|",
    ]
    for s in signal_stats:
        lines.append(
            f"| {s['ma']} | {s['tol']} | {s['body_k']} | {s['dts']} | {s['leg2']} | {s['leg2_retest']} |"
        )
    lines += [
        "",
        "## Accuracy meaning",
        "",
        "PROVEN ≠ 100%. It means hit@target before SL cleared ~35%+ with +EV on train and OOS.",
        "Many 2nd-leg shorts still stop; edge comes from R multiple when T hits.",
        "",
        f"_Generated in {time.time() - t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"PROVEN={len(proven)} PROMISING={len(promising)} scored={len(books)}", flush=True)
    if books:
        b0 = books[0]
        print("TOP", b0["book"], b0["verdict"], b0["oos"], flush=True)
    print(f"wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
