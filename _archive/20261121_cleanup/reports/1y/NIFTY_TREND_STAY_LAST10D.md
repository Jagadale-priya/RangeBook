# NIFTY trend-stay · long-stay pullback rule

**Source:** `kite` 5m · **cost:** 1.0 pt · **probability gate:** off (no model cols)

## Rule (frozen)

- Balance 09:15–10:15 · width 25–160
- 15m close beyond IBH/IBL + same side of VWAP
- Entry = first pullback touch + close back in break direction (not the break)
- Chase >25 pts without touch → no call
- Initial stop 15 pts inside level · reject risk >40
- Trail completed post-entry 15m swing · VWAP close exit · flat 14:45 · no reverse
- Module: `prod_live/logic/nifty_trend_stay.py`

## Last 10 sessions

- sessions: **10**
- calls: **2**
- wins / losses: **1 / 1**
- hit rate: **50.0%**
- avg winner / loser: **86.00 / -28.85**
- winner÷|loser|: **2.98** (keep if ≥2)
- net points: **57.15**
- no-call days: **8**
- reasons: `{'balance_width_out_of_range': 5, 'stop': 2, 'price_ran_away_before_pullback': 1, 'missing_balance': 1, 'no_pullback_after_break': 1}`

### Day-by-day

| Date | Status | Side | Width | Signal | Entry | Stop0 | Exit | Pts | MFE | Reason |
|---|---|---|---:|---|---:|---:|---|---:|---:|---|
| 2026-11-05 | no_call | buy | 145.9 | 12:45 | —/— | — | — | — | — | price_ran_away_before_pullback |
| 2026-11-06 | no_call | — | 285.5 | — | —/— | — | — | — | — | balance_width_out_of_range |
| 2026-11-08 | no_call | — | — | — | —/— | — | — | — | — | missing_balance |
| 2026-11-09 | no_call | — | 209.2 | — | —/— | — | — | — | — | balance_width_out_of_range |
| 2026-11-11 | no_call | — | 160.5 | — | —/— | — | — | — | — | balance_width_out_of_range |
| 2026-11-12 | no_call | — | 241.8 | — | —/— | — | — | — | — | balance_width_out_of_range |
| 2026-11-13 | stop | buy | 151.9 | 10:30 | 10:45/25242.25 | 25214.40 | 10:55 | -27.8 | 1.8 | stop |
| 2026-11-16 | no_call | — | 142.2 | — | —/— | — | — | — | — | no_pullback_after_break |
| 2026-11-17 | stop | buy | 119.5 | 10:15 | 10:40/25389.95 | 25371.75 | 12:30 | 87.0 | 111.4 | stop |
| 2026-11-18 | no_call | — | 184.6 | — | —/— | — | — | — | — | balance_width_out_of_range |

## Context windows

| Window | Calls | W/L | Hit | Avg W | Avg L | W÷|L| | Net | No-call |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| last 10 | 2 | 1/1 | 50.0% | 86.00 | -28.85 | 2.98 | 57.15 | 8 |
| last 20 | 3 | 1/2 | 33.3% | 86.00 | -22.60 | 3.81 | 40.80 | 17 |
| last 40 | 9 | 5/4 | 55.6% | 35.05 | -20.19 | 1.74 | 94.50 | 31 |
| last 60 | 20 | 8/11 | 40.0% | 27.49 | -12.55 | 2.19 | 81.90 | 40 |

### Taken calls · last 40

| Date | Side | Width | Entry | Stop0 | Status | Pts | MFE |
|---|---|---:|---:|---:|---|---:|---:|
| 2026-09-23 | buy | 65.0 | 23417.35 | 23399.55 | stop | 9.7 | 28.6 |
| 2026-09-24 | sell | 76.5 | 23195.70 | 23220.45 | stop | 16.0 | 30.9 |
| 2026-09-30 | buy | 96.0 | 22768.15 | 22740.75 | stop | 7.5 | 41.2 |
| 2026-10-06 | buy | 105.8 | 22670.40 | 22652.35 | stop | -18.1 | 1.2 |
| 2026-10-07 | buy | 114.7 | 22705.10 | 22677.95 | stop | -15.5 | 5.7 |
| 2026-10-08 | sell | 153.3 | 22435.30 | 22460.70 | stop | 60.0 | 106.8 |
| 2026-10-27 | buy | 151.3 | 22804.85 | 22789.50 | stop | -15.3 | 3.2 |
| 2026-11-13 | buy | 151.9 | 25242.25 | 25214.40 | stop | -27.8 | 1.8 |
| 2026-11-17 | buy | 119.5 | 25389.95 | 25371.75 | stop | 87.0 | 111.4 |

CSV: `prod_live/reports/1y/NIFTY_TREND_STAY_LAST10D.csv`
