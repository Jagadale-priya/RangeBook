# clean34 — **HOLD unknown** diagnose

Hold window **`2026-08-01` → `2026-11-16`** · days **73**
Gate: `clean34` = hard EMA34 (align+stack-with+slope) + `close_ok` + not `fail_risk`
Book: **46** micros locked 100% on train · evaluated blind on hold

| Mode | n | Hit% | Days | Cover | Avg T1 | Avg SL | all_win |
|---|---:|---:|---:|---:|---:|---:|:---:|
| Train 1/day (lock) | 129 | 100.0% | 129 | 73.7% | 27.75 | 9.74 | True |
| Hold full (all micro matches) | 1686 | 28.94% | 72 | 98.6% | 28.54 | 9.84 | False |
| **Hold 1/day (first call)** | **72** | **41.67%** | **72** | **98.6%** | **28.61** | **10.82** | **False** |
| Hold gate-only 1/day (no micro) | 73 | 47.95% | 73 | 100.0% | 28.7 | 7.48 | False |

Wins **30** · Losses **42** · SL-first with MFE≥T1: **18**

## By month (1/day)

| Month | n | Hit% | W | L | AvgT1 | AvgSL |
|---|---:|---:|---:|---:|---:|---:|
| 2026-08 | 21 | 42.86% | 9 | 12 | 28.6 | 10.1 |
| 2026-09 | 21 | 28.57% | 6 | 15 | 29.0 | 10.8 |
| 2026-10 | 20 | 50.0% | 10 | 10 | 28.5 | 11.4 |
| 2026-11 | 10 | 50.0% | 5 | 5 | 28.0 | 11.2 |

## Mix on hold 1/day

- Patterns: bull_run3×16, bear_run3×14, bear_engulf×8, bull_run2×7, bear_run2×6, belt_bear×6, marubozu_bear×5, marubozu_bull×2, evening_star×2, bull_engulf×2
- Side: {'BUY': 30, 'SELL': 42}
- SL style: cap12×50, cap10×17, prev×5
- T1 used: 30.0×62, 20.0×10
- Loss patterns: bull_run3×7, belt_bear×6, bear_engulf×6, bear_run3×6, bull_run2×4, marubozu_bear×3, bear_run2×3, marubozu_bull×2
- Win patterns: bull_run3×9, bear_run3×8, bull_run2×3, bear_run2×3, marubozu_bear×2, bear_engulf×2, evening_star×1, bull_kicker×1

## Day-by-day (1/day first call)

