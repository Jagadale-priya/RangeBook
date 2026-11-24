# NIFTY 1m — structure + prior-2 H/L + VIX **analysis**

Research only. Path win = **target before prev/sig/swing2 SL**.

- Analyze: **2024+2025** · Hold: **2026 Jan–Nov6** · FWD: **Nov9–16**
- Features: close location, prior-2 H/L break/hold, stair (HH/HL), stack, engulf, VIX prior-day, strong-pattern flag

## What wins look like (analyze)

| T1 | Win close_ok% | Loss close_ok% | Win strong% | Loss strong% | Win very_strong% | Win adv_lo% |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 62.4 | 57.8 | 32.0 | 24.0 | 11.2 | 43.2 |
| 15 | 63.0 | 57.6 | 32.5 | 25.2 | 11.1 | 44.6 |
| 20 | 63.4 | 58.2 | 32.9 | 25.6 | 11.1 | 45.0 |

### Win structure mix (T10)

- struct2 wins: `{'break_hi_hold': 1477, 'break_lo_hold': 1406, 'hold_above_lo': 739, 'hold_under_hi': 729, 'cut_lo': 192}`
- struct2 loss: `{'break_hi_hold': 1672, 'break_lo_hold': 1466, 'hold_under_hi': 630, 'hold_above_lo': 626, 'cut_lo': 167}`
- VIX wins: `{'NORMAL': 3188, 'LOW': 1079, 'ELEVATED': 478, 'HIGH': 180, 'UNK': 75}` · loss: `{'NORMAL': 3058, 'LOW': 1193, 'ELEVATED': 496, 'HIGH': 170, 'UNK': 83}`
- family wins: `{'runs': 2179, 'engulf': 1184, 'belt_maru': 869, 'other': 291, 'three': 221, 'kick': 186}`
- stair wins: `{'LH_LL': 1919, 'HH_HL': 1757, 'inside': 772, 'outside': 501, 'mixed': 51}`

## Feature lift (analyze · prev SL · T10) — top values

- **primary**: three_soldiers 57.0% n=207 (Δ10.27), marubozu_bull 55.75% n=2253 (Δ9.02), marubozu_bear 54.96% n=2280 (Δ8.23)
- **family**: stars 53.17% n=568 (Δ6.44), belt_maru 52.63% n=7844 (Δ5.9), three 49.33% n=5854 (Δ2.6)
- **decision**: BUY 47.52% n=14972 (Δ0.79), SELL 46.79% n=14778 (Δ0.06)
- **close_zone**: near_low 48.95% n=12105 (Δ2.22), near_high 48.89% n=12273 (Δ2.16), mid 44.65% n=14138 (Δ-2.08)
- **close_ok**: 1 48.67% n=16358 (Δ1.94), 0 44.47% n=14397 (Δ-2.26)
- **struct2**: break_hi_hold 49.69% n=12342 (Δ2.96), break_lo_hold 48.65% n=12113 (Δ1.92), hold_above_lo 45.78% n=6953 (Δ-0.95)
- **stack2**: dn_dn 48.07% n=9774 (Δ1.34), dn_up 47.71% n=12821 (Δ0.98), up_dn 47.38% n=12701 (Δ0.65)
- **stair**: outside 49.42% n=6078 (Δ2.69), LH_LL 47.59% n=13533 (Δ0.86), HH_HL 47.46% n=13624 (Δ0.73)
- **engulf_p1**: 1 47.45% n=16897 (Δ0.72), 0 46.87% n=14858 (Δ0.14)
- **broke_swing_fav**: 1 48.05% n=17349 (Δ1.32), 0 44.75% n=12056 (Δ-1.98)
- **adv_bin**: adv_lo 50.22% n=14123 (Δ3.49), adv_mid 46.38% n=11804 (Δ-0.35), adv_hi 44.41% n=13160 (Δ-2.32)
- **body_bin**: b70+ 52.54% n=12916 (Δ5.81), b55+ 47.33% n=10266 (Δ0.6), b45+ 45.97% n=7336 (Δ-0.76)
- **vix_regime**: HIGH 51.41% n=249 (Δ4.68), UNK 49.43% n=174 (Δ2.7), ELEVATED 49.14% n=1695 (Δ2.41)
- **strong**: 1 51.24% n=11454 (Δ4.51), 0 45.91% n=17468 (Δ-0.82)
- **very_strong**: 1 53.94% n=5621 (Δ7.21), 0 46.68% n=18385 (Δ-0.05)
- **pat_class**: strong_pat 48.63% n=14231 (Δ1.9), weak_pat 46.17% n=15977 (Δ-0.56)
- **pre_regime**: reversal 47.74% n=13400 (Δ1.01), continuation 47.47% n=13895 (Δ0.74), balanced 46.63% n=10107 (Δ-0.1)
- **clock**: early 51.61% n=3908 (Δ4.88), late 46.04% n=3521 (Δ-0.69), morning 46.03% n=5123 (Δ-0.7)
- **align_session**: 1 48.09% n=15199 (Δ1.36), 0 46.34% n=14552 (Δ-0.39)
- **slbin**: sl16-20 62.78% n=5645 (Δ16.05), sl12-16 56.66% n=8651 (Δ9.93), sl8-12 49.48% n=12201 (Δ2.75)

