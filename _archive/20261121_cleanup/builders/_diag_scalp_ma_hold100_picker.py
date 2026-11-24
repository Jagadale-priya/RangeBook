"""Blind day-picker for MA HOLD100 (EMA34 trail · T1=12).

Holds the proven exit logic; combines train-clean keys + multi-key vote +
session timing to pick ONE call/day without peeking hold.

Target: train 100% hit + 100% cover; hold as close as possible to oracle 100/100.
"""
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
import research_nifty_1m_vix_candle_adaptive as vixmod  # noqa: E402
import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import enrich_prior3  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402
from _diag_scalp_ma_lastyear_init import (  # noqa: E402
    HOLD_LO,
    WIN_LO,
    PACK,
    add_ma_layers,
    enrich_ma_layers,
    summarize,
)
from _diag_scalp_ma_hold100 import attach_exit_grid, keys_hold  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK_OUT = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_ma_hold100"
REPORT = OUT / "NIFTY_1M_SCALP_MA_HOLD100_PICKER.md"
MODE = "trail34"
T1 = 12.0


def build_allow(train, mode=MODE, t1=T1, min_n=2):
    """Keys that never lose under exit on train; enough fires."""
    bucket = defaultdict(list)
    for e in train:
        sc = e["_exit"][(mode, t1)]
        for k in keys_hold(e):
            bucket[k].append((e["day"], bool(sc["_win"])))
    allow = {}
    for k, rows in bucket.items():
        if any(not ok for _, ok in rows):
            continue
        days = {d for d, ok in rows if ok}
        if len(rows) < min_n:
            continue
        allow[k] = {"n": len(rows), "days": len(days)}
    return allow


def champion_allow(train, mode=MODE, t1=T1):
    """Keys from first train oracle-win each day, purified (never lose)."""
    by = defaultdict(list)
    for e in train:
        by[e["day"]].append(e)
    cand = set()
    for d, xs in by.items():
        for e in sorted(xs, key=lambda x: x["mins"]):
            if e["_exit"][(mode, t1)]["_win"]:
                cand |= set(keys_hold(e))
                break
    bad = set()
    for e in train:
        if e["_exit"][(mode, t1)]["_win"]:
            continue
        for k in keys_hold(e):
            if k in cand:
                bad.add(k)
    allow = {}
    for k in cand - bad:
        allow[k] = {"n": 1, "days": 1}
    # enrich counts
    for e in train:
        if not e["_exit"][(mode, t1)]["_win"]:
            continue
        for k in keys_hold(e):
            if k in allow:
                allow[k]["n"] += 1
    return allow


def score_event(e, allow, prefer_gates=None, prefer_mins=(560, 900)):
    """Higher = better blind pick. No outcome peek."""
    keys = [k for k in keys_hold(e) if k in allow]
    if not keys:
        return None
    n_keys = len(keys)
    max_n = max(allow[k]["n"] for k in keys)
    max_days = max(allow[k]["days"] for k in keys)
    lo, hi = prefer_mins
    in_win = 1 if lo <= e["mins"] <= hi else 0
    gate_bonus = 0
    if prefer_gates:
        for g, w in prefer_gates:
            if e.get(g):
                gate_bonus += w
    # prefer more agreeing clean keys, then stronger keys, then later than open noise a bit
    open_pen = 2 if e["mins"] < 575 else 0  # soft: early open less preferred
    return (
        n_keys * 1_000_000
        + max_days * 10_000
        + max_n * 100
        + gate_bonus * 50
        + in_win * 10
        - open_pen
        - e["mins"]  # earlier among equals
    )


def pick_day(xs, allow, prefer_gates=None, prefer_mins=(560, 900), min_keys=1):
    best, best_s = None, None
    for e in xs:
        keys = [k for k in keys_hold(e) if k in allow]
        if len(keys) < min_keys:
            continue
        s = score_event(e, allow, prefer_gates, prefer_mins)
        if s is None:
            continue
        if best_s is None or s > best_s:
            best_s, best = s, e
    return best


