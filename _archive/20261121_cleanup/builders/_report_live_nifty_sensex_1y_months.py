"""Replay CURRENT live desks · last 1y · monthly accuracy through today.

NIFTY live:
  - CHAMP_PLUS_T30SL30_CAP6 (±30 Cap6) — primary Calls book (FINAL)
  - Cap4 backup compare when present
  - Morning strong L5_u70_b80 (additive; afternoon OFF)

SENSEX live:
  - SENSEX_DUAL_FB_BF20_T50 (±50) — primary Calls book

  python -u prod_live/tests/builders/_report_live_nifty_sensex_1y_months.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app"), str(ROOT / "app" / "fno")]

OUT_MD = ROOT / "prod_live" / "reports" / "1y" / "LIVE_NIFTY_SENSEX_1Y_MONTHLY.md"
OUT_JSON = ROOT / "prod_live" / "reports" / "1y" / "LIVE_NIFTY_SENSEX_1Y_MONTHLY.json"

NIFTY_CHAMP = ROOT / "prod_live" / "holding_accurate" / "champion_plus" / "t30_sl30_5y_calls.json"
NIFTY_CHAMP_CAP4 = (
    ROOT / "prod_live" / "holding_accurate" / "champion_plus" / "t30_sl30_5y_calls_cap4_backup.json"
)
SENSEX_CHAMP = (
    ROOT / "prod_live" / "holding_accurate" / "sensex_final" / "champ_plus_t50_sl50_calls.json"
)
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_kite.csv"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"

TODAY = date.today().isoformat()  # 2026-11-20 expected
START_1Y = (pd.Timestamp(TODAY) - pd.DateOffset(years=1)).date().isoformat()


def _win(r: dict) -> Optional[bool]:
    if r.get("win") is True:
        return True
    if r.get("win") is False:
        return False
    if r.get("native_win") is True:
        return True
    if r.get("native_win") is False:
        return False
    o = str(r.get("outcome") or "")
    if o in ("t1_before_sl", "win"):
        return True
    if o in ("sl_before_t1", "same_bar_both", "loss"):
        return False
    return None


def _pts(r: dict, default_win: float, default_loss: float) -> float:
    if r.get("points") is not None:
        try:
            return float(r["points"])
        except (TypeError, ValueError):
            pass
    w = _win(r)
    if w is True:
        return default_win
    if w is False:
        return default_loss
    return 0.0


def _stats(rows: List[dict], *, t_pts: float, sl_pts: float) -> Dict[str, Any]:
    closed = []
    for r in rows:
        w = _win(r)
        if w is None:
            continue
        closed.append((r, w, _pts(r, t_pts, -sl_pts)))
    n = len(closed)
    wins = sum(1 for _, w, _ in closed if w)
    losses = n - wins
    pts = sum(p for _, _, p in closed)
    return {
        "n": n,
        "wins": wins,
        "losses": losses,
        "hit_pct": round(100.0 * wins / n, 2) if n else None,
        "points": round(pts, 1),
        "open_or_unknown": len(rows) - n,
        "raw": len(rows),
    }


def _monthly(rows: List[dict], *, t_pts: float, sl_pts: float, sessions_by_month: Dict[str, int]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        d = str(r.get("day") or "")[:10]
        if len(d) >= 7:
            by[d[:7]].append(r)
    out = []
    for m in sorted(by.keys()):
        st = _stats(by[m], t_pts=t_pts, sl_pts=sl_pts)
        days = sorted({str(r.get("day"))[:10] for r in by[m]})
        sess = int(sessions_by_month.get(m) or 0)
        quiet = max(0, sess - len(days)) if sess else None
        out.append(
            {
                "month": m,
                **st,
                "days_with_call": len(days),
                "sessions": sess or None,
                "quiet_days": quiet,
                "avg_calls_per_session": round(st["n"] / sess, 2) if sess else None,
            }
        )
    return out


def _load_nifty_champ(start: str, end: str, path: Optional[Path] = None) -> List[dict]:
    p = path or NIFTY_CHAMP
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else raw.get("calls") or []
    out = []
    for r in rows:
        d = str(r.get("day") or "")[:10]
        if start <= d <= end:
            rr = dict(r)
            if not rr.get("decision"):
                rr["decision"] = rr.get("side")
            out.append(rr)
    return out


def _load_sensex(start: str, end: str) -> List[dict]:
    blob = json.loads(SENSEX_CHAMP.read_text(encoding="utf-8"))
    rows = blob.get("calls") or []
    out = []
    for r in rows:
        d = str(r.get("day") or "")[:10]
        if start <= d <= end:
            out.append(dict(r))
    return out


def _load_tape_sessions() -> Tuple[List[str], Dict[str, int]]:
    if not TAPE15.exists():
        return [], {}
    df = pd.read_csv(TAPE15, index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("Asia/Kolkata")
    else:
        df.index = df.index.tz_convert("Asia/Kolkata")
    days = sorted({str(t.date()) for t in df.index})
    by_m: Dict[str, int] = defaultdict(int)
    for d in days:
        by_m[d[:7]] += 1
    return days, dict(by_m)


def _morning_l5(start: str, end: str) -> List[dict]:
    """Current live morning L5_u70_b80 on tape (same as locked research walker)."""
    if not TAPE15.exists() or not TAPE5.exists():
        return []
    import importlib.util

    path = ROOT / "prod_live" / "tests" / "builders" / "_compare_nifty_live_vs_research_windows.py"
    spec = importlib.util.spec_from_file_location("cmp_nifty_windows", path)
    cmp = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(cmp)

    bars15 = cmp._load(TAPE15)
    bars5 = cmp._load(TAPE5)
    bars15["__d"] = [cmp._day(t) for t in bars15.index]
    bars5["__d"] = [cmp._day(t) for t in bars5.index]
    g15 = {d: g.drop(columns="__d") for d, g in bars15.groupby("__d", sort=True)}
    g5 = {d: g.drop(columns="__d") for d, g in bars5.groupby("__d", sort=True)}
    out = []
    for d in sorted(g15.keys()):
        if d < start or d > end:
            continue
        sess5 = g5.get(d)
        if sess5 is None:
            continue
        r = cmp.morning_day(g15[d], sess5)
        if not r:
            continue
        w = r.get("out")
        out.append(
            {
                "day": r["d"],
                "hm": r.get("fill") or r.get("sig"),
                "decision": "BUY",
                "side": "BUY",
                "track": "morning_L5_u70_b80",
                "desk": "NIFTY_MORNING_L5_U70_B80",
                "entry": r.get("entry"),
                "win": True if w == "win" else (False if w == "loss" else None),
                "outcome": w,
                "points": 30.0 if w == "win" else (-30.0 if w == "loss" else 0.0),
                "uplift": r.get("uplift"),
            }
        )
    return out


def _fmt(st: Dict[str, Any]) -> str:
    if not st.get("n"):
        return "0"
    return f"{st['n']} @ {st['hit_pct']}%"


def main() -> int:
    end = TODAY
    start = START_1Y
    sess_days, sess_by_m = _load_tape_sessions()
    sess_1y = [d for d in sess_days if start <= d <= end]

    print(f"window {start} → {end} · today={TODAY}")
    print(f"NIFTY tape sessions in window: {len(sess_1y)}")

    nifty_champ = _load_nifty_champ(start, end)
    nifty_cap4 = _load_nifty_champ(start, end, NIFTY_CHAMP_CAP4) if NIFTY_CHAMP_CAP4.exists() else []
    sensex = _load_sensex(start, end)
    morning = _morning_l5(start, end)
    print(
        f"loaded champ_cap6={len(nifty_champ)} cap4_backup={len(nifty_cap4)} "
        f"morning={len(morning)} sensex={len(sensex)}"
    )

    n_champ = _stats(nifty_champ, t_pts=30.0, sl_pts=30.0)
    n_cap4 = _stats(nifty_cap4, t_pts=30.0, sl_pts=30.0) if nifty_cap4 else None
    n_morn = _stats(morning, t_pts=30.0, sl_pts=30.0)
    # Combined NIFTY listing set: champ ∪ morning (distinct day+hm)
    seen = {(str(r.get("day"))[:10], str(r.get("hm") or "")[:5], str(r.get("decision") or r.get("side") or "").upper()) for r in nifty_champ}
    nifty_combined = list(nifty_champ)
    for r in morning:
        k = (str(r.get("day"))[:10], str(r.get("hm") or "")[:5], "BUY")
        if k not in seen:
            nifty_combined.append(r)
            seen.add(k)
    n_comb = _stats(nifty_combined, t_pts=30.0, sl_pts=30.0)
    s_st = _stats(sensex, t_pts=50.0, sl_pts=50.0)

    n_months = _monthly(nifty_champ, t_pts=30.0, sl_pts=30.0, sessions_by_month=sess_by_m)
    n4_months = (
        _monthly(nifty_cap4, t_pts=30.0, sl_pts=30.0, sessions_by_month=sess_by_m)
        if nifty_cap4
        else []
    )
    m_months = _monthly(morning, t_pts=30.0, sl_pts=30.0, sessions_by_month=sess_by_m)
    c_months = _monthly(nifty_combined, t_pts=30.0, sl_pts=30.0, sessions_by_month=sess_by_m)
    s_months = _monthly(sensex, t_pts=50.0, sl_pts=50.0, sessions_by_month={})

    # Sensex session coverage from its own days
    s_days = sorted({str(r.get("day"))[:10] for r in sensex})
    s_by_m: Dict[str, int] = defaultdict(int)
    # approximate sessions = unique call days is undercount; use call-day set as proxy cov
    for d in s_days:
        s_by_m[d[:7]] += 1
    for row in s_months:
        m = row["month"]
        row["days_with_call"] = s_by_m.get(m, row["days_with_call"])

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "window": {"start": start, "end": end},
        "live_desks": {
            "nifty_primary": "CHAMP_PLUS_T30SL30_CAP6",
            "nifty_prior": "CHAMP_PLUS_T30SL30_CAP4",
            "nifty_additive": "NIFTY_MORNING_L5_U70_B80",
            "nifty_afternoon": "OFF",
            "sensex_primary": "SENSEX_DUAL_FB_BF20_T50",
            "p2f_p2g": "annotate tags only (do not change listing set)",
        },
        "nifty": {
            "champ_plus_cap6": n_champ,
            "champ_plus_cap4_prior": n_cap4,
            "morning_l5": n_morn,
            "combined_listing": n_comb,
            "monthly_champ_cap6": n_months,
            "monthly_champ_cap4": n4_months,
            "monthly_morning": m_months,
            "monthly_combined": c_months,
            "tape_sessions": len(sess_1y),
            "delta_vs_cap4": (
                {
                    "delta_n": n_champ["n"] - n_cap4["n"],
                    "hit_cap6": n_champ["hit_pct"],
                    "hit_cap4": n_cap4["hit_pct"],
                }
                if n_cap4
                else None
            ),
        },
        "sensex": {
            "desk": s_st,
            "monthly": s_months,
            "book_meta_desk": "SENSEX_DUAL_FB_BF20_T50",
            "brackets": {"sl": 50, "t1": 50},
        },
    }

    lines = [
        "# Live NIFTY + SENSEX · last 1y monthly (current desks)",
        "",
        f"**Generated:** `{report['generated_at']}`",
        f"**Window:** `{start}` → `{end}` (through today)",
        "",
        "## Live desks under test",
        "",
        "| Index | Desk | Brackets | Role |",
        "|---|---|---|---|",
        "| **NIFTY** | `CHAMP_PLUS_T30SL30_CAP6` | ±30 · Cap6 | Primary Calls (FINAL) |",
        "| **NIFTY** | Cap4 prior (backup) | ±30 · Cap4 | Compare only |",
        "| **NIFTY** | `L5_u70_b80` morning strong | ±30 · Cap1 | Additive (does not block CHAMP) |",
        "| **NIFTY** | Afternoon thrust | — | **OFF** (does not block) |",
        "| **NIFTY** | P2F / P2G | — | Accuracy tags / UI merge only |",
        "| **SENSEX** | `SENSEX_DUAL_FB_BF20_T50` | ±50 | Primary Calls |",
        "",
        "## Totals (1y)",
        "",
        "| Book | N | Hit% | W/L | Points |",
        "|---|---:|---:|---|---:|",
        f"| NIFTY CHAMP_PLUS Cap6 (LIVE) | {n_champ['n']} | **{n_champ['hit_pct']}%** | {n_champ['wins']}/{n_champ['losses']} | {n_champ['points']} |",
    ]
    if n_cap4:
        lines.append(
            f"| NIFTY CHAMP_PLUS Cap4 (prior) | {n_cap4['n']} | **{n_cap4['hit_pct']}%** | "
            f"{n_cap4['wins']}/{n_cap4['losses']} | {n_cap4['points']} |"
        )
        lines.append(
            f"| Cap6 − Cap4 | **{n_champ['n'] - n_cap4['n']:+d}** | "
            f"{n_champ['hit_pct']}% vs {n_cap4['hit_pct']}% | — | "
            f"{n_champ['points'] - n_cap4['points']:+.1f} |"
        )
    lines += [
        f"| NIFTY morning L5 | {n_morn['n']} | **{n_morn['hit_pct']}%** | {n_morn['wins']}/{n_morn['losses']} | {n_morn['points']} |",
        f"| NIFTY combined (Cap6 ∪ morning) | {n_comb['n']} | **{n_comb['hit_pct']}%** | {n_comb['wins']}/{n_comb['losses']} | {n_comb['points']} |",
        f"| SENSEX DUAL_FB_BF20_T50 | {s_st['n']} | **{s_st['hit_pct']}%** | {s_st['wins']}/{s_st['losses']} | {s_st['points']} |",
        "",
        f"NIFTY tape sessions in window: **{len(sess_1y)}** · CHAMP Cap6 coverage days: "
        f"**{len({str(r.get('day'))[:10] for r in nifty_champ})}**",
        "",
        "## NIFTY CHAMP_PLUS Cap6 (LIVE) — per month",
        "",
        "| Month | Sess | Calls | Hit% | W/L | Pts | Days w/ call | Quiet |",
        "|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for row in n_months:
        lines.append(
            f"| {row['month']} | {row.get('sessions') or '—'} | {row['n']} | **{row['hit_pct']}%** | "
            f"{row['wins']}/{row['losses']} | {row['points']} | {row['days_with_call']} | "
            f"{row['quiet_days'] if row['quiet_days'] is not None else '—'} |"
        )

    if n4_months:
        by4 = {r["month"]: r for r in n4_months}
        lines += [
            "",
            "## Cap6 vs Cap4 — per month",
            "",
            "| Month | Cap4 N | Cap4 Hit% | Cap6 N | Cap6 Hit% | ΔN |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        months = sorted(set(list(by4.keys()) + [r["month"] for r in n_months]))
        by6 = {r["month"]: r for r in n_months}
        for m in months:
            a = by4.get(m) or {"n": 0, "hit_pct": None}
            b = by6.get(m) or {"n": 0, "hit_pct": None}
            lines.append(
                f"| {m} | {a['n']} | {a['hit_pct']}% | {b['n']} | **{b['hit_pct']}%** | "
                f"{b['n'] - a['n']:+d} |"
            )

    lines += [
        "",
        "## NIFTY morning L5_u70_b80 — per month",
        "",
        "| Month | Calls | Hit% | W/L | Pts |",
        "|---|---:|---:|---|---:|",
    ]
    for row in m_months:
        lines.append(
            f"| {row['month']} | {row['n']} | **{row['hit_pct']}%** | {row['wins']}/{row['losses']} | {row['points']} |"
        )
    if not m_months:
        lines.append("| — | 0 | — | — | — |")

    lines += [
        "",
        "## NIFTY combined (CHAMP ∪ morning) — per month",
        "",
        "| Month | Calls | Hit% | W/L | Pts |",
        "|---|---:|---:|---|---:|",
    ]
    for row in c_months:
        lines.append(
            f"| {row['month']} | {row['n']} | **{row['hit_pct']}%** | {row['wins']}/{row['losses']} | {row['points']} |"
        )

    lines += [
        "",
        "## SENSEX DUAL_FB_BF20_T50 — per month",
        "",
        "| Month | Calls | Hit% | W/L | Pts | Days w/ call |",
        "|---|---:|---:|---|---:|---:|",
    ]
    for row in s_months:
        lines.append(
            f"| {row['month']} | {row['n']} | **{row['hit_pct']}%** | {row['wins']}/{row['losses']} | "
            f"{row['points']} | {row['days_with_call']} |"
        )

    lines += [
        "",
        "## Accuracy notes",
        "",
        "- NIFTY CHAMP_PLUS **Cap6 FINAL** settled at **±30** from held live book `t30_sl30_5y_calls.json`.",
        "- Cap4 prior kept at `t30_sl30_5y_calls_cap4_backup.json` for compare.",
        "- NIFTY morning settled at **±30** on 5m after OR+5 fill (live L5_u70_b80 rule).",
        "- SENSEX settled at **±50** from held live book `champ_plus_t50_sl50_calls.json` "
        f"(desk `{report['sensex']['book_meta_desk']}`).",
        "- P2F/P2G do not add separate entries; they tag the same CHAMP fires on the UI.",
        "- Afternoon thrust disabled — excluded from this report.",
        "",
        f"JSON: `{OUT_JSON}`",
        "",
    ]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("\n".join(lines[:80]))
    print("...")
    print("wrote", OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
