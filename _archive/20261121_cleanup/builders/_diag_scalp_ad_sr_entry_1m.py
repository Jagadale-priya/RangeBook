"""RESEARCH ONLY — last ~1 month: identify accurate BUY/SELL entries that catch
one-way moves (20/30/40+ pts) using Support/Resistance + Accumulation/Distribution.

Sources distilled (analysis, not live wiring):
  • Wyckoff: Spring / Upthrust / LPS / SOS-retest (StockCharts, TradingWyckoff)
  • A/D Line confirm + divergence (TradingSim / Skyrexio)
  • Acceptance breakout vs wick fake (Pillinger Works)
  • Break → retest → confirm (ChartsView / Tarrow)

Index volume often 0 on NIFTY CSV → A/D uses Money-Flow Multiplier × range proxy.

Accuracy (entry path only — no SL/T primary):
  Fav1st  +8 before −5
  Dom     MFE≥15 & ≥1.5×MAE
  OneDir  MFE≥20 & ≥2×MAE
  MFE20/30/40 rates

  python -u prod_live/tests/builders/_diag_scalp_ad_sr_entry_1m.py
"""
from __future__ import annotations

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
    score_path,
)
from _diag_scalp_sr_80pct_deep import score_timing  # noqa: E402

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_AD_SR_ENTRY_LAST1M.md"
REPORT_JSON = OUT / "NIFTY_1M_AD_SR_ENTRY_LAST1M.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30


def add_ad_obv_proxy(df: pd.DataFrame) -> pd.DataFrame:
    """Chaikin A/D + OBV with volume proxy when Volume is 0."""
    df = df.copy()
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    c = df["Close"].astype(float)
    o = df["Open"].astype(float)
    vol = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(0.0, index=df.index)
    rng = (h - l).replace(0, np.nan)
    # Money Flow Multiplier
    mfm = ((c - l) - (h - c)) / rng
    mfm = mfm.fillna(0.0)
    # proxy volume: real vol if present else bar range (pts) × 100
    vproxy = vol.where(vol > 0, (h - l).clip(lower=0.05) * 100.0)
    mfv = mfm * vproxy
    df["ad_line"] = mfv.cumsum()
    df["ad_slope5"] = df["ad_line"].diff(5)
    df["ad_slope10"] = df["ad_line"].diff(10)
    df["ad_rising"] = df["ad_slope5"] > 0
    df["ad_falling"] = df["ad_slope5"] < 0
    # OBV proxy
    direction = np.sign(c.diff().fillna(0.0))
    df["obv_line"] = (direction * vproxy).cumsum()
    df["obv_slope5"] = df["obv_line"].diff(5)
    df["obv_rising"] = df["obv_slope5"] > 0
    df["obv_falling"] = df["obv_slope5"] < 0
    # close location pressure
    df["clv"] = mfm  # −1..+1
    return df


