"""Refine D_exp_next_open family — hunt PROVEN on expansion → next open."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(BUILDERS), str(ROOT / "tools" / "research")]
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
from _diag_scalp_pa_bos_choch_fvg import _norm_1m  # noqa: E402
from _diag_scalp_pa_proven_logic import (  # noqa: E402
    LOOKBACK_CAL,
    N_SESSIONS,
    summarize_R,
    verdict,
)
from _diag_scalp_expansion_liquidity import (  # noqa: E402
    TRADE_HI,
    TRADE_LO,
    _mins,
    atr14,
    detect_expansions,
    detect_sweeps,
    make_trade,
    one_per_day,
    score_entry,
    split_wf,
)

OUT = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_1M_EXPANSION_LIQUIDITY_D2.json"


def main() -> int:
    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df = _norm_1m(raw)
    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:])
    days_sorted = sorted(keep)
    df = df[[str(ts.date()) in keep for ts in df.index]]

    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    atr = atr14(h, l, c)
    ema = pd.Series(c).ewm(span=34, adjust=False).mean().to_numpy()
    mins = np.array([_mins(ts) for ts in df.index])
    exps = detect_expansions(o, h, l, c, atr)
    sweeps = detect_sweeps(h, l, c)
    sw_b = [s for s in sweeps if s["side"] == "BUY"]
    sw_s = [s for s in sweeps if s["side"] == "SELL"]

    def recent(side: str, i: int, w: int = 5):
        pool = sw_b if side == "BUY" else sw_s
        best = None
        for s in pool:
            if s["i"] >= i:
                break
            if i - s["i"] <= w:
                best = s
        return best

    def ema_ok(side: str, i: int, entry: float) -> bool:
        e = float(ema[i]) if np.isfinite(ema[i]) else entry
        if side == "BUY" and entry < e:
            return False
        if side == "SELL" and entry > e:
            return False
        return True

    cands = []
    for min_batr in (1.0, 1.2, 1.5):
        for need_sw in (False, True):
            for sess in ("all", "am", "mid"):
                for mode in ("3r", "t15"):
                    trades = []
                    sw_tag = "sw" if need_sw else "any"
                    tag = f"D2_b{min_batr}_{sw_tag}_{sess}_{mode}"
                    for e in exps:
                        if e["body_atr"] < min_batr:
                            continue
                        i = e["i"]
                        j = i + 1
                        if j >= len(c):
                            continue
                        m = int(mins[j])
                        if not (TRADE_LO <= m <= TRADE_HI):
                            continue
                        if sess == "am" and m >= 12 * 60:
                            continue
                        if sess == "mid" and not (11 * 60 <= m <= 14 * 60):
                            continue
                        side = e["side"]
                        if need_sw and not recent(side, i, 5):
                            continue
                        entry = float(o[j])
                        if not ema_ok(side, j, entry):
                            continue
                        sc = score_entry(
                            h, l, c, ema, j, side, entry, mode=mode, atr_i=float(atr[j])
                        )
                        if not sc:
                            continue
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
                    trades = one_per_day(trades)
                    tr, oos = split_wf(trades, days_sorted)
                    st, so = summarize_R(tr), summarize_R(oos)
                    v = verdict(st, so)
                    keep_row = v != "NOT_PROVEN" or (
                        (so["n"] or 0) >= 40 and (so["exp_R"] or 0) >= 0.2
                    )
                    if keep_row:
                        cands.append(
                            {
                                "book": tag,
                                "verdict": v,
                                "train": st,
                                "oos": so,
                                "n": len(trades),
                            }
                        )
                        print(
                            v,
                            tag,
                            "TR",
                            st["n"],
                            st["hit"],
                            st["exp_R"],
                            "OOS",
                            so["n"],
                            so["hit"],
                            so["exp_R"],
                            "t",
                            so["t"],
                            flush=True,
                        )

    cands = sorted(
        cands,
        key=lambda r: (
            0 if r["verdict"] == "PROVEN" else 1 if r["verdict"] == "PROMISING" else 2,
            -(r["oos"]["exp_R"] or -9),
        ),
    )
    proven = [c for c in cands if c["verdict"] == "PROVEN"]
    promising = [c for c in cands if c["verdict"] == "PROMISING"]
    OUT.write_text(
        json.dumps(
            {
                "rows": cands[:50],
                "proven": [p["book"] for p in proven],
                "promising": [p["book"] for p in promising],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("PROVEN", len(proven), "PROMISING", len(promising), flush=True)
    print("wrote", OUT, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
