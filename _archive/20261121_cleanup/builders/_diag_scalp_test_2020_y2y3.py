"""Blind OOS: DENSE_Y2 / DENSE_Y3 (trained 2021→2026) on full year 2020.

Downloads NIFTY 1m for 2020 if missing, builds events, evaluates path T1=20 / SL<=10.
"""
from __future__ import annotations

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
import research_nifty_1m_vix_candle_adaptive as vixmod  # noqa: E402
import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod  # noqa: E402
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import enrich_prior3, flag_sl10, T1, SL_MAX, SL10_STYLES  # noqa: E402
from _diag_scalp_held_pre3_densify_1cpd import eval_book, stats  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402
from _diag_scalp_atlas_densify_100 import keys_combined  # noqa: E402

PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_wf100_2021"
LEDGER = ROOT / "stock_signal_data" / "fno_validate" / "research"
CACHE_2020 = LEDGER / "_cache_nifty_1m_2020.parquet"
EV_CACHE = PACK / "events_2020-01-01_2020-12-31.pkl"
OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SCALP_DENSE_Y2Y3_2020.md"
GAP = 1
YEAR_LO = "2020-01-01"
YEAR_HI = "2020-12-31"


def ensure_2020_bars() -> pd.DataFrame:
    if CACHE_2020.is_file():
        df = base._norm(pd.read_parquet(CACHE_2020))
        print(f"  cache 2020: {len(df)} bars {df.index.min()} → {df.index.max()}", flush=True)
        return df
    print("  downloading NIFTY 1m 2020 via Kite…", flush=True)
    fresh, note = base.download_1m_range(YEAR_LO, YEAR_HI)
    if note:
        print(f"  download note: {note}", flush=True)
    if fresh is None or len(fresh) == 0:
        raise RuntimeError(f"no 2020 bars downloaded: {note}")
    fresh = fresh[(fresh.index >= pd.Timestamp(YEAR_LO, tz="Asia/Kolkata")) & (fresh.index <= pd.Timestamp(YEAR_HI + " 23:59:59", tz="Asia/Kolkata"))]
    LEDGER.mkdir(parents=True, exist_ok=True)
    fresh.to_parquet(CACHE_2020)
    print(f"  wrote {CACHE_2020} bars={len(fresh)}", flush=True)
    return fresh


def month_table(calls, days):
    by_m = defaultdict(list)
    for e in calls:
        by_m[e["day"][:7]].append(e)
    months = sorted({d[:7] for d in days})
    rows = []
    for m in months:
        xs = by_m.get(m, [])
        mdays = [d for d in days if d.startswith(m)]
        if not xs:
            rows.append((m, 0, 0.0, 0, len(mdays), 0.0, 0.0))
            continue
        w = sum(1 for e in xs if e["_win"])
        hit = round(100.0 * w / len(xs), 2)
        cd = len({e["day"] for e in xs})
        cover = round(100.0 * cd / max(len(mdays), 1), 1)
        avg_sl = round(sum(e["_sl"] for e in xs) / len(xs), 2)
        rows.append((m, len(xs), hit, cd, len(mdays), cover, avg_sl))
    return rows


