"""Try densify FWD100 via rolling last3m OOS weeks; check Nov9+ path accuracy (no FWD peek)."""
from __future__ import annotations

import json
import pickle
import sys
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
import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod  # noqa: E402
from _diag_held_why_drop_and_fix100 import build_cells, eval_micros_on_fwd, greedy_fwd100  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_fwd_nov9_hold"
REPORT_MD = OUT / "NIFTY_1M_SCALP_HELD_FWD100_ROLLING_TRY.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_HELD_FWD100_ROLLING_TRY.json"

CAL_LO, CAL_HI = "2025-07-02", "2026-08-05"
L3M_LO, L3M_HI = "2026-08-06", "2026-11-06"
FWD_LO = "2026-11-09"


def week_id(day: str) -> str:
    ts = pd.Timestamp(day)
    iso = ts.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def cell_path_clean(events, k, st, gap, sl_max, h, l, c, t1) -> tuple[bool, int, int]:
    """Return (all_path_ok_or_empty, n_matched_gapped, n_wins)."""
    matched = []
    for e in events:
        keys = e.get("_keys") or set()
        if k not in keys:
            continue
        sl = fwdmod.lesser(e, st)
        if not (4 <= sl <= sl_max):
            continue
        matched.append(e)
    matched = fwdmod.apply_gap(matched, gap)
    if not matched:
        return True, 0, 0
    wins = 0
    for e in matched:
        ok, _ = fwdmod.path_ok(e, h, l, c, st, t1, sl_max=sl_max)
        if ok:
            wins += 1
        else:
            return False, len(matched), wins
    return True, len(matched), wins


def rolling_safe_cells(cells, l3m, gap, t1, sl_max, h, l, c, key_fn, min_fold_fires=0):
    """Keep cells with zero path losses on every last3m ISO-week holdout."""
    for e in l3m:
        e["_keys"] = set(key_fn(e))
        e["_week"] = week_id(e["day"])
    weeks = sorted({e["_week"] for e in l3m})
    by_week = {w: [e for e in l3m if e["_week"] == w] for w in weeks}

    safe = []
    for r in cells:
        k, st = r["k"], r["st"]
        fold_ok = True
        fold_fires = 0
        fold_wins = 0
        for w, xs in by_week.items():
            ok, n, wins = cell_path_clean(xs, k, st, gap, sl_max, h, l, c, t1)
            if not ok:
                fold_ok = False
                break
            fold_fires += n
            fold_wins += wins
        if not fold_ok:
            continue
        if fold_fires < min_fold_fires:
            continue
        safe.append(
            {
                **r,
                "roll_fires": fold_fires,
                "roll_wins": fold_wins,
                "n_weeks": len(weeks),
            }
        )
    safe.sort(key=lambda r: (-r["roll_wins"], -r["l3m_n"], -r["cal_n"], r["avg_sl"]))
    return safe, weeks


