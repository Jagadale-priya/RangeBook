"""RESEARCH ONLY — Oracle T15·EMA34 calls vs model scores on 1m/5m/10m/15m.

For each Oracle T15 entry in the last 5 sessions, score the trained F&O model
(+ session head) on candles resampled to 1m, 5m, 10m, 15m at that as-of time.

  python -u prod_live/tests/builders/_diag_oracle_t15_vs_model_scores.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "app" / "fno"))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import fno_scalper_1m as scalper  # noqa: E402
import fno_model  # noqa: E402
import fno_session_model as smodel  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ORACLE_T15_VS_MODEL_SCORES_LAST5D.md"
REPORT_JSON = OUT / "NIFTY_1M_ORACLE_T15_VS_MODEL_SCORES_LAST5D.json"

T15 = 15.0
SESSIONS = 5
LOAD_DAYS = 12
INTERVALS = (
    ("1m", 1),
    ("5m", 5),
    ("10m", 10),
    ("15m", 15),
)


def _resample(df1: pd.DataFrame, mins: int) -> pd.DataFrame:
    if mins <= 1:
        return df1.copy()
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in df1.columns:
        agg["Volume"] = "sum"
    out = df1.resample(f"{mins}min", label="left", closed="left").agg(agg)
    return out.dropna(subset=["Open", "High", "Low", "Close"])


def _slice_asof(bars: pd.DataFrame, asof) -> pd.DataFrame:
    ts = pd.Timestamp(asof)
    if ts.tzinfo is None:
        ts = ts.tz_localize("Asia/Kolkata")
    else:
        ts = ts.tz_convert("Asia/Kolkata")
    # inclusive: bars whose open <= asof
    return bars[bars.index <= ts]


def score_tf(
    bars_tf: pd.DataFrame,
    asof,
    *,
    pack: dict,
    side: str,
    interval_label: str,
) -> Dict[str, Any]:
    work = _slice_asof(bars_tf, asof)
    if work is None or len(work) < 30:
        return {
            "interval": interval_label,
            "available": False,
            "reason": "short",
            "n_bars": 0 if work is None else len(work),
        }
    force = 1.0 if side == "BUY" else -1.0
    try:
        head = fno_model.infer(
            work,
            model_pack=pack,
            force_side=force,
            symbol="NIFTY",
            asof=work.index[-1],
        )
    except Exception as exc:
        return {
            "interval": interval_label,
            "available": False,
            "reason": f"infer:{exc}",
            "n_bars": len(work),
        }

    # session / candle score on this TF (rule or trained head if we fit quick)
    try:
        sess = smodel.infer(work, None, interval="15minute" if "15" in interval_label else "5minute")
    except Exception:
        sess = {"available": False}
    feat = (sess.get("features") or {}) if isinstance(sess, dict) else {}
    candle = feat.get("candle_score")

    p_t1 = head.get("p_t1")
    decision = str(head.get("decision") or "HOLD").upper()
    # agreement vs Oracle side
    agree = None
    if decision in ("BUY", "SELL"):
        agree = decision == side
    elif p_t1 is not None:
        # forced-side p_t1: high = model likes that side
        agree = float(p_t1) >= 0.55

    return {
        "interval": interval_label,
        "available": bool(head.get("available")),
        "n_bars": len(work),
        "bar_hm": work.index[-1].strftime("%H:%M"),
        "p_t1": round(float(p_t1), 4) if p_t1 is not None else None,
        "p_t1_pct": round(100.0 * float(p_t1), 1) if p_t1 is not None else None,
        "p_up": head.get("p_up"),
        "decision": decision,
        "source": head.get("source"),
        "agree": agree,
        "candle_score": round(float(candle), 2) if candle is not None else None,
        "sess_p_up": sess.get("p_up") if isinstance(sess, dict) else None,
        "sess_source": sess.get("source") if isinstance(sess, dict) else None,
    }


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("Oracle T15 vs model scores · last 5 sessions · 1m/5m/10m/15m", flush=True)

    raw, note = scalper.load_1m_bars("NIFTY", LOAD_DAYS)
    if raw is None or raw.empty:
        print("no bars", note, flush=True)
        return 1
    df, events, err = scalper._get_prepared_frame("NIFTY", LOAD_DAYS, raw, note)
    if df is None or events is None:
        print("prepare failed", err, flush=True)
        return 1

    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-SESSIONS:])
    days_sorted = sorted(keep)
    print(f"sessions {days_sorted[0]}→{days_sorted[-1]} ({len(days_sorted)}) events={len(events)}", flush=True)

    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    idx = df.index

    # Oracle T15 causal entries in window (same as live notify universe)
    oracle_rows = []
    for e in events:
        i = int(e.get("full_i") or e.get("i") or -1)
        if i < 0 or i >= len(c):
            continue
        d = str(idx[i].date())
        if d not in keep:
            continue
        side = str(e.get("decision") or "")
        if side not in ("BUY", "SELL"):
            continue
        mins = int(idx[i].hour * 60 + idx[i].minute)
        if not (9 * 60 + 30 <= mins <= 14 * 60 + 30):
            continue
        entry = float(e.get("entry") or c[i])
        ok, reason, exit_px, j, pts = scalper.path_ma_trail(h, l, c, ema34, i, side, T15)
        oracle_rows.append(
            {
                "i": i,
                "day": d,
                "hm": idx[i].strftime("%H:%M"),
                "mins": mins,
                "side": side,
                "entry": round(entry, 2),
                "primary": e.get("primary"),
                "t15_win": bool(ok),
                "reason": reason,
                "pts": round(float(pts), 2) if pts is not None else None,
                "asof": idx[i],
            }
        )
    oracle_rows.sort(key=lambda x: (x["day"], x["mins"]))
    # 1/day first + all list
    one = []
    seen = set()
    for r in oracle_rows:
        if r["day"] not in seen:
            seen.add(r["day"])
            one.append(r)
    print(f"oracle entries: {len(oracle_rows)}  1/day: {len(one)}", flush=True)

    pack = fno_model.load(symbol="NIFTY")
    print(f"model pack available={pack.get('available')} ver={pack.get('model_version')}", flush=True)

    # Pre-resample full frame once
    bars_by_tf = {}
    for label, m in INTERVALS:
        bars_by_tf[label] = _resample(df, m)
        print(f"  {label}: {len(bars_by_tf[label])} bars", flush=True)

    # Score every oracle entry (cap to keep report readable: all 1/day + up to 40 all)
    focus = list(one)
    extra = [r for r in oracle_rows if r not in one][:35]
    to_score = focus + extra

    scored = []
    for k, r in enumerate(to_score):
        if k and k % 10 == 0:
            print(f"  scored {k}/{len(to_score)}", flush=True)
        tf_scores = {}
        for label, _m in INTERVALS:
            tf_scores[label] = score_tf(
                bars_by_tf[label],
                r["asof"],
                pack=pack,
                side=r["side"],
                interval_label=label,
            )
        scored.append({**r, "asof": str(r["asof"]), "scores": tf_scores, "is_first": r in one})

    # Summary: agreement rates by TF among T15 winners vs losers
    def agree_rate(rows, tf, winners_only=None):
        xs = rows
        if winners_only is True:
            xs = [r for r in rows if r["t15_win"]]
        elif winners_only is False:
            xs = [r for r in rows if not r["t15_win"]]
        vals = [r["scores"][tf].get("agree") for r in xs if r["scores"].get(tf, {}).get("agree") is not None]
        if not vals:
            return None, 0
        return round(100.0 * sum(1 for v in vals if v) / len(vals), 1), len(vals)

    def avg_pt1(rows, tf, winners_only=None):
        xs = rows
        if winners_only is True:
            xs = [r for r in rows if r["t15_win"]]
        elif winners_only is False:
            xs = [r for r in rows if not r["t15_win"]]
        vals = [r["scores"][tf].get("p_t1") for r in xs if r["scores"].get(tf, {}).get("p_t1") is not None]
        if not vals:
            return None, 0
        return round(100.0 * float(np.mean(vals)), 1), len(vals)

    lines = [
        "# NIFTY — Oracle T15·EMA34 vs **model scores** (last 5 sessions)",
        "",
        "> When Oracle T15 fires, what was the trained model `p_t1` / decision",
        "> on **1m · 5m · 10m · 15m** candles at that same time?",
        "",
        f"Sessions **{days_sorted[0]} → {days_sorted[-1]}**. Oracle entries **{len(oracle_rows)}** · scored **{len(scored)}**.",
        f"Model: `fno_model` NIFTY pack available=**{pack.get('available')}** · {pack.get('model_version')}.",
        f"Note: {note or err or '—'}",
        "",
        "## How to read",
        "",
        "- **Oracle** = textbook pattern entry · EMA34 trail · T15 win/loss",
        "- **p(T1)%** = model probability for Oracle’s side (force_side)",
        "- **decision** = model ticket side (BUY/SELL/HOLD)",
        "- **agree** = model decision matches Oracle side (or p(T1)≥55% if HOLD)",
        "- **candle** = session-model candle_score feature on that TF",
        "",
        "## 1) Average model p(T1) when Oracle wins vs loses",
        "",
        "| TF | Win avg p(T1)% | n | Lose avg p(T1)% | n | Agree% on wins | Agree% on loses |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, _ in INTERVALS:
        aw, nw = avg_pt1(scored, label, True)
        al, nl = avg_pt1(scored, label, False)
        gw, ngw = agree_rate(scored, label, True)
        gl, ngl = agree_rate(scored, label, False)
        lines.append(f"| **{label}** | **{aw}** | {nw} | {al} | {nl} | {gw} | {gl} |")

    lines += [
        "",
        "## 2) First Oracle call each day (1/day) + multi-TF scores",
        "",
    ]
    firsts = [r for r in scored if r.get("is_first")]
    for r in firsts:
        lines += [
            f"### {r['day']} {r['hm']} · **{r['side']}** @ **{r['entry']}** · T15={'✓' if r['t15_win'] else '✗'} ({r['reason']}, {r['pts']})",
            f"Pattern: `{r['primary']}`",
            "",
            "| TF | bar | p(T1)% | decision | agree | candle | sess p_up | source |",
            "|---|---|---:|---|---|---:|---:|---|",
        ]
        for label, _ in INTERVALS:
            s = r["scores"][label]
            if not s.get("available"):
                lines.append(f"| {label} | — | — | — | — | — | — | {s.get('reason')} |")
                continue
            lines.append(
                f"| **{label}** | {s.get('bar_hm')} | **{s.get('p_t1_pct')}** | {s.get('decision')} | "
                f"{'Y' if s.get('agree') else 'N'} | {s.get('candle_score')} | {s.get('sess_p_up')} | {s.get('source')} |"
            )
        lines.append("")

    lines += [
        "## 3) All scored Oracle entries (compact)",
        "",
        "| Day | HM | Side | Entry | T15 | 1m p% | 5m p% | 10m p% | 15m p% | 15m dec | agree15 |",
        "|---|---|---|---:|---|---:|---:|---:|---:|---|---|",
    ]
    for r in scored:
        s1, s5, s10, s15 = (r["scores"][x] for x in ("1m", "5m", "10m", "15m"))
        lines.append(
            f"| {r['day']} | {r['hm']} | **{r['side']}** | {r['entry']} | "
            f"{'Y' if r['t15_win'] else 'N'} | "
            f"{s1.get('p_t1_pct')} | {s5.get('p_t1_pct')} | {s10.get('p_t1_pct')} | {s15.get('p_t1_pct')} | "
            f"{s15.get('decision')} | {'Y' if s15.get('agree') else 'N'} |"
        )

    # Simple signal: if 15m p_t1 >= thresh, does Oracle win more?
    lines += ["", "## 4) Filter Oracle by 15m model p(T1) — does accuracy rise?", ""]
    lines += ["| 15m p(T1) ≥ | n | Oracle T15% |", "|---:|---:|---:|"]
    for thr in (0.50, 0.55, 0.60, 0.65, 0.70):
        hit = [r for r in scored if (r["scores"]["15m"].get("p_t1") or 0) >= thr]
        if not hit:
            lines.append(f"| {int(thr*100)}% | 0 | — |")
            continue
        pct = round(100.0 * sum(1 for r in hit if r["t15_win"]) / len(hit), 1)
        lines.append(f"| {int(thr*100)}% | {len(hit)} | **{pct}** |")

    lines += [
        "",
        "## Takeaway",
        "",
        "- If winners show **higher** multi-TF p(T1) than losers → model can filter Oracle noise.",
        "- If similar → model score at call time is **not** separating good Oracle entries (last 5d).",
        "- 15m is the dual-track native TF; 1m/5m/10m are the same head on resampled bars (exploratory).",
        "",
        f"_Generated in {time.time()-t0:.1f}s._",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "sessions": days_sorted,
                "n_oracle": len(oracle_rows),
                "scored": scored,
                "model": {"available": pack.get("available"), "version": pack.get("model_version")},
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {REPORT}", flush=True)
    print(f"done in {time.time()-t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
