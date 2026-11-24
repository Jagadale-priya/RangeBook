# NIFTY 1m — S/R High-Move Proven Logic

Window 6m: **2026-05-04 → 2026-11-16** (136 sessions) · 2m slice: last 45 sessions · horizon **90 bars** · session 09:30–14:30.

## What “high / one-direction move” means

- **OneDir%**: MFE≥20 and MFE≥2×MAE (favour dominates adverse)
- **Clean%**: MFE≥30 and MAE≤12 (big run, little pain)
- Also MFE≥20/30/40/50 rates — **no SL/T exits** in this study

## S/R archetypes tested

1. **Bounce** — entry near support (BUY) / resistance (SELL)
2. **Breakout** — close beyond opposing S/R with control
3. **Failed-break reverse** — liquidity grab at session magnet + sweep
4. **VWAP / open reclaim** — reclaim key level with control
5. **Runway** — room_fav ≥ 2–3×ATR so the move *can* extend
6. **Hold-break / trend** — existing setup router regimes

## Gate sweep — last ~2 months (rank by high-move score)

| Gate | n | OneDir% | Clean% | MFE≥20 | MFE≥30 | MFE≥40 | MFE≥50 | avgMFE | avgMAE | edge | score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `TIER_A/B + clear_path` | 35 | **60.0** | 48.57 | 88.57 | 74.29 | 68.57 | 62.86 | 90.18 | 38.17 | 52.01 | 61.43 |
| `HELD + hold_break + runway_2ATR` | 29 | **58.62** | 24.14 | 89.66 | 79.31 | 65.52 | 62.07 | 80.76 | 40.34 | 40.42 | 56.21 |
| `HELD + hold_break regime` | 52 | **53.85** | 23.08 | 78.85 | 71.15 | 61.54 | 55.77 | 68.67 | 47.3 | 21.37 | 51.35 |
| `HELD + bounce + clear_path` | 128 | **43.75** | 15.62 | 82.03 | 76.56 | 64.84 | 56.25 | 70.4 | 57.08 | 13.32 | 46.56 |
| `PROVEN3: hold_break|bounce + control + runway2` | 272 | **44.85** | 18.38 | 80.51 | 72.43 | 62.87 | 52.21 | 63.77 | 53.67 | 10.1 | 46.51 |
| `HELD + clear_path (≥1.5ATR room)` | 274 | **44.16** | 17.15 | 79.93 | 72.99 | 62.04 | 52.92 | 72.88 | 56.15 | 16.73 | 46.06 |
| `TIER_A hold_break` | 40 | **45.0** | 25.0 | 75.0 | 60.0 | 52.5 | 45.0 | 59.33 | 56.15 | 3.17 | 44.5 |
| `HELD raw` | 2656 | **41.83** | 18.86 | 76.05 | 66.27 | 56.51 | 46.42 | 60.48 | 53.16 | 7.32 | 43.42 |
| `TIER_A/B + runway_2ATR` | 18 | **50.0** | 33.33 | 83.33 | 66.67 | 55.56 | 50.0 | 76.34 | 45.52 | 30.82 | 43.21 |
| `HELD + runway_3ATR` | 472 | **41.53** | 15.04 | 77.97 | 69.07 | 60.59 | 49.15 | 59.89 | 52.28 | 7.61 | 43.17 |
| `HELD + bounce` | 1472 | **41.78** | 18.95 | 73.98 | 64.61 | 55.91 | 44.7 | 57.91 | 53.28 | 4.64 | 42.92 |
| `HELD + bounce + backed + control` | 1095 | **41.83** | 19.0 | 73.97 | 64.29 | 55.98 | 45.11 | 58.18 | 53.41 | 4.77 | 42.86 |
| `HELD + runway_2ATR` | 584 | **40.92** | 14.55 | 77.91 | 68.84 | 59.59 | 48.8 | 62.87 | 55.1 | 7.78 | 42.7 |
| `HELD + trend + control + clear_path` | 157 | **40.13** | 14.65 | 75.16 | 68.79 | 58.6 | 49.04 | 69.29 | 57.12 | 12.17 | 42.36 |
| `HELD + trend + runway_2ATR` | 535 | **39.81** | 14.21 | 77.2 | 68.22 | 59.63 | 48.22 | 60.85 | 55.58 | 5.27 | 41.93 |
| `HELD + vwap_reclaim` | 32 | **40.62** | 18.75 | 78.12 | 62.5 | 46.88 | 37.5 | 45.88 | 46.27 | -0.39 | 41.72 |
| `HELD + bounce + control + sweep` | 158 | **39.87** | 18.35 | 74.68 | 59.49 | 52.53 | 41.77 | 55.48 | 54.68 | 0.8 | 40.38 |
| `TIER_B control+sweep` | 135 | **37.78** | 20.74 | 74.07 | 59.26 | 54.81 | 47.41 | 63.32 | 50.66 | 12.66 | 39.96 |
| `PROVEN1: bounce+backed+control+sweep+clear` | 14 | **50.0** | 35.71 | 100.0 | 71.43 | 57.14 | 50.0 | 75.17 | 52.3 | 22.87 | 37.0 |
| `TIER_A/B + bounce` | 109 | **35.78** | 16.51 | 68.81 | 53.21 | 50.46 | 40.37 | 51.92 | 54.73 | -2.81 | 36.19 |
| `HELD + open_reclaim + control` | 46 | **21.74** | 13.04 | 67.39 | 43.48 | 36.96 | 32.61 | 40.28 | 62.62 | -22.34 | 26.09 |

