# Kill-SL-only research · Option Blue base `pa_sr_acc_mid`

Window 2026-10-22 → 2026-11-20 (22 live sessions). Same `scan_session` as Option Blue.

**BASE (Option Blue live):** n=29 hit=82.76% avgR=0.675 sum=358.15 · wins=24 · hard_SL=5

## Constraint

Do **not** touch entries that finish positive / trail winners. Only eliminate hard stop-loss entries.

## What hard-SLs looked like

| Trait | Wins | Hard SL |
|---|---:|---:|
| Opp-level distance (ATR) | +0.79 | **−0.17** (already through level) |
| Green/red streak | 1.7 | **3.2** (chase) |
| Expand vs prior bar | 1.24 | 1.25 |

## Winner-safe killer (`chase_v1`)

Block entry if **any**:

1. Expanding bar into opposing S/R: `expand ≥ 1.5` and `opp_dist ≤ 0.20 ATR`
2. Tiny structure risk: `risk ≤ 6`
3. Marubozu already through level: `body ≥ 0.95` and `opp_dist ≤ 0`

| Book | N | Hit% | AvgR | Sum | SL killed | Wins killed |
|---|---:|---:|---:|---:|---:|---:|
| Option Blue base | 29 | 82.76 | 0.675 | 358.15 | — | — |
| **+ chase_v1** | 24 | **100.0** | **1.024** | **433.4** | **5/5** | **0/24** |

Wired live as `pa_sr_acc_mid_slkill` (`sl_kill_mode=chase_v1`, logic v3c).
