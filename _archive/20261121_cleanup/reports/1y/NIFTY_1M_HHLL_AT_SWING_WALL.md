# NIFTY 1m — HHLL confirm **at swing / OR wall**

> Entry = HL (BUY) / LH (SELL) only when the pivot or price sits on
> **OR15/OR30 · swing cluster · PDH/PDL · 15m L3**. Score = EMA34 trail T15.

Window **2024-11-08→2026-11-16** (500d). SHIP = n≥25 · T15≥70 · train/oos≥65 · fold_min≥65.
SHIP **0** · SOFT **1**

| Gate | Ship | n | T15% | Train | OOS | fold_min | fold_avg |
|---|---|---:|---:|---:|---:|---:|---:|
| `wall + held + htf + atr12 + streak4` | **SOFT** | 20 | **75.0** | 66.67 | 78.57 | 75.0 | 81.25 |
| `role wall + held + htf + atr12 + streak4` | **HOLD** | 14 | **78.57** | 66.67 | 81.82 | 87.5 | 87.5 |
| `wall + desk3 + htf + atr14 + streak4` | **HOLD** | 18 | **72.22** | 60.0 | 76.92 | 77.78 | 77.78 |
| `wall + htf + atr12 + streak4 + ctrl` | **HOLD** | 21 | **61.9** | 57.14 | 64.29 | 66.67 | 66.67 |
| `wall + htf + atr14 + streak4` | **HOLD** | 21 | **71.43** | 62.5 | 76.92 | 60.0 | 68.89 |
| `wall + htf + atr12 + streak4` | **HOLD** | 27 | **66.67** | 60.0 | 70.59 | 50.0 | 65.91 |
| `wall + htf + atr14 + streak4 + am` | **HOLD** | 14 | **64.29** | 57.14 | 71.43 | 50.0 | 55.0 |
| `role wall + htf + atr14 + streak4 + am` | **HOLD** | 13 | **61.54** | 57.14 | 66.67 | 50.0 | 55.0 |
| `OR wall + SHIP stack` | **HOLD** | 7 | **57.14** | 50.0 | 60.0 | 50.0 | 50.0 |
| `wall + htf` | **HOLD** | 367 | **53.13** | 55.8 | 50.54 | 43.42 | 53.43 |
| `wall + htf + atr12 + streak4 + am` | **HOLD** | 19 | **57.89** | 55.56 | 60.0 | 40.0 | 45.0 |
| `wall + SHIP stack` | **HOLD** | 11 | **54.55** | 50.0 | 57.14 | 40.0 | 40.0 |
| `role wall + SHIP stack` | **HOLD** | 10 | **50.0** | 50.0 | 50.0 | 40.0 | 40.0 |
| `HHLL raw (no wall)` | **HOLD** | 499 | **37.47** | 38.0 | 36.95 | 34.0 | 37.47 |
| `at ANY wall` | **HOLD** | 496 | **36.49** | 36.69 | 36.29 | 29.29 | 36.48 |
| `at OR wall` | **HOLD** | 402 | **38.06** | 39.39 | 36.76 | 28.24 | 38.23 |
| `at swing/L15 wall` | **HOLD** | 493 | **35.29** | 32.39 | 38.21 | 27.55 | 35.27 |
| `role-matched wall` | **HOLD** | 489 | **31.9** | 32.92 | 30.89 | 25.77 | 31.89 |
| `at PDH/PDL` | **HOLD** | 208 | **31.73** | 32.04 | 31.43 | 18.92 | 31.39 |
| `OR+swing + htf + atr12 + streak4` | **HOLD** | 5 | **60.0** | 33.33 | 100.0 | None | None |
| `swing wall + SHIP stack` | **HOLD** | 6 | **33.33** | 33.33 | 33.33 | None | None |
| `OR+swing + SHIP stack` | **HOLD** | 2 | **0.0** | 0.0 | 0.0 | None | None |

## Best

**`wall + held + htf + atr12 + streak4`** · **SOFT**
- T15 **75.0%** · fold_min **75.0** · n=20
- train 66.67% · oos 78.57%

### Folds

| Fold | From | To | n | T15 |
|---|---|---|---:|---:|
| 1 | 2024-11-08 | 2025-04-03 | 3 | 66.67 |
| 2 | 2025-04-04 | 2025-08-29 | 3 | 66.67 |
| 3 | 2025-09-01 | 2026-01-23 | 2 | 50.0 |
| 4 | 2026-01-27 | 2026-06-23 | 8 | 87.5 |
| 5 | 2026-06-24 | 2026-11-16 | 4 | 75.0 |

## Last 5 sessions — wall HHLL (1/day)

| Day | HM | Side | Tag | Entry | Walls | ATR | T15 | pts |
|---|---|---|---|---:|---|---:|---|---:|
| 2026-11-09 | 11:21 | **BUY** | HL | 24900.4 | `OR15_LO` | 15.75 | ✓ | 15.0 |
| 2026-11-11 | 10:01 | **BUY** | HL | 25369.35 | `SWING_CLUSTER` | 13.77 | ✗ | -25.25 |
| 2026-11-12 | 10:20 | **BUY** | HL | 25357.05 | `OR30_HI` | 12.66 | ✗ | -19.5 |
| 2026-11-13 | 09:58 | **BUY** | HL | 25207.95 | `L15_LO,OR15_HI,OR30_HI` | 12.13 | ✓ | 15.0 |
| 2026-11-16 | 09:47 | **BUY** | HL | 25309.9 | `L15_HI,OR15_HI,OR30_HI` | 12.35 | ✓ | 15.0 |

## Last 5 sessions — best gate `wall + held + htf + atr12 + streak4`

| Day | HM | Side | Tag | Entry | Walls | ATR | T15 | pts |
|---|---|---|---|---:|---|---:|---|---:|
| — | — | — | — | — | none fired | — | — | — |

## How to use

```
WALL  : OR15/30 · swing cluster · PDH/PDL · 15m L3 (within 0.45×ATR)
STRUCT: HL in up bias → BUY · LH in down bias → SELL
QUAL  : HTF with + ATR≥14 + streak≥4 + EMA with + AM  (or best gate above)
EXIT  : EMA34 trail · T15
```

_Generated in 118.4s._
