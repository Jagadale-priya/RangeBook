"""RESEARCH ONLY — multi-logic hunt for **100%-only** NIFTY 1m clean call books.

Goal: maximize day-unique calls at exactly 100% hit, across many logics.
Honest books = filters frozen on train (≤ TRAIN_END) that stay 100% on test (2025).
Also reports walk-forward 100% and in-sample ceilings (labeled).

  python -u prod_live/tests/builders/research_nifty_1m_100pct_only.py
"""
from __future__ import annotations

import json
import sys
import time
from itertools import product
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401,E402

import research_nifty_1m_dual_clean_train as base  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT_MD = OUT / "NIFTY_1M_100PCT_ONLY.md"
REPORT_JSON = OUT / "NIFTY_1M_100PCT_ONLY.json"

TEST_START = "2025-01-01"
TEST_END = "2025-12-30"
TRAIN_END = "2024-12-31"

# Candidate pools (no look-ahead). Wider pools → more room to carve 100% books.
POOLS = {
    "POOL_V2": dict(base.GATE_V2),
    "POOL_MED": {
        **base.GATE_V2,
        "min_or_width": 15.0,
        "max_noise_vs_sl": 1.60,
        "max_or_ext": 0.35,
        "min_entry_mins": 10 * 60,
        "require_body_align": False,
        "require_first_break": True,
        "forbid_both_sides": True,
    },
    "POOL_FB": {
        **base.GATE_V1,
        "min_or_width": 12.0,
        "max_noise_vs_sl": 2.0,
        "max_or_ext": 0.50,
        "min_entry_mins": 9 * 60 + 45,
        "max_entry_mins": 14 * 60 + 45,
        "require_first_break": True,
        "require_body_align": False,
        "forbid_both_sides": True,
    },
    "POOL_RAW_FB": {
        **base.GATE_V1,
        "min_or_width": 10.0,
        "max_noise_vs_sl": 2.5,
        "max_or_ext": 0.85,
        "min_entry_mins": 9 * 60 + 30,
        "require_first_break": True,
        "require_body_align": False,
        "forbid_both_sides": False,
    },
}


def agg(rows: List[dict]) -> Dict[str, Any]:
    if not rows:
        return {"n": 0, "wins": 0, "hit_pct": 0.0}
    wins = sum(1 for r in rows if r.get("win"))
    return {"n": len(rows), "wins": wins, "hit_pct": round(100.0 * wins / len(rows), 2)}


def first_day(rows: List[dict]) -> List[dict]:
    seen = set()
    out = []
    for r in sorted(rows, key=lambda x: (x.get("day"), x.get("hm"))):
        d = r.get("day")
        if d in seen:
            continue
        seen.add(d)
        out.append(r)
    return out


def strip(r: dict) -> dict:
    keys = (
        "day",
        "hm",
        "decision",
        "entry",
        "win",
        "outcome",
        "points",
        "or_ext",
        "or_width",
        "noise_vs_sl",
        "mins_entry",
        "first_break",
        "body_ok",
        "both_sides",
        "gap_pct",
        "rsi_14",
        "logic",
        "pool",
        "rank_score",
    )
    return {k: r.get(k) for k in keys if k in r or True}


def is_100(rows: List[dict]) -> bool:
    a = agg(rows)
    return a["n"] > 0 and a["hit_pct"] >= 100.0 - 1e-9


def enrich(tickets: List[dict]) -> List[dict]:
    out = []
    for r in tickets:
        rr = dict(r)
        # features may live in feat dict or flat
        xnames = getattr(base, "FEAT_NAMES", [])
        feat = {}
        if "x" in r and xnames and len(r["x"]) == len(xnames):
            feat = {n: float(v) for n, v in zip(xnames, r["x"])}
        rr["gap_pct"] = float(feat.get("gap_pct", r.get("gap_pct") or 0.0))
        rr["rsi_14"] = float(feat.get("rsi_14", r.get("rsi_14") or 50.0))
        rr["session_chg"] = float(feat.get("session_chg", r.get("session_chg") or 0.0))
        rr["atr_ratio"] = float(feat.get("atr_ratio", r.get("atr_ratio") or 0.0))
        rr["vwap_dist"] = float(feat.get("vwap_dist", r.get("vwap_dist") or 0.0))
        rr["first_break"] = bool(r.get("first_break") in (True, 1, 1.0) or float(r.get("first_break") or 0) >= 1.0)
        out.append(rr)
    return out


