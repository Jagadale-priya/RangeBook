"""Try MA (EMA9/21/50) filters + keys for T20/SL<=10 path accuracy (blind 2026)."""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import Counter, defaultdict
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
from _diag_scalp_fail3_t20_sl10 import (  # noqa: E402
    SL10_STYLES,
    SL_MAX,
    T1,
    enrich_prior3,
    flag_sl10,
    path_ok_sl10,
)
from _diag_scalp_held_pre3_densify_1cpd import eval_book, stats  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep, keys_deep, index_by_key, cell_clean, greedy_1cpd  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK_IN = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_wf100_2021"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_ma_try"
REPORT_MD = OUT / "NIFTY_1M_SCALP_MA_TRY_T20_SL10.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_MA_TRY_T20_SL10.json"
GAP = 1
YEARS = [2021, 2022, 2023, 2024, 2025, 2026]


def add_ma_columns(df: pd.DataFrame) -> pd.DataFrame:
    c = df["Close"].astype(float)
    df = df.copy()
    df["ema9"] = c.ewm(span=9, adjust=False).mean()
    df["ema21"] = c.ewm(span=21, adjust=False).mean()
    df["ema50"] = c.ewm(span=50, adjust=False).mean()
    df["sma20"] = c.rolling(20, min_periods=20).mean()
    return df


def enrich_ma(events, df):
    """Attach MA regime at signal bar (no look-ahead: use same bar close vs MA)."""
    ema9 = df["ema9"].astype(float).values
    ema21 = df["ema21"].astype(float).values
    ema50 = df["ema50"].astype(float).values
    sma20 = df["sma20"].astype(float).values
    close = df["Close"].astype(float).values

    for e in events:
        i = int(e["full_i"])
        if i < 50 or not np.isfinite(ema50[i]) or not np.isfinite(sma20[i]):
            e["ma_stack"] = "unk"
            e["ma_align"] = 0
            e["ma_side"] = "unk"
            e["px_vs_ema21"] = "unk"
            e["ema_slope"] = "unk"
            e["dist_ema21_atr"] = 0.0
            e["ma_gate"] = False
            continue
        cl = float(close[i])
        e9, e21, e50, s20 = float(ema9[i]), float(ema21[i]), float(ema50[i]), float(sma20[i])
        atr = max(float(e.get("atr") or 8.0), 3.0)
        side = e["decision"]

        # stack
        if e9 > e21 > e50:
            stack = "bull"
        elif e9 < e21 < e50:
            stack = "bear"
        else:
            stack = "mix"

        above21 = cl >= e21
        above50 = cl >= e50
        if side == "BUY":
            align = int(above21 and e9 >= e21)
            ma_side = "with" if stack == "bull" else ("against" if stack == "bear" else "mix")
        else:
            align = int((not above21) and e9 <= e21)
            ma_side = "with" if stack == "bear" else ("against" if stack == "bull" else "mix")

        # slope of ema21 over last 5 bars
        if i >= 5 and np.isfinite(ema21[i - 5]):
            slope = e21 - float(ema21[i - 5])
            slope_bin = "up" if slope > 0.5 * atr * 0.1 else ("dn" if slope < -0.5 * atr * 0.1 else "flat")
        else:
            slope_bin = "unk"

        dist = (cl - e21) / atr
        if side == "SELL":
            dist = -dist
        dist_bin = "near" if abs(dist) < 0.35 else ("ext" if abs(dist) > 1.0 else "mid")

        e["ma_stack"] = stack
        e["ma_align"] = align
        e["ma_side"] = ma_side
        e["px_vs_ema21"] = "above" if above21 else "below"
        e["px_vs_ema50"] = "above" if above50 else "below"
        e["ema_slope"] = slope_bin
        e["dist_ema21"] = round(dist, 2)
        e["dist_ema21_bin"] = dist_bin
        e["sma20_side"] = "above" if cl >= s20 else "below"
        # practical gates
        e["ma_gate_soft"] = bool(align == 1)
        e["ma_gate_stack"] = bool(ma_side == "with")
        e["ma_gate_hard"] = bool(align == 1 and ma_side == "with" and slope_bin == ("up" if side == "BUY" else "dn"))
        e["ma_gate_pullback"] = bool(
            align == 1
            and dist_bin == "near"
            and ((side == "BUY" and stack in ("bull", "mix")) or (side == "SELL" and stack in ("bear", "mix")))
        )


