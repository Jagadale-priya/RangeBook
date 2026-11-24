# NIFTY 1m — **last 6 months from today** · best logic test

**Not live.**

- Today (IST): `2026-11-16`
- Test window: `2026-05-18` → `2026-11-16` (last ~6 months)
- Train / freeze through: `2026-05-17`
- Tape: `2021-01-01 09:15:00+05:30` → `2026-11-16 12:31:00+05:30` · bars=542818
- Download note: No candles: 

## Winner (practical best on last 6 months)

Window: **2026-05-18 → 2026-11-16** (from today 2026-11-16). Train frozen ≤ 2026-05-17.

**Best usable logic:** `SELL_mid_tight` on `V2_STRICT` (±30, first_break)

- Rule: **SELL only** · clock **10:30–12:00** · `or_ext≤0.15` · `OR≥15` · `noise≤1.25` · body aligned · no both-sides
- Last-6m: **4 calls · 75% hit** (3W / 1L)
- Train (pre-window): 30 @ 60%
- Beats pool base (~45%) and ML champ books on this window

| Day | HM | Side | Gap% | Win |
|---|---|---|---:|:---:|
| 2026-07-27 | 10:39 | SELL | +0.59 | N |
| 2026-08-04 | 10:31 | SELL | −0.28 | Y |
| 2026-09-03 | 11:04 | SELL | +0.35 | Y |
| 2026-09-22 | 10:32 | SELL | +0.17 | Y |

### 100% refinement (post-hoc on the 1 loss — not pre-frozen)

Adding **gap ≤ +0.35%** drops the Jul-27 loser → **3 calls @ 100%** in last 6m  
(`2026-08-04`, `2026-09-03`, `2026-09-22`). Train stays ~62% (not a train-100 rule). Treat as research tweak only.

### Strict 100%-only (honest train∩test micros)

Union / micros: **1 call @ 100%** (`2026-10-19` SELL) — too thin to use as the main logic.

## Leaderboard (last 6m)

| Rank | Pool | Logic | N | Hit% | Kind |
|---:|---|---|---:|---:|---|
| 1 | `V2_STRICT` | `UNION_MICROS_100` | 1 | **100.0** | `UNION_100` |
| 2 | `MED` | `UNION_MICROS_100` | 1 | **100.0** | `UNION_100` |
| 3 | `FB_WIDE` | `UNION_MICROS_100` | 1 | **100.0** | `UNION_100` |
| 4 | `V2_STRICT` | `STRUCT|SELL_mid_tight` | 4 | **75.0** | `STRUCT` |
| 5 | `MED` | `STRUCT|SELL_mid_tight` | 4 | **75.0** | `STRUCT` |
| 6 | `FB_WIDE` | `ML|SELL_P55` | 4 | **75.0** | `ML` |
| 7 | `FB_WIDE` | `STRUCT|SELL_mid_tight` | 4 | **75.0** | `STRUCT` |
| 8 | `FB_WIDE` | `ML|SELL_ALL` | 25 | **52.0** | `ML` |
| 9 | `FB_WIDE` | `ML|CHAMP_P55` | 20 | **50.0** | `ML` |
| 10 | `FB_WIDE` | `ML|ALL_DU` | 53 | **49.06** | `ML` |
| 11 | `FB_WIDE` | `POOL_ALL_DU` | 53 | **49.06** | `POOL_BASE` |
| 12 | `V2_STRICT` | `ML|SELL_ALL` | 17 | **47.06** | `ML` |
| 13 | `V2_STRICT` | `STRUCT|SELL_after10_ext020` | 17 | **47.06** | `STRUCT` |
| 14 | `MED` | `ML|SELL_ALL` | 17 | **47.06** | `ML` |
| 15 | `MED` | `STRUCT|SELL_after10_ext020` | 17 | **47.06** | `STRUCT` |
| 16 | `FB_WIDE` | `STRUCT|SELL_after10_ext020` | 17 | **47.06** | `STRUCT` |
| 17 | `MED` | `ML|ALL_DU` | 32 | **46.88** | `ML` |
| 18 | `MED` | `POOL_ALL_DU` | 32 | **46.88** | `POOL_BASE` |
| 19 | `MED` | `ML|BUY_ALL` | 15 | **46.67** | `ML` |
| 20 | `FB_WIDE` | `ML|BUY_ALL` | 28 | **46.43** | `ML` |
| 21 | `V2_STRICT` | `ML|ALL_DU` | 31 | **45.16** | `ML` |
| 22 | `V2_STRICT` | `STRUCT|BOTH_after10_ext020_or20` | 31 | **45.16** | `STRUCT` |
| 23 | `V2_STRICT` | `POOL_ALL_DU` | 31 | **45.16** | `POOL_BASE` |
| 24 | `MED` | `STRUCT|BOTH_after10_ext020_or20` | 31 | **45.16** | `STRUCT` |
| 25 | `FB_WIDE` | `STRUCT|BOTH_after10_ext020_or20` | 31 | **45.16** | `STRUCT` |

## Pool `V2_STRICT`

- Gates: `{"min_or_width": 20.0, "max_noise_vs_sl": 1.25, "min_future_bars": 5, "min_entry_mins": 600, "max_entry_mins": 870, "max_or_ext": 0.2, "require_first_break": true, "require_body_align": true, "forbid_both_sides": true}`
- Train n=226 ({'n': 226, 'wins': 129, 'hit_pct': 57.08}) · Test n=31 ({'n': 31, 'wins': 14, 'hit_pct': 45.16})

### ML books

