"""Research nifty_ranked_desk_guide on last ~30 calendar days.

Annotates 15m dual pack columns onto 1m bars, then runs:
  - ranked (proven → champion → ORB accurate)
  - orb_only (no dual columns)
  - ranked + trend_stay accurate as desk-4 fill when silent

  python -u prod_live/tests/builders/_diag_nifty_ranked_desk_30d.py
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live" / "tests" / "builders"),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
]
import path_setup  # noqa: F401,E402

warnings.filterwarnings("ignore")

from _diag_nifty_state_conditional_1m import load_1m  # noqa: E402
import nifty_live_dual_track as live  # noqa: E402
from prod_live.logic import nifty_ranked_desk_guide as rg  # noqa: E402
from prod_live.logic import nifty_state_conditional as state  # noqa: E402
from prod_live.logic import nifty_trend_stay as trend  # noqa: E402

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT_DIR / "NIFTY_RANKED_DESK_GUIDE_30D.md"
OUT_JSON = OUT_DIR / "NIFTY_RANKED_DESK_GUIDE_30D.json"
OUT_CALLS = OUT_DIR / "NIFTY_RANKED_DESK_GUIDE_30D_CALLS.csv"
COST = 1.0
TEST_CALENDAR_DAYS = 30
WARM_SESSIONS = 80
LOOKBACK = pd.Timedelta(days=12)


def _pct(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"{100.0 * x:.1f}%"


def _f(x: Optional[float], nd: int = 2) -> str:
    if x is None:
        return "n/a"
    return f"{x:.{nd}f}"


def _day_str(ts) -> str:
    t = ts
    if hasattr(t, "tz_convert"):
        try:
            t = t.tz_convert("Asia/Kolkata")
        except Exception:
            pass
    if hasattr(t, "strftime"):
        return t.strftime("%Y-%m-%d")
    return str(t)[:10]


def _hm(ts) -> str:
    t = ts
    if hasattr(t, "tz_convert"):
        try:
            t = t.tz_convert("Asia/Kolkata")
        except Exception:
            pass
    return t.strftime("%H:%M") if hasattr(t, "strftime") else str(t)[11:16]


def _to_frame(raw: List[dict]) -> pd.DataFrame:
    rows = []
    for r in raw:
        rows.append(
            {
                "Open": float(r["open"]),
                "High": float(r["high"]),
                "Low": float(r["low"]),
                "Close": float(r["close"]),
                "Volume": float(r.get("volume") or 0.0),
            }
        )
    idx = [pd.Timestamp(r["datetime"]) for r in raw]
    frame = pd.DataFrame(rows, index=pd.DatetimeIndex(idx))
    if frame.index.tz is None:
        frame.index = frame.index.tz_localize("Asia/Kolkata")
    else:
        frame.index = frame.index.tz_convert("Asia/Kolkata")
    return frame.sort_index()


def _resample_15m(frame: pd.DataFrame) -> pd.DataFrame:
    ohlc = frame.resample("15min", label="left", closed="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    )
    return ohlc.dropna(subset=["Open", "High", "Low", "Close"])


def _or_break_idxs(sess: pd.DataFrame) -> List[int]:
    if len(sess) < 2:
        return []
    or_hi = float(sess["High"].astype(float).iloc[0])
    or_lo = float(sess["Low"].astype(float).iloc[0])
    if or_hi <= or_lo:
        return []
    closes = sess["Close"].astype(float)
    first_up = first_dn = None
    out: List[int] = []
    for pos in range(len(sess)):
        c = float(closes.iloc[pos])
        if first_up is None and c > or_hi:
            first_up = pos
            out.append(pos)
        if first_dn is None and c < or_lo:
            first_dn = pos
            if pos not in out:
                out.append(pos)
        if first_up is not None and first_dn is not None:
            break
    return sorted(set(out))[:4]


def annotate_dual_on_1m(raw: List[dict]) -> Tuple[List[dict], Dict[str, Any]]:
    """Stamp 15m dual evaluate columns onto 1m bars at OR-break bars."""
    if not live.packs_available():
        print("dual packs missing — ORB-only path only", flush=True)
        return [dict(r) for r in raw], {"stamped": 0, "reason": "packs_missing"}

    frame = _to_frame(raw)
    bars15 = _resample_15m(frame)
    sessions = sorted({_day_str(ts) for ts in bars15.index})
    stamped = 0
    by_day_hits: Dict[str, List[dict]] = defaultdict(list)
    # map 1m timestamp -> annotation
    notes: Dict[pd.Timestamp, dict] = {}
    t0 = time.time()
    for si, day in enumerate(sessions, 1):
        sess = bars15[
            [
                _day_str(ts) == day and "09:15" <= _hm(ts) <= "15:15"
                for ts in bars15.index
            ]
        ]
        if len(sess) < 4:
            continue
        for i_local in _or_break_idxs(sess):
            ts = sess.index[i_local]
            full_i = int(bars15.index.get_indexer([ts])[0])
            if full_i < 0:
                continue
            asof = ts + pd.Timedelta("15min")
            left = int(bars15.index.searchsorted(ts - LOOKBACK))
            win = bars15.iloc[left : full_i + 1]
            price = float(bars15["Close"].iloc[full_i])
            try:
                ev = live.evaluate(win, asof=asof, price=price, session_ticket=None)
            except Exception:
                continue
            mv = (ev or {}).get("model_view") or {}
            call = (ev or {}).get("call_payload") or {}
            dec = str(call.get("decision") or mv.get("side") or "").upper()
            if dec not in ("BUY", "SELL"):
                # still stamp raw p/regime from debug if gates_fail for research transparency
                dbg = (ev or {}).get("debug") or {}
                if not dbg:
                    continue
                dec = str(dbg.get("decision") or "").upper()
                if dec not in ("BUY", "SELL"):
                    continue
                p_t1 = dbg.get("p_t1")
                regime = dbg.get("regime")
                or_ext = dbg.get("or_ext")
            else:
                p_t1 = call.get("p_t1") if call.get("p_t1") is not None else mv.get("p_t1")
                regime = mv.get("regime") or call.get("regime")
                or_ext = mv.get("or_ext") if mv.get("or_ext") is not None else call.get("or_ext")
            try:
                p_t1_f = float(p_t1) if p_t1 is not None else None
            except (TypeError, ValueError):
                p_t1_f = None
            if p_t1_f is None:
                continue
            try:
                or_ext_f = float(or_ext) if or_ext is not None else None
            except (TypeError, ValueError):
                or_ext_f = None
            # Stamp every 1m inside this 15m bucket so FiveBar last-minute sees it.
            end = ts + pd.Timedelta("15min") - pd.Timedelta("1min")
            slot = frame[(frame.index >= ts) & (frame.index <= end)]
            for one in slot.index:
                note = {
                    "regime": None if regime in (None, "") else str(regime).lower(),
                    "or_extension": or_ext_f,
                    "buy_probability": p_t1_f if dec == "BUY" else None,
                    "sell_probability": p_t1_f if dec == "SELL" else None,
                }
                # if both sides break same bucket later, keep both if possible
                prev = notes.get(one)
                if prev:
                    if note["buy_probability"] is not None:
                        prev["buy_probability"] = note["buy_probability"]
                    if note["sell_probability"] is not None:
                        prev["sell_probability"] = note["sell_probability"]
                    if note["regime"] is not None:
                        prev["regime"] = note["regime"]
                    if note["or_extension"] is not None:
                        prev["or_extension"] = note["or_extension"]
                else:
                    notes[one] = note
            stamped += 1
            by_day_hits[day].append(
                {
                    "hm": _hm(ts),
                    "decision": dec,
                    "p_t1": p_t1_f,
                    "regime": regime,
                    "or_ext": or_ext_f,
                    "proven": bool((ev or {}).get("proven_100")),
                    "champion": bool((ev or {}).get("champion")),
                }
            )
        if si % 10 == 0 or si == len(sessions):
            print(
                f"  dual annotate {si}/{len(sessions)} stamped_breaks={stamped} "
                f"({time.time() - t0:.0f}s)",
                flush=True,
            )

    out: List[dict] = []
    for r in raw:
        item = dict(r)
        ts = pd.Timestamp(r["datetime"])
        if ts.tzinfo is None:
            key = ts.tz_localize("Asia/Kolkata")
        else:
            key = ts.tz_convert("Asia/Kolkata")
        # match minute
        key = key.floor("min")
        note = notes.get(key)
        if note is None:
            # try without tz match quirks
            for k, v in notes.items():
                if k.strftime("%Y-%m-%d %H:%M") == key.strftime("%Y-%m-%d %H:%M"):
                    note = v
                    break
        if note:
            item.update(note)
        out.append(item)
    meta = {
        "stamped_breaks": stamped,
        "days_with_stamp": len(by_day_hits),
        "hits": {k: v for k, v in by_day_hits.items()},
    }
    return out, meta


def _strip_dual(raw: List[dict]) -> List[dict]:
    out = []
    for r in raw:
        item = dict(r)
        for k in ("regime", "buy_probability", "sell_probability", "or_extension"):
            item.pop(k, None)
        out.append(item)
    return out


def _pair_trades(rows: List[dict]) -> List[dict]:
    trades = []
    pending = None
    for row in rows:
        if row["action"] in ("BUY", "SELL"):
            pending = row
            continue
        if row["action"] == "DROP" and pending is not None and row["points"] is not None:
            pts = float(row["points"])
            trades.append(
                {
                    "date": pending["date"],
                    "desk": pending.get("desk"),
                    "side": pending.get("direction"),
                    "entry_time": pending["time"],
                    "entry": pending["entry"],
                    "stop": pending["stop"],
                    "target": pending["target"],
                    "exit_time": row["time"],
                    "exit_reason": row["reason"],
                    "points": pts,
                    "net": pts - COST,
                }
            )
            pending = None
    return trades


def _naive_dt(value) -> datetime:
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def _trend_fill_ticket(day_bars: List[rg.Bar], profile: str = "accurate") -> Optional[rg.Ticket]:
    """Desk-4 research: trend_stay when ranked desks silent."""
    if not day_bars:
        return None
    idx = pd.DatetimeIndex([b.dt for b in day_bars])
    frame = pd.DataFrame(
        {
            "open": [b.open for b in day_bars],
            "high": [b.high for b in day_bars],
            "low": [b.low for b in day_bars],
            "close": [b.close for b in day_bars],
            "volume": [b.volume for b in day_bars],
        },
        index=idx,
    )
    five = (
        frame.resample("5min", label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
    )
    if five.empty:
        return None
    call = trend.evaluate_day(five, profile=profile)
    direction = getattr(call, "direction", None)
    entry = getattr(call, "entry", None)
    entry_time = getattr(call, "entry_time", None)
    signal_time = getattr(call, "signal_time", None)
    stop = getattr(call, "initial_stop", None)
    if direction is None or entry is None or entry_time is None or stop is None:
        return None
    side = str(direction).lower()
    risk = abs(float(entry) - float(stop))
    if risk <= 0:
        return None
    target = float(entry) + 1.7 * risk if side == "buy" else float(entry) - 1.7 * risk
    desk = f"trend_{profile}"
    return rg.Ticket(
        desk,
        side,
        _naive_dt(signal_time if signal_time is not None else entry_time),
        _naive_dt(entry_time),
        float(entry),
        float(stop),
        float(target),
    )


def _plan_proven_orb_only(fives: List[rg.FiveBar]) -> Optional[rg.Ticket]:
    """Research: skip champion — proven_100 then ORB accurate only."""
    opening = rg._opening_range(fives)
    for index, bar in enumerate(fives[:-1]):
        dual = rg._dual_side(bar)
        if dual is not None:
            side, desk, stop_points, target_points = dual
            if desk != "proven_100":
                # Skip champion; keep scanning for proven or ORB on later bars.
                continue
            entry_bar = fives[index + 1]
            entry = entry_bar.open
            if side == "buy":
                return rg.Ticket(
                    desk, side, bar.end, entry_bar.start, entry,
                    entry - stop_points, entry + target_points,
                )
            return rg.Ticket(
                desk, side, bar.end, entry_bar.start, entry,
                entry + stop_points, entry - target_points,
            )
        if opening is None:
            continue
        opening_high, opening_low = opening
        side = rg._orb_side(bar, opening_high, opening_low)
        if side is None:
            continue
        level = opening_high if side == "buy" else opening_low
        entry_bar = fives[index + 1]
        if not rg._fill_is_close(side, entry_bar.open, level):
            continue
        entry = entry_bar.open
        if side == "buy":
            return rg.Ticket(
                "orb_accurate", side, bar.end, entry_bar.start, entry,
                opening_high - rg.ORB_STOP, entry + rg.ORB_TARGET,
            )
        return rg.Ticket(
            "orb_accurate", side, bar.end, entry_bar.start, entry,
            opening_low + rg.ORB_STOP, entry - rg.ORB_TARGET,
        )
    return None


def _state_tickets_by_day(warm_raw: List[dict], test_days: set) -> Dict[str, rg.Ticket]:
    """First state-accurate call per test day → Ticket for desk-4 fill."""
    calls = state.run(warm_raw, profile="accurate")
    out: Dict[str, rg.Ticket] = {}
    for call in calls:
        day = str(call.get("date") or "")
        if day in out:
            continue
        try:
            d = datetime.fromisoformat(day).date()
        except Exception:
            continue
        if d not in test_days:
            continue
        side = str(call.get("direction") or "").lower()
        entry = call.get("entry")
        stop = call.get("stop")
        target = call.get("target")
        entry_time = call.get("entry_time") or call.get("time")
        if side not in ("buy", "sell") or entry is None or stop is None or target is None:
            continue
        if entry_time is None:
            continue
        ent = _naive_dt(pd.Timestamp(entry_time))
        out[day] = rg.Ticket(
            "state_accurate",
            side,
            ent,
            ent,
            float(entry),
            float(stop),
            float(target),
        )
    return out


def run_variant(
    raw: List[dict],
    *,
    mode: str,
    state_by_day: Optional[Dict[str, rg.Ticket]] = None,
) -> Tuple[List[dict], List[dict], dict]:
    bars = [rg.parse_bar(r) for r in raw]
    bars.sort(key=lambda b: b.dt)
    sessions: Dict[str, List[rg.Bar]] = {}
    for bar in bars:
        if rg.OPEN <= bar.dt.time() <= rg.SESSION_END:
            sessions.setdefault(bar.dt.date().isoformat(), []).append(bar)

    rows: List[dict] = []
    for day_key in sorted(sessions):
        day = sessions[day_key]
        if mode == "orb_only":
            stripped = [
                rg.Bar(
                    dt=b.dt, open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume
                )
                for b in day
            ]
            rows.extend(rg.guide_day(stripped))
            continue
        if mode == "ranked":
            rows.extend(rg.guide_day(day))
            continue
        vwap = rg._vwap_path(day)
        fives = rg._five_minute(day, vwap)
        if mode == "proven_orb":
            ticket = _plan_proven_orb_only(fives)
            rows.extend(rg.guide_day(day, ticket=ticket, use_planner=False))
            continue
        if mode == "ranked_plus_trend_accurate":
            ticket = rg._plan_ticket(fives)
            if ticket is None:
                ticket = _trend_fill_ticket(day, "accurate")
            rows.extend(rg.guide_day(day, ticket=ticket, use_planner=False))
            continue
        if mode == "ranked_plus_trend_baseline":
            ticket = rg._plan_ticket(fives)
            if ticket is None:
                ticket = _trend_fill_ticket(day, "baseline")
            rows.extend(rg.guide_day(day, ticket=ticket, use_planner=False))
            continue
        if mode == "ranked_plus_state":
            ticket = rg._plan_ticket(fives)
            if ticket is None and state_by_day is not None:
                ticket = state_by_day.get(day_key)
            rows.extend(rg.guide_day(day, ticket=ticket, use_planner=False))
            continue
        raise ValueError(mode)

    trades = _pair_trades(rows)
    summary = rg.summarize(rows, cost_points=COST)
    called = {t["date"] for t in trades}
    summary["sessions_called"] = len(called)
    summary["sessions_silent"] = summary["sessions"] - len(called)
    return rows, trades, summary


def main() -> int:
    raw, source, _ = load_1m(WARM_SESSIONS)
    if not raw:
        print("no bars", flush=True)
        return 1
    all_dates = sorted({r["datetime"].date() for r in raw})
    hi = all_dates[-1]
    lo = hi - timedelta(days=TEST_CALENDAR_DAYS)
    test_days = [d for d in all_dates if d >= lo]
    test_set = set(test_days)
    test_raw = [r for r in raw if r["datetime"].date() in test_set]
    print(
        f"window {test_days[0]} → {test_days[-1]} · {len(test_days)} sessions · "
        f"{len(test_raw)} 1m bars · source={source}",
        flush=True,
    )

    print("annotating 15m dual columns onto 1m…", flush=True)
    annotated, dual_meta = annotate_dual_on_1m(test_raw)
    n_with_p = sum(
        1
        for r in annotated
        if r.get("buy_probability") is not None or r.get("sell_probability") is not None
    )
    print(f"1m bars with dual cols: {n_with_p} · breaks stamped: {dual_meta.get('stamped_breaks')}", flush=True)

    print("building state_accurate desk-4 map (needs deep warm)…", flush=True)
    state_raw, _, _ = load_1m(750)
    state_by_day = _state_tickets_by_day(state_raw, test_set)
    print(f"  state fills available on {len(state_by_day)} test days", flush=True)

    variants = {}
    modes = (
        "ranked",
        "orb_only",
        "proven_orb",
        "ranked_plus_trend_accurate",
        "ranked_plus_trend_baseline",
        "ranked_plus_state",
    )
    for mode in modes:
        print(f"running {mode}…", flush=True)
        feed = _strip_dual(annotated) if mode == "orb_only" else annotated
        rows, trades, summary = run_variant(
            feed, mode=mode, state_by_day=state_by_day
        )
        variants[mode] = {"rows": rows, "trades": trades, "summary": summary}
        print(
            f"  {mode}: closed={summary['closed_calls']} hit={_pct(summary['hit_rate'])} "
            f"net={_f(summary['net_points'])} called={summary['sessions_called']} "
            f"silent={summary['sessions_silent']} desks={summary.get('by_desk')}",
            flush=True,
        )

    focus = variants["ranked"]
    trades = focus["trades"]
    summary = focus["summary"]
    orb = variants["orb_only"]["summary"]
    proven_orb = variants["proven_orb"]["summary"]
    plus_ta = variants["ranked_plus_trend_accurate"]["summary"]
    plus_tb = variants["ranked_plus_trend_baseline"]["summary"]
    plus_st = variants["ranked_plus_state"]["summary"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(trades).to_csv(OUT_CALLS, index=False)

    desk_lines = []
    for desk, bucket in sorted((summary.get("by_desk") or {}).items()):
        desk_lines.append(
            f"| {desk} | {bucket['n']} | {_pct(bucket.get('hit_rate'))} | {_f(bucket['net'])} |"
        )
    trade_lines = []
    for t in trades:
        trade_lines.append(
            f"| {t['date']} | {t['desk']} | {t['side']} | {t['entry_time'][11:16]} | "
            f"{_f(t['entry'])} | {_f(t['stop'])} | {_f(t['target'])} | "
            f"{t['exit_time'][11:16]} | {t['exit_reason']} | {_f(t['points'])} | {_f(t['net'])} |"
        )

    reasons = Counter(t["exit_reason"] for t in trades)

    def _vrow(name: str, s: dict) -> str:
        return (
            f"| {name} | {s['closed_calls']} | {_pct(s['hit_rate'])} | {_f(s['net_points'])} | "
            f"{s['sessions_called']} | {s['sessions_silent']} |"
        )

    md = f"""# NIFTY ranked desk guide · last 30D

