"""Why blind DEEP fails + walk-forward 100% path logic using patterns 2021→today.

Method:
1) Explain blind OOS collapse (SL-first, key collision, regime shift)
2) Build yearly event cache 2021→2026
3) Walk-forward: lock zero-loss micros on all years < Y, score year Y (true unknown)
4) Multi-year ACC100 intersection (historical 100% only — not future proof alone)
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

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
import research_nifty_1m_vix_candle_adaptive as vixmod  # noqa: E402
import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import (  # noqa: E402
    PACK as PACK_T20,
    SL10_STYLES,
    SL_MAX,
    T1,
    enrich_prior3,
    flag_sl10,
    path_ok_sl10,
)
from _diag_scalp_held_pre3_densify_1cpd import eval_book, stats  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import (  # noqa: E402
    enrich_deep,
    keys_deep,
    index_by_key,
    cell_clean,
    greedy_1cpd,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_wf100_2021"
REPORT_MD = OUT / "NIFTY_1M_SCALP_WHY_BLIND_FAIL_WF100_2021.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_WHY_BLIND_FAIL_WF100_2021.json"
BLIND_PKL = PACK_T20 / "DEEP_BLIND_2024_2025_micros.pkl"
GAP = 1
YEARS = [2021, 2022, 2023, 2024, 2025, 2026]


def year_bounds(y: int, data_hi: str):
    lo = f"{y}-01-01"
    hi = f"{y}-12-31"
    if y == 2026:
        hi = min(hi, data_hi)
    return lo, hi


def ensure_year_events(df, data_hi: str):
    PACK.mkdir(parents=True, exist_ok=True)
    by_year = {}
    for y in YEARS:
        lo, hi = year_bounds(y, data_hi)
        cache = PACK / f"events_{lo}_{hi}.pkl"
        if cache.exists():
            xs = pickle.load(cache.open("rb"))
            print(f"  cache {y}: {len(xs)}", flush=True)
        else:
            print(f"  collect {y} {lo}→{hi}…", flush=True)
            xs = scalp.collect_scalp_events(df, lo, hi)
            pickle.dump(xs, cache.open("wb"), protocol=pickle.HIGHEST_PROTOCOL)
            print(f"    n={len(xs)}", flush=True)
        for e in xs:
            e["_year"] = y
        by_year[y] = xs
    return by_year


def enrich_all(by_year, h, l, c, o, vix, df):
    for y, xs in by_year.items():
        fwdmod.enrich_evt(xs, h, l, c, o)
        enrich_structure(xs, h, l, c, o, vix)
        enrich_prior3(xs, h, l, c, o)
        flag_sl10(xs, h, l, c)
        enrich_deep(xs, h, l, c, o, df)
        for e in xs:
            e["_keys"] = set(keys_deep(e))
        print(f"  enriched {y}={len(xs)}", flush=True)


def diagnose_blind_failures(by_year, h, l, c):
    """Compare blind book wins vs losses on 2026."""
    if not BLIND_PKL.exists():
        return {"error": "blind pkl missing"}
    micros = pickle.loads(BLIND_PKL.read_bytes())
    unk = by_year[2026]
    calls = eval_book(unk, micros, keys_deep, h, l, c, GAP)
    wins = [e for e in calls if e["_win"]]
    loss = [e for e in calls if not e["_win"]]

    def rate(xs, fn):
        return round(100.0 * sum(1 for e in xs if fn(e)) / max(len(xs), 1), 1)

    def top(xs, key, n=6):
        return Counter(e.get(key) for e in xs).most_common(n)

    diag = {
        "n": len(calls),
        "n_win": len(wins),
        "n_loss": len(loss),
        "hit": round(100.0 * len(wins) / max(len(calls), 1), 2),
        "loss_mfe_ge20": sum(1 for e in loss if e.get("mfe", 0) >= T1),
        "loss_mfe_ge20_pct": rate(loss, lambda e: e.get("mfe", 0) >= T1),
        "avg_mae_win": round(sum(e["mae"] for e in wins) / max(len(wins), 1), 2),
        "avg_mae_loss": round(sum(e["mae"] for e in loss) / max(len(loss), 1), 2),
        "avg_mfe_win": round(sum(e["mfe"] for e in wins) / max(len(wins), 1), 2),
        "avg_mfe_loss": round(sum(e["mfe"] for e in loss) / max(len(loss), 1), 2),
        "fail_signals": sorted(
            [
                {"f": "NOT close_ok", "L": rate(loss, lambda e: e.get("close_ok") != 1), "W": rate(wins, lambda e: e.get("close_ok") != 1)},
                {"f": "adv_hi", "L": rate(loss, lambda e: e.get("adv_bin") == "adv_hi"), "W": rate(wins, lambda e: e.get("adv_bin") == "adv_hi")},
                {"f": "pre3_opp>=2", "L": rate(loss, lambda e: (e.get("pre3_opp") or 0) >= 2), "W": rate(wins, lambda e: (e.get("pre3_opp") or 0) >= 2)},
                {"f": "vix_LOW", "L": rate(loss, lambda e: e.get("vix_regime") == "LOW"), "W": rate(wins, lambda e: e.get("vix_regime") == "LOW")},
                {"f": "hm09", "L": rate(loss, lambda e: e.get("hm_bin") == "09"), "W": rate(wins, lambda e: e.get("hm_bin") == "09")},
                {"f": "day_mid", "L": rate(loss, lambda e: e.get("day_pos_bin") == "mid"), "W": rate(wins, lambda e: e.get("day_pos_bin") == "mid")},
            ],
            key=lambda r: -(r["L"] - r["W"]),
        ),
        "loss_primary": top(loss, "primary"),
        "win_primary": top(wins, "primary"),
        "loss_pre3_UD": top(loss, "pre3_UD"),
        "loss_vix": top(loss, "vix_regime"),
        "why": [
            "Train-locked fingerprints are rare geometries that were path-perfect in 2024-25 only.",
            "On 2026 the same fingerprint reappears in a different tape; SL often prints first even when MFE later ≥20.",
            "Fine keys overfit local history → high in-sample 100%, weak blind OOS.",
            "Peeked DEEP looked 100% on 2026 because 2026 was used in the lock filter (not unknown).",
        ],
    }
    for r in diag["fail_signals"]:
        r["delta"] = round(r["L"] - r["W"], 1)
    return diag


def build_zero_loss_from_years(train_years, by_year, min_train_n=2, min_years_present=1):
    """Zero-loss cells across all train years; require enough fires."""
    buckets = {y: index_by_key(by_year[y], keys_deep) for y in train_years}
    cand = set()
    for y in train_years:
        for (k, st), rows in buckets[y].items():
            if any(ok for _, ok, _ in rows):
                cand.add((k, st))

    cells = []
    for k, st in cand:
        year_ev = {}
        ok_all = True
        total = 0
        years_hit = 0
        for y in train_years:
            ok, n, ev = cell_clean(buckets[y], k, st)
            if not ok:
                ok_all = False
                break
            year_ev[y] = ev
            total += n
            if n > 0:
                years_hit += 1
        if not ok_all:
            continue
        if total < min_train_n or years_hit < min_years_present:
            continue
        # flatten for greedy
        all_ev = []
        for y in train_years:
            for e in year_ev[y]:
                e[f"_ok_{st}"] = True
                e[f"_sl_{st}"] = e[f"_sl10_{st}"]
                e["_sl"] = e[f"_sl10_{st}"]
                e["_win"] = True
                e["_era_tag"] = "cal" if y == train_years[0] else "l3m"
                all_ev.append(e)
        # split first half years as cal, rest l3m for greedy mins
        mid = max(1, len(train_years) // 2)
        cal_ys = train_years[:mid]
        l3m_ys = train_years[mid:] or train_years[-1:]
        cal_calls = [e for y in cal_ys for e in year_ev[y]]
        l3m_calls = [e for y in l3m_ys for e in year_ev[y]]
        if len(cal_calls) < 1:
            cal_calls = all_ev[:1]
            l3m_calls = all_ev[1:] or all_ev[:1]
        cells.append(
            {
                "k": k,
                "st": st,
                "cal_calls": cal_calls,
                "l3m_calls": l3m_calls,
                "hold_calls": [],
                "fwd_calls": [],
                "cal_n": len(cal_calls),
                "l3m_n": len(l3m_calls),
                "hold_n": 0,
                "fwd_n": 0,
                "total_n": total,
                "years_hit": years_hit,
                "days": {e["day"] for e in all_ev},
                "avg_sl": sum(e[f"_sl10_{st}"] for e in all_ev) / max(total, 1),
            }
        )
    cells.sort(key=lambda r: (-r["years_hit"], -r["total_n"], r["avg_sl"]))
    return cells


def one_per_day(calls, n_days):
    first = {}
    for e in sorted(calls, key=lambda x: (x["day"], x["mins"])):
        first.setdefault(e["day"], e)
    ones = list(first.values())
    if not ones:
        return {"n": 0, "hit": 0.0, "cover": 0.0, "all_win": True}
    w = sum(1 for e in ones if e["_win"])
    return {
        "n": len(ones),
        "hit": round(100.0 * w / len(ones), 2),
        "cover": round(100.0 * len(ones) / max(n_days, 1), 1),
        "all_win": all(e["_win"] for e in ones),
    }


def main() -> int:
    print("=" * 60, flush=True)
    print("Why blind fails + WF100 from 2021→today", flush=True)
    print("=" * 60, flush=True)
    PACK.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    raw = base.load_existing_1m()
    data_hi = raw.index.max().strftime("%Y-%m-%d")
    print(f"bars {raw.index.min()} → {raw.index.max()}", flush=True)

    # Need history from 2021
    raw = raw[raw.index >= pd.Timestamp("2021-01-01", tz="Asia/Kolkata")]
    print("[1] textbook+rsi (2021→now)…", flush=True)
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    vix = vixmod.load_vix()

    print("[2] yearly events…", flush=True)
    by_year = ensure_year_events(df, data_hi)
    print("[3] enrich…", flush=True)
    enrich_all(by_year, h, l, c, o, vix, df)

    print("[4] why blind failed on 2026…", flush=True)
    why = diagnose_blind_failures(by_year, h, l, c)
    print(
        f"  blind 2026 hit={why.get('hit')}% n={why.get('n')} "
        f"loss_MFE>=20={why.get('loss_mfe_ge20')}/{why.get('n_loss')} ({why.get('loss_mfe_ge20_pct')}%)",
        flush=True,
    )
    print(f"  fail_signals={why.get('fail_signals', [])[:4]}", flush=True)

    # Walk-forward
    print("[5] walk-forward yearly (train all prior years → test Y)…", flush=True)
    wf = {}
    for test_y in [2023, 2024, 2025, 2026]:
        train_ys = [y for y in YEARS if y < test_y]
        print(f"\n  ### WF test={test_y} train={train_ys}", flush=True)
        cells = build_zero_loss_from_years(train_ys, by_year, min_train_n=2, min_years_present=min(2, len(train_ys)))
        print(f"    zero-loss cells={len(cells)}", flush=True)
        # denser variant: min 1 year present
        cells1 = build_zero_loss_from_years(train_ys, by_year, min_train_n=2, min_years_present=1)
        chosen, _ = greedy_1cpd(cells1, gap=GAP)
        print(f"    book micros={len(chosen)}", flush=True)
        test = by_year[test_y]
        nd = len({e["day"] for e in test})
        calls = eval_book(test, chosen, keys_deep, h, l, c, GAP)
        st = stats(calls, nd)
        one = one_per_day(calls, nd)
        print(
            f"    OOS full {st['n']}@{st['hit']}% all_win={st['all_win']} · "
            f"1/day {one['n']} cover={one['cover']}% hit={one['hit']}%",
            flush=True,
        )
        # strict multi-year-present book
        chosen_s, _ = greedy_1cpd(cells, gap=GAP)
        calls_s = eval_book(test, chosen_s, keys_deep, h, l, c, GAP)
        st_s = stats(calls_s, nd)
        one_s = one_per_day(calls_s, nd)
        print(
            f"    STRICT full {st_s['n']}@{st_s['hit']}% · 1/day {one_s['n']} cover={one_s['cover']}% hit={one_s['hit']}%",
            flush=True,
        )
        wf[test_y] = {
            "train_years": train_ys,
            "dense": {"n_micros": len(chosen), "full": st, "one": one},
            "strict": {"n_micros": len(chosen_s), "full": st_s, "one": one_s},
        }
        (PACK / f"WF_before_{test_y}_dense_micros.pkl").write_bytes(
            pickle.dumps([{"k": r["k"], "st": r["st"]} for r in chosen], protocol=pickle.HIGHEST_PROTOCOL)
        )
        (PACK / f"WF_before_{test_y}_strict_micros.pkl").write_bytes(
            pickle.dumps([{"k": r["k"], "st": r["st"]} for r in chosen_s], protocol=pickle.HIGHEST_PROTOCOL)
        )

    # Multi-year intersection: 100% on EVERY year 2021-2026 (historical accurate atlas)
    print("\n[6] multi-year ACC100 atlas (all years 100% — historical)…", flush=True)
    cells_all = build_zero_loss_from_years(YEARS, by_year, min_train_n=3, min_years_present=4)
    # require actually present in >=4 years with zero losses everywhere (already)
    chosen_all, _ = greedy_1cpd(cells_all, gap=GAP)
    atlas = {}
    for y in YEARS:
        xs = by_year[y]
        nd = len({e["day"] for e in xs})
        calls = eval_book(xs, chosen_all, keys_deep, h, l, c, GAP)
        st = stats(calls, nd)
        one = one_per_day(calls, nd)
        atlas[y] = {"full": st, "one": one, "n_days": nd}
        print(
            f"  ATLAS {y}: full {st['n']}@{st['hit']}% all_win={st['all_win']} · "
            f"1/day {one['n']} cover={one['cover']}%",
            flush=True,
        )
    (PACK / "ACC100_MULTIYEAR_ATLAS_micros.pkl").write_bytes(
        pickle.dumps([{"k": r["k"], "st": r["st"]} for r in chosen_all], protocol=pickle.HIGHEST_PROTOCOL)
    )

    # Stronger atlas: present every year 2021-2026
    cells_every = build_zero_loss_from_years(YEARS, by_year, min_train_n=6, min_years_present=6)
    chosen_every, _ = greedy_1cpd(cells_every, gap=GAP)
    atlas_every = {}
    for y in YEARS:
        xs = by_year[y]
        nd = len({e["day"] for e in xs})
        calls = eval_book(xs, chosen_every, keys_deep, h, l, c, GAP)
        st = stats(calls, nd)
        one = one_per_day(calls, nd)
        atlas_every[y] = {"full": st, "one": one}
        print(
            f"  EVERY-YEAR {y}: full {st['n']}@{st['hit']}% · 1/day {one['n']} cover={one['cover']}%",
            flush=True,
        )
    (PACK / "ACC100_EVERY_YEAR_micros.pkl").write_bytes(
        pickle.dumps([{"k": r["k"], "st": r["st"]} for r in chosen_every], protocol=pickle.HIGHEST_PROTOCOL)
    )

    results = {
        "constraints": {"t1": T1, "sl_max": SL_MAX, "gap": GAP},
        "data_hi": data_hi,
        "why_blind": why,
        "walk_forward": wf,
        "atlas_min4y": {"n_micros": len(chosen_all), "by_year": atlas},
        "atlas_every_year": {"n_micros": len(chosen_every), "by_year": atlas_every},
        "elapsed_s": round(time.time() - t0, 1),
    }

    lines = [
        "# Why blind DEEP failed + **walk-forward 100%** study (2021→today)",
        "",
        f"Data: **2021-01-01 → {data_hi}** · T1={T1} · SL≤{SL_MAX} · path win = target before SL",
        "",
        "## Why ~30% on unknown 2026 (not bad luck)",
        "",
    ]
    if "error" not in why:
        lines += [
            f"- Blind book on 2026: **{why['n']}** calls @ **{why['hit']}%**",
            f"- Losses with MFE≥20 (SL-first): **{why['loss_mfe_ge20']}/{why['n_loss']} ({why['loss_mfe_ge20_pct']}%)**",
            f"- MAE win/loss: {why['avg_mae_win']} / {why['avg_mae_loss']} · MFE win/loss: {why['avg_mfe_win']} / {why['avg_mfe_loss']}",
            "",
            "### Failure feature tilt (loss% − win%)",
            "",
            "| Feature | Loss% | Win% | Δ |",
            "|---|---:|---:|---:|",
        ]
        for r in why["fail_signals"]:
            lines.append(f"| {r['f']} | {r['L']} | {r['W']} | {r['delta']} |")
        lines += [
            "",
            f"- Loss patterns: `{why['loss_primary']}`",
            f"- Loss prior3: `{why['loss_pre3_UD']}`",
            f"- Loss VIX: `{why['loss_vix']}`",
            "",
            "### Root causes",
            "",
        ]
        for w in why["why"]:
            lines.append(f"- {w}")

    lines += [
        "",
        "## Walk-forward proof (only honest unknown test)",
        "",
        "Each row: micros locked on **all prior years only**, then scored on test year.",
        "",
        "| Test year | Train | Dense micros | OOS hit% | OOS n | 1/day hit% | 1/day cover | Strict hit% | Strict n |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for y, row in wf.items():
        d, s = row["dense"], row["strict"]
        lines.append(
            f"| {y} | {row['train_years']} | {d['n_micros']} | {d['full']['hit']}% | {d['full']['n']} | "
            f"{d['one']['hit']}% | {d['one']['cover']}% | {s['full']['hit']}% | {s['full']['n']} |"
        )

    lines += [
        "",
        "## Historical ACC100 atlases (100% on included years — not a future guarantee)",
        "",
        f"- **ACC100_MULTIYEAR_ATLAS** (≥4 years present, zero losses all years): {len(chosen_all)} micros",
        f"- **ACC100_EVERY_YEAR** (present every year 2021–2026): {len(chosen_every)} micros",
        "",
        "| Year | Atlas full n@hit | Atlas 1/day cover | Every-year full n@hit | Every-year 1/day cover |",
        "|---:|---|---:|---|---:|",
    ]
    for y in YEARS:
        a, e = atlas[y], atlas_every[y]
        lines.append(
            f"| {y} | {a['full']['n']}@{a['full']['hit']}% | {a['one']['cover']}% | "
            f"{e['full']['n']}@{e['full']['hit']}% | {e['one']['cover']}% |"
        )

    lines += [
        "",
        "## What “most accurate 100% logic” can honestly be",
        "",
        "1. **Walk-forward OOS** rarely stays 100% at high volume under T20/SL≤10 — that is the real bar.",
        "2. **Multi-year atlas / every-year** books are the safest *historical* 100% sets (few calls).",
        "3. Peeking the test year (old DEEP_1CPD) invents fake 100% — do not deploy as proof.",
        "4. Next accuracy gains: stricter fingerprints that survive WF, or relax T1/SL only if needed for coverage.",
        "",
        f"Pack: `{PACK}`",
        f"Elapsed: {results['elapsed_s']}s",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {REPORT_MD}", flush=True)
    print("DONE why-blind + WF100 2021", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
