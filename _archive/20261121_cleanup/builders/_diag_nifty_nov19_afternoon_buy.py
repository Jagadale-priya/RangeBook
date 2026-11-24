"""Diagnose why NIFTY missed the 2026-11-19 afternoon BUY (~+170 pts after 13:00).

Walks live dual.evaluate on each 15m bar + CHAMP_PLUS fill check.
Also probes relaxed afternoon BUY gates and scores them on 1y cache.

  python -u prod_live/tests/builders/_diag_nifty_nov19_afternoon_buy.py
"""
from __future__ import annotations

import json
import os
import sys
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
os.environ.setdefault("SUPPRESS_DUAL_LIST", "1")
import path_setup  # noqa: F401,E402

import kite_data  # noqa: E402
import nifty_live_dual_track as dual  # noqa: E402
from research_bn_sensex_final_brackets import score_one  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
DAY = "2026-11-19"
CACHE_DUAL = ROOT / "stock_signal_data/fno_validate/research/_cache_dual15_dual5_10y.json"
CACHE_PATH = ROOT / "stock_signal_data/fno_validate/research/_cache_path_trusted_10y.json"
WIN_1Y = ("2025-10-24", "2026-11-19")
SL = T1 = 30.0


def norm(df: pd.DataFrame) -> pd.DataFrame:
    w = df.copy()
    if getattr(w.index, "tz", None) is not None:
        w.index = w.index.tz_convert("Asia/Kolkata")
    elif w.index.tz is None:
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


