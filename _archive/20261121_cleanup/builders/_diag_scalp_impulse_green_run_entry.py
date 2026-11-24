"""RESEARCH ONLY — identify entries that precede a straight 1m impulse run.

User example: ~13:12 then ~45 pts straight with only green 1m candles.
We formalize that as an IMPULSE RUN and reverse-engineer the entry bar.

Impulse run (BUY):
  ≥ min_bars consecutive green candles (close>open)
  AND (run_high - first_open) ≥ min_pts
  Entry candidate = first bar of the run (or bar just before ignition)

Same for SELL with red candles.

Goal: what was true AT entry (S/R, A/D, compress, DI, VWAP, regime)
so we can detect similar ignitions early.

  python -u prod_live/tests/builders/_diag_scalp_impulse_green_run_entry.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
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
from _diag_scalp_ma_lastyear_init import add_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators  # noqa: E402
from _diag_scalp_ad_sr_entry_1m import add_ad_obv_proxy  # noqa: E402

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_IMPULSE_RUN_ENTRY_LAST1M.md"
REPORT_JSON = OUT / "NIFTY_1M_IMPULSE_RUN_ENTRY_LAST1M.json"

MIN_BARS = 4
MIN_PTS = 40.0
LOOK_COMPRESS = 10


def find_impulse_runs(df: pd.DataFrame, min_bars=MIN_BARS, min_pts=MIN_PTS):
    """Return list of impulse dicts with entry at first bar of run."""
    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    idx = df.index
    day = np.array([str(ts.date()) for ts in idx])
    atr = df["atr14"].astype(float).values if "atr14" in df.columns else np.full(len(c), 8.0)
    out = []
    i = 0
    n = len(c)
    while i < n:
        # BUY impulse: green streak
        if c[i] > o[i]:
            j = i
            while j + 1 < n and day[j + 1] == day[i] and c[j + 1] > o[j + 1]:
                j += 1
            nb = j - i + 1
            move = float(np.max(h[i : j + 1]) - o[i])
            if nb >= min_bars and move >= min_pts:
                out.append(_pack(df, i, j, "BUY", move, nb, o, h, l, c, atr, idx, day))
            i = j + 1
            continue
        # SELL impulse: red streak
        if c[i] < o[i]:
            j = i
            while j + 1 < n and day[j + 1] == day[i] and c[j + 1] < o[j + 1]:
                j += 1
            nb = j - i + 1
            move = float(o[i] - np.min(l[i : j + 1]))
            if nb >= min_bars and move >= min_pts:
                out.append(_pack(df, i, j, "SELL", move, nb, o, h, l, c, atr, idx, day))
            i = j + 1
            continue
        i += 1
    return out


def _pack(df, i, j, side, move, nb, o, h, l, c, atr, idx, day):
    a = float(atr[i]) if np.isfinite(atr[i]) and atr[i] > 0 else 8.0
    # pre-context compress
    i0 = max(0, i - LOOK_COMPRESS)
    span = float(np.max(h[i0:i]) - np.min(l[i0:i])) if i > i0 else 0.0
    # prior bar color
    prev_green = bool(i > 0 and c[i - 1] > o[i - 1])
    prev_red = bool(i > 0 and c[i - 1] < o[i - 1])
    return {
        "full_i": i,
        "end_i": j,
        "day": day[i],
        "hm": idx[i].strftime("%H:%M"),
        "end_hm": idx[j].strftime("%H:%M"),
        "mins": int(idx[i].hour * 60 + idx[i].minute),
        "decision": side,
        "entry": round(float(c[i]), 2),  # enter on close of first impulse bar (realistic)
        "open0": round(float(o[i]), 2),
        "n_bars": nb,
        "move": round(move, 2),
        "close_move": round(float(c[j] - o[i]) if side == "BUY" else float(o[i] - c[j]), 2),
        "atr": round(a, 2),
        "pre10_span": round(span, 2),
        "compress_pre": span <= 1.5 * a,
        "prev_opposite": (side == "BUY" and prev_red) or (side == "SELL" and prev_green),
        "first_body": round(abs(float(c[i]) - float(o[i])), 2),
        "first_body_frac": round(abs(float(c[i]) - float(o[i])) / max(float(h[i]) - float(l[i]), 0.05), 2),
    }


def enrich_entry_context(runs, df):
    """Attach S/R + A/D + HELD-like flags at entry index."""
    # fake events for setup enrichers
    events = []
    for r in runs:
        events.append(
            {
                "full_i": r["full_i"],
                "day": r["day"],
                "hm": r["hm"],
                "mins": r["mins"],
                "decision": r["decision"],
                "entry": r["entry"],
                "primary": "impulse_run",
            }
        )
    # need indicator cols on events
    if "plus_di" in df.columns:
        pdi = df["plus_di"].astype(float).values
        mdi = df["minus_di"].astype(float).values
        vwap = df["vwap"].astype(float).values if "vwap" in df.columns else df["Close"].astype(float).values
        ema34 = df["ema34"].astype(float).values
        ad_r = df["ad_rising"].astype(bool).values if "ad_rising" in df.columns else np.zeros(len(df), dtype=bool)
        ad_f = df["ad_falling"].astype(bool).values if "ad_falling" in df.columns else np.zeros(len(df), dtype=bool)
        c = df["Close"].astype(float).values
        for e in events:
            i = int(e["full_i"])
            side = e["decision"]
            e["plus_di"] = round(float(pdi[i]), 2)
            e["minus_di"] = round(float(mdi[i]), 2)
            e["di_ok"] = (side == "BUY" and pdi[i] >= mdi[i]) or (side == "SELL" and mdi[i] >= pdi[i])
            e["di_spread"] = round(float(pdi[i] - mdi[i]), 1)
            above = c[i] >= ema34[i] if np.isfinite(ema34[i]) else True
            e["gate_hard34"] = (side == "BUY" and above) or (side == "SELL" and not above)
            vd = (c[i] - vwap[i]) / max(float(df["atr14"].iloc[i] if "atr14" in df.columns else 8), 0.1)
            e["vwap_with"] = (side == "BUY" and vd >= 0) or (side == "SELL" and vd <= 0)
            e["ad_with"] = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))

    from _diag_scalp_sr_highmove_proven import enrich_sr_archetypes

    setup.apply_setup_enrichment(events, df)
    enrich_sr_archetypes(events, df)
    by_i = {e["full_i"]: e for e in events}
    for r in runs:
        e = by_i[r["full_i"]]
        r["di_ok"] = bool(e.get("di_ok"))
        r["gate_hard34"] = bool(e.get("gate_hard34"))
        r["vwap_with"] = bool(e.get("vwap_with"))
        r["held"] = bool(e.get("di_ok") and e.get("gate_hard34") and e.get("vwap_with"))
        r["ad_with"] = bool(e.get("ad_with"))
        r["room_fav"] = e.get("room_fav")
        r["room_against"] = e.get("room_against")
        r["control_with"] = bool(e.get("control_with"))
        r["sweep_with"] = bool(e.get("sweep_with"))
        r["regime"] = e.get("regime")
        r["into_extreme"] = bool(e.get("into_sess_extreme"))
        r["sr_bounce"] = bool(e.get("sr_bounce"))
        r["clear_path"] = bool(e.get("clear_path"))
        r["backed"] = bool(e.get("backed"))
        r["runway_2atr"] = bool(e.get("runway_2atr"))
        r["sr_breakout"] = bool(e.get("sr_breakout"))


def pct(rows, key):
    if not rows:
        return None
    return round(100.0 * sum(1 for r in rows if r.get(key)) / len(rows), 1)


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("IMPULSE RUN entry reverse-engineer · RESEARCH ONLY", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=45)]
    print(f"bars={len(raw)} {raw.index.min().date()}→{raw.index.max().date()}", flush=True)

    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    df = add_ad_obv_proxy(df)

    days = sorted({str(ts.date()) for ts in df.index})
    keep = set(days[-22:]) if len(days) > 22 else set(days)
    df1 = df[[str(ts.date()) in keep for ts in df.index]]
    print(f"window {min(keep)}→{max(keep)} sessions={len(keep)}", flush=True)

    runs = find_impulse_runs(df1, MIN_BARS, MIN_PTS)
    print(f"impulse runs ≥{MIN_PTS}pts / ≥{MIN_BARS} bars: {len(runs)}", flush=True)
    enrich_entry_context(runs, df)  # use full df for pivots warmup

    buys = [r for r in runs if r["decision"] == "BUY"]
    sells = [r for r in runs if r["decision"] == "SELL"]
    near_1312 = [r for r in runs if 13 * 60 <= r["mins"] <= 13 * 60 + 20]

    # feature prevalence at ignition
    feats = [
        "held",
        "di_ok",
        "gate_hard34",
        "vwap_with",
        "ad_with",
        "compress_pre",
        "prev_opposite",
        "control_with",
        "sweep_with",
        "sr_bounce",
        "clear_path",
        "backed",
        "runway_2atr",
        "into_extreme",
    ]

    def feat_table(rows, title):
        lines = [f"### {title} (n={len(rows)})", "", "| Feature at entry bar | % true |", "|---|---:|"]
        for f in feats:
            lines.append(f"| `{f}` | {pct(rows, f)} |")
        reg = Counter(r.get("regime") or "?" for r in rows)
        lines += ["", "Regimes: " + ", ".join(f"{k}={v}" for k, v in reg.most_common()), ""]
        return lines

    # combo scores: among impulse entries, which combo is most common
    combos = [
        ("compress→impulse", lambda r: r.get("compress_pre") and r.get("control_with")),
        ("HELD+compress", lambda r: r.get("held") and r.get("compress_pre")),
        ("HELD+AD+compress", lambda r: r.get("held") and r.get("ad_with") and r.get("compress_pre")),
        ("AD+ctrl+clear", lambda r: r.get("ad_with") and r.get("control_with") and r.get("clear_path")),
        ("HELD+AD+ctrl", lambda r: r.get("held") and r.get("ad_with") and r.get("control_with")),
        ("prev_opposite+ctrl+AD", lambda r: r.get("prev_opposite") and r.get("control_with") and r.get("ad_with")),
        ("bounce+backed+AD", lambda r: r.get("sr_bounce") and r.get("backed") and r.get("ad_with")),
        ("clear+AD+ctrl+!extreme", lambda r: r.get("clear_path") and r.get("ad_with") and r.get("control_with") and not r.get("into_extreme")),
        ("HELD only", lambda r: r.get("held")),
        ("strong first body≥0.55", lambda r: (r.get("first_body_frac") or 0) >= 0.55),
    ]
    combo_rows = []
    for name, fn in combos:
        sub = [r for r in runs if fn(r)]
        combo_rows.append(
            {
                "name": name,
                "n": len(sub),
                "pct_of_impulses": round(100.0 * len(sub) / len(runs), 1) if runs else 0,
                "avg_move": round(float(np.mean([r["move"] for r in sub])), 1) if sub else None,
                "buy": sum(1 for r in sub if r["decision"] == "BUY"),
                "sell": sum(1 for r in sub if r["decision"] == "SELL"),
            }
        )
    combo_rows.sort(key=lambda x: (-x["n"], -(x["avg_move"] or 0)))

    lines = [
        "# NIFTY 1m — Impulse Run Entry (straight green/red streak)",
        "",
        "> **RESEARCH ONLY.** Pattern from your example: after entry, market runs ~40–45+ pts "
        "with consecutive same-color 1m candles.",
        "",
        f"Window **{min(keep)} → {max(keep)}** ({len(keep)} sessions).",
        "",
        "## Pattern definition (what we hunt)",
        "",
        "```",
        f"IMPULSE BUY : ≥{MIN_BARS} consecutive GREEN 1m bars AND (run_high − open0) ≥ {MIN_PTS:.0f} pts",
        f"IMPULSE SELL: ≥{MIN_BARS} consecutive RED   1m bars AND (open0 − run_low)  ≥ {MIN_PTS:.0f} pts",
        "Entry bar   : FIRST bar of that streak (ignition)",
        "```",
        "",
        f"Found **{len(runs)}** impulse runs · BUY={len(buys)} · SELL={len(sells)} · "
        f"near 13:00–13:20: **{len(near_1312)}**",
        "",
        "## Note on your “today 13:12” example",
        "",
        f"Local 1m cache ends **{hi.date()}**. On **2026-11-16 13:12** NIFTY did **not** print a "
        f"≥40pt all-green run (price drifted/chopped after). Closest recent midday impulses are listed below. "
        f"If your chart is **live today (newer than cache)**, refresh Kite 1m and re-run this script.",
        "",
        "## Impulses near 13:00–13:20 (like your example)",
        "",
        "| Day | Start | End | Side | bars | move | held | AD | compress | clear | regime |",
        "|---|---|---|---|---:|---:|---|---|---|---|---|",
    ]
    for r in sorted(near_1312, key=lambda x: (x["day"], x["hm"])):
        lines.append(
            f"| {r['day']} | {r['hm']} | {r['end_hm']} | {r['decision']} | {r['n_bars']} | "
            f"**{r['move']}** | {r.get('held')} | {r.get('ad_with')} | {r.get('compress_pre')} | "
            f"{r.get('clear_path')} | {r.get('regime')} |"
        )
    if not near_1312:
        lines.append("| — | — | — | — | — | — | — | — | — | — | — |")

    lines += [
        "",
        "## All impulse runs (sample last 25)",
        "",
        "| Day | HM | Side | bars | move | held | AD | compress | ctrl | clear | regime |",
        "|---|---|---|---:|---:|---|---|---|---|---|---|",
    ]
    for r in runs[-25:]:
        lines.append(
            f"| {r['day']} | {r['hm']} | {r['decision']} | {r['n_bars']} | {r['move']} | "
            f"{r.get('held')} | {r.get('ad_with')} | {r.get('compress_pre')} | {r.get('control_with')} | "
            f"{r.get('clear_path')} | {r.get('regime')} |"
        )

    lines += ["", "## What was true at the ignition bar?", ""]
    lines += feat_table(runs, "All impulse ignitions")
    lines += feat_table(buys, "BUY impulses only")
    lines += feat_table(sells, "SELL impulses only")
    if near_1312:
        lines += feat_table(near_1312, "Near 13:00–13:20 only")

    lines += [
        "## Which feature combos cover these impulses?",
        "",
        "| Combo at ignition | n | % of impulses | avg move | BUY | SELL |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for c in combo_rows:
        lines.append(
            f"| `{c['name']}` | {c['n']} | {c['pct_of_impulses']} | {c['avg_move']} | {c['buy']} | {c['sell']} |"
        )

    # proposed detector (analysis)
    best = combo_rows[0] if combo_rows else None
    lines += [
        "",
        "## How to identify this kind of entry (working hypothesis)",
        "",
        "Your example is an **impulse ignition**, not a slow grind:",
        "",
        "1. **Spot the start of a same-color streak** (first green of a green run / first red of a red run)",
        "2. Prefer ignition after **compression** (quiet 10 bars) → expansion",
        "3. Prefer **A/D with side** + **control bar** (close in favour third)",
        "4. Prefer **not into session extreme** and some **clear path**",
        "5. HELD (DI∧hard34∧VWAP) helps filter but does **not** alone equal impulse",
        "",
    ]
    if best:
        lines.append(
            f"Most common combo on this window: **`{best['name']}`** "
            f"({best['pct_of_impulses']}% of impulses, avg move {best['avg_move']} pts)."
        )
    lines += [
        "",
        "### Next (still research)",
        "",
        "1. Score a **live detector**: flag bar when first green/red + compress+AD+ctrl — "
        "then measure how often a ≥40pt streak follows (precision) and how many streaks are caught (recall).",
        "2. Re-run when **today’s** 1m bars are in cache so we can annotate your exact 13:12 example.",
        "3. Do **not** wire to Scalper until precision/recall both look strong.",
        "",
        f"Elapsed {time.time() - t0:.0f}s",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "runs": runs,
                "combos": combo_rows,
                "near_1312": near_1312,
                "window": [min(keep), max(keep)],
                "min_pts": MIN_PTS,
                "min_bars": MIN_BARS,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {REPORT}", flush=True)
    print(f"runs={len(runs)} near1312={len(near_1312)} top_combo={best['name'] if best else None}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
