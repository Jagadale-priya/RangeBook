"""Deep scalp structure hunt: lesser SL + candle geometry → path-100 / target-100."""
from __future__ import annotations

import pickle
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_chart_only_100 as co  # noqa: E402

PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_prevcandle_100"
OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT_MD = OUT / "NIFTY_1M_SCALP_PREVCANDLE_100.md"


def geom_tags(e):
    rng = max(e["candle_range"], 0.5)
    atr = max(e["atr"], 1.0)
    body = e["body_frac"]
    return {
        "body": "body70+" if body >= 0.70 else ("body55+" if body >= 0.55 else ("body45+" if body >= 0.45 else "body<45")),
        "rng_atr": "rng>atr" if rng > atr else ("rng>0.7atr" if rng > 0.7 * atr else "rng_small"),
        "pre": (
            "pre_strong"
            if abs(e["pre_chg_5"]) >= 12
            else ("pre_med" if abs(e["pre_chg_5"]) >= 5 else "pre_flat")
        ),
        "rsi": "rsi_lo" if e["rsi_14"] < 35 else ("rsi_hi" if e["rsi_14"] > 65 else "rsi_mid"),
        "clock": e["clock"],
        "align": int(e["align_session"]),
        "regime": e["pre_regime"],
        "side": e["decision"],
        "primary": e["primary"],
        "sl_bin": (
            "sl4-8"
            if 4 <= e["sl_prev"] <= 8
            else ("sl8-12" if e["sl_prev"] <= 12 else ("sl12-16" if e["sl_prev"] <= 16 else "sl16-20"))
        ),
    }


def lesser_sl(e, style: str) -> float:
    p, s = e["sl_prev"], e["sl_sig"]
    if style == "prev":
        return p
    if style == "sig":
        return s
    if style == "min_prev_sig":
        return min(p, s) if s >= 4 else p
    if style == "cap8":
        return min(p, 8.0)
    if style == "cap10":
        return min(p, 10.0)
    if style == "cap12":
        return min(p, 12.0)
    if style == "pct75":
        return max(4.0, 0.75 * p)
    if style == "pct60":
        return max(4.0, 0.60 * p)
    return p


def enrich_path(events, h, l, c, styles, t1s):
    t0 = time.time()
    for i, e in enumerate(events):
        if i and i % 15000 == 0:
            print(f"    path enrich {i}/{len(events)} ({time.time()-t0:.0f}s)", flush=True)
        for st in styles:
            sl = lesser_sl(e, st)
            e[f"sl_{st}"] = float(sl)
            for t1 in t1s:
                key = f"{st}_t{int(t1)}"
                if sl < 4.0:
                    e[key] = "bad_sl"
                    continue
                # reuse cached prev/sig if exact match
                if st == "prev" and key.replace("prev", "prev") in e and f"prev_t{int(t1)}" in e:
                    e[key] = e[f"prev_t{int(t1)}"]
                    continue
                if st == "sig" and f"sig_t{int(t1)}" in e:
                    e[key] = e[f"sig_t{int(t1)}"]
                    continue
                win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], float(sl), float(t1))
                e[key] = "win" if (win and out == "t1") else out
    return events


def day_first(rows):
    by = {}
    for e in sorted(rows, key=lambda x: x["mins"]):
        by.setdefault(e["day"], e)
    return list(by.values())


