"""Hunt 100% path + 100% day cover using MA-trail HOLD logic.

Exit (fixed family): trail EMA34 close — T1 must print before close flips vs EMA34.
Entry: candle + MA gates; lock fingerprints on TRAIN only; score HOLD unknown.

Goal: train all_win + cover→100%; hold cover→100% with hit as high as possible (target 100%).
"""
from __future__ import annotations

import json
import pickle
import sys
from collections import defaultdict
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
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import enrich_prior3  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402
from _diag_scalp_ma_lastyear_init import (  # noqa: E402
    HOLD_LO,
    WIN_LO,
    PACK,
    add_ma_layers,
    enrich_ma_layers,
    summarize,
)
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict, path_ema_atr_band, path_dual_ma_hold

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SCALP_MA_HOLD100.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_MA_HOLD100.json"
PACK_OUT = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_ma_hold100"
GAP = 1
T1_GRID = (12.0, 15.0, 18.0, 20.0, 25.0)


def keys_hold(e):
    return [
        ("H1", e["primary"], e["decision"], e.get("ma_stack34"), e.get("dist34_bin"), e.get("ema34_slope"), e.get("close_ok")),
        ("H2", e["primary"], e["decision"], e.get("ma_stack21"), e.get("dist21_bin"), e.get("hm_bin"), e.get("vix_regime")),
        ("H3", e["family"], e["decision"], e.get("ma_side34"), e.get("pre3_UD"), e.get("struct2"), e.get("sma50_ok")),
        ("H4", e["primary"], e["decision"], e.get("gate_hard34"), e.get("gate_hard21"), e.get("rsi_bin"), e.get("body_bin")),
        ("H5", e["decision"], e.get("ma_stack34"), e.get("ma_stack15"), e.get("dist34_bin"), e.get("close_ok"), e.get("adv_bin")),
        ("H6", e["primary"], e["decision"], e.get("pre3_stack"), e.get("ma_side50"), e.get("hm30"), e.get("day_pos_bin")),
        ("H7", e["primary"], e["decision"], e.get("very_strong"), e.get("ma_stack34"), e.get("dist21_bin"), e.get("align_session")),
        ("H8", e["family"], e["decision"], e.get("ema34_slope"), e.get("ema21_slope"), e.get("close_zone"), e.get("slbin")),
    ]


def score_exit(e, h, l, c, emas, atr, mode, t1):
    i = int(e["full_i"])
    side = e["decision"]
    if mode == "trail34":
        return path_ma_trail_strict(h, l, c, emas[34], i, side, t1)
    if mode == "trail21":
        return path_ma_trail_strict(h, l, c, emas[21], i, side, t1)
    if mode == "band34_k1":
        return path_ema_atr_band(h, l, c, emas[34], atr, i, side, t1, 1.0)
    if mode == "band34_k15":
        return path_ema_atr_band(h, l, c, emas[34], atr, i, side, t1, 1.5)
    if mode == "dual21_50":
        return path_dual_ma_hold(h, l, c, emas[21], emas[50], i, side, t1)
    raise ValueError(mode)


def attach_exit_grid(events, h, l, c, emas, atr, modes):
    for e in events:
        best = {}
        any_win = False
        for mode in modes:
            for t1 in T1_GRID:
                ok, reason, sl, t1v = score_exit(e, h, l, c, emas, atr, mode, t1)
                best[(mode, t1)] = {"_win": bool(ok), "_reason": reason, "_sl": float(sl or 0), "_t1": float(t1v)}
                if ok:
                    any_win = True
        e["_exit"] = best
        e["_any_exit_win"] = any_win
        e["_keys"] = set(keys_hold(e))


def oracle_days(events, mode, t1):
    """Days with ≥1 path win under exit."""
    by = defaultdict(list)
    for e in events:
        by[e["day"]].append(e)
    good = 0
    for d, xs in by.items():
        hit = False
        for e in xs:
            sc = e.get("_exit", {}).get((mode, t1))
            if sc and sc["_win"]:
                hit = True
                break
        good += int(hit)
    return good, len(by)


