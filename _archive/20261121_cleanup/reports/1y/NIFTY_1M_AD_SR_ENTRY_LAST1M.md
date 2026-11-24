# NIFTY 1m — A/D + S/R Entry Hunt (last ~1 month)

> **RESEARCH ONLY — not wired to Scalper / live.**

Sessions **2026-10-15 → 2026-11-16** (22 days) · horizon 90 bars · 09:30–14:30.

## How we identify a “move” (entry accuracy)

After a candidate BUY/SELL bar we measure the next ~90 minutes:

| Metric | Meaning |
|---|---|
| **MFE20/30/40** | Favourable excursion ≥ 20 / 30 / 40 pts |
| **OneDir** | MFE≥20 and MFE ≥ 2×MAE (one-way dominance) |
| **Dom** | MFE≥15 and MFE ≥ 1.5×MAE |
| **Fav1st** | +8 pts favour before −5 adverse |

## Theory stack (from public Wyckoff / A/D / breakout docs)

1. **Spring** — sweep below support, close back inside → BUY (accumulation reclaim)
2. **Upthrust** — sweep above resistance, close back inside → SELL (distribution reject)
3. **Acceptance break** — close beyond S/R with control (not wick-only)
4. **Retest continuation** — backed by broken level, momentum + clear path
5. **LPS bounce + A/D** — bounce at S/R with A/D / OBV with side
6. **A/D impulse** — A/D∧OBV with side + strong body + clear path

A/D on NIFTY uses **Money Flow Multiplier × range proxy** (index volume often 0).

## Move atlas (among HELD in window)

- HELD events: **1235**
- OneDir among HELD: **522** (42.27%)
- MFE≥40 among HELD: **780**

| Regime (OneDir HELD) | n | %AD_with | %Spring/UT | %bounce | %clear |
|---|---:|---:|---:|---:|---:|
| trend | 354 | 81.4 | 55.4 | 53.7 | 13.6 |
| failed_break_risk | 104 | 89.4 | 32.7 | 33.7 | 0.0 |
| mixed | 44 | 50.0 | 47.7 | 54.5 | 22.7 |
| hold_break | 16 | 68.8 | 81.2 | 68.8 | 31.2 |
| flip | 3 | 100.0 | 66.7 | 66.7 | 0.0 |
| break_attempt | 1 | 0.0 | 100.0 | 100.0 | 0.0 |

## Gate sweep (rank by score · Dom/OneDir/MFE30)

