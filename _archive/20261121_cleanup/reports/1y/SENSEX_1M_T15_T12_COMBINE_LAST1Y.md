# SENSEX 1m — T15 UNION + T12 HELD · last 1 year

Data `2025-09-08`→`2026-11-02` · **TEST** `2025-11-03`→`2026-11-02` (**247** days)
Train (T15 key purify) days=**38** · TOP-20 keys=**20**

## Logic (same as BN stack)

1. TOP-20 Sensex-train-proven fingerprint → **T1=15** EMA34 trail
2. Else **HELD** DI+hard34+VWAP → **T1=12** EMA34 trail
3. 1 call/day first match

## Test results (last 1y)

| Book | n | Hit% | Cover | Notes |
|---|---:|---:|---:|---|
| ORACLE T12 | 247 | 100.0% | 100.0% | ceiling |
| ORACLE T15 | 247 | 100.0% | 100.0% | ceiling |
| **HELD T12** | 247 | **89.07%** | 100.0% | blind primary |
| HELD T12 session 09:30–14:30 | 247 | 85.83% | 100.0% | |
| HELD T15 | 247 | 87.45% | 100.0% | |
| UNION T15 (TOP-20) | 236 | 79.66% | 95.5% | train 37@100.0% |
| **COMBINED T15→T12** | **247** | **79.76%** | **100.0%** | avg **-2.07** · tot **-510.71** · T15:236(188W) T12:11(9W) |
| COMBINED + session | 247 | 79.76% | 100.0% | avg -1.9 · tot -469.47 |

## Combined ledger (last 1y)

