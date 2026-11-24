"""Which pattern-cross losses are visible at the signal.

Features are known when the third candle closes. Buckets are ranked on
sessions before 2025-11-16. The last year is only a check.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research_1m_ma3_pattern_exits import SELECT_END, _load, _session, _walk

OUT = Path(r"c:\Users\Priyanka\Agent\prod_live\reports\1y\MA3_1M_LOSS_FILTER.json")
LENGTHS = (15, 10, 20, 30)


def _hit(win: pd.Series) -> dict:
    n = int(win.shape[0])
    w = int(win.sum())
    return {"n": n, "win": w, "loss": n - w, "hit": None if n == 0 else round(100.0 * w / n, 2), "loss_pct": None if n == 0 else round(100.0 * (n - w) / n, 2)}


def _build() -> pd.DataFrame:
    df = _load()
    rows = []
    for day, g in df.groupby("day", sort=True):
        close = g["Close"].to_numpy(float)
        high = g["High"].to_numpy(float)
        low = g["Low"].to_numpy(float)
        mins = (g["date"].dt.hour * 60 + g["date"].dt.minute).to_numpy(int)
        pre = bool(np.datetime64(day) < SELECT_END)
        sess_hi = np.maximum.accumulate(high)
        sess_lo = np.minimum.accumulate(low)
        for length in LENGTHS:
            for a in _session(close, high, low, length):
                if a["impulse"] is None or a["reward"] is None or a["reward"] + 1e-9 < a["risk"]:
                    continue
                swing = _walk(high, low, a["i"], a["side"], a["stop"], a["impulse"])
                if swing == "open":
                    continue
                i = a["i"]
                span = float(sess_hi[i] - sess_lo[i])
                pos = 0.5 if span <= 0 else (a["entry"] - float(sess_lo[i])) / span
                ret5 = 0.0 if i < 5 else (float(close[i]) - float(close[i - 5])) * a["side"]
                rows.append(
                    {
                        "pre": pre,
                        "length": length,
                        "side": a["side"],
                        "mins": int(mins[i]),
                        "hour": int(mins[i] // 60),
                        "risk": a["risk"],
                        "rr": a["reward"] / a["risk"],
                        "chop": a["chop"],
                        "slope_aligned": a["slope"] * a["side"],
                        "dip_bars": a["dip_bars"],
                        "ma_dist_r": a["ma_dist"] / a["risk"],
                        "sess_pos": pos,
                        "ret5_r": ret5 / a["risk"],
                        "win": swing == "win",
                    }
                )
    return pd.DataFrame(rows)


def _bucket_table(train: pd.DataFrame, test: pd.DataFrame, col: str, edges, labels) -> list[dict]:
    out = []
    tr = pd.cut(train[col], edges, labels=labels, include_lowest=True)
    te = pd.cut(test[col], edges, labels=labels, include_lowest=True)
    for lab in labels:
        a = _hit(train.loc[tr == lab, "win"])
        b = _hit(test.loc[te == lab, "win"])
        out.append({"bucket": str(lab), "pre": a, "test": b})
    return out


def main() -> None:
    tix = _build()
    print("decided swing trades", len(tix), flush=True)
    report = {"select_before": "2025-11-16", "lengths": {}}
    for length in LENGTHS:
        base = tix[tix["length"] == length]
        train = base[base["pre"]]
        test = base[~base["pre"]]
        base_pre = _hit(train["win"])
        base_te = _hit(test["win"])
        print(f"L{length} base pre {base_pre} test {base_te}", flush=True)
        # loss-heavy slices discovered on train, then read on test
        rules = {
            "rr_under_1.25": lambda d: d["rr"] < 1.25,
            "rr_1.25_2": lambda d: (d["rr"] >= 1.25) & (d["rr"] < 2),
            "rr_over_3": lambda d: d["rr"] >= 3,
            "risk_under_6": lambda d: d["risk"] < 6,
            "risk_over_25": lambda d: d["risk"] >= 25,
            "chop_ge_6": lambda d: d["chop"] >= 6,
            "slope_against": lambda d: d["slope_aligned"] <= 0,
            "slope_with_strong": lambda d: d["slope_aligned"] >= 2,
            "open_hour": lambda d: d["mins"] < 10 * 60,
            "midday": lambda d: (d["mins"] >= 11 * 60) & (d["mins"] < 13 * 60),
            "after_14": lambda d: d["mins"] >= 14 * 60,
            "extended": lambda d: d["ma_dist_r"] >= 0.8,
            "tight_to_ma": lambda d: d["ma_dist_r"] < 0.15,
            "dip_le_4": lambda d: d["dip_bars"] <= 4,
            "dip_ge_20": lambda d: d["dip_bars"] >= 20,
            "against_5m": lambda d: d["ret5_r"] < 0,
            "with_5m": lambda d: d["ret5_r"] > 0.5,
            "session_low_third": lambda d: d["sess_pos"] < 0.33,
            "session_high_third": lambda d: d["sess_pos"] > 0.67,
            "buy": lambda d: d["side"] > 0,
            "sell": lambda d: d["side"] < 0,
        }
        slices = []
        for name, fn in rules.items():
            tr = train[fn(train)]
            te = test[fn(test)]
            slices.append({"rule": name, "pre": _hit(tr["win"]), "test": _hit(te["win"])})
        # keep trades that avoid the train slices whose loss rate is at least 8 points worse than base
        # and that still have 150 train trades. Freeze that refusal set, then score the kept book.
        refuse = []
        for s in slices:
            if s["pre"]["n"] >= 150 and s["pre"]["hit"] is not None and s["pre"]["hit"] <= base_pre["hit"] - 8:
                refuse.append(s["rule"])
        if refuse:
            mask_tr = pd.Series(False, index=train.index)
            mask_te = pd.Series(False, index=test.index)
            for name in refuse:
                mask_tr = mask_tr | rules[name](train)
                mask_te = mask_te | rules[name](test)
            kept = {"pre": _hit(train.loc[~mask_tr, "win"]), "test": _hit(test.loc[~mask_te, "win"]), "refused": refuse, "refused_pre": _hit(train.loc[mask_tr, "win"]), "refused_test": _hit(test.loc[mask_te, "win"])}
        else:
            kept = {"refused": [], "note": "no train slice was 8 points worse with n>=150"}
        report["lengths"][str(length)] = {
            "base_pre": base_pre,
            "base_test": base_te,
            "slices": slices,
            "kept_after_loss_slices": kept,
        }
        print(" refuse", refuse, "kept", kept.get("pre"), kept.get("test"), flush=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
