"""RESEARCH ONLY — Open ZONE BOX on 5m + chart with 1m candles.

5m defines the zones (same idea as 1m OR boxes):
  OR15 clock = first 3 × 5m bars (09:15–09:30)
  OR30 clock = first 6 × 5m bars (09:15–09:45)
  UP zone   = OR high ± 0.5×ATR5
  DOWN zone = OR low  ± 0.5×ATR5

Chart (last 5 sessions): 1m candlesticks + 5m zone boxes shaded.
Also scores swing vs break on 5m-defined zones (1m path for retest).

  python -u prod_live/tests/builders/_diag_scalp_open_zone_box_5m_chart.py
"""
from __future__ import annotations

import json
import sys
import time
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
from _diag_scalp_ma_hold100_indicators import add_indicators  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
CHART_DIR = OUT / "charts"
PNG = CHART_DIR / "NIFTY_5M_ZONE_BOX_1M_CANDLES_LAST5D.png"
HTML = CHART_DIR / "NIFTY_5M_ZONE_BOX_1M_CANDLES_LAST5D.html"
REPORT = OUT / "NIFTY_5M_OPEN_ZONE_BOX.md"
REPORT_JSON = OUT / "NIFTY_5M_OPEN_ZONE_BOX.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
ZONE_HALF_ATR = 0.50
REACT_BARS = 12  # 1m bars
BREAK_ATR = 1.0
SWING_PTS = 15.0
N_DAYS_CHART = 5
# 5m OR in wall-clock: 15min=3 bars, 30min=6 bars
OR15_5M_BARS = 3
OR30_5M_BARS = 6


def atr_series(df, n=14):
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    c = df["Close"].astype(float)
    prev = c.shift(1)
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def resample_5m(df1):
    o = df1["Open"].resample("5min").first()
    h = df1["High"].resample("5min").max()
    l = df1["Low"].resample("5min").min()
    c = df1["Close"].resample("5min").last()
    out = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c}).dropna()
    out["day"] = [str(ts.date()) for ts in out.index]
    out["mins"] = out.index.hour * 60 + out.index.minute
    out["atr"] = atr_series(out)
    return out


def make_zone(edge, atr, side):
    half = max(4.0, ZONE_HALF_ATR * atr)
    return {
        "side": side,
        "lo": round(edge - half, 2),
        "hi": round(edge + half, 2),
        "mid": round(edge, 2),
        "edge": round(edge, 2),
    }


def build_5m_or_zones(df5, keep, n_bars, method):
    """One UP + one DOWN zone per day from first n_bars of 5m session."""
    zones = []
    by = defaultdict(list)
    for i, d in enumerate(df5["day"].astype(str).values):
        by[d].append(i)
    idx = df5.index
    h = df5["High"].astype(float).values
    l = df5["Low"].astype(float).values
    atr = df5["atr"].astype(float).values
    mins = df5["mins"].astype(int).values

    for d, ilist in by.items():
        if d not in keep:
            continue
        # session bars from regular open (~09:15)
        sess = [i for i in ilist if mins[i] >= 9 * 60 + 15]
        if len(sess) < n_bars:
            continue
        slc = sess[:n_bars]
        hi = float(np.max(h[slc]))
        lo = float(np.min(l[slc]))
        live_i5 = slc[-1]
        a = float(atr[live_i5]) if np.isfinite(atr[live_i5]) and atr[live_i5] > 0 else 10.0
        live_ts = idx[live_i5]
        # zone live after this 5m bar closes → first 1m bar after
        zones.append(
            {
                "day": d,
                "method": method,
                "live_ts": live_ts,
                "up": make_zone(hi, a, "UP"),
                "down": make_zone(lo, a, "DOWN"),
                "box_lo": round(lo, 2),
                "box_hi": round(hi, 2),
                "atr": round(a, 2),
            }
        )
    return zones


def map_live_to_1m(df1, live_ts):
    t1 = df1.index
    pos = int(t1.searchsorted(live_ts, side="right")) - 1
    return max(0, min(pos, len(t1) - 1))


def in_zone(lo, hi, bar_lo, bar_hi):
    return not (bar_hi < lo or bar_lo > hi)


