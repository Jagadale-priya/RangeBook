"""NIFTY morning strong BUY — find ±30-accurate catch lane (or best wider bracket).

v1 OR-break / thrust-at-close all ~25-40% at ±30. This pass tests:
  A) retest / shallow-chase entries (enter near OR, not extended close)
  B) same thrust rules at ±40 / ±50 / ±60
  C) pullback-then-resume after first OR break
  D) impulse+dip: uplift already large, enter on green reclaim

  python -u prod_live/tests/builders/_research_nifty_morning_strong_v2.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app"), str(ROOT / "app" / "fno")]
import path_setup  # noqa: F401,E402

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT_DIR / "NIFTY_MORNING_STRONG_OR_V2.md"
OUT_JSON = OUT_DIR / "NIFTY_MORNING_STRONG_OR_V2.json"
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_kite.csv"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
HOLDOUT = 40
MIN_FZ_N = 12
MIN_HO_N = 4
MIN_FZ_HIT = 80.0
MIN_HO_HIT = 75.0


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


def _outcome(entry: float, after: pd.DataFrame, sl: float, t1: float) -> str:
    if after is None or after.empty:
        return "open"
    stop, tgt = entry - sl, entry + t1
    for _, r in after.iterrows():
        lo, hi = float(r["Low"]), float(r["High"])
        hit_sl, hit_t1 = lo <= stop, hi >= tgt
        if hit_sl and hit_t1:
            return "loss"
        if hit_t1:
            return "win"
        if hit_sl:
            return "loss"
    return "open"


def _summ(calls: List[dict]) -> Dict[str, Any]:
    dec = [c for c in calls if c["out"] in ("win", "loss")]
    n = len(dec)
    w = sum(1 for c in dec if c["out"] == "win")
    return {
        "n": n,
        "wins": w,
        "hit_pct": round(100.0 * w / n, 2) if n else None,
        "open": sum(1 for c in calls if c["out"] == "open"),
        "strong_n": sum(1 for c in calls if c.get("strong")),
    }


EntryFn = Callable[[pd.DataFrame, pd.DataFrame], Optional[dict]]


def make_close_thrust(
    *,
    hmin: str,
    hmax: str,
    min_up: float,
    prior: int,
    min_bf: float = 0.0,
    max_ext_pts: float = 9999.0,
    cont_only: bool = False,
    close_top: float = 0.0,
    min_body_frac: float = 0.0,
) -> EntryFn:
    def fn(sess: pd.DataFrame, s5: pd.DataFrame) -> Optional[dict]:
        or_hi = float(sess["High"].iloc[0])
        or_lo = float(sess["Low"].iloc[0])
        w = or_hi - or_lo
        if w <= 0:
            return None
        day_open = float(sess["Open"].iloc[0])
        first_up = None
        for i in range(len(sess)):
            if float(sess["Close"].iloc[i]) > or_hi:
                first_up = i
                break
        for i, ts in enumerate(sess.index):
            hm = _hm(ts)
            if hm < hmin or hm > hmax:
                continue
            if cont_only and (first_up is None or i <= first_up):
                continue
            if i < prior:
                continue
            row = sess.iloc[i]
            c, o, h, l = float(row["Close"]), float(row["Open"]), float(row["High"]), float(row["Low"])
            if c <= or_hi or c <= o:
                continue
            bf = (c - or_hi) / w
            if bf < min_bf:
                continue
            if (c - or_hi) > max_ext_pts:
                continue
            if (c - day_open) < min_up:
                continue
            prior_hi = max(float(sess["High"].iloc[j]) for j in range(i - prior, i))
            if c <= prior_hi:
                continue
            rng = max(h - l, 1e-9)
            if min_body_frac > 0 and abs(c - o) / rng < min_body_frac:
                continue
            if close_top > 0 and (c - l) / rng < close_top:
                continue
            after = s5[s5.index > ts] if s5 is not None and len(s5) else sess.iloc[i + 1 :]
            return {
                "hm": hm,
                "entry": c,
                "bf": bf,
                "uplift": c - day_open,
                "after": after,
                "mode": "close_thrust",
            }
        return None

    return fn


def make_retest(
    *,
    hmin: str = "09:45",
    hmax: str = "12:00",
    max_retest_dist: float = 15.0,
    require_prior_break: bool = True,
    min_impulse_up: float = 40.0,
) -> EntryFn:
    """After OR break + impulse, enter when a later bar dips near OR and closes green above OR."""

    def fn(sess: pd.DataFrame, s5: pd.DataFrame) -> Optional[dict]:
        or_hi = float(sess["High"].iloc[0])
        or_lo = float(sess["Low"].iloc[0])
        w = or_hi - or_lo
        if w <= 0:
            return None
        day_open = float(sess["Open"].iloc[0])
        broke = False
        impulse_ok = False
        for i, ts in enumerate(sess.index):
            hm = _hm(ts)
            row = sess.iloc[i]
            c, o, h, l = float(row["Close"]), float(row["Open"]), float(row["High"]), float(row["Low"])
            if c > or_hi:
                broke = True
            if broke and (float(sess["High"].iloc[: i + 1].max()) - day_open) >= min_impulse_up:
                impulse_ok = True
            if hm < hmin or hm > hmax:
                continue
            if require_prior_break and not (broke and impulse_ok):
                continue
            if c <= or_hi or c <= o:
                continue
            # shallow: low came within max_retest_dist of OR high (reclaim)
            if l > or_hi + max_retest_dist:
                continue
            if l < or_lo:  # full washout — skip
                continue
            after = s5[s5.index > ts] if s5 is not None and len(s5) else sess.iloc[i + 1 :]
            return {
                "hm": hm,
                "entry": c,
                "bf": (c - or_hi) / w,
                "uplift": c - day_open,
                "after": after,
                "mode": "retest",
            }
        return None

    return fn


def make_synthetic_near_or(
    *,
    hmin: str,
    hmax: str,
    min_up: float,
    prior: int,
    entry_offset: float = 5.0,
) -> EntryFn:
    """Thrust confirms at close, but fill assumed at OR_hi + offset (better R:R)."""

    def fn(sess: pd.DataFrame, s5: pd.DataFrame) -> Optional[dict]:
        or_hi = float(sess["High"].iloc[0])
        day_open = float(sess["Open"].iloc[0])
        for i, ts in enumerate(sess.index):
            hm = _hm(ts)
            if hm < hmin or hm > hmax or i < prior:
                continue
            row = sess.iloc[i]
            c, o, h, l = float(row["Close"]), float(row["Open"]), float(row["High"]), float(row["Low"])
            if c <= or_hi or c <= o:
                continue
            if (c - day_open) < min_up:
                continue
            prior_hi = max(float(sess["High"].iloc[j]) for j in range(i - prior, i))
            if c <= prior_hi:
                continue
            entry = or_hi + entry_offset
            # only valid if bar actually traded down to that zone
            if l > entry:
                continue
            after = s5[s5.index > ts] if s5 is not None and len(s5) else sess.iloc[i + 1 :]
            return {
                "hm": hm,
                "entry": entry,
                "bf": (c - or_hi) / max(or_hi - float(sess["Low"].iloc[0]), 1e-9),
                "uplift": c - day_open,
                "after": after,
                "mode": "synth_near_or",
            }
        return None

    return fn


def make_dip_buy(
    *,
    hmin: str = "10:00",
    hmax: str = "12:15",
    min_day_hi_up: float = 80.0,
    max_dip_from_hi: float = 35.0,
    min_hold_above_or: bool = True,
) -> EntryFn:
    """Strong morning high already printed; buy green reclaim after shallow dip."""

    def fn(sess: pd.DataFrame, s5: pd.DataFrame) -> Optional[dict]:
        or_hi = float(sess["High"].iloc[0])
        day_open = float(sess["Open"].iloc[0])
        for i, ts in enumerate(sess.index):
            hm = _hm(ts)
            if hm < hmin or hm > hmax:
                continue
            so_far = sess.iloc[: i + 1]
            day_hi = float(so_far["High"].max())
            if (day_hi - day_open) < min_day_hi_up:
                continue
            row = sess.iloc[i]
            c, o, l = float(row["Close"]), float(row["Open"]), float(row["Low"])
            if c <= o:
                continue
            if min_hold_above_or and c <= or_hi:
                continue
            dip = day_hi - l
            if dip < 12 or dip > max_dip_from_hi:
                continue
            # reclaim: close near highs of pullback bar
            if c < day_hi - max_dip_from_hi:
                continue
            after = s5[s5.index > ts] if s5 is not None and len(s5) else sess.iloc[i + 1 :]
            return {
                "hm": hm,
                "entry": c,
                "bf": 0.0,
                "uplift": c - day_open,
                "after": after,
                "mode": "dip_buy",
            }
        return None

    return fn


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df15 = _load(TAPE15)
    df5 = _load(TAPE5) if TAPE5.exists() else None
    by15 = {d: g for d, g in df15.groupby(df15.index.strftime("%Y-%m-%d"))}
    by5 = {d: g for d, g in df5.groupby(df5.index.strftime("%Y-%m-%d"))} if df5 is not None else {}
    days = sorted(by15.keys())
    if len(days) > 520:
        days = days[-520:]
    hold = set(days[-HOLDOUT:])
    print(f"sessions={len(days)} holdout={HOLDOUT}", flush=True)

    variants: List[Tuple[str, EntryFn, float, float]] = []
    # brackets sweep on best structural ideas
    for sl in (30.0, 40.0, 50.0, 60.0):
        variants.append(
            (
                f"thrust2_up50_close_pm{sl:.0f}",
                make_close_thrust(hmin="09:45", hmax="11:30", min_up=50, prior=2),
                sl,
                sl,
            )
        )
        variants.append(
            (
                f"cont_thrust2_up50_pm{sl:.0f}",
                make_close_thrust(hmin="10:00", hmax="12:00", min_up=50, prior=2, cont_only=True),
                sl,
                sl,
            )
        )
        variants.append(
            (
                f"retest15_imp40_pm{sl:.0f}",
                make_retest(max_retest_dist=15, min_impulse_up=40),
                sl,
                sl,
            )
        )
        variants.append(
            (
                f"retest25_imp60_pm{sl:.0f}",
                make_retest(max_retest_dist=25, min_impulse_up=60),
                sl,
                sl,
            )
        )
        variants.append(
            (
                f"synth_or5_up50_pm{sl:.0f}",
                make_synthetic_near_or(hmin="09:45", hmax="11:30", min_up=50, prior=2, entry_offset=5),
                sl,
                sl,
            )
        )
        variants.append(
            (
                f"dip_hi80_dip35_pm{sl:.0f}",
                make_dip_buy(min_day_hi_up=80, max_dip_from_hi=35),
                sl,
                sl,
            )
        )

    # ±30-only tight filters
    for max_ext in (20, 30, 40):
        variants.append(
            (
                f"thrust2_up40_maxext{max_ext}_pm30",
                make_close_thrust(
                    hmin="09:45", hmax="11:00", min_up=40, prior=2, max_ext_pts=float(max_ext), min_bf=0.10
                ),
                30.0,
                30.0,
            )
        )
    variants += [
        (
            "thrust2_up50_top70_pm30",
            make_close_thrust(hmin="09:45", hmax="11:30", min_up=50, prior=2, close_top=0.70),
            30.0,
            30.0,
        ),
        (
            "thrust2_up60_body55_pm30",
            make_close_thrust(hmin="10:00", hmax="12:00", min_up=60, prior=2, min_body_frac=0.55, cont_only=True),
            30.0,
            30.0,
        ),
        (
            "retest12_imp50_top_pm30",
            make_retest(max_retest_dist=12, min_impulse_up=50, hmax="11:45"),
            30.0,
            30.0,
        ),
        (
            "dip_hi100_dip30_pm30",
            make_dip_buy(min_day_hi_up=100, max_dip_from_hi=30, hmin="10:00", hmax="12:30"),
            30.0,
            30.0,
        ),
        (
            "dip_hi120_dip40_pm40",
            make_dip_buy(min_day_hi_up=120, max_dip_from_hi=40, hmin="10:00", hmax="12:30"),
            40.0,
            40.0,
        ),
        (
            "retest20_imp80_pm50",
            make_retest(max_retest_dist=20, min_impulse_up=80, hmin="10:00", hmax="12:30"),
            50.0,
            50.0,
        ),
    ]

    results = []
    for name, entry_fn, sl, t1 in variants:
        fz: List[dict] = []
        ho: List[dict] = []
        for d in days:
            sess = by15[d]
            if len(sess) < 6:
                continue
            sig = entry_fn(sess, by5.get(d, sess.iloc[0:0]))
            if not sig:
                continue
            out = _outcome(float(sig["entry"]), sig["after"], sl, t1)
            day_open = float(sess["Open"].iloc[0])
            strong = (float(sess["High"].max()) - day_open) >= 150
            rec = {
                "d": d,
                "hm": sig["hm"],
                "entry": round(float(sig["entry"]), 2),
                "out": out,
                "strong": strong,
                "mode": sig["mode"],
                "sl": sl,
            }
            (ho if d in hold else fz).append(rec)
        sf, sh = _summ(fz), _summ(ho)
        # strong-day catch in holdout
        sh_days = 0
        caught = 0
        call_days = {c["d"] for c in ho}
        for d in days[-HOLDOUT:]:
            sess = by15[d]
            if (float(sess["High"].max()) - float(sess["Open"].iloc[0])) >= 150:
                sh_days += 1
                if d in call_days:
                    caught += 1
        catch = round(100.0 * caught / sh_days, 1) if sh_days else None
        passed = bool(
            sf["n"] >= MIN_FZ_N
            and sh["n"] >= MIN_HO_N
            and (sf["hit_pct"] or 0) >= MIN_FZ_HIT
            and (sh["hit_pct"] or 0) >= MIN_HO_HIT
        )
        row = {
            "gate": name,
            "sl": sl,
            "t1": t1,
            "freeze": sf,
            "holdout": sh,
            "holdout_strong_catch_pct": catch,
            "holdout_strong_days": sh_days,
            "holdout_strong_caught": caught,
            "pass": passed,
        }
        results.append(row)
        print(
            f"{name:42s} fz {sf['n']:3d}@{sf['hit_pct']}  ho {sh['n']:3d}@{sh['hit_pct']}  "
            f"catch {catch}%  PASS={passed}",
            flush=True,
        )

    results.sort(
        key=lambda r: (
            int(r["pass"]),
            (r["holdout"]["hit_pct"] or 0),
            (r["freeze"]["hit_pct"] or 0),
            (r["holdout_strong_catch_pct"] or 0),
            r["holdout"]["n"],
        ),
        reverse=True,
    )
    # best ±30 separately
    pm30 = [r for r in results if r["sl"] == 30]
    best30 = pm30[0] if pm30 else None
    best = results[0] if results else None
    eligible = [
        r
        for r in results
        if (r["freeze"]["n"] or 0) >= 10
        and (r["holdout"]["n"] or 0) >= MIN_HO_N
        and (r["freeze"]["hit_pct"] or 0) >= 70
    ]
    best_eligible = max(
        eligible,
        key=lambda r: ((r["holdout"]["hit_pct"] or 0), (r["freeze"]["hit_pct"] or 0), (r["holdout_strong_catch_pct"] or 0)),
    ) if eligible else None

    payload = {
        "note": "Morning strong BUY v2 — retest/dip/synth + bracket sweep",
        "min_gates": {
            "freeze_n": MIN_FZ_N,
            "hold_n": MIN_HO_N,
            "freeze_hit": MIN_FZ_HIT,
            "hold_hit": MIN_HO_HIT,
        },
        "results": results,
        "best_pass": best if best and best["pass"] else None,
        "best_overall": best,
        "best_pm30": best30,
        "best_eligible_70fz": best_eligible,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# NIFTY morning strong BUY research v2",
        "",
        "v1 close-at-OR-break failed (~30% @ ±30). This pass: retest / dip / synth-near-OR + bracket sweep.",
        "",
        "| gate | SL | freeze | holdout | strong catch | pass |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in results[:40]:
        lines.append(
            f"| `{r['gate']}` | {r['sl']:.0f} | {r['freeze']['n']}@{r['freeze']['hit_pct']} | "
            f"{r['holdout']['n']}@{r['holdout']['hit_pct']} | {r['holdout_strong_catch_pct']}% | {r['pass']} |"
        )
    lines += ["", "## Recommendation", ""]
    if best and best["pass"]:
        lines.append(f"- **PASS:** `{best['gate']}` · holdout {best['holdout']['n']}@{best['holdout']['hit_pct']}%")
    elif best_eligible:
        lines.append(
            f"- **Best eligible (≥70% freeze):** `{best_eligible['gate']}` · "
            f"fz {best_eligible['freeze']['n']}@{best_eligible['freeze']['hit_pct']}% · "
            f"ho {best_eligible['holdout']['n']}@{best_eligible['holdout']['hit_pct']}% · "
            f"catch {best_eligible['holdout_strong_catch_pct']}%"
        )
    else:
        lines.append("- No gate cleared accuracy floors — morning strong may need dual p-path or skip live wire.")
    if best30:
        lines.append(
            f"- Best ±30: `{best30['gate']}` · fz {best30['freeze']['hit_pct']}% · ho {best30['holdout']['hit_pct']}%"
        )
    lines += ["", f"JSON: `{OUT_JSON}`", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT_MD, flush=True)
    if best_eligible:
        print("BEST_ELIGIBLE", best_eligible["gate"], best_eligible["holdout"], flush=True)
    if best and best["pass"]:
        print("BEST_PASS", best["gate"], flush=True)


if __name__ == "__main__":
    main()
