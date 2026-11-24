# NIFTY 1m dual CLEAN — last-1y deep accuracy (RESEARCH ONLY)

**Not live. Does not list Calls.**

- Test window: `2025-01-01` → `2025-12-30` (last full year of 1m cache)
- Train / rule-mine through: `2024-12-31` (no test leakage into heads or filters)
- Brackets: ±30 · OR bars: 15
- Bars: **461926** · days: **1235**

## Protocol

1. Build clean OR-break tickets under each gate profile.
2. Train BUY/SELL heads on pre-test tickets only.
3. Score test year; report fixed champ books.
4. Mine filter rules with **train hit = 100%** (day-unique); validate on test.
5. Oracle = in-sample max-n @100% on test (ceiling only — not a promote rule).

## Summary (test year)

| Profile | Clean | Test n | DU hit% | Best OOS-100 n | Oracle-100 n |
|---|---:|---:|---:|---:|---:|
| `V2_STRICT` | 208 | 34 | 70.59 | **0** | 24 |
| `V2_MED` | 213 | 36 | 72.22 | **0** | 26 |
| `V2_WIDE` | 391 | 67 | 62.69 | **0** | 42 |

## Profile `V2_STRICT`

- Gates: `{"min_or_width": 20.0, "max_noise_vs_sl": 1.25, "min_future_bars": 5, "min_entry_mins": 600, "max_entry_mins": 870, "max_or_ext": 0.2, "require_first_break": true, "require_body_align": true, "forbid_both_sides": true}`
- Train n=174 · Test n=34 · train100 rules=0 · oos100 rules=0

### Heads

- **BUY**: n_train=92 fit_auc=0.674 calib_auc=0.5 flip=False
- **SELL**: n_train=82 fit_auc=0.724 calib_auc=0.5 flip=False

### Fixed test books (day-unique)

| Book | N | Hit% |
|---|---:|---:|
| `ALL_DU` | 34 | 70.59 |
| `CHAMP_P55` | 14 | 57.14 |
| `CHAMP_P58` | 11 | 54.55 |
| `CHAMP_P60` | 9 | 55.56 |
| `CHAMP_P62` | 8 | 62.5 |
| `BUY_P55` | 5 | 40.0 |
| `SELL_P55` | 9 | 66.67 |

### Test slices

| Slice | N | Hit% |
|---|---:|---:|
| `ALL_day_unique` | 34 | 70.59 |
| `ALL_tickets` | 34 | 70.59 |
| `BUY_day_unique` | 21 | 66.67 |
| `SELL_day_unique` | 13 | 76.92 |
| `FB_P52_day_unique` | 18 | 66.67 |
| `FB_P55_day_unique` | 14 | 57.14 |
| `FB_P57_day_unique` | 11 | 54.55 |
| `FB_P60_day_unique` | 9 | 55.56 |
| `FB_P62_day_unique` | 8 | 62.5 |
| `FB_P65_day_unique` | 8 | 62.5 |
| `FB_P70_day_unique` | 0 | 0.0 |
| `clock_10:00-10:30` | 21 | 71.43 |
| `clock_10:30-11:30` | 7 | 71.43 |
| `clock_11:30-13:00` | 5 | 60.0 |
| `clock_13:00-14:30` | 1 | 100.0 |
| `or_ext<=0.1` | 29 | 65.52 |
| `or_ext<=0.15` | 32 | 68.75 |
| `or_ext<=0.2` | 34 | 70.59 |
| `or_ext<=0.3` | 34 | 70.59 |

### Monthly (day-unique)

| Month | N | Hit% |
|---|---:|---:|
| `2025-01` | 2 | 100.0 |
| `2025-02` | 1 | 100.0 |
| `2025-03` | 3 | 100.0 |
| `2025-04` | 1 | 100.0 |
| `2025-05` | 2 | 100.0 |
| `2025-06` | 2 | 100.0 |
| `2025-07` | 6 | 66.67 |
| `2025-08` | 4 | 50.0 |
| `2025-09` | 6 | 50.0 |
| `2025-10` | 1 | 100.0 |
| `2025-11` | 5 | 60.0 |
| `2025-12` | 1 | 0.0 |

### Best train→test **100%** rule

_No filter with train=100% also hit 100% on test with ≥1 call._

### Top mined rules (train 100% → test)

| # | Side | p≥ | ext≤ | OR≥ | clock | Test n | Test hit% | Train n |
|---:|---|---:|---:|---:|---|---:|---:|---:|

### Oracle test ceiling (in-sample — do not promote)

