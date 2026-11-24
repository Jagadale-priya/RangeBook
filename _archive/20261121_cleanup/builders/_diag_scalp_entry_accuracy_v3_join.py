"""RESEARCH ONLY — Join-in-progress ≥25pt accuracy.

Idea: don't predict the flip. After 2–3 same-color bars already moved ≥X pts,
enter for another ≥25 from that close. Often more accurate than ignition prediction.

  python -u prod_live/tests/builders/_diag_scalp_entry_accuracy_v3_join.py
"""
from __future__ import annotations

import json
import sys
import time
from itertools import combinations
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
from _diag_scalp_pa_bos_choch_fvg import _norm_1m, to_15m, structure_events, build_htf_bias, htf_bias_lookup  # noqa: E402
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ENTRY_ACCURACY_V3_JOIN.md"
REPORT_JSON = OUT / "NIFTY_1M_ENTRY_ACCURACY_V3_JOIN.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 120
LOOKBACK_CAL = 240
FWD = 60
M25 = 25.0


def pack(rows, key, mid):
    if not rows:
        return {"n": 0, "prec": None, "train_n": 0, "train_prec": None, "oos_n": 0, "oos_prec": None,
                "avg_mfe": None, "avg_mae": None, "t25": None, "clean15": None}
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
        "n": n,
        "prec": p,
        "train_n": nt,
        "train_prec": pt,
        "oos_n": no,
        "oos_prec": po,
        "avg_mfe": round(float(np.mean([r["mfe"] for r in rows])), 2),
        "avg_mae": round(float(np.mean([r["mae"] for r in rows])), 2),
        "t25": round(100.0 * sum(1 for r in rows if r.get("t25")) / n, 2),
        "clean15": round(100.0 * sum(1 for r in rows if r.get("clean15")) / n, 2),
    }


