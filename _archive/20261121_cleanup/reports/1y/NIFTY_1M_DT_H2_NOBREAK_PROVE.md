# NIFTY 1m — Double Top **H2 must NOT break H1** · then down

> **RESEARCH ONLY.** If H2 breaks H1 → NO SETUP. After H2 must go down only.

Window **2025-12-26 → 2026-11-16** · OOS from **2026-06-10**.

## Structure (required — strict)

```
H1 (top)
  └─ 1st move DOWN → neck        ← NOT a trade
H2 ≤ H1 (must NOT break H1)
  └─ if any high > H1 → INVALID
  └─ 2nd move DOWN with strength ← ONLY then entry
```

Strong 2nd leg = bearish expansion (body≥k×ATR, body/range≥0.55, close in lower quartile),
under EMA, piercing/breaking neckline. H1 break at any point before entry cancels.

## Result: **0 PROVEN** · **69 PROMISING** · 1008 books

### Setup `leg2`
- tested: 504 · proven: 0
- best: `SELL_leg2_ema20_tol55_k100_sl6_t40` · NOT_PROVEN · OOS {'n': 92, 'hit': 27.17, 'exp_R': 1.128, 't': np.float64(3.16), 'wins': 25, 'losses': 67, 'avg_pts': 6.77}
- **max SL PROVEN**: None · **min SL**: None · **max T**: None
- MAE80≈81.65 · MFE50≈40.98 · MFE80≈104.25

### Setup `leg2_retest`
- tested: 504 · proven: 0
- best: `SELL_leg2_retest_ema20_tol55_k100_sl6_t40` · NOT_PROVEN · OOS {'n': 76, 'hit': 30.26, 'exp_R': 1.32, 't': np.float64(3.25), 'wins': 23, 'losses': 53, 'avg_pts': 7.92}
- **max SL PROVEN**: None · **min SL**: None · **max T**: None
- MAE80≈76.2 · MFE50≈36.75 · MFE80≈94.3

## Top books

