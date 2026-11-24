# NIFTY 1m — Entry accuracy **v5** (focus · HTF fixed)

> Follow-up to v4 lead: `pb atr_hi+compress+engulf+ctrl` @ ~80% m25_first. HTF bias key fixed (`up`/`down`).

Window **2026-05-26 → 2026-11-16** (120d). OOS **2026-08-20**.

Pullback cands **7710** · Ignition **16610** · HTF-with on pb **50.0%**

## 1) Focus gates

| Gate | Verdict | n | m25_first% | Train | OOS | raw m25% | clean15% | MFE | MAE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `pb atr_hi+compress+engulf+ctrl+!ext|1d` | **HIGH_85** | 14 | **85.71** | 100.0 | 80.0 | 85.71 | 35.71 | 67.46 | 21.34 |
| `pb atr_hi+compress+engulf+ctrl+!ext|all` | **HIGH_85** | 21 | **85.71** | 100.0 | 80.0 | 85.71 | 38.1 | 73.31 | 22.45 |
| `pb atr_hi+compress+engulf+ctrl|1d` | **HIGH_75** | 15 | **80.0** | 80.0 | 80.0 | 80.0 | 33.33 | 63.76 | 25.96 |
| `pb atr_hi+compress+engulf+ctrl+already8|1d` | **HIGH_75** | 15 | **80.0** | 80.0 | 80.0 | 80.0 | 33.33 | 63.76 | 25.96 |
| `pb atr_hi+compress+engulf+ctrl+ad|1d` | **HIGH_75** | 14 | **78.57** | 80.0 | 77.78 | 78.57 | 28.57 | 56.69 | 26.93 |
| `pb atr_hi+compress+engulf+ctrl+close_strong|1d` | **HIGH_75** | 14 | **78.57** | 80.0 | 77.78 | 78.57 | 35.71 | 62.78 | 26.54 |
| `pb atr_hi+compress+engulf+ctrl|all` | **HIGH_75** | 23 | **78.26** | 75.0 | 80.0 | 78.26 | 34.78 | 67.96 | 28.38 |
| `pb atr_hi+compress+engulf+ctrl+already8|all` | **HIGH_75** | 23 | **78.26** | 75.0 | 80.0 | 78.26 | 34.78 | 67.96 | 28.38 |
| `pb atr_hi+compress+engulf+ctrl+close_strong|all` | **HIGH_75** | 22 | **77.27** | 75.0 | 78.57 | 77.27 | 36.36 | 67.53 | 28.86 |
| `pb atr_hi+compress+engulf+ctrl+ad|all` | **HIGH_75** | 21 | **76.19** | 75.0 | 76.92 | 76.19 | 28.57 | 58.94 | 29.9 |
| `pb atr_hi+compress+engulf+ctrl+held+htf|1d` | **THIN** | 4 | **100.0** | 100.0 | 100.0 | 100.0 | 50.0 | 66.15 | 19.11 |
| `pb atr_hi+compress+engulf+ctrl+held+htf|all` | **THIN** | 6 | **100.0** | 100.0 | 100.0 | 100.0 | 33.33 | 65.79 | 23.92 |
| `pb atr_hi+compress+engulf+ctrl+htf|all` | **THIN** | 11 | **90.91** | 100.0 | 87.5 | 90.91 | 36.36 | 73.5 | 25.17 |
| `pb atr_hi+compress+engulf+ctrl+htf|1d` | **THIN** | 8 | **87.5** | 100.0 | 80.0 | 87.5 | 37.5 | 64.44 | 24.66 |
| `pb atr_hi+compress+ctrl+htf+close_strong|all` | **THIN** | 13 | **84.62** | 100.0 | 77.78 | 84.62 | 38.46 | 66.81 | 31.83 |
| `pb atr_hi+compress+ctrl+htf+close_strong|1d` | **THIN** | 10 | **80.0** | 100.0 | 66.67 | 80.0 | 40.0 | 57.57 | 33.43 |
| `pb atr_hi+compress+engulf+ctrl+held|1d` | **THIN** | 8 | **75.0** | 50.0 | 83.33 | 75.0 | 37.5 | 61.17 | 30.93 |
| `pb atr_hi+compress+engulf+ctrl+held|all` | **THIN** | 12 | **75.0** | 33.33 | 88.89 | 75.0 | 25.0 | 61.76 | 35.22 |
| `pb compress+engulf+ctrl+htf|1d` | **WEAK** | 35 | **74.29** | 73.91 | 75.0 | 80.0 | 60.0 | 47.51 | 17.9 |
| `pb atr_hi+compress+engulf+ctrl+am|1d` | **THIN** | 11 | **72.73** | 75.0 | 71.43 | 72.73 | 36.36 | 61.64 | 26.69 |
| `pb atr_hi+compress+engulf+ctrl+am|all` | **THIN** | 18 | **72.22** | 71.43 | 72.73 | 72.22 | 38.89 | 68.76 | 28.15 |
| `pb compress+engulf+ctrl+htf|all` | **WEAK** | 74 | **68.92** | 67.39 | 71.43 | 77.03 | 47.3 | 45.89 | 21.15 |
| `pb atr_hi+compress+engulf_close+ctrl|1d` | **WEAK** | 21 | **66.67** | 77.78 | 58.33 | 76.19 | 23.81 | 51.3 | 35.77 |
| `pb atr_hi+engulf+ctrl+htf+!ext|1d` | **WEAK** | 45 | **64.44** | 61.11 | 66.67 | 66.67 | 31.11 | 46.34 | 39.02 |
| `pb atr_ok+compress+engulf+ctrl|all` | **WEAK** | 116 | **62.93** | 60.0 | 66.67 | 71.55 | 42.24 | 45.74 | 26.78 |
| `pb atr_hi+compress+engulf_close+ctrl|all` | **WEAK** | 36 | **61.11** | 62.5 | 60.0 | 66.67 | 25.0 | 54.48 | 43.25 |
| `pb atr_ok+compress+engulf+ctrl|1d` | **WEAK** | 58 | **60.34** | 60.61 | 60.0 | 67.24 | 43.1 | 42.84 | 27.01 |
| `pb atr_hi+engulf+ctrl+htf+!ext|all` | **WEAK** | 120 | **60.0** | 56.86 | 62.32 | 67.5 | 27.5 | 46.1 | 45.45 |
| `pb atr_hi+compress_soft+engulf+ctrl|1d` | **WEAK** | 40 | **55.0** | 50.0 | 58.33 | 70.0 | 22.5 | 46.54 | 42.38 |
| `pb atr_hi+compress_soft+engulf+ctrl|all` | **WEAK** | 86 | **54.65** | 39.39 | 64.15 | 69.77 | 22.09 | 46.4 | 45.68 |
| `ign ctrl+!ext+held+htf+ad+big_body|1d` | **WEAK** | 84 | **53.57** | 52.27 | 55.0 | 61.9 | 26.19 | 41.21 | 41.16 |
| `ign ctrl+!ext+held+htf+ad+big_body|all` | **WEAK** | 249 | **53.41** | 53.04 | 53.73 | 64.26 | 30.52 | 47.92 | 39.63 |
| `ign ctrl+!ext+held+htf+close_strong|1d` | **WEAK** | 118 | **52.54** | 47.46 | 57.63 | 62.71 | 30.51 | 36.25 | 36.49 |
| `ign atr_hi+compress+engulf+ctrl+htf|all` | **WEAK** | 79 | **51.9** | 47.06 | 55.56 | 69.62 | 21.52 | 45.45 | 48.25 |
| `ign atr_hi+compress+engulf+ctrl+htf|1d` | **WEAK** | 42 | **50.0** | 50.0 | 50.0 | 71.43 | 16.67 | 43.67 | 44.92 |
| `ign IGN100+htf|1d` | **WEAK** | 34 | **50.0** | 50.0 | 50.0 | 55.88 | 41.18 | 35.29 | 35.18 |
| `ign IGN100+htf|all` | **WEAK** | 36 | **50.0** | 47.83 | 53.85 | 58.33 | 41.67 | 37.87 | 34.2 |
| `ign ctrl+!ext+held+htf+close_strong|all` | **WEAK** | 1103 | **48.59** | 45.37 | 51.81 | 56.84 | 29.37 | 39.82 | 35.4 |
| `ign atr_hi+compress+engulf+ctrl|all` | **WEAK** | 120 | **47.5** | 46.67 | 48.0 | 64.17 | 20.0 | 44.19 | 51.78 |
| `ign IGN100 room+disp10+bounce+ctrl|all` | **WEAK** | 77 | **46.75** | 48.84 | 44.12 | 57.14 | 35.06 | 42.7 | 38.62 |
| `ign atr_hi+compress+engulf+ctrl|1d` | **WEAK** | 55 | **45.45** | 48.0 | 43.33 | 69.09 | 18.18 | 43.87 | 46.63 |
| `ign IGN100 room+disp10+bounce+ctrl|1d` | **WEAK** | 59 | **40.68** | 42.86 | 37.5 | 49.15 | 33.9 | 37.58 | 39.99 |