def main() -> int:
    t0 = time.time()
    y2 = pickle.loads((PACK / "DENSE_Y2_micros.pkl").read_bytes())
    y3 = pickle.loads((PACK / "DENSE_Y3_micros.pkl").read_bytes())
    print(f"Y2 micros={len(y2)} Y3 micros={len(y3)} T1={T1} SL_MAX={SL_MAX}", flush=True)

    raw = ensure_2020_bars()
    print(f"2020 bars={len(raw)} {raw.index.min()} → {raw.index.max()}", flush=True)

    print("[1] textbook + RSI…", flush=True)
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    vix = vixmod.load_vix()

    PACK.mkdir(parents=True, exist_ok=True)
    if EV_CACHE.exists():
        xs = pickle.load(EV_CACHE.open("rb"))
        print(f"[2] events cache: {len(xs)}", flush=True)
    else:
        print(f"[2] collect events {YEAR_LO}→{YEAR_HI}…", flush=True)
        xs = scalp.collect_scalp_events(df, YEAR_LO, YEAR_HI)
        pickle.dump(xs, EV_CACHE.open("wb"), protocol=pickle.HIGHEST_PROTOCOL)
        print(f"    n={len(xs)} wrote {EV_CACHE.name}", flush=True)

    print("[3] enrich…", flush=True)
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    flag_sl10(xs, h, l, c)
    enrich_deep(xs, h, l, c, o, df)
    for e in xs:
        e["_keys"] = set(keys_combined(e))
        e["_year"] = 2020

    days = sorted({e["day"] for e in xs})
    print(f"2020 events={len(xs)} trading_days={len(days)}", flush=True)

    lines = [
        "# DENSE_Y2 / DENSE_Y3 — **full year 2020** (blind OOS)",
        "",
        "Train lock was **2021→2026**. 2020 was **never** used to pick micros → true unknown year.",
        "",
        f"Data: `{raw.index.min()}` → `{raw.index.max()}` · bars **{len(raw)}** · events **{len(xs)}** · days **{len(days)}**",
        f"Rules: T1=**{T1}** · SL≤**{SL_MAX}** · path (T1 before structure SL) · gap={GAP}m",
        f"SL styles: `{', '.join(SL10_STYLES)}`",
        "",
        "## Exact logic (both books — same engine)",
        "",
        "1. **Signal**: textbook candle pattern completes on 1m (bull → BUY, bear → SELL) in session window ~09:20–15:00.",
        "2. **Fingerprint**: each bar gets deep+A keys (pattern, side, prior-3 shape, structure, VIX regime, RSI/body/clock bins).",
        "3. **Micro book**: a micro is one locked fingerprint `k` + one SL style `st` that was **100% path-clean** on enough train years (Y2 ≥2 years, Y3 ≥3 years) with SL in 4…10.",
        "4. **Call**: first matching micro on that bar; SL from that style; **win only if T1=20 hits before SL**.",
        "5. **Dense difference only**: Y2 keeps more micros (looser year count) → more calls; Y3 is stricter → fewer/safer historically.",
        "",
        "| Book | Micros | How built | Intent |",
        "|---|---:|---|---|",
        "| **DENSE_Y3** | 246 | clean fingerprint cells seen in **≥3** train years, never dirty | fewer calls, higher bar |",
        "| **DENSE_Y2** | 1001 | same cells but **≥2** train years | denser cover (~1.7 cpd on 21–26) |",
        "",
        "| Book | Calls | Hit% | all_win | Days w/ call | Cover | Avg SL | 1/day n | 1/day hit |",
        "|---|---:|---:|:---:|---:|---:|---:|---:|---:|",
    ]

    for name, micros in [("DENSE_Y3", y3), ("DENSE_Y2", y2)]:
        calls = eval_book(xs, micros, keys_combined, h, l, c, GAP)
        nd = len(days)
        st = stats(calls, nd)
        first = {}
        for e in sorted(calls, key=lambda x: (x["day"], x["mins"])):
            first.setdefault(e["day"], e)
        ones = list(first.values())
        one_hit = round(100.0 * sum(e["_win"] for e in ones) / max(len(ones), 1), 2) if ones else 0.0
        cover = round(100.0 * st["days"] / max(nd, 1), 1)
        print(f"==== {name} ====", flush=True)
        print(
            f"full n={st['n']} hit={st['hit']}% all_win={st['all_win']} "
            f"days={st['days']}/{nd} cover={cover}% avg_sl={st['avg_sl']}",
            flush=True,
        )
        print(f"1/day n={len(ones)} hit={one_hit}%", flush=True)

        lines.append(
            f"| **{name}** | {st['n']} | {st['hit']}% | {st['all_win']} | {st['days']} | "
            f"{cover}% | {st['avg_sl']} | {len(ones)} | {one_hit}% |"
        )

        # month rollup
        lines.append("")
        lines.append(f"### {name} by month")
        lines.append("")
        lines.append("| Month | Calls | Hit% | Days hit | Days | Cover | Avg SL |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for m, n, hit, cd, md, cov, avg_sl in month_table(calls, days):
            print(f"  {m} n={n} hit={hit}% days={cd}/{md} cover={cov}%", flush=True)
            lines.append(f"| {m} | {n} | {hit}% | {cd} | {md} | {cov}% | {avg_sl} |")

        # top patterns / losses
        wins = [e for e in calls if e["_win"]]
        loss = [e for e in calls if not e["_win"]]
        top_p = Counter(e.get("primary") for e in calls).most_common(8)
        top_st = Counter(e.get("_st") for e in calls).most_common(8)
        lines.append("")
        lines.append(f"### {name} mix")
        lines.append("")
        lines.append(f"- Wins **{len(wins)}** · Losses **{len(loss)}**")
        lines.append(f"- Top patterns: {', '.join(f'{p}×{n}' for p,n in top_p)}")
        lines.append(f"- Top SL styles: {', '.join(f'{p}×{n}' for p,n in top_st)}")
        if loss:
            lines.append("")
            lines.append(f"#### {name} sample losses (first 25)")
            lines.append("")
            lines.append("| Day | HM | Side | Pattern | SL style | SL | MFE |")
            lines.append("|---|---|---|---|---|---:|---:|")
            for e in sorted(loss, key=lambda x: (x["day"], x["mins"]))[:25]:
                lines.append(
                    f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
                    f"{e['_st']} | {e['_sl']:.1f} | {e.get('mfe', 0):.1f} |"
                )
                print(
                    f"  LOSS {e['day']} {e['hm']} {e['decision']} {e['primary']} "
                    f"{e['_st']} sl={e['_sl']:.1f} mfe={e.get('mfe', 0):.1f}",
                    flush=True,
                )
        lines.append("")

    lines += [
        "## Simple read",
        "",
        "- Same **call engine** for Y2 and Y3; only the **micro list size/strictness** differs.",
        "- 2020 is **pre-train** → hit% here is the real generalization check (COVID year, high VIX).",
        "- If hit% collapses vs 2021–26 lock, fingerprints overfit that era; denser Y2 usually drops more than Y3.",
        "",
        f"Elapsed: {time.time()-t0:.1f}s",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
