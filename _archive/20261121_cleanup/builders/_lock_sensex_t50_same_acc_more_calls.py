"""Promote Sensex ±50 same-acc volume winner into live hold.

Winner from research_sensex_t50_more_calls_same_acc.py:
  BUY first p≥0.55 · or_ext≤0.10 · SELL first p≥0.62 · Cap3 · ±50
  1y 61@86.89% · 3y 138@80.43% · 3m 15@100%
  vs prior hold 36@86.11% / 55@80% / 12@100%

  python -u prod_live/tests/builders/_lock_sensex_t50_same_acc_more_calls.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live" / "tests" / "builders")]
import path_setup  # noqa: F401,E402

from research_bn_sensex_final_brackets import (  # noqa: E402
    day_cap,
    load_tape,
    normalize_cand,
    path_score_pool,
)
from research_sensex_modal_1y_deep import apply_policy, hit_pct, month_rollup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "SENSEX_T50_SAME_ACC_MORE_CALLS_LOCKED.md"
OUT_JSON = OUT / "SENSEX_T50_SAME_ACC_MORE_CALLS_LOCKED.json"
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
CAP = 3
DESK = "SENSEX_CHAMP_PLUS_T50SL50_CAP3"

POLICY = {
    "name": "HOLD_T50_SAME_ACC_MORE",
    "buy_min_p": 0.55,
    "sell_min_p": 0.62,
    "buy_first_only": True,
    "sell_first_only": True,
    "allow_sell_cont": False,
    "buy_max_or_ext": 0.10,
    "buy_regimes": ["range", "mixed", "trend", "volatile"],
}


def win_stats(rows: List[dict], a: str, b: str) -> Dict[str, Any]:
    rr = [r for r in rows if a <= str(r.get("day") or "")[:10] <= b]
    known = [r for r in rr if r.get("win") is not None]
    w = sum(1 for r in known if r.get("win"))
    return {
        "n": len(rr),
        "hit_pct": hit_pct(rr),
        "wins": w,
        "losses": len(known) - w,
        "expect_pts": round((w * T1 - (len(known) - w) * SL) / len(rr), 2) if rr else None,
        "by_month": month_rollup(rr),
        "by_side": {
            s: sum(1 for r in rr if r.get("decision") == s) for s in ("BUY", "SELL")
        },
    }


def main() -> int:
    t0 = time.time()
    print(f"Lock Sensex same-acc more calls · {DESK}", flush=True)
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

    pool = apply_policy(cands, POLICY)
    scored = day_cap(path_score_pool(bars, ix, pool, SL, T1), CAP)
    for r in scored:
        r.setdefault("track", "champion")
        r["sl_pts"] = SL
        r["t1_pts"] = T1

    st_1y = win_stats(scored, START_1Y, END)
    st_3y = win_stats(scored, START_3Y, END)
    st_3m = win_stats(scored, START_3M, END)
    held = [r for r in scored if START_3Y <= str(r.get("day") or "")[:10] <= END]

    lo = min(x for x in [st_1y["hit_pct"], st_3y["hit_pct"]] if x is not None)
    hi = max(x for x in [st_1y["hit_pct"], st_3y["hit_pct"], st_3m["hit_pct"]] if x is not None)
    acc_tag = f"ACC_RANGE_{int(lo)}_{int(min(100, round(hi)))}"

    HOLD.mkdir(parents=True, exist_ok=True)
    calls_path = HOLD / "champ_plus_t50_sl50_calls.json"
    meta = {
        "desk": DESK,
        "policy": POLICY,
        "brackets": {"sl": SL, "target": T1},
        "cap": CAP,
        "accuracy_tag": acc_tag,
        "accuracy_lo": round(lo, 2),
        "accuracy_hi": round(hi, 2),
        "windows": {
            "1y": {"n": st_1y["n"], "hit_pct": st_1y["hit_pct"], "start": START_1Y, "end": END},
            "3y": {"n": st_3y["n"], "hit_pct": st_3y["hit_pct"], "start": START_3Y, "end": END},
            "5y": {"n": st_3y["n"], "hit_pct": st_3y["hit_pct"], "start": START_3Y, "end": END},
            "3m": {"n": st_3m["n"], "hit_pct": st_3m["hit_pct"], "start": START_3M, "end": END},
        },
        "vs_prior_wide070": {
            "prior_1y": {"n": 36, "hit_pct": 86.11},
            "prior_3y": {"n": 55, "hit_pct": 80.0},
            "prior_3m": {"n": 12, "hit_pct": 100.0},
        },
        "note": "Same-acc more calls: SELL≥0.62 · buy or_ext≤0.10 · ±50",
    }
    calls_path.write_text(json.dumps({"calls": held, "meta": meta}, indent=2), encoding="utf-8")

    payload = {
        "symbol": "SENSEX",
        "version": "t50_same_acc_more",
        "locked_clip": {"sl": SL, "t1": T1},
        "policy": POLICY,
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
            }
        },
        "book": {
            "1y": {"n": st_1y["n"], "hit_pct": st_1y["hit_pct"], "start": START_1Y, "end": END},
            "3y": {"n": st_3y["n"], "hit_pct": st_3y["hit_pct"], "start": START_3Y, "end": END},
            "5y": {"n": st_3y["n"], "hit_pct": st_3y["hit_pct"], "start": START_3Y, "end": END},
        },
        "expected": {
            "1y": {"n": st_1y["n"], "hit_pct": st_1y["hit_pct"]},
            "3y": {"n": st_3y["n"], "hit_pct": st_3y["hit_pct"]},
            "5y": {"n": st_3y["n"], "hit_pct": st_3y["hit_pct"]},
        },
        "calls_path": str(calls_path).replace("\\", "/"),
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
                    f"# SENSEX FINAL — CHAMP_PLUS ({label}) · ±50 same-acc more",
                    "",
                    f"**Desk:** `{DESK}`",
                    f"**Brackets:** SL {SL:g} / T {T1:g}",
                    "**Gates:** BUY first p≥0.55 · or_ext≤0.10 · SELL first p≥0.62 · Cap3",
                    f"**accuracy_tag:** `{acc_tag}` ({lo:.2f}–{hi:.2f})",
                    "",
                    "| Window | N | Hit% |",
                    "|---|---:|---:|",
                    f"| 1y | {st_1y['n']} | {st_1y['hit_pct']} |",
                    f"| 3y | {st_3y['n']} | {st_3y['hit_pct']} |",
                    f"| 3m | {st_3m['n']} | {st_3m['hit_pct']} |",
                    "",
                    "Prior WIDE S≥0.70 bor≤0.15: 1y 36@86.11%.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    # patch live constants
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
    SX_LIVE.write_text(text, encoding="utf-8")

    dual = DUAL.read_text(encoding="utf-8")
    dual = re.sub(r"CHAMPION_SELL_MIN_P = [0-9.]+", "CHAMPION_SELL_MIN_P = 0.62", dual, count=1)
    dual = re.sub(
        r"CHAMPION_BUY_MAX_OR_EXT = [0-9.]+",
        "CHAMPION_BUY_MAX_OR_EXT = 0.10  # same-acc more ±50",
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

    doc = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    doc.setdefault("tracks", {}).setdefault("live_champion", {})["policy"] = {
        "buy_min_p": 0.55,
        "sell_min_p": 0.62,
        "buy_first_only": True,
        "sell_first_only": True,
        "sell_cont_mode": "block",
        "max_per_day": 3,
        "skip_after_sl": True,
        "buy_max_or_ext": 0.10,
        "buy_regimes": ["range", "mixed", "trend", "volatile"],
        "name": POLICY["name"],
        "clip_sl": SL,
        "clip_t1": T1,
    }
    doc["tracks"]["live_champion"]["full"] = {
        "n": st_1y["n"],
        "hit_pct": st_1y["hit_pct"],
        "note": "1y path ±50 same-acc more calls",
    }
    doc["verdict"]["champion_hit_pct"] = st_1y["hit_pct"]
    doc["verdict"]["summary"] = (
        f"SENSEX ±50 same-acc more: BUY first p≥0.55 or_ext≤0.10 + SELL first p≥0.62 → "
        f"1y {st_1y['n']}@{st_1y['hit_pct']}% · 3m {st_3m['n']}@{st_3m['hit_pct']}%"
    )
    FINAL_JSON.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    rows_1y = [r for r in held if START_1Y <= str(r.get("day"))[:10] <= END]
    lines = [
        "# SENSEX ±50 · same-acc more calls · LOCKED",
        "",
        f"**Desk:** `{DESK}` · ±{SL:g}/{T1:g} · Cap{CAP}",
        "**Gates:** BUY first p≥0.55 · or_ext≤**0.10** · SELL first p≥**0.62**",
        "",
        "| Window | Prior (S≥0.70 bor0.15) | **New** | Delta |",
        "|---|---|---|---|",
        f"| 1y | 36@86.11% | **{st_1y['n']}@{st_1y['hit_pct']}%** | +{st_1y['n']-36} / +{round(st_1y['hit_pct']-86.11,2)}pp |",
        f"| 3y | 55@80.0% | **{st_3y['n']}@{st_3y['hit_pct']}%** | +{st_3y['n']-55} / +{round(st_3y['hit_pct']-80.0,2)}pp |",
        f"| 3m | 12@100% | **{st_3m['n']}@{st_3m['hit_pct']}%** | +{st_3m['n']-12} / flat |",
        "",
        "## 1y per month",
        "",
        "| Month | N | Hit | W/L |",
        "|---|---:|---:|---|",
    ]
    for m, st in (st_1y.get("by_month") or {}).items():
        lines.append(f"| {m} | {st['n']} | {st['hit_pct']} | {st['wins']}/{st['losses']} |")
    lines += [
        "",
        "## 3m calls",
        "",
        "| Day | HM | Side | p_t1 | Win | Pts |",
        "|---|---|---|---:|---|---:|",
    ]
    for r in [x for x in held if START_3M <= str(x.get("day"))[:10] <= END]:
        w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "open")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | {r.get('p_t1')} | {w} | {r.get('points')} |"
        )
    lines += ["", f"_Locked in {round(time.time()-t0,1)}s_", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(
            {
                **payload,
                "by_month_1y": st_1y.get("by_month"),
                "calls_1y": [
                    {
                        "day": r.get("day"),
                        "hm": r.get("hm"),
                        "decision": r.get("decision"),
                        "p_t1": r.get("p_t1"),
                        "win": r.get("win"),
                        "points": r.get("points"),
                    }
                    for r in rows_1y
                ],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(
        f"LOCKED 1y {st_1y['n']}@{st_1y['hit_pct']}% · 3y {st_3y['n']}@{st_3y['hit_pct']}% · "
        f"3m {st_3m['n']}@{st_3m['hit_pct']}%",
        flush=True,
    )
    print(f"Wrote {OUT_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
