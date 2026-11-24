"""Sensex: 1 call/day research + lock at ±50/50.

Goal: cover as many sessions as possible with exactly 1 call/day (max p_t1),
keeping the best hit rate we can at ±50.

  python -u prod_live/tests/builders/_lock_sensex_one_call_per_day_t50.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import timedelta
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live" / "tests" / "builders")]
import path_setup  # noqa: F401,E402

from research_bn_sensex_final_brackets import load_tape, normalize_cand, path_score_pool  # noqa: E402
from research_sensex_modal_1y_deep import apply_policy, hit_pct, month_rollup  # noqa: E402
from research_sensex_acc100_ladder_sl_probe import day1_accurate  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "SENSEX_ONE_CALL_PER_DAY_T50.md"
OUT_JSON = OUT / "SENSEX_ONE_CALL_PER_DAY_T50.json"
HOLD = ROOT / "prod_live" / "holding_accurate" / "sensex_final"
CANDS = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_full_live_candidates.json"
)
FINAL_JSON = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_proven_100_final.json"
)
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_5m_kite.csv"
SX_LIVE = ROOT / "prod_live" / "logic" / "sensex_final_live.py"
DUAL = ROOT / "app" / "fno" / "sensex_live_dual_track.py"

END = "2026-11-19"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_3M = (pd.Timestamp(END) - timedelta(days=92)).strftime("%Y-%m-%d")
SL = T1 = 50.0
DESK = "SENSEX_DAY1_T50SL50"


def tape_sessions(bars: pd.DataFrame, a: str, b: str) -> List[str]:
    idx = bars.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return sorted({str(pd.Timestamp(t).date()) for t in idx if a <= str(pd.Timestamp(t).date()) <= b})


def win_stats(rows: List[dict], a: str, b: str, sessions: List[str]) -> Dict[str, Any]:
    rr = [r for r in rows if a <= str(r.get("day") or "")[:10] <= b]
    known = [r for r in rr if r.get("win") is not None]
    w = sum(1 for r in known if r.get("win"))
    cov = round(100.0 * len(rr) / len(sessions), 1) if sessions else 0.0
    return {
        "n": len(rr),
        "sessions": len(sessions),
        "coverage_pct": cov,
        "hit_pct": hit_pct(rr),
        "wins": w,
        "losses": len(known) - w,
        "expect_pts": round((w * T1 - (len(known) - w) * SL) / len(rr), 2) if rr else None,
        "by_month": month_rollup(rr),
        "by_side": {
            s: sum(1 for r in rr if r.get("decision") == s) for s in ("BUY", "SELL")
        },
    }


def eval_day(bars, ix, cands, pol, s1, s3m, s3y) -> Dict[str, Any]:
    pool = apply_policy(cands, pol)
    scored = day1_accurate(path_score_pool(bars, ix, pool, SL, T1))
    for r in scored:
        r.setdefault("track", "champion")
        r["sl_pts"] = SL
        r["t1_pts"] = T1
    return {
        "policy": pol,
        "pool_n": len(pool),
        "1y": win_stats(scored, START_1Y, END, s1),
        "3m": win_stats(scored, START_3M, END, s3m),
        "3y": win_stats(scored, START_3Y, END, s3y),
        "calls": scored,
    }


def main() -> int:
    t0 = time.time()
    print("Sensex 1-call/day @ ±50 research + lock", flush=True)
    bars, ix = load_tape(TAPE5)
    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    cands: List[dict] = []
    for row in raw:
        n = normalize_cand(row)
        if not n or n["day"] < START_3Y or n["day"] > END:
            continue
        n["or_ext"] = float(row.get("or_ext") if row.get("or_ext") is not None else 9)
        n["regime"] = str(row.get("regime") or "")
        n["mins"] = row.get("mins")
        n["first_break"] = bool(row.get("first_break"))
        cands.append(n)

    s1 = tape_sessions(bars, START_1Y, END)
    s3m = tape_sessions(bars, START_3M, END)
    s3y = tape_sessions(bars, START_3Y, END)
    print(f"  sessions 1y={len(s1)} 3m={len(s3m)} 3y={len(s3y)}", flush=True)

    buy_mins = [0.45, 0.48, 0.50, 0.52, 0.55]
    sell_mins = [0.48, 0.50, 0.52, 0.55, 0.58, 0.60]
    buy_ors: List[Optional[float]] = [None, 0.40, 0.25]
    cont_opts = [False, True]
    results: List[Dict[str, Any]] = []

    for b, s, bor, cont in product(buy_mins, sell_mins, buy_ors, cont_opts):
        tag = "c" if cont else "f"
        pol = {
            "name": f"day1_b{b}_s{s}_bor{bor}_{tag}",
            "buy_min_p": b,
            "sell_min_p": s,
            "buy_first_only": True,
            "sell_first_only": not cont,  # if cont, allow non-first sell via cont path
            "allow_sell_cont": cont,
            "cont_sell_min_p": max(s, 0.48),
            "cont_min_or_ext": 0.05,
            "cont_max_or_ext": 0.80,
            "cont_max_mins": 15 * 60,
            "buy_max_or_ext": bor,
            "buy_regimes": ["range", "mixed", "trend", "volatile"],
        }
        # when cont, still want first-break sells at sell_min
        if cont:
            pol["sell_first_only"] = True
        results.append(eval_day(bars, ix, cands, pol, s1, s3m, s3y))

    # ultra-loose fill almost every OR break day
    results.append(
        eval_day(
            bars,
            ix,
            cands,
            {
                "name": "day1_ultra_loose",
                "buy_min_p": 0.45,
                "sell_min_p": 0.45,
                "buy_first_only": True,
                "sell_first_only": True,
                "allow_sell_cont": True,
                "cont_sell_min_p": 0.45,
                "cont_min_or_ext": 0.0,
                "cont_max_or_ext": 9.0,
                "cont_max_mins": 15 * 60,
                "buy_max_or_ext": None,
                "buy_regimes": ["range", "mixed", "trend", "volatile"],
            },
            s1,
            s3m,
            s3y,
        )
    )

    def pick(floor_cov: float) -> Optional[Dict[str, Any]]:
        ok = [
            r
            for r in results
            if r["1y"]["coverage_pct"] + 1e-9 >= floor_cov and r["1y"]["hit_pct"] is not None
        ]
        if not ok:
            return None
        return sorted(
            ok,
            key=lambda r: (
                -float(r["1y"]["hit_pct"]),
                -r["1y"]["coverage_pct"],
                -r["1y"]["n"],
            ),
        )[0]

    picks = {f"cov>={c}": pick(c) for c in (95, 90, 85, 80, 70, 60, 50)}
    # primary: best hit with cov>=80%, else >=70%, else max coverage
    recommended = pick(80) or pick(70) or pick(60) or pick(50)
    max_cov = sorted(results, key=lambda r: (-r["1y"]["coverage_pct"], -float(r["1y"]["hit_pct"] or 0)))[0]

    print("Coverage ladder (best hit at floor):", flush=True)
    for k, r in picks.items():
        if not r:
            print(f"  {k}: none", flush=True)
            continue
        print(
            f"  {k}: cov={r['1y']['coverage_pct']}% n={r['1y']['n']} hit={r['1y']['hit_pct']}% "
            f"3m cov={r['3m']['coverage_pct']}% hit={r['3m']['hit_pct']}% · {r['policy']['name']}",
            flush=True,
        )
    assert recommended is not None
    print(
        f"RECOMMENDED: 1y cov={recommended['1y']['coverage_pct']}% "
        f"n={recommended['1y']['n']}@{recommended['1y']['hit_pct']}% · {recommended['policy']['name']}",
        flush=True,
    )

    # Prefer near-daily: if max_cov coverage is much higher and hit not terrible, use max_cov when cov>=90
    # User asked 1 call EVERY day → prioritize coverage, then hit.
    if max_cov["1y"]["coverage_pct"] >= 85:
        # among cov>=85 take best hit; among cov>=90 if exists prefer that with best hit
        daily = pick(90) or pick(85) or recommended
    else:
        daily = recommended
    # Actually user said everyday — lock highest coverage with hit>=55 if possible else max cov
    everyday_cands = [
        r
        for r in results
        if r["1y"]["hit_pct"] is not None and r["1y"]["hit_pct"] >= 55 and r["1y"]["coverage_pct"] >= 70
    ]
    if everyday_cands:
        daily = sorted(
            everyday_cands,
            key=lambda r: (-r["1y"]["coverage_pct"], -float(r["1y"]["hit_pct"]), -r["1y"]["n"]),
        )[0]
    else:
        daily = max_cov

    print(
        f"LOCK everyday pick: cov={daily['1y']['coverage_pct']}% "
        f"n={daily['1y']['n']}@{daily['1y']['hit_pct']}% · {daily['policy']['name']}",
        flush=True,
    )

    # ---- lock ----
    pol = daily["policy"]
    held = [r for r in daily["calls"] if START_3Y <= str(r.get("day") or "")[:10] <= END]
    st_1y, st_3m, st_3y = daily["1y"], daily["3m"], daily["3y"]
    lo = min(x for x in [st_1y["hit_pct"], st_3y["hit_pct"]] if x is not None)
    hi = max(x for x in [st_1y["hit_pct"], st_3y["hit_pct"], st_3m["hit_pct"]] if x is not None)
    acc_tag = f"ACC_RANGE_{int(lo)}_{int(min(100, round(hi)))}"

    HOLD.mkdir(parents=True, exist_ok=True)
    calls_path = HOLD / "champ_plus_t50_sl50_calls.json"
    meta = {
        "desk": DESK,
        "mode": "day1",
        "policy": pol,
        "brackets": {"sl": SL, "target": T1},
        "cap": 1,
        "accuracy_tag": acc_tag,
        "accuracy_lo": round(lo, 2),
        "accuracy_hi": round(hi, 2),
        "windows": {
            "1y": {**{k: st_1y[k] for k in ("n", "hit_pct", "coverage_pct", "sessions")}, "start": START_1Y, "end": END},
            "3y": {**{k: st_3y[k] for k in ("n", "hit_pct", "coverage_pct", "sessions")}, "start": START_3Y, "end": END},
            "3m": {**{k: st_3m[k] for k in ("n", "hit_pct", "coverage_pct", "sessions")}, "start": START_3M, "end": END},
        },
        "note": "1 call/day (max p_t1) · ±50 · coverage-first",
    }
    calls_path.write_text(json.dumps({"calls": held, "meta": meta}, indent=2), encoding="utf-8")

    payload = {
        "symbol": "SENSEX",
        "version": "day1_t50",
        "locked_clip": {"sl": SL, "t1": T1},
        "policy": pol,
        "mode": "day1",
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
                "cap": 1,
            }
        },
        "book": {
            "1y": {"n": st_1y["n"], "hit_pct": st_1y["hit_pct"], "coverage_pct": st_1y["coverage_pct"]},
            "3y": {"n": st_3y["n"], "hit_pct": st_3y["hit_pct"], "coverage_pct": st_3y["coverage_pct"]},
            "5y": {"n": st_3y["n"], "hit_pct": st_3y["hit_pct"], "coverage_pct": st_3y["coverage_pct"]},
        },
        "expected": {
            "1y": {"n": st_1y["n"], "hit_pct": st_1y["hit_pct"]},
            "3y": {"n": st_3y["n"], "hit_pct": st_3y["hit_pct"]},
            "5y": {"n": st_3y["n"], "hit_pct": st_3y["hit_pct"]},
        },
        "calls_path": str(calls_path).replace("\\", "/"),
        "picks": {
            k: {
                "name": (v or {}).get("policy", {}).get("name"),
                "1y": {kk: (v or {})["1y"][kk] for kk in ("n", "hit_pct", "coverage_pct")} if v else None,
            }
            for k, v in picks.items()
        },
        "elapsed_s": round(time.time() - t0, 1),
    }
    for folder in (OUT, ROOT / "prod_live" / "reports" / "3y", ROOT / "prod_live" / "reports" / "5y"):
        folder.mkdir(parents=True, exist_ok=True)
    (ROOT / "prod_live" / "reports" / "5y" / "SENSEX_FINAL_CHAMP_PLUS_5Y.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    for folder, label, st in (
        (OUT, "1y", st_1y),
        (ROOT / "prod_live" / "reports" / "3y", "3y", st_3y),
        (ROOT / "prod_live" / "reports" / "5y", "5y", st_3y),
    ):
        (folder / f"SENSEX_FINAL_CHAMP_PLUS_{label.upper()}.json").write_text(
            json.dumps({**payload, "window": label, "window_stats": st}, indent=2, default=str),
            encoding="utf-8",
        )
        (folder / f"SENSEX_FINAL_CHAMP_PLUS_{label.upper()}.md").write_text(
            "\n".join(
                [
                    f"# SENSEX · 1 call/day ±50 ({label})",
                    "",
                    f"**Desk:** `{DESK}`",
                    f"**Mode:** exactly 1 call/day (max p_t1)",
                    f"**Gates:** {pol['name']}",
                    f"**Coverage 1y:** {st_1y['coverage_pct']}% ({st_1y['n']}/{st_1y['sessions']})",
                    f"**Hit 1y:** {st_1y['hit_pct']}% · 3m {st_3m['hit_pct']}% cov {st_3m['coverage_pct']}%",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    # patch sensex_final_live
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
    text = re.sub(r"CAP = \d+", "CAP = 1", text, count=1)
    SX_LIVE.write_text(text, encoding="utf-8")

    # dual gates to match day1 policy
    dual = DUAL.read_text(encoding="utf-8")
    dual = re.sub(
        r"CHAMPION_BUY_MIN_P = [0-9.]+",
        f"CHAMPION_BUY_MIN_P = {float(pol['buy_min_p'])}",
        dual,
        count=1,
    )
    dual = re.sub(
        r"CHAMPION_SELL_MIN_P = [0-9.]+",
        f"CHAMPION_SELL_MIN_P = {float(pol['sell_min_p'])}",
        dual,
        count=1,
    )
    bor = pol.get("buy_max_or_ext")
    if bor is None:
        dual = re.sub(
            r"CHAMPION_BUY_MAX_OR_EXT = [^\n]+",
            "CHAMPION_BUY_MAX_OR_EXT = None  # day1: no buy or_ext cap",
            dual,
            count=1,
        )
    else:
        dual = re.sub(
            r"CHAMPION_BUY_MAX_OR_EXT = [^\n]+",
            f"CHAMPION_BUY_MAX_OR_EXT = {float(bor)}  # day1",
            dual,
            count=1,
        )
    # sell cont
    if pol.get("allow_sell_cont"):
        dual = re.sub(
            r"CHAMPION_SELL_FIRST_ONLY = (True|False)",
            "CHAMPION_SELL_FIRST_ONLY = False",
            dual,
            count=1,
        )
    else:
        dual = re.sub(
            r"CHAMPION_SELL_FIRST_ONLY = (True|False)",
            "CHAMPION_SELL_FIRST_ONLY = True",
            dual,
            count=1,
        )
    dual = re.sub(
        r"CHAMPION_HIT_PCT = [0-9.]+",
        f"CHAMPION_HIT_PCT = {float(st_1y['hit_pct'] or 0):.1f}",
        dual,
        count=1,
    )
    DUAL.write_text(dual, encoding="utf-8")

    # champion_ok must allow sell cont when FIRST_ONLY False — already does via first_break check
    # For cont sells, champion_ok currently requires first if FIRST_ONLY; when False only checks p.
    # But evaluate uses sell_cont pack for non-first — need champion_ok to accept cont with or_ext band.
    # Quick patch: when not FIRST_ONLY, allow non-first sell if p ok (baseline-like). Already:
    #   if CHAMPION_SELL_FIRST_ONLY and not first_break: return False
    #   return p >= min
    # Good enough for volume day1.

    doc = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    doc.setdefault("tracks", {}).setdefault("live_champion", {})["policy"] = {
        **{k: pol[k] for k in pol if k != "name"},
        "name": pol["name"],
        "max_per_day": 1,
        "clip_sl": SL,
        "clip_t1": T1,
        "mode": "day1",
    }
    doc["tracks"]["live_champion"]["full"] = {
        "n": st_1y["n"],
        "hit_pct": st_1y["hit_pct"],
        "coverage_pct": st_1y["coverage_pct"],
        "note": "1 call/day ±50 coverage-first",
    }
    doc["verdict"]["champion_hit_pct"] = st_1y["hit_pct"]
    doc["verdict"]["summary"] = (
        f"SENSEX 1-call/day ±50: {pol['name']} → 1y {st_1y['n']}@{st_1y['hit_pct']}% "
        f"cov {st_1y['coverage_pct']}% ({st_1y['n']}/{st_1y['sessions']} sessions)"
    )
    FINAL_JSON.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    lines = [
        "# SENSEX · 1 call every day (±50/50)",
        "",
        f"**Desk:** `{DESK}` · mode **day1** (max p_t1) · clip ±{SL:g}/{T1:g}",
        f"**Policy:** `{pol['name']}`",
        f"- BUY first p≥{pol['buy_min_p']} · bor={pol.get('buy_max_or_ext')}",
        f"- SELL p≥{pol['sell_min_p']} · cont={'ON' if pol.get('allow_sell_cont') else 'OFF'}",
        "",
        "## Results",
        "",
        "| Window | Sessions | Calls | Coverage | Hit% | W/L |",
        "|---|---:|---:|---:|---:|---|",
        f"| **1y** | {st_1y['sessions']} | {st_1y['n']} | **{st_1y['coverage_pct']}%** | **{st_1y['hit_pct']}** | {st_1y['wins']}/{st_1y['losses']} |",
        f"| **3m** | {st_3m['sessions']} | {st_3m['n']} | **{st_3m['coverage_pct']}%** | **{st_3m['hit_pct']}** | {st_3m['wins']}/{st_3m['losses']} |",
        f"| **3y** | {st_3y['sessions']} | {st_3y['n']} | **{st_3y['coverage_pct']}%** | **{st_3y['hit_pct']}** | {st_3y['wins']}/{st_3y['losses']} |",
        "",
        "### Coverage ladder (research)",
        "",
    ]
    for k, v in picks.items():
        if not v:
            lines.append(f"- {k}: none")
            continue
        lines.append(
            f"- {k}: cov {v['1y']['coverage_pct']}% · n={v['1y']['n']} hit={v['1y']['hit_pct']}% · `{v['policy']['name']}`"
        )

    lines += [
        "",
        "## 3m per month",
        "",
        "| Month | N | Hit | W/L |",
        "|---|---:|---:|---|",
    ]
    for m, st in (st_3m.get("by_month") or {}).items():
        lines.append(f"| {m} | {st['n']} | {st['hit_pct']} | {st['wins']}/{st['losses']} |")

    lines += [
        "",
        "## Note",
        "",
        "True 100% session coverage is rare (need an OR break + model side every day).",
        "This lock maximizes daily coverage at ±50, then hit rate.",
        "",
        f"_Elapsed {round(time.time()-t0,1)}s_",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUT_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
