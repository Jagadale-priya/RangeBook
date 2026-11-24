"""Backtest locked dual+fb bf>=20% from 2021 → latest.

Same exact logic as live lock. Reports per year + per month.
Also scores 2024+ overlap on 5m vs 15m to explain accuracy drift.

  python -u prod_live/tests/builders/_backtest_sensex_dual_fb_bf20_from_2021.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live" / "tests" / "builders")]
import path_setup  # noqa: F401,E402

from research_bn_sensex_final_brackets import load_tape, normalize_cand, path_score_pool  # noqa: E402
from research_sensex_modal_1y_deep import hit_pct  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
CANDS = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_full_live_candidates.json"
)
TAPE_15 = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_15m_12y.csv"
TAPE_5 = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_5m_kite.csv"

START = "2021-01-01"
SL = T1 = 50.0
MIN_BF = 0.20
DESK = "SENSEX_DUAL_FB_BF20_T50"


def sessions(bars: pd.DataFrame, a: str, b: str) -> List[str]:
    return sorted(
        {
            str(pd.Timestamp(t).date())
            for t in bars.index
            if a <= str(pd.Timestamp(t).date()) <= b
        }
    )


def key_of(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day"))[:10], str(r.get("hm") or "")[:5], str(r.get("decision") or "").upper())


def fallback_row(bars: pd.DataFrame, day: str) -> Optional[dict]:
    db = bars[bars.index.strftime("%Y-%m-%d") == day]
    if len(db) < 2:
        return None
    or_hi = float(db["High"].iloc[0])
    or_lo = float(db["Low"].iloc[0])
    width = or_hi - or_lo
    if width <= 0:
        return None
    entry_ts = None
    for want in ("09:45", "09:30", "10:00", "10:15"):
        hit = db[db.index.strftime("%H:%M") == want]
        if len(hit):
            entry_ts = hit.index[0]
            break
    if entry_ts is None:
        entry_ts = db.index[min(1, len(db) - 1)]
    close = float(db.loc[entry_ts, "Close"])
    if close > or_hi:
        side = "BUY"
        bf = (close - or_hi) / width
    elif close < or_lo:
        side = "SELL"
        bf = (or_lo - close) / width
    else:
        return None
    if bf < MIN_BF:
        return None
    hm = f"{entry_ts.hour:02d}:{entry_ts.minute:02d}"
    return {
        "day": day,
        "hm": hm,
        "decision": side,
        "side": side,
        "p_t1": 0.55,
        "first_break": True,
        "track": "or_fallback",
        "source": "fallback",
        "tags": ["fallback", "OR_09:45", "fb_break", f"bf>={MIN_BF}"],
    }


def build_day(bars, by, day: str) -> List[dict]:
    duals = []
    for r in list(by.get(day) or []):
        if float(r.get("p_t1") or 0) < 0.45:
            continue
        duals.append(
            {
                **r,
                "source": "dual",
                "track": r.get("track") or "champion",
                "tags": ["dual", "OR_break"],
            }
        )
    duals = sorted(duals, key=lambda x: (str(x.get("hm") or ""), -float(x.get("p_t1") or 0)))
    fb = fallback_row(bars, day)
    if not duals and not fb:
        return []
    if not fb:
        return duals
    if not duals:
        return [fb]
    out: List[dict] = []
    fb_k = key_of(fb)
    merged = False
    for d in duals:
        if key_of(d) == fb_k:
            row = dict(d)
            tags = list(
                dict.fromkeys(
                    (row.get("tags") or [])
                    + (fb.get("tags") or [])
                    + ["dual", "fallback", "COMBINED"]
                )
            )
            row["tags"] = tags
            row["source"] = "dual+fallback"
            row["track"] = "dual_fb_combined"
            row["combined"] = True
            row["p_t1"] = max(float(d.get("p_t1") or 0), float(fb.get("p_t1") or 0))
            out.append(row)
            merged = True
        else:
            out.append(d)
    if not merged:
        out.append(fb)
    return out


def score_book(bars, ix, by, a: str, b: str):
    sess = sessions(bars, a, b)
    picks: List[dict] = []
    for day in sess:
        picks.extend(build_day(bars, by, day))
    scored = path_score_pool(bars, ix, picks, SL, T1)
    meta_by = {key_of(p): p for p in picks}
    for r in scored:
        m = meta_by.get(key_of(r)) or {}
        r["source"] = m.get("source") or "dual"
        r["tags"] = list(m.get("tags") or [])
        r["combined"] = bool(m.get("combined"))
        r["sl_pts"] = SL
        r["t1_pts"] = T1
    return scored, sess


def summarize(scored: List[dict], sess: List[str]) -> Dict[str, Any]:
    known = [r for r in scored if r.get("win") is not None]
    w = sum(1 for r in known if r.get("win"))
    return {
        "n": len(scored),
        "sessions": len(sess),
        "days_with_call": len({str(r.get("day"))[:10] for r in scored}),
        "hit_pct": hit_pct(scored),
        "wins": w,
        "losses": len(known) - w,
        "dual_only": sum(1 for r in scored if r.get("source") == "dual"),
        "fallback_only": sum(1 for r in scored if r.get("source") == "fallback"),
        "combined": sum(1 for r in scored if r.get("source") == "dual+fallback"),
        "points": round(sum(float(r.get("points") or 0) for r in known), 1),
    }


def rollup(rows: List[dict], key_fn) -> Dict[str, Dict[str, Any]]:
    buckets: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        buckets[key_fn(r)].append(r)
    out = {}
    for k in sorted(buckets.keys()):
        rr = buckets[k]
        known = [x for x in rr if x.get("win") is not None]
        w = sum(1 for x in known if x.get("win"))
        out[k] = {
            "n": len(rr),
            "hit_pct": hit_pct(rr),
            "wins": w,
            "losses": len(known) - w,
            "dual_only": sum(1 for x in rr if x.get("source") == "dual"),
            "fallback_only": sum(1 for x in rr if x.get("source") == "fallback"),
            "combined": sum(1 for x in rr if x.get("source") == "dual+fallback"),
            "points": round(sum(float(x.get("points") or 0) for x in known), 1),
        }
    return out


def main() -> int:
    print("Backtest dual+fb bf20 from 2021", flush=True)
    bars15, ix15 = load_tape(TAPE_15)
    if getattr(bars15.index, "tz", None) is not None:
        bars15 = bars15.copy()
        bars15.index = bars15.index.tz_localize(None)
    end15 = str(pd.Timestamp(bars15.index.max()).date())
    end = min(end15, "2026-11-19")

    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    by: Dict[str, List[dict]] = defaultdict(list)
    for row in raw:
        n = normalize_cand(row)
        if not n or n["day"] < START or n["day"] > end:
            continue
        n["first_break"] = bool(row.get("first_break"))
        n["p_t1"] = float(n.get("p_t1") or 0)
        if row.get("when"):
            try:
                ts = pd.Timestamp(row["when"])
                n["hm"] = f"{ts.hour:02d}:{ts.minute:02d}"
            except Exception:
                pass
        by[n["day"]].append(n)

    print(f"  window {START} → {end} on 15m", flush=True)
    scored15, sess15 = score_book(bars15, ix15, by, START, end)
    overall = summarize(scored15, sess15)
    by_year = rollup(scored15, lambda r: str(r.get("day"))[:4])
    by_month = rollup(scored15, lambda r: str(r.get("day"))[:7])
    print(
        f"  15m overall n={overall['n']} hit={overall['hit_pct']}% "
        f"{overall['wins']}/{overall['losses']}",
        flush=True,
    )
    for y, st in by_year.items():
        print(f"  {y}: n={st['n']} hit={st['hit_pct']}%", flush=True)

    # 5m overlap for drift diagnosis
    overlap = None
    if TAPE_5.is_file():
        bars5, ix5 = load_tape(TAPE_5)
        if getattr(bars5.index, "tz", None) is not None:
            bars5 = bars5.copy()
            bars5.index = bars5.index.tz_localize(None)
        start5 = str(pd.Timestamp(bars5.index.min()).date())
        end5 = min(str(pd.Timestamp(bars5.index.max()).date()), end)
        if start5 <= end5:
            print(f"  5m overlap {start5} → {end5}", flush=True)
            sc5, se5 = score_book(bars5, ix5, by, start5, end5)
            sc15o, se15o = score_book(bars15, ix15, by, start5, end5)
            overlap = {
                "window": {"start": start5, "end": end5},
                "on_5m": summarize(sc5, se5),
                "on_15m": summarize(sc15o, se15o),
            }
            print(
                f"  overlap 5m hit={overlap['on_5m']['hit_pct']}% n={overlap['on_5m']['n']} | "
                f"15m hit={overlap['on_15m']['hit_pct']}% n={overlap['on_15m']['n']}",
                flush=True,
            )

    # compare to 2018-2020 from prior report if present
    prior = OUT / "SENSEX_DUAL_FB_BF20_2015_2020.json"
    prior_overall = None
    if prior.is_file():
        prior_overall = json.loads(prior.read_text(encoding="utf-8")).get("overall")

    payload = {
        "desk": DESK,
        "logic": {
            "dual": "p_t1>=0.45 all OR-break · no or_ext · sell cont",
            "fallback": f"OR break-only break_frac>={MIN_BF}",
            "combine": "same hm+side → 1 COMBINED call",
            "clip": {"sl": SL, "t1": T1},
        },
        "window": {"start": START, "end": end},
        "tape": str(TAPE_15).replace("\\", "/"),
        "overall": overall,
        "by_year": by_year,
        "by_month": by_month,
        "overlap_5m_vs_15m": overlap,
        "prior_2018_2020": prior_overall,
        "why_inconsistent": [
            "Lock metrics (~77% 1y) were path-scored on 5m kite; 2018-2020 used 15m_12y only.",
            "Fixed ±50 pts is a larger % of Sensex in 2018-20 (~35k) than 2024-26 (~75k+).",
            "Dual packs/candidates are modern-era models; older regimes (esp. 2020 crash) differ.",
            "OR on 15m first bar ≠ 5m opening-range used in live research.",
        ],
    }

    lines = [
        "# SENSEX dual+fb bf≥20% · from 2021",
        "",
        f"**Desk:** `{DESK}` · exact locked logic · clip ±50/50",
        f"**Window:** {START} → {end} (15m_12y path-score)",
        "",
        "## Why accuracy looked inconsistent",
        "",
        "1. **Tape mismatch:** recent lock ~77% was on **5m**; 2018–20 test was on **15m** (coarser path).",
        "2. **Fixed ±50 pts:** much larger vs index level in 2018–20 than today → more SL hits historically.",
        "3. **Regime / model era:** dual candidates come from modern packs; 2020 crash/recovery differs.",
        "4. **OR definition:** 15m first bar ≠ live 5m opening range.",
        "",
    ]
    if overlap:
        lines += [
            "### Same window, 5m vs 15m (overlap)",
            "",
            f"Window `{overlap['window']['start']}` → `{overlap['window']['end']}`",
            "",
            f"| Tape | N | Hit% | W/L |",
            f"|---|---:|---:|---|",
            f"| **5m** | {overlap['on_5m']['n']} | **{overlap['on_5m']['hit_pct']}** | {overlap['on_5m']['wins']}/{overlap['on_5m']['losses']} |",
            f"| **15m** | {overlap['on_15m']['n']} | **{overlap['on_15m']['hit_pct']}** | {overlap['on_15m']['wins']}/{overlap['on_15m']['losses']} |",
            "",
        ]
    if prior_overall:
        lines += [
            "### Era comparison (both on 15m where possible)",
            "",
            f"| Era | N | Hit% | W/L | Pts |",
            f"|---|---:|---:|---|---:|",
            f"| 2018–2020 (15m) | {prior_overall.get('n')} | {prior_overall.get('hit_pct')} | {prior_overall.get('wins')}/{prior_overall.get('losses')} | {prior_overall.get('points')} |",
            f"| **2021→{end[:4]} (15m)** | {overall['n']} | **{overall['hit_pct']}** | {overall['wins']}/{overall['losses']} | {overall['points']} |",
            "",
        ]

    lines += [
        "## Overall from 2021 (15m)",
        "",
        f"**Calls:** {overall['n']} · **Hit:** **{overall['hit_pct']}%** · "
        f"W/L **{overall['wins']}/{overall['losses']}** · pts {overall['points']}",
        f"Days: {overall['days_with_call']}/{overall['sessions']} · "
        f"dual {overall['dual_only']} · fb {overall['fallback_only']} · combo {overall['combined']}",
        "",
        "## Per year",
        "",
        "| Year | N | Hit% | W/L | Dual | FB | Combo | Pts |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for y, st in by_year.items():
        lines.append(
            f"| **{y}** | {st['n']} | **{st['hit_pct']}** | {st['wins']}/{st['losses']} | "
            f"{st['dual_only']} | {st['fallback_only']} | {st['combined']} | {st['points']} |"
        )
    lines += [
        "",
        "## Per month",
        "",
        "| Month | N | Hit% | W/L | Dual | FB | Combo | Pts |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for m, st in by_month.items():
        lines.append(
            f"| {m} | {st['n']} | {st['hit_pct']} | {st['wins']}/{st['losses']} | "
            f"{st['dual_only']} | {st['fallback_only']} | {st['combined']} | {st['points']} |"
        )
    lines += ["", "_Backtest from 2021 complete_", ""]

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "SENSEX_DUAL_FB_BF20_FROM_2021.md"
    js = OUT / "SENSEX_DUAL_FB_BF20_FROM_2021.json"
    md.write_text("\n".join(lines), encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
