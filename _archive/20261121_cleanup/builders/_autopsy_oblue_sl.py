"""Deep autopsy of Option Blue hard-SL calls vs winners."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app"), str(ROOT / "app" / "fno"), str(ROOT / "app" / "market")]
import kite_data  # noqa: E402
from prod_live.logic import pa_structure_live as pa  # noqa: E402


def main() -> int:
    cfg = pa.load_locked_cfg()
    raw, err = kite_data.fetch_historical_candles("NIFTY", "minute", days=40, keep_partial=False)
    assert not err, err
    bars = pa.norm_1m(raw)
    all_days = sorted({str(ts.date()) for ts in bars.index})
    days = all_days[-22:]
    si = max(0, all_days.index(days[0]) - 2)
    frame = bars[bars.index.strftime("%Y-%m-%d").isin(set(all_days[si:]))]
    calls = [c for c in pa.scan_session(frame, settle=True, cfg=cfg) if c.day in set(days)]
    work = pa.norm_1m(frame)
    o, h, l, c = work["Open"].values, work["High"].values, work["Low"].values, work["Close"].values
    atr = pa.atr14(h, l, c)
    idx = work.index
    hm = {(pa._day(ts), pa._hm(ts)): i for i, ts in enumerate(idx)}

    print("=== HARD SL CALLS ===", flush=True)
    for call in calls:
        if call.exit_why != "sl":
            continue
        i = hm[(call.day, call.hm)]
        sr = pa.build_sr_map(o, h, l, c, atr, idx, i, lookback_days=2)
        liq = pa.liquidity_read(o, h, l, c, i, call.side, sr)
        rr = pa.reward_risk(call.side, float(call.entry), float(call.stop_loss), sr)
        cf = pa._candle_bar(o, h, l, c, i)
        a = float(atr[i])
        story = []
        for j in range(max(0, i - 4), i + 1):
            f = pa._candle_bar(o, h, l, c, j)
            tag = "B" if f["bull"] else ("R" if f["bear"] else "D")
            story.append(
                f"{tag} body={f['body_frac']:.2f} cl={f['close_loc']:.2f} "
                f"u={f['upper_frac']:.2f} lo={f['lower_frac']:.2f}"
            )
        print(
            call.day,
            call.hm,
            call.side,
            call.setup,
            "E",
            call.entry,
            "SL",
            call.stop_loss,
            "risk",
            call.risk,
            flush=True,
        )
        print("  rr", round(rr["rr"], 2), "liq", liq, "body", round(cf["body_frac"], 3), flush=True)
        print("  res", sr.get("nearest_res"), "sup", sr.get("nearest_sup"), flush=True)
        print("  htf", call.htf_bias, "mfe", call.mfe, "mae", call.mae, flush=True)
        print("  story:", " | ".join(story), flush=True)
        # bars to SL + first bar adverse
        for j in range(i + 1, min(len(c), i + 50)):
            hit = (call.side == "BUY" and float(l[j]) <= float(call.stop_loss)) or (
                call.side == "SELL" and float(h[j]) >= float(call.stop_loss)
            )
            if hit:
                print("  bars_to_sl", j - i, flush=True)
                break
        # expansion vs prior bar
        prev_rng = float(h[i - 1]) - float(l[i - 1]) if i >= 1 else a
        cur_rng = float(h[i]) - float(l[i])
        print(
            "  rng_atr",
            round(cur_rng / a, 3),
            "expand_vs_prev",
            round(cur_rng / max(prev_rng, 1e-9), 3),
            flush=True,
        )
        # broke into level then failed? distance to opp
        if call.side == "BUY" and sr.get("nearest_res"):
            print(
                "  opp_dist_atr",
                round((float(sr["nearest_res"]["price"]) - float(call.entry)) / a, 3),
                flush=True,
            )
        if call.side == "SELL" and sr.get("nearest_sup"):
            print(
                "  opp_dist_atr",
                round((float(call.entry) - float(sr["nearest_sup"]["price"])) / a, 3),
                flush=True,
            )
        # impulse 5
        if i >= 5:
            imp = (float(c[i]) - float(c[i - 5])) / a
            if call.side == "SELL":
                imp = -imp
            print("  impulse5", round(imp, 3), flush=True)

    def pack(call):
        i = hm[(call.day, call.hm)]
        sr = pa.build_sr_map(o, h, l, c, atr, idx, i, lookback_days=2)
        cf = pa._candle_bar(o, h, l, c, i)
        a = float(atr[i])
        if call.side == "BUY":
            od = (
                (float(sr["nearest_res"]["price"]) - float(call.entry)) / a
                if sr.get("nearest_res")
                else 9.0
            )
            bd = (
                (float(call.entry) - float(sr["nearest_sup"]["price"])) / a
                if sr.get("nearest_sup")
                else 9.0
            )
        else:
            od = (
                (float(call.entry) - float(sr["nearest_sup"]["price"])) / a
                if sr.get("nearest_sup")
                else 9.0
            )
            bd = (
                (float(sr["nearest_res"]["price"]) - float(call.entry)) / a
                if sr.get("nearest_res")
                else 9.0
            )
        impulse = (float(c[i]) - float(c[max(0, i - 5)])) / a
        if call.side == "SELL":
            impulse = -impulse
        rng_atr = (float(h[i]) - float(l[i])) / a
        prev_rng = float(h[i - 1]) - float(l[i - 1]) if i >= 1 else a
        expand = rng_atr / max(prev_rng / a, 1e-9)
        streak = 0
        for j in range(i, -1, -1):
            f = pa._candle_bar(o, h, l, c, j)
            ok = (call.side == "BUY" and f["bull"]) or (call.side == "SELL" and f["bear"])
            if ok:
                streak += 1
            else:
                break
        # micro: next bar would be unknown; use entry bar vs OR mid
        return {
            "opp_d": od,
            "base_d": bd,
            "body": cf["body_frac"],
            "close": cf["close_loc"],
            "impulse": impulse,
            "rng_atr": rng_atr,
            "expand": expand,
            "streak": streak,
            "risk": float(call.risk),
            "upper": cf["upper_frac"],
            "lower": cf["lower_frac"],
            "mins": int(call.hm.split(":")[0]) * 60 + int(call.hm.split(":")[1]),
        }

    slp = [pack(c) for c in calls if c.exit_why == "sl"]
    wp = [pack(c) for c in calls if c.win]
    print("\n=== MEAN win vs SL ===", flush=True)
    for k in (
        "opp_d",
        "base_d",
        "body",
        "close",
        "impulse",
        "rng_atr",
        "expand",
        "streak",
        "risk",
        "upper",
        "lower",
        "mins",
    ):
        print(
            k,
            "win",
            round(float(np.mean([p[k] for p in wp])), 3),
            "sl",
            round(float(np.mean([p[k] for p in slp])), 3),
            flush=True,
        )

    # Find thresholds that kill SLs with 0 win hits
    print("\n=== SEARCH winner-safe thresholds ===", flush=True)
    candidates = []
    # impulse too high = chase
    for thr in np.arange(0.5, 3.0, 0.1):
        w_k = sum(1 for p in wp if p["impulse"] >= thr)
        s_k = sum(1 for p in slp if p["impulse"] >= thr)
        if w_k == 0 and s_k > 0:
            candidates.append(("impulse_ge", thr, s_k, w_k))
    for thr in np.arange(0.2, 2.0, 0.05):
        w_k = sum(1 for p in wp if p["opp_d"] <= thr)
        s_k = sum(1 for p in slp if p["opp_d"] <= thr)
        if w_k == 0 and s_k > 0:
            candidates.append(("opp_d_le", thr, s_k, w_k))
    for thr in np.arange(0.5, 2.5, 0.1):
        w_k = sum(1 for p in wp if p["rng_atr"] >= thr)
        s_k = sum(1 for p in slp if p["rng_atr"] >= thr)
        if w_k == 0 and s_k > 0:
            candidates.append(("rng_atr_ge", thr, s_k, w_k))
    for thr in np.arange(1.2, 4.0, 0.1):
        w_k = sum(1 for p in wp if p["expand"] >= thr)
        s_k = sum(1 for p in slp if p["expand"] >= thr)
        if w_k == 0 and s_k > 0:
            candidates.append(("expand_ge", thr, s_k, w_k))
    for thr in range(1, 8):
        w_k = sum(1 for p in wp if p["streak"] >= thr)
        s_k = sum(1 for p in slp if p["streak"] >= thr)
        if w_k == 0 and s_k > 0:
            candidates.append(("streak_ge", thr, s_k, w_k))
    for thr in np.arange(0.75, 0.95, 0.01):
        # BUY close too high exhaustion — but side-aware hard; use upper wick
        w_k = sum(1 for p in wp if p["upper"] >= thr)
        s_k = sum(1 for p in slp if p["upper"] >= thr)
        if w_k == 0 and s_k > 0:
            candidates.append(("upper_ge", thr, s_k, w_k))

    # combo: high impulse AND close to opp
    for ithr in np.arange(0.3, 2.0, 0.1):
        for othr in np.arange(0.05, 0.8, 0.05):
            w_k = sum(1 for p in wp if p["impulse"] >= ithr and p["opp_d"] <= othr)
            s_k = sum(1 for p in slp if p["impulse"] >= ithr and p["opp_d"] <= othr)
            if w_k == 0 and s_k > 0:
                candidates.append((f"imp>={ithr:.1f}&opp<={othr:.2f}", None, s_k, w_k))

    # combo: expand chase into resistance
    for ethr in np.arange(1.3, 3.0, 0.1):
        for othr in np.arange(0.1, 0.8, 0.05):
            w_k = sum(1 for p in wp if p["expand"] >= ethr and p["opp_d"] <= othr)
            s_k = sum(1 for p in slp if p["expand"] >= ethr and p["opp_d"] <= othr)
            if w_k == 0 and s_k > 0:
                candidates.append((f"exp>={ethr:.1f}&opp<={othr:.2f}", None, s_k, w_k))

    # allow 0 win kill; sort by SL kill
    candidates.sort(key=lambda x: -x[2])
    seen = set()
    for name, thr, sk, wk in candidates[:40]:
        key = (name, thr, sk)
        if key in seen:
            continue
        seen.add(key)
        print(f"SAFE {name} thr={thr} kill_SL={sk}/{len(slp)} win_kill={wk}", flush=True)

    # near-safe: kill 1 win max if kill >=2 SL
    print("\n=== NEAR-SAFE (≤1 win) ===", flush=True)
    near = []
    for ithr in np.arange(0.2, 2.5, 0.1):
        for othr in np.arange(0.05, 1.0, 0.05):
            w_k = sum(1 for p in wp if p["impulse"] >= ithr and p["opp_d"] <= othr)
            s_k = sum(1 for p in slp if p["impulse"] >= ithr and p["opp_d"] <= othr)
            if w_k <= 1 and s_k >= 2 and s_k > w_k:
                near.append((f"imp>={ithr:.1f}&opp<={othr:.2f}", s_k, w_k))
    for ethr in np.arange(1.1, 3.0, 0.1):
        for othr in np.arange(0.05, 1.0, 0.05):
            w_k = sum(1 for p in wp if p["expand"] >= ethr and p["opp_d"] <= othr)
            s_k = sum(1 for p in slp if p["expand"] >= ethr and p["opp_d"] <= othr)
            if w_k <= 1 and s_k >= 2 and s_k > w_k:
                near.append((f"exp>={ethr:.1f}&opp<={othr:.2f}", s_k, w_k))
    # streak exhausted into opp
    for sth in range(3, 8):
        for othr in np.arange(0.1, 0.9, 0.05):
            w_k = sum(1 for p in wp if p["streak"] >= sth and p["opp_d"] <= othr)
            s_k = sum(1 for p in slp if p["streak"] >= sth and p["opp_d"] <= othr)
            if w_k <= 1 and s_k >= 2 and s_k > w_k:
                near.append((f"streak>={sth}&opp<={othr:.2f}", s_k, w_k))
    near.sort(key=lambda x: (-x[1], x[2]))
    seen2 = set()
    for name, sk, wk in near[:30]:
        if name in seen2:
            continue
        seen2.add(name)
        print(f"NEAR {name} kill_SL={sk}/{len(slp)} win_kill={wk}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