def score_zones_on_1m(df1, zones, keep):
    h = df1["High"].astype(float).values
    l = df1["Low"].astype(float).values
    c = df1["Close"].astype(float).values
    atr = df1["atr14"].astype(float).values
    day = df1["day"].astype(str).values
    mins = (df1.index.hour * 60 + df1.index.minute).astype(int)
    events = []

    for z in zones:
        if z["day"] not in keep:
            continue
        live = map_live_to_1m(df1, z["live_ts"])
        for key in ("up", "down"):
            box = z[key]
            lo, hi, mid, side = box["lo"], box["hi"], box["mid"], box["side"]
            left = False
            touch_i = None
            for j in range(live + 1, len(c)):
                if day[j] != z["day"]:
                    break
                if mins[j] < MINS_LO or mins[j] >= MINS_HI:
                    continue
                a = float(atr[j]) if np.isfinite(atr[j]) and atr[j] > 0 else 10.0
                cl = float(c[j])
                if not left:
                    if side == "UP" and cl < lo - 0.3 * a:
                        left = True
                    elif side == "DOWN" and cl > hi + 0.3 * a:
                        left = True
                    elif abs(cl - mid) >= 0.8 * a and not in_zone(
                        lo, hi, float(l[j]), float(h[j])
                    ):
                        left = True
                    continue
                if in_zone(lo, hi, float(l[j]), float(h[j])):
                    touch_i = j
                    break
            if touch_i is None:
                events.append(
                    {
                        "method": z["method"],
                        "day": z["day"],
                        "side": side,
                        "outcome": "no_retest",
                        "swing": False,
                        "broke": False,
                    }
                )
                continue
            a = float(atr[touch_i]) if np.isfinite(atr[touch_i]) else 10.0
            end = min(len(c) - 1, touch_i + REACT_BARS)
            while end > touch_i and day[end] != z["day"]:
                end -= 1
            if side == "UP":
                broke = float(np.max(c[touch_i : end + 1])) >= hi + BREAK_ATR * a
                bounce = mid - float(np.min(l[touch_i : end + 1]))
                reclaim = any(float(c[k]) <= mid for k in range(touch_i, end + 1))
            else:
                broke = float(np.min(c[touch_i : end + 1])) <= lo - BREAK_ATR * a
                bounce = float(np.max(h[touch_i : end + 1])) - mid
                reclaim = any(float(c[k]) >= mid for k in range(touch_i, end + 1))
            swung = (not broke) and reclaim and bounce >= SWING_PTS
            outcome = "break" if broke else ("swing" if swung else "weak")
            events.append(
                {
                    "method": z["method"],
                    "day": z["day"],
                    "side": side,
                    "outcome": outcome,
                    "swing": swung,
                    "broke": broke,
                    "bounce": round(float(bounce), 2),
                    "decisive": swung or broke,
                    "touch_hm": str(df1.index[touch_i])[11:16],
                }
            )
    return events


def summarize(events, method):
    sub = [e for e in events if e["method"] == method and e["outcome"] != "no_retest"]
    n = len(sub)
    if n < 8:
        return {"method": method, "n": n, "swing_pct": None, "break_pct": None, "decisive_pct": None}
    sw = sum(1 for e in sub if e["swing"])
    br = sum(1 for e in sub if e["broke"])
    return {
        "method": method,
        "n": n,
        "swing_pct": round(100.0 * sw / n, 2),
        "break_pct": round(100.0 * br / n, 2),
        "decisive_pct": round(100.0 * sum(1 for e in sub if e["decisive"]) / n, 2),
        "avg_bounce": round(float(np.mean([e["bounce"] for e in sub if e["swing"]] or [0])), 2),
    }


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
        ax.vlines(i, l[i], h[i], color=color, linewidth=0.6, zorder=2)
        bottom = min(o[i], c[i])
        height = abs(c[i] - o[i]) or 0.15
        ax.add_patch(
            Rectangle(
                (i - width / 2, bottom),
                width,
                height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.3,
                zorder=3,
            )
        )
    return n


def draw_zone_band(ax, n, lo, hi, color, label, alpha=0.18):
    ax.axhspan(lo, hi, xmin=0, xmax=1, color=color, alpha=alpha, zorder=1, label=label)
    ax.axhline(lo, color=color, linewidth=0.8, alpha=0.7, linestyle="--", zorder=4)
    ax.axhline(hi, color=color, linewidth=0.8, alpha=0.7, linestyle="--", zorder=4)