**Source:** `{source}` 1m + 15m dual packs · cost {COST}
**Window:** {test_days[0]} → {test_days[-1]} ({len(test_days)} sessions)
**Module:** `prod_live/logic/nifty_ranked_desk_guide.py`

## Logic (frozen)

1. **proven_100** — buy: range/mixed · p≥0.62 · or_ext≤0.10 · <13:00 · sell: trend · p≥0.58 · ±30
2. **champion** — if proven silent · buy p≥0.55 · sell p≥0.58 · SL20/T30
3. **ORB accurate** — if dual silent · width 40–100 · 5m close within 5 of OR + VWAP · SL12 thru / T20 · flat 14:45

One ticket/session · no reverse · P2F/P2G not a second entry.

Dual columns: stamped from 15m `live.evaluate` OR-breaks onto 1m in that 15m bucket
({dual_meta.get('stamped_breaks')} breaks · {dual_meta.get('days_with_stamp')} days).

## Variant comparison

| Variant | Closed | Hit | Net | Called | Silent |
|---|---:|---:|---:|---:|---:|
{_vrow("**ranked** (proven→champ→ORB)", summary)}
{_vrow("proven+ORB only (skip champion)", proven_orb)}
{_vrow("orb_only", orb)}
{_vrow("ranked + trend_accurate fill", plus_ta)}
{_vrow("ranked + trend_baseline fill", plus_tb)}
{_vrow("ranked + state_accurate fill", plus_st)}

