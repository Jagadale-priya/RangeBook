"""Compare NIFTY live lanes vs research on 1y / 3y / 5y (fast).

Live lanes only:
  - morning strong OR+5 (locked L5_u70_b80) — same rule as research
  - afternoon thrust2_up30 — live evaluate() first fire/day

  python -u prod_live/tests/builders/_compare_nifty_live_vs_research_windows.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
]

TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_kite.csv"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
OUT_MD = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_LIVE_THRUST_ONLY_1_3_5Y.md"
OUT_JSON = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_LIVE_THRUST_ONLY_1_3_5Y.json"
SL = T1 = 30.0
CFG = {
    "lim": 5.0,
    "min_up": 70.0,
    "body": 0.8,
    "hmin": "09:45",
    "hmax": "11:30",
    "fill_green": True,
    "forbid_both_sides": True,
    "max_fill_bars": 18,
    "prior": 2,
}


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


def _day(ts: Any) -> str:
    return str(pd.Timestamp(ts).tz_convert("Asia/Kolkata").date())


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


def morning_day(sess: pd.DataFrame, s5: pd.DataFrame) -> Optional[dict]:
    if len(sess) < 6 or s5 is None or s5.empty:
        return None
    or_hi = float(sess["High"].iloc[0])
    or_lo = float(sess["Low"].iloc[0])
    day_open = float(sess["Open"].iloc[0])
    prior_n = int(CFG["prior"])
    if CFG["forbid_both_sides"]:
        first_up = first_dn = None
        closes = sess["Close"].astype(float).values
        for i, c in enumerate(closes):
            if first_up is None and c > or_hi:
                first_up = i
            if first_dn is None and c < or_lo:
                first_dn = i
        if first_up is not None and first_dn is not None and first_dn < first_up:
            return None
    sig_ts = None
    uplift = 0.0
    highs = sess["High"].astype(float).values
    opens = sess["Open"].astype(float).values
    lows = sess["Low"].astype(float).values
    # First loose thrust, then require locked gates on that same bar.
    for i, ts in enumerate(sess.index):
        hm = _hm(ts)
        if hm < CFG["hmin"] or hm > CFG["hmax"] or i < prior_n:
            continue
        c, o, hi, lo = float(closes[i]), float(opens[i]), float(highs[i]), float(lows[i])
        if c <= or_hi or c <= o:
            continue
        up = c - day_open
        if up < 40.0:
            continue
        if c <= max(highs[i - prior_n : i]):
            continue
        rng = max(hi - lo, 1e-9)
        body = abs(c - o) / rng
        if body < 0.50:
            continue
        if up < CFG["min_up"] or body < CFG["body"]:
            return None
        sig_ts = ts
        uplift = up
        break
    if sig_ts is None:
        return None
    lim = or_hi + CFG["lim"]
    after5 = s5[s5.index > sig_ts]
    n = 0
    for ts, row in after5.iterrows():
        n += 1
        if n > CFG["max_fill_bars"]:
            break
        hm = _hm(ts)
        if hm > "13:00":
            break
        if float(row["Low"]) > lim:
            continue
        if float(row["Close"]) <= or_hi:
            continue
        if CFG["fill_green"] and float(row["Close"]) <= float(row["Open"]):
            continue
        entry = lim
        # Locked research settles on 5m after fill (not 15m).
        after5 = s5[s5.index > ts]
        return {
            "d": _day(sig_ts),
            "lane": "morning",
            "sig": _hm(sig_ts),
            "fill": hm,
            "entry": round(entry, 2),
            "out": _outcome(entry, after5),
            "uplift": round(uplift, 1),
            "fill_ts": ts,
        }
    return None


def afternoon_day(sess: pd.DataFrame) -> Optional[dict]:
    if len(sess) < 8:
        return None
    or_hi = float(sess["High"].iloc[0])
    open13 = None
    for ts in sess.index:
        if _hm(ts) == "13:00":
            open13 = float(sess.loc[ts, "Open"])
            break
    if open13 is None:
        return None
    highs = sess["High"].astype(float).values
    opens = sess["Open"].astype(float).values
    closes = sess["Close"].astype(float).values
    for i, ts in enumerate(sess.index):
        hm = _hm(ts)
        if hm < "13:15" or hm > "14:45" or i < 2:
            continue
        c, o = float(closes[i]), float(opens[i])
        if c <= or_hi or c <= o:
            continue
        if (c - open13) < 30.0:
            continue
        if c <= max(highs[i - 2 : i]):
            continue
        entry = c
        after = sess.iloc[i + 1 :]
        return {
            "d": _day(ts),
            "lane": "afternoon",
            "sig": hm,
            "fill": hm,
            "entry": round(entry, 2),
            "out": _outcome(entry, after),
            "uplift": round(c - open13, 1),
            "fill_ts": ts,
        }


def _stats_last_n_sessions(rows: List[dict], days: List[str], n_sessions: int) -> Dict[str, Any]:
    cut_days = set(days[-n_sessions:]) if len(days) >= n_sessions else set(days)
    return _stats([r for r in rows if r["d"] in cut_days])
    return None


def verify_live_modules(morning_rows: List[dict], afternoon_rows: List[dict], bars15, bars5) -> Dict[str, Any]:
    """Spot-check live evaluate() matches research fires (sample up to 15 each)."""
    import nifty_afternoon_thrust as nat
    import nifty_morning_strong_thrust as nmst

    m_ok = m_fail = 0
    for r in morning_rows[:15]:
        ts = r["fill_ts"]
        w15 = bars15[bars15.index <= ts]
        w5 = bars5[bars5.index <= ts]
        fire = nmst.evaluate(w15, w5, asof=ts.to_pydatetime(), price=float(r["entry"]))
        if isinstance(fire, dict) and fire.get("decision") == "BUY" and abs(float(fire["entry"]) - float(r["entry"])) < 0.05:
            m_ok += 1
        else:
            m_fail += 1
    a_ok = a_fail = 0
    for r in afternoon_rows[:15]:
        ts = r["fill_ts"]
        w15 = bars15[bars15.index <= ts]
        fire = nat.evaluate(w15, asof=ts.to_pydatetime(), price=float(r["entry"]))
        if isinstance(fire, dict) and fire.get("decision") == "BUY":
            a_ok += 1
        else:
            a_fail += 1
    return {
        "morning_live_match": {"ok": m_ok, "fail": m_fail, "sampled": m_ok + m_fail},
        "afternoon_live_match": {"ok": a_ok, "fail": a_fail, "sampled": a_ok + a_fail},
        "live_min_uplift": nmst.MIN_UPLIFT,
        "live_body": nmst.MIN_BODY_FRAC,
        "live_forbid_dn": nmst.FORBID_DOWN_BREAK_FIRST,
    }


def _stats(rows: List[dict]) -> Dict[str, Any]:
    closed = [r for r in rows if r.get("out") in ("win", "loss")]
    wins = sum(1 for r in closed if r["out"] == "win")
    n = len(closed)
    return {
        "n": n,
        "wins": wins,
        "losses": n - wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else None,
        "open": sum(1 for r in rows if r.get("out") == "open"),
        "raw": len(rows),
    }


def main() -> int:
    if not TAPE15.exists() or not TAPE5.exists():
        print("MISSING tapes", TAPE15.exists(), TAPE5.exists())
        return 2
    bars15 = _load(TAPE15)
    bars5 = _load(TAPE5)
    # Pre-group by day (fast)
    bars15["__d"] = [_day(t) for t in bars15.index]
    bars5["__d"] = [_day(t) for t in bars5.index]
    g15 = {d: g.drop(columns="__d") for d, g in bars15.groupby("__d", sort=True)}
    g5 = {d: g.drop(columns="__d") for d, g in bars5.groupby("__d", sort=True)}
    days = sorted(g15.keys())
    end = pd.Timestamp(days[-1])
    print(f"tape days={len(days)} end={days[-1]} 15m={len(bars15)} 5m={len(bars5)}")

    morning: List[dict] = []
    afternoon: List[dict] = []
    for d in days:
        sess15 = g15[d]
        sess5 = g5.get(d)
        if sess5 is None or len(sess15) < 8:
            continue
        m = morning_day(sess15, sess5)
        if m:
            morning.append(m)
        a = afternoon_day(sess15)
        if a:
            afternoon.append(a)

    live_check = verify_live_modules(morning, afternoon, bars15.drop(columns="__d", errors="ignore"), bars5.drop(columns="__d", errors="ignore"))
    print("live module check", live_check)

    def in_win(rows: List[dict], years: float) -> List[dict]:
        cut = (end - pd.DateOffset(years=years)).date().isoformat()
        return [r for r in rows if r["d"] >= cut]

    report: Dict[str, Any] = {
        "end": days[-1],
        "live_lanes": ["morning_strong_L5_u70_b80", "afternoon_thrust2_up30"],
        "live_module_check": live_check,
        "windows": {},
    }
    lines = [
        "# NIFTY live thrust-only · 1y / 3y / 5y",
        "",
        f"End day: `{days[-1]}` · brackets ±{SL:.0f}",
        "",
        "**Live Calls (accuracy desk):** Morning strong `L5_u70_b80` only.",
        "- Afternoon `thrust2_up30` measured below but **disabled live** (full-window ~50%).",
        "- Dual / CHAMP / crown are **not** NIFTY Calls.",
        "",
        "| Window | Morning LIVE n@hit | Afternoon (off) n@hit | If both on | Morning ~/yr |",
        "|---|---:|---:|---:|---:|",
    ]

    def fmt(s: Dict[str, Any]) -> str:
        if not s.get("n"):
            return "0"
        return f"{s['n']}@{s['hit_pct']}%"

    for wname, yrs in (("1y", 1), ("3y", 3), ("5y", 5)):
        m = in_win(morning, yrs)
        a = in_win(afternoon, yrs)
        # same-day both: still 2 calls (not skipped)
        combined = m + a
        sm, sa, sc = _stats(m), _stats(a), _stats(combined)
        per_yr = round(sm["n"] / yrs, 1) if sm["n"] else 0
        lines.append(f"| {wname} | {fmt(sm)} | {fmt(sa)} | {fmt(sc)} | {per_yr} |")
        report["windows"][wname] = {
            "morning": sm,
            "afternoon": sa,
            "combined_if_afternoon_on": sc,
            "calls_per_year_morning_live": per_yr,
            "morning_days": [r["d"] for r in m],
            "afternoon_days": [r["d"] for r in a],
            "overlap_days": sorted(set(r["d"] for r in m) & set(r["d"] for r in a)),
        }

    # Recent-session afternoon (original 60-session study window)
    aft60 = _stats_last_n_sessions(afternoon, days, 60)
    aft120 = _stats_last_n_sessions(afternoon, days, 120)
    aft250 = _stats_last_n_sessions(afternoon, days, 250)
    report["afternoon_recent"] = {"60": aft60, "120": aft120, "250": aft250}

    # Locked research expectation from report
    lines += [
        "",
        "## vs locked research file",
        "",
        "- Morning locked report: **1y 11@100% · 3y 26@100% · 5y 41@100%** (5m settle)",
        f"- Morning this run: "
        f"**1y {fmt(report['windows']['1y']['morning'])} · "
        f"3y {fmt(report['windows']['3y']['morning'])} · "
        f"5y {fmt(report['windows']['5y']['morning'])}**",
        "",
        "## Afternoon recent sessions (original study was 60)",
        "",
        f"- last 60: **{fmt(aft60)}**",
        f"- last 120: **{fmt(aft120)}**",
        f"- last 250: **{fmt(aft250)}**",
        "",
        "## Live module parity",
        "",
        f"- morning evaluate match sample: {live_check['morning_live_match']}",
        f"- afternoon evaluate match sample: {live_check['afternoon_live_match']}",
        f"- live constants: uplift≥{live_check['live_min_uplift']} body≥{live_check['live_body']} forbid_dn={live_check['live_forbid_dn']}",
        "",
        "## Meaning",
        "",
        "- Not zero calls — only accurate research lanes.",
        "- Combined = morning + afternoon (overlap days count as 2 calls).",
        "- Afternoon full 1y/3y/5y is weaker than the 60-session ~92% study — see recent table.",
        "",
        f"JSON: `{OUT_JSON}`",
        "",
    ]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("\n".join(lines))
    print("wrote", OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