| Day | Book | Entry | Side | Pattern | T1 | Reason | Pts | Result |
|---|---|---|---|---|---:|---|---:|---|
| 2025-11-03 | `T15_UNION` | 09:23 | SELL | falling_3_methods | 15 | `t1` | +15.0 | WIN |
| 2025-11-04 | `T15_UNION` | 11:10 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2025-11-06 | `T15_UNION` | 09:54 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2025-11-07 | `T15_UNION` | 09:53 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2025-11-10 | `T15_UNION` | 09:45 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2025-11-11 | `T15_UNION` | 10:02 | SELL | hanging_man | 15 | `ma_sl` | -14.3 | LOSS |
| 2025-11-12 | `T15_UNION` | 11:06 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2025-11-13 | `T15_UNION` | 09:56 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2025-11-14 | `T15_UNION` | 09:58 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2025-11-17 | `T12_HELD` | 09:20 | BUY | three_outside_up | 12 | `t1` | +12.0 | WIN |
| 2025-11-18 | `T15_UNION` | 09:35 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2025-11-19 | `T15_UNION` | 09:40 | BUY | bull_engulf | 15 | `ma_sl` | -38.6 | LOSS |
| 2025-11-20 | `T15_UNION` | 11:27 | BUY | bull_run2 | 15 | `ma_sl` | -37.4 | LOSS |
| 2025-11-21 | `T15_UNION` | 10:03 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2025-11-24 | `T15_UNION` | 10:12 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2025-11-25 | `T15_UNION` | 09:34 | BUY | bull_engulf | 15 | `ma_sl` | -62.4 | LOSS |
| 2025-11-26 | `T15_UNION` | 09:43 | BUY | bull_kicker | 15 | `t1` | +15.0 | WIN |
| 2025-11-27 | `T15_UNION` | 09:27 | BUY | bull_kicker | 15 | `t1` | +15.0 | WIN |
| 2025-11-28 | `T15_UNION` | 10:24 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2025-12-01 | `T15_UNION` | 10:50 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2025-12-02 | `T15_UNION` | 10:00 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2025-12-03 | `T15_UNION` | 11:00 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2025-12-04 | `T15_UNION` | 11:39 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2025-12-05 | `T15_UNION` | 10:40 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2025-12-08 | `T15_UNION` | 09:29 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2025-12-09 | `T15_UNION` | 10:18 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2025-12-10 | `T15_UNION` | 11:43 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2025-12-11 | `T15_UNION` | 11:04 | SELL | marubozu_bear | 15 | `ma_sl` | -124.0 | LOSS |
| 2025-12-12 | `T15_UNION` | 11:24 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2025-12-15 | `T15_UNION` | 09:42 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2025-12-16 | `T15_UNION` | 10:19 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2025-12-17 | `T15_UNION` | 09:59 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2025-12-18 | `T15_UNION` | 09:22 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2025-12-19 | `T15_UNION` | 09:22 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2025-12-22 | `T15_UNION` | 09:51 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2025-12-23 | `T15_UNION` | 09:54 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2025-12-24 | `T15_UNION` | 10:46 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2025-12-26 | `T15_UNION` | 12:01 | SELL | falling_3_methods | 15 | `t1` | +15.0 | WIN |
| 2025-12-29 | `T15_UNION` | 11:04 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2025-12-30 | `T15_UNION` | 09:41 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2025-12-31 | `T15_UNION` | 09:37 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-01-01 | `T15_UNION` | 09:48 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-01-02 | `T15_UNION` | 09:44 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-01-05 | `T15_UNION` | 11:23 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2026-01-06 | `T15_UNION` | 09:52 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-01-07 | `T15_UNION` | 10:48 | SELL | falling_3_methods | 15 | `ma_sl` | -23.0 | LOSS |
| 2026-01-08 | `T15_UNION` | 10:01 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-01-09 | `T15_UNION` | 09:28 | SELL | three_outside_dn | 15 | `t1` | +15.0 | WIN |
| 2026-01-12 | `T15_UNION` | 09:59 | SELL | bear_run3 | 15 | `ma_sl` | -83.7 | LOSS |
| 2026-01-13 | `T15_UNION` | 12:10 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2026-01-14 | `T15_UNION` | 10:02 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-01-16 | `T15_UNION` | 09:41 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-01-19 | `T15_UNION` | 09:59 | SELL | three_outside_dn | 15 | `t1` | +15.0 | WIN |
| 2026-01-20 | `T15_UNION` | 10:20 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-01-21 | `T15_UNION` | 09:45 | SELL | three_outside_dn | 15 | `t1` | +15.0 | WIN |
| 2026-01-22 | `T15_UNION` | 09:27 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-01-23 | `T15_UNION` | 09:45 | SELL | marubozu_bear | 15 | `ma_sl` | -112.1 | LOSS |
| 2026-01-27 | `T15_UNION` | 10:43 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2026-01-28 | `T15_UNION` | 11:25 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-01-29 | `T12_HELD` | 09:33 | SELL | bear_engulf | 12 | `t1` | +12.0 | WIN |
| 2026-01-30 | `T15_UNION` | 13:52 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-02-01 | `T15_UNION` | 09:34 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-02-02 | `T15_UNION` | 10:02 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-02-03 | `T15_UNION` | 12:35 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2026-02-04 | `T15_UNION` | 12:26 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-02-05 | `T15_UNION` | 10:06 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2026-02-06 | `T15_UNION` | 10:42 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-02-09 | `T15_UNION` | 09:24 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-02-10 | `T15_UNION` | 10:34 | BUY | belt_bull | 15 | `ma_sl` | -49.8 | LOSS |
| 2026-02-11 | `T15_UNION` | 09:49 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-02-12 | `T15_UNION` | 12:24 | BUY | bull_run2 | 15 | `ma_sl` | -20.1 | LOSS |
| 2026-02-13 | `T15_UNION` | 10:15 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-02-16 | `T15_UNION` | 10:13 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-02-17 | `T15_UNION` | 09:20 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2026-02-18 | `T15_UNION` | 09:44 | BUY | bull_run2 | 15 | `ma_sl` | -26.4 | LOSS |
| 2026-02-19 | `T15_UNION` | 11:50 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-02-20 | `T15_UNION` | 09:33 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-02-23 | `T15_UNION` | 09:42 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-02-24 | `T15_UNION` | 12:16 | SELL | three_outside_dn | 15 | `t1` | +15.0 | WIN |
| 2026-02-25 | `T15_UNION` | 11:19 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-02-26 | `T15_UNION` | 11:25 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-02-27 | `T15_UNION` | 09:50 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-03-02 | `T15_UNION` | 09:21 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2026-03-04 | `T15_UNION` | 10:12 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-03-05 | `T15_UNION` | 10:44 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-03-06 | `T15_UNION` | 10:16 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-03-09 | `T15_UNION` | 10:06 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-03-10 | `T15_UNION` | 11:56 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2026-03-11 | `T15_UNION` | 09:59 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2026-03-12 | `T15_UNION` | 10:13 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-03-13 | `T15_UNION` | 09:43 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-03-16 | `T15_UNION` | 11:07 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-03-17 | `T15_UNION` | 09:35 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-03-18 | `T15_UNION` | 11:00 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-03-19 | `T15_UNION` | 09:58 | SELL | hanging_man | 15 | `t1` | +15.0 | WIN |
| 2026-03-20 | `T15_UNION` | 11:19 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-03-23 | `T15_UNION` | 10:13 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-03-24 | `T15_UNION` | 09:36 | BUY | bull_run2 | 15 | `ma_sl` | -290.7 | LOSS |
| 2026-03-25 | `T15_UNION` | 09:51 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-03-27 | `T15_UNION` | 09:22 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2026-03-30 | `T15_UNION` | 09:44 | SELL | bear_run3 | 15 | `ma_sl` | -56.9 | LOSS |
| 2026-04-01 | `T15_UNION` | 09:45 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-04-02 | `T15_UNION` | 12:11 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-04-06 | `T15_UNION` | 09:24 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-04-07 | `T15_UNION` | 10:56 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2026-04-08 | `T15_UNION` | 09:30 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-04-09 | `T15_UNION` | 11:28 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-04-10 | `T15_UNION` | 09:37 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-04-13 | `T15_UNION` | 11:08 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-04-15 | `T15_UNION` | 09:52 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-04-16 | `T15_UNION` | 10:17 | SELL | bear_engulf | 15 | `ma_sl` | -112.4 | LOSS |
| 2026-04-17 | `T15_UNION` | 12:30 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2026-04-20 | `T15_UNION` | 09:47 | SELL | marubozu_bear | 15 | `ma_sl` | -164.1 | LOSS |
| 2026-04-21 | `T15_UNION` | 12:12 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-04-22 | `T15_UNION` | 09:35 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2026-04-23 | `T15_UNION` | 10:22 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-04-24 | `T12_HELD` | 09:20 | SELL | marubozu_bear | 12 | `t1` | +12.0 | WIN |
| 2026-04-27 | `T15_UNION` | 12:33 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-04-28 | `T15_UNION` | 09:23 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-04-29 | `T15_UNION` | 09:36 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-04-30 | `T15_UNION` | 10:25 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-05-04 | `T15_UNION` | 09:56 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-05-05 | `T15_UNION` | 10:07 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-05-06 | `T15_UNION` | 11:52 | SELL | bear_run3 | 15 | `ma_sl` | -19.1 | LOSS |
| 2026-05-07 | `T15_UNION` | 09:51 | BUY | bull_run2 | 15 | `ma_sl` | -20.4 | LOSS |
| 2026-05-08 | `T15_UNION` | 09:50 | SELL | shooting_star | 15 | `ma_sl` | -121.1 | LOSS |
| 2026-05-11 | `T15_UNION` | 14:57 | SELL | three_outside_dn | 15 | `t1` | +15.0 | WIN |
| 2026-05-12 | `T15_UNION` | 11:54 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-05-13 | `T15_UNION` | 13:55 | SELL | marubozu_bear | 15 | `ma_sl` | -75.6 | LOSS |
| 2026-05-14 | `T15_UNION` | 10:05 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-05-15 | `T15_UNION` | 11:05 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2026-05-18 | `T15_UNION` | 09:27 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2026-05-19 | `T15_UNION` | 11:14 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2026-05-20 | `T15_UNION` | 12:34 | SELL | bear_engulf | 15 | `ma_sl` | -7.2 | LOSS |
| 2026-05-21 | `T15_UNION` | 12:01 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-05-22 | `T15_UNION` | 12:54 | BUY | bull_engulf | 15 | `ma_sl` | -62.1 | LOSS |
| 2026-05-25 | `T15_UNION` | 10:13 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-05-26 | `T15_UNION` | 09:31 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-05-27 | `T15_UNION` | 11:09 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-05-29 | `T15_UNION` | 11:53 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-06-01 | `T12_HELD` | 09:44 | SELL | bear_run3 | 12 | `t1` | +12.0 | WIN |
| 2026-06-02 | `T15_UNION` | 10:12 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-06-03 | `T12_HELD` | 09:20 | SELL | bear_run3 | 12 | `t1` | +12.0 | WIN |
| 2026-06-04 | `T15_UNION` | 13:02 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-06-05 | `T15_UNION` | 11:08 | BUY | bull_engulf | 15 | `ma_sl` | -206.3 | LOSS |
| 2026-06-08 | `T15_UNION` | 09:59 | BUY | three_outside_up | 15 | `ma_sl` | -97.7 | LOSS |
| 2026-06-09 | `T15_UNION` | 10:10 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-06-10 | `T15_UNION` | 12:43 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2026-06-11 | `T15_UNION` | 10:03 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-06-12 | `T15_UNION` | 09:23 | BUY | belt_bull | 15 | `ma_sl` | -199.8 | LOSS |
| 2026-06-15 | `T15_UNION` | 09:40 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-06-16 | `T15_UNION` | 09:53 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-06-17 | `T12_HELD` | 09:26 | BUY | three_outside_up | 12 | `t1` | +12.0 | WIN |
| 2026-06-18 | `T15_UNION` | 10:39 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2026-06-19 | `T15_UNION` | 10:25 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-06-22 | `T15_UNION` | 09:57 | BUY | bull_kicker | 15 | `t1` | +15.0 | WIN |
| 2026-06-23 | `T15_UNION` | 11:15 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-06-24 | `T15_UNION` | 09:55 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-06-25 | `T15_UNION` | 09:34 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-06-29 | `T15_UNION` | 10:00 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-06-30 | `T15_UNION` | 09:24 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-07-01 | `T15_UNION` | 09:56 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-07-02 | `T15_UNION` | 10:16 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-07-03 | `T15_UNION` | 12:05 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-07-06 | `T12_HELD` | 09:30 | BUY | marubozu_bull | 12 | `t1` | +12.0 | WIN |
| 2026-07-07 | `T15_UNION` | 09:41 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-07-08 | `T15_UNION` | 10:05 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-07-09 | `T15_UNION` | 10:32 | SELL | bear_engulf | 15 | `ma_sl` | -58.4 | LOSS |
| 2026-07-10 | `T15_UNION` | 14:27 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-07-13 | `T15_UNION` | 11:07 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-07-14 | `T15_UNION` | 09:54 | SELL | bear_run3 | 15 | `ma_sl` | -87.2 | LOSS |
| 2026-07-15 | `T15_UNION` | 12:45 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2026-07-16 | `T15_UNION` | 11:55 | SELL | bear_engulf | 15 | `ma_sl` | -21.7 | LOSS |
| 2026-07-17 | `T15_UNION` | 11:52 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-07-20 | `T15_UNION` | 14:56 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-07-21 | `T15_UNION` | 09:32 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-07-22 | `T15_UNION` | 09:44 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2026-07-23 | `T15_UNION` | 09:56 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-07-24 | `T15_UNION` | 11:05 | BUY | three_outside_up | 15 | `ma_sl` | -9.8 | LOSS |
| 2026-07-27 | `T15_UNION` | 09:34 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-07-28 | `T15_UNION` | 09:43 | BUY | bull_kicker | 15 | `ma_sl` | -47.1 | LOSS |
| 2026-07-29 | `T15_UNION` | 09:31 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-07-30 | `T15_UNION` | 09:45 | SELL | hanging_man | 15 | `ma_sl` | -88.6 | LOSS |
| 2026-07-31 | `T15_UNION` | 09:39 | BUY | bull_engulf | 15 | `ma_sl` | -9.0 | LOSS |
| 2026-08-03 | `T15_UNION` | 09:26 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-08-04 | `T15_UNION` | 09:56 | BUY | bull_run2 | 15 | `ma_sl` | -46.9 | LOSS |
| 2026-08-05 | `T15_UNION` | 09:58 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-08-06 | `T15_UNION` | 09:39 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-08-07 | `T15_UNION` | 12:49 | BUY | bull_engulf | 15 | `ma_sl` | -29.7 | LOSS |
| 2026-08-10 | `T15_UNION` | 11:07 | BUY | bull_run2 | 15 | `ma_sl` | -14.1 | LOSS |
| 2026-08-11 | `T15_UNION` | 09:34 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2026-08-12 | `T15_UNION` | 09:32 | SELL | bear_run3 | 15 | `ma_sl` | -21.9 | LOSS |
| 2026-08-13 | `T12_HELD` | 09:54 | BUY | belt_bull | 12 | `ma_sl` | -32.7 | LOSS |
| 2026-08-14 | `T15_UNION` | 09:57 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-08-17 | `T15_UNION` | 10:08 | SELL | three_outside_dn | 15 | `t1` | +15.0 | WIN |
| 2026-08-18 | `T15_UNION` | 09:32 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-08-19 | `T15_UNION` | 10:09 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-08-20 | `T15_UNION` | 09:55 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-08-21 | `T15_UNION` | 09:29 | BUY | three_outside_up | 15 | `ma_sl` | -18.8 | LOSS |
| 2026-08-24 | `T15_UNION` | 13:46 | BUY | three_outside_up | 15 | `ma_sl` | -5.3 | LOSS |
| 2026-08-25 | `T15_UNION` | 09:45 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2026-08-26 | `T15_UNION` | 11:03 | SELL | dark_cloud | 15 | `t1` | +15.0 | WIN |
| 2026-08-27 | `T15_UNION` | 09:38 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-08-28 | `T12_HELD` | 09:20 | SELL | bear_run3 | 12 | `ma_sl` | -85.1 | LOSS |
| 2026-08-31 | `T15_UNION` | 10:17 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-09-01 | `T15_UNION` | 11:07 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-09-02 | `T15_UNION` | 09:30 | SELL | shooting_star | 15 | `ma_sl` | -109.4 | LOSS |
| 2026-09-03 | `T15_UNION` | 09:34 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-09-04 | `T15_UNION` | 09:50 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-09-07 | `T15_UNION` | 14:01 | BUY | belt_bull | 15 | `ma_sl` | -46.8 | LOSS |
| 2026-09-08 | `T15_UNION` | 09:55 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-09-09 | `T15_UNION` | 14:42 | SELL | falling_3_methods | 15 | `t1` | +15.0 | WIN |
| 2026-09-10 | `T15_UNION` | 09:31 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-09-11 | `T15_UNION` | 09:21 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2026-09-15 | `T15_UNION` | 10:03 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-09-16 | `T12_HELD` | 09:37 | SELL | bear_engulf | 12 | `t1` | +12.0 | WIN |
| 2026-09-17 | `T15_UNION` | 11:14 | SELL | shooting_star | 15 | `ma_sl` | -82.1 | LOSS |
| 2026-09-18 | `T15_UNION` | 09:52 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-09-21 | `T15_UNION` | 10:21 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-09-22 | `T15_UNION` | 10:26 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-09-23 | `T15_UNION` | 09:59 | BUY | bull_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-09-24 | `T15_UNION` | 09:40 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-09-25 | `T15_UNION` | 09:25 | SELL | bear_run3 | 15 | `ma_sl` | -40.9 | LOSS |
| 2026-09-28 | `T15_UNION` | 10:16 | SELL | three_outside_dn | 15 | `t1` | +15.0 | WIN |
| 2026-09-29 | `T15_UNION` | 09:44 | SELL | three_outside_dn | 15 | `t1` | +15.0 | WIN |
| 2026-09-30 | `T15_UNION` | 10:14 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-10-01 | `T15_UNION` | 11:36 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-10-05 | `T15_UNION` | 10:20 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-10-06 | `T15_UNION` | 11:02 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-10-07 | `T15_UNION` | 09:38 | SELL | three_outside_dn | 15 | `t1` | +15.0 | WIN |
| 2026-10-08 | `T15_UNION` | 11:43 | SELL | shooting_star | 15 | `t1` | +15.0 | WIN |
| 2026-10-09 | `T12_HELD` | 09:27 | BUY | belt_bull | 12 | `t1` | +12.0 | WIN |
| 2026-10-12 | `T15_UNION` | 10:11 | SELL | three_outside_dn | 15 | `t1` | +15.0 | WIN |
| 2026-10-13 | `T15_UNION` | 09:47 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-10-14 | `T15_UNION` | 09:41 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-10-15 | `T15_UNION` | 11:04 | BUY | three_outside_up | 15 | `ma_sl` | -65.9 | LOSS |
| 2026-10-16 | `T15_UNION` | 10:04 | BUY | belt_bull | 15 | `t1` | +15.0 | WIN |
| 2026-10-19 | `T15_UNION` | 11:02 | SELL | bear_run3 | 15 | `ma_sl` | -36.1 | LOSS |
| 2026-10-21 | `T15_UNION` | 10:12 | SELL | marubozu_bear | 15 | `t1` | +15.0 | WIN |
| 2026-10-22 | `T15_UNION` | 09:50 | BUY | bull_engulf | 15 | `ma_sl` | -138.5 | LOSS |
| 2026-10-23 | `T15_UNION` | 10:51 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-10-26 | `T15_UNION` | 09:20 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-10-27 | `T15_UNION` | 10:24 | SELL | bear_run3 | 15 | `ma_sl` | -139.5 | LOSS |
| 2026-10-28 | `T15_UNION` | 09:29 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-10-29 | `T15_UNION` | 11:21 | BUY | bull_run2 | 15 | `ma_sl` | -41.7 | LOSS |
| 2026-10-30 | `T15_UNION` | 10:43 | BUY | three_outside_up | 15 | `ma_sl` | -83.4 | LOSS |
| 2026-11-02 | `T15_UNION` | 12:25 | BUY | bull_run2 | 15 | `ma_sl` | -52.7 | LOSS |

## Verdict

- Prefer the book with highest test hit among HELD T12 vs COMBINED.
- Same pattern as BN if COMBINED < HELD T12 → do not upgrade with T15 UNION.
