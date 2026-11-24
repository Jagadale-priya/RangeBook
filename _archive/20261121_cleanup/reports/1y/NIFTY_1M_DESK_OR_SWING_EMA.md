# NIFTY 1m — Desk **OR · Swing · EMA cross** (what you see)

> Chart observation: on Desk (Fib·EMA·VWAP·BB), when **OR + Swing** meet and **EMA crosses**
> — price goes **up → BUY**, goes **below → SELL**. Measured on 1m.

Window **2026-05-26 → 2026-11-16** (120d). OOS **2026-08-20**. EMA20-cross events **4637**.
OR = first **15** 1m bars. Swing = fractal L=3 clusters. Exit metric = EMA34 trail **T15**.

## How the indication moves

```
1) OR high / OR low drawn after 09:15–09:29 (15×1m)
2) Swing cluster S/R nearby (often stacks on OR)
3) EMA20 crosses up through price → BUY bias
    EMA20 crosses down               → SELL bias
4) Best when OR hold/break + Swing agree with that cross
```

## 1) Lift on USER OR·Swing·EMA (winners vs losers)

| Mark | % Winners | % Losers | Lift pp |
|---|---:|---:|---:|
| `atr_hi` | 37.4 | 20.4 | 17.0 |
| `atr_12` | 19.7 | 10.2 | 9.5 |
| `desk_ge3` | 67.3 | 58.9 | 8.4 |
| `above_below_or` | 78.9 | 73.9 | 5.0 |
| `or_break_swing` | 12.2 | 7.3 | 4.9 |
| `or_break_dn` | 7.5 | 3.5 | 4.0 |
| `held` | 34.7 | 31.5 | 3.2 |
| `htf_with` | 76.9 | 73.9 | 3.0 |
| `vwap_x` | 11.6 | 9.2 | 2.3 |
| `or_break_up` | 4.8 | 3.8 | 0.9 |
| `streak6` | 1.4 | 0.6 | 0.7 |
| `or_hold_sup` | 6.1 | 6.7 | -0.6 |
| `bb_x` | 63.9 | 65.0 | -1.0 |
| `streak4` | 2.7 | 5.7 | -3.0 |
| `or_hold_res` | 4.1 | 8.6 | -4.5 |
| `tight_or_swing` | 9.5 | 15.3 | -5.8 |
| `swing_hold` | 87.1 | 95.2 | -8.1 |

## 2) Gates (1/day · T15%)

