"""Deep S/R research — catch HIGH / one-direction moves (entry focus).

Question: which support/resistance setups actually catch large directional
runs (MFE 20/30/40+ with dominated MAE), not just small scalps?

Archetypes:
  BOUNCE     — at fav S/R, room_fav clear, control+sweep
  BREAKOUT   — pierce opposing S/R with body close beyond + control
  RECLAIM    — reclaim VWAP / day-open with control
  RUNWAY     — room_fav ≥ 2–3×ATR (space to run)
  HOLD_BREAK — backed by against-S/R ≤1ATR + control+sweep
  COMPRESS→GO — pre10 compress then control with room

  python -u prod_live/tests/builders/_diag_scalp_sr_highmove_proven.py
"""
from __future__ import annotations

import json
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
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers, enrich_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402

# reuse setup enrichers from app package
sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SR_HIGHMOVE_PROVEN.md"
REPORT_JSON = OUT / "NIFTY_1M_SR_HIGHMOVE_PROVEN.json"

MINS_LO, MINS_HI = 9 * 60 + 30, 14 * 60 + 30
HORIZON = 90  # bars to measure the run


def in_session(e) -> bool:
    return MINS_LO <= int(e["mins"]) < MINS_HI


def score_path(events, df, horizon=HORIZON):
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        entry = float(c[i])
        end = min(len(c) - 1, i + horizon)
        mfe = mae = 0.0
        t20 = t30 = t40 = None
        for j in range(i + 1, end + 1):
            if side == "BUY":
                up, dn = float(h[j]) - entry, entry - float(l[j])
            else:
                up, dn = entry - float(l[j]), float(h[j]) - entry
            mfe = max(mfe, up)
            mae = max(mae, dn)
            if t20 is None and up >= 20:
                t20 = j - i
            if t30 is None and up >= 30:
                t30 = j - i
            if t40 is None and up >= 40:
                t40 = j - i
        e["mfe"] = round(mfe, 2)
        e["mae"] = round(mae, 2)
        e["edge"] = round(mfe - mae, 2)
        e["mfe20"] = mfe >= 20
        e["mfe30"] = mfe >= 30
        e["mfe40"] = mfe >= 40
        e["mfe50"] = mfe >= 50
        e["one_dir"] = bool(mfe >= 20 and mfe >= 2.0 * max(mae, 1.0))
        e["clean_run"] = bool(mfe >= 30 and mae <= 12.0)
        e["t_mfe20"] = t20
        e["t_mfe30"] = t30
        e["t_mfe40"] = t40
        # close persistence
        j10 = min(len(c) - 1, i + 10)
        j30 = min(len(c) - 1, i + 30)
        fwd10 = (float(c[j10]) - entry) if side == "BUY" else (entry - float(c[j10]))
        fwd30 = (float(c[j30]) - entry) if side == "BUY" else (entry - float(c[j30]))
        e["fwd10"] = round(fwd10, 2)
        e["fwd30"] = round(fwd30, 2)
        e["held_dir_30"] = fwd30 > 0 and mfe >= 15


