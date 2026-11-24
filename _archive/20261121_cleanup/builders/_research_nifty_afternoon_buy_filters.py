"""Tighten afternoon BUY: catch Nov19-style thrust without 40% junk.

Idea: after 13:00, require a fresh thrust bar (close > prior 2 highs) while
already above OR, optional min day uplift from 13:00 open.

  python -u prod_live/tests/builders/_research_nifty_afternoon_buy_filters.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
import path_setup  # noqa: F401,E402
import kite_data  # noqa: E402
from research_bn_sensex_final_brackets import score_one  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
DAY = "2026-11-19"
SL = T1 = 30.0
SESSIONS = 60


def norm(df: pd.DataFrame) -> pd.DataFrame:
    w = df.copy()
    if getattr(w.index, "tz", None) is not None:
        w.index = w.index.tz_convert("Asia/Kolkata").tz_localize(None)
    w = w.rename(columns={c: str(c).title() for c in w.columns})
    for need in ("Open", "High", "Low", "Close"):
        if need not in w.columns:
            for c in list(w.columns):
                if str(c).lower() == need.lower():
                    w = w.rename(columns={c: need})
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in w.columns]
    w = w[cols].sort_index()
    w = w[~w.index.duplicated(keep="last")]
    hm = w.index.strftime("%H:%M")
    return w[(hm >= "09:15") & (hm <= "15:30")]


def build_ix(bars: pd.DataFrame) -> Dict[Tuple[str, str], int]:
    ix = {}
    for i, ts in enumerate(bars.index):
        d = str(pd.Timestamp(ts).date())
        hm = f"{pd.Timestamp(ts).hour:02d}:{pd.Timestamp(ts).minute:02d}"
        ix[(d, hm)] = i
    return ix


def hit(rows: List[dict]) -> Optional[float]:
    known = [r for r in rows if r.get("win") is not None]
    if not known:
        return None
    return round(100.0 * sum(1 for r in known if r.get("win")) / len(known), 2)


def day_signals(d15: pd.DataFrame, rules: Dict[str, Any]) -> Optional[dict]:
    if len(d15) < 8:
        return None
    or_hi = float(d15["High"].iloc[0])
    or_lo = float(d15["Low"].iloc[0])
    # 13:00 bar
    b13 = d15[d15.index.strftime("%H:%M") == "13:00"]
    if not len(b13):
        return None
    open13 = float(b13["Open"].iloc[0])
    hm_min = rules.get("hm_min", "13:15")
    hm_max = rules.get("hm_max", "14:45")
    min_uplift = float(rules.get("min_uplift_from_13", 0))
    need_above_or = bool(rules.get("above_or", True))
    break_n = int(rules.get("break_prior_highs", 2))
    min_bar_range = float(rules.get("min_bar_range", 0))
    require_green = bool(rules.get("require_green", True))
    max_one = True

    for i, (ts, row) in enumerate(d15.iterrows()):
        hm = ts.strftime("%H:%M")
        if hm < hm_min or hm > hm_max:
            continue
        close = float(row["Close"])
        high = float(row["High"])
        low = float(row["Low"])
        opn = float(row["Open"])
        if need_above_or and close <= or_hi:
            continue
        if require_green and close <= opn:
            continue
        if (high - low) < min_bar_range:
            continue
        uplift = close - open13
        if uplift < min_uplift:
            continue
        # thrust: close breaks prior N bar highs
        if i < break_n:
            continue
        prior_highs = [float(d15["High"].iloc[j]) for j in range(i - break_n, i)]
        if close <= max(prior_highs):
            continue
        # optional: close near high of bar (strong close)
        if rules.get("close_in_top_frac") is not None:
            rng = high - low
            if rng <= 0:
                continue
            if (close - low) / rng < float(rules["close_in_top_frac"]):
                continue
        return {
            "hm": hm,
            "entry": close,
            "or_hi": or_hi,
            "or_lo": or_lo,
            "uplift_from_13": round(uplift, 1),
            "bar_range": round(high - low, 1),
            "ext_vs_or": round((close - or_hi) / max(or_hi - or_lo, 1e-9), 3),
        }
    return None


def run_rules(bars15, bars5, ix, days, rules, name) -> Dict[str, Any]:
    picks = []
    for day in days:
        d15 = bars15[bars15.index.strftime("%Y-%m-%d") == day]
        sig = day_signals(d15, rules)
        if not sig:
            continue
        picks.append({"day": day, "decision": "BUY", **sig})
    scored = []
    for r in picks:
        sc = score_one(bars5, ix, r["day"], r["hm"], "BUY", SL, T1)
        if not sc:
            continue
        scored.append({**r, **sc})
    today = [r for r in scored if r["day"] == DAY]
    return {
        "name": name,
        "rules": rules,
        "n": len(scored),
        "hit_pct": hit(scored),
        "wins": sum(1 for r in scored if r.get("win")),
        "losses": sum(1 for r in scored if r.get("win") is False),
        "days": len({r["day"] for r in scored}),
        "today_n": len(today),
        "today": today,
        "calls": scored,
    }


def main() -> int:
    print("Pull tape…", flush=True)
    b15, e15 = kite_data.fetch_historical_candles("NIFTY", "15minute", days=90, keep_partial=True)
    b5, e5 = kite_data.fetch_historical_candles("NIFTY", "5minute", days=90, keep_partial=True)
    if e15 or e5 or b15 is None or b5 is None:
        raise SystemExit(f"kite {e15} {e5}")
    bars15 = norm(b15)
    bars5 = norm(b5)
    days = sorted(set(bars15.index.strftime("%Y-%m-%d")))[-SESSIONS:]
    ix = build_ix(bars5)
    print(f"sessions {len(days)} {days[0]}→{days[-1]}", flush=True)

    grid = [
        ("thrust2_green", dict(break_prior_highs=2, require_green=True, min_uplift_from_13=0)),
        ("thrust2_up20", dict(break_prior_highs=2, require_green=True, min_uplift_from_13=20)),
        ("thrust2_up30", dict(break_prior_highs=2, require_green=True, min_uplift_from_13=30)),
        ("thrust2_up40", dict(break_prior_highs=2, require_green=True, min_uplift_from_13=40)),
        ("thrust2_up50", dict(break_prior_highs=2, require_green=True, min_uplift_from_13=50)),
        ("thrust3_up30", dict(break_prior_highs=3, require_green=True, min_uplift_from_13=30)),
        ("thrust2_up30_rng25", dict(break_prior_highs=2, require_green=True, min_uplift_from_13=30, min_bar_range=25)),
        ("thrust2_up30_top70", dict(break_prior_highs=2, require_green=True, min_uplift_from_13=30, close_in_top_frac=0.70)),
        ("thrust2_up40_top70", dict(break_prior_highs=2, require_green=True, min_uplift_from_13=40, close_in_top_frac=0.70)),
        ("thrust2_up40_rng30_top70", dict(break_prior_highs=2, require_green=True, min_uplift_from_13=40, min_bar_range=30, close_in_top_frac=0.70)),
        ("hm14_up30", dict(hm_min="14:00", hm_max="14:45", break_prior_highs=2, require_green=True, min_uplift_from_13=30)),
        ("hm14_up40_rng30", dict(hm_min="14:00", hm_max="14:45", break_prior_highs=2, require_green=True, min_uplift_from_13=40, min_bar_range=30)),
    ]

    results = []
    for name, rules in grid:
        st = run_rules(bars15, bars5, ix, days, rules, name)
        results.append(st)
        print(
            f"  {name}: n={st['n']} hit={st['hit_pct']}% today={st['today_n']} "
            f"{st['today'][0]['hm'] if st['today'] else ''}",
            flush=True,
        )

    # Prefer: fires today, hit>=70, n>=8; else best hit among today-firers with n>=5
    cands = [r for r in results if r["today_n"] and r["hit_pct"] is not None]
    best = None
    for r in cands:
        if r["n"] < 5:
            continue
        score = (r["hit_pct"], r["n"])
        if best is None or score > (best["hit_pct"], best["n"]):
            best = r

    lines = [
        "# NIFTY afternoon BUY · price-action thrust filters",
        "",
        f"**Target day:** `{DAY}` ~+170 pts after 13:00",
        f"**Sample:** last {SESSIONS} sessions · ±30 · 1 call/day",
        "",
        "Naive dual-cont afternoon was only **40%** hit — not live-ready.",
        "These rules ignore model p and use **OR-up + thrust bar** after 13:00.",
        "",
        "| Rule | N | Hit% | W/L | Today | Today HM |",
        "|---|---:|---:|---|---|---|",
    ]
    for r in results:
        thm = r["today"][0]["hm"] if r["today"] else "—"
        lines.append(
            f"| `{r['name']}` | {r['n']} | {r['hit_pct']} | {r['wins']}/{r['losses']} | "
            f"{'YES' if r['today_n'] else 'no'} | {thm} |"
        )
    if best:
        lines += [
            "",
            f"## Selected: `{best['name']}` · **{best['hit_pct']}%** · n={best['n']}",
            "",
            f"Rules: `{json.dumps(best['rules'])}`",
            "",
            "### Today",
            "",
        ]
        for r in best["today"]:
            lines.append(
                f"- **{r['hm']}** BUY @ {r['entry']} · uplift_from_13={r['uplift_from_13']} · "
                f"win={r.get('win')} pts={r.get('points')}"
            )
        lines += [
            "",
            "### All calls",
            "",
            "| Day | HM | Entry | Uplift13 | ExtOR | Win | Pts |",
            "|---|---|---:|---:|---:|---|---:|",
        ]
        for r in best["calls"]:
            w = "W" if r.get("win") else ("L" if r.get("win") is False else "?")
            lines.append(
                f"| {r['day']} | {r['hm']} | {r['entry']} | {r['uplift_from_13']} | "
                f"{r['ext_vs_or']} | {w} | {r.get('points')} |"
            )
        lines += [
            "",
            "## Live proposal",
            "",
            f"- Add **NIFTY afternoon thrust BUY** lane (`{best['name']}`)",
            "- Does **not** loosen morning dual first-break",
            "- Cap 1/day · ±30 · after 13:00 only",
            "",
        ]
        if best["hit_pct"] < 70:
            lines.append(
                f"**Caution:** hit {best['hit_pct']}% is below 70% desk floor — "
                "treat as research / paper until more history confirms."
            )
    else:
        lines += ["", "No rule both fired today and had n≥5.", ""]

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "NIFTY_AFTERNOON_BUY_THRUST_FILTERS.md"
    js = OUT / "NIFTY_AFTERNOON_BUY_THRUST_FILTERS.json"
    md.write_text("\n".join(lines), encoding="utf-8")
    js.write_text(json.dumps({"results": results, "best": best["name"] if best else None}, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
