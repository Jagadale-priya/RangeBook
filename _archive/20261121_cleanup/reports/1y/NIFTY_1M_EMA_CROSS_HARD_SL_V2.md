# NIFTY 1m — EMA cross **hold → strong** · hard SL (v2)

> Your chart: light EMA crosses dark EMA → short hold → strong move.
> Desk: **EMA9 × EMA20** (primary) · also test **EMA20 × EMA50**.

**Accurate @ SL** = never goes ≥ SL pts against, AND moves with us.
**pos_run** = consecutive candles in our color right after entry.

Window **2026-05-26→2026-11-16** (120d). OOS ≥ **2026-08-20**.

| Gate | Verd | n | Acc@10 | Acc@15 | Acc@20 | Acc@25 | Train15 | OOS15 | pos_run | MFE | MAE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `ema20x50 BUY + VWAP+HTF` | **WEAK** | 50 | 38.0 | **56.0** | 70.0 | 76.0 | 45.16 | 73.68 | **0.8** | 37.47 | 20.38 |
| `ema9x20 + ATR12+HTF+VWAP` | **WEAK** | 24 | 33.33 | **54.17** | 54.17 | 62.5 | 62.5 | 50.0 | **1.92** | 79.93 | 32.22 |
| `ema20x50 + HTF` | **WEAK** | 104 | 36.54 | **50.0** | 58.65 | 65.38 | 46.3 | 54.0 | **1.4** | 34.08 | 25.82 |
| `ema20x50 + e50+HTF` | **WEAK** | 104 | 36.54 | **50.0** | 58.65 | 65.38 | 46.3 | 54.0 | **1.4** | 34.08 | 25.82 |
| `ema20x50 + AM+VWAP+HTF` | **WEAK** | 58 | 31.03 | **48.28** | 55.17 | 63.79 | 48.39 | 48.15 | **1.21** | 37.71 | 26.79 |
| `ema20x50 + VWAP+HTF` | **WEAK** | 90 | 32.22 | **46.67** | 55.56 | 64.44 | 41.67 | 52.38 | **1.21** | 33.3 | 26.79 |
| `ema20x50 + both+HTF+VWAP` | **WEAK** | 90 | 32.22 | **46.67** | 55.56 | 64.44 | 41.67 | 52.38 | **1.21** | 33.3 | 26.79 |
| `ema20x50 + DI+VWAP+HTF` | **WEAK** | 88 | 32.95 | **45.45** | 53.41 | 63.64 | 40.43 | 51.22 | **1.19** | 34.05 | 27.57 |
| `ema9x20 BUY + VWAP+HTF` | **WEAK** | 62 | 32.26 | **45.16** | 46.77 | 64.52 | 48.48 | 41.38 | **0.95** | 36.8 | 24.12 |
| `ema20x50 + delay3-6 + HTF+VWAP` | **WEAK** | 72 | 29.17 | **44.44** | 48.61 | 58.33 | 43.9 | 45.16 | **1.46** | 35.56 | 29.23 |
| `ema20x50 visual` | **WEAK** | 115 | 27.83 | **42.61** | 46.09 | 57.39 | 44.07 | 41.07 | **1.14** | 30.22 | 29.07 |
| `ema20x50 + both_side` | **WEAK** | 115 | 27.83 | **42.61** | 46.09 | 57.39 | 44.07 | 41.07 | **1.14** | 30.22 | 29.07 |
| `ema20x50 + ATR12+HTF+VWAP` | **WEAK** | 19 | 42.11 | **42.11** | 47.37 | 47.37 | 25.0 | 54.55 | **2.16** | 59.86 | 41.82 |
| `ema9x20 + DI+VWAP+HTF` | **WEAK** | 110 | 30.91 | **41.82** | 46.36 | 57.27 | 44.44 | 39.29 | **1.52** | 36.16 | 28.04 |
| `ema9x20 + VWAP+HTF` | **WEAK** | 111 | 30.63 | **41.44** | 45.95 | 56.76 | 44.44 | 38.6 | **1.5** | 35.69 | 28.41 |
| `ema9x20 + both+HTF+VWAP` | **WEAK** | 111 | 30.63 | **41.44** | 45.95 | 56.76 | 44.44 | 38.6 | **1.52** | 35.56 | 28.43 |
| `ema9x20 + delay3-6 + HTF+VWAP` | **WEAK** | 99 | 27.27 | **40.4** | 46.46 | 56.57 | 45.83 | 35.29 | **1.61** | 31.98 | 29.92 |
| `ema9x20 visual` | **WEAK** | 119 | 28.57 | **39.5** | 47.9 | 57.14 | 35.0 | 44.07 | **1.45** | 35.88 | 30.02 |
| `ema9x20 + both_side` | **WEAK** | 119 | 28.57 | **39.5** | 47.9 | 57.14 | 35.0 | 44.07 | **1.45** | 35.88 | 30.02 |
| `ema9x20 + AM+VWAP+HTF` | **WEAK** | 89 | 28.09 | **39.33** | 42.7 | 52.81 | 44.19 | 34.78 | **1.51** | 37.25 | 30.42 |
| `ema9x20 + HTF` | **WEAK** | 115 | 29.57 | **39.13** | 43.48 | 54.78 | 44.64 | 33.9 | **1.5** | 35.02 | 29.53 |
| `ema20x50 SELL + VWAP+HTF` | **WEAK** | 47 | 27.66 | **38.3** | 42.55 | 53.19 | 40.91 | 36.0 | **1.74** | 30.88 | 32.76 |
| `ema9x20 + e50+HTF` | **WEAK** | 115 | 28.7 | **38.26** | 42.61 | 53.91 | 42.86 | 33.9 | **1.5** | 34.49 | 30.11 |
| `ema9x20 SELL + VWAP+HTF` | **WEAK** | 71 | 29.58 | **38.03** | 43.66 | 47.89 | 42.86 | 33.33 | **2.03** | 35.09 | 31.47 |
| `ema9x20 + strong+broke+HTF` | **THIN** | 0 | None | **None** | None | None | None | None | **None** | None | None |
| `ema20x50 + strong+broke+HTF` | **THIN** | 0 | None | **None** | None | None | None | None | **None** | None | None |

