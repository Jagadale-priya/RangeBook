"""NIFTY + SENSEX live logics · last 30 sessions · per-day report.

NIFTY (unchanged proven/champ dual gates):
  - CHAMP_PLUS Calls board (±30 Cap4)
  - Confident afternoon thrust BUY (not proven_100) when dual silent
SENSEX:
  - Locked dual+fb bf>=0.20 · ±50

  python -u prod_live/tests/builders/_replay_nifty_sensex_live_30d.py
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
os.environ.setdefault("ENABLE_NIFTY_AFTERNOON_THRUST", "1")
os.environ.setdefault("ENABLE_SENSEX_FINAL_LIVE", "1")
import path_setup  # noqa: F401,E402

import kite_data  # noqa: E402
import nifty_afternoon_thrust as nat  # noqa: E402
import sensex_live_dual_track as sx_dual  # noqa: E402
from prod_live.logic import sensex_final_live as sx  # noqa: E402
from prod_live.logic.champ_plus_live import load_live_book, DESK as CHAMP_DESK  # noqa: E402
from research_bn_sensex_final_brackets import score_one  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "NIFTY_SENSEX_LIVE_30D.md"
OUT_JSON = OUT / "NIFTY_SENSEX_LIVE_30D.json"
OUT_BY_DAY = OUT / "NIFTY_SENSEX_LIVE_30D_BY_DAY.md"
SESSIONS = 30
PULL_DAYS = 50
SX_SL = SX_T1 = float(sx.BRACKETS["sl"])
NF_SL = NF_T1 = 30.0
TAPE_DIR = ROOT / "stock_signal_data" / "fno_validate"
TAPE_MAP = {
    ("NIFTY", "5minute"): TAPE_DIR / "NIFTY_5m_kite.csv",
    ("NIFTY", "15minute"): TAPE_DIR / "NIFTY_15m_kite.csv",
    ("SENSEX", "5minute"): TAPE_DIR / "SENSEX_5m_kite.csv",
    ("SENSEX", "15minute"): TAPE_DIR / "SENSEX_15m_kite.csv",
}


def norm(df: pd.DataFrame) -> pd.DataFrame:
    w = df.copy()
    if not isinstance(w.index, pd.DatetimeIndex):
        w.index = pd.to_datetime(w.index)
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


def resample_15(df5: pd.DataFrame) -> pd.DataFrame:
    ohlc = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
    }
    if "Volume" in df5.columns:
        ohlc["Volume"] = "sum"
    out = df5.resample("15min", label="left", closed="left").agg(ohlc).dropna(subset=["Open", "Close"])
    return norm(out)


def load_tape(symbol: str, interval: str, *, tail_days: int = 80) -> pd.DataFrame:
    path = TAPE_MAP.get((symbol, interval))
    if path is None or not path.exists():
        raise RuntimeError(f"No local tape for {symbol} {interval}")
    raw = pd.read_csv(path, index_col=0, parse_dates=True)
    w = norm(raw)
    if tail_days and len(w):
        cut = w.index.max() - pd.Timedelta(days=int(tail_days))
        w = w[w.index >= cut]
    return w


def pull(symbol: str, interval: str, days: int) -> Tuple[pd.DataFrame, str]:
    """Prefer live Kite; fall back to local kite CSV tapes (resample 15m from 5m if thin)."""
    src = "kite"
    try:
        df, err = kite_data.fetch_historical_candles(
            symbol, interval=interval, days=days, keep_partial=True
        )
        if not err and df is not None and not df.empty:
            return norm(df), src
        print(f"  kite miss {symbol} {interval}: {err} → tape", flush=True)
    except Exception as exc:
        print(f"  kite err {symbol} {interval}: {exc} → tape", flush=True)

    src = "tape"
    if interval == "15minute":
        # Prefer full 5m→15m so last sessions are complete (15m tapes often truncate).
        try:
            df5 = load_tape(symbol, "5minute")
            return resample_15(df5), "tape5→15"
        except Exception:
            return load_tape(symbol, "15minute"), src
    return load_tape(symbol, "5minute"), src


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


def day_stats(rows: List[dict]) -> Dict[str, Any]:
    known = [r for r in rows if r.get("win") is not None]
    return {
        "n": len(rows),
        "hit_pct": hit(rows),
        "wins": sum(1 for r in known if r.get("win")),
        "losses": sum(1 for r in known if r.get("win") is False),
        "open": len(rows) - len(known),
        "points": round(sum(float(r.get("points") or 0) for r in known), 1),
    }


def score_rows(rows: List[dict], bars5: pd.DataFrame, sl: float, t1: float) -> List[dict]:
    sc = bars5.copy()
    if sc.index.tz is not None:
        sc.index = sc.index.tz_localize(None)
    ix = build_ix(sc)
    out = []
    for r in rows:
        s = score_one(sc, ix, r["day"], str(r.get("hm") or ""), str(r.get("decision") or ""), sl, t1)
        rr = dict(r)
        if s:
            rr.update(s)
        out.append(rr)
    return out


def replay_sensex(bars15: pd.DataFrame, days: List[str]) -> List[dict]:
    from prod_live.logic import sensex_everyday_fallback as sx_fb

    picks = []
    for day in days:
        d15 = bars15[bars15.index.strftime("%Y-%m-%d") == day]
        prev = None
        fb_taken = False
        for ts, row in d15.iterrows():
            asof = pd.Timestamp(ts)
            hm = asof.tz_convert("Asia/Kolkata").strftime("%H:%M")
            window = bars15[bars15.index <= asof].tail(100)
            if len(window) < 20:
                continue
            dual_payload = None
            try:
                ev = sx_dual.evaluate(window, asof=asof.to_pydatetime(), price=float(row["Close"]))
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
                if key != prev:
                    entry = float(dual_payload.get("entry") or row["Close"])
                    lv = sx.levels(entry, side)
                    picks.append(
                        {
                            "symbol": "SENSEX",
                            "day": day,
                            "hm": hm,
                            "decision": side,
                            "source": "dual",
                            "track": track,
                            "entry": entry,
                            "sl_pts": SX_SL,
                            "t1_pts": SX_T1,
                            **{k: lv[k] for k in ("stop_loss", "target_1")},
                        }
                    )
                prev = key
            else:
                prev = None
            if not fb_taken and hm >= "09:45":
                try:
                    fb = sx_fb.or_fallback_call(window, asof=asof.to_pydatetime(), price=float(row["Close"]))
                except Exception:
                    fb = None
                if isinstance(fb, dict) and fb.get("decision") in ("BUY", "SELL"):
                    fb_taken = True
                    fb_side = str(fb["decision"]).upper()
                    fb_hm = str(fb.get("hm") or "09:45")[:5]
                    merged = False
                    for i, r in enumerate(picks):
                        if r["day"] == day and r["hm"] in (fb_hm, hm) and r["decision"] == fb_side and r["source"] == "dual":
                            picks[i] = {**r, "source": "dual+fallback", "track": "dual_fb_combined"}
                            merged = True
                            break
                    if not merged:
                        entry = float(fb.get("entry") or row["Close"])
                        lv = sx.levels(entry, fb_side)
                        picks.append(
                            {
                                "symbol": "SENSEX",
                                "day": day,
                                "hm": fb_hm,
                                "decision": fb_side,
                                "source": "fallback",
                                "track": "or_fallback",
                                "entry": entry,
                                "sl_pts": SX_SL,
                                "t1_pts": SX_T1,
                                **{k: lv[k] for k in ("stop_loss", "target_1")},
                            }
                        )
    return picks


def replay_nifty_confident_thrust(bars15: pd.DataFrame, days: List[str]) -> List[dict]:
    picks = []
    for day in days:
        d15 = bars15[bars15.index.strftime("%Y-%m-%d") == day]
        fired = False
        for ts, row in d15.iterrows():
            if fired:
                break
            hm = pd.Timestamp(ts).tz_convert("Asia/Kolkata").strftime("%H:%M")
            if hm < "13:15" or hm > "14:45":
                continue
            window = bars15[bars15.index <= ts]
            ev = nat.evaluate(window, asof=pd.Timestamp(ts).to_pydatetime(), price=float(row["Close"]))
            if not ev:
                continue
            picks.append(
                {
                    "symbol": "NIFTY",
                    "day": day,
                    "hm": hm,
                    "decision": "BUY",
                    "source": "confident_afternoon",
                    "track": ev.get("track") or "confident",
                    "entry": ev.get("entry"),
                    "stop_loss": ev.get("stop_loss"),
                    "target_1": ev.get("target_1"),
                    "sl_pts": NF_SL,
                    "t1_pts": NF_T1,
                    "accuracy_label": ev.get("accuracy_label"),
                    "uplift_from_13": ev.get("uplift_from_13"),
                }
            )
            fired = True
    return picks


def nifty_champ_plus(days: List[str]) -> List[dict]:
    book = load_live_book()
    dayset = set(days)
    out = []
    for r in book:
        day = str(r.get("day") or "")[:10]
        if day not in dayset:
            continue
        side = str(r.get("decision") or r.get("side") or "").upper()
        if side not in ("BUY", "SELL"):
            continue
        out.append(
            {
                "symbol": "NIFTY",
                "day": day,
                "hm": str(r.get("hm") or "")[:5],
                "decision": side,
                "source": "champ_plus",
                "track": r.get("track") or CHAMP_DESK,
                "entry": r.get("entry"),
                "stop_loss": r.get("stop_loss"),
                "target_1": r.get("target_1"),
                "sl_pts": NF_SL,
                "t1_pts": NF_T1,
                "win": r.get("win"),
                "points": r.get("points"),
                "outcome": r.get("outcome"),
            }
        )
    return out


def merge_nifty(champ: List[dict], thrust: List[dict]) -> List[dict]:
    """Board = CHAMP_PLUS ∪ confident afternoon (no drop of either; dedupe exact day+hm+side)."""
    seen = set()
    out = []
    for r in sorted(champ + thrust, key=lambda x: (x["day"], x.get("hm") or "")):
        k = (r["day"], str(r.get("hm") or "")[:5], r["decision"])
        if k in seen:
            # prefer champ_plus row if duplicate slot
            continue
        seen.add(k)
        out.append(r)
    return out


def write_by_day(payload: dict) -> Path:
    rows = []
    for r in payload["nifty"]["calls"]:
        rows.append({**r, "symbol": "NIFTY"})
    for r in payload["sensex"]["calls"]:
        rows.append({**r, "symbol": "SENSEX"})
    rows.sort(key=lambda x: (x.get("day") or "", x.get("hm") or "", x.get("symbol") or ""))
    by = defaultdict(list)
    for r in rows:
        by[r["day"]].append(r)
    all_days = sorted(
        set(list(payload["nifty"]["by_day"]) + list(payload["sensex"]["by_day"]))
    )
    start, end = payload["window"]["start"], payload["window"]["end"]
    lines = [
        "# NIFTY + SENSEX · live 30d · each day · date/time sorted",
        "",
        f"**Window:** `{start}` → `{end}`",
        f"**NIFTY:** {payload['nifty']['overall']['n']} @ {payload['nifty']['overall']['hit_pct']}% · "
        f"**SENSEX:** {payload['sensex']['overall']['n']} @ {payload['sensex']['overall']['hit_pct']}%",
        f"**Sources:** NIFTY champ_plus + confident afternoon · SENSEX dual+fb ±50",
        "",
    ]
    for day in all_days:
        rs = by.get(day) or []
        lines.append(f"## {day}")
        lines.append("")
        if not rs:
            lines.append("_No calls_")
            lines.append("")
            continue
        lines.append("| Time | Symbol | Side | Source | Track | Win | Pts |")
        lines.append("|---|---|---|---|---|---|---:|")
        for r in rs:
            w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "?")
            lines.append(
                f"| {r.get('hm')} | **{r.get('symbol')}** | {r.get('decision')} | "
                f"{r.get('source')} | {r.get('track')} | {w} | {r.get('points')} |"
            )
        lines.append("")
    OUT_BY_DAY.write_text("\n".join(lines), encoding="utf-8")
    return OUT_BY_DAY


def main() -> int:
    print(f"NIFTY+SENSEX live 30d · confident afternoon on NIFTY (not proven)", flush=True)
    print("Pull bars (Kite → local tape fallback)…", flush=True)
    nf15, nf15_src = pull("NIFTY", "15minute", PULL_DAYS)
    nf5, nf5_src = pull("NIFTY", "5minute", PULL_DAYS)
    sx15, sx15_src = pull("SENSEX", "15minute", PULL_DAYS)
    sx5, sx5_src = pull("SENSEX", "5minute", PULL_DAYS)
    print(
        f"  sources nf15={nf15_src} nf5={nf5_src} sx15={sx15_src} sx5={sx5_src}",
        flush=True,
    )

    # Use last SESSIONS fully populated session days (need afternoon bars for thrust)
    def session_days(bars: pd.DataFrame) -> List[str]:
        if bars is None or bars.empty:
            return []
        counts = bars.groupby(bars.index.strftime("%Y-%m-%d")).size()
        return [d for d, n in counts.items() if int(n) >= 8]

    days_nf = session_days(nf15)[-SESSIONS:]
    days_sx = session_days(sx15)[-SESSIONS:]
    # align to intersection for side-by-side table
    days = sorted(set(days_nf) & set(days_sx))[-SESSIONS:]
    if len(days) < SESSIONS:
        days = sorted(set(days_nf) | set(days_sx))[-SESSIONS:]
    print(f"Sessions {len(days)} · {days[0]} → {days[-1]}", flush=True)

    print("NIFTY CHAMP_PLUS + confident afternoon…", flush=True)
    champ = nifty_champ_plus(days)
    thrust = replay_nifty_confident_thrust(nf15, days)
    # re-score thrust; keep champ wins from book when present else path-score
    thrust_sc = score_rows(thrust, nf5, NF_SL, NF_T1)
    champ_need = [r for r in champ if r.get("win") is None]
    if champ_need:
        scored_c = score_rows(champ_need, nf5, NF_SL, NF_T1)
        byk = {(r["day"], r["hm"], r["decision"]): r for r in scored_c}
        for i, r in enumerate(champ):
            k = (r["day"], r["hm"], r["decision"])
            if r.get("win") is None and k in byk:
                champ[i] = {**r, **{x: byk[k].get(x) for x in ("win", "points", "outcome", "hm")}}
    nifty = merge_nifty(champ, thrust_sc)

    print("SENSEX dual+fb…", flush=True)
    sensex = score_rows(replay_sensex(sx15, days), sx5, SX_SL, SX_T1)

    nf_st = day_stats(nifty)
    sx_st = day_stats(sensex)
    print(
        f"NIFTY n={nf_st['n']} hit={nf_st['hit_pct']}% (champ={len(champ)} confident_aft={len(thrust_sc)})",
        flush=True,
    )
    print(f"SENSEX n={sx_st['n']} hit={sx_st['hit_pct']}%", flush=True)

    by_nf: Dict[str, List[dict]] = defaultdict(list)
    by_sx: Dict[str, List[dict]] = defaultdict(list)
    for r in nifty:
        by_nf[r["day"]].append(r)
    for r in sensex:
        by_sx[r["day"]].append(r)

    lines = [
        "# NIFTY + SENSEX · live logic · last 30 sessions · per day",
        "",
        f"**Window:** `{days[0]}` → `{days[-1]}` · {len(days)} sessions",
        "",
        "## What runs (no proven change)",
        "",
        "| Symbol | Live path | Brackets |",
        "|---|---|---|",
        f"| **NIFTY** | CHAMP_PLUS board + **confident** afternoon thrust (not proven_100) | ±30 |",
        f"| **SENSEX** | dual + OR fallback bf≥20% · `{sx.DESK_CHAMP}` | ±50 |",
        "",
        "Proven_100 / 13:00 cut **unchanged**. Afternoon thrust only fills when dual silent · confident tag.",
        "",
        "## Headline",
        "",
        "| Symbol | N | Hit% | W/L/O | Pts | Notes |",
        "|---|---:|---:|---|---:|---|",
        f"| **NIFTY** | {nf_st['n']} | **{nf_st['hit_pct']}** | "
        f"{nf_st['wins']}/{nf_st['losses']}/{nf_st['open']} | {nf_st['points']} | "
        f"champ_plus {len(champ)} · confident_aft {len(thrust_sc)} |",
        f"| **SENSEX** | {sx_st['n']} | **{sx_st['hit_pct']}** | "
        f"{sx_st['wins']}/{sx_st['losses']}/{sx_st['open']} | {sx_st['points']} | dual+fb |",
        "",
        "## Per day",
        "",
        "| Day | NIFTY N | NF Hit | NF W/L | SENSEX N | SX Hit | SX W/L |",
        "|---|---:|---:|---|---:|---:|---|",
    ]
    for d in days:
        ns = day_stats(by_nf.get(d) or [])
        ss = day_stats(by_sx.get(d) or [])
        lines.append(
            f"| **{d}** | {ns['n']} | {ns['hit_pct'] if ns['hit_pct'] is not None else '—'} | "
            f"{ns['wins']}/{ns['losses']} | {ss['n']} | "
            f"{ss['hit_pct'] if ss['hit_pct'] is not None else '—'} | {ss['wins']}/{ss['losses']} |"
        )

    lines += [
        "",
        "## NIFTY calls",
        "",
        "| Day | HM | Side | Source | Track | Win | Pts |",
        "|---|---|---|---|---|---|---:|",
    ]
    for r in sorted(nifty, key=lambda x: (x["day"], x.get("hm") or "")):
        w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "?")
        lines.append(
            f"| {r['day']} | {r.get('hm')} | {r.get('decision')} | {r.get('source')} | "
            f"{r.get('track')} | {w} | {r.get('points')} |"
        )
    if not nifty:
        lines.append("| — | — | — | — | — | — | — |")

    lines += [
        "",
        "## SENSEX calls",
        "",
        "| Day | HM | Side | Source | Track | Win | Pts |",
        "|---|---|---|---|---|---|---:|",
    ]
    for r in sorted(sensex, key=lambda x: (x["day"], x.get("hm") or "")):
        w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "?")
        lines.append(
            f"| {r['day']} | {r.get('hm')} | {r.get('decision')} | {r.get('source')} | "
            f"{r.get('track')} | {w} | {r.get('points')} |"
        )
    if not sensex:
        lines.append("| — | — | — | — | — | — | — |")

    lines += ["", "_Generated by `_replay_nifty_sensex_live_30d.py`_", ""]

    payload = {
        "window": {"start": days[0], "end": days[-1], "sessions": len(days)},
        "sources": {
            "nifty_15m": nf15_src,
            "nifty_5m": nf5_src,
            "sensex_15m": sx15_src,
            "sensex_5m": sx5_src,
        },
        "nifty": {
            "overall": nf_st,
            "champ_plus_n": len(champ),
            "confident_afternoon_n": len(thrust_sc),
            "by_day": {d: day_stats(by_nf.get(d) or []) for d in days},
            "calls": nifty,
        },
        "sensex": {
            "overall": sx_st,
            "desk": sx.DESK_CHAMP,
            "by_day": {d: day_stats(by_sx.get(d) or []) for d in days},
            "calls": sensex,
        },
        "notes": {
            "proven_100_unchanged": True,
            "afternoon_on_confident_tag": True,
            "sensex_unchanged": True,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    by_day_path = write_by_day(payload)
    print(f"Wrote {OUT_MD}", flush=True)
    print(f"Wrote {by_day_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
