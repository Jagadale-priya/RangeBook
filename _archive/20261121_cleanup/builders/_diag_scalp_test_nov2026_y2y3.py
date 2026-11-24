"""Test DENSE_Y2 and DENSE_Y3 on November 2026 only."""
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
from _diag_scalp_fail3_t20_sl10 import enrich_prior3, flag_sl10, T1, SL_MAX  # noqa: E402
from _diag_scalp_held_pre3_densify_1cpd import eval_book, stats  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402
from _diag_scalp_atlas_densify_100 import keys_combined  # noqa: E402

PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_wf100_2021"
OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SCALP_DENSE_Y2Y3_NOV2026.md"


def main() -> int:
    y2 = pickle.loads((PACK / "DENSE_Y2_micros.pkl").read_bytes())
    y3 = pickle.loads((PACK / "DENSE_Y3_micros.pkl").read_bytes())
    print(f"Y2 micros={len(y2)} Y3 micros={len(y3)} T1={T1} SL_MAX={SL_MAX}", flush=True)

    raw = base.load_existing_1m()
    print(f"data end={raw.index.max()}", flush=True)
    raw = raw[raw.index >= pd.Timestamp("2021-01-01", tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    vix = vixmod.load_vix()

    xs = pickle.load(next(PACK.glob("events_2026-01-01_*.pkl")).open("rb"))
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    flag_sl10(xs, h, l, c)
    enrich_deep(xs, h, l, c, o, df)

    nov = [e for e in xs if "2026-11-01" <= e["day"] <= "2026-11-30"]
    days = sorted({e["day"] for e in nov})
    print(f"NOV2026 events={len(nov)} days={days}", flush=True)

    for e in nov:
        e["_keys"] = set(keys_combined(e))

    lines = [
        "# DENSE_Y2 / DENSE_Y3 test — **November 2026**",
        "",
        f"Data through `{raw.index.max()}` · T1=**{T1}** · SL≤**{SL_MAX}** · path",
        f"Nov trading days in sample: **{', '.join(days)}** ({len(days)} days)",
        "",
        "| Book | Calls | Hit% | all_win | Days w/ call | Cover | Avg SL | 1/day n | 1/day hit |",
        "|---|---:|---:|:---:|---:|---:|---:|---:|---:|",
    ]

    for name, micros in [("DENSE_Y3", y3), ("DENSE_Y2", y2)]:
        calls = eval_book(nov, micros, keys_combined, h, l, c, 1)
        nd = len(days)
        st = stats(calls, nd)
        first = {}
        for e in sorted(calls, key=lambda x: (x["day"], x["mins"])):
            first.setdefault(e["day"], e)
        ones = list(first.values())
        one_hit = round(100.0 * sum(e["_win"] for e in ones) / max(len(ones), 1), 2) if ones else 0
        cover = round(100.0 * st["days"] / max(nd, 1), 1)
        print(f"==== {name} ====", flush=True)
        print(
            f"full n={st['n']} hit={st['hit']}% all_win={st['all_win']} "
            f"days={st['days']}/{nd} cover={cover}% avg_sl={st['avg_sl']}",
            flush=True,
        )
        print(f"1/day n={len(ones)} hit={one_hit}%", flush=True)
        lines.append(
            f"| **{name}** | {st['n']} | {st['hit']}% | {st['all_win']} | {st['days']} | "
            f"{cover}% | {st['avg_sl']} | {len(ones)} | {one_hit}% |"
        )

        by = defaultdict(list)
        for e in calls:
            by[e["day"]].append(e)
        lines.append("")
        lines.append(f"### {name} day-by-day")
        lines.append("")
        lines.append("| Day | n | Results |")
        lines.append("|---|---:|---|")
        for d in days:
            xs = by.get(d, [])
            if not xs:
                print(f"  {d} NO_CALL", flush=True)
                lines.append(f"| {d} | 0 | NO_CALL |")
                continue
            bits = []
            for e in xs:
                mark = "Y" if e["_win"] else "N"
                bits.append(
                    f"{mark} {e['hm']} {e['decision']} {e['primary']} {e['_st']} "
                    f"sl={e['_sl']:.1f} mfe={e['mfe']:.0f}"
                )
                print(
                    f"  {d} {mark} {e['hm']} {e['decision']} {e['primary']} "
                    f"{e['_st']} sl={e['_sl']:.1f} mfe={e['mfe']:.1f}",
                    flush=True,
                )
            lines.append(f"| {d} | {len(xs)} | {' · '.join(bits)} |")
        lines.append("")

    lines += [
        "Note: Nov 2026 sample is only sessions present in local 1m (through data end).",
        "These books include 2026 in historical 100% lock — this is a **hold-month replay**, not a blind OOS prove.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
