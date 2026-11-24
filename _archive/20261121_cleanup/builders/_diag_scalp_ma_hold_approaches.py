"""Different MA *hold* approaches (not last-10 entry filter).

Entry stays clean34 (or hard34). What changes is HOW we hold/exit with MA:
  A) MA-stop at entry (SL = dist to EMA)
  B) MA-trail on close (exit when close flips vs EMA)
  C) MA-trail after cushion (structure SL first, then trail EMA)
  D) Dual-MA hold (stay while fast+slow still with side)
  E) ATR-band around EMA as trailing stop
  F) Target = k * |entry-EMA| (MA-sized target), SL = structure/MA

Train < HOLD_LO; hold months unknown.
"""
from __future__ import annotations

import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
import research_nifty_1m_vix_candle_adaptive as vixmod  # noqa: E402
import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import enrich_prior3  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402
from _diag_scalp_ma_lastyear_init import (  # noqa: E402
    HOLD_LO,
    WIN_LO,
    PACK,
    add_ma_layers,
    enrich_ma_layers,
    one_per_day,
    summarize,
)

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SCALP_MA_HOLD_APPROACHES.md"
MAX_BARS = 120  # ~2h hold cap


def path_fixed(h, l, c, i, side, sl_pts, t1_pts, max_bars=MAX_BARS):
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    if side == "BUY":
        sl, t1 = entry - sl_pts, entry + t1_pts
        for j in range(i + 1, end + 1):
            hi, lo = float(h[j]), float(l[j])
            hit_sl, hit_t = lo <= sl, hi >= t1
            if hit_sl and hit_t:
                return False, "both", sl_pts, t1_pts
            if hit_t:
                return True, "t1", sl_pts, t1_pts
            if hit_sl:
                return False, "sl", sl_pts, t1_pts
        return False, "exp", sl_pts, t1_pts
    sl, t1 = entry + sl_pts, entry - t1_pts
    for j in range(i + 1, end + 1):
        hi, lo = float(h[j]), float(l[j])
        hit_sl, hit_t = hi >= sl, lo <= t1
        if hit_sl and hit_t:
            return False, "both", sl_pts, t1_pts
        if hit_t:
            return True, "t1", sl_pts, t1_pts
        if hit_sl:
            return False, "sl", sl_pts, t1_pts
    return False, "exp", sl_pts, t1_pts


def path_ma_trail_close(h, l, c, ma, i, side, t1_pts, max_bars=MAX_BARS):
    """Hold while close stays with MA; T1 fixed; SL = flip close vs MA."""
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    if side == "BUY":
        t1 = entry + t1_pts
        for j in range(i + 1, end + 1):
            hi, lo, cl, m = float(h[j]), float(l[j]), float(c[j]), float(ma[j])
            if not np.isfinite(m):
                return False, "bad", 0, t1_pts
            if hi >= t1:
                return True, "t1", max(entry - m, 0.0), t1_pts
            if cl < m:  # lost MA hold
                sl_dist = entry - cl
                return (cl > entry), "ma_exit", abs(sl_dist), t1_pts
        return False, "exp", 0, t1_pts
    t1 = entry - t1_pts
    for j in range(i + 1, end + 1):
        hi, lo, cl, m = float(h[j]), float(l[j]), float(c[j]), float(ma[j])
        if not np.isfinite(m):
            return False, "bad", 0, t1_pts
        if lo <= t1:
            return True, "t1", max(m - entry, 0.0), t1_pts
        if cl > m:
            sl_dist = cl - entry
            return (cl < entry), "ma_exit", abs(sl_dist), t1_pts
    return False, "exp", 0, t1_pts


def path_ma_trail_strict(h, l, c, ma, i, side, t1_pts, max_bars=MAX_BARS):
    """Win only if T1 before MA flip; MA flip = loss (even if green)."""
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    if side == "BUY":
        t1 = entry + t1_pts
        for j in range(i + 1, end + 1):
            hi, cl, m = float(h[j]), float(c[j]), float(ma[j])
            if hi >= t1:
                return True, "t1", max(entry - float(ma[i]), 4.0), t1_pts
            if cl < m:
                return False, "ma_sl", abs(entry - cl), t1_pts
        return False, "exp", 0, t1_pts
    t1 = entry - t1_pts
    for j in range(i + 1, end + 1):
        lo, cl, m = float(l[j]), float(c[j]), float(ma[j])
        if lo <= t1:
            return True, "t1", max(float(ma[i]) - entry, 4.0), t1_pts
        if cl > m:
            return False, "ma_sl", abs(cl - entry), t1_pts
    return False, "exp", 0, t1_pts


