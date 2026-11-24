# NIFTY 1m — **T1=15/20 deeper densify** (held books locked)

**Not live.** Hold T1=10 and prior T1=15 more-calls logic. Deepen T1=15 & T1=20 for **more PATH@100% calls**.

### Breakthrough
Family + session-slot cells + dense micro-union unlocked **every-day** high-T coverage:
- **T1=15:** 465 calls / 64 days · **0 blank** · ~7.3/day · RR ~1.57
- **T1=20:** 324 calls / 64 days · **0 blank** · ~5.1/day · RR ~1.82

## Held baselines (locked)

| Book | T1 | Calls | Days | Zero | /day | AvgSL |
|---|---:|---:|---:|---:|---:|---:|
| HELD10 | 10 | 307 | 64 | 0 | 4.8 | 8.78 |
| HELD15 | 15 | 103 | 44 | 20 | 1.61 | 12.52 |

## New deep champions

| T1 | Kind | SLmax | Gap | Calls | Days | Zero | /day-all | AvgSL | RR | vs HELD15 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 15 | zero_fill_dense / best_coverage | 15.0 | 4 | 465 | 64 | 0 | 7.27 | 9.54 | 1.57 | Δcalls +362 · Δdays +20 |
| 15 | deep_dense / best_calls | 20.0 | 4 | 532 | 63 | 1 | 8.31 | 10.96 | 1.37 |  |
| 20 | zero_fill_dense / best_coverage | 20.0 | 4 | 324 | 64 | 0 | 5.06 | 10.97 | 1.82 |  |
| 20 | zero_fill_dense / best_calls | 20.0 | 4 | 324 | 64 | 0 | 5.06 | 10.97 | 1.82 |  |

## T1=15 deep champion — `zero_fill_dense`

- **465 calls / 64 days** · zero **0** · 7.27/day-all · avg SL **9.54** · RR **1.57**
- SLmax=15.0 gap=4 micros=397
- Hist: `{1: 1, 3: 9, 4: 7, 5: 6, 6: 7, 7: 6, 8: 7, 9: 5, 10: 4, 11: 3, 12: 5, 14: 1, 15: 1, 16: 2}`

### Zero-day oracle autopsy (before fill)

- Zero days: **0** · oracle path-wins on them: **0**
- Top patterns on zero days: []
- Feature hits: `{}`

### Calls (sample)

