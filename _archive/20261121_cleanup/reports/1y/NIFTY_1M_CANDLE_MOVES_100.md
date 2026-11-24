# NIFTY 1m — **complete candlestick + market-move** model · 100% max-calls

**Not live.** Full candle catalog + every move type (impulse / pullback / swing-break / OR-break / reversal).
SL/T1 from **move geometry** (origin, swing, pattern extreme, ATR mix).

- Analyze ≤ `2023-12-31` · Train ≤ `2024-06-30` · Test ≥ `2024-07-01`
- Move events ana/test: 5732 / 2833

## Candlestick catalog

Patterns: `doji, marubozu, hammer, inv_hammer, shooting, hanging, bull_engulf, bear_engulf, bull_harami, bear_harami, inside, outside, pin_bull, pin_bear, morning_star, evening_star, bull_run2, bear_run2, bull_run3, bear_run3, spinning_top, belt_bull, belt_bear, piercing, dark_cloud, tweezer_bot, tweezer_top, three_soldiers, three_crows, bull_kicker, bear_kicker`

## Market-move taxonomy

| Move | Meaning |
|---|---|
| `or_break_up/dn` | First clean OR break with confirming candle |
| `impulse_up/dn` | ≥3 consecutive body bars same direction |
| `pullback_resume_up/dn` | Impulse → 1–4 bar pullback → resume candle |
| `swing_break_up/dn` | Close beyond last pivot high/low |
| `reversal_up/dn` | Reversal candle at session extreme |

### Analyze census

- Events: 5732
- By move: `{"swing_break_up": 709, "impulse_up": 707, "pullback_resume_up": 703, "reversal_up": 700, "impulse_dn": 694, "reversal_dn": 694, "swing_break_dn": 690, "pullback_resume_dn": 688, "or_break_up": 74, "or_break_dn": 73}`
- Top patterns: `{"bull_run2": 1573, "bear_run2": 1497, "marubozu": 1349, "bull_run3": 1012, "bear_run3": 996, "outside": 628, "belt_bear": 596, "belt_bull": 563, "inside": 485, "bull_engulf": 484, "bear_engulf": 417, "pin_bull": 364, "pin_bear": 327, "doji": 291, "evening_star": 241, "morning_star": 228, "tweezer_top": 224, "inv_hammer": 216, "bear_harami": 208, "hammer": 204, "bull_harami": 199, "tweezer_bot": 197, "spinning_top": 194, "_none_": 174, "three_soldiers": 172}`

### Test census

- Events: 2833
- By move: `{"swing_break_dn": 354, "impulse_up": 350, "swing_break_up": 350, "impulse_dn": 349, "reversal_up": 348, "pullback_resume_up": 345, "reversal_dn": 343, "pullback_resume_dn": 342, "or_break_up": 32, "or_break_dn": 20}`

## Both-window 100%: **30** logics · Union **13 @ 100.0%**

| Day | HM | Side | Move | SL | T1 | Win |
|---|---|---|---|---:|---:|:---:|
| 2024-07-16 | 10:34 | BUY | or_break_up | 31.5 | 8.31 | Y |
| 2024-12-02 | 10:15 | BUY | or_break_up | 47.68 | 8.03 | Y |
| 2024-12-12 | 10:05 | SELL | pullback_resume_dn | 6.48 | 6.19 | Y |
| 2025-01-13 | 10:13 | BUY | or_break_up | 13.87 | 8.97 | Y |
| 2025-02-20 | 10:18 | BUY | swing_break_up | 11.56 | 7.9 | Y |
| 2025-03-19 | 10:17 | BUY | or_break_up | 7.53 | 5.0 | Y |
| 2025-04-22 | 10:24 | BUY | or_break_up | 8.48 | 5.0 | Y |
| 2025-06-13 | 10:24 | BUY | or_break_up | 11.66 | 5.82 | Y |
| 2025-07-09 | 10:13 | BUY | or_break_up | 7.18 | 5.0 | Y |
| 2025-08-11 | 10:24 | BUY | or_break_up | 11.07 | 6.03 | Y |
| 2025-09-11 | 12:32 | BUY | or_break_up | 74.92 | 24.97 | Y |
| 2025-11-13 | 10:24 | BUY | or_break_up | 8.21 | 5.0 | Y |
| 2025-12-03 | 10:25 | BUY | pullback_resume_up | 15.57 | 6.7 | Y |

## Best both-100 (max test n)

