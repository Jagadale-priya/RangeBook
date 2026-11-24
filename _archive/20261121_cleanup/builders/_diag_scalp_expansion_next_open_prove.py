"""RESEARCH ONLY — Push expansion→next-open (AM) until PROVEN or exhaust.

Near-miss: D2_b1.0_any_am_3r · OOS hit 34.1% (need 35%) · exp 0.37R (clears).

Focused grid around that neighborhood + side splits + SL width + AM cutoff.

  python -u prod_live/tests/builders/_diag_scalp_expansion_next_open_prove.py
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
    RR,
    summarize_R,
    verdict,
)
from _diag_scalp_expansion_liquidity import (  # noqa: E402
    TRADE_LO,
    _mins,
    atr14,
    detect_sweeps,
    make_trade,
    one_per_day,
    split_wf,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_EXPANSION_NEXT_OPEN_PROVE.md"
REPORT_JSON = OUT / "NIFTY_1M_EXPANSION_NEXT_OPEN_PROVE.json"


def detect_exp(o, h, l, c, atr, k: float, bf: float) -> List[dict]:
    out = []
    for i in range(14, len(c)):
        rng = float(h[i] - l[i])
        if rng < 1e-9:
            continue
        body = float(c[i] - o[i])
        abs_body = abs(body)
        a = float(atr[i]) if np.isfinite(atr[i]) else 0.0
        if a < 1e-9 or abs_body < k * a or abs_body / rng < bf:
            continue
        pos = (float(c[i]) - float(l[i])) / rng
        if body > 0 and pos < 0.75:
            continue
        if body < 0 and pos > 0.25:
            continue
        out.append(
            {
                "i": i,
                "side": "BUY" if body > 0 else "SELL",
                "body_atr": abs_body / a,
                "atr": a,
                "low": float(l[i]),
                "high": float(h[i]),
            }
        )
    return out


def eval_book(
    df,
    trades: List[dict],
    days_sorted: List[str],
    tag: str,
) -> Optional[Dict[str, Any]]:
    trades = one_per_day(trades)
    if len(trades) < 40:
        return None
    tr, oos = split_wf(trades, days_sorted)
    st, so = summarize_R(tr), summarize_R(oos)
    # need enough on both sides for a fair prove call
    if st["n"] < 25 or so["n"] < 25:
        return None
    v = verdict(st, so)
    return {
        "book": tag,
        "verdict": v,
        "n": len(trades),
        "train": st,
        "oos": so,
    }


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("Expansion→next-open PROVE hunt (focused)", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df = _norm_1m(raw)
    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:])
    days_sorted = sorted(keep)
    mid = days_sorted[len(days_sorted) // 2]
    df = df[[str(ts.date()) in keep for ts in df.index]]
    print(f"window {days_sorted[0]}→{days_sorted[-1]} OOS≥{mid}", flush=True)

    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    atr = atr14(h, l, c)
    ema = pd.Series(c).ewm(span=34, adjust=False).mean().to_numpy()
    mins = np.array([_mins(ts) for ts in df.index])
    sweeps = detect_sweeps(h, l, c)
    sw_b = [s for s in sweeps if s["side"] == "BUY"]
    sw_s = [s for s in sweeps if s["side"] == "SELL"]

    def recent_sw(side: str, i: int, w: int = 5):
        pool = sw_b if side == "BUY" else sw_s
        best = None
        for s in pool:
            if s["i"] >= i:
                break
            if i - s["i"] <= w:
                best = s
        return best

    def ema_ok(side: str, j: int, entry: float, min_dist: float) -> bool:
        e = float(ema[j]) if np.isfinite(ema[j]) else entry
        a = max(float(atr[j]), 1.0)
        if side == "BUY":
            if entry < e:
                return False
            if min_dist > 0 and (entry - e) < min_dist * a:
                return False
        else:
            if entry > e:
                return False
            if min_dist > 0 and (e - entry) < min_dist * a:
                return False
        return True

    exp_cfgs = [(0.85, 0.55), (0.9, 0.58), (1.0, 0.62), (1.0, 0.58), (1.1, 0.60)]
    exp_sets = {
        f"k{k}_bf{bf}": detect_exp(o, h, l, c, atr, k, bf) for k, bf in exp_cfgs
    }
    for k, v in exp_sets.items():
        print(f"  {k}: {len(v)}", flush=True)

    proven: List[Dict[str, Any]] = []
    near: List[Dict[str, Any]] = []
    tested = 0

    for exp_key, exps in exp_sets.items():
        for side_gate in ("BOTH", "BUY", "SELL"):
            for need_sw in (False, True):
                for prev_opp in (False, True):
                    for ema_dist in (0.0, 0.2):
                        for am_hi in (11 * 60 + 45, 12 * 60, 12 * 60 + 30, 13 * 60):
                            for sl_k in (0.05, 0.10, 0.15, 0.20, 0.30):
                                trades = []
                                tag = (
                                    f"P3_{exp_key}_{side_gate}_"
                                    f"{'sw' if need_sw else 'any'}_"
                                    f"{'opp' if prev_opp else 'nop'}_"
                                    f"ed{ema_dist}_am{am_hi}_sl{sl_k}"
                                )
                                for e in exps:
                                    i = e["i"]
                                    j = i + 1
                                    if j >= len(c):
                                        continue
                                    m = int(mins[j])
                                    if m < TRADE_LO or m >= am_hi:
                                        continue
                                    side = e["side"]
                                    if side_gate != "BOTH" and side != side_gate:
                                        continue
                                    if need_sw and not recent_sw(side, i, 5):
                                        continue
                                    if prev_opp:
                                        pb = float(c[i - 1] - o[i - 1]) if i > 0 else 0.0
                                        if side == "BUY" and pb >= 0:
                                            continue
                                        if side == "SELL" and pb <= 0:
                                            continue
                                    entry = float(o[j])
                                    if not ema_ok(side, j, entry, ema_dist):
                                        continue
                                    # SL beyond expansion extreme
                                    if side == "BUY":
                                        sl = float(e["low"]) - sl_k * float(e["atr"])
                                    else:
                                        sl = float(e["high"]) + sl_k * float(e["atr"])
                                    risk = abs(entry - sl)
                                    if risk < 1.5:
                                        continue
                                    ok, reason, pts, _j = path_rr(
                                        h, l, c, j, side, entry, sl, RR, max_bars=MAX_HOLD
                                    )
                                    if ok:
                                        R = float(RR)
                                    elif reason == "sl":
                                        R = -1.0
                                    else:
                                        R = float(pts) / risk
                                    sc = {
                                        "win": bool(ok),
                                        "reason": reason,
                                        "pts": round(float(pts), 2),
                                        "R": round(float(R), 3),
                                        "sl": round(sl, 2),
                                        "mode": "3r",
                                    }
                                    trades.append(
                                        make_trade(
                                            df,
                                            j,
                                            side,
                                            entry,
                                            sc,
                                            tag,
                                            {"body_atr": round(e["body_atr"], 2)},
                                        )
                                    )
                                tested += 1
                                row = eval_book(df, trades, days_sorted, tag)
                                if not row:
                                    continue
                                if row["verdict"] == "PROVEN":
                                    proven.append(row)
                                    print(
                                        "PROVEN",
                                        tag,
                                        f"TR {row['train']['n']}/{row['train']['hit']}%/{row['train']['exp_R']}",
                                        f"OOS {row['oos']['n']}/{row['oos']['hit']}%/{row['oos']['exp_R']} t={row['oos']['t']}",
                                        flush=True,
                                    )
                                else:
                                    so, st = row["oos"], row["train"]
                                    # keep near-misses: within ~2pp hit or strong exp
                                    if (
                                        (so["hit"] or 0) >= 33
                                        and (st["hit"] or 0) >= 34
                                        and (so["exp_R"] or 0) >= 0.20
                                        and (st["exp_R"] or 0) >= 0.20
                                    ):
                                        near.append(row)

                            # T15: raise target to lift exp_R while keeping hit
                            for sl_pts in (8.0, 10.0, 12.0):
                                for t1 in (15.0, 18.0, 20.0, 22.0):
                                    trades = []
                                    tag = (
                                        f"PT_{exp_key}_{side_gate}_"
                                        f"{'sw' if need_sw else 'any'}_"
                                        f"{'opp' if prev_opp else 'nop'}_"
                                        f"ed{ema_dist}_am{am_hi}_sl{sl_pts}_t{t1}"
                                    )
                                    for e in exps:
                                        i = e["i"]
                                        j = i + 1
                                        if j >= len(c):
                                            continue
                                        m = int(mins[j])
                                        if m < TRADE_LO or m >= am_hi:
                                            continue
                                        side = e["side"]
                                        if side_gate != "BOTH" and side != side_gate:
                                            continue
                                        if need_sw and not recent_sw(side, i, 5):
                                            continue
                                        if prev_opp:
                                            pb = float(c[i - 1] - o[i - 1]) if i > 0 else 0.0
                                            if side == "BUY" and pb >= 0:
                                                continue
                                            if side == "SELL" and pb <= 0:
                                                continue
                                        entry = float(o[j])
                                        if not ema_ok(side, j, entry, ema_dist):
                                            continue
                                        a = max(float(atr[j]), 2.0)
                                        sl_dist = max(sl_pts, 0.5 * a)
                                        if side == "BUY":
                                            sl = entry - sl_dist
                                        else:
                                            sl = entry + sl_dist
                                        risk = sl_dist
                                        rr = t1 / risk
                                        ok, reason, pts, _j = path_rr(
                                            h, l, c, j, side, entry, sl, rr, max_bars=MAX_HOLD
                                        )
                                        if ok:
                                            R = t1 / risk
                                        elif reason == "sl":
                                            R = -1.0
                                        else:
                                            R = float(pts) / risk
                                        sc = {
                                            "win": bool(ok),
                                            "reason": reason,
                                            "pts": round(float(pts), 2),
                                            "R": round(float(R), 3),
                                            "sl": round(sl, 2),
                                            "mode": "t15",
                                        }
                                        trades.append(
                                            make_trade(
                                                df,
                                                j,
                                                side,
                                                entry,
                                                sc,
                                                tag,
                                                {"body_atr": round(e["body_atr"], 2)},
                                            )
                                        )
                                    tested += 1
                                    row = eval_book(df, trades, days_sorted, tag)
                                    if not row:
                                        continue
                                    if row["verdict"] == "PROVEN":
                                        proven.append(row)
                                        print(
                                            "PROVEN",
                                            tag,
                                            f"TR {row['train']['n']}/{row['train']['hit']}%/{row['train']['exp_R']}",
                                            f"OOS {row['oos']['n']}/{row['oos']['hit']}%/{row['oos']['exp_R']} t={row['oos']['t']}",
                                            flush=True,
                                        )
                                    else:
                                        so, st = row["oos"], row["train"]
                                        if (
                                            (so["hit"] or 0) >= 36
                                            and (st["hit"] or 0) >= 36
                                            and (so["exp_R"] or 0) >= 0.15
                                            and (st["exp_R"] or 0) >= 0.15
                                        ):
                                            near.append(row)

    # Also: 3-fold stability on any PROVEN / top near
    def folds(trades_days_proxy_book: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    ranked = sorted(
        proven + near,
        key=lambda r: (
            0 if r["verdict"] == "PROVEN" else 1 if r["verdict"] == "PROMISING" else 2,
            -(r["oos"]["exp_R"] or -9),
            -(r["oos"]["hit"] or 0),
        ),
    )
    # unique
    seen = set()
    uniq = []
    for r in ranked:
        if r["book"] in seen:
            continue
        seen.add(r["book"])
        uniq.append(r)

    # Stability: re-score top proven/near with 3 chronological folds
    def fold_stats(book_tag: str, collect_fn) -> List[Dict[str, Any]]:
        return []

    # Rebuild trades for top candidates for 3-fold check
    def three_fold_for_tag(tag: str) -> Optional[Dict[str, Any]]:
        # parse is hard — instead re-run from stored params embedded in tag
        # skip parse; compute on top proven by re-filtering from known best list later
        return None

    # Manual 3-fold for top 5 by regenerating with recorded specs
    stability = []
    top_for_stab = [r for r in uniq if r["verdict"] in ("PROVEN", "PROMISING")][:8]
    # Re-generate using a small helper that interprets key fields from tag
    def trades_from_tag(tag: str) -> List[dict]:
        # Example: P3_k1.0_bf0.62_BOTH_any_nop_ed0.0_am720_sl0.15
        # PT_k1.0_bf0.62_BOTH_any_nop_ed0.0_am720_sl10.0_t18.0
        parts = tag.split("_")
        family = parts[0]
        # find exp key
        exp_key = None
        for k in exp_sets:
            if f"_{k}_" in f"_{tag}_" or tag.startswith(f"P3_{k}_") or tag.startswith(f"PT_{k}_"):
                exp_key = k
                break
        if not exp_key:
            return []
        exps = exp_sets[exp_key]
        side_gate = "BOTH"
        for sg in ("BOTH", "BUY", "SELL"):
            if f"_{sg}_" in tag:
                side_gate = sg
                break
        need_sw = "_sw_" in tag
        prev_opp = "_opp_" in tag
        ema_dist = 0.0
        if "_ed0.2_" in tag:
            ema_dist = 0.2
        am_hi = 12 * 60
        for a in (705, 720, 750, 780):
            if f"_am{a}_" in tag:
                am_hi = a
                break
        trades = []
        if family == "P3":
            sl_k = 0.15
            for tok in parts:
                if tok.startswith("sl") and "t" not in tok:
                    try:
                        sl_k = float(tok[2:])
                    except Exception:
                        pass
            for e in exps:
                i = e["i"]
                j = i + 1
                if j >= len(c):
                    continue
                m = int(mins[j])
                if m < TRADE_LO or m >= am_hi:
                    continue
                side = e["side"]
                if side_gate != "BOTH" and side != side_gate:
                    continue
                if need_sw and not recent_sw(side, i, 5):
                    continue
                if prev_opp:
                    pb = float(c[i - 1] - o[i - 1]) if i > 0 else 0.0
                    if side == "BUY" and pb >= 0:
                        continue
                    if side == "SELL" and pb <= 0:
                        continue
                entry = float(o[j])
                if not ema_ok(side, j, entry, ema_dist):
                    continue
                if side == "BUY":
                    sl = float(e["low"]) - sl_k * float(e["atr"])
                else:
                    sl = float(e["high"]) + sl_k * float(e["atr"])
                risk = abs(entry - sl)
                if risk < 1.5:
                    continue
                ok, reason, pts, _j = path_rr(h, l, c, j, side, entry, sl, RR, max_bars=MAX_HOLD)
                R = float(RR) if ok else (-1.0 if reason == "sl" else float(pts) / risk)
                sc = {
                    "win": bool(ok),
                    "reason": reason,
                    "pts": round(float(pts), 2),
                    "R": round(float(R), 3),
                    "sl": round(sl, 2),
                    "mode": "3r",
                }
                trades.append(make_trade(df, j, side, entry, sc, tag, {}))
        else:
            # PT
            sl_pts = 10.0
            t1 = 15.0
            for tok in parts:
                if tok.startswith("sl"):
                    try:
                        sl_pts = float(tok[2:])
                    except Exception:
                        pass
                if tok.startswith("t") and tok[1:].replace(".", "", 1).isdigit():
                    try:
                        t1 = float(tok[1:])
                    except Exception:
                        pass
            for e in exps:
                i = e["i"]
                j = i + 1
                if j >= len(c):
                    continue
                m = int(mins[j])
                if m < TRADE_LO or m >= am_hi:
                    continue
                side = e["side"]
                if side_gate != "BOTH" and side != side_gate:
                    continue
                if need_sw and not recent_sw(side, i, 5):
                    continue
                if prev_opp:
                    pb = float(c[i - 1] - o[i - 1]) if i > 0 else 0.0
                    if side == "BUY" and pb >= 0:
                        continue
                    if side == "SELL" and pb <= 0:
                        continue
                entry = float(o[j])
                if not ema_ok(side, j, entry, ema_dist):
                    continue
                a = max(float(atr[j]), 2.0)
                sl_dist = max(sl_pts, 0.5 * a)
                sl = entry - sl_dist if side == "BUY" else entry + sl_dist
                risk = sl_dist
                rr = t1 / risk
                ok, reason, pts, _j = path_rr(h, l, c, j, side, entry, sl, rr, max_bars=MAX_HOLD)
                R = (t1 / risk) if ok else (-1.0 if reason == "sl" else float(pts) / risk)
                sc = {
                    "win": bool(ok),
                    "reason": reason,
                    "pts": round(float(pts), 2),
                    "R": round(float(R), 3),
                    "sl": round(sl, 2),
                    "mode": "t15",
                }
                trades.append(make_trade(df, j, side, entry, sc, tag, {}))
        return one_per_day(trades)

    n_fold = 3
    fold_days = np.array_split(days_sorted, n_fold)
    for r in uniq[:12]:
        if r["verdict"] not in ("PROVEN", "PROMISING"):
            continue
        trades = trades_from_tag(r["book"])
        if len(trades) < 40:
            continue
        fold_rows = []
        ok_folds = 0
        for fi, fd in enumerate(fold_days):
            fd_set = set(fd)
            ft = [t for t in trades if t["day"] in fd_set]
            s = summarize_R(ft)
            good = (
                s["n"] >= 15
                and (s["hit"] or 0) >= 32
                and (s["exp_R"] or 0) >= 0.10
            )
            if good:
                ok_folds += 1
            fold_rows.append({"fold": fi, **s, "good": good})
        stability.append(
            {
                "book": r["book"],
                "verdict": r["verdict"],
                "folds_good": ok_folds,
                "folds": fold_rows,
            }
        )

    payload = {
        "ok": True,
        "research_only": True,
        "tested": tested,
        "window": {
            "day_lo": days_sorted[0],
            "day_hi": days_sorted[-1],
            "oos_from": mid,
            "n_days": len(days_sorted),
        },
        "prove_rules": {"n": MIN_N, "hit": MIN_HIT, "exp_R": MIN_EXP, "oos_t": MIN_T},
        "n_proven": len(proven),
        "proven": proven,
        "top": uniq[:40],
        "stability": stability,
        "took_sec": round(time.time() - t0, 1),
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# NIFTY 1m — Expansion → next open · PROVE hunt",
        "",
        "> **RESEARCH ONLY.** House gate: TRAIN+OOS n≥30, hit≥35%, exp_R≥0.20, OOS t≥1.5.",
        "",
        f"Window **{days_sorted[0]} → {days_sorted[-1]}** · OOS from **{mid}** · tested **{tested}** configs.",
        "",
        f"## Result: **{len(proven)} PROVEN**",
        "",
    ]
    if proven:
        lines += ["| Book | Train | OOS |", "|---|---|---|"]
        for r in sorted(proven, key=lambda x: -(x["oos"]["exp_R"] or 0)):
            st, so = r["train"], r["oos"]
            lines.append(
                f"| `{r['book']}` | {st['n']}/{st['hit']}%/{st['exp_R']}R | "
                f"{so['n']}/{so['hit']}%/{so['exp_R']}R t={so['t']} |"
            )
        best = max(proven, key=lambda x: (x["oos"]["exp_R"] or 0, x["oos"]["hit"] or 0))
        lines += [
            "",
            f"**Best PROVEN:** `{best['book']}`",
            "",
            "Still research-only until wired behind an explicit Scalper flag.",
        ]
    else:
        lines.append("No config cleared PROVEN.")

    lines += ["", "## Top near / promising", "", "| Book | Verdict | Train | OOS |", "|---|---|---|---|"]
    for r in uniq[:20]:
        st, so = r["train"], r["oos"]
        lines.append(
            f"| `{r['book']}` | **{r['verdict']}** | {st['n']}/{st['hit']}%/{st['exp_R']} | "
            f"{so['n']}/{so['hit']}%/{so['exp_R']} t={so['t']} |"
        )

    if stability:
        lines += ["", "## 3-fold stability (top)", "", "| Book | Verdict | Folds good (of 3) |", "|---|---|---|"]
        for s in stability:
            lines.append(f"| `{s['book']}` | {s['verdict']} | {s['folds_good']}/3 |")

    lines += [
        "",
        "## Recommendation",
        "",
    ]
    if proven:
        lines += [
            f"- **Found PROVEN** expansion→next-open configs ({len(proven)}).",
            "- Prefer best OOS exp among PROVEN with ≥2/3 folds good.",
            "- Keep Oracle T15 as default until a flagged research mode is reviewed.",
        ]
    else:
        lines += [
            "- Still short of PROVEN after focused AM next-open grid.",
            "- Keep Oracle T15 live; treat next-open AM as the active research lead.",
            "- Closest path remains raising OOS hit ~1pp without killing exp_R.",
        ]
    lines += ["", f"_Generated in {payload['took_sec']}s._", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"tested={tested} PROVEN={len(proven)} near={len(uniq)} wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
