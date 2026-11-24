"""Larger-tape multi-window research: which logic stays most profitable?

Uses archive NIFTY 15m (12y/5y) for history beyond Kite's ~200d cap.
Compares prod1 / prod2 / A+ / PDF filters across consecutive 30-session blocks.

Also encodes weak-window diagnosis: lower hit on W1–W3 was regime/path
(RANGE, pre-10, non-first), not a broken harness.

  python -u tools/research/research_large_window_profit.py
  python -u tools/research/research_large_window_profit.py --sessions 240 --from-cache
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import pandas as pd

warnings.filterwarnings("ignore", category=DeprecationWarning)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "research"))

import fno_model
import fno_pdf_accuracy as acc
import research_pdf_deep_algo as deep

OUT = ROOT / "stock_signal_data" / "fno_validate" / "research"
CACHE = OUT / "large_window_candidates.json"
REPORT = OUT / "large_window_profit_report.json"


def _load_csv_bars() -> pd.DataFrame:
    for path in (
        ROOT / "stock_signal_data" / "fno_validate" / "archive" / "NIFTY_15m_12y.csv",
        ROOT / "stock_signal_data" / "fno_validate" / "archive" / "NIFTY_15m_5y.csv",
        ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_12y.csv",
        ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_5y.csv",
    ):
        if path.is_file():
            raw = pd.read_csv(path, index_col=0, parse_dates=True)
            print(f"csv {path.name} bars={len(raw)} {raw.index[0]}->{raw.index[-1]}", flush=True)
            return deep._norm(raw)
    raise SystemExit("need NIFTY_15m_12y.csv or NIFTY_15m_5y.csv under fno_validate/archive")


def _full_days(bars: pd.DataFrame, min_bars: int = 20) -> List:
    counts = pd.Series(bars.index.map(lambda t: t.date())).value_counts()
    return sorted(d for d, n in counts.items() if int(n) >= min_bars)


def _stats(rows: List[dict]) -> Dict[str, Any]:
    n = len(rows)
    if not n:
        return {"calls": 0, "t1": 0, "hit_pct": 0.0, "points": 0.0, "pts_per_call": 0.0}
    outs, pts = [], []
    for r in rows:
        o, p = deep._early(
            float(r["favor"]), float(r["against"]), float(r["risk"]), r["outcome"], float(r["points"])
        )
        outs.append(o)
        pts.append(p)
    t1 = sum(1 for o in outs if o == "t1_before_sl")
    return {
        "calls": n,
        "t1": t1,
        "hit_pct": round(100.0 * t1 / n, 1),
        "points": round(sum(pts), 1),
        "pts_per_call": round(sum(pts) / n, 1) if n else 0.0,
    }


def _issued(c: dict) -> bool:
    return bool(c.get("issued_prod")) and not c.get("bar_note")


def policies() -> Dict[str, Callable[[dict], bool]]:
    def floor52(c):
        return (
            float(c["score"]) >= 0.52
            and float(c.get("or_break") or 0) != 0
            and not c.get("bar_note")
        )

    def a_plus(c):
        return _issued(c) and acc.is_accuracy_plus(
            score=float(c["score"]),
            first_break=bool(c.get("first_break")),
            hour=float(c.get("hour") or 12),
            regime=str(c.get("regime") or ""),
            chase=bool(c.get("chase")),
            direction_ok=bool(c.get("direction_ok") or c.get("soft_direction")),
        )

    def no_pre10(c):
        return _issued(c) and float(c.get("hour") or 12) >= 10.0

    def first_only(c):
        return _issued(c) and bool(c.get("first_break"))

    def no_range(c):
        return _issued(c) and str(c.get("regime") or "").upper() != "RANGE"

    def trend_vol(c):
        return _issued(c) and str(c.get("regime") or "").upper() in ("TREND", "VOLATILE")

    def cboe_router(c):
        reg = str(c.get("regime") or "").upper()
        if not floor52(c):
            return False
        if reg == "RANGE":
            return float(c["score"]) >= 0.54 and bool(c.get("atm_like"))
        if 0.25 < float(c.get("or_ext") or 0) <= 0.55 and not c.get("first_break"):
            return False
        return True

    def calendar_settle(c):
        return floor52(c) and float(c.get("hour") or 12) >= 10.0 and (
            bool(c.get("first_break")) or bool(c.get("atm_like"))
        )

    def pdf_quality(c):
        """Compromise: issued + post-10 + no chase + direction (more calls than A+)."""
        return (
            _issued(c)
            and float(c.get("hour") or 12) >= 10.0
            and not c.get("chase")
            and bool(c.get("direction_ok") or c.get("soft_direction") or c.get("first_break"))
        )

    return {
        "prod1": lambda c: _issued(c),
        "a_plus": a_plus,
        "no_pre10": no_pre10,
        "first_only": first_only,
        "no_range": no_range,
        "trend_vol": trend_vol,
        "pdf_quality": pdf_quality,
        "cboe_router": cboe_router,
        "calendar_settle": calendar_settle,
        "floor52": floor52,
    }


def make_blocks(days: List, size: int) -> List[Tuple[str, List]]:
    rem = list(days)
    out = []
    i = 0
    while len(rem) >= size:
        chunk = rem[-size:]
        rem = rem[:-size]
        out.append((f"W{i}", chunk))
        i += 1
    if rem:
        out.append((f"W{i}p{len(rem)}", rem))
    return out


def eval_all(cands: List[dict], day_strs: List[str], pols: Dict[str, Callable], max_n_prod2: bool = True):
    want = set(day_strs)
    slice_c = [c for c in cands if c["day"] in want]
    row: Dict[str, Any] = {"n_candidates": len(slice_c)}
    for name, pred in pols.items():
        st1 = _stats(deep._pick(slice_c, pred, max_n=1))
        row[name] = st1
        if name == "prod1" and max_n_prod2:
            row["prod2"] = _stats(deep._pick(slice_c, pred, max_n=2))
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=240, help="Trailing sessions to walk (~8×30)")
    ap.add_argument("--block-size", type=int, default=30)
    ap.add_argument("--from-cache", action="store_true")
    ap.add_argument("--min-bars", type=int, default=20)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    pack = fno_model.load(symbol="NIFTY")
    if not fno_model.pack_usable(pack):
        raise SystemExit(pack.get("reason"))

    if args.from_cache and CACHE.is_file():
        raw = json.loads(CACHE.read_text(encoding="utf-8"))
        cands = [deep._enrich_legacy(c) for c in raw["candidates"]]
        all_days = [pd.Timestamp(str(d)).date() for d in raw["sessions"]]
        print(f"cache cands={len(cands)} sessions={len(all_days)}", flush=True)
    else:
        bars = _load_csv_bars()
        all_days = _full_days(bars, args.min_bars)
        if len(all_days) < args.sessions:
            print(f"only {len(all_days)} sessions available, using all", flush=True)
            use_days = all_days
        else:
            use_days = all_days[-args.sessions :]
        print(f"walking {len(use_days)} sessions {use_days[0]}->{use_days[-1]}", flush=True)
        cands = [deep._enrich_legacy(c) for c in deep.collect(bars, pack, use_days)]
        CACHE.write_text(
            json.dumps(
                {"candidates": cands, "sessions": [str(d) for d in use_days], "source": "csv_archive"},
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"wrote {CACHE} n={len(cands)}", flush=True)
        all_days = use_days

    pols = policies()
    blocks = make_blocks(all_days, args.block_size)
    block_rows = []
    print("\n=== PER-WINDOW (hit% / calls / pts) ===", flush=True)
    header = f"{'win':<8} {'span':<25} " + " ".join(f"{k:>10}" for k in ["prod1", "prod2", "a_plus", "pdf_quality", "cboe_router", "no_pre10"])
    print(header, flush=True)

    for label, days in blocks:
        day_strs = [str(d) for d in days]
        ev = eval_all(cands, day_strs, pols)
        ev["label"] = label
        ev["from"] = day_strs[0]
        ev["to"] = day_strs[-1]
        ev["n_sessions"] = len(day_strs)
        block_rows.append(ev)

        def cell(key):
            s = ev.get(key) or {}
            if not s or not s.get("calls"):
                return f"{'—':>10}"
            return f"{s['hit_pct']:4.0f}%/{s['calls']:<2}"

        print(
            f"{label:<8} {ev['from']}→{ev['to'][-5:]} "
            f"{cell('prod1')} {cell('prod2')} {cell('a_plus')} {cell('pdf_quality')} "
            f"{cell('cboe_router')} {cell('no_pre10')}",
            flush=True,
        )

    full = [b for b in block_rows if b["n_sessions"] >= args.block_size]

    def pool(key: str) -> Dict[str, Any]:
        calls = sum((b.get(key) or {}).get("calls", 0) for b in full)
        t1 = sum((b.get(key) or {}).get("t1", 0) for b in full)
        pts = sum((b.get(key) or {}).get("points", 0) for b in full)
        hits = [b[key]["hit_pct"] for b in full if (b.get(key) or {}).get("calls", 0) > 0]
        return {
            "calls": calls,
            "t1": t1,
            "hit_pct": round(100.0 * t1 / calls, 1) if calls else 0.0,
            "points": round(pts, 1),
            "pts_per_call": round(pts / calls, 1) if calls else 0.0,
            "min_window_hit": min(hits) if hits else None,
            "max_window_hit": max(hits) if hits else None,
            "windows_with_calls": len(hits),
            "windows_ge_80": sum(1 for h in hits if h >= 80),
            "windows_100": sum(1 for h in hits if h >= 100),
        }

    keys = ["prod1", "prod2", "a_plus", "pdf_quality", "cboe_router", "calendar_settle", "no_pre10", "first_only", "no_range", "trend_vol", "floor52"]
    pooled = {k: pool(k) for k in keys if any(k in b for b in full)}

    # Rank by: hit (durable), then points, then calls — require min calls
    min_calls = max(8, int(0.5 * pooled["prod1"]["calls"])) if pooled.get("prod1", {}).get("calls") else 8
    ranked = sorted(
        [
            {"algo": k, **v}
            for k, v in pooled.items()
            if v["calls"] >= (1 if k == "a_plus" else min_calls) or k == "a_plus"
        ],
        key=lambda r: (r["hit_pct"], r["points"], r["calls"]),
        reverse=True,
    )
    # Best profit among algos with hit >= prod1 - 2pp
    base_hit = pooled.get("prod1", {}).get("hit_pct", 0)
    profit = sorted(
        [r for r in ranked if r["hit_pct"] >= base_hit - 2.0 and r["algo"] != "a_plus"],
        key=lambda r: (r["points"], r["hit_pct"], r["calls"]),
        reverse=True,
    )

    print("\n=== POOLED FULL BLOCKS ===", flush=True)
    for r in ranked:
        print(
            f"  {r['algo']:<16} n={r['calls']:3d} hit={r['hit_pct']:5.1f}% pts={r['points']:+8.0f} "
            f"/call={r['pts_per_call']:+.1f} minW={r['min_window_hit']} 100W={r['windows_100']}/{r['windows_with_calls']}",
            flush=True,
        )

    diagnosis = {
        "question": "Why W1/W2/W3 lower accuracy than latest?",
        "answer": (
            "Not a testing miss. Same model, BUY_P=0.52, early-drop, Kite/CSV 15m. "
            "Losses cluster on not-A+: RANGE days, pre-10:00 entries, non-first breaks, chase. "
            "Latest window had more TREND + cleaner first breaks (easy regime)."
        ),
        "detail_file": "weak_window_diagnosis.json",
    }

    report = {
        "note": "Large-window profit research on CSV archive. Research only.",
        "diagnosis": diagnosis,
        "n_sessions": len(all_days),
        "span": f"{all_days[0]}→{all_days[-1]}",
        "block_size": args.block_size,
        "n_full_blocks": len(full),
        "blocks": [
            {
                "label": b["label"],
                "from": b["from"],
                "to": b["to"],
                "n_sessions": b["n_sessions"],
                **{k: b[k] for k in b if isinstance(b[k], dict) and "hit_pct" in b[k]},
            }
            for b in block_rows
        ],
        "pooled": pooled,
        "ranked_by_hit": ranked,
        "best_profit_near_prod1_hit": profit[:5],
        "verdict": {
            "most_accurate": ranked[0] if ranked else None,
            "most_points_keeping_hit": profit[0] if profit else None,
            "a_plus": pooled.get("a_plus"),
            "prod1": pooled.get("prod1"),
            "prod2": pooled.get("prod2"),
        },
    }
    REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {REPORT}", flush=True)
    print("\n=== VERDICT ===", flush=True)
    print("diagnosis:", diagnosis["answer"], flush=True)
    if ranked:
        print("best hit:", ranked[0]["algo"], ranked[0], flush=True)
    if profit:
        print("best profit ~prod1 hit:", profit[0]["algo"], profit[0], flush=True)


if __name__ == "__main__":
    main()
