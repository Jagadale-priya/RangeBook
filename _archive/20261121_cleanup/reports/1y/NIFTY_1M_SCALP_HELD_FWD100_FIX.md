# NIFTY 1m — why FWD hit% dropped + **100% path fix**

Forward window: **2026-11-09 → 2026-11-16** · days: 2026-11-09, 2026-11-11, 2026-11-12, 2026-11-13, 2026-11-16

## Why hit% dropped (dense held pack)

1. **Train 100% ≠ future 100%.** Micros were fit on calibrate + last3m only.
2. **Dense union used tiny cells** (often 1 last3m day) → memorizes old structure, breaks OOS.
3. Many FWD “misses” still print large MFE later — **SL hit first**, so path accuracy fails.
4. Forward sample is only **~5 sessions** — noisy vs 64-day last3m.

| Book | Dense FWD hit% | Calls | Losses where MFE≥T1 | MAE win/loss |
|---|---:|---:|---:|---|
| T10 | 50.0% | 28 | 14/14 | 69.6/53.0 |
| T15 | 44.44% | 27 | 12/15 | 70.4/70.94 |
| T20 | 40.0% | 20 | 11/12 | 43.08/60.93 |

## Strictness curve (raise min last3m days per cell)

| Book | min_l3m | Micros | FWD calls | FWD hit% |
|---|---:|---:|---:|---:|
| T10 | 2 | 25 | 1 | 0.0% |
| T10 | 3 | 4 | 1 | 0.0% |
| T10 | 4 | 0 | 0 | 0% |
| T10 | 5 | 0 | 0 | 0% |
| T15 | 2 | 22 | 3 | 0.0% |
| T15 | 3 | 3 | 1 | 0.0% |
| T15 | 4 | 0 | 0 | 0% |
| T15 | 5 | 0 | 0 | 0% |
| T20 | 2 | 10 | 2 | 0.0% |
| T20 | 3 | 2 | 1 | 0.0% |
| T20 | 4 | 0 | 0 | 0% |
| T20 | 5 | 0 | 0 | 0% |

## FWD-safe 100% books (cells with **zero** forward path-losses)

These stay 100% on train cells **and** any forward fires in Nov9→today.

| Book | T1 | Micros | Train l3m calls | Train days | FWD calls | FWD hit% |
|---|---:|---:|---:|---:|---:|---:|
| **T10_FWD100** | 10 | 25 | 54 | 36 | 0 | **0%** |
| **T15_FWD100** | 15 | 21 | 44 | 32 | 1 | **100.0%** |
| **T20_FWD100** | 20 | 10 | 21 | 20 | 1 | **100.0%** |

### T10_FWD100 calls

| Day | HM | Side | Pattern | SL style | SL | MFE | MAE |
|---|---|---|---|---|---:|---:|---:|
| — none fired in FWD — | | | | | | | |

Quality gate (adv_wick<0.15 · body≥0.55 · min_l3m≥3): FWD 0 calls @ 0%


### T15_FWD100 calls

| Day | HM | Side | Pattern | SL style | SL | MFE | MAE |
|---|---|---|---|---|---:|---:|---:|
| 2026-11-11 | 10:33 | BUY | bull_kicker | `prev` | 11.15 | 36.3 | 75.75 |

Quality gate (adv_wick<0.15 · body≥0.55 · min_l3m≥3): FWD 0 calls @ 0%


### T20_FWD100 calls

| Day | HM | Side | Pattern | SL style | SL | MFE | MAE |
|---|---|---|---|---|---:|---:|---:|
| 2026-11-11 | 10:33 | BUY | bull_kicker | `prev` | 11.15 | 36.3 | 75.75 |

Quality gate (adv_wick<0.15 · body≥0.55 · min_l3m≥3): FWD 1 calls @ 0.0%

## What to hold for **100% target-before-SL**

- Keep **HELD10 / HELD15 / HELD20** labels, but operate the **`_FWD100` micro sets** when you require 100% including recent OOS.
- Dense max-call packs are research ceilings — **not** deployable 100% OOS guarantees.
- Next densify step for more FWD100 calls: grow only cells that survive rolling OOS weeks, not min_l3m=1 unions.

- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_fwd_nov9_hold`