def enrich_ad_structure(events, df):
    """Wyckoff-ish + A/D flags on each textbook event."""
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    ad_r = df["ad_rising"].astype(bool).values
    ad_f = df["ad_falling"].astype(bool).values
    ob_r = df["obv_rising"].astype(bool).values
    ob_f = df["obv_falling"].astype(bool).values
    ad_s5 = df["ad_slope5"].astype(float).values
    day = np.array([str(ts.date()) for ts in df.index])

    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        entry = float(e["entry"])
        a = float(e.get("atr") or 8.0)
        support = e.get("sr_support")
        resist = e.get("sr_resist")
        prev = max(0, i - 1)
        look = max(0, i - 20)

        e["ad_rising"] = bool(ad_r[i]) if i < len(ad_r) else False
        e["ad_falling"] = bool(ad_f[i]) if i < len(ad_f) else False
        e["obv_rising"] = bool(ob_r[i]) if i < len(ob_r) else False
        e["obv_falling"] = bool(ob_f[i]) if i < len(ob_f) else False
        e["ad_with"] = (side == "BUY" and e["ad_rising"]) or (side == "SELL" and e["ad_falling"])
        e["obv_with"] = (side == "BUY" and e["obv_rising"]) or (side == "SELL" and e["obv_falling"])
        e["ad_obv_with"] = e["ad_with"] and e["obv_with"]
        e["ad_slope5"] = round(float(ad_s5[i]), 2) if np.isfinite(ad_s5[i]) else 0.0

        # local range (20 bars) for spring/upthrust
        loc_hi = float(np.max(h[look : i + 1]))
        loc_lo = float(np.min(l[look : i + 1]))
        e["loc_hi"] = round(loc_hi, 2)
        e["loc_lo"] = round(loc_lo, 2)

        # SPRING: prior bar (or this) wicked below support/loc_lo, close back inside, BUY
        swept_lo = float(l[i]) < loc_lo + 0.15 * a and float(c[i]) > loc_lo + 0.2 * a
        if support is not None:
            swept_lo = swept_lo or (
                float(l[i]) < float(support) - 0.05 * a and float(c[i]) > float(support)
            )
        e["spring"] = bool(side == "BUY" and swept_lo and e.get("control_with"))

        # UPTHRUST: wick above resist/loc_hi, close back inside, SELL
        swept_hi = float(h[i]) > loc_hi - 0.15 * a and float(c[i]) < loc_hi - 0.2 * a
        if resist is not None:
            swept_hi = swept_hi or (
                float(h[i]) > float(resist) + 0.05 * a and float(c[i]) < float(resist)
            )
        e["upthrust"] = bool(side == "SELL" and swept_hi and e.get("control_with"))

        # ACCEPTANCE BREAKOUT: close beyond opposing S/R with control (not wick-only)
        e["accept_break"] = bool(e.get("sr_breakout") and e.get("control_with") and e.get("close_ext"))

        # BREAK+RETEST proxy: near recently broken level (room_against small after break)
        # backed + mom_with + clear ahead
        e["retest_cont"] = bool(
            e.get("backed")
            and e.get("mom_with")
            and e.get("clear_path")
            and e.get("control_with")
            and not e.get("into_sess_extreme")
        )

        # LPS / bounce at S/R with A/D
        e["lps_bounce_ad"] = bool(
            e.get("sr_bounce") and e.get("backed") and e.get("control_with") and e["ad_with"]
        )

        # Structure shift: pre10 mom flips then control with side
        e["choch_proxy"] = bool(
            e.get("mom_against") and e.get("control_with") and e.get("sweep_with") and e["ad_with"]
        )

        # Strong A/D impulse with clear path
        e["ad_impulse"] = bool(
            e["ad_obv_with"] and e.get("control_with") and e.get("clear_path") and e.get("strong_body", False)
        )
        # strong_body may be missing — compute
        body = abs(float(c[i]) - float(o[i]))
        br = max(float(h[i]) - float(l[i]), 0.05)
        e["strong_body"] = body / br >= 0.55
        e["ad_impulse"] = bool(
            e["ad_obv_with"] and e.get("control_with") and e.get("clear_path") and e["strong_body"]
        )

        # Divergence: price high but A/D not (bearish) / price low A/D rising (bullish)
        # simple: last 10 bars price extreme vs ad slope
        if side == "SELL":
            e["ad_div"] = bool(float(c[i]) >= float(np.max(c[look:i+1])) - 0.3 * a and e["ad_falling"])
        else:
            e["ad_div"] = bool(float(c[i]) <= float(np.min(c[look:i+1])) + 0.3 * a and e["ad_rising"])


def enrich_strong_body(events, df):
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    for e in events:
        i = int(e["full_i"])
        body = abs(float(c[i]) - float(o[i]))
        br = max(float(h[i]) - float(l[i]), 0.05)
        e["strong_body"] = body / br >= 0.55
        e["close_ext"] = (
            (e["decision"] == "BUY" and float(e.get("close_loc") or 0) >= 0.75)
            or (e["decision"] == "SELL" and float(e.get("close_loc") or 1) <= 0.25)
        )


def summarize(rows, label):
    n = len(rows)
    keys = ("fav1st", "dom", "one_dir", "clean_run", "mfe20", "mfe30", "mfe40", "acc", "path12_strict")
    out = {"label": label, "n": n}
    if not n:
        for k in keys:
            out[k] = None
        out["avg_mfe"] = out["avg_mae"] = out["avg_edge"] = None
        out["score"] = -1
        return out

    def pct(k):
        return round(100.0 * sum(1 for e in rows if e.get(k)) / n, 2)

    for k in keys:
        out[k] = pct(k)
    out["avg_mfe"] = round(float(np.mean([e["mfe"] for e in rows])), 2)
    out["avg_mae"] = round(float(np.mean([e["mae"] for e in rows])), 2)
    out["avg_edge"] = round(float(np.mean([e["edge"] for e in rows])), 2)
    # rank: Dom + OneDir + MFE30, soft n floor
    out["score"] = round(
        0.35 * out["dom"] + 0.35 * out["one_dir"] + 0.2 * out["mfe30"] + 0.1 * out["fav1st"]
        - max(0, 15 - n) * 0.8,
        2,
    )
    return out


