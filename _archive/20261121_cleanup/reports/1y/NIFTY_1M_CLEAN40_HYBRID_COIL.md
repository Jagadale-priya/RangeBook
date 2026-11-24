# NIFTY 1m — Clean ≥40 **hybrid coil** (dual squeeze → impulse break)

> Test: BB-width squeeze **AND** ATR compression ≥5 bars → Donchian break → impulse candle.
> Success = clean one-direction ≥40 (only green to +40 / only red to −40).

Window **2026-05-26 → 2026-11-16** (120d). OOS **2026-08-20**. True clean40: **382**.

## Recipe

```
BB squeeze : bbWidth < SMA(bbWidth,20) × 0.6
ATR compress: ATR14 < SMA(ATR,20) × 0.75
COIL       : both true for ≥ 5 bars; box = high/low during coil
BREAK      : close outside coil box (same-color body)
IMPULSE    : body ≥ 0.8×ATR + control close
SUCCESS    : from streak open, only same-color until ±40
```

## Results

| Gate | 1d n | 1d prec% | OOS% | all n | all prec% | Coverage% | score | avg ext |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `or30_break+ctrl+impulse+atr_hi` | 33 | **39.39** | 43.48 | 36 | 38.89 | 4.2 | 1.65 | 52.8 |
| `box20_break+ctrl+impulse+atr_hi` | 86 | **33.72** | 36.36 | 594 | 35.69 | 46.6 | 15.71 | 59.0 |
| `confirm1+ctrl+impulse+atr_hi` | 84 | **26.19** | 33.33 | 472 | 24.36 | 30.4 | 7.96 | 58.5 |
| `box20_break+ctrl+impulse` | 120 | **25.0** | 25.0 | 2237 | 18.82 | 68.6 | 17.15 | 57.1 |
| `coil_break_1perside+ctrl+impulse+held` | 16 | **25.0** | 37.5 | 17 | 23.53 | 1.3 | 0.33 | 48.7 |
| `box20_break` | 120 | **24.17** | 25.0 | 4494 | 15.22 | 76.2 | 18.42 | 55.2 |
| `or30_break` | 114 | **22.81** | 26.79 | 145 | 22.07 | 10.2 | 2.33 | 52.8 |
| `or30_break+ctrl+impulse` | 79 | **22.78** | 23.81 | 90 | 23.33 | 6.5 | 1.48 | 54.3 |
| `coil_break+ctrl+impulse+held` | 25 | **20.0** | 33.33 | 31 | 19.35 | 1.8 | 0.36 | 47.9 |
| `coil_break_1perside+impulse` | 26 | **19.23** | 36.36 | 30 | 16.67 | 1.6 | 0.31 | 56.3 |
| `coil_break_1perside+ctrl+impulse` | 26 | **19.23** | 36.36 | 30 | 16.67 | 1.6 | 0.31 | 56.3 |
| `coil_break_1perside+ctrl+impulse+ad` | 26 | **19.23** | 36.36 | 30 | 16.67 | 1.6 | 0.31 | 56.3 |
| `coil_break_1perside+ctrl` | 48 | **18.75** | 33.33 | 52 | 17.31 | 3.1 | 0.58 | 53.0 |
| `coil_break` | 55 | **18.18** | 31.03 | 103 | 15.53 | 4.2 | 0.76 | 53.1 |
| `coil_break_1perside` | 55 | **18.18** | 31.03 | 61 | 16.39 | 3.4 | 0.62 | 52.3 |
| `coil_break+ctrl` | 51 | **17.65** | 30.77 | 85 | 16.47 | 3.9 | 0.69 | 51.2 |
| `coil_break+ctrl+impulse+ad` | 34 | **17.65** | 33.33 | 44 | 15.91 | 2.1 | 0.37 | 53.4 |
| `confirm1+ctrl+impulse` | 120 | **17.5** | 25.0 | 1806 | 8.97 | 42.7 | 7.47 | 56.2 |
| `coil_break+ctrl+impulse` | 35 | **17.14** | 33.33 | 45 | 15.56 | 2.1 | 0.36 | 53.4 |
| `coil_break+impulse` | 36 | **16.67** | 31.25 | 46 | 15.22 | 2.1 | 0.35 | 53.4 |
| `coil_break+ctrl+impulse+atr_hi` | 19 | **15.79** | 33.33 | 23 | 17.39 | 1.3 | 0.21 | 59.9 |
| `coil_break+FULL` | 19 | **15.79** | 33.33 | 23 | 17.39 | 1.3 | 0.21 | 59.9 |
| `coil_break_1perside+ctrl+impulse+atr_hi` | 15 | **13.33** | 33.33 | 16 | 12.5 | 0.8 | 0.11 | 73.5 |
| `coil_break_1perside+FULL` | 15 | **13.33** | 33.33 | 16 | 12.5 | 0.8 | 0.11 | 73.5 |
| `confirm1` | 120 | **11.67** | 15.0 | 8675 | 4.33 | 97.6 | 11.39 | 55.6 |
| `coil_break+FULL+held` | 10 | **20.0** | 33.33 | 13 | 23.08 | 1.0 | 0.2 | 51.0 |
| `coil_break_1perside+FULL+held` | 6 | **16.67** | 33.33 | 7 | 14.29 | 0.5 | 0.08 | 60.5 |

## vs prior markers (same metric)

| Approach | Typical 1d prec | Coverage |
|---|---:|---:|
| confirm1 (prior) | ~29% | ~93% |
| OR30+ctrl+atr_hi (prior) | ~43% | ~4% |
| box break (prior) | ~25–28% | ~50% |
| **This hybrid best prec** `or30_break+ctrl+impulse+atr_hi` | **39.39%** | 4.2% |
| **This hybrid best balance** `box20_break` | **24.17%** | 76.2% |

## Verdict

**No breakthrough.** Dual-squeeze hybrid did **not** clearly beat prior best ~43% OR30 precision (or stays in the same ballpark). Clean≥40 entry remains hard.

### Samples (best balance 1/day)

| Day | HM | Side | Entry | clean40 | ext | impulse | ctrl |
|---|---|---|---:|---|---:|---|---|
| 2026-05-26 | 09:37 | **BUY** | **24060.55** | True | 54.05 | True | True |
| 2026-05-27 | 09:30 | **SELL** | **23893.85** | False | 78.55 | False | True |
| 2026-05-29 | 09:43 | **SELL** | **23880.25** | True | 50.8 | True | True |
| 2026-06-01 | 09:35 | **SELL** | **23585.0** | True | 40.3 | True | True |
| 2026-06-02 | 09:53 | **BUY** | **23307.9** | True | 45.15 | True | True |
| 2026-06-03 | 09:32 | **SELL** | **23261.9** | False | 37.7 | True | True |
| 2026-06-04 | 09:45 | **BUY** | **23368.95** | True | 49.45 | True | True |
| 2026-06-05 | 09:30 | **BUY** | **23474.15** | False | 36.45 | True | True |
| 2026-06-08 | 09:30 | **BUY** | **23167.15** | False | 37.95 | False | True |
| 2026-06-09 | 09:31 | **BUY** | **23243.4** | False | 27.15 | False | True |

_Generated in 10.2s._
