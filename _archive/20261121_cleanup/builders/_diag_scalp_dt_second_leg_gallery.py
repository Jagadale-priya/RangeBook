"""Render real DT second-leg candle galleries as PNG images.

  python -u prod_live/tests/builders/_diag_scalp_dt_second_leg_gallery.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(BUILDERS), str(ROOT / "tools" / "research")]
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
from _diag_scalp_pa_bos_choch_fvg import _norm_1m  # noqa: E402
from _diag_scalp_dt_ma_retest_prove import (  # noqa: E402
    atr14,
    build_signals,
    detect_double_tops,
)

OUT_DIR = ROOT / "prod_live" / "reports" / "1y" / "dt_h2_nobreak_gallery"


def draw_candles(ax, o, h, l, c, start: int, end: int):
    for i, j in enumerate(range(start, end)):
        up = c[j] >= o[j]
        color = "#1f7a4c" if up else "#b42318"
        ax.plot([i, i], [l[j], h[j]], color=color, lw=0.9, solid_capstyle="round")
        body_lo = min(o[j], c[j])
        body_hi = max(o[j], c[j])
        ax.add_patch(
            mpatches.Rectangle(
                (i - 0.35, body_lo),
                0.7,
                max(body_hi - body_lo, 0.05),
                facecolor=color,
                edgecolor=color,
                lw=0.4,
            )
        )


def annotate(ax, x, y, text, color="#111"):
    ax.annotate(
        text,
        xy=(x, y),
        xytext=(0, 12 if "H" in text or "2nd" in text or "entry" in text else -14),
        textcoords="offset points",
        ha="center",
        fontsize=8,
        color=color,
        fontweight="bold",
        arrowprops=dict(arrowstyle="-", color=color, lw=0.6),
    )


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=120)]
    df = _norm_1m(raw)
    # prefer recent sessions for gallery
    days = sorted({str(ts.date()) for ts in df.index})
    keep = set(days[-40:])
    df = df[[str(ts.date()) in keep for ts in df.index]].copy()

    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    idx = df.index
    atr = atr14(h, l, c)
    ema = df["Close"].astype(float).ewm(span=20, adjust=False).mean().to_numpy(dtype=float)

    dts = detect_double_tops(h, l, atr, 0.80)
    sigs = build_signals(df, ema, atr, dts, 20, 1.0)
    # prefer retest examples; also show pure leg2
    examples = []
    # rebuild DT map for annotation
    dt_by_key = {}
    for dt in dts:
        dt_by_key[(round(dt["p1"], 1), round(dt["p2"], 1), round(dt["neck"], 1))] = dt

    for setup_name in ("leg2_retest", "leg2"):
        for r in sigs[setup_name]:
            key = (round(r["p1"], 1), round(r["p2"], 1), round(r["neck"], 1))
            dt = dt_by_key.get(key)
            if not dt:
                continue
            examples.append({**r, "dt": dt, "setup_name": setup_name})

    # unique by day, latest first
    seen = set()
    picked = []
    for e in sorted(examples, key=lambda x: x["i_entry"], reverse=True):
        d = e["day"]
        if d in seen:
            continue
        seen.add(d)
        picked.append(e)
        if len(picked) >= 8:
            break

    print(f"gallery examples: {len(picked)}", flush=True)
    paths = []
    for n, e in enumerate(picked, 1):
        dt = e["dt"]
        i1, i2, vi = int(dt["i1"]), int(dt["i2"]), int(dt["valley_i"])
        i_sig, i_entry = int(e["i_sig"]), int(e["i_entry"])
        start = max(0, i1 - 8)
        end = min(len(c), i_entry + 25)
        width = end - start

        fig, ax = plt.subplots(figsize=(12, 4.8), dpi=140)
        draw_candles(ax, o, h, l, c, start, end)

        # EMA overlay in window
        xs = list(range(width))
        ax.plot(xs, ema[start:end], color="#2563eb", lw=1.2, alpha=0.9, label="EMA20")

        # neckline
        ax.axhline(e["neck"], color="#6b7280", ls="--", lw=0.9, alpha=0.8)

        def x_of(i):
            return i - start

        annotate(ax, x_of(i1), h[i1], "H1", "#111")
        annotate(ax, x_of(vi), l[vi], "1st down / neck", "#6b7280")
        annotate(ax, x_of(i2), h[i2], "H2", "#111")
        annotate(ax, x_of(i_sig), l[i_sig] if e["setup_name"] == "leg2" else c[i_sig], "2nd leg / signal", "#b42318")
        annotate(ax, x_of(i_entry), e["entry"], f"ENTRY {e['setup_name']}", "#b42318")

        # shade first vs second move
        ax.axvspan(x_of(i1), x_of(vi), color="#f3f4f6", alpha=0.35, zorder=0)
        ax.axvspan(x_of(i2), x_of(i_sig), color="#fee2e2", alpha=0.35, zorder=0)

        t0 = idx[start].strftime("%Y-%m-%d %H:%M")
        t1 = idx[end - 1].strftime("%H:%M")
        ax.set_title(
            f"Ex {n} · {e['day']} · {e['setup_name']} · H1={dt['p1']} H2={dt['p2']} neck={dt['neck']}\n"
            f"{t0} → {t1} · grey=1st down · red tint=2nd down zone · blue=EMA20",
            fontsize=10,
        )
        ax.set_xlim(-1, width)
        ax.set_ylabel("NIFTY")
        ax.grid(True, alpha=0.2)
        ax.legend(loc="upper right", fontsize=8)
        fig.tight_layout()
        out = OUT_DIR / f"ex{n:02d}_{e['day']}_{e['setup_name']}.png"
        fig.savefig(out, bbox_inches="tight")
        plt.close(fig)
        paths.append(out)
        print(f"wrote {out}", flush=True)

    # also one schematic strip
    fig, ax = plt.subplots(figsize=(10, 3.2), dpi=140)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.set_title("STRICT setup: H2 must NOT break H1, then down", fontsize=12, pad=8)
    steps = [
        (1.2, 3.8, "H1 (top)"),
        (3.0, 1.6, "1st down\n(neck)"),
        (5.0, 3.3, "H2 ≤ H1\n(no break)"),
        (7.0, 1.3, "DOWN only\n(2nd leg)"),
        (8.8, 2.0, "entry"),
    ]
    xs = [s[0] for s in steps]
    ys = [s[1] for s in steps]
    ax.plot(xs, ys, color="#b42318", lw=2)
    for x, y, lab in steps:
        ax.scatter([x], [y], s=60, color="#111", zorder=3)
        ax.text(x, y + 0.45, lab, ha="center", fontsize=9, fontweight="bold")
    ax.text(5, 0.35, "If H2 breaks above H1 → NO SETUP. After H2 must go down; else cancel.", ha="center", fontsize=9)
    schema = OUT_DIR / "00_setup_map.png"
    fig.savefig(schema, bbox_inches="tight")
    plt.close(fig)
    paths.insert(0, schema)
    print(f"gallery dir: {OUT_DIR}", flush=True)
    print("PATHS")
    for p in paths:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
