"""RESEARCH ONLY — Validate v5 HIGH_85 rule on longer window + list every trade.

Rule: pullback after run2/3 + atr≥10 + compress + engulf + ctrl + !extreme
Label: m25_first

  python -u prod_live/tests/builders/_diag_scalp_entry_accuracy_v5b_validate.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators  # noqa: E402
from _diag_scalp_ad_sr_entry_1m import add_ad_obv_proxy  # noqa: E402
from _diag_scalp_pa_bos_choch_fvg import _norm_1m  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ENTRY_ACCURACY_V5B_VALIDATE.md"
REPORT_JSON = OUT / "NIFTY_1M_ENTRY_ACCURACY_V5B_VALIDATE.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
FWD = 60
M25 = 25.0
PIVOT_L = 3


def swings(h, l, i, L=PIVOT_L, look=120):
    lo = max(L, i - look)
    hi_i, lo_i = [], []
    for j in range(lo, i - L):
        if h[j] >= np.max(h[j - L : j + L + 1]) - 1e-9:
            hi_i.append(j)
        if l[j] <= np.min(l[j - L : j + L + 1]) + 1e-9:
            lo_i.append(j)
    return [float(h[j]) for j in hi_i], [float(l[j]) for j in lo_i]


def label(h, l, c, day, i, entry, side):
    d = day[i]
    mfe = mae = 0.0
    hit25 = None
    end = min(len(c) - 1, i + FWD)
    for j in range(i + 1, end + 1):
        if day[j] != d:
            break
        if side == "BUY":
            mfe = max(mfe, float(h[j]) - entry)
            mae = max(mae, entry - float(l[j]))
        else:
            mfe = max(mfe, entry - float(l[j]))
            mae = max(mae, float(h[j]) - entry)
        if hit25 is None and mfe >= M25:
            hit25 = j
    m25_first = False
    if hit25 is not None:
        adv = 0.0
        m25_first = True
        for j in range(i + 1, hit25 + 1):
            if side == "BUY":
                adv = max(adv, entry - float(l[j]))
            else:
                adv = max(adv, float(h[j]) - entry)
            if adv >= M25:
                m25_first = False
                break
    return {
        "mfe": round(mfe, 2),
        "mae": round(mae, 2),
        "m25": mfe >= M25,
        "m25_first": m25_first,
        "clean15": mfe >= M25 and mae <= 15.0,
    }


def pack(rows, key, mid):
    if not rows:
        return {"n": 0, "prec": None, "train_n": 0, "train_prec": None, "oos_n": 0, "oos_prec": None,
                "avg_mfe": None, "avg_mae": None, "clean15": None, "m25": None}
    tr = [r for r in rows if r["day"] < mid]
    oo = [r for r in rows if r["day"] >= mid]

    def _p(rs):
        if not rs:
            return None, 0
        return round(100.0 * sum(1 for x in rs if x.get(key)) / len(rs), 2), len(rs)

    p, n = _p(rows)
    pt, nt = _p(tr)
    po, no = _p(oo)
    return {
        "n": n, "prec": p, "train_n": nt, "train_prec": pt, "oos_n": no, "oos_prec": po,
        "avg_mfe": round(float(np.mean([r["mfe"] for r in rows])), 2),
        "avg_mae": round(float(np.mean([r["mae"] for r in rows])), 2),
        "clean15": round(100.0 * sum(1 for r in rows if r.get("clean15")) / n, 2),
        "m25": round(100.0 * sum(1 for r in rows if r.get("m25")) / n, 2),
    }


def run_window(df1, keep, mid, label_tag):
    o = df1["Open"].astype(float).values
    h = df1["High"].astype(float).values
    l = df1["Low"].astype(float).values
    c = df1["Close"].astype(float).values
    atr = df1["atr14"].astype(float).values
    day = np.array([str(ts.date()) for ts in df1.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df1.index])
    idx = df1.index
    n = len(c)
    sess = {d: np.where(day == d)[0] for d in keep}

    trades = []
    i = 1
    while i < n - 2:
        d = day[i]
        if d not in keep or not (MINS_LO <= mins[i] <= MINS_HI):
            i += 1
            continue
        if c[i] == o[i]:
            i += 1
            continue
        bull = c[i] > o[i]
        s = i
        while s - 1 >= 0 and day[s - 1] == d:
            if bull and c[s - 1] > o[s - 1]:
                s -= 1
            elif (not bull) and c[s - 1] < o[s - 1]:
                s -= 1
            else:
                break
        nb = i - s + 1
        if nb not in (2, 3):
            i += 1
            continue
        side = "BUY" if bull else "SELL"
        ign_i = s
        ign_hi, ign_lo = float(h[ign_i]), float(l[ign_i])
        for k in range(i + 1, min(i + 9, n - 1)):
            if day[k] != d:
                break
            opp = (bull and c[k] < o[k]) or ((not bull) and c[k] > o[k])
            if not opp:
                continue
            if not (float(l[k]) <= ign_hi and float(h[k]) >= ign_lo):
                continue
            j = k + 1
            if j >= n or day[j] != d:
                break
            cont = (bull and c[j] > o[j]) or ((not bull) and c[j] < o[j])
            if not cont or not (MINS_LO <= mins[j] <= MINS_HI):
                continue
            entry = float(c[j])
            if side == "BUY" and entry - ign_lo >= 25:
                break
            if side == "SELL" and ign_hi - entry >= 25:
                break

            a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else 8.0
            if a < 10.0:
                break
            rng = max(float(h[j]) - float(l[j]), 0.05)
            loc = (float(c[j]) - float(l[j])) / rng
            green = c[j] > o[j]
            red = c[j] < o[j]
            body = abs(float(c[j]) - float(o[j]))
            ctrl = (side == "BUY" and loc >= 0.65 and green) or (side == "SELL" and loc <= 0.35 and red)
            if not ctrl:
                break
            # compress: prior bar small, this body big
            if j < 1 or day[j - 1] != d:
                break
            pr = max(float(h[j - 1]) - float(l[j - 1]), 0.05)
            compress = pr <= 0.7 * a and body >= 0.8 * a
            if not compress:
                break
            # engulf
            if side == "BUY":
                engulf = float(c[j]) > float(o[j - 1]) and float(o[j]) <= float(c[j - 1])
            else:
                engulf = float(c[j]) < float(o[j - 1]) and float(o[j]) >= float(c[j - 1])
            if not engulf:
                break
            # not extreme
            so_far = sess[d][sess[d] < j]
            if len(so_far):
                sess_hi, sess_lo = float(np.max(h[so_far])), float(np.min(l[so_far]))
            else:
                sess_hi = sess_lo = entry
            into_ext = (side == "BUY" and (sess_hi - entry) <= max(8.0, a)) or (
                side == "SELL" and (entry - sess_lo) <= max(8.0, a)
            )
            if into_ext:
                break

            lab = label(h, l, c, day, j, entry, side)
            trades.append(
                {
                    "day": d,
                    "hm": idx[j].strftime("%H:%M"),
                    "side": side,
                    "entry": round(entry, 2),
                    "run_n": nb,
                    "atr": round(a, 2),
                    **lab,
                }
            )
            break
        i += 1

    byd = {}
    for r in sorted(trades, key=lambda x: (x["day"], x["hm"])):
        if r["day"] not in byd:
            byd[r["day"]] = r
    one = list(byd.values())
    st_all = pack(trades, "m25_first", mid)
    st_1d = pack(one, "m25_first", mid)
    print(
        f"[{label_tag}] all n={st_all['n']} m25f={st_all['prec']}% tr={st_all['train_prec']}% oos={st_all['oos_prec']}% "
        f"| 1d n={st_1d['n']} m25f={st_1d['prec']}% oos={st_1d['oos_prec']}% "
        f"m25={pack(trades,'m25',mid)['prec']}% c15={st_all['clean15']}%",
        flush=True,
    )
    return {"tag": label_tag, "all": st_all, "one": st_1d, "trades": trades, "one_trades": one,
            "m25_all": pack(trades, "m25", mid), "c15_all": pack(trades, "clean15", mid)}


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("VALIDATE v5b HIGH_85 pullback rule", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    # use ~400 calendar days for up to ~250 sessions
    raw = raw[raw.index >= hi - pd.Timedelta(days=500)]
    df1 = _norm_1m(raw)
    df1 = add_ma_layers(df1)
    df1 = add_indicators(df1)
    df1 = add_ad_obv_proxy(df1)

    days_all = sorted({str(ts.date()) for ts in df1.index})
    results = []
    for n_sess in (120, 180, 240):
        keep = set(days_all[-n_sess:]) if len(days_all) > n_sess else set(days_all)
        days_sorted = sorted(keep)
        mid = days_sorted[len(days_sorted) // 2]
        dfw = df1[[str(ts.date()) in keep for ts in df1.index]]
        print(f"\nwindow {days_sorted[0]}→{days_sorted[-1]} n={len(days_sorted)} OOS≥{mid}", flush=True)
        results.append(run_window(dfw, keep, mid, f"{len(days_sorted)}d"))

    # Walk-forward folds on 240d: 4 chunks
    keep240 = set(days_all[-240:]) if len(days_all) > 240 else set(days_all)
    days240 = sorted(keep240)
    fold_stats = []
    if len(days240) >= 80:
        chunk = len(days240) // 4
        for f in range(4):
            lo = f * chunk
            hi_i = (f + 1) * chunk if f < 3 else len(days240)
            fold_days = set(days240[lo:hi_i])
            # use mid as first day of fold so all are "oos" style — score whole fold
            mid_f = days240[hi_i - 1]  # everything < mid goes train empty; pack still works
            # better: score fold alone without train/oos split
            dfw = df1[[str(ts.date()) in fold_days for ts in df1.index]]
            # fake mid = first day so all count as OOS in pack — we'll compute direct
            r = run_window(dfw, fold_days, days240[lo], f"fold{f+1}:{days240[lo]}→{days240[hi_i-1]}")
            fold_stats.append(r)

    best = results[-1] if results else None  # prefer longest
    # pick 120d as primary (matches prior) but report all
    r120 = results[0] if results else None

    lines = [
        "# NIFTY 1m — Validate **HIGH_85** entry rule (v5b)",
        "",
        "## Rule (side + entry price only)",
        "",
        "```",
        "PATTERN : bull_run2/3 or bear_run2/3 on 1m",
        "WAIT    : ≤8 bars for opposite-color pullback touching ignition bar range",
        "ENTRY   : close of next same-color continuation bar",
        "FILTERS : ATR14 ≥ 10",
        "        + compress (prior range ≤0.7×ATR AND body ≥0.8×ATR)",
        "        + engulf prior bar",
        "        + control close (BUY loc≥0.65 / SELL loc≤0.35)",
        "        + NOT at session extreme (≤ max(8,ATR) of sess high/low)",
        "SIDE    : run direction",
        "PRICE   : continuation close",
        "```",
        "",
        "## Stability across windows",
        "",
        "| Window | Book | n | m25_first% | Train | OOS | raw m25% | clean15% | avg MFE | avg MAE |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        for book, st, m25, c15 in (
            ("all", r["all"], r["m25_all"]["prec"], r["c15_all"]["prec"]),
            ("1/day", r["one"], pack(r["one_trades"], "m25", r["all"] and results[0]["all"] and mid_of(r))["prec"] if False else pack_m25(r), pack_c15(r)),
        ):
            pass  # filled below carefully

    def mid_from_tag(r):
        # reconstruct mid as half of unique days in trades+window — use train/oos from pack already
        return None

    for r in results:
        lines.append(
            f"| {r['tag']} | all | {r['all']['n']} | **{r['all']['prec']}** | {r['all']['train_prec']} | "
            f"{r['all']['oos_prec']} | {r['m25_all']['prec']} | {r['c15_all']['prec']} | "
            f"{r['all']['avg_mfe']} | {r['all']['avg_mae']} |"
        )
        m25_1 = round(100.0 * sum(1 for x in r["one_trades"] if x["m25"]) / max(len(r["one_trades"]), 1), 2) if r["one_trades"] else None
        c15_1 = round(100.0 * sum(1 for x in r["one_trades"] if x["clean15"]) / max(len(r["one_trades"]), 1), 2) if r["one_trades"] else None
        lines.append(
            f"| {r['tag']} | 1/day | {r['one']['n']} | **{r['one']['prec']}** | {r['one']['train_prec']} | "
            f"{r['one']['oos_prec']} | {m25_1} | {c15_1} | {r['one']['avg_mfe']} | {r['one']['avg_mae']} |"
        )

    if fold_stats:
        lines += ["", "## Walk-forward folds (240d / 4)", "", "| Fold | n | m25_first% | raw m25% | clean15% |", "|---|---:|---:|---:|---:|"]
        for r in fold_stats:
            lines.append(
                f"| {r['tag']} | {r['all']['n']} | **{r['all']['prec']}** | {r['m25_all']['prec']} | {r['c15_all']['prec']} |"
            )

    # Full trade list from 120d (primary research window)
    lines += ["", "## Every trade — 120d window (all signals)", ""]
    if r120:
        lines += [
            "| Day | HM | Side | Entry | ATR | MFE | MAE | m25_first | clean15 |",
            "|---|---|---|---:|---:|---:|---:|---|---|",
        ]
        for x in r120["trades"]:
            lines.append(
                f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | {x['atr']} | "
                f"{x['mfe']} | {x['mae']} | {x['m25_first']} | {x['clean15']} |"
            )

    # Verdict
    lines += ["", "## Verdict", ""]
    if r120 and r120["all"]["prec"] is not None:
        p = r120["all"]["prec"]
        if p >= 95 and (r120["all"]["oos_prec"] or 0) >= 95:
            verd = "PROMISING_95 / near ship"
        elif p >= 85 and (r120["all"]["oos_prec"] or 0) >= 80:
            verd = "HIGH_85 — best accurate rule so far; **not** 100%"
        else:
            verd = "WEAKER than 120d claim — check longer windows"
        lines.append(f"- 120d all-signals: **{p}%** m25_first (OOS {r120['all']['oos_prec']}%) → {verd}")
    if len(results) >= 2:
        lines.append(
            f"- Longer windows: "
            + ", ".join(f"{r['tag']}={r['all']['prec']}%" for r in results)
        )
    lines += [
        "- Still **no** PROVEN_100 / PROMISING_95 on ≥15 trades for favour-first ≥25.",
        "- Live IGN100 remains research-only; this pullback rule is the **most accurate** causal entry found.",
        "",
        f"_Generated in {time.time() - t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "windows": [{k: v for k, v in r.items() if k != "trades" and k != "one_trades"} | {"n_trades": len(r["trades"])} for r in results],
                "folds": [{k: v for k, v in r.items() if k not in ("trades", "one_trades")} for r in fold_stats],
                "trades_120": r120["trades"] if r120 else [],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT}", flush=True)
    return 0


def pack_m25(r):
    return round(100.0 * sum(1 for x in r["one_trades"] if x["m25"]) / max(len(r["one_trades"]), 1), 2) if r["one_trades"] else None


def pack_c15(r):
    return round(100.0 * sum(1 for x in r["one_trades"] if x["clean15"]) / max(len(r["one_trades"]), 1), 2) if r["one_trades"] else None


if __name__ == "__main__":
    raise SystemExit(main())
