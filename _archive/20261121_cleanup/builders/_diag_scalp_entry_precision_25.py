"""RESEARCH ONLY — Accurate ENTRY only (price + BUY/SELL).

User goal:
  Find 1m candle patterns that precede a SAME-DIRECTION move ≥25 pts.
  Only 2 outputs matter: entry price, side (BUY/SELL).
  Density irrelevant. Precision → as close to 100% as possible.
  Suggested book: run2|run3 + control + AD (± HELD / !extreme).
  Also score EMA34-trail T15 + major (trail MFE≥40).
  Union with oracle_t15_clean only if precision holds.

Labels (causal, from entry close):
  m25  = raw MFE ≥ 25 in trade direction (within 60 bars / same day)
  t15  = EMA34 trail reaches +15 before trail stop
  maj  = trail MFE ≥ 40

  python -u prod_live/tests/builders/_diag_scalp_entry_precision_25.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
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
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers, enrich_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402
from _diag_scalp_sr_highmove_proven import enrich_sr_archetypes, in_session  # noqa: E402
from _diag_scalp_ad_sr_entry_1m import add_ad_obv_proxy  # noqa: E402

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ENTRY_PRECISION_25.md"
REPORT_JSON = OUT / "NIFTY_1M_ENTRY_PRECISION_25.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 66  # ~3 months — enough for precision hunt
LOOKBACK_CAL = 140
FWD_BARS = 60
M25 = 25.0
T15 = 15.0
MAJ = 40.0
RUN_PATS = {"bull_run2", "bull_run3", "bear_run2", "bear_run3"}

# Prove floors for "accurate entry"
HARD_PREC = 100.0  # ideal
SOFT_PREC = 95.0
MIN_N_HARD = 12
MIN_N_SOFT = 20


def score_raw_mfe(events, h, l, c, day, max_bars=FWD_BARS):
    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        entry = float(c[i])  # entry = close of pattern bar
        e["entry_px"] = round(entry, 2)
        d = e["day"]
        mfe = 0.0
        mae = 0.0
        hit25_i = None
        end = min(len(c) - 1, i + max_bars)
        for j in range(i + 1, end + 1):
            if day[j] != d:
                break
            if side == "BUY":
                mfe = max(mfe, float(h[j]) - entry)
                mae = max(mae, entry - float(l[j]))
            else:
                mfe = max(mfe, entry - float(l[j]))
                mae = max(mae, float(h[j]) - entry)
            if hit25_i is None and mfe >= M25:
                hit25_i = j
        e["_mfe_raw"] = round(mfe, 2)
        e["_mae_raw"] = round(mae, 2)
        e["_m25"] = bool(mfe >= M25)
        e["_m40_raw"] = bool(mfe >= MAJ)
        # favour-first vs 25: did we reach +25 before -25 adverse?
        e["_m25_first"] = False
        if hit25_i is not None:
            adv = 0.0
            ok = True
            for j in range(i + 1, hit25_i + 1):
                if side == "BUY":
                    adv = max(adv, entry - float(l[j]))
                else:
                    adv = max(adv, float(h[j]) - entry)
                if adv >= M25:
                    ok = False
                    break
            e["_m25_first"] = ok


def score_trail(events, h, l, c, ema34):
    for e in events:
        ok, reason, sl, t1v = path_ma_trail_strict(
            h, l, c, ema34, int(e["full_i"]), e["decision"], float(T15)
        )
        e["_t15"] = bool(ok)
        e["_t15_pts"] = float(t1v if ok else 0.0)
        # trail MFE
        i = int(e["full_i"])
        side = e["decision"]
        entry = float(c[i])
        mfe = 0.0
        for j in range(i + 1, min(len(c), i + 120 + 1)):
            hi, lo, cl, m = float(h[j]), float(l[j]), float(c[j]), float(ema34[j])
            if not np.isfinite(m):
                break
            if side == "BUY":
                mfe = max(mfe, hi - entry)
                if cl < m:
                    break
            else:
                mfe = max(mfe, entry - lo)
                if cl > m:
                    break
        e["_mfe_trail"] = round(mfe, 2)
        e["_maj"] = bool(mfe >= MAJ)


def book_stats(rows: List[dict], n_days: int) -> Dict[str, Any]:
    if not rows:
        return {"n": 0, "cpd": 0.0, "m25": None, "m25_first": None, "t15": None, "maj": None, "avg_mfe": None}
    n = len(rows)
    return {
        "n": n,
        "cpd": round(n / n_days, 2) if n_days else 0.0,
        "m25": round(100.0 * sum(1 for e in rows if e.get("_m25")) / n, 2),
        "m25_first": round(100.0 * sum(1 for e in rows if e.get("_m25_first")) / n, 2),
        "t15": round(100.0 * sum(1 for e in rows if e.get("_t15")) / n, 2),
        "maj": round(100.0 * sum(1 for e in rows if e.get("_maj")) / n, 2),
        "m40_raw": round(100.0 * sum(1 for e in rows if e.get("_m40_raw")) / n, 2),
        "avg_mfe": round(float(np.mean([e.get("_mfe_raw") or 0 for e in rows])), 2),
        "avg_mae": round(float(np.mean([e.get("_mae_raw") or 0 for e in rows])), 2),
        "avg_mfe_trail": round(float(np.mean([e.get("_mfe_trail") or 0 for e in rows])), 2),
    }


def is_run(e: dict) -> bool:
    p = str(e.get("primary") or "")
    pats = set(e.get("patterns") or [])
    return p in RUN_PATS or bool(pats & RUN_PATS)


Gate = Tuple[str, Callable[[dict], bool]]


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("ENTRY PRECISION ≥25pts (RESEARCH ONLY) — side + price only", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    df = add_ad_obv_proxy(df)

    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    mid = days_sorted[n_days // 2]
    print(f"window {day_lo}→{day_hi} n_days={n_days} OOS≥{mid}", flush=True)

    events = scalp.collect_scalp_events(df, str(df.index.min().date()), str(df.index.max().date()))
    enrich_ma_layers(events, df)
    enrich_ind(events, df)
    setup.apply_setup_enrichment(events, df)
    enrich_sr_archetypes(events, df)

    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    day = np.array([str(ts.date()) for ts in df.index])
    ad_r = df["ad_rising"].astype(bool).values if "ad_rising" in df.columns else np.zeros(len(df), dtype=bool)
    ad_f = df["ad_falling"].astype(bool).values if "ad_falling" in df.columns else np.zeros(len(df), dtype=bool)

    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        e["ad_with"] = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))
        e["not_extreme"] = not bool(e.get("into_sess_extreme"))
        e["held"] = held_gate(e)
        e["sess"] = bool(in_session(e)) and MINS_LO <= int(e["mins"]) <= MINS_HI
        e["ctrl"] = bool(e.get("control_with"))
        e["tier_ab"] = bool(e.get("setup_ok"))
        e["hold_break"] = e.get("regime") == "hold_break" or bool(e.get("hold_break_setup"))
        e["bounce"] = bool(e.get("sr_bounce"))
        e["runway2"] = bool(e.get("runway_2atr"))
        e["room_ok"] = bool(e.get("clear_path"))
        e["is_run"] = is_run(e)
        e["run2"] = str(e.get("primary") or "") in ("bull_run2", "bear_run2") or bool(
            set(e.get("patterns") or []) & {"bull_run2", "bear_run2"}
        )
        e["run3"] = str(e.get("primary") or "") in ("bull_run3", "bear_run3") or bool(
            set(e.get("patterns") or []) & {"bull_run3", "bear_run3"}
        )
        if i > 0:
            prev_green = c[i - 1] > o[i - 1]
            prev_red = c[i - 1] < o[i - 1]
            e["prev_opposite"] = (side == "BUY" and prev_red) or (side == "SELL" and prev_green)
        else:
            e["prev_opposite"] = False

    score_raw_mfe(events, h, l, c, day)
    score_trail(events, h, l, c, ema34)

    pool = [e for e in events if e["day"] in keep and e["sess"]]
    print(f"pool={len(pool)} run2|3={sum(1 for e in pool if e['is_run'])}", flush=True)

    # ---- Gate grid (precision-first) ----
    gates: List[Gate] = [
        # User suggested core
        ("run2|3 + ctrl + AD", lambda e: e["is_run"] and e["ctrl"] and e["ad_with"]),
        ("run2|3 + ctrl + AD + HELD", lambda e: e["is_run"] and e["ctrl"] and e["ad_with"] and e["held"]),
        ("run2|3 + ctrl + AD + !extreme", lambda e: e["is_run"] and e["ctrl"] and e["ad_with"] and e["not_extreme"]),
        (
            "run2|3 + ctrl + AD + HELD + !extreme",
            lambda e: e["is_run"] and e["ctrl"] and e["ad_with"] and e["held"] and e["not_extreme"],
        ),
        ("run3 + ctrl + AD", lambda e: e["run3"] and e["ctrl"] and e["ad_with"]),
        ("run3 + ctrl + AD + HELD", lambda e: e["run3"] and e["ctrl"] and e["ad_with"] and e["held"]),
        ("run3 + ctrl + AD + !extreme", lambda e: e["run3"] and e["ctrl"] and e["ad_with"] and e["not_extreme"]),
        (
            "run3 + ctrl + AD + HELD + !extreme",
            lambda e: e["run3"] and e["ctrl"] and e["ad_with"] and e["held"] and e["not_extreme"],
        ),
        ("run2 + ctrl + AD", lambda e: e["run2"] and e["ctrl"] and e["ad_with"]),
        ("run2 + ctrl + AD + HELD", lambda e: e["run2"] and e["ctrl"] and e["ad_with"] and e["held"]),
        # Tighten further for 100%
        (
            "run2|3 + ctrl + AD + HELD + room",
            lambda e: e["is_run"] and e["ctrl"] and e["ad_with"] and e["held"] and e["room_ok"],
        ),
        (
            "run2|3 + ctrl + AD + HELD + runway2",
            lambda e: e["is_run"] and e["ctrl"] and e["ad_with"] and e["held"] and e["runway2"],
        ),
        (
            "run2|3 + ctrl + AD + HELD + room + !extreme",
            lambda e: e["is_run"] and e["ctrl"] and e["ad_with"] and e["held"] and e["room_ok"] and e["not_extreme"],
        ),
        (
            "run3 + ctrl + AD + HELD + room + !extreme",
            lambda e: e["run3"] and e["ctrl"] and e["ad_with"] and e["held"] and e["room_ok"] and e["not_extreme"],
        ),
        (
            "run2|3 + ctrl + AD + hold_break",
            lambda e: e["is_run"] and e["ctrl"] and e["ad_with"] and e["hold_break"],
        ),
        (
            "run2|3 + ctrl + AD + HELD + hold_break",
            lambda e: e["is_run"] and e["ctrl"] and e["ad_with"] and e["held"] and e["hold_break"],
        ),
        (
            "run2|3 + ctrl + AD + prev_opp + HELD",
            lambda e: e["is_run"] and e["ctrl"] and e["ad_with"] and e["prev_opposite"] and e["held"],
        ),
        # Baselines
        ("TierAB (oracle_t15_clean twin)", lambda e: e["tier_ab"]),
        ("run2|3 alone", lambda e: e["is_run"]),
        ("ctrl + AD", lambda e: e["ctrl"] and e["ad_with"]),
        ("HELD + ctrl + AD", lambda e: e["held"] and e["ctrl"] and e["ad_with"]),
        (
            "HELD + ctrl + AD + !extreme",
            lambda e: e["held"] and e["ctrl"] and e["ad_with"] and e["not_extreme"],
        ),
        (
            "HELD + hold_break + ctrl",
            lambda e: e["held"] and e["hold_break"] and e["ctrl"],
        ),
    ]

    rows = []
    for name, pred in gates:
        hits = [e for e in pool if pred(e)]
        train = [e for e in hits if e["day"] < mid]
        oos = [e for e in hits if e["day"] >= mid]
        sf, st, so = book_stats(hits, n_days), book_stats(train, n_days // 2), book_stats(oos, n_days - n_days // 2)
        # verdict on m25 precision
        verdict = "NOT_PROVEN"
        if (
            sf["n"] >= MIN_N_HARD
            and sf["m25"] == HARD_PREC
            and st["n"] >= max(5, MIN_N_HARD // 2)
            and so["n"] >= max(5, MIN_N_HARD // 2)
            and st["m25"] == HARD_PREC
            and so["m25"] == HARD_PREC
        ):
            verdict = "PROVEN_100"
        elif (
            sf["n"] >= MIN_N_SOFT
            and sf["m25"] is not None
            and sf["m25"] >= SOFT_PREC
            and st["m25"] is not None
            and so["m25"] is not None
            and st["m25"] >= SOFT_PREC
            and so["m25"] >= SOFT_PREC
            and st["n"] >= 8
            and so["n"] >= 8
        ):
            verdict = "PROMISING_95"
        elif sf["m25"] is not None and sf["m25"] >= 90 and sf["n"] >= 10:
            verdict = "HIGH_90"
        rows.append(
            {
                "name": name,
                "verdict": verdict,
                "full": sf,
                "train": st,
                "oos": so,
            }
        )
        print(
            f"  {name}: n={sf['n']} m25={sf['m25']}% m25first={sf['m25_first']}% "
            f"t15={sf['t15']}% maj={sf['maj']}% | OOS m25={so['m25']}% → {verdict}",
            flush=True,
        )

    # Rank by (m25 prec, then m25_first, then maj, then n)
    ranked = sorted(
        rows,
        key=lambda r: (
            r["full"]["m25"] if r["full"]["m25"] is not None else -1,
            r["full"]["m25_first"] if r["full"]["m25_first"] is not None else -1,
            r["full"]["maj"] if r["full"]["maj"] is not None else -1,
            r["full"]["n"],
        ),
        reverse=True,
    )

    # Auto-search: among run2|3 pool, find feature combo with 100% m25 (greedy)
    run_pool = [e for e in pool if e["is_run"]]
    feat_keys = [
        "ctrl",
        "ad_with",
        "held",
        "not_extreme",
        "room_ok",
        "runway2",
        "hold_break",
        "bounce",
        "prev_opposite",
        "run3",
        "tier_ab",
    ]

    def prec(subset):
        if not subset:
            return None, 0
        return 100.0 * sum(1 for e in subset if e.get("_m25")) / len(subset), len(subset)

    # Brute small combos of 2–4 features on run pool
    auto = []
    from itertools import combinations

    for k in (2, 3, 4):
        for combo in combinations(feat_keys, k):
            sub = [e for e in run_pool if all(e.get(f) for f in combo)]
            p, n = prec(sub)
            if n >= 8 and p is not None and p >= 90.0:
                # split WF
                tr = [e for e in sub if e["day"] < mid]
                oo = [e for e in sub if e["day"] >= mid]
                pt, nt = prec(tr)
                po, no = prec(oo)
                auto.append(
                    {
                        "feats": "+".join(combo),
                        "n": n,
                        "m25": round(p, 2),
                        "train_n": nt,
                        "train_m25": round(pt, 2) if pt is not None else None,
                        "oos_n": no,
                        "oos_m25": round(po, 2) if po is not None else None,
                        "t15": round(100.0 * sum(1 for e in sub if e.get("_t15")) / n, 2),
                        "maj": round(100.0 * sum(1 for e in sub if e.get("_maj")) / n, 2),
                        "avg_mfe": round(float(np.mean([e["_mfe_raw"] for e in sub])), 2),
                    }
                )
    auto = sorted(auto, key=lambda x: (x["m25"], x["oos_m25"] or 0, x["n"]), reverse=True)[:25]
    print(f"auto combos ≥90% m25 (n≥8): {len(auto)}", flush=True)

    # Best proven / promising
    proven = [r for r in rows if r["verdict"] == "PROVEN_100"]
    promising = [r for r in rows if r["verdict"] == "PROMISING_95"]
    best = (proven + promising + ranked)[0] if ranked else None

    # Union with TierAB if a high-prec gate exists
    union_rows = []
    if best and best["full"]["m25"] and best["full"]["m25"] >= 90:
        best_pred = next(p for n, p in gates if n == best["name"])
        clean = [e for e in pool if e["tier_ab"]]
        gated = [e for e in pool if best_pred(e)]
        # union by (day, mins, side)
        keys = {(e["day"], e["mins"], e["decision"]) for e in clean}
        uni = list(clean)
        for e in gated:
            k = (e["day"], e["mins"], e["decision"])
            if k not in keys:
                uni.append(e)
                keys.add(k)
        union_rows = [
            {"book": "TierAB alone", **book_stats(clean, n_days)},
            {"book": f"best gate `{best['name']}`", **book_stats(gated, n_days)},
            {"book": "TierAB ∪ best gate", **book_stats(uni, n_days)},
        ]

    # Sample accurate entries from top gate
    top_name = ranked[0]["name"] if ranked else None
    top_pred = next((p for n, p in gates if n == top_name), lambda e: False)
    samples = [
        {
            "day": e["day"],
            "hm": e["hm"],
            "side": e["decision"],
            "entry": e["entry_px"],
            "primary": e.get("primary"),
            "mfe": e["_mfe_raw"],
            "m25": e["_m25"],
            "t15": e["_t15"],
            "maj": e["_maj"],
            "held": e["held"],
            "ctrl": e["ctrl"],
            "ad": e["ad_with"],
        }
        for e in sorted([e for e in pool if top_pred(e)], key=lambda x: (x["day"], x["mins"]))[:40]
    ]

    # Failures of top gate (if any)
    fails = [s for s in samples if not s["m25"]]

    payload = {
        "ok": True,
        "research_only": True,
        "goal": "entry_price + BUY/SELL only · ≥25pt unidirectional precision",
        "window": {"day_lo": day_lo, "day_hi": day_hi, "n_days": n_days, "oos_from": mid},
        "labels": {
            "m25": "raw MFE≥25 within 60 bars same day from pattern close",
            "m25_first": "reach +25 before −25 adverse",
            "t15": "EMA34 trail +15",
            "maj": "trail MFE≥40",
            "entry": "close of pattern completion bar",
        },
        "gates": rows,
        "auto_run_combos_top": auto,
        "proven_100": [r["name"] for r in proven],
        "promising_95": [r["name"] for r in promising],
        "best": best,
        "union": union_rows,
        "samples": samples,
        "took_sec": round(time.time() - t0, 1),
    }

    lines = [
        "# NIFTY 1m — **Accurate ENTRY** (price + BUY/SELL) · ≥25pt moves",
        "",
        "> **RESEARCH ONLY.** Density ignored. Precision is the only score that matters.",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS from **{mid}**.",
        "",
        "## What we want",
        "",
        "```",
        "INPUT  : 1m candle pattern completes",
        "OUTPUT : entry_price = close of that bar",
        "         side        = BUY or SELL",
        "SUCCESS: price then runs ≥25 pts in that direction (raw MFE)",
        "GOAL   : precision → 100% (every call is a real ≥25pt move)",
        "```",
        "",
        "Suggested core from major-move autopsy: **`run2|run3 + control + AD`** (± HELD / !extreme).",
        "",
        "## 1) Gate precision table (ranked by m25%)",
        "",
        "| Gate | Verdict | n | **m25%** | m25-first% | T15% | Maj% | avg MFE | OOS m25% |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in ranked:
        f, o = r["full"], r["oos"]
        lines.append(
            f"| `{r['name']}` | **{r['verdict']}** | {f['n']} | **{f['m25']}** | {f['m25_first']} | "
            f"{f['t15']} | {f['maj']} | {f['avg_mfe']} | {o['m25']} |"
        )

    lines += ["", "## 2) Auto-search on run2|3 (feature combos ≥90% m25, n≥8)", ""]
    if not auto:
        lines.append("_No run2|3 combo cleared 90% m25 with n≥8._")
    else:
        lines.append("| Feats | n | m25% | Train | OOS | T15% | Maj% | avg MFE |")
        lines.append("|---|---:|---:|---|---|---:|---:|---:|")
        for a in auto[:15]:
            lines.append(
                f"| `run + {a['feats']}` | {a['n']} | **{a['m25']}** | "
                f"{a['train_n']}/{a['train_m25']}% | {a['oos_n']}/{a['oos_m25']}% | "
                f"{a['t15']} | {a['maj']} | {a['avg_mfe']} |"
            )

    lines += ["", "## 3) Verdict — most accurate entry logic", ""]
    if proven:
        b = proven[0]
        lines.append(f"**PROVEN @100% m25:** `{b['name']}` · n={b['full']['n']} · OOS also 100%.")
        lines.append("")
        lines.append("### Exact entry rule")
        lines.append("")
        lines.append("```")
        lines.append("IF primary/patterns in {bull_run2, bull_run3, bear_run2, bear_run3}")
        lines.append("AND control_with (buyer bar for BUY / seller bar for SELL)")
        lines.append("AND AD with side")
        lines.append("+ any extra filters named in the gate")
        lines.append("THEN")
        lines.append("  side  = BUY if bull_run* else SELL")
        lines.append("  entry = close of the pattern completion 1m candle")
        lines.append("```")
    elif promising:
        b = promising[0]
        lines.append(f"**PROMISING ≥95%:** `{b['name']}` · n={b['full']['n']} · m25={b['full']['m25']}%")
        lines.append("Not 100% yet — do not claim perfect precision.")
    else:
        top = ranked[0]
        lines.append(
            f"**No 100% book.** Highest precision: `{top['name']}` · "
            f"m25=**{top['full']['m25']}%** · n={top['full']['n']} · "
            f"OOS {top['oos']['m25']}% · T15 {top['full']['t15']}% · maj {top['full']['maj']}%"
        )
        lines.append("")
        lines.append("100% on ≥25pt raw moves is extremely hard once n is meaningful — "
                     "report the tightest stable gate, not a fake perfect.")

    if union_rows:
        lines += [
            "",
            "## 4) Union with oracle_t15_clean twin (TierAB) — only if gate ≥90%",
            "",
            "| Book | n | m25% | T15% | Maj% | avg MFE |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for u in union_rows:
            lines.append(
                f"| {u['book']} | {u['n']} | {u['m25']} | {u['t15']} | {u['maj']} | {u['avg_mfe']} |"
            )
        uni = union_rows[-1]
        if uni["m25"] is not None and uni["m25"] >= 90:
            lines.append("")
            lines.append(f"Union **holds** m25={uni['m25']}% — candidate to layer on clean.")
        else:
            lines.append("")
            lines.append(
                f"Union **dilutes** precision to m25={uni['m25']}% — **do not** union; keep gate separate."
            )

    lines += [
        "",
        f"## 5) Sample entries — `{top_name}`",
        "",
        "| Day | HM | Side | **Entry** | Pattern | MFE | m25 | T15 | Maj |",
        "|---|---|---|---:|---|---:|---|---|---|",
    ]
    for s in samples[:25]:
        lines.append(
            f"| {s['day']} | {s['hm']} | **{s['side']}** | **{s['entry']}** | `{s['primary']}` | "
            f"{s['mfe']} | {s['m25']} | {s['t15']} | {s['maj']} |"
        )
    if fails:
        lines += ["", f"Failures in sample (m25=False): **{len(fails)}** — these are why precision < 100%."]

    lines += [
        "",
        "## 6) Bottom line",
        "",
        "- We are **not** optimizing call count.",
        "- Entry = **pattern close** + **side from bull/bear run**.",
        "- Ship only a gate that is **PROVEN_100** or at least **PROMISING_95** on TRAIN and OOS.",
        "- If union with TierAB drops m25 below 90%, keep books separate.",
        "",
        f"_Generated in {payload['took_sec']}s._",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    if best:
        print(
            f"BEST={best['name']} m25={best['full']['m25']}% n={best['full']['n']} "
            f"verdict={best['verdict']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
