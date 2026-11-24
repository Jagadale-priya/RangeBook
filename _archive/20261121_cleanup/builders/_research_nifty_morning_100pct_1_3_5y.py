"""NIFTY morning strong BUY — hold 100% accuracy · test 1y / 3y / 5y.

Honest path: 15m thrust → 5m fill at OR+lim · ±30 · 1 call/day.

Builds one event table (loose signal), then filters gates in-memory.

  python -u prod_live/tests/builders/_research_nifty_morning_100pct_1_3_5y.py
"""
from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]
import path_setup  # noqa: F401,E402

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT_DIR / "NIFTY_MORNING_STRONG_100PCT_1_3_5Y.md"
OUT_JSON = OUT_DIR / "NIFTY_MORNING_STRONG_100PCT_1_3_5Y.json"
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_kite.csv"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"

SL = T1 = 30.0
# session floors for "holds 100%" claim
MIN_N = {"1y": 5, "3y": 8, "5y": 10}
SESSIONS = {"1y": 252, "3y": 756, "5y": 1260}


def _load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.columns = [str(c).strip().title() for c in df.columns]
    if df.index.tz is None:
        df.index = df.index.tz_localize("Asia/Kolkata")
    else:
        df.index = df.index.tz_convert("Asia/Kolkata")
    return df.sort_index()


def _hm(ts: Any) -> str:
    t = pd.Timestamp(ts).tz_convert("Asia/Kolkata")
    return f"{int(t.hour):02d}:{int(t.minute):02d}"


def _outcome(entry: float, after: pd.DataFrame) -> str:
    if after is None or after.empty:
        return "open"
    stop, tgt = entry - SL, entry + T1
    for _, r in after.iterrows():
        lo, hi = float(r["Low"]), float(r["High"])
        if lo <= stop and hi >= tgt:
            return "loss"
        if hi >= tgt:
            return "win"
        if lo <= stop:
            return "loss"
    return "open"


def build_events(by15: Dict[str, pd.DataFrame], by5: Dict[str, pd.DataFrame], days: List[str]) -> List[dict]:
    """One first-fill event per day under loose signal (for later gate filter)."""
    events: List[dict] = []
    for di, d in enumerate(days):
        if di % 200 == 0:
            print(f"  events {di}/{len(days)}", flush=True)
        sess = by15[d]
        if len(sess) < 6:
            continue
        s5 = by5.get(d)
        or_hi = float(sess["High"].iloc[0])
        or_lo = float(sess["Low"].iloc[0])
        width = or_hi - or_lo
        if width <= 0:
            continue
        day_open = float(sess["Open"].iloc[0])
        first_up = first_dn = None
        for i in range(len(sess)):
            c = float(sess["Close"].iloc[i])
            if first_up is None and c > or_hi:
                first_up = i
            if first_dn is None and c < or_lo:
                first_dn = i
        down_first = bool(
            first_up is not None and first_dn is not None and first_dn < first_up
        )
        # first loose signal in morning window
        sig_i = None
        for i, ts in enumerate(sess.index):
            hm = _hm(ts)
            if hm < "09:45" or hm > "12:00" or i < 2:
                continue
            row = sess.iloc[i]
            c = float(row["Close"])
            o = float(row["Open"])
            h = float(row["High"])
            l = float(row["Low"])
            if c <= or_hi or c <= o:
                continue
            uplift = c - day_open
            if uplift < 40:  # loose floor
                continue
            prior_hi = max(float(sess["High"].iloc[j]) for j in range(i - 2, i))
            if c <= prior_hi:
                continue
            rng = max(h - l, 1e-9)
            body = abs(c - o) / rng
            if body < 0.50:
                continue
            top = (c - l) / rng
            sig_i = i
            sig_ts = ts
            sig_hm = hm
            sig_uplift = uplift
            sig_body = body
            sig_top = top
            sig_rng = rng
            sig_bf = (c - or_hi) / width
            cont = first_up is not None and i > first_up
            break
        if sig_i is None:
            continue

        after_sig = s5[s5.index > sig_ts] if s5 is not None and len(s5) else sess.iloc[sig_i + 1 :]
        # record first fill for lim=5 and lim=8 separately (two events max / day / lim)
        for lim_off in (5.0, 8.0):
            lim = or_hi + lim_off
            n_fill = 0
            filled = None
            for thr, r2 in after_sig.iterrows():
                hm2 = _hm(thr)
                if hm2 > "13:00":
                    break
                n_fill += 1
                if n_fill > 36:  # ~3h of 5m
                    break
                if float(r2["Low"]) > lim:
                    continue
                if float(r2["Close"]) <= or_hi:
                    continue
                fill_green = float(r2["Close"]) > float(r2["Open"])
                fill_hold_or = float(r2["Low"]) >= or_lo
                after = after_sig[after_sig.index > thr]
                out5 = _outcome(lim, after)
                filled = {
                    "d": d,
                    "sig_hm": sig_hm,
                    "fill_hm": hm2,
                    "fill_bars": n_fill,
                    "lim_off": lim_off,
                    "entry": round(lim, 2),
                    "uplift": round(sig_uplift, 1),
                    "body": round(sig_body, 4),
                    "top": round(sig_top, 4),
                    "bar_rng": round(sig_rng, 1),
                    "bf": round(sig_bf, 4),
                    "or_w": round(width, 1),
                    "down_first": down_first,
                    "cont": cont,
                    "fill_green": fill_green,
                    "fill_hold_or": fill_hold_or,
                    "out": out5,
                    "win": out5 == "win",
                    "decided": out5 in ("win", "loss"),
                    "strong": (float(sess["High"].max()) - day_open) >= 150,
                }
                break
            if filled and filled["decided"]:
                events.append(filled)
    return events


