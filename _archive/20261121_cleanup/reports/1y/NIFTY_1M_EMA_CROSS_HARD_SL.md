# NIFTY 1m — **EMA9×EMA20 cross** · hard SL accuracy (no T15)

> Desk indications: **light blue = EMA9**, **dark blue = EMA20**.
> Cross below → SELL setup · cross above → BUY setup.
> Optional: short **hold**, then break / strong candle (your chart pattern).

**Accurate** = after entry, never goes **≥15 (or 20) pts against**, AND moves in our direction.
**Clean** = never hits hard SL AND MFE ≥ hard SL the other way.
**pos_run** = consecutive same-color candles in our direction right after entry.

Window **2026-05-26→2026-11-16** (120d). OOS ≥ **2026-08-20**.

| Gate | Verd | n | Acc@15 | Acc@20 | Clean@15 | Train | OOS | avg MFE | avg MAE | pos_run | pos_tot |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `B + ATR≥12 + HTF + VWAP` | **WEAK** | 24 | **54.17** | 54.17 | 54.17 | 62.5 | 50.0 | 78.9 | 30.21 | 2.21 | 15.79 |
| `B BUY only + HTF + VWAP` | **WEAK** | 64 | **48.44** | 54.69 | 46.88 | 52.94 | 43.33 | 37.92 | 23.08 | 1.06 | 13.5 |
| `B + DI + VWAP + HTF` | **WEAK** | 112 | **42.86** | 49.11 | 41.96 | 48.21 | 37.5 | 35.4 | 28.3 | 1.56 | 14.24 |
| `B + delay 3-8 + strong + HTF` | **WEAK** | 117 | **42.74** | 51.28 | 41.03 | 48.28 | 37.29 | 34.42 | 28.38 | 1.43 | 13.66 |
| `B + VWAP + HTF` | **WEAK** | 113 | **42.48** | 48.67 | 41.59 | 48.21 | 36.84 | 35.13 | 28.58 | 1.58 | 14.16 |
| `B + AM + HTF + VWAP` | **WEAK** | 92 | **41.3** | 47.83 | 40.22 | 51.11 | 31.91 | 36.68 | 29.96 | 1.54 | 13.62 |
| `B + delay≤6 + HTF + VWAP` | **WEAK** | 107 | **41.12** | 47.66 | 39.25 | 41.51 | 40.74 | 34.0 | 28.87 | 1.66 | 13.79 |
| `A + HTF + VWAP` | **WEAK** | 116 | **40.52** | 47.41 | 37.93 | 46.55 | 34.48 | 37.14 | 29.63 | 1.18 | 14.0 |
| `B + HTF with` | **WEAK** | 117 | **40.17** | 47.86 | 39.32 | 48.28 | 32.2 | 34.46 | 28.91 | 1.49 | 13.55 |
| `B + EMA50 with + HTF` | **WEAK** | 117 | **39.32** | 47.01 | 38.46 | 46.55 | 32.2 | 33.71 | 29.43 | 1.48 | 13.32 |
| `B + streak≥3` | **WEAK** | 104 | **38.46** | 47.12 | 37.5 | 34.55 | 42.86 | 35.24 | 28.41 | 1.39 | 13.38 |
| `C + streak≥3 + HTF + VWAP` | **WEAK** | 104 | **38.46** | 50.0 | 35.58 | 50.0 | 25.0 | 37.13 | 27.44 | 1.09 | 13.3 |
| `B SELL only + HTF + VWAP` | **WEAK** | 73 | **38.36** | 42.47 | 36.99 | 45.95 | 30.56 | 34.18 | 31.97 | 2.05 | 14.85 |
| `B + VWAP with` | **WEAK** | 118 | **38.14** | 45.76 | 36.44 | 38.98 | 37.29 | 36.09 | 29.86 | 1.37 | 13.25 |
| `A + price vs20 + HTF` | **WEAK** | 118 | **37.29** | 46.61 | 36.44 | 42.37 | 32.2 | 35.78 | 31.24 | 0.99 | 13.14 |
| `B + ATR≥10 + HTF` | **WEAK** | 44 | **36.36** | 45.45 | 36.36 | 35.71 | 36.67 | 48.83 | 39.44 | 1.43 | 11.11 |
| `B hold_break (delay)` | **WEAK** | 119 | **36.13** | 44.54 | 34.45 | 36.67 | 35.59 | 36.39 | 29.97 | 1.39 | 13.03 |
| `B + price vs EMA20` | **WEAK** | 119 | **36.13** | 44.54 | 34.45 | 36.67 | 35.59 | 36.39 | 29.97 | 1.39 | 13.03 |
| `B + strong candle` | **WEAK** | 119 | **36.13** | 44.54 | 34.45 | 36.67 | 35.59 | 36.39 | 29.97 | 1.39 | 13.03 |
| `C + HTF + VWAP` | **WEAK** | 116 | **33.62** | 45.69 | 31.03 | 46.55 | 20.69 | 35.89 | 32.09 | 1.03 | 11.78 |
| `A cross_bar` | **WEAK** | 119 | **29.41** | 34.45 | 27.73 | 28.33 | 30.51 | 37.47 | 35.73 | 0.93 | 10.17 |
| `C impulse after cross` | **WEAK** | 119 | **29.41** | 39.5 | 28.57 | 25.0 | 33.9 | 39.69 | 32.73 | 1.03 | 10.63 |
| `C + strong + HTF` | **WEAK** | 117 | **29.06** | 43.59 | 27.35 | 32.76 | 25.42 | 30.46 | 30.77 | 1.16 | 10.99 |
| `C + ATR≥10 + HTF + VWAP` | **WEAK** | 48 | **20.83** | 35.42 | 20.83 | 22.73 | 19.23 | 50.38 | 42.18 | 1.12 | 8.29 |

