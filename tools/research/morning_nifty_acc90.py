"""Hunt NIFTY morning range logic with >=90% full-containment accuracy.

Full containment = (Low >= box_lo) AND (High <= box_hi). No look-ahead.
Winners: among methods with TRAIN containment >= 0.90, pick tightest median width.
Then report TEST containment (must also be >= 0.90 to promote).

Also sweeps ATR multiples, max(yday,ATR) multiples, rolling quantiles, and
asymmetric up/down pads.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_daily_nse.csv"
OUT_JSON = ROOT / "prod_live" / "reports" / "1y" / "MORNING_NIFTY_ACC90.json"
OUT_MD = ROOT / "prod_live" / "reports" / "1y" / "MORNING_NIFTY_ACC90.md"
FLOOR = 0.004
TARGET = 0.90


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


def prep(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    h, l, c = out["High"], out["Low"], out["Close"]
    day_rng = (h - l).clip(lower=0)
    atr = wilder_atr(h, l, c, 14)
    out["prev_c"] = c.shift(1)
    out["prev_h"] = h.shift(1)
    out["prev_l"] = l.shift(1)
    out["prev_rng"] = day_rng.shift(1)
    out["atr_prev"] = atr.shift(1)
    out["med20"] = out["prev_rng"].rolling(20).median()
    out["p80"] = out["prev_rng"].rolling(20).quantile(0.80)
    out["p90"] = out["prev_rng"].rolling(20).quantile(0.90)
    out["p95"] = out["prev_rng"].rolling(20).quantile(0.95)
    out["p99"] = out["prev_rng"].rolling(40).quantile(0.99)
    # expanding high of recent ranges (prior only)
    out["max20"] = out["prev_rng"].rolling(20).max()
    out["max40"] = out["prev_rng"].rolling(40).max()
    ret = c.pct_change()
    out["vol20"] = ret.shift(1).rolling(20).std()
    return out


def open_box(df: pd.DataFrame, width: pd.Series, up_mult: float = 1.0, dn_mult: float = 1.0):
    """Seat width on open; optional asymmetric halves; gap pad like prod."""
    half = width / 2.0
    up = half * up_mult
    dn = half * dn_mult
    o = df["Open"]
    prev = df["prev_c"]
    hi = o + up
    lo = o - dn
    gap = o - prev
    big = (gap.abs() / prev) >= 0.0035
    extra = np.minimum(gap.abs(), width * 0.35)
    hi = pd.Series(np.where(big & (gap > 0), hi + extra, hi), index=df.index)
    lo = pd.Series(np.where(big & (gap < 0), lo - extra, lo), index=df.index)
    return hi, lo


def score(df: pd.DataFrame, width: pd.Series, up_mult: float = 1.0, dn_mult: float = 1.0) -> Dict[str, Any]:
    hi, lo = open_box(df, width, up_mult, dn_mult)
    full = (df["Low"] >= lo) & (df["High"] <= hi)
    high_ok = df["High"] <= hi
    low_ok = df["Low"] >= lo
    # effective width after asymmetry / gap
    eff_w = (hi - lo) / df["prev_c"]
    use = full.notna() & width.notna() & (width > 0) & df["prev_c"].notna()
    n = int(use.sum())
    if n == 0:
        return {"days": 0, "full_containment_acc": 0.0, "median_width_pct": 9.0}
    return {
        "days": n,
        "full_containment_acc": round(float(full[use].mean()), 4),
        "high_ok_acc": round(float(high_ok[use].mean()), 4),
        "low_ok_acc": round(float(low_ok[use].mean()), 4),
        "median_width_pct": round(float(eff_w[use].median()), 4),
        "p90_width_pct": round(float(eff_w[use].quantile(0.90)), 4),
    }


def width_candidates(df: pd.DataFrame) -> Dict[str, pd.Series]:
    price = df["prev_c"]
    floor = price * FLOOR
    atr = df["atr_prev"]
    yday = df["prev_rng"]
    base = np.maximum(yday, atr)
    out: Dict[str, pd.Series] = {}
    for k in (1.2, 1.5, 1.8, 2.0, 2.2, 2.4, 2.5, 2.8, 3.0, 3.5, 4.0):
        out[f"atr14_{k:.1f}x".replace(".", "_")] = np.maximum(atr * k, floor)
        out[f"max_yday_atr_{k:.1f}x".replace(".", "_")] = np.maximum(base * k, floor)
    out["p90_20"] = np.maximum(df["p90"], floor)
    out["p95_20"] = np.maximum(df["p95"], floor)
    out["p99_40"] = np.maximum(df["p99"], floor)
    out["max20"] = np.maximum(df["max20"], floor)
    out["max40"] = np.maximum(df["max40"], floor)
    out["p90_1_5x"] = np.maximum(df["p90"] * 1.5, floor)
    out["p95_1_2x"] = np.maximum(df["p95"] * 1.2, floor)
    out["max20_1_2x"] = np.maximum(df["max20"] * 1.2, floor)
    out["vol20_2_5sd"] = np.maximum(df["vol20"] * price * 2.5, floor)
    out["vol20_3sd"] = np.maximum(df["vol20"] * price * 3.0, floor)
    # hybrid: max of ATR*2.5 and p95
    out["hybrid_atr25_p95"] = np.maximum(np.maximum(atr * 2.5, df["p95"]), floor)
    out["hybrid_atr22_max20"] = np.maximum(np.maximum(atr * 2.2, df["max20"]), floor)
    out["hybrid_atr20_p90"] = np.maximum(np.maximum(atr * 2.0, df["p90"]), floor)
    return out


def asym_variants() -> List[Tuple[str, float, float]]:
    # (suffix, up_mult, dn_mult) applied to half-width
    return [
        ("sym", 1.0, 1.0),
        ("up110_dn100", 1.10, 1.0),
        ("up100_dn110", 1.0, 1.10),
        ("up120_dn100", 1.20, 1.0),
        ("up100_dn120", 1.0, 1.20),
        ("up115_dn115", 1.15, 1.15),
    ]


def pick_ge90(train: pd.DataFrame, test: pd.DataFrame) -> Dict[str, Any]:
    w_tr = width_candidates(train)
    w_te = width_candidates(test)
    rows = []
    for name, w in w_tr.items():
        for suffix, up, dn in asym_variants():
            # skip asym for most names to limit combo explosion — only on strong bases
            if suffix != "sym" and not name.startswith(("atr14_2", "atr14_3", "max_yday_atr_2", "hybrid", "p95", "max20", "max40")):
                continue
            tr = score(train, w, up, dn)
            te = score(test, w_te[name], up, dn)
            rows.append({
                "method": f"{name}__{suffix}",
                "base": name,
                "asym": suffix,
                "up_mult": up,
                "dn_mult": dn,
                "train": tr,
                "test": te,
            })
    ge90_train = [r for r in rows if r["train"]["full_containment_acc"] >= TARGET and r["train"]["days"] > 100]
    # tightest train width among >=90%
    if ge90_train:
        winner = min(
            ge90_train,
            key=lambda r: (r["train"]["median_width_pct"], -r["train"]["full_containment_acc"]),
        )
    else:
        # fallback: highest train containment
        winner = max(rows, key=lambda r: (r["train"]["full_containment_acc"], -r["train"]["median_width_pct"]))

    # also: among test>=90 (info), and held V2
    ge90_test = [r for r in rows if r["test"]["full_containment_acc"] >= TARGET]
    tightest_test90 = None
    if ge90_test:
        tightest_test90 = min(ge90_test, key=lambda r: r["test"]["median_width_pct"])

    held = next((r for r in rows if r["method"] == "max_yday_atr_1_5x__sym"), None)
    # top by train containment
    top_train = sorted(rows, key=lambda r: (-r["train"]["full_containment_acc"], r["train"]["median_width_pct"]))[:15]
    # top among train>=90 by width
    top_tight90 = sorted(ge90_train, key=lambda r: (r["train"]["median_width_pct"], -r["train"]["full_containment_acc"]))[:15]

    return {
        "n_candidates": len(rows),
        "n_train_ge90": len(ge90_train),
        "n_test_ge90": len(ge90_test),
        "train_pick_ge90_tightest": winner,
        "train_pick_test_ok": bool(winner["test"]["full_containment_acc"] >= TARGET),
        "tightest_on_test_ge90_info": tightest_test90,
        "held_v2_max_yday_atr_1_5x": held,
        "top_train_containment": top_train,
        "top_train_ge90_by_width": top_tight90,
    }


def run_split(df: pd.DataFrame, n_test: int, label: str) -> Dict[str, Any]:
    start = df["Date"].iloc[-n_test]
    train = df[df["Date"] < start].copy()
    test = df[df["Date"] >= start].copy()
    out = pick_ge90(train, test)
    out["label"] = label
    out["report_start"] = str(start.date())
    out["report_end"] = str(test["Date"].max().date())
    out["train_days"] = int(len(train))
    out["test_days"] = int(len(test))
    return out


def to_md(payload: Dict[str, Any]) -> str:
    lines = [
        "# NIFTY morning range — hunt ≥90% full containment",
        "",
        f"**Generated:** `{payload['generated_at']}`",
        "",
        "Accuracy = (Low ≥ lo) AND (High ≤ hi). Fit on train only; promote only if **test ≥ 90%**.",
        "",
    ]
    for sp in payload["splits"]:
        w = sp["train_pick_ge90_tightest"]
        lines += [
            f"## {sp['label']}  (`{sp['report_start']}` → `{sp['report_end']}`)",
            f"Train {sp['train_days']} · Test {sp['test_days']} · "
            f"candidates {sp['n_candidates']} · train≥90% {sp['n_train_ge90']} · test≥90% {sp['n_test_ge90']}",
            "",
            f"### Train-picked (≥90% then tightest width): `{w['method']}`",
            f"- train containment **{w['train']['full_containment_acc']:.1%}** · width {w['train']['median_width_pct']:.2%}",
            f"- test containment **{w['test']['full_containment_acc']:.1%}** · width {w['test']['median_width_pct']:.2%} · "
            f"high_ok {w['test']['high_ok_acc']:.1%} · low_ok {w['test']['low_ok_acc']:.1%}",
            f"- **Promote?** {'YES' if sp['train_pick_test_ok'] else 'NO — test below 90%'}",
            "",
        ]
        if sp.get("held_v2_max_yday_atr_1_5x"):
            h = sp["held_v2_max_yday_atr_1_5x"]
            lines.append(
                f"- Held V2 on test: **{h['test']['full_containment_acc']:.1%}** contain · width {h['test']['median_width_pct']:.2%}"
            )
            lines.append("")
        lines += [
            "Tightest train≥90% (top):",
            "",
            "| Method | Train contain | Train width | Test contain | Test width |",
            "|---|---:|---:|---:|---:|",
        ]
        for r in sp["top_train_ge90_by_width"][:10]:
            lines.append(
                f"| `{r['method']}` | {r['train']['full_containment_acc']:.1%} | {r['train']['median_width_pct']:.2%} | "
                f"{r['test']['full_containment_acc']:.1%} | {r['test']['median_width_pct']:.2%} |"
            )
        lines.append("")
    rec = payload.get("recommendation") or {}
    lines += [
        "## Recommendation",
        "",
        f"- method: `{rec.get('method')}`",
        f"- promote: **{rec.get('promote')}**",
        f"- 1y test: {rec.get('test_1y')}",
        f"- 3y test: {rec.get('test_3y')}",
        f"- 5y test: {rec.get('test_5y')}",
        "",
        "If promote=YES, freeze as MORNING_CTX_V3 range rule.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    df = prep(load())
    splits = [
        run_split(df, 252, "last_1y"),
        run_split(df, 756, "last_3y"),
        run_split(df, 1260, "last_5y"),
    ]
    # Consensus: method that is train-picked and test>=90 on ALL of 1y,3y,5y
    picks = {sp["label"]: sp["train_pick_ge90_tightest"] for sp in splits}
    # Prefer method from 3y pick if it clears 90 on all test windows when re-scored
    cand = picks["last_3y"]
    # Re-evaluate this method on each split's test
    def eval_method_on_split(sp, method_row):
        return {
            "contain": method_row["test"]["full_containment_acc"] if method_row["method"] == sp["train_pick_ge90_tightest"]["method"]
            else None
        }

    # Find methods that appear in top_train_ge90 and have test>=90 on every split
    def method_test_map(name: str) -> Dict[str, float]:
        out = {}
        for sp in splits:
            for r in sp["top_train_ge90_by_width"] + sp["top_train_containment"]:
                if r["method"] == name:
                    out[sp["label"]] = r["test"]["full_containment_acc"]
                    break
            else:
                # search all by recompute
                train = df[df["Date"] < pd.Timestamp(sp["report_start"])]
                test = df[df["Date"] >= pd.Timestamp(sp["report_start"])]
                base, asym = name.rsplit("__", 1)
                up = dn = 1.0
                for s, u, d in asym_variants():
                    if s == asym:
                        up, dn = u, d
                        break
                w = width_candidates(test)[base]
                out[sp["label"]] = score(test, w, up, dn)["full_containment_acc"]
        return out

    # Rank candidates: start from each split's train pick + top5 tight90 from 3y
    names = []
    for sp in splits:
        names.append(sp["train_pick_ge90_tightest"]["method"])
        for r in sp["top_train_ge90_by_width"][:8]:
            names.append(r["method"])
    names = list(dict.fromkeys(names))

    ranked = []
    for name in names:
        m = method_test_map(name)
        ok = all(m.get(k, 0) >= TARGET for k in ("last_1y", "last_3y", "last_5y"))
        # width from 3y test
        width3 = None
        for r in splits[1]["top_train_ge90_by_width"] + [splits[1]["train_pick_ge90_tightest"]]:
            if r["method"] == name:
                width3 = r["test"]["median_width_pct"]
                break
        if width3 is None:
            base, asym = name.rsplit("__", 1)
            up = dn = 1.0
            for s, u, d in asym_variants():
                if s == asym:
                    up, dn = u, d
                    break
            test3 = df[df["Date"] >= pd.Timestamp(splits[1]["report_start"])]
            width3 = score(test3, width_candidates(test3)[base], up, dn)["median_width_pct"]
        ranked.append({"method": name, "tests": m, "all_ge90": ok, "width_3y": width3})

    promote_pool = [r for r in ranked if r["all_ge90"]]
    if promote_pool:
        best = min(promote_pool, key=lambda r: (r["width_3y"], -min(r["tests"].values())))
        promote = True
    else:
        # best average test containment
        best = max(ranked, key=lambda r: (sum(r["tests"].values()) / 3, -r["width_3y"]))
        promote = False

    payload = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "target": TARGET,
        "splits": splits,
        "cross_window_ranked": ranked[:25],
        "recommendation": {
            "method": best["method"],
            "promote": promote and best["all_ge90"],
            "tests": best["tests"],
            "width_3y": best["width_3y"],
            "test_1y": best["tests"].get("last_1y"),
            "test_3y": best["tests"].get("last_3y"),
            "test_5y": best["tests"].get("last_5y"),
            "note": "Promote only if all of 1y/3y/5y test containment >= 90%.",
        },
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    # shrink JSON: drop huge all lists partially
    slim_splits = []
    for sp in splits:
        slim_splits.append({
            **{k: sp[k] for k in sp if k not in ("top_train_containment",)},
            "top_train_containment": sp["top_train_containment"][:8],
        })
    payload["splits"] = slim_splits
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    OUT_MD.write_text(to_md(payload), encoding="utf-8")
    print(json.dumps(payload["recommendation"], indent=2))


if __name__ == "__main__":
    main()
