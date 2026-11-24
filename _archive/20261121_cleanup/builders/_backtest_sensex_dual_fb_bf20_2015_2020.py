"""Backtest locked Sensex dual+fb bf>=20% on 2015-2020 (data-limited).

Exact logic (same as live lock):
  - Dual: OR-break p_t1>=0.45, no or_ext cap, sell cont allowed, all duals
  - Fallback: OR break-only @ 09:45 with break_frac>=0.20 (no mid)
  - Same hm+side: 1 call with dual+fallback COMBINED tags
  - Clip ±50/50 · no mutual block

Data note: repo Sensex history starts 2018-03 (15m_12y + dual cands).
2015-2017 has no tape/candidates — reported as unavailable.

  python -u prod_live/tests/builders/_backtest_sensex_dual_fb_bf20_2015_2020.py
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
# Longest available Sensex OHLCV for this window
TAPE = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_15m_12y.csv"

REQ_START = "2015-01-01"
REQ_END = "2020-12-31"
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
        "fb_kind": "break",
        "break_frac": bf,
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


def rollup(rows: List[dict], key_fn) -> Dict[str, Dict[str, Any]]:
    buckets: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        buckets[key_fn(r)].append(r)
    out: Dict[str, Dict[str, Any]] = {}
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
    print("Backtest dual+fb bf20 · requested 2015-2020", flush=True)
    bars, ix = load_tape(TAPE)
    if getattr(bars.index, "tz", None) is not None:
        bars = bars.copy()
        bars.index = bars.index.tz_localize(None)

    tape_start = str(pd.Timestamp(bars.index.min()).date())
    tape_end = str(pd.Timestamp(bars.index.max()).date())
    data_start = max(REQ_START, tape_start)
    data_end = min(REQ_END, tape_end)
    print(f"  tape {tape_start} → {tape_end}", flush=True)
    print(f"  usable window {data_start} → {data_end}", flush=True)

    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    by: Dict[str, List[dict]] = defaultdict(list)
    for row in raw:
        n = normalize_cand(row)
        if not n or n["day"] < data_start or n["day"] > data_end:
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

    sess = sessions(bars, data_start, data_end)
    picks: List[dict] = []
    for day in sess:
        picks.extend(build_day(bars, by, day))
    print(f"  sessions={len(sess)} picks={len(picks)} dual_days={len(by)}", flush=True)

    scored = path_score_pool(bars, ix, picks, SL, T1)
    meta_by = {key_of(p): p for p in picks}
    for r in scored:
        m = meta_by.get(key_of(r)) or {}
        r["source"] = m.get("source") or "dual"
        r["track"] = m.get("track") or "champion"
        r["tags"] = list(m.get("tags") or [])
        r["combined"] = bool(m.get("combined"))
        r["sl_pts"] = SL
        r["t1_pts"] = T1

    known = [r for r in scored if r.get("win") is not None]
    w = sum(1 for r in known if r.get("win"))
    overall = {
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
    by_year = rollup(scored, lambda r: str(r.get("day"))[:4])
    by_month = rollup(scored, lambda r: str(r.get("day"))[:7])

    # fill missing requested years
    year_rows = []
    for y in range(2015, 2021):
        ys = str(y)
        if ys in by_year:
            st = by_year[ys]
            year_rows.append((ys, st, "tested"))
        else:
            year_rows.append(
                (
                    ys,
                    {
                        "n": 0,
                        "hit_pct": None,
                        "wins": 0,
                        "losses": 0,
                        "dual_only": 0,
                        "fallback_only": 0,
                        "combined": 0,
                        "points": 0,
                    },
                    "no_data",
                )
            )

    print(
        f"  OVERALL n={overall['n']} hit={overall['hit_pct']}% "
        f"W/L {overall['wins']}/{overall['losses']} pts={overall['points']}",
        flush=True,
    )
    for ys, st, flag in year_rows:
        print(
            f"  {ys} [{flag}] n={st['n']} hit={st['hit_pct']} "
            f"{st['wins']}/{st['losses']}",
            flush=True,
        )

    payload = {
        "desk": DESK,
        "logic": {
            "dual": "p_t1>=0.45 all OR-break · no or_ext · sell cont",
            "fallback": f"OR break-only break_frac>={MIN_BF}",
            "combine": "same hm+side → 1 COMBINED call",
            "clip": {"sl": SL, "t1": T1},
            "mutual_block": False,
        },
        "requested_window": {"start": REQ_START, "end": REQ_END},
        "data_window": {"start": data_start, "end": data_end},
        "tape": str(TAPE).replace("\\", "/"),
        "tape_note": "15m_12y used (5m kite only covers 2024+). 2015-2017 unavailable in repo.",
        "overall": overall,
        "by_year": {ys: {**st, "status": flag} for ys, st, flag in year_rows},
        "by_month": by_month,
    }

    lines = [
        "# SENSEX dual+fb bf≥20% · backtest 2015–2020",
        "",
        f"**Desk / logic:** `{DESK}` (exact locked combine)",
        "",
        "## Logic (unchanged)",
        "",
        "1. Dual OR-break `p_t1 ≥ 0.45` · no or_ext · sell cont · all duals",
        f"2. Fallback OR break-only @ 09:45 with **break_frac ≥ {MIN_BF:.0%}**",
        "3. Same hm+side → **1 call** tags `dual`+`fallback`+`COMBINED`",
        "4. Clip ±50/50 · no mutual block",
        "",
        "## Data coverage",
        "",
        f"- Requested: **{REQ_START} → {REQ_END}**",
        f"- Available tape: **{tape_start} → {tape_end}** (`SENSEX_15m_12y.csv`)",
        f"- Tested: **{data_start} → {data_end}**",
        "- **2015–2017:** no Sensex OHLCV / dual candidates in repo → not tested",
        "",
        "## Overall (tested window)",
        "",
        f"**Calls:** {overall['n']} · **Hit:** **{overall['hit_pct']}%** · "
        f"W/L **{overall['wins']}/{overall['losses']}** · pts {overall['points']}",
        f"Days w/ call: {overall['days_with_call']}/{overall['sessions']} · "
        f"dual {overall['dual_only']} · fb {overall['fallback_only']} · combo {overall['combined']}",
        "",
        "## Per year",
        "",
        "| Year | Status | N | Hit% | W/L | Dual | FB | Combo | Pts |",
        "|---|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for ys, st, flag in year_rows:
        hit = st["hit_pct"] if st["hit_pct"] is not None else "—"
        lines.append(
            f"| **{ys}** | {flag} | {st['n']} | {hit} | "
            f"{st['wins']}/{st['losses']} | {st['dual_only']} | {st['fallback_only']} | "
            f"{st['combined']} | {st['points']} |"
        )

    lines += [
        "",
        "## Per month (tested)",
        "",
        "| Month | N | Hit% | W/L | Dual | FB | Combo | Pts |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for m, st in by_month.items():
        lines.append(
            f"| {m} | {st['n']} | {st['hit_pct']} | {st['wins']}/{st['losses']} | "
            f"{st['dual_only']} | {st['fallback_only']} | {st['combined']} | {st['points']} |"
        )
    lines += ["", "_Backtest complete_", ""]

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "SENSEX_DUAL_FB_BF20_2015_2020.md"
    js = OUT / "SENSEX_DUAL_FB_BF20_2015_2020.json"
    md.write_text("\n".join(lines), encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
