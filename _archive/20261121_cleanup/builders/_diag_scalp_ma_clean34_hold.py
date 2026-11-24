"""Day-by-day HOLD diagnose for clean34 MA book (last-year INIT)."""
from __future__ import annotations

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
    attach_scores,
    enrich_ma_layers,
    hunt_clean_1cpd,
    one_per_day,
    summarize,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SCALP_MA_CLEAN34_HOLD.md"


def main() -> int:
    micros_path = PACK / "BOOK_clean34_micros.pkl"
    print(f"clean34 micros file={micros_path.exists()} n={len(pickle.loads(micros_path.read_bytes())) if micros_path.exists() else 0}", flush=True)

    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    vix = vixmod.load_vix()

    data_hi = str(raw.index.max().date())
    xs = pickle.load((PACK / f"events_{WIN_LO}_{data_hi}.pkl").open("rb"))
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)
    attach_scores(xs, h, l, c)

    train = [e for e in xs if e["day"] < HOLD_LO]
    hold = [e for e in xs if e["day"] >= HOLD_LO]
    hold_days = sorted({e["day"] for e in hold})
    train_days = sorted({e["day"] for e in train})

    gate = lambda e: e.get("gate_clean34")
    chosen, tr1, ho_full, ho1 = hunt_clean_1cpd(train, hold, h, l, c, gate, min_train=2)
    st_tr = summarize(tr1, len(train_days))
    st_full = summarize(ho_full, len(hold_days))
    st_1 = summarize(ho1, len(hold_days))

    print(f"micros={len(chosen)} train1d={st_tr} hold_full={st_full} hold_1d={st_1}", flush=True)

    wins = [e for e in ho1 if e["_win"]]
    loss = [e for e in ho1 if not e["_win"]]

    # also gate-only 1/day adaptive (no micro lock) for contrast
    gate_hold = []
    by = defaultdict(list)
    for e in hold:
        if gate(e) and e.get("_sc_adapt"):
            by[e["day"]].append({**e, **e["_sc_adapt"]})
    for d in hold_days:
        xs_d = by.get(d, [])
        if not xs_d:
            continue
        gate_hold.append(sorted(xs_d, key=lambda x: x["mins"])[0])
    gate_hold = fwdmod.apply_gap(gate_hold, 1)
    st_gate = summarize(gate_hold, len(hold_days))

    lines = [
        "# clean34 — **HOLD unknown** diagnose",
        "",
        f"Hold window **`{HOLD_LO}` → `{data_hi}`** · days **{len(hold_days)}**",
        f"Gate: `clean34` = hard EMA34 (align+stack-with+slope) + `close_ok` + not `fail_risk`",
        f"Book: **{len(chosen)}** micros locked 100% on train · evaluated blind on hold",
        "",
        "| Mode | n | Hit% | Days | Cover | Avg T1 | Avg SL | all_win |",
        "|---|---:|---:|---:|---:|---:|---:|:---:|",
        f"| Train 1/day (lock) | {st_tr['n']} | {st_tr['hit']}% | {st_tr['days']} | {st_tr['cover']}% | {st_tr['avg_t1']} | {st_tr['avg_sl']} | {st_tr['all_win']} |",
        f"| Hold full (all micro matches) | {st_full['n']} | {st_full['hit']}% | {st_full['days']} | {st_full['cover']}% | {st_full['avg_t1']} | {st_full['avg_sl']} | {st_full['all_win']} |",
        f"| **Hold 1/day (first call)** | **{st_1['n']}** | **{st_1['hit']}%** | **{st_1['days']}** | **{st_1['cover']}%** | **{st_1['avg_t1']}** | **{st_1['avg_sl']}** | **{st_1['all_win']}** |",
        f"| Hold gate-only 1/day (no micro) | {st_gate['n']} | {st_gate['hit']}% | {st_gate['days']} | {st_gate['cover']}% | {st_gate['avg_t1']} | {st_gate['avg_sl']} | {st_gate['all_win']} |",
        "",
        f"Wins **{len(wins)}** · Losses **{len(loss)}** · SL-first with MFE≥T1: "
        f"**{sum(1 for e in loss if e.get('mfe', 0) >= e.get('_t1', 20))}**",
        "",
        "## By month (1/day)",
        "",
        "| Month | n | Hit% | W | L | AvgT1 | AvgSL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    by_m = defaultdict(list)
    for e in ho1:
        by_m[e["day"][:7]].append(e)
    for m in sorted(by_m):
        xs_m = by_m[m]
        w = sum(1 for e in xs_m if e["_win"])
        hit = round(100.0 * w / len(xs_m), 2)
        lines.append(
            f"| {m} | {len(xs_m)} | {hit}% | {w} | {len(xs_m)-w} | "
            f"{round(sum(e['_t1'] for e in xs_m)/len(xs_m),1)} | "
            f"{round(sum(e['_sl'] for e in xs_m)/len(xs_m),1)} |"
        )
        print(f"  {m} n={len(xs_m)} hit={hit}%", flush=True)

    lines += [
        "",
        "## Mix on hold 1/day",
        "",
        f"- Patterns: {', '.join(f'{p}×{n}' for p,n in Counter(e.get('primary') for e in ho1).most_common(10))}",
        f"- Side: {dict(Counter(e.get('decision') for e in ho1))}",
        f"- SL style: {', '.join(f'{p}×{n}' for p,n in Counter(e.get('_st') for e in ho1).most_common())}",
        f"- T1 used: {', '.join(f'{p}×{n}' for p,n in Counter(e.get('_t1') for e in ho1).most_common())}",
        f"- Loss patterns: {', '.join(f'{p}×{n}' for p,n in Counter(e.get('primary') for e in loss).most_common(8))}",
        f"- Win patterns: {', '.join(f'{p}×{n}' for p,n in Counter(e.get('primary') for e in wins).most_common(8))}",
        "",
        "## Day-by-day (1/day first call)",
        "",
        "| Day | Result | HM | Side | Pattern | T1 | SL style | SL | MFE | MAE | stack34 | dist34 |",
        "|---|---|---|---|---|---:|---|---:|---:|---:|---|---|",
    ]

    by1 = {e["day"]: e for e in ho1}
    for d in hold_days:
        e = by1.get(d)
        if e is None:
            print(f"  {d} NO_CALL", flush=True)
            lines.append(f"| {d} | NO_CALL | | | | | | | | | | |")
            continue
        mark = "Y" if e["_win"] else "N"
        print(
            f"  {d} {mark} {e['hm']} {e['decision']} {e['primary']} t1={e['_t1']} "
            f"{e['_st']} sl={e['_sl']:.1f} mfe={e.get('mfe',0):.1f}",
            flush=True,
        )
        lines.append(
            f"| {d} | {mark} | {e['hm']} | {e['decision']} | {e['primary']} | {e['_t1']:.0f} | "
            f"{e['_st']} | {e['_sl']:.1f} | {e.get('mfe',0):.1f} | {e.get('mae',0):.1f} | "
            f"{e.get('ma_stack34')} | {e.get('dist34_bin')} |"
        )

    lines += [
        "",
        "## Loss sample detail (all hold 1/day losses)",
        "",
        "| Day | HM | Side | Pattern | T1 | SL | MFE | MAE | Why note |",
        "|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    for e in sorted(loss, key=lambda x: (x["day"], x["mins"])):
        mfe = float(e.get("mfe") or 0)
        t1 = float(e["_t1"])
        note = "SL-first (MFE later ≥T1)" if mfe >= t1 else ("weak MFE" if mfe < t1 * 0.5 else "path SL before T1")
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | {t1:.0f} | "
            f"{e['_sl']:.1f} | {mfe:.1f} | {float(e.get('mae') or 0):.1f} | {note} |"
        )

    lines += [
        "",
        "## Simple read",
        "",
        f"- Hold 1/day hit **{st_1['hit']}%** on **{st_1['n']}/{len(hold_days)}** days — cover almost full, accuracy not 100%.",
        f"- Gate-only (no fingerprint lock) hold 1/day was **{st_gate['hit']}%** — micros help a bit vs raw gate when they do.",
        "- Many losses are **SL-first**: price eventually travels ≥T1 after stop already hit.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
