# NIFTY morning range — push past 90% (93/95 hunt)

**Generated:** `2026-11-15T17:42:13`

## Cross-window winners (must clear ALL of 1y/3y/5y)

### ≥90% tightest: `v3_hybrid__dn120`
- 1y **92.5%** · 3y **90.7%** · 5y **91.7%**
- width 3y 2.68% · ge93=False · ge95=False

### ≥93% tightest: `hy_atr25_max40__dn120`
- 1y **95.2%** · 3y **94.8%** · 5y **95.4%**
- width 3y 3.05% · ge93=True · ge95=False

### ≥95% tightest: `atr_2_6x__dn120`
- 1y **96.0%** · 3y **95.2%** · 5y **95.7%**
- width 3y 3.13% · ge93=True · ge95=True

### Best min-acc (width≤4%): `reg_atr30_40_max40__both120`
- 1y **98.0%** · 3y **98.0%** · 5y **98.2%**
- width 3y 3.91% · ge93=True · ge95=True

## Per-split train picks

### 1y (`2025-11-03` → `2026-11-11`)
- train≥90% pick `reg_atr22_30__dn120` → train 90.7%/2.90% · test 90.1%/2.68% · promote YES
- train≥93% pick `v3_hybrid__dn130` → train 93.1%/3.16% · test 94.4%/3.00% · promote YES
- train≥95% pick `reg_atr25_40_max20__both115` → train 95.0%/3.46% · test 94.0%/3.15% · promote NO

| Top test | Acc | Width |
|---|---:|---:|
| `maxya_4_0x__dn110` | 100.0% | 4.98% |
| `atr_4_0x__dn130` | 100.0% | 5.08% |
| `maxya_3_5x__both125` | 100.0% | 5.18% |
| `maxya_4_0x__dn120` | 100.0% | 5.21% |
| `maxya_4_0x__both110` | 100.0% | 5.21% |
| `maxya_4_5x__sym` | 100.0% | 5.33% |

### 3y (`2023-10-16` → `2026-11-11`)
- train≥90% pick `reg_atr22_30_max20__dn110` → train 90.3%/2.96% · test 88.4%/2.55% · promote NO
- train≥93% pick `reg_atr25_40__dn110` → train 93.3%/3.23% · test 91.1%/2.83% · promote NO
- train≥95% pick `reg_atr25_40__both115` → train 95.2%/3.52% · test 93.2%/3.09% · promote NO

| Top test | Acc | Width |
|---|---:|---:|
| `atr_4_5x__dn120` | 99.9% | 5.35% |
| `atr_4_5x__dn130` | 99.9% | 5.59% |
| `maxya_4_5x__dn120` | 99.9% | 5.60% |
| `atr_4_5x__both120` | 99.9% | 5.82% |
| `maxya_4_5x__dn130` | 99.9% | 5.85% |
| `atr_5_0x__dn120` | 99.9% | 5.93% |

### 5y (`2021-10-04` → `2026-11-11`)
- train≥90% pick `reg_atr22_30_max20__dn110` → train 90.3%/2.96% · test 89.2%/2.66% · promote NO
- train≥93% pick `v3_hybrid__dn130` → train 93.2%/3.27% · test 93.2%/2.94% · promote YES
- train≥95% pick `reg_atr25_40__both115` → train 95.0%/3.51% · test 94.4%/3.20% · promote NO

| Top test | Acc | Width |
|---|---:|---:|
| `atr_4_5x__dn120` | 99.9% | 5.55% |
| `atr_4_5x__dn130` | 99.9% | 5.80% |
| `maxya_4_5x__dn120` | 99.9% | 5.90% |
| `atr_4_5x__both120` | 99.9% | 6.04% |
| `atr_5_0x__dn120` | 99.9% | 6.16% |
| `maxya_4_5x__dn130` | 99.9% | 6.17% |

## Recommendation

- **method:** `atr_2_6x__dn120`
- **tier:** 95
- tests: {'1y': 0.9603, '3y': 0.9524, '5y': 0.9571}
- width 3y: 0.0313
- vs V3: {'1y': 0.0357, '3y': 0.045, '5y': 0.0404} (V3={'1y': 0.9246, '3y': 0.9074, '5y': 0.9167})
