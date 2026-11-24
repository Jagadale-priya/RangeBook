# NIFTY 1m — **MA last-year INIT** (adaptive T/SL)

Window **2025-11-17 → 2026-11-16** · Train days **175** (`<2026-08-01`) · Hold unknown **73** (`≥2026-08-01`)

## Exact logic under test

1. Signal = textbook 1m candle (bull→BUY / bear→SELL).
2. MA layers: EMA **9/15/21/34/50/100** + SMA **20/50** (same-bar close vs MA, no look-ahead).
3. Noise gates: align / stack-with / pullback-near / hard (align+stack+slope) / clean (hard+close_ok+!fail_risk).
4. **Adaptive bracket**: T1 hint 15/20/25/30 and SL-cap 8/10/12 from MA distance+stack; path win = T1 before structure SL.
5. Blind rule: hold months never used to choose gates or micros.

## A) Gate lift — full calls (adaptive) then **1/day**

| Gate | Train n@hit | Train 1d n@hit cover | Hold n@hit | Hold 1d n@hit cover | AvgT1/SL hold |
|---|---|---|---|---|---|
| `raw` | 41383@32.01% | 175@37.71% 100.0% | 17070@30.83% | 73@35.62% 100.0% | 22.12/7.28 |
| `ema15_align` | 29981@31.46% | 175@33.71% 100.0% | 12339@30.69% | 73@36.99% 100.0% | 25.62/7.3 |
| `ema21_align` | 28618@31.04% | 175@36.0% 100.0% | 11777@30.47% | 73@34.25% 100.0% | 25.68/7.33 |
| `ema34_align` | 26876@30.52% | 175@36.57% 100.0% | 11122@29.74% | 73@36.99% 100.0% | 25.68/7.28 |
| `ema50_align` | 25762@30.14% | 175@34.86% 100.0% | 10684@29.14% | 73@35.62% 100.0% | 25.75/7.28 |
| `stack15_with` | 18928@27.6% | 175@37.14% 100.0% | 7926@27.72% | 73@38.36% 100.0% | 26.1/7.17 |
| `stack21_with` | 17731@26.85% | 175@35.43% 100.0% | 7475@26.96% | 73@35.62% 100.0% | 26.58/7.09 |
| `stack34_with` | 16802@27.85% | 175@34.86% 100.0% | 7167@26.75% | 73@39.73% 100.0% | 26.71/7.1 |
| `pull15` | 2167@29.3% | 175@32.0% 100.0% | 1065@29.2% | 73@34.25% 100.0% | 18.77/5.92 |
| `pull21` | 1880@30.43% | 175@38.86% 100.0% | 902@33.15% | 72@43.06% 98.6% | 17.08/5.82 |
| `pull34` | 1459@34.41% | 173@39.31% 98.9% | 693@31.31% | 71@36.62% 97.3% | 15.35/5.71 |
| `hard15` | 16896@27.64% | 175@37.14% 100.0% | 7095@27.51% | 73@35.62% 100.0% | 26.71/7.14 |
| `hard21` | 16039@26.49% | 175@35.43% 100.0% | 6772@26.65% | 73@34.25% 100.0% | 27.4/7.17 |
| `hard34` | 14742@27.19% | 175@32.57% 100.0% | 6248@26.7% | 73@39.73% 100.0% | 27.4/7.17 |
| `hard50` | 17336@26.82% | 175@33.71% 100.0% | 7317@26.84% | 73@34.25% 100.0% | 27.05/7.17 |
| `clean21` | 5882@28.32% | 175@30.86% 100.0% | 2395@29.69% | 73@41.1% 100.0% | 28.49/7.59 |
| `clean34` | 5179@28.96% | 175@29.14% 100.0% | 2092@29.21% | 73@47.95% 100.0% | 28.7/7.48 |
| `clean50` | 10235@28.63% | 175@34.29% 100.0% | 4072@29.4% | 73@35.62% 100.0% | 27.47/7.37 |

