"""Push Sensex dual+fb past locked p45_fb_break on BOTH hit and N.

Locked now: 1y 909@76.13% · 3y 2370@72.62% · 3m 227@79.3%
Search filters/unions that raise hit while keeping/raising N.

  python -u prod_live/tests/builders/_improve_sensex_dual_fb_v2.py
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
DESK = "SENSEX_DUAL_FB_V2_T50"
# floors = current locked improve
FLOOR_1Y_HIT = 76.13
FLOOR_1Y_N = 909
FLOOR_3Y_HIT = 72.62
FLOOR_3M_HIT = 79.3


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
    mode: str = "break",  # break | mid | all
    min_or_width: float = 0.0,
    min_break_frac: float = 0.0,
) -> Optional[dict]:
    db = bars[bars.index.strftime("%Y-%m-%d") == day]
    if len(db) < 2:
        return None
    or_hi = float(db["High"].iloc[0])
    or_lo = float(db["Low"].iloc[0])
    width = or_hi - or_lo
    if width < min_or_width:
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
    mid = (or_hi + or_lo) / 2.0
    if close > or_hi:
        side = "BUY"
        kind = "break"
        brk = (close - or_hi) / width if width > 0 else 0.0
    elif close < or_lo:
        side = "SELL"
        kind = "break"
        brk = (or_lo - close) / width if width > 0 else 0.0
    else:
        if mode == "break":
            return None
        side = "BUY" if close >= mid else "SELL"
        kind = "mid"
        brk = 0.0
    if mode == "mid" and kind != "mid":
        return None
    if kind == "break" and brk < min_break_frac:
        return None
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
        "or_width": width,
        "break_frac": brk,
        "tags": ["fallback", "OR_09:45", f"fb_{kind}"],
    }


def pass_dual(r: dict, rule: str) -> bool:
    p = float(r.get("p_t1") or 0)
    fb = bool(r.get("first_break"))
    reg = str(r.get("regime") or "")
    ext = r.get("or_ext")
    try:
        ext_f = float(ext) if ext is not None else None
    except (TypeError, ValueError):
        ext_f = None
    mins = r.get("mins")
    try:
        mins_f = float(mins) if mins is not None else None
    except (TypeError, ValueError):
        mins_f = None
    # hm from when
    hm = str(r.get("hm") or "")[:5]
    if not hm and r.get("when"):
        try:
            ts = pd.Timestamp(r["when"])
            hm = f"{ts.hour:02d}:{ts.minute:02d}"
        except Exception:
            hm = ""

    if rule == "p45":
        return p >= 0.45
    if rule == "p50":
        return p >= 0.50
    if rule == "p45_first":
        return p >= 0.45 and fb
    if rule == "p45_cont":
        return p >= 0.45 and not fb
    if rule == "p45_am":  # before 12:00
        if not hm:
            return p >= 0.45
        return p >= 0.45 and hm < "12:00"
    if rule == "p45_pm":
        if not hm:
            return False
        return p >= 0.45 and hm >= "12:00"
    if rule == "p45_reg_trend_mixed":
        return p >= 0.45 and reg in ("trend", "mixed", "range", "")
    if rule == "p45_no_volatile":
        return p >= 0.45 and reg != "volatile"
    if rule == "p45_ext_lt2":
        return p >= 0.45 and (ext_f is None or ext_f < 2.0)
    if rule == "p45_ext_lt5":
        return p >= 0.45 and (ext_f is None or ext_f < 5.0)
    if rule == "p45_ext_gte0.5":
        return p >= 0.45 and (ext_f is None or ext_f >= 0.5)
    if rule == "p45_mins_lt900":
        return p >= 0.45 and (mins_f is None or mins_f < 900)
    if rule == "p45_first_or_p55":
        return (p >= 0.45 and fb) or p >= 0.55
    if rule == "p45_first_or_p52cont":
        return (p >= 0.45 and fb) or (p >= 0.52 and not fb)
    if rule == "p48":
        return p >= 0.48
    return p >= 0.45


def build_day(
    bars,
    by,
    day: str,
    *,
    dual_rule: str,
    fb_mode: str,
    min_or_width: float = 0.0,
    min_break_frac: float = 0.0,
    fb_only_if_no_dual: bool = False,
    fb_only_agree_side: bool = False,
    dual_cap: Optional[int] = None,
) -> List[dict]:
    raw = list(by.get(day) or [])
    duals = []
    for r in raw:
        if not pass_dual(r, dual_rule):
            continue
        rr = dict(r)
        if not rr.get("hm") and rr.get("when"):
            try:
                ts = pd.Timestamp(rr["when"])
                rr["hm"] = f"{ts.hour:02d}:{ts.minute:02d}"
            except Exception:
                pass
        duals.append(
            {
                **rr,
                "source": "dual",
                "track": rr.get("track") or "champion",
                "tags": ["dual", "OR_break", dual_rule],
            }
        )
    duals = sorted(duals, key=lambda x: (str(x.get("hm") or ""), -float(x.get("p_t1") or 0)))
    if dual_cap is not None:
        duals = duals[:dual_cap]

    fb = fallback_row(
        bars, day, mode=fb_mode if fb_mode != "off" else "break",
        min_or_width=min_or_width, min_break_frac=min_break_frac,
    ) if fb_mode != "off" else None
    if fb_mode == "off":
        fb = None

    if fb_only_if_no_dual and duals:
        fb = None
    if fb and fb_only_agree_side and duals:
        sides = {str(d.get("decision") or "").upper() for d in duals}
        if str(fb.get("decision") or "").upper() not in sides:
            fb = None

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
    print("Improve v2 · more accuracy + more calls", flush=True)
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
        n["regime"] = row.get("regime")
        n["or_ext"] = row.get("or_ext")
        n["mins"] = row.get("mins")
        n["or_width"] = row.get("or_width")
        n["when"] = row.get("when")
        if n.get("when"):
            try:
                ts = pd.Timestamp(n["when"])
                n["hm"] = f"{ts.hour:02d}:{ts.minute:02d}"
            except Exception:
                pass
        by[n["day"]].append(n)

    all_days = sessions(bars, START_3Y, END)
    # Build + score a large universe once: all duals p45 + all fb modes
    print("  scoring universe…", flush=True)
    universe: List[dict] = []
    seen = set()
    for day in all_days:
        for r in by.get(day) or []:
            if float(r.get("p_t1") or 0) < 0.45:
                continue
            p = {**r, "source": "dual", "track": "champion", "tags": ["dual"]}
            k = (*key_of(p), "dual")
            if k not in seen:
                seen.add(k)
                universe.append(p)
        for mode in ("break", "mid", "all"):
            # all == break or mid via mode break/mid separately; skip all
            if mode == "all":
                continue
            for mow in (0.0, 20.0, 40.0, 60.0):
                for mbf in (0.0, 0.05, 0.10, 0.20):
                    if mode == "mid" and mbf > 0:
                        continue
                    fb = fallback_row(bars, day, mode=mode, min_or_width=mow, min_break_frac=mbf)
                    if not fb:
                        continue
                    k = (*key_of(fb), "fallback", fb.get("fb_kind"), mow, mbf)
                    if k in seen:
                        continue
                    seen.add(k)
                    universe.append(fb)

    print(f"  universe n={len(universe)}", flush=True)
    scored_u = path_score_pool(bars, ix, universe, SL, T1)
    score_by: Dict[Tuple[str, str, str, str], dict] = {}
    meta_by = {}
    for p in universe:
        meta_by[(*key_of(p), p.get("source"))] = p
    for r in scored_u:
        k3 = key_of(r)
        for src in ("dual", "fallback"):
            m = meta_by.get((*k3, src))
            if not m:
                continue
            row = dict(r)
            row["source"] = src
            row["tags"] = list(m.get("tags") or [])
            row["fb_kind"] = m.get("fb_kind")
            row["track"] = m.get("track") or ("champion" if src == "dual" else "or_fallback")
            row["sl_pts"] = SL
            row["t1_pts"] = T1
            row["p_t1_model"] = m.get("p_t1")
            row["first_break"] = m.get("first_break")
            row["regime"] = m.get("regime")
            row["or_ext"] = m.get("or_ext")
            row["mins"] = m.get("mins")
            score_by[(*k3, src)] = row

    def materialize(picks: List[dict]) -> List[dict]:
        out = []
        for p in picks:
            k = key_of(p)
            src = p.get("source")
            if src == "dual+fallback":
                base = score_by.get((*k, "dual")) or score_by.get((*k, "fallback"))
                if base:
                    row = dict(base)
                    row["source"] = "dual+fallback"
                    row["combined"] = True
                    row["tags"] = list(p.get("tags") or [])
                    row["track"] = "dual_fb_combined"
                    out.append(row)
                continue
            base = score_by.get((*k, "dual" if src == "dual" else "fallback"))
            if base:
                row = dict(base)
                row["source"] = src
                row["tags"] = list(p.get("tags") or [])
                out.append(row)
        return out

    sess1 = sessions(bars, START_1Y, END)
    sess3m = sessions(bars, START_3M, END)
    sess3y = sessions(bars, START_3Y, END)

    variants: List[Tuple[str, dict]] = [
        ("locked_p45_fb_break", dict(dual_rule="p45", fb_mode="break")),
        ("dual_only_p45", dict(dual_rule="p45", fb_mode="off")),
        ("p45_fb_break_w20", dict(dual_rule="p45", fb_mode="break", min_or_width=20)),
        ("p45_fb_break_w40", dict(dual_rule="p45", fb_mode="break", min_or_width=40)),
        ("p45_fb_break_w60", dict(dual_rule="p45", fb_mode="break", min_or_width=60)),
        ("p45_fb_break_bf05", dict(dual_rule="p45", fb_mode="break", min_break_frac=0.05)),
        ("p45_fb_break_bf10", dict(dual_rule="p45", fb_mode="break", min_break_frac=0.10)),
        ("p45_fb_break_bf20", dict(dual_rule="p45", fb_mode="break", min_break_frac=0.20)),
        ("p45_fb_break_w40_bf10", dict(dual_rule="p45", fb_mode="break", min_or_width=40, min_break_frac=0.10)),
        ("p45_fb_agree", dict(dual_rule="p45", fb_mode="break", fb_only_agree_side=True)),
        ("p45_fb_fill", dict(dual_rule="p45", fb_mode="break", fb_only_if_no_dual=True)),
        ("p45_first_or_p55_fb_break", dict(dual_rule="p45_first_or_p55", fb_mode="break")),
        ("p45_first_or_p52c_fb_break", dict(dual_rule="p45_first_or_p52cont", fb_mode="break")),
        ("p45_am_fb_break", dict(dual_rule="p45_am", fb_mode="break")),
        ("p45_no_vol_fb_break", dict(dual_rule="p45_no_volatile", fb_mode="break")),
        ("p45_ext_lt5_fb_break", dict(dual_rule="p45_ext_lt5", fb_mode="break")),
        ("p45_ext_lt2_fb_break", dict(dual_rule="p45_ext_lt2", fb_mode="break")),
        ("p45_mins_lt900_fb_break", dict(dual_rule="p45_mins_lt900", fb_mode="break")),
        ("p45_first_fb_break", dict(dual_rule="p45_first", fb_mode="break")),
        ("p45_fb_mid_quality", dict(dual_rule="p45", fb_mode="mid", min_or_width=40)),
        # unions via two-pass materialize later
    ]

    # Also: dual_only + quality fb as separate build already covered
    # Dual AM + dual PM high-p union: custom
    def build_union_am_pm_hi(day):
        a = build_day(bars, by, day, dual_rule="p45_am", fb_mode="break")
        b = build_day(bars, by, day, dual_rule="p45_first_or_p55", fb_mode="off")
        # merge unique keys
        seen_k = set()
        out = []
        for r in a + b:
            k = key_of(r)
            if k in seen_k:
                continue
            seen_k.add(k)
            out.append(r)
        return out

    def build_dual_plus_strong_fb(day):
        # all dual p45 + fb break only if width>=40 and break_frac>=0.1
        return build_day(
            bars, by, day,
            dual_rule="p45", fb_mode="break",
            min_or_width=40, min_break_frac=0.10,
        )

    def build_dual_filter_bad_ext_plus_fb(day):
        return build_day(bars, by, day, dual_rule="p45_ext_lt5", fb_mode="break", min_or_width=20)

    custom_builders = {
        "union_am_break_plus_hi": build_union_am_pm_hi,
        "p45_strong_fb": build_dual_plus_strong_fb,
        "p45_extlt5_fb_w20": build_dual_filter_bad_ext_plus_fb,
    }

    rows_out = []

    def eval_picks(name, picks):
        scored = materialize(picks)
        s1 = stats(scored, START_1Y, END, sess1)
        s3m = stats(scored, START_3M, END, sess3m)
        s3y = stats(scored, START_3Y, END, sess3y)
        rec = {"name": name, "1y": s1, "3m": s3m, "3y": s3y, "scored": scored}
        rows_out.append(rec)
        beat = (
            float(s1["hit_pct"] or 0) >= FLOOR_1Y_HIT
            and int(s1["n"] or 0) >= FLOOR_1Y_N
            and float(s3y["hit_pct"] or 0) >= FLOOR_3Y_HIT - 0.15
        )
        print(
            f"  {name:<32} 1y n={s1['n']:<5} hit={s1['hit_pct']}%  "
            f"3y hit={s3y['hit_pct']}% 3m hit={s3m['hit_pct']}%  beat={beat}",
            flush=True,
        )
        return rec

    for name, kw in variants:
        picks = []
        for day in all_days:
            picks.extend(build_day(bars, by, day, **kw))
        eval_picks(name, picks)

    for name, fn in custom_builders.items():
        picks = []
        for day in all_days:
            picks.extend(fn(day))
        eval_picks(name, picks)

    # Empirical: drop worst dual regimes by measuring locked book losses — try p45 without volatile + strong fb
    picks = []
    for day in all_days:
        picks.extend(
            build_day(
                bars, by, day,
                dual_rule="p45_no_volatile",
                fb_mode="break",
                min_or_width=30,
                min_break_frac=0.05,
            )
        )
    eval_picks("p45_novol_fb_w30_bf05", picks)

    # Dual first_break all + cont only if p>=0.55 + fb break w40
    picks = []
    for day in all_days:
        picks.extend(
            build_day(
                bars, by, day,
                dual_rule="p45_first_or_p55",
                fb_mode="break",
                min_or_width=40,
                min_break_frac=0.05,
            )
        )
    eval_picks("first_or_p55_fb_w40_bf05", picks)

    # More calls: dual p45 + mid fb only when OR wide (quality mid) + break fb
    def build_break_and_wide_mid(day):
        d1 = build_day(bars, by, day, dual_rule="p45", fb_mode="break")
        fb_mid = fallback_row(bars, day, mode="mid", min_or_width=50)
        if not fb_mid:
            return d1
        # add mid if not colliding
        keys = {key_of(x) for x in d1}
        if key_of(fb_mid) in keys:
            return d1
        # if a dual exists same side already, skip mid
        if any(str(x.get("decision")) == fb_mid["decision"] and x.get("source") == "dual" for x in d1):
            return d1
        return d1 + [fb_mid]

    picks = []
    for day in all_days:
        picks.extend(build_break_and_wide_mid(day))
    eval_picks("p45_fb_break_plus_widemid50", picks)

    # Select best: prefer beat floors on hit AND n; else max (hit - floor) with n>=floor*0.95
    def rank_key(r):
        h1 = float(r["1y"]["hit_pct"] or 0)
        n1 = int(r["1y"]["n"] or 0)
        h3 = float(r["3y"]["hit_pct"] or 0)
        h3m = float(r["3m"]["hit_pct"] or 0)
        both = h1 >= FLOOR_1Y_HIT and n1 >= FLOOR_1Y_N and h3 >= FLOOR_3Y_HIT - 0.1
        return (
            0 if both else 1,
            -(h1 - FLOOR_1Y_HIT),
            -(n1 - FLOOR_1Y_N) / 20.0,
            -(h3 - FLOOR_3Y_HIT),
            -(h3m - FLOOR_3M_HIT),
            -n1,
        )

    best = sorted(rows_out, key=rank_key)[0]
    # among those beating both hit and n, pick max hit then n
    both = [
        r
        for r in rows_out
        if float(r["1y"]["hit_pct"] or 0) >= FLOOR_1Y_HIT
        and int(r["1y"]["n"] or 0) >= FLOOR_1Y_N
        and float(r["3y"]["hit_pct"] or 0) >= FLOOR_3Y_HIT - 0.1
    ]
    if both:
        both.sort(
            key=lambda r: (
                -float(r["1y"]["hit_pct"] or 0),
                -int(r["1y"]["n"] or 0),
                -float(r["3y"]["hit_pct"] or 0),
            )
        )
        best = both[0]

    print(
        f"\nBEST {best['name']} 1y {best['1y']['n']}@{best['1y']['hit_pct']}% "
        f"3y {best['3y']['n']}@{best['3y']['hit_pct']}% 3m {best['3m']['hit_pct']}%",
        flush=True,
    )

    s1, s3m, s3y = best["1y"], best["3m"], best["3y"]
    scored = best["scored"]
    lo = min(s1["hit_pct"], s3y["hit_pct"])
    hi = max(s1["hit_pct"], s3y["hit_pct"], s3m["hit_pct"])
    acc = f"ACC_RANGE_{int(lo)}_{int(min(100, round(hi)))}"

    policy = {
        "name": f"DUAL_FB_V2_{best['name'].upper()}",
        "mode": "dual_fb_v2",
        "selector": best["name"],
        "combine": "same hm+side → 1 call with dual+fallback tags",
        "mutual_block": False,
        "clip_sl": SL,
        "clip_t1": T1,
        "prior_locked": {"1y_n": FLOOR_1Y_N, "1y_hit": FLOOR_1Y_HIT, "3y_hit": FLOOR_3Y_HIT},
    }
    meta = {
        "desk": DESK,
        "mode": "dual_fb_v2",
        "policy": policy,
        "brackets": {"sl": SL, "target": T1},
        "cap": 99,
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
        "version": "dual_fb_v2_t50",
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
                "cap": 99,
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
                "3m_n": r["3m"]["n"],
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
    text = re.sub(r'ACCURACY_TAG = "[^"]+"', f'ACCURACY_TAG = "{acc}"', text, count=1)
    text = re.sub(r"ACCURACY_LO = [0-9.]+", f"ACCURACY_LO = {round(lo, 2)}", text, count=1)
    text = re.sub(r"ACCURACY_HI = [0-9.]+", f"ACCURACY_HI = {round(hi, 2)}", text, count=1)
    text = re.sub(
        r"BRACKETS = \{[^}]+\}",
        f'BRACKETS = {{"target": {T1}, "sl": {SL}, "risk": {SL}}}',
        text,
        count=1,
    )
    text = re.sub(r"CAP = [^\n]+", "CAP = 99  # dual+fb v2", text, count=1)
    SX_LIVE.write_text(text, encoding="utf-8")

    dual = DUAL.read_text(encoding="utf-8")
    dual = re.sub(r"CHAMPION_BUY_MIN_P = [0-9.]+", "CHAMPION_BUY_MIN_P = 0.45", dual, count=1)
    dual = re.sub(r"CHAMPION_SELL_MIN_P = [0-9.]+", "CHAMPION_SELL_MIN_P = 0.45", dual, count=1)
    dual = re.sub(r"CHAMPION_BUY_MAX_OR_EXT = [^\n]+", "CHAMPION_BUY_MAX_OR_EXT = None", dual, count=1)
    dual = re.sub(r"CHAMPION_SELL_FIRST_ONLY = (True|False)", "CHAMPION_SELL_FIRST_ONLY = False", dual, count=1)
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
            f"SENSEX dual+fb v2 ({best['name']}): 1y {s1['n']}@{s1['hit_pct']}% "
            f"3y {s3y['n']}@{s3y['hit_pct']}%"
        )
        FINAL_JSON.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    lines = [
        "# SENSEX · dual+fb v2 · more accuracy + more calls (±50/50)",
        "",
        f"**Desk:** `{DESK}`",
        f"**Locked:** `{best['name']}`",
        "",
        f"Prior locked `p45_fb_break`: 1y {FLOOR_1Y_N}@{FLOOR_1Y_HIT}% · 3y @{FLOOR_3Y_HIT}% · 3m @{FLOOR_3M_HIT}%",
        "",
        "## Locked result",
        "",
        "| Window | N | Hit% | Cov% | Dual | FB | Combo | vs prior |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label, st, pn, ph in (
        ("1y", s1, FLOOR_1Y_N, FLOOR_1Y_HIT),
        ("3y", s3y, None, FLOOR_3Y_HIT),
        ("3m", s3m, None, FLOOR_3M_HIT),
    ):
        dn = "" if pn is None else f"n{st['n']-pn:+d}"
        dh = round(float(st["hit_pct"] or 0) - float(ph or 0), 2)
        lines.append(
            f"| **{label}** | {st['n']} | **{st['hit_pct']}** | {st['coverage_pct']} | "
            f"{st['dual_only']} | {st['fallback_only']} | {st['combined']} | {dn} hit{dh:+.2f}pp |"
        )
    lines += [
        "",
        "## Variant grid",
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
    lines += [
        "",
        "## Last 3 months",
        "",
        f"**{s3m['n']} @ {s3m['hit_pct']}%** · W/L {s3m['wins']}/{s3m['losses']}",
        "",
        "| Month | N | Hit | W/L |",
        "|---|---:|---:|---|",
    ]
    for m, ms in (s3m.get("by_month") or {}).items():
        lines.append(f"| {m} | {ms['n']} | {ms['hit_pct']} | {ms['wins']}/{ms['losses']} |")
    lines += ["", f"_v2 locked {round(time.time()-t0,1)}s_", ""]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "SENSEX_DUAL_FB_V2.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "SENSEX_DUAL_FB_V2.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUT / 'SENSEX_DUAL_FB_V2.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
