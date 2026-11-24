# NIFTY 1m — Double Top **SECOND LEG DOWN** · prove hunt

> **RESEARCH ONLY.** First dip after H1 is structure only. Trade = strong 2nd move after H2.

Window **2025-12-26 → 2026-11-16** · OOS from **2026-06-10**.

## Structure (required)

```
H1 (first high)
  └─ 1st move DOWN → valley/neck   ← NOT a trade
H2 (second push up into supply)
  └─ 2nd move DOWN with strength   ← ONLY then setups fire
```

Strong 2nd leg = bearish expansion (body≥k×ATR, body/range≥0.55, close in lower quartile),
under EMA, piercing/breaking neckline.

## Result: **13 PROVEN** · **101 PROMISING** · 1008 books

### Setup `leg2`
- tested: 504 · proven: 0
- best: `SELL_leg2_ema20_tol35_k100_sl6_t40` · NOT_PROVEN · OOS {'n': 109, 'hit': 22.02, 'exp_R': 0.688, 't': np.float64(2.25), 'wins': 24, 'losses': 85, 'avg_pts': 4.13}
- **max SL PROVEN**: None · **min SL**: None · **max T**: None
- MAE80≈89.6 · MFE50≈41.75 · MFE80≈101.45

### Setup `leg2_retest`
- tested: 504 · proven: 13
- best: `SELL_leg2_retest_ema20_tol80_k100_sl6_t15` · PROVEN · OOS {'n': 103, 'hit': 46.6, 'exp_R': 0.631, 't': np.float64(3.65), 'wins': 48, 'losses': 55, 'avg_pts': 3.79}
- **max SL PROVEN**: 15.0 · **min SL**: 6.0 · **max T**: 30.0
- MAE80≈85.2 · MFE50≈42.33 · MFE80≈94.75

## Top books

