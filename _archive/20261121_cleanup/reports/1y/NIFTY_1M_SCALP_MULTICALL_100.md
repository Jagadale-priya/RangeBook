# NIFTY 1m — **scalp multi-call 100%**

**Not live.** Maximize number of scalping calls with **100%** on calibrate + last3m.

- T1 **10** (also tested 20) · SL = prev candle or lesser (`cap8/10/12`, signal, `0.75×prev`)
- Multi-call gap **15** min · SL band **4–12**
- **Champion = PATH** (T1 hits before structure SL) — real scalp fill logic
- MFE book = target always prints (SL as insurance only; path-win ~40%)

## ★ PATH multi-call champion (both windows 100%)

- **Calibrate: 357 calls / 201 days** · 1.78/day · 106 multi-call days
- **Last3m: 187 calls / 64 days** · **2.92/day** · **51 multi-call days** · max **8/day** · avg SL **8.6**
- **78 structure micros** · T1=10 before prev/sig/cap SL
- Oracle ceiling ~21 path-wins/day → this book is non-lookahead structure union

Top path micros: `bear_engulf` early balanced body70+; GEOM BUY/SELL reversal morning/early; `bear_run2` early reversal SL4–8 (~5 pts).

## Sparse single-micro PATH (reference)

- Gap **10** min · seed `sig_t10`
- Calibrate: **6 calls / 6 days** · 1.0/day · multi-days 0
- Last3m: **3 calls / 3 days** · 1.0/day · multi-days 0 · max/day 1 · avg SL 7.95
- Micros used: **1**

### Micros

| Cal | L3m | AvgSL | Exit | Cell |
|---:|---:|---:|---|---|
| 6 | 3 | 7.95 | `sig_t10` | `('GEOM', 'BUY', 'continuation', 1, 'midday', 'b45+', 'sl12-16', 'mid', 'r>atr', 'p_med')` |

### Last3m calls

| Day | HM | Side | Pattern | SL style | SL | T1 |
|---|---|---|---|---|---:|---:|
| 2026-10-16 | 12:10 | BUY | bull_run3 | `sig` | 8.25 | 10.0 |
| 2026-11-02 | 12:09 | BUY | bull_run2 | `sig` | 8.4 | 10.0 |
| 2026-11-03 | 12:52 | BUY | bull_run2 | `sig` | 7.2 | 10.0 |

## Best TARGET-REACHED multi-call book (MFE≥T1 · both 100%)

- Gap **10** · seed `cap8_t10`
- Calibrate: **1246 calls / 268 days** · 4.65/day · multi-days 254
- Last3m: **561 calls / 64 days** · 8.77/day · multi-days 64 · max/day 13 · avg SL 7.08 · path-win 40.6%

### Top micros

