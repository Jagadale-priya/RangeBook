# NIFTY 1m — VIX + candle patterns + **adaptive** SL/T1

**Not live. SL/T1 are not hardcoded ±30 — learned from MAE/MFE + ATR/OR + VIX.**

- Analyze: `2023-12-31` and before · Test: `2024-01-01` → `2025-12-30`
- India VIX: prior-day close from `IDX_INDIAVIX.csv` (no look-ahead)
- Events analyze/test: 147 / 72

## VIX regime mix (analyze events)

`{"ELEVATED": 47, "HIGH": 17, "UNK": 2, "NORMAL": 31, "LOW": 50}`

## Adaptive brackets (examples learned on analyze)

| Recipe key | N | SL | T1 | R:R | MAE p60 | MFE p55 |
|---|---:|---:|---:|---:|---:|---:|
| `*|BUY|*` | 74 | 31.89 | 30.92 | 0.97 | 31.89 | 30.92 |
| `*|SELL|*` | 73 | 41.55 | 35.32 | 0.85 | 41.55 | 34.61 |
| `bull_run2|BUY|*` | 63 | 31.57 | 29.39 | 0.931 | 31.57 | 29.39 |
| `bear_run2|SELL|*` | 59 | 43.87 | 37.29 | 0.85 | 43.87 | 33.66 |
| `bear_run3|SELL|*` | 47 | 43.84 | 37.26 | 0.85 | 43.84 | 35.01 |
| `bull_run3|BUY|*` | 40 | 34.05 | 29.88 | 0.878 | 34.05 | 29.88 |
| `marubozu|SELL|*` | 38 | 41.55 | 44.78 | 1.078 | 41.55 | 44.78 |
| `marubozu|BUY|*` | 37 | 26.36 | 40.08 | 1.52 | 26.36 | 40.08 |
| `*|BUY|LOW` | 27 | 31.36 | 26.66 | 0.85 | 31.36 | 23.89 |
| `*|SELL|ELEVATED` | 24 | 43.51 | 46.09 | 1.059 | 43.51 | 46.09 |
| `bull_run2|BUY|LOW` | 24 | 29.5 | 25.07 | 0.85 | 29.5 | 22.94 |
| `*|BUY|ELEVATED` | 23 | 41.95 | 35.66 | 0.85 | 41.95 | 32.46 |
| `*|SELL|LOW` | 23 | 41.91 | 35.62 | 0.85 | 41.91 | 26.73 |
| `bear_run2|SELL|ELEVATED` | 21 | 43.9 | 42.6 | 0.97 | 43.9 | 42.6 |

## Winner (best calls × accuracy — must also work on analyze)

Selection rule: analyze hit ≥55% & n≥15, then maximize **test hit**, then **test n**.  
(Rejects thin “lucky” test books that failed in 2021–2023.)

### Best balanced (accuracy + enough calls)

**`learned_mae_mfe` · SELL · VIX=NORMAL · adaptive MAE/MFE brackets**
- Analyze: **17 @ 64.7%** · avg SL/T1 ≈ **36 / 35** (from path stats, not ±30)
- **Test 2024–25: 14 @ 71.4%**

### Best volume × accuracy

**`learned_mae_mfe` · patterns={marubozu, bear_engulf} · VIX∈{LOW,NORMAL}**
- Analyze: **36 @ 55.6%**
- **Test: 24 @ 66.7%** · avg SL/T1 ≈ **35.5 / 35.3**

### High-volume runner-up

**`or_15_25`** (SL=15% OR width, T1=25% OR width, VIX-scaled) → test **25 @ 68%** (analyze ~53%)

### Note on a thin 90% book (not chosen)

`vix_scaled_atr` + SELL marubozu morning hit **11 @ 90.9%** on test but only **42%** on analyze — **not promote** (test luck).

## Top logics by test hit (n≥5, analyze hit≥55)

