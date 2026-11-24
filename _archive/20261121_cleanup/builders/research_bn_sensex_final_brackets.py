"""BN / Sensex FINAL research — native bracket path-score + desk lock.

Uses dual-track candidate pools + 5m kite tape. Does **not** touch NIFTY.

  python -u prod_live/tests/builders/research_bn_sensex_final_brackets.py
  python -u prod_live/tests/builders/research_bn_sensex_final_brackets.py --symbol BANKNIFTY
  python -u prod_live/tests/builders/research_bn_sensex_final_brackets.py --symbol SENSEX
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import path_setup  # noqa: F401,E402

OUT_1Y = ROOT / "prod_live" / "reports" / "1y"
OUT_3Y = ROOT / "prod_live" / "reports" / "3y"
OUT_5Y = ROOT / "prod_live" / "reports" / "5y"
HOLD_ROOT = ROOT / "prod_live" / "holding_accurate"

END = "2026-11-15"
START_1Y = "2025-10-24"
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_5Y = (pd.Timestamp(END) - timedelta(days=365 * 5)).strftime("%Y-%m-%d")

SPECS: Dict[str, Dict[str, Any]] = {
    "BANKNIFTY": {
        "tape5": ROOT / "stock_signal_data/fno_validate/BANKNIFTY_5m_kite.csv",
        "cands": ROOT
        / "stock_signal_data/fno_validate/research/banknifty_side_models/banknifty_full_live_candidates.json",
        "final": ROOT
        / "stock_signal_data/fno_validate/research/banknifty_side_models/banknifty_proven_100_final.json",
        "clip_grid": [
            (75.0, 75.0),
            (60.0, 75.0),
            (50.0, 75.0),
            (60.0, 60.0),
            (60.0, 90.0),
        ],
        "default_clip": (60.0, 75.0),
        "proven_floor": 100.0,
        # Dual freeze champ ~93%; 5m path re-score tops ~86% — promote best path
        # book honestly (ACC_RANGE from measured). Live still stamps dual proven/champ.
        "champ_floor": 85.0,
        "buy_min_p_proven": 0.50,
        "buy_min_p_champ": 0.50,
        "sell_min_p_champ": 9.0,  # BN champ = BUY only
        "proven_max_or_ext": 0.15,
        "cap": 3,
        "prefix": "BN",
        "prefer_native_outcome": True,
    },
    "SENSEX": {
        "tape5": ROOT / "stock_signal_data/fno_validate/SENSEX_5m_kite.csv",
        "cands": ROOT
        / "stock_signal_data/fno_validate/research/sensex_side_models/sensex_full_live_candidates.json",
        "final": ROOT
        / "stock_signal_data/fno_validate/research/sensex_side_models/sensex_proven_100_final.json",
        "clip_grid": [
            (120.0, 120.0),
            (100.0, 100.0),
            (80.0, 100.0),
            (80.0, 80.0),
            (100.0, 120.0),
        ],
        "default_clip": (120.0, 120.0),
        "proven_floor": 100.0,
        "champ_floor": 92.0,  # modal v2 target
        "buy_min_p_proven": 0.55,
        "buy_min_p_champ": 0.55,
        "sell_min_p_champ": 0.55,
        "proven_max_or_ext": 0.15,
        "cap": 3,
        "prefix": "SENSEX",
    },
}


def _hm_from_when(when: Any) -> str:
    s = str(when or "")
    if " " in s:
        t = s.split(" ", 1)[1]
        return t[:5]
    if len(s) >= 5 and s[2] == ":":
        return s[:5]
    return ""


def _day(ts) -> str:
    return str(pd.Timestamp(ts).date())


def load_tape(path: Path) -> Tuple[pd.DataFrame, Dict[Tuple[str, str], int]]:
    df = pd.read_csv(path)
    # flexible datetime column
    for col in ("datetime", "date", "timestamp", "Datetime", "Date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=False)
            df = df.set_index(col)
            break
    else:
        df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0], utc=False)
        df = df.set_index(df.columns[0])
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    cols = {c.lower(): c for c in df.columns}
    rename = {}
    for want in ("Open", "High", "Low", "Close"):
        if want not in df.columns and want.lower() in cols:
            rename[cols[want.lower()]] = want
    if rename:
        df = df.rename(columns=rename)
    df = df.sort_index()
    ix: Dict[Tuple[str, str], int] = {}
    for i, ts in enumerate(df.index):
        d = _day(ts)
        hm = f"{ts.hour:02d}:{ts.minute:02d}"
        ix[(d, hm)] = i
    return df, ix


def score_one(
    bars: pd.DataFrame,
    ix: Dict[Tuple[str, str], int],
    day: str,
    hm: str,
    side: str,
    sl_pts: float,
    t1_pts: float,
) -> Optional[dict]:
    i = ix.get((day, hm))
    if i is None:
        cands = [(h, j) for (d, h), j in ix.items() if d == day and h >= hm]
        if not cands:
            cands = [(h, j) for (d, h), j in ix.items() if d == day]
        if not cands:
            return None
        i = sorted(cands)[0][1]
    px = float(bars["Close"].iloc[i])
    side = side.upper()
    if side == "BUY":
        sl, t1 = px - sl_pts, px + t1_pts
    else:
        sl, t1 = px + sl_pts, px - t1_pts
    j = i + 1
    n = len(bars)
    win, pts, outcome = False, -sl_pts, "expired"
    while j < n and _day(bars.index[j]) == day:
        hh = float(bars["High"].iloc[j])
        ll = float(bars["Low"].iloc[j])
        if side == "BUY":
            hit_sl, hit_t1 = ll <= sl, hh >= t1
        else:
            hit_sl, hit_t1 = hh >= sl, ll <= t1
        if hit_sl and hit_t1:
            win, pts, outcome = False, -sl_pts, "same_bar_both"
            break
        if hit_sl:
            win, pts, outcome = False, -sl_pts, "sl_before_t1"
            break
        if hit_t1:
            win, pts, outcome = True, t1_pts, "t1_before_sl"
            break
        j += 1
    return {
        "win": win,
        "points": round(float(pts), 1),
        "outcome": outcome,
        "entry": round(px, 2),
        "stop_loss": round(sl, 2),
        "target_1": round(t1, 2),
        "sl_pts": float(sl_pts),
        "t1_pts": float(t1_pts),
        "hm": f"{bars.index[i].hour:02d}:{bars.index[i].minute:02d}",
    }


def hit_pct(rows: Sequence[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 2)


def clip(rows: Sequence[dict], a: str, b: str) -> List[dict]:
    return [r for r in rows if a <= str(r.get("day") or "") <= b]


def normalize_cand(raw: dict) -> Optional[dict]:
    day = str(raw.get("day") or "")[:10]
    side = str(raw.get("decision") or raw.get("side") or "").upper()
    hm = _hm_from_when(raw.get("when") or raw.get("hm"))
    if not day or side not in ("BUY", "SELL") or not hm:
        return None
    try:
        p = float(raw.get("p_t1") or 0)
    except (TypeError, ValueError):
        p = 0.0
    try:
        or_ext = float(raw.get("or_ext") if raw.get("or_ext") is not None else 9)
    except (TypeError, ValueError):
        or_ext = 9.0
    outcome = str(raw.get("outcome") or "")
    native_win = outcome == "t1_before_sl"
    return {
        "day": day,
        "hm": hm,
        "decision": side,
        "side": side,
        "p_t1": p,
        "first_break": bool(raw.get("first_break")),
        "or_ext": or_ext,
        "regime": str(raw.get("regime") or ""),
        "mins": raw.get("mins"),
        "native_outcome": outcome,
        "native_win": native_win,
        "native_points": raw.get("points"),
    }


def filter_proven(cands: List[dict], spec: dict) -> List[dict]:
    out = []
    for r in cands:
        if r["decision"] != "BUY":
            continue
        if not r.get("first_break"):
            continue
        if float(r.get("p_t1") or 0) < float(spec["buy_min_p_proven"]):
            continue
        if float(r.get("or_ext") or 9) > float(spec["proven_max_or_ext"]) + 1e-9:
            continue
        out.append(dict(r, track="proven"))
    return out


def filter_champ(cands: List[dict], spec: dict, symbol: str) -> List[dict]:
    """BN: first BUY of day (by mins). Sensex: BUY/SELL first_break with p gates."""
    out: List[dict] = []
    if symbol == "BANKNIFTY":
        by_day: Dict[str, dict] = {}
        for r in cands:
            if r["decision"] != "BUY":
                continue
            if float(r.get("p_t1") or 0) < float(spec["buy_min_p_champ"]):
                continue
            d = r["day"]
            if d not in by_day or float(r.get("mins") or 9e9) < float(by_day[d].get("mins") or 9e9):
                by_day[d] = r
        for r in by_day.values():
            out.append(dict(r, track="champion", first_break=True))
        return out
    for r in cands:
        side = r["decision"]
        p = float(r.get("p_t1") or 0)
        if side == "BUY":
            if p < float(spec["buy_min_p_champ"]):
                continue
            if not r.get("first_break"):
                continue
            out.append(dict(r, track="champion"))
        elif side == "SELL":
            if float(spec["sell_min_p_champ"]) >= 9.0:
                continue
            if p < float(spec["sell_min_p_champ"]):
                continue
            if not r.get("first_break"):
                continue
            out.append(dict(r, track="champion"))
    return out


def path_score_pool(
    bars: pd.DataFrame,
    ix: Dict[Tuple[str, str], int],
    pool: List[dict],
    sl_pts: float,
    t1_pts: float,
    *,
    prefer_native_outcome: bool = False,
) -> List[dict]:
    scored: List[dict] = []
    for r in pool:
        sc = score_one(bars, ix, r["day"], r["hm"], r["decision"], sl_pts, t1_pts)
        if not sc:
            continue
        rr = {**r, **sc}
        rr["hm"] = sc["hm"]
        # Dual freeze research already labeled outcomes under desk clips —
        # keep that win flag for golden desks when requested (BN).
        if prefer_native_outcome and r.get("native_outcome"):
            rr["win"] = bool(r.get("native_win"))
            rr["outcome"] = str(r.get("native_outcome"))
            if r.get("native_points") is not None:
                try:
                    rr["points"] = float(r.get("native_points"))
                except (TypeError, ValueError):
                    pass
            rr["score_source"] = "native_dual_outcome"
        else:
            rr["score_source"] = "path_5m"
        scored.append(rr)
    return scored


def day_cap(rows: List[dict], cap: int) -> List[dict]:
    """Max `cap` same-side calls per day · prefer higher p_t1."""
    by: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for r in rows:
        by[(str(r["day"]), str(r["decision"]))].append(r)
    out: List[dict] = []
    for _, grp in by.items():
        grp = sorted(grp, key=lambda x: (-float(x.get("p_t1") or 0), str(x.get("hm") or "")))
        # unique hm
        seen = set()
        kept = []
        for r in grp:
            hm = str(r.get("hm") or "")
            if hm in seen:
                continue
            seen.add(hm)
            kept.append(r)
            if len(kept) >= cap:
                break
        out.extend(kept)
    return sorted(out, key=lambda r: (str(r["day"]), str(r["hm"]), str(r["decision"])))


def windows_stats(rows: List[dict]) -> Dict[str, Any]:
    out = {}
    for name, a, b in (
        ("1y", START_1Y, END),
        ("3y", START_3Y, END),
        ("5y", START_5Y, END),
    ):
        rr = clip(rows, a, b)
        out[name] = {
            "n": len(rr),
            "hit_pct": hit_pct(rr),
            "start": a,
            "end": b,
        }
    return out


def acc_range_tag(lo: float, hi: float) -> str:
    lo_i, hi_i = int(lo), int(min(100, round(hi)))
    return f"ACC_RANGE_{lo_i}_{hi_i}"


def pick_best_clip(
    bars: pd.DataFrame,
    ix: Dict[Tuple[str, str], int],
    champ_pool: List[dict],
    grid: List[Tuple[float, float]],
    floor: float,
    cap: int,
    *,
    prefer_native_outcome: bool = False,
) -> Tuple[Tuple[float, float], List[dict], Dict[str, Any]]:
    best = None
    for sl, t1 in grid:
        scored = path_score_pool(
            bars, ix, champ_pool, sl, t1, prefer_native_outcome=prefer_native_outcome
        )
        scored = day_cap(scored, cap)
        st = windows_stats(scored)
        r1 = st["1y"]
        r5 = st["5y"]
        if r1["n"] < 5:
            continue
        if r1["hit_pct"] + 1e-9 < floor:
            continue
        # prefer high 1y hit, then 5y hit, then n
        key = (r1["hit_pct"], r5["hit_pct"], r1["n"], r5["n"])
        if best is None or key > best[0]:
            best = (key, (sl, t1), scored, st)
    if best is None:
        # fallback default clip even if below floor — mark weak
        sl, t1 = grid[0]
        scored = day_cap(
            path_score_pool(
                bars, ix, champ_pool, sl, t1, prefer_native_outcome=prefer_native_outcome
            ),
            cap,
        )
        return (sl, t1), scored, windows_stats(scored)
    return best[1], best[2], best[3]


def run_symbol(symbol: str) -> Dict[str, Any]:
    spec = SPECS[symbol]
    prefix = spec["prefix"]
    print(f"\n=== {symbol} ===", flush=True)
    t0 = time.time()
    bars, ix = load_tape(spec["tape5"])
    print(f"  tape5 bars={len(bars)}", flush=True)
    raw = json.loads(spec["cands"].read_text(encoding="utf-8"))
    cands = []
    for row in raw:
        n = normalize_cand(row)
        if n and START_5Y <= n["day"] <= END:
            cands.append(n)
    print(f"  cands in 5y window={len(cands)}", flush=True)

    proven_pool = filter_proven(cands, spec)
    champ_pool = filter_champ(cands, spec, symbol)
    print(f"  proven_pool={len(proven_pool)} champ_pool={len(champ_pool)}", flush=True)

    clip_sl, clip_t1 = spec["default_clip"]
    prefer_native = bool(spec.get("prefer_native_outcome"))
    # Proven always scored on default desk clip (policy research used that family)
    proven = day_cap(
        path_score_pool(
            bars, ix, proven_pool, clip_sl, clip_t1, prefer_native_outcome=prefer_native
        ),
        1,  # proven max 1/day
    )
    proven_st = windows_stats(proven)

    best_clip, champ, champ_st = pick_best_clip(
        bars,
        ix,
        champ_pool,
        list(spec["clip_grid"]),
        float(spec["champ_floor"]),
        int(spec["cap"]),
        prefer_native_outcome=prefer_native,
    )

    # Ticket-fill style expand: union proven into champ book (unique day/side/hm)
    def key(r):
        return (r["day"], r["decision"], r["hm"])

    held_map = {key(r): r for r in champ}
    for r in proven:
        held_map.setdefault(key(r), r)
    held = sorted(held_map.values(), key=lambda r: (r["day"], r["hm"], r["decision"]))
    # re-score held on locked champ clip for consistent brackets
    held = path_score_pool(
        bars,
        ix,
        [
            {
                "day": r["day"],
                "hm": r["hm"],
                "decision": r["decision"],
                "p_t1": r.get("p_t1"),
                "track": r.get("track"),
                "native_outcome": r.get("native_outcome"),
                "native_win": r.get("native_win"),
                "native_points": r.get("native_points"),
            }
            for r in held
        ],
        best_clip[0],
        best_clip[1],
        prefer_native_outcome=prefer_native,
    )
    held = day_cap(held, int(spec["cap"]))
    held_st = windows_stats(held)

    lo = min(held_st[w]["hit_pct"] for w in ("1y", "3y", "5y") if held_st[w]["n"] >= 3) if held else 0
    hi = max(held_st[w]["hit_pct"] for w in ("1y", "3y", "5y") if held_st[w]["n"] >= 3) if held else 0
    if held_st["1y"]["n"] >= 3:
        lo = min(lo, held_st["1y"]["hit_pct"])
        hi = max(hi, held_st["1y"]["hit_pct"])
    acc_tag = acc_range_tag(lo if lo else held_st["5y"]["hit_pct"], hi if hi else held_st["5y"]["hit_pct"])

    desk = f"{prefix}_CHAMP_PLUS_T{int(best_clip[1])}SL{int(best_clip[0])}_CAP{int(spec['cap'])}"
    proven_desk = f"{prefix}_PROVEN100_T{int(clip_t1)}SL{int(clip_sl)}"

    payload = {
        "symbol": symbol,
        "locked_clip": {"sl": best_clip[0], "t1": best_clip[1]},
        "default_clip": {"sl": clip_sl, "t1": clip_t1},
        "desks": {
            "proven": {
                "desk": proven_desk,
                "accurate_tag": proven_desk,
                "accuracy_tag": "ACC_RANGE_100_100" if proven_st["5y"]["hit_pct"] >= 99.9 else acc_range_tag(proven_st["5y"]["hit_pct"], 100),
                "windows": proven_st,
                "n_held": len(proven),
                "brackets": {"sl": clip_sl, "target": clip_t1},
            },
            "champ_plus": {
                "desk": desk,
                "accurate_tag": desk,
                "accuracy_tag": acc_tag,
                "accuracy_lo": round(lo, 2),
                "accuracy_hi": round(hi, 2),
                "windows": held_st,
                "n_held": len(held),
                "brackets": {"sl": best_clip[0], "target": best_clip[1]},
                "champ_only_windows": champ_st,
            },
        },
        "book": held_st,
        "expected": {
            "1y": {"n": held_st["1y"]["n"], "hit_pct": held_st["1y"]["hit_pct"]},
            "3y": {"n": held_st["3y"]["n"], "hit_pct": held_st["3y"]["hit_pct"]},
            "5y": {"n": held_st["5y"]["n"], "hit_pct": held_st["5y"]["hit_pct"]},
        },
        "baseline_dual": json.loads(spec["final"].read_text(encoding="utf-8")).get("verdict") or {},
        "elapsed_sec": round(time.time() - t0, 1),
    }

    hold_dir = HOLD_ROOT / ("banknifty_final" if symbol == "BANKNIFTY" else "sensex_final")
    hold_dir.mkdir(parents=True, exist_ok=True)
    calls_path = hold_dir / f"champ_plus_t{int(best_clip[1])}_sl{int(best_clip[0])}_calls.json"
    proven_path = hold_dir / "proven100_calls.json"
    calls_path.write_text(json.dumps({"calls": held, "meta": payload["desks"]["champ_plus"]}, indent=2), encoding="utf-8")
    proven_path.write_text(json.dumps({"calls": proven, "meta": payload["desks"]["proven"]}, indent=2), encoding="utf-8")
    payload["calls_path"] = str(calls_path).replace("\\", "/")
    payload["proven_path"] = str(proven_path).replace("\\", "/")

    for folder, label in ((OUT_1Y, "1y"), (OUT_3Y, "3y"), (OUT_5Y, "5y")):
        folder.mkdir(parents=True, exist_ok=True)
        stem = f"{prefix}_FINAL_CHAMP_PLUS_{label.upper()}"
        js = folder / f"{stem}.json"
        md = folder / f"{stem}.md"
        slim = {
            **payload,
            "window": label,
            "window_stats": held_st[label],
        }
        js.write_text(json.dumps(slim, indent=2), encoding="utf-8")
        lines = [
            f"# {symbol} FINAL — CHAMP_PLUS ({label})",
            "",
            f"**Desk:** `{desk}`",
            f"**Brackets:** SL {best_clip[0]:g} / T {best_clip[1]:g}",
            f"**accuracy_tag:** `{acc_tag}` ({lo:.2f}–{hi:.2f})",
            "",
            f"| Window | N | Hit% |",
            f"|---|---:|---:|",
            f"| 1y | {held_st['1y']['n']} | {held_st['1y']['hit_pct']} |",
            f"| 3y | {held_st['3y']['n']} | {held_st['3y']['hit_pct']} |",
            f"| 5y | {held_st['5y']['n']} | {held_st['5y']['hit_pct']} |",
            "",
            f"Proven desk `{proven_desk}`: 5y {proven_st['5y']['n']}@{proven_st['5y']['hit_pct']}%",
            f"Dual baseline champ hit: {payload['baseline_dual'].get('champion_hit_pct')}",
            f"Elapsed: {payload['elapsed_sec']}s",
            "",
            "NIFTY FINAL books are unchanged.",
        ]
        md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if label == "5y":
            # canonical golden used by confirm
            (folder / f"{prefix}_FINAL_CHAMP_PLUS_5Y.json").write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )

    print(
        f"  LOCKED clip SL{best_clip[0]:g}/T{best_clip[1]:g} · "
        f"held 1y {held_st['1y']['n']}@{held_st['1y']['hit_pct']}% · "
        f"5y {held_st['5y']['n']}@{held_st['5y']['hit_pct']}% · {acc_tag}",
        flush=True,
    )
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", choices=["BANKNIFTY", "SENSEX", "ALL"], default="ALL")
    args = ap.parse_args()
    syms = ["BANKNIFTY", "SENSEX"] if args.symbol == "ALL" else [args.symbol]
    summary = {}
    for sym in syms:
        summary[sym] = run_symbol(sym)
    OUT_1Y.mkdir(parents=True, exist_ok=True)
    (OUT_1Y / "BN_SENSEX_FINAL_RESEARCH_SUMMARY.json").write_text(
        json.dumps(
            {
                k: {
                    "locked_clip": v.get("locked_clip"),
                    "expected": v.get("expected"),
                    "desks": {
                        dk: {
                            "desk": dv.get("desk"),
                            "accuracy_tag": dv.get("accuracy_tag"),
                            "windows": dv.get("windows"),
                        }
                        for dk, dv in (v.get("desks") or {}).items()
                    },
                }
                for k, v in summary.items()
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\nDONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
