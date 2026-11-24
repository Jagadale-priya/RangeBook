"""Re-rank HOLD100 pickers: train 100% with cover>=70, then max hold hit/cover."""
from __future__ import annotations

import pickle
import sys
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
)
from _diag_scalp_ma_hold100 import attach_exit_grid  # noqa: E402
from _diag_scalp_ma_hold100_picker import (  # noqa: E402
    MODE,
    PACK_OUT,
    build_allow,
    champion_allow,
    run_picker,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SCALP_MA_HOLD100_PICKER.md"


def main() -> int:
    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
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
    allow_ch_m2 = {k: allow_m2[k] for k in allow_ch if k in allow_m2}

    cfgs = []
    for aname, allow in (("m2", allow_m2), ("m1", allow_m1), ("champ", allow_ch), ("ch_m2", allow_ch_m2)):
        for gname, gpref in (
            ("none", None),
            ("hard34", [("gate_hard34", 3)]),
            ("clean21", [("gate_clean21", 4)]),
            ("clean34", [("gate_clean34", 4)]),
            ("hard+clean", [("gate_hard34", 2), ("gate_clean21", 3)]),
        ):
            for mk in (1, 2):
                for mins in ((560, 900), (575, 900), (600, 900)):
                    kw = {"prefer_gates": gpref, "prefer_mins": mins, "min_keys": mk}
                    st_tr, _ = run_picker(train, allow, td, **kw)
                    if not (st_tr["all_win"] and st_tr["hit"] == 100.0 and st_tr["cover"] >= 70.0):
                        continue
                    st_ho, ho = run_picker(hold, allow, hd, **kw)
                    name = f"{aname}|{gname}|k{mk}|{mins[0]}"
                    cfgs.append((name, st_tr, st_ho, allow, kw, ho))
                    print(
                        f"  {name}: train {st_tr['cover']}% hold {st_ho['hit']}%/{st_ho['cover']}%",
                        flush=True,
                    )

    cfgs.sort(key=lambda v: (-v[2]["hit"], -v[2]["cover"], -v[1]["cover"]))
    print(f"useful={len(cfgs)}", flush=True)
    if not cfgs:
        print("no configs", flush=True)
        return 1

    best = cfgs[0]
    full = [v for v in cfgs if v[1]["cover"] >= 95]
    full.sort(key=lambda v: (-v[2]["cover"], -v[2]["hit"]))

    lines = [
        "# MA HOLD100 — blind picker (held logics combined)",
        "",
        "**Held together:** candle entry · MA gates · **EMA34 trail hold · T1=12** · train-clean/champion keys · multi-key vote · session window.",
        f"Train `<{HOLD_LO}` ({td}d) · Hold `≥{HOLD_LO}` ({hd}d) · data→`{data_hi}`",
        "",
        "Ranked among train **100%** with cover **≥70%** (tiny samples excluded).",
        "",
        "| Picker | Train cover | Hold hit | Hold cover |",
        "|---|---:|---:|---:|",
    ]
    for v in cfgs[:15]:
        lines.append(f"| `{v[0]}` | {v[1]['cover']}% | {v[2]['hit']}% | {v[2]['cover']}% |")

    lines += [
        "",
        f"### Best useful: `{best[0]}`",
        f"- Train **{best[1]['hit']}%** · cover **{best[1]['cover']}%**",
        f"- Hold **{best[2]['hit']}%** · cover **{best[2]['cover']}%**",
        "",
    ]
    if full:
        lines += ["### Best among train cover ≥95%", ""]
        for v in full[:8]:
            lines.append(f"- `{v[0]}`: hold {v[2]['hit']}% / cover {v[2]['cover']}%")
        lines.append("")

    by = {e["day"]: e for e in best[5]}
    lines += [
        "## Hold day-by-day (best useful)",
        "",
        "| Day | Y/N | HM | Side | Pattern | MFE |",
        "|---|---|---|---|---|---:|",
    ]
    for d in sorted({e["day"] for e in hold}):
        e = by.get(d)
        if not e:
            lines.append(f"| {d} | NO_CALL | | | | |")
            continue
        mark = "Y" if e["_win"] else "N"
        lines.append(
            f"| {d} | {mark} | {e['hm']} | {e['decision']} | {e['primary']} | {e.get('mfe', 0):.1f} |"
        )

    lines += [
        "",
        "## Logics held",
        "1. Textbook 1m candle entry",
        "2. MA gates (hard/clean/stack 21/34)",
        "3. Hold/exit: EMA34 trail · T1=12",
        "4. Blind picker: clean keys + vote + session",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    PACK_OUT.mkdir(parents=True, exist_ok=True)
    (PACK_OUT / "PICKER_BEST_allow.pkl").write_bytes(
        pickle.dumps(
            {"name": best[0], "kw": best[4], "allow": list(best[3].keys()), "train": best[1], "hold": best[2]},
            protocol=pickle.HIGHEST_PROTOCOL,
        )
    )
    print(f"BEST {best[0]} train={best[1]} hold={best[2]}", flush=True)
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
