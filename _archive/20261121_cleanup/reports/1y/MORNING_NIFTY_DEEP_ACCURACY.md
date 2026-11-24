# NIFTY-only deep morning context accuracy

**Generated:** `2026-11-15T15:58:08`

## Accuracy definitions

1. **Range full containment** = actual Low ≥ box_lo **and** actual High ≤ box_hi (both required).
2. Also reported: high_ok, low_ok, close_inside, median width %.
3. **Bias accuracy** = among days with a side prediction only; lift vs majority on those days. Abstain ≠ hit.
4. **Gap accuracy** = predicted class vs actual open-vs-prior-close (±0.35%).
5. Winners fit on **train only**; test is holdout.

## last_1y_252  (`2025-11-03` → `2026-11-11`)
Train 3367 · Test **252**

### Range — session_open (useful after cash open)

- **Train-picked winner:** `max_yday_atr_1_5x`
  - train containment **71.2%** · width 1.84%
  - test containment **74.6%** · high_ok 90.1% · low_ok 84.5% · close_in 86.5% · width 1.67%
- **Held `atr14_1_2x` on test:** containment **51.6%** · width 1.28% · high_ok 78.2% · low_ok 73.0%

Top test containment (info only — not used to pick):

| Method | Full contain | High ok | Low ok | Close in | Width |
|---|---:|---:|---:|---:|---:|
| `atr14_2_5x` | 92.1% | 98.0% | 94.0% | 95.6% | 2.66% |
| `atr14_2_0x` | 83.7% | 94.8% | 88.9% | 92.5% | 2.13% |
| `max_yday_atr_1_5x` | 74.6% | 90.1% | 84.5% | 86.5% | 1.67% |
| `atr14_1_5x` | 70.6% | 87.7% | 82.5% | 83.7% | 1.60% |
| `vol20_2sd` | 62.7% | 82.5% | 79.8% | 80.6% | 1.53% |
| `max_yday_atr_1_2x` | 58.3% | 82.9% | 75.4% | 77.8% | 1.34% |
| `p90_20` | 52.0% | 79.4% | 72.2% | 76.6% | 1.38% |
| `held_atr14_1_2x` | 51.6% | 78.2% | 73.0% | 75.4% | 1.28% |

### Range — premarket (prev_close center)
- Train winner `max_yday_atr_1_5x` → test containment **55.6%** width 1.67%
- Held atr14_1_2x test containment **27.4%**

### Bias
- Choice: **NEUTRAL_ABSTAIN_no_edge** · rule `NEUTRAL_ABSTAIN`
  - test: abstain (base up-rate 0.4921)

### Gap / Vol
- Gap winner `always_natural` test accuracy **63.1%** (natural base 63.1%)
- Vol tercile test accuracy **52.0%**

## last_3y_756  (`2023-10-16` → `2026-11-11`)
Train 2863 · Test **756**

### Range — session_open (useful after cash open)

- **Train-picked winner:** `max_yday_atr_1_5x`
  - train containment **71.2%** · width 1.89%
  - test containment **72.2%** · high_ok 88.5% · low_ok 83.5% · close_in 84.9% · width 1.64%
- **Held `atr14_1_2x` on test:** containment **51.5%** · width 1.26% · high_ok 78.4% · low_ok 72.1%

Top test containment (info only — not used to pick):

| Method | Full contain | High ok | Low ok | Close in | Width |
|---|---:|---:|---:|---:|---:|
| `atr14_2_5x` | 90.9% | 96.8% | 94.0% | 95.6% | 2.62% |
| `atr14_2_0x` | 81.6% | 92.7% | 88.8% | 90.3% | 2.09% |
| `max_yday_atr_1_5x` | 72.2% | 88.5% | 83.5% | 84.9% | 1.64% |
| `atr14_1_5x` | 66.8% | 85.5% | 80.7% | 81.6% | 1.57% |
| `vol20_2sd` | 62.0% | 83.1% | 78.4% | 79.0% | 1.44% |
| `max_yday_atr_1_2x` | 57.8% | 82.4% | 74.9% | 77.4% | 1.32% |
| `p90_20` | 57.1% | 81.3% | 75.0% | 76.8% | 1.44% |
| `held_atr14_1_2x` | 51.5% | 78.4% | 72.1% | 73.8% | 1.26% |

### Range — premarket (prev_close center)
- Train winner `max_yday_atr_1_5x` → test containment **58.3%** width 1.64%
- Held atr14_1_2x test containment **34.3%**

### Bias
- Choice: **NEUTRAL_ABSTAIN_no_edge** · rule `NEUTRAL_ABSTAIN`
  - test: abstain (base up-rate 0.5238)

