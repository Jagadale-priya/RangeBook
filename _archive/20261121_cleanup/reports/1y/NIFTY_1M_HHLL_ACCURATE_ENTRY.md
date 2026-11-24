# NIFTY 1m — **HH / HL / LH / LL** accurate entry

> Structure from highs & lows only. Find accurate entry logic.

Window **2026-05-26 → 2026-11-16** (120d). OOS **2026-08-20**. Candidates **7929**.

## Structure

```
Swing L=3 → label vs prior:
  high > prior high = HH   high < prior high = LH
  low  > prior low  = HL   low  < prior low  = LL
Bias: HH+HL = UP · LH+LL = DOWN
```

| Tag | n |
|---|---:|
| `HH` | 1976 |
| `HL` | 2165 |
| `LH` | 2845 |
| `LL` | 2691 |

| Logic | n |
|---|---:|
| `HH_break_retest` | 393 |
| `HH_confirm` | 1110 |
| `HL_confirm` | 1167 |
| `HL_retest` | 1075 |
| `LH_confirm` | 1302 |
| `LH_retest` | 1156 |
| `LL_break_retest` | 467 |
| `LL_confirm` | 1259 |

## Lift on retest family

| Mark | % Win | % Lose | Lift |
|---|---:|---:|---:|
| `desk_ge3` | 81.1 | 46.0 | 35.1 |
| `ema_with` | 76.7 | 43.4 | 33.3 |
| `held` | 52.6 | 21.6 | 31.0 |
| `htf_with` | 67.2 | 51.4 | 15.8 |
| `atr_hi` | 27.4 | 18.6 | 8.8 |
| `atr_12` | 14.8 | 7.8 | 7.0 |
| `streak4` | 9.2 | 4.9 | 4.3 |
| `bias_with` | 77.5 | 74.1 | 3.4 |
| `ctrl` | 90.9 | 88.2 | 2.7 |
| `not_extreme` | 87.2 | 95.1 | -7.9 |

## Gates (1/day T15)

