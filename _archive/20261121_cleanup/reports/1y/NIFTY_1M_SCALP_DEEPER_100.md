# NIFTY 1m — **deeper scalp 100%** densification

**Not live.** Wick/ATR/stack features · score picker · re-entry · deeper micros.

- Prior PATH union baseline: **187 calls / 64 days** (~2.9/day)
- **Current champion: 307 calls / 64 days (4.8/day)** · gap8 · avg SL 8.78 · both-100 path
- Oracle ceiling: ~21 path-wins/day (SL≤12, T1=10) — still headroom

## Feature lift (calibrate · prev SL 4–12)

- Base path-win rate: **67.7%**

| Feature | N | Win% | Lift |
|---|---:|---:|---:|
| `body70+` | 9619 | 71.3 | +3.5pp |
| `early` | 5847 | 69.6 | +1.9pp |
| `fav_wick>0.3` | 11306 | 68.3 | +0.6pp |
| `align` | 18495 | 68.1 | +0.4pp |
| `continuation` | 15058 | 68.1 | +0.4pp |
| `adv_wick<0.15` | 16450 | 68.0 | +0.3pp |
| `adv_wick<0.25` | 21763 | 68.0 | +0.3pp |
| `stack2==2` | 8489 | 67.8 | +0.0pp |
| `stack2>=1` | 25806 | 67.6 | -0.1pp |
| `morning` | 9873 | 67.5 | -0.2pp |
| `midday` | 13112 | 66.9 | -0.8pp |
| `body_atr>=0.8` | 7882 | 66.6 | -1.2pp |

## Best deep PATH union

- Gap **8** · micros **127** · cells scanned **231**
- Calibrate: **543 calls / 229 days** · 2.37/day · multi-days 164
- Last3m: **307 calls / 64 days** · **4.8/day** · multi-days 64 · max/day 11 · avg SL **8.78**

### Top deep micros

| Cal | L3m | AvgSL | Exit | Cell |
|---:|---:|---:|---|---|
| 13 | 7 | 10.25 | `prev` | `('bull_run2', 'BUY', 1, 'morning', 'adv_mid', 'ba>0.8', 'sl8-12', 'fo_near')` |
| 3 | 6 | 10.12 | `prev` | `('GEOM', 'SELL', 'reversal', 1, 'early', 'b70+', 'sl8-12', 'mid', 'adv_lo', 'ba>0.8', 'st1')` |
| 4 | 5 | 10.41 | `prev` | `('GEOM', 'SELL', 'continuation', 1, 'midday', 'b70+', 'sl8-12', 'mid', 'adv_lo', 'ba>0.8', 'st0')` |
| 4 | 4 | 9.12 | `prev` | `('bear_run2', 'SELL', 1, 'late', 'adv_mid', 'ba>0.8', 'sl8-12', 'fo_near')` |
| 4 | 4 | 9.18 | `sig` | `('GEOM', 'SELL', 'continuation', 1, 'morning', 'b70+', 'sl8-12', 'lo', 'adv_mid', 'ba<0.5', 'st2')` |
| 4 | 4 | 9.55 | `prev` | `('GEOM', 'BUY', 'continuation', 0, 'early', 'b<45', 'sl8-12', 'mid', 'adv_lo', 'ba>0.8', 'st1')` |
| 4 | 4 | 10.39 | `prev` | `('GEOM', 'SELL', 'continuation', 1, 'morning', 'b70+', 'sl8-12', 'lo', 'adv_mid', 'ba<0.5', 'st2')` |
| 3 | 4 | 6.55 | `sig` | `('three_outside_dn', 'SELL', 'reversal', 1, 'early', 'b70+', 'sl8-12', 'adv_lo')` |
| 3 | 4 | 7.38 | `prev` | `('GEOM', 'SELL', 'balanced', 1, 'morning', 'b70+', 'sl4-8', 'lo', 'adv_lo', 'ba<0.5', 'st1')` |
| 3 | 4 | 7.51 | `sig` | `('GEOM', 'SELL', 'balanced', 1, 'morning', 'b70+', 'sl4-8', 'lo', 'adv_lo', 'ba<0.5', 'st1')` |
| 3 | 4 | 9.99 | `prev` | `('GEOM', 'BUY', 'balanced', 0, 'early', 'b70+', 'sl8-12', 'mid', 'adv_lo', 'ba>0.8', 'st1')` |
| 3 | 4 | 10.59 | `prev` | `('three_outside_dn', 'SELL', 'reversal', 1, 'early', 'b70+', 'sl8-12', 'adv_lo')` |
| 8 | 3 | 6.37 | `prev` | `('three_outside_dn', 'SELL', 'continuation', 1, 'morning', 'b<45', 'sl4-8', 'adv_lo')` |
| 7 | 3 | 6.72 | `prev` | `('bull_run2', 'BUY', 'reversal', 0, 'morning', 'b45+', 'sl4-8', 'adv_lo')` |
| 7 | 3 | 9.92 | `prev` | `('GEOM', 'SELL', 'continuation', 1, 'midday', 'b70+', 'sl8-12', 'mid', 'adv_hi', 'ba<0.5', 'st0')` |
| 7 | 3 | 10.08 | `prev` | `('bear_engulf', 'SELL', 'continuation', 1, 'late', 'b70+', 'sl8-12', 'adv_hi')` |
| 6 | 3 | 7.23 | `sig` | `('belt_bear', 'SELL', 1, 'midday', 'adv_lo', 'ba>0.5', 'sl12-16', 'fo_near')` |
| 6 | 3 | 10.12 | `prev` | `('bull_run3', 'BUY', 'reversal', 0, 'morning', 'b<45', 'sl8-12', 'adv_lo')` |
| 6 | 3 | 10.6 | `prev` | `('GEOM', 'BUY', 'reversal', 1, 'midday', 'b70+', 'sl8-12', 'mid', 'adv_lo', 'ba>0.5', 'st1')` |
| 5 | 3 | 6.87 | `prev` | `('GEOM', 'SELL', 'continuation', 0, 'morning', 'b45+', 'sl4-8', 'mid', 'adv_hi', 'ba<0.5', 'st1')` |

