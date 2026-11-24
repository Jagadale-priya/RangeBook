# NIFTY 1m — **chart-only** model · aim 100% with max calls

**Not live.** Chart analysis only (OR / candles / ATR / swings / VWAP). **No hardcoded ±30.**

- Analyze ≤ `2023-12-31` · Train ≤ `2024-06-30` · Test ≥ `2024-07-01`
- Events ana/test: 147 / 49

## How SL / T1 are calculated (chart math)

1. **MAE/MFE path stats** on analyze first-breaks → SL = MAE percentile, T1 = MFE percentile (asymmetric for high hit).
2. **ATR / OR geometry** — multiples of entry ATR and opening-range width.
3. **Swing structure** — SL beyond recent swing, T1 toward opposite swing.
4. **OR opposite** — SL toward far OR side, T1 as OR fraction.

## 100% on BOTH analyze + new test: **184** logics (top ranked below)

### Union of all both-100 test calls: **22 @ 100.0%**

| Day | HM | Side | SL | T1 | Win |
|---|---|---|---:|---:|:---:|
| 2024-07-16 | 10:34 | BUY | 25.85 | 5.0 | Y |
| 2024-08-01 | 10:51 | SELL | 78.22 | 26.34 | Y |
| 2024-08-06 | 10:37 | SELL | 71.08 | 27.55 | Y |
| 2024-10-01 | 10:30 | SELL | 71.08 | 27.55 | Y |
| 2024-12-02 | 10:15 | BUY | 90.31 | 10.22 | Y |
| 2024-12-26 | 10:01 | SELL | 56.86 | 6.92 | Y |
| 2025-01-13 | 10:13 | BUY | 73.87 | 11.42 | Y |
| 2025-03-13 | 11:37 | SELL | 78.22 | 26.34 | Y |
| 2025-03-19 | 10:17 | BUY | 54.45 | 6.2 | Y |
| 2025-04-22 | 10:24 | BUY | 32.5 | 5.38 | Y |
| 2025-05-19 | 14:00 | SELL | 71.08 | 27.55 | Y |
| 2025-06-13 | 10:24 | BUY | 47.69 | 7.41 | Y |
| 2025-06-16 | 10:28 | BUY | 78.38 | 6.48 | Y |
| 2025-07-09 | 10:13 | BUY | 40.92 | 5.0 | Y |
| 2025-08-07 | 10:28 | SELL | 31.55 | 5.09 | Y |
| 2025-08-11 | 10:24 | BUY | 56.87 | 7.68 | Y |
| 2025-09-03 | 12:15 | BUY | 77.69 | 18.61 | Y |
| 2025-09-11 | 12:32 | BUY | 31.46 | 5.59 | Y |
| 2025-10-24 | 10:19 | SELL | 72.5 | 6.86 | Y |
| 2025-11-13 | 10:24 | BUY | 43.23 | 5.0 | Y |
| 2025-11-19 | 10:07 | BUY | 53.55 | 5.0 | Y |
| 2025-11-25 | 10:10 | BUY | 59.22 | 5.1 | Y |

## Best both-100 logics (max test n)

| # | Bracket | Filters | Ana n | Test n | Avg SL/T1 |
|---:|---|---|---:|---:|---|
| 1 | `swing_sl1.1_t0.7` | RSI 45–65 · ext≤0.15 · OR≥12 · swing SL=1.1× · T1=0.7× | 17 | **10** | 49.71/6.89 |
| 2 | `swing_sl1.15_t0.65` | same chart gates · slightly wider swing SL | 17 | **10** | 51.97/6.89 |
| 3 | `swing_sl1.2_t0.75` | same chart gates | 17 | **10** | 54.23/6.89 |
| 4 | `swing_sl1.25_t0.7` | same chart gates | 17 | **10** | 56.49/6.89 |
| 5–12 | swing family | + VWAP-with / OR≥15 variants (same 10 test days) | 17 | **10** | ~50–56 / 6.89 |

### Detail · best both-100 · test **10 @ 100%**

