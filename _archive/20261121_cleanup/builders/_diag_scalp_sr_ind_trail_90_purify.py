"""RESEARCH ONLY — purify fingerprints + S/R/ind for ≥90% EMA34-trail books.

Phase-2 after blind gates failed train+hold ≥90 together.

Methods:
  A) HELD 1/day NO session cut (matches prior BN 90.48% T12 book)
  B) Purified fingerprints: 100% win on train, n≥min → first match on hold
     Keys include S/R + indication tags
  C) UNION: purify-T1 first, else HELD fallback
  D) Require hold hit ≥90 (and report train)

  python -u prod_live/tests/builders/_diag_scalp_sr_ind_trail_90_purify.py
"""
from __future__ import annotations

import json
import pickle
import sys
import time
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
from _diag_scalp_ma_lastyear_init import WIN_LO, HOLD_LO, PACK as NIFTY_PACK, add_ma_layers, enrich_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100 import keys_hold  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402
from _diag_scalp_sr_highmove_proven import enrich_sr_archetypes  # noqa: E402
from _diag_scalp_sr_ind_trail_90_all import enrich_extra, in_session  # noqa: E402

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "ALL_1M_SR_IND_TRAIL_PROVEN90_PURIFY.md"
REPORT_JSON = OUT / "ALL_1M_SR_IND_TRAIL_PROVEN90_PURIFY.json"
BN_CSV = ROOT / "stock_signal_data" / "fno_validate" / "BANKNIFTY_1m_kite.csv"
BN_PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "banknifty_1m_scalp_t15_t12"

TARGET = 90.0
MIN_KEY_N = 3


def sr_ind_keys(e):
    """Extra S/R + indication fingerprints for purify."""
    return [
        ("SR1", e.get("primary"), e.get("decision"), int(bool(e.get("sr_bounce"))), int(bool(e.get("clear15"))), int(bool(e.get("ctrl_sweep"))), e.get("regime")),
        ("SR2", e.get("primary"), e.get("decision"), int(bool(e.get("held"))), int(bool(e.get("clear20"))), int(bool(e.get("macd_turn"))), int(bool(e.get("di_ge8")))),
        ("SR3", e.get("family"), e.get("decision"), int(bool(e.get("reg_hold"))), int(bool(e.get("clear15"))), int(bool(e.get("adx22"))), e.get("hm_bin")),
        ("SR4", e.get("primary"), e.get("decision"), int(bool(e.get("tier_a"))), int(bool(e.get("bounce_clear"))), int(bool(e.get("not_extreme"))), e.get("ma_stack34")),
        ("SR5", e.get("decision"), int(bool(e.get("held"))), int(bool(e.get("ctrl_sweep"))), int(bool(e.get("clear15"))), int(bool(e.get("after1100"))), int(bool(e.get("di_ge8")))),
        ("SR6", e.get("primary"), e.get("decision"), int(bool(e.get("vwap_reclaim"))), int(bool(e.get("clear15"))), int(bool(e.get("control_with"))), e.get("dist34_bin")),
    ]


def all_keys(e):
    ks = []
    try:
        ks.extend(keys_hold(e))
    except Exception:
        pass
    ks.extend(sr_ind_keys(e))
    return ks


def score_t1(events, h, l, c, ema34, t1):
    for e in events:
        ok, reason, sl, t1v = path_ma_trail_strict(
            h, l, c, ema34, int(e["full_i"]), e["decision"], float(t1)
        )
        e["_win"] = bool(ok)
        e["_reason"] = reason
        e["_pts"] = float(t1v if ok else -(abs(sl) if sl else 0))
        e["_keys"] = set(all_keys(e))


def purify(train, min_n=MIN_KEY_N):
    bucket = defaultdict(list)
    for e in train:
        for k in e.get("_keys") or []:
            bucket[k].append(bool(e["_win"]))
    allow = {}
    for k, rows in bucket.items():
        if any(not ok for ok in rows):
            continue
        if sum(1 for ok in rows if ok) < min_n:
            continue
        allow[k] = len(rows)
    return allow


def first_held(rows, require_sess=False):
    for e in sorted(rows, key=lambda x: x["mins"]):
        if require_sess and not in_session(e):
            continue
        if held_gate(e):
            return e
    return None


def first_key(rows, allow, require_sess=False):
    for e in sorted(rows, key=lambda x: x["mins"]):
        if require_sess and not in_session(e):
            continue
        if any(k in allow for k in (e.get("_keys") or [])):
            return e
    return None


