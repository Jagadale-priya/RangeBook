# NIFTY 1m — **HELD scalp logic** + higher-T / lower-SL hunt

**Not live.** Hold the proven T1=10 PATH book. Hunt the same style with **higher target + lower SL** using accurate (low-MAE / high-MFE) move structure.

## ★ HELD logic (do not change) — T1=10 PATH

| Metric | Value |
|---|---|
| Window | last3m 64 days |
| Calls | **307** |
| Days covered | **64 / 64** (every day) |
| Calls / day | **4.8** avg · min 2 · max 11 |
| Avg SL | **8.78** (structure prev/lesser) |
| Hit rule | T1=10 **before** SL · **100%** both windows |
| Gap | 8 min · 127 micros · wick/ATR/stack cells |

This is the **perfect baseline** to hold.

## Accurate-move DNA (low MAE + high MFE)

Moves that can support higher T1 with tight SL look like:

| Label | Window | N | Days | Avg MAE | Avg MFE | Med bars→T | body70% | adv_wick lo% | Top patterns |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `clean15` | cal | 3147 | 265 | 2.79 | 115.82 | 14 | 29.1 | 48.2 | bear_run3:517, bull_run3:453, bear_run2:360 |
| `clean15` | l3m | 823 | 64 | 2.9 | 99.72 | 10 | 30.6 | 52.0 | bear_run3:172, bear_engulf:92, bull_run2:86 |
| `clean20` | cal | 3578 | 266 | 3.24 | 113.64 | 19 | 29.6 | 48.3 | bear_run3:584, bull_run3:515, bear_run2:422 |
| `clean20` | l3m | 959 | 64 | 3.42 | 98.51 | 14 | 30.2 | 51.4 | bear_run3:196, bear_engulf:114, bull_run2:102 |
| `clean25` | cal | 3996 | 266 | 3.69 | 112.61 | 24 | 29.4 | 47.9 | bear_run3:658, bull_run3:583, bear_run2:472 |
| `clean25` | l3m | 1085 | 64 | 3.9 | 97.95 | 18 | 30.4 | 50.7 | bear_run3:226, bear_engulf:138, bear_run2:113 |
| `elite20` | cal | 2733 | 264 | 2.38 | 116.18 | 20 | 29.5 | 48.4 | bear_run3:431, bull_run3:397, bear_run2:310 |
| `elite20` | l3m | 699 | 64 | 2.43 | 102.65 | 16 | 30.8 | 51.4 | bear_run3:157, bear_engulf:79, bull_run2:75 |
| `elite25` | cal | 3139 | 265 | 2.78 | 116.06 | 26 | 29.1 | 48.3 | bear_run3:517, bull_run3:450, bear_run2:358 |
| `elite25` | l3m | 821 | 64 | 2.9 | 99.9 | 18 | 30.7 | 51.9 | bear_run3:172, bear_engulf:91, bull_run2:86 |

### Structure rules implied by accurate moves

1. **Low adverse wick** on signal candle (`adv_wick < 0.15`) — little rejection against trade
2. **Strong body** (`body ≥ 0.70` preferred) — commitment in direction
3. **Tight structure stop** available (`prev SL` often ≤8) — room for cap6/cap8
4. Prefer **session align + continuation** when present
5. Target expansion often prints in a few bars when MAE stays small

## Oracle (last3m) — is high-T + low-SL even feasible?

| T1 | SLmax | Calls | Days | Zero days | /day (all 64) |
|---:|---:|---:|---:|---:|---:|
| 15 | 6 | 1899 | 64 | 0 | 29.67 |
| 15 | 7 | 1994 | 64 | 0 | 31.16 |
| 15 | 8 | 2059 | 64 | 0 | 32.17 |
| 15 | 10 | 2136 | 64 | 0 | 33.38 |
| 20 | 6 | 1715 | 64 | 0 | 26.8 |
| 20 | 7 | 1837 | 64 | 0 | 28.7 |
| 20 | 8 | 1907 | 64 | 0 | 29.8 |
| 20 | 10 | 1985 | 64 | 0 | 31.02 |
| 25 | 6 | 1381 | 64 | 0 | 21.58 |
| 25 | 7 | 1438 | 64 | 0 | 22.47 |
| 25 | 8 | 1480 | 64 | 0 | 23.12 |
| 25 | 10 | 1523 | 64 | 0 | 23.8 |

