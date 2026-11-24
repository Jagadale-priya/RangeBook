# NIFTY ORB30 VWAP futures · refined (description-aligned)

**Source:** `kite` 5m · **cost:** 1.0 pt · **probability gate:** off (no model cols on tape)

## Refactors vs prior code

1. **Entry at the level** — fill ORH/ORL when the next bar still trades it (`at_level`); else next trade only if ≤10 pts past (`next_trade`).
2. **Stop through the level** — buy stop = ORH−12, sell stop = ORL+12 (not entry±12).
3. **Target from fill** — entry±20.
4. **Failed fill ≠ day consumed** — keep scanning for a later valid break (still one live trade; no reverse after a stop).
5. **VIX expected range** — annotated when `india_vix` present (price × VIX/100 / √252); width gate stays frozen at 30–90.

## Self-check

- buy at_level ok entry=101.0 mode=at_level
- buy next_trade ok entry=106.0
- buy chase reject ok (entry_moved_too_far_from_level)
- stops through level: buy_stop=89.0 sell_stop=111.0 (SL=12.0 T1=20.0 ext=10.0 width=30.0-90.0)

## Last 10 sessions (primary)

- sessions: **10**
- calls: **0**
- wins / losses: **0 / 0**
- hit rate: **n/a**
- avg win / avg loss: **n/a / n/a**
- net points (after cost): **0.00**
- no-call days: **10**
- reasons: `{'opening_width_out_of_range': 9, 'missing_opening_range': 1}`

### Day-by-day

| Date | Status | Side | Width | Mode | Signal | Entry | Stop | Target | Exit | Pts | Reason |
|---|---|---|---:|---|---|---:|---:|---:|---|---:|---|
| 2026-11-05 | no_call | — | 95.7 | — | — | — | — | — | — | — | opening_width_out_of_range |
| 2026-11-06 | no_call | — | 194.0 | — | — | — | — | — | — | — | opening_width_out_of_range |
| 2026-11-08 | no_call | — | — | — | — | — | — | — | — | — | missing_opening_range |
| 2026-11-09 | no_call | — | 209.2 | — | — | — | — | — | — | — | opening_width_out_of_range |
| 2026-11-11 | no_call | — | 153.2 | — | — | — | — | — | — | — | opening_width_out_of_range |
| 2026-11-12 | no_call | — | 212.9 | — | — | — | — | — | — | — | opening_width_out_of_range |
| 2026-11-13 | no_call | — | 132.3 | — | — | — | — | — | — | — | opening_width_out_of_range |
| 2026-11-16 | no_call | — | 115.4 | — | — | — | — | — | — | — | opening_width_out_of_range |
| 2026-11-17 | no_call | — | 90.8 | — | — | — | — | — | — | — | opening_width_out_of_range |
| 2026-11-18 | no_call | — | 163.2 | — | — | — | — | — | — | — | opening_width_out_of_range |

## Context windows (same frozen rule)

| Window | Calls | W/L | Hit | Avg win | Avg loss | Net | No-call |
|---|---:|---:|---:|---:|---:|---:|---:|
| last 10 | 0 | 0/0 | n/a | n/a | n/a | 0.00 | 10 |
| last 20 | 1 | 0/1 | 0.0% | n/a | -18.05 | -18.05 | 19 |
| last 40 | 9 | 6/3 | 66.7% | 19.00 | -20.77 | 51.70 | 31 |
| last 60 | 21 | 11/10 | 52.4% | 17.44 | -18.25 | 9.35 | 39 |

### Taken calls · last 40

| Date | Side | Width | Mode | Entry | Stop | Target | Status | Pts |
|---|---|---:|---|---:|---:|---:|---|---:|
| 2026-09-22 | sell | 63.3 | next_trade | 23422.25 | 23437.70 | 23402.25 | target | 20.0 |
| 2026-09-23 | buy | 62.8 | next_trade | 23417.40 | 23402.55 | 23437.40 | target | 20.0 |
| 2026-09-24 | sell | 76.5 | next_trade | 23204.15 | 23217.45 | 23184.15 | target | 20.0 |
| 2026-09-30 | buy | 76.9 | next_trade | 22739.10 | 22724.65 | 22759.10 | target | 20.0 |
| 2026-10-01 | buy | 82.0 | next_trade | 22599.50 | 22578.05 | 22619.50 | stop | -21.5 |
| 2026-10-05 | buy | 89.1 | next_trade | 22604.20 | 22583.40 | 22624.20 | stop | -20.8 |
| 2026-10-06 | buy | 68.4 | next_trade | 22633.15 | 22617.95 | 22653.15 | target | 20.0 |
| 2026-10-14 | sell | 88.5 | next_trade | 22657.85 | 22675.80 | 22637.85 | target | 20.0 |
| 2026-10-30 | sell | 74.9 | next_trade | 22914.80 | 22931.85 | 22894.80 | stop | -17.0 |

Module: `prod_live/logic/nifty_orb30_vwap_fut.py`
CSV: `prod_live/reports/1y/NIFTY_ORB30_VWAP_FUT_LAST10D.csv`
