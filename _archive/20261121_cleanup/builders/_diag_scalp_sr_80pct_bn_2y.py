"""RESEARCH ONLY — validate NIFTY ≥80% entry logic on BANKNIFTY (max available ~2y).

Logic under test (from NIFTY_1M_SR_80PCT_DEEP.md):
  L80 = HELD
       ∧ not into session extreme
       ∧ clear_path (room_fav ≥ 1.5×ATR)
       ∧ control + sweep (buyer/seller bar + wick with side)
       ∧ |DI spread| ≥ 8
       ∧ time ≥ 11:00 IST

Also report L80_MID (11:00–13:00 only) and baselines.

Accuracy (same defs as NIFTY study):
  Acc%    MFE≥20 and MFE > MAE
  Dom%    MFE≥15 and MFE ≥ 1.5×MAE
  Dom20%  MFE≥20 and MFE ≥ 1.5×MAE
  OneDir% MFE≥20 and MFE ≥ 2×MAE
  Path12s +12 before −8
  AccATR  MFE≥2×ATR and MFE > MAE   (BN-fair scale)

  python -u prod_live/tests/builders/_diag_scalp_sr_80pct_bn_2y.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
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
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers, enrich_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402
from _diag_scalp_sr_highmove_proven import (  # noqa: E402
    HORIZON,
    enrich_sr_archetypes,
    in_session,
    one_per_gap,
    score_path,
)
from _diag_scalp_sr_80pct_deep import enrich_deep_atoms, score_timing, summarize  # noqa: E402

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

BN_CSV = ROOT / "stock_signal_data" / "fno_validate" / "BANKNIFTY_1m_kite.csv"
OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "BANKNIFTY_1M_SR_80PCT_LOGIC_2Y.md"
REPORT_JSON = OUT / "BANKNIFTY_1M_SR_80PCT_LOGIC_2Y.json"


def load_bn_1m() -> pd.DataFrame:
    if not BN_CSV.is_file():
        raise FileNotFoundError(BN_CSV)
    raw = base._norm(pd.read_csv(BN_CSV))
    print(f"  BANKNIFTY_1m_kite.csv: {len(raw)} bars {raw.index.min()} → {raw.index.max()}", flush=True)
    return raw


def add_bn_metrics(events):
    for e in events:
        a = float(e.get("atr") or 8.0)
        mfe = float(e.get("mfe") or 0)
        mae = float(e.get("mae") or 0)
        e["acc_atr"] = bool(mfe >= 2.0 * a and mfe > mae)
        e["dom_atr"] = bool(mfe >= 1.5 * a and mfe >= 1.5 * max(mae, 1.0))
        e["mfe2atr"] = mfe >= 2.0 * a


def gate_l80(e) -> bool:
    """Primary NIFTY ≥80% Acc logic (after1100 variant — larger n)."""
    return bool(
        e.get("held")
        and e.get("not_extreme")
        and e.get("clear15")
        and e.get("ctrl_sweep")
        and e.get("di_ge8")
        and e.get("after1100")
    )


def gate_l80_mid(e) -> bool:
    """Mid-slot variant (11:00–13:00) — higher Acc on NIFTY, smaller n."""
    return bool(
        e.get("held")
        and e.get("not_extreme")
        and e.get("clear15")
        and e.get("ctrl_sweep")
        and e.get("di_ge8")
        and e.get("mid_slot")
    )


def gate_l80_tier(e) -> bool:
    return bool(
        e.get("held")
        and e.get("not_extreme")
        and e.get("clear15")
        and e.get("tier_ab")
        and e.get("di_ge8")
        and e.get("after1100")
    )


GATES = [
    ("L80 · HELD+clear15+ctrl_sweep+DI≥8+after1100", gate_l80),
    ("L80_MID · same + mid_slot(11–13)", gate_l80_mid),
    ("L80_TIER · HELD+clear15+TierAB+DI≥8+after1100", gate_l80_tier),
    ("BASE · HELD raw", lambda e: bool(e.get("held"))),
    ("BASE · HELD+clear15", lambda e: bool(e.get("held") and e.get("clear15"))),
    ("BASE · TierAB+clear15", lambda e: bool(e.get("tier_ab") and e.get("clear15"))),
]


def summarize_bn(rows, label):
    s = summarize(rows, label)
    n = len(rows)
    if not n:
        s["acc_atr"] = s["dom_atr"] = s["mfe2atr"] = None
        return s

    def pct(key):
        return round(100.0 * sum(1 for e in rows if e.get(key)) / n, 2)

    s["acc_atr"] = pct("acc_atr")
    s["dom_atr"] = pct("dom_atr")
    s["mfe2atr"] = pct("mfe2atr")
    return s


def month_table(rows, metric="acc"):
    by = defaultdict(list)
    for e in rows:
        by[e["day"][:7]].append(e)
    out = []
    for m in sorted(by):
        xs = by[m]
        n = len(xs)
        pct = round(100.0 * sum(1 for e in xs if e.get(metric)) / n, 2) if n else None
        out.append((m, n, pct))
    return out


def build_pool(raw):
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    day_lo = str(df.index.min().date())
    day_hi = str(df.index.max().date())
    print(f"  collect events {day_lo}→{day_hi}…", flush=True)
    events = scalp.collect_scalp_events(df, day_lo, day_hi)
    enrich_ma_layers(events, df)
    enrich_ind(events, df)
    setup.apply_setup_enrichment(events, df)
    enrich_sr_archetypes(events, df)
    score_path(events, df)
    score_timing(events, df)
    enrich_deep_atoms(events, df)
    add_bn_metrics(events)
    pool = [e for e in events if in_session(e)]
    return df, pool


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("BANKNIFTY validate L80 logic (RESEARCH ONLY)", flush=True)

    raw = load_bn_1m()
    data_hi = raw.index.max()
    data_lo = raw.index.min()
    # request last 2y; clamp to available
    want_lo = data_hi - pd.DateOffset(years=2)
    use_lo = max(data_lo, pd.Timestamp(want_lo))
    # warmup for MA/ATR
    warm = use_lo - pd.Timedelta(days=15)
    raw = raw[raw.index >= warm]
    print(
        f"  requested 2y from {want_lo.date()} · available from {data_lo.date()} · "
        f"using {use_lo.date()} → {data_hi.date()}",
        flush=True,
    )

    df, pool_all = build_pool(raw)
    pool = [e for e in pool_all if e["day"] >= str(use_lo.date())]
    days = sorted({e["day"] for e in pool})
    print(f"pool={len(pool)} days={len(days)} {days[0] if days else '?'}→{days[-1] if days else '?'}", flush=True)

    # slices
    days_2m = set(days[-45:]) if len(days) > 45 else set(days)
    days_6m = set(days[-120:]) if len(days) > 120 else set(days)
    # calendar year splits inside available
    y1_lo = str((data_hi - pd.DateOffset(years=1) + pd.Timedelta(days=1)).date())
    slices = {
        "ALL_available": pool,
        "LAST_1Y": [e for e in pool if e["day"] >= y1_lo],
        "LAST_6M": [e for e in pool if e["day"] in days_6m],
        "LAST_2M": [e for e in pool if e["day"] in days_2m],
    }

    results = []
    for gname, gfn in GATES:
        for stag, spool in slices.items():
            sub = [e for e in spool if gfn(e)]
            s = summarize_bn(sub, f"{gname} · {stag}")
            gap = summarize_bn(one_per_gap(sub, gap=15), f"{gname} · {stag} · gap15")
            results.append(
                {
                    "gate": gname,
                    "slice": stag,
                    "stats": s,
                    "gap15": gap,
                    "months_acc": month_table(sub, "acc"),
                }
            )
            print(
                f"  {gname} | {stag}: n={s['n']} Acc={s['acc']} Dom20={s['dom20']} "
                f"OneDir={s['one_dir']} AccATR={s['acc_atr']} Path12s={s['path12_strict']}",
                flush=True,
            )

    # focus L80 detail
    l80_all = [e for e in pool if gate_l80(e)]
    l80_gap = one_per_gap(l80_all, gap=15)
    hits = [e for e in l80_all if e.get("acc")][:15]
    misses = [e for e in l80_all if not e.get("acc")][:12]

    lines = [
        "# BANKNIFTY 1m — Validate NIFTY ≥80% Entry Logic",
        "",
        "> **RESEARCH ONLY — not wired to live.**",
        "",
        f"Data file: `{BN_CSV.name}` · bars {data_lo.date()} → {data_hi.date()}.",
        f"Requested **last 2 years**; available history starts **{data_lo.date()}** "
        f"(~{round((data_hi - data_lo).days / 30.4, 1)} months). "
        f"Test window used: **{days[0] if days else '?'} → {days[-1] if days else '?'}** "
        f"({len(days)} sessions) · horizon {HORIZON} bars · 09:30–14:30.",
        "",
        "## Logic under test (from NIFTY study)",
        "",
        "```",
        "L80 entry when ALL true:",
        "  1. HELD base     = DI_ok ∧ hard34 ∧ VWAP_with",
        "  2. not_extreme   = NOT buying near session high / selling near session low",
        "  3. clear15       = room_fav ≥ 1.5 × ATR  (space to run toward next S/R)",
        "  4. ctrl_sweep    = control bar (buyer/seller) AND wick sweep with side",
        "  5. di_ge8        = |plus_DI − minus_DI| ≥ 8",
        "  6. after1100     = clock ≥ 11:00 IST",
        "",
        "L80_MID = same but mid_slot 11:00–13:00 instead of after1100",
        "```",
        "",
        "Accuracy defs (pts, same as NIFTY) + **AccATR** (MFE≥2×ATR & MFE>MAE) for BN scale.",
        "",
        "## Results by gate × window",
        "",
        "| Gate | Slice | n | Acc% | Dom20% | OneDir% | Path12s% | AccATR% | avgMFE | avgMAE | edge |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for r in results:
        s = r["stats"]
        if s["n"] == 0:
            lines.append(
                f"| `{r['gate']}` | {r['slice']} | 0 | — | — | — | — | — | — | — | — |"
            )
            continue
        lines.append(
            f"| `{r['gate']}` | {r['slice']} | {s['n']} | **{s['acc']}** | {s['dom20']} | "
            f"{s['one_dir']} | {s['path12_strict']} | {s['acc_atr']} | {s['avg_mfe']} | "
            f"{s['avg_mae']} | {s['avg_edge']} |"
        )

    lines += [
        "",
        "## L80 gap-15 multi-call book (deployment shape)",
        "",
        "| Slice | n | Acc% | Dom20% | OneDir% | AccATR% | avgMFE | avgMAE | edge |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        if r["gate"].startswith("L80 ·"):
            g = r["gap15"]
            if g["n"] == 0:
                lines.append(f"| {r['slice']} gap15 | 0 | — | — | — | — | — | — | — |")
            else:
                lines.append(
                    f"| {r['slice']} gap15 | {g['n']} | **{g['acc']}** | {g['dom20']} | "
                    f"{g['one_dir']} | {g['acc_atr']} | {g['avg_mfe']} | {g['avg_mae']} | {g['avg_edge']} |"
                )

    lines += [
        "",
        "## L80 monthly Acc% (ALL available)",
        "",
        "| Month | n | Acc% |",
        "|---|---:|---:|",
    ]
    for m, n, pct in month_table(l80_all, "acc"):
        mark = " ✅" if pct is not None and pct >= 80 else ("" if pct is None else "")
        lines.append(f"| {m} | {n} | {pct}{mark} |")

    lines += [
        "",
        f"L80 ALL n={len(l80_all)} · after gap15 n={len(l80_gap)}",
        "",
        "## Sample L80 hits (Acc)",
        "",
        "| Day | HM | Side | Regime | ATR | room_fav | MFE | MAE | AccATR |",
        "|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    for e in hits:
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e.get('regime')} | "
            f"{e.get('atr')} | {e.get('room_fav')} | {e['mfe']} | {e['mae']} | {e.get('acc_atr')} |"
        )
    lines += [
        "",
        "## Sample L80 misses (!Acc)",
        "",
        "| Day | HM | Side | Regime | into_ext | MFE | MAE |",
        "|---|---|---|---|---|---:|---:|",
    ]
    for e in misses:
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e.get('regime')} | "
            f"{e.get('into_sess_extreme')} | {e['mfe']} | {e['mae']} |"
        )

    # verdict
    focus = next(
        (r for r in results if r["gate"].startswith("L80 ·") and r["slice"] == "ALL_available"),
        None,
    )
    verdict = "INCONCLUSIVE"
    note = ""
    if focus and focus["stats"]["n"]:
        acc = focus["stats"]["acc"]
        n = focus["stats"]["n"]
        if acc >= 80 and n >= 20:
            verdict = "PASS ≥80% Acc on available BN history"
        elif acc >= 70:
            verdict = "NEAR — Acc≥70% but below 80% lock bar"
        else:
            verdict = "FAIL — Acc below 70% on BN (NIFTY gate does not transfer raw)"
        note = f"ALL Acc={acc}% n={n} · AccATR={focus['stats']['acc_atr']}% · edge={focus['stats']['avg_edge']}"

    lines += [
        "",
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
        note,
        "",
        "Still **not live**. If BN AccATR holds while pt Acc differs, consider ATR-scaled thresholds for BN.",
        "",
        f"Elapsed {time.time() - t0:.0f}s",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "verdict": verdict,
                "note": note,
                "data_lo": str(data_lo.date()),
                "data_hi": str(data_hi.date()),
                "days": len(days),
                "results": [
                    {
                        "gate": r["gate"],
                        "slice": r["slice"],
                        "stats": r["stats"],
                        "gap15": r["gap15"],
                        "months_acc": r["months_acc"],
                    }
                    for r in results
                ],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {REPORT}", flush=True)
    print(f"VERDICT: {verdict} | {note}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
