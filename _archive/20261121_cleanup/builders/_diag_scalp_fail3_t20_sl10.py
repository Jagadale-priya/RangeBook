"""Why path calls fail: prior-3 candles + time/VIX; hunt 100% T1>15 SL<=10 max calls."""
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
import research_nifty_1m_chart_only_100 as co  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure, STRONG_PATS  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK_IN = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_acc100_all"
PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_t20_sl10_acc100"
REPORT_MD = OUT / "NIFTY_1M_SCALP_FAIL3_T20_SL10_ACC100.md"
REPORT_JSON = OUT / "NIFTY_1M_SCALP_FAIL3_T20_SL10_ACC100.json"
EV_CACHE = PACK_IN / "events_all_2024-01-02_2026-11-16.pkl"
HIST_LO = "2023-11-01"

ANALYZE_ERAS = ("E2024", "E2025")
HOLD_ERAS = ("E2026A", "E2026B")
FWD_ERAS = ("FWD",)

# SL styles that can stay ≤10
SL10_STYLES = ["prev", "sig", "min_ps", "cap8", "cap10", "p75", "p60"]
T1 = 20.0  # more than 15
SL_MAX = 10.0
GAP = 4


def enrich_prior3(events, h, l, c, o):
    """Add prior-3 candle shape/structure tags used to explain failures."""
    for e in events:
        i = int(e["full_i"])
        if i < 3:
            continue
        side = e["decision"]
        bars = []
        for k in range(3, 0, -1):  # p3, p2, p1
            j = i - k
            hj, lj, cj, oj = float(h[j]), float(l[j]), float(c[j]), float(o[j])
            rng = max(hj - lj, 0.5)
            body = abs(cj - oj) / rng
            dir_ = "up" if cj > oj else ("dn" if cj < oj else "doji")
            close_pos = (cj - lj) / rng
            bars.append(
                {
                    "dir": dir_,
                    "body": body,
                    "rng": rng,
                    "hi": hj,
                    "lo": lj,
                    "c": cj,
                    "o": oj,
                    "close_pos": close_pos,
                    "upper": (hj - max(oj, cj)) / rng,
                    "lower": (min(oj, cj) - lj) / rng,
                }
            )
        p3, p2, p1 = bars
        e["p3_dir"], e["p2_dir"], e["p1_dir"] = p3["dir"], p2["dir"], p1["dir"]
        e["pre3_stack"] = f"{p3['dir']}_{p2['dir']}_{p1['dir']}"

        # opposing pressure in prior 3 (against trade side)
        if side == "BUY":
            opp = sum(1 for b in bars if b["dir"] == "dn")
            favor = sum(1 for b in bars if b["dir"] == "up")
            # any prior bar with strong upper rejection
            rej = sum(1 for b in bars if b["upper"] >= 0.45)
            # prior lows rising?
            higher_lows = int(p1["lo"] > p2["lo"] > p3["lo"])
            lower_highs = int(p1["hi"] < p2["hi"] < p3["hi"])
            # broke below p3 low already before signal
            weak = int(min(p1["lo"], p2["lo"]) < p3["lo"])
        else:
            opp = sum(1 for b in bars if b["dir"] == "up")
            favor = sum(1 for b in bars if b["dir"] == "dn")
            rej = sum(1 for b in bars if b["lower"] >= 0.45)
            higher_lows = int(p1["lo"] > p2["lo"] > p3["lo"])
            lower_highs = int(p1["hi"] < p2["hi"] < p3["hi"])
            weak = int(max(p1["hi"], p2["hi"]) > p3["hi"])

        e["pre3_opp"] = opp  # 0-3 candles against side
        e["pre3_favor"] = favor
        e["pre3_rej"] = rej
        e["pre3_higher_lows"] = higher_lows
        e["pre3_lower_highs"] = lower_highs
        e["pre3_weak_struct"] = weak
        e["pre3_avg_body"] = round(sum(b["body"] for b in bars) / 3, 3)
        e["pre3_avg_rng"] = round(sum(b["rng"] for b in bars) / 3, 2)
        e["pre3_body_bin"] = (
            "pb70+" if e["pre3_avg_body"] >= 0.70 else ("pb55+" if e["pre3_avg_body"] >= 0.55 else "pb<55")
        )
        # chronos
        e["hm_bin"] = (
            "09"
            if e["mins"] < 600
            else (
                "10"
                if e["mins"] < 660
                else (
                    "11"
                    if e["mins"] < 720
                    else ("12" if e["mins"] < 780 else ("13" if e["mins"] < 840 else "14+"))
                )
            )
        )
        # fail-risk composite
        e["fail_risk"] = (
            (opp >= 2)
            or (rej >= 2)
            or (weak == 1 and favor == 0)
            or (e.get("adv_bin") == "adv_hi")
            or (e.get("close_ok", 0) == 0)
        )


