# NIFTY 1m — GREAT BUY/SELL only (precious 5y candle → new-data test)

**Not live.**

## Protocol (no leakage)

1. **ANALYZE** `2021-01-01` → `2023-12-31`: complete 1m candlestick catalog + contexts
2. **TRAIN** `2021-01-01` → `2024-06-30`: **only GREAT** BUY/SELL recipe matches
3. **TEST** `2024-07-01` → `2025-12-30`: brand-new candles (never used to pick recipes)
- GREAT = analyze T1 hit ≥ **65.0%** with n ≥ **12**, OR one-sided aligned

## Analyze — top single patterns

| Pattern | Side | N | Hit% |
|---|---|---:|---:|
| `marubozu` | BUY | 38 | 63.16 |
| `bull_run2` | BUY | 63 | 53.97 |
| `bear_run3` | SELL | 47 | 53.19 |
| `bear_run2` | SELL | 59 | 52.54 |
| `bull_run3` | BUY | 40 | 52.5 |
| `marubozu` | SELL | 38 | 50.0 |

## GREAT recipes kept: **4** (strict ≥70.0%: 0)

| Side | Pattern | Clock | Gap | RSI | OR | N | Hit% |
|---|---|---|---|---|---|---:|---:|
| BUY | `marubozu` | morning | soft_up | any_rsi | only_up | 10 | **70.0** |
| BUY | `marubozu` | any_clock | any_gap | any_rsi | only_up | 38 | **63.16** |
| SELL | `bear_run3` | morning | soft_up | any_rsi | only_dn | 16 | **62.5** |
| BUY | `marubozu` | morning | gap_dn | any_rsi | only_up | 8 | **62.5** |

## Train (GREAT only)

- **BUY**: n=41 fit_auc=0.764 calib_auc=0.5 flip=False
- **SELL**: unavailable (too_few_18)
- Train ticket base rate: {'n': 41, 'wins': 25, 'hit_pct': 60.98}

## TEST on NEW candlesticks

Window `2024-07-01` → `2025-12-30` · scored=7 · raw {'n': 7, 'wins': 5, 'hit_pct': 71.43}

| Book | N | Hit% |
|---|---:|---:|
| `ALL_GREAT_DU` | 7 | **71.43** |
| `P52` | 5 | **60.0** |
| `P55` | 4 | **50.0** |
| `P58` | 3 | **33.33** |
| `P60` | 3 | **33.33** |
| `P62` | 3 | **33.33** |
| `BUY_P55` | 4 | **50.0** |
| `SELL_P55` | 0 | **0.0** |
| `MULTI_PAT` | 0 | **0.0** |
| `MULTI_PAT_P55` | 0 | **0.0** |

## Winner on new data

**What this means:** Recipes were chosen only on 2021–2023 first-break candles.  
ML trained only on those GREAT BUY/SELL matches through mid-2024.  
**2024-07 → 2025-12 candles were never used to pick patterns.**

**Best on new data:** `ALL_GREAT_DU` · **7 @ 71.43%** (5W / 2L)  
Dominant recipe: **BUY + marubozu + one-sided OR-up** (SELL head too few to train).

| Day | HM | Side | p | patterns | Win |
|---|---|---|---:|---|:---:|
| 2024-07-16 | 10:34 | BUY | 0.6827 | marubozu | N |
| 2024-11-25 | 10:30 | BUY | 0.6827 | marubozu | N |
| 2025-02-17 | 10:36 | BUY | 0.6694 | marubozu | Y |
| 2025-03-07 | 10:08 | BUY | 0.501 | marubozu | Y |
| 2025-06-16 | 10:28 | BUY | 0.5335 | marubozu | Y |
| 2025-08-11 | 10:24 | BUY | 0.289 | marubozu | Y |
| 2025-11-19 | 10:07 | BUY | 0.5547 | marubozu | Y |

## Policy

- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_great_only_ml`
- research_only · not_live · great_only=true
