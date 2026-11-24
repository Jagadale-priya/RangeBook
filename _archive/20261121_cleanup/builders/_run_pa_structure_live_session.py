"""Live poller — PA structure desk during market hours.

Every ~60s: pull Kite NIFTY 1m (today), evaluate closed bars, toast new entries
with structure SL (no fixed target).

  python -u prod_live/tests/builders/_run_pa_structure_live_session.py
  python -u prod_live/tests/builders/_run_pa_structure_live_session.py --once
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
    str(ROOT / "app" / "desk"),
    str(ROOT / "prod_live" / "tests" / "builders"),
]
import path_setup  # noqa: F401,E402
import kite_data  # noqa: E402

from prod_live.adapters.live_session_pa import annotate_from_1m  # noqa: E402
from prod_live.logic.pa_structure_live import norm_1m  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")


def in_session(now: datetime | None = None) -> bool:
    n = now or datetime.now(IST)
    if n.weekday() >= 5:
        return False
    m = n.hour * 60 + n.minute
    return (9 * 60 + 20) <= m <= (15 * 60 + 25)


def pull_today():
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=3, keep_partial=False
    )
    if err or raw is None:
        return None, err
    bars = norm_1m(raw)
    today = datetime.now(IST).date().isoformat()
    return bars[bars.index.strftime("%Y-%m-%d") == today], None


def tick(emit: bool = True) -> dict:
    bars, err = pull_today()
    if err or bars is None or bars.empty:
        return {"ok": False, "err": err or "no bars"}
    meta = annotate_from_1m(bars, emit_notify=emit)
    return {"ok": True, **meta, "bars": len(bars)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="single evaluate then exit")
    ap.add_argument("--force", action="store_true", help="run even outside session")
    ap.add_argument("--no-notify", action="store_true")
    ap.add_argument("--sleep", type=int, default=55)
    args = ap.parse_args()

    emit = not args.no_notify

    def run_one():
        now = datetime.now(IST)
        print(f"[{now.strftime('%H:%M:%S')}] PA evaluate…", flush=True)
        out = tick(emit=emit)
        if not out.get("ok"):
            print(f"  FAIL {out.get('err')}", flush=True)
            return
        print(
            f"  bars={out.get('bars')} day_calls={out.get('n_day')} "
            f"added={out.get('n_added')} notified={len(out.get('notified') or [])}",
            flush=True,
        )
        for r in out.get("added") or []:
            print(
                f"  NEW {r.get('hm')} {r.get('side')} {r.get('setup')} "
                f"entry={r.get('entry')} SL={r.get('stop_loss')} risk={r.get('risk')}",
                flush=True,
            )

    if args.once or args.force:
        if not args.force and not in_session() and args.once:
            print("Outside session — use --force to evaluate anyway", flush=True)
        run_one()
        return 0

    print("PA_STRUCTURE_SL_LIVE poller armed (Ctrl+C to stop)", flush=True)
    while True:
        if in_session():
            try:
                run_one()
            except Exception as exc:
                print(f"  ERR {exc}", flush=True)
        else:
            now = datetime.now(IST)
            print(f"[{now.strftime('%H:%M:%S')}] outside session — idle", flush=True)
            time.sleep(120)
            continue
        time.sleep(max(20, int(args.sleep)))


if __name__ == "__main__":
    raise SystemExit(main())
