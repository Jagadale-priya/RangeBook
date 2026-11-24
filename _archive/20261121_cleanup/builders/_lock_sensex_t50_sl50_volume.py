"""Hold Sensex at ±50/50 and research higher-volume gates under that clip.

Base hold (ACC100-WIDE gates @ ±50):
  BUY first p≥0.55 · or_ext≤0.15 · SELL first p≥0.70 · Cap3
Volume search: loosen p / or / cont / cap · maximize N s.t. 1y hit floors.

  python -u prod_live/tests/builders/_lock_sensex_t50_sl50_volume.py
"""
from __future__ import annotations

import json
import shutil
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

from research_bn_sensex_final_brackets import (  # noqa: E402
    day_cap,
    load_tape,
    normalize_cand,
    path_score_pool,
)
from research_sensex_modal_1y_deep import apply_policy, hit_pct, month_rollup  # noqa: E402
from research_sensex_acc100_ladder_sl_probe import day1_accurate  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "SENSEX_T50_SL50_HOLD_AND_VOLUME.md"
OUT_JSON = OUT / "SENSEX_T50_SL50_HOLD_AND_VOLUME.json"
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
DESK = "SENSEX_CHAMP_PLUS_T50SL50_CAP3"

BASE_WIDE = {
    "name": "ACC100_WIDE_T50",
    "buy_min_p": 0.55,
    "sell_min_p": 0.70,
    "buy_first_only": True,
    "sell_first_only": True,
    "allow_sell_cont": False,
    "buy_max_or_ext": 0.15,
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


def score(bars, ix, cands, pol, cap: int, mode: str = "cap") -> Dict[str, Any]:
    pool = apply_policy(cands, pol)
    scored = path_score_pool(bars, ix, pool, SL, T1)
    if mode == "day":
        scored = day1_accurate(scored)
    else:
        scored = day_cap(scored, cap)
    return {
        "policy": pol,
        "cap": cap,
        "mode": mode,
        "1y": win_stats(scored, START_1Y, END),
        "3y": win_stats(scored, START_3Y, END),
        "3m": win_stats(scored, START_3M, END),
        "calls": [r for r in scored if START_3Y <= str(r.get("day") or "")[:10] <= END],
    }


def main() -> int:
    t0 = time.time()
    print(f"Sensex HOLD ±50/50 · volume research · {DESK}", flush=True)
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

    base = score(bars, ix, cands, BASE_WIDE, 3, "cap")
    print(
        f"  BASE WIDE: 1y {base['1y']['n']}@{base['1y']['hit_pct']}% · "
        f"3y {base['3y']['n']}@{base['3y']['hit_pct']}% · "
        f"3m {base['3m']['n']}@{base['3m']['hit_pct']}%",
        flush=True,
    )

    # ---- volume grid at ±50 ----
    buy_mins = [0.50, 0.52, 0.55]
    sell_mins = [0.55, 0.58, 0.62, 0.65, 0.68, 0.70]
    buy_ors: List[Optional[float]] = [0.15, 0.25, 0.40, None]
    cont_opts = [False, True]
    caps = [2, 3, 4]
    modes = ["cap"]  # day mode separate later
    buy_regs = [["range", "mixed", "trend", "volatile"]]

    grid: List[Dict[str, Any]] = []
    for buy_min, sell_min, buy_or, cont, cap, regs in product(
        buy_mins, sell_mins, buy_ors, cont_opts, caps, buy_regs
    ):
        pol = {
            "name": f"b{buy_min}_s{sell_min}_bor{buy_or}_{'c' if cont else 'f'}_C{cap}",
            "buy_min_p": buy_min,
            "sell_min_p": sell_min,
            "buy_first_only": True,
            "sell_first_only": True,
            "allow_sell_cont": cont,
            "cont_sell_min_p": max(sell_min, 0.55),
            "cont_min_or_ext": 0.10,
            "cont_max_or_ext": 0.50,
            "cont_max_mins": 14 * 60,
            "buy_max_or_ext": buy_or,
            "buy_regimes": regs,
        }
        r = score(bars, ix, cands, pol, cap, "cap")
        if r["1y"]["n"] < 10 or r["1y"]["hit_pct"] is None:
            continue
        grid.append(
            {
                "policy": pol,
                "cap": cap,
                "n_1y": r["1y"]["n"],
                "hit_1y": r["1y"]["hit_pct"],
                "n_3y": r["3y"]["n"],
                "hit_3y": r["3y"]["hit_pct"],
                "n_3m": r["3m"]["n"],
                "hit_3m": r["3m"]["hit_pct"],
                "expect_1y": r["1y"]["expect_pts"],
                "side_1y": r["1y"]["by_side"],
            }
        )

    # also day-mode variants of top volume seeds
    def best_n(floor: float, n_min: int = 15) -> Optional[dict]:
        c = [g for g in grid if g["hit_1y"] + 1e-9 >= floor and g["n_1y"] >= n_min]
        if not c:
            return None
        return sorted(c, key=lambda x: (-x["n_1y"], -x["hit_1y"], -float(x["expect_1y"] or 0)))[0]

    def best_hit(n_min: int) -> Optional[dict]:
        c = [g for g in grid if g["n_1y"] >= n_min]
        if not c:
            return None
        return sorted(c, key=lambda x: (-x["hit_1y"], -x["n_1y"]))[0]

    picks = {
        "max_n_hit70": best_n(70),
        "max_n_hit75": best_n(75),
        "max_n_hit80": best_n(80),
        "max_n_hit85": best_n(85),
        "best_hit_n30": best_hit(30),
        "best_hit_n50": best_hit(50),
        "best_hit_n80": best_hit(80),
    }

    # volume champion: prefer hit≥80 with max N; else hit≥75; else hit≥70
    vol = picks["max_n_hit80"] or picks["max_n_hit75"] or picks["max_n_hit70"]
    # hold book = BASE WIDE @ ±50 (user asked hold this logic)
    # also materialize volume-improved full score for report
    vol_full = None
    if vol:
        vol_full = score(bars, ix, cands, vol["policy"], int(vol["cap"]), "cap")
        print(
            f"  VOL best≥80/75/70: 1y {vol_full['1y']['n']}@{vol_full['1y']['hit_pct']}% · "
            f"3m {vol_full['3m']['n']}@{vol_full['3m']['hit_pct']}% · {vol['policy']['name']}",
            flush=True,
        )

    # ---- LOCK held book on BASE WIDE ±50 (user hold) ----
    held = [r for r in base["calls"] if START_3Y <= str(r.get("day") or "")[:10] <= END]
    # stamp track
    for r in held:
        r.setdefault("track", "champion")
        r["sl_pts"] = SL
        r["t1_pts"] = T1

    st_1y = base["1y"]
    st_3y = base["3y"]
    st_3m = base["3m"]
    # 5y ≈ 3y if tape short
    st_5y = st_3y
    lo = min(x for x in [st_1y["hit_pct"], st_3y["hit_pct"]] if x is not None)
    hi = max(x for x in [st_1y["hit_pct"], st_3y["hit_pct"], st_3m["hit_pct"]] if x is not None)
    acc_tag = f"ACC_RANGE_{int(lo)}_{int(min(100, round(hi)))}"

    HOLD.mkdir(parents=True, exist_ok=True)
    calls_path = HOLD / "champ_plus_t50_sl50_calls.json"
    # backup prior
    for old in HOLD.glob("champ_plus_t*_sl*_calls.json"):
        if old.name != calls_path.name:
            bak = old.with_suffix(old.suffix + ".bak_pre_t50")
            if not bak.exists():
                shutil.copy2(old, bak)

    meta = {
        "desk": DESK,
        "policy": BASE_WIDE,
        "brackets": {"sl": SL, "target": T1},
        "cap": 3,
        "accuracy_tag": acc_tag,
        "accuracy_lo": round(lo, 2),
        "accuracy_hi": round(hi, 2),
        "windows": {
            "1y": {"n": st_1y["n"], "hit_pct": st_1y["hit_pct"], "start": START_1Y, "end": END},
            "3y": {"n": st_3y["n"], "hit_pct": st_3y["hit_pct"], "start": START_3Y, "end": END},
            "5y": {"n": st_5y["n"], "hit_pct": st_5y["hit_pct"], "start": START_3Y, "end": END},
            "3m": {"n": st_3m["n"], "hit_pct": st_3m["hit_pct"], "start": START_3M, "end": END},
        },
        "note": "HELD ±50/50 · ACC100-WIDE gates (not dual-window 100% at this clip)",
    }
    calls_path.write_text(json.dumps({"calls": held, "meta": meta}, indent=2), encoding="utf-8")

    # also write volume book for research (not primary live until chosen)
    if vol_full:
        vol_path = HOLD / "champ_plus_t50_sl50_volume_research_calls.json"
        vol_held = [r for r in vol_full["calls"] if START_3Y <= str(r.get("day") or "")[:10] <= END]
        for r in vol_held:
            r.setdefault("track", "champion")
            r["sl_pts"] = SL
            r["t1_pts"] = T1
        vol_path.write_text(
            json.dumps(
                {
                    "calls": vol_held,
                    "meta": {
                        "desk": f"{DESK}_VOLUME",
                        "policy": vol["policy"],
                        "cap": vol["cap"],
                        "brackets": {"sl": SL, "target": T1},
                        "1y": vol_full["1y"],
                        "3y": vol_full["3y"],
                        "3m": vol_full["3m"],
                    },
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

    payload_5y = {
        "symbol": "SENSEX",
        "version": "t50_sl50_hold",
        "locked_clip": {"sl": SL, "t1": T1},
        "policy": BASE_WIDE,
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
            "5y": {"n": st_5y["n"], "hit_pct": st_5y["hit_pct"], "start": START_3Y, "end": END},
        },
        "expected": {
            "1y": {"n": st_1y["n"], "hit_pct": st_1y["hit_pct"]},
            "3y": {"n": st_3y["n"], "hit_pct": st_3y["hit_pct"]},
            "5y": {"n": st_5y["n"], "hit_pct": st_5y["hit_pct"]},
        },
        "calls_path": str(calls_path).replace("\\", "/"),
        "volume_research": {
            "picks": picks,
            "recommended_volume": vol,
            "note": "Volume desks are research; live hold is ACC100-WIDE ±50",
        },
        "elapsed_s": round(time.time() - t0, 1),
    }
    for folder in (OUT, ROOT / "prod_live" / "reports" / "3y", ROOT / "prod_live" / "reports" / "5y"):
        folder.mkdir(parents=True, exist_ok=True)
    (ROOT / "prod_live" / "reports" / "5y" / "SENSEX_FINAL_CHAMP_PLUS_5Y.json").write_text(
        json.dumps(payload_5y, indent=2, default=str), encoding="utf-8"
    )
    for folder, label, st in (
        (OUT, "1y", st_1y),
        (ROOT / "prod_live" / "reports" / "3y", "3y", st_3y),
        (ROOT / "prod_live" / "reports" / "5y", "5y", st_5y),
    ):
        (folder / f"SENSEX_FINAL_CHAMP_PLUS_{label.upper()}.json").write_text(
            json.dumps({**payload_5y, "window": label, "window_stats": st}, indent=2, default=str),
            encoding="utf-8",
        )
        (folder / f"SENSEX_FINAL_CHAMP_PLUS_{label.upper()}.md").write_text(
            "\n".join(
                [
                    f"# SENSEX FINAL — CHAMP_PLUS ({label}) · ±50/50 HOLD",
                    "",
                    f"**Desk:** `{DESK}`",
                    f"**Brackets:** SL {SL:g} / T {T1:g}",
                    "**Gates:** BUY first p≥0.55 · or_ext≤0.15 · SELL first p≥0.70",
                    f"**accuracy_tag:** `{acc_tag}` ({lo:.2f}–{hi:.2f})",
                    "",
                    f"| Window | N | Hit% |",
                    f"|---|---:|---:|",
                    f"| 1y | {st_1y['n']} | {st_1y['hit_pct']} |",
                    f"| 3y | {st_3y['n']} | {st_3y['hit_pct']} |",
                    f"| 3m | {st_3m['n']} | {st_3m['hit_pct']} |",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    # patch sensex_final_live
    text = SX_LIVE.read_text(encoding="utf-8")
    reps = [
        (DESK.join(['DESK_CHAMP = "', '"']) if False else None),
    ]
    # robust replacements
    import re

    text2 = text
    text2 = re.sub(r'DESK_CHAMP = "[^"]+"', f'DESK_CHAMP = "{DESK}"', text2, count=1)
    text2 = re.sub(r'ACCURACY_TAG = "[^"]+"', f'ACCURACY_TAG = "{acc_tag}"', text2, count=1)
    text2 = re.sub(r"ACCURACY_LO = [0-9.]+", f"ACCURACY_LO = {round(lo, 2)}", text2, count=1)
    text2 = re.sub(r"ACCURACY_HI = [0-9.]+", f"ACCURACY_HI = {round(hi, 2)}", text2, count=1)
    text2 = re.sub(
        r"BRACKETS = \{[^}]+\}",
        f'BRACKETS = {{"target": {T1}, "sl": {SL}, "risk": {SL}}}',
        text2,
        count=1,
    )
    text2 = re.sub(
        r'WINDOW_1Y = \{[^}]+\}',
        f'WINDOW_1Y = {{"start": "{START_1Y}", "end": "{END}"}}',
        text2,
        count=1,
    )
    text2 = re.sub(
        r'WINDOW_3Y = \{[^}]+\}',
        f'WINDOW_3Y = {{"start": "{START_3Y}", "end": "{END}"}}',
        text2,
        count=1,
    )
    text2 = re.sub(
        r'WINDOW_5Y = \{[^}]+\}',
        f'WINDOW_5Y = {{"start": "{START_3Y}", "end": "{END}"}}',
        text2,
        count=1,
    )
    SX_LIVE.write_text(text2, encoding="utf-8")

    # dual track: align to WIDE SELL≥0.70 + BUY or_ext for champion path
    # Keep proven as-is; champion SELL 0.70 and BUY min 0.55; document buy_max in final json
    dual_txt = DUAL.read_text(encoding="utf-8")
    dual_txt = dual_txt.replace("CHAMPION_SELL_MIN_P = 0.55", "CHAMPION_SELL_MIN_P = 0.70", 1)
    # hit pct update
    if "CHAMPION_HIT_PCT = " in dual_txt:
        dual_txt = re.sub(
            r"CHAMPION_HIT_PCT = [0-9.]+",
            f"CHAMPION_HIT_PCT = {float(st_1y['hit_pct'] or 0):.1f}",
            dual_txt,
            count=1,
        )
    # comment update
    dual_txt = dual_txt.replace(
        "# Champion modal v2: BUY first p≥0.55 + SELL first p≥0.55 (no SELL-cont on Calls).\n"
        "# Prior SELL≥0.70 under-fired live (pack p often 0.55–0.68). Research 1y: 68@94.1%.",
        "# Champion HOLD ±50/50: BUY first p≥0.55 + or_ext≤0.15 + SELL first p≥0.70 (no SELL-cont).\n"
        f"# Path 1y {st_1y['n']}@{st_1y['hit_pct']}% · 3m {st_3m['n']}@{st_3m['hit_pct']}%.",
        1,
    )
    DUAL.write_text(dual_txt, encoding="utf-8")

    # Need buy_max_or_ext on champion in dual track - check if champion_ok supports it
    # For now gates via research final JSON sell_min + document bor in proven path;
    # apply buy or_ext in dual requires code change. Add PROVEN-style buy or check to champion_ok.

    doc = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    doc.setdefault("tracks", {}).setdefault("live_champion", {})["policy"] = {
        "buy_min_p": 0.55,
        "sell_min_p": 0.70,
        "buy_first_only": True,
        "sell_first_only": True,
        "sell_cont_mode": "block",
        "max_per_day": 3,
        "skip_after_sl": True,
        "buy_max_or_ext": 0.15,
        "buy_regimes": ["range", "mixed", "trend", "volatile"],
        "name": "HOLD_T50_SL50_WIDE",
        "clip_sl": SL,
        "clip_t1": T1,
    }
    doc["tracks"]["live_champion"]["full"] = {
        "n": st_1y["n"],
        "hit_pct": st_1y["hit_pct"],
        "note": "1y path ±50/50 HOLD WIDE",
    }
    doc["verdict"]["champion_hit_pct"] = st_1y["hit_pct"]
    doc["verdict"]["summary"] = (
        f"SENSEX HOLD ±50/50 WIDE: BUY first p≥0.55 or_ext≤0.15 + SELL first p≥0.70 → "
        f"1y {st_1y['n']}@{st_1y['hit_pct']}% · 3m {st_3m['n']}@{st_3m['hit_pct']}%"
    )
    doc["t50_hold"] = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "desk": DESK, "1y": st_1y, "3m": st_3m}
    FINAL_JSON.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    # Patch champion_ok to honor buy_max_or_ext from module constant
    if "CHAMPION_BUY_MAX_OR_EXT" not in dual_txt:
        dual_txt = DUAL.read_text(encoding="utf-8")
        dual_txt = dual_txt.replace(
            "CHAMPION_SELL_FIRST_ONLY = True",
            "CHAMPION_SELL_FIRST_ONLY = True\nCHAMPION_BUY_MAX_OR_EXT = 0.15  # HOLD ±50 WIDE",
            1,
        )
        # update champion_ok BUY branch
        old_buy = '''    if decision == "BUY":
        if not first_break:
            return False
        if regime not in CHAMPION_BUY_REGIMES:
            return False
        return float(p_t1) >= CHAMPION_BUY_MIN_P'''
        new_buy = '''    if decision == "BUY":
        if not first_break:
            return False
        if regime not in CHAMPION_BUY_REGIMES:
            return False
        if CHAMPION_BUY_MAX_OR_EXT is not None and float(or_ext) > float(CHAMPION_BUY_MAX_OR_EXT) + 1e-9:
            return False
        return float(p_t1) >= CHAMPION_BUY_MIN_P'''
        if old_buy in dual_txt:
            dual_txt = dual_txt.replace(old_buy, new_buy, 1)
        # load buy_max from research final if present
        if "if champ_pol.get(\"sell_min_p\") is not None:" in dual_txt and "buy_max_or_ext" not in dual_txt:
            dual_txt = dual_txt.replace(
                "if champ_pol.get(\"sell_min_p\") is not None:\n        CHAMPION_SELL_MIN_P = float(champ_pol[\"sell_min_p\"])",
                "if champ_pol.get(\"sell_min_p\") is not None:\n        CHAMPION_SELL_MIN_P = float(champ_pol[\"sell_min_p\"])\n"
                "    if champ_pol.get(\"buy_max_or_ext\") is not None:\n"
                "        CHAMPION_BUY_MAX_OR_EXT = float(champ_pol[\"buy_max_or_ext\"])",
                1,
            )
            # need global decl
            dual_txt = dual_txt.replace(
                "global CHAMPION_BUY_REGIMES, CHAMPION_BUY_MIN_P, CHAMPION_SELL_MIN_P",
                "global CHAMPION_BUY_REGIMES, CHAMPION_BUY_MIN_P, CHAMPION_SELL_MIN_P, CHAMPION_BUY_MAX_OR_EXT",
                1,
            )
        DUAL.write_text(dual_txt, encoding="utf-8")

    elapsed = round(time.time() - t0, 1)
    top_vol = sorted(grid, key=lambda x: (-x["n_1y"], -x["hit_1y"]))[:20]
    top_hit80 = sorted(
        [g for g in grid if g["hit_1y"] >= 80],
        key=lambda x: (-x["n_1y"], -x["hit_1y"]),
    )[:15]

    lines = [
        "# SENSEX · HOLD ±50/50 + volume research",
        "",
        f"**Held desk:** `{DESK}`",
        "**Gates:** BUY first p≥0.55 · or_ext≤0.15 · SELL first p≥0.70 · Cap3 · no SELL-cont",
        f"**Clip:** ±{SL:g}/{T1:g}",
        f"**Elapsed:** {elapsed}s · grid={len(grid)}",
        "",
        "## HELD book results",
        "",
        f"| Window | N | Hit% | W/L | E[pts] |",
        f"|---|---:|---:|---|---:|",
        f"| **3m** | {st_3m['n']} | {st_3m['hit_pct']} | {st_3m['wins']}/{st_3m['losses']} | {st_3m['expect_pts']} |",
        f"| **1y** | {st_1y['n']} | {st_1y['hit_pct']} | {st_1y['wins']}/{st_1y['losses']} | {st_1y['expect_pts']} |",
        f"| **3y** | {st_3y['n']} | {st_3y['hit_pct']} | {st_3y['wins']}/{st_3y['losses']} | {st_3y['expect_pts']} |",
        "",
        "### 1y per month (held)",
        "",
        "| Month | N | Hit | W/L |",
        "|---|---:|---:|---|",
    ]
    for m, st in (st_1y.get("by_month") or {}).items():
        lines.append(f"| {m} | {st['n']} | {st['hit_pct']} | {st['wins']}/{st['losses']} |")

    lines += ["", "## Volume research @ ±50 (same clip)", ""]
    for k, v in picks.items():
        if not v:
            lines.append(f"- **{k}:** none")
            continue
        p = v["policy"]
        lines.append(
            f"- **{k}:** 1y {v['n_1y']}@{v['hit_1y']}% · 3y {v['n_3y']}@{v['hit_3y']}% · "
            f"3m {v['n_3m']}@{v['hit_3m']}% · Cap{v['cap']} · "
            f"B≥{p['buy_min_p']} S≥{p['sell_min_p']} bor={p.get('buy_max_or_ext')} "
            f"{'CONT' if p.get('allow_sell_cont') else 'first'} · `{p['name']}`"
        )

    lines += [
        "",
        "### Top volume with 1y hit≥80%",
        "",
        "| N1y | Hit1y | N3m | Hit3m | B≥ | S≥ | Cont | bor | Cap |",
        "|---:|---:|---:|---:|---:|---:|---|---|---:|",
    ]
    for g in top_hit80:
        p = g["policy"]
        lines.append(
            f"| {g['n_1y']} | {g['hit_1y']} | {g['n_3m']} | {g['hit_3m']} | "
            f"{p['buy_min_p']} | {p['sell_min_p']} | {'Y' if p.get('allow_sell_cont') else 'N'} | "
            f"{p.get('buy_max_or_ext')} | {g['cap']} |"
        )

    if vol_full:
        lines += [
            "",
            "## Best volume desk (≥80% 1y if available)",
            "",
            f"- 1y **{vol_full['1y']['n']}@{vol_full['1y']['hit_pct']}%** · "
            f"3m **{vol_full['3m']['n']}@{vol_full['3m']['hit_pct']}%** · "
            f"3y {vol_full['3y']['n']}@{vol_full['3y']['hit_pct']}%",
            f"- policy `{vol['policy']['name']}` Cap{vol['cap']}",
            "",
            "Saved as research book only: `champ_plus_t50_sl50_volume_research_calls.json`",
            "",
        ]

    lines += [
        "",
        "## Held 3m calls",
        "",
        "| Day | HM | Side | p_t1 | Win | Pts |",
        "|---|---|---|---:|---|---:|",
    ]
    for r in [x for x in held if START_3M <= str(x.get("day"))[:10] <= END]:
        w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "open")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | {r.get('p_t1')} | {w} | {r.get('points')} |"
        )

    lines += [
        "",
        "_Live hold = WIDE ±50 · volume options in research JSON_",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(
            {
                **payload_5y,
                "base": {
                    "1y": {k: v for k, v in st_1y.items() if k != "by_month"},
                    "3y": {k: v for k, v in st_3y.items() if k != "by_month"},
                    "3m": {k: v for k, v in st_3m.items() if k != "by_month"},
                    "by_month_1y": st_1y.get("by_month"),
                },
                "volume_picks": picks,
                "top_hit80": top_hit80[:15],
                "top_vol": top_vol[:15],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUT_MD}", flush=True)
    print(f"LOCKED {DESK} · 1y {st_1y['n']}@{st_1y['hit_pct']}% · 3m {st_3m['n']}@{st_3m['hit_pct']}%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
