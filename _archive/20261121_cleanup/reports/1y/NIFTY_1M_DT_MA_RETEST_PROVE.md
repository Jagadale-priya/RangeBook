# NIFTY 1m — Double Top → MA breakdown → MA retest · prove hunt

> **RESEARCH ONLY.** Same house PROVEN gate as expansion/PA books.

Window **2025-12-26 → 2026-11-16** · OOS from **2026-06-10**.

## Logic under test

1. **Double Top** — two swing highs within ATR tolerance, valley between (neckline).
2. **Breakdown** — close below neckline **and** below EMA (path of least resistance flips down).
3. **Setup A `brk`** — short **next open** after breakdown bar.
4. **Setup B `retest`** — after breakdown, price leaves MA then **retests MA from below** → short next open (institutional premium supply).
5. Grid **SL** ∈ (6.0, 8.0, 10.0, 12.0, 15.0, 20.0, 25.0) · **T** ∈ (10.0, 12.0, 15.0, 18.0, 20.0, 25.0, 30.0, 40.0).

## Result: **24 PROVEN** · **101 PROMISING** · 672 books scored

### Setup `brk`
- tested books: 336 · proven: 3
- best: `SELL_brk_ema20_tol55_sl10_t25` · PROVEN · OOS {'n': 109, 'hit': 36.7, 'exp_R': 0.284, 't': np.float64(1.75), 'wins': 40, 'losses': 69, 'avg_pts': 2.84}
- **max SL (still PROVEN)**: 10.0 · **min SL PROVEN**: 6.0
- **max target (still PROVEN)**: 25.0
- path geometry: MAE p80≈86.12 (SL sizing) · MFE p50≈41.85 / p80≈96.7 (target ceiling)

### Setup `retest`
- tested books: 336 · proven: 21
- best: `SELL_retest_ema20_tol35_sl6_t18` · PROVEN · OOS {'n': 108, 'hit': 35.19, 'exp_R': 0.407, 't': np.float64(2.21), 'wins': 38, 'losses': 70, 'avg_pts': 2.44}
- **max SL (still PROVEN)**: 20.0 · **min SL PROVEN**: 6.0
- **max target (still PROVEN)**: 40.0
- path geometry: MAE p80≈77.08 (SL sizing) · MFE p50≈42.5 / p80≈91.35 (target ceiling)

## Top books

