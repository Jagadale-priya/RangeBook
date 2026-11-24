"""Check whether locked 100% morning-strong rule fires on today (live Kite tape)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
import path_setup  # noqa: F401,E402
import kite_data  # noqa: E402
import nifty_morning_strong_thrust as nmst  # noqa: E402


def norm(df: pd.DataFrame) -> pd.DataFrame:
    w = df.copy()
    if getattr(w.index, "tz", None) is not None:
        w.index = w.index.tz_convert("Asia/Kolkata")
    else:
        w.index = w.index.tz_localize("Asia/Kolkata")
    w = w.rename(columns={c: str(c).title() for c in w.columns})
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in w.columns]
    w = w[cols].sort_index()
    w = w[~w.index.duplicated(keep="last")]
    hm = w.index.strftime("%H:%M")
    return w[(hm >= "09:15") & (hm <= "15:30")]


def hm(ts) -> str:
    t = pd.Timestamp(ts).tz_convert("Asia/Kolkata")
    return f"{int(t.hour):02d}:{int(t.minute):02d}"


def eval_locked(sess15: pd.DataFrame, sess5: pd.DataFrame) -> dict:
    """L5_u70_b80_fg_fb_mb18 locked research rule."""
    or_hi = float(sess15["High"].iloc[0])
    or_lo = float(sess15["Low"].iloc[0])
    day_open = float(sess15["Open"].iloc[0])
    first_up = first_dn = None
    for i in range(len(sess15)):
        c = float(sess15["Close"].iloc[i])
        if first_up is None and c > or_hi:
            first_up = i
        if first_dn is None and c < or_lo:
            first_dn = i
    down_first = (
        first_up is not None and first_dn is not None and first_dn < first_up
    )
    detail = {
        "or_hi": round(or_hi, 2),
        "or_lo": round(or_lo, 2),
        "day_open": round(day_open, 2),
        "day_hi": round(float(sess15["High"].max()), 2),
        "day_up": round(float(sess15["High"].max()) - day_open, 1),
        "down_first": down_first,
        "bars15": len(sess15),
        "bars5": len(sess5),
        "signals_checked": [],
    }
    if down_first:
        detail["result"] = "NO — down break first (forbid_both_sides)"
        return detail

    for i, ts in enumerate(sess15.index):
        h = hm(ts)
        if h < "09:45" or h > "11:30" or i < 2:
            continue
        row = sess15.iloc[i]
        c = float(row["Close"])
        o = float(row["Open"])
        hi = float(row["High"])
        lo = float(row["Low"])
        uplift = c - day_open
        prior_hi = max(float(sess15["High"].iloc[j]) for j in range(i - 2, i))
        rng = max(hi - lo, 1e-9)
        body = abs(c - o) / rng
        reasons = []
        if c <= or_hi:
            reasons.append("not_above_OR")
        if c <= o:
            reasons.append("not_green")
        if uplift < 70:
            reasons.append(f"uplift<{70}:{uplift:.1f}")
        if c <= prior_hi:
            reasons.append("no_prior2_break")
        if body < 0.80:
            reasons.append(f"body<{0.80}:{body:.3f}")
        chk = {
            "hm": h,
            "close": round(c, 2),
            "uplift": round(uplift, 1),
            "body": round(body, 3),
            "prior_hi": round(prior_hi, 2),
            "ok": not reasons,
            "reject": reasons,
        }
        detail["signals_checked"].append(chk)
        if reasons:
            continue
        # fill
        lim = or_hi + 5.0
        after = sess5[sess5.index > ts] if len(sess5) else sess15.iloc[i + 1 :]
        n = 0
        for thr, r2 in after.iterrows():
            h2 = hm(thr)
            if h2 > "13:00":
                break
            n += 1
            if n > 18:
                break
            if float(r2["Low"]) > lim:
                continue
            if float(r2["Close"]) <= or_hi:
                continue
            if float(r2["Close"]) <= float(r2["Open"]):
                continue
            detail["result"] = "YES — CALL"
            detail["sig_hm"] = h
            detail["fill_hm"] = h2
            detail["entry"] = round(lim, 2)
            detail["sl"] = round(lim - 30, 2)
            detail["t1"] = round(lim + 30, 2)
            detail["fill_bars"] = n
            detail["sig_uplift"] = round(uplift, 1)
            detail["sig_body"] = round(body, 3)
            return detail
        detail["result"] = f"NO — signal at {h} but no OR+5 green fill within 18×5m"
        detail["sig_hm"] = h
        detail["sig_uplift"] = round(uplift, 1)
        detail["sig_body"] = round(body, 3)
        return detail

    detail["result"] = "NO — no qualifying 15m thrust signal"
    return detail


def main() -> int:
    print("Pulling Kite 15m/5m…", flush=True)
    b15, e15 = kite_data.fetch_historical_candles(
        "NIFTY", "15minute", days=5, keep_partial=True
    )
    b5, e5 = kite_data.fetch_historical_candles(
        "NIFTY", "5minute", days=5, keep_partial=True
    )
    if e15 or e5 or b15 is None or b5 is None:
        print("KITE_ERROR", e15, e5)
        return 1
    bars15 = norm(b15)
    bars5 = norm(b5)
    today = str(pd.Timestamp(bars15.index[-1]).tz_convert("Asia/Kolkata").date())
    print("today", today, flush=True)
    s15 = bars15[bars15.index.strftime("%Y-%m-%d") == today]
    s5 = bars5[bars5.index.strftime("%Y-%m-%d") == today]
    print("15m bars", len(s15), "5m bars", len(s5), flush=True)
    print("--- session path ---", flush=True)
    if len(s15):
        or_hi = float(s15["High"].iloc[0])
        for ts, row in s15.iterrows():
            c = float(row["Close"])
            o = float(row["Open"])
            bf = (c - or_hi) / max(or_hi - float(s15["Low"].iloc[0]), 1e-9) if c > or_hi else 0
            body = abs(c - o) / max(float(row["High"]) - float(row["Low"]), 1e-9)
            print(
                hm(ts),
                f"O={o:.1f} H={float(row['High']):.1f} L={float(row['Low']):.1f} C={c:.1f}",
                f"uplift={c-float(s15['Open'].iloc[0]):.1f}",
                f"body={body:.2f}",
                f"bf={bf:.2f}" if c > or_hi else "",
                "GREEN" if c > o else "RED",
                flush=True,
            )

    locked = eval_locked(s15, s5)
    print("\n=== LOCKED 100% rule (L5_u70_b80) ===", flush=True)
    print("result:", locked["result"], flush=True)
    for k in (
        "or_hi",
        "day_open",
        "day_up",
        "down_first",
        "sig_hm",
        "fill_hm",
        "entry",
        "sl",
        "t1",
        "sig_uplift",
        "sig_body",
        "fill_bars",
    ):
        if k in locked:
            print(f"  {k}: {locked[k]}", flush=True)
    print("signal checks:", flush=True)
    for chk in locked.get("signals_checked") or []:
        print(" ", chk, flush=True)

    # live-wired module (looser L5_u50_b55)
    asof = s15.index[-1] if len(s15) else None
    live = nmst.evaluate(s15, s5, asof=asof, price=float(s15["Close"].iloc[-1]) if len(s15) else None)
    print("\n=== LIVE wire (L5_u50_b55_fg) ===", flush=True)
    if live:
        print("YES", live.get("message"), "entry", live.get("entry"), "hm", live.get("hm"), flush=True)
    else:
        print("NO — live module did not fire", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
