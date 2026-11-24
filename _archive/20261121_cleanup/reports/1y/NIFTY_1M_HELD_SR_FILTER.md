# NIFTY HELD — Support/Resistance path filter

Skip entries that must travel **into nearby opposing S/R** (wall) before T1.

**S/R sources:** swing pivots (L=3), day open, prior day H/L/C, VWAP.
**Entry base:** DI+hard34+VWAP · 09:30–14:30 · 1/day · Exit T1=12 EMA34 trail

## Loss vs win: wall frequency (HELD baseline, 1y)

| | n | wall&lt;T1 | wall&lt;20 | bounce | avg room_fav |
|---|---:|---:|---:|---:|---:|
| Wins | 172 | 51.2% | 62.2% | 51.2% | 164.7 |
| Losses | 75 | 68.0% | 74.7% | 60.0% | 180.2 |

## last_1y (`2025-11-17` → `2026-11-16`)

### Exit = fixed T12

| Gate | n | Hit% | Cover | Avg pts | Total | PF | avg room |
|---|---:|---:|---:|---:|---:|---:|---:|
| `HELD only` | 247 | 69.64% | 99.6% | **-1.16** | -286.0 | 0.88 | 169.42 |
| `HELD + clear_T1 (no wall <12)` | 247 | 73.28% | 99.6% | **0.93** | 230.2 | 1.12 | 325.19 |
| `HELD + clear_20` | 247 | 70.45% | 99.6% | **-0.13** | -32.05 | 0.98 | 466.33 |
| `HELD + clear_30` | 246 | 67.48% | 99.19% | **-1.64** | -404.15 | 0.83 | 549.03 |
| `HELD + clear_ATR` | 247 | 74.49% | 99.6% | **1.14** | 280.75 | 1.15 | 306.46 |
| `HELD + clear_1.5ATR` | 247 | 72.06% | 99.6% | **0.34** | 83.95 | 1.04 | 419.44 |
| `HELD + bounce (near fav S/R)` | 247 | 70.04% | 99.6% | **-0.02** | -4.85 | 1.0 | 135.4 |
| `HELD + bounce + clear_T1` | 246 | 69.11% | 99.19% | **0.44** | 108.2 | 1.06 | 305.67 |
| `HELD + clear_T1 + not_bounce_only` | 247 | 73.28% | 99.6% | **0.93** | 230.2 | 1.12 | 325.19 |
| `HELD + clear_20 + bounce` | 242 | 68.18% | 97.58% | **0.22** | 53.5 | 1.03 | 447.63 |
| `HELD + room_fav≥15` | 247 | 69.64% | 99.6% | **-0.25** | -62.95 | 0.97 | 383.46 |
| `HELD + room_fav≥20` | 247 | 70.45% | 99.6% | **-0.13** | -32.05 | 0.98 | 466.33 |
| `HELD + room_fav≥25` | 246 | 69.51% | 99.19% | **-0.89** | -218.4 | 0.9 | 524.66 |
| `HELD + !into_wall + room_against≤1ATR (backed)` | 247 | 72.87% | 99.6% | **1.52** | 376.1 | 1.21 | 301.28 |

### Exit = ratchet arm12 gb8

| Gate | n | Hit% | Cover | Avg pts | Total | PF |
|---|---:|---:|---:|---:|---:|---:|
| `HELD only` | 247 | 69.64% | 99.6% | **2.0** | 493.3 | 1.21 |
| `HELD + clear_T1 (no wall <12)` | 247 | 73.28% | 99.6% | **3.86** | 953.05 | 1.49 |
| `HELD + clear_20` | 247 | 70.45% | 99.6% | **2.54** | 626.15 | 1.3 |
| `HELD + room_fav≥20` | 247 | 70.45% | 99.6% | **2.54** | 626.15 | 1.3 |
| `HELD + bounce (near fav S/R)` | 247 | 70.04% | 99.6% | **2.8** | 691.45 | 1.33 |
| `HELD + clear_T1 + not_bounce_only` | 247 | 73.28% | 99.6% | **3.86** | 953.05 | 1.49 |
| `HELD + !into_wall + room_against≤1ATR (backed)` | 247 | 72.87% | 99.6% | **4.36** | 1077.3 | 1.6 |