| Day | Result | HM | Side | Pattern | T1 | SL style | SL | MFE | MAE | stack34 | dist34 |
|---|---|---|---|---|---:|---|---:|---:|---:|---|---|
| 2026-08-03 | Y | 09:24 | BUY | bull_run2 | 30 | cap12 | 11.5 | 75.5 | 3.7 | bull | ext |
| 2026-08-04 | Y | 09:41 | BUY | bull_run3 | 30 | cap12 | 8.2 | 34.9 | 58.8 | bull | ext |
| 2026-08-05 | N | 09:32 | BUY | marubozu_bull | 30 | cap12 | 12.0 | 41.1 | 59.2 | bull | ext |
| 2026-08-06 | N | 09:20 | BUY | bull_run2 | 30 | cap10 | 10.0 | 32.1 | 31.7 | bull | ext |
| 2026-08-07 | N | 09:30 | SELL | marubozu_bear | 20 | cap10 | 10.0 | 42.4 | 35.8 | bear | ext |
| 2026-08-10 | N | 09:45 | SELL | bear_run2 | 20 | cap10 | 5.0 | 0.0 | 95.7 | bear | ext |
| 2026-08-11 | N | 09:23 | SELL | bear_run2 | 30 | cap12 | 12.0 | 52.9 | 15.0 | bear | ext |
| 2026-08-12 | Y | 09:45 | SELL | marubozu_bear | 30 | cap12 | 12.0 | 140.0 | 1.8 | bear | ext |
| 2026-08-13 | N | 10:29 | SELL | belt_bear | 30 | cap12 | 10.5 | 7.8 | 95.8 | bear | ext |
| 2026-08-14 | N | 09:20 | SELL | bear_engulf | 30 | prev | 6.3 | 22.2 | 40.2 | bear | ext |
| 2026-08-17 | N | 09:32 | SELL | bear_run3 | 30 | cap12 | 12.0 | 59.4 | 26.1 | bear | ext |
| 2026-08-18 | Y | 09:29 | SELL | bear_run3 | 30 | cap12 | 12.0 | 62.8 | 4.1 | bear | ext |
| 2026-08-19 | Y | 09:23 | SELL | bear_run2 | 30 | cap12 | 12.0 | 83.2 | 1.8 | bear | ext |
| 2026-08-20 | N | 09:45 | BUY | bull_run3 | 30 | cap12 | 6.0 | 12.7 | 20.0 | bull | ext |
| 2026-08-21 | N | 09:34 | SELL | belt_bear | 30 | prev | 12.0 | 1.5 | 58.9 | bear | ext |
| 2026-08-24 | Y | 11:02 | SELL | evening_star | 30 | cap12 | 7.9 | 76.1 | 1.7 | bear | ext |
| 2026-08-25 | Y | 09:51 | SELL | bear_run3 | 30 | cap12 | 9.2 | 34.6 | 16.8 | bear | ext |
| 2026-08-26 | Y | 09:22 | BUY | bull_run3 | 30 | cap10 | 10.0 | 33.5 | 50.8 | bull | ext |
| 2026-08-27 | Y | 09:20 | SELL | bear_run2 | 30 | cap12 | 12.0 | 102.6 | 7.8 | bear | ext |
| 2026-08-28 | N | 09:22 | SELL | bear_engulf | 20 | cap10 | 10.0 | 0.0 | 76.0 | bear | ext |
| 2026-08-31 | N | 09:26 | SELL | belt_bear | 30 | cap12 | 12.0 | 55.6 | 18.2 | bear | ext |
| 2026-09-01 | N | 09:43 | SELL | belt_bear | 30 | cap12 | 12.0 | 23.2 | 110.4 | bear | ext |
| 2026-09-02 | N | 09:22 | SELL | three_outside_dn | 30 | cap12 | 12.0 | 16.5 | 92.8 | bear | ext |
| 2026-09-03 | Y | 09:29 | BUY | bull_run3 | 30 | cap12 | 12.0 | 40.6 | 61.9 | bull | ext |
| 2026-09-04 | N | 09:35 | SELL | evening_star | 20 | cap10 | 10.0 | 5.6 | 89.1 | bear | mid |
| 2026-09-07 | N | 09:27 | SELL | belt_bear | 30 | prev | 7.8 | 67.6 | 15.5 | bear | ext |
| 2026-09-08 | Y | 09:20 | SELL | bear_run2 | 30 | cap12 | 6.0 | 33.3 | 26.8 | bear | ext |
| 2026-09-09 | Y | 09:47 | SELL | bear_run3 | 30 | cap12 | 11.9 | 44.2 | 38.5 | bear | ext |
| 2026-09-10 | N | 09:22 | SELL | bear_engulf | 30 | cap12 | 12.0 | 18.7 | 29.9 | bear | ext |
| 2026-09-11 | N | 09:32 | SELL | marubozu_bear | 30 | cap12 | 12.0 | 2.5 | 112.5 | bear | ext |
| 2026-09-15 | N | 10:03 | SELL | bear_engulf | 30 | cap12 | 12.0 | 66.2 | 21.5 | bear | ext |
| 2026-09-16 | Y | 09:39 | SELL | bear_run3 | 30 | cap12 | 12.0 | 35.2 | 127.5 | bear | ext |
| 2026-09-17 | N | 09:28 | BUY | bull_run3 | 20 | cap10 | 10.0 | 68.1 | 47.0 | bull | mid |
| 2026-09-18 | N | 09:23 | BUY | bull_run3 | 30 | cap10 | 10.0 | 11.0 | 40.9 | bull | ext |
| 2026-09-21 | N | 09:48 | BUY | bull_engulf | 30 | prev | 10.0 | 7.8 | 46.0 | bull | ext |
| 2026-09-22 | N | 09:42 | BUY | bull_run2 | 30 | cap12 | 9.1 | 14.0 | 93.6 | bull | ext |
| 2026-09-23 | N | 11:32 | BUY | bull_kicker | 30 | cap10 | 8.0 | 25.9 | 16.8 | bull | ext |
| 2026-09-24 | Y | 09:39 | SELL | bear_run3 | 30 | cap12 | 12.0 | 50.8 | 2.8 | bear | ext |
| 2026-09-25 | N | 09:49 | SELL | bear_run2 | 30 | prev | 11.0 | 15.6 | 56.8 | bear | ext |
| 2026-09-28 | N | 09:22 | SELL | bear_run3 | 30 | cap12 | 12.0 | 106.5 | 23.8 | bear | ext |
| 2026-09-29 | Y | 09:26 | SELL | bear_run3 | 30 | cap12 | 12.0 | 82.8 | 49.0 | bear | ext |
| 2026-09-30 | N | 09:20 | BUY | bull_run3 | 30 | cap12 | 12.0 | 51.5 | 54.3 | bull | ext |
| 2026-10-01 | Y | 09:20 | SELL | bear_run3 | 30 | cap12 | 12.0 | 38.2 | 64.4 | bear | ext |
| 2026-10-05 | Y | 09:24 | BUY | bull_run3 | 30 | cap12 | 12.0 | 77.5 | 92.6 | bull | ext |
| 2026-10-06 | Y | 09:23 | BUY | bull_run3 | 30 | cap12 | 12.0 | 103.9 | 2.1 | bull | ext |
| 2026-10-07 | Y | 09:32 | SELL | marubozu_bear | 20 | cap10 | 7.7 | 48.3 | 84.2 | bear | ext |
| 2026-10-08 | Y | 09:24 | SELL | bear_engulf | 30 | cap12 | 12.0 | 124.3 | 8.8 | bear | ext |
| 2026-10-09 | N | 09:29 | BUY | marubozu_bull | 30 | cap12 | 12.0 | 159.3 | 12.6 | bull | ext |
| 2026-10-12 | Y | 09:50 | SELL | bear_engulf | 20 | cap10 | 10.0 | 149.9 | 23.2 | bear | ext |
| 2026-10-13 | Y | 09:22 | BUY | bull_run2 | 30 | cap12 | 12.0 | 131.0 | 8.4 | bull | ext |
| 2026-10-14 | N | 09:44 | BUY | bull_run3 | 30 | cap12 | 12.0 | 25.8 | 76.8 | bull | ext |
| 2026-10-15 | Y | 09:29 | BUY | bull_run2 | 30 | cap12 | 12.0 | 209.5 | 11.8 | bull | ext |
| 2026-10-16 | N | 09:35 | SELL | bear_run3 | 30 | cap12 | 12.0 | 13.4 | 222.6 | bear | ext |
| 2026-10-19 | N | 09:28 | SELL | marubozu_bear | 30 | cap12 | 12.0 | 7.0 | 191.0 | bear | ext |
| 2026-10-21 | N | 09:31 | BUY | bull_run2 | 30 | cap10 | 10.0 | 23.2 | 228.2 | bull | ext |
| 2026-10-22 | N | 09:24 | SELL | bear_engulf | 30 | cap12 | 12.0 | 5.6 | 224.6 | bear | ext |
| 2026-10-23 | Y | 10:01 | SELL | bear_run3 | 30 | cap12 | 12.0 | 186.0 | 2.2 | bear | ext |
| 2026-10-26 | N | 09:21 | SELL | belt_bear | 30 | cap12 | 12.0 | 24.8 | 294.0 | bear | ext |
| 2026-10-27 | N | 09:29 | BUY | bull_run3 | 30 | cap12 | 12.0 | 58.1 | 61.9 | bull | ext |
| 2026-10-28 | N | 09:29 | SELL | bear_run3 | 30 | cap12 | 12.0 | 54.2 | 109.5 | bear | ext |
| 2026-10-29 | Y | 09:51 | BUY | bull_run3 | 20 | cap10 | 10.0 | 126.9 | 12.8 | bull | ext |
| 2026-10-30 | N | 09:30 | BUY | bull_engulf | 30 | cap12 | 11.2 | 68.4 | 69.6 | bull | ext |
| 2026-11-02 | N | 09:28 | BUY | bull_run3 | 30 | cap12 | 12.0 | 88.4 | 17.1 | bull | ext |
| 2026-11-03 | Y | 09:20 | BUY | bull_kicker | 30 | cap10 | 10.0 | 87.3 | 9.5 | bull | ext |
| 2026-11-04 | Y | 09:20 | BUY | bull_run3 | 30 | cap12 | 12.0 | 59.5 | 109.4 | bull | ext |
| 2026-11-05 | Y | 09:36 | BUY | bull_run3 | 30 | cap12 | 12.0 | 99.8 | 0.0 | bull | ext |
| 2026-11-06 | N | 09:25 | SELL | bear_run3 | 20 | cap10 | 10.0 | 11.0 | 226.6 | bear | ext |
| 2026-11-08 | NO_CALL | | | | | | | | | | |
| 2026-11-09 | N | 10:14 | SELL | bear_engulf | 20 | cap10 | 10.0 | 77.6 | 143.7 | bear | ext |
| 2026-11-11 | Y | 09:33 | BUY | bull_run3 | 30 | cap12 | 12.0 | 66.5 | 29.9 | bull | ext |
| 2026-11-12 | Y | 09:24 | BUY | hammer | 30 | cap10 | 10.0 | 86.3 | 17.5 | bull | ext |
| 2026-11-13 | N | 09:21 | SELL | bear_run3 | 30 | cap12 | 12.0 | 10.0 | 158.8 | bear | ext |
| 2026-11-16 | N | 09:21 | BUY | bull_run2 | 30 | cap12 | 12.0 | 71.0 | 76.3 | bull | ext |

