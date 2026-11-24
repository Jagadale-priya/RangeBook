"""Test locked Option Blue PA logic on NIFTY / BANKNIFTY / SENSEX."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app"), str(ROOT / "app" / "fno"), str(ROOT / "app" / "market")]
import kite_data  # noqa: E402
from prod_live.logic import pa_structure_live as pa  # noqa: E402


def run_sym(sym: str, cfg: pa.PaConfig) -> None:
    print(f"=== {sym} ===", flush=True)
    raw, err = kite_data.fetch_historical_candles(sym, "minute", days=40, keep_partial=False)
    if err or raw is None:
        print("FETCH_ERR", err, flush=True)
        return
    bars = pa.norm_1m(raw)
    all_days = sorted({str(ts.date()) for ts in bars.index})
    days = all_days[-22:]
    si = max(0, all_days.index(days[0]) - 2)
    frame = bars[bars.index.strftime("%Y-%m-%d").isin(set(all_days[si:]))]
    calls = [c for c in pa.scan_session(frame, settle=True, cfg=cfg) if c.day in set(days)]
    s = pa.summarize(calls)
    by = Counter(c.day for c in calls)
    with_n = sum(1 for d in days if by[d] > 0)
    blank = sum(1 for d in days if by[d] == 0)
    print(f"window {days[0]}->{days[-1]} sessions={len(days)}", flush=True)
    print(
        f"n={s.get('n')} hit={s.get('hit_pct')} avgR={s.get('avg_R')} "
        f"sum={s.get('sum_pts')} hit1R={s.get('hit_1R_pct')}",
        flush=True,
    )
    print(f"by_setup={s.get('by_setup')}", flush=True)
    print(
        f"days_with_calls={with_n} blank={blank} avg/day={round(len(calls)/len(days), 2)}",
        flush=True,
    )
    print("per-day:", flush=True)
    for d in days:
        dc = [c for c in calls if c.day == d]
        if not dc:
            print(f"  {d}  n=0", flush=True)
            continue
        bits = ",".join(f"{c.hm}{c.side[0]}" for c in dc)
        print(f"  {d}  n={len(dc)}  {bits}", flush=True)
    today = days[-1]
    tc = [c for c in calls if c.day == today]
    print("today", today, pa.summarize(tc), flush=True)
    for c in tc:
        print(
            f"  {c.hm} {c.side} {c.setup} E={c.entry} SL={c.stop_loss} R={c.R} {c.exit_why}",
            flush=True,
        )
    print(flush=True)


def main() -> int:
    cfg = pa.load_locked_cfg()
    print(
        f"cfg={cfg.name} sl_kill={cfg.sl_kill_mode} sr={cfg.sr_gate} "
        f"or_retest={cfg.allow_or_retest} lo={cfg.trade_lo} hi={cfg.trade_hi}",
        flush=True,
    )
    print(flush=True)
    for sym in ("NIFTY", "BANKNIFTY", "SENSEX"):
        run_sym(sym, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