def sl_of(e, st):
    return fwdmod.lesser(e, st)


def path_ok_sl10(e, h, l, c, st, t1=T1):
    sl = sl_of(e, st)
    if not (4.0 <= sl <= SL_MAX):
        return False, sl
    # use cached when style is prev/sig
    if st == "prev" and e.get("prev_t20") is not None:
        return e["prev_t20"] == "win", sl
    if st == "sig" and e.get("sig_t20") is not None:
        return e["sig_t20"] == "win", sl
    win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], float(sl), float(t1))
    return (win and out == "t1"), sl


def flag_sl10(events, h, l, c):
    for e in events:
        for st in SL10_STYLES:
            ok, sl = path_ok_sl10(e, h, l, c, st)
            e[f"_ok10_{st}"] = ok
            e[f"_sl10_{st}"] = sl


def diagnose_failures(events, h, l, c, label):
    """For each event take best available SL<=10 style; split win/loss; profile prior-3."""
    rows = []
    for e in events:
        best = None
        for st in SL10_STYLES:
            sl = e.get(f"_sl10_{st}", 99)
            if not (4 <= sl <= SL_MAX):
                continue
            ok = e.get(f"_ok10_{st}")
            # prefer styles that win; else first valid
            cand = (st, sl, bool(ok))
            if best is None:
                best = cand
            elif ok and not best[2]:
                best = cand
            elif ok == best[2] and sl < best[1]:
                best = cand
        if best is None:
            continue
        st, sl, ok = best
        rows.append({**e, "_st": st, "_sl": sl, "_win": ok})

    rows = fwdmod.apply_gap(rows, GAP)
    wins = [e for e in rows if e["_win"]]
    loss = [e for e in rows if not e["_win"]]

    def top(xs, key, n=8):
        return Counter(e.get(key) for e in xs).most_common(n)

    def rate(xs, fn):
        return round(100.0 * sum(1 for e in xs if fn(e)) / max(len(xs), 1), 1)

    diag = {
        "label": label,
        "n": len(rows),
        "n_win": len(wins),
        "n_loss": len(loss),
        "hit": round(100.0 * len(wins) / max(len(rows), 1), 2),
        "loss_mfe_ge_t1": sum(1 for e in loss if e.get("mfe", 0) >= T1),
        "loss_pre3_stack": top(loss, "pre3_stack"),
        "win_pre3_stack": top(wins, "pre3_stack"),
        "loss_pre3_opp": top(loss, "pre3_opp"),
        "win_pre3_opp": top(wins, "pre3_opp"),
        "loss_hm": top(loss, "hm_bin"),
        "win_hm": top(wins, "hm_bin"),
        "loss_vix": top(loss, "vix_regime"),
        "win_vix": top(wins, "vix_regime"),
        "loss_primary": top(loss, "primary"),
        "win_primary": top(wins, "primary"),
        "loss_struct2": top(loss, "struct2"),
        "win_struct2": top(wins, "struct2"),
        "loss_clock": top(loss, "clock"),
        "loss_fail_risk_pct": rate(loss, lambda e: e.get("fail_risk")),
        "win_fail_risk_pct": rate(wins, lambda e: e.get("fail_risk")),
        "loss_close_ok_pct": rate(loss, lambda e: e.get("close_ok") == 1),
        "win_close_ok_pct": rate(wins, lambda e: e.get("close_ok") == 1),
        "loss_opp_ge2_pct": rate(loss, lambda e: (e.get("pre3_opp") or 0) >= 2),
        "win_opp_ge2_pct": rate(wins, lambda e: (e.get("pre3_opp") or 0) >= 2),
        "loss_weak_pct": rate(loss, lambda e: e.get("pre3_weak_struct") == 1),
        "win_weak_pct": rate(wins, lambda e: e.get("pre3_weak_struct") == 1),
        "loss_rej_ge2_pct": rate(loss, lambda e: (e.get("pre3_rej") or 0) >= 2),
        "win_rej_ge2_pct": rate(wins, lambda e: (e.get("pre3_rej") or 0) >= 2),
        "loss_adv_hi_pct": rate(loss, lambda e: e.get("adv_bin") == "adv_hi"),
        "win_adv_hi_pct": rate(wins, lambda e: e.get("adv_bin") == "adv_hi"),
        "avg_mae_loss": round(sum(e["mae"] for e in loss) / max(len(loss), 1), 2),
        "avg_mfe_loss": round(sum(e["mfe"] for e in loss) / max(len(loss), 1), 2),
    }
    # relative lift of fail features
    fail_signals = []
    for name, lrate, wrate in [
        ("pre3_opp>=2", diag["loss_opp_ge2_pct"], diag["win_opp_ge2_pct"]),
        ("pre3_weak_struct", diag["loss_weak_pct"], diag["win_weak_pct"]),
        ("pre3_rej>=2", diag["loss_rej_ge2_pct"], diag["win_rej_ge2_pct"]),
        ("fail_risk", diag["loss_fail_risk_pct"], diag["win_fail_risk_pct"]),
        ("adv_hi", diag["loss_adv_hi_pct"], diag["win_adv_hi_pct"]),
        ("NOT close_ok", 100 - diag["loss_close_ok_pct"], 100 - diag["win_close_ok_pct"]),
    ]:
        fail_signals.append({"feature": name, "in_loss%": lrate, "in_win%": wrate, "delta": round(lrate - wrate, 1)})
    fail_signals.sort(key=lambda x: -x["delta"])
    diag["fail_signal_rank"] = fail_signals
    return diag, rows


