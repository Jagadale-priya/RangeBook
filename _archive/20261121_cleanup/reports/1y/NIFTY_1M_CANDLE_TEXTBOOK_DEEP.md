# NIFTY 1m — **textbook candlestick deep research** (5y, every bar)

**Not live.** Rules from online candlestick docs; every detection re-verified.

## Sources

- https://raw.githubusercontent.com/cm45t3r/candlestick/master/docs/PATTERNS.md
- https://chartschool.stockcharts.com/table-of-contents/chart-analysis/candlestick-charts/candlestick-pattern-dictionary
- https://ta-lib.github.io/ta-lib-python/func_groups/pattern_recognition.html

- Tape: `2021-01-01` → `2025-12-30` · Analyze≤`2023-12-31` · Test≥`2024-07-01`
- Bars: **461926** · Pattern coverage: **94.02%**

## Pattern ID integrity (textbook re-check): **100.0%**

- Checked 5221 random hits · passed 5221

| Pattern | Count (5y) | Checked | Pass% |
|---|---:|---:|---:|
| `doji` | 39711 | 100 | **100.0** |
| `dragonfly_doji` | 3150 | 100 | **100.0** |
| `gravestone_doji` | 3168 | 100 | **100.0** |
| `long_legged_doji` | 17453 | 100 | **100.0** |
| `marubozu` | 42493 | 100 | **100.0** |
| `marubozu_bull` | 21393 | 100 | **100.0** |
| `marubozu_bear` | 21100 | 100 | **100.0** |
| `spinning_top` | 69597 | 100 | **100.0** |
| `high_wave` | 17281 | 100 | **100.0** |
| `hammer` | 11459 | 100 | **100.0** |
| `hanging_man` | 10982 | 100 | **100.0** |
| `inv_hammer` | 10109 | 100 | **100.0** |
| `shooting_star` | 4807 | 100 | **100.0** |
| `belt_bull` | 34856 | 100 | **100.0** |
| `belt_bear` | 32235 | 100 | **100.0** |
| `long_line` | 122664 | 100 | **100.0** |
| `short_line` | 40774 | 100 | **100.0** |
| `bull_engulf` | 26231 | 100 | **100.0** |
| `bear_engulf` | 24512 | 100 | **100.0** |
| `bull_harami` | 25886 | 100 | **100.0** |
| `bear_harami` | 27924 | 100 | **100.0** |
| `harami_cross` | 9445 | 100 | **100.0** |
| `piercing` | 1736 | 100 | **100.0** |
| `dark_cloud` | 1523 | 100 | **100.0** |
| `tweezer_bot` | 1875 | 100 | **100.0** |
| `tweezer_top` | 1829 | 100 | **100.0** |
| `bull_kicker` | 4164 | 100 | **100.0** |
| `bear_kicker` | 4228 | 100 | **100.0** |
| `matching_low` | 922 | 100 | **100.0** |
| `inside_bar` | 60544 | 100 | **100.0** |
| `outside_bar` | 43323 | 100 | **100.0** |
| `sep_lines_bull` | 1005 | 100 | **100.0** |
| `sep_lines_bear` | 1070 | 100 | **100.0** |
| `counterattack` | 5 | 5 | **100.0** |
| `morning_star` | 1162 | 100 | **100.0** |
| `evening_star` | 1055 | 100 | **100.0** |
| `morning_doji_star` | 544 | 100 | **100.0** |
| `evening_doji_star` | 504 | 100 | **100.0** |
| `three_soldiers` | 1208 | 100 | **100.0** |
| `three_crows` | 1120 | 100 | **100.0** |
| `three_inside_up` | 7622 | 100 | **100.0** |
| `three_inside_dn` | 7911 | 100 | **100.0** |
| `three_outside_up` | 12966 | 100 | **100.0** |
| `three_outside_dn` | 11977 | 100 | **100.0** |
| `tri_star_bull` | 183 | 100 | **100.0** |
| `tri_star_bear` | 172 | 100 | **100.0** |
| `stick_sandwich` | 625 | 100 | **100.0** |
| `abandoned_baby_bull` | 7 | 7 | **100.0** |
| `abandoned_baby_bear` | 9 | 9 | **100.0** |
| `rising_3_methods` | 2855 | 100 | **100.0** |
| `falling_3_methods` | 2482 | 100 | **100.0** |
| `bull_run2` | 117631 | 100 | **100.0** |
| `bear_run2` | 115554 | 100 | **100.0** |
| `bull_run3` | 59174 | 100 | **100.0** |
| `bear_run3` | 57795 | 100 | **100.0** |

## 5y census (top patterns)

| Pattern | Count |
|---|---:|
| `long_line` | 122664 |
| `bull_run2` | 117631 |
| `bear_run2` | 115554 |
| `spinning_top` | 69597 |
| `inside_bar` | 60544 |
| `bull_run3` | 59174 |
| `bear_run3` | 57795 |
| `outside_bar` | 43323 |
| `marubozu` | 42493 |
| `short_line` | 40774 |
| `doji` | 39711 |
| `belt_bull` | 34856 |
| `belt_bear` | 32235 |
| `bear_harami` | 27924 |
| `bull_engulf` | 26231 |
| `bull_harami` | 25886 |
| `bear_engulf` | 24512 |
| `marubozu_bull` | 21393 |
| `marubozu_bear` | 21100 |
| `long_legged_doji` | 17453 |
| `high_wave` | 17281 |
| `three_outside_up` | 12966 |
| `three_outside_dn` | 11977 |
| `hammer` | 11459 |
| `hanging_man` | 10982 |
| `inv_hammer` | 10109 |
| `harami_cross` | 9445 |
| `three_inside_dn` | 7911 |
| `three_inside_up` | 7622 |
| `shooting_star` | 4807 |

