# DENSE_Y2 / DENSE_Y3 — **full year 2020** (blind OOS)

Train lock was **2021→2026**. 2020 was **never** used to pick micros → true unknown year.

Data: `2020-01-01 09:15:00+05:30` → `2020-12-31 15:29:00+05:30` · bars **94120** · events **60749** · days **251**
Rules: T1=**20.0** · SL≤**10.0** · path (T1 before structure SL) · gap=1m
SL styles: `prev, sig, min_ps, cap8, cap10, p75, p60`

## Exact logic (both books — same engine)

1. **Signal**: textbook candle pattern completes on 1m (bull → BUY, bear → SELL) in session window ~09:20–15:00.
2. **Fingerprint**: each bar gets deep+A keys (pattern, side, prior-3 shape, structure, VIX regime, RSI/body/clock bins).
3. **Micro book**: a micro is one locked fingerprint `k` + one SL style `st` that was **100% path-clean** on enough train years (Y2 ≥2 years, Y3 ≥3 years) with SL in 4…10.
4. **Call**: first matching micro on that bar; SL from that style; **win only if T1=20 hits before SL**.
5. **Dense difference only**: Y2 keeps more micros (looser year count) → more calls; Y3 is stricter → fewer/safer historically.

| Book | Micros | How built | Intent |
|---|---:|---|---|
| **DENSE_Y3** | 246 | clean fingerprint cells seen in **≥3** train years, never dirty | fewer calls, higher bar |
| **DENSE_Y2** | 1001 | same cells but **≥2** train years | denser cover (~1.7 cpd on 21–26) |

| Book | Calls | Hit% | all_win | Days w/ call | Cover | Avg SL | 1/day n | 1/day hit |
|---|---:|---:|:---:|---:|---:|---:|---:|---:|
| **DENSE_Y3** | 168 | 23.21% | False | 120 | 47.8% | 6.96 | 120 | 22.5% |

### DENSE_Y3 by month

| Month | Calls | Hit% | Days hit | Days | Cover | Avg SL |
|---|---:|---:|---:|---:|---:|---:|
| 2020-01 | 12 | 25.0% | 9 | 23 | 39.1% | 5.25 |
| 2020-02 | 12 | 16.67% | 8 | 20 | 40.0% | 6.95 |
| 2020-03 | 20 | 20.0% | 11 | 21 | 52.4% | 8.05 |
| 2020-04 | 19 | 10.53% | 14 | 18 | 77.8% | 7.16 |
| 2020-05 | 9 | 22.22% | 7 | 19 | 36.8% | 6.99 |
| 2020-06 | 17 | 29.41% | 13 | 22 | 59.1% | 7.34 |
| 2020-07 | 17 | 23.53% | 10 | 23 | 43.5% | 7.21 |
| 2020-08 | 16 | 25.0% | 14 | 21 | 66.7% | 6.59 |
| 2020-09 | 16 | 31.25% | 11 | 22 | 50.0% | 6.93 |
| 2020-10 | 12 | 25.0% | 9 | 21 | 42.9% | 6.39 |
| 2020-11 | 10 | 10.0% | 7 | 19 | 36.8% | 7.06 |
| 2020-12 | 8 | 50.0% | 7 | 22 | 31.8% | 6.44 |

### DENSE_Y3 mix

- Wins **39** · Losses **129**
- Top patterns: bear_engulf×19, three_outside_up×16, belt_bull×13, belt_bear×12, bear_run3×12, piercing×11, dark_cloud×10, bear_run2×9
- Top SL styles: cap8×30, p60×29, p75×28, cap10×26, prev×24, sig×20, min_ps×11

#### DENSE_Y3 sample losses (first 25)

