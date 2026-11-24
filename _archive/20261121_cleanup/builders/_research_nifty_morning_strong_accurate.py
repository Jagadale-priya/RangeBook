"""Deep research: accurate NIFTY morning strong BUY (honest 15m→5m OR+lim fill).

Goal: find gates with freeze≥85% & holdout≥80% (or best soft ≥80/80) at ±30.
Research only — does not change live wire.

  python -u prod_live/tests/builders/_research_nifty_morning_strong_accurate.py
"""
from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]
import path_setup  # noqa: F401,E402

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT_DIR / "NIFTY_MORNING_STRONG_ACCURATE.md"
OUT_JSON = OUT_DIR / "NIFTY_MORNING_STRONG_ACCURATE.json"
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_kite.csv"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
HOLDOUT = 40
SL = T1 = 30.0
MIN_FZ_N = 15
MIN_HO_N = 5
HARD_FZ = 85.0
HARD_HO = 80.0
SOFT_FZ = 80.0
SOFT_HO = 80.0


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
    or_lo = float(sess["Low"].iloc[0])
    width = or_hi - or_lo
    if width <= 0:
        return None
    min_w, max_w = float(cfg.get("min_or_w", 0)), float(cfg.get("max_or_w", 9999))
    if width < min_w or width > max_w:
        return None
    day_open = float(sess["Open"].iloc[0])
    prior_n = int(cfg.get("prior", 2))
    forbid_both = bool(cfg.get("forbid_both_sides", False))
    # first breaks
    first_up = first_dn = None
    for i in range(len(sess)):
        c = float(sess["Close"].iloc[i])
        if first_up is None and c > or_hi:
            first_up = i
        if first_dn is None and c < or_lo:
            first_dn = i
    if forbid_both and first_up is not None and first_dn is not None and first_dn < first_up:
        return None  # down break first — skip BUY morning

    for i, ts in enumerate(sess.index):
        hm = _hm(ts)
        if hm < cfg["hmin"] or hm > cfg["hmax"] or i < prior_n:
            continue
        if cfg.get("cont_only") and (first_up is None or i <= first_up):
            continue
        row = sess.iloc[i]
        c = float(row["Close"])
        o = float(row["Open"])
        h = float(row["High"])
        l = float(row["Low"])
        if c <= or_hi or c <= o:
            continue
        uplift = c - day_open
        if uplift < float(cfg["min_up"]):
            continue
        # day high so far vs open (impulse already printed)
        day_hi_so_far = float(sess["High"].iloc[: i + 1].max())
        if (day_hi_so_far - day_open) < float(cfg.get("min_day_hi_up", 0)):
            continue
        prior_hi = max(float(sess["High"].iloc[j]) for j in range(i - prior_n, i))
        if c <= prior_hi:
            continue
        rng = max(h - l, 1e-9)
        body_frac = abs(c - o) / rng
        if body_frac < float(cfg["body"]):
            continue
        top = float(cfg.get("top") or 0)
        if top and (c - l) / rng < top:
            continue
        min_rng = float(cfg.get("min_bar_rng", 0))
        if rng < min_rng:
            continue
        max_ext = cfg.get("max_sig_ext")
        if max_ext is not None and (c - or_hi) > float(max_ext):
            continue
        min_bf = float(cfg.get("min_bf", 0))
        bf = (c - or_hi) / width
        if bf < min_bf:
            continue
        sig_near = cfg.get("sig_near")
        if sig_near is not None and l > or_hi + float(sig_near):
            continue

        lim = or_hi + float(cfg["lim"])
        after_sig = s5[s5.index > ts] if s5 is not None and len(s5) else sess.iloc[i + 1 :]
        fill_max = cfg.get("fill_max", "13:00")
        max_fill_bars = cfg.get("max_fill_bars")  # 5m bars after signal
        n_fill = 0
        for thr, r2 in after_sig.iterrows():
            hm2 = _hm(thr)
            if hm2 > fill_max:
                break
            n_fill += 1
            if max_fill_bars is not None and n_fill > int(max_fill_bars):
                break
            if float(r2["Low"]) > lim:
                continue
            if float(r2["Close"]) <= or_hi:
                continue
            if cfg.get("fill_green") and float(r2["Close"]) <= float(r2["Open"]):
                continue
            # optional: fill bar must not undercut OR low (no full wash)
            if cfg.get("fill_hold_or") and float(r2["Low"]) < or_lo:
                continue
            after = after_sig[after_sig.index > thr]
            out = _outcome(lim, after)
            return {
                "d": str(pd.Timestamp(ts).tz_convert("Asia/Kolkata").date()),
                "sig_hm": hm,
                "fill_hm": hm2,
                "entry": round(lim, 2),
                "or_hi": round(or_hi, 2),
                "or_w": round(width, 1),
                "uplift": round(uplift, 1),
                "bf": round(bf, 3),
                "body": round(body_frac, 3),
                "out": out,
                "strong": (float(sess["High"].max()) - day_open) >= 150,
                "fill_bars": n_fill,
            }
        return None
    return None


