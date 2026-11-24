"""RESEARCH ONLY — find indicators that cut hard-SL losses on locked frvp_vah_break.

Does NOT change locked_cfg. Scores filters as:
  · how many SL-exits removed
  · hit% / avgR / sum_pts after filter
  · net: keep edge, fewer stops

  python -u prod_live/tests/builders/_research_pa_reduce_sl_indicators.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
]
import kite_data  # noqa: E402
from prod_live.logic import pa_structure_live as pa  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
MD = OUT / "PA_REDUCE_SL_INDICATORS.md"
JS = OUT / "PA_REDUCE_SL_INDICATORS.json"


def rsi(closes: np.ndarray, n: int = 14) -> np.ndarray:
    out = np.full(len(closes), np.nan)
    if len(closes) < n + 1:
        return out
    d = np.diff(closes)
    up = np.where(d > 0, d, 0.0)
    dn = np.where(d < 0, -d, 0.0)
    au = np.mean(up[:n])
    ad = np.mean(dn[:n])
    out[n] = 100.0 if ad == 0 else 100.0 - (100.0 / (1.0 + au / ad))
    for i in range(n, len(d)):
        au = (au * (n - 1) + up[i]) / n
        ad = (ad * (n - 1) + dn[i]) / n
        out[i + 1] = 100.0 if ad == 0 else 100.0 - (100.0 / (1.0 + au / max(ad, 1e-12)))
    return out


def ema(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    out[n - 1] = np.mean(x[:n])
    k = 2.0 / (n + 1)
    for i in range(n, len(x)):
        out[i] = x[i] * k + out[i - 1] * (1 - k)
    return out


def session_vwap(h, l, c, v, day) -> np.ndarray:
    tp = (h + l + c) / 3.0
    out = np.full(len(c), np.nan)
    for d in sorted(set(day)):
        idxs = [i for i, x in enumerate(day) if x == d]
        cum_pv = 0.0
        cum_v = 0.0
        for i in idxs:
            vv = float(v[i]) if np.isfinite(v[i]) and v[i] > 0 else 1.0
            cum_pv += tp[i] * vv
            cum_v += vv
            out[i] = cum_pv / max(cum_v, 1e-9)
    return out


def annotate_context(bars: pd.DataFrame, calls: List[pa.PaCall]) -> List[dict]:
    work = pa.norm_1m(bars)
    o = work["Open"].astype(float).values
    h = work["High"].astype(float).values
    l = work["Low"].astype(float).values
    c = work["Close"].astype(float).values
    v = work["Volume"].astype(float).values if "Volume" in work.columns else np.ones(len(c))
    atr = pa.atr14(h, l, c)
    idx = work.index
    day = np.array([str(ts.date()) for ts in idx])
    mins = np.array([int(ts.hour * 60 + ts.minute) for ts in idx])
    rs = rsi(c, 14)
    e9 = ema(c, 9)
    e21 = ema(c, 21)
    vw = session_vwap(h, l, c, v, day)

    # map bar_i from calls — re-scan gives bar_i on same window
    by_key = {}
    for call in calls:
        by_key[(call.day, call.hm, call.side, call.setup)] = call

    rows = []
    for call in calls:
        i = int(call.bar_i)
        if i < 0 or i >= len(c):
            continue
        a = float(atr[i]) if np.isfinite(atr[i]) else 10.0
        rng = max(float(h[i]) - float(l[i]), 1e-9)
        body = abs(float(c[i]) - float(o[i])) / rng
        # vol vs prior 20
        j0 = max(0, i - 20)
        vavg = float(np.mean(v[j0:i])) if i > j0 else float(v[i])
        v_ratio = float(v[i]) / max(vavg, 1e-9)
        # chop: range of last 10 / atr
        j1 = max(0, i - 10)
        chop = float(np.max(h[j1 : i + 1]) - np.min(l[j1 : i + 1])) / max(a, 1e-9)
        # extension from OR mid approx: use day open distance
        day_idxs = [k for k, dd in enumerate(day) if dd == call.day]
        day_open = float(o[day_idxs[0]]) if day_idxs else float(o[i])
        uplift = float(c[i]) - day_open
        rows.append(
            {
                "call": call,
                "is_sl": call.exit_why == "sl",
                "win": bool(call.win),
                "rsi": float(rs[i]) if np.isfinite(rs[i]) else None,
                "ema_align": (
                    (call.side == "BUY" and e9[i] > e21[i] and c[i] > e9[i])
                    or (call.side == "SELL" and e9[i] < e21[i] and c[i] < e9[i])
                )
                if np.isfinite(e9[i]) and np.isfinite(e21[i])
                else False,
                "above_vwap": float(c[i]) >= float(vw[i]) if np.isfinite(vw[i]) else None,
                "vwap_dist_atr": (float(c[i]) - float(vw[i])) / a if np.isfinite(vw[i]) else None,
                "body": body,
                "v_ratio": v_ratio,
                "chop10": chop,
                "hm_min": int(mins[i]),
                "setup": call.setup,
                "risk": float(call.risk),
                "mfe": float(call.mfe or 0),
                "uplift": uplift,
                "atr": a,
            }
        )
    return rows


FilterFn = Callable[[dict], bool]


def apply_filter(rows: List[dict], fn: FilterFn) -> List[dict]:
    return [r for r in rows if fn(r)]


def stats(rows: List[dict]) -> Dict[str, Any]:
    if not rows:
        return {"n": 0, "hit": None, "avg_R": None, "sum_pts": None, "sl_n": 0, "sl_pct": None}
    calls = [r["call"] for r in rows]
    s = pa.summarize(calls)
    sl_n = sum(1 for r in rows if r["is_sl"])
    return {
        "n": s.get("n"),
        "hit": s.get("hit_pct"),
        "avg_R": s.get("avg_R"),
        "sum_pts": s.get("sum_pts"),
        "sl_n": sl_n,
        "sl_pct": round(100.0 * sl_n / len(rows), 1),
        "wins": s.get("wins"),
        "losses": s.get("losses"),
    }


def main() -> int:
    cfg = pa.load_locked_cfg()
    print(f"Base locked={cfg.name} (unchanged)", flush=True)
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=40, keep_partial=False
    )
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    days = sorted({str(ts.date()) for ts in bars.index})[-22:]
    window = bars[bars.index.strftime("%Y-%m-%d").isin(set(days))]
    calls = pa.scan_session(window, settle=True, cfg=cfg)
    base_sum = pa.summarize(calls)
    rows = annotate_context(window, calls)
    base_st = stats(rows)
    print(
        f"Base n={base_st['n']} hit={base_st['hit']} SL={base_st['sl_n']} ({base_st['sl_pct']}%) "
        f"sum={base_st['sum_pts']}",
        flush=True,
    )

    # Loss autopsy snippets
    sl_rows = [r for r in rows if r["is_sl"]]
    win_rows = [r for r in rows if r["win"]]
    print("SL setups", Counter(r["setup"] for r in sl_rows), flush=True)
    print(
        "SL avg RSI",
        round(np.nanmean([r["rsi"] for r in sl_rows if r["rsi"] is not None]), 1)
        if sl_rows
        else None,
        "WIN avg RSI",
        round(np.nanmean([r["rsi"] for r in win_rows if r["rsi"] is not None]), 1)
        if win_rows
        else None,
        flush=True,
    )

    filters: Dict[str, FilterFn] = {
        "drop_OR_RETEST": lambda r: r["setup"] != "OR_RETEST",
        "ema9_21_align": lambda r: r["ema_align"],
        "rsi_buy_gt45_sell_lt55": lambda r: (
            r["rsi"] is not None
            and (
                (r["call"].side == "BUY" and r["rsi"] >= 45)
                or (r["call"].side == "SELL" and r["rsi"] <= 55)
            )
        ),
        "rsi_not_extreme": lambda r: (
            r["rsi"] is not None
            and (
                (r["call"].side == "BUY" and 40 <= r["rsi"] <= 75)
                or (r["call"].side == "SELL" and 25 <= r["rsi"] <= 60)
            )
        ),
        "vwap_side": lambda r: (
            r["above_vwap"] is not None
            and (
                (r["call"].side == "BUY" and r["above_vwap"])
                or (r["call"].side == "SELL" and not r["above_vwap"])
            )
        ),
        "vwap_not_stretched": lambda r: (
            r["vwap_dist_atr"] is not None
            and (
                (r["call"].side == "BUY" and r["vwap_dist_atr"] <= 2.5)
                or (r["call"].side == "SELL" and r["vwap_dist_atr"] >= -2.5)
            )
        ),
        "body_ge_60": lambda r: r["body"] >= 0.60,
        "vol_ge_1.1x": lambda r: r["v_ratio"] >= 1.1,
        "vol_ge_1.3x": lambda r: r["v_ratio"] >= 1.3,
        "chop10_ge_1.2": lambda r: r["chop10"] >= 1.2,  # not ultra-tight coil entry
        "chop10_le_3.5": lambda r: r["chop10"] <= 3.5,  # avoid wild expansion chase
        "risk_ge_8": lambda r: r["risk"] >= 8.0,
        "risk_ge_10": lambda r: r["risk"] >= 10.0,
        "skip_first_30m": lambda r: r["hm_min"] >= 9 * 60 + 45,
        "skip_after_1400": lambda r: r["hm_min"] <= 14 * 60,
        "ema_and_vwap": lambda r: r["ema_align"]
        and r["above_vwap"] is not None
        and (
            (r["call"].side == "BUY" and r["above_vwap"])
            or (r["call"].side == "SELL" and not r["above_vwap"])
        ),
        "drop_OR_plus_ema": lambda r: r["setup"] != "OR_RETEST" and r["ema_align"],
        "drop_OR_plus_vwap": lambda r: r["setup"] != "OR_RETEST"
        and r["above_vwap"] is not None
        and (
            (r["call"].side == "BUY" and r["above_vwap"])
            or (r["call"].side == "SELL" and not r["above_vwap"])
        ),
        "rsi_vwap_ema": lambda r: (
            r["ema_align"]
            and r["rsi"] is not None
            and r["above_vwap"] is not None
            and (
                (
                    r["call"].side == "BUY"
                    and r["rsi"] >= 45
                    and r["above_vwap"]
                )
                or (
                    r["call"].side == "SELL"
                    and r["rsi"] <= 55
                    and not r["above_vwap"]
                )
            )
        ),
    }

    results = []
    for name, fn in filters.items():
        kept = apply_filter(rows, fn)
        st = stats(kept)
        sl_cut = base_st["sl_n"] - st["sl_n"]
        n_cut = (base_st["n"] or 0) - (st["n"] or 0)
        # score: cut SL, keep hit, keep sum
        if not st["n"] or st["n"] < 20:
            sc = -999.0
        else:
            hit_d = (st["hit"] or 0) - (base_st["hit"] or 0)
            sl_d = (base_st["sl_pct"] or 0) - (st["sl_pct"] or 0)
            sum_d = (st["sum_pts"] or 0) - (base_st["sum_pts"] or 0)
            sc = sl_d * 2.0 + hit_d * 1.5 + (sum_d / 50.0) + min(st["n"], 80) * 0.05
        results.append(
            {
                "name": name,
                **st,
                "sl_cut": sl_cut,
                "n_cut": n_cut,
                "score": round(sc, 3),
            }
        )
        print(
            f"{name:22} n={st['n']:3} hit={st['hit']} SL={st['sl_n']}({st['sl_pct']}%) "
            f"cutSL={sl_cut} sum={st['sum_pts']} score={sc:.1f}",
            flush=True,
        )

    ranked = sorted(results, key=lambda r: r["score"], reverse=True)

    # autopsy table for SL vs win on key indicators
    def avg(xs):
        xs = [x for x in xs if x is not None and np.isfinite(x)]
        return round(float(np.mean(xs)), 2) if xs else None

    autopsy = {
        "sl": {
            "n": len(sl_rows),
            "avg_rsi": avg([r["rsi"] for r in sl_rows]),
            "ema_align_pct": round(100 * sum(1 for r in sl_rows if r["ema_align"]) / max(1, len(sl_rows)), 1),
            "vwap_ok_pct": round(
                100
                * sum(
                    1
                    for r in sl_rows
                    if r["above_vwap"] is not None
                    and (
                        (r["call"].side == "BUY" and r["above_vwap"])
                        or (r["call"].side == "SELL" and not r["above_vwap"])
                    )
                )
                / max(1, len(sl_rows)),
                1,
            ),
            "avg_body": avg([r["body"] for r in sl_rows]),
            "avg_vol_ratio": avg([r["v_ratio"] for r in sl_rows]),
            "avg_chop": avg([r["chop10"] for r in sl_rows]),
            "avg_risk": avg([r["risk"] for r in sl_rows]),
            "setups": dict(Counter(r["setup"] for r in sl_rows)),
        },
        "win": {
            "n": len(win_rows),
            "avg_rsi": avg([r["rsi"] for r in win_rows]),
            "ema_align_pct": round(100 * sum(1 for r in win_rows if r["ema_align"]) / max(1, len(win_rows)), 1),
            "vwap_ok_pct": round(
                100
                * sum(
                    1
                    for r in win_rows
                    if r["above_vwap"] is not None
                    and (
                        (r["call"].side == "BUY" and r["above_vwap"])
                        or (r["call"].side == "SELL" and not r["above_vwap"])
                    )
                )
                / max(1, len(win_rows)),
                1,
            ),
            "avg_body": avg([r["body"] for r in win_rows]),
            "avg_vol_ratio": avg([r["v_ratio"] for r in win_rows]),
            "avg_chop": avg([r["chop10"] for r in win_rows]),
            "avg_risk": avg([r["risk"] for r in win_rows]),
            "setups": dict(Counter(r["setup"] for r in win_rows)),
        },
    }

    lines = [
        f"# Reduce SL calls · indicator research (locked `{cfg.name}` untouched)",
        "",
        f"Window last ~1m · base n={base_st['n']} hit={base_st['hit']}% "
        f"SL={base_st['sl_n']} ({base_st['sl_pct']}%) sum={base_st['sum_pts']}",
        "",
        "## SL vs Win autopsy",
        "",
        "| Feature | SL exits | Wins |",
        "|---|---|---|",
        f"| N | {autopsy['sl']['n']} | {autopsy['win']['n']} |",
        f"| Avg RSI | {autopsy['sl']['avg_rsi']} | {autopsy['win']['avg_rsi']} |",
        f"| EMA9/21 align % | {autopsy['sl']['ema_align_pct']} | {autopsy['win']['ema_align_pct']} |",
        f"| VWAP side OK % | {autopsy['sl']['vwap_ok_pct']} | {autopsy['win']['vwap_ok_pct']} |",
        f"| Avg body | {autopsy['sl']['avg_body']} | {autopsy['win']['avg_body']} |",
        f"| Avg vol ratio | {autopsy['sl']['avg_vol_ratio']} | {autopsy['win']['avg_vol_ratio']} |",
        f"| Avg chop10/ATR | {autopsy['sl']['avg_chop']} | {autopsy['win']['avg_chop']} |",
        f"| Avg risk | {autopsy['sl']['avg_risk']} | {autopsy['win']['avg_risk']} |",
        f"| Setups | {autopsy['sl']['setups']} | {autopsy['win']['setups']} |",
        "",
        "## Filter trials (post-entry gate on same calls)",
        "",
        "| Filter | N | Hit% | SL n (%) | SL cut | Sum pts | Score |",
        "|---|---:|---:|---|---:|---:|---:|",
        f"| **BASE (locked)** | {base_st['n']} | {base_st['hit']} | "
        f"{base_st['sl_n']} ({base_st['sl_pct']}%) | 0 | {base_st['sum_pts']} | — |",
    ]
    for r in ranked:
        lines.append(
            f"| {r['name']} | {r['n']} | {r['hit']} | {r['sl_n']} ({r['sl_pct']}%) | "
            f"{r['sl_cut']} | {r['sum_pts']} | {r['score']} |"
        )

    top = [r for r in ranked if r["score"] > -900][:5]
    lines += [
        "",
        "## Promising (research only — not locked)",
        "",
    ]
    for r in top:
        lines.append(
            f"- **{r['name']}**: SL {base_st['sl_n']}→{r['sl_n']} (cut {r['sl_cut']}), "
            f"hit {base_st['hit']}→{r['hit']}, sum {base_st['sum_pts']}→{r['sum_pts']}, "
            f"n {base_st['n']}→{r['n']}"
        )
    lines += [
        "",
        "## Takeaway",
        "",
        "Locked logic stays. Best add-ons to *try next* for fewer hard stops:",
        "1. **EMA 9/21 align** — trend filter",
        "2. **Session VWAP side** — BUY above / SELL below",
        "3. **Drop or tighten OR_RETEST** — weakest setup in SL pile",
        "4. **RSI band** — avoid chasing extremes",
        "5. **Volume ≥1.1×** — confirm participation",
        "",
        "_No locked_cfg changes in this run._",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    MD.write_text("\n".join(lines), encoding="utf-8")
    JS.write_text(
        json.dumps(
            {
                "base": base_st,
                "base_summary": base_sum,
                "autopsy": autopsy,
                "ranked": ranked,
                "locked_untouched": True,
                "cfg": cfg.name,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