- n=24 hit=100.0% · `IN_SAMPLE_CEILING_not_for_promote`

| Day | HM | Side | p | Win |
|---|---|---|---:|:---:|
| 2025-05-19 | 14:00 | SELL | 0.6661 | Y |
| 2025-05-30 | 10:15 | SELL | 0.6576 | Y |
| 2025-08-07 | 10:28 | SELL | 0.6576 | Y |
| 2025-01-09 | 10:46 | SELL | 0.6518 | Y |
| 2025-07-30 | 10:28 | SELL | 0.6518 | Y |
| 2025-07-31 | 11:01 | BUY | 0.5837 | Y |
| 2025-09-12 | 10:53 | BUY | 0.5716 | Y |
| 2025-09-18 | 12:37 | SELL | 0.5565 | Y |
| 2025-11-06 | 10:09 | SELL | 0.5495 | Y |
| 2025-03-13 | 11:37 | SELL | 0.5431 | Y |
| 2025-10-24 | 10:19 | SELL | 0.5431 | Y |
| 2025-07-25 | 10:14 | SELL | 0.5337 | Y |
| 2025-03-07 | 10:08 | BUY | 0.4892 | Y |
| 2025-06-16 | 10:28 | BUY | 0.4892 | Y |
| 2025-02-01 | 11:18 | BUY | 0.4681 | Y |
| 2025-07-15 | 10:38 | BUY | 0.4681 | Y |
| 2025-09-11 | 12:32 | BUY | 0.4681 | Y |
| 2025-03-19 | 10:17 | BUY | 0.4491 | Y |
| 2025-04-22 | 10:24 | BUY | 0.4491 | Y |
| 2025-11-13 | 10:24 | BUY | 0.4491 | Y |
| 2025-11-19 | 10:07 | BUY | 0.4491 | Y |
| 2025-01-13 | 10:13 | BUY | 0.3755 | Y |
| 2025-06-13 | 10:24 | BUY | 0.3755 | Y |
| 2025-08-11 | 10:24 | BUY | 0.3755 | Y |

### Loss autopsy (test tickets)

- losses=10 wins=24
- mean p loss/win: 0.5465 / 0.5197
- mean or_ext loss/win: 0.0382 / 0.0614
- by side losses: `{"BUY": 7, "SELL": 3}`

## Profile `V2_MED`

- Gates: `{"min_or_width": 16.0, "max_noise_vs_sl": 1.5, "min_future_bars": 5, "min_entry_mins": 600, "max_entry_mins": 870, "max_or_ext": 0.3, "require_first_break": true, "require_body_align": true, "forbid_both_sides": true}`
- Train n=177 · Test n=36 · train100 rules=0 · oos100 rules=0

### Heads

- **BUY**: n_train=93 fit_auc=0.659 calib_auc=0.5 flip=False
- **SELL**: n_train=84 fit_auc=0.706 calib_auc=0.5 flip=False

### Fixed test books (day-unique)

| Book | N | Hit% |
|---|---:|---:|
| `ALL_DU` | 36 | 72.22 |
| `CHAMP_P55` | 15 | 60.0 |
| `CHAMP_P58` | 10 | 60.0 |
| `CHAMP_P60` | 10 | 60.0 |
| `CHAMP_P62` | 3 | 33.33 |
| `BUY_P55` | 6 | 50.0 |
| `SELL_P55` | 9 | 66.67 |

### Test slices

| Slice | N | Hit% |
|---|---:|---:|
| `ALL_day_unique` | 36 | 72.22 |
| `ALL_tickets` | 36 | 72.22 |
| `BUY_day_unique` | 22 | 68.18 |
| `SELL_day_unique` | 14 | 78.57 |
| `FB_P52_day_unique` | 20 | 70.0 |
| `FB_P55_day_unique` | 15 | 60.0 |
| `FB_P57_day_unique` | 10 | 60.0 |
| `FB_P60_day_unique` | 10 | 60.0 |
| `FB_P62_day_unique` | 3 | 33.33 |
| `FB_P65_day_unique` | 2 | 50.0 |
| `FB_P70_day_unique` | 0 | 0.0 |
| `clock_10:00-10:30` | 21 | 71.43 |
| `clock_10:30-11:30` | 8 | 75.0 |
| `clock_11:30-13:00` | 5 | 60.0 |
| `clock_13:00-14:30` | 1 | 100.0 |
| `or_ext<=0.1` | 30 | 66.67 |
| `or_ext<=0.15` | 33 | 69.7 |
| `or_ext<=0.2` | 35 | 71.43 |
| `or_ext<=0.3` | 36 | 72.22 |

