"""Replay FINAL live logic bar-by-bar for last 3 months (same session code).

For every session date · every 5m candle (09:15–15:30):
  - run CHAMP_PLUS live engine exactly as session annotate does
  - P2F / P2G rebuilt from held recipes (same live desks)
  - combine UI · never block
Then validate vs golden held/report slices.

  python -u prod_live/tests/builders/replay_live_logic_3m_bar_by_bar.py
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "prod_live"))
import path_setup  # noqa: F401,E402

from accuracy_max_6m import _agg, _champ_floor  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    _norm,
    build_bar_index,
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
from prod_live.adapters.live_session_final import annotate_analyze_result  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "LIVE_LOGIC_3M_BAR_REPLAY.md"
OUT_JSON = OUT / "LIVE_LOGIC_3M_BAR_REPLAY.json"
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"
LEDGER_BAK = eng._HOLD / "live_session_calls.json.bak_3m_replay"

END = "2026-11-15"
START = (pd.Timestamp(END) - timedelta(days=92)).strftime("%Y-%m-%d")  # ~3m


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
    print(f"LIVE 3m bar replay {START} → {END}", flush=True)

    # isolate live ledger
    if eng._LIVE_LEDGER.exists():
        shutil.copy2(eng._LIVE_LEDGER, LEDGER_BAK)
    eng.save_live_ledger([])

    # ---- tape bars ----
    print("  load 5m tape…", flush=True)
    bars = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    hm = bars.index.strftime("%H:%M")
    bars = bars[(hm >= "09:15") & (hm <= "15:30")]
    mask = (bars.index.strftime("%Y-%m-%d") >= START) & (
        bars.index.strftime("%Y-%m-%d") <= END
    )
    bars3 = bars.loc[mask]
    print(f"  bars3m={len(bars3)} days={bars3.index.strftime('%Y-%m-%d').nunique()}", flush=True)

    # ---- P2F rebuild (same live code) ----
    print("  P2F rebuild…", flush=True)
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

    # ---- P2G rebuild ----
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

    # ---- index candidates by (day,hm) for dual simulation ----
    print("  index session candidates…", flush=True)
    by_dh: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    # use engine cache loader per day (once)
    days = sorted(set(bars3.index.strftime("%Y-%m-%d")))
    for day in days:
        for r in eng._load_cache_candidates_for_day(day):
            by_dh[(day, str(r.get("hm") or ""))].append(r)

    # ---- bar-by-bar live CHAMP (same annotate path) ----
    print("  bar-by-bar CHAMP live engine…", flush=True)
    bar_events = 0
    fire_events = 0
    annotate_ok = 0
    last_day = None
    for ts, row in bars3.iterrows():
        day = ts.strftime("%Y-%m-%d")
        hm_s = ts.strftime("%H:%M")
        px = float(row["Close"])
        bar_events += 1
        # once per day: run engine for day (cache candidates) — same as session open
        if day != last_day:
            last_day = day
            ensure_session_calls(day)

        dual = None
        cands = by_dh.get((day, hm_s)) or []
        if cands:
            # pick best p as live dual would surface one call at this candle
            best = max(cands, key=lambda x: float(x.get("p_t1") or 0))
            dual = {
                "decision": _side(best),
                "day": day,
                "hm": hm_s,
                "entry": best.get("entry") or px,
                "p_t1": float(best.get("p_t1") or 0.6),
                "track": best.get("track") or "session",
            }

        if dual:
            meta = ensure_session_calls(
                day, dual_call=dual, hm=hm_s, entry=float(dual["entry"])
            )
            if int(meta.get("n_added") or 0) > 0:
                fire_events += 1
            # same annotate code path as live session (no toast spam)
            result = {"fno_analysis": {}}
            annotate_analyze_result(
                result,
                symbol="NIFTY",
                dual_call=dict(dual),
                readings={"hm": hm_s, "entry": px},
                emit_notify=False,
            )
            if (result.get("fno_analysis") or {}).get("champ_plus_live"):
                annotate_ok += 1

        if bar_events % 2000 == 0:
            print(
                f"    bars={bar_events} fires={fire_events} annotate_ok={annotate_ok}",
                flush=True,
            )

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

    # ---- validations ----
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

    # held CHAMP keys must still be present in full book
    held_keys = {call_key(r) for r in champ_held_3m if all(call_key(r))}
    full_keys = {call_key(r) for r in champ_full_3m if all(call_key(r))}
    add_check(
        "champ_held_preserved",
        held_keys <= full_keys,
        f"held_3m={len(held_keys)} full_3m={len(full_keys)} missing={len(held_keys-full_keys)}",
    )

    # CHAMP levels ±30
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

    # tags
    bad_tag = sum(
        1
        for r in champ_full_3m
        if r.get("accurate_tag") != CHAMP_DESK or r.get("accuracy_tag") != CHAMP_ACC
    )
    add_check("champ_tags", bad_tag == 0, f"bad_tag={bad_tag}")

    # P2F 1y confirm still matches when rebuilt (full 1y window — golden)
    p2f_ok = True
    p2f_details = []
    for desk in LIVE_DAY_DESKS:
        rs = _clip(p2f_day_full.get(desk) or [], P2F_1Y["start"], P2F_1Y["end"])
        exp = P2F_DAY_EXP[desk]
        ok = len(rs) == int(exp["n"]) and abs(hit(rs) - float(exp["hit_pct"])) <= 0.05
        p2f_ok = p2f_ok and ok
        p2f_details.append(f"{desk}:{len(rs)}@{hit(rs)}")
    add_check("p2f_day_1y_golden", p2f_ok, "; ".join(p2f_details[:3]) + "…")

    p2f_c_ok = True
    for desk in LIVE_CAP2_DESKS:
        rs = _clip(p2f_cap2_full.get(desk) or [], P2F_1Y["start"], P2F_1Y["end"])
        exp = P2F_CAP2_EXP[desk]
        ok = len(rs) == int(exp["n"]) and abs(hit(rs) - float(exp["hit_pct"])) <= 0.05
        p2f_c_ok = p2f_c_ok and ok
    add_check("p2f_cap2_1y_golden", p2f_c_ok, "all cap2 desks match EXPECTED_1Y")

    # P2F path risk documentation sample
    good30 = (path_u.get("good_by_risk") or {}).get("30.0") or (path_u.get("good_by_risk") or {}).get("30") or []
    risk_ok = bool(good30) and all(
        float(r.get("risk") or r.get("path_risk") or 0) == 30.0 for r in good30[:50]
    )
    add_check(
        "p2f_research_risk_30",
        risk_ok,
        f"good_by_risk[30] n={len(good30)} · points ±30 (target/SL)",
    )

    # 3m book stats
    stats = {
        "window": {"start": START, "end": END},
        "bars_replayed": bar_events,
        "champ_fire_events": fire_events,
        "annotate_ok": annotate_ok,
        "champ_held_3m": {"n": len(champ_held_3m), "hit_pct": hit(champ_held_3m)},
        "champ_full_3m": {"n": len(champ_full_3m), "hit_pct": hit(champ_full_3m)},
        "combine": {
            "n_raw": combined["n_raw"],
            "n_ui": combined["n_ui"],
            "n_multi": combined["n_multi_desk"],
            "blocked_distinct": blocked,
        },
        "p2f_day_3m": {
            d: {"n": len(p2f_day[d]), "hit_pct": hit(p2f_day[d])} for d in LIVE_DAY_DESKS
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

    lines = [
        "# LIVE logic · 3m bar-by-bar replay",
        "",
        f"**Window:** `{START}` → `{END}` (~3 months)",
        f"**Bars replayed:** {bar_events} (every 5m candle 09:15–15:30)",
        f"**Code path:** `ensure_session_calls` + `annotate_analyze_result` (same as live)",
        f"**CHAMP fire events:** {fire_events} · annotate_ok={annotate_ok}",
        f"**Combine UI:** raw={combined['n_raw']} · ui={combined['n_ui']} · multi={combined['n_multi_desk']} · **blocked={blocked}**",
        "",
        "## P2F research Target / SL",
        "",
        "P2F (and P2G) path tickets use **risk = 30.0** → Target **+30** · SL **−30** (symmetric).",
        "`good_by_risk['30.0']` points are ±30. Crown also has 20/35/40 buckets; main accurate desks score on **30**.",
        "",
        "## CHAMP_PLUS 3m",
        "",
        f"| Slice | N | Hit% |",
        f"|---|---:|---:|",
        f"| Held book | {len(champ_held_3m)} | {hit(champ_held_3m)} |",
        f"| Held ∪ live engine | {len(champ_full_3m)} | {hit(champ_full_3m)} |",
        "",
        "## Validation",
        "",
    ]
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

    # restore ledger
    if LEDGER_BAK.exists():
        shutil.copy2(LEDGER_BAK, eng._LIVE_LEDGER)
        LEDGER_BAK.unlink(missing_ok=True)

    print(f"Wrote {OUT_MD}", flush=True)
    print(f"VERDICT {verdict} · fails={len(fails)}", flush=True)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