## 2) Exhaustive around lead (≥75%)

| Rule | Verdict | n | m25_first% | Train | OOS | m25% | clean15% |
|---|---|---:|---:|---:|---:|---:|---:|
| `pb|all|atr_hi+compress+engulf+ctrl+not_extreme` | **HIGH_85** | 21 | **85.71** | 100.0 | 80.0 | 85.71 | 38.1 |
| `pb|all|atr_hi+compress+compress_soft+engulf+ctrl+not_extreme` | **HIGH_85** | 21 | **85.71** | 100.0 | 80.0 | 85.71 | 38.1 |
| `pb|all|atr_hi+compress+engulf+engulf_close+ctrl+not_extreme` | **HIGH_85** | 21 | **85.71** | 100.0 | 80.0 | 85.71 | 38.1 |
| `pb|all|atr_hi+compress+engulf+ctrl+not_extreme+already8` | **HIGH_85** | 21 | **85.71** | 100.0 | 80.0 | 85.71 | 38.1 |
| `pb|all|atr_hi+compress+engulf+ctrl+not_extreme+big_body` | **HIGH_85** | 21 | **85.71** | 100.0 | 80.0 | 85.71 | 38.1 |
| `pb|all|atr_hi+compress+engulf+ctrl+not_extreme+disp08` | **HIGH_85** | 21 | **85.71** | 100.0 | 80.0 | 85.71 | 38.1 |
| `pb|all|atr_hi+compress+engulf+ctrl+not_extreme+body_dom` | **HIGH_85** | 21 | **85.71** | 100.0 | 80.0 | 85.71 | 38.1 |
| `pb|1d|atr_hi+compress+engulf+ctrl+not_extreme` | **HIGH_85** | 14 | **85.71** | 100.0 | 80.0 | 85.71 | 35.71 |
| `pb|1d|atr_hi+compress+compress_soft+engulf+ctrl+not_extreme` | **HIGH_85** | 14 | **85.71** | 100.0 | 80.0 | 85.71 | 35.71 |
| `pb|1d|atr_hi+compress+engulf+engulf_close+ctrl+not_extreme` | **HIGH_85** | 14 | **85.71** | 100.0 | 80.0 | 85.71 | 35.71 |
| `pb|1d|atr_hi+compress+engulf+ctrl+not_extreme+already8` | **HIGH_85** | 14 | **85.71** | 100.0 | 80.0 | 85.71 | 35.71 |
| `pb|1d|atr_hi+compress+engulf+ctrl+not_extreme+big_body` | **HIGH_85** | 14 | **85.71** | 100.0 | 80.0 | 85.71 | 35.71 |
| `pb|1d|atr_hi+compress+engulf+ctrl+not_extreme+disp08` | **HIGH_85** | 14 | **85.71** | 100.0 | 80.0 | 85.71 | 35.71 |
| `pb|1d|atr_hi+compress+engulf+ctrl+not_extreme+body_dom` | **HIGH_85** | 14 | **85.71** | 100.0 | 80.0 | 85.71 | 35.71 |
| `pb|all|atr_hi+compress+engulf+ctrl+not_extreme+close_strong` | **HIGH_75** | 20 | **85.0** | 100.0 | 78.57 | 85.0 | 40.0 |
| `pb|1d|atr_hi+compress+engulf+ctrl+not_extreme+ad` | **HIGH_75** | 13 | **84.62** | 100.0 | 77.78 | 84.62 | 30.77 |
| `pb|1d|atr_hi+compress+engulf+ctrl+not_extreme+close_strong` | **HIGH_75** | 13 | **84.62** | 100.0 | 77.78 | 84.62 | 38.46 |
| `pb|1d|atr_hi+compress_soft+engulf+ctrl+ad+disp08` | **HIGH_75** | 19 | **84.21** | 85.71 | 83.33 | 84.21 | 31.58 |
| `pb|all|atr_hi+engulf+ctrl+ad+htf_with+disp08` | **HIGH_75** | 36 | **83.33** | 90.91 | 80.0 | 86.11 | 38.89 |
| `pb|all|atr_hi+engulf+ctrl+htf_with+already8+disp08` | **HIGH_75** | 47 | **82.98** | 91.67 | 80.0 | 87.23 | 46.81 |
| `pb|1d|atr_hi+compress_soft+engulf+ctrl+already8+disp08` | **HIGH_75** | 23 | **82.61** | 87.5 | 80.0 | 82.61 | 39.13 |
| `pb|1d|atr_hi+compress_soft+engulf+ctrl+not_extreme+disp08` | **HIGH_75** | 23 | **82.61** | 100.0 | 76.47 | 86.96 | 39.13 |
| `pb|1d|atr_hi+compress_soft+engulf+ctrl+htf_with+disp08` | **HIGH_75** | 17 | **82.35** | 100.0 | 72.73 | 88.24 | 35.29 |
| `pb|all|atr_hi+engulf+ctrl+htf_with+disp08` | **HIGH_75** | 56 | **82.14** | 94.12 | 76.92 | 89.29 | 44.64 |
| `pb|all|atr_hi+engulf+engulf_close+ctrl+htf_with+disp08` | **HIGH_75** | 56 | **82.14** | 94.12 | 76.92 | 89.29 | 44.64 |
| `pb|all|atr_hi+engulf+ctrl+htf_with+big_body+disp08` | **HIGH_75** | 56 | **82.14** | 94.12 | 76.92 | 89.29 | 44.64 |
| `pb|all|atr_hi+engulf+ctrl+htf_with+disp08+body_dom` | **HIGH_75** | 56 | **82.14** | 94.12 | 76.92 | 89.29 | 44.64 |
| `pb|all|atr_hi+engulf+ctrl+not_extreme+htf_with+disp08` | **HIGH_75** | 48 | **81.25** | 100.0 | 72.73 | 89.58 | 41.67 |
| `pb|all|compress+engulf+ctrl+htf_with+close_strong+big_body` | **HIGH_75** | 32 | **81.25** | 88.89 | 71.43 | 81.25 | 34.38 |
| `pb|all|atr_hi+compress_soft+engulf+ctrl+already8+disp08` | **HIGH_75** | 37 | **81.08** | 83.33 | 80.0 | 83.78 | 40.54 |