| Gate | Verdict | n | T15% | Train | OOS | avg MFE | avg pts |
|---|---|---:|---:|---:|---:|---:|---:|
| `HUNT:HL_LH_confirm|held+atr_12+streak4` | **THIN** | 17 | **88.24** | 66.67 | 92.86 | 45.3 | 9.48 |
| `HUNT:HL_LH_confirm|held+atr_hi+atr_12+streak4` | **THIN** | 17 | **88.24** | 66.67 | 92.86 | 45.3 | 9.48 |
| `HUNT:HL_LH_confirm|held+atr_12+bias_with+streak4` | **THIN** | 17 | **88.24** | 66.67 | 92.86 | 45.3 | 9.48 |
| `HUNT:HL_LH_confirm|held+atr_12+desk_ge3+streak4` | **THIN** | 17 | **88.24** | 66.67 | 92.86 | 45.3 | 9.48 |
| `HUNT:HL_LH_confirm|held+atr_12+streak4+ema_with` | **THIN** | 17 | **88.24** | 66.67 | 92.86 | 45.3 | 9.48 |
| `HUNT:HL_LH_confirm|held+atr_12+ctrl+streak4` | **THIN** | 15 | **86.67** | 66.67 | 91.67 | 46.07 | 8.74 |
| `HUNT:HL_LH_confirm|htf_with+atr_hi+desk_ge3+streak4` | **HIGH_75** | 29 | **82.76** | 70.0 | 89.47 | 42.14 | 7.91 |
| `HUNT:HL_LH_confirm|htf_with+atr_hi+streak4+ema_with` | **HIGH_75** | 29 | **82.76** | 70.0 | 89.47 | 42.14 | 7.91 |
| `HUNT:HL_LH_confirm|held+htf_with+atr_hi+streak4` | **HIGH_75** | 27 | **81.48** | 70.0 | 88.24 | 39.92 | 7.39 |
| `HUNT:HH_LL_confirm|held+htf_with+atr_12+ctrl` | **HIGH_75** | 26 | **80.77** | 70.0 | 87.5 | 52.63 | 6.32 |
| `HUNT:HL_LH_confirm|htf_with+atr_hi+streak4` | **OK_65** | 30 | **80.0** | 63.64 | 89.47 | 43.0 | 7.57 |
| `HUNT:HL_LH_confirm|htf_with+atr_hi+bias_with+streak4` | **OK_65** | 30 | **80.0** | 63.64 | 89.47 | 43.0 | 7.57 |
| `HH_break_retest+held+htf+atr10+!ext` | **THIN** | 15 | **80.0** | 83.33 | 77.78 | 46.59 | 8.78 |
| `HUNT:HL_LH_confirm|htf_with+atr_12+streak4` | **THIN** | 15 | **80.0** | 50.0 | 90.91 | 50.89 | 7.58 |
| `HUNT:HL_LH_confirm|htf_with+atr_hi+atr_12+streak4` | **THIN** | 15 | **80.0** | 50.0 | 90.91 | 50.89 | 7.58 |
| `HUNT:HL_LH_confirm|htf_with+atr_12+bias_with+streak4` | **THIN** | 15 | **80.0** | 50.0 | 90.91 | 50.89 | 7.58 |
| `HUNT:HH_LL_confirm|htf_with+atr_12+ctrl+desk_ge3` | **HIGH_75** | 27 | **77.78** | 80.0 | 76.47 | 50.44 | 5.41 |
| `HUNT:HH_LL_confirm|htf_with+atr_12+ctrl+ema_with` | **HIGH_75** | 27 | **77.78** | 80.0 | 76.47 | 50.44 | 5.41 |
| `HH_break_retest+bias+htf+atr10` | **HIGH_75** | 22 | **77.27** | 83.33 | 75.0 | 52.53 | 7.08 |
| `HUNT:HL_LH_retest|held+atr_12+not_extreme` | **OK_65** | 22 | **77.27** | 60.0 | 82.35 | 44.82 | 7.3 |
| `HUNT:HL_LH_retest|held+atr_hi+atr_12+not_extreme` | **OK_65** | 22 | **77.27** | 60.0 | 82.35 | 44.82 | 7.3 |
| `HUNT:HL_LH_retest|held+atr_12+not_extreme+desk_ge3` | **OK_65** | 22 | **77.27** | 60.0 | 82.35 | 44.82 | 7.3 |
| `HUNT:HL_LH_confirm|held+atr_12+ctrl+ema_with` | **OK_65** | 39 | **76.92** | 58.33 | 85.19 | 42.46 | 4.5 |
| `HUNT:HL_LH_confirm|held+htf_with+atr_12+ema_with` | **OK_65** | 47 | **76.6** | 62.5 | 83.87 | 49.13 | 6.1 |
| `HUNT:HL_LH_confirm|held+atr_hi+streak4` | **OK_65** | 34 | **76.47** | 53.85 | 90.48 | 39.49 | 5.65 |
| `HUNT:HL_LH_confirm|held+atr_hi+bias_with+streak4` | **OK_65** | 34 | **76.47** | 53.85 | 90.48 | 39.49 | 5.65 |
| `HUNT:HL_LH_confirm|held+atr_hi+desk_ge3+streak4` | **OK_65** | 34 | **76.47** | 53.85 | 90.48 | 39.49 | 5.65 |
| `HUNT:HL_LH_confirm|held+atr_hi+streak4+ema_with` | **OK_65** | 34 | **76.47** | 53.85 | 90.48 | 39.49 | 5.65 |
| `HH_break_retest+held+htf+atr10+ctrl` | **THIN** | 17 | **76.47** | 100.0 | 63.64 | 58.23 | 5.27 |
| `HUNT:HL_LH_retest|held+atr_12+ctrl+not_extreme` | **OK_65** | 21 | **76.19** | 60.0 | 81.25 | 43.89 | 6.93 |
| `HUNT:HL_LH_confirm|atr_hi+atr_12+desk_ge3+streak4` | **OK_70** | 20 | **75.0** | 66.67 | 76.47 | 41.33 | 4.98 |
| `HUNT:HL_LH_confirm|atr_hi+atr_12+streak4+ema_with` | **OK_65** | 20 | **75.0** | 50.0 | 81.25 | 41.71 | 5.61 |
| `HUNT:HL_LH_confirm|atr_12+bias_with+desk_ge3+streak4` | **OK_70** | 20 | **75.0** | 66.67 | 76.47 | 41.33 | 4.98 |
| `HUNT:HL_LH_confirm|atr_12+bias_with+streak4+ema_with` | **OK_65** | 20 | **75.0** | 50.0 | 81.25 | 41.71 | 5.61 |
| `HUNT:HL_LH_confirm|htf_with+atr_12+desk_ge3+ema_with` | **OK_70** | 51 | **74.51** | 66.67 | 78.79 | 46.04 | 4.44 |
| `HUNT:HL_LH_confirm|held+htf_with+atr_12` | **OK_65** | 47 | **74.47** | 62.5 | 80.65 | 48.94 | 5.2 |
| `HUNT:HL_LH_confirm|held+htf_with+atr_hi+atr_12` | **OK_65** | 47 | **74.47** | 62.5 | 80.65 | 48.94 | 5.2 |
| `HUNT:HL_LH_confirm|held+htf_with+atr_12+bias_with` | **OK_65** | 47 | **74.47** | 62.5 | 80.65 | 48.94 | 5.2 |
| `HUNT:HL_LH_confirm|held+htf_with+atr_12+desk_ge3` | **OK_65** | 47 | **74.47** | 62.5 | 80.65 | 48.94 | 5.2 |
| `HUNT:HL_LH_confirm|atr_hi+atr_12+ctrl+ema_with` | **OK_65** | 43 | **74.42** | 60.0 | 82.14 | 41.42 | 2.93 |
| `HUNT:HL_LH_confirm|atr_12+bias_with+ctrl+ema_with` | **OK_65** | 43 | **74.42** | 60.0 | 82.14 | 41.42 | 2.93 |
| `HUNT:HL_LH_confirm|held+atr_12+ctrl` | **OK_65** | 39 | **74.36** | 58.33 | 81.48 | 42.23 | 3.41 |
| `HUNT:HL_LH_confirm|held+atr_hi+atr_12+ctrl` | **OK_65** | 39 | **74.36** | 58.33 | 81.48 | 42.23 | 3.41 |
| `HUNT:HL_LH_confirm|held+atr_12+bias_with+ctrl` | **OK_65** | 39 | **74.36** | 58.33 | 81.48 | 42.23 | 3.41 |
| `HUNT:HL_LH_confirm|held+atr_12+ctrl+desk_ge3` | **OK_65** | 39 | **74.36** | 58.33 | 81.48 | 42.23 | 3.41 |
| `HH_break_retest+held+htf+atr10` | **OK_70** | 19 | **73.68** | 85.71 | 66.67 | 52.34 | 5.51 |
| `HUNT:HH_LL_break|held+htf_with+atr_12+not_extreme` | **OK_65** | 19 | **73.68** | 100.0 | 61.54 | 39.87 | 6.3 |
| `HUNT:HL_LH_confirm|htf_with+atr_hi+not_extreme+streak4` | **OK_65** | 19 | **73.68** | 33.33 | 92.31 | 36.15 | 5.42 |
| `HUNT:HL_LH_confirm|held+atr_12+ema_with` | **OK_65** | 56 | **73.21** | 57.89 | 81.08 | 48.87 | 5.45 |
| `HUNT:HL_LH_confirm|held+atr_hi+atr_12+ema_with` | **OK_65** | 56 | **73.21** | 57.89 | 81.08 | 48.87 | 5.45 |
| `HUNT:HL_LH_confirm|held+atr_12+bias_with+ema_with` | **OK_65** | 56 | **73.21** | 57.89 | 81.08 | 48.87 | 5.45 |
| `HUNT:HL_LH_confirm|held+atr_12+desk_ge3+ema_with` | **OK_65** | 56 | **73.21** | 57.89 | 81.08 | 48.87 | 5.45 |
| `HUNT:HL_LH_confirm|held+htf_with+streak4` | **OK_70** | 82 | **73.17** | 67.5 | 78.57 | 31.19 | 6.83 |
| `HUNT:HL_LH_confirm|held+htf_with+bias_with+streak4` | **OK_70** | 82 | **73.17** | 67.5 | 78.57 | 31.19 | 6.83 |
| `HUNT:HL_LH_confirm|held+htf_with+desk_ge3+streak4` | **OK_70** | 82 | **73.17** | 67.5 | 78.57 | 31.19 | 6.83 |
| `HUNT:HL_LH_confirm|held+htf_with+streak4+ema_with` | **OK_70** | 82 | **73.17** | 67.5 | 78.57 | 31.19 | 6.83 |
| `HUNT:HL_LH_retest|held+atr_12+not_extreme+ema_with` | **OK_65** | 22 | **72.73** | 40.0 | 82.35 | 43.98 | 5.7 |
| `HUNT:HL_LH_confirm|htf_with+atr_hi+ctrl+streak4` | **OK_65** | 22 | **72.73** | 50.0 | 85.71 | 48.32 | 4.87 |
| `LH_confirm+held+htf+atr12` | **OK_65** | 29 | **72.41** | 61.54 | 81.25 | 46.78 | 4.63 |
| `HUNT:HH_LL_confirm|htf_with+atr_12+ctrl` | **OK_70** | 29 | **72.41** | 72.73 | 72.22 | 50.79 | 5.08 |

