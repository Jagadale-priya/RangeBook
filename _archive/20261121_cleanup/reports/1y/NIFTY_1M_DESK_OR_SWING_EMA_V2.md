# NIFTY 1m — Desk OR-line cross × Swing × EMA (v2)

> Trigger = **price crosses OR high/low** (the OR line).
> Require **Swing stacked on OR** + **EMA20 with side** (up=BUY / below=SELL).

Window **2026-05-26 → 2026-11-16** (120d). OOS **2026-08-20**. Candidates **4068**.

## Gates (1/day · T15)

| Gate | Verdict | n | T15% | Train | OOS | path% | avg MFE | avg pts |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `USER + VWAP with + HTF + ATR≥10` | **OK_70** | 16 | **75.0** | 66.67 | 80.0 | 68.75 | 46.66 | 5.8 |
| `USER + held + HTF + ATR≥10` | **OK_70** | 15 | **73.33** | 66.67 | 77.78 | 60.0 | 41.89 | 5.82 |
| `USER + held + HTF` | **WEAK** | 22 | **63.64** | 55.56 | 69.23 | 68.18 | 36.51 | 4.42 |
| `USER OR-cross BUY only` | **WEAK** | 16 | **62.5** | 55.56 | 71.43 | 75.0 | 31.41 | 5.53 |
| `OR cross + Swing + EMA with (USER)` | **WEAK** | 37 | **62.16** | 52.94 | 70.0 | 72.97 | 35.63 | 3.61 |
| `OR cross + Swing + EMA stack` | **WEAK** | 29 | **62.07** | 53.85 | 68.75 | 75.86 | 31.76 | 3.08 |
| `USER + held` | **WEAK** | 33 | **60.61** | 50.0 | 68.42 | 72.73 | 33.39 | 3.46 |
| `USER OR-cross SELL only` | **WEAK** | 22 | **59.09** | 50.0 | 64.29 | 72.73 | 37.35 | 1.92 |
| `Swing cross USER + held + HTF + ATR≥10` | **WEAK** | 17 | **58.82** | 60.0 | 58.33 | 52.94 | 44.88 | -2.08 |
| `OR cross + EMA with` | **WEAK** | 118 | **58.47** | 58.33 | 58.62 | 66.1 | 28.55 | -0.13 |
| `OR cross + Swing on OR` | **WEAK** | 40 | **57.5** | 45.0 | 70.0 | 72.5 | 35.37 | 3.15 |
| `OR cross (any)` | **WEAK** | 118 | **55.93** | 53.33 | 58.62 | 64.41 | 28.11 | -0.66 |
| `Swing cross near OR + EMA` | **WEAK** | 61 | **49.18** | 44.83 | 53.12 | 60.66 | 30.35 | 0.02 |
| `OR hold + Swing + EMA` | **WEAK** | 21 | **33.33** | 28.57 | 42.86 | 52.38 | 28.35 | -1.39 |

## Best

**`USER + VWAP with + HTF + ATR≥10`** · **OK_70**
- T15 **75.0%** · TRAIN 66.67% · OOS 80.0% · n=16
- path **68.75%** · MFE **46.66**

```
WATCH : OR high / OR low (after 09:30)
STACK : Swing cluster sitting on that OR line
EMA   : price already above EMA20 (BUY) / below (SELL)
ENTRY : close crosses OR line in that direction
QUALITY: held + HTF15 + ATR≥10 when aiming for T15 accuracy
EXIT  : EMA34 trail · T15
```

| Day | HM | Side | Entry | mode | ATR | T15 | MFE |
|---|---|---|---:|---|---:|---|---:|
| 2026-06-05 | 11:44 | **SELL** | **23422.8** | or_cross_dn | 10.88 | False | 25.85 |
| 2026-06-30 | 10:20 | **SELL** | **23886.05** | or_cross_dn | 10.38 | False | 14.75 |
| 2026-07-06 | 09:30 | **BUY** | **24360.45** | or_cross_up | 10.53 | True | 33.95 |
| 2026-07-08 | 09:30 | **SELL** | **24224.55** | or_cross_dn | 13.4 | True | 17.35 |
| 2026-07-15 | 13:06 | **SELL** | **24061.65** | or_cross_dn | 25.04 | True | 20.25 |
| 2026-07-22 | 09:31 | **SELL** | **24031.65** | or_cross_dn | 13.14 | True | 22.95 |
| 2026-08-31 | 09:42 | **SELL** | **24033.0** | or_cross_dn | 10.03 | True | 23.2 |
| 2026-09-16 | 09:37 | **SELL** | **23170.2** | or_cross_dn | 18.39 | True | 54.1 |

## vs what you see

- The **visual** (OR + Swing + EMA direction) is real and common on 1m Desk.
- Short bounce (0.35×ATR path) often looks right — that is why it *feels* accurate.
- For **Oracle T15** (EMA34 trail +15), raw visual alone is not enough; need held/HTF/ATR.

_Generated in 9.1s._
