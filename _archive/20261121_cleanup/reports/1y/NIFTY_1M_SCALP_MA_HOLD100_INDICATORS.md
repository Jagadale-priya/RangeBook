# MA HOLD100 — **indicator research** → aim 100%

Exit: **trail34 T1=12** · Hold last3m **`2026-08-17`→`2026-11-16`** (63d) · Train 185d

## Indicator lift: oracle-win vs early-loss (train)

| Flag | Oracle% | EarlyLoss% | Gap |
|---|---:|---:|---:|
| `macd_turn` | 69.7% | 28.6% | +41.1pp |
| `di_ok` | 69.7% | 24.3% | +45.4pp |
| `vwap_with` | 76.2% | 67.6% | +8.6pp |
| `adx_trend` | 99.5% | 98.9% | +0.6pp |
| `rsi_ok` | 40.0% | 34.6% | +5.4pp |
| `rsi_pull` | 13.5% | 17.8% | -4.3pp |
| `stoch_ok` | 49.2% | 80.5% | -31.3pp |
| `ind_basic` | 24.3% | 13.0% | +11.3pp |
| `ind_strict` | 5.4% | 2.7% | +2.7pp |
| `ind_strict3` | 3.8% | 1.6% | +2.2pp |
| `ind_pull` | 0.0% | 1.1% | -1.1pp |

## A) Indicator gate only (1st match / day)

| Gate | Train n@hit cover | Hold n@hit cover |
|---|---|---|
| `raw` | 185@55.68% 100.0% | 63@53.97% 100.0% |
| `macd_turn` | 185@68.11% 100.0% | 63@73.02% 100.0% |
| `di_ok` | 185@67.57% 100.0% | 63@77.78% 100.0% |
| `vwap_with` | 185@54.05% 100.0% | 63@57.14% 100.0% |
| `adx_trend` | 185@55.14% 100.0% | 63@53.97% 100.0% |
| `ind_basic` | 185@56.76% 100.0% | 63@49.21% 100.0% |
| `ind_strict` | 185@49.73% 100.0% | 63@50.79% 100.0% |
| `ind_strict2` | 185@53.51% 100.0% | 63@61.9% 100.0% |
| `ind_strict3` | 185@64.86% 100.0% | 62@66.13% 98.4% |
| `ind_pull` | 185@58.92% 100.0% | 63@66.67% 100.0% |
| `macd+di` | 185@68.65% 100.0% | 63@74.6% 100.0% |
| `macd+di+vwap` | 185@68.11% 100.0% | 63@69.84% 100.0% |
| `macd+di+vwap+hard34` | 185@72.97% 100.0% | 62@80.65% 98.4% |
| `strict3+stack34` | 185@64.86% 100.0% | 62@66.13% 98.4% |
| `basic+hard34` | 185@69.19% 100.0% | 63@77.78% 100.0% |

## B) Indicator + clean-key picker (train 100% keys)

