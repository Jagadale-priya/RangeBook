"""Nov19: does dual payload block afternoon thrust in live gate order?"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "prod_live"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
os.environ.setdefault("USE_DUAL_TRACK", "1")
os.environ.setdefault("SUPPRESS_DUAL_LIST", "1")
os.environ.setdefault("ENABLE_NIFTY_AFTERNOON_THRUST", "1")

import kite_data  # noqa: E402
import nifty_afternoon_thrust as nat  # noqa: E402
import nifty_live_dual_track as nd  # noqa: E402


def norm(df: pd.DataFrame) -> pd.DataFrame:
    w = df.copy()
    if w.index.tz is not None:
        w.index = w.index.tz_convert("Asia/Kolkata")
    else:
        w.index = w.index.tz_localize("Asia/Kolkata")
    w = w.rename(columns={c: str(c).title() for c in w.columns})
    return w


def main() -> int:
    df, err = kite_data.fetch_historical_candles(
        "NIFTY", interval="15minute", days=8, keep_partial=True
    )
    if err or df is None:
        print("fail", err)
        return 1
    bars = norm(df)
    day = "2026-11-19"
    d = bars[bars.index.strftime("%Y-%m-%d") == day]
    print("Nov19 bars", len(d))
    for ts, row in d.iterrows():
        hm = pd.Timestamp(ts).tz_convert("Asia/Kolkata").strftime("%H:%M")
        if hm < "12:45":
            continue
        window = bars[bars.index <= ts]
        dual = None
        try:
            ev = nd.evaluate(
                window, asof=pd.Timestamp(ts).to_pydatetime(), price=float(row["Close"])
            )
            if isinstance(ev, dict) and isinstance(ev.get("call_payload"), dict):
                dual = ev["call_payload"]
                if dual.get("decision") not in ("BUY", "SELL"):
                    dual = None
        except Exception as exc:
            print(hm, "dual_err", exc)
            continue
        dual_blocks = isinstance(dual, dict) and dual.get("decision") in ("BUY", "SELL")
        thrust_raw = nat.evaluate(
            window, asof=pd.Timestamp(ts).to_pydatetime(), price=float(row["Close"])
        )
        ds = None
        if isinstance(dual, dict):
            ds = f"{dual.get('decision')}/{dual.get('track')}/p={dual.get('p_t1')}"
        print(
            hm,
            "dual=",
            ds,
            "blocks=",
            dual_blocks,
            "thrust_raw=",
            bool(thrust_raw),
            "uplift=",
            (thrust_raw or {}).get("uplift_from_13"),
            "live_would_list_thrust=",
            (not dual_blocks) and bool(thrust_raw),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
