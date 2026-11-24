# NIFTY 1m — Oracle/Desk streak **v2** (enter when streak hits 4/5/6)

> Entry = close of the bar where same-color streak **first reaches** 4, 5, or 6.
> Side = streak direction. Desk = Fib·EMA·VWAP·BB. Optional: textbook event inside streak.
> Metric = EMA34 trail **T15** win (scalper Oracle exit).

Window **2026-05-26 → 2026-11-16** (120d). OOS **2026-08-20**. Candidates **4585**.

| Gate | Verdict | n | T15% | Train | OOS | all n/prec | avg pts |
|---|---|---:|---:|---:|---:|---|---:|
| `hit6+desk≥3+held` | **WEAK** | 114 | **58.77** | 56.9 | 60.71 | 450/51.56 | 1.1 |
| `hit6+oracle_evt+desk≥3+held` | **WEAK** | 114 | **58.77** | 56.9 | 60.71 | 450/51.56 | 1.1 |
| `hit6+vwap+ema+ema50` | **WEAK** | 113 | **58.41** | 53.45 | 63.64 | 454/51.1 | 1.02 |
| `hit6+FULL` | **WEAK** | 112 | **58.04** | 53.45 | 62.96 | 422/52.61 | 0.9 |
| `hit6+vwap+ema` | **WEAK** | 113 | **57.52** | 55.17 | 60.0 | 463/50.54 | 0.85 |
| `hit6+vwap+ema+held` | **WEAK** | 112 | **57.14** | 55.17 | 59.26 | 431/51.97 | 0.73 |
| `hit6+desk≥2` | **WEAK** | 119 | **55.46** | 53.33 | 57.63 | 706/43.34 | 1.47 |
| `hit6+oracle_evt+desk≥2` | **WEAK** | 119 | **55.46** | 53.33 | 57.63 | 706/43.34 | 1.47 |
| `hit6+desk≥3` | **WEAK** | 118 | **55.08** | 55.0 | 55.17 | 634/46.53 | 0.85 |
| `hit4+desk≥3` | **WEAK** | 119 | **52.94** | 38.33 | 67.8 | 1780/46.12 | -1.74 |
| `hit4+vwap+ema` | **WEAK** | 119 | **52.94** | 38.33 | 67.8 | 1272/50.86 | -1.91 |
| `hit6` | **WEAK** | 119 | **52.94** | 51.67 | 54.24 | 768/40.62 | 1.63 |
| `hit4+vwap+ema+ema50` | **WEAK** | 119 | **52.1** | 36.67 | 67.8 | 1257/50.91 | -2.18 |
| `any4-6+desk≥3+held` | **WEAK** | 119 | **52.1** | 43.33 | 61.02 | 2356/50.38 | -2.66 |
| `any4-6+oracle+desk≥3+held` | **WEAK** | 119 | **52.1** | 43.33 | 61.02 | 2356/50.38 | -2.66 |
| `any4-6+vwap+ema+held` | **WEAK** | 119 | **52.1** | 43.33 | 61.02 | 2253/51.13 | -2.69 |
| `hit4+desk≥2` | **WEAK** | 119 | **50.42** | 35.0 | 66.1 | 2070/42.32 | -0.42 |
| `hit4+oracle_evt+desk≥2` | **WEAK** | 119 | **50.42** | 35.0 | 66.1 | 2070/42.32 | -0.42 |
| `hit4+vwap+ema+held` | **WEAK** | 119 | **48.74** | 38.33 | 59.32 | 1145/51.7 | -3.21 |
| `hit4+desk≥3+held` | **WEAK** | 119 | **48.74** | 38.33 | 59.32 | 1202/50.75 | -3.26 |
| `hit4+oracle_evt+desk≥3+held` | **WEAK** | 119 | **48.74** | 38.33 | 59.32 | 1202/50.75 | -3.26 |
| `hit4+FULL` | **WEAK** | 119 | **48.74** | 38.33 | 59.32 | 1136/51.76 | -3.23 |
| `hit5+desk≥3+held` | **WEAK** | 117 | **48.72** | 46.67 | 50.88 | 704/49.01 | -2.8 |
| `hit5+oracle_evt+desk≥3+held` | **WEAK** | 117 | **48.72** | 46.67 | 50.88 | 704/49.01 | -2.8 |
| `hit5+vwap+ema+ema50` | **WEAK** | 118 | **48.31** | 45.0 | 51.72 | 728/49.18 | -2.97 |
| `hit5+vwap+ema+held` | **WEAK** | 117 | **47.86** | 45.0 | 50.88 | 677/49.63 | -2.86 |
| `hit5+FULL` | **WEAK** | 116 | **47.41** | 44.07 | 50.88 | 669/49.63 | -3.23 |
| `hit5+desk≥3` | **WEAK** | 119 | **47.06** | 41.67 | 52.54 | 1037/45.13 | -2.58 |
| `hit5+vwap+ema` | **WEAK** | 118 | **46.61** | 43.33 | 50.0 | 740/48.92 | -2.98 |
| `hit4` | **WEAK** | 120 | **45.83** | 33.33 | 58.33 | 2469/36.53 | -0.38 |
| `hit5+desk≥2` | **WEAK** | 119 | **42.02** | 33.33 | 50.85 | 1168/42.12 | -2.06 |
| `hit5+oracle_evt+desk≥2` | **WEAK** | 119 | **42.02** | 33.33 | 50.85 | 1168/42.12 | -2.06 |
| `hit5` | **WEAK** | 120 | **39.17** | 31.67 | 46.67 | 1348/37.91 | -1.23 |

## Best accurate entry

**`hit6+desk≥3+held`** · WEAK
- 1/day T15 **58.77%** · TRAIN 56.9% · OOS **60.71%** · n=114

```
WAIT  : 4–6 consecutive same-color 1m candles
ENTER : close of the bar that completes the count
FILTER: Desk confluence (VWAP + EMA stack ± held / hits≥3)
SIDE  : streak direction (BUY green / SELL red)
EXIT  : EMA34 trail · T15 (Oracle T15 geometry)
```

| Day | HM | Side | Entry | streak | desk | T15 |
|---|---|---|---:|---:|---:|---|
| 2026-05-26 | 12:13 | **SELL** | **24022.2** | 6 | 4 | False |
| 2026-05-27 | 12:29 | **SELL** | **23906.3** | 6 | 4 | False |
| 2026-05-29 | 10:07 | **BUY** | **23950.9** | 6 | 4 | False |
| 2026-06-02 | 09:53 | **BUY** | **23307.9** | 6 | 4 | True |
| 2026-06-03 | 12:31 | **BUY** | **23275.1** | 6 | 4 | True |
| 2026-06-04 | 09:49 | **BUY** | **23388.35** | 6 | 4 | True |
| 2026-06-05 | 10:39 | **SELL** | **23364.15** | 6 | 4 | True |
| 2026-06-08 | 09:56 | **BUY** | **23189.8** | 6 | 3 | False |
| 2026-06-09 | 11:24 | **SELL** | **23113.1** | 6 | 4 | False |
| 2026-06-10 | 12:42 | **SELL** | **23355.65** | 6 | 4 | True |

## vs v1

- v1 (pattern already had streak): best ~**63%** T15
- v2 (enter at streak hit): best **58.77%**

_Generated in 69.0s._
