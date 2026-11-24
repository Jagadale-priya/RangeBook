"""Diagnose Scalper today 1m bar coverage (why chart stalls after open)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app"), str(ROOT / "app" / "fno"), str(ROOT / "app" / "market")]

import path_setup  # noqa: F401
import fno_scalper_1m as sc
import kite_data


def main() -> None:
    now = sc._now_ist()
    today = str(now.date())
    open_m = 9 * 60 + 15
    now_m = int(now.hour * 60 + now.minute)
    expect = max(0, min(now_m, 15 * 60 + 29) - open_m + 1) if sc._session_open_now() else 0
    print(f"now={now} session_open={sc._session_open_now()} expect_today≈{expect}")
    print(f"kite_enabled={kite_data.kite_enabled()} kite_dead={sc._kite_is_dead()} ws={sc._ws_ticks_alive('NIFTY')}")

    # Direct kite hist
    t0 = time.time()
    df, err = kite_data.fetch_historical_candles("NIFTY", interval="minute", days=3, keep_partial=True)
    print(f"kite hist took={int((time.time()-t0)*1000)}ms err={err} n={0 if df is None else len(df)}")
    if df is not None and len(df):
        raw = sc._norm_bars(df)
        today_bars = raw[[str(ts.date()) == today for ts in raw.index]]
        print(f"  kite norm n={len(raw)} today={len(today_bars)} last={raw.index.max()}")
        if len(today_bars):
            print(f"  today first={today_bars.index.min()} last={today_bars.index.max()}")
            print(f"  today times={[ts.strftime('%H:%M') for ts in today_bars.index[:12]]}...")

    # Via load_1m_bars (with cache)
    sc._force_refresh_symbol("NIFTY")
    t0 = time.time()
    raw2, note = sc.load_1m_bars("NIFTY", days=2)
    print(f"load_1m_bars note={note} n={len(raw2)} took={int((time.time()-t0)*1000)}ms")
    if len(raw2):
        today_bars = raw2[[str(ts.date()) == today for ts in raw2.index]]
        print(f"  today={len(today_bars)} last={raw2.index.max()}")
        if len(today_bars):
            print(f"  today first={today_bars.index.min()} last={today_bars.index.max()}")

    # scan chart candles
    sc._force_refresh_symbol("NIFTY")
    t0 = time.time()
    out = sc.scan_scalper("NIFTY", days=2, chart_days=1, mode="oracle_t15", force_refresh=True)
    candles = out.get("candles") or []
    print(f"scan ok={out.get('ok')} cached={out.get('cached')} n_candles={len(candles)} took={out.get('took_ms')}")
    if candles:
        import pandas as pd

        def day_of(t):
            return str(pd.Timestamp(int(t), unit="s", tz="UTC").tz_convert("Asia/Kolkata").date())

        today_c = [c for c in candles if day_of(c["time"]) == today]
        print(f"  chart today candles={len(today_c)} expect≈{expect}")
        if today_c:
            times = [
                pd.Timestamp(int(c["time"]), unit="s", tz="UTC").tz_convert("Asia/Kolkata").strftime("%H:%M")
                for c in today_c
            ]
            print(f"  today times={times}")
        print(f"  last candle time={candles[-1].get('time')} feed note={out.get('note')}")

    tick = sc.scalper_tick("NIFTY")
    print(
        f"tick ok={tick.get('ok')} feed={tick.get('feed')} candle={tick.get('candle')} "
        f"quote={tick.get('quote')} note={tick.get('note')}"
    )


if __name__ == "__main__":
    main()
