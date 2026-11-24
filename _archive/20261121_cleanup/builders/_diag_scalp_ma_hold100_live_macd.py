"""LIVE today: audit held logic + rebuild toward 100% using MACD indication.

1) Refresh today 1m
2) Score every textbook event with EMA34-trail T1=12
3) Show live MACD state at each candidate
4) Hunt MACD-centric filters that are 100% on *completed* today paths
5) Cross-check best filter on last-3m (honest OOS for the rule shape)
"""
from __future__ import annotations

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
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import enrich_prior3  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402
from _diag_scalp_ma_lastyear_init import WIN_LO, PACK, add_ma_layers, enrich_ma_layers, summarize  # noqa: E402
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402
from _diag_scalp_ma_hold100_picker import MODE, T1  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SCALP_MA_HOLD100_LIVE_MACD.md"


def ensure_today(raw, today: str):
    n = int(((raw.index >= today) & (raw.index < pd.Timestamp(today, tz="Asia/Kolkata") + pd.Timedelta(days=1))).sum())
    if n >= 50:
        return raw, n
    start_dl = (pd.Timestamp(today) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    print(f"download {start_dl}→{today}…", flush=True)
    fresh, note = base.download_1m_range(start_dl, today)
    if note:
        print(f"  note: {note}", flush=True)
    if fresh is None or len(fresh) == 0:
        return raw, n
    raw = pd.concat([raw, fresh]).sort_index()
    raw = raw[~raw.index.duplicated(keep="last")]
    n = int(((raw.index >= today) & (raw.index < pd.Timestamp(today, tz="Asia/Kolkata") + pd.Timedelta(days=1))).sum())
    return raw, n


def macd_live_tags(e):
    """Stricter MACD live indication tags."""
    side = e["decision"]
    mh = float(e.get("macd_hist") or 0)
    # enrich_ind sets macd_turn; also use hist magnitude via stored fields
    e["macd_hist_pos"] = mh > 0
    e["macd_hist_neg"] = mh < 0
    e["macd_with"] = (mh > 0) if side == "BUY" else (mh < 0)
    e["macd_against"] = not e["macd_with"]
    # cross-ish: turn already means hist sign with side
    e["macd_live"] = bool(e.get("macd_turn") and e.get("macd_with"))
    # stronger: MACD with + DI + not against VWAP
    e["macd_ind_a"] = bool(e["macd_live"] and e.get("di_ok"))
    e["macd_ind_b"] = bool(e["macd_live"] and e.get("di_ok") and e.get("vwap_with"))
    e["macd_ind_c"] = bool(e["macd_live"] and e.get("di_ok") and e.get("vwap_with") and e.get("gate_hard34"))
    e["macd_ind_d"] = bool(e["macd_live"] and e.get("di_ok") and e.get("gate_hard34") and e.get("bb_mid_ok"))
    e["macd_ind_e"] = bool(e["macd_live"] and e.get("gate_hard34") and e.get("mom_ok") and e.get("close_ok") == 1)
    e["macd_ind_f"] = bool(
        e["macd_live"] and e.get("di_ok") and e.get("vwap_with") and e.get("gate_hard34") and e.get("close_ok") == 1 and not e.get("fail_risk")
    )
    return e


def score_events(xs, h, l, c, ema34):
    for e in xs:
        ok, reason, sl, t1 = path_ma_trail_strict(h, l, c, ema34, int(e["full_i"]), e["decision"], T1)
        e["_win"] = bool(ok)
        e["_reason"] = reason
        e["_sl"] = float(sl or 0)
        e["_t1"] = float(t1)
        e["_done"] = reason in ("t1", "ma_sl", "both")  # completed path
        macd_live_tags(e)


def first_pass(xs, pred):
    for e in sorted(xs, key=lambda x: x["mins"]):
        if pred(e):
            return e
    return None


def all_pass(xs, pred, gap=1):
    out, last = [], None
    for e in sorted(xs, key=lambda x: x["mins"]):
        if not pred(e):
            continue
        if last is not None and e["mins"] - last < gap:
            continue
        out.append(e)
        last = e["mins"]
    return out


def hit_of(calls, only_done=True):
    rows = [e for e in calls if (e["_done"] if only_done else True)]
    if not rows:
        return {"n": 0, "hit": 0.0, "wins": 0, "pending": sum(1 for e in calls if not e["_done"])}
    w = sum(1 for e in rows if e["_win"])
    return {
        "n": len(rows),
        "wins": w,
        "hit": round(100.0 * w / len(rows), 2),
        "all_win": all(e["_win"] for e in rows),
        "pending": sum(1 for e in calls if not e["_done"]),
    }


def main() -> int:
    today = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
    print(f"LIVE+MACD audit today={today}", flush=True)

    raw = base.load_existing_1m()
    raw, n_today = ensure_today(raw, today)
    print(f"end={raw.index.max()} today_bars={n_today}", flush=True)
    if n_today < 30:
        REPORT.write_text(f"# LIVE MACD `{today}`\n\nNot enough bars ({n_today}).\n", encoding="utf-8")
        return 1

    warm_lo = (pd.Timestamp(today) - pd.Timedelta(days=15)).strftime("%Y-%m-%d")
    work = raw[raw.index >= pd.Timestamp(warm_lo, tz="Asia/Kolkata")].copy()
    df = tb.detect_textbook(work)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    macdh = df["macd_hist"].astype(float).values
    macd = df["macd"].astype(float).values
    macds = df["macd_sig"].astype(float).values
    vix = vixmod.load_vix()

    xs = scalp.collect_scalp_events(df, today, today)
    print(f"events={len(xs)}", flush=True)
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)
    enrich_ind(xs, df)
    # attach raw macd numbers for display
    for e in xs:
        i = int(e["full_i"])
        e["macd"] = round(float(macd[i]), 3)
        e["macd_sig"] = round(float(macds[i]), 3)
        e["macd_hist"] = round(float(macdh[i]), 3)
        e["ema34"] = round(float(ema34[i]), 2)
        e["px"] = round(float(c[i]), 2)
    score_events(xs, h, l, c, ema34)

    # --- A) old held vs MACD indications on TODAY ---
    filters = [
        ("OLD_held DI+hard34+VWAP", held_gate),
        ("MACD_live (hist with side)", lambda e: e.get("macd_live")),
        ("MACD+DI", lambda e: e.get("macd_ind_a")),
        ("MACD+DI+VWAP", lambda e: e.get("macd_ind_b")),
        ("MACD+DI+VWAP+hard34", lambda e: e.get("macd_ind_c")),
        ("MACD+DI+hard34+BBmid", lambda e: e.get("macd_ind_d")),
        ("MACD+hard34+mom+close", lambda e: e.get("macd_ind_e")),
        ("MACD+DI+VWAP+hard34+close+!fail", lambda e: e.get("macd_ind_f")),
        ("MACD cross-up only BUY hist>0 & hard34", lambda e: e.get("decision") == "BUY" and e.get("macd_hist", 0) > 0 and e.get("gate_hard34")),
        ("MACD hist accelerating", lambda e: e.get("macd_live") and abs(float(e.get("macd_hist") or 0)) >= 0.5 and e.get("di_ok")),
    ]

    lines = [
        f"# LIVE today `{today}` — MACD indication hunt → 100%",
        "",
        f"Data through `{raw.index.max()}` · bars today **{n_today}** · events **{len(xs)}**",
        f"Exit check: EMA34 trail · T1=**{T1:.0f}** (completed = t1 or ma_sl)",
        "",
        "## A) Filters on TODAY (completed paths only)",
        "",
        "| Filter | 1st call | Completed n@hit | all_win | Pending |",
        "|---|---|---:|:---:|---:|",
    ]

    best_today = None
    print("[A] today filters…", flush=True)
    for name, pred in filters:
        calls = all_pass(xs, pred, gap=1)
        first = calls[0] if calls else None
        st = hit_of(calls, only_done=True)
        first_s = "NO_CALL" if first is None else f"{first['hm']} {first['decision']} {first['primary']}"
        print(f"  {name}: first={first_s} done {st['n']}@{st.get('hit',0)}% pend={st['pending']}", flush=True)
        lines.append(
            f"| `{name}` | {first_s} | {st['n']}@{st.get('hit',0)}% | {st.get('all_win', False)} | {st['pending']} |"
        )
        if st["n"] >= 1 and st.get("all_win") and (best_today is None or st["n"] > best_today[1]["n"]):
            best_today = (name, st, pred, calls)

    # --- timeline of old held vs macd ---
    lines += [
        "",
        "## B) Live timeline — every event with MACD / gates / path",
        "",
        "| HM | Side | Pat | px | MACD hist | macd_live | DI | hard34 | VWAP | OLD | path |",
        "|---|---|---|---:|---:|:---:|:---:|:---:|:---:|:---:|---|",
    ]
    for e in sorted(xs, key=lambda x: x["mins"]):
        path = "…" if not e["_done"] else ("Y" if e["_win"] else "N")
        lines.append(
            f"| {e['hm']} | {e['decision']} | {e['primary']} | {e['px']} | {e['macd_hist']} | "
            f"{int(bool(e.get('macd_live')))} | {int(bool(e.get('di_ok')))} | "
            f"{int(bool(e.get('gate_hard34')))} | {int(bool(e.get('vwap_with')))} | "
            f"{int(held_gate(e))} | {path}/{e['_reason']} |"
        )

    # --- C) Cross-check filters that were 100% today on last-3m ---
    print("[C] cross-check last3m…", flush=True)
    raw_full = base.load_existing_1m()
    # merge today fresh into full for continuity
    raw_full = pd.concat([raw_full, raw]).sort_index()
    raw_full = raw_full[~raw_full.index.duplicated(keep="last")]
    raw_full = raw_full[raw_full.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    data_hi = str(raw_full.index.max().date())
    hold_lo = str((pd.Timestamp(data_hi) - pd.DateOffset(months=3) + pd.Timedelta(days=1)).date())

    df2 = tb.detect_textbook(raw_full)
    df2 = beh.add_rsi(df2)
    df2 = add_ma_layers(df2)
    df2 = add_indicators(df2)
    h2 = df2["High"].astype(float).values
    l2 = df2["Low"].astype(float).values
    c2 = df2["Close"].astype(float).values
    o2 = df2["Open"].astype(float).values
    atr2 = df2["atr14"].astype(float).values
    emas2 = {n: df2[f"ema{n}"].astype(float).values for n in (15, 21, 34, 50)}
    mh2 = df2["macd_hist"].astype(float).values
    vix = vixmod.load_vix()

    cache = next(PACK.glob("events_2025-11-17_*.pkl"))
    ev = pickle.load(cache.open("rb"))
    hold = [e for e in ev if hold_lo <= e["day"] < today]
    # if today in hold_lo range, exclude today for pure history check; include separately
    fwdmod.enrich_evt(hold, h2, l2, c2, o2)
    enrich_structure(hold, h2, l2, c2, o2, vix)
    enrich_prior3(hold, h2, l2, c2, o2)
    enrich_deep(hold, h2, l2, c2, o2, df2)
    enrich_ma_layers(hold, df2)
    enrich_ind(hold, df2)
    for e in hold:
        i = int(e["full_i"])
        e["macd_hist"] = round(float(mh2[i]), 3) if i < len(mh2) else 0.0
    attach = __import__("_diag_scalp_ma_hold100", fromlist=["attach_exit_grid"]).attach_exit_grid
    attach(hold, h2, l2, c2, emas2, atr2, [MODE])
    for e in hold:
        sc = e["_exit"][(MODE, T1)]
        e["_win"] = sc["_win"]
        e["_sl"] = float(sc.get("_sl") or 0)
        e["_t1"] = float(sc.get("_t1") or T1)
        e["_reason"] = sc.get("_reason", "t1" if sc["_win"] else "ma_sl")
        e["_done"] = True
        macd_live_tags(e)

    days = sorted({e["day"] for e in hold})
    lines += [
        "",
        f"## C) Same MACD filters on last-3m history (`{hold_lo}`→ before today) — 1/day first",
        "",
        "| Filter | n@hit cover | all_win |",
        "|---|---|:---:|",
    ]
    for name, pred in filters:
        by = defaultdict(list)
        for e in hold:
            by[e["day"]].append(e)
        calls = []
        for d, rows in sorted(by.items()):
            e = first_pass(rows, pred)
            if e:
                calls.append(e)
        st = summarize(calls, len(days))
        print(f"  L3M {name}: {st['n']}@{st['hit']}%/{st['cover']}%", flush=True)
        lines.append(f"| `{name}` | {st['n']}@{st['hit']}% {st['cover']}% | {st['all_win']} |")

    # Live recommendation
    lines += ["", "## Live indication (what to use now)", ""]
    if best_today and best_today[1].get("all_win"):
        name, st, pred, calls = best_today
        live = first_pass(xs, pred)
        lines += [
            f"On **completed** paths today, **`{name}`** is **100%** ({st['n']} done).",
            f"- First live fire: **{live['hm'] if live else 'NONE'}** "
            + (f"{live['decision']} {live['primary']} px={live['px']} MACD_hist={live['macd_hist']}" if live else ""),
            "- Still verify on history (section C) — today-only 100% can overfit.",
            "",
        ]
        print(f"TODAY 100% filter: {name} n={st['n']}", flush=True)
    else:
        lines += [
            "No MACD filter achieved **100%** on today’s completed multi signals with enough samples.",
            "Prefer **MACD+DI+VWAP+hard34** as live indication (best large-sample compromise historically).",
            "",
        ]
        live = first_pass(xs, lambda e: e.get("macd_ind_c"))
        if live:
            lines.append(
                f"**Current preferred call:** {live['hm']} {live['decision']} {live['primary']} "
                f"px={live['px']} MACD_hist={live['macd_hist']} EMA34={live['ema34']} T1=+{T1:.0f}"
            )
            print(
                f"PREFERRED: {live['hm']} {live['decision']} {live['primary']} hist={live['macd_hist']}",
                flush=True,
            )

    # Compare OLD first call vs MACD preferred
    old = first_pass(xs, held_gate)
    macd_pref = first_pass(xs, lambda e: e.get("macd_ind_c"))
    lines += [
        "",
        "## Today call comparison",
        "",
        f"- OLD held first: "
        + (f"**{old['hm']} {old['decision']} {old['primary']}** path={old['_reason']}" if old else "NO_CALL"),
        f"- MACD+DI+VWAP+hard34 first: "
        + (
            f"**{macd_pref['hm']} {macd_pref['decision']} {macd_pref['primary']}** path={macd_pref['_reason']} hist={macd_pref['macd_hist']}"
            if macd_pref
            else "NO_CALL"
        ),
        "",
        "### Exact MACD live rule under test",
        "1. Candle signal fires",
        "2. **MACD histogram with trade** (BUY hist>0 / SELL hist<0) = `macd_live`",
        "3. Plus DI align + VWAP with + EMA34 hard (preferred stack)",
        "4. Hold EMA34 trail · T1=12",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
