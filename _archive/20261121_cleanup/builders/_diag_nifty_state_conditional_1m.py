"""Test nifty_state_conditional on last ~1 month of sessions.

Needs prior-day memory (MIN_ANALOGS=30), so we warm on older 1m bars and
score only calls whose date falls in the last calendar month window.

  python -u prod_live/tests/builders/_diag_nifty_state_conditional_1m.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live" / "tests" / "builders"),
    str(ROOT / "app"),
    str(ROOT / "app" / "market"),
]
import path_setup  # noqa: F401,E402

from prod_live.logic.nifty_state_conditional import (  # noqa: E402
    COST_POINTS,
    MIN_ANALOGS,
    MIN_HIT_RATE,
    PROFILES,
    run,
    summarize,
)

TAPE = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_1m_kite.csv"
OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_CSV = OUT_DIR / "NIFTY_STATE_CONDITIONAL_1M.csv"
OUT_MD = OUT_DIR / "NIFTY_STATE_CONDITIONAL_1M.md"
OUT_JSON = OUT_DIR / "NIFTY_STATE_CONDITIONAL_1M.json"
WARM_SESSIONS = 750  # prior sessions so MIN_ANALOGS=30 states can fill
TEST_CALENDAR_DAYS = 31


def _to_raw(df: pd.DataFrame) -> List[dict]:
    frame = df.copy()
    if "datetime" in frame.columns:
        frame["datetime"] = pd.to_datetime(frame["datetime"])
        frame = frame.set_index("datetime")
    frame.index = pd.to_datetime(frame.index)
    if getattr(frame.index, "tz", None) is not None:
        frame.index = frame.index.tz_convert("Asia/Kolkata").tz_localize(None)
    frame = frame.rename(columns={c: str(c).lower() for c in frame.columns})
    if "volume" not in frame.columns:
        frame["volume"] = 0.0
    rows = []
    for ts, row in frame.iterrows():
        rows.append(
            {
                "datetime": ts.to_pydatetime(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume") or 0.0),
            }
        )
    return rows


def load_1m(warm_sessions: int = WARM_SESSIONS) -> Tuple[List[dict], str, List[date]]:
    """CSV warm history + fresh kite 1m tail (after token refresh)."""
    frame = pd.read_csv(TAPE, index_col=0, parse_dates=True)
    if getattr(frame.index, "tz", None) is not None:
        frame.index = frame.index.tz_convert("Asia/Kolkata")
    days_list = sorted({(ts.tz_convert("Asia/Kolkata") if getattr(ts, "tzinfo", None) else ts).date() for ts in frame.index})
    keep_days = days_list[-warm_sessions:]
    keep = set(keep_days)
    clip = frame[[(ts.tz_convert("Asia/Kolkata") if getattr(ts, "tzinfo", None) else ts).date() in keep for ts in frame.index]].copy()
    print(f"csv warm: {len(clip)} bars · {clip.index[0]} → {clip.index[-1]}", flush=True)
    source = "csv"

    try:
        import kite_auth
        import kite_data

        tok, terr = kite_auth.get_access_token(force_refresh=False)
        if not tok:
            print(f"kite token missing: {terr}", flush=True)
        else:
            df, err = kite_data.fetch_historical_candles(
                "NIFTY", "minute", days=60, keep_partial=True
            )
            if df is None or not len(df):
                print(f"kite 1m miss: {err}", flush=True)
            else:
                print(f"kite 1m: {len(df)} bars · {df.index[0]} → {df.index[-1]}", flush=True)
                kite = df.rename(columns={c: str(c).title() for c in df.columns})
                # align columns to csv
                for col in ("Open", "High", "Low", "Close", "Volume"):
                    if col not in kite.columns and col.lower() in df.columns:
                        kite[col] = df[col.lower()]
                if "Volume" not in kite.columns:
                    kite["Volume"] = 0.0
                kite = kite[["Open", "High", "Low", "Close", "Volume"]].copy()
                if getattr(kite.index, "tz", None) is None:
                    kite.index = kite.index.tz_localize("Asia/Kolkata")
                else:
                    kite.index = kite.index.tz_convert("Asia/Kolkata")
                if getattr(clip.index, "tz", None) is None:
                    clip.index = clip.index.tz_localize("Asia/Kolkata")
                else:
                    clip.index = clip.index.tz_convert("Asia/Kolkata")
                # drop overlapping timestamps from csv, append kite
                clip = clip[~clip.index.isin(kite.index)]
                clip = pd.concat([clip, kite]).sort_index()
                source = "csv+kite"
                print(f"merged: {len(clip)} bars · {clip.index[0]} → {clip.index[-1]}", flush=True)
    except Exception as exc:
        print(f"kite merge err: {exc} — csv only", flush=True)

    raw = _to_raw(clip)
    sessions = sorted({parse_bar_date(r) for r in raw})
    return raw, source, sessions


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw, source, session_dates = load_1m(WARM_SESSIONS)
    print(
        f"running state-conditional on {len(raw)} bars / {len(session_dates)} sessions…",
        flush=True,
    )
    if not session_dates:
        raise SystemExit("no bars")

    # Last ~1 calendar month of sessions
    end = session_dates[-1]
    start_cut = end - timedelta(days=TEST_CALENDAR_DAYS)
    month_sessions = [d for d in session_dates if d >= start_cut]
    month_set = {d.isoformat() for d in month_sessions}

    profile_stats = {}
    for profile in ("baseline", "accurate"):
        all_calls = run(raw, profile=profile)
        month_calls = [c for c in all_calls if c["date"] in month_set]
        profile_stats[profile] = {
            "all_calls": all_calls,
            "month_calls": month_calls,
            "warm": summarize(all_calls, cost_points=COST_POINTS),
            "month": summarize(month_calls, cost_points=COST_POINTS),
        }
        print(
            f"profile={profile} warm={profile_stats[profile]['warm']} "
            f"month={profile_stats[profile]['month']}",
            flush=True,
        )

    # Report focuses on accurate; baseline kept for comparison.
    all_calls = profile_stats["accurate"]["all_calls"]
    month_calls = profile_stats["accurate"]["month_calls"]
    stats_all = profile_stats["accurate"]["warm"]
    stats = profile_stats["accurate"]["month"]

    # Write CSV of month calls
    if month_calls:
        pd.DataFrame(month_calls).to_csv(OUT_CSV, index=False)
    else:
        pd.DataFrame(
            columns=[
                "date",
                "direction",
                "state",
                "entry",
                "stop",
                "target",
                "points",
                "reason",
            ]
        ).to_csv(OUT_CSV, index=False)

    by_day = Counter(c["date"] for c in month_calls)
    reasons = Counter(c.get("reason") for c in month_calls)
    states = Counter(c.get("state") for c in month_calls)

    acc = PROFILES["accurate"]
    base_m = profile_stats["baseline"]["month"]
    base_w = profile_stats["baseline"]["warm"]
    lines = [
        "# NIFTY state-conditional · last 1 month (accurate profile)",
        "",
        f"**Source:** `{source}` 1m · cost {COST_POINTS}",
        f"**Warm history:** last **{len(session_dates)}** sessions",
        f"**Test window:** {month_sessions[0]} → {month_sessions[-1]} "
        f"({len(month_sessions)} sessions)",
        "",
        "## Profiles",
        "",
        f"- `baseline`: analogs≥{MIN_ANALOGS} · hit≥{MIN_HIT_RATE} · max {PROFILES['baseline'].max_calls}/day",
        f"- `accurate`: analogs≥{acc.min_analogs} · hit≥{acc.min_hit_rate} · "
        f"max {acc.max_calls}/day (freeze/holdout pick `n22_h54_c1`)",
        "",
        "## Baseline vs accurate",
        "",
        "| Profile | Month N/hit/net | Warm N/hit/net |",
        "|---|---|---|",
        f"| baseline | {int(base_m.get('calls') or 0)}/{_pct(base_m.get('hit_rate'))}/"
        f"{_num(base_m.get('net_points'))} | {int(base_w.get('calls') or 0)}/"
        f"{_pct(base_w.get('hit_rate'))}/{_num(base_w.get('net_points'))} |",
        f"| **accurate** | **{int(stats.get('calls') or 0)}/{_pct(stats.get('hit_rate'))}/"
        f"{_num(stats.get('net_points'))}** | {int(stats_all.get('calls') or 0)}/"
        f"{_pct(stats_all.get('hit_rate'))}/{_num(stats_all.get('net_points'))} |",
        "",
        "## Accurate · last 1 month",
        "",
        f"- sessions in window: **{len(month_sessions)}**",
        f"- calls: **{stats.get('calls', 0)}**",
        f"- wins / losses: **{stats.get('wins', 0)} / {stats.get('losses', 0)}**",
        f"- hit rate: **{_pct(stats.get('hit_rate'))}**",
        f"- net points (after cost): **{_num(stats.get('net_points'))}**",
        f"- calls/day (on days with ≥1 call): **{_num(stats.get('calls_per_day'))}**",
        f"- exit reasons: `{dict(reasons)}`",
        "",
        "## Warm-window context (accurate)",
        "",
        f"- total calls: **{stats_all.get('calls', 0)}** · hit **{_pct(stats_all.get('hit_rate'))}** · "
        f"net **{_num(stats_all.get('net_points'))}**",
        "",
        "### Calls by day (test month · accurate)",
        "",
        "| Date | N | Sides | Net pts |",
        "|---|---:|---|---:|",
    ]
    for d in month_sessions:
        key = d.isoformat()
        day_calls = [c for c in month_calls if c["date"] == key]
        if not day_calls:
            lines.append(f"| {key} | 0 | — | 0 |")
            continue
        sides = ",".join(c["direction"] for c in day_calls)
        net = sum(float(c["points"]) - COST_POINTS for c in day_calls)
        lines.append(f"| {key} | {len(day_calls)} | {sides} | {net:.1f} |")

    lines += [
        "",
        "### Call detail",
        "",
        "| Date | Side | State | Signal | Entry | Stop | Target | Exit | Pts | Analogs | Hit | Reason |",
        "|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---|",
    ]
    for c in month_calls:
        lines.append(
            f"| {c['date']} | {c['direction']} | `{c['state']}` | "
            f"{_hm(c['signal_time'])} | {float(c['entry']):.2f} | "
            f"{float(c['stop']):.2f} | {float(c['target']):.2f} | "
            f"{_hm(c['exit_time'])} | {float(c['points']):.1f} | "
            f"{c['analog_count']} | {c['analog_hit_rate']} | {c['reason']} |"
        )

    lines += [
        "",
        "### Top states",
        "",
    ]
    for state, n in states.most_common(12):
        lines.append(f"- `{state}` × {n}")
    lines += ["", f"CSV: `{OUT_CSV.relative_to(ROOT).as_posix()}`", ""]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    payload: Dict[str, Any] = {
        "source": source,
        "test_start": month_sessions[0].isoformat(),
        "test_end": month_sessions[-1].isoformat(),
        "sessions": len(month_sessions),
        "profiles": {
            "baseline": {
                "month": profile_stats["baseline"]["month"],
                "warm": profile_stats["baseline"]["warm"],
            },
            "accurate": {"month": stats, "warm": stats_all},
        },
        "month_summary": stats,
        "warm_summary": stats_all,
        "calls_per_day": dict(by_day),
        "reasons": dict(reasons),
        "calls": month_calls,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "baseline_month": profile_stats["baseline"]["month"],
                "accurate_month": stats,
                "sessions": len(month_sessions),
            },
            indent=2,
        )
    )
    print(f"wrote {OUT_MD}")


def parse_bar_date(raw: dict) -> date:
    dt = raw["datetime"]
    if hasattr(dt, "date"):
        return dt.date()
    return pd.Timestamp(dt).date()


def _pct(v: Any) -> str:
    if v is None:
        return "n/a"
    return f"{100.0 * float(v):.1f}%"


def _num(v: Any) -> str:
    if v is None:
        return "n/a"
    return f"{float(v):.2f}"


def _hm(iso: str) -> str:
    try:
        return pd.Timestamp(iso).strftime("%H:%M")
    except Exception:
        return str(iso)[:16]


if __name__ == "__main__":
    main()
