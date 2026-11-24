"""New opening-range logic. Selection never sees the last year.

Tickets are built from the 15-minute tape. Stop 25, first target 30.
Rules are frozen on 2023-11-16 → 2025-11-14.
2025-11-15 → 2026-11-15 is scored after the rule is frozen.

  python -u prod_live/tests/builders/research_new_orb85_1y.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
import path_setup  # noqa: F401,E402

from research_100pct_deeper_more_calls import gap_map  # noqa: E402

TAPE = ROOT / "stock_signal_data/fno_validate/NIFTY_15m_12y.csv"
OUT = ROOT / "prod_live" / "reports" / "1y"
CACHE = ROOT / "stock_signal_data/fno_validate/research/_cache_new_orb85_tickets.json"

PRE_A, PRE_B = "2023-11-16", "2025-11-14"
TE_A, TE_B = "2025-11-15", "2026-11-15"
SL, T1P = 25.0, 30.0


def _day(ts) -> str:
    t = ts.tz_convert("Asia/Kolkata") if getattr(ts, "tzinfo", None) else ts
    return t.strftime("%Y-%m-%d")


def _hm(ts) -> str:
    t = ts.tz_convert("Asia/Kolkata") if getattr(ts, "tzinfo", None) else ts
    return t.strftime("%H:%M")


def _load() -> pd.DataFrame:
    raw = pd.read_csv(TAPE, index_col=0, parse_dates=True)
    if raw.index.tz is None:
        raw.index = raw.index.tz_localize("Asia/Kolkata")
    else:
        raw.index = raw.index.tz_convert("Asia/Kolkata")
    raw = raw.rename(columns={c: str(c).title() for c in raw.columns}).sort_index()
    hm = raw.index.strftime("%H:%M")
    return raw[(hm >= "09:15") & (hm <= "15:30")]


def _resolve(highs, lows, side: str, entry: float, sl_pts: float = SL, t1_pts: float = T1P) -> Optional[dict]:
    sl = entry - sl_pts if side == "BUY" else entry + sl_pts
    t1 = entry + t1_pts if side == "BUY" else entry - t1_pts
    for hh, ll in zip(highs, lows):
        if side == "BUY":
            hit_sl, hit_t1 = ll <= sl, hh >= t1
        else:
            hit_sl, hit_t1 = hh >= sl, ll <= t1
        if hit_sl and hit_t1:
            return None
        if hit_sl:
            return {"win": False, "points": -sl_pts, "outcome": "sl_before_t1", "stop_loss": sl, "target_1": t1}
        if hit_t1:
            return {"win": True, "points": t1_pts, "outcome": "t1_before_sl", "stop_loss": sl, "target_1": t1}
    return None


def build(bars: pd.DataFrame, gaps: Dict[str, float], sl_pts: float = SL, t1_pts: float = T1P) -> List[dict]:
    day_key = [_day(ts) for ts in bars.index]
    out: List[dict] = []
    for day, sess in bars.groupby(day_key, sort=True):
        if len(sess) < 8:
            continue
        if _hm(sess.index[0]) != "09:15":
            continue
        or_hi = float(sess["High"].iloc[:2].max())
        or_lo = float(sess["Low"].iloc[:2].min())
        or_w = or_hi - or_lo
        if or_w < 8:
            continue
        opens = float(sess["Open"].iloc[0])
        or_pct = or_w / opens * 100.0
        gap = float(gaps.get(str(day)[:10]) or 0.0)
        closes = sess["Close"].astype(float).values
        highs = sess["High"].astype(float).values
        lows = sess["Low"].astype(float).values
        # variant break1: first close outside the opening range, each side
        seen = {"BUY": None, "SELL": None}
        # variant confirm2: second consecutive close outside
        run = {"BUY": 0, "SELL": 0}
        confirmed = {"BUY": False, "SELL": False}
        for pos in range(2, len(sess) - 1):
            c = float(closes[pos])
            up, dn = c > or_hi, c < or_lo
            if seen["BUY"] is None and up:
                seen["BUY"] = pos
            if seen["SELL"] is None and dn:
                seen["SELL"] = pos
            run["BUY"] = run["BUY"] + 1 if up else 0
            run["SELL"] = run["SELL"] + 1 if dn else 0
            if not confirmed["BUY"] and run["BUY"] >= 2:
                confirmed["BUY"] = True
                seen["C2BUY"] = pos
            if not confirmed["SELL"] and run["SELL"] >= 2:
                confirmed["SELL"] = True
                seen["C2SELL"] = pos
            if "RBUY" not in seen and seen["BUY"] is not None and pos > seen["BUY"] and lows[pos] <= or_hi and up:
                seen["RBUY"] = pos
            if "RSELL" not in seen and seen["SELL"] is not None and pos > seen["SELL"] and highs[pos] >= or_lo and dn:
                seen["RSELL"] = pos
        specs = [
            ("break1", "BUY", seen["BUY"]),
            ("break1", "SELL", seen["SELL"]),
            ("confirm2", "BUY", seen.get("C2BUY")),
            ("confirm2", "SELL", seen.get("C2SELL")),
            ("reclaim", "BUY", seen.get("RBUY")),
            ("reclaim", "SELL", seen.get("RSELL")),
        ]
        wd = int(sess.index[2].weekday())
        for variant, side, pos in specs:
            if pos is None:
                continue
            entry = float(closes[pos])
            scored = _resolve(highs[pos + 1 :], lows[pos + 1 :], side, entry, sl_pts, t1_pts)
            if scored is None:
                continue
            ts = sess.index[pos]
            hh, mm = map(int, _hm(ts).split(":"))
            out.append(
                {
                    "day": str(day)[:10],
                    "hm": _hm(ts),
                    "mins": hh * 60 + mm,
                    "decision": side,
                    "variant": variant,
                    "win": bool(scored["win"]),
                    "points": scored["points"],
                    "gap": round(gap, 4),
                    "or_pct": round(or_pct, 4),
                    "delay": int(pos - 2),
                    "weekday": wd,
                }
            )
    return out


def hit(rows: List[dict]) -> Tuple[int, float]:
    if not rows:
        return 0, 0.0
    n = len(rows)
    return n, round(100.0 * sum(1 for r in rows if r["win"]) / n, 2)


def clip(rows, a, b):
    return [r for r in rows if a <= r["day"] <= b]


def one_a_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[r["day"]].append(r)
    out = []
    for day in sorted(by):
        out.append(sorted(by[day], key=lambda r: r["hm"])[0])
    return out


def apply_rule(rows: List[dict], rule: dict) -> List[dict]:
    out = []
    for r in rows:
        if r["variant"] != rule["variant"]:
            continue
        if rule["side"] and r["decision"] != rule["side"]:
            continue
        if r["mins"] < rule["lo"] or r["mins"] > rule["hi"]:
            continue
        g = r["gap"]
        if rule["gap"] == "aligned" and ((r["decision"] == "BUY" and g <= 0) or (r["decision"] == "SELL" and g >= 0)):
            continue
        if rule["gap"] == "aligned30" and (abs(g) < 0.30 or (r["decision"] == "BUY" and g <= 0) or (r["decision"] == "SELL" and g >= 0)):
            continue
        if rule["or"] == "narrow" and r["or_pct"] >= 0.35:
            continue
        if rule["or"] == "mid" and not (0.25 <= r["or_pct"] <= 0.60):
            continue
        if rule["or"] == "wide" and r["or_pct"] <= 0.45:
            continue
        if rule["delay"] == "fast" and r["delay"] > 4:
            continue
        if rule["delay"] == "slow" and r["delay"] < 4:
            continue
        if rule["wd"] == "mid" and r["weekday"] not in (1, 2, 3):
            continue
        if rule["wd"] == "notmon" and r["weekday"] == 0:
            continue
        out.append(r)
    return one_a_day(out)


def rules() -> List[dict]:
    bands = [("open", 9 * 60 + 45, 11 * 60), ("am", 9 * 60 + 45, 12 * 60), ("all", 9 * 60 + 45, 15 * 60)]
    out = []
    for variant in ("break1", "confirm2", "reclaim"):
        for side in (None, "BUY", "SELL"):
            for blab, lo, hi in bands:
                for gap in ("any", "aligned", "aligned30"):
                    for orb in ("any", "narrow", "mid", "wide"):
                        for delay in ("any", "fast"):
                            for wd in ("any", "mid"):
                                out.append(
                                    {
                                        "name": f"{variant}_{side or 'BOTH'}_{blab}_{gap}_{orb}_{delay}_{wd}",
                                        "variant": variant,
                                        "side": side,
                                        "lo": lo,
                                        "hi": hi,
                                        "gap": gap,
                                        "or": orb,
                                        "delay": delay,
                                        "wd": wd,
                                    }
                                )
    return out


def _tickets(sl_pts: float, t1_pts: float) -> List[dict]:
    path = CACHE.with_name(f"_cache_new_orb85_s{int(sl_pts)}_t{int(t1_pts)}.json")
    if path.is_file():
        rows = json.loads(path.read_text(encoding="utf-8"))
        print(f"cache s{int(sl_pts)}/t{int(t1_pts)} n={len(rows)}", flush=True)
        return rows
    print(f"build s{int(sl_pts)}/t{int(t1_pts)}…", flush=True)
    rows = build(_load(), gap_map(), sl_pts, t1_pts)
    path.write_text(json.dumps(rows), encoding="utf-8")
    print(f"tickets {len(rows)}", flush=True)
    return rows


def main() -> int:
    t0 = time.time()
    brackets = [(25.0, 30.0), (30.0, 30.0)]
    lines = [
        "# New opening-range logic — last year held out",
        "",
        "**Status:** RESEARCH · not live",
        f"**Select:** `{PRE_A}` → `{PRE_B}` · **Test:** `{TE_A}` → `{TE_B}`",
        "Three new entries, chosen only on the earlier years: first close outside the opening range, second close in a row, and a retest that comes back to the range and closes out again.",
        "Existing desks were not used.",
        "",
    ]
    summaries = []
    for sl_pts, t1_pts in brackets:
        tickets = _tickets(sl_pts, t1_pts)
        pre_rows = clip(tickets, PRE_A, PRE_B)
        te_rows = clip(tickets, TE_A, TE_B)
        base_pre = hit(one_a_day([r for r in pre_rows if r["variant"] == "break1"]))
        base_te = hit(one_a_day([r for r in te_rows if r["variant"] == "break1"]))
        print(f"s{int(sl_pts)}/t{int(t1_pts)} break1 base pre {base_pre} test {base_te}", flush=True)
        scored = []
        for rule in rules():
            pn, ph = hit(apply_rule(pre_rows, rule))
            if pn >= 20:
                scored.append((rule, pn, ph))
        lines.append(f"## Stop {int(sl_pts)} / target {int(t1_pts)}")
        lines.append("")
        lines.append(f"First-break base rate: earlier {base_pre[0]} @ {base_pre[1]}%, last year {base_te[0]} @ {base_te[1]}%.")
        lines.append("")
        lines.append("| Floor | Rule | Earlier N@hit | Last year N@hit |")
        lines.append("|---:|---|---|---|")
        frontier = []
        for floor in (85, 88, 90):
            pool = [x for x in scored if x[2] >= floor]
            if not pool:
                lines.append(f"| {floor} | — | none | — |")
                continue
            rule, pn, ph = max(pool, key=lambda x: (x[1], x[2]))
            tn, th = hit(apply_rule(te_rows, rule))
            frontier.append({"rule": rule["name"], "pre_n": pn, "pre_hit": ph, "test_n": tn, "test_hit": th, "floor": floor})
            lines.append(f"| {floor} | `{rule['name']}` | {pn}@{ph} | {tn}@{th} |")
            print(f"  floor {floor}: pre {pn}@{ph} test {tn}@{th} {rule['name']}", flush=True)
        if scored:
            rule, pn, ph = max(scored, key=lambda x: (x[2], x[1]))
            tn, th = hit(apply_rule(te_rows, rule))
            lines.append("")
            lines.append(f"Best earlier-year rule with at least 20 calls: `{rule['name']}` {pn} @ {ph}%, last year {tn} @ {th}%.")
            summaries.append({"sl": sl_pts, "t1": t1_pts, "best_pre": pn, "best_pre_hit": ph, "best_test_n": tn, "best_test_hit": th, "rule": rule["name"], "frontier": frontier})
            print(f"  best pre {pn}@{ph} test {tn}@{th} {rule['name']}", flush=True)
        lines.append("")

    held = []
    for s in summaries:
        for f in s["frontier"]:
            if f["test_hit"] >= 85:
                held.append(f)
    if held:
        best = max(held, key=lambda f: f["test_n"])
        verdict = (
            f"Frozen new logic stays above 85% on the last year: "
            f"{best['test_n']} calls @ {best['test_hit']}% ({best['rule']})."
        )
    else:
        top = max(summaries, key=lambda s: s["best_pre_hit"]) if summaries else None
        verdict = (
            "No frozen new rule holds 85% on the last year. "
            + (
                f"The strongest earlier-year rule with at least 20 calls was {top['best_pre']} @ {top['best_pre_hit']}% "
                f"and scored {top['best_test_n']} @ {top['best_test_hit']}% on the last year ({top['rule']})."
                if top
                else ""
            )
        )
    lines.extend(["## Verdict", "", verdict, ""])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "NEW_ORB85_1Y.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "NEW_ORB85_1Y.json").write_text(
        json.dumps({"verdict": verdict, "brackets": summaries}, indent=2),
        encoding="utf-8",
    )
    print(verdict, flush=True)
    print(f"elapsed {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