| Gate | Verdict | n | T15% | Train | OOS | path% | avg MFE | avg pts |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `Above/Below OR + held + HTF + ATR≥10` | **WEAK** | 30 | **56.67** | 54.55 | 57.89 | 60.0 | 39.53 | 2.97 |
| `BREAK: OR break·Swing·EMA` | **WEAK** | 27 | **48.15** | 47.06 | 50.0 | 74.07 | 32.51 | 3.1 |
| `USER + held + HTF + ATR≥10` | **WEAK** | 19 | **47.37** | 33.33 | 53.85 | 57.89 | 37.68 | 0.09 |
| `USER + desk≥3` | **WEAK** | 95 | **45.26** | 36.96 | 53.06 | 67.37 | 27.15 | 1.87 |
| `OR break + EMA` | **WEAK** | 51 | **41.18** | 38.46 | 44.0 | 62.75 | 32.14 | 1.74 |
| `USER: OR·Swing·EMA` | **WEAK** | 110 | **40.0** | 37.04 | 42.86 | 67.27 | 30.25 | 2.12 |
| `USER + VWAP cross same` | **WEAK** | 30 | **40.0** | 27.78 | 58.33 | 60.0 | 33.47 | 1.4 |
| `USER + BB mid cross same` | **WEAK** | 99 | **38.38** | 30.0 | 46.94 | 70.71 | 29.44 | 1.15 |
| `USER + held` | **WEAK** | 80 | **37.5** | 30.0 | 45.0 | 61.25 | 25.38 | 0.27 |
| `USER + held + HTF` | **WEAK** | 72 | **37.5** | 32.35 | 42.11 | 61.11 | 25.33 | 0.43 |
| `Above/Below OR + EMA` | **WEAK** | 108 | **37.04** | 30.91 | 43.4 | 62.96 | 26.91 | -1.01 |
| `Swing hold + EMA` | **WEAK** | 119 | **34.45** | 30.0 | 38.98 | 67.23 | 28.57 | 1.63 |
| `EMA20 cross SELL` | **WEAK** | 119 | **32.77** | 25.0 | 40.68 | 67.23 | 31.48 | 1.31 |
| `Swing near + EMA` | **WEAK** | 111 | **32.43** | 34.55 | 30.36 | 57.66 | 23.36 | 1.35 |
| `EMA20 cross BUY` | **WEAK** | 119 | **31.93** | 26.67 | 37.29 | 59.66 | 30.69 | -0.83 |
| `OR mid cross + EMA` | **WEAK** | 51 | **29.41** | 29.17 | 29.63 | 56.86 | 31.64 | 1.09 |
| `OR hold + EMA + VWAP x` | **THIN** | 14 | **28.57** | 20.0 | 50.0 | 64.29 | 38.57 | -3.41 |
| `OR↔Swing stacked + EMA` | **WEAK** | 95 | **27.37** | 14.0 | 42.22 | 58.95 | 26.42 | 0.39 |
| `Inside OR + EMA` | **WEAK** | 104 | **26.92** | 17.65 | 35.85 | 63.46 | 32.4 | 0.9 |
| `OR hold + EMA` | **WEAK** | 65 | **26.15** | 21.88 | 30.3 | 69.23 | 32.57 | 0.59 |
| `EMA20 cross (any)` | **WEAK** | 119 | **25.21** | 16.67 | 33.9 | 62.18 | 31.99 | 1.01 |
| `TIGHT: OR hold·Swing·EMA` | **WEAK** | 41 | **21.95** | 17.39 | 27.78 | 78.05 | 28.99 | -1.04 |
| `USER + streak≥4` | **WEAK** | 21 | **19.05** | 10.0 | 27.27 | 66.67 | 23.15 | -0.84 |

## 3) Best recipe from this pass

**`Above/Below OR + held + HTF + ATR≥10`** · **WEAK**
- 1/day T15 **56.67%** · TRAIN **54.55%** · OOS **57.89%** · n=30
- path(0.35×ATR) **60.0%** · avg MFE **39.53** · avg pts **2.97**

### Samples

| Day | HM | Side | Entry | streak | ATR | T15 | MFE |
|---|---|---|---:|---:|---:|---|---:|
| 2026-06-01 | 09:35 | **SELL** | **23585.0** | 1 | 17.31 | True | 48.0 |
| 2026-06-02 | 13:42 | **BUY** | **23509.95** | 1 | 11.99 | True | 36.85 |
| 2026-06-03 | 10:44 | **SELL** | **23227.15** | 1 | 10.04 | False | 32.35 |
| 2026-06-04 | 10:17 | **BUY** | **23432.6** | 1 | 10.38 | True | 17.5 |
| 2026-06-05 | 10:51 | **SELL** | **23381.7** | 1 | 15.81 | False | 3.85 |
| 2026-06-11 | 11:15 | **BUY** | **23186.2** | 1 | 10.35 | True | 71.1 |
| 2026-06-15 | 14:04 | **SELL** | **23895.75** | 1 | 10.55 | False | 13.15 |
| 2026-06-29 | 13:43 | **SELL** | **23939.35** | 1 | 10.9 | False | 13.05 |
| 2026-06-30 | 10:15 | **SELL** | **23885.95** | 2 | 11.32 | False | 14.65 |
| 2026-07-13 | 10:18 | **BUY** | **24113.3** | 1 | 11.42 | True | 44.1 |

## 4) Takeaway

- Raw EMA20 cross alone is **noisy** on 1m.
- Adding **OR + Swing** (your visual) improves direction clarity.
- Same quality stack as v3 (**held + HTF + ATR≥10**) is what pushes accuracy up.
- This is the Desk indication you notice — now measured, not guessed.

_Generated in 9.4s._
