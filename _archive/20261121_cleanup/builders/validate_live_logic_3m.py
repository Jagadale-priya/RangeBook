"""Fast 3m validate of FINAL live 3-books vs golden + report counts/accuracy.

Same rebuild code as live (P2F / P2G / CHAMP held∪engine day seed).
Skips per-candle annotate (that hung overnight) — validates books + combine.

  python -u prod_live/tests/builders/validate_live_logic_3m.py
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "prod_live"))
import path_setup  # noqa: F401,E402

from accuracy_max_6m import _champ_floor  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    gap_map,
    union_unique_days,
)
from research_confirm_dual_tf_deep import _clip, _side  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
from prod_live.logic.accurate_desks import build_all_accurate_desks  # noqa: E402
from prod_live.logic.combined_live_book import call_key, combine_live_rows  # noqa: E402
from prod_live.logic import champ_plus_engine as eng  # noqa: E402
from prod_live.logic.champ_plus_live import (  # noqa: E402
    ACCURACY_TAG as CHAMP_ACC,
    DESK as CHAMP_DESK,
    ensure_session_calls,
    load_held_calls,
    stamp_live,
)
from prod_live.logic.p2f_day_live import (  # noqa: E402
    EXPECTED_1Y as P2F_DAY_EXP,
    LIVE_DAY_DESKS,
    WINDOW_1Y as P2F_1Y,
    build_p2f_day_desks,
    load_phase2f_day_recipes,
)
from prod_live.logic.p2f_cap2_live import (  # noqa: E402
    EXPECTED_1Y as P2F_CAP2_EXP,
    LIVE_CAP2_DESKS,
    build_p2f_cap2_desks,
    load_phase2f_cap2_recipes,
)
from prod_live.logic.p2g_10m import (  # noqa: E402
    BASE_KEY_BY_DESK,
    HARD_GATES,
    WINDOW_5Y,
)
from prod_live.logic.p2g_10m_live import (  # noqa: E402
    LIVE_P2G_DESKS,
    load_phase2g_recipes,
    stamp_live as stamp_p2g,
)
from research_acc_phase2g_10m_1y import desk_ok, load_d10, mine_streams, universes_p2g  # noqa: E402
from prod_live.holding_accurate.rebuild_streams import rebuild_all_tags  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "LIVE_LOGIC_3M_BAR_REPLAY.md"
OUT_JSON = OUT / "LIVE_LOGIC_3M_BAR_REPLAY.json"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"
LEDGER_BAK = eng._HOLD / "live_session_calls.json.bak_3m_replay"

END = "2026-11-15"
START = (pd.Timestamp(END) - timedelta(days=92)).strftime("%Y-%m-%d")


def clip_incl(rows: List[dict], a: str, b: str) -> List[dict]:
    return [r for r in rows if a <= str(r.get("day") or "") <= b]


def hit(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    known = [r for r in rows if r.get("win") is not None]
    if not known:
        return 0.0
    return round(100.0 * sum(1 for r in known if r.get("win")) / len(known), 2)


def rebuild_held_p2g(seed, tags, by_tag, floor):
    cur = list(seed)
    if not desk_ok(cur, floor):
        cur = []
    for tag in tags:
        rows = by_tag.get(tag)
        if rows:
            cur = union_unique_days(cur, rows)
    return cur


def main() -> int:
    t0 = time.time()
    print(f"LIVE 3m validate {START} → {END}", flush=True)

    if eng._LIVE_LEDGER.exists():
        shutil.copy2(eng._LIVE_LEDGER, LEDGER_BAK)
    eng.save_live_ledger([])

    print("  load caches…", flush=True)
    dual = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(5000)
    sess_1y = [d for d in sessions_all if P2F_1Y["start"] < d <= P2F_1Y["end"]]
    active_1y = fs._active_days(sess_1y, fs._load_daily()) if sess_1y else set()
    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ_rows = _champ_floor(
        [dict(r, track="champion") for r in dual["dual15"]["champion"]]
    )
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]
    champ_native = path_u.get("champ_native") or champ_rows

    # ---- P2F ----
    print("  P2F rebuild…", flush=True)
    phase1_1y = build_all_accurate_desks(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=path_u.get("crown_by_risk") or {},
        good_by_risk=path_u.get("good_by_risk") or {},
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active_1y,
    )
    recipes_f = load_phase2f_day_recipes()
    recipes_c = load_phase2f_cap2_recipes()
    all_tags: List[str] = []
    seen = set()
    for desk in list(LIVE_DAY_DESKS) + list(LIVE_CAP2_DESKS):
        meta = recipes_f.get(desk) or recipes_c.get(desk) or {}
        for t in meta.get("stream_tags_research") or []:
            if t not in seen:
                seen.add(t)
                all_tags.append(t)
    by_tag = rebuild_all_tags(
        all_tags, path_u, gaps, active_1y, dual15, dual5, proven, champ_rows
    )
    p2f_day_full = build_p2f_day_desks(phase1_1y, by_tag)
    p2f_cap2_full = build_p2f_cap2_desks(phase1_1y, by_tag)
    p2f_day = {d: clip_incl(p2f_day_full.get(d) or [], START, END) for d in LIVE_DAY_DESKS}
    p2f_cap2 = {
        d: clip_incl(p2f_cap2_full.get(d) or [], START, END) for d in LIVE_CAP2_DESKS
    }

    # ---- P2G ----
    print("  P2G rebuild…", flush=True)
    sess_5y = [d for d in sessions_all if WINDOW_5Y["start"] < d <= WINDOW_5Y["end"]]
    active_5y = fs._active_days(sess_5y, fs._load_daily()) if sess_5y else set()
    phase1_5y = build_all_accurate_desks(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=path_u.get("crown_by_risk") or {},
        good_by_risk=path_u.get("good_by_risk") or {},
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active_5y,
    )
    d10 = load_d10()
    univ = universes_p2g(path_u, d10, champ_native)
    streams_all = mine_streams(univ, gaps, active_5y, floor_min=82.71)
    by_tag_g = {t: rows for t, rows in streams_all}
    recipes_g = load_phase2g_recipes()
    p2g: Dict[str, List[dict]] = {}
    for desk in LIVE_P2G_DESKS:
        floor = HARD_GATES[desk]
        meta = recipes_g.get(desk) or {}
        tags = list(meta.get("stream_tags_research") or [])
        seed = list(phase1_5y.get(BASE_KEY_BY_DESK[desk]) or [])
        rows = stamp_p2g(rebuild_held_p2g(seed, tags, by_tag_g, floor), desk)
        p2g[desk] = clip_incl(rows, START, END)

    # ---- CHAMP: day-open seed only (same ensure_session_calls as live open) ----
    print("  CHAMP day-open seed…", flush=True)
    days = sorted(
        {
            d
            for d in sessions_all
            if START <= d <= END
        }
    )
    # also include any day present in held book in window
    for r in load_held_calls():
        d = str(r.get("day") or "")
        if START <= d <= END:
            days.append(d)
    days = sorted(set(days))
    for i, day in enumerate(days):
        ensure_session_calls(day)
        if (i + 1) % 20 == 0:
            print(f"    seeded {i+1}/{len(days)}", flush=True)

    champ_held_3m = clip_incl(load_held_calls(), START, END)
    champ_live_raw = eng.load_full_book_raw()
    champ_full_3m = stamp_live(clip_incl(champ_live_raw, START, END))

    combined = combine_live_rows(
        p2f_day=p2f_day,
        p2f_cap2=p2f_cap2,
        p2g_10m=p2g,
        champ_plus=champ_full_3m,
    )
    blocked = int(combined.get("blocked_distinct") or 0)

    checks: List[Dict[str, Any]] = []

    def add_check(name: str, ok: bool, detail: str):
        checks.append({"name": name, "ok": ok, "detail": detail})
        print(f"  {'PASS' if ok else 'FAIL'} {name}: {detail}", flush=True)

    add_check("blocked_distinct_0", blocked == 0, f"blocked={blocked}")
    raw_keys = {call_key(r) for r in combined["raw_rows"] if all(call_key(r))}
    ui_keys = {call_key(r) for r in combined["ui_rows"]}
    add_check(
        "no_missing_ui_keys",
        len(raw_keys - ui_keys) == 0,
        f"missing={len(raw_keys - ui_keys)} ui={len(ui_keys)} raw_keys={len(raw_keys)}",
    )

    held_keys = {call_key(r) for r in champ_held_3m if all(call_key(r))}
    full_keys = {call_key(r) for r in champ_full_3m if all(call_key(r))}
    add_check(
        "champ_held_preserved",
        held_keys <= full_keys,
        f"held_3m={len(held_keys)} full_3m={len(full_keys)} missing={len(held_keys-full_keys)}",
    )

    bad_lvl = 0
    for r in champ_full_3m:
        try:
            e = float(r.get("entry"))
            side = _side(r)
            sl = float(r.get("stop_loss"))
            t1 = float(r.get("target_1"))
            if side == "BUY":
                if abs((t1 - e) - 30) > 0.05 or abs((e - sl) - 30) > 0.05:
                    bad_lvl += 1
            elif side == "SELL":
                if abs((e - t1) - 30) > 0.05 or abs((sl - e) - 30) > 0.05:
                    bad_lvl += 1
        except Exception:
            bad_lvl += 1
    add_check("champ_brackets_t30_sl30", bad_lvl == 0, f"bad_levels={bad_lvl}")

    bad_tag = sum(
        1
        for r in champ_full_3m
        if r.get("accurate_tag") != CHAMP_DESK or r.get("accuracy_tag") != CHAMP_ACC
    )
    add_check("champ_tags", bad_tag == 0, f"bad_tag={bad_tag}")

    p2f_ok = True
    p2f_details = []
    for desk in LIVE_DAY_DESKS:
        rs = _clip(p2f_day_full.get(desk) or [], P2F_1Y["start"], P2F_1Y["end"])
        exp = P2F_DAY_EXP[desk]
        ok = len(rs) == int(exp["n"]) and abs(hit(rs) - float(exp["hit_pct"])) <= 0.05
        p2f_ok = p2f_ok and ok
        p2f_details.append(f"{desk}:{len(rs)}@{hit(rs)}(exp {exp['n']}@{exp['hit_pct']})")
    add_check("p2f_day_1y_golden", p2f_ok, "; ".join(p2f_details))

    p2f_c_ok = True
    p2f_c_details = []
    for desk in LIVE_CAP2_DESKS:
        rs = _clip(p2f_cap2_full.get(desk) or [], P2F_1Y["start"], P2F_1Y["end"])
        exp = P2F_CAP2_EXP[desk]
        ok = len(rs) == int(exp["n"]) and abs(hit(rs) - float(exp["hit_pct"])) <= 0.05
        p2f_c_ok = p2f_c_ok and ok
        p2f_c_details.append(f"{desk}:{len(rs)}@{hit(rs)}(exp {exp['n']}@{exp['hit_pct']})")
    add_check("p2f_cap2_1y_golden", p2f_c_ok, "; ".join(p2f_c_details))

    good30 = (path_u.get("good_by_risk") or {}).get("30.0") or (
        path_u.get("good_by_risk") or {}
    ).get("30") or []
    risk_ok = bool(good30)
    add_check(
        "p2f_research_risk_30",
        risk_ok,
        f"good_by_risk[30] n={len(good30)} · Target +30 / SL −30",
    )

    # month rollup for combined UI
    by_month: Dict[str, List[dict]] = {}
    for r in combined["ui_rows"]:
        m = str(r.get("day") or "")[:7]
        by_month.setdefault(m, []).append(r)

    stats = {
        "window": {"start": START, "end": END},
        "mode": "day_open_seed_validate",
        "days_seeded": len(days),
        "champ_held_3m": {"n": len(champ_held_3m), "hit_pct": hit(champ_held_3m)},
        "champ_full_3m": {"n": len(champ_full_3m), "hit_pct": hit(champ_full_3m)},
        "combine": {
            "n_raw": combined["n_raw"],
            "n_ui": combined["n_ui"],
            "n_multi": combined["n_multi_desk"],
            "blocked_distinct": blocked,
            "hit_pct_ui": hit(combined["ui_rows"]),
        },
        "by_month_ui": {
            m: {"n": len(rs), "hit_pct": hit(rs)} for m, rs in sorted(by_month.items())
        },
        "p2f_day_3m": {
            d: {"n": len(p2f_day[d]), "hit_pct": hit(p2f_day[d])} for d in LIVE_DAY_DESKS
        },
        "p2f_cap2_3m": {
            d: {"n": len(p2f_cap2[d]), "hit_pct": hit(p2f_cap2[d])}
            for d in LIVE_CAP2_DESKS
        },
        "p2g_3m": {
            d: {"n": len(p2g[d]), "hit_pct": hit(p2g[d])} for d in LIVE_P2G_DESKS
        },
        "p2f_brackets": {"target": 30.0, "sl": 30.0, "risk": 30.0},
        "champ_brackets": {"target": 30.0, "sl": 30.0},
        "checks": checks,
    }

    fails = [c for c in checks if not c["ok"]]
    verdict = "PASS" if not fails else "FAIL"
    elapsed = round(time.time() - t0, 1)

    def desk_table(title: str, book: Dict[str, List[dict]]) -> List[str]:
        lines = [f"### {title}", "", "| Desk | N | Hit% |", "|---|---:|---:|"]
        for d, rs in book.items():
            lines.append(f"| `{d}` | {len(rs)} | {hit(rs)} |")
        lines.append("")
        return lines

    lines = [
        "# LIVE logic · 3m validate (count + accuracy)",
        "",
        f"**Window:** `{START}` → `{END}` (~3 months)",
        f"**Mode:** day-open `ensure_session_calls` + full P2F/P2G rebuild (same live code)",
        f"**Days seeded:** {len(days)}",
        f"**Combine UI:** raw={combined['n_raw']} · ui={combined['n_ui']} · multi={combined['n_multi_desk']} · **blocked={blocked}** · UI hit={hit(combined['ui_rows'])}%",
        "",
        "## P2F research Target / SL",
        "",
        "P2F path tickets use **risk = 30.0** → **Target +30 · SL −30** (symmetric).",
        "`good_by_risk['30.0']` is the research universe. Crown also has 20/35/40; live desks score on **30**.",
        f"Cache sample: good_by_risk[30] n={len(good30)}.",
        "",
        "## CHAMP_PLUS 3m",
        "",
        "| Slice | N | Hit% |",
        "|---|---:|---:|",
        f"| Held book | {len(champ_held_3m)} | {hit(champ_held_3m)} |",
        f"| Held ∪ live engine | {len(champ_full_3m)} | {hit(champ_full_3m)} |",
        "",
        "## Combined UI by month",
        "",
        "| Month | N | Hit% |",
        "|---|---:|---:|",
    ]
    for m, rs in sorted(by_month.items()):
        lines.append(f"| {m} | {len(rs)} | {hit(rs)} |")
    lines.append("")
    lines.extend(desk_table("P2F day · 3m", p2f_day))
    lines.extend(desk_table("P2F cap2 · 3m", p2f_cap2))
    lines.extend(desk_table("P2G 10m · 3m", p2g))
    lines.extend(["## Validation vs golden", ""])
    for c in checks:
        lines.append(f"- {'PASS' if c['ok'] else 'FAIL'} `{c['name']}` — {c['detail']}")
    lines.extend(
        [
            "",
            f"## Verdict: **{verdict}**",
            "",
            f"Fails: {len(fails)} · Elapsed {elapsed}s",
            "",
        ]
    )
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")

    if LEDGER_BAK.exists():
        shutil.copy2(LEDGER_BAK, eng._LIVE_LEDGER)
        print("  ledger restored", flush=True)

    print(f"\n=== {verdict} · wrote {OUT_MD} · {elapsed}s ===", flush=True)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
