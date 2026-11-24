"""HELD + clear_20 + bounce on UNKNOWN windows + chart.

Gate locked from last-1m peek interest — now scored on prior unknown months
and plotted on last 5 trading days (visual verify).

  Entry: DI+hard34+VWAP · 09:30–14:30 · clear_20 · bounce · 1/day first
  Exit : EMA34 trail · T1=12

  python -u prod_live/tests/builders/_diag_scalp_ma_hold100_sr_bounce20_unknown.py
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
from _diag_scalp_ma_hold100_sr_filter import (  # noqa: E402
    MINS_LO,
    MINS_HI,
    T1,
    build_pivots,
    day_levels_map,
    enrich_sr,
    in_session,
    path_fixed_t1,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_DIR = OUT / "charts"
PNG = OUT_DIR / "NIFTY_1M_HELD_CLEAR20_BOUNCE_UNKNOWN5D.png"
HTML = OUT_DIR / "NIFTY_1M_HELD_CLEAR20_BOUNCE_UNKNOWN5D.html"
REPORT = OUT / "NIFTY_1M_HELD_CLEAR20_BOUNCE_UNKNOWN.md"
N_DAYS = 5


def gate_clear20_bounce(e) -> bool:
    return (
        in_session(e)
        and held_gate(e)
        and bool(e.get("sr_clear_20"))
        and bool(e.get("sr_bounce"))
    )


def first_pass(xs, pred):
    for e in sorted(xs, key=lambda x: x["mins"]):
        if pred(e):
            return e
    return None


def score_calls(events, days, h, l, c, ema34, gate):
    by = defaultdict(list)
    for e in events:
        by[e["day"]].append(e)
    calls = []
    for d in days:
        e = first_pass(by.get(d, []), gate)
        if not e:
            continue
        i = int(e["full_i"])
        ok, reason, pts = path_fixed_t1(h, l, c, ema34, i, e["decision"], T1)
        row = dict(e)
        row["_win"] = bool(ok)
        row["_reason"] = reason
        row["_pts"] = float(pts)
        # exit detail for chart
        entry = float(e["entry"])
        end = min(len(c) - 1, i + 120)
        exit_i, exit_px = end, float(c[end])
        if e["decision"] == "BUY":
            t1 = entry + T1
            for j in range(i + 1, end + 1):
                hi, cl, m = float(h[j]), float(c[j]), float(ema34[j])
                if hi >= t1:
                    exit_i, exit_px = j, t1
                    break
                if cl < m:
                    exit_i, exit_px = j, cl
                    break
        else:
            t1 = entry - T1
            for j in range(i + 1, end + 1):
                lo, cl, m = float(l[j]), float(c[j]), float(ema34[j])
                if lo <= t1:
                    exit_i, exit_px = j, t1
                    break
                if cl > m:
                    exit_i, exit_px = j, cl
                    break
        row["_exit_i"] = exit_i
        row["_exit_px"] = exit_px
        calls.append(row)
    return calls


def summarize(calls, nd):
    n = len(calls)
    if n == 0:
        return {"n": 0, "hit": 0.0, "cover": 0.0, "avg_pts": 0.0, "total_pts": 0.0}
    w = sum(1 for e in calls if e["_win"])
    pts = [e["_pts"] for e in calls]
    return {
        "n": n,
        "hit": round(100 * w / n, 2),
        "cover": round(100 * n / nd, 2) if nd else 0.0,
        "avg_pts": round(float(np.mean(pts)), 2),
        "total_pts": round(float(np.sum(pts)), 2),
        "wins": w,
        "losses": n - w,
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
        ax.vlines(i, l[i], h[i], color=color, linewidth=0.7, zorder=2)
        bottom = min(o[i], c[i])
        height = abs(c[i] - o[i]) or 0.15
        ax.add_patch(
            Rectangle((i - width / 2, bottom), width, height, facecolor=color, edgecolor=color, linewidth=0.4, zorder=3)
        )
    return n


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("HELD+clear20+bounce · UNKNOWN windows + 5d chart", flush=True)

    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    data_hi = str(raw.index.max().date())
    y1_lo = max(str((pd.Timestamp(data_hi) - pd.DateOffset(years=1) + pd.Timedelta(days=1)).date()), WIN_LO)

    # last 1m = SEEN (where combo looked good); everything before = UNKNOWN
    seen_lo = max(str((pd.Timestamp(data_hi) - pd.DateOffset(months=1) + pd.Timedelta(days=1)).date()), y1_lo)
    unk_hi = str((pd.Timestamp(seen_lo) - pd.Timedelta(days=1)).date())

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

    print("[1] pivots + S/R…", flush=True)
    piv_hi, piv_lo = build_pivots(h, l)
    prev_map, opens = day_levels_map(df)

    cache = next(PACK.glob("events_2025-11-17_*.pkl"))
    xs = [e for e in pickle.load(cache.open("rb")) if y1_lo <= e["day"] <= data_hi]
    print(f"events={len(xs)}", flush=True)

    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)
    enrich_ind(xs, df)
    enrich_sr(xs, h, l, c, df, piv_hi, piv_lo, prev_map, opens)

    sess_days = sorted({e["day"] for e in xs if in_session(e)})

    def days_in(lo, hi):
        return [d for d in sess_days if lo <= d <= hi]

    # UNKNOWN slices (before last 1m)
    unk_1m_lo = max(str((pd.Timestamp(unk_hi) - pd.DateOffset(months=1) + pd.Timedelta(days=1)).date()), y1_lo)
    unk_3m_lo = max(str((pd.Timestamp(unk_hi) - pd.DateOffset(months=3) + pd.Timedelta(days=1)).date()), y1_lo)
    windows = [
        ("SEEN last_1m (reference)", seen_lo, data_hi),
        ("UNKNOWN prior_1m", unk_1m_lo, unk_hi),
        ("UNKNOWN prior_3m", unk_3m_lo, unk_hi),
        ("UNKNOWN rest_of_1y (excl last_1m)", y1_lo, unk_hi),
    ]

    lines = [
        "# HELD + clear_20 + bounce — UNKNOWN test",
        "",
        "Gate locked after last-1m interest. **Unknown** = months before last 1m (not used to pick the gate).",
        "",
        f"- Entry: DI+hard34+VWAP · 09:30–14:30 · **room_fav ≥ 20** · **bounce** (near fav S/R) · 1/day",
        f"- Exit: EMA34 trail · T1={T1:.0f}",
        f"- Data end `{data_hi}` · seen last_1m from `{seen_lo}` · unknown through `{unk_hi}`",
        "",
        "| Window | n | Hit% | Cover | W/L | Avg pts | Total |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    print(f"seen {seen_lo}→{data_hi} · unknown ≤{unk_hi}", flush=True)
    all_ledgers = {}
    for wname, wlo, whi in windows:
        wdays = days_in(wlo, whi)
        # also compare plain HELD
        held_only = score_calls(xs, wdays, h, l, c, ema34, lambda e: in_session(e) and held_gate(e))
        gated = score_calls(xs, wdays, h, l, c, ema34, gate_clear20_bounce)
        st_h = summarize(held_only, len(wdays))
        st_g = summarize(gated, len(wdays))
        print(
            f"  {wname}: HELD {st_h['n']}@{st_h['hit']}%/{st_h['avg_pts']}  "
            f"clear20+bounce {st_g['n']}@{st_g['hit']}%/{st_g['avg_pts']} cover={st_g['cover']}%",
            flush=True,
        )
        lines.append(
            f"| **{wname}** | {st_g['n']} | **{st_g['hit']}%** | {st_g['cover']}% | "
            f"{st_g.get('wins',0)}/{st_g.get('losses',0)} | {st_g['avg_pts']} | {st_g['total_pts']} |"
        )
        lines.append(
            f"| ↳ plain HELD (same window) | {st_h['n']} | {st_h['hit']}% | {st_h['cover']}% | "
            f"{st_h.get('wins',0)}/{st_h.get('losses',0)} | {st_h['avg_pts']} | {st_h['total_pts']} |"
        )
        all_ledgers[wname] = gated

    # UNKNOWN prior_1m full ledger
    unk_calls = all_ledgers["UNKNOWN prior_1m"]
    lines += [
        "",
        f"## UNKNOWN prior_1m ledger (`{unk_1m_lo}` → `{unk_hi}`)",
        "",
        "| Day | Entry | Side | Pattern | room_fav | S | R | Exit | Reason | Pts |",
        "|---|---|---|---|---:|---:|---:|---|---|---:|",
    ]
    for e in unk_calls:
        # exit hm
        j = int(e["_exit_i"])
        ehm = pd.Timestamp(idx[j]).tz_convert("Asia/Kolkata").strftime("%H:%M")
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
            f"{e.get('sr_room_fav')} | {e.get('sr_support')} | {e.get('sr_resist')} | "
            f"{ehm} | `{e['_reason']}` | {e['_pts']:+.1f} |"
        )
    lines.append("")

    # ---- chart last 5 days ----
    all_days = sorted({str(ts.date()) for ts in raw.index})
    days5 = all_days[-N_DAYS:]
    day_lo, day_hi = days5[0], days5[-1]
    chart_calls = score_calls(xs, days5, h, l, c, ema34, gate_clear20_bounce)
    held5 = score_calls(xs, days5, h, l, c, ema34, lambda e: in_session(e) and held_gate(e))
    by_c = {e["day"]: e for e in chart_calls}
    by_h = {e["day"]: e for e in held5}
    print(f"\nchart days {days5}", flush=True)
    for d in days5:
        e = by_c.get(d)
        if e:
            print(
                f"  {d} CLEAR20+BOUNCE {e['hm']} {e['decision']} {e['primary']} "
                f"room={e.get('sr_room_fav')} → {e['_reason']} {e['_pts']:+.1f}",
                flush=True,
            )
        else:
            hld = by_h.get(d)
            why = "no HELD" if not hld else f"HELD@{hld['hm']} blocked (room={hld.get('sr_room_fav')} bounce={hld.get('sr_bounce')})"
            print(f"  {d} NO clear20+bounce · {why}", flush=True)

    fig, axes = plt.subplots(N_DAYS, 1, figsize=(16, 3.2 * N_DAYS), sharex=False)
    if N_DAYS == 1:
        axes = [axes]
    fig.suptitle(
        f"NIFTY 1m · HELD + clear_20 + bounce · T1={T1:.0f} · 09:30–14:30\n"
        f"Last {N_DAYS} days {day_lo} → {day_hi} (visual unknown check)",
        fontsize=12,
        fontweight="bold",
        y=0.995,
    )

    for ax, d in zip(axes, days5):
        day_df = df[df["day"] == d].copy() if "day" in df.columns else df[df.index.strftime("%Y-%m-%d") == d].copy()
        day_df = day_df[(day_df.index.strftime("%H:%M") >= "09:15") & (day_df.index.strftime("%H:%M") <= "15:29")]
        if day_df.empty:
            ax.set_title(f"{d} (no bars)")
            continue
        n = draw_candles(ax, day_df)
        xs_i = np.arange(n)
        ax.plot(xs_i, day_df["ema34"].astype(float).values, color="#1f4e79", lw=1.2, label="EMA34", zorder=4)
        if "vwap" in day_df.columns:
            ax.plot(xs_i, day_df["vwap"].astype(float).values, color="#8e44ad", lw=1.0, alpha=0.85, label="VWAP", zorder=4)

        hm = day_df.index.strftime("%H:%M").tolist()
        for i, t in enumerate(hm):
            if t < "09:30" or t >= "14:30":
                ax.axvspan(i - 0.5, i + 0.5, color="#bdc3c7", alpha=0.25, zorder=0)

        tr = by_c.get(d)
        skipped = by_h.get(d) if tr is None else None

        def loc(ts):
            try:
                ei = day_df.index.get_loc(ts)
                if isinstance(ei, slice):
                    return ei.start
                if isinstance(ei, np.ndarray):
                    return int(np.where(ei)[0][0])
                return int(ei)
            except KeyError:
                return None

        if tr is not None:
            # S/R lines
            if tr.get("sr_support") is not None:
                ax.axhline(tr["sr_support"], color="#27ae60", ls=":", lw=1.0, alpha=0.8, label=f"S {tr['sr_support']}")
            if tr.get("sr_resist") is not None:
                ax.axhline(tr["sr_resist"], color="#e74c3c", ls=":", lw=1.0, alpha=0.8, label=f"R {tr['sr_resist']}")
            ei = loc(idx[int(tr["full_i"])])
            xj = loc(idx[int(tr["_exit_i"])])
            if ei is not None:
                y = float(tr["entry"])
                mk = "^" if tr["decision"] == "BUY" else "v"
                col = "#0b6e4f" if tr["decision"] == "BUY" else "#922b21"
                ax.scatter([ei], [y], marker=mk, s=130, color=col, zorder=6)
                ax.annotate(
                    f"{tr['hm']} {tr['decision']}\n{tr['primary']}\nroom={tr.get('sr_room_fav')}",
                    (ei, y),
                    textcoords="offset points",
                    xytext=(6, 10),
                    fontsize=7,
                )
            if xj is not None:
                yx = float(tr["_exit_px"])
                col = "#0b6e4f" if tr["_win"] else "#922b21"
                ax.scatter([xj], [yx], marker="X", s=90, color=col, zorder=6)
                if ei is not None:
                    ax.plot([ei, xj], [float(tr["entry"]), yx], color=col, ls="--", lw=1.0, alpha=0.7)
            res = "WIN" if tr["_win"] else "LOSS"
            ax.set_title(
                f"{d}  CLEAR20+BOUNCE  {tr['decision']} {tr['primary']} @ {tr['hm']}  "
                f"S={tr.get('sr_support')} R={tr.get('sr_resist')} room={tr.get('sr_room_fav')}  "
                f"→ {tr['_reason']} {tr['_pts']:+.1f} [{res}]",
                fontsize=8,
            )
        elif skipped is not None:
            if skipped.get("sr_support") is not None:
                ax.axhline(skipped["sr_support"], color="#27ae60", ls=":", lw=1.0, alpha=0.5)
            if skipped.get("sr_resist") is not None:
                ax.axhline(skipped["sr_resist"], color="#e74c3c", ls=":", lw=1.0, alpha=0.5)
            ei = loc(idx[int(skipped["full_i"])])
            if ei is not None:
                ax.scatter([ei], [float(skipped["entry"])], marker="o", s=60, facecolors="none", edgecolors="#7f8c8d", zorder=5)
            ax.set_title(
                f"{d}  SKIPPED  HELD@{skipped['hm']} {skipped['decision']} "
                f"room={skipped.get('sr_room_fav')} bounce={int(bool(skipped.get('sr_bounce')))} clear20={int(bool(skipped.get('sr_clear_20')))}",
                fontsize=8,
            )
        else:
            ax.set_title(f"{d}  no HELD call in session", fontsize=9)

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

    st5 = summarize(chart_calls, len(days5))
    rows = []
    for e in chart_calls:
        j = int(e["_exit_i"])
        ehm = pd.Timestamp(idx[j]).tz_convert("Asia/Kolkata").strftime("%H:%M")
        rows.append(
            f"<tr><td>{e['day']}</td><td>{e['hm']}</td><td>{e['decision']}</td><td>{e['primary']}</td>"
            f"<td>{e.get('sr_room_fav')}</td><td>{e.get('sr_support')}</td><td>{e.get('sr_resist')}</td>"
            f"<td>{ehm}</td><td>{e['_reason']}</td><td>{e['_pts']:+.1f}</td>"
            f"<td>{'WIN' if e['_win'] else 'LOSS'}</td></tr>"
        )
    HTML.write_text(
        f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>clear20+bounce</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f7f7f5}}
img{{max-width:100%;border:1px solid #ddd}}table{{border-collapse:collapse;background:#fff}}
th,td{{border:1px solid #ccc;padding:6px 10px;font-size:13px}}th{{background:#eee}}</style></head>
<body><h2>HELD + clear_20 + bounce · last 5d</h2>
<p>Hit {st5['hit']}% · n={st5['n']} · grey=session skip · green/red dotted=S/R · hollow circle=HELD blocked</p>
<img src="{PNG.name}" alt="chart"/>
<table><tr><th>Day</th><th>Entry</th><th>Side</th><th>Pattern</th><th>room</th>
<th>S</th><th>R</th><th>Exit</th><th>Why</th><th>Pts</th><th>Result</th></tr>
{''.join(rows)}</table></body></html>""",
        encoding="utf-8",
    )

    lines += [
        f"## Last {N_DAYS} days chart",
        "",
        f"- PNG: `{PNG.relative_to(ROOT).as_posix()}`",
        f"- HTML: `{HTML.relative_to(ROOT).as_posix()}`",
        f"- Calls **{st5['n']}** · hit **{st5['hit']}%** · avg {st5['avg_pts']}",
        "",
        "| Day | Entry | Side | Pattern | room | Result | Pts |",
        "|---|---|---|---|---:|---|---:|",
    ]
    for e in chart_calls:
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
            f"{e.get('sr_room_fav')} | {'WIN' if e['_win'] else 'LOSS'} | {e['_pts']:+.1f} |"
        )
    for d in days5:
        if d not in by_c:
            hld = by_h.get(d)
            if hld:
                lines.append(
                    f"| {d} | — | SKIP | HELD@{hld['hm']} room={hld.get('sr_room_fav')} "
                    f"bounce={int(bool(hld.get('sr_bounce')))} | {hld.get('sr_room_fav')} | — | — |"
                )
            else:
                lines.append(f"| {d} | — | no HELD | — | — | — | — |")

    lines += [
        "",
        "## Verdict",
        "",
        "If UNKNOWN prior windows keep hit/avg near SEEN last_1m → gate is usable; "
        "if they collapse → last_1m was lucky, do not lock yet.",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
