"""RESEARCH ONLY — catch major moves that Oracle T15 clean (TierAB) misses.

Major = trail MFE ≥ 40 under EMA34 trail (primary), plus impulse ≥40pts/≥4 bars tag.
Find complementary blind gates that recover missed majors without flooding.

  python -u prod_live/tests/builders/_diag_scalp_oracle_major_move_catch.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
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
from _diag_scalp_impulse_green_run_entry import find_impulse_runs  # noqa: E402

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ORACLE_MAJOR_MOVE_CATCH.md"
REPORT_JSON = OUT / "NIFTY_1M_ORACLE_MAJOR_MOVE_CATCH.json"

T15, T20 = 15.0, 20.0
MAJOR_MFE = 40.0
GAP = 15
MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
MIN_RECOVER = 0.40
MIN_BLIND_HIT = 58.0
MIN_BLIND_N = 25
MIN_MAJOR_PREC = 45.0


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
        e["_major"] = bool(mfe >= MAJOR_MFE)


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


def event_key(e: dict) -> Tuple:
    return (e.get("day"), int(e.get("mins") or 0), e.get("decision"), int(e.get("full_i") or -1))


def feat_rate(rows: List[dict], key: str) -> Optional[float]:
    if not rows:
        return None
    return round(100.0 * sum(1 for e in rows if e.get(key)) / len(rows), 1)


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("Oracle major-move catch research (RESEARCH ONLY)", flush=True)

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

    o = df["Open"].astype(float).values
    c_arr = df["Close"].astype(float).values
    ad_r = df["ad_rising"].astype(bool).values if "ad_rising" in df.columns else np.zeros(len(df), dtype=bool)
    ad_f = df["ad_falling"].astype(bool).values if "ad_falling" in df.columns else np.zeros(len(df), dtype=bool)

    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        e["ad_with"] = (side == "BUY" and bool(ad_r[i])) or (side == "SELL" and bool(ad_f[i]))
        e["not_extreme"] = not bool(e.get("into_sess_extreme"))
        e["held"] = held_gate(e)
        e["sess"] = bool(in_session(e)) and MINS_LO <= int(e["mins"]) <= MINS_HI
        e["room_ok"] = bool(e.get("clear_path"))
        e["ctrl"] = bool(e.get("control_with"))
        e["tier_ab"] = bool(e.get("setup_ok"))
        e["hold_break"] = e.get("regime") == "hold_break" or bool(e.get("hold_break_setup"))
        e["bounce"] = bool(e.get("sr_bounce"))
        e["runway2"] = bool(e.get("runway_2atr"))
        # prev opposite color
        if i > 0:
            prev_green = c_arr[i - 1] > o[i - 1]
            prev_red = c_arr[i - 1] < o[i - 1]
            e["prev_opposite"] = (side == "BUY" and prev_red) or (side == "SELL" and prev_green)
        else:
            e["prev_opposite"] = False

    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    score_trail(events, h, l, c, ema34, T15)
    score_trail(events, h, l, c, ema34, T20)
    score_mfe(events, h, l, c, ema34)

    pool = [e for e in events if e["day"] in keep and e["sess"]]
    majors_all = [e for e in pool if e.get("_major")]
    oracle = [e for e in pool if e.get("_w15")]
    # Primary: great moves inside Oracle T15 (path-win + MFE≥40) — what clean should catch
    majors = [e for e in oracle if e.get("_major")]
    clean = [e for e in oracle if e.get("tier_ab")]
    clean_keys = {event_key(e) for e in clean}
    oracle_keys = {event_key(e) for e in oracle}
    tier_keys = {event_key(e) for e in pool if e.get("tier_ab")}

    # Impulse runs in window
    runs = find_impulse_runs(df)
    runs = [r for r in runs if r["day"] in keep and MINS_LO <= int(r["mins"]) <= MINS_HI]
    impulse_i = {(r["day"], int(r["mins"]), r["decision"]) for r in runs}
    for e in pool:
        e["_impulse"] = (e.get("day"), int(e.get("mins") or 0), e.get("decision")) in impulse_i

    def covered(maj_list, keys):
        hit = [e for e in maj_list if event_key(e) in keys]
        return hit, pct(len(hit), len(maj_list))

    maj_oracle, cov_oracle = covered(majors, oracle_keys)
    maj_clean, cov_clean = covered(majors, clean_keys)
    maj_tier, cov_tier = covered(majors, tier_keys)
    missed = [e for e in majors if event_key(e) not in clean_keys]
    _, cov_clean_all = covered(majors_all, clean_keys)
    impulse_events = [e for e in pool if e.get("_impulse")]
    _, cov_clean_imp = covered(impulse_events, clean_keys)

    print(
        f"pool={len(pool)} majors_all={len(majors_all)} oracle_majors={len(majors)} "
        f"oracle={len(oracle)} clean={len(clean)} missed={len(missed)} "
        f"impulses={len(runs)} cov_clean={cov_clean}% "
        f"cov_clean_all={cov_clean_all}% cov_clean_imp={cov_clean_imp}%",
        flush=True,
    )

    miss_autopsy = {
        "n": len(missed),
        "held": feat_rate(missed, "held"),
        "ad_with": feat_rate(missed, "ad_with"),
        "clear_path": feat_rate(missed, "room_ok"),
        "runway_2atr": feat_rate(missed, "runway2"),
        "hold_break": feat_rate(missed, "hold_break"),
        "bounce": feat_rate(missed, "bounce"),
        "ctrl": feat_rate(missed, "ctrl"),
        "into_extreme": feat_rate(missed, "into_sess_extreme"),
        "prev_opposite": feat_rate(missed, "prev_opposite"),
        "impulse": feat_rate(missed, "_impulse"),
        "avg_mfe": round(float(np.mean([e["_mfe"] for e in missed])), 2) if missed else None,
        "patterns": Counter(str(e.get("primary") or "?") for e in missed).most_common(12),
    }

    Gate = Tuple[str, Callable[[dict], bool]]
    gates: List[Gate] = [
        ("HELD + clear_path", lambda e: e.get("held") and e.get("room_ok")),
        ("HELD + runway_2ATR", lambda e: e.get("held") and e.get("runway2")),
        ("HELD + hold_break + runway_2ATR", lambda e: e.get("held") and e.get("hold_break") and e.get("runway2")),
        ("HELD + AD + clear_path", lambda e: e.get("held") and e.get("ad_with") and e.get("room_ok")),
        ("HELD + AD + runway_2ATR", lambda e: e.get("held") and e.get("ad_with") and e.get("runway2")),
        (
            "PROVEN3: hold_break|bounce + ctrl + runway2",
            lambda e: e.get("held")
            and e.get("ctrl")
            and e.get("runway2")
            and (e.get("hold_break") or e.get("bounce")),
        ),
        (
            "Impulse-pre: prev_opp + clear + AD",
            lambda e: e.get("prev_opposite") and e.get("room_ok") and e.get("ad_with"),
        ),
        (
            "Impulse-pre + HELD",
            lambda e: e.get("held") and e.get("prev_opposite") and e.get("room_ok") and e.get("ad_with"),
        ),
        ("HELD + clear + runway_2ATR", lambda e: e.get("held") and e.get("room_ok") and e.get("runway2")),
        (
            "HELD + AD + clear + !extreme",
            lambda e: e.get("held") and e.get("ad_with") and e.get("room_ok") and e.get("not_extreme"),
        ),
        ("TierAB + clear_path", lambda e: e.get("tier_ab") and e.get("room_ok")),
        ("TierAB + runway_2ATR", lambda e: e.get("tier_ab") and e.get("runway2")),
        (
            "clear + runway2 + AD (no HELD)",
            lambda e: e.get("room_ok") and e.get("runway2") and e.get("ad_with"),
        ),
        (
            "prev_opp + clear + runway2",
            lambda e: e.get("prev_opposite") and e.get("room_ok") and e.get("runway2"),
        ),
        # Gates that can fire without TierAB / strict HELD (miss autopsy often non-held)
        ("AD + clear_path", lambda e: e.get("ad_with") and e.get("room_ok")),
        ("AD + runway_2ATR", lambda e: e.get("ad_with") and e.get("runway2")),
        ("clear_path + runway_2ATR", lambda e: e.get("room_ok") and e.get("runway2")),
        (
            "AD + clear + runway2",
            lambda e: e.get("ad_with") and e.get("room_ok") and e.get("runway2"),
        ),
        (
            "ctrl + runway2 + clear",
            lambda e: e.get("ctrl") and e.get("runway2") and e.get("room_ok"),
        ),
        (
            "Oracle-major proxy: AD + ctrl + runway2",
            lambda e: e.get("ad_with") and e.get("ctrl") and e.get("runway2"),
        ),
        (
            "into_extreme + AD + runway2",
            lambda e: e.get("into_sess_extreme") and e.get("ad_with") and e.get("runway2"),
        ),
    ]

    gate_rows: List[Dict[str, Any]] = []
    for name, pred in gates:
        # Recovered missed majors (any matching event, not gap-spaced)
        recovered = [e for e in missed if pred(e)]
        recover_pct = pct(len(recovered), len(missed)) if missed else None
        # Blind gap15 book on full pool
        book = gap_book(pool, pred, GAP)
        n = len(book)
        t15_w = sum(1 for e in book if e.get("_w15"))
        major_n = sum(1 for e in book if e.get("_major"))
        mfes = [float(e.get("_mfe") or 0) for e in book]
        row = {
            "name": name,
            "recovered_n": len(recovered),
            "recover_pct": recover_pct,
            "gap_n": n,
            "gap_cpd": round(n / n_days, 2) if n_days else 0.0,
            "t15_hit": pct(t15_w, n),
            "major_prec": pct(major_n, n),
            "avg_mfe": round(float(np.mean(mfes)), 2) if mfes else None,
            "major_n": major_n,
        }
        gate_rows.append(row)
        print(
            f"  {name}: recover={recover_pct}% ({len(recovered)}/{len(missed)}) "
            f"gap n={n} t15={row['t15_hit']}% majPrec={row['major_prec']}%",
            flush=True,
        )

    # Winner selection
    # Strict: recover ≥40% of clean-missed Oracle-majors (hard when TierAB is sparse).
    candidates = []
    for r in gate_rows:
        if (r.get("recover_pct") or 0) < MIN_RECOVER * 100:
            continue
        t15_ok = (r.get("gap_n") or 0) >= MIN_BLIND_N and (r.get("t15_hit") or 0) >= MIN_BLIND_HIT
        prec_ok = (r.get("major_prec") or 0) >= MIN_MAJOR_PREC
        if not (t15_ok or prec_ok):
            continue
        candidates.append(r)

    def cand_key(r):
        # Prefer recover + major precision + T15 hit; then fewer calls
        return (
            -(r.get("recover_pct") or 0),
            -(r.get("major_prec") or 0),
            -(r.get("t15_hit") or 0),
            (r.get("gap_n") or 0),
        )

    candidates.sort(key=cand_key)
    winner = candidates[0] if candidates else None
    if winner is None:
        # Practical fallback: accurate blind books (T15≥58%, n≥25), max recover of missed majors.
        # Full 40% recover is often unreachable because clean/TierAB is very sparse.
        soft = [
            r
            for r in gate_rows
            if (r.get("gap_n") or 0) >= MIN_BLIND_N
            and (r.get("t15_hit") or 0) >= MIN_BLIND_HIT
        ]

        def soft_key(r):
            # Most accurate major-catcher: precision + T15 hit first, then recover
            score = (
                (r.get("major_prec") or 0)
                + 0.5 * (r.get("t15_hit") or 0)
                + 0.25 * (r.get("recover_pct") or 0)
            )
            return (-score, r.get("gap_n") or 0)

        soft.sort(key=soft_key)
        winner = soft[0] if soft else None
        if winner:
            winner = {
                **winner,
                "note": (
                    "best accurate complementary gate (T15≥58%, n≥25; ranked by "
                    "major_prec + T15 hit + recover) — no gate recovered ≥40% of "
                    "clean-missed Oracle-majors (TierAB is sparse vs MFE≥40 Oracle set)"
                ),
            }

    # Union: clean ∪ winner gate, gap15 dedupe
    def union_pred(e, gate_pred):
        return bool(e.get("_w15") and e.get("tier_ab")) or gate_pred(e)

    union_stats = None
    clean_gap = gap_book(pool, lambda e: e.get("_w15") and e.get("tier_ab"), GAP)
    if winner:
        wpred = next(p for n, p in gates if n == winner["name"])
        union_book = gap_book(pool, lambda e, p=wpred: union_pred(e, p), GAP)
        # Also: oracle-clean peek union for chart-shaped book
        clean_peek_gap = gap_book(oracle, lambda e: e.get("tier_ab"), GAP)
        union_peek = gap_book(
            pool,
            lambda e, p=wpred: (e.get("_w15") and e.get("tier_ab")) or p(e),
            GAP,
        )

        def book_stats(book, label):
            keys = {event_key(e) for e in book}
            maj_hit = [e for e in majors if event_key(e) in keys]
            miss_hit = [e for e in missed if event_key(e) in keys]
            t15_w = sum(1 for e in book if e.get("_w15"))
            return {
                "label": label,
                "n": len(book),
                "cpd": round(len(book) / n_days, 2) if n_days else 0.0,
                "t15_hit": pct(t15_w, len(book)),
                "majors_caught": len(maj_hit),
                "majors_cov": pct(len(maj_hit), len(majors)),
                "missed_recovered": len(miss_hit),
                "miss_recover_pct": pct(len(miss_hit), len(missed)) if missed else None,
                "avg_mfe": round(float(np.mean([float(e.get("_mfe") or 0) for e in book])), 2)
                if book
                else None,
                "major_prec": pct(sum(1 for e in book if e.get("_major")), len(book)),
            }

        union_stats = {
            "clean_gap": book_stats(clean_gap, "oracle_t15_clean gap15"),
            "major_gate_gap": book_stats(gap_book(pool, wpred, GAP), winner["name"]),
            "union_gap": book_stats(union_book, f"clean ∪ {winner['name']}"),
            "clean_peek_gap": book_stats(clean_peek_gap, "clean peek gap15"),
            "union_peek_gap": book_stats(union_peek, f"clean peek ∪ {winner['name']}"),
        }

    # Sample missed majors
    missed_sample = sorted(missed, key=lambda e: -float(e.get("_mfe") or 0))[:25]
    sample_rows = [
        {
            "day": e["day"],
            "hm": e.get("hm"),
            "side": e["decision"],
            "mfe": e.get("_mfe"),
            "pattern": e.get("primary"),
            "held": bool(e.get("held")),
            "ad": bool(e.get("ad_with")),
            "clear": bool(e.get("room_ok")),
            "runway2": bool(e.get("runway2")),
            "hold_break": bool(e.get("hold_break")),
            "impulse": bool(e.get("_impulse")),
        }
        for e in missed_sample
    ]

    payload = {
        "ok": True,
        "research_only": True,
        "window": {"day_lo": day_lo, "day_hi": day_hi, "n_days": n_days},
        "major_def": {
            "primary": "oracle_t15_pathwin_and_trail_mfe_ge_40",
            "trail_mfe_ge": MAJOR_MFE,
            "impulse_pts": 40,
            "impulse_bars": 4,
        },
        "counts": {
            "pool": len(pool),
            "majors_all_pool": len(majors_all),
            "majors_oracle_mfe40": len(majors),
            "oracle_t15": len(oracle),
            "clean": len(clean),
            "missed": len(missed),
            "impulses": len(runs),
        },
        "coverage": {
            "oracle_t15": cov_oracle,
            "oracle_t15_clean": cov_clean,
            "tier_ab": cov_tier,
            "clean_vs_all_pool_majors": cov_clean_all,
            "clean_vs_impulse": cov_clean_imp,
            "n_oracle": len(maj_oracle),
            "n_clean": len(maj_clean),
            "n_tier": len(maj_tier),
        },
        "miss_autopsy": miss_autopsy,
        "gates": gate_rows,
        "winner": winner,
        "union": union_stats,
        "missed_sample": sample_rows,
        "rules": {
            "min_recover_pct": MIN_RECOVER * 100,
            "min_blind_hit": MIN_BLIND_HIT,
            "min_blind_n": MIN_BLIND_N,
            "min_major_prec": MIN_MAJOR_PREC,
        },
        "took_sec": round(time.time() - t0, 1),
    }

    lines = [
        "# NIFTY 1m — Oracle T15 clean · **major-move catch**",
        "",
        "> **RESEARCH ONLY — not changing Scalper live / UI.**",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days} sessions) · 09:30–14:30 · EMA34 trail.",
        "",
        f"**Primary major** = Oracle T15 path-win **and** trail MFE ≥ **{MAJOR_MFE:.0f}**. "
        "Impulse ≥40pts/≥4 bars is a secondary tag. Pool-wide MFE≥40 shown for context only.",
        "",
        "## 1) Coverage vs Oracle T15 clean",
        "",
        "| Book | Count | Coverage of Oracle-majors |",
        "|---|---:|---:|",
        f"| Oracle-majors (T15 win ∩ MFE≥40) | {len(majors)} | 100% |",
        f"| Oracle T15 raw (all path-wins) | {len(oracle)} | {cov_oracle}% of Oracle-majors |",
        f"| **Oracle T15 clean (TierAB)** | {len(maj_clean)} | **{cov_clean}%** |",
        f"| Setup TierAB alone | {len(maj_tier)} | {cov_tier}% |",
        f"| **Missed by clean** | {len(missed)} | {pct(len(missed), len(majors))}% |",
        f"| All pool MFE≥40 (context) | {len(majors_all)} | clean covers {cov_clean_all}% |",
        f"| Impulse runs | {len(runs)} | clean covers {cov_clean_imp}% of impulse bars |",
        "",
        "## 2) Missed Oracle-major autopsy (features at entry)",
        "",
        f"n={miss_autopsy['n']} · avg MFE={miss_autopsy['avg_mfe']}",
        "",
        "| Feature | % true on missed Oracle-majors |",
        "|---|---:|",
        f"| held | {miss_autopsy['held']} |",
        f"| ad_with | {miss_autopsy['ad_with']} |",
        f"| clear_path | {miss_autopsy['clear_path']} |",
        f"| runway_2atr | {miss_autopsy['runway_2atr']} |",
        f"| hold_break | {miss_autopsy['hold_break']} |",
        f"| bounce | {miss_autopsy['bounce']} |",
        f"| control | {miss_autopsy['ctrl']} |",
        f"| into_extreme | {miss_autopsy['into_extreme']} |",
        f"| prev_opposite | {miss_autopsy['prev_opposite']} |",
        f"| impulse tag | {miss_autopsy['impulse']} |",
        "",
        "Top patterns on missed Oracle-majors:",
        "",
        "| Pattern | n |",
        "|---|---:|",
    ]
    for pat, n in miss_autopsy["patterns"]:
        lines.append(f"| `{pat}` | {n} |")

    lines += [
        "",
        "## 3) Complementary gate grid (blind)",
        "",
        "Recover% = share of **clean-missed Oracle-majors** that match the gate. "
        "gap15 = deployable multi-call book on full pool. Major prec = share of gap calls with MFE≥40.",
        "",
        "| Gate | Recover% | n rec | gap n | cpd | T15 hit% | Major prec% | avg MFE |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in sorted(gate_rows, key=lambda x: (-(x.get("recover_pct") or 0), -(x.get("major_prec") or 0))):
        lines.append(
            f"| `{r['name']}` | {r['recover_pct']} | {r['recovered_n']} | {r['gap_n']} | "
            f"{r['gap_cpd']} | {r['t15_hit']} | {r['major_prec']} | {r['avg_mfe']} |"
        )

    lines += [
        "",
        "## 4) Winner",
        "",
        f"Rules: recover ≥{MIN_RECOVER*100:.0f}% of clean-missed majors; "
        f"and (gap15 T15 hit ≥{MIN_BLIND_HIT:.0f}% with n≥{MIN_BLIND_N} **or** major prec ≥{MIN_MAJOR_PREC:.0f}%).",
        "",
    ]
    if winner:
        lines += [
            f"**Recommended major gate:** `{winner['name']}`",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Recovered missed majors | {winner['recovered_n']} ({winner['recover_pct']}%) |",
            f"| Gap15 calls | {winner['gap_n']} |",
            f"| T15 hit% | {winner['t15_hit']} |",
            f"| Major precision | {winner['major_prec']}% |",
            f"| Avg MFE | {winner['avg_mfe']} |",
        ]
        if winner.get("note"):
            lines += ["", f"Note: {winner['note']}"]
    else:
        lines.append("**No gate met the winner rules** on this window.")

    if union_stats:
        lines += [
            "",
            "## 5) Union book: clean ∪ major gate",
            "",
            "| Book | n | cpd | T15 hit% | Majors cov% | Miss recovered% | Major prec% | avg MFE |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for key in ("clean_gap", "major_gate_gap", "union_gap", "clean_peek_gap", "union_peek_gap"):
            b = union_stats[key]
            lines.append(
                f"| `{b['label']}` | {b['n']} | {b['cpd']} | {b['t15_hit']} | "
                f"{b['majors_cov']} | {b['miss_recover_pct']} | {b['major_prec']} | {b['avg_mfe']} |"
            )
        lines += [
            "",
            "**Ship later (not this run):** Scalper mode `oracle_t15_clean_major` = "
            f"`oracle_t15_clean` ∪ `{winner['name'] if winner else 'TBD'}` (gap15 dedupe).",
        ]

    lines += [
        "",
        "## 6) Sample missed majors (highest MFE)",
        "",
        "| Day | HM | Side | MFE | Pattern | held | AD | clear | runway2 | hold_break | impulse |",
        "|---|---|---|---:|---|---|---|---|---|---|---|",
    ]
    for s in sample_rows:
        lines.append(
            f"| {s['day']} | {s['hm']} | {s['side']} | {s['mfe']} | `{s['pattern']}` | "
            f"{s['held']} | {s['ad']} | {s['clear']} | {s['runway2']} | {s['hold_break']} | {s['impulse']} |"
        )

    lines += [
        "",
        "## 7) Takeaway",
        "",
        "- Oracle T15 clean stays the **accurate core** (Tier A/B ∩ path-win).",
        "- Major moves often ignite **without** Tier A/B — need a complementary runway/clear/impulse-pre gate.",
        "- Union only if the major gate recovers enough misses without collapsing T15 hit / flooding calls.",
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
            f"WINNER {winner['name']} recover={winner['recover_pct']}% "
            f"t15={winner['t15_hit']}% majPrec={winner['major_prec']}%",
            flush=True,
        )
    else:
        print("NO WINNER under rules", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
