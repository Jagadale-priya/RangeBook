"""Compare 1/day vs multi-call under HELD gate (last 3m + show gap effect)."""
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
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402
from _diag_scalp_ma_hold100_picker import MODE, T1  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SCALP_MA_HOLD100_MULTICALL.md"


def take_calls(events, gap):
    by = defaultdict(list)
    for e in events:
        if held_gate(e):
            by[e["day"]].append(e)
    out = []
    for d, xs in sorted(by.items()):
        last = None
        for e in sorted(xs, key=lambda x: x["mins"]):
            if last is not None and e["mins"] - last < gap:
                continue
            sc = e["_exit"][(MODE, T1)]
            out.append({**e, **sc})
            last = e["mins"]
    return out


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
    hold = [e for e in xs if e["day"] >= hold_lo]
    # enrich only hold window events - still need full df arrays
    fwdmod.enrich_evt(hold, h, l, c, o)
    enrich_structure(hold, h, l, c, o, vix)
    enrich_prior3(hold, h, l, c, o)
    enrich_deep(hold, h, l, c, o, df)
    enrich_ma_layers(hold, df)
    enrich_ind(hold, df)
    attach_exit_grid(hold, h, l, c, emas, atr, [MODE])

    days = sorted({e["day"] for e in hold})
    nd = len(days)
    lines = [
        f"# HELD multi-call vs 1/day — last 3m `{hold_lo}`→`{data_hi}`",
        "",
        "Same gates/exit (DI+hard34+VWAP · EMA34 trail · T1=12). Only pacing changes.",
        "",
        "| Pace | Calls | Hit% | Days | Cover | cpd |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    print(f"last3m days={nd}", flush=True)
    for gap, label in ((10**9, "1/day (first only)"), (15, "multi gap≥15m"), (5, "multi gap≥5m"), (1, "multi gap≥1m")):
        calls = take_calls(hold, gap if gap < 10**8 else 10**9)
        # for 1/day force first only
        if label.startswith("1/day"):
            first = {}
            for e in calls:
                first.setdefault(e["day"], e)
            calls = list(first.values())
        st = summarize(calls, nd)
        print(f"{label}: n={st['n']} hit={st['hit']}% cover={st['cover']}% cpd={st['cpd']}", flush=True)
        lines.append(
            f"| {label} | {st['n']} | {st['hit']}% | {st['days']} | {st['cover']}% | {st['cpd']} |"
        )

    lines += [
        "",
        "## Read",
        "- **Yes, multi-call works mechanically** — same gates fire many times/day.",
        "- Hit% usually **falls** vs 1/day because extra signals add more MA-flip losses.",
        "- Use a **time gap** (e.g. 15–30m) if you want more calls without stacking noise.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
