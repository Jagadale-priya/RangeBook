# NIFTY 1m — Entry accuracy **v6** (fold-stable)

> Goal: rules that stay accurate across **4 folds of 240d**, not just recent 120d.

Window **2025-11-27 → 2026-11-16** (240d). Mid **2026-05-26**.

## Prior HIGH_85 on 240d (sanity)

- `pb atr_hi+compress+engulf+ctrl+!ext`: n=65 overall **70.77%** min_fold **62.5%** folds=[62.5, 63.89, 100.0, 80.0] ns=[8, 36, 6, 15]

## Fold-stable hunt (min_fold≥60, n≥25, overall≥65)

| Rule | n | overall% | min_fold% | fold% | OOS% | m25% | clean15% |
|---|---:|---:|---:|---|---:|---:|---:|
| `pb|all|ctrl+held+room_ok+disp08+atr_hi` | 31 | **70.97** | **77.78** | [0.0, 77.78, 80.0, 80.0] | 80.0 | 90.32 | 29.03 |
| `pb|all|ctrl+held+htf_with+atr_hi+compress` | 35 | **74.29** | **68.75** | [80.0, 68.75, 50.0, 100.0] | 77.78 | 91.43 | 31.43 |
| `pb|all|ctrl+bounce+room_ok+atr_hi+engulf` | 32 | **81.25** | **66.67** | [66.67, 100.0, 66.67, 66.67] | 66.67 | 90.62 | 43.75 |
| `pb|all|ctrl+atr_hi+compress+engulf+close_strong` | 71 | **70.42** | **65.79** | [72.73, 65.79, 75.0, 78.57] | 77.27 | 84.51 | 33.8 |
| `pb|all|ctrl+held+not_extreme+atr_hi+compress` | 35 | **71.43** | **62.5** | [62.5, 62.5, 100.0, 88.89] | 90.91 | 85.71 | 25.71 |
| `pb|all|ctrl+not_extreme+atr_hi+compress+engulf` | 65 | **70.77** | **62.5** | [62.5, 63.89, 100.0, 80.0] | 85.71 | 84.62 | 32.31 |
| `pb|all|ctrl+room_ok+htf_with+atr_hi+engulf` | 49 | **67.35** | **62.5** | [66.67, 67.86, 62.5, 75.0] | 66.67 | 87.76 | 38.78 |
| `pb|all|ctrl+not_extreme+htf_with+atr_hi+compress` | 51 | **68.63** | **62.07** | [70.0, 62.07, 100.0, 77.78] | 83.33 | 88.24 | 29.41 |
| `pb|all|ctrl+held+room_ok+big_body+engulf` | 54 | **66.67** | **61.54** | [66.67, 69.57, 61.54, 66.67] | 63.64 | 79.63 | 40.74 |
| `pb|all|ctrl+ad+htf_with+atr_hi+compress` | 53 | **66.04** | **60.71** | [75.0, 60.71, 66.67, 71.43] | 69.23 | 84.91 | 26.42 |
| `pb|all|ctrl+htf_with+atr_hi+compress+am` | 30 | **76.67** | **60.0** | [100.0, 75.0, 60.0, 71.43] | 66.67 | 86.67 | 33.33 |
| `pb|all|ctrl+htf_with+atr_hi+compress+engulf` | 43 | **72.09** | **60.0** | [85.71, 65.22, 60.0, 87.5] | 76.92 | 90.7 | 37.21 |
| `pb|all|ctrl+held+room_ok+atr_hi+engulf` | 43 | **69.77** | **60.0** | [60.0, 76.19, 62.5, 66.67] | 64.71 | 93.02 | 39.53 |
| `pb|all|ctrl+atr_hi+compress+engulf+body_dom` | 74 | **67.57** | **60.0** | [72.73, 60.0, 75.0, 80.0] | 78.26 | 82.43 | 31.08 |
| `pb|all|ctrl+held+big_body+compress+engulf` | 63 | **66.67** | **60.0** | [60.0, 61.9, 68.75, 75.0] | 71.88 | 74.6 | 31.75 |
| `pb|all|ctrl+disp10+htf_with+compress+engulf` | 83 | **66.27** | **60.0** | [65.0, 73.91, 64.0, 60.0] | 62.5 | 74.7 | 43.37 |
| `pb|all|ctrl+disp10+htf_with+atr_hi+compress` | 44 | **65.91** | **60.0** | [63.64, 70.37, 60.0, 0.0] | 50.0 | 84.09 | 36.36 |

## Most accurate **stable** logic

**Best fold-stable:** `pb|all|ctrl+held+room_ok+disp08+atr_hi`
- overall m25_first **70.97%** · min_fold **77.78%** · OOS **80.0%** · n=31
- folds [0.0, 77.78, 80.0, 80.0] (ns [3, 18, 5, 5])
- raw m25 **90.32%** · clean15 **29.03%**
- avg MFE 61.21 · avg MAE 41.2

## Ceiling vs 100% goal

- Fold-stable ≥85% overall AND min_fold≥80: **0**
- Recent 120d HIGH_85 **failed** longer-window / early folds (~62–64%).
- Honest ceiling for causal 1m favour-first ≥25 on 240d is currently **~70–75%** if stability required.
- Near-**100%** one-way entry remains **unproven**.

_Generated in 107.0s._