### Monthly (day-unique)

| Month | N | Hit% |
|---|---:|---:|
| `2025-01` | 2 | 100.0 |
| `2025-02` | 2 | 100.0 |
| `2025-03` | 3 | 100.0 |
| `2025-04` | 1 | 100.0 |
| `2025-05` | 2 | 100.0 |
| `2025-06` | 2 | 100.0 |
| `2025-07` | 6 | 66.67 |
| `2025-08` | 4 | 50.0 |
| `2025-09` | 6 | 50.0 |
| `2025-10` | 2 | 100.0 |
| `2025-11` | 5 | 60.0 |
| `2025-12` | 1 | 0.0 |

### Best train→test **100%** rule

_No filter with train=100% also hit 100% on test with ≥1 call._

### Top mined rules (train 100% → test)

| # | Side | p≥ | ext≤ | OR≥ | clock | Test n | Test hit% | Train n |
|---:|---|---:|---:|---:|---|---:|---:|---:|

### Oracle test ceiling (in-sample — do not promote)

- n=26 hit=100.0% · `IN_SAMPLE_CEILING_not_for_promote`

| Day | HM | Side | p | Win |
|---|---|---|---:|:---:|
| 2025-05-19 | 14:00 | SELL | 0.6758 | Y |
| 2025-02-17 | 10:36 | BUY | 0.6133 | Y |
| 2025-07-31 | 11:01 | BUY | 0.6133 | Y |
| 2025-01-09 | 10:46 | SELL | 0.6057 | Y |
| 2025-05-30 | 10:15 | SELL | 0.6057 | Y |
| 2025-07-30 | 10:28 | SELL | 0.6057 | Y |
| 2025-09-12 | 10:53 | BUY | 0.5713 | Y |
| 2025-03-13 | 11:37 | SELL | 0.5579 | Y |
| 2025-11-06 | 10:09 | SELL | 0.5579 | Y |
| 2025-02-01 | 11:18 | BUY | 0.5317 | Y |
| 2025-03-07 | 10:08 | BUY | 0.5236 | Y |
| 2025-06-16 | 10:28 | BUY | 0.5236 | Y |
| 2025-09-18 | 12:37 | SELL | 0.5215 | Y |
| 2025-10-21 | 14:30 | SELL | 0.5215 | Y |
| 2025-07-15 | 10:38 | BUY | 0.5004 | Y |
| 2025-09-11 | 12:32 | BUY | 0.5004 | Y |
| 2025-07-25 | 10:14 | SELL | 0.4818 | Y |
| 2025-08-07 | 10:28 | SELL | 0.4818 | Y |
| 2025-10-24 | 10:19 | SELL | 0.4818 | Y |
| 2025-03-19 | 10:17 | BUY | 0.462 | Y |
| 2025-04-22 | 10:24 | BUY | 0.462 | Y |
| 2025-11-13 | 10:24 | BUY | 0.462 | Y |
| 2025-11-19 | 10:07 | BUY | 0.462 | Y |
| 2025-01-13 | 10:13 | BUY | 0.4097 | Y |
| 2025-06-13 | 10:24 | BUY | 0.4097 | Y |
| 2025-08-11 | 10:24 | BUY | 0.4097 | Y |

### Loss autopsy (test tickets)

- losses=10 wins=26
- mean p loss/win: 0.5458 / 0.5212
- mean or_ext loss/win: 0.0382 / 0.0664
- by side losses: `{"BUY": 7, "SELL": 3}`

## Profile `V2_WIDE`

- Gates: `{"min_or_width": 14.0, "max_noise_vs_sl": 1.75, "min_future_bars": 5, "min_entry_mins": 585, "max_entry_mins": 870, "max_or_ext": 0.4, "require_first_break": true, "require_body_align": false, "forbid_both_sides": true}`
- Train n=324 · Test n=67 · train100 rules=0 · oos100 rules=0

### Heads

- **BUY**: n_train=164 fit_auc=0.66 calib_auc=0.76 flip=True
- **SELL**: n_train=160 fit_auc=0.655 calib_auc=0.542 flip=False

### Fixed test books (day-unique)

| Book | N | Hit% |
|---|---:|---:|
| `ALL_DU` | 67 | 62.69 |
| `CHAMP_P55` | 41 | 60.98 |
| `CHAMP_P58` | 29 | 55.17 |
| `CHAMP_P60` | 25 | 52.0 |
| `CHAMP_P62` | 13 | 46.15 |
| `BUY_P55` | 25 | 60.0 |
| `SELL_P55` | 16 | 62.5 |