def build_cells_sl10(cal, l3m, key_fn, h, l, c):
    """Cells that are 100% path under some SL10 style on cal+l3m."""
    cal_b, l3m_b = defaultdict(list), defaultdict(list)
    for e in cal:
        if 4 <= e["sl_prev"] <= 20:
            for k in key_fn(e):
                cal_b[k].append(e)
    for e in l3m:
        if 4 <= e["sl_prev"] <= 20:
            for k in key_fn(e):
                l3m_b[k].append(e)

    cells = []
    for st in SL10_STYLES:
        for k, ces in cal_b.items():
            cr = []
            for e in fwdmod.apply_gap(ces, GAP):
                sl = e.get(f"_sl10_{st}", 99)
                if 4 <= sl <= SL_MAX and e.get(f"_ok10_{st}"):
                    cr.append(e)
            cr = fwdmod.apply_gap(cr, GAP)
            if len(cr) < 2:
                continue
            tr = []
            for e in fwdmod.apply_gap(l3m_b.get(k, []), GAP):
                sl = e.get(f"_sl10_{st}", 99)
                if 4 <= sl <= SL_MAX and e.get(f"_ok10_{st}"):
                    tr.append(e)
            tr = fwdmod.apply_gap(tr, GAP)
            if len(tr) < 1:
                continue
            # anti-fail filters baked optionally later
            # alias for fwdmod.greedy which reads _ok_{st} / _sl_{st}
            for e in cr + tr:
                e[f"_ok_{st}"] = True
                e[f"_sl_{st}"] = e[f"_sl10_{st}"]
            cells.append(
                {
                    "k": k,
                    "st": st,
                    "cal_calls": cr,
                    "l3m_calls": tr,
                    "cal_n": len(cr),
                    "l3m_n": len(tr),
                    "avg_sl": sum(e[f"_sl10_{st}"] for e in tr) / len(tr),
                }
            )
    cells.sort(key=lambda r: (-r["l3m_n"], -r["cal_n"], r["avg_sl"]))
    seen, uniq = set(), []
    for r in cells:
        id_ = (r["k"], r["st"])
        if id_ in seen:
            continue
        seen.add(id_)
        uniq.append(r)
    return uniq


