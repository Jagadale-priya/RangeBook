"""Recheck Sensex dual+fallback at ±50 with NO call-count block.

All dual OR-break cands kept. Fallback only on days with zero dual.
No max_per_day / best-of-day pick.

  python -u prod_live/tests/builders/_check_sensex_everyday_no_cap.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live" / "tests" / "builders")]
import path_setup  # noqa: F401,E402

from research_bn_sensex_final_brackets import load_tape, normalize_cand, path_score_pool  # noqa: E402
from research_sensex_modal_1y_deep import hit_pct, month_rollup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "SENSEX_EVERYDAY_NO_CAP_T50.md"
OUT_JSON = OUT / "SENSEX_EVERYDAY_NO_CAP_T50.json"
CANDS = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_full_live_candidates.json"
)
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_5m_kite.csv"
SX_LIVE = ROOT / "prod_live" / "logic" / "sensex_final_live.py"
FINAL_JSON = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_proven_100_final.json"
)
HOLD = ROOT / "prod_live" / "holding_accurate" / "sensex_final"

END = "2026-11-19"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_3M = (pd.Timestamp(END) - timedelta(days=92)).strftime("%Y-%m-%d")
SL = T1 = 50.0
DESK = "SENSEX_EVERYDAY_T50SL50"


def sessions(bars: pd.DataFrame, a: str, b: str) -> List[str]:
    idx = bars.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return sorted({str(pd.Timestamp(t).date()) for t in idx if a <= str(pd.Timestamp(t).date()) <= b})


def day_bars(bars: pd.DataFrame, day: str) -> pd.DataFrame:
    return bars[bars.index.strftime("%Y-%m-%d") == day]


def fallback_row(bars: pd.DataFrame, day: str) -> Optional[dict]:
    db = day_bars(bars, day)
    if len(db) < 2:
        return None
    or_hi = float(db["High"].iloc[0])
    or_lo = float(db["Low"].iloc[0])
    entry_ts = None
    for want in ("09:45", "09:30", "10:00", "10:15"):
        hit = db[db.index.strftime("%H:%M") == want]
        if len(hit):
            entry_ts = hit.index[0]
            break
    if entry_ts is None:
        entry_ts = db.index[min(1, len(db) - 1)]
    close = float(db.loc[entry_ts, "Close"])
    mid = (or_hi + or_lo) / 2.0
    if close > or_hi:
        side = "BUY"
    elif close < or_lo:
        side = "SELL"
    else:
        side = "BUY" if close >= mid else "SELL"
    hm = f"{entry_ts.hour:02d}:{entry_ts.minute:02d}"
    return {
        "day": day,
        "hm": hm,
        "decision": side,
        "side": side,
        "p_t1": 0.50,
        "first_break": True,
        "track": "day1_fallback",
        "source": "fallback",
    }


def stats(scored: List[dict], a: str, b: str, sess: List[str]) -> Dict[str, Any]:
    rr = [r for r in scored if a <= str(r.get("day") or "")[:10] <= b]
    known = [r for r in rr if r.get("win") is not None]
    w = sum(1 for r in known if r.get("win"))
    days = sorted({str(r.get("day"))[:10] for r in rr})
    return {
        "n": len(rr),
        "sessions": len(sess),
        "days_with_call": len(days),
        "coverage_pct": round(100.0 * len(days) / len(sess), 1) if sess else 0.0,
        "hit_pct": hit_pct(rr),
        "wins": w,
        "losses": len(known) - w,
        "dual_n": sum(1 for r in rr if r.get("source") == "dual"),
        "fallback_n": sum(1 for r in rr if r.get("source") == "fallback"),
        "avg_calls_per_day": round(len(rr) / len(days), 2) if days else 0.0,
        "by_month": month_rollup(rr),
    }


def main() -> int:
    print("Sensex dual+fallback NO CAP @ ±50", flush=True)
    bars, ix = load_tape(TAPE5)
    if getattr(bars.index, "tz", None) is not None:
        bars = bars.copy()
        bars.index = bars.index.tz_localize(None)

    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    cands: List[dict] = []
    for row in raw:
        n = normalize_cand(row)
        if not n or n["day"] < START_3Y or n["day"] > END:
            continue
        n["first_break"] = bool(row.get("first_break"))
        n["p_t1"] = float(n.get("p_t1") or 0)
        cands.append(n)
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in cands:
        by[r["day"]].append(r)

    picks: List[dict] = []
    for day in sessions(bars, START_3Y, END):
        rs = list(by.get(day) or [])
        if rs:
            for r in rs:
                picks.append({**r, "source": "dual", "track": r.get("track") or "champion"})
        else:
            fb = fallback_row(bars, day)
            if fb:
                picks.append(fb)

    scored = path_score_pool(bars, ix, picks, SL, T1)
    meta_by = {(p["day"], p["hm"], p["decision"]): p for p in picks}
    for r in scored:
        m = meta_by.get((r["day"], r["hm"], r["decision"])) or {}
        r["source"] = m.get("source") or "dual"
        r["track"] = m.get("track") or "champion"
        r["sl_pts"] = SL
        r["t1_pts"] = T1

    s1 = stats(scored, START_1Y, END, sessions(bars, START_1Y, END))
    s3m = stats(scored, START_3M, END, sessions(bars, START_3M, END))
    s3y = stats(scored, START_3Y, END, sessions(bars, START_3Y, END))
    for label, s in (("1y", s1), ("3m", s3m), ("3y", s3y)):
        print(
            f"  {label}: n={s['n']} days={s['days_with_call']}/{s['sessions']} "
            f"cov={s['coverage_pct']}% hit={s['hit_pct']}% dual={s['dual_n']} "
            f"fb={s['fallback_n']} avg/day={s['avg_calls_per_day']}",
            flush=True,
        )

    lo = min(x for x in [s1["hit_pct"], s3y["hit_pct"]] if x is not None)
    hi = max(x for x in [s1["hit_pct"], s3y["hit_pct"], s3m["hit_pct"]] if x is not None)
    acc_tag = f"ACC_RANGE_{int(lo)}_{int(min(100, round(hi)))}"

    HOLD.mkdir(parents=True, exist_ok=True)
    held = [r for r in scored if START_3Y <= str(r.get("day") or "")[:10] <= END]
    policy = {
        "name": "EVERYDAY_DUAL_ALL_PLUS_FALLBACK",
        "mode": "everyday_no_cap",
        "dual": "ALL dual OR-break cands (no max_per_day)",
        "fallback": "OR break/mid at 09:45 only if dual silent that day",
        "buy_min_p": 0.45,
        "sell_min_p": 0.45,
        "allow_sell_cont": True,
        "buy_max_or_ext": None,
        "max_per_day": None,
        "clip_sl": SL,
        "clip_t1": T1,
    }
    meta = {
        "desk": DESK,
        "mode": "everyday_no_cap",
        "policy": policy,
        "brackets": {"sl": SL, "target": T1},
        "cap": None,
        "accuracy_tag": acc_tag,
        "accuracy_lo": round(lo, 2),
        "accuracy_hi": round(hi, 2),
        "windows": {
            "1y": {k: s1[k] for k in ("n", "hit_pct", "coverage_pct", "sessions", "dual_n", "fallback_n", "avg_calls_per_day", "days_with_call")},
            "3m": {k: s3m[k] for k in ("n", "hit_pct", "coverage_pct", "sessions", "dual_n", "fallback_n", "avg_calls_per_day", "days_with_call")},
            "3y": {k: s3y[k] for k in ("n", "hit_pct", "coverage_pct", "sessions", "dual_n", "fallback_n", "avg_calls_per_day", "days_with_call")},
        },
        "note": "no call-count block · all dual + fallback on empty days",
    }
    calls_path = HOLD / "champ_plus_t50_sl50_calls.json"
    calls_path.write_text(json.dumps({"calls": held, "meta": meta}, indent=2), encoding="utf-8")

    payload = {
        "symbol": "SENSEX",
        "version": "everyday_t50_no_cap",
        "locked_clip": {"sl": SL, "t1": T1},
        "policy": policy,
        "desks": {
            "champ_plus": {
                "desk": DESK,
                "accurate_tag": DESK,
                "accuracy_tag": acc_tag,
                "accuracy_lo": round(lo, 2),
                "accuracy_hi": round(hi, 2),
                "windows": meta["windows"],
                "n_held": len(held),
                "brackets": {"sl": SL, "target": T1},
                "cap": None,
            }
        },
        "book": {
            "1y": {"n": s1["n"], "hit_pct": s1["hit_pct"], "coverage_pct": s1["coverage_pct"]},
            "3y": {"n": s3y["n"], "hit_pct": s3y["hit_pct"], "coverage_pct": s3y["coverage_pct"]},
            "5y": {"n": s3y["n"], "hit_pct": s3y["hit_pct"], "coverage_pct": s3y["coverage_pct"]},
        },
        "expected": {
            "1y": {"n": s1["n"], "hit_pct": s1["hit_pct"]},
            "3y": {"n": s3y["n"], "hit_pct": s3y["hit_pct"]},
            "5y": {"n": s3y["n"], "hit_pct": s3y["hit_pct"]},
        },
        "calls_path": str(calls_path).replace("\\", "/"),
    }
    for folder in (OUT, ROOT / "prod_live" / "reports" / "3y", ROOT / "prod_live" / "reports" / "5y"):
        folder.mkdir(parents=True, exist_ok=True)
    (ROOT / "prod_live" / "reports" / "5y" / "SENSEX_FINAL_CHAMP_PLUS_5Y.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    for folder, label, st in (
        (OUT, "1y", s1),
        (ROOT / "prod_live" / "reports" / "3y", "3y", s3y),
        (ROOT / "prod_live" / "reports" / "5y", "5y", s3y),
    ):
        (folder / f"SENSEX_FINAL_CHAMP_PLUS_{label.upper()}.json").write_text(
            json.dumps({**payload, "window": label, "window_stats": st}, indent=2, default=str),
            encoding="utf-8",
        )

    # live: no call-count block
    text = SX_LIVE.read_text(encoding="utf-8")
    text = re.sub(r'DESK_CHAMP = "[^"]+"', f'DESK_CHAMP = "{DESK}"', text, count=1)
    text = re.sub(r'ACCURACY_TAG = "[^"]+"', f'ACCURACY_TAG = "{acc_tag}"', text, count=1)
    text = re.sub(r"ACCURACY_LO = [0-9.]+", f"ACCURACY_LO = {round(lo, 2)}", text, count=1)
    text = re.sub(r"ACCURACY_HI = [0-9.]+", f"ACCURACY_HI = {round(hi, 2)}", text, count=1)
    text = re.sub(
        r"BRACKETS = \{[^}]+\}",
        f'BRACKETS = {{"target": {T1}, "sl": {SL}, "risk": {SL}}}',
        text,
        count=1,
    )
    text = re.sub(r"CAP = [^\n]+", "CAP = 99  # no practical call-count block; dedupe only", text, count=1)
    SX_LIVE.write_text(text, encoding="utf-8")

    if FINAL_JSON.is_file():
        doc = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
        doc.setdefault("tracks", {}).setdefault("live_champion", {})["policy"] = {
            **policy,
            "max_per_day": None,
        }
        doc["tracks"]["live_champion"]["full"] = {
            "n": s1["n"],
            "hit_pct": s1["hit_pct"],
            "coverage_pct": s1["coverage_pct"],
        }
        doc["verdict"]["champion_hit_pct"] = s1["hit_pct"]
        doc["verdict"]["summary"] = (
            f"SENSEX dual+fallback NO CAP ±50: 1y {s1['n']}@{s1['hit_pct']}% "
            f"cov {s1['coverage_pct']}% avg {s1['avg_calls_per_day']}/day"
        )
        FINAL_JSON.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    lines = [
        "# SENSEX · dual+fallback · NO call-count block (±50/50)",
        "",
        f"**Desk:** `{DESK}`",
        "**Logic kept:** all dual OR-break candidates; OR fallback @ 09:45 only when dual silent that day.",
        "**Removed:** max_per_day / CAP / best-of-day single pick.",
        f"**Clip:** ±{SL:g}/{T1:g}",
        "",
        "## Results",
        "",
        "| Window | Days covered | Calls | Cov% | Hit% | Dual | Fallback | Avg/day | W/L |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        f"| **1y** | {s1['days_with_call']}/{s1['sessions']} | {s1['n']} | {s1['coverage_pct']} | {s1['hit_pct']} | {s1['dual_n']} | {s1['fallback_n']} | {s1['avg_calls_per_day']} | {s1['wins']}/{s1['losses']} |",
        f"| **3m** | {s3m['days_with_call']}/{s3m['sessions']} | {s3m['n']} | {s3m['coverage_pct']} | {s3m['hit_pct']} | {s3m['dual_n']} | {s3m['fallback_n']} | {s3m['avg_calls_per_day']} | {s3m['wins']}/{s3m['losses']} |",
        f"| **3y** | {s3y['days_with_call']}/{s3y['sessions']} | {s3y['n']} | {s3y['coverage_pct']} | {s3y['hit_pct']} | {s3y['dual_n']} | {s3y['fallback_n']} | {s3y['avg_calls_per_day']} | {s3y['wins']}/{s3y['losses']} |",
        "",
        "## 3m months",
        "",
        "| Month | N | Hit | W/L |",
        "|---|---:|---:|---|",
    ]
    for m, ms in (s3m.get("by_month") or {}).items():
        lines.append(f"| {m} | {ms['n']} | {ms['hit_pct']} | {ms['wins']}/{ms['losses']} |")
    lines += ["", "_No call-count restriction._", ""]
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps({**payload, "by_month_3m": s3m.get("by_month"), "by_month_1y": s1.get("by_month")}, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"Wrote {OUT_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
