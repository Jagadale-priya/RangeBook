# SENSEX · 1 call every day (±50/50)

**Desk:** `SENSEX_DAY1_T50SL50` · mode **day1** (max p_t1) · clip ±50/50
**Policy:** `day1_b0.45_s0.48_borNone_c`
- BUY first p≥0.45 · bor=None
- SELL p≥0.48 · cont=ON

## Results

| Window | Sessions | Calls | Coverage | Hit% | W/L |
|---|---:|---:|---:|---:|---|
| **1y** | 249 | 145 | **58.2%** | **81.38** | 118/27 |
| **3m** | 64 | 31 | **48.4%** | **83.87** | 26/5 |
| **3y** | 624 | 355 | **56.9%** | **78.31** | 278/77 |

### Coverage ladder (research)

- cov>=95: none
- cov>=90: none
- cov>=85: none
- cov>=80: none
- cov>=70: none
- cov>=60: none
- cov>=50: cov 55.8% · n=139 hit=84.17% · `day1_ultra_loose`

## 3m per month

| Month | N | Hit | W/L |
|---|---:|---:|---|
| 2026-08 | 6 | 83.33 | 5/1 |
| 2026-09 | 13 | 76.92 | 10/3 |
| 2026-10 | 12 | 91.67 | 11/1 |

## Note

True 100% session coverage is rare (need an OR break + model side every day).
This lock maximizes daily coverage at ±50, then hit rate.

_Elapsed 243.3s_
