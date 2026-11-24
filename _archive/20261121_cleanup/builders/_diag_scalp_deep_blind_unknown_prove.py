"""Blind prove DEEP logic on UNKNOWN 1m candles.

Important: locked HELD_DEEP_1CPD used hold/FWD in zero-loss filter (not fully unknown).
This rebuilds micros on **2024+2025 only**, then scores **all 2026 bars** as unknown OOS.
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
import research_nifty_1m_vix_candle_adaptive as vixmod  # noqa: E402
import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import (  # noqa: E402
    EV_CACHE,
    HIST_LO,
    PACK,
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
REPORT_MD = OUT / "NIFTY_1M_SCALP_DEEP_BLIND_UNKNOWN_PROVE.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_DEEP_BLIND_UNKNOWN_PROVE.json"
GAP = 1


def one_per_day_stats(calls, n_days):
    first = {}
    for e in sorted(calls, key=lambda x: (x["day"], x["mins"])):
        first.setdefault(e["day"], e)
    ones = list(first.values())
    if not ones:
        return {"n": 0, "hit": 0.0, "cover": 0.0, "all_win": True, "days": 0}
    w = sum(1 for e in ones if e["_win"])
    return {
        "n": len(ones),
        "hit": round(100.0 * w / len(ones), 2),
        "cover": round(100.0 * len(ones) / max(n_days, 1), 1),
        "all_win": all(e["_win"] for e in ones),
        "days": len(ones),
    }


def main() -> int:
    print("=" * 60, flush=True)
    print("BLIND prove: train 2024-25 → UNKNOWN all 2026 1m", flush=True)
    print("=" * 60, flush=True)
    PACK.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    blob = pickle.load(EV_CACHE.open("rb"))
    era = blob["era_events"]
    cal, l3m = era["E2024"], era["E2025"]
    unk_a = era["E2026A"]  # 2026-01-01 → 2026-08-05
    unk_b = era["E2026B"]  # 2026-08-06 → 2026-11-06
    unk_c = era["FWD"]  # 2026-11-09 → 2026-11-16
    unknown = unk_a + unk_b + unk_c

    print(
        "UNKNOWN candles (never used to lock micros in THIS blind run):",
        flush=True,
    )
    print(f"  UNK_2026A {min(e['day'] for e in unk_a)}→{max(e['day'] for e in unk_a)} events={len(unk_a)}", flush=True)
    print(f"  UNK_2026B {min(e['day'] for e in unk_b)}→{max(e['day'] for e in unk_b)} events={len(unk_b)}", flush=True)
    print(f"  UNK_FWD   {min(e['day'] for e in unk_c)}→{max(e['day'] for e in unk_c)} events={len(unk_c)}", flush=True)
    print(
        "NOTE: prior HELD_DEEP_1CPD peeked hold/FWD at build — this blind book does NOT.",
        flush=True,
    )

    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(HIST_LO, tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    vix = vixmod.load_vix()

    print("[1] enrich…", flush=True)
    for name, xs in [("cal", cal), ("l3m", l3m), ("unk", unknown)]:
        fwdmod.enrich_evt(xs, h, l, c, o)
        enrich_structure(xs, h, l, c, o, vix)
        enrich_prior3(xs, h, l, c, o)
        flag_sl10(xs, h, l, c)
        enrich_deep(xs, h, l, c, o, df)
        print(f"  {name}={len(xs)}", flush=True)

    print("[2] build BLINDED deep micros (zero-loss on 2024+2025 ONLY)…", flush=True)
    for e in cal + l3m:
        e["_keys"] = set(keys_deep(e))
    cal_b = index_by_key(cal, keys_deep)
    l3m_b = index_by_key(l3m, keys_deep)

    cand = set()
    for bucket in (cal_b, l3m_b):
        for (k, st), rows in bucket.items():
            if any(ok for _, ok, _ in rows):
                cand.add((k, st))
    print(f"  candidates={len(cand)}", flush=True)

    cells = []
    for i, (k, st) in enumerate(cand):
        if i and i % 100000 == 0:
            print(f"    scanned {i}/{len(cand)} cells={len(cells)}", flush=True)
        ok_c, n_c, c_ev = cell_clean(cal_b, k, st)
        ok_l, n_l, l_ev = cell_clean(l3m_b, k, st)
        if not (ok_c and ok_l):
            continue
        if n_c < 1 or n_c + n_l < 2:
            continue
        for e in c_ev + l_ev:
            e[f"_ok_{st}"] = True
            e[f"_sl_{st}"] = e[f"_sl10_{st}"]
            e["_sl"] = e[f"_sl10_{st}"]
            e["_win"] = True
        cells.append(
            {
                "k": k,
                "st": st,
                "cal_calls": c_ev,
                "l3m_calls": l_ev,
                "hold_calls": [],
                "fwd_calls": [],
                "cal_n": n_c,
                "l3m_n": n_l,
                "hold_n": 0,
                "fwd_n": 0,
                "total_n": n_c + n_l,
                "days": {e["day"] for e in c_ev + l_ev},
                "avg_sl": sum(e[f"_sl10_{st}"] for e in c_ev + l_ev) / max(n_c + n_l, 1),
            }
        )
    print(f"  blind zero-loss cells={len(cells)}", flush=True)
    chosen, _ = greedy_1cpd(cells, gap=GAP)
    print(f"  blind book micros={len(chosen)}", flush=True)

    (PACK / "DEEP_BLIND_2024_2025_micros.pkl").write_bytes(
        pickle.dumps([{"k": r["k"], "st": r["st"]} for r in chosen], protocol=pickle.HIGHEST_PROTOCOL)
    )

    # Also score previously locked peeked book on unknown for comparison (contaminated)
    peeked = []
    peeked_path = PACK / "HELD_DEEP_1CPD_100_micros.pkl"
    if peeked_path.exists():
        peeked = pickle.loads(peeked_path.read_bytes())

    print("[3] score UNKNOWN 2026…", flush=True)
    windows = [
        ("TRAIN_2024", cal),
        ("TRAIN_2025", l3m),
        ("UNK_2026A", unk_a),
        ("UNK_2026B", unk_b),
        ("UNK_FWD_Nov9_16", unk_c),
        ("UNK_ALL_2026", unknown),
    ]

    results = {"blind_micros": len(chosen), "windows": {}, "peeked_compare": {}}
    for label, xs in windows:
        nd = len({e["day"] for e in xs})
        calls = eval_book(xs, chosen, keys_deep, h, l, c, GAP)
        st = stats(calls, nd)
        one = one_per_day_stats(calls, nd)
        results["windows"][label] = {"full": st, "one_per_day": one, "n_days": nd}
        print(
            f"  {label}: full {st['n']}c hit={st['hit']}% all_win={st['all_win']} · "
            f"1/day {one['n']}c cover={one['cover']}% hit={one['hit']}%",
            flush=True,
        )
        if label.startswith("UNK") and calls:
            # show first few unknown calls
            for e in sorted(calls, key=lambda x: (x["day"], x["mins"]))[:8]:
                mark = "Y" if e["_win"] else "N"
                print(
                    f"    {e['day']} {e['hm']} {e['decision']} {e['primary']} "
                    f"{e['_st']} sl={e['_sl']:.1f} {mark} mfe={e['mfe']:.1f}",
                    flush=True,
                )

    if peeked:
        print("[4] compare peeked HELD_DEEP on same UNKNOWN (not a clean proof)…", flush=True)
        for label, xs in [("UNK_ALL_2026", unknown), ("UNK_FWD_Nov9_16", unk_c)]:
            nd = len({e["day"] for e in xs})
            calls = eval_book(xs, peeked, keys_deep, h, l, c, GAP)
            st = stats(calls, nd)
            one = one_per_day_stats(calls, nd)
            results["peeked_compare"][label] = {"full": st, "one_per_day": one}
            print(
                f"  PEEKED {label}: full {st['n']}@{st['hit']}% · 1/day {one['n']} cover={one['cover']}% hit={one['hit']}%",
                flush=True,
            )

    # losses detail on unknown if any
    unk_calls = eval_book(unknown, chosen, keys_deep, h, l, c, GAP)
    losses = [e for e in unk_calls if not e["_win"]]
    results["unk_losses"] = [
        {
            "day": e["day"],
            "hm": e["hm"],
            "decision": e["decision"],
            "primary": e["primary"],
            "st": e["_st"],
            "sl": round(e["_sl"], 2),
            "mfe": round(e["mfe"], 1),
            "mae": round(e["mae"], 1),
        }
        for e in losses[:40]
    ]
    results["elapsed_s"] = round(time.time() - t0, 1)

    uw = results["windows"]["UNK_ALL_2026"]
    lines = [
        "# DEEP logic — **blind prove on UNKNOWN 2026 1m candles**",
        "",
        "## Which candles are new / unknown?",
        "",
        "| Window | Dates | Role |",
        "|---|---|---|",
        "| TRAIN_2024 / TRAIN_2025 | 2024 + 2025 | used to **lock** blind micros |",
        "| **UNK_2026A** | 2026-01-01 → 2026-08-05 | **unknown OOS** |",
        "| **UNK_2026B** | 2026-08-06 → 2026-11-06 | **unknown OOS** |",
        "| **UNK_FWD** | 2026-11-09 → 2026-11-16 | **unknown OOS** (latest local bars) |",
        "",
        "No newer bars exist after 2026-11-16 in local store (today).",
        "",
        "Prior `HELD_DEEP_1CPD` filtered cells using hold/FWD too — **not** a clean unknown proof.",
        "This run locks `DEEP_BLIND_2024_2025_micros.pkl` on train only.",
        "",
        f"Blind micros: **{len(chosen)}** · T1={T1} · SL≤{SL_MAX} · path",
        "",
        "## Blind accuracy on unknown",
        "",
        "| Window | Days | Full calls | Full hit% | all_win | 1/day n | 1/day cover | 1/day hit% |",
        "|---|---:|---:|---:|:---:|---:|---:|---:|",
    ]
    for label, _ in windows:
        w = results["windows"][label]
        f, o = w["full"], w["one_per_day"]
        lines.append(
            f"| **{label}** | {w['n_days']} | {f['n']} | {f['hit']}% | {f['all_win']} | "
            f"{o['n']} | {o['cover']}% | {o['hit']}% |"
        )

    lines += [
        "",
        f"### Verdict (UNK_ALL_2026)",
        "",
        f"- Full path: **{uw['full']['n']}** calls @ **{uw['full']['hit']}%** · all_win={uw['full']['all_win']}",
        f"- 1 call/day: **{uw['one_per_day']['n']}** days ({uw['one_per_day']['cover']}% cover) @ **{uw['one_per_day']['hit']}%**",
        "",
    ]
    if losses:
        lines.append(f"Unknown path losses (**{len(losses)}**):")
        lines.append("")
        for e in results["unk_losses"][:15]:
            lines.append(
                f"- {e['day']} {e['hm']} {e['decision']} {e['primary']} {e['st']} "
                f"sl={e['sl']} mfe={e['mfe']} mae={e['mae']}"
            )
        lines.append("")
    else:
        lines.append("No unknown path losses in this blind test.")
        lines.append("")

    if results["peeked_compare"]:
        lines += ["## Peeked HELD_DEEP on same unknown (contaminated — reference only)", ""]
        for label, w in results["peeked_compare"].items():
            lines.append(
                f"- {label}: full {w['full']['n']}@{w['full']['hit']}% · "
                f"1/day {w['one_per_day']['n']} cover={w['one_per_day']['cover']}% hit={w['one_per_day']['hit']}%"
            )
        lines.append("")

    lines += [
        f"Pack: `{PACK / 'DEEP_BLIND_2024_2025_micros.pkl'}`",
        f"Elapsed: {results['elapsed_s']}s",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {REPORT_MD}", flush=True)
    print("DONE blind unknown prove", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