### Gap / Vol
- Gap winner `always_natural` test accuracy **68.2%** (natural base 68.2%)
- Vol tercile test accuracy **48.0%**

## last_5y_1260  (`2021-10-04` → `2026-11-11`)
Train 2359 · Test **1260**

### Range — session_open (useful after cash open)

- **Train-picked winner:** `max_yday_atr_1_5x`
  - train containment **70.7%** · width 1.89%
  - test containment **72.8%** · high_ok 89.7% · low_ok 82.9% · close_in 85.2% · width 1.71%
- **Held `atr14_1_2x` on test:** containment **52.5%** · width 1.31% · high_ok 80.0% · low_ok 71.8%

Top test containment (info only — not used to pick):

| Method | Full contain | High ok | Low ok | Close in | Width |
|---|---:|---:|---:|---:|---:|
| `atr14_2_5x` | 92.1% | 97.6% | 94.4% | 96.6% | 2.72% |
| `atr14_2_0x` | 83.4% | 94.0% | 89.3% | 91.3% | 2.18% |
| `max_yday_atr_1_5x` | 72.8% | 89.7% | 82.9% | 85.2% | 1.71% |
| `atr14_1_5x` | 67.8% | 87.3% | 80.1% | 82.3% | 1.63% |
| `vol20_2sd` | 62.1% | 84.5% | 77.2% | 79.5% | 1.47% |
| `max_yday_atr_1_2x` | 58.9% | 83.8% | 74.8% | 77.2% | 1.37% |
| `p90_20` | 57.5% | 82.5% | 74.4% | 77.0% | 1.45% |
| `held_atr14_1_2x` | 52.5% | 80.0% | 71.8% | 74.3% | 1.31% |

### Range — premarket (prev_close center)
- Train winner `max_yday_atr_1_5x` → test containment **57.0%** width 1.71%
- Held atr14_1_2x test containment **33.2%**

### Bias
- Choice: **NEUTRAL_ABSTAIN_no_edge** · rule `NEUTRAL_ABSTAIN`
  - test: abstain (base up-rate 0.5246)

### Gap / Vol
- Gap winner `always_natural` test accuracy **62.2%** (natural base 62.2%)
- Vol tercile test accuracy **50.0%**

## calendar_2024_plus  (`2024-01-01` → `2026-11-11`)
Train 2914 · Test **705**

### Range — session_open (useful after cash open)

- **Train-picked winner:** `max_yday_atr_1_5x`
  - train containment **71.4%** · width 1.88%
  - test containment **71.6%** · high_ok 88.1% · low_ok 83.3% · close_in 84.4% · width 1.66%
- **Held `atr14_1_2x` on test:** containment **50.8%** · width 1.28% · high_ok 78.0% · low_ok 71.8%

Top test containment (info only — not used to pick):

| Method | Full contain | High ok | Low ok | Close in | Width |
|---|---:|---:|---:|---:|---:|
| `atr14_2_5x` | 90.9% | 96.9% | 94.0% | 95.6% | 2.67% |
| `atr14_2_0x` | 81.3% | 92.5% | 88.6% | 90.3% | 2.13% |
| `max_yday_atr_1_5x` | 71.6% | 88.1% | 83.3% | 84.4% | 1.66% |
| `atr14_1_5x` | 66.2% | 85.1% | 80.4% | 81.3% | 1.60% |
| `vol20_2sd` | 61.3% | 82.5% | 78.2% | 78.4% | 1.46% |
| `max_yday_atr_1_2x` | 57.2% | 82.0% | 74.6% | 76.7% | 1.33% |
| `p90_20` | 56.9% | 81.0% | 75.0% | 76.6% | 1.45% |
| `held_atr14_1_2x` | 50.8% | 78.0% | 71.8% | 73.2% | 1.28% |

### Range — premarket (prev_close center)
- Train winner `max_yday_atr_1_5x` → test containment **58.6%** width 1.66%
- Held atr14_1_2x test containment **34.0%**

### Bias
- Choice: **NEUTRAL_ABSTAIN_no_edge** · rule `NEUTRAL_ABSTAIN`
  - test: abstain (base up-rate 0.5177)

### Gap / Vol
- Gap winner `always_natural` test accuracy **68.8%** (natural base 68.8%)
- Vol tercile test accuracy **46.4%**

## Verdict notes

- Prefer session_open containment as the live morning box accuracy.
- If held method trails a wider ATR multiple on containment, note the width tradeoff.
- Keep bias NEUTRAL unless a rule shows train lift ≥ +2% with coverage ≥ 20% and holds on test.
