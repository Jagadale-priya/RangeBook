"""Smoke: Nov19 afternoon confident thrust lists via live CHAMP fill path.

  python -u prod_live/tests/builders/_smoke_afternoon_thrust_live.py
"""
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
from prod_live.logic.champ_plus_live import ensure_session_calls  # noqa: E402


def norm(df: pd.DataFrame) -> pd.DataFrame:
    w = df.copy()
    if w.index.tz is not None:
        w.index = w.index.tz_convert("Asia/Kolkata")
    else:
        w.index = w.index.tz_localize("Asia/Kolkata")
    w = w.rename(columns={c: str(c).title() for c in w.columns})
    return w


def main() -> int:
    # Gate helpers
    fake_dual = {"decision": "BUY", "track": "champion", "p_t1": 0.7}
    assert nat.dual_blocks_thrust(fake_dual, suppress_dual_list=True) is False
    assert nat.dual_blocks_thrust(fake_dual, suppress_dual_list=False) is True
    print("OK dual_blocks_thrust suppress-aware")

    df, err = kite_data.fetch_historical_candles(
        "NIFTY", interval="15minute", days=8, keep_partial=True
    )
    if err or df is None:
        print("kite fail", err)
        return 1
    bars = norm(df)
    day = "2026-11-19"
    d = bars[bars.index.strftime("%Y-%m-%d") == day]
    fire = None
    for ts, row in d.iterrows():
        hm = pd.Timestamp(ts).tz_convert("Asia/Kolkata").strftime("%H:%M")
        if hm != "14:00":
            continue
        window = bars[bars.index <= ts]
        # even with a suppressed dual BUY present, thrust must evaluate
        assert not nat.dual_blocks_thrust(fake_dual, suppress_dual_list=True)
        fire = nat.evaluate(
            window, asof=pd.Timestamp(ts).to_pydatetime(), price=float(row["Close"])
        )
        print("14:00 thrust", bool(fire), fire and {k: fire[k] for k in ("decision", "track", "entry", "hm", "uplift_from_13")})
        break
    if not fire:
        print("FAIL: expected thrust FIRE at 14:00 on", day)
        return 2

    meta = ensure_session_calls(
        day,
        dual_call=fire,
        hm=fire.get("hm") or "14:00",
        entry=float(fire["entry"]),
    )
    added = meta.get("added") or []
    day_calls = meta.get("day_calls") or []
    conf = [
        r
        for r in day_calls
        if str(r.get("track")) == "confident"
        or r.get("afternoon_thrust")
        or str(r.get("hm") or "")[:5] == "14:00"
    ]
    print(
        "ensure_session_calls",
        "n_added=",
        meta.get("n_added"),
        "n_day=",
        meta.get("n_day"),
        "confident_or_1400=",
        len(conf),
    )
    for r in conf:
        print(
            " ",
            r.get("hm"),
            r.get("decision"),
            r.get("track"),
            r.get("entry"),
            r.get("source"),
            r.get("afternoon_thrust"),
        )
    if not conf and not added:
        # may already be in ledger from prior run
        print("WARN: no new add — check ledger already has 14:00")
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
