# SENSEX · dual+fb · stronger break fallback (bf≥20%) (±50/50)

**Desk:** `SENSEX_DUAL_FB_BF20_T50`

## Exact logic

1. **Dual:** OR-break `p≥0.45` · no or_ext cap · sell cont · all duals
2. **Fallback:** OR **break-only** @ 09:45 with **break_frac ≥ 20%** (no mid-OR)
3. **Same hm+side:** 1 call tagged `dual` + `fallback` + `COMBINED`
4. No mutual block otherwise · ±50/50

## Why this lock

Grid could **not** raise both N and hit vs prior 909@76.13% (p40/p42 add no new duals).
Best accuracy step that keeps combine: require a clearer OR break on fallback.

| Window | Prior break-only | **This (bf≥20%)** |
|---|---|---|
| **1y** | 909 @ 76.13% | **871 @ 77.38%** |
| **3y** | 2370 @ 72.62% | **2293 @ 73.79%** |
| **3m** | 227 @ 79.3% | **215 @ 80.0%** |

## 3m months

| Month | N | Hit | W/L |
|---|---:|---:|---|
| 2026-08 | 44 | 79.55 | 35/9 |
| 2026-09 | 80 | 81.25 | 65/15 |
| 2026-10 | 84 | 83.33 | 70/14 |
| 2026-11 | 7 | 28.57 | 2/5 |

_Locked bf>=0.20_
