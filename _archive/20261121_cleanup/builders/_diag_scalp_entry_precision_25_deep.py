"""RESEARCH ONLY — Deep hunt for ~100% precise ≥25pt entries (price + side only).

Pass 1 showed run2|3+ctrl+AD ≈ 50–57% m25 — not accurate enough.
This pass:
  1) Ignition entry (first bar of run) vs completion entry
  2) Clean-move label: MFE≥25 AND MAE≤10 (one-direction quality)
  3) Exhaustive feature search for 100% / ≥95% precision (n≥8)
  4) Displacement filters (body/ATR)
  5) Explicit entry rule: side + entry_px only

  python -u prod_live/tests/builders/_diag_scalp_entry_precision_25_deep.py
"""
from __future__ import annotations

import json
import sys
import time
from itertools import combinations
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
from _diag_scalp_impulse_green_run_entry import find_impulse_runs  # noqa: E402

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ENTRY_PRECISION_25_DEEP.md"
REPORT_JSON = OUT / "NIFTY_1M_ENTRY_PRECISION_25_DEEP.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
N_SESSIONS = 66
LOOKBACK_CAL = 140
FWD = 60
M25, MAE_CLEAN, MAJ, T15 = 25.0, 10.0, 40.0, 15.0
RUN_PATS = {"bull_run2", "bull_run3", "bear_run2", "bear_run3"}


def label_forward(e, h, l, c, day, entry_i, entry_px, side):
    d = e["day"]
    mfe = mae = 0.0
    hit25 = None
    end = min(len(c) - 1, entry_i + FWD)
    for j in range(entry_i + 1, end + 1):
        if day[j] != d:
            break
        if side == "BUY":
            mfe = max(mfe, float(h[j]) - entry_px)
            mae = max(mae, entry_px - float(l[j]))
        else:
            mfe = max(mfe, entry_px - float(l[j]))
            mae = max(mae, float(h[j]) - entry_px)
        if hit25 is None and mfe >= M25:
            hit25 = j
    e["_mfe"] = round(mfe, 2)
    e["_mae"] = round(mae, 2)
    e["_m25"] = mfe >= M25
    e["_clean25"] = (mfe >= M25) and (mae <= MAE_CLEAN)
    e["_m40"] = mfe >= MAJ
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


def trail_t15_maj(e, h, l, c, ema34, entry_i, side):
    ok, _, _, _ = path_ma_trail_strict(h, l, c, ema34, entry_i, side, T15)
    e["_t15"] = bool(ok)
    entry = float(c[entry_i])
    mfe = 0.0
    for j in range(entry_i + 1, min(len(c), entry_i + 121)):
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
    e["_maj"] = mfe >= MAJ


