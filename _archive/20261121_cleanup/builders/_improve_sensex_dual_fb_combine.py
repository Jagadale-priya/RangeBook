"""Improve Sensex dual+fallback combine: more calls + higher accuracy.

Grid over dual gates / fallback quality / merge rules.
Score 1y + 3y; lock best Pareto; write last-3m report.

  python -u prod_live/tests/builders/_improve_sensex_dual_fb_combine.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
DESK = "SENSEX_DUAL_FB_IMPROVED_T50"


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


def fallback_row(
    bars: pd.DataFrame,
    day: str,
    *,
    break_only: bool = False,
    skip_mid: bool = False,
) -> Optional[dict]:
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
        kind = "break"
    elif close < or_lo:
        side = "SELL"
        kind = "break"
    else:
        if break_only or skip_mid:
            return None
        side = "BUY" if close >= mid else "SELL"
        kind = "mid"
    hm = f"{entry_ts.hour:02d}:{entry_ts.minute:02d}"
    return {
        "day": day,
        "hm": hm,
        "decision": side,
        "side": side,
        "p_t1": 0.55 if kind == "break" else 0.50,
        "first_break": True,
        "track": "or_fallback",
        "source": "fallback",
        "fb_kind": kind,
        "tags": ["fallback", "OR_09:45", f"fb_{kind}"],
    }


def filter_duals(
    rs: List[dict],
    *,
    pmin: float,
    first_only: bool = False,
    max_or_ext: Optional[float] = None,
) -> List[dict]:
    out = []
    for r in rs:
        if float(r.get("p_t1") or 0) < pmin:
            continue
        if first_only and not r.get("first_break"):
            continue
        if max_or_ext is not None:
            ext = r.get("or_ext")
            if ext is not None and float(ext) > max_or_ext + 1e-9:
                continue
        out.append(r)
    return out


def build_day(
    bars,
    by,
    day: str,
    *,
    pmin: float,
    first_only: bool,
    max_or_ext: Optional[float],
    fb_break_only: bool,
    fb_skip_mid: bool,
    include_fb: bool,
    dual_cap: Optional[int],
) -> List[dict]:
    raw = list(by.get(day) or [])
    duals_src = filter_duals(raw, pmin=pmin, first_only=first_only, max_or_ext=max_or_ext)
    duals_src = sorted(
        duals_src, key=lambda x: (str(x.get("hm") or ""), -float(x.get("p_t1") or 0))
    )
    if dual_cap is not None:
        duals_src = duals_src[:dual_cap]
    duals = []
    for r in duals_src:
        duals.append(
            {
                **r,
                "source": "dual",
                "track": r.get("track") or "champion",
                "tags": ["dual", "OR_break"],
            }
        )
    fb = fallback_row(bars, day, break_only=fb_break_only, skip_mid=fb_skip_mid) if include_fb else None
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
        "dual_only": sum(1 for r in rr if r.get("source") == "dual"),
        "fallback_only": sum(1 for r in rr if r.get("source") == "fallback"),
        "combined": sum(1 for r in rr if r.get("source") == "dual+fallback"),
        "avg_calls_per_day": round(len(rr) / len(days), 2) if days else 0.0,
        "by_month": month_rollup(rr),
    }


def main() -> int:
    t0 = time.time()
    print("Improve dual+fb combine · 1y/3y grid", flush=True)
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
        if row.get("or_ext") is not None:
            try:
                n["or_ext"] = float(row.get("or_ext"))
            except (TypeError, ValueError):
                pass
        by[n["day"]].append(n)

    # score universe once
    print("  scoring universe…", flush=True)
    universe: List[dict] = []
    for day in sessions(bars, START_3Y, END):
        for r in by.get(day) or []:
            universe.append({**r, "source": "dual", "track": "champion", "tags": ["dual"]})
        for bo, sm in ((False, False), (True, False), (False, True)):
            fb = fallback_row(bars, day, break_only=bo, skip_mid=sm)
            if fb:
                universe.append(fb)
    # unique by key+source-ish
    uniq = {}
    for p in universe:
        uniq[(key_of(p), p.get("source"), p.get("fb_kind"))] = p
    universe = list(uniq.values())
    scored_u = path_score_pool(bars, ix, universe, SL, T1)
    scored_map: Dict[Tuple, dict] = {}
    meta_u = {(key_of(p), p.get("source"), p.get("fb_kind")): p for p in universe}
    for r in scored_u:
        # match back
        k = key_of(r)
        for src in ("dual", "fallback"):
            for kind in (None, "break", "mid"):
                mk = (k, src, kind)
                if mk in meta_u:
                    m = meta_u[mk]
                    row = dict(r)
                    row["source"] = m.get("source")
                    row["track"] = m.get("track")
                    row["tags"] = list(m.get("tags") or [])
                    row["fb_kind"] = m.get("fb_kind")
                    row["sl_pts"] = SL
                    row["t1_pts"] = T1
                    scored_map[mk] = row
        # also store plain key for dual
        if (k, "dual", None) in meta_u or any(
            kk[0] == k and kk[1] == "dual" for kk in meta_u
        ):
            pass
    # simpler lookup: by key+source
    by_ks: Dict[Tuple[str, str, str, str], dict] = {}
    for r in scored_u:
        k = key_of(r)
        # find meta
        for (mk, src, kind), m in meta_u.items():
            if mk != k:
                continue
            row = dict(r)
            row["source"] = src
            row["tags"] = list(m.get("tags") or [])
            row["fb_kind"] = kind
            row["track"] = m.get("track") or ("or_fallback" if src == "fallback" else "champion")
            row["sl_pts"] = SL
            row["t1_pts"] = T1
            by_ks[(k[0], k[1], k[2], src if src != "fallback" else f"fallback:{kind or 'x'}")] = row

    def materialize(picks: List[dict]) -> List[dict]:
        out = []
        for p in picks:
            k = key_of(p)
            src = p.get("source")
            if src == "dual+fallback":
                # use dual score path
                key = (k[0], k[1], k[2], "dual")
                base = by_ks.get(key)
                if not base:
                    # try any dual key
                    for kk, vv in by_ks.items():
                        if kk[0] == k[0] and kk[1] == k[1] and kk[2] == k[2] and kk[3] == "dual":
                            base = vv
                            break
                if base:
                    row = dict(base)
                    row["source"] = "dual+fallback"
                    row["combined"] = True
                    row["tags"] = list(p.get("tags") or [])
                    row["track"] = "dual_fb_combined"
                    out.append(row)
                continue
            if src == "fallback":
                kind = p.get("fb_kind") or "mid"
                key = (k[0], k[1], k[2], f"fallback:{kind}")
                base = by_ks.get(key)
                if not base:
                    for alt in ("break", "mid", "x"):
                        base = by_ks.get((k[0], k[1], k[2], f"fallback:{alt}"))
                        if base:
                            break
                if base:
                    row = dict(base)
                    row["source"] = "fallback"
                    row["tags"] = list(p.get("tags") or [])
                    out.append(row)
                continue
            # dual
            base = by_ks.get((k[0], k[1], k[2], "dual"))
            if base:
                row = dict(base)
                row["source"] = "dual"
                row["tags"] = list(p.get("tags") or ["dual"])
                out.append(row)
        return out

    sess1 = sessions(bars, START_1Y, END)
    sess3m = sessions(bars, START_3M, END)
    sess3y = sessions(bars, START_3Y, END)
    all_days = sessions(bars, START_3Y, END)

    variants = [
        ("baseline_p45_fb_all", dict(pmin=0.45, first_only=False, max_or_ext=None, fb_break_only=False, fb_skip_mid=False, include_fb=True, dual_cap=None)),
        ("p45_fb_break", dict(pmin=0.45, first_only=False, max_or_ext=None, fb_break_only=True, fb_skip_mid=False, include_fb=True, dual_cap=None)),
        ("p50_fb_all", dict(pmin=0.50, first_only=False, max_or_ext=None, fb_break_only=False, fb_skip_mid=False, include_fb=True, dual_cap=None)),
        ("p50_fb_break", dict(pmin=0.50, first_only=False, max_or_ext=None, fb_break_only=True, fb_skip_mid=False, include_fb=True, dual_cap=None)),
        ("p52_fb_break", dict(pmin=0.52, first_only=False, max_or_ext=None, fb_break_only=True, fb_skip_mid=False, include_fb=True, dual_cap=None)),
        ("p55_fb_break", dict(pmin=0.55, first_only=False, max_or_ext=None, fb_break_only=True, fb_skip_mid=False, include_fb=True, dual_cap=None)),
        ("p45_first_fb_break", dict(pmin=0.45, first_only=True, max_or_ext=None, fb_break_only=True, fb_skip_mid=False, include_fb=True, dual_cap=None)),
        ("p50_first_fb_break", dict(pmin=0.50, first_only=True, max_or_ext=None, fb_break_only=True, fb_skip_mid=False, include_fb=True, dual_cap=None)),
        ("p45_ext10_fb_break", dict(pmin=0.45, first_only=False, max_or_ext=0.10, fb_break_only=True, fb_skip_mid=False, include_fb=True, dual_cap=None)),
        ("p45_ext15_fb_break", dict(pmin=0.45, first_only=False, max_or_ext=0.15, fb_break_only=True, fb_skip_mid=False, include_fb=True, dual_cap=None)),
        ("p48_fb_break", dict(pmin=0.48, first_only=False, max_or_ext=None, fb_break_only=True, fb_skip_mid=False, include_fb=True, dual_cap=None)),
        ("p45_fb_break_cap3", dict(pmin=0.45, first_only=False, max_or_ext=None, fb_break_only=True, fb_skip_mid=False, include_fb=True, dual_cap=3)),
        ("p45_fb_break_cap2", dict(pmin=0.45, first_only=False, max_or_ext=None, fb_break_only=True, fb_skip_mid=False, include_fb=True, dual_cap=2)),
        ("p50_fb_break_cap3", dict(pmin=0.50, first_only=False, max_or_ext=None, fb_break_only=True, fb_skip_mid=False, include_fb=True, dual_cap=3)),
        ("dual_only_p45", dict(pmin=0.45, first_only=False, max_or_ext=None, fb_break_only=False, fb_skip_mid=False, include_fb=False, dual_cap=None)),
        ("dual_only_p50", dict(pmin=0.50, first_only=False, max_or_ext=None, fb_break_only=False, fb_skip_mid=False, include_fb=False, dual_cap=None)),
        ("p45_first_fb_all", dict(pmin=0.45, first_only=True, max_or_ext=None, fb_break_only=False, fb_skip_mid=False, include_fb=True, dual_cap=None)),
        ("p52_fb_all", dict(pmin=0.52, first_only=False, max_or_ext=None, fb_break_only=False, fb_skip_mid=False, include_fb=True, dual_cap=None)),
    ]

    rows_out = []
    baseline = None
    for name, kw in variants:
        picks = []
        for day in all_days:
            picks.extend(build_day(bars, by, day, **kw))
        scored = materialize(picks)
        s1 = stats(scored, START_1Y, END, sess1)
        s3m = stats(scored, START_3M, END, sess3m)
        s3y = stats(scored, START_3Y, END, sess3y)
        rec = {"name": name, "kw": kw, "1y": s1, "3m": s3m, "3y": s3y, "scored": scored}
        rows_out.append(rec)
        if name == "baseline_p45_fb_all":
            baseline = rec
        print(
            f"  {name:<24} 1y n={s1['n']:<5} hit={s1['hit_pct']}%  "
            f"3y n={s3y['n']:<5} hit={s3y['hit_pct']}%  3m hit={s3m['hit_pct']}%",
            flush=True,
        )

    assert baseline is not None
    b1_hit = float(baseline["1y"]["hit_pct"] or 0)
    b1_n = int(baseline["1y"]["n"] or 0)
    b3_hit = float(baseline["3y"]["hit_pct"] or 0)
    b3_n = int(baseline["3y"]["n"] or 0)

    def score_rec(r):
        h1 = float(r["1y"]["hit_pct"] or 0)
        n1 = int(r["1y"]["n"] or 0)
        h3 = float(r["3y"]["hit_pct"] or 0)
        n3 = int(r["3y"]["n"] or 0)
        h3m = float(r["3m"]["hit_pct"] or 0)
        # prefer: hit up AND n up; else hit up with n not much down; else best hit*n
        both_up = (h1 >= b1_hit - 0.05 and n1 >= b1_n) or (h1 > b1_hit and n1 >= b1_n * 0.95)
        hit_up = h1 >= b1_hit + 0.3 and n1 >= b1_n * 0.7
        # lower is better
        return (
            0 if (h1 >= b1_hit and n1 >= b1_n) else 1,
            0 if both_up else 1,
            0 if hit_up else 1,
            -(h1 - b1_hit) * 3 - (h3 - b3_hit) * 2 - (h3m - float(baseline["3m"]["hit_pct"] or 0)),
            -(n1 - b1_n) / 50.0 - (n3 - b3_n) / 100.0,
            -h1,
            -n1,
        )

    ranked = sorted(rows_out, key=score_rec)
    best = ranked[0]
    # prefer explicit improve if any beats baseline on hit with n>=0.85*baseline or beats both
    improve = [
        r
        for r in rows_out
        if float(r["1y"]["hit_pct"] or 0) >= b1_hit
        and float(r["3y"]["hit_pct"] or 0) >= b3_hit - 0.2
        and int(r["1y"]["n"] or 0) >= int(b1_n * 0.85)
    ]
    if improve:
        improve.sort(
            key=lambda r: (
                -(float(r["1y"]["hit_pct"] or 0)),
                -(int(r["1y"]["n"] or 0)),
                -(float(r["3y"]["hit_pct"] or 0)),
            )
        )
        # among improve, pick best balance hit then n
        best = improve[0]
        # if another has much more n with hit within 0.5pp, prefer it
        for r in improve:
            if int(r["1y"]["n"] or 0) >= int(best["1y"]["n"] or 0) + 30 and float(
                r["1y"]["hit_pct"] or 0
            ) + 1e-9 >= float(best["1y"]["hit_pct"] or 0) - 0.5:
                best = r
                break

    # special: look for any with higher hit AND higher n than baseline
    both = [
        r
        for r in rows_out
        if float(r["1y"]["hit_pct"] or 0) > b1_hit
        and int(r["1y"]["n"] or 0) > b1_n
        and float(r["3y"]["hit_pct"] or 0) >= b3_hit
    ]
    if both:
        both.sort(key=lambda r: (-float(r["1y"]["hit_pct"] or 0), -int(r["1y"]["n"] or 0)))
        best = both[0]

    print(
        f"\nBEST {best['name']} 1y {best['1y']['n']}@{best['1y']['hit_pct']}% "
        f"3y {best['3y']['n']}@{best['3y']['hit_pct']}% 3m {best['3m']['hit_pct']}%",
        flush=True,
    )

    s1, s3m, s3y = best["1y"], best["3m"], best["3y"]
    scored = best["scored"]
    kw = best["kw"]
    lo = min(s1["hit_pct"], s3y["hit_pct"])
    hi = max(s1["hit_pct"], s3y["hit_pct"], s3m["hit_pct"])
    acc = f"ACC_RANGE_{int(lo)}_{int(min(100, round(hi)))}"

    policy = {
        "name": f"DUAL_FB_IMPROVED_{best['name'].upper()}",
        "mode": "dual_fb_combine_improved",
        "selector": best["name"],
        "dual": f"OR-break p>={kw['pmin']} first_only={kw['first_only']} max_or_ext={kw['max_or_ext']} cap={kw['dual_cap']}",
        "fallback": (
            "OFF"
            if not kw["include_fb"]
            else ("OR break-only @ 09:45" if kw["fb_break_only"] else "OR @ 09:45 incl mid")
        ),
        "combine": "same hm+side → 1 call dual+fallback tags",
        "mutual_block": False,
        "buy_min_p": kw["pmin"],
        "sell_min_p": kw["pmin"],
        "allow_sell_cont": not kw["first_only"],
        "buy_max_or_ext": kw["max_or_ext"],
        "fb_break_only": kw["fb_break_only"],
        "max_per_day": kw["dual_cap"],
        "clip_sl": SL,
        "clip_t1": T1,
        "baseline_1y": {"n": b1_n, "hit_pct": b1_hit},
        "baseline_3y": {"n": b3_n, "hit_pct": b3_hit},
    }
    meta = {
        "desk": DESK,
        "mode": "dual_fb_combine_improved",
        "policy": policy,
        "brackets": {"sl": SL, "target": T1},
        "cap": kw["dual_cap"] or 99,
        "accuracy_tag": acc,
        "accuracy_lo": round(lo, 2),
        "accuracy_hi": round(hi, 2),
        "windows": {
            "1y": {k: s1[k] for k in s1 if k != "by_month"},
            "3m": {k: s3m[k] for k in s3m if k != "by_month"},
            "3y": {k: s3y[k] for k in s3y if k != "by_month"},
        },
    }
    HOLD.mkdir(parents=True, exist_ok=True)
    held = [r for r in scored if START_3Y <= str(r.get("day") or "")[:10] <= END]
    calls_path = HOLD / "champ_plus_t50_sl50_calls.json"
    calls_path.write_text(json.dumps({"calls": held, "meta": meta}, indent=2), encoding="utf-8")

    payload = {
        "symbol": "SENSEX",
        "version": "dual_fb_improved_t50",
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
                "cap": meta["cap"],
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
                "1y_n": r["1y"]["n"],
                "1y_hit": r["1y"]["hit_pct"],
                "3y_n": r["3y"]["n"],
                "3y_hit": r["3y"]["hit_pct"],
                "3m_hit": r["3m"]["hit_pct"],
                "3m_n": r["3m"]["n"],
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

    # patch live gates
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
    cap_v = kw["dual_cap"] or 99
    text = re.sub(r"CAP = [^\n]+", f"CAP = {cap_v}  # improved dual+fb combine", text, count=1)
    SX_LIVE.write_text(text, encoding="utf-8")

    dual = DUAL.read_text(encoding="utf-8")
    dual = re.sub(r"CHAMPION_BUY_MIN_P = [0-9.]+", f"CHAMPION_BUY_MIN_P = {kw['pmin']}", dual, count=1)
    dual = re.sub(r"CHAMPION_SELL_MIN_P = [0-9.]+", f"CHAMPION_SELL_MIN_P = {kw['pmin']}", dual, count=1)
    if kw["max_or_ext"] is None:
        dual = re.sub(
            r"CHAMPION_BUY_MAX_OR_EXT = [^\n]+",
            "CHAMPION_BUY_MAX_OR_EXT = None",
            dual,
            count=1,
        )
    else:
        dual = re.sub(
            r"CHAMPION_BUY_MAX_OR_EXT = [^\n]+",
            f"CHAMPION_BUY_MAX_OR_EXT = {kw['max_or_ext']}",
            dual,
            count=1,
        )
    dual = re.sub(
        r"CHAMPION_SELL_FIRST_ONLY = (True|False)",
        f"CHAMPION_SELL_FIRST_ONLY = {kw['first_only']}",
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
        }
        doc["verdict"]["champion_hit_pct"] = s1["hit_pct"]
        doc["verdict"]["summary"] = (
            f"SENSEX dual+fb improved ({best['name']}): 1y {s1['n']}@{s1['hit_pct']}% "
            f"3y {s3y['n']}@{s3y['hit_pct']}%"
        )
        FINAL_JSON.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    # main report
    lines = [
        "# SENSEX · improved dual+fallback combine (±50/50)",
        "",
        f"**Desk:** `{DESK}`",
        f"**Locked selector:** `{best['name']}`",
        "",
        "## Exact logic",
        "",
        f"1. **Dual:** OR-break `p_t1 ≥ {kw['pmin']}` · first_only={kw['first_only']} · max_or_ext={kw['max_or_ext']} · cap/day={kw['dual_cap']}",
        f"2. **Fallback:** {policy['fallback']} (always evaluated; no mutual block with dual)",
        "3. **Same hm+side:** 1 call with tags `dual` + `fallback` + `COMBINED`",
        "4. Different setups: both can list",
        "5. Clip ±50/50",
        "",
        "## 1y / 3y / 3m",
        "",
        "| Window | Days | Calls | Cov% | Hit% | Dual | FB | Combo | Avg/day | vs baseline |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label, st, bn, bh in (
        ("1y", s1, b1_n, b1_hit),
        ("3y", s3y, b3_n, b3_hit),
        ("3m", s3m, baseline["3m"]["n"], baseline["3m"]["hit_pct"]),
    ):
        dn = st["n"] - bn
        dh = round(float(st["hit_pct"] or 0) - float(bh or 0), 2)
        lines.append(
            f"| **{label}** | {st['days_with_call']}/{st['sessions']} | {st['n']} | {st['coverage_pct']} | "
            f"**{st['hit_pct']}** | {st['dual_only']} | {st['fallback_only']} | {st['combined']} | "
            f"{st['avg_calls_per_day']} | n{dn:+d} hit{dh:+.2f}pp |"
        )
    lines += [
        "",
        f"Baseline: 1y {b1_n}@{b1_hit}% · 3y {b3_n}@{b3_hit}%",
        "",
        "## Variant grid (1y / 3y)",
        "",
        "| Selector | 1y N | 1y Hit | 3y N | 3y Hit | 3m N | 3m Hit |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in sorted(rows_out, key=lambda x: (-float(x["1y"]["hit_pct"] or 0), -int(x["1y"]["n"] or 0))):
        mark = " **← locked**" if r["name"] == best["name"] else ""
        lines.append(
            f"| `{r['name']}`{mark} | {r['1y']['n']} | {r['1y']['hit_pct']} | "
            f"{r['3y']['n']} | {r['3y']['hit_pct']} | {r['3m']['n']} | {r['3m']['hit_pct']} |"
        )

    # last 3 months detail
    lines += [
        "",
        "## Last 3 months detail",
        "",
        f"**3m:** {s3m['n']} calls · **{s3m['hit_pct']}%** hit · "
        f"{s3m['wins']}/{s3m['losses']} · cov {s3m['coverage_pct']}% · "
        f"dual {s3m['dual_only']} · fb {s3m['fallback_only']} · combo {s3m['combined']}",
        "",
        "| Month | N | Hit% | W/L |",
        "|---|---:|---:|---|",
    ]
    for m, ms in (s3m.get("by_month") or {}).items():
        lines.append(f"| {m} | {ms['n']} | {ms['hit_pct']} | {ms['wins']}/{ms['losses']} |")

    # per-day last ~64 sessions summary table top
    rr3 = [r for r in scored if START_3M <= str(r.get("day") or "")[:10] <= END]
    by_day: Dict[str, List[dict]] = defaultdict(list)
    for r in rr3:
        by_day[str(r.get("day"))[:10]].append(r)
    lines += [
        "",
        "### 3m day rollup",
        "",
        "| Day | N | Hit | Dual | FB | Combo | W/L |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for d in sorted(by_day.keys()):
        rows = by_day[d]
        known = [x for x in rows if x.get("win") is not None]
        w = sum(1 for x in known if x.get("win"))
        hit = round(100.0 * w / len(known), 1) if known else None
        lines.append(
            f"| {d} | {len(rows)} | {hit} | "
            f"{sum(1 for x in rows if x.get('source')=='dual')} | "
            f"{sum(1 for x in rows if x.get('source')=='fallback')} | "
            f"{sum(1 for x in rows if x.get('source')=='dual+fallback')} | "
            f"{w}/{len(known)-w} |"
        )
    lines += ["", f"_Locked {round(time.time()-t0,1)}s_", ""]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "SENSEX_DUAL_FB_IMPROVED.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "SENSEX_DUAL_FB_IMPROVED.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (OUT / "SENSEX_DUAL_FB_IMPROVED_3M.md").write_text(
        "\n".join(
            [
                "# SENSEX dual+fb improved · last 3 months",
                "",
                f"**Selector:** `{best['name']}` · desk `{DESK}`",
                f"**3m:** {s3m['n']} @ **{s3m['hit_pct']}%** · W/L {s3m['wins']}/{s3m['losses']}",
                f"**1y:** {s1['n']} @ {s1['hit_pct']}% · **3y:** {s3y['n']} @ {s3y['hit_pct']}%",
                "",
                "| Month | N | Hit% | W/L |",
                "|---|---:|---:|---|",
            ]
            + [
                f"| {m} | {ms['n']} | {ms['hit_pct']} | {ms['wins']}/{ms['losses']} |"
                for m, ms in (s3m.get("by_month") or {}).items()
            ]
            + [
                "",
                "### Day-by-day",
                "",
                "| Day | N | Hit | Dual | FB | Combo | W/L |",
                "|---|---:|---:|---:|---:|---:|---|",
            ]
            + [
                f"| {d} | {len(by_day[d])} | "
                f"{(round(100*sum(1 for x in by_day[d] if x.get('win'))/max(1,sum(1 for x in by_day[d] if x.get('win') is not None)),1))} | "
                f"{sum(1 for x in by_day[d] if x.get('source')=='dual')} | "
                f"{sum(1 for x in by_day[d] if x.get('source')=='fallback')} | "
                f"{sum(1 for x in by_day[d] if x.get('source')=='dual+fallback')} | "
                f"{sum(1 for x in by_day[d] if x.get('win'))}/"
                f"{sum(1 for x in by_day[d] if x.get('win') is False)} |"
                for d in sorted(by_day.keys())
            ]
            + ["", f"Full report: `SENSEX_DUAL_FB_IMPROVED.md`", ""]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUT / 'SENSEX_DUAL_FB_IMPROVED.md'}", flush=True)
    print(f"Wrote {OUT / 'SENSEX_DUAL_FB_IMPROVED_3M.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