## Best

**`ema20x50 BUY + VWAP+HTF`** · **WEAK**
- Acc@15 **56.0%** · Acc@20 **70.0%** · Acc@25 **76.0%**
- avg **0.8** positive candles in direction after entry
- n=50 · MFE 37.47 · MAE 20.38

## Last 5 sessions — best gate

| Day | Cross→Entry | Side | Delay | Acc15 | Acc20 | MAE | MFE | pos_run |
|---|---|---|---:|---|---|---:|---:|---:|
| 2026-11-16 | 11:57→12:04 | **BUY** @ 25252.6 | 7 | ✓ | ✓ | 7.45 | 48.85 | **0** |

## Last 5 — raw EMA9×20 visual (1/day)

| Day | Cross→Entry | Side | Delay | Acc15 | Acc20 | MAE | MFE | pos_run | HTF | VWAP |
|---|---|---|---:|---|---|---:|---:|---:|---|---|
| 2026-11-09 | 10:18→10:21 | **BUY** @ 24950.1 | 3 | ✗ | ✗ | 111.35 | 7.95 | **1** | Y | Y |
| 2026-11-11 | 09:57→10:02 | **SELL** @ 25356.15 | 5 | ✗ | ✓ | 18.7 | 28.2 | **0** | N | Y |
| 2026-11-12 | 10:11→10:16 | **SELL** @ 25336.6 | 5 | ✗ | ✗ | 24.35 | 16.5 | **1** | N | N |
| 2026-11-13 | 09:37→09:41 | **BUY** @ 25177.65 | 4 | ✓ | ✓ | 11.45 | 51.75 | **0** | N | Y |
| 2026-11-16 | 11:01→11:04 | **BUY** @ 25242.5 | 3 | ✗ | ✗ | 35.35 | 6.75 | **1** | Y | N |

## Read

- If Acc@15 stays <65% even with HTF/VWAP → hard 15pt SL is too tight for this 1m cross alone.
- Acc@20 / Acc@25 show whether the **same signal** works with a slightly wider hard stop.
- High **pos_run** with low Acc@15 = move starts right but wick against tags the 15pt stop.

_Generated in 68.9s._