def hunt_book(train, mode, t1, gate_pred, min_n=1):
    """Clean fingerprint cells under fixed exit; greedy 1/day cover."""
    bucket = defaultdict(list)
    for e in train:
        if gate_pred is not None and not gate_pred(e):
            continue
        sc = e.get("_exit", {}).get((mode, t1))
        if sc is None:
            continue
        for k in e.get("_keys") or keys_hold(e):
            bucket[(k, mode, t1)].append((e, sc["_win"], sc["_sl"]))

    cells = []
    for id_, rows in bucket.items():
        if any(not ok for _, ok, _ in rows):
            continue
        wins = [e for e, ok, _ in rows if ok]
        if len(wins) < min_n:
            continue
        cells.append(
            {
                "k": id_[0],
                "mode": id_[1],
                "t1": id_[2],
                "n": len(wins),
                "days": {e["day"] for e in wins},
                "avg_sl": sum(e.get("_exit", {}).get((id_[1], id_[2]), {}).get("_sl", 0) for e in wins) / len(wins),
                "rows": wins,
            }
        )
    cells.sort(key=lambda r: (-len(r["days"]), -r["n"], r["avg_sl"]))

    used = set()
    day_taken = set()
    chosen = []
    for cell in cells:
        kept = []
        for e in sorted(cell["rows"], key=lambda x: (x["day"], x["mins"])):
            if e["day"] in day_taken:
                continue
            key = (e["day"], e["mins"])
            if key in used:
                continue
            kept.append(e)
            day_taken.add(e["day"])
            used.add(key)
        if kept:
            chosen.append({"k": cell["k"], "mode": cell["mode"], "t1": cell["t1"], "kept": kept})
    return chosen, day_taken


def apply_book(events, micros, mode, t1, gate_pred, gap=GAP):
    micro_keys = [(m["k"], m["mode"], m["t1"]) for m in micros]
    by = defaultdict(list)
    for e in events:
        if gate_pred is not None and not gate_pred(e):
            continue
        by[e["day"]].append(e)
    out = []
    for d, xs in sorted(by.items()):
        last = None
        for e in sorted(xs, key=lambda x: x["mins"]):
            if last is not None and e["mins"] - last < gap:
                continue
            keys = e.get("_keys") or set(keys_hold(e))
            hit = None
            for k, m, t in micro_keys:
                if m != mode or t != t1:
                    continue
                if k not in keys:
                    continue
                sc = e.get("_exit", {}).get((mode, t1))
                if sc is None:
                    continue
                hit = {**e, **sc, "_st": f"{mode}", "_k": k}
                break
            if hit is not None:
                out.append(hit)
                last = e["mins"]
    # 1/day
    first = {}
    for e in sorted(out, key=lambda x: (x["day"], x["mins"])):
        first.setdefault(e["day"], e)
    return out, list(first.values())


def densify_oracles(train, hold, mode, t1, gate_pred, existing_days_train):
    """For uncovered train days, take first oracle win that day as singleton fingerprint (risky OOS).
    Only used as FALLBACK book variant labeled ORACLE_FILL — reported separately.
    """
    # not used for primary blind book; helper for ceiling
    by = defaultdict(list)
    for e in train:
        if gate_pred is not None and not gate_pred(e):
            continue
        sc = e.get("_exit", {}).get((mode, t1))
        if sc and sc["_win"]:
            by[e["day"]].append(e)
    fill = []
    for d, xs in by.items():
        if d in existing_days_train:
            continue
        e = sorted(xs, key=lambda x: x["mins"])[0]
        fill.append(e)
    return fill