| # | Name | Filters (short) | Ana n/hit | Test n/hit | Avg SL/T1 |
|---:|---|---|---|---|---|
| 1 | `learned_mae_mfe` | side=SELL vix=['NORMAL'] pats=None clk=None | 17@64.71% | **14@71.43%** | 36.33/34.89 |
| 2 | `learned_mae_mfe` | side=SELL vix=['NORMAL'] pats=None clk=None | 17@64.71% | **14@71.43%** | 36.33/34.89 |
| 3 | `learned_mae_mfe` | side=SELL vix=['NORMAL'] pats=None clk=None | 17@64.71% | **14@71.43%** | 36.33/34.89 |
| 4 | `learned_mae_mfe` | side=SELL vix=['NORMAL', 'ELEVATED'] pats=None clk=['morning'] | 37@56.76% | **13@69.23%** | 36.95/35.61 |
| 5 | `learned_mae_mfe` | side=SELL vix=['NORMAL', 'ELEVATED'] pats=None clk=['morning'] | 37@56.76% | **13@69.23%** | 36.95/35.61 |
| 6 | `learned_mae_mfe` | side=SELL vix=['NORMAL', 'ELEVATED'] pats=None clk=['morning'] | 37@56.76% | **13@69.23%** | 36.95/35.61 |
| 7 | `learned_mae_mfe` | side=SELL vix=['NORMAL'] pats=None clk=None | 17@64.71% | **13@69.23%** | 36.43/35.29 |
| 8 | `learned_mae_mfe` | side=SELL vix=['NORMAL'] pats=None clk=None | 17@64.71% | **13@69.23%** | 36.43/35.29 |
| 9 | `learned_mae_mfe` | side=SELL vix=['NORMAL'] pats=None clk=None | 17@64.71% | **13@69.23%** | 36.43/35.29 |
| 10 | `learned_mae_mfe` | side=SELL vix=['NORMAL'] pats=None clk=['morning', 'midday'] | 17@64.71% | **13@69.23%** | 36.43/35.29 |
| 11 | `learned_mae_mfe` | side=SELL vix=['NORMAL'] pats=None clk=['morning', 'midday'] | 17@64.71% | **13@69.23%** | 36.43/35.29 |
| 12 | `learned_mae_mfe` | side=SELL vix=['NORMAL'] pats=None clk=['morning', 'midday'] | 17@64.71% | **13@69.23%** | 36.43/35.29 |
| 13 | `learned_mae_mfe` | side=None vix=['LOW', 'NORMAL'] pats=['marubozu', 'bear_engulf'] clk=None | 36@55.56% | **24@66.67%** | 35.52/35.28 |
| 14 | `learned_mae_mfe` | side=None vix=['LOW', 'NORMAL'] pats=['marubozu', 'bear_engulf'] clk=None | 36@55.56% | **24@66.67%** | 35.52/35.28 |
| 15 | `learned_mae_mfe` | side=None vix=['LOW', 'NORMAL'] pats=['marubozu', 'bear_engulf'] clk=None | 36@55.56% | **24@66.67%** | 35.52/35.28 |

## High-volume candidates (test n≥15)

| # | Name | Test n/hit | Ana n/hit |
|---:|---|---|---|
| 1 | `learned_mae_mfe` | **22@68.18%** | 35@54.29% |
| 2 | `learned_mae_mfe` | **22@68.18%** | 35@54.29% |
| 3 | `learned_mae_mfe` | **22@68.18%** | 35@54.29% |
| 4 | `learned_mae_mfe` | **22@68.18%** | 35@54.29% |
| 5 | `learned_mae_mfe` | **22@68.18%** | 35@54.29% |
| 6 | `learned_mae_mfe` | **22@68.18%** | 35@54.29% |
| 7 | `or_15_25` | **25@68.0%** | 74@52.7% |
| 8 | `or_15_25` | **25@68.0%** | 73@52.05% |
| 9 | `learned_mae_mfe` | **25@68.0%** | 35@54.29% |
| 10 | `learned_mae_mfe` | **25@68.0%** | 35@54.29% |

## How SL/T1 are set (not hardcoded)

1. On analyze events, measure MAE (adverse) and MFE (favorable) path from entry.
2. Per pattern × side × VIX regime: SL ≈ MAE p60, T1 ≈ MFE p55, floored by ATR/OR medians.
3. At live event: pick most specific learned recipe; widen/narrow slightly by VIX regime.
4. Alternate families (ATR/OR multiples, VIX-scaled ATR) competed in the hunt — same adaptive idea.

## Policy

- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_vix_candle_adaptive`
- research_only · not_live
