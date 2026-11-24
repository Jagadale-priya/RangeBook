"""Lock Sensex modal v2 from 1y deep research and refresh held books.

Policy (path-scored 1y):
  BUY first p≥0.55 · SELL first p≥0.55 · no SELL-cont · Cap3 · ±120
  1y: 68 @ 94.12%  (was live SELL≥0.70 ±100 → 38 @ 94.74%)

  python -u prod_live/tests/builders/_lock_sensex_modal_v2_1y.py
"""
from __future__ import annotations

import json
import shutil
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
from research_sensex_modal_1y_deep import apply_policy, month_rollup, hit_pct  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "SENSEX_MODAL_V2_1Y.md"
OUT_JSON = OUT / "SENSEX_MODAL_V2_1Y.json"
OUT_3Y = ROOT / "prod_live" / "reports" / "3y"
OUT_5Y = ROOT / "prod_live" / "reports" / "5y"
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

END = "2026-11-19"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_5Y = (pd.Timestamp(END) - timedelta(days=365 * 5)).strftime("%Y-%m-%d")

POLICY = {
    "name": "LIVE_champion_v2_sell055_t120",
    "buy_min_p": 0.55,
    "sell_min_p": 0.55,
    "buy_first_only": True,
    "sell_first_only": True,
    "allow_sell_cont": False,
    "buy_regimes": ["range", "mixed", "trend", "volatile"],
}
SL, T1, CAP = 120.0, 120.0, 3
DESK = f"SENSEX_CHAMP_PLUS_T{int(T1)}SL{int(SL)}_CAP{CAP}"


def win_stats(rows: List[dict], a: str, b: str) -> Dict[str, Any]:
    rr = [r for r in rows if a <= str(r.get("day") or "")[:10] <= b]
    return {
        "n": len(rr),
        "hit_pct": hit_pct(rr) or 0.0,
        "start": a,
        "end": b,
        "wins": sum(1 for r in rr if r.get("win") is True),
        "losses": sum(1 for r in rr if r.get("win") is False),
    }


