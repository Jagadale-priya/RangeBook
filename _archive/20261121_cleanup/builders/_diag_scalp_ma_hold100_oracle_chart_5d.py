"""Chart ORACLE T12 vs HELD T12 on last 5 NIFTY 1m days.

ORACLE = first textbook event that day that path-wins under EMA34 trail · T1
(not a live gate — peeks outcome).

  python -u prod_live/tests/builders/_diag_scalp_ma_hold100_oracle_chart_5d.py
"""
from __future__ import annotations

import pickle
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
import research_nifty_1m_vix_candle_adaptive as vixmod  # noqa: E402
import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import enrich_prior3  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402
from _diag_scalp_ma_lastyear_init import WIN_LO, PACK, add_ma_layers, enrich_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402

OUT_DIR = ROOT / "prod_live" / "reports" / "1y" / "charts"
PNG = OUT_DIR / "NIFTY_1M_ORACLE_T12_LAST5D.png"
HTML = OUT_DIR / "NIFTY_1M_ORACLE_T12_LAST5D.html"
REPORT = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_1M_ORACLE_LOGIC_EXPLAIN.md"

T12, T15 = 12.0, 15.0
MAX_BARS = 120
N_DAYS = 5


def path_detail(h, l, c, ma, i, side, t1_pts, max_bars=MAX_BARS):
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    if side == "BUY":
        t1 = entry + t1_pts
        for j in range(i + 1, end + 1):
            hi, cl, m = float(h[j]), float(c[j]), float(ma[j])
            if not np.isfinite(m):
                return False, "bad", entry, i, 0.0
            if hi >= t1:
                return True, "t1", t1, j, float(t1_pts)
            if cl < m:
                return False, "ma_sl", cl, j, cl - entry
        px = float(c[end])
        return False, "exp", px, end, px - entry
    t1 = entry - t1_pts
    for j in range(i + 1, end + 1):
        lo, cl, m = float(l[j]), float(c[j]), float(ma[j])
        if not np.isfinite(m):
            return False, "bad", entry, i, 0.0
        if lo <= t1:
            return True, "t1", t1, j, float(t1_pts)
        if cl > m:
            return False, "ma_sl", cl, j, entry - cl
    px = float(c[end])
    return False, "exp", px, end, entry - px


def draw_candles(ax, day_df):
    o = day_df["Open"].astype(float).values
    h = day_df["High"].astype(float).values
    l = day_df["Low"].astype(float).values
    c = day_df["Close"].astype(float).values
    n = len(day_df)
    width = 0.6
    for i in range(n):
        up = c[i] >= o[i]
        color = "#1b7f4e" if up else "#c0392b"
        ax.vlines(i, l[i], h[i], color=color, linewidth=0.7, zorder=2)
        bottom = min(o[i], c[i])
        height = abs(c[i] - o[i]) or 0.15
        ax.add_patch(
            Rectangle((i - width / 2, bottom), width, height, facecolor=color, edgecolor=color, linewidth=0.4, zorder=3)
        )
    return n


def score_all(xs, h, l, c, ema34, idx, t1):
    for e in xs:
        i = int(e["full_i"])
        ok, reason, exit_px, j, pts = path_detail(h, l, c, ema34, i, e["decision"], t1)
        e["_win"] = bool(ok)
        e["_reason"] = reason
        e["_exit_px"] = float(exit_px)
        e["_exit_i"] = int(j)
        e["_pts"] = float(pts)
        e["_t1"] = float(t1)
        if 0 <= j < len(idx):
            e["_exit_hm"] = pd.Timestamp(idx[j]).tz_convert("Asia/Kolkata").strftime("%H:%M")
        else:
            e["_exit_hm"] = "?"


def pick_oracle(rows):
    for e in sorted(rows, key=lambda x: x["mins"]):
        if e.get("_win"):
            return e
    return None