| Book | N | Hit% |
|---|---:|---:|
| `ALL_DU` | 31 | 45.16 |
| `CHAMP_P55` | 2 | 0.0 |
| `CHAMP_P58` | 2 | 0.0 |
| `CHAMP_P60` | 2 | 0.0 |
| `SELL_P55` | 0 | 0.0 |
| `BUY_P55` | 2 | 0.0 |
| `SELL_ALL` | 17 | 47.06 |
| `BUY_ALL` | 14 | 42.86 |

### Structural books

| Book | Train n/hit | Test n/hit |
|---|---|---|
| `SELL_mid_tight` | 30@60.0% | **4@75.0%** |
| `BUY_1030_1130_soft_dn_gap` | 6@100.0% | **1@0.0%** |
| `BOTH_after10_ext020_or20` | 226@57.08% | **31@45.16%** |
| `SELL_after10_ext020` | 105@58.1% | **17@47.06%** |
| `BOTH_10_1030_flat_gap` | 88@55.68% | **13@30.77%** |

### Honest union (train100∩test100 micros): **1 @ 100.0%** (micros=180)

| Day | HM | Side | Win |
|---|---|---|:---:|
| 2026-10-19 | 12:03 | SELL | Y |

### Monthly (pool day-unique)

| Month | N | Hit% |
|---|---:|---:|
| `2026-05` | 2 | 0.0 |
| `2026-06` | 3 | 0.0 |
| `2026-07` | 9 | 44.44 |
| `2026-08` | 5 | 80.0 |
| `2026-09` | 9 | 44.44 |
| `2026-10` | 3 | 66.67 |

## Pool `MED`

- Gates: `{"min_or_width": 15.0, "max_noise_vs_sl": 1.6, "min_future_bars": 5, "min_entry_mins": 600, "max_entry_mins": 870, "max_or_ext": 0.35, "require_first_break": true, "require_body_align": false, "forbid_both_sides": true}`
- Train n=236 ({'n': 236, 'wins': 135, 'hit_pct': 57.2}) · Test n=32 ({'n': 32, 'wins': 15, 'hit_pct': 46.88})

### ML books

| Book | N | Hit% |
|---|---:|---:|
| `ALL_DU` | 32 | 46.88 |
| `CHAMP_P55` | 8 | 37.5 |
| `CHAMP_P58` | 5 | 40.0 |
| `CHAMP_P60` | 5 | 40.0 |
| `SELL_P55` | 0 | 0.0 |
| `BUY_P55` | 8 | 37.5 |
| `SELL_ALL` | 17 | 47.06 |
| `BUY_ALL` | 15 | 46.67 |

### Structural books

| Book | Train n/hit | Test n/hit |
|---|---|---|
| `SELL_mid_tight` | 30@60.0% | **4@75.0%** |
| `BUY_1030_1130_soft_dn_gap` | 7@100.0% | **1@0.0%** |
| `BOTH_after10_ext020_or20` | 226@57.08% | **31@45.16%** |
| `SELL_after10_ext020` | 105@58.1% | **17@47.06%** |
| `BOTH_10_1030_flat_gap` | 88@55.68% | **13@30.77%** |

### Honest union (train100∩test100 micros): **1 @ 100.0%** (micros=180)

| Day | HM | Side | Win |
|---|---|---|:---:|
| 2026-10-19 | 12:03 | SELL | Y |

### Monthly (pool day-unique)

| Month | N | Hit% |
|---|---:|---:|
| `2026-05` | 2 | 0.0 |
| `2026-06` | 3 | 0.0 |
| `2026-07` | 9 | 44.44 |
| `2026-08` | 6 | 83.33 |
| `2026-09` | 9 | 44.44 |
| `2026-10` | 3 | 66.67 |

## Pool `FB_WIDE`

- Gates: `{"min_or_width": 12.0, "max_noise_vs_sl": 2.0, "min_future_bars": 2, "min_entry_mins": 585, "max_entry_mins": 885, "max_or_ext": 0.5, "require_first_break": true, "require_body_align": false, "forbid_both_sides": true}`
- Train n=432 ({'n': 432, 'wins': 236, 'hit_pct': 54.63}) · Test n=53 ({'n': 53, 'wins': 26, 'hit_pct': 49.06})

### ML books

| Book | N | Hit% |
|---|---:|---:|
| `ALL_DU` | 53 | 49.06 |
| `CHAMP_P55` | 20 | 50.0 |
| `CHAMP_P58` | 12 | 25.0 |
| `CHAMP_P60` | 10 | 30.0 |
| `SELL_P55` | 4 | 75.0 |
| `BUY_P55` | 16 | 43.75 |
| `SELL_ALL` | 25 | 52.0 |
| `BUY_ALL` | 28 | 46.43 |

### Structural books

| Book | Train n/hit | Test n/hit |
|---|---|---|
| `SELL_mid_tight` | 30@60.0% | **4@75.0%** |
| `BUY_1030_1130_soft_dn_gap` | 7@100.0% | **1@0.0%** |
| `BOTH_after10_ext020_or20` | 226@57.08% | **31@45.16%** |
| `SELL_after10_ext020` | 105@58.1% | **17@47.06%** |
| `BOTH_10_1030_flat_gap` | 88@55.68% | **13@30.77%** |

### Honest union (train100∩test100 micros): **1 @ 100.0%** (micros=180)

| Day | HM | Side | Win |
|---|---|---|:---:|
| 2026-10-19 | 12:03 | SELL | Y |

### Monthly (pool day-unique)

| Month | N | Hit% |
|---|---:|---:|
| `2026-05` | 2 | 0.0 |
| `2026-06` | 8 | 25.0 |
| `2026-07` | 10 | 50.0 |
| `2026-08` | 10 | 70.0 |
| `2026-09` | 12 | 41.67 |
| `2026-10` | 7 | 71.43 |
| `2026-11` | 4 | 50.0 |

## Policy

- Research only · `not_live=true`
- Do not wire live without a separate promote + paper plan.
