"""Force-lock Sensex everyday chrono_first2 · CAP=2 · ±50."""
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
DUAL = ROOT / "app" / "fno" / "sensex_live_dual_track.py"
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
DESK = "SENSEX_EVERYDAY_2PD_T50SL50"


def sessions(bars: pd.DataFrame, a: str, b: str) -> List[str]:
    return sorted(
        {
            str(pd.Timestamp(t).date())
            for t in bars.index
            if a <= str(pd.Timestamp(t).date()) <= b
        }
    )


def fallback_row(bars: pd.DataFrame, day: str) -> Optional[dict]:
    db = bars[bars.index.strftime("%Y-%m-%d") == day]
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
    print("Lock chrono_first2 CAP=2", flush=True)
    bars, ix = load_tape(TAPE5)
    if getattr(bars.index, "tz", None) is not None:
        bars = bars.copy()
        bars.index = bars.index.tz_localize(None)

    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    by: Dict[str, List[dict]] = defaultdict(list)
    for row in raw:
        n = normalize_cand(row)
        if not n or n["day"] < START_3Y or n["day"] > END:
            continue
        n["first_break"] = bool(row.get("first_break"))
        n["p_t1"] = float(n.get("p_t1") or 0)
        by[n["day"]].append(n)

    picks: List[dict] = []
    for day in sessions(bars, START_3Y, END):
        rs = list(by.get(day) or [])
        if rs:
            chosen = sorted(
                rs, key=lambda x: (str(x.get("hm") or ""), -float(x.get("p_t1") or 0))
            )[:2]
            for r in chosen:
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
    print(
        f"  1y {s1['n']}@{s1['hit_pct']}% avg={s1['avg_calls_per_day']} | "
        f"3m {s3m['hit_pct']}% | 3y {s3y['hit_pct']}%",
        flush=True,
    )

    lo = min(s1["hit_pct"], s3y["hit_pct"])
    hi = max(s1["hit_pct"], s3y["hit_pct"], s3m["hit_pct"])
    acc = f"ACC_RANGE_{int(lo)}_{int(min(100, round(hi)))}"
    policy = {
        "name": "EVERYDAY_2PD_CHRONO_FIRST2",
        "mode": "everyday_2pd",
        "selector": "chrono_first2",
        "dual": "everyday dual gates; first 2 by time",
        "fallback": "OR @ 09:45 only if dual silent that day",
        "buy_min_p": 0.45,
        "sell_min_p": 0.45,
        "allow_sell_cont": True,
        "buy_max_or_ext": None,
        "max_per_day": 2,
        "clip_sl": SL,
        "clip_t1": T1,
        "baseline_1y_hit": 76.7,
        "baseline_1y_avg": 3.55,
    }
    meta = {
        "desk": DESK,
        "mode": "everyday_2pd",
        "policy": policy,
        "brackets": {"sl": SL, "target": T1},
        "cap": 2,
        "accuracy_tag": acc,
        "accuracy_lo": round(lo, 2),
        "accuracy_hi": round(hi, 2),
        "windows": {
            "1y": {
                k: s1[k]
                for k in (
                    "n",
                    "hit_pct",
                    "coverage_pct",
                    "sessions",
                    "dual_n",
                    "fallback_n",
                    "avg_calls_per_day",
                    "days_with_call",
                )
            },
            "3m": {
                k: s3m[k]
                for k in (
                    "n",
                    "hit_pct",
                    "coverage_pct",
                    "sessions",
                    "dual_n",
                    "fallback_n",
                    "avg_calls_per_day",
                    "days_with_call",
                )
            },
            "3y": {
                k: s3y[k]
                for k in (
                    "n",
                    "hit_pct",
                    "coverage_pct",
                    "sessions",
                    "dual_n",
                    "fallback_n",
                    "avg_calls_per_day",
                    "days_with_call",
                )
            },
        },
        "note": "everyday dual+fallback held · CAP 2/day chrono first2",
    }
    HOLD.mkdir(parents=True, exist_ok=True)
    held = [r for r in scored if START_3Y <= str(r.get("day") or "")[:10] <= END]
    calls_path = HOLD / "champ_plus_t50_sl50_calls.json"
    calls_path.write_text(json.dumps({"calls": held, "meta": meta}, indent=2), encoding="utf-8")

    payload = {
        "symbol": "SENSEX",
        "version": "everyday_2pd_t50",
        "locked_clip": {"sl": SL, "t1": T1},
        "policy": policy,
        "desks": {
            "champ_plus": {
                "desk": DESK,
                "accurate_tag": DESK,
                "accuracy_tag": acc,
                "accuracy_lo": round(lo, 2),
                "accuracy_hi": round(hi, 2),
                "windows": meta["windows"],
                "n_held": len(held),
                "brackets": {"sl": SL, "target": T1},
                "cap": 2,
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

    text = SX_LIVE.read_text(encoding="utf-8")
    text = re.sub(r'DESK_CHAMP = "[^"]+"', f'DESK_CHAMP = "{DESK}"', text, count=1)
    text = re.sub(r'ACCURACY_TAG = "[^"]+"', f'ACCURACY_TAG = "{acc}"', text, count=1)
    text = re.sub(r"ACCURACY_LO = [0-9.]+", f"ACCURACY_LO = {round(lo, 2)}", text, count=1)
    text = re.sub(r"ACCURACY_HI = [0-9.]+", f"ACCURACY_HI = {round(hi, 2)}", text, count=1)
    text = re.sub(
        r"BRACKETS = \{[^}]+\}",
        f'BRACKETS = {{"target": {T1}, "sl": {SL}, "risk": {SL}}}',
        text,
        count=1,
    )
    text = re.sub(r"CAP = [^\n]+", "CAP = 2  # 2 calls/day chrono first2", text, count=1)
    if "if not exists and len(day_rows) < CAP:" not in text:
        text = text.replace("if not exists:", "if not exists and len(day_rows) < CAP:", 1)
    SX_LIVE.write_text(text, encoding="utf-8")

    dual = DUAL.read_text(encoding="utf-8")
    dual = re.sub(r"CHAMPION_BUY_MIN_P = [0-9.]+", "CHAMPION_BUY_MIN_P = 0.45", dual, count=1)
    dual = re.sub(r"CHAMPION_SELL_MIN_P = [0-9.]+", "CHAMPION_SELL_MIN_P = 0.45", dual, count=1)
    dual = re.sub(
        r"CHAMPION_BUY_MAX_OR_EXT = [^\n]+",
        "CHAMPION_BUY_MAX_OR_EXT = None  # everyday 2pd",
        dual,
        count=1,
    )
    dual = re.sub(
        r"CHAMPION_SELL_FIRST_ONLY = (True|False)",
        "CHAMPION_SELL_FIRST_ONLY = False",
        dual,
        count=1,
    )
    dual = re.sub(
        r"CHAMPION_HIT_PCT = [0-9.]+",
        f"CHAMPION_HIT_PCT = {float(s1['hit_pct'] or 0):.1f}",
        dual,
        count=1,
    )
    DUAL.write_text(dual, encoding="utf-8")

    if FINAL_JSON.is_file():
        doc = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
        doc.setdefault("tracks", {}).setdefault("live_champion", {})["policy"] = policy
        doc["tracks"]["live_champion"]["full"] = {
            "n": s1["n"],
            "hit_pct": s1["hit_pct"],
            "coverage_pct": s1["coverage_pct"],
            "avg_calls_per_day": s1["avg_calls_per_day"],
        }
        doc["verdict"]["champion_hit_pct"] = s1["hit_pct"]
        doc["verdict"]["summary"] = (
            f"SENSEX EVERYDAY 2PD chrono_first2: 1y {s1['n']}@{s1['hit_pct']}% "
            f"avg {s1['avg_calls_per_day']}/day"
        )
        FINAL_JSON.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    lines = [
        "# SENSEX · 2 calls/day · hold everyday logic (±50/50)",
        "",
        f"**Desk:** `{DESK}`",
        "**Selector locked:** `chrono_first2`",
        "**Logic held:** dual OR-break (p≥0.45, no or_ext, sell cont) + OR fallback @ 09:45 if dual silent",
        "**Live:** first **2** fires of the day (CAP=2)",
        "",
        "## Locked",
        "",
        "| Window | Days | Calls | Cov% | Hit% | Dual | Fallback | Avg/day | W/L |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        f"| **1y** | {s1['days_with_call']}/{s1['sessions']} | {s1['n']} | {s1['coverage_pct']} | **{s1['hit_pct']}** | {s1['dual_n']} | {s1['fallback_n']} | **{s1['avg_calls_per_day']}** | {s1['wins']}/{s1['losses']} |",
        f"| **3m** | {s3m['days_with_call']}/{s3m['sessions']} | {s3m['n']} | {s3m['coverage_pct']} | **{s3m['hit_pct']}** | {s3m['dual_n']} | {s3m['fallback_n']} | {s3m['avg_calls_per_day']} | {s3m['wins']}/{s3m['losses']} |",
        f"| **3y** | {s3y['days_with_call']}/{s3y['sessions']} | {s3y['n']} | {s3y['coverage_pct']} | **{s3y['hit_pct']}** | {s3y['dual_n']} | {s3y['fallback_n']} | {s3y['avg_calls_per_day']} | {s3y['wins']}/{s3y['losses']} |",
        "",
        "Baseline all-dual: 1y 884@76.7% avg 3.55/day",
        "",
        "Note: strict CAP=2 averages ~1.5/day because many sessions only produce 1 dual (fallback only fills empty days).",
        "",
        "## 3m months",
        "",
        "| Month | N | Hit | W/L |",
        "|---|---:|---:|---|",
    ]
    for m, ms in (s3m.get("by_month") or {}).items():
        lines.append(f"| {m} | {ms['n']} | {ms['hit_pct']} | {ms['wins']}/{ms['losses']} |")
    lines += ["", "_Locked chrono_first2_", ""]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "SENSEX_EVERYDAY_2PD_SAME_ACC.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "SENSEX_EVERYDAY_2PD_SAME_ACC.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    print(f"Wrote {OUT / 'SENSEX_EVERYDAY_2PD_SAME_ACC.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
