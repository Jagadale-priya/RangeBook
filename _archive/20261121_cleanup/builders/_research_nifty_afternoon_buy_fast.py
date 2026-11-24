"""Fast research: NIFTY afternoon BUY continuation (catch Nov19-style moves).

Today (2026-11-19) after 13:00: ~+170 pts. Live dual saw BUY p≈0.68 in trend
but gates_fail (first_break=False + regime trend not in {range,mixed}).

Probe: ≥13:00 · OR broken up · allow continuation · allow trend/volatile · p floors.

  python -u prod_live/tests/builders/_research_nifty_afternoon_buy_fast.py
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
    str(ROOT / "prod_live"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
os.environ.setdefault("USE_DUAL_TRACK", "1")
import path_setup  # noqa: F401,E402

import kite_data  # noqa: E402
import nifty_live_dual_track as dual  # noqa: E402
from research_bn_sensex_final_brackets import score_one  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
DAY = "2026-11-19"
SL = T1 = 30.0
# Sample every 15m from 13:00 but only first rising fire/day
CHECK_HMS = ("13:00", "13:15", "13:30", "13:45", "14:00", "14:15", "14:30")
SESSIONS = 45  # ~2 months tape already pulled


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


def patch_champ(pmin: float, allow_cont: bool, regimes: set):
    dual.CHAMPION_BUY_MIN_P = pmin
    dual.CHAMPION_BUY_REGIMES = frozenset(regimes)

    def champion_ok(**kw):
        if kw.get("skip_after_sl"):
            return False
        decision = kw.get("decision")
        if decision != "BUY":
            # keep stock SELL logic
            p_t1 = float(kw.get("p_t1") or 0)
            first = bool(kw.get("first_break"))
            mins = kw.get("mins")
            or_ext = float(kw.get("or_ext") or 0)
            if first:
                return p_t1 >= dual.CHAMPION_SELL_MIN_P
            if mins is not None and int(mins) > dual.CHAMPION_SELL_CONT_MAX_MINS:
                return False
            return (
                p_t1 >= dual.CHAMPION_SELL_MIN_P
                and dual.CHAMPION_SELL_CONT_MIN_EXT <= or_ext <= dual.CHAMPION_SELL_CONT_MAX_EXT
            )
        first = bool(kw.get("first_break"))
        if not first and not allow_cont:
            return False
        regime = kw.get("regime")
        if regime not in dual.CHAMPION_BUY_REGIMES:
            return False
        mins = kw.get("mins")
        if mins is not None and int(mins) < 13 * 60:
            return False  # afternoon lane only
        if mins is not None and int(mins) > 14 * 60 + 45:
            return False
        return float(kw.get("p_t1") or 0) >= pmin

    dual.champion_ok = champion_ok  # type: ignore


def main() -> int:
    print("Pull NIFTY 15m/5m…", flush=True)
    b15, e15 = kite_data.fetch_historical_candles("NIFTY", "15minute", days=70, keep_partial=True)
    b5, e5 = kite_data.fetch_historical_candles("NIFTY", "5minute", days=70, keep_partial=True)
    if e15 or e5 or b15 is None or b5 is None:
        raise SystemExit(f"kite {e15} {e5}")
    bars15 = norm(b15)
    bars5 = norm(b5)
    days = sorted(set(bars15.index.strftime("%Y-%m-%d")))[-SESSIONS:]
    print(f"sessions={len(days)} {days[0]}→{days[-1]}", flush=True)

    # Warm packs once
    _ = dual.evaluate(bars15.tail(80), asof=bars15.index[-1].to_pydatetime(), price=float(bars15["Close"].iloc[-1]))

    sc_bars = bars5.copy()
    if sc_bars.index.tz is not None:
        sc_bars.index = sc_bars.index.tz_localize(None)
    ix = build_ix(sc_bars)

    probes_spec = [
        ("aft_p55_cont_trend+", 0.55, True, {"range", "mixed", "trend", "volatile"}),
        ("aft_p55_cont_range_mixed", 0.55, True, {"range", "mixed"}),
        ("aft_p50_cont_trend+", 0.50, True, {"range", "mixed", "trend", "volatile"}),
        ("aft_p58_cont_trend+", 0.58, True, {"range", "mixed", "trend", "volatile"}),
        ("aft_p55_fb_only_trend+", 0.55, False, {"range", "mixed", "trend", "volatile"}),
    ]

    results = []
    for name, pmin, allow_cont, regimes in probes_spec:
        print(f"probe {name}…", flush=True)
        patch_champ(pmin, allow_cont, regimes)
        picks: List[dict] = []
        for di, day in enumerate(days, 1):
            d15 = bars15[bars15.index.strftime("%Y-%m-%d") == day]
            fired = False
            for ts, row in d15.iterrows():
                if fired:
                    break
                hm = pd.Timestamp(ts).tz_convert("Asia/Kolkata").strftime("%H:%M")
                if hm not in CHECK_HMS:
                    continue
                window = bars15[bars15.index <= ts].tail(100)
                if len(window) < 20:
                    continue
                try:
                    ev = dual.evaluate(
                        window, asof=pd.Timestamp(ts).to_pydatetime(), price=float(row["Close"])
                    )
                except Exception:
                    continue
                payload = ev.get("call_payload") if isinstance(ev, dict) else None
                if not (isinstance(payload, dict) and payload.get("decision") == "BUY"):
                    continue
                picks.append(
                    {
                        "day": day,
                        "hm": hm,
                        "decision": "BUY",
                        "track": payload.get("track") or "champion",
                        "p_t1": payload.get("p_t1"),
                        "entry": float(payload.get("entry") or row["Close"]),
                        "first_break": bool((payload.get("model_view") or {}).get("first_break")),
                        "regime": (payload.get("model_view") or {}).get("regime"),
                    }
                )
                fired = True
            if di % 10 == 0:
                print(f"  [{di}/{len(days)}] picks={len(picks)}", flush=True)

        scored = []
        for r in picks:
            sc = score_one(sc_bars, ix, r["day"], r["hm"], "BUY", SL, T1)
            if not sc:
                continue
            scored.append({**r, **sc})
        today = [r for r in scored if r["day"] == DAY]
        st = {
            "name": name,
            "pmin": pmin,
            "allow_cont": allow_cont,
            "regimes": sorted(regimes),
            "n": len(scored),
            "hit_pct": hit(scored),
            "wins": sum(1 for r in scored if r.get("win")),
            "losses": sum(1 for r in scored if r.get("win") is False),
            "days": len({r["day"] for r in scored}),
            "today_n": len(today),
            "today": today,
            "calls": scored,
        }
        results.append(st)
        print(
            f"  → n={st['n']} hit={st['hit_pct']}% W/L={st['wins']}/{st['losses']} today={st['today_n']}",
            flush=True,
        )

    # Restore defaults by reimport is hard; reset known values
    dual.CHAMPION_BUY_MIN_P = 0.55
    dual.CHAMPION_BUY_REGIMES = frozenset({"range", "mixed"})
    # leave champion_ok patched? re-bind original from module reload
    import importlib

    importlib.reload(dual)

    best = None
    for st in results:
        if st["today_n"] and st["hit_pct"] is not None and st["n"] >= 5:
            if best is None or (st["hit_pct"], st["n"]) > (best["hit_pct"], best["n"]):
                best = st

    lines = [
        "# NIFTY afternoon BUY continuation research",
        "",
        f"**Problem day:** `{DAY}` after 13:00 · ~**+170 pts** (25345 → 25514)",
        "",
        "## Why live missed it",
        "",
        "Dual walk today showed **BUY want** with **p≈0.68** at 11:15, 12:00–12:30, **13:45**, **14:15** "
        "but `gates_fail` because:",
        "",
        "1. `first_break=False` (OR already broken earlier) — champion BUY is first-break only",
        "2. afternoon bars often `regime=trend` — champion BUY only allows `{range, mixed}`",
        "3. `proven_100` BUY hard cutoff at **13:00**",
        "",
        "So the big afternoon push was invisible to the live dual gates.",
        "",
        f"## Probes · last {SESSIONS} sessions · entry in {CHECK_HMS} · 1 BUY/day · ±30",
        "",
        "| Probe | N | Hit% | W/L | Days | Today? |",
        "|---|---:|---:|---|---:|---|",
    ]
    for st in results:
        tod = "YES" if st["today_n"] else "no"
        lines.append(
            f"| `{st['name']}` | {st['n']} | {st['hit_pct']} | {st['wins']}/{st['losses']} | "
            f"{st['days']} | **{tod}** |"
        )
    if best:
        lines += [
            "",
            f"## Best that also fires today: `{best['name']}`",
            "",
            f"**{best['n']}** calls · **{best['hit_pct']}%** · {best['wins']}/{best['losses']} · "
            f"{best['days']} days",
            "",
            "### Today",
            "",
            "| HM | Track | Regime | p_t1 | FB | Win | Pts |",
            "|---|---|---|---:|---|---|---:|",
        ]
        for r in best["today"]:
            w = "W" if r.get("win") else ("L" if r.get("win") is False else "?")
            lines.append(
                f"| {r.get('hm')} | {r.get('track')} | {r.get('regime')} | {r.get('p_t1')} | "
                f"{r.get('first_break')} | {w} | {r.get('points')} |"
            )
        lines += [
            "",
            "### All calls",
            "",
            "| Day | HM | Regime | p | FB | Win | Pts |",
            "|---|---|---|---:|---|---|---:|",
        ]
        for r in best["calls"]:
            w = "W" if r.get("win") else ("L" if r.get("win") is False else "?")
            lines.append(
                f"| {r.get('day')} | {r.get('hm')} | {r.get('regime')} | {r.get('p_t1')} | "
                f"{r.get('first_break')} | {w} | {r.get('points')} |"
            )
        lines += [
            "",
            "## Proposed live add-on (NIFTY only · does not change Sensex)",
            "",
            f"- Lane: **afternoon BUY cont** · `{best['name']}`",
            "- Time: **13:00–14:45**",
            "- OR broken up · allow continuation · regimes include **trend/volatile**",
            f"- p_t1 ≥ **{best['pmin']}**",
            "- Cap **1** afternoon BUY/day · brackets **±30**",
            "- Keep morning first-break champion unchanged",
            "",
        ]
    else:
        lines += ["", "**No probe both fired today and cleared a usable hit floor.**", ""]

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "NIFTY_AFTERNOON_BUY_CONT_RESEARCH.md"
    js = OUT / "NIFTY_AFTERNOON_BUY_CONT_RESEARCH.json"
    md.write_text("\n".join(lines), encoding="utf-8")
    js.write_text(
        json.dumps(
            {
                "day": DAY,
                "probes": [
                    {k: v for k, v in st.items() if k != "calls"} | {"calls": st["calls"]}
                    for st in results
                ],
                "best": best["name"] if best else None,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {md}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