## Loss sample detail (all hold 1/day losses)

| Day | HM | Side | Pattern | T1 | SL | MFE | MAE | Why note |
|---|---|---|---|---:|---:|---:|---:|---|
| 2026-08-05 | 09:32 | BUY | marubozu_bull | 30 | 12.0 | 41.1 | 59.2 | SL-first (MFE later ≥T1) |
| 2026-08-06 | 09:20 | BUY | bull_run2 | 30 | 10.0 | 32.1 | 31.7 | SL-first (MFE later ≥T1) |
| 2026-08-07 | 09:30 | SELL | marubozu_bear | 20 | 10.0 | 42.4 | 35.8 | SL-first (MFE later ≥T1) |
| 2026-08-10 | 09:45 | SELL | bear_run2 | 20 | 5.0 | 0.0 | 95.7 | weak MFE |
| 2026-08-11 | 09:23 | SELL | bear_run2 | 30 | 12.0 | 52.9 | 15.0 | SL-first (MFE later ≥T1) |
| 2026-08-13 | 10:29 | SELL | belt_bear | 30 | 10.5 | 7.8 | 95.8 | weak MFE |
| 2026-08-14 | 09:20 | SELL | bear_engulf | 30 | 6.3 | 22.2 | 40.2 | path SL before T1 |
| 2026-08-17 | 09:32 | SELL | bear_run3 | 30 | 12.0 | 59.4 | 26.1 | SL-first (MFE later ≥T1) |
| 2026-08-20 | 09:45 | BUY | bull_run3 | 30 | 6.0 | 12.7 | 20.0 | weak MFE |
| 2026-08-21 | 09:34 | SELL | belt_bear | 30 | 12.0 | 1.5 | 58.9 | weak MFE |
| 2026-08-28 | 09:22 | SELL | bear_engulf | 20 | 10.0 | 0.0 | 76.0 | weak MFE |
| 2026-08-31 | 09:26 | SELL | belt_bear | 30 | 12.0 | 55.6 | 18.2 | SL-first (MFE later ≥T1) |
| 2026-09-01 | 09:43 | SELL | belt_bear | 30 | 12.0 | 23.2 | 110.4 | path SL before T1 |
| 2026-09-02 | 09:22 | SELL | three_outside_dn | 30 | 12.0 | 16.5 | 92.8 | path SL before T1 |
| 2026-09-04 | 09:35 | SELL | evening_star | 20 | 10.0 | 5.6 | 89.1 | weak MFE |
| 2026-09-07 | 09:27 | SELL | belt_bear | 30 | 7.8 | 67.6 | 15.5 | SL-first (MFE later ≥T1) |
| 2026-09-10 | 09:22 | SELL | bear_engulf | 30 | 12.0 | 18.7 | 29.9 | path SL before T1 |
| 2026-09-11 | 09:32 | SELL | marubozu_bear | 30 | 12.0 | 2.5 | 112.5 | weak MFE |
| 2026-09-15 | 10:03 | SELL | bear_engulf | 30 | 12.0 | 66.2 | 21.5 | SL-first (MFE later ≥T1) |
| 2026-09-17 | 09:28 | BUY | bull_run3 | 20 | 10.0 | 68.1 | 47.0 | SL-first (MFE later ≥T1) |
| 2026-09-18 | 09:23 | BUY | bull_run3 | 30 | 10.0 | 11.0 | 40.9 | weak MFE |
| 2026-09-21 | 09:48 | BUY | bull_engulf | 30 | 10.0 | 7.8 | 46.0 | weak MFE |
| 2026-09-22 | 09:42 | BUY | bull_run2 | 30 | 9.1 | 14.0 | 93.6 | weak MFE |
| 2026-09-23 | 11:32 | BUY | bull_kicker | 30 | 8.0 | 25.9 | 16.8 | path SL before T1 |
| 2026-09-25 | 09:49 | SELL | bear_run2 | 30 | 11.0 | 15.6 | 56.8 | path SL before T1 |
| 2026-09-28 | 09:22 | SELL | bear_run3 | 30 | 12.0 | 106.5 | 23.8 | SL-first (MFE later ≥T1) |
| 2026-09-30 | 09:20 | BUY | bull_run3 | 30 | 12.0 | 51.5 | 54.3 | SL-first (MFE later ≥T1) |
| 2026-10-09 | 09:29 | BUY | marubozu_bull | 30 | 12.0 | 159.3 | 12.6 | SL-first (MFE later ≥T1) |
| 2026-10-14 | 09:44 | BUY | bull_run3 | 30 | 12.0 | 25.8 | 76.8 | path SL before T1 |
| 2026-10-16 | 09:35 | SELL | bear_run3 | 30 | 12.0 | 13.4 | 222.6 | weak MFE |
| 2026-10-19 | 09:28 | SELL | marubozu_bear | 30 | 12.0 | 7.0 | 191.0 | weak MFE |
| 2026-10-21 | 09:31 | BUY | bull_run2 | 30 | 10.0 | 23.2 | 228.2 | path SL before T1 |
| 2026-10-22 | 09:24 | SELL | bear_engulf | 30 | 12.0 | 5.6 | 224.6 | weak MFE |
| 2026-10-26 | 09:21 | SELL | belt_bear | 30 | 12.0 | 24.8 | 294.0 | path SL before T1 |
| 2026-10-27 | 09:29 | BUY | bull_run3 | 30 | 12.0 | 58.1 | 61.9 | SL-first (MFE later ≥T1) |
| 2026-10-28 | 09:29 | SELL | bear_run3 | 30 | 12.0 | 54.2 | 109.5 | SL-first (MFE later ≥T1) |
| 2026-10-30 | 09:30 | BUY | bull_engulf | 30 | 11.2 | 68.4 | 69.6 | SL-first (MFE later ≥T1) |
| 2026-11-02 | 09:28 | BUY | bull_run3 | 30 | 12.0 | 88.4 | 17.1 | SL-first (MFE later ≥T1) |
| 2026-11-06 | 09:25 | SELL | bear_run3 | 20 | 10.0 | 11.0 | 226.6 | path SL before T1 |
| 2026-11-09 | 10:14 | SELL | bear_engulf | 20 | 10.0 | 77.6 | 143.7 | SL-first (MFE later ≥T1) |
| 2026-11-13 | 09:21 | SELL | bear_run3 | 30 | 12.0 | 10.0 | 158.8 | weak MFE |
| 2026-11-16 | 09:21 | BUY | bull_run2 | 30 | 12.0 | 71.0 | 76.3 | SL-first (MFE later ≥T1) |

## Simple read

- Hold 1/day hit **41.67%** on **72/73** days — cover almost full, accuracy not 100%.
- Gate-only (no fingerprint lock) hold 1/day was **47.95%** — micros help a bit vs raw gate when they do.
- Many losses are **SL-first**: price eventually travels ≥T1 after stop already hit.
