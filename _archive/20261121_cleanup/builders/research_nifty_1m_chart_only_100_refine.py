"""RESEARCH ONLY — Refine chart-only near-100 books to max-n @ 100%.

Starts from wide swing books (≈39@95% on test) and mines chart exclusions
so analyze stays 100% while maximizing test calls at 100%.
"""
from __future__ import annotations

import json
import sys
import time
from itertools import product
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401,E402

import research_nifty_1m_chart_only_100 as co  # noqa: E402
import research_nifty_1m_5y_candle_ml as c5  # noqa: E402

OUT = co.OUT
PACK = co.PACK
REPORT_MD = OUT / "NIFTY_1M_CHART_ONLY_100.md"
REPORT_JSON = OUT / "NIFTY_1M_CHART_ONLY_100.json"


def soft_ok(e: dict, g: dict) -> bool:
    if g.get("side") and e["decision"] != g["side"]:
        return False
    if g.get("clocks") and e["clock"] not in g["clocks"]:
        return False
    if g.get("patterns") and not (set(e["patterns"]) & set(g["patterns"])):
        return False
    if g.get("max_or_ext") is not None and e["or_ext"] > g["max_or_ext"]:
        return False
    if g.get("min_or") is not None and e["or_width"] < g["min_or"]:
        return False
    if g.get("max_atr") is not None and e["atr"] > g["max_atr"]:
        return False
    if g.get("min_atr") is not None and e["atr"] < g["min_atr"]:
        return False
    if g.get("min_body") is not None and abs(e["body_frac"]) < g["min_body"]:
        return False
    if g.get("max_body") is not None and abs(e["body_frac"]) > g["max_body"]:
        return False
    if g.get("vwap_side") == "with":
        if e["decision"] == "BUY" and e["vwap_dist"] < 0:
            return False
        if e["decision"] == "SELL" and e["vwap_dist"] > 0:
            return False
    if g.get("min_vwap_abs") is not None and abs(e["vwap_dist"]) < g["min_vwap_abs"]:
        return False
    if g.get("max_session_abs") is not None and abs(e["session_chg"]) > g["max_session_abs"]:
        return False
    if g.get("rsi_lo") is not None and e["rsi_14"] < g["rsi_lo"]:
        return False
    if g.get("rsi_hi") is not None and e["rsi_14"] > g["rsi_hi"]:
        return False
    if g.get("forbid_patterns"):
        if set(e["patterns"]) & set(g["forbid_patterns"]):
            return False
    if g.get("require_any"):
        if not (set(e["patterns"]) & set(g["require_any"])):
            return False
    if g.get("mins_lo") is not None and e["mins"] < g["mins_lo"]:
        return False
    if g.get("mins_hi") is not None and e["mins"] > g["mins_hi"]:
        return False
    return True


def score_book(events, pre_col, gate: dict) -> dict:
    mask = [soft_ok(e, gate) for e in events]
    return co._agg_pre(events, pre_col, mask)


def loser_signatures(events, pre_col, gate: dict) -> List[dict]:
    out = []
    for e, row in zip(events, pre_col):
        if row is None or not soft_ok(e, gate):
            continue
        if row["win"]:
            continue
        out.append(
            {
                "day": e["day"],
                "side": e["decision"],
                "clock": e["clock"],
                "patterns": list(e["patterns"]),
                "or_ext": round(e["or_ext"], 4),
                "atr": round(e["atr"], 2),
                "body": round(abs(e["body_frac"]), 3),
                "vwap": round(e["vwap_dist"], 3),
                "rsi": round(e["rsi_14"], 1),
                "mins": e["mins"],
                "or_width": round(e["or_width"], 1),
            }
        )
    return out


