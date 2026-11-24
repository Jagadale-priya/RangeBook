"""Download SENSEX 5m from 2018 if needed, test locked dual+fb bf>=20% on 2018-2020.

  python -u prod_live/tests/builders/_download_sensex_5m_2018_2020_test.py
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "market"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
import path_setup  # noqa: F401,E402

from research_bn_sensex_final_brackets import load_tape, normalize_cand, path_score_pool  # noqa: E402
from research_sensex_modal_1y_deep import hit_pct  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
CANDS = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_full_live_candidates.json"
)
TAPE = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_5m_kite.csv"
DL_START = "2018-01-01"
WIN_A, WIN_B = "2018-01-01", "2020-12-31"
SL = T1 = 50.0
MIN_BF = 0.20
DESK = "SENSEX_DUAL_FB_BF20_T50"


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    if getattr(work.index, "tz", None) is not None:
        work.index = work.index.tz_convert("Asia/Kolkata").tz_localize(None)
    rename = {}
    for want in ("Open", "High", "Low", "Close", "Volume"):
        if want not in work.columns:
            for c in work.columns:
                if str(c).lower() == want.lower():
                    rename[c] = want
    if rename:
        work = work.rename(columns=rename)
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in work.columns]
    work = work[cols].sort_index()
    work = work[~work.index.duplicated(keep="last")]
    hm = work.index.strftime("%H:%M")
    work = work[(hm >= "09:15") & (hm <= "15:30")]
    return work


def ensure_tape_from_2018() -> Dict[str, Any]:
    import kite_data

    need_dl = True
    if TAPE.exists():
        try:
            existing = pd.read_csv(TAPE, index_col=0, parse_dates=True)
            existing = _normalize_df(existing)
            mn = str(existing.index.min().date())
            if mn <= "2018-03-01":
                need_dl = False
                print(f"Tape already covers from {mn} — skip download", flush=True)
                return {
                    "skipped": True,
                    "n": len(existing),
                    "min": str(existing.index.min()),
                    "max": str(existing.index.max()),
                    "sessions": int(existing.index.strftime("%Y-%m-%d").nunique()),
                }
            print(f"Tape starts {mn} — extending back to {DL_START}", flush=True)
        except Exception as exc:
            print(f"Could not read existing tape ({exc}) — full re-download", flush=True)

    if not kite_data.kite_enabled():
        raise RuntimeError("Kite not enabled / not configured")

    start = datetime(2018, 1, 1)
    days = max(1, (datetime.now() - start).days + 2)
    print(f"Downloading SENSEX 5m via Kite · days={days} (from ~{DL_START})", flush=True)
    df, err = kite_data.fetch_historical_candles(
        "SENSEX", interval="5minute", days=days, keep_partial=True, strict=False
    )
    if err or df is None or getattr(df, "empty", True):
        raise RuntimeError(f"kite download failed: {err}")

    work = _normalize_df(df)
    work = work[work.index.strftime("%Y-%m-%d") >= DL_START]

    # merge with any existing rows we already have
    if TAPE.exists():
        try:
            old = _normalize_df(pd.read_csv(TAPE, index_col=0, parse_dates=True))
            work = pd.concat([old, work]).sort_index()
            work = work[~work.index.duplicated(keep="last")]
        except Exception:
            pass

    TAPE.parent.mkdir(parents=True, exist_ok=True)
    if TAPE.exists():
        bak = TAPE.with_suffix(TAPE.suffix + f".bak_{int(time.time())}")
        shutil.copy2(TAPE, bak)
        print(f"  backed up old tape → {bak.name}", flush=True)
    out = work.copy()
    out.index.name = "date"
    out.to_csv(TAPE)
    meta = {
        "path": str(TAPE).replace("\\", "/"),
        "n": len(work),
        "min": str(work.index.min()),
        "max": str(work.index.max()),
        "sessions": int(work.index.strftime("%Y-%m-%d").nunique()),
    }
    print(
        f"  saved {meta['n']} bars · {meta['sessions']} sessions · "
        f"{meta['min']} → {meta['max']}",
        flush=True,
    )
    return meta


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


def rollup(rows: List[dict], key_fn) -> Dict[str, Dict[str, Any]]:
    buckets: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        buckets[key_fn(r)].append(r)
    out = {}
    for k in sorted(buckets.keys()):
        rr = buckets[k]
        known = [x for x in rr if x.get("win") is not None]
        w = sum(1 for x in known if x.get("win"))
        out[k] = {
            "n": len(rr),
            "hit_pct": hit_pct(rr),
            "wins": w,
            "losses": len(known) - w,
            "dual_only": sum(1 for x in rr if x.get("source") == "dual"),
            "fallback_only": sum(1 for x in rr if x.get("source") == "fallback"),
            "combined": sum(1 for x in rr if x.get("source") == "dual+fallback"),
            "points": round(sum(float(x.get("points") or 0) for x in known), 1),
        }
    return out


def run_test(bars, ix) -> Dict[str, Any]:
    tape_min = str(pd.Timestamp(bars.index.min()).date())
    tape_max = str(pd.Timestamp(bars.index.max()).date())
    start = max(WIN_A, tape_min)
    end = min(WIN_B, tape_max)
    raw = json.loads(CANDS.read_text(encoding="utf-8"))
    by: Dict[str, List[dict]] = defaultdict(list)
    for row in raw:
        n = normalize_cand(row)
        if not n or n["day"] < start or n["day"] > end:
            continue
        n["first_break"] = bool(row.get("first_break"))
        n["p_t1"] = float(n.get("p_t1") or 0)
        if row.get("when"):
            try:
                ts = pd.Timestamp(row["when"])
                n["hm"] = f"{ts.hour:02d}:{ts.minute:02d}"
            except Exception:
                pass
        by[n["day"]].append(n)

    sess = sessions(bars, start, end)
    picks: List[dict] = []
    for day in sess:
        picks.extend(build_day(bars, by, day))
    print(f"Scoring {len(picks)} picks on {len(sess)} sessions ({start}→{end})", flush=True)
    scored = path_score_pool(bars, ix, picks, SL, T1)
    meta_by = {key_of(p): p for p in picks}
    for r in scored:
        m = meta_by.get(key_of(r)) or {}
        r["source"] = m.get("source") or "dual"
        r["tags"] = list(m.get("tags") or [])
        r["combined"] = bool(m.get("combined"))
        r["sl_pts"] = SL
        r["t1_pts"] = T1

    known = [r for r in scored if r.get("win") is not None]
    w = sum(1 for r in known if r.get("win"))
    overall = {
        "n": len(scored),
        "sessions": len(sess),
        "days_with_call": len({str(r.get("day"))[:10] for r in scored}),
        "hit_pct": hit_pct(scored),
        "wins": w,
        "losses": len(known) - w,
        "dual_only": sum(1 for r in scored if r.get("source") == "dual"),
        "fallback_only": sum(1 for r in scored if r.get("source") == "fallback"),
        "combined": sum(1 for r in scored if r.get("source") == "dual+fallback"),
        "points": round(sum(float(r.get("points") or 0) for r in known), 1),
        "start": start,
        "end": end,
        "tape_min": tape_min,
        "tape_max": tape_max,
    }
    return {
        "overall": overall,
        "by_year": rollup(scored, lambda r: str(r.get("day"))[:4]),
        "by_month": rollup(scored, lambda r: str(r.get("day"))[:7]),
        "scored": scored,
    }


def main() -> int:
    t0 = time.time()
    try:
        dl = ensure_tape_from_2018()
    except Exception as exc:
        print(f"DOWNLOAD FAILED: {exc}", flush=True)
        print("Will still try to test whatever 5m tape is on disk…", flush=True)
        dl = {"error": str(exc)}

    bars, ix = load_tape(TAPE)
    if getattr(bars.index, "tz", None) is not None:
        bars = bars.copy()
        bars.index = bars.index.tz_localize(None)
    print(
        f"Tape on disk: {bars.index.min()} → {bars.index.max()} n={len(bars)}",
        flush=True,
    )

    result = run_test(bars, ix)
    overall = result["overall"]
    by_year = result["by_year"]
    by_month = result["by_month"]
    print(
        f"OVERALL n={overall['n']} hit={overall['hit_pct']}% "
        f"{overall['wins']}/{overall['losses']} pts={overall['points']}",
        flush=True,
    )
    for y, st in by_year.items():
        print(f"  {y}: n={st['n']} hit={st['hit_pct']}%", flush=True)

    payload = {
        "desk": DESK,
        "logic": "dual p>=0.45 + OR break bf>=0.20 + combine · ±50/50",
        "window": f"{WIN_A} → {WIN_B}",
        "download": dl,
        "tape": str(TAPE).replace("\\", "/"),
        "overall": overall,
        "by_year": by_year,
        "by_month": by_month,
        "elapsed_s": round(time.time() - t0, 1),
    }
    lines = [
        "# SENSEX dual+fb bf≥20% · 5m · 2018–2020",
        "",
        f"**Desk:** `{DESK}` · exact locked logic · ±50/50",
        f"**Tape:** `{TAPE.name}` (Kite 5m)",
        f"**Window scored:** {overall['start']} → {overall['end']}",
        f"**Tape span:** {overall['tape_min']} → {overall['tape_max']}",
        "",
        "## Download",
        "",
    ]
    if dl.get("error"):
        lines += [f"- **Download error:** `{dl['error']}`", "- Tested existing tape on disk", ""]
    elif dl.get("skipped"):
        lines += [
            f"- Skipped (already from {dl.get('min')})",
            f"- Bars: **{dl.get('n')}** · sessions **{dl.get('sessions')}**",
            "",
        ]
    else:
        lines += [
            f"- Bars: **{dl.get('n')}** · sessions **{dl.get('sessions')}**",
            f"- Range: **{dl.get('min')} → {dl.get('max')}**",
            "",
        ]
    lines += [
        "## Overall (5m path-score · 2018–2020)",
        "",
        f"**Calls:** {overall['n']} · **Hit:** **{overall['hit_pct']}%** · "
        f"W/L **{overall['wins']}/{overall['losses']}** · pts {overall['points']}",
        f"Days: {overall['days_with_call']}/{overall['sessions']} · "
        f"dual {overall['dual_only']} · fb {overall['fallback_only']} · combo {overall['combined']}",
        "",
        "## Per year",
        "",
        "| Year | N | Hit% | W/L | Dual | FB | Combo | Pts |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for y, st in by_year.items():
        lines.append(
            f"| **{y}** | {st['n']} | **{st['hit_pct']}** | {st['wins']}/{st['losses']} | "
            f"{st['dual_only']} | {st['fallback_only']} | {st['combined']} | {st['points']} |"
        )
    lines += [
        "",
        "## Per month",
        "",
        "| Month | N | Hit% | W/L | Dual | FB | Combo | Pts |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for m, st in by_month.items():
        lines.append(
            f"| {m} | {st['n']} | {st['hit_pct']} | {st['wins']}/{st['losses']} | "
            f"{st['dual_only']} | {st['fallback_only']} | {st['combined']} | {st['points']} |"
        )
    lines += ["", f"_Done in {round(time.time()-t0,1)}s_", ""]

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "SENSEX_DUAL_FB_BF20_5M_2018_2020.md"
    js = OUT / "SENSEX_DUAL_FB_BF20_5M_2018_2020.json"
    md.write_text("\n".join(lines), encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