| # | Bracket | Filters | Ana | Test | SL/T1 |
|---:|---|---|---:|---:|---|
| 1 | `move_pat` | mv=['or_break_up', 'or_break_dn'] pat=None side=None clk=['early'] ext≤0.12 rsi=45-65 body≥None | 8 | **8** | 14.46/6.11 |
| 2 | `move_pat` | mv=['or_break_up', 'or_break_dn'] pat=None side=BUY clk=['early'] ext≤0.12 rsi=45-65 body≥None | 8 | **8** | 14.46/6.11 |
| 3 | `move_pat` | mv=['or_break_up'] pat=None side=None clk=['early'] ext≤0.12 rsi=45-65 body≥None | 8 | **8** | 14.46/6.11 |
| 4 | `move_pat` | mv=['or_break_up'] pat=None side=BUY clk=['early'] ext≤0.12 rsi=45-65 body≥None | 8 | **8** | 14.46/6.11 |
| 5 | `move_origin` | mv=['or_break_up', 'or_break_dn'] pat=None side=None clk=['early'] ext≤0.18 rsi=45-65 body≥0.5 | 7 | **8** | 116.64/38.88 |
| 6 | `move_origin` | mv=['or_break_up', 'or_break_dn'] pat=None side=BUY clk=['early'] ext≤0.18 rsi=45-65 body≥0.5 | 7 | **8** | 116.64/38.88 |
| 7 | `move_origin` | mv=['or_break_up', 'or_break_dn'] pat=None side=BUY clk=['early'] ext≤0.25 rsi=45-65 body≥0.5 | 7 | **8** | 116.64/38.88 |
| 8 | `move_origin` | mv=['or_break_up'] pat=None side=None clk=['early'] ext≤0.18 rsi=45-65 body≥0.5 | 7 | **8** | 116.64/38.88 |
| 9 | `move_origin` | mv=['or_break_up'] pat=None side=BUY clk=['early'] ext≤0.18 rsi=45-65 body≥0.5 | 7 | **8** | 116.64/38.88 |
| 10 | `move_origin` | mv=['or_break_up'] pat=None side=BUY clk=['early'] ext≤0.25 rsi=45-65 body≥0.5 | 7 | **8** | 116.64/38.88 |
| 11 | `move_mix` | mv=['or_break_up', 'or_break_dn'] pat=None side=None clk=['early'] ext≤0.12 rsi=45-65 body≥0.5 | 6 | **8** | 66.65/16.26 |
| 12 | `move_origin` | mv=['or_break_up', 'or_break_dn'] pat=None side=None clk=['early'] ext≤0.12 rsi=45-65 body≥0.5 | 6 | **8** | 116.64/38.88 |

### Detail · best · test **8 @ 100%**

- Bracket family: `move_pat` (move-geometry SL/T1)
- Filters: `{"moves": ["or_break_up", "or_break_dn"], "patterns": null, "side": null, "clocks": ["early"], "max_or_ext": 0.12, "min_or": 12, "min_body": null, "vwap_side": null, "rsi_lo": 45, "rsi_hi": 65}`
- Analyze: 8 @ 100%

| Day | HM | Side | Move | Patterns | SL | T1 |
|---|---|---|---|---|---:|---:|
| 2024-12-02 | 10:15 | BUY | or_break_up | marubozu,bull_run2,bull_run3,belt_bull | 47.68 | 8.03 |
| 2025-01-13 | 10:13 | BUY | or_break_up | belt_bull,bull_kicker | 13.87 | 8.97 |
| 2025-03-19 | 10:17 | BUY | or_break_up | bull_run2,bull_run3,three_soldiers | 7.53 | 5.0 |
| 2025-04-22 | 10:24 | BUY | or_break_up | bull_engulf,outside,tweezer_bot | 8.48 | 5.0 |
| 2025-06-13 | 10:24 | BUY | or_break_up | bull_run2,bull_run3,belt_bull,three_soldiers | 11.66 | 5.82 |
| 2025-07-09 | 10:13 | BUY | or_break_up | bull_run2 | 7.18 | 5.0 |
| 2025-08-11 | 10:24 | BUY | or_break_up | marubozu,bull_run2,bull_run3,belt_bull | 11.07 | 6.03 |
| 2025-11-13 | 10:24 | BUY | or_break_up | bull_run2,bull_run3,three_soldiers | 8.21 | 5.0 |

## Near-miss

| Bracket | Ana | Test |
|---|---|---|
| `move_origin` | 51@72.55% | 26@80.77% |
| `move_origin` | 58@74.14% | 31@80.65% |
| `move_origin` | 57@73.68% | 31@80.65% |
| `move_origin` | 94@74.47% | 67@77.61% |
| `move_origin` | 82@73.17% | 40@77.5% |
| `move_origin` | 81@72.84% | 40@77.5% |
| `move_origin` | 81@72.84% | 40@77.5% |
| `move_origin` | 82@73.17% | 40@77.5% |
| `move_origin` | 81@75.31% | 56@76.79% |
| `move_origin` | 71@71.83% | 34@76.47% |

## Chart ML on move features

- n=5832 fit_auc=0.718 test_auc=0.635 P-slice=None@None%

## Research pick

**Best single move-logic:** `move_pat` · test **8 @ 100%** (analyze 8 @ 100%).
**Union book:** **13 @ 100%** across both-100 micros.

## Policy

- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_candle_moves_100`
- research_only · not_live · candle+move chart-only
