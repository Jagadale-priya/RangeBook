# MA HOLD100 — hunt **100% path** + **100% cover**

Window `2025-11-17`→`2026-11-16` · Train `<2026-08-01` (175d) · Hold unknown `≥2026-08-01` (73d)

## Hold/exit logic (accurate)

1. Enter on textbook candle when gate passes.
2. **Hold with MA**: stay while close on right side of EMA (trail34/21) or inside EMA±k·ATR band.
3. **Win** only if chosen T1 prints **before** MA hold breaks.
4. Fingerprints locked **100% clean on train only**; hold is blind.

## Oracle ceiling (any gated event that wins under exit)

| Mode@T1 | Train oracle days | Hold oracle days |
|---|---:|---:|
| `trail34` t15 | 175/175 (100.0%) | 73/73 (100.0%) |
| `trail34` t20 | 175/175 (100.0%) | 73/73 (100.0%) |
| `trail21` t15 | 175/175 (100.0%) | 73/73 (100.0%) |
| `trail21` t20 | 175/175 (100.0%) | 73/73 (100.0%) |
| `band34_k1` t15 | 175/175 (100.0%) | 73/73 (100.0%) |
| `band34_k1` t20 | 175/175 (100.0%) | 73/73 (100.0%) |
| `band34_k15` t15 | 175/175 (100.0%) | 73/73 (100.0%) |
| `band34_k15` t20 | 175/175 (100.0%) | 73/73 (100.0%) |
| `dual21_50` t15 | 175/175 (100.0%) | 73/73 (100.0%) |
| `dual21_50` t20 | 175/175 (100.0%) | 73/73 (100.0%) |

## Blind books (100% train lock)

| Book | Micros | Train 1d n@hit cover | Hold 1d n@hit cover | all_win hold |
|---|---:|---|---|:---:|
| **band34_k15_t12_hard34_m1** | 74 | 175@100.0% 100.0% | 59@76.27% 80.8% | False |
| **band34_k15_t12_hard34_m2** | 74 | 175@100.0% 100.0% | 59@76.27% 80.8% | False |
| **band34_k15_t12_stack34_m1** | 78 | 175@100.0% 100.0% | 63@74.6% 86.3% | False |
| **band34_k15_t12_stack34_m2** | 78 | 175@100.0% 100.0% | 63@74.6% 86.3% | False |
| **band34_k15_t12_hard50_m1** | 70 | 175@100.0% 100.0% | 60@73.33% 82.2% | False |
| **band34_k15_t12_hard50_m2** | 70 | 175@100.0% 100.0% | 60@73.33% 82.2% | False |
| **band34_k1_t12_hard34_m1** | 83 | 175@100.0% 100.0% | 62@72.58% 84.9% | False |
| **band34_k15_t12_hard21_m1** | 76 | 175@100.0% 100.0% | 65@72.31% 89.0% | False |
| **band34_k15_t12_hard21_m2** | 76 | 175@100.0% 100.0% | 65@72.31% 89.0% | False |
| **band34_k1_t12_hard21_m1** | 81 | 175@100.0% 100.0% | 57@68.42% 78.1% | False |
| **band34_k1_t12_hard21_m2** | 81 | 175@100.0% 100.0% | 57@68.42% 78.1% | False |
| **band34_k1_t12_stack34_m1** | 82 | 175@100.0% 100.0% | 64@64.06% 87.7% | False |
| **band34_k15_t12_ema34_m1** | 65 | 175@100.0% 100.0% | 65@63.08% 89.0% | False |
| **band34_k15_t12_ema34_m2** | 65 | 175@100.0% 100.0% | 65@63.08% 89.0% | False |
| **band34_k1_t12_hard50_m1** | 76 | 175@100.0% 100.0% | 63@61.9% 86.3% | False |
| **trail34_t12_stack34_m1** | 91 | 175@100.0% 100.0% | 65@61.54% 89.0% | False |
| **band34_k1_t12_ema34_m1** | 73 | 175@100.0% 100.0% | 62@59.68% 84.9% | False |
| **band34_k1_t12_ema34_m2** | 73 | 175@100.0% 100.0% | 62@59.68% 84.9% | False |
| **band34_k15_t18_ema34_m1** | 85 | 175@100.0% 100.0% | 55@58.18% 75.3% | False |
| **band34_k15_t18_ema34_m2** | 85 | 175@100.0% 100.0% | 55@58.18% 75.3% | False |
| **band34_k15_t20_ema34_m1** | 92 | 175@100.0% 100.0% | 64@57.81% 87.7% | False |
| **band34_k15_t20_ema34_m2** | 92 | 175@100.0% 100.0% | 64@57.81% 87.7% | False |
| **band34_k1_t12_any_m1** | 80 | 175@100.0% 100.0% | 65@56.92% 89.0% | False |
| **band34_k1_t18_any_m1** | 98 | 175@100.0% 100.0% | 55@56.36% 75.3% | False |
| **band34_k15_t12_any_m1** | 63 | 175@100.0% 100.0% | 61@55.74% 83.6% | False |

