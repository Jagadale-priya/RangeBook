# NIFTY minute guide · last 1 month (accurate upgrade)

**Source:** `csv+kite` · cost 1.0
**Holdout:** 2026-10-19 → 2026-11-18 (22 sessions)
**Freeze:** 2026-07-27 → 2026-10-16 (58 sessions)

## What changed vs avoid_stop

Autopsy of avoid_stop holdout:
- **09–10** bled: 56 trades · 32% hit · 32% stops · **−88 net**
- From 10:00 onward: +302 net · stop share 11%
- **SELL** +230 vs **BUY** −16

`accurate` (new default): avoid_stop gates + **earliest 10:00** + **SELL only**

## Profile comparison

| Profile | Fr N | Fr hit | Fr net | Fr stop | Ho N | Ho hit | Ho net | Ho stop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 2418 | 38.3% | -920.92 | 29.6% | 1292 | 35.2% | -1119.37 | 41.7% |
| avoid_stop | 531 | 36.2% | -122.17 | 10.2% | 222 | 35.6% | 214.32 | 16.7% |
| accurate ** | 215 | 41.9% | 99.05 | 7.4% | 85 | 40.0% | 315.84 | 8.2% |
| skip10_both | 393 | 36.6% | -63.00 | 7.4% | 166 | 36.7% | 301.97 | 11.4% |
| skip10_enter35_both | 297 | 36.7% | -128.80 | 7.4% | 125 | 36.0% | 122.30 | 16.0% |
| skip10_sell | 215 | 41.9% | 99.05 | 7.4% | 85 | 40.0% | 315.84 | 8.2% |
| skip10_enter40_sell | 134 | 33.6% | -37.40 | 11.2% | 48 | 47.9% | 238.42 | 10.4% |
| skip10_sell_eff40 | 163 | 36.8% | -16.00 | 8.0% | 57 | 35.1% | 94.97 | 15.8% |

## accurate · holdout trades (sample)

| Date | Side | Signal | Entry | Exit | Net |
|---|---|---|---:|---|---:|
| 2026-10-19 | sell | 11:34 | 23021.95 | score_turned | -5.35 |
| 2026-10-19 | sell | 11:37 | 23009.05 | target | 19.40 |
| 2026-10-19 | sell | 13:22 | 22881.75 | score_turned | -0.50 |
| 2026-10-19 | sell | 13:27 | 22866.35 | stop | -13.00 |
| 2026-10-19 | sell | 14:25 | 22847.65 | score_turned | -4.30 |
| 2026-10-21 | sell | 10:00 | 23009.70 | stop | -13.00 |
| 2026-10-21 | sell | 10:03 | 22998.55 | target | 19.40 |
| 2026-10-21 | sell | 10:07 | 22963.45 | score_turned | -6.70 |
| 2026-10-21 | sell | 11:33 | 22870.00 | target | 19.40 |
| 2026-10-21 | sell | 11:38 | 22849.80 | target | 19.40 |
| 2026-10-21 | sell | 12:13 | 22758.10 | target | 19.40 |
| 2026-10-21 | sell | 12:18 | 22737.60 | score_turned | -0.05 |
| 2026-10-21 | sell | 12:21 | 22722.90 | score_turned | 1.35 |
| 2026-10-21 | sell | 14:21 | 22667.95 | score_turned | -2.20 |
| 2026-10-21 | sell | 14:25 | 22665.25 | score_turned | -2.65 |
| 2026-10-22 | sell | 11:44 | 22683.15 | target | 19.40 |
| 2026-10-22 | sell | 11:46 | 22640.50 | target | 19.40 |
| 2026-10-22 | sell | 11:49 | 22616.25 | stop | -13.00 |
| 2026-10-22 | sell | 13:19 | 22657.60 | score_turned | 1.35 |
| 2026-10-22 | sell | 13:24 | 22642.20 | target | 19.40 |

Full: `NIFTY_MINUTE_GUIDE_1M_CALLS.csv`
