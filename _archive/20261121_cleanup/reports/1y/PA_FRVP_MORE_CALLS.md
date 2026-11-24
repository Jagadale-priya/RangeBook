# PA + FRVP locked · 2026-11-20 · `frvp_vah_break`

Hard 3-call/day **removed** (cap 12). FRVP morning levels quality-gate PA entries.

| Knob | Value |
|---|---|
| FRVP | OR30 → POC / VAH / VAL |
| Mode | **vah_break** — BUY at/above VAH · SELL at/below VAL |
| SL | structure + FRVP bias |
| Max calls/day | 12 (cooldown 10) |

| Scope | N | Hit% | AvgR | Sum | Calls/day |
|---|---:|---:|---:|---:|---:|
| Full 20d | 76 | 67.11 | 0.46 | 610.91 | 4.22 |
| Today | 7 | 71.43 | 0.809 | 95.8 | — |

## Today calls

| HM | Side | Setup | Entry | SL | Pts | R |
|---|---|---|---:|---:|---:|---:|
| 10:21 | BUY | SWEEP_RECLAIM | 25500.05 | 25484.2 | 26.65 | 1.681 |
| 11:22 | BUY | BREAK_HOLD | 25548.35 | 25529.6 | -18.75 | -1.0 |
| 11:39 | BUY | SWEEP_RECLAIM | 25556.1 | 25547.25 | 8.65 | 0.977 |
| 11:52 | BUY | BREAK_HOLD | 25573.4 | 25552.05 | 63.55 | 2.977 |
| 12:07 | BUY | SWEEP_RECLAIM | 25635.05 | 25622.8 | 11.6 | 0.947 |
| 13:59 | BUY | BREAK_HOLD | 25744.95 | 25724.4 | 22.25 | 1.083 |
| 14:14 | BUY | BREAK_HOLD | 25766.2 | 25748.05 | -18.15 | -1.0 |

## Why this vs cap3 / near_dense

- Wanted **more calls** — not stuck at 3/day
- Wanted **FRVP S/R** from morning indicator
- `frvp_vah_break`: ~4.2 calls/day · L10 ~73% · today 7 / +96
- `pa_uncap` has more N but no FRVP filter; this keeps FRVP quality