| Cal | L3m | AvgSL | Path% | Exit | Cell |
|---:|---:|---:|---:|---|---|
| 13 | 9 | 8.0 | 55.6 | `cap8_t10` | `('GEOM', 'SELL', 'balanced', 1, 'late', 'b55+', 'sl8-12', 'mid', 'r>atr', 'p_flat')` |
| 25 | 6 | 6.04 | 37.5 | `cap8_t10` | `('GEOM', 'SELL', 'continuation', 1, 'late', 'b<45', 'sl4-8', 'mid', 'r>0.7a', 'p_med')` |
| 14 | 8 | 5.26 | 25.0 | `cap8_t10` | `('GEOM', 'SELL', 'continuation', 0, 'midday', 'b<45', 'sl4-8', 'lo', 'r>0.7a', 'p_str')` |
| 9 | 8 | 8.0 | 50.0 | `cap8_t10` | `('GEOM', 'SELL', 'reversal', 1, 'early', 'b70+', 'sl8-12', 'mid', 'r>atr', 'p_med')` |
| 4 | 8 | 5.62 | 37.5 | `cap8_t10` | `('GEOM', 'BUY', 'continuation', 0, 'early', 'b<45', 'sl4-8', 'mid', 'r>0.7a', 'p_med')` |
| 11 | 7 | 8.0 | 42.9 | `cap8_t10` | `('GEOM', 'SELL', 'continuation', 1, 'morning', 'b70+', 'sl16-20', 'lo', 'r>atr', 'p_med')` |
| 10 | 7 | 8.0 | 28.6 | `cap8_t10` | `('GEOM', 'BUY', 'continuation', 1, 'midday', 'b55+', 'sl12-16', 'hi', 'r>atr', 'p_str')` |
| 8 | 7 | 5.32 | 14.3 | `cap8_t10` | `('GEOM', 'SELL', 'continuation', 0, 'late', 'b<45', 'sl4-8', 'mid', 'r>atr', 'p_med')` |
| 7 | 7 | 6.17 | 14.3 | `cap8_t10` | `('GEOM', 'SELL', 'reversal', 1, 'early', 'b70+', 'sl4-8', 'mid', 'r>0.7a', 'p_med')` |
| 21 | 6 | 8.0 | 50.0 | `cap8_t10` | `('GEOM', 'SELL', 'continuation', 1, 'midday', 'b55+', 'sl12-16', 'lo', 'r>atr', 'p_str')` |
| 13 | 6 | 6.64 | 50.0 | `cap8_t10` | `('bear_engulf', 'SELL', 'balanced', 1, 'midday', 'b55+', 'sl4-8', 'mid', 'r>atr', 'p_flat')` |
| 9 | 4 | 5.31 | 66.7 | `cap8_t10` | `('GEOM', 'SELL', 'continuation', 1, 'midday', 'b45+', 'sl4-8', 'mid', 'r>atr', 'p_flat')` |
| 9 | 6 | 8.0 | 50.0 | `cap8_t10` | `('marubozu_bear', 'SELL', 'continuation', 1, 'morning', 'b70+', 'sl12-16', 'mid', 'r>atr', 'p_med')` |
| 7 | 6 | 5.31 | 50.0 | `cap8_t10` | `('GEOM', 'SELL', 'continuation', 1, 'midday', 'b45+', 'sl4-8', 'mid', 'r_sm', 'p_med')` |
| 8 | 6 | 8.0 | 16.7 | `cap8_t10` | `('GEOM', 'SELL', 'continuation', 1, 'morning', 'b70+', 'sl8-12', 'lo', 'r>atr', 'p_flat')` |
| 5 | 6 | 8.0 | 50.0 | `cap8_t10` | `('three_outside_dn', 'SELL', 'balanced', 1, 'midday', 'b70+', 'sl8-12', 'mid', 'r>atr', 'p_flat')` |
| 6 | 6 | 8.0 | 33.3 | `cap8_t10` | `('GEOM', 'BUY', 'continuation', 1, 'late', 'b<45', 'sl8-12', 'hi', 'r>atr', 'p_str')` |
| 6 | 6 | 8.0 | 50.0 | `cap8_t10` | `('bear_engulf', 'SELL', 'reversal', 1, 'midday', 'b70+', 'sl16-20', 'mid', 'r>atr', 'p_str')` |
| 19 | 3 | 5.62 | 80.0 | `cap8_t10` | `('GEOM', 'SELL', 'reversal', 1, 'midday', 'b55+', 'sl4-8', 'mid', 'r>0.7a', 'p_med')` |
| 16 | 5 | 8.0 | 40.0 | `cap8_t10` | `('GEOM', 'BUY', 'balanced', 1, 'morning', 'b<45', 'sl8-12', 'mid', 'r>0.7a', 'p_flat')` |

### Last3m sample calls

