# PA S/R + Liquidity research (NO FRVP)

Window 2026-10-22 → 2026-11-20 (22 sessions). S/R from last 2 sessions’ candle behavior.

## Baselines

| Book | N | Hit% | AvgR | Sum |
|---|---:|---:|---:|---:|
| Locked FRVP+read_v3 | 50 | 76.0 | 0.512 | 435.56 |
| PA only (no FRVP/candle) | 96 | 64.58 | 0.489 | 691.5 |

## Runtime concepts tested

1. **Multi-day S/R** — swing clusters + PDH/PDL + OR + touch/reject/cross scores
2. **Range** — where price stayed (histogram density band)
3. **Liquidity** — wick beyond level then reclaim (favor) vs trap break into level
4. **R:R** — distance to next opposing level / risk
5. **Candles** — read_v3 / no_exhaust nested in full_* gates
6. **Trail** — structure + pin_protect

## Ablation

| Variant | N | Hit% | AvgR | Sum |
|---|---:|---:|---:|---:|
| full_v1|struct|pin_protect | 24 | 83.33 | 0.615 | 257.9 |
| full_v1|struct|base | 24 | 79.17 | 0.576 | 236.45 |
| **full_v3|struct|pin_protect** | 25 | 76.0 | 0.505 | 200.0 |
| full_v1|sr_prefer|pin_protect | 21 | 66.67 | 0.73 | 181.49 |
| no_trap|struct|pin_protect | 94 | 65.96 | 0.424 | 651.3 |
| sr_align|struct|pin_protect | 94 | 65.96 | 0.424 | 651.3 |
| pa_only|struct|pin_protect | 96 | 65.62 | 0.427 | 663.6 |
| no_trap|struct|base | 94 | 64.89 | 0.487 | 679.2 |
| edge|struct|pin_protect | 91 | 64.84 | 0.389 | 595.3 |
| full_v3|sr_prefer|pin_protect | 24 | 62.5 | 0.788 | 196.89 |
| full_v2|struct|pin_protect | 42 | 61.9 | 0.201 | 167.55 |
| full_v2|struct|base | 42 | 59.52 | 0.179 | 146.1 |
| no_trap|sr_prefer|pin_protect | 83 | 59.04 | 0.475 | 539.23 |
| rr20|struct|pin_protect | 38 | 57.89 | 0.221 | 134.1 |
| edge|sr_prefer|pin_protect | 80 | 57.5 | 0.398 | 483.23 |
| rr15|struct|pin_protect | 44 | 56.82 | 0.166 | 113.75 |
| liq_favor|struct|pin_protect | 23 | 56.52 | 0.177 | 62.3 |
| full_v2|sr_prefer|pin_protect | 32 | 50.0 | 0.262 | 93.31 |
| rr15|sr_prefer|pin_protect | 36 | 47.22 | 0.195 | 95.56 |

## Recommendation

**Wired live (v3a):** `full_v1|struct|pin_protect` — n=24 hit=**83.33%** avgR=0.615 sum=257.9 (beats FRVP 76%)
- Script “best” under n≥25 floor was `full_v3` (76% tie with FRVP); **full_v1 is the accuracy winner** so that is locked.
**Best sum (volume):** `no_trap|struct|base` — n=94 hit=64.89 sum=679.2

Locked: `use_frvp=false`, `sr_gate=full_v1`, `candle_trail_mode=pin_protect`, name=`pa_sr_full_v1`.