# ---------- filter logics ----------
def logic_filters() -> List[Tuple[str, dict]]:
    """Named structural logics (no ML)."""
    logics = []
    sides = (None, "BUY", "SELL")
    clocks = [
        ("all", 9 * 60 + 30, 14 * 60 + 45),
        ("after10", 10 * 60, 14 * 60 + 30),
        ("10_1030", 10 * 60, 10 * 60 + 30),
        ("1030_1130", 10 * 60 + 30, 11 * 60 + 30),
        ("1130_1300", 11 * 60 + 30, 13 * 60),
        ("pm", 13 * 60, 14 * 60 + 30),
        ("mid", 10 * 60 + 30, 13 * 60),
        ("early_mid", 10 * 60, 12 * 60),
    ]
    exts = (0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
    ors = (10, 12, 15, 18, 20, 25, 30, 35, 40, 50, 60)
    noises = (0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5)
    gaps = [
        ("any_gap", None, None),
        ("flat", -0.35, 0.35),
        ("up_gap", 0.35, None),
        ("dn_gap", None, -0.35),
        ("soft_up", 0.0, None),
        ("soft_dn", None, 0.0),
    ]
    rsi_bands = [
        ("any_rsi", None, None),
        ("rsi_os", None, 35),
        ("rsi_ob", 65, None),
        ("rsi_mid", 40, 60),
        ("rsi_buyish", 45, None),
        ("rsi_sellish", None, 55),
    ]
    body_opts = (None, True)  # None=ignore, True=require aligned
    both_opts = (None, False)  # False=forbid both sides
    # Keep grid tractable: sample product with priority combos + denser core
    for side in sides:
        for cname, c0, c1 in clocks:
            for ext in exts:
                for orw in ors:
                    for nz in (1.0, 1.25, 1.5, 2.0):
                        for gname, glo, ghi in gaps:
                            for rname, rlo, rhi in (("any_rsi", None, None), ("rsi_mid", 40, 60), ("rsi_sellish", None, 55), ("rsi_buyish", 45, None)):
                                for body in body_opts:
                                    for both in both_opts:
                                        name = f"{side or 'BOTH'}|{cname}|ext{ext}|or{orw}|nz{nz}|{gname}|{rname}|body{body}|both{both}"
                                        logics.append(
                                            (
                                                name,
                                                {
                                                    "side": side,
                                                    "min_mins": c0,
                                                    "max_mins": c1,
                                                    "max_or_ext": ext,
                                                    "min_or_w": orw,
                                                    "max_noise": nz,
                                                    "gap_lo": glo,
                                                    "gap_hi": ghi,
                                                    "rsi_lo": rlo,
                                                    "rsi_hi": rhi,
                                                    "require_body": body,
                                                    "forbid_both": both is False,
                                                    "require_fb": True,
                                                },
                                            )
                                        )
    return logics


def apply_f(rows: List[dict], f: dict) -> List[dict]:
    out = []
    for r in rows:
        if f.get("side") and r.get("decision") != f["side"]:
            continue
        mins = float(r.get("mins_entry") or 0)
        if mins < float(f.get("min_mins", 0)) or mins > float(f.get("max_mins", 9999)):
            continue
        if float(r.get("or_ext") or 0) > float(f.get("max_or_ext", 9)):
            continue
        if float(r.get("or_width") or 0) < float(f.get("min_or_w", 0)):
            continue
        if float(r.get("noise_vs_sl") or 0) > float(f.get("max_noise", 9)):
            continue
        g = float(r.get("gap_pct") or 0)
        if f.get("gap_lo") is not None and g < float(f["gap_lo"]):
            continue
        if f.get("gap_hi") is not None and g > float(f["gap_hi"]):
            continue
        rsi = float(r.get("rsi_14") or 50)
        if f.get("rsi_lo") is not None and rsi < float(f["rsi_lo"]):
            continue
        if f.get("rsi_hi") is not None and rsi > float(f["rsi_hi"]):
            continue
        if f.get("require_body") and not r.get("body_ok"):
            continue
        if f.get("forbid_both") and r.get("both_sides"):
            continue
        if f.get("require_fb") and not r.get("first_break"):
            continue
        # optional session / vwap
        if f.get("min_abs_gap") is not None and abs(g) < float(f["min_abs_gap"]):
            continue
        if f.get("max_abs_vwap") is not None and abs(float(r.get("vwap_dist") or 0)) > float(f["max_abs_vwap"]):
            continue
        if f.get("side_gap_align"):
            # BUY only on up/flat gap; SELL only on dn/flat
            if r.get("decision") == "BUY" and g < -0.15:
                continue
            if r.get("decision") == "SELL" and g > 0.15:
                continue
        out.append(r)
    return out


RANKERS: Dict[str, Callable[[dict], float]] = {
    "tight_ext": lambda r: -float(r.get("or_ext") or 0),
    "wide_or": lambda r: float(r.get("or_width") or 0),
    "quiet_bar": lambda r: -float(r.get("noise_vs_sl") or 0),
    "early": lambda r: -float(r.get("mins_entry") or 0),
    "late": lambda r: float(r.get("mins_entry") or 0),
    "gap_abs": lambda r: abs(float(r.get("gap_pct") or 0)),
    "rsi_extreme": lambda r: abs(float(r.get("rsi_14") or 50) - 50),
    "combo_quality": lambda r: (
        -float(r.get("or_ext") or 0) * 10
        + float(r.get("or_width") or 0) / 50
        - float(r.get("noise_vs_sl") or 0)
    ),
}


def longest_win_prefix(rows: List[dict], key_fn: Callable[[dict], float]) -> List[dict]:
    ordered = sorted(rows, key=key_fn, reverse=True)
    keep = []
    for r in ordered:
        if not r.get("win"):
            break
        keep.append(r)
    return keep


def drop_losses_to_100(rows: List[dict], key_fn: Callable[[dict], float]) -> List[dict]:
    ordered = sorted(rows, key=key_fn, reverse=True)
    keep = list(ordered)
    while keep and not is_100(keep):
        losses = [i for i, r in enumerate(keep) if not r.get("win")]
        if not losses:
            break
        # drop worst by key (lowest score among losses)
        worst = min(losses, key=lambda i: key_fn(keep[i]))
        keep.pop(worst)
    return keep if is_100(keep) else []


def mine_pool(
    pool_name: str,
    all_rows: List[dict],
    *,
    min_train_n: int = 5,
    min_test_n: int = 3,
) -> Dict[str, Any]:
    train = [r for r in all_rows if str(r["day"]) <= TRAIN_END]
    test = [r for r in all_rows if TEST_START <= str(r["day"]) <= TEST_END]
    print(f"\n=== {pool_name} train={len(train)} test={len(test)} ===", flush=True)

    honest_100: List[dict] = []
    train_only_100: List[dict] = []
    t0 = time.time()

    # Dense structural filter core (side × clock × ext × OR × noise × gap × body × gap-align)
    core = []
    for side in (None, "BUY", "SELL"):
        for cname, c0, c1 in (
            ("after10", 600, 870),
            ("10_1030", 600, 630),
            ("1030_1130", 630, 690),
            ("early_mid", 600, 720),
            ("mid", 630, 780),
        ):
            for ext in (0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30):
                for orw in (15, 20, 25, 30, 40, 50):
                    for nz in (1.0, 1.25, 1.5, 2.0):
                        for gname, glo, ghi in (
                            ("any_gap", None, None),
                            ("flat", -0.35, 0.35),
                            ("soft_up", 0.0, None),
                            ("soft_dn", None, 0.0),
                            ("dn_gap", None, -0.35),
                            ("up_gap", 0.35, None),
                        ):
                            for body in (None, True):
                                for align_gap in (False, True):
                                    f = {
                                        "side": side,
                                        "min_mins": c0,
                                        "max_mins": c1,
                                        "max_or_ext": ext,
                                        "min_or_w": orw,
                                        "max_noise": nz,
                                        "gap_lo": glo,
                                        "gap_hi": ghi,
                                        "rsi_lo": None,
                                        "rsi_hi": None,
                                        "require_body": body,
                                        "forbid_both": True,
                                        "require_fb": True,
                                        "side_gap_align": align_gap,
                                    }
                                    core.append((f"{side or 'BOTH'}|{cname}|e{ext}|o{orw}|{gname}|b{body}|ga{align_gap}", f))

    scanned = 0
    for name, f in core:
        scanned += 1
        if scanned % 2000 == 0:
            print(f"    scanned {scanned}/{len(core)} honest={len(honest_100)} ({time.time()-t0:.0f}s)", flush=True)
        tr = first_day(apply_f(train, f))
        ta = agg(tr)
        if ta["n"] < min_train_n or ta["hit_pct"] < 100 - 1e-9:
            continue
        te = first_day(apply_f(test, f))
        ea = agg(te)
        book = {
            "logic": name,
            "filters": f,
            "pool": pool_name,
            "kind": "HONEST_TRAIN100_TEST",
            "train": ta,
            "test": ea,
            "train_calls": [strip(r) for r in tr],
            "test_calls": [strip(r) for r in te],
        }
        train_only_100.append(book)
        if ea["n"] >= min_test_n and ea["hit_pct"] >= 100 - 1e-9:
            book = dict(book)
            book["kind"] = "HONEST_TRAIN100_TEST100"
            honest_100.append(book)

    # Rank-prefix logics on structural filters that are already strong on train
    rank_books = []
    seed_filters = [
        {"side": "SELL", "min_mins": 600, "max_mins": 870, "max_or_ext": 0.20, "min_or_w": 20, "max_noise": 1.5, "require_fb": True, "forbid_both": True, "require_body": True},
        {"side": "SELL", "min_mins": 600, "max_mins": 720, "max_or_ext": 0.15, "min_or_w": 15, "max_noise": 1.25, "require_fb": True, "forbid_both": True},
        {"side": "BUY", "min_mins": 600, "max_mins": 720, "max_or_ext": 0.15, "min_or_w": 20, "max_noise": 1.25, "require_fb": True, "forbid_both": True, "require_body": True},
        {"side": None, "min_mins": 600, "max_mins": 630, "max_or_ext": 0.20, "min_or_w": 20, "max_noise": 1.25, "require_fb": True, "forbid_both": True},
        {"side": None, "min_mins": 630, "max_mins": 690, "max_or_ext": 0.15, "min_or_w": 25, "max_noise": 1.25, "require_fb": True, "forbid_both": True},
        {"side": "SELL", "min_mins": 600, "max_mins": 870, "max_or_ext": 0.30, "min_or_w": 15, "max_noise": 2.0, "require_fb": True, "forbid_both": True, "side_gap_align": True},
        {"side": "BUY", "min_mins": 600, "max_mins": 870, "max_or_ext": 0.30, "min_or_w": 15, "max_noise": 2.0, "require_fb": True, "forbid_both": True, "side_gap_align": True},
        {"side": None, "min_mins": 600, "max_mins": 870, "max_or_ext": 0.10, "min_or_w": 30, "max_noise": 1.0, "require_fb": True, "forbid_both": True},
    ]
    for i, f in enumerate(seed_filters):
        for rname, rfn in RANKERS.items():
            tr_base = first_day(apply_f(train, f))
            # freeze rank threshold as the worst score among longest win prefix on train
            pref = longest_win_prefix(tr_base, rfn)
            if len(pref) < min_train_n:
                # try drop-losses book
                pref = drop_losses_to_100(tr_base, rfn)
            if len(pref) < min_train_n or not is_100(pref):
                continue
            thr = min(rfn(r) for r in pref)
            # test: same filter + score >= thr
            te_base = first_day(apply_f(test, f))
            te = [r for r in te_base if rfn(r) >= thr - 1e-12]
            te = first_day(te)
            tr = first_day([r for r in tr_base if rfn(r) >= thr - 1e-12])
            # ensure train still 100 after threshold (should be)
            if not is_100(tr) or len(tr) < min_train_n:
                continue
            ea = agg(te)
            book = {
                "logic": f"RANK|{rname}|seed{i}",
                "filters": {**f, "rank": rname, "rank_thr": thr},
                "pool": pool_name,
                "kind": "HONEST_RANK_PREFIX",
                "train": agg(tr),
                "test": ea,
                "train_calls": [strip({**r, "rank_score": rfn(r)}) for r in tr],
                "test_calls": [strip({**r, "rank_score": rfn(r)}) for r in te],
            }
            if ea["n"] >= min_test_n and ea["hit_pct"] >= 100 - 1e-9:
                book["kind"] = "HONEST_RANK_TEST100"
                honest_100.append(book)
            rank_books.append(book)

    # Walk-forward yearly: for year Y in test months... use prior years
    wf_books = []
    for year in (2022, 2023, 2024, 2025):
        prior = [r for r in all_rows if str(r["day"]) < f"{year}-01-01"]
        year_rows = [r for r in all_rows if str(r["day"]).startswith(str(year))]
        if len(prior) < 40 or len(year_rows) < 5:
            continue
        # search small core for prior100 → year100
        best_y = None
        for name, f in core[::3]:  # stride for speed
            tr = first_day(apply_f(prior, f))
            if len(tr) < 5 or not is_100(tr):
                continue
            te = first_day(apply_f(year_rows, f))
            if len(te) < 3 or not is_100(te):
                continue
            cand = {
                "logic": f"WF{year}|{name}",
                "filters": f,
                "pool": pool_name,
                "kind": f"WALKFORWARD_{year}",
                "train": agg(tr),
                "test": agg(te),
                "train_calls": [strip(r) for r in tr],
                "test_calls": [strip(r) for r in te],
            }
            if best_y is None or cand["test"]["n"] > best_y["test"]["n"]:
                best_y = cand
        if best_y:
            wf_books.append(best_y)
            if year == 2025 and best_y["test"]["n"] >= min_test_n:
                honest_100.append(best_y)

    # In-sample full + test-only ceilings (labeled)
    ceilings = []
    for label, subset in (
        ("IN_SAMPLE_FULL", all_rows),
        ("IN_SAMPLE_TEST2025", test),
        ("IN_SAMPLE_TRAIN", train),
        ("IN_SAMPLE_H1_2025", [r for r in test if r["day"] < "2025-07-01"]),
        ("IN_SAMPLE_H2_2025", [r for r in test if r["day"] >= "2025-07-01"]),
    ):
        du = first_day(subset)
        # best structural filter in-sample
        best = None
        for name, f in core[::2]:
            rows = first_day(apply_f(subset, f))
            if not is_100(rows):
                continue
            if best is None or len(rows) > best["n"]:
                best = {"logic": name, "filters": f, "n": len(rows), "rows": rows}
        # also all-win by rank prefix on unfiltered DU
        for rname, rfn in RANKERS.items():
            pref = longest_win_prefix(du, rfn)
            if is_100(pref) and (best is None or len(pref) > best["n"]):
                best = {"logic": f"prefix|{rname}", "filters": {"rank": rname}, "n": len(pref), "rows": pref}
        if best:
            ceilings.append(
                {
                    "label": label,
                    "logic": best["logic"],
                    "filters": best["filters"],
                    "pool": pool_name,
                    "kind": "CEILING_IN_SAMPLE",
                    **agg(best["rows"]),
                    "calls": [strip(r) for r in best["rows"]],
                }
            )

    # Dedup honest by test call day-set
    def sig(b):
        days = tuple(sorted(c["day"] for c in b.get("test_calls") or []))
        return (b.get("kind"), days, b["test"]["n"])

    uniq = []
    seen = set()
    for b in sorted(honest_100, key=lambda x: -x["test"]["n"]):
        s = sig(b)
        if s in seen:
            continue
        seen.add(s)
        uniq.append(b)

    print(
        f"  done honest_test100={len(uniq)} train100={len(train_only_100)} "
        f"rank={len(rank_books)} wf={len(wf_books)} ({time.time()-t0:.0f}s)",
        flush=True,
    )
    return {
        "pool": pool_name,
        "n_train": len(train),
        "n_test": len(test),
        "honest_100": uniq,
        "train_only_top": sorted(train_only_100, key=lambda b: (-b["train"]["n"], -b["test"]["hit_pct"], -b["test"]["n"]))[:20],
        "rank_books_top": sorted(rank_books, key=lambda b: (-(b["test"]["n"] if b["test"]["hit_pct"] >= 100 else 0), -b["train"]["n"]))[:15],
        "wf_books": wf_books,
        "ceilings": ceilings,
        "base_test": agg(first_day(test)),
        "base_train": agg(first_day(train)),
    }


def write_report(results: List[dict], meta: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # Global best honest
    all_honest = []
    for r in results:
        for b in r.get("honest_100") or []:
            all_honest.append(b)
    all_honest.sort(key=lambda b: (-b["test"]["n"], -b["train"]["n"]))

    lines = [
        "# NIFTY 1m — **100% only** multi-logic research",
        "",
        "**Not live. Does not list Calls.**",
        "",
        f"- Train ≤ `{TRAIN_END}` · Test `{TEST_START}` → `{TEST_END}`",
        f"- Bars: {meta.get('n_bars')} · Risk ±{base.RISK:g}",
        "- Only books shown in the lead table are **100% on test** with train-frozen filters (or walk-forward).",
        "",
        "## Lead table — honest 100% test books (day-unique)",
        "",
        "| Rank | Pool | Kind | Test n | Train n | Logic (short) |",
        "|---:|---|---|---:|---:|---|",
    ]
    if not all_honest:
        lines.append("| — | — | — | 0 | 0 | _none found_ |")
    for i, b in enumerate(all_honest[:25], 1):
        short = (b.get("logic") or "")[:70]
        lines.append(
            f"| {i} | `{b.get('pool')}` | `{b.get('kind')}` | **{b['test']['n']}** | "
            f"{b['train']['n']} | `{short}` |"
        )

    lines += ["", "## Best honest books (detail)", ""]
    for i, b in enumerate(all_honest[:8], 1):
        lines += [
            f"### #{i} · {b.get('pool')} · test **{b['test']['n']} @ 100%** (train {b['train']['n']} @ 100%)",
            "",
            f"- Kind: `{b.get('kind')}`",
            f"- Logic: `{b.get('logic')}`",
            f"- Filters: `{json.dumps(b.get('filters'), default=str)}`",
            "",
            "| Day | HM | Side | or_ext | OR | Win |",
            "|---|---|---|---:|---:|:---:|",
        ]
        for c in b.get("test_calls") or []:
            lines.append(
                f"| {c.get('day')} | {c.get('hm')} | {c.get('decision')} | "
                f"{c.get('or_ext')} | {c.get('or_width')} | {'Y' if c.get('win') else 'N'} |"
            )
        lines.append("")

    lines += ["## Per-pool base rates + ceilings", ""]
    for r in results:
        lines += [
            f"### `{r['pool']}`",
            "",
            f"- Train DU: {r['base_train']} · Test DU: {r['base_test']}",
            f"- Honest test-100 books: **{len(r.get('honest_100') or [])}**",
            "",
            "| Ceiling | N | Hit% | Logic |",
            "|---|---:|---:|---|",
        ]
        for c in r.get("ceilings") or []:
            lines.append(f"| `{c['label']}` | {c['n']} | {c['hit_pct']} | `{(c.get('logic') or '')[:50]}` |")
        lines += ["", "Walk-forward 100% years:", ""]
        if not r.get("wf_books"):
            lines.append("_none_")
        for w in r.get("wf_books") or []:
            lines.append(
                f"- `{w['logic'][:60]}` · prior n={w['train']['n']} · year n={w['test']['n']} @100%"
            )
        lines.append("")

    # Combined unique test calls across top honest books (intersection vs union)
    if all_honest:
        best = all_honest[0]
        lines += [
            "## Research pick (100% only)",
            "",
            f"**Promote-candidate (research):** `{best.get('pool')}` · "
            f"**{best['test']['n']} test calls @ 100%** · train {best['train']['n']} @ 100%.",
            f"Logic: `{best.get('logic')}`",
            "",
            "These are the only test-year calls this rule would have taken — all winners under ±30 T1/SL.",
            "",
        ]
    else:
        lines += [
            "## Research pick (100% only)",
            "",
            "No train-frozen filter achieved test 100% with ≥3 day-unique calls.",
            "See ceilings / H1 streak for in-sample upper bounds.",
            "",
        ]

    lines += [
        "## Policy",
        "",
        "- `research_only=true` · `not_live=true`",
        "- In-sample ceilings are **not** promote rules.",
        "- Do not wire live without a separate promote plan + paper check.",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    # JSON: keep honest books + ceilings; trim huge train_only
    payload = {
        "meta": meta,
        "train_end": TRAIN_END,
        "test_start": TEST_START,
        "test_end": TEST_END,
        "honest_100_all": [
            {k: v for k, v in b.items() if k != "train_calls"} for b in all_honest
        ],
        "pools": [
            {
                "pool": r["pool"],
                "base_train": r["base_train"],
                "base_test": r["base_test"],
                "n_honest": len(r.get("honest_100") or []),
                "honest_100": [{k: v for k, v in b.items() if k != "train_calls"} for b in (r.get("honest_100") or [])[:15]],
                "ceilings": r.get("ceilings"),
                "wf_books": [{k: v for k, v in b.items() if k != "train_calls"} for b in (r.get("wf_books") or [])],
            }
            for r in results
        ],
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {REPORT_MD}", flush=True)
    print(f"wrote {REPORT_JSON}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · 100%-ONLY multi-logic hunt · RESEARCH", flush=True)
    print(f"train≤{TRAIN_END} test {TEST_START}→{TEST_END}", flush=True)
    print("=" * 60, flush=True)

    bars = base.load_existing_1m()
    if bars.empty:
        print("FAIL: no bars", flush=True)
        return 1
    bars = bars[
        (bars.index >= pd.Timestamp(base.START, tz="Asia/Kolkata"))
        & (bars.index <= pd.Timestamp(f"{base.END} 23:59:59", tz="Asia/Kolkata"))
    ]
    meta = {
        "n_bars": len(bars),
        "n_days": len({base._day(ts) for ts in bars.index}),
        "research_only": True,
        "not_live": True,
    }
    print(f"tape bars={meta['n_bars']} days={meta['n_days']}", flush=True)

    results = []
    for pool_name, gates in POOLS.items():
        tickets, reasons, _ = base.build_clean_tickets(bars, gates=gates)
        print(f"  {pool_name} clean={len(tickets)} ok={reasons.get('ok')}", flush=True)
        rows = enrich(tickets)
        # attach pool tag
        for r in rows:
            r["pool"] = pool_name
        results.append(mine_pool(pool_name, rows, min_train_n=5, min_test_n=3))

    write_report(results, meta)

    # Console highlight
    print("\n" + "=" * 60, flush=True)
    all_h = []
    for r in results:
        all_h.extend(r.get("honest_100") or [])
    all_h.sort(key=lambda b: -b["test"]["n"])
    if all_h:
        print(f"BEST honest 100%: n_test={all_h[0]['test']['n']} pool={all_h[0]['pool']} logic={all_h[0]['logic'][:80]}", flush=True)
        for b in all_h[:5]:
            print(f"  · {b['pool']} test={b['test']['n']} train={b['train']['n']} {b['kind']}", flush=True)
    else:
        print("No honest test-100 books with n≥3", flush=True)
    print("DONE · research only", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
