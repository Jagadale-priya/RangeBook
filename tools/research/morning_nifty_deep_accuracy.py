"""Deep NIFTY-only accuracy research for morning session context (no calls).

Accuracy definitions (no look-ahead):
  RANGE (primary):
    full_containment = (Low >= box_lo) AND (High <= box_hi)
    Also: high_ok, low_ok, close_inside, median_width_pct, breach_mean_pct
  BIAS:
    hit = predicted side matches (Close > prev_close) when not abstaining
    coverage = fraction of days with a side prediction
    lift = accuracy - majority_class_accuracy on same days
  GAP (premarket proxies only):
    hit = predicted class == actual open-vs-prev_close class (±0.35%)
  VOL:
    hit = predicted tercile == realized range tercile

Fit: winners chosen only on TRAIN (Date < report_start).
Report windows: last 1y / 3y / 5y (and optional fixed calendar splits).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_daily_nse.csv"
OUT_JSON = ROOT / "prod_live" / "reports" / "1y" / "MORNING_NIFTY_DEEP_ACCURACY.json"
OUT_MD = ROOT / "prod_live" / "reports" / "1y" / "MORNING_NIFTY_DEEP_ACCURACY.md"
GAP_TH = 0.35
FLOOR = 0.004


def wilder_atr(high, low, close, n=14):
    prev_c = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_c).abs(), (low - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def load() -> pd.DataFrame:
    df = pd.read_csv(SRC, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.normalize()
    for c in ("Open", "High", "Low", "Close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["Open", "High", "Low", "Close"]).reset_index(drop=True)


def features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    h, l, c, o = out["High"], out["Low"], out["Close"], out["Open"]
    day_rng = (h - l).clip(lower=0)
    atr = wilder_atr(h, l, c, 14)
    prev_c = c.shift(1)
    prev_rng = day_rng.shift(1)
    atr_prev = atr.shift(1)
    ret = c.pct_change()
    out["prev_c"] = prev_c
    out["prev_rng"] = prev_rng
    out["atr_prev"] = atr_prev
    out["med20"] = prev_rng.rolling(20).median()
    out["p70"] = prev_rng.rolling(20).quantile(0.70)
    out["p80"] = prev_rng.rolling(20).quantile(0.80)
    out["p90"] = prev_rng.rolling(20).quantile(0.90)
    out["vol20"] = ret.shift(1).rolling(20).std()
    out["sma20"] = c.shift(1).rolling(20).mean()
    out["sma50"] = c.shift(1).rolling(50).mean()
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    out["rsi"] = (100 - 100 / (1 + up / down.replace(0, np.nan))).shift(1)
    out["ret1"] = ret.shift(1)
    # structure 10d vs prior 10d (prior close only)
    rh = h.shift(1).rolling(10).max()
    rl = l.shift(1).rolling(10).min()
    out["structure"] = np.where(
        (rh > rh.shift(10)) & (rl > rl.shift(10)), "UPTREND",
        np.where((rh < rh.shift(10)) & (rl < rl.shift(10)), "DOWNTREND", "RANGE"),
    )
    out["gap_pct"] = (o - prev_c) / prev_c * 100
    out["gap_class"] = np.where(
        out["gap_pct"] > GAP_TH, "GAP_UP",
        np.where(out["gap_pct"] < -GAP_TH, "GAP_DOWN", "NATURAL"),
    )
    out["close_up"] = c > prev_c
    out["realized_pct"] = day_rng / prev_c * 100
    atr_pct = atr_prev / prev_c * 100
    out["atr_pct"] = atr_pct
    q33 = atr_pct.expanding(60).quantile(0.33)
    q66 = atr_pct.expanding(60).quantile(0.66)
    out["vol_pred"] = np.where(atr_pct >= q66, "HIGH", np.where(atr_pct <= q33, "LOW", "NORMAL"))
    rq33 = out["realized_pct"].expanding(60).quantile(0.33)
    rq66 = out["realized_pct"].expanding(60).quantile(0.66)
    out["vol_act"] = np.where(
        out["realized_pct"] >= rq66, "HIGH",
        np.where(out["realized_pct"] <= rq33, "LOW", "NORMAL"),
    )
    return out


def width_bank(df: pd.DataFrame) -> Dict[str, pd.Series]:
    price = df["prev_c"]
    floor = price * FLOOR
    atr = df["atr_prev"]
    yday = df["prev_rng"]
    return {
        "held_atr14_1_2x": np.maximum(atr * 1.2, floor),
        "atr14": np.maximum(atr, floor),
        "atr14_1_5x": np.maximum(atr * 1.5, floor),
        "atr14_2_0x": np.maximum(atr * 2.0, floor),
        "atr14_2_5x": np.maximum(atr * 2.5, floor),
        "max_yday_atr": np.maximum(np.maximum(yday, atr), floor),
        "max_yday_atr_1_2x": np.maximum(np.maximum(yday, atr) * 1.2, floor),
        "max_yday_atr_1_5x": np.maximum(np.maximum(yday, atr) * 1.5, floor),
        "yesterday_range": yday,
        "median_20": df["med20"],
        "p70_20": df["p70"],
        "p80_20": df["p80"],
        "p90_20": df["p90"],
        "vol20_1_5sd": df["vol20"] * price * 1.5,
        "vol20_2sd": df["vol20"] * price * 2.0,
    }


def box_from_width(df: pd.DataFrame, width: pd.Series, anchor: str) -> Tuple[pd.Series, pd.Series]:
    half = width / 2.0
    if anchor == "session_open":
        center = df["Open"]
        hi = center + half
        lo = center - half
        prev = df["prev_c"]
        gap = center - prev
        big = (gap.abs() / prev) >= 0.0035
        extra = np.minimum(gap.abs(), width * 0.35)
        hi = pd.Series(np.where(big & (gap > 0), hi + extra, hi), index=df.index)
        lo = pd.Series(np.where(big & (gap < 0), lo - extra, lo), index=df.index)
    else:
        center = df["prev_c"]
        hi = center + half
        lo = center - half
    return hi, lo


def range_accuracy(df: pd.DataFrame, width: pd.Series, anchor: str) -> Dict[str, Any]:
    """Correct range accuracy: BOTH high and low must stay inside the box."""
    hi, lo = box_from_width(df, width, anchor)
    high_ok = df["High"] <= hi
    low_ok = df["Low"] >= lo
    full = high_ok & low_ok
    close_in = (df["Close"] >= lo) & (df["Close"] <= hi)
    width_pct = width / df["prev_c"]
    # how far outside when missed (as fraction of price)
    high_breach = ((df["High"] - hi).clip(lower=0) / df["prev_c"]).where(~high_ok)
    low_breach = ((lo - df["Low"]).clip(lower=0) / df["prev_c"]).where(~low_ok)
    use = full.notna() & width.notna() & (width > 0) & df["prev_c"].notna()
    n = int(use.sum())
    if n == 0:
        return {"days": 0}
    return {
        "days": n,
        "full_containment_acc": round(float(full[use].mean()), 4),
        "high_ok_acc": round(float(high_ok[use].mean()), 4),
        "low_ok_acc": round(float(low_ok[use].mean()), 4),
        "close_inside_acc": round(float(close_in[use].mean()), 4),
        "median_width_pct": round(float(width_pct[use].median()), 4),
        "p90_width_pct": round(float(width_pct[use].quantile(0.90)), 4),
        "mean_high_breach_pct": round(float(np.nan_to_num(high_breach[use].mean(skipna=True), nan=0.0)) * 100, 4),
        "mean_low_breach_pct": round(float(np.nan_to_num(low_breach[use].mean(skipna=True), nan=0.0)) * 100, 4),
        # efficiency: containment per unit width (not used as sole winner)
        "efficiency": round(float(full[use].mean()) / float(width_pct[use].median()), 4)
        if float(width_pct[use].median()) > 0 else 0.0,
    }


def pick_range_winner(train: pd.DataFrame, widths: Dict[str, pd.Series], anchor: str) -> Dict[str, Any]:
    """Primary: max full_containment among methods with median_width_pct <= 2.0%.
    Tie-break: higher efficiency, then tighter width.
    Fallback: best containment if none under 2%.
    """
    rows = []
    for name, w in widths.items():
        m = range_accuracy(train, w, anchor)
        m["method"] = name
        m["anchor"] = anchor
        rows.append(m)
    under = [r for r in rows if r.get("days", 0) > 50 and r.get("median_width_pct", 99) <= 0.02]
    pool = under if under else [r for r in rows if r.get("days", 0) > 50]
    winner = max(
        pool,
        key=lambda r: (
            r.get("full_containment_acc", 0),
            r.get("efficiency", 0),
            -r.get("median_width_pct", 99),
        ),
    )
    return {"winner": winner, "all": rows}


def bias_rules(df: pd.DataFrame) -> Dict[str, pd.Series]:
    """1=up, 0=down, NaN=abstain."""
    mom = (df["ret1"] > 0).astype(float)
    fade = (df["ret1"] < 0).astype(float)
    above = (df["prev_c"] > df["sma50"]).astype(float)
    rsi_up = (df["rsi"] > 50).astype(float)
    votes = mom.fillna(0) + above.fillna(0) + rsi_up.fillna(0)
    # only when unanimous
    uni = pd.Series(np.nan, index=df.index, dtype=float)
    uni = uni.mask(votes == 3, 1.0).mask(votes == 0, 0.0)
    # structure only
    st = pd.Series(np.nan, index=df.index, dtype=float)
    st = st.mask(df["structure"] == "UPTREND", 1.0).mask(df["structure"] == "DOWNTREND", 0.0)
    # structure + SMA agree
    agree = pd.Series(np.nan, index=df.index, dtype=float)
    agree = agree.mask((df["structure"] == "UPTREND") & (df["prev_c"] > df["sma50"]), 1.0)
    agree = agree.mask((df["structure"] == "DOWNTREND") & (df["prev_c"] <= df["sma50"]), 0.0)
    # always neutral = all NaN (abstain forever)
    neutral = pd.Series(np.nan, index=df.index, dtype=float)
    return {
        "NEUTRAL_ABSTAIN": neutral,
        "yesterday_continue": mom,
        "yesterday_fade": fade,
        "above_sma50": above,
        "rsi_above_50": rsi_up,
        "vote3_unanimous": uni,
        "structure_only": st,
        "structure_and_sma50": agree,
    }


def bias_accuracy(df: pd.DataFrame, pred: pd.Series) -> Dict[str, Any]:
    actual = df["close_up"].astype(float)
    spoken = pred.notna() & actual.notna() & df["prev_c"].notna()
    n_all = int((actual.notna() & df["prev_c"].notna()).sum())
    n = int(spoken.sum())
    if n == 0:
        # abstain-all: directional accuracy N/A; report base rate only
        base = float(actual[actual.notna()].mean()) if n_all else 0.0
        return {
            "days_spoken": 0,
            "coverage": 0.0,
            "accuracy": None,
            "base_up_rate_all": round(base, 4),
            "majority_acc_spoken": None,
            "lift": None,
            "note": "abstain — no directional calls",
        }
    hit = float((pred[spoken] == actual[spoken]).mean())
    base_spoken = float(actual[spoken].mean())
    maj = 1.0 if base_spoken >= 0.5 else 0.0
    maj_acc = float((actual[spoken] == maj).mean())
    return {
        "days_spoken": n,
        "coverage": round(n / max(n_all, 1), 4),
        "accuracy": round(hit, 4),
        "base_up_rate_spoken": round(base_spoken, 4),
        "majority_acc_spoken": round(maj_acc, 4),
        "lift": round(hit - maj_acc, 4),
    }


def gap_accuracy(df: pd.DataFrame, pred: pd.Series) -> Dict[str, Any]:
    actual = df["gap_class"]
    m = pred.notna() & actual.notna()
    n = int(m.sum())
    if n == 0:
        return {"days": 0, "accuracy": None}
    hit = float((pred[m] == actual[m]).mean())
    # class-conditional
    by = {}
    for cls in ("GAP_UP", "GAP_DOWN", "NATURAL"):
        mm = m & (actual == cls)
        if mm.sum():
            # accuracy when actual is cls: how often we predicted correctly
            by[cls] = {
                "n": int(mm.sum()),
                "recall": round(float((pred[mm] == cls).mean()), 4),
            }
    return {
        "days": n,
        "accuracy": round(hit, 4),
        "natural_base_rate": round(float((actual[m] == "NATURAL").mean()), 4),
        "by_actual": by,
    }


def vol_accuracy(df: pd.DataFrame) -> Dict[str, Any]:
    m = df["vol_pred"].notna() & df["vol_act"].notna()
    n = int(m.sum())
    if n == 0:
        return {"days": 0}
    return {
        "days": n,
        "accuracy": round(float((df.loc[m, "vol_pred"] == df.loc[m, "vol_act"]).mean()), 4),
    }


def eval_window(df: pd.DataFrame, start: pd.Timestamp, end: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    m = df["Date"] >= start
    if end is not None:
        m &= df["Date"] <= end
    return df.loc[m].copy()


def run_split(df: pd.DataFrame, report_start: pd.Timestamp, label: str) -> Dict[str, Any]:
    train = df[df["Date"] < report_start].copy()
    test = df[df["Date"] >= report_start].copy()
    if len(test) < 40 or len(train) < 200:
        return {"label": label, "error": f"train={len(train)} test={len(test)}"}

    # --- RANGE ---
    w_train = width_bank(train)
    w_test = width_bank(test)
    range_out = {}
    for anchor in ("prev_close", "session_open"):
        pick = pick_range_winner(train, w_train, anchor)
        win = pick["winner"]
        # evaluate ALL methods on test with correct containment
        test_rows = []
        for name, w in w_test.items():
            row = range_accuracy(test, w, anchor)
            row["method"] = name
            test_rows.append(row)
        held = next(r for r in test_rows if r["method"] == "held_atr14_1_2x")
        win_test = next(r for r in test_rows if r["method"] == win["method"])
        # also best-on-test for information only (not for selection)
        best_test = max(test_rows, key=lambda r: (r.get("full_containment_acc", 0), -r.get("median_width_pct", 99)))
        range_out[anchor] = {
            "train_winner": win,
            "train_winner_on_test": win_test,
            "held_atr14_1_2x_on_test": held,
            "oracle_best_on_test_info_only": best_test,
            "all_test": sorted(test_rows, key=lambda r: -r.get("full_containment_acc", 0)),
        }

    # --- BIAS ---
    bias_rows = []
    rules_tr = bias_rules(train)
    rules_te = bias_rules(test)
    for name, pred in rules_tr.items():
        bias_rows.append({
            "rule": name,
            "train": bias_accuracy(train, pred),
            "test": bias_accuracy(test, rules_te[name]),
        })
    # winner: among rules with train coverage>=0.2 OR NEUTRAL, prefer lift then accuracy; NEUTRAL if no lift>=0.02
    spoken = [r for r in bias_rows if r["rule"] != "NEUTRAL_ABSTAIN" and (r["train"].get("lift") or -1) is not None]
    good = [r for r in spoken if (r["train"].get("coverage") or 0) >= 0.2 and (r["train"].get("lift") or -1) >= 0.02]
    if good:
        win_bias = max(good, key=lambda r: (r["train"]["lift"], r["train"]["accuracy"], r["train"]["coverage"]))
        bias_choice = "directional"
    else:
        win_bias = next(r for r in bias_rows if r["rule"] == "NEUTRAL_ABSTAIN")
        bias_choice = "NEUTRAL_ABSTAIN_no_edge"

    # --- GAP ---
    train = train.copy()
    test = test.copy()
    train["g_continue"] = np.where(train["ret1"] * 100 > GAP_TH, "GAP_UP", np.where(train["ret1"] * 100 < -GAP_TH, "GAP_DOWN", "NATURAL"))
    test["g_continue"] = np.where(test["ret1"] * 100 > GAP_TH, "GAP_UP", np.where(test["ret1"] * 100 < -GAP_TH, "GAP_DOWN", "NATURAL"))
    train["g_fade"] = np.where(train["ret1"] * 100 > GAP_TH, "GAP_DOWN", np.where(train["ret1"] * 100 < -GAP_TH, "GAP_UP", "NATURAL"))
    test["g_fade"] = np.where(test["ret1"] * 100 > GAP_TH, "GAP_DOWN", np.where(test["ret1"] * 100 < -GAP_TH, "GAP_UP", "NATURAL"))
    train["g_natural"] = "NATURAL"
    test["g_natural"] = "NATURAL"
    train["g_struct"] = np.where(train["structure"] == "UPTREND", "GAP_UP", np.where(train["structure"] == "DOWNTREND", "GAP_DOWN", "NATURAL"))
    test["g_struct"] = np.where(test["structure"] == "UPTREND", "GAP_UP", np.where(test["structure"] == "DOWNTREND", "GAP_DOWN", "NATURAL"))
    gap_rows = []
    for col, gap_rule in (
        ("g_natural", "always_natural"),
        ("g_continue", "prior_continue"),
        ("g_fade", "prior_fade"),
        ("g_struct", "structure"),
    ):
        gap_rows.append({
            "rule": gap_rule,
            "train": gap_accuracy(train, train[col]),
            "test": gap_accuracy(test, test[col]),
        })
    win_gap = max(gap_rows, key=lambda r: (r["train"].get("accuracy") or 0, r["train"].get("days") or 0))

    return {
        "label": label,
        "report_start": str(report_start.date()),
        "report_end": str(test["Date"].max().date()),
        "train_days": int(len(train)),
        "test_days": int(len(test)),
        "range": range_out,
        "bias": {"choice": bias_choice, "winner": win_bias, "all": bias_rows},
        "gap": {"winner": win_gap, "all": gap_rows},
        "vol": {"train": vol_accuracy(train), "test": vol_accuracy(test)},
    }


def to_md(payload: Dict[str, Any]) -> str:
    lines = [
        "# NIFTY-only deep morning context accuracy",
        "",
        f"**Generated:** `{payload['generated_at']}`",
        "",
        "## Accuracy definitions",
        "",
        "1. **Range full containment** = actual Low ≥ box_lo **and** actual High ≤ box_hi (both required).",
        "2. Also reported: high_ok, low_ok, close_inside, median width %.",
        "3. **Bias accuracy** = among days with a side prediction only; lift vs majority on those days. Abstain ≠ hit.",
        "4. **Gap accuracy** = predicted class vs actual open-vs-prior-close (±0.35%).",
        "5. Winners fit on **train only**; test is holdout.",
        "",
    ]
    for split in payload["splits"]:
        if split.get("error"):
            lines += [f"## {split['label']}", f"Error: {split['error']}", ""]
            continue
        lines += [
            f"## {split['label']}  (`{split['report_start']}` → `{split['report_end']}`)",
            f"Train {split['train_days']} · Test **{split['test_days']}**",
            "",
            "### Range — session_open (useful after cash open)",
            "",
        ]
        ro = split["range"]["session_open"]
        w = ro["train_winner"]
        wt = ro["train_winner_on_test"]
        held = ro["held_atr14_1_2x_on_test"]
        lines += [
            f"- **Train-picked winner:** `{w['method']}`",
            f"  - train containment **{w['full_containment_acc']:.1%}** · width {w['median_width_pct']:.2%}",
            f"  - test containment **{wt['full_containment_acc']:.1%}** · high_ok {wt['high_ok_acc']:.1%} · "
            f"low_ok {wt['low_ok_acc']:.1%} · close_in {wt['close_inside_acc']:.1%} · width {wt['median_width_pct']:.2%}",
            f"- **Held `atr14_1_2x` on test:** containment **{held['full_containment_acc']:.1%}** · "
            f"width {held['median_width_pct']:.2%} · high_ok {held['high_ok_acc']:.1%} · low_ok {held['low_ok_acc']:.1%}",
            "",
            "Top test containment (info only — not used to pick):",
            "",
            "| Method | Full contain | High ok | Low ok | Close in | Width |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for r in ro["all_test"][:8]:
            lines.append(
                f"| `{r['method']}` | {r['full_containment_acc']:.1%} | {r['high_ok_acc']:.1%} | "
                f"{r['low_ok_acc']:.1%} | {r['close_inside_acc']:.1%} | {r['median_width_pct']:.2%} |"
            )
        rp = split["range"]["prev_close"]
        lines += [
            "",
            "### Range — premarket (prev_close center)",
            f"- Train winner `{rp['train_winner']['method']}` → test containment "
            f"**{rp['train_winner_on_test']['full_containment_acc']:.1%}** width "
            f"{rp['train_winner_on_test']['median_width_pct']:.2%}",
            f"- Held atr14_1_2x test containment **{rp['held_atr14_1_2x_on_test']['full_containment_acc']:.1%}**",
            "",
            "### Bias",
            f"- Choice: **{split['bias']['choice']}** · rule `{split['bias']['winner']['rule']}`",
        ]
        bt = split["bias"]["winner"]["test"]
        if bt.get("accuracy") is None:
            lines.append(f"  - test: abstain (base up-rate {bt.get('base_up_rate_all')})")
        else:
            lines.append(
                f"  - test accuracy **{bt['accuracy']:.1%}** · lift {bt['lift']:+.1%} · coverage {bt['coverage']:.0%}"
            )
        gacc = split["gap"]["winner"]["test"].get("accuracy") or 0
        gbase = split["gap"]["winner"]["test"].get("natural_base_rate") or 0
        vacc = split["vol"]["test"].get("accuracy") or 0
        grule = split["gap"]["winner"]["rule"]
        lines += [
            "",
            "### Gap / Vol",
            f"- Gap winner `{grule}` test accuracy **{gacc:.1%}** (natural base {gbase:.1%})",
            f"- Vol tercile test accuracy **{vacc:.1%}**",
            "",
        ]
    lines += [
        "## Verdict notes",
        "",
        "- Prefer session_open containment as the live morning box accuracy.",
        "- If held method trails a wider ATR multiple on containment, note the width tradeoff.",
        "- Keep bias NEUTRAL unless a rule shows train lift ≥ +2% with coverage ≥ 20% and holds on test.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    raw = load()
    df = features(raw)
    end = df["Date"].max()
    # report windows by session count
    splits = []
    for label, n in (("last_1y_252", 252), ("last_3y_756", 756), ("last_5y_1260", 1260)):
        start = df["Date"].iloc[-n]
        try:
            splits.append(run_split(df, start, label))
        except Exception as exc:
            splits.append({"label": label, "error": repr(exc)})
    try:
        splits.append(run_split(df, pd.Timestamp("2024-01-01"), "calendar_2024_plus"))
    except Exception as exc:
        splits.append({"label": "calendar_2024_plus", "error": repr(exc)})

    payload = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "symbol": "NIFTY",
        "source": str(SRC),
        "end": str(end.date()),
        "definitions": {
            "range_full_containment": "(Low >= box_lo) AND (High <= box_hi)",
            "bias": "spoken days only; abstain excluded from accuracy denominator",
            "no_lookahead": "widths and predictors use prior close / prior ATR only",
        },
        "splits": splits,
    }
    s3 = next((s for s in splits if s.get("label") == "last_3y_756"), None)
    if s3 and not s3.get("error"):
        open_w = s3["range"]["session_open"]
        payload["recommendation"] = {
            "from_split": "last_3y_756",
            "range_open_method": open_w["train_winner"]["method"],
            "range_open_test_containment": open_w["train_winner_on_test"]["full_containment_acc"],
            "range_open_test_width": open_w["train_winner_on_test"]["median_width_pct"],
            "held_atr14_1_2x_test_containment": open_w["held_atr14_1_2x_on_test"]["full_containment_acc"],
            "held_atr14_1_2x_test_width": open_w["held_atr14_1_2x_on_test"]["median_width_pct"],
            "bias": s3["bias"]["choice"],
            "gap": s3["gap"]["winner"]["rule"],
            "vol_test": s3["vol"]["test"]["accuracy"],
        }
    elif s3:
        payload["recommendation"] = {"error": s3.get("error")}

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    OUT_MD.write_text(to_md(payload), encoding="utf-8")
    print(json.dumps({"wrote": str(OUT_MD), "recommendation": payload.get("recommendation")}, indent=2))


if __name__ == "__main__":
    main()
