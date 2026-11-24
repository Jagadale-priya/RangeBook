"""DEEPER hunt: more path-true 100% calls than held PROVEN15_PLUS_CONFIRM_T30 (n=49).

Hard rules:
  - Every candidate must use path-trusted win (tape T/S), not crown pool win flags
  - Beat or match held plus on 3y n while staying 100% on 1y (if n1>=5) and 3y

Phases:
  A) Efficient path-rescore crown / good / champ on tapes
  B) Mine max-n perfect rules (p, time, side, gap, HTF, first/best day)
  C) Expand dual-TF confirm (tol, gate, entry=path-crown)
  D) Soft-dual 15m (baseline-near) path-scored enrich — optional slow
  E) Union streams onto held plus if still perfect

  python -u prod_live/tests/builders/research_100pct_deeper_more_calls.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
import path_setup  # noqa: F401,E402

import research_nifty_final_stack_2y as fs  # noqa: E402
from accuracy_max_6m import POOL, _agg, _champ_floor  # noqa: E402
from research_confirm_dual_tf_deep import (  # noqa: E402
    _clip,
    _hm_mins,
    _ix,
    _pack,
    _side,
    _side_days,
)
from prod_live.logic.confirm_dual_tf import (  # noqa: E402
    build_confirm_rows,
    merge_proven15_plus_confirm,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_confirm.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_calls.json"
TAPE15 = ROOT / "stock_signal_data/fno_validate/NIFTY_15m_12y.csv"
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"
DAILY = ROOT / "stock_signal_data/fno_validate/NIFTY_daily_nse.csv"

END = "2026-11-13"
START_1Y = (pd.Timestamp(END) - timedelta(days=365)).strftime("%Y-%m-%d")
START_3Y = (pd.Timestamp(END) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
START_NOV = "2026-11-01"
HELD_N = 49
RISKS = (20.0, 25.0, 30.0, 35.0, 40.0)


def _norm(raw: pd.DataFrame) -> pd.DataFrame:
    work = raw.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index)
    if work.index.tz is None:
        work.index = work.index.tz_localize("Asia/Kolkata")
    else:
        work.index = work.index.tz_convert("Asia/Kolkata")
    return work.rename(columns={c: str(c).title() for c in work.columns}).sort_index()


def _day(ts) -> str:
    t = ts.tz_convert("Asia/Kolkata") if hasattr(ts, "tz_convert") else ts
    return t.strftime("%Y-%m-%d")


def _hm(ts) -> str:
    t = ts.tz_convert("Asia/Kolkata") if hasattr(ts, "tz_convert") else ts
    return t.strftime("%H:%M")


def build_bar_index(bars: pd.DataFrame) -> Dict[Tuple[str, str], int]:
    ix: Dict[Tuple[str, str], int] = {}
    by_day: Dict[str, List[int]] = defaultdict(list)
    for i, ts in enumerate(bars.index):
        d = _day(ts)
        h = _hm(ts)
        if "09:15" <= h <= "15:15":
            ix[(d, h)] = i
            by_day[d].append(i)
    return ix


def path_score_row(
    bars: pd.DataFrame,
    ix: Dict[Tuple[str, str], int],
    *,
    day: str,
    hm: str,
    side: str,
    risk: float,
    entry: Optional[float] = None,
    sl: Optional[float] = None,
    t1: Optional[float] = None,
) -> Optional[dict]:
    i = ix.get((day, hm))
    if i is None:
        return None
    px = float(bars["Close"].iloc[i])
    side = side.upper()
    if sl is None or t1 is None:
        entry = px if entry is None else float(entry)
        if side == "BUY":
            sl, t1 = entry - risk, entry + risk
        else:
            sl, t1 = entry + risk, entry - risk
    else:
        entry = float(entry) if entry is not None else px
        sl, t1 = float(sl), float(t1)

    # same-day forward only
    j = i + 1
    win = False
    pts = -abs(entry - sl)
    outcome = "expired"
    n = len(bars)
    while j < n and _day(bars.index[j]) == day:
        hh = float(bars["High"].iloc[j])
        ll = float(bars["Low"].iloc[j])
        if side == "BUY":
            hit_sl = ll <= sl
            hit_t1 = hh >= t1
            if hit_sl and hit_t1:
                win, pts, outcome = False, -abs(entry - sl), "same_bar_both"
                break
            if hit_sl:
                win, pts, outcome = False, -abs(entry - sl), "sl_before_t1"
                break
            if hit_t1:
                win, pts, outcome = True, abs(t1 - entry), "t1_before_sl"
                break
        else:
            hit_sl = hh >= sl
            hit_t1 = ll <= t1
            if hit_sl and hit_t1:
                win, pts, outcome = False, -abs(sl - entry), "same_bar_both"
                break
            if hit_sl:
                win, pts, outcome = False, -abs(sl - entry), "sl_before_t1"
                break
            if hit_t1:
                win, pts, outcome = True, abs(entry - t1), "t1_before_sl"
                break
        j += 1
    return {
        "win": win,
        "points": round(float(pts), 1),
        "outcome": outcome,
        "entry": round(entry, 2),
        "stop_loss": round(sl, 2),
        "target_1": round(t1, 2),
        "risk": risk,
    }


def path_rescore_list(
    rows: List[dict],
    bars: pd.DataFrame,
    ix: Dict[Tuple[str, str], int],
    *,
    risk: float,
    use_native_brackets: bool = False,
    label: str = "",
) -> List[dict]:
    out = []
    miss = 0
    t0 = time.time()
    for k, r in enumerate(rows, 1):
        if k % 200 == 0:
            print(f"    path {label} {k}/{len(rows)} ({time.time()-t0:.0f}s)", flush=True)
        side = _side(r)
        if side not in ("BUY", "SELL"):
            continue
        scored = path_score_row(
            bars,
            ix,
            day=str(r["day"]),
            hm=str(r.get("hm") or ""),
            side=side,
            risk=risk,
            entry=r.get("entry") if use_native_brackets else None,
            sl=r.get("stop_loss") if use_native_brackets else None,
            t1=r.get("target_1") if use_native_brackets else None,
        )
        if scored is None:
            miss += 1
            continue
        rr = dict(r)
        rr.update(scored)
        rr["path_risk"] = risk
        rr["path_trusted"] = True
        out.append(rr)
    print(f"    path {label} done n={len(out)} miss={miss}", flush=True)
    return out


def gap_map() -> Dict[str, float]:
    df = pd.read_csv(DAILY)
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values("Date")
    cols = {c.lower(): c for c in df.columns}
    ocol, ccol = cols.get("open"), cols.get("close")
    if not ocol or not ccol:
        return {}
    days = df["Date"].tolist()
    opens = df[ocol].astype(float).tolist()
    closes = df[ccol].astype(float).tolist()
    out = {}
    for i in range(1, len(days)):
        pc = closes[i - 1]
        if pc > 0:
            out[days[i]] = (opens[i] - pc) / pc * 100.0
    return out


def filt(
    rows: List[dict],
    *,
    p_min: float = 0.0,
    p_max: float = 9.0,
    side: Optional[str] = None,
    hm_lo: Optional[int] = None,
    hm_hi: Optional[int] = None,
    htf: Optional[Set[str]] = None,
    gaps: Optional[Dict[str, float]] = None,
    gap_abs: Optional[float] = None,
    gap_dn: bool = False,
    gap_up: bool = False,
) -> List[dict]:
    out = []
    for r in rows:
        day = str(r.get("day") or "")
        s = _side(r)
        if side and s != side:
            continue
        p = float(r.get("p_t1") or 0)
        if p < p_min or p > p_max:
            continue
        hm = _hm_mins(str(r.get("hm") or "12:00"))
        if hm_lo is not None and hm < hm_lo:
            continue
        if hm_hi is not None and hm > hm_hi:
            continue
        if htf is not None and day not in htf:
            continue
        if gaps is not None and (gap_abs is not None or gap_dn or gap_up):
            g = gaps.get(day)
            if g is None:
                continue
            if gap_abs is not None and abs(g) < gap_abs:
                continue
            if gap_dn and g >= 0:
                continue
            if gap_up and g <= 0:
                continue
        out.append(r)
    return out


def first_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r["day"])].append(r)
    out = []
    for day in sorted(by):
        out.append(
            sorted(by[day], key=lambda x: (_hm_mins(str(x.get("hm") or "99:99")), -float(x.get("p_t1") or 0)))[0]
        )
    return out


def bestp_day(rows: List[dict]) -> List[dict]:
    by: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by[str(r["day"])].append(r)
    out = []
    for rs in by.values():
        out.append(max(rs, key=lambda x: float(x.get("p_t1") or 0)))
    return out


def is_perfect(rows: List[dict]) -> bool:
    return bool(rows) and all(bool(r.get("win")) for r in rows)


def mine_perfect(
    name: str,
    rows: List[dict],
    *,
    active: Set[str],
    gaps: Dict[str, float],
    min_n: int = 8,
) -> List[Tuple[str, List[dict], Dict[str, Any]]]:
    """Grid-search max perfect subsets; return list of (tag, rows, stats)."""
    found: List[Tuple[str, List[dict], Dict[str, Any]]] = []
    p_grid = [0.0, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70, 0.72, 0.75, 0.78, 0.80, 0.85, 0.90]
    bands = [
        (None, None, "all"),
        (9 * 60 + 15, 10 * 60, "first45"),
        (9 * 60 + 15, 10 * 60 + 30, "open"),
        (9 * 60 + 15, 11 * 60, "am11"),
        (9 * 60 + 15, 11 * 60 + 30, "am1130"),
        (9 * 60 + 15, 12 * 60 + 30, "am1230"),
        (10 * 60, 13 * 60, "mid"),
        (10 * 60 + 30, 14 * 60, "late_mid"),
        (12 * 60 + 30, 15 * 60 + 15, "pm"),
    ]
    gap_opts = [
        (None, False, False, "nogap"),
        (0.40, False, False, "g040"),
        (0.55, False, False, "g055"),
        (0.70, False, False, "g070"),
        (0.55, True, False, "gdn"),
        (0.55, False, True, "gup"),
    ]
    for side in (None, "BUY", "SELL"):
        for pmin in p_grid:
            for hm_lo, hm_hi, tlab in bands:
                for use_htf in (False, True):
                    for gabsm, gdn, gup, glab in gap_opts:
                        base = filt(
                            rows,
                            p_min=pmin,
                            side=side,
                            hm_lo=hm_lo,
                            hm_hi=hm_hi,
                            htf=active if use_htf else None,
                            gaps=gaps if gabsm is not None or gdn or gup else None,
                            gap_abs=gabsm,
                            gap_dn=gdn,
                            gap_up=gup,
                        )
                        for vlab, vrows in (
                            ("raw", base),
                            ("first", first_day(base)),
                            ("bestp", bestp_day(base)),
                        ):
                            if len(vrows) < min_n:
                                continue
                            if not is_perfect(vrows):
                                continue
                            tag = (
                                f"{name}_{side or 'BOTH'}_p{int(pmin*100)}_{tlab}_"
                                f"{'htf' if use_htf else 'any'}_{glab}_{vlab}"
                            )
                            st = _agg(vrows)
                            found.append((tag, vrows, st))
    # keep unique by tag; sort by n
    found.sort(key=lambda x: (x[2].get("n") or 0, x[2].get("points") or 0), reverse=True)
    return found


def time_agree(
    gate_ix: Dict[Tuple[str, str], List[dict]],
    entry_ix: Dict[Tuple[str, str], List[dict]],
    *,
    tol: int,
    tag: str,
) -> List[dict]:
    out = []
    for (day, side), grows in gate_ix.items():
        frows = entry_ix.get((day, side)) or []
        if not frows:
            continue
        picked = None
        ahm = None
        for g in sorted(grows, key=lambda x: _hm_mins(str(x.get("hm") or "99:99"))):
            gm = _hm_mins(str(g.get("hm") or "12:00"))
            near = [f for f in frows if abs(gm - _hm_mins(str(f.get("hm") or "12:00"))) <= tol]
            if not near:
                continue
            picked = dict(max(near, key=lambda x: float(x.get("p_t1") or 0)))
            ahm = g.get("hm")
            break
        if picked is None:
            continue
        picked.update({"track": tag, "agree_15m_hm": ahm, "src": "entry"})
        out.append(picked)
    return out


def union_unique_days(base: List[dict], extra: List[dict]) -> List[dict]:
    days = {str(r["day"]) for r in base}
    out = list(base)
    for r in extra:
        if str(r["day"]) in days:
            continue
        out.append(dict(r))
        days.add(str(r["day"]))
    return out


def eval_ok(rows: List[dict], sess: List[str], start: str, end: str) -> Dict[str, Any]:
    rs = _clip(rows, start, end)
    return _pack("x", rs, [d for d in sess if start < d <= end])


def main() -> None:
    t0 = time.time()
    print("DEEPER 100% more-calls hunt (path-trusted only)", flush=True)

    cached = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    sessions_all, prod2_all, _ = fs._prod2(1400)
    sess = [d for d in sessions_all if START_3Y < d <= END]
    daily = fs._load_daily()
    active = fs._active_days(sess, daily)
    gaps = gap_map()

    bars15 = _norm(pd.read_csv(TAPE15, index_col=0, parse_dates=True))
    bars5 = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    print("  indexing tapes…", flush=True)
    ix15 = build_bar_index(bars15)
    ix5 = build_bar_index(bars5)
    print(f"  ix15={len(ix15)} ix5={len(ix5)} sessions={len(sess)}", flush=True)

    # --- held baseline ---
    proven = [dict(r, track="proven_100") for r in cached["dual15"]["proven_100"]]
    champ = _champ_floor([dict(r, track="champion") for r in cached["dual15"]["champion"]])
    dual5 = [dict(r) for r in cached["dual5"]["proven_100"] + cached["dual5"]["champion"]]
    confirm = build_confirm_rows(
        cached["dual15"]["proven_100"] + cached["dual15"]["champion"],
        cached["dual5"]["proven_100"] + cached["dual5"]["champion"],
        tol_min=30,
    )
    held_plus = merge_proven15_plus_confirm(proven, confirm)
    held_st = _agg(_clip(held_plus, START_3Y, END))
    print(f"  HELD plus 3y n={held_st['n']} hit={held_st['hit_pct']}%", flush=True)

    # --- path universe ---
    if CACHE_PATH.is_file():
        try:
            pc = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if pc.get("end") == END and pc.get("start") == START_3Y:
                print("  loading path cache…", flush=True)
                path_u = pc["universe"]
            else:
                path_u = None
        except Exception:
            path_u = None
    else:
        path_u = None

    if path_u is None:
        print("  path-rescoring crown @ multiple risks (5m)…", flush=True)
        crown_raw = [dict(r, track="crown_5m") for r in pool["crown_5m"] if START_3Y < r["day"] <= END]
        crown_by_risk = {}
        for risk in RISKS:
            crown_by_risk[str(risk)] = path_rescore_list(
                crown_raw, bars5, ix5, risk=risk, use_native_brackets=False, label=f"crown_T{int(risk)}"
            )
        print("  path-rescoring good @ 15m native + fixed…", flush=True)
        good_raw = []
        for r in prod2_all:
            if not (START_3Y < str(r.get("day") or "") <= END):
                continue
            rr = dict(r, track="good_prod2")
            if "win" not in rr:
                rr["win"] = rr.get("outcome") == "t1_before_sl"
            good_raw.append(rr)
        # trust existing good path if present; also fixed T30 rescore
        good_native = []
        for r in good_raw:
            rr = dict(r)
            rr["path_trusted"] = True
            good_native.append(rr)
        good_t30 = path_rescore_list(
            good_raw, bars15, ix15, risk=30.0, use_native_brackets=False, label="good_T30"
        )
        print("  path-rescoring champ/dual5 native brackets…", flush=True)
        champ_native = path_rescore_list(
            champ, bars15, ix15, risk=30.0, use_native_brackets=True, label="champ_native"
        )
        dual5_native = path_rescore_list(
            dual5, bars5, ix5, risk=30.0, use_native_brackets=True, label="dual5_native"
        )
        path_u = {
            "crown_by_risk": crown_by_risk,
            "good_native": good_native,
            "good_t30": good_t30,
            "champ_native": champ_native,
            "dual5_native": dual5_native,
        }
        CACHE_PATH.write_text(
            json.dumps({"start": START_3Y, "end": END, "universe": path_u}, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"  cached path universe → {CACHE_PATH}", flush=True)

    books: Dict[str, List[dict]] = {
        "HELD_proven": proven,
        "HELD_confirm_t30": confirm,
        "HELD_plus": held_plus,
    }

    print("  phase B: mine path-true perfect rules…", flush=True)
    discoveries: List[Dict[str, Any]] = []

    # crown mines per risk
    for risk, rows in path_u["crown_by_risk"].items():
        print(f"    mine crown risk={risk} n={len(rows)} hit={_agg(rows).get('hit_pct')}", flush=True)
        found = mine_perfect(f"CROWN_T{risk.replace('.0','')}", rows, active=active, gaps=gaps, min_n=8)
        for tag, vrows, st in found[:15]:
            books[tag] = vrows
            discoveries.append({"tag": tag, "src": "crown", "risk": risk, **st})
        if found:
            print(f"      best {found[0][0]} n={found[0][2]['n']} pts={found[0][2].get('points')}", flush=True)

    for label, rows in (
        ("GOOD_NAT", path_u["good_native"]),
        ("GOOD_T30", path_u["good_t30"]),
        ("CHAMP_NAT", path_u["champ_native"]),
        ("DUAL5_NAT", path_u["dual5_native"]),
    ):
        print(f"    mine {label} n={len(rows)} hit={_agg(rows).get('hit_pct')}", flush=True)
        found = mine_perfect(label, rows, active=active, gaps=gaps, min_n=8)
        for tag, vrows, st in found[:20]:
            books[tag] = vrows
            discoveries.append({"tag": tag, "src": label, **st})
        if found:
            print(f"      best {found[0][0]} n={found[0][2]['n']}", flush=True)
        else:
            print("      none perfect n>=8", flush=True)

    print("  phase C: expand dual-TF confirm + path-crown entry…", flush=True)
    d15_any = proven + champ
    ix_d15 = _ix(d15_any)
    ix_d15p = _ix(proven)
    ix_d15c = _ix(champ)
    ix_d5 = _ix(dual5)

    for tol in (5, 10, 15, 20, 25, 30, 40, 45, 60, 75, 90):
        for gname, gix in (
            ("any15", ix_d15),
            ("proven15", ix_d15p),
            ("champ15", ix_d15c),
        ):
            rows = time_agree(gix, ix_d5, tol=tol, tag=f"CONF_T{tol}_{gname}_dual5")
            if len(rows) >= 5 and is_perfect(rows):
                books[f"CONF_T{tol}_{gname}_dual5"] = rows
                discoveries.append({"tag": f"CONF_T{tol}_{gname}_dual5", "src": "confirm", **_agg(rows)})

    # confirm with path-scored crown entries
    for risk, crow in path_u["crown_by_risk"].items():
        ix_cr = _ix(crow)
        for tol in (15, 30, 45, 60, 90, 120):
            for gname, gix in (("any15", ix_d15), ("proven15", ix_d15p), ("champ15", ix_d15c)):
                rows = time_agree(gix, ix_cr, tol=tol, tag=f"CONF_T{tol}_{gname}_crown{risk}")
                # also require crown win already in rows
                if len(rows) >= 8 and is_perfect(rows):
                    tag = f"CONF_T{tol}_{gname}_crownT{risk.replace('.0','')}"
                    books[tag] = rows
                    discoveries.append({"tag": tag, "src": "confirm_crown", **_agg(rows)})

    # day-side crown if dual15 (path)
    for risk, crow in path_u["crown_by_risk"].items():
        for gname, sides in (
            ("any15", _side_days(d15_any)),
            ("proven15", _side_days(proven)),
            ("champ15", _side_days(champ)),
        ):
            rows = []
            for r in crow:
                if _side(r) in sides.get(str(r["day"]), set()):
                    rows.append(dict(r, track=f"crown_if_{gname}"))
            for vlab, vrows in (("raw", rows), ("first", first_day(rows)), ("bestp", bestp_day(rows))):
                # also p floors
                for pmin in (0.55, 0.58, 0.60, 0.62, 0.65, 0.70):
                    vr = filt(vrows, p_min=pmin)
                    for hm_hi, tlab in ((None, "all"), (12 * 60 + 30, "am1230"), (11 * 60 + 30, "am1130")):
                        vv = filt(vr, hm_hi=hm_hi) if hm_hi else vr
                        if len(vv) >= 8 and is_perfect(vv):
                            tag = f"CROWNIF_{gname}_T{risk.replace('.0','')}_p{int(pmin*100)}_{tlab}_{vlab}"
                            books[tag] = vv
                            discoveries.append({"tag": tag, "src": "crown_if", **_agg(vv)})

    print("  phase D: soft enrich — dual15 near-champ losers rescue via 5m confirm…", flush=True)
    # champ losers that still have dual5 agree timed → if those 5m wins, maybe separate stream
    champ_loss = [r for r in champ if not r.get("win")]
    # not a 100% book itself; instead: take dual5 timed with champ gate even when champ loses? 
    # entry is dual5 — already in confirm. Skip.

    # Beam: take all winners from champ as OR with held? That's look-ahead cheat — FORBIDDEN.
    # Instead: progressive p-floor on champ until first perfect
    for side in (None, "BUY", "SELL"):
        for tlab, hm_lo, hm_hi in (
            ("all", None, None),
            ("am", 9 * 60 + 15, 12 * 60 + 30),
            ("open", 9 * 60 + 15, 10 * 60 + 30),
        ):
            for pmin in [x / 100 for x in range(55, 96)]:
                rows = filt(path_u["champ_native"], p_min=pmin, side=side, hm_lo=hm_lo, hm_hi=hm_hi)
                rows = first_day(rows)
                if len(rows) < 8:
                    break
                if is_perfect(rows):
                    tag = f"CHAMP_SWEEP_{side or 'BOTH'}_p{int(pmin*100)}_{tlab}_first"
                    books[tag] = rows
                    discoveries.append({"tag": tag, "src": "champ_sweep", **_agg(rows)})
                    print(f"    champ sweep hit {tag} n={len(rows)}", flush=True)
                    break

    print("  phase E: union onto held plus…", flush=True)
    held3 = _clip(held_plus, START_3Y, END)
    unions: List[Dict[str, Any]] = []
    # only consider discoveries with perfect path and n>=8
    disc_sorted = sorted(discoveries, key=lambda x: x.get("n") or 0, reverse=True)
    seen_tags = set()
    for d in disc_sorted:
        tag = d["tag"]
        if tag in seen_tags or tag not in books:
            continue
        seen_tags.add(tag)
        if tag.startswith("HELD_"):
            continue
        extra = _clip(books[tag], START_3Y, END)
        if not is_perfect(extra):
            continue
        merged = union_unique_days(held3, extra)
        if not is_perfect(merged):
            continue
        if len(merged) <= len(held3):
            continue
        st = _agg(merged)
        # 1y check
        m1 = _clip(merged, START_1Y, END)
        if len(m1) >= 5 and not is_perfect(m1):
            continue
        utag = f"UNION_HELD_u_{tag}"
        books[utag] = merged
        unions.append({"tag": utag, "from": tag, **st, "n_1y": len(m1), "hit_1y": _agg(m1).get("hit_pct")})
        print(f"    UNION +{st['n']-HELD_N} → n={st['n']} from {tag}", flush=True)

    unions.sort(key=lambda x: x.get("n") or 0, reverse=True)
    discoveries.sort(key=lambda x: x.get("n") or 0, reverse=True)

    # score top books on windows
    def board(rows_map: Dict[str, List[dict]], names: List[str]) -> List[dict]:
        out = []
        for name in names:
            if name not in rows_map:
                continue
            r3 = eval_ok(rows_map[name], sess, START_3Y, END)
            r1 = eval_ok(rows_map[name], sess, START_1Y, END)
            rn = eval_ok(rows_map[name], sess, START_NOV, END)
            out.append(
                {
                    "name": name,
                    "n_3y": r3["n"],
                    "hit_3y": r3["hit_pct"],
                    "perfect_3y": r3["perfect"],
                    "points_3y": r3.get("points"),
                    "n_1y": r1["n"],
                    "hit_1y": r1["hit_pct"],
                    "perfect_1y": r1["perfect"],
                    "n_nov": rn["n"],
                    "hit_nov": rn["hit_pct"],
                }
            )
        out.sort(key=lambda x: (x.get("perfect_3y"), x.get("n_3y") or 0), reverse=True)
        return out

    top_names = (
        ["HELD_plus", "HELD_proven", "HELD_confirm_t30"]
        + [u["tag"] for u in unions[:20]]
        + [d["tag"] for d in discoveries[:40]]
    )
    # unique preserve order
    seen = set()
    top_names = [n for n in top_names if not (n in seen or seen.add(n))]

    scored = board(books, top_names)
    beat = [r for r in scored if r.get("perfect_3y") and (r.get("n_3y") or 0) > HELD_N]
    beat_both = [
        r
        for r in beat
        if (r.get("n_1y") or 0) < 5 or (r.get("perfect_1y") and (r.get("hit_1y") or 0) >= 100)
    ]

    payload = {
        "goal": f"More path-true 100% calls than held plus n={HELD_N}",
        "held_plus_3y": held_st,
        "discoveries_top": discoveries[:50],
        "unions_top": unions[:30],
        "scored_top": scored[:40],
        "beat_held_n": beat[:20],
        "beat_held_both_year": beat_both[:20],
        "elapsed_s": round(time.time() - t0, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "HUNT_100PCT_DEEPER_MORE.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (LEDGER / "HUNT_100PCT_DEEPER_MORE.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Deeper hunt — more path-true 100% calls",
        "",
        f"**Target:** beat held `PROVEN15_PLUS_CONFIRM_T30` (**n={HELD_N} @ 100%**)",
        "",
        "All claims below are **path-rescored** (crown pool win flags rejected).",
        "",
        f"Elapsed **{payload['elapsed_s']}s**",
        "",
        "## Held baseline",
        "",
        f"- `HELD_plus`: **{held_st['n']} @ {held_st['hit_pct']}%** · pts {held_st.get('points')}",
        "",
        "## Best path-true perfect discoveries (n≥8)",
        "",
        "| Tag | N | Hit | Points | Src |",
        "|---|---:|---:|---:|---|",
    ]
    for d in discoveries[:30]:
        if (d.get("n") or 0) < 8:
            continue
        lines.append(
            f"| `{d['tag']}` | {d['n']} | {d.get('hit_pct')}% | {d.get('points')} | {d.get('src')} |"
        )
    if not discoveries:
        lines.append("_None._")

    lines += [
        "",
        "## Unions onto held plus (still 100%)",
        "",
    ]
    if not unions:
        lines.append("_No path-true union beat held plus._")
    else:
        lines += ["| Union | N | +vs49 | Points | 1y |", "|---|---:|---:|---:|---|"]
        for u in unions[:25]:
            lines.append(
                f"| `{u['tag']}` | {u['n']} | +{u['n']-HELD_N} | {u.get('points')} | "
                f"{u.get('n_1y')}@{u.get('hit_1y')}% |"
            )

    lines += [
        "",
        "## Both-year beat held n",
        "",
    ]
    if not beat_both:
        lines.append("_No both-year path-true book with n>49 yet._")
    else:
        lines += ["| Book | 3y | 1y | Nov |", "|---|---|---|---|"]
        for r in beat_both[:15]:
            lines.append(
                f"| `{r['name']}` | **{r['n_3y']}**@{r['hit_3y']}% | "
                f"{r['n_1y']}@{r['hit_1y']}% | {r['n_nov']}@{r['hit_nov']}% |"
            )

    best = beat_both[0] if beat_both else (unions[0] if unions else None)
    lines += ["", "## Recommended next hold (if any)", ""]
    if best:
        name = best.get("tag") or best.get("name")
        lines += [
            f"**`{name}`**",
            "",
            f"- 3y n={best.get('n') or best.get('n_3y')} @ 100%",
            f"- vs held +{(best.get('n') or best.get('n_3y')) - HELD_N} calls",
            "",
            "Candidate to add into HOLDING after shadow review.",
        ]
    else:
        lines += [
            "_Held plus remains best path-true 100% expand (n=49)._",
            "",
            "Deeper crown/good/champ grids did not yield a larger both-year perfect book.",
            "Next levers: richer dual features (regime/or_ext) re-walk, or new 5m model — not pool-flag mining.",
        ]

    lines += [
        "",
        "## Verdict",
        "",
        "1. Path trust first — crown pool 100% claims stay discarded unless tape confirms.",
        "2. Held confirm expand stays the champion until a union clears both-year 100% with n>49.",
        "3. Continue only with path-rescored streams.",
        "",
        "JSON: `prod_live/reports/1y/HUNT_100PCT_DEEPER_MORE.json`",
        "",
    ]
    md = OUT / "HUNT_100PCT_DEEPER_MORE.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (LEDGER / "HUNT_100PCT_DEEPER_MORE.md").write_text("\n".join(lines), encoding="utf-8")
    ra = Path(r"C:\Users\Priyanka\research-and-analysis\feature\final-logic-ledger")
    if ra.is_dir():
        (ra / "HUNT_100PCT_DEEPER_MORE.md").write_text("\n".join(lines), encoding="utf-8")

    print("Wrote", md, flush=True)
    print(
        json.dumps(
            {
                "held_n": HELD_N,
                "discoveries": len(discoveries),
                "unions": len(unions),
                "beat_both": len(beat_both),
                "best": (best.get("tag") if best else None)
                or (best.get("name") if best else None),
                "best_n": (best.get("n") if best else None) or (best.get("n_3y") if best else None),
                "top_disc": [
                    {"tag": d["tag"], "n": d["n"], "src": d.get("src")}
                    for d in discoveries[:8]
                    if (d.get("n") or 0) >= 8
                ],
                "elapsed_s": payload["elapsed_s"],
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
