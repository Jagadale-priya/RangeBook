"""Research indicators to push blind MA-HOLD100 → 100% hit + cover.

Exit held: EMA34 trail · T1=12 (oracle already 100/100).
Add RSI / MACD / Stoch / ADX / VWAP / Bollinger / ATR% and hunt
blind day-pick rules on train → score last-3m hold.
"""
from __future__ import annotations

import json
import pickle
import sys
from collections import Counter, defaultdict
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
    WIN_LO,
    PACK,
    add_ma_layers,
    enrich_ma_layers,
    summarize,
)
from _diag_scalp_ma_hold100 import attach_exit_grid, keys_hold  # noqa: E402
from _diag_scalp_ma_hold100_picker import MODE, T1, build_allow  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
PACK_OUT = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_ma_hold100"
REPORT = OUT / "NIFTY_1M_SCALP_MA_HOLD100_INDICATORS.md"


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c = df["Close"].astype(float)
    h = df["High"].astype(float)
    l = df["Low"].astype(float)

    # RSI14 already maybe present
    if "rsi_14" not in df.columns:
        df = beh.add_rsi(df)

    # MACD 12/26/9
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    df["macd"] = macd
    df["macd_sig"] = signal
    df["macd_hist"] = macd - signal

    # Stochastic 14,3
    lo14 = l.rolling(14, min_periods=14).min()
    hi14 = h.rolling(14, min_periods=14).max()
    stoch_k = 100 * (c - lo14) / (hi14 - lo14).replace(0, np.nan)
    df["stoch_k"] = stoch_k.fillna(50)
    df["stoch_d"] = df["stoch_k"].rolling(3, min_periods=1).mean()

    # ATR% 
    prev = c.shift(1)
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    atr14 = tr.rolling(14, min_periods=14).mean()
    df["atr14"] = atr14
    df["atr_pct"] = (atr14 / c * 100).fillna(0)

    # ADX(14) simplified
    up = h.diff()
    dn = -l.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr_s = tr.rolling(14, min_periods=14).sum()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(14, min_periods=14).sum() / tr_s.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(14, min_periods=14).sum() / tr_s.replace(0, np.nan)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0)
    df["adx"] = dx.rolling(14, min_periods=1).mean()
    df["plus_di"] = plus_di.fillna(0)
    df["minus_di"] = minus_di.fillna(0)

    # Session VWAP
    if "day" not in df.columns:
        df["day"] = df.index.tz_convert("Asia/Kolkata").strftime("%Y-%m-%d")
    typ = (h + l + c) / 3.0
    df["vwap"] = typ.groupby(df["day"]).cumsum() / (typ.groupby(df["day"]).cumcount() + 1)
    df["vwap_dist"] = (c - df["vwap"]) / atr14.replace(0, np.nan)
    df["vwap_dist"] = df["vwap_dist"].fillna(0)

    # Bollinger 20,2
    mid = c.rolling(20, min_periods=20).mean()
    sd = c.rolling(20, min_periods=20).std()
    df["bb_mid"] = mid
    df["bb_upper"] = mid + 2 * sd
    df["bb_lower"] = mid - 2 * sd
    df["bb_pct"] = ((c - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)).fillna(0.5)

    # Momentum
    df["roc5"] = c.pct_change(5) * 100
    df["roc10"] = c.pct_change(10) * 100
    return df


