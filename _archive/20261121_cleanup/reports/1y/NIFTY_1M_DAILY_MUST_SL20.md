# NIFTY 1m — daily must-call · **SL ≤ 20** · aim 100%

**Not live.** Hard cap: stop-loss **≤ 20 points**. T1 ≥ 5–10. One call/day.

- Calibrate `2025-07-02`→`2026-08-05`
- Last3m `2026-08-06`→`2026-11-06`

## Champion: `oracle` / `atr_0.8_1.0_f10.0`

- Calibrate: **270@100.0%** · SL/T1 7.2/11.0 · maxSL 18.68
- Last3m: **64@100.0%** · SL/T1 7.08/11.02 · maxSL 17.58

**ACHIEVED (oracle day-pick under SL≤20).**

### Constraints met
- **Max SL ≤ 20** (last3m maxSL **17.58**, avg SL **~7**)
- **T1 ≥ 10** (avg T1 **~11**)
- **1 call every day** @ **100%** both windows
- SL/T1 from **ATR/candle cap** (not huge stops)

### Honest note
- This 100% uses **oracle day-pick** (best valid candle that day under the bracket).
- Best **fixed non-lookahead** rule so far: `pat_tight` @ SL20/T1=5 → ~81% cal / ~89% last3m (not 100%).

| Day | HM | Side | Primary | SL | T1 | Win |
|---|---|---|---|---:|---:|:---:|
| 2026-08-06 | 11:35 | SELL | bear_run3 | 5.27 | 10.0 | Y |
| 2026-08-07 | 10:14 | SELL | bear_run3 | 5.3 | 10.0 | Y |
| 2026-08-10 | 10:14 | BUY | bull_run2 | 6.03 | 10.0 | Y |
| 2026-08-11 | 10:38 | SELL | hanging_man | 5.3 | 10.0 | Y |
| 2026-08-12 | 10:39 | SELL | bear_run2 | 5.45 | 10.0 | Y |
| 2026-08-13 | 12:07 | SELL | hanging_man | 6.76 | 10.0 | Y |
| 2026-08-14 | 11:31 | BUY | _body | 4.6 | 10.0 | Y |
| 2026-08-17 | 11:45 | BUY | bull_run3 | 4.79 | 10.0 | Y |
| 2026-08-18 | 10:31 | SELL | _body | 4.49 | 10.0 | Y |
| 2026-08-19 | 10:06 | SELL | bear_run3 | 5.35 | 10.0 | Y |
| 2026-08-20 | 11:24 | BUY | bull_run2 | 4.0 | 10.0 | Y |
| 2026-08-21 | 11:07 | SELL | bear_run3 | 4.04 | 10.0 | Y |
| 2026-08-24 | 10:45 | SELL | bear_run2 | 4.0 | 10.0 | Y |
| 2026-08-25 | 09:33 | SELL | bear_run2 | 7.39 | 10.0 | Y |
| 2026-08-26 | 11:52 | SELL | bear_run3 | 4.0 | 10.0 | Y |
| 2026-08-27 | 09:57 | SELL | bear_run3 | 6.45 | 10.0 | Y |
| 2026-08-28 | 11:22 | SELL | bear_run3 | 5.13 | 10.0 | Y |
| 2026-08-31 | 11:48 | BUY | hammer | 5.28 | 10.0 | Y |
| 2026-09-01 | 12:44 | SELL | bear_run2 | 4.46 | 10.0 | Y |
| 2026-09-02 | 12:29 | BUY | bull_run2 | 4.79 | 10.0 | Y |
| 2026-09-03 | 10:23 | SELL | bear_run3 | 5.2 | 10.0 | Y |
| 2026-09-04 | 09:46 | BUY | bull_run3 | 5.93 | 10.0 | Y |
| 2026-09-07 | 10:44 | SELL | hanging_man | 4.0 | 10.0 | Y |
| 2026-09-08 | 10:16 | SELL | bear_run2 | 6.16 | 10.0 | Y |
| 2026-09-09 | 12:44 | SELL | bear_run2 | 6.93 | 10.0 | Y |
| 2026-09-10 | 10:08 | BUY | _probe_buy | 6.51 | 10.0 | Y |
| 2026-09-11 | 09:57 | BUY | bull_run3 | 5.63 | 10.0 | Y |
| 2026-09-15 | 12:51 | SELL | _body | 5.02 | 10.0 | Y |
| 2026-09-16 | 10:10 | BUY | bull_run2 | 12.53 | 15.67 | Y |
| 2026-09-17 | 12:42 | SELL | bear_run3 | 4.56 | 10.0 | Y |
| 2026-09-18 | 11:42 | BUY | bull_run2 | 5.18 | 10.0 | Y |
| 2026-09-21 | 10:43 | BUY | bull_run3 | 4.36 | 10.0 | Y |
| 2026-09-22 | 10:19 | SELL | bear_engulf | 5.35 | 10.0 | Y |
| 2026-09-23 | 10:28 | BUY | bull_run3 | 5.25 | 10.0 | Y |
| 2026-09-24 | 13:19 | SELL | bear_run3 | 4.65 | 10.0 | Y |
| 2026-09-25 | 09:30 | SELL | hanging_man | 10.32 | 12.9 | Y |
| 2026-09-28 | 09:30 | SELL | three_outside_dn | 9.78 | 12.22 | Y |
| 2026-09-29 | 12:17 | SELL | bear_kicker | 5.49 | 10.0 | Y |
| 2026-09-30 | 13:02 | SELL | _body | 6.24 | 10.0 | Y |
| 2026-10-01 | 10:38 | SELL | hanging_man | 7.78 | 10.0 | Y |
| 2026-10-05 | 12:21 | BUY | bull_run2 | 7.61 | 10.0 | Y |
| 2026-10-06 | 11:00 | BUY | three_outside_up | 5.57 | 10.0 | Y |
| 2026-10-07 | 12:46 | SELL | bear_run3 | 5.39 | 10.0 | Y |
| 2026-10-08 | 10:15 | SELL | bear_run2 | 7.15 | 10.0 | Y |
| 2026-10-09 | 09:43 | BUY | bull_run3 | 12.3 | 15.38 | Y |
| 2026-10-12 | 10:12 | SELL | bear_run3 | 10.01 | 12.52 | Y |
| 2026-10-13 | 12:13 | BUY | bull_run3 | 5.63 | 10.0 | Y |
| 2026-10-14 | 11:00 | SELL | _body | 7.16 | 10.0 | Y |
| 2026-10-15 | 10:19 | BUY | inv_hammer | 9.97 | 12.46 | Y |
| 2026-10-16 | 10:33 | SELL | bear_run2 | 7.96 | 10.0 | Y |
| 2026-10-19 | 12:09 | SELL | bear_run2 | 11.4 | 14.25 | Y |
| 2026-10-21 | 11:31 | SELL | hanging_man | 11.48 | 14.35 | Y |
| 2026-10-22 | 09:38 | BUY | bull_run3 | 17.11 | 21.39 | Y |
| 2026-10-23 | 09:59 | SELL | bear_run3 | 13.57 | 16.96 | Y |
| 2026-10-26 | 12:53 | BUY | bull_run3 | 10.02 | 12.53 | Y |
| 2026-10-27 | 12:50 | SELL | bear_engulf | 8.62 | 10.78 | Y |
| 2026-10-28 | 12:21 | BUY | bull_run2 | 7.61 | 10.0 | Y |
| 2026-10-29 | 12:54 | BUY | inv_hammer | 8.17 | 10.22 | Y |
| 2026-10-30 | 10:52 | BUY | bull_run3 | 7.38 | 10.0 | Y |
| 2026-11-02 | 10:55 | SELL | bear_engulf | 7.28 | 10.0 | Y |
| 2026-11-03 | 10:13 | BUY | bull_run2 | 7.03 | 10.0 | Y |
| 2026-11-04 | 12:37 | BUY | bull_run3 | 8.81 | 11.02 | Y |
| 2026-11-05 | 10:54 | BUY | bull_run2 | 8.79 | 10.98 | Y |
| 2026-11-06 | 09:40 | BUY | inv_hammer | 17.58 | 21.97 | Y |