| Book | Verdict | Train n/hit/exp | OOS n/hit/exp/t | MAE80 | MFE50 |
|---|---|---|---|---|---|
| `SELL_leg2_retest_ema20_tol80_k100_sl6_t15` | **PROVEN** | 99/36.36%/0.273 | 103/46.6%/0.631/t=3.65 | 85.2 | 42.33 |
| `SELL_leg2_retest_ema20_tol80_k85_sl6_t15` | **PROVEN** | 104/37.5%/0.312 | 104/46.15%/0.615/t=3.58 | 83.3 | 42.4 |
| `SELL_leg2_retest_ema20_tol80_k85_sl6_t12` | **PROVEN** | 104/42.31%/0.269 | 104/50.0%/0.5/t=3.38 | 83.3 | 42.4 |
| `SELL_leg2_retest_ema20_tol35_k100_sl6_t15` | **PROVEN** | 97/36.08%/0.263 | 99/42.42%/0.485/t=2.77 | 82.7 | 39.6 |
| `SELL_leg2_retest_ema20_tol55_k85_sl12_t30` | **PROVEN** | 101/36.63%/0.282 | 102/40.2%/0.445/t=2.63 | 83.33 | 40.3 |
| `SELL_leg2_retest_ema20_tol55_k85_sl6_t12` | **PROVEN** | 101/41.58%/0.248 | 102/47.06%/0.412/t=2.76 | 83.33 | 40.3 |
| `SELL_leg2_retest_ema20_tol35_k85_sl12_t30` | **PROVEN** | 101/38.61%/0.351 | 101/38.61%/0.39/t=2.31 | 82.52 | 38.9 |
| `SELL_leg2_retest_ema20_tol80_k85_sl12_t30` | **PROVEN** | 104/37.5%/0.312 | 104/38.46%/0.384/t=2.31 | 83.3 | 42.4 |
| `SELL_leg2_retest_ema20_tol35_k100_sl12_t30` | **PROVEN** | 97/38.14%/0.335 | 99/38.38%/0.369/t=2.16 | 82.7 | 39.6 |
| `SELL_leg2_retest_ema20_tol35_k85_sl15_t30` | **PROVEN** | 101/41.58%/0.248 | 101/43.56%/0.346/t=2.35 | 82.52 | 38.9 |
| `SELL_leg2_retest_ema20_tol35_k100_sl15_t30` | **PROVEN** | 97/42.27%/0.268 | 99/43.43%/0.329/t=2.21 | 82.7 | 39.6 |
| `SELL_leg2_retest_ema20_tol80_k100_sl12_t30` | **PROVEN** | 99/36.36%/0.273 | 103/36.89%/0.315/t=1.9 | 85.2 | 42.33 |
| `SELL_leg2_retest_ema20_tol35_k100_sl12_t25` | **PROVEN** | 97/40.21%/0.24 | 99/41.41%/0.297/t=1.94 | 82.7 | 39.6 |
| `SELL_leg2_retest_ema20_tol80_k100_sl6_t18` | **PROMISING** | 99/33.33%/0.333 | 103/40.78%/0.631/t=3.24 | 85.2 | 42.33 |
| `SELL_leg2_retest_ema20_tol35_k100_sl6_t18` | **PROMISING** | 97/34.02%/0.361 | 99/40.4%/0.616/t=3.11 | 82.7 | 39.6 |
| `SELL_leg2_retest_ema20_tol55_k85_sl6_t18` | **PROMISING** | 101/32.67%/0.307 | 102/40.2%/0.608/t=3.11 | 83.33 | 40.3 |
| `SELL_leg2_retest_ema20_tol80_k85_sl6_t20` | **PROMISING** | 104/32.69%/0.417 | 104/36.54%/0.583/t=2.84 | 83.3 | 42.4 |
| `SELL_leg2_retest_ema20_tol80_k85_sl6_t18` | **PROMISING** | 104/33.65%/0.346 | 104/39.42%/0.577/t=3.0 | 83.3 | 42.4 |
| `SELL_leg2_retest_ema20_tol55_k100_sl6_t15` | **PROMISING** | 97/35.05%/0.227 | 100/45.0%/0.575/t=3.29 | 84.8 | 41.25 |
| `SELL_leg2_retest_ema20_tol35_k85_sl6_t18` | **PROMISING** | 101/33.66%/0.347 | 101/38.61%/0.545/t=2.8 | 82.52 | 38.9 |
| `SELL_leg2_retest_ema20_tol35_k85_sl6_t20` | **PROMISING** | 101/32.67%/0.416 | 101/35.64%/0.544/t=2.62 | 82.52 | 38.9 |
| `SELL_leg2_retest_ema20_tol80_k100_sl6_t12` | **PROMISING** | 99/39.39%/0.182 | 103/50.49%/0.515/t=3.46 | 85.2 | 42.33 |
| `SELL_leg2_retest_ema20_tol55_k85_sl6_t15` | **PROMISING** | 101/35.64%/0.248 | 102/43.14%/0.51/t=2.96 | 83.33 | 40.3 |
| `SELL_leg2_retest_ema20_tol55_k85_sl8_t20` | **PROMISING** | 101/32.67%/0.144 | 102/43.14%/0.51/t=2.96 | 83.33 | 40.3 |
| `SELL_leg2_retest_ema20_tol35_k85_sl8_t18` | **PROMISING** | 101/35.64%/0.158 | 101/45.54%/0.48/t=2.97 | 82.52 | 38.9 |

## Signal counts

| EMA | tol | body_k | DTs | leg2 | leg2_retest |
|---|---|---|---|---|---|
| 20 | 0.35 | 0.85 | 3193 | 1469 | 927 |
| 20 | 0.35 | 1.0 | 3193 | 1333 | 845 |
| 20 | 0.55 | 0.85 | 3529 | 1607 | 1025 |
| 20 | 0.55 | 1.0 | 3529 | 1457 | 932 |
| 20 | 0.8 | 0.85 | 4132 | 1888 | 1181 |
| 20 | 0.8 | 1.0 | 4132 | 1717 | 1076 |
| 34 | 0.35 | 0.85 | 3193 | 1467 | 801 |
| 34 | 0.35 | 1.0 | 3193 | 1332 | 722 |
| 34 | 0.55 | 0.85 | 3529 | 1605 | 887 |
| 34 | 0.55 | 1.0 | 3529 | 1458 | 805 |
| 34 | 0.8 | 0.85 | 4132 | 1886 | 1052 |
| 34 | 0.8 | 1.0 | 4132 | 1718 | 959 |

## Accuracy meaning

PROVEN ≠ 100%. It means hit@target before SL cleared ~35%+ with +EV on train and OOS.
Many 2nd-leg shorts still stop; edge comes from R multiple when T hits.

_Generated in 66.4s._