## Formation examples (how pattern builds)

### `bear_engulf` · 2021-01-01 10:00 · SELL

| Role | HM | O | H | L | C | body_frac |
|---|---|---:|---:|---:|---:|---:|
| lead | 09:58 | 14031.1 | 14032.3 | 14029.1 | 14032.3 | 0.375 |
| star/mid | 09:59 | 14032.35 | 14033.3 | 14031.1 | 14032.4 | 0.023 |
| confirm | 10:00 | 14032.5 | 14033.2 | 14026.8 | 14026.8 | 0.891 |

### `morning_star` · 2021-01-04 10:14 · BUY

| Role | HM | O | H | L | C | body_frac |
|---|---|---:|---:|---:|---:|---:|
| lead | 10:12 | 14088.55 | 14088.9 | 14080.35 | 14083.35 | 0.608 |
| star/mid | 10:13 | 14082.75 | 14087.15 | 14082.2 | 14083.15 | 0.081 |
| confirm | 10:14 | 14083.55 | 14086.55 | 14081.65 | 14086.55 | 0.612 |

### `hammer` · 2021-01-05 10:18 · BUY

| Role | HM | O | H | L | C | body_frac |
|---|---|---:|---:|---:|---:|---:|
| lead | 10:16 | 14064.25 | 14065.5 | 14061.8 | 14061.8 | 0.662 |
| star/mid | 10:17 | 14061.6 | 14061.85 | 14056.75 | 14056.75 | 0.951 |
| confirm | 10:18 | 14057.55 | 14059.45 | 14054.0 | 14059.25 | 0.312 |

### `hammer` · 2021-01-07 10:00 · BUY

| Role | HM | O | H | L | C | body_frac |
|---|---|---:|---:|---:|---:|---:|
| lead | 09:58 | 14226.35 | 14229.75 | 14225.9 | 14228.25 | 0.494 |
| star/mid | 09:59 | 14228.75 | 14228.75 | 14223.3 | 14223.45 | 0.972 |
| confirm | 10:00 | 14223.5 | 14223.75 | 14219.85 | 14223.75 | 0.064 |

### `bear_engulf` · 2021-01-08 10:02 · SELL

| Role | HM | O | H | L | C | body_frac |
|---|---|---:|---:|---:|---:|---:|
| lead | 10:00 | 14242.85 | 14244.9 | 14242.1 | 14244.0 | 0.411 |
| star/mid | 10:01 | 14243.8 | 14246.05 | 14242.65 | 14244.5 | 0.206 |
| confirm | 10:02 | 14245.45 | 14245.45 | 14240.35 | 14241.15 | 0.843 |

### `bear_engulf` · 2021-01-11 10:03 · SELL

| Role | HM | O | H | L | C | body_frac |
|---|---|---:|---:|---:|---:|---:|
| lead | 10:01 | 14467.75 | 14470.45 | 14463.7 | 14464.1 | 0.541 |
| star/mid | 10:02 | 14464.55 | 14467.35 | 14461.7 | 14466.7 | 0.381 |
| confirm | 10:03 | 14467.1 | 14467.15 | 14464.3 | 14464.55 | 0.895 |

### `bear_engulf` · 2021-01-12 10:01 · SELL

| Role | HM | O | H | L | C | body_frac |
|---|---|---:|---:|---:|---:|---:|
| lead | 09:59 | 14468.7 | 14473.05 | 14466.95 | 14471.9 | 0.525 |
| star/mid | 10:00 | 14472.7 | 14476.15 | 14469.25 | 14475.9 | 0.464 |
| confirm | 10:01 | 14476.1 | 14479.35 | 14471.6 | 14471.6 | 0.581 |

### `bull_engulf` · 2021-01-13 10:08 · BUY

| Role | HM | O | H | L | C | body_frac |
|---|---|---:|---:|---:|---:|---:|
| lead | 10:06 | 14633.0 | 14633.95 | 14630.35 | 14631.55 | 0.403 |
| star/mid | 10:07 | 14630.5 | 14632.3 | 14628.4 | 14630.05 | 0.115 |
| confirm | 10:08 | 14628.75 | 14632.05 | 14627.5 | 14631.0 | 0.495 |

## Both-window 100% logics: **0** · Union **0 @ 0.0%**

## Best both-100

| # | Bracket | Filters | Ana | Test |
|---:|---|---|---:|---:|

## Research pick

No both-100 — pattern ID is complete; tighten trade gates further.

## Policy

- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_candle_textbook_deep`
- research_only · not_live · textbook candle deep

## Refined trade hunt (RSI + textbook patterns)

- Both-100 logics: **0** · Union **0 @ 0.0%**