| Book | Verdict | Train n/hit/exp | OOS n/hit/exp/t | MAE80 | MFE50 |
|---|---|---|---|---|---|
| `SELL_retest_ema20_tol35_sl6_t18` | **PROVEN** | 106/37.74%/0.509 | 108/35.19%/0.407/t=2.21 | 77.08 | 42.5 |
| `SELL_retest_ema20_tol55_sl6_t18` | **PROVEN** | 106/37.74%/0.509 | 108/35.19%/0.407/t=2.21 | 79.44 | 42.77 |
| `SELL_retest_ema20_tol55_sl8_t18` | **PROVEN** | 106/38.68%/0.257 | 108/41.67%/0.354/t=2.29 | 79.44 | 42.77 |
| `SELL_retest_ema20_tol55_sl6_t15` | **PROVEN** | 106/39.62%/0.387 | 108/37.96%/0.329/t=2.0 | 79.44 | 42.77 |
| `SELL_retest_ema20_tol35_sl8_t18` | **PROVEN** | 106/38.68%/0.257 | 108/40.74%/0.324/t=2.1 | 77.08 | 42.5 |
| `SELL_retest_ema20_tol80_sl8_t18` | **PROVEN** | 108/38.89%/0.264 | 108/40.74%/0.324/t=2.1 | 82.19 | 42.85 |
| `SELL_retest_ema34_tol80_sl6_t15` | **PROVEN** | 105/37.14%/0.3 | 109/37.61%/0.317/t=1.94 | 81.95 | 41.67 |
| `SELL_retest_ema20_tol80_sl12_t30` | **PROVEN** | 108/37.04%/0.296 | 108/37.04%/0.299/t=1.83 | 82.19 | 42.85 |
| `SELL_retest_ema20_tol35_sl6_t15` | **PROVEN** | 106/38.68%/0.354 | 108/37.04%/0.296/t=1.81 | 77.08 | 42.5 |
| `SELL_retest_ema20_tol55_sl8_t20` | **PROVEN** | 106/36.79%/0.288 | 108/37.04%/0.296/t=1.81 | 79.44 | 42.77 |
| `SELL_brk_ema20_tol55_sl10_t25` | **PROVEN** | 110/35.45%/0.241 | 109/36.7%/0.284/t=1.75 | 86.12 | 41.85 |
| `SELL_retest_ema20_tol80_sl8_t15` | **PROVEN** | 108/42.59%/0.225 | 108/44.44%/0.278/t=2.01 | 82.19 | 42.85 |
| `SELL_retest_ema20_tol55_sl6_t12` | **PROVEN** | 106/43.4%/0.302 | 108/42.59%/0.278/t=1.94 | 79.44 | 42.77 |
| `SELL_retest_ema20_tol35_sl8_t20` | **PROVEN** | 106/36.79%/0.288 | 108/36.11%/0.264/t=1.62 | 77.08 | 42.5 |
| `SELL_retest_ema20_tol80_sl6_t15` | **PROVEN** | 108/41.67%/0.458 | 108/36.11%/0.264/t=1.62 | 82.19 | 42.85 |
| `SELL_retest_ema20_tol80_sl8_t20` | **PROVEN** | 108/37.04%/0.296 | 108/36.11%/0.264/t=1.62 | 82.19 | 42.85 |
| `SELL_brk_ema20_tol55_sl6_t15` | **PROVEN** | 110/39.09%/0.368 | 109/35.78%/0.252/t=1.56 | 86.12 | 41.85 |
| `SELL_retest_ema20_tol35_sl6_t12` | **PROVEN** | 106/40.57%/0.217 | 108/41.67%/0.25/t=1.75 | 77.08 | 42.5 |
| `SELL_retest_ema20_tol55_sl12_t30` | **PROVEN** | 106/41.51%/0.453 | 108/35.19%/0.25/t=1.55 | 79.44 | 42.77 |
| `SELL_retest_ema20_tol80_sl20_t40` | **PROVEN** | 108/41.67%/0.273 | 108/37.04%/0.24/t=1.74 | 82.19 | 42.85 |
| `SELL_brk_ema20_tol55_sl6_t12` | **PROVEN** | 110/42.73%/0.282 | 109/41.28%/0.239/t=1.68 | 86.12 | 41.85 |
| `SELL_retest_ema20_tol35_sl20_t40` | **PROVEN** | 106/45.28%/0.382 | 108/37.04%/0.224/t=1.62 | 77.08 | 42.5 |
| `SELL_retest_ema20_tol80_sl6_t12` | **PROVEN** | 108/46.3%/0.389 | 108/40.74%/0.222/t=1.56 | 82.19 | 42.85 |
| `SELL_retest_ema20_tol55_sl6_t10` | **PROVEN** | 106/48.11%/0.283 | 108/45.37%/0.21/t=1.64 | 79.44 | 42.77 |
| `SELL_retest_ema20_tol80_sl10_t30` | **PROMISING** | 108/33.33%/0.333 | 108/34.26%/0.37/t=2.02 | 82.19 | 42.85 |

## Signal counts

| EMA | DT tol | DTs | brk raw | retest raw |
|---|---|---|---|---|
| 20 | 0.35 | 3763 | 2114 | 1228 |
| 20 | 0.55 | 4165 | 2315 | 1352 |
| 20 | 0.8 | 4841 | 2666 | 1553 |
| 34 | 0.35 | 3763 | 2105 | 1047 |
| 34 | 0.55 | 4165 | 2306 | 1145 |
| 34 | 0.8 | 4841 | 2652 | 1314 |

## How to read max SL / max target

- **max SL PROVEN** = widest stop in the grid that still clears house gate (not ‘infinite room’).
- **MAE p80** = 80th percentile adverse excursion on the raw path — practical upper bound before most shorts are wrong.
- **max T PROVEN** = farthest fixed target that still clears gate; **MFE p50/p80** = how far price typically travels in favor.

_Generated in 62.2s._
