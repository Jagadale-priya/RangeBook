"""Ablate PA structure improvements vs v1 · lock best · retest today.

  python -u prod_live/tests/builders/_research_pa_structure_v2_ablate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "market"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
import path_setup  # noqa: F401,E402
import kite_data  # noqa: E402

from prod_live.logic import pa_structure_live as pa  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
MD = OUT / "PA_STRUCTURE_V2_ABLATE.md"
JS = OUT / "PA_STRUCTURE_V2_ABLATE.json"
TODAY_MD = OUT / "PA_STRUCTURE_TODAY_LIVE.md"
TODAY_JS = OUT / "PA_STRUCTURE_TODAY_LIVE.json"


def fetch_1m(days: int = 25) -> pd.DataFrame:
    print(f"Pulling Kite NIFTY 1m · {days}d …", flush=True)
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=days, keep_partial=False
    )
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    print(f"  bars={len(bars)}  {bars.index.min()} → {bars.index.max()}", flush=True)
    return bars


def score(s: dict) -> float:
    """Rank: prefer hit% then avg_R then sum_pts; require n>=8."""
    if not s or not s.get("n") or s["n"] < 8:
        return -999.0
    hit = float(s.get("hit_pct") or 0)
    ar = float(s.get("avg_R") or 0)
    sp = float(s.get("sum_pts") or 0)
    return hit * 2.0 + ar * 40.0 + sp / 100.0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    bars = fetch_1m(25)
    days = sorted({str(ts.date()) for ts in bars.index})
    today = days[-1]
    last10 = set(days[-10:])
    today_bars = bars[bars.index.strftime("%Y-%m-%d") == today]

    rows = []
    by_prof = {}
    for name, cfg in pa.profiles().items():
        print(f"  profile {name} …", flush=True)
        allc = pa.scan_session(bars, settle=True, cfg=cfg)
        c10 = [c for c in allc if c.day in last10]
        ct = pa.scan_session(today_bars, settle=True, cfg=cfg)
        s_all = pa.summarize(allc)
        s10 = pa.summarize(c10)
        st = pa.summarize(ct)
        row = {
            "name": name,
            "full": s_all,
            "last10": s10,
            "today": st,
            "today_calls": [c.to_dict() for c in ct],
            "score_full": round(score(s_all), 3),
            "score_last10": round(score(s10), 3),
        }
        rows.append(row)
        by_prof[name] = row
        print(
            f"    full n={s_all.get('n')} hit={s_all.get('hit_pct')} "
            f"avgR={s_all.get('avg_R')} sum={s_all.get('sum_pts')} | "
            f"today n={st.get('n')} hit={st.get('hit_pct')} sum={st.get('sum_pts')}",
            flush=True,
        )

    # pick best by last10 then full (stability)
    ranked = sorted(
        rows, key=lambda r: (r["score_last10"], r["score_full"]), reverse=True
    )
    best = ranked[0]
    best_name = best["name"]
    print(f"BEST={best_name} score_l10={best['score_last10']}", flush=True)

    # lock CFG to best profile for live (persisted)
    locked = pa.profiles()[best_name]
    pa.save_locked_cfg(locked)
    pa.CFG = locked
    ct_best = pa.scan_session(today_bars, settle=True, cfg=locked)
    pa.save_ledger(
        {
            "desk": pa.DESK,
            "logic_ver": pa.LOGIC_VER,
            "cfg_name": best_name,
            "calls": [],
            "updated_at": pd.Timestamp.now().isoformat(),
        }
    )
    ledger_meta = pa.append_live_calls(ct_best, mark_fire=True)

    payload = {
        "today": today,
        "best": best_name,
        "ranked": [
            {
                "name": r["name"],
                "score_last10": r["score_last10"],
                "score_full": r["score_full"],
                "full": r["full"],
                "last10": r["last10"],
                "today": r["today"],
            }
            for r in ranked
        ],
        "best_today_calls": [c.to_dict() for c in ct_best],
        "ledger": ledger_meta,
        "improvements": [
            "MIN_RISK 9 (cut tight-SL noise losses)",
            "Strict HTF up/down only",
            "OR-side align vs OR mid",
            "Sweep depth/wick/reclaim quality",
            "Break momentum 2-of-3",
            "Side-flip + post-loss cooldown",
            "Trade window 09:50–14:30 · max 3/day",
        ],
    }
    JS.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# PA Structure v2 ablation · {today}",
        "",
        f"**Locked live profile:** `{best_name}`",
        "",
        "## Why we changed (v1 loss autopsy)",
        "",
        "- Losses avg risk **13.4** / MFE **5.6** vs wins risk **17.3** / MFE **34.7**",
        "- Tight SL + weak sweeps stopped out before follow-through",
        "- Fix: higher MIN_RISK, sweep quality, OR-side + strict HTF, cooldowns",
        "",
        "## Profile comparison",
        "",
        "| Profile | Full N | Hit% | AvgR | Sum | L10 N | L10 Hit% | L10 AvgR | Today N | Today Hit% | Today Sum | Score L10 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in ranked:
        f, l, t = r["full"], r["last10"], r["today"]
        lines.append(
            f"| {'**'+r['name']+'**' if r['name']==best_name else r['name']} | "
            f"{f.get('n')} | {f.get('hit_pct')} | {f.get('avg_R')} | {f.get('sum_pts')} | "
            f"{l.get('n')} | {l.get('hit_pct')} | {l.get('avg_R')} | "
            f"{t.get('n')} | {t.get('hit_pct')} | {t.get('sum_pts')} | {r['score_last10']} |"
        )

    st = best["today"]
    lines += [
        "",
        f"## Today with locked `{best_name}`",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Calls | **{st.get('n', 0)}** |",
        f"| Hit | **{st.get('hit_pct')}%** |" if st.get("n") else "| Hit | — |",
        f"| Avg R | {st.get('avg_R')} |",
        f"| Sum pts | {st.get('sum_pts')} |",
        f"| 1R / 2R | {st.get('hit_1R_pct')}% / {st.get('hit_2R_pct')}% |",
        "",
        "| HM | Side | Setup | Entry | SL | Risk | Exit | Pts | R | MFE |",
        "|---|---|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for c in ct_best:
        lines.append(
            f"| {c.hm} | {c.side} | {c.setup} | {c.entry} | {c.stop_loss} | {c.risk} | "
            f"{c.exit_why} | {c.pts} | {c.R} | {c.mfe} |"
        )
    if not ct_best:
        lines.append("| — | — | no setup cleared v2 gates | — | — | — | — | — | — | — |")

    v1t = by_prof["v1"]["today"]
    v2t = by_prof.get(best_name, best)["today"]
    lines += [
        "",
        "## v1 → locked today delta",
        "",
        f"| | v1 | `{best_name}` |",
        f"|---|---|---|",
        f"| N | {v1t.get('n')} | {v2t.get('n')} |",
        f"| Hit% | {v1t.get('hit_pct')} | {v2t.get('hit_pct')} |",
        f"| Sum pts | {v1t.get('sum_pts')} | {v2t.get('sum_pts')} |",
        f"| Avg R | {v1t.get('avg_R')} | {v2t.get('avg_R')} |",
        "",
        f"Ledger refreshed: added={ledger_meta.get('n_added')} cfg=`{best_name}`",
        "",
    ]
    MD.write_text("\n".join(lines), encoding="utf-8")

    # refresh TODAY report to locked profile
    s_all = best["full"]
    s10 = best["last10"]
    today_payload = {
        "desk": pa.DESK,
        "logic_ver": pa.LOGIC_VER,
        "cfg_name": best_name,
        "today": today,
        "today_summary": st,
        "today_calls": [c.to_dict() for c in ct_best],
        "window_days": len(days),
        "window_first": days[0],
        "window_last": days[-1],
        "window_summary": s_all,
        "last10_summary": s10,
        "ablate": str(MD).replace("\\", "/"),
    }
    TODAY_JS.write_text(json.dumps(today_payload, indent=2), encoding="utf-8")
    TODAY_MD.write_text(
        "\n".join(
            [
                f"# PA Structure Live · {today} · `{best_name}`",
                "",
                f"See ablation: `{MD.name}`",
                "",
                f"**Locked:** `{best_name}` · structure SL · no fixed target",
                "",
                f"| Calls | Hit% | AvgR | Sum |",
                f"|---:|---:|---:|---:|",
                f"| {st.get('n')} | {st.get('hit_pct')} | {st.get('avg_R')} | {st.get('sum_pts')} |",
                "",
                "| HM | Side | Setup | Entry | SL | Risk | Exit | Pts | R |",
                "|---|---|---|---:|---:|---:|---|---:|---:|",
            ]
            + [
                f"| {c.hm} | {c.side} | {c.setup} | {c.entry} | {c.stop_loss} | {c.risk} | "
                f"{c.exit_why} | {c.pts} | {c.R} |"
                for c in ct_best
            ]
            + [
                "",
                f"Window {days[0]}→{days[-1]}: n={s_all.get('n')} hit={s_all.get('hit_pct')}% "
                f"avgR={s_all.get('avg_R')} sum={s_all.get('sum_pts')}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {MD}", flush=True)
    print(f"Wrote {TODAY_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
