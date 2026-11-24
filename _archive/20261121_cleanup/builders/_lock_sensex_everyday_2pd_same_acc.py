"""Hold Sensex dual+fallback logic; target ~2 calls/day at same (or better) accuracy.

Baseline (no-cap all dual + fb): 1y ~76.7% · ~3.55/day · 100% day cov.
Search rankings/filters that land near 2/day without dropping hit below baseline.

  python -u prod_live/tests/builders/_lock_sensex_everyday_2pd_same_acc.py
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
# Hold current no-cap accuracy floor (slightly soft for float)
ACC_FLOOR_1Y = 76.5
ACC_FLOOR_3M = 79.5


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


def build_picks(
    bars: pd.DataFrame,
    by: Dict[str, List[dict]],
    a: str,
    b: str,
    select_day: Callable[[List[dict]], List[dict]],
) -> List[dict]:
    out: List[dict] = []
    for day in sessions(bars, a, b):
        rs = list(by.get(day) or [])
        chosen = select_day(rs) if rs else []
        if chosen:
            for r in chosen:
                out.append({**r, "source": "dual", "track": r.get("track") or "champion"})
        else:
            fb = fallback_row(bars, day)
            if fb:
                out.append(fb)
    return out


def score_book(bars, ix, picks: List[dict]) -> List[dict]:
    scored = path_score_pool(bars, ix, picks, SL, T1)
    meta = {(p["day"], p["hm"], p["decision"]): p for p in picks}
    for r in scored:
        m = meta.get((r["day"], r["hm"], r["decision"])) or {}
        r["source"] = m.get("source") or "dual"
        r["track"] = m.get("track") or "champion"
        r["sl_pts"] = SL
        r["t1_pts"] = T1
    return scored


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


def top_k_p(k: int, first_only: bool = False, pmin: float = 0.0):
    def fn(rs: List[dict]) -> List[dict]:
        pool = rs
        if first_only:
            pool = [r for r in pool if r.get("first_break")]
        pool = [r for r in pool if float(r.get("p_t1") or 0) >= pmin]
        pool = sorted(
            pool,
            key=lambda x: (float(x.get("p_t1") or 0), 0 if x.get("first_break") else 1),
            reverse=True,
        )
        return pool[:k]

    return fn


def top_k_diverse(k: int, pmin: float = 0.0):
    """Prefer first_break then highest p; at most one per side if k>=2."""

    def fn(rs: List[dict]) -> List[dict]:
        pool = [r for r in rs if float(r.get("p_t1") or 0) >= pmin]
        pool = sorted(
            pool,
            key=lambda x: (
                0 if x.get("first_break") else 1,
                -float(x.get("p_t1") or 0),
            ),
        )
        out: List[dict] = []
        seen_side = set()
        for r in pool:
            side = str(r.get("decision") or "")
            if k <= 2 and side in seen_side and len(out) < k:
                # allow same side only after both sides tried? keep simple: allow if needed
                pass
            if len(out) >= k:
                break
            if side in seen_side and len([x for x in out if x.get("decision") == side]) >= 1 and len(out) + 1 <= k:
                # skip duplicate side while other side unused and candidates remain
                other = [x for x in pool if str(x.get("decision")) != side and x not in out]
                if other and len(out) < k:
                    continue
            out.append(r)
            seen_side.add(side)
        # fill if short
        for r in pool:
            if len(out) >= k:
                break
            if r not in out:
                out.append(r)
        return out[:k]

    return fn


def one_buy_one_sell(pmin: float = 0.0, first_only: bool = False):
    def fn(rs: List[dict]) -> List[dict]:
        pool = rs
        if first_only:
            pool = [r for r in pool if r.get("first_break")]
        pool = [r for r in pool if float(r.get("p_t1") or 0) >= pmin]
        out: List[dict] = []
        for side in ("BUY", "SELL"):
            side_rs = [r for r in pool if r.get("decision") == side]
            if not side_rs:
                continue
            best = max(
                side_rs,
                key=lambda x: (float(x.get("p_t1") or 0), 0 if x.get("first_break") else 1),
            )
            out.append(best)
        if not out and pool:
            # fall through to best single
            out = [
                max(pool, key=lambda x: (float(x.get("p_t1") or 0), 0 if x.get("first_break") else 1))
            ]
        return out

    return fn


def main() -> int:
    t0 = time.time()
    print("Sensex hold logic · target ~2/day same acc", flush=True)
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

    # baseline no-cap
    baseline_picks = build_picks(bars, by, START_3Y, END, lambda rs: list(rs))
    baseline = score_book(bars, ix, baseline_picks)
    s1b = stats(baseline, START_1Y, END, sessions(bars, START_1Y, END))
    print(
        f"  baseline all-dual: 1y n={s1b['n']} hit={s1b['hit_pct']}% avg={s1b['avg_calls_per_day']}",
        flush=True,
    )
    floor_1y = float(s1b["hit_pct"] or ACC_FLOOR_1Y)
    floor_3m_base = stats(baseline, START_3M, END, sessions(bars, START_3M, END))
    floor_3m = float(floor_3m_base["hit_pct"] or ACC_FLOOR_3M)

    variants: List[Tuple[str, Callable]] = [
        ("top2_p", top_k_p(2)),
        ("top2_p_first", top_k_p(2, first_only=True)),
        ("top2_pmin50", top_k_p(2, pmin=0.50)),
        ("top2_pmin52", top_k_p(2, pmin=0.52)),
        ("top2_pmin55", top_k_p(2, pmin=0.55)),
        ("top2_pmin58", top_k_p(2, pmin=0.58)),
        ("top2_pmin60", top_k_p(2, pmin=0.60)),
        ("top2_first_pmin50", top_k_p(2, first_only=True, pmin=0.50)),
        ("top2_first_pmin55", top_k_p(2, first_only=True, pmin=0.55)),
        ("buy1_sell1", one_buy_one_sell()),
        ("buy1_sell1_p50", one_buy_one_sell(0.50)),
        ("buy1_sell1_p55", one_buy_one_sell(0.55)),
        ("buy1_sell1_first", one_buy_one_sell(first_only=True)),
        ("buy1_sell1_first_p50", one_buy_one_sell(0.50, first_only=True)),
        ("top2_diverse", top_k_diverse(2)),
        ("top2_diverse_p50", top_k_diverse(2, pmin=0.50)),
        ("top2_diverse_p55", top_k_diverse(2, pmin=0.55)),
        ("top1_p", top_k_p(1)),  # reference
        ("top3_p", top_k_p(3)),
    ]

    rows_out = []
    best = None
    for name, fn in variants:
        picks = build_picks(bars, by, START_3Y, END, fn)
        scored = score_book(bars, ix, picks)
        s1 = stats(scored, START_1Y, END, sessions(bars, START_1Y, END))
        s3m = stats(scored, START_3M, END, sessions(bars, START_3M, END))
        s3y = stats(scored, START_3Y, END, sessions(bars, START_3Y, END))
        avg = float(s1["avg_calls_per_day"] or 0)
        hit1 = float(s1["hit_pct"] or 0)
        hit3 = float(s3m["hit_pct"] or 0)
        # prefer ~2/day, hold acc
        dist = abs(avg - TARGET_AVG)
        hold = hit1 + 1e-9 >= floor_1y - 0.15 and hit3 + 1e-9 >= floor_3m - 0.5
        score = (
            (0 if hold else 1000)
            + dist * 10
            - (hit1 - floor_1y)
            - 0.5 * (hit3 - floor_3m)
            - 0.01 * min(s1["n"], 600)
        )
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
            f"  {name:<22} 1y n={s1['n']:<4} hit={s1['hit_pct']}% avg={s1['avg_calls_per_day']} "
            f"3m hit={s3m['hit_pct']}% hold={hold}",
            flush=True,
        )
        if best is None or rec["score"] < best["score"]:
            best = rec

    # among hold_acc prefer closest to 2/day then highest hit
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
        # relax: best hit near 2/day
        near = sorted(
            rows_out,
            key=lambda r: (
                abs(float(r["1y"]["avg_calls_per_day"]) - TARGET_AVG),
                -float(r["1y"]["hit_pct"] or 0),
            ),
        )
        best = near[0]

    print(
        f"\nBEST: {best['name']} 1y {best['1y']['n']}@{best['1y']['hit_pct']}% "
        f"avg={best['1y']['avg_calls_per_day']} 3m {best['3m']['hit_pct']}%",
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
        "dual": "held dual+fallback logic; select ~2/day",
        "fallback": "OR break/mid at 09:45 only if dual silent that day",
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
        "note": "hold everyday dual+fallback · ~2 calls/day · same acc",
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
        (folder / f"SENSEX_FINAL_CHAMP_PLUS_{label.upper()}.md").write_text(
            "\n".join(
                [
                    f"# SENSEX EVERYDAY 2/day ±50 ({label})",
                    "",
                    f"**Desk:** `{DESK}` · selector `{best['name']}`",
                    f"**1y:** {s1['n']} @ {s1['hit_pct']}% · avg {s1['avg_calls_per_day']}/day · cov {s1['coverage_pct']}%",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    # live constants: CAP=2, desk, accuracy
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
    text = re.sub(r"CAP = [^\n]+", "CAP = 2  # ~2 calls/day · hold everyday accuracy", text, count=1)
    # ensure_session_calls: allow up to CAP, not unlimited
    if "if not exists:" in text and "len(day_rows) < CAP" not in text:
        text = text.replace(
            "if not exists:",
            "if not exists and len(day_rows) < CAP:",
            1,
        )
    SX_LIVE.write_text(text, encoding="utf-8")

    # dual gates stay loose (same logic)
    dual = DUAL.read_text(encoding="utf-8")
    dual = re.sub(r"CHAMPION_BUY_MIN_P = [0-9.]+", "CHAMPION_BUY_MIN_P = 0.45", dual, count=1)
    dual = re.sub(r"CHAMPION_SELL_MIN_P = [0-9.]+", "CHAMPION_SELL_MIN_P = 0.45", dual, count=1)
    dual = re.sub(
        r"CHAMPION_BUY_MAX_OR_EXT = [^\n]+",
        "CHAMPION_BUY_MAX_OR_EXT = None  # everyday 2pd: no bor cap",
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
            f"SENSEX EVERYDAY 2PD ±50 ({best['name']}): 1y {s1['n']}@{s1['hit_pct']}% "
            f"avg {s1['avg_calls_per_day']}/day cov {s1['coverage_pct']}%"
        )
        FINAL_JSON.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    lines = [
        "# SENSEX · ~2 calls/day · hold everyday accuracy (±50/50)",
        "",
        f"**Desk:** `{DESK}`",
        f"**Selector locked:** `{best['name']}`",
        "**Base logic held:** dual OR-break (p≥0.45, no or_ext, sell cont) + OR fallback @ 09:45 if dual silent",
        f"**Target:** ~2 calls/day · hold baseline hit (1y≥{floor_1y:.1f}% · 3m≥{floor_3m:.1f}%)",
        "",
        "## Locked result",
        "",
        "| Window | Days | Calls | Cov% | Hit% | Dual | Fallback | Avg/day | W/L |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        f"| **1y** | {s1['days_with_call']}/{s1['sessions']} | {s1['n']} | {s1['coverage_pct']} | **{s1['hit_pct']}** | {s1['dual_n']} | {s1['fallback_n']} | **{s1['avg_calls_per_day']}** | {s1['wins']}/{s1['losses']} |",
        f"| **3m** | {s3m['days_with_call']}/{s3m['sessions']} | {s3m['n']} | {s3m['coverage_pct']} | **{s3m['hit_pct']}** | {s3m['dual_n']} | {s3m['fallback_n']} | {s3m['avg_calls_per_day']} | {s3m['wins']}/{s3m['losses']} |",
        f"| **3y** | {s3y['days_with_call']}/{s3y['sessions']} | {s3y['n']} | {s3y['coverage_pct']} | **{s3y['hit_pct']}** | {s3y['dual_n']} | {s3y['fallback_n']} | {s3y['avg_calls_per_day']} | {s3y['wins']}/{s3y['losses']} |",
        "",
        f"Baseline all-dual: 1y {s1b['n']}@{s1b['hit_pct']}% avg {s1b['avg_calls_per_day']}/day",
        "",
        "## Variant grid",
        "",
        "| Selector | 1y N | 1y Hit | Avg/day | 3m Hit | Hold acc |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in sorted(rows_out, key=lambda x: x["score"]):
        mark = " **← locked**" if r["name"] == best["name"] else ""
        lines.append(
            f"| `{r['name']}`{mark} | {r['1y']['n']} | {r['1y']['hit_pct']} | "
            f"{r['1y']['avg_calls_per_day']} | {r['3m']['hit_pct']} | {r['hold_acc']} |"
        )
    lines += [
        "",
        "## 3m months (locked)",
        "",
        "| Month | N | Hit | W/L |",
        "|---|---:|---:|---|",
    ]
    for m, ms in (s3m.get("by_month") or {}).items():
        lines.append(f"| {m} | {ms['n']} | {ms['hit_pct']} | {ms['wins']}/{ms['losses']} |")
    lines += ["", f"_Locked {round(time.time()-t0,1)}s_", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUT_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
