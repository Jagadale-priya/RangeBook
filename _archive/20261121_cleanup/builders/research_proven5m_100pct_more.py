"""RESEARCH — build Proven@100% from dual **5m** with more calls.

Approach:
  1) Soft-walk dual packs on 5m OR-break (lower champ p floor → more tickets)
  2) Mine ex-ante filters (p / time / side / gap / HTF / weekday / pick)
  3) Greedy union at hard **100%** floor (3y; 1y must stay 100% if n≥5)

Does NOT promote to LIVE.

  python -u prod_live/tests/builders/research_proven5m_100pct_more.py
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
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
warnings.filterwarnings("ignore")
import path_setup  # noqa: F401,E402

os.environ.setdefault("TELEGRAM_NOTIFY", "0")
os.environ.setdefault("WHATSAPP_NOTIFY", "0")
os.environ["ENABLE_NSE_MID_GATE"] = "0"

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _agg  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    bestp_day,
    filt,
    first_day,
    gap_map,
    is_perfect,
    mine_perfect,
    union_unique_days,
)
from research_confirm_dual_tf_deep import _clip, _hm_mins, _side  # noqa: E402
from research_dual15_dual5_confirm100 import (  # noqa: E402
    _collect_dual,
    _norm,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_SOFT5 = LEDGER / "_cache_dual5_soft_3y_research.json"
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"

END = "2026-11-15"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_6M = (pd.Timestamp(END) - timedelta(days=183)).strftime("%Y-%m-%d")
GOLDEN = ("2025-10-24", "2026-10-23")


def weekday_filt(rows: List[dict], weekdays: Set[int]) -> List[dict]:
    out = []
    for r in rows:
        try:
            wd = pd.Timestamp(str(r.get("day") or "")).weekday()
        except Exception:
            continue
        if wd in weekdays:
            out.append(r)
    return out


def last_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")].append(r)
    out = []
    for day in sorted(by):
        out.append(
            sorted(
                by[day],
                key=lambda x: (_hm_mins(str(x.get("hm") or "00:00")), float(x.get("p_t1") or 0)),
                reverse=True,
            )[0]
        )
    return out


def mid_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")].append(r)
    out = []
    for day in sorted(by):
        ordered = sorted(by[day], key=lambda x: _hm_mins(str(x.get("hm") or "99:99")))
        out.append(ordered[len(ordered) // 2])
    return out


def mine_extra(
    name: str,
    rows: List[dict],
    *,
    active: Set[str],
    gaps: Dict[str, float],
    min_n: int = 3,
) -> List[Tuple[str, List[dict], Dict[str, Any]]]:
    found = mine_perfect(name, rows, active=active, gaps=gaps, min_n=min_n)
    p_grid = [0.50, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70, 0.72, 0.75, 0.80, 0.85, 0.90]
    bands = [
        (9 * 60 + 15, 9 * 60 + 45, "first30"),
        (9 * 60 + 15, 10 * 60 + 15, "first60"),
        (9 * 60 + 15, 11 * 60 + 30, "am1130"),
        (11 * 60, 12 * 60 + 30, "brunch"),
        (12 * 60, 14 * 60, "lunch"),
        (13 * 60, 15 * 60 + 15, "earlypm"),
        (14 * 60, 15 * 60 + 15, "last75"),
    ]
    gap_opts = [
        (None, False, False, "nogap"),
        (0.20, False, False, "g020"),
        (0.30, False, False, "g030"),
        (0.40, False, False, "g040"),
        (0.25, True, False, "gdn025"),
        (0.25, False, True, "gup025"),
        (0.40, True, False, "gdn040"),
        (0.40, False, True, "gup040"),
    ]
    wd_opts = [
        (None, "wd_all"),
        ({0, 1, 2, 3, 4}, "wd_all"),
        ({0, 1, 2}, "wd_mtw"),
        ({2, 3, 4}, "wd_wrf"),
        ({0, 4}, "wd_mf"),
        ({1, 3}, "wd_tt"),
    ]
    seen = {t for t, _, _ in found}
    for side in (None, "BUY", "SELL"):
        for pmin in p_grid:
            for hm_lo, hm_hi, tlab in bands:
                for use_htf in (False, True):
                    for gabsm, gdn, gup, glab in gap_opts:
                        base0 = filt(
                            rows,
                            p_min=pmin,
                            side=side,
                            hm_lo=hm_lo,
                            hm_hi=hm_hi,
                            htf=active if use_htf else None,
                            gaps=gaps if gabsm is not None or gdn or gup else None,
                            gap_abs=gabsm,
                            gap_dn=gdn,
                            gap_up=gup,
                        )
                        for wd_set, wdlab in wd_opts:
                            base = base0 if wd_set is None else weekday_filt(base0, wd_set)
                            for vlab, vrows in (
                                ("raw", base),
                                ("first", first_day(base)),
                                ("bestp", bestp_day(base)),
                                ("mid", mid_day(base)),
                                ("last", last_day(base)),
                            ):
                                if len(vrows) < min_n:
                                    continue
                                if not is_perfect(vrows):
                                    continue
                                tag = (
                                    f"{name}_{side or 'BOTH'}_p{int(pmin*100)}_{tlab}_"
                                    f"{'htf' if use_htf else 'any'}_{glab}_{wdlab}_{vlab}"
                                )
                                if tag in seen:
                                    continue
                                seen.add(tag)
                                found.append((tag, vrows, _agg(vrows)))
    found.sort(key=lambda x: (x[2].get("n") or 0, x[2].get("points") or 0), reverse=True)
    return found


def greedy_union(
    streams: List[Tuple[str, List[dict], Dict[str, Any]]],
    *,
    start_gate: str,
    end_gate: str,
    start_1y: str,
    mode: str = "day",
    max_streams: int = 100,
) -> Tuple[List[dict], List[str]]:
    cur: List[dict] = []
    used: List[str] = []

    def merge(a: List[dict], b: List[dict]) -> List[dict]:
        if mode == "day":
            return union_unique_days(a, b)
        seen = {(str(r.get("day")), _side(r), str(r.get("hm") or "")) for r in a}
        out = list(a)
        for r in b:
            k = (str(r.get("day")), _side(r), str(r.get("hm") or ""))
            if k in seen:
                continue
            seen.add(k)
            out.append(dict(r))
        return out

    for tag, rows, _st in streams:
        seed = _clip(rows, start_gate, end_gate)
        if not seed or not is_perfect(seed):
            continue
        rs1 = _clip(rows, start_1y, end_gate)
        if len(rs1) >= 5 and not is_perfect(rs1):
            continue
        cur = list(seed)
        used = [tag]
        break
    if not cur:
        return [], []

    improved = True
    while improved and len(used) < max_streams:
        improved = False
        best = None
        best_n = len(cur)
        for tag, rows, _st in streams:
            if tag in used:
                continue
            cand = _clip(rows, start_gate, end_gate)
            if not cand:
                continue
            merged = merge(cur, cand)
            if len(merged) <= best_n:
                continue
            if not is_perfect(merged):
                continue
            m1 = _clip(merged, start_1y, end_gate)
            if len(m1) >= 5 and not is_perfect(m1):
                continue
            best = (tag, merged)
            best_n = len(merged)
        if best:
            used.append(best[0])
            cur = best[1]
            improved = True
            if len(used) <= 12 or len(used) % 10 == 0:
                print(f"    +{best[0][:72]} → n={len(cur)}", flush=True)
    return cur, used


def score_windows(rows: List[dict]) -> Dict[str, Any]:
    out = {}
    for label, a, b in (
        ("3y", START_3Y, END),
        ("1y", START_1Y, END),
        ("6m", START_6M, END),
        ("golden", GOLDEN[0], GOLDEN[1]),
    ):
        rs = _clip(rows, a, b)
        st = _agg(rs)
        out[label] = {**st, "start": a, "end": b, "perfect": (not rs) or is_perfect(rs)}
    return out


def load_or_build_soft_dual5(sessions: List[str]) -> Dict[str, List[dict]]:
    if CACHE_SOFT5.is_file():
        try:
            raw = json.loads(CACHE_SOFT5.read_text(encoding="utf-8"))
            if raw.get("start") == START_3Y and raw.get("end") == END:
                print(
                    f"  soft dual5 cache hit proven={len(raw['dual5']['proven_100'])} "
                    f"champ={len(raw['dual5']['champion'])}",
                    flush=True,
                )
                return raw["dual5"]
        except Exception:
            pass

    # Soft champ floors → more 5m tickets to mine from
    import research_dual15_dual5_confirm100 as dmod

    dmod.CHAMP_BUY_MIN = 0.50
    dmod.CHAMP_SELL_MIN = 0.50
    print(f"  soft-walk dual5 on 5m ({len(sessions)} sessions)…", flush=True)
    bars5 = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    dual5 = _collect_dual(bars5, sessions, tf="5m")
    payload = {
        "status": "RESEARCH",
        "start": START_3Y,
        "end": END,
        "champ_buy_min": 0.50,
        "champ_sell_min": 0.50,
        "dual5": dual5,
    }
    CACHE_SOFT5.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(
        f"  soft dual5 saved proven={len(dual5['proven_100'])} champ={len(dual5['champion'])}",
        flush=True,
    )
    return dual5


def main() -> int:
    t0 = time.time()
    print("RESEARCH dual5 Proven@100% more-calls (soft expand + mine)", flush=True)

    dual_lock = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    sessions_all, _, _ = fs._prod2(4000)
    sess = sorted(d for d in sessions_all if START_3Y < d <= END)
    daily = fs._load_daily()
    active = fs._active_days(sess, daily) if sess else set()
    gaps = gap_map()

    p15 = [dict(r, track="proven_100_15m") for r in dual_lock["dual15"].get("proven_100") or []]
    p5_locked = [
        dict(r, track="proven_100_5m_locked") for r in dual_lock["dual5"].get("proven_100") or []
    ]

    soft = load_or_build_soft_dual5(sess)
    soft_any = [
        dict(r, track=str(r.get("track") or "dual5"), src_model="dual5_soft")
        for r in (soft.get("proven_100") or []) + (soft.get("champion") or [])
    ]
    soft_3y = _clip(soft_any, START_3Y, END)
    print(
        f"  soft dual5 3y n={len(soft_3y)} hit={_agg(soft_3y).get('hit_pct')} "
        f"wins={_agg(soft_3y).get('wins')}",
        flush=True,
    )

    print("  mine perfect streams (min_n=3)…", flush=True)
    streams = mine_extra("D5S", soft_3y, active=active, gaps=gaps, min_n=3)
    streams = [(t, r, s) for t, r, s in streams if is_perfect(r)]
    print(f"  perfect streams: {len(streams)}", flush=True)

    print("  greedy union day…", flush=True)
    day_rows, day_tags = greedy_union(
        streams, start_gate=START_3Y, end_gate=END, start_1y=START_1Y, mode="day"
    )
    print("  greedy union raw…", flush=True)
    raw_rows, raw_tags = greedy_union(
        streams, start_gate=START_3Y, end_gate=END, start_1y=START_1Y, mode="raw"
    )

    books = {
        "BASE_dual15_proven": p15,
        "BASE_dual5_proven_locked": p5_locked,
        "SOFT_dual5_any": soft_any,
        "D5_PROVEN100_DAY": day_rows,
        "D5_PROVEN100_RAW": raw_rows,
    }

    payload: Dict[str, Any] = {
        "status": "RESEARCH",
        "not_live": True,
        "model": "dual5 soft-expand (same dual packs, 5m OR-break, champ p>=0.50)",
        "hard_floor": 100.0,
        "streams_found": len(streams),
        "day_stream_tags": day_tags,
        "raw_stream_tags": raw_tags,
        "top_streams": [
            {"tag": t, "n": s.get("n"), "hit_pct": s.get("hit_pct"), "points": s.get("points")}
            for t, _r, s in streams[:30]
        ],
        "books": {},
    }

    lines = [
        "# RESEARCH — Dual5 Proven@100% with more calls",
        "",
        "**Status:** RESEARCH only · **not live**",
        "**Model:** same dual packs · walked on **5m** OR-break · soft champ p≥0.50",
        "**Hard floor:** 100% (3y gate; 1y 100% when n≥5)",
        "",
        f"Soft dual5 3y pool: **{len(soft_3y)}** @ {_agg(soft_3y).get('hit_pct')}%",
        f"Perfect streams: **{len(streams)}** · day used **{len(day_tags)}** · raw used **{len(raw_tags)}**",
        "",
        "## Top perfect streams",
        "",
        "| Tag | N | Hit | Pts |",
        "|---|---:|---:|---:|",
    ]
    for t, _r, s in streams[:30]:
        lines.append(f"| `{t}` | {s.get('n')} | {s.get('hit_pct')} | {s.get('points')} |")

    lines.extend(
        [
            "",
            "## Books",
            "",
            "| Book | 3y | 1y | 6m | Golden | Perfect3y |",
            "|---|---|---|---|---|---|",
        ]
    )

    for name, rows in books.items():
        sc = score_windows(rows)
        payload["books"][name] = {"windows": sc}

        def fmt(w: str) -> str:
            x = sc[w]
            n = x.get("n") or 0
            return f"{n}@{x.get('hit_pct')}" if n else "0"

        lines.append(
            f"| `{name}` | {fmt('3y')} | {fmt('1y')} | {fmt('6m')} | {fmt('golden')} | "
            f"{'Y' if sc['3y'].get('perfect') else 'N'} |"
        )

    d1 = payload["books"]["D5_PROVEN100_DAY"]["windows"]["1y"]
    d3 = payload["books"]["D5_PROVEN100_DAY"]["windows"]["3y"]
    b15 = payload["books"]["BASE_dual15_proven"]["windows"]["1y"]
    b5 = payload["books"]["BASE_dual5_proven_locked"]["windows"]["1y"]

    if day_rows and d3.get("perfect") and d1.get("perfect") and (d1.get("n") or 0) >= (b15.get("n") or 0):
        verdict = (
            f"PROMISING — `D5_PROVEN100_DAY` {d1.get('n')}@100% on 1y "
            f"(≥ dual15 proven {b15.get('n')}@{b15.get('hit_pct')}%). Still RESEARCH."
        )
    elif day_rows and d3.get("perfect") and (d1.get("n") or 0) > (b5.get("n") or 0):
        verdict = (
            f"PARTIAL — dual5 100% day desk {d1.get('n')}@{d1.get('hit_pct')}% 1y "
            f"beats locked dual5 proven ({b5.get('n')}@{b5.get('hit_pct')}%) "
            f"but below dual15 proven ({b15.get('n')}@{b15.get('hit_pct')}%)."
        )
    elif day_rows and d3.get("perfect"):
        verdict = (
            f"THIN — 100% dual5 desk exists ({d3.get('n')}@100% 3y) but not enough calls."
        )
    else:
        verdict = (
            "FAIL — dual5 alone cannot sustain Proven@100 with more calls; "
            "keep dual15 proven for LIVE."
        )

    payload["verdict"] = verdict
    payload["elapsed_s"] = round(time.time() - t0, 1)

    lines.extend(["", "## Day stream order", ""])
    for i, t in enumerate(day_tags, 1):
        lines.append(f"{i}. `{t}`")
    lines.extend(
        [
            "",
            "## Sample 1y day calls",
            "",
            "| Day | HM | Side | Win | p |",
            "|---|---|---|---|---:|",
        ]
    )
    for r in sorted(_clip(day_rows, START_1Y, END), key=lambda x: (x.get("day"), x.get("hm")))[:50]:
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {_side(r)} | "
            f"{'W' if r.get('win') else 'L'} | {round(float(r.get('p_t1') or 0), 3)} |"
        )
    lines.extend(["", "## Verdict", "", verdict, "", f"Elapsed {payload['elapsed_s']}s", ""])

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "RESEARCH_PROVEN5M_100PCT_MORE.md"
    js = OUT / "RESEARCH_PROVEN5M_100PCT_MORE.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
