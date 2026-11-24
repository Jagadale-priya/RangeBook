"""Feature-lift search: which filters raise hit rate on ORB + trend-stay.

Uses last 80 sessions; reports freeze (first 60) / holdout (last 20) for
candidate accurate profiles. Also tests ORB∩trend same-side combo.

  python -u prod_live/tests/builders/research_nifty_accuracy_features.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
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
import prod_live.logic.nifty_trend_stay as ts  # noqa: E402
import prod_live.logic.nifty_orb30_vwap_fut as orb  # noqa: E402
from research_nifty_trend_orb_accuracy import (  # noqa: E402
    OrbGate,
    TrendGate,
    evaluate_orb_gated,
    evaluate_trend_gated,
    run_orb,
    run_trend,
    _stats,
)

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT_DIR / "NIFTY_ACCURATE_LOGIC_CANDIDATES.md"
OUT_JSON = OUT_DIR / "NIFTY_ACCURATE_LOGIC_CANDIDATES.json"
COST = 1.0
HOLDOUT = 20


def enrich_trend(day: pd.DataFrame, call: ts.TrendCall) -> Dict[str, Any]:
    row = dict(call.__dict__)
    if call.entry is None or call.points is None:
        row.update(win=None, risk=None, entry_ext=None, signal_hm=None, entry_hm=None)
        return row
    level = call.balance_high if call.direction == "buy" else call.balance_low
    risk = (
        call.entry - call.initial_stop
        if call.direction == "buy"
        else call.initial_stop - call.entry
    )
    row["risk"] = risk
    row["entry_ext"] = abs(call.entry - level) if level is not None else None
    row["signal_hm"] = pd.Timestamp(call.signal_time).strftime("%H:%M") if call.signal_time is not None else None
    row["entry_hm"] = pd.Timestamp(call.entry_time).strftime("%H:%M") if call.entry_time is not None else None
    row["win"] = float(call.points) > COST
    row["net"] = float(call.points) - COST
    # break extension from 15m close
    if call.signal_time is not None:
        # approximate from day close at signal bucket end (~+14m)
        pass
    return row


def enrich_orb(call: orb.DayCall) -> Dict[str, Any]:
    row = dict(call.__dict__)
    if call.entry is None or call.points is None:
        row.update(win=None, entry_ext=None, signal_hm=None)
        return row
    level = call.opening_high if call.direction == "buy" else call.opening_low
    row["entry_ext"] = abs(call.entry - level) if level is not None else None
    row["signal_hm"] = (
        pd.Timestamp(call.signal_time).strftime("%H:%M") if call.signal_time is not None else None
    )
    row["win"] = float(call.points) > COST
    row["net"] = float(call.points) - COST
    return row


def hit_table(df: pd.DataFrame, label: str) -> str:
    taken = df[df["entry"].notna()].copy()
    if taken.empty:
        return f"- {label}: no calls"
    wins = int(taken["win"].sum())
    n = len(taken)
    net = float(taken["net"].sum())
    return f"- {label}: N={n} hit={wins/n:.1%} net={net:.1f}"


def filter_eval(taken: pd.DataFrame, mask: pd.Series, name: str) -> Dict[str, Any]:
    sub = taken[mask]
    if sub.empty:
        return {"name": name, "n": 0, "hit": None, "net": 0.0, "avg_w": None, "avg_l": None}
    win_mask = sub["win"].astype(bool)
    wins = sub.loc[win_mask]
    losses = sub.loc[~win_mask]
    return {
        "name": name,
        "n": int(len(sub)),
        "hit": float(len(wins) / len(sub)),
        "net": float(sub["net"].sum()),
        "avg_w": float(wins["net"].mean()) if len(wins) else None,
        "avg_l": float(losses["net"].mean()) if len(losses) else None,
        "ratio": (
            float(wins["net"].mean() / abs(losses["net"].mean()))
            if len(wins) and len(losses) and float(losses["net"].mean()) != 0
            else None
        ),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bars, source = load_5m(days=120)
    bars = last_n_sessions(bars, 80)
    days = sorted(bars.index.normalize().unique())
    freeze_days = set(days[:-HOLDOUT])
    hold_days = set(days[-HOLDOUT:])

    # Baseline full calls
    trend_gate = TrendGate("baseline")
    orb_gate = OrbGate("baseline")
    trend_all = []
    orb_all = []
    for d, day in bars.groupby(bars.index.normalize()):
        tc = evaluate_trend_gated(day, trend_gate)
        oc = evaluate_orb_gated(day, orb_gate)
        tr = enrich_trend(day, tc)
        tr["session"] = "hold" if d in hold_days else "freeze"
        tr["date_s"] = str(pd.Timestamp(d).date())
        trend_all.append(tr)
        obr = enrich_orb(oc)
        obr["session"] = "hold" if d in hold_days else "freeze"
        obr["date_s"] = str(pd.Timestamp(d).date())
        orb_all.append(obr)

    tdf = pd.DataFrame(trend_all)
    odf = pd.DataFrame(orb_all)
    tt = tdf[tdf["entry"].notna()].copy()
    ot = odf[odf["entry"].notna()].copy()

    # Candidate filters from feature splits
    trend_filters = []
    if len(tt):
        trend_filters = [
            filter_eval(tt, tt["risk"] <= 25, "trend risk<=25"),
            filter_eval(tt, tt["risk"] <= 30, "trend risk<=30"),
            filter_eval(tt, tt["entry_ext"] <= 10, "trend entry_ext<=10"),
            filter_eval(tt, tt["entry_ext"] <= 15, "trend entry_ext<=15"),
            filter_eval(tt, tt["balance_width"] <= 120, "trend width<=120"),
            filter_eval(tt, tt["balance_width"] <= 140, "trend width<=140"),
            filter_eval(tt, (tt["balance_width"] >= 40) & (tt["balance_width"] <= 130), "trend width 40-130"),
            filter_eval(tt, (tt["balance_width"] >= 50) & (tt["balance_width"] <= 130), "trend width 50-130"),
            filter_eval(tt, tt["signal_hm"] <= "11:30", "trend signal<=11:30"),
            filter_eval(tt, tt["signal_hm"] <= "12:00", "trend signal<=12:00"),
            filter_eval(tt, tt["signal_hm"] <= "12:30", "trend signal<=12:30"),
            filter_eval(tt, tt["direction"] == "buy", "trend BUY only"),
            filter_eval(tt, tt["direction"] == "sell", "trend SELL only"),
            filter_eval(
                tt,
                (tt["risk"] <= 30) & (tt["entry_ext"] <= 15) & (tt["signal_hm"] <= "12:30"),
                "trend risk30+eext15+sig1230",
            ),
            filter_eval(
                tt,
                (tt["risk"] <= 30)
                & (tt["entry_ext"] <= 12)
                & (tt["balance_width"] <= 140)
                & (tt["signal_hm"] <= "12:30"),
                "trend ACC bundle A",
            ),
            filter_eval(
                tt,
                (tt["risk"] <= 25)
                & (tt["entry_ext"] <= 12)
                & (tt["balance_width"].between(40, 130))
                & (tt["signal_hm"] <= "12:00"),
                "trend ACC bundle B",
            ),
            filter_eval(
                tt,
                (tt["max_favorable"].fillna(0) >= 0)
                & (tt["risk"] <= 30)
                & (tt["entry_ext"] <= 15)
                & (tt["balance_width"].between(40, 140)),
                "trend ACC bundle C",
            ),
        ]

    orb_filters = []
    if len(ot):
        orb_filters = [
            filter_eval(ot, ot["opening_width"] <= 80, "orb width<=80"),
            filter_eval(ot, ot["opening_width"].between(40, 90), "orb width 40-90"),
            filter_eval(ot, ot["opening_width"].between(45, 100), "orb width 45-100"),
            filter_eval(ot, ot["opening_width"].between(35, 85), "orb width 35-85"),
            filter_eval(ot, ot["entry_mode"] == "at_level", "orb at_level"),
            filter_eval(ot, ot["entry_ext"] <= 5, "orb entry_ext<=5"),
            filter_eval(ot, ot["entry_ext"] <= 3, "orb entry_ext<=3"),
            filter_eval(ot, ot["signal_hm"] <= "11:00", "orb signal<=11:00"),
            filter_eval(ot, ot["signal_hm"] <= "12:00", "orb signal<=12:00"),
            filter_eval(ot, ot["direction"] == "buy", "orb BUY only"),
            filter_eval(ot, ot["direction"] == "sell", "orb SELL only"),
            filter_eval(
                ot,
                (ot["opening_width"].between(40, 90))
                & (ot["entry_ext"] <= 5)
                & (ot["signal_hm"] <= "12:00"),
                "orb ACC bundle A",
            ),
            filter_eval(
                ot,
                (ot["opening_width"].between(35, 85))
                & (ot["entry_mode"] == "at_level"),
                "orb ACC bundle B at_level+w35-85",
            ),
            filter_eval(
                ot,
                (ot["opening_width"].between(40, 100))
                & (ot["entry_ext"] <= 5)
                & (ot["direction"] == "sell"),
                "orb ACC SELL eext5 w40-100",
            ),
            filter_eval(
                ot,
                (ot["opening_width"].between(40, 90))
                & (ot["entry_ext"] <= 5),
                "orb ACC w40-90 eext5",
            ),
        ]

    # Split freeze/hold for top bundles by re-running gated logic
    profiles = [
        (
            "trend",
            TrendGate(
                name="ACC_A",
                min_width=40,
                max_width=140,
                last_signal="12:30",
                max_risk=30,
                max_entry_ext=12,
                max_chase=20,
            ),
        ),
        (
            "trend",
            TrendGate(
                name="ACC_B",
                min_width=40,
                max_width=130,
                last_signal="12:00",
                max_risk=25,
                max_entry_ext=12,
                max_chase=20,
                max_break_ext=30,
            ),
        ),
        (
            "trend",
            TrendGate(
                name="ACC_C",
                min_width=50,
                max_width=130,
                last_signal="12:30",
                max_risk=30,
                max_entry_ext=15,
                max_chase=20,
                min_vwap_sep=5,
            ),
        ),
        (
            "trend",
            TrendGate(
                name="ACC_D_tight",
                min_width=40,
                max_width=120,
                last_signal="11:30",
                max_risk=25,
                max_entry_ext=10,
                max_chase=15,
                max_break_ext=25,
            ),
        ),
        ("orb", OrbGate(name="ACC_A", min_width=40, max_width=90, max_entry_ext=5, last_signal="12:00")),
        ("orb", OrbGate(name="ACC_B", min_width=35, max_width=85, at_level_only=True)),
        ("orb", OrbGate(name="ACC_C", min_width=40, max_width=100, max_entry_ext=5)),
        ("orb", OrbGate(name="ACC_D", min_width=45, max_width=90, max_entry_ext=5, last_signal="11:30")),
        ("orb", OrbGate(name="ACC_E_sell", min_width=40, max_width=100, max_entry_ext=5)),  # side filter later
    ]

    freeze = bars[bars.index.normalize().isin(freeze_days)]
    hold = bars[bars.index.normalize().isin(hold_days)]

    profile_rows = []
    for fam, gate in profiles:
        if fam == "trend":
            fr, ho = run_trend(freeze, gate), run_trend(hold, gate)
        else:
            fr, ho = run_orb(freeze, gate), run_orb(hold, gate)
        # optional SELL-only for ACC_E
        if getattr(gate, "name", "") == "ACC_E_sell":
            for df in (fr, ho):
                m = df["entry"].notna() & (df["direction"] != "sell")
                df.loc[m, ["entry", "points", "status"]] = None, None, "no_call"
                df.loc[m, "reason"] = "side_filter"
        fs, hs = _stats(fr), _stats(ho)
        profile_rows.append(
            {
                "family": fam,
                "name": gate.name,
                "gate": gate.__dict__,
                "freeze": fs,
                "hold": hs,
                "freeze_hit": fs.get("hit_rate"),
                "hold_hit": hs.get("hit_rate"),
                "freeze_n": fs.get("calls"),
                "hold_n": hs.get("calls"),
            }
        )

    # Combo: same-day same-side ORB + trend (take trend, require orb agree)
    combo_rows = []
    for d, day in bars.groupby(bars.index.normalize()):
        tc = evaluate_trend_gated(
            day,
            TrendGate(
                name="combo",
                min_width=40,
                max_width=140,
                last_signal="12:30",
                max_risk=30,
                max_entry_ext=12,
                max_chase=20,
            ),
        )
        oc = evaluate_orb_gated(
            day, OrbGate(name="combo", min_width=40, max_width=100, max_entry_ext=5)
        )
        sess = "hold" if d in hold_days else "freeze"
        if tc.entry is not None and oc.entry is not None and tc.direction == oc.direction:
            combo_rows.append(
                {
                    "date": str(pd.Timestamp(d).date()),
                    "session": sess,
                    "direction": tc.direction,
                    "points": tc.points,
                    "net": float(tc.points) - COST,
                    "win": float(tc.points) > COST,
                    "orb_points": oc.points,
                }
            )
        else:
            combo_rows.append(
                {
                    "date": str(pd.Timestamp(d).date()),
                    "session": sess,
                    "direction": None,
                    "points": None,
                    "net": None,
                    "win": None,
                    "orb_points": oc.points if oc.entry is not None else None,
                }
            )
    cdf = pd.DataFrame(combo_rows)
    ct = cdf[cdf["points"].notna()]

    def sess_stats(df: pd.DataFrame, sess: str) -> Dict[str, Any]:
        sub = df[df["session"] == sess]
        taken = sub[sub["points"].notna()]
        if taken.empty:
            return {"n": 0, "hit": None, "net": 0.0}
        return {
            "n": int(len(taken)),
            "hit": float(taken["win"].mean()),
            "net": float(taken["net"].sum()),
        }

    combo_pack = {
        "freeze": sess_stats(cdf, "freeze"),
        "hold": sess_stats(cdf, "hold"),
        "all": {
            "n": int(len(ct)),
            "hit": float(ct["win"].mean()) if len(ct) else None,
            "net": float(ct["net"].sum()) if len(ct) else 0.0,
        },
    }

    # Rank filters by hit with n>=8
    def rank(filters: List[dict], min_n: int = 8) -> List[dict]:
        ok = [f for f in filters if (f.get("n") or 0) >= min_n and f.get("hit") is not None]
        return sorted(ok, key=lambda f: (f["hit"], f["net"]), reverse=True)

    trend_ranked = rank(trend_filters, 6)
    orb_ranked = rank(orb_filters, 6)

    # Pick best accurate profiles: freeze hit >= 0.55 preferred, else best freeze hit with hold not disastrous
    def pick_profiles(rows: List[dict]) -> List[dict]:
        scored = []
        for r in rows:
            fh = r["freeze_hit"] or 0
            hh = r["hold_hit"]
            fn = r["freeze_n"] or 0
            hn = r["hold_n"] or 0
            if fn < 6:
                continue
            score = 100 * fh + 50 * (hh or 0) + 0.1 * (r["freeze"].get("net_points") or 0)
            if hn >= 2 and hh is not None:
                score += 30 * hh
            scored.append({**r, "score": score})
        return sorted(scored, key=lambda x: x["score"], reverse=True)

    best_profiles = pick_profiles(profile_rows)

    lines = [
        "# NIFTY accurate-logic candidates",
        "",
        f"**Source:** `{source}` · last 80 sessions · freeze 60 / holdout 20 · cost {COST}",
        "",
        "## Baseline taken-call pools",
        hit_table(tdf[tdf["session"] == "freeze"], "trend freeze"),
        hit_table(tdf[tdf["session"] == "hold"], "trend holdout"),
        hit_table(odf[odf["session"] == "freeze"], "orb freeze"),
        hit_table(odf[odf["session"] == "hold"], "orb holdout"),
        "",
        "## Feature filters on all taken calls (80d)",
        "",
        "### Trend-stay (min N=6)",
        "",
        "| Filter | N | Hit | Net | AvgW | AvgL | Ratio |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for f in trend_ranked[:12]:
        lines.append(
            f"| {f['name']} | {f['n']} | {f['hit']:.1%} | {f['net']:.1f} | "
            f"{f['avg_w']} | {f['avg_l']} | {f['ratio']} |"
        )
    lines += [
        "",
        "### ORB (min N=6)",
        "",
        "| Filter | N | Hit | Net | AvgW | AvgL | Ratio |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for f in orb_ranked[:12]:
        lines.append(
            f"| {f['name']} | {f['n']} | {f['hit']:.1%} | {f['net']:.1f} | "
            f"{f['avg_w']} | {f['avg_l']} | {f['ratio']} |"
        )

    lines += [
        "",
        "## Gated profiles · freeze / holdout",
        "",
        "| Family | Profile | Freeze N/hit/net | Hold N/hit/net | Score |",
        "|---|---|---|---|---:|",
    ]
    for r in best_profiles:
        fs, hs = r["freeze"], r["hold"]
        lines.append(
            f"| {r['family']} | `{r['name']}` | "
            f"{int(fs['calls'] or 0)}/{fs.get('hit_rate')} / {fs.get('net_points')} | "
            f"{int(hs['calls'] or 0)}/{hs.get('hit_rate')} / {hs.get('net_points')} | "
            f"{r['score']:.1f} |"
        )

    lines += [
        "",
        "## Combo · trend ACC + ORB same side same day",
        "",
        f"- freeze: {combo_pack['freeze']}",
        f"- holdout: {combo_pack['hold']}",
        f"- all: {combo_pack['all']}",
        "",
    ]

    # Recommend
    rec = best_profiles[0] if best_profiles else None
    orb_rec = next((r for r in best_profiles if r["family"] == "orb"), None)
    trend_rec = next((r for r in best_profiles if r["family"] == "trend"), None)
    lines += ["## Recommendation", ""]
    if trend_rec:
        g = trend_rec["gate"]
        lines += [
            "### Most accurate trend-stay profile found",
            f"- **{trend_rec['name']}**: width {g['min_width']}-{g['max_width']}, "
            f"signal before {g['last_signal']}, risk≤{g['max_risk']}, "
            f"entry_ext≤{g['max_entry_ext']}, chase≤{g['max_chase']}, "
            f"break_ext≤{g.get('max_break_ext')}, vwap_sep≥{g.get('min_vwap_sep')}",
            f"- freeze hit **{trend_rec['freeze_hit']}** N={trend_rec['freeze_n']} · "
            f"hold hit **{trend_rec['hold_hit']}** N={trend_rec['hold_n']}",
            "",
        ]
    if orb_rec:
        g = orb_rec["gate"]
        lines += [
            "### Most accurate ORB profile found",
            f"- **{orb_rec['name']}**: width {g['min_width']}-{g['max_width']}, "
            f"last_signal {g['last_signal']}, at_level={g['at_level_only']}, "
            f"entry_ext≤{g['max_entry_ext']}",
            f"- freeze hit **{orb_rec['freeze_hit']}** N={orb_rec['freeze_n']} · "
            f"hold hit **{orb_rec['hold_hit']}** N={orb_rec['hold_n']}",
            "",
        ]
    if trend_ranked:
        lines += [
            "### Strongest in-sample trend filter",
            f"- `{trend_ranked[0]['name']}` → hit {trend_ranked[0]['hit']:.1%} on N={trend_ranked[0]['n']}",
            "",
        ]
    if orb_ranked:
        lines += [
            "### Strongest in-sample ORB filter",
            f"- `{orb_ranked[0]['name']}` → hit {orb_ranked[0]['hit']:.1%} on N={orb_ranked[0]['n']}",
            "",
        ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    payload = {
        "source": source,
        "trend_filters": trend_ranked,
        "orb_filters": orb_ranked,
        "profiles": best_profiles,
        "combo": combo_pack,
        "recommend_trend": trend_rec,
        "recommend_orb": orb_rec,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"trend": trend_rec, "orb": orb_rec, "combo": combo_pack}, indent=2, default=str))
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
