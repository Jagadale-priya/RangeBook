"""Deep Nov 2026 calls from 1 Nov — proven LIVE stack + 1-day empty-fill + confirm.

Books:
  1) STACK_PLUS_CROWN_HTF_CAP2     (FINALIZED proven>good>champ>crown HTF, cap2)
  2) EMPTY_FILL_FADE1030_GAP055_T35 (HOLDING 1-day fill on stack-silent + |gap|≥0.55)
  3) STACK_PLUS_EMPTY_FILL_GAP055_T35
  4) PROVEN15_PLUS_CONFIRM_T30     (HOLDING 100% accurate)
  5) ACC100_MULTI_V5 / V11 snapshot from held reports when available

  python -u prod_live/tests/builders/research_nov2026_deep_calls.py
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
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import POOL, PRIORITY, _champ_floor, _agg  # noqa: E402
from prod_live.logic.empty_fill import (  # noqa: E402
    ENTRY_HM,
    GAP_MIN_PCT,
    RISK,
    TAG as FILL_TAG,
    build_empty_fill_row,
    merge_stack_plus_empty_fill,
)
from prod_live.logic.confirm_dual_tf import (  # noqa: E402
    TAG_CONFIRM,
    build_confirm_rows,
    merge_proven15_plus_confirm,
)
from prod_live.logic.accurate_desks import build_all_accurate_desks  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "nov1_14"
DAILY = ROOT / "stock_signal_data/fno_validate/NIFTY_daily_nse.csv"
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"
CACHE_DUAL = ROOT / "stock_signal_data/fno_validate/research/_cache_dual15_dual5_10y.json"

START = "2026-11-01"
END = min(date.today().strftime("%Y-%m-%d"), "2026-11-15")


def _clean(rows: List[dict]) -> List[dict]:
    out = []
    for r in rows:
        if r is None:
            continue
        rr = dict(r)
        if "win" not in rr:
            o = rr.get("outcome")
            if o == "t1_before_sl":
                rr["win"] = True
            elif o in ("sl_before_t1", "same_bar_both"):
                rr["win"] = False
        out.append(rr)
    return out


def _hm_mins(hm: str) -> int:
    try:
        h, m = str(hm).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0


def path_score_t35(bars5: pd.DataFrame, day: str, hm: str, side: str, entry: float, risk: float = RISK) -> Tuple[Optional[bool], Optional[float], str]:
    """Intraday path T/S @ risk from entry bar forward same day."""
    day_bars = bars5[bars5["_day"] == day]
    if day_bars.empty:
        return None, None, "no_bars"
    # find entry bar at/after hm
    target = _hm_mins(hm)
    idxs = [i for i, ts in enumerate(day_bars.index) if _hm_mins(ts.strftime("%H:%M")) >= target]
    if not idxs:
        return None, None, "no_entry_bar"
    i0 = idxs[0]
    entry_px = float(day_bars["Close"].iloc[i0]) if entry is None else float(entry)
    if side == "BUY":
        sl, t1 = entry_px - risk, entry_px + risk
    else:
        sl, t1 = entry_px + risk, entry_px - risk
    fut = day_bars.iloc[i0 + 1 :]
    if fut.empty:
        return False, -risk, "no_future"
    for _, row in fut.iterrows():
        hi, lo = float(row["High"]), float(row["Low"])
        if side == "BUY":
            hit_sl, hit_t1 = lo <= sl, hi >= t1
            if hit_sl and hit_t1:
                return False, -risk, "same_bar_both"
            if hit_sl:
                return False, -risk, "sl_before_t1"
            if hit_t1:
                return True, risk, "t1_before_sl"
        else:
            hit_sl, hit_t1 = hi >= sl, lo <= t1
            if hit_sl and hit_t1:
                return False, -risk, "same_bar_both"
            if hit_sl:
                return False, -risk, "sl_before_t1"
            if hit_t1:
                return True, risk, "t1_before_sl"
    return False, -risk, "expired"


def load_bars5() -> pd.DataFrame:
    df = pd.read_csv(TAPE5)
    df["date"] = pd.to_datetime(df["date"])
    if df["date"].dt.tz is None:
        df["date"] = df["date"].dt.tz_localize("Asia/Kolkata")
    else:
        df["date"] = df["date"].dt.tz_convert("Asia/Kolkata")
    df = df.set_index("date").sort_index()
    df["_day"] = [ts.strftime("%Y-%m-%d") for ts in df.index]
    df["_hm"] = [ts.strftime("%H:%M") for ts in df.index]
    return df


def load_daily_gap() -> Dict[str, dict]:
    d = pd.read_csv(DAILY)
    d["Date"] = pd.to_datetime(d["Date"]).dt.strftime("%Y-%m-%d")
    d = d.sort_values("Date")
    out = {}
    prev_c = None
    for _, r in d.iterrows():
        day = str(r["Date"])[:10]
        o, c = float(r["Open"]), float(r["Close"])
        gap = None if prev_c is None or prev_c <= 0 else (o - prev_c) / prev_c * 100.0
        out[day] = {
            "open": o,
            "close": c,
            "prior_close": prev_c,
            "gap_pct": None if gap is None else round(gap, 4),
            "change_pct": float(r["ChangePct"]) if "ChangePct" in d.columns and pd.notna(r.get("ChangePct")) else None,
        }
        prev_c = c
    return out


def build_live_stack(start: str, end: str) -> dict:
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    sessions_all, prod2_all, _ = fs._prod2(1400)
    sess = sorted(d for d in sessions_all if start <= d <= end)

    proven = [
        dict(r, track="proven_100", priority=PRIORITY["proven_100"])
        for r in pool["proven_100"]
        if start <= r["day"] <= end
    ]
    champ = _champ_floor([r for r in pool["champion"] if start <= r["day"] <= end])
    for r in champ:
        r["track"] = "champion"
        r["priority"] = PRIORITY["champion"]
    crown = [
        dict(r, track="crown_5m", priority=PRIORITY["crown_5m"])
        for r in pool["crown_5m"]
        if start <= r["day"] <= end
    ]
    good = [
        dict(r, track="good_prod2", priority=PRIORITY["good_prod2"])
        for r in prod2_all
        if start <= r["day"] <= end
    ]
    daily = fs._load_daily()
    active = fs._active_days(sess, daily)
    crown_htf = [r for r in crown if r["day"] in active]
    stack = fs._union(
        {
            "proven_100": proven,
            "good_prod2": good,
            "champion": champ,
            "crown_5m": crown_htf,
        },
        day_cap=2,
    )
    return {
        "sess": sess,
        "stack": _clean(stack),
        "proven": proven,
        "champ": champ,
        "crown_htf": crown_htf,
        "good": _clean(good),
        "active": active,
        "raw": {
            "proven_100": proven,
            "good_prod2": good,
            "champion": champ,
            "crown_5m": crown_htf,
        },
    }


def build_empty_fills(sess: List[str], stack_days: Set[str], daily_gap: dict, bars5: pd.DataFrame) -> List[dict]:
    fills = []
    for day in sess:
        if day in stack_days:
            continue
        info = daily_gap.get(day) or {}
        o, prev = info.get("open"), info.get("prior_close")
        if o is None or prev is None:
            continue
        # entry = 10:30 5m close
        day_bars = bars5[(bars5["_day"] == day) & (bars5["_hm"] >= ENTRY_HM)]
        if day_bars.empty:
            continue
        entry_px = float(day_bars["Close"].iloc[0])
        row = build_empty_fill_row(
            day=day,
            open_px=float(o),
            prior_close=float(prev),
            entry_px=entry_px,
            hm=ENTRY_HM,
            risk=RISK,
            gap_min=GAP_MIN_PCT,
        )
        if not row:
            continue
        win, pts, outcome = path_score_t35(bars5, day, ENTRY_HM, row["decision"], entry_px, RISK)
        row["win"] = win
        row["points"] = pts
        row["outcome"] = outcome
        row["desk_tag"] = FILL_TAG
        row["accurate_tag"] = None
        row["accuracy_tag"] = None  # structure fill — never accuracy range stamp as AGREE
        row["lane"] = "HOLDING"
        row["logic_level"] = "EMPTY_FILL"
        row["tags"] = [FILL_TAG, "LOGIC_EMPTY_FILL", "ACC_FLOOR_structure"]
        fills.append(row)
    return fills


def load_dual_nov() -> Tuple[List[dict], List[dict]]:
    if not CACHE_DUAL.exists():
        return [], []
    d = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))

    def rows(block):
        out = []
        if isinstance(block, dict):
            for v in block.values():
                if isinstance(v, list):
                    out.extend(v)
        elif isinstance(block, list):
            out = block
        return [r for r in out if START <= str(r.get("day") or "") <= END]

    return rows(d.get("dual15")), rows(d.get("dual5"))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Deep Nov calls {START} → {END}", flush=True)

    print("Loading daily + 5m…", flush=True)
    daily_gap = load_daily_gap()
    bars5 = load_bars5()

    print("Building LIVE stack (proven>good>champ>crown HTF)…", flush=True)
    live = build_live_stack(START, END)
    sess = live["sess"]
    stack = live["stack"]
    stack_days = {str(r["day"]) for r in stack}
    print(f"  sessions={len(sess)} stack_calls={len(stack)} days={sorted(stack_days)}", flush=True)

    print("Building EMPTY_FILL (1-day) on silent days…", flush=True)
    fills = build_empty_fills(sess, stack_days, daily_gap, bars5)
    print(f"  fills={len(fills)}", flush=True)

    desk = merge_stack_plus_empty_fill(stack, fills, day_cap=2)

    # Stamp live stack rows
    for r in stack:
        r["lane"] = "LIVE"
        r["desk_tag"] = "STACK_PLUS_CROWN_HTF_CAP2"
        r["logic_level"] = "LIVE"
        track = str(r.get("track") or "")
        r["accurate_tag"] = None
        tags = ["STACK_PLUS_CROWN_HTF_CAP2", track, "LOGIC_LIVE"]
        if track == "proven_100":
            tags.append("PROVEN_100")
            r["accurate_tag"] = "PROVEN_100"
            r["accuracy_tag"] = "ACC_RANGE_100_100"
            tags.append("ACC_RANGE_100_100")
        r["tags"] = tags

    for r in desk:
        if r.get("holding_tag") == FILL_TAG:
            continue
        r.setdefault("lane", "LIVE")
        r.setdefault("desk_tag", "STACK_PLUS_EMPTY_FILL_GAP055_T35")

    # Confirm / proven15
    print("Building PROVEN15_PLUS_CONFIRM…", flush=True)
    d15, d5 = load_dual_nov()
    # Prefer dual from pool if cache empty for Nov
    if not d15:
        # use live proven as dual15 stand-in + empty dual5 → confirm won't add
        d15 = list(live["proven"])
    confirm = build_confirm_rows(d15, d5, tol_min=30) if d15 and d5 else []
    proven15_plus = merge_proven15_plus_confirm(live["proven"], confirm)
    proven15_plus = [r for r in proven15_plus if START <= str(r.get("day") or "") <= END]

    # ACC desks (Phase-1) for Nov window only — may be sparse
    print("Building Phase-1 accurate desks (Nov clip)…", flush=True)
    acc_nov = {}
    try:
        # reuse path caches via build_all if possible — skip heavy if fails
        from research_acc_all_levels_1y_today import (  # type: ignore
            _load_inputs,
        )
    except Exception:
        _load_inputs = None

    # Pull Nov from held priority report for ACC
    pri_path = ROOT / "prod_live" / "reports" / "1y" / "ACC_PRIORITY_LEVELS_6M_1Y.json"
    acc_calls = defaultdict(list)
    if pri_path.exists():
        pri = json.loads(pri_path.read_text(encoding="utf-8"))
        for key, block in (pri.get("results") or {}).items():
            for c in block.get("calls_1y") or []:
                day = str(c.get("day") or "")
                if START <= day <= END:
                    acc_calls[key].append(c)

    # Day-by-day table
    lines = [
        "# Deep Nov 2026 calls · from 1 Nov — proven + 1-day fill",
        "",
        f"**Window:** `{START}` → `{END}`",
        "",
        "Books used:",
        "",
        "1. **LIVE** `STACK_PLUS_CROWN_HTF_CAP2` — proven > good > champ > crown HTF · cap2",
        "2. **1-day fill** `EMPTY_FILL_FADE1030_GAP055_T35` — stack-silent + `|gap|≥0.55` · 10:30 fade · T35",
        "3. **Holding desk** `STACK_PLUS_EMPTY_FILL_GAP055_T35` = stack ∪ fill",
        "4. **Proven accurate** `PROVEN15_PLUS_CONFIRM_T30` / `PROVEN_100`",
        "5. **Holding ACC** P2F (from held report) — high-accuracy subset",
        "",
        "## Summary",
        "",
    ]

    def sum_rows(rows: List[dict]) -> dict:
        rows = [r for r in rows if r.get("win") is not None]
        n = len(rows)
        w = sum(1 for r in rows if r.get("win"))
        pts = round(sum(float(r.get("points") or 0) for r in rows), 1)
        return {
            "n": n,
            "wins": w,
            "losses": n - w,
            "hit_pct": round(100.0 * w / n, 2) if n else None,
            "points": pts,
        }

    s_live = sum_rows(stack)
    s_fill = sum_rows(fills)
    s_desk = sum_rows(desk)
    s_p15 = sum_rows(proven15_plus)

    lines += [
        "| Book | N | W/L | Hit% | Points |",
        "|---|---:|---|---:|---:|",
        f"| LIVE `STACK_PLUS_CROWN_HTF_CAP2` | {s_live['n']} | {s_live['wins']}/{s_live['losses']} | {s_live['hit_pct']} | {s_live['points']} |",
        f"| 1-day `EMPTY_FILL…T35` | {s_fill['n']} | {s_fill['wins']}/{s_fill['losses']} | {s_fill['hit_pct']} | {s_fill['points']} |",
        f"| **Holding desk stack+fill** | **{s_desk['n']}** | {s_desk['wins']}/{s_desk['losses']} | **{s_desk['hit_pct']}** | **{s_desk['points']}** |",
        f"| `PROVEN15_PLUS_CONFIRM_T30` | {s_p15['n']} | {s_p15['wins']}/{s_p15['losses']} | {s_p15['hit_pct']} | {s_p15['points']} |",
        "",
        "## Raw channels before cap (LIVE)",
        "",
        "| Channel | n |",
        "|---|---:|",
    ]
    for tr, rows in live["raw"].items():
        lines.append(f"| `{tr}` | {len(rows)} |")

    lines += [
        "",
        "## Day-by-day (every session)",
        "",
        "| Day | Gap% | LIVE stack | 1-day fill | Holding desk call(s) | Proven/ACC |",
        "|---|---:|---|---|---|---|",
    ]

    fill_by = {str(r["day"]): r for r in fills}
    stack_by = defaultdict(list)
    for r in stack:
        stack_by[str(r["day"])].append(r)
    desk_by = defaultdict(list)
    for r in desk:
        desk_by[str(r["day"])].append(r)
    p15_by = defaultdict(list)
    for r in proven15_plus:
        p15_by[str(r.get("day"))].append(r)
    # ACC P2F P100 from report
    acc_p100 = []
    for c in acc_calls.get("P2F|P100") or []:
        acc_p100.append(c)
    acc_by = defaultdict(list)
    for c in acc_p100:
        acc_by[str(c.get("day"))].append(c)

    for day in sess:
        gap = (daily_gap.get(day) or {}).get("gap_pct")
        gap_s = "—" if gap is None else f"{gap:+.2f}"
        st = stack_by.get(day) or []
        if st:
            live_s = "; ".join(
                f"{r.get('hm')} {r.get('decision')} `{r.get('track')}` "
                f"{'W' if r.get('win') else 'L'} {r.get('points')}"
                for r in st
            )
        else:
            live_s = "—"
        fl = fill_by.get(day)
        if fl:
            fill_s = (
                f"{fl.get('hm')} {fl.get('decision')} gap={fl.get('gap_pct')} "
                f"{'W' if fl.get('win') else 'L' if fl.get('win') is False else '?'} {fl.get('points')}"
            )
        else:
            if day in stack_days:
                fill_s = "(stack has call — fill off)"
            elif gap is not None and abs(gap) < GAP_MIN_PCT:
                fill_s = f"gap {gap:+.2f} < 0.55 — no fill"
            else:
                fill_s = "—"
        dk = desk_by.get(day) or []
        desk_s = "; ".join(
            f"{r.get('hm')} {r.get('decision')} "
            f"`{r.get('holding_tag') or r.get('track')}` "
            f"{'W' if r.get('win') else 'L' if r.get('win') is False else '?'}"
            for r in dk
        ) or "—"
        acc = acc_by.get(day) or []
        p15 = p15_by.get(day) or []
        bits = []
        if p15:
            bits.append("PROVEN15+")
        if acc:
            bits.append(f"ACC `{acc[0].get('tag')}`")
        acc_s = ", ".join(bits) if bits else "—"
        lines.append(f"| {day} | {gap_s} | {live_s} | {fill_s} | {desk_s} | {acc_s} |")

    lines += [
        "",
        "## LIVE stack calls (detail)",
        "",
        "| Day | HM | Side | Track | Win | Pts | Tags |",
        "|---|---|---|---|---|---:|---|",
    ]
    for r in stack:
        win = "W" if r.get("win") else "L"
        tags = ", ".join(f"`{t}`" for t in (r.get("tags") or []))
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | `{r.get('track')}` | "
            f"{win} | {r.get('points')} | {tags} |"
        )
    if not stack:
        lines.append("| — | — | — | — | — | — | no LIVE stack calls |")

    lines += [
        "",
        "## 1-day empty-fill calls (detail)",
        "",
        "| Day | HM | Side | Gap% | Win | Pts | Outcome | Tags |",
        "|---|---|---|---:|---|---:|---|---|",
    ]
    for r in fills:
        win = "W" if r.get("win") else ("L" if r.get("win") is False else "?")
        tags = ", ".join(f"`{t}`" for t in (r.get("tags") or []))
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | {r.get('gap_pct')} | "
            f"{win} | {r.get('points')} | {r.get('outcome')} | {tags} |"
        )
    if not fills:
        lines.append("| — | — | — | — | — | — | — | no fills (no silent+|gap|≥0.55 days) |")

    lines += [
        "",
        "## Why some days still empty",
        "",
        "- **LIVE proven/good/champ/crown** need OR-break + model gates; Nov often `gates_fail` / `side_score_miss`.",
        "- **1-day fill** only on stack-silent days with `|gap|≥0.55`. Small-gap silent days stay empty by design.",
        "- **ACC100 / P2F** need path-true crown/good streams — Nov only matched crown on 11-06.",
        "- **PROVEN15+confirm** needs dual15∩dual5; Nov dual pool is sparse in research cache.",
        "",
        "Tape max ~2026-11-13 · daily NSE through ~2026-11-11.",
        "",
    ]

    md = OUT / "NOV2026_DEEP_CALLS.md"
    md.write_text("\n".join(lines), encoding="utf-8")

    payload = {
        "window": {"start": START, "end": END},
        "sessions": sess,
        "summary": {
            "live_stack": s_live,
            "empty_fill": s_fill,
            "stack_plus_fill": s_desk,
            "proven15_plus_confirm": s_p15,
        },
        "live_stack_calls": stack,
        "empty_fill_calls": fills,
        "holding_desk_calls": desk,
        "proven15_plus_confirm": proven15_plus,
        "acc_p2f_p100_from_report": acc_p100,
        "daily_gap": {d: daily_gap.get(d) for d in sess},
    }
    (OUT / "NOV2026_DEEP_CALLS.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    # also mirror under reports/1y
    (ROOT / "prod_live" / "reports" / "1y" / "NOV2026_DEEP_CALLS.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", md)
    print("LIVE", s_live, "FILL", s_fill, "DESK", s_desk, "P15", s_p15)


if __name__ == "__main__":
    main()
