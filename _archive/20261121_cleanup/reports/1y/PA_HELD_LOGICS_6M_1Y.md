# Held PA logics · 22d / 6m / 1y (live-path 1m)

NIFTY 1m Kite · available `2025-10-17` → `2026-11-20` (271 sessions).
Evaluation = same causal `scan_session` as Option Blue (closed 1m bars).
Live lock **not changed**: `pa_sr_acc_mid_slkill`.

## 22d_ref · 2026-10-22 → 2026-11-20 (22 sessions)

| Logic | N | Hit% | AvgR | Sum pts | Hard SL | Days w/ | /day |
|---|---:|---:|---:|---:|---:|---:|---:|
| **pa_only** | 96 | 64.58 | 0.489 | 691.5 | 32 | 20 | 4.36 |
| no_trap | 95 | 65.26 | 0.409 | 643.5 | 32 | 20 | 4.32 |
| frvp_no_exhaust | 76 | 67.11 | 0.466 | 631.06 | 23 | 19 | 3.45 |
| frvp_vah_break | 83 | 65.06 | 0.426 | 624.41 | 27 | 20 | 3.77 |
| frvp_read_v3_pin | 50 | 76.0 | 0.512 | 435.56 | 12 | 18 | 2.27 |
| pa_sr_acc_mid_slkill | 24 | 100.0 | 1.024 | 433.4 | 0 | 13 | 1.09 |
| pa_sr_acc_mid | 29 | 82.76 | 0.675 | 358.15 | 5 | 13 | 1.32 |
| pa_sr_full_v1 | 42 | 69.05 | 0.41 | 300.5 | 13 | 17 | 1.91 |

**Best sum:** `pa_only` · sum=691.5 · hit=64.58
**Best hit:** `pa_sr_acc_mid_slkill` · hit=100.0 · sum=433.4

## 6m · 2026-05-22 → 2026-11-20 (126 sessions)

| Logic | N | Hit% | AvgR | Sum pts | Hard SL | Days w/ | /day |
|---|---:|---:|---:|---:|---:|---:|---:|
| **pa_only** | 783 | 61.3 | 0.367 | 3704.9 | 291 | 120 | 6.21 |
| no_trap | 773 | 62.35 | 0.356 | 3662.15 | 284 | 120 | 6.13 |
| frvp_vah_break | 706 | 60.06 | 0.324 | 3055.31 | 271 | 119 | 5.6 |
| frvp_no_exhaust | 653 | 59.11 | 0.282 | 2608.23 | 256 | 118 | 5.18 |
| frvp_read_v3_pin | 482 | 61.62 | 0.334 | 2286.93 | 180 | 116 | 3.83 |
| pa_sr_full_v1 | 385 | 58.44 | 0.287 | 1418.7 | 156 | 111 | 3.06 |
| pa_sr_acc_mid | 273 | 61.17 | 0.326 | 1330.95 | 102 | 99 | 2.17 |
| pa_sr_acc_mid_slkill | 184 | 63.04 | 0.32 | 952.4 | 67 | 90 | 1.46 |

**Best sum:** `pa_only` · sum=3704.9 · hit=61.3
**Best hit:** `pa_sr_acc_mid_slkill` · hit=63.04 · sum=952.4

## 1y · 2025-11-17 → 2026-11-20 (252 sessions)

| Logic | N | Hit% | AvgR | Sum pts | Hard SL | Days w/ | /day |
|---|---:|---:|---:|---:|---:|---:|---:|
| **pa_only** | 1527 | 61.95 | 0.406 | 7915.35 | 545 | 240 | 6.06 |
| no_trap | 1507 | 62.84 | 0.396 | 7791.85 | 535 | 240 | 5.98 |
| frvp_vah_break | 1365 | 61.68 | 0.391 | 7159.57 | 488 | 235 | 5.42 |
| frvp_no_exhaust | 1249 | 61.49 | 0.36 | 6192.07 | 450 | 231 | 4.96 |
| frvp_read_v3_pin | 926 | 63.61 | 0.374 | 4832.21 | 320 | 223 | 3.67 |
| pa_sr_full_v1 | 729 | 60.08 | 0.323 | 2806.55 | 279 | 213 | 2.89 |
| pa_sr_acc_mid | 511 | 62.04 | 0.309 | 2328.6 | 187 | 188 | 2.03 |
| pa_sr_acc_mid_slkill | 338 | 63.31 | 0.313 | 1625.0 | 120 | 165 | 1.34 |

**Best sum:** `pa_only` · sum=7915.35 · hit=61.95
**Best hit:** `frvp_read_v3_pin` · hit=63.61 · sum=4832.21
