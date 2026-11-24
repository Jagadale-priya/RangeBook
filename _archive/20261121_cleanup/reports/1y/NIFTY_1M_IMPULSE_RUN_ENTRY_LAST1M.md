# NIFTY 1m — Impulse Run Entry (straight green/red streak)

> **RESEARCH ONLY.** Pattern from your example: after entry, market runs ~40–45+ pts with consecutive same-color 1m candles.

Window **2026-10-15 → 2026-11-16** (22 sessions).

## Pattern definition (what we hunt)

```
IMPULSE BUY : ≥4 consecutive GREEN 1m bars AND (run_high − open0) ≥ 40 pts
IMPULSE SELL: ≥4 consecutive RED   1m bars AND (open0 − run_low)  ≥ 40 pts
Entry bar   : FIRST bar of that streak (ignition)
```

Found **149** impulse runs · BUY=63 · SELL=86 · near 13:00–13:20: **7**

## Note on your “today 13:12” example

Local 1m cache ends **2026-11-16**. On **2026-11-16 13:12** NIFTY did **not** print a ≥40pt all-green run (price drifted/chopped after). Closest recent midday impulses are listed below. If your chart is **live today (newer than cache)**, refresh Kite 1m and re-run this script.

## Impulses near 13:00–13:20 (like your example)

| Day | Start | End | Side | bars | move | held | AD | compress | clear | regime |
|---|---|---|---|---:|---:|---|---|---|---|---|
| 2026-10-21 | 13:00 | 13:03 | SELL | 4 | **44.6** | True | True | False | True | trend |
| 2026-10-27 | 13:08 | 13:13 | SELL | 6 | **60.85** | True | True | False | False | trend |
| 2026-10-28 | 13:01 | 13:10 | SELL | 10 | **53.05** | False | True | False | True | mixed |
| 2026-11-02 | 13:03 | 13:09 | SELL | 7 | **61.3** | True | True | False | True | trend |
| 2026-11-02 | 13:16 | 13:20 | BUY | 5 | **45.5** | False | False | False | True | mixed |
| 2026-11-09 | 13:06 | 13:11 | SELL | 6 | **52.45** | False | True | False | True | mixed |
| 2026-11-09 | 13:14 | 13:17 | SELL | 4 | **68.75** | False | True | False | True | trend |

## All impulse runs (sample last 25)

| Day | HM | Side | bars | move | held | AD | compress | ctrl | clear | regime |
|---|---|---|---:|---:|---|---|---|---|---|---|
| 2026-11-09 | 12:04 | BUY | 4 | 45.6 | False | False | False | False | True | mixed |
| 2026-11-09 | 13:06 | SELL | 6 | 52.45 | False | True | False | True | True | mixed |
| 2026-11-09 | 13:14 | SELL | 4 | 68.75 | False | True | False | False | True | trend |
| 2026-11-11 | 09:20 | SELL | 7 | 65.45 | False | False | False | False | True | mixed |
| 2026-11-11 | 09:31 | BUY | 4 | 44.5 | True | False | False | False | True | mixed |
| 2026-11-11 | 09:49 | SELL | 7 | 64.75 | False | True | False | False | True | trend |
| 2026-11-11 | 12:05 | SELL | 10 | 69.4 | False | True | False | False | True | mixed |
| 2026-11-11 | 12:48 | BUY | 4 | 41.75 | True | False | False | False | True | trend |
| 2026-11-11 | 13:25 | SELL | 10 | 71.2 | False | True | False | True | True | mixed |
| 2026-11-11 | 13:44 | SELL | 10 | 66.0 | False | False | False | False | True | mixed |
| 2026-11-11 | 13:54 | BUY | 7 | 57.7 | True | False | False | False | True | mixed |
| 2026-11-11 | 14:02 | BUY | 6 | 41.8 | True | True | False | False | True | trend |
| 2026-11-11 | 14:50 | SELL | 19 | 93.1 | False | True | False | False | True | mixed |
| 2026-11-12 | 09:15 | BUY | 5 | 88.05 | False | False | False | False | True | mixed |
| 2026-11-12 | 09:23 | BUY | 5 | 64.7 | False | False | False | False | True | mixed |
| 2026-11-12 | 09:42 | SELL | 6 | 42.9 | False | True | False | False | True | mixed |
| 2026-11-12 | 11:09 | SELL | 5 | 43.85 | False | False | False | False | True | mixed |
| 2026-11-12 | 12:04 | SELL | 5 | 49.9 | False | False | False | False | False | mixed |
| 2026-11-13 | 09:19 | SELL | 4 | 49.85 | False | True | False | True | True | flip |
| 2026-11-13 | 09:32 | BUY | 6 | 74.5 | True | False | False | True | False | mixed |
| 2026-11-13 | 09:44 | BUY | 4 | 40.05 | True | True | False | False | True | trend |
| 2026-11-16 | 09:58 | SELL | 5 | 41.7 | False | True | False | True | True | trend |
| 2026-11-16 | 10:28 | SELL | 7 | 67.25 | False | False | False | False | True | mixed |
| 2026-11-16 | 10:57 | BUY | 6 | 41.55 | True | False | False | False | True | mixed |
| 2026-11-16 | 12:06 | BUY | 6 | 46.85 | True | True | False | True | True | trend |

