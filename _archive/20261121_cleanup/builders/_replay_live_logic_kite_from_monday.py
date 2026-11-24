"""Replay held NIFTY live logic Mon→today using fresh Kite 5m/15m bars.

Live path: SUPPRESS_DUAL_LIST=1 · CHAMP_PLUS fill (±30 Cap4) · ExtraTrees off.
Steps:
  1) Pull NIFTY 5m + 15m from Kite (Mon..now)
  2) Merge 5m into research tape so path-score uses live candles
  3) Walk each 15m bar · dual.evaluate → CHAMP ensure_session_calls(dual_call)
  4) Report calls / hit by day

  python -u prod_live/tests/builders/_replay_live_logic_kite_from_monday.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

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
os.environ.setdefault("ENABLE_EXTRA_TREES_SINGLE", "0")
import path_setup  # noqa: F401,E402

import kite_data  # noqa: E402
import nifty_live_dual_track as dual  # noqa: E402
from prod_live.logic import champ_plus_engine as eng  # noqa: E402
from prod_live.logic.champ_plus_live import ensure_session_calls, stamp_live  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "NIFTY_LIVE_LOGIC_KITE_FROM_MONDAY.md"
OUT_JSON = OUT / "NIFTY_LIVE_LOGIC_KITE_FROM_MONDAY.json"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_kite.csv"
LEDGER_BAK = eng._HOLD / "live_session_calls.json.bak_kite_monday_replay"

START = "2026-11-16"  # Monday


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
    rename = {c: str(c).title() for c in work.columns}
    work = work.rename(columns=rename)
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


def pull_kite(interval: str, days: int = 6) -> pd.DataFrame:
    df, err = kite_data.fetch_historical_candles(
        "NIFTY", interval=interval, days=days, keep_partial=True
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
        # keep history before START; replace START..end with kite
        keep = old[old.index.strftime("%Y-%m-%d") < START]
        merged = pd.concat([keep, fresh[fresh.index.strftime("%Y-%m-%d") >= START]])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    else:
        merged = fresh
    out = merged.copy()
    out.index = out.index.tz_convert("Asia/Kolkata")
    # write naive IST for tape consumers that re-localize
    out2 = out.copy()
    out2.index = out2.index.tz_localize(None)
    out2.to_csv(path)
    return {
        "path": str(path),
        "bak": str(bak) if path.exists() else None,
        "n": len(merged),
        "min": str(merged.index.min()),
        "max": str(merged.index.max()),
        "days": sorted(set(merged.index.strftime("%Y-%m-%d"))),
    }


def hit(rows: List[dict]) -> float:
    known = [r for r in rows if r.get("win") is not None]
    if not known:
        return 0.0
    return round(100.0 * sum(1 for r in known if r.get("win")) / len(known), 2)


def main() -> int:
    t0 = time.time()
    print("Pull Kite 5m/15m…", flush=True)
    bars5 = pull_kite("5minute", days=6)
    bars15 = pull_kite("15minute", days=6)
    # clip from Monday
    bars5 = bars5[bars5.index.strftime("%Y-%m-%d") >= START]
    bars15 = bars15[bars15.index.strftime("%Y-%m-%d") >= START]
    print(
        f"  kite 5m n={len(bars5)} {bars5.index.min()} → {bars5.index.max()}",
        flush=True,
    )
    print(
        f"  kite 15m n={len(bars15)} {bars15.index.min()} → {bars15.index.max()}",
        flush=True,
    )

    print("Merge into research tapes…", flush=True)
    m5 = merge_tape(TAPE5, bars5)
    m15 = merge_tape(TAPE15, bars15)
    print(f"  5m tape n={m5['n']} max={m5['max']}", flush=True)
    print(f"  15m tape n={m15['n']} max={m15['max']}", flush=True)

    # isolate live ledger for clean replay adds
    if eng._LIVE_LEDGER.exists():
        shutil.copy2(eng._LIVE_LEDGER, LEDGER_BAK)
    # keep prior ledger rows BEFORE monday; clear Mon+ for clean fire count
    prev = eng.load_live_ledger()
    kept = [r for r in prev if str(r.get("day") or "")[:10] < START]
    eng.save_live_ledger(kept)

    days = sorted(set(bars15.index.strftime("%Y-%m-%d")))
    print(f"Replay days {days} · dual.evaluate → CHAMP fill (dual list suppressed)", flush=True)

    dual_fires: List[dict] = []
    champ_adds: List[dict] = []
    by_day: Dict[str, Dict[str, Any]] = {}

    for day in days:
        day15 = bars15[bars15.index.strftime("%Y-%m-%d") == day]
        dual_day = []
        champ_day_added = []
        for ts, row in day15.iterrows():
            # evaluate as-of this closed 15m bar
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
            except Exception as exc:
                continue
            payload = ev.get("call_payload") if isinstance(ev, dict) else None
            if not (isinstance(payload, dict) and payload.get("decision") in ("BUY", "SELL")):
                continue
            hm = asof.tz_convert("Asia/Kolkata").strftime("%H:%M")
            dual_row = {
                "day": day,
                "hm": hm,
                "decision": payload.get("decision"),
                "track": payload.get("track"),
                "p_t1": payload.get("p_t1"),
                "entry": payload.get("entry") or float(row["Close"]),
                "accuracy_label": payload.get("accuracy_label"),
                "suppressed_list": True,
            }
            dual_day.append(dual_row)
            dual_fires.append(dual_row)
            # Live board: dual does NOT list; CHAMP_PLUS may fill from dual_call
            meta = ensure_session_calls(
                day,
                dual_call={
                    **payload,
                    "day": day,
                    "hm": hm,
                    "entry": dual_row["entry"],
                },
                hm=hm,
                entry=float(dual_row["entry"]),
            )
            for a in meta.get("added") or []:
                aa = dict(a)
                aa["from_dual_hm"] = hm
                champ_day_added.append(aa)
                champ_adds.append(aa)

        # also day-open seed (cache candidates) once per day
        meta0 = ensure_session_calls(day)
        for a in meta0.get("added") or []:
            if a not in champ_day_added:
                champ_day_added.append(a)
                champ_adds.append(a)

        day_calls = stamp_live(
            [r for r in eng.load_full_book_raw() if str(r.get("day") or "")[:10] == day]
        )
        # re-score unsettled with kite 5m
        from research_100pct_deeper_more_calls import build_bar_index, _norm

        bars_sc = _norm(bars5)
        ix = build_bar_index(bars_sc)
        scored = []
        for r in day_calls:
            rr = dict(r)
            s = eng.path_score_one(
                bars_sc, ix, str(rr.get("day")), str(rr.get("hm") or ""), str(rr.get("decision") or rr.get("side") or "")
            )
            if s:
                rr.update(s)
            scored.append(rr)

        by_day[day] = {
            "dual_fires": len(dual_day),
            "champ_n": len(scored),
            "champ_hit": hit(scored),
            "champ_wins": sum(1 for r in scored if r.get("win") is True),
            "champ_losses": sum(1 for r in scored if r.get("win") is False),
            "champ_open": sum(1 for r in scored if r.get("win") is None),
            "calls": scored,
            "dual": dual_day,
            "added_this_replay": champ_day_added,
        }
        print(
            f"  {day}: dual_fire={len(dual_day)} champ_board={len(scored)} "
            f"hit={hit(scored)}% W/L/O="
            f"{by_day[day]['champ_wins']}/{by_day[day]['champ_losses']}/{by_day[day]['champ_open']}",
            flush=True,
        )

    all_calls = [c for d in by_day.values() for c in d["calls"]]
    elapsed = round(time.time() - t0, 1)

    lines = [
        "# NIFTY live logic · Kite replay from Monday",
        "",
        f"**Window:** `{START}` → `{bars5.index.max()}` (Kite 5m/15m)",
        "**Live path:** `SUPPRESS_DUAL_LIST=1` · dual scores but does **not** list · "
        "**CHAMP_PLUS** Cap4 ±30 fills Calls",
        f"**Elapsed:** {elapsed}s",
        "",
        "## Why this works now",
        "",
        "Earlier Mon–Wed looked empty because the **local 5m CSV stopped ~13 Nov** and "
        "dual research caches had no those days. Kite Connect still has full Mon→today bars — "
        "this run pulls them live and merges into the research tape for path-score.",
        "",
        "## Headline",
        "",
        "| Day | Dual fires (suppressed list) | CHAMP_PLUS board N | Hit% | W / L / open |",
        "|---|---:|---:|---:|---|",
    ]
    for day, st in by_day.items():
        lines.append(
            f"| **{day}** | {st['dual_fires']} | {st['champ_n']} | {st['champ_hit']} | "
            f"{st['champ_wins']} / {st['champ_losses']} / {st['champ_open']} |"
        )
    lines.extend(
        [
            "",
            f"**Total CHAMP board:** {len(all_calls)} · hit **{hit(all_calls)}%** "
            f"({sum(1 for r in all_calls if r.get('win'))}W / "
            f"{sum(1 for r in all_calls if r.get('win') is False)}L / "
            f"{sum(1 for r in all_calls if r.get('win') is None)} open)",
            "",
            "## Calls (CHAMP_PLUS board)",
            "",
            "| Day | HM | Side | Track | Win | Pts | Outcome |",
            "|---|---|---|---|---|---:|---|",
        ]
    )
    for r in sorted(all_calls, key=lambda x: (str(x.get("day")), str(x.get("hm") or ""))):
        w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "?")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | "
            f"{str(r.get('decision') or r.get('side') or '').upper()} | "
            f"{r.get('track') or '—'} | {w} | {r.get('points') if r.get('points') is not None else ''} | "
            f"{r.get('outcome') or ''} |"
        )
    lines.extend(
        [
            "",
            "## Dual fires (NOT listed on Calls — annotate/fill seed only)",
            "",
            "| Day | HM | Side | Track | p_t1 |",
            "|---|---|---|---|---:|",
        ]
    )
    for r in dual_fires:
        lines.append(
            f"| {r['day']} | {r['hm']} | {r['decision']} | {r.get('track') or '—'} | {r.get('p_t1') or ''} |"
        )
    if not dual_fires:
        lines.append("| — | — | — | none this window | — |")
    lines.extend(
        [
            "",
            "## Tape update",
            "",
            f"- 5m: `{m5['path']}` n={m5['n']} · {m5['min']} → {m5['max']}",
            f"- 15m: `{m15['path']}` n={m15['n']} · {m15['min']} → {m15['max']}",
            "",
            "_Generated by `tests/builders/_replay_live_logic_kite_from_monday.py`_",
            "",
        ]
    )
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(
            {
                "start": START,
                "end": str(bars5.index.max()),
                "by_day": {
                    d: {
                        **{k: v for k, v in st.items() if k not in ("calls", "dual", "added_this_replay")},
                        "calls": st["calls"],
                        "dual": st["dual"],
                    }
                    for d, st in by_day.items()
                },
                "dual_fires": dual_fires,
                "champ_total": len(all_calls),
                "champ_hit": hit(all_calls),
                "tape5": m5,
                "tape15": m15,
                "elapsed_s": elapsed,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    # restore prior live ledger (merge: keep pre-monday + any new from this run optional)
    # Prefer restore backup so we don't pollute production ledger with replay fires
    if LEDGER_BAK.exists():
        shutil.copy2(LEDGER_BAK, eng._LIVE_LEDGER)
        print("  live ledger restored from backup", flush=True)

    print(f"\nWrote {OUT_MD}", flush=True)
    print(f"Total CHAMP {len(all_calls)} @ {hit(all_calls)}% · dual_fires={len(dual_fires)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