## Closest to 100% hold hit (train still 100%)

- `trail34_t12_clean21_m1`: hold **83.33%** cover 65.8% · train cover 95.4% · micros 82
- `trail34_t12_clean21_m2`: hold **82.98%** cover 64.4% · train cover 91.4% · micros 75
- `band34_k1_t12_clean34_m2`: hold **78.57%** cover 76.7% · train cover 94.3% · micros 82
- `band34_k1_t12_clean34_m1`: hold **76.79%** cover 76.7% · train cover 97.1% · micros 87
- `band34_k1_t12_clean21_m1`: hold **76.36%** cover 75.3% · train cover 97.7% · micros 89
- `band34_k1_t12_clean21_m2`: hold **76.36%** cover 75.3% · train cover 95.4% · micros 85
- `band34_k15_t12_hard34_m1`: hold **76.27%** cover 80.8% · train cover 100.0% · micros 74
- `band34_k15_t12_hard34_m2`: hold **76.27%** cover 80.8% · train cover 100.0% · micros 74
- `band34_k15_t12_clean34_m1`: hold **75.47%** cover 72.6% · train cover 98.9% · micros 81
- `band34_k15_t12_clean34_m2`: hold **75.47%** cover 72.6% · train cover 96.6% · micros 77

## UNION densest (gate=any, min_n=1, train 100% cells)

| Book | Micros | Train | Hold |
|---|---:|---|---|
| **UNION_trail34_t15** | 86 | 175@100.0% 100.0% | 63@52.38% 86.3% |
| **UNION_trail34_t18** | 108 | 175@100.0% 100.0% | 57@50.88% 78.1% |
| **UNION_trail34_t20** | 110 | 174@100.0% 99.4% | 53@49.06% 72.6% |
| **UNION_band34_k15_t15** | 68 | 175@100.0% 100.0% | 55@45.45% 75.3% |
| **UNION_band34_k15_t18** | 87 | 175@100.0% 100.0% | 55@43.64% 75.3% |
| **UNION_band34_k15_t20** | 98 | 175@100.0% 100.0% | 63@50.79% 86.3% |
| **UNION_trail21_t15** | 97 | 175@100.0% 100.0% | 61@36.07% 83.6% |
| **UNION_trail21_t18** | 117 | 175@100.0% 100.0% | 53@50.94% 72.6% |
| **UNION_trail21_t20** | 118 | 174@100.0% 99.4% | 47@44.68% 64.4% |

### Hold day-by-day — `UNION_trail34_t15` (52.38% / cover 86.3%)

