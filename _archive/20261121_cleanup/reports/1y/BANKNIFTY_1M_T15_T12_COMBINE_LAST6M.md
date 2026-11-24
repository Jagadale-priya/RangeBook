# BANKNIFTY 1m — T15 UNION + T12 HELD combined · last 6 months

Data `2025-09-08`→`2026-11-02` · **TEST** `2026-05-03`→`2026-11-02` (126 days)
Train (key purify) `2025-09-08`→ before `2026-05-03` (159 days) · clean T15 keys=**20**

## Combine rule (1/day)

1. If BN-purified **T15 fingerprint** matches → **T1=15** EMA34 trail
2. Else if **HELD** (DI+hard34+VWAP) → **T1=12** EMA34 trail

## Test results (last 6m)

| Book | n | Hit% | Cover | Notes |
|---|---:|---:|---:|---|
| ORACLE T12 | 126 | 100.0% | 100.0% | ceiling |
| ORACLE T15 | 126 | 100.0% | 100.0% | ceiling |
| HELD T12 | 126 | 90.48% | 100.0% | blind |
| HELD T12 session 09:30–14:30 | 126 | 87.3% | 100.0% | |
| HELD T15 | 126 | 87.3% | 100.0% | |
| UNION T15 (BN train keys) | 76 | 76.32% | 60.3% | train 99@100.0% |
| **COMBINED T15→T12** | **126** | **83.33%** | **100.0%** | avg pts **0.66** · total **82.6** · T15:76(58W) T12:50(47W) |
| COMBINED + session cut | 126 | 82.54% | 100.0% | avg pts 0.5 · total 62.75 |

## Combined trade ledger (last 6m)