**Top hold 1/day gates:** `clean34`, `pull21`, `clean21`, `stack34_with`, `hard34`

## B) Fixed T20/SL≤10 vs adaptive (selected gates)

| Gate | Mode | Train 1d hit/cover | Hold 1d hit/cover |
|---|---|---|---|
| `raw` | adapt | 37.71% / 100.0% | 35.62% / 100.0% |
| `raw` | t20sl10 | 34.86% / 100.0% | 28.77% / 100.0% |
| `hard21` | adapt | 35.43% / 100.0% | 34.25% / 100.0% |
| `hard21` | t20sl10 | 36.57% / 100.0% | 26.03% / 100.0% |
| `hard34` | adapt | 32.57% / 100.0% | 39.73% / 100.0% |
| `hard34` | t20sl10 | 34.86% / 100.0% | 31.51% / 100.0% |
| `hard50` | adapt | 33.71% / 100.0% | 34.25% / 100.0% |
| `hard50` | t20sl10 | 34.86% / 100.0% | 26.03% / 100.0% |
| `clean21` | adapt | 30.86% / 100.0% | 41.1% / 100.0% |
| `clean21` | t20sl10 | 38.29% / 100.0% | 36.99% / 100.0% |
| `clean34` | adapt | 29.14% / 100.0% | 47.95% / 100.0% |
| `clean34` | t20sl10 | 37.14% / 100.0% | 43.84% / 100.0% |
| `clean50` | adapt | 34.29% / 100.0% | 35.62% / 100.0% |
| `clean50` | t20sl10 | 38.86% / 100.0% | 30.14% / 100.0% |
| `pull21` | adapt | 38.86% / 100.0% | 43.06% / 98.6% |
| `pull21` | t20sl10 | 35.43% / 100.0% | 40.28% / 98.6% |
| `pull34` | adapt | 39.31% / 98.9% | 36.62% / 97.3% |
| `pull34` | t20sl10 | 34.1% / 98.9% | 28.17% / 97.3% |

## C) Clean fingerprint micros (100% train path) → hold unknown

| Book (gate) | Micros | Train 1d n@hit cover | Hold full n@hit | Hold 1d n@hit cover | all_win hold1 |
|---|---:|---|---|---|:---:|
| **hard34** | 57 | 169@100.0% 96.6% | 3936@27.72% | 73@38.36% 100.0% | False |
| **hard50** | 60 | 172@100.0% 98.3% | 4431@27.62% | 73@41.1% 100.0% | False |
| **clean34** | 46 | 129@100.0% 73.7% | 1746@28.92% | 72@43.06% 98.6% | False |
| **clean50** | 60 | 169@100.0% 96.6% | 3077@29.31% | 73@38.36% 100.0% | False |
| **hard21** | 58 | 169@100.0% 96.6% | 4619@27.41% | 73@39.73% 100.0% | False |
| **pull34** | 62 | 104@100.0% 59.4% | 196@30.1% | 65@32.31% 89.0% | False |
| **stack34_with** | 60 | 173@100.0% 98.9% | 4020@27.79% | 73@38.36% 100.0% | False |

### Best hold 1/day book: `clean34`

- Micros **46** · hold 1/day **72@43.06%** cover **98.6%**
- Train was locked at **100.0%** on **129** days covered (73.7%)

## Simple read

- This is **batch-1 / last year only** — not 2011→now yet.
- Longer MA gates (34/50) are meant to strip noisy counter-trend ticks; adaptive T/SL lets tight pullbacks take smaller targets and trend mid takes larger.
- If hold hit stays ~25–40%, fingerprints still overfit train months — next batch adds prior years **without** peeking hold.
- Target state: hold 1/day hit → **100%** with cover near session count; we are measuring the gap now.

Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_ma_lastyear`
Elapsed: 67.1s
