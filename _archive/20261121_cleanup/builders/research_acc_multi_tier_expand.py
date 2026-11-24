"""Hold ACC100 V1–V3; hunt more calls across accuracy tiers.

Tiers (3y primary gate, 5y soft check):
  100 — perfect (path win)  → maybe ACC100_MULTI_V4
  98 / 95 / 92 / 90 / 85    → ACC_WIDE_* desks (max n @ floor)

User intent: keep high-acc desks + collect volume desks for later filter.
Not live.

  python -u prod_live/tests/builders/research_acc_multi_tier_expand.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
import path_setup  # noqa: F401,E402

import pandas as pd  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _hm_mins, _side, _ix  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    filt,
    first_day,
    bestp_day,
    gap_map,
    is_perfect,
    time_agree,
    union_unique_days,
)
from prod_live.logic.acc100_streams import merge_acc100_multi_v3  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL_10Y = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH_10Y = LEDGER / "_cache_path_trusted_10y.json"

END = "2026-11-13"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_5Y = (pd.Timestamp(END) - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
MIN_N = 5
FLOORS = (100.0, 98.0, 95.0, 92.0, 90.0, 85.0)


def hit_pct(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    w = sum(1 for r in rows if r.get("win"))
    return round(100.0 * w / len(rows), 4)


def meets_floor(rows: List[dict], floor: float, *, start: str) -> bool:
    rs = _clip(rows, start, END)
    if len(rs) < MIN_N:
        return True  # too thin to reject on this window
    if floor >= 100.0:
        return is_perfect(rs)
    return hit_pct(rs) + 1e-9 >= floor


def desk_ok(rows: List[dict], floor: float) -> bool:
    """3y hard + 5y soft (allow −2pp on 5y for non-100)."""
    if not meets_floor(rows, floor, start=START_3Y):
        return False
    soft = floor if floor >= 100.0 else max(floor - 2.0, 80.0)
    if not meets_floor(rows, soft, start=START_5Y):
        return False
    if not meets_floor(rows, soft, start=START_1Y):
        return False
    return True


def stream_ok(rows: List[dict], floor: float) -> bool:
    rs3 = _clip(rows, START_3Y, END)
    if len(rs3) < MIN_N:
        return False
    if floor >= 100.0:
        if not is_perfect(rs3):
            return False
        return meets_floor(rows, 100.0, start=START_5Y) and meets_floor(
            rows, 100.0, start=START_1Y
        )
    if hit_pct(rs3) + 1e-9 < floor:
        return False
    rs5 = _clip(rows, START_5Y, END)
    if len(rs5) >= MIN_N and hit_pct(rs5) + 1e-9 < max(floor - 2.0, 80.0):
        return False
    return True


BANDS = [
    ("first45", 9 * 60 + 15, 10 * 60),
    ("open", 9 * 60 + 15, 10 * 60 + 30),
    ("am11", 9 * 60 + 15, 11 * 60),
    ("am1130", 9 * 60 + 15, 11 * 60 + 30),
    ("am1230", 9 * 60 + 15, 12 * 60 + 30),
    ("mid", 10 * 60, 13 * 60),
    ("latemid", 10 * 60 + 30, 14 * 60),
    ("pm", 12 * 60 + 30, 15 * 60 + 15),
    ("all", None, None),
]
GAPS = [
    ("nogap", None, False, False),
    ("g035", 0.35, False, False),
    ("g040", 0.40, False, False),
    ("g045", 0.45, False, False),
    ("g055", 0.55, False, False),
    ("gdn040", 0.40, True, False),
    ("gdn055", 0.55, True, False),
    ("gup040", 0.40, False, True),
    ("gup055", 0.55, False, True),
]
PMINS = (0.0, 0.52, 0.55, 0.57, 0.60, 0.62, 0.65, 0.68, 0.70, 0.75, 0.80, 0.85)


def mine_all(
    path_u: dict,
    gaps: dict,
    active: set,
    dual15,
    dual5,
    proven,
    champ,
    *,
    floor_min: float = 85.0,
) -> List[Tuple[str, List[dict], Dict[str, Any]]]:
    """Mine stream candidates with 3y hit >= floor_min."""
    streams: List[Tuple[str, List[dict]]] = []

    universes: Dict[str, List[dict]] = {}
    for rk, rows in (path_u.get("crown_by_risk") or {}).items():
        if str(rk).startswith("_"):
            continue
        universes[f"CR{str(rk).replace('.0', '')}"] = rows
    for rk, rows in (path_u.get("good_by_risk") or {}).items():
        if str(rk).startswith("_") or rk == "native":
            continue
        universes[f"GD{str(rk).replace('.0', '')}"] = rows
    universes["CH"] = path_u.get("champ_native") or champ
    universes["D5"] = dual5
    universes["PR"] = proven

    n_eval = 0
    for uname, urows in universes.items():
        for side in (None, "BUY", "SELL"):
            for blab, lo, hi in BANDS:
                for glab, gabsm, gdn, gup in GAPS:
                    for use_htf in (False, True):
                        for pmin in PMINS:
                            base = filt(
                                urows,
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
                            ):
                                n_eval += 1
                                rs3 = _clip(vrows, START_3Y, END)
                                if len(rs3) < MIN_N:
                                    continue
                                h3 = hit_pct(rs3)
                                if h3 + 1e-9 < floor_min:
                                    continue
                                tag = (
                                    f"{uname}_{side or 'BOTH'}_p{int(round(pmin * 100))}_{blab}_"
                                    f"{'htf' if use_htf else 'any'}_{glab}_{vlab}"
                                )
                                streams.append((tag, vrows))

    # timed confirms
    ix15 = _ix(dual15)
    ix15p = _ix(proven)
    ix5 = _ix(dual5)
    for tol in (5, 10, 15, 20, 25, 30, 40, 45, 60, 90):
        for tag, rows in (
            (f"CF_T{tol}_any15_d5", time_agree(ix15, ix5, tol=tol, tag="cf")),
            (f"CF_T{tol}_p15_d5", time_agree(ix15p, ix5, tol=tol, tag="cf")),
        ):
            rs3 = _clip(rows, START_3Y, END)
            if len(rs3) >= MIN_N and hit_pct(rs3) + 1e-9 >= floor_min:
                streams.append((tag, rows))
        for rk, crow in (path_u.get("crown_by_risk") or {}).items():
            if str(rk).startswith("_"):
                continue
            tag = f"CF_T{tol}_any15_cr{str(rk).replace('.0', '')}"
            rows = time_agree(ix15, _ix(crow), tol=tol, tag="cf")
            rs3 = _clip(rows, START_3Y, END)
            if len(rs3) >= MIN_N and hit_pct(rs3) + 1e-9 >= floor_min:
                streams.append((tag, rows))

    # dedupe by day-side-hm signature; keep highest 3y n then hit
    by_sig: Dict[tuple, Tuple[str, List[dict], Dict[str, Any]]] = {}
    for tag, rows in streams:
        sig = tuple(
            sorted((str(r["day"]), _side(r), str(r.get("hm") or "")) for r in rows)
        )
        rs3 = _clip(rows, START_3Y, END)
        st = {
            "n_3y": len(rs3),
            "hit_3y": hit_pct(rs3),
            "n_5y": len(_clip(rows, START_5Y, END)),
            "hit_5y": hit_pct(_clip(rows, START_5Y, END)),
            "perfect_3y": is_perfect(rs3) if rs3 else False,
        }
        prev = by_sig.get(sig)
        if prev is None or st["n_3y"] > prev[2]["n_3y"] or (
            st["n_3y"] == prev[2]["n_3y"] and st["hit_3y"] > prev[2]["hit_3y"]
        ):
            by_sig[sig] = (tag, rows, st)

    out = list(by_sig.values())
    out.sort(key=lambda x: (x[2]["hit_3y"], x[2]["n_3y"]), reverse=True)
    print(f"  mined eval≈{n_eval} → unique streams={len(out)} (≥{floor_min}% 3y)", flush=True)
    return out


def greedy(
    base: List[dict],
    streams: List[Tuple[str, List[dict], Dict[str, Any]]],
    floor: float,
    *,
    max_rounds: int = 80,
) -> Tuple[List[dict], List[dict]]:
    cur = list(base)
    added: List[dict] = []
    improved = True
    rounds = 0
    while improved and rounds < max_rounds:
        improved = False
        rounds += 1
        cur_days = {str(r["day"]) for r in cur}
        ranked = []
        for tag, rows, st in streams:
            if not stream_ok(rows, floor):
                continue
            new_n = sum(1 for r in rows if str(r["day"]) not in cur_days)
            if new_n:
                # prefer more new days, then higher stream hit
                ranked.append((new_n, st.get("hit_3y") or 0, tag, rows))
        ranked.sort(reverse=True)
        for new_n, _h, tag, rows in ranked:
            merged = union_unique_days(cur, rows)
            if len(merged) <= len(cur):
                continue
            if not desk_ok(merged, floor):
                continue
            cur = merged
            d3 = _clip(cur, START_3Y, END)
            added.append(
                {
                    "tag": tag,
                    "new_n": new_n,
                    "desk_n": len(cur),
                    "desk_n_3y": len(d3),
                    "desk_hit_3y": hit_pct(d3),
                    "stream_n": len(rows),
                }
            )
            print(
                f"    [{floor:g}%] +{new_n} {tag} → desk3y={len(d3)}@{hit_pct(d3):.1f}%",
                flush=True,
            )
            improved = True
            break
    return cur, added


def parse_recipe(tag: str) -> Optional[Dict[str, Any]]:
    """Best-effort parse mined tag → stream recipe for packaging."""
    m = re.match(
        r"^(CR|GD|CH|D5|PR)(\d*)_(BUY|SELL|BOTH)_p(\d+)_(.+?)_(htf|any)_(.+?)_(raw|first|bestp)$",
        tag,
    )
    if not m:
        return None
    ch_raw, risk_s, side, p_s, blab, htf, glab, pick = m.groups()
    channel = {"CR": "crown", "GD": "good", "CH": "champ", "D5": "dual5", "PR": "proven"}[
        ch_raw
    ]
    band = {b[0]: (b[1], b[2]) for b in BANDS}
    lo, hi = band.get(blab, (None, None))
    recipe: Dict[str, Any] = {
        "tag": f"ACC_WIDE_{tag}",
        "source_tag": tag,
        "channel": channel,
        "risk": float(risk_s) if risk_s else None,
        "side": None if side == "BOTH" else side,
        "p_min": int(p_s) / 100.0,
        "hm_lo": lo,
        "hm_hi": hi,
        "htf": htf == "htf",
        "pick": pick,
    }
    if glab == "nogap":
        pass
    elif glab.startswith("gdn"):
        recipe["gap_dn"] = float(glab.replace("gdn", "")) / 100.0 if glab[3:].isdigit() else 0.40
        if glab[3:].isdigit():
            recipe["gap_dn"] = int(glab[3:]) / 100.0
    elif glab.startswith("gup"):
        recipe["gap_up"] = int(glab[3:]) / 100.0 if glab[3:].isdigit() else 0.40
    elif glab.startswith("g") and glab[1:].isdigit():
        recipe["gap_abs"] = int(glab[1:]) / 100.0
    return recipe


def summarize(desk: List[dict]) -> Dict[str, Any]:
    d3 = _clip(desk, START_3Y, END)
    d5 = _clip(desk, START_5Y, END)
    d1 = _clip(desk, START_1Y, END)
    return {
        "n_3y": len(d3),
        "hit_3y": hit_pct(d3),
        "perfect_3y": is_perfect(d3) if d3 else False,
        "points_3y": _agg(d3).get("points"),
        "n_5y": len(d5),
        "hit_5y": hit_pct(d5),
        "perfect_5y": is_perfect(d5) if d5 else False,
        "points_5y": _agg(d5).get("points"),
        "n_1y": len(d1),
        "hit_1y": hit_pct(d1),
    }


def main() -> None:
    t0 = time.time()
    print("MULTI-TIER expand from held ACC100_MULTI_V3 (keep V1+V2+V3)", flush=True)

    dual = json.loads(CACHE_DUAL_10Y.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH_10Y.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(4000)
    sess = [d for d in sessions_all if START_5Y < d <= END]
    daily = fs._load_daily()
    active = fs._active_days(sess, daily)

    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ = _champ_floor([dict(r, track="champion") for r in dual["dual15"]["champion"]])
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]
    crown_by_risk = path_u.get("crown_by_risk") or {}
    good_by_risk = path_u.get("good_by_risk") or {}
    champ_native = path_u.get("champ_native") or champ

    print("  rebuild V3 desk…", flush=True)
    v3 = merge_acc100_multi_v3(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active,
    )
    v3_sum = summarize(v3)
    print(
        f"  V3 3y n={v3_sum['n_3y']} hit={v3_sum['hit_3y']} | "
        f"5y n={v3_sum['n_5y']} hit={v3_sum['hit_5y']}",
        flush=True,
    )

    print("  mining streams (≥85% 3y)…", flush=True)
    path_bundle = {
        "crown_by_risk": crown_by_risk,
        "good_by_risk": good_by_risk,
        "champ_native": champ_native,
    }
    all_streams = mine_all(
        path_bundle, gaps, active, dual15, dual5, proven, champ, floor_min=85.0
    )
    perfect_streams = [s for s in all_streams if s[2].get("perfect_3y")]
    print(f"  perfect-3y streams={len(perfect_streams)}", flush=True)

    tiers: Dict[str, Any] = {}
    # 100% first from V3
    print("  greedy 100% onto V3…", flush=True)
    desk100, added100 = greedy(v3, perfect_streams, 100.0)
    tiers["100"] = {
        "desk_tag": "ACC100_MULTI_V4" if added100 else "ACC100_MULTI_V3",
        "baseline": "ACC100_MULTI_V3",
        "floor": 100.0,
        "result": summarize(desk100),
        "delta_vs_v3_3y": summarize(desk100)["n_3y"] - v3_sum["n_3y"],
        "added_streams": added100,
        "recipes": [parse_recipe(a["tag"]) for a in added100],
    }

    prev_desk = desk100
    prev_tag = tiers["100"]["desk_tag"]
    for floor in FLOORS:
        if floor >= 100.0:
            continue
        key = str(int(floor))
        print(f"  greedy {floor:g}% onto prior desk…", flush=True)
        eligible = [s for s in all_streams if stream_ok(s[1], floor)]
        desk, added = greedy(prev_desk, eligible, floor)
        tag = f"ACC_WIDE_P{key}"
        tiers[key] = {
            "desk_tag": tag,
            "baseline": prev_tag,
            "floor": floor,
            "result": summarize(desk),
            "delta_vs_v3_3y": summarize(desk)["n_3y"] - v3_sum["n_3y"],
            "added_streams": added,
            "recipes": [r for r in (parse_recipe(a["tag"]) for a in added) if r],
            "streams_eligible": len(eligible),
        }
        prev_desk = desk
        prev_tag = tag

    # also: max-volume at 85% starting from V3 directly (not chained) for comparison
    print("  greedy 85% direct from V3 (volume path)…", flush=True)
    eligible85 = [s for s in all_streams if stream_ok(s[1], 85.0)]
    desk85d, added85d = greedy(v3, eligible85, 85.0, max_rounds=120)
    tiers["85_direct"] = {
        "desk_tag": "ACC_WIDE_P85_DIRECT",
        "baseline": "ACC100_MULTI_V3",
        "floor": 85.0,
        "result": summarize(desk85d),
        "delta_vs_v3_3y": summarize(desk85d)["n_3y"] - v3_sum["n_3y"],
        "added_streams": added85d,
        "recipes": [r for r in (parse_recipe(a["tag"]) for a in added85d) if r],
    }

    payload = {
        "keep_held": ["ACC100_MULTI_V1", "ACC100_MULTI_V2", "ACC100_MULTI_V3"],
        "v3_baseline": v3_sum,
        "streams_mined": len(all_streams),
        "perfect_streams": len(perfect_streams),
        "tiers": tiers,
        "elapsed_s": round(time.time() - t0, 1),
        "note": "HOLDING — filter later; not live",
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ACC_MULTI_TIER_EXPAND.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (LEDGER / "ACC_MULTI_TIER_EXPAND.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Multi-tier expand (hold V1–V3)",
        "",
        "Keep held 100% desks; collect more calls at lower floors for later filter.",
        "",
        f"V3 baseline: 3y **{v3_sum['n_3y']}** @ {v3_sum['hit_3y']}% · "
        f"5y **{v3_sum['n_5y']}** @ {v3_sum['hit_5y']}%",
        "",
        f"Mined streams (≥85% 3y): {len(all_streams)} · perfect-3y: {len(perfect_streams)} · "
        f"elapsed {payload['elapsed_s']}s",
        "",
        "## Desk ladder",
        "",
        "| Desk | Floor | 3y N | 3y Hit | 5y N | 5y Hit | 1y N | Δ vs V3 3y |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        f"| `ACC100_MULTI_V3` | 100 | {v3_sum['n_3y']} | {v3_sum['hit_3y']} | "
        f"{v3_sum['n_5y']} | {v3_sum['hit_5y']} | {v3_sum['n_1y']} | 0 |",
    ]
    order = ["100", "98", "95", "92", "90", "85", "85_direct"]
    for k in order:
        t = tiers.get(k)
        if not t:
            continue
        r = t["result"]
        lines.append(
            f"| `{t['desk_tag']}` | {t['floor']:g} | {r['n_3y']} | {r['hit_3y']} | "
            f"{r['n_5y']} | {r['hit_5y']} | {r['n_1y']} | {t['delta_vs_v3_3y']:+d} |"
        )

    lines += ["", "## Added streams (per tier)", ""]
    for k in order:
        t = tiers.get(k)
        if not t:
            continue
        lines.append(f"### `{t['desk_tag']}` ({t['floor']:g}%)")
        lines.append("")
        if not t["added_streams"]:
            lines.append("_No new stream cleared this floor._")
        else:
            lines += ["| # | Tag | +days | Desk3y | Hit3y |", "|---:|---|---:|---:|---:|"]
            for i, a in enumerate(t["added_streams"], 1):
                lines.append(
                    f"| {i} | `{a['tag']}` | +{a['new_n']} | {a.get('desk_n_3y')} | "
                    f"{a.get('desk_hit_3y')} |"
                )
        lines.append("")

    lines += [
        "## Verdict",
        "",
        "- Keep **V1 + V2 + V3** (100%).",
        "- Hold any **V4** if 100% tier added calls.",
        "- Hold **ACC_WIDE_P*** desks as filter candidates (not live).",
        "",
        "JSON: `ACC_MULTI_TIER_EXPAND.json`",
        "",
    ]
    md = OUT / "ACC_MULTI_TIER_EXPAND.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (LEDGER / "ACC_MULTI_TIER_EXPAND.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", md, flush=True)
    print(json.dumps({k: tiers[k]["result"] for k in tiers}, indent=2), flush=True)


if __name__ == "__main__":
    main()