## Gate sweep — last ~6 months

| Gate | n | OneDir% | Clean% | MFE≥20 | MFE≥30 | MFE≥40 | MFE≥50 | avgMFE | avgMAE | edge | score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `TIER_A/B + clear_path` | 96 | **42.71** | 30.21 | 78.12 | 67.71 | 58.33 | 46.88 | 69.31 | 44.04 | 25.26 | 47.08 |
| `HELD + vwap_reclaim` | 144 | **41.67** | 27.78 | 76.39 | 63.19 | 51.39 | 37.5 | 51.31 | 48.58 | 2.73 | 44.65 |
| `TIER_A/B + runway_2ATR` | 53 | **41.51** | 22.64 | 73.58 | 62.26 | 52.83 | 43.4 | 69.17 | 47.2 | 21.97 | 43.02 |
| `PROVEN1: bounce+backed+control+sweep+clear` | 46 | **39.13** | 26.09 | 76.09 | 60.87 | 52.17 | 41.3 | 62.21 | 50.02 | 12.19 | 42.39 |
| `HELD + trend + control + clear_path` | 488 | **41.6** | 21.52 | 72.95 | 60.66 | 52.25 | 44.47 | 60.91 | 46.06 | 14.85 | 42.3 |
| `HELD + hold_break regime` | 145 | **41.38** | 18.62 | 71.03 | 61.38 | 48.97 | 41.38 | 57.7 | 45.92 | 11.78 | 41.69 |
| `HELD + hold_break + runway_2ATR` | 80 | **42.5** | 16.25 | 75.0 | 61.25 | 47.5 | 41.25 | 63.34 | 44.19 | 19.15 | 41.56 |
| `HELD + clear_path (≥1.5ATR room)` | 862 | **39.91** | 21.0 | 71.46 | 59.98 | 50.58 | 42.69 | 58.27 | 47.82 | 10.45 | 41.2 |
| `HELD + bounce + backed + control` | 3399 | **38.31** | 19.77 | 70.79 | 57.52 | 46.16 | 35.89 | 51.52 | 46.92 | 4.6 | 39.44 |
| `HELD + bounce + clear_path` | 407 | **38.33** | 20.15 | 68.8 | 57.0 | 48.16 | 40.54 | 53.82 | 47.82 | 6.0 | 39.39 |
| `TIER_B control+sweep` | 389 | **37.02** | 19.54 | 69.41 | 58.61 | 47.56 | 36.76 | 51.98 | 47.52 | 4.46 | 39.13 |
| `PROVEN3: hold_break|bounce + control + runway2` | 773 | **37.65** | 17.59 | 71.54 | 58.99 | 46.31 | 37.77 | 54.92 | 46.32 | 8.61 | 39.04 |
| `HELD raw` | 8180 | **37.43** | 19.52 | 70.51 | 57.63 | 45.79 | 36.22 | 51.4 | 47.15 | 4.25 | 39.01 |
| `TIER_A hold_break` | 112 | **36.61** | 19.64 | 69.64 | 58.04 | 47.32 | 38.39 | 54.29 | 49.82 | 4.47 | 38.8 |
| `HELD + runway_3ATR` | 1275 | **37.57** | 16.0 | 71.53 | 58.82 | 47.92 | 38.67 | 56.25 | 46.52 | 9.73 | 38.55 |
| `HELD + bounce` | 4785 | **37.18** | 19.48 | 69.53 | 56.18 | 44.68 | 34.48 | 49.81 | 46.97 | 2.84 | 38.45 |
| `HELD + runway_2ATR` | 1603 | **36.93** | 16.59 | 70.99 | 57.89 | 47.16 | 38.68 | 56.09 | 47.81 | 8.27 | 38.13 |
| `HELD + trend + runway_2ATR` | 1462 | **36.46** | 16.62 | 70.52 | 57.18 | 46.92 | 38.44 | 55.24 | 47.55 | 7.68 | 37.72 |
| `HELD + bounce + control + sweep` | 456 | **35.75** | 18.42 | 69.74 | 55.92 | 45.18 | 34.21 | 49.7 | 47.87 | 1.83 | 37.47 |
| `TIER_A/B + bounce` | 315 | **35.56** | 18.1 | 67.94 | 56.19 | 46.67 | 35.24 | 49.38 | 49.04 | 0.34 | 37.38 |
| `HELD + open_reclaim + control` | 153 | **32.03** | 21.57 | 67.97 | 50.33 | 40.52 | 28.1 | 44.55 | 52.41 | -7.86 | 34.91 |
| `PROVEN4: vwap_reclaim + control + clear + !extreme` | 15 | **33.33** | 6.67 | 60.0 | 53.33 | 46.67 | 46.67 | 48.34 | 57.18 | -8.85 | 27.77 |

