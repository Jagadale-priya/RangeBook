# NIFTY 1m — daily must-call · **dynamic candle/pattern SL & T1**

**Not live.** Rejected ATR×80 / fixed 5pt. Brackets come from the **signal candle + pattern**.

- Calibrate `2025-07-02`→`2026-08-05` (270 days)
- Last3m `2026-08-06`→`2026-11-06` (64 days)

## Champion: `first_trend_skip` / `pat_sl4.0_t0.35_f8.0`

- Calibrate: **270@88.15%** · avg SL/T1 **101.17/11.34** · RR **8.65**
- Last3m: **64@90.62%** · avg SL/T1 **96.75/11.68** · RR **7.93**
- Median last3m: SL 78.4 / T1 9.86

**Best high-hit dynamic book so far** (not 100% yet with tight RR). Misses cal=['2025-07-03', '2025-07-28', '2025-08-20', '2025-09-10', '2025-09-29'] l3m=['2026-08-10', '2026-08-20', '2026-08-24', '2026-08-28', '2026-09-16']

### Better RR alternative (recommended for risk)

| Book | Hit cal / l3m | Avg SL / T1 | Avg RR |
|---|---|---|---|
| High-hit `pat×4.0` / T1 floor 8 | 88.2% / 90.6% | 97 / 12 | ~7.9 |
| Sane RR `pat×2.5` / T1 floor 8 | 82.6% / 85.9% | **60 / 12** | **~5.0** |

ATR×80 / fixed 5pt is **discarded** (RR ~240 — not tradeable).

### How SL / T1 are set

- Kind `pat` · params `{'sl_k': 4.0, 't1_k': 0.35, 't1_floor': 8.0, 't1_cap': 40.0, 'sl_min': 5.0}`
- **SL** = `sl_k ×` distance from entry to **3-bar pattern extreme** (moves with each candle — not fixed points).
- **T1** = `t1_k ×` pattern range, **floor 8 pts** (so target is 8–~40, not stuck at 5).

### Entry

- Each day: best **trend-aligned** textbook pattern in morning (structure score).
- Skip weak `bull_run2`/`bear_run2` when a better tag exists.