| Day | Book | Entry | Side | Pattern | T1 | Reason | Pts | Result |
|---|---|---|---|---|---:|---|---:|---|
| 2026-05-04 | `T15_UNION` | 09:58 | SELL | bear_engulf | 15 | `ma_sl` | -16.8 | LOSS |
| 2026-05-05 | `T15_UNION` | 09:25 | SELL | bear_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-05-06 | `T15_UNION` | 14:30 | BUY | bull_kicker | 15 | `t1` | +15.0 | WIN |
| 2026-05-07 | `T12_HELD` | 09:35 | BUY | marubozu_bull | 12 | `t1` | +12.0 | WIN |
| 2026-05-08 | `T15_UNION` | 10:06 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-05-11 | `T15_UNION` | 12:02 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-05-12 | `T15_UNION` | 09:31 | SELL | bear_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-05-13 | `T15_UNION` | 09:22 | SELL | bear_run2 | 15 | `ma_sl` | -86.7 | LOSS |
| 2026-05-14 | `T15_UNION` | 10:54 | SELL | bear_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-05-15 | `T15_UNION` | 11:24 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-05-18 | `T15_UNION` | 09:21 | SELL | bear_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-05-19 | `T15_UNION` | 11:13 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-05-20 | `T15_UNION` | 09:41 | SELL | bear_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-05-21 | `T15_UNION` | 09:52 | SELL | bear_engulf | 15 | `ma_sl` | -46.8 | LOSS |
| 2026-05-22 | `T15_UNION` | 11:37 | SELL | bear_engulf | 15 | `ma_sl` | -54.8 | LOSS |
| 2026-05-25 | `T15_UNION` | 10:03 | BUY | marubozu_bull | 15 | `t1` | +15.0 | WIN |
| 2026-05-26 | `T12_HELD` | 09:21 | BUY | bull_run3 | 12 | `t1` | +12.0 | WIN |
| 2026-05-27 | `T15_UNION` | 10:08 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-05-29 | `T15_UNION` | 11:00 | BUY | bull_kicker | 15 | `t1` | +15.0 | WIN |
| 2026-06-01 | `T12_HELD` | 09:36 | SELL | three_outside_dn | 12 | `t1` | +12.0 | WIN |
| 2026-06-02 | `T12_HELD` | 09:33 | SELL | bear_run3 | 12 | `ma_sl` | -169.0 | LOSS |
| 2026-06-03 | `T15_UNION` | 09:23 | SELL | bear_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-06-04 | `T15_UNION` | 10:03 | BUY | marubozu_bull | 15 | `t1` | +15.0 | WIN |
| 2026-06-05 | `T12_HELD` | 09:22 | BUY | belt_bull | 12 | `t1` | +12.0 | WIN |
| 2026-06-08 | `T12_HELD` | 09:43 | SELL | bear_run3 | 12 | `ma_sl` | -90.4 | LOSS |
| 2026-06-09 | `T15_UNION` | 11:09 | BUY | three_outside_up | 15 | `ma_sl` | -34.0 | LOSS |
| 2026-06-10 | `T12_HELD` | 09:39 | BUY | bull_run3 | 12 | `t1` | +12.0 | WIN |
| 2026-06-11 | `T15_UNION` | 10:27 | BUY | marubozu_bull | 15 | `ma_sl` | -66.8 | LOSS |
| 2026-06-12 | `T15_UNION` | 10:04 | BUY | hammer | 15 | `t1` | +15.0 | WIN |
| 2026-06-15 | `T15_UNION` | 12:59 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-06-16 | `T12_HELD` | 09:40 | SELL | bear_run3 | 12 | `t1` | +12.0 | WIN |
| 2026-06-17 | `T15_UNION` | 09:44 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-06-18 | `T15_UNION` | 14:49 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-06-19 | `T12_HELD` | 09:21 | SELL | marubozu_bear | 12 | `t1` | +12.0 | WIN |
| 2026-06-22 | `T15_UNION` | 09:38 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-06-23 | `T15_UNION` | 14:11 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-06-24 | `T12_HELD` | 09:26 | BUY | bull_run3 | 12 | `t1` | +12.0 | WIN |
| 2026-06-25 | `T15_UNION` | 09:44 | SELL | bear_engulf | 15 | `ma_sl` | -41.6 | LOSS |
| 2026-06-29 | `T12_HELD` | 09:24 | SELL | three_crows | 12 | `t1` | +12.0 | WIN |
| 2026-06-30 | `T12_HELD` | 09:29 | SELL | bear_engulf | 12 | `t1` | +12.0 | WIN |
| 2026-07-01 | `T15_UNION` | 10:36 | BUY | three_outside_up | 15 | `ma_sl` | -36.0 | LOSS |
| 2026-07-02 | `T15_UNION` | 13:29 | SELL | three_outside_dn | 15 | `t1` | +15.0 | WIN |
| 2026-07-03 | `T15_UNION` | 09:33 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-07-06 | `T15_UNION` | 12:03 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-07-07 | `T12_HELD` | 09:22 | BUY | marubozu_bull | 12 | `t1` | +12.0 | WIN |
| 2026-07-08 | `T15_UNION` | 09:56 | BUY | bull_run2 | 15 | `ma_sl` | -57.8 | LOSS |
| 2026-07-09 | `T12_HELD` | 09:28 | BUY | bull_engulf | 12 | `t1` | +12.0 | WIN |
| 2026-07-10 | `T15_UNION` | 12:51 | BUY | bull_kicker | 15 | `t1` | +15.0 | WIN |
| 2026-07-13 | `T15_UNION` | 09:47 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-07-14 | `T12_HELD` | 09:35 | SELL | marubozu_bear | 12 | `t1` | +12.0 | WIN |
| 2026-07-15 | `T12_HELD` | 09:20 | BUY | belt_bull | 12 | `t1` | +12.0 | WIN |
| 2026-07-16 | `T15_UNION` | 12:58 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-07-17 | `T15_UNION` | 09:22 | BUY | bull_kicker | 15 | `t1` | +15.0 | WIN |
| 2026-07-20 | `T15_UNION` | 11:04 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-07-21 | `T15_UNION` | 11:00 | SELL | belt_bear | 15 | `ma_sl` | -73.8 | LOSS |
| 2026-07-22 | `T12_HELD` | 09:20 | SELL | bear_run3 | 12 | `t1` | +12.0 | WIN |
| 2026-07-23 | `T15_UNION` | 13:14 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-07-24 | `T12_HELD` | 09:24 | SELL | bear_run2 | 12 | `t1` | +12.0 | WIN |
| 2026-07-27 | `T15_UNION` | 13:59 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-07-28 | `T12_HELD` | 09:22 | SELL | marubozu_bear | 12 | `t1` | +12.0 | WIN |
| 2026-07-29 | `T12_HELD` | 09:20 | BUY | belt_bull | 12 | `t1` | +12.0 | WIN |
| 2026-07-30 | `T15_UNION` | 09:22 | SELL | bear_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-07-31 | `T15_UNION` | 09:51 | SELL | bear_engulf | 15 | `ma_sl` | -42.2 | LOSS |
| 2026-08-03 | `T15_UNION` | 09:23 | BUY | hammer | 15 | `t1` | +15.0 | WIN |
| 2026-08-04 | `T15_UNION` | 12:20 | BUY | bull_run2 | 15 | `ma_sl` | -46.2 | LOSS |
| 2026-08-05 | `T12_HELD` | 09:21 | BUY | bull_run2 | 12 | `t1` | +12.0 | WIN |
| 2026-08-06 | `T12_HELD` | 09:20 | BUY | bull_run2 | 12 | `t1` | +12.0 | WIN |
| 2026-08-07 | `T15_UNION` | 09:30 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-08-10 | `T12_HELD` | 09:30 | SELL | bear_run3 | 12 | `t1` | +12.0 | WIN |
| 2026-08-11 | `T12_HELD` | 09:26 | SELL | bear_engulf | 12 | `t1` | +12.0 | WIN |
| 2026-08-12 | `T15_UNION` | 12:34 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-08-13 | `T15_UNION` | 09:26 | SELL | bear_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-08-14 | `T15_UNION` | 09:28 | SELL | bear_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-08-17 | `T15_UNION` | 12:55 | BUY | bull_kicker | 15 | `t1` | +15.0 | WIN |
| 2026-08-18 | `T12_HELD` | 09:24 | SELL | bear_engulf | 12 | `t1` | +12.0 | WIN |
| 2026-08-19 | `T15_UNION` | 09:23 | SELL | bear_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-08-20 | `T15_UNION` | 12:47 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-08-21 | `T12_HELD` | 09:36 | BUY | three_outside_up | 12 | `t1` | +12.0 | WIN |
| 2026-08-24 | `T15_UNION` | 11:05 | SELL | belt_bear | 15 | `t1` | +15.0 | WIN |
| 2026-08-25 | `T15_UNION` | 13:01 | SELL | three_outside_dn | 15 | `t1` | +15.0 | WIN |
| 2026-08-26 | `T12_HELD` | 09:20 | BUY | bull_run2 | 12 | `t1` | +12.0 | WIN |
| 2026-08-27 | `T12_HELD` | 09:23 | SELL | belt_bear | 12 | `t1` | +12.0 | WIN |
| 2026-08-28 | `T12_HELD` | 09:20 | SELL | marubozu_bear | 12 | `t1` | +12.0 | WIN |
| 2026-08-31 | `T15_UNION` | 14:08 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-09-01 | `T15_UNION` | 10:30 | BUY | bull_kicker | 15 | `ma_sl` | -74.8 | LOSS |
| 2026-09-02 | `T12_HELD` | 10:38 | BUY | bull_run2 | 12 | `t1` | +12.0 | WIN |
| 2026-09-03 | `T15_UNION` | 12:41 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-09-04 | `T12_HELD` | 09:20 | SELL | marubozu_bear | 12 | `t1` | +12.0 | WIN |
| 2026-09-07 | `T12_HELD` | 09:20 | SELL | bear_run2 | 12 | `t1` | +12.0 | WIN |
| 2026-09-08 | `T12_HELD` | 09:20 | SELL | bear_run3 | 12 | `t1` | +12.0 | WIN |
| 2026-09-09 | `T12_HELD` | 09:21 | SELL | bear_engulf | 12 | `t1` | +12.0 | WIN |
| 2026-09-10 | `T15_UNION` | 14:26 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-09-11 | `T12_HELD` | 09:41 | SELL | belt_bear | 12 | `t1` | +12.0 | WIN |
| 2026-09-15 | `T15_UNION` | 13:53 | SELL | bear_run3 | 15 | `t1` | +15.0 | WIN |
| 2026-09-16 | `T12_HELD` | 09:35 | SELL | marubozu_bear | 12 | `t1` | +12.0 | WIN |
| 2026-09-17 | `T15_UNION` | 12:33 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-09-18 | `T12_HELD` | 09:39 | BUY | bull_run3 | 12 | `ma_sl` | -61.7 | LOSS |
| 2026-09-21 | `T12_HELD` | 09:23 | BUY | bull_run2 | 12 | `t1` | +12.0 | WIN |
| 2026-09-22 | `T15_UNION` | 09:20 | SELL | bear_engulf | 15 | `ma_sl` | -25.8 | LOSS |
| 2026-09-23 | `T12_HELD` | 09:21 | BUY | bull_run2 | 12 | `t1` | +12.0 | WIN |
| 2026-09-24 | `T12_HELD` | 09:25 | SELL | bear_run2 | 12 | `t1` | +12.0 | WIN |
| 2026-09-25 | `T15_UNION` | 14:03 | BUY | marubozu_bull | 15 | `ma_sl` | -101.9 | LOSS |
| 2026-09-28 | `T12_HELD` | 09:20 | SELL | bear_run3 | 12 | `t1` | +12.0 | WIN |
| 2026-09-29 | `T15_UNION` | 09:25 | SELL | bear_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-09-30 | `T15_UNION` | 12:08 | BUY | bull_kicker | 15 | `t1` | +15.0 | WIN |
| 2026-10-01 | `T15_UNION` | 09:38 | SELL | bear_engulf | 15 | `ma_sl` | -39.8 | LOSS |
| 2026-10-05 | `T15_UNION` | 09:45 | BUY | three_outside_up | 15 | `t1` | +15.0 | WIN |
| 2026-10-06 | `T12_HELD` | 09:30 | BUY | bull_run3 | 12 | `t1` | +12.0 | WIN |
| 2026-10-07 | `T12_HELD` | 09:20 | SELL | marubozu_bear | 12 | `t1` | +12.0 | WIN |
| 2026-10-08 | `T12_HELD` | 09:25 | SELL | marubozu_bear | 12 | `t1` | +12.0 | WIN |
| 2026-10-09 | `T12_HELD` | 09:26 | BUY | marubozu_bull | 12 | `t1` | +12.0 | WIN |
| 2026-10-12 | `T15_UNION` | 09:26 | SELL | bear_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-10-13 | `T12_HELD` | 09:22 | BUY | bull_run2 | 12 | `t1` | +12.0 | WIN |
| 2026-10-14 | `T15_UNION` | 13:46 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-10-15 | `T12_HELD` | 09:31 | BUY | bull_engulf | 12 | `t1` | +12.0 | WIN |
| 2026-10-16 | `T12_HELD` | 09:29 | SELL | bear_run3 | 12 | `t1` | +12.0 | WIN |
| 2026-10-19 | `T12_HELD` | 09:20 | SELL | three_outside_dn | 12 | `t1` | +12.0 | WIN |
| 2026-10-21 | `T15_UNION` | 11:22 | SELL | belt_bear | 15 | `t1` | +15.0 | WIN |
| 2026-10-22 | `T15_UNION` | 10:11 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-10-23 | `T15_UNION` | 09:21 | SELL | bear_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-10-26 | `T15_UNION` | 10:27 | BUY | hammer | 15 | `ma_sl` | -12.5 | LOSS |
| 2026-10-27 | `T15_UNION` | 11:19 | SELL | bear_engulf | 15 | `t1` | +15.0 | WIN |
| 2026-10-28 | `T15_UNION` | 09:46 | BUY | bull_run2 | 15 | `t1` | +15.0 | WIN |
| 2026-10-29 | `T12_HELD` | 09:21 | SELL | bear_engulf | 12 | `t1` | +12.0 | WIN |
| 2026-10-30 | `T15_UNION` | 09:26 | SELL | bear_run2 | 15 | `ma_sl` | -172.0 | LOSS |
| 2026-11-02 | `T15_UNION` | 10:43 | BUY | bull_kicker | 15 | `t1` | +15.0 | WIN |

## Notes

- T15 keys are **re-purified on BN train** (NIFTY fingerprints not reused).
- Absolute targets 12/15 pts (same as NIFTY books); BN moves larger so these are easier path-wise.
- If train history is short, UNION cover on test will be thin — HELD leg carries most days.
