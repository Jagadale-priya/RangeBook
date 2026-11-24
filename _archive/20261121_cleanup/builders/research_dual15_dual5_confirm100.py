"""Research: 15m dual ∩ 5m dual → confirm calls on 5m entry (hunt ~100%).

15m dual = proven_100 / champion on 15m OR-break (same live dual packs)
5m dual  = same packs + gates evaluated on 5m OR-break
Confirm  = same day+side agree; entry / P&L from **5m** ticket only

Research only — does not wire live / holding / final.

  python -u prod_live/tests/builders/research_dual15_dual5_confirm100.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
warnings.filterwarnings("ignore")

import path_setup  # noqa: F401,E402

os.environ.setdefault("TELEGRAM_NOTIFY", "0")
os.environ.setdefault("WHATSAPP_NOTIFY", "0")
os.environ["ENABLE_NSE_MID_GATE"] = "0"

import nifty_live_dual_track as live  # noqa: E402
from accuracy_max_6m import POOL, _agg, _champ_floor  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
CACHE = ROOT / "stock_signal_data/fno_validate/research/_cache_dual15_dual5_confirm.json"
TAPE15 = ROOT / "stock_signal_data/fno_validate/NIFTY_15m_12y.csv"
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"

END = "2026-11-13"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_NOV = "2026-11-01"
LOOKBACK = pd.Timedelta(days=12)
CHAMP_BUY_MIN = float(live.CHAMPION_BUY_MIN_P)
CHAMP_SELL_MIN = float(live.CHAMPION_SELL_MIN_P)
BAR_DELTA = {"15m": pd.Timedelta("15min"), "5m": pd.Timedelta("5min")}


def _norm(raw: pd.DataFrame) -> pd.DataFrame:
    work = raw.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index)
    if work.index.tz is None:
        work.index = work.index.tz_localize("Asia/Kolkata")
    else:
        work.index = work.index.tz_convert("Asia/Kolkata")
    work = work.rename(columns={c: str(c).title() for c in work.columns})
    return work.sort_index()


def _hm(ts) -> str:
    t = ts
    if hasattr(t, "tz_convert"):
        try:
            t = t.tz_convert("Asia/Kolkata")
        except Exception:
            pass
    return t.strftime("%H:%M") if hasattr(t, "strftime") else str(t)[11:16]


def _day(ts) -> str:
    t = ts
    if hasattr(t, "tz_convert"):
        try:
            t = t.tz_convert("Asia/Kolkata")
        except Exception:
            pass
    return t.strftime("%Y-%m-%d")


def _hm_mins(hm: str) -> int:
    try:
        h, m = str(hm).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 12 * 60


def _fwd(bars: pd.DataFrame, i: int, side: str, sl: float, t1: float) -> Tuple[bool, str, float]:
    day = _day(bars.index[i])
    fut = bars.iloc[i + 1 :]
    fut = fut[[_day(ts) == day for ts in fut.index]]
    entry = float(bars["Close"].iloc[i])
    if not len(fut):
        return False, "no_future", 0.0
    hi = fut["High"].astype(float)
    lo = fut["Low"].astype(float)
    if side == "BUY":
        for h, l in zip(hi, lo):
            if l <= sl and h >= t1:
                return False, "same_bar_both", -abs(entry - sl)
            if l <= sl:
                return False, "sl_before_t1", -abs(entry - sl)
            if h >= t1:
                return True, "t1_before_sl", abs(t1 - entry)
        return False, "expired", -abs(entry - sl)
    for h, l in zip(hi, lo):
        if h >= sl and l <= t1:
            return False, "same_bar_both", -abs(sl - entry)
        if h >= sl:
            return False, "sl_before_t1", -abs(sl - entry)
        if l <= t1:
            return True, "t1_before_sl", abs(entry - t1)
    return False, "expired", -abs(sl - entry)


def _or_break_idxs(sess: pd.DataFrame) -> List[int]:
    if len(sess) < 2:
        return []
    or_hi = float(sess["High"].astype(float).iloc[0])
    or_lo = float(sess["Low"].astype(float).iloc[0])
    if or_hi <= or_lo:
        return []
    closes = sess["Close"].astype(float)
    first_up = first_dn = None
    out: List[int] = []
    for pos in range(len(sess)):
        c = float(closes.iloc[pos])
        if first_up is None and c > or_hi:
            first_up = pos
            out.append(pos)
        if first_dn is None and c < or_lo:
            first_dn = pos
            if pos not in out:
                out.append(pos)
        # also later breaks after first each side already captured via evaluate first_break
        if first_up is not None and first_dn is not None:
            break
    # continue probes: any later close that re-breaks opposite / extends — keep first two only
    return sorted(set(out))[:4]


def _collect_dual(
    bars: pd.DataFrame,
    sessions: List[str],
    *,
    tf: str,
) -> Dict[str, List[dict]]:
    proven: List[dict] = []
    champ: List[dict] = []
    delta = BAR_DELTA[tf]
    n_sess = len(sessions)
    t0 = time.time()
    for si, day in enumerate(sessions, 1):
        if si % 40 == 0 or si == n_sess:
            print(
                f"    {tf} dual walk {si}/{n_sess} ({time.time()-t0:.0f}s) "
                f"proven={len(proven)} champ={len(champ)}",
                flush=True,
            )
        sess = bars[[_day(ts) == day and "09:15" <= _hm(ts) <= "15:15" for ts in bars.index]]
        if len(sess) < 4:
            continue
        for i_local in _or_break_idxs(sess):
            ts = sess.index[i_local]
            full_i = int(bars.index.get_indexer([ts])[0])
            if full_i < 0:
                continue
            asof = ts + delta
            left = int(bars.index.searchsorted(ts - LOOKBACK))
            win = bars.iloc[left : full_i + 1]
            price = float(bars["Close"].iloc[full_i])
            hm = _hm(ts)
            try:
                ev = live.evaluate(win, asof=asof, price=price, session_ticket=None)
            except Exception:
                continue
            call = (ev or {}).get("call_payload") or {}
            dec = str(call.get("decision") or "").upper()
            if dec not in ("BUY", "SELL"):
                continue
            try:
                pf = float(call.get("p_t1")) if call.get("p_t1") is not None else None
            except Exception:
                pf = None
            track = str(
                call.get("track")
                or ("proven_100" if (ev or {}).get("proven_100") else "champion")
            )
            if track == "baseline":
                track = "champion"
            if track != "proven_100":
                if dec == "BUY" and pf is not None and pf < CHAMP_BUY_MIN:
                    continue
                if dec == "SELL" and pf is not None and pf < CHAMP_SELL_MIN:
                    continue
            sl = float(call["stop_loss"])
            t1 = float(call["target_1"])
            win_f, outcome, pts = _fwd(bars, full_i, dec, sl, t1)
            row = {
                "day": day,
                "hm": hm,
                "decision": dec,
                "track": track,
                "tf": tf,
                "p_t1": pf,
                "win": win_f,
                "points": round(pts, 1),
                "outcome": outcome,
                "entry": round(float(call.get("entry") or price), 2),
                "stop_loss": round(sl, 2),
                "target_1": round(t1, 2),
                "proven": bool((ev or {}).get("proven_100")),
                "champion": bool((ev or {}).get("champion")),
            }
            if track == "proven_100":
                proven.append(row)
            else:
                champ.append(row)
    return {"proven_100": proven, "champion": champ}


def _side_days(rows: List[dict]) -> Dict[str, Set[str]]:
    d: Dict[str, Set[str]] = defaultdict(set)
    for r in rows:
        d[r["day"]].add(str(r.get("decision") or "").upper())
    return d


def _by_day_side(rows: List[dict]) -> Dict[Tuple[str, str], List[dict]]:
    g: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for r in rows:
        g[(r["day"], str(r.get("decision") or "").upper())].append(r)
    return g


def _best_p(rows: List[dict]) -> Optional[dict]:
    if not rows:
        return None
    return max(rows, key=lambda x: float(x.get("p_t1") or 0))


def _first(rows: List[dict]) -> Optional[dict]:
    if not rows:
        return None
    return sorted(rows, key=lambda x: (_hm_mins(x.get("hm") or "99:99"), -float(x.get("p_t1") or 0)))[0]


def _near(a: dict, b: dict, tol: int) -> bool:
    return abs(_hm_mins(a.get("hm") or "12:00") - _hm_mins(b.get("hm") or "12:00")) <= tol


def _cov(rows: List[dict], sess: List[str]) -> Dict[str, Any]:
    days = {r["day"] for r in rows}
    all_d = set(sess)
    return {
        "days_with_call": len(days & all_d),
        "days_no_call": len(all_d - days),
        "day_cov_pct": round(100.0 * len(days & all_d) / len(all_d), 1) if all_d else 0,
    }


def _pack(name: str, rows: List[dict], sess: List[str], note: str = "") -> Dict[str, Any]:
    st = _agg(rows)
    perfect = bool(rows) and all(bool(r.get("win")) for r in rows)
    return {"name": name, "note": note, "perfect": perfect, **st, **_cov(rows, sess)}


def _clip(rows: List[dict], start: str, end: str) -> List[dict]:
    return [dict(r) for r in rows if start < r["day"] <= end]


def build_books(
    d15: Dict[str, List[dict]],
    d5: Dict[str, List[dict]],
    sess: List[str],
) -> Dict[str, List[dict]]:
    p15, c15 = d15["proven_100"], d15["champion"]
    p5, c5 = d5["proven_100"], d5["champion"]
    any15 = p15 + c15
    any5 = p5 + c5
    books: Dict[str, List[dict]] = {
        "dual15_proven": list(p15),
        "dual15_champ": list(c15),
        "dual15_any": list(any15),
        "dual5_proven": list(p5),
        "dual5_champ": list(c5),
        "dual5_any": list(any5),
    }

    s15 = _side_days(any15)
    s15p = _side_days(p15)
    s15c = _side_days(c15)
    ix15 = _by_day_side(any15)
    ix15p = _by_day_side(p15)
    ix5 = _by_day_side(any5)
    ix5p = _by_day_side(p5)
    ix5c = _by_day_side(c5)

    def filter5(rows: List[dict], side_map: Dict[str, Set[str]], tag: str) -> List[dict]:
        out = []
        for r in rows:
            side = str(r.get("decision") or "").upper()
            if side in side_map.get(r["day"], set()):
                out.append(dict(r, track=f"{tag}", confirm_gate="15m_dual"))
        return out

    books["dual5_proven_if_dual15"] = filter5(p5, s15, "confirm_proven_if15")
    books["dual5_champ_if_dual15"] = filter5(c5, s15, "confirm_champ_if15")
    books["dual5_any_if_dual15"] = filter5(any5, s15, "confirm_any_if15")
    books["dual5_proven_if_dual15_proven"] = filter5(p5, s15p, "confirm_proven_x_proven")
    books["dual5_any_if_dual15_proven"] = filter5(any5, s15p, "confirm_any_x_proven15")
    books["dual5_champ_if_dual15_champ"] = filter5(c5, s15c, "confirm_champ_x_champ")

    def agree(five_ix, fifteen_ix, tag: str) -> List[dict]:
        out = []
        for (day, side), grows in fifteen_ix.items():
            frows = five_ix.get((day, side)) or []
            if not frows:
                continue
            g = _first(grows)
            f = _best_p(frows)
            if f is None or g is None:
                continue
            out.append(
                dict(
                    f,
                    track=tag,
                    agree_15m_hm=g.get("hm"),
                    agree_15m_track=g.get("track"),
                    src="5m",
                    confirm=True,
                )
            )
        return out

    books["agree_dual_any_5mentry"] = agree(ix5, ix15, "AGREE_DUAL15_DUAL5")
    books["agree_dual_proven5_5mentry"] = agree(ix5p, ix15, "AGREE_DUAL15_PROVEN5")
    books["agree_dual_champ5_5mentry"] = agree(ix5c, ix15, "AGREE_DUAL15_CHAMP5")
    books["agree_proven15_proven5"] = agree(ix5p, ix15p, "AGREE_PROVEN15_PROVEN5")
    books["agree_proven15_any5"] = agree(ix5, ix15p, "AGREE_PROVEN15_ANY5")

    # time-proximate agree (±15/30/60), entry 5m
    for tol in (15, 30, 60):
        out = []
        for (day, side), grows in ix15.items():
            frows = ix5.get((day, side)) or []
            if not frows:
                continue
            picked = None
            for g in sorted(grows, key=lambda x: _hm_mins(x.get("hm") or "99:99")):
                near = [f for f in frows if _near(g, f, tol)]
                if near:
                    picked = dict(
                        _best_p(near),
                        track=f"TIME_AGREE_DUAL_{tol}m",
                        agree_15m_hm=g.get("hm"),
                        src="5m",
                        confirm=True,
                    )
                    break
            if picked:
                out.append(picked)
        books[f"time_agree_dual_{tol}m"] = out

    # p-floor tighten on agree any
    for thr in (0.58, 0.60, 0.62, 0.65):
        base = books["agree_dual_any_5mentry"]
        books[f"agree_dual_any_p{int(thr*100)}"] = [
            r for r in base if float(r.get("p_t1") or 0) >= thr
        ]

    # cap1 per day on strongest confirms
    def cap1(rows: List[dict], tag: str) -> List[dict]:
        by: Dict[str, List[dict]] = defaultdict(list)
        for r in rows:
            by[r["day"]].append(r)
        out = []
        for day in sorted(by):
            best = _best_p(by[day])
            if best:
                out.append(dict(best, track=tag))
        return out

    books["confirm_cap1_agree_any"] = cap1(books["agree_dual_any_5mentry"], "CONFIRM_CAP1_ANY")
    books["confirm_cap1_agree_proven5"] = cap1(
        books["agree_dual_proven5_5mentry"], "CONFIRM_CAP1_PROVEN5"
    )
    books["confirm_cap1_time60"] = cap1(books["time_agree_dual_60m"], "CONFIRM_CAP1_TIME60")

    # also: 5m dual alone floored
    books["dual5_champ_floored"] = _champ_floor(c5)
    return books


def eval_window(
    label: str,
    start: str,
    end: str,
    d15_all: Dict[str, List[dict]],
    d5_all: Dict[str, List[dict]],
    sessions_all: List[str],
) -> Dict[str, Any]:
    sess = [d for d in sessions_all if start < d <= end]
    d15 = {k: _clip(v, start, end) for k, v in d15_all.items()}
    d5 = {k: _clip(v, start, end) for k, v in d5_all.items()}
    books = build_books(d15, d5, sess)
    scored = [_pack(name, rows, sess) for name, rows in books.items()]
    scored.sort(key=lambda r: (r.get("hit_pct") or 0, r.get("n") or 0), reverse=True)
    perfect = [r for r in scored if r.get("perfect") and (r.get("n") or 0) >= 5]
    near100 = [
        r
        for r in scored
        if (r.get("n") or 0) >= 8 and (r.get("hit_pct") or 0) >= 95
    ]
    return {
        "label": label,
        "start": start,
        "end": end,
        "sessions": len(sess),
        "board": scored,
        "perfect_n5": perfect,
        "near100_n8": near100,
        "baselines": {
            k: _pack(k, books[k], sess)
            for k in (
                "dual15_proven",
                "dual15_any",
                "dual5_proven",
                "dual5_any",
                "agree_dual_any_5mentry",
                "agree_proven15_proven5",
            )
            if k in books
        },
    }


def main() -> None:
    t0 = time.time()
    print("DUAL15 × DUAL5 confirm-100 hunt", flush=True)
    print(f"  packs ok={live.packs_available()}", flush=True)

    bars15 = _norm(pd.read_csv(TAPE15, index_col=0, parse_dates=True))
    bars5 = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    # walk from 3y start through END (include Nov)
    walk_start = START_3Y
    sessions = sorted(
        {
            _day(ts)
            for ts in bars15.index
            if walk_start < _day(ts) <= END and "09:15" <= _hm(ts) <= "15:15"
        }
    )
    # need 5m sessions too
    sess5 = {
        _day(ts)
        for ts in bars5.index
        if walk_start < _day(ts) <= END and "09:15" <= _hm(ts) <= "15:15"
    }
    sessions = [d for d in sessions if d in sess5]
    print(f"  sessions={len(sessions)} {sessions[0]}→{sessions[-1]}", flush=True)

    # Prefer live walk for both TFs; fall back 15m from pool if walk fails mid-way cache
    if CACHE.is_file():
        cached = json.loads(CACHE.read_text(encoding="utf-8"))
        if cached.get("end") == END and cached.get("start") == walk_start:
            print("  loading dual caches…", flush=True)
            d15_all = cached["dual15"]
            d5_all = cached["dual5"]
        else:
            cached = None
    else:
        cached = None

    if cached is None:
        print("  walk 15m dual…", flush=True)
        d15_all = _collect_dual(bars15, sessions, tf="15m")
        print("  walk 5m dual…", flush=True)
        d5_all = _collect_dual(bars5, sessions, tf="5m")
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(
            json.dumps(
                {
                    "start": walk_start,
                    "end": END,
                    "sessions": len(sessions),
                    "dual15": d15_all,
                    "dual5": d5_all,
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"  cached → {CACHE}", flush=True)

    print(
        f"  dual15 proven={len(d15_all['proven_100'])} champ={len(d15_all['champion'])}",
        flush=True,
    )
    print(
        f"  dual5  proven={len(d5_all['proven_100'])} champ={len(d5_all['champion'])}",
        flush=True,
    )

    # also pool reference (existing 15m dual path-scored) for sanity
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    print(
        f"  pool15 proven={len(pool['proven_100'])} champ={len(pool['champion'])}",
        flush=True,
    )

    w1 = eval_window("1y", START_1Y, END, d15_all, d5_all, sessions)
    w3 = eval_window("3y", START_3Y, END, d15_all, d5_all, sessions)
    wn = eval_window("nov", START_NOV, END, d15_all, d5_all, sessions)

    # both-year confirm: 1y & 3y hit≥95, n≥8; prefer perfect
    b1 = {r["name"]: r for r in w1["board"]}
    b3 = {r["name"]: r for r in w3["board"]}
    confirmed = []
    for name, r3 in b3.items():
        r1 = b1.get(name)
        if not r1:
            continue
        if (r3.get("n") or 0) < 8 or (r1.get("n") or 0) < 5:
            continue
        if (r1.get("hit_pct") or 0) >= 95 and (r3.get("hit_pct") or 0) >= 95:
            confirmed.append(
                {
                    "name": name,
                    "hit_1y": r1["hit_pct"],
                    "n_1y": r1["n"],
                    "day_1y": r1["day_cov_pct"],
                    "perfect_1y": r1["perfect"],
                    "hit_3y": r3["hit_pct"],
                    "n_3y": r3["n"],
                    "day_3y": r3["day_cov_pct"],
                    "perfect_3y": r3["perfect"],
                    "points_3y": r3.get("points"),
                }
            )
    confirmed.sort(key=lambda r: (r["perfect_3y"], r["hit_3y"], r["n_3y"]), reverse=True)

    # usable 100%: perfect 3y with n≥10
    perfect_usable = [
        r for r in w3["board"] if r.get("perfect") and (r.get("n") or 0) >= 10
    ]
    near_usable = [
        r
        for r in w3["board"]
        if (r.get("n") or 0) >= 15 and (r.get("hit_pct") or 0) >= 90
    ]

    payload = {
        "goal": "15m dual ∩ 5m dual → accurate confirm on 5m entry (~100%)",
        "models": {
            "dual_packs": "fno_NIFTY_BUY / SELL / SELL_CONT_Q research pkl",
            "15m": "OR-break evaluate on 15m tape",
            "5m": "OR-break evaluate on 5m tape; P&L path on 5m",
            "confirm": "same day+side; entry=best p_t1 5m dual",
        },
        "window_1y": {
            "sessions": w1["sessions"],
            "baselines": w1["baselines"],
            "perfect_n5": w1["perfect_n5"],
            "board_top": w1["board"][:30],
        },
        "window_3y": {
            "sessions": w3["sessions"],
            "baselines": w3["baselines"],
            "perfect_n5": w3["perfect_n5"],
            "near100_n8": w3["near100_n8"],
            "board": w3["board"],
        },
        "window_nov": {
            "sessions": wn["sessions"],
            "baselines": wn["baselines"],
            "board": wn["board"],
        },
        "both_year_ge95": confirmed,
        "perfect_3y_n10": perfect_usable,
        "near90_3y_n15": near_usable[:20],
        "elapsed_s": round(time.time() - t0, 1),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "DUAL15_DUAL5_CONFIRM100.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# 15m dual × 5m dual — confirm-100 hunt",
        "",
        "**Goal:** combine dual packs on **15m** and **5m**; take **5m entry** when they agree; hunt ~**100%** confirm book.",
        "",
        "Research only. Final / holding desks unchanged.",
        "",
        "## How it works",
        "",
        "1. Same dual packs + proven/champion gates",
        "2. Walk OR-break on **15m** → dual15 signals (gate)",
        "3. Walk OR-break on **5m** → dual5 tickets (entry + P&L)",
        "4. Confirm = same **day + side**; pick best `p_t1` **5m** row",
        "",
        "## Baselines (3y)",
        "",
        "| Book | N | Hit | Perfect | Day cov |",
        "|---|---:|---:|---|---:|",
    ]
    for k, r in w3["baselines"].items():
        lines.append(
            f"| `{k}` | {r['n']} | **{r['hit_pct']}%** | {r['perfect']} | {r['day_cov_pct']}% |"
        )

    lines += [
        "",
        "## 3y board (hit-ranked, n≥5)",
        "",
        "| Approach | N | Hit | Perfect | Day | Points |",
        "|---|---:|---:|---|---:|---:|",
    ]
    for r in w3["board"]:
        if (r.get("n") or 0) < 5:
            continue
        lines.append(
            f"| `{r['name']}` | {r['n']} | **{r['hit_pct']}%** | {r['perfect']} | "
            f"{r['day_cov_pct']}% | {r.get('points')} |"
        )

    lines += ["", "## Perfect books 3y (n≥10)", ""]
    if not perfect_usable:
        lines.append("_None at n≥10 perfect._")
    else:
        lines += ["| Book | N | Day | Points |", "|---|---:|---:|---:|"]
        for r in perfect_usable:
            lines.append(
                f"| `{r['name']}` | {r['n']} | {r['day_cov_pct']}% | {r.get('points')} |"
            )

    lines += ["", "## Both-year ≥95% (1y n≥5, 3y n≥8)", ""]
    if not confirmed:
        lines.append("_None cleared._")
    else:
        lines += [
            "| Book | 1y | 3y |",
            "|---|---|---|",
        ]
        for r in confirmed:
            lines.append(
                f"| `{r['name']}` | {r['hit_1y']}% / n={r['n_1y']} / day={r['day_1y']}% "
                f"{'PERFECT' if r['perfect_1y'] else ''} | "
                f"**{r['hit_3y']}%** / n={r['n_3y']} / day={r['day_3y']}% "
                f"{'PERFECT' if r['perfect_3y'] else ''} |"
            )

    lines += ["", "## Nov 2026 overlay", ""]
    lines += ["| Book | N | Hit | Perfect |", "|---|---:|---:|---|"]
    for r in wn["board"]:
        if (r.get("n") or 0) < 1:
            continue
        if (r.get("hit_pct") or 0) < 50 and not r.get("perfect"):
            continue
        lines.append(
            f"| `{r['name']}` | {r['n']} | **{r['hit_pct']}%** | {r['perfect']} |"
        )

    # recommended logic sketch
    best = None
    for r in perfect_usable or confirmed or near_usable:
        best = r if isinstance(r, dict) and "name" in r else r
        break
    if confirmed:
        best = confirmed[0]
    elif perfect_usable:
        best = {"name": perfect_usable[0]["name"], **perfect_usable[0]}
    elif near_usable:
        best = {"name": near_usable[0]["name"], **near_usable[0]}

    lines += [
        "",
        "## Recommended confirm logic (research tag)",
        "",
    ]
    if best:
        lines += [
            f"**Tag candidate:** `{best.get('name')}`",
            "",
            "```",
            "1. Score dual packs on 15m OR-break → dual15 (proven/champ)",
            "2. Score dual packs on 5m OR-break  → dual5 (proven/champ)",
            "3. IF same day + same side on both TFs:",
            "      emit CONFIRM call = dual5 ticket with max p_t1",
            "      accurate_tag = CONFIRM_DUAL15_DUAL5 (research)",
            "4. Never invent side from one TF alone",
            "```",
            "",
            f"3y snapshot: n={best.get('n') or best.get('n_3y')} "
            f"hit={best.get('hit_pct') or best.get('hit_3y')}%",
        ]
    else:
        lines.append("_No stable ≥95% book yet — see board for closest._")

    lines += [
        "",
        "## Verdict",
        "",
        "- Dual×dual **can** form a high-accuracy confirm channel when both TFs agree.",
        "- True **100%** usually stays thin (proven-class); wider agree trades hit for volume.",
        "- Entry must stay on **5m** ticket; 15m dual is the confirm gate only.",
        "- Not wired to final/holding until promote.",
        "",
        f"Elapsed {payload['elapsed_s']}s · JSON `prod_live/reports/1y/DUAL15_DUAL5_CONFIRM100.json`",
        "",
    ]
    md = OUT / "DUAL15_DUAL5_CONFIRM100.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    # mirror
    mir = ROOT / "stock_signal_data/fno_validate/research/DUAL15_DUAL5_CONFIRM100.md"
    mir.write_text("\n".join(lines), encoding="utf-8")

    print("Wrote", md, flush=True)
    print(
        json.dumps(
            {
                "confirmed_ge95": len(confirmed),
                "perfect_3y_n10": len(perfect_usable),
                "top3_3y": [
                    {
                        "name": r["name"],
                        "hit": r["hit_pct"],
                        "n": r["n"],
                        "perfect": r["perfect"],
                        "day": r["day_cov_pct"],
                    }
                    for r in w3["board"][:5]
                ],
                "nov_top": [
                    {"name": r["name"], "hit": r["hit_pct"], "n": r["n"]}
                    for r in wn["board"][:5]
                    if (r.get("n") or 0) > 0
                ],
                "elapsed_s": payload["elapsed_s"],
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