def main() -> int:
    t0 = time.time()
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    print("5m ZONE BOX + 1m candle chart (NOT live)", flush=True)

    raw = base.load_existing_1m()
    hi_ts = raw.index.max()
    raw = raw[raw.index >= hi_ts - pd.Timedelta(days=55)]
    df1 = raw.copy()
    df1["day"] = [str(ts.date()) for ts in df1.index]
    df1 = add_indicators(df1)

    days_all = sorted(set(df1["day"].astype(str)))
    keep = set(days_all[-22:]) if len(days_all) > 22 else set(days_all)
    days_chart = days_all[-N_DAYS_CHART:]
    day_lo, day_hi = min(keep), max(keep)
    print(f"stats window {day_lo}→{day_hi} · chart days {days_chart[0]}→{days_chart[-1]}", flush=True)

    df5 = resample_5m(df1)
    z15 = build_5m_or_zones(df5, keep, OR15_5M_BARS, "5m_OR15")
    z30 = build_5m_or_zones(df5, keep, OR30_5M_BARS, "5m_OR30")
    zones_all = z15 + z30
    print(f"5m zones OR15={len(z15)} OR30={len(z30)}", flush=True)

    events = score_zones_on_1m(df1, zones_all, keep)
    sums = [summarize(events, m) for m in ("5m_OR15", "5m_OR30")]
    for s in sums:
        print(
            f"  {s['method']}: n={s['n']} swing={s['swing_pct']} break={s['break_pct']} "
            f"decisive={s['decisive_pct']}",
            flush=True,
        )

    # ---- chart: 1m candles + 5m OR30 zones (primary) ----
    z_by_day = {z["day"]: z for z in z30 if z["day"] in days_chart}
    # fallback OR15 if no OR30
    for z in z15:
        if z["day"] in days_chart and z["day"] not in z_by_day:
            z_by_day[z["day"]] = z

    fig, axes = plt.subplots(N_DAYS_CHART, 1, figsize=(16, 3.4 * N_DAYS_CHART), sharex=False)
    if N_DAYS_CHART == 1:
        axes = [axes]
    fig.suptitle(
        "NIFTY · 5m Opening ZONE BOX (UP/DOWN) · 1m candles\n"
        f"Zones from 5m OR30 (first 6×5m bars) · ±0.5×ATR · {days_chart[0]} → {days_chart[-1]}",
        fontsize=12,
        fontweight="bold",
        y=0.995,
    )

    for ax, d in zip(axes, days_chart):
        day_df = df1[df1["day"] == d].copy()
        day_df = day_df[
            (day_df.index.strftime("%H:%M") >= "09:15")
            & (day_df.index.strftime("%H:%M") <= "15:29")
        ]
        if day_df.empty:
            ax.set_title(f"{d} (no bars)")
            continue
        n = draw_candles(ax, day_df)
        hm = day_df.index.strftime("%H:%M").tolist()

        z = z_by_day.get(d)
        title_extra = "no 5m zone"
        if z:
            up, dn = z["up"], z["down"]
            draw_zone_band(ax, n, up["lo"], up["hi"], "#c0392b", f"UP zone {up['edge']:.0f}", 0.20)
            draw_zone_band(ax, n, dn["lo"], dn["hi"], "#1b7f4e", f"DOWN zone {dn['edge']:.0f}", 0.20)
            # OR box mid lines
            ax.axhline(z["box_hi"], color="#922b21", linewidth=1.1, alpha=0.9, label=f"OR high {z['box_hi']}")
            ax.axhline(z["box_lo"], color="#0b6e4f", linewidth=1.1, alpha=0.9, label=f"OR low {z['box_lo']}")
            # mark live time
            try:
                live_ts = z["live_ts"]
                # find first 1m >= live
                pos = day_df.index.searchsorted(live_ts, side="left")
                if 0 <= pos < n:
                    ax.axvline(pos, color="#2c3e50", linewidth=1.0, linestyle=":", alpha=0.8, label="zone live")
            except Exception:
                pass
            title_extra = (
                f"5m {z['method']}  UP[{up['lo']}-{up['hi']}]  DOWN[{dn['lo']}-{dn['hi']}]  "
                f"box {z['box_lo']}-{z['box_hi']}"
            )

        # grey outside research session
        for i, t in enumerate(hm):
            if t < "09:30" or t >= "14:30":
                ax.axvspan(i - 0.5, i + 0.5, color="#bdc3c7", alpha=0.2, zorder=0)

        # mark retest events for this day (OR30)
        day_ev = [
            e
            for e in events
            if e["day"] == d and e["method"] == "5m_OR30" and e["outcome"] != "no_retest"
        ]
        for e in day_ev:
            # find touch index in day_df by hm match approx — use bounce annotate at mid
            pass

        ax.set_title(f"{d}  ·  {title_extra}", fontsize=9)
        tick_idx, tick_lbl = [], []
        for i, t in enumerate(hm):
            if t.endswith(":00") or t.endswith(":30") or i == 0 or i == n - 1:
                tick_idx.append(i)
                tick_lbl.append(t)
        ax.set_xticks(tick_idx[::2] if len(tick_idx) > 12 else tick_idx)
        ax.set_xticklabels(
            [tick_lbl[j] for j in range(0, len(tick_lbl), 2)] if len(tick_idx) > 12 else tick_lbl,
            fontsize=7,
        )
        ax.set_xlim(-1, n)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="upper left", fontsize=7, framealpha=0.85, ncol=2)

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(PNG, dpi=140)
    plt.close(fig)
    print(f"Wrote {PNG}", flush=True)

    # report
    lines = [
        "# NIFTY — Opening ZONE BOX on **5m** · chart with **1m candles**",
        "",
        "> **RESEARCH ONLY.**",
        "",
        f"Stats window **{day_lo} → {day_hi}** · Chart **{days_chart[0]} → {days_chart[-1]}**.",
        "",
        "## 5m zone definition (same idea as 1m OR)",
        "",
        "```",
        "5m_OR15 = high/low of first 3 × 5m bars  (~09:15–09:30)",
        "5m_OR30 = high/low of first 6 × 5m bars  (~09:15–09:45)",
        "UP zone   = OR high ± 0.5×ATR(5m)",
        "DOWN zone = OR low  ± 0.5×ATR(5m)",
        "Retest scored on 1m path after leave (swing ≥15pts vs break ≥1×ATR)",
        "```",
        "",
        "## 5m zone proven (swing vs break)",
        "",
        "| Method | Retests | Swing% | Break% | Decisive% | Avg swing bounce |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for s in sums:
        lines.append(
            f"| `{s['method']}` | {s['n']} | **{s['swing_pct']}** | {s['break_pct']} | "
            f"{s['decisive_pct']} | {s.get('avg_bounce')} |"
        )

    lines += [
        "",
        "## Chart",
        "",
        f"![5m zones + 1m candles](charts/{PNG.name})",
        "",
        "Red band = UP zone · Green band = DOWN zone · Horizontal lines = OR high/low · "
        "Candles = **1m**.",
        "",
        f"Elapsed {time.time() - t0:.0f}s",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    HTML.write_text(
        f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>5m Zone Box + 1m candles</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f7f7f5;color:#1a1a1a}}
img{{max-width:100%;border:1px solid #ddd;background:#fff}}
code{{background:#eee;padding:1px 4px}}
</style></head><body>
<h2>NIFTY — 5m Opening Zone Box · 1m candles</h2>
<p>UP/DOWN zones from <code>5m OR30</code> (first 6 five-minute bars), width ±0.5×ATR.<br>
Candlesticks are <b>1 minute</b>.</p>
<p><img src="{PNG.name}" alt="chart"/></p>
<p>Report: <code>{REPORT.name}</code></p>
</body></html>
""",
        encoding="utf-8",
    )

    REPORT_JSON.write_text(
        json.dumps(
            {
                "window": [day_lo, day_hi],
                "chart_days": days_chart,
                "summaries": sums,
                "png": str(PNG),
                "zones_chart": [
                    {
                        "day": z["day"],
                        "method": z["method"],
                        "up": z["up"],
                        "down": z["down"],
                        "box_lo": z["box_lo"],
                        "box_hi": z["box_hi"],
                    }
                    for z in z30
                    if z["day"] in days_chart
                ],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
