"""Replay ONLY live Cap6 logic · last 1 month · same as live session.

Live path (no Cap4):
  SUPPRESS_DUAL_LIST=1
  CHAMP_PLUS_T30SL30_CAP6 ±30 Cap6 via ensure_session_calls
  Morning L5_u70_b80 additive
  Afternoon OFF

Walk 15m bars → dual.evaluate (annotate only) → CHAMP fill.
Each new CHAMP/morning list = would-notify event. Settle ±30 on 5m.
Also compare vs knowledge.db session tickets + desk_notifications if present.

  python -u prod_live/tests/builders/_replay_nifty_live_cap6_1m.py
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
    str(ROOT / "app" / "desk"),
    str(ROOT / "app" / "legacy"),
    str(ROOT / "prod_live"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
os.environ["SUPPRESS_DUAL_LIST"] = "1"
os.environ["USE_DUAL_TRACK"] = "1"
os.environ["ENABLE_EXTRA_TREES_SINGLE"] = "0"
os.environ["ENABLE_NIFTY_AFTERNOON_THRUST"] = "0"
import path_setup  # noqa: F401,E402

import nifty_live_dual_track as dual  # noqa: E402
from prod_live.logic import champ_plus_engine as eng  # noqa: E402
from prod_live.logic.champ_plus_live import (  # noqa: E402
    DESK,
    MODE,
    ensure_session_calls,
    stamp_live,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "NIFTY_LIVE_CAP6_1M_SESSION.md"
OUT_JSON = OUT / "NIFTY_LIVE_CAP6_1M_SESSION.json"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_kite.csv"
LEDGER_BAK = eng._HOLD / "live_session_calls.json.bak_1m_cap6_replay"
DB = ROOT / "stock_signal_data" / "knowledge.db"

TODAY = date.today().isoformat()
START = (pd.Timestamp(TODAY) - pd.DateOffset(months=1)).date().isoformat()


def _norm_idx(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
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


def _hit(rows: List[dict]) -> Optional[float]:
    known = [r for r in rows if r.get("win") is not None]
    if not known:
        return None
    return round(100.0 * sum(1 for r in known if r.get("win")) / len(known), 2)


def _key(r: dict) -> Tuple[str, str, str]:
    return (
        str(r.get("day") or "")[:10],
        str(r.get("decision") or r.get("side") or "").upper(),
        str(r.get("hm") or "")[:5],
    )


def _load_tapes() -> Tuple[pd.DataFrame, pd.DataFrame]:
    bars5 = _norm_idx(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    bars15 = _norm_idx(pd.read_csv(TAPE15, index_col=0, parse_dates=True))
    # try refresh recent from kite
    try:
        import kite_data

        fresh5, err5 = kite_data.fetch_historical_candles(
            "NIFTY", interval="5minute", days=40, keep_partial=True
        )
        fresh15, err15 = kite_data.fetch_historical_candles(
            "NIFTY", interval="15minute", days=40, keep_partial=True
        )
        if not err5 and fresh5 is not None and not fresh5.empty:
            f5 = _norm_idx(fresh5)
            bars5 = pd.concat([bars5, f5])
            bars5 = bars5[~bars5.index.duplicated(keep="last")].sort_index()
            print(f"  kite 5m merged → max {bars5.index.max()}", flush=True)
        else:
            print(f"  kite 5m skip: {err5}", flush=True)
        if not err15 and fresh15 is not None and not fresh15.empty:
            f15 = _norm_idx(fresh15)
            bars15 = pd.concat([bars15, f15])
            bars15 = bars15[~bars15.index.duplicated(keep="last")].sort_index()
            print(f"  kite 15m merged → max {bars15.index.max()}", flush=True)
        else:
            print(f"  kite 15m skip: {err15}", flush=True)
    except Exception as exc:
        print(f"  kite unavailable: {exc} · using tape only", flush=True)
    bars5 = bars5[bars5.index.strftime("%Y-%m-%d") >= START]
    bars15 = bars15[bars15.index.strftime("%Y-%m-%d") >= START]
    return bars5, bars15


def _morning_days(bars15: pd.DataFrame, bars5: pd.DataFrame) -> Dict[str, dict]:
    import importlib.util

    path = ROOT / "prod_live" / "tests" / "builders" / "_compare_nifty_live_vs_research_windows.py"
    spec = importlib.util.spec_from_file_location("cmp_nifty_windows", path)
    cmp = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(cmp)
    b15 = bars15.copy()
    b5 = bars5.copy()
    b15["__d"] = [str(t.date()) for t in b15.index]
    b5["__d"] = [str(t.date()) for t in b5.index]
    g15 = {d: g.drop(columns="__d") for d, g in b15.groupby("__d", sort=True)}
    g5 = {d: g.drop(columns="__d") for d, g in b5.groupby("__d", sort=True)}
    out: Dict[str, dict] = {}
    for d, sess15 in g15.items():
        sess5 = g5.get(d)
        if sess5 is None:
            continue
        r = cmp.morning_day(sess15, sess5)
        if not r:
            continue
        w = r.get("out")
        out[d] = {
            "day": r["d"],
            "hm": r.get("fill") or r.get("sig"),
            "decision": "BUY",
            "side": "BUY",
            "track": "morning_L5_u70_b80",
            "desk": "NIFTY_MORNING_L5_U70_B80",
            "entry": r.get("entry"),
            "win": True if w == "win" else (False if w == "loss" else None),
            "outcome": w,
            "points": 30.0 if w == "win" else (-30.0 if w == "loss" else None),
            "would_notify": True,
            "source": "morning_strong_thrust",
        }
    return out


def _db_live_rows(start: str, end: str) -> Dict[str, Any]:
    """Pull actual session / notify rows for NIFTY in window."""
    info: Dict[str, Any] = {"db": str(DB), "tables": {}, "nifty_tickets": [], "notifications": []}
    if not DB.exists():
        return info
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    info["all_tables"] = tables
    interesting = [t for t in tables if any(x in t.lower() for x in ("session", "call", "ticket", "notif", "desk"))]
    for t in interesting:
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
        info["tables"][t] = cols
        colset = {c.lower() for c in cols}
        # notifications
        if "notif" in t.lower() or t.lower() in ("desk_notifications", "notifications"):
            qcols = cols
            rows = cur.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 500").fetchall()
            for row in rows:
                d = dict(row)
                blob = json.dumps(d, default=str).lower()
                if "nifty" not in blob:
                    continue
                ts = str(d.get("created_at") or d.get("ts") or d.get("time") or d.get("at") or "")
                if ts and (ts[:10] < start or ts[:10] > end):
                    # also allow day field
                    day = str(d.get("day") or d.get("session_date") or "")[:10]
                    if day and (day < start or day > end):
                        continue
                    if not day:
                        continue
                info["notifications"].append(d)
        # session tickets / calls
        if any(x in t.lower() for x in ("session", "call", "ticket")):
            try:
                rows = cur.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 2000").fetchall()
            except Exception:
                continue
            for row in rows:
                d = dict(row)
                blob = json.dumps(d, default=str).upper()
                if "NIFTY" not in blob:
                    continue
                day = str(
                    d.get("session_date")
                    or d.get("day")
                    or d.get("date")
                    or d.get("taken_at")
                    or d.get("created_at")
                    or ""
                )[:10]
                if day and (day < start or day > end):
                    continue
                if not day:
                    continue
                info["nifty_tickets"].append({"table": t, **{k: d[k] for k in list(d)[:40]}})
    con.close()
    return info


def main() -> int:
    t0 = time.time()
    print(f"LIVE Cap6 only · 1m session replay · {START} → {TODAY}", flush=True)
    print(f"DESK={DESK} MODE={MODE} CAP={eng.CAP}", flush=True)
    assert eng.CAP == 6 and "CAP6" in DESK, (eng.CAP, DESK)

    bars5, bars15 = _load_tapes()
    days = sorted(set(bars15.index.strftime("%Y-%m-%d")))
    print(f"sessions={len(days)} 5m={len(bars5)} 15m={len(bars15)} max={bars15.index.max()}", flush=True)

    # isolate ledger: keep pre-window, clear in-window for clean would-notify count
    if eng._LIVE_LEDGER.exists():
        shutil.copy2(eng._LIVE_LEDGER, LEDGER_BAK)
    prev = eng.load_live_ledger()
    kept = [r for r in prev if str(r.get("day") or "")[:10] < START]
    eng.save_live_ledger(kept)

    morning_map = _morning_days(bars15, bars5)
    print(f"morning L5 fires in window: {len(morning_map)}", flush=True)

    from research_100pct_deeper_more_calls import build_bar_index, _norm

    bars_sc = _norm(bars5)
    ix = build_bar_index(bars_sc)

    by_day: Dict[str, Dict[str, Any]] = {}
    all_notifies: List[dict] = []
    all_board: List[dict] = []

    for day in days:
        day15 = bars15[bars15.index.strftime("%Y-%m-%d") == day]
        dual_n = 0
        added_today: List[dict] = []

        # day-open seed (cache candidates) — same as live open
        meta0 = ensure_session_calls(day)
        for a in meta0.get("added") or []:
            aa = dict(a)
            aa["would_notify"] = True
            aa["notify_reason"] = "champ_day_open_seed"
            added_today.append(aa)

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
            dual_n += 1
            hm = asof.tz_convert("Asia/Kolkata").strftime("%H:%M")
            meta = ensure_session_calls(
                day,
                dual_call={**payload, "day": day, "hm": hm, "entry": payload.get("entry") or float(row["Close"])},
                hm=hm,
                entry=float(payload.get("entry") or row["Close"]),
            )
            for a in meta.get("added") or []:
                aa = dict(a)
                aa["would_notify"] = True
                aa["notify_reason"] = "champ_from_dual_seed"
                aa["from_dual_hm"] = hm
                added_today.append(aa)

        # morning thrust — live additive list
        morn = morning_map.get(day)
        morn_rows = []
        if morn:
            morn_rows.append(morn)
            all_notifies.append(dict(morn))

        # board = held∪ledger for day, re-scored
        day_calls = stamp_live(
            [r for r in eng.load_full_book_raw() if str(r.get("day") or "")[:10] == day]
        )
        scored = []
        for r in day_calls:
            rr = dict(r)
            s = eng.path_score_one(
                bars_sc,
                ix,
                str(rr.get("day")),
                str(rr.get("hm") or ""),
                str(rr.get("decision") or rr.get("side") or ""),
            )
            if s:
                rr.update(s)
            scored.append(rr)

        # dedupe notify events
        seen = set()
        notifies = []
        for a in added_today:
            k = _key(a)
            if k in seen:
                continue
            seen.add(k)
            # attach settle if present on board
            for r in scored:
                if _key(r) == k:
                    a = {**a, "win": r.get("win"), "outcome": r.get("outcome"), "points": r.get("points")}
                    break
            notifies.append(a)
            all_notifies.append(a)

        for r in scored:
            all_board.append(r)

        by_day[day] = {
            "dual_fires_suppressed": dual_n,
            "champ_board_n": len(scored),
            "champ_hit": _hit(scored),
            "champ_wins": sum(1 for r in scored if r.get("win") is True),
            "champ_losses": sum(1 for r in scored if r.get("win") is False),
            "champ_open": sum(1 for r in scored if r.get("win") is None),
            "would_notify_n": len(notifies) + (1 if morn else 0),
            "notifies": notifies,
            "morning": morn,
            "calls": scored,
        }
        print(
            f"  {day}: dual={dual_n} board={len(scored)} notify={by_day[day]['would_notify_n']} "
            f"hit={by_day[day]['champ_hit']}% "
            f"W/L/O={by_day[day]['champ_wins']}/{by_day[day]['champ_losses']}/{by_day[day]['champ_open']}"
            + (" +morning" if morn else ""),
            flush=True,
        )

    # restore ledger
    if LEDGER_BAK.exists():
        shutil.copy2(LEDGER_BAK, eng._LIVE_LEDGER)
        print("  live ledger restored", flush=True)

    db_info = _db_live_rows(START, TODAY)
    print(
        f"DB nifty_tickets={len(db_info.get('nifty_tickets') or [])} "
        f"notifications={len(db_info.get('notifications') or [])} "
        f"interesting_tables={list((db_info.get('tables') or {}).keys())[:12]}",
        flush=True,
    )

    settled = [r for r in all_board if r.get("win") is not None]
    notify_settled = [r for r in all_notifies if r.get("win") is not None]
    elapsed = round(time.time() - t0, 1)

    lines = [
        "# NIFTY LIVE Cap6 · last 1 month · same as live session",
        "",
        f"**Generated:** `{datetime.now().isoformat(timespec='seconds')}`",
        f"**Window:** `{START}` → `{TODAY}`",
        f"**Live desk only:** `{DESK}` · mode `{MODE}` · Cap{eng.CAP} · ±30",
        "**Path:** `SUPPRESS_DUAL_LIST=1` · dual does **not** list · CHAMP_PLUS Cap6 fills Calls · morning L5 additive · afternoon OFF",
        f"**Sessions:** {len(days)} · elapsed {elapsed}s",
        "",
        "## Headline",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| CHAMP board calls (settled) | {len(settled)} @ **{_hit(settled)}%** ({sum(1 for r in settled if r.get('win'))}W / {sum(1 for r in settled if r.get('win') is False)}L) |",
        f"| Would-notify events | {len(all_notifies)} |",
        f"| Would-notify settled accuracy | {len(notify_settled)} @ **{_hit(notify_settled)}%** |",
        f"| Morning L5 notifies | {sum(1 for r in all_notifies if r.get('source')=='morning_strong_thrust' or r.get('track')=='morning_L5_u70_b80')} |",
        f"| Cap4 shown? | **No — Cap4 is not live** |",
        "",
        "## Per day (live session)",
        "",
        "| Day | Dual (no list) | CHAMP board | Hit% | W/L/open | Would-notify | Morning |",
        "|---|---:|---:|---:|---|---:|---|",
    ]
    for day, st in by_day.items():
        lines.append(
            f"| **{day}** | {st['dual_fires_suppressed']} | {st['champ_board_n']} | "
            f"{st['champ_hit'] if st['champ_hit'] is not None else '—'} | "
            f"{st['champ_wins']}/{st['champ_losses']}/{st['champ_open']} | "
            f"{st['would_notify_n']} | {'YES' if st.get('morning') else '—'} |"
        )

    lines += [
        "",
        "## Would-notify calls (accurate settle)",
        "",
        "| Day | HM | Side | Source | Win | Pts | Outcome |",
        "|---|---|---|---|---|---:|---|",
    ]
    for r in sorted(all_notifies, key=lambda x: (str(x.get("day")), str(x.get("hm") or ""))):
        w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "?")
        src = r.get("notify_reason") or r.get("source") or r.get("track") or "champ"
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | "
            f"{str(r.get('decision') or r.get('side') or '').upper()} | {src} | {w} | "
            f"{r.get('points') if r.get('points') is not None else ''} | {r.get('outcome') or ''} |"
        )
    if not all_notifies:
        lines.append("| — | — | — | none | — | — | — |")

    lines += [
        "",
        "## Full CHAMP Cap6 board (held ∪ live fill)",
        "",
        "| Day | HM | Side | Track | Win | Pts | Outcome |",
        "|---|---|---|---|---|---:|---|",
    ]
    for r in sorted(all_board, key=lambda x: (str(x.get("day")), str(x.get("hm") or ""))):
        w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "?")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | "
            f"{str(r.get('decision') or r.get('side') or '').upper()} | "
            f"{r.get('track') or '—'} | {w} | "
            f"{r.get('points') if r.get('points') is not None else ''} | {r.get('outcome') or ''} |"
        )

    # DB compare section
    lines += [
        "",
        "## Live DB check (knowledge.db)",
        "",
        f"- Path: `{DB}`",
        f"- NIFTY ticket-like rows in window: **{len(db_info.get('nifty_tickets') or [])}**",
        f"- Notification-like rows in window: **{len(db_info.get('notifications') or [])}**",
        f"- Tables scanned: {', '.join((db_info.get('tables') or {}).keys()) or 'none'}",
        "",
    ]
    if db_info.get("nifty_tickets"):
        lines += [
            "### Sample DB tickets",
            "",
            "| Day | Side | HM/time | Table |",
            "|---|---|---|---|",
        ]
        for d in (db_info["nifty_tickets"])[:40]:
            day = str(d.get("session_date") or d.get("day") or d.get("date") or d.get("taken_at") or "")[:10]
            side = str(d.get("decision") or d.get("side") or "")
            hm = str(d.get("hm") or d.get("taken_at") or d.get("time") or "")[11:16] or str(d.get("hm") or "")
            lines.append(f"| {day} | {side} | {hm} | {d.get('table')} |")
    else:
        lines.append(
            "_No NIFTY session tickets found in DB for this window "
            "(replay still shows what live Cap6 **would** notify)._"
        )

    lines += [
        "",
        "## Notes",
        "",
        "- Cap4 is **not live** and is not included in this report.",
        "- Dual fires are scored but **never listed** (`SUPPRESS_DUAL_LIST=1`).",
        "- A would-notify = new Cap6 CHAMP add or morning L5 list (same events that trigger desktop toast in live).",
        "- Ledger restored after replay — production live_session_calls.json unchanged.",
        "",
        f"JSON: `{OUT_JSON}`",
        "",
    ]

    OUT.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    # trim DB blobs in JSON
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "window": {"start": START, "end": TODAY},
        "desk": DESK,
        "mode": MODE,
        "cap": eng.CAP,
        "sessions": len(days),
        "board_settled": {
            "n": len(settled),
            "hit_pct": _hit(settled),
            "wins": sum(1 for r in settled if r.get("win")),
            "losses": sum(1 for r in settled if r.get("win") is False),
        },
        "would_notify": {
            "n": len(all_notifies),
            "settled_n": len(notify_settled),
            "hit_pct": _hit(notify_settled),
        },
        "by_day": {
            d: {k: v for k, v in st.items() if k not in ("calls", "notifies", "morning")}
            | {
                "calls": st["calls"],
                "notifies": st["notifies"],
                "morning": st.get("morning"),
            }
            for d, st in by_day.items()
        },
        "db": {
            "nifty_ticket_n": len(db_info.get("nifty_tickets") or []),
            "notification_n": len(db_info.get("notifications") or []),
            "tables": list((db_info.get("tables") or {}).keys()),
            "sample_tickets": (db_info.get("nifty_tickets") or [])[:20],
            "sample_notifications": (db_info.get("notifications") or [])[:20],
        },
        "elapsed_s": elapsed,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("\n".join(lines[:70]))
    print("...")
    print("wrote", OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