def pick_held(rows):
    for e in sorted(rows, key=lambda x: x["mins"]):
        if held_gate(e):
            return e
    return None


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("ORACLE chart · last 5d", flush=True)

    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    all_days = sorted({str(ts.date()) for ts in raw.index})
    days5 = all_days[-N_DAYS:]
    day_lo, day_hi = days5[0], days5[-1]
    print(f"days={days5}", flush=True)

    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    idx = df.index
    vix = vixmod.load_vix()

    cache = next(PACK.glob("events_2025-11-17_*.pkl"))
    xs = [e for e in pickle.load(cache.open("rb")) if day_lo <= e["day"] <= day_hi]
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)
    enrich_ind(xs, df)

    # score T12 for chart + T15 for table compare
    score_all(xs, h, l, c, ema34, idx, T12)
    by = defaultdict(list)
    for e in xs:
        by[e["day"]].append(e)

    oracle12 = {d: pick_oracle(by[d]) for d in days5}
    held12 = {d: pick_held(by[d]) for d in days5}

    # also T15 oracle picks (re-score copy fields)
    score_all(xs, h, l, c, ema34, idx, T15)
    oracle15 = {d: pick_oracle(by[d]) for d in days5}
    # restore T12 detail on oracle12/held objects — re-score T12 again for chart markers
    score_all(xs, h, l, c, ema34, idx, T12)
    oracle12 = {d: pick_oracle(by[d]) for d in days5}
    held12 = {d: pick_held(by[d]) for d in days5}

    fig, axes = plt.subplots(N_DAYS, 1, figsize=(16, 3.3 * N_DAYS), sharex=False)
    if N_DAYS == 1:
        axes = [axes]
    fig.suptitle(
        f"NIFTY 1m · ORACLE T12 (gold) vs HELD T12 (blue) · EMA34 trail\n"
        f"{day_lo} → {day_hi}  ·  ORACLE = first path-win (hindsight, not live)",
        fontsize=12,
        fontweight="bold",
        y=0.995,
    )

    def loc(day_df, ts):
        try:
            ei = day_df.index.get_loc(ts)
            if isinstance(ei, slice):
                return ei.start
            if isinstance(ei, np.ndarray):
                return int(np.where(ei)[0][0])
            return int(ei)
        except KeyError:
            return None

    def mark(ax, day_df, e, marker, color, label, y_off):
        if e is None:
            return
        ei = loc(day_df, idx[int(e["full_i"])])
        xj = loc(day_df, idx[int(e["_exit_i"])])
        if ei is not None:
            ax.scatter([ei], [float(e["entry"])], marker=marker, s=140, color=color, zorder=7, label=label)
            ax.annotate(
                f"{label}\n{e['hm']} {e['decision']} {e['primary']}",
                (ei, float(e["entry"])),
                textcoords="offset points",
                xytext=(6, y_off),
                fontsize=6.5,
                color=color,
            )
        if xj is not None:
            ax.scatter([xj], [float(e["_exit_px"])], marker="X", s=80, color=color, zorder=7)
            if ei is not None:
                ax.plot(
                    [ei, xj],
                    [float(e["entry"]), float(e["_exit_px"])],
                    color=color,
                    ls="--",
                    lw=1.0,
                    alpha=0.75,
                    zorder=5,
                )

    for ax, d in zip(axes, days5):
        day_df = df[df["day"] == d].copy() if "day" in df.columns else df[df.index.strftime("%Y-%m-%d") == d].copy()
        day_df = day_df[(day_df.index.strftime("%H:%M") >= "09:15") & (day_df.index.strftime("%H:%M") <= "15:29")]
        n = draw_candles(ax, day_df)
        xs_i = np.arange(n)
        ax.plot(xs_i, day_df["ema34"].astype(float).values, color="#1f4e79", lw=1.2, label="EMA34", zorder=4)
        if "vwap" in day_df.columns:
            ax.plot(xs_i, day_df["vwap"].astype(float).values, color="#8e44ad", lw=1.0, alpha=0.8, label="VWAP", zorder=4)

        o12 = oracle12.get(d)
        h12 = held12.get(d)
        mark(ax, day_df, o12, "*", "#b7950b", "ORACLE T12", 12)
        # only mark HELD if different time from oracle
        if h12 is not None and (o12 is None or h12["mins"] != o12["mins"] or h12["decision"] != o12["decision"]):
            mark(ax, day_df, h12, "^" if h12["decision"] == "BUY" else "v", "#2471a3", "HELD T12", -28)
        elif h12 is not None and o12 is not None and h12["mins"] == o12["mins"]:
            ax.set_title(
                f"{d}  ORACLE=HELD same call  {o12['hm']} {o12['decision']} {o12['primary']} → {o12['_exit_hm']} +{o12['_pts']:.0f}",
                fontsize=8,
            )
        if o12 is not None and (h12 is None or h12["mins"] != o12["mins"]):
            same = "same as HELD" if (h12 and h12["mins"] == o12["mins"]) else "≠ HELD"
            ax.set_title(
                f"{d}  ORACLE {o12['hm']} {o12['decision']} {o12['primary']} → {o12['_exit_hm']} "
                f"`{o12['_reason']}` +{o12['_pts']:.0f}  ({same})"
                + (
                    f"  |  HELD {h12['hm']} {h12['decision']} → {h12['_exit_hm']} "
                    f"{'WIN' if h12['_win'] else 'LOSS'} {h12['_pts']:+.0f}"
                    if h12
                    else "  |  no HELD"
                ),
                fontsize=8,
            )

        hm = day_df.index.strftime("%H:%M").tolist()
        tick_idx = [i for i, t in enumerate(hm) if t.endswith(":00") or t.endswith(":30") or i == 0 or i == n - 1]
        ax.set_xticks(tick_idx[::2] if len(tick_idx) > 12 else tick_idx)
        ax.set_xticklabels([hm[i] for i in (tick_idx[::2] if len(tick_idx) > 12 else tick_idx)], fontsize=7)
        ax.set_xlim(-1, n)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="upper left", fontsize=7, framealpha=0.85)

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(PNG, dpi=140)
    plt.close(fig)
    print(f"Wrote {PNG}", flush=True)

    # explain md
    lines = [
        "# What is ORACLE T12 / T15?",
        "",
        "## Short answer",
        "",
        "**ORACLE is not a live entry system.** It answers: *“Did at least one textbook candle that day win under the exit rules?”* "
        "and picks the **first** such winning event (hindsight).",
        "",
        "| | ORACLE T12 | ORACLE T15 | HELD T12 (live-style) |",
        "|---|---|---|---|",
        "| **Entry filter** | none (any textbook pattern) | same | **DI_ok ∧ hard34 ∧ VWAP** |",
        "| **Which call** | first event that **will win** (peek) | same | first that passes gates (blind) |",
        "| **Exit** | EMA34 trail · **T1=12** | EMA34 trail · **T1=15** | EMA34 trail · **T1=12** |",
        "| **Live usable?** | **No** | **No** | Yes (research desk) |",
        "",
        "## Exit parameters (same for Oracle & HELD)",
        "",
        "| Parameter | Value | Meaning |",
        "|---|---|---|",
        "| Trail MA | **EMA34** | exit when **close** flips against side vs EMA34 |",
        "| Target T1 | **12** or **15** pts | BUY: high ≥ entry+T1 · SELL: low ≤ entry−T1 |",
        "| Win rule | T1 **before** MA flip | else loss (`ma_sl`) even if green |",
        "| Max hold | ~120 bars (~2h) | else expire = loss |",
        "| Side | from candle pattern | bull patterns → BUY, bear → SELL |",
        "",
        "## What you need to “run” Oracle (research only)",
        "",
        "1. NIFTY **1m OHLC** for the day (+ ~100 bars warm-up for EMA34)",
        "2. Textbook candle detector (same catalog as scalp research)",
        "3. Simulate every candidate forward with EMA34 trail + T1",
        "4. Pick **first winner** chronologically → that is the oracle call",
        "",
        "**No** DI / VWAP / hard34 parameters — those are only for **HELD**.",
        "",
        "## Why 100% every day?",
        "",
        "Because oracle **searches** until it finds a path that already worked. "
        "It proves the **exit geometry** can pay T1 that day — not that you know which entry live.",
        "",
        f"## Chart (last {N_DAYS} days)",
        "",
        f"- PNG: `{PNG.relative_to(ROOT).as_posix()}`",
        f"- Gold ★ = ORACLE T12 entry → exit",
        f"- Blue ▲/▼ = HELD T12 when different from oracle",
        "",
        "| Day | Oracle T12 | HELD T12 | Same? |",
        "|---|---|---|---|",
    ]
    # rebuild T15 labels for table
    score_all(xs, h, l, c, ema34, idx, T15)
    o15 = {d: pick_oracle(by[d]) for d in days5}
    score_all(xs, h, l, c, ema34, idx, T12)
    o12 = {d: pick_oracle(by[d]) for d in days5}
    h12 = {d: pick_held(by[d]) for d in days5}
    for d in days5:
        a, b = o12.get(d), h12.get(d)
        same = "YES" if (a and b and a["mins"] == b["mins"] and a["decision"] == b["decision"]) else "no"
        as_ = f"{a['hm']} {a['decision']} {a['primary']}" if a else "—"
        bs_ = f"{b['hm']} {b['decision']} {b['primary']} ({'W' if b and b['_win'] else 'L'})" if b else "—"
        lines.append(f"| {d} | {as_} | {bs_} | {same} |")

    lines += ["", "### Oracle T15 first-win (same days)", "", "| Day | Oracle T15 |", "|---|---|"]
    for d in days5:
        a = o15.get(d)
        lines.append(f"| {d} | {a['hm']} {a['decision']} {a['primary']}" if a else f"| {d} | — |")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    HTML.write_text(
        f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Oracle T12</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f7f7f5}}
img{{max-width:100%;border:1px solid #ddd}}code{{background:#eee;padding:1px 4px}}</style></head>
<body>
<h2>ORACLE T12 vs HELD · last 5d</h2>
<p><b>Oracle</b> = first textbook path-win (hindsight). <b>HELD</b> = DI+hard34+VWAP blind.<br>
Exit both: EMA34 trail · T1=12</p>
<img src="{PNG.name}" alt="chart"/>
<p>See <code>NIFTY_1M_ORACLE_LOGIC_EXPLAIN.md</code></p>
</body></html>""",
        encoding="utf-8",
    )
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
