"""Try 2025 as long OOS: train on 2024, check fire-rate + path hit% (live availability)."""
from __future__ import annotations

import json
import pickle
import sys
import time
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
from _diag_held_why_drop_and_fix100 import build_cells, eval_micros_on_fwd, greedy_fwd100  # noqa: E402
from _diag_held_fwd100_rolling_try import rolling_safe_cells  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_oos_2025"
REPORT_MD = OUT / "NIFTY_1M_SCALP_OOS_2025_TRY.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_OOS_2025_TRY.json"

# Train = 2024 only (no 2025 leakage). OOS = full calendar 2025.
CAL_LO, CAL_HI = "2024-01-02", "2024-09-30"
L3M_LO, L3M_HI = "2024-10-01", "2024-12-31"
OOS_LO, OOS_HI = "2025-01-01", "2025-12-31"
HIST_LO = "2023-11-01"


def main() -> int:
    print("=" * 60, flush=True)
    print("Try 2025 OOS — train 2024 → score full 2025 (availability)", flush=True)
    print("=" * 60, flush=True)
    PACK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(HIST_LO, tz="Asia/Kolkata")]
    raw = raw[raw.index <= pd.Timestamp(OOS_HI + " 23:59:59", tz="Asia/Kolkata")]
    print(f"bars={len(raw)} {raw.index.min()} → {raw.index.max()}", flush=True)

    print("[1] textbook+rsi…", flush=True)
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values

    ev_cache = PACK / f"events_{CAL_LO}_{OOS_HI}.pkl"
    if ev_cache.exists():
        blob = pickle.load(ev_cache.open("rb"))
        cal, l3m, oos = blob["cal"], blob["l3m"], blob["oos"]
        print(f"[2] cache cal={len(cal)} l3m={len(l3m)} oos={len(oos)}", flush=True)
    else:
        print("[2] collect events (2024 train + 2025 oos)…", flush=True)
        cal = scalp.collect_scalp_events(df, CAL_LO, CAL_HI)
        l3m = scalp.collect_scalp_events(df, L3M_LO, L3M_HI)
        oos = scalp.collect_scalp_events(df, OOS_LO, OOS_HI)
        pickle.dump({"cal": cal, "l3m": l3m, "oos": oos}, ev_cache.open("wb"), protocol=pickle.HIGHEST_PROTOCOL)
        print(f"  cal={len(cal)} l3m={len(l3m)} oos={len(oos)}", flush=True)

    fwdmod.enrich_evt(cal, h, l, c, o)
    fwdmod.enrich_evt(l3m, h, l, c, o)
    fwdmod.enrich_evt(oos, h, l, c, o)
    oos_days = sorted({e["day"] for e in oos})
    print(f"  oos trading days={len(oos_days)} ({OOS_LO}→{OOS_HI})", flush=True)

    specs = [
        {"name": "T10", "t1": 10.0, "sl_max": 12.0, "gap": 8, "key_fn": fwdmod.keys_t10, "styles": ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "p75"]},
        {"name": "T15", "t1": 15.0, "sl_max": 15.0, "gap": 4, "key_fn": fwdmod.keys_hight, "styles": fwdmod.STYLES},
        {"name": "T20", "t1": 20.0, "sl_max": 20.0, "gap": 4, "key_fn": fwdmod.keys_hight, "styles": fwdmod.STYLES},
    ]

    results = {
        "train": {"cal": [CAL_LO, CAL_HI], "l3m": [L3M_LO, L3M_HI]},
        "oos": [OOS_LO, OOS_HI],
        "oos_days": len(oos_days),
        "books": {},
        "elapsed_s": 0,
    }

    for spec in specs:
        name, t1 = spec["name"], spec["t1"]
        print(f"\n######## {name} ########", flush=True)
        fwdmod.flag_paths(cal, h, l, c, t1)
        fwdmod.flag_paths(l3m, h, l, c, t1)

        cells_dense = build_cells(cal, l3m, spec["key_fn"], spec["styles"], t1, spec["sl_max"], spec["gap"], min_cal=2, min_l3m=1)
        chosen_dense = fwdmod.greedy(cells_dense, spec["gap"], min_cal=2, min_l3m=1)
        dense_calls = eval_micros_on_fwd(oos, chosen_dense, spec["gap"], t1, spec["sl_max"], h, l, c, spec["key_fn"])
        st_dense = fwdmod.stats([{**e, "_win": e["_win"]} for e in dense_calls], len(oos_days))
        print(
            f"  DENSE(train2024): micros={len(chosen_dense)} oos2025 {st_dense['n']}c "
            f"hit={st_dense['hit_pct']}% cpd={st_dense['cpd_all']}",
            flush=True,
        )

        safe_roll, weeks = rolling_safe_cells(
            cells_dense, l3m, spec["gap"], t1, spec["sl_max"], h, l, c, spec["key_fn"]
        )
        roll_m2 = [r for r in safe_roll if r["l3m_n"] >= 2]
        chosen_roll = fwdmod.greedy(roll_m2, spec["gap"], min_cal=2, min_l3m=2)
        roll_calls = eval_micros_on_fwd(oos, chosen_roll, spec["gap"], t1, spec["sl_max"], h, l, c, spec["key_fn"])
        st_roll = fwdmod.stats([{**e, "_win": e["_win"]} for e in roll_calls], len(oos_days))
        print(
            f"  ROLL_m2(honest): micros={len(chosen_roll)} weeks={len(weeks)} "
            f"oos {st_roll['n']}c hit={st_roll['hit_pct']}% cpd={st_roll['cpd_all']} "
            f"days={st_roll['days']}",
            flush=True,
        )

        cells_m2 = build_cells(cal, l3m, spec["key_fn"], spec["styles"], t1, spec["sl_max"], spec["gap"], min_cal=3, min_l3m=2)
        # Peek 2025 for ceiling of "100% if we could filter losers" — not live-deployable
        _, chosen_peek = greedy_fwd100(
            cells_m2, oos, spec["gap"], t1, spec["sl_max"], h, l, c, spec["key_fn"], min_cal=2, min_l3m=2
        )
        peek_calls = eval_micros_on_fwd(oos, chosen_peek, spec["gap"], t1, spec["sl_max"], h, l, c, spec["key_fn"])
        st_peek = fwdmod.stats([{**e, "_win": e["_win"]} for e in peek_calls], len(oos_days))
        print(
            f"  PEEK_2025_100: micros={len(chosen_peek)} oos {st_peek['n']}c "
            f"hit={st_peek['hit_pct']}% cpd={st_peek['cpd_all']} days={st_peek['days']}",
            flush=True,
        )

        # Monthly fire profile for honest ROLL
        by_m = {}
        for e in roll_calls:
            m = e["day"][:7]
            by_m.setdefault(m, {"n": 0, "w": 0})
            by_m[m]["n"] += 1
            by_m[m]["w"] += int(e["_win"])
        monthly = {
            m: {
                "n": v["n"],
                "hit_pct": round(100.0 * v["w"] / v["n"], 1) if v["n"] else 0,
            }
            for m, v in sorted(by_m.items())
        }
        for m, v in monthly.items():
            print(f"    {m}: {v['n']}c hit={v['hit_pct']}%", flush=True)

        # sample wins/losses
        for e in roll_calls[:5]:
            mark = "Y" if e["_win"] else "N"
            print(
                f"    eg {e['day']} {e['hm']} {e['decision']} {e['primary']} "
                f"{e['_st']} {mark} mfe={e['mfe']:.1f}",
                flush=True,
            )

        (PACK / f"{name}_ROLL_m2_2024train_micros.pkl").write_bytes(
            pickle.dumps(
                [{"k": r["k"], "st": r["st"], "cal_n": r["cal_n"], "l3m_n": r["l3m_n"]} for r in chosen_roll],
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        )

        results["books"][name] = {
            "t1": t1,
            "dense": {"n_micros": len(chosen_dense), "oos": st_dense},
            "roll_m2": {
                "n_micros": len(chosen_roll),
                "n_roll_weeks": len(weeks),
                "oos": st_roll,
                "monthly": monthly,
            },
            "peek_2025_100": {"n_micros": len(chosen_peek), "oos": st_peek},
        }

    results["elapsed_s"] = round(time.time() - t0, 1)

    lines = [
        "# NIFTY 1m — try **2025 full-year OOS** (train = 2024 only)",
        "",
        f"Train: cal `{CAL_LO}→{CAL_HI}` · l3m `{L3M_LO}→{L3M_HI}`",
        f"OOS: `{OOS_LO}→{OOS_HI}` · **{len(oos_days)}** trading days",
        "",
        "## Why Nov FWD looked empty",
        "",
        "- Nov9–16 is only ~5 sessions — rare micro geometries often **do not appear**.",
        "- That is **not** missing OOS data; bars were present. Filters simply did not match.",
        "- Live session: a call fires **only when** the locked micro (pattern+geometry+SL style) prints. Not every day.",
        "",
        "## 2025 OOS results (availability check)",
        "",
        "| Book | Variant | Micros | 2025 calls | Hit% | Calls/day (all) | Days with call |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for name, b in results["books"].items():
        for label, key in [("DENSE", "dense"), ("ROLL_m2 honest", "roll_m2"), ("PEEK_2025_100", "peek_2025_100")]:
            row = b[key]
            st = row["oos"]
            lines.append(
                f"| {name} | {label} | {row['n_micros']} | {st['n']} | {st['hit_pct']}% | "
                f"{st['cpd_all']} | {st['days']} |"
            )

    lines += [
        "",
        "### Monthly ROLL_m2 fire rate",
        "",
    ]
    for name, b in results["books"].items():
        lines.append(f"**{name}**")
        lines.append("")
        lines.append("| Month | Calls | Hit% |")
        lines.append("|---|---:|---:|")
        for m, v in b["roll_m2"]["monthly"].items():
            lines.append(f"| {m} | {v['n']} | {v['hit_pct']}% |")
        lines.append("")

    lines += [
        "## Live takeaway",
        "",
        "- **Yes, available live** when micro matches — 2025 shows year-long fire count, not a guarantee of daily calls.",
        "- Honest `ROLL_m2` hit% on 2025 is the deployable estimate (no peek).",
        "- `PEEK_2025_100` is an oracle ceiling only — not usable for live without future labels.",
        f"",
        f"Elapsed: {results['elapsed_s']}s · pack `{PACK}`",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {REPORT_MD}", flush=True)
    print("DONE 2025 OOS try", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
