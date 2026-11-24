# NIFTY 1m — **Oracle T15 × Desk (Fib·EMA·VWAP·BB) × same-color 4–6**

> Deep entry accuracy. Target later. Metric = **T15 win** under EMA34 trail (same as scalper Oracle T15).

Window **2026-05-26 → 2026-11-16** (120d). OOS **2026-08-20**. Events **24807**.

## Recipe under test

```
1) Textbook pattern event (Oracle universe)
2) Require 4–6 consecutive same-color 1m bars ending at entry
3) Desk confluence: VWAP / EMA9-20 stack / EMA50 / BB / Fib nearby
4) Side = pattern decision · Exit check = EMA34 trail · T15
```

## 0) Raw Oracle vs streak cut

- Raw textbook T15 win (all signals): **30.6%** n=24807
- Among streak≥4: T15 win **39.3%** n=5294

## 1) Desk marks on streak≥4 winners vs losers

| Mark | % of Winners | % of Losers | Lift pp |
|---|---:|---:|---:|
| `vwap_with` | 80.7 | 61.0 | 19.7 |
| `ema_with` | 87.4 | 59.8 | 27.6 |
| `ema50_with` | 92.6 | 67.0 | 25.6 |
| `bb_bounce` | 0.0 | 0.1 | -0.1 |
| `bb_mid_with` | 96.3 | 81.4 | 14.9 |
| `fib_near` | 18.8 | 33.8 | -15.0 |
| `held` | 53.1 | 30.6 | 22.5 |
| `setup_ok` | 2.5 | 1.4 | 1.1 |
| `desk_ge2` | 97.7 | 82.0 | 15.7 |
| `desk_ge3` | 93.5 | 68.9 | 24.6 |
| `desk_ge4` | 78.6 | 53.4 | 25.2 |

## 2) Curated gates (1/day · T15 win%)

| Gate | Verdict | n | T15% | Train | OOS | gap n/prec | avg pts |
|---|---|---:|---:|---:|---:|---|---:|
| `desk≥3` | **WEAK** | 120 | **63.33** | 61.67 | 65.0 | 2208/42.71 | 0.91 |
| `Oracle + held` | **WEAK** | 119 | **63.03** | 55.0 | 71.19 | 1414/50.07 | 0.65 |
| `ema_with` | **WEAK** | 120 | **62.5** | 61.67 | 63.33 | 2166/42.57 | 0.46 |
| `streak≥6+desk≥2+held` | **WEAK** | 109 | **62.39** | 60.34 | 64.71 | 330/53.03 | 1.43 |
| `streak≥6+desk≥3+held` | **WEAK** | 109 | **62.39** | 60.34 | 64.71 | 330/53.03 | 1.43 |
| `streak≥6+desk≥2+setup` | **WEAK** | 29 | **62.07** | 56.25 | 69.23 | 37/59.46 | 4.18 |
| `desk≥4` | **WEAK** | 120 | **61.67** | 61.67 | 61.67 | 2030/43.6 | 0.21 |
| `streak≥5+desk≥2+setup` | **WEAK** | 39 | **61.54** | 54.55 | 70.59 | 55/56.36 | 3.69 |
| `desk≥2` | **WEAK** | 120 | **60.0** | 60.0 | 60.0 | 2275/40.13 | 0.81 |
| `streak≥5+desk≥2+held` | **WEAK** | 116 | **57.76** | 55.93 | 59.65 | 489/51.94 | 0.3 |
| `streak≥5+desk≥3+held` | **WEAK** | 116 | **57.76** | 55.93 | 59.65 | 489/51.94 | 0.3 |
| `streak≥4+desk≥2+held` | **WEAK** | 119 | **57.14** | 48.33 | 66.1 | 753/53.12 | -1.25 |
| `streak≥4+desk≥3+held` | **WEAK** | 119 | **57.14** | 48.33 | 66.1 | 753/53.12 | -1.25 |
| `vwap_with` | **WEAK** | 120 | **55.83** | 60.0 | 51.67 | 2162/38.39 | 1.45 |
| `streak≥4+desk≥3` | **WEAK** | 119 | **54.62** | 45.0 | 64.41 | 1279/46.91 | -1.57 |
| `streak≥6+desk≥3` | **WEAK** | 118 | **54.24** | 55.0 | 53.45 | 586/46.76 | 0.22 |
| `streak≥6+vwap+ema` | **WEAK** | 115 | **53.91** | 51.67 | 56.36 | 460/49.13 | -0.14 |
| `streak≥6+vwap+ema+bbmid` | **WEAK** | 115 | **53.91** | 51.67 | 56.36 | 457/49.23 | -0.14 |
| `streak≥4+vwap+ema` | **WEAK** | 119 | **53.78** | 45.0 | 62.71 | 1035/49.47 | -2.46 |
| `streak≥4+vwap+ema+bbmid` | **WEAK** | 119 | **53.78** | 45.0 | 62.71 | 1025/49.56 | -2.46 |
| `streak≥4+desk≥2+setup` | **WEAK** | 60 | **53.33** | 43.75 | 64.29 | 86/52.33 | 2.09 |
| `Oracle + streak≥6` | **WEAK** | 119 | **52.94** | 53.33 | 52.54 | 662/41.54 | 1.04 |
| `streak≥6` | **WEAK** | 119 | **52.94** | 53.33 | 52.54 | 662/41.54 | 1.04 |
| `streak≥6+desk≥2` | **WEAK** | 119 | **52.94** | 53.33 | 52.54 | 634/43.38 | 0.89 |
| `streak≥4+desk≥2` | **WEAK** | 120 | **50.83** | 38.33 | 63.33 | 1382/42.69 | -0.47 |
| `Oracle + streak≥4` | **WEAK** | 120 | **47.5** | 36.67 | 58.33 | 1493/37.71 | -0.71 |
| `streak≥4` | **WEAK** | 120 | **47.5** | 36.67 | 58.33 | 1493/37.71 | -0.71 |
| `Oracle raw (all textbook)` | **WEAK** | 120 | **46.67** | 51.67 | 41.67 | 2379/29.55 | -0.17 |
| `streak≥5+desk≥3` | **WEAK** | 119 | **46.22** | 43.33 | 49.15 | 880/44.89 | -2.82 |
| `streak≥5+vwap+ema` | **WEAK** | 118 | **45.76** | 41.67 | 50.0 | 686/47.81 | -3.46 |
| `streak≥5+vwap+ema+bbmid` | **WEAK** | 118 | **45.76** | 41.67 | 50.0 | 680/47.94 | -3.46 |
| `streak≥4+vwap+ema+fib` | **WEAK** | 104 | **45.19** | 32.08 | 58.82 | 230/37.39 | -0.49 |
| `streak≥5+vwap+ema+fib` | **WEAK** | 75 | **42.67** | 30.77 | 55.56 | 134/36.57 | 0.5 |
| `Oracle + setup_ok` | **WEAK** | 113 | **42.48** | 31.58 | 53.57 | 332/44.28 | -1.81 |
| `streak≥5+desk≥2` | **WEAK** | 120 | **41.67** | 35.0 | 48.33 | 955/41.26 | -1.91 |
| `Oracle + streak≥5` | **WEAK** | 120 | **40.83** | 35.0 | 46.67 | 1019/38.27 | -1.35 |
| `streak≥5` | **WEAK** | 120 | **40.83** | 35.0 | 46.67 | 1019/38.27 | -1.35 |
| `streak≥6+vwap+ema+fib` | **WEAK** | 54 | **40.74** | 36.67 | 45.83 | 77/37.66 | 0.06 |
| `fib_near` | **WEAK** | 120 | **36.67** | 30.0 | 43.33 | 1479/22.18 | 1.39 |
| `streak≥4+bb_bounce+vwap` | **THIN** | 3 | **33.33** | 50.0 | 0.0 | 4/25.0 | 3.5 |
| `streak≥5+bb_bounce+vwap` | **THIN** | 3 | **33.33** | 50.0 | 0.0 | 3/33.33 | 3.93 |
| `bb_bounce` | **WEAK** | 111 | **3.6** | 5.26 | 1.85 | 391/4.09 | -0.87 |
| `streak≥6+bb_bounce+vwap` | **THIN** | 1 | **0.0** | None | 0.0 | 1/0.0 | 0.8 |