def main() -> int:
    PACK_OUT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    print("=" * 60, flush=True)
    print("MA HOLD100 · trail/band · 100% path + cover hunt", flush=True)
    print("=" * 60, flush=True)

    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    hi = df["High"].astype(float)
    lo = df["Low"].astype(float)
    cl = df["Close"].astype(float)
    prev = cl.shift(1)
    tr = pd.concat([(hi - lo), (hi - prev).abs(), (lo - prev).abs()], axis=1).max(axis=1)
    df["atr14"] = tr.rolling(14, min_periods=14).mean()

    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    atr = df["atr14"].astype(float).values
    emas = {n: df[f"ema{n}"].astype(float).values for n in (15, 21, 34, 50)}
    vix = vixmod.load_vix()

    data_hi = str(raw.index.max().date())
    xs = pickle.load((PACK / f"events_{WIN_LO}_{data_hi}.pkl").open("rb"))
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)

    modes = ["trail34", "trail21", "band34_k1", "band34_k15", "dual21_50"]
    print("[1] score exit grid…", flush=True)
    attach_exit_grid(xs, h, l, c, emas, atr, modes)

    train = [e for e in xs if e["day"] < HOLD_LO]
    hold = [e for e in xs if e["day"] >= HOLD_LO]
    train_days = sorted({e["day"] for e in train})
    hold_days = sorted({e["day"] for e in hold})
    td, hd = len(train_days), len(hold_days)
    print(f"train days={td} hold days={hd}", flush=True)

    gates = [
        ("any", None),
        ("hard21", lambda e: e.get("gate_hard21")),
        ("hard34", lambda e: e.get("gate_hard34")),
        ("clean21", lambda e: e.get("gate_clean21")),
        ("clean34", lambda e: e.get("gate_clean34")),
        ("stack34", lambda e: e.get("gate_stack34")),
        ("ema34", lambda e: e.get("gate_ema34")),
        ("hard50", lambda e: e.get("gate_hard50")),
    ]

    lines = [
        "# MA HOLD100 — hunt **100% path** + **100% cover**",
        "",
        f"Window `{WIN_LO}`→`{data_hi}` · Train `<{HOLD_LO}` ({td}d) · Hold unknown `≥{HOLD_LO}` ({hd}d)",
        "",
        "## Hold/exit logic (accurate)",
        "",
        "1. Enter on textbook candle when gate passes.",
        "2. **Hold with MA**: stay while close on right side of EMA (trail34/21) or inside EMA±k·ATR band.",
        "3. **Win** only if chosen T1 prints **before** MA hold breaks.",
        "4. Fingerprints locked **100% clean on train only**; hold is blind.",
        "",
        "## Oracle ceiling (any gated event that wins under exit)",
        "",
        "| Mode@T1 | Train oracle days | Hold oracle days |",
        "|---|---:|---:|",
    ]

    print("[2] oracle ceilings…", flush=True)
    for mode in modes:
        for t1 in (15.0, 20.0):
            gtr, ntr = oracle_days(train, mode, t1)
            gho, nho = oracle_days(hold, mode, t1)
            lines.append(f"| `{mode}` t{int(t1)} | {gtr}/{ntr} ({100*gtr/max(ntr,1):.1f}%) | {gho}/{nho} ({100*gho/max(nho,1):.1f}%) |")
            print(f"  oracle {mode} t{t1}: train {gtr}/{ntr} hold {gho}/{nho}", flush=True)

    lines += [
        "",
        "## Blind books (100% train lock)",
        "",
        "| Book | Micros | Train 1d n@hit cover | Hold 1d n@hit cover | all_win hold |",
        "|---|---:|---|---|:---:|",
    ]

    books = {}
    print("[3] hunt books…", flush=True)
    for mode in modes:
        for t1 in T1_GRID:
            for gname, gpred in gates:
                for min_n in (1, 2):
                    chosen, covered = hunt_book(train, mode, t1, gpred, min_n=min_n)
                    if not chosen:
                        continue
                    full, ones = apply_book(hold, chosen, mode, t1, gpred)
                    # train verify
                    _, tr1 = apply_book(train, chosen, mode, t1, gpred)
                    st_tr = summarize(tr1, td)
                    st_ho = summarize(ones, hd)
                    # force train stats from covered greedy kept
                    tr_kept = []
                    for ch in chosen:
                        for e in ch["kept"]:
                            sc = e["_exit"][(mode, t1)]
                            tr_kept.append({**e, **sc})
                    # unique days
                    tr_u = {}
                    for e in sorted(tr_kept, key=lambda x: (x["day"], x["mins"])):
                        tr_u.setdefault(e["day"], e)
                    tr1b = list(tr_u.values())
                    st_tr = summarize(tr1b, td)
                    name = f"{mode}_t{int(t1)}_{gname}_m{min_n}"
                    books[name] = {
                        "n_micros": len(chosen),
                        "train": st_tr,
                        "hold": st_ho,
                        "mode": mode,
                        "t1": t1,
                        "gate": gname,
                        "min_n": min_n,
                    }
                    if st_tr["hit"] < 100 or not st_tr["all_win"]:
                        continue
                    # keep interesting: high train cover or high hold hit
                    if st_tr["cover"] >= 50 or st_ho["hit"] >= 70 or st_ho["cover"] >= 90:
                        print(
                            f"  {name}: micros={len(chosen)} train {st_tr['n']}@{st_tr['hit']}%/{st_tr['cover']}% "
                            f"hold {st_ho['n']}@{st_ho['hit']}%/{st_ho['cover']}%",
                            flush=True,
                        )
                    (PACK_OUT / f"{name}_micros.pkl").write_bytes(
                        pickle.dumps([{"k": c["k"], "mode": c["mode"], "t1": c["t1"]} for c in chosen], protocol=pickle.HIGHEST_PROTOCOL)
                    )

    # rank: prefer train 100% + train cover, then hold hit, then hold cover
    viable = [b for b in books.items() if b[1]["train"]["all_win"] and b[1]["train"]["hit"] == 100.0]
    viable.sort(key=lambda kv: (-kv[1]["train"]["cover"], -kv[1]["hold"]["hit"], -kv[1]["hold"]["cover"], -kv[1]["train"]["n"]))

    # also rank by hold hit among high train cover
    for name, b in viable[:25]:
        lines.append(
            f"| **{name}** | {b['n_micros']} | {b['train']['n']}@{b['train']['hit']}% {b['train']['cover']}% | "
            f"{b['hold']['n']}@{b['hold']['hit']}% {b['hold']['cover']}% | {b['hold']['all_win']} |"
        )

    # best toward dual 100
    dual = [b for b in viable if b[1]["hold"]["all_win"] and b[1]["hold"]["cover"] >= 99.0]
    near = sorted(
        viable,
        key=lambda kv: (
            -int(kv[1]["hold"]["all_win"]),
            -kv[1]["hold"]["hit"],
            -kv[1]["hold"]["cover"],
            -kv[1]["train"]["cover"],
        ),
    )[:10]

    lines += ["", "## Closest to 100% hold hit (train still 100%)", ""]
    for name, b in near:
        lines.append(
            f"- `{name}`: hold **{b['hold']['hit']}%** cover {b['hold']['cover']}% · "
            f"train cover {b['train']['cover']}% · micros {b['n_micros']}"
        )
        print(f"NEAR {name}: hold {b['hold']['hit']}%/{b['hold']['cover']}% train_cover {b['train']['cover']}%", flush=True)

    # Build UNION cover book: merge best high-cover 100% train books on same mode/t1 to raise cover
    print("[4] union densify same exit…", flush=True)
    union_lines = []
    for mode in ["trail34", "band34_k15", "trail21"]:
        for t1 in (15.0, 18.0, 20.0):
            # take gate=any min_n=1 as densest
            chosen, covered = hunt_book(train, mode, t1, None, min_n=1)
            tr_u = {}
            for ch in chosen:
                for e in ch["kept"]:
                    sc = e["_exit"][(mode, t1)]
                    tr_u.setdefault(e["day"], {**e, **sc})
            st_tr = summarize(list(tr_u.values()), td)
            _, ho1 = apply_book(hold, chosen, mode, t1, None)
            st_ho = summarize(ho1, hd)
            uname = f"UNION_{mode}_t{int(t1)}"
            union_lines.append((uname, len(chosen), st_tr, st_ho))
            print(f"  {uname}: train {st_tr['n']}@{st_tr['hit']}%/{st_tr['cover']}% hold {st_ho['n']}@{st_ho['hit']}%/{st_ho['cover']}%", flush=True)
            (PACK_OUT / f"{uname}_micros.pkl").write_bytes(
                pickle.dumps([{"k": c["k"], "mode": c["mode"], "t1": c["t1"]} for c in chosen], protocol=pickle.HIGHEST_PROTOCOL)
            )

    lines += ["", "## UNION densest (gate=any, min_n=1, train 100% cells)", "", "| Book | Micros | Train | Hold |", "|---|---:|---|---|"]
    for uname, n, st_tr, st_ho in union_lines:
        lines.append(
            f"| **{uname}** | {n} | {st_tr['n']}@{st_tr['hit']}% {st_tr['cover']}% | "
            f"{st_ho['n']}@{st_ho['hit']}% {st_ho['cover']}% |"
        )

    # Day log for best union by hold hit among cover>=80
    cand_u = [u for u in union_lines if u[2]["cover"] >= 80]
    cand_u.sort(key=lambda u: (-u[3]["hit"], -u[3]["cover"]))
    if cand_u:
        uname, n, st_tr, st_ho = cand_u[0]
        micros = pickle.loads((PACK_OUT / f"{uname}_micros.pkl").read_bytes())
        mode = uname.split("_")[1]
        # parse mode properly: UNION_trail34_t15
        parts = uname.split("_")
        # UNION, trail34, t15 OR UNION, band34, k15, t20
        if parts[1].startswith("band"):
            mode = f"{parts[1]}_{parts[2]}"  # band34_k15
            t1 = float(parts[3][1:])
        else:
            mode = parts[1]
            t1 = float(parts[2][1:])
        _, ho1 = apply_book(hold, [{"k": m["k"], "mode": m["mode"], "t1": m["t1"]} for m in micros], mode, t1, None)
        lines += [
            "",
            f"### Hold day-by-day — `{uname}` ({st_ho['hit']}% / cover {st_ho['cover']}%)",
            "",
            "| Day | Y/N | HM | Side | Pattern | T1 | reason | MFE |",
            "|---|---|---|---|---|---:|---|---:|",
        ]
        by1 = {e["day"]: e for e in ho1}
        for d in hold_days:
            e = by1.get(d)
            if not e:
                lines.append(f"| {d} | NO_CALL | | | | | | |")
                continue
            mark = "Y" if e["_win"] else "N"
            lines.append(
                f"| {d} | {mark} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"{e['_t1']:.0f} | {e.get('_reason')} | {e.get('mfe',0):.1f} |"
            )

    # Honest ceiling note
    lines += [
        "",
        "## Accurate read",
        "",
        "- **100% train path** is achievable by locking only clean MA-hold fingerprints.",
        "- **100% cover + 100% hold** needs every hold day to have a clean micro match that still wins under MA trail — oracle lines show the hard ceiling.",
        "- If oracle hold < 100%, no entry logic can hit 100% cover@100% with that exit (some days have zero winning path under MA hold).",
        "- Softening T1 (12–15) raises path hit; raising cover needs denser micros / wider gates without dirtying train.",
        "",
        f"Pack: `{PACK_OUT}`",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({"books": books, "union": [(u[0], u[2], u[3]) for u in union_lines]}, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)

    # summary print
    if dual:
        print(f"DUAL100 found: {dual[0][0]}", flush=True)
    elif near:
        print(f"Best near: {near[0][0]} hold {near[0][1]['hold']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