### Last3m calls (sample)

| Day | HM | Side | Pattern | SL style | SL |
|---|---|---|---|---|---:|
| 2026-08-06 | 09:31 | SELL | bear_engulf | `prev` | 10.45 |
| 2026-08-06 | 10:05 | SELL | belt_bear | `prev` | 9.55 |
| 2026-08-06 | 11:18 | BUY | bull_run2 | `prev` | 11.7 |
| 2026-08-06 | 11:56 | BUY | bull_run2 | `prev` | 8.9 |
| 2026-08-06 | 12:38 | SELL | bear_run3 | `prev` | 5.25 |
| 2026-08-06 | 13:42 | SELL | marubozu_bear | `sig` | 9.95 |
| 2026-08-07 | 09:33 | SELL | belt_bear | `prev` | 8.2 |
| 2026-08-07 | 11:48 | SELL | three_crows | `sig` | 7.55 |
| 2026-08-07 | 13:34 | SELL | bear_run3 | `prev` | 5.15 |
| 2026-08-07 | 14:12 | SELL | belt_bear | `prev` | 11.9 |
| 2026-08-10 | 09:33 | SELL | bear_engulf | `prev` | 11.05 |
| 2026-08-10 | 10:15 | BUY | marubozu_bull | `sig` | 10.85 |
| 2026-08-10 | 10:42 | SELL | bear_engulf | `prev` | 5.45 |
| 2026-08-10 | 12:10 | BUY | bull_run2 | `prev` | 9.95 |
| 2026-08-10 | 14:20 | BUY | belt_bull | `sig` | 5.7 |
| 2026-08-10 | 14:59 | BUY | bull_run3 | `prev` | 8.35 |
| 2026-08-11 | 09:40 | SELL | bear_run2 | `prev` | 9.45 |
| 2026-08-11 | 11:20 | SELL | bear_engulf | `prev` | 4.75 |
| 2026-08-11 | 11:34 | BUY | bull_run2 | `prev` | 5.9 |
| 2026-08-11 | 13:02 | BUY | bull_kicker | `sig` | 7.1 |
| 2026-08-11 | 13:25 | BUY | bull_run2 | `sig` | 5.4 |
| 2026-08-12 | 09:32 | SELL | bear_run3 | `prev` | 10.7 |
| 2026-08-12 | 10:18 | BUY | bull_run3 | `prev` | 11.9 |
| 2026-08-12 | 11:08 | SELL | bear_run2 | `prev` | 8.1 |
| 2026-08-13 | 09:38 | BUY | bull_kicker | `prev` | 11.55 |
| 2026-08-13 | 13:42 | BUY | bull_run3 | `prev` | 11.25 |
| 2026-08-13 | 13:58 | SELL | belt_bear | `prev` | 6.7 |
| 2026-08-14 | 09:23 | BUY | bull_kicker | `prev` | 9.35 |
| 2026-08-14 | 09:40 | SELL | bear_run2 | `prev` | 11.7 |
| 2026-08-14 | 09:59 | BUY | bull_run2 | `prev` | 8.55 |
| 2026-08-14 | 10:20 | SELL | bear_run3 | `prev` | 7.2 |
| 2026-08-14 | 10:30 | SELL | marubozu_bear | `sig` | 8.5 |
| 2026-08-14 | 13:22 | SELL | bear_engulf | `prev` | 4.2 |
| 2026-08-14 | 14:11 | SELL | bear_run3 | `prev` | 4.65 |
| 2026-08-14 | 14:19 | SELL | bear_run3 | `prev` | 5.8 |
| 2026-08-17 | 09:50 | BUY | bull_run3 | `prev` | 5.55 |
| 2026-08-17 | 10:38 | SELL | bear_run3 | `prev` | 6.75 |
| 2026-08-17 | 11:26 | BUY | bull_run3 | `prev` | 11.95 |
| 2026-08-17 | 14:23 | SELL | bear_run3 | `prev` | 8.45 |
| 2026-08-17 | 14:36 | SELL | three_outside_dn | `prev` | 11.15 |
| 2026-08-18 | 09:32 | SELL | bear_run3 | `prev` | 10.35 |
| 2026-08-18 | 10:01 | SELL | bear_run2 | `prev` | 11.65 |
| 2026-08-18 | 12:57 | SELL | three_outside_dn | `prev` | 6.4 |
| 2026-08-18 | 14:23 | SELL | bear_run3 | `prev` | 5.85 |
| 2026-08-18 | 14:57 | BUY | bull_run3 | `prev` | 8.5 |
| 2026-08-19 | 09:45 | SELL | bear_run2 | `prev` | 8.7 |
| 2026-08-19 | 10:01 | SELL | bear_engulf | `prev` | 6.55 |
| 2026-08-19 | 10:21 | SELL | bear_run3 | `prev` | 8.55 |
| 2026-08-19 | 10:37 | SELL | bear_engulf | `prev` | 7.55 |
| 2026-08-19 | 11:17 | SELL | bear_run3 | `prev` | 6.05 |
| … | | | | | 257 more |

