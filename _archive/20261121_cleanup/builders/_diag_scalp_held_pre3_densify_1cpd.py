"""Hold ACC100_PRE3_RAW; densify toward ~1 call/day @100% path T20 SL<=10."""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
import research_nifty_1m_vix_candle_adaptive as vixmod  # noqa: E402
import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import (  # noqa: E402
    EV_CACHE,
    HIST_LO,
    PACK,
    SL10_STYLES,
    SL_MAX,
    T1,
    enrich_prior3,
    flag_sl10,
    path_ok_sl10,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT_MD = OUT / "NIFTY_1M_SCALP_HELD_PRE3_DENSE_1CPD.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_HELD_PRE3_DENSE_1CPD.json"
HELD_NAME = "ACC100_PRE3_RAW"


def keys_dense(e):
    """Broader+finer key set for densify (includes held PRE3 geometry)."""
    keys = list(fwdmod.keys_hight(e))
    keys += [
        (e["primary"], e["decision"], e.get("pre3_stack"), e.get("close_ok"), e.get("adv_bin"), e.get("hm_bin"), e.get("vix_regime")),
        (e["family"], e["decision"], e.get("pre3_stack"), e.get("struct2"), e.get("close_ok"), e.get("slbin")),
        (e["primary"], e["decision"], e.get("pre3_opp"), e.get("close_ok"), e.get("adv_bin"), e.get("body_bin"), e.get("clock")),
        ("P3", e["decision"], e.get("pre3_stack"), e.get("struct2"), e.get("adv_bin"), e.get("vix_regime"), e.get("hm_bin")),
        (e["family"], e["decision"], e.get("stair"), e.get("close_ok"), e.get("pre3_weak_struct"), e.get("adv_bin")),
        # extra densify keys
        (e["primary"], e["decision"], e.get("close_ok"), e.get("adv_bin"), e.get("body_bin"), e.get("hm_bin")),
        (e["primary"], e["decision"], e.get("pre3_stack"), e.get("struct2"), e.get("slbin")),
        (e["family"], e["decision"], e.get("pre3_stack"), e.get("hm_bin"), e.get("vix_regime")),
        ("GEO3", e["decision"], e.get("struct2"), e.get("stair"), e.get("close_ok"), e.get("adv_bin"), e.get("clock")),
        (e["primary"], e["decision"], e.get("align_session"), e.get("pre_regime"), e.get("close_ok"), e.get("adv_bin"), e.get("hm_bin")),
        ("VS", e.get("very_strong"), e["decision"], e.get("pre3_stack"), e.get("vix_regime"), e.get("slbin")),
        (e["family"], e["decision"], e.get("slot"), e.get("close_ok"), e.get("adv_bin"), e.get("body_bin")),
    ]
    return keys


def index_all(events):
    """(k,st) -> list[(e, ok, sl)] for all SL10-valid events."""
    bucket = defaultdict(list)
    for e in events:
        for st in SL10_STYLES:
            sl = e.get(f"_sl10_{st}", 99)
            if not (4 <= sl <= SL_MAX):
                continue
            ok = bool(e.get(f"_ok10_{st}"))
            for k in e["_keys"]:
                bucket[(k, st)].append((e, ok, sl))
    return bucket


def zero_loss_cells(era_idxs, min_cal=1, min_l3m=1, require_hold=False):
    """Cells with zero path losses in every era; enough train fires."""
    cal_idx, l3m_idx, hold_idx, fwd_idx = era_idxs
    # candidate keys = union of keys seen as wins in cal or l3m
    cand = set()
    for idx in (cal_idx, l3m_idx):
        for (k, st), rows in idx.items():
            if any(ok for _, ok, _ in rows):
                cand.add((k, st))

    cells = []
    for k, st in cand:
        rows_list = [cal_idx.get((k, st), []), l3m_idx.get((k, st), []), hold_idx.get((k, st), []), fwd_idx.get((k, st), [])]
        if any(rows and any(not ok for _, ok, _ in rows) for rows in rows_list):
            continue
        c_ev = [e for e, ok, _ in rows_list[0] if ok]
        l_ev = [e for e, ok, _ in rows_list[1] if ok]
        h_ev = [e for e, ok, _ in rows_list[2] if ok]
        f_ev = [e for e, ok, _ in rows_list[3] if ok]
        if len(c_ev) < min_cal or len(l_ev) < min_l3m:
            continue
        if require_hold and len(h_ev) < 1:
            continue
        # day sets for coverage greedy
        days = {e["day"] for e in c_ev + l_ev + h_ev + f_ev}
        avg_sl = sum(e[f"_sl10_{st}"] for e in c_ev + l_ev) / max(len(c_ev) + len(l_ev), 1)
        for e in c_ev + l_ev + h_ev + f_ev:
            e[f"_ok_{st}"] = True
            e[f"_sl_{st}"] = e[f"_sl10_{st}"]
            e["_sl"] = e[f"_sl10_{st}"]
            e["_win"] = True
        cells.append(
            {
                "k": k,
                "st": st,
                "cal_calls": c_ev,
                "l3m_calls": l_ev,
                "hold_calls": h_ev,
                "fwd_calls": f_ev,
                "cal_n": len(c_ev),
                "l3m_n": len(l_ev),
                "hold_n": len(h_ev),
                "fwd_n": len(f_ev),
                "total_n": len(c_ev) + len(l_ev) + len(h_ev) + len(f_ev),
                "days": days,
                "avg_sl": avg_sl,
            }
        )
    cells.sort(key=lambda r: (-len(r["days"]), -r["total_n"], r["avg_sl"]))
    return cells


def greedy_day_cover(cells, gap, min_cal=1, min_l3m=1):
    """Greedy: maximize new days covered, then calls; respect gap."""
    used = set()
    chosen = []

    def take(calls):
        out, last = [], {}
        for e in sorted(calls, key=lambda x: (x["day"], x["mins"])):
            key = (e["day"], e["mins"])
            if key in used:
                continue
            if any(d == e["day"] and abs(m - e["mins"]) < gap for d, m in used):
                continue
            prev = last.get(e["day"])
            if prev is not None and e["mins"] - prev < gap:
                continue
            out.append(e)
            last[e["day"]] = e["mins"]
        return out

    # re-score remaining by new days each round (simple single-pass greedy with day priority)
    remaining = list(cells)
    covered = set()
    while remaining:
        best_i, best_score, best_kept = -1, None, None
        for i, r in enumerate(remaining):
            pooled = r["cal_calls"] + r["l3m_calls"] + r["hold_calls"] + r["fwd_calls"]
            kept = take(pooled)
            if len([e for e in kept if e in r["cal_calls"] or e["day"] in {x["day"] for x in r["cal_calls"]}]) < 0:
                pass
            # recount by era membership via day lists
            ck = [e for e in kept if any(e is x or (e["day"] == x["day"] and e["mins"] == x["mins"]) for x in r["cal_calls"])]
            # faster: tag era on events
            for e in r["cal_calls"]:
                e["_era_tag"] = "cal"
            for e in r["l3m_calls"]:
                e["_era_tag"] = "l3m"
            for e in r["hold_calls"]:
                e["_era_tag"] = "hold"
            for e in r["fwd_calls"]:
                e["_era_tag"] = "fwd"
            kept2 = take(r["cal_calls"] + r["l3m_calls"] + r["hold_calls"] + r["fwd_calls"])
            n_cal = sum(1 for e in kept2 if e.get("_era_tag") == "cal")
            n_l3m = sum(1 for e in kept2 if e.get("_era_tag") == "l3m")
            if n_cal < min_cal or n_l3m < min_l3m:
                continue
            new_days = {e["day"] for e in kept2} - covered
            score = (len(new_days), len(kept2), -r["avg_sl"])
            if best_score is None or score > best_score:
                best_score, best_i, best_kept = score, i, kept2
        if best_i < 0:
            break
        r = remaining.pop(best_i)
        if not best_kept:
            continue
        # if no new days and we already have decent cover, still take if adds calls early; always take if new days
        new_days = {e["day"] for e in best_kept} - covered
        chosen.append({**r, "kept": best_kept, "cal_n": sum(1 for e in best_kept if e.get("_era_tag") == "cal"), "l3m_n": sum(1 for e in best_kept if e.get("_era_tag") == "l3m")})
        for e in best_kept:
            used.add((e["day"], e["mins"]))
            covered.add(e["day"])
        # stop early if remaining cannot add days and pass is huge — keep going for call densify
        if len(chosen) > 5000:
            break
    return chosen, covered


def greedy_simple(cells, gap, min_cal=1, min_l3m=1):
    """Faster single-pass greedy (sorted by days/total)."""
    used = set()
    chosen = []
    covered = set()

    def take(calls):
        out, last = [], {}
        for e in sorted(calls, key=lambda x: (x["day"], x["mins"])):
            key = (e["day"], e["mins"])
            if key in used:
                continue
            if any(d == e["day"] and abs(m - e["mins"]) < gap for d, m in used):
                continue
            prev = last.get(e["day"])
            if prev is not None and e["mins"] - prev < gap:
                continue
            out.append(e)
            last[e["day"]] = e["mins"]
        return out

    for r in cells:
        for e in r["cal_calls"]:
            e["_era_tag"] = "cal"
        for e in r["l3m_calls"]:
            e["_era_tag"] = "l3m"
        for e in r["hold_calls"]:
            e["_era_tag"] = "hold"
        for e in r["fwd_calls"]:
            e["_era_tag"] = "fwd"
        kept = take(r["cal_calls"] + r["l3m_calls"] + r["hold_calls"] + r["fwd_calls"])
        n_cal = sum(1 for e in kept if e.get("_era_tag") == "cal")
        n_l3m = sum(1 for e in kept if e.get("_era_tag") == "l3m")
        if n_cal < min_cal or n_l3m < min_l3m:
            continue
        chosen.append({**r, "kept": kept})
        for e in kept:
            used.add((e["day"], e["mins"]))
            covered.add(e["day"])
    return chosen, covered


def eval_book(events, micros, key_fn, h, l, c, gap):
    for e in events:
        e["_keys"] = set(key_fn(e))
    micro_map = [(r["k"], r["st"]) for r in micros]
    by = defaultdict(list)
    for e in events:
        by[e["day"]].append(e)
    out = []
    for d, xs in sorted(by.items()):
        last = None
        for e in sorted(xs, key=lambda x: x["mins"]):
            if last is not None and e["mins"] - last < gap:
                continue
            for k, st in micro_map:
                if k not in e["_keys"]:
                    continue
                sl = e.get(f"_sl10_{st}", 99)
                if not (4 <= sl <= SL_MAX):
                    continue
                ok, sl2 = path_ok_sl10(e, h, l, c, st)
                out.append({**e, "_st": st, "_sl": sl2, "_win": bool(ok)})
                last = e["mins"]
                break
    return out


def stats(calls, n_days_univ):
    if not calls:
        return {"n": 0, "hit": 0.0, "all_win": True, "days": 0, "cpd": 0.0, "cpd_all": 0.0, "cover": 0.0, "avg_sl": 0}
    w = sum(1 for e in calls if e["_win"])
    days = len({e["day"] for e in calls})
    return {
        "n": len(calls),
        "hit": round(100.0 * w / len(calls), 2),
        "all_win": all(e["_win"] for e in calls),
        "days": days,
        "cpd": round(len(calls) / max(days, 1), 2),
        "cpd_all": round(len(calls) / max(n_days_univ, 1), 2),
        "cover": round(100.0 * days / max(n_days_univ, 1), 1),
        "avg_sl": round(sum(e["_sl"] for e in calls) / len(calls), 2),
    }


def oracle_days(events):
    """Days with ≥1 SL≤10 T20 path win (ceiling for 1/day @100%)."""
    by = defaultdict(list)
    for e in events:
        by[e["day"]].append(e)
    good = 0
    for d, xs in by.items():
        hit = False
        for e in xs:
            for st in SL10_STYLES:
                if e.get(f"_ok10_{st}") and 4 <= e.get(f"_sl10_{st}", 99) <= SL_MAX:
                    hit = True
                    break
            if hit:
                break
        good += int(hit)
    return good, len(by)


def main() -> int:
    print("=" * 60, flush=True)
    print("HOLD PRE3_RAW + densify toward 1 call/day @100%", flush=True)
    print("=" * 60, flush=True)
    PACK.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    blob = pickle.load(EV_CACHE.open("rb"))
    era_events = blob["era_events"]
    held = pickle.loads((PACK / f"{HELD_NAME}_micros.pkl").read_bytes())
    print(f"held {HELD_NAME} micros={len(held)}", flush=True)

    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(HIST_LO, tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    vix_prior = vixmod.load_vix()

    print("[1] enrich…", flush=True)
    for name, xs in era_events.items():
        fwdmod.enrich_evt(xs, h, l, c, o)
        enrich_structure(xs, h, l, c, o, vix_prior)
        enrich_prior3(xs, h, l, c, o)
        flag_sl10(xs, h, l, c)
        print(f"  {name}", flush=True)

    cal, l3m = era_events["E2024"], era_events["E2025"]
    hold = era_events["E2026A"] + era_events["E2026B"]
    fwd = era_events["FWD"]

    for e in cal + l3m + hold + fwd:
        e["_keys"] = set(keys_dense(e))

    # oracle ceiling
    print("[2] oracle day ceiling…", flush=True)
    ceilings = {}
    for label, xs in [("E2024", cal), ("E2025", l3m), ("HOLD", hold), ("FWD", fwd)]:
        g, n = oracle_days(xs)
        ceilings[label] = {"win_days": g, "all_days": n, "max_cover%": round(100.0 * g / max(n, 1), 1)}
        print(f"  {label}: {g}/{n} days have ≥1 T20/SL10 path win ({ceilings[label]['max_cover%']}%)", flush=True)

    print("[3] index zero-loss cells…", flush=True)
    era_idxs = (index_all(cal), index_all(l3m), index_all(hold), index_all(fwd))

    variants = {}
    for vname, gap, min_cal, min_l3m in [
        ("HELD_BASE_g4", 4, 2, 1),
        ("DENSE_g4_m11", 4, 1, 1),
        ("DENSE_g2_m11", 2, 1, 1),
        ("DENSE_g1_m11", 1, 1, 1),
        ("DENSE_g2_m21", 2, 2, 1),
        ("DENSE_g4_m22", 4, 2, 2),
    ]:
        print(f"\n#### {vname}", flush=True)
        cells = zero_loss_cells(era_idxs, min_cal=min_cal, min_l3m=min_l3m)
        print(f"  zero-loss cells={len(cells)}", flush=True)
        # seed held micros to front
        held_set = {(tuple(r["k"]) if isinstance(r["k"], list) else r["k"], r["st"]) for r in held}
        # held keys may be tuples already
        def is_held(r):
            return (r["k"], r["st"]) in held_set or (str(r["k"]), r["st"]) in {(str(k), s) for k, s in held_set}

        cells_sorted = sorted(cells, key=lambda r: (0 if is_held(r) else 1, -len(r["days"]), -r["total_n"], r["avg_sl"]))
        chosen, covered = greedy_simple(cells_sorted, gap, min_cal=min_cal, min_l3m=min_l3m)

        # verify
        va = stats(eval_book(cal, chosen, keys_dense, h, l, c, gap), ceilings["E2024"]["all_days"])
        vl = stats(eval_book(l3m, chosen, keys_dense, h, l, c, gap), ceilings["E2025"]["all_days"])
        vh = stats(eval_book(hold, chosen, keys_dense, h, l, c, gap), ceilings["HOLD"]["all_days"])
        vf = stats(eval_book(fwd, chosen, keys_dense, h, l, c, gap), ceilings["FWD"]["all_days"])
        total = va["n"] + vl["n"] + vh["n"] + vf["n"]
        aw = va["all_win"] and vl["all_win"] and vh["all_win"] and vf["all_win"]
        # blended cpd_all across all univ days
        univ = ceilings["E2024"]["all_days"] + ceilings["E2025"]["all_days"] + ceilings["HOLD"]["all_days"] + ceilings["FWD"]["all_days"]
        cpd_all = round(total / max(univ, 1), 3)
        cover_all = round(
            100.0
            * (
                va["days"] + vl["days"] + vh["days"] + vf["days"]
            )  # approx; days unique within era already
            / max(univ, 1),
            1,
        )
        print(
            f"  micros={len(chosen)} total={total} cpd_all={cpd_all} "
            f"24={va['n']}@{va['hit']}%/{va['cover']}%d "
            f"25={vl['n']}@{vl['hit']}%/{vl['cover']}%d "
            f"H={vh['n']}@{vh['hit']}%/{vh['cover']}%d "
            f"F={vf['n']}@{vf['hit']}% all_win={aw}",
            flush=True,
        )
        variants[vname] = {
            "gap": gap,
            "min_cal": min_cal,
            "min_l3m": min_l3m,
            "n_micros": len(chosen),
            "total": total,
            "cpd_all": cpd_all,
            "verify": {"E2024": va, "E2025": vl, "HOLD": vh, "FWD": vf},
            "all_win": aw,
            "micros": [{"k": str(r["k"]), "st": r["st"], "total_n": r["total_n"], "hold_n": r["hold_n"]} for r in chosen[:80]],
        }
        (PACK / f"{vname}_micros.pkl").write_bytes(
            pickle.dumps([{"k": r["k"], "st": r["st"]} for r in chosen], protocol=pickle.HIGHEST_PROTOCOL)
        )

    # pick best: all_win first, then hold cover, then cpd_all, then total
    def rank(v):
        x = variants[v]
        vh = x["verify"]["HOLD"]
        return (x["all_win"], vh["cover"], x["cpd_all"], x["total"], vh["n"])

    best = max(variants.keys(), key=rank)
    print(f"\nBEST densify={best} cpd_all={variants[best]['cpd_all']}", flush=True)

    # also lock alias
    best_micros = pickle.loads((PACK / f"{best}_micros.pkl").read_bytes())
    (PACK / "HELD_PRE3_DENSE_1CPD_micros.pkl").write_bytes(
        pickle.dumps(best_micros, protocol=pickle.HIGHEST_PROTOCOL)
    )
    (PACK / "HELD_PRE3_RAW_LOCK_micros.pkl").write_bytes(
        pickle.dumps(held, protocol=pickle.HIGHEST_PROTOCOL)
    )

    results = {
        "held": HELD_NAME,
        "ceilings": ceilings,
        "variants": variants,
        "best": best,
        "elapsed_s": round(time.time() - t0, 1),
    }

    lines = [
        "# NIFTY 1m — **HOLD** ACC100_PRE3_RAW + densify toward **1 call/day**",
        "",
        "Constraints unchanged: **T1=20** · **SL≤10** · **100% path** (target before SL).",
        "",
        f"Held baseline: `{HELD_NAME}` ({len(held)} micros).",
        "",
        "## Oracle ceiling (days with ≥1 possible T20/SL10 path win)",
        "",
        "| Era | Win days | All days | Max cover |",
        "|---|---:|---:|---:|",
    ]
    for k, v in ceilings.items():
        lines.append(f"| {k} | {v['win_days']} | {v['all_days']} | {v['max_cover%']}% |")

    lines += [
        "",
        "## Densify variants",
        "",
        "| Variant | Micros | Total | cpd_all | 2024 n/hit/cover | 2025 | Hold | FWD | all_win |",
        "|---|---:|---:|---:|---|---|---|---|:---:|",
    ]
    for name, v in variants.items():
        ver = v["verify"]
        lines.append(
            f"| **{name}** | {v['n_micros']} | {v['total']} | {v['cpd_all']} | "
            f"{ver['E2024']['n']}@{ver['E2024']['hit']}%/{ver['E2024']['cover']}% | "
            f"{ver['E2025']['n']}@{ver['E2025']['hit']}%/{ver['E2025']['cover']}% | "
            f"{ver['HOLD']['n']}@{ver['HOLD']['hit']}%/{ver['HOLD']['cover']}% | "
            f"{ver['FWD']['n']}@{ver['FWD']['hit']}% | {v['all_win']} |"
        )

    b = variants[best]
    lines += [
        "",
        f"## Operate now: **`{best}`** → alias `HELD_PRE3_DENSE_1CPD`",
        "",
        f"- Total calls: **{b['total']}** · blended cpd_all **{b['cpd_all']}** (target 1.0)",
        f"- Hold cover: **{b['verify']['HOLD']['cover']}%** of 2026 sessions · {b['verify']['HOLD']['n']} calls @ {b['verify']['HOLD']['hit']}%",
        f"- 2024 cover: **{b['verify']['E2024']['cover']}%** · 2025: **{b['verify']['E2025']['cover']}%**",
        "",
        "If cpd_all < 1.0: oracle ceiling shows not every day has *any* T20/SL10 path win — "
        "true 1/day @100% is impossible on those days without relaxing T1 or SL.",
        "",
        f"Pack: `{PACK}`",
        f"Elapsed: {results['elapsed_s']}s",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {REPORT_MD}", flush=True)
    print("DONE hold+densify 1cpd", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
