"""SENSEX locked dual+fb bf>=20% · fresh Kite candles · last ~20 sessions.

Live-shaped replay:
  1) Pull SENSEX 15m (signals) + 5m (path-score) from Kite
  2) Walk each closed 15m bar · dual.evaluate + OR-fallback combine
  3) Path-score ±50 on 5m · day-by-day report

  python -u prod_live/tests/builders/_replay_sensex_dual_fb_kite_20d.py
"""
from __future__ import annotations

import json
import os
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
os.environ.setdefault("USE_DUAL_TRACK", "1")
os.environ.setdefault("ENABLE_SENSEX_FINAL_LIVE", "1")
os.environ.setdefault("SUPPRESS_DUAL_LIST", "0")
os.environ.setdefault("ENABLE_EXTRA_TREES_SINGLE", "0")
import path_setup  # noqa: F401,E402

import kite_data  # noqa: E402
import sensex_live_dual_track as dual  # noqa: E402
from prod_live.logic import sensex_final_live as sx  # noqa: E402
from research_bn_sensex_final_brackets import score_one  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "SENSEX_DUAL_FB_BF20_KITE_20D.md"
OUT_JSON = OUT / "SENSEX_DUAL_FB_BF20_KITE_20D.json"

SESSIONS = 20
PULL_DAYS = 40
SL_PTS = float(sx.BRACKETS["sl"])
T1_PTS = float(sx.BRACKETS["target"])
DESK = sx.DESK_CHAMP


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


def pull_kite(interval: str, days: int) -> pd.DataFrame:
    df, err = kite_data.fetch_historical_candles(
        "SENSEX", interval=interval, days=days, keep_partial=True
    )
    if err or df is None or df.empty:
        raise RuntimeError(f"kite {interval} failed: {err}")
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


def _source_of(payload: dict) -> str:
    src = str(payload.get("source") or "").lower()
    if "dual+fallback" in src or payload.get("combined"):
        return "dual+fallback"
    if "fallback" in src or str(payload.get("track") or "") == "or_fallback":
        return "fallback"
    return "dual"


def _mk_row(
    *,
    day: str,
    hm: str,
    side: str,
    source: str,
    track: Any,
    p_t1: Any,
    entry: float,
    asof: Any,
) -> dict:
    lv = sx.levels(entry, side)
    return {
        "day": day,
        "hm": hm,
        "decision": side,
        "side": side,
        "source": source,
        "track": track or source,
        "p_t1": p_t1,
        "entry": entry,
        "stop_loss": lv.get("stop_loss"),
        "target_1": lv.get("target_1"),
        "t1_pts": T1_PTS,
        "sl_pts": SL_PTS,
        "desk": DESK,
        "asof": str(asof),
    }


