# Advanced accuracy · NIFTY last 20 sessions

**Window:** `2026-10-26` → `2026-11-20`
**Prior lock:** `pa_no_trap` · **Wired now:** `adv_near_wall_10` (accuracy-first; see Action)

Stack from autopsy: near opposing wall / real S/R help; far-empty & large planned RR hurt. Optional `chase_v1` SL-killer. No day-call / loss-pause holds.

## Summary (accuracy-first sort in report body)

| Logic | N | Hit% | AvgR | Sum | Hit1R% | Hard SL | Gate / kill |
|---|---:|---:|---:|---:|---:|---:|---|
| `adv_near15_chase_read` | 24 | 91.67 | 0.86 | 319.65 | 91.7 | 2 | adv_near_wall+chase_v1 |
| `adv_real_tgt_read_v3` | 31 | 83.87 | 0.66 | 301.05 | 83.9 | 5 | adv_real_tgt+none |
| `adv_near15_read_v3` | 29 | 82.76 | 0.666 | 285.5 | 82.8 | 5 | adv_near_wall+none |
| `adv_near_wall_10` | 35 | 77.14 | 0.712 | 419.7 | 77.1 | 8 | adv_near_wall+none |
| `adv_real_tgt_chase` | 42 | 73.81 | 0.459 | 307.4 | 76.2 | 10 | adv_real_tgt+chase_v1 |
| `adv_near20_chase` | 38 | 73.68 | 0.469 | 261.05 | 73.7 | 10 | adv_near_wall+chase_v1 |
| `adv_v1_nw20_chase` | 38 | 73.68 | 0.469 | 261.05 | 73.7 | 10 | adv_v1+chase_v1 |
| `adv_near15_chase` | 37 | 72.97 | 0.458 | 252.65 | 73.0 | 10 | adv_near_wall+chase_v1 |
| `adv_v1_nw15_chase` | 37 | 72.97 | 0.458 | 252.65 | 73.0 | 10 | adv_v1+chase_v1 |
| `adv_real_tgt` | 51 | 72.55 | 0.585 | 462.15 | 74.5 | 13 | adv_real_tgt+none |
| `adv_near_wall_20` | 46 | 71.74 | 0.54 | 401.9 | 71.7 | 13 | adv_near_wall+none |
| `adv_v1_nw20` | 46 | 71.74 | 0.54 | 401.9 | 71.7 | 13 | adv_v1+none |
| `adv_no_far_chase` | 70 | 71.43 | 0.428 | 498.8 | 71.4 | 20 | adv_no_far+chase_v1 |
| `adv_near_wall_15` | 45 | 71.11 | 0.532 | 393.5 | 71.1 | 13 | adv_near_wall+none |
| `adv_v1_nw15` | 45 | 71.11 | 0.532 | 393.5 | 71.1 | 13 | adv_v1+none |
| `no_trap_chase` | 72 | 69.44 | 0.395 | 485.55 | 70.8 | 21 | no_trap+chase_v1 |
| `adv_no_far` | 85 | 68.24 | 0.426 | 629.35 | 68.2 | 27 | adv_no_far+none |
| `BASE_pa_no_trap` | 88 | 67.05 | 0.434 | 630.0 | 68.2 | 28 | no_trap+none |

**BASE:** n=88 hit=67.05% sum=630.0
**Best hit overall:** `adv_near15_chase_read` hit=91.67% n=24 sum=319.65

### Wire rule
Auto-script Pareto (hit≥BASE+1 **and** sum≥85% BASE): only `adv_no_far` (+1.2 hit, same points).

**Accuracy-first override (user ask):** wired **`adv_near_wall_10`**
- Rule: require nearest opposing S/R within **1.0R** (plus no_trap)
- 20d: n=35 hit=**77.14%** avgR=0.712 sum=419.7 (vs BASE 67.05% / 630)
- Tradeoff: fewer points (−33%) for **+10 hit pts** and fewer hard SLs (8 vs 28)

Max-hit research (not wired — sum ~半): `adv_near15_chase_read` 91.7% / sum 320.

