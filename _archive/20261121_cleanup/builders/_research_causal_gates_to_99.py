"""Find causal (live-safe) gates that approach 99% hit — no win hindsight.

  python -u prod_live/tests/builders/_research_causal_gates_to_99.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live"), str(ROOT / "prod_live" / "tests" / "builders")]
import path_setup  # noqa: F401,E402

from prod_live.logic import champ_plus_engine as eng  # noqa: E402
from research_100pct_deeper_more_calls import _norm, build_bar_index  # noqa: E402

OUT_MD = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_CAUSAL_GATES_TO_99.md"
OUT_JSON = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_CAUSAL_GATES_TO_99.json"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"

TODAY = date.today().isoformat()
START = (pd.Timestamp(TODAY) - pd.DateOffset(years=1)).date().isoformat()
END = TODAY


def win(r: dict) -> Optional[bool]:
    if r.get("win") is True:
        return True
    if r.get("win") is False:
        return False
    o = str(r.get("outcome") or "")
    if o in ("t1_before_sl", "win"):
        return True
    if o in ("sl_before_t1", "same_bar_both", "loss"):
        return False
    return None


def agg(rows: List[dict]) -> Dict[str, Any]:
    c = [r for r in rows if win(r) is not None]
    n = len(c)
    w = sum(1 for r in c if win(r))
    return {
        "n": n,
        "wins": w,
        "losses": n - w,
        "hit_pct": round(100.0 * w / n, 2) if n else None,
        "points": round(sum(30.0 if win(r) else -30.0 for r in c), 1),
    }


def side(r: dict) -> str:
    return str(r.get("decision") or r.get("side") or "").upper()


def key(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day") or "")[:10], side(r), str(r.get("hm") or "")[:5])


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
        if buy_p is not None and sd == "BUY" and p < buy_p:
            continue
        if sell_p is not None and sd == "SELL" and p < sell_p:
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


def main() -> int:
    print(f"Causal gates → 99%? · {START}→{END}", flush=True)
    bars = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    hm = bars.index.strftime("%H:%M")
    bars = bars[(hm >= "09:15") & (hm <= "15:30")]
    ix = build_bar_index(bars)
    days = sorted({str(t.date()) for t in bars.index if START <= str(t.date()) <= END})

    all_scored: List[dict] = []
    seen: Set[Tuple[str, str, str]] = set()
    for i, day in enumerate(days, 1):
        cands = eng._load_cache_candidates_for_day(day)
        scored = eng.score_candidates(cands)
        for r in scored:
            if r.get("track") == "champion" and not eng._champ_floor_ok(r):
                continue
            if side(r) not in ("BUY", "SELL") or r.get("entry") is None:
                continue
            s = eng.path_score_one(bars, ix, day, str(r.get("hm") or ""), side(r))
            if not s:
                continue
            rr = dict(r)
            rr.update(s)
            k = key(rr)
            if k in seen:
                continue
            seen.add(k)
            all_scored.append(rr)
        if i % 50 == 0:
            print(f"  days {i}/{len(days)} pool={len(all_scored)}", flush=True)
    print(f"pool={len(all_scored)} {agg(all_scored)}", flush=True)

    results: List[dict] = []
    tracks_opts: List[Optional[Set[str]]] = [
        None,
        {"champion", "proven_research", "dual10m"},
        {"champion", "proven_research"},
        {"champion"},
        {"dual10m"},
        {"proven_research", "dual10m"},
        {"good_prod2", "champion", "proven_research"},
    ]
    pmins = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
    caps = [1, 2, 3, 4, 6]
    hm_windows = [
        (None, None),
        ("09:30", "14:30"),
        ("10:00", "14:00"),
        ("09:45", "13:30"),
    ]

    for cap in caps:
        for pmin in pmins:
            for tracks in tracks_opts:
                for hm_lo, hm_hi in hm_windows:
                    book = fill(
                        all_scored,
                        cap,
                        pmin=pmin,
                        tracks=tracks,
                        hm_lo=hm_lo,
                        hm_hi=hm_hi,
                    )
                    st = agg(book)
                    if not st["n"]:
                        continue
                    hit = st["hit_pct"] or 0
                    results.append(
                        {
                            "cap": cap,
                            "pmin": pmin,
                            "tracks": sorted(tracks) if tracks else "ALL",
                            "hm": f"{hm_lo or '*'}-{hm_hi or '*'}",
                            **st,
                            "meets_99": hit >= 99.0,
                            "meets_98": hit >= 98.0,
                            "meets_95": hit >= 95.0,
                            "meets_90": hit >= 90.0,
                        }
                    )

    for cap in (1, 2, 4, 6):
        for bp, sp in (
            (0.70, 0.70),
            (0.75, 0.75),
            (0.80, 0.80),
            (0.85, 0.85),
            (0.90, 0.90),
            (0.70, 0.75),
            (0.75, 0.80),
            (0.80, 0.85),
        ):
            book = fill(all_scored, cap, buy_p=bp, sell_p=sp)
            st = agg(book)
            if not st["n"]:
                continue
            hit = st["hit_pct"] or 0
            results.append(
                {
                    "cap": cap,
                    "pmin": f"B{bp}/S{sp}",
                    "tracks": "ALL",
                    "hm": "*-*",
                    **st,
                    "meets_99": hit >= 99.0,
                    "meets_98": hit >= 98.0,
                    "meets_95": hit >= 95.0,
                    "meets_90": hit >= 90.0,
                }
            )

    def best(flag: str) -> Optional[dict]:
        ok = [r for r in results if r.get(flag)]
        return max(ok, key=lambda x: (x["n"], x["hit_pct"] or 0)) if ok else None

    b99, b98, b95, b90 = best("meets_99"), best("meets_98"), best("meets_95"), best("meets_90")
    base = fill(all_scored, 6, pmin=0.0)
    base_st = agg(base)
    top20 = sorted([r for r in results if r["n"] >= 20], key=lambda x: (-(x["hit_pct"] or 0), -x["n"]))[:20]
    top50 = sorted([r for r in results if r["n"] >= 50], key=lambda x: (-(x["hit_pct"] or 0), -x["n"]))[:15]

    print("baseline Cap6", base_st)
    print("best>=99", b99)
    print("best>=98", b98)
    print("best>=95", b95)
    print("best>=90", b90)

    lines = [
        "# Causal gates toward 99% live accuracy",
        "",
        f"**Window:** `{START}` → `{END}` · ±30 · **no win hindsight**",
        "",
        "## Can we get 99% on live?",
        "",
    ]
    if b99:
        lines.append(
            f"**YES with tight gates:** Cap{b99['cap']} · p≥{b99['pmin']} · "
            f"tracks={b99['tracks']} · hm={b99['hm']} → **{b99['n']} @ {b99['hit_pct']}%**"
        )
        lines.append("")
        lines.append("Tradeoff: much fewer calls than open Cap6.")
    else:
        lines.append(
            "**No causal gate in this grid reached ≥99% with volume.** "
            "The old 99% book used win-lookahead and cannot be rebuilt as a dense live book."
        )
    lines.append("")
    if b98:
        lines.append(
            f"- Best ≥98%: Cap{b98['cap']} p≥{b98['pmin']} tracks={b98['tracks']} "
            f"hm={b98['hm']} → **{b98['n']}@{b98['hit_pct']}%**"
        )
    if b95:
        lines.append(
            f"- Best ≥95%: Cap{b95['cap']} p≥{b95['pmin']} tracks={b95['tracks']} "
            f"hm={b95['hm']} → **{b95['n']}@{b95['hit_pct']}%**"
        )
    if b90:
        lines.append(
            f"- Best ≥90%: Cap{b90['cap']} p≥{b90['pmin']} tracks={b90['tracks']} "
            f"hm={b90['hm']} → **{b90['n']}@{b90['hit_pct']}%**"
        )
    lines += [
        "",
        f"Open Cap6 baseline: **{base_st['n']} @ {base_st['hit_pct']}%**",
        "",
        "## Live-safe levers (real hacks)",
        "",
        "1. **Raise p_t1 floor** (strongest)",
        "2. **Lower day cap** (Cap1–2)",
        "3. **Whitelist tracks** (champion / proven / dual10m)",
        "4. **Time window** (skip weak open/late)",
        "",
        "## Not live-safe (fake 99%)",
        "",
        "- Filter on historical `win`",
        "- Year accuracy floor after seeing outcomes",
        "- Measure Cap6 while crown/scalper notify",
        "",
        "## Top (N≥20) by hit%",
        "",
        "| Cap | pmin | Tracks | HM | N | Hit% | W/L |",
        "|---:|---|---|---|---:|---:|---|",
    ]
    for r in top20:
        lines.append(
            f"| {r['cap']} | {r['pmin']} | {r['tracks']} | {r['hm']} | {r['n']} | "
            f"**{r['hit_pct']}%** | {r['wins']}/{r['losses']} |"
        )
    lines += [
        "",
        "## Top (N≥50) by hit%",
        "",
        "| Cap | pmin | Tracks | HM | N | Hit% | W/L |",
        "|---:|---|---|---|---:|---:|---|",
    ]
    for r in top50:
        lines.append(
            f"| {r['cap']} | {r['pmin']} | {r['tracks']} | {r['hm']} | {r['n']} | "
            f"**{r['hit_pct']}%** | {r['wins']}/{r['losses']} |"
        )
    lines += ["", f"JSON: `{OUT_JSON}`", ""]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(
            {
                "baseline_cap6": base_st,
                "best_99": b99,
                "best_98": b98,
                "best_95": b95,
                "best_90": b90,
                "top20_n20": top20,
                "top15_n50": top50,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print("\n".join(lines[:40]))
    print("wrote", OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