| Day | HM | Side | Pattern | SL style | SL | MFE |
|---|---|---|---|---|---:|---:|
| 2020-01-01 | 10:06 | SELL | bear_run2 | p75 | 4.0 | 23.5 |
| 2020-01-06 | 10:17 | SELL | bear_kicker | p75 | 4.0 | 67.9 |
| 2020-01-06 | 10:30 | BUY | marubozu_bull | cap8 | 6.4 | 12.0 |
| 2020-01-08 | 10:44 | SELL | bear_engulf | prev | 5.6 | 32.4 |
| 2020-01-10 | 13:45 | SELL | marubozu_bear | sig | 4.0 | 41.6 |
| 2020-01-16 | 10:22 | BUY | bull_run2 | p60 | 4.0 | 0.5 |
| 2020-01-22 | 13:15 | BUY | bull_kicker | cap8 | 6.2 | 0.7 |
| 2020-01-24 | 13:20 | SELL | bear_kicker | p60 | 4.0 | 1.4 |
| 2020-01-27 | 11:28 | BUY | rising_3_methods | p75 | 4.0 | 17.4 |
| 2020-02-01 | 10:54 | BUY | bull_run3 | cap10 | 5.0 | 26.6 |
| 2020-02-03 | 14:23 | BUY | bull_run2 | cap10 | 10.0 | 150.7 |
| 2020-02-05 | 09:35 | BUY | belt_bull | p75 | 10.0 | 14.5 |
| 2020-02-05 | 11:01 | BUY | inv_hammer | prev | 4.4 | 6.2 |
| 2020-02-06 | 09:35 | SELL | belt_bear | prev | 4.0 | 37.0 |
| 2020-02-07 | 10:10 | BUY | three_outside_up | cap8 | 8.0 | 1.2 |
| 2020-02-07 | 10:11 | BUY | bull_run3 | cap10 | 7.1 | 0.0 |
| 2020-02-07 | 11:36 | SELL | evening_star | p75 | 4.0 | 14.8 |
| 2020-02-18 | 12:49 | BUY | marubozu_bull | prev | 6.9 | 29.3 |
| 2020-02-24 | 09:26 | SELL | belt_bear | p75 | 9.0 | 0.7 |
| 2020-03-03 | 12:22 | SELL | bear_run2 | cap10 | 10.0 | 27.6 |
| 2020-03-05 | 10:31 | SELL | bear_run3 | cap10 | 10.0 | 5.2 |
| 2020-03-05 | 12:45 | BUY | belt_bull | min_ps | 9.1 | 23.9 |
| 2020-03-06 | 14:23 | SELL | bear_engulf | cap8 | 6.5 | 411.7 |
| 2020-03-09 | 11:44 | SELL | bear_run3 | sig | 6.8 | 235.0 |
| 2020-03-09 | 13:37 | SELL | bear_run2 | cap8 | 8.0 | 0.0 |

| **DENSE_Y2** | 586 | 23.89% | False | 210 | 83.7% | 6.61 | 210 | 20.0% |

### DENSE_Y2 by month

| Month | Calls | Hit% | Days hit | Days | Cover | Avg SL |
|---|---:|---:|---:|---:|---:|---:|
| 2020-01 | 30 | 13.33% | 16 | 23 | 69.6% | 5.28 |
| 2020-02 | 36 | 25.0% | 14 | 20 | 70.0% | 6.09 |
| 2020-03 | 72 | 27.78% | 18 | 21 | 85.7% | 7.47 |
| 2020-04 | 64 | 10.94% | 17 | 18 | 94.4% | 7.08 |
| 2020-05 | 56 | 33.93% | 18 | 19 | 94.7% | 7.05 |
| 2020-06 | 61 | 26.23% | 21 | 22 | 95.5% | 6.67 |
| 2020-07 | 64 | 23.44% | 21 | 23 | 91.3% | 6.54 |
| 2020-08 | 45 | 26.67% | 18 | 21 | 85.7% | 6.18 |
| 2020-09 | 50 | 32.0% | 17 | 22 | 77.3% | 6.25 |
| 2020-10 | 44 | 15.91% | 19 | 21 | 90.5% | 6.18 |
| 2020-11 | 35 | 14.29% | 14 | 19 | 73.7% | 6.59 |
| 2020-12 | 29 | 34.48% | 17 | 22 | 77.3% | 6.6 |

