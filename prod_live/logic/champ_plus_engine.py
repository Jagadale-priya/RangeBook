"""CHAMP_PLUS live ticket-fill engine — fires new days without blockers.

Same logic family as research CHAMP_PLUS T30/SL30 Cap6 (final):
  champion-floor seed · research candidate streams · day cap 6 same-side
  · prefer high p_t1 · path-score ±30 when 5m bars exist.

Held 5y book stays intact. New session calls append to a live ledger so
tomorrow can fire when logic satisfies — other desks never block.
"""
from __future__ import annotations

import json
import threading
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
_HOLD = Path(__file__).resolve().parents[1] / "holding_accurate" / "champion_plus"
_LIVE_LEDGER = _HOLD / "live_session_calls.json"
_HELD_5Y = _HOLD / "t30_sl30_5y_calls.json"

T1_PTS = 30.0
SL_PTS = 30.0
CAP = 6
# Locked 1y seed floor from CHAMP Cap6 research (informational; live day fill does not
# re-score full 1y on every tick — day cap + p gates are the live fire rules).
FLOOR_1Y = 99.42

_LOCK = threading.Lock()

LEDGER = ROOT / "stock_signal_data/fno_validate/research"
POOL = LEDGER / "_cache_nifty_final_stack_5y_pools.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_XY = LEDGER / "_cache_dual10m_xy_research.json"
PACKS = LEDGER / "nifty_side_models_10m_research" / "dual10m_packs.joblib"
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"

_PACKS_CACHE = None
_XY_CACHE = None
_POOL_CACHE = None
_PATH_CACHE = None
_DUAL_CACHE = None


def _side(r: dict) -> str:
    return str(r.get("decision") or r.get("side") or "").upper()


def call_key(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day") or ""), _side(r), str(r.get("hm") or ""))


def levels(entry: float, side: str) -> Dict[str, float]:
    side = side.upper()
    if side == "BUY":
        return {
            "entry": round(float(entry), 2),
            "stop_loss": round(float(entry) - SL_PTS, 2),
            "target_1": round(float(entry) + T1_PTS, 2),
            "t1_pts": T1_PTS,
            "sl_pts": SL_PTS,
        }
    return {
        "entry": round(float(entry), 2),
        "stop_loss": round(float(entry) + SL_PTS, 2),
        "target_1": round(float(entry) - T1_PTS, 2),
        "t1_pts": T1_PTS,
        "sl_pts": SL_PTS,
    }


def _champ_floor_ok(r: dict) -> bool:
    side = _side(r)
    p = float(r.get("p_t1") or 0)
    if side == "BUY":
        return p >= 0.55
    if side == "SELL":
        return p >= 0.58
    return False


def _normalize_cand(r: dict, *, track: str = "") -> Optional[dict]:
    side = _side(r)
    day = str(r.get("day") or "")[:10]
    hm = str(r.get("hm") or "")
    if side not in ("BUY", "SELL") or not day or not hm:
        return None
    entry = r.get("entry")
    if entry is None:
        entry = r.get("close") or r.get("px") or r.get("price")
    try:
        entry_f = float(entry) if entry is not None else None
    except (TypeError, ValueError):
        entry_f = None
    rr = {k: v for k, v in r.items() if k != "x"}
    rr["day"] = day
    rr["hm"] = hm
    rr["decision"] = side
    rr["side"] = side
    if track:
        rr["track"] = track
    elif not rr.get("track"):
        rr["track"] = "session"
    if entry_f is not None:
        rr.update(levels(entry_f, side))
    return rr


def merge_cap(a: Sequence[dict], b: Sequence[dict], cap: int = CAP) -> List[dict]:
    out = [dict(r) for r in a]
    by_day: Dict[str, List[dict]] = defaultdict(list)
    for r in out:
        by_day[str(r.get("day") or "")].append(r)
    for r in b:
        day = str(r.get("day") or "")
        existing = by_day.get(day, [])
        if len(existing) >= cap:
            continue
        if existing and _side(existing[0]) != _side(r):
            continue
        k = call_key(r)
        if any(call_key(x) == k for x in existing):
            continue
        rr = dict(r)
        out.append(rr)
        by_day[day].append(rr)
    return out


def _read_json_list(path: Path) -> List[dict]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("calls") or raw.get("rows") or []
    return list(raw or [])


def load_held_raw() -> List[dict]:
    return _read_json_list(_HELD_5Y)


def load_live_ledger() -> List[dict]:
    return _read_json_list(_LIVE_LEDGER)


def save_live_ledger(rows: List[dict]) -> None:
    _HOLD.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "desk": "CHAMP_PLUS_T30SL30_CAP6",
        "brackets": {"target": T1_PTS, "sl": SL_PTS},
        "cap": CAP,
        "calls": rows,
    }
    _LIVE_LEDGER.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def book_union(held: Sequence[dict], live: Sequence[dict]) -> List[dict]:
    """Held first; live adds only new keys (never drops held)."""
    seen = {call_key(r) for r in held}
    out = [dict(r) for r in held]
    for r in live:
        k = call_key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(dict(r))
    return out


