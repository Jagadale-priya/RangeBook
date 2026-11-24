"""RESEARCH ONLY — Oracle T15 clean + higher-target filter analysis.

Same textbook entry + EMA34 trail as Scalper Oracle T15.
Goal: find proven gates that remove unnecessary calls and keep higher-target quality (T20/T25).

  python -u prod_live/tests/builders/_diag_scalp_oracle_t15_clean_hightarget.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
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

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ORACLE_T15_CLEAN_HIGHTARGET.md"
REPORT_JSON = OUT / "NIFTY_1M_ORACLE_T15_CLEAN_HIGHTARGET.json"

T15, T20, T25 = 15.0, 20.0, 25.0
GAP = 15
MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
MIN_CUT = 0.30  # ≥30% call volume cut vs Oracle gap15
MIN_BLIND_HIT = 60.0
MIN_BLIND_N = 30


def score_trail(events, h, l, c, ema34, t1: float) -> None:
    key = f"_w{int(t1)}"
    for e in events:
        ok, reason, sl, t1v = path_ma_trail_strict(
            h, l, c, ema34, int(e["full_i"]), e["decision"], float(t1)
        )
        e[key] = bool(ok)
        e[f"_r{int(t1)}"] = reason
        e[f"_pts{int(t1)}"] = float(t1v if ok else -(abs(sl) if sl else 0))


def score_mfe(events, h, l, c, ema34, max_bars: int = 120) -> None:
    """Max favorable excursion under EMA34 trail (same stop logic, no T1)."""
    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        entry = float(c[i])
        end = min(len(c) - 1, i + max_bars)
        mfe = 0.0
        for j in range(i + 1, end + 1):
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
        e["_mfe"] = round(float(mfe), 2)


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


def pct(n: int, d: int) -> Optional[float]:
    if d <= 0:
        return None
    return round(100.0 * n / d, 2)


def oracle_quality(calls: List[dict], n_days: int) -> Dict[str, Any]:
    """Among Oracle-T15 survivors: density + higher-target shares."""
    n = len(calls)
    if not n:
        return {
            "n": 0,
            "cpd": 0.0,
            "t20_share": None,
            "t25_share": None,
            "avg_mfe": None,
            "days": 0,
        }
    n20 = sum(1 for e in calls if e.get("_w20"))
    n25 = sum(1 for e in calls if e.get("_w25"))
    days = len({e["day"] for e in calls})
    mfes = [float(e.get("_mfe") or 0) for e in calls]
    return {
        "n": n,
        "cpd": round(n / n_days, 2) if n_days else 0.0,
        "t20_share": pct(n20, n),
        "t25_share": pct(n25, n),
        "avg_mfe": round(float(np.mean(mfes)), 2),
        "days": days,
        "n20": n20,
        "n25": n25,
    }


def blind_t15(calls: List[dict], n_days: int) -> Dict[str, Any]:
    n = len(calls)
    if not n:
        return {"n": 0, "hit": None, "cpd": 0.0, "avg_pts": None}
    w = sum(1 for e in calls if e.get("_w15"))
    pts = [float(e.get("_pts15") or 0) for e in calls]
    return {
        "n": n,
        "hit": pct(w, n),
        "cpd": round(n / n_days, 2) if n_days else 0.0,
        "avg_pts": round(float(np.mean(pts)), 2),
        "w": w,
        "l": n - w,
    }


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("Oracle T15 clean + high-target filter analysis (RESEARCH ONLY)", flush=True)

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

    events = scalp.collect_scalp_events(df, str(df.index.min().date()), str(df.index.max().date()))
    enrich_ma_layers(events, df)
    enrich_ind(events, df)
    setup.apply_setup_enrichment(events, df)
    enrich_sr_archetypes(events, df)

    ad_r = df["ad_rising"].astype(bool).values
    ad_f = df["ad_falling"].astype(bool).values
    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        e["ad_with"] = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))
        e["not_extreme"] = not bool(e.get("into_sess_extreme"))
        e["held"] = held_gate(e)
        e["sess"] = bool(in_session(e)) and MINS_LO <= int(e["mins"]) <= MINS_HI
        e["room_ok"] = bool(e.get("clear_path"))
        e["ctrl"] = bool(e.get("control_with"))
        e["tier_a"] = e.get("setup_tier") == "A"
        e["tier_ab"] = bool(e.get("setup_ok"))

    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    score_trail(events, h, l, c, ema34, T15)
    score_trail(events, h, l, c, ema34, T20)
    score_trail(events, h, l, c, ema34, T25)
    score_mfe(events, h, l, c, ema34)

    pool = [e for e in events if e["day"] in keep and e["sess"]]
    oracle_all = [e for e in pool if e.get("_w15")]
    oracle_gap = gap_book(pool, lambda e: e.get("_w15"), GAP)
    base_q = oracle_quality(oracle_gap, n_days)
    print(
        f"pool={len(pool)} oracle_t15_all={len(oracle_all)} "
        f"oracle_gap15={base_q['n']} t20%={base_q['t20_share']} t25%={base_q['t25_share']}",
        flush=True,
    )

    # Gates applied ON TOP of Oracle T15 path-wins (peek clean) + same gates as blind filters
    Gate = Tuple[str, Callable[[dict], bool]]
    clean_gates: List[Gate] = [
        ("Oracle T15 raw (gap15)", lambda e: True),
        ("+ HELD", lambda e: e.get("held")),
        ("+ AD_with", lambda e: e.get("ad_with")),
        ("+ ctrl", lambda e: e.get("ctrl")),
        ("+ !extreme", lambda e: e.get("not_extreme")),
        ("+ clear_path", lambda e: e.get("room_ok")),
        ("+ TierAB", lambda e: e.get("tier_ab")),
        ("+ TierA", lambda e: e.get("tier_a")),
        ("+ HELD + AD", lambda e: e.get("held") and e.get("ad_with")),
        ("+ HELD + !extreme", lambda e: e.get("held") and e.get("not_extreme")),
        ("+ HELD + AD + !extreme", lambda e: e.get("held") and e.get("ad_with") and e.get("not_extreme")),
        ("+ HELD + AD + ctrl", lambda e: e.get("held") and e.get("ad_with") and e.get("ctrl")),
        ("+ HELD + AD + !extreme + ctrl", lambda e: e.get("held") and e.get("ad_with") and e.get("not_extreme") and e.get("ctrl")),
        ("+ HELD + clear", lambda e: e.get("held") and e.get("room_ok")),
        ("+ HELD + !extreme + clear", lambda e: e.get("held") and e.get("not_extreme") and e.get("room_ok")),
        ("+ HELD + AD + clear", lambda e: e.get("held") and e.get("ad_with") and e.get("room_ok")),
        ("+ HELD + AD + !extreme + clear", lambda e: e.get("held") and e.get("ad_with") and e.get("not_extreme") and e.get("room_ok")),
        ("+ TierAB + !extreme", lambda e: e.get("tier_ab") and e.get("not_extreme")),
        ("+ TierAB + AD", lambda e: e.get("tier_ab") and e.get("ad_with")),
        ("+ TierA + AD", lambda e: e.get("tier_a") and e.get("ad_with")),
        ("+ into_extreme + AD", lambda e: e.get("into_sess_extreme") and e.get("ad_with")),
        ("+ HELD + into_extreme + AD", lambda e: e.get("held") and e.get("into_sess_extreme") and e.get("ad_with")),
    ]

    clean_rows: List[Dict[str, Any]] = []
    for name, pred in clean_gates:
        # Filter oracle gap book (same spacing as Scalper multi-call)
        calls = [e for e in oracle_gap if pred(e)]
        # Also rebuild gap on oracle_all ∩ gate for fair density after filter
        calls_re = gap_book(oracle_all, pred, GAP)
        q = oracle_quality(calls_re, n_days)
        cut = None
        if base_q["n"]:
            cut = round(100.0 * (1.0 - q["n"] / base_q["n"]), 2)
        t20_lift = None
        if base_q["t20_share"] is not None and q["t20_share"] is not None:
            t20_lift = round(q["t20_share"] - base_q["t20_share"], 2)
        t25_lift = None
        if base_q["t25_share"] is not None and q["t25_share"] is not None:
            t25_lift = round(q["t25_share"] - base_q["t25_share"], 2)
        row = {
            "name": name,
            "peek": True,
            "n": q["n"],
            "cpd": q["cpd"],
            "cut_pct": cut if name != "Oracle T15 raw (gap15)" else 0.0,
            "t20_share": q["t20_share"],
            "t25_share": q["t25_share"],
            "t20_lift": t20_lift if name != "Oracle T15 raw (gap15)" else 0.0,
            "t25_lift": t25_lift if name != "Oracle T15 raw (gap15)" else 0.0,
            "avg_mfe": q["avg_mfe"],
            "days": q["days"],
            "subset_of_gap": len(calls),
        }
        clean_rows.append(row)
        print(
            f"  clean {name}: n={q['n']} cut={row['cut_pct']}% "
            f"t20={q['t20_share']}% t25={q['t25_share']}% mfe={q['avg_mfe']}",
            flush=True,
        )

    # Blind gates on full pool (deployable — no peek at _w15)
    blind_gates: List[Gate] = [
        ("ALL textbook sess", lambda e: True),
        ("HELD", lambda e: e.get("held")),
        ("HELD + AD", lambda e: e.get("held") and e.get("ad_with")),
        ("HELD + !extreme", lambda e: e.get("held") and e.get("not_extreme")),
        ("HELD + AD + !extreme", lambda e: e.get("held") and e.get("ad_with") and e.get("not_extreme")),
        ("HELD + AD + ctrl", lambda e: e.get("held") and e.get("ad_with") and e.get("ctrl")),
        ("HELD + AD + !extreme + ctrl", lambda e: e.get("held") and e.get("ad_with") and e.get("not_extreme") and e.get("ctrl")),
        ("HELD + clear", lambda e: e.get("held") and e.get("room_ok")),
        ("HELD + !extreme + clear", lambda e: e.get("held") and e.get("not_extreme") and e.get("room_ok")),
        ("HELD + AD + clear", lambda e: e.get("held") and e.get("ad_with") and e.get("room_ok")),
        ("HELD + AD + !extreme + clear", lambda e: e.get("held") and e.get("ad_with") and e.get("not_extreme") and e.get("room_ok")),
        ("TierAB", lambda e: e.get("tier_ab")),
        ("TierA", lambda e: e.get("tier_a")),
        ("TierAB + !extreme", lambda e: e.get("tier_ab") and e.get("not_extreme")),
        ("TierAB + AD", lambda e: e.get("tier_ab") and e.get("ad_with")),
        ("TierA + AD", lambda e: e.get("tier_a") and e.get("ad_with")),
        ("HELD + into_extreme + AD", lambda e: e.get("held") and e.get("into_sess_extreme") and e.get("ad_with")),
    ]

    blind_rows: List[Dict[str, Any]] = []
    for name, pred in blind_gates:
        cg = gap_book(pool, pred, GAP)
        c1 = first_per_day(pool, pred)
        sg = blind_t15(cg, n_days)
        s1 = blind_t15(c1, n_days)
        # Among blind gap calls that DID win T15: higher-target share
        winners = [e for e in cg if e.get("_w15")]
        q_w = oracle_quality(winners, n_days) if winners else oracle_quality([], n_days)
        blind_rows.append(
            {
                "name": name,
                "gap15": sg,
                "1cpd": s1,
                "among_t15_wins": {
                    "n": q_w["n"],
                    "t20_share": q_w["t20_share"],
                    "t25_share": q_w["t25_share"],
                    "avg_mfe": q_w["avg_mfe"],
                },
            }
        )
        print(
            f"  blind {name}: gap hit={sg['hit']}% n={sg['n']} | "
            f"1cpd hit={s1['hit']}% n={s1['n']} | "
            f"winT20%={q_w['t20_share']}",
            flush=True,
        )

    # Winner selection (plan rule)
    # Prefer clean (peek-on-oracle) gates that cut ≥30%, T20 share ≥ baseline, …
    # For deployable recommendation, also require blind gap15 hit ≥60% n≥30.
    candidates = []
    for r in clean_rows:
        if r["name"] == "Oracle T15 raw (gap15)":
            continue
        cut = r.get("cut_pct")
        if cut is None or cut < MIN_CUT * 100:
            continue
        if r.get("t20_share") is None or base_q["t20_share"] is None:
            continue
        if r["t20_share"] < base_q["t20_share"]:
            continue
        # Match blind gate by stripping "+ " prefix mapping
        blind_name = r["name"][2:] if r["name"].startswith("+ ") else r["name"]
        # Map clean names to blind names
        name_map = {
            "HELD": "HELD",
            "AD_with": None,
            "ctrl": None,
            "!extreme": None,
            "clear_path": None,
            "TierAB": "TierAB",
            "TierA": "TierA",
            "HELD + AD": "HELD + AD",
            "HELD + !extreme": "HELD + !extreme",
            "HELD + AD + !extreme": "HELD + AD + !extreme",
            "HELD + AD + ctrl": "HELD + AD + ctrl",
            "HELD + AD + !extreme + ctrl": "HELD + AD + !extreme + ctrl",
            "HELD + clear": "HELD + clear",
            "HELD + !extreme + clear": "HELD + !extreme + clear",
            "HELD + AD + clear": "HELD + AD + clear",
            "HELD + AD + !extreme + clear": "HELD + AD + !extreme + clear",
            "TierAB + !extreme": "TierAB + !extreme",
            "TierAB + AD": "TierAB + AD",
            "TierA + AD": "TierA + AD",
            "into_extreme + AD": None,
            "HELD + into_extreme + AD": "HELD + into_extreme + AD",
        }
        bn = name_map.get(blind_name)
        blind_hit = None
        blind_n = 0
        if bn:
            br = next((x for x in blind_rows if x["name"] == bn), None)
            if br:
                blind_hit = br["gap15"]["hit"]
                blind_n = br["gap15"]["n"]
        # Soft: if blind exists, require ≥60% when n≥30; if no blind twin, still keep as peek-clean candidate
        if bn and blind_n >= MIN_BLIND_N and (blind_hit is None or blind_hit < MIN_BLIND_HIT):
            continue
        candidates.append(
            {
                **r,
                "blind_name": bn,
                "blind_gap_hit": blind_hit,
                "blind_gap_n": blind_n,
            }
        )

    def cand_key(x):
        return (
            -(x.get("t20_lift") or 0),
            -(x.get("t25_share") or 0),
            -(x.get("cut_pct") or 0),
            x.get("n") or 0,
        )

    candidates.sort(key=cand_key)
    winner = candidates[0] if candidates else None

    # Fallback: best clean gate by (t20_lift, cut) even if blind soft-fail — still report
    if winner is None:
        fallback = [
            r
            for r in clean_rows
            if r["name"] != "Oracle T15 raw (gap15)"
            and (r.get("cut_pct") or 0) >= MIN_CUT * 100
            and r.get("t20_share") is not None
            and base_q["t20_share"] is not None
            and r["t20_share"] >= base_q["t20_share"]
        ]
        fallback.sort(key=cand_key)
        winner = fallback[0] if fallback else None
        if winner:
            winner = {**winner, "note": "peek-clean only — no blind twin passed ≥60% gap15"}

    # Best blind by gap15 hit among n≥30, with T20 share among its T15 winners
    blind_ranked = [
        r
        for r in blind_rows
        if (r["gap15"]["n"] or 0) >= MIN_BLIND_N and r["gap15"]["hit"] is not None
    ]
    blind_ranked.sort(
        key=lambda r: (
            -(r["gap15"]["hit"] or 0),
            -(r["among_t15_wins"].get("t20_share") or 0),
            -(r["gap15"]["n"] or 0),
        )
    )
    best_blind = blind_ranked[0] if blind_ranked else None

    payload = {
        "ok": True,
        "research_only": True,
        "window": {"day_lo": day_lo, "day_hi": day_hi, "n_days": n_days},
        "oracle_baseline_gap15": base_q,
        "oracle_all_n": len(oracle_all),
        "clean_on_oracle": clean_rows,
        "blind_gates": blind_rows,
        "winner_clean": winner,
        "best_blind": best_blind,
        "rules": {
            "min_cut_pct": MIN_CUT * 100,
            "min_blind_hit": MIN_BLIND_HIT,
            "min_blind_n": MIN_BLIND_N,
            "gap_mins": GAP,
        },
        "took_sec": round(time.time() - t0, 1),
    }

    # Markdown
    lines = [
        "# NIFTY 1m — Oracle T15 · **clean filters + higher target**",
        "",
        "> **RESEARCH ONLY — not changing Scalper live Setup A/B.**",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days} sessions) · 09:30–14:30 · exit **EMA34 trail**.",
        "",
        "Same entry logic as Scalper **Oracle T15** (textbook path-wins). "
        "This report finds gates that **drop unnecessary calls** and keep / lift **T20–T25** path quality.",
        "",
        "## 1) Oracle baseline (gap15)",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Oracle T15 all path-wins | {len(oracle_all)} |",
        f"| Oracle gap15 calls | {base_q['n']} |",
        f"| Calls / day | {base_q['cpd']} |",
        f"| Also path-win T20 | {base_q['t20_share']}% |",
        f"| Also path-win T25 | {base_q['t25_share']}% |",
        f"| Avg MFE (trail) | {base_q['avg_mfe']} |",
        "",
        "## 2) Clean filters on Oracle T15 (peek — same entries, fewer calls)",
        "",
        "Applied on top of Oracle T15 path-wins, then re-spaced gap15.",
        "",
        "| Gate | n | cut% | cpd | T20% | T25% | ΔT20 | avg MFE |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in clean_rows:
        lines.append(
            f"| `{r['name']}` | {r['n']} | {r['cut_pct']} | {r['cpd']} | "
            f"{r['t20_share']} | {r['t25_share']} | {r['t20_lift']} | {r['avg_mfe']} |"
        )

    lines += [
        "",
        "## 3) Blind gates (deployable — no peek)",
        "",
        "Same EMA34 trail · T15 scored after the gate. Among T15 winners, report T20/T25 share.",
        "",
        "| Gate | gap15 Hit% | n | cpd | 1cpd Hit% | n | T20% of T15 wins | T25% | avg MFE |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in sorted(
        blind_rows,
        key=lambda x: (-(x["gap15"]["hit"] or 0), -(x["gap15"]["n"] or 0)),
    ):
        aw = r["among_t15_wins"]
        lines.append(
            f"| `{r['name']}` | {r['gap15']['hit']} | {r['gap15']['n']} | {r['gap15']['cpd']} | "
            f"{r['1cpd']['hit']} | {r['1cpd']['n']} | {aw['t20_share']} | {aw['t25_share']} | {aw['avg_mfe']} |"
        )

    lines += ["", "## 4) Winner (plan rules)", ""]
    lines.append(
        f"Rules: cut Oracle gap15 **≥{MIN_CUT*100:.0f}%**, T20 share **≥ baseline**, "
        f"blind gap15 hit **≥{MIN_BLIND_HIT:.0f}%** when n≥{MIN_BLIND_N} (if blind twin exists)."
    )
    lines.append("")
    if winner:
        lines += [
            f"**Recommended clean gate:** `{winner['name']}`",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Calls after clean | {winner['n']} |",
            f"| Cut vs Oracle gap15 | {winner.get('cut_pct')}% |",
            f"| T20 share | {winner.get('t20_share')}% |",
            f"| T25 share | {winner.get('t25_share')}% |",
            f"| ΔT20 vs baseline | {winner.get('t20_lift')} |",
            f"| Avg MFE | {winner.get('avg_mfe')} |",
        ]
        if winner.get("blind_name"):
            lines.append(f"| Blind twin | `{winner['blind_name']}` |")
            lines.append(f"| Blind gap15 hit | {winner.get('blind_gap_hit')}% (n={winner.get('blind_gap_n')}) |")
        if winner.get("note"):
            lines += ["", f"Note: {winner['note']}"]
        lines += [
            "",
            "**Ship later (not this run):** Scalper mode `oracle_t15_clean` = Oracle T15 path-wins "
            f"∩ `{winner['name']}` (or blind twin `{winner.get('blind_name')}` for live/deployable).",
        ]
    else:
        lines += [
            "**No gate met all plan rules** on this window.",
            "See tables above for nearest trade-offs (cut vs T20 lift vs blind hit).",
        ]

    if best_blind:
        lines += [
            "",
            "### Best blind (gap15 hit, n≥30)",
            "",
            f"- Gate: `{best_blind['name']}`",
            f"- gap15 Hit% **{best_blind['gap15']['hit']}** · n={best_blind['gap15']['n']} · cpd={best_blind['gap15']['cpd']}",
            f"- Among its T15 wins: T20 **{best_blind['among_t15_wins']['t20_share']}%** · "
            f"T25 **{best_blind['among_t15_wins']['t25_share']}%** · "
            f"avg MFE {best_blind['among_t15_wins']['avg_mfe']}",
        ]

    lines += [
        "",
        "## 5) Takeaway",
        "",
        "- Oracle T15 remains the **hindsight ceiling** (100% by selecting path-wins).",
        "- Cleaning = drop Oracle calls that lack structure (HELD / AD / Tier / extreme rules).",
        "- Higher target quality = among survivors, share that also path-win **T20/T25** under the same trail.",
        "- Do **not** change Setup A/B until a clean gate is wired as an explicit Scalper mode.",
        "",
        f"_Generated in {payload['took_sec']}s._",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    print(f"wrote {REPORT_JSON}", flush=True)
    if winner:
        print(
            f"WINNER {winner['name']} cut={winner.get('cut_pct')}% "
            f"t20={winner.get('t20_share')}% t25={winner.get('t25_share')}%",
            flush=True,
        )
    else:
        print("NO WINNER under strict rules", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