def one_per_gap(rows, gap=15):
    by = defaultdict(list)
    for e in rows:
        by[e["day"]].append(e)
    out = []
    for d in sorted(by):
        next_ok = None
        for e in sorted(by[d], key=lambda x: x["mins"]):
            if next_ok is not None and e["mins"] < next_ok:
                continue
            out.append(e)
            next_ok = int(e["mins"]) + gap
    return out


GATES = [
    ("ALL textbook sess", lambda e: True),
    ("HELD", lambda e: held_gate(e)),
    ("HELD+AD_with", lambda e: held_gate(e) and e.get("ad_with")),
    ("HELD+AD+OBV_with", lambda e: held_gate(e) and e.get("ad_obv_with")),
    ("HELD+AD+clear15", lambda e: held_gate(e) and e.get("ad_with") and e.get("clear_path")),
    ("HELD+AD+OBV+clear15+ctrl", lambda e: held_gate(e) and e.get("ad_obv_with") and e.get("clear_path") and e.get("control_with")),
    ("SPRING+AD (BUY fail-break reclaim)", lambda e: e.get("spring") and e.get("ad_with")),
    ("SPRING+AD+HELD", lambda e: held_gate(e) and e.get("spring") and e.get("ad_with")),
    ("UPTHRUST+AD (SELL fail-break reject)", lambda e: e.get("upthrust") and e.get("ad_with")),
    ("UPTHRUST+AD+HELD", lambda e: held_gate(e) and e.get("upthrust") and e.get("ad_with")),
    ("SPRING|UPTHRUST + AD+HELD", lambda e: held_gate(e) and e.get("ad_with") and (e.get("spring") or e.get("upthrust"))),
    ("ACCEPT_BREAK+AD", lambda e: e.get("accept_break") and e.get("ad_with")),
    ("ACCEPT_BREAK+AD+HELD+!extreme", lambda e: held_gate(e) and e.get("accept_break") and e.get("ad_with") and not e.get("into_sess_extreme")),
    ("RETEST_CONT+AD", lambda e: e.get("retest_cont") and e.get("ad_with")),
    ("RETEST_CONT+AD+OBV+HELD", lambda e: held_gate(e) and e.get("retest_cont") and e.get("ad_obv_with")),
    ("LPS_BOUNCE+AD", lambda e: e.get("lps_bounce_ad")),
    ("LPS_BOUNCE+AD+HELD+clear15", lambda e: held_gate(e) and e.get("lps_bounce_ad") and e.get("clear_path")),
    ("CHOCH_proxy+AD+clear15", lambda e: e.get("choch_proxy") and e.get("clear_path")),
    ("CHOCH+AD+HELD", lambda e: held_gate(e) and e.get("choch_proxy")),
    ("AD_IMPULSE (A/D+OBV+ctrl+clear)", lambda e: e.get("ad_impulse")),
    ("AD_IMPULSE+HELD", lambda e: held_gate(e) and e.get("ad_impulse")),
    ("AD_DIV+ctrl+clear15", lambda e: e.get("ad_div") and e.get("control_with") and e.get("clear_path")),
    ("AD_DIV+HELD+ctrl", lambda e: held_gate(e) and e.get("ad_div") and e.get("control_with")),
    ("bounce+backed+ctrl+sweep+AD", lambda e: e.get("sr_bounce") and e.get("backed") and e.get("control_with") and e.get("sweep_with") and e.get("ad_with")),
    ("bounce+backed+ctrl+sweep+AD+HELD+clear", lambda e: held_gate(e) and e.get("sr_bounce") and e.get("backed") and e.get("control_with") and e.get("sweep_with") and e.get("ad_with") and e.get("clear_path")),
    ("hold_break+AD+clear15", lambda e: held_gate(e) and e.get("regime") == "hold_break" and e.get("ad_with") and e.get("clear_path")),
    ("TierAB+AD+clear15", lambda e: e.get("setup_ok") and e.get("ad_with") and e.get("clear_path")),
]


