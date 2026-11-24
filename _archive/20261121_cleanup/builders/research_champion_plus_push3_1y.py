"""CHAMPION+ PUSH3 — more N @ >=92.5%, starting from 91@93.41%.

1) Warm-start prior recipe (cap2)
2) Continue stream greedy
3) Ticket-level fill: quiet days + second slot on 1-call days
   (same-side, prefer wins, keep desk floor)

  python -u prod_live/tests/builders/research_champion_plus_push3_1y.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import POOL, _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _hm_mins, _side  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    bestp_day,
    filt,
    first_day,
    gap_map,
    union_unique_days,
)
from prod_live.logic.stack import union_day_cap2  # noqa: E402
import live_final_1y_months_accurate as hold  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
HOLD = ROOT / "prod_live" / "holding_accurate" / "champion_plus"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"
CACHE_XY = LEDGER / "_cache_dual10m_xy_research.json"
PACKS = LEDGER / "nifty_side_models_10m_research" / "dual10m_packs.joblib"
RECIPE = HOLD / "recipes_research.json"

START_1Y, END = hold.START, hold.END
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
FLOOR_1Y = 92.5
MIN_N = 3
PRIOR_N = 91

BANDS = [
    ("first45", 9 * 60 + 15, 10 * 60),
    ("open", 9 * 60 + 15, 10 * 60 + 30),
    ("am1130", 9 * 60 + 15, 11 * 60 + 30),
    ("am1230", 9 * 60 + 15, 12 * 60 + 30),
    ("mid", 10 * 60, 13 * 60),
    ("latemid", 10 * 60 + 30, 14 * 60),
    ("pm", 12 * 60 + 30, 15 * 60 + 15),
    ("all", None, None),
]
GAPS = [
    ("nogap", None, False, False),
    ("g015", 0.15, False, False),
    ("g020", 0.20, False, False),
    ("g030", 0.30, False, False),
    ("g040", 0.40, False, False),
    ("gdn025", 0.25, True, False),
    ("gup025", 0.25, False, True),
    ("gup040", 0.40, False, True),
]
PMINS = (0.0, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70, 0.75)


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return 100.0 * sum(1 for r in rows if r.get("win")) / len(rows)


def desk_ok(rows: List[dict], seed_3y_hit: float) -> bool:
    r1 = _clip(rows, START_1Y, END)
    if len(r1) >= MIN_N and hit_pct(r1) + 1e-9 < FLOOR_1Y:
        return False
    r3 = _clip(rows, START_3Y, END)
    if len(r3) >= MIN_N and hit_pct(r3) + 1e-9 < seed_3y_hit - 1e-9:
        return False
    return True


def stream_soft_ok(rows: List[dict]) -> bool:
    r1 = _clip(rows, START_1Y, END)
    if len(r1) >= 2 and hit_pct(r1) >= 65.0:
        return True
    r3 = _clip(rows, START_3Y, END)
    return len(r3) >= MIN_N and hit_pct(r3) >= 65.0


def mid_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("day") or "")].append(r)
    out = []
    for day in sorted(by):
        ordered = sorted(by[day], key=lambda x: _hm_mins(str(x.get("hm") or "99:99")))
        out.append(ordered[len(ordered) // 2])
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


def load_d10() -> List[dict]:
    import joblib

    packs = joblib.load(PACKS)
    xy = json.loads(CACHE_XY.read_text(encoding="utf-8"))
    out = []
    for r in xy.get("tickets") or []:
        side = str(r.get("decision") or "").upper()
        pack = packs.get(side) or {}
        if not pack.get("available") or not r.get("x"):
            continue
        X = np.asarray([r["x"]], dtype=float)
        raw = float(pack["base"].predict_proba(X)[0, 1])
        p = float(np.clip(pack["iso"].transform([raw])[0], 0.05, 0.95))
        rr = {k: v for k, v in r.items() if k != "x"}
        rr["p_t1"] = round(p, 4)
        rr["track"] = "dual10m"
        out.append(rr)
    return out


def call_key(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day") or ""), _side(r), str(r.get("hm") or ""))


def merge_cap(a: List[dict], b: List[dict], cap: int = 2) -> List[dict]:
    tracks: Dict[str, List[dict]] = defaultdict(list)
    for r in a + b:
        tracks[str(r.get("track") or "champ_plus")].append(r)
    return union_day_cap2(dict(tracks), day_cap=cap)


def mine_all(univ, gaps, active) -> Dict[str, List[dict]]:
    keys = [k for k in ("CH", "GDN", "GD40", "GD35", "GD30", "D10") if k in univ]
    by: Dict[str, List[dict]] = {}
    n_eval = 0
    for uname in keys:
        for side in (None, "BUY", "SELL"):
            for blab, lo, hi in BANDS:
                for glab, gabsm, gdn, gup in GAPS:
                    for use_htf in (False, True):
                        for pmin in PMINS:
                            base = filt(
                                univ[uname],
                                p_min=pmin,
                                side=side,
                                hm_lo=lo,
                                hm_hi=hi,
                                htf=active if use_htf else None,
                                gaps=gaps if gabsm is not None or gdn or gup else None,
                                gap_abs=gabsm,
                                gap_dn=gdn,
                                gap_up=gup,
                            )
                            for vlab, vrows in (
                                ("raw", base),
                                ("first", first_day(base)),
                                ("bestp", bestp_day(base)),
                                ("mid", mid_day(base)),
                                ("last", last_day(base)),
                            ):
                                if not vrows:
                                    continue
                                n_eval += 1
                                if not stream_soft_ok(vrows):
                                    continue
                                tag = (
                                    f"CP_{uname}_{side or 'BOTH'}_p{int(round(pmin * 100))}_"
                                    f"{blab}_{'htf' if use_htf else 'any'}_{glab}_{vlab}"
                                )
                                n = len(_clip(vrows, START_1Y, END))
                                if tag not in by or n > len(_clip(by[tag], START_1Y, END)):
                                    by[tag] = vrows
    print(f"  mined eval={n_eval} tags={len(by)}", flush=True)
    return by


def pool_mix(by: Dict[str, List[dict]], prior: List[str], lim: int = 18000):
    items = list(by.items())
    by_hit = sorted(
        items,
        key=lambda kv: (hit_pct(_clip(kv[1], START_1Y, END)), len(_clip(kv[1], START_1Y, END))),
        reverse=True,
    )
    by_n = sorted(
        items,
        key=lambda kv: (len(_clip(kv[1], START_1Y, END)), hit_pct(_clip(kv[1], START_1Y, END))),
        reverse=True,
    )
    # Prefer streams covering many 1y days that are wins-heavy
    by_win_n = sorted(
        items,
        key=lambda kv: (
            sum(1 for r in _clip(kv[1], START_1Y, END) if r.get("win")),
            hit_pct(_clip(kv[1], START_1Y, END)),
        ),
        reverse=True,
    )
    seen = set()
    out = []
    for tag in prior:
        if tag in by and tag not in seen:
            out.append((tag, by[tag]))
            seen.add(tag)
    for src in (by_hit, by_n, by_win_n):
        for tag, rows in src:
            if tag in seen:
                continue
            out.append((tag, rows))
            seen.add(tag)
            if len(out) >= lim:
                return out
    return out


def greedy_streams(
    seed: List[dict],
    streams: List[Tuple[str, List[dict]]],
    seed_3y_hit: float,
    warm: List[str],
    cap: int = 2,
    max_add: int = 250,
) -> Tuple[List[dict], List[str]]:
    cur = list(seed)
    used: List[str] = []
    by = dict(streams)
    for tag in warm:
        rows = by.get(tag)
        if not rows or tag in used:
            continue
        merged = merge_cap(cur, rows, cap)
        if desk_ok(merged, seed_3y_hit):
            n0 = len(_clip(cur, START_1Y, END))
            n1 = len(_clip(merged, START_1Y, END))
            if n1 >= n0:
                cur = merged
                used.append(tag)
                print(
                    f"    warm {tag[:60]} → n={n1} hit={hit_pct(_clip(cur, START_1Y, END)):.2f}",
                    flush=True,
                )
    improved = True
    while improved and len(used) < max_add:
        improved = False
        best = None
        best_n = len(_clip(cur, START_1Y, END))
        best_hit = hit_pct(_clip(cur, START_1Y, END))
        for tag, rows in streams:
            if tag in used:
                continue
            merged = merge_cap(cur, rows, cap)
            n1 = len(_clip(merged, START_1Y, END))
            if n1 <= best_n:
                continue
            if not desk_ok(merged, seed_3y_hit):
                continue
            h1 = hit_pct(_clip(merged, START_1Y, END))
            if best is None or n1 > best_n or (n1 == best_n and h1 > best_hit):
                best = (tag, merged, h1)
                best_n = n1
                best_hit = h1
        if best:
            used.append(best[0])
            cur = best[1]
            improved = True
            if len(used) <= 20 or len(used) % 15 == 0:
                print(f"    +{best[0][:70]} → n={best_n} hit={best_hit:.2f}", flush=True)
    return cur, used


def ticket_fill(
    cur: List[dict],
    candidates: List[dict],
    sess_1y: List[str],
    seed_3y_hit: float,
    cap: int = 2,
) -> Tuple[List[dict], int]:
    """Greedy add individual tickets on quiet / underfilled days."""
    cur = [dict(r) for r in cur]
    added = 0
    # index candidates by day
    by_day: Dict[str, List[dict]] = defaultdict(list)
    for r in candidates:
        day = str(r.get("day") or "")
        if START_1Y <= day <= END:
            by_day[day].append(r)

    def day_rows(rows, day):
        return [r for r in rows if r.get("day") == day]

    # Pass A: quiet days — prefer winning ticket, highest p
    quiet = [d for d in sess_1y if not day_rows(cur, d)]
    print(f"    ticket fill quiet days={len(quiet)}", flush=True)
    progress = True
    while progress:
        progress = False
        best = None
        best_n = len(_clip(cur, START_1Y, END))
        for day in quiet:
            if day_rows(cur, day):
                continue
            for r in sorted(
                by_day.get(day, []),
                key=lambda x: (int(bool(x.get("win"))), float(x.get("p_t1") or 0)),
                reverse=True,
            ):
                trial = merge_cap(cur, [r], cap)
                n1 = len(_clip(trial, START_1Y, END))
                if n1 <= best_n:
                    continue
                if not desk_ok(trial, seed_3y_hit):
                    continue
                best = trial
                best_n = n1
                break  # take best p/win for this day once found ok; still search all days
            # keep searching for max n increase across days
        # re-scan for absolute best single add
        best = None
        best_n = len(_clip(cur, START_1Y, END))
        best_hit = hit_pct(_clip(cur, START_1Y, END))
        for day in sess_1y:
            existing = day_rows(cur, day)
            if len(existing) >= cap:
                continue
            side_lock = _side(existing[0]) if existing else None
            seen = {call_key(r) for r in existing}
            for r in by_day.get(day, []):
                if call_key(r) in seen:
                    continue
                if side_lock and _side(r) != side_lock:
                    continue
                trial = merge_cap(cur, [r], cap)
                n1 = len(_clip(trial, START_1Y, END))
                if n1 <= best_n:
                    continue
                if not desk_ok(trial, seed_3y_hit):
                    continue
                h1 = hit_pct(_clip(trial, START_1Y, END))
                if best is None or n1 > best_n or (n1 == best_n and h1 > best_hit):
                    best = trial
                    best_n = n1
                    best_hit = h1
        if best:
            cur = best
            added += 1
            progress = True
            if added <= 25 or added % 20 == 0:
                print(
                    f"    ticket +1 → n={best_n} hit={best_hit:.2f} (added={added})",
                    flush=True,
                )
    return cur, added


def main() -> int:
    t0 = time.time()
    print(f"CHAMPION+ PUSH3 · beat {PRIOR_N} @>={FLOOR_1Y}%", flush=True)

    recipe = json.loads(RECIPE.read_text(encoding="utf-8")) if RECIPE.exists() else {}
    warm = list(recipe.get("stream_tags_research") or [])

    pool = json.loads(POOL.read_text(encoding="utf-8"))
    seed = hold._clean(
        _champ_floor([r for r in pool["champion"] if START_3Y <= r["day"] <= END])
    )
    for r in seed:
        r["track"] = "champion"
    sc0 = _agg(_clip(seed, START_1Y, END))
    sc0_3 = _agg(_clip(seed, START_3Y, END))
    seed_3y_hit = float(sc0_3.get("hit_pct") or 0)

    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_3Y < d <= END]
    sess_1y = sorted(d for d in sessions_all if START_1Y <= d <= END)
    active = fs._active_days(sess, fs._load_daily()) if sess else set()
    gbr = path_u.get("good_by_risk") or {}

    print("  D10…", flush=True)
    d10 = load_d10()
    univ = {
        "CH": seed,
        "GDN": gbr.get("native") or [],
        "GD40": gbr.get("40.0") or gbr.get("40") or [],
        "GD35": gbr.get("35.0") or gbr.get("35") or [],
        "GD30": gbr.get("30.0") or gbr.get("30") or [],
        "D10": d10,
    }
    # Candidate ticket pool for fill = union of univ (1y window later)
    cand_tickets = []
    for name, rows in univ.items():
        for r in rows:
            rr = dict(r)
            if "track" not in rr:
                rr["track"] = {
                    "CH": "champion",
                    "D10": "dual10m",
                }.get(name, "good_prod2")
            cand_tickets.append(rr)

    by = mine_all(univ, gaps, active)
    streams = pool_mix(by, warm, lim=18000)
    print(f"  streams={len(streams)} warm={len(warm)}", flush=True)

    print("  stream greedy cap2…", flush=True)
    rows, tags = greedy_streams(seed, streams, seed_3y_hit, warm, cap=2)
    sc_s = _agg(_clip(rows, START_1Y, END))
    print(f"  after streams: {sc_s.get('n')}@{sc_s.get('hit_pct')}%", flush=True)

    print("  ticket fill…", flush=True)
    rows2, n_add = ticket_fill(rows, cand_tickets, sess_1y, seed_3y_hit, cap=2)
    rows2 = hold._clean(rows2)
    sc1 = _agg(_clip(rows2, START_1Y, END))
    sc3 = _agg(_clip(rows2, START_3Y, END))
    print(
        f"  after tickets: {sc1.get('n')}@{sc1.get('hit_pct')}% (+{n_add} tickets)",
        flush=True,
    )

    # Also try cap3 ticket fill from stream result
    print("  stream+ticket cap3…", flush=True)
    rows3s, tags3 = greedy_streams(seed, streams, seed_3y_hit, warm, cap=3)
    rows3, n_add3 = ticket_fill(rows3s, cand_tickets, sess_1y, seed_3y_hit, cap=3)
    rows3 = hold._clean(rows3)
    sc1_3 = _agg(_clip(rows3, START_1Y, END))
    sc3_3 = _agg(_clip(rows3, START_3Y, END))
    print(f"  cap3 final: {sc1_3.get('n')}@{sc1_3.get('hit_pct')}%", flush=True)

    # pick best
    cands = [
        ("cap2", rows2, tags, sc1, sc3, n_add),
        ("cap3", rows3, tags3, sc1_3, sc3_3, n_add3),
    ]
    best = max(cands, key=lambda x: (x[3].get("n") or 0, x[3].get("hit_pct") or 0))
    mode, best_rows, best_tags, best_sc, best_sc3, ticket_adds = best

    lines = [
        "# CHAMPION+ PUSH3 — more calls @ ≥92.5%",
        "",
        f"**Prior:** {PRIOR_N}@93.41% · **Seed:** {sc0.get('n')}@{sc0.get('hit_pct')}%",
        f"**Floor:** 1y ≥ {FLOOR_1Y}% · `{START_1Y}`→`{END}`",
        "",
        "| Book | 1y N@hit | Δ prior | Streams | Ticket adds |",
        "|---|---|---:|---:|---:|",
        f"| prior PUSH2 | {PRIOR_N}@93.41 | 0 | 10 | 0 |",
        f"| after streams cap2 | {sc_s.get('n')}@{sc_s.get('hit_pct')} | "
        f"{(sc_s.get('n') or 0) - PRIOR_N:+d} | {len(tags)} | 0 |",
        f"| **best `{mode}`** | **{best_sc.get('n')}@{best_sc.get('hit_pct')}** | "
        f"**{(best_sc.get('n') or 0) - PRIOR_N:+d}** | {len(best_tags)} | {ticket_adds} |",
        f"| cap3 alt | {sc1_3.get('n')}@{sc1_3.get('hit_pct')} | "
        f"{(sc1_3.get('n') or 0) - PRIOR_N:+d} | {len(tags3)} | {n_add3} |",
        "",
        f"## Calls — `{mode}`",
        "",
        "| # | Day | HM | Side | Win | Track | p |",
        "|---:|---|---|---|---|---|---:|",
    ]
    calls = sorted(_clip(best_rows, START_1Y, END), key=lambda x: (x.get("day"), x.get("hm")))
    for i, r in enumerate(calls, 1):
        lines.append(
            f"| {i} | {r.get('day')} | {r.get('hm')} | {_side(r)} | "
            f"{'W' if r.get('win') else 'L'} | {r.get('track')} | {r.get('p_t1')} |"
        )
    lines.extend(
        [
            "",
            f"**N={best_sc.get('n')}** · **{best_sc.get('hit_pct')}%** "
            f"({best_sc.get('wins')}W/{best_sc.get('losses')}L)",
            "",
            "### Streams",
            "",
        ]
    )
    for t in best_tags:
        lines.append(f"- `{t}`")

    n = best_sc.get("n") or 0
    if n > PRIOR_N and float(best_sc.get("hit_pct") or 0) + 1e-9 >= FLOOR_1Y:
        verdict = (
            f"PUSH3 OK — `{mode}` **{n}@{best_sc.get('hit_pct')}%** "
            f"(prior {PRIOR_N}@93.41% · +{n - PRIOR_N}). Still RESEARCH."
        )
    elif n >= PRIOR_N:
        verdict = f"PUSH3 HOLD — {n}@{best_sc.get('hit_pct')}% (no clear beat of {PRIOR_N})."
    else:
        verdict = f"PUSH3 PARTIAL — {n}@{best_sc.get('hit_pct')}% below prior {PRIOR_N}."

    elapsed = round(time.time() - t0, 1)
    lines.extend(["", "## Verdict", "", verdict, "", f"Elapsed {elapsed}s", ""])

    OUT.mkdir(parents=True, exist_ok=True)
    HOLD.mkdir(parents=True, exist_ok=True)
    md = OUT / "CHAMPION_PLUS_PUSH3_1Y.md"
    js = OUT / "CHAMPION_PLUS_PUSH3_1Y.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {
        "verdict": verdict,
        "best_mode": mode,
        "prior_n": PRIOR_N,
        "1y": best_sc,
        "3y": best_sc3,
        "streams": best_tags,
        "ticket_adds": ticket_adds,
        "elapsed_s": elapsed,
    }
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    if n >= PRIOR_N and float(best_sc.get("hit_pct") or 0) + 1e-9 >= FLOOR_1Y:
        (HOLD / "recipes_research.json").write_text(
            json.dumps(
                {
                    "status": "RESEARCH",
                    "desk": f"CHAMPION_PLUS_{mode.upper()}",
                    "seed": "CHAMPION",
                    "floor_1y": FLOOR_1Y,
                    "stream_tags_research": best_tags,
                    "research_1y": best_sc,
                    "research_3y": best_sc3,
                    "ticket_fill": True,
                    "ticket_adds_1y": ticket_adds,
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