def _load_cache_candidates_for_day(day: str) -> List[dict]:
    """Research caches → same candidate family as CHAMP fill (day slice)."""
    out: List[dict] = []
    seen = set()

    def add(rows: Iterable[dict], track: str, *, require_floor: bool = False):
        for r in rows or []:
            if str(r.get("day") or "")[:10] != day:
                continue
            if require_floor and not _champ_floor_ok(r):
                continue
            rr = _normalize_cand(r, track=track)
            if not rr:
                continue
            k = call_key(rr)
            if k in seen:
                continue
            seen.add(k)
            out.append(rr)

    global _POOL_CACHE, _PATH_CACHE, _DUAL_CACHE
    try:
        if POOL.exists():
            if _POOL_CACHE is None:
                _POOL_CACHE = json.loads(POOL.read_text(encoding="utf-8"))
            pool = _POOL_CACHE
            add(pool.get("champion") or [], "champion", require_floor=True)
            add(pool.get("proven_100") or [], "proven_research")
            for r in pool.get("crown_5m") or []:
                # Causal: p gate only — never filter on historical win (live cannot know).
                if float(r.get("p_t1") or 0) < 0.58:
                    continue
                add([r], "crown_research")
    except Exception:
        pass

    try:
        if CACHE_PATH.exists():
            if _PATH_CACHE is None:
                _PATH_CACHE = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            path_u = _PATH_CACHE
            for rk, rows in (path_u.get("good_by_risk") or {}).items():
                if str(rk).startswith("_"):
                    continue
                add(rows or [], "good_prod2")
            for rk, rows in (path_u.get("crown_by_risk") or {}).items():
                if str(rk).startswith("_"):
                    continue
                risk = 99.0
                try:
                    if str(rk)[0].isdigit():
                        risk = float(str(rk).replace(".0", "") or 99)
                except Exception:
                    risk = 99.0
                if risk > 30:
                    continue
                for r in rows or []:
                    # Causal: p gate only — never require historical win.
                    if float(r.get("p_t1") or 0) < 0.55:
                        continue
                    add([r], "crown_research")
    except Exception:
        pass

    try:
        if CACHE_DUAL.exists():
            if _DUAL_CACHE is None:
                _DUAL_CACHE = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
            dual = _DUAL_CACHE
            add((dual.get("dual15") or {}).get("champion") or [], "champion", require_floor=True)
            add((dual.get("dual15") or {}).get("proven_100") or [], "proven_research")
            for r in (dual.get("dual5") or {}).get("champion") or []:
                # Causal: p≥0.62 only (no win filter).
                if float(r.get("p_t1") or 0) >= 0.62:
                    add([r], "dual5_research")
    except Exception:
        pass

    # dual10m packs (cached — never reload joblib per day)
    try:
        if CACHE_XY.exists() and PACKS.exists():
            import joblib
            import numpy as np

            global _PACKS_CACHE, _XY_CACHE
            if _PACKS_CACHE is None:
                _PACKS_CACHE = joblib.load(PACKS)
            if _XY_CACHE is None:
                _XY_CACHE = json.loads(CACHE_XY.read_text(encoding="utf-8"))
            packs = _PACKS_CACHE
            for r in _XY_CACHE.get("tickets") or []:
                if str(r.get("day") or "")[:10] != day:
                    continue
                side = str(r.get("decision") or "").upper()
                pack = packs.get(side) or {}
                if not pack.get("available") or not r.get("x"):
                    continue
                X = np.asarray([r["x"]], dtype=float)
                raw = float(pack["base"].predict_proba(X)[0, 1])
                p = float(np.clip(pack["iso"].transform([raw])[0], 0.05, 0.95))
                rr = {k: v for k, v in r.items() if k != "x"}
                rr["p_t1"] = round(p, 4)
                add([rr], "dual10m")
    except Exception:
        pass

    return out


