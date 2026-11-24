# NIFTY 1m — Entry accuracy **v7** (Range Support / Resistance)

> Add **range S/R** then find entry: OR15/OR30, prior-day H/L, swing clusters.
> Modes: **bounce** (fade retest) · **break_retest** (continue).

Window **2026-05-26 → 2026-11-16** (120d). OOS **2026-08-20**. Candidates **1667**.

## 0) Candidate counts

| Source|Mode | n |
|---|---:|
| `OR15|bounce` | 168 |
| `OR15|break_retest` | 134 |
| `OR30|bounce` | 158 |
| `OR30|break_retest` | 117 |
| `PDHL|bounce` | 76 |
| `PDHL|break_retest` | 63 |
| `SWING_R|bounce` | 270 |
| `SWING_R|break_retest` | 173 |
| `SWING_S|bounce` | 290 |
| `SWING_S|break_retest` | 218 |

## 1) Curated gates (m25_first)

| Gate | Verdict | n | m25_first% | Train | OOS | m25% | clean15% | MFE | MAE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `SWING_S break ctrl+htf|1d` | **HIGH_75** | 35 | **80.0** | 73.68 | 87.5 | 82.86 | 62.86 | 57.66 | 19.38 |
| `SWING_S break ctrl+ad+htf|1d` | **HIGH_75** | 29 | **79.31** | 78.57 | 80.0 | 82.76 | 62.07 | 60.01 | 15.08 |
| `SWING_S break ctrl|1d` | **HIGH_75** | 55 | **78.18** | 72.41 | 84.62 | 81.82 | 60.0 | 55.27 | 19.44 |
| `SWING_S break ctrl+!ext+htf|1d` | **HIGH_75** | 32 | **78.12** | 72.22 | 85.71 | 81.25 | 62.5 | 59.07 | 20.19 |
| `SWING_S break ctrl+held+close_strong+htf|1d` | **WEAK** | 22 | **81.82** | 66.67 | 92.31 | 81.82 | 63.64 | 57.12 | 25.83 |
| `SWING_S break ctrl+close_strong+htf|1d` | **WEAK** | 30 | **80.0** | 68.75 | 92.86 | 80.0 | 60.0 | 53.84 | 23.44 |
| `SWING_S break ctrl+held+htf|1d` | **WEAK** | 27 | **77.78** | 66.67 | 86.67 | 85.19 | 62.96 | 62.49 | 21.64 |
| `SWING_S break ctrl+held|1d` | **WEAK** | 39 | **76.92** | 66.67 | 85.71 | 82.05 | 64.1 | 58.24 | 21.9 |
| `SWING_R break ctrl+held+htf|1d` | **WEAK** | 16 | **75.0** | 50.0 | 90.0 | 81.25 | 43.75 | 52.14 | 22.15 |
| `SWING_S break ctrl+held+htf|all` | **WEAK** | 36 | **75.0** | 57.14 | 86.36 | 80.56 | 55.56 | 56.78 | 24.43 |
| `SWING_S break ctrl+held+ad+htf|all` | **WEAK** | 31 | **74.19** | 58.33 | 84.21 | 80.65 | 54.84 | 56.55 | 24.07 |
| `SWING_S break ctrl+held+!ext|1d` | **WEAK** | 34 | **73.53** | 60.0 | 84.21 | 79.41 | 58.82 | 59.11 | 24.33 |
| `SWING_R break ctrl+held+ad+htf|1d` | **WEAK** | 15 | **73.33** | 50.0 | 88.89 | 80.0 | 40.0 | 49.12 | 23.55 |
| `SWING_R break ctrl|1d` | **WEAK** | 33 | **72.73** | 64.71 | 81.25 | 78.79 | 36.36 | 48.57 | 36.59 |
| `SWING_R break ctrl+htf|1d` | **WEAK** | 22 | **72.73** | 55.56 | 84.62 | 77.27 | 45.45 | 50.15 | 23.12 |
| `SWING_R break ctrl+held+htf|all` | **WEAK** | 18 | **72.22** | 42.86 | 90.91 | 77.78 | 44.44 | 54.87 | 21.99 |
| `SWING_S break ctrl+held+ad+htf|1d` | **WEAK** | 25 | **72.0** | 63.64 | 78.57 | 80.0 | 60.0 | 60.36 | 21.87 |
| `SWING_R break ctrl+held|1d` | **WEAK** | 24 | **70.83** | 54.55 | 84.62 | 79.17 | 41.67 | 48.94 | 27.35 |
| `SWING_S break raw|1d` | **WEAK** | 93 | **68.82** | 70.21 | 67.39 | 75.27 | 50.54 | 48.87 | 27.46 |
| `SWING_R break ctrl+held+ad+htf|all` | **WEAK** | 16 | **68.75** | 42.86 | 88.89 | 75.0 | 37.5 | 47.21 | 24.6 |
| `SWING_R break ctrl+ad+htf|1d` | **WEAK** | 18 | **66.67** | 42.86 | 81.82 | 72.22 | 33.33 | 46.55 | 27.62 |
| `SWING_S break ctrl+engulf+htf|1d` | **WEAK** | 24 | **66.67** | 58.33 | 75.0 | 75.0 | 50.0 | 49.34 | 31.55 |
| `SWING_S break ctrl+engulf+htf|all` | **WEAK** | 29 | **65.52** | 50.0 | 80.0 | 75.86 | 48.28 | 56.53 | 33.13 |
| `SWING_R break raw|1d` | **WEAK** | 76 | **64.47** | 66.67 | 62.16 | 73.68 | 47.37 | 47.66 | 32.48 |
| `SWING_R break ctrl+close_strong+htf|1d` | **WEAK** | 14 | **64.29** | 33.33 | 87.5 | 71.43 | 42.86 | 53.12 | 29.43 |
| `ALL break ctrl+held+!ext|1d` | **WEAK** | 61 | **63.93** | 51.85 | 73.53 | 73.77 | 47.54 | 48.92 | 28.41 |
| `SWING_R break ctrl+held+!ext|1d` | **WEAK** | 19 | **63.16** | 37.5 | 81.82 | 73.68 | 52.63 | 46.33 | 28.7 |
| `ALL break ctrl+atr_hi+htf|all` | **WEAK** | 52 | **61.54** | 57.89 | 63.64 | 82.69 | 28.85 | 61.69 | 43.18 |
| `SWING_R break ctrl+!ext+htf|1d` | **WEAK** | 18 | **61.11** | 28.57 | 81.82 | 66.67 | 55.56 | 45.71 | 25.15 |
| `ALL break ctrl+held+close_strong+htf|1d` | **WEAK** | 63 | **60.32** | 53.33 | 66.67 | 68.25 | 36.51 | 46.87 | 33.72 |
| `ALL break ctrl+!ext+htf|1d` | **WEAK** | 62 | **58.06** | 53.12 | 63.33 | 70.97 | 45.16 | 45.13 | 27.92 |
| `ALL break ctrl+held+htf|all` | **WEAK** | 123 | **57.72** | 48.0 | 64.38 | 65.85 | 34.96 | 45.39 | 32.98 |
| `SWING_R bounce ctrl+held|1d` | **WEAK** | 14 | **57.14** | 33.33 | 75.0 | 71.43 | 50.0 | 54.52 | 37.77 |
| `ALL break ctrl+held+ad+htf|all` | **WEAK** | 110 | **56.36** | 48.94 | 61.9 | 64.55 | 32.73 | 43.45 | 33.25 |
| `ALL break ctrl+held+htf|1d` | **WEAK** | 77 | **54.55** | 51.43 | 57.14 | 63.64 | 31.17 | 41.46 | 35.13 |
| `SWING_R bounce ctrl+held+!ext|1d` | **WEAK** | 13 | **53.85** | 33.33 | 71.43 | 69.23 | 46.15 | 51.48 | 40.61 |
| `ALL break ctrl+close_strong+htf|1d` | **WEAK** | 73 | **53.42** | 50.0 | 56.76 | 68.49 | 32.88 | 43.79 | 35.51 |
| `ALL break ctrl+held+ad+htf|1d` | **WEAK** | 75 | **53.33** | 51.43 | 55.0 | 62.67 | 28.0 | 40.29 | 35.4 |
| `ALL break ctrl+ad+htf|1d` | **WEAK** | 80 | **52.5** | 51.28 | 53.66 | 63.75 | 27.5 | 40.2 | 33.09 |
| `ALL break ctrl+atr_hi+htf|1d` | **WEAK** | 35 | **51.43** | 50.0 | 52.38 | 80.0 | 22.86 | 51.38 | 46.89 |
| `OR30 bounce raw|1d` | **WEAK** | 113 | **51.33** | 52.54 | 50.0 | 58.41 | 33.63 | 38.65 | 35.03 |
| `OR30 break ctrl+held+htf|1d` | **WEAK** | 26 | **50.0** | 54.55 | 46.67 | 53.85 | 30.77 | 34.95 | 33.89 |
| `OR30 break ctrl+held+htf|all` | **WEAK** | 26 | **50.0** | 54.55 | 46.67 | 53.85 | 30.77 | 34.95 | 33.89 |
| `PDHL break ctrl+atr_hi+htf|1d` | **WEAK** | 12 | **50.0** | 25.0 | 62.5 | 83.33 | 25.0 | 45.7 | 54.5 |
| `PDHL break ctrl+held+close_strong+htf|1d` | **WEAK** | 14 | **50.0** | 16.67 | 75.0 | 64.29 | 28.57 | 43.36 | 37.39 |
| `ALL break ctrl+held|1d` | **WEAK** | 92 | **50.0** | 50.0 | 50.0 | 65.22 | 32.61 | 40.45 | 36.92 |
| `ALL break ctrl+engulf+htf|all` | **WEAK** | 68 | **50.0** | 42.86 | 55.0 | 60.29 | 32.35 | 46.23 | 35.28 |
| `ALL break ctrl+engulf+htf|1d` | **WEAK** | 49 | **48.98** | 45.45 | 51.85 | 59.18 | 32.65 | 43.31 | 36.78 |
| `ALL break ctrl+htf|1d` | **WEAK** | 88 | **48.86** | 47.62 | 50.0 | 63.64 | 28.41 | 38.86 | 36.14 |
| `ALL bounce raw|1d` | **WEAK** | 119 | **47.9** | 45.0 | 50.85 | 62.18 | 25.21 | 42.77 | 42.81 |
| `PDHL bounce raw|1d` | **WEAK** | 69 | **47.83** | 51.61 | 44.74 | 57.97 | 24.64 | 39.83 | 43.71 |
| `ALL break ctrl|1d` | **WEAK** | 102 | **47.06** | 50.0 | 44.23 | 68.63 | 28.43 | 41.07 | 35.17 |
| `OR15 bounce ctrl+close_strong+htf|1d` | **WEAK** | 15 | **46.67** | 42.86 | 50.0 | 46.67 | 26.67 | 45.83 | 45.76 |
| `OR15 bounce raw|1d` | **WEAK** | 114 | **46.49** | 44.07 | 49.09 | 59.65 | 26.32 | 42.99 | 42.01 |
| `OR30 break ctrl+htf|1d` | **WEAK** | 28 | **46.43** | 54.55 | 41.18 | 53.57 | 28.57 | 37.53 | 32.75 |
| `OR15 break raw|1d` | **WEAK** | 108 | **46.3** | 46.43 | 46.15 | 66.67 | 26.85 | 41.76 | 38.93 |
| `OR15 bounce ctrl+atr_hi+htf|1d` | **WEAK** | 13 | **46.15** | 40.0 | 50.0 | 53.85 | 30.77 | 53.22 | 54.87 |
| `OR30 break ctrl+held+ad+htf|1d` | **WEAK** | 24 | **45.83** | 54.55 | 38.46 | 50.0 | 29.17 | 33.91 | 33.32 |
| `OR30 break ctrl+held+ad+htf|all` | **WEAK** | 24 | **45.83** | 54.55 | 38.46 | 50.0 | 29.17 | 33.91 | 33.32 |
| `SWING_R bounce ctrl|1d` | **WEAK** | 59 | **45.76** | 53.57 | 38.71 | 50.85 | 38.98 | 44.96 | 47.28 |

