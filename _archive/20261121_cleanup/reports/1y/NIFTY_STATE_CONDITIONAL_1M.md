# NIFTY state-conditional · last 1 month (accurate profile)

**Source:** `csv+kite` 1m · cost 1.0
**Warm history:** last **752** sessions
**Test window:** 2026-10-19 → 2026-11-18 (22 sessions)

## Profiles

- `baseline`: analogs≥20 · hit≥0.52 · max 3/day
- `accurate`: analogs≥22 · hit≥0.54 · max 1/day (freeze/holdout pick `n22_h54_c1`)

## Baseline vs accurate

| Profile | Month N/hit/net | Warm N/hit/net |
|---|---|---|
| baseline | 6/66.7%/51.60 | 50/46.0%/101.60 |
| **accurate** | **4/75.0%/45.20** | 35/40.0%/5.00 |

## Accurate · last 1 month

- sessions in window: **22**
- calls: **4**
- wins / losses: **3 / 1**
- hit rate: **75.0%**
- net points (after cost): **45.20**
- calls/day (on days with ≥1 call): **1.00**
- exit reasons: `{'target': 3, 'stop': 1}`

## Warm-window context (accurate)

- total calls: **35** · hit **40.0%** · net **5.00**

### Calls by day (test month · accurate)

| Date | N | Sides | Net pts |
|---|---:|---|---:|
| 2026-10-19 | 0 | — | 0 |
| 2026-10-21 | 0 | — | 0 |
| 2026-10-22 | 0 | — | 0 |
| 2026-10-23 | 0 | — | 0 |
| 2026-10-26 | 0 | — | 0 |
| 2026-10-27 | 1 | sell | 19.4 |
| 2026-10-28 | 0 | — | 0 |
| 2026-10-29 | 0 | — | 0 |
| 2026-10-30 | 1 | buy | 19.4 |
| 2026-11-02 | 0 | — | 0 |
| 2026-11-03 | 0 | — | 0 |
| 2026-11-04 | 0 | — | 0 |
| 2026-11-05 | 0 | — | 0 |
| 2026-11-06 | 0 | — | 0 |
| 2026-11-08 | 0 | — | 0 |
| 2026-11-09 | 1 | buy | 19.4 |
| 2026-11-11 | 0 | — | 0 |
| 2026-11-12 | 0 | — | 0 |
| 2026-11-13 | 0 | — | 0 |
| 2026-11-16 | 0 | — | 0 |
| 2026-11-17 | 0 | — | 0 |
| 2026-11-18 | 1 | buy | -13.0 |

### Call detail

| Date | Side | State | Signal | Entry | Stop | Target | Exit | Pts | Analogs | Hit | Reason |
|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---|
| 2026-10-27 | sell | `high|failed_up|below|down|afternoon` | 13:15 | 22715.25 | 22727.25 | 22694.85 | 13:22 | 20.4 | 22 | 0.5909 | target |
| 2026-10-30 | buy | `high|failed_down|above|up|late_morning` | 11:01 | 22982.55 | 22970.55 | 23002.95 | 11:08 | 20.4 | 27 | 0.5556 | target |
| 2026-11-09 | buy | `high|failed_down|above|up|late_morning` | 11:28 | 24928.30 | 24916.30 | 24948.70 | 11:29 | 20.4 | 28 | 0.5714 | target |
| 2026-11-18 | buy | `high|failed_down|above|up|late_morning` | 11:20 | 25282.10 | 25270.10 | 25302.50 | 11:23 | -12.0 | 29 | 0.5862 | stop |

### Top states

- `high|failed_down|above|up|late_morning` × 3
- `high|failed_up|below|down|afternoon` × 1

CSV: `prod_live/reports/1y/NIFTY_STATE_CONDITIONAL_1M.csv`
