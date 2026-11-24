"""Analyze candle structure + prior-2 H/L + VIX → accurate high-count tags (research)."""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
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
import research_nifty_1m_chart_only_100 as co  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_acc100_all"
PACK_OUT = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_struct_vix"
REPORT_MD = OUT / "NIFTY_1M_SCALP_STRUCT_VIX_ANALYZE.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_STRUCT_VIX_ANALYZE.json"

EV_CACHE = PACK / "events_all_2024-01-02_2026-11-16.pkl"
HIST_LO = "2023-11-01"

# Analyze = 2024+2025 · Hold = 2026A+B · FWD = Nov week
ANALYZE_ERAS = ("E2024", "E2025")
HOLD_ERAS = ("E2026A", "E2026B")
FWD_ERAS = ("FWD",)

STRONG_PATS = {
    "bull_engulf",
    "bear_engulf",
    "bull_kicker",
    "bear_kicker",
    "morning_star",
    "evening_star",
    "three_outside_up",
    "three_outside_dn",
    "marubozu_bull",
    "marubozu_bear",
    "belt_bull",
    "belt_bear",
    "piercing",
    "dark_cloud",
}


def enrich_structure(events, h, l, c, o, vix_prior):
    """Attach close location, prior-2 H/L structure, VIX (no look-ahead)."""
    for e in events:
        i = int(e["full_i"])
        if i < 2:
            continue
        hi, lo, cl, op = float(h[i]), float(l[i]), float(c[i]), float(o[i])
        p1h, p1l, p1c, p1o = float(h[i - 1]), float(l[i - 1]), float(c[i - 1]), float(o[i - 1])
        p2h, p2l, p2c, p2o = float(h[i - 2]), float(l[i - 2]), float(c[i - 2]), float(o[i - 2])
        rng = max(hi - lo, 0.5)
        close_pos = (cl - lo) / rng
        upper = hi - max(op, cl)
        lower = min(op, cl) - lo
        side = e["decision"]

        # where close sits
        if close_pos >= 0.75:
            close_zone = "near_high"
        elif close_pos <= 0.25:
            close_zone = "near_low"
        else:
            close_zone = "mid"

        # side-aligned close (BUY wants near_high, SELL near_low)
        close_ok = (side == "BUY" and close_zone == "near_high") or (
            side == "SELL" and close_zone == "near_low"
        )

        # prior-2 structure vs signal
        swing_hi = max(p1h, p2h)
        swing_lo = min(p1l, p2l)
        broke_swing_hi = hi > swing_hi or cl > swing_hi
        broke_swing_lo = lo < swing_lo or cl < swing_lo
        if side == "BUY":
            struct2 = (
                "break_hi"
                if broke_swing_hi
                else ("hold_above_lo" if lo >= swing_lo else ("cut_lo" if lo < swing_lo else "inside"))
            )
            if broke_swing_hi and lo >= p1l:
                struct2 = "break_hi_hold"
        else:
            struct2 = (
                "break_lo"
                if broke_swing_lo
                else ("hold_under_hi" if hi <= swing_hi else ("cut_hi" if hi > swing_hi else "inside"))
            )
            if broke_swing_lo and hi <= p1h:
                struct2 = "break_lo_hold"

        # last 2 candle directions
        d1 = "up" if p1c > p1o else ("dn" if p1c < p1o else "doji")
        d2 = "up" if p2c > p2o else ("dn" if p2c < p2o else "doji")
        stack = f"{d2}_{d1}"

        # HH/HL vs prior
        if p1h > p2h and p1l > p2l:
            stair = "HH_HL"
        elif p1h < p2h and p1l < p2l:
            stair = "LH_LL"
        elif p1h > p2h and p1l < p2l:
            stair = "outside"
        elif p1h < p2h and p1l > p2l:
            stair = "inside"
        else:
            stair = "mixed"

        # engulf prior body
        engulf = abs(cl - op) > abs(p1c - p1o) and (
            (side == "BUY" and cl > p1h) or (side == "SELL" and cl < p1l) or (side == "BUY" and op <= p1c and cl >= p1o) or (side == "SELL" and op >= p1c and cl <= p1o)
        )

        # distances to prior highs/lows (structure map)
        if side == "BUY":
            dist_p1_lo = cl - p1l
            dist_p2_lo = cl - p2l
            dist_swing = cl - swing_lo
            room_up = swing_hi - cl
        else:
            dist_p1_lo = p1h - cl  # reuse name as dist to adverse prior extreme
            dist_p2_lo = p2h - cl
            dist_swing = swing_hi - cl
            room_up = cl - swing_lo

        vix = float(vix_prior.get(e["day"], np.nan))
        vr = vixmod.vix_regime(vix)

        body = float(e["body_frac"])
        adv = (upper if side == "BUY" else lower) / rng
        strong = (
            e["primary"] in STRONG_PATS
            and body >= 0.55
            and close_ok
            and adv <= 0.30
        )
        very_strong = strong and body >= 0.70 and adv <= 0.15 and e.get("align_session", 0) == 1

        e.update(
            {
                "close_pos": round(close_pos, 3),
                "close_zone": close_zone,
                "close_ok": int(close_ok),
                "adv_wick": round(adv, 3),
                "adv_bin": "adv_lo" if adv < 0.15 else ("adv_mid" if adv < 0.30 else "adv_hi"),
                "body_bin": "b70+" if body >= 0.70 else ("b55+" if body >= 0.55 else ("b45+" if body >= 0.45 else "b<45")),
                "struct2": struct2,
                "stack2": stack,
                "stair": stair,
                "engulf_p1": int(bool(engulf)),
                "broke_swing_fav": int(broke_swing_hi if side == "BUY" else broke_swing_lo),
                "p1_range": round(p1h - p1l, 2),
                "p2_range": round(p2h - p2l, 2),
                "swing_range": round(swing_hi - swing_lo, 2),
                "dist_p1": round(dist_p1_lo, 2),
                "dist_p2": round(dist_p2_lo, 2),
                "dist_swing": round(dist_swing, 2),
                "room_opp": round(room_up, 2),
                "slbin": (
                    "sl4-8"
                    if e["sl_prev"] <= 8
                    else ("sl8-12" if e["sl_prev"] <= 12 else ("sl12-16" if e["sl_prev"] <= 16 else "sl16-20"))
                ),
                "vix": vix,
                "vix_regime": vr,
                "strong": int(strong),
                "very_strong": int(very_strong),
                "pat_class": "strong_pat" if e["primary"] in STRONG_PATS else "weak_pat",
                "family": next(
                    (fn for fn, ps in fwdmod.FAMILIES.items() if e["primary"] in ps),
                    "other",
                ),
            }
        )