def hunt_cells(cal, test, path_key: str, mode: str, min_cal=3, min_l3m=2):
    """mode: path = all win on path_key; mfe = all mfe>=T1 from key."""
    t1 = float(path_key.split("_t")[-1])
    cal_c, test_c = defaultdict(list), defaultdict(list)

    def ok_event(e):
        if not (4 <= e["sl_prev"] <= 20):
            return False
        if e.get(path_key) == "bad_sl":
            return False
        return True

    for e in cal:
        if not ok_event(e):
            continue
        g = geom_tags(e)
        # pattern+geom cell
        k1 = (
            g["primary"],
            g["side"],
            g["regime"],
            g["align"],
            g["clock"],
            g["body"],
            g["sl_bin"],
            g["rsi"],
            g["rng_atr"],
            g["pre"],
        )
        # geometry-only (no pattern name)
        k2 = (
            "GEOM",
            g["side"],
            g["regime"],
            g["align"],
            g["clock"],
            g["body"],
            g["sl_bin"],
            g["rsi"],
            g["rng_atr"],
            g["pre"],
        )
        cal_c[k1].append(e)
        cal_c[k2].append(e)
    for e in test:
        if not ok_event(e):
            continue
        g = geom_tags(e)
        k1 = (
            g["primary"],
            g["side"],
            g["regime"],
            g["align"],
            g["clock"],
            g["body"],
            g["sl_bin"],
            g["rsi"],
            g["rng_atr"],
            g["pre"],
        )
        k2 = (
            "GEOM",
            g["side"],
            g["regime"],
            g["align"],
            g["clock"],
            g["body"],
            g["sl_bin"],
            g["rsi"],
            g["rng_atr"],
            g["pre"],
        )
        test_c[k1].append(e)
        test_c[k2].append(e)

    cells = []
    for k, es in cal_c.items():
        rows = day_first(es)
        if len(rows) < min_cal:
            continue
        if mode == "path":
            if any(e.get(path_key) != "win" for e in rows):
                continue
        else:
            if any(e["mfe"] < t1 for e in rows):
                continue
        te = day_first(test_c.get(k, []))
        if len(te) < min_l3m:
            continue
        if mode == "path":
            if any(e.get(path_key) != "win" for e in te):
                continue
        else:
            if any(e["mfe"] < t1 for e in te):
                continue
        sl_field = "sl_" + path_key.split("_t")[0]
        avg_sl = sum(e.get(sl_field, e["sl_prev"]) for e in te) / len(te)
        path_w = sum(1 for e in te if e.get(path_key) == "win") / len(te)
        cells.append(
            {
                "k": k,
                "cal_n": len(rows),
                "l3m_n": len(te),
                "avg_sl": avg_sl,
                "path_win": path_w,
                "cal_days": [e["day"] for e in rows],
                "l3m_days": [e["day"] for e in te],
                "calls": te,
                "path_key": path_key,
                "mode": mode,
            }
        )
    cells.sort(key=lambda r: (-r["l3m_n"], r["avg_sl"], -r["cal_n"]))
    return cells


def greedy_union(cells, max_sl=None):
    used_c, used_t = set(), set()
    chosen = []
    for r in cells:
        if max_sl is not None and r["avg_sl"] > max_sl:
            continue
        ca, lt = set(r["cal_days"]), set(r["l3m_days"])
        if ca & used_c or lt & used_t:
            continue
        chosen.append(r)
        used_c |= ca
        used_t |= lt
    return chosen, used_c, used_t


