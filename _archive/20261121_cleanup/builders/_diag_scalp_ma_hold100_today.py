"""Run HELD MA HOLD100 logic for TODAY only — show where the call fires.

Held: DI_ok + gate_hard34 + VWAP_with · EMA34 trail · T1=12 · 1/day first
Downloads fresh NIFTY 1m if today missing.
"""
from __future__ import annotations

import sys
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
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import enrich_prior3  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers, enrich_ma_layers  # noqa: E402
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SCALP_MA_HOLD100_TODAY.md"
T1 = 12.0


def main() -> int:
    today = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
    print(f"HELD logic · today={today}", flush=True)

    raw = base.load_existing_1m()
    need_dl = raw.empty or raw.index.max().strftime("%Y-%m-%d") < today
    # also if zero bars today
    n_today = 0 if raw.empty else int(((raw.index >= today) & (raw.index < pd.Timestamp(today, tz="Asia/Kolkata") + pd.Timedelta(days=1))).sum())
    if n_today < 50:
        need_dl = True
    print(f"local end={None if raw.empty else raw.index.max()} today_bars={n_today} need_dl={need_dl}", flush=True)

    if need_dl:
        # download last few days to be safe
        start_dl = (pd.Timestamp(today) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        print(f"downloading {start_dl}→{today}…", flush=True)
        fresh, note = base.download_1m_range(start_dl, today)
        if note:
            print(f"  note: {note}", flush=True)
        if fresh is None or len(fresh) == 0:
            print("ERROR: no bars downloaded — cannot score today", flush=True)
            REPORT.write_text(
                f"# HELD today `{today}`\n\n**No 1m data** for today (download failed: {note}).\n",
                encoding="utf-8",
            )
            return 1
        # merge into working frame (don't rewrite main research cache window)
        parts = [p for p in (raw, fresh) if p is not None and len(p)]
        raw = pd.concat(parts).sort_index()
        raw = raw[~raw.index.duplicated(keep="last")]
        n_today = int(((raw.index >= today) & (raw.index < pd.Timestamp(today, tz="Asia/Kolkata") + pd.Timedelta(days=1))).sum())
        print(f"after dl end={raw.index.max()} today_bars={n_today}", flush=True)

    if n_today < 30:
        print(f"ERROR: only {n_today} bars today — market may not have enough session yet", flush=True)
        REPORT.write_text(
            f"# HELD today `{today}`\n\nOnly **{n_today}** bars so far — not enough to evaluate.\nData end: `{raw.index.max()}`\n",
            encoding="utf-8",
        )
        return 1

    # warm-up history for MA/indicators (need ~100+ bars before today)
    warm_lo = (pd.Timestamp(today) - pd.Timedelta(days=15)).strftime("%Y-%m-%d")
    work = raw[raw.index >= pd.Timestamp(warm_lo, tz="Asia/Kolkata")].copy()
    print(f"work bars={len(work)} {work.index.min()}→{work.index.max()}", flush=True)

    df = tb.detect_textbook(work)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    vix = vixmod.load_vix()

    print("collect today events…", flush=True)
    xs = scalp.collect_scalp_events(df, today, today)
    print(f"events today={len(xs)}", flush=True)
    if not xs:
        REPORT.write_text(f"# HELD today `{today}`\n\nNo textbook candle events yet.\n", encoding="utf-8")
        print("NO events", flush=True)
        return 0

    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)
    enrich_ind(xs, df)

    # score exit path for each event
    for e in xs:
        ok, reason, sl, t1 = path_ma_trail_strict(h, l, c, ema34, int(e["full_i"]), e["decision"], T1)
        e["_win"] = bool(ok)
        e["_reason"] = reason
        e["_sl"] = float(sl or 0)
        e["_t1"] = float(t1)

    gated = [e for e in sorted(xs, key=lambda x: x["mins"]) if held_gate(e)]
    call = gated[0] if gated else None

    # also show near-misses: each gate flag
    lines = [
        f"# HELD logic — **today `{today}`**",
        "",
        "Gate: `DI_ok` + `EMA34 hard` + `VWAP_with` · Hold: EMA34 trail · **T1=12** · 1/day first",
        f"Data: `{work.index.min()}` → `{work.index.max()}` · today bars **{n_today}** · events **{len(xs)}** · gated **{len(gated)}**",
        "",
    ]

    if call is None:
        lines += ["## Call: **NO_CALL** (no bar passed all 3 gates yet)", ""]
        print("CALL: NO_CALL", flush=True)
    else:
        mark = "WIN path so far" if call["_win"] else f"LOSS/open ({call['_reason']})"
        entry = float(c[int(call["full_i"])])
        lines += [
            "## Call (first gated today)",
            "",
            f"| Field | Value |",
            f"|---|---|",
            f"| **Time** | **{call['hm']}** |",
            f"| **Side** | **{call['decision']}** |",
            f"| **Pattern** | **{call['primary']}** |",
            f"| Entry ~close | {entry:.2f} |",
            f"| Target T1 | **+{T1:.0f} pts** → {entry+T1 if call['decision']=='BUY' else entry-T1:.2f} |",
            f"| Stop | close flips vs EMA34 (trail) |",
            f"| Path so far | {mark} · MFE={call.get('mfe',0):.1f} |",
            f"| Gates | DI={int(bool(call.get('di_ok')))} hard34={int(bool(call.get('gate_hard34')))} VWAP={int(bool(call.get('vwap_with')))} |",
            "",
        ]
        print(
            f"CALL: {call['hm']} {call['decision']} {call['primary']} entry~{entry:.2f} "
            f"T1={T1} path={call['_win']} {call['_reason']} mfe={call.get('mfe',0):.1f}",
            flush=True,
        )

    # all gated candidates chronologically
    lines += ["## All gated candidates today (in order)", "", "| # | HM | Side | Pattern | DI | hard34 | VWAP | path | reason | MFE |", "|---:|---|---|---|---:|---:|---:|---|---|---:|"]
    if not gated:
        lines.append("| — | — | — | — | | | | | NO_CALL | |")
    else:
        for i, e in enumerate(gated, 1):
            star = " ← CALL" if call is not None and e is call else ""
            lines.append(
                f"| {i}{star} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"{int(bool(e.get('di_ok')))} | {int(bool(e.get('gate_hard34')))} | {int(bool(e.get('vwap_with')))} | "
                f"{'Y' if e['_win'] else 'N'} | {e['_reason']} | {e.get('mfe',0):.1f} |"
            )
            print(
                f"  gated {e['hm']} {e['decision']} {e['primary']} "
                f"path={'Y' if e['_win'] else 'N'} {e['_reason']}",
                flush=True,
            )

    # first 15 events with gate breakdown (why skipped)
    lines += [
        "",
        "## Early events gate check (first 20)",
        "",
        "| HM | Side | Pattern | DI | hard34 | VWAP | pass? |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for e in sorted(xs, key=lambda x: x["mins"])[:20]:
        ok = held_gate(e)
        lines.append(
            f"| {e['hm']} | {e['decision']} | {e['primary']} | "
            f"{int(bool(e.get('di_ok')))} | {int(bool(e.get('gate_hard34')))} | "
            f"{int(bool(e.get('vwap_with')))} | {'YES' if ok else 'no'} |"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
