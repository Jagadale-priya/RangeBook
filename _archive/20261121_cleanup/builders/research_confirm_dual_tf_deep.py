"""Deep research: 15m dual gate × 5m entry confirm (expand 100%/≥95% books).

Uses cached dual15/dual5 walks + pool crown + prod2.
Prod already has 15m dual proven; 5m has NO proven — only crown.
This hunt asks: what 5m entry + gates make a stable confirm channel?

Research only — does not wire live.

  python -u prod_live/tests/builders/research_confirm_dual_tf_deep.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import POOL, PRIORITY, _agg, _champ_floor, _union  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
CACHE = ROOT / "stock_signal_data/fno_validate/research/_cache_dual15_dual5_confirm.json"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"

END = "2026-11-13"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_6M = (pd.Timestamp(END) - timedelta(days=183)).strftime("%Y-%m-%d")
START_NOV = "2026-11-01"

TOLS = (0, 5, 10, 15, 20, 30, 45, 60, 90)
P_FLOORS = (0.0, 0.55, 0.58, 0.60, 0.62, 0.65, 0.70)
PASS_HIT = 95.0
PASS_N = 8


def _hm_mins(hm: str) -> int:
    try:
        h, m = str(hm).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 12 * 60


def _side(r: dict) -> str:
    return str(r.get("decision") or "").upper()


def _clip(rows: List[dict], start: str, end: str) -> List[dict]:
    return [dict(r) for r in rows if start < str(r.get("day") or "") <= end]


def _side_days(rows: List[dict]) -> Dict[str, Set[str]]:
    d: Dict[str, Set[str]] = defaultdict(set)
    for r in rows:
        s = _side(r)
        if s in ("BUY", "SELL"):
            d[str(r["day"])].add(s)
    return d


def _ix(rows: List[dict]) -> Dict[Tuple[str, str], List[dict]]:
    g: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for r in rows:
        s = _side(r)
        if s in ("BUY", "SELL"):
            g[(str(r["day"]), s)].append(r)
    return g


def _best_p(rows: List[dict]) -> Optional[dict]:
    if not rows:
        return None
    return max(rows, key=lambda x: float(x.get("p_t1") or 0))


def _first(rows: List[dict]) -> Optional[dict]:
    if not rows:
        return None
    return sorted(
        rows,
        key=lambda x: (_hm_mins(str(x.get("hm") or "99:99")), -float(x.get("p_t1") or 0)),
    )[0]


def _cov(rows: List[dict], sess: List[str]) -> Dict[str, Any]:
    days = {str(r["day"]) for r in rows}
    all_d = set(sess)
    return {
        "days_with_call": len(days & all_d),
        "days_no_call": len(all_d - days),
        "day_cov_pct": round(100.0 * len(days & all_d) / max(len(all_d), 1), 1),
    }


def _pack(name: str, rows: List[dict], sess: List[str], note: str = "") -> Dict[str, Any]:
    st = _agg(rows)
    perfect = bool(rows) and all(bool(r.get("win")) for r in rows)
    by_side = {"BUY": 0, "SELL": 0, "BUY_w": 0, "SELL_w": 0}
    for r in rows:
        s = _side(r)
        if s in ("BUY", "SELL"):
            by_side[s] += 1
            if r.get("win"):
                by_side[f"{s}_w"] += 1
    return {
        "name": name,
        "note": note,
        "perfect": perfect,
        **st,
        **_cov(rows, sess),
        "buy_n": by_side["BUY"],
        "sell_n": by_side["SELL"],
        "buy_hit": round(100.0 * by_side["BUY_w"] / by_side["BUY"], 1) if by_side["BUY"] else None,
        "sell_hit": round(100.0 * by_side["SELL_w"] / by_side["SELL"], 1) if by_side["SELL"] else None,
    }


def _months(rows: List[dict]) -> Dict[str, Dict[str, Any]]:
    g: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        g[str(r["day"])[:7]].append(r)
    out = {}
    for m, rs in sorted(g.items()):
        w = sum(1 for r in rs if r.get("win"))
        out[m] = {
            "n": len(rs),
            "hit_pct": round(100.0 * w / len(rs), 1) if rs else None,
            "points": round(sum(float(r.get("points") or 0) for r in rs), 1),
            "perfect": bool(rs) and all(bool(r.get("win")) for r in rs),
        }
    return out


def time_agree(
    gate_ix: Dict[Tuple[str, str], List[dict]],
    entry_ix: Dict[Tuple[str, str], List[dict]],
    *,
    tol: int,
    p_min: float = 0.0,
    side_only: Optional[str] = None,
    morning: bool = False,
    gate_track: Optional[str] = None,
    entry_track: Optional[str] = None,
    tag: str,
) -> List[dict]:
    out: List[dict] = []
    for (day, side), grows in gate_ix.items():
        if side_only and side != side_only:
            continue
        frows = entry_ix.get((day, side)) or []
        if not frows:
            continue
        if gate_track:
            grows = [g for g in grows if str(g.get("track") or "") == gate_track]
        if entry_track:
            frows = [f for f in frows if str(f.get("track") or "") == entry_track]
        if not grows or not frows:
            continue
        if p_min > 0:
            frows = [f for f in frows if float(f.get("p_t1") or 0) >= p_min]
        if not frows:
            continue
        if morning:
            grows = [g for g in grows if _hm_mins(str(g.get("hm") or "99:99")) < 12 * 60 + 30]
            frows = [f for f in frows if _hm_mins(str(f.get("hm") or "99:99")) < 12 * 60 + 30]
        if not grows or not frows:
            continue
        picked = None
        agree_hm = None
        for g in sorted(grows, key=lambda x: _hm_mins(str(x.get("hm") or "99:99"))):
            gm = _hm_mins(str(g.get("hm") or "12:00"))
            near = [
                f
                for f in frows
                if abs(gm - _hm_mins(str(f.get("hm") or "12:00"))) <= tol
            ]
            if not near:
                continue
            best = _best_p(near)
            picked = dict(best)
            agree_hm = g.get("hm")
            break
        if picked is None:
            continue
        picked.update(
            {
                "track": tag,
                "agree_15m_hm": agree_hm,
                "src": "5m",
                "confirm": True,
                "tol_min": tol,
            }
        )
        out.append(picked)
    return out


def day_side_filter(
    entry_rows: List[dict],
    gate_sides: Dict[str, Set[str]],
    *,
    tag: str,
    p_min: float = 0.0,
    side_only: Optional[str] = None,
) -> List[dict]:
    out = []
    for r in entry_rows:
        side = _side(r)
        if side_only and side != side_only:
            continue
        if side not in gate_sides.get(str(r["day"]), set()):
            continue
        if float(r.get("p_t1") or 0) < p_min:
            continue
        out.append(dict(r, track=tag, confirm_gate=True))
    return out


def cap1(rows: List[dict], tag: str) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r["day"])].append(r)
    out = []
    for day in sorted(by):
        best = _best_p(by[day])
        if best:
            out.append(dict(best, track=tag))
    return out


def build_all(
    *,
    dual15: Dict[str, List[dict]],
    dual5: Dict[str, List[dict]],
    pool15: Dict[str, List[dict]],
    crown_htf: List[dict],
    crown_all: List[dict],
    good: List[dict],
    sess: List[str],
) -> Dict[str, List[dict]]:
    p15, c15 = dual15["proven_100"], dual15["champion"]
    any15 = p15 + c15
    p5, c5 = dual5["proven_100"], dual5["champion"]
    any5 = p5 + c5
    pool_p, pool_c = pool15["proven_100"], pool15["champion"]
    pool_any = pool_p + pool_c

    books: Dict[str, List[dict]] = {
        "BASE_dual15_proven": list(p15),
        "BASE_dual15_champ": list(c15),
        "BASE_dual15_any": list(any15),
        "BASE_pool15_proven": list(pool_p),
        "BASE_dual5_proven": list(p5),
        "BASE_dual5_champ": list(c5),
        "BASE_dual5_any": list(any5),
        "BASE_crown_htf": list(crown_htf),
        "BASE_crown_all": list(crown_all),
        "BASE_good_prod2": list(good),
    }

    # indexes
    ix15 = _ix(any15)
    ix15p = _ix(p15)
    ix15c = _ix(c15)
    ix_pool_p = _ix(pool_p)
    ix_pool = _ix(pool_any)
    ix5 = _ix(any5)
    ix5c = _ix(c5)
    ix5p = _ix(p5)
    ix_cr = _ix(crown_htf)
    ix_cr_all = _ix(crown_all)
    # crown as "true prod 5m"
    ix_5m_prod = _ix(any5 + crown_htf)  # dual5 research ∪ crown prod

    s15p = _side_days(p15)
    s15 = _side_days(any15)
    s_pool_p = _side_days(pool_p)

    # --- A: time-agree grids (prod-shaped: gate=15m dual, entry=5m channels) ---
    grids = [
        ("gate15any_entry5any", ix15, ix5),
        ("gate15proven_entry5any", ix15p, ix5),
        ("gate15proven_entry5champ", ix15p, ix5c),
        ("gate15any_entry5champ", ix15, ix5c),
        ("gate15proven_entry_crown", ix15p, ix_cr),
        ("gate15any_entry_crown", ix15, ix_cr),
        ("gate15champ_entry_crown", ix15c, ix_cr),
        ("gate_pool_proven_entry5any", ix_pool_p, ix5),
        ("gate_pool_proven_entry_crown", ix_pool_p, ix_cr),
        ("gate15proven_entry_5mprod", ix15p, ix_5m_prod),
        ("gate15any_entry_5mprod", ix15, ix_5m_prod),
        ("gate15any_entry_crown_all", ix15, ix_cr_all),
    ]
    for gname, gix, eix in grids:
        for tol in TOLS:
            tag = f"T{tol}_{gname}"
            books[tag] = time_agree(gix, eix, tol=tol, tag=tag)

    # --- B: day+side filter (no clock) ---
    books["D_dual5_if_proven15"] = day_side_filter(any5, s15p, tag="D_dual5_if_proven15")
    books["D_dual5_if_any15"] = day_side_filter(any5, s15, tag="D_dual5_if_any15")
    books["D_crown_if_proven15"] = day_side_filter(crown_htf, s15p, tag="D_crown_if_proven15")
    books["D_crown_if_any15"] = day_side_filter(crown_htf, s15, tag="D_crown_if_any15")
    books["D_5mprod_if_proven15"] = day_side_filter(
        any5 + crown_htf, s15p, tag="D_5mprod_if_proven15"
    )

    # --- C: p-floor on best timed books ---
    for tol in (15, 30, 60):
        for pmin in P_FLOORS:
            if pmin <= 0:
                continue
            tag = f"T{tol}_gate15proven_entry5any_p{int(pmin*100)}"
            books[tag] = time_agree(
                ix15p, ix5, tol=tol, p_min=pmin, tag=tag
            )
            tag2 = f"T{tol}_gate15any_entry_crown_p{int(pmin*100)}"
            books[tag2] = time_agree(
                ix15, ix_cr, tol=tol, p_min=pmin, tag=tag2
            )
            tag3 = f"T{tol}_gate15proven_entry_crown_p{int(pmin*100)}"
            books[tag3] = time_agree(
                ix15p, ix_cr, tol=tol, p_min=pmin, tag=tag3
            )

    # --- D: side splits on top timed ---
    for tol in (15, 30):
        for side in ("BUY", "SELL"):
            tag = f"T{tol}_gate15any_entry5any_{side}"
            books[tag] = time_agree(
                ix15, ix5, tol=tol, side_only=side, tag=tag
            )
            tag2 = f"T{tol}_gate15proven_entry_crown_{side}"
            books[tag2] = time_agree(
                ix15p, ix_cr, tol=tol, side_only=side, tag=tag2
            )

    # --- E: morning-only ---
    for tol in (15, 30, 60):
        tag = f"T{tol}_gate15any_entry5any_am"
        books[tag] = time_agree(ix15, ix5, tol=tol, morning=True, tag=tag)
        tag2 = f"T{tol}_gate15any_entry_crown_am"
        books[tag2] = time_agree(ix15, ix_cr, tol=tol, morning=True, tag=tag2)

    # --- F: cap1 hygiene ---
    for src in (
        "T30_gate15any_entry5any",
        "T15_gate15any_entry5any",
        "T30_gate15proven_entry5any",
        "T30_gate15any_entry_crown",
        "T30_gate15proven_entry_crown",
        "T60_gate15any_entry5any",
        "D_crown_if_proven15",
        "D_dual5_if_proven15",
    ):
        if src in books:
            books[f"CAP1_{src}"] = cap1(books[src], f"CAP1_{src}")

    # --- G: union expand — proven15 alone (prod) + timed confirm extras not already proven day ---
    proven_days = {r["day"] for r in p15}
    for src in (
        "T30_gate15any_entry5any",
        "T15_gate15any_entry5any",
        "T30_gate15champ_entry_crown",
        "T30_gate15any_entry_crown",
        "T60_gate15any_entry_crown",
    ):
        if src not in books:
            continue
        extras = [r for r in books[src] if r["day"] not in proven_days]
        books[f"PROVEN15_PLUS_{src}"] = list(p15) + [
            dict(r, track=f"add_{src}") for r in extras
        ]

    # --- H: vs existing AGREE shape — good15 ∩ dual5 / crown (reference) ---
    ix_good = _ix(good)
    books["REF_agree_good_dual5"] = time_agree(ix_good, ix5, tol=9999, tag="REF_agree_good_dual5")
    # day+side only via huge tol
    books["REF_agree_good_crown"] = time_agree(ix_good, ix_cr, tol=9999, tag="REF_agree_good_crown")
    books["REF_time30_good_dual5"] = time_agree(ix_good, ix5, tol=30, tag="REF_time30_good_dual5")
    books["REF_time30_good_crown"] = time_agree(ix_good, ix_cr, tol=30, tag="REF_time30_good_crown")

    return books


def eval_window(
    label: str,
    start: str,
    end: str,
    channels: Dict[str, Any],
) -> Dict[str, Any]:
    sess = [d for d in channels["sessions"] if start < d <= end]
    dual15 = {k: _clip(v, start, end) for k, v in channels["dual15"].items()}
    dual5 = {k: _clip(v, start, end) for k, v in channels["dual5"].items()}
    pool15 = {k: _clip(v, start, end) for k, v in channels["pool15"].items()}
    books = build_all(
        dual15=dual15,
        dual5=dual5,
        pool15=pool15,
        crown_htf=_clip(channels["crown_htf"], start, end),
        crown_all=_clip(channels["crown_all"], start, end),
        good=_clip(channels["good"], start, end),
        sess=sess,
    )
    scored = [_pack(n, rs, sess) for n, rs in books.items()]
    scored.sort(key=lambda r: (r.get("hit_pct") or 0, r.get("n") or 0), reverse=True)

    perfect = [r for r in scored if r.get("perfect") and (r.get("n") or 0) >= PASS_N]
    ge95 = [
        r
        for r in scored
        if (r.get("n") or 0) >= PASS_N and (r.get("hit_pct") or 0) >= PASS_HIT
    ]
    ge90_n15 = [
        r
        for r in scored
        if (r.get("n") or 0) >= 15 and (r.get("hit_pct") or 0) >= 90
    ]
    # max-n among perfect
    best_perfect = max(perfect, key=lambda r: r["n"]) if perfect else None
    best_ge95 = max(ge95, key=lambda r: (r["hit_pct"], r["n"])) if ge95 else None

    return {
        "label": label,
        "start": start,
        "end": end,
        "sessions": len(sess),
        "board": scored,
        "perfect_n8": perfect,
        "ge95_n8": ge95,
        "ge90_n15": ge90_n15,
        "best_perfect": best_perfect,
        "best_ge95": best_ge95,
        "books": books,  # keep for monthly on winners
    }


def main() -> None:
    t0 = time.time()
    print("DEEP confirm: 15m dual gate × 5m entry", flush=True)
    if not CACHE.is_file():
        raise SystemExit(f"missing cache {CACHE} — run research_dual15_dual5_confirm100.py first")

    cached = json.loads(CACHE.read_text(encoding="utf-8"))
    dual15_all = cached["dual15"]
    dual5_all = cached["dual5"]
    print(
        f"  cache dual15 proven={len(dual15_all['proven_100'])} champ={len(dual15_all['champion'])}",
        flush=True,
    )
    print(
        f"  cache dual5  proven={len(dual5_all['proven_100'])} champ={len(dual5_all['champion'])}",
        flush=True,
    )

    pool = json.loads(POOL.read_text(encoding="utf-8"))
    pool15_all = {
        "proven_100": list(pool["proven_100"]),
        "champion": _champ_floor(list(pool["champion"])),
    }
    crown_all = [
        dict(r, track="crown_5m", priority=PRIORITY["crown_5m"])
        for r in pool["crown_5m"]
    ]

    sessions_all, prod2_all, _ = fs._prod2(1400)
    good_all = [
        dict(r, track="good_prod2", priority=PRIORITY["good_prod2"])
        for r in prod2_all
    ]
    # sessions from cache range
    sess = sorted(
        d
        for d in sessions_all
        if cached["start"] < d <= cached["end"]
    )
    # align with dual cache days if needed
    print(f"  sessions={len(sess)} good={len(good_all)} crown={len(crown_all)}", flush=True)

    daily = fs._load_daily()
    active = fs._active_days(sess, daily)
    crown_htf_all = [r for r in crown_all if r["day"] in active]
    print(f"  crown_htf={len(crown_htf_all)} active_days={len(active)}", flush=True)

    channels = {
        "sessions": sess,
        "dual15": dual15_all,
        "dual5": dual5_all,
        "pool15": pool15_all,
        "crown_htf": crown_htf_all,
        "crown_all": crown_all,
        "good": good_all,
    }

    windows = {
        "3y": eval_window("3y", START_3Y, END, channels),
        "1y": eval_window("1y", START_1Y, END, channels),
        "6m": eval_window("6m", START_6M, END, channels),
        "nov": eval_window("nov", START_NOV, END, channels),
    }

    # both-year: 1y & 3y hit≥95 n≥8 (1y n≥5 ok if 3y n≥8)
    b1 = {r["name"]: r for r in windows["1y"]["board"]}
    b3 = {r["name"]: r for r in windows["3y"]["board"]}
    b6 = {r["name"]: r for r in windows["6m"]["board"]}
    bn = {r["name"]: r for r in windows["nov"]["board"]}

    confirmed = []
    for name, r3 in b3.items():
        r1 = b1.get(name)
        if not r1:
            continue
        if (r3.get("n") or 0) < PASS_N:
            continue
        if (r1.get("n") or 0) < 5:
            continue
        if (r3.get("hit_pct") or 0) >= PASS_HIT and (r1.get("hit_pct") or 0) >= PASS_HIT:
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
                    "hit_6m": (b6.get(name) or {}).get("hit_pct"),
                    "n_6m": (b6.get(name) or {}).get("n"),
                    "hit_nov": (bn.get(name) or {}).get("hit_pct"),
                    "n_nov": (bn.get(name) or {}).get("n") or 0,
                }
            )
    confirmed.sort(
        key=lambda r: (r["perfect_3y"], r["hit_3y"], r["n_3y"], r["points_3y"] or 0),
        reverse=True,
    )

    # monthly for top candidates
    top_names = []
    for r in confirmed[:12]:
        top_names.append(r["name"])
    for r in windows["3y"]["perfect_n8"][:8]:
        if r["name"] not in top_names:
            top_names.append(r["name"])
    # always include key baselines
    for n in (
        "BASE_dual15_proven",
        "T30_gate15any_entry5any",
        "T15_gate15any_entry5any",
        "T30_gate15proven_entry_crown",
        "T30_gate15any_entry_crown",
        "PROVEN15_PLUS_T30_gate15any_entry5any",
        "PROVEN15_PLUS_T30_gate15any_entry_crown",
    ):
        if n not in top_names:
            top_names.append(n)

    monthly = {}
    books_1y = windows["1y"]["books"]
    for name in top_names:
        rows = books_1y.get(name) or []
        monthly[name] = _months(rows)

    # Pareto: among confirmed perfect, max n; among ge95 max n
    perfect_conf = [c for c in confirmed if c["perfect_3y"] and c["perfect_1y"]]
    best_add = None
    for name in (
        "PROVEN15_PLUS_T30_gate15any_entry5any",
        "PROVEN15_PLUS_T15_gate15any_entry5any",
        "PROVEN15_PLUS_T30_gate15any_entry_crown",
        "PROVEN15_PLUS_T60_gate15any_entry_crown",
    ):
        r = b3.get(name)
        if r and (best_add is None or (r.get("n") or 0) > (best_add.get("n") or 0)):
            best_add = {"name": name, **r}

    # drop heavy books from payload
    for w in windows.values():
        w.pop("books", None)

    payload = {
        "goal": "Deep: 15m dual gate (prod proven exists) × 5m entry confirm — expand 100%",
        "facts": {
            "prod_15m_dual_proven": True,
            "prod_5m_proven": False,
            "prod_5m_channel": "crown_5m only",
            "research_5m_dual": "same packs replayed on 5m — not a trained 5m proven",
        },
        "windows": {
            k: {
                "sessions": v["sessions"],
                "best_perfect": v["best_perfect"],
                "best_ge95": v["best_ge95"],
                "perfect_n8": v["perfect_n8"][:25],
                "ge95_n8": v["ge95_n8"][:40],
                "ge90_n15": v["ge90_n15"][:25],
                "board_top": v["board"][:40],
            }
            for k, v in windows.items()
        },
        "both_year_ge95": confirmed,
        "monthly_1y_top": monthly,
        "best_proven15_plus": best_add,
        "elapsed_s": round(time.time() - t0, 1),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "CONFIRM_DUAL_TF_DEEP.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    LEDGER.mkdir(parents=True, exist_ok=True)
    (LEDGER / "CONFIRM_DUAL_TF_DEEP.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    # markdown
    lines = [
        "# Deep research — 15m dual gate × 5m entry confirm",
        "",
        "**Prod facts:** 15m dual `proven_100` is already live · 5m has **no** proven (only `crown_5m`).",
        "",
        "Research only. Final / holding unchanged.",
        "",
        "## Question",
        "",
        "Can we build a **100% / ≥95% confirm** book whose **entry is 5m**, gated by 15m dual,",
        "and ideally **add** calls beyond prod proven — without inventing a fake 5m proven?",
        "",
        "## Baselines (3y)",
        "",
        "| Book | N | Hit | Perfect | Day |",
        "|---|---:|---:|---|---:|",
    ]
    for name in (
        "BASE_dual15_proven",
        "BASE_dual15_any",
        "BASE_dual5_any",
        "BASE_dual5_proven",
        "BASE_crown_htf",
        "T30_gate15any_entry5any",
        "T15_gate15any_entry5any",
        "T30_gate15proven_entry_crown",
        "T30_gate15any_entry_crown",
        "D_crown_if_proven15",
        "PROVEN15_PLUS_T30_gate15any_entry5any",
        "PROVEN15_PLUS_T30_gate15any_entry_crown",
        "REF_time30_good_crown",
        "REF_agree_good_crown",
    ):
        r = b3.get(name)
        if not r:
            continue
        lines.append(
            f"| `{name}` | {r['n']} | **{r['hit_pct']}%** | {r['perfect']} | {r['day_cov_pct']}% |"
        )

    lines += [
        "",
        "## Perfect books 3y (n≥8) — max coverage first",
        "",
    ]
    perf = sorted(windows["3y"]["perfect_n8"], key=lambda r: r["n"], reverse=True)
    if not perf:
        lines.append("_None._")
    else:
        lines += ["| Book | N | Day | Points | 1y hit/n |", "|---|---:|---:|---:|---|"]
        for r in perf[:30]:
            r1 = b1.get(r["name"]) or {}
            lines.append(
                f"| `{r['name']}` | {r['n']} | {r['day_cov_pct']}% | {r.get('points')} | "
                f"{r1.get('hit_pct')}% / {r1.get('n')} |"
            )

    lines += ["", "## Both-year ≥95% (sorted perfect → n)", ""]
    if not confirmed:
        lines.append("_None cleared._")
    else:
        lines += [
            "| Book | 1y | 3y | 6m | Nov |",
            "|---|---|---|---|---|",
        ]
        for r in confirmed[:40]:
            lines.append(
                f"| `{r['name']}` | {r['hit_1y']}%/{r['n_1y']} "
                f"{'P' if r['perfect_1y'] else ''} | "
                f"**{r['hit_3y']}%**/{r['n_3y']} {'P' if r['perfect_3y'] else ''} | "
                f"{r.get('hit_6m')}%/{r.get('n_6m')} | "
                f"{r.get('hit_nov')}%/{r.get('n_nov')} |"
            )

    lines += ["", "## Expand beyond prod proven (PROVEN15_PLUS_*)", ""]
    if best_add:
        lines.append(
            f"- Best add-on combo: `{best_add['name']}` → "
            f"**{best_add.get('hit_pct')}%** n={best_add.get('n')} "
            f"perfect={best_add.get('perfect')} day={best_add.get('day_cov_pct')}%"
        )
    else:
        lines.append("_No plus book outperformed on board lookup._")
    for name in (
        "BASE_dual15_proven",
        "PROVEN15_PLUS_T30_gate15any_entry5any",
        "PROVEN15_PLUS_T15_gate15any_entry5any",
        "PROVEN15_PLUS_T30_gate15any_entry_crown",
        "PROVEN15_PLUS_T60_gate15any_entry_crown",
    ):
        r = b3.get(name)
        if r:
            lines.append(
                f"- `{name}`: n={r['n']} hit={r['hit_pct']}% perfect={r['perfect']} pts={r.get('points')}"
            )

    lines += ["", "## 1y monthly (selected)", ""]
    for name in top_names[:8]:
        mm = monthly.get(name) or {}
        if not mm:
            continue
        lines.append(f"### `{name}`")
        lines.append("")
        lines.append("| Month | N | Hit | Perfect | Pts |")
        lines.append("|---|---:|---:|---|---:|")
        for m, st in mm.items():
            lines.append(
                f"| {m} | {st['n']} | {st['hit_pct']}% | {st['perfect']} | {st['points']} |"
            )
        lines.append("")

    # Nov detail
    lines += ["## Nov 2026 (n>0)", "", "| Book | N | Hit | Perfect |", "|---|---:|---:|---|"]
    for r in windows["nov"]["board"]:
        if (r.get("n") or 0) < 1:
            continue
        lines.append(
            f"| `{r['name']}` | {r['n']} | **{r['hit_pct']}%** | {r['perfect']} |"
        )

    # recommendation
    rec = None
    for c in confirmed:
        if c["perfect_3y"] and c["perfect_1y"] and "entry5" in c["name"]:
            rec = c
            break
    if rec is None:
        for c in confirmed:
            if c["perfect_3y"] and c["perfect_1y"]:
                rec = c
                break
    if rec is None and confirmed:
        rec = confirmed[0]

    lines += ["", "## Recommended research logic", ""]
    if rec:
        lines += [
            f"**Primary confirm tag:** `{rec['name']}`",
            "",
            f"- 1y: {rec['hit_1y']}% / n={rec['n_1y']} · 3y: **{rec['hit_3y']}%** / n={rec['n_3y']}",
            "",
            "```",
            "GATE  = 15m dual (proven_100 and/or champion) — already in prod",
            "ENTRY = 5m dual replay OR crown_5m (prod 5m channel)",
            "RULE  = same day + side + clock tolerance from tag",
            "TAKE  = best p_t1 on ENTRY ticket (5m P&L)",
            "NOTE  = do not invent a 5m proven_100 pack; crown or timed dual5 only",
            "```",
        ]
    else:
        lines.append("_No both-year ≥95% book — see board._")

    lines += [
        "",
        "## Verdict",
        "",
        "1. **Prod 15m dual proven stays the only true 100% dual proven book** (n≈41/3y).",
        "2. **No 5m proven exists** — replaying dual gates on 5m is research-only and weak alone.",
        "3. **Timed 15m∩5m agree** is the path to 100% *on a 5m entry*, but coverage stays thin.",
        "4. **Crown as 5m entry** gated by 15m dual is the prod-shaped alternative to explore for more n.",
        "5. Prefer **PROVEN15_PLUS_*** only if add-ons keep ≥95% — else keep confirm as a parallel accurate tag.",
        "",
        f"Elapsed {payload['elapsed_s']}s · `CONFIRM_DUAL_TF_DEEP.md`",
        "",
    ]

    md = OUT / "CONFIRM_DUAL_TF_DEEP.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (LEDGER / "CONFIRM_DUAL_TF_DEEP.md").write_text("\n".join(lines), encoding="utf-8")
    # research-and-analysis mirror if present
    ra = Path(r"C:\Users\Priyanka\research-and-analysis\feature\final-logic-ledger")
    if ra.is_dir():
        (ra / "CONFIRM_DUAL_TF_DEEP.md").write_text("\n".join(lines), encoding="utf-8")
        (ra / "CONFIRM_DUAL_TF_DEEP.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )

    print("Wrote", md, flush=True)
    print(
        json.dumps(
            {
                "confirmed_ge95": len(confirmed),
                "perfect_3y_n8": len(windows["3y"]["perfect_n8"]),
                "best_perfect_3y": (windows["3y"]["best_perfect"] or {}).get("name"),
                "best_perfect_n": (windows["3y"]["best_perfect"] or {}).get("n"),
                "top_confirmed": [
                    {"name": c["name"], "n_3y": c["n_3y"], "hit_3y": c["hit_3y"], "P": c["perfect_3y"]}
                    for c in confirmed[:8]
                ],
                "proven_plus": {
                    "name": (best_add or {}).get("name"),
                    "n": (best_add or {}).get("n"),
                    "hit": (best_add or {}).get("hit_pct"),
                    "perfect": (best_add or {}).get("perfect"),
                },
                "elapsed_s": payload["elapsed_s"],
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
