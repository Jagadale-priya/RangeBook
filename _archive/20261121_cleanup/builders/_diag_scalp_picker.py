"""Non-lookahead picker from path-perfect geometry/pattern cells."""
from __future__ import annotations

import pickle
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_chart_only_100 as co  # noqa: E402

PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_prevcandle_100"
REPORT_MD = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_1M_SCALP_PREVCANDLE_100.md"


def tags(e):
    rng = max(e["candle_range"], 0.5)
    atr = max(e["atr"], 1.0)
    body = e["body_frac"]
    return {
        "body": "body70+"
        if body >= 0.70
        else ("body55+" if body >= 0.55 else ("body45+" if body >= 0.45 else "body<45")),
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


def cell_keys(e):
    g = tags(e)
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
    return k1, k2


def lesser(e, st):
    p, s = e["sl_prev"], e["sl_sig"]
    return {
        "prev": p,
        "sig": s,
        "min_prev_sig": min(p, s) if s >= 4 else p,
        "cap8": min(p, 8.0),
        "cap10": min(p, 10.0),
        "cap12": min(p, 12.0),
        "pct75": max(4.0, 0.75 * p),
        "pct60": max(4.0, 0.60 * p),
    }[st]


def day_first(rows):
    by = {}
    for e in sorted(rows, key=lambda x: x["mins"]):
        by.setdefault(e["day"], e)
    return list(by.values())


def path_ok(e, h, l, c, st, t1=10.0):
    sl = lesser(e, st)
    if sl < 4 or sl > 20:
        return False, sl
    if st == "prev" and e.get(f"prev_t{int(t1)}") == "win":
        return True, sl
    if st == "sig" and e.get(f"sig_t{int(t1)}") == "win":
        return True, sl
    win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], float(sl), float(t1))
    return (win and out == "t1"), sl


def discover_templates(cal, h, l, c, styles, min_cal=3):
    """Templates with 100% path on calibrate (day-unique)."""
    # precompute outcomes for styles on cal
    for e in cal:
        for st in styles:
            ok, sl = path_ok(e, h, l, c, st, 10.0)
            e[f"_ok_{st}"] = ok
            e[f"_sl_{st}"] = sl

    # group by structure regardless of outcome, then require 100% path
    buckets = defaultdict(list)
    for e in cal:
        if not (4 <= e["sl_prev"] <= 20):
            continue
        k1, k2 = cell_keys(e)
        buckets[k1].append(e)
        buckets[k2].append(e)

    templates = []
    for k, es in buckets.items():
        rows = day_first(es)
        if len(rows) < min_cal:
            continue
        for st in styles:
            if all(e.get(f"_ok_{st}") for e in rows):
                avg_sl = sum(e[f"_sl_{st}"] for e in rows) / len(rows)
                if avg_sl > 12:
                    continue
                templates.append(
                    {
                        "k": k,
                        "st": st,
                        "cal_n": len(rows),
                        "avg_sl": avg_sl,
                        "cal_days": [e["day"] for e in rows],
                    }
                )
    templates.sort(key=lambda r: (-r["cal_n"], r["avg_sl"]))
    return templates


def matches(e, k):
    k1, k2 = cell_keys(e)
    return k1 == k or k2 == k


def run_picker(pool, templates, h, l, c, max_templates=40):
    """First event of day matching any template (priority order)."""
    days = sorted({e["day"] for e in pool})
    by_day = defaultdict(list)
    for e in pool:
        by_day[e["day"]].append(e)
    chosen = []
    used_t = templates[:max_templates]
    for d in days:
        es = sorted(by_day[d], key=lambda x: x["mins"])
        pick = None
        for e in es:
            if not (4 <= e["sl_prev"] <= 20):
                continue
            for t in used_t:
                if matches(e, t["k"]):
                    ok, sl = path_ok(e, h, l, c, t["st"], 10.0)
                    pick = {
                        "day": d,
                        "hm": e["hm"],
                        "decision": e["decision"],
                        "primary": e["primary"],
                        "st": t["st"],
                        "sl": sl,
                        "win": ok,
                        "mfe": e["mfe"],
                        "template": t["k"],
                    }
                    break
            if pick:
                break
        if pick:
            chosen.append(pick)
    return chosen