| Book | Train | Hold |
|---|---|---|
| `raw_m1_k1` | 185@100.0% 100.0% | 63@50.79% 100.0% |
| `raw_m1_k2` | 170@100.0% 91.9% | 52@46.15% 82.5% |
| `raw_m2_k1` | 184@100.0% 99.5% | 62@54.84% 98.4% |
| `raw_m2_k2` | 118@100.0% 63.8% | 24@54.17% 38.1% |
| `macd_turn_m1_k1` | 185@100.0% 100.0% | 63@55.56% 100.0% |
| `macd_turn_m1_k2` | 174@100.0% 94.1% | 48@56.25% 76.2% |
| `macd_turn_m2_k1` | 184@100.0% 99.5% | 61@55.74% 96.8% |
| `macd_turn_m2_k2` | 114@100.0% 61.6% | 21@57.14% 33.3% |
| `di_ok_m1_k1` | 185@100.0% 100.0% | 63@55.56% 100.0% |
| `di_ok_m1_k2` | 173@100.0% 93.5% | 52@50.0% 82.5% |
| `di_ok_m2_k1` | 185@100.0% 100.0% | 62@54.84% 98.4% |
| `di_ok_m2_k2` | 120@100.0% 64.9% | 26@50.0% 41.3% |
| `vwap_with_m1_k1` | 185@100.0% 100.0% | 63@57.14% 100.0% |
| `vwap_with_m1_k2` | 173@100.0% 93.5% | 54@59.26% 85.7% |
| `vwap_with_m2_k1` | 185@100.0% 100.0% | 63@52.38% 100.0% |
| `vwap_with_m2_k2` | 135@100.0% 73.0% | 34@50.0% 54.0% |
| `adx_trend_m1_k1` | 185@100.0% 100.0% | 63@55.56% 100.0% |
| `adx_trend_m1_k2` | 179@100.0% 96.8% | 49@46.94% 77.8% |
| `adx_trend_m2_k1` | 183@100.0% 98.9% | 61@63.93% 96.8% |
| `adx_trend_m2_k2` | 126@100.0% 68.1% | 23@47.83% 36.5% |
| `ind_basic_m1_k1` | 184@100.0% 99.5% | 63@52.38% 100.0% |
| `ind_basic_m1_k2` | 172@100.0% 93.0% | 60@53.33% 95.2% |
| `ind_basic_m2_k1` | 184@100.0% 99.5% | 61@50.82% 96.8% |
| `ind_basic_m2_k2` | 130@100.0% 70.3% | 28@32.14% 44.4% |
| `ind_strict_m1_k1` | 178@100.0% 96.2% | 62@53.23% 98.4% |
| `ind_strict_m1_k2` | 162@100.0% 87.6% | 46@54.35% 73.0% |
| `ind_strict_m2_k1` | 166@100.0% 89.7% | 57@59.65% 90.5% |
| `ind_strict2_m1_k1` | 159@100.0% 85.9% | 61@50.82% 96.8% |
| `ind_strict2_m1_k2` | 128@100.0% 69.2% | 45@55.56% 71.4% |
| `ind_strict2_m2_k1` | 150@100.0% 81.1% | 54@61.11% 85.7% |
| `ind_strict2_m2_k2` | 81@100.0% 43.8% | 13@76.92% 20.6% |
| `ind_strict3_m1_k1` | 175@100.0% 94.6% | 62@61.29% 98.4% |
| `ind_strict3_m1_k2` | 140@100.0% 75.7% | 42@54.76% 66.7% |
| `ind_strict3_m2_k1` | 161@100.0% 87.0% | 53@58.49% 84.1% |
| `ind_strict3_m2_k2` | 96@100.0% 51.9% | 25@48.0% 39.7% |
| `ind_pull_m1_k1` | 154@100.0% 83.2% | 59@55.93% 93.7% |
| `ind_pull_m1_k2` | 128@100.0% 69.2% | 35@65.71% 55.6% |
| `ind_pull_m2_k1` | 128@100.0% 69.2% | 48@58.33% 76.2% |
| `macd+di_m1_k1` | 185@100.0% 100.0% | 62@54.84% 98.4% |
| `macd+di_m1_k2` | 168@100.0% 90.8% | 50@54.0% 79.4% |
| `macd+di_m2_k1` | 183@100.0% 98.9% | 61@55.74% 96.8% |
| `macd+di_m2_k2` | 114@100.0% 61.6% | 23@56.52% 36.5% |
| `macd+di+vwap_m1_k1` | 185@100.0% 100.0% | 63@53.97% 100.0% |
| `macd+di+vwap_m1_k2` | 173@100.0% 93.5% | 54@55.56% 85.7% |
| `macd+di+vwap_m2_k1` | 183@100.0% 98.9% | 62@54.84% 98.4% |
| `macd+di+vwap_m2_k2` | 135@100.0% 73.0% | 35@57.14% 55.6% |
| `macd+di+vwap+hard34_m1_k1` | 180@100.0% 97.3% | 62@62.9% 98.4% |
| `macd+di+vwap+hard34_m1_k2` | 146@100.0% 78.9% | 45@60.0% 71.4% |
| `macd+di+vwap+hard34_m2_k1` | 177@100.0% 95.7% | 60@63.33% 95.2% |
| `macd+di+vwap+hard34_m2_k2` | 105@100.0% 56.8% | 24@54.17% 38.1% |
| `strict3+stack34_m1_k1` | 175@100.0% 94.6% | 62@61.29% 98.4% |
| `strict3+stack34_m1_k2` | 140@100.0% 75.7% | 42@54.76% 66.7% |
| `strict3+stack34_m2_k1` | 161@100.0% 87.0% | 53@58.49% 84.1% |
| `strict3+stack34_m2_k2` | 96@100.0% 51.9% | 25@48.0% 39.7% |
| `basic+hard34_m1_k1` | 183@100.0% 98.9% | 61@59.02% 96.8% |
| `basic+hard34_m1_k2` | 164@100.0% 88.6% | 51@58.82% 81.0% |
| `basic+hard34_m2_k1` | 175@100.0% 94.6% | 61@59.02% 96.8% |
| `basic+hard34_m2_k2` | 117@100.0% 63.2% | 19@52.63% 30.2% |

