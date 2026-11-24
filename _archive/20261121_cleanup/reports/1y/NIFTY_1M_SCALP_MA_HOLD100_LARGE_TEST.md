# MA HOLD100 — **LARGE blind test**

## Locked logic
1. **Entry:** textbook 1m candle pattern (bull→BUY / bear→SELL)
2. **Gate:** `DI_ok` + `gate_hard34` (EMA34 align+stack+slope) + `VWAP_with`
3. **Hold/exit:** stay while close on right side of **EMA34**; win if **T1=12** before MA flip
4. **Pace:** 1 call/day (first gated match)

Train `2021-01-01`→`2024-12-31` (**987** days) · Test `2025-01-01`→`2026-11-16` (**465** days) — LARGE OOS

| Book | Window | Calls | Hit% | Cover | all_win |
|---|---|---:|---:|---:|:---:|
| ORACLE | train | 987 | 100.0% | 100.0% | True |
| **HELD** | train | 987 | 65.96% | 100.0% | False |
| ORACLE | **TEST large** | 465 | 100.0% | 100.0% | True |
| **HELD** | **TEST large** | 465 | 74.19% | 100.0% | False |

## Test by year

| Year | HELD n@hit cover | ORACLE n@hit cover |
|---|---|---|
| 2025 | 249@73.09% 100.0% | 249@100.0% 100.0% |
| 2026 | 216@75.46% 100.0% | 216@100.0% 100.0% |

## Test by month

| Month | n | Hit% | W | L | Days |
|---|---:|---:|---:|---:|---:|
| 2025-01 | 23 | 60.87% | 14 | 9 | 23/23 |
| 2025-02 | 20 | 70.0% | 14 | 6 | 20/20 |
| 2025-03 | 19 | 68.42% | 13 | 6 | 19/19 |
| 2025-04 | 19 | 73.68% | 14 | 5 | 19/19 |
| 2025-05 | 21 | 71.43% | 15 | 6 | 21/21 |
| 2025-06 | 21 | 85.71% | 18 | 3 | 21/21 |
| 2025-07 | 23 | 73.91% | 17 | 6 | 23/23 |
| 2025-08 | 19 | 84.21% | 16 | 3 | 19/19 |
| 2025-09 | 22 | 54.55% | 12 | 10 | 22/22 |
| 2025-10 | 21 | 71.43% | 15 | 6 | 21/21 |
| 2025-11 | 19 | 73.68% | 14 | 5 | 19/19 |
| 2025-12 | 22 | 90.91% | 20 | 2 | 22/22 |
| 2026-01 | 20 | 75.0% | 15 | 5 | 20/20 |
| 2026-02 | 21 | 71.43% | 15 | 6 | 21/21 |
| 2026-03 | 19 | 84.21% | 16 | 3 | 19/19 |
| 2026-04 | 20 | 65.0% | 13 | 7 | 20/20 |
| 2026-05 | 19 | 78.95% | 15 | 4 | 19/19 |
| 2026-06 | 21 | 71.43% | 15 | 6 | 21/21 |
| 2026-07 | 23 | 69.57% | 16 | 7 | 23/23 |
| 2026-08 | 21 | 61.9% | 13 | 8 | 21/21 |
| 2026-09 | 21 | 80.95% | 17 | 4 | 21/21 |
| 2026-10 | 20 | 85.0% | 17 | 3 | 20/20 |
| 2026-11 | 11 | 100.0% | 11 | 0 | 11/11 |

## Last-3m slice inside test (`2026-08-17`→`2026-11-16`)

- HELD: **84.13%** hit · **100.0%** cover · n=63
- ORACLE: **100.0%** hit · **100.0%** cover · n=63

## Test losses sample (120 total, show 40)