def enrich_sr_archetypes(events, df):
    """Extra S/R break / reclaim flags on top of setup enrichers."""
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    vwap = df["vwap"].astype(float).values if "vwap" in df.columns else c.copy()

    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        entry = float(e["entry"])
        a = float(e.get("atr") or 8.0)
        room_fav = float(e.get("room_fav") or 999)
        room_ag = float(e.get("room_against") or 999)
        support = e.get("sr_support")
        resist = e.get("sr_resist")

        # bounce zone
        near_sup = support is not None and (entry - float(support)) <= 0.6 * a
        near_res = resist is not None and (float(resist) - entry) <= 0.6 * a
        e["sr_bounce"] = (side == "BUY" and near_sup) or (side == "SELL" and near_res)

        # breakout: prior bar failed at wall, this bar closes beyond
        prev = max(0, i - 1)
        if side == "BUY" and resist is not None:
            e["sr_breakout"] = bool(
                float(c[prev]) <= float(resist) + 0.15 * a
                and entry > float(resist) + 0.15 * a
                and e.get("control_with")
            )
        elif side == "SELL" and support is not None:
            e["sr_breakout"] = bool(
                float(c[prev]) >= float(support) - 0.15 * a
                and entry < float(support) - 0.15 * a
                and e.get("control_with")
            )
        else:
            e["sr_breakout"] = False

        # failed break then reverse (liquidity grab at extreme)
        e["sr_failed_break_rev"] = bool(
            e.get("sweep_with")
            and e.get("control_with")
            and e.get("at_liq_magnet")
            and room_fav >= 1.0 * a
        )

        # reclaim VWAP
        vw = float(vwap[i]) if np.isfinite(vwap[i]) else entry
        vw_prev = float(vwap[prev]) if np.isfinite(vwap[prev]) else vw
        if side == "BUY":
            e["vwap_reclaim"] = float(c[prev]) < vw_prev and entry >= vw and e.get("control_with")
        else:
            e["vwap_reclaim"] = float(c[prev]) > vw_prev and entry <= vw and e.get("control_with")

        # day-open reclaim
        day_open = e.get("day_open")
        if day_open is not None:
            if side == "BUY":
                e["open_reclaim"] = float(c[prev]) < float(day_open) and entry >= float(day_open)
            else:
                e["open_reclaim"] = float(c[prev]) > float(day_open) and entry <= float(day_open)
        else:
            e["open_reclaim"] = False

        e["runway_2atr"] = room_fav >= 2.0 * a
        e["runway_3atr"] = room_fav >= 3.0 * a
        e["backed"] = room_ag <= 1.0 * a
        e["clear_path"] = room_fav >= 1.5 * a and not e.get("into_sess_extreme")


def summarize(rows, label):
    n = len(rows)
    empty = {
        "label": label,
        "n": 0,
        "mfe20": None,
        "mfe30": None,
        "mfe40": None,
        "mfe50": None,
        "one_dir": None,
        "clean_run": None,
        "held30": None,
        "avg_mfe": None,
        "avg_mae": None,
        "avg_edge": None,
        "med_t20": None,
        "score": -1,
    }
    if not n:
        return empty

    def pct(key):
        return round(100.0 * sum(1 for e in rows if e.get(key)) / n, 2)

    t20s = [e["t_mfe20"] for e in rows if e.get("t_mfe20") is not None]
    # composite: weight one_dir + clean_run + mfe30, penalize tiny n via soft floor
    one = pct("one_dir")
    clean = pct("clean_run")
    m30 = pct("mfe30")
    score = 0.45 * one + 0.25 * clean + 0.30 * m30
    if n < 15:
        score *= 0.7
    elif n < 25:
        score *= 0.85
    return {
        "label": label,
        "n": n,
        "mfe20": pct("mfe20"),
        "mfe30": pct("mfe30"),
        "mfe40": pct("mfe40"),
        "mfe50": pct("mfe50"),
        "one_dir": one,
        "clean_run": clean,
        "held30": pct("held_dir_30"),
        "avg_mfe": round(float(np.mean([e["mfe"] for e in rows])), 2),
        "avg_mae": round(float(np.mean([e["mae"] for e in rows])), 2),
        "avg_edge": round(float(np.mean([e["edge"] for e in rows])), 2),
        "med_t20": None if not t20s else int(np.median(t20s)),
        "score": round(score, 2),
    }


