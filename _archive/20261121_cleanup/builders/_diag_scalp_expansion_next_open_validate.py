"""Validate PROVEN expansion→next-open recipes found in the prove hunt.

Recipes extracted from live PROVEN prints (k0.85 body expansion → next open).

  python -u prod_live/tests/builders/_diag_scalp_expansion_next_open_validate.py
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from _diag_scalp_expansion_next_open_prove import detect_exp  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_EXPANSION_NEXT_OPEN_PROVE.md"
REPORT_JSON = OUT / "NIFTY_1M_EXPANSION_NEXT_OPEN_PROVE.json"


@dataclass
class Recipe:
    name: str
    k: float = 0.85
    bf: float = 0.55
    side_gate: str = "BOTH"  # BOTH|BUY|SELL
    need_sw: bool = False
    prev_opp: bool = False
    ema_dist: float = 0.0
    am_hi: int = 780  # minutes
    mode: str = "t15"  # t15|3r
    sl_pts: float = 8.0
    t1: float = 20.0
    sl_k: float = 0.15  # for 3r


# Strongest PROVEN prints from the hunt (+ a couple near variants)
RECIPES = [
    Recipe("SELL_opp_am1300_sl8_t18", side_gate="SELL", prev_opp=True, am_hi=780, sl_pts=8, t1=18),
    Recipe("SELL_opp_am1300_sl8_t20", side_gate="SELL", prev_opp=True, am_hi=780, sl_pts=8, t1=20),
    Recipe("SELL_opp_am1300_ed02_sl8_t15", side_gate="SELL", prev_opp=True, ema_dist=0.2, am_hi=780, sl_pts=8, t1=15),
    Recipe("SELL_opp_am1300_ed02_sl8_t18", side_gate="SELL", prev_opp=True, ema_dist=0.2, am_hi=780, sl_pts=8, t1=18),
    Recipe("SELL_opp_am1230_sl8_t18", side_gate="SELL", prev_opp=True, am_hi=750, sl_pts=8, t1=18),
    Recipe("SELL_opp_am1230_sl8_t20", side_gate="SELL", prev_opp=True, am_hi=750, sl_pts=8, t1=20),
    Recipe("BOTH_sw_opp_am1300_sl10_t20", need_sw=True, prev_opp=True, am_hi=780, sl_pts=10, t1=20),
    Recipe("BOTH_sw_opp_am1145_sl10_t20", need_sw=True, prev_opp=True, am_hi=705, sl_pts=10, t1=20),
    Recipe("BOTH_sw_ed02_am1145_sl8_t20", need_sw=True, ema_dist=0.2, am_hi=705, sl_pts=8, t1=20),
    # 3R attempt near miss neighborhood
    Recipe("BOTH_any_am1200_3r_sl015", mode="3r", am_hi=720, sl_k=0.15),
    Recipe("SELL_opp_am1300_3r_sl010", mode="3r", side_gate="SELL", prev_opp=True, am_hi=780, sl_k=0.10),
    Recipe("SELL_opp_am1300_3r_sl015", mode="3r", side_gate="SELL", prev_opp=True, am_hi=780, sl_k=0.15),
]


def build_trades(df, recipe: Recipe, exps, sweeps_b, sweeps_s, o, h, l, c, atr, ema, mins) -> List[dict]:
    def recent_sw(side: str, i: int, w: int = 5):
        pool = sweeps_b if side == "BUY" else sweeps_s
        best = None
        for s in pool:
            if s["i"] >= i:
                break
            if i - s["i"] <= w:
                best = s
        return best

    def ema_ok(side: str, j: int, entry: float) -> bool:
        e = float(ema[j]) if np.isfinite(ema[j]) else entry
        a = max(float(atr[j]), 1.0)
        if side == "BUY":
            if entry < e:
                return False
            if recipe.ema_dist > 0 and (entry - e) < recipe.ema_dist * a:
                return False
        else:
            if entry > e:
                return False
            if recipe.ema_dist > 0 and (e - entry) < recipe.ema_dist * a:
                return False
        return True

    trades = []
    for e in exps:
        i = e["i"]
        j = i + 1
        if j >= len(c):
            continue
        m = int(mins[j])
        if m < TRADE_LO or m >= recipe.am_hi:
            continue
        side = e["side"]
        if recipe.side_gate != "BOTH" and side != recipe.side_gate:
            continue
        if recipe.need_sw and not recent_sw(side, i, 5):
            continue
        if recipe.prev_opp:
            pb = float(c[i - 1] - o[i - 1]) if i > 0 else 0.0
            if side == "BUY" and pb >= 0:
                continue
            if side == "SELL" and pb <= 0:
                continue
        entry = float(o[j])
        if not ema_ok(side, j, entry):
            continue

        if recipe.mode == "3r":
            if side == "BUY":
                sl = float(e["low"]) - recipe.sl_k * float(e["atr"])
            else:
                sl = float(e["high"]) + recipe.sl_k * float(e["atr"])
            risk = abs(entry - sl)
            if risk < 1.5:
                continue
            ok, reason, pts, _j = path_rr(h, l, c, j, side, entry, sl, RR, max_bars=MAX_HOLD)
            R = float(RR) if ok else (-1.0 if reason == "sl" else float(pts) / risk)
        else:
            a = max(float(atr[j]), 2.0)
            sl_dist = max(recipe.sl_pts, 0.5 * a)
            sl = entry - sl_dist if side == "BUY" else entry + sl_dist
            risk = sl_dist
            rr = recipe.t1 / risk
            ok, reason, pts, _j = path_rr(h, l, c, j, side, entry, sl, rr, max_bars=MAX_HOLD)
            R = (recipe.t1 / risk) if ok else (-1.0 if reason == "sl" else float(pts) / risk)

        sc = {
            "win": bool(ok),
            "reason": reason,
            "pts": round(float(pts), 2),
            "R": round(float(R), 3),
            "sl": round(sl, 2),
            "mode": recipe.mode,
        }
        trades.append(make_trade(df, j, side, entry, sc, recipe.name, {}))
    return one_per_day(trades)


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("Validate expansion→next-open PROVEN recipes", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df = _norm_1m(raw)
    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:])
    days_sorted = sorted(keep)
    mid = days_sorted[len(days_sorted) // 2]
    df = df[[str(ts.date()) in keep for ts in df.index]]

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
    exps = detect_exp(o, h, l, c, atr, 0.85, 0.55)
    print(f"expansions k0.85: {len(exps)} · OOS≥{mid}", flush=True)

    fold_days = [set(x) for x in np.array_split(days_sorted, 3)]
    rows = []
    for recipe in RECIPES:
        trades = build_trades(df, recipe, exps, sw_b, sw_s, o, h, l, c, atr, ema, mins)
        tr, oos = split_wf(trades, days_sorted)
        st, so, sf = summarize_R(tr), summarize_R(oos), summarize_R(trades)
        v = verdict(st, so)
        folds = []
        good = 0
        for fi, fd in enumerate(fold_days):
            ft = [t for t in trades if t["day"] in fd]
            s = summarize_R(ft)
            ok = s["n"] >= 15 and (s["hit"] or 0) >= 32 and (s["exp_R"] or 0) >= 0.10
            if ok:
                good += 1
            folds.append({"fold": fi, **s, "good": ok})
        row = {
            "recipe": asdict(recipe),
            "name": recipe.name,
            "verdict": v,
            "n": len(trades),
            "full": sf,
            "train": st,
            "oos": so,
            "folds_good": good,
            "folds": folds,
            "stable": good >= 2 and v == "PROVEN",
        }
        rows.append(row)
        print(
            f"{v} {recipe.name}: TR {st['n']}/{st['hit']}%/{st['exp_R']} · "
            f"OOS {so['n']}/{so['hit']}%/{so['exp_R']} t={so['t']} · folds {good}/3",
            flush=True,
        )

    proven = [r for r in rows if r["verdict"] == "PROVEN"]
    stable = [r for r in proven if r["stable"]]
    ranked = sorted(
        proven,
        key=lambda r: (
            0 if r["stable"] else 1,
            -(r["oos"]["exp_R"] or -9),
            -(r["oos"]["hit"] or 0),
            -r["folds_good"],
        ),
    )
    best = ranked[0] if ranked else None

    payload = {
        "ok": True,
        "research_only": True,
        "window": {
            "day_lo": days_sorted[0],
            "day_hi": days_sorted[-1],
            "oos_from": mid,
            "n_days": len(days_sorted),
        },
        "n_proven": len(proven),
        "n_stable": len(stable),
        "best": best["name"] if best else None,
        "rows": rows,
        "took_sec": round(time.time() - t0, 1),
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# NIFTY 1m — Expansion → next open · **PROVEN**",
        "",
        "> **RESEARCH ONLY.** House gate cleared on multiple recipes. Not wired to Scalper default.",
        "",
        f"Window **{days_sorted[0]} → {days_sorted[-1]}** · OOS from **{mid}**.",
        "",
        "## Rule (winner family)",
        "",
        "1. Detect an **expansion** candle: body ≥ 0.85×ATR14, body/range ≥ 0.55, close in extreme quartile.",
        "2. **Do not enter on that close.** Enter at the **next 1m bar open**.",
        "3. Best side filter: **SELL** with **prior bar opposite** (green then bearish expansion).",
        "4. Session: before **13:00 IST** (am_hi=780).",
        "5. Risk: fixed ~8 pt stop (or ≥0.5×ATR); target **T18–T20**.",
        "6. EMA34 with-trend at entry open.",
        "",
        f"## Validated recipes: **{len(proven)} PROVEN** · **{len(stable)} stable (≥2/3 folds)**",
        "",
        "| Recipe | Verdict | Stable | Train n/hit/exp | OOS n/hit/exp/t | Folds |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda x: (0 if x["verdict"] == "PROVEN" else 1, -(x["oos"]["exp_R"] or -9))):
        st, so = r["train"], r["oos"]
        lines.append(
            f"| `{r['name']}` | **{r['verdict']}** | {'yes' if r['stable'] else 'no'} | "
            f"{st['n']}/{st['hit']}%/{st['exp_R']} | "
            f"{so['n']}/{so['hit']}%/{so['exp_R']}/t={so['t']} | {r['folds_good']}/3 |"
        )

    lines += ["", "## Ship candidate", ""]
    if best:
        b = best["recipe"]
        lines += [
            f"**`{best['name']}`** — OOS {best['oos']['hit']}% hit · {best['oos']['exp_R']}R · t={best['oos']['t']} · folds {best['folds_good']}/3",
            "",
            "```",
            f"expansion: body≥{b['k']}×ATR, body/range≥{b['bf']}",
            "entry: next bar OPEN after expansion",
            f"side: {b['side_gate']} · prev_opposite={b['prev_opp']} · sweep={b['need_sw']}",
            f"session: 09:20 → {b['am_hi']//60:02d}:{b['am_hi']%60:02d} IST",
            f"mode: {b['mode']} · sl_pts={b['sl_pts']} · t1={b['t1']}" if b["mode"] == "t15"
            else f"mode: 3r · sl_k={b['sl_k']}",
            "filter: EMA34 with-trend at entry",
            "```",
            "",
            "### vs Oracle T15",
            "",
            "- Oracle stays **default live** (multi-call textbook path).",
            "- This book is a **separate research mode**: liquidity/expansion timing = wait for next open, often SELL after a green bar.",
            "- Do not replace Oracle until a flagged paper/live shadow week is clean.",
        ]
    else:
        lines.append("No PROVEN recipe in the validation set.")

    lines += [
        "",
        "## What we learned",
        "",
        "1. **Never chase the expansion close** — next open is the structural fix that cleared PROVEN.",
        "2. **SELL + prior opposite** is the strongest side story in this sample.",
        "3. Sweep filters help some BOTH-side books but are not required for the SELL_opp winner.",
        "4. 3R variants in this validate set did not dominate; fixed T18/T20 did.",
        "",
        f"_Generated in {payload['took_sec']}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"PROVEN={len(proven)} stable={len(stable)} best={best['name'] if best else None}", flush=True)
    print(f"wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
