"""SENSEX live logic · last ~2 months · per-month report.

Live path (same shape as NIFTY, Sensex books):
  SUPPRESS_DUAL_LIST=1 · dual proven/champion scores but does NOT list
  Board fill: SENSEX_CHAMP_PLUS_T100SL100_CAP3 (±100 · Cap3) via ensure_session_calls

Steps:
  1) Pull SENSEX 5m + 15m from Kite (~70d) · merge into research tapes
  2) Walk each closed 15m bar · sensex dual.evaluate → CHAMP fill
  3) Path-score ±100 on 5m · report overall + by calendar month

  python -u prod_live/tests/builders/_replay_sensex_live_logic_2m.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
    str(ROOT / "prod_live"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
os.environ.setdefault("SUPPRESS_DUAL_LIST", "1")
os.environ.setdefault("USE_DUAL_TRACK", "1")
os.environ.setdefault("ENABLE_SENSEX_FINAL_LIVE", "1")
os.environ.setdefault("ENABLE_EXTRA_TREES_SINGLE", "0")
import path_setup  # noqa: F401,E402

import kite_data  # noqa: E402
import sensex_live_dual_track as dual  # noqa: E402
from prod_live.logic import sensex_final_live as sx  # noqa: E402
from research_bn_sensex_final_brackets import score_one  # noqa: E402


def build_bar_index(bars: pd.DataFrame) -> Dict[Tuple[str, str], int]:
    ix: Dict[Tuple[str, str], int] = {}
    for i, ts in enumerate(bars.index):
        d = str(pd.Timestamp(ts).date())
        hm = f"{pd.Timestamp(ts).hour:02d}:{pd.Timestamp(ts).minute:02d}"
        ix[(d, hm)] = i
    return ix

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "SENSEX_LIVE_LOGIC_2M.md"
OUT_JSON = OUT / "SENSEX_LIVE_LOGIC_2M.json"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_5m_kite.csv"
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_15m_kite.csv"
LEDGER = sx._LIVE_LEDGER
LEDGER_BAK = LEDGER.with_suffix(".json.bak_2m_replay")

END = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
START = (pd.Timestamp(END) - timedelta(days=62)).strftime("%Y-%m-%d")
SL_PTS = float(sx.BRACKETS["sl"])
T1_PTS = float(sx.BRACKETS["target"])
CAP = int(sx.CAP)


def _norm_idx(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
        if "date" in work.columns:
            work["date"] = pd.to_datetime(work["date"])
            work = work.set_index("date")
        else:
            work.index = pd.to_datetime(work.index)
    if work.index.tz is None:
        work.index = work.index.tz_localize("Asia/Kolkata")
    else:
        work.index = work.index.tz_convert("Asia/Kolkata")
    work = work.rename(columns={c: str(c).title() for c in work.columns})
    for need in ("Open", "High", "Low", "Close"):
        if need not in work.columns:
            for c in list(work.columns):
                if str(c).lower() == need.lower():
                    work = work.rename(columns={c: need})
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in work.columns]
    work = work[cols].sort_index()
    work = work[~work.index.duplicated(keep="last")]
    hm = work.index.strftime("%H:%M")
    return work[(hm >= "09:15") & (hm <= "15:30")]


def pull_kite(interval: str, days: int = 70) -> pd.DataFrame:
    df, err = kite_data.fetch_historical_candles(
        "SENSEX", interval=interval, days=days, keep_partial=True
    )
    if err or df is None or df.empty:
        raise RuntimeError(f"kite {interval} failed: {err}")
    return _norm_idx(df)


def merge_tape(path: Path, fresh: pd.DataFrame) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    bak = path.with_suffix(path.suffix + f".bak_{int(time.time())}")
    old = None
    if path.exists():
        shutil.copy2(path, bak)
        try:
            old = _norm_idx(pd.read_csv(path, index_col=0, parse_dates=True))
        except Exception:
            old = None
    if old is not None and len(old):
        keep = old[old.index.strftime("%Y-%m-%d") < START]
        merged = pd.concat([keep, fresh[fresh.index.strftime("%Y-%m-%d") >= START]])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    else:
        merged = fresh
    out = merged.copy()
    out.index = out.index.tz_convert("Asia/Kolkata")
    out2 = out.copy()
    out2.index = out2.index.tz_localize(None)
    out2.to_csv(path)
    return {
        "path": str(path),
        "n": len(merged),
        "min": str(merged.index.min()),
        "max": str(merged.index.max()),
    }


def hit(rows: List[dict]) -> Optional[float]:
    known = [r for r in rows if r.get("win") is not None]
    if not known:
        return None
    return round(100.0 * sum(1 for r in known if r.get("win")) / len(known), 2)


def month_stats(rows: List[dict]) -> Dict[str, Any]:
    known = [r for r in rows if r.get("win") is not None]
    wins = sum(1 for r in known if r.get("win") is True)
    losses = sum(1 for r in known if r.get("win") is False)
    opens = sum(1 for r in rows if r.get("win") is None)
    return {
        "n": len(rows),
        "settled": len(known),
        "hit_pct": hit(rows),
        "wins": wins,
        "losses": losses,
        "open": opens,
        "by_side": {
            s: sum(1 for r in rows if str(r.get("decision") or r.get("side") or "").upper() == s)
            for s in ("BUY", "SELL")
            if any(str(r.get("decision") or r.get("side") or "").upper() == s for r in rows)
        },
        "by_track": {
            t: sum(1 for r in rows if str(r.get("track") or "") == t)
            for t in sorted({str(r.get("track") or "champion") for r in rows})
        },
    }


def main() -> int:
    t0 = time.time()
    print(f"SENSEX live 2m · {START} → {END} · desk {sx.DESK_CHAMP} ±{SL_PTS}/{T1_PTS} Cap{CAP}", flush=True)
    print("Pull Kite 5m/15m…", flush=True)
    bars5 = pull_kite("5minute", days=70)
    bars15 = pull_kite("15minute", days=70)
    bars5 = bars5[bars5.index.strftime("%Y-%m-%d") >= START]
    bars15 = bars15[bars15.index.strftime("%Y-%m-%d") >= START]
    print(f"  kite 5m n={len(bars5)} {bars5.index.min()} → {bars5.index.max()}", flush=True)
    print(f"  kite 15m n={len(bars15)} {bars15.index.min()} → {bars15.index.max()}", flush=True)

    print("Merge tapes…", flush=True)
    m5 = merge_tape(TAPE5, bars5)
    m15 = merge_tape(TAPE15, bars15)
    print(f"  5m n={m5['n']} max={m5['max']}", flush=True)
    print(f"  15m n={m15['n']} max={m15['max']}", flush=True)

    # isolate ledger
    if LEDGER.exists():
        shutil.copy2(LEDGER, LEDGER_BAK)
    sx._ledger_save([])

    days = sorted(set(bars15.index.strftime("%Y-%m-%d")))
    print(
        f"Replay {len(days)} sessions · dual.evaluate → CHAMP fill (dual list suppressed)",
        flush=True,
    )

    dual_fires: List[dict] = []
    board_rows: List[dict] = []

    for di, day in enumerate(days, 1):
        day15 = bars15[bars15.index.strftime("%Y-%m-%d") == day]
        dual_day: List[dict] = []
        for ts, row in day15.iterrows():
            asof = pd.Timestamp(ts)
            window = bars15[bars15.index <= asof].tail(80)
            if len(window) < 20:
                continue
            try:
                ev = dual.evaluate(
                    window,
                    asof=asof.to_pydatetime(),
                    price=float(row["Close"]),
                )
            except Exception:
                continue
            payload = ev.get("call_payload") if isinstance(ev, dict) else None
            if not (isinstance(payload, dict) and payload.get("decision") in ("BUY", "SELL")):
                continue
            hm = asof.tz_convert("Asia/Kolkata").strftime("%H:%M")
            dual_row = {
                "day": day,
                "hm": hm,
                "decision": payload.get("decision"),
                "track": payload.get("track") or ("proven_100" if ev.get("proven_100") else "champion"),
                "p_t1": payload.get("p_t1"),
                "entry": payload.get("entry") or float(row["Close"]),
                "suppressed_list": True,
            }
            dual_day.append(dual_row)
            dual_fires.append(dual_row)
            sx.ensure_session_calls(
                day,
                dual_call={
                    **payload,
                    "day": day,
                    "hm": hm,
                    "track": dual_row["track"],
                    "entry": dual_row["entry"],
                },
                hm=hm,
                entry=float(dual_row["entry"]),
            )

        day_calls = [
            r
            for r in sx._ledger_load()
            if str(r.get("day") or "")[:10] == day
        ]
        if di % 5 == 0 or di == len(days):
            print(
                f"  [{di}/{len(days)}] {day}: dual_fire={len(dual_day)} board={len(day_calls)}",
                flush=True,
            )

    # path-score board
    print("Path-score board ±100 on 5m…", flush=True)
    # score_one expects naive or tz index with _day helper — normalize like research
    bars_sc = bars5.copy()
    if bars_sc.index.tz is not None:
        bars_sc.index = bars_sc.index.tz_localize(None)
    # rebuild Continuous index from full merged tape for lookback continuity within day
    full5 = _norm_idx(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    if full5.index.tz is not None:
        full5.index = full5.index.tz_localize(None)
    # keep from a bit before START
    full5 = full5[full5.index.strftime("%Y-%m-%d") >= (pd.Timestamp(START) - timedelta(days=5)).strftime("%Y-%m-%d")]
    ix = build_bar_index(full5)

    ledger = sx.stamp_live(sx._ledger_load())
    for r in ledger:
        day = str(r.get("day") or "")[:10]
        hm = str(r.get("hm") or "")[:5]
        side = str(r.get("decision") or r.get("side") or "").upper()
        sc = score_one(full5, ix, day, hm, side, SL_PTS, T1_PTS)
        rr = dict(r)
        if sc:
            rr.update(sc)
            # open if same-day path didn't resolve and day is today
            if sc.get("outcome") == "expired" and day >= END:
                rr["win"] = None
        board_rows.append(rr)

    # restore ledger
    if LEDGER_BAK.exists():
        shutil.copy2(LEDGER_BAK, LEDGER)
        print("  live ledger restored from backup", flush=True)

    by_month: Dict[str, List[dict]] = defaultdict(list)
    for r in board_rows:
        by_month[str(r.get("day") or "")[:7]].append(r)

    overall = month_stats(board_rows)
    dual_by_month: Dict[str, List[dict]] = defaultdict(list)
    for r in dual_fires:
        dual_by_month[str(r.get("day") or "")[:7]].append(r)

    elapsed = round(time.time() - t0, 1)
    payload = {
        "symbol": "SENSEX",
        "window": {"start": START, "end": END},
        "desk": sx.DESK_CHAMP,
        "brackets": dict(sx.BRACKETS),
        "cap": CAP,
        "suppress_dual_list": True,
        "elapsed_s": elapsed,
        "sessions": len(days),
        "dual_fires_n": len(dual_fires),
        "board": overall,
        "by_month": {m: month_stats(rs) for m, rs in sorted(by_month.items())},
        "dual_by_month": {m: {"n": len(rs)} for m, rs in sorted(dual_by_month.items())},
        "calls": board_rows,
        "dual_fires": dual_fires,
        "tapes": {"5m": m5, "15m": m15},
    }

    OUT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# SENSEX live logic · last 2 months",
        "",
        f"**Window:** `{START}` → `{END}` · {len(days)} sessions",
        f"**Desk:** `{sx.DESK_CHAMP}` · ±{SL_PTS:.0f}/{T1_PTS:.0f} · Cap{CAP}",
        f"**Path:** `SUPPRESS_DUAL_LIST=1` · dual scores but does **not** list · CHAMP fills Calls",
        f"**Elapsed:** {elapsed}s",
        "",
        "## Headline",
        "",
        f"- **Board N={overall['n']}** · settled={overall['settled']} · "
        f"**hit={overall['hit_pct']}%** · W/L/O="
        f"{overall['wins']}/{overall['losses']}/{overall['open']}",
        f"- Dual fires (suppressed list): **{len(dual_fires)}**",
        f"- by side: `{overall['by_side']}` · by track: `{overall['by_track']}`",
        "",
        "## Per month",
        "",
        "| Month | Dual fires | Board N | Settled | Hit% | W / L / open | Side |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    # include every calendar month in the window even if empty
    month_keys = sorted(
        {
            *(by_month.keys()),
            *(dual_by_month.keys()),
            *pd.period_range(START[:7], END[:7], freq="M").strftime("%Y-%m").tolist(),
        }
    )
    for m in month_keys:
        st = month_stats(by_month.get(m) or [])
        dfire = len(dual_by_month.get(m) or [])
        lines.append(
            f"| **{m}** | {dfire} | {st['n']} | {st['settled']} | "
            f"{st['hit_pct'] if st['hit_pct'] is not None else '—'} | "
            f"{st['wins']} / {st['losses']} / {st['open']} | `{st['by_side']}` |"
        )

    lines += [
        "",
        "## Calls (CHAMP board)",
        "",
        "| Day | HM | Side | Track | Win | Pts | Outcome |",
        "|---|---|---|---|---|---:|---|",
    ]
    for r in board_rows:
        w = r.get("win")
        wlab = "W" if w is True else ("L" if w is False else "open")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | "
            f"{r.get('track')} | {wlab} | {r.get('points')} | {r.get('outcome')} |"
        )
    if not board_rows:
        lines.append("| — | — | — | — | — | — | no board fills |")

    lines += [
        "",
        "## Dual fires (NOT listed — seed only)",
        "",
        "| Day | HM | Side | Track | p_t1 |",
        "|---|---|---|---|---:|",
    ]
    for r in dual_fires:
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | "
            f"{r.get('track')} | {r.get('p_t1')} |"
        )
    if not dual_fires:
        lines.append("| — | — | — | — | no dual fires |")

    lines += [
        "",
        "## Tape",
        "",
        f"- 5m: `{TAPE5}` n={m5['n']} · max {m5['max']}",
        f"- 15m: `{TAPE15}` n={m15['n']} · max {m15['max']}",
        "",
        "_Generated by `tests/builders/_replay_sensex_live_logic_2m.py`_",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_MD}", flush=True)
    print(
        f"Total board {overall['n']} @ {overall['hit_pct']}% · dual_fires={len(dual_fires)}",
        flush=True,
    )
    for m, st in sorted(payload["by_month"].items()):
        print(
            f"  {m}: n={st['n']} hit={st['hit_pct']}% W/L/O={st['wins']}/{st['losses']}/{st['open']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
