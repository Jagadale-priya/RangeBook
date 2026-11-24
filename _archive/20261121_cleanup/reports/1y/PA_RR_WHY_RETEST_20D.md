# Why R:R-accurate failed · autopsy + retest · NIFTY 20d

**Window:** `2026-10-26` → `2026-11-20` · live lock `pa_no_trap` unchanged.

## 1) Why `rr_accurate` hurt

- BASE: n=88 hit=67.05% avgR=0.434 sum=630.0
- rr_acc would **keep** 8 / **kill** 80
- Of kills: **54 winners** removed, 26 losers removed
- Kill reasons (wins): `{'rr_lt_min': 32, 'kept': 5, 'no_real_target': 22}`
- Kill reasons (losses): `{'no_real_target': 16, 'rr_lt_min': 10, 'kept': 3}`

### Real target presence

- Wins with real tgt: **62.7%** · Losses with real tgt: **44.8%**
- Book **with** real tgt: {'n': 50, 'hit': 74.0, 'sum': 483.3, 'avgR': 0.616}
- Book **without** real tgt: {'n': 38, 'hit': 57.9, 'sum': 146.6, 'avgR': 0.194}

### Planned real RR buckets (only rows with real tgt)

| Bucket | N | Hit% | AvgR | Sum | Hit1R% |
|---|---:|---:|---:|---:|---:|
| rr<1.0 | 31 | 80.6 | 0.779 | 414.6 | 80.6 |
| 1.0-1.5 | 11 | 63.6 | 0.255 | 38.3 | 63.6 |
| 1.5-2.5 | 3 | 66.7 | 0.057 | 4.9 | 66.7 |
| 2.5-4 | 2 | 100.0 | 0.747 | 31.6 | 100.0 |
| >=4 far | 3 | 33.3 | 0.733 | -6.0 | 66.7 |

### Distance to nearest opposing level (R units)

| Bucket | N | Hit% | AvgR | Sum | Hit1R% |
|---|---:|---:|---:|---:|---:|
| no_real | 38 | 57.9 | 0.194 | 146.6 | 57.9 |
| <1R tight | 31 | 80.6 | 0.779 | 414.6 | 80.6 |
| 1-2R | 11 | 63.6 | 0.255 | 38.3 | 63.6 |
| 2-3R | 4 | 75.0 | 0.24 | 21.4 | 75.0 |
| >=3R far | 4 | 50.0 | 0.727 | 9.1 | 75.0 |

### Path / emptiness checks

- Wall inside 1R **yes**: {'n': 31, 'hit': 80.6, 'sum': 414.6, 'avgR': 0.779}
- Wall inside 1R **no**: {'n': 57, 'hit': 59.6, 'sum': 215.5, 'avgR': 0.246}
- Far empty (≥3R) **yes**: {'n': 4, 'hit': 50.0, 'sum': 9.1, 'avgR': 0.727}
- Far empty **no**: {'n': 84, 'hit': 67.9, 'sum': 621.0, 'avgR': 0.42}

### Planned RR vs realized

- Wins avg MFE_R=1.841 · avg planned RR_real=1.141
- Loss avg MFE_R=0.499 · avg planned RR_real=3.601
- Corr(planned RR_real, realized R) = **-0.125**

## Root cause (plain)

1. This book **pays via trail@1R / pin_protect**, not by tagging a far PDH/range target — so **large planned R:R ≠ edge** (corr vs realized R = **-0.125**).
2. The **best** rows are **tight to an opposing wall (<1R)** — hit **80.6%**, sum **414.6** of BASE’s 630. Classic textbook “need R:R≥1.5” **kills those winners** (`rr_lt_min` removed **32 wins**).
3. Requiring `min_rr≥1.5` + real target kept only ~8–10 trades; far buckets (`RR≥4` / `≥3R`) are weak.
4. **Inverted** vs the first “clear-1R” idea: wall-inside-1R is a **feature** here (often sweep/reclaim into level), not a bug — `clear_1R` gate collapsed hit to 53%.
5. Mild useful filter: **`reject_far_empty`** (drop nearest opp ≥3R) → hit 68.24% / sum ~629 (tiny lift, almost same book).

## 2) Retest — better R:R definitions

| Logic | N | Hit% | AvgR | Sum | Hit1R% | Hard SL |
|---|---:|---:|---:|---:|---:|---:|
| `BASE_pa_no_trap` | 88 | 67.05 | 0.434 | 630.0 | 68.2 | 28 |
| `rr_acc_15` | 10 | 50.0 | 0.186 | 3.0 | 60.0 | 4 |
| `clear_1R` | 49 | 53.06 | 0.143 | 90.5 | 55.1 | 22 |
| `reject_far_empty` | 85 | 68.24 | 0.426 | 629.35 | 68.2 | 27 |
| `soft_rr_15` | 50 | 58.0 | 0.243 | 209.7 | 60.0 | 20 |
| `no_tight_wall` | 46 | 54.35 | 0.182 | 111.2 | 56.5 | 20 |
| `clear_1R_and_no_far` | 46 | 56.52 | 0.146 | 126.6 | 56.5 | 20 |

**Best on this window (hit→sum→avgR):** `reject_far_empty` n=85 hit=68.24% sum=629.35

Live lock **not** wired. Prefer a gate that lifts hit without collapsing sum vs BASE.