| Day | Y/N | HM | Side | Pattern | T1 | reason | MFE |
|---|---|---|---|---|---:|---|---:|
| 2026-08-03 | N | 14:31 | BUY | bull_engulf | 15 | ma_sl | 184.5 |
| 2026-08-04 | Y | 10:22 | SELL | three_crows | 15 | t1 | 104.6 |
| 2026-08-05 | N | 09:34 | SELL | marubozu_bear | 15 | ma_sl | 48.5 |
| 2026-08-06 | N | 13:47 | SELL | marubozu_bear | 15 | ma_sl | 84.7 |
| 2026-08-07 | N | 11:15 | SELL | marubozu_bear | 15 | ma_sl | 30.6 |
| 2026-08-10 | Y | 14:47 | SELL | falling_3_methods | 15 | t1 | 102.1 |
| 2026-08-11 | NO_CALL | | | | | | |
| 2026-08-12 | N | 13:08 | SELL | bear_run3 | 15 | ma_sl | 3.9 |
| 2026-08-13 | N | 10:30 | SELL | three_crows | 15 | ma_sl | 0.5 |
| 2026-08-14 | Y | 09:26 | SELL | hanging_man | 15 | t1 | 26.8 |
| 2026-08-17 | NO_CALL | | | | | | |
| 2026-08-18 | Y | 09:52 | SELL | hanging_man | 15 | t1 | 54.2 |
| 2026-08-19 | N | 10:46 | SELL | belt_bear | 15 | ma_sl | 24.8 |
| 2026-08-20 | NO_CALL | | | | | | |
| 2026-08-21 | NO_CALL | | | | | | |
| 2026-08-24 | NO_CALL | | | | | | |
| 2026-08-25 | Y | 10:09 | SELL | three_crows | 15 | t1 | 19.6 |
| 2026-08-26 | Y | 09:23 | BUY | rising_3_methods | 15 | t1 | 33.3 |
| 2026-08-27 | Y | 10:51 | SELL | three_crows | 15 | t1 | 27.2 |
| 2026-08-28 | N | 10:43 | SELL | three_outside_dn | 15 | ma_sl | 82.6 |
| 2026-08-31 | N | 10:11 | SELL | three_crows | 15 | ma_sl | 21.4 |
| 2026-09-01 | N | 09:22 | SELL | bear_engulf | 15 | ma_sl | 32.1 |
| 2026-09-02 | N | 14:04 | SELL | marubozu_bear | 15 | ma_sl | 22.1 |
| 2026-09-03 | N | 10:22 | SELL | three_outside_dn | 15 | ma_sl | 85.7 |
| 2026-09-04 | NO_CALL | | | | | | |
| 2026-09-07 | Y | 10:40 | SELL | belt_bear | 15 | t1 | 45.2 |
| 2026-09-08 | Y | 09:52 | SELL | three_outside_dn | 15 | t1 | 25.8 |
| 2026-09-09 | N | 10:34 | SELL | marubozu_bear | 15 | ma_sl | 55.0 |
| 2026-09-10 | N | 10:02 | SELL | three_crows | 15 | ma_sl | 9.5 |
| 2026-09-11 | N | 11:03 | SELL | marubozu_bear | 15 | ma_sl | 2.3 |
| 2026-09-15 | Y | 14:45 | SELL | three_outside_dn | 15 | t1 | 91.6 |
| 2026-09-16 | Y | 10:20 | BUY | tweezer_bot | 15 | t1 | 75.7 |
| 2026-09-17 | N | 13:42 | SELL | bear_engulf | 15 | ma_sl | 6.5 |
| 2026-09-18 | Y | 11:46 | BUY | three_outside_up | 15 | t1 | 34.3 |
| 2026-09-21 | N | 14:52 | BUY | bull_kicker | 15 | ma_sl | 38.3 |
| 2026-09-22 | Y | 13:54 | SELL | bear_run2 | 15 | t1 | 21.8 |
| 2026-09-23 | N | 13:11 | SELL | belt_bear | 15 | ma_sl | 35.5 |
| 2026-09-24 | Y | 09:59 | SELL | hanging_man | 15 | t1 | 35.2 |
| 2026-09-25 | N | 09:25 | SELL | bear_engulf | 15 | ma_sl | 42.7 |
| 2026-09-28 | Y | 10:17 | SELL | three_crows | 15 | t1 | 32.4 |
| 2026-09-29 | NO_CALL | | | | | | |
| 2026-09-30 | N | 09:26 | BUY | marubozu_bull | 15 | ma_sl | 38.8 |
| 2026-10-01 | Y | 13:40 | SELL | bear_kicker | 15 | t1 | 110.4 |
| 2026-10-05 | N | 10:56 | BUY | marubozu_bull | 15 | ma_sl | 35.5 |
| 2026-10-06 | Y | 10:59 | BUY | bull_engulf | 15 | t1 | 67.0 |
| 2026-10-07 | N | 10:36 | SELL | marubozu_bear | 15 | ma_sl | 6.8 |
| 2026-10-08 | Y | 10:20 | SELL | three_crows | 15 | t1 | 124.8 |
| 2026-10-09 | Y | 09:29 | BUY | marubozu_bull | 15 | t1 | 159.3 |
| 2026-10-12 | Y | 10:51 | SELL | belt_bear | 15 | t1 | 87.8 |
| 2026-10-13 | Y | 14:37 | BUY | bull_kicker | 15 | t1 | 116.0 |
| 2026-10-14 | Y | 11:53 | BUY | three_outside_up | 15 | t1 | 24.8 |
| 2026-10-15 | Y | 09:25 | BUY | belt_bull | 15 | t1 | 214.2 |
| 2026-10-16 | N | 11:34 | BUY | marubozu_bull | 15 | ma_sl | 19.5 |
| 2026-10-19 | N | 09:37 | BUY | belt_bull | 15 | ma_sl | 1.4 |
| 2026-10-21 | Y | 13:28 | SELL | three_outside_dn | 15 | t1 | 77.9 |
| 2026-10-22 | Y | 09:48 | BUY | belt_bull | 15 | t1 | 121.3 |
| 2026-10-23 | Y | 10:03 | SELL | three_crows | 15 | t1 | 157.7 |
| 2026-10-26 | N | 09:45 | BUY | belt_bull | 15 | ma_sl | 224.1 |
| 2026-10-27 | N | 13:36 | SELL | bear_engulf | 15 | ma_sl | 143.9 |
| 2026-10-28 | Y | 10:55 | BUY | bull_kicker | 15 | t1 | 159.8 |
| 2026-10-29 | N | 13:01 | SELL | bear_run3 | 15 | ma_sl | 2.5 |
| 2026-10-30 | Y | 10:50 | BUY | bull_engulf | 15 | t1 | 175.6 |
| 2026-11-02 | Y | 13:26 | SELL | bear_run3 | 15 | t1 | 36.1 |
| 2026-11-03 | NO_CALL | | | | | | |
| 2026-11-04 | N | 09:27 | BUY | marubozu_bull | 15 | ma_sl | 11.6 |
| 2026-11-05 | N | 10:58 | BUY | bull_engulf | 15 | ma_sl | 80.7 |
| 2026-11-06 | NO_CALL | | | | | | |
| 2026-11-08 | NO_CALL | | | | | | |
| 2026-11-09 | Y | 14:43 | BUY | bull_kicker | 15 | t1 | 419.0 |
| 2026-11-11 | N | 10:18 | BUY | rising_3_methods | 15 | ma_sl | 28.8 |
| 2026-11-12 | Y | 09:24 | BUY | hammer | 15 | t1 | 86.3 |
| 2026-11-13 | Y | 10:13 | BUY | bull_engulf | 15 | t1 | 47.4 |
| 2026-11-16 | Y | 09:42 | BUY | tweezer_bot | 15 | t1 | 46.9 |

## Accurate read

### Hold/exit that can do 100/100 (proven)

**EMA34 trail · T1=12**: stay in while close holds the right side of EMA34; win only if +12 hits first.

| Selector | Train | Hold |
|---|---|---|
| **ORACLE** first winning bar of day | **100% hit · 100% cover** | **100% hit · 100% cover** |
| Blind first clean fingerprint | 100% · 100% | 58.9% · 100% |
| Blind `trail34_t12_clean21` book | 100% · 95% | **83.3% · 66%** |
| UNION densest trail34 | 100% · 100% | ~50% · ~86% |

- **Oracle proves** every day (train + hold) has ≥1 accurate MA-hold call → **100% cover @ 100% accuracy is possible** with this exit.
- **Blind selector is the remaining gap** — fingerprints locked on train still pick wrong bars ~17–40% of hold days.
- Do **not** use oracle live; next work is a non-peeking day-picker that matches oracle more often (time-of-day rank, multi-key vote, stricter MA stack at entry).

Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_ma_hold100`