def keys_ma(e):
    keys = list(keys_deep(e))
    keys += [
        ("MA1", e["primary"], e["decision"], e.get("ma_stack"), e.get("ma_align"), e.get("ema_slope"), e.get("dist_ema21_bin")),
        ("MA2", e["family"], e["decision"], e.get("ma_side"), e.get("px_vs_ema21"), e.get("close_ok"), e.get("adv_bin")),
        ("MA3", e["primary"], e["decision"], e.get("ma_gate_hard"), e.get("pre3_UD"), e.get("vix_regime"), e.get("hm_bin")),
        ("MA4", e["decision"], e.get("ma_stack"), e.get("ema_slope"), e.get("struct2"), e.get("close_ok"), e.get("body_bin")),
        ("MA5", e["primary"], e["decision"], e.get("ma_gate_pullback"), e.get("px_vs_ema50"), e.get("rsi_bin"), e.get("slbin")),
    ]
    return keys


def path_any_sl10(e):
    for st in SL10_STYLES:
        if e.get(f"_ok10_{st}") and 4 <= e.get(f"_sl10_{st}", 99) <= SL_MAX:
            return True
    return False


def filter_lift(events, pred, gap=GAP):
    """Best SL10 style chronologically among gated events — hit rate."""
    xs = []
    for e in events:
        if pred is not None and not pred(e):
            continue
        best = None
        for st in SL10_STYLES:
            sl = e.get(f"_sl10_{st}", 99)
            if not (4 <= sl <= SL_MAX):
                continue
            ok = bool(e.get(f"_ok10_{st}"))
            cand = (st, sl, ok)
            if best is None or (ok and not best[2]) or (ok == best[2] and sl < best[1]):
                best = cand
        if best is None:
            continue
        st, sl, ok = best
        xs.append({**e, "_st": st, "_sl": sl, "_win": ok})
    xs = fwdmod.apply_gap(xs, gap)
    if not xs:
        return {"n": 0, "hit": 0.0, "wins": 0}
    w = sum(1 for e in xs if e["_win"])
    return {"n": len(xs), "wins": w, "hit": round(100.0 * w / len(xs), 2)}


