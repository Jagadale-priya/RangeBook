"""Find bias threshold that clears 1y/3y/5y AND walk-forward min."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from morning_deep_fusion_validate import load_nifty, prep, fusion_features, score_spoken, walk_forward  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y" / "MORNING_BIAS_STABILITY_SCAN.md"


def main():
    d = fusion_features(prep(load_nifty()).dropna(subset=["spx_ret", "prev_c"]).reset_index(drop=True))
    rows = []
    for th in np.arange(4.0, 12.5, 0.5):
        def rule_fn(sub, th=th):
            s = fusion_features(sub)["fuse_us_asia"]
            return {
                "r": pd.Series(
                    np.where(s >= th, "BULLISH", np.where(s <= -th, "BEARISH", "NEUTRAL")),
                    index=sub.index,
                )
            }

        tests = {}
        pred = rule_fn(d)["r"]
        for lab, n in (("1y", 252), ("3y", 756), ("5y", 1260)):
            tests[lab] = score_spoken(pred.iloc[-n:], d.iloc[-n:]["dir_true"], ("BULLISH", "BEARISH"))
        folds = walk_forward(d, "r", rule_fn, "dir_true", ("BULLISH", "BEARISH"))
        accs = [f["spoken_acc"] for f in folds if f.get("spoken_acc") is not None and f["days_spoken"] >= 5]
        win70 = all((tests[k].get("spoken_acc") or 0) >= 0.70 and tests[k]["days_spoken"] >= 10 for k in tests)
        win65 = all((tests[k].get("spoken_acc") or 0) >= 0.65 and tests[k]["days_spoken"] >= 10 for k in tests)
        wmin = min(accs) if accs else None
        wmean = float(np.mean(accs)) if accs else None
        rows.append(
            {
                "th": th,
                "win70": win70,
                "win65": win65,
                "walk_min": round(wmin, 4) if wmin is not None else None,
                "walk_mean": round(wmean, 4) if wmean is not None else None,
                "1y": tests["1y"],
                "3y": tests["3y"],
                "5y": tests["5y"],
                "stable70": bool(win70 and wmin is not None and wmin >= 0.67 and wmean >= 0.70),
                "stable65": bool(win65 and wmin is not None and wmin >= 0.60 and wmean >= 0.65),
            }
        )

    # also try agree_spx variants
    extra = []
    for th in (0.8, 1.0, 1.2, 1.5, 2.0):
        up = d["us_asia_agree"] & (d["spx_ret"] >= th)
        dn = d["us_asia_agree"] & (d["spx_ret"] <= -th)
        pred = pd.Series(np.where(up, "BULLISH", np.where(dn, "BEARISH", "NEUTRAL")), index=d.index)

        def rule_fn(sub, th=th):
            x = fusion_features(sub)
            up = x["us_asia_agree"] & (x["spx_ret"] >= th)
            dn = x["us_asia_agree"] & (x["spx_ret"] <= -th)
            return {
                "r": pd.Series(np.where(up, "BULLISH", np.where(dn, "BEARISH", "NEUTRAL")), index=sub.index)
            }

        tests = {
            lab: score_spoken(pred.iloc[-n:], d.iloc[-n:]["dir_true"], ("BULLISH", "BEARISH"))
            for lab, n in (("1y", 252), ("3y", 756), ("5y", 1260))
        }
        folds = walk_forward(d, "r", rule_fn, "dir_true", ("BULLISH", "BEARISH"))
        accs = [f["spoken_acc"] for f in folds if f.get("spoken_acc") is not None and f["days_spoken"] >= 5]
        wmin = min(accs) if accs else None
        wmean = float(np.mean(accs)) if accs else None
        win70 = all((tests[k].get("spoken_acc") or 0) >= 0.70 and tests[k]["days_spoken"] >= 8 for k in tests)
        extra.append(
            {
                "rule": f"agree_spx_{th}",
                "win70": win70,
                "walk_min": round(wmin, 4) if wmin is not None else None,
                "walk_mean": round(wmean, 4) if wmean is not None else None,
                "1y": tests["1y"],
                "3y": tests["3y"],
                "5y": tests["5y"],
                "stable70": bool(win70 and wmin is not None and wmin >= 0.67 and wmean >= 0.70),
            }
        )

    lines = ["# Bias stability scan", "", "## fuse_us_asia thresholds", "", "| th | 1y | 3y | 5y | walk_min | walk_mean | win70 | stable70 | stable65 |", "|---|---:|---:|---:|---:|---:|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r['th']} | {r['1y'].get('spoken_acc')} n={r['1y']['days_spoken']} | "
            f"{r['3y'].get('spoken_acc')} n={r['3y']['days_spoken']} | "
            f"{r['5y'].get('spoken_acc')} n={r['5y']['days_spoken']} | "
            f"{r['walk_min']} | {r['walk_mean']} | {r['win70']} | {r['stable70']} | {r['stable65']} |"
        )
    lines += ["", "## agree_spx", "", "| rule | 1y | 3y | 5y | walk_min | walk_mean | win70 | stable70 |", "|---|---:|---:|---:|---:|---:|---|---|"]
    for r in extra:
        lines.append(
            f"| {r['rule']} | {r['1y'].get('spoken_acc')} n={r['1y']['days_spoken']} | "
            f"{r['3y'].get('spoken_acc')} n={r['3y']['days_spoken']} | "
            f"{r['5y'].get('spoken_acc')} n={r['5y']['days_spoken']} | "
            f"{r['walk_min']} | {r['walk_mean']} | {r['win70']} | {r['stable70']} |"
        )
    best70 = [r for r in rows if r["stable70"]] + [r for r in extra if r["stable70"]]
    best65 = [r for r in rows if r["stable65"]]
    lines += ["", f"**stable70 count:** {len(best70)}", f"**stable65 count:** {len(best65)}", ""]
    if best70:
        lines.append(f"Best stable70: {best70}")
    elif best65:
        # pick highest walk_min among stable65
        b = max(best65, key=lambda r: (r["walk_min"] or 0, r["3y"].get("spoken_acc") or 0))
        lines.append(f"Best stable65 fuse th={b['th']} walk_min={b['walk_min']} 3y={b['3y']}")
    else:
        # best compromise: max walk_min among win65
        pool = [r for r in rows if r["win65"]]
        if pool:
            b = max(pool, key=lambda r: (r["walk_min"] or 0, r["walk_mean"] or 0))
            lines.append(f"Compromise win65 best walk: th={b['th']} walk_min={b['walk_min']} walk_mean={b['walk_mean']}")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[-20:]))


if __name__ == "__main__":
    main()
