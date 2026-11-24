# NIFTY 1m — **scalp 100%** · T1 10/20 · SL = previous candle

**Not live.** Scalping research: fixed target **10 or 20 pts**. Stop = **previous candle low/high** (or signal-candle / 2-bar swing). If T1 always prints first, SL is only structure insurance.

- Calibrate `2025-07-02`→`2026-08-05`
- Last3m `2026-08-06`→`2026-11-06`
- Events: cal **63364** · last3m **15158**

## Exit rules tested

| Style | Stop definition |
|---|---|
| `prev` | BUY: prior bar **low** · SELL: prior bar **high** |
| `sig` | Signal candle extreme (own low/high) |
| `swing2` | 2-bar swing extreme |

Target: **8 / 10 / 12 / 15 / 20** points.

## Pattern behavior (prev-candle SL · T1=10)

| Pattern | N | Hit% | Med SL | Clean N | Clean Hit% |
|---|---:|---:|---:|---:|---:|
| evening_star | 178 | 56.7 | 13.02 | 8 | 75.0 |
| morning_star | 186 | 60.2 | 13.05 | 15 | 66.7 |
| three_crows | 419 | 61.8 | 15.95 | 189 | 64.6 |
| marubozu_bear | 2447 | 61.9 | 16.35 | 558 | 62.7 |
| three_soldiers | 221 | 64.3 | 15.2 | 79 | 60.8 |
| marubozu_bull | 2138 | 63.3 | 16.55 | 420 | 58.8 |
| three_outside_dn | 2747 | 55.4 | 11.9 | 455 | 58.7 |
| falling_3_methods | 197 | 49.7 | 8.35 | 55 | 58.2 |
| bear_run3 | 7908 | 50.1 | 9.6 | 1746 | 56.1 |
| three_outside_up | 2225 | 55.2 | 11.9 | 331 | 54.4 |
| belt_bull | 2296 | 54.1 | 11.68 | 558 | 54.3 |
| bear_run2 | 5760 | 49.0 | 9.3 | 610 | 54.3 |
| bull_run3 | 7956 | 49.0 | 9.5 | 1647 | 53.6 |
| bull_run2 | 6309 | 48.7 | 9.55 | 631 | 52.8 |
| bull_kicker | 856 | 44.9 | 7.9 | 106 | 50.9 |
| belt_bear | 2455 | 52.3 | 10.7 | 706 | 50.8 |
| bull_engulf | 3860 | 48.7 | 8.45 | 573 | 49.4 |
| bear_engulf | 4635 | 49.3 | 8.45 | 713 | 48.8 |
| bear_kicker | 533 | 44.8 | 7.85 | 80 | 48.8 |
| dark_cloud | 194 | 47.4 | 6.77 | 22 | 45.5 |

## Champion 100% book

### `day_unique` · SL=`prev` · T1=10.0

- Filter: `{'primaries': ['morning_star', 'evening_star'], 'regime': 'continuation', 'align': 1, 'min_body': 0.45, 'rsi_lo': 20, 'rsi_hi': 55, 'max_sl_prev': 25.0, 'sl_style': 'prev'}`
- Calibrate: **9 @ 88.89%** · avg/med SL 13.03/10.0 · maxSL 22.2
- Last3m: **4 @ 100.0%** · avg/med SL 10.54/10.57 · maxSL 13.1


| Day | HM | Side | Primary | SL | T1 | RR | Win |
|---|---|---|---|---:|---:|---:|:---:|
| 2026-08-24 | 11:02 | SELL | evening_star | 7.9 | 10.0 | 0.79 | Y |
| 2026-09-03 | 10:40 | SELL | evening_star | 10.45 | 10.0 | 1.05 | Y |
| 2026-09-07 | 09:58 | SELL | evening_star | 10.7 | 10.0 | 1.07 | Y |
| 2026-10-21 | 12:05 | SELL | evening_star | 13.1 | 10.0 | 1.31 | Y |

### Perfect day-unique


### Perfect multi-call

- none

### Near