def path_score_one(
    bars,
    ix: Dict[Tuple[str, str], int],
    day: str,
    hm: str,
    side: str,
) -> Optional[dict]:
    """5m path T30/SL30 — same as research score_one."""
    try:
        from research_100pct_deeper_more_calls import _day
    except Exception:
        def _day(ts):  # type: ignore
            return str(ts)[:10]

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
        sl, t1 = px - SL_PTS, px + T1_PTS
    else:
        sl, t1 = px + SL_PTS, px - T1_PTS
    j = i + 1
    n = len(bars)
    win, pts, outcome = False, -SL_PTS, "expired"
    while j < n and _day(bars.index[j]) == day:
        hh = float(bars["High"].iloc[j])
        ll = float(bars["Low"].iloc[j])
        if side == "BUY":
            hit_sl, hit_t1 = ll <= sl, hh >= t1
        else:
            hit_sl, hit_t1 = hh >= sl, ll <= t1
        if hit_sl and hit_t1:
            win, pts, outcome = False, -SL_PTS, "same_bar_both"
            break
        if hit_sl:
            win, pts, outcome = False, -SL_PTS, "sl_before_t1"
            break
        if hit_t1:
            win, pts, outcome = True, T1_PTS, "t1_before_sl"
            break
        j += 1
    return {
        "win": win,
        "points": round(float(pts), 1),
        "outcome": outcome,
        **levels(px, side),
    }


_BARS_CACHE = None
_IX_CACHE = None


def _try_load_bars_index():
    global _BARS_CACHE, _IX_CACHE
    if _BARS_CACHE is not None and _IX_CACHE is not None:
        return _BARS_CACHE, _IX_CACHE
    try:
        import pandas as pd
        from research_100pct_deeper_more_calls import _norm, build_bar_index

        if not TAPE5.exists():
            return None, None
        bars = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
        hm = bars.index.strftime("%H:%M")
        bars = bars[(hm >= "09:15") & (hm <= "15:30")]
        _BARS_CACHE = bars
        _IX_CACHE = build_bar_index(bars)
        return _BARS_CACHE, _IX_CACHE
    except Exception:
        return None, None


def score_candidates(cands: List[dict]) -> List[dict]:
    bars, ix = _try_load_bars_index()
    out = []
    for r in cands:
        rr = dict(r)
        # Live session / afternoon thrust already carry tape entry — never replace
        # with stale research TAPE5 (caused ghost prices like 23946 on Nov16).
        keep_live_px = bool(
            rr.get("afternoon_thrust")
            or rr.get("morning_strong_thrust")
            or str(rr.get("source") or "")
            in (
                "session_dual",
                "nifty_afternoon_thrust_confident",
                "nifty_morning_strong_thrust_confident",
            )
        ) and rr.get("entry") is not None
        if bars is not None and ix is not None:
            s = path_score_one(bars, ix, rr["day"], rr["hm"], _side(rr))
            if s:
                if keep_live_px:
                    live_levels = levels(float(rr["entry"]), _side(rr))
                    rr.update(live_levels)
                    rr["outcome"] = "open_pending"
                    rr["win"] = None
                else:
                    rr.update(s)
            elif rr.get("entry") is None:
                continue
            else:
                rr.setdefault("outcome", "open_pending")
                rr.setdefault("win", None)
        else:
            if rr.get("entry") is None:
                continue
            rr.setdefault("outcome", "open_pending")
            rr.setdefault("win", None)
        out.append(rr)
    return out


def fill_day(
    day: str,
    cur: List[dict],
    cands: List[dict],
    *,
    prefer_wins: bool = False,
) -> Tuple[List[dict], List[dict]]:
    """Add candidates into day book up to Cap6 same-side. Returns (book, added).

    Causal / live-identical: rank by p_t1 only. Never prefer historical wins
    (live cannot know outcome). No accuracy-floor blocker.
    `prefer_wins` kept for API compat but ignored.
    """
    day = str(day)[:10]
    cur = [dict(r) for r in cur]
    added: List[dict] = []
    opts = [
        r
        for r in cands
        if str(r.get("day") or "") == day and _side(r) in ("BUY", "SELL")
    ]
    # Causal rank: p_t1 only (same as live session — no win lookahead).
    opts = sorted(opts, key=lambda x: float(x.get("p_t1") or 0), reverse=True)

    for r in opts:
        trial = merge_cap(cur, [r], CAP)
        if len(trial) <= len(cur):
            continue
        # never block due to other desks — only day cap / same-side
        cur = trial
        added.append(dict(r))
        day_rows = [x for x in cur if str(x.get("day") or "") == day]
        if len(day_rows) >= CAP:
            break
    return cur, added


