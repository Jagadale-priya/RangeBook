"""RESEARCH ONLY — deep search for ≥80% accurate entry logic (S/R + structure).

NOT wired to live Scalper. Do not apply until explicitly approved.

Targets (all entry-path, no SL/T as primary):
  Acc%     — MFE≥20 and MFE > MAE          (accurate directional entry)
  Dom%     — MFE≥15 and MFE ≥ 1.5×MAE
  OneDir%  — MFE≥20 and MFE ≥ 2×MAE
  Path12%  — favour +12 before adverse -8  (timing accuracy)
  Clean%   — MFE≥30 and MAE≤12

Search:
  1) Hand stacks (S/R bounce/break/reclaim/runway/hold_break)
  2) Combinatorial AND of atomic flags (size 2..5)
  3) Require ≥80% on BOTH 2m and 6m with min n + monthly stability

  python -u prod_live/tests/builders/_diag_scalp_sr_80pct_deep.py
"""
from __future__ import annotations

import itertools
import json
import sys
import time
from collections import defaultdict
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
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers, enrich_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402
from _diag_scalp_sr_highmove_proven import (  # noqa: E402
    HORIZON,
    enrich_sr_archetypes,
    in_session,
    one_per_gap,
    score_path,
)

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SR_80PCT_DEEP.md"
REPORT_JSON = OUT / "NIFTY_1M_SR_80PCT_DEEP.json"
CACHE = OUT / "_cache_sr_80pct_pool6.pkl"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
TARGET = 80.0
MIN_N_2M = 12
MIN_N_6M = 20
MIN_N_MONTH = 5


def score_timing(events, df):
    """Favour-first / path timing accuracy on top of MFE scores."""
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        entry = float(c[i])
        end = min(len(c) - 1, i + HORIZON)
        fav8 = adv5 = path12 = path15 = None
        for j in range(i + 1, end + 1):
            if side == "BUY":
                up, dn = float(h[j]) - entry, entry - float(l[j])
            else:
                up, dn = entry - float(l[j]), float(h[j]) - entry
            if fav8 is None and up >= 8:
                fav8 = j - i
            if adv5 is None and dn >= 5:
                adv5 = j - i
            if path12 is None and up >= 12:
                path12 = j - i
            if path15 is None and up >= 15:
                path15 = j - i
        e["fav1st"] = bool(fav8 is not None and (adv5 is None or fav8 < adv5))
        e["path12"] = bool(path12 is not None and (adv5 is None or path12 <= (adv5 or 999)))
        # stricter: +12 before -8
        adv8 = None
        for j in range(i + 1, end + 1):
            if side == "BUY":
                dn = entry - float(l[j])
            else:
                dn = float(h[j]) - entry
            if adv8 is None and dn >= 8:
                adv8 = j - i
                break
        e["path12_strict"] = bool(
            path12 is not None and (adv8 is None or path12 < adv8)
        )
        e["path15"] = bool(path15 is not None and (adv8 is None or path15 < (adv8 or 999)))
        mfe = float(e.get("mfe") or 0)
        mae = float(e.get("mae") or 0)
        e["acc"] = bool(mfe >= 20 and mfe > mae)  # accurate directional entry
        e["dom"] = bool(mfe >= 15 and mfe >= 1.5 * max(mae, 1.0))
        e["dom20"] = bool(mfe >= 20 and mfe >= 1.5 * max(mae, 1.0))