## Best

**`B + ATR≥12 + HTF + VWAP`** · **WEAK**
- Acc@15 **54.17%** · Acc@20 **54.17%** · Clean@15 **54.17%**
- n=24 · train 62.5% · oos 50.0%
- avg MFE 78.9 · avg MAE 30.21 · avg pos_run **2.21** candles

```
SIGNAL : EMA9 crosses EMA20 (light × dark)
SELL   : 9 crosses below 20 → hold under 20 → break / strong red
BUY    : 9 crosses above 20 → hold over 20 → break / strong green
ACCURATE: MAE < 15–20 pts against, and price moves with us
```

## Last 5 sessions — hold_break (1/day)

| Day | Cross | Entry | Side | Delay | Acc@15 | Acc@20 | MAE | MFE | pos_run | pos_tot |
|---|---|---|---|---:|---|---|---:|---:|---:|---:|
| 2026-11-09 | 09:55 | 10:02 **SELL** @ 24924.75 | SELL | 7 | ✗ | ✗ | 33.9 | 86.0 | 0 | 3 |
| 2026-11-11 | 09:57 | 10:02 **SELL** @ 25356.15 | SELL | 5 | ✗ | ✓ | 19.25 | 28.2 | 0 | 9 |
| 2026-11-12 | 10:11 | 10:14 **SELL** @ 25336.8 | SELL | 3 | ✗ | ✗ | 24.15 | 16.7 | 0 | 2 |
| 2026-11-13 | 09:37 | 09:41 **BUY** @ 25177.65 | BUY | 4 | ✓ | ✓ | 11.45 | 51.75 | 0 | 24 |
| 2026-11-16 | 11:01 | 11:04 **BUY** @ 25242.5 | BUY | 3 | ✗ | ✗ | 35.55 | 6.75 | 1 | 1 |

## Last 5 — best gate `B + ATR≥12 + HTF + VWAP`

| Day | Cross | Entry | Side | Delay | Acc@15 | MAE | MFE | pos_run |
|---|---|---|---|---:|---|---:|---:|---:|
| 2026-11-09 | 10:34 | 10:38 **SELL** @ 24900.9 | SELL | 4 | ✗ | 31.3 | 62.15 | 0 |

_Generated in 72.2s._
