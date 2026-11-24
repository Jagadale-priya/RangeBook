"""NIFTY proven_100 BUY · remove 13:00 cutoff · last ~30 sessions.

Same proven gates (first-break, range/mixed, or_ext<=0.10, p>=0.62) but allow
after 13:00. Compare locked (cut 13:00) vs open-to-close.

  python -u prod_live/tests/builders/_research_nifty_proven_buy_after_1300.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
os.environ.setdefault("USE_DUAL_TRACK", "1")
import path_setup  # noqa: F401,E402

import kite_data  # noqa: E402
import nifty_live_dual_track as dual  # noqa: E402
from research_bn_sensex_final_brackets import score_one  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
SESSIONS = 30
PULL_DAYS = 50
SL = T1 = 30.0
# Locked proven max = 13:00; open = allow through close
LOCKED_MAX = 13 * 60
OPEN_MAX = 15 * 60 + 30


def norm(df: pd.DataFrame) -> pd.DataFrame:
    w = df.copy()
    if getattr(w.index, "tz", None) is not None:
        w.index = w.index.tz_convert("Asia/Kolkata")
    else:
        w.index = w.index.tz_localize("Asia/Kolkata")
    w = w.rename(columns={c: str(c).title() for c in w.columns})
    for need in ("Open", "High", "Low", "Close"):
        if need not in w.columns:
            for c in list(w.columns):
                if str(c).lower() == need.lower():
                    w = w.rename(columns={c: need})
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in w.columns]
    w = w[cols].sort_index()
    w = w[~w.index.duplicated(keep="last")]
    hm = w.index.strftime("%H:%M")
    return w[(hm >= "09:15") & (hm <= "15:30")]


def build_ix(bars: pd.DataFrame) -> Dict[Tuple[str, str], int]:
    ix = {}
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


def stats(rows: List[dict]) -> Dict[str, Any]:
    known = [r for r in rows if r.get("win") is not None]
    return {
        "n": len(rows),
        "settled": len(known),
        "hit_pct": hit(rows),
        "wins": sum(1 for r in known if r.get("win")),
        "losses": sum(1 for r in known if r.get("win") is False),
        "points": round(sum(float(r.get("points") or 0) for r in known), 1),
    }


def collect_proven(bars15: pd.DataFrame, days: List[str], max_mins: int) -> List[dict]:
    dual.PROVEN_BUY_MAX_MINS = max_mins
    # Force proven track only in evaluate outcome — we filter call_payload track
    picks: List[dict] = []
    for di, day in enumerate(days, 1):
        d15 = bars15[bars15.index.strftime("%Y-%m-%d") == day]
        seen = set()
        for ts, row in d15.iterrows():
            asof = pd.Timestamp(ts)
            hm = asof.tz_convert("Asia/Kolkata").strftime("%H:%M")
            window = bars15[bars15.index <= asof].tail(120)
            if len(window) < 20:
                continue
            try:
                ev = dual.evaluate(
                    window, asof=asof.to_pydatetime(), price=float(row["Close"])
                )
            except Exception:
                continue
            if not isinstance(ev, dict) or not ev.get("proven_100"):
                continue
            payload = ev.get("call_payload") if isinstance(ev.get("call_payload"), dict) else None
            if not payload or payload.get("decision") != "BUY":
                continue
            if str(payload.get("track")) != "proven_100":
                continue
            key = (day, hm)
            if key in seen:
                continue
            seen.add(key)
            mv = payload.get("model_view") or ev.get("model_view") or {}
            picks.append(
                {
                    "day": day,
                    "hm": hm,
                    "decision": "BUY",
                    "track": "proven_100",
                    "p_t1": payload.get("p_t1") or mv.get("p_t1"),
                    "entry": float(payload.get("entry") or row["Close"]),
                    "first_break": bool(mv.get("first_break") or payload.get("first_break")),
                    "regime": mv.get("regime"),
                    "or_ext": mv.get("or_ext"),
                    "mins": mv.get("mins"),
                    "after_1300": hm >= "13:00",
                }
            )
        if di % 5 == 0 or di == len(days):
            print(f"  [{di}/{len(days)}] proven_buys={len(picks)}", flush=True)
    return picks


def score_all(picks: List[dict], bars5: pd.DataFrame) -> List[dict]:
    sc_bars = bars5.copy()
    if sc_bars.index.tz is not None:
        sc_bars.index = sc_bars.index.tz_localize(None)
    ix = build_ix(sc_bars)
    out = []
    for r in picks:
        sc = score_one(sc_bars, ix, r["day"], r["hm"], "BUY", SL, T1)
        if not sc:
            continue
        out.append({**r, **sc})
    return out


def main() -> int:
    print(f"NIFTY proven BUY · remove 13:00 · last {SESSIONS} sessions", flush=True)
    if not kite_data.kite_enabled():
        raise SystemExit("Kite not enabled")

    b15, e15 = kite_data.fetch_historical_candles("NIFTY", "15minute", days=PULL_DAYS, keep_partial=True)
    b5, e5 = kite_data.fetch_historical_candles("NIFTY", "5minute", days=PULL_DAYS, keep_partial=True)
    if e15 or e5 or b15 is None or b5 is None:
        raise SystemExit(f"kite fail {e15} {e5}")
    bars15 = norm(b15)
    bars5 = norm(b5)
    days = sorted(set(bars15.index.strftime("%Y-%m-%d")))[-SESSIONS:]
    print(f"Window {days[0]} → {days[-1]} · {len(days)} sessions", flush=True)

    # Warm packs
    _ = dual.evaluate(
        bars15.tail(80), asof=bars15.index[-1].to_pydatetime(), price=float(bars15["Close"].iloc[-1])
    )

    # Single walk with open cutoff; locked = subset before 13:00 (same gates).
    print("Proven BUY walk (max 15:30; locked = before 13:00 subset)…", flush=True)
    open_picks = collect_proven(bars15, days, OPEN_MAX)
    dual.PROVEN_BUY_MAX_MINS = LOCKED_MAX

    opened = score_all(open_picks, bars5)
    locked = [r for r in opened if not r.get("after_1300")]
    after = [r for r in opened if r.get("after_1300")]
    added = list(after)  # removing cut only adds after-13:00 proven fires

    st_locked = stats(locked)
    st_open = stats(opened)
    st_after = stats(after)
    st_added = stats(added)

    print(
        f"LOCKED n={st_locked['n']} hit={st_locked['hit_pct']}% | "
        f"OPEN n={st_open['n']} hit={st_open['hit_pct']}% | "
        f"AFTER13 n={st_after['n']} hit={st_after['hit_pct']}% | "
        f"ADDED n={st_added['n']} hit={st_added['hit_pct']}%",
        flush=True,
    )

    payload = {
        "window": {"start": days[0], "end": days[-1], "sessions": len(days)},
        "gates": "proven BUY · first_break · range/mixed · or_ext<=0.10 · p>=0.62 · ±30",
        "locked_max_hm": "13:00",
        "open_max_hm": "15:30",
        "locked": st_locked,
        "open_no_1300_cut": st_open,
        "after_1300_only": st_after,
        "added_by_removing_cut": st_added,
        "locked_calls": locked,
        "open_calls": opened,
        "after_1300_calls": after,
        "added_calls": added,
    }

    lines = [
        "# NIFTY proven_100 BUY · remove 13:00 cutoff · last 30 sessions",
        "",
        f"**Window:** `{days[0]}` → `{days[-1]}` · {len(days)} sessions",
        "**Same logic:** first-break · regime ∈ {range, mixed} · or_ext ≤ 0.10 · p ≥ 0.62 · ±30",
        "**Only change:** allow proven BUY after **13:00** (through 15:30)",
        "",
        "## Headline",
        "",
        "| Variant | N | Hit% | W/L | Pts |",
        "|---|---:|---:|---|---:|",
        f"| **Locked (cut @13:00)** | {st_locked['n']} | {st_locked['hit_pct']} | "
        f"{st_locked['wins']}/{st_locked['losses']} | {st_locked['points']} |",
        f"| **No 13:00 cut** | {st_open['n']} | {st_open['hit_pct']} | "
        f"{st_open['wins']}/{st_open['losses']} | {st_open['points']} |",
        f"| After 13:00 only | {st_after['n']} | {st_after['hit_pct']} | "
        f"{st_after['wins']}/{st_after['losses']} | {st_after['points']} |",
        f"| **Added by removing cut** | {st_added['n']} | {st_added['hit_pct']} | "
        f"{st_added['wins']}/{st_added['losses']} | {st_added['points']} |",
        "",
        "## Added calls (would be new if cut removed)",
        "",
        "| Day | HM | p_t1 | Regime | or_ext | Win | Pts |",
        "|---|---|---:|---|---:|---|---:|",
    ]
    for r in added:
        w = "W" if r.get("win") else ("L" if r.get("win") is False else "?")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('p_t1')} | {r.get('regime')} | "
            f"{r.get('or_ext')} | {w} | {r.get('points')} |"
        )
    if not added:
        lines.append("| — | — | — | — | — | — | no new proven BUY after 13:00 |")

    lines += [
        "",
        "## All after-13:00 proven BUYs (open policy)",
        "",
        "| Day | HM | p_t1 | Regime | or_ext | Win | Pts |",
        "|---|---|---:|---|---:|---|---:|",
    ]
    for r in after:
        w = "W" if r.get("win") else ("L" if r.get("win") is False else "?")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('p_t1')} | {r.get('regime')} | "
            f"{r.get('or_ext')} | {w} | {r.get('points')} |"
        )
    if not after:
        lines.append("| — | — | — | — | — | — | none |")

    lines += [
        "",
        "## Locked proven BUYs (for reference)",
        "",
        "| Day | HM | p_t1 | Regime | Win | Pts |",
        "|---|---|---:|---|---|---:|",
    ]
    for r in locked:
        w = "W" if r.get("win") else ("L" if r.get("win") is False else "?")
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('p_t1')} | {r.get('regime')} | "
            f"{w} | {r.get('points')} |"
        )
    if not locked:
        lines.append("| — | — | — | — | — | none in window |")

    lines += [
        "",
        "## Verdict",
        "",
    ]
    if st_added["n"] == 0:
        lines.append(
            "Removing the 13:00 cut added **0** proven BUYs in the last 30 sessions — "
            "after 13:00 the other proven gates (first-break / range-mixed / or_ext≤0.10) still block. "
            "Today’s move was continuation + trend, so it still would **not** enter proven_100."
        )
    else:
        lines.append(
            f"Removing the cut adds **{st_added['n']}** calls @ **{st_added['hit_pct']}%** "
            f"({st_added['wins']}/{st_added['losses']}). "
            + (
                "Hit holds — consider relaxing proven time cut."
                if (st_added["hit_pct"] or 0) >= 90
                else "Hit below proven 100% bar — keep 13:00 cut; use afternoon thrust lane instead."
            )
        )
    lines += ["", "_Generated by `_research_nifty_proven_buy_after_1300.py`_", ""]

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "NIFTY_PROVEN_BUY_AFTER_1300_30D.md"
    js = OUT / "NIFTY_PROVEN_BUY_AFTER_1300_30D.json"
    md.write_text("\n".join(lines), encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
