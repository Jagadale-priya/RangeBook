"""NIFTY · 1 Nov → now · LIVE stack (NSE mid OFF) + tags.

Same logic as 6m complete report:
  stack_plus_crown_htf_cap2 · proven>good>champ>HTF-crown · cap2 · same-side
  ENABLE_NSE_MID_GATE=0 · champ BUY≥0.55
  Tags: Stacked · track · Clean morning / Clean multi

Fresh dual (OR-break) + good snapshot + live crown on extended tapes.

  python -u tools/validate/fno_nifty_nov1_stack_live_report.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "research"))
sys.path.insert(0, str(ROOT / "tools" / "validate"))
sys.path.insert(0, str(ROOT / "prod_live" / "tests" / "builders"))
warnings.filterwarnings("ignore")

import path_setup  # noqa: F401,E402

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass

os.environ.setdefault("TELEGRAM_NOTIFY", "0")
os.environ.setdefault("WHATSAPP_NOTIFY", "0")
os.environ["ENABLE_STACKED_CALLS"] = "1"
os.environ["ENABLE_PRE_DUAL_SINGLE"] = "1"
os.environ["USE_DUAL_TRACK"] = "0"
os.environ["ENABLE_5M_CROWN"] = "1"
os.environ["ENABLE_5M_CROWN_ALL"] = "1"
os.environ["ENABLE_15M_CLASSIC"] = "0"
os.environ["ENABLE_DAILY_FILL"] = "0"
os.environ["ENABLE_NSE_MID_GATE"] = "0"
os.environ["CROWN_BUILD_QUIET"] = "1"

import fno_clean_call_tags as clean_tags  # noqa: E402
import fno_live_config as live_cfg  # noqa: E402
import fno_nse_mid_gate as nse_gate  # noqa: E402
import nifty_live_dual_track as live  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402


def _norm(raw: pd.DataFrame) -> pd.DataFrame:
    work = raw.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index)
    if work.index.tz is None:
        work.index = work.index.tz_localize("Asia/Kolkata")
    else:
        work.index = work.index.tz_convert("Asia/Kolkata")
    work = work.rename(columns={c: str(c).title() for c in work.columns})
    return work.sort_index()

OUT_DIR = ROOT / "stock_signal_data/fno_validate/research"
TAPE15 = ROOT / "stock_signal_data/fno_validate/NIFTY_15m_12y.csv"
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"
DAILY = ROOT / "stock_signal_data/fno_validate/NIFTY_daily_nse.csv"
OUT_JSON = OUT_DIR / "fno_nifty_nov1_stack_live_report.json"
OUT_MD = OUT_DIR / "fno_nifty_nov1_stack_live_report.md"
OUT_CSV = OUT_DIR / "fno_nifty_nov1_stack_live_calls.csv"

START = "2026-11-01"
LOOKBACK = pd.Timedelta(days=12)
FLAT_BPS = 0.15
PRIORITY = fs.PRIORITY
CHAMP_BUY_MIN = float(live.CHAMPION_BUY_MIN_P)
CHAMP_SELL_MIN = float(live.CHAMPION_SELL_MIN_P)


def _hm(ts) -> str:
    t = ts
    if hasattr(t, "tz_convert"):
        try:
            t = t.tz_convert("Asia/Kolkata")
        except Exception:
            pass
    return t.strftime("%H:%M") if hasattr(t, "strftime") else str(t)[11:16]


def _day(ts) -> str:
    t = ts
    if hasattr(t, "tz_convert"):
        try:
            t = t.tz_convert("Asia/Kolkata")
        except Exception:
            pass
    return t.strftime("%Y-%m-%d")


def _day_moves() -> Dict[str, dict]:
    d = pd.read_csv(DAILY)
    d["Date"] = pd.to_datetime(d["Date"]).dt.strftime("%Y-%m-%d")
    out = {}
    for _, r in d.iterrows():
        day = str(r["Date"])[:10]
        if day < START:
            continue
        chg = float(r["ChangePct"])
        move = "FLAT" if abs(chg) < FLAT_BPS else ("UP" if chg > 0 else "DOWN")
        out[day] = {"change_pct": chg, "move": move}
    return out


def _fwd(bars: pd.DataFrame, i: int, side: str, sl: float, t1: float) -> Tuple[bool, str, float]:
    fut = bars.iloc[i + 1 :]
    day = _day(bars.index[i])
    fut = fut[[_day(x) == day for x in fut.index]]
    entry = float(bars["Close"].iloc[i])
    if fut.empty:
        return False, "no_future", 0.0
    hi = fut["High"].astype(float)
    lo = fut["Low"].astype(float)
    if side == "BUY":
        for h, l in zip(hi, lo):
            hit_sl, hit_t1 = l <= sl, h >= t1
            if hit_sl and hit_t1:
                return False, "same_bar_both", -abs(entry - sl)
            if hit_sl:
                return False, "sl_before_t1", -abs(entry - sl)
            if hit_t1:
                return True, "t1_before_sl", abs(t1 - entry)
        return False, "expired", -abs(entry - sl)
    for h, l in zip(hi, lo):
        hit_sl, hit_t1 = h >= sl, l <= t1
        if hit_sl and hit_t1:
            return False, "same_bar_both", -abs(sl - entry)
        if hit_sl:
            return False, "sl_before_t1", -abs(sl - entry)
        if hit_t1:
            return True, "t1_before_sl", abs(entry - t1)
    return False, "expired", -abs(sl - entry)


def _candle_bias(day_win: pd.DataFrame) -> str:
    try:
        import analysis_engine as ae

        idxs = [i for i, ts in enumerate(day_win.index) if _hm(ts) >= "10:00"]
        i = idxs[0] if idxs else len(day_win) - 1
        cs = ae.analyze_candlestick(day_win.iloc[: i + 1])
        return str((cs or {}).get("bias") or "NEUTRAL").upper()
    except Exception:
        return "NEUTRAL"


def _or_break_idxs(sess: pd.DataFrame) -> List[int]:
    closes = sess["Close"].astype(float).to_numpy()
    try:
        or_hi = float(sess["High"].astype(float).iloc[0])
        or_lo = float(sess["Low"].astype(float).iloc[0])
    except Exception:
        return []
    if or_hi <= or_lo:
        return []
    first_up = first_dn = None
    cand: List[int] = []
    for i in range(1, len(sess)):
        c = float(closes[i])
        if first_up is None and c > or_hi:
            first_up = i
            cand.append(i)
        if first_dn is None and c < or_lo:
            first_dn = i
            cand.append(i)
        if first_up is not None and first_dn is not None:
            break
    return sorted(set(cand))


def _stamp_tags(
    *,
    track: str,
    side: str,
    p_t1: Any,
    hm: str,
    candle: str,
    overlay_today: List[dict],
) -> dict:
    try:
        mins = int(hm[:2]) * 60 + int(hm[3:5])
    except Exception:
        mins = None
    if track == "proven_100":
        label = "Priority · Confident 100% proven"
        tags = [
            {
                "code": "proven_100",
                "label": "Priority · Confident 100%",
                "tone": "proven",
                "priority": 10,
            }
        ]
    elif track == "champion":
        label = f"Priority · High accuracy (~{live.CHAMPION_HIT_PCT:.0f}% hit target)"
        tags = [
            {
                "code": "most_accurate",
                "label": "Priority · High accuracy",
                "tone": "champion",
                "priority": 11,
            }
        ]
    elif track == "crown_5m":
        label = "5m crown"
        tags = [{"code": "5m_crown", "label": "5m crown", "tone": "champion", "priority": 12}]
    else:
        label = "Good · pre-dual single"
        tags = list(live_cfg.good_accuracy_tags(decision=side))

    payload = {
        "track": track,
        "decision": side,
        "p_t1": p_t1,
        "mins": mins,
        "accuracy_label": label,
        "accuracy_tags": list(tags),
    }
    tags2 = list(payload["accuracy_tags"])
    tags2.insert(
        0,
        {
            "code": live_cfg.STACK_TAG_CODE,
            "label": f"Stacked · {track}",
            "detail": live_cfg.STACK_TRACK,
            "tone": "good",
            "priority": 10,
        },
    )
    payload["accuracy_tags"] = tags2
    clean_tags.stamp_clean(
        payload,
        mins=mins,
        candle_bias=candle,
        overlay_today=overlay_today,
        track="crown_5m" if track == "crown_5m" else track,
        decision=side,
        p_t1=p_t1,
    )
    labels = [str(t.get("label")) for t in (payload.get("accuracy_tags") or []) if t.get("label")]
    return {
        "accuracy_label": payload.get("accuracy_label") or label,
        "tags": " | ".join(labels),
        "tag_list": labels,
        "clean": bool(payload.get("clean")),
        "clean_multi": bool(payload.get("clean_multi")),
        "clean_morning": bool(payload.get("clean_morning")),
    }


def _collect_dual_good(bars: pd.DataFrame, sessions: List[str]) -> Dict[str, List[dict]]:
    import fno_model
    import fno_session_replay as fsr_snap

    pack = fno_model.load(symbol="NIFTY")
    pack_ok = fno_model.pack_usable(pack)
    proven: List[dict] = []
    champ: List[dict] = []
    good: List[dict] = []

    for day in sessions:
        sess = bars[[_day(ts) == day and "09:15" <= _hm(ts) <= "15:15" for ts in bars.index]]
        if len(sess) < 4:
            continue
        for i_local in _or_break_idxs(sess):
            ts = sess.index[i_local]
            full_i = int(bars.index.get_indexer([ts])[0])
            if full_i < 0:
                continue
            asof = ts + pd.Timedelta("15min")
            left = int(bars.index.searchsorted(ts - LOOKBACK))
            win = bars.iloc[left : full_i + 1]
            price = float(bars["Close"].iloc[full_i])
            hm = _hm(ts)

            # Dual
            try:
                ev = live.evaluate(win, asof=asof, price=price, session_ticket=None)
            except Exception:
                ev = None
            call = (ev or {}).get("call_payload") or {}
            dec = str(call.get("decision") or "").upper()
            if dec in ("BUY", "SELL"):
                p = call.get("p_t1")
                try:
                    pf = float(p) if p is not None else None
                except Exception:
                    pf = None
                ok = True
                if dec == "BUY" and pf is not None and pf < CHAMP_BUY_MIN:
                    # proven may still pass via track
                    if str(call.get("track") or "") != "proven_100":
                        ok = False
                if dec == "SELL" and pf is not None and pf < CHAMP_SELL_MIN:
                    if str(call.get("track") or "") != "proven_100":
                        ok = False
                if ok:
                    sl = float(call["stop_loss"])
                    t1 = float(call["target_1"])
                    win_f, outcome, pts = _fwd(bars, full_i, dec, sl, t1)
                    track = str(call.get("track") or ("proven_100" if (ev or {}).get("proven_100") else "champion"))
                    if track == "baseline":
                        track = "champion"
                    row = {
                        "day": day,
                        "hm": hm,
                        "decision": dec,
                        "track": track,
                        "priority": PRIORITY.get(track, 2),
                        "p_t1": pf,
                        "win": win_f,
                        "points": round(pts, 1),
                        "outcome": outcome,
                        "entry": round(float(call.get("entry") or price), 2),
                        "stop_loss": round(sl, 2),
                        "target_1": round(t1, 2),
                    }
                    if track == "proven_100":
                        proven.append(row)
                    else:
                        champ.append(row)

            # Good snapshot
            if pack_ok:
                try:
                    box = fsr_snap.session_day_range(win, lookback=2)
                    snap = fsr_snap.score_snapshot(
                        win,
                        symbol="NIFTY",
                        day_range=box,
                        model_pack=pack,
                        primary=True,
                        asof=ts,
                        session_ticket=None,
                    )
                    issued = snap.get("issued_ticket") or {}
                    dec_s = str(
                        (issued.get("decision") if issued else None)
                        or snap.get("decision")
                        or ""
                    ).upper()
                    if dec_s in ("BUY", "SELL"):
                        if issued:
                            entry = float(issued.get("entry") or price)
                            sl = issued.get("stop_loss")
                            t1 = issued.get("target_1")
                            p_t1 = (snap.get("fno_head") or {}).get("p_t1")
                        else:
                            ft = ((snap.get("risk") or {}).get("fno_trade") or {})
                            entry = float(ft.get("entry") or price)
                            sl = ft.get("stop_loss")
                            t1 = ft.get("target_1")
                            p_t1 = (snap.get("fno_head") or {}).get("p_t1")
                        if sl is not None and t1 is not None:
                            win_f, outcome, pts = _fwd(
                                bars, full_i, dec_s, float(sl), float(t1)
                            )
                            try:
                                pf = float(p_t1) if p_t1 is not None else None
                            except Exception:
                                pf = None
                            good.append(
                                {
                                    "day": day,
                                    "hm": hm,
                                    "decision": dec_s,
                                    "track": "good_prod2",
                                    "priority": PRIORITY["good_prod2"],
                                    "p_t1": pf,
                                    "win": win_f,
                                    "points": round(pts, 1),
                                    "outcome": outcome,
                                    "entry": round(entry, 2),
                                    "stop_loss": round(float(sl), 2),
                                    "target_1": round(float(t1), 2),
                                }
                            )
                except Exception:
                    pass
    return {"proven_100": proven, "champion": champ, "good_prod2": good}


def _collect_crown(df5: pd.DataFrame, df15: pd.DataFrame, sessions: List[str], active: set) -> List[dict]:
    import fno_5m_crown as crown

    rows: List[dict] = []
    for day in sessions:
        if day not in active:
            continue
        c_ix = [
            i
            for i, ts in enumerate(df5.index)
            if _day(ts) == day and "09:15" <= _hm(ts) <= "15:25"
        ]
        for i in c_ix:
            ts = df5.index[i]
            left = int(df5.index.searchsorted(ts - LOOKBACK))
            win5 = df5.iloc[left : i + 1]
            if len(win5) < 80:
                continue
            i15 = int(df15.index.searchsorted(ts, side="right")) - 1
            if i15 < 0:
                continue
            left15 = int(df15.index.searchsorted(df15.index[i15] - LOOKBACK))
            win15 = df15.iloc[left15 : i15 + 1]
            try:
                sig = crown.evaluate_latest(
                    "NIFTY",
                    win5,
                    bars_15m=win15,
                    price=float(df5["Close"].iloc[i]),
                    asof=ts,
                )
            except Exception:
                sig = None
            if not isinstance(sig, dict) or sig.get("decision") not in ("BUY", "SELL"):
                continue
            side = str(sig["decision"]).upper()
            entry = float(sig.get("entry") or df5["Close"].iloc[i])
            sl = float(sig["stop_loss"])
            t1 = float(sig["target_1"])
            # forward on 5m same day
            fut = df5.iloc[i + 1 :]
            fut = fut[[_day(x) == day for x in fut.index]]
            win_f = False
            outcome = "expired"
            pts = -abs(entry - sl) if side == "BUY" else -abs(sl - entry)
            if len(fut):
                hi = fut["High"].astype(float)
                lo = fut["Low"].astype(float)
                if side == "BUY":
                    for h, l in zip(hi, lo):
                        if l <= sl and h >= t1:
                            outcome = "same_bar_both"
                            break
                        if l <= sl:
                            outcome = "sl_before_t1"
                            break
                        if h >= t1:
                            win_f, outcome, pts = True, "t1_before_sl", abs(t1 - entry)
                            break
                    else:
                        outcome = "expired"
                else:
                    for h, l in zip(hi, lo):
                        if h >= sl and l <= t1:
                            outcome = "same_bar_both"
                            break
                        if h >= sl:
                            outcome = "sl_before_t1"
                            break
                        if l <= t1:
                            win_f, outcome, pts = True, "t1_before_sl", abs(entry - t1)
                            break
                    else:
                        outcome = "expired"
                if outcome in ("sl_before_t1", "same_bar_both", "expired") and not win_f:
                    pts = -abs(entry - sl) if side == "BUY" else -abs(sl - entry)
            try:
                pf = float(sig.get("p_t1")) if sig.get("p_t1") is not None else None
            except Exception:
                pf = None
            rows.append(
                {
                    "day": day,
                    "hm": _hm(ts),
                    "decision": side,
                    "track": "crown_5m",
                    "priority": PRIORITY["crown_5m"],
                    "p_t1": pf,
                    "win": win_f,
                    "points": round(float(pts), 1),
                    "outcome": outcome,
                    "entry": round(entry, 2),
                    "stop_loss": round(sl, 2),
                    "target_1": round(t1, 2),
                }
            )
            break  # first crown signal of day (union will re-pick)
    return rows


def main() -> None:
    t0 = time.time()
    print("NIFTY · Nov1→now · LIVE stack (NSE mid OFF) + tags", flush=True)
    print(
        f"  NSE mid enabled={nse_gate.enabled()} · champ BUY≥{CHAMP_BUY_MIN}",
        flush=True,
    )

    bars = _norm(pd.read_csv(TAPE15, index_col=0, parse_dates=True))
    df5 = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
    moves = _day_moves()
    print(f"  tape15 {bars.index.min()} → {bars.index.max()}", flush=True)
    print(f"  tape5  {df5.index.min()} → {df5.index.max()}", flush=True)

    sessions = sorted(
        {
            _day(ts)
            for ts in bars.index
            if _day(ts) >= START and "09:15" <= _hm(ts) <= "15:15"
        }
    )
    print(f"  sessions={len(sessions)} {sessions[0]}→{sessions[-1]}", flush=True)

    daily_htf = fs._load_daily()
    # Extend HTF daily with NSE daily if needed for recent days
    try:
        nse = pd.read_csv(DAILY)
        nse["Date"] = pd.to_datetime(nse["Date"])
        # ensure Volume/High/Low/Close
        extra = nse[nse["Date"] > daily_htf["Date"].max()].copy()
        if len(extra):
            daily_htf = (
                pd.concat([daily_htf, extra], ignore_index=True)
                .drop_duplicates(subset=["Date"], keep="last")
                .sort_values("Date")
                .reset_index(drop=True)
            )
    except Exception:
        pass
    active = fs._active_days(sessions, daily_htf)
    print(f"  HTF-active days={len(active)}", flush=True)

    print("  dual+good OR-break walk…", flush=True)
    pools = _collect_dual_good(bars, sessions)
    print(
        f"    proven={len(pools['proven_100'])} champ={len(pools['champion'])} "
        f"good={len(pools['good_prod2'])}",
        flush=True,
    )

    print("  crown HTF walk…", flush=True)
    crown = _collect_crown(df5, bars, sessions, active)
    print(f"    crown_htf={len(crown)}", flush=True)

    stack = fs._union(
        {
            "proven_100": pools["proven_100"],
            "good_prod2": pools["good_prod2"],
            "champion": pools["champion"],
            "crown_5m": crown,
        },
        day_cap=2,
    )
    print(f"  stack listed={len(stack)}", flush=True)

    # candles + overlay lean for tags
    overlay_acc: Dict[str, List[dict]] = defaultdict(list)
    candle_by: Dict[str, str] = {}
    try:
        import fno_overlay_indication as foi

        for day in sessions:
            day_only = bars[
                [_day(ts) == day and "09:15" <= _hm(ts) <= "15:15" for ts in bars.index]
            ]
            candle_by[day] = _candle_bias(day_only)
            for i, ts in enumerate(day_only.index):
                if _hm(ts) >= "10:00":
                    left = int(bars.index.searchsorted(ts - LOOKBACK))
                    full_i = int(bars.index.get_indexer([ts])[0])
                    win = bars.iloc[left : full_i + 1]
                    try:
                        sig = foi.evaluate_latest(win, "NIFTY")
                        if isinstance(sig, dict) and sig.get("decision") in ("BUY", "SELL"):
                            overlay_acc[day].append(sig)
                    except Exception:
                        pass
                    break
    except Exception:
        for day in sessions:
            candle_by[day] = "NEUTRAL"

    live_calls: List[dict] = []
    for r in stack:
        d = r["day"]
        side = str(r["decision"]).upper()
        track = str(r["track"])
        move = (moves.get(d) or {}).get("move")
        align = "flat"
        if (move == "UP" and side == "BUY") or (move == "DOWN" and side == "SELL"):
            align = "align"
        elif move in ("UP", "DOWN"):
            align = "against"
        tagged = _stamp_tags(
            track=track,
            side=side,
            p_t1=r.get("p_t1"),
            hm=r.get("hm") or "",
            candle=candle_by.get(d) or "NEUTRAL",
            overlay_today=overlay_acc.get(d) or [],
        )
        live_calls.append(
            {
                "day": d,
                "hm": r.get("hm"),
                "decision": side,
                "track": track,
                "p_t1": None if r.get("p_t1") is None else round(float(r["p_t1"]), 4),
                "entry": r.get("entry"),
                "stop_loss": r.get("stop_loss"),
                "target_1": r.get("target_1"),
                "win": bool(r.get("win")),
                "outcome": r.get("outcome"),
                "points": round(float(r.get("points") or 0), 1),
                "move": move,
                "change_pct": (moves.get(d) or {}).get("change_pct"),
                "align": align,
                "candle": candle_by.get(d),
                "accuracy_label": tagged["accuracy_label"],
                "tags": tagged["tags"],
                "tag_list": tagged["tag_list"],
                "clean": tagged["clean"],
                "clean_multi": tagged["clean_multi"],
                "clean_morning": tagged["clean_morning"],
            }
        )

    n = len(live_calls)
    wins = sum(1 for c in live_calls if c["win"])
    pts = round(sum(c["points"] for c in live_calls), 1)
    tag_counts: Dict[str, int] = defaultdict(int)
    for c in live_calls:
        for t in c.get("tag_list") or []:
            tag_counts[t] += 1
        if c.get("clean_multi"):
            tag_counts["[flag] clean_multi"] += 1
        if c.get("clean_morning"):
            tag_counts["[flag] clean_morning"] += 1

    by_tr: Dict[str, List[dict]] = defaultdict(list)
    for c in live_calls:
        by_tr[c["track"]].append(c)

    runtime = round((time.time() - t0) / 60.0, 2)
    lines = [
        "# NIFTY · 1 Nov → now · LIVE stack (NSE mid OFF)",
        "",
        f"Generated `{datetime.now().isoformat(timespec='seconds')}` · runtime {runtime} min",
        f"Window **{sessions[0]} → {sessions[-1]}** · sessions **{len(sessions)}**",
        f"Tape15 max `{bars.index.max()}` · Tape5 max `{df5.index.max()}`",
        f"NSE mid gate: **OFF** · champ BUY≥{CHAMP_BUY_MIN} · stack_plus_crown_htf_cap2",
        "",
        "## Combined",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Calls | **{n}** |",
        f"| Wins / Losses | {wins} / {n - wins} |",
        f"| Hit % | **{round(100.0 * wins / n, 2) if n else None}** |",
        f"| Total points | **{pts}** |",
        f"| Pts / call | **{round(pts / n, 2) if n else None}** |",
        f"| Days with call | {len({c['day'] for c in live_calls})} / {len(sessions)} |",
        f"| Clean multi | {tag_counts.get('[flag] clean_multi', 0)} |",
        f"| Clean morning | {tag_counts.get('[flag] clean_morning', 0)} |",
        "",
        "## Channels raw (before day-cap)",
        "",
        "| Channel | n | Hit % | Points |",
        "|---|---:|---:|---:|",
    ]
    for tr, rows in (
        ("proven_100", pools["proven_100"]),
        ("good_prod2", pools["good_prod2"]),
        ("champion", pools["champion"]),
        ("crown_5m_htf", crown),
    ):
        if not rows:
            lines.append(f"| `{tr}` | 0 | — | 0 |")
            continue
        w = sum(1 for r in rows if r.get("win"))
        lines.append(
            f"| `{tr}` | {len(rows)} | {round(100.0 * w / len(rows), 1)} | "
            f"{round(sum(float(r.get('points') or 0) for r in rows), 1)} |"
        )

    lines += [
        "",
        "## LIVE listed · by track",
        "",
        "| Track | n | Hit % | Points |",
        "|---|---:|---:|---:|",
    ]
    for tr in ("proven_100", "good_prod2", "champion", "crown_5m"):
        sub = by_tr.get(tr) or []
        if not sub:
            lines.append(f"| `{tr}` | 0 | — | 0 |")
            continue
        w = sum(1 for c in sub if c["win"])
        lines.append(
            f"| `{tr}` | {len(sub)} | {round(100.0 * w / len(sub), 1)} | "
            f"{round(sum(c['points'] for c in sub), 1)} |"
        )

    lines += ["", "## Tags count", "", "| Tag | Count |", "|---|---:|"]
    for lab, cnt in sorted(tag_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {lab} | {cnt} |")

    lines += [
        "",
        "## Every call + tags",
        "",
        "| Day | HM | Side | Track | p | Win | Pts | Move | Align | Accuracy label | Tags |",
        "|---|---|---|---|---:|---|---:|---|---|---|---|",
    ]
    for c in live_calls:
        lines.append(
            f"| {c['day']} | {c['hm']} | **{c['decision']}** | `{c['track']}` | {c['p_t1']} | "
            f"{'Y' if c['win'] else 'N'} | {c['points']} | {c.get('move')} | {c.get('align')} | "
            f"{c['accuracy_label']} | {c['tags']} |"
        )
    if not live_calls:
        lines.append("| — | — | — | — | — | — | — | — | — | **no calls** | — |")

    lines += [
        "",
        "## Day context",
        "",
        "| Day | Move | Chg% | Candle | HTF | Calls | Pts |",
        "|---|---|---:|---|---|---:|---:|",
    ]
    by_day = defaultdict(list)
    for c in live_calls:
        by_day[c["day"]].append(c)
    for day in sessions:
        m = moves.get(day) or {}
        cs = by_day.get(day) or []
        lines.append(
            f"| {day} | {m.get('move')} | {m.get('change_pct')} | {candle_by.get(day)} | "
            f"{'Y' if day in active else 'N'} | {len(cs)} | "
            f"{round(sum(c['points'] for c in cs), 1)} |"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    pd.DataFrame(live_calls).to_csv(OUT_CSV, index=False)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "runtime_min": runtime,
        "nse_mid_gate": False,
        "window": {"start": sessions[0], "end": sessions[-1], "sessions": sessions},
        "summary": {
            "n": n,
            "wins": wins,
            "losses": n - wins,
            "hit_pct": round(100.0 * wins / n, 2) if n else None,
            "points": pts,
            "pts_per_call": round(pts / n, 2) if n else None,
            "days_with_call": len({c["day"] for c in live_calls}),
            "clean_multi": tag_counts.get("[flag] clean_multi", 0),
            "clean_morning": tag_counts.get("[flag] clean_morning", 0),
        },
        "raw": {
            "proven_100": len(pools["proven_100"]),
            "champion": len(pools["champion"]),
            "good_prod2": len(pools["good_prod2"]),
            "crown_5m_htf": len(crown),
        },
        "tag_counts": dict(tag_counts),
        "calls": live_calls,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUT_MD}", flush=True)
    print(
        f"NOV1+ LIVE n={n} hit={payload['summary']['hit_pct']} pts={pts} "
        f"clean_multi={tag_counts.get('[flag] clean_multi', 0)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
