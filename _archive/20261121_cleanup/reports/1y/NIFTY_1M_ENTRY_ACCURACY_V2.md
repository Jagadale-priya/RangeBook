# NIFTY 1m — Entry accuracy **v2** (truth-aligned ignition)

> Fix: real ≥25pt moves rarely have `room_ok` / `disp10`. Align filters with truth rates.

Window **2026-05-26 → 2026-11-16** (120d). OOS **2026-08-20**.

## Insight

| Feature at true impulse | Rate | Use in gate? |
|---|---:|---|
| prev_opposite | ~99% | **required** (defines ignition) |
| control_with | ~84% | **required** |
| not_extreme | ~86% | **required** |
| bounce | ~59% | optional tighten |
| AD with | ~56% | optional tighten |
| room_ok | ~11% | **do not require** |
| disp10 | ~24% | **do not require** |

Entry modes: `ignition0` = close of flip bar · `confirm1` = wait 1 more same-color bar then enter.
Books reported as **1 trade/day** (first signal) for stability.

## 1) Truth-aligned gates (1/day · m25_first)

| Gate | Verdict | n | m25_first% | OOS | clean15% | avg MFE | avg MAE |
|---|---|---:|---:|---:|---:|---:|---:|
| `conf1 ctrl+!ext+ad+held+big_body` | **WEAK** | 86 | **52.33** | 51.11 | 24.42 | 39.79 | 39.67 |
| `ign0 prev_opp+ctrl+!ext+ad+held+big_body` | **WEAK** | 99 | **50.51** | 50.0 | 27.27 | 40.19 | 41.29 |
| `ign0 prev_opp+ctrl+!ext+held+big_body` | **WEAK** | 105 | **50.48** | 51.02 | 25.71 | 39.91 | 38.93 |
| `ign0 prev_opp+ctrl+!ext+held` | **WEAK** | 119 | **50.42** | 57.63 | 23.53 | 39.43 | 39.84 |
| `conf1 ctrl+!ext+ad+held+bounce+big_body` | **WEAK** | 74 | **50.0** | 50.0 | 29.73 | 41.28 | 38.96 |
| `conf1 ctrl+!ext+held+bounce+big_body` | **WEAK** | 75 | **49.33** | 48.78 | 28.0 | 43.02 | 40.37 |
| `ign0 prev_opp+ctrl+!ext+ad+held+bounce+big_body` | **WEAK** | 86 | **48.84** | 48.78 | 27.91 | 40.36 | 41.42 |
| `ign0 prev_opp+ctrl+!ext` | **WEAK** | 120 | **48.33** | 53.33 | 25.0 | 41.82 | 46.36 |
| `conf1 ctrl+!ext+ad+held+bounce+disp08` | **WEAK** | 99 | **47.47** | 48.0 | 28.28 | 35.02 | 39.31 |
| `conf1 ctrl+!ext` | **WEAK** | 120 | **45.83** | 48.33 | 22.5 | 37.99 | 48.73 |
| `ign0 prev_opp+ctrl+!ext+held+bounce` | **WEAK** | 119 | **44.54** | 52.54 | 22.69 | 39.07 | 39.22 |
| `conf1 ctrl+!ext+ad` | **WEAK** | 119 | **44.54** | 47.46 | 17.65 | 37.88 | 46.58 |
| `ign0 prev_opp+ctrl+!ext+held+ad` | **WEAK** | 119 | **43.7** | 49.15 | 21.85 | 35.88 | 40.62 |
| `ign0 prev_opp+ctrl+!ext+ad` | **WEAK** | 119 | **43.7** | 42.37 | 23.53 | 42.97 | 42.23 |
| `conf1 ctrl+!ext+ad+bounce+big_body` | **WEAK** | 110 | **43.64** | 44.44 | 26.36 | 35.34 | 42.59 |
| `ign0 prev_opp+ctrl+!ext+ad+bounce` | **WEAK** | 119 | **42.86** | 44.07 | 21.85 | 41.55 | 41.84 |
| `ign0 prev_opp+ctrl+!ext+big_body` | **WEAK** | 120 | **42.5** | 51.67 | 25.0 | 40.7 | 43.27 |
| `conf1 ctrl+!ext+ad+held` | **WEAK** | 119 | **42.02** | 49.15 | 18.49 | 32.46 | 40.98 |
| `ign0 prev_opp+ctrl+!ext+ad+big_body` | **WEAK** | 119 | **42.02** | 45.76 | 21.85 | 37.98 | 43.59 |
| `ign0 prev_opp+ctrl+!ext+bounce` | **WEAK** | 120 | **40.0** | 48.33 | 18.33 | 37.95 | 48.01 |
| `conf1 ctrl+!ext+ad+held+bounce` | **WEAK** | 118 | **37.29** | 40.68 | 20.34 | 33.49 | 37.21 |

## 2) Exhaustive hunt ≥85% m25_first (1/day)

### confirm1

_None._

### ignition0

_None._

## 3) Most accurate logic

**Best effort:** `conf1 ctrl+!ext+ad+held+big_body` · WEAK
- 1/day m25_first **52.33%** OOS **51.11%** n=86
- clean15 **24.42%** · avg MFE 39.79 · avg MAE 39.67

### Samples

| Day | HM | Side | Entry | MFE | MAE | m25_first | clean15 |
|---|---|---|---:|---:|---:|---|---|
| 2026-05-26 | 11:30 | **SELL** | **24028.45** | 11.0 | 43.45 | False | False |
| 2026-05-27 | 10:08 | **BUY** | **23938.55** | 37.85 | 19.65 | True | False |
| 2026-05-29 | 09:41 | **SELL** | **23901.9** | 30.8 | 52.6 | True | False |
| 2026-06-01 | 10:24 | **SELL** | **23549.6** | 31.9 | 69.65 | True | False |
| 2026-06-02 | 11:20 | **BUY** | **23323.85** | 40.1 | 47.25 | True | False |
| 2026-06-03 | 10:56 | **SELL** | **23233.4** | 38.6 | 11.45 | True | True |
| 2026-06-04 | 10:18 | **BUY** | **23447.9** | 2.2 | 73.1 | False | False |
| 2026-06-05 | 12:41 | **SELL** | **23387.9** | 95.75 | 2.25 | True | True |
| 2026-06-08 | 10:31 | **BUY** | **23195.8** | 27.65 | 16.8 | True | False |
| 2026-06-09 | 09:49 | **SELL** | **23184.9** | 53.5 | 31.8 | False | False |
| 2026-06-10 | 10:14 | **SELL** | **23317.0** | 11.2 | 71.9 | False | False |
| 2026-06-11 | 11:18 | **BUY** | **23202.75** | 104.3 | 3.4 | True | True |

## 4) Action for live IGN100

- Old `run_ignition_100` (room+disp10+bounce) is **not** the most accurate one-direction rule.
- Prefer a **truth-aligned** gate from this report once PROVEN_100 / PROMISING_95 appears.
- Until then: keep IGN100 as research mode, do not claim clean one-way accuracy.

_Generated in 36.2s._