## Gap-15 multi-call books (deployment shape)

| Gate | n | OneDir% | Clean% | MFE≥20 | MFE≥30 | MFE≥40 | MFE≥50 | avgMFE | avgMAE | edge | score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `PROVEN1 · 2m · gap15` | 13 | **53.85** | 38.46 | 100.0 | 76.92 | 61.54 | 53.85 | 79.4 | 52.08 | 27.32 | 39.85 |
| `PROVEN1 · 6m · gap15` | 43 | **41.86** | 27.91 | 79.07 | 65.12 | 55.81 | 44.19 | 65.93 | 48.34 | 17.59 | 45.35 |
| `PROVEN3 · 2m · gap15` | 161 | **42.86** | 17.39 | 77.02 | 70.81 | 60.87 | 50.31 | 64.08 | 55.69 | 8.4 | 44.88 |
| `PROVEN3 · 6m · gap15` | 456 | **36.18** | 16.23 | 69.96 | 58.77 | 45.83 | 37.28 | 53.95 | 48.68 | 5.27 | 37.97 |
| `PROVEN6 · 2m · gap15` | 2 | **50.0** | 50.0 | 50.0 | 50.0 | 50.0 | 50.0 | 80.65 | 26.5 | 54.15 | 35.0 |
| `PROVEN6 · 6m · gap15` | 9 | **55.56** | 33.33 | 77.78 | 77.78 | 77.78 | 77.78 | 113.21 | 32.64 | 80.57 | 39.67 |
| `TIER_AB+runway2 · 2m · gap15` | 15 | **46.67** | 26.67 | 86.67 | 66.67 | 53.33 | 46.67 | 76.75 | 51.04 | 25.71 | 40.52 |
| `TIER_AB+runway2 · 6m · gap15` | 46 | **41.3** | 21.74 | 76.09 | 65.22 | 54.35 | 43.48 | 72.31 | 47.81 | 24.5 | 43.59 |

## Locked proven entry logic (catch the run)

Base always: textbook · DI_ok · hard34 · VWAP_with · 09:30–14:30 · multi-call gap 15m

### P1 — Bounce + backed + control + sweep + clear path
BUY near support / SELL near resistance, backed (room_against≤1ATR), buyer/seller bar, liquidity sweep with side, room_fav≥1.5ATR, not into session extreme.

### P2 — Breakout + control + runway 2ATR
Close beyond opposing S/R, control bar, ≥2ATR free space ahead, not chasing session extreme.

### P3 — Hold-break **or** bounce + control + runway 2ATR
Combines best regime (hold_break) with bounce/runway — designed for **continuation runs**.

### P5 — Failed-break reverse + clear path
Grab liquidity at session magnet (sweep+control) then reverse into open runway.

### P6 — Trend + control + sweep + runway 2ATR
One-direction trend days: only when space exists; skip buying highs / selling lows.

### Router (dynamic)
1. If **P1 or P3** forms → take (bounce/hold into space)
2. Else if **P2** forms → take (true breakout with runway)
3. Else if **P5** forms → take (liq grab reverse)
4. Else if **P6** forms → take (trend continuation)
5. Else **wait** — do not force HELD alone (raw HELD under-captures clean runs)

### Best gates 6m (n≥25) by score

