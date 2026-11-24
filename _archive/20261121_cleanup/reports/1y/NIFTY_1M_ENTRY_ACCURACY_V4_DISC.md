# NIFTY 1m — Entry accuracy **v4** (discriminator + pullback + OR)

> Deeper pass after v2 (~52%) and v3 join (~54%). Mines feature lift, pullback joins, OR break+retest.

Window **2026-05-26 → 2026-11-16** (120d). OOS **2026-08-20**.

## 0) Universe sizes

- Ignition (color flip): **16610**
- Pullback after run2/3: **7710**
- OR retest: **282**
- Ignition TRAIN base m25_first: **43.42%**

## 1) Feature lift (TRAIN ignition · m25_first)

| Feat | n | prec% | lift pp |
|---|---:|---:|---:|
| `atr_hi` | 1373 | 48.22 | +4.79 |
| `compress` | 334 | 47.6 | +4.18 |
| `big_body` | 980 | 47.55 | +4.13 |
| `room_ok` | 851 | 46.77 | +3.34 |
| `hl3` | 1282 | 46.33 | +2.91 |
| `disp08` | 1591 | 45.51 | +2.08 |
| `disp10` | 881 | 45.06 | +1.64 |
| `body_dom` | 3309 | 44.91 | +1.48 |
| `atr_ok` | 6848 | 44.7 | +1.28 |
| `runway2` | 589 | 44.48 | +1.06 |
| `close_strong` | 3750 | 44.43 | +1.00 |
| `engulf` | 1856 | 44.23 | +0.81 |
| `am` | 2461 | 43.84 | +0.42 |
| `ctrl` | 5838 | 43.75 | +0.32 |
| `pm` | 2575 | 43.73 | +0.30 |
| `not_extreme` | 7711 | 43.7 | +0.28 |
| `tight_wick` | 1065 | 43.57 | +0.14 |
| `cc2` | 7855 | 43.46 | +0.04 |
| `rsi_ok` | 8371 | 43.42 | +0.00 |
| `rsi_mid` | 8371 | 43.42 | +0.00 |

## 2) Curated gates (1/day · m25_first)

| Gate | Verdict | n | m25_first% | OOS | raw m25% | clean15% | avg MFE | avg MAE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `OR30 retest ctrl+held+ad+!ext` | **THIN** | 1 | **100.0** | None | 100.0 | 100.0 | 48.1 | 11.2 |
| `ign ctrl+!ext+held+tight_wick+body_dom` | **THIN** | 6 | **66.67** | 100.0 | 83.33 | 50.0 | 47.22 | 22.39 |
| `ign ctrl+!ext+held+close_strong` | **WEAK** | 119 | **46.22** | 55.93 | 59.66 | 19.33 | 35.88 | 40.48 |
| `pb run2/3 ctrl+!ext+held` | **WEAK** | 119 | **46.22** | 55.93 | 57.98 | 22.69 | 34.1 | 38.59 |
| `pb ctrl+!ext+held+hl3+already12` | **WEAK** | 33 | **45.45** | 46.15 | 60.61 | 27.27 | 39.11 | 30.65 |
| `ign ctrl+!ext+held+hl3+cc2` | **WEAK** | 112 | **44.64** | 49.09 | 51.79 | 22.32 | 33.52 | 36.65 |
| `ign IGN100-like room+disp10+bounce` | **WEAK** | 59 | **40.68** | 37.5 | 49.15 | 33.9 | 37.58 | 39.99 |
| `ign ctrl+!ext+held+htf+close_strong` | **THIN** | 0 | **None** | None | None | None | None | None |
| `ign ctrl+!ext+htf+compress` | **THIN** | 0 | **None** | None | None | None | None | None |
| `ign ctrl+!ext+htf+engulf+close_strong` | **THIN** | 0 | **None** | None | None | None | None | None |
| `ign ctrl+!ext+ad+held+htf+am` | **THIN** | 0 | **None** | None | None | None | None | None |
| `ign ctrl+!ext+htf+or15+close_strong` | **THIN** | 0 | **None** | None | None | None | None | None |
| `ign IGN100+htf` | **THIN** | 0 | **None** | None | None | None | None | None |
| `ign IGN100+held+htf` | **THIN** | 0 | **None** | None | None | None | None | None |
| `pb ctrl+!ext+held+htf` | **THIN** | 0 | **None** | None | None | None | None | None |
| `pb ctrl+!ext+held+ad+htf` | **THIN** | 0 | **None** | None | None | None | None | None |
| `pb ctrl+!ext+held+htf+already8+lt25` | **THIN** | 0 | **None** | None | None | None | None | None |
| `pb ctrl+!ext+htf+close_strong+already8` | **THIN** | 0 | **None** | None | None | None | None | None |
| `OR15 retest ctrl+htf` | **THIN** | 0 | **None** | None | None | None | None | None |
| `OR15 retest ctrl+held+htf` | **THIN** | 0 | **None** | None | None | None | None | None |
| `OR15 retest ctrl+held+ad+htf` | **THIN** | 0 | **None** | None | None | None | None | None |
| `OR30 retest ctrl+htf` | **THIN** | 0 | **None** | None | None | None | None | None |
| `OR30 retest ctrl+held+htf` | **THIN** | 0 | **None** | None | None | None | None | None |
| `OR30 retest ctrl+held+htf+close_strong` | **THIN** | 0 | **None** | None | None | None | None | None |

## 3) Exhaustive hunt ≥75% m25_first (1/day)

