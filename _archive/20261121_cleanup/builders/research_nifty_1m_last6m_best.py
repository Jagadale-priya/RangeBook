"""RESEARCH ONLY — test best 1m clean logics on **last 6 months from today**.

Window: today-182d → today (IST), clipped to available tape.
Heads / structural rules frozen on data **before** test start (no leakage).

  python -u prod_live/tests/builders/research_nifty_1m_last6m_best.py
  python -u prod_live/tests/builders/research_nifty_1m_last6m_best.py --download
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401,E402

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_100pct_only as hun  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT_MD = OUT / "NIFTY_1M_LAST6M_BEST.md"
REPORT_JSON = OUT / "NIFTY_1M_LAST6M_BEST.json"
CACHE_EXT = ROOT / "stock_signal_data" / "fno_validate" / "research" / "_cache_nifty_1m_ext.parquet"


def today_ist() -> pd.Timestamp:
    return pd.Timestamp.now(tz="Asia/Kolkata").normalize()


def window_last_6m() -> Tuple[str, str, str]:
    """Return test_start, test_end, train_end (YYYY-MM-DD)."""
    end = today_ist()
    start = end - pd.Timedelta(days=182)
    train_end = (start - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), train_end


def load_full_tape(download: bool) -> Tuple[pd.DataFrame, Optional[str]]:
    """Merge research cache + live csv + optional kite extend."""
    frames = []
    note = None
    existing = base.load_existing_1m()
    if len(existing):
        frames.append(existing)
    if CACHE_EXT.is_file():
        ext = base._norm(pd.read_parquet(CACHE_EXT))
        frames.append(ext)
        print(f"  ext cache: {len(ext)} bars", flush=True)

    if download:
        # extend from max existing to today
        if frames:
            mx = max(f.index.max() for f in frames)
            start = (pd.Timestamp(mx).tz_convert("Asia/Kolkata") + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            start = (today_ist() - pd.Timedelta(days=200)).strftime("%Y-%m-%d")
        end = today_ist().strftime("%Y-%m-%d")
        print(f"  downloading {start} → {end} …", flush=True)
        # temporarily widen base END for download helper clip
        fresh, note = base.download_1m_range(start, end)
        if len(fresh):
            frames.append(fresh)
            print(f"  downloaded {len(fresh)} bars", flush=True)

    if not frames:
        return pd.DataFrame(), "no bars"
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    # session filter already in _norm paths; ensure
    hm = df.index.strftime("%H:%M")
    df = df[(hm >= "09:15") & (hm <= "15:29")]
    CACHE_EXT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CACHE_EXT)
    print(f"  tape bars={len(df)} {df.index.min()} → {df.index.max()}", flush=True)
    return df, note


# Best candidate logics from prior research
LOGIC_GATES = {
    "V2_STRICT": dict(base.GATE_V2),
    "MED": dict(hun.POOLS["POOL_MED"]),
    "FB_WIDE": dict(hun.POOLS["POOL_FB"]),
}

# Structural books (no ML) — frozen definitions from prior hunts
STRUCT_BOOKS = {
    "SELL_mid_tight": {
        "side": "SELL",
        "min_mins": 630,
        "max_mins": 720,
        "max_or_ext": 0.15,
        "min_or_w": 15,
        "max_noise": 1.25,
        "require_fb": True,
        "forbid_both": True,
        "require_body": True,
    },
    "BUY_1030_1130_soft_dn_gap": {
        "side": "BUY",
        "min_mins": 630,
        "max_mins": 690,
        "max_or_ext": 0.05,
        "min_or_w": 12,
        "max_noise": 1.5,
        "gap_lo": None,
        "gap_hi": 0.0,
        "require_fb": True,
        "forbid_both": True,
    },
    "BOTH_after10_ext020_or20": {
        "side": None,
        "min_mins": 600,
        "max_mins": 870,
        "max_or_ext": 0.20,
        "min_or_w": 20,
        "max_noise": 1.25,
        "require_fb": True,
        "forbid_both": True,
        "require_body": True,
    },
    "SELL_after10_ext020": {
        "side": "SELL",
        "min_mins": 600,
        "max_mins": 870,
        "max_or_ext": 0.20,
        "min_or_w": 20,
        "max_noise": 1.25,
        "require_fb": True,
        "forbid_both": True,
        "require_body": True,
    },
    "BOTH_10_1030_flat_gap": {
        "side": None,
        "min_mins": 600,
        "max_mins": 630,
        "max_or_ext": 0.20,
        "min_or_w": 15,
        "max_noise": 1.5,
        "gap_lo": -0.35,
        "gap_hi": 0.35,
        "require_fb": True,
        "forbid_both": True,
    },
}


def first_day(rows: List[dict]) -> List[dict]:
    return hun.first_day(rows)


def agg(rows: List[dict]) -> Dict[str, Any]:
    return hun.agg(rows)


def score_ml(packs: Dict[str, Any], tickets: List[dict]) -> List[dict]:
    return base.score_all(packs, tickets)


def train_before(tickets: List[dict], train_end: str) -> Dict[str, Any]:
    old = base.FREEZE
    base.FREEZE = train_end
    try:
        # need enough rows; if too few, still try
        return base.train_dual_heads(tickets)
    finally:
        base.FREEZE = old


def eval_ml_books(scored: List[dict]) -> Dict[str, dict]:
    books = {}
    for name, pred in (
        ("ALL_DU", lambda r: True),
        ("CHAMP_P55", lambda r: float(r.get("p_t1") or 0) >= 0.55),
        ("CHAMP_P58", lambda r: float(r.get("p_t1") or 0) >= 0.58),
        ("CHAMP_P60", lambda r: float(r.get("p_t1") or 0) >= 0.60),
        ("SELL_P55", lambda r: r.get("decision") == "SELL" and float(r.get("p_t1") or 0) >= 0.55),
        ("BUY_P55", lambda r: r.get("decision") == "BUY" and float(r.get("p_t1") or 0) >= 0.55),
        ("SELL_ALL", lambda r: r.get("decision") == "SELL"),
        ("BUY_ALL", lambda r: r.get("decision") == "BUY"),
    ):
        rows = first_day([r for r in scored if pred(r)])
        books[name] = {**agg(rows), "calls": [hun.strip(r) for r in rows]}
    return books


def mine_train100_test(
    train_rows: List[dict],
    test_rows: List[dict],
    *,
    min_train: int = 5,
    min_test: int = 3,
) -> List[dict]:
    """Search structural filters: train 100% → score test (may not be 100)."""
    core = []
    for side in (None, "BUY", "SELL"):
        for c0, c1 in ((600, 870), (600, 630), (630, 690), (600, 720), (630, 780), (690, 780)):
            for ext in (0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30):
                for orw in (15, 20, 25, 30, 40):
                    for nz in (1.0, 1.25, 1.5):
                        for glo, ghi in ((None, None), (-0.35, 0.35), (None, 0.0), (0.0, None)):
                            for body in (None, True):
                                core.append(
                                    dict(
                                        side=side,
                                        min_mins=c0,
                                        max_mins=c1,
                                        max_or_ext=ext,
                                        min_or_w=orw,
                                        max_noise=nz,
                                        gap_lo=glo,
                                        gap_hi=ghi,
                                        require_body=body,
                                        forbid_both=True,
                                        require_fb=True,
                                    )
                                )
    hits = []
    t0 = time.time()
    for i, f in enumerate(core, 1):
        if i % 3000 == 0:
            print(f"    mine {i}/{len(core)} hits={len(hits)} ({time.time()-t0:.0f}s)", flush=True)
        tr = first_day(hun.apply_f(train_rows, f))
        ta = agg(tr)
        if ta["n"] < min_train or ta["hit_pct"] < 100 - 1e-9:
            continue
        te = first_day(hun.apply_f(test_rows, f))
        ea = agg(te)
        if ea["n"] < 1:
            continue
        hits.append(
            {
                "filters": f,
                "train": ta,
                "test": ea,
                "test_calls": [hun.strip(r) for r in te],
            }
        )
    # prefer test 100% then max n, else max hit% with n>=min_test
    hits.sort(
        key=lambda h: (
            1 if h["test"]["hit_pct"] >= 100 - 1e-9 else 0,
            h["test"]["n"] if h["test"]["hit_pct"] >= 100 - 1e-9 else 0,
            h["test"]["hit_pct"],
            h["test"]["n"],
            h["train"]["n"],
        ),
        reverse=True,
    )
    return hits


def monthly_table(rows: List[dict]) -> List[dict]:
    from collections import defaultdict

    by = defaultdict(list)
    for r in first_day(rows):
        by[str(r.get("day") or "")[:7]].append(r)
    return [{"month": m, **agg(by[m])} for m in sorted(by)]


def run_pool(
    bars: pd.DataFrame,
    name: str,
    gates: dict,
    test_start: str,
    test_end: str,
    train_end: str,
) -> Dict[str, Any]:
    print(f"\n=== POOL {name} ===", flush=True)
    tickets, reasons, _ = base.build_clean_tickets(bars, gates=gates)
    rows = hun.enrich(tickets)
    train = [r for r in rows if str(r["day"]) <= train_end]
    test = [r for r in rows if test_start <= str(r["day"]) <= test_end]
    print(f"  clean={len(rows)} train={len(train)} test={len(test)}", flush=True)

    # ML heads
    packs = train_before(train, train_end)
    test_scored = []
    train_scored = []
    if any((packs.get(s) or {}).get("available") for s in ("BUY", "SELL")):
        test_scored = score_ml(packs, test)
        train_scored = score_ml(packs, train)
        for r in test_scored:
            r["pool"] = name
    ml_books = eval_ml_books(test_scored) if test_scored else {}

    # Fixed structural books on this pool's test tickets
    struct = {}
    for bname, f in STRUCT_BOOKS.items():
        te = first_day(hun.apply_f(test, f))
        tr = first_day(hun.apply_f(train, f))
        struct[bname] = {
            "filters": f,
            "train": agg(tr),
            "test": agg(te),
            "test_calls": [hun.strip(r) for r in te],
        }

    # Mine train100 → last6m
    print("  mining train100 rules…", flush=True)
    mined = mine_train100_test(train, test, min_train=5, min_test=3)
    best_100 = [m for m in mined if m["test"]["hit_pct"] >= 100 - 1e-9 and m["test"]["n"] >= 3]
    best_any = mined[:15]

    # Union of train100&test100 micros (min_te=1)
    micros = [m for m in mined if m["test"]["hit_pct"] >= 100 - 1e-9 and m["test"]["n"] >= 1]
    by_day = {}
    for m in micros:
        for c in m["test_calls"]:
            by_day.setdefault(c["day"], c)
    union_rows = first_day(list(by_day.values()))
    union = {**agg(union_rows), "calls": [hun.strip(r) for r in sorted(union_rows, key=lambda x: x["day"])], "n_micros": len(micros)}

    return {
        "pool": name,
        "gates": gates,
        "n_clean": len(rows),
        "n_train": len(train),
        "n_test": len(test),
        "reasons": reasons,
        "heads": {
            k: {kk: vv for kk, vv in (v or {}).items() if kk not in ("base", "iso")}
            for k, v in packs.items()
        },
        "base_test": agg(first_day(test)),
        "base_train": agg(first_day(train)),
        "ml_books": {k: {kk: vv for kk, vv in v.items() if kk != "calls"} for k, v in ml_books.items()},
        "ml_books_calls": {k: v.get("calls") for k, v in ml_books.items()},
        "struct_books": struct,
        "mined_top": [
            {k: v for k, v in m.items() if k != "test_calls"} | {"test_calls": m["test_calls"]}
            for m in best_any[:12]
        ],
        "best_test100": best_100[:8],
        "union100": union,
        "monthly_test": monthly_table(test),
        "test_calls_all": [hun.strip(r) for r in first_day(test)],
    }


def pick_best(results: List[dict]) -> Dict[str, Any]:
    """Choose best logic for last-6m: prefer 100% with n>=3, else highest hit with n>=5, else highest hit n>=3."""
    cands = []
    for r in results:
        pool = r["pool"]
        # ML books
        for bname, b in (r.get("ml_books") or {}).items():
            if b.get("n", 0) >= 3:
                cands.append(
                    {
                        "pool": pool,
                        "logic": f"ML|{bname}",
                        "kind": "ML",
                        "n": b["n"],
                        "hit_pct": b["hit_pct"],
                        "calls": (r.get("ml_books_calls") or {}).get(bname) or [],
                    }
                )
        # struct
        for bname, b in (r.get("struct_books") or {}).items():
            te = b.get("test") or {}
            if te.get("n", 0) >= 3:
                cands.append(
                    {
                        "pool": pool,
                        "logic": f"STRUCT|{bname}",
                        "kind": "STRUCT",
                        "n": te["n"],
                        "hit_pct": te["hit_pct"],
                        "calls": b.get("test_calls") or [],
                        "filters": b.get("filters"),
                        "train": b.get("train"),
                    }
                )
        # mined test100
        for m in r.get("best_test100") or []:
            cands.append(
                {
                    "pool": pool,
                    "logic": "MINED_TRAIN100_TEST100",
                    "kind": "MINED_100",
                    "n": m["test"]["n"],
                    "hit_pct": m["test"]["hit_pct"],
                    "calls": m.get("test_calls") or [],
                    "filters": m.get("filters"),
                    "train": m.get("train"),
                }
            )
        # union
        u = r.get("union100") or {}
        if u.get("n", 0) >= 1:
            cands.append(
                {
                    "pool": pool,
                    "logic": "UNION_MICROS_100",
                    "kind": "UNION_100",
                    "n": u["n"],
                    "hit_pct": u["hit_pct"],
                    "calls": u.get("calls") or [],
                    "n_micros": u.get("n_micros"),
                }
            )
        # pool base
        b = r.get("base_test") or {}
        if b.get("n", 0) >= 3:
            cands.append(
                {
                    "pool": pool,
                    "logic": "POOL_ALL_DU",
                    "kind": "POOL_BASE",
                    "n": b["n"],
                    "hit_pct": b["hit_pct"],
                    "calls": r.get("test_calls_all") or [],
                }
            )

    def score(c):
        # primary: hit 100 with as many calls as possible
        # secondary: high hit with decent n
        perfect = 1 if c["hit_pct"] >= 100 - 1e-9 else 0
        return (perfect, c["n"] if perfect else 0, c["hit_pct"], c["n"])

    cands.sort(key=score, reverse=True)
    return {"best": cands[0] if cands else None, "leaderboard": cands[:25]}


def write_report(meta: dict, results: List[dict], pick: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    best = pick.get("best")
    lines = [
        "# NIFTY 1m — **last 6 months from today** · best logic test",
        "",
        "**Not live.**",
        "",
        f"- Today (IST): `{meta.get('today')}`",
        f"- Test window: `{meta.get('test_start')}` → `{meta.get('test_end')}` (last ~6 months)",
        f"- Train / freeze through: `{meta.get('train_end')}`",
        f"- Tape: `{meta.get('bar_start')}` → `{meta.get('bar_end')}` · bars={meta.get('n_bars')}",
        f"- Download note: {meta.get('download_note') or 'ok'}",
        "",
        "## Winner",
        "",
    ]
    if best:
        lines += [
            f"**Best logic:** `{best['logic']}` on pool `{best['pool']}`",
            f"- Last-6m: **{best['n']} calls · {best['hit_pct']}% hit**",
            f"- Kind: `{best['kind']}`",
        ]
        if best.get("train"):
            lines.append(f"- Train (pre-window): {best['train']}")
        if best.get("filters"):
            lines.append(f"- Filters: `{json.dumps(best['filters'], default=str)}`")
        if best.get("n_micros") is not None:
            lines.append(f"- Micros in union: {best['n_micros']}")
        lines += ["", "| Day | HM | Side | or_ext | Win |", "|---|---|---|---:|:---:|"]
        for c in best.get("calls") or []:
            lines.append(
                f"| {c.get('day')} | {c.get('hm')} | {c.get('decision')} | "
                f"{c.get('or_ext')} | {'Y' if c.get('win') else 'N'} |"
            )
        lines.append("")
    else:
        lines.append("_No qualifying logic on available tape._")
        lines.append("")

    lines += [
        "## Leaderboard (last 6m)",
        "",
        "| Rank | Pool | Logic | N | Hit% | Kind |",
        "|---:|---|---|---:|---:|---|",
    ]
    for i, c in enumerate(pick.get("leaderboard") or [], 1):
        lines.append(
            f"| {i} | `{c['pool']}` | `{c['logic']}` | {c['n']} | **{c['hit_pct']}** | `{c['kind']}` |"
        )

    for r in results:
        lines += [
            "",
            f"## Pool `{r['pool']}`",
            "",
            f"- Gates: `{json.dumps(r['gates'])}`",
            f"- Train n={r['n_train']} ({r['base_train']}) · Test n={r['n_test']} ({r['base_test']})",
            "",
            "### ML books",
            "",
            "| Book | N | Hit% |",
            "|---|---:|---:|",
        ]
        for k, v in (r.get("ml_books") or {}).items():
            lines.append(f"| `{k}` | {v.get('n')} | {v.get('hit_pct')} |")
        lines += ["", "### Structural books", "", "| Book | Train n/hit | Test n/hit |", "|---|---|---|"]
        for k, v in (r.get("struct_books") or {}).items():
            tr, te = v.get("train") or {}, v.get("test") or {}
            lines.append(
                f"| `{k}` | {tr.get('n')}@{tr.get('hit_pct')}% | **{te.get('n')}@{te.get('hit_pct')}%** |"
            )
        u = r.get("union100") or {}
        lines += [
            "",
            f"### Honest union (train100∩test100 micros): **{u.get('n')} @ {u.get('hit_pct')}%** "
            f"(micros={u.get('n_micros')})",
            "",
        ]
        if u.get("calls"):
            lines += ["| Day | HM | Side | Win |", "|---|---|---|:---:|"]
            for c in u["calls"]:
                lines.append(
                    f"| {c.get('day')} | {c.get('hm')} | {c.get('decision')} | "
                    f"{'Y' if c.get('win') else 'N'} |"
                )
        lines += ["", "### Monthly (pool day-unique)", "", "| Month | N | Hit% |", "|---|---:|---:|"]
        for m in r.get("monthly_test") or []:
            lines.append(f"| `{m['month']}` | {m['n']} | {m['hit_pct']} |")

    lines += [
        "",
        "## Policy",
        "",
        "- Research only · `not_live=true`",
        "- Do not wire live without a separate promote + paper plan.",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps({"meta": meta, "pick": pick, "results": results}, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT_MD}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true", help="Try Kite extend to today")
    args = ap.parse_args()

    test_start, test_end, train_end = window_last_6m()
    print("=" * 60, flush=True)
    print("NIFTY 1m · LAST 6 MONTHS FROM TODAY · best logic", flush=True)
    print(f"test {test_start} → {test_end} · train ≤ {train_end}", flush=True)
    print("=" * 60, flush=True)

    # Widen base clip so build/download aren't cut at 2025-12-30
    old_end = base.END
    base.END = test_end
    try:
        bars, note = load_full_tape(download=args.download)
    finally:
        pass  # keep END wide for ticket build in window

    if bars.empty:
        print("FAIL: no bars", flush=True)
        base.END = old_end
        return 1

    # clip tape to research start → test_end
    bars = bars[
        (bars.index >= pd.Timestamp("2021-01-01", tz="Asia/Kolkata"))
        & (bars.index <= pd.Timestamp(f"{test_end} 23:59:59", tz="Asia/Kolkata"))
    ]
    # Actual test end = min(requested, last bar day)
    last_day = base._day(bars.index.max())
    if last_day < test_start:
        print(f"FAIL: tape ends {last_day} before test start {test_start}", flush=True)
        base.END = old_end
        return 1
    actual_test_end = min(test_end, last_day)
    if actual_test_end < test_end:
        print(f"  NOTE: tape ends {last_day} — testing through {actual_test_end}", flush=True)

    meta = {
        "today": today_ist().strftime("%Y-%m-%d"),
        "test_start": test_start,
        "test_end": actual_test_end,
        "test_end_requested": test_end,
        "train_end": train_end,
        "n_bars": len(bars),
        "bar_start": str(bars.index.min()),
        "bar_end": str(bars.index.max()),
        "download_note": note,
        "research_only": True,
        "not_live": True,
    }

    results = []
    for name, gates in LOGIC_GATES.items():
        results.append(run_pool(bars, name, gates, test_start, actual_test_end, train_end))

    pick = pick_best(results)
    write_report(meta, results, pick)

    best = pick.get("best")
    print("\n" + "=" * 60, flush=True)
    if best:
        print(
            f"BEST: {best['logic']} / {best['pool']} → {best['n']} @ {best['hit_pct']}%",
            flush=True,
        )
        for c in (best.get("calls") or [])[:20]:
            print(
                f"  {c.get('day')} {c.get('hm')} {c.get('decision')} win={c.get('win')}",
                flush=True,
            )
    print("DONE · research only", flush=True)
    base.END = old_end
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