| Day | HM | Side | Pattern | Family | Slot | SL style | SL |
|---|---|---|---|---|---|---|---:|
| 2026-08-06 | 09:51 | SELL | bear_engulf | engulf | open | `p75` | 4.0 |
| 2026-08-06 | 11:32 | SELL | bear_run3 | runs | mid | `cap20` | 12.35 |
| 2026-08-06 | 12:20 | SELL | bear_run3 | runs | mid | `prev` | 14.7 |
| 2026-08-06 | 14:37 | SELL | three_outside_dn | three | close | `prev` | 5.5 |
| 2026-08-06 | 14:52 | SELL | bear_run3 | runs | close | `sig` | 5.2 |
| 2026-08-07 | 09:25 | SELL | hanging_man | other | open | `prev` | 9.6 |
| 2026-08-07 | 09:49 | BUY | bull_run2 | runs | open | `sig` | 4.6 |
| 2026-08-07 | 11:06 | BUY | bull_run2 | runs | morn | `prev` | 10.55 |
| 2026-08-07 | 11:40 | SELL | belt_bear | belt_maru | mid | `prev` | 6.0 |
| 2026-08-07 | 12:26 | BUY | bull_run2 | runs | mid | `p75` | 13.39 |
| 2026-08-07 | 13:55 | SELL | three_crows | three | aft | `p75` | 12.04 |
| 2026-08-07 | 14:03 | SELL | belt_bear | belt_maru | aft | `cap8` | 8.0 |
| 2026-08-10 | 09:22 | SELL | bear_engulf | engulf | open | `prev` | 15.0 |
| 2026-08-10 | 10:00 | BUY | bull_run2 | runs | morn | `prev` | 6.95 |
| 2026-08-10 | 10:19 | BUY | bull_run3 | runs | morn | `sig` | 4.95 |
| 2026-08-10 | 10:26 | SELL | three_outside_dn | three | morn | `min_ps` | 5.65 |
| 2026-08-11 | 09:56 | BUY | bull_run2 | runs | open | `cap15` | 15.0 |
| 2026-08-11 | 12:20 | BUY | bull_run2 | runs | mid | `p60` | 4.68 |
| 2026-08-11 | 13:26 | BUY | bull_run3 | runs | aft | `cap12` | 12.0 |
| 2026-08-11 | 14:28 | SELL | belt_bear | belt_maru | aft | `sig` | 5.1 |
| 2026-08-12 | 09:50 | SELL | belt_bear | belt_maru | open | `p75` | 9.68 |
| 2026-08-12 | 09:57 | SELL | three_crows | three | open | `cap20` | 14.0 |
| 2026-08-12 | 10:42 | SELL | bear_run3 | runs | morn | `min_ps` | 5.85 |
| 2026-08-12 | 11:24 | SELL | bear_engulf | engulf | morn | `p75` | 10.12 |
| 2026-08-12 | 11:46 | SELL | bear_run2 | runs | mid | `prev` | 4.15 |
| 2026-08-12 | 13:42 | SELL | three_outside_dn | three | aft | `p75` | 7.76 |
| 2026-08-13 | 10:13 | BUY | bull_run2 | runs | morn | `cap15` | 15.0 |
| 2026-08-13 | 10:37 | BUY | bull_kicker | kick | morn | `prev` | 8.9 |
| 2026-08-13 | 11:57 | BUY | bull_run2 | runs | mid | `prev` | 14.9 |
| 2026-08-13 | 12:42 | SELL | bear_run2 | runs | mid | `prev` | 7.35 |
| 2026-08-13 | 14:01 | SELL | three_outside_dn | three | aft | `sig` | 5.25 |
| 2026-08-14 | 11:33 | BUY | rising_3_methods | other | mid | `cap20` | 8.9 |
| 2026-08-14 | 13:22 | SELL | bear_engulf | engulf | aft | `prev` | 4.2 |
| 2026-08-14 | 13:37 | BUY | three_outside_up | three | aft | `cap8` | 5.85 |
| 2026-08-17 | 09:30 | SELL | bear_engulf | engulf | open | `sig` | 11.9 |
| 2026-08-17 | 09:59 | SELL | three_outside_dn | three | open | `p60` | 6.93 |
| 2026-08-17 | 10:38 | SELL | bear_run3 | runs | morn | `p60` | 4.05 |
| 2026-08-17 | 11:27 | BUY | bull_run3 | runs | morn | `prev` | 10.95 |
| 2026-08-17 | 11:48 | BUY | three_outside_up | three | mid | `prev` | 12.2 |
| 2026-08-17 | 12:45 | BUY | three_outside_up | three | mid | `sig` | 7.45 |
| 2026-08-17 | 14:54 | BUY | three_outside_up | three | close | `cap10` | 10.0 |
| 2026-08-18 | 10:40 | SELL | marubozu_bear | belt_maru | morn | `sig` | 9.75 |
| 2026-08-18 | 11:18 | SELL | three_crows | three | morn | `sig` | 5.45 |
| 2026-08-18 | 13:07 | BUY | bull_kicker | kick | aft | `sig` | 6.65 |
| 2026-08-18 | 14:37 | BUY | bull_run2 | runs | close | `prev` | 5.25 |
| … | | | | | | | 420 more |

### T1=15 top packs

| Kind | SLmax | Gap | Calls | Days | Zero | RR |
|---|---:|---:|---:|---:|---:|---:|
| zero_fill_dense | 15.0 | 4 | 465 | 64 | 0 | 1.57 |
| deep_dense | 15.0 | 4 | 465 | 64 | 0 | 1.57 |
| deep_dense | 15.0 | 5 | 454 | 64 | 0 | 1.57 |
| deep_dense | 15.0 | 6 | 438 | 64 | 0 | 1.56 |
| deep_dense | 15.0 | 8 | 416 | 64 | 0 | 1.57 |
| deep_dense | 12.0 | 4 | 366 | 64 | 0 | 1.89 |
| deep_dense | 12.0 | 5 | 357 | 64 | 0 | 1.89 |
| deep_dense | 12.0 | 6 | 345 | 64 | 0 | 1.88 |
| deep_dense | 12.0 | 8 | 331 | 64 | 0 | 1.89 |
| deep_dense | 20.0 | 4 | 532 | 63 | 1 | 1.37 |
| deep_dense | 20.0 | 5 | 511 | 63 | 1 | 1.37 |
| deep_dense | 20.0 | 6 | 480 | 63 | 1 | 1.37 |

