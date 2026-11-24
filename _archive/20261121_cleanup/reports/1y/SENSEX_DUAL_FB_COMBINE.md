# SENSEX · dual + fallback · combine same-time (±50/50)

**Desk:** `SENSEX_DUAL_FB_COMBINE_T50`

## Exact logic

1. **Dual** — OR-break `p_t1 ≥ 0.45` BUY/SELL · no or_ext · sell cont · all duals kept
2. **Fallback** — OR @ 09:45 **every** session (always evaluated — not only when dual empty)
3. **No mutual block** — dual does not block fallback; fallback does not block dual
4. **Same time** (same day + hm + side): emit **1 call** with tags `dual` + `fallback` + `COMBINED`
5. Different times/sides: both can list (more than 1 call OK)
6. Clip ±50/50

## Results

| Window | Days | Calls | Cov% | Hit% | Dual-only | FB-only | Combined | Avg/day | W/L |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **1y** | 249/249 | 1021 | 100.0 | **72.58** | 772 | 209 | 40 | 4.1 | 741/280 |
| **3m** | 64/64 | 257 | 100.0 | **75.49** | 193 | 59 | 5 | 4.02 | 194/63 |
| **3y** | 624/624 | 2626 | 100.0 | **69.73** | 2002 | 529 | 95 | 4.21 | 1831/795 |

## 3m months

| Month | N | Hit | W/L |
|---|---:|---:|---|
| 2026-08 | 50 | 80.0 | 40/10 |
| 2026-09 | 97 | 74.23 | 72/25 |
| 2026-10 | 96 | 77.08 | 74/22 |
| 2026-11 | 14 | 57.14 | 8/6 |

_Locked dual+fallback combine_