def path_dual_ma_hold(h, l, c, ma_fast, ma_slow, i, side, t1_pts, max_bars=MAX_BARS):
    """Hold while close with fast AND fast vs slow stack with side; else exit loss if T1 not hit."""
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    if side == "BUY":
        t1 = entry + t1_pts
        for j in range(i + 1, end + 1):
            hi, cl = float(h[j]), float(c[j])
            f, s = float(ma_fast[j]), float(ma_slow[j])
            if hi >= t1:
                return True, "t1", abs(entry - f), t1_pts
            if cl < f or f < s:
                return False, "dual_exit", abs(entry - cl), t1_pts
        return False, "exp", 0, t1_pts
    t1 = entry - t1_pts
    for j in range(i + 1, end + 1):
        lo, cl = float(l[j]), float(c[j])
        f, s = float(ma_fast[j]), float(ma_slow[j])
        if lo <= t1:
            return True, "t1", abs(f - entry), t1_pts
        if cl > f or f > s:
            return False, "dual_exit", abs(cl - entry), t1_pts
    return False, "exp", 0, t1_pts


def path_cushion_then_trail(h, l, c, ma, i, side, struct_sl, t1_pts, cushion, max_bars=MAX_BARS):
    """Use structure SL until +cushion MFE, then trail MA close."""
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    armed = False
    if side == "BUY":
        hard_sl = entry - struct_sl
        t1 = entry + t1_pts
        for j in range(i + 1, end + 1):
            hi, lo, cl, m = float(h[j]), float(l[j]), float(c[j]), float(ma[j])
            if hi >= t1:
                return True, "t1", struct_sl, t1_pts
            if not armed:
                if lo <= hard_sl:
                    return False, "sl", struct_sl, t1_pts
                if (hi - entry) >= cushion:
                    armed = True
            else:
                if cl < m:
                    return False, "trail_ma", abs(entry - cl), t1_pts
        return False, "exp", struct_sl, t1_pts
    hard_sl = entry + struct_sl
    t1 = entry - t1_pts
    for j in range(i + 1, end + 1):
        hi, lo, cl, m = float(h[j]), float(l[j]), float(c[j]), float(ma[j])
        if lo <= t1:
            return True, "t1", struct_sl, t1_pts
        if not armed:
            if hi >= hard_sl:
                return False, "sl", struct_sl, t1_pts
            if (entry - lo) >= cushion:
                armed = True
        else:
            if cl > m:
                return False, "trail_ma", abs(cl - entry), t1_pts
    return False, "exp", struct_sl, t1_pts


def path_ema_atr_band(h, l, c, ma, atr, i, side, t1_pts, k=1.0, max_bars=MAX_BARS):
    """Trailing stop = EMA - k*ATR (BUY) / EMA + k*ATR (SELL), updated each bar."""
    entry = float(c[i])
    end = min(len(c) - 1, i + max_bars)
    a0 = max(float(atr[i]), 3.0)
    if side == "BUY":
        t1 = entry + t1_pts
        for j in range(i + 1, end + 1):
            hi, lo, m = float(h[j]), float(l[j]), float(ma[j])
            a = max(float(atr[j]) if j < len(atr) else a0, 3.0)
            stop = m - k * a
            if hi >= t1:
                return True, "t1", max(entry - stop, 4.0), t1_pts
            if lo <= stop:
                return False, "band_sl", abs(entry - stop), t1_pts
        return False, "exp", 0, t1_pts
    t1 = entry - t1_pts
    for j in range(i + 1, end + 1):
        hi, lo, m = float(h[j]), float(l[j]), float(ma[j])
        a = max(float(atr[j]) if j < len(atr) else a0, 3.0)
        stop = m + k * a
        if lo <= t1:
            return True, "t1", max(stop - entry, 4.0), t1_pts
        if hi >= stop:
            return False, "band_sl", abs(stop - entry), t1_pts
    return False, "exp", 0, t1_pts


def struct_sl(e, cap=12.0):
    p = float(e.get("sl_prev") or 99)
    s = float(e.get("sl_sig") or 99)
    sl = min(p, s) if s >= 4 else p
    sl = max(4.0, min(sl, cap))
    return sl


def ma_dist_sl(entry, ma_i, side, floor=4.0, cap=15.0):
    if side == "BUY":
        d = entry - ma_i
    else:
        d = ma_i - entry
    if d < floor:
        return None  # MA already wrong side / too tight
    return float(min(max(d, floor), cap))


def first_clean_per_day(events, gate):
    by = defaultdict(list)
    for e in events:
        if gate(e):
            by[e["day"]].append(e)
    out = []
    for d, xs in sorted(by.items()):
        out.append(sorted(xs, key=lambda x: x["mins"])[0])
    return out