def gate_match(ev: dict, g: Dict[str, Any]) -> bool:
    if ev["lim_off"] != float(g["lim"]):
        return False
    if ev["uplift"] < float(g["min_up"]):
        return False
    if ev["body"] < float(g["body"]):
        return False
    top = float(g.get("top") or 0)
    if top and ev["top"] < top:
        return False
    if ev["sig_hm"] < g["hmin"] or ev["sig_hm"] > g["hmax"]:
        return False
    if g.get("fill_green") and not ev["fill_green"]:
        return False
    if g.get("forbid_both_sides") and ev["down_first"]:
        return False
    if g.get("fill_hold_or") and not ev["fill_hold_or"]:
        return False
    if g.get("cont_only") and not ev["cont"]:
        return False
    mb = g.get("max_fill_bars")
    if mb is not None and ev["fill_bars"] > int(mb):
        return False
    min_w = float(g.get("min_or_w") or 0)
    max_w = float(g.get("max_or_w") or 9999)
    if ev["or_w"] < min_w or ev["or_w"] > max_w:
        return False
    min_rng = float(g.get("min_bar_rng") or 0)
    if ev["bar_rng"] < min_rng:
        return False
    return True


def score_window(events: List[dict], days_set: set, g: Dict[str, Any]) -> Dict[str, Any]:
    # first matching event per day (events already first-fill)
    picked = []
    seen = set()
    for ev in events:
        if ev["d"] not in days_set or ev["d"] in seen:
            continue
        if not gate_match(ev, g):
            continue
        seen.add(ev["d"])
        picked.append(ev)
    dec = [e for e in picked if e["decided"]]
    n = len(dec)
    wins = sum(1 for e in dec if e["win"])
    losses = n - wins
    hit = round(100.0 * wins / n, 2) if n else None
    return {
        "n": n,
        "wins": wins,
        "losses": losses,
        "hit_pct": hit,
        "open": sum(1 for e in picked if e["out"] == "open"),
        "strong_n": sum(1 for e in picked if e.get("strong")),
        "calls": [
            {"d": e["d"], "sig": e["sig_hm"], "fill": e["fill_hm"], "entry": e["entry"], "out": e["out"], "uplift": e["uplift"]}
            for e in dec
        ],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("loading tape…", flush=True)
    df15 = _load(TAPE15)
    df5 = _load(TAPE5)
    by15 = {d: g for d, g in df15.groupby(df15.index.strftime("%Y-%m-%d"))}
    by5 = {d: g for d, g in df5.groupby(df5.index.strftime("%Y-%m-%d"))}
    all_days = sorted(by15.keys())
    need = SESSIONS["5y"] + 20
    days = all_days[-need:] if len(all_days) > need else all_days
    print(f"sessions_used={len(days)} {days[0]}→{days[-1]}", flush=True)

    print("building event table…", flush=True)
    events = build_events(by15, by5, days)
    print(f"events={len(events)}", flush=True)

    windows = {}
    for label, n in SESSIONS.items():
        wdays = days[-n:] if len(days) >= n else days
        windows[label] = set(wdays)
        print(f"  window {label}: {len(wdays)} sessions {wdays[0]}→{wdays[-1]}", flush=True)

    # Gate grid aimed at 100% (tight)
    gates: List[Dict[str, Any]] = []
    for lim, up, body, top, hmax, fg, fb, mb in product(
        (5.0,),
        (50, 55, 60, 65, 70, 80, 90, 100),
        (0.55, 0.60, 0.65, 0.70, 0.75),
        (0.0, 0.70, 0.80),
        ("10:30", "11:00", "11:30"),
        (True,),
        (True, False),
        (6, 8, 12, 18, 24),
    ):
        # prune loosest
        if up < 60 and body < 0.65 and mb > 12:
            continue
        if up >= 90 and mb > 18:
            continue
        gates.append(
            {
                "name": f"L{int(lim)}_u{up}_b{int(body*100)}_t{int(top*100)}_{hmax}_fg{int(fg)}_fb{int(fb)}_mb{mb}",
                "lim": lim,
                "min_up": up,
                "body": body,
                "top": top,
                "hmin": "09:45",
                "hmax": hmax,
                "fill_green": fg,
                "forbid_both_sides": fb,
                "max_fill_bars": mb,
            }
        )
    curated = [
        dict(name="acc_best_prev", lim=5, min_up=60, body=0.65, top=0, hmin="09:45", hmax="11:00", fill_green=True, forbid_both_sides=True, max_fill_bars=12),
        dict(name="acc_u70_b70_t80_mb8_fb", lim=5, min_up=70, body=0.70, top=0.80, hmin="09:45", hmax="11:00", fill_green=True, forbid_both_sides=True, max_fill_bars=8),
        dict(name="acc_u80_b70_mb6_fb", lim=5, min_up=80, body=0.70, top=0.70, hmin="09:45", hmax="10:30", fill_green=True, forbid_both_sides=True, max_fill_bars=6),
        dict(name="acc_u90_b75_mb6_fb", lim=5, min_up=90, body=0.75, top=0.80, hmin="09:45", hmax="11:00", fill_green=True, forbid_both_sides=True, max_fill_bars=6),
        dict(name="acc_u100_b70_mb12_fb", lim=5, min_up=100, body=0.70, top=0.70, hmin="09:45", hmax="11:00", fill_green=True, forbid_both_sides=True, max_fill_bars=12),
        dict(name="acc_u60_b70_mb6_fb_t70", lim=5, min_up=60, body=0.70, top=0.70, hmin="09:45", hmax="11:00", fill_green=True, forbid_both_sides=True, max_fill_bars=6),
        dict(name="acc_u65_b65_mb8_fb_hold", lim=5, min_up=65, body=0.65, top=0, hmin="09:45", hmax="11:00", fill_green=True, forbid_both_sides=True, max_fill_bars=8, fill_hold_or=True),
        dict(name="acc_u70_b65_mb12_fb_w60_180", lim=5, min_up=70, body=0.65, top=0, hmin="09:45", hmax="11:00", fill_green=True, forbid_both_sides=True, max_fill_bars=12, min_or_w=60, max_or_w=180),
        dict(name="acc_u80_b65_mb12_fb_rng30", lim=5, min_up=80, body=0.65, top=0.70, hmin="09:45", hmax="11:00", fill_green=True, forbid_both_sides=True, max_fill_bars=12, min_bar_rng=30),
        dict(name="live_L5_u50_b55_fg", lim=5, min_up=50, body=0.55, top=0, hmin="09:45", hmax="11:30", fill_green=True, forbid_both_sides=False, max_fill_bars=None),
    ]
    # max_fill_bars None → treat as 36
    for c in curated:
        if c.get("max_fill_bars") is None:
            c["max_fill_bars"] = 36
        gates.append(c)

    seen = set()
    uniq = []
    for g in gates:
        if g["name"] in seen:
            continue
        seen.add(g["name"])
        uniq.append(g)
    gates = uniq
    print(f"gates={len(gates)}", flush=True)

    results = []
    for gi, g in enumerate(gates):
        row: Dict[str, Any] = {"gate": g["name"], "params": {k: v for k, v in g.items() if k != "name"}}
        all100 = True
        any_fail_n = False
        for label in ("1y", "3y", "5y"):
            sc = score_window(events, windows[label], g)
            # drop bulky calls from 3y/5y in row storage except 1y
            slim = {k: sc[k] for k in ("n", "wins", "losses", "hit_pct", "strong_n")}
            if label == "1y":
                slim["calls"] = sc["calls"]
            row[label] = slim
            hit = sc["hit_pct"]
            n = sc["n"]
            if n < MIN_N[label] or hit != 100.0:
                all100 = False
            if n < MIN_N[label]:
                any_fail_n = True
        row["hold_100_all"] = bool(
            all(
                (row[lb]["hit_pct"] == 100.0 and row[lb]["n"] >= MIN_N[lb])
                for lb in ("1y", "3y", "5y")
            )
        )
        row["hold_100_1y"] = bool(row["1y"]["hit_pct"] == 100.0 and row["1y"]["n"] >= MIN_N["1y"])
        row["hold_100_1y3y"] = bool(
            row["hold_100_1y"]
            and row["3y"]["hit_pct"] == 100.0
            and row["3y"]["n"] >= MIN_N["3y"]
        )
        results.append(row)
        if row["hold_100_all"] or row["hold_100_1y3y"] or (row["hold_100_1y"] and (gi % 40 == 0)):
            print(
                f"{g['name'][:64]:64s} 1y {row['1y']['n']}@{row['1y']['hit_pct']}  "
                f"3y {row['3y']['n']}@{row['3y']['hit_pct']}  "
                f"5y {row['5y']['n']}@{row['5y']['hit_pct']}  "
                f"ALL100={row['hold_100_all']}",
                flush=True,
            )

    results.sort(
        key=lambda r: (
            int(r["hold_100_all"]),
            int(r["hold_100_1y3y"]),
            int(r["hold_100_1y"]),
            r["5y"]["n"] if r["hold_100_all"] else 0,
            r["3y"]["n"] if r.get("hold_100_1y3y") else 0,
            r["1y"]["n"] if r["hold_100_1y"] else 0,
            (r["5y"]["hit_pct"] or 0),
            (r["3y"]["hit_pct"] or 0),
            (r["1y"]["hit_pct"] or 0),
        ),
        reverse=True,
    )

    all100 = [r for r in results if r["hold_100_all"]]
    y13 = [r for r in results if r["hold_100_1y3y"]]
    y1 = [r for r in results if r["hold_100_1y"]]

    best_all = all100[0] if all100 else None
    best_13 = y13[0] if y13 else None
    best_1 = y1[0] if y1 else None
    # among all100 prefer largest 5y n
    if all100:
        best_all = max(all100, key=lambda r: (r["5y"]["n"], r["3y"]["n"], r["1y"]["n"]))

    payload = {
        "brackets": {"sl": SL, "t1": T1},
        "min_n": MIN_N,
        "sessions": {k: len(windows[k]) for k in windows},
        "range": {"start": days[0], "end": days[-1]},
        "events": len(events),
        "gates_tested": len(results),
        "hold_100_all_n": len(all100),
        "hold_100_1y3y_n": len(y13),
        "hold_100_1y_n": len(y1),
        "best_hold_100_all": best_all,
        "best_hold_100_1y3y": best_13,
        "best_hold_100_1y": best_1,
        "top": results[:40],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# NIFTY morning strong BUY · 100% accuracy · 1y / 3y / 5y",
        "",
        "Path: **15m thrust → 5m OR+lim fill · ±30** (honest fills only).",
        "",
        f"Sample: `{days[0]}` → `{days[-1]}` · events={len(events)} · gates={len(results)}",
        f"Floors: 1y n≥{MIN_N['1y']} · 3y n≥{MIN_N['3y']} · 5y n≥{MIN_N['5y']} · hit **100%**",
        "",
        f"- Hold 100% on **1y+3y+5y**: **{len(all100)}**",
        f"- Hold 100% on **1y+3y**: **{len(y13)}**",
        f"- Hold 100% on **1y**: **{len(y1)}**",
        "",
        "## Best that holds 100% on 1y + 3y + 5y",
        "",
    ]
    if best_all:
        lines += [
            f"- **`{best_all['gate']}`**",
            f"- 1y {best_all['1y']['n']}@{best_all['1y']['hit_pct']}% · "
            f"3y {best_all['3y']['n']}@{best_all['3y']['hit_pct']}% · "
            f"5y {best_all['5y']['n']}@{best_all['5y']['hit_pct']}%",
            f"- params: `{json.dumps(best_all['params'])}`",
            "",
            "### 1y calls",
            "",
        ]
        for c in best_all["1y"].get("calls") or []:
            lines.append(f"- {c['d']} sig {c['sig']} fill {c['fill']} @ {c['entry']} · {c['out']} · uplift {c['uplift']}")
    else:
        lines.append("- **None** — no gate stayed 100% across 1y, 3y, and 5y with n floors.")

    lines += ["", "## Best that holds 100% on 1y + 3y", ""]
    if best_13:
        lines.append(
            f"- **`{best_13['gate']}`** · 1y {best_13['1y']['n']}@{best_13['1y']['hit_pct']}% · "
            f"3y {best_13['3y']['n']}@{best_13['3y']['hit_pct']}% · "
            f"5y {best_13['5y']['n']}@{best_13['5y']['hit_pct']}% (5y may be <100)"
        )
        lines.append(f"- params: `{json.dumps(best_13['params'])}`")
    else:
        lines.append("- None")

    lines += ["", "## Best that holds 100% on 1y only", ""]
    if best_1:
        lines.append(
            f"- **`{best_1['gate']}`** · 1y {best_1['1y']['n']}@{best_1['1y']['hit_pct']}% · "
            f"3y {best_1['3y']['n']}@{best_1['3y']['hit_pct']}% · "
            f"5y {best_1['5y']['n']}@{best_1['5y']['hit_pct']}%"
        )
        lines.append(f"- params: `{json.dumps(best_1['params'])}`")
    else:
        lines.append("- None")

    lines += [
        "",
        "## Ranking (100%-first)",
        "",
        "| gate | 1y | 3y | 5y | all100 |",
        "|---|---:|---:|---:|---|",
    ]
    for r in results[:35]:
        lines.append(
            f"| `{r['gate']}` | {r['1y']['n']}@{r['1y']['hit_pct']} | "
            f"{r['3y']['n']}@{r['3y']['hit_pct']} | {r['5y']['n']}@{r['5y']['hit_pct']} | "
            f"{r['hold_100_all']} |"
        )
    lines += ["", f"JSON: `{OUT_JSON}`", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT_MD, flush=True)
    print("ALL100", len(all100), "Y13", len(y13), "Y1", len(y1), flush=True)
    if best_all:
        print("BEST_ALL", best_all["gate"], best_all["1y"], best_all["3y"], best_all["5y"], flush=True)
    elif best_13:
        print("BEST_13", best_13["gate"], best_13["1y"], best_13["3y"], best_13["5y"], flush=True)
    elif best_1:
        print("BEST_1", best_1["gate"], best_1["1y"], best_1["3y"], best_1["5y"], flush=True)


if __name__ == "__main__":
    main()