## T1=20 deep champion — `zero_fill_dense`

- **324 calls / 64 days** · zero **0** · 5.06/day-all · avg SL **10.97** · RR **1.82**
- SLmax=20.0 gap=4 micros=283
- Hist: `{1: 7, 2: 6, 3: 9, 4: 11, 5: 8, 6: 4, 7: 5, 8: 7, 9: 1, 10: 2, 12: 3, 14: 1}`

### Zero-day oracle autopsy (before fill)

- Zero days: **0** · oracle path-wins on them: **0**
- Top patterns on zero days: []
- Feature hits: `{}`

### Calls (sample)

| Day | HM | Side | Pattern | Family | Slot | SL style | SL |
|---|---|---|---|---|---|---|---:|
| 2026-08-06 | 12:20 | SELL | bear_run3 | runs | mid | `prev` | 14.7 |
| 2026-08-06 | 13:27 | BUY | bull_run2 | runs | aft | `prev` | 13.6 |
| 2026-08-06 | 13:39 | SELL | bear_run3 | runs | aft | `prev` | 19.35 |
| 2026-08-06 | 14:37 | SELL | three_outside_dn | three | close | `prev` | 5.5 |
| 2026-08-06 | 14:52 | SELL | bear_run3 | runs | close | `sig` | 5.2 |
| 2026-08-07 | 11:06 | BUY | bull_run2 | runs | morn | `prev` | 10.55 |
| 2026-08-07 | 11:40 | SELL | belt_bear | belt_maru | mid | `prev` | 6.0 |
| 2026-08-07 | 12:26 | BUY | bull_run2 | runs | mid | `p75` | 13.39 |
| 2026-08-07 | 13:55 | SELL | three_crows | three | aft | `p75` | 12.04 |
| 2026-08-10 | 09:34 | SELL | three_outside_dn | three | open | `prev` | 16.7 |
| 2026-08-10 | 10:19 | BUY | bull_run3 | runs | morn | `sig` | 4.95 |
| 2026-08-10 | 10:26 | SELL | three_outside_dn | three | morn | `min_ps` | 5.65 |
| 2026-08-11 | 09:56 | BUY | bull_run2 | runs | open | `cap15` | 15.0 |
| 2026-08-11 | 12:20 | BUY | bull_run2 | runs | mid | `p60` | 4.68 |
| 2026-08-11 | 14:28 | SELL | belt_bear | belt_maru | aft | `min_ps` | 5.1 |
| 2026-08-12 | 10:42 | SELL | bear_run3 | runs | morn | `min_ps` | 5.85 |
| 2026-08-12 | 13:42 | SELL | three_outside_dn | three | aft | `p75` | 7.76 |
| 2026-08-13 | 10:13 | BUY | bull_run2 | runs | morn | `cap15` | 15.0 |
| 2026-08-13 | 12:42 | SELL | bear_run2 | runs | mid | `prev` | 7.35 |
| 2026-08-13 | 14:01 | SELL | three_outside_dn | three | aft | `prev` | 16.15 |
| 2026-08-14 | 13:37 | BUY | three_outside_up | three | aft | `cap8` | 5.85 |
| 2026-08-17 | 10:38 | SELL | bear_run3 | runs | morn | `p60` | 4.05 |
| 2026-08-17 | 11:27 | BUY | bull_run3 | runs | morn | `prev` | 10.95 |
| 2026-08-17 | 12:45 | BUY | three_outside_up | three | mid | `sig` | 7.45 |
| 2026-08-17 | 14:54 | BUY | three_outside_up | three | close | `cap10` | 10.0 |
| 2026-08-18 | 10:40 | SELL | marubozu_bear | belt_maru | morn | `sig` | 9.75 |
| 2026-08-18 | 11:18 | SELL | three_crows | three | morn | `sig` | 5.45 |
| 2026-08-19 | 09:30 | SELL | marubozu_bear | belt_maru | open | `sig` | 10.35 |
| 2026-08-19 | 10:09 | SELL | bear_engulf | engulf | morn | `sig` | 6.95 |
| 2026-08-19 | 14:14 | SELL | belt_bear | belt_maru | aft | `sig` | 5.5 |
| 2026-08-20 | 13:01 | BUY | bull_engulf | engulf | aft | `p75` | 4.0 |
| 2026-08-21 | 10:23 | BUY | bull_run3 | runs | morn | `prev` | 11.3 |
| 2026-08-21 | 10:52 | BUY | bull_run3 | runs | morn | `cap8` | 8.0 |
| 2026-08-21 | 13:15 | SELL | bear_run3 | runs | aft | `p60` | 4.0 |
| 2026-08-24 | 09:30 | SELL | bear_run3 | runs | open | `cap8` | 7.6 |
| 2026-08-24 | 09:54 | SELL | belt_bear | belt_maru | open | `min_ps` | 4.25 |
| 2026-08-24 | 11:23 | SELL | bear_run3 | runs | morn | `p60` | 7.83 |
| 2026-08-24 | 13:06 | SELL | three_outside_dn | three | aft | `cap15` | 15.0 |
| 2026-08-24 | 14:12 | SELL | bear_run3 | runs | aft | `min_ps` | 6.3 |
| 2026-08-24 | 14:42 | SELL | bear_engulf | engulf | close | `cap10` | 9.4 |
| 2026-08-25 | 09:44 | SELL | belt_bear | belt_maru | open | `prev` | 11.5 |
| 2026-08-25 | 09:59 | SELL | three_outside_dn | three | open | `min_ps` | 6.95 |
| 2026-08-25 | 12:21 | SELL | bear_engulf | engulf | mid | `prev` | 8.7 |
| 2026-08-26 | 13:46 | BUY | bull_engulf | engulf | aft | `min_ps` | 5.55 |
| 2026-08-27 | 09:36 | SELL | bear_run2 | runs | open | `cap15` | 15.0 |
| … | | | | | | | 279 more |