def main() -> int:
    print("=" * 60, flush=True)
    print("Try: rolling-OOS densify + check Nov9+ (no FWD peek)", flush=True)
    print("=" * 60, flush=True)

    raw = base.load_existing_1m()
    today = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
    fwd_hi = min(today, raw.index.max().strftime("%Y-%m-%d"))
    blob = pickle.load((PACK / f"events_{CAL_LO}_{fwd_hi}.pkl").open("rb"))
    cal, l3m, fwd = blob["cal"], blob["l3m"], blob["fwd"]
    print(f"events cal={len(cal)} l3m={len(l3m)} fwd={len(fwd)} window={FWD_LO}->{fwd_hi}", flush=True)

    raw = raw[raw.index >= pd.Timestamp("2025-06-01", tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    fwdmod.enrich_evt(cal, h, l, c, o)
    fwdmod.enrich_evt(l3m, h, l, c, o)
    fwdmod.enrich_evt(fwd, h, l, c, o)
    fwd_days = sorted({e["day"] for e in fwd})

    specs = [
        {"name": "T10", "t1": 10.0, "sl_max": 12.0, "gap": 8, "key_fn": fwdmod.keys_t10, "styles": ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "p75"]},
        {"name": "T15", "t1": 15.0, "sl_max": 15.0, "gap": 4, "key_fn": fwdmod.keys_hight, "styles": fwdmod.STYLES},
        {"name": "T20", "t1": 20.0, "sl_max": 20.0, "gap": 4, "key_fn": fwdmod.keys_hight, "styles": fwdmod.STYLES},
    ]

    results = {"fwd_days": fwd_days, "fwd_hi": fwd_hi, "books": {}}

    for spec in specs:
        name, t1 = spec["name"], spec["t1"]
        print(f"\n######## {name} ########", flush=True)
        fwdmod.flag_paths(cal, h, l, c, t1)
        fwdmod.flag_paths(l3m, h, l, c, t1)

        # dense pool (min_l3m=1) then filter by rolling OOS cleanliness
        cells_dense = build_cells(cal, l3m, spec["key_fn"], spec["styles"], t1, spec["sl_max"], spec["gap"], min_cal=2, min_l3m=1)
        safe_roll, weeks = rolling_safe_cells(
            cells_dense, l3m, spec["gap"], t1, spec["sl_max"], h, l, c, spec["key_fn"], min_fold_fires=0
        )
        print(f"  l3m weeks={len(weeks)} dense_cells={len(cells_dense)} roll_safe={len(safe_roll)}", flush=True)

        variants = []
        for label, pool, min_cal, min_l3m in [
            ("ROLL_m1", safe_roll, 2, 1),
            ("ROLL_m2", [r for r in safe_roll if r["l3m_n"] >= 2], 2, 2),
            ("ROLL_m3", [r for r in safe_roll if r["l3m_n"] >= 3], 2, 3),
        ]:
            chosen = fwdmod.greedy(pool, spec["gap"], min_cal=min_cal, min_l3m=min_l3m)
            calls = eval_micros_on_fwd(fwd, chosen, spec["gap"], t1, spec["sl_max"], h, l, c, spec["key_fn"])
            st = fwdmod.stats([{**e, "_win": e["_win"]} for e in calls], len(fwd_days))
            train_l3m_n = sum(len(r["l3m_calls"]) for r in chosen)
            train_days = len({e["day"] for r in chosen for e in r["l3m_calls"]})
            all_win = all(e["_win"] for e in calls) if calls else True
            print(
                f"  {label}: micros={len(chosen)} train_l3m {train_l3m_n}/{train_days}d "
                f"fwd {st['n']}c hit={st['hit_pct']}% all_win={all_win}",
                flush=True,
            )
            for e in calls:
                mark = "Y" if e["_win"] else "N"
                print(
                    f"    {e['day']} {e['hm']} {e['decision']} {e['primary']} "
                    f"{e['_st']} sl={e[f'_sl_{e['_st']}']:.1f} {mark} mfe={e['mfe']:.1f}",
                    flush=True,
                )
            variants.append(
                {
                    "label": label,
                    "n_micros": len(chosen),
                    "train_l3m_calls": train_l3m_n,
                    "train_l3m_days": train_days,
                    "fwd": st,
                    "all_win": all_win,
                    "fwd_calls": [
                        {
                            "day": e["day"],
                            "hm": e["hm"],
                            "decision": e["decision"],
                            "primary": e["primary"],
                            "st": e["_st"],
                            "sl": round(e[f"_sl_{e['_st']}"], 2),
                            "win": bool(e["_win"]),
                            "mfe": round(e["mfe"], 1),
                            "mae": round(e["mae"], 2),
                        }
                        for e in calls
                    ],
                    "micros": [{"k": str(r["k"]), "st": r["st"], "l3m_n": r["l3m_n"]} for r in chosen],
                }
            )
            # persist best-effort roll packs
            (PACK / f"{name}_{label}_micros.pkl").write_bytes(
                pickle.dumps(
                    [{"k": r["k"], "st": r["st"], "cal_n": r["cal_n"], "l3m_n": r["l3m_n"]} for r in chosen],
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
            )

        # Compare: peek FWD100 (existing method) vs honest roll
        cells_m2 = build_cells(cal, l3m, spec["key_fn"], spec["styles"], t1, spec["sl_max"], spec["gap"], min_cal=3, min_l3m=2)
        _, chosen_peek = greedy_fwd100(cells_m2, fwd, spec["gap"], t1, spec["sl_max"], h, l, c, spec["key_fn"], min_cal=2, min_l3m=2)
        calls_peek = eval_micros_on_fwd(fwd, chosen_peek, spec["gap"], t1, spec["sl_max"], h, l, c, spec["key_fn"])
        st_peek = fwdmod.stats([{**e, "_win": e["_win"]} for e in calls_peek], len(fwd_days))
        print(
            f"  PEEK_FWD100 (ref): micros={len(chosen_peek)} fwd {st_peek['n']}c hit={st_peek['hit_pct']}%",
            flush=True,
        )

        # Combo: roll-safe ∩ no FWD losses (operate when need 100% including this week)
        safe_roll_m2 = [r for r in safe_roll if r["l3m_n"] >= 2]
        _, chosen_combo = greedy_fwd100(
            safe_roll_m2, fwd, spec["gap"], t1, spec["sl_max"], h, l, c, spec["key_fn"], min_cal=2, min_l3m=2
        )
        calls_combo = eval_micros_on_fwd(fwd, chosen_combo, spec["gap"], t1, spec["sl_max"], h, l, c, spec["key_fn"])
        st_combo = fwdmod.stats([{**e, "_win": e["_win"]} for e in calls_combo], len(fwd_days))
        all_win_c = all(e["_win"] for e in calls_combo) if calls_combo else True
        print(
            f"  ROLL∩FWD100: micros={len(chosen_combo)} fwd {st_combo['n']}c "
            f"hit={st_combo['hit_pct']}% all_win={all_win_c}",
            flush=True,
        )
        for e in calls_combo:
            print(
                f"    {e['day']} {e['hm']} {e['decision']} {e['primary']} "
                f"{e['_st']} sl={e[f'_sl_{e['_st']}']:.1f} Y mfe={e['mfe']:.1f}",
                flush=True,
            )
        (PACK / f"{name}_ROLL_FWD100_micros.pkl").write_bytes(
            pickle.dumps(
                [{"k": r["k"], "st": r["st"], "cal_n": r["cal_n"], "l3m_n": r["l3m_n"]} for r in chosen_combo],
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        )

        results["books"][name] = {
            "t1": t1,
            "n_weeks": len(weeks),
            "weeks": weeks,
            "n_dense_cells": len(cells_dense),
            "n_roll_safe": len(safe_roll),
            "variants": variants,
            "peek_fwd100": {"n_micros": len(chosen_peek), "fwd": st_peek},
            "roll_and_fwd100": {
                "n_micros": len(chosen_combo),
                "fwd": st_combo,
                "all_win": all_win_c,
                "fwd_calls": [
                    {
                        "day": e["day"],
                        "hm": e["hm"],
                        "decision": e["decision"],
                        "primary": e["primary"],
                        "st": e["_st"],
                        "sl": round(e[f"_sl_{e['_st']}"], 2),
                        "mfe": round(e["mfe"], 1),
                    }
                    for e in calls_combo
                ],
            },
        }

    # markdown
    lines = [
        "# NIFTY 1m — try rolling-OOS densify + check Nov9+",
        "",
        f"Forward: **{FWD_LO} → {fwd_hi}** · days: {', '.join(fwd_days)}",
        "",
        "Selection uses **calibrate + last3m rolling ISO-week holdouts only** (no FWD peek).",
        "`ROLL∩FWD100` additionally drops any cell with a Nov9+ path loss.",
        "",
        "## Results",
        "",
        "| Book | Variant | Micros | Train l3m | FWD calls | FWD hit% | all_win |",
        "|---|---|---:|---:|---:|---:|:---:|",
    ]
    for name, b in results["books"].items():
        for v in b["variants"]:
            lines.append(
                f"| {name} | {v['label']} | {v['n_micros']} | {v['train_l3m_calls']}/{v['train_l3m_days']}d "
                f"| {v['fwd']['n']} | {v['fwd']['hit_pct']}% | {v['all_win']} |"
            )
        p = b["peek_fwd100"]
        lines.append(
            f"| {name} | PEEK_FWD100 | {p['n_micros']} | — | {p['fwd']['n']} | {p['fwd']['hit_pct']}% | — |"
        )
        c = b["roll_and_fwd100"]
        lines.append(
            f"| {name} | **ROLL∩FWD100** | {c['n_micros']} | — | {c['fwd']['n']} | "
            f"{c['fwd']['hit_pct']}% | {c['all_win']} |"
        )

    lines += [
        "",
        "## Takeaway",
        "",
        "- Honest `ROLL_m*` = deployable without peeking at Nov9+; hit% is the real OOS check.",
        "- `ROLL∩FWD100` = operate when you require 100% including this forward week.",
        "- Packs written under `nifty_1m_scalp_fwd_nov9_hold/*_ROLL*_micros.pkl`.",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {REPORT_MD}", flush=True)
    print("DONE rolling try + check", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
