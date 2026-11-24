"""RESEARCH — replay locked dual packs on **10m** candles; hunt Proven@100% high-N.

Uses existing BUY/SELL dual packs (same as live proven/champ) evaluated on
resampled 10m OR-breaks — not a new train. Complements dual10m train script.

  python -u prod_live/tests/builders/research_dual_packs_on_10m.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
warnings.filterwarnings("ignore")
import path_setup  # noqa: F401,E402

os.environ.setdefault("TELEGRAM_NOTIFY", "0")
os.environ.setdefault("WHATSAPP_NOTIFY", "0")
os.environ["ENABLE_NSE_MID_GATE"] = "0"

from accuracy_max_6m import _agg  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    bestp_day,
    first_day,
    gap_map,
    is_perfect,
    mine_perfect,
    union_unique_days,
)
from research_confirm_dual_tf_deep import _clip  # noqa: E402
from research_dual10m_proven100 import resample_10m, _norm  # noqa: E402
from research_dual15_dual5_confirm100 import _collect_dual  # noqa: E402
import research_dual15_dual5_confirm100 as dmod  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE = LEDGER / "_cache_dual_packs_on_10m_1y.json"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"

END = "2026-11-13"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_6M = (pd.Timestamp(END) - timedelta(days=183)).strftime("%Y-%m-%d")
# Fast pass: walk packs on 1y only (3y full walk ~1h)
WALK_START = START_1Y


def greedy_day(streams, start_gate, end_gate, start_1y):
    cur, used = [], []
    for tag, rows, _st in streams:
        seed = _clip(rows, start_gate, end_gate)
        if not seed or not is_perfect(seed):
            continue
        s1 = _clip(rows, start_1y, end_gate)
        if len(s1) >= 5 and not is_perfect(s1):
            continue
        cur, used = list(seed), [tag]
        break
    if not cur:
        return [], []
    improved = True
    while improved and len(used) < 60:
        improved = False
        best = None
        best_n = len(cur)
        for tag, rows, _st in streams:
            if tag in used:
                continue
            merged = union_unique_days(cur, _clip(rows, start_gate, end_gate))
            if len(merged) <= best_n or not is_perfect(merged):
                continue
            m1 = _clip(merged, start_1y, end_gate)
            if len(m1) >= 5 and not is_perfect(m1):
                continue
            best = (tag, merged)
            best_n = len(merged)
        if best:
            used.append(best[0])
            cur = best[1]
            improved = True
            print(f"    +{best[0][:70]} → n={len(cur)}", flush=True)
    return cur, used


def main() -> int:
    t0 = time.time()
    print("RESEARCH locked dual packs on 10m candles", flush=True)

    dual_lock = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    p15 = dual_lock["dual15"]["proven_100"]
    p5 = dual_lock["dual5"]["proven_100"]

    if CACHE.is_file():
        raw = json.loads(CACHE.read_text(encoding="utf-8"))
        if raw.get("start") == WALK_START and raw.get("end") == END:
            dual10 = raw["dual10"]
            print(
                f"  cache hit proven={len(dual10['proven_100'])} champ={len(dual10['champion'])}",
                flush=True,
            )
        else:
            dual10 = None
    else:
        dual10 = None

    sessions_all, _, _ = fs._prod2(4000)
    sess_walk = sorted(d for d in sessions_all if WALK_START < d <= END)
    sess = sorted(d for d in sessions_all if START_3Y < d <= END)

    if dual10 is None:
        print(
            f"  resample 5m→10m + walk locked dual packs on 1y ({len(sess_walk)} sess)…",
            flush=True,
        )
        bars5 = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
        bars5 = bars5[bars5.index >= WALK_START]
        bars10 = resample_10m(bars5)
        dmod.BAR_DELTA["10m"] = pd.Timedelta("10min")
        dmod.CHAMP_BUY_MIN = 0.50
        dmod.CHAMP_SELL_MIN = 0.50
        dual10 = _collect_dual(bars10, sess_walk, tf="10m")
        CACHE.write_text(
            json.dumps({"start": WALK_START, "end": END, "dual10": dual10}, default=str),
            encoding="utf-8",
        )
        print(
            f"  dual10 proven={len(dual10['proven_100'])} champ={len(dual10['champion'])}",
            flush=True,
        )

    any10 = [
        dict(r, track=str(r.get("track") or "dual10"))
        for r in (dual10.get("proven_100") or []) + (dual10.get("champion") or [])
    ]
    proven10 = [dict(r) for r in dual10.get("proven_100") or []]

    gaps = gap_map()
    daily = fs._load_daily()
    active = fs._active_days(sess_walk, daily) if sess_walk else set()

    print("  mine perfect…", flush=True)
    streams = mine_perfect("DP10", any10, active=active, gaps=gaps, min_n=3)

    streams = [(t, r, s) for t, r, s in streams if is_perfect(r)]
    print(f"  perfect streams={len(streams)}", flush=True)
    # Gate on 1y walk window (hard 100%); still report dual15 1y baseline
    day_rows, day_tags = greedy_day(streams, WALK_START, END, START_1Y)

    books = {
        "BASE_dual15_proven": p15,
        "BASE_dual5_proven": p5,
        "DUALPACKS_10m_proven_raw": proven10,
        "DUALPACKS_10m_any": any10,
        "DP10_PROVEN100_DAY": day_rows,
    }

    lines = [
        "# RESEARCH — Locked dual packs on 10m candles → Proven@100%",
        "",
        "**Status:** RESEARCH only · **not live**",
        "**Model:** existing dual BUY/SELL packs · OR-break walked on **10m** tape",
        "",
        f"10m proven fires: **{len(proven10)}** @ {_agg(proven10).get('hit_pct')}%",
        f"10m any (proven∪champ soft): **{len(any10)}** @ {_agg(any10).get('hit_pct')}%",
        f"Perfect streams: **{len(streams)}** · day desk tags: **{len(day_tags)}**",
        "",
        "## Books",
        "",
        "| Book | 3y | 1y | 6m | Perfect3y |",
        "|---|---|---|---|---|",
    ]
    payload: Dict[str, Any] = {
        "status": "RESEARCH",
        "not_live": True,
        "mode": "locked_dual_packs_on_10m",
        "books": {},
        "day_stream_tags": day_tags,
        "top_streams": [
            {"tag": t, "n": s.get("n"), "hit_pct": s.get("hit_pct")} for t, _r, s in streams[:20]
        ],
    }

    for name, rows in books.items():
        sc = {}
        for lab, a, b in (
            ("3y", START_3Y, END),
            ("1y", START_1Y, END),
            ("6m", START_6M, END),
        ):
            rs = _clip(rows, a, b)
            st = _agg(rs)
            sc[lab] = {**st, "perfect": (not rs) or is_perfect(rs)}
        payload["books"][name] = sc

        def fmt(w):
            x = sc[w]
            n = x.get("n") or 0
            return f"{n}@{x.get('hit_pct')}" if n else "0"

        lines.append(
            f"| `{name}` | {fmt('3y')} | {fmt('1y')} | {fmt('6m')} | "
            f"{'Y' if sc['3y'].get('perfect') else 'N'} |"
        )

    d1 = payload["books"]["DP10_PROVEN100_DAY"]["1y"]
    d3 = payload["books"]["DP10_PROVEN100_DAY"]["3y"]
    b15 = payload["books"]["BASE_dual15_proven"]["1y"]
    if day_rows and d3.get("perfect") and d1.get("perfect") and (d1.get("n") or 0) >= (b15.get("n") or 0):
        verdict = (
            f"PROMISING — dual-packs@10m day desk {d1.get('n')}@100% ≥ dual15 proven "
            f"{b15.get('n')}@{b15.get('hit_pct')}%. Still RESEARCH."
        )
    elif day_rows and d3.get("perfect"):
        verdict = (
            f"PARTIAL/THIN — 100% desk {d3.get('n')}@100% 3y / {d1.get('n')}@{d1.get('hit_pct')}% 1y; "
            f"dual15 proven still {b15.get('n')}@100%."
        )
    else:
        verdict = (
            "FAIL — locked dual packs on 10m do not yield high-N Proven@100; "
            "keep dual15 (15m) proven for LIVE."
        )
    payload["verdict"] = verdict
    payload["elapsed_s"] = round(time.time() - t0, 1)

    lines.extend(["", "## Day streams", ""])
    for i, t in enumerate(day_tags, 1):
        lines.append(f"{i}. `{t}`")
    lines.extend(["", "## Verdict", "", verdict, "", f"Elapsed {payload['elapsed_s']}s", ""])

    # append train summary pointer
    train_md = OUT / "RESEARCH_DUAL10M_PROVEN100.md"
    lines.extend(
        [
            "## Related",
            "",
            f"New 10m dual **train** (candlestick HGB) report: `{train_md.name}` — also RESEARCH.",
            "",
        ]
    )

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "RESEARCH_DUAL_PACKS_ON_10M.md"
    js = OUT / "RESEARCH_DUAL_PACKS_ON_10M.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    print(f"VERDICT: {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
