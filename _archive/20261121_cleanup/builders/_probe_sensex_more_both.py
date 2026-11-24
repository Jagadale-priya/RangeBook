"""Probe paths that could raise BOTH N and hit vs 909@76.13%."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live" / "tests" / "builders")]
import path_setup  # noqa: F401,E402
from research_bn_sensex_final_brackets import load_tape, normalize_cand, path_score_pool  # noqa: E402
from research_sensex_modal_1y_deep import hit_pct  # noqa: E402

END = "2026-11-19"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_3M = (pd.Timestamp(END) - timedelta(days=92)).strftime("%Y-%m-%d")
SL = T1 = 50.0
CANDS = ROOT / "stock_signal_data/fno_validate/research/sensex_side_models/sensex_full_live_candidates.json"
TAPE = ROOT / "stock_signal_data/fno_validate/SENSEX_5m_kite.csv"


def sessions(bars, a, b):
    return sorted({str(pd.Timestamp(t).date()) for t in bars.index if a <= str(pd.Timestamp(t).date()) <= b})


def key(r):
    return (str(r.get("day"))[:10], str(r.get("hm") or "")[:5], str(r.get("decision") or "").upper())


def fb_break(bars, day, min_bf=0.0, min_w=0.0):
    db = bars[bars.index.strftime("%Y-%m-%d") == day]
    if len(db) < 2:
        return None
    hi, lo = float(db["High"].iloc[0]), float(db["Low"].iloc[0])
    w = hi - lo
    if w < min_w:
        return None
    entry_ts = None
    for want in ("09:45", "09:30", "10:00"):
        hit = db[db.index.strftime("%H:%M") == want]
        if len(hit):
            entry_ts = hit.index[0]
            break
    if entry_ts is None:
        entry_ts = db.index[min(1, len(db) - 1)]
    c = float(db.loc[entry_ts, "Close"])
    if c > hi:
        side, bf = "BUY", (c - hi) / w if w else 0
    elif c < lo:
        side, bf = "SELL", (lo - c) / w if w else 0
    else:
        return None
    if bf < min_bf:
        return None
    hm = f"{entry_ts.hour:02d}:{entry_ts.minute:02d}"
    return {"day": day, "hm": hm, "decision": side, "side": side, "p_t1": 0.55, "source": "fallback", "first_break": True}


def fb_mid(bars, day, min_w=50.0):
    db = bars[bars.index.strftime("%Y-%m-%d") == day]
    if len(db) < 2:
        return None
    hi, lo = float(db["High"].iloc[0]), float(db["Low"].iloc[0])
    w = hi - lo
    if w < min_w:
        return None
    entry_ts = None
    for want in ("09:45", "09:30", "10:00"):
        hit = db[db.index.strftime("%H:%M") == want]
        if len(hit):
            entry_ts = hit.index[0]
            break
    if entry_ts is None:
        entry_ts = db.index[min(1, len(db) - 1)]
    c = float(db.loc[entry_ts, "Close"])
    if c > hi or c < lo:
        return None
    mid = (hi + lo) / 2
    side = "BUY" if c >= mid else "SELL"
    hm = f"{entry_ts.hour:02d}:{entry_ts.minute:02d}"
    return {"day": day, "hm": hm, "decision": side, "side": side, "p_t1": 0.50, "source": "fallback", "first_break": True}


def st(scored, a, b, sess):
    rr = [r for r in scored if a <= str(r.get("day") or "")[:10] <= b]
    return len(rr), hit_pct(rr), len({str(r.get("day"))[:10] for r in rr}), len(sess)


def main():
    bars, ix = load_tape(TAPE)
    if getattr(bars.index, "tz", None) is not None:
        bars = bars.copy()
        bars.index = bars.index.tz_localize(None)
    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    by = defaultdict(list)
    for row in raw:
        n = normalize_cand(row)
        if not n or n["day"] < START_3Y or n["day"] > END:
            continue
        n["first_break"] = bool(row.get("first_break"))
        n["p_t1"] = float(n.get("p_t1") or 0)
        n["regime"] = row.get("regime")
        n["or_ext"] = row.get("or_ext")
        if row.get("when"):
            ts = pd.Timestamp(row["when"])
            n["hm"] = f"{ts.hour:02d}:{ts.minute:02d}"
        by[n["day"]].append(n)

    days = sessions(bars, START_3Y, END)
    # universe: duals p>=0.40 + fb variants
    uni = []
    seen = set()
    for day in days:
        for r in by[day]:
            if r["p_t1"] < 0.40:
                continue
            p = {**r, "source": "dual"}
            k = (*key(p), "dual")
            if k not in seen:
                seen.add(k)
                uni.append(p)
        for fn in (
            lambda d: fb_break(bars, d, 0.0, 0.0),
            lambda d: fb_break(bars, d, 0.20, 0.0),
            lambda d: fb_mid(bars, d, 50.0),
            lambda d: fb_mid(bars, d, 80.0),
        ):
            fb = fn(day)
            if not fb:
                continue
            k = (*key(fb), "fallback")
            if k not in seen:
                seen.add(k)
                uni.append(fb)
    print("scoring", len(uni), flush=True)
    scored = path_score_pool(bars, ix, uni, SL, T1)
    sm = {}
    meta = {(*key(p), p["source"]): p for p in uni}
    for r in scored:
        for src in ("dual", "fallback"):
            m = meta.get((*key(r), src))
            if m:
                rr = dict(r)
                rr["source"] = src
                rr["p_model"] = m.get("p_t1")
                rr["first_break"] = m.get("first_break")
                rr["regime"] = m.get("regime")
                rr["or_ext"] = m.get("or_ext")
                sm[(*key(r), src)] = rr

    def mat(picks):
        out = []
        for p in picks:
            b = sm.get((*key(p), "dual" if p.get("source") != "fallback" else "fallback"))
            if b:
                out.append({**b, "source": p.get("source")})
        return out

    def build(dual_pmin, fb="break", bf=0.0, mid_w=None, drop_vol=False, only_first=False, ext_max=None):
        picks = []
        for day in days:
            duals = []
            for r in by[day]:
                if r["p_t1"] < dual_pmin:
                    continue
                if only_first and not r.get("first_break"):
                    continue
                if drop_vol and r.get("regime") == "volatile":
                    continue
                if ext_max is not None and r.get("or_ext") is not None and float(r["or_ext"]) > ext_max:
                    continue
                duals.append({**r, "source": "dual"})
            duals = sorted(duals, key=lambda x: (x.get("hm") or "", -x["p_t1"]))
            fb_row = None
            if fb == "break":
                fb_row = fb_break(bars, day, bf, 0.0)
            elif fb == "mid":
                fb_row = fb_mid(bars, day, mid_w or 50)
            elif fb == "break+mid":
                fb_row = fb_break(bars, day, bf, 0.0)
                mid = fb_mid(bars, day, mid_w or 50)
                # keep both later
                rows = list(duals)
                keys = {key(x) for x in rows}
                if fb_row and key(fb_row) not in keys:
                    # merge if same
                    merged = False
                    for i, d in enumerate(rows):
                        if key(d) == key(fb_row):
                            rows[i] = {**d, "source": "dual+fallback"}
                            merged = True
                            break
                    if not merged:
                        rows.append(fb_row)
                    keys = {key(x) for x in rows}
                if mid and key(mid) not in keys:
                    rows.append(mid)
                picks.extend(rows)
                continue
            rows = list(duals)
            if fb_row:
                merged = False
                for i, d in enumerate(rows):
                    if key(d) == key(fb_row):
                        rows[i] = {**d, "source": "dual+fallback"}
                        merged = True
                        break
                if not merged:
                    rows.append(fb_row)
            picks.extend(rows)
        return picks

    sess1, sess3m, sess3y = sessions(bars, START_1Y, END), sessions(bars, START_3M, END), sessions(bars, START_3Y, END)
    tests = [
        ("base_p45_break", dict(dual_pmin=0.45, fb="break")),
        ("p42_break", dict(dual_pmin=0.42, fb="break")),
        ("p40_break", dict(dual_pmin=0.40, fb="break")),
        ("p45_break_bf20", dict(dual_pmin=0.45, fb="break", bf=0.20)),
        ("p42_break_bf20", dict(dual_pmin=0.42, fb="break", bf=0.20)),
        ("p40_break_bf20", dict(dual_pmin=0.40, fb="break", bf=0.20)),
        ("p45_break_mid50", dict(dual_pmin=0.45, fb="break+mid", mid_w=50)),
        ("p45_break_mid80", dict(dual_pmin=0.45, fb="break+mid", mid_w=80)),
        ("p42_break_mid80", dict(dual_pmin=0.42, fb="break+mid", mid_w=80)),
        ("p45_novol_break", dict(dual_pmin=0.45, fb="break", drop_vol=True)),
        ("p42_novol_break_bf10", dict(dual_pmin=0.42, fb="break", bf=0.10, drop_vol=True)),
        ("p45_break_ext5", dict(dual_pmin=0.45, fb="break", ext_max=5.0)),
        ("p40_only_first_break", dict(dual_pmin=0.40, fb="break", only_first=True)),
        ("p45_plus_p40first_break", None),  # custom
    ]
    # custom: all p45 duals + p40 first_break duals + fb break bf20
    def custom_p45_plus_p40first():
        picks = []
        for day in days:
            rows = []
            seen_k = set()
            for r in by[day]:
                ok = r["p_t1"] >= 0.45 or (r["p_t1"] >= 0.40 and r.get("first_break"))
                if not ok:
                    continue
                p = {**r, "source": "dual"}
                if key(p) in seen_k:
                    continue
                seen_k.add(key(p))
                rows.append(p)
            fb = fb_break(bars, day, 0.20, 0.0)
            if fb:
                merged = False
                for i, d in enumerate(rows):
                    if key(d) == key(fb):
                        rows[i] = {**d, "source": "dual+fallback"}
                        merged = True
                        break
                if not merged:
                    rows.append(fb)
            picks.extend(rows)
        return picks

    print(f"{'name':<28} {'1y_n':>5} {'1y_hit':>7} {'3y_n':>5} {'3y_hit':>7} {'3m_hit':>7} both?")
    for name, kw in tests:
        if name == "p45_plus_p40first_break":
            picks = custom_p45_plus_p40first()
        else:
            picks = build(**kw)
        sc = mat(picks)
        n1, h1, _, _ = st(sc, START_1Y, END, sess1)
        n3, h3, _, _ = st(sc, START_3Y, END, sess3y)
        _, h3m, _, _ = st(sc, START_3M, END, sess3m)
        both = h1 is not None and n1 >= 909 and h1 >= 76.13 and (h3 or 0) >= 72.5
        print(f"{name:<28} {n1:5d} {h1:7} {n3:5d} {h3:7} {h3m:7} {both}")


if __name__ == "__main__":
    main()