def main() -> int:
    print(f"Pull NIFTY tape for {DAY}…", flush=True)
    b15, e15 = kite_data.fetch_historical_candles("NIFTY", "15minute", days=40, keep_partial=True)
    b5, e5 = kite_data.fetch_historical_candles("NIFTY", "5minute", days=40, keep_partial=True)
    if e15 or e5 or b15 is None or b5 is None:
        raise SystemExit(f"kite fail {e15} {e5}")
    bars15 = norm(b15)
    bars5 = norm(b5)
    day15 = bars15[bars15.index.strftime("%Y-%m-%d") == DAY]
    print(f"15m bars today={len(day15)} tape {bars15.index.min()}→{bars15.index.max()}", flush=True)

    # Walk dual evaluate
    rows = []
    for ts, row in day15.iterrows():
        asof = pd.Timestamp(ts)
        hm = asof.tz_convert("Asia/Kolkata").strftime("%H:%M")
        window = bars15[bars15.index <= asof].tail(120)
        try:
            ev = dual.evaluate(window, asof=asof.to_pydatetime(), price=float(row["Close"]))
        except Exception as exc:
            rows.append({"hm": hm, "err": str(exc)})
            continue
        dbg = (ev or {}).get("debug") or {}
        mv = (ev or {}).get("model_view") or {}
        st = (ev or {}).get("or_state") or {}
        payload = (ev or {}).get("call_payload")
        rows.append(
            {
                "hm": hm,
                "close": round(float(row["Close"]), 1),
                "available": bool((ev or {}).get("available")),
                "reason": (ev or {}).get("reason"),
                "decision": (payload or {}).get("decision") if isinstance(payload, dict) else None,
                "track": (payload or {}).get("track") if isinstance(payload, dict) else None,
                "p_t1": (payload or mv or dbg).get("p_t1") if isinstance(payload or mv or dbg, dict) else None,
                "first_break": st.get("first_break") if st else dbg.get("first_break"),
                "regime": (mv or dbg).get("regime") if isinstance(mv or dbg, dict) else None,
                "or_ext": st.get("or_ext") if st else dbg.get("or_ext"),
                "up": st.get("up"),
                "dn": st.get("dn"),
                "mins": st.get("mins"),
                "debug_decision": dbg.get("decision"),
            }
        )

    print("\n=== Dual walk today ===", flush=True)
    for r in rows:
        if r.get("err"):
            print(f"  {r['hm']} ERR {r['err']}", flush=True)
            continue
        flag = "CALL" if r.get("decision") else (r.get("reason") or "—")
        print(
            f"  {r['hm']} C={r['close']} avail={r['available']} {flag} "
            f"p={r.get('p_t1')} fb={r.get('first_break')} reg={r.get('regime')} "
            f"up={r.get('up')} dn={r.get('dn')} ext={r.get('or_ext')} "
            f"want={r.get('debug_decision')}",
            flush=True,
        )

    # Afternoon move context
    aft = day15[day15.index.strftime("%H:%M") >= "13:00"]
    move = {
        "low": float(aft["Low"].min()) if len(aft) else None,
        "high": float(aft["High"].max()) if len(aft) else None,
        "pts": round(float(aft["High"].max()) - float(aft["Low"].min()), 1) if len(aft) else None,
        "from_13_open_to_high": round(float(aft["High"].max()) - float(aft["Open"].iloc[0]), 1)
        if len(aft)
        else None,
    }
    print(f"\nAfternoon move: {move}", flush=True)

    # Research: afternoon BUY continuations from dual champion pool (after first break already happened)
    # Probe: BUY when up, p>=0.50/0.55, mins>=13:00, first_break OR continuation, regime any
    dual_cache = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}

    # Use live evaluate rising-edge after 13:00 with relaxed floors on historical tape last 1y
    # Faster: scan champion+proven rows and also invent afternoon cont from path cache if available
    champ = [dict(r, track="champion") for r in dual_cache["dual15"]["champion"]]
    proven = [dict(r, track="proven_100") for r in dual_cache["dual15"]["proven_100"]]
    all_dual = proven + champ

    def clip(rows, a, b):
        return [r for r in rows if a <= str(r.get("day") or "")[:10] <= b]

    y1 = clip(all_dual, *WIN_1Y)
    after_13 = [
        r
        for r in y1
        if str(r.get("hm") or "") >= "13:00"
        and str(r.get("decision") or r.get("side") or "").upper() == "BUY"
    ]
    print(f"\nExisting dual BUY after 13:00 in 1y cache: n={len(after_13)}", flush=True)

    # Probe afternoon continuation on last ~60 sessions via evaluate with temporary gate relax
    # Save originals
    orig = {
        "CHAMPION_BUY_MIN_P": dual.CHAMPION_BUY_MIN_P,
        "CHAMPION_BUY_REGIMES": dual.CHAMPION_BUY_REGIMES,
        "PROVEN_BUY_MAX_MINS": dual.PROVEN_BUY_MAX_MINS,
    }

    def replay_afternoons(
        *,
        pmin: float,
        allow_cont: bool,
        regimes: Optional[set],
        max_mins: int = 15 * 60 + 15,
        sessions: int = 60,
    ) -> Dict[str, Any]:
        dual.CHAMPION_BUY_MIN_P = pmin
        if regimes is not None:
            dual.CHAMPION_BUY_REGIMES = frozenset(regimes)
        # monkeypatch champion_ok BUY cont
        _old_champ = dual.champion_ok

        def _champ_ok(**kw):
            decision = kw.get("decision")
            first_break = kw.get("first_break")
            regime = kw.get("regime")
            p_t1 = float(kw.get("p_t1") or 0)
            mins = kw.get("mins")
            skip = kw.get("skip_after_sl")
            if skip:
                return False
            if decision == "BUY":
                if mins is not None and int(mins) > max_mins:
                    return False
                if regimes is not None and regime not in dual.CHAMPION_BUY_REGIMES:
                    return False
                if not first_break and not allow_cont:
                    return False
                # afternoon focus: only count fires at/after 13:00 for this probe's "afternoon" set
                return p_t1 >= pmin
            return _old_champ(**kw)

        dual.champion_ok = _champ_ok  # type: ignore
        days = sorted(set(bars15.index.strftime("%Y-%m-%d")))
        days = [d for d in days if WIN_1Y[0] <= d <= WIN_1Y[1]][-sessions:]
        picks = []
        for day in days:
            d15 = bars15[bars15.index.strftime("%Y-%m-%d") == day]
            prev = None
            for ts, row in d15.iterrows():
                asof = pd.Timestamp(ts)
                hm = asof.tz_convert("Asia/Kolkata").strftime("%H:%M")
                if hm < "13:00":
                    continue
                window = bars15[bars15.index <= asof].tail(120)
                if len(window) < 20:
                    continue
                try:
                    ev = dual.evaluate(
                        window, asof=asof.to_pydatetime(), price=float(row["Close"])
                    )
                except Exception:
                    continue
                payload = ev.get("call_payload") if isinstance(ev, dict) else None
                if not (isinstance(payload, dict) and payload.get("decision") == "BUY"):
                    prev = None
                    continue
                key = (day, hm, "BUY", str(payload.get("track")))
                if key[:2] == (prev or (None, None))[:2] and prev and prev[2] == "BUY":
                    # rising edge by side only
                    continue
                # rising edge
                if prev and prev[0] == day and prev[2] == "BUY":
                    # still same side ongoing — skip unless track change
                    if prev[3] == str(payload.get("track")):
                        continue
                picks.append(
                    {
                        "day": day,
                        "hm": hm,
                        "decision": "BUY",
                        "track": payload.get("track"),
                        "p_t1": payload.get("p_t1"),
                        "entry": float(payload.get("entry") or row["Close"]),
                        "first_break": bool((payload.get("model_view") or {}).get("first_break")),
                    }
                )
                prev = (day, hm, "BUY", str(payload.get("track")))
        dual.champion_ok = _old_champ  # type: ignore
        dual.CHAMPION_BUY_MIN_P = orig["CHAMPION_BUY_MIN_P"]
        dual.CHAMPION_BUY_REGIMES = orig["CHAMPION_BUY_REGIMES"]

        # score on 5m
        sc_bars = bars5.copy()
        if sc_bars.index.tz is not None:
            sc_bars.index = sc_bars.index.tz_localize(None)
        ix = build_ix(sc_bars)
        scored = []
        for r in picks:
            sc = score_one(sc_bars, ix, r["day"], r["hm"], "BUY", SL, T1)
            if not sc:
                continue
            rr = {**r, **sc}
            scored.append(rr)
        today_hits = [r for r in scored if r["day"] == DAY]
        return {
            "pmin": pmin,
            "allow_cont": allow_cont,
            "regimes": sorted(regimes) if regimes else "default",
            "n": len(scored),
            "hit_pct": hit(scored),
            "wins": sum(1 for r in scored if r.get("win")),
            "losses": sum(1 for r in scored if r.get("win") is False),
            "today_n": len(today_hits),
            "today": today_hits,
            "by_day_n": len({r["day"] for r in scored}),
        }

    print("\n=== Afternoon BUY probes (last 60 sessions, ≥13:00, ±30) ===", flush=True)
    probes = []
    for name, kwargs in [
        ("live_champ_p55_fb_only", dict(pmin=0.55, allow_cont=False, regimes={"range", "mixed"})),
        ("p55_cont_range_mixed", dict(pmin=0.55, allow_cont=True, regimes={"range", "mixed"})),
        ("p55_cont_all_regimes", dict(pmin=0.55, allow_cont=True, regimes={"range", "mixed", "trend", "volatile"})),
        ("p50_cont_all_regimes", dict(pmin=0.50, allow_cont=True, regimes={"range", "mixed", "trend", "volatile"})),
        ("p50_fb_all_regimes", dict(pmin=0.50, allow_cont=False, regimes={"range", "mixed", "trend", "volatile"})),
        ("p58_cont_trend_vol", dict(pmin=0.58, allow_cont=True, regimes={"trend", "volatile", "range", "mixed"})),
    ]:
        print(f"  probe {name}…", flush=True)
        st = replay_afternoons(**kwargs)
        st["name"] = name
        probes.append(st)
        print(
            f"    n={st['n']} hit={st['hit_pct']}% days={st['by_day_n']} today={st['today_n']}",
            flush=True,
        )

    # restore
    dual.CHAMPION_BUY_MIN_P = orig["CHAMPION_BUY_MIN_P"]
    dual.CHAMPION_BUY_REGIMES = orig["CHAMPION_BUY_REGIMES"]
    dual.PROVEN_BUY_MAX_MINS = orig["PROVEN_BUY_MAX_MINS"]

    # Why missed today: summarize after 13:00 debug
    after_rows = [r for r in rows if r.get("hm", "") >= "13:00"]
    reasons = defaultdict(int)
    for r in after_rows:
        reasons[str(r.get("reason") or ("CALL:" + str(r.get("track")) if r.get("decision") else "none"))] += 1

    payload = {
        "day": DAY,
        "afternoon_move": move,
        "dual_walk": rows,
        "after_13_reason_counts": dict(reasons),
        "existing_dual_buy_after_13_1y": len(after_13),
        "probes": [{k: v for k, v in p.items() if k != "today"} | {"today": p.get("today")} for p in probes],
        "note": (
            "Live proven BUY cuts at 13:00; champion BUY needs first_break + regime∈{range,mixed} + p≥0.55. "
            "Afternoon trend continuation often fails first_break / regime gates."
        ),
    }

    lines = [
        f"# NIFTY · why we missed {DAY} afternoon BUY · research probes",
        "",
        f"**Move after 13:00:** low {move['low']} → high {move['high']} · **+{move['pts']} pts** "
        f"(from 13:00 open to high **+{move['from_13_open_to_high']}**)",
        "",
        "## Why live dual did not list",
        "",
        "- `proven_100` BUY hard-stops at **13:00** (`PROVEN_BUY_MAX_MINS`).",
        "- `champion` BUY needs **first_break** + regime ∈ {range, mixed} + p≥**0.55** — "
        "afternoon continuation after OR already broken usually fails `first_break`.",
        "- `SUPPRESS_DUAL_LIST=1` anyway; CHAMP_PLUS fill still needs a seed call from dual/stack.",
        "",
        "### Dual walk · after 13:00 reason counts",
        "",
        "| Reason | Bars |",
        "|---|---:|",
    ]
    for k, v in sorted(reasons.items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{k}` | {v} |")
    lines += [
        "",
        "### Full dual walk today",
        "",
        "| HM | Close | Call? | Reason | p_t1 | FB | Regime | Up |",
        "|---|---:|---|---|---:|---|---|---|",
    ]
    for r in rows:
        if r.get("err"):
            continue
        lines.append(
            f"| {r['hm']} | {r['close']} | {r.get('decision') or '—'} | "
            f"{r.get('reason') or ('CALL' if r.get('decision') else '—')} | "
            f"{r.get('p_t1')} | {r.get('first_break')} | {r.get('regime')} | {r.get('up')} |"
        )
    lines += [
        "",
        "## Afternoon BUY probes (last 60 sessions, entry ≥13:00, ±30 on 5m)",
        "",
        "| Probe | N | Hit% | W/L | Days | Fired today? |",
        "|---|---:|---:|---|---:|---|",
    ]
    for p in probes:
        tod = "YES" if p["today_n"] else "no"
        lines.append(
            f"| `{p['name']}` | {p['n']} | {p['hit_pct']} | {p['wins']}/{p['losses']} | "
            f"{p['by_day_n']} | **{tod}** |"
        )
    # show today fires
    for p in probes:
        if not p["today"]:
            continue
        lines += ["", f"### Today fires · `{p['name']}`", "", "| HM | Track | p_t1 | Win | Pts |", "|---|---|---:|---|---:|"]
        for r in p["today"]:
            w = "W" if r.get("win") else ("L" if r.get("win") is False else "?")
            lines.append(
                f"| {r.get('hm')} | {r.get('track')} | {r.get('p_t1')} | {w} | {r.get('points')} |"
            )
    lines += [
        "",
        "## Recommendation",
        "",
        "Add a **separate afternoon BUY continuation lane** (not loosening morning first-break champ):",
        "- Window **13:00–14:45**",
        "- OR already broken up · close > OR high · p≥0.55 (or 0.50 if hit holds)",
        "- Allow **continuation** (not first_break-only)",
        "- Regime allow trend/volatile",
        "- Cap 1 afternoon BUY/day · ±30",
        "",
        "Only promote a probe that both **fires today** and keeps probe hit ≥ ~70% on the 60d sample.",
        "",
    ]

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "NIFTY_NOV19_AFTERNOON_BUY_RESEARCH.md"
    js = OUT / "NIFTY_NOV19_AFTERNOON_BUY_RESEARCH.json"
    md.write_text("\n".join(lines), encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
