"""FINAL accuracy research — NIFTY Cap6 + SENSEX T50 → near-100% causal gates.

Honest rules (no fake 100%):
  · Gates use ONLY live-known fields: p_t1, track, hm, or_ext, first_break, side, day-cap
  · Never filter on historical `win`
  · Every kept call is re-settled on 5m tape (±30 NIFTY / ±50 SENSEX)
  · Primary window: last 20 sessions
  · OOS check: prior 40 sessions (same gate, no retune)

  python -u prod_live/tests/builders/research_nifty_sensex_100pct_last20.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "prod_live"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
import path_setup  # noqa: F401,E402

OUT = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT / "NIFTY_SENSEX_100PCT_LAST20_FINAL.md"
OUT_JSON = OUT / "NIFTY_SENSEX_100PCT_LAST20_FINAL.json"

NIFTY_CALLS = (
    ROOT / "prod_live" / "holding_accurate" / "champion_plus" / "t30_sl30_5y_calls.json"
)
SENSEX_CALLS = (
    ROOT
    / "prod_live"
    / "holding_accurate"
    / "sensex_final"
    / "champ_plus_t50_sl50_calls.json"
)
NIFTY_5M = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
SENSEX_5M = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_5m_kite.csv"

NIFTY_SL = NIFTY_T1 = 30.0
SENSEX_SL = SENSEX_T1 = 50.0


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    w = df.copy()
    if getattr(w.index, "tz", None) is not None:
        w.index = w.index.tz_convert("Asia/Kolkata")
    else:
        w.index = w.index.tz_localize("Asia/Kolkata")
    w = w.rename(columns={c: str(c).title() for c in w.columns})
    cols = [c for c in ("Open", "High", "Low", "Close") if c in w.columns]
    w = w[cols].astype(float).sort_index()
    w = w[~w.index.duplicated(keep="last")]
    hm = w.index.strftime("%H:%M")
    return w[(hm >= "09:15") & (hm <= "15:30")]


def build_bar_index(bars: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for d, g in bars.groupby(bars.index.strftime("%Y-%m-%d")):
        out[str(d)] = g
    return out


def side(r: dict) -> str:
    return str(r.get("decision") or r.get("side") or "").upper()


def key(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day") or "")[:10], side(r), str(r.get("hm") or "")[:5])


def settle_one(
    day_bars: pd.DataFrame,
    hm: str,
    sd: str,
    *,
    sl_pts: float,
    t1_pts: float,
) -> Optional[Dict[str, Any]]:
    """Causal path settle: first touch of SL vs T1 after entry bar (inclusive walk)."""
    if day_bars is None or day_bars.empty or sd not in ("BUY", "SELL"):
        return None
    times = day_bars.index.strftime("%H:%M")
    hits = [i for i, t in enumerate(times) if t == hm[:5]]
    if not hits:
        # nearest bar at/after hm
        after = [i for i, t in enumerate(times) if t >= hm[:5]]
        if not after:
            return None
        i0 = after[0]
    else:
        i0 = hits[0]
    entry = float(day_bars.iloc[i0]["Close"])
    if sd == "BUY":
        sl = entry - sl_pts
        t1 = entry + t1_pts
    else:
        sl = entry + sl_pts
        t1 = entry - t1_pts
    for j in range(i0 + 1, len(day_bars)):
        hi = float(day_bars.iloc[j]["High"])
        lo = float(day_bars.iloc[j]["Low"])
        if sd == "BUY":
            hit_sl = lo <= sl
            hit_t1 = hi >= t1
        else:
            hit_sl = hi >= sl
            hit_t1 = lo <= t1
        if hit_sl and hit_t1:
            return {
                "win": False,
                "points": -sl_pts,
                "outcome": "same_bar_both",
                "entry": entry,
                "stop_loss": sl,
                "target_1": t1,
            }
        if hit_sl:
            return {
                "win": False,
                "points": -sl_pts,
                "outcome": "sl_before_t1",
                "entry": entry,
                "stop_loss": sl,
                "target_1": t1,
            }
        if hit_t1:
            return {
                "win": True,
                "points": t1_pts,
                "outcome": "t1_before_sl",
                "entry": entry,
                "stop_loss": sl,
                "target_1": t1,
            }
    # session end — mark open as not settled win
    last = float(day_bars.iloc[-1]["Close"])
    if sd == "BUY":
        pts = last - entry
    else:
        pts = entry - last
    return {
        "win": pts > 0,
        "points": round(pts, 2),
        "outcome": "session_end",
        "entry": entry,
        "stop_loss": sl,
        "target_1": t1,
    }


def load_calls(path: Path) -> List[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "calls" in raw:
        rows = list(raw["calls"])
    elif isinstance(raw, list):
        rows = list(raw)
    else:
        raise ValueError(f"bad calls file: {path}")
    out = []
    for r in rows:
        sd = side(r)
        if sd not in ("BUY", "SELL"):
            continue
        day = str(r.get("day") or "")[:10]
        hm = str(r.get("hm") or "")[:5]
        if not day or not hm:
            continue
        out.append(dict(r))
    return out


def resettle(
    rows: List[dict],
    by_day: Dict[str, pd.DataFrame],
    *,
    sl_pts: float,
    t1_pts: float,
) -> List[dict]:
    out: List[dict] = []
    for r in rows:
        day = str(r.get("day") or "")[:10]
        db = by_day.get(day)
        s = settle_one(db, str(r.get("hm") or ""), side(r), sl_pts=sl_pts, t1_pts=t1_pts)
        if not s:
            continue
        rr = dict(r)
        rr.update(s)
        rr["decision"] = side(r)
        rr["side"] = side(r)
        rr["p_t1"] = float(r.get("p_t1") or 0)
        rr["track"] = str(r.get("track") or "")
        rr["or_ext"] = float(r["or_ext"]) if r.get("or_ext") is not None else None
        fb = r.get("first_break")
        rr["first_break"] = bool(fb) if fb is not None else None
        out.append(rr)
    return out


def session_list(rows: List[dict]) -> List[str]:
    return sorted({str(r.get("day") or "")[:10] for r in rows})


def clip_days(rows: List[dict], days: Sequence[str]) -> List[dict]:
    ds = set(days)
    return [r for r in rows if str(r.get("day") or "")[:10] in ds]


def agg(rows: List[dict], *, t1: float, sl: float) -> Dict[str, Any]:
    known = [r for r in rows if r.get("win") is not None]
    n = len(known)
    w = sum(1 for r in known if r.get("win"))
    return {
        "n": n,
        "wins": w,
        "losses": n - w,
        "hit_pct": round(100.0 * w / n, 2) if n else None,
        "points": round(sum(float(r.get("points") or (t1 if r.get("win") else -sl)) for r in known), 1),
        "sessions": len({str(r.get("day") or "")[:10] for r in known}),
        "buy_n": sum(1 for r in known if side(r) == "BUY"),
        "sell_n": sum(1 for r in known if side(r) == "SELL"),
    }


def merge_cap(cur: List[dict], add: List[dict], cap: int) -> List[dict]:
    out = [dict(r) for r in cur]
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in out:
        by[str(r["day"])[:10]].append(r)
    for r in add:
        day = str(r["day"])[:10]
        ex = by.get(day, [])
        if len(ex) >= cap:
            continue
        if ex and side(ex[0]) != side(r):
            continue
        if any(key(x) == key(r) for x in ex):
            continue
        out.append(dict(r))
        by[day].append(r)
    return out


def fill(
    rows: List[dict],
    cap: int,
    *,
    pmin: float = 0.0,
    tracks: Optional[Set[str]] = None,
    hm_lo: Optional[str] = None,
    hm_hi: Optional[str] = None,
    buy_p: Optional[float] = None,
    sell_p: Optional[float] = None,
    max_or_ext: Optional[float] = None,
    first_only: bool = False,
    sides: Optional[Set[str]] = None,
) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        p = float(r.get("p_t1") or 0)
        if p < pmin:
            continue
        tr = str(r.get("track") or "")
        if tracks is not None and tr not in tracks:
            continue
        h = str(r.get("hm") or "")[:5]
        if hm_lo and h < hm_lo:
            continue
        if hm_hi and h > hm_hi:
            continue
        sd = side(r)
        if sides is not None and sd not in sides:
            continue
        if buy_p is not None and sd == "BUY" and p < buy_p:
            continue
        if sell_p is not None and sd == "SELL" and p < sell_p:
            continue
        if max_or_ext is not None and r.get("or_ext") is not None:
            if float(r["or_ext"]) > max_or_ext:
                continue
        if first_only and r.get("first_break") is False:
            continue
        by[str(r["day"])[:10]].append(r)
    out: List[dict] = []
    for day in sorted(by):
        filled: List[dict] = []
        opts = sorted(by[day], key=lambda x: float(x.get("p_t1") or 0), reverse=True)
        for r in opts:
            trial = merge_cap(filled, [r], cap)
            if len(trial) > len(filled):
                filled = trial
            if len(filled) >= cap:
                break
        out.extend(filled)
    return out


def search_gates(
    pool: List[dict],
    *,
    t1: float,
    sl: float,
    label: str,
    min_n: int = 5,
) -> List[dict]:
    tracks_opts: List[Optional[Set[str]]] = [
        None,
        {"champion"},
        {"champion", "proven_research"},
        {"champion", "proven_research", "dual10m"},
        {"champion", "good_prod2", "proven_research"},
        {"dual10m"},
        {"good_prod2"},
    ]
    pmins = [0.55, 0.58, 0.60, 0.62, 0.65, 0.70, 0.75, 0.80, 0.85]
    caps = [1, 2, 3]
    hm_windows = [
        (None, None),
        ("09:30", "14:30"),
        ("10:00", "14:00"),
        ("09:45", "13:30"),
        ("10:00", "13:00"),
    ]
    or_exts: List[Optional[float]] = [None, 0.10, 0.15, 0.20, 0.30]
    first_opts = [False, True]
    side_opts: List[Optional[Set[str]]] = [None, {"BUY"}, {"SELL"}]
    buy_sell_floors = [
        (None, None),
        (0.55, 0.62),
        (0.60, 0.65),
        (0.62, 0.70),
    ]

    results: List[dict] = []
    for cap in caps:
        for pmin in pmins:
            for tracks in tracks_opts:
                for hm_lo, hm_hi in hm_windows:
                    for max_or in or_exts:
                        for first_only in first_opts:
                            for sides in side_opts:
                                for buy_p, sell_p in buy_sell_floors:
                                    book = fill(
                                        pool,
                                        cap,
                                        pmin=pmin,
                                        tracks=tracks,
                                        hm_lo=hm_lo,
                                        hm_hi=hm_hi,
                                        buy_p=buy_p,
                                        sell_p=sell_p,
                                        max_or_ext=max_or,
                                        first_only=first_only,
                                        sides=sides,
                                    )
                                    st = agg(book, t1=t1, sl=sl)
                                    if not st["n"] or st["n"] < min_n:
                                        continue
                                    results.append(
                                        {
                                            "label": label,
                                            "cap": cap,
                                            "pmin": pmin,
                                            "tracks": sorted(tracks) if tracks else "ALL",
                                            "hm_lo": hm_lo or "*",
                                            "hm_hi": hm_hi or "*",
                                            "max_or_ext": max_or,
                                            "first_only": first_only,
                                            "sides": sorted(sides) if sides else "BOTH",
                                            "buy_p": buy_p,
                                            "sell_p": sell_p,
                                            **st,
                                        }
                                    )
    results.sort(
        key=lambda x: (
            -(x["hit_pct"] or 0),
            -x["n"],
            -x["points"],
        )
    )
    return results


def pick_best_100(results: List[dict], *, min_n: int = 5) -> Optional[dict]:
    perfect = [r for r in results if (r.get("hit_pct") or 0) >= 99.999 and r["n"] >= min_n]
    if perfect:
        return perfect[0]
    near = [r for r in results if (r.get("hit_pct") or 0) >= 95.0 and r["n"] >= min_n]
    return near[0] if near else (results[0] if results else None)


def gate_from_row(row: dict) -> Dict[str, Any]:
    tracks = row.get("tracks")
    if tracks == "ALL":
        tracks_set = None
    else:
        tracks_set = set(tracks)
    sides = row.get("sides")
    if sides == "BOTH":
        sides_set = None
    else:
        sides_set = set(sides)
    hm_lo = None if row.get("hm_lo") in (None, "*") else row.get("hm_lo")
    hm_hi = None if row.get("hm_hi") in (None, "*") else row.get("hm_hi")
    return {
        "cap": int(row["cap"]),
        "pmin": float(row["pmin"]),
        "tracks": tracks_set,
        "hm_lo": hm_lo,
        "hm_hi": hm_hi,
        "max_or_ext": row.get("max_or_ext"),
        "first_only": bool(row.get("first_only")),
        "sides": sides_set,
        "buy_p": row.get("buy_p"),
        "sell_p": row.get("sell_p"),
    }


def apply_gate(pool: List[dict], g: Dict[str, Any], *, t1: float, sl: float) -> Dict[str, Any]:
    book = fill(
        pool,
        int(g["cap"]),
        pmin=float(g["pmin"]),
        tracks=g.get("tracks"),
        hm_lo=g.get("hm_lo"),
        hm_hi=g.get("hm_hi"),
        buy_p=g.get("buy_p"),
        sell_p=g.get("sell_p"),
        max_or_ext=g.get("max_or_ext"),
        first_only=bool(g.get("first_only")),
        sides=g.get("sides"),
    )
    st = agg(book, t1=t1, sl=sl)
    st["calls"] = [
        {
            "day": r["day"],
            "hm": r["hm"],
            "side": side(r),
            "p_t1": round(float(r.get("p_t1") or 0), 4),
            "track": r.get("track"),
            "win": r.get("win"),
            "points": r.get("points"),
            "outcome": r.get("outcome"),
            "or_ext": r.get("or_ext"),
            "first_break": r.get("first_break"),
        }
        for r in sorted(book, key=lambda x: (str(x["day"]), str(x["hm"])))
    ]
    return st


def research_index(
    name: str,
    calls_path: Path,
    tape_path: Path,
    *,
    sl: float,
    t1: float,
    live_policy: Dict[str, Any],
) -> Dict[str, Any]:
    print(f"\n=== {name} ===", flush=True)
    if not calls_path.exists():
        return {"ok": False, "error": f"missing {calls_path}"}
    if not tape_path.exists():
        return {"ok": False, "error": f"missing {tape_path}"}

    bars = _norm(pd.read_csv(tape_path, index_col=0, parse_dates=True))
    by_day = build_bar_index(bars)
    raw = load_calls(calls_path)
    # Keep only days present on tape
    raw = [r for r in raw if str(r.get("day") or "")[:10] in by_day]
    days_all = session_list(raw)
    if len(days_all) < 25:
        # fallback: use tape sessions that have any call
        days_all = session_list(raw)
    last20 = days_all[-20:]
    prior40 = days_all[-60:-20] if len(days_all) >= 60 else days_all[:-20]

    print(f"  tape days with calls: {len(days_all)} · last20={last20[0]}→{last20[-1]}", flush=True)
    pool_all = resettle(raw, by_day, sl_pts=sl, t1_pts=t1)
    pool20 = clip_days(pool_all, last20)
    pool_oos = clip_days(pool_all, prior40)

    base20 = apply_gate(pool20, live_policy, t1=t1, sl=sl)
    base_oos = apply_gate(pool_oos, live_policy, t1=t1, sl=sl) if prior40 else None
    open20 = agg(pool20, t1=t1, sl=sl)

    print(f"  open Cap pool last20: {open20}", flush=True)
    print(f"  live policy last20: { {k: base20[k] for k in ('n','hit_pct','wins','losses','points')} }", flush=True)

    t_search = time.time()
    results = search_gates(pool20, t1=t1, sl=sl, label=name, min_n=5)
    # also allow sparse perfect books N>=3
    results_sparse = search_gates(pool20, t1=t1, sl=sl, label=name, min_n=3)
    print(f"  searched {len(results)} / sparse {len(results_sparse)} in {time.time()-t_search:.1f}s", flush=True)

    best100 = pick_best_100(results, min_n=5) or pick_best_100(results_sparse, min_n=3)
    best_dense = None
    for r in results:
        if r["n"] >= 10 and (r.get("hit_pct") or 0) >= 90:
            best_dense = r
            break
    if best_dense is None:
        for r in results:
            if r["n"] >= 8:
                best_dense = r
                break

    out: Dict[str, Any] = {
        "ok": True,
        "name": name,
        "sl": sl,
        "t1": t1,
        "last20": {"start": last20[0], "end": last20[-1], "n_sessions": len(last20)},
        "prior40": (
            {"start": prior40[0], "end": prior40[-1], "n_sessions": len(prior40)}
            if prior40
            else None
        ),
        "open_pool_last20": open20,
        "live_policy": live_policy,
        "live_policy_last20": {k: base20[k] for k in base20 if k != "calls"},
        "live_policy_last20_calls": base20.get("calls"),
        "live_policy_oos": (
            {k: base_oos[k] for k in base_oos if k != "calls"} if base_oos else None
        ),
        "top10_last20": results[:10],
        "perfect_last20": [r for r in results if (r.get("hit_pct") or 0) >= 99.999][:15],
        "perfect_sparse": [
            r for r in results_sparse if (r.get("hit_pct") or 0) >= 99.999
        ][:15],
    }

    if best100:
        g = gate_from_row(best100)
        is20 = apply_gate(pool20, g, t1=t1, sl=sl)
        oos = apply_gate(pool_oos, g, t1=t1, sl=sl) if prior40 else None
        out["best_accuracy_gate"] = {
            "spec": {
                **{k: (sorted(v) if isinstance(v, set) else v) for k, v in g.items()},
                "hit_row": best100,
            },
            "last20": {k: is20[k] for k in is20 if k != "calls"},
            "last20_calls": is20.get("calls"),
            "oos_prior40": ({k: oos[k] for k in oos if k != "calls"} if oos else None),
            "oos_calls": (oos.get("calls") if oos else None),
        }
        print(
            f"  BEST ACC: n={is20['n']} hit={is20['hit_pct']}% · OOS={None if not oos else oos['hit_pct']}%",
            flush=True,
        )

    if best_dense and (
        not best100
        or best_dense.get("n", 0) > (best100.get("n") or 0)
        or (best_dense.get("hit_pct") or 0) < 99.999
    ):
        g2 = gate_from_row(best_dense)
        is20 = apply_gate(pool20, g2, t1=t1, sl=sl)
        oos = apply_gate(pool_oos, g2, t1=t1, sl=sl) if prior40 else None
        out["best_dense_gate"] = {
            "spec": {
                **{k: (sorted(v) if isinstance(v, set) else v) for k, v in g2.items()},
                "hit_row": best_dense,
            },
            "last20": {k: is20[k] for k in is20 if k != "calls"},
            "last20_calls": is20.get("calls"),
            "oos_prior40": ({k: oos[k] for k in oos if k != "calls"} if oos else None),
        }

    return out


def md_gate(g: Optional[dict]) -> str:
    if not g:
        return "_none_"
    s = g.get("spec") or {}
    return (
        f"cap={s.get('cap')} · p≥{s.get('pmin')} · tracks={s.get('tracks')} · "
        f"hm={s.get('hm_lo')}-{s.get('hm_hi')} · or_ext≤{s.get('max_or_ext')} · "
        f"first_only={s.get('first_only')} · sides={s.get('sides')} · "
        f"buy_p={s.get('buy_p')} sell_p={s.get('sell_p')}"
    )


def write_report(nifty: dict, sensex: dict) -> None:
    lines = [
        "# NIFTY + SENSEX · FINAL 100% accuracy research (last 20 sessions)",
        "",
        f"**Generated:** `{datetime.now().isoformat(timespec='seconds')}`",
        "",
        "## Method (accurate / live-safe)",
        "",
        "- Universe = locked live desks: **NIFTY CHAMP_PLUS Cap6 ±30** · **SENSEX T50 Cap3 ±50**",
        "- Every call **re-settled on 5m kite tape** (first touch SL vs T1)",
        "- Gates use only: `p_t1`, `track`, `hm`, `or_ext`, `first_break`, side floors, day-cap",
        "- **Never** filter on historical `win` (fake 100% forbidden)",
        "- Primary measure: **last 20 sessions**",
        "- Honesty check: same gate on **prior 40 sessions** (OOS, no retune)",
        "",
        "## Verdict up front",
        "",
    ]

    def verdict(block: dict, title: str) -> None:
        lines.append(f"### {title}")
        if not block.get("ok"):
            lines.append(f"- ERROR: {block.get('error')}")
            lines.append("")
            return
        live = block.get("live_policy_last20") or {}
        best = block.get("best_accuracy_gate") or {}
        b20 = best.get("last20") or {}
        oos = best.get("oos_prior40") or {}
        lines.append(
            f"- Live policy last20: **{live.get('n')} @ {live.get('hit_pct')}%** "
            f"(W/L {live.get('wins')}/{live.get('losses')})"
        )
        if best:
            lines.append(f"- Best accuracy gate: `{md_gate(best)}`")
            lines.append(
                f"- Last20: **{b20.get('n')} @ {b20.get('hit_pct')}%** "
                f"(W/L {b20.get('wins')}/{b20.get('losses')}, pts {b20.get('points')})"
            )
            if oos:
                lines.append(
                    f"- OOS prior40: **{oos.get('n')} @ {oos.get('hit_pct')}%** "
                    f"(W/L {oos.get('wins')}/{oos.get('losses')})"
                )
            hit = b20.get("hit_pct")
            oos_hit = oos.get("hit_pct") if oos else None
            if hit == 100 and oos and oos_hit == 100:
                lines.append("- **LOCK CANDIDATE:** 100% last20 + 100% OOS")
            elif hit == 100 and oos and (oos_hit or 0) >= 95:
                lines.append("- **STRONG:** 100% last20 · OOS ≥95% (prefer this over volume)")
            elif hit == 100:
                lines.append(
                    "- **IN-SAMPLE 100% only** — OOS not perfect; use as sparse desk, not claim forever-100%"
                )
            else:
                lines.append("- No causal 100% book with enough volume on last20")
        lines.append("")

    verdict(nifty, "NIFTY")
    verdict(sensex, "SENSEX")

    for block, title, t1 in (
        (nifty, "NIFTY detail", 30),
        (sensex, "SENSEX detail", 50),
    ):
        if not block.get("ok"):
            continue
        lines += [
            f"## {title}",
            "",
            f"Window last20: `{block['last20']['start']}` → `{block['last20']['end']}` "
            f"({block['last20']['n_sessions']} sessions)",
            "",
            "### Open pool vs live policy (last20)",
            "",
            f"- Open resettled pool: `{block.get('open_pool_last20')}`",
            f"- Live policy: `{block.get('live_policy_last20')}`",
            "",
            "### Top causal gates (last20, N≥5)",
            "",
            "| Cap | pmin | Tracks | HM | or≤ | first | sides | N | Hit% | W/L | Pts |",
            "|---:|---:|---|---|---:|---|---|---:|---:|---|---:|",
        ]
        for r in (block.get("top10_last20") or [])[:10]:
            lines.append(
                f"| {r['cap']} | {r['pmin']} | {r['tracks']} | {r['hm_lo']}-{r['hm_hi']} | "
                f"{r['max_or_ext']} | {r['first_only']} | {r['sides']} | {r['n']} | "
                f"**{r['hit_pct']}** | {r['wins']}/{r['losses']} | {r['points']} |"
            )
        best = block.get("best_accuracy_gate")
        if best:
            lines += [
                "",
                "### Best accuracy calls (last20)",
                "",
                "| Day | HM | Side | p | Track | Win | Pts | Outcome |",
                "|---|---|---|---:|---|---|---:|---|",
            ]
            for c in best.get("last20_calls") or []:
                lines.append(
                    f"| {c['day']} | {c['hm']} | {c['side']} | {c['p_t1']} | {c['track']} | "
                    f"{'W' if c['win'] else 'L'} | {c['points']} | {c['outcome']} |"
                )
        dense = block.get("best_dense_gate")
        if dense:
            lines += [
                "",
                "### Best denser ≥90% gate (if any)",
                "",
                f"- Spec: `{md_gate(dense)}`",
                f"- Last20: `{dense.get('last20')}`",
                f"- OOS: `{dense.get('oos_prior40')}`",
                "",
            ]

    lines += [
        "## What this means for live",
        "",
        "1. Keep **scalper PA `pa_no_trap`** unchanged (separate desk).",
        "2. For NIFTY/SENSEX **Calls board**: prefer the **best accuracy gate** over Cap6/T50 volume.",
        "3. If OOS is also ≥95–100%, that gate is the final lock candidate.",
        "4. If only last20 is 100%, ship as **sparse high-accuracy mode** (Cap1 / high p) — do not claim eternal 100%.",
        "",
        f"JSON: `{OUT_JSON}`",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    t0 = time.time()
    print("FINAL 100% research · NIFTY Cap6 + SENSEX T50 · last20 + OOS40", flush=True)

    nifty_live = {
        "cap": 6,
        "pmin": 0.0,
        "tracks": None,
        "hm_lo": None,
        "hm_hi": None,
        "max_or_ext": None,
        "first_only": False,
        "sides": None,
        "buy_p": None,
        "sell_p": None,
    }
    # Current Sensex lock: BUY first p≥0.55 or≤0.10 · SELL first p≥0.62 · Cap3
    sensex_live = {
        "cap": 3,
        "pmin": 0.55,
        "tracks": None,
        "hm_lo": None,
        "hm_hi": None,
        "max_or_ext": 0.10,
        "first_only": True,
        "sides": None,
        "buy_p": 0.55,
        "sell_p": 0.62,
    }

    nifty = research_index(
        "NIFTY_CHAMP_PLUS_CAP6",
        NIFTY_CALLS,
        NIFTY_5M,
        sl=NIFTY_SL,
        t1=NIFTY_T1,
        live_policy=nifty_live,
    )
    sensex = research_index(
        "SENSEX_T50_CAP3",
        SENSEX_CALLS,
        SENSEX_5M,
        sl=SENSEX_SL,
        t1=SENSEX_T1,
        live_policy=sensex_live,
    )

    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "method": {
            "resettle": "5m first-touch SL vs T1",
            "gates": "p_t1/track/hm/or_ext/first_break/side/cap only",
            "no_win_hindsight": True,
            "primary": "last_20_sessions",
            "oos": "prior_40_sessions",
        },
        "nifty": nifty,
        "sensex": sensex,
        "elapsed_s": round(time.time() - t0, 1),
    }
    # JSON-safe sets already converted in nested structures
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    write_report(nifty, sensex)
    print(f"\nWrote {OUT_MD}", flush=True)
    print(f"Wrote {OUT_JSON}", flush=True)
    print(f"Elapsed {time.time()-t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