## 3) Hunt ≥65% T15 (1/day, n≥15)

_None._

## 4) Most accurate entry (this pass)

**Best effort:** `desk≥3` · **WEAK**
- 1/day T15 **63.33%** · TRAIN **61.67%** · OOS **65.0%** · n=120

### How it moves with indication

1. Wait for **4–6 same-color** 1m bars (direction locked).
2. Prefer entry when **Desk** agrees: VWAP side + EMA stack (+ BB/Fib if present).
3. Take **Oracle textbook** event at that bar (side from pattern).
4. Manage with **EMA34 trail · T15** (same as scalper).

### Samples

| Day | HM | Side | Entry | streak | desk | T15 |
|---|---|---|---:|---:|---:|---|
| 2026-05-26 | 09:31 | **BUY** | **24036.0** | 1 | 4 | False |
| 2026-05-27 | 09:30 | **SELL** | **23893.85** | 9 | 5 | True |
| 2026-05-29 | 09:37 | **BUY** | **23933.35** | 3 | 4 | False |
| 2026-06-01 | 09:30 | **BUY** | **23605.95** | 1 | 3 | False |
| 2026-06-02 | 09:30 | **SELL** | **23276.9** | 2 | 3 | True |
| 2026-06-03 | 09:30 | **SELL** | **23276.9** | 2 | 4 | True |
| 2026-06-04 | 09:30 | **SELL** | **23330.4** | 2 | 5 | True |
| 2026-06-05 | 09:30 | **BUY** | **23474.15** | 3 | 5 | False |

## 5) Verdict for live scalper

- Gates ≥75% T15 walk-forward: **0**
- If best ≥75% OOS-stable: candidate filter = streak 4–6 + desk confluence on Oracle T15.
- If still <70%: streak cuts noise but desk alone does not unlock near-certain entries.

_Generated in 200.7s._
