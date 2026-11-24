"""Deep analysis: 15m model (prod2) ∩ 5m models for higher-accuracy calls.

15m = good_prod2 (fno_NIFTY.pkl issued_prod, max 2/day)
5m  = proven_100 / champion / crown_5m (live pool, path-scored)

Research only — does not wire live or change held stack.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import POOL, PRIORITY, _champ_floor, _agg, _union  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
MODEL_DIR = ROOT / "prod_live" / "models"

END = "2026-10-23"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")


def _hm_mins(hm: str) -> int:
    try:
        h, m = str(hm).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 12 * 60


def _load_channels(start: str, end: str) -> Dict[str, Any]:
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    sessions_all, prod2_all, _ = fs._prod2(1400)
    sess = sorted(d for d in sessions_all if start < d <= end)

    def clip(rows, track):
        out = []
        for r in rows:
            if not (start < r["day"] <= end):
                continue
            rr = dict(r, track=track, priority=PRIORITY.get(track, 9))
            out.append(rr)
        return out

    proven = clip(pool["proven_100"], "proven_100")
    champ_raw = clip(pool["champion"], "champion")
    champ = _champ_floor(champ_raw)
    for r in champ:
        r["track"] = "champion"
        r["priority"] = PRIORITY["champion"]
    crown = clip(pool["crown_5m"], "crown_5m")
    good = clip(prod2_all, "good_prod2")

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
        "stack": stack,
        "good": good,
        "proven": proven,
        "champ": champ,
        "champ_raw": champ_raw,
        "crown": crown,
        "crown_htf": crown_htf,
        "active": active,
    }


def _side_days(rows: List[dict]) -> Dict[str, Set[str]]:
    """day -> set of sides present."""
    d: Dict[str, Set[str]] = defaultdict(set)
    for r in rows:
        d[r["day"]].add(str(r.get("decision") or "").upper())
    return d


def _by_day_side(rows: List[dict]) -> Dict[Tuple[str, str], List[dict]]:
    g: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for r in rows:
        g[(r["day"], str(r.get("decision") or "").upper())].append(r)
    return g


def _first(rows: List[dict]) -> Optional[dict]:
    if not rows:
        return None
    return sorted(rows, key=lambda x: (_hm_mins(x.get("hm") or "99:99"), -float(x.get("p_t1") or 0)))[0]


def _best_p(rows: List[dict]) -> Optional[dict]:
    if not rows:
        return None
    return max(rows, key=lambda x: float(x.get("p_t1") or x.get("score") or 0))


def _near(a: dict, b: dict, tol_min: int) -> bool:
    return abs(_hm_mins(a.get("hm") or "12:00") - _hm_mins(b.get("hm") or "12:00")) <= tol_min


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
    cv = _cov(rows, sess)
    return {"name": name, "note": note, **st, **cv}


def build_books(ch: Dict[str, Any]) -> Dict[str, List[dict]]:
    sess = ch["sess"]
    good, proven, champ, crown, crown_htf = (
        ch["good"],
        ch["proven"],
        ch["champ"],
        ch["crown"],
        ch["crown_htf"],
    )
    books: Dict[str, List[dict]] = {}

    # baselines
    books["15m_prod2_alone"] = list(good)
    books["5m_proven_alone"] = list(proven)
    books["5m_champ_alone"] = list(champ)
    books["5m_crown_htf_alone"] = list(crown_htf)
    books["5m_crown_all_alone"] = list(crown)
    books["stack_held"] = list(ch["stack"])

    # 5m union (no 15m)
    books["5m_union_cap2"] = fs._union(
        {"proven_100": proven, "champion": champ, "crown_5m": crown_htf},
        day_cap=2,
    )

    good_ds = _side_days(good)
    proven_ds = _side_days(proven)
    champ_ds = _side_days(champ)
    crown_ds = _side_days(crown)
    crown_htf_ds = _side_days(crown_htf)

    good_ix = _by_day_side(good)
    proven_ix = _by_day_side(proven)
    champ_ix = _by_day_side(champ)
    crown_ix = _by_day_side(crown)
    crown_htf_ix = _by_day_side(crown_htf)

    any5_ds: Dict[str, Set[str]] = defaultdict(set)
    for ds in (proven_ds, champ_ds, crown_htf_ds):
        for day, sides in ds.items():
            any5_ds[day] |= sides

    any5_all_ds: Dict[str, Set[str]] = defaultdict(set)
    for ds in (proven_ds, champ_ds, crown_ds):
        for day, sides in ds.items():
            any5_all_ds[day] |= sides

    # --- A: 15m call kept only if 5m same side that day ---
    def filter_15m_by_5m(side_map: Dict[str, Set[str]], tag: str) -> List[dict]:
        out = []
        for r in good:
            side = str(r.get("decision") or "").upper()
            if side in side_map.get(r["day"], set()):
                out.append(dict(r, track=f"15m_if_{tag}", agree_with=tag))
        return out

    books["15m_if_any5_htf"] = filter_15m_by_5m(any5_ds, "any5_htf")
    books["15m_if_any5_all"] = filter_15m_by_5m(any5_all_ds, "any5_all")
    books["15m_if_proven"] = filter_15m_by_5m(proven_ds, "proven")
    books["15m_if_champ"] = filter_15m_by_5m(champ_ds, "champ")
    books["15m_if_crown_htf"] = filter_15m_by_5m(crown_htf_ds, "crown_htf")
    books["15m_if_crown_all"] = filter_15m_by_5m(crown_ds, "crown_all")

    # --- B: 5m call kept only if 15m same side that day ---
    def filter_5m_by_15m(rows: List[dict], tag: str) -> List[dict]:
        out = []
        for r in rows:
            side = str(r.get("decision") or "").upper()
            if side in good_ds.get(r["day"], set()):
                out.append(dict(r, track=f"{tag}_if_15m", agree_with="15m"))
        return out

    books["proven_if_15m"] = filter_5m_by_15m(proven, "proven")
    books["champ_if_15m"] = filter_5m_by_15m(champ, "champ")
    books["crown_htf_if_15m"] = filter_5m_by_15m(crown_htf, "crown_htf")
    books["crown_all_if_15m"] = filter_5m_by_15m(crown, "crown_all")
    books["5m_union_if_15m"] = filter_5m_by_15m(
        books["5m_union_cap2"], "5m_union"
    )

    # --- C: intersection day+side — emit ONE call (prefer 5m entry, else 15m) ---
    def intersect(five_ix, five_name: str, prefer: str = "5m") -> List[dict]:
        out = []
        for (day, side), grows in good_ix.items():
            frows = five_ix.get((day, side)) or []
            if not frows:
                continue
            g = _first(grows)
            f = _best_p(frows) if prefer == "5m" else _first(frows)
            if prefer == "5m":
                pick = dict(f, track=f"agree_{five_name}", agree_15m_hm=g.get("hm"), src="5m")
            else:
                pick = dict(g, track=f"agree_{five_name}_15mentry", agree_5m_hm=f.get("hm"), src="15m")
            # both must win for "strict"? No — report entry channel win
            out.append(pick)
        return out

    books["agree_proven_5mentry"] = intersect(proven_ix, "proven", "5m")
    books["agree_champ_5mentry"] = intersect(champ_ix, "champ", "5m")
    books["agree_crown_htf_5mentry"] = intersect(crown_htf_ix, "crown_htf", "5m")
    books["agree_crown_all_5mentry"] = intersect(crown_ix, "crown_all", "5m")
    books["agree_proven_15mentry"] = intersect(proven_ix, "proven", "15m")
    books["agree_champ_15mentry"] = intersect(champ_ix, "champ", "15m")
    books["agree_crown_htf_15mentry"] = intersect(crown_htf_ix, "crown_htf", "15m")

    # any 5m (htf crown)
    any5_ix: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for ix in (proven_ix, champ_ix, crown_htf_ix):
        for k, rs in ix.items():
            any5_ix[k].extend(rs)
    books["agree_any5_5mentry"] = intersect(any5_ix, "any5", "5m")
    books["agree_any5_15mentry"] = intersect(any5_ix, "any5", "15m")

    any5_all_ix: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for ix in (proven_ix, champ_ix, crown_ix):
        for k, rs in ix.items():
            any5_all_ix[k].extend(rs)
    books["agree_any5all_5mentry"] = intersect(any5_all_ix, "any5all", "5m")
    books["agree_any5all_15mentry"] = intersect(any5_all_ix, "any5all", "15m")

    # --- D: time-proximate agreement (±15 / ±30 / ±60 min) ---
    def time_agree(five_rows: List[dict], tol: int, tag: str) -> List[dict]:
        out = []
        five_ix_local = _by_day_side(five_rows)
        for (day, side), grows in good_ix.items():
            frows = five_ix_local.get((day, side)) or []
            if not frows:
                continue
            for g in grows:
                near = [f for f in frows if _near(g, f, tol)]
                if not near:
                    continue
                f = _best_p(near)
                out.append(
                    dict(
                        f,
                        track=f"time_agree_{tag}_{tol}m",
                        agree_15m_hm=g.get("hm"),
                        src="5m",
                    )
                )
                break  # one per day-side from first matching 15m
        # dedupe day-side
        seen = set()
        uniq = []
        for r in out:
            k = (r["day"], str(r.get("decision") or "").upper())
            if k in seen:
                continue
            seen.add(k)
            uniq.append(r)
        return uniq

    for tol in (15, 30, 60):
        books[f"time_any5_{tol}m"] = time_agree(
            proven + champ + crown_htf, tol, "any5"
        )
        books[f"time_crown_{tol}m"] = time_agree(crown_htf, tol, "crown")
        books[f"time_champ_{tol}m"] = time_agree(champ, tol, "champ")

    # --- E: both must win proxy — require dual confirmation AND take only if
    #     15m and 5m same side; keep stack-like priority among agrees ---
    books["agree_cap1_any5"] = _union(
        [
            dict(r, priority=0)
            for r in books["agree_proven_5mentry"]
        ]
        + [dict(r, priority=1) for r in books["agree_champ_5mentry"]]
        + [dict(r, priority=2) for r in books["agree_crown_htf_5mentry"]],
        day_cap=1,
    )
    books["agree_cap2_any5"] = _union(
        [
            dict(r, priority=0)
            for r in books["agree_proven_5mentry"]
        ]
        + [dict(r, priority=1) for r in books["agree_champ_5mentry"]]
        + [dict(r, priority=2) for r in books["agree_crown_htf_5mentry"]],
        day_cap=2,
    )

    # --- F: stack filtered — stack call only if 15m∩5m agree that side OR proven ---
    #     (keep proven always; filter good/champ/crown needing cross-TF)
    def stack_cross_filter(mode: str) -> List[dict]:
        out = []
        by_day: Dict[str, List[dict]] = defaultdict(list)
        for r in ch["stack"]:
            by_day[r["day"]].append(r)
        for day, rs in by_day.items():
            kept = []
            for r in sorted(rs, key=lambda x: (x.get("priority", 9), x.get("hm") or "")):
                tr = r.get("track")
                side = str(r.get("decision") or "").upper()
                if tr == "proven_100":
                    kept.append(r)
                    continue
                if mode == "need_15m":
                    # 5m tracks need 15m same side; good needs any5
                    if tr == "good_prod2":
                        if side in any5_ds.get(day, set()):
                            kept.append(dict(r, track="stack_good_x5"))
                    else:
                        if side in good_ds.get(day, set()):
                            kept.append(dict(r, track=f"stack_{tr}_x15"))
                elif mode == "need_both_nonproven":
                    # non-proven must have both TFs on side
                    if side in good_ds.get(day, set()) and side in any5_ds.get(day, set()):
                        kept.append(dict(r, track=f"stack_both_{tr}"))
            out.extend(kept[:2])
        return out

    books["stack_xTF_need_15m"] = stack_cross_filter("need_15m")
    books["stack_xTF_both_nonproven"] = stack_cross_filter("need_both_nonproven")

    # --- G: empty-day only — 15m∩5m soft on days stack silent ---
    stack_days = {r["day"] for r in ch["stack"]}
    empty = [d for d in sess if d not in stack_days]

    def empty_agree(five_ix, tag: str) -> List[dict]:
        out = []
        for day in empty:
            for side in ("BUY", "SELL"):
                grows = good_ix.get((day, side)) or []
                frows = five_ix.get((day, side)) or []
                if grows and frows:
                    f = _best_p(frows)
                    out.append(dict(f, track=f"empty_agree_{tag}", src="5m"))
                    break
        return out

    books["empty_agree_any5"] = empty_agree(any5_ix, "any5")
    books["empty_agree_crown"] = empty_agree(crown_ix, "crown")
    # stack + empty agree fill
    books["stack_plus_empty_agree_any5"] = list(ch["stack"]) + books["empty_agree_any5"]
    books["stack_plus_empty_agree_crown"] = list(ch["stack"]) + books["empty_agree_crown"]

    # 15m alone on empty (no 5m) — control
    books["empty_15m_only"] = [
        dict(r, track="empty_15m")
        for r in good
        if r["day"] in set(empty)
    ]
    # first per day
    by_e: Dict[str, List[dict]] = defaultdict(list)
    for r in books["empty_15m_only"]:
        by_e[r["day"]].append(r)
    books["empty_15m_only"] = [_first(rs) for rs in by_e.values() if _first(rs)]

    books["stack_plus_empty_15m"] = list(ch["stack"]) + books["empty_15m_only"]

    return books


def eval_window(label: str, start: str, end: str) -> Dict[str, Any]:
    print(f"window {label} {start}→{end}…", flush=True)
    ch = _load_channels(start, end)
    books = build_books(ch)
    scored = []
    for name, rows in books.items():
        # ensure win bool present
        cleaned = []
        for r in rows:
            if r is None:
                continue
            rr = dict(r)
            if "win" not in rr:
                # prod2 uses outcome sometimes
                o = rr.get("outcome")
                if o == "t1_before_sl":
                    rr["win"] = True
                elif o in ("sl_before_t1", "same_bar_both"):
                    rr["win"] = False
            cleaned.append(rr)
        scored.append(_pack(name, cleaned, ch["sess"]))
        st = scored[-1]
        if st["n"] and (st.get("hit_pct") or 0) >= 70:
            print(
                f"  {name}: n={st['n']} hit={st['hit_pct']}% "
                f"day={st['day_cov_pct']}% no={st['days_no_call']}",
                flush=True,
            )
    scored.sort(key=lambda r: (r.get("hit_pct") or 0, r.get("n") or 0), reverse=True)
    return {
        "label": label,
        "start": start,
        "end": end,
        "sessions": len(ch["sess"]),
        "baselines": {
            k: _pack(k, books[k], ch["sess"])
            for k in (
                "15m_prod2_alone",
                "5m_proven_alone",
                "5m_champ_alone",
                "5m_crown_htf_alone",
                "5m_union_cap2",
                "stack_held",
            )
        },
        "board": scored,
    }


def main() -> None:
    w1 = eval_window("1y", START_1Y, END)
    w3 = eval_window("3y", START_3Y, END)

    # cross-confirm: names that hit >=78 on 1y and >=75 on 3y with n>=20
    b1 = {r["name"]: r for r in w1["board"]}
    b3 = {r["name"]: r for r in w3["board"]}
    confirmed = []
    for name, r3 in b3.items():
        r1 = b1.get(name)
        if not r1:
            continue
        if (r3.get("n") or 0) < 20:
            continue
        if (r1.get("hit_pct") or 0) >= 78 and (r3.get("hit_pct") or 0) >= 75:
            confirmed.append(
                {
                    "name": name,
                    "hit_1y": r1["hit_pct"],
                    "n_1y": r1["n"],
                    "day_1y": r1["day_cov_pct"],
                    "hit_3y": r3["hit_pct"],
                    "n_3y": r3["n"],
                    "day_3y": r3["day_cov_pct"],
                    "no_call_3y": r3["days_no_call"],
                }
            )
    confirmed.sort(key=lambda r: (r["hit_3y"], r["n_3y"]), reverse=True)

    # best accuracy with usable coverage
    usable = [
        r
        for r in w3["board"]
        if (r.get("n") or 0) >= 30 and (r.get("day_cov_pct") or 0) >= 20
    ]
    best_acc = max(usable, key=lambda r: (r.get("hit_pct") or 0, r.get("n") or 0)) if usable else None
    best_bal = None
    for r in sorted(usable, key=lambda x: (x.get("hit_pct") or 0), reverse=True):
        if (r.get("hit_pct") or 0) >= 78 and (r.get("day_cov_pct") or 0) >= 35:
            best_bal = r
            break
    if best_bal is None:
        for r in sorted(usable, key=lambda x: (x.get("hit_pct") or 0), reverse=True):
            if (r.get("hit_pct") or 0) >= 76 and (r.get("day_cov_pct") or 0) >= 40:
                best_bal = r
                break

    stack3 = w3["baselines"]["stack_held"]
    prod3 = w3["baselines"]["15m_prod2_alone"]

    payload = {
        "goal": "Combine 15m prod2 + 5m models for higher accuracy",
        "models": {
            "15m": "good_prod2 / fno_NIFTY.pkl issued_prod max2",
            "5m": "proven_100, champion (floored), crown_5m (+ HTF gate variants)",
        },
        "window_1y": w1,
        "window_3y": {
            "label": w3["label"],
            "start": w3["start"],
            "end": w3["end"],
            "sessions": w3["sessions"],
            "baselines": w3["baselines"],
            "board": w3["board"],
        },
        "both_year_agree_hit": confirmed,
        "best_acc_3y_n30_day20": best_acc,
        "best_bal_3y": best_bal,
        "verdict": (
            "Agreement filters raise hit vs 15m alone; compare to held stack (~76%). "
            "Strict 15m∩5m is the accuracy lever; coverage falls. "
            "Empty-day 15m∩5m is thin because quiet days lack both signals."
        ),
    }
    # shrink 1y board in payload size — keep full in md
    payload["window_1y"] = {
        "label": w1["label"],
        "sessions": w1["sessions"],
        "baselines": w1["baselines"],
        "board_top": w1["board"][:25],
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    (MODEL_DIR / "dual_tf_15m_5m_agree.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# 15m × 5m model agreement — deep analysis",
        "",
        "**15m:** `good_prod2` (`fno_NIFTY.pkl`, issued_prod, max 2/day)  ",
        "**5m:** `proven_100` · `champion` · `crown_5m` (live pool, path-scored)",
        "",
        "Research only. Held stack unchanged.",
        "",
        "## Baselines (3y)",
        "",
        "| Book | N | Hit | Day cov | No-call |",
        "|---|---:|---:|---:|---:|",
    ]
    for k, r in w3["baselines"].items():
        lines.append(
            f"| `{k}` | {r['n']} | **{r['hit_pct']}%** | {r['day_cov_pct']}% | {r['days_no_call']} |"
        )

    lines += [
        "",
        "## 3y board (hit-ranked, n≥12)",
        "",
        "| Approach | N | Hit | Day cov | No-call |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in w3["board"]:
        if (r.get("n") or 0) < 12:
            continue
        lines.append(
            f"| `{r['name']}` | {r['n']} | **{r['hit_pct']}%** | {r['day_cov_pct']}% | {r['days_no_call']} |"
        )

    lines += ["", "## Both-year agree (1y≥78% & 3y≥75%, n≥20)", ""]
    if not confirmed:
        lines.append("_None cleared both-year bar._")
    else:
        lines += [
            "| Approach | 1y hit / n / day | 3y hit / n / day |",
            "|---|---|---|",
        ]
        for r in confirmed:
            lines.append(
                f"| `{r['name']}` | {r['hit_1y']}% / {r['n_1y']} / {r['day_1y']}% | "
                f"**{r['hit_3y']}%** / {r['n_3y']} / {r['day_3y']}% |"
            )

    def blk(title, r):
        lines.append(f"## {title}")
        lines.append("")
        if not r:
            lines.append("_none_")
        else:
            lines.append(
                f"- `{r['name']}`: **{r['hit_pct']}%** n={r['n']} · "
                f"day {r['day_cov_pct']}% · no-call {r['days_no_call']}"
            )
            lines.append(
                f"- vs stack **{stack3['hit_pct']}%** · vs 15m alone **{prod3['hit_pct']}%**"
            )
        lines.append("")

    blk("Best accuracy (3y, n≥30, day≥20%)", best_acc)
    blk("Best balance (prefer hit≥78 & day≥35%)", best_bal)

    lines += [
        "## How to read",
        "",
        "- `15m_if_*` = take 15m call only when that 5m channel has same side that day",
        "- `*_if_15m` = take 5m call only when 15m has same side",
        "- `agree_*` = day+side intersection; entry from 5m or 15m",
        "- `time_*` = same side and clocks within ±N minutes",
        "- `stack_xTF_*` = filter held stack with cross-TF rules",
        "- `empty_agree_*` = fill stack-silent days only when both TFs agree",
        "",
        "## Verdict",
        "",
        payload["verdict"],
        "",
        "Not wired. Stack stays `HELD_FOR_FINAL`.",
        "",
    ]
    (OUT / "DUAL_TF_15M_5M.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", OUT / "DUAL_TF_15M_5M.md")
    print(
        json.dumps(
            {
                "confirmed_n": len(confirmed),
                "best_acc": (best_acc or {}).get("name"),
                "best_bal": (best_bal or {}).get("name"),
                "stack_3y": stack3.get("hit_pct"),
                "top3_3y": [
                    {"name": r["name"], "hit": r["hit_pct"], "n": r["n"], "day": r["day_cov_pct"]}
                    for r in w3["board"][:3]
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