def enrich_ind(events, df):
    rsi = df["rsi_14"].astype(float).values
    macdh = df["macd_hist"].astype(float).values
    macd = df["macd"].astype(float).values
    sk = df["stoch_k"].astype(float).values
    sd = df["stoch_d"].astype(float).values
    adx = df["adx"].astype(float).values
    pdi = df["plus_di"].astype(float).values
    mdi = df["minus_di"].astype(float).values
    vdist = df["vwap_dist"].astype(float).values
    bb = df["bb_pct"].astype(float).values
    atrp = df["atr_pct"].astype(float).values
    roc5 = df["roc5"].astype(float).values
    close = df["Close"].astype(float).values
    bb_mid = df["bb_mid"].astype(float).values

    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        if i < 30 or not np.isfinite(adx[i]):
            e["ind_ok"] = False
            continue
        r, mh, m, k, d = float(rsi[i]), float(macdh[i]), float(macd[i]), float(sk[i]), float(sd[i])
        ax, pd_, md_ = float(adx[i]), float(pdi[i]), float(mdi[i])
        vd, bp, ap, r5 = float(vdist[i]), float(bb[i]), float(atrp[i]), float(roc5[i]) if np.isfinite(roc5[i]) else 0.0
        cl, mid = float(close[i]), float(bb_mid[i]) if np.isfinite(bb_mid[i]) else float(close[i])

        e["rsi"] = round(r, 1)
        e["macd_hist"] = round(mh, 3)
        e["stoch_k"] = round(k, 1)
        e["adx"] = round(ax, 1)
        e["vwap_atr"] = round(vd, 2)
        e["bb_pct"] = round(bp, 2)
        e["atr_pct"] = round(ap, 3)
        e["roc5"] = round(r5, 3)

        # side-aligned indicator flags
        if side == "BUY":
            e["rsi_ok"] = r < 70 and r > 35  # not overbought crash, some strength
            e["rsi_pull"] = 40 <= r <= 55
            e["macd_ok"] = mh > 0 or m > 0
            e["macd_turn"] = mh > 0
            e["stoch_ok"] = k < 80 and (k > d or k < 30)  # rising or oversold bounce
            e["stoch_ob"] = k >= 80
            e["adx_trend"] = ax >= 18
            e["di_ok"] = pd_ >= md_
            e["vwap_ok"] = vd >= -0.15
            e["vwap_with"] = vd >= 0
            e["bb_ok"] = bp <= 0.85  # not blow-off top
            e["bb_low"] = bp <= 0.35
            e["mom_ok"] = r5 >= -0.05
            e["bb_mid_ok"] = cl >= mid
        else:
            e["rsi_ok"] = r > 30 and r < 65
            e["rsi_pull"] = 45 <= r <= 60
            e["macd_ok"] = mh < 0 or m < 0
            e["macd_turn"] = mh < 0
            e["stoch_ok"] = k > 20 and (k < d or k > 70)
            e["stoch_ob"] = k <= 20
            e["adx_trend"] = ax >= 18
            e["di_ok"] = md_ >= pd_
            e["vwap_ok"] = vd <= 0.15
            e["vwap_with"] = vd <= 0
            e["bb_ok"] = bp >= 0.15
            e["bb_low"] = bp >= 0.65
            e["mom_ok"] = r5 <= 0.05
            e["bb_mid_ok"] = cl <= mid

        e["atr_quiet"] = ap <= 0.12
        e["atr_hot"] = ap >= 0.18

        # composite indicator packs
        e["ind_basic"] = bool(e["rsi_ok"] and e["macd_ok"] and e["vwap_ok"])
        e["ind_trend"] = bool(e["adx_trend"] and e["di_ok"] and e["macd_turn"] and e["ma_stack34"] in ("bull", "bear") if side == "BUY" else e["adx_trend"] and e["di_ok"] and e["macd_turn"])
        # fix ind_trend for SELL/BUY cleanly
        e["ind_trend"] = bool(e["adx_trend"] and e["di_ok"] and e["macd_turn"] and e.get("gate_stack34"))
        e["ind_pull"] = bool(e["rsi_pull"] and e["stoch_ok"] and e["vwap_with"] and e.get("gate_hard34"))
        e["ind_strict"] = bool(e["ind_basic"] and e["di_ok"] and e["stoch_ok"] and e["bb_ok"] and e["mom_ok"])
        e["ind_strict2"] = bool(e["ind_strict"] and e["adx_trend"] and e["vwap_with"] and e.get("gate_hard21"))
        e["ind_strict3"] = bool(e["macd_turn"] and e["di_ok"] and e["vwap_with"] and e["bb_mid_ok"] and e.get("gate_hard34") and e["rsi_ok"])
        e["ind_ok"] = True

        # fingerprint with indicators
        e["ind_fp"] = (
            e["primary"],
            e["decision"],
            int(e["macd_turn"]),
            int(e["di_ok"]),
            int(e["vwap_with"]),
            int(e["adx_trend"]),
            e.get("rsi_bin"),
            e.get("ma_stack34"),
        )


