"""Deep NIFTY hunt: gap (UP/DOWN/NATURAL) + bias (BULLISH/BEARISH/NEUTRAL).

Rules of honesty
----------------
* Gap AFTER open is observed (±0.35%) — accuracy is definitional 100%. That is
  classification, not prediction. Premarket gap prediction is the hard problem.
* Bias = direction of close vs prior close (session direction). NEUTRAL = abstain.
* When the model SPEAKS (not NATURAL/NEUTRAL), spoken accuracy must clear the
  floor on train; promote only if 1y+3y+5y TEST spoken accuracy also clears.
* Coverage reported separately — 90% with 2% coverage is honest but weak for desk use.

Targets: spoken accuracy >= 0.90 (prefer >= 0.95), maximize coverage among those.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_daily_nse.csv"
OUT_JSON = ROOT / "prod_live" / "reports" / "1y" / "MORNING_NIFTY_GAP_BIAS_90.json"
OUT_MD = ROOT / "prod_live" / "reports" / "1y" / "MORNING_NIFTY_GAP_BIAS_90.md"
GAP_TH = 0.35
FLOOR_SPOKEN = 0.90
FLOOR_SPOKEN_95 = 0.95
MIN_SPEAK_TRAIN = 40  # need enough spoken days on train


def wilder_atr(h, l, c, n=14):
    prev = c.shift(1)
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def load() -> pd.DataFrame:
    df = pd.read_csv(SRC, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.normalize()
    for c in ("Open", "High", "Low", "Close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["Open", "High", "Low", "Close"]).reset_index(drop=True)


def prep(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    h, l, c, o = out["High"], out["Low"], out["Close"], out["Open"]
    atr = wilder_atr(h, l, c, 14)
    prev_c = c.shift(1)
    ret = c.pct_change()
    out["prev_c"] = prev_c
    out["atr_prev"] = atr.shift(1)
    out["atr_pct"] = out["atr_prev"] / prev_c * 100
    out["ret1"] = ret.shift(1)
    out["ret2"] = ret.shift(1) + ret.shift(2)
    out["ret5"] = c.shift(1) / c.shift(6) - 1
    out["sma20"] = c.shift(1).rolling(20).mean()
    out["sma50"] = c.shift(1).rolling(50).mean()
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    out["rsi"] = (100 - 100 / (1 + up / down.replace(0, np.nan))).shift(1)
    # structure
    rh = h.shift(1).rolling(10).max()
    rl = l.shift(1).rolling(10).min()
    out["struct"] = np.where(
        (rh > rh.shift(10)) & (rl > rl.shift(10)), "UP",
        np.where((rh < rh.shift(10)) & (rl < rl.shift(10)), "DN", "RG"),
    )
    # realized gap class (needs open — for scoring gap predictors & post-open truth)
    out["gap_pct"] = (o - prev_c) / prev_c * 100
    out["gap_true"] = np.where(
        out["gap_pct"] > GAP_TH, "GAP_UP",
        np.where(out["gap_pct"] < -GAP_TH, "GAP_DOWN", "NATURAL"),
    )
    # session direction
    out["dir_true"] = np.where(c > prev_c, "BULLISH", "BEARISH")
    out["otc_true"] = np.where(c > o, "BULLISH", np.where(c < o, "BEARISH", "NEUTRAL"))
    # overnight proxy strength features (prior only)
    out["abs_ret1"] = out["ret1"].abs() * 100
    out["above50"] = prev_c > out["sma50"]
    out["rsi_hi"] = out["rsi"] > 55
    out["rsi_lo"] = out["rsi"] < 45
    out["rsi_hi65"] = out["rsi"] > 65
    out["rsi_lo35"] = out["rsi"] < 35
    out["vol_hi"] = out["atr_pct"] > out["atr_pct"].expanding(60).quantile(0.66)
    return out


def score_class(pred: pd.Series, actual: pd.Series, speak_labels: Tuple[str, ...], abstain: str) -> Dict[str, Any]:
    """Spoken accuracy among days where pred in speak_labels; abstain otherwise."""
    m_all = actual.notna() & pred.notna()
    spoken = m_all & pred.isin(list(speak_labels))
    n_all = int(m_all.sum())
    n_sp = int(spoken.sum())
    if n_sp == 0:
        return {
            "days_all": n_all,
            "days_spoken": 0,
            "coverage": 0.0,
            "spoken_acc": None,
            "abstain_rate": 1.0,
            "by_pred": {},
        }
    hit = float((pred[spoken] == actual[spoken]).mean())
    by = {}
    for lab in speak_labels:
        mm = spoken & (pred == lab)
        if mm.sum():
            by[lab] = {
                "n": int(mm.sum()),
                "acc": round(float((pred[mm] == actual[mm]).mean()), 4),
            }
    # overall including abstain as automatic non-error? NO — we only score spoken
    return {
        "days_all": n_all,
        "days_spoken": n_sp,
        "coverage": round(n_sp / max(n_all, 1), 4),
        "spoken_acc": round(hit, 4),
        "abstain_rate": round(1 - n_sp / max(n_all, 1), 4),
        "by_pred": by,
    }


def gap_predictors(df: pd.DataFrame) -> Dict[str, pd.Series]:
    """Premarket gap class predictors (cannot use today's open)."""
    out: Dict[str, pd.Series] = {}
    # always natural
    out["always_natural"] = pd.Series("NATURAL", index=df.index)
    # continue prior day move
    out["continue_th035"] = np.where(
        df["ret1"] * 100 > GAP_TH, "GAP_UP",
        np.where(df["ret1"] * 100 < -GAP_TH, "GAP_DOWN", "NATURAL"),
    )
    out["continue_th050"] = np.where(
        df["ret1"] * 100 > 0.50, "GAP_UP",
        np.where(df["ret1"] * 100 < -0.50, "GAP_DOWN", "NATURAL"),
    )
    out["continue_th080"] = np.where(
        df["ret1"] * 100 > 0.80, "GAP_UP",
        np.where(df["ret1"] * 100 < -0.80, "GAP_DOWN", "NATURAL"),
    )
    out["fade_th050"] = np.where(
        df["ret1"] * 100 > 0.50, "GAP_DOWN",
        np.where(df["ret1"] * 100 < -0.50, "GAP_UP", "NATURAL"),
    )
    out["fade_th080"] = np.where(
        df["ret1"] * 100 > 0.80, "GAP_DOWN",
        np.where(df["ret1"] * 100 < -0.80, "GAP_UP", "NATURAL"),
    )
    # structure-led
    out["struct"] = np.where(df["struct"] == "UP", "GAP_UP", np.where(df["struct"] == "DN", "GAP_DOWN", "NATURAL"))
    # strong only: speak gap only if |ret1| large AND structure agrees; else NATURAL
    strong_up = (df["ret1"] * 100 > 0.80) & (df["struct"] == "UP")
    strong_dn = (df["ret1"] * 100 < -0.80) & (df["struct"] == "DN")
    out["strong_continue_struct"] = np.where(strong_up, "GAP_UP", np.where(strong_dn, "GAP_DOWN", "NATURAL"))
    # only speak extreme; else NATURAL
    out["extreme_ret1_1pct"] = np.where(
        df["ret1"] * 100 > 1.0, "GAP_UP",
        np.where(df["ret1"] * 100 < -1.0, "GAP_DOWN", "NATURAL"),
    )
    out["extreme_ret1_1_5pct"] = np.where(
        df["ret1"] * 100 > 1.5, "GAP_UP",
        np.where(df["ret1"] * 100 < -1.5, "GAP_DOWN", "NATURAL"),
    )
    # 2-day momentum
    out["ret2_th100"] = np.where(
        df["ret2"] * 100 > 1.0, "GAP_UP",
        np.where(df["ret2"] * 100 < -1.0, "GAP_DOWN", "NATURAL"),
    )
    return {k: pd.Series(v, index=df.index) for k, v in out.items()}


def bias_predictors(df: pd.DataFrame) -> Dict[str, pd.Series]:
    """Session direction predictors. NEUTRAL = abstain."""
    out: Dict[str, pd.Series] = {}
    out["always_neutral"] = pd.Series("NEUTRAL", index=df.index)
    out["always_bull"] = pd.Series("BULLISH", index=df.index)
    # continue / fade
    out["cont_any"] = np.where(df["ret1"] > 0, "BULLISH", "BEARISH")
    out["fade_any"] = np.where(df["ret1"] > 0, "BEARISH", "BULLISH")
    out["sma50"] = np.where(df["above50"], "BULLISH", "BEARISH")
    out["rsi50"] = np.where(df["rsi"] > 50, "BULLISH", "BEARISH")
    out["struct"] = np.where(df["struct"] == "UP", "BULLISH", np.where(df["struct"] == "DN", "BEARISH", "NEUTRAL"))
    # unanimous votes
    votes_up = df["above50"].astype(int) + (df["rsi"] > 50).astype(int) + (df["ret1"] > 0).astype(int)
    uni = pd.Series("NEUTRAL", index=df.index)
    uni = uni.mask(votes_up == 3, "BULLISH").mask(votes_up == 0, "BEARISH")
    out["vote3_unanimous"] = uni
    # stronger filters
    strong = pd.Series("NEUTRAL", index=df.index)
    strong = strong.mask(df["rsi_hi65"] & df["above50"] & (df["struct"] == "UP"), "BULLISH")
    strong = strong.mask(df["rsi_lo35"] & (~df["above50"]) & (df["struct"] == "DN"), "BEARISH")
    out["strong_rsi_sma_struct"] = strong
    # only speak on large prior move continue
    big = pd.Series("NEUTRAL", index=df.index)
    big = big.mask(df["ret1"] * 100 > 1.0, "BULLISH").mask(df["ret1"] * 100 < -1.0, "BEARISH")
    out["big_ret1_continue"] = big
    bigf = pd.Series("NEUTRAL", index=df.index)
    bigf = bigf.mask(df["ret1"] * 100 > 1.0, "BEARISH").mask(df["ret1"] * 100 < -1.0, "BULLISH")
    out["big_ret1_fade"] = bigf
    # gap-conditioned AFTER open (uses open — valid for "morning after 9:15" bias, not premarket)
    # If gap up, lean fade or continue variants
    gap_cont = pd.Series("NEUTRAL", index=df.index)
    gap_cont = gap_cont.mask(df["gap_true"] == "GAP_UP", "BULLISH").mask(df["gap_true"] == "GAP_DOWN", "BEARISH")
    out["after_open_gap_continue"] = gap_cont
    gap_fade = pd.Series("NEUTRAL", index=df.index)
    gap_fade = gap_fade.mask(df["gap_true"] == "GAP_UP", "BEARISH").mask(df["gap_true"] == "GAP_DOWN", "BULLISH")
    out["after_open_gap_fade"] = gap_fade
    # only speak on gap days
    gap_only_cont = pd.Series("NEUTRAL", index=df.index)
    gap_only_cont = gap_only_cont.mask(df["gap_true"] == "GAP_UP", "BULLISH").mask(df["gap_true"] == "GAP_DOWN", "BEARISH")
    out["gap_days_continue"] = gap_only_cont  # same as after_open_gap_continue
    # gap + structure agree
    gsa = pd.Series("NEUTRAL", index=df.index)
    gsa = gsa.mask((df["gap_true"] == "GAP_UP") & (df["struct"] == "UP"), "BULLISH")
    gsa = gsa.mask((df["gap_true"] == "GAP_DOWN") & (df["struct"] == "DN"), "BEARISH")
    out["gap_struct_agree"] = gsa
    # gap fade only when |gap| large
    gf = pd.Series("NEUTRAL", index=df.index)
    gf = gf.mask(df["gap_pct"] > 0.80, "BEARISH").mask(df["gap_pct"] < -0.80, "BULLISH")
    out["gap_fade_th080"] = gf
    gf2 = pd.Series("NEUTRAL", index=df.index)
    gf2 = gf2.mask(df["gap_pct"] > 1.0, "BEARISH").mask(df["gap_pct"] < -1.0, "BULLISH")
    out["gap_fade_th100"] = gf2
    gc2 = pd.Series("NEUTRAL", index=df.index)
    gc2 = gc2.mask(df["gap_pct"] > 1.0, "BULLISH").mask(df["gap_pct"] < -1.0, "BEARISH")
    out["gap_cont_th100"] = gc2
    # open-to-close target variants stored separately via actual series
    return {k: pd.Series(v, index=df.index) for k, v in out.items()}


def evaluate_family(
    train: pd.DataFrame,
    test: pd.DataFrame,
    predictors_fn,
    actual_col: str,
    speak_labels: Tuple[str, ...],
    abstain: str,
    family: str,
) -> Dict[str, Any]:
    rows = []
    ptr, pte = predictors_fn(train), predictors_fn(test)
    for name, pred_tr in ptr.items():
        tr = score_class(pred_tr, train[actual_col], speak_labels, abstain)
        te = score_class(pte[name], test[actual_col], speak_labels, abstain)
        rows.append({"rule": name, "family": family, "train": tr, "test": te})

    def ok_train(r, floor):
        t = r["train"]
        return (
            t.get("spoken_acc") is not None
            and t["spoken_acc"] >= floor
            and t["days_spoken"] >= MIN_SPEAK_TRAIN
        )

    picks = {}
    for floor, tag in ((FLOOR_SPOKEN, "90"), (FLOOR_SPOKEN_95, "95")):
        pool = [r for r in rows if ok_train(r, floor)]
        if pool:
            # maximize coverage, then spoken_acc
            win = max(pool, key=lambda r: (r["train"]["coverage"], r["train"]["spoken_acc"]))
            test_ok = (
                win["test"].get("spoken_acc") is not None
                and win["test"]["spoken_acc"] >= floor
                and win["test"]["days_spoken"] >= 10
            )
            picks[tag] = {"rule": win["rule"], "train": win["train"], "test": win["test"], "test_ok": test_ok}
        else:
            # best spoken acc even if below floor
            spoken = [r for r in rows if r["train"].get("spoken_acc") is not None and r["train"]["days_spoken"] >= 20]
            if spoken:
                win = max(spoken, key=lambda r: (r["train"]["spoken_acc"], r["train"]["coverage"]))
                picks[tag] = {
                    "rule": win["rule"],
                    "train": win["train"],
                    "test": win["test"],
                    "test_ok": False,
                    "note": "no rule cleared floor on train with enough speaks",
                }
            else:
                picks[tag] = {"rule": None, "test_ok": False, "note": "no spoken rules"}

    # always include always_natural / always_neutral baselines
    base_name = "always_natural" if abstain == "NATURAL" else "always_neutral"
    base = next((r for r in rows if r["rule"] == base_name), None)
    return {
        "picks": picks,
        "baseline": base,
        "all": sorted(
            rows,
            key=lambda r: (
                -(r["train"].get("spoken_acc") or -1),
                -(r["train"].get("coverage") or 0),
            ),
        ),
    }


def cross_promote(df: pd.DataFrame, rule: str, family: str, actual_col: str, speak, abstain, predictors_fn, floor: float):
    """Evaluate one rule on 1y/3y/5y tests."""
    out = {}
    for lab, n in (("1y", 252), ("3y", 756), ("5y", 1260)):
        start = df["Date"].iloc[-n]
        test = df[df["Date"] >= start]
        pred = predictors_fn(test)[rule]
        sc = score_class(pred, test[actual_col], speak, abstain)
        out[lab] = sc
    ok = all(
        (out[k].get("spoken_acc") or 0) >= floor and out[k]["days_spoken"] >= 10
        for k in ("1y", "3y", "5y")
    )
    # if rule never speaks, not ok
    if all(out[k]["days_spoken"] == 0 for k in out):
        ok = False
    return {"rule": rule, "family": family, "floor": floor, "tests": out, "promote": ok}


def main() -> None:
    df = prep(load())
    splits = []
    for lab, n in (("1y", 252), ("3y", 756), ("5y", 1260)):
        start = df["Date"].iloc[-n]
        train, test = df[df["Date"] < start], df[df["Date"] >= start]
        gap = evaluate_family(
            train, test, gap_predictors, "gap_true",
            ("GAP_UP", "GAP_DOWN"), "NATURAL", "premarket_gap",
        )
        # For gap, also score "spoken includes NATURAL" overall accuracy (3-class)
        # but promotion uses spoken UP/DOWN accuracy when we call a gap.
        bias_close = evaluate_family(
            train, test, bias_predictors, "dir_true",
            ("BULLISH", "BEARISH"), "NEUTRAL", "bias_close_vs_prev",
        )
        bias_otc = evaluate_family(
            train, test, bias_predictors, "otc_true",
            ("BULLISH", "BEARISH"), "NEUTRAL", "bias_open_to_close",
        )
        # observed gap accuracy (post-open) — definitional
        observed = score_class(test["gap_true"], test["gap_true"], ("GAP_UP", "GAP_DOWN", "NATURAL"), "")
        splits.append({
            "label": lab,
            "start": str(start.date()),
            "end": str(test["Date"].max().date()),
            "train_days": len(train),
            "test_days": len(test),
            "gap_premarket": {
                "picks": gap["picks"],
                "top": [
                    {"rule": r["rule"], "train": r["train"], "test": r["test"]}
                    for r in gap["all"][:15]
                ],
            },
            "gap_observed_after_open": {
                "note": "Using true open vs prior close — classification is exact by definition",
                "test_3class_acc": 1.0,
                "gap_up_rate": round(float((test["gap_true"] == "GAP_UP").mean()), 4),
                "gap_down_rate": round(float((test["gap_true"] == "GAP_DOWN").mean()), 4),
                "natural_rate": round(float((test["gap_true"] == "NATURAL").mean()), 4),
            },
            "bias_close": {
                "picks": bias_close["picks"],
                "top": [
                    {"rule": r["rule"], "train": r["train"], "test": r["test"]}
                    for r in bias_close["all"][:15]
                ],
            },
            "bias_open_to_close": {
                "picks": bias_otc["picks"],
                "top": [
                    {"rule": r["rule"], "train": r["train"], "test": r["test"]}
                    for r in bias_otc["all"][:15]
                ],
            },
        })

    # Cross-window promote candidates from 3y train picks + top spoken
    candidates = []
    s3 = next(s for s in splits if s["label"] == "3y")
    for family, key, actual, speak, abstain, pfn in (
        ("premarket_gap", "gap_premarket", "gap_true", ("GAP_UP", "GAP_DOWN"), "NATURAL", gap_predictors),
        ("bias_close", "bias_close", "dir_true", ("BULLISH", "BEARISH"), "NEUTRAL", bias_predictors),
        ("bias_otc", "bias_open_to_close", "otc_true", ("BULLISH", "BEARISH"), "NEUTRAL", bias_predictors),
    ):
        for floor_tag, floor in (("90", 0.90), ("95", 0.95)):
            pick = s3[key]["picks"].get(floor_tag) or {}
            if pick.get("rule"):
                candidates.append((pick["rule"], family, actual, speak, abstain, pfn, floor, floor_tag))
        for r in s3[key]["top"][:8]:
            if r["train"].get("spoken_acc"):
                candidates.append((r["rule"], family, actual, speak, abstain, pfn, 0.90, "top"))

    # unique
    seen = set()
    promos = []
    for rule, family, actual, speak, abstain, pfn, floor, tag in candidates:
        k = (rule, family, floor)
        if k in seen:
            continue
        seen.add(k)
        promos.append(cross_promote(df, rule, family, actual, speak, abstain, pfn, floor))

    # best promote per family
    best = {}
    for family in ("premarket_gap", "bias_close", "bias_otc"):
        pool = [p for p in promos if p["family"] == family and p["promote"]]
        if pool:
            # prefer higher floor cleared, then coverage on 3y
            def key(p):
                cov = p["tests"]["3y"]["coverage"]
                acc = p["tests"]["3y"]["spoken_acc"] or 0
                return (1 if p["floor"] >= 0.95 else 0, acc, cov)
            best[family] = max(pool, key=key)
        else:
            # best min spoken acc across windows among those with coverage>0
            pool2 = [p for p in promos if p["family"] == family]
            if pool2:
                def mink(p):
                    accs = [p["tests"][k]["spoken_acc"] for k in ("1y", "3y", "5y") if p["tests"][k]["spoken_acc"] is not None]
                    covs = [p["tests"][k]["coverage"] for k in ("1y", "3y", "5y")]
                    return (min(accs) if accs else 0, sum(covs) / 3)
                best[family] = max(pool2, key=mink)
                best[family] = {**best[family], "promote": False}

    payload = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "definitions": {
            "gap_true": f"open vs prior close ±{GAP_TH}% → GAP_UP/GAP_DOWN/NATURAL",
            "bias_close": "close vs prior close → BULLISH/BEARISH",
            "bias_otc": "close vs open → BULLISH/BEARISH/NEUTRAL",
            "spoken_accuracy": "accuracy only on days the rule does NOT abstain",
            "promote": "spoken_acc >= floor on ALL of 1y,3y,5y test with >=10 spoken days each",
        },
        "splits": splits,
        "promotions": promos,
        "best_per_family": best,
        "recommendation": {
            "gap_after_open": {
                "method": "observe_open_vs_prev_close",
                "accuracy": 1.0,
                "note": "Not a prediction — classify when cash open is known.",
            },
            "gap_premarket": best.get("premarket_gap"),
            "bias_close": best.get("bias_close"),
            "bias_open_to_close": best.get("bias_otc"),
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    # slim promotions for JSON size
    payload["promotions"] = [
        p for p in promos if p.get("promote") or p["rule"] in {
            (best.get(f) or {}).get("rule") for f in best
        }
    ]
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# NIFTY gap + bias deep hunt (≥90% / ≥95% when speaking)",
        "",
        f"**Generated:** `{payload['generated_at']}`",
        "",
        "## Definitions",
        "",
        "- **Gap true:** open vs prior close (±0.35%) → GAP_UP / GAP_DOWN / NATURAL.",
        "- **Bias (close):** close vs prior close → BULLISH / BEARISH.",
        "- **Bias (open→close):** close vs open.",
        "- **Spoken accuracy:** only days the rule does **not** abstain (NEUTRAL/NATURAL).",
        "- **Promote:** spoken_acc ≥ floor on **1y + 3y + 5y** tests.",
        "",
        "## Gap after open (observed)",
        "",
        "Once cash open is known, gap class is **exact by definition (100%)**.",
        "This is classification for the morning brief after 9:15 — not a forecast.",
        "",
        "## Recommendation summary",
        "",
    ]
    for title, key in (
        ("Premarket gap (hard)", "gap_premarket"),
        ("Bias close vs prior", "bias_close"),
        ("Bias open→close", "bias_open_to_close"),
    ):
        b = payload["recommendation"].get(key)
        lines.append(f"### {title}")
        if not b:
            lines += ["No candidate.", ""]
            continue
        lines += [
            f"- rule: `{b.get('rule')}` · promote **{b.get('promote')}** · floor {b.get('floor')}",
        ]
        for lab in ("1y", "3y", "5y"):
            t = b["tests"][lab]
            lines.append(
                f"  - {lab}: spoken_acc **{(t.get('spoken_acc') or 0):.1%}** · "
                f"coverage {t.get('coverage'):.1%} · spoken_days {t.get('days_spoken')}"
            )
        lines.append("")

    lines += ["## Per-split detail (3y train picks)", ""]
    for sp in splits:
        if sp["label"] != "3y":
            continue
        lines.append(f"### Window `{sp['start']}` → `{sp['end']}`")
        for fam, key in (
            ("Premarket gap", "gap_premarket"),
            ("Bias close", "bias_close"),
            ("Bias OTC", "bias_open_to_close"),
        ):
            lines.append(f"#### {fam}")
            for tag in ("90", "95"):
                p = sp[key]["picks"].get(tag) or {}
                if not p.get("rule"):
                    lines.append(f"- ≥{tag}%: none")
                    continue
                tr, te = p["train"], p["test"]
                lines.append(
                    f"- ≥{tag}% pick `{p['rule']}` train spoken **{(tr.get('spoken_acc') or 0):.1%}** "
                    f"cov {tr.get('coverage'):.1%} → test **{(te.get('spoken_acc') or 0):.1%}** "
                    f"cov {te.get('coverage'):.1%} · test_ok={p.get('test_ok')}"
                )
            lines.append("")
            lines.append("| Top train spoken | Train acc | Train cov | Test acc | Test cov |")
            lines.append("|---|---:|---:|---:|---:|")
            for r in sp[key]["top"][:8]:
                tr, te = r["train"], r["test"]
                lines.append(
                    f"| `{r['rule']}` | {tr.get('spoken_acc')} | {tr.get('coverage')} | "
                    f"{te.get('spoken_acc')} | {te.get('coverage')} |"
                )
            lines.append("")

    lines += [
        "## Honest conclusion gates",
        "",
        "1. **Gap after open:** hold observe-open classifier (100%).",
        "2. **Premarket gap / bias:** hold a speaking rule only if promote=True at ≥90%.",
        "3. If nothing promotes, keep **NATURAL / NEUTRAL** as the proven default.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "wrote": str(OUT_MD),
        "recommendation": {
            k: (
                {"rule": v.get("rule"), "promote": v.get("promote"), "tests": {
                    lab: {"acc": v["tests"][lab].get("spoken_acc"), "cov": v["tests"][lab].get("coverage")}
                    for lab in ("1y", "3y", "5y")
                }} if isinstance(v, dict) and "tests" in v else v
            )
            for k, v in payload["recommendation"].items()
        },
    }, indent=2))


if __name__ == "__main__":
    main()