## 3) Most accurate logic

**Best effort:** `pb atr_hi+compress+engulf+ctrl+!ext|all` · **HIGH_85**
- m25_first **85.71%** · TRAIN **100.0%** · OOS **80.0%** · n=21
- raw m25 **85.71%** · clean15 **38.1%**
- avg MFE 73.31 · avg MAE 22.45

### Entry rule (side + price)

```
1) Wait for bull_run2/3 or bear_run2/3 on 1m
2) Within 8 bars: opposite-color pullback that touches ignition bar range
3) Next same-color continuation bar = ENTRY BAR
4) Filters (best): atr≥10 + prior bar compress + engulf + control close
SIDE  : BUY/SELL from run direction
ENTRY : close of continuation bar
```

### Samples

| Day | HM | Side | Entry | MFE | MAE | m25_first | clean15 |
|---|---|---|---:|---:|---:|---|---|
| 2026-06-04 | 13:26 | **BUY** | **23364.4** | 69.35 | 18.25 | True | False |
| 2026-06-29 | 09:49 | **SELL** | **24082.7** | 30.95 | 37.3 | True | False |
| 2026-06-29 | 10:34 | **SELL** | **24105.35** | 86.7 | 11.1 | True | True |
| 2026-06-29 | 10:34 | **SELL** | **24105.35** | 86.7 | 11.1 | True | True |
| 2026-07-07 | 10:48 | **BUY** | **24488.7** | 37.05 | 18.85 | True | False |
| 2026-07-24 | 09:34 | **SELL** | **23688.6** | 82.3 | 7.6 | True | True |
| 2026-08-31 | 09:38 | **SELL** | **24050.1** | 52.15 | 1.8 | True | True |
| 2026-09-29 | 09:54 | **BUY** | **22605.55** | 13.7 | 34.0 | False | False |
| 2026-10-05 | 10:14 | **SELL** | **22543.75** | 82.95 | 16.75 | True | False |
| 2026-10-05 | 10:14 | **SELL** | **22543.75** | 82.95 | 16.75 | True | False |
| 2026-10-12 | 10:14 | **SELL** | **22486.0** | 109.75 | 17.4 | True | False |
| 2026-10-12 | 10:14 | **SELL** | **22486.0** | 109.75 | 17.4 | True | False |

## 4) Ship decision

- Gates ≥85% walk-forward: **16**
- Do **not** replace live IGN100 claiming 100% one-way unless PROVEN_100 / PROMISING_95 appears.
- Current best accuracy class: **HIGH_85** @ **85.71%** m25_first.

_Generated in 53.0s._
