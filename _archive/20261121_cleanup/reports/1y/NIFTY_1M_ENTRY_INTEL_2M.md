# NIFTY 1m — Entry Intelligence (last 2 months)

Window: **2026-09-15 → 2026-11-16** · session 09:30–14:30 · textbook events scored by **favour-first** (not SL/T).

## Accuracy definitions (entry only — no SL/T)

- **Fav1st**: +8 favour before -5 adverse (strict timing).
- **Edge%**: MFE≥12 and MFE>MAE (path eventually favour-dominant).
- **Dom%**: MFE≥12 and MFE≥1.5×MAE (strong dominance — primary rank).
- **Fwd10%**: close +ve after 10 bars and MFE≥8.

## Market structure map (last ~1 month)

Liquidity proxies = **equal highs/lows** (stop pools) + session extremes. Volume unavailable on index CSV → structure used.

### Most-visited resistance liquidity (equal highs, rounded 5)

- **22770** · touches/weight 17
- **22940** · touches/weight 15
- **24950** · touches/weight 14
- **25135** · touches/weight 14
- **22720** · touches/weight 13
- **22520** · touches/weight 12
- **23910** · touches/weight 12
- **25130** · touches/weight 12

### Most-visited support liquidity (equal lows, rounded 5)

- **22940** · touches/weight 20
- **23120** · touches/weight 17
- **22710** · touches/weight 16
- **22840** · touches/weight 15
- **22665** · touches/weight 14
- **22925** · touches/weight 11
- **23330** · touches/weight 11
- **25275** · touches/weight 11

### Latest session levels (last 5 mapped days)

| Day | Open | High | Low | Close | Range |
|---|---:|---:|---:|---:|---:|
| 2026-11-09 | 25076.4 | 25084.05 | 24838.75 | 25044.65 | 245.3 |
| 2026-11-11 | 25337.8 | 25424.35 | 25095.35 | 25255.05 | 329.0 |
| 2026-11-12 | 25213.5 | 25384.8 | 25142.95 | 25299.35 | 241.85 |
| 2026-11-13 | 25209.85 | 25246.35 | 25054.4 | 25144.3 | 191.95 |
| 2026-11-16 | 25206.15 | 25337.6 | 25172.1 | 25291.1 | 165.5 |

## Regime mix (all textbook · 2m)

```
{'trend': 3279, 'failed_break_risk': 613, 'mixed': 3423, 'break_attempt': 898, 'hold_break': 87, 'flip': 409}
```

### HELD accuracy by regime (favour-first)

| Gate | n | Dom% | Edge% | Fav1st% | Fwd10% | MFE≥12% | avg MFE | avg MAE | edge |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `HELD · trend` | 1673 | **46.5** | 54.69 | 45.07 | 51.29 | 82.13 | 44.71 | 40.02 | 4.69 |
| `HELD · hold_break` | 51 | **58.82** | 66.67 | 60.78 | 49.02 | 84.31 | 50.63 | 33.56 | 17.08 |
| `HELD · flip` | 20 | **45.0** | 60.0 | 40.0 | 70.0 | 85.0 | 52.73 | 30.59 | 22.14 |
| `HELD · break_attempt` | 1 | **100.0** | 100.0 | 100.0 | 100.0 | 100.0 | 100.4 | 2.95 | 97.45 |
| `HELD · failed_break_risk` | 510 | **46.67** | 59.41 | 45.88 | 56.08 | 84.71 | 46.25 | 39.75 | 6.5 |
| `HELD · mixed` | 303 | **44.55** | 53.14 | 42.57 | 53.47 | 79.21 | 43.21 | 43.64 | -0.43 |

## Gate sweep — last 2 months (entry accuracy)

