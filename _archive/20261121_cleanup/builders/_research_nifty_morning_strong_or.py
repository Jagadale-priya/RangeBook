"""Research: catch strong NIFTY morning BUY OR thrusts dual/CHAMP miss.

Target miss shape (2026-11-20): first close>OR ~09:45, or_ext~0.23, huge day
up-move, dual side_score_miss (p_t1 soft), CHAMP empty.

Brackets: ±30 (CHAMP_PLUS). Cap 1 BUY / day.
Freeze = older sessions; holdout = last 40 sessions.

  python -u prod_live/tests/builders/_research_nifty_morning_strong_or.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app"), str(ROOT / "app" / "market"), str(ROOT / "app" / "fno"), str(ROOT / "app" / "legacy")]
import path_setup  # noqa: F401,E402

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT_DIR / "NIFTY_MORNING_STRONG_OR.md"
OUT_JSON = OUT_DIR / "NIFTY_MORNING_STRONG_OR.json"
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_kite.csv"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
SL = 30.0
T1 = 30.0
HOLDOUT_SESSIONS = 40
MIN_FREEZE_N = 20
MIN_HOLD_N = 5
MIN_HOLD_HIT = 80.0
MIN_FREEZE_HIT = 85.0


def _load_tape(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.columns = [str(c).strip().title() for c in df.columns]
    if df.index.tz is None:
        df.index = df.index.tz_localize("Asia/Kolkata")
    else:
        df.index = df.index.tz_convert("Asia/Kolkata")
    return df.sort_index()


def _hm(ts: Any) -> str:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("Asia/Kolkata")
    return f"{int(t.hour):02d}:{int(t.minute):02d}"


def _session_days(df: pd.DataFrame) -> List[str]:
    return sorted({str(pd.Timestamp(t).tz_convert("Asia/Kolkata").date()) for t in df.index})


def _path_outcome(entry: float, side: str, after: pd.DataFrame) -> str:
    """Return win|loss|open using high/low path (T1 before SL)."""
    if after is None or after.empty:
        return "open"
    if side == "BUY":
        sl, t1 = entry - SL, entry + T1
        for _, r in after.iterrows():
            lo, hi = float(r["Low"]), float(r["High"])
            hit_sl = lo <= sl
            hit_t1 = hi >= t1
            if hit_sl and hit_t1:
                return "loss"  # conservative same-bar
            if hit_t1:
                return "win"
            if hit_sl:
                return "loss"
        return "open"
    sl, t1 = entry + SL, entry - T1
    for _, r in after.iterrows():
        lo, hi = float(r["Low"]), float(r["High"])
        hit_sl = hi >= sl
        hit_t1 = lo <= t1
        if hit_sl and hit_t1:
            return "loss"
        if hit_t1:
            return "win"
        if hit_sl:
            return "loss"
    return "open"


@dataclass(frozen=True)
class Gate:
    name: str
    min_bf: float = 0.15
    max_bf: float = 9.0
    hm_list: Tuple[str, ...] = ("09:45",)
    first_break_only: bool = True
    require_green: bool = True
    min_uplift_from_open: float = 0.0
    break_prior_highs: int = 0
    max_or_width: float = 9999.0
    min_or_width: float = 0.0
    buy_only: bool = True


GATES: List[Gate] = [
    Gate("sx_like_bf20_0945", min_bf=0.20, hm_list=("09:45",), require_green=False, first_break_only=False),
    Gate("sx_like_bf15_0945", min_bf=0.15, hm_list=("09:45",), require_green=False, first_break_only=False),
    Gate("sx_like_bf25_0945", min_bf=0.25, hm_list=("09:45",), require_green=False, first_break_only=False),
    Gate("first_bf20_green_0945", min_bf=0.20, hm_list=("09:45",), require_green=True, first_break_only=True),
    Gate("first_bf15_green_0945", min_bf=0.15, hm_list=("09:45",), require_green=True, first_break_only=True),
    Gate("first_bf20_green_0930_1000", min_bf=0.20, hm_list=("09:30", "09:45", "10:00"), require_green=True, first_break_only=True),
    Gate("first_bf20_green_uplift80", min_bf=0.20, hm_list=("09:45", "10:00", "10:15"), require_green=True, first_break_only=True, min_uplift_from_open=80.0),
    Gate("first_bf20_green_uplift120", min_bf=0.20, hm_list=("09:45", "10:00", "10:15", "10:30"), require_green=True, first_break_only=True, min_uplift_from_open=120.0),
    Gate("first_bf20_prior1", min_bf=0.20, hm_list=("09:45", "10:00"), require_green=True, first_break_only=True, break_prior_highs=1),
    Gate("first_bf20_prior2", min_bf=0.20, hm_list=("09:45", "10:00", "10:15"), require_green=True, first_break_only=True, break_prior_highs=2),
    Gate("first_bf18_green_width80_220", min_bf=0.18, hm_list=("09:45",), require_green=True, first_break_only=True, min_or_width=80.0, max_or_width=220.0),
    Gate("first_bf22_green_0945", min_bf=0.22, hm_list=("09:45",), require_green=True, first_break_only=True),
    Gate("cont_bf20_green_after_first", min_bf=0.20, hm_list=("10:00", "10:15", "10:30"), require_green=True, first_break_only=False, min_uplift_from_open=100.0),
]


def _first_break_pos(sess: pd.DataFrame, or_hi: float, or_lo: float) -> Tuple[Optional[int], Optional[int]]:
    closes = sess["Close"].astype(float)
    first_up = first_dn = None
    for i in range(len(sess)):
        c = float(closes.iloc[i])
        if first_up is None and c > or_hi:
            first_up = i
        if first_dn is None and c < or_lo:
            first_dn = i
    return first_up, first_dn


def evaluate_day(sess: pd.DataFrame, gate: Gate, path5: Optional[pd.DataFrame]) -> Optional[dict]:
    if sess is None or len(sess) < 2:
        return None
    or_hi = float(sess["High"].astype(float).iloc[0])
    or_lo = float(sess["Low"].astype(float).iloc[0])
    width = or_hi - or_lo
    if width <= 0:
        return None
    if width < gate.min_or_width or width > gate.max_or_width:
        return None
    day_open = float(sess["Open"].astype(float).iloc[0])
    first_up, first_dn = _first_break_pos(sess, or_hi, or_lo)
    for i, ts in enumerate(sess.index):
        hm = _hm(ts)
        if hm not in gate.hm_list:
            continue
        close = float(sess["Close"].astype(float).iloc[i])
        opn = float(sess["Open"].astype(float).iloc[i])
        if gate.buy_only:
            if close <= or_hi:
                continue
            side = "BUY"
            bf = (close - or_hi) / width
        else:
            if close > or_hi:
                side, bf = "BUY", (close - or_hi) / width
            elif close < or_lo:
                side, bf = "SELL", (or_lo - close) / width
            else:
                continue
        if bf < gate.min_bf or bf > gate.max_bf:
            continue
        if gate.require_green and side == "BUY" and close <= opn:
            continue
        if gate.require_green and side == "SELL" and close >= opn:
            continue
        if gate.first_break_only:
            if side == "BUY" and first_up is None:
                continue
            if side == "BUY" and i != first_up:
                continue
            if side == "SELL" and (first_dn is None or i != first_dn):
                continue
        if gate.min_uplift_from_open > 0 and side == "BUY":
            if (close - day_open) < gate.min_uplift_from_open:
                continue
        if gate.break_prior_highs > 0 and i >= gate.break_prior_highs and side == "BUY":
            prior = [float(sess["High"].astype(float).iloc[j]) for j in range(i - gate.break_prior_highs, i)]
            if close <= max(prior):
                continue
        entry = close
        # path on 5m if available else remaining 15m
        after = None
        if path5 is not None and not path5.empty:
            after = path5[path5.index > ts]
        if after is None or after.empty:
            after = sess.iloc[i + 1 :]
        outc = _path_outcome(entry, side, after)
        day_hi = float(sess["High"].astype(float).max())
        day_lo = float(sess["Low"].astype(float).min())
        strong_day = (day_hi - day_open) >= 150.0 if side == "BUY" else (day_open - day_lo) >= 150.0
        return {
            "day": str(pd.Timestamp(ts).tz_convert("Asia/Kolkata").date()),
            "hm": hm,
            "side": side,
            "entry": round(entry, 2),
            "bf": round(bf, 4),
            "or_width": round(width, 2),
            "uplift": round(close - day_open, 1),
            "outcome": outc,
            "win": outc == "win",
            "strong_day": strong_day,
            "day_up_pts": round(day_hi - day_open, 1),
            "gate": gate.name,
        }
    return None


def summarize(calls: List[dict]) -> Dict[str, Any]:
    decided = [c for c in calls if c.get("outcome") in ("win", "loss")]
    n = len(decided)
    wins = sum(1 for c in decided if c["win"])
    return {
        "n": n,
        "wins": wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else None,
        "open": sum(1 for c in calls if c.get("outcome") == "open"),
        "strong_day_n": sum(1 for c in calls if c.get("strong_day")),
        "strong_day_hit": (
            round(
                100.0
                * sum(1 for c in calls if c.get("strong_day") and c.get("win"))
                / max(1, sum(1 for c in calls if c.get("strong_day") and c.get("outcome") in ("win", "loss"))),
                2,
            )
            if any(c.get("strong_day") and c.get("outcome") in ("win", "loss") for c in calls)
            else None
        ),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not TAPE15.exists():
        raise SystemExit(f"missing tape {TAPE15}")
    df15 = _load_tape(TAPE15)
    df5 = _load_tape(TAPE5) if TAPE5.exists() else None
    days = _session_days(df15)
    # use last ~2y of sessions if available
    if len(days) > 520:
        days = days[-520:]
    freeze_days = days[:-HOLDOUT_SESSIONS] if len(days) > HOLDOUT_SESSIONS + MIN_FREEZE_N else days[: max(1, len(days) - HOLDOUT_SESSIONS)]
    hold_days = days[-HOLDOUT_SESSIONS:]
    hold_set = set(hold_days)
    print(f"sessions={len(days)} freeze={len(freeze_days)} holdout={len(hold_days)}", flush=True)

    # Pre-slice once — avoid O(gates * days) full-index strftime filters.
    by15: Dict[str, pd.DataFrame] = {d: g for d, g in df15.groupby(df15.index.strftime("%Y-%m-%d"))}
    by5: Dict[str, pd.DataFrame] = {}
    if df5 is not None:
        by5 = {d: g for d, g in df5.groupby(df5.index.strftime("%Y-%m-%d"))}
    strong_hold_days = 0
    for d in hold_days:
        sess = by15.get(d)
        if sess is None or sess.empty:
            continue
        day_open = float(sess["Open"].iloc[0])
        day_hi = float(sess["High"].max())
        if (day_hi - day_open) >= 150:
            strong_hold_days += 1
    print(f"holdout_strong_days={strong_hold_days}", flush=True)

    results = []
    for gate in GATES:
        freeze_calls: List[dict] = []
        hold_calls: List[dict] = []
        for d in days:
            sess = by15.get(d)
            if sess is None or sess.empty:
                continue
            call = evaluate_day(sess, gate, by5.get(d))
            if not call:
                continue
            if d in hold_set:
                hold_calls.append(call)
            else:
                freeze_calls.append(call)
        fz = summarize(freeze_calls)
        ho = summarize(hold_calls)
        strong_caught = sum(1 for c in hold_calls if c.get("strong_day"))
        # Recheck catch vs all strong holdout days (not just gated strong_day on calls)
        strong_caught = 0
        hold_call_days = {c["day"] for c in hold_calls}
        for d in hold_days:
            sess = by15.get(d)
            if sess is None or sess.empty:
                continue
            day_open = float(sess["Open"].iloc[0])
            day_hi = float(sess["High"].max())
            if (day_hi - day_open) >= 150 and d in hold_call_days:
                strong_caught += 1
        catch = round(100.0 * strong_caught / strong_hold_days, 1) if strong_hold_days else None
        row = {
            "gate": gate.name,
            "params": asdict(gate),
            "freeze": fz,
            "holdout": ho,
            "holdout_strong_days": strong_hold_days,
            "holdout_strong_caught": strong_caught,
            "holdout_strong_catch_pct": catch,
            "pass": bool(
                fz["n"] >= MIN_FREEZE_N
                and ho["n"] >= MIN_HOLD_N
                and (fz["hit_pct"] or 0) >= MIN_FREEZE_HIT
                and (ho["hit_pct"] or 0) >= MIN_HOLD_HIT
            ),
        }
        results.append(row)
        print(
            f"{gate.name:40s} fz {fz['n']:3d}@{fz['hit_pct']}  "
            f"ho {ho['n']:3d}@{ho['hit_pct']}  strong_catch {catch}%  pass={row['pass']}",
            flush=True,
        )

    results.sort(
        key=lambda r: (
            int(r["pass"]),
            (r["holdout"]["hit_pct"] or 0),
            (r["holdout_strong_catch_pct"] or 0),
            (r["freeze"]["hit_pct"] or 0),
            r["holdout"]["n"],
        ),
        reverse=True,
    )
    best = results[0] if results else None
    # also pick best by holdout hit among n>=MIN_HOLD_N
    eligible = [r for r in results if (r["holdout"]["n"] or 0) >= MIN_HOLD_N and (r["freeze"]["n"] or 0) >= 10]
    best_acc = max(eligible, key=lambda r: ((r["holdout"]["hit_pct"] or 0), (r["freeze"]["hit_pct"] or 0))) if eligible else best

    payload = {
        "brackets": {"sl": SL, "t1": T1},
        "holdout_sessions": HOLDOUT_SESSIONS,
        "min_gates": {
            "freeze_n": MIN_FREEZE_N,
            "hold_n": MIN_HOLD_N,
            "freeze_hit": MIN_FREEZE_HIT,
            "hold_hit": MIN_HOLD_HIT,
        },
        "results": results,
        "best_pass": best if best and best["pass"] else None,
        "best_accuracy": best_acc,
        "note": (
            "Morning strong OR BUY research for dual side_score_miss fills. "
            "Outcome = T1 before SL on 5m path (±30)."
        ),
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# NIFTY morning strong OR BUY research",
        "",
        f"Brackets ±{SL:.0f}. Holdout last {HOLDOUT_SESSIONS} sessions. Path = 5m T1-before-SL.",
        "",
        "## Ranking (pass first, then holdout hit, strong-day catch)",
        "",
        "| gate | freeze n@hit | holdout n@hit | strong catch | pass |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| `{r['gate']}` | {r['freeze']['n']}@{r['freeze']['hit_pct']} | "
            f"{r['holdout']['n']}@{r['holdout']['hit_pct']} | "
            f"{r['holdout_strong_catch_pct']}% | {r['pass']} |"
        )
    lines += ["", "## Best accuracy (n floors)", ""]
    if best_acc:
        lines.append(f"- **{best_acc['gate']}** holdout {best_acc['holdout']['n']}@{best_acc['holdout']['hit_pct']}% · freeze {best_acc['freeze']['n']}@{best_acc['freeze']['hit_pct']}% · strong catch {best_acc['holdout_strong_catch_pct']}%")
        lines.append(f"- params: `{json.dumps(best_acc['params'])}`")
    if best and best["pass"]:
        lines += ["", "## Pass gate", "", f"- `{best['gate']}`"]
    else:
        lines += ["", "## Pass gate", "", "- none met freeze≥85% & holdout≥80% with n floors — pick best_accuracy with caution."]
    lines += ["", f"JSON: `{OUT_JSON}`", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT_MD)
    if best_acc:
        print("BEST_ACC", best_acc["gate"], best_acc["holdout"], "catch", best_acc["holdout_strong_catch_pct"])


if __name__ == "__main__":
    main()