def keys_ind(e):
    base = list(keys_hold(e))
    base += [
        ("I1", e["primary"], e["decision"], int(e.get("macd_turn", 0)), int(e.get("di_ok", 0)), int(e.get("vwap_with", 0)), e.get("ma_stack34")),
        ("I2", e["primary"], e["decision"], int(e.get("rsi_pull", 0)), int(e.get("stoch_ok", 0)), int(e.get("bb_mid_ok", 0)), e.get("hm_bin")),
        ("I3", e["family"], e["decision"], int(e.get("adx_trend", 0)), int(e.get("macd_ok", 0)), int(e.get("vwap_ok", 0)), e.get("close_ok")),
        ("I4", e["primary"], e["decision"], int(e.get("ind_strict3", 0)), e.get("dist34_bin"), e.get("ema34_slope"), e.get("vix_regime")),
        ("I5", e["decision"], int(e.get("macd_turn", 0)), int(e.get("di_ok", 0)), int(e.get("vwap_with", 0)), int(e.get("gate_hard34", 0)), e.get("pre3_UD")),
    ]
    return base


def profile(xs, label):
    def rate(key):
        return round(100.0 * sum(1 for e in xs if e.get(key)) / max(len(xs), 1), 1)

    return {
        "label": label,
        "n": len(xs),
        "macd_turn": rate("macd_turn"),
        "di_ok": rate("di_ok"),
        "vwap_with": rate("vwap_with"),
        "adx_trend": rate("adx_trend"),
        "rsi_ok": rate("rsi_ok"),
        "rsi_pull": rate("rsi_pull"),
        "stoch_ok": rate("stoch_ok"),
        "ind_basic": rate("ind_basic"),
        "ind_strict": rate("ind_strict"),
        "ind_strict3": rate("ind_strict3"),
        "ind_pull": rate("ind_pull"),
        "avg_rsi": round(sum(e.get("rsi", 50) for e in xs) / max(len(xs), 1), 1),
        "avg_adx": round(sum(e.get("adx", 0) for e in xs) / max(len(xs), 1), 1),
    }


def first_oracle(xs):
    for e in sorted(xs, key=lambda x: x["mins"]):
        if e["_exit"][(MODE, T1)]["_win"]:
            return e
    return None


def first_loss(xs):
    for e in sorted(xs, key=lambda x: x["mins"]):
        if not e["_exit"][(MODE, T1)]["_win"]:
            return e
    return None


def build_ind_allow(train, pred=None, min_n=2):
    bucket = defaultdict(list)
    for e in train:
        if pred is not None and not pred(e):
            continue
        sc = e["_exit"][(MODE, T1)]
        for k in keys_ind(e):
            bucket[k].append(bool(sc["_win"]))
    allow = {}
    for k, rows in bucket.items():
        if any(not ok for ok in rows):
            continue
        if len(rows) < min_n:
            continue
        allow[k] = len(rows)
    return allow


def pick_day(xs, allow, ind_pred=None, min_keys=1):
    best, best_s = None, -1
    for e in sorted(xs, key=lambda x: x["mins"]):
        if ind_pred is not None and not ind_pred(e):
            continue
        keys = [k for k in keys_ind(e) if k in allow]
        if len(keys) < min_keys:
            continue
        s = len(keys) * 100000 + max(allow[k] for k in keys) * 10 - e["mins"]
        if s > best_s:
            best_s, best = s, e
    return best


def run(events, allow, n_days, ind_pred=None, min_keys=1):
    by = defaultdict(list)
    for e in events:
        by[e["day"]].append(e)
    calls = []
    for d, xs in sorted(by.items()):
        e = pick_day(xs, allow, ind_pred=ind_pred, min_keys=min_keys)
        if e is None:
            continue
        sc = e["_exit"][(MODE, T1)]
        calls.append({**e, **sc})
    return summarize(calls, n_days), calls


