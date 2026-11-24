# NIFTY 1m — Last 3 months pattern + accurate-logic integration

**Not live.** Textbook candles on last 3m + OR/swing/RSI accurate-style gates.

- Window: `2026-08-06` → `2026-11-06` (last 3m)
- Calibrate: `2026-02-06` → `2026-08-05`
- Events cal/test: 26 / 16

## Last-3m pattern census

- Bars: 24000 · coverage 93.81%
- Top patterns: `{"bear_run2": 7556, "long_line": 5064, "bull_run2": 4636, "spinning_top": 4542, "bear_run3": 4466, "inside_bar": 3762, "outside_bar": 3095, "doji": 2255, "belt_bear": 2193, "bull_run3": 2164, "bull_harami": 1791, "bear_engulf": 1744, "short_line": 1681, "marubozu": 1509, "long_legged_doji": 1159}`

## Baseline (proven chart logic on last 3m)

- `swing_1.1/0.7` + RSI 45–65 + OR ext≤0.15 → **1 @ 100.0%** (avg SL/T1 67.49/5.22)

| Day | HM | Side | Primary | SL | T1 | Win |
|---|---|---|---|---:|---:|:---:|
| 2026-10-01 | 10:01 | BUY | three_soldiers | 67.49 | 5.22 | Y |

## Last-3m @ 100%: **20** logics · Union **16 @ 100.0%**

| Day | HM | Side | Primary | SL | T1 |
|---|---|---|---|---:|---:|
| 2026-08-17 | 10:11 | SELL | bear_run2 | 130.2 | 6.55 |
| 2026-08-18 | 10:15 | SELL | marubozu_bear | 130.2 | 6.55 |
| 2026-08-20 | 12:47 | BUY | bull_run3 | 130.2 | 6.55 |
| 2026-08-25 | 10:22 | SELL | belt_bear | 130.2 | 6.55 |
| 2026-09-02 | 10:30 | BUY | bull_run2 | 130.2 | 6.55 |
| 2026-09-03 | 11:04 | SELL | bear_run3 | 130.2 | 6.55 |
| 2026-09-09 | 10:00 | SELL | marubozu_bear | 130.2 | 6.55 |
| 2026-09-10 | 10:02 | SELL | three_crows | 130.2 | 6.55 |
| 2026-09-11 | 10:08 | BUY | long_line | 130.2 | 6.55 |
| 2026-09-22 | 10:32 | SELL | marubozu_bear | 130.2 | 6.55 |
| 2026-09-23 | 10:45 | BUY | bull_run2 | 130.2 | 6.55 |
| 2026-09-24 | 10:22 | SELL | bear_run3 | 130.2 | 6.55 |
| 2026-09-30 | 10:05 | BUY | marubozu_bull | 130.2 | 6.55 |
| 2026-10-01 | 10:01 | BUY | three_soldiers | 130.2 | 6.55 |
| 2026-10-19 | 12:03 | SELL | bear_engulf | 130.2 | 6.55 |
| 2026-10-22 | 10:22 | BUY | marubozu_bull | 130.2 | 9.14 |

### Best last-3m 100% books

| # | Bracket | Filters | Cal | Last3m |
|---:|---|---|---:|---:|
| 1 | `mae_p85_30` | side=None clk=None ext≤0.25 rsi=None-None agreePat=False pri=None | 26@88.46% | **16@100.0%** |
| 2 | `mae_p85_30` | side=None clk=None ext≤0.25 rsi=None-None agreePat=False pri=None | 26@88.46% | **16@100.0%** |
| 3 | `mae_p85_30` | side=None clk=None ext≤0.25 rsi=None-None agreePat=False pri=None | 26@88.46% | **16@100.0%** |
| 4 | `swing_1_1_0_7` | side=None clk=None ext≤0.25 rsi=None-None agreePat=False pri=None | 26@76.92% | **16@100.0%** |
| 5 | `swing_1_05_0_8` | side=None clk=None ext≤0.25 rsi=None-None agreePat=False pri=None | 26@76.92% | **16@100.0%** |
| 6 | `mae_p80_35` | side=None clk=None ext≤0.25 rsi=None-None agreePat=False pri=None | 26@76.92% | **16@100.0%** |
| 7 | `swing_1_1_0_7` | side=None clk=None ext≤0.25 rsi=None-None agreePat=False pri=None | 26@76.92% | **16@100.0%** |
| 8 | `swing_1_05_0_8` | side=None clk=None ext≤0.25 rsi=None-None agreePat=False pri=None | 26@76.92% | **16@100.0%** |
| 9 | `mae_p80_35` | side=None clk=None ext≤0.25 rsi=None-None agreePat=False pri=None | 26@76.92% | **16@100.0%** |
| 10 | `swing_1_1_0_7` | side=None clk=None ext≤0.25 rsi=None-None agreePat=False pri=None | 26@76.92% | **16@100.0%** |