| Gate | n | Dom% | OneDir% | Fav1st% | MFE20 | MFE30 | MFE40 | avgMFE | avgMAE | edge | score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `hold_break+AD+clear15` | 5 | **60.0** | **60.0** | 80.0 | 100.0 | 80.0 | 60.0 | 134.14 | 69.89 | 64.25 | 58.0 |
| `TierAB+AD+clear15` | 7 | **57.14** | **57.14** | 71.43 | 100.0 | 71.43 | 57.14 | 120.37 | 59.52 | 60.85 | 55.03 |
| `LPS_BOUNCE+AD+HELD+clear15` | 46 | **47.83** | **39.13** | 47.83 | 84.78 | 80.43 | 67.39 | 80.91 | 62.74 | 18.17 | 51.31 |
| `SPRING+AD+HELD` | 266 | **50.38** | **42.86** | 44.36 | 75.94 | 68.42 | 62.03 | 69.39 | 49.08 | 20.31 | 50.75 |
| `RETEST_CONT+AD+OBV+HELD` | 59 | **44.07** | **37.29** | 50.85 | 83.05 | 79.66 | 62.71 | 80.12 | 65.52 | 14.6 | 49.49 |
| `SPRING+AD (BUY fail-break reclaim)` | 645 | **47.6** | **42.33** | 41.4 | 75.66 | 68.99 | 62.33 | 72.74 | 55.22 | 17.52 | 49.41 |
| `HELD` | 1235 | **46.8** | **42.27** | 42.67 | 78.06 | 69.8 | 63.16 | 67.99 | 60.31 | 7.68 | 49.4 |
| `HELD+AD+OBV_with` | 940 | **46.6** | **42.13** | 42.34 | 78.3 | 70.11 | 63.3 | 69.21 | 61.27 | 7.94 | 49.31 |
| `SPRING|UPTHRUST + AD+HELD` | 545 | **46.79** | **41.65** | 46.06 | 76.33 | 68.62 | 61.83 | 66.27 | 61.8 | 4.47 | 49.28 |
| `RETEST_CONT+AD` | 115 | **45.22** | **40.87** | 46.09 | 77.39 | 72.17 | 60.0 | 71.59 | 61.71 | 9.88 | 49.17 |
| `HELD+AD_with` | 994 | **46.38** | **41.95** | 42.35 | 77.77 | 69.52 | 62.78 | 68.19 | 61.62 | 6.57 | 49.05 |
| `bounce+backed+ctrl+sweep+AD` | 214 | **46.73** | **41.12** | 44.39 | 74.77 | 67.29 | 58.41 | 67.67 | 64.51 | 3.15 | 48.64 |
| `HELD+AD+clear15` | 128 | **43.75** | **39.84** | 44.53 | 82.03 | 73.44 | 62.5 | 72.74 | 62.5 | 10.24 | 48.4 |
| `HELD+AD+OBV+clear15+ctrl` | 98 | **43.88** | **38.78** | 50.0 | 80.61 | 71.43 | 59.18 | 71.68 | 61.97 | 9.71 | 48.22 |
| `CHOCH+AD+HELD` | 5 | **60.0** | **60.0** | 20.0 | 100.0 | 60.0 | 60.0 | 58.16 | 48.17 | 9.99 | 48.0 |
| `UPTHRUST+AD+HELD` | 279 | **43.37** | **40.5** | 47.67 | 76.7 | 68.82 | 61.65 | 63.3 | 73.94 | -10.64 | 47.89 |
| `LPS_BOUNCE+AD` | 1456 | **44.92** | **40.52** | 42.03 | 74.04 | 67.31 | 59.0 | 65.94 | 63.44 | 2.5 | 47.57 |
| `ALL textbook sess` | 4349 | **44.24** | **38.91** | 40.26 | 75.63 | 66.89 | 58.47 | 65.28 | 63.88 | 1.4 | 46.51 |
| `UPTHRUST+AD (SELL fail-break reject)` | 1097 | **43.39** | **38.2** | 41.66 | 73.66 | 66.09 | 57.16 | 60.69 | 70.07 | -9.38 | 45.94 |
| `AD_IMPULSE (A/D+OBV+ctrl+clear)` | 173 | **41.62** | **37.57** | 41.62 | 76.88 | 68.79 | 56.07 | 63.24 | 64.81 | -1.57 | 45.64 |
| `AD_IMPULSE+HELD` | 82 | **40.24** | **35.37** | 47.56 | 79.27 | 69.51 | 56.1 | 69.0 | 63.89 | 5.11 | 45.12 |
| `CHOCH_proxy+AD+clear15` | 10 | **40.0** | **30.0** | 30.0 | 70.0 | 60.0 | 60.0 | 46.84 | 86.66 | -39.82 | 35.5 |
| `bounce+backed+ctrl+sweep+AD+HELD+clear` | 4 | **25.0** | **25.0** | 50.0 | 100.0 | 50.0 | 25.0 | 99.08 | 91.64 | 7.44 | 23.7 |
| `AD_DIV+ctrl+clear15` | 4 | **25.0** | **25.0** | 50.0 | 25.0 | 25.0 | 25.0 | 23.53 | 87.46 | -63.94 | 18.7 |
| `ACCEPT_BREAK+AD` | 0 | — | — | — | — | — | — | — | — | — | — |
| `ACCEPT_BREAK+AD+HELD+!extreme` | 0 | — | — | — | — | — | — | — | — | — | — |
| `AD_DIV+HELD+ctrl` | 0 | — | — | — | — | — | — | — | — | — | — |

## Gap-15 books (top gates n≥10)

| Gate | n | Dom% | OneDir% | MFE30 | edge |
|---|---:|---:|---:|---:|---:|
| `LPS_BOUNCE+AD+HELD+clear15` | 38 | 47.37 | 39.47 | 78.95 | 23.6 |
| `SPRING+AD+HELD` | 103 | 46.6 | 42.72 | 64.08 | 15.71 |
| `RETEST_CONT+AD+OBV+HELD` | 40 | 47.5 | 37.5 | 80.0 | 23.07 |
| `SPRING+AD (BUY fail-break reclaim)` | 232 | 46.55 | 41.38 | 66.81 | 18.54 |
| `HELD` | 250 | 45.2 | 40.8 | 69.2 | 5.9 |
| `HELD+AD+OBV_with` | 221 | 44.8 | 41.18 | 67.42 | 3.92 |
| `SPRING|UPTHRUST + AD+HELD` | 184 | 46.2 | 42.93 | 67.39 | 6.75 |
| `RETEST_CONT+AD` | 79 | 45.57 | 41.77 | 68.35 | 10.53 |
| `HELD+AD_with` | 227 | 44.49 | 40.53 | 67.4 | 3.79 |
| `bounce+backed+ctrl+sweep+AD` | 151 | 45.7 | 40.4 | 68.87 | 3.65 |
| `HELD+AD+clear15` | 53 | 47.17 | 39.62 | 77.36 | 21.86 |
| `HELD+AD+OBV+clear15+ctrl` | 48 | 50.0 | 43.75 | 77.08 | 22.5 |
| `UPTHRUST+AD+HELD` | 81 | 45.68 | 43.21 | 71.6 | -4.64 |
| `LPS_BOUNCE+AD` | 337 | 45.7 | 40.95 | 67.95 | 8.63 |
| `ALL textbook sess` | 420 | 40.71 | 34.52 | 63.81 | -2.65 |
| `UPTHRUST+AD (SELL fail-break reject)` | 287 | 42.16 | 36.93 | 65.51 | -14.07 |
| `AD_IMPULSE (A/D+OBV+ctrl+clear)` | 92 | 41.3 | 39.13 | 65.22 | 0.88 |
| `AD_IMPULSE+HELD` | 41 | 46.34 | 41.46 | 75.61 | 20.43 |
| `CHOCH_proxy+AD+clear15` | 10 | 40.0 | 30.0 | 60.0 | -39.82 |