## Hunt ≥70% stable

| Pool | Combo | Verdict | n | T15 | Train | OOS |
|---|---|---|---:|---:|---:|---:|
| `HL_LH_confirm` | `held+atr_12+streak4` | **THIN** | 17 | **88.24** | 66.67 | 92.86 |
| `HL_LH_confirm` | `held+atr_hi+atr_12+streak4` | **THIN** | 17 | **88.24** | 66.67 | 92.86 |
| `HL_LH_confirm` | `held+atr_12+bias_with+streak4` | **THIN** | 17 | **88.24** | 66.67 | 92.86 |
| `HL_LH_confirm` | `held+atr_12+desk_ge3+streak4` | **THIN** | 17 | **88.24** | 66.67 | 92.86 |
| `HL_LH_confirm` | `held+atr_12+streak4+ema_with` | **THIN** | 17 | **88.24** | 66.67 | 92.86 |
| `HL_LH_confirm` | `held+atr_12+ctrl+streak4` | **THIN** | 15 | **86.67** | 66.67 | 91.67 |
| `HL_LH_confirm` | `htf_with+atr_hi+desk_ge3+streak4` | **HIGH_75** | 29 | **82.76** | 70.0 | 89.47 |
| `HL_LH_confirm` | `htf_with+atr_hi+streak4+ema_with` | **HIGH_75** | 29 | **82.76** | 70.0 | 89.47 |
| `HL_LH_confirm` | `held+htf_with+atr_hi+streak4` | **HIGH_75** | 27 | **81.48** | 70.0 | 88.24 |
| `HH_LL_confirm` | `held+htf_with+atr_12+ctrl` | **HIGH_75** | 26 | **80.77** | 70.0 | 87.5 |
| `HH_LL_confirm` | `htf_with+atr_12+ctrl+desk_ge3` | **HIGH_75** | 27 | **77.78** | 80.0 | 76.47 |
| `HH_LL_confirm` | `htf_with+atr_12+ctrl+ema_with` | **HIGH_75** | 27 | **77.78** | 80.0 | 76.47 |
| `HL_LH_confirm` | `atr_hi+atr_12+desk_ge3+streak4` | **OK_70** | 20 | **75.0** | 66.67 | 76.47 |
| `HL_LH_confirm` | `atr_12+bias_with+desk_ge3+streak4` | **OK_70** | 20 | **75.0** | 66.67 | 76.47 |
| `HL_LH_confirm` | `htf_with+atr_12+desk_ge3+ema_with` | **OK_70** | 51 | **74.51** | 66.67 | 78.79 |
| `HL_LH_confirm` | `held+htf_with+streak4` | **OK_70** | 82 | **73.17** | 67.5 | 78.57 |
| `HL_LH_confirm` | `held+htf_with+bias_with+streak4` | **OK_70** | 82 | **73.17** | 67.5 | 78.57 |
| `HL_LH_confirm` | `held+htf_with+desk_ge3+streak4` | **OK_70** | 82 | **73.17** | 67.5 | 78.57 |
| `HL_LH_confirm` | `held+htf_with+streak4+ema_with` | **OK_70** | 82 | **73.17** | 67.5 | 78.57 |
| `HH_LL_confirm` | `htf_with+atr_12+ctrl` | **OK_70** | 29 | **72.41** | 72.73 | 72.22 |

