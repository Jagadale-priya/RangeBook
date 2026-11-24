# Live accuracy research · `pa_sr_full_v1`

Window 2026-10-22 → 2026-11-20 (**22 live sessions**). Real `scan_session` path.

**BASE:** n=42 hit=69.05% avgR=0.41 sum=300.5

## Loss autopsy (vs wins)

| Feature | Wins | Losses |
|---|---|---|
| N | 29 | 13 |
| Liq favor % | 27.6 | 23.1 |
| Mid-range % | 3.4 | 0.0 |
| Hit 1R % | 100.0 | 0.0 |
| Prior exhaust % | 0.0 | 0.0 |
| Avg soft RR | 2.966 | 3.435 |
| Avg risk pts | 17.09 | 17.342 |
| Avg body | 0.721 | 0.697 |
| Avg MFE / MAE | 28.626 / 6.222 | 7.246 / 19.9 |
| Setups | {'SWEEP_RECLAIM': 7, 'BREAK_HOLD': 18, 'OR_RETEST': 4} | {'OR_RETEST': 7, 'SWEEP_RECLAIM': 1, 'BREAK_HOLD': 5} |
| Time-of-day | {'mid_1030_1230': 17, 'early_pm_1230_1400': 8, 'open_930_1030': 1, 'late_1400_plus': 3} | {'mid_1030_1230': 5, 'late_1400_plus': 2, 'early_pm_1230_1400': 2, 'open_930_1030': 4} |
| Exit why | {'trail_sl': 29} | {'sl': 13} |

## Ablation (production scan path)

| Variant | N | Hit% | AvgR | Sum |
|---|---:|---:|---:|---:|
| **BASE** | 42 | 69.05 | 0.41 | 300.5 |
| **mid_session** | 29 | 82.76 | 0.675 | 358.15 |
| acc_B | 29 | 82.76 | 0.675 | 358.15 |
| no_or | 32 | 81.25 | 0.676 | 397.95 |
| no_or_rr18 | 32 | 81.25 | 0.676 | 397.95 |
| sweep_break | 32 | 81.25 | 0.676 | 397.95 |
| open_1000_no_or | 32 | 81.25 | 0.676 | 397.95 |
| acc_A | 30 | 80.0 | 0.68 | 377.05 |
| acc_E | 25 | 80.0 | 0.645 | 298.65 |
| full_v3_no_or | 34 | 79.41 | 0.656 | 394.15 |
| acc_D | 34 | 79.41 | 0.656 | 394.15 |
| body60_no_or | 29 | 79.31 | 0.663 | 360.7 |
| cd14_no_or | 27 | 77.78 | 0.57 | 280.7 |
| acc_C | 26 | 76.92 | 0.571 | 273.65 |
| full_v3 | 44 | 72.73 | 0.482 | 352.65 |
| rr20 | 40 | 72.5 | 0.481 | 332.4 |
| open_1000 | 41 | 70.73 | 0.445 | 321.0 |
| rr18 | 41 | 70.73 | 0.445 | 316.2 |
| cut_1400 | 37 | 70.27 | 0.414 | 265.25 |
| BASE_full_v1 | 42 | 69.05 | 0.41 | 300.5 |
| flip18 | 42 | 69.05 | 0.41 | 300.5 |
| v3_trail_base | 42 | 66.67 | 0.396 | 286.75 |
| body60 | 39 | 66.67 | 0.381 | 263.25 |
| no_trap | 95 | 65.26 | 0.409 | 643.5 |
| cd14 | 37 | 64.86 | 0.286 | 179.05 |

## Recommendation

**Wired live (v3b `pa_sr_acc_mid`):** `mid_session` — drop OR_RETEST + trade 10:00–14:00  
→ n=29 hit=**82.76%** avgR=0.675 sum=358 (was 69.05% / sum 300)

Key finding: **OR_RETEST = 54% of losses** (7/13) but only 14% of wins. Dropping it alone → 81.25% / sum 398.