| Book | Verdict | Train n/hit/exp | OOS n/hit/exp/t | MAE80 | MFE50 |
|---|---|---|---|---|---|
| `SELL_leg2_retest_ema20_tol55_k100_sl6_t15` | **PROMISING** | 75/33.33%/0.167 | 76/52.63%/0.842/t=4.17 | 76.2 | 36.75 |
| `SELL_leg2_retest_ema20_tol35_k100_sl6_t15` | **PROMISING** | 70/34.29%/0.2 | 73/50.68%/0.774/t=3.75 | 73.6 | 35.85 |
| `SELL_leg2_retest_ema20_tol35_k85_sl6_t15` | **PROMISING** | 75/32.0%/0.12 | 78/48.72%/0.705/t=3.54 | 71.65 | 34.7 |
| `SELL_leg2_retest_ema20_tol55_k100_sl6_t12` | **PROMISING** | 75/38.67%/0.16 | 76/56.58%/0.697/t=4.06 | 76.2 | 36.75 |
| `SELL_leg2_retest_ema20_tol35_k85_sl6_t12` | **PROMISING** | 75/38.67%/0.16 | 78/55.13%/0.654/t=3.85 | 71.65 | 34.7 |
| `SELL_leg2_retest_ema20_tol35_k100_sl6_t12` | **PROMISING** | 70/37.14%/0.114 | 73/54.79%/0.644/t=3.66 | 73.6 | 35.85 |
| `SELL_leg2_retest_ema20_tol55_k85_sl6_t12` | **PROMISING** | 79/37.97%/0.139 | 80/53.75%/0.613/t=3.64 | 75.25 | 36.25 |
| `SELL_leg2_retest_ema20_tol80_k85_sl6_t12` | **PROMISING** | 87/36.78%/0.103 | 88/52.27%/0.568/t=3.54 | 76.2 | 36.75 |
| `SELL_leg2_retest_ema20_tol55_k100_sl10_t12` | **PROMISING** | 75/50.67%/0.115 | 76/65.79%/0.447/t=3.71 | 76.2 | 36.75 |
| `SELL_leg2_ema34_tol35_k100_sl10_t25` | **PROMISING** | 90/32.22%/0.128 | 91/40.66%/0.441/t=2.44 | 78.55 | 38.8 |
| `SELL_leg2_retest_ema20_tol35_k100_sl10_t12` | **PROMISING** | 70/50.0%/0.1 | 73/64.38%/0.416/t=3.35 | 73.6 | 35.85 |
| `SELL_leg2_retest_ema20_tol35_k100_sl15_t30` | **PROMISING** | 70/37.14%/0.114 | 73/45.21%/0.399/t=2.29 | 73.6 | 35.85 |
| `SELL_leg2_ema20_tol35_k100_sl8_t18` | **PROMISING** | 91/35.16%/0.143 | 91/41.76%/0.377/t=2.24 | 79.15 | 38.85 |
| `SELL_leg2_ema20_tol35_k100_sl10_t18` | **PROMISING** | 91/39.56%/0.108 | 91/48.35%/0.372/t=2.54 | 79.15 | 38.85 |
| `SELL_leg2_ema34_tol35_k100_sl8_t18` | **PROMISING** | 90/35.56%/0.156 | 91/40.66%/0.341/t=2.04 | 78.55 | 38.8 |
| `SELL_leg2_retest_ema34_tol35_k85_sl12_t30` | **PROMISING** | 67/34.33%/0.201 | 68/36.76%/0.33/t=1.61 | 70.21 | 35.67 |
| `SELL_leg2_retest_ema34_tol35_k85_sl12_t25` | **PROMISING** | 67/35.82%/0.104 | 68/42.65%/0.315/t=1.69 | 70.21 | 35.67 |
| `SELL_leg2_ema34_tol35_k100_sl10_t18` | **PROMISING** | 90/40.0%/0.12 | 91/46.15%/0.311/t=2.12 | 78.55 | 38.8 |
| `SELL_leg2_retest_ema34_tol35_k85_sl15_t25` | **PROMISING** | 67/41.79%/0.115 | 68/47.06%/0.29/t=1.8 | 70.21 | 35.67 |
| `SELL_leg2_retest_ema34_tol35_k100_sl10_t25` | **PROMISING** | 62/32.26%/0.129 | 63/36.51%/0.278/t=1.3 | 72.52 | 36.75 |
| `SELL_leg2_retest_ema34_tol35_k85_sl15_t30` | **PROMISING** | 67/40.3%/0.209 | 68/39.71%/0.276/t=1.57 | 70.21 | 35.67 |
| `SELL_leg2_ema34_tol35_k100_sl8_t12` | **PROMISING** | 90/44.44%/0.111 | 91/49.45%/0.236/t=1.79 | 78.55 | 38.8 |
| `SELL_leg2_retest_ema34_tol35_k85_sl12_t12` | **PROMISING** | 67/55.22%/0.104 | 68/61.76%/0.235/t=1.98 | 70.21 | 35.67 |
| `SELL_leg2_ema20_tol55_k85_sl6_t15` | **PROMISING** | 99/32.32%/0.131 | 94/35.11%/0.229/t=1.32 | 80.14 | 40.35 |
| `SELL_leg2_ema34_tol55_k85_sl6_t15` | **PROMISING** | 98/32.65%/0.143 | 94/35.11%/0.229/t=1.32 | 80.11 | 40.33 |

## Signal counts

| EMA | tol | body_k | DTs | leg2 | leg2_retest |
|---|---|---|---|---|---|
| 20 | 0.35 | 0.85 | 1630 | 538 | 339 |
| 20 | 0.35 | 1.0 | 1630 | 491 | 308 |
| 20 | 0.55 | 0.85 | 1826 | 612 | 389 |
| 20 | 0.55 | 1.0 | 1826 | 558 | 351 |
| 20 | 0.8 | 0.85 | 2266 | 792 | 484 |
| 20 | 0.8 | 1.0 | 2266 | 725 | 439 |
| 34 | 0.35 | 0.85 | 1630 | 536 | 300 |
| 34 | 0.35 | 1.0 | 1630 | 490 | 264 |
| 34 | 0.55 | 0.85 | 1826 | 610 | 337 |
| 34 | 0.55 | 1.0 | 1826 | 558 | 300 |
| 34 | 0.8 | 0.85 | 2266 | 790 | 438 |
| 34 | 0.8 | 1.0 | 2266 | 726 | 392 |

## Accuracy meaning

PROVEN ≠ 100%. It means hit@target before SL cleared ~35%+ with +EV on train and OOS.
Many 2nd-leg shorts still stop; edge comes from R multiple when T hits.

_Generated in 29.2s._
