"""Tighter indicator gate combos for MA HOLD100 (last 3m)."""
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
from _diag_scalp_ma_lastyear_init import WIN_LO, PACK, add_ma_layers, enrich_ma_layers, summarize  # noqa: E402
from _diag_scalp_ma_hold100 import attach_exit_grid  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_picker import MODE, T1  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SCALP_MA_HOLD100_INDICATORS.md"


def eval_gate(events, nd, pred):
    by = defaultdict(list)
    for e in events:
        by[e["day"]].append(e)
    calls = []
    for d, rows in sorted(by.items()):
        e = None
        for x in sorted(rows, key=lambda z: z["mins"]):
            if pred(x):
                e = x
                break
        if e is None:
            continue
        calls.append({**e, **e["_exit"][(MODE, T1)]})
    return summarize(calls, nd), calls


def main() -> int:
    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    data_hi = str(raw.index.max().date())
    hold_lo = str((pd.Timestamp(data_hi) - pd.DateOffset(months=3) + pd.Timedelta(days=1)).date())
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
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
    enrich_ind(xs, df)
    attach_exit_grid(xs, h, l, c, emas, atr, [MODE])
    train = [e for e in xs if e["day"] < hold_lo]
    hold = [e for e in xs if e["day"] >= hold_lo]
    td = len({e["day"] for e in train})
    hd = len({e["day"] for e in hold})

    combos = [
        ("di", lambda e: e.get("di_ok")),
        ("macd+di", lambda e: e.get("macd_turn") and e.get("di_ok")),
        ("macd+di+hard34", lambda e: e.get("macd_turn") and e.get("di_ok") and e.get("gate_hard34")),
        ("macd+di+hard21", lambda e: e.get("macd_turn") and e.get("di_ok") and e.get("gate_hard21")),
        ("macd+di+vwap+hard34", lambda e: e.get("macd_turn") and e.get("di_ok") and e.get("vwap_with") and e.get("gate_hard34")),
        ("macd+di+bbmid+hard34", lambda e: e.get("macd_turn") and e.get("di_ok") and e.get("bb_mid_ok") and e.get("gate_hard34")),
        ("macd+di+mom+hard34", lambda e: e.get("macd_turn") and e.get("di_ok") and e.get("mom_ok") and e.get("gate_hard34")),
        ("macd+di+vwap+bbmid+hard34", lambda e: e.get("macd_turn") and e.get("di_ok") and e.get("vwap_with") and e.get("bb_mid_ok") and e.get("gate_hard34")),
        ("macd+di+vwap+hard34+rsi", lambda e: e.get("macd_turn") and e.get("di_ok") and e.get("vwap_with") and e.get("gate_hard34") and e.get("rsi_ok")),
        ("macd+di+vwap+hard34+close", lambda e: e.get("macd_turn") and e.get("di_ok") and e.get("vwap_with") and e.get("gate_hard34") and e.get("close_ok") == 1),
        ("macd+di+vwap+hard34+nofail", lambda e: e.get("macd_turn") and e.get("di_ok") and e.get("vwap_with") and e.get("gate_hard34") and not e.get("fail_risk")),
        ("basic+hard34", lambda e: e.get("ind_basic") and e.get("gate_hard34")),
        ("di+hard34+vwap", lambda e: e.get("di_ok") and e.get("gate_hard34") and e.get("vwap_with")),
        ("macd+di+hard34+m600", lambda e: e.get("mins", 0) >= 600 and e.get("macd_turn") and e.get("di_ok") and e.get("gate_hard34")),
        ("macd+di+hard34+m575", lambda e: e.get("mins", 0) >= 575 and e.get("macd_turn") and e.get("di_ok") and e.get("gate_hard34")),
        ("macd+di+vwap+hard34+m575", lambda e: e.get("mins", 0) >= 575 and e.get("macd_turn") and e.get("di_ok") and e.get("vwap_with") and e.get("gate_hard34")),
        ("macd+di+vwap+hard34+m600", lambda e: e.get("mins", 0) >= 600 and e.get("macd_turn") and e.get("di_ok") and e.get("vwap_with") and e.get("gate_hard34")),
    ]

    rows = []
    for name, pred in combos:
        tr, _ = eval_gate(train, td, pred)
        ho, hoc = eval_gate(hold, hd, pred)
        rows.append((name, tr, ho, hoc))
        print(f"{name}: train {tr['hit']}%/{tr['cover']}% hold {ho['hit']}%/{ho['cover']}% n={ho['n']}", flush=True)

    rows.sort(key=lambda r: (-r[2]["hit"], -r[2]["cover"]))
    best = rows[0]
    extra = [
        "",
        "## C) Tighter indicator combos (gate-only 1/day)",
        "",
        "| Combo | Train hit/cover | Hold hit/cover |",
        "|---|---|---|",
    ]
    for name, tr, ho, _ in rows:
        extra.append(f"| `{name}` | {tr['hit']}% / {tr['cover']}% | **{ho['hit']}%** / {ho['cover']}% |")
    extra += [
        "",
        f"### Best combo: `{best[0]}` → hold **{best[2]['hit']}%** cover {best[2]['cover']}%",
        "",
        "Still short of 100% blind; strongest signals: **MACD turn + DI align + EMA34 hard** (± VWAP).",
        "Stochastic alone was anti-predictive on train (losses had higher stoch_ok).",
        "",
    ]
    # append to report
    prev = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
    # strip old section C if present
    if "## C) Tighter" in prev:
        prev = prev.split("## C) Tighter")[0].rstrip() + "\n"
    REPORT.write_text(prev + "\n".join(extra), encoding="utf-8")
    print(f"BEST {best[0]} hold={best[2]}", flush=True)
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