## Built PATH books — higher T1 + lower SL (both 100%)

| T1 | SLmax | Gap | Mode | Calls | Days | Zero | /day-all | AvgSL | RR | Micros |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 15 | 6 | 5 | dense | 12 | 12 | 52 | 0.19 | 5.36 | 2.8 | 8 |
| 15 | 6 | 5 | strict | 7 | 7 | 57 | 0.11 | 5.16 | 2.91 | 3 |
| 15 | 7 | 5 | dense | 23 | 21 | 43 | 0.36 | 5.79 | 2.59 | 17 |
| 15 | 7 | 5 | strict | 11 | 11 | 53 | 0.17 | 5.36 | 2.8 | 5 |
| 15 | 8 | 5 | dense | 27 | 24 | 40 | 0.42 | 6.39 | 2.35 | 18 |
| 15 | 8 | 5 | strict | 16 | 15 | 49 | 0.25 | 6.26 | 2.4 | 7 |
| 15 | 10 | 10 | dense | 48 | 33 | 31 | 0.75 | 7.53 | 1.99 | 33 |
| 15 | 10 | 10 | strict | 27 | 21 | 43 | 0.42 | 7.2 | 2.08 | 12 |
| 20 | 6 | 5 | dense | 1 | 1 | 63 | 0.02 | 5.6 | 3.57 | 1 |
| 20 | 7 | 5 | dense | 5 | 5 | 59 | 0.08 | 6.21 | 3.22 | 5 |
| 20 | 8 | 5 | dense | 8 | 8 | 56 | 0.12 | 7.12 | 2.81 | 7 |
| 20 | 8 | 5 | strict | 2 | 2 | 62 | 0.03 | 8.0 | 2.5 | 1 |
| 20 | 10 | 5 | dense | 19 | 14 | 50 | 0.3 | 8.3 | 2.41 | 15 |
| 20 | 10 | 5 | strict | 8 | 6 | 58 | 0.12 | 8.76 | 2.28 | 4 |
| 25 | 7 | 5 | dense | 2 | 2 | 62 | 0.03 | 6.2 | 4.03 | 2 |
| 25 | 8 | 5 | dense | 6 | 5 | 59 | 0.09 | 6.91 | 3.62 | 4 |
| 25 | 8 | 5 | strict | 4 | 3 | 61 | 0.06 | 6.86 | 3.64 | 2 |
| 25 | 10 | 5 | dense | 8 | 7 | 57 | 0.12 | 8.93 | 2.8 | 5 |
| 25 | 10 | 5 | strict | 6 | 5 | 59 | 0.09 | 8.83 | 2.83 | 3 |

## Playbook candidates (closest to held quality)

### 1. T1=15 · SLmax=10 · `max_coverage` · gap10 dense

- Last3m: **48 calls / 33 days** · **31 zero-days** · 0.75/day-all
- Avg SL **7.53** · RR **1.99** · micros 33
- Per-day hist: `{1: 21, 2: 10, 3: 1, 4: 1}`

