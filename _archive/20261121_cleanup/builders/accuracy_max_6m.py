"""Deep combine Final Logic books → accuracy-max algo · last 6m live pools.

Uses cached live-scored channel pools (same candles as stack prove).
Research only — does not wire live.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import fno_nse_mid_gate as nse_gate  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
MODEL_DIR = ROOT / "prod_live" / "models"
POOL = ROOT / "stock_signal_data/fno_validate/research/_cache_nifty_final_stack_5y_pools.json"
GATED_CSV = ROOT / "analysis/nifty_5m_buy_20pt_1y/gated_both_calls.csv"
DAILY_NSE = ROOT / "stock_signal_data/fno_validate/NIFTY_daily_nse.csv"
HTF = ROOT / "stock_signal_data/fno_validate/NIFTY_htf_nse_bundle.csv"

PRIORITY = {"proven_100": 0, "champion": 1, "crown_5m": 2, "good_prod2": 3, "gated_both": 4}


def _agg(rows: List[dict]) -> Dict[str, Any]:
    if not rows:
        return {"n": 0, "hit_pct": None, "wins": 0, "losses": 0, "points": 0.0, "days": 0, "by_track": {}}
    wins = sum(1 for r in rows if r.get("win"))
    n = len(rows)
    pts = float(sum(float(r.get("points") or 0) for r in rows))
    return {
        "n": n,
        "hit_pct": round(100.0 * wins / n, 2),
        "wins": wins,
        "losses": n - wins,
        "points": round(pts, 1),
        "days": len({r["day"] for r in rows}),
        "by_track": _by_track(rows),
    }


def _by_track(rows: List[dict]) -> Dict[str, Any]:
    g: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        g[str(r.get("track") or "?")].append(r)
    out = {}
    for k, rs in sorted(g.items()):
        w = sum(1 for r in rs if r.get("win"))
        out[k] = {
            "n": len(rs),
            "hit_pct": round(100.0 * w / len(rs), 2) if rs else None,
            "points": round(sum(float(r.get("points") or 0) for r in rs), 1),
        }
    return out


def _champ_floor(rows: List[dict]) -> List[dict]:
    kept = []
    for r in rows:
        side = str(r.get("decision") or "").upper()
        p = float(r.get("p_t1") or 0)
        if side == "BUY" and p < 0.55:
            continue
        if side == "SELL" and p < 0.58:
            continue
        kept.append(dict(r))
    return kept


def _union(cands: List[dict], *, day_cap: int) -> List[dict]:
    by_day: Dict[str, List[dict]] = defaultdict(list)
    for r in cands:
        by_day[str(r["day"])[:10]].append(dict(r))
    out: List[dict] = []
    for day in sorted(by_day):
        rows = sorted(
            by_day[day],
            key=lambda r: (
                int(r.get("priority", 9)),
                -float(r.get("p_t1") or 0),
                str(r.get("hm") or ""),
            ),
        )
        picked: List[dict] = []
        seen = set()
        for r in rows:
            key = (r["day"], str(r.get("decision")), str(r.get("hm")))
            if key in seen:
                continue
            if picked and any(str(p.get("decision")) != str(r.get("decision")) for p in picked):
                continue
            picked.append(r)
            seen.add(key)
            if len(picked) >= day_cap:
                break
        out.extend(picked)
    return out


def _nse_mid_map(days: List[str]) -> Dict[str, bool]:
    lo, hi = nse_gate.FROZEN_CUTS["AbsChangePct"]
    df = pd.read_csv(DAILY_NSE)
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values("Date")
    df["Abs"] = df["ChangePct"].astype(float).abs()
    df["prior_Abs"] = df["Abs"].shift(1)
    m = {str(r["Date"]): r["prior_Abs"] for _, r in df.iterrows()}
    out = {}
    for d in days:
        v = m.get(d)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            prior = df[df["Date"] < d]
            v = float(prior.iloc[-1]["Abs"]) if len(prior) else None
        else:
            v = float(v)
        out[d] = bool(v is not None and lo <= v < hi)
    return out


def _load_gated_6m(start: str, end: str) -> List[dict]:
    if not GATED_CSV.is_file():
        return []
    df = pd.read_csv(GATED_CSV)
    rows = []
    for _, r in df.iterrows():
        day = str(r["day"])[:10]
        if day < start or day > end:
            continue
        side = str(r["side"]).upper()
        decision = "BUY" if side.startswith("B") else "SELL"
        rows.append(
            {
                "day": day,
                "hm": str(r.get("time") or "")[:5],
                "decision": decision,
                "track": "gated_both",
                "priority": PRIORITY["gated_both"],
                "p_t1": 0.55,
                "win": bool(int(r["win"])),
                "points": float(r["points"]),
            }
        )
    return rows


def _side(r: dict) -> str:
    return "BUY" if str(r.get("decision") or "").upper() == "BUY" else "SELL"


def _day_side_index(rows: List[dict]) -> Dict[Tuple[str, str], List[dict]]:
    idx: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for r in rows:
        idx[(r["day"], _side(r))].append(r)
    return idx


def recipe_accuracy_max(
    *,
    proven: List[dict],
    champ: List[dict],
    good: List[dict],
    crown_htf: List[dict],
    gated: List[dict],
    nse_ok: Dict[str, bool],
    day_cap: int = 1,
) -> List[dict]:
    for r in proven:
        r["priority"] = PRIORITY["proven_100"]
        r["track"] = "proven_100"
    for r in champ:
        r["priority"] = PRIORITY["champion"]
        r["track"] = "champion"
    for r in good:
        r["priority"] = PRIORITY["good_prod2"]
        r["track"] = "good_prod2"
    for r in crown_htf:
        r["priority"] = PRIORITY["crown_5m"]
        r["track"] = "crown_5m"
    for r in gated:
        r["priority"] = PRIORITY["gated_both"]
        r["track"] = "gated_both"

    g_idx = _day_side_index(gated)
    good_idx = _day_side_index(good)
    crown_idx = _day_side_index(crown_htf)
    champ_idx = _day_side_index(champ)

    cands: List[dict] = []
    cands.extend(dict(r, reason="proven") for r in proven)

    for r in champ:
        day, side = r["day"], _side(r)
        gated_agree = bool(g_idx.get((day, side)))
        if nse_ok.get(day) or gated_agree:
            rr = dict(r)
            rr["reason"] = "champ_nse" if nse_ok.get(day) else "champ_gated_agree"
            cands.append(rr)

    days = sorted({r["day"] for r in (good + crown_htf + gated + champ)})
    for day in days:
        if not nse_ok.get(day):
            continue
        for side in ("BUY", "SELL"):
            tracks = []
            pick = None
            for name, idx in (
                ("champion", champ_idx),
                ("crown_5m", crown_idx),
                ("good_prod2", good_idx),
                ("gated_both", g_idx),
            ):
                rs = idx.get((day, side)) or []
                if rs:
                    tracks.append(name)
                    best = sorted(
                        rs, key=lambda x: (-float(x.get("p_t1") or 0), str(x.get("hm") or ""))
                    )[0]
                    if pick is None or PRIORITY[name] < PRIORITY.get(str(pick.get("track")), 9):
                        pick = dict(best)
            if len(tracks) >= 2 and pick is not None:
                pick["reason"] = "multi_agree_" + "+".join(tracks)
                pick["agree_n"] = len(tracks)
                cands.append(pick)

    for r in crown_htf:
        day, side = r["day"], _side(r)
        if nse_ok.get(day) and g_idx.get((day, side)):
            rr = dict(r)
            rr["reason"] = "crown_nse_gated"
            cands.append(rr)

    return _union(cands, day_cap=day_cap)


def main() -> None:
    print("loading cached live pools…", flush=True)
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    sessions_all, prod2_all, last_day = fs._prod2(800)
    last_dt = pd.Timestamp(str(last_day)[:10])
    # Align to live 6m report family: ~183d back from tape end in pool/prod2
    end = max(str(last_day)[:10], max(r["day"] for r in pool["proven_100"]))
    # Prefer the stack 6m end used in reports if within pool
    report_end = "2026-10-23"
    if any(r["day"] <= report_end for r in pool["crown_5m"]):
        end = report_end
    start = (pd.Timestamp(end) - timedelta(days=183)).strftime("%Y-%m-%d")
    sess = sorted({d for d in sessions_all if start < d <= end})
    if not sess:
        # fall back to days present in pools
        all_days = sorted(
            {
                str(r["day"])[:10]
                for rows in (pool["proven_100"], pool["champion"], pool["crown_5m"], prod2_all)
                for r in rows
            }
        )
        sess = [d for d in all_days if start < d <= end]
    print(f"6m window {start} → {end} · sessions {len(sess)}", flush=True)

    proven = [
        dict(r, track="proven_100", priority=PRIORITY["proven_100"])
        for r in pool["proven_100"]
        if start < r["day"] <= end
    ]
    champ = _champ_floor(
        [r for r in pool["champion"] if start < r["day"] <= end]
    )
    for r in champ:
        r["track"] = "champion"
        r["priority"] = PRIORITY["champion"]
    crown = [
        dict(r, track="crown_5m", priority=PRIORITY["crown_5m"])
        for r in pool["crown_5m"]
        if start < r["day"] <= end
    ]
    good = [
        dict(r, track="good_prod2", priority=PRIORITY["good_prod2"])
        for r in prod2_all
        if start < r["day"] <= end
    ]

    daily = fs._load_daily()
    active = fs._active_days(sess if sess else sorted({r["day"] for r in crown}), daily)
    crown_htf = [r for r in crown if r["day"] in active]
    nse_ok = _nse_mid_map(sorted(set(sess) | set(active) | {r["day"] for r in proven + champ + good + crown}))
    gated = _load_gated_6m(start, end)

    stack_base = fs._union(
        {
            "proven_100": proven,
            "good_prod2": good,
            "champion": champ,
            "crown_5m": crown_htf,
        },
        day_cap=2,
    )

    am1 = recipe_accuracy_max(
        proven=proven, champ=champ, good=good, crown_htf=crown_htf, gated=gated, nse_ok=nse_ok, day_cap=1
    )
    am2 = recipe_accuracy_max(
        proven=proven, champ=champ, good=good, crown_htf=crown_htf, gated=gated, nse_ok=nse_ok, day_cap=2
    )

    books = {
        "LIVE_STACK_BASE": _agg(stack_base),
        "PROVEN_ONLY": _agg(_union(proven, day_cap=2)),
        "PROVEN_CHAMP_CAP1": _agg(_union(proven + champ, day_cap=1)),
        "PROVEN_CHAMP_CAP2": _agg(_union(proven + champ, day_cap=2)),
        "PROVEN_CHAMP_NSE_CAP1": _agg(
            _union(proven + [r for r in champ if nse_ok.get(r["day"])], day_cap=1)
        ),
        "STACK_NSE_CAP1": _agg(_union([r for r in stack_base if nse_ok.get(r["day"])], day_cap=1)),
        "STACK_NSE_CAP2": _agg(_union([r for r in stack_base if nse_ok.get(r["day"])], day_cap=2)),
        "CROWN_HTF_NSE": _agg(_union([r for r in crown_htf if nse_ok.get(r["day"])], day_cap=2)),
        "GATED_BOTH_6M": _agg(gated),
        "ACCURACY_MAX_CAP1": _agg(am1),
        "ACCURACY_MAX_CAP2": _agg(am2),
    }

    raw = {
        "proven_100": _agg(proven),
        "champion_floored": _agg(champ),
        "good_prod2": _agg(good),
        "crown_htf": _agg(crown_htf),
        "gated_both": _agg(gated),
        "nse_mid_days": int(sum(1 for d in sess if nse_ok.get(d))),
        "htf_active_days": len(active),
        "sessions": len(sess),
    }

    ranked = sorted(
        ((k, v) for k, v in books.items() if v and v["n"] >= 8),
        key=lambda kv: (kv[1]["hit_pct"] or 0, kv[1]["n"]),
        reverse=True,
    )
    best = ranked[0] if ranked else (None, None)

    common = {
        "shared_bones": [
            "prior-day context gate (VIX / NSE AbsChangePct / HTF volume-range)",
            "structure lean (OR / VWAP-EMA / first break)",
            "model P(win) floor",
            "enter at signal close",
            "day cap + same-side discipline",
        ],
        "accuracy_levers": [
            "proven_100 rare ~100% — always keep",
            "champion next — keep with NSE or gated agree",
            "good_prod2 alone ~70% — drops accuracy if taken solo",
            "NSE mid day gate lifts hit, cuts volume",
            "multi-channel same-side agree adds confirmed calls",
            "gated_both is independent VIX-split confirm",
        ],
        "algo": "ACCURACY_MAX",
        "steps": [
            "1. Take every PROVEN_100",
            "2. Take CHAMPION if NSE_MID_ABS or GATED_BOTH same side",
            "3. On NSE_MID days take multi-agree (≥2 of champ/crown/good/gated)",
            "4. Take CROWN_HTF only if NSE mid AND gated same side",
            "5. Never take GOOD alone",
            "6. Cap1 (strict) or Cap2; same-side; priority proven>champ>crown>good>gated",
        ],
    }

    payload = {
        "window": {"start": start, "end": end, "sessions": len(sess)},
        "common_analysis": common,
        "raw_channels": raw,
        "books": books,
        "ranked": [{"name": k, **v} for k, v in ranked],
        "best": {"name": best[0], **best[1]} if best[0] else None,
        "accuracy_max_cap1_calls": [
            {
                "day": r["day"],
                "hm": r.get("hm"),
                "side": _side(r),
                "track": r.get("track"),
                "p": r.get("p_t1"),
                "win": bool(r.get("win")),
                "points": r.get("points"),
                "reason": r.get("reason"),
            }
            for r in am1
        ],
    }
    (MODEL_DIR / "accuracy_max_6m.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Accuracy-max single algo · last 6m live candles",
        "",
        f"Window `{start}` → `{end}` · sessions **{len(sess)}**",
        "Pools = live-scored channels (same candles as stack prove). Research only.",
        "",
        "## What is common",
        "",
    ]
    for x in common["shared_bones"]:
        lines.append(f"- {x}")
    lines += ["", "## Accuracy levers", ""]
    for x in common["accuracy_levers"]:
        lines.append(f"- {x}")
    lines += ["", "## Algo `ACCURACY_MAX`", ""]
    for x in common["steps"]:
        lines.append(x)
    lines += ["", "## Raw channels (6m)", "", "| Channel | N | Hit | Pts |", "|---|---:|---:|---:|"]
    for k in ("proven_100", "champion_floored", "good_prod2", "crown_htf", "gated_both"):
        s = raw[k]
        lines.append(f"| `{k}` | {s['n']} | {s['hit_pct']}% | {s['points']} |")
    lines += [
        "",
        f"NSE mid days: **{raw['nse_mid_days']}** / {raw['sessions']} · HTF-active: **{raw['htf_active_days']}**",
        "",
        "## Combined books (ranked by hit, n≥8)",
        "",
        "| Book | N | Hit | W/L | Pts | Days |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for k, v in ranked:
        lines.append(
            f"| `{k}` | {v['n']} | **{v['hit_pct']}%** | {v['wins']}/{v['losses']} | {v['points']} | {v['days']} |"
        )
    if best[0]:
        base = books["LIVE_STACK_BASE"]
        lines += [
            "",
            f"**Best:** `{best[0]}` → **{best[1]['hit_pct']}%** of {best[1]['n']} "
            f"(live stack {base['hit_pct']}% of {base['n']})",
            "",
            "### Track mix · ACCURACY_MAX_CAP1",
            "",
        ]
        for tr, s in (books["ACCURACY_MAX_CAP1"].get("by_track") or {}).items():
            lines.append(f"- `{tr}`: {s['n']} @ {s['hit_pct']}% · pts {s['points']}")
    (OUT / "ACCURACY_MAX_6M.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"best": payload["best"], "ranked": payload["ranked"], "raw": raw}, indent=2))
    print("Wrote", MODEL_DIR / "accuracy_max_6m.json")
    print("Wrote", OUT / "ACCURACY_MAX_6M.md")


if __name__ == "__main__":
    main()
