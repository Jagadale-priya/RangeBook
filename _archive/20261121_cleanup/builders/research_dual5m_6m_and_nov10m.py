"""RESEARCH — 5m dual-train unique calls (last 6m incl Nov) + 10m Nov list.

Fast path: train on 5m OR-break (bar features), score 6m window, day-unique lists.
10m Nov taken from prior P2G compare (no full re-expand).

  python -u prod_live/tests/builders/research_dual5m_6m_and_nov10m.py
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
warnings.filterwarnings("ignore")
import path_setup  # noqa: F401,E402

from accuracy_max_6m import _agg  # noqa: E402
from research_100pct_deeper_more_calls import (  # noqa: E402
    bestp_day,
    first_day,
    gap_map,
    is_perfect,
    union_unique_days,
)
from research_confirm_dual_tf_deep import _clip, _hm_mins, _side  # noqa: E402
from research_dual10m_proven100 import (  # noqa: E402
    FEAT_NAMES,
    RISK,
    _day,
    _hm,
    _norm,
    candle_feats,
    fwd_path,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_XY5 = LEDGER / "_cache_dual5m_xy_research.json"
PACK_DIR = LEDGER / "nifty_side_models_5m_research"
PACK_DIR.mkdir(parents=True, exist_ok=True)
TAPE5 = ROOT / "stock_signal_data/fno_validate/NIFTY_5m_kite.csv"
COMPARE_NOV = OUT / "COMPARE_P2F_P2G_UNIQUE_NOV.json"

END = "2026-11-15"
START_6M = (pd.Timestamp(END) - timedelta(days=183)).strftime("%Y-%m-%d")
NOV_A, NOV_B = "2026-11-01", END
FREEZE = "2024-09-10"
OR_BARS_5M = 6  # first ~30m on 5m tape


def build_tickets_5m(bars5: pd.DataFrame, gaps: Dict[str, float]) -> List[dict]:
    idx_map = {ts: i for i, ts in enumerate(bars5.index)}
    day_key = pd.Index([_day(ts) for ts in bars5.index])
    groups = bars5.groupby(day_key, sort=True)
    days = list(groups.groups.keys())
    out: List[dict] = []
    t0 = time.time()
    for di, day in enumerate(days, 1):
        if di % 250 == 0:
            print(f"    5m tickets {di}/{len(days)} n={len(out)} ({time.time()-t0:.0f}s)", flush=True)
        sess = groups.get_group(day)
        if len(sess) < OR_BARS_5M + 4:
            continue
        or_hi = float(sess["High"].iloc[:OR_BARS_5M].max())
        or_lo = float(sess["Low"].iloc[:OR_BARS_5M].min())
        or_w = or_hi - or_lo
        if or_w < 8:
            continue
        day_open = float(sess["Open"].iloc[0])
        first_up = first_dn = None
        closes = sess["Close"].astype(float).values
        for pos in range(OR_BARS_5M, len(sess)):
            c = float(closes[pos])
            if first_up is None and c > or_hi:
                first_up = pos
            if first_dn is None and c < or_lo:
                first_dn = pos
            if first_up is not None and first_dn is not None:
                break
        for side, pos in (("BUY", first_up), ("SELL", first_dn)):
            if pos is None:
                continue
            first = 0.0
            if side == "BUY" and (first_dn is None or (first_up is not None and first_up <= first_dn)):
                first = 1.0
            if side == "SELL" and (first_up is None or (first_dn is not None and first_dn < first_up)):
                first = 1.0
            ts = sess.index[pos]
            full_i = idx_map.get(ts)
            if full_i is None:
                continue
            left = max(0, full_i - 48)
            window = bars5.iloc[left : full_i + 1]
            entry = float(bars5["Close"].iloc[full_i])
            if side == "BUY":
                sl, t1 = entry - RISK, entry + RISK
                or_ext = (entry - or_hi) / or_w
            else:
                sl, t1 = entry + RISK, entry - RISK
                or_ext = (or_lo - entry) / or_w
            win_f, outcome, pts = fwd_path(bars5, full_i, side, entry, sl, t1)
            if outcome not in ("t1_before_sl", "sl_before_t1"):
                continue
            cf = candle_feats(window)
            sess_so_far = sess.iloc[: pos + 1]
            hi = sess_so_far["High"].astype(float)
            lo = sess_so_far["Low"].astype(float)
            cl = sess_so_far["Close"].astype(float)
            typ = (hi + lo + cl) / 3.0
            vwap = float(typ.mean())
            atr = float((hi - lo).tail(14).mean())
            hm = _hm(ts)
            hh, mm = map(int, hm.split(":"))
            mins = hh * 60 + mm
            feat = {
                **cf,
                "vwap_dist": (entry - vwap) / max(entry, 1.0) * 100.0,
                "range_pos": (entry - float(lo.min())) / max(float(hi.max() - lo.min()), 1e-6),
                "or_width": or_w,
                "or_ext": float(or_ext),
                "mins_entry": float(mins),
                "first_break": float(first),
                "gap_pct": float(gaps.get(day) or 0.0),
                "session_chg": (entry - day_open) / max(day_open, 1.0) * 100.0,
                "atr_ratio": atr / RISK if RISK else 0.0,
                "side": 1.0 if side == "BUY" else -1.0,
            }
            x = [float(feat.get(k, 0.0)) for k in FEAT_NAMES]
            out.append(
                {
                    "day": day,
                    "hm": hm,
                    "decision": side,
                    "win": bool(win_f),
                    "points": round(float(pts), 1),
                    "outcome": outcome,
                    "entry": round(entry, 2),
                    "stop_loss": round(sl, 2),
                    "target_1": round(t1, 2),
                    "p_t1": None,
                    "track": "dual5m",
                    "tf": "5m",
                    "first_break": bool(first),
                    "x": x,
                    "y": 1 if win_f else 0,
                }
            )
    return out


class IdentityOrFlip:
    """joblib score map. flip=True when the freeze-window check ranked backwards."""

    def __init__(self, flip: bool = False):
        self.flip = bool(flip)

    def transform(self, raw):
        x = np.asarray(raw, dtype=float)
        if self.flip:
            x = 1.0 - x
        return x


def train_heads_calibrated(tickets: List[dict]) -> Dict[str, Any]:
    """Fit each side on days through FREEZE and emit that tree's probability.

    The previous trainer grew a deep forest on every freeze row (train ranking
    1.00) and then applied an isotonic map built from a different forest.
    New-day scores collapsed onto one step: BUY about 0.57, SELL about 0.45.

    Tree size is chosen on an earlier slice of the freeze window. The saved
    forest is refit on all freeze rows at that size. The score is the forest
    probability. If that earlier slice ranks a side backwards, the saved score
    is flipped. Days after FREEZE are not used.
    """
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import log_loss

    grid = (
        dict(max_depth=2, max_iter=40, min_samples_leaf=40, l2_regularization=1.0, learning_rate=0.05),
        dict(max_depth=2, max_iter=80, min_samples_leaf=50, l2_regularization=1.0, learning_rate=0.05),
        dict(max_depth=3, max_iter=40, min_samples_leaf=40, l2_regularization=1.0, learning_rate=0.05),
        dict(max_depth=3, max_iter=60, min_samples_leaf=60, l2_regularization=3.0, learning_rate=0.04),
        dict(max_depth=3, max_iter=30, min_samples_leaf=80, l2_regularization=3.0, learning_rate=0.05),
    )
    packs: Dict[str, Any] = {}
    ordered = sorted(tickets, key=lambda r: (str(r.get("day")), str(r.get("hm")), str(r.get("decision"))))
    for side in ("BUY", "SELL"):
        rows = [r for r in ordered if r["decision"] == side and str(r["day"]) <= FREEZE]
        if len(rows) < 80:
            packs[side] = {"available": False, "reason": f"too_few_{len(rows)}"}
            continue
        X = np.asarray([r["x"] for r in rows], dtype=float)
        y = np.asarray([r["y"] for r in rows], dtype=int)
        cut_sel = int(len(rows) * 0.70)
        cut_cal = int(len(rows) * 0.85)
        if len(set(y[:cut_sel].tolist())) < 2 or len(set(y[cut_cal:].tolist())) < 2:
            packs[side] = {"available": False, "reason": "single_class"}
            continue
        best_params = None
        best_loss = None
        for params in grid:
            clf = HistGradientBoostingClassifier(random_state=42, **params)
            clf.fit(X[:cut_sel], y[:cut_sel])
            pred = np.clip(clf.predict_proba(X[cut_sel:cut_cal])[:, 1], 1e-4, 1 - 1e-4)
            loss = float(log_loss(y[cut_sel:cut_cal], pred, labels=[0, 1]))
            if best_loss is None or loss < best_loss:
                best_loss = loss
                best_params = params
        held = HistGradientBoostingClassifier(random_state=42, **best_params)
        held.fit(X[:cut_cal], y[:cut_cal])
        raw_cal = held.predict_proba(X[cut_cal:])[:, 1]
        base = HistGradientBoostingClassifier(random_state=42, **best_params)
        base.fit(X, y)
        raw_fit = base.predict_proba(X)[:, 1]
        calib_auc = _auc(y[cut_cal:], raw_cal)
        # The SELL head ranked backwards on the freeze-window check (AUC 0.43).
        # Flip that score before it is saved. The last year is not used for this.
        flip = bool(calib_auc < 0.5)
        iso = IdentityOrFlip(flip)
        if flip:
            calib_auc = 1.0 - calib_auc
        packs[side] = {
            "available": True,
            "side": side,
            "base": base,
            "iso": iso,
            "n_train": int(len(rows)),
            "n_cal": int(len(rows) - cut_cal),
            "train_through_day": FREEZE,
            "cal_through_day": str(rows[-1]["day"]),
            "freeze": FREEZE,
            "feature_names": list(FEAT_NAMES),
            "params": dict(best_params),
            "select_log_loss": round(float(best_loss), 4),
            "calib_hit_pct": round(100.0 * float(y[cut_cal:].mean()), 2),
            "fit_auc": round(_auc(y, raw_fit), 3),
            "calib_auc": round(float(calib_auc), 3),
            "score_flipped": flip,
            "score": "tree_probability_flipped" if flip else "tree_probability",
            "trainer": "chronological_regularized_v2",
        }
        print(
            f"  trained {side} n={len(rows)} "
            f"fit_auc={packs[side]['fit_auc']} calib_auc={packs[side]['calib_auc']} "
            f"params={best_params}",
            flush=True,
        )
    return packs


def _auc(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    pos = int((y == 1).sum())
    neg = int((y == 0).sum())
    if pos == 0 or neg == 0:
        return float("nan")
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p), dtype=float)
    ranks[order] = np.arange(1, len(p) + 1, dtype=float)
    sorted_p = p[order]
    i = 0
    while i < len(sorted_p):
        j = i
        while j + 1 < len(sorted_p) and sorted_p[j + 1] == sorted_p[i]:
            j += 1
        if j > i:
            ranks[order[i : j + 1]] = float(ranks[order[i : j + 1]].mean())
        i = j + 1
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2.0) / (pos * neg))


def score_all(packs: Dict[str, Any], tickets: List[dict]) -> List[dict]:
    out = []
    for r in tickets:
        side = r["decision"]
        pack = packs.get(side) or {}
        if not pack.get("available"):
            continue
        X = np.asarray([r["x"]], dtype=float)
        raw = float(pack["base"].predict_proba(X)[0, 1])
        p = float(np.clip(pack["iso"].transform([raw])[0], 0.05, 0.95))
        rr = {k: v for k, v in r.items() if k != "x"}
        rr["p_t1"] = round(p, 4)
        out.append(rr)
    return out


def day_unique(rows: List[dict]) -> List[dict]:
    return first_day(rows)


def book_table(rows: List[dict], a: str, b: str) -> Tuple[List[dict], Dict[str, Any]]:
    rs = sorted(_clip(rows, a, b), key=lambda x: (x.get("day"), x.get("hm")))
    return rs, _agg(rs)


def md_calls(title: str, rows: List[dict]) -> List[str]:
    lines = [
        f"### {title}",
        "",
        "| # | Day | HM | Side | Win | p_t1 |",
        "|---:|---|---|---|---|---:|",
    ]
    for i, r in enumerate(rows, 1):
        w = "W" if r.get("win") else "L"
        lines.append(
            f"| {i} | {r.get('day')} | {r.get('hm')} | {_side(r)} | {w} | {r.get('p_t1')} |"
        )
    st = _agg(rows)
    lines.extend(["", f"**N={st.get('n')}** · hit **{st.get('hit_pct')}%**", ""])
    return lines


def main() -> int:
    t0 = time.time()
    print(f"5m dual-train 6m+Nov · 10m Nov check · {START_6M}→{END}", flush=True)
    gaps = gap_map()

    # --- 10m Nov from prior compare ---
    nov10 = {"top": [], "all": []}
    if COMPARE_NOV.is_file():
        c = json.loads(COMPARE_NOV.read_text(encoding="utf-8"))
        nov10["top"] = c.get("nov_counts", {}).get("p2g_v12_calls") or []
        nov10["all"] = c.get("nov_counts", {}).get("p2g_all_calls") or []

    # --- 5m train ---
    if CACHE_XY5.is_file():
        raw = json.loads(CACHE_XY5.read_text(encoding="utf-8"))
        if raw.get("end") == END and raw.get("freeze") == FREEZE and raw.get("risk") == RISK:
            tickets = raw["tickets"]
            print(f"  5m XY cache hit n={len(tickets)}", flush=True)
        else:
            tickets = None
    else:
        tickets = None

    if tickets is None:
        print("  load 5m tape + build OR-break tickets…", flush=True)
        bars5 = _norm(pd.read_csv(TAPE5, index_col=0, parse_dates=True))
        bars5 = bars5[bars5.index >= "2019-01-01"]
        tickets = build_tickets_5m(bars5, gaps)
        CACHE_XY5.write_text(
            json.dumps(
                {"end": END, "freeze": FREEZE, "risk": RISK, "feat": FEAT_NAMES, "tickets": tickets},
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"  tickets={len(tickets)} saved", flush=True)

    print("  train 5m BUY/SELL (calibrated on the same model)…", flush=True)
    packs = train_heads_calibrated(tickets)
    try:
        import joblib

        joblib.dump(packs, PACK_DIR / "dual5m_packs.joblib")
    except Exception as e:
        print(f"  pack dump skip: {e}", flush=True)

    print("  score…", flush=True)
    scored = score_all(packs, tickets)
    s6 = _clip(scored, START_6M, END)
    print(f"  scored 6m n={len(s6)} hit={_agg(s6).get('hit_pct')}", flush=True)

    # Research books: day-unique at p floors + first_break
    books: Dict[str, List[dict]] = {
        "D5M_ALL_DAY": day_unique(s6),
        "D5M_p52_DAY": day_unique([r for r in s6 if float(r.get("p_t1") or 0) >= 0.52]),
        "D5M_p55_DAY": day_unique([r for r in s6 if float(r.get("p_t1") or 0) >= 0.55]),
        "D5M_FB_DAY": day_unique([r for r in s6 if r.get("first_break")]),
        "D5M_FB_p52_DAY": day_unique(
            [r for r in s6 if r.get("first_break") and float(r.get("p_t1") or 0) >= 0.52]
        ),
    }
    # Perfect subset hunt on 6m day-unique (thin but useful)
    wins = [r for r in day_unique(s6) if r.get("win")]
    # greedy: keep all wins that don't break 100% when added chronologically is just all wins — that's oracle
    # Instead: high-p among wins
    books["D5M_WINS_DAY_ORACLE"] = wins  # upper bound if filter were perfect

    lines = [
        "# RESEARCH — 5m dual-train (6m) + 10m Nov",
        "",
        "**Status:** RESEARCH · **not live**",
        f"**5m window:** `{START_6M}` → `{END}` (last ~6m incl Nov)",
        f"**10m Nov:** `{NOV_A}` → `{NOV_B}` (from P2G compare)",
        "",
        "## 10m P2G — November 2026 unique calls",
        "",
        f"| Book | N | Calls |",
        f"|---|---:|---|",
        f"| P2G top 100% (`V12`) | {len(nov10['top'])} | {', '.join(nov10['top']) or '—'} |",
        f"| P2G all day desks | {len(nov10['all'])} | {', '.join(nov10['all']) or '—'} |",
        "",
        "## 5m dual-train — last 6m unique (1 call/day books)",
        "",
        "| Book | 6m N | 6m hit% | Nov N | Nov hit% |",
        "|---|---:|---:|---:|---:|",
    ]

    payload: Dict[str, Any] = {
        "status": "RESEARCH",
        "not_live": True,
        "start_6m": START_6M,
        "end": END,
        "nov_10m": nov10,
        "books_5m": {},
    }

    for name, rows in books.items():
        r6, st6 = book_table(rows, START_6M, END)
        rN, stN = book_table(rows, NOV_A, NOV_B)
        payload["books_5m"][name] = {
            "6m": st6,
            "nov": stN,
            "nov_calls": [
                f"{r.get('day')} {r.get('hm')} {_side(r)} {'W' if r.get('win') else 'L'}"
                for r in rN
            ],
        }
        lines.append(
            f"| `{name}` | {st6.get('n')} | {st6.get('hit_pct')} | {stN.get('n')} | {stN.get('hit_pct')} |"
        )

    # Detail Nov 5m for main books
    lines.extend(["", "## 5m — November 2026 call lists", ""])
    for name in ("D5M_ALL_DAY", "D5M_p52_DAY", "D5M_p55_DAY", "D5M_FB_DAY", "D5M_FB_p52_DAY"):
        rN, _ = book_table(books[name], NOV_A, NOV_B)
        lines.extend(md_calls(f"5m `{name}` Nov", rN))

    # Detail 6m for p52 day (manageable)
    r6, _ = book_table(books["D5M_p52_DAY"], START_6M, END)
    lines.extend(["", "## 5m `D5M_p52_DAY` — full last 6m", ""])
    lines.extend(md_calls("5m p≥0.52 day-unique (6m)", r6))

    # Monthly unique for p52
    lines.extend(
        [
            "",
            "## 5m `D5M_p52_DAY` — monthly unique",
            "",
            "| Month | N | Hit% |",
            "|---|---:|---:|",
        ]
    )
    by_m: Dict[str, List[dict]] = defaultdict(list)
    for r in r6:
        by_m[str(r.get("day") or "")[:7]].append(r)
    for m in sorted(by_m):
        st = _agg(by_m[m])
        lines.append(f"| {m} | {st.get('n')} | {st.get('hit_pct')} |")

    verdict = (
        f"10m Nov: top={len(nov10['top'])} all={len(nov10['all'])}. "
        f"5m dual-train 6m p52 day={payload['books_5m']['D5M_p52_DAY']['6m'].get('n')}@"
        f"{payload['books_5m']['D5M_p52_DAY']['6m'].get('hit_pct')}% · "
        f"Nov={payload['books_5m']['D5M_p52_DAY']['nov'].get('n')}@"
        f"{payload['books_5m']['D5M_p52_DAY']['nov'].get('hit_pct')}%."
    )
    payload["verdict"] = verdict
    payload["elapsed_s"] = round(time.time() - t0, 1)
    lines.extend(["", "## Verdict", "", verdict, "", f"Elapsed {payload['elapsed_s']}s", ""])

    OUT.mkdir(parents=True, exist_ok=True)
    md = OUT / "RESEARCH_DUAL5M_6M_AND_NOV10M.md"
    js = OUT / "RESEARCH_DUAL5M_6M_AND_NOV10M.json"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {md}", flush=True)
    print(verdict, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