## 2) Hunt ≥75% m25_first

| Rule | Verdict | n | m25_first% | Train | OOS | m25% | clean15% |
|---|---|---:|---:|---:|---:|---:|---:|
| `SWING_S break|1d|ctrl+ad+not_extreme+close_strong` | **HIGH_75** | 32 | **81.25** | 76.47 | 86.67 | 84.38 | 56.25 |
| `SWING_S break|all|ctrl+htf_with+not_extreme+disp08` | **HIGH_75** | 21 | **80.95** | 81.82 | 80.0 | 80.95 | 61.9 |
| `SWING_S break|1d|ctrl+htf_with+not_extreme+close_strong` | **HIGH_75** | 26 | **80.77** | 73.33 | 90.91 | 80.77 | 61.54 |
| `SWING_S break|all|ctrl+not_extreme+disp08` | **HIGH_75** | 31 | **80.65** | 80.0 | 81.25 | 80.65 | 58.06 |
| `SWING_S break|all|ctrl+ad+not_extreme+close_strong` | **HIGH_75** | 36 | **80.56** | 77.78 | 83.33 | 83.33 | 55.56 |
| `SWING_S break|1d|ctrl+htf_with` | **HIGH_75** | 35 | **80.0** | 73.68 | 87.5 | 82.86 | 62.86 |
| `SWING_S break|1d|ctrl+ad+htf_with+close_strong` | **HIGH_75** | 25 | **80.0** | 75.0 | 84.62 | 80.0 | 60.0 |
| `SWING_S break|1d|ctrl+ad+htf_with+not_extreme` | **HIGH_75** | 25 | **80.0** | 76.92 | 83.33 | 84.0 | 64.0 |
| `SWING_S break|all|ctrl+ad+close_strong` | **HIGH_75** | 44 | **79.55** | 76.19 | 82.61 | 81.82 | 56.82 |
| `SWING_S break|all|ctrl+ad+htf_with+close_strong` | **HIGH_75** | 29 | **79.31** | 75.0 | 82.35 | 79.31 | 58.62 |
| `SWING_S break|1d|ctrl+ad+htf_with` | **HIGH_75** | 29 | **79.31** | 78.57 | 80.0 | 82.76 | 62.07 |
| `SWING_S break|all|ctrl+disp08` | **HIGH_75** | 38 | **78.95** | 73.68 | 84.21 | 81.58 | 55.26 |
| `SWING_S break|1d|ctrl+ad+close_strong` | **HIGH_75** | 38 | **78.95** | 73.68 | 84.21 | 81.58 | 55.26 |
| `SWING_S break|1d|ctrl+htf_with+not_extreme` | **HIGH_75** | 32 | **78.12** | 72.22 | 85.71 | 81.25 | 62.5 |
| `SWING_S break|1d|ctrl+htf_with+not_extreme+disp08` | **HIGH_75** | 18 | **77.78** | 81.82 | 71.43 | 77.78 | 61.11 |
| `SWING_S break|1d|ctrl+ad+not_extreme` | **HIGH_75** | 40 | **77.5** | 75.0 | 80.0 | 82.5 | 55.0 |
| `SWING_S break|all|ctrl+close_strong+disp08` | **HIGH_75** | 31 | **77.42** | 75.0 | 80.0 | 77.42 | 51.61 |
| `SWING_S break|all|ctrl+not_extreme+engulf+disp08` | **HIGH_75** | 22 | **77.27** | 72.73 | 81.82 | 77.27 | 54.55 |
| `SWING_S break|1d|ctrl+ad` | **HIGH_75** | 44 | **77.27** | 76.19 | 78.26 | 81.82 | 56.82 |
| `SWING_S break|1d|ctrl+not_extreme` | **HIGH_75** | 52 | **76.92** | 71.43 | 83.33 | 80.77 | 57.69 |
| `SWING_S break|all|ctrl+not_extreme+close_strong+disp08` | **HIGH_75** | 26 | **76.92** | 76.92 | 76.92 | 76.92 | 50.0 |
| `SWING_S break|1d|ctrl+not_extreme+disp08` | **HIGH_75** | 26 | **76.92** | 78.57 | 75.0 | 76.92 | 53.85 |
| `SWING_S break|all|ctrl+ad+htf_with+not_extreme` | **HIGH_75** | 30 | **76.67** | 71.43 | 81.25 | 83.33 | 56.67 |
| `SWING_S break|all|ctrl+ad+not_extreme` | **HIGH_75** | 47 | **76.6** | 72.73 | 80.0 | 82.98 | 53.19 |
| `SWING_S break|all|ctrl+ad` | **HIGH_75** | 59 | **76.27** | 71.43 | 80.65 | 83.05 | 52.54 |