## Balanced (cal≥85% & last3m≥85%) — integrate candidates

| # | Bracket | Cal | Last3m | Key gates |
|---:|---|---:|---:|---|
| 1 | `mae_p80_35` | 5@100.0% | 6@100.0% | rsi=None-None agree=False ext≤0.2 |
| 2 | `mae_p85_30` | 5@100.0% | 6@100.0% | rsi=None-None agree=False ext≤0.2 |
| 3 | `mae_p80_35` | 5@100.0% | 6@100.0% | rsi=None-None agree=False ext≤0.2 |
| 4 | `mae_p85_30` | 5@100.0% | 6@100.0% | rsi=None-None agree=False ext≤0.2 |
| 5 | `mae_p80_35` | 5@100.0% | 6@100.0% | rsi=None-None agree=False ext≤0.2 |
| 6 | `mae_p85_30` | 5@100.0% | 6@100.0% | rsi=None-None agree=False ext≤0.2 |
| 7 | `mae_p80_35` | 5@100.0% | 6@100.0% | rsi=None-None agree=False ext≤0.25 |
| 8 | `mae_p85_30` | 5@100.0% | 6@100.0% | rsi=None-None agree=False ext≤0.25 |
| 9 | `mae_p80_35` | 5@100.0% | 6@100.0% | rsi=None-None agree=False ext≤0.25 |
| 10 | `mae_p85_30` | 5@100.0% | 6@100.0% | rsi=None-None agree=False ext≤0.25 |

## How to integrate into accurate logic (research design)

1. **Entry stack (AND):** OR first-break clean · body agrees · optional RSI band · **textbook pattern agrees with side**.
2. **SL/T1:** swing geometry (`1.1× / 0.7×`) or MAE/MFE percentiles from calibrate window — **not** hardcoded ±30.
3. **Research accurate_tag:** e.g. `ACC_RESEARCH_1M_PATTERN_V1` with measured last-3m / calibrate ranges.
4. **UI merge:** same as live desks — key `(day, side, hm)`; merge tags; highest-accuracy desk first via `collapse_to_ui_calls`.
5. **Do not wire live** until promote pack + freeze split signed off.

### Proposed research tag mapping

| accurate_tag | When | Brackets |
|---|---|---|
| `ACC_RESEARCH_1M_SWING_RSI` | RSI 45–65 · OR ext≤0.15 · swing SL/T1 | chart swing |
| `ACC_RESEARCH_1M_PATTERN_AGREE` | + bullish/bearish textbook pattern agrees | swing or MAE |
| `ACC_RESEARCH_1M_PATTERN_UNION` | union of last-3m 100% micros | per-micro |

## Research pick

**Sample note:** only **16** clean OR first-breaks in last 3m — treat 100% books as research, not promote-ready.

**Wide MAE `p85/30` (SL≈130 / T1≈6.5)** can mark all 16 @ 100% but R:R is poor — use only as upper-bound coverage, not the integrate path.

**Integrate candidate (both windows 100%):** `mae_p80_35` · **SELL · early · OR ext≤0.20**  
→ cal **5 @ 100%** · last3m **6 @ 100%** (avg SL/T1 ≈ 104 / 10.5)

**Strict accurate-style baseline:** swing `1.1/0.7` + RSI 45–65 → **1 @ 100%** last3m (`2026-10-01` BUY · `three_soldiers`).

**Practical integrate stack for high-accuracy calls:**
1. OR first-break + body agree  
2. Textbook pattern agrees with side (`agree_pat`) — almost all last-3m winners already had this  
3. Prefer **early** clock; optional RSI band for fewer/higher-conviction  
4. SL/T1 from calibrate MAE or swing geometry  
5. Emit research tag → merge via `collapse_to_ui_calls` — **not live until freeze/promote**

## Policy

- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_last3m_pattern`
- research_only · not_live · last3m pattern integrate