## Ranked · by desk

| Desk | N | Hit | Net |
|---|---:|---:|---:|
{chr(10).join(desk_lines) if desk_lines else "| — | 0 | — | 0 |"}

### Exit reasons (ranked)

```
{dict(reasons)}
```

### Add-on desks (when used)

| Variant | Desks |
|---|---|
| + trend_accurate | `{plus_ta.get("by_desk")}` |
| + trend_baseline | `{plus_tb.get("by_desk")}` |
| + state_accurate | `{plus_st.get("by_desk")}` |
| proven+ORB | `{proven_orb.get("by_desk")}` |

## Trade log (ranked)

| Date | Desk | Side | Entry t | Entry | Stop | Target | Exit | Reason | Pts | Net |
|---|---|---|---|---:|---:|---:|---|---|---:|---:|
{chr(10).join(trade_lines) if trade_lines else "| — | — | — | — | — | — | — | — | — | — | — |"}

## Readout

- Ranked book is the live priority stack in one ticket/day.
- Champion was the drag on this window; **proven+ORB** is the accuracy lift to check.
- Desk-4 fills (trend / state) only help if they fire on silent days without wrecking hit rate.
- Artifacts: `{OUT_CALLS.name}` · `{OUT_JSON.name}`
"""
    OUT_MD.write_text(md, encoding="utf-8")
    payload = {
        "source": source,
        "window": {"lo": str(test_days[0]), "hi": str(test_days[-1]), "sessions": len(test_days)},
        "dual_meta": {
            "stamped_breaks": dual_meta.get("stamped_breaks"),
            "days_with_stamp": dual_meta.get("days_with_stamp"),
        },
        "variants": {
            k: {"summary": v["summary"], "trades": v["trades"]} for k, v in variants.items()
        },
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"wrote {OUT_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
