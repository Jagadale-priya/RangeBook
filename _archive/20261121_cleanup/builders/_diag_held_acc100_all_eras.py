"""Find most accurate scalp micros: 100% path on EVERY era (2024, 2025, 2026, NovFWD).

Fast path: build cells from E2024 (100% + mins), then keep only those still 100%
on E2025 / E2026A / E2026B / FWD.
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import defaultdict
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
import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod  # noqa: E402
from _diag_held_why_drop_and_fix100 import build_cells, eval_micros_on_fwd  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_acc100_all"
REPORT_MD = OUT / "NIFTY_1M_SCALP_ACC100_ALL_ERAS.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_ACC100_ALL_ERAS.json"

ERAS = [
    ("E2024", "2024-01-02", "2024-12-31"),
    ("E2025", "2025-01-01", "2025-12-31"),
    ("E2026A", "2026-01-01", "2026-08-05"),
    ("E2026B", "2026-08-06", "2026-11-06"),
    ("FWD", "2026-11-09", "2026-11-16"),
]
HIST_LO = "2023-11-01"


def score_cell(events, k, st, gap, sl_max, h, l, c, t1):
    matched = []
    for e in events:
        if k not in e["_keys"]:
            continue
        sl = fwdmod.lesser(e, st)
        if not (4 <= sl <= sl_max):
            continue
        matched.append(e)
    matched = fwdmod.apply_gap(matched, gap)
    if not matched:
        return True, 0, []
    out = []
    for e in matched:
        ok, sl = fwdmod.path_ok(e, h, l, c, st, t1, sl_max=sl_max)
        if not ok:
            return False, len(matched), []
        out.append({**e, "_win": True, "_st": st, f"_sl_{st}": sl})
    return True, len(out), out


def greedy_book(cells, gap, min_era):
    used = set()
    chosen = []

    def take(calls):
        out, last = [], {}
        for e in sorted(calls, key=lambda x: (x["day"], x["mins"])):
            key = (e["day"], e["mins"])
            if key in used:
                continue
            if any(d == e["day"] and abs(m - e["mins"]) < gap for d, m in used):
                continue
            prev = last.get(e["day"])
            if prev is not None and e["mins"] - prev < gap:
                continue
            out.append(e)
            last[e["day"]] = e["mins"]
        return out

    for r in cells:
        pooled = []
        for xs in r["era_calls"].values():
            pooled.extend(xs)
        kept = take(pooled)
        by_era = defaultdict(list)
        for e in kept:
            by_era[e["_era"]].append(e)
        if any(len(by_era.get(era, [])) < need for era, need in min_era.items()):
            continue
        chosen.append({**r, "kept": kept, "era_n_kept": {e: len(by_era.get(e, [])) for e in min_era}})
        for e in kept:
            used.add((e["day"], e["mins"]))
    return chosen


def main() -> int:
    print("=" * 60, flush=True)
    print("Hunt ACC100 across ALL eras (fast cell filter)", flush=True)
    print("=" * 60, flush=True)
    PACK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    raw = base.load_existing_1m()
    today = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
    eras = []
    for name, lo, hi in ERAS:
        hi2 = hi if name != "FWD" else min(hi, today, raw.index.max().strftime("%Y-%m-%d"))
        eras.append((name, lo, hi2))

    raw = raw[raw.index >= pd.Timestamp(HIST_LO, tz="Asia/Kolkata")]
    print(f"bars={len(raw)} → {raw.index.max()}", flush=True)

    print("[1] textbook+rsi…", flush=True)
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values

    ev_cache = PACK / f"events_all_{eras[0][1]}_{eras[-1][2]}.pkl"
    if ev_cache.exists():
        blob = pickle.load(ev_cache.open("rb"))
        era_events = blob["era_events"]
        print(f"[2] cache {[ (k, len(v)) for k,v in era_events.items() ]}", flush=True)
    else:
        print("[2] collect events…", flush=True)
        era_events = {}
        for name, lo, hi in eras:
            xs = scalp.collect_scalp_events(df, lo, hi)
            for e in xs:
                e["_era"] = name
            era_events[name] = xs
            print(f"  {name}: {len(xs)}", flush=True)
        pickle.dump({"era_events": era_events, "eras": eras}, ev_cache.open("wb"), protocol=pickle.HIGHEST_PROTOCOL)

    for xs in era_events.values():
        fwdmod.enrich_evt(xs, h, l, c, o)

    # Split E2024 into cal/l3m for cell building (path-100 inside 2024)
    e24 = era_events["E2024"]
    cal24 = [e for e in e24 if e["day"] <= "2024-09-30"]
    l3m24 = [e for e in e24 if e["day"] >= "2024-10-01"]

    specs = [
        {
            "name": "T10",
            "t1": 10.0,
            "sl_max": 12.0,
            "gap": 8,
            "key_fn": fwdmod.keys_t10,
            "styles": ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "p75"],
        },
        {
            "name": "T15",
            "t1": 15.0,
            "sl_max": 15.0,
            "gap": 4,
            "key_fn": fwdmod.keys_hight,
            "styles": fwdmod.STYLES,
        },
        {
            "name": "T20",
            "t1": 20.0,
            "sl_max": 20.0,
            "gap": 4,
            "key_fn": fwdmod.keys_hight,
            "styles": fwdmod.STYLES,
        },
    ]

    results = {"eras": eras, "books": {}}

    for spec in specs:
        name, t1 = spec["name"], spec["t1"]
        print(f"\n######## {name} ########", flush=True)
        key_fn = spec["key_fn"]

        fwdmod.flag_paths(cal24, h, l, c, t1)
        fwdmod.flag_paths(l3m24, h, l, c, t1)
        for era_name, xs in era_events.items():
            if era_name == "E2024":
                for e in xs:
                    e["_keys"] = set(key_fn(e))
                continue
            fwdmod.flag_paths(xs, h, l, c, t1)
            for e in xs:
                e["_keys"] = set(key_fn(e))

        # Dense 2024-proven cells (train 100%)
        cells = build_cells(
            cal24, l3m24, key_fn, spec["styles"], t1, spec["sl_max"], spec["gap"], min_cal=2, min_l3m=1
        )
        print(f"  2024-proven cells={len(cells)}", flush=True)

        # Filter: must stay 100% on every later era
        survivors = []
        for i, r in enumerate(cells, 1):
            if i % 200 == 0:
                print(f"    scored {i}/{len(cells)} survivors={len(survivors)}", flush=True)
            k, st = r["k"], r["st"]
            era_calls = {"E2024": []}
            # rebuild E2024 calls for this cell (gapped)
            ok, n, detailed = score_cell(e24, k, st, spec["gap"], spec["sl_max"], h, l, c, t1)
            if not ok or n < 2:
                continue
            for d in detailed:
                d["_era"] = "E2024"
            era_calls["E2024"] = detailed

            all_ok = True
            for era_name in ("E2025", "E2026A", "E2026B", "FWD"):
                ok, n, detailed = score_cell(
                    era_events[era_name], k, st, spec["gap"], spec["sl_max"], h, l, c, t1
                )
                if not ok:
                    all_ok = False
                    break
                for d in detailed:
                    d["_era"] = era_name
                era_calls[era_name] = detailed
            if not all_ok:
                continue

            total_n = sum(len(v) for v in era_calls.values())
            sample = era_calls["E2024"] + era_calls["E2025"]
            survivors.append(
                {
                    "k": k,
                    "st": st,
                    "era_calls": era_calls,
                    "era_n": {era: len(era_calls.get(era, [])) for era in era_calls},
                    "total_n": total_n,
                    "avg_sl": sum(e[f"_sl_{st}"] for xs in era_calls.values() for e in xs) / max(total_n, 1),
                    "avg_adv": sum(e.get("adv_wick", 0) for e in sample) / max(len(sample), 1),
                    "avg_body": sum(e.get("body_frac", 0) for e in sample) / max(len(sample), 1),
                    "cal_n": r["cal_n"],
                    "l3m_n": r["l3m_n"],
                }
            )

        survivors.sort(key=lambda r: (-r["total_n"], -r["era_n"].get("E2025", 0), r["avg_sl"]))
        print(f"  all-era 100% survivors={len(survivors)}", flush=True)

        variants = {}
        for vlabel, filt, min_era in [
            ("ACC100_ALL", lambda r: True, {"E2024": 2, "E2025": 2, "E2026A": 1, "E2026B": 1, "FWD": 0}),
            ("ACC100_SOFT", lambda r: True, {"E2024": 2, "E2025": 1, "E2026A": 1, "E2026B": 0, "FWD": 0}),
            ("ACC100_Y25Y26", lambda r: True, {"E2024": 1, "E2025": 2, "E2026A": 1, "E2026B": 1, "FWD": 0}),
            ("ACC100_FWD1", lambda r: r["era_n"].get("FWD", 0) >= 1, {"E2024": 2, "E2025": 1, "E2026A": 1, "E2026B": 0, "FWD": 1}),
            ("ACC100_Q", lambda r: r["avg_adv"] < 0.20 and r["avg_body"] >= 0.50, {"E2024": 2, "E2025": 1, "E2026A": 1, "E2026B": 0, "FWD": 0}),
            ("ACC100_CORE", lambda r: True, {"E2024": 3, "E2025": 3, "E2026A": 2, "E2026B": 2, "FWD": 0}),
        ]:
            pool_v = [
                r
                for r in survivors
                if filt(r) and all(r["era_n"].get(era, 0) >= need for era, need in min_era.items())
            ]
            pool_v.sort(key=lambda r: (-r["total_n"], -r["era_n"].get("E2025", 0), r["avg_sl"]))
            chosen = greedy_book(pool_v, spec["gap"], min_era)
            all_calls = [e for r in chosen for e in r["kept"]]
            era_stats = {}
            for era_name in era_events:
                xs = [e for e in all_calls if e["_era"] == era_name]
                era_stats[era_name] = {
                    "n": len(xs),
                    "hit_pct": 100.0 if xs else 0,
                    "days": len({e["day"] for e in xs}),
                }
            print(
                f"  {vlabel}: micros={len(chosen)} total={len(all_calls)} "
                + " ".join(f"{k}={v['n']}" for k, v in era_stats.items()),
                flush=True,
            )
            for r in chosen[:6]:
                print(
                    f"    {r['st']} n={r['total_n']} eras={r['era_n']} · {str(r['k'])[:88]}",
                    flush=True,
                )

            # chronological verify on each era (union book)
            verify = {}
            if chosen:
                for era_name, xs in era_events.items():
                    calls = eval_micros_on_fwd(xs, chosen, spec["gap"], t1, spec["sl_max"], h, l, c, key_fn)
                    st = fwdmod.stats([{**e, "_win": e["_win"]} for e in calls], None)
                    verify[era_name] = {
                        "n": st["n"],
                        "hit_pct": st["hit_pct"],
                        "all_win": all(e["_win"] for e in calls) if calls else True,
                    }
                print(
                    "    VERIFY "
                    + " ".join(f"{k}:{v['n']}c/{v['hit_pct']}%/{v['all_win']}" for k, v in verify.items()),
                    flush=True,
                )

            variants[vlabel] = {
                "n_micros": len(chosen),
                "total_calls": len(all_calls),
                "era_stats": era_stats,
                "verify": verify,
                "micros": [
                    {
                        "st": r["st"],
                        "k": str(r["k"]),
                        "era_n": r["era_n"],
                        "total_n": r["total_n"],
                        "avg_sl": round(r["avg_sl"], 2),
                        "avg_adv": round(r["avg_adv"], 3),
                        "avg_body": round(r["avg_body"], 3),
                    }
                    for r in chosen
                ],
                "sample_calls": [
                    {
                        "era": e["_era"],
                        "day": e["day"],
                        "hm": e["hm"],
                        "decision": e["decision"],
                        "primary": e["primary"],
                        "st": e["_st"],
                        "sl": round(e[f"_sl_{e['_st']}"], 2),
                        "mfe": round(e["mfe"], 1),
                    }
                    for e in sorted(all_calls, key=lambda x: (x["day"], x["mins"]))[:50]
                ],
            }
            (PACK / f"{name}_{vlabel}_micros.pkl").write_bytes(
                pickle.dumps(
                    [{"k": r["k"], "st": r["st"], "era_n": r["era_n"], "total_n": r["total_n"]} for r in chosen],
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
            )

        results["books"][name] = {"t1": t1, "n_survivors": len(survivors), "variants": variants}

    results["elapsed_s"] = round(time.time() - t0, 1)

    lines = [
        "# NIFTY 1m — **ACC100 ALL ERAS** (accuracy-first)",
        "",
        "Find micros that stay **100% target-before-SL on every era** (2024 → Nov2026 FWD).",
        "",
        "Eras:",
    ]
    for name_, lo, hi in eras:
        lines.append(f"- **{name_}**: `{lo} → {hi}` · events={len(era_events[name_])}")
    lines += [
        "",
        "| Book | Variant | Micros | Calls | E2024 | E2025 | E2026A | E2026B | FWD | Verify all_win |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for bname, b in results["books"].items():
        for vlabel, v in b["variants"].items():
            es = v["era_stats"]
            ver = v.get("verify") or {}
            aw = all(x.get("all_win", True) for x in ver.values()) if ver else ""
            lines.append(
                f"| {bname} | **{vlabel}** | {v['n_micros']} | {v['total_calls']} | "
                f"{es.get('E2024',{}).get('n',0)} | {es.get('E2025',{}).get('n',0)} | "
                f"{es.get('E2026A',{}).get('n',0)} | {es.get('E2026B',{}).get('n',0)} | "
                f"{es.get('FWD',{}).get('n',0)} | {aw} |"
            )

    lines += [
        "",
        "## Operate these for 100% accuracy-first",
        "",
        "- Prefer **ACC100_ALL** / **ACC100_Y25Y26** (must print in 2024+2025+2026).",
        "- **ACC100_FWD1** if you also need a Nov9+ live print in-sample.",
        "- Dense HELD packs optimize call count — **not** all-era accuracy.",
        "",
        f"Pack: `{PACK}`",
        f"Elapsed: {results['elapsed_s']}s",
        "",
    ]
    for bname, b in results["books"].items():
        for vlabel in ("ACC100_ALL", "ACC100_SOFT", "ACC100_FWD1"):
            v = b["variants"].get(vlabel) or {}
            lines.append(f"### {bname} {vlabel} ({v.get('n_micros', 0)} micros)")
            lines.append("")
            if not v.get("micros"):
                lines.append("_none_")
                lines.append("")
                continue
            lines.append("| SL | Total | E24 | E25 | 26A | 26B | FWD | key |")
            lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
            for m in v["micros"][:30]:
                en = m["era_n"]
                lines.append(
                    f"| {m['st']} | {m['total_n']} | {en.get('E2024',0)} | {en.get('E2025',0)} | "
                    f"{en.get('E2026A',0)} | {en.get('E2026B',0)} | {en.get('FWD',0)} | `{m['k'][:84]}` |"
                )
            lines.append("")

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {REPORT_MD}", flush=True)
    print("DONE ACC100 all eras", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
