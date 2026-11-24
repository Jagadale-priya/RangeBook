"""RESEARCH ONLY — Deep hunt for MORE ACCURATE ≥25pt entries (side + price only).

Prior IGN100 (ctrl+room+disp10+bounce) = 100% raw m25 but n=12 and some fat MAE.
This pass optimizes TRUE one-direction accuracy:

  m25_first : reach +25 BEFORE −25 adverse (favour-first to 25)
  clean15   : MFE≥25 and MAE≤15
  clean10   : MFE≥25 and MAE≤10

Method:
  1) Find every true ≥25pt same-color impulse ignition (ground truth)
  2) Feature rates on those ignitions (what is almost always true)
  3) Forward-test candidate gates on textbook events (completion + ignition)
  4) Walk-forward TRAIN/OOS · require both sides high precision
  5) Greedy tighten from best base until 100% or best stable ≥95%

  python -u prod_live/tests/builders/_diag_scalp_entry_accuracy_deep.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
from _diag_scalp_impulse_green_run_entry import find_impulse_runs  # noqa: E402

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ENTRY_ACCURACY_DEEP.md"
REPORT_JSON = OUT / "NIFTY_1M_ENTRY_ACCURACY_DEEP.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 120  # ~6 months
LOOKBACK_CAL = 240
FWD = 60
M25 = 25.0
RUN_PATS = {"bull_run2", "bull_run3", "bear_run2", "bear_run3"}
STRONG_PATS = RUN_PATS | {
    "bull_engulf",
    "bear_engulf",
    "marubozu_bull",
    "marubozu_bear",
    "three_outside_up",
    "three_outside_dn",
    "belt_bull",
    "belt_bear",
    "bull_kicker",
    "bear_kicker",
    "three_soldiers",
    "three_crows",
}


def label_path(e, h, l, c, day, entry_i, entry_px, side):
    d = e["day"]
    mfe = mae = 0.0
    hit25 = None
    end = min(len(c) - 1, entry_i + FWD)
    for j in range(entry_i + 1, end + 1):
        if day[j] != d:
            break
        if side == "BUY":
            fav = float(h[j]) - entry_px
            adv = entry_px - float(l[j])
        else:
            fav = entry_px - float(l[j])
            adv = float(h[j]) - entry_px
        mfe = max(mfe, fav)
        mae = max(mae, adv)
        if hit25 is None and mfe >= M25:
            hit25 = j
    e["_mfe"] = round(mfe, 2)
    e["_mae"] = round(mae, 2)
    e["_m25"] = mfe >= M25
    e["_clean15"] = mfe >= M25 and mae <= 15.0
    e["_clean10"] = mfe >= M25 and mae <= 10.0
    e["_m25_first"] = False
    if hit25 is not None:
        adv = 0.0
        ok = True
        for j in range(entry_i + 1, hit25 + 1):
            if side == "BUY":
                adv = max(adv, entry_px - float(l[j]))
            else:
                adv = max(adv, float(h[j]) - entry_px)
            if adv >= M25:
                ok = False
                break
        e["_m25_first"] = ok
        e["_mae_to_25"] = round(adv, 2)
    else:
        e["_mae_to_25"] = None


def trail_score(e, h, l, c, ema34, entry_i, side):
    ok, _, _, _ = path_ma_trail_strict(h, l, c, ema34, entry_i, side, 25.0)
    e["_t25"] = bool(ok)
    ok15, _, _, _ = path_ma_trail_strict(h, l, c, ema34, entry_i, side, 15.0)
    e["_t15"] = bool(ok15)


def prec(rows, key):
    if not rows:
        return None, 0
    return round(100.0 * sum(1 for e in rows if e.get(key)) / len(rows), 2), len(rows)


def pack_stats(rows, key, mid):
    tr = [e for e in rows if e["day"] < mid]
    oo = [e for e in rows if e["day"] >= mid]
    p, n = prec(rows, key)
    pt, nt = prec(tr, key)
    po, no = prec(oo, key)
    return {
        "n": n,
        "prec": p,
        "train_n": nt,
        "train_prec": pt,
        "oos_n": no,
        "oos_prec": po,
        "avg_mfe": round(float(np.mean([e["_mfe"] for e in rows])), 2) if rows else None,
        "avg_mae": round(float(np.mean([e["_mae"] for e in rows])), 2) if rows else None,
        "t25": round(100.0 * sum(1 for e in rows if e.get("_t25")) / n, 2) if n else None,
        "t15": round(100.0 * sum(1 for e in rows if e.get("_t15")) / n, 2) if n else None,
        "m25": round(100.0 * sum(1 for e in rows if e.get("_m25")) / n, 2) if n else None,
        "m25_first": round(100.0 * sum(1 for e in rows if e.get("_m25_first")) / n, 2) if n else None,
        "clean15": round(100.0 * sum(1 for e in rows if e.get("_clean15")) / n, 2) if n else None,
    }


def verdict(st, soft=95.0, hard=100.0, min_n=12, min_half=5):
    if not st or st["n"] < min_n:
        return "THIN"
    if (
        st["prec"] == hard
        and st["train_prec"] == hard
        and st["oos_prec"] == hard
        and (st["train_n"] or 0) >= min_half
        and (st["oos_n"] or 0) >= min_half
    ):
        return "PROVEN_100"
    if (
        st["prec"] is not None
        and st["prec"] >= soft
        and st["train_prec"] is not None
        and st["oos_prec"] is not None
        and st["train_prec"] >= soft
        and st["oos_prec"] >= soft
        and (st["train_n"] or 0) >= min_half
        and (st["oos_n"] or 0) >= min_half
    ):
        return "PROMISING_95"
    if st["prec"] is not None and st["prec"] >= 90 and (st["oos_prec"] or 0) >= 85:
        return "HIGH_90"
    return "WEAK"


FEATS = [
    "ctrl",
    "ad_with",
    "held",
    "not_extreme",
    "room_ok",
    "runway2",
    "hold_break",
    "bounce",
    "prev_opposite",
    "disp10",
    "disp15",
    "big_body",
    "is_run",
    "run3",
    "strong_pat",
    "tier_ab",
    "di_ok",
    "vwap_with",
    "gate_hard34",
]


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("DEEP ENTRY ACCURACY (≥25 one-direction) — RESEARCH ONLY", flush=True)

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
    print(f"window {day_lo}→{day_hi} n={n_days} OOS≥{mid}", flush=True)

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
    atr = df["atr14"].astype(float).values
    day = np.array([str(ts.date()) for ts in df.index])
    ad_r = df["ad_rising"].astype(bool).values if "ad_rising" in df.columns else np.zeros(len(c), dtype=bool)
    ad_f = df["ad_falling"].astype(bool).values if "ad_falling" in df.columns else np.zeros(len(c), dtype=bool)
    idx = df.index

    # ---- Ground-truth impulses ≥25 ----
    runs = find_impulse_runs(df, min_bars=3, min_pts=25.0)
    runs = [r for r in runs if r["day"] in keep and MINS_LO <= int(r["mins"]) <= MINS_HI]
    print(f"true ≥25pt impulses: {len(runs)}", flush=True)

    # Feature snapshot at impulse ignition (borrow nearby event or compute)
    by_i = {int(e["full_i"]): e for e in events if e["day"] in keep}
    truth_feat = Counter()
    truth_n = 0
    for r in runs:
        i = int(r["full_i"])
        side = r["decision"]
        base_e = by_i.get(i) or by_i.get(i + 1) or by_i.get(i + 2) or {}
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        body = abs(float(c[i]) - float(o[i]))
        feats = {
            "ctrl": bool(base_e.get("control_with")),
            "ad_with": (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i])),
            "held": bool(base_e.get("di_ok") and base_e.get("gate_hard34") and base_e.get("vwap_with"))
            if base_e
            else False,
            "room_ok": bool(base_e.get("clear_path")),
            "bounce": bool(base_e.get("sr_bounce")),
            "runway2": bool(base_e.get("runway_2atr")),
            "not_extreme": not bool(base_e.get("into_sess_extreme")) if base_e else True,
            "disp10": body >= 1.0 * a,
            "disp15": body >= 1.5 * a,
            "big_body": body >= max(8.0, 0.6 * a),
            "prev_opposite": (side == "BUY" and i > 0 and c[i - 1] < o[i - 1])
            or (side == "SELL" and i > 0 and c[i - 1] > o[i - 1]),
            "hold_break": bool(base_e.get("regime") == "hold_break" or base_e.get("hold_break_setup")),
        }
        truth_n += 1
        for k, v in feats.items():
            if v:
                truth_feat[k] += 1
    truth_rates = {k: round(100.0 * truth_feat[k] / truth_n, 1) for k in sorted(truth_feat)} if truth_n else {}
    print(f"truth feature rates (top): {sorted(truth_rates.items(), key=lambda x: -x[1])[:10]}", flush=True)

    # ---- Build candidate pool (completion + ignition for strong patterns) ----
    pool: List[dict] = []
    for e0 in events:
        if e0["day"] not in keep:
            continue
        if not (bool(in_session(e0)) and MINS_LO <= int(e0["mins"]) <= MINS_HI):
            continue
        i = int(e0["full_i"])
        side = e0["decision"]
        prim = str(e0.get("primary") or "")
        pats = set(e0.get("patterns") or []) | ({prim} if prim else set())
        e = dict(e0)
        e["side"] = side
        e["ctrl"] = bool(e.get("control_with"))
        e["ad_with"] = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))
        e["held"] = held_gate(e)
        e["not_extreme"] = not bool(e.get("into_sess_extreme"))
        e["room_ok"] = bool(e.get("clear_path"))
        e["runway2"] = bool(e.get("runway_2atr"))
        e["hold_break"] = e.get("regime") == "hold_break" or bool(e.get("hold_break_setup"))
        e["bounce"] = bool(e.get("sr_bounce"))
        e["tier_ab"] = bool(e.get("setup_ok"))
        e["di_ok"] = bool(e.get("di_ok"))
        e["vwap_with"] = bool(e.get("vwap_with"))
        e["gate_hard34"] = bool(e.get("gate_hard34"))
        e["is_run"] = bool(pats & RUN_PATS)
        e["run3"] = bool(pats & {"bull_run3", "bear_run3"})
        e["run2"] = bool(pats & {"bull_run2", "bear_run2"})
        e["strong_pat"] = bool(pats & STRONG_PATS)
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        body = abs(float(c[i]) - float(o[i]))
        e["disp10"] = body >= 1.0 * a
        e["disp15"] = body >= 1.5 * a
        e["big_body"] = body >= max(8.0, 0.6 * a)
        if i > 0:
            e["prev_opposite"] = (side == "BUY" and c[i - 1] < o[i - 1]) or (
                side == "SELL" and c[i - 1] > o[i - 1]
            )
        else:
            e["prev_opposite"] = False

        # completion
        ec = dict(e)
        ec["entry_mode"] = "completion"
        ec["entry_i"] = i
        ec["entry_px"] = round(float(c[i]), 2)
        label_path(ec, h, l, c, day, i, float(c[i]), side)
        trail_score(ec, h, l, c, ema34, i, side)
        pool.append(ec)

        # ignition for runs
        if e["is_run"]:
            ig = i - 2 if e["run3"] else i - 1
            if ig >= 0 and day[ig] == day[i]:
                ei = dict(e)
                ei["entry_mode"] = "ignition"
                ei["entry_i"] = ig
                ei["entry_px"] = round(float(c[ig]), 2)
                ei["hm"] = idx[ig].strftime("%H:%M")
                ei["ad_with"] = (side == "BUY" and bool(ad_r[ig])) or (side == "SELL" and bool(ad_f[ig]))
                a_ig = float(atr[ig]) if np.isfinite(atr[ig]) and atr[ig] > 0 else a
                body_ig = abs(float(c[ig]) - float(o[ig]))
                ei["disp10"] = body_ig >= 1.0 * a_ig
                ei["disp15"] = body_ig >= 1.5 * a_ig
                ei["big_body"] = body_ig >= max(8.0, 0.6 * a_ig)
                if ig > 0:
                    ei["prev_opposite"] = (side == "BUY" and c[ig - 1] < o[ig - 1]) or (
                        side == "SELL" and c[ig - 1] > o[ig - 1]
                    )
                label_path(ei, h, l, c, day, ig, float(c[ig]), side)
                trail_score(ei, h, l, c, ema34, ig, side)
                pool.append(ei)

        # engulf / marubozu / kicker as completion-only strong
        if (pats & STRONG_PATS) and not e["is_run"]:
            pass  # already have completion

    print(f"pool={len(pool)}", flush=True)

    # ---- Manual priority (accuracy-first) ----
    def gate(name, pred, mode=None, key="_m25_first"):
        rows = [e for e in pool if pred(e) and (mode is None or e["entry_mode"] == mode)]
        st = pack_stats(rows, key, mid)
        st_c15 = pack_stats(rows, "_clean15", mid)
        st_m25 = pack_stats(rows, "_m25", mid)
        return {
            "name": name,
            "label": key,
            "stats": st,
            "clean15": st_c15,
            "raw_m25": st_m25,
            "verdict": verdict(st),
            "verdict_clean15": verdict(st_c15, min_n=10),
            "samples": [
                {
                    "day": e["day"],
                    "hm": e.get("hm"),
                    "side": e["side"],
                    "entry": e["entry_px"],
                    "mode": e["entry_mode"],
                    "primary": e.get("primary"),
                    "mfe": e["_mfe"],
                    "mae": e["_mae"],
                    "m25_first": e["_m25_first"],
                    "clean15": e["_clean15"],
                    "t25": e["_t25"],
                }
                for e in sorted(rows, key=lambda x: (x["day"], x.get("mins", 0)))[:20]
            ],
        }

    priority = [
        # Old IGN100 on stricter label
        gate(
            "OLD IGN100 ignition ctrl+room+disp10+bounce",
            lambda e: e["is_run"] and e["ctrl"] and e["room_ok"] and e["disp10"] and e["bounce"],
            "ignition",
            "_m25_first",
        ),
        gate(
            "OLD IGN100 → clean15",
            lambda e: e["is_run"] and e["ctrl"] and e["room_ok"] and e["disp10"] and e["bounce"],
            "ignition",
            "_clean15",
        ),
        # Tighten old with MAE-friendly filters
        gate(
            "IGN + ctrl+room+disp10+bounce+held",
            lambda e: e["is_run"] and e["ctrl"] and e["room_ok"] and e["disp10"] and e["bounce"] and e["held"],
            "ignition",
            "_m25_first",
        ),
        gate(
            "IGN + ctrl+room+disp10+bounce+ad",
            lambda e: e["is_run"] and e["ctrl"] and e["room_ok"] and e["disp10"] and e["bounce"] and e["ad_with"],
            "ignition",
            "_m25_first",
        ),
        gate(
            "IGN + ctrl+room+disp15+bounce",
            lambda e: e["is_run"] and e["ctrl"] and e["room_ok"] and e["disp15"] and e["bounce"],
            "ignition",
            "_m25_first",
        ),
        gate(
            "IGN + ctrl+room+disp10+bounce+!extreme+held",
            lambda e: e["is_run"]
            and e["ctrl"]
            and e["room_ok"]
            and e["disp10"]
            and e["bounce"]
            and e["not_extreme"]
            and e["held"],
            "ignition",
            "_m25_first",
        ),
        gate(
            "IGN run3 + ctrl+room+disp10+bounce+ad+held",
            lambda e: e["run3"]
            and e["ctrl"]
            and e["room_ok"]
            and e["disp10"]
            and e["bounce"]
            and e["ad_with"]
            and e["held"],
            "ignition",
            "_m25_first",
        ),
        # Truth-inspired: prev_opposite is very common on impulses
        gate(
            "IGN + prev_opp+ctrl+ad+disp10+room",
            lambda e: e["is_run"]
            and e["prev_opposite"]
            and e["ctrl"]
            and e["ad_with"]
            and e["disp10"]
            and e["room_ok"],
            "ignition",
            "_m25_first",
        ),
        gate(
            "IGN + prev_opp+ctrl+ad+disp10+bounce",
            lambda e: e["is_run"]
            and e["prev_opposite"]
            and e["ctrl"]
            and e["ad_with"]
            and e["disp10"]
            and e["bounce"],
            "ignition",
            "_m25_first",
        ),
        gate(
            "IGN + prev_opp+held+ad+disp10+room+bounce",
            lambda e: e["is_run"]
            and e["prev_opposite"]
            and e["held"]
            and e["ad_with"]
            and e["disp10"]
            and e["room_ok"]
            and e["bounce"],
            "ignition",
            "_m25_first",
        ),
        # hold_break family
        gate(
            "COMP hold_break+ctrl+ad+disp10+room",
            lambda e: e["hold_break"] and e["ctrl"] and e["ad_with"] and e["disp10"] and e["room_ok"],
            "completion",
            "_m25_first",
        ),
        gate(
            "COMP hold_break+ctrl+held+bounce+disp10",
            lambda e: e["hold_break"] and e["ctrl"] and e["held"] and e["bounce"] and e["disp10"],
            "completion",
            "_m25_first",
        ),
        # strong patterns
        gate(
            "COMP strong+ctrl+ad+held+room+disp10",
            lambda e: e["strong_pat"]
            and e["ctrl"]
            and e["ad_with"]
            and e["held"]
            and e["room_ok"]
            and e["disp10"],
            "completion",
            "_m25_first",
        ),
        gate(
            "COMP engulf/maru + ctrl+ad+held+bounce+room",
            lambda e: str(e.get("primary") or "")
            in (
                "bull_engulf",
                "bear_engulf",
                "marubozu_bull",
                "marubozu_bear",
                "three_outside_up",
                "three_outside_dn",
            )
            and e["ctrl"]
            and e["ad_with"]
            and e["held"]
            and e["bounce"]
            and e["room_ok"],
            "completion",
            "_m25_first",
        ),
    ]

    for p in priority:
        s = p["stats"]
        print(
            f"  {p['name']}: n={s['n']} {p['label']}={s['prec']}% "
            f"OOS={s['oos_prec']}% clean15={p['clean15']['prec']}% → {p['verdict']}",
            flush=True,
        )

    # ---- Exhaustive hunt on ignition runs for m25_first & clean15 ----
    def hunt(base_rows, label, min_n=10, min_prec=90.0):
        found = []
        feat_pool = [
            "ctrl",
            "ad_with",
            "held",
            "not_extreme",
            "room_ok",
            "runway2",
            "bounce",
            "prev_opposite",
            "disp10",
            "disp15",
            "big_body",
            "run3",
            "hold_break",
        ]
        for k in (2, 3, 4, 5):
            for combo in combinations(feat_pool, k):
                sub = [e for e in base_rows if all(e.get(f) for f in combo)]
                if len(sub) < min_n:
                    continue
                st = pack_stats(sub, label, mid)
                if st["prec"] is None or st["prec"] < min_prec:
                    continue
                found.append(
                    {
                        "name": "+".join(combo),
                        "label": label,
                        **st,
                        "verdict": verdict(st, min_n=min_n),
                    }
                )
        found.sort(
            key=lambda x: (
                0 if x["verdict"] == "PROVEN_100" else 1 if x["verdict"] == "PROMISING_95" else 2,
                -(x["prec"] or 0),
                -(x["oos_prec"] or 0),
                -x["n"],
            )
        )
        # dedupe keep best
        seen = set()
        out = []
        for x in found:
            if x["name"] in seen:
                continue
            seen.add(x["name"])
            out.append(x)
        return out[:30]

    ign_runs = [e for e in pool if e["entry_mode"] == "ignition" and e["is_run"]]
    print(f"hunting ignition runs n={len(ign_runs)} for m25_first…", flush=True)
    hunt_first = hunt(ign_runs, "_m25_first", min_n=10, min_prec=90.0)
    print(f"  ≥90% m25_first: {len(hunt_first)}", flush=True)
    print(f"hunting ignition runs for clean15…", flush=True)
    hunt_clean = hunt(ign_runs, "_clean15", min_n=8, min_prec=85.0)
    print(f"  ≥85% clean15: {len(hunt_clean)}", flush=True)

    # Also hunt all completion strong
    comp_strong = [e for e in pool if e["entry_mode"] == "completion" and e["strong_pat"]]
    print(f"hunting completion strong n={len(comp_strong)} for m25_first…", flush=True)
    hunt_strong = hunt(comp_strong, "_m25_first", min_n=10, min_prec=90.0)
    print(f"  ≥90%: {len(hunt_strong)}", flush=True)

    # Greedy tighten: start from ignition+ctrl+ad+disp10, add best feature by OOS m25_first
    def greedy(base_pred, label="_m25_first"):
        cur = [e for e in ign_runs if base_pred(e)]
        path = ["base"]
        hist = [pack_stats(cur, label, mid)]
        remaining = [
            "held",
            "bounce",
            "room_ok",
            "runway2",
            "not_extreme",
            "prev_opposite",
            "disp15",
            "run3",
            "hold_break",
            "big_body",
        ]
        while remaining and cur:
            best_f, best_st, best_sub = None, None, None
            for f in remaining:
                sub = [e for e in cur if e.get(f)]
                if len(sub) < 8:
                    continue
                st = pack_stats(sub, label, mid)
                # maximize OOS prec then full prec then n
                score = (st["oos_prec"] or 0, st["prec"] or 0, st["n"])
                if best_st is None or score > (
                    best_st["oos_prec"] or 0,
                    best_st["prec"] or 0,
                    best_st["n"],
                ):
                    best_f, best_st, best_sub = f, st, sub
            if best_f is None:
                break
            # stop if adding doesn't help OOS prec and cuts n hard
            prev = hist[-1]
            if (best_st["oos_prec"] or 0) < (prev["oos_prec"] or 0) and best_st["n"] < prev["n"] * 0.5:
                break
            path.append(best_f)
            hist.append(best_st)
            cur = best_sub
            remaining.remove(best_f)
            if best_st["prec"] == 100 and best_st["oos_prec"] == 100 and best_st["train_prec"] == 100:
                break
        return {"path": path, "hist": hist, "final": hist[-1] if hist else None, "n_left": len(cur)}

    greedy_first = greedy(lambda e: e["ctrl"] and e["ad_with"] and e["disp10"], "_m25_first")
    greedy_clean = greedy(lambda e: e["ctrl"] and e["ad_with"] and e["disp10"], "_clean15")
    print(f"greedy m25_first path={greedy_first['path']} final={greedy_first['final']}", flush=True)
    print(f"greedy clean15 path={greedy_clean['path']} final={greedy_clean['final']}", flush=True)

    # Pick winners
    proven = [p for p in priority if p["verdict"] == "PROVEN_100"]
    promising = [p for p in priority if p["verdict"] == "PROMISING_95"]
    hunt_proven = [h for h in hunt_first + hunt_clean + hunt_strong if h["verdict"] == "PROVEN_100"]
    hunt_prom = [h for h in hunt_first + hunt_clean + hunt_strong if h["verdict"] == "PROMISING_95"]

    # Best by (verdict, oos_prec, prec, n) on m25_first among priority
    best_pri = sorted(
        priority,
        key=lambda p: (
            0 if p["verdict"] == "PROVEN_100" else 1 if p["verdict"] == "PROMISING_95" else 2 if p["verdict"] == "HIGH_90" else 3,
            -(p["stats"]["oos_prec"] or 0),
            -(p["stats"]["prec"] or 0),
            -(p["clean15"]["prec"] or 0),
            p["stats"]["n"],
        ),
    )[0]

    payload = {
        "ok": True,
        "research_only": True,
        "window": {"day_lo": day_lo, "day_hi": day_hi, "n_days": n_days, "oos_from": mid},
        "goal": "more accurate ≥25pt one-direction entry (side + price)",
        "labels": {
            "m25_first": "reach +25 before −25 adverse",
            "clean15": "MFE≥25 and MAE≤15",
            "clean10": "MFE≥25 and MAE≤10",
        },
        "truth_impulses": len(runs),
        "truth_feat_rates": truth_rates,
        "priority": [
            {
                "name": p["name"],
                "verdict": p["verdict"],
                "verdict_clean15": p["verdict_clean15"],
                "stats": p["stats"],
                "clean15": p["clean15"],
                "raw_m25": p["raw_m25"],
                "samples": p["samples"][:12],
            }
            for p in priority
        ],
        "hunt_m25_first": hunt_first[:15],
        "hunt_clean15": hunt_clean[:15],
        "hunt_strong": hunt_strong[:10],
        "greedy_m25_first": greedy_first,
        "greedy_clean15": greedy_clean,
        "proven_priority": [p["name"] for p in proven],
        "promising_priority": [p["name"] for p in promising],
        "hunt_proven": hunt_proven[:10],
        "hunt_promising": hunt_prom[:10],
        "best_priority": best_pri["name"],
        "took_sec": round(time.time() - t0, 1),
    }

    lines = [
        "# NIFTY 1m — **More accurate** ≥25pt entry (deep)",
        "",
        "> Precision over calls. Metric = **one-direction** quality, not raw MFE touch.",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS from **{mid}**.",
        "",
        "## Accuracy metrics (stricter than raw m25)",
        "",
        "| Metric | Meaning | Why |",
        "|---|---|---|",
        "| **m25_first** | +25 pts before −25 adverse | True directional capture |",
        "| **clean15** | MFE≥25 and MAE≤15 | Move is mostly one-way |",
        "| raw m25 | MFE≥25 anytime | Old IGN100 metric (can have huge MAE) |",
        "",
        f"Ground-truth ≥25pt impulses in window: **{len(runs)}**.",
        "",
        "### What is usually true at real impulse ignition",
        "",
        "| Feature | % of true ≥25 ignitions |",
        "|---|---:|",
    ]
    for k, v in sorted(truth_rates.items(), key=lambda x: -x[1]):
        lines.append(f"| `{k}` | {v} |")

    lines += [
        "",
        "## 1) Priority gates (ranked internally; table by m25_first)",
        "",
        "| Gate | Verdict | n | **m25_first%** | OOS | clean15% | raw m25% | T25% |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    order = sorted(
        priority,
        key=lambda p: (
            0 if p["verdict"] == "PROVEN_100" else 1 if p["verdict"] == "PROMISING_95" else 2,
            -(p["stats"]["prec"] or 0),
            -(p["stats"]["oos_prec"] or 0),
        ),
    )
    for p in order:
        s, c15, r = p["stats"], p["clean15"], p["raw_m25"]
        lines.append(
            f"| `{p['name']}` | **{p['verdict']}** | {s['n']} | **{s['prec']}** | {s['oos_prec']} | "
            f"{c15['prec']} | {r['prec']} | {s['t25']} |"
        )

    lines += [
        "",
        "## 2) Exhaustive hunt (ignition runs)",
        "",
        "### Best m25_first (≥90%)",
        "",
    ]
    if not hunt_first:
        lines.append("_None ≥90% with n≥10._")
    else:
        lines.append("| Feats | n | prec | Train | OOS | Verdict |")
        lines.append("|---|---:|---:|---|---|---|")
        for h_ in hunt_first[:12]:
            lines.append(
                f"| `ign+{h_['name']}` | {h_['n']} | **{h_['prec']}** | "
                f"{h_['train_n']}/{h_['train_prec']}% | {h_['oos_n']}/{h_['oos_prec']}% | **{h_['verdict']}** |"
            )

    lines += ["", "### Best clean15 (≥85%)", ""]
    if not hunt_clean:
        lines.append("_None ≥85% with n≥8._")
    else:
        lines.append("| Feats | n | prec | Train | OOS | Verdict |")
        lines.append("|---|---:|---:|---|---|---|")
        for h_ in hunt_clean[:12]:
            lines.append(
                f"| `ign+{h_['name']}` | {h_['n']} | **{h_['prec']}** | "
                f"{h_['train_n']}/{h_['train_prec']}% | {h_['oos_n']}/{h_['oos_prec']}% | **{h_['verdict']}** |"
            )

    lines += [
        "",
        "## 3) Greedy tighten (from ctrl+AD+disp10 ignition)",
        "",
        f"- **m25_first path:** `{' → '.join(greedy_first['path'])}`",
        f"  - final n={greedy_first['final']['n'] if greedy_first['final'] else 0} "
        f"prec={greedy_first['final']['prec'] if greedy_first['final'] else None}% "
        f"OOS={greedy_first['final']['oos_prec'] if greedy_first['final'] else None}%",
        f"- **clean15 path:** `{' → '.join(greedy_clean['path'])}`",
        f"  - final n={greedy_clean['final']['n'] if greedy_clean['final'] else 0} "
        f"prec={greedy_clean['final']['prec'] if greedy_clean['final'] else None}% "
        f"OOS={greedy_clean['final']['oos_prec'] if greedy_clean['final'] else None}%",
        "",
        "## 4) Most accurate rule now",
        "",
    ]

    # Choose best overall: hunt proven first, else priority proven, else best_pri
    winner = None
    if hunt_proven:
        winner = ("hunt", hunt_proven[0])
    elif proven:
        winner = ("priority", proven[0])
    elif hunt_prom:
        winner = ("hunt_prom", hunt_prom[0])
    elif promising:
        winner = ("priority_prom", promising[0])
    else:
        winner = ("best_effort", best_pri)

    if winner[0] == "hunt":
        w = winner[1]
        lines += [
            f"**PROVEN_100 on {w['label']}:** ignition + `{w['name']}`",
            "",
            f"- n=**{w['n']}** · prec=**{w['prec']}%** · TRAIN {w['train_n']}/{w['train_prec']}% · OOS {w['oos_n']}/{w['oos_prec']}%",
            f"- avg MFE {w['avg_mfe']} · avg MAE {w['avg_mae']} · T25 {w['t25']}%",
            "",
            "```",
            "ENTRY MODE : ignition (first bar of bull/bear run2|3)",
            f"FILTERS    : {w['name'].replace('+', ' + ')}",
            "SIDE       : BUY if bull_run* else SELL",
            "ENTRY PX   : close of ignition 1m candle",
            "```",
        ]
    elif winner[0].startswith("priority"):
        w = winner[1]
        lines += [
            f"**{w['verdict']}:** `{w['name']}`",
            "",
            f"- m25_first **{w['stats']['prec']}%** (OOS {w['stats']['oos_prec']}%) · n={w['stats']['n']}",
            f"- clean15 **{w['clean15']['prec']}%** · raw m25 **{w['raw_m25']['prec']}%**",
            "",
            "### Samples",
            "",
            "| Day | HM | Side | Entry | MFE | MAE | m25_first | clean15 |",
            "|---|---|---|---:|---:|---:|---|---|",
        ]
        for s in w["samples"][:15]:
            lines.append(
                f"| {s['day']} | {s['hm']} | **{s['side']}** | **{s['entry']}** | "
                f"{s['mfe']} | {s['mae']} | {s['m25_first']} | {s['clean15']} |"
            )
    else:
        w = winner[1]
        lines += [
            f"**Best effort (not proven):** `{w['name']}` · {w['verdict']}",
            f"- m25_first {w['stats']['prec']}% OOS {w['stats']['oos_prec']}% · clean15 {w['clean15']['prec']}%",
        ]

    lines += [
        "",
        "## 5) vs old IGN100 (raw m25 100%)",
        "",
        "- Old IGN100 optimized **raw MFE≥25** — can still chop hard (MAE 40–180 on some hits).",
        "- This pass requires **m25_first / clean15** — harder, more honest “one direction”.",
        "- If a new PROVEN_100 appears above, **replace** live `run_ignition_100` with it.",
        "- If not, keep IGN100 but treat it as sparse raw-25, not clean one-way.",
        "",
        f"_Generated in {payload['took_sec']}s._",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    print(f"BEST={best_pri['name']} verdict={best_pri['verdict']} hunt_proven={len(hunt_proven)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