| Day | HM | Side | Pattern | SL | T1 | MFE |
|---|---|---|---|---:|---:|---:|
| 2026-08-06 | 09:31 | SELL | bear_engulf | 8.0 | 10.0 | 30.8 |
| 2026-08-06 | 09:45 | BUY | bull_run3 | 8.0 | 10.0 | 28.1 |
| 2026-08-06 | 09:59 | SELL | belt_bear | 8.0 | 10.0 | 30.4 |
| 2026-08-06 | 10:15 | SELL | belt_bear | 8.0 | 10.0 | 11.0 |
| 2026-08-06 | 10:40 | SELL | bear_run2 | 8.0 | 10.0 | 19.1 |
| 2026-08-06 | 11:15 | BUY | bull_run3 | 5.75 | 10.0 | 22.5 |
| 2026-08-06 | 12:48 | SELL | bear_engulf | 7.85 | 10.0 | 32.1 |
| 2026-08-06 | 13:36 | BUY | bull_run2 | 8.0 | 10.0 | 10.0 |
| 2026-08-06 | 13:57 | SELL | bear_run3 | 4.9 | 10.0 | 98.5 |
| 2026-08-06 | 14:09 | SELL | bear_run2 | 7.15 | 10.0 | 120.0 |
| 2026-08-06 | 14:37 | SELL | three_outside_dn | 5.5 | 10.0 | 118.9 |
| 2026-08-06 | 14:52 | SELL | bear_run3 | 5.3 | 10.0 | 110.7 |
| 2026-08-07 | 09:37 | SELL | bear_engulf | 6.0 | 10.0 | 49.2 |
| 2026-08-07 | 10:39 | BUY | bull_kicker | 8.0 | 10.0 | 16.8 |
| 2026-08-07 | 11:06 | BUY | bull_run2 | 8.0 | 10.0 | 25.9 |
| 2026-08-07 | 13:10 | SELL | belt_bear | 8.0 | 10.0 | 31.6 |
| 2026-08-07 | 13:23 | BUY | bull_run2 | 8.0 | 10.0 | 28.8 |
| 2026-08-07 | 13:50 | BUY | bull_run3 | 8.0 | 10.0 | 42.2 |
| 2026-08-07 | 14:11 | SELL | belt_bear | 8.0 | 10.0 | 20.4 |
| 2026-08-07 | 14:35 | SELL | bear_run2 | 6.35 | 10.0 | 32.2 |
| 2026-08-07 | 14:59 | SELL | bear_engulf | 4.95 | 10.0 | 31.1 |
| 2026-08-10 | 09:29 | SELL | bear_run3 | 8.0 | 10.0 | 42.5 |
| 2026-08-10 | 09:47 | BUY | belt_bull | 8.0 | 10.0 | 84.9 |
| 2026-08-10 | 10:00 | BUY | bull_run2 | 6.95 | 10.0 | 77.5 |
| 2026-08-10 | 10:32 | SELL | bear_engulf | 6.85 | 10.0 | 19.6 |
| 2026-08-10 | 10:50 | SELL | bear_run2 | 8.0 | 10.0 | 22.0 |
| 2026-08-10 | 11:20 | BUY | bull_run2 | 8.0 | 10.0 | 14.8 |
| 2026-08-10 | 11:30 | SELL | marubozu_bear | 8.0 | 10.0 | 22.7 |
| 2026-08-10 | 12:05 | SELL | bear_engulf | 4.35 | 10.0 | 20.6 |
| 2026-08-10 | 12:46 | SELL | bear_run3 | 4.2 | 10.0 | 32.9 |
| 2026-08-10 | 13:35 | BUY | bull_run3 | 4.1 | 10.0 | 11.2 |
| 2026-08-10 | 13:46 | SELL | bear_engulf | 5.9 | 10.0 | 125.8 |
| 2026-08-10 | 14:09 | SELL | bear_run2 | 7.5 | 10.0 | 133.8 |
| 2026-08-10 | 14:33 | SELL | bear_run3 | 4.65 | 10.0 | 120.6 |
| 2026-08-11 | 09:40 | SELL | bear_run2 | 8.0 | 10.0 | 42.5 |
| 2026-08-11 | 09:52 | SELL | evening_star | 6.05 | 10.0 | 34.6 |
| 2026-08-11 | 10:06 | SELL | bear_run3 | 8.0 | 10.0 | 48.9 |
| 2026-08-11 | 10:46 | SELL | bear_run3 | 6.6 | 10.0 | 39.0 |
| 2026-08-11 | 11:25 | SELL | bear_engulf | 4.4 | 10.0 | 13.9 |
| 2026-08-11 | 11:48 | BUY | bull_run3 | 4.65 | 10.0 | 21.0 |

## Policy

- research_only · not_live · multi-scalp · structure SL
- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_multicall_100`
- Source events: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_prevcandle_100`



## Dense PATH multi-call (min_l3m=2 · SL≤12 · gap=15)

- Both-100 path micros: **153**
- Union: cal **357 calls / 201 days** (1.78/day, multi-days 106)
- Union: last3m **187 calls / 64 days** (2.92/day, multi-days 51, max/day 8) · avg SL **8.6** · micros **78**

### Path micros (multi-capable)