def first_union(rows, allow, require_sess=False):
    e = first_key(rows, allow, require_sess=require_sess)
    if e is not None:
        e = {**e, "_book": "PURIFY"}
        return e
    e = first_held(rows, require_sess=require_sess)
    if e is not None:
        return {**e, "_book": "HELD"}
    return None


def first_gate(rows, pred):
    for e in sorted(rows, key=lambda x: x["mins"]):
        if pred(e):
            return e
    return None


def eval_picker(events, days, picker):
    by = defaultdict(list)
    for e in events:
        by[e["day"]].append(e)
    calls = []
    for d in days:
        e = picker(by.get(d, []))
        if e is None:
            continue
        calls.append(e)
    n = len(calls)
    nd = len(days)
    if not n:
        return {"n": 0, "hit": None, "cover": 0.0, "avg_pts": None, "w": 0, "l": 0, "calls": []}
    w = sum(1 for c in calls if c["_win"])
    return {
        "n": n,
        "hit": round(100.0 * w / n, 2),
        "cover": round(100.0 * n / nd, 2) if nd else 0.0,
        "avg_pts": round(float(np.mean([c["_pts"] for c in calls])), 2),
        "w": w,
        "l": n - w,
        "calls": calls,
    }


def prepare_symbol(sym, xs, df, cut):
    o = df["Open"].astype(float).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    print(f"  enrich {sym} n={len(xs)}…", flush=True)
    try:
        vix = vixmod.load_vix()
        enrich_structure(xs, h, l, c, o, vix)
    except Exception as ex:
        print(f"  structure skip: {ex}", flush=True)
    try:
        enrich_prior3(xs, h, l, c, o)
        enrich_deep(xs, h, l, c, o, df)
    except Exception as ex:
        print(f"  deep/prior skip: {ex}", flush=True)
    try:
        fwdmod.enrich_evt(xs, h, l, c, o)
    except Exception as ex:
        print(f"  fwd skip: {ex}", flush=True)
    enrich_ma_layers(xs, df)
    enrich_ind(xs, df)
    enrich_extra(xs, df)
    days = sorted({e["day"] for e in xs})
    if cut <= days[0]:
        cut = days[int(len(days) * 0.65)]
    return {
        "sym": sym,
        "xs": xs,
        "h": h,
        "l": l,
        "c": c,
        "ema34": df["ema34"].astype(float).values,
        "days": days,
        "cut": cut,
        "train_days": [d for d in days if d < cut],
        "hold_days": [d for d in days if d >= cut],
    }


