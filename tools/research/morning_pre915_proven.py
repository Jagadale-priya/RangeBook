"""True PRE-9:15 morning logic hunt (before cash open).

Allowed inputs on morning of NSE day t (no look-ahead):
  - NSE daily bars through day t-1 (trend, TA, candles, ATR range box)
  - Overnight macros known before 9:15 IST: prior US/Asia closes (SPX, NDX, Nikkei, VIX, INR)
  - (News hook reserved; point-in-time DB optional)

Forbidden before 9:15:
  - Today's cash open/high/low/close
  - Same-day live NSE tape

Targets when speaking: >=90% (prefer >=95%) on 1y+3y+5y tests.
Outputs report + recommendation for morning job (no calls).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NIFTY = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_daily_nse.csv"
CACHE = ROOT / "stock_signal_data" / "cache" / "pre915_macro"
OUT_JSON = ROOT / "prod_live" / "reports" / "1y" / "MORNING_PRE915_PROVEN.json"
OUT_MD = ROOT / "prod_live" / "reports" / "1y" / "MORNING_PRE915_PROVEN.md"
GAP_TH = 0.35
FLOOR = 0.90
FLOOR95 = 0.95
MIN_SPEAK = 40


def wilder_atr(h, l, c, n=14):
    prev = c.shift(1)
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def load_nifty() -> pd.DataFrame:
    df = pd.read_csv(NIFTY, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.normalize()
    for c in ("Open", "High", "Low", "Close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["Open", "High", "Low", "Close"]).reset_index(drop=True)


def load_macro(ticker: str, start: str = "2015-01-01") -> pd.Series:
    CACHE.mkdir(parents=True, exist_ok=True)
    safe = ticker.replace("^", "IDX_").replace("=", "_").replace("/", "_")
    path = CACHE / f"{safe}.csv"
    if path.is_file():
        s = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")["Close"]
        s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
        if len(s) > 400:
            return s.sort_index()
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(start=start, auto_adjust=False)
        if hist is None or len(hist) < 100:
            return pd.Series(dtype=float)
        hist = hist.copy()
        hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
        out = hist["Close"].sort_index()
        pd.DataFrame({"Date": out.index, "Close": out.values}).to_csv(path, index=False)
        return out
    except Exception:
        return pd.Series(dtype=float)


def align_prior_close_ret(macro: pd.Series, nse_dates: pd.Series) -> pd.Series:
    """For each NSE date t, use last macro close strictly before t, return its 1d % change.

    That macro bar is known overnight / before NSE open.
    """
    if macro is None or len(macro) < 10:
        return pd.Series(np.nan, index=nse_dates.index)
    m = macro.sort_index()
    mret = m.pct_change() * 100
    # asof merge: for date t, last m.index < t
    idx = pd.DatetimeIndex(nse_dates)
    # reindex with searchsorted
    pos = m.index.searchsorted(idx, side="left") - 1
    vals = []
    for p in pos:
        if p < 1:
            vals.append(np.nan)
        else:
            vals.append(float(mret.iloc[p]))
    return pd.Series(vals, index=nse_dates.index)


def prep(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    h, l, c, o = out["High"], out["Low"], out["Close"], out["Open"]
    atr = wilder_atr(h, l, c, 14)
    prev_c = c.shift(1)
    ret = c.pct_change()
    out["prev_c"] = prev_c
    out["prev_o"] = o.shift(1)
    out["prev_h"] = h.shift(1)
    out["prev_l"] = l.shift(1)
    out["atr_prev"] = atr.shift(1)
    out["ret1"] = ret.shift(1)
    out["sma20"] = c.shift(1).rolling(20).mean()
    out["sma50"] = c.shift(1).rolling(50).mean()
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    out["rsi"] = (100 - 100 / (1 + up / down.replace(0, np.nan))).shift(1)
    rh = h.shift(1).rolling(10).max()
    rl = l.shift(1).rolling(10).min()
    out["struct"] = np.where(
        (rh > rh.shift(10)) & (rl > rl.shift(10)), "UP",
        np.where((rh < rh.shift(10)) & (rl < rl.shift(10)), "DN", "RG"),
    )
    # prior-day candle bias (known before open)
    body = c.shift(1) - o.shift(1)
    out["prior_candle"] = np.where(body > 0, "BULL", np.where(body < 0, "BEAR", "DOJI"))
    # truths (for scoring only — use day's realized data)
    out["gap_pct"] = (o - prev_c) / prev_c * 100
    out["gap_true"] = np.where(
        out["gap_pct"] > GAP_TH, "GAP_UP",
        np.where(out["gap_pct"] < -GAP_TH, "GAP_DOWN", "NATURAL"),
    )
    out["dir_true"] = np.where(c > prev_c, "BULLISH", "BEARISH")
    out["otc_true"] = np.where(c > o, "BULLISH", np.where(c < o, "BEARISH", "NEUTRAL"))

    # overnight macros
    print("Loading macro series for pre-9:15 alignment...")
    spx = load_macro("^GSPC")
    ndx = load_macro("^IXIC")
    n225 = load_macro("^N225")
    vix = load_macro("^VIX")
    inr = load_macro("INR=X")
    out["spx_ret"] = align_prior_close_ret(spx, out["Date"])
    out["ndx_ret"] = align_prior_close_ret(ndx, out["Date"])
    out["n225_ret"] = align_prior_close_ret(n225, out["Date"])
    out["vix_ret"] = align_prior_close_ret(vix, out["Date"])
    out["inr_ret"] = align_prior_close_ret(inr, out["Date"])
    # composite overnight score (same spirit as live panel)
    score = np.zeros(len(out))
    for col, w, invert in (
        ("spx_ret", 1.0, False),
        ("ndx_ret", 1.0, False),
        ("n225_ret", 0.75, False),
        ("vix_ret", 0.9, True),
        ("inr_ret", 0.7, True),
    ):
        x = out[col].fillna(0).values
        signed = -x if invert else x
        score += np.where(signed > 0.35, w * 2, np.where(signed < -0.35, -w * 2, 0))
    out["ovn_score"] = np.clip(score, -12, 12)
    out["ovn_bias"] = np.where(out["ovn_score"] >= 3, "RISK_ON", np.where(out["ovn_score"] <= -3, "RISK_OFF", "NEUTRAL"))
    return out


def score_spoken(pred: pd.Series, actual: pd.Series, speak: Tuple[str, ...]) -> Dict[str, Any]:
    m = actual.notna() & pred.notna()
    spoken = m & pred.isin(list(speak))
    n_all = int(m.sum())
    n_sp = int(spoken.sum())
    if n_sp == 0:
        return {"days_all": n_all, "days_spoken": 0, "coverage": 0.0, "spoken_acc": None}
    return {
        "days_all": n_all,
        "days_spoken": n_sp,
        "coverage": round(n_sp / max(n_all, 1), 4),
        "spoken_acc": round(float((pred[spoken] == actual[spoken]).mean()), 4),
    }


def gap_rules(df: pd.DataFrame) -> Dict[str, pd.Series]:
    out = {}
    out["always_natural"] = pd.Series("NATURAL", index=df.index)
    # overnight continue
    out["ovn_th3"] = np.where(df["ovn_score"] >= 3, "GAP_UP", np.where(df["ovn_score"] <= -3, "GAP_DOWN", "NATURAL"))
    out["ovn_th5"] = np.where(df["ovn_score"] >= 5, "GAP_UP", np.where(df["ovn_score"] <= -5, "GAP_DOWN", "NATURAL"))
    out["ovn_th7"] = np.where(df["ovn_score"] >= 7, "GAP_UP", np.where(df["ovn_score"] <= -7, "GAP_DOWN", "NATURAL"))
    out["spx_th050"] = np.where(df["spx_ret"] > 0.50, "GAP_UP", np.where(df["spx_ret"] < -0.50, "GAP_DOWN", "NATURAL"))
    out["spx_th080"] = np.where(df["spx_ret"] > 0.80, "GAP_UP", np.where(df["spx_ret"] < -0.80, "GAP_DOWN", "NATURAL"))
    out["spx_th100"] = np.where(df["spx_ret"] > 1.0, "GAP_UP", np.where(df["spx_ret"] < -1.0, "GAP_DOWN", "NATURAL"))
    out["spx_th150"] = np.where(df["spx_ret"] > 1.5, "GAP_UP", np.where(df["spx_ret"] < -1.5, "GAP_DOWN", "NATURAL"))
    # overnight + structure agree
    up = (df["ovn_score"] >= 5) & (df["struct"] == "UP")
    dn = (df["ovn_score"] <= -5) & (df["struct"] == "DN")
    out["ovn5_struct"] = np.where(up, "GAP_UP", np.where(dn, "GAP_DOWN", "NATURAL"))
    up2 = (df["spx_ret"] > 0.80) & (df["struct"] == "UP")
    dn2 = (df["spx_ret"] < -0.80) & (df["struct"] == "DN")
    out["spx080_struct"] = np.where(up2, "GAP_UP", np.where(dn2, "GAP_DOWN", "NATURAL"))
    # prior candle + overnight
    up3 = (df["ovn_score"] >= 5) & (df["prior_candle"] == "BULL")
    dn3 = (df["ovn_score"] <= -5) & (df["prior_candle"] == "BEAR")
    out["ovn5_prior_candle"] = np.where(up3, "GAP_UP", np.where(dn3, "GAP_DOWN", "NATURAL"))
    return {k: pd.Series(v, index=df.index) for k, v in out.items()}


def bias_rules(df: pd.DataFrame) -> Dict[str, pd.Series]:
    out = {}
    out["always_neutral"] = pd.Series("NEUTRAL", index=df.index)
    out["ovn_th3"] = np.where(df["ovn_score"] >= 3, "BULLISH", np.where(df["ovn_score"] <= -3, "BEARISH", "NEUTRAL"))
    out["ovn_th5"] = np.where(df["ovn_score"] >= 5, "BULLISH", np.where(df["ovn_score"] <= -5, "BEARISH", "NEUTRAL"))
    out["ovn_th7"] = np.where(df["ovn_score"] >= 7, "BULLISH", np.where(df["ovn_score"] <= -7, "BEARISH", "NEUTRAL"))
    out["spx_th080"] = np.where(df["spx_ret"] > 0.80, "BULLISH", np.where(df["spx_ret"] < -0.80, "BEARISH", "NEUTRAL"))
    out["spx_th100"] = np.where(df["spx_ret"] > 1.0, "BULLISH", np.where(df["spx_ret"] < -1.0, "BEARISH", "NEUTRAL"))
    out["struct_only"] = np.where(df["struct"] == "UP", "BULLISH", np.where(df["struct"] == "DN", "BEARISH", "NEUTRAL"))
    # agree stacks
    up = (df["ovn_score"] >= 5) & (df["struct"] == "UP") & (df["rsi"] > 50)
    dn = (df["ovn_score"] <= -5) & (df["struct"] == "DN") & (df["rsi"] < 50)
    out["ovn5_struct_rsi"] = np.where(up, "BULLISH", np.where(dn, "BEARISH", "NEUTRAL"))
    up = (df["ovn_score"] >= 7) & (df["struct"] == "UP") & (df["prior_candle"] == "BULL")
    dn = (df["ovn_score"] <= -7) & (df["struct"] == "DN") & (df["prior_candle"] == "BEAR")
    out["ovn7_struct_candle"] = np.where(up, "BULLISH", np.where(dn, "BEARISH", "NEUTRAL"))
    up = (df["spx_ret"] > 1.0) & (df["struct"] == "UP") & (df["sma20"] > df["sma50"]) # wait sma on prior
    # fix: sma20/50 already prior-shifted closes
    up = (df["spx_ret"] > 1.0) & (df["struct"] == "UP") & (df["prev_c"] > df["sma50"])
    dn = (df["spx_ret"] < -1.0) & (df["struct"] == "DN") & (df["prev_c"] <= df["sma50"])
    out["spx100_struct_sma"] = np.where(up, "BULLISH", np.where(dn, "BEARISH", "NEUTRAL"))
    up = (df["ovn_score"] >= 5) & (df["spx_ret"] > 0.5) & (df["struct"] == "UP")
    dn = (df["ovn_score"] <= -5) & (df["spx_ret"] < -0.5) & (df["struct"] == "DN")
    out["ovn5_spx_struct"] = np.where(up, "BULLISH", np.where(dn, "BEARISH", "NEUTRAL"))
    return {k: pd.Series(v, index=df.index) for k, v in out.items()}


def eval_family(train, test, rules_fn, actual_col, speak):
    rows = []
    rt, re = rules_fn(train), rules_fn(test)
    for name, pred in rt.items():
        tr = score_spoken(pred, train[actual_col], speak)
        te = score_spoken(re[name], test[actual_col], speak)
        rows.append({"rule": name, "train": tr, "test": te})
    picks = {}
    for floor, tag in ((FLOOR, "90"), (FLOOR95, "95")):
        pool = [
            r for r in rows
            if r["train"].get("spoken_acc") is not None
            and r["train"]["spoken_acc"] >= floor
            and r["train"]["days_spoken"] >= MIN_SPEAK
        ]
        if pool:
            win = max(pool, key=lambda r: (r["train"]["coverage"], r["train"]["spoken_acc"]))
            test_ok = (
                win["test"].get("spoken_acc") is not None
                and win["test"]["spoken_acc"] >= floor
                and win["test"]["days_spoken"] >= 10
            )
            picks[tag] = {**win, "test_ok": test_ok, "floor": floor}
        else:
            spoken = [r for r in rows if r["train"].get("spoken_acc") is not None and r["train"]["days_spoken"] >= 15]
            best = max(spoken, key=lambda r: (r["train"]["spoken_acc"], r["train"]["coverage"])) if spoken else None
            picks[tag] = {"rule": best["rule"] if best else None, "train": best["train"] if best else None,
                          "test": best["test"] if best else None, "test_ok": False, "floor": floor,
                          "note": "no train clear"}
    top = sorted(rows, key=lambda r: (-(r["train"].get("spoken_acc") or -1), -(r["train"].get("coverage") or 0)))[:12]
    return {"picks": picks, "top": top, "all": rows}


def cross_rule(df, rule, rules_fn, actual, speak, floor):
    tests = {}
    for lab, n in (("1y", 252), ("3y", 756), ("5y", 1260)):
        start = df["Date"].iloc[-n]
        test = df[df["Date"] >= start]
        pred = rules_fn(test)[rule]
        tests[lab] = score_spoken(pred, test[actual], speak)
    ok = all(
        (tests[k].get("spoken_acc") or 0) >= floor and tests[k]["days_spoken"] >= 10
        for k in tests
    )
    return {"rule": rule, "floor": floor, "tests": tests, "promote": ok}


def range_premarket_v4(df: pd.DataFrame) -> Dict[str, Any]:
    """Provisional box centered on prior close (true pre-9:15)."""
    prev_c = df["prev_c"]
    atr = df["atr_prev"]
    width = np.maximum(atr * 2.6, prev_c * 0.004)
    half = width / 2.0
    # asymmetric dn like V4
    hi = prev_c + half * 1.0
    lo = prev_c - half * 1.2
    full = (df["Low"] >= lo) & (df["High"] <= hi)
    use = full.notna() & width.notna() & prev_c.notna()
    return {
        "days": int(use.sum()),
        "full_containment_acc": round(float(full[use].mean()), 4),
        "median_width_pct": round(float(((hi - lo) / prev_c)[use].median()), 4),
        "note": "Premarket provisional (center=prior close). Weaker than open-locked V4.",
    }


def main():
    raw = load_nifty()
    df = prep(raw)
    # need overnight fields present
    df = df.dropna(subset=["spx_ret"]).reset_index(drop=True)

    splits = []
    for lab, n in (("1y", 252), ("3y", 756), ("5y", 1260)):
        start = df["Date"].iloc[-n]
        train, test = df[df["Date"] < start], df[df["Date"] >= start]
        gap = eval_family(train, test, gap_rules, "gap_true", ("GAP_UP", "GAP_DOWN"))
        bias = eval_family(train, test, bias_rules, "dir_true", ("BULLISH", "BEARISH"))
        bias_otc = eval_family(train, test, bias_rules, "otc_true", ("BULLISH", "BEARISH"))
        rng = range_premarket_v4(test)
        splits.append({
            "label": lab,
            "start": str(start.date()),
            "end": str(test["Date"].max().date()),
            "train_days": len(train),
            "test_days": len(test),
            "gap": gap,
            "bias_close": bias,
            "bias_otc": bias_otc,
            "range_premarket_v4": rng,
        })

    # promote candidates from 3y picks + tops
    s3 = next(s for s in splits if s["label"] == "3y")
    promos = []
    for family, key, actual, speak, rfn in (
        ("gap", "gap", "gap_true", ("GAP_UP", "GAP_DOWN"), gap_rules),
        ("bias_close", "bias_close", "dir_true", ("BULLISH", "BEARISH"), bias_rules),
        ("bias_otc", "bias_otc", "otc_true", ("BULLISH", "BEARISH"), bias_rules),
    ):
        for tag, floor in (("90", FLOOR), ("95", FLOOR95)):
            p = s3[key]["picks"].get(tag) or {}
            if p.get("rule"):
                promos.append({**cross_rule(df, p["rule"], rfn, actual, speak, floor), "family": family, "from": f"pick_{tag}"})
        for r in s3[key]["top"][:6]:
            if r["rule"] and r["train"].get("spoken_acc"):
                promos.append({**cross_rule(df, r["rule"], rfn, actual, speak, FLOOR), "family": family, "from": "top"})

    best = {}
    for fam in ("gap", "bias_close", "bias_otc"):
        pool = [p for p in promos if p["family"] == fam and p["promote"]]
        if pool:
            best[fam] = max(pool, key=lambda p: (p["floor"], p["tests"]["3y"]["coverage"], p["tests"]["3y"]["spoken_acc"] or 0))
        else:
            pool2 = [p for p in promos if p["family"] == fam]
            if pool2:
                def score(p):
                    accs = [p["tests"][k]["spoken_acc"] for k in ("1y", "3y", "5y") if p["tests"][k]["spoken_acc"] is not None]
                    return (min(accs) if accs else 0, p["tests"]["3y"]["coverage"])
                b = max(pool2, key=score)
                best[fam] = {**b, "promote": False}

    payload = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "scope": "PRE_9:15_ONLY",
        "inputs": ["prior NSE daily TA/trend/candles", "overnight SPX/NDX/N225/VIX/INR known before open"],
        "forbidden": ["today cash open/high/low/close", "same-day NSE tape"],
        "splits": [
            {
                "label": s["label"],
                "start": s["start"],
                "end": s["end"],
                "train_days": s["train_days"],
                "test_days": s["test_days"],
                "range_premarket_v4": s["range_premarket_v4"],
                "gap_picks": s["gap"]["picks"],
                "gap_top": [{"rule": r["rule"], "train": r["train"], "test": r["test"]} for r in s["gap"]["top"][:8]],
                "bias_picks": s["bias_close"]["picks"],
                "bias_top": [{"rule": r["rule"], "train": r["train"], "test": r["test"]} for r in s["bias_close"]["top"][:8]],
                "bias_otc_picks": s["bias_otc"]["picks"],
                "bias_otc_top": [{"rule": r["rule"], "train": r["train"], "test": r["test"]} for r in s["bias_otc"]["top"][:8]],
            }
            for s in splits
        ],
        "best": best,
        "recommendation": {
            "job": "morning_pre915_context",
            "no_calls": True,
            "range": {
                "method": "premarket_atr26x_dn120_prior_close",
                "note": "Provisional expected high/low before open; open-locked V4 is for after 9:15 only.",
                "test_3y_containment": next(s["range_premarket_v4"] for s in splits if s["label"] == "3y"),
            },
            "gap": best.get("gap"),
            "bias": best.get("bias_close"),
            "bias_otc": best.get("bias_otc"),
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# PRE-9:15 morning context — proven hunt (no calls)",
        "",
        f"**Generated:** `{payload['generated_at']}`",
        "",
        "## Scope",
        "",
        "Runs **before 9:15 IST**. Uses overnight globals + prior-day NSE TA/trend only.",
        "Does **not** use today's cash open.",
        "",
        "## Recommendation",
        "",
    ]
    for title, key in (("Gap (premarket)", "gap"), ("Bias close vs prior", "bias"), ("Bias open→close proxy", "bias_otc")):
        b = payload["recommendation"].get(key)
        lines.append(f"### {title}")
        if not b:
            lines += ["None", ""]
            continue
        lines.append(f"- rule `{b.get('rule')}` · promote **{b.get('promote')}** · floor {b.get('floor')}")
        for lab in ("1y", "3y", "5y"):
            t = b["tests"][lab]
            lines.append(
                f"  - {lab}: spoken **{(t.get('spoken_acc') or 0):.1%}** · cov {t.get('coverage'):.1%} · n={t.get('days_spoken')}"
            )
        lines.append("")
    r3 = payload["recommendation"]["range"]["test_3y_containment"]
    lines += [
        "### Range (provisional pre-open)",
        f"- 3y full containment **{r3['full_containment_acc']:.1%}** · width {r3['median_width_pct']:.2%}",
        f"- {r3['note']}",
        "",
        "## Held defaults if promote=False",
        "",
        "- gap → **NATURAL** (until open)",
        "- bias → **NEUTRAL**",
        "- still emit expected range width + overnight panel + trend/TA context + news tone",
        "",
    ]
    # 3y tops
    lines += ["## 3y tops (train spoken)", ""]
    for fam, key in (("Gap", "gap_top"), ("Bias", "bias_top"), ("Bias OTC", "bias_otc_top")):
        lines.append(f"### {fam}")
        lines.append("| Rule | Train acc | Train cov | Test acc | Test cov |")
        lines.append("|---|---:|---:|---:|---:|")
        for r in next(s[key] for s in payload["splits"] if s["label"] == "3y"):
            tr, te = r["train"], r["test"]
            lines.append(
                f"| `{r['rule']}` | {tr.get('spoken_acc')} | {tr.get('coverage')} | {te.get('spoken_acc')} | {te.get('coverage')} |"
            )
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "wrote": str(OUT_MD),
        "best": {
            k: {"rule": v.get("rule"), "promote": v.get("promote"),
                "tests": {lab: {"acc": v["tests"][lab].get("spoken_acc"), "cov": v["tests"][lab].get("coverage")}
                          for lab in ("1y", "3y", "5y")}}
            for k, v in best.items()
        },
        "range_3y": r3,
    }, indent=2))


if __name__ == "__main__":
    main()