### Test slices

| Slice | N | Hit% |
|---|---:|---:|
| `ALL_day_unique` | 67 | 62.69 |
| `ALL_tickets` | 67 | 62.69 |
| `BUY_day_unique` | 34 | 55.88 |
| `SELL_day_unique` | 33 | 69.7 |
| `FB_P52_day_unique` | 45 | 62.22 |
| `FB_P55_day_unique` | 41 | 60.98 |
| `FB_P57_day_unique` | 29 | 55.17 |
| `FB_P60_day_unique` | 25 | 52.0 |
| `FB_P62_day_unique` | 13 | 46.15 |
| `FB_P65_day_unique` | 7 | 42.86 |
| `FB_P70_day_unique` | 0 | 0.0 |
| `clock_10:00-10:30` | 23 | 65.22 |
| `clock_10:30-11:30` | 9 | 77.78 |
| `clock_11:30-13:00` | 5 | 60.0 |
| `clock_13:00-14:30` | 1 | 100.0 |
| `or_ext<=0.1` | 56 | 60.71 |
| `or_ext<=0.15` | 60 | 63.33 |
| `or_ext<=0.2` | 63 | 65.08 |
| `or_ext<=0.3` | 66 | 63.64 |

### Monthly (day-unique)

| Month | N | Hit% |
|---|---:|---:|
| `2025-01` | 5 | 100.0 |
| `2025-02` | 6 | 50.0 |
| `2025-03` | 5 | 100.0 |
| `2025-04` | 4 | 75.0 |
| `2025-05` | 5 | 80.0 |
| `2025-06` | 3 | 66.67 |
| `2025-07` | 9 | 66.67 |
| `2025-08` | 8 | 25.0 |
| `2025-09` | 6 | 50.0 |
| `2025-10` | 3 | 66.67 |
| `2025-11` | 7 | 57.14 |
| `2025-12` | 6 | 50.0 |

### Best train→test **100%** rule

_No filter with train=100% also hit 100% on test with ≥1 call._

### Top mined rules (train 100% → test)

| # | Side | p≥ | ext≤ | OR≥ | clock | Test n | Test hit% | Train n |
|---:|---|---:|---:|---:|---|---:|---:|---:|

### Oracle test ceiling (in-sample — do not promote)

- n=42 hit=100.0% · `IN_SAMPLE_CEILING_not_for_promote`

| Day | HM | Side | p | Win |
|---|---|---|---:|:---:|
| 2025-03-11 | 09:48 | BUY | 0.6815 | Y |
| 2025-03-27 | 09:53 | BUY | 0.6779 | Y |
| 2025-05-05 | 09:53 | BUY | 0.6621 | Y |
| 2025-01-13 | 10:13 | BUY | 0.6337 | Y |
| 2025-06-13 | 10:24 | BUY | 0.6337 | Y |
| 2025-05-30 | 10:15 | SELL | 0.6246 | Y |
| 2025-02-01 | 11:18 | BUY | 0.6179 | Y |
| 2025-08-11 | 10:24 | BUY | 0.6141 | Y |
| 2025-02-17 | 10:36 | BUY | 0.6102 | Y |
| 2025-03-07 | 10:08 | BUY | 0.6102 | Y |
| 2025-06-16 | 10:28 | BUY | 0.6102 | Y |
| 2025-05-06 | 09:53 | SELL | 0.6101 | Y |
| 2025-07-31 | 11:01 | BUY | 0.6063 | Y |
| 2025-07-03 | 09:59 | BUY | 0.5975 | Y |
| 2025-01-24 | 09:50 | SELL | 0.5872 | Y |
| 2025-11-06 | 10:09 | SELL | 0.5872 | Y |
| 2025-04-08 | 09:55 | SELL | 0.5794 | Y |
| 2025-03-19 | 10:17 | BUY | 0.5765 | Y |
| 2025-01-17 | 10:49 | SELL | 0.5723 | Y |
| 2025-03-13 | 11:37 | SELL | 0.5723 | Y |
| 2025-04-04 | 09:50 | SELL | 0.5723 | Y |
| 2025-07-15 | 10:38 | BUY | 0.5716 | Y |
| 2025-02-11 | 09:55 | SELL | 0.5645 | Y |
| 2025-09-11 | 12:32 | BUY | 0.555 | Y |
| 2025-07-25 | 10:14 | SELL | 0.5534 | Y |
| 2025-12-02 | 09:49 | SELL | 0.5409 | Y |
| 2025-10-24 | 10:19 | SELL | 0.5256 | Y |
| 2025-01-16 | 09:45 | SELL | 0.5229 | Y |
| 2025-05-19 | 14:00 | SELL | 0.5188 | Y |
| 2025-11-13 | 10:24 | BUY | 0.5121 | Y |
| 2025-11-19 | 10:07 | BUY | 0.5121 | Y |
| 2025-08-07 | 10:28 | SELL | 0.5113 | Y |
| 2025-10-21 | 14:30 | SELL | 0.5062 | Y |
| 2025-09-18 | 12:37 | SELL | 0.4909 | Y |
| 2025-04-22 | 10:24 | BUY | 0.4902 | Y |
| 2025-11-18 | 09:49 | SELL | 0.4796 | Y |
| 2025-01-09 | 10:46 | SELL | 0.4717 | Y |
| 2025-07-30 | 10:28 | SELL | 0.4717 | Y |
| 2025-07-24 | 09:48 | SELL | 0.444 | Y |
| 2025-12-29 | 09:58 | SELL | 0.4402 | Y |
| 2025-09-12 | 10:53 | BUY | 0.4185 | Y |
| 2025-12-01 | 09:59 | SELL | 0.4031 | Y |