## Gap sweep unions

| Gap | Cal calls | Cal days | L3m calls | L3m days | L3m /day | Multi-days | Micros |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 543 | 229 | 307 | 64 | 4.8 | 64 | 127 |
| 10 | 497 | 223 | 288 | 64 | 4.5 | 64 | 118 |
| 12 | 476 | 222 | 277 | 64 | 4.33 | 64 | 114 |
| 15 | 435 | 214 | 256 | 64 | 4.0 | 61 | 104 |
| 20 | 387 | 209 | 229 | 64 | 3.58 | 60 | 92 |

## Global high-lift rules @100%

- none held both windows


## Policy

- research_only · not_live · deeper densify
- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_deeper_100`
- Related: [`NIFTY_1M_SCALP_MULTICALL_100.md`](NIFTY_1M_SCALP_MULTICALL_100.md)



## Ultra-dense PATH sweep

| T1 | Gap | Mode | Cal calls | Cal days | L3m calls | L3m days | /day | Multi | Max | AvgSL | Micros |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 5 | dense | 362 | 198 | 135 | 53 | 2.55 | 42 | 7 | 8.47 | 82 |
| 8 | 6 | dense | 353 | 197 | 134 | 53 | 2.53 | 42 | 7 | 8.46 | 81 |
| 8 | 8 | dense | 351 | 197 | 133 | 53 | 2.51 | 42 | 7 | 8.45 | 81 |
| 8 | 10 | dense | 339 | 196 | 131 | 53 | 2.47 | 42 | 7 | 8.44 | 79 |
| 8 | 5 | strict | 173 | 133 | 98 | 45 | 2.18 | 32 | 6 | 8.36 | 45 |
| 8 | 6 | strict | 172 | 133 | 98 | 45 | 2.18 | 32 | 6 | 8.36 | 45 |
| 8 | 8 | strict | 168 | 130 | 96 | 45 | 2.13 | 32 | 6 | 8.32 | 44 |
| 8 | 10 | strict | 168 | 130 | 96 | 45 | 2.13 | 32 | 6 | 8.32 | 44 |
| 10 | 5 | dense | 204 | 143 | 81 | 46 | 1.76 | 20 | 5 | 8.75 | 48 |
| 10 | 6 | dense | 197 | 141 | 80 | 46 | 1.74 | 20 | 5 | 8.73 | 47 |
| 10 | 8 | dense | 197 | 141 | 79 | 46 | 1.72 | 20 | 5 | 8.73 | 47 |
| 10 | 10 | dense | 197 | 141 | 79 | 46 | 1.72 | 20 | 5 | 8.73 | 47 |
| 10 | 5 | strict | 106 | 90 | 62 | 38 | 1.63 | 14 | 5 | 8.71 | 29 |
| 10 | 6 | strict | 105 | 90 | 62 | 38 | 1.63 | 14 | 5 | 8.71 | 29 |
| 10 | 8 | strict | 102 | 87 | 60 | 38 | 1.58 | 14 | 4 | 8.65 | 28 |
| 10 | 10 | strict | 102 | 87 | 60 | 38 | 1.58 | 14 | 4 | 8.65 | 28 |

### Ultra champion: T1=8 gap=5 dense

- Last3m **135 calls / 53 days** · **2.55/day** · multi-days 42 · max 7/day · avg SL 8.47
- Calibrate **362 / 198** · micros 82

| Day | HM | Side | Pattern | SL style | SL |
|---|---|---|---|---|---:|
| 2026-08-06 | 11:52 | BUY | bull_run3 | `prev` | 7.0 |
| 2026-08-06 | 13:46 | SELL | bear_run2 | `prev` | 8.3 |
| 2026-08-07 | 13:23 | BUY | bull_run2 | `cap10` | 8.4 |
| 2026-08-07 | 14:03 | SELL | belt_bear | `cap8` | 8.0 |
| 2026-08-10 | 14:36 | SELL | bear_run2 | `cap8` | 8.0 |
| 2026-08-11 | 11:03 | SELL | bear_run3 | `min_ps` | 5.3 |
| 2026-08-11 | 12:01 | SELL | three_outside_dn | `p75` | 6.9 |
| 2026-08-12 | 10:31 | BUY | bull_run2 | `prev` | 10.6 |
| 2026-08-14 | 10:35 | BUY | bull_run2 | `cap8` | 8.0 |
| 2026-08-14 | 13:22 | SELL | bear_engulf | `prev` | 4.2 |
| 2026-08-17 | 12:37 | BUY | three_outside_up | `cap8` | 6.65 |
| 2026-08-19 | 13:13 | SELL | bear_run3 | `prev` | 9.15 |
| 2026-08-19 | 14:13 | SELL | bear_run2 | `cap8` | 8.0 |
| 2026-08-24 | 12:10 | BUY | bull_run2 | `min_ps` | 6.6 |
| 2026-08-24 | 12:37 | SELL | bear_engulf | `prev` | 4.9 |
| 2026-08-25 | 09:44 | SELL | belt_bear | `prev` | 11.5 |
| 2026-08-25 | 10:21 | SELL | bear_run3 | `prev` | 6.15 |
| 2026-08-25 | 11:54 | BUY | bull_run3 | `prev` | 12.0 |
| 2026-08-25 | 12:42 | SELL | bear_run3 | `p75` | 4.0 |
| 2026-08-25 | 13:12 | SELL | bear_engulf | `prev` | 7.05 |
| 2026-08-28 | 14:50 | BUY | bull_run3 | `cap8` | 8.0 |
| 2026-08-31 | 10:17 | SELL | bear_run3 | `prev` | 4.4 |
| 2026-08-31 | 11:44 | SELL | belt_bear | `min_ps` | 4.05 |
| 2026-09-01 | 10:44 | SELL | bear_engulf | `cap8` | 4.5 |
| 2026-09-01 | 14:01 | SELL | bear_run3 | `cap8` | 8.0 |
| 2026-09-02 | 10:12 | BUY | marubozu_bull | `prev` | 7.95 |
| 2026-09-02 | 13:00 | BUY | bull_run3 | `p75` | 5.03 |
| 2026-09-02 | 13:26 | BUY | bull_run3 | `p75` | 4.0 |
| 2026-09-03 | 10:35 | SELL | three_outside_dn | `min_ps` | 11.05 |
| 2026-09-03 | 13:20 | SELL | bear_run3 | `prev` | 6.4 |
| 2026-09-04 | 14:26 | BUY | bull_run3 | `prev` | 9.05 |
| 2026-09-04 | 14:45 | SELL | bear_run3 | `p75` | 4.69 |
| 2026-09-07 | 09:58 | SELL | evening_star | `prev` | 10.7 |
| 2026-09-07 | 11:48 | SELL | belt_bear | `min_ps` | 4.1 |
| 2026-09-09 | 09:41 | SELL | bear_engulf | `sig` | 7.15 |
| 2026-09-09 | 10:09 | BUY | bull_kicker | `min_ps` | 5.5 |
| 2026-09-09 | 11:10 | SELL | bear_run3 | `prev` | 7.05 |
| 2026-09-09 | 14:07 | SELL | belt_bear | `sig` | 5.55 |
| 2026-09-10 | 11:32 | SELL | marubozu_bear | `cap12` | 12.0 |
| 2026-09-15 | 11:36 | BUY | bull_run2 | `cap12` | 12.0 |
| … | | | | | 95 more |


## Push beyond 307

- Extra keys + swing2 + min_l3m=1 did **not** beat deep gap8 (**307 @ 4.8/day** still champion).
- Best of this push: gap **4** `push1` → 168 calls / 58 days (2.9/day) · avg SL 8.86 (worse pack from overlap).
- Calibrate for that pack: **502 / 230** · micros 120

| Gap | Mode | Cal | L3m | /day | Multi | Max | AvgSL | Micros |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 4 | strict2 | 161 | 90 | 2.05 | 27 | 5 | 8.97 | 42 |
| 4 | push1 | 502 | 168 | 2.9 | 47 | 7 | 8.86 | 120 |
| 4 | push1_cal3 | 498 | 166 | 2.86 | 47 | 7 | 8.87 | 118 |
| 5 | strict2 | 161 | 90 | 2.05 | 27 | 5 | 8.97 | 42 |
| 5 | push1 | 501 | 168 | 2.9 | 47 | 7 | 8.86 | 120 |
| 5 | push1_cal3 | 497 | 166 | 2.86 | 47 | 7 | 8.87 | 118 |
| 6 | strict2 | 156 | 88 | 2.0 | 27 | 5 | 9.03 | 41 |
| 6 | push1 | 483 | 164 | 2.83 | 47 | 7 | 8.87 | 117 |
| 6 | push1_cal3 | 477 | 160 | 2.76 | 46 | 6 | 8.85 | 114 |
| 8 | strict2 | 152 | 86 | 1.95 | 27 | 4 | 8.87 | 40 |
| 8 | push1 | 462 | 158 | 2.72 | 46 | 7 | 8.84 | 113 |
| 8 | push1_cal3 | 456 | 154 | 2.66 | 45 | 6 | 8.82 | 110 |
| 10 | strict2 | 149 | 84 | 1.91 | 27 | 4 | 8.82 | 39 |
| 10 | push1 | 461 | 157 | 2.71 | 46 | 7 | 8.83 | 113 |
| 10 | push1_cal3 | 455 | 153 | 2.64 | 45 | 6 | 8.81 | 110 |


## HELD lock + Nov9 forward

See [`NIFTY_1M_SCALP_HELD_LOCK_FWD_NOV9.md`](NIFTY_1M_SCALP_HELD_LOCK_FWD_NOV9.md) (`2026-11-09`→`2026-11-16`).
- **HELD10** locked · FWD 10 calls @ **50.0%** (5/5 days)
- **HELD15** locked · FWD 11 calls @ **45.45%** (5/5 days)
- **HELD20** locked · FWD 6 calls @ **50.0%** (4/5 days)