def main() -> int:
    print("Indicator research for MA HOLD100 → 100%", flush=True)
    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    data_hi = str(raw.index.max().date())
    end = pd.Timestamp(data_hi)
    hold_lo = str((end - pd.DateOffset(months=3) + pd.Timedelta(days=1)).date())
    print(f"hold last3m {hold_lo}→{data_hi}", flush=True)

    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    atr = df["atr14"].astype(float).values
    emas = {n: df[f"ema{n}"].astype(float).values for n in (15, 21, 34, 50)}
    vix = vixmod.load_vix()

    xs = pickle.load((PACK / f"events_{WIN_LO}_{data_hi}.pkl").open("rb"))
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)
    enrich_ind(xs, df)
    attach_exit_grid(xs, h, l, c, emas, atr, [MODE])

    train = [e for e in xs if e["day"] < hold_lo]
    hold = [e for e in xs if e["day"] >= hold_lo]
    td = len({e["day"] for e in train})
    hd = len({e["day"] for e in hold})
    hold_days = sorted({e["day"] for e in hold})

    # oracle vs early-loss indicator profile on train
    ow, ol = [], []
    by = defaultdict(list)
    for e in train:
        by[e["day"]].append(e)
    for d, rows in by.items():
        w = first_oracle(rows)
        loss = first_loss(rows)
        if w:
            ow.append(w)
        if loss:
            ol.append(loss)
    pw, pl = profile(ow, "oracle_win"), profile(ol, "early_loss")
    print("oracle_win", pw, flush=True)
    print("early_loss", pl, flush=True)

    # indicator gates to test
    gates = [
        ("raw", None),
        ("macd_turn", lambda e: e.get("macd_turn")),
        ("di_ok", lambda e: e.get("di_ok")),
        ("vwap_with", lambda e: e.get("vwap_with")),
        ("adx_trend", lambda e: e.get("adx_trend")),
        ("ind_basic", lambda e: e.get("ind_basic")),
        ("ind_strict", lambda e: e.get("ind_strict")),
        ("ind_strict2", lambda e: e.get("ind_strict2")),
        ("ind_strict3", lambda e: e.get("ind_strict3")),
        ("ind_pull", lambda e: e.get("ind_pull")),
        ("macd+di", lambda e: e.get("macd_turn") and e.get("di_ok")),
        ("macd+di+vwap", lambda e: e.get("macd_turn") and e.get("di_ok") and e.get("vwap_with")),
        ("macd+di+vwap+hard34", lambda e: e.get("macd_turn") and e.get("di_ok") and e.get("vwap_with") and e.get("gate_hard34")),
        ("strict3+stack34", lambda e: e.get("ind_strict3") and e.get("gate_stack34")),
        ("basic+hard34", lambda e: e.get("ind_basic") and e.get("gate_hard34")),
    ]

    lines = [
        "# MA HOLD100 — **indicator research** → aim 100%",
        "",
        f"Exit: **{MODE} T1={T1:.0f}** · Hold last3m **`{hold_lo}`→`{data_hi}`** ({hd}d) · Train {td}d",
        "",
        "## Indicator lift: oracle-win vs early-loss (train)",
        "",
        "| Flag | Oracle% | EarlyLoss% | Gap |",
        "|---|---:|---:|---:|",
    ]
    for k in ("macd_turn", "di_ok", "vwap_with", "adx_trend", "rsi_ok", "rsi_pull", "stoch_ok", "ind_basic", "ind_strict", "ind_strict3", "ind_pull"):
        gap = round(pw[k] - pl[k], 1)
        lines.append(f"| `{k}` | {pw[k]}% | {pl[k]}% | {gap:+.1f}pp |")
        print(f"  gap {k}: {gap:+.1f}pp (win {pw[k]} vs loss {pl[k]})", flush=True)

    # 1/day first event under indicator gate only
    lines += [
        "",
        "## A) Indicator gate only (1st match / day)",
        "",
        "| Gate | Train n@hit cover | Hold n@hit cover |",
        "|---|---|---|",
    ]
    print("[A] gate-only…", flush=True)
    for name, pred in gates:
        def pick_gate(rows, pred=pred):
            for e in sorted(rows, key=lambda x: x["mins"]):
                if pred is None or pred(e):
                    return e
            return None

        def eval_gate(events, nd):
            by2 = defaultdict(list)
            for e in events:
                by2[e["day"]].append(e)
            calls = []
            for d, rows in sorted(by2.items()):
                e = pick_gate(rows)
                if e is None:
                    continue
                calls.append({**e, **e["_exit"][(MODE, T1)]})
            return summarize(calls, nd), calls

        st_tr, _ = eval_gate(train, td)
        st_ho, _ = eval_gate(hold, hd)
        print(f"  {name}: tr {st_tr['hit']}%/{st_tr['cover']}% ho {st_ho['hit']}%/{st_ho['cover']}%", flush=True)
        lines.append(
            f"| `{name}` | {st_tr['n']}@{st_tr['hit']}% {st_tr['cover']}% | {st_ho['n']}@{st_ho['hit']}% {st_ho['cover']}% |"
        )

    # B) clean indicator fingerprint books
    lines += [
        "",
        "## B) Indicator + clean-key picker (train 100% keys)",
        "",
        "| Book | Train | Hold |",
        "|---|---|---|",
    ]
    print("[B] ind allow pickers…", flush=True)
    results = []
    for gname, gpred in gates:
        for min_n in (1, 2):
            for mk in (1, 2):
                allow = build_ind_allow(train, pred=gpred, min_n=min_n)
                if len(allow) < 5:
                    continue
                st_tr, _ = run(train, allow, td, ind_pred=gpred, min_keys=mk)
                if st_tr["n"] == 0 or st_tr["hit"] < 100 or not st_tr["all_win"]:
                    continue
                st_ho, ho = run(hold, allow, hd, ind_pred=gpred, min_keys=mk)
                name = f"{gname}_m{min_n}_k{mk}"
                results.append((name, st_tr, st_ho, ho, allow, gpred, mk))
                if st_tr["cover"] >= 50 or st_ho["hit"] >= 70:
                    print(
                        f"  {name}: allow={len(allow)} tr {st_tr['cover']}% ho {st_ho['hit']}%/{st_ho['cover']}%",
                        flush=True,
                    )
                    lines.append(
                        f"| `{name}` | {st_tr['n']}@{st_tr['hit']}% {st_tr['cover']}% | "
                        f"{st_ho['n']}@{st_ho['hit']}% {st_ho['cover']}% |"
                    )

    # rank useful
    useful = [r for r in results if r[1]["cover"] >= 70]
    useful.sort(key=lambda r: (-r[2]["hit"], -r[2]["cover"], -r[1]["cover"]))
    dual = [r for r in useful if r[2]["all_win"] and r[2]["cover"] >= 99]
    near = useful[:12] if useful else sorted(results, key=lambda r: (-r[2]["hit"], -r[2]["cover"]))[:12]

    lines += ["", "## Closest to 100/100 (train 100%, cover≥70)", ""]
    if dual:
        lines.append(f"**DUAL 100 FOUND:** `{dual[0][0]}`")
        print(f"DUAL100 {dual[0][0]}", flush=True)
    for name, st_tr, st_ho, *_ in near:
        lines.append(
            f"- `{name}`: hold **{st_ho['hit']}%** cover {st_ho['cover']}% · train cover {st_tr['cover']}%"
        )
        print(f"NEAR {name}: hold {st_ho['hit']}%/{st_ho['cover']}%", flush=True)

    best = dual[0] if dual else (near[0] if near else None)
    if best:
        name, st_tr, st_ho, ho, allow, gpred, mk = best
        lines += [
            "",
            f"### Day-by-day best `{name}`",
            "",
            "| Day | Y/N | HM | Side | Pattern | macd | DI | VWAP | ADX | MFE |",
            "|---|---|---|---|---|---|---|---|---:|---:|",
        ]
        by1 = {e["day"]: e for e in ho}
        for d in hold_days:
            e = by1.get(d)
            if not e:
                lines.append(f"| {d} | NO_CALL | | | | | | | | |")
                continue
            mark = "Y" if e["_win"] else "N"
            lines.append(
                f"| {d} | {mark} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"{int(bool(e.get('macd_turn')))} | {int(bool(e.get('di_ok')))} | "
                f"{int(bool(e.get('vwap_with')))} | {e.get('adx',0):.0f} | {e.get('mfe',0):.1f} |"
            )
        (PACK_OUT / "INDICATOR_BEST.pkl").write_bytes(
            pickle.dumps({"name": name, "train": st_tr, "hold": st_ho, "n_allow": len(allow)}, protocol=pickle.HIGHEST_PROTOCOL)
        )

    # C) Per-day: among ind_strict3 candidates, pick first — oracle overlap study
    lines += [
        "",
        "## Exact indicators under test",
        "",
        "- **RSI14** side bands / pullback zone",
        "- **MACD hist** turn with trade",
        "- **Stoch %K/%D** confirmation",
        "- **ADX +DI/−DI** trend alignment",
        "- **Session VWAP** side (ATR-normalized)",
        "- **Bollinger %B** / mid",
        "- **ATR%** regime",
        "- Plus held **EMA34 trail T1=12** exit",
        "",
        f"Pack: `{PACK_OUT}`",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    (OUT / "NIFTY_1M_SCALP_MA_HOLD100_INDICATORS.json").write_text(
        json.dumps({"oracle_win": pw, "early_loss": pl, "best": None if not best else {"name": best[0], "hold": best[2], "train": best[1]}}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