def summ(cs: List[dict]) -> Dict[str, Any]:
    dec = [c for c in cs if c["out"] in ("win", "loss")]
    n = len(dec)
    w = sum(1 for c in dec if c["out"] == "win")
    return {
        "n": n,
        "wins": w,
        "losses": n - w,
        "hit_pct": round(100.0 * w / n, 2) if n else None,
        "strong_n": sum(1 for c in cs if c.get("strong")),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df15 = _load(TAPE15)
    df5 = _load(TAPE5)
    by15 = {d: g for d, g in df15.groupby(df15.index.strftime("%Y-%m-%d"))}
    by5 = {d: g for d, g in df5.groupby(df5.index.strftime("%Y-%m-%d"))}
    days = sorted(by15.keys())[-520:]
    hold = set(days[-HOLDOUT:])
    print(f"sessions={len(days)} holdout={HOLDOUT}", flush=True)

    # Baseline live lock for comparison
    baselines = [
        {
            "name": "LIVE_L5_u50_b55_fg",
            "lim": 5,
            "min_up": 50,
            "body": 0.55,
            "top": 0,
            "hmin": "09:45",
            "hmax": "11:30",
            "prior": 2,
            "fill_green": True,
        },
        {
            "name": "LIVE_alt_L5_u60_b65",
            "lim": 5,
            "min_up": 60,
            "body": 0.65,
            "top": 0,
            "hmin": "09:45",
            "hmax": "11:30",
            "prior": 2,
            "fill_green": False,
        },
    ]

    grid: List[Dict[str, Any]] = list(baselines)

    # Compact accuracy grid (~200 gates)
    for lim, up, body, top, hmax, fg, forbid, fill_bars in product(
        (5,),
        (50, 55, 60, 70, 80),
        (0.55, 0.60, 0.65, 0.70),
        (0.0, 0.70),
        ("11:00", "11:30"),
        (True,),
        (False, True),
        (None, 6, 12, 24),
    ):
        name = (
            f"L{lim}_u{up}_b{int(body*100)}_t{int(top*100)}_"
            f"{hmax}_fg1_fb{int(forbid)}_mb{fill_bars or 0}"
        )
        grid.append(
            {
                "name": name,
                "lim": lim,
                "min_up": up,
                "body": body,
                "top": top,
                "hmin": "09:45",
                "hmax": hmax,
                "prior": 2,
                "fill_green": fg,
                "forbid_both_sides": forbid,
                "max_fill_bars": fill_bars,
            }
        )

    # Structure / width / hold-OR curated bets
    curated = [
        dict(name="acc_L5_u60_b65_fg_fb_t70", lim=5, min_up=60, body=0.65, top=0.7, hmin="09:45", hmax="11:30", prior=2, fill_green=True, forbid_both_sides=True),
        dict(name="acc_L5_u70_b65_fg_fb", lim=5, min_up=70, body=0.65, top=0, hmin="09:45", hmax="11:30", prior=2, fill_green=True, forbid_both_sides=True),
        dict(name="acc_L5_u50_b70_fg_fb_mb12", lim=5, min_up=50, body=0.70, top=0, hmin="09:45", hmax="11:30", prior=2, fill_green=True, forbid_both_sides=True, max_fill_bars=12),
        dict(name="acc_L5_u60_b65_fg_mb12", lim=5, min_up=60, body=0.65, top=0, hmin="09:45", hmax="11:30", prior=2, fill_green=True, max_fill_bars=12),
        dict(name="acc_L5_u55_b65_fg_fb_w40_180", lim=5, min_up=55, body=0.65, top=0, hmin="09:45", hmax="11:00", prior=2, fill_green=True, forbid_both_sides=True, min_or_w=40, max_or_w=180),
        dict(name="acc_L5_u60_b70_fg_rng35_fb", lim=5, min_up=60, body=0.70, top=0.7, hmin="09:45", hmax="11:30", prior=2, fill_green=True, forbid_both_sides=True, min_bar_rng=35),
        dict(name="acc_L5_u50_b65_fg_fb_holdOR", lim=5, min_up=50, body=0.65, top=0, hmin="09:45", hmax="11:30", prior=2, fill_green=True, forbid_both_sides=True, fill_hold_or=True),
        dict(name="acc_L5_u60_b65_fg_fb_holdOR_mb24", lim=5, min_up=60, body=0.65, top=0, hmin="09:45", hmax="11:30", prior=2, fill_green=True, forbid_both_sides=True, fill_hold_or=True, max_fill_bars=24),
        dict(name="acc_L8_u60_b65_fg_fb", lim=8, min_up=60, body=0.65, top=0, hmin="09:45", hmax="11:30", prior=2, fill_green=True, forbid_both_sides=True),
        dict(name="acc_L5_u80_b70_fg_fb", lim=5, min_up=80, body=0.70, top=0.7, hmin="09:45", hmax="11:00", prior=2, fill_green=True, forbid_both_sides=True),
        dict(name="acc_L5_u50_b55_fg_fb_mb6", lim=5, min_up=50, body=0.55, top=0, hmin="09:45", hmax="11:30", prior=2, fill_green=True, forbid_both_sides=True, max_fill_bars=6),
        dict(name="acc_L5_u60_b65_p3_fg_fb", lim=5, min_up=60, body=0.65, top=0, hmin="09:45", hmax="11:30", prior=3, fill_green=True, forbid_both_sides=True),
        dict(name="acc_cont_L5_u60_b65_fg", lim=5, min_up=60, body=0.65, top=0, hmin="10:00", hmax="12:00", prior=2, fill_green=True, cont_only=True),
        dict(name="acc_L5_u55_b65_fg_fb_t70_mb12", lim=5, min_up=55, body=0.65, top=0.7, hmin="09:45", hmax="11:00", prior=2, fill_green=True, forbid_both_sides=True, max_fill_bars=12),
        dict(name="acc_L5_u60_b65_fg_fb_w60_200_rng25", lim=5, min_up=60, body=0.65, top=0, hmin="09:45", hmax="11:30", prior=2, fill_green=True, forbid_both_sides=True, min_or_w=60, max_or_w=200, min_bar_rng=25),
        dict(name="acc_L5_u70_b70_fg_fb_mb12_holdOR", lim=5, min_up=70, body=0.70, top=0.7, hmin="09:45", hmax="11:00", prior=2, fill_green=True, forbid_both_sides=True, max_fill_bars=12, fill_hold_or=True),
        dict(name="acc_L5_u55_b60_fg_fb_mb12", lim=5, min_up=55, body=0.60, top=0, hmin="09:45", hmax="11:30", prior=2, fill_green=True, forbid_both_sides=True, max_fill_bars=12),
        dict(name="acc_L5_u65_b65_fg_fb_t70", lim=5, min_up=65, body=0.65, top=0.7, hmin="09:45", hmax="11:30", prior=2, fill_green=True, forbid_both_sides=True),
    ]
    grid.extend(curated)

    # de-dupe by name
    seen = set()
    uniq = []
    for g in grid:
        if g["name"] in seen:
            continue
        seen.add(g["name"])
        uniq.append(g)
    grid = uniq
    print(f"gates={len(grid)}", flush=True)

    results = []
    for cfg in grid:
        fz: List[dict] = []
        ho: List[dict] = []
        for d in days:
            call = evaluate_day(by15[d], by5.get(d, by15[d].iloc[0:0]), cfg)
            if not call:
                continue
            (ho if d in hold else fz).append(call)
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
        hard = bool(
            sf["n"] >= MIN_FZ_N
            and sh["n"] >= MIN_HO_N
            and (sf["hit_pct"] or 0) >= HARD_FZ
            and (sh["hit_pct"] or 0) >= HARD_HO
        )
        soft = bool(
            sf["n"] >= MIN_FZ_N
            and sh["n"] >= MIN_HO_N
            and (sf["hit_pct"] or 0) >= SOFT_FZ
            and (sh["hit_pct"] or 0) >= SOFT_HO
        )
        row = {
            "gate": cfg["name"],
            "params": {k: v for k, v in cfg.items() if k != "name"},
            "freeze": sf,
            "holdout": sh,
            "holdout_strong_catch_pct": catch,
            "hard_pass": hard,
            "soft_pass": soft,
            "holdout_calls": [
                {k: c[k] for k in ("d", "sig_hm", "fill_hm", "entry", "out", "uplift")}
                for c in ho
            ],
        }
        results.append(row)
        if hard or soft or (sf["hit_pct"] or 0) >= 82:
            print(
                f"{cfg['name'][:70]:70s} fz {sf['n']:3d}@{sf['hit_pct']}  "
                f"ho {sh['n']:3d}@{sh['hit_pct']}  catch {catch}%  "
                f"HARD={hard} SOFT={soft}",
                flush=True,
            )

    results.sort(
        key=lambda r: (
            int(r["hard_pass"]),
            int(r["soft_pass"]),
            (r["holdout"]["hit_pct"] or 0),
            (r["freeze"]["hit_pct"] or 0),
            (r["holdout_strong_catch_pct"] or 0),
            r["holdout"]["n"],
        ),
        reverse=True,
    )

    hard = [r for r in results if r["hard_pass"]]
    soft = [r for r in results if r["soft_pass"]]
    # best among soft/hard with catch preference
    pool = hard or soft or results[:1]
    best = max(
        pool,
        key=lambda r: (
            int(r["hard_pass"]),
            int(r["soft_pass"]),
            (r["holdout"]["hit_pct"] or 0),
            (r["freeze"]["hit_pct"] or 0),
            (r["holdout_strong_catch_pct"] or 0),
            r["holdout"]["n"],
        ),
    )
    # best catch among soft≥80/80 or hard
    catch_pool = [r for r in results if r["hard_pass"] or r["soft_pass"]]
    best_catch = (
        max(
            catch_pool,
            key=lambda r: (
                (r["holdout_strong_catch_pct"] or 0),
                (r["holdout"]["hit_pct"] or 0),
                (r["freeze"]["hit_pct"] or 0),
            ),
        )
        if catch_pool
        else best
    )

    live = next((r for r in results if r["gate"] == "LIVE_L5_u50_b55_fg"), None)

    payload = {
        "brackets": {"sl": SL, "t1": T1},
        "floors": {"hard": [HARD_FZ, HARD_HO], "soft": [SOFT_FZ, SOFT_HO], "min_n": [MIN_FZ_N, MIN_HO_N]},
        "n_gates": len(results),
        "hard_pass_n": len(hard),
        "soft_pass_n": len(soft),
        "live_baseline": live,
        "best_accurate": {
            "gate": best["gate"],
            "params": best["params"],
            "freeze": best["freeze"],
            "holdout": best["holdout"],
            "catch": best["holdout_strong_catch_pct"],
            "hard_pass": best["hard_pass"],
            "soft_pass": best["soft_pass"],
            "holdout_calls": best["holdout_calls"],
        },
        "best_catch_among_pass": {
            "gate": best_catch["gate"],
            "params": best_catch["params"],
            "freeze": best_catch["freeze"],
            "holdout": best_catch["holdout"],
            "catch": best_catch["holdout_strong_catch_pct"],
            "hard_pass": best_catch["hard_pass"],
            "soft_pass": best_catch["soft_pass"],
        },
        "top": [
            {
                "gate": r["gate"],
                "freeze": r["freeze"],
                "holdout": r["holdout"],
                "catch": r["holdout_strong_catch_pct"],
                "hard": r["hard_pass"],
                "soft": r["soft_pass"],
                "params": r["params"],
            }
            for r in results[:40]
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# NIFTY morning strong BUY · accuracy research",
        "",
        "Honest path only: **15m thrust → 5m fill at OR+lim · ±30**.",
        "Close-chase OR breaks remain ~30% — excluded.",
        "",
        f"Gates tested: **{len(results)}** · hard pass (≥{HARD_FZ}/{HARD_HO}): **{len(hard)}** · "
        f"soft pass (≥{SOFT_FZ}/{SOFT_HO}): **{len(soft)}**",
        "",
        "## Live baseline",
        "",
    ]
    if live:
        lines.append(
            f"- `{live['gate']}` · freeze {live['freeze']['n']}@{live['freeze']['hit_pct']}% · "
            f"holdout {live['holdout']['n']}@{live['holdout']['hit_pct']}% · catch {live['holdout_strong_catch_pct']}% · "
            f"hard={live['hard_pass']} soft={live['soft_pass']}"
        )
    lines += [
        "",
        "## Best accurate",
        "",
        f"- **`{best['gate']}`** · freeze {best['freeze']['n']}@{best['freeze']['hit_pct']}% · "
        f"holdout {best['holdout']['n']}@{best['holdout']['hit_pct']}% · catch {best['holdout_strong_catch_pct']}% · "
        f"hard={best['hard_pass']} soft={best['soft_pass']}",
        f"- params: `{json.dumps(best['params'])}`",
        "",
        "## Best catch among pass gates",
        "",
        f"- **`{best_catch['gate']}`** · catch {best_catch['holdout_strong_catch_pct']}% · "
        f"fz {best_catch['freeze']['n']}@{best_catch['freeze']['hit_pct']}% · "
        f"ho {best_catch['holdout']['n']}@{best_catch['holdout']['hit_pct']}%",
        f"- params: `{json.dumps(best_catch['params'])}`",
        "",
        "## Ranking",
        "",
        "| gate | freeze | holdout | catch | hard | soft |",
        "|---|---:|---:|---:|---|---|",
    ]
    for r in results[:30]:
        lines.append(
            f"| `{r['gate']}` | {r['freeze']['n']}@{r['freeze']['hit_pct']} | "
            f"{r['holdout']['n']}@{r['holdout']['hit_pct']} | {r['holdout_strong_catch_pct']}% | "
            f"{r['hard_pass']} | {r['soft_pass']} |"
        )
    lines += ["", "## Holdout calls (best accurate)", ""]
    for c in best["holdout_calls"]:
        lines.append(
            f"- {c['d']} sig {c['sig_hm']} fill {c['fill_hm']} @ {c['entry']} · {c['out']} · uplift {c['uplift']}"
        )
    lines += [
        "",
        "## Verdict",
        "",
    ]
    if hard:
        lines.append(
            f"- Hard-pass gate exists: prefer **`{best['gate']}`** for accuracy before any live retune."
        )
    elif soft:
        lines.append(
            f"- No hard ≥{HARD_FZ}/{HARD_HO}; soft-pass **`{best['gate']}`** is the accuracy pick."
        )
    else:
        lines.append(
            "- No gate cleared soft ≥80/80 with n floors — morning strong stays research-cautious; "
            "live L5_u50_b55_fg remains the catch-biased soft lane."
        )
    lines += ["", f"JSON: `{OUT_JSON}`", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("BEST", best["gate"], best["freeze"], best["holdout"], "catch", best["holdout_strong_catch_pct"], flush=True)
    print("BEST_CATCH", best_catch["gate"], "catch", best_catch["holdout_strong_catch_pct"], flush=True)
    print("hard_n", len(hard), "soft_n", len(soft), flush=True)
    print("wrote", OUT_MD, flush=True)


if __name__ == "__main__":
    main()