| Day | HM | Side | Pattern | SL style | SL | MAE | MFE |
|---|---|---|---|---|---:|---:|---:|
| 2026-08-06 | 14:30 | SELL | bear_run3 | `sig` | 5.35 | 8.5 | 121.8 |
| 2026-08-07 | 09:25 | SELL | hanging_man | `prev` | 9.6 | 20.0 | 58.2 |
| 2026-08-07 | 13:49 | BUY | bull_run2 | `sig` | 9.4 | 50.7 | 47.5 |
| 2026-08-11 | 09:40 | SELL | bear_run2 | `cap10` | 9.45 | 12.65 | 42.5 |
| 2026-08-11 | 12:20 | BUY | bull_run2 | `p60` | 4.68 | 11.8 | 32.8 |
| 2026-08-14 | 13:22 | SELL | bear_engulf | `prev` | 4.2 | 61.3 | 16.6 |
| 2026-08-18 | 13:57 | SELL | three_outside_dn | `cap10` | 10.0 | 41.25 | 124.4 |
| 2026-08-19 | 14:31 | BUY | bull_run3 | `sig` | 6.1 | 13.75 | 178.5 |
| 2026-08-20 | 14:43 | SELL | bear_run3 | `sig` | 4.05 | 46.8 | 32.0 |
| 2026-08-21 | 09:30 | SELL | bear_engulf | `min_ps` | 8.85 | 45.55 | 15.3 |
| 2026-08-21 | 13:21 | SELL | bear_run3 | `p60` | 5.85 | 12.1 | 14.7 |
| 2026-08-24 | 12:37 | SELL | bear_engulf | `prev` | 4.9 | 2.3 | 43.9 |
| 2026-08-28 | 12:27 | BUY | belt_bull | `prev` | 5.6 | 3.65 | 26.2 |
| 2026-09-03 | 09:39 | BUY | three_outside_up | `cap10` | 10.0 | 85.75 | 16.8 |
| 2026-09-03 | 10:06 | SELL | bear_engulf | `p60` | 4.86 | 9.6 | 78.2 |
| 2026-09-03 | 10:29 | SELL | bear_run2 | `cap10` | 8.5 | 4.75 | 79.9 |
| 2026-09-03 | 12:23 | SELL | bear_run3 | `cap8` | 8.0 | 27.0 | 17.3 |
| 2026-09-08 | 12:40 | SELL | bear_run3 | `p60` | 5.4 | 7.4 | 41.2 |
| 2026-09-09 | 10:31 | SELL | belt_bear | `sig` | 6.3 | 10.1 | 62.8 |
| 2026-09-09 | 11:10 | SELL | bear_run3 | `prev` | 7.05 | 43.0 | 57.7 |
| 2026-09-15 | 14:53 | SELL | bear_run2 | `sig` | 6.6 | 98.1 | 67.0 |
| 2026-09-22 | 12:45 | SELL | bear_run3 | `cap8` | 8.0 | 60.25 | 57.1 |
| 2026-09-23 | 09:31 | SELL | bear_engulf | `p60` | 5.31 | 76.65 | 15.0 |
| 2026-09-23 | 09:54 | SELL | belt_bear | `cap10` | 10.0 | 93.3 | 0.8 |
| 2026-09-23 | 14:34 | SELL | three_crows | `sig` | 6.75 | 3.85 | 237.7 |
| … | | | | | | | 23 more |

### 2. T1=15 · SLmax=8 · `tight_sl` · gap5 dense

- Last3m: **27 calls / 24 days** · **40 zero-days** · 0.42/day-all
- Avg SL **6.39** · RR **2.35** · micros 18
- Per-day hist: `{1: 21, 2: 3}`

| Day | HM | Side | Pattern | SL style | SL | MAE | MFE |
|---|---|---|---|---|---:|---:|---:|
| 2026-08-06 | 14:30 | SELL | bear_run3 | `sig` | 5.35 | 8.5 | 121.8 |
| 2026-08-11 | 12:20 | BUY | bull_run2 | `p60` | 4.68 | 11.8 | 32.8 |
| 2026-08-14 | 13:22 | SELL | bear_engulf | `prev` | 4.2 | 61.3 | 16.6 |
| 2026-08-20 | 14:43 | SELL | bear_run3 | `sig` | 4.05 | 46.8 | 32.0 |
| 2026-08-21 | 13:21 | SELL | bear_run3 | `p60` | 5.85 | 12.1 | 14.7 |
| 2026-08-24 | 12:37 | SELL | bear_engulf | `prev` | 4.9 | 2.3 | 43.9 |
| 2026-08-28 | 12:27 | BUY | belt_bull | `prev` | 5.6 | 3.65 | 26.2 |
| 2026-09-03 | 10:06 | SELL | bear_engulf | `p60` | 4.86 | 9.6 | 78.2 |
| 2026-09-03 | 12:23 | SELL | bear_run3 | `cap8` | 8.0 | 27.0 | 17.3 |
| 2026-09-04 | 09:52 | BUY | bull_run3 | `sig` | 7.75 | 7.35 | 62.3 |
| 2026-09-08 | 12:40 | SELL | bear_run3 | `p60` | 5.4 | 7.4 | 41.2 |
| 2026-09-09 | 11:10 | SELL | bear_run3 | `prev` | 7.05 | 43.0 | 57.7 |
| 2026-09-15 | 14:59 | SELL | bear_run3 | `min_ps` | 6.6 | 106.25 | 58.8 |
| 2026-09-22 | 12:45 | SELL | bear_run3 | `cap8` | 8.0 | 60.25 | 57.1 |
| 2026-09-23 | 09:31 | SELL | bear_engulf | `p60` | 5.31 | 76.65 | 15.0 |
| 2026-09-23 | 14:34 | SELL | three_crows | `sig` | 6.75 | 3.85 | 237.7 |
| 2026-09-24 | 12:05 | BUY | three_outside_up | `cap6` | 6.0 | 161.7 | 3.2 |
| 2026-09-24 | 13:40 | SELL | bear_run3 | `cap8` | 8.0 | 4.5 | 105.9 |
| 2026-09-28 | 14:49 | BUY | three_outside_up | `cap8` | 8.0 | 228.95 | 9.9 |
| 2026-09-29 | 14:51 | BUY | bull_run2 | `min_ps` | 6.15 | 17.85 | 94.1 |
| 2026-10-01 | 10:42 | SELL | bear_kicker | `prev` | 7.6 | 11.7 | 111.6 |
| 2026-10-05 | 12:34 | SELL | bear_run3 | `p60` | 5.61 | 124.9 | 9.7 |
| 2026-10-14 | 10:59 | BUY | three_outside_up | `cap8` | 8.0 | 92.95 | 1.2 |
| 2026-10-19 | 12:47 | SELL | bear_run2 | `p60` | 7.86 | 30.7 | 85.5 |
| 2026-10-22 | 11:04 | BUY | bull_run3 | `cap6` | 6.0 | 158.25 | 41.4 |
| … | | | | | | | 2 more |