def eval_approach(entries, fn):
    rows = []
    for e in entries:
        ok, reason, sl, t1 = fn(e)
        if ok is None:
            continue
        rows.append({**e, "_win": bool(ok), "_reason": reason, "_sl": float(sl or 0), "_t1": float(t1 or 0)})
    return rows


def main() -> int:
    print("MA HOLD approaches (different exits)…", flush=True)
    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    # ATR14 for band
    hi = df["High"].astype(float)
    lo = df["Low"].astype(float)
    cl = df["Close"].astype(float)
    prev_c = cl.shift(1)
    tr = pd.concat([(hi - lo), (hi - prev_c).abs(), (lo - prev_c).abs()], axis=1).max(axis=1)
    df["atr14"] = tr.rolling(14, min_periods=14).mean()

    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    atr = df["atr14"].astype(float).values
    emas = {n: df[f"ema{n}"].astype(float).values for n in (15, 21, 34, 50)}
    vix = vixmod.load_vix()

    data_hi = str(raw.index.max().date())
    xs = pickle.load((PACK / f"events_{WIN_LO}_{data_hi}.pkl").open("rb"))
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)

    train = [e for e in xs if e["day"] < HOLD_LO]
    hold = [e for e in xs if e["day"] >= HOLD_LO]
    td = len({e["day"] for e in train})
    hd = len({e["day"] for e in hold})
    gate = lambda e: bool(e.get("gate_clean34"))

    tr_e = first_clean_per_day(train, gate)
    ho_e = first_clean_per_day(hold, gate)
    print(f"entries/day train={len(tr_e)} hold={len(ho_e)}", flush=True)

    approaches = []

    # baseline structure SL + fixed T
    for t1 in (15.0, 20.0, 25.0, 30.0):
        approaches.append(
            (
                f"base_struct_t{int(t1)}",
                lambda e, t1=t1: path_fixed(h, l, c, int(e["full_i"]), e["decision"], struct_sl(e), t1),
            )
        )

    # A) MA stop at entry + T = k * SL or fixed
    for span in (15, 21, 34, 50):
        ma = emas[span]
        for t1 in (15.0, 20.0, 25.0, 30.0):

            def fn(e, ma=ma, t1=t1, span=span):
                i = int(e["full_i"])
                entry = float(c[i])
                sl = ma_dist_sl(entry, float(ma[i]), e["decision"])
                if sl is None:
                    return None, "skip", 0, t1
                return path_fixed(h, l, c, i, e["decision"], sl, t1)

            approaches.append((f"A_ma{span}_stop_t{int(t1)}", fn))

        def fn_rr(e, ma=ma, span=span):
            i = int(e["full_i"])
            entry = float(c[i])
            sl = ma_dist_sl(entry, float(ma[i]), e["decision"], floor=4, cap=15)
            if sl is None:
                return None, "skip", 0, 0
            t1 = max(12.0, min(2.0 * sl, 30.0))
            return path_fixed(h, l, c, i, e["decision"], sl, t1)

        approaches.append((f"A_ma{span}_stop_rr2", fn_rr))

    # B) MA trail close (strict T1-before-flip)
    for span in (15, 21, 34):
        ma = emas[span]
        for t1 in (15.0, 20.0, 25.0, 30.0):
            approaches.append(
                (
                    f"B_trail{span}_strict_t{int(t1)}",
                    lambda e, ma=ma, t1=t1: path_ma_trail_strict(
                        h, l, c, ma, int(e["full_i"]), e["decision"], t1
                    ),
                )
            )
            approaches.append(
                (
                    f"B_trail{span}_soft_t{int(t1)}",
                    lambda e, ma=ma, t1=t1: path_ma_trail_close(
                        h, l, c, ma, int(e["full_i"]), e["decision"], t1
                    ),
                )
            )

    # C) cushion then trail
    for span in (15, 21, 34):
        ma = emas[span]
        for cushion in (5.0, 8.0, 10.0):
            for t1 in (20.0, 25.0, 30.0):
                approaches.append(
                    (
                        f"C_cush{int(cushion)}_trail{span}_t{int(t1)}",
                        lambda e, ma=ma, cushion=cushion, t1=t1: path_cushion_then_trail(
                            h, l, c, ma, int(e["full_i"]), e["decision"], struct_sl(e), t1, cushion
                        ),
                    )
                )

    # D) dual MA hold
    for fast, slow in ((15, 34), (21, 50), (15, 50)):
        for t1 in (20.0, 25.0, 30.0):
            approaches.append(
                (
                    f"D_dual{fast}_{slow}_t{int(t1)}",
                    lambda e, f=fast, s=slow, t1=t1: path_dual_ma_hold(
                        h, l, c, emas[f], emas[s], int(e["full_i"]), e["decision"], t1
                    ),
                )
            )

    # E) EMA ATR band trail
    for span in (21, 34):
        for k in (0.5, 1.0, 1.5):
            for t1 in (20.0, 25.0, 30.0):
                approaches.append(
                    (
                        f"E_band{span}_k{k}_t{int(t1)}",
                        lambda e, span=span, k=k, t1=t1: path_ema_atr_band(
                            h, l, c, emas[span], atr, int(e["full_i"]), e["decision"], t1, k
                        ),
                    )
                )

    # F) MA-sized target, structure SL
    for span in (21, 34):
        ma = emas[span]
        for mult in (1.5, 2.0, 2.5):

            def fn(e, ma=ma, mult=mult):
                i = int(e["full_i"])
                entry = float(c[i])
                dist = abs(entry - float(ma[i]))
                t1 = max(12.0, min(mult * max(dist, 6.0), 35.0))
                return path_fixed(h, l, c, i, e["decision"], struct_sl(e), t1)

            approaches.append((f"F_struct_t_ma{span}x{mult}", fn))

    lines = [
        "# NIFTY 1m — **MA HOLD approaches** (exit logic, not last-10 filter)",
        "",
        f"Entry: first `clean34` per day · Train `<{HOLD_LO}` · Hold unknown `≥{HOLD_LO}` → `{data_hi}`",
        "",
        "Families:",
        "- **A** MA-stop at entry (SL = distance to EMA)",
        "- **B** Trail/hold on EMA close (strict = MA flip is loss; soft = green MA-exit counts win)",
        "- **C** Structure SL until cushion, then trail EMA",
        "- **D** Dual-MA hold (fast+slow stack)",
        "- **E** EMA ± k·ATR trailing band",
        "- **F** Structure SL + target sized from |entry−EMA|",
        "",
        "| Approach | Train n@hit cover | Hold n@hit cover | Hold avgSL/T1 |",
        "|---|---|---|---|",
    ]

    rows_out = []
    print(f"testing {len(approaches)} approaches…", flush=True)
    for name, fn in approaches:
        tr = eval_approach(tr_e, fn)
        ho = eval_approach(ho_e, fn)
        st_tr = summarize(
            [{**e, "_t1": e.get("_t1", 0)} for e in tr],
            td,
        )
        # summarize expects _t1
        for e in tr + ho:
            e.setdefault("_t1", 0)
            e.setdefault("_sl", 0)
        st_tr = summarize(tr, td)
        st_ho = summarize(ho, hd)
        rows_out.append((name, st_tr, st_ho))
        if name.startswith("base") or "trail21" in name or "dual21" in name or name.endswith("t20") and name[0] in "ABCDEF":
            print(f"  {name}: tr {st_tr['n']}@{st_tr['hit']}% ho {st_ho['n']}@{st_ho['hit']}%/{st_ho['cover']}%", flush=True)

    # rank by hold hit then cover
    ranked = sorted(rows_out, key=lambda r: (-r[2]["hit"], -r[2]["cover"], -r[1]["hit"]))
    top = ranked[:20]
    base_rows = [r for r in rows_out if r[0].startswith("base_")]

    for name, st_tr, st_ho in base_rows + top:
        lines.append(
            f"| `{name}` | {st_tr['n']}@{st_tr['hit']}% {st_tr['cover']}% | "
            f"{st_ho['n']}@{st_ho['hit']}% {st_ho['cover']}% | {st_ho['avg_sl']}/{st_ho['avg_t1']} |"
        )

    # best per family
    lines += ["", "## Best per family (by hold hit)", ""]
    for fam in "ABCDEF":
        fam_rows = [r for r in ranked if r[0].startswith(f"{fam}_")]
        if not fam_rows:
            continue
        name, st_tr, st_ho = fam_rows[0]
        lines.append(
            f"- **{fam}** `{name}` → hold **{st_ho['hit']}%** cover {st_ho['cover']}% "
            f"(train {st_tr['hit']}%/{st_tr['cover']}%)"
        )
        print(f"BEST {fam}: {name} hold {st_ho['hit']}% cover {st_ho['cover']}%", flush=True)

    best = ranked[0]
    lines += [
        "",
        f"### Overall best hold: `{best[0]}` → **{best[2]['hit']}%** ({best[2]['n']} days, cover {best[2]['cover']}%)",
        "",
        "Note: soft trail counts green MA-exit as win — useful for hold-PnL, not path-T1 purity.",
        "Strict trail = T1 must print before MA flip (closer to your 100% path goal).",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)
    print(f"TOP5:", flush=True)
    for name, st_tr, st_ho in ranked[:5]:
        print(f"  {name}: hold {st_ho['hit']}% cover {st_ho['cover']}% train {st_tr['hit']}%", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