| Rule | Verdict | n | m25_first% | OOS | raw m25% | clean15% |
|---|---|---:|---:|---:|---:|---:|
| `pb|1d|atr_hi+compress+engulf+ctrl` | **HIGH_75** | 15 | **80.0** | 80.0 | 80.0 | 33.33 |
| `pb|1d|atr_hi+compress+big_body+engulf+ctrl` | **HIGH_75** | 15 | **80.0** | 80.0 | 80.0 | 33.33 |
| `pb|1d|atr_hi+compress+disp08+engulf+ctrl` | **HIGH_75** | 15 | **80.0** | 80.0 | 80.0 | 33.33 |
| `pb|1d|atr_hi+compress+body_dom+engulf+ctrl` | **HIGH_75** | 15 | **80.0** | 80.0 | 80.0 | 33.33 |
| `pb|1d|atr_hi+compress+atr_ok+engulf+ctrl` | **HIGH_75** | 15 | **80.0** | 80.0 | 80.0 | 33.33 |
| `pb|1d|atr_hi+compress+big_body+disp08+engulf+ctrl` | **HIGH_75** | 15 | **80.0** | 80.0 | 80.0 | 33.33 |
| `pb|1d|atr_hi+compress+big_body+body_dom+engulf+ctrl` | **HIGH_75** | 15 | **80.0** | 80.0 | 80.0 | 33.33 |
| `pb|1d|atr_hi+compress+big_body+atr_ok+engulf+ctrl` | **HIGH_75** | 15 | **80.0** | 80.0 | 80.0 | 33.33 |
| `pb|1d|atr_hi+compress+disp08+body_dom+engulf+ctrl` | **HIGH_75** | 15 | **80.0** | 80.0 | 80.0 | 33.33 |
| `pb|1d|atr_hi+compress+disp08+atr_ok+engulf+ctrl` | **HIGH_75** | 15 | **80.0** | 80.0 | 80.0 | 33.33 |
| `pb|1d|atr_hi+compress+body_dom+atr_ok+engulf+ctrl` | **HIGH_75** | 15 | **80.0** | 80.0 | 80.0 | 33.33 |
| `pb|1d|atr_hi+room_ok+close_strong+am+ctrl` | **HIGH_75** | 20 | **75.0** | 70.0 | 85.0 | 25.0 |
| `pb|1d|atr_hi+room_ok+atr_ok+close_strong+am+ctrl` | **HIGH_75** | 20 | **75.0** | 70.0 | 85.0 | 25.0 |
| `pb|1d|atr_hi+room_ok+close_strong+am+ctrl+not_extreme` | **HIGH_75** | 20 | **75.0** | 70.0 | 85.0 | 25.0 |
| `pb|1d|atr_hi+compress+engulf+ctrl+not_extreme` | **THIN** | 14 | **85.71** | 80.0 | 85.71 | 35.71 |
| `pb|1d|atr_hi+compress+big_body+engulf+ctrl+not_extreme` | **THIN** | 14 | **85.71** | 80.0 | 85.71 | 35.71 |
| `pb|1d|atr_hi+compress+disp08+engulf+ctrl+not_extreme` | **THIN** | 14 | **85.71** | 80.0 | 85.71 | 35.71 |
| `pb|1d|atr_hi+compress+body_dom+engulf+ctrl+not_extreme` | **THIN** | 14 | **85.71** | 80.0 | 85.71 | 35.71 |
| `pb|1d|atr_hi+compress+atr_ok+engulf+ctrl+not_extreme` | **THIN** | 14 | **85.71** | 80.0 | 85.71 | 35.71 |
| `pb|1d|atr_hi+compress+close_strong+engulf+ctrl+not_extreme` | **THIN** | 13 | **84.62** | 77.78 | 84.62 | 38.46 |
| `pb|1d|atr_hi+compress+close_strong+engulf+ctrl` | **THIN** | 14 | **78.57** | 77.78 | 78.57 | 35.71 |
| `pb|1d|atr_hi+compress+big_body+close_strong+engulf+ctrl` | **THIN** | 14 | **78.57** | 77.78 | 78.57 | 35.71 |
| `pb|1d|atr_hi+compress+disp08+close_strong+engulf+ctrl` | **THIN** | 14 | **78.57** | 77.78 | 78.57 | 35.71 |
| `pb|1d|atr_hi+compress+body_dom+close_strong+engulf+ctrl` | **THIN** | 14 | **78.57** | 77.78 | 78.57 | 35.71 |
| `pb|1d|atr_hi+compress+atr_ok+close_strong+engulf+ctrl` | **THIN** | 14 | **78.57** | 77.78 | 78.57 | 35.71 |

## 4) Perfect raw-m25 books (honest m25_first)

_None with train+OOS 100% raw m25, n≥10._

## 5) Most accurate logic this pass

**Best effort:** `OR30 retest ctrl+held+ad+!ext` · THIN
- 1/day m25_first **100.0%** OOS **None%** n=1
- raw m25 **100.0%** · clean15 **100.0%**
- avg MFE 48.1 · avg MAE 11.2

### Samples

| Day | HM | Side | Entry | MFE | MAE | m25_first | clean15 |
|---|---|---|---:|---:|---:|---|---|
| 2026-06-10 | 10:52 | **BUY** | **23361.7** | 48.1 | 11.2 | True | True |

## 6) Action vs live IGN100

- Keep judging on **m25_first** (favour-first), not raw m25 alone.
- Replace IGN100 only if this pass yields PROVEN_100 / PROMISING_95 on m25_first.
- If best remains WEAK/HIGH_75: near-100% one-way entry is **not** established on 120d.

_Generated in 189.7s._