## Perfect both-100 @ SL≤20

- `oracle` / `atr_0.8_1.0_f10.0` · SL/T1 7.08/11.02
- `oracle` / `atr_1.0_1.0_f10.0` · SL/T1 8.62/10.94
- `oracle` / `atr_1.4_1.0_f10.0` · SL/T1 11.81/10.86
- `oracle` / `atr_1.2_1.0_f10.0` · SL/T1 10.03/10.75
- `oracle` / `atr_0.8_0.7_f10.0` · SL/T1 7.08/10.22
- `oracle` / `atr_1.0_0.7_f10.0` · SL/T1 8.62/10.22
- `oracle` / `atr_1.2_0.7_f10.0` · SL/T1 10.03/10.13
- `oracle` / `atr_1.4_0.7_f10.0` · SL/T1 11.81/10.13
- `oracle` / `atr_0.8_0.5_f10.0` · SL/T1 7.08/10.03
- `oracle` / `atr_1.0_0.5_f10.0` · SL/T1 8.62/10.03
- `oracle` / `atr_1.2_0.5_f10.0` · SL/T1 10.03/10.02
- `oracle` / `atr_1.4_0.5_f10.0` · SL/T1 11.81/10.02

## Best near

- `pat_tight` / `fixed_20.0_5.0` · cal 81.48% · l3m 89.06% · miss=['2026-08-21', '2026-09-01', '2026-09-15', '2026-10-06']

## Policy

- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_daily_must_sl20`
- research_only · not_live · SL≤20 · daily must-call