## Samples — best gate `LPS_BOUNCE+AD+HELD+clear15`

### OneDir hits

| Day | HM | Side | Pattern | AD | Spring/UT | room | MFE | MAE |
|---|---|---|---|---|---|---:|---:|---:|
| 2026-10-21 | 13:03 | SELL | belt_bear | True | True | 27.6 | 67.35 | 21.35 |
| 2026-10-21 | 13:11 | SELL | bear_engulf | True | True | 21.5 | 61.25 | 18.7 |
| 2026-10-21 | 13:22 | SELL | bear_run3 | True | True | 19.0 | 74.7 | 18.4 |
| 2026-10-23 | 11:35 | SELL | marubozu_bear | True | True | 19.3 | 80.2 | 24.8 |
| 2026-10-28 | 11:24 | BUY | bull_kicker | True | True | 20.0 | 108.3 | 16.25 |
| 2026-10-28 | 11:57 | BUY | bull_run2 | True | True | 22.3 | 138.85 | 15.8 |
| 2026-10-30 | 11:07 | BUY | bull_run2 | True | True | 21.65 | 112.95 | 0.6 |
| 2026-11-02 | 13:00 | SELL | marubozu_bear | True | True | 17.75 | 73.5 | 11.45 |
| 2026-11-03 | 12:57 | BUY | bull_run3 | True | True | 14.75 | 57.7 | 17.45 |
| 2026-11-04 | 13:18 | BUY | bull_kicker | True | True | 17.3 | 61.15 | 5.75 |
| 2026-11-04 | 13:32 | BUY | bull_run3 | True | True | 69.9 | 53.45 | 21.6 |
| 2026-11-04 | 14:24 | BUY | bull_run3 | True | True | 13.9 | 488.35 | 11.0 |

### Misses (MFE<20)

| Day | HM | Side | into_ext | clear | MFE | MAE |
|---|---|---|---|---|---:|---:|
| 2026-10-16 | 11:30 | BUY | False | True | 15.1 | 38.35 |
| 2026-10-22 | 12:18 | SELL | False | True | 0.8 | 169.85 |
| 2026-10-30 | 13:58 | SELL | False | True | 16.35 | 58.4 |
| 2026-11-04 | 12:15 | SELL | False | True | 0.0 | 179.8 |
| 2026-11-11 | 10:57 | BUY | False | True | 18.95 | 81.1 |
| 2026-11-12 | 12:16 | SELL | False | True | 0.3 | 65.85 |
| 2026-11-16 | 12:15 | BUY | False | True | 5.6 | 61.95 |

## Analysis takeaways (entry only)

1. **`LPS_BOUNCE+AD+HELD+clear15`** — Dom **47.83%** · OneDir **39.13%** · MFE30 80.43% · n=46 · edge=18.17
2. **`SPRING+AD+HELD`** — Dom **50.38%** · OneDir **42.86%** · MFE30 68.42% · n=266 · edge=20.31
3. **`RETEST_CONT+AD+OBV+HELD`** — Dom **44.07%** · OneDir **37.29%** · MFE30 79.66% · n=59 · edge=14.6
4. **`SPRING+AD (BUY fail-break reclaim)`** — Dom **47.6%** · OneDir **42.33%** · MFE30 68.99% · n=645 · edge=17.52
5. **`HELD`** — Dom **46.8%** · OneDir **42.27%** · MFE30 69.8% · n=1235 · edge=7.68

### What “accurate entry” means here

We are **not** scoring EMA34-trail hit% in this study. Goal is: after the signal bar, does price run 20–40+ pts in the same direction with limited adverse?

### Next deepen (still research)

1. Require **2-bar acceptance** after Spring/UT / break (close holds beyond level).
2. Add **5m structure bias** filter before 1m trigger.
3. Split range-day vs trend-day (ATR% / ADX).
4. Re-test same gates on BANKNIFTY last 1m.
5. Only then consider Scalper wiring — **not now**.

Elapsed 19s
