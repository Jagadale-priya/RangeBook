# PA Structure v2 ablation · 2026-11-20

**Locked live profile:** `v1`

## Why we changed (v1 loss autopsy)

- Losses avg risk **13.4** / MFE **5.6** vs wins risk **17.3** / MFE **34.7**
- Tight SL + weak sweeps stopped out before follow-through
- Fix: higher MIN_RISK, sweep quality, OR-side + strict HTF, cooldowns

## Profile comparison

| Profile | Full N | Hit% | AvgR | Sum | L10 N | L10 Hit% | L10 AvgR | Today N | Today Hit% | Today Sum | Score L10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **v1** | 76 | 67.11 | 0.461 | 611.9 | 36 | 63.89 | 0.402 | 4 | 50.0 | 27.8 | 146.871 |
| v2 | 40 | 55.0 | 0.29 | 143.15 | 19 | 52.63 | 0.245 | 2 | 50.0 | 7.9 | 115.427 |
| v2_soft_htf | 40 | 55.0 | 0.29 | 143.15 | 19 | 52.63 | 0.245 | 2 | 50.0 | 7.9 | 115.427 |
| v2_minrisk7 | 40 | 55.0 | 0.29 | 143.15 | 19 | 52.63 | 0.245 | 2 | 50.0 | 7.9 | 115.427 |
| v2_nosweep | 36 | 52.78 | 0.242 | 96.45 | 16 | 50.0 | 0.195 | 1 | 0.0 | -18.75 | 107.857 |
| v2_trail08 | 40 | 52.5 | 0.17 | 70.9 | 19 | 47.37 | 0.053 | 2 | 50.0 | 7.9 | 96.737 |
| v2_break_only | 20 | 60.0 | 0.306 | 106.0 | 9 | 33.33 | -0.264 | 1 | 0.0 | -18.75 | 55.596 |

## Today with locked `v1`

| Metric | Value |
|---|---|
| Calls | **4** |
| Hit | **50.0%** |
| Avg R | 0.14 |
| Sum pts | 27.8 |
| 1R / 2R | 50.0% / 25.0% |

| HM | Side | Setup | Entry | SL | Risk | Exit | Pts | R | MFE |
|---|---|---|---:|---:|---:|---|---:|---:|---:|
| 10:21 | BUY | SWEEP_RECLAIM | 25500.05 | 25484.2 | 15.85 | trail_sl | 26.65 | 1.681 | 41.7 |
| 10:45 | SELL | SWEEP_RECLAIM | 25546.25 | 25552.7 | 6.45 | sl | -6.45 | -1.0 | 2.95 |
| 10:58 | SELL | BREAK_HOLD | 25552.1 | 25572.7 | 20.6 | trail_sl | 18.1 | 0.879 | 34.25 |
| 11:10 | SELL | SWEEP_RECLAIM | 25525.65 | 25536.15 | 10.5 | sl | -10.5 | -1.0 | 6.1 |

## v1 → locked today delta

| | v1 | `v1` |
|---|---|---|
| N | 4 | 4 |
| Hit% | 50.0 | 50.0 |
| Sum pts | 27.8 | 27.8 |
| Avg R | 0.14 | 0.14 |

Ledger refreshed: added=4 cfg=`v1`
