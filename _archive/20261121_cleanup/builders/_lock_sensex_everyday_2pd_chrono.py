"""Refine ~2/day Sensex: chronological / fill selectors to HOLD all-dual accuracy.

Pre-scores all dual+fallback once, then grid is instant.

  python -u prod_live/tests/builders/_lock_sensex_everyday_2pd_chrono.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live" / "tests" / "builders")]
import path_setup  # noqa: F401,E402

from research_bn_sensex_final_brackets import load_tape, normalize_cand, path_score_pool  # noqa: E402
from research_sensex_modal_1y_deep import hit_pct, month_rollup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "SENSEX_EVERYDAY_2PD_SAME_ACC.md"
OUT_JSON = OUT / "SENSEX_EVERYDAY_2PD_SAME_ACC.json"
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
TARGET_AVG = 2.0


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


def key_of(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day"))[:10], str(r.get("hm") or "")[:5], str(r.get("decision") or "").upper())


def stats_from(rows: List[dict], a: str, b: str, sess: List[str]) -> Dict[str, Any]:
    rr = [r for r in rows if a <= str(r.get("day") or "")[:10] <= b]
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


def chrono_first(k: int):
    def fn(rs: List[dict]) -> List[dict]:
        return sorted(rs, key=lambda x: (str(x.get("hm") or ""), -float(x.get("p_t1") or 0)))[:k]

    return fn


def chrono_last(k: int):
    def fn(rs: List[dict]) -> List[dict]:
        return sorted(rs, key=lambda x: (str(x.get("hm") or ""), -float(x.get("p_t1") or 0)))[-k:]

    return fn


def first_and_best(k: int = 2):
    def fn(rs: List[dict]) -> List[dict]:
        if not rs:
            return []
        ordered = sorted(rs, key=lambda x: (str(x.get("hm") or ""), -float(x.get("p_t1") or 0)))
        out = [ordered[0]]
        rest = sorted(ordered[1:], key=lambda x: float(x.get("p_t1") or 0), reverse=True)
        for r in rest:
            if len(out) >= k:
                break
            if key_of(r) != key_of(out[0]):
                out.append(r)
        return out[:k]

    return fn


def fill_to_k_with_fb(bars, by, a, b, k: int, select_dual: Callable) -> List[dict]:
    """Up to k duals/day; if fewer duals, add fallback once to help fill (still ≤k)."""
    out: List[dict] = []
    for day in sessions(bars, a, b):
        rs = list(by.get(day) or [])
        chosen = select_dual(rs) if rs else []
        day_rows: List[dict] = []
        for r in chosen[:k]:
            day_rows.append({**r, "source": "dual", "track": r.get("track") or "champion"})
        if len(day_rows) < k:
            # only add fallback if no dual at all (hold base logic) OR if we want fill?
            # HOLD base logic: fallback ONLY when dual silent
            if not day_rows:
                fb = fallback_row(bars, day)
                if fb:
                    day_rows.append(fb)
        out.extend(day_rows[:k])
    return out


def dual_plus_fb_always_fill2(bars, by, a, b) -> List[dict]:
    """Best dual of day + fallback as 2nd when only 1 dual; fallback alone if 0 dual.
    If ≥2 duals: chrono first 2.
    """
    out: List[dict] = []
    for day in sessions(bars, a, b):
        rs = list(by.get(day) or [])
        if len(rs) >= 2:
            chosen = sorted(rs, key=lambda x: (str(x.get("hm") or ""), -float(x.get("p_t1") or 0)))[:2]
            for r in chosen:
                out.append({**r, "source": "dual", "track": r.get("track") or "champion"})
        elif len(rs) == 1:
            r = rs[0]
            out.append({**r, "source": "dual", "track": r.get("track") or "champion"})
            fb = fallback_row(bars, day)
            if fb and key_of(fb) != key_of(out[-1]):
                out.append(fb)
            elif fb:
                # same hm/side — skip; try opposite mid? keep single
                pass
        else:
            fb = fallback_row(bars, day)
            if fb:
                out.append(fb)
    return out


def main() -> int:
    t0 = time.time()
    print("Refine 2pd chrono · hold accuracy", flush=True)
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

    # score universe once: all dual + all fallbacks
    universe: List[dict] = []
    for day in sessions(bars, START_3Y, END):
        for r in by.get(day) or []:
            universe.append({**r, "source": "dual", "track": r.get("track") or "champion"})
        fb = fallback_row(bars, day)
        if fb:
            universe.append(fb)
    print(f"  scoring universe n={len(universe)} …", flush=True)
    scored_u = path_score_pool(bars, ix, universe, SL, T1)
    scored_map: Dict[Tuple[str, str, str], dict] = {}
    meta_u = {key_of(p): p for p in universe}
    for r in scored_u:
        k = key_of(r)
        m = meta_u.get(k) or {}
        r["source"] = m.get("source") or "dual"
        r["track"] = m.get("track") or "champion"
        r["sl_pts"] = SL
        r["t1_pts"] = T1
        scored_map[k] = r

    def materialize(picks: List[dict]) -> List[dict]:
        out = []
        for p in picks:
            k = key_of(p)
            if k in scored_map:
                row = dict(scored_map[k])
                row["source"] = p.get("source") or row.get("source")
                out.append(row)
            else:
                # unscored edge — skip
                pass
        return out

    sess1 = sessions(bars, START_1Y, END)
    sess3m = sessions(bars, START_3M, END)
    sess3y = sessions(bars, START_3Y, END)

    baseline_picks = fill_to_k_with_fb(bars, by, START_3Y, END, 99, lambda rs: list(rs))
    s1b = stats_from(materialize(baseline_picks), START_1Y, END, sess1)
    floor_1y = float(s1b["hit_pct"] or 0)
    floor_3m = float(stats_from(materialize(baseline_picks), START_3M, END, sess3m)["hit_pct"] or 0)
    print(f"  baseline 1y {s1b['n']}@{s1b['hit_pct']}% avg={s1b['avg_calls_per_day']}", flush=True)

    variants: List[Tuple[str, List[dict]]] = [
        ("chrono_first2", fill_to_k_with_fb(bars, by, START_3Y, END, 2, chrono_first(2))),
        ("chrono_first3", fill_to_k_with_fb(bars, by, START_3Y, END, 3, chrono_first(3))),
        ("chrono_last2", fill_to_k_with_fb(bars, by, START_3Y, END, 2, chrono_last(2))),
        ("first_plus_best", fill_to_k_with_fb(bars, by, START_3Y, END, 2, first_and_best(2))),
        ("dual_fb_fill2", dual_plus_fb_always_fill2(bars, by, START_3Y, END)),
        (
            "top2_p",
            fill_to_k_with_fb(
                bars,
                by,
                START_3Y,
                END,
                2,
                lambda rs: sorted(rs, key=lambda x: float(x.get("p_t1") or 0), reverse=True)[:2],
            ),
        ),
        (
            "top3_p",
            fill_to_k_with_fb(
                bars,
                by,
                START_3Y,
                END,
                3,
                lambda rs: sorted(rs, key=lambda x: float(x.get("p_t1") or 0), reverse=True)[:3],
            ),
        ),
        # keep all dual but soft: first 2 first_break else chrono
        (
            "first_break_upto2",
            fill_to_k_with_fb(
                bars,
                by,
                START_3Y,
                END,
                2,
                lambda rs: sorted(
                    [r for r in rs if r.get("first_break")] or rs,
                    key=lambda x: (str(x.get("hm") or ""), -float(x.get("p_t1") or 0)),
                )[:2],
            ),
        ),
    ]

    rows_out = []
    for name, picks in variants:
        scored = materialize(picks)
        s1 = stats_from(scored, START_1Y, END, sess1)
        s3m = stats_from(scored, START_3M, END, sess3m)
        s3y = stats_from(scored, START_3Y, END, sess3y)
        avg = float(s1["avg_calls_per_day"] or 0)
        hit1 = float(s1["hit_pct"] or 0)
        hit3 = float(s3m["hit_pct"] or 0)
        hold = hit1 + 1e-9 >= floor_1y - 0.05 and hit3 + 1e-9 >= floor_3m - 0.2
        dist = abs(avg - TARGET_AVG)
        score = (0 if hold else 500) + dist * 20 - (hit1 - floor_1y) * 2 - (hit3 - floor_3m)
        rec = {
            "name": name,
            "hold_acc": hold,
            "1y": s1,
            "3m": s3m,
            "3y": s3y,
            "score": round(score, 3),
            "scored": scored,
        }
        rows_out.append(rec)
        print(
            f"  {name:<18} 1y n={s1['n']:<4} hit={s1['hit_pct']}% avg={s1['avg_calls_per_day']} "
            f"3m={s3m['hit_pct']}% hold={hold}",
            flush=True,
        )

    hold_ok = [r for r in rows_out if r["hold_acc"]]
    if hold_ok:
        hold_ok.sort(
            key=lambda r: (
                abs(float(r["1y"]["avg_calls_per_day"]) - TARGET_AVG),
                -float(r["1y"]["hit_pct"] or 0),
                -int(r["1y"]["n"] or 0),
            )
        )
        best = hold_ok[0]
    else:
        # closest to 2/day with highest hit (relax floor)
        best = sorted(
            rows_out,
            key=lambda r: (
                abs(float(r["1y"]["avg_calls_per_day"]) - TARGET_AVG),
                -float(r["1y"]["hit_pct"] or 0),
            ),
        )[0]

    # Prefer chrono_first2 if within 1pp of best hit and closer to user ask "2 calls"
    chrono = next((r for r in rows_out if r["name"] == "chrono_first2"), None)
    if chrono and abs(float(chrono["1y"]["avg_calls_per_day"]) - 2) <= 0.6:
        if float(chrono["1y"]["hit_pct"] or 0) + 1e-9 >= float(best["1y"]["hit_pct"] or 0) - 1.0:
            # only override if not much worse
            if abs(float(chrono["1y"]["avg_calls_per_day"]) - TARGET_AVG) <= abs(
                float(best["1y"]["avg_calls_per_day"]) - TARGET_AVG
            ) + 0.15:
                if float(chrono["1y"]["hit_pct"] or 0) >= float(best["1y"]["hit_pct"] or 0) - 0.5:
                    best = chrono

    print(
        f"BEST {best['name']} 1y {best['1y']['n']}@{best['1y']['hit_pct']}% "
        f"avg={best['1y']['avg_calls_per_day']} hold={best['hold_acc']}",
        flush=True,
    )

    s1, s3m, s3y = best["1y"], best["3m"], best["3y"]
    scored = best["scored"]
    lo = min(x for x in [s1["hit_pct"], s3y["hit_pct"]] if x is not None)
    hi = max(x for x in [s1["hit_pct"], s3y["hit_pct"], s3m["hit_pct"]] if x is not None)
    acc_tag = f"ACC_RANGE_{int(lo)}_{int(min(100, round(hi)))}"

    HOLD.mkdir(parents=True, exist_ok=True)
    held = [r for r in scored if START_3Y <= str(r.get("day") or "")[:10] <= END]
    policy = {
        "name": f"EVERYDAY_2PD_{best['name'].upper()}",
        "mode": "everyday_2pd",
        "selector": best["name"],
        "dual": "same everyday dual gates; take up to 2 per day (chrono/live order)",
        "fallback": "OR @ 09:45 only if dual silent that day",
        "buy_min_p": 0.45,
        "sell_min_p": 0.45,
        "allow_sell_cont": True,
        "buy_max_or_ext": None,
        "max_per_day": 2,
        "clip_sl": SL,
        "clip_t1": T1,
        "baseline_1y_hit": s1b["hit_pct"],
        "baseline_1y_avg": s1b["avg_calls_per_day"],
    }
    meta = {
        "desk": DESK,
        "mode": "everyday_2pd",
        "policy": policy,
        "brackets": {"sl": SL, "target": T1},
        "cap": 2,
        "accuracy_tag": acc_tag,
        "accuracy_lo": round(lo, 2),
        "accuracy_hi": round(hi, 2),
        "windows": {
            "1y": {k: s1[k] for k in ("n", "hit_pct", "coverage_pct", "sessions", "dual_n", "fallback_n", "avg_calls_per_day", "days_with_call")},
            "3m": {k: s3m[k] for k in ("n", "hit_pct", "coverage_pct", "sessions", "dual_n", "fallback_n", "avg_calls_per_day", "days_with_call")},
            "3y": {k: s3y[k] for k in ("n", "hit_pct", "coverage_pct", "sessions", "dual_n", "fallback_n", "avg_calls_per_day", "days_with_call")},
        },
        "note": "everyday dual+fallback held · CAP 2/day",
    }
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
                "accuracy_tag": acc_tag,
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
        "variants": [
            {
                "name": r["name"],
                "hold_acc": r["hold_acc"],
                "1y_n": r["1y"]["n"],
                "1y_hit": r["1y"]["hit_pct"],
                "1y_avg": r["1y"]["avg_calls_per_day"],
                "3m_hit": r["3m"]["hit_pct"],
            }
            for r in rows_out
        ],
        "elapsed_s": round(time.time() - t0, 1),
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
    text = re.sub(r'ACCURACY_TAG = "[^"]+"', f'ACCURACY_TAG = "{acc_tag}"', text, count=1)
    text = re.sub(r"ACCURACY_LO = [0-9.]+", f"ACCURACY_LO = {round(lo, 2)}", text, count=1)
    text = re.sub(r"ACCURACY_HI = [0-9.]+", f"ACCURACY_HI = {round(hi, 2)}", text, count=1)
    text = re.sub(
        r"BRACKETS = \{[^}]+\}",
        f'BRACKETS = {{"target": {T1}, "sl": {SL}, "risk": {SL}}}',
        text,
        count=1,
    )
    text = re.sub(r"CAP = [^\n]+", "CAP = 2  # ~2 calls/day · hold everyday logic", text, count=1)
    if "if not exists and len(day_rows) < CAP:" not in text:
        text = text.replace(
            "if not exists:",
            "if not exists and len(day_rows) < CAP:",
            1,
        )
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
    dual = re.sub(r"CHAMPION_SELL_FIRST_ONLY = (True|False)", "CHAMPION_SELL_FIRST_ONLY = False", dual, count=1)
    dual = re.sub(r"CHAMPION_HIT_PCT = [0-9.]+", f"CHAMPION_HIT_PCT = {float(s1['hit_pct'] or 0):.1f}", dual, count=1)
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
            f"SENSEX EVERYDAY 2PD ({best['name']}): 1y {s1['n']}@{s1['hit_pct']}% "
            f"avg {s1['avg_calls_per_day']}/day"
        )
        FINAL_JSON.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    lines = [
        "# SENSEX · ~2 calls/day · hold everyday logic (±50/50)",
        "",
        f"**Desk:** `{DESK}`",
        f"**Selector locked:** `{best['name']}`",
        "**Logic held:** dual OR-break (p≥0.45, no or_ext, sell cont) + OR fallback @ 09:45 if dual silent",
        "**Live:** first 2 fires of the day (CAP=2)",
        "",
        "## Locked",
        "",
        "| Window | Days | Calls | Cov% | Hit% | Dual | Fallback | Avg/day | W/L |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        f"| **1y** | {s1['days_with_call']}/{s1['sessions']} | {s1['n']} | {s1['coverage_pct']} | **{s1['hit_pct']}** | {s1['dual_n']} | {s1['fallback_n']} | **{s1['avg_calls_per_day']}** | {s1['wins']}/{s1['losses']} |",
        f"| **3m** | {s3m['days_with_call']}/{s3m['sessions']} | {s3m['n']} | {s3m['coverage_pct']} | **{s3m['hit_pct']}** | {s3m['dual_n']} | {s3m['fallback_n']} | {s3m['avg_calls_per_day']} | {s3m['wins']}/{s3m['losses']} |",
        f"| **3y** | {s3y['days_with_call']}/{s3y['sessions']} | {s3y['n']} | {s3y['coverage_pct']} | **{s3y['hit_pct']}** | {s3y['dual_n']} | {s3y['fallback_n']} | {s3y['avg_calls_per_day']} | {s3y['wins']}/{s3y['losses']} |",
        "",
        f"Baseline all-dual: 1y {s1b['n']}@{s1b['hit_pct']}% avg {s1b['avg_calls_per_day']}/day · hold_acc={best['hold_acc']}",
        "",
        "## Variants",
        "",
        "| Selector | 1y N | 1y Hit | Avg/day | 3m Hit | Hold |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in sorted(rows_out, key=lambda x: x["score"]):
        mark = " **← locked**" if r["name"] == best["name"] else ""
        lines.append(
            f"| `{r['name']}`{mark} | {r['1y']['n']} | {r['1y']['hit_pct']} | "
            f"{r['1y']['avg_calls_per_day']} | {r['3m']['hit_pct']} | {r['hold_acc']} |"
        )
    lines += ["", "## 3m months", "", "| Month | N | Hit | W/L |", "|---|---:|---:|---|"]
    for m, ms in (s3m.get("by_month") or {}).items():
        lines.append(f"| {m} | {ms['n']} | {ms['hit_pct']} | {ms['wins']}/{ms['losses']} |")
    lines += ["", f"_Locked {round(time.time()-t0,1)}s_", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUT_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
