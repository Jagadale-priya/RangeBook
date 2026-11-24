# Candle-aware research · locked `frvp_vah_break`

Window 2026-10-22 → 2026-11-20 (22 sessions). Understanding candles **before** entry and **during** the move.

## What candles say (autopsy)

| Feature | Wins | Hard SL |
|---|---|---|
| N | 54 | 27 |
| Entry weak (doji/pin against/poor close) % | 1.9 | 3.7 |
| Entry OK close location % | 96.3 | 92.6 |
| Entry reject (pin/engulf) % | 13.0 | 33.3 |
| Engulf % | 13.0 | 22.2 |
| Marubozu % | 11.1 | 14.8 |
| Prior exhaust % | 5.6 | 18.5 |
| Prior reject % | 35.2 | 25.9 |
| Avg green/red streak | 1.56 | 1.85 |
| Avg entry body | 0.66 | 0.6 |
| Avg bars to 1R | 8.26 | 17.55 |
| Avg opposing candles to 1R | 5.72 | 14.93 |
| Avg pin-against during path | 0.83 | 1.15 |

## Ablation (entry candle gate × trail mode)

Base locked: n=83 hit=65.06% avgR=0.426 sum=624.41

| Variant | N | Hit% | AvgR | Sum |
|---|---:|---:|---:|---:|
| **BASE** | 83 | 65.06 | 0.426 | 624.41 |
| **quality+base** | 64 | 70.31 | 0.461 | 510.06 |
| streak2+base | 32 | 68.75 | 0.617 | 361.71 |
| no_exhaust+base | 73 | 68.49 | 0.503 | 648.66 |
| quality+candle_tight | 64 | 67.19 | 0.378 | 436.11 |
| quality_soft+base | 78 | 66.67 | 0.428 | 588.01 |
| ok_close+base | 79 | 65.82 | 0.421 | 586.76 |
| no_weak+base | 81 | 65.43 | 0.425 | 607.56 |
| none+base | 83 | 65.06 | 0.426 | 624.41 |
| quality_soft+candle_tight | 78 | 64.1 | 0.332 | 483.16 |
| quality+candle_hold | 64 | 64.06 | 0.336 | 388.86 |
| no_weak+candle_tight | 81 | 62.96 | 0.331 | 501.21 |
| none+candle_tight | 83 | 62.65 | 0.321 | 499.86 |
| quality_soft+candle_hold | 78 | 61.54 | 0.293 | 426.26 |
| no_weak+candle_hold | 81 | 60.49 | 0.296 | 447.01 |
| none+candle_hold | 83 | 60.24 | 0.302 | 466.41 |
| reject_or_maru+base | 22 | 45.45 | -0.06 | -49.15 |

## Recommended candle handling

| Pick | Why |
|---|---|
| **Live lock: `no_exhaust` + structure trail** | n=73 hit=68.5% avgR=0.503 **sum=648.7** (beats base sum 624) |
| Hit-max research: `quality+base` | n=64 hit=70.3% but sum falls to 510 — too few calls |
| Candle trail modes | All worse than structure trail — **not wired** |

### What candles taught us

1. **Before entry — prior exhaustion is the real poison:** SL trades show 18.5% prior-exhaust vs 5.6% on wins. Skip that bar + weak dojis/pin-against.
2. **Before entry — reject/engulf at the signal bar is NOT a free win:** higher on SL than wins; do not require pin/engulf to fire.
3. **During move — speed to 1R:** wins ~8 bars, hard-SL ~17 bars with more opposing candles. Structure trail after 1R already handles this better than candle_tight / candle_hold.
4. **Trail:** keep ratchet under/over prior bar + 3-bar structure_fail. Do not exit early on 2 opposing closes (cuts expectancy).

_Wired into locked `frvp_vah_break` as `candle_entry_mode=no_exhaust` (logic v2g)._