1. `TIER_A/B + clear_path` — OneDir **42.71%** · Clean 30.21% · MFE30 67.71% · n=96 · edge=25.26 · score=47.08
2. `HELD + vwap_reclaim` — OneDir **41.67%** · Clean 27.78% · MFE30 63.19% · n=144 · edge=2.73 · score=44.65
3. `TIER_A/B + runway_2ATR` — OneDir **41.51%** · Clean 22.64% · MFE30 62.26% · n=53 · edge=21.97 · score=43.02
4. `PROVEN1: bounce+backed+control+sweep+clear` — OneDir **39.13%** · Clean 26.09% · MFE30 60.87% · n=46 · edge=12.19 · score=42.39
5. `HELD + trend + control + clear_path` — OneDir **41.6%** · Clean 21.52% · MFE30 60.66% · n=488 · edge=14.85 · score=42.3
6. `HELD + hold_break regime` — OneDir **41.38%** · Clean 18.62% · MFE30 61.38% · n=145 · edge=11.78 · score=41.69
7. `HELD + hold_break + runway_2ATR` — OneDir **42.5%** · Clean 16.25% · MFE30 61.25% · n=80 · edge=19.15 · score=41.56
8. `HELD + clear_path (≥1.5ATR room)` — OneDir **39.91%** · Clean 21.0% · MFE30 59.98% · n=862 · edge=10.45 · score=41.2

## Sample OneDir hits (P3 on 2m)

| Day | HM | Side | Pattern | Regime | Entry | room_fav | MFE | MAE |
|---|---|---|---|---|---:|---:|---:|---:|
| 2026-09-11 | 13:57 | BUY | rising_3_methods | trend | 23387.3 | 59.3 | 60.8 | 11.3 |
| 2026-09-11 | 14:00 | BUY | bull_run2 | trend | 23397.75 | 48.85 | 195.1 | 10.55 |
| 2026-09-15 | 10:10 | SELL | bear_run3 | trend | 23370.45 | 100.15 | 58.9 | 28.85 |
| 2026-09-15 | 10:28 | SELL | bear_run2 | trend | 23365.35 | 95.05 | 53.8 | 10.3 |
| 2026-09-15 | 10:29 | SELL | bear_run3 | trend | 23362.65 | 92.35 | 51.1 | 13.0 |
| 2026-09-15 | 10:38 | SELL | bear_run2 | mixed | 23369.6 | 18.1 | 58.05 | 4.2 |
| 2026-09-15 | 13:31 | SELL | belt_bear | trend | 23266.5 | 35.1 | 114.5 | 15.7 |
| 2026-09-15 | 14:14 | SELL | marubozu_bear | trend | 23229.2 | 999.0 | 110.6 | 51.95 |
| 2026-09-21 | 13:33 | BUY | bull_run3 | trend | 23434.45 | 999.0 | 32.35 | 11.1 |
| 2026-09-21 | 13:34 | BUY | three_soldiers | trend | 23436.95 | 999.0 | 29.85 | 13.6 |
| 2026-09-22 | 10:38 | SELL | belt_bear | trend | 23406.25 | 76.05 | 64.75 | 5.05 |
| 2026-09-22 | 10:39 | SELL | bear_run2 | trend | 23400.15 | 69.95 | 58.65 | 11.15 |
| 2026-09-22 | 11:33 | SELL | bear_engulf | hold_break | 23382.35 | 13.55 | 63.25 | 2.3 |
| 2026-09-22 | 11:34 | SELL | three_outside_dn | hold_break | 23380.65 | 11.85 | 61.55 | 0.8 |
| 2026-09-22 | 11:46 | SELL | belt_bear | trend | 23361.2 | 31.0 | 42.1 | 8.6 |

## Sample misses (P3, MFE<20) — learn

| Day | HM | Side | Pattern | into_extreme | MFE | MAE |
|---|---|---|---|---|---:|---:|
| 2026-09-10 | 10:08 | SELL | three_crows | True | 5.45 | 42.85 |
| 2026-09-10 | 12:13 | BUY | bull_run3 | False | 15.9 | 34.85 |
| 2026-09-15 | 10:55 | SELL | bear_engulf | True | 18.35 | 30.55 |
| 2026-09-16 | 10:48 | BUY | marubozu_bull | False | 18.65 | 53.9 |
| 2026-09-17 | 10:10 | BUY | bull_kicker | True | 9.25 | 105.85 |
| 2026-09-17 | 12:17 | BUY | bull_run2 | True | 16.75 | 102.75 |
| 2026-09-17 | 12:22 | BUY | bull_kicker | True | 8.6 | 110.9 |
| 2026-09-23 | 12:06 | BUY | bull_kicker | True | 12.35 | 36.95 |

Elapsed 484s

Next: wire P1–P6 router into Scalper (replace/extend Tier A/B) so live only fires on these S/R-proven setups.

