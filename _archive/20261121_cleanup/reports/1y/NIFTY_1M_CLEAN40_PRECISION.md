# NIFTY 1m — Clean ≥40 **precision** (marker → move follows)

> When we **mark** a level/break/flip, how often does a clean one-direction ≥40 follow?
> Clean = only green candles to +40 / only red to −40.

Window **2026-05-26 → 2026-11-16** (120d). OOS **2026-08-20**. True clean40 moves: **558**.

## Definitions

| Term | Meaning |
|---|---|
| **Precision** | Of marker signals, % that become clean ≥40 |
| **Coverage** | Of true clean40 moves, % caught by that marker |
| **1/day** | First signal per day (stable book) |

## 1) All marker books (1/day + all)

| Marker | Verdict-ish | 1d n | 1d prec% | OOS% | all n | all prec% | Coverage% | caught | avg ext |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `or30_break+ctrl+atr_hi` | OK | 44 | **43.18** | 53.33 | 50 | 40.0 | **3.9** | 22 | 53.2 |
| `sess_ext+ctrl+atr_hi` | OK | 103 | **38.83** | 45.28 | 636 | 31.6 | **29.0** | 162 | 57.0 |
| `sess_ext+ctrl+big_body` | OK | 116 | **38.79** | 44.07 | 731 | 28.59 | **33.2** | 185 | 56.4 |
| `sess_ext+ctrl` | OK | 120 | **36.67** | 41.67 | 1360 | 21.54 | **35.5** | 198 | 54.4 |
| `sess_ext` | OK | 120 | **35.83** | 41.67 | 1610 | 21.12 | **37.6** | 210 | 53.8 |
| `sess_ext+ctrl+ad` | OK | 120 | **35.83** | 40.0 | 1345 | 21.56 | **35.3** | 197 | 54.2 |
| `sess_ext+ctrl+held` | OK | 119 | **35.29** | 38.33 | 1258 | 21.07 | **30.8** | 172 | 54.6 |
| `sess_ext+ctrl+disp08` | OK | 117 | **35.04** | 38.98 | 785 | 24.33 | **30.8** | 172 | 56.7 |
| `ANY_structure+ctrl+ad` | WEAK | 120 | **33.33** | 38.33 | 4086 | 16.86 | **66.8** | 373 | 55.1 |
| `ANY_structure+ctrl` | WEAK | 120 | **32.5** | 38.33 | 4143 | 16.8 | **67.4** | 376 | 55.5 |
| `structure_or_SR+ctrl` | WEAK | 120 | **31.67** | 35.0 | 9080 | 9.13 | **76.9** | 429 | 55.6 |
| `or30_break+ctrl+big_body` | WEAK | 70 | **31.43** | 35.0 | 80 | 31.25 | **5.2** | 29 | 54.3 |
| `structure_or_SR+ctrl+ad` | WEAK | 120 | **30.83** | 33.33 | 6574 | 11.56 | **69.4** | 387 | 55.3 |
| `structure_or_SR+ctrl+held` | WEAK | 120 | **30.0** | 35.0 | 3967 | 14.8 | **57.0** | 318 | 55.0 |
| `or15_break+ctrl+atr_hi` | WEAK | 68 | **29.41** | 33.33 | 76 | 28.95 | **4.5** | 25 | 50.0 |
| `confirm1+ctrl+big_body` | WEAK | 119 | **29.41** | 31.67 | 1369 | 15.85 | **42.7** | 238 | 58.1 |
| `confirm1+ctrl+disp08` | WEAK | 120 | **29.17** | 35.0 | 1902 | 10.57 | **39.8** | 222 | 56.4 |
| `confirm1` | WEAK | 120 | **29.17** | 33.33 | 9136 | 5.18 | **92.8** | 518 | 55.7 |
| `confirm1+ctrl` | WEAK | 120 | **29.17** | 31.67 | 6304 | 5.84 | **71.9** | 401 | 55.2 |
| `confirm1+ctrl+ad+disp08` | WEAK | 119 | **28.57** | 33.9 | 1569 | 10.77 | **33.3** | 186 | 55.8 |
| `confirm1+ctrl+atr_hi` | WEAK | 119 | **28.57** | 32.2 | 1763 | 15.43 | **53.2** | 297 | 56.6 |
| `box_break+ctrl+big_body` | WEAK | 120 | **28.33** | 33.33 | 1688 | 24.41 | **51.6** | 288 | 58.0 |
| `ANY_structure_break` | WEAK | 120 | **27.5** | 35.0 | 4899 | 16.37 | **71.5** | 399 | 55.1 |
| `structure_or_SR` | WEAK | 120 | **27.5** | 31.67 | 12054 | 8.02 | **81.2** | 453 | 55.1 |
| `or15_break+ctrl+big_body` | WEAK | 77 | **27.27** | 27.03 | 90 | 26.67 | **5.0** | 28 | 49.3 |
| `pdhl_break+ctrl+big_body` | WEAK | 57 | **26.32** | 26.67 | 59 | 25.42 | **5.0** | 28 | 60.1 |
| `tight_range_break` | WEAK | 119 | **26.05** | 30.51 | 1184 | 14.27 | **21.1** | 118 | 56.4 |
| `box_break+ctrl+held` | WEAK | 119 | **26.05** | 23.73 | 3076 | 17.07 | **48.6** | 271 | 54.5 |
| `confirm1+ctrl+held+ad` | WEAK | 120 | **25.83** | 30.0 | 1871 | 8.34 | **31.2** | 174 | 56.1 |
| `box_break` | WEAK | 120 | **25.83** | 28.33 | 4660 | 15.82 | **59.1** | 330 | 55.0 |
| `or15_break+ctrl+disp08` | WEAK | 79 | **25.32** | 23.68 | 91 | 24.18 | **4.7** | 26 | 49.6 |
| `tight_range_break+ctrl+big_body` | WEAK | 115 | **25.22** | 33.93 | 442 | 22.17 | **15.6** | 87 | 60.7 |
| `confirm1+ctrl+held` | WEAK | 120 | **25.0** | 30.0 | 2267 | 7.68 | **34.9** | 195 | 56.5 |
| `confirm1+ctrl+ad` | WEAK | 120 | **25.0** | 28.33 | 4549 | 6.46 | **57.5** | 321 | 54.7 |
| `box_break+ctrl+disp08` | WEAK | 120 | **25.0** | 26.67 | 2257 | 19.14 | **49.5** | 276 | 57.2 |
| `or30_break+ctrl` | WEAK | 101 | **24.75** | 31.37 | 124 | 22.58 | **5.7** | 32 | 53.8 |
| `or30_break+ctrl+ad` | WEAK | 101 | **24.75** | 31.37 | 123 | 22.76 | **5.7** | 32 | 53.8 |
| `tight_range_break+ctrl+atr_hi` | WEAK | 107 | **24.3** | 30.36 | 309 | 31.07 | **12.7** | 71 | 57.6 |
| `or30_break+ctrl+held` | WEAK | 99 | **24.24** | 30.61 | 122 | 22.13 | **5.6** | 31 | 54.3 |
| `box_break+ctrl+atr_hi` | WEAK | 112 | **24.11** | 26.32 | 1122 | 30.48 | **41.2** | 230 | 57.3 |
| `tight_range_break+ctrl+held` | WEAK | 119 | **23.53** | 23.73 | 661 | 16.19 | **14.5** | 81 | 56.6 |
| `flip0+ctrl+big_body` | WEAK | 120 | **23.33** | 28.33 | 2425 | 9.28 | **40.3** | 225 | 56.0 |
| `flip0+ctrl+disp08` | WEAK | 120 | **23.33** | 28.33 | 3286 | 6.24 | **36.7** | 205 | 55.7 |
| `pdhl_break+ctrl+ad` | WEAK | 73 | **23.29** | 20.0 | 75 | 22.67 | **5.9** | 33 | 58.7 |
| `pdhl_break+ctrl+disp08` | WEAK | 52 | **23.08** | 21.43 | 54 | 22.22 | **4.1** | 23 | 58.1 |
| `or30_break` | WEAK | 114 | **22.81** | 26.79 | 145 | 22.07 | **7.0** | 39 | 52.8 |
| `or30_break+ctrl+disp08` | WEAK | 79 | **22.78** | 23.81 | 90 | 23.33 | **4.5** | 25 | 54.3 |
| `or15_break+ctrl+held` | WEAK | 101 | **22.77** | 21.82 | 131 | 21.37 | **5.9** | 33 | 49.9 |
| `tight_range_break+ctrl+disp08` | WEAK | 119 | **22.69** | 27.12 | 602 | 15.28 | **14.9** | 83 | 58.7 |
| `box_break+ctrl` | WEAK | 120 | **22.5** | 25.0 | 3949 | 16.21 | **56.3** | 314 | 55.4 |
| `flip0` | WEAK | 120 | **21.67** | 26.67 | 17396 | 2.71 | **84.4** | 471 | 55.7 |
| `box_break+ctrl+ad` | WEAK | 120 | **21.67** | 25.0 | 3907 | 16.23 | **55.9** | 312 | 55.1 |
| `or15_break+ctrl` | WEAK | 108 | **21.3** | 21.82 | 138 | 20.29 | **5.9** | 33 | 49.9 |
| `or15_break+ctrl+ad` | WEAK | 108 | **21.3** | 21.82 | 138 | 20.29 | **5.9** | 33 | 49.9 |
| `or15_break` | WEAK | 118 | **21.19** | 22.41 | 156 | 19.87 | **6.6** | 37 | 50.0 |
| `tight_range_break+ctrl` | WEAK | 119 | **21.01** | 27.12 | 1018 | 13.95 | **18.8** | 105 | 56.7 |
| `pdhl_break+ctrl` | WEAK | 83 | **20.48** | 18.6 | 86 | 19.77 | **6.1** | 34 | 58.7 |
| `tight_range_break+ctrl+ad` | WEAK | 119 | **20.17** | 27.12 | 997 | 13.94 | **18.5** | 103 | 55.8 |
| `pdhl_break+ctrl+atr_hi` | WEAK | 65 | **20.0** | 22.86 | 66 | 19.7 | **5.0** | 28 | 58.2 |
| `pdhl_break+ctrl+held` | WEAK | 73 | **19.18** | 15.0 | 75 | 18.67 | **5.6** | 31 | 58.5 |
| `flip0+ctrl` | WEAK | 120 | **19.17** | 20.0 | 12288 | 3.1 | **68.3** | 381 | 55.7 |
| `flip0+ctrl+atr_hi` | WEAK | 120 | **18.33** | 20.0 | 3559 | 7.81 | **49.8** | 278 | 56.3 |
| `pdhl_break` | WEAK | 100 | **18.0** | 18.87 | 107 | 17.76 | **7.2** | 40 | 59.0 |
| `flip0+ctrl+ad` | WEAK | 119 | **16.81** | 18.64 | 6854 | 3.59 | **44.1** | 246 | 56.0 |
| `resist_bounce+ctrl+big_body` | WEAK | 100 | **16.0** | 24.49 | 490 | 9.8 | **8.6** | 48 | 56.8 |
| `support_bounce+ctrl+atr_hi` | WEAK | 94 | **13.83** | 14.58 | 689 | 8.71 | **10.8** | 60 | 59.3 |
| `resist_bounce+ctrl+disp08` | WEAK | 116 | **13.79** | 21.05 | 718 | 6.96 | **9.0** | 50 | 53.4 |
| `resist_bounce+ctrl+atr_hi` | WEAK | 96 | **13.54** | 13.73 | 651 | 8.6 | **10.0** | 56 | 57.8 |
| `flip0+ctrl+held` | WEAK | 119 | **13.45** | 20.34 | 3633 | 3.96 | **25.8** | 144 | 56.2 |
| `ANY_SR_bounce` | WEAK | 119 | **12.61** | 15.25 | 7380 | 2.51 | **33.2** | 185 | 56.4 |
| `ANY_SR_bounce+ctrl` | WEAK | 119 | **12.61** | 15.25 | 5147 | 2.97 | **27.4** | 153 | 57.2 |
| `resist_bounce+ctrl` | WEAK | 119 | **11.76** | 13.56 | 2541 | 3.23 | **14.7** | 82 | 55.0 |
| `resist_bounce` | WEAK | 119 | **10.92** | 13.56 | 3678 | 2.8 | **18.5** | 103 | 54.3 |
| `support_bounce+ctrl+big_body` | WEAK | 99 | **10.1** | 12.5 | 451 | 9.76 | **7.9** | 44 | 58.1 |
| `support_bounce+ctrl` | WEAK | 119 | **10.08** | 11.86 | 2606 | 2.72 | **12.7** | 71 | 59.7 |
| `support_bounce+ctrl+disp08` | WEAK | 117 | **9.4** | 12.28 | 602 | 5.65 | **6.1** | 34 | 59.6 |
| `resist_bounce+ctrl+ad` | WEAK | 118 | **9.32** | 10.34 | 1485 | 3.1 | **8.2** | 46 | 57.3 |
| `support_bounce` | WEAK | 119 | **7.56** | 8.47 | 3702 | 2.22 | **14.7** | 82 | 59.0 |
| `support_bounce+ctrl+ad` | WEAK | 119 | **6.72** | 6.78 | 1205 | 3.65 | **7.9** | 44 | 60.0 |
| `resist_bounce+ctrl+held` | WEAK | 93 | **6.45** | 11.63 | 431 | 5.57 | **4.3** | 24 | 58.0 |
| `support_bounce+ctrl+held` | WEAK | 97 | **6.19** | 8.51 | 448 | 3.57 | **2.9** | 16 | 64.9 |

