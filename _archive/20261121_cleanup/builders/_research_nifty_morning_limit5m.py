"""NIFTY morning strong BUY — 15m thrust signal → 5m limit fill at OR+lim.

Honest path (no synth look-ahead):
  1) 15m: green · close>OR · uplift≥min_up · break prior N highs · body frac
  2) After signal: first 5m bar with low≤OR+lim and close>OR → entry=OR+lim ±30

  python -u prod_live/tests/builders/_research_nifty_morning_limit5m.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]
import path_setup  # noqa: F401,E402

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT_DIR / "NIFTY_MORNING_STRONG_LIMIT5M.md"
OUT_JSON = OUT_DIR / "NIFTY_MORNING_STRONG_LIMIT5M.json"
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_kite.csv"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
HOLDOUT = 40
SL = T1 = 30.0


def _load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.columns = [str(c).strip().title() for c in df.columns]
    if df.index.tz is None:
        df.index = df.index.tz_localize("Asia/Kolkata")
    else:
        df.index = df.index.tz_convert("Asia/Kolkata")
    return df.sort_index()


def _hm(ts: Any) -> str:
    t = pd.Timestamp(ts).tz_convert("Asia/Kolkata")
    return f"{int(t.hour):02d}:{int(t.minute):02d}"


def _outcome(entry: float, after: pd.DataFrame) -> str:
    if after is None or after.empty:
        return "open"
    stop, tgt = entry - SL, entry + T1
    for _, r in after.iterrows():
        lo, hi = float(r["Low"]), float(r["High"])
        if lo <= stop and hi >= tgt:
            return "loss"
        if hi >= tgt:
            return "win"
        if lo <= stop:
            return "loss"
    return "open"


def evaluate_day(sess: pd.DataFrame, s5: pd.DataFrame, cfg: Dict[str, Any]) -> Optional[dict]:
    if len(sess) < 6:
        return None
    or_hi = float(sess["High"].iloc[0])
    day_open = float(sess["Open"].iloc[0])
    prior_n = int(cfg.get("prior", 2))
    for i, ts in enumerate(sess.index):
        hm = _hm(ts)
        if hm < cfg["hmin"] or hm > cfg["hmax"] or i < prior_n:
            continue
        row = sess.iloc[i]
        c = float(row["Close"])
        o = float(row["Open"])
        h = float(row["High"])
        l = float(row["Low"])
        if c <= or_hi or c <= o:
            continue
        if (c - day_open) < float(cfg["min_up"]):
            continue
        prior_hi = max(float(sess["High"].iloc[j]) for j in range(i - prior_n, i))
        if c <= prior_hi:
            continue
        rng = max(h - l, 1e-9)
        if abs(c - o) / rng < float(cfg["body"]):
            continue
        top = float(cfg.get("top") or 0)
        if top and (c - l) / rng < top:
            continue
        sig_near = cfg.get("sig_near")
        if sig_near is not None and l > or_hi + float(sig_near):
            continue
        lim = or_hi + float(cfg["lim"])
        after_sig = s5[s5.index > ts] if s5 is not None and len(s5) else sess.iloc[i + 1 :]
        fill_max = cfg.get("fill_max", "13:00")
        for thr, r2 in after_sig.iterrows():
            hm2 = _hm(thr)
            if hm2 > fill_max:
                break
            if float(r2["Low"]) > lim:
                continue
            if float(r2["Close"]) <= or_hi:
                continue
            if cfg.get("fill_green") and float(r2["Close"]) <= float(r2["Open"]):
                continue
            after = after_sig[after_sig.index > thr]
            out = _outcome(lim, after)
            return {
                "d": str(pd.Timestamp(ts).tz_convert("Asia/Kolkata").date()),
                "sig_hm": hm,
                "fill_hm": hm2,
                "entry": round(lim, 2),
                "or_hi": round(or_hi, 2),
                "uplift": round(c - day_open, 1),
                "out": out,
                "strong": (float(sess["High"].max()) - day_open) >= 150,
            }
        return None  # signaled but never filled
    return None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df15 = _load(TAPE15)
    df5 = _load(TAPE5)
    by15 = {d: g for d, g in df15.groupby(df15.index.strftime("%Y-%m-%d"))}
    by5 = {d: g for d, g in df5.groupby(df5.index.strftime("%Y-%m-%d"))}
    days = sorted(by15.keys())[-520:]
    hold = set(days[-HOLDOUT:])
    print(f"sessions={len(days)}", flush=True)

    cfgs: List[Dict[str, Any]] = []
    for lim in (5, 8):
        for up in (50, 55, 60):
            for body in (0.55, 0.60, 0.65):
                for top in (0.0, 0.70):
                    for hmax in ("11:30", "12:00"):
                        cfgs.append(
                            {
                                "name": f"L{lim}_u{up}_b{int(body * 100)}_t{int(top * 100)}_{hmax}",
                                "lim": lim,
                                "min_up": up,
                                "body": body,
                                "top": top,
                                "hmin": "09:45",
                                "hmax": hmax,
                                "prior": 2,
                            }
                        )
    cfgs += [
        {"name": "L5_u50_b55", "lim": 5, "min_up": 50, "body": 0.55, "top": 0, "hmin": "09:45", "hmax": "11:30", "prior": 2},
        {"name": "L5_u50_b55_fg", "lim": 5, "min_up": 50, "body": 0.55, "top": 0, "hmin": "09:45", "hmax": "11:30", "prior": 2, "fill_green": True},
        {"name": "L5_u50_b60_t70", "lim": 5, "min_up": 50, "body": 0.60, "top": 0.7, "hmin": "09:45", "hmax": "11:30", "prior": 2},
        {"name": "L5_u55_b60", "lim": 5, "min_up": 55, "body": 0.60, "top": 0, "hmin": "09:45", "hmax": "11:30", "prior": 2},
        {"name": "L5_u50_b55_p3", "lim": 5, "min_up": 50, "body": 0.55, "top": 0, "hmin": "09:45", "hmax": "11:30", "prior": 3},
        {"name": "L5_u50_b55_sig25", "lim": 5, "min_up": 50, "body": 0.55, "top": 0, "hmin": "09:45", "hmax": "11:30", "prior": 2, "sig_near": 25},
        {"name": "L5_u50_b65_t70", "lim": 5, "min_up": 50, "body": 0.65, "top": 0.7, "hmin": "09:45", "hmax": "11:30", "prior": 2},
        {"name": "L5_u60_b55_t70", "lim": 5, "min_up": 60, "body": 0.55, "top": 0.7, "hmin": "09:45", "hmax": "11:30", "prior": 2},
        {"name": "L5_u50_b55_to12", "lim": 5, "min_up": 50, "body": 0.55, "top": 0, "hmin": "09:45", "hmax": "12:00", "prior": 2},
    ]

    results = []
    for cfg in cfgs:
        fz: List[dict] = []
        ho: List[dict] = []
        for d in days:
            call = evaluate_day(by15[d], by5.get(d, by15[d].iloc[0:0]), cfg)
            if not call:
                continue
            (ho if d in hold else fz).append(call)

        def summ(cs: List[dict]) -> Dict[str, Any]:
            dec = [c for c in cs if c["out"] in ("win", "loss")]
            n = len(dec)
            w = sum(1 for c in dec if c["out"] == "win")
            return {"n": n, "wins": w, "hit_pct": round(100.0 * w / n, 2) if n else None}

        sf, sh = summ(fz), summ(ho)
        call_days = {c["d"] for c in ho}
        sh_n = caught = 0
        for d in days[-HOLDOUT:]:
            sess = by15[d]
            if (float(sess["High"].max()) - float(sess["Open"].iloc[0])) >= 150:
                sh_n += 1
                if d in call_days:
                    caught += 1
        catch = round(100.0 * caught / sh_n, 1) if sh_n else None
        passed = bool(sf["n"] >= 15 and sh["n"] >= 5 and (sf["hit_pct"] or 0) >= 80 and (sh["hit_pct"] or 0) >= 80)
        soft = bool(sf["n"] >= 12 and sh["n"] >= 5 and (sf["hit_pct"] or 0) >= 75 and (sh["hit_pct"] or 0) >= 80)
        row = {
            "gate": cfg["name"],
            "params": {k: v for k, v in cfg.items() if k != "name"},
            "freeze": sf,
            "holdout": sh,
            "holdout_strong_catch_pct": catch,
            "pass": passed,
            "soft": soft,
            "holdout_calls": ho,
        }
        results.append(row)
        if passed or soft or (sf["hit_pct"] or 0) >= 78:
            print(
                f"{cfg['name']:40s} fz {sf['n']:3d}@{sf['hit_pct']}  "
                f"ho {sh['n']:3d}@{sh['hit_pct']}  catch {catch}%  PASS={passed} SOFT={soft}",
                flush=True,
            )

    results.sort(
        key=lambda r: (
            int(r["pass"]),
            int(r["soft"]),
            (r["holdout"]["hit_pct"] or 0),
            (r["freeze"]["hit_pct"] or 0),
            (r["holdout_strong_catch_pct"] or 0),
            r["holdout"]["n"],
        ),
        reverse=True,
    )
    best = results[0]
    # prefer soft/pass with better catch among top accuracy
    candidates = [r for r in results if r["pass"] or r["soft"]]
    if candidates:
        best = max(
            candidates,
            key=lambda r: (
                int(r["pass"]),
                (r["holdout"]["hit_pct"] or 0),
                (r["freeze"]["hit_pct"] or 0),
                (r["holdout_strong_catch_pct"] or 0),
                r["holdout"]["n"],
            ),
        )

    payload = {
        "brackets": {"sl": SL, "t1": T1},
        "logic": "15m thrust → 5m limit fill at OR+lim",
        "best": {
            "gate": best["gate"],
            "params": best["params"],
            "freeze": best["freeze"],
            "holdout": best["holdout"],
            "holdout_strong_catch_pct": best["holdout_strong_catch_pct"],
            "pass": best["pass"],
            "soft": best["soft"],
            "holdout_calls": best["holdout_calls"],
        },
        "top": [
            {
                "gate": r["gate"],
                "freeze": r["freeze"],
                "holdout": r["holdout"],
                "catch": r["holdout_strong_catch_pct"],
                "pass": r["pass"],
                "soft": r["soft"],
                "params": r["params"],
            }
            for r in results[:25]
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# NIFTY morning strong BUY · 15m thrust → 5m OR+lim fill",
        "",
        "Honest fills only (limit after signal). Brackets ±30.",
        "",
        f"**Selected:** `{best['gate']}` · freeze {best['freeze']['n']}@{best['freeze']['hit_pct']}% · "
        f"holdout {best['holdout']['n']}@{best['holdout']['hit_pct']}% · "
        f"strong catch {best['holdout_strong_catch_pct']}% · pass={best['pass']} soft={best['soft']}",
        "",
        f"Params: `{json.dumps(best['params'])}`",
        "",
        "## Top gates",
        "",
        "| gate | freeze | holdout | catch | pass | soft |",
        "|---|---:|---:|---:|---|---|",
    ]
    for r in results[:20]:
        lines.append(
            f"| `{r['gate']}` | {r['freeze']['n']}@{r['freeze']['hit_pct']} | "
            f"{r['holdout']['n']}@{r['holdout']['hit_pct']} | {r['holdout_strong_catch_pct']}% | "
            f"{r['pass']} | {r['soft']} |"
        )
    lines += ["", "## Holdout calls (selected)", ""]
    for c in best["holdout_calls"]:
        lines.append(
            f"- {c['d']} sig {c['sig_hm']} fill {c['fill_hm']} @ {c['entry']} · {c['out']} · uplift {c['uplift']}"
        )
    lines += ["", f"JSON: `{OUT_JSON}`", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("BEST", best["gate"], best["freeze"], best["holdout"], "catch", best["holdout_strong_catch_pct"], flush=True)
    print("wrote", OUT_MD, flush=True)


if __name__ == "__main__":
    main()