| Gate | n | Dom% | Edge% | Fav1st% | Fwd10% | MFE≥12% | avg MFE | avg MAE | edge |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `SETUP: trend + control + sweep + room≥ATR + !into_extreme` | 9 | **77.78** | 88.89 | 44.44 | 55.56 | 88.89 | 84.97 | 18.84 | 66.13 |
| `HELD + hold_break` | 51 | **58.82** | 66.67 | 60.78 | 49.02 | 84.31 | 50.63 | 33.56 | 17.08 |
| `SETUP: hold_break + control + room_against≤ATR` | 51 | **58.82** | 66.67 | 60.78 | 49.02 | 84.31 | 50.63 | 33.56 | 17.08 |
| `INTEL: HELD+control+sweep+room≥ATR+!into_extreme` | 54 | **55.56** | 68.52 | 48.15 | 50.0 | 85.19 | 53.85 | 33.85 | 20.0 |
| `SETUP: hold_break + sweep + !into_extreme` | 32 | **53.12** | 62.5 | 56.25 | 43.75 | 81.25 | 42.01 | 38.89 | 3.12 |
| `INTEL4: HELD+control+sweep+(hold_break|flip|trend)` | 180 | **50.0** | 58.89 | 48.89 | 53.33 | 83.89 | 47.58 | 32.22 | 15.36 |
| `HELD + control + sweep` | 260 | **49.23** | 58.08 | 49.62 | 56.15 | 84.23 | 46.96 | 36.07 | 10.89 |
| `SETUP: hold_break|flip + control + sweep + !into_extreme` | 51 | **49.02** | 60.78 | 50.98 | 52.94 | 82.35 | 46.37 | 36.18 | 10.19 |
| `HELD + sweep_with` | 305 | **48.52** | 57.38 | 50.49 | 55.41 | 83.93 | 46.01 | 35.93 | 10.08 |
| `HELD + room_fav≥ATR` | 928 | **48.17** | 57.97 | 44.61 | 51.19 | 84.16 | 46.63 | 41.48 | 5.15 |
| `HELD + room_fav≥1.5ATR` | 692 | **48.12** | 57.95 | 46.24 | 51.45 | 84.54 | 47.04 | 41.35 | 5.69 |
| `INTEL3: HELD+(hold_break|flip|trend)+control` | 1313 | **47.91** | 55.98 | 47.6 | 51.94 | 82.86 | 45.89 | 39.37 | 6.51 |
| `INTEL2: HELD+control+!failed_break+room≥ATR` | 731 | **47.88** | 57.05 | 46.79 | 50.21 | 84.13 | 47.16 | 42.15 | 5.01 |
| `HELD + control_with` | 1874 | **47.23** | 55.82 | 47.6 | 52.88 | 82.71 | 46.04 | 40.32 | 5.72 |
| `HELD` | 2558 | **46.56** | 55.75 | 45.23 | 52.62 | 82.37 | 45.04 | 40.18 | 4.87 |
| `HELD + !compress` | 2558 | **46.56** | 55.75 | 45.23 | 52.62 | 82.37 | 45.04 | 40.18 | 4.87 |
| `HELD + !into_sess_extreme` | 1508 | **46.55** | 54.64 | 45.36 | 51.72 | 81.17 | 43.93 | 39.87 | 4.07 |
| `HELD + !failed_break_risk` | 2048 | **46.53** | 54.83 | 45.07 | 51.76 | 81.79 | 44.74 | 40.28 | 4.46 |
| `HELD + di_strong + control` | 1651 | **46.52** | 55.3 | 47.55 | 52.15 | 82.56 | 45.81 | 40.5 | 5.3 |
| `HELD + trend` | 1673 | **46.5** | 54.69 | 45.07 | 51.29 | 82.13 | 44.71 | 40.02 | 4.69 |
| `HELD + liq_fav within 25` | 654 | **46.48** | 53.67 | 45.41 | 56.12 | 79.2 | 43.48 | 35.62 | 7.86 |
| `HELD + flip` | 20 | **45.0** | 60.0 | 40.0 | 70.0 | 85.0 | 52.73 | 30.59 | 22.14 |
| `ALL textbook sess` | 8709 | **43.84** | 51.64 | 42.69 | 49.73 | 78.62 | 43.63 | 41.26 | 2.36 |

## Gate sweep — last ~1 month