def main() -> int:
    print("Deep scalp structure · lesser SL + geometry", flush=True)
    blob = pickle.load(next(PACK.glob("scalp_events_*.pkl")).open("rb"))
    cal, test = blob["cal"], blob["test"]
    print(f"events cal={len(cal)} test={len(test)}", flush=True)

    print("load 1m bars…", flush=True)
    raw = base.load_existing_1m()
    # ensure features if needed
    if "atr14" not in raw.columns:
        raw = base.prepare_1m(raw) if hasattr(base, "prepare_1m") else raw
    h = raw["High"].astype(float).values
    l = raw["Low"].astype(float).values
    c = raw["Close"].astype(float).values

    styles = ["prev", "sig", "min_prev_sig", "cap8", "cap10", "cap12", "pct75", "pct60"]
    t1s = [10.0, 20.0]
    print("enrich path for lesser SL styles…", flush=True)
    enrich_path(cal, h, l, c, styles, t1s)
    enrich_path(test, h, l, c, styles, t1s)

    # quick style comparison (day-unique first signal any pattern)
    print("\n=== Style scan (all events, day-unique first, T1=10) ===", flush=True)
    for st in styles:
        key = f"{st}_t10"
        for name, pool in (("cal", cal), ("l3m", test)):
            by = {}
            for e in sorted(pool, key=lambda x: (x["day"], x["mins"])):
                if e.get(key) == "bad_sl":
                    continue
                if not (4 <= lesser_sl(e, st) <= 20):
                    continue
                by.setdefault(e["day"], e)
            rows = list(by.values())
            if not rows:
                continue
            wr = 100 * sum(1 for e in rows if e.get(key) == "win") / len(rows)
            mfe = 100 * sum(1 for e in rows if e["mfe"] >= 10) / len(rows)
            asl = sum(lesser_sl(e, st) for e in rows) / len(rows)
            print(f"  {st:14s} {name}: n={len(rows)} path={wr:.1f}% mfe10={mfe:.1f}% avgSL={asl:.1f}", flush=True)

    # hunt path-100 and mfe-100 with deep geometry
    all_path, all_mfe = [], []
    for st in styles:
        for t1 in t1s:
            key = f"{st}_t{int(t1)}"
            pc = hunt_cells(cal, test, key, "path", min_cal=3, min_l3m=2)
            mc = hunt_cells(cal, test, key, "mfe", min_cal=3, min_l3m=2)
            print(f"  {key}: path-both100 cells={len(pc)} mfe-both100 cells={len(mc)}", flush=True)
            all_path.extend(pc)
            all_mfe.extend(mc)

    all_path.sort(key=lambda r: (-r["l3m_n"], r["avg_sl"], -r["cal_n"]))
    all_mfe.sort(key=lambda r: (-r["l3m_n"], r["avg_sl"], -r["cal_n"]))

    # prefer tight SL
    path_tight = [r for r in all_path if r["avg_sl"] <= 12]
    mfe_tight = [r for r in all_mfe if r["avg_sl"] <= 12]

    u_path, ucp, utp = greedy_union(all_path)
    u_path_t, ucpt, utpt = greedy_union(path_tight)
    u_mfe, ucm, utm = greedy_union(all_mfe)
    u_mfe_t, ucmt, utmt = greedy_union(mfe_tight)

    print("\n=== Unions ===", flush=True)
    print(f"PATH both-100 union: cal {len(ucp)} / l3m {len(utp)} · micros {len(u_path)}", flush=True)
    print(f"PATH tight SL≤12:   cal {len(ucpt)} / l3m {len(utpt)} · micros {len(u_path_t)}", flush=True)
    print(f"MFE  both-100 union: cal {len(ucm)} / l3m {len(utm)} · micros {len(u_mfe)}", flush=True)
    print(f"MFE  tight SL≤12:   cal {len(ucmt)} / l3m {len(utmt)} · micros {len(u_mfe_t)}", flush=True)

    print("\nTop PATH both-100 (tight first):", flush=True)
    for r in (path_tight or all_path)[:12]:
        print(
            f"  l3m{r['l3m_n']} cal{r['cal_n']} avgSL={r['avg_sl']:.1f} "
            f"{r['path_key']} {r['k']}",
            flush=True,
        )
    print("\nTop MFE both-100 tight:", flush=True)
    for r in mfe_tight[:12]:
        print(
            f"  l3m{r['l3m_n']} cal{r['cal_n']} avgSL={r['avg_sl']:.1f} "
            f"pathWin={r['path_win']*100:.0f}% {r['path_key']} {r['k']}",
            flush=True,
        )

    # GEOM-only stars
    geom_path = [r for r in all_path if r["k"][0] == "GEOM"]
    geom_mfe = [r for r in all_mfe if r["k"][0] == "GEOM" and r["avg_sl"] <= 12]
    print(f"\nGEOM-only path-100 cells: {len(geom_path)}", flush=True)
    for r in geom_path[:8]:
        print(f"  l3m{r['l3m_n']} cal{r['cal_n']} avgSL={r['avg_sl']:.1f} {r['path_key']} {r['k']}", flush=True)
    print(f"GEOM-only mfe-100 tight: {len(geom_mfe)}", flush=True)
    for r in geom_mfe[:8]:
        print(
            f"  l3m{r['l3m_n']} cal{r['cal_n']} avgSL={r['avg_sl']:.1f} "
            f"pathWin={r['path_win']*100:.0f}% {r['path_key']} {r['k']}",
            flush=True,
        )

    # write report section
    lines = [
        "",
        "## Deep structure · lesser SL + candle geometry",
        "",
        "Exit variants vs previous-candle stop:",
        "",
        "| Style | Meaning |",
        "|---|---|",
        "| `prev` | Prior bar low/high |",
        "| `sig` | Signal candle extreme |",
        "| `min_prev_sig` | Tighter of prev vs signal |",
        "| `cap8/10/12` | `min(prev, cap)` — lesser SL |",
        "| `pct75/60` | 75%/60% of prev distance |",
        "",
        f"- **Path both-100 union**: {len(ucp)} cal / **{len(utp)} last3m** days · {len(u_path)} micros",
        f"- **Path tight (avg SL≤12)**: {len(ucpt)} / **{len(utpt)}** · {len(u_path_t)} micros",
        f"- **Target-reached (MFE) union**: {len(ucm)} / **{len(utm)}** · {len(u_mfe)} micros",
        f"- **MFE tight**: {len(ucmt)} / **{len(utmt)}** · {len(u_mfe_t)} micros",
        f"- Geometry-only path-100 cells: **{len(geom_path)}** · MFE tight: **{len(geom_mfe)}**",
        "",
        "### Path-perfect champions (T1 before lesser/structure SL)",
        "",
        "| Cal | L3m | AvgSL | Exit | Cell |",
        "|---:|---:|---:|---|---|",
    ]
    for r in (path_tight or all_path)[:15]:
        lines.append(
            f"| {r['cal_n']} | {r['l3m_n']} | {r['avg_sl']:.1f} | `{r['path_key']}` | `{r['k']}` |"
        )

    lines += [
        "",
        "### Target-always champions (MFE≥T1 · tight SL ≤12 · SL = insurance)",
        "",
        "| Cal | L3m | AvgSL | Path% | Exit | Cell |",
        "|---:|---:|---:|---:|---|---|",
    ]
    for r in mfe_tight[:15]:
        lines.append(
            f"| {r['cal_n']} | {r['l3m_n']} | {r['avg_sl']:.1f} | {r['path_win']*100:.0f} | "
            f"`{r['path_key']}` | `{r['k']}` |"
        )

    if u_path_t:
        lines += [
            "",
            "### Example path-perfect tight book (last3m)",
            "",
            "| Day | HM | Side | Pattern | SL style | SL | T1 |",
            "|---|---|---|---|---|---:|---:|",
        ]
        shown = []
        for r in u_path_t:
            for e in sorted(r["calls"], key=lambda x: x["day"]):
                st = r["path_key"].split("_t")[0]
                t1 = r["path_key"].split("_t")[-1]
                shown.append(
                    f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
                    f"`{st}` | {e.get('sl_'+st, e['sl_prev']):.1f} | {t1} |"
                )
        lines.extend(shown[:25])

    if geom_path:
        lines += [
            "",
            "### Geometry-only path-100 (no pattern name)",
            "",
            "| Cal | L3m | AvgSL | Exit | Structure |",
            "|---:|---:|---:|---|---|",
        ]
        for r in geom_path[:10]:
            lines.append(
                f"| {r['cal_n']} | {r['l3m_n']} | {r['avg_sl']:.1f} | `{r['path_key']}` | `{r['k']}` |"
            )

    md = REPORT_MD.read_text(encoding="utf-8")
    marker = "## Deep structure · lesser SL + candle geometry"
    if marker in md:
        md = md.split(marker)[0].rstrip()
    REPORT_MD.write_text(md + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"updated {REPORT_MD}", flush=True)
    print("DONE structure deep", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
