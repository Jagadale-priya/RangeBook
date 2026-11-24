# NIFTY 1m — **MA HOLD approaches** (exit logic, not last-10 filter)

Entry: first `clean34` per day · Train `<2026-08-01` · Hold unknown `≥2026-08-01` → `2026-11-16`

Families:
- **A** MA-stop at entry (SL = distance to EMA)
- **B** Trail/hold on EMA close (strict = MA flip is loss; soft = green MA-exit counts win)
- **C** Structure SL until cushion, then trail EMA
- **D** Dual-MA hold (fast+slow stack)
- **E** EMA ± k·ATR trailing band
- **F** Structure SL + target sized from |entry−EMA|

| Approach | Train n@hit cover | Hold n@hit cover | Hold avgSL/T1 |
|---|---|---|---|
| `base_struct_t15` | 175@40.0% 100.0% | 73@53.42% 100.0% | 9.67/15.0 |
| `base_struct_t20` | 175@35.43% 100.0% | 73@46.58% 100.0% | 9.67/20.0 |
| `base_struct_t25` | 175@28.57% 100.0% | 73@43.84% 100.0% | 9.67/25.0 |
| `base_struct_t30` | 175@24.57% 100.0% | 73@42.47% 100.0% | 9.67/30.0 |
| `B_trail34_strict_t15` | 175@68.0% 100.0% | 73@75.34% 100.0% | 51.3/15.0 |
| `B_trail34_soft_t15` | 175@68.0% 100.0% | 73@75.34% 100.0% | 39.99/15.0 |
| `E_band34_k1.5_t20` | 175@68.57% 100.0% | 73@71.23% 100.0% | 55.77/20.0 |
| `B_trail34_soft_t20` | 175@62.29% 100.0% | 73@71.23% 100.0% | 35.4/20.0 |
| `E_band21_k1.5_t20` | 175@65.14% 100.0% | 73@69.86% 100.0% | 42.59/20.0 |
| `B_trail21_strict_t15` | 175@64.0% 100.0% | 73@69.86% 100.0% | 38.32/15.0 |
| `B_trail21_soft_t15` | 175@64.0% 100.0% | 73@69.86% 100.0% | 27.5/15.0 |
| `E_band34_k1.0_t20` | 175@66.29% 100.0% | 73@68.49% 100.0% | 48.93/20.0 |
| `E_band34_k0.5_t20` | 175@63.43% 100.0% | 73@68.49% 100.0% | 41.4/20.0 |
| `B_trail34_strict_t20` | 175@61.71% 100.0% | 73@68.49% 100.0% | 49.35/20.0 |
| `E_band21_k1.0_t20` | 175@61.14% 100.0% | 73@67.12% 100.0% | 35.44/20.0 |
| `B_trail15_soft_t15` | 175@57.71% 100.0% | 73@67.12% 100.0% | 19.63/15.0 |
| `E_band34_k1.5_t25` | 175@60.57% 100.0% | 73@65.75% 100.0% | 49.82/25.0 |
| `B_trail15_strict_t15` | 175@56.57% 100.0% | 73@65.75% 100.0% | 29.7/15.0 |
| `E_band21_k0.5_t20` | 175@57.14% 100.0% | 73@64.38% 100.0% | 28.61/20.0 |
| `E_band21_k1.5_t25` | 175@56.0% 100.0% | 73@64.38% 100.0% | 37.36/25.0 |
| `B_trail21_soft_t20` | 175@58.29% 100.0% | 73@63.01% 100.0% | 23.42/20.0 |
| `E_band34_k1.0_t25` | 175@57.71% 100.0% | 73@63.01% 100.0% | 43.51/25.0 |
| `B_trail34_soft_t25` | 175@56.0% 100.0% | 73@63.01% 100.0% | 31.29/25.0 |
| `B_trail21_strict_t20` | 175@57.71% 100.0% | 73@61.64% 100.0% | 36.85/20.0 |

## Best per family (by hold hit)

- **A** `A_ma34_stop_t15` → hold **58.9%** cover 100.0% (train 48.85%/99.4%)
- **B** `B_trail34_strict_t15` → hold **75.34%** cover 100.0% (train 68.0%/100.0%)
- **C** `C_cush5_trail34_t20` → hold **56.16%** cover 100.0% (train 44.0%/100.0%)
- **D** `D_dual21_50_t20` → hold **61.64%** cover 100.0% (train 57.71%/100.0%)
- **E** `E_band34_k1.5_t20` → hold **71.23%** cover 100.0% (train 68.57%/100.0%)
- **F** `F_struct_t_ma21x1.5` → hold **42.47%** cover 100.0% (train 25.14%/100.0%)

### Overall best hold: `B_trail34_strict_t15` → **75.34%** (73 days, cover 100.0%)

Note: soft trail counts green MA-exit as win — useful for hold-PnL, not path-T1 purity.
Strict trail = T1 must print before MA flip (closer to your 100% path goal).
