"""Plot HELD MA-trail logic on last 5 NIFTY 1m trading days (candlestick chart).

Entry: textbook pattern + DI_ok + gate_hard34 + vwap_with
       session window 09:30–14:30 · 1/day first
Exit : EMA34 trail · T1=12

Writes PNG + small HTML companion under reports/1y/charts/

  python -u prod_live/tests/builders/_diag_scalp_ma_hold100_chart_5d.py
"""
from __future__ import annotations

import pickle
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.dates as mdates
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
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import enrich_prior3  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402
from _diag_scalp_ma_lastyear_init import PACK, WIN_LO, add_ma_layers, enrich_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402

OUT_DIR = ROOT / "prod_live" / "reports" / "1y" / "charts"
PNG = OUT_DIR / "NIFTY_1M_HELD_MA_TRAIL_LAST5D.png"
HTML = OUT_DIR / "NIFTY_1M_HELD_MA_TRAIL_LAST5D.html"
REPORT = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_1M_HELD_MA_TRAIL_LAST5D_CHART.md"

T1 = 12.0
MAX_BARS = 120
MINS_LO = 9 * 60 + 30
MINS_HI = 14 * 60 + 30
N_DAYS = 5


def in_session(e) -> bool:
    return MINS_LO <= int(e["mins"]) < MINS_HI