## 3) Most accurate range S/R entry

**Best effort:** `SWING_S break|1d|ctrl+ad+not_extreme+close_strong` · **HIGH_75**
- m25_first **81.25%** · TRAIN **76.47%** · OOS **86.67%** · n=32
- raw m25 **84.38%** · clean15 **56.25%**
- avg MFE 56.12 · avg MAE 17.13

### Entry rule (side + price)

```
1) Build range level (OR15/OR30 edge, prior-day H/L, or swing cluster)
2) Zone = level ± 0.5×ATR14
3) BREAK path: close through → extend ≥0.5×ATR → retest zone → enter continuation close
   BOUNCE path: leave ≥0.5×ATR → retest zone → enter fade close
4) Apply best filters from this report (ctrl / held / htf / …)
SIDE  : BUY/SELL from path
ENTRY : close of signal 1m bar
```

### Samples

| Day | HM | Side | Entry | Level | MFE | MAE | m25_first | clean15 |
|---|---|---|---:|---:|---:|---:|---|---|
| 2026-05-26 | 11:20 | **SELL** | **24066.6** | 24067.19 | 48.1 | 5.3 | True | True |
| 2026-05-27 | 12:29 | **SELL** | **23906.3** | 23919.14 | 22.15 | 32.0 | False | False |
| 2026-06-05 | 11:14 | **SELL** | **23444.4** | 23449.91 | 51.3 | 7.8 | True | True |
| 2026-06-08 | 13:40 | **SELL** | **23184.95** | 23195.45 | 39.25 | 0.6 | True | True |
| 2026-06-10 | 14:21 | **SELL** | **23328.4** | 23341.5 | 143.8 | 9.7 | True | True |
| 2026-06-11 | 12:51 | **SELL** | **23278.6** | 23289.45 | 65.15 | 48.85 | False | False |
| 2026-06-15 | 11:15 | **SELL** | **23965.55** | 23972.4 | 42.15 | 17.4 | True | False |
| 2026-06-23 | 13:14 | **SELL** | **23922.6** | 23924.2 | 59.95 | 8.75 | True | True |
| 2026-06-25 | 14:18 | **SELL** | **24120.55** | 24130.95 | 79.1 | 8.35 | True | True |
| 2026-06-29 | 10:50 | **SELL** | **24070.45** | 24087.5 | 51.8 | 20.45 | True | False |

## 4) vs prior research

- OR break+retest was **PROVEN** for 3R expectancy (~40–45% hit) — different metric than m25_first.
- Gates ≥85% m25_first this pass: **0**
- Near-100% favour-first still requires PROVEN_100 / PROMISING_95 — report if absent.

_Generated in 10.5s._