## Closest to 100/100 (train 100%, cover≥70)

- `adx_trend_m2_k1`: hold **63.93%** cover 96.8% · train cover 98.9%
- `macd+di+vwap+hard34_m2_k1`: hold **63.33%** cover 95.2% · train cover 95.7%
- `macd+di+vwap+hard34_m1_k1`: hold **62.9%** cover 98.4% · train cover 97.3%
- `ind_strict3_m1_k1`: hold **61.29%** cover 98.4% · train cover 94.6%
- `strict3+stack34_m1_k1`: hold **61.29%** cover 98.4% · train cover 94.6%
- `ind_strict2_m2_k1`: hold **61.11%** cover 85.7% · train cover 81.1%
- `macd+di+vwap+hard34_m1_k2`: hold **60.0%** cover 71.4% · train cover 78.9%
- `ind_strict_m2_k1`: hold **59.65%** cover 90.5% · train cover 89.7%
- `vwap_with_m1_k2`: hold **59.26%** cover 85.7% · train cover 93.5%
- `basic+hard34_m1_k1`: hold **59.02%** cover 96.8% · train cover 98.9%
- `basic+hard34_m2_k1`: hold **59.02%** cover 96.8% · train cover 94.6%
- `basic+hard34_m1_k2`: hold **58.82%** cover 81.0% · train cover 88.6%

### Day-by-day best `adx_trend_m2_k1`

