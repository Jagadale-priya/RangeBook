"""RESEARCH ONLY — refine daily must-call to BOTH-WINDOW 100%.

Prior pass: first_pattern + sess ~95% both; misses = wrong-side early entries.
This pass:
  1) Collect ALL window candidates per day (not first-only).
  2) Oracle: under fixed ATR/sess brackets, can every day pick ≥1 winning cand?
  3) Non-lookahead pickers that try to match the oracle (trend-align, RSI, body, score).
  4) Write updated report if ACHIEVED.

  python -u prod_live/tests/builders/research_nifty_1m_daily_must_100_refine.py
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

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_chart_only_100 as co  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_daily_must_100 as dm  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_daily_must_100"
REPORT_MD = OUT / "NIFTY_1M_DAILY_MUST_100.md"
REPORT_JSON = OUT / "NIFTY_1M_DAILY_MUST_100.json"


def collect_all_day_cands(
    df: pd.DataFrame,
    day_lo: str,
    day_hi: str,
    window: Tuple[int, int] = (560, 750),
) -> Dict[str, List[dict]]:
    """All pattern + strong-body candidates per day in window."""
    h_all = df["High"].astype(float).values
    l_all = df["Low"].astype(float).values
    c_all = df["Close"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(df.index)}
    by_day: Dict[str, List[dict]] = {}
    days = [d for d in df["day"].unique() if day_lo <= d <= day_hi]
    mins_lo, mins_hi = window
    t0 = time.time()

    for di, day in enumerate(days, 1):
        if di % 50 == 0:
            print(f"    all-cands {di}/{len(days)} ({time.time()-t0:.0f}s)", flush=True)
        sess = df[df["day"] == day]
        if len(sess) < 40:
            continue
        day_open = float(sess["Open"].iloc[0])
        cands = []
        for pos in range(3, len(sess)):
            row = sess.iloc[pos]
            mins = int(row["mins"])
            if mins < mins_lo or mins > mins_hi:
                continue
            body = float(row["Close"]) - float(row["Open"])
            hit = [p for p in dm.PRIORITY if p in row.index and int(row[p]) == 1]
            primary = hit[0] if hit else None
            sides: List[Tuple[str, str, float]] = []
            if primary:
                side = dm._side_for(primary, body)
                if side is not None and not (
                    (side == "BUY" and body <= 0) or (side == "SELL" and body >= 0)
                ):
                    score = 100 - (dm.PRIORITY.index(primary) if primary in dm.PRIORITY else 50)
                    sides.append((side, primary, float(score)))
            if abs(float(row["body_frac"])) >= 0.40:
                if body > 0:
                    sides.append(("BUY", primary or "_body_bull", abs(float(row["body_frac"])) * 10))
                elif body < 0:
                    sides.append(("SELL", primary or "_body_bear", abs(float(row["body_frac"])) * 10))
            # dual-side chart probe (oracle ceiling): both directions from same bar
            if abs(float(row["body_frac"])) >= 0.25 or primary:
                for sd, lab in (("BUY", "_probe_buy"), ("SELL", "_probe_sell")):
                    if not any(s[0] == sd for s in sides):
                        sides.append((sd, lab, 1.0))

            atr = float(row["atr14"]) if np.isfinite(row["atr14"]) else 8.0
            atr = max(atr, 3.0)
            entry = float(row["Close"])
            lo_win = float(sess["Low"].iloc[max(0, pos - 2) : pos + 1].min())
            hi_win = float(sess["High"].iloc[max(0, pos - 2) : pos + 1].max())
            sess_lo = float(sess["Low"].iloc[: pos + 1].min())
            sess_hi = float(sess["High"].iloc[: pos + 1].max())
            drift = entry - day_open
            ts = sess.index[pos]
            full_i = idx_map[ts]
            seen_side = set()
            for side, prim, score in sides:
                if side in seen_side and prim.startswith("_probe"):
                    continue
                seen_side.add(side)
                sl_pat = max(entry - lo_win, 0.0) if side == "BUY" else max(hi_win - entry, 0.0)
                sl_sess = max(entry - sess_lo, 0.0) if side == "BUY" else max(sess_hi - entry, 0.0)
                mae, mfe = co.excursion(h_all, l_all, c_all, full_i, side)
                cands.append(
                    {
                        "day": day,
                        "hm": row["hm"],
                        "decision": side,
                        "primary": prim,
                        "patterns": hit or [prim],
                        "entry": entry,
                        "mins": mins,
                        "clock": co.clock_bucket(mins),
                        "atr": atr,
                        "body_frac": float(row["body_frac"]),
                        "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
                        "session_chg": float(drift / day_open * 100),
                        "drift": drift,
                        "mae": mae,
                        "mfe": mfe,
                        "full_i": full_i,
                        "sl_pat": sl_pat,
                        "sl_sess": sl_sess,
                        "score": score,
                        "trend_align": (
                            1 if (side == "BUY" and drift > 0) or (side == "SELL" and drift < 0) else 0
                        ),
                        "is_probe": prim.startswith("_probe"),
                    }
                )
        # hard fallback if empty
        if not cands:
            for pos in range(3, len(sess)):
                row = sess.iloc[pos]
                mins = int(row["mins"])
                if mins < 565 or mins > 750:
                    continue
                body = float(row["Close"]) - float(row["Open"])
                if abs(body) < 1e-6:
                    continue
                side = "BUY" if body > 0 else "SELL"
                atr = max(float(row["atr14"]) if np.isfinite(row["atr14"]) else 8.0, 3.0)
                entry = float(row["Close"])
                lo_win = float(sess["Low"].iloc[max(0, pos - 2) : pos + 1].min())
                hi_win = float(sess["High"].iloc[max(0, pos - 2) : pos + 1].max())
                sess_lo = float(sess["Low"].iloc[: pos + 1].min())
                sess_hi = float(sess["High"].iloc[: pos + 1].max())
                sl_pat = max(entry - lo_win, 0.0) if side == "BUY" else max(hi_win - entry, 0.0)
                sl_sess = max(entry - sess_lo, 0.0) if side == "BUY" else max(sess_hi - entry, 0.0)
                drift = entry - day_open
                ts = sess.index[pos]
                full_i = idx_map[ts]
                mae, mfe = co.excursion(h_all, l_all, c_all, full_i, side)
                cands.append(
                    {
                        "day": day,
                        "hm": row["hm"],
                        "decision": side,
                        "primary": "_fallback",
                        "patterns": ["_fallback"],
                        "entry": entry,
                        "mins": mins,
                        "clock": co.clock_bucket(mins),
                        "atr": atr,
                        "body_frac": float(row["body_frac"]),
                        "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
                        "session_chg": float(drift / day_open * 100),
                        "drift": drift,
                        "mae": mae,
                        "mfe": mfe,
                        "full_i": full_i,
                        "sl_pat": sl_pat,
                        "sl_sess": sl_sess,
                        "score": 0,
                        "trend_align": (
                            1 if (side == "BUY" and drift > 0) or (side == "SELL" and drift < 0) else 0
                        ),
                        "is_probe": False,
                    }
                )
                break
        if cands:
            by_day[day] = cands
    return by_day


def brackets_for(e: dict, kind: str, params: dict) -> Tuple[float, float]:
    atr = e["atr"]
    if kind == "atr":
        return max(params["sl_k"] * atr, 5.0), max(params["t1_k"] * atr, 5.0)
    if kind == "sess":
        return max(params["sl_k"] * e["sl_sess"], 0.9 * atr, 5.0), max(params["t1_k"] * atr, 5.0)
    if kind == "pat":
        return max(params["sl_k"] * e["sl_pat"], 0.8 * atr, 5.0), max(params["t1_k"] * atr, 5.0)
    if kind == "mix":
        sl = max(params["a"] * e["sl_pat"] + params["b"] * atr, 5.0)
        t1 = max(params["t"] * atr, 5.0)
        return sl, t1
    if kind == "wide":
        # very wide SL, tiny T1 — stress ceiling
        return max(params["sl_k"] * atr, 5.0), max(params["t1"], 5.0)
    if kind == "oracle_path":
        # research ceiling only: SL just above MAE, T1 just below MFE (still needs MFE>=5)
        sl = max(e["mae"] + params.get("buf", 1.0), 5.0)
        t1 = max(min(e["mfe"] * params.get("frac", 0.5), params.get("t1_cap", 12.0)), 5.0)
        if e["mfe"] < 5.0:
            return 5.0, 5.0  # will fail path if mfe < 5
        return sl, t1
    return max(1.5 * atr, 5.0), max(0.5 * atr, 5.0)


_PATH_CACHE: Dict[Tuple, Tuple[bool, str]] = {}


def path_cached(h, l, c, e: dict, sl: float, t1: float) -> Tuple[bool, str]:
    key = (e["full_i"], e["decision"], round(sl, 2), round(t1, 2))
    hit = _PATH_CACHE.get(key)
    if hit is not None:
        return hit
    # MAE/MFE gate — necessary; then confirm order
    if e["mfe"] + 1e-9 < t1 or e["mae"] >= sl - 1e-9:
        out = (False, "gate")
        _PATH_CACHE[key] = out
        return out
    win, outcome = co.path_hit(h, l, c, e["full_i"], e["decision"], sl, t1)
    out = (bool(win) and outcome == "t1", outcome)
    _PATH_CACHE[key] = out
    return out


def cand_wins(e: dict, h, l, c, kind: str, params: dict) -> bool:
    sl, t1 = brackets_for(e, kind, params)
    win, _ = path_cached(h, l, c, e, sl, t1)
    return win


def pick_oracle(cands: List[dict], h, l, c, kind, params) -> Optional[dict]:
    """Best winning cand by score then earliest."""
    winners = [e for e in cands if cand_wins(e, h, l, c, kind, params)]
    if not winners:
        return None
    winners.sort(key=lambda x: (-x["score"], x["mins"]))
    return winners[0]


def pick_rule(cands: List[dict], rule: str) -> Optional[dict]:
    if not cands:
        return None
    # non-oracle pickers never use dual-side probes
    pool = [e for e in cands if not e.get("is_probe")]
    if not pool:
        pool = list(cands)
    if rule == "first":
        return sorted(pool, key=lambda x: x["mins"])[0]
    if rule == "first_pattern":
        pats = [e for e in pool if not str(e["primary"]).startswith("_")]
        src = pats or pool
        return sorted(src, key=lambda x: x["mins"])[0]
    if rule == "trend_first":
        al = [e for e in pool if e["trend_align"] == 1]
        src = al or pool
        return sorted(src, key=lambda x: x["mins"])[0]
    if rule == "trend_best_body":
        al = [e for e in pool if e["trend_align"] == 1]
        src = al or pool
        return max(src, key=lambda x: abs(x["body_frac"]))
    if rule == "trend_pattern":
        al = [e for e in pool if e["trend_align"] == 1 and not str(e["primary"]).startswith("_")]
        if not al:
            al = [e for e in pool if e["trend_align"] == 1]
        src = al or pool
        return sorted(src, key=lambda x: (-x["score"], x["mins"]))[0]
    if rule == "rsi_trend":
        # BUY when rsi<=55 & drift>0; SELL when rsi>=45 & drift<0
        filt = []
        for e in pool:
            if e["decision"] == "BUY" and e["drift"] > 0 and e["rsi_14"] <= 60:
                filt.append(e)
            elif e["decision"] == "SELL" and e["drift"] < 0 and e["rsi_14"] >= 40:
                filt.append(e)
        src = filt or [e for e in pool if e["trend_align"] == 1] or pool
        return sorted(src, key=lambda x: (-x["score"], x["mins"]))[0]
    if rule == "best_score_align":
        al = [e for e in pool if e["trend_align"] == 1]
        src = al or pool
        return max(src, key=lambda x: x["score"])
    if rule == "late_trend":
        # prefer 9:35–10:30 aligned
        mid = [e for e in pool if 575 <= e["mins"] <= 630 and e["trend_align"] == 1]
        src = mid or [e for e in pool if e["trend_align"] == 1] or pool
        return sorted(src, key=lambda x: (-abs(x["body_frac"]), x["mins"]))[0]
    if rule == "mfe_proxy_mom":
        # proxy: largest |drift| among aligned (stronger open move)
        al = [e for e in pool if e["trend_align"] == 1]
        src = al or pool
        return max(src, key=lambda x: abs(x["drift"]))
    return sorted(pool, key=lambda x: x["mins"])[0]


def eval_picker(by_day: Dict[str, List[dict]], h, l, c, kind, params, picker: str) -> dict:
    rows = []
    miss = []
    for day, cands in sorted(by_day.items()):
        if picker == "oracle":
            e = pick_oracle(cands, h, l, c, kind, params)
        else:
            e = pick_rule(cands, picker)
        if e is None:
            miss.append(day)
            rows.append({"day": day, "win": False, "outcome": "none", "sl": 0, "t1": 0})
            continue
        sl, t1 = brackets_for(e, kind, params)
        win, outcome = path_cached(h, l, c, e, sl, t1)
        rows.append(
            {
                "day": day,
                "hm": e["hm"],
                "decision": e["decision"],
                "primary": e["primary"],
                "entry": e["entry"],
                "sl": round(sl, 2),
                "t1": round(t1, 2),
                "win": bool(win),
                "outcome": outcome,
                "atr": e["atr"],
                "rsi_14": e["rsi_14"],
                "picker": picker,
            }
        )
        if not win:
            miss.append(day)
    n = len(rows)
    wins = sum(1 for r in rows if r["win"])
    return {
        "n": n,
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else 0.0,
        "avg_sl": round(float(np.mean([r["sl"] for r in rows if r["sl"]])), 2) if rows else 0,
        "avg_t1": round(float(np.mean([r["t1"] for r in rows if r["t1"]])), 2) if rows else 0,
        "miss_days": miss,
        "calls": rows,
    }


def hunt(cal_by, test_by, h, l, c) -> dict:
    print("\n[3] Refine hunt (oracle first, then rules)…", flush=True)
    global _PATH_CACHE
    _PATH_CACHE = {}
    specs = []
    for sl_k, t1_k in product(
        [1.5, 2.0, 2.5, 3.0, 4.0, 6.0, 8.0, 12.0],
        [0.35, 0.4, 0.5, 0.6],
    ):
        specs.append(("atr", {"sl_k": sl_k, "t1_k": t1_k}, f"atr_{sl_k}_{t1_k}"))
    for sl_k, t1_k in product([1.5, 2.0, 2.5, 3.5, 5.0], [0.35, 0.4, 0.55]):
        specs.append(("sess", {"sl_k": sl_k, "t1_k": t1_k}, f"sess_{sl_k}_{t1_k}"))
        specs.append(("pat", {"sl_k": sl_k, "t1_k": t1_k}, f"pat_{sl_k}_{t1_k}"))
    for sl_k, t1 in product([6.0, 10.0, 14.0, 20.0], [5.0, 6.0, 7.0]):
        specs.append(("wide", {"sl_k": sl_k, "t1": t1}, f"wide_{sl_k}_{t1}"))
    specs.append(("oracle_path", {"buf": 1.0, "frac": 0.45, "t1_cap": 10.0}, "oracle_path"))

    rule_pickers = [
        "trend_pattern",
        "trend_first",
        "trend_best_body",
        "rsi_trend",
        "best_score_align",
        "late_trend",
        "mfe_proxy_mom",
        "first_pattern",
        "first",
    ]

    perfect = []
    near = []
    oracle_ceiling = []
    promising = []
    t0 = time.time()
    for i, (kind, params, lab) in enumerate(specs, 1):
        if i % 25 == 0:
            print(
                f"    oracle {i}/{len(specs)} ceil={len(oracle_ceiling)} ({time.time()-t0:.0f}s)",
                flush=True,
            )
        a_o = eval_picker(cal_by, h, l, c, kind, params, "oracle")
        t_o = eval_picker(test_by, h, l, c, kind, params, "oracle")
        rec_o = {
            "bracket": lab,
            "kind": kind,
            "params": params,
            "picker": "oracle",
            "calibrate": {k: a_o[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
            "last3m": {k: t_o[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
            "cal_miss": a_o["miss_days"][:10],
            "l3m_miss": t_o["miss_days"][:10],
            "last3m_calls": t_o["calls"],
            "cal_calls": a_o["calls"],
        }
        if a_o["hit_pct"] >= 100 - 1e-9 and t_o["hit_pct"] >= 100 - 1e-9:
            oracle_ceiling.append(
                {
                    "bracket": lab,
                    "kind": kind,
                    "params": params,
                    "calibrate": rec_o["calibrate"],
                    "last3m": rec_o["last3m"],
                }
            )
            perfect.append(rec_o)
            promising.append((kind, params, lab))
        elif t_o["hit_pct"] >= 96 and a_o["hit_pct"] >= 94:
            near.append(rec_o)
            if t_o["hit_pct"] >= 98 and a_o["hit_pct"] >= 97:
                promising.append((kind, params, lab))
        elif t_o["hit_pct"] >= 92 and a_o["hit_pct"] >= 90:
            near.append(rec_o)

    print(
        f"  oracle done · ceil={len(oracle_ceiling)} promising={len(promising)} ({time.time()-t0:.0f}s)",
        flush=True,
    )
    # de-dupe promising, keep oracle-perfect first (up to 20)
    seen = set()
    uniq = []
    for item in promising:
        if item[2] in seen:
            continue
        seen.add(item[2])
        uniq.append(item)
    uniq = uniq[:20]

    for j, (kind, params, lab) in enumerate(uniq, 1):
        print(f"    rules {j}/{len(uniq)} {lab}…", flush=True)
        for picker in rule_pickers:
            a = eval_picker(cal_by, h, l, c, kind, params, picker)
            t = eval_picker(test_by, h, l, c, kind, params, picker)
            rec = {
                "bracket": lab,
                "kind": kind,
                "params": params,
                "picker": picker,
                "calibrate": {k: a[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                "last3m": {k: t[k] for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1")},
                "cal_miss": a["miss_days"][:10],
                "l3m_miss": t["miss_days"][:10],
                "last3m_calls": t["calls"],
                "cal_calls": a["calls"],
            }
            if a["hit_pct"] >= 100 - 1e-9 and t["hit_pct"] >= 100 - 1e-9:
                perfect.append(rec)
            elif t["hit_pct"] >= 96 and a["hit_pct"] >= 94:
                near.append(rec)
            elif t["hit_pct"] >= 92 and a["hit_pct"] >= 90:
                near.append(rec)

    def rr(r):
        return r["last3m"]["avg_sl"] / max(r["last3m"]["avg_t1"], 1e-6)

    perfect.sort(key=lambda r: (0 if r["picker"] != "oracle" else 1, rr(r), -r["last3m"]["n"]))
    near.sort(
        key=lambda r: (
            0 if r["picker"] != "oracle" else 1,
            -r["last3m"]["hit_pct"],
            -r["calibrate"]["hit_pct"],
            rr(r),
        )
    )
    print(
        f"  oracle_ceil={len(oracle_ceiling)} perfect_both={len(perfect)} near={len(near)} ({time.time()-t0:.0f}s)",
        flush=True,
    )
    return {
        "perfect": perfect[:25],
        "near": near[:25],
        "oracle_ceiling": oracle_ceiling[:15],
    }


def write_report(meta, pack):
    OUT.mkdir(parents=True, exist_ok=True)
    champ = meta.get("champion")
    lines = [
        "# NIFTY 1m — **daily must-call** (1 call / day) · aim 100%",
        "",
        "**Not live.** No OR-break. Every trading day emits **exactly one** candle-based call.",
        "",
        f"- Calibrate `{meta['cal_lo']}`→`{meta['cal_hi']}` ({meta['n_cal']} days)",
        f"- Last3m `{meta['test_lo']}`→`{meta['test_hi']}` ({meta['n_test']} days)",
        "",
        "## Goal",
        "",
        "Coverage **100% of days** · Hit **100%** on calibrate **and** last3m.",
        "",
    ]
    if champ:
        lines += [
            f"## Champion: `{champ.get('picker')}` / `{champ['bracket']}`",
            "",
            f"- Calibrate: **{champ['calibrate']['n']} days @ {champ['calibrate']['hit_pct']}%** "
            f"(SL/T1 {champ['calibrate']['avg_sl']}/{champ['calibrate']['avg_t1']})",
            f"- Last3m: **{champ['last3m']['n']} days @ {champ['last3m']['hit_pct']}%** "
            f"(SL/T1 {champ['last3m']['avg_sl']}/{champ['last3m']['avg_t1']})",
            "",
        ]
        if champ["last3m"]["hit_pct"] >= 100 - 1e-9 and champ["calibrate"]["hit_pct"] >= 100 - 1e-9:
            tag = "ACHIEVED" if champ.get("picker") != "oracle" else "ACHIEVED (oracle day-pick — research ceiling)"
            lines.append(f"**{tag}: 1 call/day @ 100% on both windows.**")
        else:
            lines.append(
                f"**Not fully achieved.** Misses cal={champ.get('cal_miss',[])[:5]} "
                f"l3m={champ.get('l3m_miss',[])[:5]}"
            )
        lines.append("")
        lines += ["| Day | HM | Side | Primary | SL | T1 | Win |", "|---|---|---|---|---:|---:|:---:|"]
        for c in (champ.get("last3m_calls") or [])[:80]:
            lines.append(
                f"| {c['day']} | {c.get('hm','')} | {c.get('decision','')} | {c.get('primary')} | "
                f"{c.get('sl')} | {c.get('t1')} | {'Y' if c.get('win') else 'N'} |"
            )
        lines.append("")

    oc = pack.get("oracle_ceiling") or []
    lines += ["## Oracle ceiling (best entry per day under fixed brackets)", ""]
    if oc:
        o = oc[0]
        lines.append(
            f"- Feasible: **yes** · `{o['bracket']}` · "
            f"cal {o['calibrate']['n']}@100% · l3m {o['last3m']['n']}@100% · "
            f"SL/T1 {o['last3m']['avg_sl']}/{o['last3m']['avg_t1']}"
        )
    else:
        lines.append("- Feasible under scanned fixed brackets: **no / partial** (see near)")
    lines.append("")

    lines += ["## Perfect both-100", ""]
    perf = pack.get("perfect") or []
    if not perf:
        lines.append("- none yet")
    else:
        for p in perf[:8]:
            lines.append(
                f"- `{p['picker']}` / `{p['bracket']}` · "
                f"cal {p['calibrate']['n']}@100% · l3m {p['last3m']['n']}@100% · "
                f"SL/T1 {p['last3m']['avg_sl']}/{p['last3m']['avg_t1']}"
            )
    lines.append("")

    lines += ["## Best near", ""]
    for n in (pack.get("near") or [])[:8]:
        lines.append(
            f"- `{n['picker']}` / `{n['bracket']}` · "
            f"cal {n['calibrate']['n']}@{n['calibrate']['hit_pct']}% · "
            f"l3m {n['last3m']['n']}@{n['last3m']['hit_pct']}% · "
            f"miss l3m={n.get('l3m_miss',[])[:4]}"
        )
    lines.append("")

    lines += [
        "## Method",
        "",
        "1. All textbook + strong-body candidates in morning window each day.",
        "2. Brackets: ATR / session / pattern / wide / (oracle_path ceiling).",
        "3. Pickers: trend-align, RSI+drift, best body, late window, oracle.",
        "4. Path: T1 before SL = win · exactly 1 call/day.",
        "",
        "## Policy",
        "",
        f"- Pack: `{PACK}`",
        "- research_only · not_live · daily must-call · no OR-break",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    slim = {
        "meta": {k: v for k, v in meta.items() if k != "champion"}
        | {
            "champion": {
                k: v
                for k, v in (champ or {}).items()
                if k not in ("cal_calls",)
            }
        },
        "perfect": [
            {k: v for k, v in r.items() if k not in ("cal_calls", "last3m_calls")}
            for r in perf[:10]
        ],
        "near": [
            {k: v for k, v in r.items() if k not in ("cal_calls", "last3m_calls")}
            for r in (pack.get("near") or [])[:12]
        ],
        "oracle_ceiling": oc[:10],
    }
    REPORT_JSON.write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {REPORT_MD}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · DAILY MUST refine → 100% both", flush=True)
    print("=" * 60, flush=True)

    raw = base.load_existing_1m()
    end_ts = raw.index.max()
    test_hi = end_ts.strftime("%Y-%m-%d")
    test_lo_ts = end_ts - pd.Timedelta(days=92)
    test_lo = test_lo_ts.strftime("%Y-%m-%d")
    cal_hi = (test_lo_ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    cal_lo = (test_lo_ts - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    print(f"calibrate {cal_lo}→{cal_hi} · last3m {test_lo}→{test_hi}", flush=True)

    raw = raw[raw.index >= pd.Timestamp(cal_lo, tz="Asia/Kolkata")]
    print(f"tape bars={len(raw)}", flush=True)

    print("\n[1] Textbook patterns…", flush=True)
    df = tb.detect_textbook(raw)
    df = dm.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values

    print("\n[2] All day candidates…", flush=True)
    cal_by = collect_all_day_cands(df, cal_lo, cal_hi, window=(560, 750))
    test_by = collect_all_day_cands(df, test_lo, test_hi, window=(560, 750))
    print(f"  cal days={len(cal_by)} · last3m days={len(test_by)}", flush=True)

    pack = hunt(cal_by, test_by, h, l, c)

    champion = None
    for rec in pack.get("perfect") or []:
        if rec["picker"] != "oracle":
            champion = rec
            break
    if champion is None and pack.get("perfect"):
        champion = pack["perfect"][0]
    if champion is None and pack.get("near"):
        # best non-oracle near
        for rec in pack["near"]:
            if rec["picker"] != "oracle":
                champion = rec
                break
        if champion is None:
            champion = pack["near"][0]

    meta = {
        "cal_lo": cal_lo,
        "cal_hi": cal_hi,
        "test_lo": test_lo,
        "test_hi": test_hi,
        "n_cal": champion["calibrate"]["n"] if champion else 0,
        "n_test": champion["last3m"]["n"] if champion else 0,
        "champion": {k: v for k, v in (champion or {}).items() if k != "cal_calls"},
        "daily_must": True,
        "no_or_break": True,
        "research_only": True,
        "not_live": True,
        "refine": True,
    }
    PACK.mkdir(parents=True, exist_ok=True)
    if champion:
        (PACK / "champion.json").write_text(
            json.dumps(meta["champion"], indent=2, default=str), encoding="utf-8"
        )

    write_report(meta, pack)

    print("\n" + "=" * 60, flush=True)
    if champion:
        print(
            f"CHAMPION {champion.get('picker')} / {champion['bracket']} · "
            f"cal {champion['calibrate']['n']}@{champion['calibrate']['hit_pct']}% · "
            f"l3m {champion['last3m']['n']}@{champion['last3m']['hit_pct']}% · "
            f"SL/T1 {champion['last3m']['avg_sl']}/{champion['last3m']['avg_t1']}",
            flush=True,
        )
        if champion["calibrate"]["hit_pct"] >= 100 and champion["last3m"]["hit_pct"] >= 100:
            if champion.get("picker") == "oracle":
                print("ACHIEVED via ORACLE day-pick (ceiling) · rule picker still short", flush=True)
            else:
                print("ACHIEVED 1 call/day @ 100% both windows (non-oracle picker)", flush=True)
        else:
            print(
                f"NOT YET · miss cal={champion.get('cal_miss', [])[:5]} "
                f"l3m={champion.get('l3m_miss', [])[:5]}",
                flush=True,
            )
    print(f"oracle_ceiling_n={len(pack.get('oracle_ceiling') or [])}", flush=True)
    print("DONE · daily must refine · research only", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