| Gate | n | Dom% | Edge% | Fav1st% | Fwd10% | MFE≥12% | avg MFE | avg MAE | edge |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `HELD + hold_break` | 27 | **62.96** | 70.37 | 70.37 | 51.85 | 92.59 | 61.79 | 35.9 | 25.89 |
| `SETUP: hold_break + control + room_against≤ATR` | 27 | **62.96** | 70.37 | 70.37 | 51.85 | 92.59 | 61.79 | 35.9 | 25.89 |
| `SETUP: hold_break + sweep + !into_extreme` | 13 | **61.54** | 69.23 | 69.23 | 46.15 | 92.31 | 54.88 | 46.2 | 8.67 |
| `SETUP: hold_break|flip + control + sweep + !into_extreme` | 22 | **50.0** | 59.09 | 50.0 | 45.45 | 90.91 | 49.61 | 46.2 | 3.41 |
| `HELD + control + sweep` | 126 | **47.62** | 57.14 | 49.21 | 55.56 | 87.3 | 49.09 | 43.23 | 5.85 |
| `INTEL3: HELD+(hold_break|flip|trend)+control` | 659 | **47.5** | 55.39 | 48.56 | 52.81 | 84.83 | 49.23 | 45.7 | 3.53 |
| `INTEL4: HELD+control+sweep+(hold_break|flip|trend)` | 87 | **47.13** | 58.62 | 52.87 | 51.72 | 88.51 | 49.8 | 37.94 | 11.86 |
| `HELD + sweep_with` | 147 | **46.94** | 57.14 | 49.66 | 55.78 | 86.39 | 48.47 | 42.58 | 5.89 |
| `HELD + !into_sess_extreme` | 746 | **46.51** | 54.29 | 45.58 | 51.47 | 82.44 | 47.53 | 46.89 | 0.64 |
| `HELD + trend` | 826 | **46.49** | 54.24 | 45.76 | 52.54 | 83.29 | 48.22 | 46.42 | 1.8 |
| `HELD + control_with` | 922 | **46.2** | 54.45 | 48.16 | 54.23 | 83.95 | 50.11 | 47.23 | 2.87 |
| `HELD + !failed_break_risk` | 989 | **45.8** | 53.89 | 45.8 | 52.17 | 82.81 | 48.37 | 47.38 | 0.98 |
| `HELD + di_strong + control` | 802 | **45.64** | 54.49 | 48.5 | 53.74 | 83.92 | 50.17 | 47.1 | 3.07 |
| `HELD` | 1235 | **45.51** | 54.82 | 45.99 | 53.85 | 83.4 | 49.62 | 47.15 | 2.47 |
| `HELD + !compress` | 1235 | **45.51** | 54.82 | 45.99 | 53.85 | 83.4 | 49.62 | 47.15 | 2.47 |
| `INTEL: HELD+control+sweep+room≥ATR+!into_extreme` | 22 | **45.45** | 59.09 | 50.0 | 36.36 | 86.36 | 47.19 | 47.7 | -0.51 |
| `HELD + room_fav≥ATR` | 467 | **45.18** | 54.82 | 45.4 | 50.75 | 84.15 | 48.31 | 49.57 | -1.26 |
| `INTEL2: HELD+control+!failed_break+room≥ATR` | 364 | **45.05** | 53.57 | 48.9 | 50.55 | 84.89 | 48.44 | 50.58 | -2.14 |
| `HELD + liq_fav within 25` | 270 | **44.81** | 54.44 | 45.19 | 61.11 | 78.89 | 53.6 | 43.29 | 10.31 |
| `ALL textbook sess` | 4349 | **43.23** | 51.21 | 43.78 | 50.49 | 80.52 | 48.62 | 47.05 | 1.57 |
| `HELD + room_fav≥1.5ATR` | 365 | **42.47** | 52.33 | 47.67 | 50.68 | 84.11 | 45.77 | 49.81 | -4.04 |
| `SETUP: trend + control + sweep + room≥ATR + !into_extreme` | 3 | **33.33** | 66.67 | 33.33 | 0.0 | 66.67 | 43.75 | 41.03 | 2.72 |
| `HELD + flip` | 9 | **33.33** | 44.44 | 22.22 | 44.44 | 88.89 | 42.0 | 46.2 | -4.2 |

## 1-call-per-day books

| Gate | n | Dom% | Edge% | Fav1st% | Fwd10% | MFE≥12% | avg MFE | avg MAE | edge |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `HELD 1cpd` | 42 | **47.62** | 57.14 | 57.14 | 59.52 | 90.48 | 59.3 | 50.35 | 8.95 |
| `INTEL4 1cpd (control+sweep+regime)` | 42 | **40.48** | 59.52 | 52.38 | 54.76 | 90.48 | 47.49 | 42.42 | 5.08 |

## Sample accurate INTEL entries

