# PA accuracy lock · 2026-11-20 · `v2f_cap3`

Research: Consol→Break→Retest (CBRT) + structure ablations on **NIFTY 1m** Kite.

## Locked for live

| Knob | Value |
|---|---|
| body_min | 0.55 |
| or_side_align | True |
| side_flip_cooldown | 20 bars |
| max_calls_day | 3 |
| SL | prev candle + swing (structure) |
| Target | none — trail after 1R |

## Comparison

| Book | Full N/Hit/R/Sum | L10 Hit | Today Hit/Sum |
|---|---|---:|---|
| v1 | 76/67.11/0.461/611.9 | 63.89 | 4/50.0/27.8 |
| body55_or | 58/67.24/0.531/405.4 | 70.97 | 4/75.0/80.1 |
| **v2f_cap3** | 46/71.74/0.644/376.9 | 75.0 | 3/66.67/16.55 |
| cbrt_v2 | 22/63.64/0.285/159.15 | 63.64 | 3/66.67/50.85 |
| cbrt_v2_chase | 35/68.57/0.371/286.9 | 64.29 | 3/66.67/50.85 |

## Today locked calls

| HM | Side | Setup | Entry | SL | Risk | Exit | Pts | R | MFE |
|---|---|---|---:|---:|---:|---|---:|---:|---:|
| 10:21 | BUY | SWEEP_RECLAIM | 25500.05 | 25484.2 | 15.85 | trail_sl | 26.65 | 1.681 | 41.7 |
| 11:22 | BUY | BREAK_HOLD | 25548.35 | 25529.6 | 18.75 | sl | -18.75 | -1.0 | 9.3 |
| 11:39 | BUY | SWEEP_RECLAIM | 25556.1 | 25547.25 | 8.85 | trail_sl | 8.65 | 0.977 | 17.55 |

## Notes

- **CBRT v2** improved vs v1 (45%→64%) after requiring break **extension before retest**.
- Still below structure accuracy on this 20-session tape — kept as research path.
- **v2f_cap3** = body55_or + flip cooldown + cap3 → best L10 accuracy **75%**.
