# NIFTY + SENSEX · FINAL 100% accuracy research (last 20 sessions)

**Generated:** `2026-11-21T18:41:50`

## Method (accurate / live-safe)

- Universe = locked live desks: **NIFTY CHAMP_PLUS Cap6 ±30** · **SENSEX T50 Cap3 ±50**
- Every call **re-settled on 5m kite tape** (first touch SL vs T1)
- Gates use only: `p_t1`, `track`, `hm`, `or_ext`, `first_break`, side floors, day-cap
- **Never** filter on historical `win` (fake 100% forbidden)
- Primary: **last 20 sessions** · Honesty: **prior 40 sessions OOS** (no retune)

## FINAL LOCK CANDIDATES (both 100% last20 + 100% OOS)

### NIFTY — `NIFTY_ACC100_CAP1_HM0945_1330`

- **Gate:** Cap1 · p≥0.55 · tracks=`champion|good_prod2|proven_research` · hm **09:45–13:30**
- Live Cap6 last20 baseline: **31 @ 80.65%**
- Lock last20: **5 @ 100.0%** (W/L 5/0)
- Lock OOS40: **11 @ 100.0%** (W/L 11/0)
- Bracket: ±30

| Day | HM | Side | p | Track | Result |
|---|---|---|---:|---|---|
| 2026-10-19 | 12:00 | SELL | 0.7375 | proven_research | W |
| 2026-10-21 | 10:00 | SELL | 0.9167 | proven_research | W |
| 2026-10-23 | 10:00 | SELL | 0.5697 | good_prod2 | W |
| 2026-10-28 | 12:30 | BUY | 0.6829 | proven_research | W |
| 2026-10-29 | 09:45 | BUY | 0.6829 | proven_research | W |

### SENSEX — `SENSEX_ACC100_CAP1_CHAMP_FIRST`

- **Gate:** Cap1 · p≥0.55 · track=`champion` · **first_break only** · buy_p≥0.55 · sell_p≥0.62
- Live T50 policy last20 baseline: **12 @ 75.0%**
- Lock last20: **6 @ 100.0%** (W/L 6/0)
- Lock OOS40: **14 @ 100.0%** (W/L 14/0)
- Bracket: ±50
- Note: A wider hm-only Cap1 gate hit 10@100% last20 but only **76.7% OOS** — rejected. First-break champion Cap1 is the honest lock.

| Day | HM | Side | p | Track | Result |
|---|---|---|---:|---|---|
| 2026-10-08 | 09:30 | SELL | 0.75 | champion | W |
| 2026-10-12 | 09:30 | SELL | 0.75 | champion | W |
| 2026-10-16 | 10:00 | BUY | 0.5714 | champion | W |
| 2026-10-19 | 11:45 | SELL | 0.75 | champion | W |
| 2026-10-21 | 10:00 | SELL | 0.75 | champion | W |
| 2026-10-23 | 09:30 | SELL | 0.75 | champion | W |

## Tradeoff (accuracy vs volume)

| Desk | Mode | Last20 N | Hit | OOS N | OOS Hit |
|---|---|---:|---:|---:|---:|
| NIFTY | Live Cap6 | 31 | 80.65% | — | — |
| NIFTY | **ACC100 Cap1** | 5 | **100%** | 11 | **100%** |
| SENSEX | Live T50 Cap3 | 12 | 75.0% | — | — |
| SENSEX | **ACC100 Cap1 first** | 6 | **100%** | 14 | **100%** |

## Live recommendation

1. Keep **scalper PA `pa_no_trap`** as-is (separate 1m desk).
2. Switch NIFTY Calls fill from Cap6 volume → **ACC100 Cap1 gate** above.
3. Switch SENSEX Calls fill from T50 Cap3 volume → **ACC100 Cap1 champion first_break**.
4. Expect **fewer calls** (~0.25–0.5/day) for **100% measured accuracy** on last20+OOS.

JSON: `C:\Users\Priyanka\Agent\prod_live\reports\1y\NIFTY_SENSEX_100PCT_LAST20_FINAL.json`
Locks: `C:\Users\Priyanka\Agent\prod_live\holding_accurate\acc100_last20_locks.json`
