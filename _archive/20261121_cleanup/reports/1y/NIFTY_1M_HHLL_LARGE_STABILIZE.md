# NIFTY 1m — HHLL **stabilize** on 500d

Window **2024-11-08→2026-11-16** (500d). Goal: SHIP = n≥30 · T15≥70 · train/oos≥65 · fold_min≥65.

SHIP count: **76** · SOFT: **18**

| Gate | Ship | n | T15% | Train | OOS | fold_min | fold_avg |
|---|---|---:|---:|---:|---:|---:|---:|
| `htf_with+atr_14+streak4+ema_with+am` | **SHIP** | 40 | **85.0** | 87.5 | 83.33 | 80.0 | 84.24 |
| `htf_with+atr_14+streak4+am` | **SHIP** | 42 | **83.33** | 83.33 | 83.33 | 80.0 | 84.47 |
| `htf_with+atr_hi+atr_14+streak4+am` | **SHIP** | 42 | **83.33** | 83.33 | 83.33 | 80.0 | 84.47 |
| `htf_with+atr_12+atr_14+streak4+am` | **SHIP** | 42 | **83.33** | 83.33 | 83.33 | 80.0 | 84.47 |
| `htf_with+desk_ge3+atr_14+streak4+am` | **SHIP** | 41 | **82.93** | 82.35 | 83.33 | 80.0 | 84.24 |
| `htf_with+atr_14+streak4+vwap_with+am` | **SHIP** | 41 | **82.93** | 82.35 | 83.33 | 80.0 | 84.24 |
| `htf_with+atr_14+streak4+ctrl+am` | **SHIP** | 34 | **82.35** | 76.92 | 85.71 | 80.0 | 84.13 |
| `htf_with+atr_14+streak4+skip_open+am` | **SHIP** | 30 | **76.67** | 72.73 | 78.95 | 78.57 | 79.28 |
| `htf_with+atr_14+streak4+prime+am` | **SHIP** | 30 | **76.67** | 72.73 | 78.95 | 78.57 | 79.28 |
| `htf_with+atr_14+streak4+ema_with` | **SHIP** | 52 | **80.77** | 81.82 | 80.0 | 75.0 | 78.66 |
| `htf_with+desk_ge3+atr_14+streak4+ema_with` | **SHIP** | 52 | **80.77** | 81.82 | 80.0 | 75.0 | 78.66 |
| `htf_with+atr_hi+atr_14+streak4+ema_with` | **SHIP** | 52 | **80.77** | 81.82 | 80.0 | 75.0 | 78.66 |
| `htf_with+atr_12+atr_14+streak4+ema_with` | **SHIP** | 52 | **80.77** | 81.82 | 80.0 | 75.0 | 78.66 |
| `held+htf_with+atr_14+streak4+am` | **SHIP** | 36 | **80.56** | 78.57 | 81.82 | 75.0 | 79.82 |
| `htf_with+atr_14+streak4+ema_with+vwap_with` | **SHIP** | 51 | **80.39** | 80.95 | 80.0 | 75.0 | 78.33 |
| `htf_with+atr_14+streak4` | **SHIP** | 54 | **79.63** | 79.17 | 80.0 | 75.0 | 78.93 |
| `htf_with+atr_hi+atr_14+streak4` | **SHIP** | 54 | **79.63** | 79.17 | 80.0 | 75.0 | 78.93 |
| `htf_with+atr_12+atr_14+streak4` | **SHIP** | 54 | **79.63** | 79.17 | 80.0 | 75.0 | 78.93 |
| `htf_with+atr_hi+atr_12+atr_14+streak4` | **SHIP** | 54 | **79.63** | 79.17 | 80.0 | 75.0 | 78.93 |
| `htf_with+atr_12+streak4+ema_with+am` | **SHIP** | 63 | **79.37** | 78.57 | 80.0 | 75.0 | 80.56 |
| `htf+atr14+desk+streak4` | **SHIP** | 53 | **79.25** | 78.26 | 80.0 | 75.0 | 78.66 |
| `htf_with+desk_ge3+atr_14+streak4` | **SHIP** | 53 | **79.25** | 78.26 | 80.0 | 75.0 | 78.66 |
| `htf_with+atr_14+streak4+vwap_with` | **SHIP** | 53 | **79.25** | 78.26 | 80.0 | 75.0 | 78.66 |
| `htf_with+desk_ge3+atr_hi+atr_14+streak4` | **SHIP** | 53 | **79.25** | 78.26 | 80.0 | 75.0 | 78.66 |
| `htf_with+desk_ge3+atr_12+atr_14+streak4` | **SHIP** | 53 | **79.25** | 78.26 | 80.0 | 75.0 | 78.66 |
| `htf_with+atr_hi+atr_14+streak4+vwap_with` | **SHIP** | 53 | **79.25** | 78.26 | 80.0 | 75.0 | 78.66 |
| `htf_with+atr_12+atr_14+streak4+vwap_with` | **SHIP** | 53 | **79.25** | 78.26 | 80.0 | 75.0 | 78.66 |
| `htf_with+desk_ge3+atr_14+streak4+vwap_with` | **SHIP** | 52 | **78.85** | 77.27 | 80.0 | 75.0 | 78.33 |
| `held+htf+atr14+streak4` | **SHIP** | 49 | **77.55** | 75.0 | 79.31 | 72.73 | 75.42 |
| `held+htf_with+atr_14+streak4` | **SHIP** | 49 | **77.55** | 75.0 | 79.31 | 72.73 | 75.42 |
| `held+htf_with+desk_ge3+atr_14+streak4` | **SHIP** | 49 | **77.55** | 75.0 | 79.31 | 72.73 | 75.42 |
| `held+htf_with+atr_hi+atr_14+streak4` | **SHIP** | 49 | **77.55** | 75.0 | 79.31 | 72.73 | 75.42 |
| `held+htf_with+atr_12+atr_14+streak4` | **SHIP** | 49 | **77.55** | 75.0 | 79.31 | 72.73 | 75.42 |
| `held+htf_with+atr_14+streak4+ema_with` | **SHIP** | 49 | **77.55** | 75.0 | 79.31 | 72.73 | 75.42 |
| `held+htf_with+atr_14+streak4+vwap_with` | **SHIP** | 49 | **77.55** | 75.0 | 79.31 | 72.73 | 75.42 |
| `htf_with+atr_14+streak4+ema_with+prime` | **SHIP** | 35 | **80.0** | 78.57 | 80.95 | 71.43 | 78.67 |
| `htf_with+atr_14+streak4+prime` | **SHIP** | 37 | **78.38** | 75.0 | 80.95 | 71.43 | 79.46 |
| `htf_with+atr_hi+atr_14+streak4+prime` | **SHIP** | 37 | **78.38** | 75.0 | 80.95 | 71.43 | 79.46 |
| `htf_with+atr_12+atr_14+streak4+prime` | **SHIP** | 37 | **78.38** | 75.0 | 80.95 | 71.43 | 79.46 |
| `htf_with+atr_14+streak4+vwap_with+prime` | **SHIP** | 37 | **78.38** | 75.0 | 80.95 | 71.43 | 79.46 |

## Decision

**WIRE Scalper:** `htf_with+atr_14+streak4+ema_with+am`
- T15 **85.0%** · fold_min **80.0%** · n=40

### Folds

| Fold | From | To | n | T15 |
|---|---|---|---:|---:|
| 1 | 2024-11-08 | 2025-04-03 | 10 | 90.0 |
| 2 | 2025-04-04 | 2025-08-29 | 5 | 80.0 |
| 3 | 2025-09-01 | 2026-01-23 | 2 | 100.0 |
| 4 | 2026-01-27 | 2026-06-23 | 16 | 81.25 |
| 5 | 2026-06-24 | 2026-11-16 | 7 | 85.71 |

_Generated in 15.3s._
