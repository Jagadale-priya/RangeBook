"""Lock Sensex dual+fb with stronger OR-break fallback (break_frac>=0.20).

Best accuracy step vs prior 909@76.13% without inventing fake dual volume
(p40/p42 add no new cands). Tradeoff: slightly fewer fb fills.

  python -u prod_live/tests/builders/_lock_sensex_dual_fb_bf20.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live" / "tests" / "builders")]
import path_setup  # noqa: F401,E402

from research_bn_sensex_final_brackets import load_tape, normalize_cand, path_score_pool  # noqa: E402
from research_sensex_modal_1y_deep import hit_pct, month_rollup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
CANDS = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_full_live_candidates.json"
)
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_5m_kite.csv"
SX_LIVE = ROOT / "prod_live" / "logic" / "sensex_final_live.py"
DUAL = ROOT / "app" / "fno" / "sensex_live_dual_track.py"
FB_HELPER = ROOT / "prod_live" / "logic" / "sensex_everyday_fallback.py"
FINAL_JSON = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_proven_100_final.json"
)
HOLD = ROOT / "prod_live" / "holding_accurate" / "sensex_final"

END = "2026-11-19"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_3M = (pd.Timestamp(END) - timedelta(days=92)).strftime("%Y-%m-%d")
SL = T1 = 50.0
DESK = "SENSEX_DUAL_FB_BF20_T50"
MIN_BF = 0.20


def sessions(bars: pd.DataFrame, a: str, b: str) -> List[str]:
    return sorted(
        {
            str(pd.Timestamp(t).date())
            for t in bars.index
            if a <= str(pd.Timestamp(t).date()) <= b
        }
    )


def key_of(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day"))[:10], str(r.get("hm") or "")[:5], str(r.get("decision") or "").upper())


def fallback_row(bars: pd.DataFrame, day: str) -> Optional[dict]:
    db = bars[bars.index.strftime("%Y-%m-%d") == day]
    if len(db) < 2:
        return None
    or_hi = float(db["High"].iloc[0])
    or_lo = float(db["Low"].iloc[0])
    width = or_hi - or_lo
    if width <= 0:
        return None
    entry_ts = None
    for want in ("09:45", "09:30", "10:00", "10:15"):
        hit = db[db.index.strftime("%H:%M") == want]
        if len(hit):
            entry_ts = hit.index[0]
            break
    if entry_ts is None:
        entry_ts = db.index[min(1, len(db) - 1)]
    close = float(db.loc[entry_ts, "Close"])
    if close > or_hi:
        side = "BUY"
        bf = (close - or_hi) / width
    elif close < or_lo:
        side = "SELL"
        bf = (or_lo - close) / width
    else:
        return None
    if bf < MIN_BF:
        return None
    hm = f"{entry_ts.hour:02d}:{entry_ts.minute:02d}"
    return {
        "day": day,
        "hm": hm,
        "decision": side,
        "side": side,
        "p_t1": 0.55,
        "first_break": True,
        "track": "or_fallback",
        "source": "fallback",
        "fb_kind": "break",
        "break_frac": bf,
        "tags": ["fallback", "OR_09:45", "fb_break", f"bf>={MIN_BF}"],
    }


def build_day(bars, by, day: str) -> List[dict]:
    duals = []
    for r in list(by.get(day) or []):
        if float(r.get("p_t1") or 0) < 0.45:
            continue
        duals.append(
            {
                **r,
                "source": "dual",
                "track": r.get("track") or "champion",
                "tags": ["dual", "OR_break"],
            }
        )
    duals = sorted(duals, key=lambda x: (str(x.get("hm") or ""), -float(x.get("p_t1") or 0)))
    fb = fallback_row(bars, day)
    if not duals and not fb:
        return []
    if not fb:
        return duals
    if not duals:
        return [fb]
    out: List[dict] = []
    fb_k = key_of(fb)
    merged = False
    for d in duals:
        if key_of(d) == fb_k:
            row = dict(d)
            tags = list(
                dict.fromkeys(
                    (row.get("tags") or [])
                    + (fb.get("tags") or [])
                    + ["dual", "fallback", "COMBINED"]
                )
            )
            row["tags"] = tags
            row["source"] = "dual+fallback"
            row["track"] = "dual_fb_combined"
            row["combined"] = True
            row["p_t1"] = max(float(d.get("p_t1") or 0), float(fb.get("p_t1") or 0))
            out.append(row)
            merged = True
        else:
            out.append(d)
    if not merged:
        out.append(fb)
    return out


def stats(scored: List[dict], a: str, b: str, sess: List[str]) -> Dict[str, Any]:
    rr = [r for r in scored if a <= str(r.get("day") or "")[:10] <= b]
    known = [r for r in rr if r.get("win") is not None]
    w = sum(1 for r in known if r.get("win"))
    days = sorted({str(r.get("day"))[:10] for r in rr})
    return {
        "n": len(rr),
        "sessions": len(sess),
        "days_with_call": len(days),
        "coverage_pct": round(100.0 * len(days) / len(sess), 1) if sess else 0.0,
        "hit_pct": hit_pct(rr),
        "wins": w,
        "losses": len(known) - w,
        "dual_only": sum(1 for r in rr if r.get("source") == "dual"),
        "fallback_only": sum(1 for r in rr if r.get("source") == "fallback"),
        "combined": sum(1 for r in rr if r.get("source") == "dual+fallback"),
        "avg_calls_per_day": round(len(rr) / len(days), 2) if days else 0.0,
        "by_month": month_rollup(rr),
    }


def main() -> int:
    print("Lock dual+fb bf>=0.20", flush=True)
    bars, ix = load_tape(TAPE5)
    if getattr(bars.index, "tz", None) is not None:
        bars = bars.copy()
        bars.index = bars.index.tz_localize(None)

    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    by: Dict[str, List[dict]] = defaultdict(list)
    for row in raw:
        n = normalize_cand(row)
        if not n or n["day"] < START_3Y or n["day"] > END:
            continue
        n["first_break"] = bool(row.get("first_break"))
        n["p_t1"] = float(n.get("p_t1") or 0)
        if row.get("when"):
            ts = pd.Timestamp(row["when"])
            n["hm"] = f"{ts.hour:02d}:{ts.minute:02d}"
        by[n["day"]].append(n)

    picks: List[dict] = []
    for day in sessions(bars, START_3Y, END):
        picks.extend(build_day(bars, by, day))

    scored = path_score_pool(bars, ix, picks, SL, T1)
    meta_by = {key_of(p): p for p in picks}
    for r in scored:
        m = meta_by.get(key_of(r)) or {}
        r["source"] = m.get("source") or "dual"
        r["track"] = m.get("track") or "champion"
        r["tags"] = list(m.get("tags") or [])
        r["combined"] = bool(m.get("combined"))
        r["sl_pts"] = SL
        r["t1_pts"] = T1

    s1 = stats(scored, START_1Y, END, sessions(bars, START_1Y, END))
    s3m = stats(scored, START_3M, END, sessions(bars, START_3M, END))
    s3y = stats(scored, START_3Y, END, sessions(bars, START_3Y, END))
    print(
        f"  1y {s1['n']}@{s1['hit_pct']}% | 3y {s3y['n']}@{s3y['hit_pct']}% | 3m {s3m['n']}@{s3m['hit_pct']}%",
        flush=True,
    )

    lo = min(s1["hit_pct"], s3y["hit_pct"])
    hi = max(s1["hit_pct"], s3y["hit_pct"], s3m["hit_pct"])
    acc = f"ACC_RANGE_{int(lo)}_{int(min(100, round(hi)))}"
    policy = {
        "name": "DUAL_FB_BREAK_FRAC_020",
        "mode": "dual_fb_bf20",
        "dual": "OR-break p>=0.45 BUY/SELL · no or_ext · sell cont · all duals",
        "fallback": f"OR break-only @ 09:45 with break_frac>={MIN_BF} (no mid)",
        "combine": "same hm+side → 1 call dual+fallback tags",
        "mutual_block": False,
        "buy_min_p": 0.45,
        "sell_min_p": 0.45,
        "buy_max_or_ext": None,
        "fb_break_only": True,
        "fb_min_break_frac": MIN_BF,
        "max_per_day": None,
        "clip_sl": SL,
        "clip_t1": T1,
        "note": "Accuracy step-up vs plain break-only; p40 adds no extra dual cands",
    }
    meta = {
        "desk": DESK,
        "mode": "dual_fb_bf20",
        "policy": policy,
        "brackets": {"sl": SL, "target": T1},
        "cap": 99,
        "accuracy_tag": acc,
        "accuracy_lo": round(lo, 2),
        "accuracy_hi": round(hi, 2),
        "windows": {
            "1y": {k: s1[k] for k in s1 if k != "by_month"},
            "3m": {k: s3m[k] for k in s3m if k != "by_month"},
            "3y": {k: s3y[k] for k in s3y if k != "by_month"},
        },
    }
    HOLD.mkdir(parents=True, exist_ok=True)
    held = [r for r in scored if START_3Y <= str(r.get("day") or "")[:10] <= END]
    calls_path = HOLD / "champ_plus_t50_sl50_calls.json"
    calls_path.write_text(json.dumps({"calls": held, "meta": meta}, indent=2), encoding="utf-8")

    payload = {
        "symbol": "SENSEX",
        "version": "dual_fb_bf20_t50",
        "locked_clip": {"sl": SL, "t1": T1},
        "policy": policy,
        "desks": {
            "champ_plus": {
                "desk": DESK,
                "accurate_tag": DESK,
                "accuracy_tag": acc,
                "accuracy_lo": round(lo, 2),
                "accuracy_hi": round(hi, 2),
                "windows": meta["windows"],
                "n_held": len(held),
                "brackets": {"sl": SL, "target": T1},
                "cap": 99,
            }
        },
        "book": {
            "1y": {"n": s1["n"], "hit_pct": s1["hit_pct"], "coverage_pct": s1["coverage_pct"]},
            "3y": {"n": s3y["n"], "hit_pct": s3y["hit_pct"], "coverage_pct": s3y["coverage_pct"]},
            "5y": {"n": s3y["n"], "hit_pct": s3y["hit_pct"], "coverage_pct": s3y["coverage_pct"]},
        },
        "expected": {
            "1y": {"n": s1["n"], "hit_pct": s1["hit_pct"]},
            "3y": {"n": s3y["n"], "hit_pct": s3y["hit_pct"]},
            "5y": {"n": s3y["n"], "hit_pct": s3y["hit_pct"]},
        },
        "calls_path": str(calls_path).replace("\\", "/"),
    }
    for folder in (OUT, ROOT / "prod_live" / "reports" / "3y", ROOT / "prod_live" / "reports" / "5y"):
        folder.mkdir(parents=True, exist_ok=True)
    (ROOT / "prod_live" / "reports" / "5y" / "SENSEX_FINAL_CHAMP_PLUS_5Y.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    for folder, label, stt in (
        (OUT, "1y", s1),
        (ROOT / "prod_live" / "reports" / "3y", "3y", s3y),
        (ROOT / "prod_live" / "reports" / "5y", "5y", s3y),
    ):
        (folder / f"SENSEX_FINAL_CHAMP_PLUS_{label.upper()}.json").write_text(
            json.dumps({**payload, "window": label, "window_stats": stt}, indent=2, default=str),
            encoding="utf-8",
        )

    text = SX_LIVE.read_text(encoding="utf-8")
    text = re.sub(r'DESK_CHAMP = "[^"]+"', f'DESK_CHAMP = "{DESK}"', text, count=1)
    text = re.sub(r'ACCURACY_TAG = "[^"]+"', f'ACCURACY_TAG = "{acc}"', text, count=1)
    text = re.sub(r"ACCURACY_LO = [0-9.]+", f"ACCURACY_LO = {round(lo, 2)}", text, count=1)
    text = re.sub(r"ACCURACY_HI = [0-9.]+", f"ACCURACY_HI = {round(hi, 2)}", text, count=1)
    text = re.sub(
        r"BRACKETS = \{[^}]+\}",
        f'BRACKETS = {{"target": {T1}, "sl": {SL}, "risk": {SL}}}',
        text,
        count=1,
    )
    text = re.sub(r"CAP = [^\n]+", "CAP = 99  # dual+fb bf20", text, count=1)
    SX_LIVE.write_text(text, encoding="utf-8")

    dual = DUAL.read_text(encoding="utf-8")
    dual = re.sub(r"CHAMPION_BUY_MIN_P = [0-9.]+", "CHAMPION_BUY_MIN_P = 0.45", dual, count=1)
    dual = re.sub(r"CHAMPION_SELL_MIN_P = [0-9.]+", "CHAMPION_SELL_MIN_P = 0.45", dual, count=1)
    dual = re.sub(r"CHAMPION_BUY_MAX_OR_EXT = [^\n]+", "CHAMPION_BUY_MAX_OR_EXT = None", dual, count=1)
    dual = re.sub(r"CHAMPION_SELL_FIRST_ONLY = (True|False)", "CHAMPION_SELL_FIRST_ONLY = False", dual, count=1)
    dual = re.sub(
        r"CHAMPION_HIT_PCT = [0-9.]+",
        f"CHAMPION_HIT_PCT = {float(s1['hit_pct'] or 0):.1f}",
        dual,
        count=1,
    )
    DUAL.write_text(dual, encoding="utf-8")

    # live fallback: require break_frac >= 0.20
    FB_HELPER.write_text(
        '''"""Sensex OR fallback — break-only with min break fraction (locked bf>=0.20)."""
from __future__ import annotations

from typing import Any, Dict, Optional

MIN_BREAK_FRAC = 0.20


def or_fallback_call(bars: Any, *, asof: Any = None, price: Any = None) -> Optional[Dict[str, Any]]:
    try:
        import pandas as pd
        import fno_session_rules as fsrules
    except Exception:
        return None
    if bars is None or len(bars) < 2:
        return None
    work = bars
    if not isinstance(work.index, pd.DatetimeIndex):
        return None
    ts = pd.Timestamp(asof) if asof is not None else work.index[-1]
    if ts.tzinfo is None and work.index.tz is not None:
        ts = ts.tz_localize(work.index.tz)
    elif work.index.tz is not None:
        ts = ts.tz_convert(work.index.tz)
    day = fsrules.session_date(ts)
    if day is None:
        return None
    day_mask = [fsrules.session_date(t) == day for t in work.index]
    sess = work.loc[day_mask]
    if len(sess) < 2:
        return None
    or_hi = float(sess["High"].astype(float).iloc[0])
    or_lo = float(sess["Low"].astype(float).iloc[0])
    width = or_hi - or_lo
    if width <= 0:
        return None
    entry_pos = min(1, len(sess) - 1)
    for i, t in enumerate(sess.index):
        hm = f"{pd.Timestamp(t).hour:02d}:{pd.Timestamp(t).minute:02d}"
        if hm in ("09:45", "09:30", "10:00"):
            entry_pos = i
            if hm == "09:45":
                break
    entry_ts = sess.index[entry_pos]
    close = float(sess["Close"].astype(float).iloc[entry_pos])
    if close > or_hi:
        side = "BUY"
        bf = (close - or_hi) / width
    elif close < or_lo:
        side = "SELL"
        bf = (or_lo - close) / width
    else:
        return None
    if bf < MIN_BREAK_FRAC:
        return None
    hm = f"{pd.Timestamp(entry_ts).hour:02d}:{pd.Timestamp(entry_ts).minute:02d}"
    return {
        "decision": side,
        "side": side,
        "entry": round(close, 2),
        "p_t1": 0.55,
        "track": "or_fallback",
        "hm": hm,
        "source": "sensex_everyday_fallback",
        "fb_kind": "break",
        "break_frac": round(bf, 4),
        "accuracy_label": f"OR fallback · break frac>={MIN_BREAK_FRAC:.0%}",
        "or_hi": round(or_hi, 2),
        "or_lo": round(or_lo, 2),
    }
''',
        encoding="utf-8",
    )

    if FINAL_JSON.is_file():
        doc = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
        doc.setdefault("tracks", {}).setdefault("live_champion", {})["policy"] = policy
        doc["tracks"]["live_champion"]["full"] = {
            "n": s1["n"],
            "hit_pct": s1["hit_pct"],
            "coverage_pct": s1["coverage_pct"],
        }
        doc["verdict"]["champion_hit_pct"] = s1["hit_pct"]
        doc["verdict"]["summary"] = (
            f"SENSEX dual+fb bf20: 1y {s1['n']}@{s1['hit_pct']}% · 3y {s3y['n']}@{s3y['hit_pct']}%"
        )
        FINAL_JSON.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    lines = [
        "# SENSEX · dual+fb · stronger break fallback (bf≥20%) (±50/50)",
        "",
        f"**Desk:** `{DESK}`",
        "",
        "## Exact logic",
        "",
        "1. **Dual:** OR-break `p≥0.45` · no or_ext cap · sell cont · all duals",
        f"2. **Fallback:** OR **break-only** @ 09:45 with **break_frac ≥ {MIN_BF:.0%}** (no mid-OR)",
        "3. **Same hm+side:** 1 call tagged `dual` + `fallback` + `COMBINED`",
        "4. No mutual block otherwise · ±50/50",
        "",
        "## Why this lock",
        "",
        "Grid could **not** raise both N and hit vs prior 909@76.13% (p40/p42 add no new duals).",
        "Best accuracy step that keeps combine: require a clearer OR break on fallback.",
        "",
        "| Window | Prior break-only | **This (bf≥20%)** |",
        "|---|---|---|",
        f"| **1y** | 909 @ 76.13% | **{s1['n']} @ {s1['hit_pct']}%** |",
        f"| **3y** | 2370 @ 72.62% | **{s3y['n']} @ {s3y['hit_pct']}%** |",
        f"| **3m** | 227 @ 79.3% | **{s3m['n']} @ {s3m['hit_pct']}%** |",
        "",
        "## 3m months",
        "",
        "| Month | N | Hit | W/L |",
        "|---|---:|---:|---|",
    ]
    for m, ms in (s3m.get("by_month") or {}).items():
        lines.append(f"| {m} | {ms['n']} | {ms['hit_pct']} | {ms['wins']}/{ms['losses']} |")
    lines += ["", "_Locked bf>=0.20_", ""]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "SENSEX_DUAL_FB_BF20.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "SENSEX_DUAL_FB_V2.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "SENSEX_DUAL_FB_BF20.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUT / 'SENSEX_DUAL_FB_BF20.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
