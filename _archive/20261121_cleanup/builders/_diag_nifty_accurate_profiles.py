"""Compare baseline vs accurate profiles for ORB + trend-stay.

  python -u prod_live/tests/builders/_diag_nifty_accurate_profiles.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live" / "tests" / "builders"),
    str(ROOT / "app"),
    str(ROOT / "app" / "market"),
]
import path_setup  # noqa: F401,E402

from _diag_nifty_orb30_vwap_last10d import load_5m, last_n_sessions  # noqa: E402
import prod_live.logic.nifty_orb30_vwap_fut as orb  # noqa: E402
import prod_live.logic.nifty_trend_stay as ts  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_ACCURATE_PROFILES_TEST.md"
OUT_JSON = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_ACCURATE_PROFILES_TEST.json"
COST = 1.0
WINDOWS = (10, 40, 60, 80)


def _fmt(v, pct=False):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "n/a"
    if pct:
        return f"{100*float(v):.1f}%"
    return f"{float(v):.2f}" if isinstance(v, float) else str(v)


def main() -> None:
    bars, source = load_5m(days=120)
    bars = last_n_sessions(bars, 80)
    rows = []
    lines = [
        "# NIFTY accurate profiles · baseline vs accurate",
        "",
        f"**Source:** `{source}` 5m · cost {COST}",
        "",
        "## Profiles",
        "",
        "- ORB `accurate`: width 40–100 · entry within **5** pts of ORH/ORL",
        "- Trend `accurate`: **SELL only** · signal before 12:00 · risk≤30 · entry_ext≤15 · chase≤20",
        "",
        "| Family | Profile | Window | N | Hit | AvgW | AvgL | Ratio | Net |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for n in WINDOWS:
        clip = last_n_sessions(bars, n)
        for fam, mod, profiles in (
            ("orb", orb, ("baseline", "accurate")),
            ("trend", ts, ("baseline", "accurate")),
        ):
            for profile in profiles:
                calls = mod.generate_calls(clip, require_probability=False, profile=profile)
                stats = mod.summarize(calls, cost_points_per_call=COST)
                # normalize orb keys
                if fam == "orb":
                    avg_w = stats.get("average_win")
                    avg_l = stats.get("average_loss")
                    ratio = (
                        float(avg_w / abs(avg_l))
                        if avg_w is not None
                        and avg_l is not None
                        and not pd.isna(avg_w)
                        and not pd.isna(avg_l)
                        and avg_l != 0
                        else None
                    )
                else:
                    avg_w = stats.get("average_winner")
                    avg_l = stats.get("average_loser")
                    ratio = stats.get("winner_loser_ratio")
                pack = {
                    "family": fam,
                    "profile": profile,
                    "window": n,
                    "calls": stats.get("calls"),
                    "hit": stats.get("hit_rate"),
                    "avg_w": avg_w,
                    "avg_l": avg_l,
                    "ratio": ratio,
                    "net": stats.get("net_points"),
                }
                rows.append(pack)
                lines.append(
                    f"| {fam} | {profile} | {n} | {int(pack['calls'] or 0)} | "
                    f"{_fmt(pack['hit'], pct=True)} | {_fmt(pack['avg_w'])} | "
                    f"{_fmt(pack['avg_l'])} | {_fmt(pack['ratio'])} | {_fmt(pack['net'])} |"
                )

    lines += [
        "",
        "## Verdict",
        "",
        "- Prefer **ORB accurate** when you want higher hit rate (~60% band on 80d pool with entry_ext≤5).",
        "- Prefer **trend baseline** (or accurate SELL) when you want larger winners; hit stays ~40%.",
        "",
        "Reports: `NIFTY_ACCURATE_LOGIC_CANDIDATES.md` · `NIFTY_TREND_ORB_ACCURACY_SEARCH.md`",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps({"source": source, "rows": rows}, indent=2, default=str), encoding="utf-8")
    print(json.dumps(rows, indent=2, default=str))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
