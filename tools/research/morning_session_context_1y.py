"""Honest 1y bake-off for pre-live morning session CONTEXT (no trade calls).

Fit candidates only on dates BEFORE the report window.
Report window = last ~1y of available sessions.
No parameter is chosen using report-window outcomes.

Outputs:
  prod_live/reports/1y/MORNING_SESSION_CONTEXT_1Y.json
  prod_live/reports/1y/MORNING_SESSION_CONTEXT_1Y.md
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NIFTY_PATH = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_daily_nse.csv"
BANK_PATH = ROOT / "stock_signal_data" / "cache" / "IDX_NSEBANK.csv"
VIX_PATH = ROOT / "stock_signal_data" / "cache" / "regime_IDX_INDIAVIX.csv"
CACHE = ROOT / "stock_signal_data" / "cache"
OUT_JSON = ROOT / "prod_live" / "reports" / "1y" / "MORNING_SESSION_CONTEXT_1Y.json"
OUT_MD = ROOT / "prod_live" / "reports" / "1y" / "MORNING_SESSION_CONTEXT_1Y.md"

STOCKS = [
    "RELIANCE", "HDFCBANK", "INFY", "TCS", "SBIN", "ICICIBANK",
    "BAJFINANCE", "BHARTIARTL", "AXISBANK", "ITC", "LT", "TATASTEEL",
]
GAP_TH = 0.35  # percent — matches structural_analysis.analyze_gap


def wilder_atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    prev_c = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_c).abs(), (low - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def load_ohlc(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Date may be tz-aware string
    df["Date"] = pd.to_datetime(df["Date"], utc=False).dt.tz_localize(None).dt.normalize()
    for c in ("Open", "High", "Low", "Close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if "Volume" in df.columns:
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close"]).sort_values("Date").reset_index(drop=True)
    return df


def load_stock(sym: str) -> Optional[pd.DataFrame]:
    path = CACHE / f"{sym}_NS.csv"
    if not path.is_file():
        return None
    return load_ohlc(path)


def load_vix() -> Optional[pd.Series]:
    if not VIX_PATH.is_file():
        return None
    df = pd.read_csv(VIX_PATH)
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.normalize()
    s = pd.Series(df["Close"].astype(float).values, index=df["Date"]).sort_index()
    return s


def prepare(df: pd.DataFrame, vix: Optional[pd.Series] = None) -> pd.DataFrame:
    """All predictors for day t use only info known before the open of t (prior close)."""
    out = df.copy()
    h, l, c, o = out["High"], out["Low"], out["Close"], out["Open"]
    day_rng = (h - l).clip(lower=0)
    atr = wilder_atr(h, l, c, 14)
    prev_c = c.shift(1)
    prev_h = h.shift(1)
    prev_l = l.shift(1)
    prev_o = o.shift(1)
    prev_rng = day_rng.shift(1)
    atr_prev = atr.shift(1)
    med20 = prev_rng.rolling(20).median()
    p80 = prev_rng.rolling(20).quantile(0.80)
    ret = c.pct_change()
    vol20 = ret.shift(1).rolling(20).std()
    sma20 = c.shift(1).rolling(20).mean()
    sma50 = c.shift(1).rolling(50).mean()
    # RSI on prior closes
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / down.replace(0, np.nan))).shift(1)

    # Trend from prior bars only: compare last two non-overlapping 10-day swing
    # extremes known at prior close (vectorized; no look-ahead).
    roll_high = h.shift(1).rolling(10).max()
    roll_low = l.shift(1).rolling(10).min()
    prev_roll_high = roll_high.shift(10)
    prev_roll_low = roll_low.shift(10)
    structure = np.where(
        (roll_high > prev_roll_high) & (roll_low > prev_roll_low),
        "UPTREND",
        np.where(
            (roll_high < prev_roll_high) & (roll_low < prev_roll_low),
            "DOWNTREND",
            np.where(roll_high.notna() & prev_roll_high.notna(), "RANGE", "UNKNOWN"),
        ),
    )

    out["prev_c"] = prev_c
    out["prev_h"] = prev_h
    out["prev_l"] = prev_l
    out["prev_o"] = prev_o
    out["prev_rng"] = prev_rng
    out["atr_prev"] = atr_prev
    out["med20"] = med20
    out["p80"] = p80
    out["vol20"] = vol20
    out["sma20"] = sma20
    out["sma50"] = sma50
    out["rsi"] = rsi
    out["ret1"] = ret.shift(1)  # yesterday's return known at open
    out["structure"] = structure
    out["gap_pct"] = (o - prev_c) / prev_c * 100
    out["gap_class"] = np.where(
        out["gap_pct"] > GAP_TH, "GAP_UP",
        np.where(out["gap_pct"] < -GAP_TH, "GAP_DOWN", "NATURAL"),
    )
    out["close_up"] = c > prev_c
    out["open_to_close_up"] = c > o
    out["realized_rng"] = day_rng
    out["realized_rng_pct"] = day_rng / prev_c * 100

    # Expected gap proxy WITHOUT knowing today's open: use prior gap persistence + overnight N/A
    # Premarket gap forecast candidates use only prior-day features.
    out["pred_gap_continue"] = np.where(
        out["ret1"] * 100 > GAP_TH, "GAP_UP",
        np.where(out["ret1"] * 100 < -GAP_TH, "GAP_DOWN", "NATURAL"),
    )
    # Fade prior day extreme move
    out["pred_gap_fade"] = np.where(
        out["ret1"] * 100 > GAP_TH, "GAP_DOWN",
        np.where(out["ret1"] * 100 < -GAP_TH, "GAP_UP", "NATURAL"),
    )
    # Structure-led gap expectation (weak)
    out["pred_gap_structure"] = np.where(
        out["structure"] == "UPTREND", "GAP_UP",
        np.where(out["structure"] == "DOWNTREND", "GAP_DOWN", "NATURAL"),
    )

    if vix is not None and len(vix):
        # prior close VIX
        vix_aligned = out["Date"].map(lambda d: float(vix.get(d, np.nan)) if d in vix.index else np.nan)
        # use previous available VIX (as of prior session)
        vix_s = pd.Series(vix_aligned.values, index=out.index)
        out["vix_prev"] = vix_s.shift(1).ffill()
    else:
        out["vix_prev"] = np.nan

    # Vol label from prior ATR%
    atr_pct = atr_prev / prev_c * 100
    out["atr_pct_prev"] = atr_pct
    q33 = atr_pct.expanding(min_periods=60).quantile(0.33)
    q66 = atr_pct.expanding(min_periods=60).quantile(0.66)
    out["vol_pred_atr"] = np.where(atr_pct >= q66, "HIGH", np.where(atr_pct <= q33, "LOW", "NORMAL"))
    # Realized vol tercile within expanding window of realized_rng_pct (for scoring, known after day)
    rq33 = out["realized_rng_pct"].expanding(min_periods=60).quantile(0.33)
    rq66 = out["realized_rng_pct"].expanding(min_periods=60).quantile(0.66)
    out["vol_realized"] = np.where(
        out["realized_rng_pct"] >= rq66, "HIGH",
        np.where(out["realized_rng_pct"] <= rq33, "LOW", "NORMAL"),
    )
    return out


def range_widths(df: pd.DataFrame) -> Dict[str, pd.Series]:
    price = df["prev_c"]
    floor = price * 0.004
    return {
        "current_max_yday_atr_floor": np.maximum(np.maximum(df["prev_rng"], df["atr_prev"]), floor),
        "yesterday_range": df["prev_rng"],
        "atr14": np.maximum(df["atr_prev"], floor),
        "median_20_ranges": df["med20"],
        "p80_20_ranges": df["p80"],
        "vol20_1sd": (df["vol20"] * price),
        "vol20_1_5sd": (df["vol20"] * price * 1.5),
        "atr14_1_2x": np.maximum(df["atr_prev"] * 1.2, floor),
    }


def score_range(df: pd.DataFrame, width: pd.Series, anchor: str) -> Dict[str, float]:
    """anchor: prev_close | session_open"""
    half = width / 2.0
    if anchor == "session_open":
        center = df["Open"]
        # gap asymmetric like lock_day_range_on_open
        hi = center + half
        lo = center - half
        prev = df["prev_c"]
        gap = center - prev
        big = (gap.abs() / prev) >= 0.0035
        extra = np.minimum(gap.abs(), width * 0.35)
        hi = np.where(big & (gap > 0), hi + extra, hi)
        lo = np.where(big & (gap < 0), lo - extra, lo)
    else:
        center = df["prev_c"]
        hi = center + half
        lo = center - half
    inside = (df["Low"] >= lo) & (df["High"] <= hi)
    width_pct = width / df["prev_c"]
    use = inside.notna() & width.notna() & (width > 0) & df["prev_c"].notna()
    if use.sum() == 0:
        return {"days": 0, "inside_pct": 0.0, "median_width_pct": 0.0, "score": 0.0}
    sl_in = inside[use]
    sl_w = width_pct[use]
    med_w = float(sl_w.median())
    inside_pct = float(sl_in.mean())
    score = inside_pct / med_w if med_w > 0 else 0.0
    return {
        "days": int(use.sum()),
        "inside_pct": round(inside_pct, 4),
        "median_width_pct": round(med_w, 4),
        "score": round(score, 4),
    }


def bias_rules(df: pd.DataFrame) -> Dict[str, pd.Series]:
    """Predict close_up (vs prior close). True=bullish. NEUTRAL encoded as NaN (abstain)."""
    mom = df["ret1"] > 0
    fade = df["ret1"] < 0
    above50 = df["prev_c"] > df["sma50"]
    rsi_up = df["rsi"] > 50
    struct_up = df["structure"] == "UPTREND"
    struct_dn = df["structure"] == "DOWNTREND"
    # Strong structure only
    struct_only = pd.Series(np.nan, index=df.index, dtype=float)
    struct_only = struct_only.mask(struct_up, 1.0).mask(struct_dn, 0.0)
    # Ensemble: majority of mom, above50, rsi
    votes = mom.astype(int) + above50.astype(int) + rsi_up.astype(int)
    ens = pd.Series(np.nan, index=df.index, dtype=float)
    ens = ens.mask(votes >= 2, 1.0).mask(votes <= 1, 0.0)
    # Strong ensemble: need 3/3 or 0/3 else abstain
    ens_strong = pd.Series(np.nan, index=df.index, dtype=float)
    ens_strong = ens_strong.mask(votes == 3, 1.0).mask(votes == 0, 0.0)
    # Structure + SMA agree
    agree = pd.Series(np.nan, index=df.index, dtype=float)
    agree = agree.mask(struct_up & above50, 1.0).mask(struct_dn & ~above50, 0.0)
    return {
        "always_up": pd.Series(1.0, index=df.index),
        "yesterday_up_continues": mom.astype(float),
        "yesterday_up_fades": fade.astype(float),
        "above_sma50": above50.astype(float),
        "rsi14_above_50": rsi_up.astype(float),
        "structure_only": struct_only,
        "vote3_majority": ens,
        "vote3_unanimous": ens_strong,
        "structure_and_sma50": agree,
    }


def score_bias(df: pd.DataFrame, pred: pd.Series) -> Dict[str, Any]:
    actual = df["close_up"].astype(float)
    mask = pred.notna() & actual.notna() & df["prev_c"].notna()
    n = int(mask.sum())
    if n == 0:
        return {"days": 0, "coverage": 0.0, "accuracy": 0.0, "base_up_rate": 0.0, "lift": 0.0}
    hit = (pred[mask] == actual[mask]).mean()
    base = float(actual[mask].mean())
    # lift vs always predicting majority class
    majority = 1.0 if base >= 0.5 else 0.0
    maj_acc = float((actual[mask] == majority).mean())
    return {
        "days": n,
        "coverage": round(n / max(int(actual.notna().sum()), 1), 4),
        "accuracy": round(float(hit), 4),
        "base_up_rate": round(base, 4),
        "majority_acc": round(maj_acc, 4),
        "lift": round(float(hit) - maj_acc, 4),
    }


def score_gap(df: pd.DataFrame, pred_col: str) -> Dict[str, Any]:
    pred = df[pred_col]
    actual = df["gap_class"]
    mask = pred.notna() & actual.notna() & df["prev_c"].notna()
    n = int(mask.sum())
    if n == 0:
        return {"days": 0, "accuracy": 0.0, "by_class": {}}
    hit = (pred[mask] == actual[mask]).mean()
    by = {}
    for cls in ("GAP_UP", "GAP_DOWN", "NATURAL"):
        m = mask & (pred == cls)
        if m.sum():
            by[cls] = {
                "n": int(m.sum()),
                "hit": round(float((pred[m] == actual[m]).mean()), 4),
            }
    # natural base rate
    nat_rate = float((actual[mask] == "NATURAL").mean())
    return {
        "days": n,
        "accuracy": round(float(hit), 4),
        "natural_base_rate": round(nat_rate, 4),
        "by_class": by,
    }


def score_vol(df: pd.DataFrame, pred_col: str) -> Dict[str, Any]:
    pred = df[pred_col]
    actual = df["vol_realized"]
    mask = pred.notna() & actual.notna()
    n = int(mask.sum())
    if n == 0:
        return {"days": 0, "accuracy": 0.0}
    return {
        "days": n,
        "accuracy": round(float((pred[mask] == actual[mask]).mean()), 4),
    }


def score_trend_continuation(df: pd.DataFrame) -> Dict[str, Any]:
    """If prior structure is UPTREND/DOWNTREND, did close continue that way?"""
    rows = []
    for label, want_up in (("UPTREND", True), ("DOWNTREND", False)):
        m = (df["structure"] == label) & df["close_up"].notna()
        n = int(m.sum())
        if n == 0:
            rows.append({"structure": label, "days": 0, "continuation_hit": 0.0})
            continue
        hit = float((df.loc[m, "close_up"] == want_up).mean())
        rows.append({"structure": label, "days": n, "continuation_hit": round(hit, 4)})
    return {"slices": rows}


def chain_guidance(vol_label: str, bias: str, atr_pct: float, vix: Optional[float]) -> Dict[str, Any]:
    """Guidance only — never a trade call."""
    vix_reg = "UNKNOWN"
    if vix is not None and vix == vix:
        if vix < 14:
            vix_reg = "LOW"
        elif vix < 18:
            vix_reg = "NORMAL"
        elif vix < 22:
            vix_reg = "ELEVATED"
        else:
            vix_reg = "HIGH"

    # Style preference by vol / VIX
    if vix_reg == "HIGH" or vol_label == "HIGH":
        style = "SPREAD"
        why = "High vol/VIX — prefer defined-risk spreads; avoid naked ATM debit chase."
    elif vix_reg == "LOW" and vol_label == "LOW":
        style = "INDEX_FUT"
        why = "Low vol — futures or slightly OTM; avoid overpaying premium."
    elif vix_reg in ("ELEVATED",) or vol_label == "HIGH":
        style = "ATM_OPTION"
        why = "Elevated vol — ATM/near-ATM options with size down."
    else:
        style = "ATM_OR_FUT"
        why = "Normal regime — futures or ATM options."

    side = "NONE"
    if bias == "BULLISH":
        side = "CE" if style != "INDEX_FUT" else "FUT_LONG"
    elif bias == "BEARISH":
        side = "PE" if style != "INDEX_FUT" else "FUT_SHORT"

    strike = "ATM"
    if style == "SPREAD":
        strike = "ATM_SPREAD"
    elif style == "INDEX_FUT":
        strike = "FUTURE"
    elif atr_pct is not None and atr_pct == atr_pct and atr_pct > 1.2:
        strike = "ITM_OR_ATM"  # need more delta when move is large

    return {
        "style": style,
        "side_hint": side,
        "strike_band": strike,
        "vix_regime": vix_reg,
        "why": why,
        "guide_only": True,
        "is_call": False,
    }


def score_chain_guidance(df: pd.DataFrame, bias_pred: pd.Series) -> Dict[str, Any]:
    """Regret proxy: HIGH-vol days where guidance said INDEX_FUT (wrong style)."""
    wrong_fut_on_high = 0
    right_spread_on_high = 0
    high_days = 0
    low_fut_ok = 0
    low_days = 0
    for i in df.index:
        vol = df.at[i, "vol_realized"]
        atr_pct = df.at[i, "atr_pct_prev"]
        vix = df.at[i, "vix_prev"]
        bp = bias_pred.at[i] if i in bias_pred.index else np.nan
        if bp == bp:
            bias = "BULLISH" if bp >= 0.5 else "BEARISH"
        else:
            bias = "NEUTRAL"
        g = chain_guidance(str(df.at[i, "vol_pred_atr"]), bias, float(atr_pct) if atr_pct == atr_pct else 0.0, float(vix) if vix == vix else None)
        if vol == "HIGH":
            high_days += 1
            if g["style"] == "INDEX_FUT":
                wrong_fut_on_high += 1
            if g["style"] in ("SPREAD", "ATM_OPTION"):
                right_spread_on_high += 1
        if vol == "LOW":
            low_days += 1
            if g["style"] in ("INDEX_FUT", "ATM_OR_FUT"):
                low_fut_ok += 1
    return {
        "high_vol_days": high_days,
        "avoided_naked_fut_on_high_pct": round(1 - wrong_fut_on_high / high_days, 4) if high_days else None,
        "defined_risk_or_opt_on_high_pct": round(right_spread_on_high / high_days, 4) if high_days else None,
        "low_vol_days": low_days,
        "fut_or_atm_on_low_pct": round(low_fut_ok / low_days, 4) if low_days else None,
    }


def window_mask(df: pd.DataFrame, start: pd.Timestamp, end: Optional[pd.Timestamp] = None) -> pd.Series:
    m = df["Date"] >= start
    if end is not None:
        m &= df["Date"] <= end
    return m


def run_symbol(name: str, df_raw: pd.DataFrame, vix: Optional[pd.Series], report_start: pd.Timestamp) -> Dict[str, Any]:
    df = prepare(df_raw, vix)
    train = df[df["Date"] < report_start].copy()
    test = df[df["Date"] >= report_start].copy()
    if len(test) < 50 or len(train) < 100:
        return {"symbol": name, "error": f"insufficient bars train={len(train)} test={len(test)}"}

    # --- Range bake-off ---
    range_rows = []
    widths_train = range_widths(train)
    widths_test = range_widths(test)
    for method, w_tr in widths_train.items():
        for anchor in ("prev_close", "session_open"):
            tr = score_range(train, w_tr, anchor)
            te = score_range(test, widths_test[method], anchor)
            range_rows.append({
                "method": method,
                "anchor": anchor,
                "train": tr,
                "test": te,
            })
    # Winner on TRAIN score only (prev_close and open ranked separately; primary = open-locked for live morning after 9:15, premarket = prev_close)
    pre_train = [r for r in range_rows if r["anchor"] == "prev_close"]
    open_train = [r for r in range_rows if r["anchor"] == "session_open"]
    win_pre = max(pre_train, key=lambda r: r["train"]["score"])
    win_open = max(open_train, key=lambda r: r["train"]["score"])

    # --- Bias ---
    bias_rows = []
    rules_tr = bias_rules(train)
    rules_te = bias_rules(test)
    for rule, pred_tr in rules_tr.items():
        bias_rows.append({
            "rule": rule,
            "train": score_bias(train, pred_tr),
            "test": score_bias(test, rules_te[rule]),
        })
    # Prefer train lift, then accuracy; require coverage >= 0.25 for abstaining rules
    def bias_key(r):
        t = r["train"]
        cov_ok = 1 if t["coverage"] >= 0.25 or r["rule"].startswith("always") or "yesterday" in r["rule"] or "sma" in r["rule"] or "rsi" in r["rule"] else 0
        return (cov_ok, t["lift"], t["accuracy"], t["days"])

    win_bias = max(bias_rows, key=bias_key)

    # --- Gap ---
    gap_rows = []
    for col, label in (
        ("pred_gap_continue", "prior_day_continue"),
        ("pred_gap_fade", "prior_day_fade"),
        ("pred_gap_structure", "structure"),
    ):
        gap_rows.append({
            "rule": label,
            "train": score_gap(train, col),
            "test": score_gap(test, col),
        })
    # Always NATURAL baseline
    train2 = train.copy()
    test2 = test.copy()
    train2["pred_always_natural"] = "NATURAL"
    test2["pred_always_natural"] = "NATURAL"
    gap_rows.append({
        "rule": "always_natural",
        "train": score_gap(train2, "pred_always_natural"),
        "test": score_gap(test2, "pred_always_natural"),
    })
    win_gap = max(gap_rows, key=lambda r: (r["train"]["accuracy"], r["train"]["days"]))

    # --- Vol ---
    vol_tr = score_vol(train, "vol_pred_atr")
    vol_te = score_vol(test, "vol_pred_atr")

    # --- Trend ---
    trend_tr = score_trend_continuation(train)
    trend_te = score_trend_continuation(test)

    # --- Chain guidance using winning bias on test ---
    best_bias_rule = win_bias["rule"]
    chain_te = score_chain_guidance(test, rules_te[best_bias_rule])
    chain_tr = score_chain_guidance(train, rules_tr[best_bias_rule])

    return {
        "symbol": name,
        "bars_total": len(df),
        "train_days": int((df["Date"] < report_start).sum()),
        "test_days": int((df["Date"] >= report_start).sum()),
        "report_start": str(report_start.date()),
        "report_end": str(df["Date"].max().date()),
        "range": {
            "all": range_rows,
            "train_winner_premarket": {
                "method": win_pre["method"],
                "anchor": win_pre["anchor"],
                "train": win_pre["train"],
                "test": win_pre["test"],
            },
            "train_winner_open_locked": {
                "method": win_open["method"],
                "anchor": win_open["anchor"],
                "train": win_open["train"],
                "test": win_open["test"],
            },
            "current_method_test_open": next(
                r for r in range_rows
                if r["method"] == "current_max_yday_atr_floor" and r["anchor"] == "session_open"
            )["test"],
        },
        "bias": {
            "all": bias_rows,
            "train_winner": {
                "rule": win_bias["rule"],
                "train": win_bias["train"],
                "test": win_bias["test"],
            },
        },
        "gap": {
            "all": gap_rows,
            "train_winner": {
                "rule": win_gap["rule"],
                "train": win_gap["train"],
                "test": win_gap["test"],
            },
        },
        "vol": {"method": "atr_pct_expanding_tercile", "train": vol_tr, "test": vol_te},
        "trend": {"train": trend_tr, "test": trend_te},
        "chain_guidance": {"train": chain_tr, "test": chain_te, "bias_rule_used": best_bias_rule},
    }


def to_md(payload: Dict[str, Any]) -> str:
    lines = [
        "# Morning session context — 1y bake-off (no calls)",
        "",
        f"**Report window start (fit before this):** `{payload['report_start']}`",
        f"**Generated:** `{payload['generated_at']}`",
        "",
        "Winners chosen on **train only**. Test = last ~1y held out.",
        "This product emits context only — **no BUY/SELL calls**.",
        "",
        "## Frozen recommendation (from NIFTY train winners)",
        "",
    ]
    nifty = payload["symbols"].get("NIFTY") or {}
    if nifty and "error" not in nifty:
        rp = nifty["range"]["train_winner_premarket"]
        ro = nifty["range"]["train_winner_open_locked"]
        b = nifty["bias"]["train_winner"]
        g = nifty["gap"]["train_winner"]
        lines += [
            f"- **Premarket range:** `{rp['method']}` @ prev_close — train score {rp['train']['score']} · "
            f"test inside {rp['test']['inside_pct']:.1%} width_med {rp['test']['median_width_pct']:.2%}",
            f"- **Open-locked range:** `{ro['method']}` @ session_open — train score {ro['train']['score']} · "
            f"test inside {ro['test']['inside_pct']:.1%} width_med {ro['test']['median_width_pct']:.2%}",
            f"- **Bias:** `{b['rule']}` — train acc {b['train']['accuracy']:.1%} lift {b['train']['lift']:+.1%} · "
            f"test acc {b['test']['accuracy']:.1%} lift {b['test']['lift']:+.1%} cov {b['test']['coverage']:.0%}",
            f"- **Gap:** `{g['rule']}` — train {g['train']['accuracy']:.1%} · test {g['test']['accuracy']:.1%}",
            f"- **Vol:** expanding ATR% tercile — test hit {nifty['vol']['test']['accuracy']:.1%}",
            f"- **Chain guidance:** high-vol avoid naked fut test="
            f"{nifty['chain_guidance']['test'].get('avoided_naked_fut_on_high_pct')}",
            "",
        ]
    lines += ["## Per symbol", ""]
    for sym, block in payload["symbols"].items():
        if block.get("error"):
            lines.append(f"### {sym}")
            lines.append(f"Error: {block['error']}")
            lines.append("")
            continue
        b = block["bias"]["train_winner"]
        rp = block["range"]["train_winner_premarket"]
        lines += [
            f"### {sym}",
            f"- bars train/test: {block['train_days']}/{block['test_days']} · end {block['report_end']}",
            f"- range winner (pre): `{rp['method']}` test inside **{rp['test']['inside_pct']:.1%}**",
            f"- bias winner: `{b['rule']}` test **{b['test']['accuracy']:.1%}** (lift {b['test']['lift']:+.1%})",
            f"- gap winner: `{block['gap']['train_winner']['rule']}` test "
            f"**{block['gap']['train_winner']['test']['accuracy']:.1%}**",
            f"- vol test: **{block['vol']['test']['accuracy']:.1%}**",
            "",
        ]
    lines += [
        "## Notes",
        "",
        "- Gap predictors here are prior-day proxies (true premarket gap needs futures overnight; not in this CSV bake-off).",
        "- Bias lift must beat majority baseline; thin-coverage rules are only winners if coverage ≥ 25% on train.",
        "- Chain guidance is style mapping only (`guide_only`); never a ticket.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    vix = load_vix()
    nifty = load_ohlc(NIFTY_PATH)
    # Report = last 252 sessions on NIFTY
    report_start = nifty["Date"].iloc[-252]
    # Align to calendar year-ish if possible
    payload: Dict[str, Any] = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "report_start": str(report_start.date()),
        "note": "No calls. Winners fit on train only. Test = last 252 NIFTY sessions.",
        "gap_threshold_pct": GAP_TH,
        "symbols": {},
    }

    payload["symbols"]["NIFTY"] = run_symbol("NIFTY", nifty, vix, report_start)

    if BANK_PATH.is_file():
        bank = load_ohlc(BANK_PATH)
        payload["symbols"]["BANKNIFTY"] = run_symbol("BANKNIFTY", bank, vix, report_start)

    for sym in STOCKS:
        sdf = load_stock(sym)
        if sdf is None or len(sdf) < 300:
            payload["symbols"][sym] = {"symbol": sym, "error": "missing_or_short_cache"}
            continue
        # use same calendar report_start
        payload["symbols"][sym] = run_symbol(sym, sdf, vix, report_start)

    # Freeze recipe from NIFTY
    n = payload["symbols"]["NIFTY"]
    if "error" not in n:
        payload["frozen_recipe"] = {
            "logic_tag": "MORNING_CTX_V1_CANDIDATE",
            "status": "RESEARCH",
            "range_premarket_method": n["range"]["train_winner_premarket"]["method"],
            "range_open_method": n["range"]["train_winner_open_locked"]["method"],
            "bias_rule": n["bias"]["train_winner"]["rule"],
            "gap_rule": n["gap"]["train_winner"]["rule"],
            "vol_method": "atr_pct_expanding_tercile",
            "chain_guidance": "vix_x_vol_pred_atr",
            "nifty_1y_test": {
                "range_pre_inside": n["range"]["train_winner_premarket"]["test"]["inside_pct"],
                "range_open_inside": n["range"]["train_winner_open_locked"]["test"]["inside_pct"],
                "bias_accuracy": n["bias"]["train_winner"]["test"]["accuracy"],
                "bias_lift": n["bias"]["train_winner"]["test"]["lift"],
                "gap_accuracy": n["gap"]["train_winner"]["test"]["accuracy"],
                "vol_accuracy": n["vol"]["test"]["accuracy"],
            },
            "no_calls": True,
        }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    OUT_MD.write_text(to_md(payload), encoding="utf-8")
    print(json.dumps({
        "wrote": str(OUT_JSON),
        "md": str(OUT_MD),
        "frozen": payload.get("frozen_recipe"),
    }, indent=2))


if __name__ == "__main__":
    main()