## Best logic

**`HUNT:HL_LH_confirm|htf_with+atr_hi+desk_ge3+streak4`** · **HIGH_75**
- T15 **82.76%** · TRAIN **70.0%** · OOS **89.47%** · n=29

```
1) Mark swing H/L (L=3)
2) Label HH/HL/LH/LL vs prior swing
3) Bias = HH+HL (buy) or LH+LL (sell)
4) Enter on best gate (confirm or retest — see name)
5) Filter: held + HTF15 + ATR≥10
6) Exit: EMA34 trail · T15
```

| Day | HM | Side | Entry | logic | tag | ATR | T15 | MFE |
|---|---|---|---:|---|---|---:|---|---:|
| 2026-06-02 | 12:57 | **BUY** | **23467.4** | HL_confirm | HL | 17.95 | True | 31.85 |
| 2026-06-04 | 12:16 | **BUY** | **23448.3** | HL_confirm | HL | 10.65 | False | 1.7 |
| 2026-06-05 | 13:42 | **SELL** | **23297.85** | LH_confirm | LH | 11.39 | True | 15.2 |
| 2026-06-09 | 11:56 | **BUY** | **23175.2** | HL_confirm | HL | 11.72 | True | 34.2 |
| 2026-06-23 | 12:05 | **SELL** | **23970.45** | LH_confirm | LH | 11.42 | True | 53.15 |
| 2026-06-29 | 10:04 | **SELL** | **24053.45** | LH_confirm | LH | 10.39 | False | 1.7 |
| 2026-07-01 | 09:37 | **BUY** | **23932.3** | HL_confirm | HL | 10.16 | True | 64.1 |
| 2026-07-02 | 09:33 | **BUY** | **24128.3** | HL_confirm | HL | 11.95 | True | 31.15 |
| 2026-07-14 | 09:36 | **SELL** | **24114.6** | LH_confirm | LH | 13.84 | True | 52.15 |
| 2026-07-17 | 14:27 | **BUY** | **24310.95** | HL_confirm | HL | 17.8 | False | 23.85 |

_Generated in 33.1s._
