"""Improve nifty_minute_guide beyond avoid_stop.

Freeze: older sessions in last ~80 · Holdout: last ~22 (≈1 month).

  python -u prod_live/tests/builders/research_nifty_minute_guide_improve.py
"""
from __future__ import annotations

import json
import sys
from datetime import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live" / "tests" / "builders"),
    str(ROOT / "app"),
    str(ROOT / "app" / "market"),
]
import path_setup  # noqa: F401,E402

from _diag_nifty_state_conditional_1m import load_1m  # noqa: E402
from prod_live.logic.nifty_minute_guide import (  # noqa: E402
    GuideProfile,
    guide,
    resolve_profile,
    summarize,
)

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT_DIR / "NIFTY_MINUTE_GUIDE_IMPROVE.md"
OUT_JSON = OUT_DIR / "NIFTY_MINUTE_GUIDE_IMPROVE.json"
COST = 1.0
POOL_SESSIONS = 80
HOLDOUT_SESSIONS = 22


def _pct(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"{100.0 * x:.1f}%"


def _f(x: Optional[float], nd: int = 2) -> str:
    if x is None:
        return "n/a"
    return f"{x:.{nd}f}"


def _split(raw: List[dict]) -> Tuple[List[dict], List[dict], List[Any], List[Any]]:
    days = sorted({r["datetime"].date() for r in raw})
    hold_days = days[-HOLDOUT_SESSIONS:]
    freeze_days = days[:-HOLDOUT_SESSIONS]
    hold_set, freeze_set = set(hold_days), set(freeze_days)
    freeze_raw = [r for r in raw if r["datetime"].date() in freeze_set]
    hold_raw = [r for r in raw if r["datetime"].date() in hold_set]
    return freeze_raw, hold_raw, freeze_days, hold_days


def _eval(raw: List[dict], profile: GuideProfile) -> Dict[str, Any]:
    rows = guide(raw, profile=profile)
    summary = summarize(rows, cost_points=COST)
    closed = [r for r in rows if r["action"] == "DROP" and r["points"] is not None]
    stops = sum(1 for r in closed if r.get("reason") == "stop")
    summary["stops"] = stops
    summary["stop_share"] = None if not closed else stops / len(closed)
    return summary


def _candidates() -> List[GuideProfile]:
    """Small freeze/holdout grid (~150) around avoid_stop + structural caps."""
    seeds = [
        # (enter, eff, stretch, press, z1, earliest, cap, cool, drop)
        (0.30, 0.30, 0.0, 0.0, -999.0, time(9, 15), 999, 0, 0.12),  # avoid_stop
        (0.35, 0.30, 0.0, 0.0, -999.0, time(9, 15), 999, 0, 0.12),
        (0.40, 0.30, 0.0, 0.0, -999.0, time(9, 15), 999, 0, 0.12),
        (0.35, 0.40, 0.0, 0.0, -999.0, time(9, 15), 999, 0, 0.12),
        (0.35, 0.40, 0.30, 0.0, -999.0, time(9, 15), 999, 0, 0.12),
        (0.35, 0.40, 0.30, 0.25, -999.0, time(9, 15), 999, 0, 0.12),
        (0.35, 0.40, 0.30, 0.25, 0.0, time(9, 15), 999, 0, 0.12),
        (0.35, 0.40, 0.30, 0.25, 0.0, time(9, 30), 999, 0, 0.12),
        (0.35, 0.40, 0.30, 0.25, 0.0, time(9, 30), 8, 0, 0.12),
        (0.35, 0.40, 0.30, 0.25, 0.0, time(9, 30), 5, 0, 0.12),
        (0.35, 0.40, 0.30, 0.25, 0.0, time(9, 30), 5, 5, 0.12),
        (0.35, 0.40, 0.30, 0.25, 0.0, time(9, 30), 5, 10, 0.12),
        (0.35, 0.40, 0.30, 0.25, 0.0, time(9, 30), 3, 5, 0.12),
        (0.40, 0.40, 0.30, 0.25, 0.0, time(9, 30), 5, 5, 0.12),
        (0.40, 0.50, 0.30, 0.25, 0.0, time(9, 30), 5, 5, 0.12),
        (0.40, 0.50, 0.50, 0.25, 0.0, time(9, 30), 5, 5, 0.12),
        (0.45, 0.40, 0.30, 0.25, 0.0, time(9, 30), 5, 5, 0.12),
        (0.35, 0.40, 0.30, 0.25, 0.5, time(9, 30), 5, 5, 0.12),
        (0.35, 0.40, 0.30, 0.25, 0.0, time(9, 45), 5, 5, 0.12),
        (0.35, 0.40, 0.30, 0.25, 0.0, time(9, 30), 5, 5, 0.18),
        (0.30, 0.40, 0.30, 0.0, 0.0, time(9, 30), 8, 5, 0.12),
        (0.30, 0.50, 0.30, 0.25, 0.0, time(9, 30), 5, 5, 0.12),
        (0.40, 0.40, 0.0, 0.0, 0.0, time(9, 30), 5, 5, 0.12),
        (0.35, 0.50, 0.50, 0.25, 0.0, time(9, 30), 3, 10, 0.12),
        (0.45, 0.50, 0.50, 0.25, 0.5, time(9, 45), 3, 10, 0.18),
    ]
    # Cross a few structural levers on the best-shaped core
    core = (0.35, 0.40, 0.30, 0.25, 0.0)
    for earliest in (time(9, 15), time(9, 30), time(9, 45)):
        for cap in (999, 8, 5, 3):
            for cool in (0, 5, 10):
                for drop in (0.12, 0.18):
                    seeds.append((*core, earliest, cap, cool, drop))
    for enter in (0.30, 0.40, 0.45):
        for eff in (0.40, 0.50):
            seeds.append((enter, eff, 0.30, 0.25, 0.0, time(9, 30), 5, 5, 0.12))
            seeds.append((enter, eff, 0.50, 0.25, 0.0, time(9, 30), 5, 5, 0.12))
            seeds.append((enter, eff, 0.30, 0.25, 0.5, time(9, 30), 5, 5, 0.12))

    out: List[GuideProfile] = [
        resolve_profile("baseline"),
        resolve_profile("avoid_stop"),
        resolve_profile("accurate"),
    ]
    seen = {
        (
            p.enter,
            p.min_efficiency,
            p.min_vwap_align,
            p.min_pressure_align,
            p.min_z1_align,
            p.earliest_entry,
            p.max_calls_per_day,
            p.cooldown_after_stop,
            p.drop_line,
        )
        for p in out
    }
    for enter, eff, stretch, press, z1, earliest, cap, cool, drop in seeds:
        key = (enter, eff, stretch, press, z1, earliest, cap, cool, drop)
        if key in seen:
            continue
        seen.add(key)
        early_tag = f"{earliest.hour:02d}{earliest.minute:02d}"
        name = (
            f"e{enter:.2f}_eff{eff:.2f}_st{stretch:.2f}_pr{press:.2f}_"
            f"z{z1:.1f}_{early_tag}_c{cap}_cd{cool}_d{drop:.2f}"
        )
        out.append(
            GuideProfile(
                name=name,
                enter=enter,
                drop_line=drop,
                min_efficiency=eff,
                min_vwap_align=stretch,
                min_pressure_align=press,
                min_z1_align=z1,
                earliest_entry=earliest,
                max_calls_per_day=cap,
                cooldown_after_stop=cool,
            )
        )
    return out


def main() -> int:
    raw, source, _ = load_1m(POOL_SESSIONS)
    if not raw:
        print("no bars", flush=True)
        return 1
    days = sorted({r["datetime"].date() for r in raw})
    keep = set(days[-POOL_SESSIONS:])
    raw = [r for r in raw if r["datetime"].date() in keep]
    freeze_raw, hold_raw, freeze_days, hold_days = _split(raw)
    print(
        f"source={source} pool={len(keep)} freeze={len(freeze_days)} "
        f"hold={len(hold_days)} ({hold_days[0]}→{hold_days[-1]})",
        flush=True,
    )

    cur = resolve_profile("avoid_stop")
    cur_f, cur_h = _eval(freeze_raw, cur), _eval(hold_raw, cur)
    print(
        f"avoid_stop hold n={cur_h['closed_calls']} hit={_pct(cur_h['hit_rate'])} "
        f"net={_f(cur_h['net_points'])} stop%={_pct(cur_h['stop_share'])}",
        flush=True,
    )

    cands = _candidates()
    print(f"sweeping {len(cands)} profiles…", flush=True)
    rows_out: List[dict] = []
    for i, prof in enumerate(cands, 1):
        fr = _eval(freeze_raw, prof)
        ho = _eval(hold_raw, prof)
        hn = ho.get("closed_calls") or 0
        fn = fr.get("closed_calls") or 0
        ok = hn >= 12 and fn >= 25
        hh = ho.get("hit_rate") or 0.0
        hnet = ho.get("net_points") or 0.0
        hstop = ho.get("stop_share") or 1.0
        fh = fr.get("hit_rate") or 0.0
        score = (
            -1e9
            if not ok
            else (1000 * hh + 2.0 * hnet + 150 * fh - 250 * hstop + 0.3 * (fr.get("net_points") or 0))
        )
        rows_out.append(
            {
                "name": prof.name,
                "enter": prof.enter,
                "min_efficiency": prof.min_efficiency,
                "min_vwap_align": prof.min_vwap_align,
                "min_pressure_align": prof.min_pressure_align,
                "min_z1_align": prof.min_z1_align,
                "earliest_entry": str(prof.earliest_entry),
                "max_calls_per_day": prof.max_calls_per_day,
                "cooldown_after_stop": prof.cooldown_after_stop,
                "drop_line": prof.drop_line,
                "freeze": fr,
                "holdout": ho,
                "score": score,
                "ok": ok,
                "profile": prof,
            }
        )
        if i % 50 == 0 or i == len(cands):
            best = max(rows_out, key=lambda r: r["score"])
            print(
                f"  {i}/{len(cands)} best_so_far={best['name'][:40]} "
                f"ho_hit={_pct(best['holdout'].get('hit_rate'))} "
                f"ho_net={_f(best['holdout'].get('net_points'))}",
                flush=True,
            )

    cur_hit = cur_h.get("hit_rate") or 0.0
    cur_net = cur_h.get("net_points") or 0.0
    cur_stop = cur_h.get("stop_share") or 1.0

    improved = []
    for row in rows_out:
        if not row["ok"]:
            continue
        ho = row["holdout"]
        hh = ho.get("hit_rate") or 0.0
        hnet = ho.get("net_points") or 0.0
        hstop = ho.get("stop_share") or 1.0
        if hstop > cur_stop + 0.03:
            continue
        # Must improve holdout hit by ≥3pp OR net by ≥30 with hit not worse
        if hh >= cur_hit + 0.03 or (hnet >= cur_net + 30 and hh >= cur_hit - 0.005):
            if hh >= cur_hit - 0.01:
                improved.append(row)

    improved.sort(
        key=lambda r: (
            -(r["holdout"].get("hit_rate") or 0),
            -(r["holdout"].get("net_points") or 0),
            r["holdout"].get("stop_share") or 1,
        )
    )
    by_score = sorted([r for r in rows_out if r["ok"]], key=lambda r: -r["score"])
    pick = improved[0] if improved else None
    # Prefer pick that also has freeze hit >= avoid_stop freeze - 2pp
    if pick is not None:
        for row in improved:
            fh = row["freeze"].get("hit_rate") or 0.0
            cf = cur_f.get("hit_rate") or 0.0
            if fh >= cf - 0.02:
                pick = row
                break

    print(
        f"improved={len(improved)} pick={None if pick is None else pick['name']}",
        flush=True,
    )
    if pick:
        ho = pick["holdout"]
        print(
            f"  hold n={ho['closed_calls']} hit={_pct(ho['hit_rate'])} "
            f"net={_f(ho['net_points'])} stop%={_pct(ho['stop_share'])}",
            flush=True,
        )

    # Serialize without GuideProfile object
    def _slim(row: dict) -> dict:
        return {k: v for k, v in row.items() if k != "profile"}

    payload = {
        "source": source,
        "cost": COST,
        "freeze": [str(d) for d in freeze_days],
        "holdout": [str(d) for d in hold_days],
        "current_avoid_stop": {"freeze": cur_f, "holdout": cur_h},
        "pick": None if pick is None else _slim(pick),
        "top_improved": [_slim(r) for r in improved[:12]],
        "top_by_score": [_slim(r) for r in by_score[:12]],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def _line(tag: str, fr: dict, ho: dict) -> str:
        return (
            f"| {tag} | {fr.get('closed_calls')} | {_pct(fr.get('hit_rate'))} | "
            f"{_f(fr.get('net_points'))} | {_pct(fr.get('stop_share'))} | "
            f"{ho.get('closed_calls')} | {_pct(ho.get('hit_rate'))} | "
            f"{_f(ho.get('net_points'))} | {_pct(ho.get('stop_share'))} |"
        )

    lines = [_line("avoid_stop", cur_f, cur_h)]
    for r in (improved[:10] or by_score[:10]):
        lines.append(_line(f"`{r['name'][:60]}`", r["freeze"], r["holdout"]))

    pick_md = "No profile beat avoid_stop on holdout under the lift rules."
    if pick is not None:
        pick_md = f"""**Selected for `accurate` profile:** `{pick['name']}`

| Param | Value |
|---|---|
| enter | {pick['enter']} |
| min_efficiency | {pick['min_efficiency']} |
| min_vwap_align | {pick['min_vwap_align']} |
| min_pressure_align | {pick['min_pressure_align']} |
| min_z1_align | {pick['min_z1_align']} |
| earliest_entry | {pick['earliest_entry']} |
| max_calls_per_day | {pick['max_calls_per_day']} |
| cooldown_after_stop | {pick['cooldown_after_stop']} |
| drop_line | {pick['drop_line']} |

Holdout vs avoid_stop: hit {_pct(cur_hit)}→{_pct(pick['holdout'].get('hit_rate'))} · \
net {_f(cur_net)}→{_f(pick['holdout'].get('net_points'))} · \
stop% {_pct(cur_stop)}→{_pct(pick['holdout'].get('stop_share'))}
"""

    OUT_MD.write_text(
        f"""# NIFTY minute guide · improve avoid_stop

**Source:** `{source}` · cost {COST}
**Freeze:** {freeze_days[0]} → {freeze_days[-1]} ({len(freeze_days)})
**Holdout:** {hold_days[0]} → {hold_days[-1]} ({len(hold_days)})

## Comparison

| Profile | Fr N | Fr hit | Fr net | Fr stop | Ho N | Ho hit | Ho net | Ho stop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(lines)}

## Pick

{pick_md}
""",
        encoding="utf-8",
    )
    print(f"wrote {OUT_MD}", flush=True)

    # Write pick path for apply step
    if pick is not None:
        pick_path = OUT_DIR / "NIFTY_MINUTE_GUIDE_ACCURATE_PICK.json"
        pick_path.write_text(
            json.dumps(
                {
                    "enter": pick["enter"],
                    "drop_line": pick["drop_line"],
                    "min_efficiency": pick["min_efficiency"],
                    "min_vwap_align": pick["min_vwap_align"],
                    "min_pressure_align": pick["min_pressure_align"],
                    "min_z1_align": pick["min_z1_align"],
                    "earliest_entry": pick["earliest_entry"],
                    "max_calls_per_day": pick["max_calls_per_day"],
                    "cooldown_after_stop": pick["cooldown_after_stop"],
                    "holdout": pick["holdout"],
                    "freeze": pick["freeze"],
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"wrote {pick_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