### Best T12 by hit then avg pts

1. `HELD + clear_ATR` → hit **74.49%** · avg **1.14** · cover 99.6% · n=247
2. `HELD + clear_T1 (no wall <12)` → hit **73.28%** · avg **0.93** · cover 99.6% · n=247
3. `HELD + clear_T1 + not_bounce_only` → hit **73.28%** · avg **0.93** · cover 99.6% · n=247
4. `HELD + !into_wall + room_against≤1ATR (backed)` → hit **72.87%** · avg **1.52** · cover 99.6% · n=247
5. `HELD + clear_1.5ATR` → hit **72.06%** · avg **0.34** · cover 99.6% · n=247

## last_3m (`2026-08-17` → `2026-11-16`)

### Exit = fixed T12

| Gate | n | Hit% | Cover | Avg pts | Total | PF | avg room |
|---|---:|---:|---:|---:|---:|---:|---:|
| `HELD only` | 62 | 77.42% | 98.41% | **3.89** | 241.05 | 1.72 | 147.75 |
| `HELD + clear_T1 (no wall <12)` | 62 | 75.81% | 98.41% | **3.22** | 199.75 | 1.55 | 274.66 |
| `HELD + clear_20` | 62 | 66.13% | 98.41% | **-0.96** | -59.75 | 0.89 | 551.01 |
| `HELD + clear_30` | 62 | 64.52% | 98.41% | **-2.71** | -168.1 | 0.74 | 663.61 |
| `HELD + clear_ATR` | 62 | 79.03% | 98.41% | **3.42** | 212.15 | 1.56 | 230.87 |
| `HELD + clear_1.5ATR` | 62 | 66.13% | 98.41% | **-1.3** | -80.6 | 0.86 | 454.32 |
| `HELD + bounce (near fav S/R)` | 62 | 79.03% | 98.41% | **4.26** | 263.95 | 1.81 | 93.5 |
| `HELD + bounce + clear_T1` | 62 | 72.58% | 98.41% | **2.21** | 136.85 | 1.34 | 302.87 |
| `HELD + clear_T1 + not_bounce_only` | 62 | 75.81% | 98.41% | **3.22** | 199.75 | 1.55 | 274.66 |
| `HELD + clear_20 + bounce` | 61 | 65.57% | 96.83% | **0.15** | 9.35 | 1.02 | 540.44 |
| `HELD + room_fav≥15` | 62 | 64.52% | 98.41% | **-1.42** | -88.1 | 0.84 | 407.69 |
| `HELD + room_fav≥20` | 62 | 66.13% | 98.41% | **-0.96** | -59.75 | 0.89 | 551.01 |
| `HELD + room_fav≥25` | 62 | 64.52% | 98.41% | **-2.27** | -140.5 | 0.77 | 631.38 |
| `HELD + !into_wall + room_against≤1ATR (backed)` | 62 | 75.81% | 98.41% | **3.98** | 246.95 | 1.78 | 257.52 |

### Exit = ratchet arm12 gb8

| Gate | n | Hit% | Cover | Avg pts | Total | PF |
|---|---:|---:|---:|---:|---:|---:|
| `HELD only` | 62 | 77.42% | 98.41% | **8.42** | 522.1 | 2.56 |
| `HELD + clear_T1 (no wall <12)` | 62 | 75.81% | 98.41% | **6.23** | 386.05 | 2.06 |
| `HELD + clear_20` | 62 | 66.13% | 98.41% | **2.24** | 139.1 | 1.25 |
| `HELD + room_fav≥20` | 62 | 66.13% | 98.41% | **2.24** | 139.1 | 1.25 |
| `HELD + bounce (near fav S/R)` | 62 | 79.03% | 98.41% | **7.73** | 479.1 | 2.48 |
| `HELD + clear_T1 + not_bounce_only` | 62 | 75.81% | 98.41% | **6.23** | 386.05 | 2.06 |
| `HELD + !into_wall + room_against≤1ATR (backed)` | 62 | 75.81% | 98.41% | **6.35** | 393.55 | 2.24 |

