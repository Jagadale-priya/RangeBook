"""ANALYSIS ONLY — last ~5 sessions NIFTY 1m.

Annotate support/resistance, day H/L, OR range, HH/HL/LH/LL, expansions, textbook
patterns. No entries, no stops, no calls.

  python -u prod_live/tests/builders/_diag_scalp_analysis_watch_5d.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path[:0] = [
    str(ROOT),
    str(BUILDERS),
    str(ROOT / "tools" / "research"),
    str(ROOT / "app"),
    str(ROOT / "app" / "market"),
    str(ROOT / "app" / "fno"),
]
import path_setup  # noqa: F401

from _diag_scalp_pa_bos_choch_fvg import _norm_1m, swing_points  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_daily_must_100 as dm  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_1M_ANALYSIS_WATCH_LAST5D.json"


def load_5d() -> pd.DataFrame:
    try:
        import kite_data

        df, err = kite_data.fetch_historical_candles(
            "NIFTY", "minute", days=5, keep_partial=True
        )
        if df is not None and len(df):
            print(f"kite 1m: {len(df)} bars · {df.index[0]} → {df.index[-1]}", flush=True)
            return _norm_1m(df)
        print(f"kite miss: {err} — falling back to cache", flush=True)
    except Exception as exc:
        print(f"kite err: {exc} — falling back to cache", flush=True)
    import research_nifty_1m_dual_clean_train as base

    raw = _norm_1m(base.load_existing_1m())
    days = sorted({str(ts.date()) for ts in raw.index})
    keep = set(days[-5:])
    return raw[[str(ts.date()) in keep for ts in raw.index]].copy()


def session_levels(df: pd.DataFrame) -> List[dict]:
    rows = []
    for d, sess in df.groupby([str(ts.date()) for ts in df.index]):
        if len(sess) < 5:
            continue
        or_bars = sess.iloc[:15]
        day_hi = float(sess["High"].max())
        day_lo = float(sess["Low"].min())
        or_hi = float(or_bars["High"].max())
        or_lo = float(or_bars["Low"].min())
        # accuracy check
        ok_hi = abs(day_hi - float(sess["High"].max())) < 1e-9
        ok_or = len(or_bars) == min(15, len(sess))
        rows.append(
            {
                "day": d,
                "n": int(len(sess)),
                "day_hi": round(day_hi, 2),
                "day_lo": round(day_lo, 2),
                "or_hi": round(or_hi, 2),
                "or_lo": round(or_lo, 2),
                "range": round(day_hi - day_lo, 2),
                "checks": {"day_hl_ok": ok_hi, "or_15_ok": ok_or},
            }
        )
    return rows


def main() -> int:
    df = load_5d()
    days = sorted({str(ts.date()) for ts in df.index})
    last = days[-1]
    print(f"sessions {days} · last={last} · bars={len(df)}", flush=True)

    o = df["Open"].astype(float)
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    c = df["Close"].astype(float)
    tr = pd.concat(
        [(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1
    ).max(axis=1)
    atr = tr.rolling(14, min_periods=1).mean()
    body = (c - o).abs()
    rng = (h - l).replace(0, np.nan)
    exp = (body >= 0.85 * atr) & (body / rng >= 0.55)
    pos = (c - l) / rng
    bull_exp = exp & (c > o) & (pos >= 0.75)
    bear_exp = exp & (c < o) & (pos <= 0.25)

    work = tb.detect_textbook(df)
    patterns: List[Any] = []
    for i in range(len(work)):
        row = work.iloc[i]
        hits = [p for p in dm.PRIORITY if p in work.columns and int(row.get(p, 0) or 0) == 1]
        patterns.append(hits[0] if hits else None)

    sh, sl = swing_points(h.values, l.values, L=3)
    sh_set, sl_set = set(sh), set(sl)

    sessions = session_levels(df)
    sess = df[[str(ts.date()) == last for ts in df.index]]
    gpos = {ts: i for i, ts in enumerate(df.index)}

    # structure labels on last day
    swings = []
    last_h = last_l = None
    for ts in sess.index:
        i = gpos[ts]
        if i in sh_set:
            px = round(float(h.iloc[i]), 2)
            lab = "HH" if last_h is not None and px > last_h else ("LH" if last_h is not None else "H")
            last_h = px
            swings.append({"t": ts.strftime("%H:%M"), "kind": "H", "label": lab, "px": px})
        if i in sl_set:
            px = round(float(l.iloc[i]), 2)
            lab = "HL" if last_l is not None and px > last_l else ("LL" if last_l is not None else "L")
            last_l = px
            swings.append({"t": ts.strftime("%H:%M"), "kind": "L", "label": lab, "px": px})

    candles = []
    pat_counts: Dict[str, int] = {}
    exp_n = 0
    for ts in sess.index:
        i = gpos[ts]
        pat = patterns[i]
        if pat:
            pat_counts[pat] = pat_counts.get(pat, 0) + 1
        expansion = "BUY" if bool(bull_exp.iloc[i]) else ("SELL" if bool(bear_exp.iloc[i]) else None)
        if expansion:
            exp_n += 1
        candles.append(
            {
                "t": ts.strftime("%H:%M"),
                "o": round(float(o.iloc[i]), 2),
                "h": round(float(h.iloc[i]), 2),
                "l": round(float(l.iloc[i]), 2),
                "c": round(float(c.iloc[i]), 2),
                "pattern": pat,
                "expansion": expansion,
                "swing_h": i in sh_set,
                "swing_l": i in sl_set,
                "atr": round(float(atr.iloc[i]), 2),
            }
        )

    # accuracy probes
    day_row = next(s for s in sessions if s["day"] == last)
    recomputed_hi = max(x["h"] for x in candles)
    recomputed_lo = min(x["l"] for x in candles)
    or15 = candles[:15]
    checks = {
        "day_hi_matches_candles": abs(day_row["day_hi"] - recomputed_hi) < 0.011,
        "day_lo_matches_candles": abs(day_row["day_lo"] - recomputed_lo) < 0.011,
        "or_hi_matches_first15": abs(day_row["or_hi"] - max(x["h"] for x in or15)) < 0.011,
        "or_lo_matches_first15": abs(day_row["or_lo"] - min(x["l"] for x in or15)) < 0.011,
        "n_bars_session": len(candles),
        "expansion_bars_have_large_body": all(
            (abs(x["c"] - x["o"]) >= 0.85 * x["atr"] - 1e-6)
            for x in candles
            if x["expansion"]
        ),
        "pattern_names_in_priority": all(
            (x["pattern"] in dm.PRIORITY) for x in candles if x["pattern"]
        ),
    }

    # downsample chart series every 2m for canvas size, keep event markers full
    chart = candles[::2]
    events = [
        x
        for x in candles
        if x["pattern"] or x["expansion"] or x["swing_h"] or x["swing_l"]
    ]

    out = {
        "mode": "analysis_watch_only",
        "no_entries": True,
        "success_rate_note": {
            "book": "SELL_opp_am1300_sl8_t18",
            "oos_hit_pct": 39.12,
            "train_hit_pct": 39.15,
            "oos_exp_R": 0.266,
            "meaning": "Success rate = % of that book's trades that hit T18 before ~8pt stop (OOS). Not pattern frequency.",
        },
        "window_days": days,
        "last_day": last,
        "sessions": sessions,
        "last_day_bars": len(candles),
        "pattern_counts": dict(sorted(pat_counts.items(), key=lambda kv: -kv[1])),
        "expansion_bars": exp_n,
        "structure": swings,
        "accuracy_checks": checks,
        "candles_1m": candles,
        "chart_downsample_2m": chart,
        "events": events,
        "support_resistance": {
            "day_high": day_row["day_hi"],
            "day_low": day_row["day_lo"],
            "or_high": day_row["or_hi"],
            "or_low": day_row["or_lo"],
            "note": "S/R here = day H/L + opening-range (first 15×1m). Swing HH/LL listed in structure.",
        },
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    slim_path = OUT.parent / "_analysis_watch_canvas_slim.json"
    slim = {
        "success_rate_note": out["success_rate_note"],
        "window_days": days,
        "last_day": last,
        "sessions": sessions,
        "pattern_counts": out["pattern_counts"],
        "expansion_bars": exp_n,
        "last_day_bars": len(candles),
        "accuracy_checks": checks,
        "support_resistance": out["support_resistance"],
        "structure": swings,
        "candles_1m": candles,
    }
    slim_path.write_text(json.dumps(slim, separators=(",", ":")), encoding="utf-8")
    print("accuracy", json.dumps(checks, indent=2), flush=True)
    print(f"patterns {pat_counts}", flush=True)
    print(f"expansions {exp_n} swings {len(swings)} events {len(events)}", flush=True)
    print(f"wrote {OUT}", flush=True)
    print(f"wrote slim {slim_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
