"""RESEARCH ONLY — Oracle T15 + EMA34 trail: explain session-extreme & boost accuracy.

What user likes: Oracle T15 · EMA34 trail (high success; some fails OK).
Goal: research filters that keep that logic but lift blind/deployable accuracy.

Also documents: into_sess_extreme (“not into session extreme”).

  python -u prod_live/tests/builders/_diag_scalp_oracle_t15_accuracy_boost.py
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
REPORT = OUT / "NIFTY_1M_ORACLE_T15_ACCURACY_BOOST.md"
REPORT_JSON = OUT / "NIFTY_1M_ORACLE_T15_ACCURACY_BOOST.json"

T15 = 15.0
T12 = 12.0
GAP = 15
MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30


def score_trail(events, h, l, c, ema34, t1):
    key = f"_w{int(t1)}"
    for e in events:
        ok, reason, sl, t1v = path_ma_trail_strict(
            h, l, c, ema34, int(e["full_i"]), e["decision"], float(t1)
        )
        e[key] = bool(ok)
        e[f"_r{int(t1)}"] = reason
        e[f"_pts{int(t1)}"] = float(t1v if ok else -(abs(sl) if sl else 0))


def first_per_day(rows, pred):
    by = defaultdict(list)
    for e in rows:
        by[e["day"]].append(e)
    out = []
    for d in sorted(by):
        for e in sorted(by[d], key=lambda x: x["mins"]):
            if pred(e):
                out.append(e)
                break
    return out


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


def summarize(calls, t1, n_days):
    n = len(calls)
    if not n:
        return {"n": 0, "hit": None, "cover": 0.0, "w": 0, "l": 0, "avg_pts": None}
    key = f"_w{int(t1)}"
    w = sum(1 for e in calls if e.get(key))
    pts = [e.get(f"_pts{int(t1)}") or 0 for e in calls]
    return {
        "n": n,
        "hit": round(100.0 * w / n, 2),
        "cover": round(100.0 * n / n_days, 2) if n_days else 0.0,
        "w": w,
        "l": n - w,
        "avg_pts": round(float(np.mean(pts)), 2),
    }


def feat_rate(rows, key, t1=None):
    if not rows:
        return None
    if t1 is None:
        return round(100.0 * sum(1 for e in rows if e.get(key)) / len(rows), 1)
    wk = f"_w{int(t1)}"
    return round(100.0 * sum(1 for e in rows if e.get(key) and e.get(wk)) / len(rows), 1)


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("Oracle T15 accuracy boost research (NOT live)", flush=True)

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
    print(f"window {day_lo}→{day_hi} n_days={len(keep)}", flush=True)

    events = scalp.collect_scalp_events(df, str(df.index.min().date()), str(df.index.max().date()))
    enrich_ma_layers(events, df)
    enrich_ind(events, df)
    setup.apply_setup_enrichment(events, df)
    enrich_sr_archetypes(events, df)

    # A/D with
    ad_r = df["ad_rising"].astype(bool).values
    ad_f = df["ad_falling"].astype(bool).values
    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        e["ad_with"] = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))
        e["not_extreme"] = not bool(e.get("into_sess_extreme"))
        e["held"] = held_gate(e)
        e["sess"] = in_session(e)
        a = float(e.get("atr") or 8.0)
        # finer extreme bands
        dh = e.get("dist_sess_high")
        dl = e.get("dist_sess_low")
        e["near_high_1atr"] = dh is not None and dh <= 1.0 * a
        e["near_low_1atr"] = dl is not None and dl <= 1.0 * a
        e["near_high_2atr"] = dh is not None and dh <= 2.0 * a
        e["near_low_2atr"] = dl is not None and dl <= 2.0 * a
        e["into_ext_1atr"] = (side == "BUY" and e["near_high_1atr"]) or (
            side == "SELL" and e["near_low_1atr"]
        )
        e["into_ext_2atr"] = (side == "BUY" and e["near_high_2atr"]) or (
            side == "SELL" and e["near_low_2atr"]
        )
        e["room_ok"] = bool(e.get("clear_path"))
        e["ctrl"] = bool(e.get("control_with"))
        e["di8"] = abs(float(e.get("di_spread") or 0)) >= 8

    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    score_trail(events, h, l, c, ema34, T15)
    score_trail(events, h, l, c, ema34, T12)

    pool = [e for e in events if e["day"] in keep and e["sess"]]
    n_days = len(keep)
    wins15 = [e for e in pool if e.get("_w15")]
    loss15 = [e for e in pool if not e.get("_w15")]
    print(f"pool={len(pool)} T15 wins={len(wins15)} losses={len(loss15)}", flush=True)

    # Oracle books (hindsight path-wins) — what Scalper Oracle mode shows
    oracle_1cpd = first_per_day(pool, lambda e: e.get("_w15"))
    oracle_gap = gap_book(pool, lambda e: e.get("_w15"), GAP)
    # Among oracle wins: session extreme stats
    ext_on_wins = sum(1 for e in wins15 if e.get("into_sess_extreme"))
    ext_on_loss = sum(1 for e in loss15 if e.get("into_sess_extreme"))

    # Blind gates scored with T15 trail (deployable shape)
    gates = [
        ("ALL textbook sess", lambda e: True),
        ("HELD", lambda e: e.get("held")),
        ("HELD + !extreme (code default)", lambda e: e.get("held") and e.get("not_extreme")),
        ("HELD + !ext_1atr", lambda e: e.get("held") and not e.get("into_ext_1atr")),
        ("HELD + !ext_2atr", lambda e: e.get("held") and not e.get("into_ext_2atr")),
        ("HELD + clear_path", lambda e: e.get("held") and e.get("room_ok")),
        ("HELD + !extreme + clear", lambda e: e.get("held") and e.get("not_extreme") and e.get("room_ok")),
        ("HELD + !extreme + AD", lambda e: e.get("held") and e.get("not_extreme") and e.get("ad_with")),
        ("HELD + !extreme + ctrl", lambda e: e.get("held") and e.get("not_extreme") and e.get("ctrl")),
        ("HELD + !extreme + clear + AD", lambda e: e.get("held") and e.get("not_extreme") and e.get("room_ok") and e.get("ad_with")),
        ("HELD + !extreme + clear + ctrl", lambda e: e.get("held") and e.get("not_extreme") and e.get("room_ok") and e.get("ctrl")),
        ("HELD + !extreme + clear + AD + ctrl", lambda e: e.get("held") and e.get("not_extreme") and e.get("room_ok") and e.get("ad_with") and e.get("ctrl")),
        ("HELD + !extreme + di8", lambda e: e.get("held") and e.get("not_extreme") and e.get("di8")),
        ("HELD + !extreme + clear + di8", lambda e: e.get("held") and e.get("not_extreme") and e.get("room_ok") and e.get("di8")),
        ("TierAB + !extreme", lambda e: e.get("setup_ok")),
        ("TierAB + clear", lambda e: e.get("setup_ok") and e.get("room_ok")),
        ("TierA only", lambda e: e.get("setup_tier") == "A"),
        ("Oracle T15 (hindsight 1/day)", None),  # placeholder
    ]

    rows = []
    for name, pred in gates:
        if pred is None:
            s1 = summarize(oracle_1cpd, T15, n_days)
            sg = summarize(oracle_gap, T15, n_days)
            rows.append({"name": name + " [peek]", "1cpd": s1, "gap15": sg, "peek": True})
            continue
        c1 = first_per_day(pool, pred)
        cg = gap_book(pool, pred, GAP)
        rows.append(
            {
                "name": name,
                "1cpd": summarize(c1, T15, n_days),
                "gap15": summarize(cg, T15, n_days),
                "peek": False,
            }
        )
        print(
            f"  {name}: 1cpd hit={rows[-1]['1cpd']['hit']}% n={rows[-1]['1cpd']['n']} | "
            f"gap hit={rows[-1]['gap15']['hit']}% n={rows[-1]['gap15']['n']}",
            flush=True,
        )

    # Also T12 for Oracle comparison
    oracle12_1 = first_per_day(pool, lambda e: e.get("_w12"))
    s_or12 = summarize(oracle12_1, T12, n_days)
    s_or15 = summarize(oracle_1cpd, T15, n_days)

    # Feature lift: P(win|feat) vs baseline among HELD
    held_pool = [e for e in pool if e.get("held")]
    base_hit = 100.0 * sum(1 for e in held_pool if e.get("_w15")) / len(held_pool) if held_pool else 0

    def cond_hit(pred):
        sub = [e for e in held_pool if pred(e)]
        if len(sub) < 20:
            return len(sub), None, None
        hit = 100.0 * sum(1 for e in sub if e.get("_w15")) / len(sub)
        return len(sub), round(hit, 2), round(hit - base_hit, 2)

    lifts = []
    for label, pred in [
        ("not_extreme", lambda e: e.get("not_extreme")),
        ("INTO extreme (bad)", lambda e: e.get("into_sess_extreme")),
        ("!ext_1atr", lambda e: not e.get("into_ext_1atr")),
        ("clear_path", lambda e: e.get("room_ok")),
        ("ad_with", lambda e: e.get("ad_with")),
        ("ctrl", lambda e: e.get("ctrl")),
        ("di8", lambda e: e.get("di8")),
        ("not_extreme+clear", lambda e: e.get("not_extreme") and e.get("room_ok")),
        ("not_extreme+clear+AD", lambda e: e.get("not_extreme") and e.get("room_ok") and e.get("ad_with")),
        ("not_extreme+clear+ctrl", lambda e: e.get("not_extreme") and e.get("room_ok") and e.get("ctrl")),
    ]:
        n, hit, lift = cond_hit(pred)
        lifts.append({"label": label, "n": n, "hit": hit, "lift": lift})

    # Sort blind gates by 1cpd hit
    blind = [r for r in rows if not r["peek"] and r["1cpd"]["n"] >= 8]
    blind.sort(key=lambda r: (-(r["1cpd"]["hit"] or 0), -(r["1cpd"]["cover"] or 0)))

    lines = [
        "# NIFTY 1m — Oracle T15 + EMA34 trail · accuracy research",
        "",
        "> **RESEARCH ONLY — not changing Scalper live Setup A/B.**",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days} sessions) · session 09:30–14:30 · exit **EMA34 trail strict**.",
        "",
        "## 1) What is “Not into session extreme”?",
        "",
        "On each bar we track **today’s session high / low so far** (only bars before entry).",
        "",
        "```",
        "near_sess_high = distance to session high ≤ max(8 pts, 1×ATR)",
        "near_sess_low  = distance to session low  ≤ max(8 pts, 1×ATR)",
        "",
        "into_sess_extreme =",
        "  BUY  when price is already near the session HIGH  (buying the top)",
        "  SELL when price is already near the session LOW   (selling the bottom)",
        "",
        "not_extreme = NOT into_sess_extreme",
        "```",
        "",
        "Why it matters: chasing the day’s high/low often means **no room left** for T15 before "
        "EMA34 flips. Skipping those is a simple anti-chase rule.",
        "",
        f"Among all sess textbook events this window: T15 path-wins **{len(wins15)}** / losses **{len(loss15)}**.",
        f"- `into_sess_extreme` on **wins**: {ext_on_wins} ({round(100*ext_on_wins/max(len(wins15),1),1)}%)",
        f"- `into_sess_extreme` on **losses**: {ext_on_loss} ({round(100*ext_on_loss/max(len(loss15),1),1)}%)",
        "",
        "## 2) Oracle T15 · EMA34 trail (the logic you like)",
        "",
        "Oracle = take textbook events that **already path-win** T15 under EMA34 trail "
        "(hindsight). Scalper chart marks those. High hit% is expected because losers are hidden.",
        "",
        "| Book | T1 | n | Hit% | Cover | avg pts |",
        "|---|---:|---:|---:|---:|---:|",
        f"| Oracle 1/day | 15 | {s_or15['n']} | **{s_or15['hit']}** | {s_or15['cover']} | {s_or15['avg_pts']} |",
        f"| Oracle 1/day | 12 | {s_or12['n']} | **{s_or12['hit']}** | {s_or12['cover']} | {s_or12['avg_pts']} |",
        f"| Oracle gap15 | 15 | {summarize(oracle_gap, T15, n_days)['n']} | "
        f"**{summarize(oracle_gap, T15, n_days)['hit']}** | "
        f"{summarize(oracle_gap, T15, n_days)['cover']} | "
        f"{summarize(oracle_gap, T15, n_days)['avg_pts']} |",
        "",
        "Fails still happen on Oracle gap books if a later ‘would-be win’ is taken after a "
        "winner that then… wait — Oracle only selects `_win` events, so **hit is ~100% by construction** "
        "on pure oracle picks. Chart ‘fails’ you see are usually **non-oracle / Setup** calls, or "
        "trail path that looked good then stopped (if mixed modes).",
        "",
        "## 3) Using Oracle *style* for more accuracy (blind filters + T15 trail)",
        "",
        "We keep **same exit** (EMA34 trail · T15) and test **entry filters** without peeking.",
        "Ranked by 1-call/day hit% (n≥8):",
        "",
        "| Gate (blind) | 1cpd Hit% | n | cover | gap15 Hit% | n |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in blind[:18]:
        a, b = r["1cpd"], r["gap15"]
        lines.append(
            f"| `{r['name']}` | **{a['hit']}** | {a['n']} | {a['cover']}% | {b['hit']} | {b['n']} |"
        )

    lines += [
        "",
        "### Feature lift on HELD pool (T15 trail hit)",
        "",
        f"HELD baseline T15 hit (all HELD bars, not 1/day): **{round(base_hit, 2)}%** n={len(held_pool)}",
        "",
        "| Condition | n | T15 hit% | lift vs HELD |",
        "|---|---:|---:|---:|",
    ]
    for x in lifts:
        lines.append(f"| `{x['label']}` | {x['n']} | {x['hit']} | {x['lift']} |")

    # Recommendation block
    top = blind[0] if blind else None
    lines += [
        "",
        "## 4) Research conclusion (not live yet)",
        "",
        "**Keep loving Oracle T15 + EMA34 trail** as the quality ceiling / chart teacher.",
        "",
        "To get **more accuracy in a usable book** (no peek):",
        "",
        "1. Same exit: **T1=15 · EMA34 trail strict**",
        "2. Entry base: **HELD** (DI ∧ hard34 ∧ VWAP)",
        "3. Add **`not_extreme`** — skip buy-high / sell-low vs session",
        "4. Prefer **clear_path** (room ≥ 1.5×ATR) so T15 has space",
        "5. Optional: **AD_with** or **control** bar for extra lift",
        "",
    ]
    if top:
        lines.append(
            f"Best blind 1cpd on this window: **`{top['name']}`** → "
            f"Hit **{top['1cpd']['hit']}%** · n={top['1cpd']['n']} · cover {top['1cpd']['cover']}%."
        )
    lines += [
        "",
        "Oracle stays the high-success **reference**. Blind filters above are how we "
        "approximate it for live later — **this script does not wire Scalper.**",
        "",
        f"Elapsed {time.time() - t0:.0f}s",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "oracle15_1cpd": s_or15,
                "oracle12_1cpd": s_or12,
                "blind": rows,
                "lifts": lifts,
                "extreme_on_wins": ext_on_wins,
                "extreme_on_loss": ext_on_loss,
                "window": [day_lo, day_hi],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {REPORT}", flush=True)
    if top:
        print(f"BEST blind: {top['name']} hit={top['1cpd']['hit']} n={top['1cpd']['n']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