### 3. T1=20 · SLmax=10 · `max_coverage` · gap5 dense

- Last3m: **19 calls / 14 days** · **50 zero-days** · 0.3/day-all
- Avg SL **8.3** · RR **2.41** · micros 15
- Per-day hist: `{1: 10, 2: 3, 3: 1}`

| Day | HM | Side | Pattern | SL style | SL | MAE | MFE |
|---|---|---|---|---|---:|---:|---:|
| 2026-08-18 | 13:57 | SELL | three_outside_dn | `cap10` | 10.0 | 41.25 | 124.4 |
| 2026-08-19 | 14:31 | BUY | bull_run3 | `sig` | 6.1 | 13.75 | 178.5 |
| 2026-08-28 | 12:27 | BUY | belt_bull | `prev` | 5.6 | 3.65 | 26.2 |
| 2026-09-03 | 10:06 | SELL | bear_engulf | `cap10` | 8.1 | 9.6 | 78.2 |
| 2026-09-03 | 12:22 | SELL | three_outside_dn | `cap10` | 10.0 | 23.95 | 20.3 |
| 2026-09-09 | 10:31 | SELL | belt_bear | `sig` | 6.3 | 10.1 | 62.8 |
| 2026-09-23 | 09:31 | SELL | bear_engulf | `cap10` | 8.85 | 76.65 | 15.0 |
| 2026-09-23 | 09:54 | SELL | belt_bear | `cap10` | 10.0 | 93.3 | 0.8 |
| 2026-09-23 | 14:34 | SELL | three_crows | `sig` | 6.75 | 3.85 | 237.7 |
| 2026-09-28 | 14:49 | BUY | three_outside_up | `cap8` | 8.0 | 228.95 | 9.9 |
| 2026-10-01 | 10:20 | SELL | bear_run2 | `prev` | 8.8 | 26.95 | 68.4 |
| 2026-10-14 | 10:59 | BUY | three_outside_up | `cap8` | 8.0 | 92.95 | 1.2 |
| 2026-10-19 | 12:47 | SELL | bear_run2 | `p75` | 9.83 | 30.7 | 85.5 |
| 2026-10-23 | 14:09 | SELL | bear_run3 | `p60` | 7.71 | 56.45 | 156.2 |
| 2026-10-23 | 14:16 | BUY | three_outside_up | `cap8` | 8.0 | 178.5 | 93.2 |
| 2026-10-26 | 13:17 | BUY | bull_engulf | `min_ps` | 8.65 | 3.5 | 92.3 |
| 2026-10-30 | 12:31 | SELL | bear_engulf | `p60` | 8.13 | 39.9 | 78.0 |
| 2026-10-30 | 13:04 | SELL | bear_engulf | `p60` | 8.97 | 4.85 | 97.0 |
| 2026-11-02 | 11:37 | SELL | three_outside_dn | `sig` | 9.9 | 43.95 | 97.9 |

