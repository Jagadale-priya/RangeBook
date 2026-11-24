# Sensex DUAL_FB_BF20_T50 · causal = live match

**Generated:** `2026-11-20T21:23:17`
**Desk:** `SENSEX_DUAL_FB_BF20_T50` · ±50.0 · dual p≥0.45 + fb break_frac≥0.2
**Window 1y:** `2025-11-20` → `2026-11-20`

## Rules (causal — no win hindsight)

1. Dual OR-break candidates with **p_t1 ≥ 0.45**
2. Fallback OR break @ ~09:45 with **break_frac ≥ 0.20**
3. Same hm+side → merge tags (no mutual block)
4. Settle **±50** on 5m

## 1y match

| Book | N | Hit% | W/L | Pts |
|---|---:|---:|---|---:|
| **Held live book** | **869** | **77.33%** | 672/197 | 23750.0 |
| **Causal rebuild (same rules)** | **869** | **77.33%** | 672/197 | 23750.0 |

**N match:** YES · **Hit match (±0.5):** YES
Only-in-held: 0 · Only-in-causal: 0

## Last 1m · candle live vs causal

| Book | N | Hit% | W/L | Pts |
|---|---:|---:|---|---:|
| Causal clip | 35 | 77.14% | 27/8 | 950.0 |
| Live candles (dual.evaluate + fb) | 85 | 61.18% | 52/33 | 950.0 |

## Causal 1y — per month

| Month | Held N | Held Hit% | Causal N | Causal Hit% |
|---|---:|---:|---:|---:|
| 2025-11 | 12 | 75.0% | 12 | **75.0%** |
| 2025-12 | 101 | 77.23% | 101 | **77.23%** |
| 2026-01 | 72 | 80.56% | 72 | **80.56%** |
| 2026-02 | 88 | 70.45% | 88 | **70.45%** |
| 2026-03 | 62 | 79.03% | 62 | **79.03%** |
| 2026-04 | 68 | 82.35% | 68 | **82.35%** |
| 2026-05 | 65 | 66.15% | 65 | **66.15%** |
| 2026-06 | 81 | 79.01% | 81 | **79.01%** |
| 2026-07 | 53 | 75.47% | 53 | **75.47%** |
| 2026-08 | 96 | 79.17% | 96 | **79.17%** |
| 2026-09 | 80 | 81.25% | 80 | **81.25%** |
| 2026-10 | 84 | 83.33% | 84 | **83.33%** |
| 2026-11 | 7 | 28.57% | 7 | **28.57%** |

## Live candles 1m — per month

| Month | N | Hit% | W/L | Pts |
|---|---:|---:|---|---:|
| 2026-10 | 35 | **60.0%** | 21/14 | 350.0 |
| 2026-11 | 50 | **62.0%** | 31/19 | 600.0 |

## Notes

- Sensex held book was built with these same dual+fb rules (already mostly causal).
- Unlike old NIFTY Cap6, this desk does **not** prefer historical wins to inflate hit%.
- Elapsed: 239.0s
- JSON: `C:\Users\Priyanka\Agent\prod_live\reports\1y\SENSEX_CAUSAL_LIVE_MATCH.json`