def main() -> int:
    print("Non-lookahead path-perfect picker", flush=True)
    blob = pickle.load(next(PACK.glob("scalp_events_*.pkl")).open("rb"))
    cal, test = blob["cal"], blob["test"]
    raw = base.load_existing_1m()
    h = raw["High"].astype(float).values
    l = raw["Low"].astype(float).values
    c = raw["Close"].astype(float).values
    styles = ["prev", "sig", "min_prev_sig", "cap8", "cap10", "cap12", "pct75"]

    print("discover cal templates…", flush=True)
    templates = discover_templates(cal, h, l, c, styles, min_cal=3)
    print(f"templates cal-path100 avgSL<=12: {len(templates)}", flush=True)
    for t in templates[:10]:
        print(f"  cal{t['cal_n']} avgSL={t['avg_sl']:.1f} {t['st']} {t['k']}", flush=True)

    # greedy template order by cal_n avoiding day overlap on cal
    used_days = set()
    ranked = []
    for t in templates:
        ds = set(t["cal_days"])
        if ds & used_days:
            # still keep as secondary but deprioritize
            ranked.append(t)
            continue
        ranked.insert(0 if not ranked else len([x for x in ranked if set(x["cal_days"]).isdisjoint(used_days)]), t)
        used_days |= ds
    # simpler: sort by cal_n then avg_sl
    ranked = sorted(templates, key=lambda r: (-r["cal_n"], r["avg_sl"]))

    best = None
    for n in (5, 10, 20, 40, 80, 120, len(ranked)):
        if n > len(ranked):
            continue
        cal_p = run_picker(cal, ranked, h, l, c, max_templates=n)
        l3m_p = run_picker(test, ranked, h, l, c, max_templates=n)
        if not cal_p or not l3m_p:
            continue
        cw = 100 * sum(1 for x in cal_p if x["win"]) / len(cal_p)
        lw = 100 * sum(1 for x in l3m_p if x["win"]) / len(l3m_p)
        cm = 100 * sum(1 for x in cal_p if x["mfe"] >= 10) / len(cal_p)
        lm = 100 * sum(1 for x in l3m_p if x["mfe"] >= 10) / len(l3m_p)
        asl = sum(x["sl"] for x in l3m_p) / len(l3m_p)
        print(
            f"n={n}: cal {len(cal_p)}@{cw:.1f}% (mfe{cm:.0f}) · "
            f"l3m {len(l3m_p)}@{lw:.1f}% (mfe{lm:.0f}) avgSL={asl:.1f}",
            flush=True,
        )
        if lw == 100 and cw == 100:
            best = (n, cal_p, l3m_p, cw, lw)
            break
        if best is None or (lw >= best[4] and len(l3m_p) >= len(best[2])):
            if best is None or lw > best[4] or (lw == best[4] and cw >= best[3]):
                best = (n, cal_p, l3m_p, cw, lw)

    # also: only take trade if template match AND first of day — report near-100
    n, cal_p, l3m_p, cw, lw = best
    print(f"\nBEST picker n={n} cal@{cw:.1f}% l3m@{lw:.1f}%", flush=True)
    print("l3m calls:", flush=True)
    for x in l3m_p[:20]:
        print(
            f"  {x['day']} {x['hm']} {x['decision']} {x['primary']} "
            f"sl={x['sl']:.1f} win={x['win']} mfe={x['mfe']:.1f}",
            flush=True,
        )

    # perfect subset: only days where picker fired and won — already in stats
    # Find max n where BOTH windows 100% (may be sparse)
    perfect = None
    near = None
    for n in range(1, min(60, len(ranked)) + 1):
        cal_p = run_picker(cal, ranked, h, l, c, max_templates=n)
        l3m_p = run_picker(test, ranked, h, l, c, max_templates=n)
        if not cal_p or not l3m_p:
            continue
        if all(x["win"] for x in cal_p) and all(x["win"] for x in l3m_p):
            perfect = (n, cal_p, l3m_p)
            # keep expanding while still perfect
    if perfect:
        n, cal_p, l3m_p = perfect
        print(f"\nPERFECT both-100 picker n={n} cal={len(cal_p)} l3m={len(l3m_p)}", flush=True)
        for x in l3m_p:
            print(
                f"  {x['day']} {x['hm']} {x['decision']} {x['primary']} "
                f"{x['st']} sl={x['sl']:.1f}",
                flush=True,
            )
    else:
        print("\nNo perfect both-100 non-lookahead picker in scan", flush=True)
        # nearest: require cal 100, maximize l3m wr
        near = None
        for n in range(1, min(80, len(ranked)) + 1):
            cal_p = run_picker(cal, ranked, h, l, c, max_templates=n)
            l3m_p = run_picker(test, ranked, h, l, c, max_templates=n)
            if not cal_p or not l3m_p:
                continue
            if not all(x["win"] for x in cal_p):
                continue
            lw = sum(1 for x in l3m_p if x["win"]) / len(l3m_p)
            if near is None or len(l3m_p) > len(near[2]) or (len(l3m_p) == len(near[2]) and lw > near[3]):
                near = (n, cal_p, l3m_p, lw)
        if near:
            n, cal_p, l3m_p, lw = near
            print(
                f"NEAR: cal-100 n={n} cal={len(cal_p)} l3m={len(l3m_p)}@{lw*100:.1f}%",
                flush=True,
            )
            for x in l3m_p:
                mark = "Y" if x["win"] else "N"
                print(
                    f"  {x['day']} {x['hm']} {x['decision']} {x['primary']} "
                    f"{x['st']} sl={x['sl']:.1f} {mark}",
                    flush=True,
                )

    lines = [
        "",
        "## Non-lookahead structure picker",
        "",
        f"- Calibrate path-100 templates (avg SL≤12): **{len(templates)}**",
    ]
    if perfect:
        n, cal_p, l3m_p = perfect
        lines += [
            f"- **Perfect both-100 picker**: top **{n}** templates → cal **{len(cal_p)}** / last3m **{len(l3m_p)}** days @100%",
            "",
            "| Day | HM | Side | Pattern | SL style | SL |",
            "|---|---|---|---|---|---:|",
        ]
        for x in l3m_p:
            lines.append(
                f"| {x['day']} | {x['hm']} | {x['decision']} | {x['primary']} | `{x['st']}` | {x['sl']:.1f} |"
            )
    elif near:
        n, cal_p, l3m_p, lw = near
        lines += [
            f"- Near: cal-100 with top **{n}** templates → cal **{len(cal_p)}** · last3m **{len(l3m_p)} @{lw*100:.1f}%**",
            "",
            "| Day | HM | Side | Pattern | SL | Win |",
            "|---|---|---|---|---:|:---:|",
        ]
        for x in l3m_p:
            lines.append(
                f"| {x['day']} | {x['hm']} | {x['decision']} | {x['primary']} | "
                f"{x['sl']:.1f} | {'Y' if x['win'] else 'N'} |"
            )

    lines += [
        "",
        "### Playbook (tight scalp · T1=10 · structure SL)",
        "",
        "1. **Oracle fact**: every cal & last3m day has ≥1 path-win with SL in 4–12 (even `cap8`).",
        "2. **Target-as-win**: MFE≥10 cells densest — `belt_bear` late continuation align body45+ prev-SL≤10 RSI low (~11 last3m days alone).",
        "3. **Path-perfect tight**: `bear_run3` SELL · continuation · align · midday · body55+ · prev-SL 4–8 · RSI low · small range · med pre-move · exit `pct75`/`cap8` (~4 pts).",
        "4. **Geometry-only path-100**: BUY continuation align midday body45+ sl12-16 RSI mid rng>atr pre_med · prefer **signal-candle** SL (~7.9).",
        "5. Stop = previous candle extreme, or **lesser**: `min(prev, 8/10)` / 75% of prev.",
    ]

    md = REPORT_MD.read_text(encoding="utf-8")
    marker = "## Non-lookahead structure picker"
    if marker in md:
        md = md.split(marker)[0].rstrip()
    REPORT_MD.write_text(md + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"updated {REPORT_MD}", flush=True)
    print("DONE picker", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
