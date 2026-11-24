"""Quick: can ±50 chase/continuation hold 100% on 1y/3y/5y for runaway shape?"""
from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Set

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]
import path_setup  # noqa: F401,E402

OUT = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_MORNING_RUNAWAY_PM50_100.md"
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_kite.csv"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
SL = T1 = 50.0
SESSIONS = {"1y": 252, "3y": 756, "5y": 1260}
MIN_N = {"1y": 5, "3y": 8, "5y": 10}


def load(p):
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.columns = [str(c).strip().title() for c in df.columns]
    df.index = df.index.tz_localize("Asia/Kolkata") if df.index.tz is None else df.index.tz_convert("Asia/Kolkata")
    return df.sort_index()


def hm(ts):
    t = pd.Timestamp(ts).tz_convert("Asia/Kolkata")
    return f"{int(t.hour):02d}:{int(t.minute):02d}"


def outcome(entry, after):
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


def main():
    df15, df5 = load(TAPE15), load(TAPE5)
    by15 = {d: g for d, g in df15.groupby(df15.index.strftime("%Y-%m-%d"))}
    by5 = {d: g for d, g in df5.groupby(df5.index.strftime("%Y-%m-%d"))}
    days = sorted(by15)[-(SESSIONS["5y"] + 20) :]
    events = []
    print("build", len(days), flush=True)
    for di, d in enumerate(days):
        if di % 250 == 0:
            print(" ", di, flush=True)
        sess = by15[d]
        if len(sess) < 6:
            continue
        s5 = by5.get(d, sess.iloc[0:0])
        or_hi = float(sess["High"].iloc[0])
        day_open = float(sess["Open"].iloc[0])
        first_up = first_dn = None
        for i in range(len(sess)):
            c = float(sess["Close"].iloc[i])
            if first_up is None and c > or_hi:
                first_up = i
            if first_dn is None and c < or_lo if False else (c < float(sess["Low"].iloc[0])):
                first_dn = i
        or_lo = float(sess["Low"].iloc[0])
        down_first = first_up is not None and first_dn is not None and first_dn < first_up
        if down_first:
            continue
        n_close = 0
        for i, ts in enumerate(sess.index):
            h = hm(ts)
            if h < "09:45" or h > "12:00" or i < 2:
                continue
            row = sess.iloc[i]
            c, o, hi, lo = float(row["Close"]), float(row["Open"]), float(row["High"]), float(row["Low"])
            if c <= or_hi or c <= o:
                continue
            uplift = c - day_open
            if uplift < 60:
                continue
            prior2 = max(float(sess["High"].iloc[j]) for j in range(i - 2, i))
            if c <= prior2:
                continue
            rng = max(hi - lo, 1e-9)
            body = abs(c - o) / rng
            if body < 0.40:
                continue
            after = s5[s5.index > ts] if len(s5) else sess.iloc[i + 1 :]
            # close
            if n_close < 5:
                out = outcome(c, after)
                if out in ("win", "loss"):
                    events.append(
                        dict(
                            d=d,
                            mode="close",
                            sig_hm=h,
                            entry=c,
                            uplift=uplift,
                            body=body,
                            day_hi_up=float(sess["High"].iloc[: i + 1].max()) - day_open,
                            out=out,
                        )
                    )
                    n_close += 1
            # brk 5m high
            if len(s5):
                for thr, r2 in s5[s5.index > ts].iterrows():
                    if hm(thr) > "13:00":
                        break
                    c2, o2 = float(r2["Close"]), float(r2["Open"])
                    if c2 > hi and c2 > o2:
                        after2 = s5[s5.index > thr]
                        out2 = outcome(c2, after2)
                        if out2 in ("win", "loss"):
                            events.append(
                                dict(
                                    d=d,
                                    mode="brk5",
                                    sig_hm=h,
                                    entry=c2,
                                    uplift=uplift,
                                    body=body,
                                    day_hi_up=float(sess["High"].iloc[: i + 1].max()) - day_open,
                                    out=out2,
                                )
                            )
                        break
    print("events", len(events), flush=True)
    windows = {lb: set(days[-n:]) for lb, n in SESSIONS.items()}

    def score(days_set, g):
        seen, picked = set(), []
        for e in events:
            if e["d"] not in days_set or e["d"] in seen:
                continue
            if e["mode"] != g["mode"]:
                continue
            if e["sig_hm"] < g["hmin"] or e["sig_hm"] > g["hmax"]:
                continue
            if e["uplift"] < g["min_up"] or e["body"] < g["min_body"]:
                continue
            if e["body"] > g["max_body"]:
                continue
            if e["day_hi_up"] < g["min_hi"]:
                continue
            seen.add(e["d"])
            picked.append(e)
        n = len(picked)
        w = sum(1 for e in picked if e["out"] == "win")
        return n, round(100 * w / n, 2) if n else None

    gates = []
    for mode, up, body, maxb, hmax, hi in product(
        ("close", "brk5"),
        (100, 120, 150, 180),
        (0.45, 0.55, 0.65),
        (0.75, 0.85, 9.0),
        ("11:00", "11:30", "12:00"),
        (0, 120, 150),
    ):
        if maxb < body:
            continue
        gates.append(
            dict(
                name=f"pm50_{mode}_u{up}_b{int(body*100)}_{hmax}_hi{hi}",
                mode=mode,
                min_up=up,
                min_body=body,
                max_body=maxb,
                hmin="09:45",
                hmax=hmax,
                min_hi=hi,
            )
        )
    all100 = []
    best1 = []
    for g in gates:
        s = {}
        for lb in ("1y", "3y", "5y"):
            n, hit = score(windows[lb], g)
            s[lb] = (n, hit)
        ok = all(s[lb][1] == 100 and s[lb][0] >= MIN_N[lb] for lb in ("1y", "3y", "5y"))
        if ok:
            all100.append((s["5y"][0], s["3y"][0], s["1y"][0], g["name"], g, s))
        if s["1y"][1] == 100 and s["1y"][0] >= 5:
            best1.append((s["3y"][1] or 0, s["5y"][1] or 0, s["1y"][0], g["name"], s))
    all100.sort(reverse=True)
    best1.sort(reverse=True)
    print("ALL100", len(all100), "Y1", len(best1), flush=True)
    lines = [
        "# Runaway morning · ±50 chase · 100% check",
        "",
        f"ALL100 1y+3y+5y: **{len(all100)}** · 1y@100 n≥5: **{len(best1)}**",
        "",
    ]
    if all100:
        t = all100[0]
        lines += [f"## Best ±50 all-100", f"- `{t[3]}` 1y {t[5]['1y']} 3y {t[5]['3y']} 5y {t[5]['5y']}", ""]
    else:
        lines.append("## No ±50 gate holds 100% on 1y+3y+5y")
        lines.append("")
    if best1:
        t = best1[0]
        lines += [
            "## Best 1y@100 by 3y/5y hit",
            f"- `{t[3]}` 1y n={t[2]}@100 · 3y@{t[0]} · 5y@{t[1]}",
            "",
        ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT, flush=True)
    if best1:
        print("BEST1", best1[0][3], best1[0][4], flush=True)


if __name__ == "__main__":
    main()