def path_win(e, t1, style="prev"):
    key = f"{style}_t{int(t1)}"
    if e.get(key) == "win":
        return True
    if e.get(key) in ("sl", "exp", "both", "bad_sl"):
        return False
    return None


def tag_of(e, parts):
    vals = []
    for p in parts:
        vals.append(f"{p}={e.get(p)}")
    return "|".join(vals)


def score_tag(events, pred, t1, style, gap=8):
    xs = [e for e in events if pred(e) and 4 <= e["sl_prev"] <= 20]
    xs = fwdmod.apply_gap(xs, gap)
    wins = 0
    n = 0
    for e in xs:
        w = path_win(e, t1, style)
        if w is None:
            continue
        n += 1
        wins += int(w)
    if n == 0:
        return {"n": 0, "wins": 0, "hit": 0.0, "cpd": 0.0, "days": 0}
    days = len({e["day"] for e in xs})
    return {
        "n": n,
        "wins": wins,
        "hit": round(100.0 * wins / n, 2),
        "days": days,
        "cpd": round(n / max(days, 1), 2),
    }


def main() -> int:
    print("=" * 60, flush=True)
    print("Analyze structure + prior2 H/L + VIX → accurate tags", flush=True)
    print("=" * 60, flush=True)
    PACK_OUT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    blob = pickle.load(EV_CACHE.open("rb"))
    era_events = blob["era_events"]
    print(f"eras={[ (k, len(v)) for k,v in era_events.items() ]}", flush=True)

    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(HIST_LO, tz="Asia/Kolkata")]
    print("[1] textbook+rsi…", flush=True)
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values

    print("[2] VIX prior-day…", flush=True)
    vix_prior = vixmod.load_vix()

    print("[3] enrich structure…", flush=True)
    for name, xs in era_events.items():
        enrich_structure(xs, h, l, c, o, vix_prior)
        print(f"  {name} enriched={len(xs)}", flush=True)

    analyze = [e for er in ANALYZE_ERAS for e in era_events[er]]
    hold = [e for er in HOLD_ERAS for e in era_events[er]]
    fwd = [e for er in FWD_ERAS for e in era_events[er]]
    print(f"analyze={len(analyze)} hold={len(hold)} fwd={len(fwd)}", flush=True)

    # --- Feature lift tables (path prev @ T10) ---
    feature_dims = [
        "primary",
        "family",
        "decision",
        "close_zone",
        "close_ok",
        "struct2",
        "stack2",
        "stair",
        "engulf_p1",
        "broke_swing_fav",
        "adv_bin",
        "body_bin",
        "vix_regime",
        "strong",
        "very_strong",
        "pat_class",
        "pre_regime",
        "clock",
        "align_session",
        "slbin",
    ]

    lift = {}
    for t1 in (10.0, 15.0, 20.0):
        lift[t1] = {}
        base_sc = score_tag(analyze, lambda e: True, t1, "prev")
        lift[t1]["_BASE_"] = base_sc
        print(f"\nT{int(t1)} BASE analyze hit={base_sc['hit']}% n={base_sc['n']}", flush=True)
        for dim in feature_dims:
            rows = []
            vals = sorted({e.get(dim) for e in analyze if e.get(dim) is not None})
            for v in vals:
                sc = score_tag(analyze, lambda e, d=dim, vv=v: e.get(d) == vv, t1, "prev")
                if sc["n"] < 80:
                    continue
                rows.append({"value": v, **sc, "lift": round(sc["hit"] - base_sc["hit"], 2)})
            rows.sort(key=lambda r: (-r["hit"], -r["n"]))
            lift[t1][dim] = rows[:12]
            if rows:
                top = rows[0]
                print(
                    f"  best {dim}: {top['value']} hit={top['hit']}% n={top['n']} lift={top['lift']}",
                    flush=True,
                )

    # --- Combinatorial accurate tags (high n + high hit) ---
    # Building blocks with positive lift
    combos_specs = [
        ("close_ok", "struct2", "vix_regime"),
        ("close_ok", "adv_bin", "body_bin"),
        ("family", "close_ok", "vix_regime"),
        ("primary", "close_ok", "struct2"),
        ("strong", "vix_regime", "clock"),
        ("very_strong", "vix_regime", "slbin"),
        ("pat_class", "struct2", "adv_bin"),
        ("family", "stair", "close_ok"),
        ("decision", "struct2", "vix_regime"),
        ("primary", "adv_bin", "vix_regime"),
        ("family", "body_bin", "close_ok"),
        ("engulf_p1", "close_ok", "vix_regime"),
        ("broke_swing_fav", "close_ok", "adv_bin"),
        ("stack2", "close_ok", "vix_regime"),
        ("very_strong", "struct2", "vix_regime"),
        ("strong", "struct2", "slbin"),
        ("primary", "close_zone", "stair"),
        ("family", "pre_regime", "close_ok"),
    ]

    tag_results = {}
    for t1 in (10.0, 15.0, 20.0):
        for style in ("prev", "swing2", "sig"):
            key = f"T{int(t1)}_{style}"
            print(f"\n#### Hunt tags {key}", flush=True)
            candidates = []
            # single strong filters
            for dim in ("very_strong", "strong", "close_ok", "struct2", "vix_regime", "primary", "family"):
                for v in sorted({e.get(dim) for e in analyze}):
                    if v is None:
                        continue
                    if dim in ("very_strong", "strong", "close_ok") and int(v) == 0:
                        continue
                    tag = f"{dim}={v}"
                    pred = lambda e, d=dim, vv=v: e.get(d) == vv
                    a = score_tag(analyze, pred, t1, style)
                    if a["n"] < 40:
                        continue
                    hld = score_tag(hold, pred, t1, style)
                    fw = score_tag(fwd, pred, t1, style)
                    candidates.append(
                        {
                            "tag": tag,
                            "kind": "single",
                            "analyze": a,
                            "hold": hld,
                            "fwd": fw,
                            "dims": (dim,),
                        }
                    )

            # multi-feature tags
            for dims in combos_specs:
                # gather value tuples present enough times
                counts = Counter()
                for e in analyze:
                    if not (4 <= e["sl_prev"] <= 20):
                        continue
                    tup = tuple(e.get(d) for d in dims)
                    if any(x is None for x in tup):
                        continue
                    counts[tup] += 1
                for tup, cnt in counts.most_common(80):
                    if cnt < 40:
                        continue
                    # skip weak flags
                    skip = False
                    for d, v in zip(dims, tup):
                        if d in ("very_strong", "strong", "close_ok", "engulf_p1", "broke_swing_fav") and int(v) == 0:
                            skip = True
                            break
                    if skip:
                        continue
                    tag = "|".join(f"{d}={v}" for d, v in zip(dims, tup))

                    def pred(e, ds=dims, vs=tup):
                        return all(e.get(d) == v for d, v in zip(ds, vs))

                    a = score_tag(analyze, pred, t1, style)
                    if a["n"] < 25:
                        continue
                    hld = score_tag(hold, pred, t1, style)
                    fw = score_tag(fwd, pred, t1, style)
                    candidates.append(
                        {
                            "tag": tag,
                            "kind": "combo",
                            "analyze": a,
                            "hold": hld,
                            "fwd": fw,
                            "dims": dims,
                        }
                    )

            # rank: require analyze hit high + decent n; prefer hold also strong
            def rank_key(r):
                a, hld = r["analyze"], r["hold"]
                # prioritize hold hit when n>=10, else analyze
                hold_score = hld["hit"] if hld["n"] >= 10 else a["hit"] * 0.5
                return (hold_score, a["hit"], a["n"], hld["n"])

            # buckets
            acc_high = [r for r in candidates if r["analyze"]["hit"] >= 70 and r["analyze"]["n"] >= 30]
            acc_bal = [
                r
                for r in candidates
                if r["analyze"]["hit"] >= 60
                and r["analyze"]["n"] >= 80
                and r["hold"]["n"] >= 15
                and r["hold"]["hit"] >= 55
            ]
            acc100ish = [r for r in candidates if r["analyze"]["hit"] >= 85 and r["analyze"]["n"] >= 15]
            acc_high.sort(key=rank_key, reverse=True)
            acc_bal.sort(key=rank_key, reverse=True)
            acc100ish.sort(key=rank_key, reverse=True)

            print(f"  candidates={len(candidates)} high70={len(acc_high)} bal={len(acc_bal)} ~85+={len(acc100ish)}", flush=True)
            for label, rows in (("BAL", acc_bal[:8]), ("HIGH70", acc_high[:5]), ("NEAR100", acc100ish[:5])):
                for r in rows:
                    print(
                        f"  {label} {r['tag'][:90]} A={r['analyze']['n']}@{r['analyze']['hit']}% "
                        f"H={r['hold']['n']}@{r['hold']['hit']}% F={r['fwd']['n']}@{r['fwd']['hit']}%",
                        flush=True,
                    )

            tag_results[key] = {
                "n_candidates": len(candidates),
                "balanced": acc_bal[:20],
                "high70": acc_high[:20],
                "near100": acc100ish[:20],
            }

    # --- Structure insight summary (what wins look like) ---
    insights = []
    for t1 in (10.0, 15.0, 20.0):
        wins = [e for e in analyze if path_win(e, t1, "prev") is True and 4 <= e["sl_prev"] <= 20]
        loss = [e for e in analyze if path_win(e, t1, "prev") is False and 4 <= e["sl_prev"] <= 20]
        # sample caps
        wins_g = fwdmod.apply_gap(wins, 8)[:5000]
        loss_g = fwdmod.apply_gap(loss, 8)[:5000]

        def rate(xs, fn):
            return round(100.0 * sum(1 for e in xs if fn(e)) / max(len(xs), 1), 1)

        insights.append(
            {
                "t1": t1,
                "n_win": len(wins_g),
                "n_loss": len(loss_g),
                "win_close_ok": rate(wins_g, lambda e: e.get("close_ok") == 1),
                "loss_close_ok": rate(loss_g, lambda e: e.get("close_ok") == 1),
                "win_strong": rate(wins_g, lambda e: e.get("strong") == 1),
                "loss_strong": rate(loss_g, lambda e: e.get("strong") == 1),
                "win_very_strong": rate(wins_g, lambda e: e.get("very_strong") == 1),
                "loss_very_strong": rate(loss_g, lambda e: e.get("very_strong") == 1),
                "win_adv_lo": rate(wins_g, lambda e: e.get("adv_bin") == "adv_lo"),
                "loss_adv_lo": rate(loss_g, lambda e: e.get("adv_bin") == "adv_lo"),
                "win_vix": dict(Counter(e.get("vix_regime") for e in wins_g).most_common(5)),
                "loss_vix": dict(Counter(e.get("vix_regime") for e in loss_g).most_common(5)),
                "win_struct2": dict(Counter(e.get("struct2") for e in wins_g).most_common(5)),
                "loss_struct2": dict(Counter(e.get("struct2") for e in loss_g).most_common(5)),
                "win_stair": dict(Counter(e.get("stair") for e in wins_g).most_common(5)),
                "win_family": dict(Counter(e.get("family") for e in wins_g).most_common(6)),
            }
        )
        print(f"insight T{int(t1)} win_close_ok={insights[-1]['win_close_ok']} vs loss={insights[-1]['loss_close_ok']}", flush=True)

    results = {
        "analyze_eras": ANALYZE_ERAS,
        "hold_eras": HOLD_ERAS,
        "lift": lift,
        "tags": tag_results,
        "insights": insights,
        "elapsed_s": round(time.time() - t0, 1),
    }

    # markdown
    lines = [
        "# NIFTY 1m — structure + prior-2 H/L + VIX **analysis**",
        "",
        "Research only. Path win = **target before prev/sig/swing2 SL**.",
        "",
        f"- Analyze: **2024+2025** · Hold: **2026 Jan–Nov6** · FWD: **Nov9–16**",
        f"- Features: close location, prior-2 H/L break/hold, stair (HH/HL), stack, engulf, VIX prior-day, strong-pattern flag",
        "",
        "## What wins look like (analyze)",
        "",
        "| T1 | Win close_ok% | Loss close_ok% | Win strong% | Loss strong% | Win very_strong% | Win adv_lo% |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for ins in insights:
        lines.append(
            f"| {int(ins['t1'])} | {ins['win_close_ok']} | {ins['loss_close_ok']} | "
            f"{ins['win_strong']} | {ins['loss_strong']} | {ins['win_very_strong']} | {ins['win_adv_lo']} |"
        )

    lines += ["", "### Win structure mix (T10)", ""]
    ins0 = insights[0]
    lines.append(f"- struct2 wins: `{ins0['win_struct2']}`")
    lines.append(f"- struct2 loss: `{ins0['loss_struct2']}`")
    lines.append(f"- VIX wins: `{ins0['win_vix']}` · loss: `{ins0['loss_vix']}`")
    lines.append(f"- family wins: `{ins0['win_family']}`")
    lines.append(f"- stair wins: `{ins0['win_stair']}`")

    lines += [
        "",
        "## Feature lift (analyze · prev SL · T10) — top values",
        "",
    ]
    for dim, rows in (lift.get(10.0) or {}).items():
        if dim == "_BASE_" or not rows:
            continue
        top3 = ", ".join(f"{r['value']} {r['hit']}% n={r['n']} (Δ{r['lift']})" for r in rows[:3])
        lines.append(f"- **{dim}**: {top3}")

    lines += [
        "",
        "## Accurate tags with volume (hold must also work when n≥15)",
        "",
    ]
    for key in ("T10_prev", "T15_prev", "T20_prev", "T10_swing2", "T15_swing2"):
        block = tag_results.get(key) or {}
        lines.append(f"### {key}")
        lines.append("")
        lines.append("| Rank | Tag | Analyze | Hold | FWD |")
        lines.append("|---:|---|---|---|---|")
        for i, r in enumerate((block.get("balanced") or [])[:12], 1):
            a, hld, fw = r["analyze"], r["hold"], r["fwd"]
            lines.append(
                f"| {i} | `{r['tag']}` | {a['n']}@{a['hit']}% | {hld['n']}@{hld['hit']}% | {fw['n']}@{fw['hit']}% |"
            )
        if not block.get("balanced"):
            lines.append("| — | _no balanced tag_ | | | |")
        lines.append("")
        near = block.get("near100") or []
        if near:
            lines.append("Near-100% (analyze ≥85%, n≥15):")
            lines.append("")
            for r in near[:8]:
                a, hld = r["analyze"], r["hold"]
                lines.append(
                    f"- `{r['tag']}` · A {a['n']}@{a['hit']}% · H {hld['n']}@{hld['hit']}%"
                )
            lines.append("")

    lines += [
        "## Next",
        "",
        "- Promote tags that stay ≥60% on **hold 2026** with n≥15 and decent analyze volume.",
        "- Very-strong + VIX + structure tags are the accuracy ladder; widen only after hold confirms.",
        f"- Pack: `{PACK_OUT}`",
        f"- Elapsed: {results['elapsed_s']}s",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    # shrink json — drop huge raw candidates
    slim = {
        "insights": insights,
        "lift_t10": {k: v[:8] if isinstance(v, list) else v for k, v in (lift.get(10.0) or {}).items()},
        "tags": {
            k: {
                "balanced": v.get("balanced", [])[:15],
                "near100": v.get("near100", [])[:10],
                "high70": v.get("high70", [])[:10],
            }
            for k, v in tag_results.items()
        },
        "elapsed_s": results["elapsed_s"],
    }
    REPORT_JSON.write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {REPORT_MD}", flush=True)
    print("DONE structure+VIX analyze", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