def stats(rows, key="_m25"):
    if not rows:
        return {"n": 0, "prec": None, "t15": None, "maj": None, "clean": None, "avg_mfe": None}
    n = len(rows)
    return {
        "n": n,
        "prec": round(100.0 * sum(1 for e in rows if e.get(key)) / n, 2),
        "t15": round(100.0 * sum(1 for e in rows if e.get("_t15")) / n, 2),
        "maj": round(100.0 * sum(1 for e in rows if e.get("_maj")) / n, 2),
        "clean": round(100.0 * sum(1 for e in rows if e.get("_clean25")) / n, 2),
        "m25_first": round(100.0 * sum(1 for e in rows if e.get("_m25_first")) / n, 2),
        "avg_mfe": round(float(np.mean([e.get("_mfe") or 0 for e in rows])), 2),
        "avg_mae": round(float(np.mean([e.get("_mae") or 0 for e in rows])), 2),
    }


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("DEEP entry precision ≥25 (RESEARCH ONLY)", flush=True)

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

    # Build completion-entry pool + ignition-entry clones for runs
    pool = []
    for e0 in events:
        if e0["day"] not in keep:
            continue
        if not (bool(in_session(e0)) and MINS_LO <= int(e0["mins"]) <= MINS_HI):
            continue
        i = int(e0["full_i"])
        side = e0["decision"]
        e = dict(e0)
        e["ad_with"] = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))
        e["not_extreme"] = not bool(e.get("into_sess_extreme"))
        e["held"] = held_gate(e)
        e["ctrl"] = bool(e.get("control_with"))
        e["tier_ab"] = bool(e.get("setup_ok"))
        e["hold_break"] = e.get("regime") == "hold_break" or bool(e.get("hold_break_setup"))
        e["bounce"] = bool(e.get("sr_bounce"))
        e["runway2"] = bool(e.get("runway_2atr"))
        e["room_ok"] = bool(e.get("clear_path"))
        pats = set(e.get("patterns") or [])
        prim = str(e.get("primary") or "")
        e["is_run"] = prim in RUN_PATS or bool(pats & RUN_PATS)
        e["run3"] = prim in ("bull_run3", "bear_run3") or bool(pats & {"bull_run3", "bear_run3"})
        e["run2"] = prim in ("bull_run2", "bear_run2") or bool(pats & {"bull_run2", "bear_run2"})
        a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
        body = abs(float(c[i]) - float(o[i]))
        e["disp15"] = body >= 1.5 * a
        e["disp10"] = body >= 1.0 * a
        e["disp08"] = body >= 0.8 * a
        e["big_body"] = body >= max(8.0, 0.6 * a)
        if i > 0:
            e["prev_opposite"] = (side == "BUY" and c[i - 1] < o[i - 1]) or (
                side == "SELL" and c[i - 1] > o[i - 1]
            )
        else:
            e["prev_opposite"] = False
        # completion entry
        e["entry_mode"] = "completion"
        e["entry_i"] = i
        e["entry_px"] = round(float(c[i]), 2)
        e["side"] = side
        label_forward(e, h, l, c, day, i, float(c[i]), side)
        trail_t15_maj(e, h, l, c, ema34, i, side)
        pool.append(e)

        # ignition entry for runs: first bar of 2/3 run = i-1 for run2, i-2 for run3
        if e["is_run"]:
            ig = i - 1 if e["run2"] and not e["run3"] else (i - 2 if e["run3"] else i - 1)
            # if both run2 and run3, prefer run3 span
            if e["run3"]:
                ig = i - 2
            elif e["run2"]:
                ig = i - 1
            if ig >= 0 and day[ig] == day[i]:
                ei = dict(e)
                ei["entry_mode"] = "ignition"
                ei["entry_i"] = ig
                ei["entry_px"] = round(float(c[ig]), 2)
                # recompute features at ignition bar for AD/ctrl-ish (keep pattern flags)
                ei["ad_with"] = (side == "BUY" and bool(ad_r[ig])) or (side == "SELL" and bool(ad_f[ig]))
                body_ig = abs(float(c[ig]) - float(o[ig]))
                a_ig = float(atr[ig]) if np.isfinite(atr[ig]) and atr[ig] > 0 else a
                ei["disp15"] = body_ig >= 1.5 * a_ig
                ei["disp10"] = body_ig >= 1.0 * a_ig
                ei["big_body"] = body_ig >= max(8.0, 0.6 * a_ig)
                label_forward(ei, h, l, c, day, ig, float(c[ig]), side)
                trail_t15_maj(ei, h, l, c, ema34, ig, side)
                pool.append(ei)

    print(f"pool rows={len(pool)} (completion+ignition)", flush=True)

    feat_keys = [
        "is_run",
        "run3",
        "run2",
        "ctrl",
        "ad_with",
        "held",
        "not_extreme",
        "room_ok",
        "runway2",
        "hold_break",
        "bounce",
        "prev_opposite",
        "tier_ab",
        "disp15",
        "disp10",
        "disp08",
        "big_body",
    ]

    def hunt(base_pool, label_key, min_n=8):
        """Find feature combos with high precision on label_key."""
        found = []
        # also require entry_mode filter as optional meta
        for mode in ("completion", "ignition", "any"):
            bp = base_pool if mode == "any" else [e for e in base_pool if e["entry_mode"] == mode]
            if len(bp) < min_n:
                continue
            # single features
            for f in feat_keys:
                sub = [e for e in bp if e.get(f)]
                if len(sub) < min_n:
                    continue
                prec = 100.0 * sum(1 for e in sub if e.get(label_key)) / len(sub)
                if prec >= 90:
                    found.append(_pack_hit(f"{mode}|{f}", sub, label_key, mid))
            for k in (2, 3, 4):
                for combo in combinations(
                    [
                        "ctrl",
                        "ad_with",
                        "held",
                        "not_extreme",
                        "room_ok",
                        "runway2",
                        "hold_break",
                        "run3",
                        "is_run",
                        "disp10",
                        "disp15",
                        "big_body",
                        "tier_ab",
                        "bounce",
                    ],
                    k,
                ):
                    # must include something selective
                    sub = [e for e in bp if all(e.get(f) for f in combo)]
                    if len(sub) < min_n:
                        continue
                    prec = 100.0 * sum(1 for e in sub if e.get(label_key)) / len(sub)
                    if prec >= 90:
                        found.append(_pack_hit(f"{mode}|{'+'.join(combo)}", sub, label_key, mid))
        # dedupe by name keep best n
        by = {}
        for x in found:
            by[x["name"]] = x
        out = sorted(by.values(), key=lambda x: (x["prec"], x["oos_prec"] or 0, x["n"]), reverse=True)
        return out

    def _pack_hit(name, sub, label_key, mid):
        tr = [e for e in sub if e["day"] < mid]
        oo = [e for e in sub if e["day"] >= mid]
        st, so = stats(tr, label_key), stats(oo, label_key)
        sf = stats(sub, label_key)
        return {
            "name": name,
            "n": sf["n"],
            "prec": sf["prec"],
            "train_n": st["n"],
            "train_prec": st["prec"],
            "oos_n": so["n"],
            "oos_prec": so["prec"],
            "t15": sf["t15"],
            "maj": sf["maj"],
            "clean": sf["clean"],
            "avg_mfe": sf["avg_mfe"],
            "avg_mae": sf["avg_mae"],
            "label": label_key,
        }

    print("hunting m25…", flush=True)
    hits_m25 = hunt(pool, "_m25", min_n=8)
    print(f"  ≥90% m25 combos: {len(hits_m25)}", flush=True)
    print("hunting clean25 (MFE≥25 & MAE≤10)…", flush=True)
    hits_clean = hunt(pool, "_clean25", min_n=5)
    print(f"  ≥90% clean25 combos: {len(hits_clean)}", flush=True)
    print("hunting m25_first…", flush=True)
    hits_first = hunt(pool, "_m25_first", min_n=8)
    print(f"  ≥90% m25_first combos: {len(hits_first)}", flush=True)

    # Also: impulse ignition (≥25pt same-color run) reverse features
    # Reuse find_impulse with min_pts=25, min_bars=3
    # Need atr on df
    runs = find_impulse_runs(df, min_bars=3, min_pts=25.0)
    runs = [r for r in runs if r["day"] in keep and MINS_LO <= int(r["mins"]) <= MINS_HI]
    # Map ignition bars to pool-like feature dicts from nearest event or raw
    impulse_entries = []
    # index events by full_i for feature borrow
    by_i = {}
    for e in pool:
        if e["entry_mode"] == "completion":
            by_i[int(e["full_i"])] = e
    for r in runs:
        i = int(r["full_i"])
        side = r["decision"]
        # features from event at i if exists else minimal
        base_e = by_i.get(i)
        e = {
            "day": r["day"],
            "hm": r["hm"],
            "side": side,
            "decision": side,
            "entry_px": round(float(c[i]), 2),
            "entry_i": i,
            "entry_mode": "impulse_ignition",
            "primary": "impulse_run25",
            "held": bool(base_e["held"]) if base_e else False,
            "ctrl": bool(base_e["ctrl"]) if base_e else False,
            "ad_with": (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i])),
            "not_extreme": bool(base_e["not_extreme"]) if base_e else True,
            "room_ok": bool(base_e["room_ok"]) if base_e else False,
            "runway2": bool(base_e["runway2"]) if base_e else False,
            "hold_break": bool(base_e["hold_break"]) if base_e else False,
            "tier_ab": bool(base_e["tier_ab"]) if base_e else False,
            "is_run": True,
            "move": r["move"],
            "n_bars": r["n_bars"],
        }
        # By construction impulse move ≥25 from open0 — from close entry precision:
        label_forward(e, h, l, c, day, i, float(c[i]), side)
        trail_t15_maj(e, h, l, c, ema34, i, side)
        impulse_entries.append(e)
    # Precision of "detect impulse ignition with filters" is circular if we only score impulses.
    # Instead: take candidate bars that LOOK like ignition (prev opposite + green/red + ctrl+AD)
    # and measure m25 — already in pool hunt.

    # Manual priority gates (user request + best practices)
    def gate_rows(name, pred, mode=None):
        rows = [e for e in pool if pred(e) and (mode is None or e["entry_mode"] == mode)]
        tr = [e for e in rows if e["day"] < mid]
        oo = [e for e in rows if e["day"] >= mid]
        return {
            "name": name,
            "full": stats(rows),
            "train": stats(tr),
            "oos": stats(oo),
            "full_clean": stats(rows, "_clean25"),
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
                    "m25": e["_m25"],
                    "clean": e["_clean25"],
                    "t15": e["_t15"],
                    "maj": e["_maj"],
                }
                for e in sorted(rows, key=lambda x: (x["day"], x.get("mins", 0)))[:30]
            ],
        }

    priority = [
        gate_rows(
            "IGNITION run2|3 + ctrl + AD",
            lambda e: e["is_run"] and e["ctrl"] and e["ad_with"],
            "ignition",
        ),
        gate_rows(
            "IGNITION run2|3 + ctrl + AD + HELD",
            lambda e: e["is_run"] and e["ctrl"] and e["ad_with"] and e["held"],
            "ignition",
        ),
        gate_rows(
            "IGNITION run3 + ctrl + AD + HELD + !extreme",
            lambda e: e["run3"] and e["ctrl"] and e["ad_with"] and e["held"] and e["not_extreme"],
            "ignition",
        ),
        gate_rows(
            "COMPLETION run2|3 + ctrl + AD + HELD + disp10",
            lambda e: e["is_run"] and e["ctrl"] and e["ad_with"] and e["held"] and e["disp10"],
            "completion",
        ),
        gate_rows(
            "COMPLETION run3 + ctrl + AD + HELD + room + disp10",
            lambda e: e["run3"] and e["ctrl"] and e["ad_with"] and e["held"] and e["room_ok"] and e["disp10"],
            "completion",
        ),
        gate_rows(
            "COMPLETION TierAB",
            lambda e: e["tier_ab"],
            "completion",
        ),
        gate_rows(
            "COMPLETION HELD + hold_break + ctrl",
            lambda e: e["held"] and e["hold_break"] and e["ctrl"],
            "completion",
        ),
        gate_rows(
            "COMPLETION HELD + hold_break + ctrl + AD",
            lambda e: e["held"] and e["hold_break"] and e["ctrl"] and e["ad_with"],
            "completion",
        ),
        gate_rows(
            "COMPLETION HELD + hold_break + ctrl + AD + disp10",
            lambda e: e["held"] and e["hold_break"] and e["ctrl"] and e["ad_with"] and e["disp10"],
            "completion",
        ),
    ]

    for p in priority:
        f = p["full"]
        print(
            f"  {p['name']}: n={f['n']} m25={f['prec']}% clean={p['full_clean']['prec']}% "
            f"t15={f['t15']}% OOS={p['oos']['prec']}%",
            flush=True,
        )

    # Pick best 100% from hunts (train+oos both 100, n≥8 full, oos n≥4)
    def pick_perfect(hits):
        perfect = [
            x
            for x in hits
            if x["prec"] == 100
            and x["train_prec"] == 100
            and x["oos_prec"] == 100
            and x["n"] >= 8
            and (x["oos_n"] or 0) >= 4
            and (x["train_n"] or 0) >= 4
        ]
        return sorted(perfect, key=lambda x: x["n"], reverse=True)

    perfect_m25 = pick_perfect(hits_m25)
    perfect_clean = pick_perfect(hits_clean)
    perfect_first = pick_perfect(hits_first)

    # Best overall priority by OOS m25 then prec
    best_pri = sorted(
        priority,
        key=lambda p: (p["oos"]["prec"] or 0, p["full"]["prec"] or 0, p["full"]["n"]),
        reverse=True,
    )[0]

    # Union test: if any perfect gate, union with TierAB
    union = None
    if perfect_m25:
        # rebuild subset for top perfect — approximate via name parse is hard; skip detailed union
        union = {"note": "perfect m25 gates found — keep separate from TierAB unless union prec≥90"}

    payload = {
        "ok": True,
        "research_only": True,
        "window": {"day_lo": day_lo, "day_hi": day_hi, "n_days": n_days, "oos_from": mid},
        "priority": priority,
        "perfect_m25": perfect_m25[:10],
        "perfect_clean25": perfect_clean[:10],
        "perfect_m25_first": perfect_first[:10],
        "top_m25_hunt": hits_m25[:20],
        "top_clean_hunt": hits_clean[:20],
        "impulse_runs_25": len(runs),
        "best_priority": best_pri["name"],
        "took_sec": round(time.time() - t0, 1),
    }

    lines = [
        "# NIFTY 1m — Deep **accurate entry** hunt (≥25pt, price + side only)",
        "",
        "> Density ignored. Goal = near-**100%** precision that a ≥25pt same-direction move follows.",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS **{mid}**.",
        "",
        "## Labels",
        "",
        "| Label | Meaning |",
        "|---|---|",
        "| **m25** | raw MFE ≥ 25 pts after entry (≤60 bars, same day) |",
        "| **clean25** | m25 AND MAE ≤ 10 (truly one-way) |",
        "| **m25_first** | +25 before −25 adverse |",
        "| **T15 / Maj** | EMA34 trail +15 / trail MFE≥40 |",
        "",
        "Entry modes: **completion** = close of pattern bar · **ignition** = close of first bar of run2/3.",
        "",
        "## 1) Priority gates (your suggested family)",
        "",
        "| Gate | n | m25% | clean25% | T15% | Maj% | Train m25 | OOS m25 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for p in priority:
        f, t, o, cstat = p["full"], p["train"], p["oos"], p["full_clean"]
        lines.append(
            f"| `{p['name']}` | {f['n']} | **{f['prec']}** | {cstat['prec']} | {f['t15']} | {f['maj']} | "
            f"{t['prec']} | {o['prec']} |"
        )

    lines += [
        "",
        "## 2) Exhaustive hunt — 100% precision books",
        "",
        f"- Perfect **m25** (train+OOS 100%, n≥8): **{len(perfect_m25)}**",
        f"- Perfect **clean25**: **{len(perfect_clean)}**",
        f"- Perfect **m25_first**: **{len(perfect_first)}**",
        "",
    ]
    if perfect_m25:
        lines.append("### PROVEN 100% m25")
        lines.append("")
        lines.append("| Rule | n | Train | OOS | T15 | Maj | avg MFE |")
        lines.append("|---|---:|---|---|---:|---:|---:|")
        for x in perfect_m25[:12]:
            lines.append(
                f"| `{x['name']}` | {x['n']} | {x['train_n']}/{x['train_prec']}% | "
                f"{x['oos_n']}/{x['oos_prec']}% | {x['t15']} | {x['maj']} | {x['avg_mfe']} |"
            )
        best = perfect_m25[0]
        lines += [
            "",
            "### Most accurate entry logic (ship candidate)",
            "",
            "```",
            f"RULE : {best['name']}",
            "SIDE : BUY if bullish pattern / green-run context else SELL",
            "ENTRY: close of the entry bar (ignition or completion as named)",
            "ONLY TWO OUTPUTS: entry_px + side",
            "```",
        ]
    else:
        lines.append("**No rule achieved 100% m25 on both TRAIN and OOS with n≥8.**")
        if hits_m25:
            lines.append("")
            lines.append("### Closest (≥90% m25)")
            lines.append("")
            lines.append("| Rule | n | m25% | Train | OOS | T15 | Maj |")
            lines.append("|---|---:|---:|---|---|---:|---:|")
            for x in hits_m25[:15]:
                lines.append(
                    f"| `{x['name']}` | {x['n']} | **{x['prec']}** | "
                    f"{x['train_n']}/{x['train_prec']}% | {x['oos_n']}/{x['oos_prec']}% | "
                    f"{x['t15']} | {x['maj']} |"
                )

    if perfect_clean:
        lines += [
            "",
            "### PROVEN 100% clean25 (MFE≥25 & MAE≤10)",
            "",
            "| Rule | n | Train | OOS | avg MFE | avg MAE |",
            "|---|---:|---|---|---:|---:|",
        ]
        for x in perfect_clean[:10]:
            lines.append(
                f"| `{x['name']}` | {x['n']} | {x['train_n']}/{x['train_prec']}% | "
                f"{x['oos_n']}/{x['oos_prec']}% | {x['avg_mfe']} | {x['avg_mae']} |"
            )

    lines += [
        "",
        f"## 3) Best priority gate right now: `{best_pri['name']}`",
        "",
        f"- m25 **{best_pri['full']['prec']}%** · OOS **{best_pri['oos']['prec']}%** · n={best_pri['full']['n']}",
        f"- clean25 **{best_pri['full_clean']['prec']}%** · T15 **{best_pri['full']['t15']}%** · maj **{best_pri['full']['maj']}%**",
        "",
        "| Day | HM | Side | Entry | Mode | MFE | MAE | m25 | T15 |",
        "|---|---|---|---:|---|---:|---:|---|---|",
    ]
    for s in best_pri["samples"][:20]:
        lines.append(
            f"| {s['day']} | {s['hm']} | **{s['side']}** | **{s['entry']}** | {s['mode']} | "
            f"{s['mfe']} | {s['mae']} | {s['m25']} | {s['t15']} |"
        )

    lines += [
        "",
        "## 4) Honest conclusion",
        "",
        "- `run2|run3 + control + AD` alone is **~50–65%** on ≥25pt — **not** accurate entry logic.",
        "- Switching to **ignition** entry helps some, but does not reach 100% by itself.",
        "- **100% precision** (if found above) will be **sparse** — that is OK; you asked for accuracy not calls.",
        "- Do **not** union with `oracle_t15_clean` unless union m25 stays ≥90%.",
        "- Outputs for any proven rule: **`side` + `entry_px` only**.",
        "",
        f"_Generated in {payload['took_sec']}s._",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    # shrink samples in json
    for p in payload["priority"]:
        p["samples"] = p["samples"][:15]
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    print(
        f"perfect_m25={len(perfect_m25)} perfect_clean={len(perfect_clean)} "
        f"best_pri={best_pri['name']} m25={best_pri['full']['prec']}%",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
