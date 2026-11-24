"""RESEARCH ONLY — Scalp 100%: T1 = 10/20 pts, SL = previous-candle extreme.

User logic: if target is hit first every time, stop is only structure insurance.
SL = prior bar low (BUY) / prior bar high (SELL) — tight, chart-based.
Also test: signal-candle extreme, 2-bar swing.

Goal: max calls @ 100% both windows (calibrate + last3m).

  python -u prod_live/tests/builders/research_nifty_1m_scalp_prevcandle_100.py
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import defaultdict
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
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_prevcandle_100"
REPORT_MD = OUT / "NIFTY_1M_SCALP_PREVCANDLE_100.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_PREVCANDLE_100.json"


def side_for(primary: str, body: float) -> Optional[str]:
    if primary in tb.BULLISH:
        return "BUY"
    if primary in tb.BEARISH:
        return "SELL"
    return None


def collect_scalp_events(df: pd.DataFrame, day_lo: str, day_hi: str) -> List[dict]:
    """Pattern completions with prev-candle / structure SL distances + path."""
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(df.index)}
    events = []
    days = [d for d in df["day"].unique() if day_lo <= d <= day_hi]
    t0 = time.time()

    for di, day in enumerate(days, 1):
        if di % 50 == 0:
            print(f"    events {di}/{len(days)} n={len(events)} ({time.time()-t0:.0f}s)", flush=True)
        sess = df[df["day"] == day]
        if len(sess) < 40:
            continue
        day_open = float(sess["Open"].iloc[0])
        for pos in range(5, len(sess)):
            row = sess.iloc[pos]
            mins = int(row["mins"])
            if mins < 560 or mins > 900:
                continue
            body = float(row["Close"]) - float(row["Open"])
            hits = [p for p in dm.PRIORITY if p in row.index and int(row[p]) == 1]
            if not hits:
                continue
            primary = hits[0]
            side = side_for(primary, body)
            if side is None:
                continue
            if side == "BUY" and body <= 0:
                continue
            if side == "SELL" and body >= 0:
                continue

            entry = float(row["Close"])
            hi, lo = float(row["High"]), float(row["Low"])
            prev = sess.iloc[pos - 1]
            prev2 = sess.iloc[pos - 2]
            prev_hi, prev_lo = float(prev["High"]), float(prev["Low"])
            p2_hi = max(prev_hi, float(prev2["High"]))
            p2_lo = min(prev_lo, float(prev2["Low"]))

            if side == "BUY":
                sl_prev = entry - prev_lo  # previous candle low
                sl_sig = entry - lo  # signal candle low
                sl_swing2 = entry - p2_lo
            else:
                sl_prev = prev_hi - entry
                sl_sig = hi - entry
                sl_swing2 = p2_hi - entry

            # invalid / too wide structural stops skipped later
            atr = max(float(row["atr14"]) if np.isfinite(row["atr14"]) else 8.0, 3.0)
            full_i = idx_map[sess.index[pos]]
            mae, mfe = co.excursion(h, l, c, full_i, side, max_bars=120)

            # path outcomes for each SL style × T1
            outcomes = {}
            for sl_name, sl_pts in (
                ("prev", sl_prev),
                ("sig", sl_sig),
                ("swing2", sl_swing2),
            ):
                for t1 in (10.0, 20.0, 15.0, 12.0, 8.0):
                    # path_hit needs sl,t1 >= 4; tiny structure SL → skip
                    if sl_pts < 4.0:
                        outcomes[f"{sl_name}_t{int(t1)}"] = "bad_sl"
                        continue
                    win, out = co.path_hit(h, l, c, full_i, side, float(sl_pts), t1)
                    outcomes[f"{sl_name}_t{int(t1)}"] = "win" if (win and out == "t1") else out

            drift = entry - day_open
            align = 1 if (side == "BUY" and drift > 0) or (side == "SELL" and drift < 0) else 0
            # pre 5-bar regime
            look = sess.iloc[max(0, pos - 5) : pos]
            pre_chg = float(look["Close"].iloc[-1] - look["Open"].iloc[0]) if len(look) else 0.0
            if side == "BUY":
                regime = "continuation" if pre_chg > 3 else ("reversal" if pre_chg < -3 else "balanced")
            else:
                regime = "continuation" if pre_chg < -3 else ("reversal" if pre_chg > 3 else "balanced")

            events.append(
                {
                    "day": day,
                    "hm": row["hm"],
                    "mins": mins,
                    "clock": co.clock_bucket(mins),
                    "decision": side,
                    "primary": primary,
                    "entry": entry,
                    "atr": atr,
                    "body_abs": abs(body),
                    "body_frac": float(row["body_frac"]),
                    "candle_range": max(hi - lo, 0.5),
                    "sl_prev": float(sl_prev),
                    "sl_sig": float(sl_sig),
                    "sl_swing2": float(sl_swing2),
                    "mae": mae,
                    "mfe": mfe,
                    "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
                    "align_session": align,
                    "pre_regime": regime,
                    "pre_chg_5": pre_chg,
                    "full_i": full_i,
                    **outcomes,
                }
            )
    return events


def slice_ev(events: List[dict], spec: dict) -> List[dict]:
    out = []
    for e in events:
        if spec.get("primaries") and e["primary"] not in spec["primaries"]:
            continue
        if spec.get("side") and e["decision"] != spec["side"]:
            continue
        if spec.get("regime") and e["pre_regime"] != spec["regime"]:
            continue
        if spec.get("align") is not None and e["align_session"] != spec["align"]:
            continue
        if spec.get("clocks") and e["clock"] not in spec["clocks"]:
            continue
        if spec.get("min_body") is not None and e["body_frac"] < spec["min_body"]:
            continue
        if spec.get("max_sl_prev") is not None and e["sl_prev"] > spec["max_sl_prev"]:
            continue
        if spec.get("max_sl_sig") is not None and e["sl_sig"] > spec["max_sl_sig"]:
            continue
        if spec.get("rsi_lo") is not None and e["rsi_14"] < spec["rsi_lo"]:
            continue
        if spec.get("rsi_hi") is not None and e["rsi_14"] > spec["rsi_hi"]:
            continue
        if spec.get("min_mfe") is not None and e["mfe"] < spec["min_mfe"]:
            continue  # analysis only — never use for live filter
        out.append(e)
    return out


def eval_book(events: List[dict], sl_style: str, t1: float, day_unique: bool = True) -> dict:
    key = f"{sl_style}_t{int(t1)}"
    rows = []
    used = set()
    sl_field = {"prev": "sl_prev", "sig": "sl_sig", "swing2": "sl_swing2"}[sl_style]
    for e in sorted(events, key=lambda x: (x["day"], x["mins"])):
        if day_unique and e["day"] in used:
            continue
        outcome = e.get(key, "missing")
        if outcome == "bad_sl":
            continue
        sl = e[sl_field]
        win = outcome == "win"
        rows.append(
            {
                "day": e["day"],
                "hm": e["hm"],
                "decision": e["decision"],
                "primary": e["primary"],
                "entry": e["entry"],
                "sl": round(sl, 2),
                "t1": t1,
                "rr": round(sl / t1, 2) if t1 else 0,
                "win": win,
                "outcome": outcome,
                "sl_style": sl_style,
                "mae": round(e["mae"], 2),
                "mfe": round(e["mfe"], 2),
            }
        )
        if day_unique:
            used.add(e["day"])
    n = len(rows)
    wins = sum(1 for r in rows if r["win"])
    sls = [r["sl"] for r in rows]
    return {
        "n": n,
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else 0.0,
        "avg_sl": round(float(np.mean(sls)), 2) if sls else 0,
        "med_sl": round(float(np.median(sls)), 2) if sls else 0,
        "max_sl": round(float(np.max(sls)), 2) if sls else 0,
        "avg_t1": t1,
        "avg_rr": round(float(np.mean([r["rr"] for r in rows])), 2) if rows else 0,
        "miss_days": [r["day"] for r in rows if not r["win"]],
        "calls": rows,
    }


def eval_multi(events: List[dict], sl_style: str, t1: float, gap: int = 15) -> dict:
    key = f"{sl_style}_t{int(t1)}"
    sl_field = {"prev": "sl_prev", "sig": "sl_sig", "swing2": "sl_swing2"}[sl_style]
    rows = []
    last = {}
    for e in sorted(events, key=lambda x: (x["day"], x["mins"])):
        if e.get(key) == "bad_sl":
            continue
        prev = last.get(e["day"])
        if prev is not None and e["mins"] - prev < gap:
            continue
        win = e.get(key) == "win"
        sl = e[sl_field]
        rows.append(
            {
                "day": e["day"],
                "hm": e["hm"],
                "decision": e["decision"],
                "primary": e["primary"],
                "entry": e["entry"],
                "sl": round(sl, 2),
                "t1": t1,
                "rr": round(sl / t1, 2),
                "win": win,
                "outcome": e.get(key),
            }
        )
        last[e["day"]] = e["mins"]
    n = len(rows)
    wins = sum(1 for r in rows if r["win"])
    return {
        "n": n,
        "n_days": len({r["day"] for r in rows}),
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else 0.0,
        "avg_sl": round(float(np.mean([r["sl"] for r in rows])), 2) if rows else 0,
        "med_sl": round(float(np.median([r["sl"] for r in rows])), 2) if rows else 0,
        "max_sl": round(float(np.max([r["sl"] for r in rows])), 2) if rows else 0,
        "avg_t1": t1,
        "miss_days": sorted({r["day"] for r in rows if not r["win"]}),
        "calls": rows,
    }


def behavior_by_pattern(events: List[dict], sl_style: str = "prev", t1: float = 10.0) -> List[dict]:
    key = f"{sl_style}_t{int(t1)}"
    by = defaultdict(list)
    for e in events:
        if e.get(key) == "bad_sl":
            continue
        by[e["primary"]].append(e)
    rows = []
    for pat, xs in by.items():
        if len(xs) < 15:
            continue
        wins = sum(1 for e in xs if e.get(key) == "win")
        # clean continuation subset
        clean = [
            e
            for e in xs
            if e["pre_regime"] == "continuation"
            and e["align_session"] == 1
            and e["body_frac"] >= 0.45
            and e["sl_prev"] <= 25
        ]
        cw = sum(1 for e in clean if e.get(key) == "win")
        rows.append(
            {
                "pattern": pat,
                "n": len(xs),
                "hit_pct": round(100.0 * wins / len(xs), 1),
                "avg_sl_prev": round(float(np.mean([e["sl_prev"] for e in xs])), 2),
                "med_sl_prev": round(float(np.median([e["sl_prev"] for e in xs])), 2),
                "avg_mfe": round(float(np.mean([e["mfe"] for e in xs])), 2),
                "clean_n": len(clean),
                "clean_hit": round(100.0 * cw / len(clean), 1) if clean else 0.0,
            }
        )
    rows.sort(key=lambda r: (-r["clean_hit"], -r["hit_pct"], -r["n"]))
    return rows


def hunt(cal, test) -> dict:
    print("\n[B] Hunt 100% scalp books (prev-candle SL)…", flush=True)
    families = [
        ["morning_star", "evening_star"],
        ["morning_star", "evening_star", "morning_doji_star", "evening_doji_star"],
        ["hanging_man", "shooting_star"],
        ["hanging_man", "shooting_star", "hammer", "inv_hammer"],
        ["bear_engulf", "bull_engulf"],
        ["bear_engulf", "bull_engulf", "dark_cloud", "piercing"],
        ["three_outside_dn", "three_outside_up"],
        ["three_crows", "three_soldiers"],
        ["falling_3_methods", "rising_3_methods"],
        ["marubozu_bear", "marubozu_bull", "belt_bear", "belt_bull"],
        ["bear_kicker", "bull_kicker"],
        # top singles expanded later from behavior
    ]
    # add single-pattern micros for high clean patterns
    singles = [
        "evening_star",
        "morning_star",
        "hanging_man",
        "shooting_star",
        "three_crows",
        "falling_3_methods",
        "bear_engulf",
        "three_outside_dn",
        "marubozu_bear",
        "belt_bear",
    ]
    for p in singles:
        families.append([p])

    perfect_day, perfect_multi, near = [], [], []
    t0 = time.time()
    n = 0
    for pats, regime, align, min_body, max_sl, clocks, rsi, side in product(
        families,
        ["continuation", None],
        [1, None],
        [0.45, 0.55, None],
        [15.0, 20.0, 25.0],
        [None, ["early"], ["early", "morning"]],
        [(None, None), (20, 55), (40, 80)],
        [None, "SELL"],
    ):
        if side == "SELL" and all(p in tb.BULLISH for p in pats):
            continue
        base_spec = {
            "primaries": pats,
            "regime": regime,
            "align": align,
            "min_body": min_body,
            "clocks": clocks,
            "rsi_lo": rsi[0],
            "rsi_hi": rsi[1],
            "side": side,
            "max_sl_prev": max_sl,
        }
        cal_base = slice_ev(cal, base_spec)
        test_base = slice_ev(test, base_spec)
        if len(cal_base) < 5 or len(test_base) < 3:
            continue

        for sl_style, t1 in product(["prev", "sig", "swing2"], [10.0, 20.0, 15.0]):
            # re-slice with sig max if needed
            if sl_style == "sig":
                spec = dict(base_spec)
                spec.pop("max_sl_prev", None)
                spec["max_sl_sig"] = max_sl
                cal_s = slice_ev(cal, spec)
                test_s = slice_ev(test, spec)
            else:
                spec = dict(base_spec)
                cal_s, test_s = cal_base, test_base
            if len(cal_s) < 5 or len(test_s) < 3:
                continue
            n += 1
            if n % 3000 == 0:
                print(
                    f"    {n} p_day={len(perfect_day)} p_multi={len(perfect_multi)} ({time.time()-t0:.0f}s)",
                    flush=True,
                )

            a = eval_book(cal_s, sl_style, t1, day_unique=True)
            t = eval_book(test_s, sl_style, t1, day_unique=True)
            if a["n"] < 4 or t["n"] < 2:
                continue
            filt = {k: v for k, v in spec.items() if v is not None}
            filt["sl_style"] = sl_style
            rec = {
                "mode": "day_unique",
                "sl_style": sl_style,
                "t1": t1,
                "filter": filt,
                "calibrate": {
                    k: a[k]
                    for k in ("n", "wins", "hit_pct", "avg_sl", "med_sl", "max_sl", "avg_t1", "avg_rr")
                },
                "last3m": {
                    k: t[k]
                    for k in ("n", "wins", "hit_pct", "avg_sl", "med_sl", "max_sl", "avg_t1", "avg_rr")
                },
                "cal_miss": a["miss_days"][:6],
                "l3m_miss": t["miss_days"][:6],
                "last3m_calls": t["calls"],
                "cal_calls": a["calls"],
            }
            if a["hit_pct"] >= 100 - 1e-9 and t["hit_pct"] >= 100 - 1e-9:
                perfect_day.append(rec)
            elif t["hit_pct"] >= 90 and a["hit_pct"] >= 85 and t["n"] >= 4:
                near.append(rec)

            am = eval_multi(cal_s, sl_style, t1, gap=15)
            tm = eval_multi(test_s, sl_style, t1, gap=15)
            if am["n"] >= 5 and tm["n"] >= 3:
                recm = {
                    "mode": "multi",
                    "sl_style": sl_style,
                    "t1": t1,
                    "filter": filt,
                    "calibrate": {
                        k: am[k]
                        for k in ("n", "n_days", "wins", "hit_pct", "avg_sl", "med_sl", "max_sl", "avg_t1")
                    },
                    "last3m": {
                        k: tm[k]
                        for k in ("n", "n_days", "wins", "hit_pct", "avg_sl", "med_sl", "max_sl", "avg_t1")
                    },
                    "cal_miss": am["miss_days"][:6],
                    "l3m_miss": tm["miss_days"][:6],
                    "last3m_calls": tm["calls"],
                }
                if am["hit_pct"] >= 100 - 1e-9 and tm["hit_pct"] >= 100 - 1e-9:
                    perfect_multi.append(recm)
                elif tm["hit_pct"] >= 90 and am["hit_pct"] >= 85 and tm["n"] >= 5:
                    near.append(recm)

    def rank(r):
        return (
            -r["last3m"]["n"],
            -r["calibrate"]["n"],
            r["last3m"]["avg_sl"],
            -r["t1"],
        )

    perfect_day.sort(key=rank)
    perfect_multi.sort(key=rank)
    near.sort(key=lambda r: (-r["last3m"]["hit_pct"], -r["last3m"]["n"], -r["calibrate"]["hit_pct"]))
    print(
        f"  specs~{n} perfect_day={len(perfect_day)} perfect_multi={len(perfect_multi)} "
        f"near={len(near)} ({time.time()-t0:.0f}s)",
        flush=True,
    )
    return {
        "perfect_day": perfect_day[:30],
        "perfect_multi": perfect_multi[:30],
        "near": near[:25],
    }


def write_report(meta, behavior, hunt):
    champ = meta.get("champion")
    lines = [
        "# NIFTY 1m — **scalp 100%** · T1 10/20 · SL = previous candle",
        "",
        "**Not live.** Scalping research: fixed target **10 or 20 pts**. "
        "Stop = **previous candle low/high** (or signal-candle / 2-bar swing). "
        "If T1 always prints first, SL is only structure insurance.",
        "",
        f"- Calibrate `{meta['cal_lo']}`→`{meta['cal_hi']}`",
        f"- Last3m `{meta['test_lo']}`→`{meta['test_hi']}`",
        f"- Events: cal **{meta['n_cal']}** · last3m **{meta['n_test']}**",
        "",
        "## Exit rules tested",
        "",
        "| Style | Stop definition |",
        "|---|---|",
        "| `prev` | BUY: prior bar **low** · SELL: prior bar **high** |",
        "| `sig` | Signal candle extreme (own low/high) |",
        "| `swing2` | 2-bar swing extreme |",
        "",
        "Target: **8 / 10 / 12 / 15 / 20** points.",
        "",
        "## Pattern behavior (prev-candle SL · T1=10)",
        "",
        "| Pattern | N | Hit% | Med SL | Clean N | Clean Hit% |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in behavior[:20]:
        lines.append(
            f"| {r['pattern']} | {r['n']} | {r['hit_pct']} | {r['med_sl_prev']} | "
            f"{r['clean_n']} | {r['clean_hit']} |"
        )

    lines += ["", "## Champion 100% book", ""]
    if champ:
        c, t = champ["calibrate"], champ["last3m"]
        lines += [
            f"### `{champ['mode']}` · SL=`{champ['sl_style']}` · T1={champ['t1']}",
            "",
            f"- Filter: `{champ.get('filter')}`",
            f"- Calibrate: **{c['n']} @ {c['hit_pct']}%** · avg/med SL {c['avg_sl']}/{c.get('med_sl')} · maxSL {c.get('max_sl')}",
            f"- Last3m: **{t['n']} @ {t['hit_pct']}%** · avg/med SL {t['avg_sl']}/{t.get('med_sl')} · maxSL {t.get('max_sl')}",
            "",
        ]
        if c["hit_pct"] >= 100 and t["hit_pct"] >= 100:
            lines.append("**ACHIEVED 100% both windows** — target hit before structural stop.")
        lines += [
            "",
            "| Day | HM | Side | Primary | SL | T1 | RR | Win |",
            "|---|---|---|---|---:|---:|---:|:---:|",
        ]
        for r in (champ.get("last3m_calls") or [])[:60]:
            lines.append(
                f"| {r['day']} | {r['hm']} | {r['decision']} | {r.get('primary')} | "
                f"{r['sl']} | {r['t1']} | {r.get('rr')} | {'Y' if r['win'] else 'N'} |"
            )

    lines += ["", "### Perfect day-unique", ""]
    for p in (hunt.get("perfect_day") or [])[:10]:
        lines.append(
            f"- SL `{p['sl_style']}` T1={p['t1']} · cal {p['calibrate']['n']}@100% · "
            f"l3m {p['last3m']['n']}@100% · medSL {p['last3m'].get('med_sl')} · `{p['filter']}`"
        )
    lines += ["", "### Perfect multi-call", ""]
    for p in (hunt.get("perfect_multi") or [])[:10]:
        lines.append(
            f"- SL `{p['sl_style']}` T1={p['t1']} · cal {p['calibrate']['n']}c/"
            f"{p['calibrate'].get('n_days')}d @100% · l3m {p['last3m']['n']}c/"
            f"{p['last3m'].get('n_days')}d @100% · medSL {p['last3m'].get('med_sl')} · `{p['filter']}`"
        )
    if not hunt.get("perfect_multi"):
        lines.append("- none")
    lines += ["", "### Near", ""]
    for n in (hunt.get("near") or [])[:8]:
        lines.append(
            f"- `{n['mode']}` SL `{n['sl_style']}` T1={n['t1']} · "
            f"cal {n['calibrate']['n']}@{n['calibrate']['hit_pct']}% · "
            f"l3m {n['last3m']['n']}@{n['last3m']['hit_pct']}% · `{n['filter']}`"
        )
    lines += [
        "",
        "## Policy",
        "",
        f"- Pack: `{PACK}`",
        "- research_only · not_live · scalp · prev-candle SL · T1 10/20",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "meta": {k: v for k, v in meta.items() if k != "champion"},
                "champion": {k: v for k, v in (champ or {}).items() if k != "cal_calls"},
                "behavior": behavior[:25],
                "perfect_day": [
                    {k: v for k, v in r.items() if k not in ("last3m_calls", "cal_calls")}
                    for r in (hunt.get("perfect_day") or [])[:15]
                ],
                "perfect_multi": [
                    {k: v for k, v in r.items() if k not in ("last3m_calls", "cal_calls")}
                    for r in (hunt.get("perfect_multi") or [])[:15]
                ],
                "near": [
                    {k: v for k, v in r.items() if k not in ("last3m_calls", "cal_calls")}
                    for r in (hunt.get("near") or [])[:12]
                ],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT_MD}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · SCALP 100% · prev-candle SL · T1 10/20", flush=True)
    print("=" * 60, flush=True)

    raw = base.load_existing_1m()
    end = raw.index.max()
    test_hi = end.strftime("%Y-%m-%d")
    test_lo_ts = end - pd.Timedelta(days=92)
    test_lo = test_lo_ts.strftime("%Y-%m-%d")
    cal_hi = (test_lo_ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    cal_lo = (test_lo_ts - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    print(f"calibrate {cal_lo}→{cal_hi} · last3m {test_lo}→{test_hi}", flush=True)

    PACK.mkdir(parents=True, exist_ok=True)
    cache = PACK / f"scalp_events_{cal_lo}_{test_hi}.pkl"
    if cache.exists():
        print(f"  load {cache.name}", flush=True)
        blob = pickle.load(cache.open("rb"))
        cal, test = blob["cal"], blob["test"]
    else:
        raw = raw[raw.index >= pd.Timestamp(cal_lo, tz="Asia/Kolkata")]
        print("\n[A1] Patterns…", flush=True)
        df = tb.detect_textbook(raw)
        df = beh.add_rsi(df)
        print("\n[A2] Scalp events (prev-candle SL paths)…", flush=True)
        cal = collect_scalp_events(df, cal_lo, cal_hi)
        test = collect_scalp_events(df, test_lo, test_hi)
        pickle.dump({"cal": cal, "test": test}, cache.open("wb"), protocol=pickle.HIGHEST_PROTOCOL)
        print(f"  wrote {cache.name}", flush=True)

    print(f"  events cal={len(cal)} · last3m={len(test)}", flush=True)

    print("\n[A3] Behavior leaderboard (prev · T1=10)…", flush=True)
    behavior = behavior_by_pattern(cal, "prev", 10.0)
    for r in behavior[:8]:
        print(
            f"  {r['pattern']}: hit={r['hit_pct']}% clean={r['clean_n']}@{r['clean_hit']}% "
            f"medSL={r['med_sl_prev']}",
            flush=True,
        )

    hunt_res = hunt(cal, test)

    champion = None
    for bucket in ("perfect_multi", "perfect_day"):
        for rec in hunt_res.get(bucket) or []:
            if champion is None:
                champion = rec
            else:
                # prefer more calls, then lower avg SL, then higher T1
                def key(r):
                    return (
                        -r["last3m"]["n"],
                        -r["calibrate"]["n"],
                        r["last3m"]["avg_sl"],
                        -r["t1"],
                    )

                if key(rec) < key(champion):
                    champion = rec
    if champion is None and hunt_res.get("near"):
        champion = hunt_res["near"][0]

    meta = {
        "cal_lo": cal_lo,
        "cal_hi": cal_hi,
        "test_lo": test_lo,
        "test_hi": test_hi,
        "n_cal": len(cal),
        "n_test": len(test),
        "champion": champion,
        "research_only": True,
        "not_live": True,
        "scalp": True,
        "sl_rule": "previous_candle_extreme",
    }
    write_report(meta, behavior, hunt_res)
    if champion:
        (PACK / "champion.json").write_text(
            json.dumps({k: v for k, v in champion.items() if k not in ("cal_calls",)}, indent=2, default=str),
            encoding="utf-8",
        )

    print("\n" + "=" * 60, flush=True)
    if champion:
        print(
            f"CHAMPION {champion['mode']} SL={champion['sl_style']} T1={champion['t1']} · "
            f"cal {champion['calibrate']['n']}@{champion['calibrate']['hit_pct']}% · "
            f"l3m {champion['last3m']['n']}@{champion['last3m']['hit_pct']}% · "
            f"avgSL {champion['last3m']['avg_sl']} medSL {champion['last3m'].get('med_sl')}",
            flush=True,
        )
        print(f"  filter={champion.get('filter')}", flush=True)
        if champion["calibrate"]["hit_pct"] >= 100 and champion["last3m"]["hit_pct"] >= 100:
            print("ACHIEVED 100% both · target before prev-candle stop", flush=True)
    print(
        f"perfect_day={len(hunt_res.get('perfect_day') or [])} "
        f"perfect_multi={len(hunt_res.get('perfect_multi') or [])}",
        flush=True,
    )
    print("DONE · scalp prev-candle 100%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
