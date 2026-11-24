"""NIFTY + SENSEX · live logic · fresh Kite · last ~1 month through today.

  Sensex: locked dual+fb bf>=0.20 · ±50/50
  Nifty:  live dual proven/champion · ±30/30 (unchanged)

  python -u prod_live/tests/builders/_replay_nifty_sensex_kite_1m.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
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
os.environ.setdefault("USE_DUAL_TRACK", "1")
os.environ.setdefault("ENABLE_SENSEX_FINAL_LIVE", "1")
os.environ.setdefault("SUPPRESS_DUAL_LIST", "0")
os.environ.setdefault("ENABLE_EXTRA_TREES_SINGLE", "0")
import path_setup  # noqa: F401,E402

import kite_data  # noqa: E402
import nifty_live_dual_track as nifty_dual  # noqa: E402
import sensex_live_dual_track as sensex_dual  # noqa: E402
from prod_live.logic import sensex_final_live as sx  # noqa: E402
from research_bn_sensex_final_brackets import score_one  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "NIFTY_SENSEX_KITE_1M.md"
OUT_JSON = OUT / "NIFTY_SENSEX_KITE_1M.json"

CAL_DAYS = 31
PULL_DAYS = 45
TODAY = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
START_CAL = (pd.Timestamp(TODAY) - pd.Timedelta(days=int(CAL_DAYS))).strftime("%Y-%m-%d")

SX_SL = SX_T1 = float(sx.BRACKETS["sl"])
SX_DESK = sx.DESK_CHAMP
NF_SL, NF_T1 = nifty_dual.champion_clip_pts()
NF_DESK = f"NIFTY_DUAL_T{int(NF_T1)}SL{int(NF_SL)}"


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


def pull_kite(symbol: str, interval: str, days: int) -> pd.DataFrame:
    df, err = kite_data.fetch_historical_candles(
        symbol, interval=interval, days=days, keep_partial=True
    )
    if err or df is None or df.empty:
        raise RuntimeError(f"kite {symbol} {interval} failed: {err}")
    return _norm_idx(df)


def build_bar_index(bars: pd.DataFrame) -> Dict[Tuple[str, str], int]:
    ix: Dict[Tuple[str, str], int] = {}
    for i, ts in enumerate(bars.index):
        d = str(pd.Timestamp(ts).date())
        hm = f"{pd.Timestamp(ts).hour:02d}:{pd.Timestamp(ts).minute:02d}"
        ix[(d, hm)] = i
    return ix


def hit(rows: List[dict]) -> Optional[float]:
    known = [r for r in rows if r.get("win") is not None]
    if not known:
        return None
    return round(100.0 * sum(1 for r in known if r.get("win")) / len(known), 2)


def day_stats(rows: List[dict]) -> Dict[str, Any]:
    known = [r for r in rows if r.get("win") is not None]
    wins = sum(1 for r in known if r.get("win") is True)
    losses = sum(1 for r in known if r.get("win") is False)
    return {
        "n": len(rows),
        "settled": len(known),
        "hit_pct": hit(rows),
        "wins": wins,
        "losses": losses,
        "open": len(rows) - len(known),
        "points": round(sum(float(r.get("points") or 0) for r in known), 1),
        "dual": sum(1 for r in rows if r.get("source") == "dual"),
        "fallback": sum(1 for r in rows if r.get("source") == "fallback"),
        "combined": sum(1 for r in rows if r.get("source") == "dual+fallback"),
    }


def replay_sensex_day(bars15: pd.DataFrame, day: str) -> List[dict]:
    from prod_live.logic import sensex_everyday_fallback as sx_fb

    day15 = bars15[bars15.index.strftime("%Y-%m-%d") == day]
    out: List[dict] = []
    prev_key: Optional[Tuple[str, str]] = None
    fb_taken = False
    for ts, row in day15.iterrows():
        asof = pd.Timestamp(ts)
        hm_bar = asof.tz_convert("Asia/Kolkata").strftime("%H:%M")
        window = bars15[bars15.index <= asof].tail(100)
        if len(window) < 20:
            continue
        dual_payload = None
        try:
            ev = sensex_dual.evaluate(
                window, asof=asof.to_pydatetime(), price=float(row["Close"])
            )
        except Exception:
            ev = {}
        if isinstance(ev, dict):
            dual_payload = ev.get("call_payload") if isinstance(ev.get("call_payload"), dict) else None
            if dual_payload and dual_payload.get("decision") not in ("BUY", "SELL"):
                dual_payload = None
        if dual_payload:
            side = str(dual_payload["decision"]).upper()
            track = str(dual_payload.get("track") or "champion")
            key = (side, track)
            if key != prev_key:
                entry = float(dual_payload.get("entry") or row["Close"])
                lv = sx.levels(entry, side)
                out.append(
                    {
                        "symbol": "SENSEX",
                        "day": day,
                        "hm": hm_bar,
                        "decision": side,
                        "source": "dual",
                        "track": track,
                        "p_t1": dual_payload.get("p_t1"),
                        "entry": entry,
                        "stop_loss": lv.get("stop_loss"),
                        "target_1": lv.get("target_1"),
                        "sl_pts": SX_SL,
                        "t1_pts": SX_T1,
                        "desk": SX_DESK,
                    }
                )
            prev_key = key
        else:
            prev_key = None

        if not fb_taken and hm_bar >= "09:45":
            try:
                fb = sx_fb.or_fallback_call(
                    window, asof=asof.to_pydatetime(), price=float(row["Close"])
                )
            except Exception:
                fb = None
            if isinstance(fb, dict) and fb.get("decision") in ("BUY", "SELL"):
                fb_side = str(fb["decision"]).upper()
                fb_hm = str(fb.get("hm") or "09:45")[:5]
                fb_taken = True
                merged = False
                for i, r in enumerate(out):
                    if r["hm"] in (fb_hm, hm_bar) and r["decision"] == fb_side and r["source"] == "dual":
                        rr = dict(r)
                        rr["source"] = "dual+fallback"
                        rr["track"] = "dual_fb_combined"
                        out[i] = rr
                        merged = True
                        break
                if not merged:
                    entry = float(fb.get("entry") or row["Close"])
                    lv = sx.levels(entry, fb_side)
                    out.append(
                        {
                            "symbol": "SENSEX",
                            "day": day,
                            "hm": fb_hm,
                            "decision": fb_side,
                            "source": "fallback",
                            "track": "or_fallback",
                            "p_t1": fb.get("p_t1"),
                            "entry": entry,
                            "stop_loss": lv.get("stop_loss"),
                            "target_1": lv.get("target_1"),
                            "sl_pts": SX_SL,
                            "t1_pts": SX_T1,
                            "desk": SX_DESK,
                        }
                    )
    return out


def replay_nifty_day(bars15: pd.DataFrame, day: str) -> List[dict]:
    day15 = bars15[bars15.index.strftime("%Y-%m-%d") == day]
    out: List[dict] = []
    prev_key: Optional[Tuple[str, str]] = None
    for ts, row in day15.iterrows():
        asof = pd.Timestamp(ts)
        hm_bar = asof.tz_convert("Asia/Kolkata").strftime("%H:%M")
        window = bars15[bars15.index <= asof].tail(100)
        if len(window) < 20:
            continue
        try:
            ev = nifty_dual.evaluate(
                window, asof=asof.to_pydatetime(), price=float(row["Close"])
            )
        except Exception:
            continue
        payload = ev.get("call_payload") if isinstance(ev, dict) else None
        if not (isinstance(payload, dict) and payload.get("decision") in ("BUY", "SELL")):
            prev_key = None
            continue
        side = str(payload["decision"]).upper()
        track = str(payload.get("track") or "champion")
        key = (side, track)
        if key == prev_key:
            continue
        prev_key = key
        entry = float(payload.get("entry") or row["Close"])
        # Prefer payload levels (live clips); fall back to champion_clip_pts.
        try:
            stop = float(payload.get("stop_loss"))
            target = float(payload.get("target_1"))
        except (TypeError, ValueError):
            stop = target = None
        if stop is None or target is None:
            if side == "BUY":
                stop, target = entry - NF_SL, entry + NF_T1
            else:
                stop, target = entry + NF_SL, entry - NF_T1
        out.append(
            {
                "symbol": "NIFTY",
                "day": day,
                "hm": hm_bar,
                "decision": side,
                "source": "dual",
                "track": track,
                "p_t1": payload.get("p_t1"),
                "entry": entry,
                "stop_loss": round(stop, 2),
                "target_1": round(target, 2),
                "sl_pts": NF_SL,
                "t1_pts": NF_T1,
                "desk": NF_DESK,
            }
        )
    return out


def score_picks(picks: List[dict], bars5: pd.DataFrame, sl: float, t1: float) -> List[dict]:
    bars_sc = bars5.copy()
    if bars_sc.index.tz is not None:
        bars_sc.index = bars_sc.index.tz_localize(None)
    ix = build_bar_index(bars_sc)
    scored: List[dict] = []
    for r in picks:
        sc = score_one(bars_sc, ix, r["day"], r["hm"], r["decision"], sl, t1)
        rr = dict(r)
        if sc:
            rr.update(sc)
            if sc.get("outcome") == "expired" and r["day"] >= TODAY:
                rr["win"] = None
        scored.append(rr)
    return scored


def run_symbol(symbol: str) -> Dict[str, Any]:
    print(f"\n=== {symbol} ===", flush=True)
    print(f"Pull Kite 15m + 5m (~{PULL_DAYS}d)…", flush=True)
    bars15 = pull_kite(symbol, "15minute", PULL_DAYS)
    bars5 = pull_kite(symbol, "5minute", PULL_DAYS)
    print(f"  15m n={len(bars15)} {bars15.index.min()} → {bars15.index.max()}", flush=True)
    print(f"  5m  n={len(bars5)} {bars5.index.min()} → {bars5.index.max()}", flush=True)

    all_days = sorted(
        d for d in set(bars15.index.strftime("%Y-%m-%d")) if START_CAL <= d <= TODAY
    )
    if not all_days:
        raise RuntimeError(f"No sessions for {symbol} in {START_CAL}→{TODAY}")
    start, end = all_days[0], all_days[-1]
    print(f"Replay {len(all_days)} sessions · {start} → {end}", flush=True)

    picks: List[dict] = []
    for di, day in enumerate(all_days, 1):
        if symbol == "SENSEX":
            day_picks = replay_sensex_day(bars15, day)
            sl, t1, desk = SX_SL, SX_T1, SX_DESK
        else:
            day_picks = replay_nifty_day(bars15, day)
            sl, t1, desk = NF_SL, NF_T1, NF_DESK
        picks.extend(day_picks)
        if di % 5 == 0 or di == len(all_days) or day_picks:
            print(
                f"  [{di}/{len(all_days)}] {day}: calls={len(day_picks)}",
                flush=True,
            )

    scored = score_picks(picks, bars5, sl, t1)
    by_day: Dict[str, List[dict]] = defaultdict(list)
    for r in scored:
        by_day[str(r.get("day"))[:10]].append(r)
    overall = day_stats(scored)
    print(
        f"OVERALL {symbol} n={overall['n']} hit={overall['hit_pct']}% "
        f"W/L/O={overall['wins']}/{overall['losses']}/{overall['open']} pts={overall['points']}",
        flush=True,
    )
    return {
        "symbol": symbol,
        "desk": desk,
        "brackets": {"sl": sl, "t1": t1},
        "window": {"start": start, "end": end, "sessions": len(all_days)},
        "days": all_days,
        "overall": overall,
        "by_day": {d: day_stats(by_day.get(d) or []) for d in all_days},
        "calls": scored,
        "kite": {
            "15m": {"n": len(bars15), "min": str(bars15.index.min()), "max": str(bars15.index.max())},
            "5m": {"n": len(bars5), "min": str(bars5.index.min()), "max": str(bars5.index.max())},
        },
    }


def _section(lines: List[str], block: Dict[str, Any]) -> None:
    sym = block["symbol"]
    o = block["overall"]
    br = block["brackets"]
    lines += [
        f"## {sym}",
        "",
        f"**Desk:** `{block['desk']}` · ±{br['sl']:.0f}/{br['t1']:.0f}",
        f"**Window:** `{block['window']['start']}` → `{block['window']['end']}` · "
        f"{block['window']['sessions']} sessions",
        "",
        f"**Calls:** {o['n']} · **Hit:** **{o['hit_pct']}%** · "
        f"W/L/O {o['wins']}/{o['losses']}/{o['open']} · pts {o['points']}",
        f"Sources: dual {o['dual']} · fb {o['fallback']} · combo {o['combined']}",
        "",
        "### Per day",
        "",
        "| Day | N | Hit% | W/L/O | Pts |",
        "|---|---:|---:|---|---:|",
    ]
    for d in block["days"]:
        st = block["by_day"][d]
        hp = st["hit_pct"] if st["hit_pct"] is not None else "—"
        lines.append(
            f"| **{d}** | {st['n']} | {hp} | {st['wins']}/{st['losses']}/{st['open']} | {st['points']} |"
        )
    lines += [
        "",
        "### Calls",
        "",
        "| Day | HM | Side | Source | Track | Win | Pts | Outcome |",
        "|---|---|---|---|---|---|---:|---|",
    ]
    for r in block["calls"]:
        w = r.get("win")
        wlab = "W" if w is True else ("L" if w is False else "open")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | {r.get('source')} | "
            f"{r.get('track')} | {wlab} | {r.get('points')} | {r.get('outcome')} |"
        )
    if not block["calls"]:
        lines.append("| — | — | — | — | — | — | — | no calls |")
    lines.append("")


def main() -> int:
    t0 = time.time()
    print(
        f"NIFTY+SENSEX Kite 1m · {START_CAL} → {TODAY} · "
        f"SX ±{SX_SL:.0f}/{SX_T1:.0f} · NF ±{NF_SL:.0f}/{NF_T1:.0f}",
        flush=True,
    )
    if not kite_data.kite_enabled():
        raise SystemExit("Kite not enabled")

    nifty = run_symbol("NIFTY")
    sensex = run_symbol("SENSEX")
    elapsed = round(time.time() - t0, 1)

    payload = {
        "window_calendar": {"start": START_CAL, "end": TODAY},
        "elapsed_s": elapsed,
        "nifty": {k: v for k, v in nifty.items() if k != "calls"} | {"calls": nifty["calls"]},
        "sensex": {k: v for k, v in sensex.items() if k != "calls"} | {"calls": sensex["calls"]},
    }

    lines = [
        "# NIFTY + SENSEX · Kite live candles · last 1 month",
        "",
        f"**Calendar:** `{START_CAL}` → `{TODAY}`",
        f"**Candles:** fresh Kite **15m** (call) · **5m** (path-score)",
        f"**Elapsed:** {elapsed}s",
        "",
        "## Headline",
        "",
        f"| Symbol | Desk | ±SL/T1 | Sessions | N | Hit% | W/L/O | Pts |",
        f"|---|---|---|---:|---:|---:|---|---:|",
    ]
    for b in (nifty, sensex):
        o = b["overall"]
        lines.append(
            f"| **{b['symbol']}** | `{b['desk']}` | ±{b['brackets']['sl']:.0f}/{b['brackets']['t1']:.0f} | "
            f"{b['window']['sessions']} | {o['n']} | **{o['hit_pct']}** | "
            f"{o['wins']}/{o['losses']}/{o['open']} | {o['points']} |"
        )
    lines.append("")
    _section(lines, nifty)
    _section(lines, sensex)
    lines += ["_Generated by `_replay_nifty_sensex_kite_1m.py`_", ""]

    OUT.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {OUT_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