### T1=20 top packs

| Kind | SLmax | Gap | Calls | Days | Zero | RR |
|---|---:|---:|---:|---:|---:|---:|
| zero_fill_dense | 20.0 | 4 | 324 | 64 | 0 | 1.82 |
| deep_dense | 20.0 | 4 | 324 | 64 | 0 | 1.82 |
| deep_dense | 20.0 | 5 | 317 | 64 | 0 | 1.82 |
| deep_dense | 20.0 | 6 | 306 | 64 | 0 | 1.82 |
| deep_dense | 15.0 | 4 | 297 | 64 | 0 | 2.05 |
| deep_dense | 15.0 | 5 | 290 | 64 | 0 | 2.05 |
| deep_dense | 20.0 | 8 | 290 | 64 | 0 | 1.83 |
| deep_dense | 15.0 | 6 | 282 | 64 | 0 | 2.05 |
| deep_dense | 15.0 | 8 | 268 | 64 | 0 | 2.07 |
| deep_dense | 12.0 | 4 | 217 | 62 | 2 | 2.48 |
| deep_dense | 12.0 | 5 | 213 | 62 | 2 | 2.48 |
| deep_dense | 12.0 | 6 | 209 | 62 | 2 | 2.48 |

## Policy

- **HELD10** T1=10 deep PATH — locked
- **HELD15** prior more-calls T1=15 — locked; deeper pack is additive if better
- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_t15_t20_deeper`



## HELD lock + Nov9 forward

See [`NIFTY_1M_SCALP_HELD_LOCK_FWD_NOV9.md`](NIFTY_1M_SCALP_HELD_LOCK_FWD_NOV9.md) (`2026-11-09`→`2026-11-16`).
- **HELD10** locked · FWD 10 calls @ **50.0%** (5/5 days)
- **HELD15** locked · FWD 11 calls @ **45.45%** (5/5 days)
- **HELD20** locked · FWD 6 calls @ **50.0%** (4/5 days)