## 2) Best balance (precision × coverage, 1d n≥20)

| Marker | score | 1d prec% | Coverage% | 1d n | OOS% |
|---|---:|---:|---:|---:|---:|
| `confirm1` | **27.07** | 29.17 | 92.8 | 120 | 33.33 |
| `structure_or_SR+ctrl` | **24.35** | 31.67 | 76.9 | 120 | 35.0 |
| `structure_or_SR` | **22.33** | 27.5 | 81.2 | 120 | 31.67 |
| `ANY_structure+ctrl+ad` | **22.26** | 33.33 | 66.8 | 120 | 38.33 |
| `ANY_structure+ctrl` | **21.91** | 32.5 | 67.4 | 120 | 38.33 |
| `structure_or_SR+ctrl+ad` | **21.4** | 30.83 | 69.4 | 120 | 33.33 |
| `confirm1+ctrl` | **20.97** | 29.17 | 71.9 | 120 | 31.67 |
| `ANY_structure_break` | **19.66** | 27.5 | 71.5 | 120 | 35.0 |
| `flip0` | **18.29** | 21.67 | 84.4 | 120 | 26.67 |
| `structure_or_SR+ctrl+held` | **17.1** | 30.0 | 57.0 | 120 | 35.0 |
| `box_break` | **15.27** | 25.83 | 59.1 | 120 | 28.33 |
| `confirm1+ctrl+atr_hi` | **15.2** | 28.57 | 53.2 | 119 | 32.2 |
| `box_break+ctrl+big_body` | **14.62** | 28.33 | 51.6 | 120 | 33.33 |
| `confirm1+ctrl+ad` | **14.37** | 25.0 | 57.5 | 120 | 28.33 |
| `sess_ext` | **13.47** | 35.83 | 37.6 | 120 | 41.67 |