def main() -> int:
    t0 = time.time()
    print(f"Lock Sensex modal v2 · {DESK}", flush=True)
    bars, ix = load_tape(TAPE5)
    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    cands: List[dict] = []
    for row in raw:
        n = normalize_cand(row)
        if not n or n["day"] < START_5Y or n["day"] > END:
            continue
        n["or_ext"] = float(row.get("or_ext") if row.get("or_ext") is not None else 9)
        n["regime"] = str(row.get("regime") or "")
        n["mins"] = row.get("mins")
        n["first_break"] = bool(row.get("first_break"))
        cands.append(n)

    pool = apply_policy(cands, POLICY)
    scored = day_cap(path_score_pool(bars, ix, pool, SL, T1), CAP)
    # proven BUY first or_ext≤0.15 p≥0.55 (unchanged) on ±120 for book union label
    proven_pol = {
        **POLICY,
        "name": "proven_buy",
        "buy_min_p": 0.55,
        "sell_min_p": 9.0,
        "buy_max_or_ext": 0.15,
    }
    # proven: BUY only via apply — sell_min 9 blocks sells; add buy_max_or
    proven_pool = []
    for r in cands:
        if r["decision"] != "BUY":
            continue
        if not r.get("first_break"):
            continue
        if float(r.get("p_t1") or 0) < 0.55:
            continue
        if float(r.get("or_ext") or 9) > 0.15 + 1e-9:
            continue
        proven_pool.append({**r, "track": "proven_100"})
    proven = day_cap(path_score_pool(bars, ix, proven_pool, 80.0, 100.0), 1)

    held_map = {(r["day"], r["decision"], r["hm"]): r for r in scored}
    for r in proven:
        held_map.setdefault((r["day"], r["decision"], r["hm"]), {**r, "track": r.get("track") or "proven_100"})
    # re-score union on ±120
    union_seed = [
        {
            "day": r["day"],
            "hm": r["hm"],
            "decision": r["decision"],
            "p_t1": r.get("p_t1"),
            "track": r.get("track") or "champion",
        }
        for r in held_map.values()
    ]
    held = day_cap(path_score_pool(bars, ix, union_seed, SL, T1), CAP)
    for r in held:
        if not r.get("track"):
            r["track"] = "champion"

    st_1y = win_stats(held, START_1Y, END)
    st_3y = win_stats(held, START_3Y, END)
    st_5y = win_stats(held, START_5Y, END)
    champ_only_1y = win_stats(scored, START_1Y, END)

    lo = min(x["hit_pct"] for x in (st_1y, st_3y, st_5y) if x["n"] >= 3)
    hi = max(x["hit_pct"] for x in (st_1y, st_3y, st_5y) if x["n"] >= 3)
    acc_tag = f"ACC_RANGE_{int(lo)}_{int(min(100, round(hi)))}"

    HOLD.mkdir(parents=True, exist_ok=True)
    calls_path = HOLD / f"champ_plus_t{int(T1)}_sl{int(SL)}_calls.json"
    # backup old
    old = HOLD / "champ_plus_t100_sl100_calls.json"
    if old.is_file():
        shutil.copy2(old, old.with_suffix(".json.bak_pre_v2"))
    calls_path.write_text(
        json.dumps(
            {
                "calls": held,
                "meta": {
                    "desk": DESK,
                    "policy": POLICY,
                    "brackets": {"sl": SL, "target": T1},
                    "cap": CAP,
                    "accuracy_tag": acc_tag,
                    "accuracy_lo": round(lo, 2),
                    "accuracy_hi": round(hi, 2),
                    "windows": {"1y": st_1y, "3y": st_3y, "5y": st_5y},
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    proven_path = HOLD / "proven100_calls.json"
    proven_path.write_text(
        json.dumps(
            {
                "calls": proven,
                "meta": {
                    "desk": "SENSEX_PROVEN100_T100SL80",
                    "brackets": {"sl": 80.0, "target": 100.0},
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = {
        "symbol": "SENSEX",
        "version": "modal_v2",
        "locked_clip": {"sl": SL, "t1": T1},
        "default_clip": {"sl": 80.0, "t1": 100.0},
        "policy": POLICY,
        "desks": {
            "proven": {
                "desk": "SENSEX_PROVEN100_T100SL80",
                "n_held": len(proven),
                "brackets": {"sl": 80.0, "target": 100.0},
                "windows": {
                    "1y": win_stats(proven, START_1Y, END),
                    "3y": win_stats(proven, START_3Y, END),
                    "5y": win_stats(proven, START_5Y, END),
                },
            },
            "champ_plus": {
                "desk": DESK,
                "accurate_tag": DESK,
                "accuracy_tag": acc_tag,
                "accuracy_lo": round(lo, 2),
                "accuracy_hi": round(hi, 2),
                "windows": {"1y": st_1y, "3y": st_3y, "5y": st_5y},
                "n_held": len(held),
                "brackets": {"sl": SL, "target": T1},
                "champ_only_windows": {"1y": champ_only_1y},
            },
        },
        "book": {"1y": st_1y, "3y": st_3y, "5y": st_5y},
        "expected": {
            "1y": {"n": st_1y["n"], "hit_pct": st_1y["hit_pct"]},
            "3y": {"n": st_3y["n"], "hit_pct": st_3y["hit_pct"]},
            "5y": {"n": st_5y["n"], "hit_pct": st_5y["hit_pct"]},
        },
        "by_month_1y": month_rollup([r for r in held if START_1Y <= str(r.get("day"))[:10] <= END]),
        "calls_path": str(calls_path).replace("\\", "/"),
        "proven_path": str(proven_path).replace("\\", "/"),
        "elapsed_s": round(time.time() - t0, 1),
        "vs_prior": {
            "prior_desk": "SENSEX_CHAMP_PLUS_T100SL100_CAP3",
            "prior_1y": {"n": 38, "hit_pct": 94.74, "note": "SELL≥0.70 ±100 path"},
            "new_1y": st_1y,
        },
    }

    for folder in (OUT, OUT_3Y, OUT_5Y):
        folder.mkdir(parents=True, exist_ok=True)
    (OUT_5Y / "SENSEX_FINAL_CHAMP_PLUS_5Y.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    for folder, label, st in (
        (OUT, "1y", st_1y),
        (OUT_3Y, "3y", st_3y),
        (OUT_5Y, "5y", st_5y),
    ):
        slim = {**payload, "window": label, "window_stats": st}
        (folder / f"SENSEX_FINAL_CHAMP_PLUS_{label.upper()}.json").write_text(
            json.dumps(slim, indent=2, default=str), encoding="utf-8"
        )
        (folder / f"SENSEX_FINAL_CHAMP_PLUS_{label.upper()}.md").write_text(
            "\n".join(
                [
                    f"# SENSEX FINAL — CHAMP_PLUS ({label}) · modal v2",
                    "",
                    f"**Desk:** `{DESK}`",
                    f"**Brackets:** SL {SL:g} / T {T1:g}",
                    f"**Policy:** BUY first p≥0.55 · SELL first p≥0.55 · Cap{CAP}",
                    f"**accuracy_tag:** `{acc_tag}` ({lo:.2f}–{hi:.2f})",
                    "",
                    "| Window | N | Hit% |",
                    "|---|---:|---:|",
                    f"| 1y | {st_1y['n']} | {st_1y['hit_pct']} |",
                    f"| 3y | {st_3y['n']} | {st_3y['hit_pct']} |",
                    f"| 5y | {st_5y['n']} | {st_5y['hit_pct']} |",
                    "",
                    f"Prior ±100 SELL≥0.70 1y was 38@94.74%.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    # update proven_100_final champion policy so live dual loads new cuts
    doc = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    doc.setdefault("tracks", {}).setdefault("live_champion", {})["policy"] = {
        "buy_min_p": 0.55,
        "sell_min_p": 0.55,
        "buy_first_only": True,
        "sell_first_only": True,
        "sell_cont_mode": "block",
        "max_per_day": 3,
        "skip_after_sl": True,
        "buy_regimes": ["range", "mixed", "trend", "volatile"],
        "name": POLICY["name"],
        "clip_sl": SL,
        "clip_t1": T1,
    }
    doc["tracks"]["live_champion"]["full"] = {
        "n": champ_only_1y["n"],
        "hit_pct": champ_only_1y["hit_pct"],
        "buy_n": sum(1 for r in scored if START_1Y <= r["day"] <= END and r["decision"] == "BUY"),
        "sell_n": sum(1 for r in scored if START_1Y <= r["day"] <= END and r["decision"] == "SELL"),
        "note": "1y path-score ±120 Cap3 after modal v2 lock",
    }
    doc["verdict"]["champion_hit_pct"] = champ_only_1y["hit_pct"]
    doc["verdict"]["summary"] = (
        f"SENSEX modal v2: Champion BUY/SELL first p≥0.55 ±120 Cap3 → "
        f"1y {st_1y['n']}@{st_1y['hit_pct']}% (path). Proven BUY unchanged."
    )
    doc["modal_v2_locked"] = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "desk": DESK,
        "1y": st_1y,
    }
    FINAL_JSON.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    # patch sensex_final_live.py constants
    text = SX_LIVE.read_text(encoding="utf-8")
    replacements = [
        (
            'DESK_CHAMP = "SENSEX_CHAMP_PLUS_T100SL100_CAP3"',
            f'DESK_CHAMP = "{DESK}"',
        ),
        (
            'ACCURACY_TAG = "ACC_RANGE_94_95"',
            f'ACCURACY_TAG = "{acc_tag}"',
        ),
        (
            "ACCURACY_LO = 94.87",
            f"ACCURACY_LO = {round(lo, 2)}",
        ),
        (
            "ACCURACY_HI = 95.0",
            f"ACCURACY_HI = {round(hi, 2)}",
        ),
        (
            'BRACKETS = {"target": 100.0, "sl": 100.0, "risk": 100.0}',
            f'BRACKETS = {{"target": {T1}, "sl": {SL}, "risk": {SL}}}',
        ),
        (
            'WINDOW_1Y = {"start": "2025-10-24", "end": "2026-11-15"}',
            f'WINDOW_1Y = {{"start": "{START_1Y}", "end": "{END}"}}',
        ),
        (
            'WINDOW_3Y = {"start": "2023-11-16", "end": "2026-11-15"}',
            f'WINDOW_3Y = {{"start": "{START_3Y}", "end": "{END}"}}',
        ),
        (
            'WINDOW_5Y = {"start": "2021-11-16", "end": "2026-11-15"}',
            f'WINDOW_5Y = {{"start": "{START_5Y}", "end": "{END}"}}',
        ),
    ]
    for a, b in replacements:
        if a not in text:
            print(f"  WARN missing snippet: {a[:60]}", flush=True)
        else:
            text = text.replace(a, b, 1)
    SX_LIVE.write_text(text, encoding="utf-8")

    # 1y report
    rows_1y = [r for r in held if START_1Y <= str(r.get("day"))[:10] <= END]
    lines = [
        "# SENSEX modal v2 · 1y locked",
        "",
        f"**Desk:** `{DESK}` · Cap{CAP} · ±{SL:g}/{T1:g}",
        "**Gates:** BUY first p≥0.55 · SELL first p≥0.55 · SELL-cont OFF",
        f"**Window:** `{START_1Y}` → `{END}`",
        "",
        "## Headline",
        "",
        f"- **1y N={st_1y['n']} · hit {st_1y['hit_pct']}%** · W/L={st_1y['wins']}/{st_1y['losses']}",
        f"- 3y {st_3y['n']}@{st_3y['hit_pct']}% · 5y {st_5y['n']}@{st_5y['hit_pct']}%",
        f"- Prior live (SELL≥0.70 ±100): 38@94.74% → **+{st_1y['n']-38} calls**, hit {st_1y['hit_pct']}%",
        "",
        "## Per month (1y)",
        "",
        "| Month | N | Hit% | W/L |",
        "|---|---:|---:|---|",
    ]
    for m, st in sorted((payload["by_month_1y"] or {}).items()):
        lines.append(
            f"| **{m}** | {st['n']} | {st['hit_pct']} | {st['wins']}/{st['losses']} |"
        )
    lines += [
        "",
        "## Calls",
        "",
        "| Day | HM | Side | Track | p_t1 | Win | Pts |",
        "|---|---|---|---|---:|---|---:|",
    ]
    for r in rows_1y:
        w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "open")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | "
            f"{r.get('track')} | {r.get('p_t1')} | {w} | {r.get('points')} |"
        )
    lines += [
        "",
        "_Locked by `tests/builders/_lock_sensex_modal_v2_1y.py`_",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print(
        f"LOCKED {DESK} · 1y {st_1y['n']}@{st_1y['hit_pct']}% · "
        f"3y {st_3y['n']}@{st_3y['hit_pct']}% · 5y {st_5y['n']}@{st_5y['hit_pct']}%",
        flush=True,
    )
    print(f"Wrote {OUT_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