| Day | Y/N | HM | Side | Pattern | macd | DI | VWAP | ADX | MFE |
|---|---|---|---|---|---|---|---|---:|---:|
| 2026-08-17 | Y | 09:21 | SELL | shooting_star | 1 | 1 | 0 | 84 | 75.3 |
| 2026-08-18 | Y | 10:00 | SELL | tweezer_top | 0 | 0 | 1 | 18 | 49.2 |
| 2026-08-19 | Y | 09:25 | SELL | three_crows | 1 | 1 | 1 | 81 | 70.1 |
| 2026-08-20 | Y | 09:20 | BUY | inv_hammer | 1 | 1 | 0 | 81 | 33.1 |
| 2026-08-21 | N | 09:53 | BUY | bull_engulf | 1 | 1 | 1 | 62 | 16.4 |
| 2026-08-24 | Y | 14:09 | SELL | hanging_man | 0 | 1 | 1 | 20 | 33.8 |
| 2026-08-25 | Y | 10:09 | SELL | three_crows | 0 | 1 | 1 | 25 | 19.6 |
| 2026-08-26 | Y | 09:23 | BUY | rising_3_methods | 1 | 1 | 1 | 83 | 33.3 |
| 2026-08-27 | Y | 09:24 | SELL | belt_bear | 1 | 1 | 1 | 37 | 86.8 |
| 2026-08-28 | N | 09:37 | BUY | hammer | 1 | 1 | 1 | 50 | 48.5 |
| 2026-08-31 | Y | 09:23 | SELL | falling_3_methods | 1 | 1 | 0 | 50 | 78.3 |
| 2026-09-01 | N | 09:22 | SELL | bear_engulf | 1 | 0 | 0 | 49 | 32.1 |
| 2026-09-02 | N | 09:46 | SELL | three_crows | 0 | 0 | 0 | 37 | 23.0 |
| 2026-09-03 | N | 10:22 | SELL | three_outside_dn | 0 | 1 | 0 | 33 | 85.7 |
| 2026-09-04 | N | 12:21 | SELL | hanging_man | 1 | 1 | 1 | 55 | 18.0 |
| 2026-09-07 | Y | 09:27 | SELL | belt_bear | 1 | 1 | 1 | 82 | 67.6 |
| 2026-09-08 | N | 10:27 | BUY | bull_engulf | 0 | 0 | 1 | 47 | 3.4 |
| 2026-09-09 | Y | 09:27 | SELL | hanging_man | 0 | 1 | 0 | 81 | 46.0 |
| 2026-09-10 | N | 10:02 | SELL | three_crows | 1 | 1 | 1 | 33 | 9.5 |
| 2026-09-11 | Y | 10:13 | BUY | bull_kicker | 1 | 1 | 1 | 76 | 65.9 |
| 2026-09-15 | N | 09:27 | BUY | inv_hammer | 0 | 1 | 0 | 52 | 6.5 |
| 2026-09-16 | Y | 10:22 | BUY | rising_3_methods | 1 | 1 | 1 | 30 | 69.4 |
| 2026-09-17 | Y | 09:27 | BUY | bull_run3 | 1 | 1 | 1 | 61 | 76.2 |
| 2026-09-18 | N | 13:12 | BUY | tweezer_bot | 0 | 1 | 1 | 27 | 57.4 |
| 2026-09-21 | Y | 10:56 | BUY | tweezer_bot | 1 | 1 | 0 | 53 | 51.1 |
| 2026-09-22 | N | 09:47 | BUY | three_outside_up | 1 | 1 | 1 | 26 | 10.6 |
| 2026-09-23 | Y | 10:44 | BUY | bull_kicker | 0 | 1 | 1 | 43 | 54.1 |
| 2026-09-24 | Y | 09:59 | SELL | hanging_man | 0 | 0 | 1 | 35 | 35.2 |
| 2026-09-25 | N | 09:25 | SELL | bear_engulf | 0 | 0 | 1 | 27 | 42.7 |
| 2026-09-28 | N | 12:05 | BUY | tweezer_bot | 1 | 0 | 0 | 42 | 19.7 |
| 2026-09-29 | N | 09:42 | BUY | three_soldiers | 1 | 0 | 0 | 76 | 108.5 |
| 2026-09-30 | Y | 09:41 | BUY | belt_bull | 0 | 0 | 0 | 34 | 75.0 |
| 2026-10-01 | Y | 13:40 | SELL | bear_kicker | 0 | 1 | 1 | 20 | 110.4 |
| 2026-10-05 | Y | 09:32 | BUY | rising_3_methods | 1 | 1 | 1 | 36 | 33.4 |
| 2026-10-06 | Y | 09:24 | BUY | rising_3_methods | 1 | 1 | 1 | 70 | 92.9 |
| 2026-10-07 | Y | 09:30 | SELL | hanging_man | 0 | 0 | 0 | 26 | 44.2 |
| 2026-10-08 | Y | 09:26 | SELL | three_crows | 1 | 1 | 1 | 86 | 135.1 |
| 2026-10-09 | Y | 09:29 | BUY | marubozu_bull | 1 | 1 | 1 | 59 | 159.3 |
| 2026-10-12 | Y | 10:30 | SELL | three_crows | 1 | 1 | 1 | 23 | 105.6 |
| 2026-10-13 | N | 10:59 | SELL | three_crows | 0 | 1 | 1 | 20 | 16.5 |
| 2026-10-14 | N | 09:33 | BUY | belt_bull | 0 | 1 | 0 | 20 | 66.5 |
| 2026-10-15 | Y | 09:52 | BUY | three_soldiers | 1 | 1 | 1 | 42 | 168.9 |
| 2026-10-16 | N | 14:59 | SELL | falling_3_methods | 1 | 1 | 1 | 55 | 110.1 |
| 2026-10-19 | N | 09:37 | BUY | belt_bull | 1 | 1 | 1 | 36 | 1.4 |
| 2026-10-21 | Y | 10:00 | SELL | belt_bear | 1 | 1 | 1 | 74 | 208.1 |
| 2026-10-22 | Y | 13:33 | SELL | bear_run2 | 1 | 1 | 1 | 40 | 19.1 |
| 2026-10-23 | Y | 10:03 | SELL | three_crows | 1 | 1 | 1 | 43 | 157.7 |
| 2026-10-26 | N | 12:02 | BUY | belt_bull | 1 | 1 | 1 | 35 | 61.2 |
| 2026-10-27 | N | 10:59 | BUY | bull_kicker | 0 | 1 | 1 | 39 | 59.2 |
| 2026-10-28 | Y | 09:38 | BUY | bull_kicker | 1 | 0 | 1 | 42 | 86.9 |
| 2026-10-29 | Y | 10:39 | BUY | tweezer_bot | 0 | 1 | 1 | 61 | 21.3 |
| 2026-10-30 | N | 09:58 | BUY | bull_run2 | 0 | 1 | 1 | 26 | 126.8 |
| 2026-11-02 | Y | 13:08 | SELL | falling_3_methods | 1 | 1 | 1 | 36 | 44.4 |
| 2026-11-03 | NO_CALL | | | | | | | | |
| 2026-11-04 | Y | 12:27 | BUY | belt_bull | 1 | 1 | 0 | 39 | 106.2 |
| 2026-11-05 | Y | 09:37 | BUY | belt_bull | 0 | 1 | 1 | 47 | 83.1 |
| 2026-11-06 | Y | 09:50 | BUY | rising_3_methods | 1 | 1 | 1 | 35 | 48.5 |
| 2026-11-08 | NO_CALL | | | | | | | | |
| 2026-11-09 | Y | 09:53 | SELL | bear_engulf | 0 | 0 | 0 | 20 | 102.5 |
| 2026-11-11 | Y | 09:54 | SELL | three_crows | 1 | 1 | 1 | 44 | 36.4 |
| 2026-11-12 | Y | 09:24 | BUY | hammer | 1 | 1 | 1 | 91 | 86.3 |
| 2026-11-13 | Y | 10:13 | BUY | bull_engulf | 0 | 0 | 1 | 18 | 47.4 |
| 2026-11-16 | N | 11:27 | SELL | marubozu_bear | 1 | 1 | 1 | 22 | 1.1 |