## 3) Practical takeaway

**Highest precision (n≥15 1d):** `or30_break+ctrl+atr_hi`
- 1/day precision **43.18%** OOS **53.33%** n=44
- Coverage **3.9%** (22/558 true moves)

**Best balance:** `confirm1` · score 27.07
- 1/day precision **29.17%** · coverage **92.8%** · n=120

### How to use

```
1. Mark range box (prior 20-bar H/L), OR15/OR30, PDHL, swing S/R
2. When 1m CLOSES beyond box / OR / PDHL (or bounces S/R with color flip) → signal
3. Side = break/bounce direction
4. Track only while candles stay SAME COLOR
5. Success = reach ±40 with no opposite-color candle
6. If opposite color prints before 40 → abandon (not a clean one-way move)
```

### Samples (best balance, 1/day)

| Day | HM | Side | Entry | clean40 | ext |
|---|---|---|---:|---|---:|
| 2026-05-26 | 09:17 | **BUY** | **23990.8** | True | 57.3 |
| 2026-06-01 | 09:16 | **SELL** | **23630.85** | True | 40.0 |
| 2026-06-02 | 09:18 | **BUY** | **23269.35** | True | 48.4 |
| 2026-06-11 | 09:18 | **BUY** | **23096.45** | True | 62.35 |
| 2026-06-29 | 09:16 | **BUY** | **24105.25** | True | 49.0 |
| 2026-07-02 | 09:16 | **BUY** | **24083.55** | True | 50.15 |
| 2026-05-27 | 09:16 | **BUY** | **23924.4** | False | 52.15 |
| 2026-05-29 | 09:18 | **BUY** | **23950.1** | False | 30.1 |
| 2026-06-03 | 09:16 | **SELL** | **23311.7** | False | 109.35 |
| 2026-06-04 | 09:17 | **BUY** | **23332.85** | False | 80.1 |

_Generated in 148.6s._
