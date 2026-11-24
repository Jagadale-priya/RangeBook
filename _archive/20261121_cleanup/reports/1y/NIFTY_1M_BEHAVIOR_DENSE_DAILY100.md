# NIFTY 1m — **dense daily** 100% (deep union + scored picker)

**Not live.** SL≤20 · T1 8–10 · aim **1 call/day @ 100%**.

- Calibrate `2025-07-02`→`2026-08-05` (271 days)
- Last3m `2026-08-06`→`2026-11-06` (64 days)

## Verdict

| Approach | Cal days @100% | Last3m days @100% | Notes |
|---|---:|---:|---|
| Path feasibility (oracle pick) | **271/271** | **64/64** | A winning SL≤20 candle exists every day |
| Best single behavior filter | 8 | 4 | morning/evening star + continuation |
| **Micro-union (17 rules)** | **87 (32%)** | **29 (45%)** | Densest both-100 pack so far |
| Scored 1/day picker (full cover) | 271 @71% | 64 @62% | Covers every day, not 100% hit |

**Honest limit:** with SL≤20 and filters that stay 100% on *both* windows, we can pack ~**half of last3m days**. Full 1/day @100% still needs either oracle day-pick or accepting <100% hit.

## Feasibility

- Every session has ≥1 pattern event that wins SL20/T10 (path-feasible 100% days).

## Exhaustive both-100 micros: **320**

### Greedy union coverage

- Calibrate: **87/271 (32.1%)** @ 100%
- Last3m: **29/64 (45.31%)** @ 100%
- Micros packed: **17**

Union is denser than any single filter but **not full calendar** yet (many cal-perfect cells fail last3m transfer).

### Union last3m calls

| Day | HM | Side | Primary | SL | T1 | Win |
|---|---|---|---|---:|---:|:---:|
| 2026-08-14 | 10:29 | SELL | three_outside_dn | 20.0 | 8.0 | Y |
| 2026-08-18 | 09:35 | SELL | hanging_man | 20.0 | 8.0 | Y |
| 2026-08-20 | 12:48 | BUY | three_soldiers | 20.0 | 8.0 | Y |
| 2026-08-21 | 09:31 | SELL | three_outside_dn | 20.0 | 8.0 | Y |
| 2026-08-24 | 09:40 | SELL | three_outside_dn | 20.0 | 8.0 | Y |
| 2026-08-25 | 09:59 | SELL | three_outside_dn | 20.0 | 8.0 | Y |
| 2026-08-26 | 09:21 | BUY | three_outside_up | 20.0 | 8.0 | Y |
| 2026-08-31 | 09:35 | SELL | three_outside_dn | 20.0 | 8.0 | Y |
| 2026-09-01 | 10:12 | BUY | bull_kicker | 20.0 | 8.0 | Y |
| 2026-09-03 | 10:07 | SELL | three_outside_dn | 20.0 | 8.0 | Y |
| 2026-09-04 | 14:20 | BUY | bull_kicker | 20.0 | 8.0 | Y |
| 2026-09-09 | 09:56 | SELL | three_outside_dn | 20.0 | 8.0 | Y |
| 2026-09-17 | 14:01 | BUY | bull_kicker | 20.0 | 8.0 | Y |
| 2026-09-18 | 09:51 | BUY | bull_engulf | 20.0 | 8.0 | Y |
| 2026-10-01 | 14:53 | BUY | marubozu_bull | 20.0 | 8.0 | Y |
| 2026-10-05 | 14:27 | BUY | bull_kicker | 20.0 | 8.0 | Y |
| 2026-10-06 | 11:13 | BUY | hammer | 20.0 | 8.0 | Y |
| 2026-10-08 | 14:13 | BUY | bull_run2 | 20.0 | 8.0 | Y |
| 2026-10-12 | 10:22 | SELL | three_outside_dn | 20.0 | 8.0 | Y |
| 2026-10-13 | 14:00 | BUY | bull_kicker | 20.0 | 8.0 | Y |
| 2026-10-16 | 10:04 | BUY | bull_kicker | 20.0 | 8.0 | Y |
| 2026-10-19 | 10:19 | BUY | bull_engulf | 20.0 | 8.0 | Y |
| 2026-10-21 | 10:27 | BUY | bull_run2 | 20.0 | 8.0 | Y |
| 2026-10-22 | 14:58 | BUY | inv_hammer | 20.0 | 8.0 | Y |
| 2026-10-23 | 14:29 | BUY | bull_run2 | 20.0 | 8.0 | Y |
| 2026-11-02 | 09:29 | SELL | dark_cloud | 20.0 | 8.0 | Y |
| 2026-11-03 | 13:56 | SELL | bear_run2 | 20.0 | 8.0 | Y |
| 2026-11-04 | 09:35 | SELL | hanging_man | 20.0 | 8.0 | Y |
| 2026-11-05 | 14:00 | SELL | three_outside_dn | 20.0 | 8.0 | Y |