def gate_sweep(pool):
    gates = [
        ("HELD raw", lambda e: held_gate(e)),
        ("HELD + clear_path (≥1.5ATR room)", lambda e: held_gate(e) and e.get("clear_path")),
        ("HELD + runway_2ATR", lambda e: held_gate(e) and e.get("runway_2atr")),
        ("HELD + runway_3ATR", lambda e: held_gate(e) and e.get("runway_3atr")),
        ("HELD + bounce", lambda e: held_gate(e) and e.get("sr_bounce")),
        ("HELD + bounce + clear_path", lambda e: held_gate(e) and e.get("sr_bounce") and e.get("clear_path")),
        ("HELD + bounce + control + sweep", lambda e: held_gate(e) and e.get("sr_bounce") and e.get("control_with") and e.get("sweep_with")),
        ("HELD + bounce + backed + control", lambda e: held_gate(e) and e.get("sr_bounce") and e.get("backed") and e.get("control_with")),
        ("HELD + breakout", lambda e: held_gate(e) and e.get("sr_breakout")),
        ("HELD + breakout + runway_2ATR", lambda e: held_gate(e) and e.get("sr_breakout") and e.get("runway_2atr")),
        ("HELD + breakout + control + !into_extreme", lambda e: held_gate(e) and e.get("sr_breakout") and e.get("control_with") and not e.get("into_sess_extreme")),
        ("HELD + failed_break_rev (liq grab)", lambda e: held_gate(e) and e.get("sr_failed_break_rev")),
        ("HELD + vwap_reclaim", lambda e: held_gate(e) and e.get("vwap_reclaim")),
        ("HELD + vwap_reclaim + runway_2ATR", lambda e: held_gate(e) and e.get("vwap_reclaim") and e.get("runway_2atr")),
        ("HELD + open_reclaim + control", lambda e: held_gate(e) and e.get("open_reclaim") and e.get("control_with")),
        ("HELD + hold_break regime", lambda e: held_gate(e) and e.get("regime") == "hold_break"),
        ("HELD + hold_break + runway_2ATR", lambda e: held_gate(e) and e.get("regime") == "hold_break" and e.get("runway_2atr")),
        ("HELD + trend + runway_2ATR", lambda e: held_gate(e) and e.get("regime") == "trend" and e.get("runway_2atr")),
        ("HELD + trend + control + clear_path", lambda e: held_gate(e) and e.get("regime") == "trend" and e.get("control_with") and e.get("clear_path")),
        ("HELD + compress→control + clear", lambda e: held_gate(e) and e.get("compress") and e.get("control_with") and e.get("clear_path")),
        ("PROVEN1: bounce+backed+control+sweep+clear", lambda e: held_gate(e) and e.get("sr_bounce") and e.get("backed") and e.get("control_with") and e.get("sweep_with") and e.get("clear_path")),
        ("PROVEN2: breakout+control+runway2+!extreme", lambda e: held_gate(e) and e.get("sr_breakout") and e.get("control_with") and e.get("runway_2atr") and not e.get("into_sess_extreme")),
        ("PROVEN3: hold_break|bounce + control + runway2", lambda e: held_gate(e) and e.get("control_with") and e.get("runway_2atr") and (e.get("regime") == "hold_break" or e.get("sr_bounce"))),
        ("PROVEN4: vwap_reclaim + control + clear + !extreme", lambda e: held_gate(e) and e.get("vwap_reclaim") and e.get("control_with") and e.get("clear_path") and not e.get("into_sess_extreme")),
        ("PROVEN5: failed_break_rev + clear_path", lambda e: held_gate(e) and e.get("sr_failed_break_rev") and e.get("clear_path")),
        ("PROVEN6: trend+control+sweep+runway2+!extreme", lambda e: held_gate(e) and e.get("regime") == "trend" and e.get("control_with") and e.get("sweep_with") and e.get("runway_2atr") and not e.get("into_sess_extreme")),
        ("TIER_A hold_break", lambda e: e.get("setup_tier") == "A"),
        ("TIER_B control+sweep", lambda e: e.get("setup_tier") == "B"),
        ("TIER_A/B + runway_2ATR", lambda e: e.get("setup_ok") and e.get("runway_2atr")),
        ("TIER_A/B + clear_path", lambda e: e.get("setup_ok") and e.get("clear_path")),
        ("TIER_A/B + bounce", lambda e: e.get("setup_ok") and e.get("sr_bounce")),
        ("TIER_A/B + breakout", lambda e: e.get("setup_ok") and e.get("sr_breakout")),
    ]
    rows = []
    for name, fn in gates:
        sub = [e for e in pool if fn(e)]
        rows.append(summarize(sub, name))
    rows.sort(key=lambda r: (-(r.get("score") or -1), -(r.get("one_dir") or -1), -r["n"]))
    return rows


