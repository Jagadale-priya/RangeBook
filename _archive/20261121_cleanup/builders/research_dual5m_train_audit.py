"""Audit the saved 5m dual packs. Prints ranking, calibration, and tape shape.

  python -u prod_live/tests/builders/research_dual5m_train_audit.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import path_setup  # noqa: F401,E402

LEDGER = ROOT / "stock_signal_data/fno_validate/research"
PACKS = LEDGER / "nifty_side_models_5m_research" / "dual5m_packs.joblib"
CACHE = LEDGER / "_cache_dual5m_xy_research.json"
TAPE = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"
FREEZE = "2024-09-10"


def auc(y, p) -> float:
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    pos = p[y == 1]
    neg = p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    # Mann–Whitney
    order = np.argsort(p)
    ranks = np.empty(len(p), dtype=float)
    ranks[order] = np.arange(1, len(p) + 1)
    # average ties
    # simple tie-average
    sp = p[order]
    i = 0
    while i < len(sp):
        j = i
        while j + 1 < len(sp) and sp[j + 1] == sp[i]:
            j += 1
        if j > i:
            avg = ranks[order[i : j + 1]].mean()
            ranks[order[i : j + 1]] = avg
        i = j + 1
    sum_pos = ranks[y == 1].sum()
    n_pos = (y == 1).sum()
    n_neg = (y == 0).sum()
    return float((sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def main() -> int:
    import joblib

    packs = joblib.load(PACKS)
    raw = json.loads(CACHE.read_text(encoding="utf-8"))
    tickets = raw["tickets"]
    print(f"tickets {len(tickets)} freeze {raw.get('freeze')} risk {raw.get('risk')}")
    print(f"feat cache==code {raw.get('feat')}")

    for side in ("BUY", "SELL"):
        pack = packs[side]
        print(
            f"\n== {side} available={pack.get('available')} n_train={pack.get('n_train')} "
            f"named_base_hit={pack.get('holdout_base_hit')} through={pack.get('train_through_day')}"
        )
        iso = pack["iso"]
        xt = np.asarray(getattr(iso, "X_thresholds_", []), dtype=float)
        yt = np.asarray(getattr(iso, "y_thresholds_", []), dtype=float)
        print(f"  iso knots {len(xt)} x {np.round(xt, 3).tolist()}")
        print(f"  iso y    {np.round(yt, 3).tolist()}")
        rows = [r for r in tickets if r["decision"] == side]
        train = [r for r in rows if str(r["day"]) <= FREEZE]
        oos = [r for r in rows if str(r["day"]) > FREEZE]
        for lab, part in (("train", train), ("oos", oos)):
            X = np.asarray([r["x"] for r in part], dtype=float)
            y = np.asarray([r["y"] for r in part], dtype=int)
            raw_p = pack["base"].predict_proba(X)[:, 1]
            cal = np.clip(pack["iso"].transform(raw_p), 0.05, 0.95)
            print(
                f"  {lab} n={len(part)} y={100*y.mean():.1f}% "
                f"raw_auc={auc(y, raw_p):.3f} cal_auc={auc(y, cal):.3f} "
                f"raw p {np.quantile(raw_p, [0.1, 0.5, 0.9]).round(3).tolist()} "
                f"cal p {np.quantile(cal, [0.1, 0.5, 0.9]).round(3).tolist()} "
                f"unique_cal={len(np.unique(np.round(cal, 4)))}"
            )

    tape = pd.read_csv(TAPE, index_col=0, parse_dates=True)
    print(f"\ntape rows={len(tape)} {tape.index.min()} → {tape.index.max()} cols={list(tape.columns)}")
    print(f"dup index {int(tape.index.duplicated().sum())} nulls {int(tape.isna().sum().sum())}")
    if tape.index.tz is None:
        idx = tape.index.tz_localize("Asia/Kolkata")
    else:
        idx = tape.index.tz_convert("Asia/Kolkata")
    days = idx.strftime("%Y-%m-%d")
    per = pd.Series(1, index=idx).groupby(days).size()
    print(f"sessions {len(per)} bars/day median {per.median():.0f} min {per.min()} max {per.max()}")
    by_year = per.groupby(per.index.str[:4]).agg(["count", "median", "min"])
    print(by_year.to_string())
    hm = idx.strftime("%H:%M")
    print("first bar of day counts", Counter(hm.groupby(days).min()).most_common(5))
    print("last bar of day counts", Counter(hm.groupby(days).max()).most_common(5))
    # ticket clock
    hms = Counter(r["hm"][:2] for r in tickets)
    print("ticket hour", dict(sorted(hms.items())))
    fb = sum(1 for r in tickets if r.get("first_break"))
    print(f"first_break {fb}/{len(tickets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