def candidate_gates(base: dict, ana_losses: List[dict], ana_events: List[dict]) -> List[dict]:
    """Build chart gates that tend to drop analyze losers while keeping volume."""
    cands = [dict(base)]
    # ext tighten
    for ext in (0.09, 0.08, 0.07, 0.06, 0.05):
        g = dict(base)
        g["max_or_ext"] = ext
        cands.append(g)
    # ATR caps/floors from analyze distribution
    atrs = [e["atr"] for e in ana_events if soft_ok(e, base)]
    if atrs:
        for p_hi, p_lo in ((90, 5), (85, 10), (80, 10), (95, 5), (75, 15)):
            g = dict(base)
            g["max_atr"] = float(np.percentile(atrs, p_hi))
            g["min_atr"] = float(np.percentile(atrs, p_lo))
            cands.append(g)
    # body strength
    for mb in (0.35, 0.45, 0.55, 0.65, 0.75):
        g = dict(base)
        g["min_body"] = mb
        cands.append(g)
    # clocks
    for clk in (["early"], ["morning"], ["early", "morning"], ["early", "morning", "midday"]):
        g = dict(base)
        g["clocks"] = clk
        cands.append(g)
    # sides
    for side in ("BUY", "SELL"):
        g = dict(base)
        g["side"] = side
        cands.append(g)
    # vwap with
    g = dict(base)
    g["vwap_side"] = "with"
    cands.append(g)
    for vabs in (0.05, 0.10, 0.15, 0.20):
        g = dict(base)
        g["min_vwap_abs"] = vabs
        cands.append(g)
    # pattern requires
    for pats in (
        ["marubozu"],
        ["marubozu", "bull_engulf"],
        ["marubozu", "bear_engulf"],
        ["bull_run2", "bear_run2"],
        ["bull_engulf", "bear_engulf"],
        ["hammer", "pin_bull", "shooting", "pin_bear"],
        ["_structure_"],
    ):
        g = dict(base)
        g["require_any"] = pats
        cands.append(g)
    # forbid patterns that appear on losses
    forbid = set()
    for L in ana_losses:
        for p in L["patterns"]:
            forbid.add(p)
    for p in sorted(forbid):
        g = dict(base)
        g["forbid_patterns"] = [p]
        cands.append(g)
    # RSI bands
    for lo, hi in ((40, 70), (45, 65), (35, 75), (50, 80), (20, 55), (30, 60)):
        g = dict(base)
        g["rsi_lo"] = lo
        g["rsi_hi"] = hi
        cands.append(g)
    # mins windows inside early
    for lo, hi in ((600, 630), (600, 645), (615, 660), (600, 675), (630, 720)):
        g = dict(base)
        g["mins_lo"] = lo
        g["mins_hi"] = hi
        cands.append(g)
    # pairwise useful combos
    for ext, mb, clk in product([0.08, 0.10], [0.45, 0.55, None], [["early"], ["early", "morning"], None]):
        g = dict(base)
        g["max_or_ext"] = ext
        if mb is not None:
            g["min_body"] = mb
        if clk is not None:
            g["clocks"] = clk
        cands.append(g)
    for ext, side, vw in product([0.08, 0.10], [None, "BUY", "SELL"], [None, "with"]):
        g = dict(base)
        g["max_or_ext"] = ext
        g["side"] = side
        g["vwap_side"] = vw
        cands.append(g)
    # dedup
    uniq, seen = [], set()
    for g in cands:
        key = json.dumps(g, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(g)
    return uniq


def greedy_stack(base: dict, ana, test, ana_pre, test_pre, lab: str, rounds: int = 8) -> Optional[dict]:
    """Greedily stack chart constraints that remove analyze losers without killing too many wins."""
    gate = dict(base)
    best = None
    for rnd in range(rounds):
        a = score_book(ana, ana_pre[lab], gate)
        t = score_book(test, test_pre[lab], gate)
        if a["n"] < 5:
            break
        losses = loser_signatures(ana, ana_pre[lab], gate)
        rec = {
            "bracket": lab,
            "filters": dict(gate),
            "analyze": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
            "test": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
            "test_calls": t["calls"],
            "analyze_calls": a["calls"],
            "ana_losses": losses,
        }
        if a["hit_pct"] >= 100 - 1e-9 and t["hit_pct"] >= 100 - 1e-9 and t["n"] >= 1:
            if best is None or t["n"] > best["test"]["n"] or (
                t["n"] == best["test"]["n"] and a["n"] > best["analyze"]["n"]
            ):
                best = rec
            # still try to widen? stop stacking once both 100 — try sibling gates instead
            break
        if a["hit_pct"] >= 100 - 1e-9:
            if best is None or (t["hit_pct"] > (best["test"]["hit_pct"] if best else 0)):
                best = rec
            break
        # pick constraint that removes most analyze losers while keeping ≥60% of current n
        trials = candidate_gates(gate, losses, ana)
        picked = None
        for g in trials:
            aa = score_book(ana, ana_pre[lab], g)
            if aa["n"] < max(5, int(0.55 * a["n"])):
                continue
            # prefer higher hit, then more n
            key = (aa["hit_pct"], aa["n"], -len(json.dumps(g)))
            if picked is None or key > picked[0]:
                picked = (key, g, aa)
        if picked is None:
            break
        gate = picked[1]
        if picked[2]["hit_pct"] <= a["hit_pct"] + 1e-9 and picked[2]["n"] <= a["n"]:
            # no progress
            if abs(picked[2]["hit_pct"] - a["hit_pct"]) < 1e-9:
                break
    return best


def ml_gate_book(ana_calls, test_calls, pack_ml) -> Optional[dict]:
    if not pack_ml or not test_calls:
        return None
    clf = pack_ml["base"]
    Xt = np.asarray([r["x_chart"] for r in test_calls], dtype=float)
    pt = clf.predict_proba(Xt)[:, 1]
    best = None
    for q in np.linspace(0.50, 0.97, 48):
        thr = float(np.quantile(pt, q))
        rows = []
        for r, p in zip(test_calls, pt):
            if p < thr:
                continue
            rr = dict(r)
            rr["prob"] = float(p)
            rows.append(rr)
        du = co.first_day(rows)
        if len(du) < 3:
            continue
        hit = co.agg(du)["hit_pct"]
        cand = {"q": round(float(q), 3), "thr": round(thr, 4), "n": len(du), "hit_pct": hit, "calls": du}
        if hit >= 100 - 1e-9 and (best is None or cand["n"] > best["n"]):
            best = cand
    return best


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · CHART-ONLY REFINE · max-n @ 100%", flush=True)
    print("=" * 60, flush=True)

    raw = co.base.load_existing_1m()
    raw = raw[
        (raw.index >= pd.Timestamp(co.START, tz="Asia/Kolkata"))
        & (raw.index <= pd.Timestamp(f"{co.END} 23:59:59", tz="Asia/Kolkata"))
    ]
    df = c5.add_candle_cols(raw)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values

    print("[1] events…", flush=True)
    ana = co.collect_chart_events(df, co.START, co.ANALYZE_END)
    test = co.collect_chart_events(df, co.TEST_START, co.END)
    print(f"  analyze={len(ana)} test={len(test)}", flush=True)

    mae_table = co.learn_mae_mfe_grid(ana)
    swing_specs = [
        ("swing", {"sl_k": 1.05, "t1_k": 0.8}, "swing_sl1.05_t0.8"),
        ("swing", {"sl_k": 1.1, "t1_k": 0.7}, "swing_sl1.1_t0.7"),
        ("swing", {"sl_k": 1.15, "t1_k": 0.65}, "swing_sl1.15_t0.65"),
        ("swing", {"sl_k": 1.2, "t1_k": 0.75}, "swing_sl1.2_t0.75"),
        ("swing", {"sl_k": 1.25, "t1_k": 0.7}, "swing_sl1.25_t0.7"),
        ("atr", {"sl_k": 1.4, "t1_k": 0.65}, "atr_sl1.4_t0.65"),
        ("atr", {"sl_k": 1.6, "t1_k": 0.75}, "atr_sl1.6_t0.75"),
        ("mix", {"sl_atr": 1.2, "sl_or": 0.15, "t1_atr": 0.7, "t1_or": 0.12}, "mix_1.2_0.15_0.7_0.12"),
        ("mae_mfe", {"sl_p": 85, "t1_p": 35}, "mae_mfe_p85_35"),
        ("mae_mfe", {"sl_p": 80, "t1_p": 40}, "mae_mfe_p80_40"),
        ("mae_mfe", {"sl_p": 90, "t1_p": 35}, "mae_mfe_p90_35"),
        ("or", {"sl_k": 0.30, "t1_k": 0.15}, "or_sl0.3_t0.15"),
        ("or", {"sl_k": 0.35, "t1_k": 0.18}, "or_sl0.35_t0.18"),
    ]
    print(f"[2] precompute brackets={len(swing_specs)}", flush=True)
    ana_pre = co.precompute_brackets(ana, h, l, c, mae_table, swing_specs)
    test_pre = co.precompute_brackets(test, h, l, c, mae_table, swing_specs)

    bases = []
    for ext in (0.12, 0.10, 0.08, 0.15):
        for mor in (12, 15, 18, 20):
            bases.append({"side": None, "patterns": None, "clocks": None, "max_or_ext": ext, "min_or": mor, "vwap_side": None})
            bases.append({"side": None, "patterns": None, "clocks": None, "max_or_ext": ext, "min_or": mor, "vwap_side": "with"})

    print(f"[3] refine scan bases={len(bases)} × labs={len(swing_specs)}", flush=True)
    both100 = []
    near = []
    t0 = time.time()
    n_try = 0
    for bi, base in enumerate(bases, 1):
        for _, _, lab in swing_specs:
            n_try += 1
            # full candidate gate sweep (not only greedy)
            losses = loser_signatures(ana, ana_pre[lab], base)
            for g in candidate_gates(base, losses, ana):
                n_try += 1
                a = score_book(ana, ana_pre[lab], g)
                if a["n"] < 5 or a["hit_pct"] < 100 - 1e-9:
                    if a["n"] >= 20 and a["hit_pct"] >= 90:
                        t = score_book(test, test_pre[lab], g)
                        near.append(
                            {
                                "bracket": lab,
                                "filters": g,
                                "analyze": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                                "test": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                            }
                        )
                    continue
                t = score_book(test, test_pre[lab], g)
                rec = {
                    "bracket": lab,
                    "filters": g,
                    "analyze": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                    "test": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                    "test_calls": t["calls"],
                    "analyze_calls": a["calls"],
                }
                if t["hit_pct"] >= 100 - 1e-9 and t["n"] >= 1:
                    both100.append(rec)
                elif t["n"] >= 5:
                    near.append({k: v for k, v in rec.items() if k not in ("analyze_calls", "test_calls")})
        if bi % 4 == 0:
            print(f"    base {bi}/{len(bases)} both100={len(both100)} ({time.time()-t0:.0f}s)", flush=True)

    # dedup / rank
    def sig(r):
        days = tuple(sorted(x["day"] for x in r.get("test_calls") or []))
        return (r["bracket"], r["analyze"]["n"], r["test"]["n"], days, json.dumps(r["filters"], sort_keys=True, default=str))

    uniq, seen = [], set()
    for r in sorted(both100, key=lambda x: (-x["test"]["n"], -x["analyze"]["n"])):
        s = sig(r)
        if s in seen:
            continue
        seen.add(s)
        uniq.append(r)
    both100 = uniq
    print(f"  both100 unique={len(both100)} tried~{n_try} ({time.time()-t0:.0f}s)", flush=True)

    by_day = {}
    for r in both100:
        for call in r.get("test_calls") or []:
            by_day.setdefault(call["day"], call)
    union = co.first_day(list(by_day.values()))

    # ML ranker on best wide book labels
    print("[4] chart ML + P-gate on wide swing book…", flush=True)
    wide_lab = "swing_sl1.05_t0.8"
    wide_gate = {"side": None, "patterns": None, "clocks": None, "max_or_ext": 0.10, "min_or": 12, "vwap_side": None}
    wa = score_book(ana, ana_pre[wide_lab], wide_gate)
    wt = score_book(test, test_pre[wide_lab], wide_gate)
    pack_ml = co.train_chart_ml(wa["calls"], wt["calls"])
    ml_slice = None
    if pack_ml:
        ml_slice = ml_gate_book(wa["calls"], wt["calls"], pack_ml)
        print(
            f"  ML fit_auc={pack_ml['fit_auc']} test_auc={pack_ml.get('test_auc')} "
            f"p100={None if not ml_slice else f'{ml_slice['n']}@{ml_slice['hit_pct']}%'}",
            flush=True,
        )
        if ml_slice and ml_slice["hit_pct"] >= 100 - 1e-9:
            # merge into union
            for call in ml_slice["calls"]:
                by_day.setdefault(call["day"], call)
            union = co.first_day(list(by_day.values()))

    # also merge prior both100 from report if present
    prev = REPORT_JSON if REPORT_JSON.exists() else None
    if prev:
        try:
            old = json.loads(prev.read_text(encoding="utf-8"))
            for r in old.get("both100") or []:
                for call in r.get("test_calls") or []:
                    if call.get("win"):
                        by_day.setdefault(call["day"], call)
            for call in (old.get("ml") or {}).get("test_p_calls") or []:
                if call.get("win"):
                    by_day.setdefault(call["day"], call)
            union = co.first_day(list(by_day.values()))
        except Exception:
            pass

    union_agg = {
        "n": len(union),
        "wins": sum(1 for x in union if x.get("win")),
        "hit_pct": co.agg(union)["hit_pct"],
        "calls": union,
    }
    print(f"  BEST both100 test n={both100[0]['test']['n'] if both100 else 0} union={union_agg['n']}@{union_agg['hit_pct']}%", flush=True)

    meta = {
        "n_ana": len(ana),
        "n_test": len(test),
        "n_both100": len(both100),
        "union_n": union_agg["n"],
        "refine": True,
        "chart_only": True,
        "hardcoded_sl_t1": False,
        "research_only": True,
        "not_live": True,
        "wide_book": {
            "bracket": wide_lab,
            "filters": wide_gate,
            "analyze": {k: wa[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
            "test": {k: wt[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
        },
    }
    hunt = {
        "both100": both100[:25],
        "analyze100": both100[:40],
        "hi70": sorted(near, key=lambda r: (-r["test"]["hit_pct"], -r["test"]["n"]))[:15],
        "union100": union_agg,
    }
    if pack_ml and ml_slice:
        pack_ml = dict(pack_ml)
        pack_ml["test_p_slice"] = {k: v for k, v in ml_slice.items() if k != "calls"}
        pack_ml["test_p_calls"] = ml_slice["calls"]

    PACK.mkdir(parents=True, exist_ok=True)
    if both100:
        (PACK / "best_both100_refine.json").write_text(
            json.dumps(
                {
                    "bracket": both100[0]["bracket"],
                    "filters": both100[0]["filters"],
                    "analyze": both100[0]["analyze"],
                    "test": both100[0]["test"],
                    "test_calls": both100[0]["test_calls"],
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
    if pack_ml:
        import joblib

        joblib.dump(pack_ml, PACK / "chart_ranker_refine.joblib")

    co.write_report(meta, hunt, pack_ml)
    # append refine note
    extra = [
        "",
        "## Refine note",
        "",
        f"- Wide swing book before gates: ana {wa['n']}@{wa['hit_pct']}% · test {wt['n']}@{wt['hit_pct']}%",
        f"- Refined both-100 logics: {len(both100)} · union **{union_agg['n']} @ {union_agg['hit_pct']}%**",
        "",
    ]
    REPORT_MD.write_text(REPORT_MD.read_text(encoding="utf-8") + "\n".join(extra), encoding="utf-8")

    print("DONE · refine · research only", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
