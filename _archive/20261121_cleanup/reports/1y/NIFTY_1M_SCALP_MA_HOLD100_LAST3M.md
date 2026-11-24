# MA HOLD100 — **last 3 months** blind test

Hold window **`2026-08-17` → `2026-11-16`** · Train before that (185 days) · Hold **63** days
Exit held: **trail34** · T1=**12** (EMA34 trail)

| Mode | Train n@hit cover | Hold n@hit cover | all_win hold |
|---|---|---|:---:|
| **ORACLE** | 185@100.0% 100.0% | 63@100.0% 100.0% | True |
| `m2_k1` | 184@100.0% 99.5% | 62@59.68% 98.4% | False |
| `m2_k1_hard34` | 184@100.0% 99.5% | 62@61.29% 98.4% | False |
| `m2_k1_clean21` | 184@100.0% 99.5% | 62@58.06% 98.4% | False |
| `m1_k1` | 185@100.0% 100.0% | 63@53.97% 100.0% | False |
| `champ_k1` | 87@100.0% 47.0% | 19@52.63% 30.2% | False |
| `m2_k2` | 92@100.0% 49.7% | 18@61.11% 28.6% | False |
| `m2_k1_after10` | 184@100.0% 99.5% | 62@59.68% 98.4% | False |

### ORACLE by month

| Month | n | Hit% | W | L | Cover days |
|---|---:|---:|---:|---:|---:|
| 2026-08 | 11 | 100.0% | 11 | 0 | 11/11 |
| 2026-09 | 21 | 100.0% | 21 | 0 | 21/21 |
| 2026-10 | 20 | 100.0% | 20 | 0 | 20/20 |
| 2026-11 | 11 | 100.0% | 11 | 0 | 11/11 |

### Best blind `m2_k1_hard34` by month

| Month | n | Hit% | W | L | Cover days |
|---|---:|---:|---:|---:|---:|
| 2026-08 | 11 | 45.45% | 5 | 6 | 11/11 |
| 2026-09 | 21 | 52.38% | 11 | 10 | 21/21 |
| 2026-10 | 20 | 65.0% | 13 | 7 | 20/20 |
| 2026-11 | 10 | 90.0% | 9 | 1 | 10/11 |

### Day-by-day — `m2_k1_hard34` (hold 61.29% / 98.4%)

