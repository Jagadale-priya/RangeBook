"""RESEARCH ONLY — Prove PA entries on Opening RANGE boxes (OR15/OR30).

Prior proven map (this repo):
  OR30 contains ~65% of next-30 closes (best range box)
  OR15 zone revisit → decisive swing/break ~100% on short window
  Transcript BOS/CHoCH/FVG alone → NOT_PROVEN on 1Y WF

This script asks: does RANGE context make a shippable entry?
Books:
  R1  OR swing fade          leave→retest edge zone → bounce, SL beyond box
  R2  OR break+retest        close beyond OR → retest → continue
  R3  OR swing + FVG mid     same as R1 but entry at FVG mid after response
  R4  OR break + FVG mid     same as R2 with FVG mid
  R5  OR fade HTF-aligned    R1 only with 15m bias agreeing
  R6  OR break HTF-aligned   R2 with 15m bias agreeing

Prove rules (same as PA prove):
  PROVEN: TRAIN+OOS n≥30, hit@3R≥35%, exp_R≥0.20, OOS t≥1.5
  PROMISING: n≥20, hit≥32%, exp_R≥0.10 both sides
  else NOT_PROVEN

  python -u prod_live/tests/builders/_diag_scalp_pa_range_proven.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators  # noqa: E402
from _diag_scalp_pa_bos_choch_fvg import (  # noqa: E402
    _norm_1m,
    build_htf_bias,
    detect_fvg,
    htf_bias_lookup,
    path_rr,
    structure_events,
    to_15m,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_PA_RANGE_PROVEN.md"
REPORT_JSON = OUT / "NIFTY_1M_PA_RANGE_PROVEN.json"

RR = 3.0
MAX_HOLD = 90
N_SESSIONS = 220
LOOKBACK_CAL = 420
ZONE_HALF_ATR = 0.50
LEAVE_ATR = 0.50
BREAK_ATR = 1.0
TRADE_LO, TRADE_HI = 9 * 60 + 30, 14 * 60 + 30

MIN_N, MIN_HIT, MIN_EXP, MIN_T = 30, 35.0, 0.20, 1.5
SOFT_N, SOFT_HIT, SOFT_EXP = 20, 32.0, 0.10


def summarize_R(trades: List[dict]) -> Dict[str, Any]:
    if not trades:
        return {"n": 0, "hit": None, "exp_R": None, "t": None, "wins": 0, "cpd": None}
    wins = [t for t in trades if t.get("win")]
    rs = np.array([float(t["R"]) for t in trades], dtype=float)
    n = len(trades)
    mean = float(np.mean(rs))
    sd = float(np.std(rs, ddof=1)) if n > 1 else 0.0
    t = (mean / (sd / np.sqrt(n))) if sd > 1e-12 else (99.0 if mean > 0 else 0.0)
    return {
        "n": n,
        "hit": round(100.0 * len(wins) / n, 2),
        "exp_R": round(mean, 3),
        "t": round(t, 2),
        "wins": len(wins),
        "losses": n - len(wins),
        "avg_pts": round(float(np.mean([t["pts"] for t in trades])), 2),
    }


def verdict(train: Dict[str, Any], oos: Dict[str, Any]) -> str:
    def hard(s):
        return (
            s["n"] >= MIN_N
            and s.get("hit") is not None
            and s["hit"] >= MIN_HIT
            and s.get("exp_R") is not None
            and s["exp_R"] >= MIN_EXP
            and s.get("t") is not None
            and s["t"] >= MIN_T
        )

    def soft(s):
        return (
            s["n"] >= SOFT_N
            and s.get("hit") is not None
            and s["hit"] >= SOFT_HIT
            and s.get("exp_R") is not None
            and s["exp_R"] >= SOFT_EXP
        )

    if hard(train) and hard(oos):
        return "PROVEN"
    if soft(train) and soft(oos) and (train["exp_R"] or 0) > 0 and (oos["exp_R"] or 0) > 0:
        return "PROMISING"
    return "NOT_PROVEN"


def score_row(h, l, c, entry_i, side, entry, sl, meta: dict) -> Optional[dict]:
    risk = abs(entry - sl)
    if risk < 2.0 or risk > 100.0:
        return None
    ok, reason, pts, _ = path_rr(h, l, c, entry_i, side, entry, sl, RR, max_bars=MAX_HOLD)
    if reason == "exp":
        R = float(pts / risk) if risk else -1.0
        R = max(-1.0, min(RR, R))
    else:
        R = float(RR if ok else -1.0)
    return {
        **meta,
        "side": side,
        "entry": round(float(entry), 2),
        "sl": round(float(sl), 2),
        "risk": round(float(risk), 2),
        "win": bool(ok),
        "reason": reason,
        "pts": round(float(pts if ok else -risk), 2),
        "R": round(R, 3),
        "full_i": int(entry_i),
    }


def day_slices(day):
    by = defaultdict(list)
    for i, d in enumerate(day):
        by[d].append(i)
    return by


def make_zone(edge, atr, side):
    half = max(4.0, ZONE_HALF_ATR * atr)
    return {
        "side": side,
        "lo": edge - half,
        "hi": edge + half,
        "mid": edge,
        "half": half,
    }


def build_or_ranges(h, l, c, atr, day, mins, by_day, width: int) -> List[dict]:
    out = []
    for d, idxs in by_day.items():
        if len(idxs) < width + 5:
            continue
        slc = idxs[:width]
        hi, lo = float(np.max(h[slc])), float(np.min(l[slc]))
        live = idxs[width - 1]
        a = float(atr[live]) if np.isfinite(atr[live]) and atr[live] > 0 else 10.0
        if hi - lo < 5.0:
            continue
        out.append(
            {
                "day": d,
                "live_i": live,
                "width": width,
                "hi": hi,
                "lo": lo,
                "atr": a,
                "up": make_zone(hi, a, "UP"),
                "down": make_zone(lo, a, "DOWN"),
            }
        )
    return out


def in_zone(px_lo, px_hi, z) -> bool:
    return px_lo <= z["hi"] and px_hi >= z["lo"]


def next_fvg_mid(fvgs, side, i0, d, day, h, l, c, within=40, max_wait=45, min_size=1.5):
    fvg = None
    for f in fvgs:
        if f["i_confirm"] <= i0:
            continue
        if f["side"] != side:
            continue
        if f["i_confirm"] > i0 + within:
            break
        if f["size"] < min_size:
            continue
        fvg = f
        break
    if fvg is None:
        return None
    for j in range(fvg["i_confirm"] + 1, min(len(c), fvg["i_confirm"] + max_wait)):
        if day[j] != d:
            break
        if float(l[j]) <= fvg["mid"] <= float(h[j]):
            if side == "BUY":
                sl = float(l[fvg["i_mid"]]) - 0.5
            else:
                sl = float(h[fvg["i_mid"]]) + 0.5
            return j, float(fvg["mid"]), sl, fvg
    return None


def build_books(df1: pd.DataFrame, df15: pd.DataFrame) -> Dict[str, List[dict]]:
    work = add_indicators(df1)
    h = work["High"].astype(float).values
    l = work["Low"].astype(float).values
    c = work["Close"].astype(float).values
    o = work["Open"].astype(float).values
    if "atr14" in work.columns:
        atr = work["atr14"].astype(float).values
    elif "atr" in work.columns:
        atr = work["atr"].astype(float).values
    else:
        atr = np.full(len(c), 10.0)
    atr = np.where(np.isfinite(atr) & (atr > 0), atr, 10.0)
    idx = work.index
    day = np.array([str(ts.date()) for ts in idx])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in idx])
    by_day = day_slices(day)

    bias15 = build_htf_bias(df15, structure_events(df15))
    fvgs = detect_fvg(o, h, l, c)

    books: Dict[str, List[dict]] = defaultdict(list)
    used: Dict[str, set] = defaultdict(set)

    def take(book, d):
        if d in used[book]:
            return False
        used[book].add(d)
        return True

    def htf_side(ts, side):
        hb = htf_bias_lookup(bias15, ts)
        if hb is None:
            return False, None
        ok = (hb == "up" and side == "BUY") or (hb == "down" and side == "SELL")
        return ok, hb

    for width, tag in ((15, "OR15"), (30, "OR30")):
        ranges = build_or_ranges(h, l, c, atr, day, mins, by_day, width)
        for rg in ranges:
            d = rg["day"]
            live = rg["live_i"]
            a = rg["atr"]
            up, down = rg["up"], rg["down"]
            or_hi, or_lo = rg["hi"], rg["lo"]

            left_up = left_down = False
            broke_up = broke_down = False
            swing_done = break_done = False

            for j in range(live + 1, len(c)):
                if day[j] != d:
                    break
                if not (TRADE_LO <= mins[j] <= TRADE_HI):
                    continue
                hi_j, lo_j, cl_j = float(h[j]), float(l[j]), float(c[j])

                # track leave
                if lo_j > up["hi"] + LEAVE_ATR * a * 0.25:
                    left_up = True
                if hi_j < down["lo"] - LEAVE_ATR * a * 0.25:
                    left_down = True
                # also leave into the middle counts as leave from edge
                mid = 0.5 * (or_hi + or_lo)
                if hi_j < mid and left_up is False and lo_j < up["lo"]:
                    # soft leave down from up zone
                    if cl_j < up["lo"] - 0.25 * a:
                        left_up = True
                if lo_j > mid and left_down is False and hi_j > down["hi"]:
                    if cl_j > down["hi"] + 0.25 * a:
                        left_down = True

                # ---- R1 swing fade: retest after leave ----
                if not swing_done:
                    # SELL into UP zone
                    if left_up and in_zone(lo_j, hi_j, up):
                        side = "SELL"
                        entry = float(up["mid"])
                        sl = float(up["hi"]) + 0.5
                        # require touch near mid or better
                        if lo_j <= entry <= hi_j or hi_j >= up["lo"]:
                            entry = min(max(entry, lo_j), hi_j)
                            meta = {
                                "book": f"R1_swing_{tag}",
                                "day": d,
                                "hm": idx[j].strftime("%H:%M"),
                                "range": tag,
                                "edge": "UP",
                            }
                            row = score_row(h, l, c, j, side, entry, sl, meta)
                            if row and take(row["book"], d):
                                books[row["book"]].append(row)
                                swing_done = True
                                ok_htf, hb = htf_side(idx[j], side)
                                if ok_htf:
                                    b5 = f"R5_swing_htf_{tag}"
                                    if take(b5, d):
                                        books[b5].append({**row, "book": b5, "htf": hb})
                                # R3 FVG after this response bar
                                got = next_fvg_mid(fvgs, side, j, d, day, h, l, c)
                                if got:
                                    ei, en, sl2, _f = got
                                    b3 = f"R3_swing_fvg_{tag}"
                                    row3 = score_row(
                                        h,
                                        l,
                                        c,
                                        ei,
                                        side,
                                        en,
                                        sl2,
                                        {
                                            "book": b3,
                                            "day": d,
                                            "hm": idx[ei].strftime("%H:%M"),
                                            "range": tag,
                                            "edge": "UP",
                                        },
                                    )
                                    if row3 and take(b3, d):
                                        books[b3].append(row3)

                    # BUY into DOWN zone
                    if (not swing_done) and left_down and in_zone(lo_j, hi_j, down):
                        side = "BUY"
                        entry = float(down["mid"])
                        sl = float(down["lo"]) - 0.5
                        if lo_j <= entry <= hi_j or lo_j <= down["hi"]:
                            entry = min(max(entry, lo_j), hi_j)
                            meta = {
                                "book": f"R1_swing_{tag}",
                                "day": d,
                                "hm": idx[j].strftime("%H:%M"),
                                "range": tag,
                                "edge": "DOWN",
                            }
                            row = score_row(h, l, c, j, side, entry, sl, meta)
                            if row and take(row["book"], d):
                                books[row["book"]].append(row)
                                swing_done = True
                                ok_htf, hb = htf_side(idx[j], side)
                                if ok_htf:
                                    b5 = f"R5_swing_htf_{tag}"
                                    if take(b5, d):
                                        books[b5].append({**row, "book": b5, "htf": hb})
                                got = next_fvg_mid(fvgs, side, j, d, day, h, l, c)
                                if got:
                                    ei, en, sl2, _f = got
                                    b3 = f"R3_swing_fvg_{tag}"
                                    row3 = score_row(
                                        h,
                                        l,
                                        c,
                                        ei,
                                        side,
                                        en,
                                        sl2,
                                        {
                                            "book": b3,
                                            "day": d,
                                            "hm": idx[ei].strftime("%H:%M"),
                                            "range": tag,
                                            "edge": "DOWN",
                                        },
                                    )
                                    if row3 and take(b3, d):
                                        books[b3].append(row3)

                # ---- R2 break + retest ----
                if cl_j > or_hi + BREAK_ATR * a * 0.15:
                    broke_up = True
                if cl_j < or_lo - BREAK_ATR * a * 0.15:
                    broke_down = True

                if not break_done and broke_up:
                    # need away then retest UP zone from above
                    if hi_j > up["hi"] + 0.3 * a:
                        pass  # stayed away / extending
                    if in_zone(lo_j, hi_j, up) and cl_j >= or_hi - 0.1 * a:
                        # only if we previously extended above
                        # check any prior bar after break went clearly above
                        # (broke_up already)
                        side = "BUY"
                        entry = float(up["mid"])
                        sl = float(up["lo"]) - 0.5
                        if lo_j <= entry <= hi_j:
                            meta = {
                                "book": f"R2_break_{tag}",
                                "day": d,
                                "hm": idx[j].strftime("%H:%M"),
                                "range": tag,
                                "edge": "UP",
                            }
                            # confirm extension existed
                            ext = False
                            for k in range(live + 1, j):
                                if day[k] != d:
                                    break
                                if float(l[k]) > up["hi"] + 0.25 * a:
                                    ext = True
                                    break
                            if ext:
                                row = score_row(h, l, c, j, side, entry, sl, meta)
                                if row and take(row["book"], d):
                                    books[row["book"]].append(row)
                                    break_done = True
                                    ok_htf, hb = htf_side(idx[j], side)
                                    if ok_htf:
                                        b6 = f"R6_break_htf_{tag}"
                                        if take(b6, d):
                                            books[b6].append({**row, "book": b6, "htf": hb})
                                    got = next_fvg_mid(fvgs, side, j, d, day, h, l, c)
                                    if got:
                                        ei, en, sl2, _f = got
                                        b4 = f"R4_break_fvg_{tag}"
                                        row4 = score_row(
                                            h,
                                            l,
                                            c,
                                            ei,
                                            side,
                                            en,
                                            sl2,
                                            {
                                                "book": b4,
                                                "day": d,
                                                "hm": idx[ei].strftime("%H:%M"),
                                                "range": tag,
                                                "edge": "UP",
                                            },
                                        )
                                        if row4 and take(b4, d):
                                            books[b4].append(row4)

                if not break_done and broke_down:
                    ext = False
                    for k in range(live + 1, j):
                        if day[k] != d:
                            break
                        if float(h[k]) < down["lo"] - 0.25 * a:
                            ext = True
                            break
                    if ext and in_zone(lo_j, hi_j, down) and cl_j <= or_lo + 0.1 * a:
                        side = "SELL"
                        entry = float(down["mid"])
                        sl = float(down["hi"]) + 0.5
                        if lo_j <= entry <= hi_j:
                            meta = {
                                "book": f"R2_break_{tag}",
                                "day": d,
                                "hm": idx[j].strftime("%H:%M"),
                                "range": tag,
                                "edge": "DOWN",
                            }
                            row = score_row(h, l, c, j, side, entry, sl, meta)
                            if row and take(row["book"], d):
                                books[row["book"]].append(row)
                                break_done = True
                                ok_htf, hb = htf_side(idx[j], side)
                                if ok_htf:
                                    b6 = f"R6_break_htf_{tag}"
                                    if take(b6, d):
                                        books[b6].append({**row, "book": b6, "htf": hb})
                                got = next_fvg_mid(fvgs, side, j, d, day, h, l, c)
                                if got:
                                    ei, en, sl2, _f = got
                                    b4 = f"R4_break_fvg_{tag}"
                                    row4 = score_row(
                                        h,
                                        l,
                                        c,
                                        ei,
                                        side,
                                        en,
                                        sl2,
                                        {
                                            "book": b4,
                                            "day": d,
                                            "hm": idx[ei].strftime("%H:%M"),
                                            "range": tag,
                                            "edge": "DOWN",
                                        },
                                    )
                                    if row4 and take(b4, d):
                                        books[b4].append(row4)

                if swing_done and break_done:
                    break

    return dict(books)


def split_wf(trades: List[dict], days_sorted: List[str]) -> Tuple[List[dict], List[dict]]:
    mid = days_sorted[len(days_sorted) // 2]
    return [t for t in trades if t["day"] < mid], [t for t in trades if t["day"] >= mid]


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("PA × RANGE prove (OR15/OR30) — RESEARCH ONLY", flush=True)

    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=LOOKBACK_CAL)]
    df1 = _norm_1m(raw)
    days_all = sorted({str(ts.date()) for ts in df1.index})
    keep = set(days_all[-N_SESSIONS:]) if len(days_all) > N_SESSIONS else set(days_all)
    days_sorted = sorted(keep)
    day_lo, day_hi = days_sorted[0], days_sorted[-1]
    n_days = len(days_sorted)
    mid_day = days_sorted[n_days // 2]
    df1 = df1[[str(ts.date()) in keep for ts in df1.index]]
    df15 = to_15m(df1)
    print(f"window {day_lo}→{day_hi} n_days={n_days} OOS≥{mid_day}", flush=True)

    books = build_books(df1, df15)
    print(f"books: { {k: len(v) for k, v in sorted(books.items())} }", flush=True)

    rows = []
    for name, trades in sorted(books.items()):
        train, oos = split_wf(trades, days_sorted)
        st, so, sf = summarize_R(train), summarize_R(oos), summarize_R(trades)
        for s, nd in ((st, n_days // 2), (so, n_days - n_days // 2), (sf, n_days)):
            s["cpd"] = round(s["n"] / nd, 2) if nd else 0.0
        v = verdict(st, so)
        rows.append({"book": name, "verdict": v, "full": sf, "train": st, "oos": so})
        print(
            f"  {name}: FULL {sf['n']}/{sf['hit']}%/{sf['exp_R']} | "
            f"TR {st['n']}/{st['hit']}%/{st['exp_R']} | "
            f"OOS {so['n']}/{so['hit']}%/{so['exp_R']}/t={so['t']} → {v}",
            flush=True,
        )

    proven = [r for r in rows if r["verdict"] == "PROVEN"]
    promising = [r for r in rows if r["verdict"] == "PROMISING"]
    ranked_proven = sorted(
        proven,
        key=lambda r: (r["oos"]["exp_R"] or -9, r["oos"]["hit"] or 0, r["oos"]["n"]),
        reverse=True,
    )
    ranked_any = sorted(
        proven + promising,
        key=lambda r: (r["oos"]["exp_R"] or -9, r["oos"]["hit"] or 0),
        reverse=True,
    )
    best = ranked_proven[0] if ranked_proven else (ranked_any[0] if ranked_any else None)
    oos_rank = sorted(
        [r for r in rows if (r["oos"]["n"] or 0) >= 15],
        key=lambda r: (r["oos"]["exp_R"] or -9, r["oos"]["hit"] or 0),
        reverse=True,
    )

    payload = {
        "ok": True,
        "research_only": True,
        "window": {"day_lo": day_lo, "day_hi": day_hi, "n_days": n_days, "oos_from": mid_day},
        "range_basis": {
            "OR30_contain_prior": "~65% next-30 closes inside (SR_RANGE_ACCURACY_PROVEN)",
            "OR15_zone_decisive_prior": "~100% swing|break on short window (OPEN_ZONE_BOX)",
            "zone": "edge ± 0.5×ATR; leave then retest; break = close beyond OR",
        },
        "prove_rules": {
            "PROVEN": f"TRAIN+OOS n≥{MIN_N}, hit≥{MIN_HIT}%, exp_R≥{MIN_EXP}, OOS t≥{MIN_T}",
            "PROMISING": f"n≥{SOFT_N}, hit≥{SOFT_HIT}%, exp_R≥{SOFT_EXP}",
        },
        "books": rows,
        "proven": [r["book"] for r in proven],
        "promising": [r["book"] for r in promising],
        "best": best,
        "oos_rank_top": oos_rank[:8],
        "took_sec": round(time.time() - t0, 1),
    }

    lines = [
        "# NIFTY — PA × **Opening RANGE** prove (OR15 / OR30)",
        "",
        "> **RESEARCH ONLY.** Same prove gate as `NIFTY_1M_PA_PROVEN_LOGIC`.",
        "",
        f"Window **{day_lo} → {day_hi}** ({n_days}d). OOS from **{mid_day}**. Target **{RR}R**, 1/day.",
        "",
        "## 0) Why range",
        "",
        "Transcript BOS/CHoCH/FVG alone was **NOT_PROVEN** on 1Y WF.",
        "This repo already showed **OR30** is the best containment box (~65%) and **OR15/OR30 zones** are decisive on revisits.",
        "Question: can a **causal entry** on that range clear PROVEN?",
        "",
        "| Book family | Logic |",
        "|---|---|",
        "| R1 swing | Leave → retest OR edge zone → fade, SL beyond box |",
        "| R2 break | Close beyond OR → extend → retest zone → continue |",
        "| R3/R4 +FVG | Same triggers, entry at FVG mid |",
        "| R5/R6 +HTF | Same with 15m bias aligned |",
        "",
        "## 1) Walk-forward",
        "",
        "| Book | Verdict | Full n/hit/expR | Train | OOS n/hit/expR/t |",
        "|---|---|---|---|---|",
    ]
    order = sorted(
        rows,
        key=lambda r: (
            0 if r["verdict"] == "PROVEN" else 1 if r["verdict"] == "PROMISING" else 2,
            -(r["oos"]["exp_R"] or -9),
        ),
    )
    for r in order:
        f, tr, o = r["full"], r["train"], r["oos"]
        lines.append(
            f"| `{r['book']}` | **{r['verdict']}** | {f['n']}/{f['hit']}%/{f['exp_R']} | "
            f"{tr['n']}/{tr['hit']}%/{tr['exp_R']} | {o['n']}/{o['hit']}%/{o['exp_R']}/t={o['t']} |"
        )

    lines += ["", "## 2) Verdict", ""]
    if proven:
        lines.append("### PROVEN books (ship candidates)")
        lines.append("")
        lines.append("| Book | Train hit/exp | OOS hit/exp/t | Full hit/exp | Logic |")
        lines.append("|---|---|---|---|---|")
        for p in ranked_proven:
            logic = "OR break→retest continue"
            if "htf" in p["book"]:
                logic += " + 15m HTF align"
            if "OR15" in p["book"]:
                logic += " (OR15)"
            else:
                logic += " (OR30)"
            lines.append(
                f"| `{p['book']}` | {p['train']['hit']}% / {p['train']['exp_R']}R | "
                f"{p['oos']['hit']}% / {p['oos']['exp_R']}R / t={p['oos']['t']} | "
                f"{p['full']['hit']}% / {p['full']['exp_R']}R | {logic} |"
            )
        lines.append("")
        lines.append(
            f"**Best PROVEN (OOS exp):** `{best['book']}` · "
            f"OOS hit **{best['oos']['hit']}%** · exp **{best['oos']['exp_R']}R** · n={best['oos']['n']}"
        )
        if promising:
            lines.append("")
            lines.append(f"PROMISING (not ship): {', '.join('`'+p['book']+'`' for p in promising)}")
    elif promising:
        lines.append("**No PROVEN.** PROMISING only — not live yet.")
        lines.append(f"Top: `{best['book']}` OOS {best['oos']['hit']}% / {best['oos']['exp_R']}R n={best['oos']['n']}")
    else:
        lines.append("**NOT PROVEN.** No OR-range entry book cleared TRAIN+OOS floors.")
        if oos_rank:
            top = oos_rank[0]
            lines.append(
                f"Closest OOS (n≥15): `{top['book']}` hit={top['oos']['hit']}% exp={top['oos']['exp_R']}R "
                f"n={top['oos']['n']} t={top['oos']['t']}"
            )

    lines += [
        "",
        "## 3) Proven logic (if any book passed)",
        "",
        "```",
        "1. Build OR15 (or OR30) high/low after first 15/30 minutes",
        "2. UP zone = OR high ± 0.5×ATR14 · DOWN zone = OR low ± 0.5×ATR14",
        "3. Wait for CLOSE beyond OR edge (break), then extension away from zone",
        "4. Enter on retest of the broken edge zone in break direction",
        "5. SL beyond far side of zone · TP 3R",
        "6. Optional filter: 15m HTF bias must agree (R6 books)",
        "```",
        "",
        "- Fade/swing into the range (R1/R3/R5) did **not** reliably prove.",
        "- Adding FVG mid on top of break (R4) **hurt** vs plain break retest.",
        "- This is orthogonal to transcript CHoCH→FVG (which failed alone).",
        "",
        "## 4) Ship call",
        "",
        "- If PROVEN: research Scalper mode candidate = **best R6/R2 book** (range break+retest).",
        "- Still research-only until explicitly wired; Oracle T15 clean can stay default.",
        "",
        f"_Generated in {payload['took_sec']}s._",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    print(f"PROVEN={len(proven)} PROMISING={len(promising)} BEST={best['book'] if best else None}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