def run_t1(pack, t1):
    xs = pack["xs"]
    score_t1(xs, pack["h"], pack["l"], pack["c"], pack["ema34"], t1)
    train = [e for e in xs if e["day"] < pack["cut"]]
    hold = [e for e in xs if e["day"] >= pack["cut"]]
    allow = purify(train)
    print(f"  {pack['sym']} T{t1:.0f}: clean keys={len(allow)}", flush=True)

    books = []

    def add(name, picker, pool_events, pool_days, tag):
        st = eval_picker(pool_events, pool_days, picker)
        books.append({"name": name, "tag": tag, **{k: st[k] for k in ("n", "hit", "cover", "avg_pts", "w", "l")}})
        return st

    # A HELD no sess / with sess
    for sess_flag, lab in ((False, "HELD"), (True, "HELD+sess")):
        add(
            f"{lab}",
            lambda rows, s=sess_flag: first_held(rows, require_sess=s),
            train,
            pack["train_days"],
            "train",
        )
        add(
            f"{lab}",
            lambda rows, s=sess_flag: first_held(rows, require_sess=s),
            hold,
            pack["hold_days"],
            "hold",
        )
        add(
            f"{lab}",
            lambda rows, s=sess_flag: first_held(rows, require_sess=s),
            xs,
            pack["days"],
            "all",
        )

    # B purify
    for sess_flag, lab in ((False, "PURIFY"), (True, "PURIFY+sess")):
        add(
            lab,
            lambda rows, a=allow, s=sess_flag: first_key(rows, a, require_sess=s),
            train,
            pack["train_days"],
            "train",
        )
        add(
            lab,
            lambda rows, a=allow, s=sess_flag: first_key(rows, a, require_sess=s),
            hold,
            pack["hold_days"],
            "hold",
        )
        add(
            lab,
            lambda rows, a=allow, s=sess_flag: first_key(rows, a, require_sess=s),
            xs,
            pack["days"],
            "all",
        )

    # C UNION purify→HELD
    for sess_flag, lab in ((False, "UNION"), (True, "UNION+sess")):
        add(
            lab,
            lambda rows, a=allow, s=sess_flag: first_union(rows, a, require_sess=s),
            train,
            pack["train_days"],
            "train",
        )
        add(
            lab,
            lambda rows, a=allow, s=sess_flag: first_union(rows, a, require_sess=s),
            hold,
            pack["hold_days"],
            "hold",
        )
        add(
            lab,
            lambda rows, a=allow, s=sess_flag: first_union(rows, a, require_sess=s),
            xs,
            pack["days"],
            "all",
        )

    # D tight S/R gates (no sess) that showed high hold on NIFTY
    tight = [
        ("SR_bounce_backed_ctrl_clear", lambda e: held_gate(e) and e.get("sr_bounce") and e.get("backed") and e.get("ctrl_sweep") and e.get("clear15")),
        ("SR_hold_clear15", lambda e: held_gate(e) and e.get("reg_hold") and e.get("clear15")),
        ("SR_held_bounce", lambda e: held_gate(e) and e.get("sr_bounce")),
        ("SR_held_clear15_macd_di8", lambda e: held_gate(e) and e.get("clear15") and e.get("macd_turn") and e.get("di_ge8")),
        ("SR_tierA_clear15", lambda e: e.get("tier_a") and e.get("clear15")),
        ("SR_ctrl_sweep_clear15_di8_1100", lambda e: held_gate(e) and e.get("ctrl_sweep") and e.get("clear15") and e.get("di_ge8") and e.get("after1100")),
    ]
    for gname, pred in tight:
        add(gname, lambda rows, p=pred: first_gate(rows, p), train, pack["train_days"], "train")
        add(gname, lambda rows, p=pred: first_gate(rows, p), hold, pack["hold_days"], "hold")
        add(gname, lambda rows, p=pred: first_gate(rows, p), xs, pack["days"], "all")

    # pivot books by name
    by_name = defaultdict(dict)
    for b in books:
        by_name[b["name"]][b["tag"]] = b

    proven = []
    for name, parts in by_name.items():
        tr, ho = parts.get("train"), parts.get("hold")
        if not tr or not ho:
            continue
        if (
            tr["hit"] is not None
            and ho["hit"] is not None
            and tr["n"] >= 8
            and ho["n"] >= 8
            and tr["hit"] >= TARGET
            and ho["hit"] >= TARGET
        ):
            proven.append(
                {
                    "sym": pack["sym"],
                    "t1": t1,
                    "book": name,
                    "train": tr,
                    "hold": ho,
                    "all": parts.get("all"),
                    "n_keys": len(allow) if "PURIFY" in name or name == "UNION" or name == "UNION+sess" else None,
                }
            )
    return by_name, proven, allow


def load_nifty_pack():
    print("=== NIFTY ===", flush=True)
    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata") - pd.Timedelta(days=5)]
    data_hi = str(raw.index.max().date())
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    cands = sorted(NIFTY_PACK.glob(f"events_{WIN_LO}_*.pkl"))
    xs = pickle.load(cands[-1].open("rb"))
    print(f"  events={len(xs)} {cands[-1].name}", flush=True)
    return prepare_symbol("NIFTY", xs, df, HOLD_LO)