## Exact indicators under test

- **RSI14** side bands / pullback zone
- **MACD hist** turn with trade
- **Stoch %K/%D** confirmation
- **ADX +DI/−DI** trend alignment
- **Session VWAP** side (ATR-normalized)
- **Bollinger %B** / mid
- **ATR%** regime
- Plus held **EMA34 trail T1=12** exit

Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_ma_hold100`

## C) Tighter indicator combos (gate-only 1/day)

| Combo | Train hit/cover | Hold hit/cover |
|---|---|---|
| `di+hard34+vwap` | 74.05% / 100.0% | **84.13%** / 100.0% |
| `macd+di+hard34` | 72.97% / 100.0% | **83.87%** / 98.4% |
| `macd+di+bbmid+hard34` | 72.97% / 100.0% | **83.87%** / 98.4% |
| `macd+di+vwap+hard34+close` | 73.51% / 100.0% | **83.87%** / 98.4% |
| `macd+di+mom+hard34` | 74.05% / 100.0% | **82.26%** / 98.4% |
| `macd+di+vwap+hard34` | 72.97% / 100.0% | **80.65%** / 98.4% |
| `macd+di+vwap+bbmid+hard34` | 72.97% / 100.0% | **80.65%** / 98.4% |
| `macd+di+vwap+hard34+nofail` | 74.59% / 100.0% | **80.65%** / 98.4% |
| `di` | 67.57% / 100.0% | **77.78%** / 100.0% |
| `basic+hard34` | 69.19% / 100.0% | **77.78%** / 100.0% |
| `macd+di+hard21` | 74.05% / 100.0% | **75.81%** / 98.4% |
| `macd+di` | 68.65% / 100.0% | **74.6%** / 100.0% |
| `macd+di+vwap+hard34+rsi` | 64.86% / 100.0% | **66.13%** / 98.4% |
| `macd+di+vwap+hard34+m575` | 65.41% / 100.0% | **66.13%** / 98.4% |
| `macd+di+hard34+m575` | 62.7% / 100.0% | **62.9%** / 98.4% |
| `macd+di+vwap+hard34+m600` | 68.11% / 100.0% | **61.29%** / 98.4% |
| `macd+di+hard34+m600` | 65.41% / 100.0% | **58.06%** / 98.4% |

### Best combo: `di+hard34+vwap` → hold **84.13%** cover 100.0%

Still short of 100% blind; strongest signals: **MACD turn + DI align + EMA34 hard** (± VWAP).
Stochastic alone was anti-predictive on train (losses had higher stoch_ok).
