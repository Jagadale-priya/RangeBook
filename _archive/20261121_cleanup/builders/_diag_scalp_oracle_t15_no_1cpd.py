"""RESEARCH ONLY — Oracle T15 + EMA34 trail filters WITHOUT 1-call/day.

Ranks blind gates by gap15 / all-calls hit (not first-of-day).

  python -u prod_live/tests/builders/_diag_scalp_oracle_t15_no_1cpd.py
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
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402
from _diag_scalp_sr_highmove_proven import enrich_sr_archetypes, in_session  # noqa: E402
from _diag_scalp_ad_sr_entry_1m import add_ad_obv_proxy  # noqa: E402

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ORACLE_T15_NO_1CPD.md"
REPORT_JSON = OUT / "NIFTY_1M_ORACLE_T15_NO_1CPD.json"

T15 = 15.0
GAP = 15


def score_trail(events, h, l, c, ema34, t1):
    key = f"_w{int(t1)}"
    for e in events:
        ok, reason, sl, t1v = path_ma_trail_strict(
            h, l, c, ema34, int(e["full_i"]), e["decision"], float(t1)
        )
        e[key] = bool(ok)
        e[f"_r{int(t1)}"] = reason
        e[f"_pts{int(t1)}"] = float(t1v if ok else -(abs(sl) if sl else 0))


def gap_book(rows, pred, gap=GAP):
    by = defaultdict(list)
    for e in rows:
        by[e["day"]].append(e)
    out = []
    for d in sorted(by):
        next_ok = None
        for e in sorted(by[d], key=lambda x: x["mins"]):
            if not pred(e):
                continue
            if next_ok is not None and e["mins"] < next_ok:
                continue
            out.append(e)
            next_ok = int(e["mins"]) + gap
    return out


def all_calls(rows, pred):
    return [e for e in rows if pred(e)]


def summarize(calls, t1, n_days):
    n = len(calls)
    if not n:
        return {"n": 0, "hit": None, "cpd": 0.0, "w": 0, "l": 0, "avg_pts": None}
    key = f"_w{int(t1)}"
    w = sum(1 for e in calls if e.get(key))
    pts = [e.get(f"_pts{int(t1)}") or 0 for e in calls]
    return {
        "n": n,
        "hit": round(100.0 * w / n, 2),
        "cpd": round(n / n_days, 2) if n_days else 0.0,
        "w": w,
        "l": n - w,
        "avg_pts": round(float(np.mean(pts)), 2),
    }


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("Oracle T15 NO 1cpd research (NOT live)", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=55)]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    df = add_ad_obv_proxy(df)

    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-22:]) if len(days_all) > 22 else set(days_all)
    day_lo, day_hi = min(keep), max(keep)
    n_days = len(keep)
    print(f"window {day_lo}→{day_hi} n_days={n_days}", flush=True)

    events = scalp.collect_scalp_events(
        df, str(df.index.min().date()), str(df.index.max().date())
    )
    enrich_ma_layers(events, df)
    enrich_ind(events, df)
    setup.apply_setup_enrichment(events, df)
    enrich_sr_archetypes(events, df)

    ad_r = df["ad_rising"].astype(bool).values
    ad_f = df["ad_falling"].astype(bool).values
    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        e["ad_with"] = (side == "BUY" and bool(ad_r[i])) or (
            side == "SELL" and bool(ad_f[i])
        )
        e["not_extreme"] = not bool(e.get("into_sess_extreme"))
        e["held"] = held_gate(e)
        e["sess"] = in_session(e)
        e["room_ok"] = bool(e.get("clear_path"))
        e["ctrl"] = bool(e.get("control_with"))
        e["di8"] = abs(float(e.get("di_spread") or 0)) >= 8
        e["magnet"] = bool(e.get("at_liq_magnet"))

    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    score_trail(events, h, l, c, ema34, T15)

    pool = [e for e in events if e["day"] in keep and e["sess"]]
    print(f"pool={len(pool)}", flush=True)

    gates = [
        ("ALL textbook sess", lambda e: True),
        ("HELD", lambda e: e.get("held")),
        ("HELD + !extreme", lambda e: e.get("held") and e.get("not_extreme")),
        ("HELD + AD", lambda e: e.get("held") and e.get("ad_with")),
        ("HELD + !extreme + AD", lambda e: e.get("held") and e.get("not_extreme") and e.get("ad_with")),
        ("HELD + AD + into_extreme", lambda e: e.get("held") and e.get("ad_with") and e.get("into_sess_extreme")),
        ("HELD + clear", lambda e: e.get("held") and e.get("room_ok")),
        ("HELD + !extreme + clear", lambda e: e.get("held") and e.get("not_extreme") and e.get("room_ok")),
        ("HELD + !extreme + clear + AD", lambda e: e.get("held") and e.get("not_extreme") and e.get("room_ok") and e.get("ad_with")),
        ("HELD + !extreme + ctrl", lambda e: e.get("held") and e.get("not_extreme") and e.get("ctrl")),
        ("HELD + AD + ctrl", lambda e: e.get("held") and e.get("ad_with") and e.get("ctrl")),
        ("HELD + !extreme + AD + ctrl", lambda e: e.get("held") and e.get("not_extreme") and e.get("ad_with") and e.get("ctrl")),
        ("HELD + !extreme + clear + AD + ctrl", lambda e: e.get("held") and e.get("not_extreme") and e.get("room_ok") and e.get("ad_with") and e.get("ctrl")),
        ("HELD + di8", lambda e: e.get("held") and e.get("di8")),
        ("HELD + !extreme + di8", lambda e: e.get("held") and e.get("not_extreme") and e.get("di8")),
        ("TierAB", lambda e: e.get("setup_ok")),
        ("TierAB + !extreme", lambda e: e.get("setup_ok") and e.get("not_extreme")),
        ("TierA only", lambda e: e.get("setup_tier") == "A"),
        ("Oracle T15 (hindsight all wins)", lambda e: e.get("_w15")),
    ]

    rows = []
    for name, pred in gates:
        gall = all_calls(pool, pred)
        ggap = gap_book(pool, pred, GAP)
        sa = summarize(gall, T15, n_days)
        sg = summarize(ggap, T15, n_days)
        peek = "Oracle" in name
        rows.append({"name": name, "all": sa, "gap15": sg, "peek": peek})
        print(
            f"  {name}: all hit={sa['hit']}% n={sa['n']} cpd={sa['cpd']} | "
            f"gap15 hit={sg['hit']}% n={sg['n']} cpd={sg['cpd']}",
            flush=True,
        )

    # Rank blind by gap15 hit then all hit (n>=30 for gap, n>=50 for all)
    blind_gap = [r for r in rows if not r["peek"] and (r["gap15"]["n"] or 0) >= 30]
    blind_gap.sort(key=lambda r: (-(r["gap15"]["hit"] or 0), -(r["gap15"]["n"] or 0)))
    blind_all = [r for r in rows if not r["peek"] and (r["all"]["n"] or 0) >= 50]
    blind_all.sort(key=lambda r: (-(r["all"]["hit"] or 0), -(r["all"]["n"] or 0)))

    lines = [
        "# NIFTY 1m — Oracle T15 · EMA34 trail · **NO 1-call/day**",
        "",
        "> **RESEARCH ONLY — not changing Scalper live.**",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days} sessions) · 09:30–14:30 · exit **EMA34 trail · T15**.",
        "",
        "Books:",
        "- **all** = every matching bar (multi-call, no spacing)",
        "- **gap15** = multi-call with ≥15 min between entries",
        "",
        "## Ranked by gap15 hit% (n≥30)",
        "",
        "| Gate | gap15 Hit% | n | calls/day | avg pts | all Hit% | n | cpd |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in blind_gap:
        a, g = r["all"], r["gap15"]
        lines.append(
            f"| `{r['name']}` | **{g['hit']}** | {g['n']} | {g['cpd']} | {g['avg_pts']} | "
            f"{a['hit']} | {a['n']} | {a['cpd']} |"
        )

    lines += [
        "",
        "## Ranked by all-calls hit% (n≥50)",
        "",
        "| Gate | all Hit% | n | calls/day | avg pts | gap15 Hit% | n |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in blind_all:
        a, g = r["all"], r["gap15"]
        lines.append(
            f"| `{r['name']}` | **{a['hit']}** | {a['n']} | {a['cpd']} | {a['avg_pts']} | "
            f"{g['hit']} | {g['n']} |"
        )

    top_g = blind_gap[0] if blind_gap else None
    top_a = blind_all[0] if blind_all else None
    oracle = next((r for r in rows if r["peek"]), None)

    lines += [
        "",
        "## Takeaway (no 1cpd)",
        "",
    ]
    if oracle:
        lines.append(
            f"Oracle (all path-wins, peek): hit **{oracle['all']['hit']}%** · "
            f"n={oracle['all']['n']} · ~{oracle['all']['cpd']}/day."
        )
    if top_g:
        lines.append(
            f"Best **gap15** blind: `{top_g['name']}` → **{top_g['gap15']['hit']}%** · "
            f"n={top_g['gap15']['n']} · {top_g['gap15']['cpd']}/day · avg {top_g['gap15']['avg_pts']} pts."
        )
    if top_a:
        lines.append(
            f"Best **all-calls** blind: `{top_a['name']}` → **{top_a['all']['hit']}%** · "
            f"n={top_a['all']['n']} · {top_a['all']['cpd']}/day."
        )
    lines += [
        "",
        "Without 1cpd, hit% drops vs first-of-day books (more mid-day noise). "
        "Prefer **gap15** over raw all-calls for a usable multi-entry book.",
        "",
        f"Elapsed {time.time() - t0:.0f}s",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {"window": [day_lo, day_hi], "n_days": n_days, "rows": rows},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {REPORT}", flush=True)
    if top_g:
        print(
            f"BEST gap15: {top_g['name']} hit={top_g['gap15']['hit']} n={top_g['gap15']['n']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