- `day_unique` SL `prev` T1=10.0 · cal 9@88.89% · l3m 4@100.0% · `{'primaries': ['morning_star', 'evening_star'], 'regime': 'continuation', 'align': 1, 'min_body': 0.45, 'rsi_lo': 20, 'rsi_hi': 55, 'max_sl_prev': 25.0, 'sl_style': 'prev'}`
- `day_unique` SL `swing2` T1=10.0 · cal 9@88.89% · l3m 4@100.0% · `{'primaries': ['morning_star', 'evening_star'], 'regime': 'continuation', 'align': 1, 'min_body': 0.45, 'rsi_lo': 20, 'rsi_hi': 55, 'max_sl_prev': 25.0, 'sl_style': 'swing2'}`
- `day_unique` SL `prev` T1=10.0 · cal 9@88.89% · l3m 4@100.0% · `{'primaries': ['morning_star', 'evening_star'], 'regime': 'continuation', 'align': 1, 'min_body': 0.55, 'rsi_lo': 20, 'rsi_hi': 55, 'max_sl_prev': 25.0, 'sl_style': 'prev'}`
- `day_unique` SL `swing2` T1=10.0 · cal 9@88.89% · l3m 4@100.0% · `{'primaries': ['morning_star', 'evening_star'], 'regime': 'continuation', 'align': 1, 'min_body': 0.55, 'rsi_lo': 20, 'rsi_hi': 55, 'max_sl_prev': 25.0, 'sl_style': 'swing2'}`
- `day_unique` SL `prev` T1=10.0 · cal 9@88.89% · l3m 4@100.0% · `{'primaries': ['morning_star', 'evening_star'], 'regime': 'continuation', 'align': 1, 'rsi_lo': 20, 'rsi_hi': 55, 'max_sl_prev': 25.0, 'sl_style': 'prev'}`
- `day_unique` SL `swing2` T1=10.0 · cal 9@88.89% · l3m 4@100.0% · `{'primaries': ['morning_star', 'evening_star'], 'regime': 'continuation', 'align': 1, 'rsi_lo': 20, 'rsi_hi': 55, 'max_sl_prev': 25.0, 'sl_style': 'swing2'}`
- `day_unique` SL `prev` T1=10.0 · cal 9@88.89% · l3m 4@100.0% · `{'primaries': ['morning_star', 'evening_star', 'morning_doji_star', 'evening_doji_star'], 'regime': 'continuation', 'align': 1, 'min_body': 0.45, 'rsi_lo': 20, 'rsi_hi': 55, 'max_sl_prev': 25.0, 'sl_style': 'prev'}`
- `day_unique` SL `swing2` T1=10.0 · cal 9@88.89% · l3m 4@100.0% · `{'primaries': ['morning_star', 'evening_star', 'morning_doji_star', 'evening_doji_star'], 'regime': 'continuation', 'align': 1, 'min_body': 0.45, 'rsi_lo': 20, 'rsi_hi': 55, 'max_sl_prev': 25.0, 'sl_style': 'swing2'}`

## Policy

- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_prevcandle_100`
- research_only · not_live · scalp · prev-candle SL · T1 10/20
- **Multi-call 100% follow-up:** [`NIFTY_1M_SCALP_MULTICALL_100.md`](NIFTY_1M_SCALP_MULTICALL_100.md) — path union **187 calls / 64 days @100%** (~2.9/day)

## Deep cell analysis (added)

### Path-win both-100 (T1 before prev-candle stop)

- Cells: **53** · Union days cal **56** · last3m **16**

| T1 | Cal days | L3m days | Med SL | Cell |
|---:|---:|---:|---:|---|
| 10.0 | 11 | 3 | 23.05 | `('three_outside_dn', 'SELL', 'continuation', 1, 'early', 'b45+', 'sl>20', 'rsi_lo')` |
| 10.0 | 5 | 3 | 23.0 | `('marubozu_bull', 'BUY', 'continuation', 0, 'early', 'b45+', 'sl>20', 'rsi_mid')` |
| 10.0 | 4 | 3 | 8.15 | `('marubozu_bear', 'SELL', 'continuation', 1, 'early', 'b45+', 'sl<=10', 'rsi_lo')` |
| 10.0 | 8 | 2 | 13.3 | `('belt_bear', 'SELL', 'balanced', 1, 'midday', 'b45+', 'sl<=15', 'rsi_mid')` |
| 10.0 | 8 | 2 | 22.77 | `('marubozu_bull', 'BUY', 'reversal', 0, 'early', 'b45+', 'sl>20', 'rsi_lo')` |
| 15.0 | 8 | 2 | 22.77 | `('marubozu_bull', 'BUY', 'reversal', 0, 'early', 'b45+', 'sl>20', 'rsi_lo')` |
| 10.0 | 4 | 2 | 11.3 | `('bull_run3', 'BUY', 'balanced', 0, 'morning', 'b<45', 'sl<=15', 'rsi_mid')` |
| 10.0 | 4 | 2 | 16.32 | `('bull_run2', 'BUY', 'reversal', 1, 'morning', 'b<45', 'sl<=20', 'rsi_lo')` |
| 20.0 | 4 | 2 | 16.32 | `('bull_run2', 'BUY', 'reversal', 1, 'morning', 'b<45', 'sl<=20', 'rsi_lo')` |
| 15.0 | 4 | 2 | 16.32 | `('bull_run2', 'BUY', 'reversal', 1, 'morning', 'b<45', 'sl<=20', 'rsi_lo')` |
| 10.0 | 4 | 2 | 21.62 | `('three_outside_dn', 'SELL', 'continuation', 0, 'late', 'b45+', 'sl>20', 'rsi_mid')` |
| 15.0 | 4 | 2 | 21.62 | `('three_outside_dn', 'SELL', 'continuation', 0, 'late', 'b45+', 'sl>20', 'rsi_mid')` |

### Union last3m calls

| Day | HM | Side | Primary | SL | T1 | Win |
|---|---|---|---|---:|---:|:---:|
| 2026-08-31 | 09:24 | SELL | belt_bear | 10.95 | 10.0 | Y |
| 2026-09-07 | 09:24 | SELL | three_outside_dn | 23.05 | 10.0 | Y |
| 2026-09-15 | 09:55 | SELL | three_outside_dn | 23.9 | 10.0 | Y |
| 2026-09-16 | 10:40 | BUY | bull_run3 | 11.05 | 10.0 | Y |
| 2026-09-28 | 12:05 | BUY | tweezer_bot | 13.3 | 10.0 | Y |
| 2026-10-08 | 09:49 | BUY | marubozu_bull | 23.05 | 10.0 | Y |
| 2026-10-09 | 10:11 | BUY | belt_bull | 15.95 | 10.0 | Y |
| 2026-10-12 | 09:51 | SELL | three_outside_dn | 20.55 | 10.0 | Y |
| 2026-10-19 | 10:08 | BUY | marubozu_bull | 22.5 | 10.0 | Y |
| 2026-10-21 | 09:46 | SELL | belt_bear | 20.45 | 10.0 | Y |
| 2026-10-22 | 09:43 | BUY | bull_run3 | 24.2 | 10.0 | Y |
| 2026-10-26 | 11:36 | BUY | bull_run2 | 17.25 | 10.0 | Y |
| 2026-10-28 | 13:28 | BUY | bull_run3 | 22.75 | 10.0 | Y |
| 2026-11-02 | 13:19 | BUY | bull_run3 | 24.45 | 10.0 | Y |
| 2026-11-04 | 10:31 | BUY | bull_run2 | 15.4 | 10.0 | Y |
| 2026-11-05 | 09:38 | BUY | bull_run3 | 23.6 | 10.0 | Y |

### Target-reached only (MFE ≥ T1, SL order ignored)

- Cells where every selected day reached T1: **863**

This matches the insight: if the scalp target always prints, the stop is only structure insurance — accuracy is defined by **target hit**.

| T1 | Cal days | L3m days | Avg prev-SL | Cell |
|---:|---:|---:|---:|---|
| 10.0 | 17 | 11 | 7.13 | `('belt_bear', 'SELL', 'continuation', 1, 'late', 'b45+', 'sl<=10', 'rsi_lo')` |
| 10.0 | 20 | 9 | 7.43 | `('belt_bear', 'SELL', 'reversal', 1, 'midday', 'b45+', 'sl<=10', 'rsi_hi')` |
| 10.0 | 8 | 8 | 17.19 | `('belt_bear', 'SELL', 'continuation', 1, 'late', 'b45+', 'sl<=20', 'rsi_lo')` |
| 20.0 | 8 | 8 | 17.19 | `('belt_bear', 'SELL', 'continuation', 1, 'late', 'b45+', 'sl<=20', 'rsi_lo')` |
| 10.0 | 13 | 7 | 7.29 | `('three_outside_dn', 'SELL', 'balanced', 1, 'midday', 'b45+', 'sl<=10', 'rsi_mid')` |
| 10.0 | 13 | 7 | 6.06 | `('belt_bear', 'SELL', 'continuation', 1, 'late', 'b45+', 'sl<=10', 'rsi_mid')` |
| 20.0 | 13 | 7 | 6.06 | `('belt_bear', 'SELL', 'continuation', 1, 'late', 'b45+', 'sl<=10', 'rsi_mid')` |
| 10.0 | 12 | 7 | 8.57 | `('bull_kicker', 'BUY', 'continuation', 1, 'midday', 'b45+', 'sl<=10', 'rsi_hi')` |
| 10.0 | 10 | 7 | 11.71 | `('bull_run2', 'BUY', 'continuation', 0, 'late', 'b<45', 'sl<=15', 'rsi_mid')` |
| 10.0 | 8 | 7 | 5.76 | `('bear_run3', 'SELL', 'balanced', 0, 'late', 'b<45', 'sl<=10', 'rsi_hi')` |
| 20.0 | 8 | 7 | 5.76 | `('bear_run3', 'SELL', 'balanced', 0, 'late', 'b<45', 'sl<=10', 'rsi_hi')` |
| 10.0 | 3 | 7 | 5.74 | `('belt_bear', 'SELL', 'balanced', 1, 'midday', 'b45+', 'sl<=10', 'rsi_hi')` |

## Target-reached union (MFE≥10 always · prev-candle structure)

- Full union: **121 cal days / 53 last3m days** · 20 micros
- Tight avg prev-SL ≤12: **110 / 46 days** · 16 micros

Best micros (target always prints; SL = prev candle as insurance):

| Cal | L3m | Avg SL | Path-win% | Cell |
|---:|---:|---:|---:|---|
| 17 | 11 | 7.1 | 36 | `('belt_bear', 'SELL', 'continuation', 1, 'late', 'b45+', 'sl<=10', 'rsi_lo')` |
| 8 | 7 | 5.8 | 57 | `('bear_run3', 'SELL', 'balanced', 0, 'late', 'b<45', 'sl<=10', 'rsi_hi')` |
| 10 | 6 | 16.9 | 50 | `('bear_engulf', 'SELL', 'continuation', 1, 'midday', 'b45+', 'sl<=20', 'rsi_lo')` |
| 19 | 5 | 17.0 | 60 | `('bull_run3', 'BUY', 'continuation', 1, 'late', 'b45+', 'sl<=20', 'rsi_hi')` |
| 7 | 2 | 5.1 | 50 | `('bull_run2', 'BUY', 'balanced', 0, 'late', 'b45+', 'sl<=10', 'rsi_lo')` |
| 5 | 2 | 5.4 | 50 | `('bear_engulf', 'SELL', 'reversal', 1, 'morning', 'b<45', 'sl<=10', 'rsi_hi')` |
| 8 | 2 | 6.7 | 50 | `('three_outside_up', 'BUY', 'balanced', 1, 'midday', 'b<45', 'sl<=10', 'rsi_hi')` |
| 3 | 2 | 7.2 | 50 | `('bull_kicker', 'BUY', 'continuation', 1, 'late', 'b45+', 'sl<=10', 'rsi_mid')` |
| 4 | 2 | 7.9 | 100 | `('bull_engulf', 'BUY', 'reversal', 1, 'late', 'b<45', 'sl<=10', 'rsi_lo')` |
| 5 | 2 | 9.5 | 50 | `('three_crows', 'SELL', 'continuation', 1, 'morning', 'b45+', 'sl<=10', 'rsi_lo')` |
| 3 | 2 | 10.7 | 100 | `('bull_run2', 'BUY', 'balanced', 1, 'late', 'b<45', 'sl<=15', 'rsi_mid')` |
| 4 | 2 | 12.9 | 50 | `('three_outside_dn', 'SELL', 'balanced', 1, 'late', 'b45+', 'sl<=15', 'rsi_lo')` |

### Example tight champion cell

`belt_bear` SELL · continuation · align · late · body≥0.45 · prev-SL≤10 · RSI low

| Day | HM | Side | PrevSL | MFE | Path T1 before SL |
|---|---|---|---:|---:|---|
| 2026-08-06 | 14:55 | SELL | 6.4 | 102.4 | sl |
| 2026-08-07 | 14:11 | SELL | 10.0 | 20.4 | sl |
| 2026-08-13 | 14:45 | SELL | 7.7 | 53.2 | win |
| 2026-08-19 | 14:19 | SELL | 9.8 | 14.0 | win |
| 2026-08-31 | 14:02 | SELL | 8.0 | 29.7 | win |
| 2026-09-01 | 14:21 | SELL | 7.8 | 172.7 | sl |
| 2026-09-03 | 14:43 | SELL | 5.3 | 31.8 | sl |
| 2026-09-10 | 14:08 | SELL | 5.5 | 185.2 | sl |
| 2026-09-28 | 14:26 | SELL | 4.0 | 229.8 | sl |
| 2026-10-12 | 14:33 | SELL | 8.2 | 41.4 | win |
| 2026-10-21 | 14:49 | SELL | 5.7 | 108.5 | sl |


## Deep structure · lesser SL + candle geometry

Exit variants vs previous-candle stop:

| Style | Meaning |
|---|---|
| `prev` | Prior bar low/high |
| `sig` | Signal candle extreme |
| `min_prev_sig` | Tighter of prev vs signal |
| `cap8/10/12` | `min(prev, cap)` — lesser SL |
| `pct75/60` | 75%/60% of prev distance |

- **Path both-100 union**: 38 cal / **21 last3m** days · 9 micros
- **Path tight (avg SL≤12)**: 41 / **20** · 9 micros
- **Target-reached (MFE) union**: 84 / **54** · 15 micros
- **MFE tight**: 84 / **54** · 15 micros
- Geometry-only path-100 cells: **27** · MFE tight: **4132**

### Path-perfect champions (T1 before lesser/structure SL)

| Cal | L3m | AvgSL | Exit | Cell |
|---:|---:|---:|---|---|
| 3 | 4 | 12.0 | `cap12_t10` | `('GEOM', 'SELL', 'balanced', 0, 'early', 'body70+', 'sl12-16', 'rsi_lo', 'rng>atr', 'pre_flat')` |
| 6 | 3 | 7.9 | `sig_t10` | `('GEOM', 'BUY', 'continuation', 1, 'midday', 'body45+', 'sl12-16', 'rsi_mid', 'rng>atr', 'pre_med')` |
| 4 | 2 | 4.0 | `pct75_t10` | `('bear_run3', 'SELL', 'continuation', 1, 'midday', 'body55+', 'sl4-8', 'rsi_lo', 'rng_small', 'pre_med')` |
| 4 | 2 | 4.1 | `min_prev_sig_t10` | `('bear_run3', 'SELL', 'continuation', 1, 'midday', 'body55+', 'sl4-8', 'rsi_lo', 'rng_small', 'pre_med')` |
| 4 | 2 | 4.1 | `cap8_t10` | `('bear_run3', 'SELL', 'continuation', 1, 'midday', 'body55+', 'sl4-8', 'rsi_lo', 'rng_small', 'pre_med')` |
| 4 | 2 | 4.1 | `cap10_t10` | `('bear_run3', 'SELL', 'continuation', 1, 'midday', 'body55+', 'sl4-8', 'rsi_lo', 'rng_small', 'pre_med')` |
| 4 | 2 | 4.1 | `cap12_t10` | `('bear_run3', 'SELL', 'continuation', 1, 'midday', 'body55+', 'sl4-8', 'rsi_lo', 'rng_small', 'pre_med')` |
| 4 | 2 | 6.0 | `prev_t10` | `('GEOM', 'BUY', 'reversal', 1, 'late', 'body<45', 'sl4-8', 'rsi_lo', 'rng>atr', 'pre_strong')` |
| 3 | 2 | 6.3 | `pct60_t10` | `('belt_bear', 'SELL', 'balanced', 1, 'morning', 'body70+', 'sl8-12', 'rsi_lo', 'rng>atr', 'pre_flat')` |
| 5 | 2 | 6.6 | `pct75_t10` | `('bull_run3', 'BUY', 'continuation', 1, 'late', 'body70+', 'sl8-12', 'rsi_hi', 'rng>atr', 'pre_strong')` |
| 4 | 2 | 7.3 | `pct75_t10` | `('bull_run3', 'BUY', 'continuation', 1, 'late', 'body<45', 'sl8-12', 'rsi_mid', 'rng>atr', 'pre_med')` |
| 3 | 2 | 7.9 | `min_prev_sig_t10` | `('three_outside_dn', 'SELL', 'continuation', 1, 'midday', 'body<45', 'sl8-12', 'rsi_mid', 'rng>atr', 'pre_med')` |
| 3 | 2 | 7.9 | `min_prev_sig_t20` | `('three_outside_dn', 'SELL', 'continuation', 1, 'midday', 'body<45', 'sl8-12', 'rsi_mid', 'rng>atr', 'pre_med')` |
| 3 | 2 | 7.9 | `pct75_t10` | `('belt_bear', 'SELL', 'balanced', 1, 'morning', 'body70+', 'sl8-12', 'rsi_lo', 'rng>atr', 'pre_flat')` |
| 3 | 2 | 8.0 | `min_prev_sig_t10` | `('belt_bear', 'SELL', 'balanced', 1, 'morning', 'body70+', 'sl8-12', 'rsi_lo', 'rng>atr', 'pre_flat')` |

### Target-always champions (MFE≥T1 · tight SL ≤12 · SL = insurance)

| Cal | L3m | AvgSL | Path% | Exit | Cell |
|---:|---:|---:|---:|---|---|
| 4 | 8 | 4.0 | 38 | `pct60_t10` | `('GEOM', 'BUY', 'continuation', 0, 'early', 'body<45', 'sl4-8', 'rsi_mid', 'rng>0.7atr', 'pre_med')` |
| 24 | 8 | 4.2 | 25 | `pct60_t10` | `('GEOM', 'SELL', 'continuation', 1, 'late', 'body<45', 'sl4-8', 'rsi_mid', 'rng>0.7atr', 'pre_med')` |
| 11 | 8 | 4.4 | 12 | `pct60_t10` | `('GEOM', 'SELL', 'continuation', 1, 'morning', 'body70+', 'sl4-8', 'rsi_lo', 'rng>atr', 'pre_med')` |
| 4 | 8 | 4.4 | 38 | `pct75_t10` | `('GEOM', 'BUY', 'continuation', 0, 'early', 'body<45', 'sl4-8', 'rsi_mid', 'rng>0.7atr', 'pre_med')` |
| 24 | 8 | 4.7 | 25 | `pct75_t10` | `('GEOM', 'SELL', 'continuation', 1, 'late', 'body<45', 'sl4-8', 'rsi_mid', 'rng>0.7atr', 'pre_med')` |
| 11 | 8 | 5.3 | 38 | `pct75_t10` | `('GEOM', 'SELL', 'continuation', 1, 'morning', 'body70+', 'sl4-8', 'rsi_lo', 'rng>atr', 'pre_med')` |
| 4 | 8 | 5.6 | 38 | `prev_t10` | `('GEOM', 'BUY', 'continuation', 0, 'early', 'body<45', 'sl4-8', 'rsi_mid', 'rng>0.7atr', 'pre_med')` |
| 4 | 8 | 5.6 | 38 | `min_prev_sig_t10` | `('GEOM', 'BUY', 'continuation', 0, 'early', 'body<45', 'sl4-8', 'rsi_mid', 'rng>0.7atr', 'pre_med')` |
| 4 | 8 | 5.6 | 38 | `cap8_t10` | `('GEOM', 'BUY', 'continuation', 0, 'early', 'body<45', 'sl4-8', 'rsi_mid', 'rng>0.7atr', 'pre_med')` |
| 4 | 8 | 5.6 | 38 | `cap10_t10` | `('GEOM', 'BUY', 'continuation', 0, 'early', 'body<45', 'sl4-8', 'rsi_mid', 'rng>0.7atr', 'pre_med')` |
| 4 | 8 | 5.6 | 38 | `cap12_t10` | `('GEOM', 'BUY', 'continuation', 0, 'early', 'body<45', 'sl4-8', 'rsi_mid', 'rng>0.7atr', 'pre_med')` |
| 24 | 8 | 5.7 | 25 | `min_prev_sig_t10` | `('GEOM', 'SELL', 'continuation', 1, 'late', 'body<45', 'sl4-8', 'rsi_mid', 'rng>0.7atr', 'pre_med')` |
| 24 | 8 | 6.0 | 50 | `prev_t10` | `('GEOM', 'SELL', 'continuation', 1, 'late', 'body<45', 'sl4-8', 'rsi_mid', 'rng>0.7atr', 'pre_med')` |
| 24 | 8 | 6.0 | 38 | `cap8_t10` | `('GEOM', 'SELL', 'continuation', 1, 'late', 'body<45', 'sl4-8', 'rsi_mid', 'rng>0.7atr', 'pre_med')` |
| 24 | 8 | 6.0 | 38 | `cap10_t10` | `('GEOM', 'SELL', 'continuation', 1, 'late', 'body<45', 'sl4-8', 'rsi_mid', 'rng>0.7atr', 'pre_med')` |

### Example path-perfect tight book (last3m)

| Day | HM | Side | Pattern | SL style | SL | T1 |
|---|---|---|---|---|---:|---:|
| 2026-08-07 | 10:11 | SELL | marubozu_bear | `cap12` | 12.0 | 10 |
| 2026-09-21 | 10:25 | SELL | belt_bear | `cap12` | 12.0 | 10 |
| 2026-09-25 | 09:52 | SELL | bear_run2 | `cap12` | 12.0 | 10 |
| 2026-10-13 | 10:25 | SELL | marubozu_bear | `cap12` | 12.0 | 10 |
| 2026-08-19 | 12:11 | SELL | bear_run3 | `pct75` | 4.0 | 10 |
| 2026-08-25 | 12:48 | SELL | bear_run3 | `pct75` | 4.0 | 10 |
| 2026-10-15 | 14:42 | BUY | hammer | `prev` | 4.5 | 10 |
| 2026-10-30 | 14:02 | BUY | bull_engulf | `prev` | 7.5 | 10 |
| 2026-10-06 | 14:40 | BUY | bull_run3 | `pct75` | 7.5 | 10 |
| 2026-10-16 | 14:44 | BUY | bull_run3 | `pct75` | 7.1 | 10 |
| 2026-08-06 | 12:49 | SELL | three_outside_dn | `min_prev_sig` | 7.2 | 10 |
| 2026-09-10 | 13:30 | SELL | three_outside_dn | `min_prev_sig` | 8.6 | 10 |
| 2026-10-05 | 10:32 | BUY | bull_run3 | `pct60` | 8.1 | 10 |
| 2026-10-07 | 10:42 | BUY | bull_run3 | `pct60` | 8.4 | 10 |
| 2026-08-28 | 14:17 | BUY | bull_run2 | `prev` | 8.2 | 10 |
| 2026-09-24 | 14:52 | BUY | bull_run3 | `prev` | 9.1 | 10 |
| 2026-09-28 | 11:34 | SELL | three_outside_dn | `cap10` | 10.0 | 10 |
| 2026-10-23 | 11:42 | SELL | three_outside_dn | `cap10` | 10.0 | 10 |
| 2026-08-18 | 11:32 | BUY | bull_run2 | `prev` | 11.1 | 10 |
| 2026-09-29 | 11:06 | BUY | bull_engulf | `prev` | 10.0 | 10 |

### Geometry-only path-100 (no pattern name)

| Cal | L3m | AvgSL | Exit | Structure |
|---:|---:|---:|---|---|
| 3 | 4 | 12.0 | `cap12_t10` | `('GEOM', 'SELL', 'balanced', 0, 'early', 'body70+', 'sl12-16', 'rsi_lo', 'rng>atr', 'pre_flat')` |
| 6 | 3 | 7.9 | `sig_t10` | `('GEOM', 'BUY', 'continuation', 1, 'midday', 'body45+', 'sl12-16', 'rsi_mid', 'rng>atr', 'pre_med')` |
| 6 | 3 | 13.4 | `prev_t10` | `('GEOM', 'BUY', 'continuation', 1, 'midday', 'body45+', 'sl12-16', 'rsi_mid', 'rng>atr', 'pre_med')` |
| 4 | 2 | 6.0 | `prev_t10` | `('GEOM', 'BUY', 'reversal', 1, 'late', 'body<45', 'sl4-8', 'rsi_lo', 'rng>atr', 'pre_strong')` |
| 3 | 2 | 8.0 | `sig_t10` | `('GEOM', 'SELL', 'reversal', 1, 'midday', 'body55+', 'sl12-16', 'rsi_mid', 'rng>0.7atr', 'pre_strong')` |
| 7 | 2 | 8.2 | `pct60_t10` | `('GEOM', 'BUY', 'continuation', 0, 'morning', 'body<45', 'sl12-16', 'rsi_mid', 'rng_small', 'pre_strong')` |
| 5 | 2 | 8.5 | `sig_t10` | `('GEOM', 'SELL', 'continuation', 0, 'midday', 'body55+', 'sl8-12', 'rsi_lo', 'rng>atr', 'pre_flat')` |
| 4 | 2 | 8.7 | `prev_t10` | `('GEOM', 'BUY', 'continuation', 0, 'late', 'body<45', 'sl8-12', 'rsi_mid', 'rng_small', 'pre_flat')` |
| 5 | 2 | 8.9 | `prev_t10` | `('GEOM', 'SELL', 'continuation', 0, 'midday', 'body55+', 'sl8-12', 'rsi_lo', 'rng>atr', 'pre_flat')` |
| 7 | 2 | 10.0 | `cap10_t10` | `('GEOM', 'BUY', 'continuation', 0, 'morning', 'body<45', 'sl12-16', 'rsi_mid', 'rng_small', 'pre_strong')` |


## Oracle coverage (path T1=10 · structure SL in 4–12)

If some entry that day can win with tight structure stop:

| Window | Days | Any style | Prev | Cap10 | Cap8 | MFE≥10 & SL≤12 |
|---|---:|---:|---:|---:|---:|---:|
| cal | 271 | 271 | 271 | 271 | 271 | 271 |
| l3m | 64 | 64 | 64 | 64 | 64 | 64 |


## Non-lookahead structure picker

- Calibrate path-100 templates (avg SL≤12): **3855**
- **Perfect both-100 picker**: top **1** templates → cal **22** / last3m **3** days @100%

| Day | HM | Side | Pattern | SL style | SL |
|---|---|---|---|---|---:|
| 2026-08-10 | 12:13 | BUY | marubozu_bull | `sig` | 6.5 |
| 2026-09-16 | 12:10 | BUY | morning_star | `sig` | 11.7 |
| 2026-09-25 | 13:59 | BUY | marubozu_bull | `sig` | 10.2 |

### Playbook (tight scalp · T1=10 · structure SL)

1. **Oracle fact**: every cal & last3m day has ≥1 path-win with SL in 4–12 (even `cap8`).
2. **Target-as-win**: MFE≥10 cells densest — `belt_bear` late continuation align body45+ prev-SL≤10 RSI low (~11 last3m days alone).
3. **Path-perfect tight**: `bear_run3` SELL · continuation · align · midday · body55+ · prev-SL 4–8 · RSI low · small range · med pre-move · exit `pct75`/`cap8` (~4 pts).
4. **Geometry-only path-100**: BUY continuation align midday body45+ sl12-16 RSI mid rng>atr pre_med · prefer **signal-candle** SL (~7.9).
5. Stop = previous candle extreme, or **lesser**: `min(prev, 8/10)` / 75% of prev.