def replay_session(bars15: pd.DataFrame, day: str) -> List[dict]:
    """Rising-edge listing: one dual fire when call newly appears; fb once @09:45.

    Avoids re-listing every 15m bar while SELL-cont gates stay hot (live board
    also treats that as the same open setup, not N new calls).
    """
    from prod_live.logic import sensex_everyday_fallback as sx_fb

    day15 = bars15[bars15.index.strftime("%Y-%m-%d") == day]
    out: List[dict] = []
    prev_dual_key: Optional[Tuple[str, str]] = None  # (side, track)
    fb_taken = False

    for ts, row in day15.iterrows():
        asof = pd.Timestamp(ts)
        hm_bar = asof.tz_convert("Asia/Kolkata").strftime("%H:%M")
        window = bars15[bars15.index <= asof].tail(100)
        if len(window) < 20:
            continue

        dual_payload = None
        try:
            ev = dual.evaluate(
                window,
                asof=asof.to_pydatetime(),
                price=float(row["Close"]),
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
            # rising edge only (new side/track vs previous bar)
            if key != prev_dual_key:
                first = bool((dual_payload.get("model_view") or {}).get("first_break")
                             or dual_payload.get("first_break"))
                # BUY must be first_break; SELL cont allowed but still one rising-edge slot
                if side == "BUY" and not first and track != "proven_100":
                    # still allow if evaluate listed it (champion already gated)
                    pass
                entry = float(dual_payload.get("entry") or row["Close"])
                out.append(
                    _mk_row(
                        day=day,
                        hm=hm_bar,
                        side=side,
                        source="dual",
                        track=track,
                        p_t1=dual_payload.get("p_t1"),
                        entry=entry,
                        asof=asof,
                    )
                )
            prev_dual_key = key
        else:
            prev_dual_key = None

        # OR fallback once from 09:45 onward (locked bf>=0.20)
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
                # combine into same-slot dual if dual already listed same hm+side
                merged = False
                for i, r in enumerate(out):
                    if r["day"] == day and r["hm"] == fb_hm and r["decision"] == fb_side and r["source"] == "dual":
                        rr = dict(r)
                        rr["source"] = "dual+fallback"
                        rr["track"] = "dual_fb_combined"
                        out[i] = rr
                        merged = True
                        break
                if not merged:
                    # if a dual at this bar matches side, combine that edge
                    for i, r in enumerate(out):
                        if (
                            r["day"] == day
                            and r["hm"] == hm_bar
                            and r["decision"] == fb_side
                            and r["source"] == "dual"
                        ):
                            rr = dict(r)
                            rr["source"] = "dual+fallback"
                            rr["track"] = "dual_fb_combined"
                            out[i] = rr
                            merged = True
                            break
                if not merged:
                    out.append(
                        _mk_row(
                            day=day,
                            hm=fb_hm,
                            side=fb_side,
                            source="fallback",
                            track="or_fallback",
                            p_t1=fb.get("p_t1"),
                            entry=float(fb.get("entry") or row["Close"]),
                            asof=asof,
                        )
                    )

    return out


def main() -> int:
    t0 = time.time()
    today = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
    print(
        f"SENSEX Kite replay · last {SESSIONS} sessions · {DESK} ±{SL_PTS:.0f}/{T1_PTS:.0f}",
        flush=True,
    )
    if not kite_data.kite_enabled():
        raise SystemExit("Kite not enabled")

    print(f"Pull Kite 15m + 5m (~{PULL_DAYS}d)…", flush=True)
    bars15 = pull_kite("15minute", PULL_DAYS)
    bars5 = pull_kite("5minute", PULL_DAYS)
    print(f"  15m n={len(bars15)} {bars15.index.min()} → {bars15.index.max()}", flush=True)
    print(f"  5m  n={len(bars5)} {bars5.index.min()} → {bars5.index.max()}", flush=True)

    all_days = sorted(set(bars15.index.strftime("%Y-%m-%d")))
    # use completed sessions; if today still open, keep it but mark open outcomes
    days = all_days[-SESSIONS:]
    start, end = days[0], days[-1]
    print(f"Replay {len(days)} sessions · {start} → {end}", flush=True)

    picks: List[dict] = []
    for di, day in enumerate(days, 1):
        day_picks = replay_session(bars15, day)
        picks.extend(day_picks)
        print(
            f"  [{di}/{len(days)}] {day}: calls={len(day_picks)} "
            f"(dual={sum(1 for r in day_picks if r['source']=='dual')} "
            f"fb={sum(1 for r in day_picks if r['source']=='fallback')} "
            f"combo={sum(1 for r in day_picks if r['source']=='dual+fallback')})",
            flush=True,
        )

    # path-score on 5m
    bars_sc = bars5.copy()
    if bars_sc.index.tz is not None:
        bars_sc.index = bars_sc.index.tz_localize(None)
    ix = build_bar_index(bars_sc)

    scored: List[dict] = []
    for r in picks:
        day = r["day"]
        hm = r["hm"]
        side = r["decision"]
        sc = score_one(bars_sc, ix, day, hm, side, SL_PTS, T1_PTS)
        rr = dict(r)
        if sc:
            rr.update(sc)
            if sc.get("outcome") == "expired" and day >= today:
                rr["win"] = None
        scored.append(rr)

    by_day: Dict[str, List[dict]] = defaultdict(list)
    for r in scored:
        by_day[str(r.get("day"))[:10]].append(r)
    overall = day_stats(scored)
    elapsed = round(time.time() - t0, 1)

    payload = {
        "desk": DESK,
        "logic": "live dual.evaluate + OR fallback bf>=0.20 combine · ±50/50",
        "candle_source": "kite live historical (15m signal / 5m path-score)",
        "window": {"start": start, "end": end, "sessions": len(days)},
        "brackets": {"sl": SL_PTS, "t1": T1_PTS},
        "overall": overall,
        "by_day": {d: day_stats(by_day[d]) for d in days},
        "calls": scored,
        "elapsed_s": elapsed,
        "kite": {
            "15m": {"n": len(bars15), "min": str(bars15.index.min()), "max": str(bars15.index.max())},
            "5m": {"n": len(bars5), "min": str(bars5.index.min()), "max": str(bars5.index.max())},
        },
    }

    lines = [
        f"# SENSEX dual+fb bf≥20% · Kite live candles · last {SESSIONS} sessions",
        "",
        f"**Desk:** `{DESK}` · ±{SL_PTS:.0f}/{T1_PTS:.0f}",
        f"**Window:** `{start}` → `{end}` · {len(days)} sessions",
        "**Candles:** fresh Kite **15m** (call) · **5m** (path-score)",
        f"**Elapsed:** {elapsed}s",
        "",
        "## Headline",
        "",
        f"**Calls:** {overall['n']} · **Hit:** **{overall['hit_pct']}%** · "
        f"W/L/O {overall['wins']}/{overall['losses']}/{overall['open']} · pts {overall['points']}",
        f"Sources: dual {overall['dual']} · fb {overall['fallback']} · combo {overall['combined']}",
        "",
        "## Per day",
        "",
        "| Day | N | Hit% | W/L/O | Dual | FB | Combo | Pts |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for d in days:
        st = day_stats(by_day.get(d) or [])
        hp = st["hit_pct"] if st["hit_pct"] is not None else "—"
        lines.append(
            f"| **{d}** | {st['n']} | {hp} | {st['wins']}/{st['losses']}/{st['open']} | "
            f"{st['dual']} | {st['fallback']} | {st['combined']} | {st['points']} |"
        )
    lines += [
        "",
        "## Calls",
        "",
        "| Day | HM | Side | Source | Track | Win | Pts | Outcome |",
        "|---|---|---|---|---|---|---:|---|",
    ]
    for r in scored:
        w = r.get("win")
        wlab = "W" if w is True else ("L" if w is False else "open")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | {r.get('source')} | "
            f"{r.get('track')} | {wlab} | {r.get('points')} | {r.get('outcome')} |"
        )
    if not scored:
        lines.append("| — | — | — | — | — | — | — | no calls |")
    lines += ["", f"_Generated by `_replay_sensex_dual_fb_kite_20d.py`_", ""]

    OUT.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(
        f"OVERALL n={overall['n']} hit={overall['hit_pct']}% "
        f"W/L/O={overall['wins']}/{overall['losses']}/{overall['open']} pts={overall['points']}",
        flush=True,
    )
    print(f"Wrote {OUT_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
