"""Deep research: map 3 options PDFs → listed NIFTY ticket policies.

Sources (research only — does not change prod):
  1. Zerodha Varsity Module 5 — Options Theory for Professional Trading
     https://zerodha-common.s3.ap-south-1.amazonaws.com/Varsity/Modules/Module%205_Options-Theory-for-Professional-Trading.pdf
  2. Cboe Advanced Options Trading Strategies
     https://cdn.cboe.com/resources/options/Advanced_Opts_Trading_Strategies.pdf
  3. IISc Option Pricing notes (Ghosh)
     https://math.iisc.ac.in/~ifcam/Option%20price_Notes.pdf

PDF → index-ticket gates (no live option chain required):
  Varsity Ch7 direction  — long-call/short-put only when bullish stack (BUY);
                           long-put/short-call only when bearish (SELL)
  Varsity Ch8 moneyness  — prefer ATM-like OR extension; skip deep chase
  Varsity Ch9–11 delta   — delta_proxy (vwap+body+confirms) ≥ ~0.45–0.55
  Varsity Ch14 theta     — avoid late-session entries (premium time crush)
  Varsity Ch15–18 vol    — high realized/ATR days need higher model bar or skip
  Cboe TREND debit       — directional ticket when TREND/VOLATILE + floor
  Cboe RANGE butterfly   — RANGE → only tight ATM + higher score (else skip)
  Cboe calendar settle   — skip first bars after OR (short-leg noise)
  Cboe mild CSP          — mild bullish: allow second ticket only with ATM Δ
  IISc σ / Greeks        — ATR-frac vol cap; early-drop as bad-delta cut
  IISc parity proxy      — HTF bias agrees with decision side

  python -u tools/research/research_pdf_deep_algo.py --sessions 126 --kite-only
  python -u tools/research/research_pdf_deep_algo.py --sessions 126 --from-cache
  python -u tools/research/research_pdf_deep_algo.py --sessions 30 --skip-last-sessions 30 --kite-only
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

warnings.filterwarnings("ignore", category=DeprecationWarning)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fno_indications
import fno_model
import fno_session_replay

OUT_DIR = ROOT / "stock_signal_data" / "fno_validate" / "research"

PDF_MAP = {
    "varsity": (
        "https://zerodha-common.s3.ap-south-1.amazonaws.com/Varsity/Modules/"
        "Module%205_Options-Theory-for-Professional-Trading.pdf"
    ),
    "cboe": "https://cdn.cboe.com/resources/options/Advanced_Opts_Trading_Strategies.pdf",
    "iisc": "https://math.iisc.ac.in/~ifcam/Option%20price_Notes.pdf",
}


def _paths(sessions: int, skip_last: int = 0) -> Tuple[Path, Path]:
    tag = f"pdfdeep_{sessions}s" + (f"_skip{skip_last}" if skip_last else "")
    return OUT_DIR / f"{tag}_candidates.json", OUT_DIR / f"{tag}_report.json"


def _norm(raw: pd.DataFrame) -> pd.DataFrame:
    work = raw.copy()
    if work.index.tz is None:
        work.index = work.index.tz_localize("Asia/Kolkata")
    else:
        work.index = work.index.tz_convert("Asia/Kolkata")
    work = work.rename(columns={c: str(c).title() for c in work.columns})
    return fno_session_replay._norm(work)


def _load_bars(lookback_days: int, *, kite_only: bool = False) -> pd.DataFrame:
    need = max(lookback_days + 10, 55)
    try:
        import kite_data

        raw, err = kite_data.fetch_historical_candles("NIFTY", "15minute", days=min(need, 200))
        if raw is not None and len(raw):
            print(f"kite 15m bars {len(raw)} span_days={need}", flush=True)
            return _norm(raw)
        print(f"kite miss ({err})", flush=True)
        if kite_only:
            raise SystemExit(f"kite-only required but fetch failed: {err}")
    except SystemExit:
        raise
    except Exception as exc:
        print(f"kite fail ({exc})", flush=True)
        if kite_only:
            raise SystemExit(f"kite-only required but fetch failed: {exc}")
    if kite_only:
        raise SystemExit("kite-only required but no bars returned")
    for name in ("NIFTY_15m_12y.csv", "NIFTY_15m_5y.csv"):
        path = ROOT / "stock_signal_data" / "fno_validate" / name
        if not path.is_file():
            path = ROOT / "stock_signal_data" / "fno_validate" / "archive" / name
        if path.is_file():
            raw = pd.read_csv(path, index_col=0, parse_dates=True)
            print(f"csv fallback {path.name} bars {len(raw)}", flush=True)
            return _norm(raw)
    raise SystemExit("no NIFTY 15m bars")


def _daily_ohlc(bars: pd.DataFrame) -> pd.DataFrame:
    g = bars.groupby(bars.index.map(lambda t: t.date()))
    return pd.DataFrame({
        "High": g["High"].max(),
        "Low": g["Low"].min(),
        "Close": g["Close"].last(),
        "Open": g["Open"].first(),
    }).sort_index()


def _cpr(daily: pd.DataFrame, day) -> dict:
    prior = daily[daily.index < day]
    if prior.empty:
        return {"available": False, "items": [], "alerts": []}
    row = prior.iloc[-1]
    reading = fno_indications.cpr(float(row["High"]), float(row["Low"]), float(row["Close"]))
    return {
        "available": True,
        "items": [{
            "key": "cpr", "kind": reading["kind"], "width_pct": reading["width_pct"],
            "available": True, "label": "CPR", "value": reading["kind"], "lean": None,
        }],
        "alerts": [],
        "reading": reading,
    }


def _window(bars: pd.DataFrame, i: int, ts) -> pd.DataFrame:
    left = int(bars.index.searchsorted(ts - pd.Timedelta(days=12)))
    return bars.iloc[left : i + 1]


def _points(decision, entry, stop, target, outcome) -> float:
    risk = abs(float(entry) - float(stop))
    reward = abs(float(target) - float(entry))
    if outcome == "t1_before_sl":
        return round(reward, 1)
    if outcome in ("sl_before_t1", "same_bar_both"):
        return round(-risk, 1)
    return 0.0


def _path_mae(decision, entry, stop, target, future):
    favor = against = 0.0
    for _, row in future.iterrows():
        hi, lo = float(row["High"]), float(row["Low"])
        if decision == "SELL":
            favor = max(favor, entry - lo)
            against = max(against, hi - entry)
            if hi >= stop or lo <= target:
                break
        else:
            favor = max(favor, hi - entry)
            against = max(against, entry - lo)
            if lo <= stop or hi >= target:
                break
    return favor, against


def _early(favor, against, risk, outcome, pts):
    if favor < 8 and against >= 0.30 * risk and outcome != "t1_before_sl":
        return "early_drop", -round(min(against, 0.35 * risk), 1)
    return outcome, pts


def _realized_vol_frac(window: pd.DataFrame, n: int = 20) -> float:
    """IISc/Varsity historical-vol proxy: std of recent 15m log returns × √bars."""
    close = window["Close"].astype(float)
    if len(close) < n + 2:
        return 0.0
    rets = close.pct_change().dropna().iloc[-n:]
    if rets.empty:
        return 0.0
    return float(rets.std() * (n ** 0.5))


def collect(bars: pd.DataFrame, pack: dict, days: List) -> List[dict]:
    out: List[dict] = []
    by_day: Dict[Any, List[int]] = {}
    for i, t in enumerate(bars.index):
        by_day.setdefault(t.date(), []).append(i)
    daily = _daily_ohlc(bars)

    for n, day in enumerate(days, 1):
        if n == 1 or n % 5 == 0 or n == len(days):
            print(f"  walk {n}/{len(days)} {day} cands {len(out)}", flush=True)
        day_idx = by_day.get(day) or []
        if len(day_idx) < 8:
            continue
        inds = _cpr(daily, day)
        box = fno_session_replay.session_day_range(bars.iloc[day_idx], lookback=2)
        or_hi = float(bars["High"].astype(float).iloc[day_idx[0]])
        or_lo = float(bars["Low"].astype(float).iloc[day_idx[0]])
        ticket = None
        resolve_i = -1

        for pos, i in enumerate(day_idx):
            ts = bars.index[i]
            if (ts.hour, ts.minute) < (9, 15) or (ts.hour, ts.minute) >= (15, 15):
                continue
            close = float(bars["Close"].astype(float).iloc[i])
            if not (close > or_hi or close < or_lo):
                continue
            if ticket is not None and i <= resolve_i:
                continue
            if ticket is not None and i > resolve_i:
                ticket = None

            window = _window(bars, i, ts)
            snap = fno_session_replay.score_snapshot(
                window,
                symbol="NIFTY",
                day_range=box,
                model_pack=pack,
                primary=True,
                asof=ts,
                session_ticket=None,
                indications=inds,
            )
            head = snap.get("fno_head") or {}
            feat = head.get("features") or {}
            side = float(feat.get("side") or head.get("side") or 0)
            p = float(head.get("p_t1") or 0)
            if side == 0 or p < 0.48:
                continue
            issued = snap.get("issued_ticket")
            entry = float(window["Close"].astype(float).iloc[-1])
            sl_pts, t1_pts, _, atr = fno_model.clip_for("NIFTY", window)
            if side > 0:
                decision, stop, target = "BUY", entry - sl_pts, entry + t1_pts
            else:
                decision, stop, target = "SELL", entry + sl_pts, entry - t1_pts
            if issued:
                decision = str(issued.get("decision") or decision)
                entry = float(issued.get("entry") or entry)
                stop = float(issued.get("stop_loss") or stop)
                target = float(issued.get("target_1") or target)

            future = bars.iloc[day_idx[pos + 1] : day_idx[-1] + 1]
            fake = {
                "decision": decision, "entry": entry, "stop_loss": stop,
                "target_1": target, "taken_at": snap.get("decision_asof") or str(ts),
            }
            outcome = fno_session_replay._close_issued_ticket(fake, future, symbol="NIFTY")
            favor, against = _path_mae(decision, entry, stop, target, future)
            pts = _points(decision, entry, stop, target, outcome)
            risk = abs(entry - stop)
            resolve_i_bar = day_idx[-1]
            for j in day_idx[pos + 1 :]:
                row = bars.iloc[j]
                hi, lo = float(row["High"]), float(row["Low"])
                hit = (hi >= stop or lo <= target) if decision == "SELL" else (lo <= stop or hi >= target)
                if hit:
                    resolve_i_bar = j
                    break

            regime = (head.get("regime") or {})
            if isinstance(regime, dict):
                regime_name = str(regime.get("name") or "")
            else:
                regime_name = str(regime or "")

            vwap = float(feat.get("vwap_sess") or 0)
            body = float(feat.get("body_frac") or 0)
            confirms = float(feat.get("confirms") or 0)
            or_ext = float(feat.get("or_ext") or 0)
            if decision == "BUY":
                delta_proxy = min(
                    1.0,
                    max(0.0, 0.35 * max(vwap, 0) + 0.35 * max(body, 0) + 0.15 * min(confirms, 3) / 3 + 0.15),
                )
            else:
                delta_proxy = min(
                    1.0,
                    max(0.0, 0.35 * max(-vwap, 0) + 0.35 * max(-body, 0) + 0.15 * min(confirms, 3) / 3 + 0.15),
                )

            atm_like = 0.08 <= or_ext <= 0.55
            chase = or_ext > 0.55
            shallow = 0.0 < or_ext < 0.08
            atr_frac = float(atr) / entry if entry else 0.0
            rv = _realized_vol_frac(window, 20)
            hour = ts.hour + ts.minute / 60.0
            htf = float(feat.get("htf_bias_num") or 0)
            direction_ok = (
                (decision == "BUY" and vwap >= 0 and htf >= 0)
                or (decision == "SELL" and vwap <= 0 and htf <= 0)
            )
            soft_direction = (
                (decision == "BUY" and vwap >= 0)
                or (decision == "SELL" and vwap <= 0)
            )

            out.append({
                "day": str(day),
                "when": str(ts),
                "decision": decision,
                "score": round(p, 4),
                "entry": entry,
                "stop": stop,
                "target": target,
                "outcome": outcome,
                "points": pts,
                "issued_prod": bool(issued),
                "should_trade": bool(head.get("should_trade")),
                "bar_note": head.get("bar_note"),
                "regime": regime_name,
                "or_ext": or_ext,
                "or_break": float(feat.get("or_break") or 0),
                "first_break": float(feat.get("first_break") or 0) >= 1,
                "confirms": confirms,
                "body_frac": body,
                "vwap_sess": vwap,
                "htf_bias_num": htf,
                "hour": hour,
                "favor": round(favor, 1),
                "against": round(against, 1),
                "risk": round(risk, 1),
                "delta_proxy": round(delta_proxy, 3),
                "atm_like": atm_like,
                "chase": chase,
                "shallow": shallow,
                "atr_frac": round(atr_frac, 5),
                "rv20": round(rv, 5),
                "direction_ok": direction_ok,
                "soft_direction": soft_direction,
                "theta_ok": hour < 14.25,
                "calendar_settle": hour >= 10.0,
                "gamma_zone": bool(atm_like and float(feat.get("first_break") or 0) >= 1),
                "resolve_i": int(resolve_i_bar),
                "bar_i": int(i),
            })
            if issued:
                ticket = {"open": True}
                resolve_i = resolve_i_bar
    return out


def _pick(cands: List[dict], pred: Callable[[dict], bool], *, max_n: int = 1) -> List[dict]:
    by_day: Dict[str, List[dict]] = defaultdict(list)
    for c in sorted(cands, key=lambda x: x["when"]):
        by_day[c["day"]].append(c)
    picked: List[dict] = []
    for day in sorted(by_day):
        free_after = None
        n = 0
        for c in by_day[day]:
            if n >= max_n:
                break
            if free_after is not None and c["bar_i"] <= free_after:
                continue
            if not pred(c):
                continue
            picked.append(c)
            n += 1
            free_after = int(c.get("resolve_i") or c["bar_i"])
    return picked


def _stats(rows: List[dict], early: bool) -> dict:
    outs, pts = [], []
    for r in rows:
        o, p = r["outcome"], float(r["points"])
        if early:
            o, p = _early(float(r["favor"]), float(r["against"]), float(r["risk"]), o, p)
        outs.append(o)
        pts.append(p)
    n = len(rows)
    wins = sum(1 for o in outs if o == "t1_before_sl")
    return {
        "calls": n,
        "t1": wins,
        "stop": sum(1 for o in outs if o in ("sl_before_t1", "same_bar_both")),
        "early_drop": sum(1 for o in outs if o == "early_drop"),
        "expired": sum(1 for o in outs if o == "expired"),
        "hit_pct": round(100.0 * wins / n, 1) if n else 0.0,
        "points": round(sum(pts), 1),
        "pts_per_call": round(sum(pts) / n, 1) if n else 0.0,
    }


def _enrich_legacy(c: dict) -> dict:
    """Backfill PDF fields if loading older strong_algo caches."""
    d = dict(c)
    or_ext = float(d.get("or_ext") or 0)
    d.setdefault("chase", or_ext > 0.55)
    d.setdefault("shallow", 0.0 < or_ext < 0.08)
    d.setdefault("rv20", float(d.get("atr_frac") or 0) * 8)
    vwap = float(d.get("vwap_sess") or 0)
    htf = float(d.get("htf_bias_num") or 0)
    dec = d.get("decision")
    d.setdefault(
        "direction_ok",
        (dec == "BUY" and vwap >= 0 and htf >= 0) or (dec == "SELL" and vwap <= 0 and htf <= 0),
    )
    d.setdefault(
        "soft_direction",
        (dec == "BUY" and vwap >= 0) or (dec == "SELL" and vwap <= 0),
    )
    hour = float(d.get("hour") or 12)
    d.setdefault("theta_ok", hour < 14.25)
    d.setdefault("calendar_settle", hour >= 10.0)
    d.setdefault("gamma_zone", bool(d.get("atm_like") and d.get("first_break")))
    return d


def build_policies() -> Dict[str, Callable[[dict], bool]]:
    def base_ok(c, floor: float) -> bool:
        return (
            float(c["score"]) >= floor
            and float(c.get("or_break") or 0) != 0
            and not c.get("bar_note")
        )

    def floor(x):
        return lambda c: base_ok(c, x)

    def varsity_direction(c):
        return bool(c.get("direction_ok") or c.get("soft_direction"))

    def varsity_atm_delta(c, dthr=0.45):
        return bool(c.get("atm_like") or c.get("first_break") or c.get("shallow")) and float(
            c.get("delta_proxy") or 0
        ) >= dthr and not bool(c.get("chase"))

    def varsity_theta(c):
        return bool(c.get("theta_ok", True))

    def iisc_vol(c, atr_cap=0.0045, rv_cap=0.012):
        return float(c.get("atr_frac") or 0) <= atr_cap and float(c.get("rv20") or 0) <= rv_cap

    def cboe_trend_debit(c):
        reg = str(c.get("regime") or "").upper()
        if reg == "RANGE":
            return False
        return base_ok(c, 0.52) and (bool(c.get("first_break")) or bool(c.get("atm_like")))

    def cboe_range_butterfly(c):
        """RANGE days: only ATM + higher bar (butterfly-like; skip otherwise)."""
        reg = str(c.get("regime") or "").upper()
        if reg != "RANGE":
            return False
        return base_ok(c, 0.54) and bool(c.get("atm_like")) and float(c.get("delta_proxy") or 0) >= 0.45

    def cboe_router(c):
        reg = str(c.get("regime") or "").upper()
        if reg == "RANGE":
            return cboe_range_butterfly(c)
        if 0.25 < float(c.get("or_ext") or 0) <= 0.55 and not bool(c.get("first_break")):
            return False
        return base_ok(c, 0.52)

    def cboe_calendar(c):
        return bool(c.get("calendar_settle", True)) and cboe_router(c)

    def pdf_stack_strict(c):
        """All three PDFs stacked — accuracy-first."""
        if not base_ok(c, 0.52):
            return False
        if not varsity_direction(c) or not varsity_atm_delta(c, 0.45) or not varsity_theta(c):
            return False
        if not iisc_vol(c):
            return False
        return cboe_router(c) or cboe_trend_debit(c) or (
            str(c.get("regime") or "").upper() != "RANGE" and bool(c.get("first_break"))
        )

    def pdf_stack_soft(c):
        """Slightly looser stack for more calls."""
        if not (base_ok(c, 0.51) and varsity_direction(c) and varsity_theta(c)):
            return False
        if bool(c.get("chase")):
            return False
        if float(c.get("delta_proxy") or 0) < 0.40:
            return False
        if not iisc_vol(c, atr_cap=0.0050, rv_cap=0.014):
            return False
        reg = str(c.get("regime") or "").upper()
        if reg == "RANGE":
            return base_ok(c, 0.54) and bool(c.get("atm_like"))
        return True

    def pdf_promote_delta(c):
        if base_ok(c, 0.52) and varsity_atm_delta(c, 0.45) and varsity_direction(c):
            return True
        return (
            base_ok(c, 0.50)
            and float(c.get("delta_proxy") or 0) >= 0.55
            and bool(c.get("atm_like"))
            and varsity_direction(c)
            and varsity_theta(c)
            and iisc_vol(c)
        )

    def pdf_gamma_first(c):
        """IISc long-gamma / Varsity ATM Δ: first ATM break only."""
        return base_ok(c, 0.52) and bool(c.get("gamma_zone") or (c.get("first_break") and c.get("atm_like")))

    def pdf_accuracy_max(c):
        """Highest bar: direction + ATM Δ + vol + theta + router."""
        return (
            base_ok(c, 0.54)
            and varsity_direction(c)
            and varsity_atm_delta(c, 0.50)
            and varsity_theta(c)
            and iisc_vol(c, atr_cap=0.0040, rv_cap=0.010)
            and (cboe_router(c) or bool(c.get("first_break")))
        )

    def pdf_more_calls(c):
        """Expand calls while keeping PDF gates (not raw floor drop)."""
        if bool(c.get("chase")) or not varsity_theta(c):
            return False
        if not varsity_direction(c):
            return False
        if float(c.get("delta_proxy") or 0) < 0.42:
            return False
        if not iisc_vol(c, atr_cap=0.0052, rv_cap=0.015):
            return False
        reg = str(c.get("regime") or "").upper()
        if reg == "RANGE":
            return base_ok(c, 0.53) and bool(c.get("atm_like"))
        return base_ok(c, 0.50) and (bool(c.get("atm_like")) or bool(c.get("first_break")) or bool(c.get("shallow")))

    def prod_or_pdf_promote(c):
        return bool(c.get("issued_prod")) or pdf_promote_delta(c)

    def vwap_htf_52(c):
        return base_ok(c, 0.52) and varsity_direction(c)

    return {
        "prod_issued": lambda c: bool(c.get("issued_prod")),
        "floor_52": floor(0.52),
        "floor_50": floor(0.50),
        "varsity_dir_atm_delta": lambda c: base_ok(c, 0.52) and varsity_direction(c) and varsity_atm_delta(c),
        "varsity_theta_52": lambda c: base_ok(c, 0.52) and varsity_theta(c),
        "cboe_regime_router": cboe_router,
        "cboe_trend_debit": cboe_trend_debit,
        "cboe_range_butterfly": lambda c: cboe_range_butterfly(c) or cboe_trend_debit(c),
        "cboe_calendar_settle": cboe_calendar,
        "iisc_vol_cap": lambda c: base_ok(c, 0.52) and iisc_vol(c),
        "pdf_stack_strict": pdf_stack_strict,
        "pdf_stack_soft": pdf_stack_soft,
        "pdf_promote_delta": pdf_promote_delta,
        "pdf_gamma_first": pdf_gamma_first,
        "pdf_accuracy_max": pdf_accuracy_max,
        "pdf_more_calls": pdf_more_calls,
        "prod_or_pdf_promote": prod_or_pdf_promote,
        "vwap_htf_52": vwap_htf_52,
        "pdf_best_combo": lambda c: (
            pdf_stack_soft(c) or (bool(c.get("issued_prod")) and varsity_direction(c) and varsity_theta(c) and iisc_vol(c))
        ),
    }


def _slice_cands(cands: List[dict], days: List[str]) -> List[dict]:
    want = set(days)
    return [c for c in cands if c["day"] in want]


def evaluate(cands: List[dict], policies: Dict[str, Callable], base_hit: Optional[float] = None) -> Tuple[dict, List[dict]]:
    base_rows = _pick(cands, policies["prod_issued"], max_n=1)
    base = _stats(base_rows, early=False)
    base_ed = _stats(base_rows, early=True)
    if base_hit is None:
        base_hit = base["hit_pct"]

    rows = []
    for name, pred in policies.items():
        for max_n in (1, 2):
            for early in (False, True):
                picked = _pick(cands, pred, max_n=max_n)
                st = _stats(picked, early)
                st["algo"] = name
                st["max_n"] = max_n
                st["mgmt"] = "early_drop" if early else "hold"
                st["delta_calls"] = st["calls"] - base["calls"]
                st["delta_hit"] = round(st["hit_pct"] - base["hit_pct"], 1)
                st["delta_pts"] = round(st["points"] - base["points"], 1)
                rows.append(st)

    soft = [
        r for r in rows
        if r["calls"] > base["calls"]
        and r["hit_pct"] >= base["hit_pct"] - 2.0
        and r["points"] >= base["points"] * 0.9
    ]
    strict = [
        r for r in rows
        if r["calls"] >= base["calls"]
        and r["hit_pct"] >= base["hit_pct"] - 0.5
        and r["points"] >= base["points"]
    ]
    acc = [r for r in rows if r["calls"] >= max(1, int(base["calls"] * 0.7)) and r["hit_pct"] >= base["hit_pct"]]
    expand = [
        r for r in rows
        if r["calls"] > base["calls"] and r["hit_pct"] >= base["hit_pct"] - 1.0
    ]
    # Best joint objective: more calls AND hit within -1pp, ranked by hit then calls then pts
    joint = [
        r for r in rows
        if r["calls"] >= base["calls"] and r["hit_pct"] >= base["hit_pct"] - 1.0
    ]

    def rank(r):
        return (r["points"], r["hit_pct"], r["calls"])

    report = {
        "baseline": base,
        "baseline_early_drop": base_ed,
        "n_candidates": len(cands),
        "pareto_strict": sorted(strict, key=rank, reverse=True)[:20],
        "pareto_soft_more_calls": sorted(soft, key=rank, reverse=True)[:20],
        "best_accuracy": sorted(acc, key=lambda r: (r["hit_pct"], r["points"], r["calls"]), reverse=True)[:15],
        "best_expand_hit_within_1pp": sorted(
            expand, key=lambda r: (r["hit_pct"], r["calls"], r["points"]), reverse=True
        )[:15],
        "best_joint_more_calls_accuracy": sorted(
            joint, key=lambda r: (r["hit_pct"], r["calls"], r["points"]), reverse=True
        )[:15],
        "best_points": sorted(rows, key=rank, reverse=True)[:15],
        "grid": rows,
    }
    return report, rows


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Deep PDF-strategy research (Varsity + Cboe + IISc). Research only."
    )
    ap.add_argument("--sessions", type=int, default=126)
    ap.add_argument("--skip-last-sessions", type=int, default=0)
    ap.add_argument("--lookback-days", type=int, default=0)
    ap.add_argument("--kite-only", action="store_true")
    ap.add_argument("--from-cache", action="store_true")
    ap.add_argument(
        "--reuse-strong-cache",
        type=str,
        default="",
        help="Path to existing strong_algo_*_candidates.json to enrich offline",
    )
    ap.add_argument("--holdout-last", type=int, default=30, help="OOS last N sessions for validation")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE, REPORT = _paths(args.sessions, args.skip_last_sessions)
    need_sessions = args.sessions + args.skip_last_sessions
    lookback = args.lookback_days or max(int(need_sessions * 2.2) + 20, 55)

    pack = fno_model.load(symbol="NIFTY")
    if not fno_model.pack_usable(pack):
        raise SystemExit(pack.get("reason"))

    days: List[Any] = []
    if args.reuse_strong_cache:
        path = Path(args.reuse_strong_cache)
        raw = json.loads(path.read_text(encoding="utf-8"))
        cands = [_enrich_legacy(c) for c in raw["candidates"]]
        days = sorted({c["day"] for c in cands})
        print(f"reuse {path.name} n={len(cands)} days={len(days)}", flush=True)
    elif args.from_cache and CACHE.is_file():
        raw = json.loads(CACHE.read_text(encoding="utf-8"))
        cands = [_enrich_legacy(c) for c in raw["candidates"]]
        days = sorted({c["day"] for c in cands})
        print(f"cache {CACHE.name} {len(cands)}", flush=True)
    else:
        bars = _load_bars(lookback, kite_only=args.kite_only)
        day_counts = pd.Series(bars.index.map(lambda t: t.date())).value_counts()
        all_days = sorted(d for d, n in day_counts.items() if int(n) >= 8)
        if len(all_days) < need_sessions:
            raise SystemExit(
                f"need {need_sessions} sessions, tape only has {len(all_days)} "
                f"({all_days[0] if all_days else '?'} -> {all_days[-1] if all_days else '?'})"
            )
        block = all_days[-need_sessions:]
        if args.skip_last_sessions:
            days = block[: args.sessions]
            skipped = block[args.sessions :]
            print(
                f"PRIOR window {days[0]} -> {days[-1]} ({len(days)}) "
                f"| excluded newest {skipped[0]} -> {skipped[-1]} ({len(skipped)}) "
                f"| kite_only={args.kite_only}",
                flush=True,
            )
        else:
            days = block
            print(
                f"sessions {days[0]} -> {days[-1]} ({len(days)}) "
                f"kite_only={args.kite_only}",
                flush=True,
            )
        cands = collect(bars, pack, days)
        CACHE.write_text(
            json.dumps(
                {
                    "candidates": cands,
                    "sessions": [str(d) for d in days],
                    "skip_last_sessions": args.skip_last_sessions,
                    "kite_only": args.kite_only,
                    "pdf_sources": PDF_MAP,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"wrote {CACHE} n={len(cands)}", flush=True)

    policies = build_policies()
    day_strs = [str(d) for d in days] if days else sorted({c["day"] for c in cands})
    holdout_n = min(args.holdout_last, max(0, len(day_strs) // 3))
    train_days = day_strs[:-holdout_n] if holdout_n else day_strs
    test_days = day_strs[-holdout_n:] if holdout_n else []

    full_report, _ = evaluate(cands, policies)
    print(f"\nBASELINE prod1 hold: {full_report['baseline']}", flush=True)
    print(f"BASELINE prod1 early: {full_report['baseline_early_drop']}", flush=True)

    def fmt(r):
        return (
            f"{r['algo']:<26} max{r['max_n']} {r['mgmt']:<11} "
            f"n={r['calls']:3d}({r['delta_calls']:+}) hit={r['hit_pct']:5.1f}%({r['delta_hit']:+.1f}) "
            f"pts={r['points']:+8.1f}({r['delta_pts']:+.0f})"
        )

    print("\n=== FULL WINDOW — STRICT ===")
    for r in full_report["pareto_strict"][:8]:
        print(fmt(r))
    print("\n=== FULL WINDOW — SOFT MORE CALLS ===")
    for r in full_report["pareto_soft_more_calls"][:8]:
        print(fmt(r))
    print("\n=== FULL WINDOW — BEST ACCURACY (keep ≥70% base calls) ===")
    for r in full_report["best_accuracy"][:8]:
        print(fmt(r))
    print("\n=== FULL WINDOW — JOINT (calls≥base, hit≥-1pp) ===")
    for r in full_report["best_joint_more_calls_accuracy"][:8]:
        print(fmt(r))

    oos = {}
    if test_days:
        train_c = _slice_cands(cands, train_days)
        test_c = _slice_cands(cands, test_days)
        train_rep, train_rows = evaluate(train_c, policies)
        # Pick top joint algos on train, score on test
        top_train = train_rep["best_joint_more_calls_accuracy"][:8] or train_rep["pareto_soft_more_calls"][:8]
        test_base_rows = _pick(test_c, policies["prod_issued"], max_n=1)
        test_base = _stats(test_base_rows, early=False)
        checked = []
        for tr in top_train:
            pred = policies[tr["algo"]]
            picked = _pick(test_c, pred, max_n=int(tr["max_n"]))
            st = _stats(picked, early=(tr["mgmt"] == "early_drop"))
            st["algo"] = tr["algo"]
            st["max_n"] = tr["max_n"]
            st["mgmt"] = tr["mgmt"]
            st["train_hit"] = tr["hit_pct"]
            st["train_calls"] = tr["calls"]
            st["delta_calls"] = st["calls"] - test_base["calls"]
            st["delta_hit"] = round(st["hit_pct"] - test_base["hit_pct"], 1)
            st["delta_pts"] = round(st["points"] - test_base["points"], 1)
            checked.append(st)
        oos = {
            "train_sessions": train_days,
            "test_sessions": test_days,
            "train_baseline": train_rep["baseline"],
            "test_baseline": test_base,
            "train_top_joint": top_train,
            "test_replay_of_train_top": sorted(
                checked, key=lambda r: (r["hit_pct"], r["calls"], r["points"]), reverse=True
            ),
        }
        print(f"\n=== OOS holdout last {holdout_n} sessions ===")
        print(f"train {train_days[0]}->{train_days[-1]} base {train_rep['baseline']}")
        print(f"test  {test_days[0]}->{test_days[-1]} base {test_base}")
        print("--- train winners replayed on holdout ---")
        for r in oos["test_replay_of_train_top"][:8]:
            print(
                f"{r['algo']:<26} max{r['max_n']} {r['mgmt']:<11} "
                f"n={r['calls']:3d}({r['delta_calls']:+}) hit={r['hit_pct']:5.1f}%({r['delta_hit']:+.1f}) "
                f"pts={r['points']:+8.1f} | train_hit={r['train_hit']}"
            )

    report = {
        "note": (
            "Deep PDF research: Varsity direction/ATM/delta/theta/vol + "
            "Cboe TREND-debit/RANGE-butterfly/calendar + IISc vol/early-drop. "
            "max_n=2 = second ticket. Research only — no prod change."
        ),
        "pdf_sources": PDF_MAP,
        "sessions": day_strs,
        "kite_only": bool(args.kite_only),
        "full_window": full_report,
        "oos_holdout": oos,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {REPORT}", flush=True)

    # Verdict line
    joint = full_report["best_joint_more_calls_accuracy"]
    acc = full_report["best_accuracy"]
    soft = full_report["pareto_soft_more_calls"]
    print("\n=== VERDICT ===", flush=True)
    if soft:
        print("more_calls+accuracy soft:", fmt(soft[0]), flush=True)
    if joint:
        print("joint best:", fmt(joint[0]), flush=True)
    if acc:
        print("max accuracy:", fmt(acc[0]), flush=True)
    if oos.get("test_replay_of_train_top"):
        print("oos best of train picks:", flush=True)
        r = oos["test_replay_of_train_top"][0]
        print(
            f"  {r['algo']} max{r['max_n']} {r['mgmt']} "
            f"n={r['calls']} hit={r['hit_pct']}% pts={r['points']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