| Day | Y/N | HM | Side | Pattern | MFE |
|---|---|---|---|---|---:|
| 2026-08-17 | N | 11:07 | SELL | falling_3_methods | 6.6 |
| 2026-08-18 | Y | 09:52 | SELL | hanging_man | 54.2 |
| 2026-08-19 | N | 10:46 | SELL | belt_bear | 24.8 |
| 2026-08-20 | Y | 09:20 | BUY | inv_hammer | 33.1 |
| 2026-08-21 | N | 09:53 | BUY | bull_engulf | 16.4 |
| 2026-08-24 | N | 11:57 | SELL | bear_run2 | 33.2 |
| 2026-08-25 | N | 10:36 | SELL | belt_bear | 6.0 |
| 2026-08-26 | Y | 09:23 | BUY | rising_3_methods | 33.3 |
| 2026-08-27 | Y | 10:57 | SELL | belt_bear | 24.7 |
| 2026-08-28 | N | 12:16 | SELL | bear_engulf | 2.2 |
| 2026-08-31 | Y | 09:23 | SELL | falling_3_methods | 78.3 |
| 2026-09-01 | N | 09:22 | SELL | bear_engulf | 32.1 |
| 2026-09-02 | Y | 14:29 | BUY | marubozu_bull | 139.0 |
| 2026-09-03 | Y | 12:00 | SELL | falling_3_methods | 62.8 |
| 2026-09-04 | N | 12:21 | SELL | hanging_man | 18.0 |
| 2026-09-07 | Y | 10:40 | SELL | belt_bear | 45.2 |
| 2026-09-08 | N | 10:27 | BUY | bull_engulf | 3.4 |
| 2026-09-09 | N | 12:15 | SELL | bear_engulf | 7.8 |
| 2026-09-10 | N | 10:02 | SELL | three_crows | 9.5 |
| 2026-09-11 | Y | 10:13 | BUY | bull_kicker | 65.9 |
| 2026-09-15 | Y | 14:45 | SELL | three_outside_dn | 91.6 |
| 2026-09-16 | Y | 13:33 | SELL | bear_engulf | 32.9 |
| 2026-09-17 | N | 13:42 | SELL | bear_engulf | 6.5 |
| 2026-09-18 | N | 09:57 | BUY | three_outside_up | 4.0 |
| 2026-09-21 | N | 14:42 | BUY | bull_engulf | 38.0 |
| 2026-09-22 | N | 09:47 | BUY | three_outside_up | 10.6 |
| 2026-09-23 | Y | 10:44 | BUY | bull_kicker | 54.1 |
| 2026-09-24 | Y | 09:59 | SELL | hanging_man | 35.2 |
| 2026-09-25 | N | 09:25 | SELL | bear_engulf | 42.7 |
| 2026-09-28 | Y | 10:17 | SELL | three_crows | 32.4 |
| 2026-09-29 | Y | 09:58 | SELL | bear_kicker | 32.4 |
| 2026-09-30 | Y | 09:41 | BUY | belt_bull | 75.0 |
| 2026-10-01 | Y | 13:40 | SELL | bear_kicker | 110.4 |
| 2026-10-05 | Y | 13:31 | BUY | bull_kicker | 158.7 |
| 2026-10-06 | Y | 09:33 | BUY | three_outside_up | 85.4 |
| 2026-10-07 | Y | 15:00 | SELL | bear_run2 | 171.5 |
| 2026-10-08 | Y | 10:20 | SELL | three_crows | 124.8 |
| 2026-10-09 | Y | 09:29 | BUY | marubozu_bull | 159.3 |
| 2026-10-12 | N | 12:14 | SELL | bear_engulf | 23.3 |
| 2026-10-13 | N | 10:59 | SELL | three_crows | 16.5 |
| 2026-10-14 | Y | 11:29 | SELL | belt_bear | 124.5 |
| 2026-10-15 | Y | 09:53 | BUY | three_soldiers | 155.4 |
| 2026-10-16 | N | 14:59 | SELL | falling_3_methods | 110.1 |
| 2026-10-19 | N | 09:37 | BUY | belt_bull | 1.4 |
| 2026-10-21 | Y | 13:28 | SELL | three_outside_dn | 77.9 |
| 2026-10-22 | Y | 13:33 | SELL | bear_run2 | 19.1 |
| 2026-10-23 | Y | 10:03 | SELL | three_crows | 157.7 |
| 2026-10-26 | Y | 10:27 | BUY | hammer | 20.5 |
| 2026-10-27 | N | 10:59 | BUY | bull_kicker | 59.2 |
| 2026-10-28 | N | 10:38 | BUY | bull_run3 | 128.2 |
| 2026-10-29 | Y | 10:39 | BUY | tweezer_bot | 21.3 |
| 2026-10-30 | N | 09:58 | BUY | bull_run2 | 126.8 |
| 2026-11-02 | Y | 13:08 | SELL | falling_3_methods | 44.4 |
| 2026-11-03 | Y | 09:34 | BUY | bull_kicker | 60.7 |
| 2026-11-04 | Y | 10:59 | SELL | three_crows | 75.8 |
| 2026-11-05 | Y | 09:37 | BUY | belt_bull | 83.1 |
| 2026-11-06 | Y | 10:54 | SELL | three_crows | 23.8 |
| 2026-11-08 | NO_CALL | | | | |
| 2026-11-09 | Y | 14:43 | BUY | bull_kicker | 419.0 |
| 2026-11-11 | Y | 10:33 | BUY | bull_kicker | 36.3 |
| 2026-11-12 | Y | 09:24 | BUY | hammer | 86.3 |
| 2026-11-13 | Y | 09:45 | BUY | three_outside_up | 53.9 |
| 2026-11-16 | N | 10:46 | SELL | belt_bear | 1.2 |

## Exact logic tested
1. Signal: textbook 1m candle
2. Hold: stay while close with EMA34; **T1=12** before flip = win
3. Blind picker: train-clean keys only (hold months unused)