### Best T12 by hit then avg pts

1. `HELD + bounce (near fav S/R)` → hit **79.03%** · avg **4.26** · cover 98.41% · n=62
2. `HELD + clear_ATR` → hit **79.03%** · avg **3.42** · cover 98.41% · n=62
3. `HELD only` → hit **77.42%** · avg **3.89** · cover 98.41% · n=62
4. `HELD + !into_wall + room_against≤1ATR (backed)` → hit **75.81%** · avg **3.98** · cover 98.41% · n=62
5. `HELD + clear_T1 (no wall <12)` → hit **75.81%** · avg **3.22** · cover 98.41% · n=62

## last_1m (`2026-10-17` → `2026-11-16`)

### Exit = fixed T12

| Gate | n | Hit% | Cover | Avg pts | Total | PF | avg room |
|---|---:|---:|---:|---:|---:|---:|---:|
| `HELD only` | 19 | 78.95% | 95.0% | **1.19** | 22.55 | 1.14 | 125.46 |
| `HELD + clear_T1 (no wall <12)` | 19 | 73.68% | 95.0% | **-0.7** | -13.3 | 0.93 | 241.59 |
| `HELD + clear_20` | 19 | 78.95% | 95.0% | **0.62** | 11.7 | 1.07 | 554.41 |
| `HELD + clear_30` | 19 | 73.68% | 95.0% | **-1.78** | -33.85 | 0.83 | 658.13 |
| `HELD + clear_ATR` | 19 | 73.68% | 95.0% | **-1.39** | -26.45 | 0.86 | 297.2 |
| `HELD + clear_1.5ATR` | 19 | 68.42% | 95.0% | **-3.32** | -63.15 | 0.71 | 555.38 |
| `HELD + bounce (near fav S/R)` | 19 | 73.68% | 95.0% | **1.01** | 19.15 | 1.13 | 162.26 |
| `HELD + bounce + clear_T1` | 19 | 73.68% | 95.0% | **-0.06** | -1.05 | 0.99 | 338.33 |
| `HELD + clear_T1 + not_bounce_only` | 19 | 73.68% | 95.0% | **-0.7** | -13.3 | 0.93 | 241.59 |
| `HELD + clear_20 + bounce` | 19 | 84.21% | 95.0% | **4.32** | 82.0 | 1.75 | 546.91 |
| `HELD + room_fav≥15` | 19 | 73.68% | 95.0% | **-0.7** | -13.3 | 0.93 | 293.48 |
| `HELD + room_fav≥20` | 19 | 78.95% | 95.0% | **0.62** | 11.7 | 1.07 | 554.41 |
| `HELD + room_fav≥25` | 19 | 73.68% | 95.0% | **-1.78** | -33.85 | 0.83 | 606.97 |
| `HELD + !into_wall + room_against≤1ATR (backed)` | 19 | 78.95% | 95.0% | **1.77** | 33.65 | 1.23 | 239.76 |

### Exit = ratchet arm12 gb8

| Gate | n | Hit% | Cover | Avg pts | Total | PF |
|---|---:|---:|---:|---:|---:|---:|
| `HELD only` | 19 | 78.95% | 95.0% | **10.09** | 191.8 | 2.22 |
| `HELD + clear_T1 (no wall <12)` | 19 | 73.68% | 95.0% | **3.93** | 74.7 | 1.41 |
| `HELD + clear_20` | 19 | 78.95% | 95.0% | **6.22** | 118.15 | 1.7 |
| `HELD + room_fav≥20` | 19 | 78.95% | 95.0% | **6.22** | 118.15 | 1.7 |
| `HELD + bounce (near fav S/R)` | 19 | 73.68% | 95.0% | **6.68** | 126.95 | 1.85 |
| `HELD + clear_T1 + not_bounce_only` | 19 | 73.68% | 95.0% | **3.93** | 74.7 | 1.41 |
| `HELD + !into_wall + room_against≤1ATR (backed)` | 19 | 78.95% | 95.0% | **5.58** | 106.0 | 1.72 |

