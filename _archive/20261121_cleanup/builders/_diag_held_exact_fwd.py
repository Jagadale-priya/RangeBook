"""Rebuild exact deep T15/T20 (+T10) micros; score FWD 2026-11-09→today; lock held."""
from __future__ import annotations

import json
import pickle
import sys
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
import research_nifty_1m_chart_only_100 as co  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402

# reuse helpers from fwd script
import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_fwd_nov9_hold"
REPORT_MD = OUT / "NIFTY_1M_SCALP_HELD_LOCK_FWD_NOV9.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_HELD_LOCK_FWD_NOV9.json"

CAL_LO, CAL_HI = "2025-07-02", "2026-08-05"
L3M_LO, L3M_HI = "2026-08-06", "2026-11-06"
FWD_LO = "2026-11-09"


def main() -> int:
    print("Exact held rebuild + FWD", flush=True)
    raw = base.load_existing_1m()
    today = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
    fwd_hi = min(today, raw.index.max().strftime("%Y-%m-%d"))
    print(f"data end={raw.index.max()} fwd={FWD_LO}->{fwd_hi}", flush=True)

    ev_cache = PACK / f"events_{CAL_LO}_{fwd_hi}.pkl"
    if ev_cache.exists():
        blob = pickle.load(ev_cache.open("rb"))
        cal, l3m, fwd = blob["cal"], blob["l3m"], blob["fwd"]
        print(f"events cal={len(cal)} l3m={len(l3m)} fwd={len(fwd)}", flush=True)
        # need arrays aligned to full_i — reload patterned df
        raw = raw[raw.index >= pd.Timestamp("2025-06-01", tz="Asia/Kolkata")]
        df = tb.detect_textbook(raw)
        df = beh.add_rsi(df)
    else:
        raw = raw[raw.index >= pd.Timestamp("2025-06-01", tz="Asia/Kolkata")]
        df = tb.detect_textbook(raw)
        df = beh.add_rsi(df)
        cal = scalp.collect_scalp_events(df, CAL_LO, CAL_HI)
        l3m = scalp.collect_scalp_events(df, L3M_LO, L3M_HI)
        fwd = scalp.collect_scalp_events(df, FWD_LO, fwd_hi)

    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    fwdmod.enrich_evt(cal, h, l, c, o)
    fwdmod.enrich_evt(l3m, h, l, c, o)
    fwdmod.enrich_evt(fwd, h, l, c, o)
    fwd_days = sorted({e["day"] for e in fwd})

    specs = [
        {
            "name": "HELD10",
            "t1": 10.0,
            "sl_max": 12.0,
            "gap": 8,
            "key_fn": fwdmod.keys_t10,
            # match deeper_100 style set roughly
            "styles": ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "p75"],
        },
        {
            "name": "HELD15",
            "t1": 15.0,
            "sl_max": 15.0,
            "gap": 4,
            "key_fn": fwdmod.keys_hight,
            "styles": fwdmod.STYLES,
        },
        {
            "name": "HELD20",
            "t1": 20.0,
            "sl_max": 20.0,
            "gap": 4,
            "key_fn": fwdmod.keys_hight,
            "styles": fwdmod.STYLES,
        },
    ]

    # Also try T15 SLmax20 gap4 for max calls variant as HELD15_MAX
    results = {
        "fwd_lo": FWD_LO,
        "fwd_hi": fwd_hi,
        "fwd_days": fwd_days,
        "books": {},
        "locked": ["HELD10", "HELD15", "HELD20"],
    }

    for spec in specs:
        name, t1 = spec["name"], spec["t1"]
        print(f"\n=== {name} ===", flush=True)
        fwdmod.flag_paths(cal, h, l, c, t1)
        fwdmod.flag_paths(l3m, h, l, c, t1)
        for e in fwd:
            e["_keys"] = set(spec["key_fn"](e))
            e["_keys_cache"] = list(e["_keys"])

        # exact densify style: merge min_cal 3 cells + min_cal 2 cells
        cal_b, l3m_b = defaultdict(list), defaultdict(list)
        for e in cal:
            if 4 <= e["sl_prev"] <= 20:
                for k in spec["key_fn"](e):
                    cal_b[k].append(e)
        for e in l3m:
            if 4 <= e["sl_prev"] <= 20:
                for k in spec["key_fn"](e):
                    l3m_b[k].append(e)

        def hunt(min_cal, min_l3m_full):
            both = []
            gap, sl_max = spec["gap"], spec["sl_max"]
            for st in spec["styles"]:
                for k, ces in cal_b.items():
                    cr = fwdmod.apply_gap(ces, gap)
                    cr = [e for e in cr if 4 <= e.get(f"_sl_{st}", 99) <= sl_max]
                    cr = fwdmod.apply_gap(cr, gap)
                    if len(cr) < min_cal:
                        continue
                    if not all(e.get(f"_ok_{st}") for e in cr):
                        continue
                    tr = fwdmod.apply_gap(l3m_b.get(k, []), gap)
                    tr = [e for e in tr if 4 <= e.get(f"_sl_{st}", 99) <= sl_max]
                    tr = fwdmod.apply_gap(tr, gap)
                    if len(tr) < 1:
                        continue
                    if len(tr) < min_l3m_full and len(cr) < 4:
                        continue
                    if not all(e.get(f"_ok_{st}") for e in tr):
                        continue
                    both.append(
                        {
                            "k": k,
                            "st": st,
                            "cal_calls": cr,
                            "l3m_calls": tr,
                            "cal_n": len(cr),
                            "l3m_n": len(tr),
                            "avg_sl": sum(e[f"_sl_{st}"] for e in tr) / len(tr),
                        }
                    )
            both.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"], r["avg_sl"]))
            seen, uniq = set(), []
            for r in both:
                id_ = (r["k"], r["st"])
                if id_ in seen:
                    continue
                seen.add(id_)
                uniq.append(r)
            return uniq

        uniq = hunt(3, 2)
        seen = {(r["k"], r["st"]) for r in uniq}
        for r in hunt(2, 1):
            if (r["k"], r["st"]) not in seen:
                uniq.append(r)
                seen.add((r["k"], r["st"]))
        uniq.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"], r["avg_sl"]))
        chosen = fwdmod.greedy(uniq, spec["gap"], min_cal=2, min_l3m=1)

        cal_all = [{**e, "_st": r["st"], "_t1": t1, "_win": True, f"_sl_{r['st']}": e[f"_sl_{r['st']}"]} for r in chosen for e in r["cal_calls"]]
        l3m_all = [{**e, "_st": r["st"], "_t1": t1, "_win": True, f"_sl_{r['st']}": e[f"_sl_{r['st']}"]} for r in chosen for e in r["l3m_calls"]]
        train_cal = fwdmod.stats(cal_all, 271)
        train_l3m = fwdmod.stats(l3m_all, 64)
        print(
            f"  train micros={len(chosen)} cal {train_cal['n']}/{train_cal['days']} "
            f"l3m {train_l3m['n']}/{train_l3m['days']} zero={train_l3m['zero']}",
            flush=True,
        )

        # Apply with SL max filter on fire
        micro_map = [(r["k"], r["st"]) for r in chosen]
        by_day = defaultdict(list)
        for e in fwd:
            by_day[e["day"]].append(e)
        out = []
        for d, xs in sorted(by_day.items()):
            xs = sorted(xs, key=lambda x: x["mins"])
            last = None
            for e in xs:
                if last is not None and e["mins"] - last < spec["gap"]:
                    continue
                fired = False
                for k, st in micro_map:
                    if k not in e["_keys"]:
                        continue
                    sl = fwdmod.lesser(e, st)
                    if not (4 <= sl <= spec["sl_max"]):
                        continue
                    ok, sl2 = fwdmod.path_ok(e, h, l, c, st, t1, sl_max=spec["sl_max"])
                    out.append(
                        {
                            **e,
                            "_st": st,
                            "_t1": t1,
                            f"_sl_{st}": sl2,
                            "_win": bool(ok),
                        }
                    )
                    last = e["mins"]
                    fired = True
                    break
                if not fired:
                    continue
        fwd_stats = fwdmod.stats(out, len(fwd_days) or 1)
        print(
            f"  FWD {fwd_stats['n']}c/{fwd_stats['days']}d hit={fwd_stats['hit_pct']}% "
            f"zero={fwd_stats['zero']} avgSL={fwd_stats['avg_sl']} miss={fwd_stats['miss_days']}",
            flush=True,
        )
        for e in out:
            print(
                f"    {e['day']} {e['hm']} {e['decision']} {e['primary']} "
                f"{e['_st']} sl={e[f'_sl_{e['_st']}']:.1f} {'Y' if e['_win'] else 'N'} "
                f"mfe={e['mfe']:.1f}",
                flush=True,
            )

        results["books"][name] = {
            "t1": t1,
            "sl_max": spec["sl_max"],
            "gap": spec["gap"],
            "n_micros": len(chosen),
            "train_cal": train_cal,
            "train_l3m": train_l3m,
            "fwd": fwd_stats,
            "fwd_calls": [
                {
                    "day": e["day"],
                    "hm": e["hm"],
                    "decision": e["decision"],
                    "primary": e["primary"],
                    "st": e["_st"],
                    "sl": round(e[f"_sl_{e['_st']}"], 2),
                    "win": e["_win"],
                    "mfe": round(e["mfe"], 1),
                    "mae": round(e["mae"], 2),
                }
                for e in out
            ],
            "held": True,
        }
        # persist micros for live reuse
        (PACK / f"{name}_micros.pkl").write_bytes(
            pickle.dumps(
                [{"k": r["k"], "st": r["st"], "cal_n": r["cal_n"], "l3m_n": r["l3m_n"]} for r in chosen],
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        )

    # rewrite report
    lines = [
        "# NIFTY 1m — **HELD logics locked** + forward check (9 Nov → today)",
        "",
        "**Not live.**",
        "",
        f"- Candle: **NIFTY 1-minute**",
        f"- Train: calibrate `{CAL_LO}`→`{CAL_HI}` · last3m `{L3M_LO}`→`{L3M_HI}`",
        f"- Forward: **`{FWD_LO}` → `{fwd_hi}`** · sessions: {', '.join(fwd_days)}",
        "- Win = **target before structure SL**",
        "",
        "## LOCKED books",
        "",
        "| Book | T1 | Train calls | Train days | Train zero | Train hit | FWD calls | FWD days | FWD hit% | FWD avgSL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("HELD10", "HELD15", "HELD20"):
        b = results["books"][name]
        lines.append(
            f"| **{name}** | {int(b['t1'])} | {b['train_l3m']['n']} | {b['train_l3m']['days']} | "
            f"{b['train_l3m']['zero']} | 100% | {b['fwd']['n']} | {b['fwd']['days']}/{len(fwd_days)} | "
            f"**{b['fwd']['hit_pct']}%** | {b['fwd']['avg_sl']} |"
        )

    for name in ("HELD10", "HELD15", "HELD20"):
        b = results["books"][name]
        lines += [
            "",
            f"## {name} LOCKED · T1={int(b['t1'])}",
            "",
            f"- Micros **{b['n_micros']}** · gap {b['gap']} · SLmax {b['sl_max']}",
            f"- Train last3m **{b['train_l3m']['n']}/{b['train_l3m']['days']}d** @100% path",
            f"- Forward **{b['fwd']['n']} calls @ {b['fwd']['hit_pct']}%** "
            f"(target-first) · avg SL {b['fwd']['avg_sl']}",
            "",
            "| Day | HM | Side | Pattern | SL | Win | MFE | MAE |",
            "|---|---|---|---|---:|:---:|---:|---:|",
        ]
        for e in b["fwd_calls"]:
            lines.append(
                f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"{e['sl']} | {'Y' if e['win'] else 'N'} | {e['mfe']} | {e['mae']} |"
            )

    lines += [
        "",
        "## Hold policy",
        "",
        "1. **HELD10** T1=10 — locked",
        "2. **HELD15** T1=15 deep family/slot — locked",
        "3. **HELD20** T1=20 deep family/slot — locked",
        "4. Forward week is OOS stress; short sample — use for monitoring, not unlock",
        "",
        f"- Pack: `{PACK}`",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"wrote {REPORT_MD}", flush=True)
    print("DONE exact held fwd", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
