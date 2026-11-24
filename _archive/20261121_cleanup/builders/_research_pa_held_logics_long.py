"""Hold all PA research logics · test 22d / 6m / 1y via live-path 1m.

Scans in monthly chunks (with 2-session lookback) — same closed 1m causal
evaluation as Option Blue, but tractable on ~1y of bars.
Live lock is NOT overwritten.

  python -u prod_live/tests/builders/_research_pa_held_logics_long.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Set

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
]
import kite_data  # noqa: E402
from prod_live.logic import pa_structure_live as pa  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
MD = OUT / "PA_HELD_LOGICS_6M_1Y.md"
JS = OUT / "PA_HELD_LOGICS_6M_1Y.json"


def _install_sr_cache() -> None:
    _orig = pa.build_sr_map
    cache: Dict[Any, Any] = {}

    def _cached(o, h, l, c, atr, idx, i: int, *, lookback_days: int = 2):
        day = pa._day(idx[i])
        # bucket ~5 bars — big speedup, still causal enough for research
        key = (day, int(i) // 5, int(lookback_days))
        hit = cache.get(key)
        if hit is not None:
            return hit
        out = _orig(o, h, l, c, atr, idx, i, lookback_days=lookback_days)
        cache[key] = out
        if len(cache) > 30000:
            cache.clear()
        return out

    pa.build_sr_map = _cached  # type: ignore[assignment]


def held_cfgs() -> List[pa.PaConfig]:
    base = pa.PaConfig(
        name="pa_only",
        use_frvp=False,
        sr_gate="none",
        sl_kill_mode="none",
        candle_entry_mode="none",
        candle_trail_mode="base",
        allow_or_retest=True,
        allow_break=True,
        allow_sweep=True,
        trade_lo=9 * 60 + 30,
        trade_hi=14 * 60 + 45,
        max_calls_day=12,
        cooldown_bars=10,
        body_min=0.55,
        or_side_align=True,
        min_risk=3.0,
        max_risk=22.0,
    )
    return [
        # fast first
        base,
        replace(
            base,
            name="frvp_vah_break",
            use_frvp=True,
            frvp_mode="vah_break",
            frvp_anchor="or30",
            frvp_prefer_sl=True,
        ),
        replace(
            base,
            name="frvp_no_exhaust",
            use_frvp=True,
            frvp_mode="vah_break",
            frvp_anchor="or30",
            frvp_prefer_sl=True,
            candle_entry_mode="no_exhaust",
        ),
        replace(
            base,
            name="frvp_read_v3_pin",
            use_frvp=True,
            frvp_mode="vah_break",
            frvp_anchor="or30",
            frvp_prefer_sl=True,
            candle_entry_mode="read_v3",
            candle_trail_mode="pin_protect",
        ),
        # SR / trap (slower)
        replace(
            base,
            name="no_trap",
            sr_gate="no_trap",
            candle_trail_mode="pin_protect",
        ),
        replace(
            base,
            name="pa_sr_full_v1",
            sr_gate="full_v1",
            sr_lookback_days=2,
            min_rr=1.5,
            candle_trail_mode="pin_protect",
        ),
        replace(
            base,
            name="pa_sr_acc_mid",
            sr_gate="full_v1",
            sr_lookback_days=2,
            min_rr=1.5,
            candle_trail_mode="pin_protect",
            allow_or_retest=False,
            trade_lo=10 * 60,
            trade_hi=14 * 60,
        ),
        replace(
            base,
            name="pa_sr_acc_mid_slkill",
            sr_gate="full_v1",
            sr_lookback_days=2,
            min_rr=1.5,
            candle_trail_mode="pin_protect",
            allow_or_retest=False,
            trade_lo=10 * 60,
            trade_hi=14 * 60,
            sl_kill_mode="chase_v1",
        ),
    ]


def monthly_chunks(all_days: List[str], lookback: int = 2) -> List[tuple]:
    """Yield (score_days_set, frame_days_list) month groups over all_days."""
    from collections import defaultdict

    by_ym: Dict[str, List[str]] = defaultdict(list)
    for d in all_days:
        by_ym[d[:7]].append(d)
    yms = sorted(by_ym.keys())
    out = []
    for ym in yms:
        score = by_ym[ym]
        i0 = all_days.index(score[0])
        start = max(0, i0 - lookback)
        frame_days = all_days[start : all_days.index(score[-1]) + 1]
        out.append((set(score), frame_days, ym))
    return out


def scan_chunked(bars, all_days: List[str], cfg: pa.PaConfig, score_days: Set[str]):
    """Live-path scan in monthly chunks; keep calls whose day is in score_days."""
    keep = []
    chunks = monthly_chunks(all_days, lookback=2)
    # only chunks that intersect score window
    for score_set, frame_days, ym in chunks:
        if not (score_set & score_days):
            continue
        frame = bars[bars.index.strftime("%Y-%m-%d").isin(set(frame_days))]
        if frame.empty:
            continue
        print(f"    chunk {ym} bars={len(frame)}…", flush=True)
        calls = pa.scan_session(frame, settle=True, cfg=cfg)
        for c in calls:
            if c.day in score_days and c.day in score_set:
                keep.append(c)
    return keep


def summarize_slice(calls, days_set: set) -> Dict[str, Any]:
    subset = [c for c in calls if c.day in days_set]
    s = pa.summarize(subset)
    hard_sl = sum(1 for c in subset if c.exit_why == "sl")
    by = Counter(c.day for c in subset)
    return {
        "n": s.get("n"),
        "hit_pct": s.get("hit_pct"),
        "avg_R": s.get("avg_R"),
        "sum_pts": s.get("sum_pts"),
        "avg_pts": s.get("avg_pts"),
        "hit_1R_pct": s.get("hit_1R_pct"),
        "hard_sl": hard_sl,
        "by_setup": s.get("by_setup"),
        "days_with": len(by),
        "avg_per_day": round(len(subset) / max(len(days_set), 1), 2),
    }


def main() -> int:
    _install_sr_cache()
    live = pa.load_locked_cfg()
    print(
        f"Live lock unchanged: {live.name}. "
        f"Holding/testing research logics on long 1m history (monthly chunks).",
        flush=True,
    )
    print("Fetching NIFTY 1m (~400 calendar days)…", flush=True)
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=400, keep_partial=False
    )
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    all_days = sorted({str(ts.date()) for ts in bars.index})
    print(
        f"Got bars={len(bars)} sessions={len(all_days)} {all_days[0]}→{all_days[-1]}",
        flush=True,
    )

    n1y = min(252, len(all_days))
    n6 = min(126, len(all_days))
    n22 = min(22, len(all_days))
    windows = {
        "22d_ref": set(all_days[-n22:]),
        "6m": set(all_days[-n6:]),
        "1y": set(all_days[-n1y:]),
    }
    window_meta = {
        "22d_ref": (all_days[-n22], all_days[-1], n22),
        "6m": (all_days[-n6], all_days[-1], n6),
        "1y": (all_days[-n1y], all_days[-1], n1y),
    }
    score_1y = windows["1y"]
    # days list covering 1y + lookback for chunking
    i0 = max(0, all_days.index(all_days[-n1y]) - 2)
    days_for_scan = all_days[i0:]

    cfgs = held_cfgs()
    per_logic: Dict[str, Dict[str, Any]] = {}
    for cfg in cfgs:
        print(f"\nSCAN {cfg.name}…", flush=True)
        calls = scan_chunked(bars, days_for_scan, cfg, score_1y)
        print(f"  total calls in 1y window: {len(calls)}", flush=True)
        per_logic[cfg.name] = {
            "cfg": cfg.name,
            "windows": {
                label: summarize_slice(calls, days_set)
                for label, days_set in windows.items()
            },
        }
        for label, row in per_logic[cfg.name]["windows"].items():
            print(
                f"  {label}: n={row['n']} hit={row['hit_pct']} R={row['avg_R']} "
                f"sum={row['sum_pts']} sl={row['hard_sl']}",
                flush=True,
            )

    results: Dict[str, Any] = {
        "available_sessions": len(all_days),
        "available_start": all_days[0],
        "available_end": all_days[-1],
        "live_lock": live.name,
        "method": "monthly_chunk_scan_session_1m",
        "per_logic": per_logic,
        "windows": {},
    }
    lines = [
        "# Held PA logics · 22d / 6m / 1y (live-path 1m)",
        "",
        f"NIFTY 1m Kite · `{all_days[0]}` → `{all_days[-1]}` ({len(all_days)} sessions).",
        "Method: monthly `scan_session` chunks + 2-session lookback (causal closed 1m, same as live).",
        f"Live lock **not changed**: `{live.name}`.",
        "",
    ]
    for label in ("22d_ref", "6m", "1y"):
        start, end, n = window_meta[label]
        rows = [
            {"name": name, **blob["windows"][label]}
            for name, blob in per_logic.items()
        ]
        by_sum = sorted(rows, key=lambda r: (r.get("sum_pts") or -1e18), reverse=True)
        by_hit = sorted(
            rows,
            key=lambda r: ((r.get("hit_pct") or 0), (r.get("sum_pts") or 0)),
            reverse=True,
        )
        results["windows"][label] = {
            "start": start,
            "end": end,
            "n_sessions": n,
            "rows": rows,
            "best_sum": by_sum[0] if by_sum else None,
            "best_hit": by_hit[0] if by_hit else None,
        }
        lines += [
            f"## {label} · {start} → {end} ({n} sessions)",
            "",
            "| Logic | N | Hit% | AvgR | Sum pts | Hard SL | Days w/ | /day |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for r in by_sum:
            mark = "**" if r["name"] == by_sum[0]["name"] else ""
            lines.append(
                f"| {mark}{r['name']}{mark} | {r.get('n')} | {r.get('hit_pct')} | "
                f"{r.get('avg_R')} | {r.get('sum_pts')} | {r.get('hard_sl')} | "
                f"{r.get('days_with')} | {r.get('avg_per_day')} |"
            )
        bs, bh = by_sum[0], by_hit[0]
        lines += [
            "",
            f"**Best sum:** `{bs['name']}` · sum={bs.get('sum_pts')} · hit={bs.get('hit_pct')}",
            f"**Best hit:** `{bh['name']}` · hit={bh.get('hit_pct')} · sum={bh.get('sum_pts')}",
            "",
        ]

    OUT.mkdir(parents=True, exist_ok=True)
    MD.write_text("\n".join(lines), encoding="utf-8")
    JS.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