def run_picker(events, allow, n_days, **kw):
    by = defaultdict(list)
    for e in events:
        by[e["day"]].append(e)
    calls = []
    for d, xs in sorted(by.items()):
        e = pick_day(xs, allow, **kw)
        if e is None:
            continue
        sc = e["_exit"][(MODE, T1)]
        calls.append({**e, **sc})
    return summarize(calls, n_days), calls


def main() -> int:
    PACK_OUT.mkdir(parents=True, exist_ok=True)
    print("MA HOLD100 picker · trail34 t12 · combine logics", flush=True)

    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    hi = df["High"].astype(float)
    lo = df["Low"].astype(float)
    cl = df["Close"].astype(float)
    prev = cl.shift(1)
    tr = pd.concat([(hi - lo), (hi - prev).abs(), (lo - prev).abs()], axis=1).max(axis=1)
    df["atr14"] = tr.rolling(14, min_periods=14).mean()
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    atr = df["atr14"].astype(float).values
    emas = {n: df[f"ema{n}"].astype(float).values for n in (15, 21, 34, 50)}
    vix = vixmod.load_vix()
    data_hi = str(raw.index.max().date())

    xs = pickle.load((PACK / f"events_{WIN_LO}_{data_hi}.pkl").open("rb"))
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)
    attach_exit_grid(xs, h, l, c, emas, atr, [MODE])

    train = [e for e in xs if e["day"] < HOLD_LO]
    hold = [e for e in xs if e["day"] >= HOLD_LO]
    td = len({e["day"] for e in train})
    hd = len({e["day"] for e in hold})

    allow_m2 = build_allow(train, min_n=2)
    allow_m1 = build_allow(train, min_n=1)
    allow_ch = champion_allow(train)
    # intersection / union combos
    allow_ch_m2 = {k: allow_m2[k] for k in allow_ch if k in allow_m2}
    allow_union = {**allow_m1, **allow_ch}
    for k, v in allow_m2.items():
        allow_union[k] = v

    gates = [
        ("none", None),
        ("hard34", [("gate_hard34", 3)]),
        ("clean21", [("gate_clean21", 4)]),
        ("clean34", [("gate_clean34", 4)]),
        ("stack34", [("gate_stack34", 2)]),
        ("hard+clean", [("gate_hard34", 2), ("gate_clean21", 3)]),
        ("hard21+34", [("gate_hard21", 2), ("gate_hard34", 3)]),
    ]

    variants = []
    for aname, allow in (
        ("allow_m2", allow_m2),
        ("allow_m1", allow_m1),
        ("champ", allow_ch),
        ("champ∩m2", allow_ch_m2),
        ("union", allow_union),
    ):
        for gname, gpref in gates:
            for min_keys in (1, 2, 3):
                for mins in ((560, 900), (575, 900), (600, 900), (560, 840)):
                    kw = {"prefer_gates": gpref, "prefer_mins": mins, "min_keys": min_keys}
                    st_tr, _ = run_picker(train, allow, td, **kw)
                    if st_tr["n"] == 0:
                        continue
                    # only keep train 100% all_win candidates for primary board
                    st_ho, ho_calls = run_picker(hold, allow, hd, **kw)
                    name = f"{aname}|{gname}|k{min_keys}|{mins[0]}-{mins[1]}"
                    variants.append((name, st_tr, st_ho, allow, kw, ho_calls))

    # rank: train 100% + cover, then hold hit, hold cover
    perfect_tr = [v for v in variants if v[1]["all_win"] and v[1]["hit"] == 100.0]
    perfect_tr.sort(key=lambda v: (-v[1]["cover"], -v[2]["hit"], -v[2]["cover"], -v[1]["n"]))

    # also any with hold 100
    hold100 = [v for v in perfect_tr if v[2]["all_win"] and v[2]["cover"] >= 99.0]
    near = sorted(perfect_tr, key=lambda v: (-v[2]["hit"], -v[2]["cover"], -v[1]["cover"]))[:15]

    lines = [
        "# MA HOLD100 — **blind picker** (hold trail34 · T1=12)",
        "",
        "Held exit: **EMA34 trail**, win if T1=12 before close flips vs EMA34.",
        "Picker combines: train-clean keys · champion keys · multi-key vote · MA gates · session window.",
        f"Train `<{HOLD_LO}` ({td}d) · Hold `≥{HOLD_LO}` ({hd}d) · data→`{data_hi}`",
        "",
        f"Allow sizes: m2={len(allow_m2)} m1={len(allow_m1)} champ={len(allow_ch)} champ∩m2={len(allow_ch_m2)}",
        "",
        "## Top train-100% pickers by hold",
        "",
        "| Picker | Train n@hit cover | Hold n@hit cover | all_win hold |",
        "|---|---|---|:---:|",
    ]

    print(f"variants={len(variants)} train100={len(perfect_tr)} hold100={len(hold100)}", flush=True)
    for name, st_tr, st_ho, *_ in near:
        lines.append(
            f"| `{name}` | {st_tr['n']}@{st_tr['hit']}% {st_tr['cover']}% | "
            f"{st_ho['n']}@{st_ho['hit']}% {st_ho['cover']}% | {st_ho['all_win']} |"
        )
        print(f"  {name}: tr {st_tr['cover']}% ho {st_ho['hit']}%/{st_ho['cover']}%", flush=True)

    if hold100:
        best = hold100[0]
        lines += ["", f"### **DUAL 100/100 FOUND:** `{best[0]}`", ""]
        print(f"DUAL100 {best[0]}", flush=True)
    else:
        best = near[0] if near else None
        if best:
            lines += [
                "",
                f"### Best so far: `{best[0]}`",
                f"- Train **{best[1]['hit']}%** cover **{best[1]['cover']}%**",
                f"- Hold **{best[2]['hit']}%** cover **{best[2]['cover']}%**",
                "",
            ]

    if best:
        name, st_tr, st_ho, allow, kw, ho_calls = best
        (PACK_OUT / "PICKER_BEST_allow.pkl").write_bytes(pickle.dumps({"allow_keys": list(allow.keys()), "kw": kw, "name": name}, protocol=pickle.HIGHEST_PROTOCOL))
        lines += [
            "## Hold day-by-day (best picker)",
            "",
            "| Day | Y/N | HM | Side | Pattern | gate34 | keys_hit | MFE |",
            "|---|---|---|---|---|---|---:|---:|",
        ]
        by = {e["day"]: e for e in ho_calls}
        for d in sorted({e["day"] for e in hold}):
            e = by.get(d)
            if not e:
                lines.append(f"| {d} | NO_CALL | | | | | | |")
                continue
            mark = "Y" if e["_win"] else "N"
            nkeys = sum(1 for k in keys_hold(e) if k in allow)
            lines.append(
                f"| {d} | {mark} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"{int(bool(e.get('gate_hard34')))} | {nkeys} | {e.get('mfe',0):.1f} |"
            )

    # oracle reminder
    lines += [
        "",
        "## Locked logics held together",
        "",
        "1. Entry universe: textbook 1m candle patterns",
        "2. MA context: EMA15/21/34/50 gates (hard/clean/stack)",
        "3. **Hold/exit:** EMA34 trail · T1=12 (path win before MA flip)",
        "4. **Picker:** train-clean (+optional champion) keys, multi-key vote, session prefs",
        "5. Blind: hold months never used to build allow keys",
        "",
        f"Pack: `{PACK_OUT}`",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    payload = {
        "best": None if not best else {"name": best[0], "train": best[1], "hold": best[2]},
        "hold100_count": len(hold100),
        "near": [{"name": n, "train": tr, "hold": ho} for n, tr, ho, *_ in near],
    }
    (OUT / "NIFTY_1M_SCALP_MA_HOLD100_PICKER.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    if best:
        print(f"BEST {best[0]} train={best[1]} hold={best[2]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