### Best T12 by hit then avg pts

1. `HELD + clear_20 + bounce` → hit **84.21%** · avg **4.32** · cover 95.0% · n=19
2. `HELD + !into_wall + room_against≤1ATR (backed)` → hit **78.95%** · avg **1.77** · cover 95.0% · n=19
3. `HELD only` → hit **78.95%** · avg **1.19** · cover 95.0% · n=19
4. `HELD + clear_20` → hit **78.95%** · avg **0.62** · cover 95.0% · n=19
5. `HELD + room_fav≥20` → hit **78.95%** · avg **0.62** · cover 95.0% · n=19

### last_1m call ledger (T12)

| Day | Side | Pattern | room_fav | wall_t1 | bounce | HELD pts | clear20 pts |
|---|---|---|---:|:---:|:---:|---:|---:|
| 2026-10-19 | BUY | three_outside_up | 1.2 | 1 | 1 | -32.4 | -52.1 |
| 2026-10-21 | BUY | bull_run2 | 77.55 | 0 | 0 | +12.0 | +12.0 |
| 2026-10-22 | SELL | three_outside_dn | 20.7 | 0 | 1 | +12.0 | +12.0 |
| 2026-10-23 | SELL | belt_bear | 0.85 | 1 | 1 | +12.0 | +12.0 |
| 2026-10-26 | BUY | bull_run3 | 151.25 | 0 | 0 | +12.0 | +12.0 |
| 2026-10-27 | BUY | hammer | 2.4 | 1 | 1 | +12.0 | +12.0 |
| 2026-10-28 | SELL | bear_run3 | 999.0 | 0 | 1 | -57.9 | -57.9 |
| 2026-10-29 | BUY | bull_kicker | 19.8 | 0 | 0 | -32.2 | +12.0 |
| 2026-10-30 | BUY | bull_engulf | 1.9 | 1 | 1 | +12.0 | +12.0 |
| 2026-11-02 | BUY | bull_run3 | 13.15 | 0 | 0 | +12.0 | +12.0 |
| 2026-11-03 | BUY | bull_kicker | 17.45 | 0 | 1 | +12.0 | -23.3 |
| 2026-11-04 | BUY | bull_run2 | 999.0 | 0 | 0 | -35.0 | -35.0 |
| 2026-11-05 | BUY | belt_bull | 18.95 | 0 | 1 | +12.0 | +12.0 |
| 2026-11-06 | BUY | inv_hammer | 1.7 | 1 | 1 | +12.0 | +12.0 |
| 2026-11-08 | — | — | — | — | — | — | — |
| 2026-11-09 | SELL | bear_run2 | 1.4 | 1 | 1 | +12.0 | +12.0 |
| 2026-11-11 | BUY | bull_run2 | 48.35 | 0 | 0 | +12.0 | +12.0 |
| 2026-11-12 | BUY | bull_run2 | 3.7 | 1 | 0 | +12.0 | +12.0 |
| 2026-11-13 | BUY | bull_run3 | 0.75 | 1 | 1 | +12.0 | +12.0 |
| 2026-11-16 | BUY | bull_engulf | 4.55 | 1 | 0 | +12.0 | +12.0 |

## How to use live

1. Same HELD entry trigger.
2. Build S/R from recent swing pivots + PDH/PDL/PDC + day open + VWAP.
3. Measure **room_fav** = distance to next opposing level (resistance for BUY, support for SELL).
4. **Skip** if `room_fav < T1` (or `< 20` for stricter) — price has a wall before target.
5. Optional: prefer **bounce** (BUY near support / SELL near resistance) when room_fav is also clear.
