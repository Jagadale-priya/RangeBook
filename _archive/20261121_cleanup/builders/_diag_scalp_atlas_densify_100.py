"""Hold ACC100_MULTIYEAR_ATLAS; densify more calls/cover at same 100% path (fast)."""
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
from _diag_scalp_fail3_t20_sl10 import SL10_STYLES, SL_MAX, T1, enrich_prior3, flag_sl10  # noqa: E402
from _diag_scalp_held_pre3_densify_1cpd import eval_book, stats  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep, keys_deep  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_wf100_2021"
REPORT_MD = OUT / "NIFTY_1M_SCALP_ATLAS_DENSE_100.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_ATLAS_DENSE_100.json"
HELD = PACK / "ACC100_MULTIYEAR_ATLAS_micros.pkl"
YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
GAP = 1


def keys_a_only(e):
    """Compact densify keys only (fast index)."""
    return [
        ("A1", e["primary"], e["decision"], e.get("pre3_UD"), e.get("close_ok"), e.get("adv_bin"), e.get("body_bin"), e.get("hm_bin"), e.get("vix_regime")),
        ("A2", e["family"], e["decision"], e.get("struct2"), e.get("close_ok"), e.get("slbin"), e.get("clock"), e.get("adv_bin")),
        ("A3", e["primary"], e["decision"], e.get("day_pos_bin"), e.get("rsi_bin"), e.get("close_ok"), e.get("adv_bin"), e.get("hm_bin")),
        ("A4", e["family"], e["decision"], e.get("pre3_UD"), e.get("struct2"), e.get("body_bin"), e.get("vix_regime")),
        ("A5", e["primary"], e["decision"], e.get("very_strong"), e.get("close_ok"), e.get("adv_bin"), e.get("slot")),
        ("A6", e["primary"], e["decision"], e.get("pre3_stack"), e.get("close_zone"), e.get("adv_bin"), e.get("body_bin"), e.get("hm30")),
        ("A7", e["family"], e["decision"], e.get("stair"), e.get("close_ok"), e.get("pre_regime"), e.get("slbin"), e.get("hm_bin")),
    ]


def keys_combined(e):
    """Held deep fingerprints + densify A-keys."""
    return list(keys_deep(e)) + keys_a_only(e)


def index_year(events, key_fn):
    """(k,st)->(all_ok, win_events). Only index SL10-valid."""
    bucket = defaultdict(list)
    for e in events:
        keys = e.get("_keys") or set(key_fn(e))
        for st in SL10_STYLES:
            sl = e.get(f"_sl10_{st}", 99)
            if not (4 <= sl <= SL_MAX):
                continue
            ok = bool(e.get(f"_ok10_{st}"))
            for k in keys:
                bucket[(k, st)].append((e, ok, sl))
    clean = {}
    dirty = set()
    for id_, rows in bucket.items():
        if any(not ok for _, ok, _ in rows):
            dirty.add(id_)
        else:
            wins = [e for e, ok, _ in rows if ok]
            if wins:
                clean[id_] = wins
    return clean, dirty


def merge_clean(year_clean, year_dirty, min_years, min_total):
    """Keys clean in every year they appear; never dirty; enough years/fires."""
    # any dirty anywhere → reject
    dirty = set()
    for y in YEARS:
        dirty |= year_dirty[y]
    # count years + collect events
    counts = defaultdict(int)
    totals = defaultdict(int)
    evs = defaultdict(list)
    for y in YEARS:
        for id_, wins in year_clean[y].items():
            if id_ in dirty:
                continue
            counts[id_] += 1
            totals[id_] += len(wins)
            for e in wins:
                e["_year"] = y
                evs[id_].append(e)
    cells = []
    for id_, n_y in counts.items():
        if n_y < min_years or totals[id_] < min_total:
            continue
        k, st = id_
        all_ev = evs[id_]
        for e in all_ev:
            e[f"_ok_{st}"] = True
            e[f"_sl_{st}"] = e[f"_sl10_{st}"]
            e["_sl"] = e[f"_sl10_{st}"]
            e["_win"] = True
        early = [e for e in all_ev if e["_year"] <= 2023]
        late = [e for e in all_ev if e["_year"] >= 2024]
        if not early:
            early = all_ev[:1]
        if not late:
            late = all_ev[-1:]
        cells.append(
            {
                "k": k,
                "st": st,
                "cal_calls": early,
                "l3m_calls": late,
                "cal_n": len(early),
                "l3m_n": len(late),
                "total_n": len(all_ev),
                "years_hit": n_y,
                "days": {e["day"] for e in all_ev},
                "avg_sl": sum(e[f"_sl10_{st}"] for e in all_ev) / len(all_ev),
            }
        )
    cells.sort(key=lambda r: (-r["years_hit"], -len(r["days"]), -r["total_n"], r["avg_sl"]))
    return cells