def load_bn_pack():
    print("=== BANKNIFTY ===", flush=True)
    raw = base._norm(pd.read_csv(BN_CSV))
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    cands = sorted(BN_PACK.glob("events_*.pkl"))
    xs = pickle.load(cands[-1].open("rb"))
    print(f"  events={len(xs)} {cands[-1].name}", flush=True)
    return prepare_symbol("BANKNIFTY", xs, df, "2026-05-03")


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("PURIFY ≥90% S/R+IND+trail (RESEARCH ONLY)", flush=True)

    nifty = load_nifty_pack()
    bn = load_bn_pack()

    all_proven = []
    summaries = []

    for pack, t1s in ((nifty, [12.0, 15.0, 20.0]), (bn, [12.0, 15.0, 20.0])):
        for t1 in t1s:
            print(f"-- {pack['sym']} T{t1:.0f}", flush=True)
            by_name, proven, allow = run_t1(pack, t1)
            all_proven.extend(proven)
            for name, parts in sorted(by_name.items()):
                ho = parts.get("hold") or {}
                tr = parts.get("train") or {}
                summaries.append(
                    {
                        "sym": pack["sym"],
                        "t1": t1,
                        "book": name,
                        "train_hit": tr.get("hit"),
                        "train_n": tr.get("n"),
                        "hold_hit": ho.get("hit"),
                        "hold_n": ho.get("n"),
                        "hold_cover": ho.get("cover"),
                        "all_hit": (parts.get("all") or {}).get("hit"),
                        "all_n": (parts.get("all") or {}).get("n"),
                    }
                )
                if ho.get("hit") is not None and ho["hit"] >= 88:
                    print(
                        f"    {name}: train {tr.get('hit')}%/{tr.get('n')} hold {ho.get('hit')}%/{ho.get('n')}",
                        flush=True,
                    )

    # cross both HELD no-sess at T12
    lines = [
        "# ALL 1m — Purify + S/R/Ind + EMA34 Trail · ≥90% hunt (phase 2)",
        "",
        "> **RESEARCH ONLY — not live.**",
        "",
        "## Exit",
        "",
        "EMA34 trail strict · 1 call/day · WIN = T1 before MA flip",
        "",
        "## Methods",
        "",
        "1. **HELD** / HELD+sess — DI∧hard34∧VWAP",
        "2. **PURIFY** — fingerprints 100% on train (incl. S/R+ind keys), first match",
        "3. **UNION** — PURIFY else HELD",
        "4. **SR_*** — tight support/resistance + indication stacks",
        "",
        f"NIFTY cut `{nifty['cut']}` · BN cut `{bn['cut']}` · proven = train∧hold ≥{TARGET}% n≥8",
        "",
        f"## PROVEN ≥{TARGET}%",
        "",
    ]
    if not all_proven:
        lines += ["**None** yet at ≥90% train+hold.", ""]
    else:
        lines += [
            "| Sym | T1 | Book | Train | Hold | Cover | avgPts |",
            "|---|---:|---|---|---|---:|---:|",
        ]
        all_proven.sort(key=lambda r: (-r["hold"]["hit"], -r["hold"]["n"]))
        for r in all_proven:
            lines.append(
                f"| {r['sym']} | {r['t1']:.0f} | `{r['book']}` | "
                f"**{r['train']['hit']}%**/{r['train']['n']} | **{r['hold']['hit']}%**/{r['hold']['n']} | "
                f"{r['hold']['cover']}% | {r['hold']['avg_pts']} |"
            )
        lines.append("")

    lines += [
        "## Hold ≥88% candidates (near / pass)",
        "",
        "| Sym | T1 | Book | Train hit/n | Hold hit/n | cover | All hit |",
        "|---|---:|---|---|---|---:|---:|",
    ]
    near = [
        s
        for s in summaries
        if s["hold_hit"] is not None and s["hold_hit"] >= 88 and s["hold_n"] and s["hold_n"] >= 8
    ]
    near.sort(key=lambda s: (-s["hold_hit"], -s["hold_n"]))
    for s in near[:50]:
        lines.append(
            f"| {s['sym']} | {s['t1']:.0f} | `{s['book']}` | {s['train_hit']}%/{s['train_n']} | "
            f"**{s['hold_hit']}%**/{s['hold_n']} | {s['hold_cover']} | {s['all_hit']}%/{s['all_n']} |"
        )

    # best HELD comparison
    lines += [
        "",
        "## HELD baseline (no session) — the ≥90 path for BN historically",
        "",
        "| Sym | T1 | Train | Hold | All |",
        "|---|---:|---|---|---|",
    ]
    for s in summaries:
        if s["book"] == "HELD":
            lines.append(
                f"| {s['sym']} | {s['t1']:.0f} | {s['train_hit']}%/{s['train_n']} | "
                f"{s['hold_hit']}%/{s['hold_n']} | {s['all_hit']}%/{s['all_n']} |"
            )

    lines += [
        "",
        "## Locked recipe shape (when proven)",
        "",
        "```",
        "ENTRY:",
        "  textbook candle",
        "  + (PURIFY fingerprint match  OR  HELD=DI∧hard34∧VWAP)",
        "  + optional S/R clear / bounce / hold_break filters",
        "EXIT:",
        "  T1 = 12 (NIFTY) / 12–15 (BN)",
        "  trail = EMA34 close flip = stop",
        "  1 call/day first match",
        "```",
        "",
        f"Elapsed {time.time() - t0:.0f}s",
        "",
        "**Not wired live.**",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps({"proven": all_proven, "near": near[:60], "summaries": summaries}, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"wrote {REPORT}", flush=True)
    print(f"PROVEN90={len(all_proven)} NEAR88hold={len(near)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