## What was true at the ignition bar?

### All impulse ignitions (n=149)

| Feature at entry bar | % true |
|---|---:|
| `held` | 40.9 |
| `di_ok` | 59.1 |
| `gate_hard34` | 54.4 |
| `vwap_with` | 55.7 |
| `ad_with` | 56.4 |
| `compress_pre` | 0.0 |
| `prev_opposite` | 94.6 |
| `control_with` | 30.9 |
| `sweep_with` | 6.0 |
| `sr_bounce` | 12.1 |
| `clear_path` | 81.9 |
| `backed` | 20.8 |
| `runway_2atr` | 80.5 |
| `into_extreme` | 0.0 |

Regimes: mixed=87, trend=55, break_attempt=4, flip=2, hold_break=1

### BUY impulses only (n=63)

| Feature at entry bar | % true |
|---|---:|
| `held` | 52.4 |
| `di_ok` | 69.8 |
| `gate_hard34` | 61.9 |
| `vwap_with` | 65.1 |
| `ad_with` | 50.8 |
| `compress_pre` | 0.0 |
| `prev_opposite` | 93.7 |
| `control_with` | 23.8 |
| `sweep_with` | 4.8 |
| `sr_bounce` | 11.1 |
| `clear_path` | 84.1 |
| `backed` | 19.0 |
| `runway_2atr` | 82.5 |
| `into_extreme` | 0.0 |

Regimes: mixed=36, trend=23, break_attempt=2, hold_break=1, flip=1

### SELL impulses only (n=86)

| Feature at entry bar | % true |
|---|---:|
| `held` | 32.6 |
| `di_ok` | 51.2 |
| `gate_hard34` | 48.8 |
| `vwap_with` | 48.8 |
| `ad_with` | 60.5 |
| `compress_pre` | 0.0 |
| `prev_opposite` | 95.3 |
| `control_with` | 36.0 |
| `sweep_with` | 7.0 |
| `sr_bounce` | 12.8 |
| `clear_path` | 80.2 |
| `backed` | 22.1 |
| `runway_2atr` | 79.1 |
| `into_extreme` | 0.0 |

Regimes: mixed=51, trend=32, break_attempt=2, flip=1

### Near 13:00–13:20 only (n=7)

| Feature at entry bar | % true |
|---|---:|
| `held` | 42.9 |
| `di_ok` | 57.1 |
| `gate_hard34` | 71.4 |
| `vwap_with` | 42.9 |
| `ad_with` | 85.7 |
| `compress_pre` | 0.0 |
| `prev_opposite` | 85.7 |
| `control_with` | 42.9 |
| `sweep_with` | 0.0 |
| `sr_bounce` | 28.6 |
| `clear_path` | 85.7 |
| `backed` | 28.6 |
| `runway_2atr` | 85.7 |
| `into_extreme` | 0.0 |

Regimes: trend=4, mixed=3

## Which feature combos cover these impulses?

| Combo at ignition | n | % of impulses | avg move | BUY | SELL |
|---|---:|---:|---:|---:|---:|
| `strong first body≥0.55` | 78 | 52.3 | 60.6 | 27 | 51 |
| `HELD only` | 61 | 40.9 | 66.2 | 33 | 28 |
| `prev_opposite+ctrl+AD` | 33 | 22.1 | 57.5 | 7 | 26 |
| `AD+ctrl+clear` | 32 | 21.5 | 62.5 | 9 | 23 |
| `clear+AD+ctrl+!extreme` | 32 | 21.5 | 62.5 | 9 | 23 |
| `HELD+AD+ctrl` | 16 | 10.7 | 66.3 | 4 | 12 |
| `bounce+backed+AD` | 13 | 8.7 | 65.6 | 5 | 8 |
| `compress→impulse` | 0 | 0.0 | None | 0 | 0 |
| `HELD+compress` | 0 | 0.0 | None | 0 | 0 |
| `HELD+AD+compress` | 0 | 0.0 | None | 0 | 0 |

## How to identify this kind of entry (working hypothesis)

Your example is an **impulse ignition**, not a slow grind:

1. **Spot the start of a same-color streak** (first green of a green run / first red of a red run)
2. Prefer ignition after **compression** (quiet 10 bars) → expansion
3. Prefer **A/D with side** + **control bar** (close in favour third)
4. Prefer **not into session extreme** and some **clear path**
5. HELD (DI∧hard34∧VWAP) helps filter but does **not** alone equal impulse

Most common combo on this window: **`strong first body≥0.55`** (52.3% of impulses, avg move 60.6 pts).

### Next (still research)

1. Score a **live detector**: flag bar when first green/red + compress+AD+ctrl — then measure how often a ≥40pt streak follows (precision) and how many streaks are caught (recall).
2. Re-run when **today’s** 1m bars are in cache so we can annotate your exact 13:12 example.
3. Do **not** wire to Scalper until precision/recall both look strong.

Elapsed 7s
