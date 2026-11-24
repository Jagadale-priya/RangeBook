"""RESEARCH ONLY — deep ≥90% proven entry (S/R + indicators) + EMA34 trail.

Goal: find blind entry logic that hits ≥90% with trailing exit, for NIFTY and BANKNIFTY.

Entry stack searched:
  HELD (DI ∧ hard34 ∧ VWAP) + S/R (clear / bounce / hold_break / not into wall)
  + indications (MACD turn, ADX, DI spread, control+sweep, session)

Exit (locked for this study):
  EMA34 trail strict — WIN only if T1 before close flips vs EMA34
  T1 grid: NIFTY {12,15,20} · BN {12,15,20,25}

Book: 1 call/day (first gated match) — same proven protocol as HOLD100.
Proven bar: hit ≥90% on TRAIN and HOLD (blind), min n.

  python -u prod_live/tests/builders/_diag_scalp_sr_ind_trail_90_all.py
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
from _diag_scalp_ma_lastyear_init import WIN_LO, HOLD_LO, PACK as NIFTY_PACK, add_ma_layers, enrich_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402
from _diag_scalp_sr_highmove_proven import enrich_sr_archetypes  # noqa: E402

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "ALL_1M_SR_IND_TRAIL_PROVEN90.md"
REPORT_JSON = OUT / "ALL_1M_SR_IND_TRAIL_PROVEN90.json"

BN_CSV = ROOT / "stock_signal_data" / "fno_validate" / "BANKNIFTY_1m_kite.csv"
BN_PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "banknifty_1m_scalp_t15_t12"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
TARGET = 90.0
MIN_N = 8  # min calls on a window for proven


def in_session(e) -> bool:
    return MINS_LO <= int(e.get("mins") or 0) < MINS_HI


def score_trail(events, h, l, c, ema34, t1):
    for e in events:
        ok, reason, sl, t1v = path_ma_trail_strict(
            h, l, c, ema34, int(e["full_i"]), e["decision"], float(t1)
        )
        e[f"_win_{int(t1)}"] = bool(ok)
        e[f"_reason_{int(t1)}"] = reason
        e[f"_pts_{int(t1)}"] = float(t1v if ok else -(abs(sl) if sl else 0))


def enrich_extra(events, df):
    setup.apply_setup_enrichment(events, df)
    enrich_sr_archetypes(events, df)
    for e in events:
        a = float(e.get("atr") or 8.0)
        room = float(e.get("room_fav") or 999)
        e["held"] = held_gate(e)
        e["sess"] = in_session(e)
        e["not_extreme"] = not bool(e.get("into_sess_extreme"))
        e["clear15"] = room >= 1.5 * a and e["not_extreme"]
        e["clear20"] = room >= 2.0 * a and e["not_extreme"]
        e["clear_atr"] = room >= 1.0 * a and e["not_extreme"]
        e["di_ge8"] = abs(float(e.get("di_spread") or 0)) >= 8
        e["di_ge12"] = abs(float(e.get("di_spread") or 0)) >= 12
        e["adx22"] = float(e.get("adx") or 0) >= 22
        e["ctrl_sweep"] = bool(e.get("control_with") and e.get("sweep_with"))
        e["reg_hold"] = e.get("regime") == "hold_break" or bool(e.get("hold_break_setup"))
        e["after1030"] = int(e.get("mins") or 0) >= 10 * 60 + 30
        e["after1100"] = int(e.get("mins") or 0) >= 11 * 60
        e["bounce_clear"] = bool(e.get("sr_bounce") and e.get("clear15"))
        e["tier_ab"] = bool(e.get("setup_ok"))
        e["tier_a"] = e.get("setup_tier") == "A"


def gate_catalog():
    """Blind entry gates — S/R + indications on HELD base."""
    return [
        ("HELD", lambda e: e.get("held") and e.get("sess")),
        ("HELD+clear15", lambda e: e.get("held") and e.get("sess") and e.get("clear15")),
        ("HELD+clear20", lambda e: e.get("held") and e.get("sess") and e.get("clear20")),
        ("HELD+clear_atr", lambda e: e.get("held") and e.get("sess") and e.get("clear_atr")),
        ("HELD+bounce", lambda e: e.get("held") and e.get("sess") and e.get("sr_bounce")),
        ("HELD+bounce+clear15", lambda e: e.get("held") and e.get("sess") and e.get("bounce_clear")),
        ("HELD+hold_break", lambda e: e.get("held") and e.get("sess") and e.get("reg_hold")),
        ("HELD+hold_break+clear15", lambda e: e.get("held") and e.get("sess") and e.get("reg_hold") and e.get("clear15")),
        ("HELD+ctrl_sweep", lambda e: e.get("held") and e.get("sess") and e.get("ctrl_sweep")),
        ("HELD+ctrl_sweep+clear15", lambda e: e.get("held") and e.get("sess") and e.get("ctrl_sweep") and e.get("clear15")),
        ("HELD+ctrl_sweep+clear15+di8", lambda e: e.get("held") and e.get("sess") and e.get("ctrl_sweep") and e.get("clear15") and e.get("di_ge8")),
        ("HELD+ctrl_sweep+clear15+di8+after1100", lambda e: e.get("held") and e.get("sess") and e.get("ctrl_sweep") and e.get("clear15") and e.get("di_ge8") and e.get("after1100")),
        ("HELD+macd+clear15", lambda e: e.get("held") and e.get("sess") and e.get("macd_turn") and e.get("clear15")),
        ("HELD+macd+adx22+clear15", lambda e: e.get("held") and e.get("sess") and e.get("macd_turn") and e.get("adx22") and e.get("clear15")),
        ("HELD+macd+di8+clear15", lambda e: e.get("held") and e.get("sess") and e.get("macd_turn") and e.get("di_ge8") and e.get("clear15")),
        ("HELD+ind_strict3+clear15", lambda e: e.get("held") and e.get("sess") and e.get("ind_strict3") and e.get("clear15")),
        ("TierA+clear15", lambda e: e.get("tier_a") and e.get("sess") and e.get("clear15")),
        ("TierAB+clear15", lambda e: e.get("tier_ab") and e.get("sess") and e.get("clear15")),
        ("TierAB+clear15+di8", lambda e: e.get("tier_ab") and e.get("sess") and e.get("clear15") and e.get("di_ge8")),
        ("TierAB+clear15+macd", lambda e: e.get("tier_ab") and e.get("sess") and e.get("clear15") and e.get("macd_turn")),
        ("bounce+backed+ctrl_sweep+clear15+HELD", lambda e: e.get("held") and e.get("sess") and e.get("sr_bounce") and e.get("backed") and e.get("ctrl_sweep") and e.get("clear15")),
        ("hold|bounce+ctrl+clear15+HELD", lambda e: e.get("held") and e.get("sess") and e.get("control_with") and e.get("clear15") and (e.get("reg_hold") or e.get("sr_bounce"))),
        ("HELD+clear15+after1030", lambda e: e.get("held") and e.get("sess") and e.get("clear15") and e.get("after1030")),
        ("HELD+clear15+adx22+di8", lambda e: e.get("held") and e.get("sess") and e.get("clear15") and e.get("adx22") and e.get("di_ge8")),
        ("HELD+not_extreme+macd+clear_atr", lambda e: e.get("held") and e.get("sess") and e.get("not_extreme") and e.get("macd_turn") and e.get("clear_atr")),
    ]


def first_gate(rows, pred):
    for e in sorted(rows, key=lambda x: x["mins"]):
        if pred(e):
            return e
    return None


def eval_1cpd(events, days, pred, t1):
    by = defaultdict(list)
    for e in events:
        by[e["day"]].append(e)
    calls = []
    for d in days:
        e = first_gate(by.get(d, []), pred)
        if e is None:
            continue
        win = bool(e.get(f"_win_{int(t1)}"))
        calls.append(
            {
                **e,
                "_win": win,
                "_reason": e.get(f"_reason_{int(t1)}"),
                "_pts": float(t1 if win else e.get(f"_pts_{int(t1)}") or 0),
            }
        )
    n = len(calls)
    nd = len(days)
    if not n:
        return {
            "n": 0,
            "hit": None,
            "cover": 0.0,
            "avg_pts": None,
            "w": 0,
            "l": 0,
            "calls": [],
        }
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


def month_hits(calls):
    by = defaultdict(list)
    for c in calls:
        by[c["day"][:7]].append(c)
    rows = []
    for m in sorted(by):
        xs = by[m]
        w = sum(1 for c in xs if c["_win"])
        rows.append((m, len(xs), round(100.0 * w / len(xs), 2)))
    return rows


def load_nifty():
    print("=== NIFTY ===", flush=True)
    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata") - pd.Timedelta(days=5)]
    data_hi = str(raw.index.max().date())
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    cache = NIFTY_PACK / f"events_{WIN_LO}_{data_hi}.pkl"
    if not cache.is_file():
        # fallback any events_WIN_LO_*.pkl
        cands = sorted(NIFTY_PACK.glob(f"events_{WIN_LO}_*.pkl"))
        if not cands:
            raise FileNotFoundError(cache)
        cache = cands[-1]
    xs = pickle.load(cache.open("rb"))
    print(f"  events={len(xs)} cache={cache.name} bars→{data_hi}", flush=True)
    # filter events to df range
    day_lo = str(df.index.min().date())
    xs = [e for e in xs if e["day"] >= max(WIN_LO, day_lo)]
    enrich_ma_layers(xs, df)
    enrich_ind(xs, df)
    enrich_extra(xs, df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    return {"sym": "NIFTY", "xs": xs, "df": df, "h": h, "l": l, "c": c, "ema34": ema34, "data_hi": data_hi}


def load_bn():
    print("=== BANKNIFTY ===", flush=True)
    raw = base._norm(pd.read_csv(BN_CSV))
    data_lo = str(raw.index.min().date())
    data_hi = str(raw.index.max().date())
    print(f"  csv {data_lo}→{data_hi} bars={len(raw)}", flush=True)
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    cands = sorted(BN_PACK.glob("events_*.pkl"))
    if not cands:
        raise FileNotFoundError(BN_PACK / "events_*.pkl")
    cache = cands[-1]
    xs = pickle.load(cache.open("rb"))
    print(f"  events={len(xs)} cache={cache.name}", flush=True)
    enrich_ma_layers(xs, df)
    enrich_ind(xs, df)
    enrich_extra(xs, df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    return {
        "sym": "BANKNIFTY",
        "xs": xs,
        "df": df,
        "h": h,
        "l": l,
        "c": c,
        "ema34": ema34,
        "data_hi": data_hi,
        "data_lo": data_lo,
    }


def run_symbol(pack, t1_list, hold_lo):
    xs = pack["xs"]
    days = sorted({e["day"] for e in xs})
    # hold_lo clamp
    if hold_lo <= days[0]:
        # use 70/30 time split
        cut = days[int(len(days) * 0.65)]
    else:
        cut = hold_lo
    train_days = [d for d in days if d < cut]
    hold_days = [d for d in days if d >= cut]
    train = [e for e in xs if e["day"] < cut]
    hold = [e for e in xs if e["day"] >= cut]
    print(
        f"  {pack['sym']}: days={len(days)} train<{cut} n_days={len(train_days)} "
        f"hold≥{cut} n_days={len(hold_days)}",
        flush=True,
    )

    for t1 in t1_list:
        score_trail(xs, pack["h"], pack["l"], pack["c"], pack["ema34"], t1)

    rows = []
    for t1 in t1_list:
        for gname, pred in gate_catalog():
            tr = eval_1cpd(train, train_days, pred, t1)
            ho = eval_1cpd(hold, hold_days, pred, t1)
            allr = eval_1cpd(xs, days, pred, t1)
            status = "—"
            if (
                tr["hit"] is not None
                and ho["hit"] is not None
                and tr["n"] >= MIN_N
                and ho["n"] >= MIN_N
                and tr["hit"] >= TARGET
                and ho["hit"] >= TARGET
            ):
                status = "PROVEN90"
            elif (
                tr["hit"] is not None
                and ho["hit"] is not None
                and tr["n"] >= MIN_N
                and ho["n"] >= max(5, MIN_N // 2)
                and min(tr["hit"], ho["hit"]) >= 85
            ):
                status = "NEAR85"
            elif allr["hit"] is not None and allr["n"] >= MIN_N and allr["hit"] >= TARGET:
                status = "ALL90_CHECK_SPLIT"
            rows.append(
                {
                    "sym": pack["sym"],
                    "t1": t1,
                    "gate": gname,
                    "cut": cut,
                    "tr": {k: tr[k] for k in ("n", "hit", "cover", "avg_pts", "w", "l")},
                    "ho": {k: ho[k] for k in ("n", "hit", "cover", "avg_pts", "w", "l")},
                    "all": {k: allr[k] for k in ("n", "hit", "cover", "avg_pts", "w", "l")},
                    "status": status,
                    "months_hold": month_hits(ho["calls"]) if ho["n"] else [],
                }
            )
            if status.startswith("PROVEN") or status.startswith("NEAR") or status.startswith("ALL"):
                print(
                    f"    T{t1:.0f} {gname}: train {tr['hit']}%/{tr['n']} hold {ho['hit']}%/{ho['n']} [{status}]",
                    flush=True,
                )
    return rows, cut, days


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("DEEP ≥90% S/R+IND+EMA34 trail · NIFTY+BN (RESEARCH ONLY)", flush=True)

    nifty = load_nifty()
    bn = load_bn()

    n_rows, n_cut, n_days = run_symbol(nifty, [12.0, 15.0, 20.0], HOLD_LO)
    # BN: use mid cut ~2026-05-01 like prior BN study
    b_rows, b_cut, b_days = run_symbol(bn, [12.0, 15.0, 20.0, 25.0], "2026-05-03")

    all_rows = n_rows + b_rows
    proven = [r for r in all_rows if r["status"] == "PROVEN90"]
    near = [r for r in all_rows if r["status"] in ("NEAR85", "ALL90_CHECK_SPLIT")]

    # cross-symbol: same gate+t1 proven/near on both
    def key(r):
        return (r["gate"], r["t1"])

    nifty_ok = {key(r): r for r in n_rows if r["status"] in ("PROVEN90", "NEAR85") and r["ho"]["hit"] and r["ho"]["hit"] >= 85}
    bn_ok = {key(r): r for r in b_rows if r["status"] in ("PROVEN90", "NEAR85") and r["ho"]["hit"] and r["ho"]["hit"] >= 85}
    both = []
    for k in sorted(set(nifty_ok) & set(bn_ok), key=lambda x: (-min(nifty_ok[x]["ho"]["hit"], bn_ok[x]["ho"]["hit"]), x[0])):
        both.append({"gate": k[0], "t1": k[1], "nifty": nifty_ok[k], "bn": bn_ok[k]})

    # best per symbol by hold hit then cover
    def best_list(rows, k=12):
        cand = [r for r in rows if r["ho"]["hit"] is not None and r["ho"]["n"] >= 5]
        cand.sort(key=lambda r: (-(r["ho"]["hit"] or 0), -(r["ho"]["cover"] or 0), -r["t1"]))
        return cand[:k]

    lines = [
        "# ALL 1m — S/R + Indicators + EMA34 Trail · Hunt ≥90%",
        "",
        "> **RESEARCH ONLY — not wired to live Scalper.**",
        "",
        "## Locked trailing exit (this study)",
        "",
        "```",
        "Exit = EMA34 trail STRICT",
        "  • WIN  = price hits T1 BEFORE close flips against EMA34",
        "  • LOSS = close flips vs EMA34 before T1 (ma_sl) or expiry",
        "Book = 1 call / day (first gated textbook event)",
        "Session = 09:30–14:30 when gate requires sess",
        "```",
        "",
        "## Entry building blocks searched",
        "",
        "| Layer | Rules |",
        "|---|---|",
        "| **HELD** | DI_ok ∧ hard34 ∧ VWAP_with |",
        "| **S/R** | clear_path (≥1–2×ATR room) · bounce at support/resist · hold_break · not into session extreme |",
        "| **Indications** | MACD turn · ADX≥22 · DI spread≥8 · control+sweep · ind_strict3 · Tier A/B |",
        "",
        f"Proven bar: **train hit ≥{TARGET}% AND hold hit ≥{TARGET}%** · n≥{MIN_N} each.",
        "",
        f"NIFTY window `{n_days[0]}→{n_days[-1]}` cut `{n_cut}` · "
        f"BN window `{b_days[0]}→{b_days[-1]}` cut `{b_cut}`.",
        "",
        f"## PROVEN ≥{TARGET}% (train + hold)",
        "",
    ]

    if not proven:
        lines += ["**None** hit ≥90% on both train and hold with min n.", ""]
    else:
        lines += [
            "| Sym | T1 | Gate | Train hit/n | Hold hit/n | Hold cover | avgPts hold |",
            "|---|---:|---|---|---|---:|---:|",
        ]
        proven.sort(key=lambda r: (-r["ho"]["hit"], -r["ho"]["n"], r["sym"]))
        for r in proven:
            lines.append(
                f"| {r['sym']} | {r['t1']:.0f} | `{r['gate']}` | "
                f"**{r['tr']['hit']}%**/{r['tr']['n']} | **{r['ho']['hit']}%**/{r['ho']['n']} | "
                f"{r['ho']['cover']}% | {r['ho']['avg_pts']} |"
            )
        lines.append("")

    lines += [
        "## Cross-symbol (NIFTY ∧ BN hold ≥85%)",
        "",
    ]
    if not both:
        lines += ["No shared gate cleared ≥85% hold on **both** symbols in this sweep.", ""]
    else:
        lines += [
            "| T1 | Gate | NIFTY hold | BN hold |",
            "|---:|---|---|---|",
        ]
        for b in both[:25]:
            lines.append(
                f"| {b['t1']:.0f} | `{b['gate']}` | "
                f"**{b['nifty']['ho']['hit']}%**/{b['nifty']['ho']['n']} | "
                f"**{b['bn']['ho']['hit']}%**/{b['bn']['ho']['n']} |"
            )
        lines.append("")

    lines += [
        "## NEAR (≥85 both splits or ALL≥90)",
        "",
        "| Sym | T1 | Gate | Train | Hold | All | status |",
        "|---|---:|---|---|---|---|---|",
    ]
    near.sort(key=lambda r: (-(r["ho"]["hit"] or 0), r["sym"]))
    for r in near[:40]:
        lines.append(
            f"| {r['sym']} | {r['t1']:.0f} | `{r['gate']}` | "
            f"{r['tr']['hit']}%/{r['tr']['n']} | {r['ho']['hit']}%/{r['ho']['n']} | "
            f"{r['all']['hit']}%/{r['all']['n']} | {r['status']} |"
        )

    for sym, rows in (("NIFTY", n_rows), ("BANKNIFTY", b_rows)):
        lines += [
            "",
            f"## Best hold hit — {sym} (top gates)",
            "",
            "| T1 | Gate | Hold hit | n | cover | Train hit | All hit | status |",
            "|---:|---|---:|---:|---:|---:|---:|---|",
        ]
        for r in best_list(rows, 15):
            lines.append(
                f"| {r['t1']:.0f} | `{r['gate']}` | **{r['ho']['hit']}** | {r['ho']['n']} | "
                f"{r['ho']['cover']} | {r['tr']['hit']} | {r['all']['hit']} | {r['status']} |"
            )

    # propose locked logic if any proven exists
    lines += [
        "",
        "## Proposed locked logic (if PROVEN90 exists)",
        "",
    ]
    if proven:
        # prefer gates that appear for both, else best coverage proven
        pick = None
        if both:
            # prefer if also PROVEN90 on either
            for b in both:
                for side in ("nifty", "bn"):
                    if b[side]["status"] == "PROVEN90":
                        pick = b
                        break
                if pick:
                    break
            if pick is None:
                pick = both[0]
            lines += [
                "### Shared-style candidate",
                "",
                f"- **Gate:** `{pick['gate']}`",
                f"- **T1:** {pick['t1']:.0f}",
                f"- **Trail:** EMA34 strict",
                f"- NIFTY hold: {pick['nifty']['ho']['hit']}% / {pick['nifty']['ho']['n']}",
                f"- BN hold: {pick['bn']['ho']['hit']}% / {pick['bn']['ho']['n']}",
                "",
            ]
        # top proven each sym
        for sym in ("NIFTY", "BANKNIFTY"):
            ps = [r for r in proven if r["sym"] == sym]
            if not ps:
                lines.append(f"- **{sym}:** no PROVEN90 in this sweep")
                continue
            r = max(ps, key=lambda x: (x["ho"]["hit"], x["ho"]["cover"], x["ho"]["n"]))
            lines += [
                f"### {sym}",
                "",
                "```",
                f"IF {r['gate']}",
                f"THEN enter · T1={r['t1']:.0f} · exit=EMA34 trail strict · 1/day",
                "```",
                f"Train **{r['tr']['hit']}%**/{r['tr']['n']} · Hold **{r['ho']['hit']}%**/{r['ho']['n']} · cover {r['ho']['cover']}%",
                "",
            ]
    else:
        lines += [
            "No ≥90% train+hold lock yet. Strongest near-gates listed above.",
            "Next deepen: purified fingerprints (100% train cells) ∪ HELD+S/R, "
            "2-bar confirm, ATR-scaled T1 for BN, ratchet trail after +12.",
            "",
        ]

    lines += [
        "## Accuracy note",
        "",
        "≥90% here means **trade hit-rate under EMA34 trail + T1**, not raw MFE Acc%.",
        "MFE-only Acc% ceilings ~50–60% on HELD — trailing + target is required for 90% books.",
        "",
        f"Elapsed {time.time() - t0:.0f}s",
        "",
        "**Not live** until a PROVEN90 gate is explicitly approved for wiring.",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "proven": proven,
                "near": near[:60],
                "both": [
                    {
                        "gate": b["gate"],
                        "t1": b["t1"],
                        "nifty_hold": b["nifty"]["ho"],
                        "bn_hold": b["bn"]["ho"],
                    }
                    for b in both[:30]
                ],
                "nifty_cut": n_cut,
                "bn_cut": b_cut,
                "target": TARGET,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {REPORT}", flush=True)
    print(f"PROVEN90={len(proven)} NEAR={len(near)} BOTH≥85={len(both)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