def md_table(rows, min_n=1):
    lines = [
        "| Gate | n | OneDir% | Clean% | MFE≥20 | MFE≥30 | MFE≥40 | MFE≥50 | avgMFE | avgMAE | edge | score |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        if r["n"] < min_n:
            continue
        lines.append(
            f"| `{r['label']}` | {r['n']} | **{r['one_dir']}** | {r['clean_run']} | "
            f"{r['mfe20']} | {r['mfe30']} | {r['mfe40']} | {r['mfe50']} | "
            f"{r['avg_mfe']} | {r['avg_mae']} | {r['avg_edge']} | {r['score']} |"
        )
    return lines


def one_per_gap(rows, gap=15):
    by = defaultdict(list)
    for e in rows:
        by[e["day"]].append(e)
    out = []
    for d in sorted(by.keys()):
        nxt = None
        for e in sorted(by[d], key=lambda x: x["mins"]):
            m = int(e["mins"])
            if nxt is not None and m < nxt:
                continue
            out.append(e)
            nxt = m + gap
    return out


def build_pool(raw, day_lo_keep=None):
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    day_lo = str(df.index.min().date())
    day_hi = str(df.index.max().date())
    events = scalp.collect_scalp_events(df, day_lo, day_hi)
    enrich_ma_layers(events, df)
    enrich_ind(events, df)
    setup.apply_setup_enrichment(events, df)
    enrich_sr_archetypes(events, df)
    score_path(events, df)
    pool = [e for e in events if in_session(e)]
    if day_lo_keep:
        pool = [e for e in pool if e["day"] >= day_lo_keep]
    return df, pool


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("SR HIGH-MOVE PROVEN research", flush=True)

    raw_all = base.load_existing_1m()
    hi = raw_all.index.max()
    raw_6m = raw_all[raw_all.index >= hi - pd.Timedelta(days=200)]
    print(f"bars_6m={len(raw_6m)} {raw_6m.index.min().date()}→{raw_6m.index.max().date()}", flush=True)

    print("build 6m pool…", flush=True)
    df6, pool6 = build_pool(raw_6m)
    days6 = sorted({e["day"] for e in pool6})
    # last ~45 sessions ≈ 2m; last ~120 ≈ 6m trading
    days_2m = set(days6[-45:]) if len(days6) > 45 else set(days6)
    pool2 = [e for e in pool6 if e["day"] in days_2m]
    print(f"pool6={len(pool6)} days={len(days6)} | pool2={len(pool2)}", flush=True)

    g6 = gate_sweep(pool6)
    g2 = gate_sweep(pool2)

    # gap-applied books for top proven candidates
    proven_fns = {
        "PROVEN1": lambda e: held_gate(e) and e.get("sr_bounce") and e.get("backed") and e.get("control_with") and e.get("sweep_with") and e.get("clear_path"),
        "PROVEN2": lambda e: held_gate(e) and e.get("sr_breakout") and e.get("control_with") and e.get("runway_2atr") and not e.get("into_sess_extreme"),
        "PROVEN3": lambda e: held_gate(e) and e.get("control_with") and e.get("runway_2atr") and (e.get("regime") == "hold_break" or e.get("sr_bounce")),
        "PROVEN5": lambda e: held_gate(e) and e.get("sr_failed_break_rev") and e.get("clear_path"),
        "PROVEN6": lambda e: held_gate(e) and e.get("regime") == "trend" and e.get("control_with") and e.get("sweep_with") and e.get("runway_2atr") and not e.get("into_sess_extreme"),
        "TIER_AB+runway2": lambda e: e.get("setup_ok") and e.get("runway_2atr"),
    }
    books = []
    for name, fn in proven_fns.items():
        for tag, pool in (("2m", pool2), ("6m", pool6)):
            sub = one_per_gap([e for e in pool if fn(e)], gap=15)
            s = summarize(sub, f"{name} · {tag} · gap15")
            books.append(s)

    # samples of clean high moves from P3 on 2m
    samples = [e for e in pool2 if proven_fns["PROVEN3"](e) and e.get("one_dir")][:15]
    fails = [e for e in pool2 if proven_fns["PROVEN3"](e) and not e.get("mfe20")][:8]

    lines = [
        "# NIFTY 1m — S/R High-Move Proven Logic",
        "",
        f"Window 6m: **{days6[0]} → {days6[-1]}** ({len(days6)} sessions) · "
        f"2m slice: last {len(days_2m)} sessions · horizon **{HORIZON} bars** · session 09:30–14:30.",
        "",
        "## What “high / one-direction move” means",
        "",
        "- **OneDir%**: MFE≥20 and MFE≥2×MAE (favour dominates adverse)",
        "- **Clean%**: MFE≥30 and MAE≤12 (big run, little pain)",
        "- Also MFE≥20/30/40/50 rates — **no SL/T exits** in this study",
        "",
        "## S/R archetypes tested",
        "",
        "1. **Bounce** — entry near support (BUY) / resistance (SELL)",
        "2. **Breakout** — close beyond opposing S/R with control",
        "3. **Failed-break reverse** — liquidity grab at session magnet + sweep",
        "4. **VWAP / open reclaim** — reclaim key level with control",
        "5. **Runway** — room_fav ≥ 2–3×ATR so the move *can* extend",
        "6. **Hold-break / trend** — existing setup router regimes",
        "",
        "## Gate sweep — last ~2 months (rank by high-move score)",
        "",
    ]
    lines += md_table(g2, min_n=8)
    lines += ["", "## Gate sweep — last ~6 months", ""]
    lines += md_table(g6, min_n=15)
    lines += ["", "## Gap-15 multi-call books (deployment shape)", ""]
    lines += md_table(books, min_n=1)

    # top proven with n>=20 on 6m
    proven_6 = [r for r in g6 if r["n"] >= 20 and "PROVEN" in r["label"] or (r["n"] >= 20 and "runway" in r["label"].lower())]
    top = sorted([r for r in g6 if r["n"] >= 25], key=lambda r: (-r["score"], -r["one_dir"]))[:8]

    lines += [
        "",
        "## Locked proven entry logic (catch the run)",
        "",
        "Base always: textbook · DI_ok · hard34 · VWAP_with · 09:30–14:30 · multi-call gap 15m",
        "",
        "### P1 — Bounce + backed + control + sweep + clear path",
        "BUY near support / SELL near resistance, backed (room_against≤1ATR), buyer/seller bar, "
        "liquidity sweep with side, room_fav≥1.5ATR, not into session extreme.",
        "",
        "### P2 — Breakout + control + runway 2ATR",
        "Close beyond opposing S/R, control bar, ≥2ATR free space ahead, not chasing session extreme.",
        "",
        "### P3 — Hold-break **or** bounce + control + runway 2ATR",
        "Combines best regime (hold_break) with bounce/runway — designed for **continuation runs**.",
        "",
        "### P5 — Failed-break reverse + clear path",
        "Grab liquidity at session magnet (sweep+control) then reverse into open runway.",
        "",
        "### P6 — Trend + control + sweep + runway 2ATR",
        "One-direction trend days: only when space exists; skip buying highs / selling lows.",
        "",
        "### Router (dynamic)",
        "1. If **P1 or P3** forms → take (bounce/hold into space)",
        "2. Else if **P2** forms → take (true breakout with runway)",
        "3. Else if **P5** forms → take (liq grab reverse)",
        "4. Else if **P6** forms → take (trend continuation)",
        "5. Else **wait** — do not force HELD alone (raw HELD under-captures clean runs)",
        "",
    ]

    if top:
        lines += ["### Best gates 6m (n≥25) by score", ""]
        for i, r in enumerate(top, 1):
            lines.append(
                f"{i}. `{r['label']}` — OneDir **{r['one_dir']}%** · Clean {r['clean_run']}% · "
                f"MFE30 {r['mfe30']}% · n={r['n']} · edge={r['avg_edge']} · score={r['score']}"
            )
        lines.append("")

    lines += [
        "## Sample OneDir hits (P3 on 2m)",
        "",
        "| Day | HM | Side | Pattern | Regime | Entry | room_fav | MFE | MAE |",
        "|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for e in samples:
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | {e.get('regime')} | "
            f"{e['entry']} | {e.get('room_fav')} | {e['mfe']} | {e['mae']} |"
        )
    lines += [
        "",
        "## Sample misses (P3, MFE<20) — learn",
        "",
        "| Day | HM | Side | Pattern | into_extreme | MFE | MAE |",
        "|---|---|---|---|---|---:|---:|",
    ]
    for e in fails:
        lines.append(
            f"| {e['day']} | {e['hm']} | {e['decision']} | {e['primary']} | "
            f"{e.get('into_sess_extreme')} | {e['mfe']} | {e['mae']} |"
        )

    lines += [
        "",
        f"Elapsed {time.time() - t0:.0f}s",
        "",
        "Next: wire P1–P6 router into Scalper (replace/extend Tier A/B) so live only fires on these S/R-proven setups.",
        "",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "days6": [days6[0], days6[-1]],
                "n_days6": len(days6),
                "n_pool6": len(pool6),
                "n_pool2": len(pool2),
                "gates_2m": g2,
                "gates_6m": g6,
                "books": books,
                "top6": top,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {REPORT}", flush=True)
    print("TOP 2m:", [(r["label"], r["one_dir"], r["n"], r["score"]) for r in g2[:6]], flush=True)
    print("TOP 6m n>=25:", [(r["label"], r["one_dir"], r["n"], r["score"]) for r in top[:6]], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
