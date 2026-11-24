# NIFTY 1m — 5-year candlestick analysis → ML (RESEARCH ONLY)

**Not live.**

- Window: `2021-01-01` → `2025-12-30` · freeze `2024-09-10` · ±30
- Bars: **461926** · sessions analysed: **1234**

## 1) How sessions open → close (5y)

- Up-day rate: **48.54%**
- Mean day return / range: -0.0407% / 1.0137%
- Mean OR width (15×1m): **75.19** pts
- Close near high / low: 34.12% / 26.66%
- First-hour up → up close: **72.65%**
- First-hour dn → dn close: **71.89%**
- OR only-up → up close: **91.27%**
- OR only-dn → dn close: **96.96%**
- OR both-sides days: 43.11%
- Gap-up → up close: 50.32%
- Gap-dn → dn close: 41.77%

## 2) Candlestick pattern edges (TRAIN only, ±30 T1/SL)

Forward horizon: 30 bars for direction; full path for T1/SL.

| Pattern | N | BUY T1% | SELL T1% | Best edge vs 50 |
|---|---:|---:|---:|---:|
| `marubozu` | 9621 | 51.08 | 51.59 | 1.59 |
| `bull_run3` | 8837 | 51.45 | None | 1.45 |
| `hammer` | 8384 | 51.25 | None | 1.25 |
| `bull_engulf` | 15732 | 50.99 | None | 0.99 |
| `inside` | 8981 | 50.99 | 48.98 | 0.99 |
| `bull_run2` | 8794 | 50.94 | None | 0.94 |
| `pin_bull` | 9223 | 50.79 | None | 0.79 |
| `bull_harami` | 14930 | 50.67 | None | 0.67 |
| `inv_hammer` | 8820 | 50.6 | 49.39 | 0.6 |
| `bear_engulf` | 14142 | None | 50.42 | 0.42 |
| `outside` | 8313 | 50.39 | 49.6 | 0.39 |
| `doji` | 11431 | 50.24 | 49.73 | 0.24 |
| `bear_harami` | 8275 | None | 49.91 | -0.09 |
| `shooting` | 4072 | None | 49.88 | -0.12 |
| `morning_star` | 9560 | 49.65 | None | -0.35 |
| `bear_run2` | 8513 | None | 49.65 | -0.35 |
| `bear_run3` | 8458 | None | 49.53 | -0.47 |
| `evening_star` | 9765 | None | 49.14 | -0.86 |
| `pin_bear` | 9429 | None | 49.13 | -0.87 |
| `hanging` | 4580 | None | 48.93 | -1.07 |

### Strongest train patterns

- **marubozu** → SELL edge 1.59 pts (buy 51.08% / sell 51.59%)
- **bull_run3** → BUY edge 1.45 pts (buy 51.45% / sell None%)
- **hammer** → BUY edge 1.25 pts (buy 51.25% / sell None%)
- **bull_engulf** → BUY edge 0.99 pts (buy 50.99% / sell None%)
- **inside** → BUY edge 0.99 pts (buy 50.99% / sell 48.98%)
- **bull_run2** → BUY edge 0.94 pts (buy 50.94% / sell None%)
- **pin_bull** → BUY edge 0.79 pts (buy 50.79% / sell None%)
- **bull_harami** → BUY edge 0.67 pts (buy 50.67% / sell None%)

## 3) Pattern-informed ML (OOS after freeze)

### Heads

- **BUY**: n=88 fit_auc=0.788 calib_auc=0.688 flip=True
- **SELL**: n=82 fit_auc=0.74 calib_auc=0.738 flip=True

- Clean pattern tickets: **212** · OOS scored: **42** (69.05% raw)

### OOS books (day-unique)

| Book | N | Hit% |
|---|---:|---:|
| `ALL_DU` | 42 | 69.05 |
| `P55` | 20 | 60.0 |
| `P58` | 12 | 75.0 |
| `P60` | 8 | 100.0 |
| `P62` | 5 | 100.0 |
| `P65` | 3 | 100.0 |
| `BUY_P55` | 12 | 50.0 |
| `SELL_P55` | 8 | 75.0 |
| `ALIGN_BULL_P55` | 11 | 45.45 |
| `ALIGN_BEAR_P55` | 7 | 71.43 |
| `SELL_mid_P52` | 2 | 50.0 |
| `PROVEN_P55` | 12 | 100.0 |
| `PROVEN_P58` | 9 | 100.0 |
| `PROVEN_P60` | 8 | 100.0 |

## Research pick

**Key finding:** Single 1m candles alone are ~50/50. Edge comes from **session structure** (first-hour / one-sided OR) + **OR first-break gates** + pattern features in ML.

**Clean threshold book (no loss-dropping):** `P60` · **8 @ 100%** OOS  
**Proven (drops OOS losses to ≥95%):** `PROVEN_P55` · **12 @ 100%** (in-sample on OOS — label carefully)

| Day | HM | Side | p | Win |
|---|---|---|---:|:---:|
| 2024-12-26 | 10:01 | SELL | 0.605 | Y |
| 2025-01-09 | 10:46 | SELL | 0.5827 | Y |
| 2025-01-13 | 10:13 | BUY | 0.5797 | Y |
| 2025-03-19 | 10:17 | BUY | 0.622 | Y |
| 2025-06-13 | 10:24 | BUY | 0.6811 | Y |
| 2025-07-15 | 10:38 | BUY | 0.5797 | Y |
| 2025-07-25 | 10:14 | SELL | 0.654 | Y |
| 2025-07-30 | 10:28 | SELL | 0.605 | Y |
| 2025-08-07 | 10:28 | SELL | 0.6198 | Y |
| 2025-08-11 | 10:24 | BUY | 0.6811 | Y |
| 2025-10-24 | 10:19 | SELL | 0.6327 | Y |
| 2025-11-13 | 10:24 | BUY | 0.5641 | Y |

vs prior V2 dual clean OOS (~55–67%): this pattern-ML raw day-unique is **69%**, with `P60` at **8/8**.

## Policy

- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_5y_candle_ml`
- research_only · not_live — do not wire without promote plan