def build_blind_book(train_events, key_fn, gate_pred, min_n=2):
    train = [e for e in train_events if gate_pred is None or gate_pred(e)]
    for e in train:
        e["_keys"] = set(key_fn(e))
    # split 2024/2025 by year tag
    cal = [e for e in train if e.get("_year") == 2024]
    l3m = [e for e in train if e.get("_year") == 2025]
    if not cal or not l3m:
        # fallback split by day
        days = sorted({e["day"] for e in train})
        mid = days[len(days) // 2] if days else ""
        cal = [e for e in train if e["day"] <= mid]
        l3m = [e for e in train if e["day"] > mid]
    cal_b = index_by_key(cal, key_fn)
    l3m_b = index_by_key(l3m, key_fn)
    cand = set()
    for b in (cal_b, l3m_b):
        for (k, st), rows in b.items():
            if any(ok for _, ok, _ in rows):
                cand.add((k, st))
    cells = []
    for k, st in cand:
        ok_c, n_c, c_ev = cell_clean(cal_b, k, st)
        ok_l, n_l, l_ev = cell_clean(l3m_b, k, st)
        if not (ok_c and ok_l):
            continue
        if n_c + n_l < min_n or n_c < 1:
            continue
        for e in c_ev + l_ev:
            e[f"_ok_{st}"] = True
            e[f"_sl_{st}"] = e[f"_sl10_{st}"]
            e["_sl"] = e[f"_sl10_{st}"]
            e["_win"] = True
            e["_era_tag"] = "cal" if e in c_ev else "l3m"
        cells.append(
            {
                "k": k,
                "st": st,
                "cal_calls": c_ev,
                "l3m_calls": l_ev,
                "hold_calls": [],
                "fwd_calls": [],
                "cal_n": n_c,
                "l3m_n": n_l,
                "hold_n": 0,
                "fwd_n": 0,
                "total_n": n_c + n_l,
                "days": {e["day"] for e in c_ev + l_ev},
                "avg_sl": sum(e[f"_sl10_{st}"] for e in c_ev + l_ev) / max(n_c + n_l, 1),
            }
        )
    cells.sort(key=lambda r: (-r["total_n"], r["avg_sl"]))
    chosen, _ = greedy_1cpd(cells, gap=GAP)
    return chosen


def score_book(events, micros, key_fn, gate_pred, h, l, c):
    xs = [e for e in events if gate_pred is None or gate_pred(e)]
    for e in xs:
        e["_keys"] = set(key_fn(e))
    calls = eval_book(xs, micros, key_fn, h, l, c, GAP)
    nd = len({e["day"] for e in events})
    st = stats(calls, nd)
    # 1/day
    first = {}
    for e in sorted(calls, key=lambda x: (x["day"], x["mins"])):
        first.setdefault(e["day"], e)
    ones = list(first.values())
    one = {
        "n": len(ones),
        "hit": round(100.0 * sum(1 for e in ones if e["_win"]) / max(len(ones), 1), 2) if ones else 0,
        "cover": round(100.0 * len(ones) / max(nd, 1), 1),
        "all_win": all(e["_win"] for e in ones) if ones else True,
    }
    return {"full": st, "one": one, "n_days": nd}


def main() -> int:
    print("=" * 60, flush=True)
    print("TRY MA filters/keys · T20 SL<=10 · blind 2026", flush=True)
    print("=" * 60, flush=True)
    PACK.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp("2021-01-01", tz="Asia/Kolkata")]
    print("[1] textbook+rsi+MA…", flush=True)
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_columns(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    vix = vixmod.load_vix()

    print("[2] load yearly events + enrich…", flush=True)
    by_year = {}
    for y in YEARS:
        path = next(PACK_IN.glob(f"events_{y}-01-01_*.pkl"))
        xs = pickle.load(path.open("rb"))
        for e in xs:
            e["_year"] = y
        by_year[y] = xs
        print(f"  {y}={len(xs)}", flush=True)

    all_train = []
    for y, xs in by_year.items():
        fwdmod.enrich_evt(xs, h, l, c, o)
        enrich_structure(xs, h, l, c, o, vix)
        enrich_prior3(xs, h, l, c, o)
        flag_sl10(xs, h, l, c)
        enrich_deep(xs, h, l, c, o, df)
        enrich_ma(xs, df)
        print(f"  enriched {y}", flush=True)
        if y in (2024, 2025):
            all_train.extend(xs)
    unk = by_year[2026]

    # --- Filter lift (no micros): MA gates alone ---
    print("[3] MA gate lift (analyze 24-25 / unknown 26)…", flush=True)
    gates = {
        "raw": None,
        "ma_align": lambda e: e.get("ma_gate_soft"),
        "ma_stack_with": lambda e: e.get("ma_gate_stack"),
        "ma_hard": lambda e: e.get("ma_gate_hard"),
        "ma_pullback": lambda e: e.get("ma_gate_pullback"),
        "ma_hard_close_ok": lambda e: e.get("ma_gate_hard") and e.get("close_ok") == 1,
        "ma_pull_b70_advlo": lambda e: (
            e.get("ma_gate_pullback") and e.get("body_bin") == "b70+" and e.get("adv_bin") == "adv_lo"
        ),
    }
    lift = {}
    for name, pred in gates.items():
        a = filter_lift(all_train, pred)
        u = filter_lift(unk, pred)
        lift[name] = {"train": a, "unk2026": u}
        print(f"  {name}: train {a['n']}@{a['hit']}% · unk {u['n']}@{u['hit']}%", flush=True)

    # --- Blind micro books with MA ---
    print("[4] blind MA micro books (lock 24-25 → test 26)…", flush=True)
    books = {}
    variants = [
        ("BLIND_DEEP_noMA", keys_deep, None),
        ("BLIND_MA_keys", keys_ma, None),
        ("BLIND_MA_align", keys_ma, lambda e: e.get("ma_gate_soft")),
        ("BLIND_MA_hard", keys_ma, lambda e: e.get("ma_gate_hard")),
        ("BLIND_MA_pull", keys_ma, lambda e: e.get("ma_gate_pullback")),
        ("BLIND_MA_hard_close", keys_ma, lambda e: e.get("ma_gate_hard") and e.get("close_ok") == 1),
    ]
    for name, kfn, gate in variants:
        print(f"  building {name}…", flush=True)
        chosen = build_blind_book(all_train, kfn, gate, min_n=2)
        # score train + unk with same gate
        tr = score_book(all_train, chosen, kfn, gate, h, l, c)
        un = score_book(unk, chosen, kfn, gate, h, l, c)
        print(
            f"    micros={len(chosen)} train {tr['full']['n']}@{tr['full']['hit']}% · "
            f"unk {un['full']['n']}@{un['full']['hit']}% all_win={un['full']['all_win']} · "
            f"1/day {un['one']['n']} cover={un['one']['cover']}% hit={un['one']['hit']}%",
            flush=True,
        )
        books[name] = {"n_micros": len(chosen), "train": tr, "unk2026": un}
        (PACK / f"{name}_micros.pkl").write_bytes(
            pickle.dumps([{"k": r["k"], "st": r["st"]} for r in chosen], protocol=pickle.HIGHEST_PROTOCOL)
        )

    # Walk-forward 2026 with MA_hard using train 2021-2025
    print("[5] WF2026 with MA_hard (train 2021-25)…", flush=True)
    train_wf = []
    for y in range(2021, 2026):
        train_wf.extend(by_year[y])
    for e in train_wf + unk:
        e["_keys"] = set(keys_ma(e))
    gate = lambda e: e.get("ma_gate_hard")
    # zero-loss across years using gated events only
    # reuse build_blind-like but multi-year: treat 2021-23 as cal, 2024-25 as l3m
    cal = [e for e in train_wf if e["_year"] <= 2023 and gate(e)]
    l3m = [e for e in train_wf if e["_year"] >= 2024 and gate(e)]
    for e in cal + l3m:
        e["_keys"] = set(keys_ma(e))
    cal_b = index_by_key(cal, keys_ma)
    l3m_b = index_by_key(l3m, keys_ma)
    cand = set(list(cal_b.keys()) + list(l3m_b.keys()))
    cells = []
    for k, st in cand:
        ok_c, n_c, c_ev = cell_clean(cal_b, k, st)
        ok_l, n_l, l_ev = cell_clean(l3m_b, k, st)
        if not (ok_c and ok_l):
            continue
        if n_c + n_l < 2 or n_c < 1:
            continue
        for e in c_ev + l_ev:
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
                "hold_calls": [],
                "fwd_calls": [],
                "cal_n": n_c,
                "l3m_n": n_l,
                "hold_n": 0,
                "fwd_n": 0,
                "total_n": n_c + n_l,
                "days": {e["day"] for e in c_ev + l_ev},
                "avg_sl": sum(e[f"_sl10_{st}"] for e in c_ev + l_ev) / max(n_c + n_l, 1),
            }
        )
    chosen_wf, _ = greedy_1cpd(cells, gap=GAP)
    wf_score = score_book(unk, chosen_wf, keys_ma, gate, h, l, c)
    print(
        f"  WF_MA_hard micros={len(chosen_wf)} unk {wf_score['full']['n']}@{wf_score['full']['hit']}% "
        f"1/day hit={wf_score['one']['hit']}% cover={wf_score['one']['cover']}%",
        flush=True,
    )
    books["WF2026_MA_hard"] = {"n_micros": len(chosen_wf), "unk2026": wf_score}
    (PACK / "WF2026_MA_hard_micros.pkl").write_bytes(
        pickle.dumps([{"k": r["k"], "st": r["st"]} for r in chosen_wf], protocol=pickle.HIGHEST_PROTOCOL)
    )

    # pick best unk hit among blind books with n>=20
    def rank(name):
        b = books[name]
        u = b["unk2026"]["full"]
        return (u["hit"], u["n"], b["unk2026"]["one"]["hit"])

    blind_names = [n for n in books if n.startswith("BLIND")]
    best = max(blind_names, key=rank)

    results = {
        "lift": lift,
        "books": books,
        "best_blind": best,
        "elapsed_s": round(time.time() - t0, 1),
    }

    lines = [
        "# NIFTY 1m — **try MA** (EMA9/21/50) for T20 / SL≤10 path",
        "",
        "Blind protocol: lock on **2024–2025 only** → score **unknown 2026**.",
        "",
        "## MA gate lift (any SL≤10 style)",
        "",
        "| Gate | Train n@hit | Unk2026 n@hit |",
        "|---|---|---|",
    ]
    for name, row in lift.items():
        lines.append(f"| `{name}` | {row['train']['n']}@{row['train']['hit']}% | {row['unk2026']['n']}@{row['unk2026']['hit']}% |")

    lines += [
        "",
        "## Blind micro books",
        "",
        "| Book | Micros | Train hit | Unk full n@hit | Unk 1/day hit | Unk cover |",
        "|---|---:|---:|---|---:|---:|",
    ]
    for name, b in books.items():
        if name.startswith("WF"):
            continue
        tr, un = b["train"]["full"], b["unk2026"]
        lines.append(
            f"| **{name}** | {b['n_micros']} | {tr['n']}@{tr['hit']}% | "
            f"{un['full']['n']}@{un['full']['hit']}% | {un['one']['hit']}% | {un['one']['cover']}% |"
        )

    wf = books["WF2026_MA_hard"]["unk2026"]
    lines += [
        "",
        f"## WF2026 MA_hard (train 2021–25)",
        "",
        f"- micros={books['WF2026_MA_hard']['n_micros']} · unk **{wf['full']['n']}@{wf['full']['hit']}%** · "
        f"1/day **{wf['one']['hit']}%** cover {wf['one']['cover']}%",
        "",
        f"**Best blind by unk hit:** `{best}` "
        f"({books[best]['unk2026']['full']['hit']}% on {books[best]['unk2026']['full']['n']} calls).",
        "",
        "MA helps only if unk hit rises vs `BLIND_DEEP_noMA`. 100% OOS still requires rare multi-year atlas logic.",
        "",
        f"Pack: `{PACK}`",
        f"Elapsed: {results['elapsed_s']}s",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {REPORT_MD}", flush=True)
    print(f"BEST_BLIND={best}", flush=True)
    print("DONE MA try", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