### DENSE_Y2 mix

- Wins **140** · Losses **446**
- Top patterns: bear_engulf×62, three_outside_dn×54, bull_engulf×51, three_outside_up×46, belt_bear×36, bear_run2×29, bear_run3×29, belt_bull×25
- Top SL styles: sig×123, p75×107, p60×105, prev×98, cap8×90, cap10×35, min_ps×28

#### DENSE_Y2 sample losses (first 25)

| Day | HM | Side | Pattern | SL style | SL | MFE |
|---|---|---|---|---|---:|---:|
| 2020-01-01 | 10:06 | SELL | bear_run2 | p75 | 4.0 | 23.5 |
| 2020-01-01 | 10:16 | BUY | inv_hammer | p75 | 4.0 | 11.4 |
| 2020-01-01 | 14:02 | SELL | marubozu_bear | p75 | 4.0 | 19.0 |
| 2020-01-01 | 14:14 | SELL | bear_run2 | prev | 7.6 | 12.6 |
| 2020-01-01 | 14:56 | SELL | marubozu_bear | p75 | 4.2 | 5.5 |
| 2020-01-01 | 14:58 | SELL | marubozu_bear | p75 | 4.0 | 2.4 |
| 2020-01-01 | 14:59 | SELL | bear_run3 | prev | 5.9 | 0.0 |
| 2020-01-06 | 10:17 | SELL | bear_kicker | p75 | 4.0 | 67.9 |
| 2020-01-06 | 10:30 | BUY | marubozu_bull | cap8 | 6.4 | 12.0 |
| 2020-01-07 | 14:37 | BUY | piercing | p60 | 4.0 | 19.2 |
| 2020-01-08 | 10:44 | SELL | bear_engulf | prev | 5.6 | 32.4 |
| 2020-01-09 | 13:18 | BUY | bull_kicker | p75 | 4.0 | 11.6 |
| 2020-01-10 | 09:25 | SELL | bear_engulf | p75 | 4.0 | 18.5 |
| 2020-01-10 | 09:26 | SELL | three_outside_dn | p75 | 5.3 | 14.3 |
| 2020-01-10 | 13:45 | SELL | marubozu_bear | sig | 4.0 | 41.6 |
| 2020-01-14 | 09:44 | SELL | three_crows | p75 | 6.0 | 11.2 |
| 2020-01-15 | 11:52 | BUY | bull_kicker | p75 | 4.0 | 3.2 |
| 2020-01-16 | 10:22 | BUY | bull_run2 | p60 | 4.0 | 0.5 |
| 2020-01-20 | 13:54 | SELL | belt_bear | p60 | 4.0 | 96.4 |
| 2020-01-22 | 13:15 | BUY | bull_kicker | cap8 | 6.2 | 0.7 |
| 2020-01-24 | 10:17 | SELL | bear_kicker | prev | 6.2 | 20.9 |
| 2020-01-24 | 13:20 | SELL | bear_kicker | p60 | 4.0 | 1.4 |
| 2020-01-27 | 11:28 | BUY | rising_3_methods | p75 | 4.0 | 17.4 |
| 2020-01-29 | 09:28 | BUY | bull_run2 | prev | 8.8 | 21.9 |
| 2020-01-30 | 11:13 | BUY | three_soldiers | p60 | 4.0 | 17.4 |

## Simple read

- Same **call engine** for Y2 and Y3; only the **micro list size/strictness** differs.
- 2020 is **pre-train** → hit% here is the real generalization check (COVID year, high VIX).
- If hit% collapses vs 2021–26 lock, fingerprints overfit that era; denser Y2 usually drops more than Y3.

Elapsed: 113.8s