| Cal | L3m | AvgSL | Exit | Cell |
|---:|---:|---:|---|---|
| 5 | 6 | 9.8 | `prev` | `('bear_engulf', 'SELL', 'balanced', 1, 'early', 'b70+', 'sl8-12', 'mid', 'r>atr', 'p_flat')` |
| 7 | 5 | 10.3 | `prev` | `('GEOM', 'BUY', 'reversal', 1, 'morning', 'b<45', 'sl8-12', 'mid', 'r>0.7a', 'p_med')` |
| 7 | 4 | 10.0 | `prev` | `('GEOM', 'SELL', 'reversal', 1, 'early', 'b70+', 'sl8-12', 'mid', 'r>0.7a', 'p_med')` |
| 5 | 4 | 7.4 | `sig` | `('GEOM', 'BUY', 'balanced', 0, 'early', 'b70+', 'sl8-12', 'hi', 'r>atr', 'p_flat')` |
| 5 | 4 | 10.2 | `prev` | `('GEOM', 'BUY', 'balanced', 0, 'early', 'b70+', 'sl8-12', 'hi', 'r>atr', 'p_flat')` |
| 4 | 4 | 5.0 | `prev` | `('bear_run2', 'SELL', 'reversal', 1, 'early', 'b<45', 'sl4-8', 'mid', 'r>0.7a', 'p_med')` |
| 4 | 4 | 9.4 | `prev` | `('bear_run3', 'SELL', 'balanced', 1, 'morning', 'b70+', 'sl8-12', 'lo', 'r>atr', 'p_flat')` |
| 4 | 4 | 11.0 | `prev` | `('bull_run2', 'BUY', 'continuation', 0, 'late', 'b<45', 'sl8-12', 'mid', 'r>0.7a', 'p_med')` |
| 4 | 4 | 11.2 | `prev` | `('marubozu_bear', 'SELL', 'continuation', 0, 'morning', 'b70+', 'sl8-12', 'mid', 'r>atr', 'p_med')` |
| 3 | 4 | 12.0 | `cap12` | `('GEOM', 'SELL', 'balanced', 0, 'early', 'b70+', 'sl12-16', 'lo', 'r>atr', 'p_flat')` |
| 8 | 3 | 6.5 | `sig` | `('GEOM', 'SELL', 'continuation', 1, 'midday', 'b70+', 'sl4-8', 'lo', 'r>atr', 'p_str')` |
| 8 | 3 | 7.6 | `prev` | `('GEOM', 'SELL', 'continuation', 1, 'midday', 'b70+', 'sl4-8', 'lo', 'r>atr', 'p_str')` |
| 8 | 3 | 8.7 | `prev` | `('GEOM', 'SELL', 'reversal', 1, 'early', 'b<45', 'sl8-12', 'mid', 'r>0.7a', 'p_str')` |
| 8 | 3 | 10.0 | `sig` | `('GEOM', 'BUY', 'reversal', 1, 'morning', 'b70+', 'sl8-12', 'lo', 'r>atr', 'p_str')` |
| 6 | 3 | 7.9 | `sig` | `('GEOM', 'BUY', 'continuation', 1, 'midday', 'b45+', 'sl12-16', 'mid', 'r>atr', 'p_med')` |
| 6 | 3 | 8.0 | `sig` | `('bull_run2', 'BUY', 'balanced', 0, 'midday', 'b70+', 'sl12-16', 'mid', 'r>atr', 'p_flat')` |
| 6 | 3 | 10.6 | `sig` | `('bear_run3', 'SELL', 'continuation', 1, 'late', 'b70+', 'sl8-12', 'lo', 'r>atr', 'p_med')` |
| 6 | 3 | 10.6 | `prev` | `('bull_run2', 'BUY', 'reversal', 1, 'morning', 'b<45', 'sl8-12', 'mid', 'r>0.7a', 'p_med')` |
| 6 | 3 | 11.3 | `prev` | `('bear_run3', 'SELL', 'continuation', 1, 'late', 'b70+', 'sl8-12', 'lo', 'r>atr', 'p_med')` |
| 5 | 3 | 11.0 | `prev` | `('GEOM', 'SELL', 'continuation', 1, 'early', 'b55+', 'sl8-12', 'mid', 'r>0.7a', 'p_med')` |

### Last3m path union calls