def enrich_deep_atoms(events, df):
    """Extra precision atoms for ≥80% hunt."""
    c = df["Close"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    o = df["Open"].astype(float).values
    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        a = float(e.get("atr") or 8.0)
        room_fav = float(e.get("room_fav") or 999)
        room_ag = float(e.get("room_against") or 999)
        mins = int(e.get("mins") or 0)

        e["held"] = held_gate(e)
        e["not_extreme"] = not bool(e.get("into_sess_extreme"))
        e["clear15"] = room_fav >= 1.5 * a and e["not_extreme"]
        e["clear20"] = room_fav >= 2.0 * a and e["not_extreme"]
        e["clear30"] = room_fav >= 3.0 * a and e["not_extreme"]
        e["backed08"] = room_ag <= 0.8 * a
        e["backed10"] = room_ag <= 1.0 * a
        e["backed15"] = room_ag <= 1.5 * a

        e["di_spread_abs"] = abs(float(e.get("di_spread") or 0))
        e["di_ge8"] = e["di_spread_abs"] >= 8
        e["di_ge12"] = e["di_spread_abs"] >= 12
        e["adx_ge22"] = float(e.get("adx") or 0) >= 22
        e["adx_ge25"] = float(e.get("adx") or 0) >= 25

        e["open_slot"] = 9 * 60 + 30 <= mins < 11 * 60  # 09:30–11:00
        e["mid_slot"] = 11 * 60 <= mins < 13 * 60
        e["pm_slot"] = 13 * 60 <= mins < 14 * 60 + 30
        e["after1030"] = mins >= 10 * 60 + 30
        e["after1100"] = mins >= 11 * 60

        body = abs(float(c[i]) - float(o[i]))
        rng = max(float(h[i]) - float(l[i]), 0.05)
        e["strong_body"] = body / rng >= 0.55
        e["close_ext"] = (side == "BUY" and float(e.get("close_loc") or 0) >= 0.75) or (
            side == "SELL" and float(e.get("close_loc") or 1) <= 0.25
        )

        e["reg_hold"] = e.get("regime") == "hold_break" or bool(e.get("hold_break_setup"))
        e["reg_trend"] = e.get("regime") == "trend"
        e["reg_flip"] = e.get("regime") == "flip"
        e["tier_ab"] = bool(e.get("setup_ok"))
        e["tier_a"] = e.get("setup_tier") == "A"

        e["bounce_clear"] = bool(e.get("sr_bounce") and e["clear15"])
        e["bounce_backed"] = bool(e.get("sr_bounce") and e["backed10"])
        e["break_runway"] = bool(e.get("sr_breakout") and e["clear20"])
        e["failrev_clear"] = bool(e.get("sr_failed_break_rev") and e["clear15"])
        e["vwap_clear"] = bool(e.get("vwap_reclaim") and e["clear15"])
        e["ctrl_sweep"] = bool(e.get("control_with") and e.get("sweep_with"))
        e["ctrl_clear"] = bool(e.get("control_with") and e["clear15"])
        e["macd_di"] = bool(e.get("macd_turn") and e.get("di_ok"))
        e["ind_strict3"] = bool(e.get("ind_strict3"))
        e["liq_magnet"] = bool(e.get("at_liq_magnet"))
        e["mom_with"] = bool(e.get("mom_with"))
        e["not_compress"] = not bool(e.get("compress"))


ATOMS = [
    "held",
    "not_extreme",
    "clear15",
    "clear20",
    "clear30",
    "backed08",
    "backed10",
    "control_with",
    "sweep_with",
    "ctrl_sweep",
    "sr_bounce",
    "sr_breakout",
    "sr_failed_break_rev",
    "vwap_reclaim",
    "runway_2atr",
    "runway_3atr",
    "reg_hold",
    "reg_trend",
    "reg_flip",
    "tier_a",
    "tier_ab",
    "di_ge8",
    "di_ge12",
    "adx_ge22",
    "adx_trend",
    "macd_turn",
    "macd_di",
    "ind_strict3",
    "strong_body",
    "close_ext",
    "open_slot",
    "mid_slot",
    "pm_slot",
    "after1030",
    "after1100",
    "liq_magnet",
    "mom_with",
    "not_compress",
    "bounce_clear",
    "bounce_backed",
    "break_runway",
    "failrev_clear",
    "vwap_clear",
    "ctrl_clear",
]

# atoms that should usually be present in high-precision stacks
CORE_HINT = {"held", "not_extreme", "clear15", "clear20", "control_with", "reg_hold", "sr_bounce"}


def summarize(rows, label, metric_keys=None):
    metric_keys = metric_keys or ("acc", "dom", "dom20", "one_dir", "clean_run", "fav1st", "path12", "path12_strict", "path15", "mfe20", "mfe30")
    n = len(rows)
    out = {"label": label, "n": n}
    if not n:
        for k in metric_keys:
            out[k] = None
        out["avg_mfe"] = out["avg_mae"] = out["avg_edge"] = None
        out["best_metric"] = None
        out["best_pct"] = -1
        return out

    def pct(key):
        return round(100.0 * sum(1 for e in rows if e.get(key)) / n, 2)

    for k in metric_keys:
        out[k] = pct(k)
    out["avg_mfe"] = round(float(np.mean([e["mfe"] for e in rows])), 2)
    out["avg_mae"] = round(float(np.mean([e["mae"] for e in rows])), 2)
    out["avg_edge"] = round(float(np.mean([e["edge"] for e in rows])), 2)
    # best among primary accuracy defs
    prim = ("acc", "dom", "dom20", "one_dir", "path12_strict", "path12", "fav1st")
    best_k, best_v = max(((k, out[k]) for k in prim if out.get(k) is not None), key=lambda x: x[1])
    out["best_metric"] = best_k
    out["best_pct"] = best_v
    return out


def monthly_stability(rows, metric, target=TARGET, min_n=MIN_N_MONTH):
    by = defaultdict(list)
    for e in rows:
        by[e["day"][:7]].append(e)
    months = []
    for m, rs in sorted(by.items()):
        if len(rs) < min_n:
            months.append((m, len(rs), None, False))
            continue
        pct = 100.0 * sum(1 for e in rs if e.get(metric)) / len(rs)
        months.append((m, len(rs), round(pct, 2), pct >= target))
    ok = [x for x in months if x[2] is not None]
    if not ok:
        return months, 0.0, False
    frac = sum(1 for x in ok if x[3]) / len(ok)
    return months, round(100.0 * frac, 1), frac >= 0.67  # ≥2/3 months hold


def hand_gates():
    """High-precision hand stacks aimed at ≥80%."""
    return [
        ("HELD raw", lambda e: e.get("held")),
        ("HELD + clear15", lambda e: e.get("held") and e.get("clear15")),
        ("HELD + clear20", lambda e: e.get("held") and e.get("clear20")),
        ("HELD + clear30", lambda e: e.get("held") and e.get("clear30")),
        ("TierA + clear15", lambda e: e.get("tier_a") and e.get("clear15")),
        ("TierA + clear20", lambda e: e.get("tier_a") and e.get("clear20")),
        ("TierAB + clear15", lambda e: e.get("tier_ab") and e.get("clear15")),
        ("TierAB + clear20", lambda e: e.get("tier_ab") and e.get("clear20")),
        ("hold + ctrl + clear15", lambda e: e.get("held") and e.get("reg_hold") and e.get("control_with") and e.get("clear15")),
        ("hold + ctrl + clear20", lambda e: e.get("held") and e.get("reg_hold") and e.get("control_with") and e.get("clear20")),
        ("hold + ctrl + sweep + clear15", lambda e: e.get("held") and e.get("reg_hold") and e.get("ctrl_sweep") and e.get("clear15")),
        ("hold + backed + ctrl + clear20", lambda e: e.get("held") and e.get("reg_hold") and e.get("backed10") and e.get("control_with") and e.get("clear20")),
        ("bounce + backed + ctrl + sweep + clear15", lambda e: e.get("held") and e.get("sr_bounce") and e.get("backed10") and e.get("ctrl_sweep") and e.get("clear15")),
        ("bounce + backed + ctrl + sweep + clear20", lambda e: e.get("held") and e.get("sr_bounce") and e.get("backed10") and e.get("ctrl_sweep") and e.get("clear20")),
        ("bounce + backed08 + ctrl + clear20 + di8", lambda e: e.get("held") and e.get("sr_bounce") and e.get("backed08") and e.get("control_with") and e.get("clear20") and e.get("di_ge8")),
        ("breakout + ctrl + clear20 + !extreme", lambda e: e.get("held") and e.get("sr_breakout") and e.get("control_with") and e.get("clear20")),
        ("breakout + ctrl + clear30 + strong_body", lambda e: e.get("held") and e.get("sr_breakout") and e.get("control_with") and e.get("clear30") and e.get("strong_body")),
        ("failrev + clear20 + ctrl", lambda e: e.get("held") and e.get("sr_failed_break_rev") and e.get("clear20") and e.get("control_with")),
        ("failrev + clear20 + di8 + adx22", lambda e: e.get("held") and e.get("sr_failed_break_rev") and e.get("clear20") and e.get("di_ge8") and e.get("adx_ge22")),
        ("vwap_reclaim + clear20 + ctrl + di8", lambda e: e.get("held") and e.get("vwap_reclaim") and e.get("clear20") and e.get("control_with") and e.get("di_ge8")),
        ("trend + ctrl + sweep + clear20", lambda e: e.get("held") and e.get("reg_trend") and e.get("ctrl_sweep") and e.get("clear20")),
        ("trend + ctrl + sweep + clear20 + di8", lambda e: e.get("held") and e.get("reg_trend") and e.get("ctrl_sweep") and e.get("clear20") and e.get("di_ge8")),
        ("trend + ctrl + clear20 + adx25 + after1030", lambda e: e.get("held") and e.get("reg_trend") and e.get("control_with") and e.get("clear20") and e.get("adx_ge25") and e.get("after1030")),
        ("hold|bounce + ctrl + clear20 + di8", lambda e: e.get("held") and e.get("control_with") and e.get("clear20") and e.get("di_ge8") and (e.get("reg_hold") or e.get("sr_bounce"))),
        ("hold|bounce + ctrl + clear20 + di12 + strong", lambda e: e.get("held") and e.get("control_with") and e.get("clear20") and e.get("di_ge12") and e.get("strong_body") and (e.get("reg_hold") or e.get("sr_bounce"))),
        ("hold|bounce + ctrl_sweep + clear20 + adx22", lambda e: e.get("held") and e.get("ctrl_sweep") and e.get("clear20") and e.get("adx_ge22") and (e.get("reg_hold") or e.get("sr_bounce"))),
        ("tierA + clear20 + di8 + strong", lambda e: e.get("tier_a") and e.get("clear20") and e.get("di_ge8") and e.get("strong_body")),
        ("tierA + clear20 + di12 + adx22", lambda e: e.get("tier_a") and e.get("clear20") and e.get("di_ge12") and e.get("adx_ge22")),
        ("tierAB + clear20 + ctrl + di8 + after1030", lambda e: e.get("tier_ab") and e.get("clear20") and e.get("control_with") and e.get("di_ge8") and e.get("after1030")),
        ("ind_strict3 + clear20 + ctrl", lambda e: e.get("held") and e.get("ind_strict3") and e.get("clear20") and e.get("control_with")),
        ("ind_strict3 + clear20 + ctrl + bounce|hold", lambda e: e.get("held") and e.get("ind_strict3") and e.get("clear20") and e.get("control_with") and (e.get("sr_bounce") or e.get("reg_hold"))),
        ("macd_di + clear20 + ctrl + not_extreme", lambda e: e.get("held") and e.get("macd_di") and e.get("clear20") and e.get("control_with")),
        ("open_slot + bounce + backed + ctrl + clear15", lambda e: e.get("held") and e.get("open_slot") and e.get("sr_bounce") and e.get("backed10") and e.get("control_with") and e.get("clear15")),
        ("pm_slot + hold + ctrl + clear20", lambda e: e.get("held") and e.get("pm_slot") and e.get("reg_hold") and e.get("control_with") and e.get("clear20")),
        ("liq_magnet + sweep + ctrl + clear20", lambda e: e.get("held") and e.get("liq_magnet") and e.get("ctrl_sweep") and e.get("clear20")),
        ("P1strict: bounce+backed08+ctrl+sweep+clear20+di8", lambda e: e.get("held") and e.get("sr_bounce") and e.get("backed08") and e.get("ctrl_sweep") and e.get("clear20") and e.get("di_ge8")),
        ("P3strict: (hold|bounce)+ctrl+clear20+di8+strong", lambda e: e.get("held") and e.get("control_with") and e.get("clear20") and e.get("di_ge8") and e.get("strong_body") and (e.get("reg_hold") or e.get("sr_bounce"))),
        ("P6strict: trend+ctrl+sweep+clear20+di8+adx22", lambda e: e.get("held") and e.get("reg_trend") and e.get("ctrl_sweep") and e.get("clear20") and e.get("di_ge8") and e.get("adx_ge22")),
        ("ULTRA: tierA+clear20+di12+adx22+strong+after1030", lambda e: e.get("tier_a") and e.get("clear20") and e.get("di_ge12") and e.get("adx_ge22") and e.get("strong_body") and e.get("after1030")),
        ("ULTRA2: hold+backed08+ctrl+sweep+clear20+di12+adx22", lambda e: e.get("held") and e.get("reg_hold") and e.get("backed08") and e.get("ctrl_sweep") and e.get("clear20") and e.get("di_ge12") and e.get("adx_ge22")),
    ]


def combo_search(pool, max_k=4, min_n=MIN_N_2M, metric="acc", target=TARGET, limit_atoms=None):
    """Bitmask-style combinatorial AND search over atomic flags."""
    atoms = limit_atoms or ATOMS
    # filter atoms that fire at least once
    live_atoms = []
    for a in atoms:
        if sum(1 for e in pool if e.get(a)) >= min_n:
            live_atoms.append(a)

    # precompute bool arrays
    n = len(pool)
    mats = {a: np.array([bool(e.get(a)) for e in pool], dtype=bool) for a in live_atoms}
    y = np.array([bool(e.get(metric)) for e in pool], dtype=bool)

    hits = []
    # always require held + not_extreme as base for precision
    base_need = [a for a in ("held", "not_extreme") if a in mats]
    free = [a for a in live_atoms if a not in base_need]

    # size 1..max_k free atoms on top of base
    for k in range(1, max_k + 1):
        # cap combinations: prefer atoms that include at least one CORE_HINT / structure atom
        for combo in itertools.combinations(free, k):
            if k >= 3 and not any(
                a in CORE_HINT
                or a.startswith("clear")
                or a.startswith("reg_")
                or a.startswith("sr_")
                or a.startswith("bounce")
                or a.startswith("break")
                or a.startswith("tier")
                for a in combo
            ):
                continue
            mask = np.ones(n, dtype=bool)
            for a in base_need:
                mask &= mats[a]
            for a in combo:
                mask &= mats[a]
            nn = int(mask.sum())
            if nn < min_n:
                continue
            pct = 100.0 * float(y[mask].sum()) / nn
            if pct + 1e-9 < target:
                continue
            label = " ∧ ".join(base_need + list(combo))
            hits.append({"label": label, "n": nn, "pct": round(pct, 2), "metric": metric, "atoms": base_need + list(combo)})
    hits.sort(key=lambda r: (-r["pct"], -r["n"]))
    return hits


def build_pool(raw):
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    day_lo = str(df.index.min().date())
    day_hi = str(df.index.max().date())
    events = scalp.collect_scalp_events(df, day_lo, day_hi)
    enrich_ma_layers(events, df)
    enrich_ind(events, df)
    setup.apply_setup_enrichment(events, df)
    enrich_sr_archetypes(events, df)
    score_path(events, df)
    score_timing(events, df)
    enrich_deep_atoms(events, df)
    pool = [e for e in events if in_session(e)]
    return df, pool


def eval_gate(pool, fn):
    return [e for e in pool if fn(e)]


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("SR ≥80% DEEP research (NOT live)", flush=True)

    raw_all = base.load_existing_1m()
    hi = raw_all.index.max()
    raw_6m = raw_all[raw_all.index >= hi - pd.Timedelta(days=200)]
    print(f"bars_6m={len(raw_6m)} {raw_6m.index.min().date()}→{raw_6m.index.max().date()}", flush=True)

    print("build 6m pool…", flush=True)
    df6, pool6 = build_pool(raw_6m)
    days6 = sorted({e["day"] for e in pool6})
    days_2m = set(days6[-45:]) if len(days6) > 45 else set(days6)
    pool2 = [e for e in pool6 if e["day"] in days_2m]
    print(f"pool6={len(pool6)} days={len(days6)} | pool2={len(pool2)}", flush=True)

    metrics = ["acc", "dom", "dom20", "one_dir", "path12_strict", "path12", "fav1st", "clean_run"]

    # --- hand gates ---
    hand_rows = []
    for name, fn in hand_gates():
        r2 = summarize(eval_gate(pool2, fn), name)
        r6 = summarize(eval_gate(pool6, fn), name)
        hand_rows.append({"name": name, "r2": r2, "r6": r6})
        print(
            f"  hand {name}: 2m n={r2['n']} best={r2['best_metric']}@{r2['best_pct']} | "
            f"6m n={r6['n']} best={r6['best_metric']}@{r6['best_pct']}",
            flush=True,
        )

    # --- combo search per metric on 2m, validate on 6m ---
    proven = []  # gates that clear ≥80 on both windows for some metric
    near = []  # ≥70 both, or ≥80 one window

    print("combo search…", flush=True)
    for metric in metrics:
        print(f"  metric={metric}", flush=True)
        hits2 = combo_search(pool2, max_k=4, min_n=MIN_N_2M, metric=metric, target=TARGET)
        print(f"    2m hits≥{TARGET}%: {len(hits2)}", flush=True)
        for h in hits2[:80]:
            atoms = h["atoms"]

            def fn(e, atoms=atoms):
                return all(e.get(a) for a in atoms)

            sub2 = eval_gate(pool2, fn)
            sub6 = eval_gate(pool6, fn)
            if len(sub6) < MIN_N_6M:
                # still keep as 2m-only candidate if n2 ok
                s2 = summarize(sub2, h["label"])
                near.append(
                    {
                        "label": h["label"],
                        "metric": metric,
                        "pct2": s2.get(metric),
                        "n2": s2["n"],
                        "pct6": None,
                        "n6": len(sub6),
                        "status": "2m_only_thin_6m",
                    }
                )
                continue
            s2 = summarize(sub2, h["label"])
            s6 = summarize(sub6, h["label"])
            p2, p6 = s2.get(metric), s6.get(metric)
            months, stab_pct, stab_ok = monthly_stability(sub6, metric)
            gap2 = summarize(one_per_gap(sub2, gap=15), h["label"] + " gap15")
            gap6 = summarize(one_per_gap(sub6, gap=15), h["label"] + " gap15")
            rec = {
                "label": h["label"],
                "metric": metric,
                "pct2": p2,
                "n2": s2["n"],
                "pct6": p6,
                "n6": s6["n"],
                "avg_mfe6": s6["avg_mfe"],
                "avg_mae6": s6["avg_mae"],
                "avg_edge6": s6["avg_edge"],
                "stab_pct": stab_pct,
                "stab_ok": stab_ok,
                "months": months,
                "gap2": {k: gap2.get(k) for k in (metric, "n", "avg_mfe", "avg_mae")},
                "gap6": {k: gap6.get(k) for k in (metric, "n", "avg_mfe", "avg_mae")},
                "full2": s2,
                "full6": s6,
            }
            if p2 is not None and p6 is not None and p2 >= TARGET and p6 >= TARGET:
                rec["status"] = "PROVEN_80_BOTH"
                proven.append(rec)
            elif p2 is not None and p6 is not None and min(p2, p6) >= 70:
                rec["status"] = "NEAR_70_BOTH"
                near.append(rec)
            elif p2 is not None and p2 >= TARGET:
                rec["status"] = "80_2m_only"
                near.append(rec)

    # also check hand gates for proven
    hand_fn = {name: fn for name, fn in hand_gates()}
    hand_proven = []
    for row in hand_rows:
        fn = hand_fn[row["name"]]
        for metric in metrics:
            p2 = row["r2"].get(metric)
            p6 = row["r6"].get(metric)
            n2, n6 = row["r2"]["n"], row["r6"]["n"]
            if (
                p2 is not None
                and p6 is not None
                and p2 >= TARGET
                and p6 >= TARGET
                and n2 >= MIN_N_2M
                and n6 >= MIN_N_6M
            ):
                months, stab_pct, stab_ok = monthly_stability(eval_gate(pool6, fn), metric)
                hand_proven.append(
                    {
                        "label": row["name"],
                        "metric": metric,
                        "pct2": p2,
                        "n2": n2,
                        "pct6": p6,
                        "n6": n6,
                        "avg_edge6": row["r6"].get("avg_edge"),
                        "stab_pct": stab_pct,
                        "stab_ok": stab_ok,
                        "r2": row["r2"],
                        "r6": row["r6"],
                        "status": "PROVEN_80_BOTH_HAND",
                    }
                )

    # dedupe proven by label+metric
    def dedupe(rows):
        seen = set()
        out = []
        for r in sorted(rows, key=lambda x: (-min(x.get("pct2") or 0, x.get("pct6") or 0), -(x.get("n6") or 0))):
            k = (r["label"], r["metric"])
            if k in seen:
                continue
            seen.add(k)
            out.append(r)
        return out

    proven = dedupe(proven + hand_proven)
    near = dedupe(near)

    # top hand table by best_pct on 6m
    hand_sorted = sorted(hand_rows, key=lambda r: (-(r["r6"]["best_pct"] or -1), -r["r6"]["n"]))

    lines = [
        "# NIFTY 1m — S/R Deep Search for ≥80% Accurate Entry",
        "",
        "> **RESEARCH ONLY — not wired to live Scalper.**",
        "",
        f"Window 6m: **{days6[0]} → {days6[-1]}** ({len(days6)} sessions) · "
        f"2m: last {len(days_2m)} sessions · horizon {HORIZON} bars · 09:30–14:30.",
        "",
        "## Accuracy definitions (entry path — no SL/T primary)",
        "",
        "| Metric | Definition |",
        "|---|---|",
        "| **Acc%** | MFE≥20 and MFE > MAE |",
        "| **Dom%** | MFE≥15 and MFE ≥ 1.5×MAE |",
        "| **Dom20%** | MFE≥20 and MFE ≥ 1.5×MAE |",
        "| **OneDir%** | MFE≥20 and MFE ≥ 2×MAE |",
        "| **Path12s%** | +12 favour before −8 adverse |",
        "| **Path12%** | +12 favour before −5 adverse |",
        "| **Fav1st%** | +8 favour before −5 adverse |",
        "| **Clean%** | MFE≥30 and MAE≤12 |",
        "",
        f"Proven bar: **≥{TARGET}% on BOTH 2m and 6m** · n2≥{MIN_N_2M} · n6≥{MIN_N_6M} · monthly stability noted.",
        "",
        f"## PROVEN ≥{TARGET}% on both windows",
        "",
    ]

    if not proven:
        lines += [
            "**None found** at ≥80% on both 2m and 6m with minimum sample sizes.",
            "",
            "Closest candidates are listed under NEAR / hand sweep below. "
            "Next deepen: tighter liquidity distance, multi-bar confirm, prior-day level tags, VIX regime splits.",
            "",
        ]
    else:
        lines += [
            "| Gate | Metric | 2m% | n2 | 6m% | n6 | stab% | edge6 | status |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
        for r in proven[:40]:
            lines.append(
                f"| `{r['label']}` | {r['metric']} | **{r['pct2']}** | {r['n2']} | "
                f"**{r['pct6']}** | {r['n6']} | {r.get('stab_pct')} | {r.get('avg_edge6') or (r.get('r6') or {}).get('avg_edge')} | {r['status']} |"
            )
        lines.append("")

    lines += [
        "## NEAR (≥70 both, or ≥80 on 2m only)",
        "",
        "| Gate | Metric | 2m% | n2 | 6m% | n6 | status |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for r in near[:50]:
        lines.append(
            f"| `{r['label']}` | {r['metric']} | {r.get('pct2')} | {r.get('n2')} | "
            f"{r.get('pct6')} | {r.get('n6')} | {r.get('status')} |"
        )

    lines += [
        "",
        "## Hand stacks — best metric on 6m (diagnostic)",
        "",
        "| Gate | n6 | best | Acc | Dom | Dom20 | OneDir | Path12s | Fav1st | Clean | avgMFE | avgMAE |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in hand_sorted[:35]:
        r = row["r6"]
        best = f"{r['best_metric']}@{r['best_pct']}"
        lines.append(
            f"| `{row['name']}` | {r['n']} | {best} | {r['acc']} | {r['dom']} | {r['dom20']} | "
            f"{r['one_dir']} | {r['path12_strict']} | {r['fav1st']} | {r['clean_run']} | "
            f"{r['avg_mfe']} | {r['avg_mae']} |"
        )

    # ceiling analysis: what % of HELD ever reach each metric
    held6 = [e for e in pool6 if e.get("held")]
    held2 = [e for e in pool2 if e.get("held")]
    lines += [
        "",
        "## Ceiling — raw HELD base rates (why 80% is hard)",
        "",
        "| Pool | n | Acc | Dom | Dom20 | OneDir | Path12s | Fav1st | Clean |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for tag, pool in (("2m HELD", held2), ("6m HELD", held6)):
        s = summarize(pool, tag)
        lines.append(
            f"| {tag} | {s['n']} | {s['acc']} | {s['dom']} | {s['dom20']} | {s['one_dir']} | "
            f"{s['path12_strict']} | {s['fav1st']} | {s['clean_run']} |"
        )

    # sample best near/proven trades
    sample_fn = None
    sample_label = None
    if proven:
        sample_label = proven[0]["label"]
        atoms = proven[0].get("atoms") or proven[0]["label"].split(" ∧ ")
        sample_fn = lambda e, atoms=atoms: all(e.get(a) for a in atoms if a in ATOMS or True)
        # safer: use label atoms if from combo
        if "atoms" in proven[0]:
            atoms = proven[0]["atoms"]
            sample_fn = lambda e, atoms=atoms: all(e.get(a) for a in atoms)
        else:
            # hand gate
            hg = dict(hand_gates())
            if sample_label in hg:
                sample_fn = hg[sample_label]

    if sample_fn is None and near:
        # pick best near by min(pct2,pct6)
        best_near = max(
            (r for r in near if r.get("pct2") and r.get("pct6")),
            key=lambda r: min(r["pct2"], r["pct6"]),
            default=None,
        )
        if best_near:
            sample_label = best_near["label"]
            atoms = [a.strip() for a in sample_label.split("∧")]
            sample_fn = lambda e, atoms=atoms: all(e.get(a.strip()) for a in atoms)

    if sample_fn is not None:
        hits = [e for e in pool2 if sample_fn(e) and e.get("acc")][:12]
        misses = [e for e in pool2 if sample_fn(e) and not e.get("acc")][:10]
        lines += [
            "",
            f"## Samples — `{sample_label}` (2m)",
            "",
            "### Hits (Acc)",
            "",
            "| Day | HM | Side | Regime | room_fav | MFE | MAE | Dom | Path12s |",
            "|---|---|---|---|---:|---:|---:|---|---|",
        ]
        for e in hits:
            lines.append(
                f"| {e['day']} | {e['hm']} | {e['decision']} | {e.get('regime')} | "
                f"{e.get('room_fav')} | {e['mfe']} | {e['mae']} | {e.get('dom')} | {e.get('path12_strict')} |"
            )
        lines += [
            "",
            "### Misses (!Acc) — learn",
            "",
            "| Day | HM | Side | Regime | into_ext | clear20 | MFE | MAE |",
            "|---|---|---|---|---|---|---:|---:|",
        ]
        for e in misses:
            lines.append(
                f"| {e['day']} | {e['hm']} | {e['decision']} | {e.get('regime')} | "
                f"{e.get('into_sess_extreme')} | {e.get('clear20')} | {e['mfe']} | {e['mae']} |"
            )

    lines += [
        "",
        f"Elapsed {time.time() - t0:.0f}s",
        "",
        "## Next research steps (still not live)",
        "",
        "1. If no ≥80 both-window gate: add **2-bar confirm** (next bar holds favour) as entry delay.",
        "2. Split by **VIX / range-day vs trend-day** — 80% may exist only in one regime.",
        "3. Require **liquidity pool distance** (equal-high/low magnet) tags.",
        "4. Walk-forward month-by-month promotion only when stab_ok.",
        "5. Wire to Scalper **only after** a PROVEN_80_BOTH gate is locked.",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    payload = {
        "proven": proven[:60],
        "near": near[:80],
        "hand": [
            {"name": r["name"], "r2": r["r2"], "r6": r["r6"]} for r in hand_sorted[:40]
        ],
        "days6": days6,
        "target": TARGET,
    }
    # json-safe: drop months heavy if needed
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    print(f"PROVEN≥80 both: {len(proven)} | NEAR: {len(near)}", flush=True)
    if proven:
        print("TOP PROVEN:", [(r["label"], r["metric"], r["pct2"], r["pct6"], r["n6"]) for r in proven[:8]], flush=True)
    else:
        # show best near
        bests = sorted(
            (r for r in near if r.get("pct2") and r.get("pct6")),
            key=lambda r: (-min(r["pct2"], r["pct6"]), -r.get("n6", 0)),
        )[:8]
        print("TOP NEAR:", [(r["label"], r["metric"], r["pct2"], r["pct6"], r["n6"]) for r in bests], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