| Day | HM | Side | Pattern | Regime | Entry | room_fav | MFE | MAE | fwd10 |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| 2026-09-15 | 13:28 | SELL | bear_kicker | trend | 23289.75 | 1.25 | 94.45 | 3.0 | 20.75 |
| 2026-09-16 | 10:44 | BUY | three_outside_up | trend | 23248.5 | 0.5 | 30.25 | 29.15 | 5.8 |
| 2026-09-17 | 11:04 | SELL | bear_run3 | trend | 23238.4 | 1.4 | 28.1 | 82.1 | 14.35 |
| 2026-09-18 | 09:56 | BUY | bull_engulf | trend | 23326.75 | 5.95 | 11.65 | 32.75 | -12.6 |
| 2026-09-18 | 11:15 | SELL | shooting_star | flip | 23302.35 | 0.35 | 10.8 | 30.4 | 5.65 |
| 2026-09-18 | 11:16 | SELL | bear_run2 | flip | 23301.7 | 1.9 | 10.15 | 31.05 | 6.75 |
| 2026-09-18 | 14:02 | BUY | bull_engulf | trend | 23330.45 | 1.35 | 58.7 | 1.6 | 23.0 |
| 2026-09-18 | 14:06 | BUY | bull_run3 | trend | 23342.3 | 0.2 | 46.85 | 1.0 | 12.65 |
| 2026-09-21 | 11:32 | BUY | bull_run3 | trend | 23402.5 | 3.3 | 31.55 | 8.0 | -0.5 |
| 2026-09-21 | 13:21 | BUY | bull_run3 | hold_break | 23425.45 | 8.55 | 41.35 | 4.2 | 3.3 |
| 2026-09-22 | 10:49 | SELL | three_outside_dn | trend | 23376.75 | 8.55 | 19.65 | 27.25 | -11.8 |
| 2026-09-22 | 11:33 | SELL | bear_engulf | hold_break | 23382.35 | 13.55 | 40.85 | 2.3 | 13.9 |

## Sample failed INTEL entries (learn)

| Day | HM | Side | Pattern | Regime | Entry | into_extreme | MFE | MAE |
|---|---|---|---|---|---:|---|---:|---:|
| 2026-09-15 | 11:53 | SELL | bear_run2 | trend | 23319.95 | False | 7.25 | 33.95 |
| 2026-09-15 | 12:39 | SELL | bear_run3 | trend | 23322.55 | False | 59.55 | 14.7 |
| 2026-09-15 | 13:16 | SELL | bear_run3 | hold_break | 23285.05 | True | 78.45 | 15.45 |
| 2026-09-15 | 13:47 | SELL | shooting_star | trend | 23264.75 | False | 93.85 | 12.7 |
| 2026-09-15 | 13:48 | SELL | bear_run3 | trend | 23265.1 | False | 113.1 | 12.35 |
| 2026-09-17 | 11:11 | SELL | bear_run2 | hold_break | 23212.75 | False | 0.0 | 127.2 |
| 2026-09-17 | 13:31 | SELL | bear_run3 | trend | 23259.55 | False | 15.5 | 32.2 |
| 2026-09-17 | 14:00 | SELL | bear_run3 | trend | 23264.25 | False | 2.15 | 47.4 |

## Locked entry logic (proposed — no SL/T yet)

**Principle:** market is supreme — do **not** force a call. Fire only when a **setup forms**.

### Tier A — primary (best evidence last 1–2m)
**HELD + `hold_break`** (backed by nearby S/R ≤1×ATR, control bar, liquidity sweep with side)

| Window | n | Dom% | Edge% | Fav1st% | path edge |
|---|---:|---:|---:|---:|---:|
| 2m | 51 | **58.8** | **66.7** | **60.8** | **+17** |
| 1m | 27 | **63.0** | **70.4** | **70.4** | **+26** |

Only regime that clearly beats blind HELD (~46% Dom) with a real sample.

### Tier B — secondary (only if Tier A absent)
- `control + sweep` → Dom ~49–50%, better edge than raw HELD
- `hold_break|flip + control + sweep + !into_extreme`

### Skip always
- buying session highs / selling session lows (`failed_break_risk`)
- textbook alone (~44% Dom)
- compress / mixed with no control

### Dynamic router
1. Base: textbook · DI · hard34 · VWAP · 09:30–14:30  
2. Control: BUY = buyer bar; SELL = seller bar  
3. Structure: live S/R + equal-high/low liquidity (recompute — never hardcode)  
4. Prefer hold_break → else flip/control+sweep → else **wait**  
5. Multi-call OK (Scalper uses ~15m gap after prior exit — no 1/day hard stop)  


### Recent map
Last sessions lived roughly **25170–25340**. Liquidity magnets rotate daily — use pivots/equal H-L, not fixed levels.

Elapsed 80s