| Day | HM | Side | Pattern | MFE | reason |
|---|---|---|---|---:|---|
| 2025-01-06 | 09:31 | BUY | bull_run2 | 5.8 | ma_sl |
| 2025-01-14 | 09:21 | BUY | marubozu_bull | 39.4 | ma_sl |
| 2025-01-15 | 09:25 | BUY | bull_kicker | 60.8 | ma_sl |
| 2025-01-17 | 09:23 | SELL | marubozu_bear | 87.9 | ma_sl |
| 2025-01-20 | 09:38 | SELL | bear_run3 | 7.6 | ma_sl |
| 2025-01-22 | 10:08 | BUY | bull_engulf | 43.3 | ma_sl |
| 2025-01-24 | 09:22 | BUY | bull_run2 | 1.9 | ma_sl |
| 2025-01-27 | 09:20 | SELL | belt_bear | 88.2 | ma_sl |
| 2025-01-28 | 09:48 | BUY | bull_run3 | 120.7 | ma_sl |
| 2025-02-07 | 09:38 | BUY | bull_engulf | 89.1 | ma_sl |
| 2025-02-13 | 09:20 | BUY | bull_run3 | 115.5 | ma_sl |
| 2025-02-18 | 09:36 | SELL | bear_engulf | 74.0 | ma_sl |
| 2025-02-19 | 09:24 | SELL | bear_run2 | 9.2 | ma_sl |
| 2025-02-25 | 09:21 | SELL | bear_engulf | 9.4 | ma_sl |
| 2025-02-27 | 09:42 | SELL | belt_bear | 28.0 | ma_sl |
| 2025-03-04 | 09:26 | SELL | three_outside_dn | 10.0 | ma_sl |
| 2025-03-11 | 09:20 | SELL | three_outside_dn | 9.7 | ma_sl |
| 2025-03-12 | 09:35 | SELL | hanging_man | 90.8 | ma_sl |
| 2025-03-13 | 09:25 | BUY | bull_run3 | 60.6 | ma_sl |
| 2025-03-24 | 09:23 | BUY | bull_run2 | 129.7 | ma_sl |
| 2025-03-27 | 09:44 | BUY | three_outside_up | 72.0 | ma_sl |
| 2025-04-01 | 09:25 | SELL | bear_run3 | 210.8 | ma_sl |
| 2025-04-07 | 09:20 | SELL | bear_run3 | 0.0 | ma_sl |
| 2025-04-25 | 09:27 | BUY | bull_run2 | 2.8 | ma_sl |
| 2025-04-29 | 09:24 | BUY | bull_run2 | 4.0 | ma_sl |
| 2025-04-30 | 09:25 | SELL | bear_run3 | 7.9 | ma_sl |
| 2025-05-16 | 09:40 | SELL | marubozu_bear | 30.1 | ma_sl |
| 2025-05-19 | 09:22 | BUY | marubozu_bull | 18.5 | ma_sl |
| 2025-05-20 | 09:23 | BUY | three_outside_up | 8.6 | ma_sl |
| 2025-05-28 | 09:37 | SELL | bear_engulf | 6.9 | ma_sl |
| 2025-05-29 | 09:21 | BUY | belt_bull | 0.3 | ma_sl |
| 2025-05-30 | 09:32 | BUY | marubozu_bull | 2.0 | ma_sl |
| 2025-06-10 | 09:24 | BUY | marubozu_bull | 25.3 | ma_sl |
| 2025-06-24 | 09:20 | BUY | three_outside_up | 39.4 | ma_sl |
| 2025-06-30 | 09:20 | SELL | belt_bear | 68.9 | ma_sl |
| 2025-07-02 | 09:21 | BUY | bull_run2 | 8.8 | ma_sl |
| 2025-07-03 | 09:20 | BUY | bull_run3 | 35.1 | ma_sl |
| 2025-07-11 | 09:34 | SELL | three_outside_dn | 137.6 | ma_sl |
| 2025-07-22 | 10:19 | BUY | bull_run2 | 5.0 | ma_sl |
| 2025-07-23 | 09:20 | BUY | bull_run3 | 3.9 | ma_sl |

Elapsed: 1408.1s
Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_ma_hold100`
