"""Test held MA HOLD100 logic on last 3 months (blind).

Train: window start → before last-3m
Hold: last 3 months through data end
Exit: EMA34 trail · T1=12
Picker: train-clean keys (m2, k1) — same held stack
"""
from __future__ import annotations

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
    WIN_LO,
    PACK,
    add_ma_layers,
    enrich_ma_layers,
    summarize,
)
from _diag_scalp_ma_hold100 import attach_exit_grid, keys_hold  # noqa: E402
from _diag_scalp_ma_hold100_picker import (  # noqa: E402
    MODE,
    T1,
    build_allow,
    champion_allow,
    run_picker,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SCALP_MA_HOLD100_LAST3M.md"
PACK_OUT = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_ma_hold100"


def main() -> int:
    print("MA HOLD100 · last 3 months blind test", flush=True)
    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    data_hi = str(raw.index.max().date())
    # last 3 calendar months relative to data end
    end = pd.Timestamp(data_hi)
    hold_lo_ts = (end - pd.DateOffset(months=3)) + pd.Timedelta(days=1)
    hold_lo = str(hold_lo_ts.date())
    print(f"data_end={data_hi} hold_lo={hold_lo} (last 3m)", flush=True)

    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    hi = df["High"].astype(float)
    lo = df["Low"].astype(float)
    cl = df["Close"].astype(float)
    prev = cl.shift(1)
    trv = pd.concat([(hi - lo), (hi - prev).abs(), (lo - prev).abs()], axis=1).max(axis=1)
    df["atr14"] = trv.rolling(14, min_periods=14).mean()
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    atr = df["atr14"].astype(float).values
    emas = {n: df[f"ema{n}"].astype(float).values for n in (15, 21, 34, 50)}
    vix = vixmod.load_vix()

    xs = pickle.load((PACK / f"events_{WIN_LO}_{data_hi}.pkl").open("rb"))
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)
    attach_exit_grid(xs, h, l, c, emas, atr, [MODE])

    train = [e for e in xs if e["day"] < hold_lo]
    hold = [e for e in xs if e["day"] >= hold_lo]
    td = len({e["day"] for e in train})
    hd = len({e["day"] for e in hold})
    hold_days = sorted({e["day"] for e in hold})
    print(f"train days={td} hold days={hd} ({hold_days[0]}→{hold_days[-1]})", flush=True)

    allow_m2 = build_allow(train, min_n=2)
    allow_m1 = build_allow(train, min_n=1)
    allow_ch = champion_allow(train)
    print(f"allow m2={len(allow_m2)} m1={len(allow_m1)} champ={len(allow_ch)}", flush=True)

    # oracle first win / day
    def oracle_calls(events, n_days):
        by = defaultdict(list)
        for e in events:
            by[e["day"]].append(e)
        calls = []
        for d, rows in sorted(by.items()):
            hit = None
            for e in sorted(rows, key=lambda x: x["mins"]):
                sc = e["_exit"][(MODE, T1)]
                if sc["_win"]:
                    hit = {**e, **sc}
                    break
            if hit:
                calls.append(hit)
        return summarize(calls, n_days), calls

    st_or_tr, _ = oracle_calls(train, td)
    st_or_ho, or_ho = oracle_calls(hold, hd)
    print(f"ORACLE train={st_or_tr} hold={st_or_ho}", flush=True)

    variants = [
        ("m2_k1", allow_m2, {"prefer_gates": None, "prefer_mins": (560, 900), "min_keys": 1}),
        ("m2_k1_hard34", allow_m2, {"prefer_gates": [("gate_hard34", 3)], "prefer_mins": (560, 900), "min_keys": 1}),
        ("m2_k1_clean21", allow_m2, {"prefer_gates": [("gate_clean21", 4)], "prefer_mins": (560, 900), "min_keys": 1}),
        ("m1_k1", allow_m1, {"prefer_gates": None, "prefer_mins": (560, 900), "min_keys": 1}),
        ("champ_k1", allow_ch, {"prefer_gates": None, "prefer_mins": (560, 900), "min_keys": 1}),
        ("m2_k2", allow_m2, {"prefer_gates": None, "prefer_mins": (560, 900), "min_keys": 2}),
        ("m2_k1_after10", allow_m2, {"prefer_gates": None, "prefer_mins": (600, 900), "min_keys": 1}),
    ]

    lines = [
        "# MA HOLD100 — **last 3 months** blind test",
        "",
        f"Hold window **`{hold_lo}` → `{data_hi}`** · Train before that ({td} days) · Hold **{hd}** days",
        f"Exit held: **{MODE}** · T1=**{T1:.0f}** (EMA34 trail)",
        "",
        "| Mode | Train n@hit cover | Hold n@hit cover | all_win hold |",
        "|---|---|---|:---:|",
        f"| **ORACLE** | {st_or_tr['n']}@{st_or_tr['hit']}% {st_or_tr['cover']}% | "
        f"{st_or_ho['n']}@{st_or_ho['hit']}% {st_or_ho['cover']}% | {st_or_ho['all_win']} |",
    ]

    best = None
    best_calls = None
    for name, allow, kw in variants:
        st_tr, _ = run_picker(train, allow, td, **kw)
        st_ho, ho = run_picker(hold, allow, hd, **kw)
        print(f"  {name}: train {st_tr['n']}@{st_tr['hit']}%/{st_tr['cover']}% hold {st_ho['n']}@{st_ho['hit']}%/{st_ho['cover']}%", flush=True)
        lines.append(
            f"| `{name}` | {st_tr['n']}@{st_tr['hit']}% {st_tr['cover']}% | "
            f"{st_ho['n']}@{st_ho['hit']}% {st_ho['cover']}% | {st_ho['all_win']} |"
        )
        if st_tr["hit"] == 100.0 and st_tr["cover"] >= 90:
            if best is None or (st_ho["hit"], st_ho["cover"]) > (best[1]["hit"], best[1]["cover"]):
                best = (name, st_ho, st_tr)
                best_calls = ho

    # month breakdown for best + oracle
    def month_table(calls, days, title):
        rows = [f"### {title}", "", "| Month | n | Hit% | W | L | Cover days |", "|---|---:|---:|---:|---:|---:|"]
        by_m = defaultdict(list)
        for e in calls:
            by_m[e["day"][:7]].append(e)
        months = sorted({d[:7] for d in days})
        for m in months:
            xs = by_m.get(m, [])
            md = [d for d in days if d.startswith(m)]
            if not xs:
                rows.append(f"| {m} | 0 | 0% | 0 | 0 | 0/{len(md)} |")
                continue
            w = sum(1 for e in xs if e["_win"])
            hit = round(100.0 * w / len(xs), 2)
            rows.append(f"| {m} | {len(xs)} | {hit}% | {w} | {len(xs)-w} | {len({e['day'] for e in xs})}/{len(md)} |")
        rows.append("")
        return rows

    lines.append("")
    lines += month_table(or_ho, hold_days, "ORACLE by month")
    if best_calls is not None:
        lines += month_table(best_calls, hold_days, f"Best blind `{best[0]}` by month")
        lines += [
            f"### Day-by-day — `{best[0]}` (hold {best[1]['hit']}% / {best[1]['cover']}%)",
            "",
            "| Day | Y/N | HM | Side | Pattern | MFE |",
            "|---|---|---|---|---|---:|",
        ]
        by1 = {e["day"]: e for e in best_calls}
        for d in hold_days:
            e = by1.get(d)
            if not e:
                print(f"  {d} NO_CALL", flush=True)
                lines.append(f"| {d} | NO_CALL | | | | |")
                continue
            mark = "Y" if e["_win"] else "N"
            print(f"  {d} {mark} {e['hm']} {e['decision']} {e['primary']} mfe={e.get('mfe',0):.1f}", flush=True)
            lines.append(
                f"| {d} | {mark} | {e['hm']} | {e['decision']} | {e['primary']} | {e.get('mfe',0):.1f} |"
            )

    lines += [
        "",
        "## Exact logic tested",
        "1. Signal: textbook 1m candle",
        "2. Hold: stay while close with EMA34; **T1=12** before flip = win",
        "3. Blind picker: train-clean keys only (hold months unused)",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    PACK_OUT.mkdir(parents=True, exist_ok=True)
    if best:
        (PACK_OUT / "LAST3M_BEST.pkl").write_bytes(
            pickle.dumps({"name": best[0], "hold": best[1], "train": best[2], "hold_lo": hold_lo, "data_hi": data_hi}, protocol=pickle.HIGHEST_PROTOCOL)
        )
        print(f"BEST {best[0]} hold={best[1]}", flush=True)
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
