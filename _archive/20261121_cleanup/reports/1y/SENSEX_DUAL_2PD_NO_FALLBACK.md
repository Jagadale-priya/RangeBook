# SENSEX · dual-only · up to 2 combine/day · NO fallback (±50/50)

**Desk:** `SENSEX_DUAL_2PD_T50SL50`
**Logic:** dual OR-break only — multiple duals can fire the same day (first 2 by time).
**Removed:** OR fallback when dual silent.

## Exact rules

1. Sensex dual OR-break candidate with `p_t1 ≥ 0.45` (BUY or SELL)
2. No `or_ext` cap · sell continuation allowed
3. Same day: keep first **2** by time (combine — more than 1 call OK)
4. If no dual that day → **no call** (no fallback)
5. Clip ±50/50

## Results

| Window | Days w/ call | Calls | Day cov% | Hit% | Avg/active day | W/L |
|---|---:|---:|---:|---:|---:|---|
| **1y** | 177/249 | 308 | 71.1 | **82.14** | 1.74 | 253/55 |
| **3m** | 39/64 | 67 | 60.9 | **89.55** | 1.72 | 60/7 |
| **3y** | 437/624 | 763 | 70.0 | **77.06** | 1.75 | 588/175 |

## 3m months

| Month | N | Hit | W/L |
|---|---:|---:|---|
| 2026-08 | 12 | 91.67 | 11/1 |
| 2026-09 | 26 | 84.62 | 22/4 |
| 2026-10 | 29 | 93.1 | 27/2 |

_Locked dual-only CAP=2 · no fallback_
