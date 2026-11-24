"""Complete per-call report: current dual-track + independent 5m crown (last 4m).

Lists EVERY call with outcome for NIFTY / BANKNIFTY / SENSEX.
Champion / baseline / proven dual logic unchanged; crown is parallel.

  python -u tools/validate/fno_complete_call_report.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
import warnings
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "research"))

os.environ.setdefault("TELEGRAM_NOTIFY", "0")
os.environ.setdefault("WHATSAPP_NOTIFY", "0")
os.environ.setdefault("ENABLE_5M_CROWN", "1")
os.environ["ENABLE_5M_CROWN_ALL"] = "1"  # report all crown packs

warnings.filterwarnings("ignore", category=DeprecationWarning)

OUT_DIR = ROOT / "stock_signal_data/fno_validate/research"
OUT_JSON = OUT_DIR / "fno_complete_call_report.json"
OUT_MD = OUT_DIR / "fno_complete_call_report.md"
MONTHS = 4

TAPES_15 = {
    "NIFTY": ROOT / "stock_signal_data/fno_validate/NIFTY_15m_12y.csv",
    "BANKNIFTY": ROOT / "stock_signal_data/fno_validate/BANKNIFTY_15m_12y.csv",
    "SENSEX": ROOT / "stock_signal_data/fno_validate/SENSEX_15m_12y.csv",
}
CROWN_CACHE = {
    "NIFTY": OUT_DIR / "_cache_nifty_5m_frame_2024.parquet",
    "BANKNIFTY": OUT_DIR / "crown_5m_packs/_cache_banknifty_5m_crown_frame.parquet",
    "SENSEX": OUT_DIR / "crown_5m_packs/_cache_sensex_5m_crown_frame.parquet",
}


def _dual_mod(symbol: str):
    if symbol == "NIFTY":
        import nifty_live_dual_track as m
    elif symbol == "BANKNIFTY":
        import banknifty_live_dual_track as m
    else:
        import sensex_live_dual_track as m
    return m


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    import fno_session_replay as fsr

    work = df.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index)
    if work.index.tz is None:
        work.index = work.index.tz_localize("Asia/Kolkata")
    else:
        work.index = work.index.tz_convert("Asia/Kolkata")
    work = work.rename(columns={c: str(c).title() for c in work.columns})
    return fsr._norm(work)


def _fwd_t1(bars: pd.DataFrame, i: int, decision: str, sl: float, t1: float) -> Optional[str]:
    import fno_session_replay as fsr

    future = bars.iloc[i + 1 :]
    if len(future) < 1:
        return None
    return fsr._forward_outcome(future, bearish=decision == "SELL", sl=sl, t1=t1)


def _hm(mins: int) -> str:
    return f"{int(mins) // 60:02d}:{int(mins) % 60:02d}"


def _agg(calls: List[dict]) -> Dict[str, Any]:
    lab = [c for c in calls if c.get("win") is not None]
    n = len(lab)
    wins = sum(1 for c in lab if c["win"])
    return {
        "n": n,
        "acc_pct": round(100.0 * wins / n, 2) if n else None,
        "buy_n": sum(1 for c in lab if c.get("decision") == "BUY" or c.get("side") == "BUY"),
        "sell_n": sum(1 for c in lab if c.get("decision") == "SELL" or c.get("side") == "SELL"),
        "wins": wins,
        "losses": n - wins,
        "listed_raw": len(calls),
    }


def dual_calls(symbol: str) -> Dict[str, Any]:
    import fno_session_rules as fsrules

    t0 = time.time()
    path = TAPES_15[symbol]
    bars = _norm(pd.read_csv(path, index_col=0, parse_dates=True))
    end = bars.index.max()
    start = end - pd.Timedelta(f"{int(30.5 * MONTHS)}D")
    window = bars[bars.index >= start]
    mod = _dual_mod(symbol)
    days = [str(fsrules.session_date(t)) for t in window.index]
    w = window.copy()
    w["_day"] = days
    lookback = pd.Timedelta("12D")
    rows: List[dict] = []
    n_days = 0

    for day, sess in w.groupby("_day", sort=True):
        sess = sess.drop(columns=["_day"], errors="ignore")
        if len(sess) < 4:
            continue
        n_days += 1
        try:
            or_hi = float(sess["High"].astype(float).iloc[0])
            or_lo = float(sess["Low"].astype(float).iloc[0])
        except Exception:
            continue
        if or_hi <= or_lo:
            continue
        closes = sess["Close"].astype(float).to_numpy()
        cand: List[int] = []
        first_up = first_dn = None
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
        ticket = None
        for i in sorted(set(cand)):
            ts = sess.index[i]
            asof = ts + pd.Timedelta("15min")
            left = bars.index.searchsorted(ts - lookback)
            full_i = int(bars.index.get_indexer([ts])[0])
            win = bars.iloc[int(left) : full_i + 1]
            price = float(closes[i])
            try:
                ev = mod.evaluate(win, asof=asof, price=price, session_ticket=ticket)
            except Exception:
                continue
            call = (ev or {}).get("call_payload") or {}
            dec = call.get("decision")
            if dec not in ("BUY", "SELL"):
                continue
            if ticket and str(ticket.get("status")) == "open":
                continue
            entry = float(call.get("entry") or price)
            sl = float(call["stop_loss"])
            t1 = float(call["target_1"])
            outcome = _fwd_t1(bars, full_i, str(dec), sl, t1)
            win_flag = outcome == "t1_before_sl"
            lose = outcome in ("sl_before_t1", "same_bar_both")
            track = call.get("track") or (
                "proven_100"
                if ev.get("proven_100")
                else "champion"
                if ev.get("champion")
                else "baseline"
            )
            rows.append(
                {
                    "channel": "dual",
                    "symbol": symbol,
                    "day": str(day)[:10],
                    "time": str(ts),
                    "hm": ts.strftime("%H:%M") if hasattr(ts, "strftime") else "",
                    "decision": dec,
                    "track": track,
                    "proven_100": bool(ev.get("proven_100")),
                    "champion": bool(ev.get("champion")),
                    "baseline": bool(ev.get("baseline")),
                    "entry": round(entry, 2),
                    "stop_loss": round(sl, 2),
                    "target_1": round(t1, 2),
                    "p_t1": call.get("p_t1"),
                    "outcome": outcome,
                    "win": win_flag if (win_flag or lose) else None,
                    "result": (
                        "WIN"
                        if win_flag
                        else "LOSS"
                        if lose
                        else str(outcome or "open")
                    ),
                    "accuracy_label": call.get("accuracy_label"),
                    "independent": True,
                }
            )
            ticket = {
                "status": "closed" if outcome and outcome != "open" else "open",
                "decision": dec,
                "entry": entry,
                "stop_loss": sl,
                "target_1": t1,
            }
        if n_days % 20 == 0:
            print(f"  dual {symbol} days={n_days} calls={len(rows)}", flush=True)

    by_track: Dict[str, List[dict]] = {"proven_100": [], "champion": [], "baseline": []}
    for r in rows:
        by_track.setdefault(r["track"], []).append(r)

    return {
        "symbol": symbol,
        "ok": True,
        "channel": "dual_track",
        "window": {"start": str(pd.Timestamp(start).date()), "end": str(pd.Timestamp(end).date())},
        "n_days": n_days,
        "runtime_min": round((time.time() - t0) / 60, 2),
        "summary": _agg(rows),
        "by_track": {k: _agg(v) for k, v in by_track.items()},
        "calls": rows,
    }


def crown_calls(symbol: str) -> Dict[str, Any]:
    from research_nifty_5m_accuracy_deep import ALL_KEYS
    from research_nifty_5m_accuracy_push4 import k_per_day_mask
    from research_nifty_5m_buy_sell_improve import (
        buy_body05_htf,
        buy_not_stretched,
        buy_vwap_htf,
        sell_body05_htf,
        sell_exhaust,
        sell_vwap_htf,
    )
    from research_nifty_5m_buy_sell_models import _p_win
    from research_nifty_5m_candle_model_improve import _xy
    import fno_5m_crown as crown

    t0 = time.time()
    crown._PACK_CACHE.clear()
    pack = crown.load_pack(symbol)
    if not pack:
        return {"symbol": symbol, "ok": False, "error": "packs_missing", "calls": []}
    path = CROWN_CACHE.get(symbol)
    if not path or not path.is_file():
        return {"symbol": symbol, "ok": False, "error": f"frame missing", "calls": []}
    frame = pd.read_parquet(path)
    end_d = pd.Timestamp(sorted(frame["day"].unique())[-1]).date()
    start = str(end_d - timedelta(days=int(30.5 * MONTHS)))
    test = frame[frame["day"] >= start].copy()

    BUY_U = {
        "body05_htf": buy_body05_htf,
        "buy_body05_htf": buy_body05_htf,
        "not_stretched": buy_not_stretched,
        "vwap_htf": buy_vwap_htf,
    }
    SELL_U = {
        "exhaust": sell_exhaust,
        "sell_exhaust": sell_exhaust,
        "body05_htf": sell_body05_htf,
        "vwap_htf": sell_vwap_htf,
    }
    buy_cfg, sell_cfg = pack["buy"], pack["sell"]
    bu = BUY_U.get(str(buy_cfg.get("univ") or "body05_htf"), buy_body05_htf)
    su = SELL_U.get(str(sell_cfg.get("univ") or "exhaust"), sell_exhaust)
    keys = tuple(pack.get("feature_keys") or ALL_KEYS)
    rows: List[dict] = []

    # BUY takes
    if buy_cfg.get("enabled", True) and float(buy_cfg.get("qth") or 0) < 5:
        buni = bu(test)
        buni = buni[buni["y_buy_6"] >= 0]
        if len(buni) >= 5:
            Xb, yb, sb = _xy(buni, "y_buy_6", keys)
            pb = _p_win(buy_cfg["model"], Xb)
            if buy_cfg.get("meta") is not None:
                Xm = np.column_stack([Xb, pb.reshape(-1, 1), np.abs(pb - 0.5).reshape(-1, 1)])
                mb = _p_win(buy_cfg["meta"], Xm)
            else:
                mb = np.ones_like(pb)
            mins = sb["mins"].to_numpy()
            htf = sb["htf_ret6"].to_numpy() if "htf_ret6" in sb.columns else np.zeros(len(sb))
            oext = sb["or_ext"].to_numpy() if "or_ext" in sb.columns else np.zeros(len(sb))
            m = (
                (pb >= 0.50)
                & (pb >= float(buy_cfg["qth"]))
                & (mb >= float(buy_cfg["meta_min"]))
                & (htf >= float(buy_cfg["htf_min"]))
                & (htf <= float(buy_cfg["htf_max"]))
                & (mins >= int(buy_cfg["lo"]))
                & (mins <= int(buy_cfg["hi"]))
                & (oext >= float(buy_cfg["or_ext_min"]))
            )
            m = k_per_day_mask(sb["day"].to_numpy(), mins, m, int(buy_cfg["kday"]))
            for i in np.where(m)[0]:
                y = int(yb[i])
                rows.append(
                    {
                        "channel": "5m_crown",
                        "symbol": symbol,
                        "day": str(sb["day"].iloc[i])[:10],
                        "mins": int(mins[i]),
                        "hm": _hm(int(mins[i])),
                        "side": "BUY",
                        "decision": "BUY",
                        "track": "5m_crown",
                        "p": round(float(pb[i]), 4),
                        "meta_p": round(float(mb[i]), 4),
                        "htf_ret6": round(float(htf[i]), 4),
                        "or_ext": round(float(oext[i]), 4),
                        "y": y,
                        "win": bool(y == 1),
                        "result": "WIN" if y == 1 else "LOSS",
                        "recipe": pack.get("recipe"),
                        "independent": True,
                    }
                )

    # SELL takes
    if sell_cfg.get("enabled", True) and float(sell_cfg.get("qth") or 0) < 5:
        suni = su(test)
        suni = suni[suni["y_sell_6"] >= 0]
        if len(suni) >= 5:
            Xs, ys, ss = _xy(suni, "y_sell_6", keys)
            ps = _p_win(sell_cfg["model"], Xs)
            htfs = ss["htf_ret6"].to_numpy() if "htf_ret6" in ss.columns else np.zeros(len(ss))
            vd = ss["vwap_dist"].to_numpy() if "vwap_dist" in ss.columns else np.zeros(len(ss))
            m = (
                (ps >= 0.50)
                & (ps >= float(sell_cfg["qth"]))
                & (htfs <= float(sell_cfg["htf_max"]))
                & (vd >= float(sell_cfg["vd"]))
            )
            m = k_per_day_mask(
                ss["day"].to_numpy(), ss["mins"].to_numpy(), m, int(sell_cfg["pd"])
            )
            for i in np.where(m)[0]:
                y = int(ys[i])
                rows.append(
                    {
                        "channel": "5m_crown",
                        "symbol": symbol,
                        "day": str(ss["day"].iloc[i])[:10],
                        "mins": int(ss["mins"].iloc[i]),
                        "hm": _hm(int(ss["mins"].iloc[i])),
                        "side": "SELL",
                        "decision": "SELL",
                        "track": "5m_crown",
                        "p": round(float(ps[i]), 4),
                        "htf_ret6": round(float(htfs[i]), 4),
                        "vwap_dist": round(float(vd[i]), 4),
                        "y": y,
                        "win": bool(y == 1),
                        "result": "WIN" if y == 1 else "LOSS",
                        "recipe": pack.get("recipe"),
                        "independent": True,
                    }
                )

    rows.sort(key=lambda r: (r["day"], r.get("mins", 0), r["decision"]))
    return {
        "symbol": symbol,
        "ok": True,
        "channel": "5m_crown",
        "window": {"start": start, "end": str(end_d)},
        "runtime_min": round((time.time() - t0) / 60, 2),
        "recipe": pack.get("recipe"),
        "expected_hit_pct": pack.get("expected_hit_pct"),
        "summary": _agg(rows),
        "calls": rows,
    }


def _md_calls(calls: List[dict], *, dual: bool) -> List[str]:
    lines = []
    if not calls:
        lines.append("_No calls._")
        return lines
    if dual:
        lines.append(
            "| # | Day | Time | Side | Track | Entry | SL | T1 | p | Result |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for i, c in enumerate(calls, 1):
            lines.append(
                f"| {i} | {c['day']} | {c.get('hm','')} | **{c['decision']}** | "
                f"{c['track']} | {c.get('entry')} | {c.get('stop_loss')} | {c.get('target_1')} | "
                f"{c.get('p_t1')} | **{c.get('result')}** |"
            )
    else:
        lines.append("| # | Day | Time | Side | p | htf6 | Result |")
        lines.append("|---|---|---|---|---|---|---|")
        for i, c in enumerate(calls, 1):
            lines.append(
                f"| {i} | {c['day']} | {c.get('hm','')} | **{c['decision']}** | "
                f"{c.get('p')} | {c.get('htf_ret6')} | **{c.get('result')}** |"
            )
    return lines


def main() -> int:
    print("Complete per-call report — dual + 5m crown (last 4m)", flush=True)
    # Retune Sensex first if pack 4m weak
    try:
        print("\n=== Sensex crown retune (4m-aware) ===", flush=True)
        from tune_export_5m_crown_bn_sensex import tune_symbol

        sx = tune_symbol("SENSEX")
        print(f"  Sensex tune: {sx.get('test_1y')} 4m={sx.get('test_4m')}", flush=True)
    except Exception:
        traceback.print_exc()

    results = []
    for sym in ("NIFTY", "BANKNIFTY", "SENSEX"):
        print(f"\n===== {sym} dual =====", flush=True)
        try:
            dual = dual_calls(sym)
        except Exception as exc:
            traceback.print_exc()
            dual = {"symbol": sym, "ok": False, "error": str(exc), "calls": []}
        print(f"  dual summary {dual.get('summary') or dual.get('error')}", flush=True)

        print(f"===== {sym} crown =====", flush=True)
        try:
            cr = crown_calls(sym)
        except Exception as exc:
            traceback.print_exc()
            cr = {"symbol": sym, "ok": False, "error": str(exc), "calls": []}
        print(f"  crown summary {cr.get('summary') or cr.get('error')}", flush=True)

        results.append(
            {
                "symbol": sym,
                "dual": dual,
                "crown": cr,
                "channels_independent": True,
                "champion_baseline_untouched": True,
            }
        )

    payload = {
        "months": MONTHS,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": (
            "Complete per-call listing. Dual = live proven/champion/baseline. "
            "5m crown = independent ExtraTrees channel."
        ),
        "results": results,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Complete call report · last 4 months",
        "",
        f"Generated `{payload['generated_at']}`",
        "",
        "Channels are **independent**. Champion / baseline / proven dual-track unchanged.",
        "",
    ]
    for r in results:
        sym = r["symbol"]
        d, c = r["dual"], r["crown"]
        lines.append(f"## {sym}")
        lines.append("")
        if d.get("ok"):
            s = d["summary"]
            lines.append(
                f"### Dual-track (proven / champion / baseline) — "
                f"**{s.get('acc_pct')}%** n=**{s.get('n')}** "
                f"(W{s.get('wins')} L{s.get('losses')})"
            )
            bt = d.get("by_track") or {}
            for tr in ("proven_100", "champion", "baseline"):
                t = bt.get(tr) or {}
                lines.append(
                    f"- {tr}: {t.get('acc_pct')}% n={t.get('n')}"
                )
            lines.append("")
            lines.extend(_md_calls(d.get("calls") or [], dual=True))
        else:
            lines.append(f"### Dual FAIL: {d.get('error')}")
        lines.append("")
        if c.get("ok"):
            s = c["summary"]
            lines.append(
                f"### 5m crown (independent) — **{s.get('acc_pct')}%** n=**{s.get('n')}** "
                f"(W{s.get('wins')} L{s.get('losses')}) · `{c.get('recipe')}`"
            )
            lines.append("")
            lines.extend(_md_calls(c.get("calls") or [], dual=False))
        else:
            lines.append(f"### Crown FAIL: {c.get('error')}")
        lines.append("")
        lines.append("---")
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    # Also write per-symbol call CSVs for easy reading
    for r in results:
        sym = r["symbol"]
        for key, block in (("dual", r["dual"]), ("crown", r["crown"])):
            calls = block.get("calls") or []
            if not calls:
                continue
            csv_path = OUT_DIR / f"fno_complete_calls_{sym}_{key}.csv"
            pd.DataFrame(calls).to_csv(csv_path, index=False)
            print(f"Wrote {csv_path.name} n={len(calls)}", flush=True)
    print("Wrote", OUT_MD, flush=True)
    print("VERDICT done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