def session_candidate_from_dual(
    dual_call: Optional[dict],
    *,
    day: Optional[str] = None,
    hm: Optional[str] = None,
    entry: Optional[float] = None,
) -> Optional[dict]:
    """Turn current session dual/stack call into a CHAMP fill candidate."""
    if not isinstance(dual_call, dict):
        return None
    side = str(dual_call.get("decision") or "").upper()
    if side not in ("BUY", "SELL"):
        return None
    d = day or str(dual_call.get("day") or "")[:10] or date.today().isoformat()
    h = hm or str(dual_call.get("hm") or dual_call.get("time") or "")
    if not h:
        now = datetime.now()
        # round down to 5m
        m = (now.minute // 5) * 5
        h = f"{now.hour:02d}:{m:02d}"
    px = entry
    if px is None:
        px = dual_call.get("entry") or dual_call.get("price") or dual_call.get("ltp")
    track = str(
        dual_call.get("track")
        or dual_call.get("source")
        or dual_call.get("channel")
        or "session"
    )
    rr = {
        "day": d,
        "hm": h,
        "decision": side,
        "side": side,
        "p_t1": float(dual_call.get("p_t1") or dual_call.get("p") or 0.6),
        "track": track if track else "session",
        "source": str(dual_call.get("source") or "session_dual"),
    }
    if dual_call.get("afternoon_thrust"):
        rr["afternoon_thrust"] = True
        rr["track"] = str(dual_call.get("track") or "confident")
        rr["source"] = str(
            dual_call.get("source") or "nifty_afternoon_thrust_confident"
        )
        if dual_call.get("accuracy_label"):
            rr["accuracy_label"] = dual_call.get("accuracy_label")
    if dual_call.get("morning_strong_thrust"):
        rr["morning_strong_thrust"] = True
        rr["track"] = str(dual_call.get("track") or "confident")
        rr["source"] = str(
            dual_call.get("source") or "nifty_morning_strong_thrust_confident"
        )
        if dual_call.get("accuracy_label"):
            rr["accuracy_label"] = dual_call.get("accuracy_label")
    if px is not None:
        try:
            rr.update(levels(float(px), side))
        except (TypeError, ValueError):
            return None
    return _normalize_cand(rr, track=rr["track"])


def ensure_session_day(
    day: Optional[str] = None,
    *,
    session_candidates: Optional[Sequence[dict]] = None,
    dual_call: Optional[dict] = None,
    hm: Optional[str] = None,
    entry: Optional[float] = None,
) -> Dict[str, Any]:
    """Ensure CHAMP_PLUS book for `day` includes any new live fills.

    Never blocks: only Cap6 / same-side limits new adds.
    Held history is never removed.
    """
    day = (day or date.today().isoformat())[:10]
    with _LOCK:
        held = load_held_raw()
        live = load_live_ledger()
        book = book_union(held, live)

        cands: List[dict] = []
        cands.extend(_load_cache_candidates_for_day(day))
        for r in session_candidates or []:
            rr = _normalize_cand(r)
            if rr:
                cands.append(rr)
        sc = session_candidate_from_dual(
            dual_call, day=day, hm=hm, entry=entry
        )
        if sc:
            cands.append(sc)

        # dedupe cand keys
        seen = set()
        uniq = []
        for r in cands:
            k = call_key(r)
            if k in seen:
                continue
            seen.add(k)
            uniq.append(r)

        scored = score_candidates(uniq)
        # Causal gates only: champion p floor · side · entry. No win / no accuracy floor.
        gated = []
        for r in scored:
            if r.get("track") == "champion" and not _champ_floor_ok(r):
                continue
            if _side(r) not in ("BUY", "SELL"):
                continue
            if r.get("entry") is None:
                continue
            gated.append(r)

        before_keys = {call_key(r) for r in book if str(r.get("day") or "") == day}
        filled, added = fill_day(day, book, gated, prefer_wins=False)
        # persist only truly new live keys (not already in held)
        held_keys = {call_key(r) for r in held}
        new_live = []
        for r in added:
            k = call_key(r)
            if k in held_keys:
                continue
            rr = dict(r)
            rr["live_fire"] = True
            rr["fired_at"] = datetime.now().isoformat(timespec="seconds")
            new_live.append(rr)

        if new_live:
            live2 = book_union(live, new_live)
            # keep ledger lean: only live-fired rows
            live_only = [
                r
                for r in live2
                if call_key(r) not in held_keys
            ]
            save_live_ledger(live_only)

        day_calls = [
            r for r in filled if str(r.get("day") or "") == day
        ]
        after_keys = {call_key(r) for r in day_calls}
        return {
            "day": day,
            "n_day": len(day_calls),
            "n_added": len(after_keys - before_keys),
            "added": [r for r in day_calls if call_key(r) in (after_keys - before_keys)],
            "day_calls": day_calls,
            "blocked": False,
            "cap": CAP,
            "brackets": {"target": T1_PTS, "sl": SL_PTS},
            "candidates_scored": len(scored),
            "candidates_gated": len(gated),
        }


def load_full_book_raw() -> List[dict]:
    return book_union(load_held_raw(), load_live_ledger())
