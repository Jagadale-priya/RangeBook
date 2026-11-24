"""Diagnose picker hit rates + train simple non-lookahead filter toward 100%."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401,E402

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_daily_must_100 as dm  # noqa: E402
import research_nifty_1m_daily_must_100_refine as R  # noqa: E402


def main() -> int:
    raw = base.load_existing_1m()
    end = raw.index.max()
    test_hi = end.strftime("%Y-%m-%d")
    test_lo_ts = end - pd.Timedelta(days=92)
    test_lo = test_lo_ts.strftime("%Y-%m-%d")
    cal_hi = (test_lo_ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    cal_lo = (test_lo_ts - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    raw = raw[raw.index >= pd.Timestamp(cal_lo, tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = dm.add_rsi(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    print("collect cands…", flush=True)
    cal_by = R.collect_all_day_cands(df, cal_lo, cal_hi, (560, 750))
    test_by = R.collect_all_day_cands(df, test_lo, test_hi, (560, 750))
    kind, params = "atr", {"sl_k": 1.5, "t1_k": 0.6}

    pickers = [
        "oracle",
        "trend_pattern",
        "trend_first",
        "trend_best_body",
        "rsi_trend",
        "best_score_align",
        "late_trend",
        "mfe_proxy_mom",
        "first_pattern",
        "first",
    ]
    print("\n=== baseline pickers atr_1.5_0.6 ===", flush=True)
    for p in pickers:
        a = R.eval_picker(cal_by, h, l, c, kind, params, p)
        t = R.eval_picker(test_by, h, l, c, kind, params, p)
        print(
            f"{p:18} cal {a['hit_pct']:6.2f}% miss={len(a['miss_days']):3d} | "
            f"l3m {t['hit_pct']:6.2f}% miss={t['miss_days'][:6]}",
            flush=True,
        )

    # Build labeled rows on calibrate for filter learning
    print("\n=== learn filter from calibrate winners ===", flush=True)
    rows = []
    for day, cands in cal_by.items():
        for e in cands:
            if e.get("is_probe"):
                continue
            win = R.cand_wins(e, h, l, c, kind, params)
            rows.append(
                {
                    "day": day,
                    "win": int(win),
                    "trend_align": e["trend_align"],
                    "score": e["score"],
                    "mins": e["mins"],
                    "rsi": e["rsi_14"],
                    "body": abs(e["body_frac"]),
                    "drift_abs": abs(e["drift"]),
                    "session_chg": e["session_chg"],
                    "side_buy": 1 if e["decision"] == "BUY" else 0,
                    "is_pat": 0 if str(e["primary"]).startswith("_") else 1,
                    "atr": e["atr"],
                    "sl_sess": e["sl_sess"],
                    "primary": e["primary"],
                }
            )
    X = pd.DataFrame(rows)
    print(f"labeled {len(X)} cands · win_rate={X['win'].mean()*100:.1f}%", flush=True)
    for col in ["trend_align", "is_pat", "side_buy"]:
        g = X.groupby(col)["win"].mean() * 100
        print(f"  {col}: {dict(g.round(1))}", flush=True)

    # Score function: prefer features enriched in winners
    w = X[X["win"] == 1]
    l_ = X[X["win"] == 0]
    print(
        f"  winners mins med={w['mins'].median():.0f} rsi={w['rsi'].median():.1f} "
        f"score={w['score'].median():.0f} body={w['body'].median():.2f}",
        flush=True,
    )
    print(
        f"  losers  mins med={l_['mins'].median():.0f} rsi={l_['rsi'].median():.1f} "
        f"score={l_['score'].median():.0f} body={l_['body'].median():.2f}",
        flush=True,
    )

    def rank_score(e):
        s = 0.0
        if e.get("is_probe"):
            return -1e9
        if not str(e["primary"]).startswith("_"):
            s += 50 + e["score"]
        s += 30 * e["trend_align"]
        s += 10 * abs(e["body_frac"])
        # mid-morning bonus (oracle often ~10:00-11:30)
        if 580 <= e["mins"] <= 700:
            s += 25
        elif 560 <= e["mins"] < 580:
            s += 5
        # RSI not extreme against side
        if e["decision"] == "BUY" and e["rsi_14"] <= 65:
            s += 8
        if e["decision"] == "SELL" and e["rsi_14"] >= 35:
            s += 8
        # open drift alignment magnitude
        if e["trend_align"]:
            s += min(abs(e["drift"]) / max(e["atr"], 1e-6), 5.0) * 3
        return s

    def pick_ranked(cands):
        pool = [e for e in cands if not e.get("is_probe")]
        if not pool:
            pool = list(cands)
        return max(pool, key=rank_score)

    def eval_custom(by_day, picker_fn):
        miss = []
        wins = 0
        n = 0
        for day, cands in sorted(by_day.items()):
            e = picker_fn(cands)
            n += 1
            if e is None or not R.cand_wins(e, h, l, c, kind, params):
                miss.append(day)
            else:
                wins += 1
        return round(100.0 * wins / n, 2), miss

    a_hit, a_miss = eval_custom(cal_by, pick_ranked)
    t_hit, t_miss = eval_custom(test_by, pick_ranked)
    print(
        f"\nranked_v1          cal {a_hit:6.2f}% miss={len(a_miss):3d} | "
        f"l3m {t_hit:6.2f}% miss={t_miss[:8]}",
        flush=True,
    )

    # first pattern with rank_score >= threshold (walk chronologically)
    def pick_first_above(thresh):
        def _fn(cands):
            pool = sorted([e for e in cands if not e.get("is_probe")], key=lambda x: x["mins"])
            for e in pool:
                if rank_score(e) >= thresh:
                    return e
            return pool[-1] if pool else None

        return _fn

    for th in [80, 100, 120, 140, 160]:
        a_hit, a_miss = eval_custom(cal_by, pick_first_above(th))
        t_hit, t_miss = eval_custom(test_by, pick_first_above(th))
        print(
            f"first_rank>={th:<3}  cal {a_hit:6.2f}% miss={len(a_miss):3d} | "
            f"l3m {t_hit:6.2f}% miss={t_miss[:6]}",
            flush=True,
        )

    # best rank in early / mid windows
    def pick_best_in_window(lo, hi):
        def _fn(cands):
            pool = [e for e in cands if not e.get("is_probe") and lo <= e["mins"] <= hi]
            if not pool:
                pool = [e for e in cands if not e.get("is_probe")]
            return max(pool, key=rank_score) if pool else None

        return _fn

    for lo, hi in [(560, 630), (575, 660), (580, 700), (590, 720), (560, 750)]:
        a_hit, a_miss = eval_custom(cal_by, pick_best_in_window(lo, hi))
        t_hit, t_miss = eval_custom(test_by, pick_best_in_window(lo, hi))
        print(
            f"best_rank_{lo}_{hi} cal {a_hit:6.2f}% miss={len(a_miss):3d} | "
            f"l3m {t_hit:6.2f}% miss={t_miss[:6]}",
            flush=True,
        )

    # quality patterns only (top priority) + trend + mid window
    TOP = set(dm.PRIORITY[:18])

    def pick_top_trend(cands):
        pool = [
            e
            for e in cands
            if not e.get("is_probe")
            and e["primary"] in TOP
            and e["trend_align"] == 1
            and 575 <= e["mins"] <= 720
        ]
        if not pool:
            pool = [e for e in cands if not e.get("is_probe") and e["trend_align"] == 1]
        if not pool:
            pool = [e for e in cands if not e.get("is_probe")]
        return sorted(pool, key=lambda x: (-x["score"], x["mins"]))[0] if pool else None

    a_hit, a_miss = eval_custom(cal_by, pick_top_trend)
    t_hit, t_miss = eval_custom(test_by, pick_top_trend)
    print(
        f"top_trend_mid     cal {a_hit:6.2f}% miss={len(a_miss):3d} | "
        f"l3m {t_hit:6.2f}% miss={t_miss[:8]}",
        flush=True,
    )

    # Among day's cands, pick the one with max pre-entry "edge":
    # edge ~= trend_align * score * body — still no MAE
    def pick_max_edge(cands):
        pool = [e for e in cands if not e.get("is_probe")]
        if not pool:
            return None

        def edge(e):
            return (
                (2 if e["trend_align"] else 0)
                + (1 if e["primary"] in TOP else 0)
                + (1 if 580 <= e["mins"] <= 700 else 0)
            ) * 100 + e["score"] + 20 * abs(e["body_frac"])

        return max(pool, key=edge)

    a_hit, a_miss = eval_custom(cal_by, pick_max_edge)
    t_hit, t_miss = eval_custom(test_by, pick_max_edge)
    print(
        f"max_edge          cal {a_hit:6.2f}% miss={len(a_miss):3d} | "
        f"l3m {t_hit:6.2f}% miss={t_miss[:8]}",
        flush=True,
    )

    # How often does max_edge / ranked pick a winner when oracle exists?
    # Coverage of winners: for each day, fraction of non-probe cands that win
    fracs = []
    for day, cands in cal_by.items():
        pool = [e for e in cands if not e.get("is_probe")]
        if not pool:
            continue
        nw = sum(1 for e in pool if R.cand_wins(e, h, l, c, kind, params))
        fracs.append(nw / len(pool))
    print(
        f"\ncal: mean fraction winning cands/day={np.mean(fracs)*100:.1f}% "
        f"· days with ≥1 non-probe win="
        f"{sum(1 for f in fracs if f > 0)}/{len(fracs)}",
        flush=True,
    )

    # non-probe oracle
    def pick_oracle_noprobe(cands):
        pool = [e for e in cands if not e.get("is_probe")]
        return R.pick_oracle(pool or cands, h, l, c, kind, params)

    a_hit, a_miss = eval_custom(cal_by, pick_oracle_noprobe)
    t_hit, t_miss = eval_custom(test_by, pick_oracle_noprobe)
    print(
        f"oracle_noprobe    cal {a_hit:6.2f}% miss={len(a_miss):3d} | "
        f"l3m {t_hit:6.2f}% miss={t_miss[:8]}",
        flush=True,
    )
    print("DONE diag", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
