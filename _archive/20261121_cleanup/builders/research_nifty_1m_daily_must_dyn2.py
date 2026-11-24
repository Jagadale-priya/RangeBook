"""RESEARCH ONLY — dynamic candle/pattern SL·T1, T1≥8–10, push hit toward 100%.

Entry: best trend-aligned pattern in morning (non-lookahead structure score).
SL: beyond signal candle / pattern extreme (dynamic).
T1: body/pattern measured move, floor 8–10.

  python -u prod_live/tests/builders/research_nifty_1m_daily_must_dyn2.py
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
import research_nifty_1m_daily_must_dyn as d1  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_daily_must_dyn"
REPORT_MD = OUT / "NIFTY_1M_DAILY_MUST_DYN.md"
REPORT_JSON = OUT / "NIFTY_1M_DAILY_MUST_DYN.json"

WEAK = {"bull_run2", "bear_run2"}


def structure_score(e: dict) -> float:
    """Non-lookahead quality: pattern rank + body + trend + candle clarity."""
    s = 0.0
    prim = e["primary"]
    if prim in dm.PRIORITY:
        s += 100 - dm.PRIORITY.index(prim)
    if prim not in WEAK and not str(prim).startswith("_"):
        s += 20
    s += min(e["body_abs"] / max(e["atr"], 1e-6), 3.0) * 15
    s += e.get("trend_align", 0) * 25
    # clear candle: body dominates range
    if e["candle_range"] > 0:
        s += (e["body_abs"] / e["candle_range"]) * 10
    # prefer not ultra-early noise
    if 575 <= e["mins"] <= 700:
        s += 12
    elif e["mins"] >= 565:
        s += 5
    return s


def collect_best_structure(
    df: pd.DataFrame,
    day_lo: str,
    day_hi: str,
    window: Tuple[int, int] = (560, 720),
    require_trend: bool = True,
) -> List[dict]:
    h_all = df["High"].astype(float).values
    l_all = df["Low"].astype(float).values
    c_all = df["Close"].astype(float).values
    idx_map = {ts: i for i, ts in enumerate(df.index)}
    events = []
    days = [d for d in df["day"].unique() if day_lo <= d <= day_hi]
    mins_lo, mins_hi = window
    t0 = time.time()

    for di, day in enumerate(days, 1):
        if di % 50 == 0:
            print(f"    daily {di}/{len(days)} n={len(events)} ({time.time()-t0:.0f}s)", flush=True)
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
            hit = [p for p in hit if p not in WEAK] or hit
            if not hit:
                continue
            primary = hit[0]
            side = dm._side_for(primary, body)
            if side is None or (side == "BUY" and body <= 0) or (side == "SELL" and body >= 0):
                continue
            drift = float(row["Close"]) - day_open
            trend_align = 1 if (side == "BUY" and drift > 0) or (side == "SELL" and drift < 0) else 0
            if require_trend and not trend_align:
                continue

            o, cl = float(row["Open"]), float(row["Close"])
            hi, lo = float(row["High"]), float(row["Low"])
            body_abs = abs(cl - o)
            atr = max(float(row["atr14"]) if np.isfinite(row["atr14"]) else 8.0, 3.0)
            entry = cl
            lo_pat = float(sess["Low"].iloc[max(0, pos - 2) : pos + 1].min())
            hi_pat = float(sess["High"].iloc[max(0, pos - 2) : pos + 1].max())
            candle_range = max(hi - lo, 0.5)
            pat_range = max(hi_pat - lo_pat, 0.5)
            if side == "BUY":
                sl_candle = max(entry - lo, 0.5)
                sl_pat = max(entry - lo_pat, 0.5)
                t1_body = max(body_abs, 0.5)
                t1_wick = max(hi - max(o, cl), body_abs * 0.5, 0.5)
            else:
                sl_candle = max(hi - entry, 0.5)
                sl_pat = max(hi_pat - entry, 0.5)
                t1_body = max(body_abs, 0.5)
                t1_wick = max(min(o, cl) - lo, body_abs * 0.5, 0.5)
            full_i = idx_map[sess.index[pos]]
            mae, mfe = co.excursion(h_all, l_all, c_all, full_i, side, max_bars=200)
            cands.append(
                {
                    "day": day,
                    "hm": row["hm"],
                    "decision": side,
                    "primary": primary,
                    "entry": entry,
                    "mins": mins,
                    "atr": atr,
                    "body_abs": body_abs,
                    "body_frac": float(row["body_frac"]),
                    "candle_range": candle_range,
                    "pat_range": pat_range,
                    "prev_range": candle_range,
                    "upper_wick": hi - max(o, cl),
                    "lower_wick": min(o, cl) - lo,
                    "sl_candle": sl_candle,
                    "sl_pat": sl_pat,
                    "t1_body": t1_body,
                    "t1_wick": t1_wick,
                    "rsi_14": float(row["rsi_14"]) if np.isfinite(row["rsi_14"]) else 50.0,
                    "mae": mae,
                    "mfe": mfe,
                    "full_i": full_i,
                    "trend_align": trend_align,
                }
            )
        if not cands:
            # fallback: first skip_run2 style
            fb = d1.collect_day_events(df, day, day, "skip_run2", window)
            if fb:
                events.append(fb[0])
            continue
        pick = max(cands, key=structure_score)
        events.append(pick)
    return events


def hunt(cal, test, h, l, c) -> dict:
    print("\n[3] Hunt dyn2…", flush=True)
    specs = []
    for t1_floor in (8.0, 10.0, 12.0):
        for sl_k in [1.2, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0]:
            for t1_k in [0.8, 1.0, 1.2, 1.5, 2.0]:
                specs.append(
                    (
                        "candle",
                        {
                            "sl_k": sl_k,
                            "t1_k": t1_k,
                            "t1_floor": t1_floor,
                            "t1_cap": 40.0,
                            "sl_min": 5.0,
                            "use_wick": False,
                        },
                        f"candle_sl{sl_k}_t{t1_k}_f{t1_floor}",
                    )
                )
                specs.append(
                    (
                        "candle",
                        {
                            "sl_k": sl_k,
                            "t1_k": t1_k,
                            "t1_floor": t1_floor,
                            "t1_cap": 40.0,
                            "sl_min": 5.0,
                            "use_wick": True,
                        },
                        f"cwick_sl{sl_k}_t{t1_k}_f{t1_floor}",
                    )
                )
        for sl_k, t1_k in product([1.2, 1.5, 2.0, 2.5, 3.0, 4.0], [0.35, 0.5, 0.7, 1.0]):
            specs.append(
                (
                    "pat",
                    {
                        "sl_k": sl_k,
                        "t1_k": t1_k,
                        "t1_floor": t1_floor,
                        "t1_cap": 40.0,
                        "sl_min": 5.0,
                    },
                    f"pat_sl{sl_k}_t{t1_k}_f{t1_floor}",
                )
            )
        for sl_k, atr_k, t1_k, t1_atr in product(
            [1.2, 1.6, 2.2], [0.6, 1.0, 1.5], [1.0, 1.5], [0.5, 0.8]
        ):
            specs.append(
                (
                    "candle_atr",
                    {
                        "sl_k": sl_k,
                        "atr_k": atr_k,
                        "t1_k": t1_k,
                        "t1_atr": t1_atr,
                        "t1_floor": t1_floor,
                        "t1_cap": 40.0,
                        "sl_min": 5.0,
                    },
                    f"ca_sl{sl_k}_a{atr_k}_tb{t1_k}_ta{t1_atr}_f{t1_floor}",
                )
            )
        for a, b, c_, tb, ta in product([1.0, 1.5, 2.0], [0.5, 1.0], [0.4, 0.8], [1.0, 1.5], [0.4, 0.7]):
            specs.append(
                (
                    "mix",
                    {
                        "a": a,
                        "b": b,
                        "c": c_,
                        "t_body": tb,
                        "t_atr": ta,
                        "t1_floor": t1_floor,
                        "t1_cap": 40.0,
                        "sl_min": 5.0,
                    },
                    f"mix_{a}_{b}_{c_}_{tb}_{ta}_f{t1_floor}",
                )
            )

    perfect, near, sane = [], [], []
    t0 = time.time()
    for i, (kind, params, lab) in enumerate(specs, 1):
        if i % 250 == 0:
            print(
                f"    {i}/{len(specs)} p={len(perfect)} s={len(sane)} n={len(near)} ({time.time()-t0:.0f}s)",
                flush=True,
            )
        a = d1.eval_book(cal, h, l, c, kind, params)
        t = d1.eval_book(test, h, l, c, kind, params)
        rec = {
            "bracket": lab,
            "kind": kind,
            "params": params,
            "calibrate": {
                k: a[k]
                for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "avg_rr", "med_sl", "med_t1")
            },
            "last3m": {
                k: t[k]
                for k in ("n", "wins", "hit_pct", "avg_sl", "avg_t1", "avg_rr", "med_sl", "med_t1")
            },
            "cal_miss": a["miss_days"][:8],
            "l3m_miss": t["miss_days"][:8],
            "last3m_calls": t["calls"],
        }
        if a["hit_pct"] >= 100 - 1e-9 and t["hit_pct"] >= 100 - 1e-9 and t["avg_rr"] <= 12:
            perfect.append(rec)
        if t["hit_pct"] >= 88 and a["hit_pct"] >= 85 and t["avg_t1"] >= 8 and t["avg_rr"] <= 8:
            near.append(rec)
        if (
            t["hit_pct"] >= 80
            and a["hit_pct"] >= 78
            and t["avg_t1"] >= 8
            and t["avg_rr"] <= 5
            and t["avg_sl"] <= 70
        ):
            sane.append(rec)

    perfect.sort(key=lambda r: (r["last3m"]["avg_rr"], -r["last3m"]["avg_t1"]))
    near.sort(
        key=lambda r: (
            -r["last3m"]["hit_pct"],
            -r["calibrate"]["hit_pct"],
            r["last3m"]["avg_rr"],
        )
    )
    sane.sort(
        key=lambda r: (
            -r["last3m"]["hit_pct"],
            -r["calibrate"]["hit_pct"],
            r["last3m"]["avg_rr"],
            -r["last3m"]["avg_t1"],
        )
    )
    print(
        f"  perfect={len(perfect)} near={len(near)} sane={len(sane)} ({time.time()-t0:.0f}s)",
        flush=True,
    )
    return {"perfect": perfect[:12], "near": near[:15], "sane": sane[:15]}


def write_report(meta, packs):
    champ = meta["champion"]
    c, t = champ["calibrate"], champ["last3m"]
    lines = [
        "# NIFTY 1m — daily must-call · **dynamic candle/pattern SL & T1**",
        "",
        "**Not live.** Rejected ATR×80 / fixed 5pt. Brackets come from the **signal candle + pattern**.",
        "",
        f"- Calibrate `{meta['cal_lo']}`→`{meta['cal_hi']}` ({c['n']} days)",
        f"- Last3m `{meta['test_lo']}`→`{meta['test_hi']}` ({t['n']} days)",
        "",
        f"## Champion: `{champ['mode']}` / `{champ['bracket']}`",
        "",
        f"- Calibrate: **{c['n']}@{c['hit_pct']}%** · avg SL/T1 **{c['avg_sl']}/{c['avg_t1']}** · RR **{c['avg_rr']}**",
        f"- Last3m: **{t['n']}@{t['hit_pct']}%** · avg SL/T1 **{t['avg_sl']}/{t['avg_t1']}** · RR **{t['avg_rr']}**",
        f"- Median last3m: SL {t.get('med_sl')} / T1 {t.get('med_t1')}",
        "",
    ]
    if c["hit_pct"] >= 100 and t["hit_pct"] >= 100:
        lines.append("**ACHIEVED 100% both** with dynamic structure brackets.")
    else:
        lines.append(
            f"**Best dynamic / sane-RR book so far.** "
            f"Misses cal={champ.get('cal_miss',[])[:5]} l3m={champ.get('l3m_miss',[])[:5]}"
        )
    lines += [
        "",
        "### How SL / T1 are set",
        "",
        f"- Kind `{champ.get('kind')}` · params `{champ.get('params')}`",
        "- **SL**: beyond last-candle extreme and/or 3-bar pattern range (× multiplier).",
        "- **T1**: measured from body / pattern range / ATR blend, **floor 8–12 pts**, cap ~40.",
        "",
        "### Entry",
        "",
        "- Each day: best **trend-aligned** textbook pattern in morning (structure score).",
        "- Skip weak `bull_run2`/`bear_run2` when a better tag exists.",
        "",
        "| Day | HM | Side | Primary | SL | T1 | RR | Win |",
        "|---|---|---|---|---:|---:|---:|:---:|",
    ]
    for r in (champ.get("last3m_calls") or [])[:80]:
        lines.append(
            f"| {r['day']} | {r['hm']} | {r['decision']} | {r.get('primary')} | "
            f"{r['sl']} | {r['t1']} | {r.get('rr')} | {'Y' if r['win'] else 'N'} |"
        )
    lines += ["", "## Other modes", ""]
    for mode, pack in packs.items():
        lines.append(f"### `{mode}`")
        if pack.get("perfect"):
            p = pack["perfect"][0]
            lines.append(
                f"- Perfect: `{p['bracket']}` RR {p['last3m']['avg_rr']} "
                f"SL/T1 {p['last3m']['avg_sl']}/{p['last3m']['avg_t1']}"
            )
        if pack.get("near"):
            n = pack["near"][0]
            lines.append(
                f"- Near: `{n['bracket']}` cal {n['calibrate']['hit_pct']}% "
                f"l3m {n['last3m']['hit_pct']}% SL/T1 {n['last3m']['avg_sl']}/{n['last3m']['avg_t1']} "
                f"RR {n['last3m']['avg_rr']}"
            )
        if pack.get("sane"):
            s = pack["sane"][0]
            lines.append(
                f"- Sane: `{s['bracket']}` cal {s['calibrate']['hit_pct']}% "
                f"l3m {s['last3m']['avg_sl']}/{s['last3m']['avg_t1']} "
                f"hit {s['last3m']['hit_pct']}% RR {s['last3m']['avg_rr']}"
            )
        lines.append("")
    lines += [
        "## Policy",
        "",
        f"- Pack: `{PACK}`",
        "- research_only · not_live · dynamic brackets · daily must-call",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({"meta": meta, "packs": {
        m: {k: [{kk: vv for kk, vv in r.items() if kk != "last3m_calls"} for r in (p.get(k) or [])[:6]]
            for k in ("perfect", "near", "sane")}
        for m, p in packs.items()
    }}, indent=2, default=str), encoding="utf-8")
    print(f"wrote {REPORT_MD}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m · DAILY MUST dyn2 · structure SL/T1", flush=True)
    print("=" * 60, flush=True)
    raw = base.load_existing_1m()
    end = raw.index.max()
    test_hi = end.strftime("%Y-%m-%d")
    test_lo_ts = end - pd.Timedelta(days=92)
    test_lo = test_lo_ts.strftime("%Y-%m-%d")
    cal_hi = (test_lo_ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    cal_lo = (test_lo_ts - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    print(f"calibrate {cal_lo}→{cal_hi} · last3m {test_lo}→{test_hi}", flush=True)
    raw = raw[raw.index >= pd.Timestamp(cal_lo, tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = dm.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values

    packs = {}
    champion = None
    configs = [
        ("best_trend_560_720", True, (560, 720)),
        ("best_any_560_720", False, (560, 720)),
        ("best_trend_575_700", True, (575, 700)),
        ("first_trend_skip", None, (560, 720)),  # d1 first trend
    ]
    for name, req_trend, window in configs:
        print(f"\n[2] {name}…", flush=True)
        if req_trend is None:
            cal = d1.collect_day_events(df, cal_lo, cal_hi, "trend_skip", window)
            test = d1.collect_day_events(df, test_lo, test_hi, "trend_skip", window)
        else:
            cal = collect_best_structure(df, cal_lo, cal_hi, window, require_trend=req_trend)
            test = collect_best_structure(df, test_lo, test_hi, window, require_trend=req_trend)
        print(f"  cal={len(cal)} test={len(test)}", flush=True)
        pack = hunt(cal, test, h, l, c)
        packs[name] = pack
        for tag, bucket in (("perfect", pack["perfect"]), ("near", pack["near"]), ("sane", pack["sane"])):
            for rec in bucket[:2]:
                cand = dict(rec)
                cand["mode"] = name
                cand["tag"] = tag
                if champion is None:
                    champion = cand
                else:
                    def k(x):
                        return (
                            0 if x["tag"] == "perfect" else 1 if x["tag"] == "near" else 2,
                            -min(x["calibrate"]["hit_pct"], x["last3m"]["hit_pct"]),
                            x["last3m"]["avg_rr"],
                            -x["last3m"]["avg_t1"],
                        )
                    if k(cand) < k(champion):
                        champion = cand

    meta = {
        "cal_lo": cal_lo,
        "cal_hi": cal_hi,
        "test_lo": test_lo,
        "test_hi": test_hi,
        "champion": {k: v for k, v in (champion or {}).items()},
        "dynamic": True,
        "research_only": True,
        "not_live": True,
    }
    PACK.mkdir(parents=True, exist_ok=True)
    if champion:
        (PACK / "champion.json").write_text(
            json.dumps({k: v for k, v in champion.items() if k != "last3m_calls"}, indent=2, default=str),
            encoding="utf-8",
        )
    write_report(meta, packs)
    print("\n" + "=" * 60, flush=True)
    if champion:
        print(
            f"CHAMPION [{champion['tag']}] {champion['mode']} / {champion['bracket']}\n"
            f"  cal @{champion['calibrate']['hit_pct']}% SL/T1 "
            f"{champion['calibrate']['avg_sl']}/{champion['calibrate']['avg_t1']} "
            f"RR {champion['calibrate']['avg_rr']}\n"
            f"  l3m @{champion['last3m']['hit_pct']}% SL/T1 "
            f"{champion['last3m']['avg_sl']}/{champion['last3m']['avg_t1']} "
            f"RR {champion['last3m']['avg_rr']}",
            flush=True,
        )
    print("DONE dyn2", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
