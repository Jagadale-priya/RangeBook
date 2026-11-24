"""Explain today's buy-heavy session vs locked PA logic."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "market"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
import path_setup  # noqa: F401,E402
import kite_data  # noqa: E402

from prod_live.logic import pa_structure_live as pa  # noqa: E402


def main() -> int:
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=3, keep_partial=False
    )
    if err or raw is None:
        print("KITE", err)
        return 1
    bars = pa.norm_1m(raw)
    today = "2026-11-20"
    tb = bars[bars.index.strftime("%Y-%m-%d") == today]
    o = float(tb["Open"].iloc[0])
    hi = float(tb["High"].max())
    lo = float(tb["Low"].min())
    cl = float(tb["Close"].iloc[-1])
    or_bars = tb.iloc[:30]
    or_hi = float(or_bars["High"].max())
    or_lo = float(or_bars["Low"].min())
    broke_up = broke_dn = None
    for ts, row in tb.iloc[30:].iterrows():
        c = float(row["Close"])
        if broke_up is None and c > or_hi:
            broke_up = ts.strftime("%H:%M")
        if broke_dn is None and c < or_lo:
            broke_dn = ts.strftime("%H:%M")

    cfg = pa.load_locked_cfg()
    calls = pa.scan_session(tb, settle=True, cfg=cfg)
    v1 = pa.scan_session(tb, settle=True, cfg=pa.CFG_V1)

    checks = [
        "09:45",
        "10:00",
        "10:30",
        "11:00",
        "11:30",
        "12:00",
        "12:30",
        "13:00",
        "14:00",
        "15:00",
        "15:29",
    ]
    path = []
    for hm in checks:
        sl = tb[tb.index.strftime("%H:%M") == hm]
        if len(sl):
            path.append(f"{hm}={float(sl['Close'].iloc[0]):.1f}")

    print("DAY", today)
    print(
        f"open={o:.1f} high={hi:.1f} low={lo:.1f} close={cl:.1f} "
        f"up_from_open={hi-o:.1f} close_vs_open={cl-o:.1f}"
    )
    print(f"OR30 hi={or_hi:.1f} lo={or_lo:.1f} mid={(or_hi+or_lo)/2:.1f}")
    print(f"first_break_up={broke_up} first_break_dn={broke_dn}")
    print("path", " · ".join(path))
    print(f"LOCKED={cfg.name} or_side_align={cfg.or_side_align}")
    print(f"locked sides={[c.side for c in calls]}")
    for c in calls:
        print(
            f"  {c.hm} {c.side} {c.setup} entry={c.entry} SL={c.stop_loss} "
            f"-> pts={c.pts} R={c.R} mfe={c.mfe}"
        )
    if calls:
        first = calls[0]
        after = tb[tb.index.strftime("%H:%M") >= first.hm]
        after_hi = float(after["High"].max())
        print(
            f"after_first_entry max_high={after_hi:.1f} "
            f"run_from_entry={after_hi-first.entry:.1f}"
        )
        print(f"sum_pts={sum(c.pts or 0 for c in calls):.1f}")
    print("V1 (no OR-align) sides:")
    for c in v1:
        print(f"  {c.hm} {c.side} {c.setup} pts={c.pts}")
    # skipped sells = in v1 not in locked
    lock_keys = {(c.hm, c.side, c.setup) for c in calls}
    skipped = [c for c in v1 if (c.hm, c.side, c.setup) not in lock_keys]
    print("Skipped vs v1 (mostly counter-OR sells):")
    for c in skipped:
        print(f"  SKIP {c.hm} {c.side} {c.setup} pts={c.pts} reason would be counter-OR or body")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