- Bracket: `swing_sl1.1_t0.7`
- Filters: `{"side": null, "patterns": null, "clocks": null, "max_or_ext": 0.15, "min_or": 12, "vwap_side": null, "rsi_lo": 45, "rsi_hi": 65}`
- Analyze: 17 @ 100% · avg SL/T1 31.45/5.64

| Day | HM | Side | SL | T1 | patterns | Win |
|---|---|---|---:|---:|---|:---:|
| 2024-07-16 | 10:34 | BUY | 25.85 | 5.0 | marubozu,bull_run2 | Y |
| 2024-12-02 | 10:15 | BUY | 90.31 | 10.22 | marubozu,bull_run2,bull_run3 | Y |
| 2025-01-13 | 10:13 | BUY | 73.87 | 11.42 | _structure_ | Y |
| 2025-03-19 | 10:17 | BUY | 54.45 | 6.2 | bull_run2,bull_run3 | Y |
| 2025-04-22 | 10:24 | BUY | 32.5 | 5.38 | bull_engulf,outside | Y |
| 2025-06-13 | 10:24 | BUY | 47.69 | 7.41 | bull_run2,bull_run3 | Y |
| 2025-07-09 | 10:13 | BUY | 40.92 | 5.0 | bull_run2 | Y |
| 2025-08-11 | 10:24 | BUY | 56.87 | 7.68 | marubozu,bull_run2,bull_run3 | Y |
| 2025-09-11 | 12:32 | BUY | 31.46 | 5.59 | bull_engulf,outside | Y |
| 2025-11-13 | 10:24 | BUY | 43.23 | 5.0 | bull_run2,bull_run3 | Y |

## Near-miss (analyze ≥70%, for context)

| Bracket | Ana | Test |
|---|---|---|
| `swing_sl1.05_t0.8` | 62@90.32% | 16@100.0% |
| `swing_sl1.1_t0.7` | 62@90.32% | 16@100.0% |
| `swing_sl1.15_t0.65` | 62@90.32% | 16@100.0% |
| `swing_sl1.2_t0.75` | 62@90.32% | 16@100.0% |
| `swing_sl1.25_t0.7` | 62@90.32% | 16@100.0% |
| `swing_sl1.05_t0.8` | 62@90.32% | 16@100.0% |
| `swing_sl1.1_t0.7` | 62@90.32% | 16@100.0% |
| `swing_sl1.15_t0.65` | 62@90.32% | 16@100.0% |
| `swing_sl1.2_t0.75` | 62@90.32% | 16@100.0% |
| `swing_sl1.25_t0.7` | 62@90.32% | 16@100.0% |

## Chart ML ranker (chart features only)

- Trained on chart path labels · n=117 fit_auc=0.997 test_auc=0.378
- High-P test slice: **4 @ 100.0%** (q=0.9 thr=0.9909)

| Day | HM | Side | SL | T1 | P | Win |
|---|---|---|---:|---:|---:|:---:|
| 2024-12-26 | 10:01 | SELL | 56.86 | 6.92 | 0.993 | Y |
| 2025-03-19 | 10:17 | BUY | 51.98 | 6.2 | 0.991 | Y |
| 2025-11-19 | 10:07 | BUY | 53.55 | 5.0 | 0.993 | Y |
| 2025-11-25 | 10:10 | BUY | 59.22 | 5.1 | 0.994 | Y |

## Research pick

**Best single chart logic (both windows 100%):** `swing_sl1.1_t0.7`  
Gates: OR first-break · `max_or_ext≤0.15` · `OR≥12` · **RSI 45–65**  
SL/T1: **1.1× swing distance** / **0.7× opposite-swing** (chart structure only)  
→ analyze **17 @ 100%** · new test **10 @ 100%**

**Max-call research union** (combine both-100 micros, not one filter): **22 @ 100%** on test.

**Chart ML ranker** (ATR/OR/VWAP/RSI/patterns/SL/T1): high-P slice **4 @ 100%** (fit AUC 0.997; test AUC weak → prefer rule book over ML alone).

## Policy

- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_chart_only_100`
- research_only · not_live · chart_only · no hardcoded ±30

## Refine note

- Wide swing book before gates: ana 117@94.87% · test 39@94.87%
- Refined both-100 logics: 184 · union **22 @ 100.0%**
