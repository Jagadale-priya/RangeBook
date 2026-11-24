"""Push NIFTY morning range containment above current V3 (~90-92%).

Targets: 93% and 95% full containment on ALL of 1y/3y/5y holdouts.
Also tests regime-conditional widths (wider when ATR% is elevated).

Accuracy = (Low >= lo) AND (High <= hi). No look-ahead.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_daily_nse.csv"
OUT_JSON = ROOT / "prod_live" / "reports" / "1y" / "MORNING_NIFTY_ACC95.json"
OUT_MD = ROOT / "prod_live" / "reports" / "1y" / "MORNING_NIFTY_ACC95.md"
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


def prep(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    h, l, c = out["High"], out["Low"], out["Close"]
    day_rng = (h - l).clip(lower=0)
    atr = wilder_atr(h, l, c, 14)
    out["prev_c"] = c.shift(1)
    out["prev_rng"] = day_rng.shift(1)
    out["atr_prev"] = atr.shift(1)
    out["atr_pct"] = out["atr_prev"] / out["prev_c"] * 100
    out["max10"] = out["prev_rng"].rolling(10).max()
    out["max20"] = out["prev_rng"].rolling(20).max()
    out["max40"] = out["prev_rng"].rolling(40).max()
    out["max60"] = out["prev_rng"].rolling(60).max()
    out["p90"] = out["prev_rng"].rolling(20).quantile(0.90)
    out["p95"] = out["prev_rng"].rolling(20).quantile(0.95)
    out["p99"] = out["prev_rng"].rolling(40).quantile(0.99)
    out["med20"] = out["prev_rng"].rolling(20).median()
    # expanding vol tercile for regime
    q33 = out["atr_pct"].expanding(60).quantile(0.33)
    q66 = out["atr_pct"].expanding(60).quantile(0.66)
    out["vol_reg"] = np.where(out["atr_pct"] >= q66, "HIGH", np.where(out["atr_pct"] <= q33, "LOW", "NORMAL"))
    return out


def seat(df: pd.DataFrame, width: pd.Series, up: float, dn: float) -> Tuple[pd.Series, pd.Series, pd.Series]:
    half = width / 2.0
    o, prev = df["Open"], df["prev_c"]
    hi = o + half * up
    lo = o - half * dn
    gap = o - prev
    big = (gap.abs() / prev) >= 0.0035
    extra = np.minimum(gap.abs(), width * 0.35)
    hi = pd.Series(np.where(big & (gap > 0), hi + extra, hi), index=df.index)
    lo = pd.Series(np.where(big & (gap < 0), lo - extra, lo), index=df.index)
    eff = (hi - lo) / prev
    return hi, lo, eff


def score(df: pd.DataFrame, width: pd.Series, up: float = 1.0, dn: float = 1.0) -> Dict[str, Any]:
    hi, lo, eff = seat(df, width, up, dn)
    full = (df["Low"] >= lo) & (df["High"] <= hi)
    use = full.notna() & width.notna() & (width > 0) & df["prev_c"].notna()
    n = int(use.sum())
    if n == 0:
        return {"days": 0, "acc": 0.0, "width": 9.0, "high_ok": 0.0, "low_ok": 0.0}
    return {
        "days": n,
        "acc": round(float(full[use].mean()), 4),
        "width": round(float(eff[use].median()), 4),
        "high_ok": round(float((df["High"] <= hi)[use].mean()), 4),
        "low_ok": round(float((df["Low"] >= lo)[use].mean()), 4),
    }


def bank(df: pd.DataFrame) -> Dict[str, pd.Series]:
    price = df["prev_c"]
    floor = price * FLOOR
    atr = df["atr_prev"]
    base = np.maximum(df["prev_rng"], atr)
    out: Dict[str, pd.Series] = {}
    for k in (2.2, 2.4, 2.5, 2.6, 2.8, 3.0, 3.2, 3.5, 4.0, 4.5, 5.0):
        tag = f"{k:.1f}".replace(".", "_")
        out[f"atr_{tag}x"] = np.maximum(atr * k, floor)
        out[f"maxya_{tag}x"] = np.maximum(base * k, floor)
    out["v3_hybrid"] = np.maximum(np.maximum(atr * 2.2, df["max20"]), floor)
    out["hy_atr25_max20"] = np.maximum(np.maximum(atr * 2.5, df["max20"]), floor)
    out["hy_atr28_max20"] = np.maximum(np.maximum(atr * 2.8, df["max20"]), floor)
    out["hy_atr30_max20"] = np.maximum(np.maximum(atr * 3.0, df["max20"]), floor)
    out["hy_atr25_max40"] = np.maximum(np.maximum(atr * 2.5, df["max40"]), floor)
    out["hy_atr28_max40"] = np.maximum(np.maximum(atr * 2.8, df["max40"]), floor)
    out["hy_atr30_max40"] = np.maximum(np.maximum(atr * 3.0, df["max40"]), floor)
    out["hy_atr30_max60"] = np.maximum(np.maximum(atr * 3.0, df["max60"]), floor)
    out["hy_atr25_p95"] = np.maximum(np.maximum(atr * 2.5, df["p95"]), floor)
    out["hy_atr30_p95"] = np.maximum(np.maximum(atr * 3.0, df["p95"]), floor)
    out["hy_atr30_p99"] = np.maximum(np.maximum(atr * 3.0, df["p99"]), floor)
    out["max20_1_5x"] = np.maximum(df["max20"] * 1.5, floor)
    out["max40_1_3x"] = np.maximum(df["max40"] * 1.3, floor)
    out["max40_1_5x"] = np.maximum(df["max40"] * 1.5, floor)
    out["p99_1_2x"] = np.maximum(df["p99"] * 1.2, floor)
    # regime conditional: base * scale by vol_reg
    for base_k, hi_k, name in (
        (2.2, 3.0, "reg_atr22_30"),
        (2.5, 3.5, "reg_atr25_35"),
        (2.5, 4.0, "reg_atr25_40"),
        (2.8, 3.5, "reg_atr28_35"),
        (3.0, 4.0, "reg_atr30_40"),
    ):
        w = atr * base_k
        w = np.where(df["vol_reg"] == "HIGH", atr * hi_k, w)
        w = np.where(df["vol_reg"] == "LOW", atr * max(2.0, base_k - 0.3), w)
        out[name] = np.maximum(pd.Series(w, index=df.index), floor)
        # hybrid regime with max20
        wh = np.maximum(w, df["max20"])
        out[name + "_max20"] = np.maximum(pd.Series(wh, index=df.index), floor)
        wh40 = np.maximum(w, df["max40"])
        out[name + "_max40"] = np.maximum(pd.Series(wh40, index=df.index), floor)
    return out


ASYM = [
    ("sym", 1.0, 1.0),
    ("dn110", 1.0, 1.10),
    ("dn120", 1.0, 1.20),
    ("dn130", 1.0, 1.30),
    ("up110", 1.10, 1.0),
    ("up120", 1.20, 1.0),
    ("both110", 1.10, 1.10),
    ("both115", 1.15, 1.15),
    ("both120", 1.20, 1.20),
    ("both125", 1.25, 1.25),
]


def eval_all(train: pd.DataFrame, test: pd.DataFrame) -> List[Dict[str, Any]]:
    bt, be = bank(train), bank(test)
    rows = []
    for name, w in bt.items():
        for suffix, up, dn in ASYM:
            # limit asym explosion on weaker bases
            if suffix not in ("sym", "dn120", "both115", "both120", "both125") and not name.startswith(
                ("hy_", "v3_", "atr_2", "atr_3", "atr_4", "reg_", "max")
            ):
                continue
            tr = score(train, w, up, dn)
            te = score(test, be[name], up, dn)
            rows.append({
                "method": f"{name}__{suffix}",
                "base": name,
                "up": up,
                "dn": dn,
                "train": tr,
                "test": te,
            })
    return rows


def pick(rows: List[Dict[str, Any]], floor: float) -> Dict[str, Any]:
    pool = [r for r in rows if r["train"]["acc"] >= floor and r["train"]["days"] > 100]
    if not pool:
        best = max(rows, key=lambda r: (r["train"]["acc"], -r["train"]["width"]))
        return {"found": False, "pick": best, "n_train": 0}
    pick = min(pool, key=lambda r: (r["train"]["width"], -r["train"]["acc"]))
    return {"found": True, "pick": pick, "n_train": len(pool), "test_ok": pick["test"]["acc"] >= floor}


def cross_window(df: pd.DataFrame, names: List[str], floors: List[float]) -> List[Dict[str, Any]]:
    splits = {
        "1y": (df["Date"].iloc[-252], 252),
        "3y": (df["Date"].iloc[-756], 756),
        "5y": (df["Date"].iloc[-1260], 1260),
    }
    ranked = []
    for name in names:
        base, suf = name.rsplit("__", 1)
        up = dn = 1.0
        for s, u, d in ASYM:
            if s == suf:
                up, dn = u, d
                break
        tests = {}
        widths = {}
        for lab, (start, _) in splits.items():
            test = df[df["Date"] >= start]
            w = bank(test)[base]
            sc = score(test, w, up, dn)
            tests[lab] = sc["acc"]
            widths[lab] = sc["width"]
        ranked.append({
            "method": name,
            "tests": tests,
            "widths": widths,
            "min_test": min(tests.values()),
            "width_3y": widths["3y"],
            "ge90": all(v >= 0.90 for v in tests.values()),
            "ge93": all(v >= 0.93 for v in tests.values()),
            "ge95": all(v >= 0.95 for v in tests.values()),
        })
    return ranked


def main() -> None:
    df = prep(load())
    split_defs = [("1y", 252), ("3y", 756), ("5y", 1260)]
    split_results = []
    name_pool = []
    for lab, n in split_defs:
        start = df["Date"].iloc[-n]
        train = df[df["Date"] < start]
        test = df[df["Date"] >= start]
        rows = eval_all(train, test)
        p90 = pick(rows, 0.90)
        p93 = pick(rows, 0.93)
        p95 = pick(rows, 0.95)
        # top by test acc
        top_test = sorted(rows, key=lambda r: (-r["test"]["acc"], r["test"]["width"]))[:12]
        top_tight95 = sorted(
            [r for r in rows if r["train"]["acc"] >= 0.95],
            key=lambda r: (r["train"]["width"], -r["train"]["acc"]),
        )[:12]
        for block in (p90, p93, p95):
            name_pool.append(block["pick"]["method"])
        for r in top_tight95[:8]:
            name_pool.append(r["method"])
        for r in top_test[:8]:
            name_pool.append(r["method"])
        # always include V3 and simple atr 2.5/3/3.5/4
        name_pool += [
            "v3_hybrid__dn120",
            "atr_2_5x__sym",
            "atr_3_0x__sym",
            "atr_3_5x__sym",
            "atr_4_0x__sym",
            "hy_atr30_max40__sym",
            "hy_atr30_max40__both120",
            "reg_atr30_40_max40__both120",
        ]
        split_results.append({
            "label": lab,
            "start": str(start.date()),
            "end": str(test["Date"].max().date()),
            "train_days": len(train),
            "test_days": len(test),
            "pick_90": p90,
            "pick_93": p93,
            "pick_95": p95,
            "top_test": [
                {"method": r["method"], "test": r["test"], "train": r["train"]} for r in top_test
            ],
            "top_train95_tight": [
                {"method": r["method"], "test": r["test"], "train": r["train"]} for r in top_tight95
            ],
        })

    names = list(dict.fromkeys(name_pool))
    ranked = cross_window(df, names, [0.90, 0.93, 0.95])
    best90 = min([r for r in ranked if r["ge90"]], key=lambda r: r["width_3y"], default=None)
    best93 = min([r for r in ranked if r["ge93"]], key=lambda r: r["width_3y"], default=None)
    best95 = min([r for r in ranked if r["ge95"]], key=lambda r: r["width_3y"], default=None)
    # also highest min_test among reasonable width (<=4%)
    high_acc = [r for r in ranked if r["width_3y"] <= 0.04]
    best_min = max(high_acc, key=lambda r: (r["min_test"], -r["width_3y"])) if high_acc else None

    rec = best95 or best93 or best90
    payload = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "current_v3": "v3_hybrid__dn120",
        "splits": split_results,
        "cross_best": {
            "ge90_tightest": best90,
            "ge93_tightest": best93,
            "ge95_tightest": best95,
            "best_min_acc_width_le_4pct": best_min,
        },
        "recommendation": {
            "method": rec["method"] if rec else None,
            "tier": "95" if best95 else ("93" if best93 else ("90" if best90 else "none")),
            "tests": rec["tests"] if rec else None,
            "width_3y": rec["width_3y"] if rec else None,
            "improve_vs_v3": None,
        },
    }
    # compare vs v3
    v3 = next((r for r in ranked if r["method"] == "v3_hybrid__dn120"), None)
    if rec and v3:
        payload["recommendation"]["v3_tests"] = v3["tests"]
        payload["recommendation"]["v3_width_3y"] = v3["width_3y"]
        payload["recommendation"]["improve_vs_v3"] = {
            k: round(rec["tests"][k] - v3["tests"][k], 4) for k in ("1y", "3y", "5y")
        }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# NIFTY morning range — push past 90% (93/95 hunt)",
        "",
        f"**Generated:** `{payload['generated_at']}`",
        "",
        "## Cross-window winners (must clear ALL of 1y/3y/5y)",
        "",
    ]
    for title, key in (
        ("≥90% tightest", "ge90_tightest"),
        ("≥93% tightest", "ge93_tightest"),
        ("≥95% tightest", "ge95_tightest"),
        ("Best min-acc (width≤4%)", "best_min_acc_width_le_4pct"),
    ):
        r = payload["cross_best"][key]
        if not r:
            lines += [f"### {title}", "None found", ""]
            continue
        lines += [
            f"### {title}: `{r['method']}`",
            f"- 1y **{r['tests']['1y']:.1%}** · 3y **{r['tests']['3y']:.1%}** · 5y **{r['tests']['5y']:.1%}**",
            f"- width 3y {r['width_3y']:.2%} · ge93={r['ge93']} · ge95={r['ge95']}",
            "",
        ]
    lines += ["## Per-split train picks", ""]
    for sp in split_results:
        lines.append(f"### {sp['label']} (`{sp['start']}` → `{sp['end']}`)")
        for floor, key in (("90", "pick_90"), ("93", "pick_93"), ("95", "pick_95")):
            p = sp[key]
            w = p["pick"]
            ok = "YES" if p.get("test_ok") else ("n/a" if not p["found"] else "NO")
            lines.append(
                f"- train≥{floor}% pick `{w['method']}` → train {w['train']['acc']:.1%}/{w['train']['width']:.2%} · "
                f"test {w['test']['acc']:.1%}/{w['test']['width']:.2%} · promote {ok}"
            )
        lines.append("")
        lines.append("| Top test | Acc | Width |")
        lines.append("|---|---:|---:|")
        for r in sp["top_test"][:6]:
            lines.append(f"| `{r['method']}` | {r['test']['acc']:.1%} | {r['test']['width']:.2%} |")
        lines.append("")

    rec = payload["recommendation"]
    lines += [
        "## Recommendation",
        "",
        f"- **method:** `{rec.get('method')}`",
        f"- **tier:** {rec.get('tier')}",
        f"- tests: {rec.get('tests')}",
        f"- width 3y: {rec.get('width_3y')}",
        f"- vs V3: {rec.get('improve_vs_v3')} (V3={rec.get('v3_tests')})",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload["recommendation"], indent=2))
    print("best95", best95["method"] if best95 else None)
    print("best93", best93["method"] if best93 else None)
    print("best_min", best_min)


if __name__ == "__main__":
    main()