def greedy_calls(cells, gap=GAP):
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

    for r in cells:
        kept = take(r["cal_calls"] + r["l3m_calls"])
        if len(kept) < 1:
            continue
        chosen.append({**r, "kept": kept})
        for e in kept:
            used.add((e["day"], e["mins"]))
    return chosen


def verify(by_year, micros, key_fn, h, l, c):
    out = {}
    total = 0
    aw = True
    all_days = 0
    cov_days = 0
    sl_sum = 0
    for y in YEARS:
        xs = by_year[y]
        for e in xs:
            e["_keys"] = set(key_fn(e))
        nd = len({e["day"] for e in xs})
        calls = eval_book(xs, micros, key_fn, h, l, c, GAP)
        st = stats(calls, nd)
        out[y] = st
        total += st["n"]
        aw = aw and st["all_win"]
        all_days += nd
        cov_days += st["days"]
        sl_sum += st["avg_sl"] * st["n"]
    return {
        "by_year": out,
        "total": total,
        "all_win": aw,
        "cover_all": round(100.0 * cov_days / max(all_days, 1), 1),
        "cpd_all": round(total / max(all_days, 1), 3),
        "avg_sl": round(sl_sum / max(total, 1), 2) if total else 0,
    }


def main() -> int:
    print("=" * 60, flush=True)
    print("HOLD ATLAS + densify @100% (fast clean-index)", flush=True)
    print("=" * 60, flush=True)
    t0 = time.time()
    held = pickle.loads(HELD.read_bytes())
    print(f"held={len(held)}", flush=True)

    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp("2021-01-01", tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    vix = vixmod.load_vix()

    print("[1] enrich…", flush=True)
    by_year = {}
    for y in YEARS:
        xs = pickle.load(next(PACK.glob(f"events_{y}-01-01_*.pkl")).open("rb"))
        fwdmod.enrich_evt(xs, h, l, c, o)
        enrich_structure(xs, h, l, c, o, vix)
        enrich_prior3(xs, h, l, c, o)
        flag_sl10(xs, h, l, c)
        enrich_deep(xs, h, l, c, o, df)
        by_year[y] = xs
        print(f"  {y}", flush=True)

    # baseline
    for y in YEARS:
        for e in by_year[y]:
            e["_keys"] = set(keys_deep(e))
    base_v = verify(by_year, held, keys_deep, h, l, c)
    print(f"[2] HELD total={base_v['total']} cover={base_v['cover_all']}% all_win={base_v['all_win']}", flush=True)

    print("[3] build A-key clean indexes (fast)…", flush=True)
    for y in YEARS:
        for e in by_year[y]:
            e["_keys"] = set(keys_a_only(e))
    year_clean, year_dirty = {}, {}
    for y in YEARS:
        year_clean[y], year_dirty[y] = index_year(by_year[y], keys_a_only)
        print(f"  {y} clean_keys={len(year_clean[y])} dirty={len(year_dirty[y])}", flush=True)

    variants = {}
    for name, min_years, min_total in [
        ("DENSE_Y4", 4, 2),
        ("DENSE_Y3", 3, 2),
        ("DENSE_Y2", 2, 2),
        ("DENSE_Y3_m1", 3, 1),
        ("DENSE_Y2_m1", 2, 1),
        ("DENSE_Y4_m3", 4, 3),
    ]:
        print(f"\n#### {name}", flush=True)
        cells = merge_clean(year_clean, year_dirty, min_years, min_total)
        print(f"  A-cells={len(cells)}", flush=True)
        chosen_a = greedy_calls(cells, gap=GAP)
        # union with held atlas micros (same accuracy family)
        chosen = [{"k": m["k"], "st": m["st"]} for m in held] + [
            {"k": r["k"], "st": r["st"]} for r in chosen_a
        ]
        # dedupe
        seen = set()
        uniq = []
        for m in chosen:
            id_ = (str(m["k"]), m["st"])
            if id_ in seen:
                continue
            seen.add(id_)
            uniq.append(m)
        chosen = uniq
        ver = verify(by_year, chosen, keys_combined, h, l, c)
        print(
            f"  micros={len(chosen)} total={ver['total']} cover={ver['cover_all']}% "
            f"cpd={ver['cpd_all']} all_win={ver['all_win']} avg_sl={ver['avg_sl']}",
            flush=True,
        )
        for y in YEARS:
            st = ver["by_year"][y]
            print(f"    {y}: {st['n']}@{st['hit']}% days={st['days']}", flush=True)
        variants[name] = {"n_micros": len(chosen), "min_years": min_years, "min_total": min_total, "verify": ver}
        (PACK / f"{name}_micros.pkl").write_bytes(
            pickle.dumps(chosen, protocol=pickle.HIGHEST_PROTOCOL)
        )

    aw = [n for n in variants if variants[n]["verify"]["all_win"]]
    best = max(aw, key=lambda n: (variants[n]["verify"]["cover_all"], variants[n]["verify"]["total"])) if aw else max(variants, key=lambda n: variants[n]["verify"]["cover_all"])
    print(f"\nBEST={best}", flush=True)
    (PACK / "HELD_ATLAS_DENSE_100_micros.pkl").write_bytes((PACK / f"{best}_micros.pkl").read_bytes())
    (PACK / "HELD_ATLAS_BASE_100_micros.pkl").write_bytes(pickle.dumps(held, protocol=pickle.HIGHEST_PROTOCOL))

    results = {"baseline": base_v, "variants": variants, "best": best, "elapsed_s": round(time.time() - t0, 1)}
    b = variants[best]["verify"]
    lines = [
        "# HOLD ATLAS + densify @ **100% path** (more calls)",
        "",
        f"T1=**{T1}** · SL≤**{SL_MAX}** · 2021→2026",
        "",
        f"Baseline held: **{base_v['total']}** calls · cover **{base_v['cover_all']}%** · all_win={base_v['all_win']}",
        "",
        "| Variant | Micros | Calls | Day cover | cpd | Avg SL | all_win |",
        "|---|---:|---:|---:|---:|---:|:---:|",
        f"| HELD_BASE | {len(held)} | {base_v['total']} | {base_v['cover_all']}% | {base_v['cpd_all']} | {base_v['avg_sl']} | {base_v['all_win']} |",
    ]
    for name, v in variants.items():
        ver = v["verify"]
        lines.append(
            f"| **{name}** | {v['n_micros']} | {ver['total']} | {ver['cover_all']}% | {ver['cpd_all']} | {ver['avg_sl']} | {ver['all_win']} |"
        )
    lines += [
        "",
        f"## Operate: **`{best}`** → `HELD_ATLAS_DENSE_100_micros.pkl`",
        "",
        f"- Calls **{b['total']}** (from {base_v['total']}) · cover **{b['cover_all']}%** (from {base_v['cover_all']}%)",
        f"- cpd_all **{b['cpd_all']}** · avg SL **{b['avg_sl']}** · T1 **{T1}** · **all_win={b['all_win']}**",
        "",
        "| Year | n | hit | days |",
        "|---:|---:|---:|---:|",
    ]
    for y in YEARS:
        st = b["by_year"][y]
        lines.append(f"| {y} | {st['n']} | {st['hit']}% | {st['days']} |")
    lines += ["", f"Pack: `{PACK}`", f"Elapsed: {results['elapsed_s']}s", ""]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {REPORT_MD}", flush=True)
    print("DONE atlas densify", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
