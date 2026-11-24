"""Test refined nifty_orb30_vwap_fut (description-aligned).

Last 10 sessions primary + 20/40/60 context. Structure only (no prob cols).

  python -u prod_live/tests/builders/_diag_nifty_orb30_vwap_last10d.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live" / "tests" / "builders"),
    str(ROOT / "app"),
    str(ROOT / "app" / "market"),
]
import path_setup  # noqa: F401,E402

from prod_live.logic.nifty_orb30_vwap_fut import (  # noqa: E402
    MAX_EXTENSION,
    MAX_WIDTH,
    MIN_WIDTH,
    STOP_POINTS,
    TARGET_POINTS,
    _resolve_entry,
    generate_calls,
    prepare_bars,
    summarize,
)

TAPE = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_CSV = OUT_DIR / "NIFTY_ORB30_VWAP_FUT_LAST10D.csv"
OUT_MD = OUT_DIR / "NIFTY_ORB30_VWAP_FUT_LAST10D.md"
OUT_JSON = OUT_DIR / "NIFTY_ORB30_VWAP_FUT_LAST10D.json"
COST = 1.0
WINDOWS = (10, 20, 40, 60)


def _to_rule_frame(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")
    df.index = pd.to_datetime(df.index)
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_convert("Asia/Kolkata").tz_localize(None)
    df = df.rename(columns={c: str(c).lower() for c in df.columns})
    if "volume" not in df.columns:
        df["volume"] = 0.0
    keep = ["open", "high", "low", "close", "volume"]
    missing = [c for c in keep if c not in df.columns]
    if missing:
        raise ValueError(f"5m frame missing {missing}; got {list(df.columns)}")
    return prepare_bars(df[keep])


def load_5m(days: int = 100) -> tuple[pd.DataFrame, str]:
    try:
        import kite_data

        df, err = kite_data.fetch_historical_candles(
            "NIFTY", "5minute", days=days, keep_partial=True
        )
        if df is not None and len(df):
            print(f"kite 5m: {len(df)} bars · {df.index[0]} → {df.index[-1]}", flush=True)
            return _to_rule_frame(df), "kite"
        print(f"kite miss: {err} — CSV fallback", flush=True)
    except Exception as exc:
        print(f"kite err: {exc} — CSV fallback", flush=True)

    raw = pd.read_csv(TAPE, index_col=0, parse_dates=True)
    print(f"csv 5m: {len(raw)} bars · {raw.index[0]} → {raw.index[-1]}", flush=True)
    return _to_rule_frame(raw), "csv"


def last_n_sessions(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    days = sorted(frame.index.normalize().unique())
    keep_days = days[-n:]
    mask = frame.index.normalize().isin(keep_days)
    out = frame.loc[mask].copy()
    print(
        f"sessions: {len(keep_days)} · {keep_days[0].date()} → {keep_days[-1].date()}",
        flush=True,
    )
    return out


def _fmt_stat(v: Any, *, pct: bool = False) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "n/a"
    if pct and isinstance(v, (int, float)):
        return f"{100.0 * float(v):.1f}%"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def self_check_entry_stop() -> List[str]:
    """Sanity: entry at level + stop through level."""
    notes: List[str] = []
    # Buy: next bar trades ORH from below → at_level; stop = ORH-12
    bar = pd.Series({"open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0})
    entry, mode, fail = _resolve_entry("buy", 101.0, bar)
    assert fail is None and mode == "at_level" and entry == 101.0
    notes.append(f"buy at_level ok entry={entry} mode={mode}")

    # Buy: open 5 past level → next_trade
    bar2 = pd.Series({"open": 106.0, "high": 108.0, "low": 105.5, "close": 107.0})
    entry2, mode2, fail2 = _resolve_entry("buy", 101.0, bar2)
    assert fail2 is None and mode2 == "next_trade" and entry2 == 106.0
    notes.append(f"buy next_trade ok entry={entry2}")

    # Buy: open 15 past → reject
    bar3 = pd.Series({"open": 116.0, "high": 118.0, "low": 115.0, "close": 117.0})
    entry3, mode3, fail3 = _resolve_entry("buy", 101.0, bar3)
    assert entry3 is None and fail3 == "entry_moved_too_far_from_level"
    notes.append(f"buy chase reject ok ({fail3})")

    # Sell mirror at_level
    bar4 = pd.Series({"open": 100.0, "high": 101.0, "low": 95.0, "close": 96.0})
    entry4, mode4, fail4 = _resolve_entry("sell", 99.0, bar4)
    assert fail4 is None and mode4 == "at_level" and entry4 == 99.0
    stop_buy = 101.0 - STOP_POINTS
    stop_sell = 99.0 + STOP_POINTS
    notes.append(
        f"stops through level: buy_stop={stop_buy} sell_stop={stop_sell} "
        f"(SL={STOP_POINTS} T1={TARGET_POINTS} ext={MAX_EXTENSION} "
        f"width={MIN_WIDTH}-{MAX_WIDTH})"
    )
    return notes


def run_window(bars: pd.DataFrame, n: int) -> Dict[str, Any]:
    clip = last_n_sessions(bars, n)
    calls = generate_calls(clip, require_probability=False)
    stats = summarize(calls, cost_points_per_call=COST)
    reasons = calls["reason"].value_counts().to_dict()
    return {
        "n": n,
        "stats": {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in stats.items()},
        "reasons": reasons,
        "calls": calls,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checks = self_check_entry_stop()
    for line in checks:
        print("check:", line, flush=True)

    bars, source = load_5m(days=100)
    results = {n: run_window(bars, n) for n in WINDOWS}
    primary = results[10]
    calls = primary["calls"]
    stats = primary["stats"]
    calls.to_csv(OUT_CSV, index=False)

    lines = [
        "# NIFTY ORB30 VWAP futures · refined (description-aligned)",
        "",
        f"**Source:** `{source}` 5m · **cost:** {COST} pt · **probability gate:** off (no model cols on tape)",
        "",
        "## Refactors vs prior code",
        "",
        "1. **Entry at the level** — fill ORH/ORL when the next bar still trades it "
        "(`at_level`); else next trade only if ≤10 pts past (`next_trade`).",
        "2. **Stop through the level** — buy stop = ORH−12, sell stop = ORL+12 "
        "(not entry±12).",
        "3. **Target from fill** — entry±20.",
        "4. **Failed fill ≠ day consumed** — keep scanning for a later valid break "
        "(still one live trade; no reverse after a stop).",
        "5. **VIX expected range** — annotated when `india_vix` present "
        "(price × VIX/100 / √252); width gate stays frozen at 30–90.",
        "",
        "## Self-check",
        "",
    ]
    lines += [f"- {c}" for c in checks]
    lines += [
        "",
        "## Last 10 sessions (primary)",
        "",
        f"- sessions: **{int(stats['sessions'])}**",
        f"- calls: **{int(stats['calls'])}**",
        f"- wins / losses: **{int(stats['wins'])} / {int(stats['losses'])}**",
        f"- hit rate: **{_fmt_stat(stats['hit_rate'], pct=True)}**",
        f"- avg win / avg loss: **{_fmt_stat(stats.get('average_win'))} / {_fmt_stat(stats.get('average_loss'))}**",
        f"- net points (after cost): **{_fmt_stat(stats['net_points'])}**",
        f"- no-call days: **{int(stats.get('no_call_days') or 0)}**",
        f"- reasons: `{primary['reasons']}`",
        "",
        "### Day-by-day",
        "",
        "| Date | Status | Side | Width | Mode | Signal | Entry | Stop | Target | Exit | Pts | Reason |",
        "|---|---|---|---:|---|---|---:|---:|---:|---|---:|---|",
    ]
    for _, row in calls.iterrows():
        d = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
        side = row["direction"] or "—"
        width = f"{row['opening_width']:.1f}" if pd.notna(row["opening_width"]) else "—"
        mode = row["entry_mode"] if pd.notna(row.get("entry_mode")) else "—"
        sig = (
            pd.Timestamp(row["signal_time"]).strftime("%H:%M")
            if pd.notna(row["signal_time"])
            else "—"
        )
        ent = f"{row['entry']:.2f}" if pd.notna(row["entry"]) else "—"
        stop = f"{row['stop']:.2f}" if pd.notna(row["stop"]) else "—"
        tgt = f"{row['target']:.2f}" if pd.notna(row["target"]) else "—"
        xt = (
            pd.Timestamp(row["exit_time"]).strftime("%H:%M")
            if pd.notna(row["exit_time"])
            else "—"
        )
        pts = f"{row['points']:.1f}" if pd.notna(row["points"]) else "—"
        lines.append(
            f"| {d} | {row['status']} | {side} | {width} | {mode} | {sig} | "
            f"{ent} | {stop} | {tgt} | {xt} | {pts} | {row['reason']} |"
        )

    lines += [
        "",
        "## Context windows (same frozen rule)",
        "",
        "| Window | Calls | W/L | Hit | Avg win | Avg loss | Net | No-call |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for n in WINDOWS:
        s = results[n]["stats"]
        lines.append(
            f"| last {n} | {int(s['calls'])} | {int(s['wins'])}/{int(s['losses'])} | "
            f"{_fmt_stat(s['hit_rate'], pct=True)} | {_fmt_stat(s.get('average_win'))} | "
            f"{_fmt_stat(s.get('average_loss'))} | {_fmt_stat(s['net_points'])} | "
            f"{int(s.get('no_call_days') or 0)} |"
        )

    # Taken calls detail for last 40
    taken40 = results[40]["calls"]
    taken40 = taken40[taken40["entry"].notna()]
    if len(taken40):
        lines += [
            "",
            "### Taken calls · last 40",
            "",
            "| Date | Side | Width | Mode | Entry | Stop | Target | Status | Pts |",
            "|---|---|---:|---|---:|---:|---:|---|---:|",
        ]
        for _, row in taken40.iterrows():
            d = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
            lines.append(
                f"| {d} | {row['direction']} | {row['opening_width']:.1f} | "
                f"{row['entry_mode']} | {row['entry']:.2f} | {row['stop']:.2f} | "
                f"{row['target']:.2f} | {row['status']} | {row['points']:.1f} |"
            )

    lines += [
        "",
        f"Module: `prod_live/logic/nifty_orb30_vwap_fut.py`",
        f"CSV: `{OUT_CSV.relative_to(ROOT).as_posix()}`",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    payload = {
        "source": source,
        "cost_points": COST,
        "require_probability": False,
        "refactors": [
            "entry_at_level_or_next_trade_within_10",
            "stop_through_level",
            "target_from_entry",
            "continue_after_failed_fill",
            "vix_expected_range_annotate",
        ],
        "self_check": checks,
        "windows": {
            str(n): {
                "stats": results[n]["stats"],
                "reasons": results[n]["reasons"],
            }
            for n in WINDOWS
        },
        "last10_calls": json.loads(calls.to_json(orient="records", date_format="iso")),
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["windows"], indent=2), flush=True)
    print(f"wrote {OUT_MD}", flush=True)


if __name__ == "__main__":
    main()