### Loss autopsy (test tickets)

- losses=25 wins=42
- mean p loss/win: 0.5737 / 0.5558
- mean or_ext loss/win: 0.0702 / 0.0601
- by side losses: `{"BUY": 15, "SELL": 10}`

## Pass 2 — deeper hunt (non-p filters, H1/H2, OOS-100 max)

Model `p_t1` is **anti-ranked** on 2025 V2 (loss mean p 0.55 > win mean p 0.52). Raising p floors **hurts**.

| Finding | Result |
|---|---|
| V2_STRICT full-year DU | **34 @ 70.59%** |
| V2_STRICT **H1 2025** (Jan–Jun) | **11 @ 100%** |
| V2_STRICT H2 2025 (Jul–Dec) | 23 @ 56.52% |
| V2_STRICT SELL-only DU | 13 @ 76.92% |
| Honest train→test 100% (V2, min train n=3) | max test **n=1** |
| Honest train→test 100% (WIDE) | max test **n=2** (SELL · 10:30–12:00 · p≥0.52 · ext≤0.20) |
| In-sample oracle ceiling (V2) | 24 @ 100% — **not for promote** |

### H1 2025 perfect book (observed streak — regime, not a pre-frozen rule)

| Day | HM | Side | p | or_ext | Win |
|---|---|---|---:|---:|:---:|
| 2025-01-09 | 10:46 | SELL | 0.6518 | 0.016 | Y |
| 2025-01-13 | 10:13 | BUY | 0.3755 | 0.030 | Y |
| 2025-02-01 | 11:18 | BUY | 0.4681 | 0.016 | Y |
| 2025-03-07 | 10:08 | BUY | 0.4892 | 0.141 | Y |
| 2025-03-13 | 11:37 | SELL | 0.5431 | 0.113 | Y |
| 2025-03-19 | 10:17 | BUY | 0.4491 | 0.021 | Y |
| 2025-04-22 | 10:24 | BUY | 0.4491 | 0.013 | Y |
| 2025-05-19 | 14:00 | SELL | 0.6661 | 0.129 | Y |
| 2025-05-30 | 10:15 | SELL | 0.6576 | 0.030 | Y |
| 2025-06-13 | 10:24 | BUY | 0.3755 | 0.038 | Y |
| 2025-06-16 | 10:28 | BUY | 0.4892 | 0.096 | Y |

H2 losses cluster Jul–Sep / Dec — same V2 gates, accuracy collapses.

## Research pick

**Best honest full-year gate performance:** `V2_STRICT` · **34 calls · 70.59%** (day-unique, ±30).

**Multi-call 100%:** only as an **H1-2025 observed streak (11 @ 100%)**, not as a train-frozen filter that also clears H2. Full-year train→test 100% books top out at **n=1–2** — too thin to promote.

**Blockers to full-year 100% with many calls:** (1) dual-head `p` inverted on 2025, (2) regime break after Jun-2025, (3) V2 already very selective (~34 test tickets).

**Next research (not live):** regime detector (trade V2 only in H1-like tape), drop/`invert` p gate, add OC/PCR features, or widen labels — then re-freeze and re-test.

## Policy

- Research only · `not_live=true`
- Do not wire into live_session / fno_ws_rescore without a separate promote plan.