def verdict(st, soft=95.0, hard=100.0, min_n=15, min_half=6):
    if not st or st["n"] < min_n:
        return "THIN"
    if st["prec"] == hard and st["train_prec"] == hard and st["oos_prec"] == hard and st["train_n"] >= min_half and st["oos_n"] >= min_half:
        return "PROVEN_100"
    if (st["prec"] or 0) >= soft and (st["train_prec"] or 0) >= soft and (st["oos_prec"] or 0) >= soft and st["train_n"] >= min_half and st["oos_n"] >= min_half:
        return "PROMISING_95"
    if (st["prec"] or 0) >= 80 and (st["oos_prec"] or 0) >= 75:
        return "HIGH_80"
    return "WEAK"


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("ENTRY ACCURACY v3 — join-in-progress", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df1 = _norm_1m(raw)
    df1 = add_ma_layers(df1)
    df1 = add_indicators(df1)
    df1 = add_ad_obv_proxy(df1)

    days_all = sorted({str(ts.date()) for ts in df1.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    mid = days_sorted[n_days // 2]
    df1 = df1[[str(ts.date()) in keep for ts in df1.index]]
    df15 = to_15m(df1)
    bias15 = build_htf_bias(df15, structure_events(df15))
    print(f"window {day_lo}→{day_hi} n={n_days} OOS≥{mid}", flush=True)

    o = df1["Open"].astype(float).values
    h = df1["High"].astype(float).values
    l = df1["Low"].astype(float).values
    c = df1["Close"].astype(float).values
    ema34 = df1["ema34"].astype(float).values
    atr = df1["atr14"].astype(float).values
    ad_r = df1["ad_rising"].astype(bool).values if "ad_rising" in df1.columns else np.zeros(len(c), dtype=bool)
    ad_f = df1["ad_falling"].astype(bool).values if "ad_falling" in df1.columns else np.zeros(len(c), dtype=bool)
    day = np.array([str(ts.date()) for ts in df1.index])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in df1.index])
    idx = df1.index

    rows = []
    i = 1
    n = len(c)
    while i < n - 1:
        if day[i] not in keep or not (MINS_LO <= mins[i] <= MINS_HI):
            i += 1
            continue
        # find same-color streak ending at i (length >=2)
        if c[i] == o[i]:
            i += 1
            continue
        bull = c[i] > o[i]
        # walk back to streak start
        s = i
        while s - 1 >= 0 and day[s - 1] == day[i]:
            if bull and c[s - 1] > o[s - 1]:
                s -= 1
            elif (not bull) and c[s - 1] < o[s - 1]:
                s -= 1
            else:
                break
        nb = i - s + 1
        if nb < 2:
            i += 1
            continue
        # only emit once per streak length threshold: when streak first hits 2 or 3
        # i.e. process when nb==2 or nb==3
        if nb not in (2, 3):
            i += 1
            continue

        side = "BUY" if bull else "SELL"
        open0 = float(o[s])
        if side == "BUY":
            already = float(np.max(h[s : i + 1]) - open0)
        else:
            already = float(open0 - np.min(l[s : i + 1]))
        entry = float(c[i])
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        body = abs(float(c[i]) - float(o[i]))
        rng = max(float(h[i]) - float(l[i]), 0.05)
        loc = (float(c[i]) - float(l[i])) / rng
        ctrl = (side == "BUY" and loc >= 0.65 and bull) or (side == "SELL" and loc <= 0.35 and not bull)
        ad = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))
        hb = htf_bias_lookup(bias15, idx[i])
        htf = (hb == "up" and side == "BUY") or (hb == "down" and side == "SELL")

        # forward from entry
        mfe = mae = 0.0
        hit25 = None
        for j in range(i + 1, min(n, i + FWD + 1)):
            if day[j] != day[i]:
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
        ok25, _, _, _ = path_ma_trail_strict(h, l, c, ema34, i, side, 25.0)
        rows.append(
            {
                "day": day[i],
                "hm": idx[i].strftime("%H:%M"),
                "mins": int(mins[i]),
                "side": side,
                "entry": round(entry, 2),
                "nb": nb,
                "already": round(already, 2),
                "already8": already >= 8,
                "already10": already >= 10,
                "already12": already >= 12,
                "already15": already >= 15,
                "ctrl": ctrl,
                "ad": ad,
                "htf": bool(htf),
                "disp08": body >= 0.8 * a,
                "disp10": body >= 1.0 * a,
                "big_body": body >= max(8.0, 0.6 * a),
                "mfe": round(mfe, 2),
                "mae": round(mae, 2),
                "m25": mfe >= M25,
                "m25_first": m25_first,
                "clean15": mfe >= M25 and mae <= 15,
                "t25": bool(ok25),
            }
        )
        i += 1

    print(f"join candidates={len(rows)}", flush=True)

    def book(name, pred):
        hit = [r for r in rows if pred(r)]
        byd = {}
        for r in sorted(hit, key=lambda x: (x["day"], x["mins"])):
            if r["day"] not in byd:
                byd[r["day"]] = r
        one = list(byd.values())
        st = pack(one, "m25_first", mid)
        return {
            "name": name,
            "stats": st,
            "verdict": verdict(st),
            "samples": one[:12],
        }

    tests = []
    for already_key, already_lab in (
        ("already8", "≥8"),
        ("already10", "≥10"),
        ("already12", "≥12"),
        ("already15", "≥15"),
    ):
        for nb in (2, 3):
            tests.append(book(f"run{nb} already{already_lab}", lambda r, nb=nb, k=already_key: r["nb"] == nb and r[k]))
            tests.append(book(f"run{nb} already{already_lab}+ctrl", lambda r, nb=nb, k=already_key: r["nb"] == nb and r[k] and r["ctrl"]))
            tests.append(book(f"run{nb} already{already_lab}+ctrl+ad", lambda r, nb=nb, k=already_key: r["nb"] == nb and r[k] and r["ctrl"] and r["ad"]))
            tests.append(book(f"run{nb} already{already_lab}+ctrl+htf", lambda r, nb=nb, k=already_key: r["nb"] == nb and r[k] and r["ctrl"] and r["htf"]))
            tests.append(book(f"run{nb} already{already_lab}+ctrl+ad+htf", lambda r, nb=nb, k=already_key: r["nb"] == nb and r[k] and r["ctrl"] and r["ad"] and r["htf"]))
            tests.append(book(f"run{nb} already{already_lab}+ctrl+ad+htf+disp08", lambda r, nb=nb, k=already_key: r["nb"] == nb and r[k] and r["ctrl"] and r["ad"] and r["htf"] and r["disp08"]))

    # hunt
    hunt = []
    feat = ["ctrl", "ad", "htf", "disp08", "disp10", "big_body", "already10", "already12", "already15"]
    for nb in (2, 3):
        base_rows = [r for r in rows if r["nb"] == nb]
        for k in (2, 3, 4):
            for combo in combinations(feat, k):
                if "already10" not in combo and "already12" not in combo and "already15" not in combo:
                    continue
                hit = [r for r in base_rows if all(r.get(f) for f in combo)]
                byd = {}
                for r in sorted(hit, key=lambda x: (x["day"], x["mins"])):
                    if r["day"] not in byd:
                        byd[r["day"]] = r
                one = list(byd.values())
                st = pack(one, "m25_first", mid)
                if st["n"] < 12 or (st["prec"] or 0) < 80:
                    continue
                hunt.append({"name": f"run{nb}|1d|" + "+".join(combo), **st, "verdict": verdict(st)})
    hunt.sort(key=lambda x: (0 if x["verdict"] == "PROVEN_100" else 1 if x["verdict"] == "PROMISING_95" else 2, -(x["prec"] or 0), -(x["oos_prec"] or 0), -x["n"]))
    seen = set()
    hunt_u = []
    for h_ in hunt:
        if h_["name"] in seen:
            continue
        seen.add(h_["name"])
        hunt_u.append(h_)
    hunt = hunt_u[:20]

    for t in tests:
        s = t["stats"]
        if s["n"] >= 8:
            print(f"  {t['name']}: n={s['n']} m25f={s['prec']}% OOS={s['oos_prec']}% clean15={s['clean15']}% → {t['verdict']}", flush=True)

    print(f"hunt ≥80% n≥12: {len(hunt)}", flush=True)
    for h_ in hunt[:10]:
        print(f"  {h_['name']}: n={h_['n']} prec={h_['prec']}% OOS={h_['oos_prec']}% {h_['verdict']}", flush=True)

    ranked = sorted(tests, key=lambda t: (0 if t["verdict"] == "PROVEN_100" else 1 if t["verdict"] == "PROMISING_95" else 2 if t["verdict"] == "HIGH_80" else 3, -(t["stats"]["prec"] or 0), -(t["stats"]["oos_prec"] or 0), -t["stats"]["n"]))
    best = ranked[0]
    proven = [h for h in hunt if h["verdict"] == "PROVEN_100"] + [t for t in tests if t["verdict"] == "PROVEN_100"]
    promising = [h for h in hunt if h["verdict"] == "PROMISING_95"] + [t for t in tests if t["verdict"] == "PROMISING_95"]

    payload = {
        "ok": True,
        "window": {"day_lo": day_lo, "day_hi": day_hi, "n_days": n_days, "oos_from": mid},
        "tests": [{"name": t["name"], "verdict": t["verdict"], "stats": t["stats"]} for t in ranked if t["stats"]["n"] >= 5],
        "hunt": hunt,
        "best": {"name": best["name"], "verdict": best["verdict"], "stats": best["stats"], "samples": best["samples"]},
        "proven": [p if isinstance(p, dict) and "stats" not in p else {"name": p["name"], "verdict": p["verdict"], **(p.get("stats") or p)} for p in proven[:5]],
        "promising_n": len(promising),
        "took_sec": round(time.time() - t0, 1),
    }

    lines = [
        "# NIFTY 1m — Entry accuracy **v3** (join-in-progress)",
        "",
        "Enter after run2/run3 already moved ≥X pts; target another ≥25 from entry (m25_first).",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS **{mid}**.",
        "",
        "## Top books (1/day)",
        "",
        "| Gate | Verdict | n | m25_first% | OOS | clean15% | avg MFE | avg MAE |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for t in ranked[:25]:
        s = t["stats"]
        if s["n"] < 5:
            continue
        lines.append(
            f"| `{t['name']}` | **{t['verdict']}** | {s['n']} | **{s['prec']}** | {s['oos_prec']} | "
            f"{s['clean15']} | {s['avg_mfe']} | {s['avg_mae']} |"
        )

    lines += ["", "## Hunt ≥80%", ""]
    if not hunt:
        lines.append("_None._")
    else:
        lines.append("| Rule | n | prec | Train | OOS | Verdict |")
        lines.append("|---|---:|---:|---|---|---|")
        for h_ in hunt[:15]:
            lines.append(
                f"| `{h_['name']}` | {h_['n']} | **{h_['prec']}** | {h_['train_n']}/{h_['train_prec']}% | "
                f"{h_['oos_n']}/{h_['oos_prec']}% | **{h_['verdict']}** |"
            )

    lines += ["", "## Winner", ""]
    if proven:
        # normalize
        w = proven[0]
        name = w.get("name")
        st = w.get("stats") or w
        lines.append(f"**PROVEN:** `{name}` · m25_first {st.get('prec')}% n={st.get('n')}")
    elif promising:
        w = promising[0]
        name = w.get("name") if isinstance(w, dict) else str(w)
        st = w.get("stats", w) if isinstance(w, dict) else {}
        lines.append(f"**PROMISING:** `{name}` · {st}")
    else:
        s = best["stats"]
        lines += [
            f"**Best effort:** `{best['name']}` · {best['verdict']}",
            f"- m25_first **{s['prec']}%** OOS **{s['oos_prec']}%** n={s['n']} · clean15 {s['clean15']}%",
            "",
            "| Day | HM | Side | Entry | already | MFE | MAE | m25_first |",
            "|---|---|---|---:|---:|---:|---:|---|",
        ]
        for x in best["samples"][:12]:
            lines.append(
                f"| {x['day']} | {x['hm']} | **{x['side']}** | **{x['entry']}** | {x['already']} | "
                f"{x['mfe']} | {x['mae']} | {x['m25_first']} |"
            )

    lines += [
        "",
        "## Bottom line across v1–v3",
        "",
        "- Predicting ignition for clean +25 before −25 is **~45–55%** at useful n.",
        "- Old IGN100 raw-m25 100% does **not** hold as one-direction accuracy.",
        "- Join-in-progress may lift accuracy; see winner above.",
        "- Do **not** claim 100% one-way until PROVEN_100 here.",
        "",
        f"_Generated in {payload['took_sec']}s._",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    print(f"BEST={best['name']} {best['verdict']} prec={best['stats']['prec']}%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
