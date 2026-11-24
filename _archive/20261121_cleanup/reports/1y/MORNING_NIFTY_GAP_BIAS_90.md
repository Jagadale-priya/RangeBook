# NIFTY gap + bias deep hunt (≥90% / ≥95% when speaking)

**Generated:** `2026-11-15T17:49:48`

## Definitions

- **Gap true:** open vs prior close (±0.35%) → GAP_UP / GAP_DOWN / NATURAL.
- **Bias (close):** close vs prior close → BULLISH / BEARISH.
- **Bias (open→close):** close vs open.
- **Spoken accuracy:** only days the rule does **not** abstain (NEUTRAL/NATURAL).
- **Promote:** spoken_acc ≥ floor on **1y + 3y + 5y** tests.

## Gap after open (observed)

Once cash open is known, gap class is **exact by definition (100%)**.
This is classification for the morning brief after 9:15 — not a forecast.

## Recommendation summary

### Premarket gap (hard)
- rule: `ret2_th100` · promote **False** · floor 0.9
  - 1y: spoken_acc **22.1%** · coverage 34.1% · spoken_days 86
  - 3y: spoken_acc **22.1%** · coverage 32.9% · spoken_days 249
  - 5y: spoken_acc **24.2%** · coverage 36.4% · spoken_days 458

### Bias close vs prior
- rule: `gap_cont_th100` · promote **True** · floor 0.95
  - 1y: spoken_acc **95.0%** · coverage 7.9% · spoken_days 20
  - 3y: spoken_acc **97.6%** · coverage 5.4% · spoken_days 41
  - 5y: spoken_acc **96.0%** · coverage 6.0% · spoken_days 76

### Bias open→close
- rule: `gap_fade_th100` · promote **False** · floor 0.9
  - 1y: spoken_acc **60.0%** · coverage 7.9% · spoken_days 20
  - 3y: spoken_acc **53.7%** · coverage 5.4% · spoken_days 41
  - 5y: spoken_acc **51.3%** · coverage 6.0% · spoken_days 76

## Per-split detail (3y train picks)

### Window `2023-10-16` → `2026-11-11`
#### Premarket gap
- ≥90% pick `extreme_ret1_1_5pct` train spoken **33.2%** cov 11.2% → test **23.7%** cov 7.8% · test_ok=False
- ≥95% pick `extreme_ret1_1_5pct` train spoken **33.2%** cov 11.2% → test **23.7%** cov 7.8% · test_ok=False

| Top train spoken | Train acc | Train cov | Test acc | Test cov |
|---|---:|---:|---:|---:|
| `extreme_ret1_1_5pct` | 0.3323 | 0.1125 | 0.2373 | 0.078 |
| `extreme_ret1_1pct` | 0.2767 | 0.2386 | 0.2374 | 0.1839 |
| `continue_th080` | 0.2759 | 0.3367 | 0.2118 | 0.2685 |
| `strong_continue_struct` | 0.2619 | 0.132 | 0.2025 | 0.1045 |
| `continue_th050` | 0.2523 | 0.5302 | 0.2011 | 0.4603 |
| `continue_th035` | 0.2475 | 0.6549 | 0.1952 | 0.6032 |
| `ret2_th100` | 0.2393 | 0.4233 | 0.2209 | 0.3294 |
| `struct` | 0.2159 | 0.7782 | 0.1551 | 0.7593 |

#### Bias close
- ≥90% pick `gap_cont_th100` train spoken **86.9%** cov 6.7% → test **97.6%** cov 5.4% · test_ok=False
- ≥95% pick `gap_cont_th100` train spoken **86.9%** cov 6.7% → test **97.6%** cov 5.4% · test_ok=False

| Top train spoken | Train acc | Train cov | Test acc | Test cov |
|---|---:|---:|---:|---:|
| `gap_cont_th100` | 0.8691 | 0.0667 | 0.9756 | 0.0542 |
| `after_open_gap_continue` | 0.7933 | 0.4038 | 0.825 | 0.3175 |
| `gap_days_continue` | 0.7933 | 0.4038 | 0.825 | 0.3175 |
| `gap_struct_agree` | 0.7817 | 0.168 | 0.8315 | 0.1177 |
| `big_ret1_continue` | 0.5681 | 0.2386 | 0.5108 | 0.1839 |
| `vote3_unanimous` | 0.5639 | 0.5575 | 0.5437 | 0.545 |
| `cont_any` | 0.5445 | 1.0 | 0.5278 | 1.0 |
| `always_bull` | 0.5382 | 1.0 | 0.5238 | 1.0 |

#### Bias OTC
- ≥90% pick `gap_fade_th100` train spoken **53.4%** cov 6.7% → test **53.7%** cov 5.4% · test_ok=False
- ≥95% pick `gap_fade_th100` train spoken **53.4%** cov 6.7% → test **53.7%** cov 5.4% · test_ok=False

| Top train spoken | Train acc | Train cov | Test acc | Test cov |
|---|---:|---:|---:|---:|
| `gap_fade_th100` | 0.534 | 0.0667 | 0.5366 | 0.0542 |
| `big_ret1_continue` | 0.5183 | 0.2386 | 0.4317 | 0.1839 |
| `gap_fade_th080` | 0.5079 | 0.1107 | 0.5172 | 0.0767 |
| `cont_any` | 0.5051 | 1.0 | 0.4696 | 1.0 |
| `after_open_gap_continue` | 0.5009 | 0.4038 | 0.4708 | 0.3175 |
| `gap_days_continue` | 0.5009 | 0.4038 | 0.4708 | 0.3175 |
| `after_open_gap_fade` | 0.4991 | 0.4038 | 0.5292 | 0.3175 |
| `fade_any` | 0.4946 | 1.0 | 0.5304 | 1.0 |

## Honest conclusion gates

1. **Gap after open:** hold observe-open classifier (**100%** by definition).
2. **Premarket gap:** **no rule** cleared ≥90% spoken accuracy on train+1y/3y/5y. Keep **NATURAL** until open.
3. **Bias open→close (true session direction):** **no rule** cleared ≥90%. Keep **NEUTRAL**.
4. **Bias close-vs-prior after |gap|≥1% (`gap_cont_th100`):** recent test spoken ~95–97%, but:
   - 3y **train** was only **86.9%** (fails honest ≥90% fit gate)
   - partly **mechanical** (large gap already moves price past prior close; OTC continue is only ~46–53%)
   - **Do not hold as bullish/bearish call.**
5. Held desk defaults: gap=observe-after-open else NATURAL; bias=NEUTRAL.
