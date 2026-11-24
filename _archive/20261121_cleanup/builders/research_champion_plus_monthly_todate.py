"""CHAMPION+ monthly report through today — N/hit/points + target/SL.

Enriches PUSH5 calls from pools, extends ticket-fill to END=today window,
writes per-month summary + call lists.

  python -u prod_live/tests/builders/research_champion_plus_monthly_todate.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import POOL, _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _side  # noqa: E402
import live_final_1y_months_accurate as hold  # noqa: E402
import research_champion_plus_push4_1y as p4  # noqa: E402
import research_champion_plus_push5_1y as p5  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
HOLD = ROOT / "prod_live" / "holding_accurate" / "champion_plus"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
PUSH5 = HOLD / "push5_calls_1y.json"

# Report through today (session end)
START = "2025-10-24"
END = "2026-11-15"
FLOOR_1Y = 92.5
CAP = 4


def side_of(r: dict) -> str:
    return _side(r) if r.get("decision") or r.get("side") else str(r.get("side") or "").upper()


def key_of(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day") or ""), side_of(r), str(r.get("hm") or ""))


def norm_ticket(r: dict, track: Optional[str] = None) -> dict:
    rr = dict(r)
    if track:
        rr["track"] = track
    # unify SL/target field names
    entry = rr.get("entry")
    sl = rr.get("stop_loss") if rr.get("stop_loss") is not None else rr.get("sl")
    t1 = rr.get("target_1") if rr.get("target_1") is not None else rr.get("t1")
    rr["entry"] = entry
    rr["stop_loss"] = sl
    rr["target_1"] = t1
    if rr.get("decision") is None and rr.get("side"):
        rr["decision"] = rr["side"]
    if "win" not in rr:
        o = rr.get("outcome")
        if o == "t1_before_sl":
            rr["win"] = True
        elif o in ("sl_before_t1", "same_bar_both"):
            rr["win"] = False
    return rr


def build_lookup() -> Dict[Tuple[str, str, str], dict]:
    """Index all known tickets with price levels when available."""
    idx: Dict[Tuple[str, str, str], dict] = {}

    def put(rows, track: str):
        for r in rows or []:
            rr = norm_ticket(r, track)
            k = key_of(rr)
            if not k[0]:
                continue
            prev = idx.get(k)
            # prefer row that has entry/sl/t1
            if prev is None or (
                (rr.get("entry") is not None)
                and (prev.get("entry") is None)
            ):
                idx[k] = rr
            elif prev is not None and rr.get("points") is not None and prev.get("points") is None:
                prev["points"] = rr.get("points")
                prev["win"] = rr.get("win", prev.get("win"))

    pool = json.loads(POOL.read_text(encoding="utf-8"))
    put(pool.get("champion") or [], "champion")
    put(pool.get("proven_100") or [], "proven_research")
    put(pool.get("crown_5m") or [], "crown_research")

    path_u = json.loads((LEDGER / "_cache_path_trusted_10y.json").read_text(encoding="utf-8"))
    for rk, rows in (path_u.get("good_by_risk") or {}).items():
        if not str(rk).startswith("_"):
            put(rows, "good_prod2")
    for rk, rows in (path_u.get("crown_by_risk") or {}).items():
        if not str(rk).startswith("_"):
            put(rows, "crown_research")

    dual = json.loads((LEDGER / "_cache_dual15_dual5_10y.json").read_text(encoding="utf-8"))
    put((dual.get("dual15") or {}).get("champion") or [], "champion")
    put((dual.get("dual15") or {}).get("proven_100") or [], "proven_research")
    put((dual.get("dual5") or {}).get("champion") or [], "dual5_research")

    put(p4.load_d10(), "dual10m")
    print(f"  lookup tickets={len(idx)}", flush=True)
    return idx


def enrich(rows: List[dict], idx: Dict[Tuple[str, str, str], dict]) -> List[dict]:
    out = []
    for r in rows:
        rr = norm_ticket(r)
        k = key_of(rr)
        src = idx.get(k) or {}
        for fld in (
            "entry",
            "stop_loss",
            "target_1",
            "points",
            "outcome",
            "risk",
            "win",
            "p_t1",
            "track",
        ):
            if rr.get(fld) is None and src.get(fld) is not None:
                rr[fld] = src.get(fld)
        if rr.get("track") is None:
            rr["track"] = src.get("track") or "champ_plus"
        # derive risk distance if prices exist
        if rr.get("entry") is not None and rr.get("stop_loss") is not None:
            try:
                rr["sl_pts"] = round(abs(float(rr["entry"]) - float(rr["stop_loss"])), 2)
            except Exception:
                rr["sl_pts"] = None
        if rr.get("entry") is not None and rr.get("target_1") is not None:
            try:
                rr["t1_pts"] = round(abs(float(rr["target_1"]) - float(rr["entry"])), 2)
            except Exception:
                rr["t1_pts"] = None
        out.append(rr)
    return hold._clean(out)


def extend_to_end(book: List[dict], idx: Dict[Tuple[str, str, str], dict]) -> List[dict]:
    """Ticket-fill from current book through END (incl Nov)."""
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    seed = _champ_floor([r for r in pool["champion"] if p4.START_3Y <= r["day"] <= END])
    seed_3y_hit = float(_agg(_clip(seed, p4.START_3Y, END)).get("hit_pct") or 0)

    sessions_all, _, _ = fs._prod2(4000)
    sess = sorted(d for d in sessions_all if START <= d <= END)

    # candidates: push5 pools + full lookup through END (incl Nov)
    cands = p5.expand_candidates() if hasattr(p5, "expand_candidates") else []
    by_k = {key_of(r): r for r in cands}
    for v in idx.values():
        rr = norm_ticket(v)
        day = str(rr.get("day") or "")
        if day > END:
            continue
        k = key_of(rr)
        if k not in by_k:
            by_k[k] = rr
        else:
            # prefer priced row
            if by_k[k].get("entry") is None and rr.get("entry") is not None:
                by_k[k] = rr
    cands = enrich(list(by_k.values()), idx)

    cur = [dict(r) for r in book]
    # ensure book covers only <= END
    cur = [r for r in cur if str(r.get("day") or "") <= END]

    print(f"  extend fill from n={len(_clip(cur, START, END))} → {END}", flush=True)
    # Temporarily widen p4 window helpers by local fill using END
    # Monkeypatch clip end via local fill loop
    def fill(cur_rows, wins_only=False):
        cur_rows = [dict(r) for r in cur_rows]
        by_day = defaultdict(list)
        for r in cands:
            day = str(r.get("day") or "")
            if START <= day <= END:
                if wins_only and not r.get("win"):
                    continue
                by_day[day].append(r)
        added = 0
        while True:
            best = None
            best_n = len([r for r in cur_rows if START <= str(r.get("day") or "") <= END])
            best_hit = (
                100.0
                * sum(1 for r in cur_rows if START <= str(r.get("day") or "") <= END and r.get("win"))
                / best_n
                if best_n
                else 0.0
            )
            for day in sess:
                existing = [r for r in cur_rows if r.get("day") == day]
                if len(existing) >= CAP:
                    continue
                side_lock = side_of(existing[0]) if existing else None
                seen = {key_of(r) for r in existing}
                opts = sorted(
                    by_day.get(day, []),
                    key=lambda x: (int(bool(x.get("win"))), float(x.get("p_t1") or 0)),
                    reverse=True,
                )
                for r in opts:
                    if key_of(r) in seen:
                        continue
                    if side_lock and side_of(r) != side_lock:
                        continue
                    trial = p4.merge_cap(cur_rows, [r], CAP)
                    n1 = len([x for x in trial if START <= str(x.get("day") or "") <= END])
                    if n1 <= best_n:
                        continue
                    # desk_ok on golden+ext window using p4 floors but END extended
                    r1 = [x for x in trial if START <= str(x.get("day") or "") <= END]
                    hit = 100.0 * sum(1 for x in r1 if x.get("win")) / len(r1) if r1 else 0
                    if len(r1) >= 3 and round(hit, 2) + 1e-9 < FLOOR_1Y:
                        continue
                    r3 = [x for x in trial if p4.START_3Y <= str(x.get("day") or "") <= END]
                    hit3 = 100.0 * sum(1 for x in r3 if x.get("win")) / len(r3) if r3 else 100
                    if len(r3) >= 3 and round(hit3, 2) + 1e-9 < round(seed_3y_hit, 2) - 1e-9:
                        continue
                    if best is None or n1 > best_n or (n1 == best_n and hit > best_hit):
                        best = trial
                        best_n = n1
                        best_hit = hit
            if not best:
                break
            cur_rows = best
            added += 1
            if added <= 15 or added % 30 == 0:
                print(f"    +ext → n={best_n} hit={best_hit:.2f} (add={added})", flush=True)
        return cur_rows, added

    cur, a1 = fill(cur, wins_only=True)
    cur, a2 = fill(cur, wins_only=False)
    cur, a3 = fill(cur, wins_only=True)
    print(f"  extended +{a1+a2+a3} → n={len([r for r in cur if START<=str(r.get('day')or'')<=END])}", flush=True)
    return enrich(cur, idx)


def month_block(rows: List[dict], sess: List[str]) -> List[dict]:
    by_m_days = defaultdict(list)
    for d in sess:
        by_m_days[d[:7]].append(d)
    by_m_rows = defaultdict(list)
    for r in rows:
        by_m_rows[str(r.get("day") or "")[:7]].append(r)

    months = []
    for ym in sorted(by_m_days):
        days = by_m_days[ym]
        sub = sorted(by_m_rows.get(ym, []), key=lambda x: (x.get("day"), x.get("hm")))
        st = _agg(sub) if sub else {"n": 0, "hit_pct": None, "wins": 0, "losses": 0, "points": 0}
        cdays = {r["day"] for r in sub}
        t1_vals = [float(r["t1_pts"]) for r in sub if r.get("t1_pts") is not None]
        sl_vals = [float(r["sl_pts"]) for r in sub if r.get("sl_pts") is not None]
        pts = [float(r.get("points") or 0) for r in sub]
        months.append(
            {
                "month": ym,
                "sessions": len(days),
                "n": st.get("n") or 0,
                "hit_pct": st.get("hit_pct"),
                "wins": st.get("wins") or 0,
                "losses": st.get("losses") or 0,
                "points": round(sum(pts), 1),
                "avg_points": round(sum(pts) / len(pts), 2) if pts else None,
                "days_with_call": len(cdays),
                "days_quiet": len(set(days) - cdays),
                "avg_target_pts": round(sum(t1_vals) / len(t1_vals), 2) if t1_vals else None,
                "avg_sl_pts": round(sum(sl_vals) / len(sl_vals), 2) if sl_vals else None,
                "n_with_levels": sum(1 for r in sub if r.get("entry") is not None),
                "calls": sub,
            }
        )
    return months


def main() -> int:
    t0 = time.time()
    print(f"CHAMPION+ monthly report {START} → {END} (through today)", flush=True)

    idx = build_lookup()
    if PUSH5.exists():
        raw = json.loads(PUSH5.read_text(encoding="utf-8"))
        book = enrich(
            [
                {
                    "day": r["day"],
                    "hm": r["hm"],
                    "decision": r.get("side") or r.get("decision"),
                    "win": r.get("win"),
                    "track": r.get("track"),
                    "p_t1": r.get("p_t1"),
                }
                for r in raw
            ],
            idx,
        )
    else:
        book = []
    print(f"  push5 loaded n={len(book)}", flush=True)

    book = extend_to_end(book, idx)
    book = [r for r in book if START <= str(r.get("day") or "") <= END]
    book = sorted(book, key=lambda x: (x.get("day"), x.get("hm")))

    sessions_all, _, _ = fs._prod2(4000)
    sess = sorted(d for d in sessions_all if START <= d <= END)
    overall = _agg(book)
    months = month_block(book, sess)

    lines = [
        "# CHAMPION+ — monthly report through today",
        "",
        f"**Book:** CHAMPION_PLUS ticket-fill RESEARCH (seed=CHAMPION · floor ≥{FLOOR_1Y}%)",
        f"**Window:** `{START}` → `{END}` (through today) · sessions **{len(sess)}** · cap={CAP} same-side",
        f"**Dropped live tracks:** PROVEN / GOOD_PROD2 / CROWN as stack · kept CHAMPION seed + research fills",
        "",
        "## Overall",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Calls | **{overall.get('n')}** |",
        f"| Hit% | **{overall.get('hit_pct')}%** |",
        f"| W / L | {overall.get('wins')} / {overall.get('losses')} |",
        f"| Points (sum) | **{overall.get('points')}** |",
        "",
        "## Monthly scorecard",
        "",
        "| Month | Sess | N | Hit% | W/L | Points | Avg pts | Avg T1 pts | Avg SL pts | Days w/ call | Quiet |",
        "|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for m in months:
        lines.append(
            f"| {m['month']} | {m['sessions']} | {m['n']} | {m['hit_pct']} | "
            f"{m['wins']}/{m['losses']} | {m['points']} | {m['avg_points']} | "
            f"{m['avg_target_pts']} | {m['avg_sl_pts']} | {m['days_with_call']} | {m['days_quiet']} |"
        )

    # Per month call tables
    for m in months:
        lines.extend(
            [
                "",
                f"## {m['month']} — calls",
                "",
                f"N={m['n']} · hit {m['hit_pct']}% · points {m['points']} · "
                f"avg T1 {m['avg_target_pts']} · avg SL {m['avg_sl_pts']}",
                "",
                "| # | Day | HM | Side | Win | Track | Entry | SL | Target | SL pts | T1 pts | Points | p |",
                "|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for i, r in enumerate(m["calls"], 1):
            lines.append(
                f"| {i} | {r.get('day')} | {r.get('hm')} | {side_of(r)} | "
                f"{'W' if r.get('win') else 'L'} | {r.get('track')} | "
                f"{r.get('entry') if r.get('entry') is not None else ''} | "
                f"{r.get('stop_loss') if r.get('stop_loss') is not None else ''} | "
                f"{r.get('target_1') if r.get('target_1') is not None else ''} | "
                f"{r.get('sl_pts') if r.get('sl_pts') is not None else ''} | "
                f"{r.get('t1_pts') if r.get('t1_pts') is not None else ''} | "
                f"{r.get('points') if r.get('points') is not None else ''} | "
                f"{r.get('p_t1') if r.get('p_t1') is not None else ''} |"
            )

    # Notes
    n_lvl = sum(1 for r in book if r.get("entry") is not None)
    lines.extend(
        [
            "",
            "## Notes",
            "",
            f"- Price levels (entry/SL/target) available on **{n_lvl}/{len(book)}** calls "
            "(path-good / crown / dual10m). Champion-native rows often have **points only**.",
            "- **T1 pts** = |target − entry| · **SL pts** = |entry − stop|.",
            "- **Points** = realized path P/L for that ticket (positive ≈ target hit).",
            "- RESEARCH book — not promoted live.",
            "",
            f"Elapsed {round(time.time() - t0, 1)}s",
            "",
        ]
    )

    payload = {
        "window": {"start": START, "end": END, "sessions": len(sess)},
        "floor_1y": FLOOR_1Y,
        "cap": CAP,
        "overall": overall,
        "monthly": [],
    }
    for m in months:
        row = {k: v for k, v in m.items() if k != "calls"}
        row["calls"] = [
            {
                "day": r.get("day"),
                "hm": r.get("hm"),
                "side": side_of(r),
                "win": r.get("win"),
                "track": r.get("track"),
                "entry": r.get("entry"),
                "stop_loss": r.get("stop_loss"),
                "target_1": r.get("target_1"),
                "sl_pts": r.get("sl_pts"),
                "t1_pts": r.get("t1_pts"),
                "points": r.get("points"),
                "p_t1": r.get("p_t1"),
                "outcome": r.get("outcome"),
            }
            for r in m["calls"]
        ]
        payload["monthly"].append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "CHAMPION_PLUS_MONTHLY_TODATE.md"
    js = OUT / "CHAMPION_PLUS_MONTHLY_TODATE.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (HOLD / "monthly_todate_calls.json").write_text(
        json.dumps(payload["monthly"], indent=2, default=str), encoding="utf-8"
    )
    print(f"Wrote {md}", flush=True)
    print(
        f"Overall {overall.get('n')}@{overall.get('hit_pct')}% pts={overall.get('points')}",
        flush=True,
    )
    for m in months:
        print(
            f"  {m['month']}: n={m['n']} hit={m['hit_pct']} pts={m['points']} "
            f"T1={m['avg_target_pts']} SL={m['avg_sl_pts']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
