"""Hold ACC100_MULTI_V2 and validate on 5y then 10y (path-true).

Extends dual15/dual5 walks beyond 3y cache, path-scores good/crown,
rebuilds V2 desk, reports 3y / 5y / 10y.

  python -u prod_live/tests/builders/research_acc100_v2_5y_10y.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
warnings.filterwarnings("ignore")
import path_setup  # noqa: F401,E402

os.environ.setdefault("TELEGRAM_NOTIFY", "0")
os.environ.setdefault("WHATSAPP_NOTIFY", "0")
os.environ["ENABLE_NSE_MID_GATE"] = "0"
os.environ.setdefault("CROWN_BUILD_QUIET", "1")

import nifty_live_dual_track as live  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import POOL, _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import _clip, _hm_mins, _side  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    build_bar_index,
    gap_map,
    path_rescore_list,
    _norm,
)
from research_dual15_dual5_confirm100 import (  # noqa: E402
    LOOKBACK,
    BAR_DELTA,
    CHAMP_BUY_MIN,
    CHAMP_SELL_MIN,
    _or_break_idxs,
    _fwd,
    _day,
    _hm,
)
from prod_live.logic.acc100_streams import (  # noqa: E402
    merge_acc100_multi_v2,
    TAG_DESK_V2,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL_3Y = LEDGER / "_cache_dual15_dual5_confirm.json"
CACHE_DUAL_10Y = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_calls.json"
CACHE_PATH_10Y = LEDGER / "_cache_path_trusted_10y.json"
TAPE15 = ROOT / "stock_signal_data/fno_validate/NIFTY_15m_12y.csv"
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"

END = "2026-11-13"
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_5Y = (pd.Timestamp(END) - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
START_10Y = (pd.Timestamp(END) - timedelta(days=365 * 10)).strftime("%Y-%m-%d")


def sessions_from_bars(bars: pd.DataFrame, start: str, end: str) -> List[str]:
    return sorted(
        {
            _day(ts)
            for ts in bars.index
            if start < _day(ts) <= end and "09:15" <= _hm(ts) <= "15:15"
        }
    )


def day_slices(bars: pd.DataFrame, sessions: List[str]) -> Dict[str, pd.DataFrame]:
    want = set(sessions)
    out: Dict[str, List] = defaultdict(list)
    # single pass
    for ts in bars.index:
        d = _day(ts)
        if d not in want:
            continue
        h = _hm(ts)
        if "09:15" <= h <= "15:15":
            out[d].append(ts)
    return {d: bars.loc[out[d]] for d in sessions if d in out and len(out[d]) >= 4}


def collect_dual_fast(
    bars: pd.DataFrame,
    sessions: List[str],
    *,
    tf: str,
    existing: Optional[Dict[str, List[dict]]] = None,
) -> Dict[str, List[dict]]:
    """OR-break dual walk with day pre-slice; merges existing cache rows."""
    have_days: Set[str] = set()
    proven: List[dict] = []
    champ: List[dict] = []
    if existing:
        for r in existing.get("proven_100") or []:
            proven.append(dict(r))
            have_days.add(str(r["day"]))
        for r in existing.get("champion") or []:
            champ.append(dict(r))
            have_days.add(str(r["day"]))
        # note: have_days marks days already walked even if empty — use cache session list if present
    cache_sess = set((existing or {}).get("_sessions") or have_days)
    todo = [d for d in sessions if d not in cache_sess]
    print(
        f"  {tf} dual: cached_days~{len(cache_sess)} todo={len(todo)}/{len(sessions)}",
        flush=True,
    )
    if not todo:
        return {"proven_100": proven, "champion": champ, "_sessions": sorted(cache_sess | set(sessions))}

    slices = day_slices(bars, todo)
    delta = BAR_DELTA[tf]
    t0 = time.time()
    for si, day in enumerate(todo, 1):
        if si % 50 == 0 or si == len(todo):
            print(
                f"    {tf} {si}/{len(todo)} ({time.time()-t0:.0f}s) "
                f"proven={len(proven)} champ={len(champ)}",
                flush=True,
            )
        sess = slices.get(day)
        if sess is None or len(sess) < 4:
            cache_sess.add(day)
            continue
        for i_local in _or_break_idxs(sess):
            ts = sess.index[i_local]
            full_i = int(bars.index.get_indexer([ts])[0])
            if full_i < 0:
                continue
            asof = ts + delta
            left = int(bars.index.searchsorted(ts - LOOKBACK))
            win = bars.iloc[left : full_i + 1]
            price = float(bars["Close"].iloc[full_i])
            hm = _hm(ts)
            try:
                ev = live.evaluate(win, asof=asof, price=price, session_ticket=None)
            except Exception:
                continue
            call = (ev or {}).get("call_payload") or {}
            dec = str(call.get("decision") or "").upper()
            if dec not in ("BUY", "SELL"):
                continue
            try:
                pf = float(call.get("p_t1")) if call.get("p_t1") is not None else None
            except Exception:
                pf = None
            track = str(
                call.get("track")
                or ("proven_100" if (ev or {}).get("proven_100") else "champion")
            )
            if track == "baseline":
                track = "champion"
            if track != "proven_100":
                if dec == "BUY" and pf is not None and pf < CHAMP_BUY_MIN:
                    continue
                if dec == "SELL" and pf is not None and pf < CHAMP_SELL_MIN:
                    continue
            sl = float(call["stop_loss"])
            t1 = float(call["target_1"])
            win_f, outcome, pts = _fwd(bars, full_i, dec, sl, t1)
            row = {
                "day": day,
                "hm": hm,
                "decision": dec,
                "track": track,
                "tf": tf,
                "p_t1": pf,
                "win": win_f,
                "points": round(pts, 1),
                "outcome": outcome,
                "entry": round(float(call.get("entry") or price), 2),
                "stop_loss": round(sl, 2),
                "target_1": round(t1, 2),
                "proven": bool((ev or {}).get("proven_100")),
                "champion": bool((ev or {}).get("champion")),
            }
            if track == "proven_100":
                proven.append(row)
            else:
                champ.append(row)
        cache_sess.add(day)
    return {
        "proven_100": proven,
        "champion": champ,
        "_sessions": sorted(cache_sess),
    }


def collect_crown_pool_and_path(
    bars5: pd.DataFrame,
    ix5: Dict[Tuple[str, str], int],
    sessions: List[str],
    active: Set[str],
) -> Dict[str, List[dict]]:
    """Use pool crown rows in range; path-rescore at multiple risks."""
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    sess_set = set(sessions)
    raw = [
        dict(r, track="crown_5m")
        for r in pool["crown_5m"]
        if str(r["day"]) in sess_set
    ]
    print(f"  crown pool in window n={len(raw)} "
          f"({min((r['day'] for r in raw), default='-')}→{max((r['day'] for r in raw), default='-')})",
          flush=True)
    out = {}
    for risk in (20.0, 30.0, 35.0, 40.0):
        out[f"{risk:.1f}"] = path_rescore_list(
            raw, bars5, ix5, risk=risk, label=f"crown_T{int(risk)}"
        )
    # also keep unfiltered list note
    out["_raw_n"] = len(raw)  # type: ignore
    out["_htf_n"] = len([r for r in raw if r["day"] in active])  # type: ignore
    return out  # type: ignore


def pack_window(rows: List[dict], sess: List[str], start: str, end: str) -> Dict[str, Any]:
    rs = _clip(rows, start, end)
    if not rs:
        return {
            "start": start,
            "end": end,
            "sessions": len([d for d in sess if start < d <= end]),
            "n": 0,
            "hit_pct": None,
            "perfect": False,
            "points": 0.0,
            "wins": 0,
            "losses": 0,
            "by_track": {},
        }
    st = _agg(rs)
    by_tag: Dict[str, List[dict]] = defaultdict(list)
    for r in rs:
        tag = str(r.get("holding_tag") or r.get("accurate_tag") or r.get("track") or "?")
        by_tag[tag].append(r)
    tag_stats = {}
    for k, xs in sorted(by_tag.items()):
        w = sum(1 for r in xs if r.get("win"))
        tag_stats[k] = {
            "n": len(xs),
            "hit_pct": round(100.0 * w / len(xs), 2) if xs else None,
            "points": round(sum(float(r.get("points") or 0) for r in xs), 1),
        }
    return {
        "start": start,
        "end": end,
        "sessions": len([d for d in sess if start < d <= end]),
        "n": st["n"],
        "hit_pct": st["hit_pct"],
        "perfect": bool(rs) and all(bool(r.get("win")) for r in rs),
        "points": st.get("points"),
        "wins": st.get("wins"),
        "losses": st.get("losses"),
        "by_track": st.get("by_track"),
        "by_holding_tag": tag_stats,
    }


def main() -> None:
    t0 = time.time()
    print("ACC100_MULTI_V2 long-horizon test (5y then 10y)", flush=True)
    print(f"  END={END}  START_5Y={START_5Y}  START_10Y={START_10Y}", flush=True)
    print(f"  packs ok={live.packs_available()}", flush=True)

    bars15 = _norm(pd.read_csv(TAPE15, index_col=0, parse_dates=True))
    bars5 = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    print(f"  tape15 {bars15.index.min()} → {bars15.index.max()}", flush=True)
    print(f"  tape5  {bars5.index.min()} → {bars5.index.max()}", flush=True)

    sess10 = sessions_from_bars(bars15, START_10Y, END)
    sess5m = set(sessions_from_bars(bars5, START_10Y, END))
    sess10 = [d for d in sess10 if d in sess5m]
    print(f"  sessions 10y={len(sess10)} {sess10[0]}→{sess10[-1]}", flush=True)

    # --- dual caches ---
    existing15 = existing5 = None
    if CACHE_DUAL_10Y.is_file():
        c10 = json.loads(CACHE_DUAL_10Y.read_text(encoding="utf-8"))
        if c10.get("end") == END and c10.get("start") <= START_10Y:
            print("  loading 10y dual cache…", flush=True)
            existing15 = {**c10["dual15"], "_sessions": c10.get("sessions15") or c10.get("sessions")}
            existing5 = {**c10["dual5"], "_sessions": c10.get("sessions5") or c10.get("sessions")}
    if existing15 is None and CACHE_DUAL_3Y.is_file():
        c3 = json.loads(CACHE_DUAL_3Y.read_text(encoding="utf-8"))
        print("  seeding from 3y dual cache…", flush=True)
        existing15 = {**c3["dual15"], "_sessions": c3.get("sessions") or []}
        # mark only days that appear in rows + assume full walk of 3y range
        s3 = set()
        for r in c3["dual15"]["proven_100"] + c3["dual15"]["champion"]:
            s3.add(r["day"])
        # better: all sessions in 3y cache start-end
        if c3.get("start") and c3.get("end"):
            s3 |= set(sessions_from_bars(bars15, c3["start"], c3["end"]))
        existing15["_sessions"] = sorted(s3)
        existing5 = {**c3["dual5"], "_sessions": sorted(s3)}

    print("  walk dual15 10y…", flush=True)
    d15 = collect_dual_fast(bars15, sess10, tf="15m", existing=existing15)
    print("  walk dual5 10y…", flush=True)
    d5 = collect_dual_fast(bars5, sess10, tf="5m", existing=existing5)

    CACHE_DUAL_10Y.write_text(
        json.dumps(
            {
                "start": START_10Y,
                "end": END,
                "dual15": {"proven_100": d15["proven_100"], "champion": d15["champion"]},
                "dual5": {"proven_100": d5["proven_100"], "champion": d5["champion"]},
                "sessions15": d15.get("_sessions"),
                "sessions5": d5.get("_sessions"),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(
        f"  dual15 proven={len(d15['proven_100'])} champ={len(d15['champion'])}",
        flush=True,
    )
    print(
        f"  dual5  proven={len(d5['proven_100'])} champ={len(d5['champion'])}",
        flush=True,
    )

    # --- good path scores ---
    print("  loading good prod2 (long hist)…", flush=True)
    sessions_all, prod2_all, _ = fs._prod2(4000)
    good_raw = [
        dict(r, track="good_prod2")
        for r in prod2_all
        if START_10Y < str(r.get("day") or "") <= END
    ]
    print(f"  good raw n={len(good_raw)}", flush=True)
    print("  indexing tapes for path…", flush=True)
    ix15 = build_bar_index(bars15)
    ix5 = build_bar_index(bars5)

    if CACHE_PATH_10Y.is_file():
        pc = json.loads(CACHE_PATH_10Y.read_text(encoding="utf-8"))
        if pc.get("end") == END and pc.get("start") == START_10Y:
            print("  loading path 10y cache…", flush=True)
            good_by_risk = pc["good_by_risk"]
            crown_by_risk = pc["crown_by_risk"]
            champ_native = pc["champ_native"]
        else:
            pc = None
    else:
        pc = None

    if pc is None:
        good_by_risk = {}
        for risk in (30.0, 35.0, 40.0):
            good_by_risk[f"{risk:.1f}"] = path_rescore_list(
                good_raw, bars15, ix15, risk=risk, label=f"good_T{int(risk)}"
            )
            good_by_risk[str(int(risk))] = good_by_risk[f"{risk:.1f}"]
        # native good wins from outcome
        good_nat = []
        for r in good_raw:
            rr = dict(r)
            if "win" not in rr:
                rr["win"] = rr.get("outcome") == "t1_before_sl"
            rr["path_trusted"] = True
            good_nat.append(rr)
        good_by_risk["native"] = good_nat

        champ_rows = _champ_floor(
            [dict(r, track="champion") for r in d15["champion"]]
        )
        champ_native = path_rescore_list(
            champ_rows, bars15, ix15, risk=30.0, use_native_brackets=True, label="champ_nat"
        )

        daily = fs._load_daily()
        active = fs._active_days(sess10, daily)
        crown_by_risk = collect_crown_pool_and_path(bars5, ix5, sess10, active)
        # normalize keys
        for k in list(crown_by_risk.keys()):
            if k.startswith("_"):
                continue
            if "." in k:
                crown_by_risk[str(int(float(k)))] = crown_by_risk[k]

        CACHE_PATH_10Y.write_text(
            json.dumps(
                {
                    "start": START_10Y,
                    "end": END,
                    "good_by_risk": {k: v for k, v in good_by_risk.items() if not k.startswith("_")},
                    "crown_by_risk": {k: v for k, v in crown_by_risk.items() if not str(k).startswith("_")},
                    "champ_native": champ_native,
                    "crown_coverage_note": "crown pool starts ~2024-05; earlier years have no crown streams",
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
    else:
        daily = fs._load_daily()
        active = fs._active_days(sess10, daily)

    gaps = gap_map()
    proven = [dict(r, track="proven_100") for r in d15["proven_100"]]
    dual15 = d15["proven_100"] + d15["champion"]
    dual5 = d5["proven_100"] + d5["champion"]

    print("  building ACC100_MULTI_V2 desk…", flush=True)
    desk = merge_acc100_multi_v2(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=crown_by_risk,
        good_by_risk=good_by_risk,
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active,
    )
    print(f"  desk full-hist n={len(desk)} hit={_agg(desk).get('hit_pct')}", flush=True)

    windows = {
        "3y": pack_window(desk, sess10, START_3Y, END),
        "5y": pack_window(desk, sess10, START_5Y, END),
        "10y": pack_window(desk, sess10, START_10Y, END),
    }

    # coverage notes
    crown_days = sorted({r["day"] for r in (crown_by_risk.get("20.0") or crown_by_risk.get("20") or [])})
    coverage = {
        "dual15_proven_range": (
            min((r["day"] for r in proven), default=None),
            max((r["day"] for r in proven), default=None),
            len(proven),
        ),
        "dual15_champ_n": len(d15["champion"]),
        "dual5_n": len(dual5),
        "good_n": len(good_raw),
        "crown_path_range": (crown_days[0] if crown_days else None, crown_days[-1] if crown_days else None, len(crown_days)),
        "crown_note": "Crown streams only fire where pool crown exists (~2024-05+). Pre-crown years = proven/confirm/good/champ only.",
    }

    payload = {
        "desk": TAG_DESK_V2,
        "status": "HOLDING",
        "end": END,
        "windows": windows,
        "coverage": coverage,
        "elapsed_s": round(time.time() - t0, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ACC100_MULTI_V2_5Y_10Y.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (LEDGER / "ACC100_MULTI_V2_5Y_10Y.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# ACC100_MULTI_V2 — 5y & 10y validation",
        "",
        "**Status:** HOLDING (not live) · desk locked as researched",
        "",
        f"End `{END}` · 5y from `{START_5Y}` · 10y from `{START_10Y}`",
        "",
        "## Results (path-true)",
        "",
        "| Window | Sessions | N | Hit | Perfect | Points | Wins/Losses |",
        "|---|---:|---:|---:|---|---:|---|",
    ]
    for key in ("3y", "5y", "10y"):
        w = windows[key]
        lines.append(
            f"| **{key}** | {w['sessions']} | **{w['n']}** | **{w['hit_pct']}%** | "
            f"{w['perfect']} | {w.get('points')} | {w.get('wins')}/{w.get('losses')} |"
        )

    lines += ["", "## By holding tag (10y slice)", ""]
    lines += ["| Tag | N | Hit | Points |", "|---|---:|---:|---:|"]
    for tag, st in (windows["10y"].get("by_holding_tag") or {}).items():
        lines.append(f"| `{tag}` | {st['n']} | {st['hit_pct']}% | {st['points']} |")

    lines += ["", "## Coverage limits", ""]
    lines.append(
        f"- Dual15 proven: n={coverage['dual15_proven_range'][2]} "
        f"({coverage['dual15_proven_range'][0]}→{coverage['dual15_proven_range'][1]})"
    )
    lines.append(f"- Dual5 n={coverage['dual5_n']} · good n={coverage['good_n']}")
    lines.append(
        f"- Crown path rows: {coverage['crown_path_range'][2]} "
        f"({coverage['crown_path_range'][0]}→{coverage['crown_path_range'][1]})"
    )
    lines.append(f"- {coverage['crown_note']}")

    lines += [
        "",
        "## Verdict",
        "",
    ]
    w5, w10 = windows["5y"], windows["10y"]
    if w5.get("perfect") and w10.get("perfect"):
        lines.append(
            f"**HOLD confirmed** on 5y ({w5['n']}@100%) and 10y ({w10['n']}@100%)."
        )
    elif w5.get("hit_pct") == 100 and w10.get("hit_pct") == 100:
        lines.append("Hit 100% on both windows — check perfect flag / empty.")
    else:
        lines.append(
            f"5y hit={w5.get('hit_pct')}% n={w5.get('n')} · "
            f"10y hit={w10.get('hit_pct')}% n={w10.get('n')} — review losses before promote."
        )
        # list losses
        for label, start in (("5y", START_5Y), ("10y", START_10Y)):
            rs = _clip(desk, start, END)
            losses = [r for r in rs if not r.get("win")]
            if losses:
                lines.append(f"")
                lines.append(f"### Losses on {label} ({len(losses)})")
                for r in losses[:30]:
                    lines.append(
                        f"- {r.get('day')} {r.get('hm')} {r.get('decision')} "
                        f"track={r.get('track')} tag={r.get('holding_tag') or r.get('accurate_tag')} "
                        f"pts={r.get('points')}"
                    )

    lines += [
        "",
        f"Elapsed {payload['elapsed_s']}s · `ACC100_MULTI_V2_5Y_10Y.json`",
        "",
    ]
    md = OUT / "ACC100_MULTI_V2_5Y_10Y.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (LEDGER / "ACC100_MULTI_V2_5Y_10Y.md").write_text("\n".join(lines), encoding="utf-8")
    ra = Path(r"C:\Users\Priyanka\research-and-analysis\feature\final-logic-ledger")
    if ra.is_dir():
        (ra / "ACC100_MULTI_V2_5Y_10Y.md").write_text("\n".join(lines), encoding="utf-8")

    # stamp holding docs pointer
    print("Wrote", md, flush=True)
    print(json.dumps({"windows": {k: {kk: windows[k][kk] for kk in ('n','hit_pct','perfect','points','sessions')} for k in windows}, "elapsed_s": payload["elapsed_s"], "coverage": coverage}, indent=2), flush=True)


if __name__ == "__main__":
    main()