def move_atlas(pool):
    """Where one-way moves actually start (among HELD)."""
    held = [e for e in pool if held_gate(e)]
    one = [e for e in held if e.get("one_dir")]
    m40 = [e for e in held if e.get("mfe40")]
    by_reg = defaultdict(list)
    for e in one:
        by_reg[e.get("regime") or "mixed"].append(e)
    reg_stats = []
    for r, xs in sorted(by_reg.items(), key=lambda kv: -len(kv[1])):
        reg_stats.append(
            {
                "regime": r,
                "n": len(xs),
                "pct_ad": round(100.0 * sum(1 for e in xs if e.get("ad_with")) / len(xs), 1),
                "pct_spring_or_ut": round(
                    100.0 * sum(1 for e in xs if e.get("spring") or e.get("upthrust")) / len(xs), 1
                ),
                "pct_bounce": round(100.0 * sum(1 for e in xs if e.get("sr_bounce")) / len(xs), 1),
                "pct_clear": round(100.0 * sum(1 for e in xs if e.get("clear_path")) / len(xs), 1),
            }
        )
    return {
        "held_n": len(held),
        "one_dir_n": len(one),
        "one_dir_pct": round(100.0 * len(one) / len(held), 2) if held else None,
        "mfe40_n": len(m40),
        "regimes": reg_stats,
    }


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("AD+S/R entry research · last 1m · RESEARCH ONLY", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    lo = hi - pd.Timedelta(days=40)  # ~1 trading month + warmup
    raw = raw[raw.index >= lo]
    print(f"bars={len(raw)} {raw.index.min().date()}→{raw.index.max().date()}", flush=True)

    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    df = add_ad_obv_proxy(df)

    day_lo = str(df.index.min().date())
    day_hi = str(df.index.max().date())
    # last ~22 sessions
    all_days = sorted({str(ts.date()) for ts in df.index})
    keep = set(all_days[-22:]) if len(all_days) > 22 else set(all_days)
    print(f"test sessions={len(keep)} {min(keep)}→{max(keep)}", flush=True)

    events = scalp.collect_scalp_events(df, day_lo, day_hi)
    enrich_ma_layers(events, df)
    enrich_ind(events, df)
    setup.apply_setup_enrichment(events, df)
    enrich_sr_archetypes(events, df)
    enrich_strong_body(events, df)
    enrich_ad_structure(events, df)
    score_path(events, df)
    score_timing(events, df)

    pool = [e for e in events if in_session(e) and e["day"] in keep]
    # ensure acc flag
    for e in pool:
        e["acc"] = bool(e.get("mfe", 0) >= 20 and e.get("mfe", 0) > e.get("mae", 0))
        e["dom"] = bool(e.get("mfe", 0) >= 15 and e.get("mfe", 0) >= 1.5 * max(e.get("mae", 0), 1.0))

    print(f"pool={len(pool)}", flush=True)
    atlas = move_atlas(pool)

    rows = []
    for name, fn in GATES:
        sub = [e for e in pool if fn(e)]
        s = summarize(sub, name)
        g = summarize(one_per_gap(sub, 15), name + " gap15")
        rows.append({"name": name, "raw": s, "gap15": g})
        print(
            f"  {name}: n={s['n']} Dom={s['dom']} OneDir={s['one_dir']} MFE30={s['mfe30']} Fav={s['fav1st']} score={s['score']}",
            flush=True,
        )

    rows.sort(key=lambda r: (-(r["raw"]["score"] or -1), -(r["raw"]["one_dir"] or -1)))

    # samples from best gate with n>=12
    best = next((r for r in rows if r["raw"]["n"] >= 12 and "ALL" not in r["name"]), rows[0])
    best_fn = dict(GATES)[best["name"]]
    hits = [e for e in pool if best_fn(e) and e.get("one_dir")][:12]
    misses = [e for e in pool if best_fn(e) and not e.get("mfe20")][:10]

    lines = [
        "# NIFTY 1m — A/D + S/R Entry Hunt (last ~1 month)",
        "",
        "> **RESEARCH ONLY — not wired to Scalper / live.**",
        "",
        f"Sessions **{min(keep)} → {max(keep)}** ({len(keep)} days) · horizon {HORIZON} bars · 09:30–14:30.",
        "",
        "## How we identify a “move” (entry accuracy)",
        "",
        "After a candidate BUY/SELL bar we measure the next ~90 minutes:",
        "",
        "| Metric | Meaning |",
        "|---|---|",
        "| **MFE20/30/40** | Favourable excursion ≥ 20 / 30 / 40 pts |",
        "| **OneDir** | MFE≥20 and MFE ≥ 2×MAE (one-way dominance) |",
        "| **Dom** | MFE≥15 and MFE ≥ 1.5×MAE |",
        "| **Fav1st** | +8 pts favour before −5 adverse |",
        "",
        "## Theory stack (from public Wyckoff / A/D / breakout docs)",
        "",
        "1. **Spring** — sweep below support, close back inside → BUY (accumulation reclaim)",
        "2. **Upthrust** — sweep above resistance, close back inside → SELL (distribution reject)",
        "3. **Acceptance break** — close beyond S/R with control (not wick-only)",
        "4. **Retest continuation** — backed by broken level, momentum + clear path",
        "5. **LPS bounce + A/D** — bounce at S/R with A/D / OBV with side",
        "6. **A/D impulse** — A/D∧OBV with side + strong body + clear path",
        "",
        "A/D on NIFTY uses **Money Flow Multiplier × range proxy** (index volume often 0).",
        "",
        "## Move atlas (among HELD in window)",
        "",
        f"- HELD events: **{atlas['held_n']}**",
        f"- OneDir among HELD: **{atlas['one_dir_n']}** ({atlas['one_dir_pct']}%)",
        f"- MFE≥40 among HELD: **{atlas['mfe40_n']}**",
        "",
        "| Regime (OneDir HELD) | n | %AD_with | %Spring/UT | %bounce | %clear |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in atlas["regimes"][:8]:
        lines.append(
            f"| {r['regime']} | {r['n']} | {r['pct_ad']} | {r['pct_spring_or_ut']} | "
            f"{r['pct_bounce']} | {r['pct_clear']} |"
        )

    lines += [
        "",
        "## Gate sweep (rank by score · Dom/OneDir/MFE30)",
        "",
        "| Gate | n | Dom% | OneDir% | Fav1st% | MFE20 | MFE30 | MFE40 | avgMFE | avgMAE | edge | score |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        s = r["raw"]
        if s["n"] == 0:
            lines.append(f"| `{r['name']}` | 0 | — | — | — | — | — | — | — | — | — | — |")
            continue
        lines.append(
            f"| `{r['name']}` | {s['n']} | **{s['dom']}** | **{s['one_dir']}** | {s['fav1st']} | "
            f"{s['mfe20']} | {s['mfe30']} | {s['mfe40']} | {s['avg_mfe']} | {s['avg_mae']} | "
            f"{s['avg_edge']} | {s['score']} |"
        )

    lines += [
        "",
        "## Gap-15 books (top gates n≥10)",
        "",
        "| Gate | n | Dom% | OneDir% | MFE30 | edge |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        g = r["gap15"]
        if g["n"] < 10:
            continue
        lines.append(
            f"| `{r['name']}` | {g['n']} | {g['dom']} | {g['one_dir']} | {g['mfe30']} | {g['avg_edge']} |"
        )

    lines += [
        "",
        f"## Samples — best gate `{best['name']}`",
        "",
        "### OneDir hits",
        "",
        "| Day | HM | Side | Pattern | AD | Spring/UT | room | MFE | MAE |",
        "|---|---|---|---|---|---|---:|---:|---:|",
    ]
    for e in hits:
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e.get('primary')} | "
            f"{e.get('ad_with')} | {bool(e.get('spring') or e.get('upthrust'))} | "
            f"{e.get('room_fav')} | {e['mfe']} | {e['mae']} |"
        )
    lines += [
        "",
        "### Misses (MFE<20)",
        "",
        "| Day | HM | Side | into_ext | clear | MFE | MAE |",
        "|---|---|---|---|---|---:|---:|",
    ]
    for e in misses:
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e.get('into_sess_extreme')} | "
            f"{e.get('clear_path')} | {e['mfe']} | {e['mae']} |"
        )

    top3 = [r for r in rows if r["raw"]["n"] >= 10][:5]
    lines += [
        "",
        "## Analysis takeaways (entry only)",
        "",
    ]
    if top3:
        for i, r in enumerate(top3, 1):
            s = r["raw"]
            lines.append(
                f"{i}. **`{r['name']}`** — Dom **{s['dom']}%** · OneDir **{s['one_dir']}%** · "
                f"MFE30 {s['mfe30']}% · n={s['n']} · edge={s['avg_edge']}"
            )
    lines += [
        "",
        "### What “accurate entry” means here",
        "",
        "We are **not** scoring EMA34-trail hit% in this study. Goal is: after the signal bar, "
        "does price run 20–40+ pts in the same direction with limited adverse?",
        "",
        "### Next deepen (still research)",
        "",
        "1. Require **2-bar acceptance** after Spring/UT / break (close holds beyond level).",
        "2. Add **5m structure bias** filter before 1m trigger.",
        "3. Split range-day vs trend-day (ATR% / ADX).",
        "4. Re-test same gates on BANKNIFTY last 1m.",
        "5. Only then consider Scalper wiring — **not now**.",
        "",
        f"Elapsed {time.time() - t0:.0f}s",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps({"atlas": atlas, "gates": rows, "best": best["name"], "days": sorted(keep)}, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"wrote {REPORT}", flush=True)
    print("TOP:", [(r["name"], r["raw"]["one_dir"], r["raw"]["dom"], r["raw"]["n"]) for r in rows[:6]], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
