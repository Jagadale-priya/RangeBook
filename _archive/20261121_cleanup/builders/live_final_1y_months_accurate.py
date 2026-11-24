"""Live held final desk · 1y monthly — same stack as live sessions + accurate tag.

Book: STACK_PLUS_CROWN_HTF_CAP2 (live path: proven > good > champ > crown_htf, cap2)
Stamp: accurate_tag = AGREE_15M_ANY5 when issued 15m ∩ this 5m entry (day+side)
Also lists rare agree extras not already in stack (STACK_PLUS_AGREE_15M_ANY5 desk).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import dual_tf_15m_5m_agree as d  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import POOL, PRIORITY, _champ_floor, _agg  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
MODEL_DIR = ROOT / "prod_live" / "models"

# Match Part D confirmation window in GATED_BOTH.md
END = "2026-10-23"
START = "2025-10-24"


def _clean(rows: List[dict]) -> List[dict]:
    out = []
    for r in rows:
        if r is None:
            continue
        rr = dict(r)
        if "win" not in rr:
            o = rr.get("outcome")
            if o == "t1_before_sl":
                rr["win"] = True
            elif o in ("sl_before_t1", "same_bar_both"):
                rr["win"] = False
        out.append(rr)
    return out


def _key(r: dict) -> Tuple[str, str, str]:
    return (r["day"], str(r.get("decision") or "").upper(), str(r.get("hm") or ""))


def _side_key(r: dict) -> Tuple[str, str]:
    return (r["day"], str(r.get("decision") or "").upper())


def _build_live_stack(start: str, end: str):
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    sessions_all, prod2_all, _ = fs._prod2(1400)
    sess = sorted(d for d in sessions_all if start <= d <= end)

    proven = [
        dict(r, track="proven_100", priority=PRIORITY["proven_100"])
        for r in pool["proven_100"]
        if start <= r["day"] <= end
    ]
    champ = _champ_floor([r for r in pool["champion"] if start <= r["day"] <= end])
    for r in champ:
        r["track"] = "champion"
        r["priority"] = PRIORITY["champion"]
    crown = [
        dict(r, track="crown_5m", priority=PRIORITY["crown_5m"])
        for r in pool["crown_5m"]
        if start <= r["day"] <= end
    ]
    good = [
        dict(r, track="good_prod2", priority=PRIORITY["good_prod2"])
        for r in prod2_all
        if start <= r["day"] <= end
    ]
    daily = fs._load_daily()
    active = fs._active_days(sess, daily)
    crown_htf = [r for r in crown if r["day"] in active]
    stack = fs._union(
        {
            "proven_100": proven,
            "good_prod2": good,
            "champion": champ,
            "crown_5m": crown_htf,
        },
        day_cap=2,
    )
    return {
        "sess": sess,
        "stack": _clean(stack),
        "proven": proven,
        "champ": champ,
        "crown_htf": crown_htf,
        "good": _clean(good),
        "active": active,
    }


def _stamp(stack: List[dict], agree_exact: Set[Tuple[str, str, str]]):
    """Stamp accurate_tag only on exact Part G agree entries (5m best-p on day+side)."""
    out = []
    for r in stack:
        rr = dict(r)
        accurate = _key(rr) in agree_exact
        rr["accurate"] = accurate
        rr["accurate_tag"] = "AGREE_15M_ANY5" if accurate else None
        out.append(rr)
    return out


def _month_block(rows: List[dict], sess: List[str]) -> List[dict]:
    by_m_days: Dict[str, List[str]] = defaultdict(list)
    for day in sess:
        by_m_days[day[:7]].append(day)
    by_m_rows: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by_m_rows[r["day"][:7]].append(r)

    months = []
    for ym in sorted(by_m_days):
        days = by_m_days[ym]
        ds = set(days)
        sub = by_m_rows.get(ym, [])
        acc = [r for r in sub if r.get("accurate")]
        rest = [r for r in sub if not r.get("accurate")]
        cdays = {r["day"] for r in sub}
        tracks = defaultdict(lambda: {"n": 0, "w": 0, "pts": 0.0, "acc_n": 0, "acc_w": 0})
        for r in sub:
            tr = r.get("track") or "?"
            tracks[tr]["n"] += 1
            tracks[tr]["w"] += int(bool(r.get("win")))
            tracks[tr]["pts"] += float(r.get("points") or 0)
            if r.get("accurate"):
                tracks[tr]["acc_n"] += 1
                tracks[tr]["acc_w"] += int(bool(r.get("win")))
        track_out = {}
        for k, v in sorted(tracks.items()):
            track_out[k] = {
                "n": v["n"],
                "hit_pct": round(100.0 * v["w"] / v["n"], 1) if v["n"] else None,
                "points": round(v["pts"], 1),
                "accurate_n": v["acc_n"],
                "accurate_hit_pct": round(100.0 * v["acc_w"] / v["acc_n"], 1) if v["acc_n"] else None,
            }
        sa, sr = _agg(acc), _agg(rest)
        st = _agg(sub)
        months.append(
            {
                "month": ym,
                "sessions": len(days),
                "n": st["n"],
                "hit_pct": st["hit_pct"],
                "wins": st["wins"],
                "losses": st["losses"],
                "points": st["points"],
                "days_with_call": len(cdays),
                "days_no_call": len(ds - cdays),
                "accurate_n": sa["n"],
                "accurate_hit_pct": sa["hit_pct"],
                "accurate_wins": sa["wins"],
                "accurate_losses": sa["losses"],
                "accurate_points": sa["points"],
                "other_n": sr["n"],
                "other_hit_pct": sr["hit_pct"],
                "by_track": track_out,
                "calls": [
                    {
                        "day": r["day"],
                        "hm": r.get("hm"),
                        "decision": r.get("decision"),
                        "track": r.get("track"),
                        "win": r.get("win"),
                        "points": r.get("points"),
                        "p_t1": r.get("p_t1"),
                        "accurate": r.get("accurate"),
                        "accurate_tag": r.get("accurate_tag"),
                    }
                    for r in sorted(sub, key=lambda x: (x["day"], x.get("hm") or ""))
                ],
            }
        )
    return months


def main() -> None:
    print(f"live final 1y {START} → {END}", flush=True)
    live = _build_live_stack(START, END)
    sess, stack = live["sess"], live["stack"]

    # Agree universe (same as Part G)
    five = live["proven"] + live["champ"] + live["crown_htf"]
    # Exact agree 5m entries (best p per day+side among 5m that agree)
    books = d.build_books(
        {
            "sess": sess,
            "stack": stack,
            "good": live["good"],
            "proven": live["proven"],
            "champ": live["champ"],
            "champ_raw": live["champ"],
            "crown": live["crown_htf"],
            "crown_htf": live["crown_htf"],
            "active": live["active"],
        }
    )
    agree_rows = _clean(books["agree_any5_5mentry"])
    agree_exact = {_key(r) for r in agree_rows}

    stamped = _stamp(stack, agree_exact)

    # Desk additive: stack + agree not already exact-duped
    seen = {_key(r) for r in stamped}
    extras = []
    for r in agree_rows:
        if _key(r) in seen:
            continue
        rr = dict(r)
        rr["track"] = "agree_15m_any5"
        rr["accurate"] = True
        rr["accurate_tag"] = "AGREE_15M_ANY5"
        rr["book"] = "agree_extra"
        extras.append(rr)
    desk = stamped + extras

    months_live = _month_block(stamped, sess)
    months_desk = _month_block(desk, sess)

    a_live = _agg(stamped)
    a_acc = _agg([r for r in stamped if r.get("accurate")])
    a_oth = _agg([r for r in stamped if not r.get("accurate")])
    a_desk = _agg(desk)

    def cov(rows):
        return round(100.0 * len({r["day"] for r in rows}) / len(sess), 1) if sess else 0

    payload = {
        "tag_live": "STACK_PLUS_CROWN_HTF_CAP2",
        "accurate_tag": "AGREE_15M_ANY5",
        "desk_tag": "STACK_PLUS_AGREE_15M_ANY5",
        "window": {"start": START, "end": END, "sessions": len(sess)},
        "live_stack": {
            **a_live,
            "day_cov_pct": cov(stamped),
            "days_no_call": len(sess) - len({r["day"] for r in stamped}),
        },
        "accurate_on_stack": {**a_acc, "day_cov_pct": cov([r for r in stamped if r.get("accurate")])},
        "other_on_stack": {**a_oth},
        "desk_combo": {
            **a_desk,
            "day_cov_pct": cov(desk),
            "agree_extras": len(extras),
        },
        "monthly_live": months_live,
        "monthly_desk": months_desk,
        "agree_extras_calls": extras,
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    (MODEL_DIR / "live_final_1y_months_accurate.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Live final hold · 1y monthly + accurate tag",
        "",
        f"**Live book:** `STACK_PLUS_CROWN_HTF_CAP2` (same as live sessions: proven > good > champ > crown_htf, day cap 2, same-side)  ",
        f"**Accurate tag:** `AGREE_15M_ANY5` when issued 15m ∩ 5m (proven/champ/crown_htf) same day+side, and this row is the 5m entry  ",
        f"**Window:** `{START}` → `{END}` · **{len(sess)}** sessions",
        "",
        "## Totals (live stack)",
        "",
        "| Slice | N | Hit | W/L | Points | Day cov |",
        "|---|---:|---:|---:|---:|---:|",
        f"| **All live stack calls** | **{a_live['n']}** | **{a_live['hit_pct']}%** | "
        f"{a_live['wins']}/{a_live['losses']} | {a_live['points']} | {cov(stamped)}% |",
        f"| With `accurate_tag=AGREE_15M_ANY5` | {a_acc['n']} | **{a_acc['hit_pct']}%** | "
        f"{a_acc['wins']}/{a_acc['losses']} | {a_acc['points']} | {cov([r for r in stamped if r.get('accurate')])}% |",
        f"| Without accurate tag | {a_oth['n']} | {a_oth['hit_pct']}% | "
        f"{a_oth['wins']}/{a_oth['losses']} | {a_oth['points']} | — |",
        f"| Desk + agree extras (`STACK_PLUS_AGREE_15M_ANY5`) | {a_desk['n']} | {a_desk['hit_pct']}% | "
        f"{a_desk['wins']}/{a_desk['losses']} | {a_desk['points']} | {cov(desk)}% "
        f"(+{len(extras)} extra) |",
        "",
        "## Live stack — per month",
        "",
        "| Month | Sess | Calls | Hit | W/L | Pts | Acc N | Acc Hit | Acc W/L | Other N | Other Hit | Days w/ call | No call |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in months_live:
        hit = "—" if m["hit_pct"] is None else f"**{m['hit_pct']}%**"
        ah = "—" if m["accurate_hit_pct"] is None else f"**{m['accurate_hit_pct']}%**"
        oh = "—" if m["other_hit_pct"] is None else f"{m['other_hit_pct']}%"
        awl = f"{m['accurate_wins']}/{m['accurate_losses']}" if m["accurate_n"] else "—"
        lines.append(
            f"| {m['month']} | {m['sessions']} | {m['n']} | {hit} | {m['wins']}/{m['losses']} | "
            f"{m['points']} | {m['accurate_n']} | {ah} | {awl} | {m['other_n']} | {oh} | "
            f"{m['days_with_call']} | **{m['days_no_call']}** |"
        )

    lines += [
        "",
        "## Track mix (live stack, 1y)",
        "",
        "| Track | N | Hit | Accurate N | Accurate hit |",
        "|---|---:|---:|---:|---:|",
    ]
    # aggregate tracks
    tr_all: Dict[str, Dict[str, int]] = defaultdict(lambda: {"n": 0, "w": 0, "an": 0, "aw": 0})
    for r in stamped:
        tr = str(r.get("track") or "?")
        tr_all[tr]["n"] += 1
        tr_all[tr]["w"] += int(bool(r.get("win")))
        if r.get("accurate"):
            tr_all[tr]["an"] += 1
            tr_all[tr]["aw"] += int(bool(r.get("win")))
    for k, v in sorted(tr_all.items()):
        hit = round(100.0 * v["w"] / v["n"], 2) if v["n"] else None
        ah = round(100.0 * v["aw"] / v["an"], 2) if v["an"] else None
        lines.append(f"| `{k}` | {v['n']} | **{hit}%** | {v['an']} | {ah if ah is not None else '—'}% |")

    lines += ["", "## Calls by month (live stack)", ""]
    for m in months_live:
        lines.append(f"### {m['month']}")
        lines.append("")
        if not m["calls"]:
            lines.append("_No calls this month._")
            lines.append("")
            continue
        lines.append("| Day | HM | Side | Track | Win | Pts | Accurate tag |")
        lines.append("|---|---|---|---|---|---:|---|")
        for c in m["calls"]:
            tag = f"`{c['accurate_tag']}`" if c.get("accurate_tag") else "—"
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['decision']} | `{c['track']}` | "
                f"{'W' if c['win'] else 'L'} | {c['points']} | {tag} |"
            )
        lines.append("")

    if extras:
        lines += [
            "## Agree extras (not already in live stack cap2)",
            "",
            "| Day | HM | Side | Win | Pts | Tag |",
            "|---|---|---|---|---:|---|",
        ]
        for c in extras:
            lines.append(
                f"| {c['day']} | {c.get('hm')} | {c.get('decision')} | "
                f"{'W' if c.get('win') else 'L'} | {c.get('points')} | `{c.get('accurate_tag')}` |"
            )
        lines.append("")

    lines += [
        "## Notes",
        "",
        "- Scoring = same live pool / prod2 path as prior stack proves (`live_session_close`).",
        "- NSE mid gate OFF (matches live `.env`).",
        "- Accurate tag = exact Part G entry (best-p 5m on day+side with issued 15m).",
        "",
    ]
    path = OUT / "LIVE_FINAL_1Y_MONTHS_ACCURATE.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "sessions": len(sess),
                "live_n": a_live["n"],
                "live_hit": a_live["hit_pct"],
                "accurate_n": a_acc["n"],
                "accurate_hit": a_acc["hit_pct"],
                "other_hit": a_oth["hit_pct"],
                "extras": len(extras),
                "wrote": str(path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
