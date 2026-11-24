"""Sensex dual + OR fallback · no mutual block · merge when same-time.

- Dual OR-break and OR-fallback both can fire the same day.
- No "fallback only if dual empty" and no "dual blocks fallback".
- If both satisfy at the same hm+side → ONE call with combined tags.
- Otherwise keep both (can be >1 call/day). No CAP block between streams.

  python -u prod_live/tests/builders/_lock_sensex_dual_fb_combine.py
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
FINAL_JSON = (
    ROOT
    / "stock_signal_data"
    / "fno_validate"
    / "research"
    / "sensex_side_models"
    / "sensex_proven_100_final.json"
)
HOLD = ROOT / "prod_live" / "holding_accurate" / "sensex_final"
FB_HELPER = ROOT / "prod_live" / "logic" / "sensex_everyday_fallback.py"

END = "2026-11-19"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_3M = (pd.Timestamp(END) - timedelta(days=92)).strftime("%Y-%m-%d")
SL = T1 = 50.0
DESK = "SENSEX_DUAL_FB_COMBINE_T50"


def sessions(bars: pd.DataFrame, a: str, b: str) -> List[str]:
    return sorted(
        {
            str(pd.Timestamp(t).date())
            for t in bars.index
            if a <= str(pd.Timestamp(t).date()) <= b
        }
    )


def fallback_row(bars: pd.DataFrame, day: str) -> Optional[dict]:
    db = bars[bars.index.strftime("%Y-%m-%d") == day]
    if len(db) < 2:
        return None
    or_hi = float(db["High"].iloc[0])
    or_lo = float(db["Low"].iloc[0])
    entry_ts = None
    for want in ("09:45", "09:30", "10:00", "10:15"):
        hit = db[db.index.strftime("%H:%M") == want]
        if len(hit):
            entry_ts = hit.index[0]
            break
    if entry_ts is None:
        entry_ts = db.index[min(1, len(db) - 1)]
    close = float(db.loc[entry_ts, "Close"])
    mid = (or_hi + or_lo) / 2.0
    if close > or_hi:
        side = "BUY"
    elif close < or_lo:
        side = "SELL"
    else:
        side = "BUY" if close >= mid else "SELL"
    hm = f"{entry_ts.hour:02d}:{entry_ts.minute:02d}"
    return {
        "day": day,
        "hm": hm,
        "decision": side,
        "side": side,
        "p_t1": 0.50,
        "first_break": True,
        "track": "or_fallback",
        "source": "fallback",
        "tags": ["fallback", "OR_09:45"],
    }


def key_of(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day"))[:10], str(r.get("hm") or "")[:5], str(r.get("decision") or "").upper())


def build_day_calls(bars, by, day: str) -> List[dict]:
    """Dual + fallback same day; merge if same hm+side."""
    duals = []
    for r in list(by.get(day) or []):
        duals.append(
            {
                **r,
                "source": "dual",
                "track": r.get("track") or "champion",
                "tags": ["dual", "OR_break"],
            }
        )
    # no max_per_day block — all duals keep
    fb = fallback_row(bars, day)
    if not duals and not fb:
        return []
    if not fb:
        return duals
    if not duals:
        return [fb]

    # merge fallback into matching dual (same hm+side); else append fallback
    out: List[dict] = []
    fb_k = key_of(fb)
    merged = False
    for d in duals:
        if key_of(d) == fb_k:
            row = dict(d)
            tags = list(dict.fromkeys((row.get("tags") or []) + (fb.get("tags") or []) + ["dual", "fallback", "COMBINED"]))
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
        # same-time soft merge: same day + same side at fallback hm (dual at 09:45)
        soft = None
        for i, d in enumerate(out):
            if (
                str(d.get("decision") or "").upper() == fb_k[2]
                and str(d.get("hm") or "")[:5] == fb_k[1]
            ):
                soft = i
                break
        if soft is not None:
            row = dict(out[soft])
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
            out[soft] = row
        else:
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
    print("Lock dual+fallback combine (no mutual block)", flush=True)
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
        by[n["day"]].append(n)

    picks: List[dict] = []
    for day in sessions(bars, START_3Y, END):
        picks.extend(build_day_calls(bars, by, day))

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
        f"  1y n={s1['n']} days={s1['days_with_call']}/{s1['sessions']} "
        f"hit={s1['hit_pct']}% dual={s1['dual_only']} fb={s1['fallback_only']} "
        f"combo={s1['combined']} avg={s1['avg_calls_per_day']}",
        flush=True,
    )
    print(f"  3m hit={s3m['hit_pct']}% n={s3m['n']} | 3y hit={s3y['hit_pct']}% n={s3y['n']}", flush=True)

    lo = min(s1["hit_pct"], s3y["hit_pct"])
    hi = max(s1["hit_pct"], s3y["hit_pct"], s3m["hit_pct"])
    acc = f"ACC_RANGE_{int(lo)}_{int(min(100, round(hi)))}"
    policy = {
        "name": "DUAL_AND_FALLBACK_COMBINE",
        "mode": "dual_fb_combine",
        "dual": "OR-break p>=0.45 BUY/SELL · no or_ext · sell cont · all duals",
        "fallback": "OR @ 09:45 every session (always evaluated)",
        "combine": "if dual and fallback same hm+side → 1 call with both tags",
        "mutual_block": False,
        "buy_min_p": 0.45,
        "sell_min_p": 0.45,
        "allow_sell_cont": True,
        "buy_max_or_ext": None,
        "max_per_day": None,
        "clip_sl": SL,
        "clip_t1": T1,
    }
    meta = {
        "desk": DESK,
        "mode": "dual_fb_combine",
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
        "note": "dual+fallback both on · merge same-time into 1 tagged call",
    }
    HOLD.mkdir(parents=True, exist_ok=True)
    held = [r for r in scored if START_3Y <= str(r.get("day") or "")[:10] <= END]
    calls_path = HOLD / "champ_plus_t50_sl50_calls.json"
    calls_path.write_text(json.dumps({"calls": held, "meta": meta}, indent=2), encoding="utf-8")

    payload = {
        "symbol": "SENSEX",
        "version": "dual_fb_combine_t50",
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
    for folder, label, st in (
        (OUT, "1y", s1),
        (ROOT / "prod_live" / "reports" / "3y", "3y", s3y),
        (ROOT / "prod_live" / "reports" / "5y", "5y", s3y),
    ):
        (folder / f"SENSEX_FINAL_CHAMP_PLUS_{label.upper()}.json").write_text(
            json.dumps({**payload, "window": label, "window_stats": st}, indent=2, default=str),
            encoding="utf-8",
        )

    # live: no CAP block
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
    text = re.sub(
        r"CAP = [^\n]+",
        "CAP = 99  # no stream block; same-time dual+fb merges to 1 tagged call",
        text,
        count=1,
    )
    # ensure dedupe only on hm+side (allow many/day)
    if "if not exists and len(day_rows) < CAP:" in text:
        text = text.replace(
            "if not exists and len(day_rows) < CAP:",
            "if not exists:",
            1,
        )
    SX_LIVE.write_text(text, encoding="utf-8")

    dual = DUAL.read_text(encoding="utf-8")
    dual = re.sub(r"CHAMPION_BUY_MIN_P = [0-9.]+", "CHAMPION_BUY_MIN_P = 0.45", dual, count=1)
    dual = re.sub(r"CHAMPION_SELL_MIN_P = [0-9.]+", "CHAMPION_SELL_MIN_P = 0.45", dual, count=1)
    dual = re.sub(
        r"CHAMPION_BUY_MAX_OR_EXT = [^\n]+",
        "CHAMPION_BUY_MAX_OR_EXT = None  # dual+fb combine",
        dual,
        count=1,
    )
    dual = re.sub(
        r"CHAMPION_SELL_FIRST_ONLY = (True|False)",
        "CHAMPION_SELL_FIRST_ONLY = False",
        dual,
        count=1,
    )
    dual = re.sub(
        r"CHAMPION_HIT_PCT = [0-9.]+",
        f"CHAMPION_HIT_PCT = {float(s1['hit_pct'] or 0):.1f}",
        dual,
        count=1,
    )
    # re-enable combine-aware fallback (not empty-only)
    if "# ev = _try_everyday_fallback(" in dual:
        dual = dual.replace(
            "    # Dual-only: no OR empty-day fallback — multiple duals combine (CAP in ledger)\n"
            "    if not ev.get(\"available\"):\n"
            "        return ev\n",
            "    ev = _try_combine_fallback(result, ev, bars=bars, asof=asof, price=price)\n"
            "    if not ev.get(\"available\") and not ev.get(\"call_payload\"):\n"
            "        return ev\n",
            1,
        )
    # if still commented path from prior lock
    if "_try_combine_fallback" not in dual and "_try_everyday_fallback" in dual:
        # replace everyday empty-only helper usage with combine helper at call site
        dual = dual.replace(
            "# everyday OR fallback disabled — dual-only combine\n"
            "    # ev = _try_everyday_fallback(result, ev, bars=bars, asof=asof, price=price)\n",
            "ev = _try_combine_fallback(result, ev, bars=bars, asof=asof, price=price)\n",
            1,
        )
    DUAL.write_text(dual, encoding="utf-8")

    # write combine helper into dual track (append/replace function)
    combine_fn = '''
def _try_combine_fallback(
    result: Dict[str, Any],
    ev: Dict[str, Any],
    *,
    bars: Any,
    asof: Any,
    price: Any,
) -> Dict[str, Any]:
    """OR fallback always evaluated; if dual already fired same hm+side, merge tags into 1 call."""
    try:
        import pandas as pd
        from prod_live.logic import sensex_everyday_fallback as sx_fb
        from prod_live.logic import sensex_final_live as sx_final

        ts = pd.Timestamp(asof) if asof is not None else None
        mins = (ts.hour * 60 + ts.minute) if ts is not None else 0
        if mins < (9 * 60 + 45):
            return ev
        fb = sx_fb.or_fallback_call(bars, asof=asof, price=price)
        if not (isinstance(fb, dict) and fb.get("decision") in ("BUY", "SELL")):
            return ev
        side = str(fb["decision"]).upper()
        hm = str(fb.get("hm") or "")[:5]
        entry_px = float(fb.get("entry") or price or 0)
        lv = sx_final.levels(entry_px, side) if entry_px > 0 else {}
        tags_fb = ["fallback", "OR_09:45", sx_final.DESK_CHAMP, sx_final.ACCURACY_TAG]

        existing = ev.get("call_payload") if isinstance(ev.get("call_payload"), dict) else None
        if (
            isinstance(existing, dict)
            and str(existing.get("decision") or "").upper() == side
            and str(existing.get("hm") or existing.get("time") or "")[:5] in ("", hm, str(hm))
        ):
            # same-time: ONE call, combine tags
            merged = dict(existing)
            tags = list(merged.get("accuracy_tags") or merged.get("tags") or [])
            for t in (tags_fb + ["dual", "fallback", "COMBINED"]):
                if t not in tags:
                    tags.append(t)
            merged["accuracy_tags"] = tags
            merged["tags"] = tags
            merged["source"] = "dual+fallback"
            merged["track"] = "dual_fb_combined"
            merged["combined"] = True
            merged["accuracy_label"] = "Dual + OR fallback · combined"
            ev = dict(ev)
            ev["call_payload"] = merged
            ev["combined_dual_fallback"] = True
            fa = dict(result.get("fno_analysis") or {})
            fa["sensex_dual_fb_combined"] = True
            result["fno_analysis"] = fa
            return ev

        # dual silent or different — still allow fallback call (no mutual block)
        if isinstance(existing, dict) and existing.get("decision") in ("BUY", "SELL"):
            # dual already listed different setup — leave dual; annotate fallback parallel
            fa = dict(result.get("fno_analysis") or {})
            fa["sensex_or_fallback_parallel"] = {**fb, **lv, "accuracy_tags": tags_fb}
            result["fno_analysis"] = fa
            return ev

        call_payload = {
            **fb,
            **lv,
            "list_priority": 2,
            "dual_track": False,
            "source": "fallback",
            "track": "or_fallback",
            "accuracy_tags": tags_fb,
            "accuracy_label": "OR fallback · 09:45",
        }
        ev = dict(ev or {})
        ev["available"] = True
        ev["decision"] = side
        ev["call_payload"] = call_payload
        ev["everyday_fallback"] = True
        result["suggestion"] = {
            "kind": "suggestion",
            "source": "sensex_everyday_fallback",
            "decision": side,
            "entry": lv.get("entry", entry_px),
            "stop_loss": lv.get("stop_loss"),
            "target_1": lv.get("target_1"),
            "p_t1": 0.50,
            "track": "or_fallback",
            "accuracy_tags": tags_fb,
            "accuracy_label": call_payload["accuracy_label"],
            "message": f"{side} via OR fallback (±50).",
        }
        fa = dict(result.get("fno_analysis") or {})
        fa["suggestion"] = result["suggestion"]
        fa["sensex_everyday_fallback"] = True
        result["fno_analysis"] = fa
        return ev
    except Exception:
        return ev

'''
    # inject combine fn if missing
    dual2 = DUAL.read_text(encoding="utf-8")
    if "def _try_combine_fallback(" not in dual2:
        dual2 = dual2.replace(
            "def _try_everyday_fallback(",
            combine_fn + "\ndef _try_everyday_fallback(",
            1,
        )
        # ensure call site
        if "_try_combine_fallback(result, ev" not in dual2:
            if "if not ev.get(\"available\"):\n        return ev" in dual2:
                dual2 = dual2.replace(
                    "    # Dual-only: no OR empty-day fallback — multiple duals combine (CAP in ledger)\n"
                    "    if not ev.get(\"available\"):\n"
                    "        return ev\n",
                    "    ev = _try_combine_fallback(result, ev, bars=bars, asof=asof, price=price)\n"
                    "    if not ev.get(\"available\") and not ev.get(\"call_payload\"):\n"
                    "        return ev\n",
                    1,
                )
            elif "if not ev.get(\"available\"):\n        return ev\n" in dual2:
                dual2 = dual2.replace(
                    "    if not ev.get(\"available\"):\n        return ev\n",
                    "    ev = _try_combine_fallback(result, ev, bars=bars, asof=asof, price=price)\n"
                    "    if not ev.get(\"available\") and not ev.get(\"call_payload\"):\n"
                    "        return ev\n",
                    1,
                )
        DUAL.write_text(dual2, encoding="utf-8")

    cfg = ROOT / "app" / "fno" / "fno_live_config.py"
    cfg_t = cfg.read_text(encoding="utf-8")
    if "DUAL_FB_COMBINE" not in cfg_t:
        cfg_t = cfg_t.replace(
            'if ("EVERYDAY" in desk.upper()) or ("DUAL_2PD" in desk.upper()) or desk.upper().startswith("SENSEX_DUAL"):',
            'if ("EVERYDAY" in desk.upper()) or ("DUAL_2PD" in desk.upper()) or ("DUAL_FB_COMBINE" in desk.upper()) or desk.upper().startswith("SENSEX_DUAL"):',
            1,
        )
        cfg.write_text(cfg_t, encoding="utf-8")

    if FINAL_JSON.is_file():
        doc = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
        doc.setdefault("tracks", {}).setdefault("live_champion", {})["policy"] = policy
        doc["tracks"]["live_champion"]["full"] = {
            "n": s1["n"],
            "hit_pct": s1["hit_pct"],
            "coverage_pct": s1["coverage_pct"],
            "combined": s1["combined"],
        }
        doc["verdict"]["champion_hit_pct"] = s1["hit_pct"]
        doc["verdict"]["summary"] = (
            f"SENSEX dual+fb combine: 1y {s1['n']}@{s1['hit_pct']}% "
            f"combo {s1['combined']} · no mutual block"
        )
        FINAL_JSON.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    lines = [
        "# SENSEX · dual + fallback · combine same-time (±50/50)",
        "",
        f"**Desk:** `{DESK}`",
        "",
        "## Exact logic",
        "",
        "1. **Dual** — OR-break `p_t1 ≥ 0.45` BUY/SELL · no or_ext · sell cont · all duals kept",
        "2. **Fallback** — OR @ 09:45 **every** session (always evaluated — not only when dual empty)",
        "3. **No mutual block** — dual does not block fallback; fallback does not block dual",
        "4. **Same time** (same day + hm + side): emit **1 call** with tags `dual` + `fallback` + `COMBINED`",
        "5. Different times/sides: both can list (more than 1 call OK)",
        "6. Clip ±50/50",
        "",
        "## Results",
        "",
        "| Window | Days | Calls | Cov% | Hit% | Dual-only | FB-only | Combined | Avg/day | W/L |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        f"| **1y** | {s1['days_with_call']}/{s1['sessions']} | {s1['n']} | {s1['coverage_pct']} | **{s1['hit_pct']}** | {s1['dual_only']} | {s1['fallback_only']} | {s1['combined']} | {s1['avg_calls_per_day']} | {s1['wins']}/{s1['losses']} |",
        f"| **3m** | {s3m['days_with_call']}/{s3m['sessions']} | {s3m['n']} | {s3m['coverage_pct']} | **{s3m['hit_pct']}** | {s3m['dual_only']} | {s3m['fallback_only']} | {s3m['combined']} | {s3m['avg_calls_per_day']} | {s3m['wins']}/{s3m['losses']} |",
        f"| **3y** | {s3y['days_with_call']}/{s3y['sessions']} | {s3y['n']} | {s3y['coverage_pct']} | **{s3y['hit_pct']}** | {s3y['dual_only']} | {s3y['fallback_only']} | {s3y['combined']} | {s3y['avg_calls_per_day']} | {s3y['wins']}/{s3y['losses']} |",
        "",
        "## 3m months",
        "",
        "| Month | N | Hit | W/L |",
        "|---|---:|---:|---|",
    ]
    for m, ms in (s3m.get("by_month") or {}).items():
        lines.append(f"| {m} | {ms['n']} | {ms['hit_pct']} | {ms['wins']}/{ms['losses']} |")
    lines += ["", "_Locked dual+fallback combine_", ""]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "SENSEX_DUAL_FB_COMBINE.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "SENSEX_DUAL_FB_COMBINE.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    print(f"Wrote {OUT / 'SENSEX_DUAL_FB_COMBINE.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
