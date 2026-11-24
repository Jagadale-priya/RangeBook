"""RESEARCH ONLY — Forward-check held scalp logics 2026-11-09 → today; lock T15/T20.

1) Download fresh NIFTY 1m (after local end 2026-11-06)
2) Rebuild held micros on train windows only (no fwd leakage)
3) Score PATH@100% books on fwd window
4) Write HELD lock report

  python -u prod_live/tests/builders/research_nifty_1m_scalp_fwd_nov9_hold.py
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_chart_only_100 as co  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_fwd_nov9_hold"
REPORT_MD = OUT / "NIFTY_1M_SCALP_HELD_LOCK_FWD_NOV9.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_HELD_LOCK_FWD_NOV9.json"
FWD_CACHE = PACK / "_fwd_nifty_1m_ext.parquet"

CAL_LO, CAL_HI = "2025-07-02", "2026-08-05"
L3M_LO, L3M_HI = "2026-08-06", "2026-11-06"
FWD_LO = "2026-11-09"

STYLES = ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "cap15", "cap20", "p75", "p60"]
FAMILIES = {
    "runs": {"bull_run2", "bull_run3", "bear_run2", "bear_run3"},
    "engulf": {"bull_engulf", "bear_engulf", "dark_cloud", "piercing"},
    "belt_maru": {"belt_bull", "belt_bear", "marubozu_bull", "marubozu_bear"},
    "stars": {"morning_star", "evening_star", "morning_doji_star", "evening_doji_star"},
    "three": {"three_outside_up", "three_outside_dn", "three_crows", "three_soldiers"},
    "kick": {"bull_kicker", "bear_kicker"},
}


def lesser(e, st):
    p, s = float(e["sl_prev"]), float(e["sl_sig"])
    return {
        "prev": p,
        "sig": s,
        "min_ps": min(p, s) if s >= 4 else p,
        "cap8": min(p, 8.0),
        "cap10": min(p, 10.0),
        "cap12": min(p, 12.0),
        "cap15": min(p, 15.0),
        "cap20": min(p, 20.0),
        "p75": max(4.0, 0.75 * p),
        "p60": max(4.0, 0.60 * p),
    }[st]


def enrich_evt(events, h, l, c, o):
    for e in events:
        fi = int(e["full_i"])
        hi, lo, cl, op = float(h[fi]), float(l[fi]), float(c[fi]), float(o[fi])
        rng = max(hi - lo, 0.5)
        upper = hi - max(op, cl)
        lower = min(op, cl) - lo
        e["adv_wick"] = (upper if e["decision"] == "BUY" else lower) / rng
        e["body_atr"] = abs(cl - op) / max(float(e["atr"]), 1.0)
        if fi >= 2:
            d1, d2 = c[fi - 1] - o[fi - 1], c[fi - 2] - o[fi - 2]
            e["stack2"] = (
                int(d1 > 0) + int(d2 > 0)
                if e["decision"] == "BUY"
                else int(d1 < 0) + int(d2 < 0)
            )
        else:
            e["stack2"] = 0
        e["family"] = "other"
        for fname, pats in FAMILIES.items():
            if e["primary"] in pats:
                e["family"] = fname
                break
        e["half"] = "am" if e["mins"] < 720 else "pm"
        e["slot"] = (
            "open"
            if e["mins"] < 600
            else (
                "morn"
                if e["mins"] < 690
                else ("mid" if e["mins"] < 780 else ("aft" if e["mins"] < 870 else "close"))
            )
        )


def path_ok(e, h, l, c, st, t1, sl_max):
    sl = lesser(e, st)
    if not (4 <= sl <= sl_max):
        return False, sl
    if st == "prev" and t1 in (10.0, 15.0, 20.0) and e.get(f"prev_t{int(t1)}") is not None:
        return e[f"prev_t{int(t1)}"] == "win", sl
    if st == "sig" and t1 in (10.0, 15.0, 20.0) and e.get(f"sig_t{int(t1)}") is not None:
        return e[f"sig_t{int(t1)}"] == "win", sl
    win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], float(sl), float(t1))
    return (win and out == "t1"), sl


def keys_t10(e):
    body = float(e["body_frac"])
    g = {
        "primary": e["primary"],
        "side": e["decision"],
        "regime": e["pre_regime"],
        "align": int(e["align_session"]),
        "clock": e["clock"],
        "body": "b70+" if body >= 0.70 else ("b55+" if body >= 0.55 else ("b45+" if body >= 0.45 else "b<45")),
        "slbin": "sl4-8" if e["sl_prev"] <= 8 else ("sl8-12" if e["sl_prev"] <= 12 else ("sl12-16" if e["sl_prev"] <= 16 else "sl16-20")),
        "rsi": "lo" if e["rsi_14"] < 35 else ("hi" if e["rsi_14"] > 65 else "mid"),
        "advw": "adv_lo" if e["adv_wick"] < 0.15 else ("adv_mid" if e["adv_wick"] < 0.30 else "adv_hi"),
        "batr": "ba>0.8" if e.get("body_atr", 0) >= 0.8 else ("ba>0.5" if e.get("body_atr", 0) >= 0.5 else "ba<0.5"),
        "stack": f"st{e.get('stack2', 0)}",
    }
    return [
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        ("GEOM", g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["advw"]),
        (g["primary"], g["side"], g["align"], g["clock"], g["advw"], g["batr"], g["slbin"], g["rsi"]),
    ]


def keys_hight(e):
    body = float(e["body_frac"])
    g = {
        "primary": e["primary"],
        "family": e["family"],
        "side": e["decision"],
        "regime": e["pre_regime"],
        "align": int(e["align_session"]),
        "clock": e["clock"],
        "half": e["half"],
        "slot": e["slot"],
        "body": "b70+" if body >= 0.70 else ("b55+" if body >= 0.55 else ("b45+" if body >= 0.45 else "b<45")),
        "slbin": "sl4-8" if e["sl_prev"] <= 8 else ("sl8-12" if e["sl_prev"] <= 12 else ("sl12-16" if e["sl_prev"] <= 16 else "sl16-20")),
        "rsi": "lo" if e["rsi_14"] < 35 else ("hi" if e["rsi_14"] > 65 else "mid"),
        "advw": "adv_lo" if e["adv_wick"] < 0.15 else ("adv_mid" if e["adv_wick"] < 0.30 else "adv_hi"),
        "batr": "ba>0.8" if e.get("body_atr", 0) >= 0.8 else ("ba>0.5" if e.get("body_atr", 0) >= 0.5 else "ba<0.5"),
        "stack": f"st{e.get('stack2', 0)}",
    }
    return [
        (g["primary"], g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        ("GEOM", g["side"], g["regime"], g["align"], g["clock"], g["body"], g["slbin"], g["rsi"], g["advw"], g["batr"], g["stack"]),
        (g["family"], g["side"], g["regime"], g["align"], g["half"], g["body"], g["slbin"], g["advw"]),
        (g["family"], g["side"], g["align"], g["slot"], g["body"], g["slbin"], g["advw"], g["stack"]),
        ("FAM", g["family"], g["side"], g["regime"], g["align"], g["clock"], g["advw"], g["slbin"]),
        (g["primary"], g["side"], g["slot"], g["align"], g["body"], g["slbin"], g["advw"]),
        ("SLOT", g["side"], g["slot"], g["regime"], g["align"], g["body"], g["slbin"], g["advw"]),
        (g["primary"], g["side"], g["align"], g["clock"], g["advw"], g["slbin"]),
        (g["primary"], g["side"], g["half"], g["advw"], g["body"]),
        (g["primary"], g["side"], g["regime"], g["clock"], g["body"], g["slbin"], g["advw"]),
    ]


def apply_gap(rows, gap):
    last, out = {}, []
    for e in sorted(rows, key=lambda x: (x["day"], x["mins"])):
        prev = last.get(e["day"])
        if prev is not None and e["mins"] - prev < gap:
            continue
        out.append(e)
        last[e["day"]] = e["mins"]
    return out


def greedy(cells, gap, min_cal=2, min_l3m=1):
    used_c, used_t, chosen = set(), set(), []

    def take(calls, used):
        out, last = [], {}
        for e in sorted(calls, key=lambda x: (x["day"], x["mins"])):
            if (e["day"], e["mins"]) in used:
                continue
            if any(d == e["day"] and abs(m - e["mins"]) < gap for d, m in used):
                continue
            prev = last.get(e["day"])
            if prev is not None and e["mins"] - prev < gap:
                continue
            out.append(e)
            last[e["day"]] = e["mins"]
        return out

    for r in cells:
        ck, tk = take(r["cal_calls"], used_c), take(r["l3m_calls"], used_t)
        if len(ck) < min_cal or len(tk) < min_l3m:
            continue
        st = r["st"]
        if not all(e.get(f"_ok_{st}") for e in ck + tk):
            continue
        chosen.append({**r, "cal_calls": ck, "l3m_calls": tk, "k": r["k"], "st": st})
        for e in ck:
            used_c.add((e["day"], e["mins"]))
        for e in tk:
            used_t.add((e["day"], e["mins"]))
    return chosen


def stats(calls, days_universe=None):
    by = Counter(e["day"] for e in calls)
    n = len(calls)
    days = len(by)
    vals = list(by.values()) if by else []
    sls = [e[f"_sl_{e['_st']}"] for e in calls] if calls else []
    wins = sum(1 for e in calls if e.get("_win"))
    univ = days_universe or days
    return {
        "n": n,
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else 0,
        "days": days,
        "zero": (univ - days) if univ else 0,
        "cpd": round(n / days, 2) if days else 0,
        "cpd_all": round(n / univ, 2) if univ else 0,
        "avg_sl": round(sum(sls) / len(sls), 2) if sls else 0,
        "hist": dict(sorted(Counter(vals).items())),
        "miss_days": sorted({e["day"] for e in calls if not e.get("_win")}),
    }


def build_book(cal, l3m, key_fn, styles, t1, sl_max, gap, min_cal=2, min_l3m=1, min_cell_cal=2):
    cal_b, l3m_b = defaultdict(list), defaultdict(list)
    for e in cal:
        if 4 <= e["sl_prev"] <= 20:
            for k in key_fn(e):
                cal_b[k].append(e)
    for e in l3m:
        if 4 <= e["sl_prev"] <= 20:
            for k in key_fn(e):
                l3m_b[k].append(e)
    cells = []
    for st in styles:
        for k, ces in cal_b.items():
            cr = apply_gap([e for e in apply_gap(ces, gap) if 4 <= e.get(f"_sl_{st}", 99) <= sl_max], gap)
            if len(cr) < min_cell_cal:
                continue
            if not all(e.get(f"_ok_{st}") for e in cr):
                continue
            tr = apply_gap([e for e in apply_gap(l3m_b.get(k, []), gap) if 4 <= e.get(f"_sl_{st}", 99) <= sl_max], gap)
            if len(tr) < 1:
                continue
            if len(tr) < 2 and len(cr) < 4:
                continue
            if not all(e.get(f"_ok_{st}") for e in tr):
                continue
            cells.append(
                {
                    "k": k,
                    "st": st,
                    "cal_calls": cr,
                    "l3m_calls": tr,
                    "cal_n": len(cr),
                    "l3m_n": len(tr),
                    "avg_sl": sum(e[f"_sl_{st}"] for e in tr) / len(tr),
                }
            )
    cells.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"], r["avg_sl"]))
    seen, uniq = set(), []
    for r in cells:
        id_ = (r["k"], r["st"])
        if id_ in seen:
            continue
        seen.add(id_)
        uniq.append(r)
    chosen = greedy(uniq, gap, min_cal=min_cal, min_l3m=min_l3m)
    return chosen


def apply_book(fwd, chosen, gap, t1, h, l, c, days_univ):
    """Non-lookahead: chronological events matching any held micro."""
    # index micros by key
    micro_map = []  # (k, st)
    for r in chosen:
        micro_map.append((r["k"], r["st"]))

    # precompute keys on fwd
    for e in fwd:
        e["_keys"] = set(e.get("_keys_cache") or [])

    by_day = defaultdict(list)
    for e in fwd:
        by_day[e["day"]].append(e)

    out = []
    for d, xs in sorted(by_day.items()):
        xs = sorted(xs, key=lambda x: x["mins"])
        last = None
        for e in xs:
            if last is not None and e["mins"] - last < gap:
                continue
            hit = None
            for k, st in micro_map:
                if k not in e["_keys"]:
                    continue
                ok, sl = path_ok(e, h, l, c, st, t1, sl_max=20.0)
                # valid structural distance required
                if not (4 <= lesser(e, st) <= 20):
                    continue
                # take first matching micro regardless — then mark win/loss
                # For held book fidelity: only fire if this micro's style SL is within the book's sl_max
                hit = (st, sl, ok, k)
                break
            if hit is None:
                continue
            st, sl, ok, k = hit
            # recompute path always for fwd (don't trust cache from other t1)
            ok2, sl2 = path_ok(e, h, l, c, st, t1, sl_max=20.0)
            ee = {
                **e,
                "_st": st,
                "_t1": t1,
                f"_sl_{st}": sl2,
                "_win": bool(ok2),
                "_k": str(k),
            }
            out.append(ee)
            last = e["mins"]
    return out, stats(out, days_univ)


def ensure_fwd_data():
    print("[1] load local 1m…", flush=True)
    existing = base.load_existing_1m()
    local_end = existing.index.max()
    print(f"  local end={local_end}", flush=True)
    today = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
    # download from day after local end through today
    start_dl = (local_end + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    if start_dl > today:
        print("  already up to date", flush=True)
        return existing, today
    print(f"[2] download {start_dl} → {today}…", flush=True)
    fresh, note = base.download_1m_range(start_dl, today)
    if note:
        print(f"  note: {note}", flush=True)
    if fresh is None or len(fresh) == 0:
        print("  WARNING: no fresh bars — validating only if local covers FWD_LO", flush=True)
        return existing, today
    # merge without research END clip
    df = pd.concat([existing, fresh]).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    PACK.mkdir(parents=True, exist_ok=True)
    # also append to existing csv for persistence
    csv_path = base.EXISTING_CSV
    save = df.reset_index().rename(columns={df.index.name or "date": "date"})
    if "date" not in save.columns:
        save = save.rename(columns={save.columns[0]: "date"})
    # write extended parquet cache for this pack
    df.to_parquet(FWD_CACHE)
    # update kite csv with full merged (user local store)
    try:
        # keep csv as the long series used by loaders
        out = df.reset_index()
        out = out.rename(columns={out.columns[0]: "date"})
        out.to_csv(csv_path, index=False)
        print(f"  updated {csv_path} bars={len(df)} end={df.index.max()}", flush=True)
    except Exception as exc:
        print(f"  csv update skipped: {exc}", flush=True)
    print(f"  merged bars={len(df)} {df.index.min()} → {df.index.max()}", flush=True)
    return df, today


def flag_paths(events, h, l, c, t1):
    for e in events:
        for st in STYLES:
            ok, sl = path_ok(e, h, l, c, st, t1, sl_max=20.0)
            e[f"_ok_{st}"] = ok
            e[f"_sl_{st}"] = sl


def main() -> int:
    print("=" * 60, flush=True)
    print("HELD lock + FWD check 2026-11-09 → today", flush=True)
    print("=" * 60, flush=True)
    PACK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    raw, today = ensure_fwd_data()
    fwd_hi = min(today, raw.index.max().strftime("%Y-%m-%d"))
    print(f"FWD window {FWD_LO} → {fwd_hi}", flush=True)
    if fwd_hi < FWD_LO:
        print("ERROR: no bars in forward window", flush=True)
        return 1

    # Need enough history for patterns/ATR before FWD_LO
    hist_lo = "2025-06-01"
    raw = raw[raw.index >= pd.Timestamp(hist_lo, tz="Asia/Kolkata")]
    print("[3] textbook patterns…", flush=True)
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values

    print("[4] collect events cal / l3m / fwd…", flush=True)
    ev_cache = PACK / f"events_{CAL_LO}_{fwd_hi}.pkl"
    if ev_cache.exists():
        blob = pickle.load(ev_cache.open("rb"))
        cal, l3m, fwd = blob["cal"], blob["l3m"], blob["fwd"]
        print(f"  loaded cache cal={len(cal)} l3m={len(l3m)} fwd={len(fwd)}", flush=True)
    else:
        cal = scalp.collect_scalp_events(df, CAL_LO, CAL_HI)
        l3m = scalp.collect_scalp_events(df, L3M_LO, L3M_HI)
        fwd = scalp.collect_scalp_events(df, FWD_LO, fwd_hi)
        pickle.dump({"cal": cal, "l3m": l3m, "fwd": fwd}, ev_cache.open("wb"), protocol=pickle.HIGHEST_PROTOCOL)
        print(f"  cal={len(cal)} l3m={len(l3m)} fwd={len(fwd)}", flush=True)

    enrich_evt(cal, h, l, c, o)
    enrich_evt(l3m, h, l, c, o)
    enrich_evt(fwd, h, l, c, o)

    fwd_days = sorted({e["day"] for e in fwd})
    print(f"  fwd trading days ({len(fwd_days)}): {fwd_days}", flush=True)

    held_specs = [
        # match deep champions
        {"name": "HELD10", "t1": 10.0, "sl_max": 12.0, "gap": 8, "key_fn": keys_t10, "styles": ["prev", "sig", "min_ps", "cap8", "cap10", "cap12", "p75"]},
        {"name": "HELD15", "t1": 15.0, "sl_max": 15.0, "gap": 4, "key_fn": keys_hight, "styles": STYLES},
        {"name": "HELD20", "t1": 20.0, "sl_max": 20.0, "gap": 4, "key_fn": keys_hight, "styles": STYLES},
    ]

    results = {"fwd_lo": FWD_LO, "fwd_hi": fwd_hi, "fwd_days": fwd_days, "books": {}}

    for spec in held_specs:
        name, t1 = spec["name"], spec["t1"]
        print(f"\n=== Build+validate {name} T1={t1} ===", flush=True)
        flag_paths(cal, h, l, c, t1)
        flag_paths(l3m, h, l, c, t1)
        # keys for fwd matching
        for e in fwd:
            e["_keys"] = set(spec["key_fn"](e))
            e["_keys_cache"] = list(e["_keys"])

        chosen = build_book(
            cal,
            l3m,
            spec["key_fn"],
            spec["styles"],
            t1,
            spec["sl_max"],
            spec["gap"],
            min_cal=2,
            min_l3m=1,
            min_cell_cal=2,
        )
        # train stats
        cal_all = [{**e, "_st": r["st"], "_t1": t1, "_win": True} for r in chosen for e in r["cal_calls"]]
        l3m_all = [{**e, "_st": r["st"], "_t1": t1, "_win": True} for r in chosen for e in r["l3m_calls"]]
        # verify train still 100
        for e in cal_all + l3m_all:
            e[f"_sl_{e['_st']}"] = e.get(f"_sl_{e['_st']}", e["sl_prev"])
        train_cal = stats(cal_all, 271)
        train_l3m = stats(l3m_all, 64)
        print(
            f"  train micros={len(chosen)} cal {train_cal['n']}/{train_cal['days']}d "
            f"l3m {train_l3m['n']}/{train_l3m['days']}d zero={train_l3m['zero']}",
            flush=True,
        )

        calls, fwd_stats = apply_book(fwd, chosen, spec["gap"], t1, h, l, c, len(fwd_days) or 1)
        print(
            f"  FWD: {fwd_stats['n']} calls / {fwd_stats['days']} days · "
            f"hit={fwd_stats['hit_pct']}% · zero={fwd_stats['zero']} · "
            f"avgSL={fwd_stats['avg_sl']} · misses={fwd_stats['miss_days']}",
            flush=True,
        )
        for e in calls[:12]:
            mark = "Y" if e["_win"] else "N"
            print(
                f"    {e['day']} {e['hm']} {e['decision']} {e['primary']} "
                f"{e['_st']} sl={e[f'_sl_{e['_st']}']:.1f} {mark}",
                flush=True,
            )

        results["books"][name] = {
            "t1": t1,
            "sl_max": spec["sl_max"],
            "gap": spec["gap"],
            "n_micros": len(chosen),
            "train_cal": train_cal,
            "train_l3m": train_l3m,
            "fwd": fwd_stats,
            "fwd_calls": [
                {
                    "day": e["day"],
                    "hm": e["hm"],
                    "decision": e["decision"],
                    "primary": e["primary"],
                    "st": e["_st"],
                    "sl": round(e[f"_sl_{e['_st']}"], 2),
                    "win": e["_win"],
                    "mfe": round(e["mfe"], 1),
                    "mae": round(e["mae"], 2),
                }
                for e in sorted(calls, key=lambda x: (x["day"], x["mins"]))
            ],
            "held": True,
        }

    # Write held lock report
    lines = [
        "# NIFTY 1m — **HELD scalp logics locked** + forward check",
        "",
        "**Not live.** Hold T1=10 / 15 / 20 PATH books. Forward window after research cut.",
        "",
        f"- Candle: **NIFTY 1-minute**",
        f"- Train calibrate: `{CAL_LO}` → `{CAL_HI}`",
        f"- Train last3m: `{L3M_LO}` → `{L3M_HI}`",
        f"- **Forward check: `{FWD_LO}` → `{fwd_hi}`** ({len(fwd_days)} sessions: {', '.join(fwd_days)})",
        "- Win rule: **target before structure SL** (prev / lesser cap)",
        "",
        "## HELD books (locked)",
        "",
        "| Book | T1 | Train l3m calls | Train days | Train zero | FWD calls | FWD days | FWD hit% | FWD avg SL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("HELD10", "HELD15", "HELD20"):
        b = results["books"][name]
        lines.append(
            f"| **{name}** | {int(b['t1'])} | {b['train_l3m']['n']} | {b['train_l3m']['days']} | "
            f"{b['train_l3m']['zero']} | {b['fwd']['n']} | {b['fwd']['days']} | "
            f"**{b['fwd']['hit_pct']}%** | {b['fwd']['avg_sl']} |"
        )

    for name in ("HELD10", "HELD15", "HELD20"):
        b = results["books"][name]
        lines += [
            "",
            f"## {name} — T1={int(b['t1'])} LOCKED",
            "",
            f"- Micros: **{b['n_micros']}** · gap **{b['gap']}** · SLmax **{b['sl_max']}**",
            f"- Train last3m: **{b['train_l3m']['n']} calls / {b['train_l3m']['days']} days** · zero {b['train_l3m']['zero']} · 100% path",
            f"- Forward `{FWD_LO}`→`{fwd_hi}`: **{b['fwd']['n']} calls** · "
            f"**{b['fwd']['hit_pct']}%** hit (target first) · days {b['fwd']['days']}/{len(fwd_days)} · "
            f"avg SL {b['fwd']['avg_sl']}",
            "",
            "| Day | HM | Side | Pattern | SL style | SL | Win | MFE | MAE |",
            "|---|---|---|---|---|---:|:---:|---:|---:|",
        ]
        for e in b["fwd_calls"]:
            lines.append(
                f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"`{e['st']}` | {e['sl']} | {'Y' if e['win'] else 'N'} | {e['mfe']} | {e['mae']} |"
            )
        if not b["fwd_calls"]:
            lines.append("| — | | | | | | | | |")

    lines += [
        "",
        "## Lock policy",
        "",
        "1. **HELD10** — T1=10 deep PATH (wick/ATR/stack micros) — locked",
        "2. **HELD15** — T1=15 deep family/slot PATH — locked",
        "3. **HELD20** — T1=20 deep family/slot PATH — locked",
        "4. Do not replace these with weaker books; additive research only",
        "",
        f"- Pack: `{PACK}`",
        f"- Data fwd cache: `{FWD_CACHE}`",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    (PACK / "held_lock.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    # stamp deeper reports
    for md_name in (
        "NIFTY_1M_SCALP_T15_T20_DEEPER.md",
        "NIFTY_1M_SCALP_DEEPER_100.md",
        "NIFTY_1M_SCALP_HELD_HIGHT_LOWSL.md",
    ):
        p = OUT / md_name
        if not p.exists():
            continue
        md = p.read_text(encoding="utf-8")
        marker = "## HELD lock + Nov9 forward"
        block = [
            "",
            "## HELD lock + Nov9 forward",
            "",
            f"See [`NIFTY_1M_SCALP_HELD_LOCK_FWD_NOV9.md`](NIFTY_1M_SCALP_HELD_LOCK_FWD_NOV9.md) "
            f"(`{FWD_LO}`→`{fwd_hi}`).",
        ]
        for name in ("HELD10", "HELD15", "HELD20"):
            b = results["books"][name]
            block.append(
                f"- **{name}** locked · FWD {b['fwd']['n']} calls @ **{b['fwd']['hit_pct']}%** "
                f"({b['fwd']['days']}/{len(fwd_days)} days)"
            )
        if marker in md:
            md = md.split(marker)[0].rstrip()
        p.write_text(md + "\n" + "\n".join(block) + "\n", encoding="utf-8")

    print(f"\nWrote {REPORT_MD}", flush=True)
    print("DONE held lock + fwd", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