## Accurate tags with volume (hold must also work when n≥15)

### T10_prev

| Rank | Tag | Analyze | Hold | FWD |
|---:|---|---|---|---|
| 1 | `strong=1|struct2=break_lo|slbin=sl16-20` | 113@63.72% | 64@76.56% | 5@60.0% |
| 2 | `very_strong=1|vix_regime=ELEVATED|slbin=sl16-20` | 149@69.8% | 173@71.1% | 12@83.33% |
| 3 | `strong=1|struct2=break_hi_hold|slbin=sl16-20` | 1303@66.54% | 515@65.63% | 12@41.67% |
| 4 | `strong=1|struct2=hold_under_hi|slbin=sl16-20` | 222@65.77% | 118@64.41% | 7@85.71% |
| 5 | `very_strong=1|vix_regime=NORMAL|slbin=sl16-20` | 787@63.53% | 264@64.02% | 7@28.57% |
| 6 | `strong=1|struct2=break_lo_hold|slbin=sl16-20` | 1235@63.89% | 694@63.4% | 28@64.29% |
| 7 | `very_strong=1|vix_regime=LOW|slbin=sl16-20` | 420@65.24% | 163@62.58% | 0@0.0% |
| 8 | `strong=1|struct2=hold_above_lo|slbin=sl16-20` | 233@66.52% | 117@62.39% | 2@50.0% |
| 9 | `strong=1|struct2=hold_under_hi|slbin=sl12-16` | 438@63.24% | 216@59.72% | 14@64.29% |
| 10 | `close_ok=1|struct2=break_lo_hold|vix_regime=HIGH` | 98@60.2% | 166@57.83% | 0@0.0% |
| 11 | `strong=1|vix_regime=ELEVATED|clock=early` | 188@61.17% | 175@57.71% | 14@35.71% |
| 12 | `strong=1|struct2=cut_hi|slbin=sl12-16` | 101@62.38% | 82@57.32% | 2@100.0% |

### T15_prev

| Rank | Tag | Analyze | Hold | FWD |
|---:|---|---|---|---|
| — | _no balanced tag_ | | | |

### T20_prev

| Rank | Tag | Analyze | Hold | FWD |
|---:|---|---|---|---|
| — | _no balanced tag_ | | | |

### T10_swing2

| Rank | Tag | Analyze | Hold | FWD |
|---:|---|---|---|---|
| 1 | `strong=1|struct2=break_lo|slbin=sl16-20` | 113@64.6% | 64@79.69% | 5@60.0% |
| 2 | `very_strong=1|vix_regime=ELEVATED|slbin=sl16-20` | 149@71.14% | 173@72.83% | 12@83.33% |
| 3 | `strong=1|struct2=break_hi_hold|slbin=sl16-20` | 1303@68.84% | 515@69.13% | 12@41.67% |
| 4 | `very_strong=1|vix_regime=NORMAL|slbin=sl16-20` | 787@65.82% | 264@66.67% | 7@28.57% |
| 5 | `primary=marubozu_bull|close_zone=near_high|stair=HH_HL` | 961@64.2% | 336@66.67% | 4@50.0% |
| 6 | `very_strong=1|struct2=break_lo_hold|vix_regime=ELEVATED` | 107@60.75% | 148@65.54% | 14@64.29% |
| 7 | `strong=1|struct2=break_lo_hold|slbin=sl16-20` | 1235@65.75% | 694@65.13% | 28@64.29% |
| 8 | `very_strong=1|vix_regime=NORMAL|slbin=sl12-16` | 1028@62.35% | 335@65.07% | 5@80.0% |
| 9 | `very_strong=1|vix_regime=LOW|slbin=sl16-20` | 420@67.62% | 163@65.03% | 0@0.0% |
| 10 | `very_strong=1|struct2=break_hi_hold|vix_regime=NORMAL` | 955@60.0% | 262@64.5% | 1@0.0% |
| 11 | `strong=1|struct2=hold_under_hi|slbin=sl16-20` | 222@66.22% | 118@64.41% | 7@85.71% |
| 12 | `strong=1|struct2=hold_above_lo|slbin=sl16-20` | 233@67.38% | 117@64.1% | 2@50.0% |

### T15_swing2

| Rank | Tag | Analyze | Hold | FWD |
|---:|---|---|---|---|
| 1 | `strong=1|struct2=break_hi_hold|slbin=sl16-20` | 1303@60.4% | 515@60.58% | 12@41.67% |

## Next

- Promote tags that stay ≥60% on **hold 2026** with n≥15 and decent analyze volume.
- Very-strong + VIX + structure tags are the accuracy ladder; widen only after hold confirms.
- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_struct_vix`
- Elapsed: 668.3s