| Day | HM | Side | Pattern | SL style | SL |
|---|---|---|---|---|---:|
| 2026-08-06 | 09:38 | BUY | bull_kicker | `prev` | 8.0 |
| 2026-08-06 | 09:59 | SELL | belt_bear | `sig` | 9.5 |
| 2026-08-06 | 10:15 | SELL | belt_bear | `prev` | 9.0 |
| 2026-08-06 | 11:02 | SELL | bear_run2 | `prev` | 7.9 |
| 2026-08-06 | 11:54 | SELL | bear_run2 | `prev` | 5.5 |
| 2026-08-06 | 12:49 | SELL | three_outside_dn | `min_ps` | 7.2 |
| 2026-08-06 | 13:14 | SELL | belt_bear | `prev` | 8.2 |
| 2026-08-06 | 14:28 | SELL | bear_run2 | `prev` | 5.8 |
| 2026-08-07 | 10:11 | SELL | marubozu_bear | `cap12` | 12.0 |
| 2026-08-07 | 11:06 | BUY | bull_run2 | `prev` | 10.5 |
| 2026-08-07 | 11:47 | SELL | marubozu_bear | `prev` | 11.3 |
| 2026-08-07 | 12:13 | SELL | bear_run3 | `prev` | 8.4 |
| 2026-08-10 | 11:37 | BUY | bull_run2 | `prev` | 11.2 |
| 2026-08-10 | 12:18 | SELL | bear_run2 | `prev` | 6.3 |
| 2026-08-10 | 13:19 | BUY | bull_engulf | `prev` | 5.5 |
| 2026-08-11 | 09:54 | SELL | bear_engulf | `prev` | 9.4 |
| 2026-08-11 | 10:40 | SELL | bear_run3 | `prev` | 6.0 |
| 2026-08-11 | 11:09 | SELL | bear_run3 | `prev` | 9.2 |
| 2026-08-11 | 12:34 | BUY | bull_run3 | `prev` | 4.5 |
| 2026-08-11 | 13:25 | BUY | bull_run2 | `sig` | 5.4 |
| 2026-08-12 | 10:27 | SELL | bear_engulf | `prev` | 9.5 |
| 2026-08-13 | 10:07 | SELL | bear_engulf | `prev` | 8.1 |
| 2026-08-13 | 11:30 | BUY | bull_run2 | `prev` | 9.3 |
| 2026-08-14 | 10:07 | BUY | marubozu_bull | `sig` | 8.8 |
| 2026-08-14 | 11:19 | BUY | bull_run3 | `prev` | 8.2 |
| 2026-08-17 | 09:52 | SELL | bear_run2 | `prev` | 4.5 |
| 2026-08-17 | 11:50 | BUY | marubozu_bull | `prev` | 11.2 |
| 2026-08-17 | 14:17 | BUY | bull_run2 | `prev` | 8.4 |
| 2026-08-18 | 10:55 | SELL | bear_engulf | `prev` | 8.0 |
| 2026-08-18 | 11:32 | BUY | bull_run2 | `prev` | 11.1 |
| 2026-08-18 | 13:09 | BUY | bull_run3 | `prev` | 5.0 |
| 2026-08-19 | 10:15 | SELL | bear_engulf | `sig` | 10.8 |
| 2026-08-19 | 12:11 | SELL | bear_run3 | `p75` | 4.0 |
| 2026-08-19 | 13:16 | SELL | bear_run3 | `prev` | 8.3 |
| 2026-08-20 | 10:23 | BUY | bull_run3 | `prev` | 5.4 |
| 2026-08-21 | 10:22 | BUY | marubozu_bull | `sig` | 5.8 |
| 2026-08-21 | 11:52 | SELL | bear_run2 | `prev` | 8.2 |
| 2026-08-24 | 10:48 | SELL | bear_run3 | `prev` | 4.1 |
| 2026-08-24 | 11:22 | SELL | bear_run3 | `prev` | 9.8 |
| 2026-08-24 | 12:18 | SELL | belt_bear | `prev` | 5.5 |
| 2026-08-24 | 13:48 | SELL | belt_bear | `prev` | 7.1 |
| 2026-08-25 | 09:24 | SELL | bear_engulf | `prev` | 11.6 |
| 2026-08-25 | 09:51 | SELL | bear_run3 | `sig` | 6.2 |
| 2026-08-25 | 12:05 | SELL | belt_bear | `prev` | 9.1 |
| 2026-08-25 | 12:21 | SELL | bear_engulf | `sig` | 5.1 |
| 2026-08-25 | 12:48 | SELL | bear_run3 | `p75` | 4.0 |
| 2026-08-26 | 10:16 | SELL | bear_engulf | `prev` | 11.6 |
| 2026-08-26 | 10:59 | SELL | bear_run2 | `prev` | 8.7 |
| 2026-08-27 | 10:11 | SELL | bear_run2 | `prev` | 5.3 |
| 2026-08-27 | 10:50 | SELL | bear_run3 | `prev` | 9.0 |
| 2026-08-27 | 14:17 | BUY | bull_run3 | `prev` | 8.4 |
| 2026-08-28 | 14:17 | BUY | bull_run2 | `prev` | 8.2 |
| 2026-08-31 | 09:22 | SELL | bear_run2 | `prev` | 9.8 |
| 2026-08-31 | 09:38 | SELL | bear_engulf | `prev` | 9.4 |
| 2026-08-31 | 10:02 | SELL | bear_run2 | `prev` | 4.8 |
| 2026-08-31 | 10:28 | BUY | bull_run3 | `prev` | 8.6 |
| 2026-08-31 | 14:03 | SELL | bear_run3 | `sig` | 9.9 |
| 2026-09-01 | 13:01 | SELL | bear_run3 | `prev` | 9.4 |
| 2026-09-02 | 10:30 | BUY | bull_run2 | `prev` | 9.5 |
| 2026-09-02 | 12:56 | BUY | belt_bull | `prev` | 4.2 |
| 2026-09-02 | 14:32 | BUY | bull_run3 | `sig` | 7.5 |
| 2026-09-03 | 10:58 | SELL | bear_run2 | `prev` | 4.8 |
| 2026-09-03 | 11:13 | SELL | bear_engulf | `prev` | 7.5 |
| 2026-09-03 | 13:41 | SELL | bear_run3 | `prev` | 9.3 |
| 2026-09-04 | 10:16 | BUY | marubozu_bull | `sig` | 6.8 |
| 2026-09-04 | 11:26 | BUY | bull_run2 | `prev` | 8.9 |
| 2026-09-07 | 11:02 | SELL | belt_bear | `prev` | 6.0 |
| 2026-09-08 | 09:23 | SELL | bear_engulf | `sig` | 10.4 |
| 2026-09-08 | 10:02 | SELL | bear_run2 | `sig` | 6.3 |
| 2026-09-08 | 12:48 | SELL | bear_run3 | `sig` | 5.0 |
| 2026-09-08 | 13:41 | SELL | bear_engulf | `sig` | 4.5 |
| 2026-09-08 | 14:04 | BUY | bull_run2 | `prev` | 10.5 |
| 2026-09-09 | 09:49 | SELL | belt_bear | `sig` | 9.3 |
| 2026-09-09 | 10:34 | SELL | marubozu_bear | `prev` | 10.1 |
| 2026-09-09 | 12:27 | BUY | bull_run3 | `prev` | 9.9 |
| 2026-09-09 | 13:23 | SELL | bear_run2 | `prev` | 9.9 |
| 2026-09-10 | 10:20 | SELL | three_outside_dn | `prev` | 9.8 |
| 2026-09-10 | 12:00 | BUY | bull_run3 | `prev` | 11.4 |
| 2026-09-10 | 13:30 | SELL | three_outside_dn | `min_ps` | 8.6 |
| 2026-09-11 | 10:51 | SELL | three_outside_dn | `prev` | 10.8 |
| 2026-09-15 | 14:33 | BUY | bull_run3 | `prev` | 8.1 |
| 2026-09-16 | 11:31 | BUY | three_outside_up | `prev` | 10.9 |
| 2026-09-16 | 13:23 | SELL | bear_run3 | `prev` | 11.2 |
| 2026-09-17 | 10:19 | SELL | belt_bear | `prev` | 8.2 |
| 2026-09-17 | 11:12 | BUY | bull_kicker | `sig` | 8.6 |
| 2026-09-17 | 12:00 | SELL | bear_engulf | `prev` | 4.8 |
| 2026-09-17 | 14:24 | SELL | bear_run3 | `prev` | 4.8 |
| 2026-09-18 | 11:57 | BUY | bull_run2 | `prev` | 9.8 |
| 2026-09-18 | 12:12 | BUY | bull_run3 | `prev` | 7.4 |
| 2026-09-18 | 14:07 | BUY | bull_run3 | `sig` | 4.4 |
| 2026-09-21 | 09:54 | SELL | bear_run3 | `prev` | 9.5 |
| 2026-09-21 | 10:25 | SELL | belt_bear | `cap12` | 12.0 |
| 2026-09-21 | 13:13 | BUY | belt_bull | `prev` | 6.8 |
| 2026-09-22 | 09:39 | BUY | bull_run3 | `prev` | 9.2 |
| 2026-09-22 | 09:58 | BUY | bull_engulf | `sig` | 6.2 |
| 2026-09-22 | 10:38 | SELL | belt_bear | `prev` | 7.8 |
| 2026-09-22 | 10:59 | BUY | bull_run3 | `sig` | 6.8 |
| 2026-09-22 | 11:14 | BUY | bull_run3 | `sig` | 6.4 |
| 2026-09-23 | 14:49 | BUY | bull_run2 | `prev` | 6.6 |
| 2026-09-24 | 10:28 | SELL | bear_run2 | `prev` | 5.3 |
| 2026-09-24 | 12:38 | BUY | bull_run3 | `prev` | 7.8 |
| 2026-09-24 | 14:32 | BUY | bull_run2 | `prev` | 11.6 |
| 2026-09-24 | 14:52 | BUY | bull_run3 | `prev` | 9.1 |
| 2026-09-25 | 09:52 | SELL | bear_run2 | `cap12` | 12.0 |
| 2026-09-25 | 10:08 | BUY | bull_run3 | `sig` | 12.0 |
| 2026-09-25 | 10:27 | SELL | bear_run2 | `prev` | 9.8 |
| 2026-09-25 | 14:18 | BUY | belt_bull | `prev` | 9.2 |
| 2026-09-28 | 09:54 | SELL | evening_star | `prev` | 9.7 |
| 2026-09-28 | 10:21 | SELL | bear_engulf | `prev` | 10.8 |
| 2026-09-28 | 10:52 | SELL | bear_engulf | `prev` | 5.6 |
| 2026-09-28 | 11:11 | SELL | bear_run3 | `prev` | 9.8 |
| 2026-09-28 | 11:34 | SELL | three_outside_dn | `cap10` | 10.0 |
| 2026-09-28 | 13:22 | BUY | bull_run2 | `prev` | 9.8 |
| 2026-09-28 | 14:15 | SELL | bear_run3 | `sig` | 11.8 |
| 2026-09-29 | 09:45 | SELL | bear_run3 | `prev` | 8.4 |
| 2026-09-29 | 10:25 | BUY | bull_run3 | `sig` | 6.8 |
| 2026-09-29 | 11:06 | BUY | bull_engulf | `prev` | 10.0 |
| 2026-09-30 | 09:49 | SELL | marubozu_bear | `sig` | 9.9 |
| 2026-09-30 | 10:44 | SELL | bear_run2 | `prev` | 11.6 |
| 2026-09-30 | 11:18 | BUY | bull_engulf | `sig` | 11.6 |
| 2026-10-01 | 10:13 | SELL | bear_run3 | `prev` | 11.6 |
| 2026-10-01 | 10:44 | SELL | marubozu_bear | `prev` | 11.4 |
| 2026-10-05 | 10:32 | BUY | bull_run3 | `cap10` | 10.0 |
| 2026-10-05 | 11:42 | SELL | bear_engulf | `prev` | 11.0 |
| 2026-10-05 | 12:41 | BUY | bull_run2 | `prev` | 9.4 |
| 2026-10-06 | 13:29 | BUY | bull_engulf | `prev` | 7.6 |
| 2026-10-06 | 14:40 | BUY | bull_run3 | `p75` | 7.5 |
| 2026-10-07 | 09:35 | SELL | bear_run3 | `prev` | 10.2 |
| 2026-10-07 | 10:42 | BUY | bull_run3 | `cap10` | 10.0 |
| 2026-10-07 | 11:08 | SELL | bear_engulf | `prev` | 9.2 |
| 2026-10-07 | 12:28 | SELL | belt_bear | `sig` | 6.3 |
| 2026-10-07 | 13:02 | SELL | dark_cloud | `sig` | 8.2 |
| 2026-10-07 | 13:27 | BUY | bull_run2 | `sig` | 7.2 |
| 2026-10-08 | 09:52 | SELL | dark_cloud | `prev` | 6.0 |
| 2026-10-08 | 10:29 | SELL | bear_run2 | `prev` | 6.2 |
| 2026-10-08 | 12:43 | BUY | bull_kicker | `prev` | 10.8 |
| 2026-10-09 | 09:56 | BUY | bull_run3 | `sig` | 11.2 |
| 2026-10-09 | 11:49 | SELL | bear_engulf | `prev` | 9.0 |
| 2026-10-09 | 14:45 | BUY | bull_run3 | `prev` | 10.4 |
| 2026-10-12 | 10:10 | SELL | bear_run2 | `prev` | 11.0 |
| 2026-10-12 | 10:58 | SELL | bear_run3 | `prev` | 8.3 |
| 2026-10-12 | 14:50 | BUY | bull_run2 | `prev` | 10.8 |
| 2026-10-13 | 10:25 | SELL | marubozu_bear | `cap12` | 12.0 |
| 2026-10-13 | 11:14 | SELL | marubozu_bear | `prev` | 11.9 |
| 2026-10-13 | 14:07 | BUY | bull_run3 | `prev` | 9.8 |
| 2026-10-14 | 14:59 | SELL | bear_run3 | `sig` | 10.0 |
| 2026-10-15 | 14:42 | BUY | hammer | `prev` | 4.5 |
| 2026-10-16 | 11:17 | SELL | three_outside_dn | `prev` | 7.3 |
| 2026-10-16 | 12:10 | BUY | bull_run3 | `sig` | 8.2 |
| 2026-10-16 | 14:44 | BUY | bull_run3 | `p75` | 7.1 |
| 2026-10-19 | 13:37 | BUY | bull_run3 | `prev` | 10.7 |
| 2026-10-21 | 10:54 | SELL | dark_cloud | `prev` | 9.8 |
| 2026-10-21 | 11:45 | SELL | bear_run2 | `prev` | 10.2 |
| 2026-10-22 | 09:59 | SELL | bear_engulf | `prev` | 11.9 |
| 2026-10-22 | 10:41 | SELL | bear_run3 | `prev` | 9.2 |
| 2026-10-22 | 11:16 | SELL | bear_engulf | `prev` | 10.9 |
| 2026-10-22 | 13:44 | BUY | bull_run2 | `sig` | 11.5 |
| 2026-10-23 | 11:42 | SELL | three_outside_dn | `cap10` | 10.0 |
| 2026-10-23 | 14:19 | BUY | bull_run2 | `prev` | 11.2 |
| 2026-10-26 | 12:47 | BUY | piercing | `prev` | 6.0 |
| 2026-10-26 | 13:54 | SELL | bear_run2 | `prev` | 8.4 |
| 2026-10-26 | 14:30 | BUY | bull_run3 | `prev` | 8.9 |
| 2026-10-27 | 09:37 | SELL | bear_engulf | `prev` | 8.3 |
| 2026-10-27 | 10:34 | BUY | bull_run3 | `prev` | 11.6 |
| 2026-10-27 | 11:20 | SELL | three_outside_dn | `prev` | 10.6 |
| 2026-10-27 | 11:37 | BUY | bull_run3 | `prev` | 8.7 |
| 2026-10-28 | 09:40 | BUY | bull_run3 | `prev` | 8.3 |
| 2026-10-28 | 10:55 | BUY | bull_kicker | `prev` | 10.2 |
| 2026-10-28 | 13:15 | SELL | bear_run3 | `prev` | 10.8 |
| 2026-10-29 | 09:54 | SELL | bear_engulf | `sig` | 8.4 |
| 2026-10-30 | 11:47 | BUY | bull_run2 | `prev` | 9.5 |
| 2026-10-30 | 12:55 | BUY | bull_engulf | `prev` | 7.6 |
| 2026-10-30 | 14:02 | BUY | bull_engulf | `prev` | 7.5 |
| 2026-11-02 | 10:00 | SELL | three_crows | `sig` | 9.5 |
| 2026-11-02 | 11:39 | BUY | bull_run2 | `prev` | 9.7 |
| 2026-11-02 | 12:09 | BUY | bull_run2 | `sig` | 8.4 |
| 2026-11-02 | 14:29 | BUY | bull_run2 | `prev` | 6.3 |
| 2026-11-03 | 10:09 | SELL | belt_bear | `sig` | 6.5 |
| 2026-11-03 | 10:53 | BUY | bull_run2 | `prev` | 11.5 |
| 2026-11-03 | 12:52 | BUY | bull_run2 | `sig` | 7.2 |
| 2026-11-04 | 10:13 | SELL | bear_run2 | `prev` | 9.7 |
| 2026-11-04 | 11:15 | SELL | bear_engulf | `prev` | 8.6 |
| 2026-11-04 | 14:03 | SELL | bear_run3 | `cap8` | 8.0 |
| 2026-11-05 | 14:19 | SELL | bear_run3 | `cap8` | 8.0 |
| 2026-11-06 | 09:59 | SELL | bear_run3 | `prev` | 8.5 |
| 2026-11-06 | 10:20 | SELL | bear_engulf | `sig` | 8.7 |
| 2026-11-06 | 11:41 | BUY | bull_run3 | `prev` | 9.0 |


## Deeper densification

See [`NIFTY_1M_SCALP_DEEPER_100.md`](NIFTY_1M_SCALP_DEEPER_100.md).
- Best deep PATH union: **307 calls / 64 days** (4.8/day) · gap 8 · avg SL 8.78


## Latest densify scoreboard

| Book | L3m calls | Days | /day | Avg SL | Notes |
|---|---:|---:|---:|---:|---|
| Prior multicall dense | 187 | 64 | 2.92 | 8.6 | path micros |
| **Deep wick/ATR union gap8** | **307** | **64** | **4.8** | **8.78** | **champion both-100** |
| Push gap4 min_l3m=1 | 168 | 58 | 2.9 | 8.86 | did not beat deep |
| MFE target-reached gap10 | 561 | 64 | 8.77 | 7.08 | path-win ~41% only |

Detail: [`NIFTY_1M_SCALP_DEEPER_100.md`](NIFTY_1M_SCALP_DEEPER_100.md)