### 4. T1=25 · SLmax=10 · `max_coverage` · gap5 dense

- Last3m: **8 calls / 7 days** · **57 zero-days** · 0.12/day-all
- Avg SL **8.93** · RR **2.8** · micros 5
- Per-day hist: `{1: 6, 2: 1}`

| Day | HM | Side | Pattern | SL style | SL | MAE | MFE |
|---|---|---|---|---|---:|---:|---:|
| 2026-08-18 | 13:57 | SELL | three_outside_dn | `cap10` | 10.0 | 41.25 | 124.4 |
| 2026-09-03 | 10:06 | SELL | bear_engulf | `cap10` | 8.1 | 9.6 | 78.2 |
| 2026-09-03 | 12:22 | SELL | three_outside_dn | `cap10` | 10.0 | 23.95 | 20.3 |
| 2026-09-23 | 09:31 | SELL | bear_engulf | `cap10` | 8.85 | 76.65 | 15.0 |
| 2026-09-28 | 14:49 | BUY | three_outside_up | `cap8` | 8.0 | 228.95 | 9.9 |
| 2026-10-19 | 12:47 | SELL | bear_run2 | `p75` | 9.83 | 30.7 | 85.5 |
| 2026-10-23 | 14:16 | BUY | three_outside_up | `cap8` | 8.0 | 178.5 | 93.2 |
| 2026-10-26 | 13:17 | BUY | bull_engulf | `min_ps` | 8.65 | 3.5 | 92.3 |

## Comparison vs held

| Book | T1 | AvgSL | RR | L3m calls | Days | Zero days | /day-all |
|---|---:|---:|---:|---:|---:|---:|---:|
| **HELD** | 10 | 8.78 | 1.14 | 307 | 64 | **0** | 4.8 |
| T1=15 SLmax=10  | 15 | 7.53 | 1.99 | 48 | 33 | 31 | 0.75 |
| T1=15 SLmax=8 tight_sl | 15 | 6.39 | 2.35 | 27 | 24 | 40 | 0.42 |
| T1=20 SLmax=10  | 20 | 8.3 | 2.41 | 19 | 14 | 50 | 0.3 |
| T1=25 SLmax=10  | 25 | 8.93 | 2.8 | 8 | 7 | 57 | 0.12 |

## Verdict

- **Hold T1=10 PATH** for daily coverage + multi calls @100%.
- **Accurate moves exist every day** (e.g. clean15: 823 events / 64 days, avg MAE ~2.9 → MFE ~100).
- Oracle: T1=15 with SL≤8 is path-feasible **every day** (~32/day). So higher-T + lower-SL is **market-real**.
- Current micro-union picker only locks sparse both-100 books (best tight: T1=15 SL≤8 → 27 calls / 24 days, RR~2.35).
- **Next build:** score/rank picker using accurate-move DNA (`adv_wick<0.15`, body70, stack, tight prev) to close oracle→book gap — as a **second book** beside held, not a replacement.

## Policy

- research_only · not_live · held + highT/lowSL hunt
- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_held_hight_lowsl`
- Held source: [`NIFTY_1M_SCALP_DEEPER_100.md`](NIFTY_1M_SCALP_DEEPER_100.md)



## High-T more-calls follow-up

See [`NIFTY_1M_SCALP_HIGHT_MORECALLS_100.md`](NIFTY_1M_SCALP_HIGHT_MORECALLS_100.md).
- T1=15: **103 calls / 44 days** (zero 20) · RR 1.2 · `micro_dense`
- T1=20: **50 calls / 29 days** (zero 35) · RR 1.37 · `micro_dense`
- T1=25: **10 calls / 10 days** (zero 54) · RR 1.75 · `micro_dense`


## HELD lock + Nov9 forward

See [`NIFTY_1M_SCALP_HELD_LOCK_FWD_NOV9.md`](NIFTY_1M_SCALP_HELD_LOCK_FWD_NOV9.md) (`2026-11-09`→`2026-11-16`).
- **HELD10** locked · FWD 10 calls @ **50.0%** (5/5 days)
- **HELD15** locked · FWD 11 calls @ **45.45%** (5/5 days)
- **HELD20** locked · FWD 6 calls @ **50.0%** (4/5 days)