def cell_clean_on(events, k, st, h, l, c, extra_pred=None):
    matched = []
    for e in events:
        if k not in e["_keys"]:
            continue
        if extra_pred and not extra_pred(e):
            continue
        sl = e.get(f"_sl10_{st}", 99)
        if not (4 <= sl <= SL_MAX):
            continue
        matched.append(e)
    matched = fwdmod.apply_gap(matched, GAP)
    if not matched:
        return True, 0, []
    out = []
    for e in matched:
        ok = e.get(f"_ok10_{st}")
        if not ok:
            # recompute to be sure
            ok2, sl = path_ok_sl10(e, h, l, c, st)
            if not ok2:
                return False, len(matched), []
            ok = ok2
        out.append({**e, "_st": st, "_sl": e[f"_sl10_{st}"], "_win": True})
    return True, len(out), out


def eval_book(events, micros, key_fn, h, l, c, extra_pred=None):
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
            if last is not None and e["mins"] - last < GAP:
                continue
            if extra_pred and not extra_pred(e):
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


def greedy(cells, min_cal=2, min_l3m=1):
    return fwdmod.greedy(cells, GAP, min_cal=min_cal, min_l3m=min_l3m)


def main() -> int:
    print("=" * 60, flush=True)
    print("Fail prior-3 diagnose + ACC100 T1=20 SL<=10 hunt", flush=True)
    print("=" * 60, flush=True)
    PACK.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    blob = pickle.load(EV_CACHE.open("rb"))
    era_events = blob["era_events"]
    print(f"eras={[ (k,len(v)) for k,v in era_events.items() ]}", flush=True)

    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(HIST_LO, tz="Asia/Kolkata")]
    print("[1] bars+patterns…", flush=True)
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    vix_prior = vixmod.load_vix()

    print("[2] enrich structure + prior3 + SL10 flags…", flush=True)
    for name, xs in era_events.items():
        fwdmod.enrich_evt(xs, h, l, c, o)
        enrich_structure(xs, h, l, c, o, vix_prior)
        enrich_prior3(xs, h, l, c, o)
        flag_sl10(xs, h, l, c)
        print(f"  {name} ok", flush=True)

    analyze = [e for er in ANALYZE_ERAS for e in era_events[er]]
    hold = [e for er in HOLD_ERAS for e in era_events[er]]
    fwd = [e for er in FWD_ERAS for e in era_events[er]]

    print("[3] diagnose failures…", flush=True)
    diag_a, rows_a = diagnose_failures(analyze, h, l, c, "analyze_2024_25")
    diag_h, rows_h = diagnose_failures(hold, h, l, c, "hold_2026")
    print(
        f"  analyze hit={diag_a['hit']}% n={diag_a['n']} loss={diag_a['n_loss']} "
        f"loss_MFE>=20={diag_a['loss_mfe_ge_t1']}",
        flush=True,
    )
    print(f"  fail_signal_rank={diag_a['fail_signal_rank'][:5]}", flush=True)
    print(f"  top loss pre3_stack={diag_a['loss_pre3_stack'][:5]}", flush=True)
    print(f"  top loss hm={diag_a['loss_hm'][:5]}", flush=True)

    # Anti-fail predicates (drop common failure causes)
    preds = {
        "raw": None,
        "no_fail_risk": lambda e: not e.get("fail_risk"),
        "opp_le1": lambda e: (e.get("pre3_opp") or 0) <= 1,
        "opp0_close_ok": lambda e: (e.get("pre3_opp") or 0) == 0 and e.get("close_ok") == 1,
        "opp0_advlo_b70": lambda e: (
            (e.get("pre3_opp") or 0) == 0
            and e.get("adv_bin") == "adv_lo"
            and e.get("body_bin") == "b70+"
            and e.get("close_ok") == 1
        ),
        "strong_opp0": lambda e: e.get("strong") == 1 and (e.get("pre3_opp") or 0) == 0 and e.get("close_ok") == 1,
        "very_strong_opp0": lambda e: (
            e.get("very_strong") == 1 and (e.get("pre3_opp") or 0) == 0 and e.get("pre3_weak_struct") == 0
        ),
        "vs_opp0_advlo_vix": lambda e: (
            e.get("very_strong") == 1
            and (e.get("pre3_opp") or 0) == 0
            and e.get("adv_bin") == "adv_lo"
            and e.get("vix_regime") in ("LOW", "NORMAL", "ELEVATED")
            and e.get("pre3_weak_struct") == 0
            and e.get("hm_bin") not in ("14+",)
        ),
        "vs_breakhold_opp0": lambda e: (
            e.get("very_strong") == 1
            and (e.get("pre3_opp") or 0) == 0
            and e.get("struct2") in ("break_hi_hold", "break_lo_hold")
            and e.get("adv_bin") == "adv_lo"
        ),
    }

    print("[4] filter lift on analyze/hold (any SL10 style first-hit)…", flush=True)
    filter_stats = {}
    for pname, pred in preds.items():
        def score(rows, pred):
            xs = [e for e in rows if pred is None or pred(e)]
            xs = fwdmod.apply_gap(xs, GAP)
            if not xs:
                return {"n": 0, "hit": 0.0, "wins": 0}
            w = sum(1 for e in xs if e["_win"])
            return {"n": len(xs), "wins": w, "hit": round(100.0 * w / len(xs), 2)}

        # rebuild rows with filter applied at selection time using diagnose path
        # Use rows_a/rows_h which already chose a style — filter those
        a = score(rows_a, pred)
        hh = score(rows_h, pred)
        filter_stats[pname] = {"analyze": a, "hold": hh}
        print(f"  {pname}: A {a['n']}@{a['hit']}%  H {hh['n']}@{hh['hit']}%", flush=True)

    # [5] Micro hunt — gate events FIRST (keeps cell count small), then ACC100 filter
    print("[5] micro ACC100 hunt T20 SL<=10…", flush=True)
    key_fn = fwdmod.keys_hight
    cal = era_events["E2024"]
    l3m = era_events["E2025"]
    for e in cal + l3m + hold + fwd:
        e["_keys"] = set(key_fn(e))

    def index_outcomes(events, pred):
        """(k,st) -> list of path bools for gated events (gapped later per cell)."""
        bucket = defaultdict(list)
        for e in events:
            if pred is not None and not pred(e):
                continue
            for st in SL10_STYLES:
                sl = e.get(f"_sl10_{st}", 99)
                if not (4 <= sl <= SL_MAX):
                    continue
                ok = bool(e.get(f"_ok10_{st}"))
                for k in e["_keys"]:
                    bucket[(k, st)].append((e, ok, sl))
        return bucket

    def keys_pre3(e):
        """Finer keys: pattern + prior-3 + close/VIX/time (anti-fail geometry)."""
        base = list(fwdmod.keys_hight(e))
        extra = [
            (e["primary"], e["decision"], e.get("pre3_stack"), e.get("close_ok"), e.get("adv_bin"), e.get("hm_bin"), e.get("vix_regime")),
            (e["family"], e["decision"], e.get("pre3_stack"), e.get("struct2"), e.get("close_ok"), e.get("slbin")),
            (e["primary"], e["decision"], e.get("pre3_opp"), e.get("close_ok"), e.get("adv_bin"), e.get("body_bin"), e.get("clock")),
            ("P3", e["decision"], e.get("pre3_stack"), e.get("struct2"), e.get("adv_bin"), e.get("vix_regime"), e.get("hm_bin")),
            (e["family"], e["decision"], e.get("stair"), e.get("close_ok"), e.get("pre3_weak_struct"), e.get("adv_bin")),
        ]
        return base + extra

    books = {}
    for pname, pred, kfn, min_l3m in [
        ("ACC100_SOFT", preds["opp0_close_ok"], key_fn, 2),
        ("ACC100_NOFAIL", preds["no_fail_risk"], key_fn, 2),
        ("ACC100_PRE3", preds["opp0_close_ok"], keys_pre3, 1),
        ("ACC100_PRE3_DENSE", preds["no_fail_risk"], keys_pre3, 1),
        ("ACC100_PRE3_RAW", None, keys_pre3, 1),
        ("ACC100_VS", preds["very_strong_opp0"], keys_pre3, 1),
        ("ACC100_STRONG", preds["strong_opp0"], keys_pre3, 1),
    ]:
        print(f"  building gated cells for {pname}…", flush=True)
        # refresh keys for this key_fn
        for e in cal + l3m + hold + fwd:
            e["_keys"] = set(kfn(e))
        cal_g = [e for e in cal if pred is None or pred(e)]
        l3m_g = [e for e in l3m if pred is None or pred(e)]
        cells = build_cells_sl10(cal_g, l3m_g, kfn, h, l, c)
        cells = [r for r in cells if r["cal_n"] >= 2 and r["l3m_n"] >= min_l3m]
        print(f"    gated train cells(min2/{min_l3m})={len(cells)}", flush=True)

        cal_idx = index_outcomes(cal, pred)
        l3m_idx = index_outcomes(l3m, pred)
        hold_idx = index_outcomes(hold, pred)
        fwd_idx = index_outcomes(fwd, pred)

        survivors = []
        for r in cells:
            k, st = r["k"], r["st"]
            # STRICT: every gated match in every era must be a path win (or era empty)
            eras_idx = (cal_idx, l3m_idx, hold_idx, fwd_idx)
            if any(rows and any(not ok for _, ok, _ in rows) for rows in (x.get((k, st), []) for x in eras_idx)):
                continue
            c_rows = cal_idx.get((k, st), [])
            l_rows = l3m_idx.get((k, st), [])
            h_rows = hold_idx.get((k, st), [])
            f_rows = fwd_idx.get((k, st), [])
            c_ev = fwdmod.apply_gap([e for e, ok, _ in c_rows if ok], GAP)
            l_ev = fwdmod.apply_gap([e for e, ok, _ in l_rows if ok], GAP)
            h_ev = fwdmod.apply_gap([e for e, ok, _ in h_rows if ok], GAP)
            f_ev = fwdmod.apply_gap([e for e, ok, _ in f_rows if ok], GAP)
            if len(c_ev) < 2 or len(l_ev) < min_l3m:
                continue
            for e in c_ev + l_ev + h_ev + f_ev:
                e["_sl"] = e[f"_sl10_{st}"]
                e["_win"] = True
                e[f"_ok_{st}"] = True
                e[f"_sl_{st}"] = e[f"_sl10_{st}"]
            survivors.append(
                {
                    "k": k,
                    "st": st,
                    "cal_calls": c_ev,
                    "l3m_calls": l_ev,
                    "cal_n": len(c_ev),
                    "l3m_n": len(l_ev),
                    "hold_n": len(h_ev),
                    "fwd_n": len(f_ev),
                    "total_n": len(c_ev) + len(l_ev) + len(h_ev) + len(f_ev),
                    "avg_sl": sum(e[f"_sl10_{st}"] for e in c_ev + l_ev) / max(len(c_ev) + len(l_ev), 1),
                }
            )
        survivors.sort(key=lambda r: (-r["total_n"], -r["hold_n"], r["avg_sl"]))
        chosen = greedy(survivors, min_cal=2, min_l3m=min_l3m)
        print(f"    survivors={len(survivors)} chosen={len(chosen)}", flush=True)

        # verify chrono books
        def summarize(xs):
            if not xs:
                return {"n": 0, "hit": 0.0, "all_win": True, "days": 0, "avg_sl": 0}
            w = sum(1 for e in xs if e["_win"])
            return {
                "n": len(xs),
                "hit": round(100.0 * w / len(xs), 2),
                "all_win": all(e["_win"] for e in xs),
                "days": len({e["day"] for e in xs}),
                "avg_sl": round(sum(e["_sl"] for e in xs) / len(xs), 2),
            }

        va = summarize(eval_book(cal, chosen, kfn, h, l, c, pred))
        vl = summarize(eval_book(l3m, chosen, kfn, h, l, c, pred))
        vh = summarize(eval_book(hold, chosen, kfn, h, l, c, pred))
        vf = summarize(eval_book(fwd, chosen, kfn, h, l, c, pred))
        total = va["n"] + vl["n"] + vh["n"] + vf["n"]
        print(
            f"  {pname}: micros={len(chosen)} total={total} "
            f"A24={va['n']}@{va['hit']}% A25={vl['n']}@{vl['hit']}% "
            f"H={vh['n']}@{vh['hit']}% F={vf['n']}@{vf['hit']}% "
            f"all_win={va['all_win'] and vl['all_win'] and vh['all_win'] and vf['all_win']}",
            flush=True,
        )
        for r in chosen[:6]:
            print(
                f"    {r['st']} tot={r['total_n']} H={r['hold_n']} F={r['fwd_n']} · {str(r['k'])[:80]}",
                flush=True,
            )

        sample = eval_book(hold, chosen, kfn, h, l, c, pred)[:20]
        books[pname] = {
            "n_micros": len(chosen),
            "n_survivors": len(survivors),
            "verify": {"E2024": va, "E2025": vl, "HOLD": vh, "FWD": vf},
            "total_calls": total,
            "micros": [
                {
                    "st": r["st"],
                    "k": str(r["k"]),
                    "cal_n": r["cal_n"],
                    "l3m_n": r["l3m_n"],
                    "hold_n": r["hold_n"],
                    "fwd_n": r["fwd_n"],
                    "avg_sl": round(r["avg_sl"], 2),
                }
                for r in chosen
            ],
            "hold_samples": [
                {
                    "day": e["day"],
                    "hm": e["hm"],
                    "decision": e["decision"],
                    "primary": e["primary"],
                    "st": e["_st"],
                    "sl": round(e["_sl"], 2),
                    "mfe": round(e["mfe"], 1),
                    "pre3": e.get("pre3_stack"),
                    "vix": e.get("vix_regime"),
                }
                for e in sample
            ],
        }
        (PACK / f"{pname}_micros.pkl").write_bytes(
            pickle.dumps([{"k": r["k"], "st": r["st"]} for r in chosen], protocol=pickle.HIGHEST_PROTOCOL)
        )

    # densest 100% among books
    best_name = max(books.keys(), key=lambda n: (books[n]["verify"]["HOLD"]["all_win"] and books[n]["verify"]["E2024"]["all_win"] and books[n]["verify"]["E2025"]["all_win"] and books[n]["verify"]["FWD"]["all_win"], books[n]["total_calls"]))

    results = {
        "constraints": {"t1": T1, "sl_max": SL_MAX, "gap": GAP},
        "diag_analyze": diag_a,
        "diag_hold": diag_h,
        "filter_stats": filter_stats,
        "books": books,
        "best": best_name,
        "elapsed_s": round(time.time() - t0, 1),
    }

    lines = [
        "# NIFTY 1m — why calls fail (prior-3) + **ACC100 T1=20 SL≤10**",
        "",
        "Constraints: **target 20 (>15)** · **SL max 10** · path = target before SL · max calls under 100%.",
        "",
        "## Why failures happen",
        "",
        f"Analyze baseline (any SL≤10 style): **{diag_a['n']}** calls · hit **{diag_a['hit']}%** · losses **{diag_a['n_loss']}** "
        f"(of which MFE≥20 after SL-first: **{diag_a['loss_mfe_ge_t1']}**).",
        "",
        "### Failure signals (more common in losses than wins)",
        "",
        "| Feature | In losses% | In wins% | Δ |",
        "|---|---:|---:|---:|",
    ]
    for fs in diag_a["fail_signal_rank"]:
        lines.append(f"| {fs['feature']} | {fs['in_loss%']} | {fs['in_win%']} | {fs['delta']} |")

    lines += [
        "",
        "### Top loss prior-3 stacks (dir of candle-3 → candle-1 before signal)",
        "",
        f"`{diag_a['loss_pre3_stack'][:8]}`",
        "",
        f"Win stacks: `{diag_a['win_pre3_stack'][:8]}`",
        "",
        f"- Loss hours: `{diag_a['loss_hm']}`",
        f"- Loss VIX: `{diag_a['loss_vix']}`",
        f"- Loss patterns: `{diag_a['loss_primary'][:6]}`",
        f"- Loss struct2: `{diag_a['loss_struct2'][:5]}`",
        f"- Loss avg MAE/MFE: {diag_a['avg_mae_loss']} / {diag_a['avg_mfe_loss']}",
        "",
        "## Anti-fail filter lift (still not 100% alone)",
        "",
        "| Gate | Analyze | Hold |",
        "|---|---|---|",
    ]
    for pname, st in filter_stats.items():
        a, hh = st["analyze"], st["hold"]
        lines.append(f"| `{pname}` | {a['n']}@{a['hit']}% | {hh['n']}@{hh['hit']}% |")

    lines += [
        "",
        "## ACC100 books (100% on 2024 + 2025 + hold 2026 + FWD, SL≤10, T1=20)",
        "",
        "| Book | Micros | Total | 2024 | 2025 | Hold | FWD | all_win |",
        "|---|---:|---:|---|---|---|---|:---:|",
    ]
    for pname, b in books.items():
        v = b["verify"]
        aw = all(v[k]["all_win"] for k in v)
        lines.append(
            f"| **{pname}** | {b['n_micros']} | {b['total_calls']} | "
            f"{v['E2024']['n']}@{v['E2024']['hit']}% | {v['E2025']['n']}@{v['E2025']['hit']}% | "
            f"{v['HOLD']['n']}@{v['HOLD']['hit']}% | {v['FWD']['n']}@{v['FWD']['hit']}% | {aw} |"
        )

    lines += [
        "",
        f"**Best densest 100% book: `{best_name}`** ({books[best_name]['total_calls']} calls).",
        "",
        "### Micros",
        "",
    ]
    for m in books[best_name]["micros"][:40]:
        lines.append(
            f"- `{m['st']}` cal={m['cal_n']} l3m={m['l3m_n']} hold={m['hold_n']} fwd={m['fwd_n']} "
            f"avgSL={m['avg_sl']} · `{m['k'][:90]}`"
        )

    lines += [
        "",
        f"Pack: `{PACK}`",
        f"Elapsed: {results['elapsed_s']}s",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    # slim json
    slim = {
        "constraints": results["constraints"],
        "diag_analyze": {
            k: diag_a[k]
            for k in (
                "n",
                "n_win",
                "n_loss",
                "hit",
                "loss_mfe_ge_t1",
                "fail_signal_rank",
                "loss_pre3_stack",
                "win_pre3_stack",
                "loss_hm",
                "loss_vix",
                "loss_primary",
            )
        },
        "filter_stats": filter_stats,
        "books": {
            k: {
                "n_micros": v["n_micros"],
                "total_calls": v["total_calls"],
                "verify": v["verify"],
                "micros": v["micros"][:30],
            }
            for k, v in books.items()
        },
        "best": best_name,
        "elapsed_s": results["elapsed_s"],
    }
    REPORT_JSON.write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {REPORT_MD}", flush=True)
    print(f"BEST={best_name} total={books[best_name]['total_calls']}", flush=True)
    print("DONE fail3 + T20 SL10 ACC100", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