| Day | HM | Side | Primary | SL | T1 | RR | Win |
|---|---|---|---|---:|---:|---:|:---:|
| 2026-08-06 | 09:22 | BUY | bull_run3 | 72.6 | 8.0 | 9.07 | Y |
| 2026-08-07 | 09:23 | BUY | bull_run2 | 81.0 | 8.66 | 9.35 | Y |
| 2026-08-10 | 09:20 | BUY | bull_run3 | 90.0 | 11.83 | 7.61 | N |
| 2026-08-11 | 09:20 | SELL | three_outside_dn | 79.6 | 8.0 | 9.95 | Y |
| 2026-08-12 | 09:21 | SELL | bear_engulf | 71.8 | 10.24 | 7.01 | Y |
| 2026-08-13 | 09:23 | SELL | bear_engulf | 54.6 | 8.0 | 6.82 | Y |
| 2026-08-14 | 09:20 | SELL | bear_engulf | 34.8 | 8.0 | 4.35 | Y |
| 2026-08-17 | 09:21 | SELL | shooting_star | 27.0 | 8.0 | 3.38 | Y |
| 2026-08-18 | 09:24 | BUY | bull_run2 | 58.0 | 8.0 | 7.25 | Y |
| 2026-08-19 | 09:20 | SELL | bear_engulf | 27.0 | 8.0 | 3.38 | Y |
| 2026-08-20 | 09:23 | SELL | bear_run2 | 28.0 | 8.0 | 3.5 | N |
| 2026-08-21 | 09:20 | SELL | marubozu_bear | 135.4 | 11.85 | 11.43 | Y |
| 2026-08-24 | 09:23 | BUY | bull_run2 | 31.2 | 8.0 | 3.9 | N |
| 2026-08-25 | 09:21 | BUY | bull_run3 | 103.6 | 10.9 | 9.5 | Y |
| 2026-08-26 | 09:21 | BUY | three_outside_up | 138.4 | 13.04 | 10.62 | Y |
| 2026-08-27 | 09:20 | SELL | bear_run2 | 74.6 | 8.0 | 9.32 | Y |
| 2026-08-28 | 09:20 | SELL | bear_run3 | 57.6 | 8.0 | 7.2 | N |
| 2026-08-31 | 09:21 | SELL | dark_cloud | 49.0 | 10.34 | 4.74 | Y |
| 2026-09-01 | 09:22 | SELL | bear_engulf | 37.8 | 8.0 | 4.73 | Y |
| 2026-09-02 | 09:21 | SELL | bear_engulf | 72.2 | 8.94 | 8.07 | Y |
| 2026-09-03 | 09:22 | SELL | bear_run2 | 58.4 | 8.0 | 7.3 | Y |
| 2026-09-04 | 09:25 | BUY | belt_bull | 41.2 | 8.0 | 5.15 | Y |
| 2026-09-07 | 09:20 | SELL | evening_star | 61.0 | 8.0 | 7.62 | Y |
| 2026-09-08 | 09:20 | SELL | bear_run2 | 29.0 | 8.0 | 3.62 | Y |
| 2026-09-09 | 09:22 | SELL | bear_engulf | 50.2 | 8.0 | 6.27 | Y |
| 2026-09-10 | 09:20 | SELL | three_outside_dn | 112.8 | 11.51 | 9.8 | Y |
| 2026-09-11 | 09:20 | SELL | hanging_man | 20.4 | 8.85 | 2.3 | Y |
| 2026-09-15 | 09:22 | SELL | belt_bear | 77.2 | 8.0 | 9.65 | Y |
| 2026-09-16 | 09:22 | BUY | bull_run2 | 76.6 | 8.0 | 9.57 | N |
| 2026-09-17 | 09:26 | BUY | bull_run2 | 41.2 | 8.0 | 5.15 | Y |
| 2026-09-18 | 09:20 | SELL | bear_engulf | 148.2 | 15.1 | 9.81 | Y |
| 2026-09-21 | 09:25 | BUY | bull_engulf | 46.2 | 8.0 | 5.77 | Y |
| 2026-09-22 | 09:20 | SELL | bear_run2 | 71.6 | 8.0 | 8.95 | Y |
| 2026-09-23 | 09:34 | BUY | bull_kicker | 36.4 | 8.0 | 4.55 | Y |
| 2026-09-24 | 09:21 | BUY | bull_run2 | 73.0 | 8.77 | 8.33 | Y |
| 2026-09-25 | 09:20 | BUY | hammer | 47.0 | 13.05 | 3.6 | Y |
| 2026-09-28 | 09:20 | SELL | belt_bear | 201.0 | 19.35 | 10.38 | Y |
| 2026-09-29 | 09:20 | SELL | bear_kicker | 172.6 | 15.79 | 10.93 | Y |
| 2026-09-30 | 09:20 | BUY | bull_run3 | 160.2 | 14.98 | 10.69 | Y |
| 2026-10-01 | 09:21 | SELL | bear_run3 | 121.4 | 12.35 | 9.83 | Y |
| 2026-10-05 | 09:21 | SELL | belt_bear | 160.0 | 16.85 | 9.49 | Y |
| 2026-10-06 | 09:20 | SELL | bear_run2 | 118.0 | 10.97 | 10.75 | N |
| 2026-10-07 | 09:20 | SELL | bear_engulf | 73.2 | 8.0 | 9.15 | Y |
| 2026-10-08 | 09:22 | SELL | bear_run2 | 96.6 | 9.94 | 9.72 | Y |
| 2026-10-09 | 09:20 | BUY | marubozu_bull | 90.2 | 19.21 | 4.69 | Y |
| 2026-10-12 | 09:20 | SELL | bear_run3 | 206.6 | 21.75 | 9.5 | Y |
| 2026-10-13 | 09:22 | BUY | bull_run2 | 163.6 | 14.75 | 11.09 | Y |
| 2026-10-14 | 09:20 | SELL | bear_run3 | 150.0 | 17.69 | 8.48 | Y |
| 2026-10-15 | 09:23 | BUY | bull_engulf | 143.0 | 14.98 | 9.55 | Y |
| 2026-10-16 | 09:25 | SELL | bear_engulf | 69.6 | 8.49 | 8.2 | Y |
| 2026-10-19 | 09:20 | SELL | bear_run2 | 205.4 | 19.04 | 10.79 | Y |
| 2026-10-21 | 09:21 | BUY | bull_run2 | 140.6 | 16.87 | 8.33 | Y |
| 2026-10-22 | 09:21 | SELL | bear_engulf | 143.8 | 13.82 | 10.4 | Y |
| 2026-10-23 | 09:20 | SELL | bear_run3 | 267.4 | 24.94 | 10.72 | Y |
| 2026-10-26 | 09:20 | SELL | bear_run3 | 122.8 | 14.87 | 8.26 | Y |
| 2026-10-27 | 09:22 | BUY | bull_run3 | 210.6 | 18.43 | 11.43 | Y |
| 2026-10-28 | 09:22 | SELL | bear_engulf | 163.4 | 18.2 | 8.98 | Y |
| 2026-10-29 | 09:23 | BUY | bull_kicker | 122.8 | 19.65 | 6.25 | Y |
| 2026-10-30 | 09:23 | SELL | marubozu_bear | 101.6 | 9.78 | 10.39 | Y |
| 2026-11-02 | 09:27 | BUY | hammer | 48.8 | 8.0 | 6.1 | Y |
| 2026-11-03 | 09:20 | BUY | bull_kicker | 108.8 | 10.82 | 10.06 | Y |
| 2026-11-04 | 09:20 | BUY | bull_run3 | 157.0 | 14.39 | 10.91 | Y |
| 2026-11-05 | 09:20 | SELL | bear_run2 | 75.0 | 8.0 | 9.38 | Y |
| 2026-11-06 | 09:21 | SELL | hanging_man | 83.4 | 18.67 | 4.47 | Y |

## Other modes

### `best_trend_560_720`
- Near: `candle_sl6.0_t0.8_f8.0` cal 87.04% l3m 92.19% SL/T1 99.58/13.11 RR 7.47
- Sane: `pat_sl2.5_t0.5_f8.0` cal 81.11% l3m 59.65/12.91 hit 82.81% RR 4.5

### `best_any_560_720`
- Near: `candle_sl6.0_t0.8_f8.0` cal 87.04% l3m 92.19% SL/T1 99.58/13.11 RR 7.47
- Sane: `pat_sl2.5_t0.5_f8.0` cal 81.11% l3m 59.65/12.91 hit 82.81% RR 4.5

### `best_trend_575_700`
- Near: `candle_sl6.0_t0.8_f8.0` cal 86.67% l3m 90.62% SL/T1 98.32/12.95 RR 7.47
- Sane: `pat_sl2.5_t0.5_f8.0` cal 80.74% l3m 58.47/12.8 hit 82.81% RR 4.46

### `first_trend_skip`
- Near: `pat_sl4.0_t0.35_f8.0` cal 88.15% l3m 90.62% SL/T1 96.75/11.68 RR 7.93
- Sane: `pat_sl2.5_t0.35_f8.0` cal 82.59% l3m 60.47/11.68 hit 85.94% RR 4.96

## Policy

- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_daily_must_dyn`
- research_only · not_live · dynamic brackets · daily must-call