## Cascade picker (ordered micros)

- Calibrate: **227@71.81%**
- Last3m: **60@76.67%**

## Scored behavior picker (best-of-day)

- Threshold **25** · tag `near`
- Calibrate: **271 days @ 71.22%**
- Last3m: **64 days @ 62.5%** · SL/T1 20/10

Misses cal=['2025-07-08', '2025-07-10', '2025-07-21', '2025-07-31', '2025-08-18', '2025-08-19'] l3m=['2026-08-06', '2026-08-13', '2026-08-14', '2026-08-18', '2026-08-20', '2026-08-21']

| Day | HM | Side | Primary | Score | Win |
|---|---|---|---|---:|:---:|
| 2026-08-06 | 09:47 | BUY | bull_kicker | 98.27 | N |
| 2026-08-07 | 11:24 | BUY | bull_run2 | 91.78 | Y |
| 2026-08-10 | 10:44 | BUY | belt_bull | 97.92 | Y |
| 2026-08-11 | 09:42 | SELL | bear_engulf | 97.13 | Y |
| 2026-08-12 | 11:52 | SELL | falling_3_methods | 102.64 | Y |
| 2026-08-13 | 10:30 | SELL | three_crows | 99.24 | N |
| 2026-08-14 | 09:29 | SELL | three_crows | 99.24 | N |
| 2026-08-17 | 09:58 | SELL | bear_engulf | 97.13 | Y |
| 2026-08-18 | 11:29 | SELL | falling_3_methods | 102.64 | N |
| 2026-08-19 | 10:13 | SELL | marubozu_bear | 97.85 | Y |
| 2026-08-20 | 10:37 | SELL | three_outside_dn | 93.07 | N |
| 2026-08-21 | 10:07 | SELL | bear_run3 | 96.69 | N |
| 2026-08-24 | 10:03 | SELL | bear_engulf | 97.13 | Y |
| 2026-08-25 | 09:38 | SELL | three_crows | 99.24 | Y |
| 2026-08-26 | 09:24 | BUY | belt_bull | 97.92 | Y |
| 2026-08-27 | 10:51 | SELL | three_crows | 99.24 | Y |
| 2026-08-28 | 11:57 | SELL | three_crows | 99.24 | N |
| 2026-08-31 | 11:11 | SELL | falling_3_methods | 102.64 | N |
| 2026-09-01 | 09:47 | SELL | three_crows | 99.24 | N |
| 2026-09-02 | 11:24 | SELL | falling_3_methods | 98.64 | Y |
| 2026-09-03 | 09:39 | BUY | three_outside_up | 97.38 | Y |
| 2026-09-04 | 10:29 | BUY | marubozu_bull | 97.04 | Y |
| 2026-09-07 | 09:54 | SELL | three_crows | 99.24 | Y |
| 2026-09-08 | 09:55 | SELL | bear_engulf | 97.13 | Y |
| 2026-09-09 | 11:51 | SELL | three_crows | 99.24 | Y |
| 2026-09-10 | 10:02 | SELL | three_crows | 99.24 | N |
| 2026-09-11 | 09:41 | SELL | three_crows | 99.24 | N |
| 2026-09-15 | 10:49 | SELL | marubozu_bear | 97.85 | Y |
| 2026-09-16 | 10:34 | BUY | belt_bull | 97.92 | Y |
| 2026-09-17 | 10:10 | BUY | bull_kicker | 98.27 | N |
| 2026-09-18 | 10:26 | SELL | falling_3_methods | 102.64 | Y |
| 2026-09-21 | 09:51 | BUY | bull_kicker | 98.27 | N |
| 2026-09-22 | 10:32 | SELL | marubozu_bear | 97.85 | Y |
| 2026-09-23 | 09:47 | BUY | bull_kicker | 98.27 | N |
| 2026-09-24 | 11:32 | SELL | three_crows | 99.24 | Y |
| 2026-09-25 | 09:34 | BUY | belt_bull | 97.92 | N |
| 2026-09-28 | 10:39 | SELL | three_crows | 99.24 | Y |
| 2026-09-29 | 09:25 | SELL | bear_run2 | 96.76 | Y |
| 2026-09-30 | 10:09 | BUY | belt_bull | 97.92 | Y |
| 2026-10-01 | 10:06 | BUY | marubozu_bull | 97.04 | N |
| 2026-10-05 | 11:19 | SELL | marubozu_bear | 97.85 | Y |
| 2026-10-06 | 09:40 | BUY | three_outside_up | 97.38 | Y |
| 2026-10-07 | 09:34 | SELL | three_crows | 99.24 | Y |
| 2026-10-08 | 10:18 | SELL | falling_3_methods | 102.64 | Y |
| 2026-10-09 | 09:42 | BUY | belt_bull | 97.92 | Y |
| 2026-10-12 | 10:18 | SELL | falling_3_methods | 102.64 | N |
| 2026-10-13 | 09:47 | BUY | belt_bull | 97.92 | Y |
| 2026-10-14 | 10:41 | BUY | belt_bull | 97.92 | Y |
| 2026-10-15 | 10:22 | BUY | three_soldiers | 98.57 | Y |
| 2026-10-16 | 10:28 | BUY | belt_bull | 97.92 | N |
| 2026-10-19 | 10:48 | SELL | falling_3_methods | 98.64 | N |
| 2026-10-21 | 11:51 | SELL | three_crows | 99.24 | N |
| 2026-10-22 | 10:28 | BUY | belt_bull | 97.92 | N |
| 2026-10-23 | 11:50 | SELL | three_crows | 99.24 | Y |
| 2026-10-26 | 10:08 | BUY | belt_bull | 93.92 | N |
| 2026-10-27 | 10:33 | BUY | marubozu_bull | 97.04 | Y |
| 2026-10-28 | 10:20 | SELL | bear_engulf | 97.13 | Y |
| 2026-10-29 | 10:12 | BUY | bull_run2 | 95.78 | Y |
| 2026-10-30 | 10:34 | SELL | bear_engulf | 97.13 | N |
| 2026-11-02 | 10:26 | BUY | bull_kicker | 98.27 | Y |