def held_session(e) -> bool:
    return in_session(e) and held_gate(e)


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
    """Simple OHLC candles on integer x for readability."""
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
            Rectangle(
                (i - width / 2, bottom),
                width,
                height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.4,
                zorder=3,
            )
        )
    return n


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("HELD chart · last 5 trading days", flush=True)

    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    data_hi = str(raw.index.max().date())

    # last N trading days present in data
    all_days = sorted({str(ts.date()) for ts in raw.index})
    days5 = all_days[-N_DAYS:]
    day_lo, day_hi = days5[0], days5[-1]
    print(f"days={days5}", flush=True)

    # full research window so cached event full_i indices align
    work = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")].copy()

    df = tb.detect_textbook(work)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    vwap = df["vwap"].astype(float).values if "vwap" in df.columns else None
    idx = df.index
    vix = vixmod.load_vix()

    # events: try cache slice else collect
    xs = []
    try:
        cache = next(PACK.glob("events_2025-11-17_*.pkl"))
        xs = [e for e in pickle.load(cache.open("rb")) if day_lo <= e["day"] <= day_hi]
        print(f"cache events in window={len(xs)}", flush=True)
    except StopIteration:
        pass
    if not xs:
        print("collect events…", flush=True)
        xs = scalp.collect_scalp_events(df, day_lo, day_hi)
        print(f"collected={len(xs)}", flush=True)

    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)
    enrich_ind(xs, df)

    for e in xs:
        i = int(e["full_i"])
        ok, reason, exit_px, j, pts = path_detail(h, l, c, ema34, i, e["decision"], T1)
        e["_win"] = bool(ok)
        e["_reason"] = reason
        e["_exit_px"] = float(exit_px)
        e["_exit_i"] = int(j)
        e["_pts"] = float(pts)
        if 0 <= j < len(idx):
            e["_exit_hm"] = pd.Timestamp(idx[j]).tz_convert("Asia/Kolkata").strftime("%H:%M")
            e["_exit_day"] = str(pd.Timestamp(idx[j]).tz_convert("Asia/Kolkata").date())
        else:
            e["_exit_hm"] = "?"
            e["_exit_day"] = e["day"]

    by = defaultdict(list)
    for e in xs:
        by[e["day"]].append(e)

    trades = []
    for d in days5:
        rows = sorted(by.get(d, []), key=lambda x: x["mins"])
        call = next((e for e in rows if held_session(e)), None)
        if call:
            trades.append(call)
            print(
                f"  {d} {call['hm']} {call['decision']} {call['primary']} "
                f"→ {call['_exit_hm']} {call['_reason']} {call['_pts']:+.1f} "
                f"{'WIN' if call['_win'] else 'LOSS'}",
                flush=True,
            )
        else:
            print(f"  {d} NO HELD call in session", flush=True)

    # ---- chart: one panel per day ----
    fig, axes = plt.subplots(N_DAYS, 1, figsize=(16, 3.2 * N_DAYS), sharex=False)
    if N_DAYS == 1:
        axes = [axes]
    fig.suptitle(
        f"NIFTY 1m · HELD (DI+hard34+VWAP) · EMA34 trail T1={T1:.0f} · session 09:30–14:30\n"
        f"{day_lo} → {day_hi}",
        fontsize=12,
        fontweight="bold",
        y=0.995,
    )

    trade_by_day = {e["day"]: e for e in trades}

    for ax, d in zip(axes, days5):
        day_df = df[df["day"] == d].copy() if "day" in df.columns else df[df.index.strftime("%Y-%m-%d") == d].copy()
        if "day" not in day_df.columns:
            day_df["day"] = d
        # session display 09:15–15:29
        day_df = day_df[(day_df.index.strftime("%H:%M") >= "09:15") & (day_df.index.strftime("%H:%M") <= "15:29")]
        if day_df.empty:
            ax.set_title(f"{d} (no bars)")
            continue

        n = draw_candles(ax, day_df)
        xs_i = np.arange(n)
        # EMA34 aligned to day slice
        e34 = day_df["ema34"].astype(float).values
        ax.plot(xs_i, e34, color="#1f4e79", linewidth=1.2, label="EMA34", zorder=4)
        if "vwap" in day_df.columns:
            ax.plot(xs_i, day_df["vwap"].astype(float).values, color="#8e44ad", linewidth=1.0, alpha=0.85, label="VWAP", zorder=4)

        # shade skip zones: before 09:30 and from 14:30
        hm = day_df.index.strftime("%H:%M").tolist()
        for i, t in enumerate(hm):
            if t < "09:30" or t >= "14:30":
                ax.axvspan(i - 0.5, i + 0.5, color="#bdc3c7", alpha=0.25, zorder=0)

        tr = trade_by_day.get(d)
        if tr is not None:
            # map entry/exit full_i → day local index
            entry_ts = idx[int(tr["full_i"])]
            exit_ts = idx[int(tr["_exit_i"])]
            # local positions
            try:
                ei = day_df.index.get_loc(entry_ts)
                if isinstance(ei, slice):
                    ei = ei.start
                elif isinstance(ei, np.ndarray):
                    ei = int(np.where(ei)[0][0])
            except KeyError:
                ei = None
            try:
                xj = day_df.index.get_loc(exit_ts)
                if isinstance(xj, slice):
                    xj = xj.start
                elif isinstance(xj, np.ndarray):
                    xj = int(np.where(xj)[0][0])
            except KeyError:
                xj = None

            if ei is not None:
                y = float(tr["entry"])
                if tr["decision"] == "BUY":
                    ax.scatter([ei], [y], marker="^", s=120, color="#0b6e4f", zorder=6, label="ENTRY BUY")
                else:
                    ax.scatter([ei], [y], marker="v", s=120, color="#922b21", zorder=6, label="ENTRY SELL")
                ax.annotate(
                    f"{tr['hm']} {tr['decision']}\n{tr['primary']}",
                    (ei, y),
                    textcoords="offset points",
                    xytext=(6, 10),
                    fontsize=7,
                    color="#1a1a1a",
                )
            if xj is not None:
                yx = float(tr["_exit_px"])
                col = "#0b6e4f" if tr["_win"] else "#922b21"
                ax.scatter([xj], [yx], marker="X", s=90, color=col, zorder=6, label=f"EXIT {tr['_reason']}")
                ax.annotate(
                    f"{tr['_exit_hm']} {tr['_reason']} {tr['_pts']:+.0f}",
                    (xj, yx),
                    textcoords="offset points",
                    xytext=(6, -14),
                    fontsize=7,
                    color=col,
                )
                if ei is not None:
                    ax.plot([ei, xj], [float(tr["entry"]), yx], color=col, linestyle="--", linewidth=1.0, alpha=0.7, zorder=5)

            res = "WIN" if tr["_win"] else "LOSS"
            ax.set_title(f"{d}  ·  {tr['decision']} {tr['primary']} @ {tr['hm']} → {tr['_exit_hm']} ({tr['_reason']})  {tr['_pts']:+.1f}  [{res}]", fontsize=9)
        else:
            ax.set_title(f"{d}  ·  no HELD call in 09:30–14:30", fontsize=9)

        # x ticks every ~30 min
        tick_idx = []
        tick_lbl = []
        for i, t in enumerate(hm):
            if t.endswith(":00") or t.endswith(":30") or i == 0 or i == n - 1:
                tick_idx.append(i)
                tick_lbl.append(t)
        ax.set_xticks(tick_idx[::2] if len(tick_idx) > 12 else tick_idx)
        ax.set_xticklabels(
            [tick_lbl[j] for j in range(0, len(tick_lbl), 2)] if len(tick_idx) > 12 else tick_lbl,
            fontsize=7,
            rotation=0,
        )
        ax.set_xlim(-1, n)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="upper left", fontsize=7, framealpha=0.85)

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(PNG, dpi=140)
    plt.close(fig)
    print(f"Wrote {PNG}", flush=True)

    # HTML companion (opens PNG + trade table)
    rows = []
    for e in trades:
        rows.append(
            f"<tr><td>{e['day']}</td><td>{e['hm']}</td><td>{e['decision']}</td>"
            f"<td>{e['primary']}</td><td>{e['entry']:.2f}</td><td>{e['_exit_hm']}</td>"
            f"<td>{e['_exit_px']:.2f}</td><td>{e['_reason']}</td>"
            f"<td>{e['_pts']:+.2f}</td><td>{'WIN' if e['_win'] else 'LOSS'}</td></tr>"
        )
    HTML.write_text(
        f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>NIFTY HELD last 5d</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f7f7f5;color:#1a1a1a}}
img{{max-width:100%;border:1px solid #ddd;background:#fff}}
table{{border-collapse:collapse;margin-top:16px;background:#fff}}
th,td{{border:1px solid #ccc;padding:6px 10px;font-size:13px}}
th{{background:#eee}}
code{{background:#eee;padding:1px 4px}}
</style></head><body>
<h2>NIFTY 1m — HELD on chart (last 5 days)</h2>
<p>Entry: textbook + <code>DI_ok</code> + <code>gate_hard34</code> + <code>vwap_with</code> · 09:30–14:30 · 1/day<br>
Exit: EMA34 trail · T1={T1:.0f} · grey bands = skipped session</p>
<p><img src="{PNG.name}" alt="chart"/></p>
<table>
<tr><th>Day</th><th>Entry</th><th>Side</th><th>Pattern</th><th>Entry₹</th>
<th>Exit</th><th>Exit₹</th><th>Reason</th><th>Pts</th><th>Result</th></tr>
{''.join(rows)}
</table>
</body></html>
""",
        encoding="utf-8",
    )
    print(f"Wrote {HTML}", flush=True)

    w = sum(1 for e in trades if e["_win"])
    md = [
        "# NIFTY 1m HELD — last 5 days on chart",
        "",
        f"Days: **{day_lo} → {day_hi}** · T1=**{T1:.0f}** · session **09:30–14:30**",
        "",
        f"- Chart PNG: `{PNG.relative_to(ROOT).as_posix()}`",
        f"- HTML: `{HTML.relative_to(ROOT).as_posix()}`",
        "",
        f"Calls **{len(trades)}** · W={w} L={len(trades)-w} · hit **{round(100*w/len(trades),1) if trades else 0}%**",
        "",
        "| Day | Entry | Side | Pattern | In | Exit | Out | Reason | Pts |",
        "|---|---|---|---|---:|---|---:|---|---:|",
    ]
    for e in trades:
        md.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | {e['entry']:.2f} | "
            f"{e['_exit_hm']} | {e['_exit_px']:.2f} | `{e['_reason']}` | {e['_pts']:+.1f} |"
        )
    REPORT.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