## Densest single micro

- `fix20.0_8.0` · cal 7@100% · l3m 5@100%
- Filter: `{'primaries': ['three_outside_dn'], 'side': 'SELL', 'regime': 'reversal', 'align': 1, 'clocks': ['early'], 'min_body': 0.45, 'max_sl_candle': 12.0, 'rsi_lo': 0, 'rsi_hi': 40}`


## Top union micros

- `fix20.0_8.0` cal 7 · l3m 5 · `{'primaries': ['three_outside_dn'], 'side': 'SELL', 'regime': 'reversal', 'align': 1, 'clocks': ['early'], 'min_body': 0.45, 'max_sl_candle': 12.0, 'rsi_lo': 0, 'rsi_hi': 40}`
- `fix20.0_8.0` cal 6 · l3m 4 · `{'primaries': ['bull_kicker'], 'side': 'BUY', 'regime': 'reversal', 'align': 1, 'clocks': ['late'], 'max_sl_candle': 12.0, 'rsi_lo': 40, 'rsi_hi': 60}`
- `fix20.0_8.0` cal 7 · l3m 3 · `{'primaries': ['three_outside_dn'], 'side': 'SELL', 'regime': 'balanced', 'align': 1, 'clocks': ['early'], 'max_sl_candle': 12.0, 'rsi_lo': 0, 'rsi_hi': 40}`
- `fix20.0_8.0` cal 7 · l3m 2 · `{'primaries': ['hanging_man'], 'side': 'SELL', 'regime': 'continuation', 'align': 0, 'clocks': ['early'], 'max_sl_candle': 12.0, 'rsi_lo': 40, 'rsi_hi': 60}`
- `fix20.0_8.0` cal 4 · l3m 2 · `{'primaries': ['bull_run2'], 'side': 'BUY', 'regime': 'reversal', 'align': 0, 'clocks': ['late'], 'min_body': 0.45, 'max_sl_candle': 20.0, 'rsi_lo': 40, 'rsi_hi': 60}`
- `fix20.0_8.0` cal 3 · l3m 2 · `{'primaries': ['bull_kicker'], 'side': 'BUY', 'regime': 'continuation', 'align': 0, 'clocks': ['early'], 'max_sl_candle': 12.0, 'rsi_lo': 60, 'rsi_hi': 100}`
- `fix20.0_8.0` cal 10 · l3m 1 · `{'primaries': ['bull_engulf'], 'side': 'BUY', 'regime': 'reversal', 'align': 0, 'clocks': ['early'], 'min_body': 0.45, 'max_sl_candle': 20.0, 'rsi_lo': 40, 'rsi_hi': 60}`
- `fix20.0_8.0` cal 8 · l3m 1 · `{'primaries': ['bull_run2'], 'side': 'BUY', 'regime': 'continuation', 'align': 0, 'clocks': ['early'], 'min_body': 0.45, 'max_sl_candle': 15.0, 'rsi_lo': 60, 'rsi_hi': 100}`
- `fix20.0_8.0` cal 5 · l3m 1 · `{'primaries': ['dark_cloud'], 'side': 'SELL', 'regime': 'reversal', 'align': 0, 'clocks': ['early'], 'min_body': 0.45, 'max_sl_candle': 12.0, 'rsi_lo': 40, 'rsi_hi': 60}`
- `fix20.0_8.0` cal 5 · l3m 1 · `{'primaries': ['three_soldiers'], 'side': 'BUY', 'regime': 'continuation', 'align': 1, 'clocks': ['midday'], 'min_body': 0.45, 'max_sl_candle': 15.0, 'rsi_lo': 60, 'rsi_hi': 100}`
- `fix20.0_8.0` cal 4 · l3m 1 · `{'primaries': ['hammer'], 'side': 'BUY', 'regime': 'balanced', 'align': 1, 'clocks': ['morning'], 'max_sl_candle': 12.0, 'rsi_lo': 60, 'rsi_hi': 100}`
- `fix20.0_8.0` cal 4 · l3m 1 · `{'primaries': ['bear_run2'], 'side': 'SELL', 'regime': 'continuation', 'align': 0, 'clocks': ['midday'], 'min_body': 0.45, 'max_sl_candle': 15.0, 'rsi_lo': 0, 'rsi_hi': 40}`
- `fix20.0_8.0` cal 4 · l3m 1 · `{'primaries': ['marubozu_bull'], 'side': 'BUY', 'regime': 'continuation', 'align': 0, 'clocks': ['late'], 'min_body': 0.45, 'max_sl_candle': 15.0, 'rsi_lo': 60, 'rsi_hi': 100}`
- `fix20.0_8.0` cal 4 · l3m 1 · `{'primaries': ['three_outside_dn'], 'side': 'SELL', 'regime': 'continuation', 'align': 0, 'clocks': ['late'], 'min_body': 0.45, 'max_sl_candle': 15.0, 'rsi_lo': 40, 'rsi_hi': 60}`
- `fix20.0_8.0` cal 3 · l3m 1 · `{'primaries': ['inv_hammer'], 'side': 'BUY', 'regime': 'balanced', 'align': 0, 'clocks': ['late'], 'max_sl_candle': 12.0, 'rsi_lo': 0, 'rsi_hi': 40}`
- `fix20.0_8.0` cal 3 · l3m 1 · `{'primaries': ['three_outside_up'], 'side': 'BUY', 'regime': 'balanced', 'align': 1, 'clocks': ['early'], 'min_body': 0.45, 'max_sl_candle': 15.0, 'rsi_lo': 60, 'rsi_hi': 100}`
- `fix20.0_8.0` cal 3 · l3m 1 · `{'primaries': ['bull_engulf'], 'side': 'BUY', 'regime': 'balanced', 'align': 0, 'clocks': ['early'], 'max_sl_candle': 12.0, 'rsi_lo': 40, 'rsi_hi': 60}`

## Policy

- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_pattern_behavior_100`
- research_only · not_live · SL≤20 · dense daily
